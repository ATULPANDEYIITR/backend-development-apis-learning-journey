import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Supplier;

/**
 * Enterprise Redis Caching and Consistency Management.
 *
 * Java 17 implementation featuring:
 * - Cache-aside
 * - Write-through
 * - TTL expiration
 * - Version-aware cache entries
 * - Cache invalidation
 * - Concurrent request deduplication
 * - Repository abstraction
 * - Policy-driven caching
 * - Metrics and failure handling
 *
 * Compile:
 *   javac RedisCaching.java
 *
 * Run:
 *   java RedisCaching
 *
 * Uses an in-memory adapter to provide an executable demonstration.
 */

public class RedisCaching {

    enum Strategy {
        CACHE_ASIDE,
        WRITE_THROUGH
    }

    enum CacheState {
        HIT,
        MISS,
        EXPIRED
    }

    static class CacheException extends RuntimeException {
        CacheException(String message) {
            super(message);
        }
    }

    static class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    record Product(
        long id,
        String name,
        double price,
        long version
    ) {
        Product {
            if (id <= 0) {
                throw new ValidationException("Invalid product ID.");
            }

            if (name == null || name.isBlank()) {
                throw new ValidationException("Product name is required.");
            }

            if (!Double.isFinite(price) || price < 0) {
                throw new ValidationException("Invalid product price.");
            }

            if (version <= 0) {
                throw new ValidationException("Invalid product version.");
            }
        }
    }

    record CacheEntry<T>(
        T value,
        long createdAt,
        long expiresAt,
        long version
    ) {
        boolean isExpired(long now) {
            return now >= expiresAt;
        }
    }

    record CacheSnapshot(
        long hits,
        long misses,
        long writes,
        long invalidations,
        long expirations,
        long originReads,
        long failures,
        double hitRate
    ) {}

    record CachePolicy(
        Duration ttl,
        boolean enabled,
        boolean cacheNegativeResults
    ) {
        CachePolicy {
            Objects.requireNonNull(ttl);

            if (ttl.isZero() || ttl.isNegative()) {
                throw new ValidationException("TTL must be positive.");
            }
        }

        static CachePolicy standard() {
            return new CachePolicy(
                Duration.ofSeconds(30),
                true,
                false
            );
        }
    }

    interface Repository<T, ID> {
        Optional<T> findById(ID id);
        T save(ID id, T value);
        boolean delete(ID id);
    }

    interface CacheAdapter<K, V> {
        Optional<V> get(K key);
        void put(K key, V value, Duration ttl);
        boolean invalidate(K key);
        void setAvailable(boolean available);
    }

    static final class ProductRepository
        implements Repository<Product, Long> {

        private final Map<Long, Product> records =
            new ConcurrentHashMap<>();

        private final AtomicLong reads = new AtomicLong();

        @Override
        public Optional<Product> findById(Long id) {
            reads.incrementAndGet();
            return Optional.ofNullable(records.get(id));
        }

        @Override
        public Product save(Long id, Product product) {
            records.put(id, product);
            return product;
        }

        @Override
        public boolean delete(Long id) {
            return records.remove(id) != null;
        }

        long readCount() {
            return reads.get();
        }
    }

    static final class InMemoryRedis
        implements CacheAdapter<String, Product> {

        private final Map<String, CacheEntry<Product>> entries =
            new ConcurrentHashMap<>();

        private final AtomicLong hits = new AtomicLong();
        private final AtomicLong misses = new AtomicLong();
        private final AtomicLong writes = new AtomicLong();
        private final AtomicLong invalidations = new AtomicLong();
        private final AtomicLong expirations = new AtomicLong();
        private final AtomicLong originReads = new AtomicLong();
        private final AtomicLong failures = new AtomicLong();

        private volatile boolean available = true;

        private void assertAvailable() {
            if (!available) {
                failures.incrementAndGet();
                throw new CacheException("Redis is unavailable.");
            }
        }

        private static void validateKey(String key) {
            if (
                key == null ||
                key.isBlank() ||
                key.length() > 512 ||
                key.chars().anyMatch(Character::isISOControl)
            ) {
                throw new ValidationException("Invalid cache key.");
            }
        }

        @Override
        public Optional<Product> get(String key) {
            validateKey(key);
            assertAvailable();

            CacheEntry<Product> entry = entries.get(key);

            if (entry == null) {
                misses.incrementAndGet();
                return Optional.empty();
            }

            if (entry.isExpired(System.nanoTime())) {
                entries.remove(key, entry);

                expirations.incrementAndGet();
                misses.incrementAndGet();

                return Optional.empty();
            }

            hits.incrementAndGet();

            return Optional.of(entry.value());
        }

        @Override
        public void put(
            String key,
            Product product,
            Duration ttl
        ) {
            validateKey(key);
            assertAvailable();

            if (ttl.isNegative() || ttl.isZero()) {
                throw new ValidationException("TTL must be positive.");
            }

            long now = System.nanoTime();
            long duration = ttl.toNanos();

            if (duration > Long.MAX_VALUE - now) {
                throw new ValidationException("TTL is too large.");
            }

            CacheEntry<Product> entry = new CacheEntry<>(
                product,
                now,
                now + duration,
                product.version()
            );

            entries.compute(key, (existingKey, existing) -> {
                if (
                    existing != null &&
                    existing.version() > product.version()
                ) {
                    return existing;
                }

                return entry;
            });

            writes.incrementAndGet();
        }

        @Override
        public boolean invalidate(String key) {
            validateKey(key);
            assertAvailable();

            boolean removed = entries.remove(key) != null;

            if (removed) {
                invalidations.incrementAndGet();
            }

            return removed;
        }

        @Override
        public void setAvailable(boolean value) {
            available = value;
        }

        void recordOriginRead() {
            originReads.incrementAndGet();
        }

        int cleanupExpired() {
            assertAvailable();

            long now = System.nanoTime();
            int removed = 0;

            for (Map.Entry<String, CacheEntry<Product>> item :
                entries.entrySet()) {

                CacheEntry<Product> entry = item.getValue();

                if (
                    entry.isExpired(now) &&
                    entries.remove(item.getKey(), entry)
                ) {
                    removed++;
                }
            }

            expirations.addAndGet(removed);

            return removed;
        }

        CacheSnapshot snapshot() {
            long hitCount = hits.get();
            long missCount = misses.get();
            long total = hitCount + missCount;

            return new CacheSnapshot(
                hitCount,
                missCount,
                writes.get(),
                invalidations.get(),
                expirations.get(),
                originReads.get(),
                failures.get(),
                total == 0 ? 0.0 : (double) hitCount / total
            );
        }
    }

    static final class CacheService {

        private final ProductRepository repository;
        private final InMemoryRedis cache;
        private final CachePolicy policy;

        private final Map<String, ReentrantLock> locks =
            new ConcurrentHashMap<>();

        CacheService(
            ProductRepository repository,
            InMemoryRedis cache,
            CachePolicy policy
        ) {
            this.repository = repository;
            this.cache = cache;
            this.policy = policy;
        }

        private String key(long id) {
            if (id <= 0) {
                throw new ValidationException("Invalid product ID.");
            }

            return "products:" + id;
        }

        private Optional<Product> readOrigin(long id) {
            cache.recordOriginRead();
            return repository.findById(id);
        }

        Optional<Product> getProduct(long id) {
            String key = key(id);

            if (!policy.enabled()) {
                return readOrigin(id);
            }

            try {
                Optional<Product> cached = cache.get(key);

                if (cached.isPresent()) {
                    return cached;
                }

            } catch (CacheException exception) {
                System.err.println(
                    "Cache read failure: " + exception.getMessage()
                );

                return readOrigin(id);
            }

            ReentrantLock lock = locks.computeIfAbsent(
                key,
                ignored -> new ReentrantLock()
            );

            lock.lock();

            try {
                Optional<Product> secondCheck;

                try {
                    secondCheck = cache.get(key);
                } catch (CacheException exception) {
                    return readOrigin(id);
                }

                if (secondCheck.isPresent()) {
                    return secondCheck;
                }

                Optional<Product> product = readOrigin(id);

                if (product.isPresent()) {
                    try {
                        cache.put(
                            key,
                            product.get(),
                            policy.ttl()
                        );
                    } catch (CacheException exception) {
                        System.err.println(
                            "Cache population failed: "
                            + exception.getMessage()
                        );
                    }
                }

                return product;

            } finally {
                lock.unlock();
            }
        }

        Product updateProduct(
            long id,
            String name,
            double price,
            Strategy strategy
        ) {
            Objects.requireNonNull(strategy);

            Product current = repository.findById(id)
                .orElseThrow(() ->
                    new ValidationException("Product not found.")
                );

            Product updated = new Product(
                id,
                name,
                price,
                current.version() + 1
            );

            // The source database is updated before cache publication.
            repository.save(id, updated);

            String key = key(id);

            if (strategy == Strategy.WRITE_THROUGH) {
                try {
                    cache.put(key, updated, policy.ttl());
                } catch (CacheException exception) {
                    System.err.println(
                        "Write-through failed. Attempting invalidation."
                    );

                    try {
                        cache.invalidate(key);
                    } catch (CacheException invalidationError) {
                        System.err.println(
                            "Invalidation also failed."
                        );
                    }
                }
            }

            if (strategy == Strategy.CACHE_ASIDE) {
                try {
                    cache.invalidate(key);
                } catch (CacheException exception) {
                    System.err.println(
                        "Invalidation failed. TTL is the recovery boundary."
                    );
                }
            }

            return updated;
        }

        boolean deleteProduct(long id) {
            boolean deleted = repository.delete(id);

            if (deleted) {
                try {
                    cache.invalidate(key(id));
                } catch (CacheException exception) {
                    System.err.println(
                        "Cache deletion failed: " + exception.getMessage()
                    );
                }
            }

            return deleted;
        }
    }

    static void demonstrate() {
        ProductRepository repository = new ProductRepository();
        InMemoryRedis redis = new InMemoryRedis();

        CachePolicy policy = CachePolicy.standard();

        CacheService service = new CacheService(
            repository,
            redis,
            policy
        );

        repository.save(
            101L,
            new Product(101, "Enterprise Database", 120000, 1)
        );

        System.out.println("\nREDIS CACHING ENTERPRISE MODEL");
        System.out.println("========================================");

        System.out.println("\n1. Cache-aside initial request");
        System.out.println(service.getProduct(101));

        System.out.println("\n2. Cache hit");
        System.out.println(service.getProduct(101));

        System.out.println("\n3. Write-through update");

        System.out.println(service.updateProduct(
            101,
            "Enterprise Database Pro",
            145000,
            Strategy.WRITE_THROUGH
        ));

        System.out.println("\n4. Read after write-through");
        System.out.println(service.getProduct(101));

        System.out.println("\n5. Cache-aside invalidation");

        System.out.println(service.updateProduct(
            101,
            "Enterprise Database Premium",
            165000,
            Strategy.CACHE_ASIDE
        ));

        System.out.println(service.getProduct(101));

        System.out.println("\n6. Cache outage and fallback");

        redis.setAvailable(false);

        System.out.println(service.getProduct(101));

        redis.setAvailable(true);

        System.out.println("\n7. Expiration");

        redis.put(
            "temporary:session",
            new Product(500, "Temporary", 100, 1),
            Duration.ofMillis(100)
        );

        try {
            Thread.sleep(150);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new CacheException("Expiration wait interrupted.");
        }

        System.out.println(redis.get("temporary:session"));

        System.out.println("\n8. Expired-entry cleanup");
        System.out.println(redis.cleanupExpired());

        System.out.println("\n9. Source deletion");
        System.out.println(service.deleteProduct(101));

        System.out.println("\n10. Metrics");
        System.out.println(redis.snapshot());

        if (redis.snapshot().hits() < 1) {
            throw new IllegalStateException("Cache hit assertion failed.");
        }

        if (redis.snapshot().misses() < 1) {
            throw new IllegalStateException("Cache miss assertion failed.");
        }

        if (repository.findById(101L).isPresent()) {
            throw new IllegalStateException("Deletion assertion failed.");
        }

        System.out.println("\nAll enterprise validation checks passed.");
    }

    public static void main(String[] args) {
        try {
            demonstrate();
        } catch (RuntimeException exception) {
            System.err.println(
                "Application error: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
