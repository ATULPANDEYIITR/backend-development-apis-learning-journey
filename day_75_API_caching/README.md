# API Caching: HTTP Caching, Cache-Control, ETags and Conditional Requests

## 1. Technical Scope

API caching reduces repeated communication between clients, intermediaries and origin servers by retaining reusable HTTP representations.

An HTTP cache stores a selected representation of a response and determines whether that representation can be reused without contacting the origin server.

The implementation covers four related areas:

| Area | Primary responsibility |
|---|---|
| HTTP caching | Stores and reuses HTTP representations |
| Cache-Control | Defines storage, freshness and validation rules |
| ETags | Identifies specific representations |
| Conditional requests | Determines whether an existing representation remains valid |

These mechanisms operate together, but they are not interchangeable.

HTTP caching manages representation reuse. Cache-Control establishes caching policy. ETags identify representation versions. Conditional requests allow a client or intermediary to validate an existing representation.

## 2. HTTP Caching Fundamentals

### 2.1 Request and response lifecycle

Consider an inventory API:

`GET /api/inventory/500`

The origin server returns:

- HTTP status: `200 OK`
- Content-Type: `application/json`
- Cache-Control: `public, max-age=60`
- ETag: `"inventory-version-1"`
- A JSON representation containing inventory information.

The cache stores the representation and its associated metadata.

A subsequent request for the same representation can be served directly from the cache while the response remains fresh.

The basic lifecycle is:

Client request
→ Cache lookup
→ Fresh representation available?
→ Yes: return cached response
→ No: contact origin
→ Validate existing representation if possible
→ Store updated representation when permitted
→ Return response

### 2.2 Cache locations

HTTP caches can operate at different architectural layers.

| Cache | Location | Typical purpose |
|---|---|---|
| Browser cache | User's browser | Reuse responses across page requests |
| Application cache | Application process | Avoid repeated internal API calls |
| Reverse proxy | Between clients and origin | Reduce origin traffic |
| CDN cache | Distributed edge infrastructure | Serve geographically distributed requests |
| Gateway cache | API gateway | Reduce backend service load |

A cache's location determines its responsibilities, security boundaries and operational characteristics.

### 2.3 Freshness and age

A cached response is fresh when its current age is less than its freshness lifetime.

A simplified model is:

`Current Age = Initial Age + Time Since Storage`

`Fresh = Current Age < Freshness Lifetime`

For example:

- Freshness lifetime: 120 seconds
- Initial age: 10 seconds
- Time since storage: 30 seconds
- Current age: 40 seconds

The representation remains fresh for approximately 80 seconds.

HTTP freshness calculations also account for response dates, the `Age` header, request and response timing, and applicable cache directives.

The implementations use simplified in-memory age calculations rather than a complete implementation of the HTTP caching specification.

## 3. Cache-Control

`Cache-Control` communicates caching instructions through HTTP request and response headers.

Example:

`Cache-Control: public, max-age=300, s-maxage=600`

This policy defines a five-minute freshness lifetime for private caches and a ten-minute freshness lifetime for shared caches.

### 3.1 Important directives

| Directive | Meaning |
|---|---|
| `public` | Permits storage by shared caches, subject to other rules |
| `private` | Restricts storage to private caches |
| `no-store` | Prohibits storing the response |
| `no-cache` | Requires successful validation before reuse |
| `max-age` | Defines freshness lifetime in seconds |
| `s-maxage` | Defines shared-cache freshness lifetime |
| `must-revalidate` | Requires successful validation after becoming stale |
| `immutable` | Indicates that the representation will not change during its freshness lifetime |
| `stale-while-revalidate` | Allows bounded stale reuse while revalidation occurs, where supported |

### 3.2 Important distinctions

**no-store versus no-cache**

These directives have different meanings.

- `no-store` prevents the cache from storing the response.
- `no-cache` permits storage but requires validation before reuse.

**max-age versus s-maxage**

- `max-age` applies to caches generally.
- `s-maxage` provides a freshness lifetime specifically for shared caches and takes precedence over `max-age` there.

**public versus private**

- `public` permits shared-cache storage when the remaining caching rules allow it.
- `private` prevents shared-cache storage.

A response containing sensitive user information should not be placed in a shared cache merely because an application expects users to access different URLs.

### 3.3 Request directives

Clients can also influence cache behavior.

Examples:

| Request directive | Behavior |
|---|---|
| `Cache-Control: no-cache` | Requests validation before reuse |
| `Cache-Control: no-store` | Requests that the request and its response not be stored |
| `Cache-Control: max-age=0` | Requires a representation with no positive current age |

The implementations demonstrate request-level bypass and revalidation controls.

## 4. ETags

An Entity Tag, or ETag, is an HTTP validator associated with a selected representation.

Example:

`ETag: "a83f102c"`

An ETag allows a client or intermediary to identify whether its stored representation still corresponds to the current origin representation.

### 4.1 Strong and weak ETags

Strong ETag:

`ETag: "version-100"`

Weak ETag:

`ETag: W/"version-100"`

A strong validator indicates byte-for-byte representation equivalence.

A weak validator indicates semantic equivalence even when the representation bytes differ.

Weak validators are useful when minor serialization or formatting changes should not necessarily invalidate a representation.

### 4.2 ETag generation

The Python, JavaScript and Java implementations calculate SHA-256 hashes of serialized response bodies.

The resulting hash is used as a representation identifier.

Conceptually:

`Representation → Serialization → SHA-256 → ETag`

This approach is suitable for demonstrating deterministic content-based validators.

Production systems must ensure that the serialization, content encoding and representation-selection process is consistent. A strong validator must identify the actual selected representation accurately.

A database-generated version identifier is another possible approach.

An ETag should not be treated as an authentication token, authorization mechanism or secret value.

## 5. Conditional Requests

Conditional requests allow clients to determine whether a stored representation remains usable.

They reduce unnecessary response-body transfers.

### 5.1 If-None-Match

A client sends:

`GET /api/products/1001`

`If-None-Match: "product-version-5"`

The origin compares the supplied validator against the current representation.

If the validator matches, the server returns:

`304 Not Modified`

The response does not contain the representation body.

The client or intermediary retains its existing body and can reuse it according to the applicable caching rules.

If the validator does not match, the origin returns the current representation with `200 OK`.

### 5.2 If-Modified-Since

This mechanism uses a modification timestamp.

Example:

`If-Modified-Since: Sat, 14 Nov 2026 05:00:00 GMT`

The origin compares the supplied date with the resource's modification time.

If the representation has not changed, the server can return `304 Not Modified`.

HTTP dates have one-second resolution. Timestamp comparison should account for this limitation.

### 5.3 Validator precedence

When both conditional headers are present:

- `If-None-Match` takes precedence over `If-Modified-Since`.
- `If-Modified-Since` is considered when `If-None-Match` is absent.

This avoids conflicting validator decisions.

### 5.4 HTTP status distinctions

| Status | Meaning |
|---|---|
| `200 OK` | Current representation returned |
| `304 Not Modified` | Existing representation remains valid |
| `404 Not Found` | Requested resource does not exist |
| `412 Precondition Failed` | A request precondition was not satisfied |

`304` is not an error response. It is an optimization mechanism for conditional retrieval.

For GET and HEAD requests, `If-None-Match` uses weak comparison semantics.

For methods such as PUT, conditional request handling has different semantics. `If-Match` is commonly used to prevent lost updates.

## 6. Cache Representation Selection and Vary

A URL alone does not always identify a unique representation.

For example:

`GET /api/products/1001`

The response may depend on:

- `Accept-Language`
- `Accept-Encoding`
- `Accept`

A server can communicate these selection dimensions through:

`Vary: Accept-Language, Accept-Encoding`

The cache must distinguish representations selected using different values of these request headers.

Example:

| URL | Accept-Language | Representation |
|---|---|---|
| `/api/products/1001` | `en` | English response |
| `/api/products/1001` | `fr` | French response |

If a cache ignores `Vary`, it may return an incorrect representation.

The Python and JavaScript implementations construct variant-specific cache identities. The PostgreSQL implementation stores selected request-header values in `vary_values`.

`Vary: *` prevents normal cache reuse based on ordinary request-header matching.

## 7. Cache Invalidation

Expiration and invalidation are separate operations.

**Expiration** determines when a representation becomes stale.

**Invalidation** removes a representation before its normal expiration time.

Consider an inventory update:

1. The client retrieves an inventory representation.
2. The cache stores version 10.
3. An administrator updates inventory.
4. The origin publishes version 11.
5. Existing cache entries are invalidated.
6. The next request retrieves version 11.

Invalidation is important when freshness windows alone cannot satisfy consistency requirements.

HTTP caching also defines invalidation behavior associated with certain successful unsafe requests. Applications should implement additional invalidation for related resources where necessary.

The implementations provide explicit resource-level invalidation.

## 8. Python Implementation

The Python script models an HTTP cache and its origin server.

### 8.1 Domain objects

| Component | Responsibility |
|---|---|
| `CacheControl` | Parses and validates caching directives |
| `HTTPResponse` | Represents an HTTP response |
| `CacheEntry` | Stores representation metadata and freshness information |
| `OriginServer` | Simulates an origin API |
| `HTTPCache` | Implements lookup, validation, storage and invalidation |

### 8.2 Cache algorithm

The cache uses:

- Dictionaries for resource and cache-entry lookup.
- `OrderedDict` for least-recently-used eviction.
- Tuples for logical cache identity.
- Locks for shared-state protection.
- Events for coordinating concurrent requests.

The lookup process first checks whether a representation exists and remains fresh.

A stale representation is conditionally validated using its ETag or Last-Modified metadata.

A successful `304` retains the original body and refreshes its metadata.

### 8.3 Concurrent requests

The `inflight` structure coordinates concurrent requests.

When multiple threads request the same stale representation, subsequent requests can wait for the first origin request rather than independently contacting the origin.

This pattern is known as request coalescing or single-flight execution.

Production implementations should use per-key synchronization, bounded waiting and careful invalidation-generation management.

### 8.4 Execution

Run:

`python api_caching.py`

The demonstration covers:

- Initial cache miss.
- Repeated cache hit.
- Origin request counting.
- Resource invalidation.
- Cache-Control parsing.
- ETag comparison.
- Invalid directive rejection.
- Unsupported URL rejection.

### 8.5 Limitations

The implementation is an educational in-memory cache rather than a complete HTTP intermediary.

It does not fully implement:

- Every HTTP age-calculation rule.
- All request and response directives.
- Range requests and partial representations.
- Complete RFC-compliant date and validator parsing.
- Distributed invalidation.
- Persistent cache storage.

## 9. JavaScript Implementation

The JavaScript implementation adopts an asynchronous event-driven architecture.

### 9.1 Architectural components

| Component | Responsibility |
|---|---|
| `ResourceOrigin` | Simulates an asynchronous API origin |
| `APICache` | Manages cached representations |
| `CacheState` | Defines observable cache outcomes |
| `parseCacheControl` | Validates cache directives |
| `createETag` | Generates content-based validators |
| `EventEmitter` | Publishes cache lifecycle events |

### 9.2 Asynchronous execution

The origin service returns asynchronous results.

The cache uses Promises to coordinate origin operations and `Promise.all()` to demonstrate concurrent requests.

The `pending` Map maintains an in-progress request for each resource identity.

This prevents multiple identical requests from initiating unnecessary concurrent origin work.

### 9.3 Event-driven monitoring

The cache publishes events for:

- `hit`
- `miss`
- `revalidated`
- `invalidate`
- `eviction`

These events can be connected to operational metrics, tracing and logging systems.

### 9.4 Execution

Run:

`node api_caching.js`

The demonstration includes concurrent requests, resource invalidation, cache statistics and validator checks.

### 9.5 Engineering considerations

The JavaScript implementation uses:

- `Map` for cache management.
- `EventEmitter` for lifecycle notifications.
- `Promise` for asynchronous coordination.
- `crypto` for SHA-256 ETag generation.
- `structuredClone` for response isolation.

A production cache should also consider request cancellation, timeout handling, distributed coordination, bounded memory usage and cache-key normalization.

## 10. C++17 Implementation

The C++ implementation focuses on a resource-cache engine with explicit state and policy modeling.

### 10.1 Domain model

| Component | Responsibility |
|---|---|
| `OriginServer` | Stores simulated origin representations |
| `CacheEntry` | Tracks response freshness |
| `CachePolicy` | Models HTTP caching directives |
| `BranchPolicy` | Configures cache security and validation requirements |
| `CacheEngine` | Evaluates requests and manages entries |
| `CacheResult` | Represents the result of a cache operation |

### 10.2 LRU eviction

The cache combines:

- `unordered_map` for average constant-time lookup.
- `list` for maintaining recency.
- Iterators for efficient removal and movement.

When capacity is reached, the least recently accessed entry is removed.

The principal operations have the following expected complexity:

| Operation | Complexity |
|---|---|
| Cache lookup | Average O(1) |
| Cache insertion | Average O(1) |
| LRU promotion | O(1) |
| LRU eviction | O(1) |
| Resource invalidation | Average O(1) |

The implementation uses a single-threaded execution model. A production multithreaded cache would require synchronization and an explicit strategy for concurrent updates.

### 10.3 Cache outcomes

The engine distinguishes:

- `HIT`: A fresh cached representation is reused.
- `MISS`: The origin supplies a representation.
- `REVALIDATED`: The origin confirms the existing representation.
- `BYPASS`: The request does not use normal cache storage or reuse.

This separation makes operational behavior easier to test and monitor.

### 10.4 Compilation

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic api_caching.cpp -o api_caching`

Run:

`./api_caching`

On Windows:

`api_caching.exe`

The program uses only the C++ standard library.

## 11. Java 17 Implementation

The Java implementation models caching as an enterprise service with explicit policy evaluation and immutable domain objects.

### 11.1 Domain types

| Type | Purpose |
|---|---|
| `Resource` | Identifies an origin resource |
| `HttpResponse` | Represents an HTTP response |
| `CachePolicy` | Holds caching instructions |
| `CacheRequest` | Represents an incoming request |
| `CacheKey` | Defines cache representation identity |
| `CacheEntry` | Tracks a stored representation |
| `CacheResult` | Associates an HTTP response with a cache outcome |

Java records are used for immutable domain data.

### 11.2 Policy evaluation

The `CachePolicyEvaluator` interface separates policy decisions from cache storage.

`EnterprisePolicy` implements the storage rules.

The service evaluates:

- Request authentication.
- Cacheability of the HTTP method.
- `no-store`.
- Private-cache restrictions.
- Response status.

This separation supports independent policy testing and alternative implementations.

### 11.3 State management

The cache uses an access-ordered `LinkedHashMap` for LRU behavior.

A `ConcurrentHashMap` maintains in-flight asynchronous requests.

`CompletableFuture` supports asynchronous origin communication and request coordination.

### 11.4 Execution

Compile:

`javac --release 17 ApiCachingEnterprise.java`

Run:

`java ApiCachingEnterprise`

No third-party libraries are required.

### 11.5 Enterprise considerations

A production implementation would require additional controls for:

- Principal-specific private caching.
- Distributed cache consistency.
- Request cancellation and timeouts.
- Asynchronous failure recovery.
- Complete Vary-aware key construction.
- Cache invalidation across application instances.
- Monitoring and audit retention.

## 12. PostgreSQL Implementation

The PostgreSQL script models cache storage, representation versioning, policy assignment, request evaluation and performance reporting.

### 12.1 Relational architecture

The primary relationships are:

`API Resources`
→ `Representations`
→ `Cache Entries`

`Cache Policies`
→ `Resource Policy Assignments`
→ `API Resources`

`HTTP Requests`
→ `Cache Events`

`Vary Headers`
→ `API Resources`

### 12.2 Table responsibilities

| Table | Responsibility |
|---|---|
| `api_resources` | Stores API resource definitions |
| `representations` | Stores versioned response bodies and ETags |
| `cache_policies` | Stores caching directives |
| `resource_policy_assignments` | Associates policies with resources |
| `vary_headers` | Defines representation-selection dimensions |
| `cache_entries` | Stores cached representation references |
| `http_requests` | Records incoming request information |
| `cache_events` | Stores cache operational events |

### 12.3 Database integrity

The schema uses:

- Primary keys for record identity.
- Foreign keys for relational consistency.
- Unique constraints for resource and version identity.
- Check constraints for valid policy values.
- Partial indexes for current representations.
- GIN indexing for JSONB Vary values.
- B-tree indexes for expiration and request retrieval.

The partial unique index on current representations prevents multiple current versions of the same resource.

### 12.4 Stored functions and procedures

| Database routine | Function |
|---|---|
| `evaluate_cache_eligibility` | Determines whether a request can be cached |
| `calculate_expiration` | Calculates cache expiration |
| `store_cache_entry` | Stores a validated representation |
| `evaluate_conditional_request` | Evaluates HTTP validators |
| `find_cache_entry` | Retrieves a matching cached representation |
| `invalidate_resource_cache` | Removes cached entries for a resource |
| `update_resource_timestamp` | Maintains resource modification timestamps |

### 12.5 Conditional request processing

The conditional-request function evaluates ETags before modification dates.

It returns:

- `200` when the current representation should be transferred.
- `304` when a conditional GET or HEAD request matches.
- `404` when the requested representation does not exist.

The function demonstrates validator evaluation rather than implementing a complete HTTP server.

### 12.6 Transaction handling

The script creates its schema and sample data inside a transaction.

Cache invalidation is demonstrated through a savepoint.

The transaction boundary allows related database modifications to be committed or rolled back together.

### 12.7 Reporting

The `cache_performance_report` view calculates:

- Total cache events.
- Cache hits.
- Cache misses.
- Revalidations.
- Bypasses.
- Cache hit percentage.
- Average recorded response time.

The view provides a basic foundation for monitoring cache behavior.

## 13. Security and Data Isolation

Caching can introduce security vulnerabilities when representation identity and authorization are handled incorrectly.

### 13.1 Private information

Consider:

`GET /api/accounts/5001`

The response contains account-specific information.

A shared cache must not return one user's representation to another user.

Appropriate controls include:

- Correct use of `private` and `no-store`.
- Principal-aware cache isolation.
- Authorization checks before serving sensitive data.
- Avoiding credentials in cache keys and logs.
- Restricting access to private cache entries.

### 13.2 Cache poisoning

Cache poisoning occurs when an attacker manipulates request inputs or headers to influence a cached representation that is subsequently served to other users.

Preventive measures include:

- Validating cacheable request headers.
- Correct implementation of `Vary`.
- Canonical cache-key construction.
- Restricting untrusted forwarding headers.
- Separating authenticated and anonymous representations.

### 13.3 Sensitive response storage

`Cache-Control: no-store` should be used when a response must not be stored by HTTP caches.

Application-level caches and database-backed caches must also enforce their own storage restrictions.

HTTP directives alone do not replace application authorization.

## 14. Performance and Operational Considerations

### 14.1 Cache hit ratio

The cache hit ratio measures the proportion of requests served from cache.

`Hit Ratio = Cache Hits / Total Cache Requests × 100`

For example:

| Metric | Value |
|---|---:|
| Total requests | 10,000 |
| Cache hits | 8,000 |
| Cache misses | 1,500 |
| Revalidations | 500 |
| Hit ratio | 80% |

A higher hit ratio can reduce origin traffic, but it does not automatically establish that the cache is operating correctly.

### 14.2 Time-to-live selection

Long freshness lifetimes are suitable for stable representations.

Short freshness lifetimes are preferable for frequently changing information.

The appropriate lifetime depends on:

- Data volatility.
- Business consistency requirements.
- Origin request cost.
- Acceptable staleness.
- Invalidation reliability.

### 14.3 Cache stampede

A cache stampede occurs when many requests simultaneously attempt to retrieve an expired representation.

Possible controls include:

- Request coalescing.
- Stale-while-revalidate.
- Controlled background refresh.
- Randomized expiration.
- Distributed locking.

### 14.4 Distributed cache consistency

An in-memory cache is local to one process.

When several application instances use independent caches, an update in one instance does not automatically invalidate entries in other instances.

Distributed deployments require a coordinated invalidation mechanism or a shared cache architecture.

## 15. Edge Cases and Failure Handling

| Scenario | Expected behavior |
|---|---|
| Missing resource | Return origin `404` |
| Fresh cached representation | Serve cached response |
| Expired representation | Revalidate or retrieve a new response |
| Matching ETag | Return `304` from origin |
| Changed ETag | Retrieve updated representation |
| `no-store` | Do not store |
| `no-cache` | Validate before reuse |
| Private response in shared cache | Do not store |
| `Vary: *` | Do not reuse through ordinary variant matching |
| Unsupported HTTP method | Bypass normal GET caching |
| Invalid Cache-Control value | Reject or safely avoid caching |
| Cache capacity reached | Evict an eligible entry |
| Origin failure | Do not treat the failed fetch as a successful refresh |
| Missing authentication | Avoid serving protected cached data |

A production system should distinguish origin failures from legitimate HTTP responses and should not replace a valid cached representation with an unsuccessful refresh.

## 16. Comparison of the Five Implementations

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Primary focus | Workflow simulation | Async cache service | Cache engine | Enterprise policy service | Relational cache model |
| Cache storage | Ordered dictionary | Map | Hash map and list | LinkedHashMap | Relational tables |
| ETag | SHA-256 | SHA-256 | Simulated validator | SHA-256 | Stored validator |
| Conditional requests | Yes | Yes | Yes | Yes | Yes |
| Cache-Control | Parser | Parser | Parser | Parser | Policy tables |
| Invalidation | Resource-level | Resource-level | Resource-level | Resource-level | Stored procedure |
| Concurrency | Thread coordination | Promise coordination | Single-threaded | CompletableFuture | Transactions |
| Monitoring | Logging | Events and statistics | Console output | Console output | Reporting view |

Each implementation addresses the same HTTP caching domain through a different engineering model.

## 17. Practical Design Rules

1. Cache only representations that are safe to reuse.
2. Use `no-store` for responses that must not be stored.
3. Use `private` for responses restricted to private caches.
4. Use `no-cache` when validation is required before reuse.
5. Use `max-age` to define freshness.
6. Use `s-maxage` when shared caches need a different freshness lifetime.
7. Generate validators that accurately identify selected representations.
8. Prefer `If-None-Match` when ETags are available.
9. Respect `If-None-Match` precedence over `If-Modified-Since`.
10. Implement `Vary` correctly when request headers influence response content.
11. Invalidate representations after relevant resource updates.
12. Prevent sensitive information from crossing authorization boundaries.
13. Monitor hit ratios, origin traffic, revalidation rates and expiration behavior.
14. Treat cache consistency as an application architecture requirement.

## 18. Standards and Implementation Boundaries

The technical model is based on HTTP caching concepts defined in:

- RFC 9110: HTTP Semantics.
- RFC 9111: HTTP Caching.

The source implementations are educational reference systems, not complete replacements for standards-compliant HTTP caches.

In particular, complete intermediary behavior requires additional handling of request directives, response directives, Age calculation, freshness heuristics, authenticated responses, cache validation, partial responses, request methods, and distributed consistency.

The central architectural distinction remains:

**The origin owns the authoritative representation. The cache owns a reusable copy. Cache-Control determines when reuse is permitted, ETags identify representations, and conditional requests establish whether an existing copy remains valid.**
