#include <algorithm>
#include <chrono>
#include <cmath>
#include <exception>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

using namespace std;

enum class DataType {
    STRING,
    HASH,
    LIST,
    SET,
    ZSET
};

using Hash = map<string, string>;
using List = vector<string>;
using Set = set<string>;
using SortedSet = map<string, double>;

using Value = variant<
    string,
    Hash,
    List,
    Set,
    SortedSet
>;

struct Entry {
    Value value;
    optional<chrono::steady_clock::time_point> expiresAt;
};

class RedisError : public runtime_error {
public:
    explicit RedisError(const string& message)
        : runtime_error(message) {}
};

class WrongTypeError : public RedisError {
public:
    explicit WrongTypeError(const string& message)
        : RedisError(message) {}
};

class ValidationError : public RedisError {
public:
    explicit ValidationError(const string& message)
        : RedisError(message) {}
};

class RedisStore {
private:
    unordered_map<string, Entry> data;

    void validateKey(const string& key) const {
        if (key.empty()) {
            throw ValidationError("Key cannot be empty.");
        }
    }

    void purge(const string& key) {
        auto it = data.find(key);

        if (it == data.end()) return;

        if (it->second.expiresAt &&
            chrono::steady_clock::now() >= *it->second.expiresAt) {
            data.erase(it);
        }
    }

    Entry* find(const string& key) {
        validateKey(key);
        purge(key);

        auto it = data.find(key);

        if (it == data.end()) return nullptr;

        return &it->second;
    }

    template<typename T>
    Entry& getOrCreate(const string& key) {
        validateKey(key);
        purge(key);

        auto it = data.find(key);

        if (it == data.end()) {
            auto inserted = data.emplace(
                key,
                Entry{T{}, nullopt}
            );

            return inserted.first->second;
        }

        if (!holds_alternative<T>(it->second.value)) {
            throw WrongTypeError("Operation uses an incorrect data type.");
        }

        return it->second;
    }

public:

    // STRING OPERATIONS

    void set(const string& key, const string& value) {
        validateKey(key);
        data[key] = Entry{value, nullopt};
    }

    optional<string> get(const string& key) {
        Entry* entry = find(key);

        if (!entry) return nullopt;

        if (!holds_alternative<string>(entry->value)) {
            throw WrongTypeError("GET requires a string.");
        }

        return get<string>(entry->value);
    }

    long long incrBy(const string& key, long long amount = 1) {
        auto current = get(key);
        long long value = 0;

        if (current) {
            try {
                size_t consumed = 0;
                value = stoll(*current, &consumed);

                if (consumed != current->size()) {
                    throw ValidationError("Invalid integer value.");
                }
            } catch (const invalid_argument&) {
                throw ValidationError("Stored value is not an integer.");
            } catch (const out_of_range&) {
                throw ValidationError("Integer is out of range.");
            }
        }

        if ((amount > 0 &&
             value > numeric_limits<long long>::max() - amount) ||
            (amount < 0 &&
             value < numeric_limits<long long>::min() - amount)) {
            throw ValidationError("Integer overflow.");
        }

        value += amount;
        set(key, to_string(value));
        return value;
    }

    // HASH OPERATIONS

    bool hset(
        const string& key,
        const string& field,
        const string& value
    ) {
        if (field.empty()) {
            throw ValidationError("Hash field cannot be empty.");
        }

        Entry& entry = getOrCreate<Hash>(key);
        auto& hash = get<Hash>(entry.value);

        return hash.emplace(field, value).second
            ? true
            : (hash[field] = value, false);
    }

    optional<string> hget(
        const string& key,
        const string& field
    ) {
        Entry* entry = find(key);

        if (!entry) return nullopt;

        if (!holds_alternative<Hash>(entry->value)) {
            throw WrongTypeError("HGET requires a hash.");
        }

        const auto& hash = get<Hash>(entry->value);
        auto it = hash.find(field);

        if (it == hash.end()) return nullopt;

        return it->second;
    }

    Hash hgetall(const string& key) {
        Entry* entry = find(key);

        if (!entry) return {};

        if (!holds_alternative<Hash>(entry->value)) {
            throw WrongTypeError("HGETALL requires a hash.");
        }

        return get<Hash>(entry->value);
    }

    // LIST OPERATIONS

    size_t lpush(const string& key, const string& value) {
        Entry& entry = getOrCreate<List>(key);
        auto& list = get<List>(entry.value);

        list.insert(list.begin(), value);
        return list.size();
    }

    size_t rpush(const string& key, const string& value) {
        Entry& entry = getOrCreate<List>(key);
        auto& list = get<List>(entry.value);

        list.push_back(value);
        return list.size();
    }

    optional<string> lpop(const string& key) {
        Entry* entry = find(key);

        if (!entry) return nullopt;

        if (!holds_alternative<List>(entry->value)) {
            throw WrongTypeError("LPOP requires a list.");
        }

        auto& list = get<List>(entry->value);

        if (list.empty()) return nullopt;

        string result = list.front();
        list.erase(list.begin());

        if (list.empty()) data.erase(key);

        return result;
    }

    vector<string> lrange(
        const string& key,
        int start,
        int stop
    ) {
        Entry* entry = find(key);

        if (!entry) return {};

        if (!holds_alternative<List>(entry->value)) {
            throw WrongTypeError("LRANGE requires a list.");
        }

        const auto& list = get<List>(entry->value);
        int size = static_cast<int>(list.size());

        if (start < 0) start = max(0, size + start);
        if (stop < 0) stop = size + stop;

        vector<string> result;

        for (int i = start; i <= stop && i < size; ++i) {
            if (i >= 0) result.push_back(list[i]);
        }

        return result;
    }

    // SET OPERATIONS

    size_t sadd(const string& key, const string& member) {
        Entry& entry = getOrCreate<Set>(key);
        auto& members = get<Set>(entry.value);

        return members.insert(member).second ? 1 : 0;
    }

    size_t srem(const string& key, const string& member) {
        Entry* entry = find(key);

        if (!entry) return 0;

        if (!holds_alternative<Set>(entry->value)) {
            throw WrongTypeError("SREM requires a set.");
        }

        auto& members = get<Set>(entry->value);
        size_t removed = members.erase(member);

        if (members.empty()) data.erase(key);

        return removed;
    }

    Set smembers(const string& key) {
        Entry* entry = find(key);

        if (!entry) return {};

        if (!holds_alternative<Set>(entry->value)) {
            throw WrongTypeError("SMEMBERS requires a set.");
        }

        return get<Set>(entry->value);
    }

    Set sinter(const string& first, const string& second) {
        Set a = smembers(first);
        Set b = smembers(second);
        Set result;

        set_intersection(
            a.begin(), a.end(),
            b.begin(), b.end(),
            inserter(result, result.begin())
        );

        return result;
    }

    Set sunion(const string& first, const string& second) {
        Set a = smembers(first);
        Set b = smembers(second);

        a.insert(b.begin(), b.end());
        return a;
    }

    // SORTED SET OPERATIONS

    bool zadd(
        const string& key,
        const string& member,
        double score
    ) {
        if (!isfinite(score)) {
            throw ValidationError("Score must be finite.");
        }

        Entry& entry = getOrCreate<SortedSet>(key);
        auto& members = get<SortedSet>(entry.value);

        return members.emplace(member, score).second
            ? true
            : (members[member] = score, false);
    }

    vector<pair<string, double>> zrange(
        const string& key,
        int start,
        int stop
    ) {
        Entry* entry = find(key);

        if (!entry) return {};

        if (!holds_alternative<SortedSet>(entry->value)) {
            throw WrongTypeError("ZRANGE requires a sorted set.");
        }

        const auto& members = get<SortedSet>(entry->value);

        vector<pair<string, double>> ordered(
            members.begin(),
            members.end()
        );

        sort(
            ordered.begin(),
            ordered.end(),
            [](const auto& a, const auto& b) {
                if (a.second != b.second) {
                    return a.second < b.second;
                }

                return a.first < b.first;
            }
        );

        int size = static_cast<int>(ordered.size());

        if (start < 0) start = max(0, size + start);
        if (stop < 0) stop = size + stop;

        vector<pair<string, double>> result;

        for (int i = start; i <= stop && i < size; ++i) {
            if (i >= 0) result.push_back(ordered[i]);
        }

        return result;
    }

    // KEY MANAGEMENT

    bool exists(const string& key) {
        return find(key) != nullptr;
    }

    size_t del(const string& key) {
        validateKey(key);
        purge(key);
        return data.erase(key);
    }

    void expire(const string& key, int seconds) {
        if (seconds <= 0) {
            throw ValidationError("TTL must be positive.");
        }

        Entry* entry = find(key);

        if (!entry) return;

        entry->expiresAt =
            chrono::steady_clock::now() +
            chrono::seconds(seconds);
    }

    long long ttl(const string& key) {
        Entry* entry = find(key);

        if (!entry) return -2;
        if (!entry->expiresAt) return -1;

        auto remaining = chrono::duration_cast<chrono::seconds>(
            *entry->expiresAt - chrono::steady_clock::now()
        ).count();

        return max(0LL, remaining);
    }

    string type(const string& key) {
        Entry* entry = find(key);

        if (!entry) return "none";

        if (holds_alternative<string>(entry->value)) return "string";
        if (holds_alternative<Hash>(entry->value)) return "hash";
        if (holds_alternative<List>(entry->value)) return "list";
        if (holds_alternative<Set>(entry->value)) return "set";

        return "zset";
    }

    size_t dbsize() {
        vector<string> keys;

        for (const auto& [key, entry] : data) {
            keys.push_back(key);
        }

        for (const auto& key : keys) purge(key);

        return data.size();
    }

    // Atomic in-memory snapshot for rollback demonstrations.
    void transaction(
        const function<void(RedisStore&)>& operations
    ) {
        auto snapshot = data;

        try {
            operations(*this);
        } catch (...) {
            data = move(snapshot);
            throw;
        }
    }
};

void printSet(const Set& values) {
    cout << "{ ";

    for (const auto& value : values) {
        cout << value << " ";
    }

    cout << "}";
}

void demonstration() {
    RedisStore redis;

    cout << "\n=== STRINGS ===\n";

    redis.set("counter", "100");
    cout << "Counter: " << redis.incrBy("counter", 25) << "\n";

    cout << "\n=== HASHES ===\n";

    redis.hset("user:1001", "name", "Atul");
    redis.hset("user:1001", "role", "developer");

    for (const auto& [field, value] : redis.hgetall("user:1001")) {
        cout << field << " = " << value << "\n";
    }

    cout << "\n=== LISTS ===\n";

    redis.rpush("queue", "job-A");
    redis.rpush("queue", "job-B");
    redis.lpush("queue", "urgent");

    for (const auto& item : redis.lrange("queue", 0, -1)) {
        cout << item << " ";
    }

    cout << "\nProcessed: " << *redis.lpop("queue") << "\n";

    cout << "\n=== SETS ===\n";

    redis.sadd("developers", "Python");
    redis.sadd("developers", "Java");
    redis.sadd("developers", "C++");

    redis.sadd("cloud", "Java");
    redis.sadd("cloud", "Go");

    cout << "Intersection: ";
    printSet(redis.sinter("developers", "cloud"));

    cout << "\nUnion: ";
    printSet(redis.sunion("developers", "cloud"));

    cout << "\n\n=== SORTED SETS ===\n";

    redis.zadd("leaderboard", "Alice", 950);
    redis.zadd("leaderboard", "Bob", 850);
    redis.zadd("leaderboard", "Charlie", 900);

    for (const auto& [member, score] :
         redis.zrange("leaderboard", 0, -1)) {
        cout << member << ": " << score << "\n";
    }

    cout << "\n=== EXPIRATION ===\n";

    redis.set("session:1", "active");
    redis.expire("session:1", 60);

    cout << "TTL: " << redis.ttl("session:1") << "\n";

    cout << "\n=== TRANSACTION ===\n";

    try {
        redis.transaction([](RedisStore& store) {
            store.set("temporary", "value");
            throw RedisError("Simulated failure.");
        });
    } catch (const RedisError& error) {
        cout << "Rollback: " << error.what() << "\n";
    }

    cout << "Temporary exists: "
         << boolalpha << redis.exists("temporary") << "\n";

    cout << "\n=== KEY MANAGEMENT ===\n";

    cout << "User type: " << redis.type("user:1001") << "\n";
    cout << "Database size: " << redis.dbsize() << "\n";
}

void runTests() {
    RedisStore redis;

    redis.set("counter", "10");
    if (redis.incrBy("counter", 5) != 15) {
        throw runtime_error("String test failed.");
    }

    redis.hset("user", "name", "Atul");
    if (redis.hget("user", "name") != optional<string>("Atul")) {
        throw runtime_error("Hash test failed.");
    }

    redis.rpush("queue", "A");
    redis.lpush("queue", "B");

    if (redis.lrange("queue", 0, -1) !=
        vector<string>{"B", "A"}) {
        throw runtime_error("List test failed.");
    }

    redis.sadd("A", "x");
    redis.sadd("A", "y");
    redis.sadd("B", "y");

    if (redis.sinter("A", "B") != Set{"y"}) {
        throw runtime_error("Set test failed.");
    }

    redis.zadd("scores", "Alice", 10);
    redis.zadd("scores", "Bob", 20);

    if (redis.zrange("scores", 0, -1).front().first != "Alice") {
        throw runtime_error("Sorted-set test failed.");
    }

    redis.set("rollback", "original");

    try {
        redis.transaction([](RedisStore& store) {
            store.set("rollback", "changed");
            throw RedisError("Failure");
        });
    } catch (const RedisError&) {}

    if (redis.get("rollback") != optional<string>("original")) {
        throw runtime_error("Transaction rollback test failed.");
    }

    bool wrongTypeDetected = false;

    try {
        redis.hgetall("counter");
    } catch (const WrongTypeError&) {
        wrongTypeDetected = true;
    }

    if (!wrongTypeDetected) {
        throw runtime_error("Type validation test failed.");
    }

    cout << "\nAll C++17 tests passed.\n";
}

int main() {
    try {
        demonstration();
        runTests();
    } catch (const exception& error) {
        cerr << "Application error: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
