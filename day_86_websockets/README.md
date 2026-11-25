# WebSockets: Persistent Connections and Real-Time Communication

## 1. Technical Scope

WebSockets provide a persistent, bidirectional communication channel between a client and a server. Unlike conventional HTTP request-response communication, a WebSocket connection remains open after its initial handshake, allowing either endpoint to transmit data independently.

This implementation explores WebSocket communication through five complementary engineering perspectives:

| Implementation | Engineering perspective |
|---|---|
| Python | RFC 6455 handshake, frame processing and asynchronous server |
| JavaScript | Event-driven client, reconnection and message management |
| C++17 | Connection lifecycle and transport-management engine |
| Java 17 | Enterprise connection domain model and asynchronous processing |
| PostgreSQL | Persistent connection metadata, messages, events and operational reporting |

The central distinction is between the network connection, its lifecycle, the application messages exchanged through it and the persistent records used to monitor its operation.

## 2. WebSocket Fundamentals

### 2.1 Conventional HTTP versus WebSocket

Conventional HTTP communication generally follows a request-response pattern.

A client sends a request, the server processes it and returns a response. A subsequent operation normally requires another HTTP request.

WebSockets begin with an HTTP request but establish a persistent communication channel through an HTTP Upgrade handshake.

| Property | HTTP request-response | WebSocket |
|---|---|---|
| Communication | Request-response | Bidirectional |
| Connection usage | Often short-lived at application level | Persistent |
| Server-initiated messages | Requires another mechanism | Native |
| Protocol establishment | HTTP request | HTTP Upgrade |
| Communication overhead | Repeated application requests | Lower repeated-request overhead |
| Typical applications | REST APIs, document retrieval | Chat, notifications, live dashboards |

HTTP keep-alive and WebSockets are different mechanisms. HTTP keep-alive allows connection reuse for HTTP exchanges, whereas WebSockets establish a distinct application communication protocol over the upgraded connection.

### 2.2 WebSocket URI Schemes

Two URI schemes identify WebSocket endpoints:

| Scheme | Meaning |
|---|---|
| `ws://` | WebSocket without transport encryption |
| `wss://` | WebSocket over TLS |

Production systems should generally use `wss://`, particularly when authentication credentials, personal information or confidential application messages are transmitted.

## 3. WebSocket Architecture

A typical WebSocket application contains several layers.

    Browser / Mobile Client
             |
             v
       HTTP Upgrade Request
             |
             v
       WebSocket Gateway
             |
             v
       Authentication
             |
             v
       Persistent Connection
             |
       +-----+------+
       |            |
       v            v
    Incoming     Outgoing
    Messages     Messages
       |            |
       v            v
    Validation   Message Queue
       |            |
       +-----+------+
             |
             v
       Application Services
             |
             v
       Database / Cache
             |
             v
       Operational Monitoring

The gateway manages transport-level communication. Application services interpret messages, enforce business rules and interact with persistent storage.

A WebSocket connection should not be confused with an authenticated application session. The network connection establishes communication, while authentication determines which user or service may use it.

## 4. HTTP Upgrade Handshake

### 4.1 Handshake Mechanism

A WebSocket connection begins with an HTTP GET request containing specific headers.

Important request headers include:

| Header | Purpose |
|---|---|
| `Upgrade: websocket` | Requests protocol upgrade |
| `Connection: Upgrade` | Identifies the upgrade operation |
| `Sec-WebSocket-Key` | Provides a random client handshake value |
| `Sec-WebSocket-Version: 13` | Identifies the WebSocket protocol version |

The server validates the request and calculates the `Sec-WebSocket-Accept` response.

The calculation is:

1. Obtain the client's `Sec-WebSocket-Key`.
2. Append the RFC 6455 WebSocket GUID.
3. Calculate the SHA-1 digest.
4. Encode the digest using Base64.
5. Return the result in the HTTP response.

The server responds with HTTP status `101 Switching Protocols`.

This response indicates that the protocol upgrade has succeeded.

### 4.2 Security Characteristics

The handshake does not independently authenticate a user.

Production implementations must separately consider:

- Authentication tokens.
- Cookie security.
- Origin validation.
- Authorization.
- TLS.
- Connection limits.
- Request-rate limits.
- Handshake timeouts.

A valid WebSocket handshake is not proof that the connecting user is authorized to access application data.

## 5. WebSocket Frame Structure

After the handshake, communication uses WebSocket frames rather than ordinary HTTP request-response messages.

The frame header contains:

| Field | Purpose |
|---|---|
| FIN | Indicates the final frame of a message |
| RSV | Reserved bits for protocol extensions |
| Opcode | Identifies the frame type |
| MASK | Indicates payload masking |
| Payload length | Identifies the payload size |
| Masking key | Used to unmask client-to-server payloads |
| Payload | Contains transmitted data |

### 5.1 Frame Opcodes

| Opcode | Frame | Purpose |
|---|---|---|
| `0x0` | Continuation | Continues a fragmented message |
| `0x1` | Text | UTF-8 text data |
| `0x2` | Binary | Binary application data |
| `0x8` | Close | Connection closure |
| `0x9` | Ping | Heartbeat request |
| `0xA` | Pong | Heartbeat response |

Control frames have specific restrictions:

- They cannot be fragmented.
- Their payload cannot exceed 125 bytes.
- They must be processed separately from ordinary application messages.

Client-to-server frames must be masked. Server-to-client frames are not masked by the protocol.

The Python implementation includes frame-length decoding, masking validation, control-frame processing and fragmented-message reconstruction.

## 6. Persistent Connection Lifecycle

A WebSocket connection is not simply open or closed. It passes through several states.

### 6.1 Lifecycle States

| State | Description |
|---|---|
| `CONNECTING` | Connection establishment is underway |
| `OPEN` | Communication is permitted |
| `RECONNECTING` | A replacement connection is being established |
| `CLOSING` | The closing handshake is underway |
| `CLOSED` | The connection has terminated |
| `FAILED` | An unrecoverable connection failure occurred |

The exact states used by an implementation can vary. The important requirement is that lifecycle transitions are controlled and invalid transitions are rejected.

### 6.2 Lifecycle Diagram

    CONNECTING
        |
        v
       OPEN
        |
        +-----------> CLOSING
        |                 |
        |                 v
        |               CLOSED
        |
        +-----------> RECONNECTING
        |                 |
        |                 v
        |             CONNECTING
        |
        +-----------> FAILED
                          |
                          v
                        CLOSED

A reconnecting client normally creates a new WebSocket transport connection. It does not revive a TCP connection that has already terminated.

The replacement connection may retain the same authenticated application identity, subject to reauthentication and authorization.

### 6.3 Important Lifecycle Events

| Event | Description |
|---|---|
| Connection attempt | Client initiates connection |
| Handshake completion | Server accepts protocol upgrade |
| Authentication | Application identity is validated |
| Message reception | Incoming application data is received |
| Heartbeat | Connection liveness is checked |
| Connection failure | Communication becomes unavailable |
| Reconnection | Client establishes another connection |
| Close handshake | Endpoints exchange closing information |
| Termination | Network resources are released |

## 7. Python Implementation: Asynchronous WebSocket Server

The Python implementation uses `asyncio` and the standard library to construct a small WebSocket server.

### 7.1 HTTP Handshake

The server parses HTTP headers and validates:

- Request method.
- HTTP protocol version.
- Upgrade header.
- Connection header.
- WebSocket protocol version.
- Client handshake key.

It calculates the server acceptance value using SHA-1 and Base64.

The implementation demonstrates why WebSocket establishment requires more than opening a TCP socket.

### 7.2 Frame Processing

The server implements:

- Frame header extraction.
- Extended payload lengths.
- Client masking.
- Payload decoding.
- Text and binary frames.
- Fragmented messages.
- Ping and pong.
- Close frames.

The frame decoder rejects unmasked client frames, invalid control frames, unsupported opcodes and oversized messages.

### 7.3 Asynchronous Communication

`asyncio.start_server()` accepts incoming TCP connections.

Each client is handled independently through an asynchronous coroutine.

This architecture avoids dedicating one operating-system thread to every connected client.

An `asyncio.Lock` protects concurrent writes to a connection. This prevents independently scheduled operations from interleaving their frame writes.

### 7.4 Application Message Protocol

The server accepts JSON application messages.

| Message type | Behaviour |
|---|---|
| `echo` | Returns the supplied data |
| `broadcast` | Sends an event to other connected clients |
| `metrics` | Returns operational counters |

The application message protocol is separate from the WebSocket framing protocol.

For example, a JSON message containing `type: echo` is transported inside a WebSocket text frame.

### 7.5 Failure Handling

The server includes:

- Handshake timeouts.
- Frame-size limits.
- Invalid JSON handling.
- UTF-8 validation.
- Connection timeouts.
- Write timeouts.
- Connection cleanup.
- Graceful shutdown.

The implementation is an educational RFC 6455 server, not a complete production WebSocket gateway. It does not implement every extension, compression negotiation, Origin policy, TLS termination or production-grade authentication.

## 8. JavaScript Implementation: Event-Driven Client

JavaScript provides an event-driven programming model that is particularly suitable for real-time communication.

The implementation uses the native WebSocket API available in Node.js 22+.

### 8.1 Event-Driven Architecture

A WebSocket client responds to lifecycle events rather than continuously polling the server.

| Event | Meaning |
|---|---|
| `open` | Connection established |
| `message` | Data received |
| `error` | Communication error |
| `close` | Connection terminated |

The client extends `EventEmitter` to expose application-level events.

Examples include:

- `connected`
- `disconnected`
- `reconnecting`
- `heartbeat`
- `protocolError`
- `sendError`

This separates transport events from application behaviour.

### 8.2 Connection State Management

The client maintains explicit lifecycle states and validates transitions.

For example:

- An idle client can connect.
- A connecting client can become open.
- An open client can reconnect or close.
- A closed client cannot reconnect.
- A failed client can begin a new connection attempt.

This prevents invalid operations from silently changing application state.

### 8.3 Automatic Reconnection

A connection can terminate because of:

- Network interruption.
- Server restart.
- Proxy timeout.
- Mobile network transition.
- Load-balancer failure.
- Server-side termination.

The JavaScript client uses exponential backoff.

The delay increases with each unsuccessful attempt:

\[
D_n = \min(D_0 \times 2^n,D_{\max})
\]

Random jitter is applied to reduce simultaneous reconnection attempts by many clients.

This is important when a server restart affects thousands of connected clients.

### 8.4 Outbound Message Queue

The client maintains a bounded outbound queue.

When the connection is unavailable, application messages can be queued temporarily.

When the connection becomes available, the client flushes the queue.

A bounded queue prevents unlimited memory consumption during prolonged outages.

Queueing does not guarantee message delivery. A production implementation needs explicit acknowledgement, persistence, retry and duplicate-handling policies for messages that must not be lost.

### 8.5 Request-Response Correlation

WebSockets provide bidirectional communication, but they do not automatically provide request-response correlation.

The JavaScript implementation assigns a unique request identifier using UUIDs.

A pending request is stored in a `Map`:

- Request identifier.
- Resolve callback.
- Reject callback.
- Timeout handle.

When a matching response arrives, the corresponding promise is resolved.

This mechanism allows application-level request-response operations over a persistent connection.

### 8.6 Transport Backpressure

The `bufferedAmount` property represents data queued by the WebSocket implementation for transmission.

The client checks this value before sending additional data.

This is different from the application's own outbound queue.

A production client should monitor both queues and define limits based on available memory, message size and expected network throughput.

## 9. C++17 Implementation: Connection Management Engine

The C++ implementation models a connection-management engine using domain classes and STL containers.

It concentrates on lifecycle correctness and resource control rather than implementing a second network stack.

### 9.1 Domain Model

The principal components are:

| Component | Responsibility |
|---|---|
| `WebSocketConnection` | Maintains one connection's state |
| `ConnectionManager` | Coordinates multiple connections |
| `ConnectionConfig` | Defines operational limits |
| `ConnectionMetrics` | Tracks communication statistics |
| `WebSocketMessage` | Represents an outbound message |

A connection maintains:

- Connection identifier.
- User identifier.
- Session identifier.
- Authentication status.
- Lifecycle state.
- Outbound queue.
- Heartbeat information.
- Operational counters.

### 9.2 Connection Registry

The connection manager uses a `map` to associate connection identifiers with connection objects.

Another mapping associates user identities with their active connection.

This allows targeted delivery without scanning every connection.

For a map-based registry:

- Lookup is approximately \(O(\log n)\).
- Insertion is approximately \(O(\log n)\).
- Iterating over all connections is \(O(n)\).

An unordered hash-based registry could provide average \(O(1)\) lookup, with different memory and ordering characteristics.

### 9.3 Backpressure and Capacity

The connection enforces maximum message sizes and maximum queued bytes.

A message is rejected when:

- The connection is not open.
- The user is not authenticated.
- The message exceeds the size limit.
- The outbound queue lacks capacity.

This protects the application against unbounded memory growth.

### 9.4 Session Replacement

A user may reconnect from a different device or after network interruption.

The connection manager supports replacement of an older active session with a newly authenticated connection.

This is useful in systems where a user should have only one active session or where concurrent session policies must be enforced.

The implementation is a lifecycle and queue-management simulation. It does not perform actual socket communication, TLS negotiation or RFC 6455 frame serialization.

## 10. Java 17 Implementation: Enterprise Connection Management

The Java implementation models an enterprise-oriented WebSocket service with explicit domain types and service boundaries.

### 10.1 Domain Types

Java records represent immutable data structures.

The implementation defines:

- `ConnectionIdentity`
- `WebSocketMessage`
- `ConnectionPolicy`
- `ConnectionSnapshot`

Enums represent lifecycle states and message categories.

This reduces accidental modification of identity and configuration data.

### 10.2 Connection Policy

The policy defines:

| Parameter | Purpose |
|---|---|
| Maximum message bytes | Limits individual payload size |
| Maximum queued messages | Limits queue length |
| Maximum queued bytes | Limits memory consumption |
| Idle timeout | Defines inactivity threshold |
| Heartbeat interval | Defines liveness-check frequency |
| Missed heartbeat limit | Defines failure threshold |
| Reconnection attempts | Limits retry operations |

Policy validation occurs when the policy object is created.

This prevents invalid configuration from propagating into connection services.

### 10.3 Connection Registry

`ConnectionRegistry` manages connection instances and user sessions.

It provides operations for:

- Registration.
- Authentication.
- Session replacement.
- Targeted message delivery.
- Broadcast.
- Closure.
- Operational reporting.

A listener interface exposes lifecycle events to other enterprise components.

This allows monitoring and audit services to observe connection activity without directly modifying connection state.

### 10.4 Asynchronous Processing

`AsyncEventProcessor` uses `ExecutorService` and `CompletableFuture`.

This separates application event processing from the calling thread.

Asynchronous execution is useful when messages require:

- Database operations.
- Business-rule evaluation.
- Notification generation.
- External service calls.
- Computational processing.

The example uses a bounded number of worker threads through a fixed thread pool.

Production implementations should also consider task queue limits, execution deadlines, cancellation, exception reporting and graceful executor shutdown.

## 11. Heartbeat and Connection Liveness

A persistent TCP connection does not necessarily indicate that an application is healthy.

A network interruption may remain undetected until another operation attempts communication.

Heartbeat messages help detect inactive connections.

### 11.1 Ping and Pong

The WebSocket protocol defines two control frames:

- Ping: sent to request a response.
- Pong: returned as a response.

The recipient of a ping must respond with a pong unless it has already received a close frame.

A heartbeat mechanism can identify:

- Unresponsive clients.
- Dead network paths.
- Server-side connection failures.
- Stalled communication.

### 11.2 Heartbeat Timing

Suppose a server sends a heartbeat every 20 seconds.

If two consecutive heartbeat responses are missed, the connection may be considered unhealthy.

The precise policy depends on network conditions and application requirements.

Short intervals improve detection speed but increase network traffic and processing overhead.

Long intervals reduce overhead but delay failure detection.

### 11.3 Transport Liveness versus Application Health

These are distinct concepts:

| Mechanism | What it demonstrates |
|---|---|
| TCP connectivity | Transport communication is possible |
| WebSocket pong | WebSocket endpoint responds |
| Application acknowledgement | Application processed or accepted an operation |
| Business transaction confirmation | Business operation reached its defined completion state |

A successful pong does not prove that a payment, notification or database operation succeeded.

## 12. Message Delivery and Reliability

WebSocket transport provides ordered communication over an individual connection, subject to the underlying TCP connection remaining valid.

It does not independently guarantee that an application operation has been completed or durably stored.

### 12.1 Message States

The database implementation models the following message states:

| State | Meaning |
|---|---|
| `queued` | Waiting for transmission |
| `sending` | Being processed for delivery |
| `sent` | Transport delivery operation completed |
| `acknowledged` | Application-level acknowledgement received |
| `failed` | Delivery processing failed |
| `expired` | Message exceeded its retention or delivery deadline |

These states are application-level records, not WebSocket protocol states.

### 12.2 Acknowledgements

Consider a notification application.

1. The server creates a notification.
2. The message enters the outbound queue.
3. The transport sends the message.
4. The client receives the message.
5. The client sends an application acknowledgement.
6. The server records the acknowledgement.

The distinction between `sent` and `acknowledged` is important.

A successful call to a WebSocket send operation does not prove that the receiving application processed the message.

### 12.3 Duplicate Delivery

Reconnection and retry mechanisms can result in duplicate application messages.

A reliable application protocol should consider:

- Unique message identifiers.
- Idempotency keys.
- Sequence numbers.
- Acknowledgements.
- Retry limits.
- Message expiry.
- Duplicate detection.
- Durable outbound storage.

Exactly-once business processing cannot be assumed merely because WebSocket uses TCP.

## 13. Reconnection and Session Management

Reconnection is a new communication establishment operation following a previous failure.

It is not equivalent to restoring the previous transport connection.

### 13.1 Reconnection Workflow

    Existing Connection
            |
            v
      Network Failure
            |
            v
     Detect Disconnection
            |
            v
      Schedule Retry
            |
            v
     Create New Socket
            |
            v
       HTTP Upgrade
            |
            v
       Authenticate
            |
            v
      Restore Session
            |
            v
      Resume Messaging

### 13.2 Exponential Backoff

A retry policy should prevent aggressive reconnection attempts.

A typical delay function is:

\[
D_n = \min(D_0 \times 2^n,D_{\max})
\]

Jitter distributes retries across time.

The server should also enforce connection limits and authentication requirements because reconnection traffic can create significant load after a large outage.

### 13.3 Session Restoration

An application may associate a replacement connection with an existing user session.

The application should validate the user's identity again and determine which messages need retransmission.

A session identifier and a connection identifier serve different purposes:

- Connection identifier: identifies one transport connection.
- Session identifier: identifies an application session.
- User identifier: identifies the application principal.
- Message identifier: identifies one application message.

These identifiers should not be treated as interchangeable.

## 14. PostgreSQL Implementation: Persistent Communication Records

PostgreSQL stores the operational and business metadata associated with WebSocket connections.

It does not replace the actual TCP or WebSocket transport.

### 14.1 Relational Domain Model

The database contains the following principal entities:

| Table | Responsibility |
|---|---|
| `tenants` | Tenant isolation |
| `application_users` | Application identities |
| `connection_policies` | Connection limits and behaviour |
| `websocket_connections` | Connection lifecycle |
| `connection_state_history` | State transition history |
| `connection_events` | Operational event records |
| `websocket_messages` | Message storage and delivery state |
| `connection_heartbeats` | Heartbeat monitoring |
| `connection_metrics` | Communication statistics |

The relationships follow this structure:

    Tenant
      |
      +---- Application Users
      |
      +---- Connection Policies
                  |
                  v
           WebSocket Connections
                  |
          +-------+--------+
          |       |        |
          v       v        v
       Messages Events Heartbeats
          |
          v
      Delivery States

### 14.2 Integrity Constraints

The database uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Enumerated lifecycle types.
- Generated payload-size columns.
- Referential integrity.
- Indexes for operational queries.

These mechanisms ensure that invalid records are rejected at the database boundary.

### 14.3 State Transition Trigger

The connection-state trigger validates lifecycle changes.

For example, a closed connection cannot return directly to the open state.

A replacement connection must be created and authenticated.

The trigger also records lifecycle history.

This provides an auditable record of connection establishment, transition and termination.

### 14.4 Transactional Message Queue

The `enqueue_message` function:

1. Locks the connection row.
2. Validates the connection state.
3. Checks authentication.
4. Retrieves the connection policy.
5. Validates message size.
6. Checks queue capacity.
7. Allocates a sequence number.
8. Inserts the message.
9. Updates connection activity.

The connection-level row lock helps prevent concurrent transactions from exceeding the configured queue limits or allocating conflicting sequence numbers.

### 14.5 Delivery and Acknowledgement

The stored procedures `mark_message_sent` and `acknowledge_message` implement separate delivery transitions.

The first records successful completion of the sending operation.

The second records application-level acknowledgement.

This distinction supports more meaningful delivery reporting.

### 14.6 Performance Indexes

Indexes support common operational access patterns:

| Index | Query pattern |
|---|---|
| Tenant and connection state | Active connection monitoring |
| User and activity timestamp | User session lookup |
| Active connection partial index | Current open connections |
| Connection and sequence number | Ordered message retrieval |
| Outbound queue partial index | Pending message processing |
| Event timeline | Connection investigation |
| Heartbeat pending index | Liveness monitoring |
| Message status | Delivery failure analysis |

For high-volume environments, message and event tables may require time-based partitioning, retention jobs and archival strategies.

## 15. Connection Security

Persistent communication creates security concerns that differ from ordinary short-lived HTTP requests.

### 15.1 Authentication

Authentication should occur during connection establishment or through a carefully controlled application authentication exchange.

A system must not assume that an open WebSocket connection remains authorized indefinitely.

Authentication expiry and session revocation should be considered.

### 15.2 Authorization

Authentication establishes identity.

Authorization determines permitted operations.

For example:

- A customer may receive notifications about their account.
- An administrator may receive operational events.
- A monitoring service may subscribe to system metrics.

A valid connection must not automatically grant access to every message channel.

### 15.3 Origin Validation

Browser-based applications should validate the HTTP `Origin` header against an approved origin policy.

This helps mitigate cross-site WebSocket hijacking risks when browser cookies are used for authentication.

Origin validation does not replace authentication or authorization.

### 15.4 Message Validation

Incoming messages should be checked for:

- Valid encoding.
- Valid application schema.
- Maximum payload size.
- Authorized event type.
- Valid identifiers.
- Permitted message frequency.

Binary and text messages should be handled according to the application's declared protocol.

### 15.5 Denial-of-Service Protection

Persistent connections can consume memory, file descriptors, CPU and bandwidth.

Important controls include:

- Maximum concurrent connections.
- Maximum message size.
- Bounded queues.
- Rate limiting.
- Idle timeouts.
- Heartbeat monitoring.
- Authentication throttling.
- Connection quotas.
- Resource cleanup.

A system should avoid creating unbounded asynchronous tasks for every incoming message.

## 16. Backpressure and Resource Management

Backpressure occurs when incoming or outgoing data is produced faster than the receiving system can process it.

For example, a dashboard may generate updates faster than a mobile client can consume them.

Without backpressure, queued messages can consume excessive memory.

### 16.1 Queue Management Strategies

| Strategy | Behaviour | Appropriate use |
|---|---|---|
| Bounded queue | Rejects new messages when full | General messaging |
| Drop-oldest | Removes older queued updates | Frequently refreshed dashboards |
| Drop-newest | Preserves existing queued data | Ordered delivery requirements |
| Coalescing | Replaces obsolete updates | Market prices and telemetry |
| Durable queue | Stores messages for later delivery | Critical notifications |

The correct strategy depends on message semantics.

Dropping an outdated dashboard value may be acceptable. Dropping a financial transaction event may not be.

### 16.2 Memory Considerations

If a server maintains \(N\) active connections and each connection has an average outbound buffer of \(B\) bytes, approximate buffered memory is:

\[
M = N \times B
\]

For 50,000 connections with an average buffered allocation of 8 KB:

\[
M = 50,000 \times 8,192
\]

\[
M = 409,600,000\text{ bytes}
\]

This is approximately 390.6 MiB, excluding connection objects, socket buffers, runtime overhead and application data.

Queue limits are therefore operational requirements rather than optional optimizations.

## 17. Scalability and Distributed Architecture

A single WebSocket server can manage multiple clients, but distributed deployments introduce additional coordination requirements.

### 17.1 Horizontal Scaling

A larger architecture may use:

    WebSocket Clients
           |
           v
      Load Balancer
           |
      +----+----+
      |         |
      v         v
    Server A  Server B
      |         |
      +----+----+
           |
           v
     Message Broker
           |
           v
     Application Services
           |
           v
       PostgreSQL

Each server manages its own connected sockets.

A client connected to Server A cannot automatically receive a message sent only to Server B.

A shared message-distribution mechanism can route application events across server instances.

### 17.2 Sticky Sessions

Some load-balancing configurations use sticky sessions to keep a client associated with a particular server.

This can simplify connection routing but does not solve all distributed messaging requirements.

Applications should still consider server failure, session recovery and shared event distribution.

### 17.3 Shared State

A distributed deployment must determine where to maintain:

- User presence.
- Session ownership.
- Connection metadata.
- Subscription information.
- Message acknowledgements.
- Reconnection state.
- Delivery retry records.

PostgreSQL provides durable relational storage. A message broker or distributed cache may be appropriate for high-volume event distribution and transient presence data.

## 18. Performance Considerations

WebSocket performance depends on more than the protocol itself.

Important factors include:

1. Number of simultaneous connections.
2. Average message size.
3. Message frequency.
4. Network round-trip time.
5. Event-loop utilization.
6. Application processing time.
7. Queue depth.
8. Database latency.
9. Heartbeat frequency.
10. Reconnection volume.

A useful monitoring model includes:

| Metric | Operational significance |
|---|---|
| Active connections | Current connection load |
| Connection establishment rate | Handshake demand |
| Connection failures | Transport reliability |
| Reconnection rate | Network or server instability |
| Messages per second | Communication throughput |
| Average message size | Bandwidth consumption |
| Queue depth | Backpressure |
| Heartbeat failures | Connection health |
| Acknowledgement latency | Application delivery performance |
| Close-code distribution | Termination analysis |

Performance testing should include normal traffic, peak traffic, mass disconnections and server recovery.

## 19. Important Protocol and Design Distinctions

| Concept | Meaning |
|---|---|
| TCP connection | Underlying reliable byte-stream transport |
| HTTP Upgrade | Establishes the WebSocket protocol |
| WebSocket connection | Persistent bidirectional communication channel |
| WebSocket frame | Protocol-level transmission unit |
| WebSocket message | One complete application payload transported through frames |
| Application event | Meaningful business or system operation |
| Heartbeat | Communication liveness check |
| Authentication | Establishes the identity of a connecting principal |
| Authorization | Determines permitted operations |
| Session | Application-level identity and continuity |
| Reconnection | Establishment of a replacement transport connection |
| Acknowledgement | Application-level confirmation |
| Backpressure | Control of data production and consumption rates |

Understanding these distinctions is essential when designing reliable real-time systems.

## 20. Implementation Limitations

The five implementations deliberately address different engineering layers.

| Implementation | Implemented | Not implemented |
|---|---|---|
| Python | Basic RFC 6455 server, handshake, frames, heartbeat and broadcast | TLS, extensions, compression, complete production authentication |
| JavaScript | Native WebSocket client, event processing, bounded queue and retry policy | Complete transport server and durable message storage |
| C++17 | Lifecycle engine, connection registry, session replacement and queue limits | Actual TCP and WebSocket networking |
| Java 17 | Enterprise domain model, policy enforcement and asynchronous event handling | Complete production network gateway |
| PostgreSQL | Relational lifecycle records, constraints, events, message queue and reporting | Socket communication and atomic network delivery |

The Python implementation is a limited protocol implementation for controlled learning and experimentation. It should not be treated as a substitute for a thoroughly tested production WebSocket library.

The C++ and Java implementations focus on connection-management architecture rather than duplicating the Python frame parser.

The PostgreSQL implementation demonstrates persistence and transaction boundaries. It does not guarantee successful network transmission.

## 21. Execution and Compatibility

| File | Requirement | Execution |
|---|---|---|
| Python | Python 3.10+ | `python websocket_server.py` |
| JavaScript | Node.js 22+ | `node websocket_client.js` |
| C++17 | C++17 compiler | `g++ -std=c++17 -O2 websocket.cpp -o websocket` |
| Java 17 | JDK 17 | `javac WebSocketEnterprise.java` followed by `java WebSocketEnterprise` |
| PostgreSQL | PostgreSQL 15+ | Execute the SQL script using `psql` |

The Python and JavaScript applications are designed to communicate using the same demonstration endpoint:

`ws://127.0.0.1:8765`

Start the Python server before running the JavaScript client.

The C++ and Java applications run their respective connection-management demonstrations independently.

The PostgreSQL script creates the relational schema, constraints, functions, procedures, triggers, sample records and operational reports.

## 22. Engineering Principles

The implementations demonstrate several principles applicable to real-time systems:

- A persistent connection requires explicit lifecycle management.
- A successful handshake does not establish application authorization.
- Transport-level delivery and business-level acknowledgement are different.
- Reconnection requires a new transport connection.
- Message queues must have resource limits.
- Heartbeat mechanisms should distinguish transport liveness from application health.
- Connection state and message state should be modeled independently.
- Concurrent message processing requires controlled state updates.
- Distributed deployments require shared event-distribution mechanisms.
- Durable message delivery requires application-level retry and acknowledgement design.
- Observability should capture connection transitions, failures and message behaviour.

These principles form the foundation of reliable WebSocket-based applications, including collaboration platforms, notification systems, trading dashboards, monitoring systems and interactive enterprise services.
