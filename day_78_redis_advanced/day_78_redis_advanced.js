'use strict';

/*
 * Redis Advanced Engineering
 *
 * Topics:
 * 1. Pipelining
 * 2. MULTI / EXEC transactions
 * 3. Lua scripting
 * 4. Distributed locks
 *
 * Runtime: Node.js 18+
 * Dependency: None
 *
 * The RESP2 client uses Node.js TCP sockets.
 */

const net = require('node:net');
const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

// --------------------------------------------------
// Configuration
// --------------------------------------------------

const CONFIG = Object.freeze({
    host: process.env.REDIS_HOST || '127.0.0.1',
    port: Number(process.env.REDIS_PORT || 6379),
    password: process.env.REDIS_PASSWORD || null,
    database: Number(process.env.REDIS_DB || 0),
    timeout: 3000
});

if (!Number.isInteger(CONFIG.port) ||
    CONFIG.port < 1 ||
    CONFIG.port > 65535) {
    throw new Error('Invalid Redis port');
}

if (!Number.isInteger(CONFIG.database) ||
    CONFIG.database < 0) {
    throw new Error('Invalid Redis database');
}

// --------------------------------------------------
// Errors
// --------------------------------------------------

class RedisError extends Error {}
class RedisProtocolError extends RedisError {}
class RedisConnectionError extends RedisError {}
class LockError extends RedisError {}

// --------------------------------------------------
// RESP2 encoding
// --------------------------------------------------

function encodeCommand(parts) {
    if (!Array.isArray(parts) || parts.length === 0) {
        throw new TypeError('A Redis command must contain arguments');
    }

    const buffers = [
        Buffer.from(`*${parts.length}\r\n`)
    ];

    for (const part of parts) {
        if (part === null || part === undefined) {
            throw new TypeError('Null Redis command argument');
        }

        const value = Buffer.from(String(part), 'utf8');

        buffers.push(
            Buffer.from(`$${value.length}\r\n`),
            value,
            Buffer.from('\r\n')
        );
    }

    return Buffer.concat(buffers);
}

// --------------------------------------------------
// RESP2 parser
// --------------------------------------------------

class RESPParser {
    constructor() {
        this.buffer = Buffer.alloc(0);
    }

    feed(chunk) {
        this.buffer = Buffer.concat([this.buffer, chunk]);

        const responses = [];

        while (true) {
            const parsed = this.parseAt(0);

            if (!parsed) break;

            responses.push(parsed.value);
            this.buffer = this.buffer.subarray(parsed.next);
        }

        return responses;
    }

    parseAt(offset) {
        if (offset >= this.buffer.length) return null;

        const type = this.buffer[offset];
        const lineEnd = this.buffer.indexOf('\r\n', offset);

        if (lineEnd === -1) return null;

        const line = this.buffer.toString(
            'utf8',
            offset + 1,
            lineEnd
        );

        const next = lineEnd + 2;

        if (type === 43) {
            return { value: line, next };
        }

        if (type === 45) {
            return {
                value: new RedisProtocolError(line),
                next
            };
        }

        if (type === 58) {
            return {
                value: Number(line),
                next
            };
        }

        if (type === 36) {
            const length = Number(line);

            if (length === -1) {
                return { value: null, next };
            }

            if (!Number.isInteger(length) || length < 0) {
                throw new RedisProtocolError('Invalid bulk length');
            }

            const end = next + length + 2;

            if (this.buffer.length < end) return null;

            return {
                value: this.buffer.toString('utf8', next, next + length),
                next: end
            };
        }

        if (type === 42) {
            const count = Number(line);

            if (count === -1) {
                return { value: null, next };
            }

            if (!Number.isInteger(count) || count < 0) {
                throw new RedisProtocolError('Invalid array length');
            }

            const values = [];
            let position = next;

            for (let i = 0; i < count; i++) {
                const item = this.parseAt(position);

                if (!item) return null;

                values.push(item.value);
                position = item.next;
            }

            return {
                value: values,
                next: position
            };
        }

        throw new RedisProtocolError(
            `Unsupported RESP type: ${type}`
        );
    }
}

// --------------------------------------------------
// Redis TCP client
// --------------------------------------------------

class RedisClient extends EventEmitter {
    constructor(config = CONFIG) {
        super();

        this.config = config;
    }

    async execute(...parts) {
        return this.runBatch([parts]).then(results => results[0]);
    }

    async runBatch(commands) {
        if (!Array.isArray(commands) || commands.length === 0) {
            return [];
        }

        const socket = new net.Socket();
        const parser = new RESPParser();

        const responses = [];
        let expected = 0;
        let completed = false;

        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                socket.destroy();
                fail(new RedisConnectionError('Redis timeout'));
            }, this.config.timeout);

            const cleanup = () => {
                clearTimeout(timer);
                socket.removeAllListeners();
            };

            const fail = error => {
                if (completed) return;

                completed = true;
                cleanup();
                socket.destroy();
                reject(error);
            };

            socket.on('error', error => {
                fail(new RedisConnectionError(error.message));
            });

            socket.on('data', chunk => {
                try {
                    const parsed = parser.feed(chunk);

                    for (const value of parsed) {
                        responses.push(value);
                        expected--;

                        if (value instanceof Error) {
                            // Preserve command-level errors as results.
                        }
                    }

                    if (expected === 0 && responses.length > 0) {
                        if (completed) return;

                        completed = true;
                        cleanup();
                        socket.end();
                        resolve(responses);
                    }

                } catch (error) {
                    fail(error);
                }
            });

            socket.connect(
                this.config.port,
                this.config.host,
                async () => {
                    try {
                        const setup = [];

                        if (this.config.password) {
                            setup.push(['AUTH', this.config.password]);
                        }

                        if (this.config.database > 0) {
                            setup.push([
                                'SELECT',
                                this.config.database
                            ]);
                        }

                        if (setup.length > 0) {
                            const setupResults = await this.runSetup(
                                socket,
                                parser,
                                setup
                            );

                            if (setupResults.some(x => x instanceof Error)) {
                                throw setupResults.find(
                                    x => x instanceof Error
                                );
                            }
                        }

                        expected = commands.length;

                        const payload = Buffer.concat(
                            commands.map(encodeCommand)
                        );

                        socket.write(payload);

                    } catch (error) {
                        fail(error);
                    }
                }
            );
        });
    }

    runSetup(socket, parser, commands) {
        return new Promise((resolve, reject) => {
            const results = [];
            let expected = commands.length;

            const onData = chunk => {
                try {
                    const parsed = parser.feed(chunk);
                    results.push(...parsed);
                    expected -= parsed.length;

                    if (expected === 0) {
                        socket.removeListener('data', onData);
                        resolve(results);
                    }
                } catch (error) {
                    reject(error);
                }
            };

            socket.on('data', onData);

            socket.write(
                Buffer.concat(commands.map(encodeCommand))
            );
        });
    }

    async ping() {
        return (await this.execute('PING')) === 'PONG';
    }
}

// --------------------------------------------------
// Pipeline
// --------------------------------------------------

class RedisPipeline {
    constructor(client) {
        this.client = client;
        this.commands = [];
    }

    add(...parts) {
        if (parts.length === 0) {
            throw new TypeError('Empty command');
        }

        this.commands.push(parts);
        return this;
    }

    async execute() {
        const commands = this.commands;

        this.commands = [];

        return this.client.runBatch(commands);
    }
}

// --------------------------------------------------
// Transaction
// --------------------------------------------------

class RedisTransaction {
    constructor(client) {
        this.client = client;
        this.commands = [];
    }

    add(...parts) {
        this.commands.push(parts);
        return this;
    }

    async execute() {
        if (this.commands.length === 0) return [];

        const commands = [
            ['MULTI'],
            ...this.commands,
            ['EXEC']
        ];

        const responses = await this.client.runBatch(commands);

        if (responses[0] !== 'OK') {
            throw new RedisError('MULTI failed');
        }

        for (let i = 1; i < responses.length - 1; i++) {
            if (responses[i] !== 'QUEUED') {
                throw new RedisError(
                    'Transaction queue rejected a command'
                );
            }
        }

        const result = responses[responses.length - 1];

        if (result === null) {
            throw new RedisError('Transaction aborted');
        }

        return result;
    }
}

// --------------------------------------------------
// Lua script manager
// --------------------------------------------------

class LuaScriptManager {
    constructor(client) {
        this.client = client;
        this.cache = new Map();
    }

    async execute(source, keys = [], args = []) {
        const sha = crypto
            .createHash('sha1')
            .update(source)
            .digest('hex');

        this.cache.set(sha, source);

        try {
            return await this.client.execute(
                'EVALSHA',
                sha,
                keys.length,
                ...keys,
                ...args
            );

        } catch (error) {
            if (!String(error.message).includes('NOSCRIPT')) {
                throw error;
            }

            return this.client.execute(
                'EVAL',
                source,
                keys.length,
                ...keys,
                ...args
            );
        }
    }
}

// --------------------------------------------------
// Inventory reservation
// --------------------------------------------------

const RESERVATION_LUA = `
local stock = tonumber(redis.call('GET', KEYS[1]) or '0')
local quantity = tonumber(ARGV[1])

if not quantity or quantity <= 0 then
    return -1
end

if stock < quantity then
    return 0
end

redis.call('DECRBY', KEYS[1], quantity)
redis.call('HSET', KEYS[2],
    'quantity', quantity,
    'status', 'reserved')

return stock - quantity
`;

class InventoryService {
    constructor(client) {
        this.client = client;
        this.scripts = new LuaScriptManager(client);
    }

    async reserve(product, orderId, quantity) {
        if (!Number.isSafeInteger(quantity) || quantity <= 0) {
            throw new TypeError('Quantity must be a positive integer');
        }

        return this.scripts.execute(
            RESERVATION_LUA,
            [
                `inventory:${product}`,
                `reservation:${orderId}`
            ],
            [quantity]
        );
    }
}

// --------------------------------------------------
// Distributed lock
// --------------------------------------------------

const RELEASE_LUA = `
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
`;

class DistributedLock {
    constructor(client, key, leaseMs = 10000) {
        if (!Number.isInteger(leaseMs) || leaseMs <= 0) {
            throw new TypeError('Invalid lease duration');
        }

        this.client = client;
        this.key = key;
        this.leaseMs = leaseMs;
        this.token = null;
        this.scripts = new LuaScriptManager(client);
    }

    async acquire(maxAttempts = 3) {
        if (!Number.isInteger(maxAttempts) || maxAttempts < 1) {
            throw new TypeError('Invalid retry count');
        }

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const token = crypto.randomUUID();

            const result = await this.client.execute(
                'SET',
                this.key,
                token,
                'NX',
                'PX',
                this.leaseMs
            );

            if (result === 'OK') {
                this.token = token;
                this.emitAcquired();

                return true;
            }

            await new Promise(resolve =>
                setTimeout(resolve, 50 * (attempt + 1))
            );
        }

        return false;
    }

    emitAcquired() {
        process.stdout.write(`Lock acquired: ${this.key}\n`);
    }

    async release() {
        if (!this.token) {
            throw new LockError('Lock is not owned by this client');
        }

        const result = await this.scripts.execute(
            RELEASE_LUA,
            [this.key],
            [this.token]
        );

        this.token = null;

        return result === 1;
    }
}

// --------------------------------------------------
// Demonstration
// --------------------------------------------------

async function main() {
    const redis = new RedisClient();

    try {
        if (!(await redis.ping())) {
            throw new RedisConnectionError('Redis unavailable');
        }

        console.log('Redis connection established');

        // Pipeline: multiple independent commands.
        const pipeline = new RedisPipeline(redis);

        pipeline
            .add('SET', 'metrics:requests', 100)
            .add('INCRBY', 'metrics:requests', 50)
            .add('GET', 'metrics:requests');

        console.log('Pipeline:', await pipeline.execute());

        // Transaction: commands executed atomically.
        const transaction = new RedisTransaction(redis);

        transaction
            .add('SET', 'wallet:A', 1000)
            .add('SET', 'wallet:B', 500)
            .add('DECRBY', 'wallet:A', 100)
            .add('INCRBY', 'wallet:B', 100);

        console.log('Transaction:', await transaction.execute());

        // Lua: atomic inventory reservation.
        await redis.execute('SET', 'inventory:phone', 25);

        const inventory = new InventoryService(redis);

        console.log(
            'Remaining inventory:',
            await inventory.reserve('phone', 'ORDER-2001', 5)
        );

        // Lock: exclusive lease acquisition.
        const lock = new DistributedLock(
            redis,
            'locks:payment-processing',
            5000
        );

        if (await lock.acquire()) {
            try {
                await redis.execute(
                    'SET',
                    'payment:last_processed',
                    Date.now()
                );
            } finally {
                console.log('Released:', await lock.release());
            }
        } else {
            console.log('Lock acquisition failed');
        }

    } catch (error) {
        console.error('Redis operation failed:', error.message);
        process.exitCode = 1;
    }
}

main();
