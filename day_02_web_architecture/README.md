# Web Architecture

## Introduction

Web architecture is the structure through which web applications, services, networks, databases, and supporting infrastructure work together to serve users.

A simple website may consist of a browser, a web server, an application, and a database. A large production system can contain DNS, CDNs, load balancers, reverse proxies, API gateways, application servers, caches, databases, message queues, search systems, object storage, authentication systems, monitoring platforms, and deployment infrastructure.

The important part of web architecture is not learning these components independently. It is understanding how they interact, why they exist, what responsibility each component has, and what trade-offs appear when a system becomes larger.

---

## Client and Server

The basic web model is based on communication between a client and a server.

The client normally initiates a request. A server receives the request, processes it, and returns a response.

A browser is a common client. It can request HTML, CSS, JavaScript, images, APIs, and other resources.

The server may perform several operations before returning a response. It may authenticate the user, execute business logic, retrieve information from a database, access a cache, call another service, or place work into a queue.

The client should generally not communicate directly with the database. The application server provides an abstraction and security boundary between the client and persistent data.

---

## URL Structure

A URL identifies a resource or destination on the Web.

A typical URL contains several components:

* Scheme
* Host
* Port
* Path
* Query string
* Fragment

For example:

`https://example.com:443/products/42?sort=price#reviews`

The scheme identifies the communication protocol.

The hostname identifies the destination.

The port identifies the network service.

The path identifies a resource or route.

The query string provides additional parameters.

The fragment is generally handled by the client and is not sent to the server as part of an ordinary HTTP request.

---

## DNS

DNS stands for Domain Name System.

It provides the naming mechanism that connects human-readable domain names to network addresses.

Instead of requiring users to remember an IP address, applications can use a domain such as:

`example.com`

DNS can resolve the domain to an appropriate network destination.

The DNS hierarchy contains root servers, top-level domain infrastructure, and authoritative name servers. DNS resolvers perform lookups on behalf of clients and frequently cache results.

Important DNS record types include:

* `A` for IPv4 addresses
* `AAAA` for IPv6 addresses
* `CNAME` for aliases
* `MX` for mail servers
* `TXT` for text and verification information
* `NS` for authoritative name servers

DNS caching is controlled partly through TTL, or Time To Live.

A longer TTL can reduce lookup traffic but means changes may take longer to propagate through caches.

---

## Network Layers

Web communication is built on multiple networking layers.

A simplified structure is:

```text
Application
    |
   HTTP
    |
Transport
    |
   TCP / UDP
    |
Internet
    |
    IP
```

Modern Web communication can use HTTP/1.1 over TCP, HTTP/2 over TCP, or HTTP/3 over QUIC.

Layering allows different responsibilities to remain separated.

HTTP handles application-level web communication.

TCP or QUIC handles transport behavior.

IP handles addressing and routing.

This separation allows protocols to evolve independently.

---

## TCP and UDP

TCP provides reliable, ordered communication.

It includes mechanisms for retransmission, congestion control, and connection management.

UDP is a simpler connectionless transport mechanism.

HTTP/3 uses QUIC, which operates over UDP while providing modern transport capabilities such as reliable streams, encryption integration, and improved connection behavior.

The choice of transport influences latency, reliability, connection establishment, and application behavior.

---

## HTTP

HTTP is the primary application protocol used by the Web.

An HTTP request generally contains:

* Method
* Target
* Headers
* Optional body

An HTTP response generally contains:

* Status code
* Headers
* Optional body

For example:

```text
GET /products/42 HTTP/1.1
Host: example.com
Accept: application/json
```

The server may respond with:

```text
HTTP/1.1 200 OK
Content-Type: application/json

{"id":42,"name":"Laptop"}
```

HTTP provides a standard communication interface between clients and servers.

---

## HTTP Methods

Important HTTP methods include:

### GET

Used to retrieve information.

### POST

Used to submit data or request processing or creation.

### PUT

Used to replace a resource representation.

### PATCH

Used to partially modify a resource.

### DELETE

Used to delete a resource.

### HEAD

Used to retrieve response metadata without the normal response body.

### OPTIONS

Used to discover communication options.

Two important properties are safety and idempotency.

A safe operation is intended not to modify server state.

An idempotent operation produces the same intended server state when repeated.

This becomes important in distributed systems because network failures can cause clients to retry requests.

---

## HTTP Status Codes

HTTP status codes communicate the result of a request.

### 1xx

Informational responses.

### 2xx

Successful responses.

Examples include:

* `200 OK`
* `201 Created`
* `204 No Content`

### 3xx

Redirection and caching-related responses.

Examples include:

* `301 Moved Permanently`
* `302 Found`
* `304 Not Modified`

### 4xx

Problems associated with the request or client context.

Examples include:

* `400 Bad Request`
* `401 Unauthorized`
* `403 Forbidden`
* `404 Not Found`
* `409 Conflict`
* `429 Too Many Requests`

### 5xx

Server-side failures.

Examples include:

* `500 Internal Server Error`
* `502 Bad Gateway`
* `503 Service Unavailable`
* `504 Gateway Timeout`

Status codes allow clients and infrastructure components to understand the outcome of an operation without knowing the internal implementation.

---

## HTTP Headers

HTTP headers contain metadata.

Important examples include:

* `Content-Type`
* `Content-Length`
* `Authorization`
* `Accept`
* `Cache-Control`
* `User-Agent`
* `Origin`

Headers can describe content, authentication information, caching rules, browser context, and other properties of a request or response.

---

## Cookies and Sessions

HTTP is fundamentally stateless.

A server does not automatically remember previous HTTP requests.

Web applications frequently need to associate multiple requests with the same user.

Cookies provide one mechanism for maintaining this association.

A browser can store a session identifier and send it with subsequent requests.

The server can then use the identifier to retrieve server-side session information.

Another approach is to use tokens that carry authenticated claims.

Both approaches have different implications for security, scalability, revocation, storage, and operational complexity.

---

## Authentication and Authorization

Authentication answers:

> Who are you?

Authorization answers:

> What are you allowed to do?

For example, a user may successfully authenticate as a particular account but still be unauthorized to delete another user's information.

A web application therefore normally treats identity verification and permission checking as separate concerns.

---

## The Web Request Lifecycle

A web request can involve many stages.

A simplified flow is:

```text
User
 |
 v
Browser
 |
 v
DNS
 |
 v
Network Connection
 |
 v
TLS
 |
 v
HTTP Request
 |
 v
CDN / Edge
 |
 v
Load Balancer
 |
 v
Reverse Proxy
 |
 v
Application
 |
 v
Cache
 |
 v
Database / Other Services
 |
 v
HTTP Response
 |
 v
Browser
```

The actual architecture may be much more complicated.

A single user action can generate multiple network requests for HTML, CSS, JavaScript, images, API calls, fonts, and other resources.

---

## Three-Tier Architecture

A classic three-tier architecture contains:

```text
Presentation Tier
        |
        v
Application Tier
        |
        v
Data Tier
```

The presentation tier manages the user-facing interface.

The application tier contains business logic and request processing.

The data tier manages persistent information.

This separation prevents the user interface from becoming directly dependent on database implementation details.

---

## N-Tier Architecture

N-tier architecture extends the concept of logical separation.

A system may contain:

```text
Presentation
    |
API Gateway
    |
Authentication
    |
Business Logic
    |
Cache
    |
Data Access
    |
Database
```

These are logical layers. They do not necessarily need to run on separate machines.

The purpose of layering is to establish responsibilities and boundaries.

---

## Monolithic Architecture

A monolithic application is deployed as one primary application unit.

A monolith can contain many internal modules:

```text
Application
 |
 +-- Users
 +-- Orders
 +-- Payments
 +-- Reporting
 +-- Administration
```

A monolith can be simple to deploy, test, debug, and operate.

It can also become difficult to scale when unrelated modules have different resource requirements.

The existence of a monolith does not automatically indicate poor architecture.

A well-designed modular monolith can maintain strong internal boundaries while retaining a simple deployment model.

---

## Modular Monolith

A modular monolith remains one deployable application while maintaining internal separation.

For example:

```text
Application
 |
 +-- User Module
 +-- Order Module
 +-- Payment Module
 +-- Reporting Module
```

Modules communicate through defined interfaces rather than unrestricted access to each other's internals.

This approach can provide architectural structure without immediately introducing distributed-system complexity.

---

## Microservices

Microservices divide an application into independently deployable services.

For example:

```text
API Gateway
 |
 +-- User Service
 |
 +-- Order Service
 |
 +-- Payment Service
```

Each service normally owns a specific responsibility.

Potential benefits include:

* Independent deployment
* Independent scaling
* Fault isolation
* Team autonomy
* Technology flexibility

Potential costs include:

* Network communication
* Distributed transactions
* Service discovery
* Observability complexity
* Data consistency problems
* Deployment complexity
* More infrastructure

Microservices do not remove complexity. They redistribute complexity from inside one application to the boundaries between multiple applications.

---

## APIs

An API provides a defined interface through which software components communicate.

For example:

```text
GET /users/42
```

The client does not need to know how the user is stored internally.

An API normally defines:

* Resources
* Operations
* Request formats
* Response formats
* Authentication
* Authorization
* Errors
* Versioning
* Rate limits
* Idempotency behavior

---

## REST

REST is an architectural style based on several constraints.

Important ideas include:

* Client-server separation
* Stateless interactions
* Cacheability
* Uniform interface
* Layered systems
* Resource-oriented design

A REST-style API may use:

```text
GET    /users/42
PATCH  /users/42
DELETE /users/42
```

REST is not simply another name for JSON over HTTP.

JSON is a data representation.

HTTP is a communication protocol.

REST is an architectural style.

---

## GraphQL

GraphQL allows clients to specify the data they need.

Traditional REST APIs may require multiple requests to retrieve related information.

GraphQL can allow a client to request several related fields through one query.

Potential benefits include:

* Client-controlled data selection
* Reduced over-fetching
* Reduced under-fetching

Potential challenges include:

* Query complexity
* Authorization at field level
* Caching complexity
* Resource exhaustion
* More complicated server-side execution

---

## RPC and gRPC

RPC means Remote Procedure Call.

It allows a program to invoke an operation provided by another system.

The call may look conceptually similar to a local function call even though a network request occurs underneath.

gRPC is a modern RPC framework often used for service-to-service communication.

RPC is particularly useful when services require strongly defined contracts and efficient communication.

---

## Web Servers

A web server receives network requests and can serve static resources or forward dynamic requests to application servers.

Typical responsibilities include:

* HTTP handling
* Static file delivery
* TLS termination
* Compression
* Proxying
* Routing
* Connection management

A web server can therefore act as an important boundary between the public Internet and application logic.

---

## Reverse Proxy

A reverse proxy represents backend servers to clients.

The architecture is:

```text
Client
 |
 v
Reverse Proxy
 |
 +-- Backend A
 +-- Backend B
 +-- Backend C
```

A reverse proxy can provide:

* Routing
* TLS termination
* Load balancing
* Caching
* Compression
* Request filtering
* Header manipulation

It also hides internal server topology from external clients.

---

## Forward Proxy

A forward proxy represents clients.

```text
Client
 |
 v
Forward Proxy
 |
 v
Internet
```

A reverse proxy represents servers:

```text
Internet
 |
 v
Reverse Proxy
 |
 v
Servers
```

The distinction is based on which side the proxy represents.

---

## Load Balancing

A load balancer distributes requests across multiple backend instances.

```text
             Load Balancer
              /    |    \
             /     |     \
            v      v      v
         Server  Server  Server
```

Load balancing provides:

* Increased capacity
* Horizontal scaling
* Fault tolerance
* Better traffic distribution
* Maintenance flexibility

Common algorithms include:

* Round Robin
* Weighted Round Robin
* Least Connections
* Random
* IP Hash
* Consistent Hashing

The correct algorithm depends on request cost, backend capacity, session behavior, and traffic characteristics.

---

## Vertical and Horizontal Scaling

Vertical scaling means increasing the resources of a machine.

For example:

```text
4 CPU -> 16 CPU
16 GB RAM -> 64 GB RAM
```

Horizontal scaling means adding more instances:

```text
Server A
Server B
Server C
Server D
```

Horizontal scaling is common in highly available web applications.

It creates additional requirements such as load balancing, state management, service discovery, centralized logging, and distributed caching.

---

## Auto Scaling

Auto scaling changes the number of running instances according to workload.

Signals may include:

* CPU usage
* Memory usage
* Request rate
* Queue depth
* Latency
* Application-specific metrics

Auto scaling allows capacity to follow changing demand.

---

## Caching

Caching stores reusable information so that expensive work does not have to be repeated.

Without caching:

```text
Application
 |
 v
Database
```

With caching:

```text
Application
 |
 v
Cache
 |
 +-- Hit --> Return
 |
 +-- Miss --> Database
```

Caching can reduce:

* Latency
* Database load
* Network traffic
* Repeated computation

Caching also introduces new problems:

* Stale data
* Invalidation
* Expiration
* Eviction
* Hot keys
* Cache stampedes

---

## Cache Strategies

Important caching strategies include:

### Cache Aside

The application checks the cache first and loads data from the database after a cache miss.

### Read Through

The cache layer automatically retrieves missing data.

### Write Through

Writes pass through the cache and are persisted immediately.

### Write Back

Writes enter the cache and are persisted later.

### Write Around

Writes bypass the cache and go directly to persistent storage.

The correct strategy depends on the workload and consistency requirements.

---

## Cache Eviction

Caches have finite capacity.

Common eviction approaches include:

* LRU
* LFU
* FIFO
* TTL expiration

LRU means Least Recently Used.

LFU means Least Frequently Used.

TTL means entries expire after a defined amount of time.

---

## CDN

A Content Delivery Network distributes content through geographically distributed edge locations.

Without a CDN:

```text
User
 |
 v
Distant Origin
```

With a CDN:

```text
User
 |
 v
Nearby Edge
 |
 v
Origin if necessary
```

CDNs are especially effective for:

* Images
* JavaScript
* CSS
* Fonts
* Videos
* Static HTML
* Some cacheable API responses

A CDN reduces geographic latency and decreases load on origin infrastructure.

---

## Database Architecture

Databases provide persistent application state.

A simple architecture is:

```text
Application
 |
 v
Database
```

A larger system may use:

```text
Application
 |
 +-- Cache
 |
 +-- Primary Database
       |
       +-- Read Replica
       +-- Read Replica
```

Databases are often harder to scale than stateless application servers because they contain persistent state and consistency requirements.

---

## SQL and NoSQL

Relational databases organize information using tables, relationships, schemas, and transactions.

NoSQL is a broad category that includes:

* Key-value stores
* Document databases
* Column-family databases
* Graph databases

The database choice should follow the workload, access pattern, consistency requirements, and operational requirements.

---

## Database Replication

Replication creates multiple copies of data.

A primary database can replicate information to one or more replicas.

Replication can improve:

* Read capacity
* Availability
* Disaster recovery
* Geographic distribution

It can also introduce replication lag and consistency challenges.

---

## Read Replicas

Read replicas allow read operations to be distributed across multiple database instances.

Writes generally go to a primary database.

Reads can be distributed to replicas.

The main architectural concern is that replicas may temporarily lag behind the primary.

Therefore, operations requiring immediate read-after-write consistency may need to read from the primary.

---

## Database Sharding

Sharding divides data across multiple database partitions.

For example:

```text
Shard 1 -> User group A
Shard 2 -> User group B
Shard 3 -> User group C
```

A shard key determines where data is stored.

A good shard key distributes data evenly.

A poor shard key can create hotspots.

Sharding increases capacity but makes cross-shard queries, transactions, and operational management more complicated.

---

## Connection Pooling

Creating a new database connection for every request can be expensive.

Connection pooling maintains reusable connections.

```text
Application
 |
 v
Connection Pool
 |
 +-- Connection
 +-- Connection
 +-- Connection
 |
 v
Database
```

Requests acquire connections when needed and release them afterward.

Connection pools must be sized carefully.

A pool that is too small can create waiting.

A pool that is too large can overwhelm the database.

---

## Transactions

Transactions group database operations into a logical unit.

ACID represents four important transaction properties:

### Atomicity

All operations succeed or the transaction is rolled back.

### Consistency

Transactions preserve valid data constraints.

### Isolation

Concurrent transactions should not incorrectly interfere.

### Durability

Committed data survives appropriate failures.

For example, a bank transfer may require:

```text
Debit Account A
Credit Account B
```

Both operations belong to one logical transaction.

---

## Transaction Isolation

Concurrent transactions can produce phenomena such as:

* Dirty Reads
* Non-repeatable Reads
* Phantom Reads

Database systems provide isolation levels such as:

* Read Uncommitted
* Read Committed
* Repeatable Read
* Serializable

Stronger isolation generally provides stronger correctness guarantees but may reduce concurrency.

---

## CAP Theorem

CAP concerns distributed systems.

The three properties are:

* Consistency
* Availability
* Partition Tolerance

A network partition occurs when distributed components cannot reliably communicate.

When a partition occurs, a distributed system has to make a trade-off between continuing to serve requests and maintaining certain consistency guarantees.

The practical lesson is that network partitions must be expected and system behavior during partitions must be deliberately designed.

---

## Consistency Models

Strong consistency means reads provide strong guarantees about the latest committed state.

Eventual consistency allows temporary differences between replicas as long as they eventually converge.

Read-after-write consistency ensures that after a successful write, subsequent reads under the specified guarantee can observe that write.

Different data may require different consistency guarantees.

Financial information may require stronger guarantees than analytics or recommendation data.

---

## Message Queues

A message queue separates producers from consumers.

```text
Producer
 |
 v
Queue
 |
 v
Consumer
```

Queues are useful for:

* Email
* Notifications
* Video processing
* Image processing
* Report generation
* Background jobs
* Data pipelines

The producer does not need to wait for the consumer to finish.

Queues provide buffering and decoupling.

---

## Event-Driven Architecture

In an event-driven system, services communicate through events.

For example:

```text
Order Service
 |
 | OrderCreated
 v
Event Bus
 /      \
v        v
Email   Inventory
```

Advantages include:

* Loose coupling
* Asynchronous processing
* Independent consumers
* Extensibility

Challenges include:

* Event ordering
* Duplicate events
* Event schema evolution
* Eventual consistency
* Replay
* Debugging

---

## Publish-Subscribe

Publish-subscribe allows multiple subscribers to receive an event.

For example:

```text
OrderCreated
 |
 +-- Email Service
 |
 +-- Analytics Service
 |
 +-- Inventory Service
```

The producer does not need direct knowledge of every consumer.

This provides a strong form of decoupling.

---

## Asynchronous Processing

Synchronous processing requires the caller to wait.

```text
Request
 |
 v
Task A
 |
 v
Task B
 |
 v
Response
```

Asynchronous processing can return earlier:

```text
Request
 |
 v
Queue
 |
 v
Immediate Response

Worker
 |
 v
Processing
```

This is useful for long-running or non-urgent operations.

---

## WebSockets

WebSockets provide persistent two-way communication.

```text
Client <================> Server
```

They are useful for:

* Chat
* Live dashboards
* Collaborative applications
* Real-time notifications
* Multiplayer systems

WebSocket architectures must handle connection limits, authentication, reconnection, heartbeats, load balancing, and scaling.

---

## Server-Sent Events

Server-Sent Events allow a server to continuously send events to a browser over an HTTP connection.

They are useful for:

* Notifications
* Progress updates
* Live status
* Streaming content

Unlike WebSockets, SSE is primarily server-to-client communication.

---

## Long Polling

Long polling keeps an HTTP request open until new data is available or a timeout occurs.

After receiving a response, the client sends another request.

It can simulate real-time behavior but generally has more overhead than persistent modern communication mechanisms.

---

## Background Jobs

Background jobs move expensive operations outside the interactive request path.

Examples include:

* Sending emails
* Generating reports
* Processing videos
* Resizing images
* Sending notifications
* Running data processing tasks

A typical architecture is:

```text
API
 |
 v
Queue
 |
 v
Worker
 |
 v
Result / Storage
```

---

## Object Storage

Large binary files are often better stored in object storage than in a relational database.

Examples include:

* Images
* Videos
* Documents
* Backups
* Large datasets

A scalable upload architecture can allow the client to upload directly to object storage using an authorization mechanism provided by the application.

The application can store metadata while object storage handles the large file.

---

## Search Architecture

Search engines are optimized for operations such as:

* Full-text search
* Relevance ranking
* Fuzzy matching
* Autocomplete
* Faceting

A search index can be derived from primary application data.

For example:

```text
Primary Database
 |
 v
Search Index
```

This creates synchronization and eventual-consistency considerations.

---

## Rate Limiting

Rate limiting controls how frequently a client can perform operations.

For example:

```text
100 requests per minute
```

Rate limiting can protect:

* APIs
* Databases
* External services
* Shared infrastructure

Common approaches include:

* Fixed Window
* Sliding Window
* Token Bucket
* Leaky Bucket

Rate limiting can be applied per IP, user, API key, organization, tenant, or endpoint.

---

## Idempotency

Idempotency is particularly important in distributed systems.

Suppose a payment request succeeds on the server but the response is lost due to a network failure.

The client retries.

Without idempotency protection, the payment could be processed twice.

An idempotency key allows the server to associate repeated requests with the same logical operation.

This is important for:

* Payments
* Orders
* Reservations
* Financial transactions

---

## Timeouts

Every network dependency should have an appropriate timeout.

Without timeouts, one slow dependency can cause requests to remain blocked for long periods.

A chain such as:

```text
Service A
 |
 v
Service B
 |
 v
Service C
```

can experience cascading delays if Service C becomes slow.

Timeouts limit the amount of time one component waits for another.

---

## Retries

Temporary failures can sometimes be handled by retries.

Immediate unlimited retries are dangerous because they can increase load on an already failing service.

Exponential backoff increases the delay between retries:

```text
1 second
2 seconds
4 seconds
8 seconds
16 seconds
```

Jitter introduces randomness so that large numbers of clients do not retry at exactly the same moment.

Retries should be limited and should only be used where repeated operations are safe.

---

## Circuit Breakers

A circuit breaker protects a system from repeatedly calling an unhealthy dependency.

It normally has three states:

### Closed

Requests flow normally.

### Open

Requests are blocked quickly because the dependency is considered unhealthy.

### Half-Open

Limited requests are allowed to test whether the dependency has recovered.

Circuit breakers reduce cascading failures and unnecessary waiting.

---

## Health Checks

Health checks allow infrastructure to determine whether an application instance is usable.

A liveness check asks whether the process is alive.

A readiness check asks whether the application is ready to receive traffic.

An application can be alive but not ready because a required dependency is unavailable or initialization has not completed.

---

## Observability

Observability allows engineers to understand system behavior through telemetry.

Three major categories are:

* Logs
* Metrics
* Traces

Logs describe events.

Metrics provide numerical measurements.

Traces show how requests move through distributed components.

---

## Logging

In a distributed application, logs should normally be centralized.

Instead of relying on individual machines:

```text
Server A -> Local Log
Server B -> Local Log
Server C -> Local Log
```

a centralized architecture can collect logs into a common system.

Useful log information includes:

* Timestamp
* Request ID
* Trace ID
* Endpoint
* Status code
* Latency
* Error information

Sensitive information should not be logged unnecessarily.

---

## Metrics

Important web architecture metrics include:

* Request rate
* Error rate
* Latency
* CPU utilization
* Memory usage
* Queue depth
* Database connections

Latency is often analyzed using percentiles.

`p50` represents the median.

`p95` means 95% of requests are at or below that latency.

`p99` means 99% of requests are at or below that latency.

Percentiles are useful because averages can hide slow requests.

---

## Distributed Tracing

A distributed request may travel through:

```text
API Gateway
 |
 v
Order Service
 |
 v
Payment Service
 |
 v
Database
```

Distributed tracing assigns a trace identity and records individual spans.

This allows engineers to determine which component contributed most to latency or failure.

---

## HTTPS and TLS

HTTPS means HTTP over TLS.

TLS provides:

* Encryption
* Authentication of the server
* Integrity protection

TLS protects communication while it travels across networks.

It does not automatically make the application itself secure.

Application-level security still requires authentication, authorization, input validation, secure session management, and other controls.

---

## JWT

JWT stands for JSON Web Token.

A JWT commonly contains:

* Header
* Payload
* Signature

The payload can contain claims such as:

* Subject
* Expiration
* Issuer
* Role

A signed JWT allows a server to verify integrity and authenticity according to the signing arrangement.

A signed JWT is not automatically encrypted.

Therefore, confidential information should not be placed in a token merely because the token is signed.

---

## OAuth

OAuth is an authorization framework for delegated access.

A simplified architecture is:

```text
User
 |
 v
Authorization Server
 |
 v
Access Token
 |
 v
Resource Server
```

OAuth allows an application to obtain delegated access without necessarily receiving the user's password.

Authentication and identity are separate concerns, with OpenID Connect commonly used for identity-related functionality on top of OAuth.

---

## CORS

CORS stands for Cross-Origin Resource Sharing.

Browsers enforce a same-origin security model.

An origin is determined by:

* Scheme
* Host
* Port

Two different origins cannot automatically access each other's resources through browser JavaScript.

CORS allows a server to declare which browser origins may access specific resources.

CORS is a browser security mechanism and is not an authentication system.

---

## CSRF

Cross-Site Request Forgery attempts to cause an authenticated browser to perform an unwanted action.

Important defenses can include:

* CSRF tokens
* SameSite cookies
* Origin checks
* Appropriate request validation

CSRF is particularly important when browser credentials are automatically attached to requests.

---

## XSS

Cross-Site Scripting occurs when attacker-controlled content is interpreted as executable browser-side code.

Common defenses include:

* Output encoding
* Safe templating
* Content Security Policy
* Avoiding unsafe HTML insertion
* Correct handling of user-controlled data

The central architectural idea is that untrusted input must be handled according to the context in which it is used.

---

## SQL Injection

SQL injection occurs when untrusted input changes the intended meaning of a database query.

Unsafe construction conceptually looks like combining raw user input directly into SQL.

Parameterized queries separate SQL structure from user data.

ORMs can help, but using an ORM does not automatically eliminate every injection vulnerability.

---

## DDoS

Distributed Denial-of-Service attacks attempt to consume resources so legitimate users cannot access a service.

Protection can include:

* CDN infrastructure
* Edge filtering
* Rate limiting
* Traffic analysis
* Load balancing
* Capacity planning
* Network controls

Filtering traffic at the edge is particularly valuable because malicious traffic can be blocked before consuming expensive application resources.

---

## Secrets Management

Secrets include:

* Database passwords
* API keys
* Signing keys
* Encryption keys
* Service credentials

Secrets should not normally be hard-coded into application source code.

A secure architecture separates application code from secret material.

Secret management includes:

* Storage
* Access control
* Rotation
* Expiration
* Auditing

---

## Zero Trust

Zero-trust architecture avoids automatically trusting requests simply because they originate from an internal network.

Requests should be evaluated according to identity, permissions, context, and other appropriate security controls.

A private network does not automatically make a request trustworthy.

---

## Deployment Architecture

Production systems generally use several environments, such as:

* Development
* Testing
* Staging
* Production

A deployment pipeline may look like:

```text
Developer
 |
 v
Git Repository
 |
 v
Build
 |
 v
Tests
 |
 v
Security Checks
 |
 v
Artifact
 |
 v
Deployment
 |
 v
Production
```

Automating this process improves repeatability and reduces manual deployment errors.

---

## Containers

Containers package applications and their runtime requirements into standardized execution environments.

A container image can contain:

* Application
* Runtime
* Dependencies
* Required configuration structure

Containers improve consistency between development, testing, and production environments.

---

## Container Orchestration

When an application contains many containers, manual management becomes difficult.

An orchestration platform can manage:

* Scheduling
* Scaling
* Health checks
* Service discovery
* Restart behavior
* Networking
* Rolling deployments

A cluster can distribute workloads across multiple machines.

---

## CI/CD

Continuous Integration focuses on frequently integrating changes and automatically validating them.

Continuous Delivery or Deployment automates the path toward production.

A pipeline may include:

1. Source control
2. Build
3. Automated testing
4. Security checks
5. Artifact creation
6. Deployment
7. Monitoring

---

## Blue-Green Deployment

Blue-green deployment maintains two environments.

```text
Blue  -> Current version
Green -> New version
```

Traffic initially goes to Blue.

The new version is deployed to Green.

After validation, traffic is switched to Green.

If necessary, traffic can be returned to Blue.

---

## Canary Deployment

Canary deployment gradually exposes a new version to users.

For example:

```text
95% -> Version A
5%  -> Version B
```

If the new version performs well, its traffic percentage can increase.

Canary deployments reduce the impact of defective releases.

---

## Rolling Deployment

A rolling deployment gradually replaces old application instances.

```text
Old Old Old Old

New Old Old Old

New New Old Old

New New New Old

New New New New
```

During the transition, old and new versions may coexist.

This makes backward-compatible APIs and schemas important.

---

## High Availability

High availability attempts to keep a service operational despite expected failures.

A single server is a potential single point of failure.

Multiple instances behind a load balancer provide redundancy.

```text
Load Balancer
    /     \
   v       v
Server A Server B
```

If one instance fails, traffic can be sent to another healthy instance.

---

## Fault Tolerance

Fault tolerance means the system can continue operating when components fail.

Potential failures include:

* Server crashes
* Network failures
* Database failures
* Dependency outages
* Disk failures
* Availability-zone failures

Techniques include:

* Redundancy
* Replication
* Failover
* Timeouts
* Retries
* Circuit breakers
* Queues
* Graceful degradation
* Backups

---

## Disaster Recovery

Disaster recovery focuses on recovering service after severe failures.

Two important concepts are:

### RPO

Recovery Point Objective describes how much data loss can be tolerated.

### RTO

Recovery Time Objective describes how quickly the service should be restored.

For example:

```text
RPO = 5 minutes
RTO = 30 minutes
```

These are business and architectural requirements, not merely technical metrics.

---

## Multi-Region Architecture

A multi-region architecture operates infrastructure in multiple geographic locations.

```text
Global Traffic
      |
 +----+----+
 |         |
 v         v
Region A Region B
```

Benefits include:

* Geographic resilience
* Lower latency
* Disaster recovery

Challenges include:

* Data replication
* Consistency
* Routing
* Cross-region latency
* Operational complexity
* Cost

---

## Latency

Latency represents the time required to complete an operation.

Web request latency can contain:

* DNS time
* Connection establishment
* TLS negotiation
* Network transfer
* Load balancer processing
* Application processing
* Database processing
* External API processing
* Serialization
* Queueing

Total latency is therefore an end-to-end property.

---

## Throughput

Throughput measures how much work a system can process over time.

Examples include:

* Requests per second
* Transactions per second
* Messages per second
* Megabytes per second

High throughput does not necessarily mean low latency.

A system can process large amounts of work while individual operations remain slow.

---

## Availability

Availability represents how much of the observed period a service remains operational.

Conceptually:

```text
Availability =
Uptime / Total Observed Time
```

Higher availability targets require increasing levels of redundancy, testing, monitoring, and recovery capability.

---

## Reliability

Reliability concerns whether a system behaves correctly and predictably over time.

A service that is reachable but frequently produces incorrect results is not reliable.

Reliability includes:

* Correctness
* Failure handling
* Recovery
* Data durability
* Predictability

---

## Performance

Web performance can be improved through:

* CDN caching
* Browser caching
* Compression
* Database indexing
* Query optimization
* Connection pooling
* Asynchronous processing
* Smaller payloads
* Fewer network requests
* Efficient application code

Performance optimization should be based on measured bottlenecks.

---

## Bottlenecks

A bottleneck is a component that limits system capacity.

Potential bottlenecks include:

* CPU
* Memory
* Database
* Network
* Disk
* Connection pools
* Thread pools
* External APIs
* Queues
* Lock contention

Adding more application servers does not solve a database bottleneck if the database is already operating at its capacity.

---

## Backpressure

Backpressure occurs when producers generate work faster than consumers can process it.

For example:

```text
Producer: 10,000 messages/sec
Consumer: 2,000 messages/sec
```

The queue grows.

A robust system must have mechanisms to handle this condition.

Possible responses include:

* Slowing producers
* Rejecting requests
* Scaling consumers
* Prioritizing important work
* Dropping low-value work
* Applying rate limits

---

## Graceful Degradation

Not every component has the same importance.

For example:

```text
Product Page
 |
 +-- Product Data
 |
 +-- Reviews
 |
 +-- Recommendations
```

If recommendations fail, the main product page may still be usable.

This is graceful degradation.

The architecture separates critical dependencies from optional dependencies.

---

## Service Discovery

In dynamic environments, application instances can change frequently.

Instead of hard-coding server addresses, services can discover available instances dynamically.

Service discovery can be implemented using:

* DNS
* Service registries
* Container orchestration platforms
* Platform-native networking

---

## API Gateway

An API gateway provides a controlled entry point into backend services.

```text
Client
 |
 v
API Gateway
 |
 +-- User Service
 +-- Order Service
 +-- Payment Service
```

Possible responsibilities include:

* Authentication
* Authorization
* Routing
* Rate limiting
* Logging
* Request transformation
* Aggregation
* TLS termination

An API gateway must itself be highly available because it sits in a critical request path.

---

## Backend for Frontend

Backend for Frontend, or BFF, creates backend interfaces specifically for different client types.

For example:

```text
Mobile App -> Mobile BFF
Web App    -> Web BFF
```

Both BFFs can communicate with common backend services.

This allows mobile and web clients to receive data shaped according to their particular needs.

---

## Database Indexing

Indexes help databases locate records efficiently.

Without a useful index, the database may need to examine many rows.

With an appropriate index, the database can find relevant records much faster.

Indexes improve reads but have costs:

* Storage
* Write overhead
* Maintenance
* Memory consumption

Index design should be based on actual query patterns.

---

## Database Normalization

Normalization organizes relational data to reduce inappropriate duplication and update anomalies.

For example, customer information can be stored separately from orders and referenced through relationships.

Normalization improves integrity.

Denormalization may sometimes be used to improve read performance.

The decision involves a trade-off between data consistency, maintainability, query efficiency, and performance.

---

## N+1 Query Problem

The N+1 problem occurs when an application performs one query to retrieve a collection and then one additional query for each item.

For example:

```text
1 query -> retrieve 100 orders

100 queries -> retrieve each order's customer
```

Total:

```text
101 queries
```

Possible solutions include:

* Joins
* Batching
* Eager loading
* Caching
* Better data-access patterns

---

## Distributed Transactions

Microservices frequently use separate databases.

An operation may therefore span multiple services.

For example:

```text
Order Service -> Order Database

Payment Service -> Payment Database
```

A single traditional database transaction cannot automatically cover both databases.

Distributed transaction approaches exist, but they introduce complexity.

Another approach is a saga, in which a sequence of operations is coordinated and compensating actions are used when later operations fail.

---

## Eventual Consistency

In a distributed system, replicas may temporarily contain different values.

For example:

```text
Primary:
name = New Name

Replica:
name = Old Name
```

After replication catches up:

```text
Replica:
name = New Name
```

This may be acceptable for search, analytics, recommendations, and other derived information.

It may not be acceptable for financial balances or security permissions.

---

## Layered Caching

Large systems can contain several cache layers:

```text
Browser Cache
 |
 v
CDN Cache
 |
 v
Reverse Proxy Cache
 |
 v
Application Cache
 |
 v
Database
```

Each layer has different capacity, location, lifetime, invalidation behavior, and consistency characteristics.

Layered caching can significantly reduce origin load.

---

## Cache Stampede

A cache stampede occurs when a popular cache entry expires and many requests simultaneously attempt to regenerate it.

For example:

```text
10,000 requests
      |
      v
Cache Miss
      |
      v
10,000 Database Queries
```

Request collapsing can allow one request to refresh the cache while other requests reuse the result.

---

## Hot Keys

A hot key is a disproportionately popular cache or database key.

One product, user, or object may receive far more traffic than other records.

Possible solutions include:

* Local caching
* Replication
* Request coalescing
* CDN caching
* Key distribution techniques

---

## Static and Dynamic Content

Static content can usually be served without executing business logic for every request.

Examples:

* CSS
* JavaScript
* Images
* Fonts

Dynamic content depends on changing state or request context.

Examples:

* Account balances
* Personalized dashboards
* Order status

Static content is highly cacheable.

Dynamic content can also be cached, but the cache must account for personalization and freshness.

---

## Client-Side Rendering

Client-side rendering sends application resources to the browser, where JavaScript builds much of the interface.

This can provide rich interactivity but may require more client-side computation.

---

## Server-Side Rendering

Server-side rendering generates HTML on the server.

The browser receives already-rendered content.

It can improve initial content delivery and can be useful for search engine visibility, but it adds server-side rendering work.

---

## Static Site Generation

Static site generation produces pages ahead of time.

The generated files can be distributed efficiently through CDNs.

This works particularly well for content that changes relatively infrequently.

Modern applications can combine client-side rendering, server-side rendering, and static generation.

---

## HTTP/1.1, HTTP/2 and HTTP/3

HTTP/1.1 uses a text-based protocol and persistent connections.

HTTP/2 introduces binary framing, multiplexing, and header compression.

HTTP/3 uses QUIC and is built over UDP.

The evolution of HTTP has focused heavily on reducing latency, improving multiplexing, improving connection behavior, and making better use of modern networks.

---

## Compression

Compression reduces the size of data transferred over the network.

Common compression methods include:

* Gzip
* Brotli

Compression is especially useful for:

* HTML
* CSS
* JavaScript
* JSON

Compression reduces bandwidth usage but requires CPU for compression and decompression.

---

## Request Batching

If a client needs many pieces of information, sending many individual requests can create unnecessary network overhead.

Batching combines multiple logical operations into fewer requests.

This can reduce:

* Network round trips
* Connection overhead
* Serialization overhead

Very large batches can increase latency and memory usage, so batch size must be controlled.

---

## API Versioning

APIs evolve over time.

A versioning scheme can allow old clients to continue working while newer clients use a newer API contract.

Versioning can be represented through:

* URL paths
* Headers
* Content negotiation

The purpose is controlled API evolution.

---

## Backward Compatibility

During a deployment, old and new application versions can temporarily run at the same time.

For example:

```text
Old Service <-> New Service
```

Therefore, APIs and database schemas often need to remain compatible during migration.

This is particularly important for rolling deployments.

---

## Schema Evolution

Database changes should often be performed gradually.

A safe migration can involve:

1. Adding a new field.
2. Deploying code that understands both versions.
3. Populating the new field.
4. Switching reads to the new field.
5. Removing the old field later.

This prevents old application instances from breaking while a new version is being deployed.

---

## Data Ownership

In a microservice architecture, each service may own its data.

For example:

```text
User Service
 |
 v
User Database

Order Service
 |
 v
Order Database
```

Other services communicate through APIs or events rather than directly accessing another service's database.

This improves ownership boundaries but makes cross-domain queries more complicated.

---

## CQRS

CQRS means Command Query Responsibility Segregation.

Commands change state.

Queries read state.

A system can maintain different models for writing and reading.

This can improve read performance for specialized workloads but adds synchronization and architectural complexity.

---

## Event Sourcing

Event sourcing stores state changes as events.

Instead of storing only the current state, the system records the sequence of events that produced the state.

For example:

```text
Deposited 1000
Deposited 5000
Withdrawn 1000
```

The current state can be reconstructed from those events.

Event sourcing can provide a strong audit history but introduces event schema, storage, replay, and operational complexity.

---

## Feature Flags

Feature flags separate software deployment from feature activation.

A feature can be deployed but kept disabled.

Feature flags can support:

* Gradual rollout
* Controlled testing
* Emergency disablement
* Targeted activation

They become part of application configuration and therefore require careful management.

---

## Multi-Tenant Architecture

A multi-tenant system serves multiple customers using shared infrastructure.

Common models include:

### Shared Database and Shared Tables

All tenants share tables and records are separated using a tenant identifier.

### Shared Database and Separate Schemas

Each tenant receives a separate schema.

### Separate Database per Tenant

Each tenant receives an independent database.

These models differ in:

* Isolation
* Cost
* Scaling
* Backup
* Operations
* Customization

---

## Tenant-Aware Resource Control

A multi-tenant system must prevent one tenant from consuming an unreasonable amount of shared capacity.

Limits can be applied to:

* Users
* Organizations
* Tenants
* API keys
* Endpoints
* IP addresses

This provides workload isolation and fairness.

---

## File Upload Architecture

A scalable file upload design often avoids sending large files through the application server.

Instead:

```text
Browser
 |
 v
Application
 |
 | Authorization
 v
Upload Permission
 |
 v
Object Storage
```

The application handles authentication, authorization, and metadata.

Object storage handles the large binary transfer.

This reduces application server bandwidth and processing requirements.

---

## Webhooks

A webhook allows one system to notify another through an HTTP request.

For example:

```text
Payment Provider
 |
 | POST /webhook
 v
Application
```

Webhook systems need to consider:

* Authentication
* Signature verification
* Retries
* Duplicate events
* Idempotency
* Ordering
* Replay protection

---

## Edge Computing

Edge computing moves processing closer to users.

Instead of:

```text
User -> Distant Region
```

processing may occur at:

```text
User -> Nearby Edge
```

This can reduce latency but increases the complexity of deploying and coordinating distributed logic.

---

## Cloud Architecture

Cloud platforms provide managed building blocks such as:

* Virtual machines
* Containers
* Load balancers
* Databases
* Object storage
* CDNs
* Queues
* Monitoring
* Identity systems

Managed infrastructure reduces operational burden but introduces provider dependency, cost management, and service-specific constraints.

---

## Serverless Architecture

Serverless architecture abstracts infrastructure management from application developers.

Conceptually:

```text
HTTP Request
 |
 v
Function
 |
 v
Database
```

Potential benefits include:

* Automatic scaling
* Reduced infrastructure management
* Usage-based execution

Potential concerns include:

* Cold starts
* Execution limits
* Vendor dependency
* Distributed debugging
* Observability complexity

---

## Architectural Trade-Offs

Web architecture is fundamentally about trade-offs.

Important trade-offs include:

* Simplicity versus flexibility
* Consistency versus availability
* Latency versus stronger guarantees
* Cost versus redundancy
* Centralization versus autonomy
* Caching versus freshness
* Normalization versus read performance
* Synchronous processing versus asynchronous processing
* Monolith simplicity versus distributed scalability
* Isolation versus operational complexity

There is no universal architecture that is optimal for every application.

---

## Monolith and Microservices Comparison

| Concern                | Monolith              | Microservices                 |
| ---------------------- | --------------------- | ----------------------------- |
| Deployment             | One main unit         | Multiple independent services |
| Internal communication | Usually local calls   | Network communication         |
| Scaling                | Scale the application | Scale individual services     |
| Data                   | Often shared database | Often service-owned databases |
| Operations             | Simpler               | More complex                  |
| Transactions           | Usually easier        | More difficult                |
| Failure isolation      | Potentially broader   | Can be narrower               |
| Team ownership         | Often centralized     | Stronger service ownership    |
| Infrastructure         | Less extensive        | More extensive                |

The correct architecture depends on system requirements, organizational structure, scale, and operational capability.

---

## Synchronous and Asynchronous Communication

Synchronous communication requires one component to wait for another.

```text
A -> B
A waits
```

Asynchronous communication can use a queue:

```text
A -> Queue
A continues

Worker -> B
```

Synchronous communication is often easier to understand.

Asynchronous communication can provide:

* Better decoupling
* Higher throughput
* Improved responsiveness
* Better buffering

It also introduces:

* Eventual consistency
* Duplicate processing
* Ordering issues
* Delayed results

---

## Common Architectural Anti-Patterns

Common problems include:

* A single server for a critical service
* A publicly exposed database
* No timeouts for external services
* Unlimited retries
* Retrying non-idempotent operations without protection
* Incorrect caching of personalized data
* Poorly defined microservice boundaries
* Excessive numbers of tiny services
* No centralized observability
* Logging secrets
* Unverified backups
* Scaling application servers while ignoring database limits
* Excessive synchronous dependencies
* Unlimited tenant resource consumption
* Incompatible service versions during deployment
* Assuming internal network traffic is automatically trusted

---

## Complete Modern Web Architecture

A modern web architecture can be represented conceptually as:

```text
                         USERS
                           |
                           v
                    +-------------+
                    |   Browser   |
                    +-------------+
                           |
                           v
                    +-------------+
                    |     DNS     |
                    +-------------+
                           |
                           v
                    +-------------+
                    |     CDN     |
                    +-------------+
                           |
                           v
                 +-------------------+
                 | Edge / WAF / TLS  |
                 +-------------------+
                           |
                           v
                 +-------------------+
                 |  Load Balancer    |
                 +-------------------+
                           |
                           v
                 +-------------------+
                 | Reverse Proxy /   |
                 |   API Gateway     |
                 +-------------------+
                           |
                 +---------+---------+
                 |         |         |
                 v         v         v
             Frontend     API      Auth
                           |
                           v
                    +-------------+
                    | Application |
                    |   Services  |
                    +-------------+
                     /     |     \
                    /      |      \
                   v       v       v
                Cache    Queue    Search
                  |        |        |
                  |        v        |
                  |     Workers     |
                  |        |        |
                  v        v        v
              +-----------------------+
              |   Persistent Data     |
              +-----------------------+
                 /       |       \
                v        v        v
            Primary   Replicas  Object
              DB        DB      Storage
```

Around these components exist additional systems for:

* Security
* Monitoring
* Logging
* Distributed tracing
* Secrets management
* CI/CD
* Backups
* Disaster recovery
* Service discovery

---

## Complete Request Flow

Consider a request for:

```text
https://shop.example.com/products/42
```

A possible sequence is:

1. The browser evaluates local resources and cached information.
2. DNS resolves the domain.
3. A network connection is established.
4. TLS provides a secure communication channel.
5. The browser sends an HTTP request.
6. The CDN receives the request.
7. A cached response may satisfy the request immediately.
8. If necessary, the request reaches the origin infrastructure.
9. A load balancer selects an application instance.
10. A reverse proxy or API gateway routes the request.
11. Authentication and authorization are evaluated.
12. The application checks the cache.
13. A cache miss may cause a database query.
14. The database returns the required data.
15. The application creates the response.
16. Caching infrastructure may store the result.
17. The response travels back through the network.
18. The browser processes and renders the result.
19. Additional resources may trigger additional requests.

This illustrates that a single web action can involve a large number of architectural components.

---

## Failure Handling

A resilient architecture anticipates failures.

If an application server fails, a load balancer can route traffic to another healthy instance.

If a cache fails, the application may fall back to the database if the architecture allows it.

If a database replica fails, traffic can be redirected to another replica.

If an external service becomes slow, timeouts and circuit breakers can prevent unlimited waiting.

If a queue grows rapidly, consumers can scale or producers can be slowed through backpressure.

If a deployment is defective, canary, blue-green, or rollback mechanisms can limit the impact.

If an entire region fails, multi-region architecture can provide a recovery path.

---

## Capacity Reasoning

Capacity planning begins with workload estimation.

Suppose:

```text
100,000 users
2 requests per minute per user
```

The average request rate is approximately:

```text
100,000 × 2 / 60
```

which is about:

```text
3,333 requests per second
```

If peak traffic is five times higher, the system may need to handle approximately:

```text
16,665 requests per second
```

Capacity planning must account for:

* Peak traffic
* Bursts
* Failures
* Maintenance
* Background workloads
* Uneven traffic distribution
* Resource headroom

---

## Queueing and Saturation

As workload approaches system capacity, waiting time can increase rapidly.

A service processing:

```text
900 requests/sec
```

with a capacity of:

```text
1,000 requests/sec
```

has more headroom than a service processing:

```text
990 requests/sec
```

with the same capacity.

Small traffic increases can therefore produce disproportionately large latency increases near saturation.

---

## Single Points of Failure

A single point of failure is a component whose failure can make the system unavailable.

For example:

```text
Application
 |
 v
Single Database
```

If the database fails, the application may fail.

Redundant infrastructure can reduce this risk:

```text
Application
 |
 +-- Database A
 |
 +-- Database B
```

Redundancy itself requires failover, replication, monitoring, and recovery mechanisms.

---

## Security Boundaries

Security boundaries separate components with different trust levels.

A typical structure may be:

```text
Internet
 |
 v
Edge
 |
 v
Public API
 |
 v
Internal Services
 |
 v
Database
```

The database should not normally be directly accessible from the public Internet.

Different layers can enforce different security controls.

---

## Network Segmentation

Infrastructure can be separated into network zones.

For example:

```text
Public Zone
 |
 v
Application Zone
 |
 v
Database Zone
```

Communication should be restricted to the paths that are actually required.

This reduces the potential impact of a compromised component.

---

## Least Privilege

Least privilege means giving identities only the permissions they require.

For example, a reporting service may need read access to certain information but does not need permission to delete or modify production data.

Least privilege reduces the potential impact of compromised credentials or vulnerable applications.

---

## Encryption

Encryption can protect information:

### In Transit

TLS protects network communication.

### At Rest

Database and storage encryption protects persisted information.

### Application-Level Encryption

Some highly sensitive information may require encryption at the application layer.

Encryption also creates a key-management responsibility because encryption is only useful when keys are properly protected.

---

## Backup Architecture

Backups protect against:

* Accidental deletion
* Corruption
* Operational mistakes
* Ransomware
* Infrastructure failures

A backup strategy must consider:

* Frequency
* Retention
* Encryption
* Geographic separation
* Restoration procedures
* Restoration testing

A backup should not be considered reliable merely because it was successfully created. The ability to restore it is equally important.

---

## Disaster Recovery Strategies

Common approaches include:

### Backup and Restore

Infrastructure and data are restored after failure.

### Pilot Light

Minimal critical infrastructure is kept ready.

### Warm Standby

A partially operational recovery environment is maintained.

### Hot Standby

A highly prepared secondary environment is maintained.

Faster recovery generally requires more continuously maintained infrastructure.

---

## Example: Chat Application

A chat application can use:

```text
Browser
 |
 v
Load Balancer
 |
 v
WebSocket Gateway
 |
 +-- Message Service
 +-- Presence Service
 +-- Notification Service
          |
          v
        Queue
          |
          v
       Workers
```

Caches can maintain presence information and connection mappings.

Queues can process notifications and offline delivery.

WebSockets maintain real-time communication between clients and servers.

---

## Example: E-Commerce Architecture

An e-commerce system may contain:

```text
Customer
 |
 v
CDN
 |
 v
API Gateway
 |
 +-- Product Service
 +-- Cart Service
 +-- Order Service
 +-- Payment Service
 +-- User Service
```

Products may use databases, caches, and search indexes.

Order creation can produce an `OrderCreated` event.

Consumers can include:

* Inventory
* Email
* Analytics
* Shipping

Payment operations require particularly careful handling of idempotency and correctness.

---

## Example: Social Media Architecture

A social platform can contain:

* User Service
* Post Service
* Media Service
* Feed Service
* Notification Service
* Search Service

Large media files can be stored in object storage and delivered through a CDN.

Feed generation can use either pull-based or push-based approaches.

A hybrid approach can treat extremely popular accounts differently from ordinary accounts.

---

## Feed Architecture

### Pull Model

The feed is generated when the user requests it.

```text
User
 |
 v
Find Followed Users
 |
 v
Retrieve Posts
 |
 v
Rank
```

### Push Model

Posts are distributed to followers when they are published.

```text
New Post
 |
 v
Fan Out
 |
 v
Follower Feeds
```

Pull models reduce write amplification for extremely popular accounts.

Push models can make reads very fast but can generate large amounts of work when content is published.

---

## Search Autocomplete

Autocomplete is highly latency-sensitive.

A typical design can use:

```text
Browser
 |
 v
Search API
 |
 v
Prefix Index / Search Engine
```

Popular prefixes can be cached.

This allows frequently requested queries to be served quickly without repeatedly performing expensive searches.

---

## Web Architecture as a System

The complete mental model can be expressed as:

```text
USER
 |
 v
CLIENT
 |
 v
DNS
 |
 v
NETWORK
 |
 v
TLS
 |
 v
HTTP
 |
 v
CDN / EDGE
 |
 v
LOAD BALANCER
 |
 v
REVERSE PROXY / API GATEWAY
 |
 v
APPLICATION
 |
 +--------------------+
 |                    |
 v                    v
CACHE               SERVICES
 |                    |
 |              +-----+-----+
 |              |           |
 v              v           v
DATABASE       QUEUE      SEARCH
 |              |           |
 +------+-------+-----------+
        |
        v
PERSISTENT STORAGE
```

Around these components are:

* Security
* Logging
* Metrics
* Tracing
* Deployment
* Backup
* Disaster recovery
* Configuration
* Secrets management

Web architecture is therefore not merely a collection of technologies.

It is a set of relationships and responsibilities.

A cache improves speed but introduces freshness concerns.

A queue provides decoupling but introduces asynchronous behavior.

A database provides durable state but can become a bottleneck.

A replica improves availability and read capacity but can introduce replication lag.

A microservice can provide independent deployment and scaling but introduces network communication and distributed-system complexity.

A CDN reduces latency but introduces another caching layer.

A load balancer improves availability but becomes infrastructure that itself needs redundancy.

The purpose of web architecture is to organize these components so that the complete system can satisfy its functional, performance, security, scalability, availability, reliability, and operational requirements.

