"use strict";

/*
 * Redis Fundamentals
 *
 * A self-contained asynchronous Redis-style store using Node.js.
 *
 * Concepts:
 * - Key-value storage
 * - Strings
 * - Hashes
 * - Lists
 * - Sets
 * - Sorted sets
 * - TTL and expiration
 * - Event-driven operations
 * - Transactions
 * - Persistence
 * - Concurrent access and validation
 *
 * Runtime: Node.js 18+
 */

const fs = require("node:fs/promises");
const path = require("node:path");
const { EventEmitter } = require("node:events");

class RedisError extends Error {}
class WrongTypeError extends RedisError {}
class ValidationError extends RedisError {}

const TYPES = Object.freeze({
    STRING: "string",
    HASH: "hash",
    LIST: "list",
    SET: "set",
    ZSET: "zset"
});

class RedisStore extends EventEmitter {
    constructor() {
        super();
        this.data = new Map();
        this.sequence = 0;
    }

    validateKey(key) {
        if (typeof key !== "string" || key.length === 0) {
            throw new ValidationError("Key must be a non-empty string.");
        }

        if (Buffer.byteLength(key, "utf8") > 512 * 1024 * 1024) {
            throw new ValidationError("Key exceeds the size limit.");
        }
    }

    purge(key) {
        const entry = this.data.get(key);

        if (entry && entry.expiresAt !== null &&
            Date.now() >= entry.expiresAt) {
            this.data.delete(key);
            this.emit("expired", { key });
        }
    }

    purgeAll() {
        for (const key of this.data.keys()) {
            this.purge(key);
        }
    }

    getEntry(key, expectedType) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) {
            throw new RedisError(`Key does not exist: ${key}`);
        }

        if (entry.type !== expectedType) {
            throw new WrongTypeError(
                `Expected ${expectedType}, received ${entry.type}.`
            );
        }

        return entry;
    }

    createEntry(key, type, value) {
        this.validateKey(key);
        this.purge(key);

        let entry = this.data.get(key);

        if (!entry) {
            entry = {
                type,
                value,
                expiresAt: null,
                version: ++this.sequence
            };

            this.data.set(key, entry);
            this.emit("created", { key, type });
        }

        if (entry.type !== type) {
            throw new WrongTypeError(
                `Key ${key} already has type ${entry.type}.`
            );
        }

        return entry;
    }

    // STRINGS

    async set(key, value, options = {}) {
        this.validateKey(key);

        if (typeof value !== "string") {
            throw new ValidationError("String value required.");
        }

        this.purge(key);

        if (options.nx && this.data.has(key)) {
            return false;
        }

        let expiresAt = null;

        if (options.exSeconds !== undefined) {
            const seconds = options.exSeconds;

            if (!Number.isFinite(seconds) || seconds <= 0) {
                throw new ValidationError("Invalid expiration.");
            }

            expiresAt = Date.now() + seconds * 1000;
        }

        this.data.set(key, {
            type: TYPES.STRING,
            value,
            expiresAt,
            version: ++this.sequence
        });

        this.emit("set", { key, value });
        return true;
    }

    async get(key) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return null;

        if (entry.type !== TYPES.STRING) {
            throw new WrongTypeError("GET requires a string.");
        }

        return entry.value;
    }

    async incrBy(key, amount = 1) {
        if (!Number.isSafeInteger(amount)) {
            throw new ValidationError("Increment must be a safe integer.");
        }

        const value = await this.get(key);
        const current = value === null ? 0 : Number(value);

        if (!Number.isSafeInteger(current)) {
            throw new RedisError("Stored value is not a safe integer.");
        }

        const result = current + amount;

        if (!Number.isSafeInteger(result)) {
            throw new RedisError("Integer overflow.");
        }

        await this.set(key, String(result));
        return result;
    }

    // HASHES

    async hset(key, field, value) {
        if (typeof field !== "string" || field.length === 0) {
            throw new ValidationError("Invalid hash field.");
        }

        if (typeof value !== "string") {
            throw new ValidationError("Hash value must be a string.");
        }

        const entry = this.createEntry(key, TYPES.HASH, new Map());
        const isNew = !entry.value.has(field);

        entry.value.set(field, value);
        return isNew ? 1 : 0;
    }

    async hget(key, field) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return null;

        if (entry.type !== TYPES.HASH) {
            throw new WrongTypeError("HGET requires a hash.");
        }

        return entry.value.get(field) ?? null;
    }

    async hgetall(key) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return {};

        if (entry.type !== TYPES.HASH) {
            throw new WrongTypeError("HGETALL requires a hash.");
        }

        return Object.fromEntries(entry.value);
    }

    async hdel(key, field) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return 0;

        if (entry.type !== TYPES.HASH) {
            throw new WrongTypeError("HDEL requires a hash.");
        }

        const deleted = entry.value.delete(field) ? 1 : 0;

        if (entry.value.size === 0) {
            this.data.delete(key);
        }

        return deleted;
    }

    // LISTS

    async lpush(key, ...values) {
        const entry = this.createEntry(key, TYPES.LIST, []);
        entry.value.unshift(...values);
        return entry.value.length;
    }

    async rpush(key, ...values) {
        const entry = this.createEntry(key, TYPES.LIST, []);
        entry.value.push(...values);
        return entry.value.length;
    }

    async lpop(key) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return null;

        if (entry.type !== TYPES.LIST) {
            throw new WrongTypeError("LPOP requires a list.");
        }

        const result = entry.value.shift();

        if (entry.value.length === 0) {
            this.data.delete(key);
        }

        return result;
    }

    async rpop(key) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return null;

        if (entry.type !== TYPES.LIST) {
            throw new WrongTypeError("RPOP requires a list.");
        }

        const result = entry.value.pop();

        if (entry.value.length === 0) {
            this.data.delete(key);
        }

        return result;
    }

    async lrange(key, start, stop) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return [];

        if (entry.type !== TYPES.LIST) {
            throw new WrongTypeError("LRANGE requires a list.");
        }

        const size = entry.value.length;
        const from = start < 0 ? Math.max(0, size + start) : start;
        const to = stop < 0 ? size + stop : stop;

        return entry.value.slice(from, to + 1);
    }

    // SETS

    async sadd(key, ...members) {
        const entry = this.createEntry(key, TYPES.SET, new Set());
        let added = 0;

        for (const member of members) {
            if (typeof member !== "string") {
                throw new ValidationError("Set members must be strings.");
            }

            if (!entry.value.has(member)) {
                entry.value.add(member);
                added++;
            }
        }

        return added;
    }

    async srem(key, ...members) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return 0;

        if (entry.type !== TYPES.SET) {
            throw new WrongTypeError("SREM requires a set.");
        }

        let removed = 0;

        for (const member of members) {
            if (entry.value.delete(member)) removed++;
        }

        if (entry.value.size === 0) {
            this.data.delete(key);
        }

        return removed;
    }

    async smembers(key) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return [];

        if (entry.type !== TYPES.SET) {
            throw new WrongTypeError("SMEMBERS requires a set.");
        }

        return [...entry.value].sort();
    }

    async sinter(...keys) {
        if (keys.length === 0) {
            throw new ValidationError("At least one key is required.");
        }

        const first = new Set(await this.smembers(keys[0]));

        for (const key of keys.slice(1)) {
            const members = new Set(await this.smembers(key));

            for (const member of first) {
                if (!members.has(member)) first.delete(member);
            }
        }

        return [...first].sort();
    }

    async sunion(...keys) {
        const result = new Set();

        for (const key of keys) {
            for (const member of await this.smembers(key)) {
                result.add(member);
            }
        }

        return [...result].sort();
    }

    // SORTED SETS

    async zadd(key, members) {
        const entry = this.createEntry(key, TYPES.ZSET, new Map());
        let added = 0;

        for (const [member, score] of Object.entries(members)) {
            if (!member || !Number.isFinite(score)) {
                throw new ValidationError("Invalid member or score.");
            }

            if (!entry.value.has(member)) added++;

            entry.value.set(member, score);
        }

        return added;
    }

    async zrange(key, start = 0, stop = -1, withScores = false) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return [];

        if (entry.type !== TYPES.ZSET) {
            throw new WrongTypeError("ZRANGE requires a sorted set.");
        }

        const sorted = [...entry.value.entries()].sort(
            ([memberA, scoreA], [memberB, scoreB]) =>
                scoreA - scoreB || memberA.localeCompare(memberB)
        );

        const size = sorted.length;
        const from = start < 0 ? Math.max(0, size + start) : start;
        const to = stop < 0 ? size + stop : stop;

        const selected = sorted.slice(from, to + 1);

        return withScores
            ? selected.map(([member, score]) => ({ member, score }))
            : selected.map(([member]) => member);
    }

    async zscore(key, member) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return null;

        if (entry.type !== TYPES.ZSET) {
            throw new WrongTypeError("ZSCORE requires a sorted set.");
        }

        return entry.value.get(member) ?? null;
    }

    // KEY MANAGEMENT

    async exists(key) {
        this.validateKey(key);
        this.purge(key);
        return this.data.has(key);
    }

    async del(...keys) {
        let deleted = 0;

        for (const key of keys) {
            this.validateKey(key);
            this.purge(key);

            if (this.data.delete(key)) deleted++;
        }

        return deleted;
    }

    async expire(key, seconds) {
        this.validateKey(key);

        if (!Number.isFinite(seconds) || seconds <= 0) {
            throw new ValidationError("Expiration must be positive.");
        }

        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return false;

        entry.expiresAt = Date.now() + seconds * 1000;
        return true;
    }

    async ttl(key) {
        this.validateKey(key);
        this.purge(key);

        const entry = this.data.get(key);

        if (!entry) return -2;
        if (entry.expiresAt === null) return -1;

        return Math.max(
            0,
            Math.floor((entry.expiresAt - Date.now()) / 1000)
        );
    }

    async keys(prefix = "") {
        this.purgeAll();

        return [...this.data.keys()]
            .filter(key => key.startsWith(prefix))
            .sort();
    }

    async type(key) {
        this.validateKey(key);
        this.purge(key);
        return this.data.get(key)?.type ?? "none";
    }

    // TRANSACTIONS
    //
    // JavaScript executes synchronous code in one event-loop turn.
    // This method rejects asynchronous callbacks so that another operation
    // cannot interleave with a transaction's synchronous command sequence.

    async transaction(callback) {
        if (typeof callback !== "function") {
            throw new ValidationError("Transaction callback required.");
        }

        const snapshot = new Map();

        for (const [key, entry] of this.data) {
            let value;

            if (entry.type === TYPES.HASH ||
                entry.type === TYPES.ZSET) {
                value = new Map(entry.value);
            } else if (entry.type === TYPES.SET) {
                value = new Set(entry.value);
            } else if (entry.type === TYPES.LIST) {
                value = [...entry.value];
            } else {
                value = entry.value;
            }

            snapshot.set(key, {
                type: entry.type,
                value,
                expiresAt: entry.expiresAt,
                version: entry.version
            });
        }

        try {
            const result = callback(this);

            if (result && typeof result.then === "function") {
                throw new ValidationError(
                    "Transactions must use synchronous callbacks."
                );
            }

            return result;
        } catch (error) {
            this.data = snapshot;
            throw error;
        }
    }

    // JSON SNAPSHOT

    async save(filePath) {
        this.purgeAll();

        const snapshot = {};

        for (const [key, entry] of this.data) {
            let value;

            if (entry.type === TYPES.HASH ||
                entry.type === TYPES.ZSET) {
                value = Object.fromEntries(entry.value);
            } else if (entry.type === TYPES.SET ||
                entry.type === TYPES.LIST) {
                value = [...entry.value];
            } else {
                value = entry.value;
            }

            snapshot[key] = {
                type: entry.type,
                value,
                expiresAt: entry.expiresAt
            };
        }

        const destination = path.resolve(filePath);
        const temporary = `${destination}.${process.pid}.tmp`;

        try {
            await fs.writeFile(
                temporary,
                JSON.stringify(snapshot, null, 2),
                { encoding: "utf8", flag: "wx" }
            );

            await fs.rename(temporary, destination);
        } catch (error) {
            await fs.rm(temporary, { force: true }).catch(() => {});
            throw error;
        }
    }

    async load(filePath) {
        const raw = await fs.readFile(filePath, "utf8");
        const snapshot = JSON.parse(raw);

        if (!snapshot || typeof snapshot !== "object" ||
            Array.isArray(snapshot)) {
            throw new ValidationError("Invalid snapshot.");
        }

        const replacement = new Map();

        for (const [key, item] of Object.entries(snapshot)) {
            this.validateKey(key);

            if (!item || !Object.values(TYPES).includes(item.type)) {
                throw new ValidationError("Invalid snapshot type.");
            }

            let value = item.value;

            if (item.type === TYPES.HASH ||
                item.type === TYPES.ZSET) {
                if (!value || typeof value !== "object" ||
                    Array.isArray(value)) {
                    throw new ValidationError("Invalid object value.");
                }

                value = new Map(Object.entries(value));
            } else if (item.type === TYPES.SET) {
                if (!Array.isArray(value)) {
                    throw new ValidationError("Invalid set value.");
                }

                value = new Set(value);
            } else if (item.type === TYPES.LIST) {
                if (!Array.isArray(value)) {
                    throw new ValidationError("Invalid list value.");
                }

                value = [...value];
            } else if (typeof value !== "string") {
                throw new ValidationError("Invalid string value.");
            }

            if (item.type === TYPES.ZSET) {
                for (const score of value.values()) {
                    if (!Number.isFinite(score)) {
                        throw new ValidationError("Invalid sorted-set score.");
                    }
                }
            }

            const expiresAt = item.expiresAt;

            if (expiresAt !== null &&
                (!Number.isFinite(expiresAt) || expiresAt <= Date.now())) {
                continue;
            }

            replacement.set(key, {
                type: item.type,
                value,
                expiresAt,
                version: ++this.sequence
            });
        }

        this.data = replacement;
    }
}

async function demonstration() {
    const redis = new RedisStore();

    redis.on("set", event => {
        console.log("EVENT set:", event.key);
    });

    redis.on("created", event => {
        console.log("EVENT created:", event.key, event.type);
    });

    console.log("\n=== STRINGS ===");
    await redis.set("counter", "100");
    console.log("Increment:", await redis.incrBy("counter", 25));
    console.log("Value:", await redis.get("counter"));

    console.log("\n=== HASHES ===");
    await redis.hset("user:1001", "name", "Atul");
    await redis.hset("user:1001", "department", "Engineering");
    console.log(await redis.hgetall("user:1001"));

    console.log("\n=== LISTS ===");
    await redis.rpush("queue", "job-A", "job-B");
    await redis.lpush("queue", "job-C");
    console.log("Queue:", await redis.lrange("queue", 0, -1));
    console.log("Processed:", await redis.lpop("queue"));

    console.log("\n=== SETS ===");
    await redis.sadd("backend", "Python", "Java", "C++");
    await redis.sadd("cloud", "Java", "Go", "Python");

    console.log("Intersection:", await redis.sinter("backend", "cloud"));
    console.log("Union:", await redis.sunion("backend", "cloud"));

    console.log("\n=== SORTED SETS ===");
    await redis.zadd("leaderboard", {
        Alice: 950,
        Bob: 850,
        Charlie: 900
    });

    console.log("Ranking:", await redis.zrange(
        "leaderboard", 0, -1, true
    ));

    console.log("\n=== TRANSACTION ===");

    try {
        redis.transaction(store => {
            store.data.set("account:A", {
                type: TYPES.STRING,
                value: "500",
                expiresAt: null,
                version: ++store.sequence
            });

            throw new RedisError("Simulated transaction failure.");
        });
    } catch (error) {
        console.log("Rolled back:", error.message);
    }

    console.log("Account exists:", await redis.exists("account:A"));

    console.log("\n=== EXPIRATION ===");
    await redis.set("session:1", "active", { exSeconds: 60 });
    console.log("TTL:", await redis.ttl("session:1"));

    console.log("\n=== KEY MANAGEMENT ===");
    console.log("Hash keys:", await redis.keys("user:"));
    console.log("Type:", await redis.type("leaderboard"));

    console.log("\n=== PERSISTENCE ===");
    const filename = path.join(
        require("node:os").tmpdir(),
        `redis-fundamentals-${process.pid}.json`
    );

    try {
        await redis.save(filename);

        const restored = new RedisStore();
        await restored.load(filename);

        console.log("Restored counter:", await restored.get("counter"));
        console.log("Restored user:", await restored.hgetall("user:1001"));
    } finally {
        await fs.rm(filename, { force: true });
    }

    console.log("\n=== ERROR HANDLING ===");

    try {
        await redis.hgetall("counter");
    } catch (error) {
        console.log(error.name + ":", error.message);
    }
}

async function runTests() {
    const redis = new RedisStore();

    await redis.set("x", "10");
    console.assert(await redis.incrBy("x", 5) === 15);

    await redis.hset("user", "name", "Atul");
    console.assert(await redis.hget("user", "name") === "Atul");

    await redis.rpush("list", "A", "B");
    await redis.lpush("list", "C");
    console.assert(
        JSON.stringify(await redis.lrange("list", 0, -1)) ===
        JSON.stringify(["C", "A", "B"])
    );

    await redis.sadd("A", "x", "y");
    await redis.sadd("B", "y", "z");
    console.assert(
        JSON.stringify(await redis.sinter("A", "B")) ===
        JSON.stringify(["y"])
    );

    await redis.zadd("scores", { Alice: 10, Bob: 20 });
    console.assert(
        JSON.stringify(await redis.zrange("scores")) ===
        JSON.stringify(["Alice", "Bob"])
    );

    const previous = await redis.get("x");

    try {
        redis.transaction(store => {
            store.data.delete("x");
            throw new RedisError("Rollback test");
        });
    } catch (_) {}

    console.assert(await redis.get("x") === previous);

    await redis.set("temporary", "value", { exSeconds: 0.02 });
    await new Promise(resolve => setTimeout(resolve, 40));
    console.assert(!(await redis.exists("temporary")));

    let rejected = false;

    try {
        await redis.set("invalid", 100);
    } catch (error) {
        rejected = error instanceof ValidationError;
    }

    console.assert(rejected);

    console.log("All JavaScript assertions completed.");
}

async function main() {
    await demonstration();
    await runTests();
}

main().catch(error => {
    console.error("Application failed:", error);
    process.exitCode = 1;
});
