"use strict";

/**
 * Rate Limiting Engine
 * Node.js 18+
 *
 * Demonstrates:
 * - Fixed window
 * - Sliding window
 * - Token bucket
 * - Distributed rate limiting
 * - Asynchronous API gateway
 * - Policy configuration and request evaluation
 *
 * No external dependencies.
 */

const { EventEmitter } = require("node:events");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");

// ============================================================
// ERRORS AND VALIDATION
// ============================================================

class ConfigurationError extends Error {}
class RateLimitError extends Error {}

function validateKey(key) {
    if (typeof key !== "string" || key.trim().length === 0) {
        throw new TypeError("A non-empty rate-limit key is required.");
    }
}

function validateCost(cost) {
    if (!Number.isSafeInteger(cost) || cost <= 0) {
        throw new TypeError("Request cost must be a positive safe integer.");
    }
}

function validatePolicy(limit, windowMs) {
    if (!Number.isSafeInteger(limit) || limit <= 0) {
        throw new ConfigurationError("Invalid request limit.");
    }

    if (!Number.isFinite(windowMs) || windowMs <= 0) {
        throw new ConfigurationError("Invalid window duration.");
    }
}

// ============================================================
// CLOCK
// ============================================================

class SystemClock {
    now() {
        return Date.now();
    }
}

class ManualClock {
    constructor(initial = 100000) {
        this.current = initial;
    }

    now() {
        return this.current;
    }

    advance(milliseconds) {
        if (!Number.isFinite(milliseconds) || milliseconds < 0) {
            throw new RangeError("Invalid clock advancement.");
        }

        this.current += milliseconds;
    }
}

// ============================================================
// RATE LIMIT EVENTS
// ============================================================

class RateLimitEvents extends EventEmitter {
    record(key, decision) {
        this.emit("decision", {
            requestId: randomUUID(),
            key,
            allowed: decision.allowed,
            algorithm: decision.algorithm,
            remaining: decision.remaining,
            retryAfterMs: decision.retryAfterMs,
            timestamp: Date.now()
        });
    }
}

// ============================================================
// BASE LIMITER
// ============================================================

class BaseLimiter {
    constructor(clock = new SystemClock()) {
        this.clock = clock;
    }

    decision(allowed, remaining, retryAfterMs, algorithm) {
        return Object.freeze({
            allowed,
            remaining: Math.max(0, Math.floor(remaining)),
            retryAfterMs: Math.max(0, Math.ceil(retryAfterMs)),
            algorithm
        });
    }
}

// ============================================================
// FIXED WINDOW
// ============================================================

class FixedWindowLimiter extends BaseLimiter {
    constructor(limit, windowMs, clock) {
        super(clock);
        validatePolicy(limit, windowMs);

        this.limit = limit;
        this.windowMs = windowMs;
        this.windows = new Map();
    }

    allow(key, cost = 1) {
        validateKey(key);
        validateCost(cost);

        const now = this.clock.now();
        const windowStart = Math.floor(now / this.windowMs) * this.windowMs;

        let state = this.windows.get(key);

        if (!state || state.windowStart !== windowStart) {
            state = {
                windowStart,
                count: 0
            };

            this.windows.set(key, state);
        }

        const allowed = state.count + cost <= this.limit;

        if (allowed) {
            state.count += cost;
        }

        return this.decision(
            allowed,
            this.limit - state.count,
            allowed ? 0 : windowStart + this.windowMs - now,
            "fixed_window"
        );
    }

    cleanup() {
        const now = this.clock.now();

        for (const [key, state] of this.windows) {
            if (now - state.windowStart > this.windowMs * 2) {
                this.windows.delete(key);
            }
        }
    }
}

// ============================================================
// SLIDING WINDOW LOG
// ============================================================

class SlidingWindowLimiter extends BaseLimiter {
    constructor(limit, windowMs, clock) {
        super(clock);
        validatePolicy(limit, windowMs);

        this.limit = limit;
        this.windowMs = windowMs;
        this.logs = new Map();
    }

    allow(key, cost = 1) {
        validateKey(key);
        validateCost(cost);

        if (cost > this.limit) {
            return this.decision(
                false,
                0,
                0,
                "sliding_window"
            );
        }

        const now = this.clock.now();
        const cutoff = now - this.windowMs;

        let timestamps = this.logs.get(key);

        if (!timestamps) {
            timestamps = [];
            this.logs.set(key, timestamps);
        }

        // Remove timestamps outside the active sliding interval.
        let expired = 0;

        while (
            expired < timestamps.length &&
            timestamps[expired] <= cutoff
        ) {
            expired++;
        }

        if (expired > 0) {
            timestamps.splice(0, expired);
        }

        const allowed = timestamps.length + cost <= this.limit;

        if (allowed) {
            for (let i = 0; i < cost; i++) {
                timestamps.push(now);
            }
        }

        const retryAfterMs =
            !allowed && timestamps.length > 0
                ? timestamps[0] + this.windowMs - now
                : 0;

        return this.decision(
            allowed,
            this.limit - timestamps.length,
            retryAfterMs,
            "sliding_window"
        );
    }

    cleanup() {
        const cutoff = this.clock.now() - this.windowMs;

        for (const [key, timestamps] of this.logs) {
            while (timestamps.length && timestamps[0] <= cutoff) {
                timestamps.shift();
            }

            if (timestamps.length === 0) {
                this.logs.delete(key);
            }
        }
    }
}

// ============================================================
// TOKEN BUCKET
// ============================================================

class TokenBucketLimiter extends BaseLimiter {
    constructor(capacity, refillRatePerSecond, clock) {
        super(clock);

        if (
            !Number.isFinite(capacity) ||
            !Number.isFinite(refillRatePerSecond) ||
            capacity <= 0 ||
            refillRatePerSecond <= 0
        ) {
            throw new ConfigurationError("Invalid token bucket settings.");
        }

        this.capacity = capacity;
        this.refillRate = refillRatePerSecond;
        this.buckets = new Map();
    }

    allow(key, cost = 1) {
        validateKey(key);
        validateCost(cost);

        const now = this.clock.now();

        let bucket = this.buckets.get(key);

        if (!bucket) {
            bucket = {
                tokens: this.capacity,
                updatedAt: now
            };

            this.buckets.set(key, bucket);
        }

        const elapsedSeconds = Math.max(
            0,
            now - bucket.updatedAt
        ) / 1000;

        bucket.tokens = Math.min(
            this.capacity,
            bucket.tokens + elapsedSeconds * this.refillRate
        );

        bucket.updatedAt = Math.max(now, bucket.updatedAt);

        const allowed = cost <= this.capacity && bucket.tokens >= cost;

        if (allowed) {
            bucket.tokens -= cost;
        }

        const retryAfterMs =
            !allowed && cost <= this.capacity
                ? ((cost - bucket.tokens) / this.refillRate) * 1000
                : 0;

        return this.decision(
            allowed,
            bucket.tokens,
            retryAfterMs,
            "token_bucket"
        );
    }
}

// ============================================================
// ASYNCHRONOUS MUTUAL EXCLUSION
// ============================================================

class AsyncMutex {
    constructor() {
        this.tail = Promise.resolve();
    }

    async runExclusive(operation) {
        let release;

        const previous = this.tail;

        this.tail = new Promise(resolve => {
            release = resolve;
        });

        await previous;

        try {
            return await operation();
        } finally {
            release();
        }
    }
}

// ============================================================
// DISTRIBUTED SHARED STORE
// ============================================================

class SharedRateLimitStore {
    constructor() {
        this.states = new Map();
        this.mutex = new AsyncMutex();
    }

    async atomic(key, operation) {
        return this.mutex.runExclusive(async () => {
            const previous = this.states.get(key);

            const next = await operation(previous);

            this.states.set(key, next.state);

            return next.result;
        });
    }
}

// ============================================================
// DISTRIBUTED TOKEN BUCKET
// ============================================================

class DistributedTokenBucket {
    constructor(store, capacity, refillRate, clock = new SystemClock()) {
        if (
            !(store instanceof SharedRateLimitStore) ||
            capacity <= 0 ||
            refillRate <= 0
        ) {
            throw new ConfigurationError("Invalid distributed limiter.");
        }

        this.store = store;
        this.capacity = capacity;
        this.refillRate = refillRate;
        this.clock = clock;
    }

    async allow(key, cost = 1) {
        validateKey(key);
        validateCost(cost);

        const now = this.clock.now();

        return this.store.atomic(
            `rate:${key}`,
            previous => {
                const state = previous || {
                    tokens: this.capacity,
                    updatedAt: now
                };

                const elapsed = Math.max(
                    0,
                    now - state.updatedAt
                ) / 1000;

                const tokens = Math.min(
                    this.capacity,
                    state.tokens + elapsed * this.refillRate
                );

                const allowed = cost <= this.capacity && tokens >= cost;

                const remainingTokens = allowed
                    ? tokens - cost
                    : tokens;

                const retryAfterMs =
                    !allowed && cost <= this.capacity
                        ? ((cost - tokens) / this.refillRate) * 1000
                        : 0;

                const nextState = {
                    tokens: remainingTokens,
                    updatedAt: Math.max(now, state.updatedAt)
                };

                return {
                    state: nextState,
                    result: Object.freeze({
                        allowed,
                        remaining: Math.floor(remainingTokens),
                        retryAfterMs: Math.ceil(retryAfterMs),
                        algorithm: "distributed_token_bucket"
                    })
                };
            }
        );
    }
}

// ============================================================
// API GATEWAY
// ============================================================

class APIGateway {
    constructor() {
        this.events = new RateLimitEvents();

        this.policies = new Map([
            [
                "/api/login",
                new FixedWindowLimiter(5, 60000)
            ],
            [
                "/api/search",
                new SlidingWindowLimiter(10, 60000)
            ],
            [
                "/api/upload",
                new TokenBucketLimiter(5, 0.5)
            ]
        ]);
    }

    async handle(request) {
        const { path, userId, cost = 1 } = request;

        const limiter = this.policies.get(path);

        if (!limiter) {
            return {
                status: 404,
                body: {
                    error: "Endpoint not found"
                }
            };
        }

        const result = limiter.allow(userId, cost);

        this.events.record(userId, result);

        if (!result.allowed) {
            return {
                status: 429,
                headers: {
                    "Retry-After": String(
                        Math.ceil(result.retryAfterMs / 1000)
                    ),
                    "X-RateLimit-Remaining": "0"
                },
                body: {
                    error: "Too many requests",
                    algorithm: result.algorithm,
                    retryAfterMs: result.retryAfterMs
                }
            };
        }

        return {
            status: 200,
            headers: {
                "X-RateLimit-Remaining": String(result.remaining)
            },
            body: {
                message: "Request accepted"
            }
        };
    }
}

// ============================================================
// DEMONSTRATION AND TESTS
// ============================================================

async function runTests() {
    const clock = new ManualClock();

    // Fixed window.
    const fixed = new FixedWindowLimiter(2, 1000, clock);

    assert.equal(fixed.allow("alice").allowed, true);
    assert.equal(fixed.allow("alice").allowed, true);
    assert.equal(fixed.allow("alice").allowed, false);

    clock.advance(1000);

    assert.equal(fixed.allow("alice").allowed, true);

    // Sliding window.
    const sliding = new SlidingWindowLimiter(2, 1000, clock);

    assert.equal(sliding.allow("bob").allowed, true);

    clock.advance(500);

    assert.equal(sliding.allow("bob").allowed, true);
    assert.equal(sliding.allow("bob").allowed, false);

    clock.advance(500);

    assert.equal(sliding.allow("bob").allowed, true);

    // Token bucket.
    const bucket = new TokenBucketLimiter(2, 1, clock);

    assert.equal(bucket.allow("carol").allowed, true);
    assert.equal(bucket.allow("carol").allowed, true);
    assert.equal(bucket.allow("carol").allowed, false);

    clock.advance(1000);

    assert.equal(bucket.allow("carol").allowed, true);

    // Distributed atomicity across instances.
    const store = new SharedRateLimitStore();

    const serverA = new DistributedTokenBucket(
        store, 2, 1, clock
    );

    const serverB = new DistributedTokenBucket(
        store, 2, 1, clock
    );

    const decisions = await Promise.all([
        serverA.allow("customer-1"),
        serverB.allow("customer-1"),
        serverA.allow("customer-1"),
        serverB.allow("customer-1")
    ]);

    assert.equal(
        decisions.filter(item => item.allowed).length,
        2
    );

    assert.equal(
        decisions.filter(item => !item.allowed).length,
        2
    );

    // Independent customers.
    assert.equal(serverA.allow("customer-2").then, undefined);
    assert.equal(
        (await serverA.allow("customer-2")).allowed,
        true
    );

    // Invalid input.
    assert.throws(
        () => fixed.allow("", 1),
        TypeError
    );

    assert.throws(
        () => fixed.allow("alice", -1),
        TypeError
    );

    console.log("All rate-limiting tests passed.");
}

async function main() {
    const gateway = new APIGateway();

    gateway.events.on("decision", event => {
        if (!event.allowed) {
            console.log(
                `[RATE LIMIT] ${event.key} blocked by ${event.algorithm}`
            );
        }
    });

    console.log("API Gateway demonstration:");

    for (let i = 0; i < 7; i++) {
        const response = await gateway.handle({
            path: "/api/login",
            userId: "user-101"
        });

        console.log({
            request: i + 1,
            status: response.status,
            body: response.body
        });
    }

    console.log("\nRunning tests...");
    await runTests();
}

main().catch(error => {
    console.error("Application failure:", error.message);
    process.exitCode = 1;
});
