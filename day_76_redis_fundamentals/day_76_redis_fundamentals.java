import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.stream.Collectors;

/*
 * Redis Fundamentals: Enterprise Cache Management
 *
 * Java 17 implementation demonstrating:
 * - Redis key-value structures
 * - String, hash, list, set and sorted-set operations
 * - TTL and expiration
 * - Type-safe domain modeling
 * - Thread-safe access
 * - Transaction rollback
 * - Cache service boundaries
 * - Validation and error handling
 *
 * No external dependencies.
 *
 * Compile: javac RedisFundamentals.java
 * Run: java RedisFundamentals
 */

public class RedisFundamentals {

    enum RedisType {
        STRING, HASH, LIST, SET, ZSET
    }

    enum CacheStatus {
        HIT, MISS, EXPIRED
    }

    static class RedisException extends RuntimeException {
        RedisException(String message) {
            super(message);
        }
    }

    static class WrongTypeException extends RedisException {
        WrongTypeException(String message) {
            super(message);
        }
    }

    static class ValidationException extends RedisException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class CacheEntry<T> {
        private final RedisType type;
        private T value;
        private Long expiresAtMillis;

        CacheEntry(RedisType type, T value) {
            this.type = type;
            this.value = value;
            this.expiresAtMillis = null;
        }

        RedisType getType() {
            return type;
        }

        T getValue() {
            return value;
        }

        void setValue(T value) {
            this.value = value;
        }

        Long getExpiresAtMillis() {
            return expiresAtMillis;
        }

        void setExpiresAtMillis(Long expiration) {
            this.expiresAtMillis = expiration;
        }
    }

    record CacheResult<T>(
        CacheStatus status,
        T value
    ) {}

    record RankedMember(
        String member,
        double score
    ) {}

    static class RedisStore {

        private final Map<String, CacheEntry<?>> database =
            new HashMap<>();

        private final ReentrantReadWriteLock lock =
            new ReentrantReadWriteLock();

        private long operations = 0;

        private void validateKey(String key) {
            if (key == null || key.isBlank()) {
                throw new ValidationException(
                    "Key must not be null or blank."
                );
            }
        }

        private void purge(String key) {
            CacheEntry<?> entry = database.get(key);

            if (entry == null) return;

            Long expiration = entry.getExpiresAtMillis();

            if (expiration != null &&
                System.currentTimeMillis() >= expiration) {
                database.remove(key);
            }
        }

        private <T> CacheEntry<T> create(
            String key,
            RedisType type,
            T initialValue
        ) {
            validateKey(key);
            purge(key);

            CacheEntry<?> existing = database.get(key);

            if (existing == null) {
                CacheEntry<T> created =
                    new CacheEntry<>(type, initialValue);

                database.put(key, created);
                operations++;

                return created;
            }

            if (existing.getType() != type) {
                throw new WrongTypeException(
                    "Expected " + type + ", received " +
                    existing.getType()
                );
            }

            @SuppressWarnings("unchecked")
            CacheEntry<T> typed = (CacheEntry<T>) existing;

            return typed;
        }

        private CacheEntry<?> find(String key) {
            validateKey(key);
            purge(key);
            return database.get(key);
        }

        private <T> T read(
            String key,
            RedisType expected,
            Class<T> valueClass
        ) {
            CacheEntry<?> entry = find(key);

            if (entry == null) return null;

            if (entry.getType() != expected) {
                throw new WrongTypeException(
                    "Operation requires " + expected
                );
            }

            return valueClass.cast(entry.getValue());
        }

        // STRING OPERATIONS

        public boolean set(String key, String value) {
            validateKey(key);

            if (value == null) {
                throw new ValidationException("Null string value.");
            }

            lock.writeLock().lock();

            try {
                database.put(
                    key,
                    new CacheEntry<>(RedisType.STRING, value)
                );

                operations++;
                return true;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public boolean setIfAbsent(String key, String value) {
            validateKey(key);

            if (value == null) {
                throw new ValidationException("Null value.");
            }

            lock.writeLock().lock();

            try {
                purge(key);

                if (database.containsKey(key)) {
                    return false;
                }

                database.put(
                    key,
                    new CacheEntry<>(RedisType.STRING, value)
                );

                operations++;
                return true;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public CacheResult<String> get(String key) {
            lock.writeLock().lock();

            try {
                validateKey(key);

                CacheEntry<?> before = database.get(key);
                boolean wasExpired = before != null &&
                    before.getExpiresAtMillis() != null &&
                    System.currentTimeMillis() >=
                    before.getExpiresAtMillis();

                CacheEntry<?> entry = find(key);

                if (entry == null) {
                    return new CacheResult<>(
                        wasExpired ? CacheStatus.EXPIRED : CacheStatus.MISS,
                        null
                    );
                }

                if (entry.getType() != RedisType.STRING) {
                    throw new WrongTypeException(
                        "GET requires STRING."
                    );
                }

                return new CacheResult<>(
                    CacheStatus.HIT,
                    (String) entry.getValue()
                );
            } finally {
                lock.writeLock().unlock();
            }
        }

        public long incrBy(String key, long increment) {
            lock.writeLock().lock();

            try {
                CacheResult<String> result = get(key);

                long current = 0;

                if (result.value() != null) {
                    try {
                        current = Long.parseLong(result.value());
                    } catch (NumberFormatException exception) {
                        throw new RedisException(
                            "Stored value is not an integer."
                        );
                    }
                }

                long updated = Math.addExact(current, increment);

                set(key, Long.toString(updated));
                return updated;
            } finally {
                lock.writeLock().unlock();
            }
        }

        // HASH OPERATIONS

        public boolean hset(
            String key,
            String field,
            String value
        ) {
            if (field == null || field.isBlank() || value == null) {
                throw new ValidationException("Invalid hash entry.");
            }

            lock.writeLock().lock();

            try {
                Map<String, String> hash = create(
                    key,
                    RedisType.HASH,
                    new LinkedHashMap<>()
                ).getValue();

                boolean added = !hash.containsKey(field);
                hash.put(field, value);

                operations++;
                return added;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public Optional<String> hget(
            String key,
            String field
        ) {
            lock.readLock().lock();

            try {
                Map<String, String> hash = read(
                    key,
                    RedisType.HASH,
                    Map.class
                );

                return hash == null
                    ? Optional.empty()
                    : Optional.ofNullable(hash.get(field));
            } finally {
                lock.readLock().unlock();
            }
        }

        public Map<String, String> hgetall(String key) {
            lock.readLock().lock();

            try {
                Map<String, String> hash = read(
                    key,
                    RedisType.HASH,
                    Map.class
                );

                return hash == null
                    ? Map.of()
                    : Map.copyOf(hash);
            } finally {
                lock.readLock().unlock();
            }
        }

        public int hdel(String key, String field) {
            lock.writeLock().lock();

            try {
                Map<String, String> hash = read(
                    key,
                    RedisType.HASH,
                    Map.class
                );

                if (hash == null) return 0;

                int removed = hash.remove(field) == null ? 0 : 1;

                if (hash.isEmpty()) database.remove(key);

                return removed;
            } finally {
                lock.writeLock().unlock();
            }
        }

        // LIST OPERATIONS

        public int lpush(String key, String... values) {
            lock.writeLock().lock();

            try {
                List<String> list = create(
                    key,
                    RedisType.LIST,
                    new ArrayList<>()
                ).getValue();

                for (String value : values) {
                    list.add(0, value);
                }

                return list.size();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public int rpush(String key, String... values) {
            lock.writeLock().lock();

            try {
                List<String> list = create(
                    key,
                    RedisType.LIST,
                    new ArrayList<>()
                ).getValue();

                for (String value : values) {
                    list.add(value);
                }

                return list.size();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public Optional<String> lpop(String key) {
            lock.writeLock().lock();

            try {
                List<String> list = read(
                    key,
                    RedisType.LIST,
                    List.class
                );

                if (list == null || list.isEmpty()) {
                    return Optional.empty();
                }

                String value = list.remove(0);

                if (list.isEmpty()) database.remove(key);

                return Optional.of(value);
            } finally {
                lock.writeLock().unlock();
            }
        }

        public List<String> lrange(
            String key,
            int start,
            int stop
        ) {
            lock.readLock().lock();

            try {
                List<String> list = read(
                    key,
                    RedisType.LIST,
                    List.class
                );

                if (list == null) return List.of();

                int size = list.size();

                int from = start < 0
                    ? Math.max(0, size + start)
                    : start;

                int to = stop < 0
                    ? size + stop
                    : stop;

                if (from >= size || to < from) {
                    return List.of();
                }

                return List.copyOf(
                    list.subList(from, Math.min(size, to + 1))
                );
            } finally {
                lock.readLock().unlock();
            }
        }

        // SET OPERATIONS

        public int sadd(String key, String... members) {
            lock.writeLock().lock();

            try {
                Set<String> set = create(
                    key,
                    RedisType.SET,
                    new HashSet<>()
                ).getValue();

                int added = 0;

                for (String member : members) {
                    if (set.add(member)) added++;
                }

                return added;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public int srem(String key, String member) {
            lock.writeLock().lock();

            try {
                Set<String> set = read(
                    key,
                    RedisType.SET,
                    Set.class
                );

                if (set == null) return 0;

                int removed = set.remove(member) ? 1 : 0;

                if (set.isEmpty()) database.remove(key);

                return removed;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public Set<String> smembers(String key) {
            lock.readLock().lock();

            try {
                Set<String> set = read(
                    key,
                    RedisType.SET,
                    Set.class
                );

                return set == null
                    ? Set.of()
                    : Set.copyOf(set);
            } finally {
                lock.readLock().unlock();
            }
        }

        public Set<String> sinter(String first, String second) {
            Set<String> result = new HashSet<>(smembers(first));
            result.retainAll(smembers(second));
            return Set.copyOf(result);
        }

        public Set<String> sunion(String first, String second) {
            Set<String> result = new HashSet<>(smembers(first));
            result.addAll(smembers(second));
            return Set.copyOf(result);
        }

        // SORTED SET OPERATIONS

        public int zadd(
            String key,
            String member,
            double score
        ) {
            if (member == null || member.isBlank() ||
                !Double.isFinite(score)) {
                throw new ValidationException(
                    "Invalid sorted-set member or score."
                );
            }

            lock.writeLock().lock();

            try {
                Map<String, Double> sortedSet = create(
                    key,
                    RedisType.ZSET,
                    new HashMap<>()
                ).getValue();

                boolean added = !sortedSet.containsKey(member);
                sortedSet.put(member, score);

                return added ? 1 : 0;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public List<RankedMember> zrange(
            String key,
            int start,
            int stop
        ) {
            lock.readLock().lock();

            try {
                Map<String, Double> sortedSet = read(
                    key,
                    RedisType.ZSET,
                    Map.class
                );

                if (sortedSet == null) return List.of();

                List<RankedMember> ordered =
                    sortedSet.entrySet()
                        .stream()
                        .map(entry -> new RankedMember(
                            entry.getKey(),
                            entry.getValue()
                        ))
                        .sorted(
                            Comparator.comparingDouble(RankedMember::score)
                                .thenComparing(RankedMember::member)
                        )
                        .collect(Collectors.toList());

                int size = ordered.size();

                int from = start < 0
                    ? Math.max(0, size + start)
                    : start;

                int to = stop < 0
                    ? size + stop
                    : stop;

                if (from >= size || to < from) return List.of();

                return List.copyOf(
                    ordered.subList(from, Math.min(size, to + 1))
                );
            } finally {
                lock.readLock().unlock();
            }
        }

        // KEY MANAGEMENT

        public boolean expire(String key, Duration duration) {
            if (duration.isNegative() || duration.isZero()) {
                throw new ValidationException(
                    "Expiration must be positive."
                );
            }

            lock.writeLock().lock();

            try {
                CacheEntry<?> entry = find(key);

                if (entry == null) return false;

                long expiration = Math.addExact(
                    System.currentTimeMillis(),
                    duration.toMillis()
                );

                entry.setExpiresAtMillis(expiration);
                return true;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public long ttl(String key) {
            lock.writeLock().lock();

            try {
                CacheEntry<?> entry = find(key);

                if (entry == null) return -2;

                if (entry.getExpiresAtMillis() == null) return -1;

                return Math.max(
                    0,
                    (entry.getExpiresAtMillis() -
                        System.currentTimeMillis()) / 1000
                );
            } finally {
                lock.writeLock().unlock();
            }
        }

        public RedisType type(String key) {
            lock.writeLock().lock();

            try {
                CacheEntry<?> entry = find(key);

                return entry == null ? null : entry.getType();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public boolean exists(String key) {
            lock.writeLock().lock();

            try {
                return find(key) != null;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public int delete(String key) {
            lock.writeLock().lock();

            try {
                validateKey(key);
                purge(key);
                return database.remove(key) == null ? 0 : 1;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public int dbsize() {
            lock.writeLock().lock();

            try {
                List<String> keys = new ArrayList<>(database.keySet());
                keys.forEach(this::purge);
                return database.size();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // Transaction with snapshot rollback.
        //
        // This is a local demonstration, not Redis MULTI/EXEC or
        // distributed transaction semantics.

        public void transaction(Runnable operation) {
            lock.writeLock().lock();

            try {
                Map<String, CacheEntry<?>> snapshot = deepCopy();

                try {
                    operation.run();
                } catch (RuntimeException exception) {
                    database.clear();
                    database.putAll(snapshot);
                    throw exception;
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        private Map<String, CacheEntry<?>> deepCopy() {
            Map<String, CacheEntry<?>> copy = new HashMap<>();

            for (Map.Entry<String, CacheEntry<?>> item :
                 database.entrySet()) {

                CacheEntry<?> source = item.getValue();
                Object value = source.getValue();

                Object cloned;

                switch (source.getType()) {
                    case STRING ->
                        cloned = value;

                    case HASH ->
                        cloned = new LinkedHashMap<>(
                            (Map<String, String>) value
                        );

                    case LIST ->
                        cloned = new ArrayList<>(
                            (List<String>) value
                        );

                    case SET ->
                        cloned = new HashSet<>(
                            (Set<String>) value
                        );

                    case ZSET ->
                        cloned = new HashMap<>(
                            (Map<String, Double>) value
                        );

                    default ->
                        throw new IllegalStateException("Unknown type.");
                }

                CacheEntry<Object> entry = new CacheEntry<>(
                    source.getType(),
                    cloned
                );

                entry.setExpiresAtMillis(source.getExpiresAtMillis());
                copy.put(item.getKey(), entry);
            }

            return copy;
        }
    }

    // Enterprise-facing cache service.

    static class CacheService {

        private final RedisStore store;

        CacheService(RedisStore store) {
            this.store = store;
        }

        public void cacheUser(
            String userId,
            String name,
            String department
        ) {
            if (userId == null || userId.isBlank()) {
                throw new ValidationException("Invalid user ID.");
            }

            store.transaction(() -> {
                store.hset("user:" + userId, "name", name);
                store.hset(
                    "user:" + userId,
                    "department",
                    department
                );
            });
        }

        public Map<String, String> getUser(String userId) {
            return store.hgetall("user:" + userId);
        }

        public void cacheSession(
            String sessionId,
            Duration duration
        ) {
            if (sessionId == null || sessionId.isBlank()) {
                throw new ValidationException("Invalid session ID.");
            }

            store.set("session:" + sessionId, "authenticated");
            store.expire("session:" + sessionId, duration);
        }
    }

    private static void runTests(RedisStore store) {
        store.set("test:counter", "10");

        if (store.incrBy("test:counter", 5) != 15) {
            throw new AssertionError("String test failed.");
        }

        store.hset("test:user", "name", "Atul");

        if (!store.hget("test:user", "name").orElse("").equals("Atul")) {
            throw new AssertionError("Hash test failed.");
        }

        store.rpush("test:list", "A", "B");
        store.lpush("test:list", "C");

        if (!store.lrange("test:list", 0, -1)
            .equals(List.of("C", "A", "B"))) {
            throw new AssertionError("List test failed.");
        }

        store.sadd("test:A", "x", "y");
        store.sadd("test:B", "y", "z");

        if (!store.sinter("test:A", "test:B").equals(Set.of("y"))) {
            throw new AssertionError("Set test failed.");
        }

        store.zadd("test:zset", "Alice", 10);
        store.zadd("test:zset", "Bob", 20);

        if (!store.zrange("test:zset", 0, -1)
            .get(0).member().equals("Alice")) {
            throw new AssertionError("Sorted-set test failed.");
        }

        store.set("test:rollback", "original");

        try {
            store.transaction(() -> {
                store.set("test:rollback", "changed");
                throw new RedisException("Failure");
            });
        } catch (RedisException expected) {
            // The transaction restores its snapshot.
        }

        if (!store.get("test:rollback").value().equals("original")) {
            throw new AssertionError("Rollback test failed.");
        }

        boolean detected = false;

        try {
            store.hgetall("test:counter");
        } catch (WrongTypeException expected) {
            detected = true;
        }

        if (!detected) {
            throw new AssertionError("Type safety test failed.");
        }

        System.out.println("\nAll Java 17 tests passed.");
    }

    public static void main(String[] args) {
        RedisStore store = new RedisStore();
        CacheService service = new CacheService(store);

        System.out.println("\n=== STRING OPERATIONS ===");

        store.set("counter", "100");
        System.out.println("Counter: " + store.incrBy("counter", 25));

        System.out.println("\n=== HASH OPERATIONS ===");

        service.cacheUser("1001", "Atul", "Engineering");
        System.out.println("User: " + service.getUser("1001"));

        System.out.println("\n=== LIST OPERATIONS ===");

        store.rpush("jobs", "build", "test", "deploy");
        store.lpush("jobs", "validate");

        System.out.println("Jobs: " + store.lrange("jobs", 0, -1));
        System.out.println("Processed: " + store.lpop("jobs"));

        System.out.println("\n=== SET OPERATIONS ===");

        store.sadd("team:backend", "Python", "Java", "C++");
        store.sadd("team:cloud", "Java", "Go", "Python");

        System.out.println(
            "Common technologies: " +
            store.sinter("team:backend", "team:cloud")
        );

        System.out.println(
            "Combined technologies: " +
            store.sunion("team:backend", "team:cloud")
        );

        System.out.println("\n=== SORTED SET OPERATIONS ===");

        store.zadd("leaderboard", "Alice", 950);
        store.zadd("leaderboard", "Bob", 850);
        store.zadd("leaderboard", "Charlie", 900);

        store.zrange("leaderboard", 0, -1)
            .forEach(System.out::println);

        System.out.println("\n=== EXPIRATION ===");

        service.cacheSession("session-1001", Duration.ofMinutes(5));

        System.out.println(
            "Session TTL: " + store.ttl("session:session-1001")
        );

        System.out.println("\n=== KEY INFORMATION ===");

        System.out.println("User type: " + store.type("user:1001"));
        System.out.println("Database size: " + store.dbsize());

        runTests(store);
    }
}
