# REST Architecture

## Topic Scope

This document explains REST architecture through three implementations:

- A Python implementation of a small HTTP API with an executable standard-library server.
- A JavaScript implementation emphasizing application-level REST processing, asynchronous behavior, content negotiation, and representation handling.
- A C++17 case study modeling an industry-style book catalog service with resource storage, validation, conditional requests, pagination, concurrency protection, and HTTP-like responses.

The central concepts are **resources, representations, statelessness, and uniform interface**. HTTP supplies the most common transport and method semantics used by REST APIs, but REST itself is an architectural style rather than a synonym for HTTP or JSON.

---

# 1. REST Architecture Introduction

REST stands for **Representational State Transfer**.

REST is an architectural style for distributed systems. It describes constraints that guide the design of networked applications.

A REST-oriented system models information as **resources**. Clients interact with those resources through representations and a consistent interface.

For example, a book can be modeled as a resource:

`/books/42`

The URI identifies the resource. The representation transferred to a client might be JSON:

`{"id":42,"title":"Clean Architecture","author":"Robert C. Martin"}`

The URI does not need to encode the operation. HTTP methods provide operation semantics:

- `GET /books/42` retrieves a representation.
- `PUT /books/42` replaces the representation.
- `PATCH /books/42` partially modifies the resource.
- `DELETE /books/42` requests deletion.
- `POST /books` submits data to the collection for processing, commonly creating a new resource.

This separation between **resource identification** and **operation semantics** is a major part of a uniform interface.

---

# 2. REST Architectural Constraints

REST is commonly explained through six architectural constraints.

## 2.1 Client-server

Client and server responsibilities are separated.

The client is responsible for user-interface concerns and interaction. The server is responsible for resource management and data-related processing.

The separation allows each side to evolve independently as long as the interface remains compatible.

The book catalog examples reflect this separation:

- The client sends HTTP-like requests.
- The API decides how the resource is stored.
- The representation defines what the client receives.
- The internal `Book` object is not necessarily identical to the public representation.

---

## 2.2 Statelessness

A REST interaction is stateless when the server does not depend on stored conversational state from previous requests to understand the current request.

For example, these requests are independently meaningful:

`GET /books/1`

and

`GET /books/2`

The server does not need to remember that the client previously requested `/books/1`.

Authentication information can also be supplied with each request, commonly through an `Authorization` header.

Statelessness does **not** mean that the server cannot store data.

A server can store:

- books
- users
- orders
- database records
- files
- configuration
- audit records

The distinction is between **persistent resource state** and **server-side conversational session state required to interpret a request**.

---

## 2.3 Cacheability

Responses should indicate whether they can be reused.

The implementations demonstrate headers such as:

`Cache-Control: max-age=60`

and:

`Cache-Control: no-cache`

The Python and JavaScript implementations also demonstrate ETags.

An ETag identifies a particular representation version. A client can send:

`If-None-Match: "etag-value"`

If the representation has not changed, the server can return:

`304 Not Modified`

without transferring the complete representation again.

This can reduce bandwidth and processing costs.

---

## 2.4 Uniform Interface

The uniform interface constraint is one of the most important REST concepts.

It consists of several related ideas:

1. Resource identification.
2. Manipulation of resources through representations.
3. Self-descriptive messages.
4. Hypermedia as the engine of application state.

The implementations demonstrate all four to varying degrees.

### Resource identification

`/books/42` identifies a particular book resource.

`/books` identifies the collection.

### Manipulation through representations

A client does not directly modify an internal C++ or Python object.

Instead, it transfers a representation such as JSON or the simplified C++ case-study request format.

### Self-descriptive messages

HTTP method, status code, headers, media type, and representation provide information needed to interpret the response.

For example:

`Content-Type: application/json`

communicates the representation format.

### Hypermedia

The implementations include links such as:

`"self": "http://localhost:8000/books/42"`

and:

`"collection": "http://localhost:8000/books"`

A richer hypermedia-driven API can expose links for operations available from the current resource state.

---

# 3. Resources

A **resource** is a conceptual target identified by a URI.

A resource does not have to be a physical database row.

Examples include:

- a user
- a book
- an invoice
- an order
- a collection
- a search result
- a document
- a product
- a weather report
- a relationship between entities

The URI identifies the resource, while a representation describes its current state.

For example:

`/books/42`

can identify a book.

A JSON representation might contain:

`id`

`title`

`author`

`year`

`genre`

The database schema could be completely different.

This distinction allows the server's internal implementation to evolve without necessarily changing the external resource interface.

---

# 4. Resource Collections and Individual Resources

A common resource structure is:

`/books`

for the collection and:

`/books/42`

for an individual resource.

The distinction is important.

## Collection

`GET /books`

retrieves a representation of a collection.

`POST /books`

submits a new item to the collection.

## Individual resource

`GET /books/42`

retrieves one resource.

`PUT /books/42`

replaces its representation.

`PATCH /books/42`

applies partial changes.

`DELETE /books/42`

requests removal.

This is generally clearer than action-oriented URIs such as:

`/getBook`

`/createBook`

`/deleteBook`

The operation is represented by the HTTP method rather than encoded into the URI.

---

# 5. Representations

A representation is information transferred between client and server that describes a resource.

Common representation formats include:

- JSON
- XML
- HTML
- plain text
- binary formats

REST does not require JSON.

JSON is popular because it is compact, widely supported, and easy to process in many programming languages.

The Python implementation converts a `Book` domain object into a JSON-compatible dictionary.

The JavaScript implementation converts the `Book` object into a JavaScript object suitable for JSON serialization.

The C++ implementation explicitly constructs a JSON representation as a string to keep the program free of third-party dependencies.

---

# 6. Resource State Versus Representation

A useful distinction is:

**Resource state** exists on the server.

**Representation** is transferred to the client.

For example, a server might internally store:

- database primary key
- version number
- timestamps
- internal audit metadata
- internal indexes

The public representation may expose only:

- id
- title
- author
- year
- genre
- links

The Python `Book.to_representation()` method demonstrates this boundary.

The C++ `Book::representation()` method demonstrates the same idea.

The API contract should not automatically expose every internal implementation detail.

---

# 7. HTTP Methods

REST APIs commonly use HTTP methods to express standardized semantics.

## GET

`GET` requests a representation.

Example:

`GET /books/42`

GET is safe and idempotent.

Safe means the method is intended for retrieval rather than requesting a state-changing action.

Idempotent means that repeating the same request has the same intended state effect as performing it once.

GET can still cause incidental server-side effects such as logging. Safe does not mean literally zero internal activity.

---

## POST

`POST` submits a representation to a target resource for processing.

Example:

`POST /books`

The server can assign a new identifier.

The Python and JavaScript implementations return:

`201 Created`

and a `Location` header containing the newly created resource URI.

POST is not inherently idempotent.

Repeating the same POST can create multiple resources.

---

## PUT

`PUT` is used to create or replace a representation at a known target URI, depending on the API's contract and resource semantics.

Example:

`PUT /books/42`

The Python, JavaScript, and C++ implementations use PUT as a complete replacement operation.

If the same valid representation is submitted repeatedly, the intended resource state remains the same. This is the practical reason PUT is idempotent.

Idempotency does not mean that every response must be byte-for-byte identical.

---

## PATCH

`PATCH` applies partial modifications.

Example:

`PATCH /books/42`

with a representation that changes only the genre.

PATCH is not inherently idempotent. An individual PATCH design can be idempotent or non-idempotent depending on its semantics.

For example, setting:

`genre = "data"`

can be idempotent.

An operation that means "increase counter by 1" is not idempotent if repeated.

---

## DELETE

`DELETE` requests removal of a resource.

Example:

`DELETE /books/42`

DELETE is idempotent in HTTP semantics.

After the resource has been removed, repeating the deletion does not create another state transition that makes the resource "more deleted."

The Python, JavaScript, and C++ examples deliberately demonstrate repeated DELETE behavior.

---

# 8. Idempotency

Idempotency is a property of an operation's intended effect on server state.

Common HTTP classifications are:

| Method | Safe | Idempotent |
|---|---:|---:|
| GET | Yes | Yes |
| HEAD | Yes | Yes |
| POST | No | No, not inherently |
| PUT | No | Yes |
| PATCH | No | Not inherently |
| DELETE | No | Yes |

Idempotency is especially important when networks are unreliable.

A client may not know whether a request reached the server if the connection fails.

Retrying an idempotent operation is generally easier to reason about than retrying a non-idempotent operation.

---

# 9. HTTP Status Codes

The implementations use several important status codes.

## 200 OK

The request succeeded and the response contains a representation.

Used for successful GET, PUT, and PATCH operations.

## 201 Created

A new resource was created.

The POST examples also return a `Location` header.

## 204 No Content

The request succeeded and there is no response representation.

The DELETE examples use 204.

## 304 Not Modified

The representation has not changed relative to the client's cached copy.

The response normally contains no representation body.

## 400 Bad Request

The request is invalid.

Examples include malformed input and invalid query parameters.

## 404 Not Found

The requested resource does not exist.

## 405 Method Not Allowed

The resource exists at the target URI, but the requested method is not supported for that resource.

The examples return an `Allow` header.

## 412 Precondition Failed

A request condition such as `If-Match` was not satisfied.

The examples use this for stale ETags.

## 413 Payload Too Large

The Python HTTP adapter demonstrates request-size protection and can reject excessively large request bodies.

---

# 10. Uniform Resource Naming

A resource-oriented API generally uses nouns rather than verbs in resource paths.

Less resource-oriented:

`/getBooks`

`/createBook`

`/deleteBook`

More resource-oriented:

`/books`

`/books/42`

The HTTP method supplies the operation semantics.

The URI therefore answers:

**Which resource?**

The HTTP method answers:

**What standardized operation is being requested?**

---

# 11. Stateless Request Processing

The Python `RestApplication.route()` method accepts all information needed to process an HTTP-like request.

It receives:

- method
- path
- query parameters
- body
- headers

This makes the stateless nature of the application boundary visible.

The application does not need a hidden variable such as:

`currentBookForUser`

to interpret:

`GET /books/42`

A production API may still use authentication, authorization, databases, caches, and other persistent infrastructure. Those do not automatically violate REST statelessness.

The key question is whether the request depends on stored conversational context from earlier requests.

---

# 12. Authentication and Statelessness

Authentication should not be confused with session state.

A request may contain:

`Authorization: Bearer <token>`

The server can validate the token for every request.

The request is then independently interpretable.

A traditional server-side session can also exist in a broader web architecture, but making every API operation dependent on an implicit conversational session introduces state that must be considered carefully when designing a REST interface.

The examples intentionally avoid implementing real authentication credentials. This prevents the educational code from pretending to provide production-grade security.

---

# 13. Content Negotiation

A client can use the `Accept` header to communicate preferred representations.

For example:

`Accept: application/json`

The JavaScript implementation includes `selectRepresentation()` to demonstrate the basic decision process.

A production API might support:

`application/json`

`application/xml`

`text/html`

or specialized media types.

The server should return an appropriate `Content-Type` header describing the actual response representation.

---

# 14. Hypermedia

REST's uniform interface constraint includes hypermedia.

The examples provide links such as:

`"self": "http://localhost:8000/books/42"`

and:

`"collection": "http://localhost:8000/books"`

The collection representation also exposes pagination links.

Hypermedia can allow clients to discover valid transitions from representations instead of hard-coding every possible URI.

For example, an order representation might expose links for:

- self
- customer
- payment
- shipment
- cancellation

The availability of a link can reflect the current state of the resource.

---

# 15. Pagination

Returning an unlimited collection can be inefficient.

The implementations use:

`limit`

and:

`offset`

for simple pagination.

Example:

`GET /books?offset=20&limit=20`

The response includes:

- offset
- limit
- count
- total
- self
- next
- previous

The Python and JavaScript versions implement this directly.

The C++ implementation demonstrates pagination parameters at the application layer.

For very large datasets, offset pagination can become expensive because the database may need to scan or skip many rows.

Cursor or keyset pagination can be more efficient.

A keyset design might use a stable ordering key such as:

`id > 100`

rather than:

`offset=100000`

---

# 16. Conditional Requests and ETags

An **ETag** is an identifier for a particular representation.

The examples calculate an ETag from the representation.

A client first retrieves:

`GET /books/42`

and receives:

`ETag: "abc123"`

The client later sends:

`If-None-Match: "abc123"`

If the representation has not changed, the server returns:

`304 Not Modified`

This supports cache validation.

ETags can also protect updates.

A client can send:

`If-Match: "abc123"`

If another client has already modified the resource, the server's current ETag differs.

The server can return:

`412 Precondition Failed`

This is a form of optimistic concurrency control.

---

# 17. Lost Update Problem

Suppose two clients read the same book.

Client A sees version A.

Client B sees version A.

Client B updates the book.

The resource is now version B.

Client A submits an update based on its stale representation.

Without concurrency protection, client A might overwrite changes made by client B.

ETags and `If-Match` can detect this situation.

The implementations deliberately demonstrate:

1. Reading a resource.
2. Saving its ETag.
3. Another client changing the resource.
4. Attempting an update with the stale ETag.
5. Receiving `412 Precondition Failed`.

This is an important production consideration for APIs where multiple clients can modify the same resource.

---

# 18. Validation

Validation should occur at the application boundary.

The examples validate:

- required fields
- unknown fields
- non-empty strings
- year ranges
- query limits
- pagination offsets

For example, the Python implementation rejects a book with an empty title.

The JavaScript implementation checks both object shape and field types.

The C++ implementation uses `ValidationError` for invalid domain values.

Validation should not be limited to the user interface. Clients can bypass a UI entirely and send HTTP requests directly.

---

# 19. Error Representations

A useful API returns structured error information.

The implementations use a structure conceptually similar to:

`{"error":{"code":"not_found","message":"Book does not exist."}}`

A structured error representation gives clients a stable machine-readable code while still providing a human-readable message.

Production APIs should avoid returning:

- stack traces
- database connection strings
- internal file paths
- SQL statements
- secret values
- internal implementation details

to untrusted clients.

---

# 20. Python Implementation

The Python implementation is the most complete executable teaching implementation.

## Resource Model

The `Book` dataclass represents the domain object.

Its fields include:

- `id`
- `title`
- `author`
- `year`
- `genre`
- internal version information
- timestamps

The `to_representation()` method creates the public representation.

This illustrates the distinction between a domain object and an API representation.

## Repository

`BookStore` provides:

- create
- get
- list
- replace
- patch
- delete

A lock protects the in-memory dictionary because the HTTP server uses `ThreadingHTTPServer`.

## Application Layer

`RestApplication` handles resource-oriented operations.

The route structure is:

`/books`

and:

`/books/{id}`

The application is separate from the HTTP adapter.

This separation makes the core behavior testable without opening a network socket.

## HTTP Adapter

`RestRequestHandler` translates actual HTTP requests into application calls.

This is an important architectural distinction:

**HTTP transport is an adapter around the resource-oriented application.**

The HTTP handler reads:

- method
- path
- query parameters
- headers
- body

and passes them into the application.

## Testing

`RestApplicationTests` uses Python's standard `unittest` module.

The tests cover:

- collection retrieval
- creation
- missing resources
- conditional GET
- PUT idempotency
- DELETE idempotency
- validation failures

---

# 21. JavaScript Implementation

The JavaScript implementation focuses on application-level REST processing and JavaScript-specific behavior.

## JavaScript Objects

`Book` represents a resource in memory.

`BookStore` manages the resource collection.

JavaScript's `Map` provides efficient lookup by numeric resource identifier.

## Asynchronous Processing

The `fetchRepresentation()` function demonstrates asynchronous HTTP access using `fetch()` and `async`/`await`.

Network communication is naturally asynchronous in JavaScript applications.

This is especially relevant to browser-based REST clients.

## Content Negotiation

`selectRepresentation()` demonstrates processing an `Accept` header.

A production implementation would normally perform more complete media-type parsing, including quality values and server-supported media types.

## ETags

The JavaScript implementation uses Web Crypto's SHA-256 functionality to create deterministic representation identifiers.

This is more representative of a production-grade hashing mechanism than the simple hash used in the C++ teaching case study.

## Application Layer

`RestApplication` provides:

- collection GET
- collection POST
- individual GET
- PUT
- PATCH
- DELETE
- validation
- conditional GET
- conditional update
- pagination
- hypermedia links

---

# 22. C++ Case Study

The C++ program models a more system-oriented implementation.

The scenario is a **Book Catalog API**.

The system has:

- resource storage
- HTTP-like requests
- HTTP-like responses
- routing
- validation
- representations
- ETags
- pagination
- optimistic concurrency
- thread-safe repository operations

## Problem Being Solved

A client needs to manage books through a consistent resource-oriented interface.

The main resources are:

`/books`

and:

`/books/{id}`

The API supports:

- collection retrieval
- resource retrieval
- resource creation
- full replacement
- partial modification
- deletion

## Repository Design

`BookRepository` owns the resource storage.

It uses:

`std::unordered_map<int, Book>`

for average O(1) identifier lookup.

A `std::mutex` protects repository access.

This is important because a production-style service may process multiple requests concurrently.

The repository is isolated from the API routing layer.

---

# 23. C++ Request and Response Model

The C++ case study defines:

`Request`

and:

`Response`

A request contains:

- method
- path
- query parameters
- headers
- body

A response contains:

- status
- headers
- body

This separation mirrors the actual conceptual structure of HTTP communication.

The application can therefore reason about REST interactions without requiring a specific networking library.

---

# 24. C++ Routing

The case study recognizes:

`/books`

and:

`/books/{id}`

using a regular expression for individual resource paths.

The router uses the HTTP method to determine the operation.

For example:

`GET /books/42`

selects retrieval.

`PATCH /books/42`

selects partial modification.

This demonstrates the uniform interface principle at the routing level.

---

# 25. C++ Full Replacement

The PUT implementation treats the supplied representation as a complete replacement.

The operation validates:

- title
- author
- year
- genre

It also checks an optional `If-Match` header.

If the supplied ETag is stale, the API returns:

`412 Precondition Failed`

This combines HTTP method semantics with concurrency control.

---

# 26. C++ Partial Modification

The PATCH implementation accepts only changed fields.

For example:

`genre=web-architecture`

changes only the genre.

Existing values remain unchanged.

PATCH requires careful API design because partial updates can have different semantics.

An API should define:

- whether missing fields are preserved
- whether null means deletion
- whether arrays are replaced or merged
- whether operations are idempotent
- how validation is applied

The case study uses simple field replacement to keep these semantics explicit.

---

# 27. C++ Thread Safety

The repository uses `std::mutex`.

This matters because a service can receive simultaneous requests.

Without synchronization, concurrent operations on mutable shared data could create data races.

The mutex provides a basic protection mechanism for this in-memory case study.

A production architecture may instead rely on:

- database transaction isolation
- connection pools
- distributed locks
- optimistic concurrency
- atomic operations
- service-level concurrency controls

The correct approach depends on the system's consistency requirements.

---

# 28. Performance Considerations

The main operations have different costs.

For the Python dictionary and C++ `unordered_map`, lookup by ID is approximately:

**Average O(1)**

Collection filtering is approximately:

**O(n)**

Sorting the complete collection is:

**O(n log n)**

The simple pagination implementation still sorts the collection before slicing it.

This is acceptable for an educational in-memory implementation but is not an ideal strategy for a very large dataset.

A production database can use indexes.

For example, an index on:

`author`

can make author filtering much more efficient than scanning every row.

An index on:

`id`

supports efficient resource lookup.

---

# 29. Database Considerations

A REST API should normally separate resource semantics from persistence implementation.

The client should not need to know whether the server stores books in:

- PostgreSQL
- MySQL
- SQLite
- a document database
- an object store
- an in-memory cache
- another service

The resource interface should remain stable while the persistence layer evolves.

The repository abstraction in the Python and C++ examples demonstrates this separation.

---

# 30. Caching Considerations

Caching can occur at multiple layers:

- browser
- mobile application
- CDN
- reverse proxy
- API gateway
- service cache
- database cache

HTTP cache-control directives communicate caching semantics.

An API should not assume that every response is automatically cacheable in the desired way.

Responses containing user-specific or security-sensitive information require careful cache policy.

ETags provide a mechanism for validating cached representations.

---

# 31. Security Considerations

REST itself is not a complete security architecture.

Production APIs should consider:

## Transport security

Use HTTPS/TLS so that credentials and resource data are protected in transit.

## Authentication

Determine who is making the request.

## Authorization

Determine whether that authenticated identity may perform the requested operation on the target resource.

Authentication and authorization are different problems.

## Input validation

Validate:

- URI parameters
- query parameters
- headers where appropriate
- request bodies
- media types
- sizes
- expected ranges

## Rate limiting

Limit excessive requests where abuse or resource exhaustion is possible.

## Request size limits

The Python HTTP adapter demonstrates a basic request-body size limit.

## Error handling

Do not expose internal implementation details to untrusted clients.

## Logging

Log useful security events without storing secrets unnecessarily.

## CORS

Browser APIs should configure Cross-Origin Resource Sharing according to actual application requirements rather than using unrestricted origins by default.

---

# 32. REST and Security Are Different Concerns

REST does not automatically make an API secure.

An API can be:

- REST-oriented and insecure
- REST-oriented and secure
- non-REST-oriented and secure
- non-REST-oriented and insecure

Security is a separate engineering concern.

The REST architecture determines how resources and interactions are modeled. Authentication, authorization, encryption, validation, rate limiting, and operational controls address security.

---

# 33. Common Mistakes

## Treating REST as JSON

REST does not require JSON.

JSON is a representation format.

## Treating REST as HTTP

HTTP is the most common protocol for REST-style APIs, but REST is an architectural style.

## Putting verbs in every URI

Paths such as:

`/getBooks`

`/createBook`

often duplicate operation information already represented by HTTP methods.

## Ignoring method semantics

Using POST for every operation removes useful HTTP semantics and makes caching, retries, tooling, and client reasoning more difficult.

## Storing conversational state unnecessarily

An API that requires the server to remember hidden client context for every request weakens the stateless constraint.

## Returning 200 for every situation

Status codes communicate important information.

A missing resource should normally not be represented as a successful response merely because the server technically generated a response.

## Exposing database models directly

A database schema is not automatically an API contract.

Representations should be intentionally designed.

## Ignoring concurrency

Multiple clients can modify the same resource.

ETags and conditional requests can help prevent lost updates.

## Returning unlimited collections

Large collections can cause memory, network, and latency problems.

Pagination should be considered for potentially large collections.

---

# 34. Limitations of the Demonstrations

These implementations are educational rather than complete production frameworks.

The Python implementation uses an in-memory store.

The JavaScript implementation models the API without building a complete production HTTP framework.

The C++ program intentionally avoids third-party networking and JSON libraries.

The C++ request-body format is simplified to keep the program self-contained.

A production implementation would normally include a proper HTTP server, standards-compliant JSON processing, persistent storage, observability, authentication, authorization, rate limiting, configuration management, deployment controls, and comprehensive automated testing.

The simplified implementations are valuable because they expose the architectural concepts instead of hiding them behind framework abstractions.

---

# 35. Important Distinctions

| Concept | Meaning |
|---|---|
| Resource | Conceptual entity identified by a URI |
| Representation | Transferable description of a resource |
| URI | Identifier for a resource |
| HTTP method | Standardized operation semantics |
| Statelessness | Requests do not depend on hidden conversational server state |
| Cacheability | Responses can define whether and how they may be reused |
| Uniform interface | Consistent resource-oriented interaction model |
| ETag | Identifier for a particular representation version |
| Idempotency | Repetition has the same intended state effect |
| Safe method | Intended for retrieval rather than requested modification |
| Hypermedia | Links and controls that can guide application state transitions |

---

# 36. Python, JavaScript, and C++ Comparison

| Area | Python | JavaScript | C++ |
|---|---|---|---|
| Main emphasis | Complete REST teaching implementation | Application and asynchronous behavior | Systems-oriented case study |
| Resource model | Dataclass | Class | Struct |
| Storage | Dictionary | Map | unordered_map |
| Validation | Explicit exception | Custom Error | Custom exception |
| HTTP adapter | Standard library server | Application-level model | HTTP-like structures |
| Concurrency | Threading HTTP server and lock | Async programming model | Mutex-protected repository |
| Representation | Dictionary to JSON | Object to JSON | Explicit JSON construction |
| ETag | SHA-256 | Web Crypto SHA-256 | Educational deterministic hash |
| Testing | unittest | Executable demonstrations | Case-study execution |
| Production relevance | High-level service design | Web/client integration | Memory, concurrency, architecture |

The same REST concepts appear in all three languages, but the implementation details differ because each language emphasizes different execution and system concerns.

---

# 37. Architectural Layering

A maintainable REST service can be organized into layers.

A typical structure is:

**Transport layer**

Handles HTTP details.

**Routing layer**

Maps methods and URIs to application operations.

**Application layer**

Coordinates use cases.

**Domain layer**

Represents business concepts and rules.

**Persistence layer**

Stores and retrieves durable data.

The Python implementation explicitly separates the HTTP adapter from the application.

The C++ implementation separates request processing, API behavior, repository storage, and domain representation.

This prevents transport-specific code from becoming tightly coupled to database logic.

---

# 38. Production Design Considerations

A production REST service should establish explicit contracts for:

- URI structure
- HTTP methods
- status codes
- media types
- request schemas
- response schemas
- validation rules
- authentication
- authorization
- caching
- concurrency
- pagination
- filtering
- sorting
- error formats
- rate limits
- observability
- version compatibility

A good resource model should remain understandable independently of the database schema.

---

# 39. Versioning Considerations

APIs sometimes need to evolve.

Possible strategies include:

- URI versioning
- media-type versioning
- header-based versioning
- backward-compatible schema evolution

Versioning is not itself a fundamental REST constraint.

The important architectural requirement is that clients and servers maintain a compatible contract while representations evolve.

For example, adding an optional response field is often less disruptive than renaming or removing an existing required field.

---

# 40. API Contract Stability

An API representation is a contract between clients and servers.

Changing:

`"author"`

to:

`"writer"`

can break clients even if the database is unchanged.

Likewise, changing a field from integer to string can create compatibility problems.

REST architecture therefore benefits from deliberate representation design.

The implementations use explicit fields rather than exposing internal objects automatically.

---

# 41. Practical Resource Design

A useful resource model asks:

1. What conceptual entities exist?
2. Which entities deserve stable identifiers?
3. Which resources are collections?
4. What relationships exist?
5. Which representations should clients receive?
6. Which methods make sense for each resource?
7. Which operations are safe?
8. Which operations are idempotent?
9. Which responses can be cached?
10. Which state transitions should be exposed through links?

For the book system, the primary answers are:

- Collection: `/books`
- Individual resource: `/books/{id}`
- Retrieval: GET
- Creation: POST on the collection
- Replacement: PUT on an individual resource
- Partial update: PATCH
- Deletion: DELETE
- Representation: JSON
- Concurrency mechanism: ETag and `If-Match`

---

# 42. Edge Cases Demonstrated

The implementations cover several important edge cases:

- Missing resource
- Invalid request body
- Missing fields
- Unknown fields
- Invalid year
- Invalid pagination limit
- Negative pagination offset
- Conditional GET
- Stale conditional update
- Repeated DELETE
- Unsupported method
- Large request body protection in Python
- Concurrent access protection in the Python and C++ storage layers

These cases are important because API correctness is defined not only by successful requests but also by predictable behavior when requests are invalid or state has changed.

---

# 43. Why the Uniform Interface Matters

Without a uniform interface, every service might invent its own operation model.

A client would have to understand many unrelated conventions.

With a consistent resource-oriented model, clients can reason using standardized concepts:

- URI identifies the target
- HTTP method expresses operation semantics
- headers describe request or response metadata
- representation carries resource information
- status code communicates outcome
- links can expose related transitions

This reduces coupling between clients and server implementation details.

---

# 44. REST Is an Architectural Style, Not a CRUD Checklist

CRUD operations are useful for teaching resource APIs, but REST is broader than CRUD.

CRUD describes:

- create
- read
- update
- delete

REST describes architectural constraints for distributed systems.

A REST resource may represent a process, search result, relationship, report, or other conceptual entity rather than a database row.

Therefore, designing a REST API is not simply a matter of creating one endpoint for each database CRUD operation.

The resource model should represent meaningful domain concepts.

---

# 45. Implementation Checklist

A REST-oriented API implementation should be able to answer:

- What are the resources?
- How are they identified?
- What representations exist?
- Which methods apply?
- What does each method mean?
- Which methods are safe?
- Which methods are idempotent?
- Is the request self-contained?
- What can be cached?
- How are representations validated?
- How are errors represented?
- How are concurrent modifications handled?
- How are large collections paginated?
- How are related resources discovered?
- How is authentication performed?
- How is authorization enforced?
- How are malformed or malicious requests handled?
- How are compatibility and version changes managed?
- How is the system monitored in production?

The three implementations provide concrete answers for a small book resource while keeping the architectural principles visible.
