# Message Queues: Producers, Consumers, Brokers, Acknowledgments, and Retries

## 1. Introduction

A message queue is a communication mechanism that allows independent software components to exchange information without requiring the sender and receiver to execute at the same time.

A producer creates and publishes a message. A broker accepts the message, manages its routing and storage, and makes it available to consumers. A consumer retrieves the message, performs an application operation, and reports whether processing succeeded.

This arrangement supports asynchronous communication, workload distribution, service isolation, and controlled processing under variable workloads.

The implementation in this repository models a payment-processing system. Payment services publish transaction events, a broker routes them into queues, and workers process them with acknowledgment, retry, and dead-letter mechanisms.

## 2. Architecture and Domain Model

The main components are:

| Component | Responsibility |
|---|---|
| Producer | Creates messages and publishes them to the broker |
| Broker | Accepts, routes, stores, and distributes messages |
| Queue | Maintains messages awaiting delivery or processing |
| Consumer | Retrieves and processes messages |
| Acknowledgment | Confirms successful processing |
| Negative acknowledgment | Reports unsuccessful processing |
| Retry mechanism | Schedules another delivery attempt |
| Dead-letter queue | Isolates messages that cannot be processed successfully |
| Idempotency mechanism | Prevents repeated business effects from duplicate deliveries |

### Architecture

    Payment Service
          |
          | Publish Message
          v
        Broker
          |
          v
       Queue
          |
          | Deliver
          v
       Consumer
          |
          +------ Successful processing
          |                 |
          |                 v
          |                ACK
          |
          +------ Processing failure
                            |
                            v
                           NACK
                            |
                  +---------+---------+
                  |                   |
                  v                   v
               Retry             Dead Letter
                  |
                  v
             Queue Again

The broker and queue have different responsibilities. The broker coordinates message distribution, while a queue maintains the state and ordering of messages associated with a particular workload.

A message is a unit of communication. A delivery is an attempt to transfer that message to a consumer. One message can therefore have several delivery records.

## 3. Message Structure

A message contains information necessary for identification, routing, processing, and recovery.

The implementations use the following conceptual structure:

| Attribute | Purpose |
|---|---|
| Message ID | Uniquely identifies a message |
| Producer ID | Identifies the originating service |
| Routing key | Describes the intended message category |
| Payload | Contains application data |
| Creation time | Records when the message was published |
| Delivery attempt | Tracks processing attempts |
| Maximum attempts | Defines the retry limit |
| Status | Represents the current message lifecycle state |
| Consumer ID | Identifies the consumer holding an active delivery |
| Availability time | Determines when a message can be delivered again |
| Last error | Records the latest processing failure |

The payment scenario uses transaction identifiers, amounts, and customer identifiers.

Message metadata and business payload serve different purposes. Metadata controls message handling, while the payload describes the application event.

A production implementation should validate payload structure, limit message size, reject malformed data, and avoid placing passwords, access tokens, or unnecessary personal information in messages.

## 4. Producers

A producer is an application component that creates and publishes messages.

Examples include:

- An order service publishing an order-created event.
- A payment service publishing a payment-completed event.
- A notification service publishing a delivery request.
- An inventory service publishing a stock-update event.

### Producer workflow

1. A business operation generates an event.
2. The producer creates a message identifier.
3. It assigns a routing key.
4. It serializes the application payload.
5. It submits the message to the broker.
6. The broker accepts or rejects publication.
7. The producer records the publication result.

A successful publication indicates that the broker accepted the message. It does not mean that a consumer has processed it.

This distinction is important when designing business workflows. A payment service must not interpret broker acceptance as confirmation that downstream accounting or notification operations have completed.

### Producer reliability

Producer-side reliability includes:

- Stable message identifiers.
- Publication retries.
- Idempotency keys.
- Payload validation.
- Bounded message sizes.
- Durable broker publication.
- Transactional outbox patterns when publication follows a database transaction.

The Python and JavaScript implementations generate unique message identifiers. The PostgreSQL implementation also supports producer-specific idempotency keys.

An idempotency key identifies a publication request that must not create multiple independent messages when the producer repeats the same request.

## 5. Brokers

A broker coordinates communication between producers and consumers.

Its responsibilities commonly include:

- Queue declaration.
- Message acceptance.
- Routing.
- Message storage.
- Consumer distribution.
- Delivery tracking.
- Acknowledgment processing.
- Retry handling.
- Dead-letter routing.
- Operational monitoring.

A broker may support multiple routing models.

| Routing model | Description |
|---|---|
| Point-to-point | A message is delivered to one competing consumer |
| Publish-subscribe | An event is distributed to multiple subscriptions |
| Topic-based | Routing depends on topic names or patterns |
| Direct routing | Routing depends on an exact routing key |
| Fanout routing | A published message is distributed to all bindings |

The implementations use named queues and routing keys. The routing key is retained as message metadata so that routing rules can be extended independently of business payload structure.

### Broker and queue distinction

A broker can manage many queues. Each queue can have its own capacity, retry policy, and consumer population.

For example:

| Queue | Workload | Consumer |
|---|---|---|
| payments | Payment processing | Payment worker |
| orders | Order fulfillment | Order worker |
| notifications | Notification delivery | Notification worker |

This separation prevents one workload from directly controlling the processing schedule of another.

## 6. Consumers

A consumer retrieves messages and executes application logic.

A consumer normally follows this sequence:

1. Request an available message.
2. Receive the message and its delivery identifier.
3. Validate the payload.
4. Execute the business operation.
5. Acknowledge successful processing.
6. Reject unsuccessful processing.
7. Allow the retry or dead-letter mechanism to determine the next state.

Consumers should not acknowledge a message before the required business operation has succeeded.

If a consumer acknowledges a message before completing its database transaction, a crash can result in lost business work.

If a consumer completes the operation but fails before sending the acknowledgment, the broker may deliver the message again.

This second condition is a central reason for designing consumers to be idempotent.

### Consumer concurrency

Multiple consumers can process messages from the same queue.

Concurrency increases throughput when tasks are independent, but it introduces additional considerations:

- Shared resource contention.
- Database connection limits.
- Duplicate business operations.
- Message ordering.
- Rate limits.
- Worker failure.
- Uneven processing times.

The JavaScript implementation uses asynchronous processing and configurable worker concurrency.

The PostgreSQL implementation uses row-level locking with `FOR UPDATE SKIP LOCKED` to prevent concurrent workers from claiming the same message.

## 7. Message Lifecycle and State Management

The message lifecycle is explicitly represented in all implementations.

| State | Meaning |
|---|---|
| READY | Message is available for delivery |
| IN_FLIGHT | A consumer currently owns the delivery |
| ACKNOWLEDGED | Successful processing has been confirmed |
| RETRY_PENDING | Another delivery is scheduled |
| DEAD_LETTERED | Automatic processing has stopped |

### State transitions

    READY
      |
      v
    IN_FLIGHT
      |
      +----------------------+
      |                      |
      v                      v
    ACKNOWLEDGED          Processing Failure
                             |
                             v
                           NACK
                             |
                  +----------+----------+
                  |                     |
                  v                     v
             RETRY_PENDING        DEAD_LETTERED
                  |
                  v
                READY

A message should not be treated as simultaneously ready and in flight.

The database enforces this distinction through a check constraint requiring an active consumer and delivery timestamp for `IN_FLIGHT` messages.

The other implementations maintain separate ready, in-flight, and retry collections.

This separation reduces accidental duplicate delivery within a running process.

## 8. Acknowledgments

An acknowledgment, commonly abbreviated as ACK, is a confirmation that a consumer has successfully processed a delivered message.

The acknowledgment communicates a delivery outcome to the broker.

### ACK workflow

1. A consumer receives a message.
2. The consumer executes the required operation.
3. The operation completes successfully.
4. The consumer sends an acknowledgment.
5. The broker marks the delivery as completed.
6. The message is no longer eligible for normal delivery.

An acknowledgment is associated with a specific message and delivery owner.

The implementations validate consumer ownership before accepting an ACK. A consumer cannot acknowledge a message currently assigned to another consumer.

### Acknowledgment modes

| Mode | Description |
|---|---|
| Automatic acknowledgment | The system acknowledges delivery without waiting for application confirmation |
| Manual acknowledgment | The consumer explicitly confirms successful processing |
| Individual acknowledgment | Confirms a specific delivery |
| Cumulative acknowledgment | Confirms a sequence of deliveries where supported |

Manual acknowledgment provides better control over application-level completion.

Automatic acknowledgment can be appropriate for low-risk workloads, but it increases the possibility of losing work if the consumer fails immediately after receiving a message.

### Duplicate acknowledgment

A message that has already been acknowledged should not be acknowledged again as if it were still in flight.

The implementations reject acknowledgments for messages that are not currently assigned to the requesting consumer.

## 9. Negative Acknowledgments

A negative acknowledgment, commonly abbreviated as NACK, indicates that processing has failed or that a message cannot currently be handled.

A consumer may reject a message because of:

- Temporary database unavailability.
- External service failure.
- Rate limiting.
- Invalid business conditions.
- Unsupported payload structure.
- Processing exceptions.

A NACK can result in requeueing, delayed retry, or dead-letter routing.

A temporary network failure may justify another attempt. A permanently invalid payload may be better isolated immediately.

Repeatedly retrying permanent failures wastes processing resources and can create a backlog.

## 10. Retries and Backoff

A retry is another delivery attempt after a previous processing attempt has failed.

A retry policy defines:

- Maximum attempts.
- Delay between attempts.
- Delay growth strategy.
- Retryable error categories.
- Final failure handling.

### Exponential backoff

The implementations support exponential backoff.

The retry delay is calculated as:

\[
D_n = \min(D_{\max},D_0 \times 2^{n-1})
\]

Where:

- \(D_n\) is the delay before retry attempt \(n\).
- \(D_0\) is the initial delay.
- \(D_{\max}\) is the maximum permitted delay.
- \(n\) is the current attempt number.

For an initial delay of one second and a maximum delay of thirty seconds:

| Attempt | Delay |
|---|---:|
| 1 | 1 second |
| 2 | 2 seconds |
| 3 | 4 seconds |
| 4 | 8 seconds |
| 5 | 16 seconds |
| 6 | 30 seconds |

The maximum retry limit prevents a permanently failing message from circulating indefinitely.

### Retry scheduling

A message with a future availability time should not be delivered immediately.

The broker or queue checks the availability timestamp and moves eligible messages back into the ready state.

The Python and Java implementations maintain retry collections. The JavaScript implementation uses asynchronous processing and retry timestamps. The PostgreSQL implementation stores availability timestamps and uses database queries to select eligible messages.

### Retry classification

| Failure | Suggested handling |
|---|---|
| Temporary network failure | Retry |
| Database temporarily unavailable | Retry |
| External API rate limit | Delayed retry |
| Malformed payload | Dead-letter |
| Missing required business identifier | Dead-letter |
| Permanently rejected business operation | Stop automatic retries |
| Worker crash | Visibility timeout recovery |

The classification should be based on application requirements rather than applying the same retry behavior to every exception.

## 11. Dead-Letter Queues

A dead-letter queue, or DLQ, stores messages that cannot be processed successfully through the normal delivery workflow.

Common reasons include:

- Maximum retry attempts exhausted.
- Invalid message structure.
- Permanent application failure.
- Repeated processing timeouts.
- Unsupported message version.

Dead-lettering prevents repeatedly failing messages from blocking normal processing.

### Dead-letter workflow

1. A message is delivered.
2. Processing fails.
3. The retry policy is evaluated.
4. The attempt limit is reached or retry is prohibited.
5. The message is marked as dead-lettered.
6. The failure reason is recorded.
7. An operator or recovery process investigates the message.

A dead-letter record should preserve the original message identifier, queue, final attempt count, and failure reason.

### Dead-letter replay

Replay returns a previously failed message to an eligible processing state.

Replay should be controlled because the original failure may still exist.

Before replaying a message, an operator should verify:

- The underlying failure has been addressed.
- The message payload remains valid.
- Reprocessing will not create duplicate business effects.
- The target queue is appropriate.
- The replay is recorded for audit purposes.

The PostgreSQL implementation includes a dead-letter replay function.

## 12. Visibility Timeouts and Consumer Failure

A visibility timeout defines how long a delivered message remains unavailable to other consumers while its current consumer is processing it.

The mechanism helps recover messages when consumers crash or become unavailable.

Example:

1. Worker A receives a message.
2. The broker marks it in flight.
3. Worker A stops responding.
4. The visibility timeout expires.
5. The broker or recovery process detects the expired delivery.
6. The message becomes eligible for another attempt.

The timeout should be appropriate for expected processing duration.

A timeout that is too short can cause unnecessary duplicate deliveries while a legitimate operation is still running.

A timeout that is too long delays recovery after a worker failure.

Production systems may use heartbeat-based delivery extensions or lease renewal to support long-running tasks.

## 13. At-Most-Once, At-Least-Once, and Exactly-Once Semantics

Delivery guarantees describe the relationship between publication, delivery, and processing.

| Guarantee | Meaning | Main trade-off |
|---|---|---|
| At-most-once | A message is delivered zero or one time | Messages may be lost |
| At-least-once | A message is delivered one or more times until completion | Duplicate deliveries are possible |
| Exactly-once processing | A business effect occurs once despite repeated delivery attempts | Requires coordinated state and careful transaction design |

### At-most-once

A message may be lost if the consumer or communication channel fails after delivery but before successful processing.

### At-least-once

The message remains eligible for redelivery until the broker receives a valid acknowledgment or the retry policy terminates processing.

The implementations use this general delivery model.

A consumer may receive the same message more than once, so application-level idempotency is required.

### Exactly-once distinction

Exactly-once delivery and exactly-once business processing are not interchangeable.

A broker may prevent duplicate publication or delivery under specific conditions, but a consumer can still repeat an external business operation after an uncertain failure.

Reliable business processing generally requires:

- Stable message identifiers.
- Idempotency keys.
- Transactional database operations.
- Deduplication records.
- Atomic state updates.
- Appropriate outbox and inbox patterns.

The Python, JavaScript, and Java implementations demonstrate idempotency stores. The PostgreSQL implementation provides producer-specific publication idempotency records.

The in-memory idempotency examples are suitable for demonstrating the mechanism, but persistent production idempotency records are necessary across process restarts.

## 14. Implementation 1: Python

The Python program models a bounded message queue using standard-library data structures.

### Main components

| Class | Responsibility |
|---|---|
| `Message` | Stores message metadata and lifecycle state |
| `MessageQueue` | Manages ready, in-flight, retry, and terminal messages |
| `Broker` | Declares and retrieves named queues |
| `Producer` | Publishes messages |
| `Consumer` | Processes and acknowledges messages |
| `QueueMetrics` | Tracks queue operations |
| `IdempotentPaymentHandler` | Prevents duplicate business transactions |

### Important mechanisms

- `deque` supports efficient FIFO insertion and removal.
- Dictionaries provide direct lookup of in-flight messages.
- Sets track completed transaction identifiers.
- Dataclasses provide structured message and metrics models.
- Enums constrain message states.
- `RLock` protects queue state during concurrent access.
- Custom exceptions distinguish capacity and acknowledgment failures.

The `receive()` operation transfers a message from the ready collection to the in-flight collection.

The `acknowledge()` operation validates ownership and records successful completion.

The `reject()` operation either schedules another attempt or moves the message into dead-letter storage.

The capacity demonstration shows that publication is rejected when the queue reaches its configured limit.

The visibility recovery method demonstrates how an abandoned delivery can be returned to processing.

### Limitations

The Python implementation is an in-memory simulation. It does not provide persistent message storage, distributed locking, process-independent recovery, or network-based communication.

Its locking mechanism protects one process, not multiple independent broker instances.

## 15. Implementation 2: JavaScript

The JavaScript implementation uses Node.js and an event-driven architecture.

### Main components

| Class | Responsibility |
|---|---|
| `Message` | Validates and stores message data |
| `MessageQueue` | Manages queue state and emits events |
| `Broker` | Maintains named queues |
| `Producer` | Publishes messages asynchronously |
| `Consumer` | Processes messages using asynchronous handlers |
| `IdempotencyStore` | Tracks completed business operations |
| `PaymentService` | Performs idempotent payment processing |

### Event-driven design

`MessageQueue` extends `EventEmitter`.

It publishes operational events such as:

- `published`
- `delivered`
- `acknowledged`
- `retryScheduled`
- `retryReady`
- `deadLettered`
- `closed`

This allows monitoring and other application components to respond without tightly coupling themselves to the queue implementation.

### Asynchronous processing

The consumer uses `async` and `await` to execute message handlers.

Configurable concurrency allows several messages to be processed simultaneously.

`Promise.all()` coordinates worker operations.

The implementation also uses Node.js timers for retry scheduling and asynchronous polling.

### Data validation

The message constructor validates:

- Message identifiers.
- Routing keys.
- Attempt limits.
- Payload structure.
- Payload serialization.
- Maximum payload size.

The payload is copied through JSON serialization to prevent later mutation of the original object from silently changing the published message.

### Limitations

The queue and idempotency store exist only in memory. The event emitter provides process-local events, not distributed event delivery.

A production implementation would require persistent storage, coordinated consumer ownership, durable acknowledgment state, and recovery after application restarts.

## 16. Implementation 3: C++17

The C++ implementation focuses on explicit domain modeling, efficient data structures, and controlled state transitions.

### Main components

| Component | Responsibility |
|---|---|
| `Message` | Represents an individual message |
| `MessageQueue` | Maintains message lifecycle and delivery state |
| `Broker` | Manages named queues |
| `Producer` | Generates and publishes message identifiers |
| `PaymentConsumer` | Represents a business consumer |
| `QueueMetrics` | Tracks processing statistics |
| `Delivery` | Records delivery ownership and attempt information |

### Data structures

| Data structure | Purpose |
|---|---|
| `std::queue` | FIFO ready-message processing |
| `std::unordered_map` | Fast message and in-flight lookup |
| `std::vector` | Retry, completed, and dead-letter collections |
| `std::set` | Tracks processed business transaction identifiers |
| `std::optional` | Represents the absence of an available message |

The ready queue supports constant-time front removal.

Hash-based message lookup has average constant-time complexity.

Retry promotion scans the pending retry collection, so its cost is proportional to the number of scheduled retries.

The implementation uses `std::chrono::steady_clock` for measuring elapsed delivery time.

### State and ownership

A delivery contains the message identifier, consumer identifier, and attempt number.

The acknowledgment operation validates that the requesting consumer owns the active delivery.

A consumer that does not own a message cannot acknowledge it.

The implementation demonstrates capacity restrictions, message rejection, retry handling, and dead-letter storage.

The business processing example uses a separate transaction identifier set to illustrate deduplication.

### Design trade-offs

The implementation uses standard containers without an external serialization or messaging library.

This makes the program self-contained, but the payload is represented as a string rather than a production serialization format.

The queue is not thread-safe. A production concurrent implementation would require mutexes, condition variables, carefully defined lock boundaries, and safe coordination between delivery and acknowledgment operations.

## 17. Implementation 4: Java 17

The Java implementation introduces enterprise-oriented domain types and service boundaries.

### Domain types

| Type | Purpose |
|---|---|
| `QueueConfiguration` | Immutable queue configuration |
| `MessagePayload` | Validated payment payload |
| `Message` | Mutable lifecycle state with immutable message identity |
| `Delivery` | Immutable delivery information |
| `QueueMetrics` | Immutable operational metrics |
| `QueueSnapshot` | Queue reporting structure |
| `MessageHandler` | Processing interface |
| `ProcessingResult` | Business processing outcome |

Java records represent immutable data structures and configuration objects.

Enums constrain supported lifecycle states.

The `MessageHandler` interface separates application processing from message transport.

### Service architecture

The main services are:

- `Broker`
- `ProducerService`
- `PaymentConsumerService`
- `IdempotencyService`
- `MessageQueue`

The broker manages named queue instances through a concurrent map.

The queue uses a `ReentrantLock` to coordinate changes to its internal collections.

Atomic counters track operational statistics.

### Policy behavior

The queue configuration defines:

- Maximum capacity.
- Maximum processing attempts.
- Initial retry delay.
- Maximum retry delay.
- Visibility timeout.

The retry service applies exponential backoff with a maximum delay.

The consumer validates application-level processing through the payment payload model.

The idempotency service ensures that repeated transaction identifiers do not produce repeated successful operations within its current in-memory lifetime.

### Enterprise considerations

A production Java implementation should separate transport concerns from application transactions.

The consumer should execute the business operation and persist its idempotency record within an appropriate transaction boundary before acknowledging the message.

The in-memory implementation demonstrates the domain and service boundaries but does not replace a durable distributed broker.

## 18. Implementation 5: PostgreSQL

The PostgreSQL implementation models the message queue workflow as a relational database system.

It uses schema-qualified objects under `message_system`.

### Relational model

    producers
        |
        v
    messages <------ queues
        |
        +------ consumers
        |
        +------ deliveries
        |
        +------ idempotency_records
        |
        +------ dead_letters

### Database tables

| Table | Responsibility |
|---|---|
| `producers` | Registered message publishers |
| `queues` | Queue configuration and capacity |
| `consumers` | Registered queue workers |
| `messages` | Message payloads and lifecycle states |
| `deliveries` | Individual processing attempts |
| `idempotency_records` | Duplicate publication prevention |
| `dead_letters` | Terminal processing failures |

### Integrity constraints

The database enforces:

- Unique producer names.
- Unique queue names.
- Positive queue capacity.
- Positive maximum attempts.
- Valid message payload types.
- Valid routing keys.
- Valid delivery attempt numbers.
- Unique message-attempt combinations.
- Consumer ownership for in-flight messages.
- Valid delivery completion state.

These constraints prevent several classes of invalid database state.

### Atomic message claiming

The `claim_message()` function uses `FOR UPDATE SKIP LOCKED`.

This is particularly important for concurrent workers.

When multiple workers request messages simultaneously, PostgreSQL locks selected message rows. Other workers skip rows already claimed by an active transaction.

The function:

1. Validates consumer registration and status.
2. Finds an eligible message.
3. Locks its row.
4. Changes its state to `IN_FLIGHT`.
5. Increments the attempt counter.
6. Records the consumer.
7. Creates a delivery-history record.
8. Returns the message details.

The claim operation must run inside a transaction. The caller should commit after receiving the result.

### Acknowledgment processing

`acknowledge_message()` verifies that the message is in flight and belongs to the requesting consumer.

It changes the message state and completes the corresponding delivery record.

These operations are transactional.

### Retry processing

`reject_message()` records the failure and calculates the next availability time.

The calculation uses exponential backoff.

If the retry limit has been exhausted, the message is marked as `DEAD_LETTERED` and its failure information is recorded.

### Visibility timeout recovery

`recover_expired_messages()` identifies deliveries that have exceeded their configured visibility timeout.

The function records the timeout outcome and either:

- Schedules another attempt.
- Marks the message as dead-lettered.

`FOR UPDATE SKIP LOCKED` also allows multiple recovery workers to process different expired messages concurrently.

### Idempotent publication

The `idempotency_records` table enforces uniqueness on:

- Producer ID.
- Idempotency key.

Repeated publication requests using the same producer and key return the existing message identifier.

This protects against duplicate publication requests.

### Views and reporting

The SQL file includes:

| Database object | Purpose |
|---|---|
| `queue_metrics` | Aggregated queue state |
| `consumer_load` | Active deliveries per consumer |
| `queue_is_eligible()` | Consumer and queue eligibility |
| Queue summary CTE | Ready, active, and retry counts |
| Delivery performance query | Success, rejection, timeout, and duration |
| Dead-letter query | Failed message inspection |
| Success-rate query | Delivery outcome reporting |

### Database transaction boundaries

Message claiming, acknowledgment, and rejection should each execute within a database transaction.

The database can atomically update its own message and delivery records.

It cannot automatically guarantee that an external payment gateway operation and a database acknowledgment occur as one atomic operation.

For such workflows, a transactional outbox/inbox design is appropriate.

## 19. Reliability and Failure Handling

Reliable message processing requires separate handling of publication, delivery, processing, and acknowledgment failures.

| Failure condition | Possible effect | Control |
|---|---|---|
| Producer crashes before publication | Event is not published | Transactional outbox |
| Broker unavailable | Publication fails | Producer retry and durable broker storage |
| Queue reaches capacity | Publication is rejected | Backpressure and capacity planning |
| Consumer crashes after delivery | Message remains unacknowledged | Visibility timeout |
| Consumer fails during processing | Business operation may be incomplete | Retry or dead-letter policy |
| ACK is lost | Message may be delivered again | Idempotent processing |
| Retry limit exhausted | Repeated processing stops | Dead-letter queue |
| Duplicate publication | Multiple messages may exist | Idempotency key |
| Invalid payload | Processing repeatedly fails | Validation and failure classification |
| Queue backlog grows | Processing latency increases | Scaling and monitoring |

The appropriate response depends on whether the failure is temporary, permanent, or uncertain.

## 20. Ordering and Message Priorities

Message queues do not automatically guarantee global processing order.

A FIFO queue can preserve the order in which messages enter a particular queue, but parallel consumers may complete their operations in a different order.

For example:

- Transaction A enters before transaction B.
- Worker A processes transaction A slowly.
- Worker B processes transaction B quickly.
- Transaction B completes first.

If ordering matters, the system must enforce it explicitly.

Possible approaches include:

- Single-consumer processing.
- Partitioning by business identifier.
- Sequence numbers.
- Per-entity ordering.
- Ordered event processing.
- Restricting concurrent processing for related messages.

The implementations demonstrate FIFO retrieval but do not guarantee completion order under concurrent consumers.

Message priority is another independent concern. A production broker may support priority levels, but priority processing can starve low-priority messages if high-priority traffic remains continuously available.

## 21. Performance and Scalability

Queue performance depends on publication rate, delivery rate, processing time, message size, and storage behavior.

### Important performance measures

| Metric | Interpretation |
|---|---|
| Publish rate | Messages accepted per second |
| Delivery rate | Messages delivered per second |
| Processing rate | Messages successfully processed per second |
| Queue depth | Number of messages awaiting processing or retry |
| Queue age | Time the oldest message has remained pending |
| Acknowledgment latency | Time between delivery and ACK |
| Retry rate | Proportion of messages requiring another attempt |
| Dead-letter rate | Proportion of messages reaching terminal failure |
| Consumer utilization | Active work relative to worker capacity |

### Queue growth

Let:

- \(\lambda\) represent the message arrival rate.
- \(\mu\) represent the total processing rate.

When arrival rate consistently exceeds processing rate:

\[
\lambda > \mu
\]

the queue backlog grows.

A stable system needs sufficient processing capacity for its expected workload, including traffic bursts and failure recovery.

### Scaling approaches

- Add consumers for parallel workloads.
- Partition messages by business key.
- Separate unrelated workload queues.
- Increase broker capacity.
- Use bounded producer buffering.
- Apply backpressure.
- Tune message batch sizes.
- Optimize database claim operations.
- Monitor oldest-message age.

Adding consumers does not always improve throughput. Database contention, external API limits, and CPU-intensive operations can become bottlenecks.

### Database indexing

The PostgreSQL implementation includes indexes for:

- Queue and availability-time lookup.
- In-flight message recovery.
- Producer history.
- Delivery history.
- Dead-letter reporting.
- Routing-key lookup.

Partial indexes reduce the number of rows indexed for frequently queried message states.

## 22. Security and Operational Governance

A message broker handles application data and should be treated as a security-sensitive component.

Important controls include:

### Authentication

Producers and consumers should authenticate before accessing broker operations.

### Authorization

Access should be restricted by queue and operation.

A payment producer should not automatically receive permission to consume every queue.

### Encryption

Use encrypted communication between services and brokers.

Sensitive payloads should be encrypted at rest where required.

### Payload validation

Validate message structure, size, type, and business constraints before processing.

Do not trust data solely because it originated from an internal service.

### Replay protection

Idempotency keys and message identifiers help prevent unintended duplicate business effects.

### Auditability

Maintain records of:

- Producer identity.
- Consumer identity.
- Publication time.
- Delivery attempts.
- Acknowledgment outcome.
- Failure reason.
- Dead-letter events.
- Administrative replay actions.

### Retention

Completed messages and delivery records should have defined retention periods.

Unrestricted retention increases storage costs and may create unnecessary data exposure.

### Observability

Monitor queue depth, message age, retry frequency, acknowledgment failures, and dead-letter volume.

A rising retry rate may indicate a downstream service failure rather than insufficient consumer capacity.

## 23. Practical Design Decisions

The five implementations intentionally use different engineering approaches.

| Language | Main perspective | Key mechanism |
|---|---|---|
| Python | Workflow simulation | Dataclasses, collections, exceptions, locks |
| JavaScript | Event-driven processing | EventEmitter, Promises, async consumers |
| C++17 | Data structures and state control | STL containers, ownership validation, optional values |
| Java 17 | Enterprise domain modeling | Records, services, interfaces, locks, typed policies |
| PostgreSQL | Durable relational workflow | Constraints, functions, transactions, row locking |

The implementations share the same core lifecycle concepts, but their internal structures are not identical.

Python emphasizes an accessible queue simulation.

JavaScript emphasizes asynchronous events and consumer concurrency.

C++17 emphasizes explicit data structures and message ownership.

Java 17 emphasizes typed domain models and service separation.

PostgreSQL emphasizes persistent state, relational integrity, and atomic database operations.

## 24. Limitations of the Implementations

These programs are learning implementations rather than production distributed brokers.

| Area | Current implementation | Production requirement |
|---|---|---|
| Persistence | In-memory in application examples | Durable broker storage |
| Distribution | Single-process broker simulations | Distributed broker cluster |
| Recovery | Local retry and timeout logic | Coordinated recovery across nodes |
| Ordering | FIFO retrieval | Explicit partition and ordering policy |
| Idempotency | In-memory stores in application examples | Persistent transactional deduplication |
| Security | Basic validation and ownership checks | Authentication, authorization, encryption |
| Monitoring | Queue counters and reports | Centralized metrics and alerting |
| Scaling | Configurable consumer concurrency | Distributed workload management |
| Serialization | JSON-like objects or strings | Versioned schema and compatibility controls |
| Business transactions | Demonstration operations | Transactional outbox/inbox or equivalent coordination |

The PostgreSQL implementation provides persistent relational storage, but a database-backed queue is not automatically equivalent to a dedicated messaging broker.

Database-backed messaging can be appropriate for moderate workloads and systems where transactional consistency with application data is important.

A dedicated broker may be more appropriate for high-throughput event distribution, large consumer populations, partitioned workloads, and independent service scaling.

## 25. Execution and Verification

### Python

- Save the first source file as `message_queue.py`.
- Run using Python 3.10 or later.
- The implementation uses only the Python standard library.
- The program generates `queue_metrics.json`.

### JavaScript

- Save the second source file as `message-queue.js`.
- Run using Node.js 18 or later.
- No npm installation is required.
- The program generates `queue-metrics.json`.

### C++17

- Save the third source file as `message_queue.cpp`.
- Compile using a C++17-compatible compiler.
- The program uses only the standard library.

### Java 17

- Save the fourth source file as `MessageQueueEnterprise.java`.
- Compile and run using Java 17.

### PostgreSQL

- Execute the fifth source file using PostgreSQL 15 or later.
- The script creates the `message_system` schema.
- The execution role requires permission to create schemas, tables, functions, types, indexes, and views.
- The role also requires access to the UUID generation function used by the script.

The SQL script includes sample producers, queues, consumers, publications, claims, acknowledgments, negative acknowledgments, and reporting queries.

## 26. Technical Learning Outcomes

The implementations demonstrate the following distinctions:

| Concept | What it represents |
|---|---|
| Publication | Acceptance of a message by the messaging system |
| Delivery | Transfer of a message to a consumer |
| Processing | Execution of application logic |
| Acknowledgment | Confirmation of successful processing |
| Negative acknowledgment | Notification of unsuccessful processing |
| Retry | Another scheduled delivery attempt |
| Visibility timeout | Recovery mechanism for abandoned deliveries |
| Dead-lettering | Isolation of terminal processing failures |
| Idempotency | Prevention of duplicate business effects |
| Backpressure | Control of message production when capacity is constrained |
| Consumer concurrency | Parallel processing of independent messages |
| Queue persistence | Preservation of message state across failures |
| Transactional outbox | Coordination between business data changes and message publication |
| Transactional inbox | Coordination between message consumption and business processing |

These concepts are related but not interchangeable.

A producer publishes a message. A broker manages its distribution. A consumer processes the message. An acknowledgment reports successful completion. A retry handles recoverable failure. A dead-letter mechanism isolates messages that cannot be processed automatically.

Reliable asynchronous systems depend on managing these mechanisms as one coordinated workflow.
