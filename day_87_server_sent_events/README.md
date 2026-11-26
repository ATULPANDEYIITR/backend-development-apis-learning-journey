# Server-Sent Events: Streaming Responses and Real-Time Updates

## 1. Server-Sent Events

Server-Sent Events (SSE) is an HTTP-based mechanism for delivering continuous updates from a server to a client over a persistent connection.

The server sends a stream of events, and the client receives them as they arrive. Unlike ordinary HTTP responses, an SSE response remains open until the connection is terminated.

SSE is designed for one-way communication:

- Server to browser: supported.
- Browser to server: performed through separate HTTP requests.
- Persistent connection: supported.
- Automatic browser reconnection: supported through the EventSource API.
- Event identification: supported through event IDs.
- Named events: supported through event types.

Typical applications include:

- Live notifications.
- Background task progress.
- Deployment monitoring.
- Financial dashboards.
- System monitoring.
- Order status updates.
- Application activity feeds.
- Real-time reporting.

## 2. SSE Architecture

A typical SSE architecture separates event production, event distribution, transport, and client consumption.

    Business Application
            |
            v
       Event Producer
            |
            v
       Event Broker
            |
            +------ Event History
            |
            +------ Subscriber Registry
            |
            v
        HTTP Server
            |
            v
     text/event-stream
            |
            v
        Browser Client
            |
            v
      Event Processing

Each component has a separate responsibility.

| Component | Responsibility |
|---|---|
| Event producer | Creates application events |
| Event broker | Distributes events to subscribers |
| Event history | Retains events for reconnection |
| Subscriber registry | Tracks active connections |
| HTTP server | Maintains persistent HTTP responses |
| Browser client | Receives and processes events |
| Database | Provides durable event storage when required |

The Python implementation demonstrates an HTTP server and an in-memory broker. JavaScript provides an event-driven Node.js implementation. C++ models a transport-independent distribution engine. Java implements an enterprise application service. PostgreSQL provides the durable relational model.

## 3. HTTP Streaming Mechanics

SSE uses the HTTP response content type:

`text/event-stream`

The server sends an HTTP response and keeps the connection open.

The response normally includes:

| Header | Purpose |
|---|---|
| `Content-Type` | Identifies the response as an SSE stream |
| `Cache-Control` | Prevents inappropriate caching |
| `Connection` | Supports persistent HTTP/1.1 connections |
| `X-Accel-Buffering` | Requests that Nginx disable response buffering |

An SSE connection differs from an ordinary HTTP request because the response body is not completed immediately.

### 3.1 Event wire format

An SSE message consists of text fields separated by line breaks.

The main fields are:

| Field | Meaning |
|---|---|
| `id` | Identifies the event |
| `event` | Specifies the named event type |
| `data` | Contains the event payload |
| `retry` | Suggests a reconnection delay in milliseconds |
| `:` | Introduces a comment |

A typical event has four lines:

    id: 105
    event: progress
    data: {"job_id":"job-100","progress":75}

A blank line terminates the event.

The browser processes the event after receiving the complete event boundary.

Multiple `data` lines are permitted. Their values are combined with newline characters when the browser dispatches the event.

A comment such as `: heartbeat` is not dispatched as an application event.

### 3.2 Event identifiers

Event identifiers support recovery after a connection interruption.

For example:

- Event 101: deployment started.
- Event 102: build completed.
- Event 103: deployment started.
- Connection interrupted.
- Browser reconnects with `Last-Event-ID: 103`.
- Server sends events with identifiers greater than 103.

The event identifier represents a position in an event stream, not necessarily a globally unique business transaction identifier.

The implementations use monotonically increasing numeric identifiers within an event stream.

A production system should define identifier scope clearly. Identifiers must remain unambiguous for the lifetime of the corresponding replay history.

## 4. Streaming Responses and Persistent Connections

A streaming response sends data progressively instead of waiting for the complete result.

Consider a background report-generation task.

| Time | Event | Progress |
|---|---|---:|
| 10:00:00 | Task created | 0% |
| 10:00:05 | Data retrieved | 20% |
| 10:00:12 | Processing | 45% |
| 10:00:20 | Validation | 80% |
| 10:00:25 | Completed | 100% |

An ordinary HTTP response might return only the final result.

An SSE connection can communicate each intermediate state.

The application therefore separates:

1. Business operation execution.
2. Event generation.
3. Event serialization.
4. Event transmission.
5. Client-side event processing.

This separation prevents HTTP transport logic from becoming tightly coupled to business processing.

## 5. EventSource API

Modern browsers provide the native `EventSource` interface.

It establishes an HTTP connection and handles standard reconnection behavior.

A browser can listen for standard messages and named events.

The JavaScript browser interface uses these methods and properties:

| API | Purpose |
|---|---|
| `new EventSource(url)` | Opens an SSE connection |
| `onmessage` | Handles unnamed message events |
| `addEventListener()` | Handles named events |
| `onopen` | Detects successful connection establishment |
| `onerror` | Detects connection errors |
| `close()` | Terminates the connection |
| `readyState` | Reports connection state |
| `CLOSED` | Indicates a closed connection |
| `CONNECTING` | Indicates connection establishment or reconnection |
| `OPEN` | Indicates an active connection |

Named events require matching event listeners.

An event named `progress` is not automatically delivered through the generic `onmessage` handler.

A browser client can also use `fetch()` and the Streams API when more control over parsing, authentication headers, or request behavior is required.

The native `EventSource` constructor does not provide arbitrary request-header configuration. Cookie-based authentication or a custom streaming client may therefore be necessary for applications requiring additional authentication mechanisms.

## 6. SSE Compared with Other Communication Mechanisms

SSE, WebSockets, HTTP polling, and long polling solve related but distinct communication problems.

| Characteristic | SSE | WebSockets | Polling | Long polling |
|---|---|---|---|---|
| Communication | One-way | Two-way | Request-response | Request-response |
| Persistent connection | Yes | Yes | No | Repeated |
| Server push | Yes | Yes | No direct push | Delayed response |
| Native browser support | EventSource | WebSocket | Fetch | Fetch |
| Event identifiers | Standard field | Application-defined | Application-defined | Application-defined |
| Automatic reconnect | Built in | Application-managed | Request scheduling | Request scheduling |
| Primary use | Live server updates | Interactive communication | Periodic retrieval | Reduced polling frequency |

SSE is appropriate when the server must continuously communicate updates and the browser does not need to send application messages through the same connection.

WebSockets are more appropriate when continuous bidirectional communication is required.

Polling remains useful for simple systems where update frequency is low and persistent connections are unnecessary.

## 7. Python Implementation

The Python source file implements a complete demonstration HTTP server using standard-library components.

### 7.1 Event domain model

`SSEEvent` is an immutable dataclass.

Its attributes are:

- Event identifier.
- Event category.
- Structured payload.
- Creation timestamp.

The `encode()` method converts the event into the SSE wire format.

The implementation uses JSON serialization to ensure that structured payloads are represented consistently.

### 7.2 Event history

`EventHistory` uses `collections.deque`.

The bounded deque prevents unlimited memory consumption.

When the configured capacity is reached, older events are automatically discarded.

The `after()` operation retrieves events following a specified cursor.

Its complexity is O(H), where H is the number of retained events.

For larger histories, an indexed event store or database-backed replay mechanism is preferable.

### 7.3 Event broker

`EventBroker` manages event publication.

Its responsibilities include:

- Generating sequential identifiers.
- Validating payloads.
- Retaining events.
- Notifying waiting connections.
- Supporting event replay.

A condition variable coordinates waiting HTTP handlers with event publication.

The broker separates event creation from HTTP response handling.

### 7.4 HTTP endpoints

The Python server exposes three endpoints.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health verification |
| `/events` | GET | Persistent SSE stream |
| `/publish` | POST | Publish a notification |

The `/events` endpoint reads the `Last-Event-ID` header and replays retained events before waiting for new events.

The response is flushed after each event to reduce transmission delay.

### 7.5 Concurrency and limitations

`ThreadingHTTPServer` allows multiple clients to maintain separate connections.

The broker uses synchronization around its event history and notification condition.

This demonstration does not implement distributed event coordination, durable replay, authentication, or production-grade connection admission control.

A production deployment should use bounded worker resources, authenticated subscriptions, reverse-proxy configuration, and durable event storage.

## 8. JavaScript Implementation

The JavaScript implementation uses Node.js native HTTP and event-driven capabilities.

### 8.1 EventEmitter

`EventEmitter` distributes events to registered listeners.

The broker emits a common event notification after an event is published.

Each connected client registers a listener and receives events through its HTTP response.

This approach separates event producers from individual subscribers.

### 8.2 Event history

`EventHistory` maintains an array of retained events.

The history supports:

- Event insertion.
- Bounded retention.
- Cursor lookup.
- Replay of events after a given identifier.

The implementation uses array slicing for replay.

Removing old events with `shift()` has O(H) worst-case movement cost. A ring buffer or dedicated indexed store is preferable for high-volume workloads.

### 8.3 Subscriber lifecycle

Each subscriber has:

- A unique client identifier.
- An HTTP response object.
- A connection timestamp.
- A connection state.
- An event listener.

When the response closes, the broker removes the corresponding listener.

This is essential because abandoned listeners can consume memory and cause events to be sent to disconnected clients.

### 8.4 Backpressure

Backpressure occurs when the server produces data faster than a client can consume it.

For example, a monitoring application might generate 1,000 events per second while a client can process only 100 events per second.

Without a defined policy, buffered responses can consume excessive memory.

The JavaScript implementation checks `response.writableLength` and disconnects clients whose buffered output exceeds a configured limit.

Other possible strategies include:

- Bounded application queues.
- Event coalescing.
- Dropping replaceable updates.
- Disconnecting slow clients.
- Reconnecting with replay.

The correct policy depends on whether event loss is acceptable.

## 9. C++17 Implementation

The C++ program implements a transport-independent event broker.

It focuses on domain modeling, subscriber management, bounded queues, and replay.

### 9.1 Domain types

The implementation uses enumerations for event types and connection states.

`SSEEvent` represents an individual event.

`Client` represents a subscriber and maintains:

- Client identity.
- Connection state.
- Event subscriptions.
- Outgoing event queue.
- Queue capacity.
- Delivery position.
- Dropped-event count.

### 9.2 Subscription filtering

A subscriber can register for specific event types.

For example:

- Browser 1 subscribes to progress events.
- Browser 2 subscribes to notification events.

The broker distributes only matching events.

An empty subscription filter represents an unrestricted subscription.

### 9.3 Bounded queues

Each client has a maximum outgoing queue capacity.

When the queue reaches its limit, the client enters the `SlowConsumer` state.

This prevents unlimited queue growth.

The demonstration uses an explicit drain operation to simulate network consumption.

### 9.4 Reconnection

The `reconnect()` method creates a new subscriber and retrieves retained events after the supplied identifier.

This represents the application-level equivalent of processing `Last-Event-ID`.

The implementation deliberately separates replay from HTTP transport.

It can therefore be adapted to a socket-based or HTTP-based networking layer without changing its core event model.

### 9.5 Complexity

Let:

- H = number of retained events.
- C = number of connected clients.
- Q = maximum queue capacity.
- S = number of event types in a subscriber filter.

| Operation | Complexity |
|---|---|
| Event history insertion | O(1) |
| Event replay | O(H) |
| Broadcasting | O(C log S) for filtered subscriptions |
| Queue insertion | O(1) |
| Queue removal | O(1) |
| Subscriber removal | Average O(1) |

The implementation uses a single-threaded execution model.

A production implementation needs synchronization and independent network writers so that slow clients cannot delay event publication.

## 10. Java 17 Enterprise Implementation

The Java implementation models a multi-tenant enterprise streaming service.

Its focus is typed domain objects, explicit service responsibilities, access control, and bounded subscriber queues.

### 10.1 Immutable records

The implementation uses Java records for:

- `SSEEvent`
- `SubscriberIdentity`
- `StreamingPolicy`

Records provide concise data structures with generated accessors and value-based methods.

The event model validates its identifiers, timestamps, and payload values.

### 10.2 Authorization service

The authorization service evaluates whether a subscriber can access an event.

It considers:

- Subscriber identity.
- Tenant identity.
- Permitted event types.
- Requested tenant.

A subscriber belonging to one tenant cannot use its identity to retrieve another tenant's events.

The example demonstrates application-level tenant isolation.

Production systems must also enforce authorization when registering subscriptions and publishing tenant-specific events.

### 10.3 Streaming policy

`StreamingPolicy` centralizes configuration.

| Policy | Purpose |
|---|---|
| History capacity | Limits retained events |
| Subscriber queue capacity | Controls per-client memory |
| Maximum payload length | Limits event size |
| Maximum subscribers | Restricts concurrent sessions |

Centralized policy objects make operational constraints explicit and easier to validate.

### 10.4 Subscriber sessions

`SubscriberSession` maintains a bounded `ArrayBlockingQueue`.

The queue provides thread-safe event insertion and retrieval.

A subscriber becomes a slow consumer when the queue cannot accept another event.

This design makes memory limits explicit.

### 10.5 Asynchronous publication

The service exposes `publishAsync()` using `CompletableFuture`.

This allows event production to integrate with asynchronous application workflows.

The example uses the default asynchronous execution facility. Production deployments should use an explicitly configured executor with bounded capacity and appropriate lifecycle management.

### 10.6 Enterprise failure handling

The implementation models:

- Invalid event identifiers.
- Invalid payloads.
- Unauthorized tenant access.
- Duplicate subscriber registration.
- Maximum subscriber limits.
- Slow consumers.
- Disconnected sessions.

The authorization, publication, and subscription services are separated so that policy decisions are not embedded in transport-specific code.

## 11. PostgreSQL Event Storage

An in-memory broker is useful for distributing events within one running application instance.

It is insufficient when events must survive application restarts or support recovery across multiple instances.

PostgreSQL provides durable storage and transactional consistency.

The SQL implementation models a multi-tenant streaming system.

### 11.1 Relational domain model

The main relationships are:

    Tenant
      |
      +---- Application User
      |
      +---- Event Stream
                |
                +---- Stream Event
                |
                +---- Event Subscription
                            |
                            +---- Subscriber
                            |
                            +---- Event Delivery

    Event Outbox
         |
         +---- Event Stream
         |
         +---- Published Event

### 11.2 Event stream

`event_stream` represents a logical event channel.

A stream belongs to a tenant and has:

- A unique name within the tenant.
- An active state.
- A retention limit.
- A next-event identifier.

The `next_event_id` field is incremented transactionally.

Updating the stream row serializes identifier allocation for that stream.

This prevents two concurrent publishers from allocating the same identifier.

### 11.3 Durable event records

`stream_event` stores the event history.

Each record contains:

- Stream identifier.
- Event identifier.
- Event type.
- JSONB payload.
- Creation timestamp.
- Optional expiration timestamp.

The unique constraint on `(stream_id, event_id)` prevents duplicate identifiers within a stream.

The replay index supports ordered retrieval.

### 11.4 Subscription management

`event_subscription` connects a subscriber to a stream.

It records:

- Tenant.
- Stream.
- Subscriber.
- Event-type filters.
- Enabled state.
- Last acknowledged event identifier.

This separates subscriber identity from subscription preferences.

A subscriber may have multiple subscriptions, and each subscription maintains its own event cursor.

### 11.5 Delivery tracking

`event_delivery` tracks individual delivery attempts.

Its states are:

| State | Meaning |
|---|---|
| `pending` | Awaiting delivery |
| `delivered` | Acknowledged according to application policy |
| `failed` | Delivery attempt failed |
| `expired` | Delivery is no longer eligible |

A durable delivery record is useful when the application needs per-subscriber delivery auditing.

It is not mandatory for every SSE deployment. Systems with large event volumes may prefer cursor-based recovery without maintaining a separate row for every subscriber-event combination.

## 12. Last-Event-ID and Replay Semantics

Reconnection is one of the most important aspects of reliable SSE implementations.

The browser maintains the last received event identifier and can include it in the next connection request.

The server uses that cursor to retrieve subsequent events.

The logical operation is:

    Incoming Last-Event-ID
              |
              v
       Validate Cursor
              |
              v
       Check Retention
              |
              v
       Retrieve Newer Events
              |
              v
       Send Replay Events
              |
              v
       Continue Live Stream

A cursor is not a guarantee that every historical event remains available.

If the requested cursor is older than the retained history, the server must identify the gap.

Possible recovery strategies include:

- Requesting a fresh application snapshot.
- Rebuilding client state from a durable source.
- Starting a new subscription.
- Informing the client that complete replay is unavailable.

The SQL `replay_events()` function explicitly rejects expired replay cursors rather than silently treating missing events as successful recovery.

## 13. Transactional Outbox Pattern

An important reliability problem occurs when a business transaction succeeds but event publication fails.

Consider an order-management application.

1. An order is saved in PostgreSQL.
2. The application attempts to publish an order-created event.
3. The event broker becomes unavailable.
4. The order exists, but subscribers never receive the notification.

The transactional outbox pattern addresses this problem.

The business transaction writes both the business record and an outbox record in the same database transaction.

A background worker later publishes the outbox event.

    Business Transaction
            |
            +---- Save Business Record
            |
            +---- Insert Outbox Event
            |
            v
          COMMIT
            |
            v
       Outbox Worker
            |
            v
       Publish Event
            |
            v
       Mark Published

The SQL implementation includes:

- `event_outbox`
- `process_event_outbox()`
- Retry attempts.
- Delayed retries.
- Failure states.
- Transactional event publication.

`FOR UPDATE SKIP LOCKED` allows multiple workers to process different outbox records concurrently.

The outbox improves reliability but does not automatically provide exactly-once delivery.

A worker can experience failures around network transmission and acknowledgement. Event identifiers and idempotent consumers remain necessary.

## 14. PostgreSQL LISTEN and NOTIFY

PostgreSQL provides `LISTEN` and `NOTIFY` for database notification.

These mechanisms can wake up an application process when a new event becomes available.

The SQL implementation calls `pg_notify()` during publication.

The notification contains the stream identifier and event identifier.

The application then queries the durable event table.

This distinction is important:

| Mechanism | Responsibility |
|---|---|
| `NOTIFY` | Signals that new information may be available |
| `stream_event` | Stores durable event data |
| `replay_events()` | Retrieves events after a cursor |
| HTTP SSE | Delivers events to browser connections |

PostgreSQL notifications are not a durable message queue.

Applications must not depend on notifications alone for event recovery.

A process that is disconnected during a notification can recover by querying the durable event table.

## 15. Heartbeats and Connection Management

An idle SSE connection may be closed by:

- Reverse proxies.
- Load balancers.
- Network intermediaries.
- Firewall policies.
- Browser or operating-system conditions.

A heartbeat is a comment sent periodically through the stream.

Example:

    : heartbeat

The browser ignores the comment as an application event.

The heartbeat nevertheless produces network activity and can help maintain idle connections.

The implementations demonstrate heartbeat generation.

A production system should configure heartbeat intervals according to the shortest relevant infrastructure idle timeout.

Heartbeat messages should not be treated as business events.

## 16. Backpressure and Resource Management

A server can produce events faster than subscribers can receive them.

This creates backpressure.

Unbounded buffering can cause:

- Memory exhaustion.
- Increasing event latency.
- Thread exhaustion.
- Delayed shutdown.
- Unresponsive subscribers.

The implementations demonstrate different approaches.

| Implementation | Backpressure mechanism |
|---|---|
| Python | Threaded connections and socket write behavior |
| JavaScript | HTTP writable buffer monitoring |
| C++17 | Bounded outgoing queues |
| Java 17 | Bounded blocking queues |
| PostgreSQL | Durable storage and delivery tracking |

Possible production policies include:

1. Disconnecting persistently slow consumers.
2. Replaying missed events after reconnection.
3. Coalescing replaceable progress updates.
4. Applying bounded queues.
5. Limiting concurrent connections.
6. Separating publication from network transmission.

Not every event can be safely dropped.

For example, intermediate progress percentages may be coalesced, while financial transaction notifications may require durable recovery.

## 17. Security Considerations

An SSE endpoint is a long-lived network resource and must be protected accordingly.

### 17.1 Authentication

The server must establish the subscriber's identity before opening a stream.

Authentication can use:

- Secure session cookies.
- Authenticated reverse-proxy identity.
- Short-lived access tokens.
- Application-specific authentication middleware.

Native browser `EventSource` has limitations around custom authorization headers.

### 17.2 Authorization

Authentication establishes identity.

Authorization determines which streams and event categories that identity can access.

The Java implementation demonstrates tenant-based authorization.

The SQL implementation checks tenant ownership during subscription registration.

Production deployments should prevent unauthorized access during:

- Initial connection.
- Subscription registration.
- Event retrieval.
- Reconnection.
- Snapshot recovery.

### 17.3 Payload validation

Event payloads must be validated before publication.

Important controls include:

- Maximum payload size.
- JSON structure validation.
- Event type validation.
- Field validation.
- Unicode handling.
- Safe serialization.

The implementations use JSON serialization rather than inserting arbitrary structured values directly into the SSE protocol.

### 17.4 Cross-Site Request Forgery

Cookie-authenticated applications must consider cross-site request forgery.

The SSE GET endpoint should not perform business-state changes.

Publication endpoints should implement appropriate authentication, authorization, CSRF protection where applicable, and request validation.

### 17.5 Transport security

Production deployments should use HTTPS.

TLS protects event contents during transmission and reduces exposure to network interception.

Connection limits, rate limits, and infrastructure-level timeout controls are also necessary.

## 18. Performance and Scalability

SSE performance depends on several factors:

- Number of simultaneous subscribers.
- Event frequency.
- Average payload size.
- Replay window.
- Subscriber processing speed.
- Network throughput.
- Retention requirements.

For a simple broker, publishing an event to C subscribers generally requires O(C) distribution work.

The memory cost of retained events is approximately proportional to the total serialized size of retained payloads.

Each subscriber also requires connection-related memory and potentially a bounded outgoing queue.

### Scaling strategies

| Challenge | Engineering approach |
|---|---|
| Large subscriber count | Async HTTP server and connection limits |
| High event frequency | Batching and event coalescing |
| Slow subscribers | Bounded queues and disconnect policies |
| Application restarts | Durable event history |
| Multiple server instances | Shared event broker or durable database |
| Large replay windows | Indexed event storage |
| High database write volume | Partitioning and retention management |
| Network interruptions | Cursor-based reconnection |

A multi-instance deployment requires coordination beyond an in-memory event broker.

Each application instance must be able to access the relevant events, either through a shared event distribution system or through durable storage and polling or notification mechanisms.

## 19. Important Reliability Distinctions

Several concepts in SSE systems are related but should not be treated as equivalent.

| Concept | Meaning |
|---|---|
| Event publication | An application creates an event |
| Event persistence | An event is stored durably |
| Event transmission | The server writes the event to a connection |
| Browser reception | The browser receives the event |
| Event dispatch | The browser dispatches the event to application code |
| Business processing | Application code completes its operation |
| Delivery acknowledgement | The application records an acknowledgement |

An HTTP write succeeding does not prove that browser application code completed the associated business operation.

Likewise, browser reconnection does not establish exactly-once delivery.

Reliable event consumers should use event identifiers, deduplication, idempotent operations, and appropriate recovery mechanisms.

## 20. Testing and Failure Scenarios

The five implementations demonstrate validation and important operational failure conditions.

| Scenario | Expected behavior |
|---|---|
| Empty event payload | Reject publication |
| Unsupported event type | Reject publication |
| Oversized payload | Reject publication |
| Invalid event cursor | Reject reconnection |
| Expired replay cursor | Require resynchronization |
| Unknown subscriber | Reject subscription operation |
| Duplicate subscriber | Reject registration |
| Unauthorized tenant | Deny access |
| Slow consumer | Apply bounded-queue policy |
| Disconnected browser | Remove subscriber state |
| Database publication failure | Preserve outbox recovery state |
| Invalid progress percentage | Reject business update |
| Stream deactivated | Reject new event publication |

The Python and JavaScript programs can be executed directly.

The C++17 program exercises the event broker in a single process.

The Java 17 program exercises the enterprise streaming service and its authorization rules.

The PostgreSQL script creates the database model, inserts sample data, executes publication and replay operations, and performs reporting queries.

## 21. Execution Requirements

| Deliverable | Runtime | External dependencies |
|---|---|---|
| Python | Python 3.10+ | None |
| JavaScript | Node.js 18+ | None |
| C++17 | C++17 compiler | None |
| Java | Java 17 | None |
| PostgreSQL | PostgreSQL 14+ | None |

### Python

Save the source as `sse_server.py`.

Run the demonstration:

`python sse_server.py`

Start the HTTP server:

`python sse_server.py --serve`

The default server address is `http://127.0.0.1:8000`.

### JavaScript

Save the source as `sse_server.js`.

Run the demonstration:

`node sse_server.js`

Start the HTTP server:

`node sse_server.js --serve`

The default server address is `http://127.0.0.1:8000`.

### C++17

Save the source as `sse_engine.cpp`.

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic sse_engine.cpp -o sse_engine`

Execute:

`./sse_engine`

### Java 17

Save the source as `Main.java`.

Compile:

`javac Main.java`

Execute:

`java Main`

### PostgreSQL

Save the SQL source as `sse_streaming.sql`.

Execute using:

`psql -U postgres -d your_database -f sse_streaming.sql`

The script creates the `sse` schema and its associated database objects.

It uses a transaction to keep the schema, sample data, and demonstration operations consistent.

## 22. Technical Learning Outcomes

The implementations cover several distinct dimensions of real-time streaming engineering.

| Area | Implemented mechanism |
|---|---|
| Protocol | SSE wire-format encoding |
| HTTP | Persistent streaming responses |
| Event modeling | Identifiers, types, payloads, timestamps |
| Event distribution | Broker and event listeners |
| Subscription | Client registration and event filtering |
| Recovery | Last-Event-ID and replay |
| Connection management | Connection state and disconnection |
| Resource management | Bounded histories and queues |
| Concurrency | Thread synchronization and asynchronous execution |
| Authorization | Subscriber and tenant access policies |
| Persistence | Relational event storage |
| Reliability | Transactional outbox and retry handling |
| Monitoring | Subscriber and event metrics |
| Database performance | Indexed replay and reporting |
| Operational security | Payload limits, authentication boundaries, and access control |

The central architectural distinction is that SSE defines the mechanism for transmitting server-originated events over HTTP. It does not independently provide durable storage, distributed coordination, business-level acknowledgements, authorization, or exactly-once processing. Those capabilities must be designed as separate application and infrastructure components.
