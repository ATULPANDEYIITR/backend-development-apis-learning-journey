# Rate Limiting

## 1. Introduction

Rate limiting controls how frequently a client can access an application resource within a defined period or according to a controlled request-processing rate.

It is commonly implemented in API gateways, authentication services, cloud applications, distributed systems, payment platforms, and microservices.

A rate limiter evaluates incoming requests against a policy and decides whether the application should process or reject each request.

The main objectives are:

- Prevent excessive API consumption.
- Protect backend services from overload.
- Reduce automated abuse and brute-force attempts.
- Allocate shared resources fairly.
- Enforce customer-specific service quotas.
- Maintain predictable application performance.
- Control request bursts and sustained traffic.

A rejected request normally receives HTTP `429 Too Many Requests`.

The response can include:

| Header | Purpose |
|---|---|
| `Retry-After` | Indicates when the client should retry. |
| `X-RateLimit-Remaining` | Indicates the remaining quota. |
| `X-RateLimit-Limit` | Indicates the configured request limit. |

The implementations use four distinct rate-limiting approaches: fixed window, sliding window, token bucket, and distributed rate limiting.

## 2. Fundamental terminology

| Term | Meaning |
|---|---|
| Client | Application, user, API key, or service making requests. |
| Rate limit | Maximum permitted request consumption. |
| Window | Time interval used to calculate request consumption. |
| Request cost | Number of quota units consumed by a request. |
| Quota | Available request capacity. |
| Burst | A temporary increase in request traffic. |
| Refill rate | Speed at which tokens become available. |
| Rate-limit key | Identifier used to maintain independent client state. |
| Retry delay | Time remaining before a blocked request can become eligible. |
| Distributed limiter | Rate limiter coordinating decisions across multiple application instances. |
| Shared state | Commonly accessible request counters, timestamps, or token balances. |

A rate-limiting decision should contain:

- Whether the request is accepted.
- Remaining capacity.
- Applicable algorithm.
- Retry delay when rejected.

The decision is separate from the actual execution of the requested API operation.

## 3. Fixed Window Rate Limiting

### 3.1 Mechanism

Fixed window rate limiting divides time into consecutive intervals of equal duration.

For example, an authentication endpoint may allow five requests per minute.

Suppose the configured policy is:

- Maximum requests: 5
- Window duration: 60 seconds
- Client: `customer-101`

The first five requests are accepted. Further requests within the same window are rejected.

When the next window begins, the counter resets.

The window can be calculated using:

`window_start = floor(current_time / window_duration) * window_duration`

The current request count determines eligibility:

`current_count + request_cost <= request_limit`

### 3.2 State management

Each client and policy combination maintains:

| Field | Description |
|---|---|
| Client key | Identifies the requesting client. |
| Window start | Beginning of the current interval. |
| Request count | Number of consumed quota units. |

The Python and Java implementations use keyed state maps.

The JavaScript implementation uses `Map`.

The C++ implementation uses `unordered_map`.

The PostgreSQL implementation stores the counter in `fixed_window_state`.

### 3.3 Boundary problem

Fixed windows can produce traffic bursts around interval boundaries.

Consider a limit of five requests per minute.

A client can submit:

- Five requests immediately before a window ends.
- Five requests immediately after the next window starts.

The client can therefore submit ten requests within a short period even though the configured limit is five requests per minute.

This is the principal weakness of fixed-window rate limiting.

### 3.4 Advantages and limitations

| Advantages | Limitations |
|---|---|
| Simple implementation | Boundary bursts |
| Low memory consumption | Coarse time-based control |
| Efficient counter updates | Does not smooth traffic |
| Easy database representation | Uneven request distribution |

**Suitable applications:** Login endpoints, basic API quotas, administrative APIs, and services requiring inexpensive request accounting.

## 4. Sliding Window Rate Limiting

### 4.1 Mechanism

Sliding window rate limiting evaluates requests within a continuously moving time interval.

Instead of resetting a counter at fixed boundaries, it considers the timestamps of requests that remain inside the current window.

For a 60-second interval:

`cutoff = current_time - 60 seconds`

Only requests satisfying the active-window condition are counted:

`request_timestamp > cutoff`

The request is accepted when:

`active_request_count + request_cost <= request_limit`

Expired request records are removed before evaluating a new request.

### 4.2 Sliding window log

The sliding window log implementation maintains an ordered collection of timestamps for each client.

Example:

| Request | Timestamp |
|---|---:|
| R1 | 10:00:00 |
| R2 | 10:00:05 |
| R3 | 10:00:15 |
| R4 | 10:00:25 |

At 10:00:30, all four requests are inside a 60-second window.

At 10:01:05, R1 expires because its timestamp is at the window boundary.

The remaining requests continue contributing to the quota.

The Python implementation uses `deque`.

The Java implementation uses `ArrayDeque`.

The JavaScript implementation uses arrays.

The C++ implementation uses `deque`.

PostgreSQL maintains individual request events in `sliding_window_events`.

### 4.3 Sliding window counter

A sliding window counter is another implementation that approximates the sliding-window request count using the current and previous fixed-window counters.

Its calculation is:

`estimated_count = current_count + previous_count * overlap_fraction`

Here, `overlap_fraction` represents the proportion of the previous window that overlaps the current sliding interval.

This approach reduces memory consumption compared with retaining every request timestamp.

The supplied implementations use sliding window logs rather than approximated counters, allowing exact timestamp-based expiration within their respective state models.

### 4.4 Advantages and limitations

| Advantages | Limitations |
|---|---|
| More consistent quota enforcement | Higher memory consumption |
| Avoids fixed-window boundary bursts | Timestamp storage |
| Accurate expiration | More state operations |
| Suitable for variable request traffic | Requires careful concurrency control |

**Suitable applications:** Search APIs, public APIs, customer-facing services, and endpoints requiring accurate rolling-window quotas.

## 5. Token Bucket Rate Limiting

### 5.1 Mechanism

The token bucket algorithm controls request traffic through a virtual bucket containing tokens.

Each accepted request consumes tokens.

Tokens are replenished continuously at a configured rate.

The bucket has two important parameters:

- Capacity: Maximum number of available tokens.
- Refill rate: Number of tokens replenished per second.

Suppose:

| Parameter | Value |
|---|---:|
| Bucket capacity | 5 tokens |
| Refill rate | 0.5 tokens/second |
| Initial balance | 5 tokens |
| Request cost | 1 token |

Five requests can be accepted immediately.

After ten seconds, five additional tokens can be replenished, provided the bucket has sufficient capacity.

### 5.2 Refill calculation

The refill calculation is:

`elapsed_time = current_time - previous_update_time`

`new_tokens = min(capacity, old_tokens + elapsed_time * refill_rate)`

A request is accepted when:

`available_tokens >= request_cost`

After acceptance:

`remaining_tokens = available_tokens - request_cost`

For an eligible request that lacks sufficient tokens, the estimated retry delay is:

`retry_delay = (request_cost - available_tokens) / refill_rate`

A request whose cost exceeds bucket capacity cannot become eligible through waiting alone. It must be rejected as invalid for that policy or evaluated against a different policy.

### 5.3 Burst handling

The token bucket permits temporary bursts while controlling long-term traffic.

Unlike fixed windows, the bucket does not reset all capacity at a particular clock boundary.

Unlike sliding logs, it does not need to retain every request timestamp.

### 5.4 Advantages and limitations

| Advantages | Limitations |
|---|---|
| Supports controlled bursts | Requires accurate refill calculations |
| Smooth long-term traffic | Requires per-client token state |
| Constant-time state evaluation | Concurrent updates must be atomic |
| Supports weighted request costs | Configuration affects burst behavior |

**Suitable applications:** File uploads, cloud APIs, payment processing, and services that permit bursts but need controlled average consumption.

## 6. Comparison of Rate-Limiting Algorithms

| Characteristic | Fixed Window | Sliding Window Log | Token Bucket |
|---|---|---|---|
| Main state | Counter | Timestamps | Token balance |
| Time handling | Fixed intervals | Moving interval | Continuous refill |
| Boundary bursts | Possible | Controlled | Controlled by capacity |
| Burst support | Limited | Limited by active quota | Explicitly supported |
| Memory usage | Low | Higher | Low |
| Request evaluation | O(1) | O(1) amortized for queue expiration | O(1) |
| State cleanup | Window expiration | Timestamp expiration | Inactive bucket expiration |
| Typical application | Basic quotas | Accurate rolling quotas | Traffic shaping |

The complexity figures describe the supplied in-memory implementations, excluding storage-system and synchronization overhead.

## 7. Distributed Rate Limiting

### 7.1 Why distributed coordination is necessary

A distributed application may operate several API servers behind a load balancer.

Consider this architecture:

Client requests
    |
    v
Load Balancer
    |
    +-------------------+
    |                   |
    v                   v
API Server A        API Server B
    |                   |
    +---------+---------+
              |
              v
       Shared State Store

Suppose the policy permits five requests per minute.

If each server maintains an independent counter, both servers may independently accept five requests.

The effective limit becomes ten requests rather than five.

This is a consistency problem.

Distributed rate limiting solves it by coordinating request decisions through shared state.

### 7.2 Shared state requirements

A distributed rate limiter requires:

- Shared client identifiers.
- Consistent policy configuration.
- Atomic counter or token updates.
- Reliable time handling.
- Concurrency control.
- Appropriate expiration and cleanup.
- Failure-handling policies.

The shared state must be updated as one logical operation.

Reading a token balance, calculating a new balance, and writing it separately can cause concurrent requests to consume the same tokens.

### 7.3 Redis-based implementation

Redis is commonly used for distributed rate-limiting state because it supports fast shared access and atomic operations.

A Redis implementation can use:

- String counters for fixed windows.
- Sorted sets for sliding window logs.
- Hashes for token bucket state.
- Expiration for automatic cleanup.
- Lua scripts for atomic multi-operation evaluation.

A fixed-window counter can use atomic increment operations with an expiration policy.

A sliding-window log can use sorted sets containing request timestamps.

A token bucket can use a hash containing the available token balance and last-refill timestamp.

For token bucket evaluation, the following operations must be atomic:

1. Retrieve the previous balance and timestamp.
2. Calculate elapsed time.
3. Refill tokens.
4. Evaluate the request cost.
5. Update the token balance.
6. Update the timestamp.
7. Return the decision.

A Lua script can execute these operations atomically on a Redis server.

### 7.4 Database-based distributed coordination

The PostgreSQL implementation uses shared relational state instead of an external cache.

Its main coordination mechanisms are:

- `INSERT ... ON CONFLICT`
- `SELECT ... FOR UPDATE`
- Transactional updates.
- Primary-key constraints.
- Shared state tables.
- Transactional audit insertion.

The combination of unique keys and row-level locks ensures that concurrent transactions coordinate around the same client-policy state.

The implementation assumes that requests are evaluated within a transaction and that application instances connect to the same authoritative database.

At PostgreSQL's default `READ COMMITTED` isolation level, the locking statements serialize updates for an individual state row.

For more complex multi-policy operations, additional transaction and isolation design may be necessary.

### 7.5 Distributed system tradeoffs

| Approach | Strength | Limitation |
|---|---|---|
| Local application memory | Very low latency | No cross-instance consistency |
| Shared Redis | Fast distributed coordination | External infrastructure dependency |
| PostgreSQL | Durable transactional state | Database contention |
| Centralized rate-limit service | Consistent policy enforcement | Additional network dependency |
| Partitioned counters | Improved scalability | Coordination and aggregation complexity |

### 7.6 Clock consistency

Distributed systems must account for differences between application-server clocks.

A server with an incorrect clock can refill tokens too early or calculate an inaccurate window boundary.

Possible approaches include:

- Use a centralized time source.
- Use Redis server-side time within atomic scripts.
- Use database server timestamps.
- Use monotonic clocks for local elapsed-time calculations.

The Python and C++ in-memory examples use elapsed-time abstractions. Their distributed simulations use shared state but do not provide real cross-machine persistence.

The SQL implementation uses PostgreSQL server timestamps.

## 8. Python Implementation

The Python file models the algorithms as independent classes.

### Implemented components

| Component | Responsibility |
|---|---|
| `RateLimitPolicy` | Validates policy configuration |
| `FixedWindowLimiter` | Maintains fixed-window counters |
| `SlidingWindowLogLimiter` | Maintains active request timestamps |
| `TokenBucketLimiter` | Maintains token balances |
| `SharedAtomicStore` | Provides common simulated distributed state |
| `DistributedTokenBucketLimiter` | Coordinates shared token consumption |
| `APIGateway` | Applies endpoint-specific policies |
| `RateLimiterTests` | Verifies algorithm behavior |

### Design decisions

Dataclasses represent decisions and state.

Enums distinguish algorithm types.

Dictionaries maintain client-specific state.

Deque provides efficient timestamp expiration.

Thread locks protect in-memory state transitions.

The injected clock makes time-dependent behavior testable without waiting for real intervals.

The test cases verify:

- Fixed-window expiration.
- Sliding-window expiration.
- Token replenishment.
- Independent client quotas.
- Shared distributed state.
- Invalid request costs.
- Invalid configuration.

The distributed store is a simulation, not a networked distributed database. Its lock provides coordination only between objects sharing that store inside the same Python process.

## 9. JavaScript Implementation

The JavaScript file presents an event-driven API gateway architecture.

### Implemented components

| Component | Responsibility |
|---|---|
| `SystemClock` | Supplies real-time timestamps |
| `ManualClock` | Supports deterministic testing |
| `RateLimitEvents` | Publishes request decisions |
| `FixedWindowLimiter` | Enforces interval quotas |
| `SlidingWindowLimiter` | Tracks active timestamps |
| `TokenBucketLimiter` | Controls burst capacity |
| `AsyncMutex` | Serializes asynchronous operations |
| `SharedRateLimitStore` | Maintains shared simulated state |
| `DistributedTokenBucket` | Coordinates application instances |
| `APIGateway` | Evaluates endpoint policies |

### Event-driven workflow

The gateway evaluates each request and produces a decision.

The event emitter publishes the result for monitoring and operational analysis.

Blocked requests can be recorded separately from successful requests.

The distributed implementation uses a promise-based mutex to ensure that concurrent asynchronous operations update shared state sequentially.

The demonstration uses `Promise.all()` to submit concurrent requests through multiple limiter instances.

The test verifies that only the configured number of requests are accepted.

The shared store is process-local. A production deployment requires an actual shared atomic storage system.

## 10. C++17 Implementation

The C++ implementation models a request-processing engine with explicit state management and synchronization.

### Implemented components

| Component | Responsibility |
|---|---|
| `Decision` | Represents an admission decision |
| `WindowState` | Stores fixed-window state |
| `BucketState` | Stores token bucket state |
| `FixedWindowLimiter` | Implements fixed-window evaluation |
| `SlidingWindowLimiter` | Implements timestamp-based expiration |
| `TokenBucketLimiter` | Implements continuous token refill |
| `SharedStateStore` | Holds shared simulated state |
| `DistributedRateLimiter` | Performs coordinated admission |
| `APIGateway` | Maps endpoints to policies |

### Engineering decisions

`unordered_map` provides average O(1) state lookup.

`deque` supports efficient removal of expired sliding-window timestamps.

`mutex` protects shared mutable state.

RAII-based `lock_guard` ensures that locks are released even when exceptions occur.

The API gateway uses separate policies for authentication, search, and upload endpoints.

The test suite verifies boundary conditions and state transitions.

The implementation is designed for a single-process simulation. A production multi-server implementation requires an external shared state service with atomic operations.

## 11. Java 17 Enterprise Implementation

The Java implementation models a more structured enterprise rate-limiting service.

### Domain model

The implementation uses:

- Records for immutable request and response objects.
- Enums for algorithm and request status.
- Interfaces for rate-limiter contracts.
- Custom exceptions for configuration failures.
- Concurrent maps for keyed state.
- Reentrant locks for per-key synchronization.
- Service classes for policy evaluation.

### Enterprise workflow

The request-processing workflow is:

Client request
    |
    v
Request validation
    |
    v
Endpoint policy lookup
    |
    v
Rate limiter evaluation
    |
    +-------------------+
    |                   |
    v                   v
Quota available     Quota exceeded
    |                   |
    v                   v
HTTP 200             HTTP 429
    |                   |
    +---------+---------+
              |
              v
       Operational result

### Policy separation

The gateway assigns different algorithms to different endpoint types.

| Endpoint | Algorithm | Policy |
|---|---|---|
| `/api/login` | Fixed Window | 5 requests per minute |
| `/api/search` | Sliding Window | 10 requests per minute |
| `/api/upload` | Token Bucket | Capacity 5, refill 0.5 tokens/second |

This separation allows each endpoint to enforce its own resource-consumption requirements.

The distributed implementation uses a shared state object protected by a lock. This models atomic state coordination but does not replace a networked distributed store.

## 12. PostgreSQL Database Implementation

The PostgreSQL implementation provides persistent relational state and transactional request evaluation.

### 12.1 Database architecture

The schema is:

`rate_limiting`

Its major relationships are:

Clients
    |
    v
Client Policy Assignments
    |
    v
Rate Limit Policies
    |
    v
API Endpoints

Rate Limit Policies
    |
    +---------------------+
    |                     |
    v                     v
Fixed Window State   Token Bucket State
    |
    +---------------------+
    |
    v
Sliding Window Events

Clients + Policies
    |
    v
Request Audit
    |
    v
Usage Reporting

### 12.2 Tables

| Table | Purpose |
|---|---|
| `clients` | Stores registered API clients |
| `api_endpoints` | Stores application endpoints |
| `rate_limit_policies` | Defines algorithm and quota configuration |
| `client_policy_assignments` | Associates clients with policies |
| `fixed_window_state` | Maintains fixed-window counters |
| `sliding_window_events` | Records individual request events |
| `token_bucket_state` | Maintains available tokens |
| `request_audit` | Stores admission decisions |

### 12.3 Constraints and indexes

Primary keys identify records.

Foreign keys maintain referential integrity.

Unique constraints prevent duplicate client-policy assignments.

Check constraints prevent invalid quotas, token capacities, request costs, and negative balances.

Indexes support:

- Client-policy lookup.
- Timestamp-based sliding-window expiration.
- Client request-history retrieval.
- Rejection analysis.
- Policy-level reporting.

### 12.4 Evaluation function

`evaluate_rate_limit()` is the main database operation.

It accepts:

- Client ID.
- Policy ID.
- Request cost.
- Application instance identifier.

It returns:

- Admission decision.
- Algorithm.
- Remaining quota.
- Retry delay.
- Decision status.

The function validates client activity, policy activity, endpoint availability, and policy assignment before modifying rate-limit state.

### 12.5 Transactional guarantees

The evaluation function performs state changes and audit insertion within the caller's transaction.

This provides an important consistency property:

A request decision and its corresponding state update must commit together.

If the transaction fails, its uncommitted changes can be rolled back.

The PostgreSQL implementation uses row-level locks to coordinate requests that target the same client-policy state.

For the sliding-window algorithm, a coordination row serializes requests before calculating the active request count.

### 12.6 Audit and reporting

The `request_audit` table records both accepted and rejected requests.

The reporting view calculates:

- Total requests.
- Accepted requests.
- Rejected requests.
- Rejection percentage.
- Last request timestamp.
- Client and endpoint information.

These records can support quota investigations, customer usage reporting, operational monitoring, and capacity planning.

### 12.7 Operational limitations

The database implementation has several important production considerations:

- Sliding-window logs can grow rapidly under high request volumes.
- Expired request records require scheduled cleanup.
- Row-level locking can create contention for heavily used clients.
- Database availability directly affects rate-limit evaluation.
- Database timestamps provide a common time reference but do not eliminate every clock and transaction-ordering concern.
- The supplied script assumes that clients and policies are provisioned before request evaluation.
- The database schema does not automatically implement external cache replication or failover.

The sample cleanup procedure provides retention management for historical audit records and sliding-window events.

## 13. Security Considerations

Rate limiting is also an application-security control.

### 13.1 Brute-force protection

Authentication endpoints should have restrictive limits to reduce password-guessing attempts.

Limits can be applied using multiple identifiers:

- Account identifier.
- API key.
- Source IP address.
- Device identifier.
- Authentication endpoint.

An IP-only policy can be insufficient when multiple users share a network.

### 13.2 Distributed denial-of-service protection

Rate limiting can reduce excessive request consumption, but it is not a complete DDoS defense.

Additional controls may include:

- Network-level traffic filtering.
- Web application firewalls.
- Connection limits.
- Request-size restrictions.
- Bot detection.
- Upstream traffic scrubbing.

### 13.3 Identity and key security

Rate-limit keys should not expose sensitive authentication credentials.

API keys should be validated before quota evaluation.

Client identifiers must be derived from trusted authentication information rather than arbitrary request headers.

### 13.4 Resource isolation

Separate policies should protect expensive endpoints.

For example:

| Endpoint | Resource risk | Control |
|---|---|---|
| Login | Authentication abuse | Strict fixed window |
| Search | High query volume | Sliding window |
| Upload | Storage and bandwidth consumption | Token bucket |
| Payment | Expensive transaction processing | Client-specific quota and transaction controls |

### 13.5 Fail-open and fail-closed behavior

A distributed limiter may become unavailable.

Two possible behaviors exist:

**Fail-open:** Allow requests when the rate-limiting service cannot be reached.

This improves application availability but can permit excessive traffic.

**Fail-closed:** Reject requests when the rate-limiting service cannot be reached.

This provides stronger quota enforcement but can interrupt legitimate application operations.

The appropriate behavior depends on the protected resource.

Authentication, payment, and other sensitive operations may require stricter failure handling than low-risk public endpoints.

## 14. Performance and Scalability

### Complexity comparison

Let:

- `n` represent the number of active requests in a sliding window.
- `k` represent the number of clients.
- `m` represent the number of stored policies.

| Algorithm | Typical evaluation | State per client |
|---|---|---|
| Fixed Window | O(1) | O(1) |
| Sliding Window Log | O(1) amortized with ordered expiration | O(n) |
| Token Bucket | O(1) | O(1) |
| Distributed Token Bucket | O(1) state evaluation plus coordination overhead | O(1) |

The sliding-window implementations remove expired timestamps from the beginning of their ordered collections.

The Python implementation uses deque, Java uses ArrayDeque, and C++ uses deque.

The JavaScript implementation uses arrays and removes expired entries from the beginning. This can require O(n) movement for large request logs.

For high-volume JavaScript applications, a ring buffer or deque implementation can reduce this overhead.

### Memory management

Rate-limit state must not grow indefinitely.

Possible approaches include:

- Expire inactive fixed-window counters.
- Remove empty sliding-window logs.
- Delete inactive token buckets.
- Apply database retention policies.
- Use bounded caches.
- Limit the number of active rate-limit keys.

### High-traffic clients

A single highly active client may create a synchronization bottleneck.

Possible improvements include:

- Efficient atomic Redis scripts.
- Carefully designed partitioning.
- Local pre-allocation of quota.
- Hierarchical rate limiting.
- Separate policies for individual resources.

Local quota allocation improves throughput but introduces temporary differences between local and global enforcement.

## 15. Practical Algorithm Selection

| Requirement | Appropriate algorithm |
|---|---|
| Simple request quotas | Fixed Window |
| Accurate rolling request limits | Sliding Window Log |
| Smooth average traffic with bursts | Token Bucket |
| Multiple API servers sharing quotas | Distributed Token Bucket or shared sliding-window state |
| Low-memory local quotas | Fixed Window or Token Bucket |
| Authentication protection | Fixed Window with additional identity-based controls |
| Expensive upload operations | Weighted Token Bucket |
| Public search API | Sliding Window |

Algorithm selection should consider request volume, fairness, burst tolerance, storage overhead, and consistency requirements.

## 16. Edge Cases and Failure Conditions

A production rate limiter must explicitly handle the following conditions.

| Condition | Expected behavior |
|---|---|
| Empty client identifier | Reject invalid input |
| Zero request cost | Reject invalid input |
| Negative request cost | Reject invalid input |
| Cost exceeds policy capacity | Reject request |
| Empty policy configuration | Reject configuration |
| Clock moves backward | Avoid negative refill calculations |
| Multiple simultaneous requests | Use atomic state transitions |
| Inactive client | Reject request |
| Disabled endpoint | Reject or disable policy evaluation |
| Expired window | Remove expired state |
| Shared store unavailable | Apply configured failure policy |
| Excessive client cardinality | Apply state cleanup and bounded storage |
| Invalid retry calculation | Never return a negative delay |

The implementations explicitly validate request keys, positive costs, policy configuration, and time-dependent calculations.

## 17. Testing Strategy

The five source files include executable examples and validation tests.

The core test scenarios are:

1. A client consumes its entire fixed-window quota.
2. The next request is rejected.
3. A new fixed window restores the quota.
4. Sliding-window events expire individually.
5. A sliding-window request is rejected while its quota is exhausted.
6. Token bucket capacity permits an initial burst.
7. Token replenishment restores request capacity.
8. Different clients maintain independent quota states.
9. Two application instances share a common distributed quota.
10. Invalid request costs and configurations produce errors.

### Expected behavior

For a policy with a capacity of three requests:

| Request | Expected decision |
|---|---|
| 1 | Allowed |
| 2 | Allowed |
| 3 | Allowed |
| 4 | Blocked |
| 5 after sufficient refill | Allowed |

This example applies directly to a token bucket with capacity three and a sufficient refill interval.

For fixed and sliding windows, eligibility depends on the respective window boundaries and expiration rules.

## 18. Running the Implementations

### Python

Requirements: Python 3.10 or later.

Run:

`python rate_limiter.py`

The script executes its demonstrations and unit tests.

### JavaScript

Requirements: Node.js 18 or later.

Run:

`node rate_limiter.js`

The program executes the asynchronous API gateway demonstration and tests.

### C++17

Compile:

`g++ -std=c++17 -O2 -pthread rate_limiter.cpp -o rate_limiter`

Run:

`./rate_limiter`

On Windows, run:

`rate_limiter.exe`

### Java 17

Compile:

`javac RateLimitingEngine.java`

Run:

`java RateLimitingEngine`

### PostgreSQL

Execute the SQL file against PostgreSQL 15 or later.

The script creates the `rate_limiting` schema, tables, indexes, functions, triggers, procedures, sample records, and demonstration queries.

The executing database role must have permission to create the required schema objects.

The script uses `gen_random_uuid()` for request identifiers and relies on PostgreSQL's built-in UUID-generation support.

## 19. Implementation Comparison

| Feature | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Fixed Window | Yes | Yes | Yes | Yes | Yes |
| Sliding Window Log | Yes | Yes | Yes | Yes | Yes |
| Token Bucket | Yes | Yes | Yes | Yes | Yes |
| Distributed simulation | Yes | Yes | Yes | Yes | Shared database |
| Atomic coordination | Thread lock | Async mutex | Mutex | Reentrant lock | Row-level lock |
| Request auditing | Console | Events | Console | API responses | Persistent table |
| Policy validation | Dataclass | Validation functions | Exceptions | Records and exceptions | Constraints |
| Deterministic testing | Fake clock | Manual clock | Explicit timestamps | Manual clock | Database execution |

The in-memory implementations demonstrate algorithm behavior and concurrency control within a process.

The PostgreSQL implementation demonstrates persistent, transactional coordination across application instances using a common database.

A production distributed architecture requires a shared state service, reliable failure handling, suitable monitoring, and carefully defined consistency guarantees.
