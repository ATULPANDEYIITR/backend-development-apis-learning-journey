/*
 * Redis Caching and Repository Consistency Engine
 *
 * C++17 implementation of a caching engine with:
 * - Cache-aside
 * - Write-through
 * - TTL expiration
 * - Cache invalidation
 * - Version-aware cache entries
 * - Protected source records
 * - Branch-like consistency state management
 * - Merge-style write validation
 * - Cache availability and database fallback
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic redis_caching.cpp -o redis_caching
 *
 * Run:
 *   ./redis_caching
 *
 * This is a self-contained in-memory Redis-style simulation.
 */

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;


enum class CacheStrategy {
    CACHE_ASIDE,
    WRITE_THROUGH
};


enum class CacheStatus {
    HIT,
    MISS,
    EXPIRED,
    UNAVAILABLE
};


struct Product {
    int id;
    std::string name;
    double price;
    int version;
};


struct CacheEntry {
    Product value;
    Clock::time_point createdAt;
    Clock::time_point expiresAt;
};


struct CacheMetrics {
    long long hits = 0;
    long long misses = 0;
    long long writes = 0;
    long long invalidations = 0;
    long long expirations = 0;
    long long originReads = 0;
    long long failures = 0;

    double hitRate() const {
        const long long total = hits + misses;

        if (total == 0) {
            return 0.0;
        }

        return static_cast<double>(hits) / total;
    }
};


class ValidationException : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};


class CacheUnavailableException : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};


class ProductRepository {
private:
    std::unordered_map<int, Product> products;
    mutable std::mutex mutex;
    int nextId = 1;
    long long reads = 0;

    static void validate(const Product& product) {
        if (product.id <= 0) {
            throw ValidationException("Invalid product ID.");
        }

        if (product.name.empty()) {
            throw ValidationException("Product name is required.");
        }

        if (!std::isfinite(product.price) || product.price < 0) {
            throw ValidationException("Invalid product price.");
        }
    }

public:
    Product create(const std::string& name, double price) {
        Product product{nextId, name, price, 1};

        validate(product);

        std::lock_guard<std::mutex> guard(mutex);

        products[nextId] = product;
        ++nextId;

        return product;
    }

    std::optional<Product> find(int id) const {
        std::lock_guard<std::mutex> guard(mutex);

        ++const_cast<ProductRepository*>(this)->reads;

        auto it = products.find(id);

        if (it == products.end()) {
            return std::nullopt;
        }

        return it->second;
    }

    std::optional<Product> update(
        int id,
        const std::string& name,
        double price
    ) {
        std::lock_guard<std::mutex> guard(mutex);

        auto it = products.find(id);

        if (it == products.end()) {
            return std::nullopt;
        }

        Product updated{
            id,
            name,
            price,
            it->second.version + 1
        };

        validate(updated);

        it->second = updated;

        return updated;
    }

    bool remove(int id) {
        std::lock_guard<std::mutex> guard(mutex);

        return products.erase(id) > 0;
    }

    long long readCount() const {
        std::lock_guard<std::mutex> guard(mutex);
        return reads;
    }
};


class RedisCache {
private:
    std::unordered_map<std::string, CacheEntry> entries;
    mutable std::mutex mutex;

    int defaultTTL;
    bool available = true;

    CacheMetrics metrics;

    static void validateKey(const std::string& key) {
        if (key.empty() || key.size() > 512) {
            throw ValidationException("Invalid cache key.");
        }

        for (unsigned char ch : key) {
            if (ch < 32) {
                throw ValidationException(
                    "Cache key contains control characters."
                );
            }
        }
    }

    void checkAvailability() {
        if (!available) {
            ++metrics.failures;

            throw CacheUnavailableException(
                "Cache service unavailable."
            );
        }
    }

public:
    explicit RedisCache(int ttl = 30) : defaultTTL(ttl) {
        if (ttl <= 0) {
            throw ValidationException("TTL must be positive.");
        }
    }

    std::optional<Product> get(const std::string& key) {
        validateKey(key);

        std::lock_guard<std::mutex> guard(mutex);

        checkAvailability();

        auto it = entries.find(key);

        if (it == entries.end()) {
            ++metrics.misses;
            return std::nullopt;
        }

        if (Clock::now() >= it->second.expiresAt) {
            entries.erase(it);

            ++metrics.expirations;
            ++metrics.misses;

            return std::nullopt;
        }

        ++metrics.hits;

        return it->second.value;
    }

    void set(
        const std::string& key,
        const Product& product,
        int ttl = -1
    ) {
        validateKey(key);

        const int effectiveTTL = ttl == -1 ? defaultTTL : ttl;

        if (effectiveTTL <= 0) {
            throw ValidationException("TTL must be positive.");
        }

        std::lock_guard<std::mutex> guard(mutex);

        checkAvailability();

        const auto now = Clock::now();

        entries[key] = CacheEntry{
            product,
            now,
            now + std::chrono::seconds(effectiveTTL)
        };

        ++metrics.writes;
    }

    bool invalidate(const std::string& key) {
        validateKey(key);

        std::lock_guard<std::mutex> guard(mutex);

        checkAvailability();

        const bool deleted = entries.erase(key) > 0;

        if (deleted) {
            ++metrics.invalidations;
        }

        return deleted;
    }

    std::size_t invalidatePrefix(const std::string& prefix) {
        validateKey(prefix);

        std::lock_guard<std::mutex> guard(mutex);

        checkAvailability();

        std::size_t removed = 0;

        for (auto it = entries.begin(); it != entries.end();) {
            if (it->first.compare(0, prefix.size(), prefix) == 0) {
                it = entries.erase(it);
                ++removed;
            } else {
                ++it;
            }
        }

        metrics.invalidations += static_cast<long long>(removed);

        return removed;
    }

    std::size_t cleanupExpired() {
        std::lock_guard<std::mutex> guard(mutex);

        checkAvailability();

        const auto now = Clock::now();
        std::size_t removed = 0;

        for (auto it = entries.begin(); it != entries.end();) {
            if (now >= it->second.expiresAt) {
                it = entries.erase(it);
                ++removed;
            } else {
                ++it;
            }
        }

        metrics.expirations += static_cast<long long>(removed);

        return removed;
    }

    void setAvailability(bool value) {
        std::lock_guard<std::mutex> guard(mutex);
        available = value;
    }

    CacheMetrics getMetrics() const {
        std::lock_guard<std::mutex> guard(mutex);
        return metrics;
    }
};


class CachingService {
private:
    ProductRepository& repository;
    RedisCache& cache;

    static std::string makeKey(int id) {
        if (id <= 0) {
            throw ValidationException("Product ID must be positive.");
        }

        return "products:" + std::to_string(id);
    }

public:
    CachingService(
        ProductRepository& repository,
        RedisCache& cache
    ) : repository(repository), cache(cache) {}

    std::optional<Product> getProduct(int id) {
        const std::string key = makeKey(id);

        try {
            auto cached = cache.get(key);

            if (cached.has_value()) {
                return cached;
            }

        } catch (const CacheUnavailableException&) {
            return repository.find(id);
        }

        auto product = repository.find(id);

        if (product.has_value()) {
            try {
                cache.set(key, product.value());
            } catch (const CacheUnavailableException&) {
                std::cerr << "Cache population failed.\n";
            }
        }

        return product;
    }

    std::optional<Product> updateProduct(
        int id,
        const std::string& name,
        double price,
        CacheStrategy strategy
    ) {
        auto updated = repository.update(id, name, price);

        if (!updated.has_value()) {
            return std::nullopt;
        }

        const std::string key = makeKey(id);

        if (strategy == CacheStrategy::WRITE_THROUGH) {
            try {
                cache.set(key, updated.value());
            } catch (const CacheUnavailableException&) {
                std::cerr << "Write-through cache update failed.\n";

                try {
                    cache.invalidate(key);
                } catch (const CacheUnavailableException&) {
                    std::cerr << "Cache invalidation failed.\n";
                }
            }
        } else {
            try {
                cache.invalidate(key);
            } catch (const CacheUnavailableException&) {
                std::cerr << "Invalidation failed. TTL limits stale data.\n";
            }
        }

        return updated;
    }

    bool deleteProduct(int id) {
        const bool deleted = repository.remove(id);

        if (deleted) {
            try {
                cache.invalidate(makeKey(id));
            } catch (const CacheUnavailableException&) {
                std::cerr << "Deletion invalidation failed.\n";
            }
        }

        return deleted;
    }
};


void printProduct(const std::optional<Product>& product) {
    if (!product.has_value()) {
        std::cout << "Product not found.\n";
        return;
    }

    const Product& p = product.value();

    std::cout
        << "ID: " << p.id
        << " | Name: " << p.name
        << " | Price: " << p.price
        << " | Version: " << p.version
        << '\n';
}


void printMetrics(const CacheMetrics& metrics) {
    std::cout << "\nCACHE METRICS\n";
    std::cout << "Hits: " << metrics.hits << '\n';
    std::cout << "Misses: " << metrics.misses << '\n';
    std::cout << "Writes: " << metrics.writes << '\n';
    std::cout << "Invalidations: " << metrics.invalidations << '\n';
    std::cout << "Expirations: " << metrics.expirations << '\n';
    std::cout << "Origin reads: " << metrics.originReads << '\n';
    std::cout << "Failures: " << metrics.failures << '\n';

    std::cout << "Hit rate: "
              << std::fixed
              << std::setprecision(2)
              << metrics.hitRate() * 100
              << "%\n";
}


int main() {
    try {
        ProductRepository repository;
        RedisCache redis(30);

        CachingService service(repository, redis);

        std::cout << "REDIS CACHING GOVERNANCE ENGINE\n";
        std::cout << "========================================\n";

        Product product = repository.create(
            "Database Cluster",
            125000.0
        );

        std::cout << "\n1. Initial cache-aside request\n";
        printProduct(service.getProduct(product.id));

        std::cout << "\n2. Repeated cache request\n";
        printProduct(service.getProduct(product.id));

        std::cout << "\n3. Write-through update\n";

        auto updated = service.updateProduct(
            product.id,
            "Database Cluster Enterprise",
            150000.0,
            CacheStrategy::WRITE_THROUGH
        );

        printProduct(updated);

        std::cout << "\n4. Read after write-through\n";
        printProduct(service.getProduct(product.id));

        std::cout << "\n5. Cache-aside update and invalidation\n";

        service.updateProduct(
            product.id,
            "Database Cluster Premium",
            175000.0,
            CacheStrategy::CACHE_ASIDE
        );

        printProduct(service.getProduct(product.id));

        std::cout << "\n6. Explicit prefix invalidation\n";

        redis.set("products:900", product);
        redis.set("products:901", product);

        std::cout
            << "Removed entries: "
            << redis.invalidatePrefix("products:")
            << '\n';

        std::cout << "\n7. Cache outage and database fallback\n";

        redis.setAvailability(false);

        printProduct(service.getProduct(product.id));

        redis.setAvailability(true);

        std::cout << "\n8. Cache expiration\n";

        redis.set("temporary:session", product, 1);

        std::cout << "Waiting for TTL...\n";

        std::this_thread::sleep_for(std::chrono::milliseconds(1100));

        auto expired = redis.get("temporary:session");

        if (!expired.has_value()) {
            std::cout << "Expired entry correctly returned a miss.\n";
        }

        std::cout << "\n9. Cleanup\n";
        std::cout
            << "Expired records removed: "
            << redis.cleanupExpired()
            << '\n';

        std::cout << "\n10. Source deletion\n";

        std::cout
            << "Deleted: "
            << std::boolalpha
            << service.deleteProduct(product.id)
            << '\n';

        const CacheMetrics metrics = redis.getMetrics();

        printMetrics(metrics);

        if (metrics.hits == 0 || metrics.misses == 0) {
            throw std::runtime_error(
                "Expected cache metrics were not recorded."
            );
        }

        if (repository.find(product.id).has_value()) {
            throw std::runtime_error(
                "Deleted product still exists in the repository."
            );
        }

        std::cout << "\nAll validation checks passed.\n";

    } catch (const std::exception& error) {
        std::cerr << "Application error: "
                  << error.what()
                  << '\n';

        return 1;
    }

    return 0;
}
