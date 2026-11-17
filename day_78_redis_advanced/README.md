# Redis Advanced: Pipelines, Transactions, Lua Scripts, and Distributed Locks

## 1. Technical Scope

Redis is an in-memory data store that supports fast data access, atomic commands, expiration, server-side scripting, and concurrent application workloads.

Advanced Redis engineering involves more than issuing individual commands. Applications must control network overhead, maintain consistency during concurrent updates, coordinate distributed workers, and handle failures safely.

This project examines four important Redis mechanisms:

| Mechanism | Primary purpose | Main characteristic |
|---|---|---|
| Pipelines | Reduce network round trips | Multiple commands are sent together |
| Transactions | Execute a group of commands atomically | `MULTI` and `EXEC` |
| Lua scripts | Implement atomic server-side logic | Commands execute within one script |
| Distributed locks | Coordinate concurrent workers | Ownership tokens and expiration |

These mechanisms solve different problems. A pipeline improves communication efficiency, a transaction groups commands into an atomic execution unit, Lua scripting supports conditional server-side operations, and distributed locks coordinate ownership of shared work.

The five source files approach these mechanisms through Python, JavaScript, C++17, Java 17, and PostgreSQL.

## 2. Redis Architecture and Execution Model

Redis processes commands through a server-side execution model. A client sends commands using the Redis Serialization Protocol (RESP).

The general execution flow is:

Client application
    |
    v
Command construction
    |
    v
RESP encoding
    |
    v
Network connection
    |
    v
Redis command processing
    |
    v
Response serialization
    |
    v
Client response handling

The client and server have different responsibilities.

- The client constructs commands and handles connection failures.
- RESP defines the communication format.
- Redis processes commands and manages stored data.
- Transactions and scripts provide server-side execution guarantees.
- Applications handle retries, ownership, idempotency, and business-level consistency.

### RESP protocol

RESP represents commands and responses using structured byte sequences.

The RESP2 protocol includes:

| Prefix | Data type | Purpose |
|---|---|---|
| `+` | Simple string | Successful textual response |
| `-` | Error | Server-side error |
| `:` | Integer | Integer result |
| `$` | Bulk string | String or binary data |
| `*` | Array | Collection of responses |

A command such as `SET inventory:laptop 20` is encoded as an array containing three bulk strings.

RESP parsing must handle incomplete network data. A TCP socket can deliver one response across multiple packets or multiple responses in a single packet.

The Python and JavaScript implementations include RESP2 handling to demonstrate these communication mechanics.

## 3. Redis Pipelines

### 3.1 Meaning

A pipeline allows a client to send several Redis commands without waiting for an individual response after every command.

Without pipelining:

1. The client sends a command.
2. Redis processes it.
3. Redis returns a response.
4. The client sends the next command.

With pipelining:

1. The client constructs several commands.
2. The client sends them together.
3. Redis processes the commands in order.
4. The client collects the responses.

The main benefit is reduced network round-trip overhead.

### 3.2 Performance characteristics

Suppose an application executes 1,000 independent Redis commands.

With individual requests, the client may experience approximately 1,000 network round trips.

With batches of 100 commands, it can reduce the communication pattern to approximately 10 batches.

This does not mean Redis executes all commands in parallel. Pipelining primarily reduces communication overhead.

Performance depends on:

- Network latency.
- Command processing time.
- Payload size.
- Batch size.
- Connection management.
- Server memory availability.
- Response parsing overhead.

### 3.3 Pipeline implementation

The Python implementation provides a `Pipeline` class.

Its responsibilities include:

- Collecting commands.
- Encoding each command using RESP.
- Combining encoded commands into one payload.
- Sending the payload through a single connection.
- Reading the corresponding responses.
- Preserving response order.
- Handling individual command errors.

The JavaScript implementation uses a `RedisPipeline` class and asynchronous execution.

The C++ and Java implementations model pipelines through collections of commands and result objects.

### 3.4 Pipeline failure handling

A pipeline is not automatically atomic.

Consider:

| Command | Result |
|---|---|
| `SET` | Successful |
| `INCRBY` | Successful |
| `HSET` | Failed |
| `GET` | Successful |

A failure in one command does not automatically cancel the other commands.

The client must inspect individual responses.

A network failure introduces a different problem. Redis might have processed some or all commands before the connection was interrupted. The client might not know which commands completed.

Blindly retrying a pipeline containing non-idempotent commands can duplicate business operations.

For example, retrying `INCRBY balance 100` may increase a balance twice.

### 3.5 Practical applications

Pipelines are useful for:

- Bulk cache updates.
- Analytics counters.
- Multiple independent reads.
- Batch session operations.
- Application telemetry.
- Large-scale metadata retrieval.

Avoid unnecessarily large batches because they can increase client memory usage, server response buffering, and latency for other workloads.

## 4. Redis Transactions

### 4.1 Meaning

Redis transactions group multiple commands into one atomic execution unit.

The principal commands are:

| Command | Function |
|---|---|
| `MULTI` | Starts transaction queuing |
| `EXEC` | Executes queued commands |
| `DISCARD` | Cancels queued commands |
| `WATCH` | Monitors keys for concurrent modifications |
| `UNWATCH` | Removes watched-key conditions |

A transaction normally follows this workflow:

Application
    |
    v
MULTI
    |
    v
Queue command 1
    |
    v
Queue command 2
    |
    v
Queue command 3
    |
    v
EXEC
    |
    v
Return command results

Redis executes the queued commands without interleaving commands from other clients during transaction execution.

### 4.2 Atomicity

Atomic execution means other clients cannot observe the transaction's intermediate command execution.

Consider a transfer between two accounts:

- Account A has 1,000 units.
- Account B has 500 units.
- Transfer amount is 100 units.

The transaction performs:

| Operation | Account A | Account B |
|---|---:|---:|
| Initial state | 1,000 | 500 |
| Debit | 900 | 500 |
| Credit | 900 | 600 |

The transaction prevents another client from executing commands between the transaction's queued operations.

### 4.3 Transactions do not provide rollback

An important distinction exists between Redis transactions and traditional relational database transactions.

Redis `MULTI` and `EXEC` do not automatically roll back earlier successful commands when a queued command encounters a runtime error.

For example:

1. A valid command executes.
2. Another command produces a `WRONGTYPE` error.
3. A later valid command can still execute.

The application receives the results of the individual queued commands.

This differs from a database transaction that can roll back the entire transaction following a runtime failure.

### 4.4 Optimistic concurrency using WATCH

`WATCH` supports optimistic concurrency control.

An application can monitor a key before making a conditional update.

Workflow:

1. Read the current account balance.
2. Watch the account key.
3. Calculate the updated balance.
4. Start a transaction.
5. Queue the update.
6. Execute the transaction.
7. Retry if the watched key changed before execution.

If a watched key changes before `EXEC`, Redis aborts the transaction and returns a null result.

This allows applications to implement conditional updates without holding a traditional database lock.

### 4.5 Practical applications

Redis transactions are useful for:

- Related counter updates.
- Coordinated cache changes.
- Conditional inventory operations.
- Multiple related key updates.
- Optimistic concurrency workflows.

For complicated conditional logic, Lua scripting can provide a simpler atomic execution model.

## 5. Redis Lua Scripts

### 5.1 Meaning

Redis supports Lua scripting to execute application logic directly inside the Redis server.

A Lua script can:

- Read keys.
- Validate values.
- Compare conditions.
- Update multiple keys.
- Return structured results.
- Perform conditional operations atomically.

The key advantage is that the entire script executes without another client's commands interleaving with its Redis operations.

### 5.2 EVAL and EVALSHA

Redis provides two important scripting commands.

| Command | Purpose |
|---|---|
| `EVAL` | Sends and executes the script source |
| `EVALSHA` | Executes a previously loaded script using its SHA-1 identifier |
| `SCRIPT LOAD` | Loads a script into the server-side script cache |
| `SCRIPT EXISTS` | Checks whether scripts are available |
| `SCRIPT FLUSH` | Clears the script cache |

`EVALSHA` reduces repeated transmission of large script sources.

The script cache is not permanent. A client can encounter a `NOSCRIPT` error after a cache flush or server-side cache loss.

A robust client therefore needs a fallback mechanism that executes the source using `EVAL` or loads it again.

### 5.3 KEYS and ARGV

Lua scripts receive two important argument collections:

- `KEYS`: Redis keys accessed by the script.
- `ARGV`: Additional application arguments.

For example, an inventory reservation script can receive:

| Argument | Example |
|---|---|
| `KEYS[1]` | `inventory:laptop` |
| `KEYS[2]` | `reservation:ORDER-1001` |
| `ARGV[1]` | `5` |

Explicit key declaration is particularly important for Redis Cluster because all keys accessed by a multi-key script must belong to compatible hash slots.

### 5.4 Inventory reservation

The implemented Lua workflow performs these operations:

1. Read current stock.
2. Convert the requested quantity into a number.
3. Reject invalid quantities.
4. Check whether sufficient stock exists.
5. Decrease stock.
6. Record the reservation.
7. Return the remaining inventory.

Possible results:

| Condition | Result |
|---|---|
| Invalid quantity | `-1` |
| Insufficient inventory | `0` |
| Successful reservation | Remaining stock |

Because validation and modification occur inside one script, concurrent clients cannot interleave another Redis command between these steps.

### 5.5 Script execution limitations

Lua scripting is powerful but requires careful design.

Important considerations:

- Long-running scripts block normal Redis command processing.
- Scripts should use bounded operations.
- Script arguments should be validated.
- Key access must follow Redis Cluster rules.
- Scripts should avoid uncontrolled memory consumption.
- Scripts should not be treated as rollback-capable database transactions.

A further distinction concerns script atomicity and external side effects. Redis cannot automatically roll back an HTTP request, payment gateway operation, or external database update triggered by application code before or after a script.

## 6. Distributed Locks

### 6.1 Meaning

A distributed lock coordinates multiple application processes that need temporary exclusive access to a shared resource.

Consider two payment workers attempting to process the same reconciliation job.

Without coordination:

Worker A
    |
    v
Read shared job
    |
    v
Begin processing

Worker B
    |
    v
Read same job
    |
    v
Begin processing

Both workers may perform the same work.

A distributed lock provides a mechanism for one worker to acquire temporary ownership.

### 6.2 Basic acquisition

Redis supports conditional key creation:

`SET lock:payment unique-token NX PX 10000`

The options mean:

| Option | Meaning |
|---|---|
| `NX` | Set the key only if it does not exist |
| `PX` | Specify expiration in milliseconds |
| `10000` | Lease duration of 10 seconds |

The unique token identifies the owner.

If Redis returns `OK`, the worker has acquired the lock.

If Redis returns null, another valid lock currently exists.

### 6.3 Why expiration matters

A process may terminate unexpectedly after acquiring a lock.

Without expiration, the lock could remain indefinitely.

A lease automatically expires after its configured duration.

This improves recovery from:

- Process crashes.
- Network failures.
- Worker termination.
- Application restarts.
- Unexpected execution interruptions.

A lease must be selected according to the expected operation duration.

A lease that is too short can expire while the original worker is still processing.

A lease that is too long can delay recovery after a worker crashes.

### 6.4 Safe lock release

Deleting a lock directly is unsafe.

Consider:

1. Worker A acquires a lock.
2. Worker A pauses long enough for its lease to expire.
3. Worker B acquires the same lock.
4. Worker A resumes.
5. Worker A deletes the lock.

Worker A has now deleted Worker B's lock.

The correct release operation compares the ownership token before deletion.

The Lua implementation uses:

`GET lock-key == ownership-token`

Only when the comparison succeeds does the script execute `DEL`.

The comparison and deletion happen atomically.

### 6.5 Lock renewal

Long-running tasks may need to extend their lease.

A safe renewal operation must:

1. Read the current ownership token.
2. Verify that the requesting worker still owns the lock.
3. Extend the expiration only when ownership matches.
4. Return failure if the lock has expired or ownership has changed.

A renewal operation must never blindly extend a lock using only its key.

### 6.6 Distributed lock limitations

A Redis lock does not automatically guarantee that a worker will stop executing when its lease expires.

For example:

- Worker A acquires a 10-second lease.
- Worker A pauses for 15 seconds.
- The lease expires.
- Worker B acquires a new lease.
- Worker A resumes and continues processing.

Both workers may now execute the critical operation.

This is why lock ownership and resource-level protection must be considered separately.

## 7. Fencing Tokens

### 7.1 Meaning

A fencing token is an increasing number assigned to successive lock owners.

Example:

| Worker | Lock acquisition | Fencing token |
|---|---|---:|
| Worker A | First | 101 |
| Worker B | Second | 102 |
| Worker C | Third | 103 |

A protected resource remembers the highest accepted fencing token.

When an operation arrives:

- Accept it if its token is newer.
- Reject it if its token is equal to or older than the stored token.

This protects against stale workers continuing after their leases expire.

### 7.2 Important implementation requirement

A fencing token must be allocated by an authoritative, monotonically increasing mechanism.

The protected resource must independently enforce token ordering.

A token that is merely generated inside an individual process is not sufficient.

The C++ and Java examples demonstrate fencing-token validation through a protected resource.

The PostgreSQL implementation includes a persistent token sequence and validation function.

For production Redis systems, the fencing-token allocation mechanism must be designed to remain safe across failover and recovery. A PostgreSQL sequence can provide an authoritative ordering source when PostgreSQL is the chosen coordinator, but it is not automatically part of a Redis atomic operation.

## 8. Comparing the Four Mechanisms

The following comparison identifies their different responsibilities.

| Property | Pipeline | Transaction | Lua script | Distributed lock |
|---|---|---|---|---|
| Main goal | Reduce network overhead | Atomic command grouping | Atomic server-side logic | Coordinate workers |
| Multiple commands | Yes | Yes | Yes | Usually associated with a critical task |
| Conditional logic | Client-side | Limited | Server-side | Ownership-dependent |
| Atomic execution | No | Yes | Yes | Not by itself |
| Reduces round trips | Yes | Can | Yes | Not its primary purpose |
| Supports expiration | Through Redis commands | Through queued commands | Through script commands | Essential to lease management |
| Handles ownership | No | No | No, unless explicitly implemented | Yes |
| Requires fencing | No | No | No | Sometimes essential |

### Choosing the correct mechanism

Use a pipeline when commands are independent and communication overhead is the main problem.

Use a transaction when several commands must execute together and the application needs Redis-level atomic execution.

Use Lua scripting when validation and conditional modifications should happen within one server-side operation.

Use distributed locks when multiple workers must coordinate ownership of a shared task.

Use fencing tokens when stale workers could damage a resource even after losing their lock.

## 9. Python Implementation

The Python file uses only the standard library.

### Components

| Component | Responsibility |
|---|---|
| `RESPClient` | Establishes connections and communicates using RESP2 |
| `Pipeline` | Executes multiple commands over one connection |
| `Transaction` | Queues commands through `MULTI` and `EXEC` |
| `LuaScript` | Uses SHA-based execution with fallback |
| `DistributedLock` | Manages lease ownership |
| `InventoryService` | Performs conditional inventory reservations |

### Important implementation decisions

The client opens a new connection for each standalone command. This avoids response interleaving between independent callers.

Pipelines use one connection for the complete batch.

The transaction implementation sends `MULTI`, queues commands, and then sends `EXEC` through the same socket.

The Lua script manager calculates the script SHA-1 identifier locally and attempts `EVALSHA` first.

The lock implementation uses a UUID ownership token and compare-and-delete Lua logic.

### Practical limitation

This is a minimal RESP2 client intended for learning and controlled demonstrations.

It does not implement:

- Redis Cluster redirection.
- RESP3.
- Connection pooling.
- Sentinel discovery.
- TLS configuration.
- Automatic reconnect and retry policies.
- Pub/Sub.
- Advanced connection multiplexing.

The basic client should not replace a production-grade Redis client library for a high-throughput application.

## 10. JavaScript Implementation

The JavaScript implementation uses Node.js networking capabilities.

### Components

| Component | Responsibility |
|---|---|
| `RESPParser` | Parses incoming RESP2 data |
| `RedisClient` | Manages TCP communication |
| `RedisPipeline` | Executes batches asynchronously |
| `RedisTransaction` | Queues transaction commands |
| `LuaScriptManager` | Manages script hashes and fallback |
| `InventoryService` | Executes atomic reservation logic |
| `DistributedLock` | Coordinates worker ownership |

### Event-driven communication

Node.js uses asynchronous socket events.

The RESP parser accumulates incoming buffers and extracts complete responses.

This is necessary because TCP does not preserve Redis response boundaries.

A response may arrive in several chunks. A single chunk may also contain several responses.

The parser must therefore preserve incomplete bytes until a complete response becomes available.

### Asynchronous execution

Promises allow application code to wait for Redis operations without blocking the JavaScript event loop during network communication.

The pipeline implementation maintains command order and resolves after all expected responses arrive.

### Practical limitation

The example is a compact RESP2 implementation. Its connection handling is intended for controlled demonstrations, not production use.

A production implementation needs robust socket lifecycle management, connection pooling, TLS, cluster support, cancellation, and careful handling of partially completed batches.

## 11. C++17 Implementation

The C++ program uses an in-memory Redis execution model.

### Components

| Component | Responsibility |
|---|---|
| `RedisEngine` | Stores values and manages expiration |
| `RedisValue` | Represents stored values |
| `Pipeline` | Executes a sequence of independent commands |
| `Transaction` | Models grouped command execution |
| `ScriptEngine` | Implements atomic inventory reservation |
| `DistributedLock` | Manages token-based lock ownership |
| `ProtectedResource` | Rejects stale fencing tokens |
| `InventoryService` | Provides inventory operations |

### Data structures

The storage engine uses an `unordered_map` for average constant-time key lookup.

The pipeline and transaction use vectors to preserve command order.

The protected resource stores the latest accepted fencing token.

The lock engine uses expiration timestamps to identify expired leases.

### Important distinction

The C++ implementation is a behavioral simulation rather than a network client.

It demonstrates the business logic and state-management requirements without requiring hiredis or another external dependency.

Its in-memory locking and execution behavior should not be interpreted as a distributed Redis deployment.

### Complexity

| Operation | Expected complexity |
|---|---|
| Key lookup | O(1) average |
| Key insertion | O(1) average |
| Key deletion | O(1) average |
| Pipeline execution | O(n) |
| Transaction execution | O(n) |
| Inventory reservation | O(1) average |
| Fencing validation | O(1) |

Here, `n` represents the number of queued commands.

## 12. Java 17 Implementation

The Java implementation provides an enterprise-oriented domain model.

### Components

| Component | Responsibility |
|---|---|
| `RedisStore` | Concurrent in-memory storage |
| `RedisCommand` | Immutable command representation |
| `CommandResult` | Structured command response |
| `PipelineService` | Pipeline processing |
| `TransactionService` | Transaction state management |
| `ScriptService` | Atomic script execution model |
| `ReviewPolicy` | Reviewer eligibility rules |
| `ApprovalService` | Approval evaluation |
| `DistributedLock` | Lock acquisition and release |
| `ProtectedResource` | Fencing-token enforcement |
| `RepositoryWorkflow` | Integrated policy example |

### Enterprise design decisions

The implementation uses Java records for immutable data structures.

Enums restrict operation types and state values.

Interfaces separate script behavior from the service that executes it.

Concurrent collections support safe access to individual stored entries.

`AtomicLong` provides an increasing fencing-token sequence.

The transaction service explicitly tracks its state:

`CREATED → QUEUED → EXECUTED`

The approval-policy component illustrates how Redis coordination can participate in a broader enterprise workflow.

### Practical limitation

The Java program demonstrates the domain and concurrency model rather than connecting to a real Redis server.

Its synchronized in-memory script execution does not provide the same execution environment as server-side Lua.

Its fencing sequence is process-local and must be replaced with an authoritative shared sequence in a distributed deployment.

## 13. PostgreSQL Data Model

The SQL implementation provides an operational governance and audit database.

It records Redis deployment information, application ownership, script metadata, operation history, transaction outcomes, lock events, and fencing-token information.

### Relational structure

Redis Deployments
    |
    +---- Applications
    |       |
    |       +---- Redis Operations
    |       |       |
    |       |       +---- Pipeline Commands
    |       |       |
    |       |       +---- Redis Transactions
    |       |       |
    |       |       +---- Lua Executions
    |       |
    |       +---- Distributed Locks
    |
    +---- Distributed Locks
    |       |
    |       +---- Lock Events
    |
    +---- Fencing Sequences

Lua Scripts
    |
    +---- Lua Executions

### Main tables

| Table | Purpose |
|---|---|
| `redis_deployments` | Redis deployment configuration |
| `applications` | Applications using Redis |
| `lua_scripts` | Script source and version registry |
| `redis_operations` | Operation execution history |
| `pipeline_commands` | Individual pipeline commands |
| `redis_transactions` | Transaction metadata |
| `lua_executions` | Script execution records |
| `distributed_locks` | Lock ownership and lease records |
| `fencing_sequences` | Monotonically increasing token allocation |
| `lock_events` | Lock lifecycle audit events |

### Constraints

The schema uses:

- Primary keys for entity identity.
- Foreign keys for relational integrity.
- Unique constraints for identifiers.
- Check constraints for valid states and positive durations.
- Partial indexes for active scripts and locks.
- Composite indexes for common lookup patterns.

### Functions and procedures

The SQL implementation provides:

| Database object | Purpose |
|---|---|
| `validate_redis_operation()` | Validates operation metrics |
| `audit_lock_status_change()` | Records lock lifecycle changes |
| `allocate_fencing_token()` | Allocates increasing tokens |
| `acquire_distributed_lock()` | Acquires an audited database-managed lease |
| `release_distributed_lock()` | Performs token-validated release |
| `validate_fencing_token()` | Checks token validity |

The lock procedure uses a PostgreSQL transaction-level advisory lock to serialize acquisition attempts for a deployment and lock key.

This is a PostgreSQL-based coordination model. It is not an implementation of Redis `SET NX PX`.

### Reporting

The SQL includes reporting views for:

- Operation performance.
- Pipeline throughput.
- Active lock monitoring.
- Lua execution history.

It also demonstrates CTE-based inserts, aggregation, filtering, validation queries, and expiration cleanup.

### Operational distinction

PostgreSQL provides durable audit and coordination metadata in this implementation.

Redis remains the intended execution engine for the actual Redis pipeline, transaction, Lua, and lease commands.

A PostgreSQL lock record does not automatically establish ownership of a Redis key. Systems using both databases must define which system is authoritative for each coordination operation.

## 14. Redis Cluster Considerations

Redis Cluster distributes keys across hash slots.

This affects multi-key operations.

A transaction or Lua script accessing multiple keys in Redis Cluster must respect the server's hash-slot requirements.

Hash tags can ensure related keys map to the same slot.

For example, these keys share the same hash tag:

- `inventory:{laptop}:stock`
- `inventory:{laptop}:reservation`

The portion inside braces determines the hash slot.

This is useful when a Lua script must access several related keys.

Cluster-aware clients must also handle:

- `MOVED` responses.
- `ASK` responses.
- Node redirection.
- Connection changes.
- Failover.
- Script cache availability on individual nodes.

A script loaded on one cluster node should not be assumed to exist on every other node.

## 15. Security Considerations

Advanced Redis operations introduce several security requirements.

### Authentication and transport

- Use Redis authentication and ACL users.
- Restrict command permissions.
- Use TLS for sensitive network connections.
- Restrict network access to trusted application systems.
- Avoid exposing Redis directly to public networks.

### Pipeline security

- Validate command arguments.
- Avoid constructing commands from untrusted input.
- Do not log passwords or sensitive payloads.
- Limit pipeline batch sizes.
- Treat command results as untrusted input when used by downstream systems.

### Transaction security

- Validate application permissions before queuing operations.
- Use `WATCH` where optimistic concurrency is required.
- Validate transaction results individually.
- Do not assume runtime command failures cause rollback.

### Lua security

- Restrict script execution privileges.
- Validate all script arguments.
- Keep scripts short and bounded.
- Declare keys explicitly.
- Avoid embedding credentials in scripts.
- Prevent untrusted users from executing arbitrary scripts.

### Lock security

- Generate unpredictable ownership tokens.
- Never release locks using only a key.
- Use bounded lease durations.
- Validate ownership during renewal.
- Apply fencing tokens to protected resources where necessary.
- Keep lock credentials and tokens out of unnecessary application logs.

## 16. Reliability and Failure Scenarios

| Failure | Possible consequence | Appropriate control |
|---|---|---|
| Network interruption | Unknown command completion | Idempotency and operation identifiers |
| Large pipeline | Memory and latency pressure | Bounded batches |
| Runtime transaction error | Partial business-level outcome | Validate individual results |
| WATCH conflict | Transaction abort | Controlled retry |
| Lua script error | Failed script execution | Validation and bounded logic |
| NOSCRIPT response | Script unavailable in cache | EVAL or reload fallback |
| Worker crash | Lock remains until expiry | Lease expiration |
| Expired worker resumes | Stale operations | Fencing tokens |
| Unsafe release | Another worker loses ownership | Token comparison |
| Redis failover | Ownership and script-cache changes | Failover-aware coordination |

### Idempotency

An idempotent operation produces the same intended business result when repeated.

For example, a payment reservation identified by a unique order ID should not create duplicate reservations when a client retries after an uncertain network response.

A production reservation script should therefore include an idempotency check before decrementing inventory again.

The demonstration script focuses on atomic stock reservation. It does not implement complete duplicate-order protection.

## 17. Performance Engineering

### Pipeline optimization

Measure:

- Commands per batch.
- Average payload size.
- Batch execution time.
- Response processing time.
- Network latency.
- Error rate.

Avoid assuming that larger pipelines are always faster.

### Transaction optimization

Keep transactions short.

Large transactions delay other commands while Redis executes their queued operations.

Use `WATCH` only when its optimistic concurrency behavior is necessary.

### Lua optimization

Keep scripts small.

Avoid large loops, unbounded data processing, and unnecessary key access.

Use `EVALSHA` when the script is already available in the server-side cache.

### Distributed lock optimization

Choose leases based on realistic operation durations.

Use renewal only when necessary.

Use bounded acquisition retries and randomized backoff to reduce synchronized retry patterns.

Monitor:

- Lock acquisition latency.
- Lock contention.
- Lease expiration.
- Ownership loss.
- Failed releases.
- Stale fencing-token rejections.

## 18. Testing and Validation Scenarios

The implementations demonstrate the following test cases.

| Scenario | Expected behavior |
|---|---|
| Successful pipeline | All valid responses returned in order |
| Empty pipeline | Empty result collection |
| Successful transaction | Queued commands execute |
| Runtime command error | Error represented in command results |
| Invalid inventory quantity | Reservation rejected |
| Sufficient inventory | Stock decreases |
| Insufficient inventory | Stock remains unchanged |
| Successful lock acquisition | Unique token assigned |
| Concurrent lock attempt | Second worker receives busy result |
| Correct-token release | Lock deleted |
| Incorrect-token release | Lock remains intact |
| Stale fencing token | Protected resource rejects update |
| Expired lease | Ownership is no longer valid |

A production test suite should also test real Redis behavior under concurrent clients, network interruption, failover, cluster redirection, script cache loss, and duplicate request delivery.

## 19. Important Technical Limitations

The source files deliberately use different implementation approaches.

| File | Execution approach | Main limitation |
|---|---|---|
| Python | RESP2 client with real Redis communication | Minimal client without cluster support |
| JavaScript | Asynchronous RESP2 TCP client | Simplified socket lifecycle |
| C++17 | In-memory Redis behavior simulation | No network communication |
| Java 17 | Enterprise-oriented in-memory model | No real Redis server integration |
| PostgreSQL | Durable operational governance database | Does not execute Redis commands |

The C++ and Java examples illustrate data structures, state management, and concurrency-related business rules. They should not be treated as production Redis clients.

The Python and JavaScript examples provide actual Redis communication but intentionally omit several features expected from mature production clients.

The PostgreSQL schema provides operational history and reporting. It does not replace Redis persistence, replication, transactions, or server-side execution.

## 20. Practical Architecture

A production application can separate its responsibilities as follows:

Application Services
    |
    +---- Redis Client Layer
    |       |
    |       +---- Connection Management
    |       |
    |       +---- Pipelines
    |       |
    |       +---- Transactions
    |       |
    |       +---- Lua Script Registry
    |       |
    |       +---- Distributed Lock Service
    |
    +---- Business Logic
    |       |
    |       +---- Inventory Reservation
    |       |
    |       +---- Payment Processing
    |       |
    |       +---- Background Workers
    |
    +---- Reliability Layer
    |       |
    |       +---- Idempotency
    |       |
    |       +---- Retry Policies
    |       |
    |       +---- Fencing Validation
    |       |
    |       +---- Failure Recovery
    |
    +---- PostgreSQL Governance Layer
            |
            +---- Execution Audit
            |
            +---- Script Registry
            |
            +---- Performance Reports
            |
            +---- Lock Event History

The separation prevents communication optimization, atomic execution, worker coordination, and durable audit responsibilities from becoming mixed into one component.

## 21. Key Engineering Distinctions

The most important concepts are the guarantees provided by each mechanism.

**Pipelining is a communication optimization.** It reduces network round trips but does not guarantee atomicity.

**Transactions provide atomic command execution.** Redis prevents other clients from interleaving commands during transaction execution, but runtime command errors do not provide automatic rollback.

**Lua scripts provide atomic server-side application logic.** They are useful when several Redis operations depend on conditions that must be evaluated together.

**Distributed locks provide temporary ownership coordination.** Their safety depends on unpredictable tokens, lease management, correct release, and careful treatment of expired workers.

**Fencing tokens protect resources against stale owners.** Their value comes from enforcement by the resource being protected, not simply from generating an increasing number.

These distinctions determine how Redis advanced features should be combined in inventory systems, payment processing, background jobs, caching infrastructure, and distributed application services.
