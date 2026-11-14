'use strict';

/**
 * API Caching Engine
 *
 * Implements HTTP caching behavior using Node.js standard capabilities.
 * Includes asynchronous origin requests, single-flight revalidation,
 * ETags, conditional requests, Vary, TTL, invalidation and event logging.
 */

const { EventEmitter } = require('node:events');
const crypto = require('node:crypto');

class CacheError extends Error {}
class ValidationError extends CacheError {}

const CacheState = Object.freeze({
    HIT: 'HIT',
    MISS: 'MISS',
    REVALIDATED: 'REVALIDATED',
    BYPASS: 'BYPASS',
    EXPIRED: 'EXPIRED'
});

function validateUrl(value) {
    let url;

    try {
        url = new URL(value);
    } catch {
        throw new ValidationError('Invalid URL');
    }

    if (!['http:', 'https:'].includes(url.protocol)) {
        throw new ValidationError('Unsupported protocol');
    }

    if (url.username || url.password) {
        throw new ValidationError('URL credentials are forbidden');
    }

    url.hash = '';

    return url;
}

function parseCacheControl(header = '') {
    if (header.length > 4096) {
        throw new ValidationError('Cache-Control is too large');
    }

    const directives = new Map();

    for (const segment of header.split(',')) {
        const item = segment.trim();

        if (!item) continue;

        const separator = item.indexOf('=');
        const key = (
            separator === -1 ? item : item.slice(0, separator)
        ).trim().toLowerCase();

        let value = separator === -1
            ? true
            : item.slice(separator + 1).trim().replace(/^"|"$/g, '');

        if (!/^[a-z][a-z0-9-]*$/.test(key)) {
            throw new ValidationError('Invalid directive');
        }

        if (directives.has(key)) {
            throw new ValidationError(`Duplicate directive: ${key}`);
        }

        directives.set(key, value);
    }

    function number(name, fallback = 0) {
        if (!directives.has(name)) return fallback;

        const value = directives.get(name);

        if (!/^\d+$/.test(String(value))) {
            throw new ValidationError(`Invalid ${name}`);
        }

        const parsed = Number(value);

        if (!Number.isSafeInteger(parsed)) {
            throw new ValidationError(`${name} exceeds safe integer`);
        }

        return parsed;
    }

    return Object.freeze({
        maxAge: number('max-age', null),
        sMaxAge: number('s-maxage', null),
        staleWhileRevalidate: number('stale-while-revalidate'),
        noStore: directives.has('no-store'),
        noCache: directives.has('no-cache'),
        private: directives.has('private'),
        public: directives.has('public'),
        mustRevalidate: directives.has('must-revalidate'),
        immutable: directives.has('immutable')
    });
}

function createETag(body) {
    const serialized = JSON.stringify(body);

    const hash = crypto
        .createHash('sha256')
        .update(serialized)
        .digest('hex');

    return `"${hash}"`;
}

function matchesETag(header, current) {
    if (!header || !current) return false;

    if (header.trim() === '*') return true;

    const normalized = current.replace(/^W\//, '');

    return header.split(',').some(candidate => {
        return candidate.trim().replace(/^W\//, '') === normalized;
    });
}

function cloneResponse(response) {
    return {
        status: response.status,
        body: response.body === null
            ? null
            : structuredClone(response.body),
        headers: { ...response.headers }
    };
}

class ResourceOrigin {
    constructor() {
        this.resources = new Map();
        this.requestCount = 0;
    }

    publish(path, body, cacheControl = 'public, max-age=20') {
        if (!path.startsWith('/')) {
            throw new ValidationError('Absolute resource path required');
        }

        this.resources.set(path, {
            body: structuredClone(body),
            modified: Date.now(),
            cacheControl
        });
    }

    async fetch(path, requestHeaders = {}) {
        this.requestCount++;

        // Simulates an asynchronous origin service.
        await new Promise(resolve => setImmediate(resolve));

        const resource = this.resources.get(path);

        if (!resource) {
            return {
                status: 404,
                body: { error: 'Not found' },
                headers: {}
            };
        }

        const etag = createETag(resource.body);

        const headers = {
            'ETag': etag,
            'Last-Modified': new Date(
                Math.floor(resource.modified / 1000) * 1000
            ).toUTCString(),
            'Cache-Control': resource.cacheControl,
            'Content-Type': 'application/json'
        };

        const inm = requestHeaders['if-none-match'];

        if (inm !== undefined) {
            if (matchesETag(inm, etag)) {
                return { status: 304, body: null, headers };
            }
        } else if (requestHeaders['if-modified-since']) {
            const since = Date.parse(
                requestHeaders['if-modified-since']
            );

            if (
                Number.isFinite(since) &&
                Math.floor(resource.modified / 1000) * 1000 <= since
            ) {
                return { status: 304, body: null, headers };
            }
        }

        return {
            status: 200,
            body: structuredClone(resource.body),
            headers
        };
    }
}

class APICache extends EventEmitter {
    constructor(origin, options = {}) {
        super();

        this.origin = origin;
        this.capacity = options.capacity ?? 500;
        this.shared = options.shared ?? true;

        if (!Number.isInteger(this.capacity) || this.capacity < 1) {
            throw new ValidationError('Invalid capacity');
        }

        this.entries = new Map();
        this.pending = new Map();
        this.statistics = {
            hits: 0,
            misses: 0,
            revalidations: 0,
            bypasses: 0,
            evictions: 0
        };
    }

    _key(url, requestHeaders, userId) {
        const identity = this.shared ? 'shared' : userId ?? 'anonymous';

        return `${identity}:${url.href}`;
    }

    _varyKey(base, vary, requestHeaders) {
        return base + ':' + JSON.stringify(
            vary.map(name => requestHeaders[name] ?? '')
        );
    }

    _find(base, requestHeaders) {
        for (const [key, entry] of this.entries) {
            if (entry.base !== base) continue;

            const candidate = this._varyKey(
                base,
                entry.vary,
                requestHeaders
            );

            if (candidate === key) {
                // Map insertion order provides LRU behavior.
                this.entries.delete(key);
                this.entries.set(key, entry);
                return { key, entry };
            }
        }

        return null;
    }

    _makeEntry(response, requestHeaders, base, previous = null) {
        if (response.status !== 200) return null;

        const headers = response.headers;
        const policy = parseCacheControl(
            headers['Cache-Control'] ?? ''
        );

        if (policy.noStore) return null;

        if (this.shared && policy.private) return null;

        const vary = (headers.Vary ?? '')
            .split(',')
            .map(x => x.trim().toLowerCase())
            .filter(Boolean)
            .sort();

        if (vary.includes('*')) return null;

        for (const field of vary) {
            if (!/^[a-z0-9-]+$/.test(field)) {
                throw new ValidationError('Invalid Vary field');
            }
        }

        const freshness = this.shared
            ? policy.sMaxAge ?? policy.maxAge ?? 0
            : policy.maxAge ?? 0;

        const age = Math.max(0, Number(headers.Age ?? 0) || 0);

        return {
            base,
            response: cloneResponse(response),
            etag: headers.ETag ?? null,
            lastModified: headers['Last-Modified'] ?? null,
            vary,
            varyValues: vary.map(x => requestHeaders[x] ?? ''),
            freshness,
            initialAge: age,
            storedAt: Date.now(),
            mustRevalidate: policy.mustRevalidate,
            staleWhileRevalidate: policy.staleWhileRevalidate,
            generation: previous?.generation ?? 0
        };
    }

    _fresh(entry) {
        const age = entry.initialAge +
            (Date.now() - entry.storedAt) / 1000;

        return age < entry.freshness;
    }

    _store(base, entry, requestHeaders) {
        const key = this._varyKey(base, entry.vary, requestHeaders);

        this.entries.set(key, entry);

        while (this.entries.size > this.capacity) {
            const oldest = this.entries.keys().next().value;
            this.entries.delete(oldest);
            this.statistics.evictions++;
            this.emit('eviction', oldest);
        }
    }

    async request(value, options = {}) {
        const url = validateUrl(value);
        const method = (options.method ?? 'GET').toUpperCase();

        if (!['GET', 'HEAD'].includes(method)) {
            this.statistics.bypasses++;
            return {
                response: await this.origin.fetch(
                    url.pathname + url.search,
                    options.headers
                ),
                state: CacheState.BYPASS
            };
        }

        const headers = Object.fromEntries(
            Object.entries(options.headers ?? {}).map(
                ([key, value]) => [key.toLowerCase(), value]
            )
        );

        if (this.shared && headers.authorization) {
            this.statistics.bypasses++;

            return {
                response: await this.origin.fetch(
                    url.pathname + url.search,
                    headers
                ),
                state: CacheState.BYPASS
            };
        }

        if (/no-store/i.test(headers['cache-control'] ?? '')) {
            this.statistics.bypasses++;

            return {
                response: await this.origin.fetch(
                    url.pathname + url.search,
                    headers
                ),
                state: CacheState.BYPASS
            };
        }

        const base = this._key(
            url,
            headers,
            options.userId
        );

        const found = this._find(base, headers);

        if (found && this._fresh(found.entry) &&
            !/no-cache/i.test(headers['cache-control'] ?? '')) {

            this.statistics.hits++;
            this.emit('hit', { url: url.href });

            const response = cloneResponse(found.entry.response);

            if (method === 'HEAD') response.body = null;

            return { response, state: CacheState.HIT };
        }

        // Requests for the same representation share one origin fetch.
        if (this.pending.has(base)) {
            const result = await this.pending.get(base);

            const refreshed = this._find(base, headers);

            if (refreshed && this._fresh(refreshed.entry)) {
                this.statistics.hits++;

                return {
                    response: method === 'HEAD'
                        ? { ...cloneResponse(refreshed.entry.response), body: null }
                        : cloneResponse(refreshed.entry.response),
                    state: CacheState.HIT
                };
            }

            if (result) {
                return {
                    response: cloneResponse(result.response),
                    state: result.state
                };
            }
        }

        const task = this._fetchAndStore(
            url,
            headers,
            base,
            found
        );

        this.pending.set(base, task);

        try {
            const result = await task;

            const response = cloneResponse(result.response);

            if (method === 'HEAD') response.body = null;

            return { response, state: result.state };
        } finally {
            this.pending.delete(base);
        }
    }

    async _fetchAndStore(url, headers, base, found) {
        this.statistics.misses++;

        const conditional = { ...headers };

        if (found?.entry.etag) {
            conditional['if-none-match'] = found.entry.etag;
        } else if (found?.entry.lastModified) {
            conditional['if-modified-since'] =
                found.entry.lastModified;
        }

        const response = await this.origin.fetch(
            url.pathname + url.search,
            conditional
        );

        if (response.status === 304 && found) {
            const merged = {
                ...found.entry.response.headers,
                ...response.headers
            };

            const updated = this._makeEntry(
                {
                    status: 200,
                    body: found.entry.response.body,
                    headers: merged
                },
                headers,
                base,
                found.entry
            );

            if (updated) {
                this._store(base, updated, headers);
            } else {
                this.entries.delete(found.key);
            }

            this.statistics.revalidations++;
            this.emit('revalidated', { url: url.href });

            return {
                response: {
                    status: 200,
                    body: found.entry.response.body,
                    headers: merged
                },
                state: CacheState.REVALIDATED
            };
        }

        const entry = this._makeEntry(
            response,
            headers,
            base
        );

        if (entry) {
            this._store(base, entry, headers);
        }

        this.emit('miss', {
            url: url.href,
            status: response.status
        });

        return {
            response,
            state: CacheState.MISS
        };
    }

    invalidate(value) {
        const url = validateUrl(value);

        let removed = 0;

        for (const [key, entry] of this.entries) {
            if (entry.base.endsWith(':' + url.href)) {
                this.entries.delete(key);
                removed++;
            }
        }

        this.emit('invalidate', {
            url: url.href,
            removed
        });

        return removed;
    }

    report() {
        return {
            ...this.statistics,
            entries: this.entries.size,
            pendingRequests: this.pending.size
        };
    }
}

async function main() {
    const origin = new ResourceOrigin();

    origin.publish(
        '/api/inventory/500',
        {
            id: 500,
            item: 'Network Router',
            quantity: 42,
            price: 8500
        },
        'public, max-age=30, s-maxage=60, must-revalidate'
    );

    const cache = new APICache(origin, {
        capacity: 100,
        shared: true
    });

    cache.on('hit', event => {
        console.log('CACHE HIT:', event.url);
    });

    cache.on('revalidated', event => {
        console.log('REVALIDATED:', event.url);
    });

    cache.on('invalidate', event => {
        console.log('INVALIDATED:', event);
    });

    const endpoint = 'https://api.example.com/api/inventory/500';

    console.log('\n1. First request');

    let result = await cache.request(endpoint);

    console.log(result.state, result.response.body);

    console.log('\n2. Second request');

    result = await cache.request(endpoint);

    console.log(result.state);

    console.log('\n3. Concurrent requests');

    const concurrent = await Promise.all(
        Array.from({ length: 10 }, () => cache.request(endpoint))
    );

    console.log(
        'Completed:', concurrent.length,
        'Origin calls:', origin.requestCount
    );

    console.log('\n4. Invalidation');

    console.log('Removed:', cache.invalidate(endpoint));

    result = await cache.request(endpoint);

    console.log(result.state, result.response.status);

    console.log('\n5. Cache-Control validation');

    try {
        parseCacheControl('max-age=-20');
    } catch (error) {
        console.log('Rejected:', error.message);
    }

    console.log('\n6. ETag validation');

    const tag = createETag({ revision: 1 });

    console.log(tag, matchesETag(`W/${tag}`, tag));

    console.log('\n7. Statistics');

    console.log(cache.report());
}

main().catch(error => {
    console.error('Application failure:', error.message);
    process.exitCode = 1;
});
