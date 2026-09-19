# FastAPI routing: GET, POST, PUT, PATCH, DELETE, and route parameters

## Introduction

FastAPI routing connects HTTP requests to Python functions. A route defines the HTTP method, URL path, parameters, validation rules, and application logic associated with a request.

The core routing patterns demonstrated in this repository are:

| HTTP method | Typical purpose | Example |
|---|---|---|
| GET | Read a resource or collection | `/api/users/42` |
| POST | Create a resource or trigger an operation | `/api/users` |
| PUT | Replace a complete resource | `/api/users/42` |
| PATCH | Partially modify a resource | `/api/users/42` |
| DELETE | Remove a resource | `/api/users/42` |

The implementations use the same conceptual API from three perspectives:

- Python demonstrates FastAPI itself and its routing mechanisms.
- JavaScript demonstrates how a client constructs URLs, sends HTTP requests, handles responses, and performs asynchronous operations.
- C++ models an industry-style API service layer with route definitions, validation, resource storage, CRUD operations, error handling, pagination, and route-parameter encoding.

The Python implementation is the actual FastAPI application. The JavaScript and C++ implementations complement it by showing client-side and systems-level representations of the same API concepts.

## Core terminology

### API

An application programming interface defines how software components communicate.

A web API commonly exposes HTTP endpoints that clients can call with methods such as GET, POST, PUT, PATCH, and DELETE.

### Endpoint

An endpoint is a particular HTTP method and URL path handled by an application.

For example:

`GET /api/users/42`

The method is GET and the path is `/api/users/42`.

### Route

A route maps an HTTP request pattern to application logic.

In FastAPI:

`@app.get("/api/users/{user_id}")`

registers a GET route whose path contains a dynamic `user_id` parameter.

### Path parameter

A path parameter is a variable component embedded in the URL path.

For:

`/api/users/{user_id}`

the value `42` in:

`/api/users/42`

is the value of `user_id`.

Path parameters generally identify a specific resource.

### Query parameter

A query parameter appears after `?` in a URL.

For example:

`/search?q=fastapi&page=2&page_size=20`

contains:

- `q`
- `page`
- `page_size`

Query parameters are commonly used for filtering, sorting, pagination, searching, and optional behavior.

### Request body

The request body contains data sent by the client.

POST, PUT, and PATCH commonly use JSON request bodies.

For example, a user creation request can contain fields such as:

`name`

`email`

`age`

### Response

A response contains the result returned by the server.

It includes an HTTP status code, headers, and optionally a response body.

### Status code

HTTP status codes communicate the result of a request.

Important codes used in the implementations include:

| Status | Meaning |
|---|---|
| 200 | Successful request |
| 201 | Resource created |
| 204 | Successful request with no response body |
| 400 | Invalid client request |
| 401 | Authentication required or invalid |
| 403 | Access denied |
| 404 | Resource not found |
| 409 | Conflict with current resource state |
| 422 | Validation failure |
| 500 | Unexpected server failure |

## FastAPI route declaration

FastAPI uses decorators to associate functions with HTTP routes.

A simple GET route is represented by:

`@app.get("/")`

The decorated function becomes the handler for GET requests to `/`.

The same application can register different handlers for different methods and paths.

The basic pattern is:

`@app.<method>("<path>")`

followed by a Python function.

Examples in the Python implementation include:

- `@app.get("/")`
- `@app.get("/users/{user_id}")`
- `@app.post("/api/users")`
- `@app.put("/api/users/{user_id}")`
- `@app.patch("/api/users/{user_id}")`
- `@app.delete("/api/users/{user_id}")`

## GET routes

GET is used to retrieve a representation of a resource.

The Python implementation contains both collection and individual-resource GET routes.

The collection route is:

`GET /api/users`

The individual-resource route is:

`GET /api/users/{user_id}`

These have different responsibilities.

The collection route returns multiple users and supports pagination.

The individual route retrieves one user.

### GET and route parameters

The route:

`/api/users/{user_id}`

contains a dynamic segment.

The Python function declares:

`user_id: int`

FastAPI uses the type annotation to validate and convert the incoming path value.

A request such as:

`/api/users/42`

produces the integer:

`42`

A request such as:

`/api/users/abc`

cannot be converted into the required integer representation and results in request validation failure.

### GET and query parameters

The Python implementation also demonstrates:

`GET /search?q=fastapi&page=2&page_size=20`

The query parameters are declared using FastAPI's `Query`.

The example validates:

- minimum query length
- maximum query length
- minimum page number
- minimum and maximum page size

This prevents unrestricted or malformed input from entering application logic.

## POST routes

POST commonly creates a new resource.

The Python implementation provides:

`POST /api/users`

The request body is represented by `UserCreate`.

The model validates:

- name length
- email format normalization
- age range
- unexpected fields

When creation succeeds, the route returns HTTP 201.

The implementation also checks for duplicate email addresses and returns HTTP 409 when the requested state conflicts with an existing resource.

### Why POST uses the collection path

A common REST-oriented design is:

`POST /api/users`

rather than:

`POST /api/users/42`

The server normally chooses the new resource identifier.

The Python implementation maintains an in-memory counter and assigns the next identifier.

A production application would normally delegate identifier management to a database or another durable persistence system.

## PUT routes

PUT is used for replacement semantics.

The Python implementation provides:

`PUT /api/users/{user_id}`

The request uses `UserUpdate`, which requires the complete representation.

For example, the conceptual representation contains:

- name
- email
- age

PUT therefore differs from PATCH in the amount of state supplied.

The implementation first verifies that the target resource exists. It then validates the replacement and checks for conflicts such as duplicate email addresses.

A successful replacement returns HTTP 200.

## PATCH routes

PATCH is intended for partial modification.

The Python implementation provides:

`PATCH /api/users/{user_id}`

The `UserPatch` model makes each field optional.

A request can therefore modify only one property.

For example, the client can provide only `age`.

The implementation uses:

`model_dump(exclude_unset=True)`

This is important because PATCH needs to distinguish between:

- a field that was omitted
- a field that was explicitly supplied

The resulting dictionary contains only fields actually supplied by the client.

### PATCH and replacement are different

Suppose a user has:

- name = Ada Lovelace
- email = ada@example.com
- age = 28

A PUT request conceptually supplies the complete representation.

A PATCH request can supply:

`{"age": 29}`

The server keeps the existing name and email while changing only the age.

The C++ implementation models the same behavior with `std::optional`.

## DELETE routes

DELETE removes a resource.

The Python implementation provides:

`DELETE /api/users/{user_id}`

The route verifies that the user exists and removes it from the in-memory dictionary.

It returns HTTP 204.

A 204 response intentionally has no response body.

The JavaScript implementation accounts for this by not attempting to parse a JSON body after a successful DELETE.

## Route parameters

Route parameters are particularly useful when the URL identifies a specific resource.

Examples include:

- `/users/{user_id}`
- `/products/{product_id}`
- `/articles/{slug}`
- `/orders/{order_id}`

The Python implementation demonstrates integer and string route parameters.

### Typed route parameters

A declaration such as:

`user_id: int`

provides type information to FastAPI.

This affects validation, conversion, generated documentation, and the resulting OpenAPI schema.

Additional constraints can be supplied with `Path`.

The Python implementation requires product identifiers to be at least 1.

This prevents values such as:

`/products/0`

from being accepted when zero is not a meaningful resource identifier.

### Route parameters are not query parameters

These two URLs have different structures:

`/api/users/42`

and:

`/api/users?id=42`

The first uses a path parameter.

The second uses a query parameter.

A path parameter normally identifies the resource being addressed.

A query parameter normally modifies how a collection or operation is processed.

## Static and dynamic routes

The Python implementation includes:

`/reports/latest`

and:

`/reports/{report_id}`

Static paths and dynamic paths need to be designed carefully so that route matching remains unambiguous.

A literal resource such as `latest` may represent a special operation or resource rather than a numeric identifier.

API design should avoid overlapping route patterns that make endpoint behavior difficult to understand.

## Nested routes

The Python implementation includes:

`GET /users/{user_id}/orders`

This expresses a relationship between users and orders.

Nested resources can be useful when the child resource is strongly associated with a parent.

The design should remain understandable. Excessively deep paths can make APIs harder to maintain.

A path such as:

`/companies/{company_id}/departments/{department_id}/teams/{team_id}/members/{member_id}`

may indicate that the API should consider whether all relationships need to be represented directly in the URL.

## Query parameters and pagination

Returning an unlimited collection can become expensive.

The Python implementation uses:

`limit`

and:

`offset`

For example:

`/api/users?limit=20&offset=40`

means that the client requests a bounded section of the collection.

The implementation validates the limits so clients cannot request arbitrarily large result sets.

Production systems may use other pagination strategies, such as cursor-based pagination, when collections are large or frequently changing.

## Request validation

FastAPI integrates strongly with Pydantic models.

The Python implementation defines:

`UserCreate`

`UserUpdate`

`UserPatch`

and:

`ProductCreate`

These models provide structured validation before business logic executes.

Examples include:

- minimum and maximum string lengths
- numeric ranges
- normalized email values
- rejection of unexpected fields
- required versus optional fields

This creates an explicit contract between the client and server.

## Error handling

The Python implementation uses `HTTPException` for application-level errors.

Examples include:

- 404 when a user does not exist
- 409 when an email conflicts with another user
- 422 for validation failures

The application also defines a custom `RequestValidationError` handler.

The handler standardizes validation responses while retaining the validation details produced by FastAPI.

A production application should expose useful client-facing errors without leaking internal implementation details.

## Python implementation

The Python script is the primary implementation of FastAPI routing.

It demonstrates:

- FastAPI application creation
- GET routes
- POST routes
- PUT routes
- PATCH routes
- DELETE routes
- route parameters
- query parameters
- request body models
- validation
- status codes
- pagination
- nested resources
- static and dynamic routes
- conflict detection
- 404 handling
- custom validation errors
- in-memory CRUD operations
- partial update semantics
- local validation checks
- production design considerations

The script can be executed directly to display the routing concepts and registered routes.

The actual API server can be started with:

`uvicorn fastapi_routing:app --reload`

The automatically generated Swagger documentation is available at:

`/docs`

The alternative ReDoc interface is available at:

`/redoc`

## JavaScript implementation

The JavaScript implementation represents a client communicating with the FastAPI application.

It demonstrates:

- HTTP method semantics
- URL construction
- route parameter encoding
- query parameter construction
- GET requests
- POST requests
- PUT requests
- PATCH requests
- DELETE requests
- JSON request bodies
- response status handling
- asynchronous requests
- concurrent requests
- client-side validation
- timeout handling
- PATCH-style local state merging
- security considerations
- performance considerations

### Fetch API

The implementation uses the standard `fetch` API.

The reusable `requestJson` function:

1. Sends an HTTP request.
2. Sets appropriate JSON headers.
3. Reads JSON responses when appropriate.
4. Preserves non-JSON responses.
5. Converts unsuccessful HTTP responses into JavaScript exceptions.

This keeps individual API functions small.

### URLSearchParams

The JavaScript implementation uses `URLSearchParams` for query strings.

This is safer and more reliable than manually concatenating query parameters because values can contain spaces and reserved characters.

For example:

`FastAPI routing & validation`

must be encoded correctly when placed into a URL.

### encodeURIComponent

Route parameter values can contain characters that have special meaning in URLs.

The JavaScript implementation uses `encodeURIComponent` when inserting a parameter into a path.

This is particularly important for values containing:

- spaces
- slashes
- question marks
- percent signs
- other reserved characters

A resource identifier should not accidentally change the structure of the URL.

## Asynchronous behavior

Network requests are asynchronous operations.

The JavaScript implementation uses `async` and `await` to make asynchronous API calls readable.

It also demonstrates `Promise.all`.

When independent requests can execute concurrently, `Promise.all` avoids unnecessary sequential waiting.

For example, retrieving users 1 and 2 can be represented as multiple promises and awaited together.

Concurrency should still be used carefully. Sending hundreds or thousands of simultaneous requests can overload the server or the network.

## Timeout handling

The JavaScript implementation uses `AbortController`.

A request can be associated with a timer. If the request exceeds the configured limit, the controller aborts it.

Timeouts are useful because network requests can fail through:

- server delays
- network interruptions
- connection problems
- overloaded services
- infrastructure failures

The appropriate timeout depends on the operation.

## C++ case study

The C++ implementation models a small API service architecture without external HTTP dependencies.

Its purpose is to demonstrate how routing-related concepts translate into a strongly typed systems language.

The case study contains:

- HTTP method modeling
- HTTP response modeling
- user domain objects
- request objects
- validation
- route construction
- path parameter encoding
- an in-memory repository
- CRUD operations
- pagination
- status codes
- error handling
- partial updates
- duplicate detection
- design trade-offs
- complexity considerations
- security considerations

## C++ system architecture

The implementation separates responsibilities into several components.

### HttpMethod

`HttpMethod` is an enumeration representing the five main methods covered by the project.

This avoids passing arbitrary method strings through the entire application.

### HttpResponse

`HttpResponse` represents:

- status code
- response body

It also provides `isSuccess()` to determine whether the response belongs to the 2xx range.

### User

`User` represents the persisted domain object.

It contains:

- id
- name
- email
- age

### Request models

Three structures represent different write operations:

`UserCreateRequest`

`UserReplaceRequest`

`UserPatchRequest`

The distinction is important because POST, PUT, and PATCH do not necessarily carry the same contract.

### UserPatchRequest

The PATCH request uses `std::optional`.

This allows the application to distinguish between an omitted field and a field that has a value.

For example:

`std::optional<int> age`

can represent both:

- no age change
- a requested new age

This closely models partial-update semantics.

## Repository pattern

The C++ case study uses `UserRepository` to isolate storage operations.

The repository provides:

- find
- list
- email existence checks
- create
- replace
- delete

The route-like API service does not directly manipulate the underlying container for every operation.

This separation is useful because a production implementation could replace the in-memory repository with a database-backed repository without changing the conceptual endpoint interface.

## In-memory storage

The case study uses:

`std::map<int, User>`

as its storage structure.

This provides ordered keys and logarithmic lookup, insertion, and deletion.

It is appropriate for a small educational system but is not a replacement for durable production storage.

Data disappears when the process terminates.

A production API generally requires persistent storage, transaction handling, concurrency control, backups, and appropriate database constraints.

## POST case study

The C++ `post` operation:

1. Validates the request.
2. Normalizes the email.
3. Checks for duplicate email addresses.
4. Creates a user.
5. Assigns an identifier.
6. Returns HTTP 201.

This corresponds conceptually to:

`POST /api/users`

## GET case study

The C++ `getCollection` method represents:

`GET /api/users`

It accepts:

- limit
- offset

and produces a bounded collection.

The `getItem` method represents:

`GET /api/users/{user_id}`

It returns 404 when the requested resource does not exist.

## PUT case study

The C++ `put` method requires a complete replacement request.

It verifies:

- validation
- resource existence
- email uniqueness

It then replaces the stored representation.

This models the complete replacement semantics associated with PUT.

## PATCH case study

The C++ `patch` method applies only the fields present in the `UserPatchRequest`.

The implementation validates each supplied field independently.

This prevents a PATCH request that changes one field from unintentionally erasing the remaining fields.

An empty PATCH request is rejected because it does not specify any change.

## DELETE case study

The C++ `deleteItem` method:

1. Verifies that the resource exists.
2. Removes it.
3. Returns HTTP 204.

A subsequent GET demonstrates that the resource is no longer available and returns HTTP 404.

## Route construction

The C++ `RouteBuilder` represents the client-side problem of constructing URLs.

For example:

`http://127.0.0.1:8000/api/users/42`

is generated from a base URL, resource name, and identifier.

The implementation also URL-encodes unsafe path characters.

This is important because identifiers can contain characters that have structural meaning in URLs.

## Route parameter encoding

The C++ implementation encodes characters outside the unreserved URL character set.

For example, a space becomes `%20`.

A slash in a parameter becomes `%2F`.

This prevents a parameter value from accidentally being interpreted as an additional path segment.

## Validation model

The C++ `UserValidator` centralizes validation.

The same basic rules apply to create and replacement operations.

The implementation checks:

- name length
- email structure
- age range

Validation is performed before storage operations.

This is an important architectural boundary because invalid data should normally be rejected before it reaches persistence or downstream services.

## Failure conditions

The case study deliberately demonstrates several failures.

### Invalid POST

An empty name, malformed email, and invalid age produce a validation response.

### Empty PATCH

A PATCH containing no fields produces HTTP 400.

### Missing resource

A GET for a nonexistent user produces HTTP 404.

### Duplicate resource state

Creating another user with an existing email produces HTTP 409.

These examples show that error handling is part of route design rather than an afterthought.

## HTTP method comparison

| Property | GET | POST | PUT | PATCH | DELETE |
|---|---|---|---|---|---|
| Typical operation | Read | Create | Replace | Modify | Remove |
| Request body | Optional | Common | Common | Common | Usually unnecessary |
| Resource identifier | Often in path | Usually generated by server | Usually in path | Usually in path | Usually in path |
| Typical success | 200 | 201 | 200 | 200 | 204 |
| Safe by HTTP semantics | Yes | No | No | No | No |
| Intended idempotency | Yes | No | Yes | Depends on operation | Generally yes |

Idempotency describes whether repeating the same request has the same intended effect as performing it once.

PUT is designed to be idempotent when the same representation is repeatedly applied.

POST is generally not idempotent because repeating a creation request may create multiple resources.

PATCH depends on the specific patch operation. A patch that sets a field to a fixed value can be idempotent, while a patch that increments a counter may not be.

DELETE is generally designed so that the desired final state remains deleted, even though subsequent calls may return 404.

## Route design principles

A well-designed route structure makes resource relationships clear.

A common resource-oriented structure is:

`GET /api/users`

`POST /api/users`

`GET /api/users/{user_id}`

`PUT /api/users/{user_id}`

`PATCH /api/users/{user_id}`

`DELETE /api/users/{user_id}`

The collection path represents the resource collection.

The path containing an identifier represents an individual resource.

This structure also avoids inventing different nouns for each operation.

## Common mistakes

### Using POST for every operation

POST can perform many kinds of operations, but using it indiscriminately makes an API less expressive.

GET, PUT, PATCH, and DELETE communicate different intended semantics.

### Treating PUT and PATCH as identical

PUT represents replacement semantics.

PATCH represents partial modification.

Using the same request model for both can make the API contract ambiguous.

### Trusting route parameters

A route parameter is client-controlled input.

A numeric identifier still needs authorization checks.

Knowing `/api/users/42` does not establish that the caller is allowed to access user 42.

### Returning unbounded collections

An endpoint that returns every record can become increasingly expensive as the dataset grows.

Pagination should be considered for large collections.

### Returning the wrong status code

Examples of meaningful distinctions include:

- 201 for successful creation
- 204 for successful deletion with no body
- 404 for a missing resource
- 409 for a resource-state conflict
- 422 for validation failure

Status codes are part of the API contract.

### Ignoring validation

Validation should occur at the API boundary.

It reduces invalid downstream operations and makes failures easier for clients to understand.

### Leaking internal errors

Internal database errors, stack traces, credentials, file paths, and implementation details should not normally be returned directly to clients.

## Edge cases

Important edge cases include:

- negative numeric route parameters
- zero identifiers
- non-numeric identifiers where integers are expected
- missing resources
- duplicate unique values
- empty PATCH requests
- invalid request bodies
- unexpected request fields
- excessively large pagination values
- special characters in path parameters
- special characters in query parameters
- empty collections
- repeated DELETE operations
- concurrent updates
- stale client representations

The Python implementation validates several of these conditions directly.

The JavaScript implementation also demonstrates URL encoding, client-side validation, timeout handling, and handling of a 204 DELETE response.

The C++ implementation models the corresponding service-level behavior.

## Exceptions and error boundaries

FastAPI automatically performs validation based on route annotations and Pydantic models.

Application-specific conditions can be represented using `HTTPException`.

The Python implementation separates:

- framework validation
- resource lookup
- business validation
- conflict detection
- successful CRUD operations

This separation makes the endpoint behavior easier to reason about.

## Performance considerations

Route matching itself is usually not the dominant cost in an API.

Real-world performance is commonly affected by:

- database queries
- network latency
- external service calls
- serialization
- CPU-intensive operations
- large response bodies
- inefficient algorithms
- excessive logging
- contention
- connection management

The Python example uses pagination to control collection size.

The C++ example uses `std::map`, which provides O(log n) lookup, insertion, and deletion.

A production database can use indexed columns for efficient resource lookup.

For very large collections, cursor-based pagination can be more appropriate than offset-based pagination.

## Asynchronous considerations

FastAPI supports asynchronous route handlers.

Asynchronous execution is especially useful when route handlers spend significant time waiting for I/O, such as:

- database operations
- HTTP calls
- file operations
- message brokers

CPU-heavy work should be considered separately because asynchronous syntax does not automatically make CPU-bound computation non-blocking.

The JavaScript implementation demonstrates asynchronous HTTP calls using `async` and `await`.

## Security considerations

Routing is an important security boundary.

### Authentication

Authentication determines who the caller is.

### Authorization

Authorization determines what the authenticated caller is allowed to do.

For example:

`GET /api/users/42`

should not automatically grant every authenticated user permission to retrieve user 42.

### Input validation

All client-controlled values should be treated as untrusted.

This includes:

- route parameters
- query parameters
- request bodies
- headers
- cookies

### HTTPS

Production APIs should use HTTPS to protect data in transit.

### Rate limiting

Public APIs can require rate limiting to reduce abuse and resource exhaustion.

### Sensitive information

Secrets and sensitive credentials should not be placed in URLs because URLs may appear in logs, browser history, monitoring systems, or other infrastructure.

### Error disclosure

Client-facing errors should provide useful information without exposing internal implementation details.

## Production implementation considerations

The Python example uses an in-memory dictionary so that routing behavior remains easy to inspect.

A production system would normally separate the application into layers such as:

- routing
- request and response schemas
- authentication
- authorization
- business services
- repositories
- database models
- persistence
- external integrations
- observability

FastAPI routers can be used to divide large applications into modules.

For example, users, products, orders, authentication, and administration can have separate route modules.

This prevents a single application file from becoming difficult to maintain.

## Testing considerations

Routing tests should cover both successful and unsuccessful requests.

Important tests include:

- GET collection
- GET existing resource
- GET nonexistent resource
- POST valid resource
- POST invalid resource
- POST duplicate resource
- PUT existing resource
- PUT nonexistent resource
- PUT invalid resource
- PATCH one field
- PATCH multiple fields
- PATCH empty body
- PATCH nonexistent resource
- DELETE existing resource
- DELETE nonexistent resource
- pagination boundaries
- invalid path parameters
- invalid query parameters
- authorization failures

Testing should verify both response status codes and response bodies.

## API contract considerations

A route is more than a Python function.

Its contract includes:

- HTTP method
- URL path
- path parameters
- query parameters
- request headers
- request body
- validation rules
- response status
- response headers
- response body
- authentication requirements
- authorization requirements
- error behavior

The Python implementation demonstrates many of these properties directly through FastAPI declarations and Pydantic models.

## Practical API structure

A user CRUD API can be modeled as:

`GET /api/users`

Returns a collection.

`POST /api/users`

Creates a user.

`GET /api/users/{user_id}`

Returns one user.

`PUT /api/users/{user_id}`

Replaces one user.

`PATCH /api/users/{user_id}`

Partially updates one user.

`DELETE /api/users/{user_id}`

Removes one user.

This structure forms the central case study shared by the three implementations.

## Relationship between the three implementations

### Python

Python provides the framework-level implementation.

It demonstrates how FastAPI converts route declarations and type annotations into an executable HTTP API.

It also demonstrates automatic validation and generated API documentation.

### JavaScript

JavaScript demonstrates the client perspective.

It shows how a frontend or other JavaScript application can:

- build URLs
- encode parameters
- send JSON
- await HTTP requests
- process status codes
- perform concurrent requests
- enforce client-side validation
- handle timeouts

### C++

C++ demonstrates a strongly typed systems-oriented model.

It focuses on:

- domain structures
- request structures
- validation
- repositories
- service logic
- HTTP method modeling
- route construction
- error handling
- algorithmic complexity
- resource state transitions

The same API concepts therefore appear at three different architectural levels.

## Important distinctions

### Path parameter versus query parameter

Path parameter:

`/users/42`

Query parameter:

`/users?limit=20`

The path parameter identifies the resource.

The query parameter modifies how the collection or operation is handled.

### PUT versus PATCH

PUT replaces the resource representation.

PATCH modifies part of the resource.

### POST versus PUT

POST commonly asks the server to create a new resource within a collection.

PUT targets a known resource identifier and replaces its representation.

### 404 versus 422

404 means the requested resource was not found.

422 means the request data failed validation.

### 409 versus 422

409 represents a conflict with the current state of the resource system.

422 represents semantically invalid request data.

The exact API policy can vary, but consistent behavior is important.

## Limitations of the educational implementation

The Python application intentionally uses in-memory data structures.

Consequently:

- data is lost after process termination
- there is no database transaction layer
- there is no multi-process shared state
- there is no authentication system
- there is no authorization system
- there is no production-grade rate limiting
- there is no distributed locking
- there is no external persistence
- there is no production observability stack

The JavaScript file demonstrates HTTP client behavior but does not implement a complete frontend application.

The C++ program models the service and routing concepts without depending on an external HTTP framework or JSON library. Its JSON serialization is intentionally limited to the small user structure used by the case study.

These limitations keep the implementations self-contained while preserving the important routing concepts.

## Best practices

Use clear resource-oriented paths.

Use HTTP methods according to their intended semantics.

Use typed path parameters.

Validate query parameters.

Validate request bodies with explicit models.

Return appropriate HTTP status codes.

Keep route handlers focused on HTTP concerns.

Move complex business logic into services.

Separate persistence from route handlers.

Use pagination for potentially large collections.

Treat all client input as untrusted.

Perform authentication and authorization before protected operations.

Do not expose internal implementation errors.

Design PUT and PATCH contracts explicitly.

Use consistent error response structures.

Test both successful and failure paths.

Document the API contract.

Consider idempotency when designing write operations.

Use HTTPS in production.

Use durable persistence for production data.

Consider concurrency and transaction behavior when multiple clients can update the same resource.

## Real-world relevance

The routing model demonstrated here applies to systems such as:

- user management APIs
- e-commerce services
- financial applications
- inventory systems
- project-management platforms
- content-management systems
- analytics platforms
- authentication services
- enterprise applications
- mobile application backends
- web application backends
- internal microservices

The same principles remain relevant even when the underlying storage, authentication model, deployment architecture, or frontend technology changes.

A route is ultimately an interface between a client and a server-side capability. Clear method semantics, explicit resource identifiers, validation, appropriate status codes, and well-defined update behavior make that interface easier to use, test, secure, and maintain.
