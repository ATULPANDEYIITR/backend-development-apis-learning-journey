# Redis Fundamentals: Key-Value Data Structures and Operations

## 1. Project Scope

Redis is an in-memory data structure store commonly used as a cache, session store, message-processing component, counter service, and real-time ranking system.

Its fundamental storage model associates a unique key with a value. Unlike a basic key-value database that stores only arbitrary byte sequences, Redis exposes several specialized data structures through commands designed for specific access patterns.

This project implements five core Redis data structures:

| Structure | Purpose | Representative commands |
|---|---|---|
| String | Store text, numbers, counters and serialized values | `SET`, `GET`, `INCR`, `DEL` |
| Hash | Store field-value collections | `HSET`, `HGET`, `HGETALL`, `HDEL` |
| List | Maintain ordered sequences | `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `LRANGE` |
| Set | Maintain unique unordered members | `SADD`, `SREM`, `SMEMBERS`, `SINTER`, `SUNION` |
| Sorted set | Maintain unique members associated with numeric scores | `ZADD`, `ZRANGE`, `ZSCORE` |

The implementations use different programming-language approaches to demonstrate how these structures can be represented, validated, manipulated, and integrated into larger systems.

The Python, JavaScript, C++17 and Java 17 files implement in-memory data stores. The PostgreSQL file provides a relational representation of the same concepts.

## 2. Redis Architecture and the Key-Value Model

A Redis database contains keys that identify stored values.

Conceptually:

    Database
       |
       +-- user:1001       -> HASH
       |
       +-- app:name        -> STRING
       |
       +-- queue:jobs      -> LIST
       |
       +-- skills:backend  -> SET
       |
       +-- leaderboard    -> SORTED SET

A key identifies one logical value. The value has a specific data type and supports operations associated with that type.

For example:

- `user:1001` identifies a user hash.
- `counter:visits` identifies a numeric string.
- `queue:jobs` identifies an ordered job list.
- `skills:backend` identifies a set of technologies.
- `leaderboard` identifies a collection of scored members.

### Key naming

A structured naming convention improves readability and reduces accidental collisions.

| Pattern | Meaning |
|---|---|
| `user:1001` | User information |
| `session:1001` | User session |
| `product:5001` | Product information |
| `queue:jobs` | Job-processing queue |
| `counter:visits` | Visit counter |
| `leaderboard:daily` | Daily ranking |

Redis keys are strings. The colon convention is an organizational choice rather than a special Redis syntax.

### Key uniqueness

A key identifies one value within a Redis database.

Setting an existing key with `SET` replaces its previous value. It does not create another independent value under the same key.

The type of a key also matters. A hash operation cannot be applied to a key currently holding a string.

Redis reports this condition as a `WRONGTYPE` error.

## 3. Strings

Strings are the basic Redis data type.

A Redis string can contain text, numeric representations, serialized JSON, or binary data.

### Main commands

| Command | Function |
|---|---|
| `SET key value` | Create or replace a string |
| `GET key` | Retrieve a string |
| `SET key value NX` | Set only when the key does not exist |
| `INCR key` | Increment an integer |
| `INCRBY key amount` | Increment by a specified amount |
| `DECR key` | Decrement an integer |
| `APPEND key value` | Append text |
| `STRLEN key` | Retrieve string length |

### Example

    SET counter:visits 1000
    GET counter:visits
    INCR counter:visits
    INCRBY counter:visits 25

The resulting value is `1026`.

### Counters

Redis supports atomic integer operations.

This makes strings useful for:

- Request counters.
- Download statistics.
- Page views.
- Rate-limiting counters.
- Inventory quantities.
- Real-time metrics.

A critical distinction is that an increment operation is not equivalent to retrieving a value, changing it in application memory, and writing it back.

A separate read-modify-write sequence can lose updates when multiple clients operate concurrently.

### Conditional writes

`SET key value NX` sets a value only when the key does not already exist.

This can support basic coordination mechanisms and lock acquisition.

For production distributed locks, expiration, ownership tokens, safe release operations, and failure recovery must also be considered.

## 4. Hashes

Hashes represent collections of fields and values under a single key.

They are suitable for objects containing several related attributes.

Example:

    user:1001
        name       = Atul
        department = Engineering
        status     = active
        role       = developer

### Main commands

| Command | Function |
|---|---|
| `HSET` | Add or update a field |
| `HGET` | Retrieve one field |
| `HGETALL` | Retrieve all fields |
| `HDEL` | Remove fields |
| `HEXISTS` | Check field existence |
| `HLEN` | Count fields |
| `HKEYS` | Retrieve field names |
| `HVALS` | Retrieve field values |
| `HINCRBY` | Increment a numeric field |

### Practical applications

Hashes are appropriate for:

- User profiles.
- Product attributes.
- Configuration records.
- Application metadata.
- Device information.
- Session metadata.

### Hashes versus serialized strings

A complete object can be stored as a JSON string or as a hash.

| Characteristic | JSON string | Hash |
|---|---|---|
| Storage model | One serialized value | Multiple fields |
| Individual field updates | Usually require serialization and rewriting | Direct field updates |
| Partial field retrieval | Application parsing required | Direct field retrieval |
| Structure | Application-defined | Redis hash |
| Typical use | Complex serialized objects | Attribute-oriented records |

A hash is not a replacement for a relational database. It does not automatically provide relational constraints, foreign keys, or joins.

## 5. Lists

Redis lists represent ordered sequences of string elements.

They support insertion and removal at both ends.

Example:

    queue:jobs
        0 -> validate
        1 -> build
        2 -> test
        3 -> deploy

### Main commands

| Command | Function |
|---|---|
| `LPUSH` | Insert at the left |
| `RPUSH` | Insert at the right |
| `LPOP` | Remove from the left |
| `RPOP` | Remove from the right |
| `LRANGE` | Retrieve an inclusive index range |
| `LLEN` | Retrieve list length |
| `LINDEX` | Retrieve an element by index |
| `LREM` | Remove matching elements |
| `LTRIM` | Retain a specified range |

### Queue behavior

A first-in, first-out queue can be implemented using:

- `RPUSH` to insert jobs.
- `LPOP` to process jobs.

A last-in, first-out structure can use operations at the same end.

### Indexing

Redis list ranges use inclusive ending indexes.

For example:

    LRANGE queue:jobs 0 -1

Returns all elements.

Negative indexes count backward from the end.

`-1` represents the last element.

### Performance

List operations at the ends are generally efficient.

Operations that require traversing or modifying elements in the middle can become expensive as the list grows.

Redis Streams and dedicated queue systems are more suitable for workflows requiring message acknowledgments, consumer groups, replay, and detailed delivery guarantees.

## 6. Sets

Sets contain unique string members without maintaining a meaningful insertion order.

Example:

    skills:backend
        Python
        Java
        C++

Adding the same member repeatedly does not create duplicate entries.

### Main commands

| Command | Function |
|---|---|
| `SADD` | Add members |
| `SREM` | Remove members |
| `SMEMBERS` | Retrieve all members |
| `SISMEMBER` | Check membership |
| `SCARD` | Count members |
| `SINTER` | Calculate intersection |
| `SUNION` | Calculate union |
| `SDIFF` | Calculate difference |
| `SPOP` | Remove and return a member |

### Set operations

Consider two sets:

    backend = {Python, Java, C++}

    cloud = {Python, Java, Go}

Intersection:

    {Python, Java}

Union:

    {Python, Java, C++, Go}

Difference:

    backend - cloud = {C++}

### Practical applications

- Unique visitor tracking.
- Technology classifications.
- User group membership.
- Feature eligibility.
- Tag collections.
- Relationship discovery.

Sets are useful when membership and uniqueness matter more than ordering.

## 7. Sorted Sets

Sorted sets combine unique members with numeric scores.

Every member has one score. Members are ordered by score, with lexicographical member ordering used to break equal-score ties in ascending range operations.

Example:

    leaderboard
        Alice   -> 950
        Charlie -> 900
        Bob     -> 850

### Main commands

| Command | Function |
|---|---|
| `ZADD` | Add or update scored members |
| `ZRANGE` | Retrieve members in ascending score order |
| `ZREVRANGE` | Retrieve members in descending score order |
| `ZSCORE` | Retrieve a member's score |
| `ZRANK` | Retrieve ascending rank |
| `ZREVRANK` | Retrieve descending rank |
| `ZREM` | Remove members |
| `ZCARD` | Count members |
| `ZCOUNT` | Count members in a score interval |
| `ZRANGEBYSCORE` | Retrieve members by score range |

### Ranking example

    ZADD leaderboard 950 Alice
    ZADD leaderboard 850 Bob
    ZADD leaderboard 900 Charlie
    ZREVRANGE leaderboard 0 2 WITHSCORES

Expected ranking:

| Rank | Member | Score |
|---:|---|---:|
| 1 | Alice | 950 |
| 2 | Charlie | 900 |
| 3 | Bob | 850 |

### Practical applications

- Gaming leaderboards.
- Popularity ranking.
- Priority scheduling.
- Time-based event scores.
- Real-time ranking systems.
- Recommendation ordering.

### Sets versus sorted sets

| Property | Set | Sorted set |
|---|---|---|
| Unique members | Yes | Yes |
| Numeric score | No | Yes |
| Ordered retrieval | No | Yes |
| Membership checking | Yes | Yes |
| Ranking | No | Yes |
| Primary purpose | Membership | Membership and ranking |

A sorted set is preferable when ranking or score-based retrieval is required.

## 8. Key Expiration and TTL

Redis supports automatic expiration of keys.

Expiration is useful for temporary information that should not remain indefinitely.

Examples include:

- Authentication sessions.
- Verification codes.
- Temporary cache entries.
- Rate-limiting windows.
- Short-lived application state.

### Main commands

| Command | Function |
|---|---|
| `EXPIRE key seconds` | Set expiration in seconds |
| `PEXPIRE key milliseconds` | Set expiration in milliseconds |
| `EXPIREAT key timestamp` | Set an absolute expiration time |
| `TTL key` | Retrieve remaining lifetime in seconds |
| `PTTL key` | Retrieve remaining lifetime in milliseconds |
| `PERSIST key` | Remove expiration |

### TTL return values

| Result | Meaning |
|---:|---|
| Positive integer | Remaining lifetime |
| `-1` | Key exists without expiration |
| `-2` | Key does not exist |

Redis expiration uses time-based semantics. Expired keys become logically unavailable, while physical removal can occur through expiration processing.

### Expiration example

    SET session:1001 authenticated
    EXPIRE session:1001 3600
    TTL session:1001

The session is configured to expire after one hour.

Expiration is associated with the key, not an individual hash field, list element, set member, or sorted-set member.

## 9. Key Management

Redis provides commands for managing keys independently of their stored data structures.

| Command | Function |
|---|---|
| `EXISTS` | Check whether keys exist |
| `DEL` | Delete keys |
| `UNLINK` | Delete keys asynchronously |
| `TYPE` | Identify a key's data type |
| `RENAME` | Rename a key |
| `KEYS` | Retrieve matching keys |
| `SCAN` | Incrementally iterate through keys |
| `DBSIZE` | Count database keys |
| `FLUSHDB` | Remove keys from the current database |

### KEYS versus SCAN

`KEYS` can block Redis while processing large keyspaces.

`SCAN` provides incremental iteration and is generally preferable for operational key inspection.

A production application should avoid using unrestricted key enumeration during normal request processing.

## 10. Python Implementation

The Python implementation uses a class-based in-memory store.

### Internal representation

The primary dictionary maps key names to entries.

Each entry contains:

- A data type.
- A stored value.
- An optional expiration timestamp.

The `Entry` dataclass represents this structure, while the `DataType` enumeration restricts the available value categories.

Python dictionaries represent strings, hashes, and sorted-set member-score mappings.

Lists represent ordered collections, while sets provide uniqueness and efficient membership operations.

### Type enforcement

The `_get` and `_create` methods centralize data type validation.

A command that expects a hash cannot operate on a string key.

This produces a dedicated `WrongTypeError` rather than allowing accidental type conversion.

### Expiration

The implementation uses `time.monotonic()` for expiration calculations.

A monotonic clock is appropriate for measuring elapsed time because changes to the system clock do not affect expiration intervals.

Expired entries are removed lazily when accessed or during key enumeration.

### Persistence

The snapshot mechanism serializes stored entries into JSON.

It uses a temporary file and replacement operation to reduce the risk of partially written snapshots.

The loader validates the snapshot before replacing existing data.

This is an educational snapshot implementation, not a complete equivalent of Redis RDB or AOF persistence.

### Testing

The script includes tests for:

- String increments.
- Conditional string creation.
- Hash operations.
- List ordering.
- Set intersections.
- Sorted-set ranking.
- Type errors.
- Missing keys.
- Expiration.
- Deletion.
- Invalid scores.
- Snapshot restoration.

## 11. JavaScript Implementation

The JavaScript implementation uses Node.js standard-library capabilities.

### Data structures

| Redis type | JavaScript representation |
|---|---|
| String | JavaScript string |
| Hash | `Map` |
| List | `Array` |
| Set | `Set` |
| Sorted set | `Map` with score-based sorting |
| Keyspace | `Map` |

The keyspace is a `Map`, allowing efficient key lookup without relying on object-property semantics.

### Asynchronous programming

Operations use asynchronous method signatures.

This provides a service-oriented interface compatible with Node.js applications that interact with networked data stores.

The implementation uses Node.js filesystem promises for snapshot persistence.

### Event-driven behavior

The store extends `EventEmitter`.

It publishes events when keys are created, strings are set, and keys expire.

These events illustrate how application components can react to changes without being tightly coupled to the storage implementation.

### Transactions

The JavaScript transaction method creates a snapshot of the in-memory keyspace.

It accepts synchronous callbacks and restores the snapshot when an exception occurs.

Asynchronous callbacks are rejected to prevent an `await` from introducing interleaving during the transaction.

This is a local rollback demonstration rather than a replacement for Redis transaction commands.

### Important limitation

JavaScript execution in a single event-loop thread does not automatically make arbitrary asynchronous workflows transactional.

A real Redis client provides server-side command execution, connection management, and Redis transaction capabilities.

## 12. C++17 Implementation

The C++ implementation focuses on domain modeling and typed storage.

### Variant-based value representation

The `Value` type uses `std::variant` to represent the five supported structures.

This allows a key to hold one of the following:

- `std::string`
- `Hash`
- `List`
- `Set`
- `SortedSet`

The implementation uses `std::holds_alternative` and `std::get` to validate and retrieve the correct representation.

### Container selection

| Container | Purpose |
|---|---|
| `unordered_map` | Main keyspace |
| `map` | Hashes and sorted-set members |
| `vector` | Lists |
| `set` | Unique members |
| `variant` | Type-safe value representation |
| `optional` | Missing values |
| `chrono` | Expiration |

### Transaction rollback

The transaction method copies the keyspace before executing operations.

An exception restores the previous state.

The design demonstrates rollback through an in-memory snapshot, but it is not equivalent to Redis server transaction isolation.

### Performance considerations

The selected STL containers have different computational properties.

| Operation | Typical complexity |
|---|---|
| `unordered_map` lookup | Average O(1) |
| `map` lookup | O(log n) |
| `set` insertion | O(log n) |
| `vector` append | Amortized O(1) |
| `vector` front removal | O(n) |
| Sorted-set demonstration | O(n log n) for ranking |

The C++ implementation prioritizes explicit type handling and understandable domain behavior over reproducing Redis's internal optimized data structures.

## 13. Java 17 Implementation

The Java implementation models an enterprise-oriented cache service.

It separates storage mechanics from application-facing operations.

### Domain components

| Component | Responsibility |
|---|---|
| `RedisType` | Defines supported data types |
| `CacheEntry` | Represents a stored value and expiration |
| `CacheResult` | Distinguishes cache hits, misses and expirations |
| `RankedMember` | Represents sorted-set ranking information |
| `RedisStore` | Executes data operations |
| `CacheService` | Provides application-level cache workflows |

### Generic structures

The `CacheEntry<T>` class represents typed storage entries.

Java collections provide the underlying structures:

- `Map` for key-value storage.
- `List` for ordered values.
- `Set` for unique members.
- `Map<String, Double>` for sorted-set scores.

Java records provide immutable result types.

### Thread safety

The implementation uses `ReentrantReadWriteLock`.

Read operations acquire a read lock where possible.

Mutation and expiration-sensitive operations use a write lock.

This protects shared in-memory state from concurrent access through the provided service methods.

The design uses a single process and does not provide distributed locking.

### Enterprise service boundary

`CacheService` exposes higher-level operations for user profiles and authentication sessions.

A user profile is represented as a hash.

A session is represented as a string with a configured expiration.

This separation allows application code to work with meaningful operations instead of directly managing internal storage entries.

### Transaction behavior

The transaction mechanism creates a deep snapshot of the keyspace and restores it if an operation fails.

This demonstrates local rollback and failure recovery.

It should not be confused with Redis `MULTI` and `EXEC`, database transactions, or distributed transaction protocols.

## 14. PostgreSQL Relational Implementation

The PostgreSQL script models Redis structures using relational tables.

Unlike the in-memory implementations, this version uses relational constraints and transactions to preserve data integrity.

### Database architecture

    redis_lab
        |
        +-- redis_keys
        |
        +-- redis_strings
        |
        +-- redis_hash_fields
        |
        +-- redis_list_items
        |
        +-- redis_set_members
        |
        +-- redis_sorted_members
        |
        +-- redis_operation_log

### Key registry

`redis_keys` is the central table.

It stores:

- Unique key names.
- Declared value types.
- Creation timestamps.
- Modification timestamps.
- Expiration timestamps.

Every specialized structure references its key through a foreign key.

This provides referential integrity and cascading deletion.

### String table

`redis_strings` stores one value for each string key.

Its primary key is also a foreign key to the registry.

### Hash table

`redis_hash_fields` stores field-value pairs.

The composite primary key `(key_id, field_name)` prevents duplicate field names within one hash.

### List table

`redis_list_items` stores list elements with explicit positions.

The composite primary key `(key_id, position)` ensures unique positions within a list.

The position field provides an ordering mechanism.

### Set table

`redis_set_members` uses a composite primary key consisting of the key identifier and member value.

This prevents duplicate set members.

### Sorted-set table

`redis_sorted_members` stores members and numeric scores.

The composite primary key prevents duplicate members within one sorted set.

The index on `(key_id, score, member_value)` supports score-ordered retrieval.

### Database functions

The script implements PostgreSQL functions and procedures for:

- String retrieval and updates.
- Integer increments.
- Hash insertion and retrieval.
- List insertion and removal.
- Set insertion and intersection.
- Sorted-set ranking.
- Key expiration.
- Key existence.
- Key deletion.
- Expired-key cleanup.

### Triggers

A trigger updates the modification timestamp whenever the key registry record changes.

### Transactions

The script demonstrates a savepoint and rollback.

PostgreSQL transaction semantics are distinct from the snapshot rollback mechanisms used in the programming-language implementations.

### Important database distinction

PostgreSQL is not an in-memory Redis implementation.

It provides relational persistence, foreign keys, constraints, indexing, SQL reporting, and transactional operations.

The relational schema models Redis-style structures for educational and data-integrity purposes.

It does not reproduce Redis protocol compatibility, memory allocation, eviction policies, persistence formats, replication, or network behavior.

## 15. Data Structure Comparison

| Feature | String | Hash | List | Set | Sorted set |
|---|---|---|---|---|---|
| Primary value | Text or bytes | Field-value pairs | Ordered elements | Unique elements | Member-score pairs |
| Duplicate members | Not applicable | Field names unique | Allowed | Not allowed | Not allowed |
| Maintains order | Value only | No application-level field order guarantee | Yes | No | Yes |
| Numeric scores | No dedicated score | No dedicated score | No | No | Yes |
| Best use | Counters and cache values | Objects and attributes | Queues and sequences | Membership | Ranking |

## 16. Operational Performance

Redis is designed around in-memory data access.

Its performance depends on data structure, operation complexity, value size, and server workload.

Typical complexity characteristics:

| Operation | Typical complexity |
|---|---|
| `GET` | O(1) |
| `SET` | O(1) |
| `HGET` | O(1) |
| `HSET` | O(1) per field, subject to implementation |
| `LPUSH` | O(1) |
| `RPUSH` | O(1) |
| `LPOP` | O(1) |
| `SADD` | O(1) per member, average |
| `SISMEMBER` | O(1), average |
| `SINTER` | Depends on input set sizes |
| `ZADD` | O(log N) per member |
| `ZRANGE` | O(log N + M), where M is returned |
| `DEL` | Depends on the size and type of the value |
| `SCAN` | Incremental iteration |

The complexity of a command does not describe its complete production cost. Network transfer, serialization, memory allocation, data size, and concurrent workload also affect latency.

## 17. Redis Transactions and Atomicity

Redis provides transaction commands that group operations for execution:

- `MULTI`
- `EXEC`
- `DISCARD`
- `WATCH`
- `UNWATCH`

A typical transaction workflow is:

    MULTI
    SET account:A 500
    INCR account:B
    EXEC

Redis executes queued commands sequentially when `EXEC` is issued.

A Redis transaction does not provide general SQL-style rollback for runtime command errors.

`WATCH` provides optimistic concurrency control by allowing a transaction to be aborted if watched keys change before execution.

The programming-language implementations use snapshots for educational rollback demonstrations. These are deliberately different from actual Redis transaction semantics.

## 18. Expiration, Eviction and Persistence

Three concepts must remain distinct.

### Expiration

Expiration controls how long a key remains valid.

It is configured using commands such as `EXPIRE` and `PEXPIRE`.

### Eviction

Eviction removes keys when Redis reaches configured memory limits.

Common policies include:

- `noeviction`
- `allkeys-lru`
- `allkeys-lfu`
- `volatile-lru`
- `volatile-lfu`
- `allkeys-random`
- `volatile-random`
- `volatile-ttl`

Expiration and eviction are different mechanisms. A key can be evicted before its configured expiration time when the applicable memory policy requires it.

### Persistence

Redis provides persistence mechanisms such as:

- RDB snapshots.
- AOF (Append Only File).
- RDB and AOF combinations.

RDB stores point-in-time snapshots.

AOF records write operations for reconstruction.

Persistence configuration affects recovery behavior, storage overhead, and durability.

The JSON snapshot mechanisms in the Python and JavaScript files are simplified educational implementations, not substitutes for Redis persistence.

## 19. Security and Production Considerations

A production Redis deployment requires security and operational controls.

### Authentication and authorization

- Enable authentication.
- Use Redis ACLs.
- Assign least-privilege permissions.
- Restrict commands and key patterns where appropriate.
- Avoid sharing administrative credentials.

### Network security

- Keep Redis inaccessible from untrusted networks.
- Configure firewall restrictions.
- Use TLS where required.
- Separate application and administrative access.

### Memory management

- Configure `maxmemory`.
- Select an appropriate eviction policy.
- Monitor memory fragmentation.
- Monitor key growth and large values.
- Avoid unbounded collections.

### Application security

- Validate key names and user-controlled values.
- Avoid embedding sensitive credentials in cache keys.
- Avoid unrestricted key enumeration.
- Use safe serialization formats.
- Apply appropriate expiration to sensitive temporary information.

### Reliability

- Configure persistence according to recovery requirements.
- Monitor replication and failover.
- Understand backup and restoration procedures.
- Handle connection failures and command timeouts.
- Use retries carefully, especially for non-idempotent operations.

### Operational monitoring

Important metrics include:

- Memory usage.
- Connected clients.
- Command execution rate.
- Cache hit ratio.
- Cache miss ratio.
- Evicted keys.
- Expired keys.
- Keyspace size.
- Command latency.
- Replication status.

## 20. Practical Redis Workflows

### User profile caching

    HSET user:1001 name Atul
    HSET user:1001 department Engineering
    HGET user:1001 name
    HGETALL user:1001

The hash stores related attributes under one key.

### Session management

    SET session:1001 authenticated
    EXPIRE session:1001 3600
    TTL session:1001

The session is configured to expire automatically.

### Job processing

    RPUSH queue:jobs build
    RPUSH queue:jobs test
    LPUSH queue:jobs urgent
    LRANGE queue:jobs 0 -1
    LPOP queue:jobs

The list maintains an ordered collection of jobs.

For reliable production processing, consider Redis Streams or a dedicated message queue when acknowledgment and recovery guarantees are required.

### Unique membership

    SADD skills:backend Python
    SADD skills:backend Java
    SADD skills:cloud Python
    SINTER skills:backend skills:cloud

The intersection identifies technologies shared between two groups.

### Leaderboard

    ZADD leaderboard 950 Alice
    ZADD leaderboard 850 Bob
    ZADD leaderboard 900 Charlie
    ZREVRANGE leaderboard 0 2 WITHSCORES

The sorted set provides score-based ranking.

## 21. Running the Implementations

### Python

Requirements: Python 3.10 or later.

Run the script directly using Python.

The demonstration and automated unit tests execute without third-party dependencies.

### JavaScript

Requirements: Node.js 18 or later.

Run the file using Node.js.

The implementation uses only built-in modules, including `fs`, `path`, `os`, and `events`.

### C++17

Requirements: A C++17-compatible compiler.

Compile using the C++17 language standard.

The program uses standard-library containers and does not require external packages.

### Java 17

Requirements: JDK 17.

Compile the single Java source file and run its main class.

The implementation uses Java standard-library collections, records, streams, time APIs, and concurrency locks.

### PostgreSQL

Requirements: PostgreSQL 15 or later.

Execute the SQL file using a database account with permission to create schemas, types, tables, functions, procedures, triggers, and views.

The script creates the `redis_lab` schema and its sample records.

The demonstration transaction intentionally rolls back to its savepoint before the final commit.

## 22. Limitations of the Educational Implementations

The five implementations demonstrate Redis data structures and their application-level behavior. They are not complete Redis server replacements.

| Capability | Implementation status |
|---|---|
| Key-value model | Implemented |
| Strings | Implemented |
| Hashes | Implemented |
| Lists | Implemented |
| Sets | Implemented |
| Sorted sets | Implemented |
| Key expiration | Implemented |
| TTL inspection | Implemented |
| Type validation | Implemented |
| Basic transaction demonstration | Implemented |
| Snapshot persistence | Implemented in Python and JavaScript |
| Redis RESP protocol | Not implemented |
| Redis client/server networking | Not implemented |
| Replication | Not implemented |
| Redis Cluster | Not implemented |
| Production eviction algorithms | Not implemented |
| RDB and AOF compatibility | Not implemented |
| Distributed locking | Not implemented |
| Redis Streams | Not implemented |

The implementations intentionally focus on fundamental storage structures, command semantics, validation, and realistic application workflows rather than reproducing Redis server internals.
