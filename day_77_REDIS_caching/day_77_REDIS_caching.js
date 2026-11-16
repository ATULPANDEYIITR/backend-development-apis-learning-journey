'use strict';

/**
 * Redis Caching Engineering Model
 *
 * Node.js implementation of:
 * - Cache-aside
 * - Write-through
 * - TTL expiration
 * - Cache invalidation
 * - Concurrent request deduplication
 * - Event-driven cache monitoring
 * - Database fallback
 *
 * Run:
 *   node redis_caching.js
 *
 * This program uses an in-memory Redis-style adapter so it runs without
 * installing Redis or third-party npm packages.
 */

const { EventEmitter } = require('node:events');
const fs = require('node:fs/promises');
const path = require('node:path');
const { performance } = require('node:perf_hooks');


class ValidationError extends Error {}
class CacheUnavailableError extends Error {}
class RepositoryError extends Error {}


const Strategy = Object.freeze({
    CACHE_ASIDE: 'CACHE_ASIDE',
    WRITE_THROUGH: 'WRITE_THROUGH'
});


function validateProduct(product) {
    if (!product || typeof product !== 'object') {
        throw new ValidationError('Product must be an object.');
    }

    if (!Number.isInteger(product.id) || product.id <= 0) {
        throw new ValidationError('Invalid product ID.');
    }

    if (typeof product.name !== 'string' || !product.name.trim()) {
        throw new ValidationError('Product name is required.');
    }

    if (
        typeof product.price !== 'number' ||
        !Number.isFinite(product.price) ||
        product.price < 0
    ) {
        throw new ValidationError('Invalid product price.');
    }

    return true;
}


class Metrics {
    constructor() {
        this.values = {
            hits: 0,
            misses: 0,
            writes: 0,
            invalidations: 0,
            expirations: 0,
            originReads: 0,
            failures: 0
        };
    }

    increment(name, amount = 1) {
        if (!(name in this.values)) {
            throw new ValidationError(`Unknown metric: ${name}`);
        }

        this.values[name] += amount;
    }

    snapshot() {
        const total = this.values.hits + this.values.misses;

        return {
            ...this.values,
            hitRate: total
                ? Number((this.values.hits / total).toFixed(4))
                : 0
        };
    }
}


class MemoryRedis extends EventEmitter {
    constructor(defaultTTLSeconds = 30) {
        super();

        if (!Number.isFinite(defaultTTLSeconds) ||
            defaultTTLSeconds <= 0) {
            throw new ValidationError('TTL must be positive.');
        }

        this.defaultTTL = defaultTTLSeconds;
        this.entries = new Map();
        this.metrics = new Metrics();
        this.available = true;
    }

    validateKey(key) {
        if (
            typeof key !== 'string' ||
            !key.trim() ||
            key.length > 512 ||
            /[\x00-\x1f]/.test(key)
        ) {
            throw new ValidationError('Invalid cache key.');
        }
    }

    assertAvailable() {
        if (!this.available) {
            this.metrics.increment('failures');
            throw new CacheUnavailableError('Redis is unavailable.');
        }
    }

    async get(key) {
        this.validateKey(key);
        this.assertAvailable();

        const entry = this.entries.get(key);

        if (!entry) {
            this.metrics.increment('misses');
            this.emit('cache:miss', { key });
            return null;
        }

        if (
            entry.expiresAt !== null &&
            performance.now() >= entry.expiresAt
        ) {
            this.entries.delete(key);
            this.metrics.increment('expirations');
            this.metrics.increment('misses');

            this.emit('cache:expired', { key });
            return null;
        }

        this.metrics.increment('hits');
        this.emit('cache:hit', { key });

        // Return a copy to prevent external mutation of cached state.
        return structuredClone(entry.value);
    }

    async set(key, value, ttl = this.defaultTTL) {
        this.validateKey(key);
        this.assertAvailable();

        if (!Number.isFinite(ttl) || ttl <= 0) {
            throw new ValidationError('TTL must be positive.');
        }

        this.entries.set(key, {
            value: structuredClone(value),
            createdAt: performance.now(),
            expiresAt: performance.now() + ttl * 1000
        });

        this.metrics.increment('writes');

        this.emit('cache:set', { key, ttl });

        return 'OK';
    }

    async delete(key) {
        this.validateKey(key);
        this.assertAvailable();

        const deleted = this.entries.delete(key);

        if (deleted) {
            this.metrics.increment('invalidations');
            this.emit('cache:invalidated', { key });
        }

        return deleted;
    }

    async deletePrefix(prefix) {
        this.validateKey(prefix);
        this.assertAvailable();

        let deleted = 0;

        for (const key of this.entries.keys()) {
            if (key.startsWith(prefix)) {
                this.entries.delete(key);
                deleted++;
            }
        }

        this.metrics.increment('invalidations', deleted);

        return deleted;
    }

    async cleanupExpired() {
        this.assertAvailable();

        const now = performance.now();
        let removed = 0;

        for (const [key, entry] of this.entries) {
            if (entry.expiresAt !== null && now >= entry.expiresAt) {
                this.entries.delete(key);
                removed++;
            }
        }

        this.metrics.increment('expirations', removed);

        return removed;
    }

    setAvailability(available) {
        this.available = Boolean(available);

        this.emit('cache:availability', {
            available: this.available
        });
    }
}


class ProductRepository {
    constructor() {
        this.products = new Map();
        this.nextId = 1;
        this.readCount = 0;
    }

    async create(name, price) {
        const product = {
            id: this.nextId++,
            name,
            price,
            version: 1
        };

        validateProduct(product);

        this.products.set(product.id, product);

        return structuredClone(product);
    }

    async findById(id) {
        this.readCount++;

        const product = this.products.get(id);

        return product ? structuredClone(product) : null;
    }

    async update(id, changes) {
        const current = this.products.get(id);

        if (!current) {
            return null;
        }

        const updated = {
            ...current,
            ...changes,
            id,
            version: current.version + 1
        };

        validateProduct(updated);

        this.products.set(id, updated);

        return structuredClone(updated);
    }

    async delete(id) {
        return this.products.delete(id);
    }
}


class CacheService {
    constructor(repository, redis) {
        this.repository = repository;
        this.redis = redis;

        // Concurrent requests for the same missing key share one operation.
        this.inFlight = new Map();
    }

    key(id) {
        if (!Number.isInteger(id) || id <= 0) {
            throw new ValidationError('Invalid product ID.');
        }

        return `products:${id}`;
    }

    async readFromOrigin(id) {
        this.redis.metrics.increment('originReads');
        return this.repository.findById(id);
    }

    async getProduct(id) {
        const key = this.key(id);

        try {
            const cached = await this.redis.get(key);

            if (cached !== null) {
                return cached;
            }
        } catch (error) {
            if (!(error instanceof CacheUnavailableError)) {
                throw error;
            }

            console.warn('Redis read failed. Using database fallback.');

            return this.readFromOrigin(id);
        }

        if (this.inFlight.has(key)) {
            return structuredClone(await this.inFlight.get(key));
        }

        const operation = (async () => {
            const secondCheck = await this.redis.get(key);

            if (secondCheck !== null) {
                return secondCheck;
            }

            const product = await this.readFromOrigin(id);

            if (product !== null) {
                try {
                    await this.redis.set(key, product, 30);
                } catch (error) {
                    if (!(error instanceof CacheUnavailableError)) {
                        throw error;
                    }

                    console.warn('Cache population failed.');
                }
            }

            return product;
        })();

        this.inFlight.set(key, operation);

        try {
            return await operation;
        } catch (error) {
            if (error instanceof CacheUnavailableError) {
                return this.readFromOrigin(id);
            }

            throw error;
        } finally {
            this.inFlight.delete(key);
        }
    }

    async updateProduct(id, changes, strategy) {
        if (!Object.values(Strategy).includes(strategy)) {
            throw new ValidationError('Unknown caching strategy.');
        }

        const updated = await this.repository.update(id, changes);

        if (!updated) {
            return null;
        }

        const key = this.key(id);

        if (strategy === Strategy.WRITE_THROUGH) {
            try {
                await this.redis.set(key, updated, 30);
            } catch (error) {
                if (!(error instanceof CacheUnavailableError)) {
                    throw error;
                }

                // Best-effort invalidation prevents serving an older value.
                try {
                    await this.redis.delete(key);
                } catch {
                    console.error(
                        'Write-through failed and invalidation is unavailable.'
                    );
                }
            }
        }

        if (strategy === Strategy.CACHE_ASIDE) {
            try {
                await this.redis.delete(key);
            } catch (error) {
                if (!(error instanceof CacheUnavailableError)) {
                    throw error;
                }

                console.error(
                    'Invalidation failed. Stale data may survive until TTL.'
                );
            }
        }

        return updated;
    }

    async deleteProduct(id) {
        const deleted = await this.repository.delete(id);

        if (deleted) {
            try {
                await this.redis.delete(this.key(id));
            } catch (error) {
                console.error('Deletion invalidation failed:', error.message);
            }
        }

        return deleted;
    }
}


async function persistMetrics(metrics, filename) {
    const destination = path.resolve(filename);
    const temporary = `${destination}.tmp`;

    try {
        await fs.writeFile(
            temporary,
            JSON.stringify(metrics, null, 2),
            { encoding: 'utf8', mode: 0o600 }
        );

        await fs.rename(temporary, destination);
    } catch (error) {
        console.error('Metrics persistence failed:', error.message);

        try {
            await fs.unlink(temporary);
        } catch {
            // Temporary file may not exist.
        }
    }
}


async function main() {
    const redis = new MemoryRedis(30);
    const repository = new ProductRepository();
    const service = new CacheService(repository, redis);

    redis.on('cache:hit', ({ key }) => {
        console.log(`[EVENT] Cache hit: ${key}`);
    });

    redis.on('cache:miss', ({ key }) => {
        console.log(`[EVENT] Cache miss: ${key}`);
    });

    redis.on('cache:invalidated', ({ key }) => {
        console.log(`[EVENT] Invalidated: ${key}`);
    });

    redis.on('cache:expired', ({ key }) => {
        console.log(`[EVENT] Expired: ${key}`);
    });

    console.log('\nREDIS CACHING DEMONSTRATION');
    console.log('='.repeat(55));

    const product = await repository.create('Cloud Server', 75000);

    console.log('\n1. Initial cache-aside request:');
    console.log(await service.getProduct(product.id));

    console.log('\n2. Repeated cache request:');
    console.log(await service.getProduct(product.id));

    console.log('\n3. Write-through update:');
    console.log(await service.updateProduct(
        product.id,
        { name: 'Cloud Server Pro', price: 95000 },
        Strategy.WRITE_THROUGH
    ));

    console.log('\n4. Cache-aside update:');
    console.log(await service.updateProduct(
        product.id,
        { name: 'Cloud Server Enterprise', price: 110000 },
        Strategy.CACHE_ASIDE
    ));

    console.log('\n5. Read after invalidation:');
    console.log(await service.getProduct(product.id));

    console.log('\n6. Concurrent cache requests:');

    const before = repository.readCount;

    const concurrentResults = await Promise.all(
        Array.from({ length: 10 }, () => service.getProduct(product.id))
    );

    console.log('Requests:', concurrentResults.length);
    console.log('Additional database reads:', repository.readCount - before);

    console.log('\n7. TTL expiration:');

    await redis.set('session:1001', { user: 'employee' }, 1);

    console.log('Before expiration:', await redis.get('session:1001'));

    await new Promise(resolve => setTimeout(resolve, 1100));

    console.log('After expiration:', await redis.get('session:1001'));

    console.log('\n8. Redis outage:');

    redis.setAvailability(false);

    console.log('Database fallback:', await service.getProduct(product.id));

    redis.setAvailability(true);

    console.log('\n9. Cache cleanup:');
    console.log('Expired entries removed:', await redis.cleanupExpired());

    console.log('\n10. Cache invalidation after deletion:');
    console.log('Deleted:', await service.deleteProduct(product.id));

    console.log('\n11. Operational metrics:');

    const metrics = redis.metrics.snapshot();

    console.log(metrics);

    await persistMetrics(metrics, 'redis_cache_metrics.json');

    if (metrics.hits < 1 || metrics.misses < 1) {
        throw new Error('Expected cache hits and misses were not recorded.');
    }

    console.log('\nAll demonstrations completed successfully.');
}


main().catch(error => {
    console.error('Application failure:', error);
    process.exitCode = 1;
});
