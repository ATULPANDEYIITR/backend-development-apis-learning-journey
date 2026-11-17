#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

/*
 * Redis Advanced Governance Engine
 *
 * C++17 implementation of:
 * - Command pipelining
 * - Atomic transaction simulation
 * - Lua-style atomic script execution
 * - Distributed lease locks
 * - Fencing tokens
 * - Inventory reservation
 *
 * This program models Redis execution semantics in memory.
 * It does not require an external Redis client library.
 */

using namespace std;

// --------------------------------------------------
// Domain errors
// --------------------------------------------------

class RedisException : public runtime_error {
public:
    using runtime_error::runtime_error;
};

class ValidationException : public RedisException {
public:
    using RedisException::RedisException;
};

class LockException : public RedisException {
public:
    using RedisException::RedisException;
};

// --------------------------------------------------
// Redis value types
// --------------------------------------------------

enum class ValueType {
    STRING,
    HASH
};

struct RedisValue {
    ValueType type = ValueType::STRING;
    string stringValue;
    unordered_map<string, string> hashValue;
    long long expiresAt = -1;
};

struct CommandResult {
    bool success;
    string value;
    string error;

    static CommandResult ok(string value) {
        return {true, move(value), ""};
    }

    static CommandResult fail(string error) {
        return {false, "", move(error)};
    }
};

// --------------------------------------------------
// Redis storage engine
// --------------------------------------------------

class RedisEngine {
private:
    unordered_map<string, RedisValue> storage;
    uint64_t logicalClock = 0;

    void purgeExpired(const string& key) {
        auto it = storage.find(key);

        if (it == storage.end()) return;

        if (it->second.expiresAt != -1 &&
            it->second.expiresAt <= currentTime()) {
            storage.erase(it);
        }
    }

    static long long currentTime() {
        return chrono::duration_cast<chrono::milliseconds>(
            chrono::steady_clock::now().time_since_epoch()
        ).count();
    }

public:
    void set(const string& key, const string& value) {
        if (key.empty()) {
            throw ValidationException("Key cannot be empty");
        }

        RedisValue item;
        item.stringValue = value;

        storage[key] = move(item);
    }

    bool setNX(
        const string& key,
        const string& value,
        long long leaseMs
    ) {
        if (leaseMs <= 0) {
            throw ValidationException("Lease must be positive");
        }

        purgeExpired(key);

        if (storage.count(key)) return false;

        RedisValue item;
        item.stringValue = value;
        item.expiresAt = currentTime() + leaseMs;

        storage[key] = move(item);

        return true;
    }

    optional<string> get(const string& key) {
        purgeExpired(key);

        auto it = storage.find(key);

        if (it == storage.end()) return nullopt;

        if (it->second.type != ValueType::STRING) {
            throw RedisException("WRONGTYPE");
        }

        return it->second.stringValue;
    }

    long long incrementBy(
        const string& key,
        long long amount
    ) {
        purgeExpired(key);

        long long value = 0;

        auto existing = get(key);

        if (existing) {
            size_t position = 0;

            try {
                value = stoll(*existing, &position);

                if (position != existing->size()) {
                    throw ValidationException("Invalid integer");
                }
            } catch (const invalid_argument&) {
                throw ValidationException("Invalid integer");
            } catch (const out_of_range&) {
                throw ValidationException("Integer overflow");
            }
        }

        if ((amount > 0 &&
             value > numeric_limits<long long>::max() - amount) ||
            (amount < 0 &&
             value < numeric_limits<long long>::min() - amount)) {
            throw ValidationException("Integer overflow");
        }

        value += amount;
        set(key, to_string(value));

        return value;
    }

    void setHash(
        const string& key,
        const unordered_map<string, string>& fields
    ) {
        purgeExpired(key);

        RedisValue item;
        item.type = ValueType::HASH;
        item.hashValue = fields;

        storage[key] = move(item);
    }

    bool deleteKey(const string& key) {
        purgeExpired(key);
        return storage.erase(key) > 0;
    }

    bool compareAndDelete(
        const string& key,
        const string& token
    ) {
        auto value = get(key);

        if (!value || *value != token) {
            return false;
        }

        return deleteKey(key);
    }

    uint64_t nextFencingToken() {
        return ++logicalClock;
    }

    size_t size() const {
        return storage.size();
    }
};

// --------------------------------------------------
// Pipeline
// --------------------------------------------------

class Pipeline {
private:
    vector<function<CommandResult(RedisEngine&)>> commands;

public:
    void add(
        function<CommandResult(RedisEngine&)> command
    ) {
        commands.push_back(move(command));
    }

    vector<CommandResult> execute(RedisEngine& redis) {
        vector<CommandResult> results;

        results.reserve(commands.size());

        for (auto& command : commands) {
            try {
                results.push_back(command(redis));
            } catch (const exception& error) {
                results.push_back(
                    CommandResult::fail(error.what())
                );
            }
        }

        commands.clear();

        return results;
    }
};

// --------------------------------------------------
// Transaction
// --------------------------------------------------

class Transaction {
private:
    vector<function<CommandResult(RedisEngine&)>> commands;

public:
    void add(
        function<CommandResult(RedisEngine&)> command
    ) {
        commands.push_back(move(command));
    }

    vector<CommandResult> execute(RedisEngine& redis) {
        /*
         * Redis MULTI/EXEC provides atomic execution against
         * other clients, but it does not provide rollback when
         * an individual command encounters a runtime error.
         *
         * This in-memory simulation executes queued commands
         * sequentially without exposing intermediate results.
         */

        vector<CommandResult> results;

        results.reserve(commands.size());

        for (auto& command : commands) {
            try {
                results.push_back(command(redis));
            } catch (const exception& error) {
                results.push_back(
                    CommandResult::fail(error.what())
                );
            }
        }

        commands.clear();

        return results;
    }
};

// --------------------------------------------------
// Atomic script engine
// --------------------------------------------------

class ScriptEngine {
private:
    RedisEngine& redis;

public:
    explicit ScriptEngine(RedisEngine& engine)
        : redis(engine) {}

    long long reserveInventory(
        const string& inventoryKey,
        const string& reservationKey,
        long long quantity
    ) {
        if (quantity <= 0) {
            return -1;
        }

        auto value = redis.get(inventoryKey);

        long long stock = 0;

        if (value) {
            try {
                stock = stoll(*value);
            } catch (...) {
                throw ValidationException(
                    "Inventory value is not numeric"
                );
            }
        }

        if (stock < quantity) {
            return 0;
        }

        long long remaining =
            redis.incrementBy(inventoryKey, -quantity);

        redis.setHash(
            reservationKey,
            {
                {"quantity", to_string(quantity)},
                {"status", "reserved"}
            }
        );

        return remaining;
    }
};

// --------------------------------------------------
// Distributed lock
// --------------------------------------------------

enum class LockStatus {
    ACQUIRED,
    BUSY,
    RELEASED,
    NOT_OWNER
};

struct LockResult {
    LockStatus status;
    string token;
    uint64_t fencingToken;
};

class DistributedLock {
private:
    RedisEngine& redis;
    string key;
    string token;
    uint64_t fencingToken = 0;
    long long leaseMs;

public:
    DistributedLock(
        RedisEngine& engine,
        string lockKey,
        long long lease
    )
        : redis(engine),
          key(move(lockKey)),
          leaseMs(lease) {

        if (key.empty() || leaseMs <= 0) {
            throw ValidationException("Invalid lock configuration");
        }
    }

    LockResult acquire() {
        if (!token.empty()) {
            throw LockException("Lock instance already owns a token");
        }

        static mt19937_64 generator(
            random_device{}()
        );

        token = to_string(generator());

        if (!redis.setNX(key, token, leaseMs)) {
            token.clear();

            return {
                LockStatus::BUSY,
                "",
                0
            };
        }

        fencingToken = redis.nextFencingToken();

        return {
            LockStatus::ACQUIRED,
            token,
            fencingToken
        };
    }

    LockStatus release() {
        if (token.empty()) {
            return LockStatus::NOT_OWNER;
        }

        bool released = redis.compareAndDelete(
            key,
            token
        );

        token.clear();

        return released
            ? LockStatus::RELEASED
            : LockStatus::NOT_OWNER;
    }
};

// --------------------------------------------------
// Fencing token protection
// --------------------------------------------------

class ProtectedResource {
private:
    uint64_t highestToken = 0;
    string state;

public:
    bool update(
        uint64_t token,
        const string& newState
    ) {
        if (token <= highestToken) {
            return false;
        }

        highestToken = token;
        state = newState;

        return true;
    }

    string getState() const {
        return state;
    }
};

// --------------------------------------------------
// Inventory service
// --------------------------------------------------

class InventoryService {
private:
    RedisEngine& redis;
    ScriptEngine scripts;

public:
    explicit InventoryService(RedisEngine& engine)
        : redis(engine), scripts(engine) {}

    void initialize(
        const string& product,
        long long quantity
    ) {
        if (quantity < 0) {
            throw ValidationException("Negative inventory");
        }

        redis.set(
            "inventory:" + product,
            to_string(quantity)
        );
    }

    long long reserve(
        const string& product,
        const string& orderId,
        long long quantity
    ) {
        if (orderId.empty()) {
            throw ValidationException("Order ID is required");
        }

        return scripts.reserveInventory(
            "inventory:" + product,
            "reservation:" + orderId,
            quantity
        );
    }
};

// --------------------------------------------------
// Reporting
// --------------------------------------------------

void printResults(
    const string& heading,
    const vector<CommandResult>& results
) {
    cout << "\n" << heading << "\n";

    for (size_t i = 0; i < results.size(); ++i) {
        cout << "Command " << i + 1 << ": ";

        if (results[i].success) {
            cout << results[i].value;
        } else {
            cout << "ERROR: " << results[i].error;
        }

        cout << "\n";
    }
}

// --------------------------------------------------
// Main
// --------------------------------------------------

int main() {
    try {
        RedisEngine redis;

        cout << "REDIS ADVANCED ENGINEERING\n";

        // Pipeline demonstration.
        Pipeline pipeline;

        pipeline.add([](RedisEngine& engine) {
            engine.set("analytics:requests", "100");
            return CommandResult::ok("SET completed");
        });

        pipeline.add([](RedisEngine& engine) {
            auto value = engine.incrementBy(
                "analytics:requests",
                50
            );

            return CommandResult::ok(to_string(value));
        });

        pipeline.add([](RedisEngine& engine) {
            auto value = engine.get("analytics:requests");

            return CommandResult::ok(
                value.value_or("nil")
            );
        });

        printResults(
            "PIPELINE",
            pipeline.execute(redis)
        );

        // Transaction demonstration.
        Transaction transaction;

        transaction.add([](RedisEngine& engine) {
            engine.set("wallet:A", "1000");
            return CommandResult::ok("Wallet A initialized");
        });

        transaction.add([](RedisEngine& engine) {
            engine.set("wallet:B", "500");
            return CommandResult::ok("Wallet B initialized");
        });

        transaction.add([](RedisEngine& engine) {
            engine.incrementBy("wallet:A", -100);
            return CommandResult::ok("Debit completed");
        });

        transaction.add([](RedisEngine& engine) {
            engine.incrementBy("wallet:B", 100);
            return CommandResult::ok("Credit completed");
        });

        printResults(
            "TRANSACTION",
            transaction.execute(redis)
        );

        // Lua-style atomic inventory reservation.
        InventoryService inventory(redis);

        inventory.initialize("laptop", 20);

        cout << "\nLUA SCRIPT SIMULATION\n";

        cout << "Remaining stock: "
             << inventory.reserve(
                 "laptop",
                 "ORDER-1001",
                 5
             )
             << "\n";

        cout << "Insufficient stock result: "
             << inventory.reserve(
                 "laptop",
                 "ORDER-1002",
                 100
             )
             << "\n";

        // Distributed lock demonstration.
        cout << "\nDISTRIBUTED LOCK\n";

        DistributedLock workerA(
            redis,
            "locks:inventory",
            10000
        );

        DistributedLock workerB(
            redis,
            "locks:inventory",
            10000
        );

        LockResult first = workerA.acquire();
        LockResult second = workerB.acquire();

        cout << "Worker A acquired: "
             << (first.status == LockStatus::ACQUIRED)
             << "\n";

        cout << "Worker B acquired: "
             << (second.status == LockStatus::ACQUIRED)
             << "\n";

        cout << "Worker A released: "
             << (workerA.release() == LockStatus::RELEASED)
             << "\n";

        // Fencing token demonstration.
        cout << "\nFENCING TOKEN\n";

        ProtectedResource resource;

        bool accepted = resource.update(
            first.fencingToken,
            "reconciliation-completed"
        );

        bool rejected = resource.update(
            first.fencingToken,
            "stale-worker-update"
        );

        cout << "First update accepted: " << accepted << "\n";
        cout << "Stale update accepted: " << rejected << "\n";

        cout << "\nStored keys: " << redis.size() << "\n";

        cout << "Execution completed.\n";

    } catch (const exception& error) {
        cerr << "ERROR: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
