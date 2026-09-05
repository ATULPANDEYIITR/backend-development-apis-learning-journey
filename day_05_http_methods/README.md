# HTTP Methods: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, Idempotency and Safe Methods

## 1. Introduction

HTTP methods define the intended semantics of requests exchanged between HTTP clients and servers. They communicate what the client is asking the server to do with a target resource or representation.

The principal methods examined in the accompanying Python script are:

- `GET`
- `POST`
- `PUT`
- `PATCH`
- `DELETE`
- `HEAD`
- `OPTIONS`

The script also examines two fundamental HTTP properties:

- **Safety**
- **Idempotency**

The distinction between these properties is essential when designing APIs, handling retries, configuring caches, implementing security controls, and building reliable distributed systems.

HTTP methods should not be treated as arbitrary labels. Their semantics influence caching, retry behavior, browser behavior, intermediaries, authorization, and API design.

---

## 2. Basic HTTP Request and Response Model

An HTTP interaction normally consists of a request from a client and a response from a server.

A conceptual request contains:

- Method
- Request target
- Headers
- Optional body

For example:

    GET /users/42 HTTP/1.1
    Host: example.com
    Accept: application/json

A response contains:

- Status code
- Headers
- Optional body

For example:

    HTTP/1.1 200 OK
    Content-Type: application/json

    {"id":42,"name":"Alice"}

The Python script represents these concepts through the `HTTPRequest` and `HTTPResponse` classes.

The purpose of these classes is educational. They model the structure of HTTP without requiring a real web server or third-party HTTP framework.

---

## 3. HTTP Method Terminology

A method communicates the intended operation.

### GET

`GET` retrieves a representation of a resource.

Typical examples:

    GET /users
    GET /users/42
    GET /products?category=books

GET is:

- Safe
- Idempotent
- Commonly cacheable when response headers permit caching

A GET request should not be designed to perform an ordinary business-state mutation.

---

### POST

`POST` submits a representation for processing.

A common API design is:

    POST /users

with a request body such as:

    {
        "name": "Alice",
        "email": "alice@example.com"
    }

The server can create the resource and return:

    201 Created

with a `Location` header identifying the new resource.

POST is generally not idempotent. Sending the same POST twice can result in two distinct operations or resources.

POST is useful for operations where the server determines the resulting resource identifier or where the request represents an action or submission rather than replacement of a known target representation.

---

### PUT

`PUT` requests creation or replacement of the representation associated with a target URI.

For example:

    PUT /users/42

can submit the representation of user `42`.

The important semantic distinction is that PUT is associated with replacement rather than simply changing whichever fields happen to appear in the request.

If the existing resource is:

    {
        "name": "Alice",
        "email": "alice@example.com",
        "city": "Delhi"
    }

and a PUT operation submits:

    {
        "name": "Alice Updated",
        "email": "alice.updated@example.com"
    }

the replacement representation does not conceptually retain `city` merely because the field was omitted.

An API can impose additional validation requirements, such as requiring all fields of a complete representation.

PUT is idempotent when the operation follows its intended replacement semantics.

---

### PATCH

`PATCH` applies partial modifications to a resource.

For example:

    PATCH /users/42

with:

    {
        "city": "Lucknow"
    }

can change only the city while preserving other fields.

PATCH is particularly useful when transmitting a complete representation would be unnecessary or inefficient.

PATCH does not automatically mean that the operation is idempotent.

An operation such as:

    {
        "status": "active"
    }

can be idempotent because applying it repeatedly leaves the resource in the same intended state.

An operation such as:

    {
        "operation": "increment",
        "amount": 10
    }

is not idempotent if each application increases the value again.

Therefore, idempotency for PATCH depends on the semantics of the particular patch operation.

---

### DELETE

`DELETE` requests removal of a target resource.

Example:

    DELETE /users/42

A successful deletion can return:

    204 No Content

The resource can be absent after the first request and remain absent after subsequent requests.

DELETE is therefore idempotent with respect to the intended resource state, even though repeated DELETE requests do not necessarily produce identical response codes.

For example:

- First DELETE may return `204 No Content`
- Second DELETE may return `404 Not Found`

The differing responses do not invalidate the idempotent property.

---

### HEAD

`HEAD` requests the metadata that would accompany a corresponding GET response, without returning response content.

For example:

    HEAD /files/report.pdf

can allow a client to inspect:

- Whether the resource exists
- Content length
- Content type
- ETag
- Last-Modified metadata

without downloading the actual representation.

HEAD is:

- Safe
- Idempotent

It is useful when a client needs metadata rather than the complete response body.

---

### OPTIONS

`OPTIONS` is used to discover communication options supported by a server or target resource.

A response can include:

    Allow: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS

OPTIONS is also important in Cross-Origin Resource Sharing, commonly abbreviated as CORS.

Browsers can issue preflight requests using OPTIONS before certain cross-origin requests.

OPTIONS is:

- Safe
- Idempotent

---

## 4. Safe HTTP Methods

A safe method is defined in terms of its intended semantics as read-only from the client's perspective.

The primary safe methods covered here are:

- GET
- HEAD
- OPTIONS

Safety does not mean that absolutely no server-side activity occurs.

A GET request can cause:

- Logging
- Metrics collection
- Authentication checks
- Cache access
- Database reads
- Internal computation

These activities do not make GET unsafe.

The important principle is that the request's intended semantics should not be state-changing.

A dangerous design would be:

    GET /delete-account?id=42

A state-changing operation should instead use an appropriate state-changing method such as:

    DELETE /accounts/42

The distinction is important for browsers, crawlers, caches, security mechanisms, and automated clients.

---

## 5. Idempotency

Idempotency is a property describing the effect of repeating an operation.

Conceptually, if an operation is idempotent:

    f(f(state)) = f(state)

The final intended state after applying it multiple times is the same as after applying it once.

The major methods have these general semantics:

| Method | Safe | Idempotent |
|---|---:|---:|
| GET | Yes | Yes |
| HEAD | Yes | Yes |
| OPTIONS | Yes | Yes |
| POST | No | Generally no |
| PUT | No | Yes |
| DELETE | No | Yes |
| PATCH | No | Depends on operation |

The table describes HTTP method semantics, not an absolute guarantee about every poorly implemented server.

---

## 6. Idempotency Does Not Mean Identical Responses

A common misunderstanding is:

> Idempotent means every repeated request returns exactly the same response.

That is incorrect.

Consider:

    DELETE /users/42

The first request might produce:

    204 No Content

A second request might produce:

    404 Not Found

The final intended state can still be the same: user `42` is absent.

Idempotency concerns the intended effect on resource state, not the requirement that every response be byte-for-byte identical.

Logging, timestamps, metrics, auditing, and other internal activities can also occur during repeated requests without necessarily violating HTTP idempotency.

---

## 7. GET, POST, PUT, PATCH and DELETE Comparison

A resource-oriented API can commonly expose:

    GET    /users
    POST   /users
    GET    /users/42
    PUT    /users/42
    PATCH  /users/42
    DELETE /users/42

Their conceptual roles are:

| Method | Typical purpose |
|---|---|
| GET | Retrieve |
| POST | Submit or create through server-assigned processing |
| PUT | Replace or create at a known target URI |
| PATCH | Partially modify |
| DELETE | Remove |

This is a useful resource-oriented design pattern, but HTTP is broader than REST-style CRUD.

---

## 8. POST Versus PUT

POST and PUT are frequently confused.

### POST

A common POST design is:

    POST /orders

The client submits an order representation, and the server determines the resulting resource URI.

For example:

    POST /orders

can produce:

    Location: /orders/1001

The client did not necessarily select `/orders/1001`.

### PUT

PUT commonly targets a known URI:

    PUT /orders/1001

The client is addressing the representation associated with `/orders/1001`.

This distinction is also related to idempotency.

POST is generally non-idempotent.

PUT is idempotent when implemented according to its replacement semantics.

---

## 9. PUT Versus PATCH

PUT and PATCH are both used for updates, but their semantics differ.

### PUT

PUT is associated with replacement.

Example:

    PUT /users/42

    {
        "name": "Alice",
        "email": "alice@example.com",
        "city": "Lucknow"
    }

The submitted representation is intended to represent the new state of the target.

### PATCH

PATCH is associated with partial modification.

Example:

    PATCH /users/42

    {
        "city": "Lucknow"
    }

The server applies the requested modification while retaining fields that are not being changed.

The script demonstrates both behaviors with dictionaries.

---

## 10. PATCH Idempotency

PATCH deserves special attention because it has no blanket idempotency guarantee.

Consider:

    PATCH /accounts/42

    {
        "balance": 1000
    }

Repeatedly applying this operation can produce the same balance.

This operation is effectively idempotent.

Compare it with:

    PATCH /accounts/42

    {
        "increment_balance": 100
    }

Applying it once might produce:

    1100

Applying it twice might produce:

    1200

The second operation is not idempotent.

The correct question is therefore not:

> Is PATCH idempotent?

The better question is:

> Is this particular PATCH operation idempotent?

---

## 11. Status Codes

HTTP methods describe intended operations. Status codes describe outcomes.

The script demonstrates the main status-code classes:

| Class | Meaning |
|---|---|
| 1xx | Informational |
| 2xx | Successful |
| 3xx | Redirection |
| 4xx | Client-side error |
| 5xx | Server-side or upstream failure |

Important examples include:

### 200 OK

The request succeeded and the server is returning a successful representation or result.

### 201 Created

A new resource was created.

This is especially common after successful POST operations.

### 202 Accepted

The request has been accepted for processing but may not yet be completed.

This is useful for asynchronous processing.

### 204 No Content

The request succeeded and there is no response content to return.

It is commonly used for successful DELETE or update operations.

### 304 Not Modified

Used with conditional retrieval to indicate that the cached representation can still be used.

### 400 Bad Request

The request is invalid or malformed at a general request level.

### 401 Unauthorized

Authentication credentials are missing or invalid.

The term can be confusing because the actual issue generally concerns authentication.

### 403 Forbidden

The server understands the request but refuses to authorize it.

### 404 Not Found

The target resource is not available.

### 405 Method Not Allowed

The resource exists but does not support the requested HTTP method.

An `Allow` header can communicate supported methods.

### 409 Conflict

The request conflicts with the current state of the resource or application.

### 412 Precondition Failed

A conditional request precondition was not satisfied.

This is important for optimistic concurrency control.

### 415 Unsupported Media Type

The server does not support the representation format sent by the client.

### 422 Unprocessable Content

The request is understood but fails semantic validation under the API's contract.

### 429 Too Many Requests

The client has exceeded a configured rate limit.

### 500 Internal Server Error

The server encountered an unexpected condition.

### 503 Service Unavailable

The service is temporarily unable to handle the request, often because of overload or maintenance.

---

## 12. The Allow Header

When a resource exists but does not support a requested method, a server can respond with:

    405 Method Not Allowed

and:

    Allow: GET, HEAD, OPTIONS

The `Allow` header helps clients understand which methods are supported for the target resource.

The Python router demonstrates this behavior.

This distinction is important:

    404 = target route/resource is not available

    405 = target exists, but this method is not allowed

---

## 13. URL Structure

A URL can contain several components.

Example:

    https://example.com:443/api/users/42?active=true&sort=name#profile

Its components include:

- Scheme: `https`
- Host: `example.com`
- Port: `443`
- Path: `/api/users/42`
- Query: `active=true&sort=name`
- Fragment: `profile`

The fragment is normally handled by the client and is not transmitted to the server as part of the HTTP request target.

The Python script uses `urllib.parse` to demonstrate URL parsing.

---

## 14. Query Parameters

GET requests commonly use query parameters for retrieval-related criteria.

Example:

    GET /products?category=books&page=2&limit=20

Typical uses include:

- Filtering
- Sorting
- Pagination
- Search
- Field selection

Query parameters should be encoded correctly.

The script uses `urlencode()` rather than manually concatenating user-controlled values.

This avoids common URL encoding errors involving spaces, ampersands, Unicode characters, and reserved characters.

---

## 15. Request Headers and Response Headers

HTTP headers carry metadata.

Important request headers include:

- `Accept`
- `Content-Type`
- `Authorization`
- `If-None-Match`
- `If-Match`
- `If-Modified-Since`
- `If-Unmodified-Since`
- `Idempotency-Key`

Important response headers include:

- `Content-Type`
- `Content-Length`
- `Location`
- `ETag`
- `Cache-Control`
- `Allow`
- `Retry-After`
- CORS-related headers

HTTP header field names are case-insensitive. The script therefore demonstrates normalization of header names.

---

## 16. Content-Type Versus Accept

These two headers have different meanings.

### Content-Type

Describes the media type of the representation being sent.

Example:

    Content-Type: application/json

This tells the server how the request body should be interpreted.

### Accept

Describes which response representations the client can accept.

Example:

    Accept: application/json

The distinction is:

    Content-Type = what I am sending

    Accept = what I want to receive

Confusing these headers is a common API implementation mistake.

---

## 17. Conditional Requests

HTTP provides mechanisms that allow clients to make requests conditional on resource state.

An important mechanism is the ETag.

Example:

    ETag: "abc123"

A client can later send:

    If-None-Match: "abc123"

For a GET request, if the resource has not changed, the server can return:

    304 Not Modified

This avoids sending the representation again.

The script creates deterministic ETag-like values using SHA-256 hashing.

---

## 18. Optimistic Concurrency Control

Conditional requests can also protect updates from lost changes.

Suppose:

1. Client A reads version 5.
2. Client B updates the resource to version 6.
3. Client A attempts to overwrite the resource using its stale version 5.

Client A can send:

    If-Match: "version-5"

The server compares the supplied condition with the current resource version.

If they do not match, the server can return:

    412 Precondition Failed

This prevents a stale client from blindly overwriting a newer state.

This is an important pattern for concurrent systems.

---

## 19. HEAD and Metadata

HEAD is particularly useful when downloading a representation would be unnecessary.

A client might use HEAD to inspect:

    Content-Length
    Content-Type
    ETag
    Last-Modified

before deciding whether to download the full representation.

The script demonstrates that the simulated HEAD response contains metadata but no body.

---

## 20. OPTIONS and Capability Discovery

OPTIONS can communicate the methods available for a target.

For example:

    OPTIONS /users/42

could produce:

    Allow: GET, PUT, PATCH, DELETE, HEAD, OPTIONS

This is useful for clients and also plays a role in CORS preflight processing.

OPTIONS itself should not be confused with authorization. Knowing that DELETE is supported does not mean a particular user is authorized to perform DELETE.

---

## 21. CORS

Cross-Origin Resource Sharing, or CORS, controls how browsers permit web applications to make cross-origin requests.

A simplified preflight can look conceptually like:

    OPTIONS /api/users

with headers such as:

    Origin: https://client.example
    Access-Control-Request-Method: PATCH
    Access-Control-Request-Headers: Content-Type, Authorization

The server can respond with:

    Access-Control-Allow-Origin
    Access-Control-Allow-Methods
    Access-Control-Allow-Headers

The script implements a simple explicit allowlist.

A critical security principle is that CORS is not an authentication system.

CORS does not replace:

- Authentication
- Authorization
- CSRF protection
- Input validation

Production systems should use explicit origin policies rather than blindly allowing arbitrary origins.

---

## 22. Authentication and Authorization

HTTP methods do not provide authorization by themselves.

Authentication answers:

> Who is making the request?

Authorization answers:

> What is this authenticated principal allowed to do?

A user may have permission for:

    GET /accounts/42

but not:

    DELETE /accounts/42

The server must enforce authorization independently for each sensitive operation.

The script includes a simple role-based authorization demonstration.

---

## 23. CSRF and Safe Methods

Cross-Site Request Forgery, or CSRF, is especially important for browser applications using automatically attached credentials such as cookies.

One fundamental defense is proper HTTP method semantics.

State-changing actions should not be exposed through GET.

A design such as:

    GET /transfer-money?amount=10000&to=42

is dangerous because browsers, crawlers, prefetchers, and other systems can cause GET requests without intending to perform a business mutation.

State-changing operations should use appropriate methods and additional CSRF protections where cookie-based authentication makes them necessary.

Common defenses include:

- SameSite cookies
- CSRF tokens
- Origin validation
- Appropriate request validation

CORS and CSRF solve different problems.

---

## 24. Idempotency Keys

POST is generally non-idempotent.

This becomes important when network failures occur.

Consider:

    Client -> POST payment
    Server -> processes payment
    Network -> response is lost
    Client -> retries POST

The client cannot necessarily know whether the original request was processed.

A second POST could accidentally create a duplicate operation.

An application can introduce an idempotency key:

    Idempotency-Key: unique-operation-key

The server stores the result associated with that key.

When the same key and equivalent request are received again, the server can return the previously stored result.

The script's `IdempotencyStore` demonstrates this concept.

Production implementations need to address:

- Key uniqueness
- Storage lifetime
- Concurrent requests
- Request fingerprints
- Key reuse with different payloads
- Failure handling
- Expiration
- Distributed storage

An idempotency key is an application-level mechanism. It does not change the fundamental HTTP classification of POST into an intrinsically idempotent method.

---

## 25. Retries

Retries are common in distributed systems because a client may experience:

- Connection timeout
- DNS problems
- Proxy failures
- Load-balancer failures
- Temporary server overload
- Lost responses

A major difficulty is that a timeout does not necessarily mean the server did nothing.

The client may know:

    "I did not receive the response."

It may not know:

    "The server did not process the request."

Idempotent methods are generally easier to retry safely from a semantic perspective, but retry safety still depends on the application and infrastructure.

Retry strategies commonly use:

- Maximum attempts
- Exponential backoff
- Jitter
- Deadlines
- Retryable status codes
- Idempotency mechanisms

The script implements an exponential backoff calculation.

Blindly retrying every HTTP request can create duplicate operations or amplify server overload.

---

## 26. Exponential Backoff

A simple exponential backoff sequence can resemble:

    attempt 0 -> 0.5 seconds
    attempt 1 -> 1.0 seconds
    attempt 2 -> 2.0 seconds
    attempt 3 -> 4.0 seconds
    attempt 4 -> 8.0 seconds

The exact production strategy can include random jitter so that many clients do not retry simultaneously.

A retry policy should also enforce a maximum delay and maximum number of attempts.

---

## 27. Rate Limiting

Rate limiting protects services from excessive traffic.

A common response is:

    429 Too Many Requests

A server can also communicate retry timing through:

    Retry-After

Rate limiting can be based on:

- IP
- User
- API key
- Tenant
- Endpoint
- Method
- Resource

State-changing operations can require additional controls because of their business impact.

The script includes a simple fixed-window rate limiter for educational purposes.

Production distributed rate limiting generally requires coordination between service instances and careful treatment of clock, storage, and concurrency behavior.

---

## 28. Request Size Limits

POST, PUT, and PATCH frequently contain request bodies.

Unrestricted request bodies can create resource-exhaustion risks.

A production API should consider limits for:

- Request body size
- Header size
- JSON nesting depth
- Number of fields
- Multipart uploads
- Parsing time
- Decompression
- Connection duration

The script demonstrates basic `Content-Length` validation.

A declared Content-Length value alone should not be treated as a complete security control. Streaming servers and intermediary infrastructure should enforce actual byte limits as appropriate.

---

## 29. Error Handling

HTTP error handling should be structured and predictable.

The script demonstrates consistent JSON error responses such as:

    {
        "error": {
            "code": "example_error",
            "message": "Human-readable description"
        }
    }

Production APIs should avoid leaking:

- Stack traces
- Passwords
- Authentication tokens
- Internal database details
- Infrastructure secrets

Error messages should be useful to legitimate clients without becoming a source of sensitive internal information.

---

## 30. REST-Style Resource Design

A common resource-oriented API uses nouns in URLs and methods to express operations.

Example:

    GET    /users
    POST   /users
    GET    /users/42
    PUT    /users/42
    PATCH  /users/42
    DELETE /users/42

This is generally clearer than using action-heavy endpoints such as:

    GET  /getUsers
    POST /createUser
    POST /updateUser
    POST /deleteUser

The method already provides semantic information, so resource-oriented design can avoid redundant action naming.

This is a design convention rather than an absolute requirement of HTTP.

---

## 31. HTTP Methods Are Not the Same as Database Commands

It is useful to understand the common conceptual mapping:

| HTTP | Database-style analogy |
|---|---|
| GET | SELECT |
| POST | INSERT/process |
| PUT | Replacement/update |
| PATCH | Partial update |
| DELETE | DELETE |

This mapping is only an analogy.

HTTP operates at the application protocol level.

A GET request might retrieve data from:

- A database
- A cache
- An object store
- Another service
- A computed result

A POST request does not necessarily insert a database row.

Therefore, HTTP method semantics should be designed independently of assumptions about the underlying storage engine.

---

## 32. Caching

GET and HEAD responses are commonly associated with HTTP caching.

Important cache-related headers include:

- `Cache-Control`
- `ETag`
- `Last-Modified`
- `Expires`
- `Vary`

A response such as:

    Cache-Control: max-age=60

communicates freshness information.

Conditional requests can reduce bandwidth and server work.

For example:

    GET
    If-None-Match: "abc123"

can result in:

    304 Not Modified

when the representation has not changed.

The `Vary` header is important when representations depend on request headers.

For example, a response can vary based on:

    Accept-Encoding
    Accept-Language
    Origin

A cache that ignores relevant variation can return an inappropriate representation.

---

## 33. Performance Considerations

Method selection itself is not a complete performance strategy.

HTTP performance can be affected by:

- Network latency
- Connection reuse
- TLS
- HTTP/1.1 persistent connections
- HTTP/2 multiplexing
- HTTP/3
- Compression
- Caching
- Conditional requests
- Payload size
- Server computation
- Database latency
- Connection pooling

HEAD can avoid unnecessary response-body transfer.

GET caching can avoid repeated server computation.

PATCH can reduce request payload size compared with sending a complete representation, although its processing and validation can be more complex.

PUT can be preferable when clients naturally possess complete resource representations and replacement semantics are appropriate.

Performance optimizations should not violate HTTP semantics.

---

## 34. Security Considerations

Important HTTP method security practices include:

### Use HTTPS

Sensitive HTTP traffic should be protected with TLS.

### Authenticate protected operations

The server must establish the identity of the caller where authentication is required.

### Authorize every sensitive operation

Authentication does not automatically grant permission.

### Validate input

Validate:

- Query parameters
- Paths
- Headers
- Content types
- Request bodies

### Restrict request sizes

Prevent excessive memory, CPU, and network consumption.

### Rate-limit abuse-prone operations

Especially sensitive operations such as authentication, payment, resource creation, and expensive queries.

### Do not place secrets in URLs

URLs can appear in:

- Logs
- Browser history
- Monitoring systems
- Analytics
- Proxy records

Sensitive credentials should not be transmitted through query parameters merely for convenience.

### Preserve method semantics

Do not make GET perform destructive operations.

### Configure CORS carefully

Use explicit origin and method allowlists where appropriate.

### Protect cookie-authenticated mutations

Apply appropriate CSRF protections.

---

## 35. HTTP Method Overriding

Some application environments support method overriding when clients cannot directly submit certain methods.

For example:

    X-HTTP-Method-Override: PATCH

This is an application or framework convention.

Method overriding does not make POST semantically equivalent to PATCH.

The application must determine the effective method consistently, and security infrastructure must agree with that interpretation.

Inconsistent method handling between:

- WAF
- Reverse proxy
- Load balancer
- Application framework

can create security vulnerabilities.

---

## 36. Proxies and Intermediaries

Real HTTP systems rarely consist of only one client and one application server.

A production path can resemble:

    Client
      |
      v
    CDN
      |
      v
    WAF
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
    Database

Every layer may affect:

- Method handling
- URL parsing
- Authentication
- Caching
- CORS
- Request limits
- Timeouts
- Forwarded headers
- Method overrides

All layers should agree about the meaning of the request.

A discrepancy between security infrastructure and application logic can cause authorization bypasses or request-smuggling-style problems.

---

## 37. Timeout Semantics

A timeout means the client did not obtain the expected result within its configured deadline.

It does not necessarily prove that the server did not process the request.

For an idempotent method such as PUT, retrying the same intended replacement is often semantically safer than retrying an arbitrary POST.

For POST, an idempotency key can make retries safer when duplicate processing would be harmful.

Retry policies should account for the uncertainty surrounding a timed-out request.

---

## 38. Observability

Production HTTP services should expose useful observability information.

Useful metrics include:

- HTTP method
- Route template
- Status code
- Latency
- Response size
- Error type
- Request ID
- Dependency latency
- Tenant or principal identifier where appropriate

Route templates are often preferable to literal paths.

For example, aggregate:

    GET /users/{id}

rather than treating:

    GET /users/1
    GET /users/2
    GET /users/3

as unrelated metric dimensions.

Sensitive values should not be logged.

Never casually log:

- Passwords
- Authentication tokens
- Session secrets
- Payment-card information
- Sensitive personal information

The script includes a simple metrics aggregation demonstration.

---

## 39. HTTP Extension Methods

The seven methods emphasized in the script are not the complete universe of HTTP methods.

HTTP also defines or accommodates methods such as:

- CONNECT
- TRACE

HTTP has an extensible method namespace, so an application should not assume that only the most commonly used REST methods can exist.

`CONNECT` is commonly associated with proxy tunneling.

`TRACE` has diagnostic semantics and is frequently disabled when not required because of security considerations.

An application may still intentionally support only a restricted method set for a particular API.

---

## 40. Method Allowlisting

An application can explicitly define which methods are supported.

For example:

    GET
    POST
    HEAD
    OPTIONS

for a collection endpoint.

And:

    GET
    PUT
    PATCH
    DELETE
    HEAD
    OPTIONS

for an individual resource endpoint.

A method allowlist reduces accidental exposure of unsupported operations and makes API behavior more predictable.

The script's router and `method_allowlist()` function demonstrate this principle.

---

## 41. HTTP Router Design

A router typically combines:

    HTTP method + path

to determine which handler should execute.

For example:

    GET /users
    POST /users
    GET /users/42
    PUT /users/42
    PATCH /users/42
    DELETE /users/42

The same path can therefore have multiple handlers depending on the method.

The educational `Router` class implements a small version of this concept.

It also demonstrates the distinction between:

- Route not found
- Method not allowed

---

## 42. The Demo API

The `DemoAPI` class combines the concepts into a complete in-memory API.

It supports:

    GET    /resources
    POST   /resources
    GET    /resources/{id}
    PUT    /resources/{id}
    PATCH  /resources/{id}
    DELETE /resources/{id}
    HEAD   /resources/{id}
    OPTIONS /resources/{id}

The API demonstrates:

- Routing
- JSON request parsing
- Validation
- Resource creation
- Resource replacement
- Partial updates
- Deletion
- HEAD metadata
- OPTIONS capability discovery
- Status codes
- Location headers
- ETags

Because the storage is an in-memory Python dictionary, the implementation is deliberately small and transparent.

---

## 43. Input Validation

The script validates example user payloads.

A valid payload resembles:

    {
        "name": "Alice",
        "email": "alice@example.com"
    }

Validation checks include:

- Object type
- Non-empty name
- Basic email structure

Real validation requirements depend on the API.

Production validation may need to address:

- Length limits
- Unicode
- Allowed characters
- Enumerations
- Numeric ranges
- Date formats
- Nested objects
- Arrays
- Cross-field constraints
- Business rules

Validation should occur before unsafe or expensive business processing.

---

## 44. Common Mistakes

### Mistake 1: Using GET for mutations

Bad:

    GET /delete-user/42

Use the method that communicates the intended mutation.

### Mistake 2: Assuming POST is idempotent

Repeated POST requests can cause repeated operations.

### Mistake 3: Assuming PATCH is always idempotent

PATCH idempotency depends on the patch semantics.

### Mistake 4: Treating DELETE idempotency as identical responses

Idempotency concerns intended final state, not necessarily identical status codes.

### Mistake 5: Confusing PUT and PATCH

PUT is associated with replacement.

PATCH is associated with partial modification.

### Mistake 6: Treating CORS as authentication

CORS is primarily a browser cross-origin access mechanism.

### Mistake 7: Treating authentication as authorization

Knowing who the caller is does not establish what they may do.

### Mistake 8: Retrying every request blindly

Retries can duplicate non-idempotent operations.

### Mistake 9: Logging secrets in URLs

Query strings can be widely logged.

### Mistake 10: Ignoring intermediary behavior

CDNs, WAFs, proxies, and load balancers can change the effective behavior of HTTP systems.

### Mistake 11: Ignoring request-size limits

Large bodies can create resource-exhaustion risks.

### Mistake 12: Assuming status code alone describes the method semantics

The method and response status answer different questions.

---

## 45. Edge Cases

Important edge cases include:

### Repeated DELETE

The first DELETE can return `204`.

A later DELETE can return `404`.

The operation can still be idempotent.

### PATCH with a counter

A patch that increments a counter is generally not idempotent.

### PUT of a missing resource

Depending on the API contract, PUT can create a resource at a known URI and return `201`.

### Invalid JSON

A body that cannot be parsed as JSON can result in a client-error response such as `400`.

### Valid JSON with invalid business fields

A syntactically valid payload can still fail semantic validation.

### Unsupported method

A known resource with an unsupported method should generally produce `405 Method Not Allowed` with an appropriate `Allow` header.

### Unknown route

A route that does not exist can result in `404 Not Found`.

### Conditional write against stale state

An outdated `If-Match` condition can result in `412 Precondition Failed`.

---

## 46. Limitations of the Educational Implementation

The Python program intentionally implements a simplified HTTP model.

It does not attempt to replace a production HTTP server.

The in-memory API does not implement:

- Actual TCP networking
- TLS
- HTTP/1.1 parsing
- HTTP/2 framing
- HTTP/3
- Distributed storage
- Real authentication infrastructure
- Real browser CORS enforcement
- Full HTTP cache semantics
- Full RFC-compliant content negotiation
- Production-grade concurrency control
- Distributed idempotency storage
- Production-grade rate limiting

The purpose is to make the semantic relationships between HTTP methods and application behavior directly executable.

---

## 47. Testing

The script includes a `unittest` test suite.

The tests cover:

- Safe method classification
- PUT idempotency
- Non-idempotent PATCH behavior
- Idempotent PATCH behavior
- POST resource creation
- GET of missing resources
- PATCH preservation of other fields
- HEAD response-body behavior
- OPTIONS method discovery
- 405 responses
- Idempotency-key replay
- Idempotency-key conflicts
- Conditional GET
- Conditional PUT

The tests are executable through the script's `main()` function.

This makes the file both an educational reference and a small executable laboratory for HTTP semantics.

---

## 48. Practical Method Selection

A conceptual decision process can be expressed as:

| Desired operation | Typical method |
|---|---|
| Retrieve a resource | GET |
| Inspect representation metadata | HEAD |
| Discover supported methods/options | OPTIONS |
| Create through server-side processing | POST |
| Create or replace at known URI | PUT |
| Replace a representation | PUT |
| Partially modify a resource | PATCH |
| Remove a resource | DELETE |

The appropriate method ultimately depends on the semantics of the operation, not merely the database command being performed underneath it.

---

## 49. Implementation Considerations

A production HTTP API should define clearly:

- Supported methods
- Resource URI structure
- Request schemas
- Response schemas
- Status-code behavior
- Authentication
- Authorization
- Validation
- Error format
- Caching policy
- Conditional requests
- Retry behavior
- Idempotency policy
- Rate limits
- Request-size limits
- Timeout policy
- CORS policy
- Logging
- Metrics
- Tracing
- Concurrency controls

The method semantics should remain consistent across the entire infrastructure stack.

---

## 50. Method Semantics and Distributed Systems

HTTP method semantics become particularly important in distributed systems.

Networks can fail independently of application execution.

A client may send a request successfully, while the response is lost.

This creates uncertainty:

    Did the server execute the request?

For idempotent operations, repeating the same intended operation is often easier to reason about.

For non-idempotent operations, application-level mechanisms such as idempotency keys may be necessary.

This is one reason method semantics matter beyond simple API naming conventions.

---

## 51. Production Design Principles

A reliable HTTP API should maintain the following principles:

1. Use GET for retrieval.
2. Keep safe methods semantically read-only.
3. Use POST when server-side processing or creation semantics require it.
4. Use PUT for complete replacement at a known URI.
5. Use PATCH for partial modifications.
6. Use DELETE for resource removal.
7. Use HEAD when metadata is needed without the representation body.
8. Use OPTIONS for capability discovery and applicable CORS preflight behavior.
9. Treat idempotency as a semantic property.
10. Do not assume every PATCH operation is idempotent.
11. Use conditional requests when stale writes are dangerous.
12. Use idempotency keys for retry-sensitive non-idempotent operations when appropriate.
13. Validate all externally supplied input.
14. Authenticate and authorize independently.
15. Do not use CORS as an authorization mechanism.
16. Protect cookie-authenticated mutations against CSRF where applicable.
17. Apply rate limits and request-size limits.
18. Avoid exposing sensitive data through URLs or logs.
19. Make retry behavior explicit.
20. Ensure proxies, security layers, and applications interpret methods consistently.

---

## 52. Executable Topics Covered by the Python Script

The script provides working demonstrations for:

- HTTP request representation
- HTTP response representation
- HTTP method classification
- Safe methods
- Idempotency
- GET
- POST
- PUT
- PATCH
- DELETE
- HEAD
- OPTIONS
- URL parsing
- Query-string construction
- Status-code classification
- HTTP routing
- 405 Method Not Allowed
- `Allow` headers
- Content negotiation basics
- `Content-Type`
- `Accept`
- ETags
- Conditional GET
- `If-None-Match`
- `If-Match`
- Optimistic concurrency
- `412 Precondition Failed`
- Idempotency keys
- Request fingerprints
- Retry backoff
- Rate limiting
- Request-size validation
- CORS preflight simulation
- Authentication and authorization concepts
- CSRF-related method semantics
- Error-response construction
- Header normalization
- REST-style resource design
- Caching concepts
- Performance calculations
- Observability
- Unit testing
- Edge cases
- Production-oriented security considerations

The examples progress from simple method classification to a complete in-memory API simulator and associated correctness tests.
