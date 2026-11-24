# Async FastAPI: Asynchronous Endpoints, Database Operations and Blocking Pitfalls

## 1. Technical Scope

Asynchronous FastAPI development involves designing HTTP endpoints and application services that can handle concurrent operations without unnecessarily blocking the event loop.

The implementation examines five connected engineering areas:

- Asynchronous HTTP request processing.
- Asynchronous database access.
- Event-loop scheduling and cooperative concurrency.
- Blocking operations and their isolation.
- Resource management, failure handling and performance monitoring.

The five implementations approach these subjects through Python application development, JavaScript event-driven execution, C++ concurrency engineering, Java enterprise service architecture and PostgreSQL data management.

## 2. Asynchronous Programming Fundamentals

### Synchronous execution

A synchronous function normally completes its operation before returning control to its caller.

Consider a request that performs three independent network operations:

    Operation A: 1 second
    Operation B: 1 second
    Operation C: 1 second

When executed sequentially, the approximate execution time is three seconds, excluding overhead.

### Asynchronous execution

An asynchronous function can suspend its execution while waiting for an operation to complete.

During that waiting period, the event loop can execute other eligible coroutines.

    Request received
          |
          v
    Start Operation A
          |
          v
    Await Operation A
          |
          +------ Event loop schedules Request B
          |
          v
    Operation A completes
          |
          v
    Resume Request A

Independent I/O operations can therefore overlap.

Asynchronous execution does not necessarily mean that instructions execute simultaneously on multiple CPU cores.

It primarily improves utilization when applications spend substantial time waiting for I/O.

### Concurrency and parallelism

| Property | Concurrency | Parallelism |
|---|---|---|
| Meaning | Multiple operations make progress | Multiple operations execute simultaneously |
| Primary mechanism | Scheduling | Multiple execution resources |
| Typical use | Network and database I/O | CPU-intensive computation |
| FastAPI application | Concurrent coroutines | Multiple processes or worker threads |

Concurrency and parallelism solve different performance problems.

## 3. Python Async FastAPI Implementation

The Python implementation provides a complete task-management API.

Its primary components are:

| Component | Responsibility |
|---|---|
| FastAPI application | HTTP request routing |
| Pydantic models | Input and output validation |
| Lifespan manager | Application startup and shutdown |
| asyncpg pool | Asynchronous PostgreSQL connections |
| asyncio.Semaphore | Concurrent operation limiting |
| asyncio.gather | Concurrent coroutine execution |
| run_in_threadpool | Isolation of synchronous operations |
| Middleware | Request identification and timing |

### 3.1 Asynchronous endpoints

An asynchronous FastAPI endpoint is declared using `async def`.

Its execution can suspend at an `await` expression.

For example, database access uses:

    record = await connection.fetchrow(query, task_id)

While PostgreSQL processes the query, the event loop can schedule other requests.

The important distinction is that `await` does not automatically make every operation asynchronous. The awaited operation must itself provide non-blocking behavior.

### 3.2 Database connection pooling

Opening a new database connection for every request introduces unnecessary overhead.

A connection pool maintains reusable connections.

The Python implementation initializes a shared asyncpg pool during application startup.

The pool provides:

- Minimum connection capacity.
- Maximum connection capacity.
- Connection acquisition.
- Connection reuse.
- Connection release.
- Application shutdown cleanup.

A connection is acquired only when required.

The `async with pool.acquire()` construct ensures that the connection is returned to the pool when the operation finishes or raises an exception.

### 3.3 Database concurrency

Asynchronous database access allows multiple queries to remain in progress without blocking the event loop.

The number of simultaneous database operations must still be controlled.

The implementation uses both:

- A bounded PostgreSQL connection pool.
- An application-level asynchronous semaphore.

These controls serve different purposes.

The connection pool limits database connections. The semaphore limits entry into selected application operations.

Increasing concurrency without considering database capacity can increase waiting time, connection contention and memory consumption.

### 3.4 Transactions

The task-creation endpoint uses a database transaction.

A transaction groups related database operations into one atomic unit.

The important properties are:

- Atomicity.
- Consistency.
- Isolation.
- Durability.

The task-creation transaction checks an idempotency key before inserting a new record.

The unique database constraint remains necessary because two concurrent requests may both initially observe that a key does not exist.

Application-level checks alone cannot prevent this race condition.

### 3.5 Idempotency

An idempotent operation produces the same intended result when the same request is repeated.

This is particularly important when:

- A client experiences a network timeout.
- A response is lost after successful database insertion.
- A client retries a request.
- A distributed service receives duplicate messages.

The `idempotency_key` column provides a database-enforced uniqueness boundary.

The Python implementation checks for an existing key and handles a concurrent uniqueness conflict.

For production payment or order-processing systems, idempotency records should also retain sufficient information to verify that a repeated key represents the same original request payload.

### 3.6 Input validation

Pydantic validates incoming task data.

The implementation checks:

- Task title length.
- Description length.
- Task status.
- Pagination limits.
- Pagination offsets.
- UUID formatting.
- Permitted update fields.

SQL values are passed as query parameters.

Dynamic SQL identifiers are selected only from a fixed allowlist. User-supplied strings are never accepted as arbitrary column names.

## 4. Event Loop Mechanics

The event loop coordinates asynchronous execution.

A coroutine does not execute merely because it has been declared with `async def`.

It must be awaited, scheduled or otherwise driven by an event loop.

### Coroutine lifecycle

    Created
       |
       v
    Scheduled
       |
       v
    Running
       |
       +---- Awaiting I/O
       |         |
       |         v
       |      Suspended
       |         |
       |         v
       |      Rescheduled
       |         |
       +---------+
       |
       v
    Completed / Failed / Cancelled

The event loop can schedule another coroutine when the current coroutine suspends.

This cooperative scheduling model makes the behavior of individual operations important.

A long-running synchronous function can prevent other coroutines from receiving execution time.

## 5. Blocking Operations and Their Consequences

### 5.1 What is a blocking operation?

A blocking operation prevents the current execution thread from progressing until the operation returns.

Common examples include:

- `time.sleep()`.
- Synchronous HTTP requests.
- Synchronous database queries.
- Large synchronous file operations.
- CPU-intensive calculations.
- Legacy libraries without asynchronous interfaces.

Calling such operations directly inside an asynchronous endpoint can block the event loop.

### 5.2 Blocking versus non-blocking sleep

| Operation | Behavior |
|---|---|
| `time.sleep(2)` | Blocks the executing thread |
| `await asyncio.sleep(2)` | Suspends the coroutine |
| `await asyncio.to_thread(function)` | Executes synchronous work in a worker thread |
| `await run_in_threadpool(function)` | Offloads synchronous work to a thread pool |

The Python implementation includes both an intentional blocking-pitfall endpoint and a thread-pool alternative.

The blocking endpoint is educational and should not be used in production.

### 5.3 Thread-pool isolation

A synchronous library may not provide an asynchronous interface.

Replacing the entire library may be impractical.

A thread pool can isolate its synchronous work from the event loop.

This is useful for:

- Legacy database drivers.
- Synchronous file operations.
- Existing SDK integrations.
- Blocking system interfaces.

Thread pools have finite capacity.

Excessive thread creation increases memory consumption and context-switching overhead.

### 5.4 CPU-bound work

Thread pools are not a universal solution for CPU-intensive Python workloads.

The conventional CPython Global Interpreter Lock limits parallel execution of Python bytecode within a process.

For substantial CPU-bound workloads, alternatives include:

- Process pools.
- Separate worker processes.
- External task-processing systems.
- Native extensions that release the GIL.

The appropriate choice depends on workload size, memory usage, serialization cost and deployment architecture.

## 6. JavaScript Event-Driven Implementation

The JavaScript implementation complements the Python service by implementing an asynchronous HTTP client and bounded request scheduler.

Its main components are:

| Component | Responsibility |
|---|---|
| `fetch` | Asynchronous HTTP communication |
| `Promise` | Asynchronous result representation |
| `Promise.all` | Waiting for multiple operations |
| `AbortController` | Request cancellation |
| `AbortSignal` | Cancellation propagation |
| `EventEmitter` | Request lifecycle events |
| `Map` and `Set` alternatives | Structured in-memory state management |
| Worker pool | Bounded concurrent execution |

### 6.1 Event-driven request processing

The client emits request lifecycle events.

The events include:

- `request:start`
- `request:success`
- `request:finish`

These events allow monitoring logic to remain separate from request execution.

This separation is useful when implementing:

- Request tracing.
- Latency measurement.
- Logging.
- Operational monitoring.
- Failure reporting.

### 6.2 Bounded concurrency

Launching thousands of requests simultaneously can overwhelm a server.

The JavaScript worker pool limits simultaneous operations.

For example, a concurrency limit of five means that no more than five operations are actively processed by the pool at a time.

This protects both the client and the remote service from uncontrolled request bursts.

### 6.3 Retry and exponential backoff

Transient network failures and selected server errors may justify retries.

Exponential backoff increases the waiting period after successive failures.

The implementation also introduces randomized jitter.

Jitter reduces the likelihood that multiple clients will retry at exactly the same moment.

Retries should not be applied indiscriminately.

A failed validation request, for example, should not be retried automatically.

Non-idempotent operations also require particular care. The task-creation example uses an idempotency key to make retry behavior safer.

### 6.4 Cancellation and timeout handling

`AbortController` allows a client to signal that an HTTP request should stop.

Cancellation is not equivalent to guaranteed rollback of server-side work.

A request may already have reached the server before cancellation occurs.

The server must independently manage its database transactions and resource cleanup.

## 7. C++17 Concurrency Engineering

The C++ implementation models a concurrent request-processing engine.

It focuses on execution resources rather than HTTP framework behavior.

### 7.1 Thread pool

The thread pool maintains a fixed collection of worker threads.

Requests are submitted into a bounded queue.

Workers retrieve tasks and execute them.

The design avoids creating a new operating-system thread for every incoming operation.

### 7.2 Futures and promises

The `std::future` interface represents a result that may become available later.

The request engine submits work and receives futures immediately.

The caller can subsequently retrieve the result using `get()`.

Exceptions raised by packaged tasks are propagated through the associated future.

### 7.3 Connection leasing

The simulated database connection pool uses a semaphore-like resource admission mechanism.

A connection lease represents temporary ownership of a database connection.

The nested `Lease` class uses RAII.

Resource Acquisition Is Initialization ensures that the connection is released when the lease object is destroyed.

This also handles exception paths.

### 7.4 Blocking work

The C++ implementation demonstrates that asynchronous submission does not make an operation itself non-blocking.

A blocking operation still occupies the worker executing it.

A bounded thread pool can therefore become saturated when too many workers perform slow synchronous operations.

### 7.5 Complexity and tradeoffs

| Mechanism | Main cost or characteristic |
|---|---|
| Task queue | O(1) insertion and removal |
| Request submission | O(1) average queue insertion |
| Worker management | Fixed thread-management overhead |
| Connection admission | Waiting when capacity is exhausted |
| Future retrieval | May block the calling thread |
| RAII resource release | Deterministic cleanup |

The C++ model is an engineering simulation, not an implementation of an HTTP server or an asynchronous networking library.

## 8. Java 17 Enterprise Service Architecture

The Java implementation models asynchronous service boundaries using `CompletableFuture`.

Its design separates domain types, repository operations and business services.

### 8.1 Domain records

Java records provide concise immutable data structures.

The `Task` record contains:

- Identifier.
- Title.
- Description.
- Task status.
- Creation timestamp.
- Update timestamp.

Validation is performed through the record's compact constructor.

This keeps invalid domain objects from entering the service layer.

### 8.2 Repository abstraction

The `TaskRepository` interface defines asynchronous operations.

Each operation returns a `CompletableFuture`.

This separates the business service from the storage implementation.

An in-memory implementation demonstrates the behavior without requiring a third-party database driver.

A production repository can implement the same interface using an asynchronous database client.

### 8.3 CompletableFuture pipelines

`CompletableFuture` provides mechanisms for composing asynchronous operations.

The implementation uses:

- `supplyAsync()` for asynchronous execution.
- `thenApply()` for result transformation.
- `thenCompose()` for dependent asynchronous operations.
- `allOf()` for coordinating independent operations.
- `handle()` for success and failure processing.

These mechanisms allow application services to compose asynchronous workflows without manually managing every thread.

### 8.4 Bounded execution

The repository uses a bounded executor queue.

An unbounded executor queue can accumulate work faster than workers can process it.

This increases memory consumption and request latency.

The bounded queue introduces an explicit capacity limit and rejection behavior.

The database admission component independently limits simulated database access.

### 8.5 Timeout semantics

A caller-side timeout limits how long a caller waits for a result.

It does not automatically guarantee that the underlying operation stops.

Cancellation behavior depends on the executor, task implementation and underlying I/O library.

This distinction is important in distributed enterprise applications.

### 8.6 State transitions

The service validates task state changes.

The permitted transitions are:

    PENDING
       |
       +------> RUNNING
       |           |
       |           +------> COMPLETED
       |           |
       |           +------> FAILED
       |
       +------> FAILED

Terminal states cannot be reopened through the demonstrated transition rules.

The PostgreSQL implementation applies a corresponding integrity rule at the database level.

The Java example focuses on domain and service-layer validation. Its in-memory update operation does not provide durable persistence or transactional state replacement.

## 9. PostgreSQL Data Architecture

The SQL implementation models an asynchronous API service from an operational database perspective.

### 9.1 Relational model

    Application Instances
           |
           +---- API Requests
           |         |
           |         +---- Tasks
           |                 |
           |                 +---- Task Attempts
           |                 |
           |                 +---- Background Jobs
           |
           +---- Connection Pool Metrics

    API Requests
           |
           +---- Operation Audit

### 9.2 Application instances

`application_instances` stores application deployment information.

It records:

- Instance identity.
- Host name.
- Worker count.
- Maximum database connections.
- Active connections.
- Instance status.
- Heartbeat information.

Constraints prevent invalid connection counts and worker configurations.

### 9.3 API requests

`api_requests` records the lifecycle of HTTP requests.

It distinguishes:

- Received requests.
- Running requests.
- Completed requests.
- Failed requests.
- Timed-out requests.
- Cancelled requests.

The table also records HTTP status codes, duration and correlation identifiers.

A correlation identifier helps connect application activity across distributed components.

### 9.4 Tasks and execution attempts

A task represents a unit of application work.

An attempt represents an individual execution of that task.

This distinction matters because one task may be executed multiple times following transient failures.

The unique constraint on `(task_id, attempt_number)` prevents duplicate attempt numbering for a task.

### 9.5 Connection pool metrics

`connection_pool_metrics` stores periodic connection-pool observations.

It enables historical analysis of:

- Active connections.
- Idle connections.
- Waiting requests.
- Maximum connection capacity.
- Pool utilization.

The data can help identify connection exhaustion and resource contention.

### 9.6 Background jobs

The background job table represents work that is scheduled for asynchronous execution outside the original HTTP request.

Its priority and scheduled time support queue ordering.

The `claim_background_job` function uses `FOR UPDATE SKIP LOCKED`.

This is particularly useful when multiple database-backed workers claim jobs concurrently.

One worker locks a selected job. Other workers skip that locked row rather than waiting for the same job.

The function returns the claimed job, while the surrounding transaction controls when its lock is released.

## 10. Database Integrity and Transaction Management

The SQL script uses several database mechanisms.

| Mechanism | Purpose |
|---|---|
| Primary keys | Unique record identity |
| Foreign keys | Referential integrity |
| Unique constraints | Duplicate prevention |
| Check constraints | Domain validation |
| Enumerated types | Restricted state values |
| Indexes | Efficient retrieval |
| Triggers | Automatic integrity enforcement |
| Functions | Reusable database operations |
| Views | Operational reporting |
| Transactions | Atomic workflow processing |
| CTEs | Structured query composition |

### 10.1 State transition enforcement

The `validate_task_transition` trigger rejects invalid task status changes.

This protects the database from invalid state transitions even when records are modified outside the Python API.

The application and database layers therefore enforce related business rules at different boundaries.

### 10.2 Automatic timestamps

The `update_task_timestamp` trigger updates `updated_at` whenever a task changes.

The request completion trigger records completion time and calculates duration when a request reaches a terminal state.

### 10.3 Indexing strategy

The implementation creates indexes for frequently used retrieval patterns.

Examples include:

- Tasks ordered by creation time.
- Tasks filtered by status.
- Pending jobs ordered by priority and schedule.
- API requests ordered by creation time.
- Task attempts grouped by task identifier.
- Connection pool observations grouped by instance.

Partial indexes are used when a query frequently targets a specific subset of records.

Indexes increase write overhead and consume storage. They should correspond to actual query patterns rather than being created indiscriminately.

## 11. Blocking Pitfalls in FastAPI

The following table distinguishes common problems from appropriate handling strategies.

| Problem | Consequence | Appropriate approach |
|---|---|---|
| `time.sleep()` in async endpoint | Event-loop blockage | `asyncio.sleep()` |
| Synchronous HTTP client | Blocks request execution thread | Asynchronous HTTP client |
| Synchronous database driver | Blocks event loop when called directly | Asynchronous driver |
| CPU-heavy Python computation | Event-loop starvation | Process pool or separate worker |
| Excessive thread creation | Resource exhaustion | Bounded executor |
| Unlimited concurrent database calls | Connection contention | Connection pool and admission control |
| Unbounded background work | Memory growth | Bounded queue |
| Missing timeout | Indefinite waiting | Explicit operation deadlines |
| Missing cancellation handling | Resource waste | Structured cancellation and cleanup |

## 12. Concurrency and Resource Capacity

Asynchronous programming does not remove physical resource limits.

An application remains constrained by:

- CPU capacity.
- Available memory.
- Database connection limits.
- Network bandwidth.
- Remote service capacity.
- Thread-pool capacity.
- Operating-system file descriptors.

### Connection capacity calculation

Suppose a deployment has four application workers.

Each worker has a PostgreSQL pool maximum of ten connections.

The theoretical maximum application connection count is:

    4 × 10 = 40 connections

If the database allows only thirty connections for the application, the deployment configuration is unsafe.

The pool configuration must account for:

- Other applications.
- Administrative connections.
- Background workers.
- Database maintenance.
- Connection overhead.

### Backpressure

Backpressure prevents incoming work from accumulating beyond the capacity of downstream systems.

Useful controls include:

- Bounded queues.
- Connection-pool limits.
- Request concurrency limits.
- Request timeouts.
- Admission control.
- Rate limiting.
- Load shedding.

A service that accepts unlimited work without considering its processing capacity may become unstable under load.

## 13. Error Handling and Failure Scenarios

Production asynchronous systems must account for failures at several layers.

| Failure | Handling mechanism |
|---|---|
| Invalid request data | Pydantic validation |
| Missing task | HTTP 404 |
| Duplicate idempotency key | Unique constraint and conflict handling |
| Database unavailable | HTTP 503 |
| Database timeout | HTTP 504 or controlled service error |
| Connection pool exhaustion | Bounded acquisition and timeout |
| Worker overload | Queue rejection or admission control |
| Client cancellation | Cancellation propagation |
| Invalid task transition | Domain validation and database trigger |
| Repeated transient failure | Bounded retry and backoff |

A database timeout does not always prove that a transaction failed.

The database may have committed a transaction even if the client did not receive the response.

Idempotency and transaction design are therefore essential when retrying state-changing operations.

## 14. Performance Measurement

Performance should be evaluated using measurements rather than assumptions.

Important metrics include:

| Metric | Interpretation |
|---|---|
| Requests per second | Processing throughput |
| Average latency | Typical response duration |
| P50 latency | Median response time |
| P95 latency | Response time experienced by most requests |
| P99 latency | Tail latency |
| Event-loop lag | Delay in event-loop scheduling |
| Active database connections | Current database resource usage |
| Idle connections | Available pooled connections |
| Waiting requests | Resource contention |
| Timeout count | Operations exceeding configured limits |
| Retry count | Repeated execution activity |

Average latency alone can hide serious performance problems.

P95 and P99 measurements provide better visibility into slower requests.

Event-loop monitoring is especially important because blocking operations can affect unrelated requests running in the same event loop.

## 15. Security Considerations

Asynchronous execution does not automatically make an application secure.

The implementations apply or discuss the following controls:

- Parameterized SQL queries.
- Input validation.
- Restricted dynamic SQL identifiers.
- Database constraints.
- Bounded request processing.
- Explicit operation timeouts.
- Controlled retries.
- Resource cleanup.
- Request correlation identifiers.
- Database connection limits.

Production deployments should also use:

- Environment-based secret management.
- TLS for database and network connections.
- Authentication and authorization.
- Least-privilege database roles.
- Request-size limits.
- Rate limiting.
- Sensitive-data filtering in logs.
- Structured audit records.
- Database backup and recovery procedures.

Request identifiers should not contain credentials, tokens or other sensitive information.

## 16. Running the Implementations

### Python

Install the required packages:

- `fastapi`
- `uvicorn`
- `asyncpg`
- `pydantic`

Create a PostgreSQL database named `async_fastapi_db`.

Set the `DATABASE_URL` environment variable to the correct connection string.

Run the application using:

    uvicorn async_fastapi:app --reload

The application starts on port 8000.

The SQL schema for tasks is also initialized during application startup.

### JavaScript

Use Node.js 20 or newer.

Run:

    node async_client.js

The client expects the FastAPI application to be available at `http://127.0.0.1:8000`.

The `API_BASE_URL` environment variable can change this address.

### C++17

Compile with a C++17-compatible compiler and thread support.

The program uses only the standard library.

### Java 17

Compile and run the standalone application using Java 17.

The program uses standard Java concurrency APIs and does not require third-party libraries.

### PostgreSQL

Create the database before executing the SQL file.

The SQL script creates its own schema, domain types, tables, constraints, functions, triggers, indexes, views and sample records.

## 17. Implementation Comparison

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Primary focus | Async HTTP API | Event-driven HTTP client | Concurrent execution engine | Enterprise service architecture | Persistent data model |
| Concurrency model | asyncio | Promises and event loop | Threads and futures | CompletableFuture and executors | Concurrent transactions |
| Resource control | Semaphore and connection pool | Bounded worker pool | Thread pool and connection leases | Bounded executor and semaphore | Constraints and row locking |
| Failure handling | HTTP exceptions | Promise rejection | Exceptions and futures | CompletionException | Transactions and constraints |
| State management | Pydantic models | Structured objects | Domain structures | Immutable records | Relational tables |
| Persistence | asyncpg | HTTP API | Simulated | In-memory repository | PostgreSQL |

## 18. Important Architectural Distinctions

### Async endpoint versus async database driver

Declaring an endpoint with `async def` does not automatically make its database operations non-blocking.

The database driver must support asynchronous execution.

### Async I/O versus background processing

An asynchronous endpoint can efficiently wait for network or database operations.

Long-running independent business workflows may need a separate background-processing system.

The HTTP request should not remain open unnecessarily while lengthy jobs execute.

### Thread pool versus event loop

An event loop schedules coroutines.

A thread pool executes synchronous work on separate threads.

These mechanisms complement one another but are not interchangeable.

### Database pooling versus request concurrency

A database pool limits the number of active database connections.

An application semaphore limits selected concurrent operations.

A system may have many concurrent HTTP requests but only a smaller number of simultaneous database operations.

### Timeout versus cancellation

A timeout limits the permitted waiting period.

Cancellation requests that an operation stop.

Neither necessarily guarantees that remote work or an already committed transaction has been reversed.

### Application validation versus database integrity

Application validation provides immediate and user-friendly feedback.

Database constraints protect persistent data regardless of which application or process performs the write.

Both are necessary in systems with multiple writers.

## 19. Practical Limitations

The implementations deliberately use different levels of abstraction.

- The Python service is a working FastAPI and asyncpg application, but its task lifecycle is a simplified domain model.
- The JavaScript implementation is an HTTP client and concurrency controller, not a second HTTP server.
- The C++ implementation models concurrency and resource admission without implementing an HTTP networking stack.
- The Java implementation demonstrates asynchronous enterprise service boundaries using an in-memory repository rather than a production database.
- The PostgreSQL implementation provides persistent relational structures and transactional job-claiming mechanisms.

The C++ and Java examples illustrate concurrency architecture rather than reproducing Python's event-loop behavior.

A production deployment must also consider multi-process coordination, distributed job recovery, database migrations, observability, authentication, authorization, deployment topology and graceful shutdown.

## 20. Key Engineering Relationships

The architecture can be represented as:

    Client
      |
      v
    HTTP Request
      |
      v
    FastAPI Router
      |
      v
    Request Validation
      |
      v
    Asynchronous Service Layer
      |
      +---------------------+
      |                     |
      v                     v
    Async Database       External API
      |                     |
      v                     v
    Connection Pool      Async HTTP Client
      |                     |
      +----------+----------+
                 |
                 v
          Response Processing
                 |
                 v
          HTTP Response

Long-running or independently scheduled work follows a separate path:

    HTTP Request
         |
         v
    Create Job Record
         |
         v
    Return Accepted Result
         |
         v
    Background Worker
         |
         v
    Execute Job
         |
         v
    Record Result and Status

The central engineering requirement is to preserve non-blocking execution where appropriate while explicitly controlling every finite resource used by the application.
