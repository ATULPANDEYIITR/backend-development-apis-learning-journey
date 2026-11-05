import java.time.Duration;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Enterprise Rate Limiting Engine.
 *
 * Java 17
 *
 * Implements:
 * 1. Fixed window
 * 2. Sliding window
 * 3. Token bucket
 * 4. Distributed rate limiting simulation
 * 5. API gateway policy evaluation
 */

public class RateLimitingEngine {

    // ========================================================
    // DOMAIN TYPES
    // ========================================================

    enum Algorithm {
        FIXED_WINDOW,
        SLIDING_WINDOW,
        TOKEN_BUCKET
    }

    enum RequestStatus {
        ACCEPTED,
        RATE_LIMITED,
        INVALID,
        INTERNAL_ERROR
    }

    record RateLimitDecision(
            boolean allowed,
            int remaining,
            long retryAfterMillis,
            Algorithm algorithm
    ) {}

    record ApiRequest(
            String userId,
            String endpoint,
            int cost,
            String requestId
    ) {
        ApiRequest {
            if (userId == null || userId.isBlank()) {
                throw new IllegalArgumentException(
                        "User ID is required."
                );
            }

            if (endpoint == null || endpoint.isBlank()) {
                throw new IllegalArgumentException(
                        "Endpoint is required."
                );
            }

            if (cost <= 0) {
                throw new IllegalArgumentException(
                        "Request cost must be positive."
                );
            }

            if (requestId == null || requestId.isBlank()) {
                throw new IllegalArgumentException(
                        "Request ID is required."
                );
            }
        }
    }

    record ApiResponse(
            RequestStatus status,
            int httpStatus,
            String message,
            RateLimitDecision decision
    ) {}

    // ========================================================
    // CLOCK ABSTRACTION
    // ========================================================

    interface Clock {
        long nowMillis();
    }

    static class SystemClock implements Clock {
        @Override
        public long nowMillis() {
            return System.nanoTime() / 1_000_000L;
        }
    }

    static class ManualClock implements Clock {
        private long current;

        ManualClock(long initial) {
            current = initial;
        }

        @Override
        public synchronized long nowMillis() {
            return current;
        }

        synchronized void advance(long milliseconds) {
            if (milliseconds < 0) {
                throw new IllegalArgumentException(
                        "Time cannot move backward."
                );
            }

            current += milliseconds;
        }
    }

    // ========================================================
    // CUSTOM EXCEPTION
    // ========================================================

    static class RateLimitConfigurationException
            extends RuntimeException {

        RateLimitConfigurationException(String message) {
            super(message);
        }
    }

    // ========================================================
    // POLICY MODEL
    // ========================================================

    record RateLimitPolicy(
            Algorithm algorithm,
            int limit,
            Duration window,
            double capacity,
            double refillRate
    ) {
        RateLimitPolicy {
            Objects.requireNonNull(algorithm);
            Objects.requireNonNull(window);

            if (limit <= 0 || window.isZero() || window.isNegative()) {
                throw new RateLimitConfigurationException(
                        "Invalid rate limit policy."
                );
            }

            if (
                    algorithm == Algorithm.TOKEN_BUCKET &&
                    (
                            !Double.isFinite(capacity) ||
                            !Double.isFinite(refillRate) ||
                            capacity <= 0 ||
                            refillRate <= 0
                    )
            ) {
                throw new RateLimitConfigurationException(
                        "Invalid token bucket policy."
                );
            }
        }
    }

    // ========================================================
    // LIMITER INTERFACE
    // ========================================================

    interface RateLimiter {
        RateLimitDecision evaluate(String key, int cost);
    }

    // ========================================================
    // FIXED WINDOW
    // ========================================================

    static class FixedWindowLimiter implements RateLimiter {

        private static class State {
            long windowStart;
            int count;

            State(long start) {
                windowStart = start;
            }
        }

        private final int limit;
        private final long windowMillis;
        private final Clock clock;

        private final Map<String, State> states =
                new ConcurrentHashMap<>();

        private final Map<String, ReentrantLock> locks =
                new ConcurrentHashMap<>();

        FixedWindowLimiter(
                int limit,
                Duration window,
                Clock clock
        ) {
            if (
                    limit <= 0 ||
                    window == null ||
                    window.isZero() ||
                    window.isNegative()
            ) {
                throw new RateLimitConfigurationException(
                        "Invalid fixed window configuration."
                );
            }

            this.limit = limit;
            this.windowMillis = window.toMillis();
            this.clock = Objects.requireNonNull(clock);
        }

        @Override
        public RateLimitDecision evaluate(
                String key,
                int cost
        ) {
            validateRequest(key, cost);

            ReentrantLock lock = locks.computeIfAbsent(
                    key,
                    ignored -> new ReentrantLock()
            );

            lock.lock();

            try {
                long now = clock.nowMillis();

                long windowStart =
                        (now / windowMillis) * windowMillis;

                State state = states.computeIfAbsent(
                        key,
                        ignored -> new State(windowStart)
                );

                if (state.windowStart != windowStart) {
                    state.windowStart = windowStart;
                    state.count = 0;
                }

                boolean allowed =
                        cost <= limit &&
                        state.count + cost <= limit;

                if (allowed) {
                    state.count += cost;
                }

                int remaining = Math.max(
                        0,
                        limit - state.count
                );

                long retry = allowed
                        ? 0
                        : windowStart + windowMillis - now;

                return new RateLimitDecision(
                        allowed,
                        remaining,
                        Math.max(0, retry),
                        Algorithm.FIXED_WINDOW
                );

            } finally {
                lock.unlock();
            }
        }
    }

    // ========================================================
    // SLIDING WINDOW LOG
    // ========================================================

    static class SlidingWindowLimiter implements RateLimiter {

        private final int limit;
        private final long windowMillis;
        private final Clock clock;

        private final Map<String, ArrayDeque<Long>> logs =
                new ConcurrentHashMap<>();

        private final Map<String, ReentrantLock> locks =
                new ConcurrentHashMap<>();

        SlidingWindowLimiter(
                int limit,
                Duration window,
                Clock clock
        ) {
            if (
                    limit <= 0 ||
                    window == null ||
                    window.isNegative() ||
                    window.isZero()
            ) {
                throw new RateLimitConfigurationException(
                        "Invalid sliding window configuration."
                );
            }

            this.limit = limit;
            this.windowMillis = window.toMillis();
            this.clock = clock;
        }

        @Override
        public RateLimitDecision evaluate(
                String key,
                int cost
        ) {
            validateRequest(key, cost);

            if (cost > limit) {
                return new RateLimitDecision(
                        false,
                        0,
                        0,
                        Algorithm.SLIDING_WINDOW
                );
            }

            ReentrantLock lock = locks.computeIfAbsent(
                    key,
                    ignored -> new ReentrantLock()
            );

            lock.lock();

            try {
                long now = clock.nowMillis();
                long cutoff = now - windowMillis;

                ArrayDeque<Long> timestamps = logs.computeIfAbsent(
                        key,
                        ignored -> new ArrayDeque<>()
                );

                while (
                        !timestamps.isEmpty() &&
                        timestamps.peekFirst() <= cutoff
                ) {
                    timestamps.removeFirst();
                }

                boolean allowed =
                        timestamps.size() + cost <= limit;

                if (allowed) {
                    for (int i = 0; i < cost; i++) {
                        timestamps.addLast(now);
                    }
                }

                long retry = 0;

                if (!allowed && !timestamps.isEmpty()) {
                    retry = Math.max(
                            0,
                            timestamps.peekFirst()
                                    + windowMillis
                                    - now
                    );
                }

                return new RateLimitDecision(
                        allowed,
                        Math.max(0, limit - timestamps.size()),
                        retry,
                        Algorithm.SLIDING_WINDOW
                );

            } finally {
                lock.unlock();
            }
        }
    }

    // ========================================================
    // TOKEN BUCKET
    // ========================================================

    static class TokenBucketLimiter implements RateLimiter {

        private static class Bucket {
            double tokens;
            long lastUpdate;

            Bucket(double capacity, long now) {
                tokens = capacity;
                lastUpdate = now;
            }
        }

        private final double capacity;
        private final double refillRate;
        private final Clock clock;

        private final Map<String, Bucket> buckets =
                new ConcurrentHashMap<>();

        private final Map<String, ReentrantLock> locks =
                new ConcurrentHashMap<>();

        TokenBucketLimiter(
                double capacity,
                double refillRate,
                Clock clock
        ) {
            if (
                    !Double.isFinite(capacity) ||
                    !Double.isFinite(refillRate) ||
                    capacity <= 0 ||
                    refillRate <= 0
            ) {
                throw new RateLimitConfigurationException(
                        "Invalid token bucket configuration."
                );
            }

            this.capacity = capacity;
            this.refillRate = refillRate;
            this.clock = clock;
        }

        @Override
        public RateLimitDecision evaluate(
                String key,
                int cost
        ) {
            validateRequest(key, cost);

            ReentrantLock lock = locks.computeIfAbsent(
                    key,
                    ignored -> new ReentrantLock()
            );

            lock.lock();

            try {
                long now = clock.nowMillis();

                Bucket bucket = buckets.computeIfAbsent(
                        key,
                        ignored -> new Bucket(capacity, now)
                );

                long elapsed = Math.max(
                        0,
                        now - bucket.lastUpdate
                );

                bucket.tokens = Math.min(
                        capacity,
                        bucket.tokens +
                                elapsed / 1000.0 * refillRate
                );

                bucket.lastUpdate = Math.max(
                        bucket.lastUpdate,
                        now
                );

                boolean allowed =
                        cost <= capacity &&
                        bucket.tokens >= cost;

                if (allowed) {
                    bucket.tokens -= cost;
                }

                long retry = 0;

                if (!allowed && cost <= capacity) {
                    retry = (long) Math.ceil(
                            (cost - bucket.tokens) /
                                    refillRate * 1000
                    );
                }

                return new RateLimitDecision(
                        allowed,
                        Math.max(0, (int) Math.floor(bucket.tokens)),
                        retry,
                        Algorithm.TOKEN_BUCKET
                );

            } finally {
                lock.unlock();
            }
        }
    }

    // ========================================================
    // DISTRIBUTED SHARED STATE STORE
    // ========================================================

    static class SharedDistributedStore {

        private static class State {
            double tokens;
            long lastUpdate;

            State(double tokens, long lastUpdate) {
                this.tokens = tokens;
                this.lastUpdate = lastUpdate;
            }
        }

        private final Map<String, State> states =
                new HashMap<>();

        private final ReentrantLock lock =
                new ReentrantLock();

        RateLimitDecision evaluate(
                String key,
                double capacity,
                double refillRate,
                long now,
                int cost
        ) {
            lock.lock();

            try {
                State state = states.computeIfAbsent(
                        key,
                        ignored -> new State(capacity, now)
                );

                long elapsed = Math.max(
                        0,
                        now - state.lastUpdate
                );

                state.tokens = Math.min(
                        capacity,
                        state.tokens +
                                elapsed / 1000.0 * refillRate
                );

                state.lastUpdate = Math.max(
                        state.lastUpdate,
                        now
                );

                boolean allowed =
                        cost <= capacity &&
                        state.tokens >= cost;

                if (allowed) {
                    state.tokens -= cost;
                }

                long retry = 0;

                if (!allowed && cost <= capacity) {
                    retry = (long) Math.ceil(
                            (cost - state.tokens) /
                                    refillRate * 1000
                    );
                }

                return new RateLimitDecision(
                        allowed,
                        Math.max(0, (int) Math.floor(state.tokens)),
                        retry,
                        Algorithm.TOKEN_BUCKET
                );

            } finally {
                lock.unlock();
            }
        }
    }

    // ========================================================
    // DISTRIBUTED LIMITER SERVICE
    // ========================================================

    static class DistributedRateLimiter {

        private final SharedDistributedStore store;
        private final double capacity;
        private final double refillRate;
        private final Clock clock;

        DistributedRateLimiter(
                SharedDistributedStore store,
                double capacity,
                double refillRate,
                Clock clock
        ) {
            this.store = Objects.requireNonNull(store);

            if (
                    !Double.isFinite(capacity) ||
                    !Double.isFinite(refillRate) ||
                    capacity <= 0 ||
                    refillRate <= 0
            ) {
                throw new RateLimitConfigurationException(
                        "Invalid distributed configuration."
                );
            }

            this.capacity = capacity;
            this.refillRate = refillRate;
            this.clock = clock;
        }

        RateLimitDecision evaluate(
                String userId,
                int cost
        ) {
            validateRequest(userId, cost);

            return store.evaluate(
                    "rate-limit:" + userId,
                    capacity,
                    refillRate,
                    clock.nowMillis(),
                    cost
            );
        }
    }

    // ========================================================
    // ENTERPRISE API GATEWAY
    // ========================================================

    static class EnterpriseApiGateway {

        private final Map<String, RateLimiter> policies =
                new ConcurrentHashMap<>();

        EnterpriseApiGateway(Clock clock) {
            policies.put(
                    "/api/login",
                    new FixedWindowLimiter(
                            5,
                            Duration.ofMinutes(1),
                            clock
                    )
            );

            policies.put(
                    "/api/search",
                    new SlidingWindowLimiter(
                            10,
                            Duration.ofMinutes(1),
                            clock
                    )
            );

            policies.put(
                    "/api/upload",
                    new TokenBucketLimiter(
                            5,
                            0.5,
                            clock
                    )
            );
        }

        ApiResponse process(ApiRequest request) {
            RateLimiter limiter = policies.get(
                    request.endpoint()
            );

            if (limiter == null) {
                return new ApiResponse(
                        RequestStatus.INVALID,
                        404,
                        "Unknown endpoint",
                        null
                );
            }

            try {
                RateLimitDecision decision = limiter.evaluate(
                        request.userId(),
                        request.cost()
                );

                if (!decision.allowed()) {
                    return new ApiResponse(
                            RequestStatus.RATE_LIMITED,
                            429,
                            "Request quota exceeded",
                            decision
                    );
                }

                return new ApiResponse(
                        RequestStatus.ACCEPTED,
                        200,
                        "Request accepted",
                        decision
                );

            } catch (IllegalArgumentException exception) {
                return new ApiResponse(
                        RequestStatus.INVALID,
                        400,
                        exception.getMessage(),
                        null
                );
            }
        }
    }

    // ========================================================
    // VALIDATION
    // ========================================================

    private static void validateRequest(
            String key,
            int cost
    ) {
        if (key == null || key.isBlank() || cost <= 0) {
            throw new IllegalArgumentException(
                    "Invalid rate-limit request."
            );
        }
    }

    // ========================================================
    // TESTING
    // ========================================================

    static void runTests() {

        ManualClock clock = new ManualClock(10000);

        FixedWindowLimiter fixed =
                new FixedWindowLimiter(
                        2,
                        Duration.ofSeconds(10),
                        clock
                );

        if (
                !fixed.evaluate("alice", 1).allowed() ||
                !fixed.evaluate("alice", 1).allowed() ||
                fixed.evaluate("alice", 1).allowed()
        ) {
            throw new AssertionError("Fixed window test failed.");
        }

        clock.advance(10000);

        if (!fixed.evaluate("alice", 1).allowed()) {
            throw new AssertionError("Fixed window reset failed.");
        }

        SlidingWindowLimiter sliding =
                new SlidingWindowLimiter(
                        2,
                        Duration.ofSeconds(10),
                        clock
                );

        sliding.evaluate("bob", 1);

        clock.advance(5000);

        sliding.evaluate("bob", 1);

        if (sliding.evaluate("bob", 1).allowed()) {
            throw new AssertionError("Sliding window limit failed.");
        }

        clock.advance(5000);

        if (!sliding.evaluate("bob", 1).allowed()) {
            throw new AssertionError("Sliding expiration failed.");
        }

        TokenBucketLimiter bucket =
                new TokenBucketLimiter(2, 1, clock);

        if (
                !bucket.evaluate("carol", 1).allowed() ||
                !bucket.evaluate("carol", 1).allowed() ||
                bucket.evaluate("carol", 1).allowed()
        ) {
            throw new AssertionError("Token bucket test failed.");
        }

        clock.advance(1000);

        if (!bucket.evaluate("carol", 1).allowed()) {
            throw new AssertionError("Token refill failed.");
        }

        SharedDistributedStore sharedStore =
                new SharedDistributedStore();

        DistributedRateLimiter serverA =
                new DistributedRateLimiter(
                        sharedStore, 2, 1, clock
                );

        DistributedRateLimiter serverB =
                new DistributedRateLimiter(
                        sharedStore, 2, 1, clock
                );

        if (
                !serverA.evaluate("enterprise-user", 1).allowed() ||
                !serverB.evaluate("enterprise-user", 1).allowed() ||
                serverA.evaluate("enterprise-user", 1).allowed()
        ) {
            throw new AssertionError(
                    "Distributed rate limiting failed."
            );
        }

        System.out.println("All Java 17 tests passed.");
    }

    // ========================================================
    // DEMONSTRATION
    // ========================================================

    public static void main(String[] args) {

        System.out.println("ENTERPRISE RATE LIMITING ENGINE");
        System.out.println("================================");

        Clock clock = new SystemClock();

        EnterpriseApiGateway gateway =
                new EnterpriseApiGateway(clock);

        System.out.println("\nAPI Gateway:");

        for (int i = 1; i <= 7; i++) {

            ApiRequest request = new ApiRequest(
                    "customer-101",
                    "/api/login",
                    1,
                    "request-" + i
            );

            ApiResponse response = gateway.process(request);

            System.out.printf(
                    "Request %d | HTTP %d | %s%n",
                    i,
                    response.httpStatus(),
                    response.message()
            );
        }

        System.out.println("\nDistributed processing:");

        ManualClock distributedClock =
                new ManualClock(100000);

        SharedDistributedStore sharedStore =
                new SharedDistributedStore();

        DistributedRateLimiter serverA =
                new DistributedRateLimiter(
                        sharedStore,
                        3,
                        0.5,
                        distributedClock
                );

        DistributedRateLimiter serverB =
                new DistributedRateLimiter(
                        sharedStore,
                        3,
                        0.5,
                        distributedClock
                );

        for (int i = 1; i <= 5; i++) {

            DistributedRateLimiter server =
                    i % 2 == 0 ? serverA : serverB;

            RateLimitDecision result =
                    server.evaluate("enterprise-customer", 1);

            System.out.printf(
                    "Request %d | %s | Remaining: %d%n",
                    i,
                    result.allowed() ? "ALLOWED" : "BLOCKED",
                    result.remaining()
            );
        }

        System.out.println("\nTesting:");

        runTests();
    }
}
