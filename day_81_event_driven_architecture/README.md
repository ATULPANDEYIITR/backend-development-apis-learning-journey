# Event-Driven Architecture

## 1. Domain Overview

Event-Driven Architecture (EDA) is a software architecture in which components communicate through events representing facts about activities that have occurred.

An event producer publishes an event without requiring direct knowledge of every component that will process it. Event consumers subscribe to relevant event types and independently perform their responsibilities.

For example, when an order is created, several independent services may respond:

- Inventory Service reserves stock.
- Payment Service authorizes payment.
- Notification Service informs the customer.
- Analytics Service records business activity.

The producer does not need to invoke each service directly.

This reduces direct dependencies between services and supports independently deployable business components.

## 2. Core Architectural Components

| Component | Responsibility |
|---|---|
| Event | Represents an occurrence in the system |
| Event producer | Creates and publishes events |
| Event consumer | Processes events |
| Event broker | Routes events to interested consumers |
| Event schema | Defines the event structure |
| Schema registry | Maintains event schema versions |
| Subscription | Connects consumers to event types |
| Event store | Retains published events |
| Delivery record | Tracks an event's delivery to a consumer |
| Dead-letter queue | Stores deliveries that repeatedly fail |
| Correlation ID | Connects related events across services |
| Idempotency key | Prevents duplicate business processing |

### Architectural relationship

Producer
→ Event
→ Broker
→ Subscription
→ Consumer
→ Business Operation
→ Processing Result

The broker separates publication from consumption. Consumers can operate independently, subject to broker availability and delivery guarantees.

## 3. Events and Event Structure

An event describes something that has already happened.

Examples:

- `OrderCreated`
- `PaymentAuthorized`
- `PaymentFailed`
- `InventoryReserved`
- `ShipmentDispatched`
- `CustomerRegistered`

An event should represent a business fact rather than a command requesting an operation.

| Event | Meaning |
|---|---|
| `OrderCreated` | An order was created |
| `PaymentCompleted` | A payment completed |
| `InventoryReserved` | Inventory was reserved |
| `ShipmentDispatched` | A shipment was dispatched |

A typical event contains:

| Field | Purpose |
|---|---|
| `event_id` | Globally unique event identifier |
| `event_type` | Name of the event |
| `version` | Schema version |
| `producer` | Originating component |
| `occurred_at` | Time of the original occurrence |
| `correlation_id` | Identifier connecting related operations |
| `causation_id` | Identifier of the event or operation that caused this event |
| `payload` | Business information |
| `metadata` | Additional processing information |

The event identifier distinguishes individual event instances. The correlation identifier connects multiple events belonging to the same business workflow.

These identifiers serve different purposes and should not be treated as interchangeable.

## 4. Event Producers

An event producer creates and publishes events after a relevant business operation occurs.

In the implemented order-processing scenario, `OrderProducer` publishes `OrderCreated`.

The producer performs:

1. Input validation.
2. Event type selection.
3. Schema version selection.
4. Event identifier assignment.
5. Correlation identifier assignment.
6. Payload construction.
7. Publication to the broker.

The producer does not directly execute inventory reservation, payment authorization, or notification delivery.

### Producer responsibilities

- Publish valid event structures.
- Use stable event type names.
- Assign unique event identifiers.
- Include relevant correlation information.
- Avoid publishing incomplete business facts.
- Handle publication failures.
- Prevent duplicate publication where business operations require it.

### Transactional publication

A significant production problem occurs when a business transaction succeeds but event publication fails.

For example:

1. An order is saved in the database.
2. The application attempts to publish `OrderCreated`.
3. The broker becomes unavailable.
4. The order exists, but downstream services never receive the event.

The transactional outbox pattern addresses this problem.

The application writes the business record and an outbox event in the same database transaction. A separate publisher reads the outbox and publishes pending events.

This prevents the database transaction and event publication intent from becoming inconsistent.

## 5. Event Consumers

A consumer subscribes to an event type and executes a business operation when the event is delivered.

The implementations contain four example consumer responsibilities.

| Consumer | Responsibility |
|---|---|
| InventoryConsumer | Reserve inventory |
| PaymentConsumer | Record payment authorization |
| NotificationConsumer | Create customer notifications |
| AnalyticsConsumer | Collect business activity |

Each consumer has an independent processing responsibility.

A consumer should not assume that another consumer has completed its operation.

For example, successful inventory reservation does not prove that payment authorization succeeded.

### Independent processing

One event can be delivered to several consumers.

OrderCreated
- InventoryConsumer
- PaymentConsumer
- NotificationConsumer
- AnalyticsConsumer

A failure in one consumer should not automatically prevent the other consumers from processing the event.

This is an important distinction between independent event consumption and a single sequential business workflow.

## 6. Event Brokers and Delivery

An event broker receives events and routes them to subscribers.

Its responsibilities include:

- Event publication.
- Subscription management.
- Event routing.
- Delivery coordination.
- Retry handling.
- Delivery tracking.
- Failure isolation.
- Dead-letter management.

The Python and JavaScript implementations use in-memory brokers to demonstrate these responsibilities.

The C++ implementation uses a domain-oriented broker with explicit consumer registration and delivery results.

The Java implementation separates broker behavior from consumer contracts through an interface.

The PostgreSQL implementation models durable event publication and consumer delivery records.

### Publish-subscribe pattern

Publish-subscribe allows multiple consumers to receive the same event independently.

For example:

`OrderCreated`

→ Inventory Service

→ Payment Service

→ Notification Service

Each subscriber maintains its own processing state.

This differs from competing consumers, where several workers belong to one consumer group and distribute messages among themselves.

A competing-consumer group generally processes each message once per group rather than once per worker.

## 7. Event Schemas and Schema Registry

An event schema defines the structure and permitted values of an event payload.

For example, `OrderCreated` version 1 contains:

| Field | Type | Required |
|---|---|---|
| `order_id` | String | Yes |
| `customer_id` | String | Yes |
| `amount` | Number | Yes |

A later version may introduce a currency field.

| Field | Version 1 | Version 2 |
|---|---|---|
| `order_id` | Required | Required |
| `customer_id` | Required | Required |
| `amount` | Required | Required |
| `currency` | Not present | Required |

The schema registry maintains the versions and allows producers and consumers to work against explicitly defined contracts.

### Schema validation

Validation checks:

- Required fields.
- Field types.
- Unknown fields.
- Numeric constraints.
- Event type.
- Schema version.
- Payload structure.

The Python implementation uses `EventSchema` and `SchemaRegistry`.

The JavaScript implementation uses a `Map`-based registry and runtime type validation.

The C++ implementation uses field validation functions.

The Java implementation uses `FieldDefinition` records and immutable schema definitions.

PostgreSQL stores JSONB schema definitions and validates payload structures through a database function.

### Schema compatibility

Schema evolution requires careful management.

| Compatibility | Meaning |
|---|---|
| Backward | New consumers can read older event data |
| Forward | Older consumers can read newer event data |
| Full | Both backward and forward compatibility |
| Breaking | A change can prevent existing producers or consumers from working |

Adding an optional field is generally safer than renaming or removing an existing required field.

Changing a field's meaning without changing its name is particularly dangerous because structural validation may still succeed.

A schema version identifies the contract. It does not automatically guarantee compatibility.

## 8. Event Delivery Semantics

Event delivery semantics describe how messages are delivered and processed.

### At-most-once delivery

An event is delivered zero or one time.

A failure can result in message loss if the event is not successfully processed.

### At-least-once delivery

An event is delivered one or more times until successful processing or a configured failure condition.

Duplicate deliveries are possible.

The implementations demonstrate at-least-once-oriented retry behavior and consumer-side idempotency.

### Exactly-once processing

Exactly-once behavior requires careful control over message delivery and business side effects.

A broker acknowledging a message does not automatically guarantee that a payment, database update, or external API call occurred exactly once.

For example:

1. A payment consumer authorizes a payment.
2. The consumer crashes before acknowledging the event.
3. The broker delivers the event again.
4. The consumer receives the same payment instruction.

A stable idempotency key and an atomic business-state update are needed to prevent duplicate authorization.

For external payment providers, the provider's idempotency mechanism must also be considered.

The examples demonstrate delivery-level idempotency, but production systems must extend this protection to actual business transactions.

## 9. Retry Handling and Dead-Letter Queues

Temporary consumer failures should not necessarily result in permanent event loss.

Common failure causes include:

- Network interruption.
- Database unavailability.
- External API timeouts.
- Temporary service overload.
- Dependency failures.
- Invalid business data.

The implementations retry failed deliveries with bounded exponential backoff.

The delay increases between attempts, reducing repeated pressure on an unavailable service.

A typical pattern is:

Attempt 1 → Short delay

Attempt 2 → Longer delay

Attempt 3 → Longer delay

Maximum attempts reached → Dead-letter queue

### Dead-letter queues

A dead-letter queue retains deliveries that cannot be processed successfully.

A dead-letter record should preserve:

- Original event identifier.
- Consumer identifier.
- Failure reason.
- Number of attempts.
- Failure timestamp.
- Replay information.

The PostgreSQL implementation stores these details in `dead_letters`.

A dead-letter event should not be discarded without investigation.

Before replaying an event, operators should establish whether:

- The original failure has been corrected.
- The payload remains valid.
- The consumer can safely process the event again.
- The business operation has already occurred.
- Replay could create duplicate external side effects.

## 10. Event Replay

Event replay means processing an existing event again.

It is useful when:

- A consumer was temporarily unavailable.
- A processing defect has been corrected.
- A downstream database has been recovered.
- A new consumer requires historical events.
- A failed delivery needs controlled recovery.

Replay should preserve the original event identity and business context.

The implementations provide consumer-specific replay operations.

A replay is not equivalent to publishing a new business event. Creating a new event can produce a new business action, while replaying an existing event attempts to recover its previous processing.

Replay must be protected by idempotency controls.

## 11. Event Filtering and Routing

Not every consumer needs every event.

Event filtering allows a consumer to receive or process events only when specific conditions are satisfied.

Example:

A large-order monitoring service processes only orders with an amount of at least 10,000.

The JavaScript implementation supports predicate-based filtering.

The C++ implementation uses a filtering function.

The Java implementation uses `Predicate<Event>`.

PostgreSQL stores subscription filtering information in JSONB for use by dispatch workers.

Filtering reduces unnecessary consumer processing, but it must not silently discard events required by critical business workflows.

## 12. Event Ordering and Concurrency

Events may be processed concurrently.

This improves throughput but can introduce ordering problems.

Consider two events:

- `OrderCreated`
- `OrderCancelled`

If the cancellation event is processed first, the consumer might observe an incorrect business sequence.

### Ordering strategies

| Strategy | Purpose |
|---|---|
| Global ordering | Preserves order across all events |
| Partition ordering | Preserves order within a partition |
| Aggregate ordering | Preserves order for a business entity |
| Sequence numbers | Detect missing or out-of-order events |
| Serialized consumer processing | Prevents concurrent handling of related events |

Global ordering can limit throughput.

Partitioning by aggregate identifier provides a practical compromise for many business systems.

The PostgreSQL schema includes `aggregate_type`, `aggregate_id`, and `aggregate_sequence` to support aggregate-level ordering.

The unique index prevents duplicate sequence numbers for a given aggregate.

A production dispatcher must still enforce the required processing sequence.

## 13. Event-Driven Architecture and Other Architectural Styles

EDA is distinct from several related architectural concepts.

| Architecture or pattern | Main characteristic |
|---|---|
| Request-response | A caller sends a request and receives a response |
| Event-driven | Components react to published events |
| Message-driven | Components communicate through messages |
| Command-driven | A component requests a specific operation |
| Microservices | Application capabilities are separated into independently managed services |
| CQRS | Separates command handling from query models |
| Event sourcing | Stores state changes as an event history |

### EDA versus event sourcing

EDA describes communication and coordination through events.

Event sourcing describes a method of storing application state as a sequence of events.

An application can use event-driven communication without using event sourcing.

Similarly, an application can use event sourcing without exposing every stored event through an external event broker.

### EDA versus CQRS

CQRS separates the write model from the read model.

EDA can connect the two models by publishing events after successful state changes.

For example:

Order Service
→ OrderCreated
→ Analytics Consumer
→ Reporting Database

The reporting database maintains a read-oriented representation of order information.

This introduces eventual consistency between the source database and the reporting database.

## 14. Python Implementation

**File:** `event_driven_architecture.py`

The Python program provides an executable event-processing simulation using standard-library components.

| Component | Implementation |
|---|---|
| Schema definition | `EventSchema` |
| Schema management | `SchemaRegistry` |
| Event representation | `Event` dataclass |
| Delivery state | `Delivery` dataclass |
| Event routing | `EventBroker` |
| Producer | `OrderService` |
| Inventory consumer | `InventoryConsumer` |
| Payment consumer | `PaymentConsumer` |
| Notification consumer | `NotificationConsumer` |

### Important mechanisms

- Dictionaries maintain event and subscription state.
- Sets maintain processed consumer-event pairs.
- A deque stores dead-letter deliveries.
- A reentrant lock protects shared broker state.
- Dataclasses provide structured domain objects.
- Enums represent event lifecycle states.
- Exceptions reject invalid events and duplicate identifiers.
- JSON serialization creates an audit snapshot.

The implementation dispatches events to registered consumers and tracks successful processing independently.

Consumer failures are isolated and retried.

The example includes validation failures, duplicate dispatch, dead-letter creation, and audit export.

The broker is in-memory, so event data is not durable across process restarts.

## 15. JavaScript Implementation

**File:** `event_driven_architecture.js`

The JavaScript implementation emphasizes asynchronous processing and event-oriented application behavior.

| Component | Implementation |
|---|---|
| Schema registry | `SchemaRegistry` |
| Event creation | `EventFactory` |
| Broker | `EventBroker` |
| Event listeners | `EventEmitter` |
| Consumer state | `Map` |
| Idempotency | `Set` |
| Concurrent processing | `Promise.all` |
| Consumer filtering | Predicate functions |
| Audit export | Node.js file system |

### Important mechanisms

`EventEmitter` provides local event notifications for broker activities such as publication, subscription, retry, consumption, and dead-letter creation.

`Promise.all` waits for independently dispatched consumer operations.

The implementation uses asynchronous handlers so consumers can perform asynchronous business operations.

`structuredClone` isolates the published event payload from subsequent producer-side mutation.

The broker also provides batch publication, replay, metrics, and graceful closure.

The concurrency setting is included as broker configuration. The sample's consumer dispatch uses concurrent promises; a production implementation would need a bounded worker pool to enforce a strict concurrency limit.

## 16. C++17 Implementation

**File:** `event_driven_architecture.cpp`

The C++ program emphasizes explicit domain modeling and efficient data structures.

| Component | Implementation |
|---|---|
| Event status | `enum class EventStatus` |
| Schema | `EventSchema` |
| Schema registry | `SchemaRegistry` |
| Event representation | `Event` struct |
| Consumer | `Consumer` struct |
| Delivery result | `DeliveryResult` struct |
| Broker | `EventBroker` |
| Inventory | `InventoryService` |
| Payments | `PaymentService` |
| Notifications | `NotificationService` |

### Important mechanisms

- `unordered_map` provides average constant-time event lookup.
- `unordered_set` tracks successfully processed deliveries.
- `map` maintains schema definitions.
- `vector` stores subscribers and delivery results.
- `function` supports consumer handlers and validation rules.
- Exceptions represent validation and processing failures.

The broker provides independent consumer delivery, retry handling, filtering, replay, and dead-letter recording.

The implementation is single-threaded. Its data structures are not intended for concurrent access without synchronization.

## 17. Java 17 Implementation

**File:** `EventDrivenArchitecture.java`

The Java implementation uses enterprise-oriented domain modeling and service contracts.

| Component | Implementation |
|---|---|
| Event schema | `EventSchema` |
| Field definition | `FieldDefinition` record |
| Event | `Event` record |
| Consumer interface | `EventConsumer` |
| Subscription | `Subscription` record |
| Broker | `EventBroker` |
| Producer | `OrderProducer` |
| Inventory | `InventoryService` |
| Payment | `PaymentService` |
| Notifications | `NotificationService` |

### Important mechanisms

The `EventConsumer` interface separates consumer behavior from broker implementation.

Records provide compact immutable domain representations.

`Map.copyOf` and unmodifiable payload maps prevent unintended changes to event data.

`ConcurrentHashMap` maintains shared event and processing state.

`CopyOnWriteArrayList` supports subscription and audit-style collections where reads are frequent.

`CompletableFuture` enables concurrent consumer dispatch.

The implementation separates schema validation, publication, delivery, and business processing.

Its asynchronous execution uses the common fork-join pool. A production deployment should use a managed executor with explicit capacity, shutdown behavior, and backpressure.

## 18. PostgreSQL Implementation

**File:** `event_driven_architecture.sql`

The SQL implementation provides a durable relational model for event publication and delivery management.

### Main relational tables

| Table | Responsibility |
|---|---|
| `producers` | Registered event producers |
| `consumers` | Registered event consumers |
| `event_schemas` | Versioned event definitions |
| `subscriptions` | Consumer-to-event relationships |
| `events` | Published event records |
| `event_deliveries` | Individual consumer delivery states |
| `idempotency_records` | Duplicate-processing protection |
| `dead_letters` | Permanently failed deliveries |
| `event_audit` | Processing history |

### Important database mechanisms

**Primary and foreign keys**

Maintain relationships between events, producers, consumers, subscriptions, and deliveries.

**Unique constraints**

Prevent duplicate schema versions, subscriptions, deliveries, and consumer idempotency keys.

**Check constraints**

Restrict invalid retry counts and malformed JSON structures.

**JSONB**

Stores event payloads, metadata, schemas, and subscription filters.

**GIN indexes**

Support searches against JSONB payloads.

**Partial indexes**

Improve retrieval of pending and failed deliveries.

**Functions**

Validate event payloads and publish events.

**Procedures**

Claim deliveries, complete processing, record failures, and replay dead-letter records.

**Triggers**

Reconcile aggregate event status after delivery changes.

**Views**

Provide event-processing reports without repeatedly writing complex aggregation queries.

### Durable publication

The `publish_event` function validates the producer, active schema, and payload before inserting the event.

The event and its consumer delivery records are inserted within the same database transaction.

This creates a durable publication and delivery record.

### Concurrent delivery workers

`claim_event_deliveries` uses `FOR UPDATE SKIP LOCKED`.

This allows multiple database workers to claim different pending deliveries without unnecessarily blocking each other.

A worker claims a delivery and commits the transaction before making external service calls.

The worker subsequently invokes either `complete_delivery` or `fail_delivery`.

The worker identifier is checked before completion or failure to prevent a different worker from modifying a delivery it does not own.

### Delivery recovery

The SQL model supports bounded retries and dead-letter routing.

Failed attempts receive an increasing retry delay.

When the retry limit is reached, the delivery is moved to the dead-letter table.

The replay procedure resets the delivery to a pending state and records the replay operation.

A production implementation should also recover abandoned processing leases when workers terminate unexpectedly.

## 19. Event Lifecycle

The principal event lifecycle is:

Event Creation
→ Schema Validation
→ Publication
→ Subscription Matching
→ Delivery Creation
→ Consumer Processing
→ Successful Acknowledgment

Failure path:

Consumer Failure
→ Retry
→ Retry Limit Reached
→ Dead-Letter Queue
→ Investigation
→ Controlled Replay

An event and its individual deliveries have different states.

For example, an event may be successfully processed by Inventory Service but still be awaiting Payment Service.

Therefore, event-level status should be derived from its associated delivery records rather than assuming that publication means every consumer has completed processing.

## 20. Security and Reliability

Production event systems require controls beyond basic message routing.

| Concern | Control |
|---|---|
| Unauthorized publication | Producer authentication and authorization |
| Unauthorized consumption | Consumer access policies |
| Data exposure | TLS and encryption at rest |
| Malformed payloads | Schema validation |
| Duplicate delivery | Idempotency |
| Repeated failures | Bounded retries |
| Poison messages | Dead-letter routing |
| Sensitive information | Payload minimization and field-level controls |
| Event tampering | Integrity protection and access restrictions |
| Service overload | Backpressure and bounded concurrency |
| Data retention | Event lifecycle and archival policies |
| Operational diagnosis | Correlation IDs and structured logs |

Events should not contain passwords, access tokens, private keys, or unnecessary personal information.

Consumer authorization should be based on event type and business responsibility.

Database users should receive only the permissions required to publish, claim, process, or inspect events.

## 21. Performance Considerations

Event throughput depends on several factors:

- Number of published events.
- Average event payload size.
- Number of consumers.
- Consumer processing time.
- Network latency.
- Broker capacity.
- Database write performance.
- Retry frequency.
- Concurrency limits.

A high number of consumers increases the number of delivery operations.

Large payloads increase network and storage costs.

Indexes improve retrieval but introduce additional write overhead.

Concurrent processing improves throughput when consumers are independent, but it requires careful control of ordering and shared business state.

For high-volume systems, event storage can be partitioned by publication time. Retention and archival policies should prevent unbounded storage growth.

## 22. Limitations of the Implementations

| Implementation | Demonstrated capability | Production limitation |
|---|---|---|
| Python | In-memory broker, validation, retries, replay | No durable broker storage |
| JavaScript | Asynchronous consumers, filters, event notifications | No distributed transport or enforced worker pool |
| C++17 | Domain modeling, validation, routing, failure handling | Single-threaded in-memory execution |
| Java 17 | Enterprise service contracts and concurrent dispatch | Common executor and in-memory persistence |
| PostgreSQL | Durable event records and delivery workflow | Requires external workers for actual service execution |

The examples demonstrate architectural mechanisms rather than complete distributed messaging infrastructure.

The PostgreSQL implementation provides a durable dispatch model, but it does not itself transmit messages to external services.

## 23. Execution

| File | Runtime |
|---|---|
| Python | Python 3.10+ |
| JavaScript | Node.js 18+ |
| C++17 | C++ compiler supporting C++17 |
| Java | Java 17 |
| PostgreSQL | PostgreSQL 15+ |

### Python

Run `python event_driven_architecture.py`.

The program executes validation and delivery tests and writes `event_audit.json`.

### JavaScript

Run `node event_driven_architecture.js`.

The program demonstrates concurrent consumer processing, filtering, retries, dead-letter handling, metrics, and audit export.

### C++17

Compile using a C++17-compatible compiler and run the resulting executable.

The program demonstrates event publication, schema validation, routing, consumer filtering, duplicate dispatch, and failure reporting.

### Java 17

Compile using `javac EventDrivenArchitecture.java` and execute using `java EventDrivenArchitecture`.

The program demonstrates schema validation, immutable events, service contracts, concurrent dispatch, and dead-letter handling.

### PostgreSQL

Execute `event_driven_architecture.sql` against a PostgreSQL 15+ database.

The script creates the schema, registers producers and consumers, publishes sample events, demonstrates delivery processing, and executes reporting queries.

The database script uses `gen_random_uuid()` for event identifiers and JSONB for payload and schema storage.
