#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;

// ============================================================
// DOMAIN TYPES
// ============================================================

enum class Algorithm {
    FIXED_WINDOW,
    SLIDING_WINDOW,
    TOKEN_BUCKET
};

string algorithmName(Algorithm algorithm) {
    switch (algorithm) {
        case Algorithm::FIXED_WINDOW:
            return "Fixed Window";

        case Algorithm::SLIDING_WINDOW:
            return "Sliding Window";

        case Algorithm::TOKEN_BUCKET:
            return "Token Bucket";
    }

    return "Unknown";
}

struct Decision {
    bool allowed;
    int remaining;
    double retryAfterSeconds;
    string algorithm;
};

struct WindowState {
    int64_t start;
    int count;
};

struct BucketState {
    double tokens;
    int64_t lastUpdate;
};

// ============================================================
// VALIDATION
// ============================================================

void validateConfiguration(int limit, int64_t window) {
    if (limit <= 0 || window <= 0) {
        throw invalid_argument("Invalid rate limit configuration.");
    }
}

void validateRequest(const string& key, int cost) {
    if (key.empty() || cost <= 0) {
        throw invalid_argument("Invalid request key or cost.");
    }
}

// ============================================================
// FIXED WINDOW LIMITER
// ============================================================

class FixedWindowLimiter {
private:
    int limit;
    int64_t windowMs;

    unordered_map<string, WindowState> states;
    mutable mutex stateMutex;

public:
    FixedWindowLimiter(int requestLimit, int64_t window)
        : limit(requestLimit), windowMs(window) {
        validateConfiguration(limit, windowMs);
    }

    Decision allow(
        const string& key,
        int cost,
        int64_t nowMs
    ) {
        validateRequest(key, cost);

        lock_guard<mutex> guard(stateMutex);

        int64_t windowStart =
            (nowMs / windowMs) * windowMs;

        auto iterator = states.find(key);

        if (iterator == states.end()) {
            iterator = states.emplace(
                key,
                WindowState{windowStart, 0}
            ).first;
        }

        WindowState& state = iterator->second;

        if (state.start != windowStart) {
            state.start = windowStart;
            state.count = 0;
        }

        bool allowed = cost <= limit &&
                       state.count + cost <= limit;

        if (allowed) {
            state.count += cost;
        }

        int remaining = max(0, limit - state.count);

        double retry = allowed
            ? 0.0
            : static_cast<double>(
                windowStart + windowMs - nowMs
            ) / 1000.0;

        return {
            allowed,
            remaining,
            retry,
            "Fixed Window"
        };
    }
};

// ============================================================
// SLIDING WINDOW LIMITER
// ============================================================

class SlidingWindowLimiter {
private:
    int limit;
    int64_t windowMs;

    unordered_map<string, deque<int64_t>> requests;
    mutable mutex stateMutex;

public:
    SlidingWindowLimiter(int requestLimit, int64_t window)
        : limit(requestLimit), windowMs(window) {
        validateConfiguration(limit, windowMs);
    }

    Decision allow(
        const string& key,
        int cost,
        int64_t nowMs
    ) {
        validateRequest(key, cost);

        if (cost > limit) {
            return {
                false,
                0,
                0.0,
                "Sliding Window"
            };
        }

        lock_guard<mutex> guard(stateMutex);

        auto& timestamps = requests[key];

        int64_t cutoff = nowMs - windowMs;

        while (
            !timestamps.empty() &&
            timestamps.front() <= cutoff
        ) {
            timestamps.pop_front();
        }

        bool allowed =
            static_cast<int>(timestamps.size()) + cost <= limit;

        if (allowed) {
            for (int i = 0; i < cost; ++i) {
                timestamps.push_back(nowMs);
            }
        }

        double retry = 0.0;

        if (!allowed && !timestamps.empty()) {
            retry = max(
                0.0,
                static_cast<double>(
                    timestamps.front() + windowMs - nowMs
                ) / 1000.0
            );
        }

        return {
            allowed,
            max(0, limit - static_cast<int>(timestamps.size())),
            retry,
            "Sliding Window"
        };
    }
};

// ============================================================
// TOKEN BUCKET LIMITER
// ============================================================

class TokenBucketLimiter {
private:
    double capacity;
    double refillRate;

    unordered_map<string, BucketState> buckets;
    mutable mutex stateMutex;

public:
    TokenBucketLimiter(double bucketCapacity, double refillPerSecond)
        : capacity(bucketCapacity),
          refillRate(refillPerSecond) {

        if (
            !isfinite(capacity) ||
            !isfinite(refillRate) ||
            capacity <= 0 ||
            refillRate <= 0
        ) {
            throw invalid_argument("Invalid token bucket configuration.");
        }
    }

    Decision allow(
        const string& key,
        double cost,
        int64_t nowMs
    ) {
        if (
            key.empty() ||
            !isfinite(cost) ||
            cost <= 0
        ) {
            throw invalid_argument("Invalid token bucket request.");
        }

        lock_guard<mutex> guard(stateMutex);

        auto iterator = buckets.find(key);

        if (iterator == buckets.end()) {
            iterator = buckets.emplace(
                key,
                BucketState{capacity, nowMs}
            ).first;
        }

        BucketState& state = iterator->second;

        int64_t elapsedMs = max(
            int64_t(0),
            nowMs - state.lastUpdate
        );

        double elapsedSeconds =
            static_cast<double>(elapsedMs) / 1000.0;

        state.tokens = min(
            capacity,
            state.tokens + elapsedSeconds * refillRate
        );

        state.lastUpdate = max(state.lastUpdate, nowMs);

        bool allowed = cost <= capacity && state.tokens >= cost;

        if (allowed) {
            state.tokens -= cost;
        }

        double retry = 0.0;

        if (!allowed && cost <= capacity) {
            retry = (cost - state.tokens) / refillRate;
        }

        return {
            allowed,
            static_cast<int>(floor(state.tokens)),
            retry,
            "Token Bucket"
        };
    }
};

// ============================================================
// DISTRIBUTED RATE LIMITING
// ============================================================

class SharedStateStore {
private:
    unordered_map<string, BucketState> states;
    mutable mutex storeMutex;

    friend class DistributedRateLimiter;
};

class DistributedRateLimiter {
private:
    SharedStateStore& store;
    double capacity;
    double refillRate;

public:
    DistributedRateLimiter(
        SharedStateStore& sharedStore,
        double bucketCapacity,
        double refillPerSecond
    )
        : store(sharedStore),
          capacity(bucketCapacity),
          refillRate(refillPerSecond) {

        if (
            !isfinite(capacity) ||
            !isfinite(refillRate) ||
            capacity <= 0 ||
            refillRate <= 0
        ) {
            throw invalid_argument("Invalid distributed configuration.");
        }
    }

    Decision allow(
        const string& user,
        double cost,
        int64_t nowMs
    ) {
        if (
            user.empty() ||
            !isfinite(cost) ||
            cost <= 0
        ) {
            throw invalid_argument("Invalid distributed request.");
        }

        lock_guard<mutex> guard(store.storeMutex);

        string key = "rate:" + user;

        auto iterator = store.states.find(key);

        if (iterator == store.states.end()) {
            iterator = store.states.emplace(
                key,
                BucketState{capacity, nowMs}
            ).first;
        }

        BucketState& state = iterator->second;

        int64_t elapsedMs = max(
            int64_t(0),
            nowMs - state.lastUpdate
        );

        state.tokens = min(
            capacity,
            state.tokens +
            (elapsedMs / 1000.0) * refillRate
        );

        state.lastUpdate = max(state.lastUpdate, nowMs);

        bool allowed = cost <= capacity && state.tokens >= cost;

        if (allowed) {
            state.tokens -= cost;
        }

        double retry = 0.0;

        if (!allowed && cost <= capacity) {
            retry = (cost - state.tokens) / refillRate;
        }

        return {
            allowed,
            static_cast<int>(floor(state.tokens)),
            retry,
            "Distributed Token Bucket"
        };
    }
};

// ============================================================
// API GATEWAY
// ============================================================

class APIGateway {
private:
    FixedWindowLimiter loginLimiter{5, 60000};
    SlidingWindowLimiter searchLimiter{10, 60000};
    TokenBucketLimiter uploadLimiter{5, 0.1};

public:
    Decision handle(
        const string& endpoint,
        const string& user,
        int64_t nowMs
    ) {
        if (endpoint == "/login") {
            return loginLimiter.allow(user, 1, nowMs);
        }

        if (endpoint == "/search") {
            return searchLimiter.allow(user, 1, nowMs);
        }

        if (endpoint == "/upload") {
            return uploadLimiter.allow(user, 1.0, nowMs);
        }

        throw invalid_argument("Unknown API endpoint.");
    }
};

// ============================================================
// REPORTING
// ============================================================

void printDecision(
    const string& request,
    const Decision& decision
) {
    cout << left << setw(28) << request
         << " | "
         << (decision.allowed ? "ALLOWED" : "BLOCKED")
         << " | Remaining: " << decision.remaining
         << " | Retry: "
         << fixed << setprecision(3)
         << decision.retryAfterSeconds
         << " seconds\n";
}

// ============================================================
// TESTS
// ============================================================

void runTests() {
    FixedWindowLimiter fixed(2, 1000);

    auto a = fixed.allow("alice", 1, 10000);
    auto b = fixed.allow("alice", 1, 10000);
    auto c = fixed.allow("alice", 1, 10000);

    if (!a.allowed || !b.allowed || c.allowed) {
        throw runtime_error("Fixed window test failed.");
    }

    auto d = fixed.allow("alice", 1, 11000);

    if (!d.allowed) {
        throw runtime_error("Fixed window reset failed.");
    }

    SlidingWindowLimiter sliding(2, 1000);

    if (!sliding.allow("bob", 1, 10000).allowed) {
        throw runtime_error("Sliding window test failed.");
    }

    sliding.allow("bob", 1, 10500);

    if (sliding.allow("bob", 1, 10500).allowed) {
        throw runtime_error("Sliding window limit failed.");
    }

    if (!sliding.allow("bob", 1, 11000).allowed) {
        throw runtime_error("Sliding window expiration failed.");
    }

    TokenBucketLimiter bucket(2, 1.0);

    if (!bucket.allow("carol", 1, 10000).allowed ||
        !bucket.allow("carol", 1, 10000).allowed ||
        bucket.allow("carol", 1, 10000).allowed) {
        throw runtime_error("Token bucket test failed.");
    }

    if (!bucket.allow("carol", 1, 11000).allowed) {
        throw runtime_error("Token refill test failed.");
    }

    SharedStateStore shared;

    DistributedRateLimiter serverA(shared, 2, 1);
    DistributedRateLimiter serverB(shared, 2, 1);

    auto x = serverA.allow("customer-1", 1, 10000);
    auto y = serverB.allow("customer-1", 1, 10000);
    auto z = serverA.allow("customer-1", 1, 10000);

    if (!x.allowed || !y.allowed || z.allowed) {
        throw runtime_error("Distributed state test failed.");
    }

    cout << "All C++17 tests passed.\n";
}

// ============================================================
// MAIN
// ============================================================

int main() {
    try {
        cout << "RATE LIMITING ENGINE\n";
        cout << "====================\n\n";

        APIGateway gateway;

        cout << "API gateway login requests:\n";

        for (int i = 1; i <= 7; ++i) {
            Decision result = gateway.handle(
                "/login",
                "user-101",
                10000
            );

            printDecision(
                "Login request " + to_string(i),
                result
            );
        }

        cout << "\nDistributed request processing:\n";

        SharedStateStore sharedStore;

        DistributedRateLimiter serverA(
            sharedStore, 3, 0.5
        );

        DistributedRateLimiter serverB(
            sharedStore, 3, 0.5
        );

        for (int i = 1; i <= 5; ++i) {
            DistributedRateLimiter& server =
                i % 2 == 0 ? serverA : serverB;

            Decision result = server.allow(
                "enterprise-customer",
                1,
                20000
            );

            printDecision(
                "Server " + to_string(i % 2 + 1) +
                " request " + to_string(i),
                result
            );
        }

        cout << "\nExecuting tests:\n";
        runTests();

    } catch (const exception& error) {
        cerr << "Failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
