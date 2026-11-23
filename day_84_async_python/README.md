# Async Python: Coroutines, Event Loops and Concurrency

## 1. Technical scope

Asynchronous Python provides a programming model for coordinating operations that spend time waiting for external events.

Typical applications include:

- HTTP API clients.
- Database operations.
- Network servers.
- Message-processing systems.
- File-transfer services.
- Concurrent data collection.
- Distributed job processing.
- Background task orchestration.

The central mechanism is cooperative multitasking. A coroutine suspends when it reaches an appropriate `await` expression, allowing the event loop to execute another ready coroutine.

Asynchronous execution is particularly useful when an application manages many I/O-bound operations.

It does not automatically make CPU-intensive Python calculations execute in parallel.

## 2. Core concepts

### 2.1 Coroutines

A coroutine is an asynchronous computation that can suspend and resume execution.

An asynchronous function is declared using `async def`.

Calling an asynchronous function creates a coroutine object. It does not immediately execute the function body to completion.

The coroutine must be awaited or scheduled as a task.

The Python implementation demonstrates:

- Coroutine declaration.
- Coroutine invocation.
- Awaiting results.
- Coroutine composition.
- Exception propagation.
- Coroutine cancellation.

The distinction between calling and executing a coroutine is important:

| Operation | Behavior |
|---|---|
| Calling an async function | Creates a coroutine object |
| `await coroutine` | Executes it within the current asynchronous task |
| `asyncio.create_task()` | Schedules it for concurrent execution |
| `asyncio.gather()` | Coordinates multiple awaitables |
| `asyncio.TaskGroup` | Provides structured task management |

### 2.2 The event loop

The event loop coordinates asynchronous execution.

Its responsibilities include:

- Tracking scheduled tasks.
- Monitoring timers.
- Processing callbacks.
- Managing readiness of asynchronous operations.
- Resuming suspended coroutines.
- Coordinating cancellation.

A simplified execution model is:

Application
→ Coroutine creation
→ Task scheduling
→ Event loop
→ Awaitable operation
→ Suspension
→ Other ready tasks
→ Operation completion
→ Coroutine resumption
→ Result delivery

An event loop does not require a separate operating-system thread for every coroutine.

Thousands of I/O-bound coroutines can be coordinated by a comparatively small number of threads.

The Python script uses `asyncio.run()` as its application entry point. It creates and manages the event loop and handles its shutdown.

### 2.3 The await expression

`await` suspends the current coroutine until the awaited operation produces a result or raises an exception.

For example, `await asyncio.sleep(1)` schedules a timer and suspends the current task.

It does not block the event-loop thread like `time.sleep(1)`.

An important restriction is that `await` can be used inside asynchronous functions, not ordinary synchronous functions.

### 2.4 Concurrency and parallelism

These concepts describe different execution properties.

| Property | Concurrency | Parallelism |
|---|---|---|
| Meaning | Multiple operations make progress during overlapping periods | Multiple operations execute simultaneously |
| Main objective | Efficient coordination | Increased computational throughput |
| Execution | Can use one thread | Requires multiple execution resources |
| Typical example | Concurrent network requests | Parallel numerical processing |
| Python mechanism | `asyncio` | Multiprocessing or suitable native execution |

An asynchronous application can be concurrent without being parallel.

The C++17 and Java 17 implementations demonstrate thread-based concurrency to provide contrasting execution models.

## 3. Coroutine scheduling and task management

### 3.1 Creating tasks

`asyncio.create_task()` schedules a coroutine to run independently of the current coroutine.

The returned task represents the scheduled execution.

Tasks support:

- Awaiting completion.
- Cancellation.
- Exception retrieval.
- Execution-state inspection.
- Naming.

Creating a task is useful when several operations should make progress concurrently.

Unmanaged background tasks can create problems when their exceptions are never retrieved or when application shutdown occurs before they finish.

### 3.2 Concurrent execution with gather

`asyncio.gather()` coordinates multiple awaitables and returns their results.

The Python implementation uses it for:

- Concurrent service operations.
- Batch processing.
- Shared-state demonstrations.
- Coordinated worker execution.

The default exception behavior propagates an exception from a failing awaitable.

With `return_exceptions=True`, exceptions are returned as result entries. This is useful when individual operations should fail independently.

A result must be inspected before it is treated as successful data.

### 3.3 Structured concurrency with TaskGroup

`asyncio.TaskGroup`, introduced in Python 3.11, manages related tasks within a defined scope.

Its main characteristics are:

- The parent scope waits for child tasks.
- A failing child causes sibling cancellation.
- Exceptions are propagated when the group exits.
- Task lifetime is associated with the containing scope.

This provides stronger lifecycle guarantees than creating independent background tasks without a clear owner.

The Python implementation uses a TaskGroup for related asynchronous operations.

## 4. Controlling concurrency

Unrestricted task creation can overwhelm external services, database connections, memory and network resources.

A concurrency limit establishes a maximum number of simultaneous operations.

### 4.1 Semaphore

`asyncio.Semaphore` maintains an available-operation counter.

When the counter reaches zero, additional tasks wait until a permit becomes available.

The implementation uses a semaphore to limit job processing.

For a concurrency limit of three:

- Three jobs can enter the protected section.
- Additional jobs wait.
- A completed job releases its permit.
- Another waiting job can proceed.

The `async with` statement releases the permit even when an exception occurs.

This is important for avoiding permanently occupied capacity.

### 4.2 Queue

`asyncio.Queue` provides asynchronous communication between producers and consumers.

The producer adds jobs using `put()`.

Consumers retrieve jobs using `get()`.

A bounded queue introduces backpressure. Producers must wait when the queue reaches its configured capacity.

The producer-consumer example demonstrates this mechanism.

`task_done()` records completion of an item, while `join()` waits until the unfinished-task count reaches zero.

Every successful `get()` must eventually have a matching `task_done()` call.

Production systems should also define shutdown signals, worker-failure handling and recovery procedures.

### 4.3 Locks

`asyncio.Lock` protects shared state from conflicting coroutine operations.

The bank-account example uses a lock to prevent concurrent deposits and withdrawals from overwriting one another's changes.

A lock is appropriate when multiple coroutines modify the same in-memory resource.

It does not provide protection against other processes or database clients.

Database transactions and database-level locking are necessary for shared persistent state.

### 4.4 Events

`asyncio.Event` provides a synchronization signal.

Multiple tasks can wait on the same event.

When `set()` is called, waiting tasks are released.

Events are useful for:

- Service initialization.
- Worker startup.
- Coordinated shutdown.
- Readiness signaling.
- Application-wide state transitions.

## 5. Error handling and resilience

### 5.1 Exception propagation

Exceptions raised inside coroutines propagate through awaited operations.

An application should distinguish expected operational failures from programming errors.

Examples include:

| Failure | Appropriate handling |
|---|---|
| Connection failure | Potential retry |
| Invalid input | Reject operation |
| Timeout | Cancel or abandon operation |
| Authorization failure | Reject without retry |
| Programming error | Record and investigate |
| Cancellation | Perform cleanup and propagate cancellation |

The examples use `try`, `except` and `finally` to manage failures and resources.

### 5.2 Timeouts

An operation that never completes can consume resources indefinitely.

`asyncio.timeout()` establishes a deadline for a block of asynchronous work.

When the deadline expires, cancellation is initiated and a `TimeoutError` is raised outside the timeout context.

Timeouts should reflect actual service expectations.

A timeout that is too short causes unnecessary failures. A timeout that is too long increases resource consumption and delays recovery.

### 5.3 Cancellation

Cancellation is a control-flow mechanism.

Calling `task.cancel()` requests cancellation. The coroutine normally receives `asyncio.CancelledError` at a suspension point.

A coroutine should:

1. Perform necessary cleanup.
2. Release acquired resources.
3. Propagate cancellation.

Swallowing cancellation without a deliberate reason can interfere with structured concurrency and application shutdown.

### 5.4 Retry and exponential backoff

Transient failures sometimes recover without intervention.

Exponential backoff increases the delay between retry attempts.

For an initial delay of 100 milliseconds:

| Attempt | Delay before retry |
|---|---:|
| 1 | 100 ms |
| 2 | 200 ms |
| 3 | 400 ms |
| 4 | 800 ms |

Retries should be limited.

Operations with side effects should use idempotency keys or equivalent safeguards to prevent duplicate transactions.

The Python implementation demonstrates bounded exponential backoff.

A production implementation should also consider jitter, retry budgets and server-provided retry instructions.

## 6. Asynchronous iteration and resource management

### 6.1 Asynchronous generators

An asynchronous generator combines `async def` and `yield`.

It allows values to be produced incrementally while supporting asynchronous operations between values.

The Python example uses `async for` to consume generated records.

This is useful for streaming large datasets without loading every record into memory.

### 6.2 Asynchronous context managers

An asynchronous context manager implements:

- `__aenter__()`
- `__aexit__()`

It is entered using `async with`.

Typical applications include:

- Database sessions.
- Network connections.
- HTTP clients.
- Asynchronous locks.
- External service resources.

The context manager example demonstrates acquisition, execution and cleanup.

Resource cleanup must also work when an operation fails or is cancelled.

## 7. Performance characteristics

Asynchronous execution is most effective when tasks spend substantial time waiting.

Consider ten independent network operations, each taking approximately 500 milliseconds.

Sequential execution has an approximate waiting time of five seconds.

Concurrent execution can approach the duration of the slowest request, subject to service latency, concurrency limits and overhead.

Actual performance depends on:

- Number of operations.
- Network latency.
- External service capacity.
- Connection-pool limits.
- Task scheduling overhead.
- Memory consumption.
- Queue capacity.
- Error and retry rates.

### CPU-bound workloads

An event loop generally executes Python coroutine code on its event-loop thread.

A CPU-intensive calculation that does not yield can prevent other coroutines from progressing.

Suitable alternatives include:

- `asyncio.to_thread()` for blocking functions that can benefit from thread execution.
- `loop.run_in_executor()` for thread or process executors.
- `ProcessPoolExecutor` for CPU-intensive Python computations.

Threads are particularly useful for blocking I/O. Process-based execution is often more appropriate for CPU-heavy Python workloads.

## 8. JavaScript implementation

The JavaScript implementation demonstrates a complementary asynchronous model based on the Node.js runtime.

### 8.1 Promises

A Promise represents a future result.

It can be:

- Pending.
- Fulfilled.
- Rejected.

`async` functions return promises, and `await` retrieves their eventual values.

### 8.2 Promise coordination

| Mechanism | Behavior |
|---|---|
| `Promise.all()` | Resolves when all inputs resolve; rejects when an input rejects |
| `Promise.allSettled()` | Returns the outcome of every input |
| `Promise.race()` | Settles according to the first settled input |
| `Promise.resolve()` | Creates a fulfilled promise |
| `Promise.reject()` | Creates a rejected promise |

The implementation uses `Promise.allSettled()` for failure isolation.

### 8.3 Event loop and microtasks

JavaScript execution involves:

- The call stack.
- Runtime-managed asynchronous operations.
- The task queues.
- The microtask queue.

Promise callbacks execute as microtasks.

Timer callbacks execute through the event-loop scheduling mechanism.

The implementation demonstrates the ordering between synchronous statements, promise callbacks and timers.

### 8.4 AbortController

`AbortController` provides a cancellation signal.

An asynchronous operation must explicitly support the signal to respond to cancellation.

A timeout race alone does not guarantee that the underlying operation stops.

The implementation passes an abort signal to its sleep operation.

### 8.5 Workflow dependencies

The JavaScript workflow engine uses a directed dependency graph.

Tasks are represented by a `Map`.

A task can execute after its dependencies complete.

Cycle detection prevents invalid dependency graphs from entering execution.

This approach is useful for data pipelines and multi-stage asynchronous processing.

## 9. C++17 implementation

C++17 does not include the language-level coroutine support introduced in C++20.

The C++ implementation therefore uses standard concurrency primitives.

### 9.1 Threads

A thread provides an independently scheduled execution path.

The thread pool maintains a fixed number of worker threads.

Workers retrieve functions from a shared queue and execute them.

This avoids repeatedly creating operating-system threads for individual tasks.

### 9.2 Futures and promises

`std::future` represents a value that becomes available later.

`std::promise` provides a mechanism for supplying that value.

`std::async()` can schedule an operation and return a future representing its result.

The implementation also demonstrates exception propagation through futures.

### 9.3 Synchronization

The implementation uses:

- `std::mutex` for mutual exclusion.
- `std::lock_guard` for scoped locking.
- `std::unique_lock` for flexible lock management.
- `std::condition_variable` for waiting and notification.
- `std::atomic` for thread-safe counters.

The message queue demonstrates producer-consumer synchronization.

A condition-variable wait uses a predicate to protect against spurious wakeups.

### 9.4 Engineering tradeoff

A thread pool provides predictable thread consumption but introduces synchronization overhead.

Its performance depends on task duration, queue contention, thread count and available hardware.

It is suitable for workloads requiring explicit multithreaded execution.

## 10. Java 17 implementation

Java offers a mature asynchronous programming model built around executors, futures and completion stages.

### 10.1 ExecutorService

`ExecutorService` separates task submission from thread management.

The implementation uses a fixed thread pool.

This provides bounded worker-thread allocation.

### 10.2 CompletableFuture

`CompletableFuture` supports asynchronous composition.

Important operations include:

| Method | Purpose |
|---|---|
| `supplyAsync()` | Executes a supplier asynchronously |
| `runAsync()` | Executes a task without a return value |
| `thenApply()` | Transforms a successful result |
| `thenCombine()` | Combines two completed results |
| `thenCompose()` | Chains dependent asynchronous operations |
| `exceptionally()` | Provides exception recovery |
| `allOf()` | Coordinates multiple futures |
| `orTimeout()` | Applies a completion timeout |

The implementation uses explicit executors to control execution resources.

### 10.3 Enterprise execution

The Java example models asynchronous enterprise jobs using immutable records.

Each job contains an identifier, description, duration and failure condition.

The job service produces structured results.

The implementation also demonstrates:

- Retry scheduling.
- Task cancellation.
- Timeout handling.
- Dependency execution.
- Failure recovery.
- Executor shutdown.

One important distinction is that cancelling a future does not guarantee that every underlying blocking operation immediately stops.

Operations must cooperate with interruption or cancellation.

## 11. PostgreSQL asynchronous job processing

The PostgreSQL implementation models persistent asynchronous execution.

Unlike an in-memory event loop, a database-backed queue stores jobs and execution state across application restarts.

### 11.1 Relational architecture

The database relationships are:

Tenant
→ Queue
→ Job
→ Job Attempt
→ Job Event

Worker
→ Job Attempt
→ Job Lease

Job
→ Job Dependency
→ Parent Job

The main tables are:

| Table | Responsibility |
|---|---|
| `tenants` | Separates organizational ownership |
| `queues` | Stores execution and retry configuration |
| `workers` | Registers processing workers |
| `jobs` | Stores persistent asynchronous jobs |
| `job_dependencies` | Defines execution prerequisites |
| `job_attempts` | Records individual executions |
| `job_events` | Maintains an execution audit trail |

### 11.2 Job lifecycle

The database uses five states:

`pending → running → completed`

`running → pending` for retryable failures.

`running → failed` when retry attempts are exhausted.

`pending → cancelled` and `running → cancelled` are also supported.

Completed, failed and cancelled jobs are treated as terminal states by the transition-validation trigger, except that failed jobs can be explicitly returned to pending.

### 11.3 Concurrent job claiming

The `claim_next_job()` function uses:

`FOR UPDATE SKIP LOCKED`

This is important for multiple workers.

When one worker locks a job row, another worker skips that locked row rather than waiting for it.

This reduces contention during queue consumption.

The claim operation:

1. Validates worker ownership.
2. Checks queue access.
3. Updates the worker heartbeat.
4. Selects an eligible job.
5. Locks the selected row.
6. Changes its state to running.
7. Assigns the worker.
8. Establishes a lease.
9. Records the execution attempt.

These operations execute within the calling transaction.

### 11.4 Worker leases

A worker lease represents temporary execution ownership.

The job stores:

- Worker identifier.
- Lease expiration timestamp.
- Current attempt count.

Completion and failure operations validate the worker identifier and lease expiration.

This prevents a worker with an expired lease from completing a job it no longer owns.

A recovery operation identifies expired leases and returns eligible jobs to the pending queue.

### 11.5 Dependencies

A dependent job becomes eligible only when all its parent jobs have completed successfully.

The dependency-validation trigger prevents cycles and cross-tenant dependencies.

The queue-claim function excludes jobs with incomplete dependencies.

For high-volume workflows, dependency graphs may require additional indexes, application-level graph validation and carefully designed locking.

### 11.6 Retry policies

The database stores maximum attempts and current attempts.

When a worker reports failure:

- The current execution attempt is closed.
- The error is recorded.
- The job is returned to pending when retries remain.
- An increasing retry delay is applied.
- The job becomes failed when its retry budget is exhausted.

This separates transient execution failures from permanently failed work.

### 11.7 Auditability

The event table records job submission, execution, completion, failure, retries and lease expiration.

The event log supports:

- Operational investigation.
- Worker-performance analysis.
- Failure-frequency reporting.
- Job lifecycle reconstruction.
- Execution monitoring.

The status-event trigger creates events automatically when job state changes.

## 12. Implementation comparison

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Main abstraction | Coroutine | Promise | Thread and future | CompletableFuture | Persistent job |
| Scheduling | Event loop | Event loop | Worker threads | Executor | Queue consumers |
| Coordination | asyncio | Promise APIs | Mutex and condition variable | Executor and futures | Transactions and locks |
| Concurrency limit | Semaphore | Custom scheduler | Fixed thread pool | Fixed executor | Queue configuration |
| Cancellation | Task cancellation | AbortController | Application-managed | Future cancellation and interruption | Job cancellation |
| Error management | Exceptions | Promise rejection | Future exceptions | Completion exceptions | SQL exceptions and status |
| Persistence | Application-dependent | Application-dependent | Application-dependent | Application-dependent | Relational tables |
| Dependency execution | Task orchestration | Workflow engine | Explicit future composition | CompletableFuture composition | Dependency records |

## 13. Security and production considerations

Asynchronous systems require explicit resource and failure management.

### Resource limits

- Bound task creation.
- Limit concurrent external requests.
- Configure connection pools.
- Set queue capacity.
- Monitor pending-task growth.
- Apply operation deadlines.

### Reliability

- Use bounded retries.
- Introduce exponential backoff and jitter.
- Make externally visible operations idempotent.
- Preserve execution state.
- Handle cancellation.
- Recover abandoned jobs.
- Avoid unobserved task exceptions.

### Security

- Validate external inputs.
- Avoid embedding credentials in task payloads.
- Use least-privilege database accounts.
- Enforce tenant isolation.
- Use authenticated network connections.
- Avoid logging confidential payloads.
- Restrict access to administrative queue operations.

### Observability

Useful metrics include:

- Active tasks.
- Pending tasks.
- Queue wait time.
- Execution duration.
- Success rate.
- Failure rate.
- Timeout count.
- Retry count.
- Cancellation count.
- Worker utilization.
- Expired leases.

Metrics should use consistent timestamps and distinguish queue waiting time from actual execution time.

## 14. Limitations and design boundaries

The five implementations demonstrate different execution models rather than interchangeable implementations of the same runtime.

Python's `asyncio` uses cooperative coroutine scheduling.

JavaScript uses promises and an event-driven runtime.

C++17 uses threads and synchronization primitives because language-level coroutines are not part of that standard.

Java 17 provides executor-based asynchronous composition.

PostgreSQL provides durable job-state management and transaction-based coordination, not an application event loop.

The SQL implementation is an educational queue model. A production queue would also require carefully managed transaction isolation, queue-level capacity enforcement, worker heartbeat policies, dependency-update propagation, dead-letter handling, role permissions and operational retention.

The practical choice depends on whether the dominant requirement is I/O coordination, CPU execution, asynchronous application orchestration or durable distributed job processing.
