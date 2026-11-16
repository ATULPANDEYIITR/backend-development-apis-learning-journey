# Redis Caching: Cache-Aside, Write-Through, TTL and Cache Invalidation

## 1. Project Overview

This project implements and compares four essential Redis caching mechanisms:

- Cache-aside
- Write-through
- Time-to-live (TTL)
- Cache invalidation

The implementations demonstrate how caching reduces repeated database reads, manages frequently accessed information, and handles consistency between an authoritative database and a faster cache layer.

The project uses a product-management scenario involving enterprise infrastructure products. The database stores authoritative product records, while the cache maintains temporary copies for faster retrieval.

The five source implementations use different engineering approaches:

| File | Engineering perspective |
|---|---|
| Python | Repository simulation and cache workflow management |
| JavaScript | Asynchronous, event-driven caching |
| C++17 | Efficient cache-state and consistency engine |
| Java 17 | Enterprise-oriented caching architecture |
| PostgreSQL | Relational cache model, auditing and transactional consistency |

The Python, JavaScript, C++17 and Java implementations use in-memory cache adapters. They demonstrate Redis-style behavior without requiring an external Redis installation. The PostgreSQL implementation models the associated caching workflow using relational structures.

## 2. Redis Caching Architecture

Redis is an in-memory data store commonly used as a caching layer between an application and its primary database.

A typical architecture is:

Application → Redis Cache → Database

The application checks Redis before accessing the database. When a suitable cached value exists, the application returns it without performing another database query.

When the requested value is absent or expired, the application retrieves the authoritative record and may populate the cache.

### Responsibilities of each layer

| Component | Responsibility |
|---|---|
| Application | Executes business operations and cache policies |
| Redis | Stores temporary, frequently accessed data |
| Database | Maintains authoritative records |
| TTL mechanism | Limits cache-entry lifetime |
| Invalidation mechanism | Removes outdated cache entries |
| Monitoring | Measures cache effectiveness and failures |

An important distinction is that the cache and database do not automatically share a transaction. Applications must explicitly manage consistency between them.

## 3. Cache-Aside

### Concept

Cache-aside is an application-managed caching strategy.

The application checks the cache before querying the database.

Its workflow is:

Application → Cache lookup

- Cache hit: Return cached data.
- Cache miss: Retrieve data from the database.
- Populate cache: Store the retrieved record.
- Return result: Send the record to the application.

### Workflow

    Request
       |
       v
    Cache lookup
       |
       +------ Cache hit ------> Return cached data
       |
       +------ Cache miss
                    |
                    v
               Database query
                    |
                    v
               Populate cache
                    |
                    v
                Return data

### Example

An enterprise application receives repeated requests for product 101.

The first request:

1. Redis does not contain the product.
2. The application queries PostgreSQL.
3. PostgreSQL returns the product.
4. The application stores the result in Redis.
5. The application returns the product.

The second request:

1. The application checks Redis.
2. Redis returns the cached product.
3. The database is not queried.

### Characteristics

- The application controls cache population.
- Only requested records normally enter the cache.
- Unused database records do not need to occupy cache memory.
- Cache misses require database access.
- Cache invalidation must be handled when source data changes.

### Implementation

The Python `CacheService.get_product()` method implements cache-aside using a second cache lookup inside a per-key lock.

The JavaScript implementation uses an `inFlight` map to coordinate concurrent requests.

The C++ implementation performs cache lookup followed by repository retrieval.

The Java implementation separates repository access from cache operations through interfaces.

The PostgreSQL `get_product_cached()` function demonstrates the equivalent relational workflow.

## 4. Write-Through Caching

### Concept

Write-through caching updates the authoritative database and cache as part of the same application-level write workflow.

The application first updates the database and then publishes the updated value into the cache.

### Workflow

    Update request
          |
          v
    Validate input
          |
          v
    Update database
          |
          v
    Update cache
          |
          v
    Return result

The purpose is to ensure that subsequent cache reads can obtain the newly updated record without requiring another database lookup.

### Example

An administrator changes an enterprise laptop price from ₹85,000 to ₹99,000.

The application:

1. Validates the new price.
2. Updates the database.
3. Increments the record version.
4. Updates the corresponding cache entry.
5. Returns the updated product.

### Characteristics

- Cache population occurs during writes.
- Frequently accessed records can remain immediately available.
- Write operations require additional cache work.
- Cache failures require explicit recovery handling.
- Database and Redis updates are not inherently atomic.

**Important consistency distinction:** A database transaction cannot normally guarantee atomic updates across PostgreSQL and an independent Redis server. A production system needs a deliberate recovery mechanism, such as transactional outbox processing, retries, idempotency, or version-aware invalidation.

The PostgreSQL implementation demonstrates transactional source modification and relational cache publication within one PostgreSQL database. It does not establish a distributed transaction with Redis.

## 5. Cache-Aside versus Write-Through

| Characteristic | Cache-aside | Write-through |
|---|---|---|
| Cache population | On cache miss | During write |
| Database read | Required on initial miss | Depends on subsequent access |
| Write operation | Updates database and invalidates cache | Updates database and cache |
| Cache consistency | Depends on invalidation and TTL | Depends on successful cache publication |
| Initial cache state | Usually empty | Can be populated during writes |
| Unused records | Generally not cached | May occupy cache |
| Primary advantage | Avoids caching unnecessary records | Keeps frequently used records updated |
| Main concern | Cache misses and stale values | Write latency and distributed failures |

These strategies are not mutually exclusive in every architecture. Applications can use different strategies for different data categories.

## 6. Time-to-Live (TTL)

### Concept

TTL defines how long a cache entry remains valid.

Redis supports expiration using commands such as:

- `SET key value EX seconds`
- `EXPIRE key seconds`
- `TTL key`

An entry with a TTL of 60 seconds becomes logically expired after that period.

### Example

    Key: products:101
    Value: Enterprise Laptop
    TTL: 60 seconds

    Creation time: 10:00:00
    Expiration:    10:01:00

After expiration, the application must retrieve the current source record when another request arrives.

### Why TTL matters

TTL helps manage:

- Stale information
- Cache memory consumption
- Session expiration
- Temporary data
- Periodic refresh requirements
- Recovery after missed invalidation events

### TTL implementation decisions

The implementations use monotonic clocks for in-memory expiration wherever supported.

A monotonic clock measures elapsed time without being affected by system-clock corrections.

The PostgreSQL implementation uses `TIMESTAMPTZ` and database time for expiration comparisons.

### TTL limitations

TTL does not guarantee that data remains current until expiration.

For example, a product price may change immediately after a cache entry is created. The entry can remain stale until invalidation or expiration.

TTL is therefore a recovery boundary, not a complete consistency mechanism.

## 7. Cache Invalidation

### Concept

Cache invalidation removes or replaces cached data when the authoritative source changes.

The purpose is to prevent subsequent requests from returning outdated information.

### Workflow

    Database update
          |
          v
    Detect source change
          |
          v
    Identify affected keys
          |
          v
    Delete or refresh cache
          |
          v
    Next request retrieves current data

### Example

The database contains:

| Product | Price | Version |
|---|---:|---:|
| Enterprise Laptop | ₹85,000 | 1 |

The cache also contains version 1.

An administrator updates the price to ₹99,000.

The database now contains version 2.

The application invalidates `products:101`.

The next request retrieves version 2 from the database and repopulates the cache.

### Invalidation approaches

| Approach | Mechanism | Application |
|---|---|---|
| Explicit invalidation | Delete a specific key | Product updates |
| Pattern-based invalidation | Delete related keys | Product-category changes |
| TTL expiration | Allow an entry to expire | Temporary information |
| Event-driven invalidation | Publish an invalidation event | Distributed applications |
| Version-based validation | Compare source and cached versions | Concurrent updates |

### Invalidation challenges

Invalidation becomes difficult when:

- Multiple application instances share Redis.
- One database record appears in several cache keys.
- An update fails after the database commits.
- An invalidation event is lost.
- Concurrent requests repopulate stale data.
- A cache outage prevents deletion.

A production system should consider durable invalidation events, retry processing, version checks and idempotent operations.

## 8. Cache Stampede and Concurrent Requests

A cache stampede occurs when many requests simultaneously encounter an expired or missing cache entry.

Each request may query the database independently.

For example, 1,000 concurrent requests for one expired product could generate 1,000 database queries.

### Prevention mechanisms

**Request coalescing**

Requests for the same missing key share one database-loading operation.

The JavaScript implementation uses a `Map` named `inFlight`.

**Per-key locking**

The Python implementation uses individual locks for cache keys.

The Java implementation uses `ConcurrentHashMap` and `ReentrantLock`.

**Expiration jitter**

A small random variation in TTL can distribute expiration times and reduce synchronized cache misses.

**Preloading**

Frequently accessed records can be loaded before predictable traffic peaks.

**Stale-while-revalidate**

Applications can temporarily serve an older value while refreshing it in the background when the business consistency requirements permit this behavior.

The C++ implementation focuses on cache-state management and version consistency rather than distributed request coordination.

## 9. Cache Consistency and Version Management

Cache consistency describes the relationship between the authoritative source and its cached representation.

Consider the following sequence:

1. Database record version 5 is cached.
2. Another application updates the database to version 6.
3. An earlier request attempts to publish version 5.
4. The cache receives an outdated value.

This is a stale-write problem.

Version-aware caching helps detect such situations.

### Version comparison

| Source version | Cache version | Interpretation |
|---:|---:|---|
| 5 | 5 | Current |
| 6 | 5 | Stale cache |
| 5 | 6 | Invalid future cache version |
| 6 | 6 | Current |

The implementations use product versions to illustrate this model.

Version comparison alone is insufficient unless updates and cache publication are coordinated correctly. Production systems may require atomic compare-and-set operations or fencing tokens.

## 10. Python Implementation

The Python script models repository behavior and caching workflows.

### Main components

| Component | Responsibility |
|---|---|
| `RedisCacheSimulator` | Cache operations and TTL |
| `ProductRepository` | Authoritative product storage |
| `CacheService` | Cache-aside and write-through workflows |
| `CacheEntry` | Value, creation time, expiration and version |
| `CacheMetrics` | Operational measurements |
| `CacheStrategy` | Strategy selection |

### Technical mechanisms

- `dataclasses` represent structured cache entries.
- `Enum` defines supported caching strategies.
- Dictionaries store product and cache records.
- `RLock` protects shared repository and cache state.
- Per-key locks reduce duplicate database loading.
- `time.monotonic()` manages expiration.
- JSON file handling persists metrics.
- Exceptions represent validation and cache availability failures.

The demonstration includes cache misses, hits, updates, invalidation, expiration, database fallback and deletion.

## 11. JavaScript Implementation

The JavaScript implementation emphasizes asynchronous programming and event-driven monitoring.

### Main components

| Component | Responsibility |
|---|---|
| `MemoryRedis` | Cache adapter |
| `ProductRepository` | Source-data operations |
| `CacheService` | Caching workflows |
| `Metrics` | Performance measurements |
| `EventEmitter` | Cache event notifications |
| `inFlight` | Concurrent request coordination |

### Technical mechanisms

- `Map` stores cache entries and repository records.
- `structuredClone()` prevents accidental mutation of returned objects.
- `async` and `await` model asynchronous database and Redis operations.
- `Promise` coordinates concurrent operations.
- `EventEmitter` publishes cache events.
- `performance.now()` provides monotonic timing.
- Node.js filesystem APIs persist metrics.

The event-driven model distinguishes cache operations from operational monitoring.

A production Redis adapter can replace the in-memory implementation while retaining the application-level service structure.

## 12. C++17 Implementation

The C++ implementation focuses on resource management, state integrity and efficient data structures.

### Main components

| Component | Responsibility |
|---|---|
| `Product` | Domain record |
| `CacheEntry` | Cached value and expiration |
| `RedisCache` | Cache operations |
| `ProductRepository` | Authoritative storage |
| `CachingService` | Business-level caching workflow |
| `CacheMetrics` | Performance counters |

### Technical mechanisms

- `unordered_map` provides average constant-time key lookup.
- `optional` represents missing records.
- `mutex` protects shared state.
- `lock_guard` provides automatic lock release.
- `steady_clock` handles TTL calculations.
- `enum class` represents caching strategies.
- Exceptions handle invalid input and cache failures.

The implementation uses separate repository and cache classes to maintain clear responsibility boundaries.

## 13. Java 17 Implementation

The Java implementation models an enterprise-oriented caching architecture.

### Main components

| Component | Responsibility |
|---|---|
| `Product` | Immutable product record |
| `CacheEntry` | Expiring cache record |
| `CachePolicy` | TTL and caching configuration |
| `Repository` | Repository contract |
| `CacheAdapter` | Cache abstraction |
| `ProductRepository` | Database simulation |
| `InMemoryRedis` | Cache adapter implementation |
| `CacheService` | Application-level workflow |

### Technical mechanisms

- Records represent immutable domain objects.
- Interfaces separate business logic from storage implementations.
- Generics define reusable repository and cache contracts.
- `ConcurrentHashMap` manages concurrent access.
- `AtomicLong` maintains thread-safe metrics.
- `ReentrantLock` coordinates requests.
- `Optional` represents potentially missing records.
- `Duration` represents expiration intervals.
- `ConcurrentHashMap.compute()` prevents an older version from replacing a newer cached version.

The architecture separates caching policy, data access and cache storage.

## 14. PostgreSQL Implementation

The SQL script models the caching workflow using relational database structures.

### Database objects

| Object | Purpose |
|---|---|
| `products` | Authoritative product information |
| `cache_policies` | Caching strategy and TTL configuration |
| `cache_entries` | Cached JSONB records |
| `cache_events` | Cache operation audit trail |
| `validate_cache_entry()` | Cache version validation |
| `invalidate_product_cache()` | Automatic invalidation |
| `get_product_cached()` | Cache-aside retrieval |
| `update_product_write_through()` | Transactional write-through demonstration |
| `invalidate_product_cache_by_id()` | Explicit invalidation |
| `cleanup_expired_cache()` | Expiration cleanup |
| `cache_performance_report` | Aggregated performance measurements |
| `product_cache_status` | Cache validity reporting |

### JSONB storage

The `cached_payload` column uses PostgreSQL JSONB.

This allows product information to be stored as structured JSON while preserving relational identifiers and constraints.

### Trigger-based invalidation

An update or deletion of an authoritative product automatically invokes the invalidation trigger.

The trigger deletes associated cache records and records the source modification.

### Version validation

The cache-entry trigger compares the proposed cache version against the current source version.

It rejects cache publication when the supplied version is stale or ahead of the source.

### Transaction handling

The write-through procedure updates the product and publishes the corresponding cache record within one PostgreSQL transaction.

The demonstration also uses database constraints and exception handling to reject invalid prices and TTL values.

## 15. Performance Measurement

Cache performance is commonly evaluated using the cache hit rate.

The formula is:

\[
\text{Hit Rate} =
\frac{\text{Cache Hits}}
{\text{Cache Hits}+\text{Cache Misses}}
\]

The miss rate is:

\[
\text{Miss Rate}=1-\text{Hit Rate}
\]

Example:

| Metric | Value |
|---|---:|
| Cache hits | 800 |
| Cache misses | 200 |
| Total requests | 1,000 |
| Hit rate | 80% |
| Miss rate | 20% |

A high hit rate generally indicates effective cache reuse, but it does not independently establish good application performance.

Other important measurements include:

- Average and percentile cache latency
- Database query volume
- Cache memory utilization
- Eviction frequency
- Expiration frequency
- Cache connection failures
- Invalidation delays
- Stale-read frequency
- Cache population failures

The implementations maintain counters for hits, misses, writes, invalidations, expirations, origin reads and failures.

## 16. Failure Handling

Caching should not become a single point of application failure.

### Cache outage

When Redis becomes unavailable, an application can use the database directly.

This approach is called cache fallback or fail-open behavior.

It preserves application availability when the source database remains operational.

It can also increase database traffic significantly.

### Cache population failure

If the database returns valid information but cache publication fails, the application can still return the database result.

The next request may encounter another cache miss.

### Invalidation failure

If the database update succeeds but cache invalidation fails, stale data may remain available.

TTL provides a recovery boundary, but it does not guarantee immediate consistency.

### Write-through failure

If the database commits but Redis publication fails, the application must not assume both stores were updated.

A reliable production implementation should record the pending cache update durably and retry it.

### Operational failure matrix

| Failure | Potential impact | Handling |
|---|---|---|
| Cache unavailable | Increased database traffic | Database fallback |
| Cache miss | Additional database read | Populate cache |
| Expired entry | Additional database read | Refresh entry |
| Invalidation failure | Stale reads | Retry and TTL |
| Write-through failure | Database/cache divergence | Durable retry |
| Concurrent miss | Database overload | Request coalescing |
| Stale publication | Older data returned | Version-aware writes |
| Invalid TTL | Incorrect expiration | Input validation |

## 17. Security Considerations

Caching introduces security and data-isolation requirements.

Important controls include:

- Validate cache keys and values.
- Use controlled key namespaces.
- Avoid accepting unrestricted user-provided key patterns.
- Never expose authentication tokens or sensitive credentials through cache diagnostics.
- Apply appropriate Redis authentication and network restrictions.
- Use TLS for Redis connections where required.
- Apply least-privilege access.
- Avoid caching sensitive information unnecessarily.
- Separate tenant-specific cache namespaces.
- Prevent cross-user data exposure.
- Use structured logging without sensitive payload disclosure.
- Apply appropriate retention and expiration policies.

A production implementation must also consider whether cached authorization decisions remain valid after permission changes.

## 18. Complexity Analysis

Let:

- \(n\) represent the number of cache entries.
- \(k\) represent the length of a cache key.
- \(m\) represent the number of entries matching an invalidation prefix.

| Operation | Expected complexity |
|---|---|
| Cache lookup | O(1) average |
| Cache insertion | O(1) average |
| Exact invalidation | O(1) average |
| Prefix invalidation | O(n × k) in the provided in-memory models |
| Full expiration cleanup | O(n) |
| Database lookup | Depends on indexing and query execution |
| Metrics snapshot | O(1) for fixed counters |

Redis uses hash-based data structures for common key operations. Its expiration mechanisms and memory-management behavior differ from the simplified in-memory implementations in this project.

Pattern-based invalidation should be designed carefully because scanning large keyspaces can create performance problems.

## 19. Execution Instructions

### Python

Run the Python file using:

`python redis_caching.py`

The script uses Python standard-library modules.

It creates a JSON metrics file after execution.

### JavaScript

Run using Node.js 18 or later:

`node redis_caching.js`

The implementation uses built-in Node.js modules and does not require npm packages.

It creates a JSON metrics file after execution.

### C++17

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic redis_caching.cpp -o redis_caching`

Execute:

`./redis_caching`

On Windows:

`redis_caching.exe`

### Java 17

Compile:

`javac RedisCaching.java`

Execute:

`java RedisCaching`

### PostgreSQL

Execute the SQL script using PostgreSQL 15 or later.

The script creates the `redis_learning` schema and its database objects.

Run the script as a database user with schema and object creation privileges.

## 20. Important Implementation Limitations

The in-memory implementations reproduce important Redis caching concepts but do not implement the Redis network protocol.

They do not provide:

- Redis persistence
- Redis replication
- Redis Cluster
- Distributed locking
- Redis eviction policies
- Network-level timeout management
- Cross-instance consistency
- Redis Sentinel
- Redis Streams
- Production connection pooling

The PostgreSQL implementation is a relational demonstration of caching behavior rather than a replacement for Redis.

Its relational transaction guarantees apply to PostgreSQL-managed records, not to an independent Redis deployment.

The in-memory prefix invalidation operations scan their local key collections. They should not be treated as a production Redis key-management strategy.

Production deployment requires an actual Redis server, an appropriate client library, connection management, operational monitoring, durable invalidation handling and a consistency policy aligned with application requirements.

## 21. Relationship Between the Four Core Mechanisms

The four concepts address different parts of cache management.

| Mechanism | Main question answered |
|---|---|
| Cache-aside | How is missing data loaded into the cache? |
| Write-through | How is updated data published during a write? |
| TTL | How long should cached information remain valid? |
| Cache invalidation | How should outdated cached information be removed? |

They operate together rather than replacing one another.

A practical enterprise application may use cache-aside for frequently accessed product records, write-through for selected updates, TTL for bounded cache retention, and explicit invalidation for source changes.

The appropriate combination depends on access frequency, write frequency, acceptable staleness, failure recovery requirements and database capacity.
