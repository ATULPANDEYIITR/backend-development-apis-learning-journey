# HTTP Status Codes: 1xx, 2xx, 3xx, 4xx, 5xx, Common Errors, Postman and cURL

## Introduction

HTTP status codes are three-digit values returned by an HTTP server to describe the result of processing a request.

They provide a standardized communication mechanism between clients and servers. A client can use the status code to determine whether a request succeeded, whether a resource was redirected, whether the request was invalid, or whether the server or one of its dependencies encountered a problem.

The first digit identifies the broad category:

| Class | Meaning | General Interpretation |
|---|---|---|
| 1xx | Informational | Request received and processing continues |
| 2xx | Successful | Request was successfully processed |
| 3xx | Redirection | Further action or another resource is involved |
| 4xx | Client Error | The request cannot be fulfilled because of a client-side condition |
| 5xx | Server Error | The server failed to successfully fulfill an otherwise processable request |

A status code is only one part of an HTTP response. A complete response may contain:

- Status code
- Status text
- Response headers
- Response body
- Cookies
- Caching metadata
- Redirection information

The Python script demonstrates these concepts with executable examples, a local HTTP server, HTTP client requests, status-code assertions, error models, cURL commands, and Postman-oriented testing concepts.

---

## 1. Basic HTTP Request and Response Structure

A typical HTTP request contains:

- HTTP method
- Request target or URL
- Request headers
- Optional request body

For example, conceptually:

    GET /users/42
    Host: api.example.com
    Accept: application/json

The server processes the request and returns a response such as:

    HTTP/1.1 200 OK
    Content-Type: application/json

    {"id": 42, "name": "Asha"}

The status code describes the result of processing the request.

The response body contains application data, while headers provide metadata and instructions concerning the response.

A useful conceptual model is:

    HTTP request
        |
        v
    Server processing
        |
        v
    HTTP status + headers + optional body

---

# 2. Understanding the Five HTTP Status Classes

## 2.1 1xx: Informational

The 1xx class represents informational responses.

They generally indicate that the server has received part of the request or is communicating an intermediate state before the final response.

Important examples include:

| Code | Name | Purpose |
|---|---|---|
| 100 | Continue | Client may continue sending the request |
| 101 | Switching Protocols | Protocol transition was accepted |
| 102 | Processing | Processing is continuing |
| 103 | Early Hints | Preliminary response information |

1xx responses are not normally the final application result.

### 100 Continue

`100 Continue` is associated with request processing where the client may first ask whether it should send the request body.

This can be useful for large request bodies.

### 101 Switching Protocols

`101 Switching Protocols` indicates that the server agrees to switch protocols when such a transition has been requested and supported.

### 103 Early Hints

`103 Early Hints` allows preliminary headers to be sent before the final response.

---

# 3. 2xx: Successful Responses

The 2xx class communicates successful processing.

Common values are:

| Code | Name | Typical Use |
|---|---|---|
| 200 | OK | Successful operation |
| 201 | Created | Resource successfully created |
| 202 | Accepted | Accepted for asynchronous processing |
| 204 | No Content | Successful operation without response body |
| 206 | Partial Content | Successful range response |

---

## 3.1 200 OK

`200 OK` is the general-purpose successful response.

Typical example:

    GET /users/42

If the resource exists and is returned successfully:

    200 OK

A response body might contain:

    {
      "id": 42,
      "name": "Asha"
    }

`200` can also be used for successful POST, PUT, PATCH, or DELETE operations when the API semantics call for a response representation.

---

## 3.2 201 Created

`201 Created` communicates successful resource creation.

For example:

    POST /users

A successful response may be:

    201 Created
    Location: /users/101

The `Location` header identifies the newly created resource.

A response body may also contain the created representation.

The Python script demonstrates this pattern with a user-creation endpoint.

---

## 3.3 202 Accepted

`202 Accepted` means that the server accepted the request for processing but the requested operation has not necessarily completed.

This is especially useful for asynchronous operations.

Example:

    POST /reports

Response:

    202 Accepted

The response can contain:

    {
      "job_id": "job-123",
      "status": "queued",
      "status_url": "/jobs/job-123"
    }

This is preferable when the server cannot honestly claim that the requested operation is already complete.

---

## 3.4 204 No Content

`204 No Content` indicates successful processing without a response body.

A common example is:

    DELETE /users/42

Response:

    204 No Content

Another example is a successful update where the API deliberately returns no representation.

The important distinction is:

- `200` can contain a response representation.
- `204` communicates successful completion with no response content.

A `204` response should not be treated as a normal response containing JSON.

---

## 3.5 206 Partial Content

`206 Partial Content` is associated with range requests.

It is important for use cases such as:

- Resumable downloads
- Large files
- Media delivery
- Partial retrieval

The response normally works with range-related headers such as `Content-Range`.

---

# 4. 3xx: Redirection Responses

The 3xx class indicates that the client may need to take another action.

Important status codes include:

| Code | Name | Primary Meaning |
|---|---|---|
| 301 | Moved Permanently | Permanent URI change |
| 302 | Found | Temporary/legacy redirection |
| 303 | See Other | Retrieve another URI |
| 304 | Not Modified | Cached representation remains valid |
| 307 | Temporary Redirect | Temporary redirect preserving method |
| 308 | Permanent Redirect | Permanent redirect preserving method |

---

## 4.1 301 Moved Permanently

`301` indicates a permanent change of URI.

Example:

    /old-products/123
            |
            v
    /products/123

A server can return:

    301 Moved Permanently
    Location: /products/123

301 is widely used for permanent website redirects.

---

## 4.2 302 Found

`302` represents a temporary redirect but has historical interoperability behavior.

Modern API design should distinguish carefully between `302`, `303`, and `307`.

---

## 4.3 303 See Other

`303 See Other` is useful when an operation has completed and the client should retrieve another resource, commonly with GET.

It can be useful after a POST where the resulting resource has a separate URI.

---

## 4.4 304 Not Modified

`304 Not Modified` is primarily associated with conditional requests and caching.

Suppose a client previously received:

    ETag: "resource-v7"

The client can later send:

    If-None-Match: "resource-v7"

If the representation has not changed, the server can return:

    304 Not Modified

The client can then use its cached representation.

A `304` response does not contain the full representation body.

The Python script demonstrates a simplified ETag-based conditional request.

---

## 4.5 307 Temporary Redirect

`307` is a temporary redirect where the original HTTP method and request body are preserved.

This distinction is important for methods such as POST, PUT, and PATCH.

---

## 4.6 308 Permanent Redirect

`308` is the permanent counterpart to `307`.

It preserves the original HTTP method and request body.

The important conceptual distinction is:

| Code | Permanence | Method Preservation |
|---|---|---|
| 301 | Permanent | Historical client behavior |
| 302 | Temporary | Historical client behavior |
| 307 | Temporary | Explicitly preserved |
| 308 | Permanent | Explicitly preserved |

---

# 5. 4xx: Client Errors

The 4xx class indicates that the server cannot successfully process the request because of a condition associated with the request.

Common codes include:

| Code | Name | Typical Meaning |
|---|---|---|
| 400 | Bad Request | Malformed or invalid request |
| 401 | Unauthorized | Authentication missing or invalid |
| 403 | Forbidden | Request understood but not permitted |
| 404 | Not Found | Resource unavailable |
| 405 | Method Not Allowed | Method unsupported |
| 406 | Not Acceptable | Representation cannot satisfy Accept preferences |
| 408 | Request Timeout | Client request did not arrive in time |
| 409 | Conflict | Conflict with current resource state |
| 410 | Gone | Resource intentionally removed |
| 412 | Precondition Failed | Client precondition failed |
| 413 | Content Too Large | Request content exceeds limit |
| 415 | Unsupported Media Type | Request body media type unsupported |
| 422 | Unprocessable Content | Content is syntactically valid but semantically invalid |
| 429 | Too Many Requests | Rate limit exceeded |

---

# 6. 400 Bad Request

`400 Bad Request` indicates that the server cannot process the request as a valid request.

Examples include:

- Malformed JSON
- Invalid request syntax
- Malformed query parameters
- Invalid request framing
- Invalid parameter structure

Example:

    POST /users
    Content-Type: application/json

    {"name": "Asha"

The JSON is incomplete.

A `400` response is appropriate because the request cannot be correctly interpreted.

---

# 7. 401 Unauthorized

Despite its name, `401 Unauthorized` generally relates to authentication.

Common cases include:

- Missing authentication credentials
- Expired access token
- Invalid access token
- Invalid authentication credentials

Conceptually:

    401 = authentication has not been successfully established

Example:

    GET /admin/users

without a valid authentication credential may result in:

    401 Unauthorized

---

# 8. 403 Forbidden

`403 Forbidden` indicates that the server understood the request but refuses to authorize it.

A common scenario is:

    User is authenticated
             |
             v
    User requests administrator operation
             |
             v
    User lacks administrator permission
             |
             v
            403

The key distinction is:

    401 -> authentication problem

    403 -> authorization problem

Security-sensitive systems may sometimes return `404` instead of `403` when revealing the existence of a protected resource would itself expose sensitive information.

---

# 9. 404 Not Found

`404 Not Found` means that the requested resource is not available at the requested target.

Example:

    GET /users/999999

If that user does not exist:

    404 Not Found

404 can also be used intentionally when an API should not disclose whether a protected resource exists.

---

# 10. 405 Method Not Allowed

`405 Method Not Allowed` means that the target resource exists but does not support the requested HTTP method.

Example:

    PATCH /users/42

If the resource supports:

    GET
    PUT
    DELETE

but not PATCH, the response can be:

    405 Method Not Allowed

The response should generally communicate supported methods using the `Allow` header:

    Allow: GET, PUT, DELETE

The Python server demonstrates this behavior.

---

# 11. 406 Not Acceptable

`406 Not Acceptable` is related to response content negotiation.

Suppose a client sends:

    Accept: application/xml

but the server only supports:

    application/json
    text/plain

The server may be unable to produce an acceptable representation.

This is different from `415`.

### 406 vs 415

| Code | Concern |
|---|---|
| 406 | Response representation requested by client cannot be provided |
| 415 | Request body media type is unsupported |

For example:

    Accept: application/xml

relates to response representation preferences.

While:

    Content-Type: application/xml

describes the format of the request body.

---

# 12. 408 Request Timeout

`408 Request Timeout` is related to the server not receiving a complete request within the time it was prepared to wait.

It is different from a gateway waiting too long for an upstream server.

---

# 13. 409 Conflict

`409 Conflict` represents a conflict with the current state of a resource.

Examples:

- Duplicate unique username
- Conflicting resource version
- Invalid state transition
- Concurrent update conflict
- Attempt to create a resource that violates a current state constraint

For example:

    POST /users

with:

    {"username": "existing-user"}

may produce:

    409 Conflict

if the username must be unique and already exists.

---

# 14. 410 Gone

`410 Gone` indicates that a resource was intentionally removed and is expected to remain unavailable.

The distinction is:

    404 -> resource is not available

    410 -> resource was deliberately removed and is expected to remain gone

404 is more common and is often sufficient.

---

# 15. 412 Precondition Failed

`412 Precondition Failed` is useful with conditional requests.

For example:

    If-Match: "v7"

If the current resource has a different ETag:

    "v8"

the condition is false.

The server can return:

    412 Precondition Failed

This supports optimistic concurrency control.

---

# 16. 413 Content Too Large

`413 Content Too Large` indicates that the request content exceeds a server-defined limit.

Examples:

- Oversized JSON payload
- Excessively large file upload
- Request exceeding gateway limits

Servers should often enforce request-size limits before expensive parsing or processing.

This reduces resource consumption and helps mitigate certain denial-of-service scenarios.

---

# 17. 415 Unsupported Media Type

`415 Unsupported Media Type` indicates that the server does not support the media type of the request content.

Example:

    Content-Type: application/xml

when the endpoint requires:

    application/json

The Python script checks the request `Content-Type` before attempting to process the JSON body.

---

# 18. 422 Unprocessable Content

`422 Unprocessable Content` is useful when the request is syntactically valid but its content violates semantic or application-level rules.

For example:

    {
      "name": "Ravi",
      "email": "invalid-email",
      "age": 16
    }

The JSON itself is valid.

The application rules are not satisfied.

Possible response:

    422 Unprocessable Content

A structured error might contain:

    {
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "User data is invalid.",
        "details": [
          "email must contain @",
          "age must be at least 18"
        ]
      }
    }

The exact use of `400` versus `422` varies between API conventions. Consistency within a particular API is essential.

---

# 19. 429 Too Many Requests

`429 Too Many Requests` communicates that a client has exceeded a rate limit.

A response may contain:

    Retry-After: 60

This tells the client that retrying after an appropriate interval may be reasonable.

Rate limiting protects:

- APIs
- Databases
- Authentication systems
- Expensive computational resources
- Third-party dependencies

Possible rate-limit headers include:

    X-RateLimit-Limit
    X-RateLimit-Remaining
    X-RateLimit-Reset

Header naming conventions vary between APIs.

---

# 20. 5xx: Server Errors

The 5xx class represents server-side failures.

Common codes include:

| Code | Name | Typical Meaning |
|---|---|---|
| 500 | Internal Server Error | Unexpected server-side failure |
| 501 | Not Implemented | Functionality is not implemented |
| 502 | Bad Gateway | Invalid upstream response |
| 503 | Service Unavailable | Service temporarily unavailable |
| 504 | Gateway Timeout | Upstream response timed out |
| 505 | HTTP Version Not Supported | HTTP version is unsupported |

---

# 21. 500 Internal Server Error

`500 Internal Server Error` is the general-purpose server-side failure status.

Possible causes include:

- Unhandled application exception
- Unexpected database failure
- Programming defect
- Internal dependency failure not more precisely represented

Production APIs should not expose internal stack traces.

Avoid returning information such as:

- Database credentials
- SQL statements
- Internal filesystem paths
- Stack traces
- Secret keys
- Infrastructure credentials

Instead, return a safe message and log the detailed diagnostic information internally.

---

# 22. 501 Not Implemented

`501 Not Implemented` indicates that the server does not support the functionality required to fulfill the request.

It should not simply be used as a generic replacement for every unsupported endpoint.

---

# 23. 502 Bad Gateway

`502 Bad Gateway` commonly applies to a gateway or proxy that received an invalid response from an upstream server.

A simplified architecture is:

    Client
      |
      v
    Gateway
      |
      v
    Application

If the application returns an invalid upstream response:

    Gateway -> 502

This status is especially useful in systems containing:

- Reverse proxies
- API gateways
- Load balancers
- Service meshes

---

# 24. 503 Service Unavailable

`503 Service Unavailable` communicates that a service is temporarily unable to handle requests.

Possible causes include:

- Maintenance
- Temporary overload
- Dependency outage
- Circuit breaker activation
- Deliberate load shedding

A service that is intentionally refusing additional traffic during overload may be healthier than allowing requests to consume resources until the entire system fails.

---

# 25. 504 Gateway Timeout

`504 Gateway Timeout` occurs when a gateway or proxy does not receive a timely response from an upstream server.

A useful distinction is:

    502 -> upstream response was invalid

    504 -> upstream response did not arrive in time

    503 -> service is temporarily unable to serve requests

---

# 26. 502 vs 503 vs 504

| Status | Meaning |
|---|---|
| 502 | Gateway received an invalid upstream response |
| 503 | Service is temporarily unavailable |
| 504 | Gateway timed out waiting for upstream |

The correct choice depends on where the failure occurred and what the server knows about the condition.

---

# 27. 401 vs 403

This distinction is one of the most important HTTP concepts.

| Scenario | Typical Status |
|---|---:|
| No authentication credentials | 401 |
| Invalid credentials | 401 |
| Expired token | 401 |
| Valid user without required permission | 403 |
| Authenticated user attempts administrator-only action | 403 |

A concise mental model is:

    401 -> "Authentication has not succeeded."

    403 -> "Authentication succeeded, but access is forbidden."

---

# 28. 400 vs 422

A practical distinction is:

### 400

Use when the request itself is malformed or cannot be correctly interpreted.

Examples:

- Invalid JSON syntax
- Invalid request structure
- Malformed request parameters

### 422

Use when the request is structurally valid but fails application-level validation.

Examples:

- Invalid email
- Age outside permitted range
- Invalid business-rule combination

Different APIs may use `400` for both categories. The critical requirement is predictable behavior.

---

# 29. 404 vs 410

| Code | Interpretation |
|---|---|
| 404 | Resource is unavailable at the requested target |
| 410 | Resource was deliberately removed and is expected to remain unavailable |

404 is generally the safer general-purpose choice.

410 provides stronger information about deliberate permanent removal.

---

# 30. 409 vs 412

These codes can both appear in concurrency scenarios.

### 409 Conflict

Represents a broader conflict with the current state of the resource.

### 412 Precondition Failed

Indicates that a specific client-supplied precondition was false.

For example:

    If-Match: "v7"

when the current resource is:

    "v8"

is a natural use case for `412`.

---

# 31. HTTP Methods and Status Codes

HTTP methods and status codes work together.

## GET

Purpose:

- Retrieve a representation

Common successful responses:

- 200
- 206
- 304

Common errors:

- 400
- 401
- 403
- 404
- 405
- 429
- 500

---

## POST

Purpose:

- Create a resource
- Trigger processing
- Submit data

Common successful responses:

- 200
- 201
- 202
- 204

Possible errors:

- 400
- 401
- 403
- 409
- 415
- 422
- 429
- 500

---

## PUT

Purpose:

- Create or replace a representation at a known target URI

Common successful responses:

- 200
- 201
- 204

---

## PATCH

Purpose:

- Apply partial modifications

Common successful responses:

- 200
- 204

---

## DELETE

Purpose:

- Remove a resource

Common successful responses:

- 200
- 202
- 204

A particular API may choose 404 or 204 for repeated deletion of an already absent resource. The API should document and apply its chosen convention consistently.

---

# 32. Idempotency

Idempotency means that repeating an operation has the same intended effect on server state as performing it once.

Commonly idempotent methods include:

- GET
- HEAD
- PUT
- DELETE

POST is generally not idempotent.

PATCH depends on the semantics of the specific operation.

Idempotency does not mean that repeated requests must produce identical responses.

For example:

    DELETE /users/42

could produce:

    First request  -> 204
    Second request -> 404

The final server state is still consistent with the resource being deleted.

---

# 33. Application-Level Idempotency Keys

Some operations, especially payments and order creation, are dangerous to repeat blindly.

Consider:

    POST /payments

If the client sends the request but loses the network connection before receiving the response, the client may not know whether the payment was created.

Retrying could create a duplicate payment.

An API can support an idempotency key such as:

    Idempotency-Key: abc-123

The server can associate the key with the original operation and safely handle a retry.

The status code remains part of the HTTP contract, while the idempotency key provides application-level protection against duplicate processing.

---

# 34. Caching and 304

Caching can reduce:

- Network traffic
- Server load
- Response latency

An API can use validators such as ETags.

Example:

    ETag: "resource-v7"

The client later sends:

    If-None-Match: "resource-v7"

If the resource is unchanged:

    304 Not Modified

The client reuses its cached representation.

This is different from returning:

    200 OK

with an empty body.

`304` specifically means that the cached representation remains valid.

---

# 35. 201 and the Location Header

A resource-creation API can return:

    201 Created
    Location: /users/101

The `Location` header communicates where the created resource can be accessed.

A response body can also provide the representation:

    {
      "id": 101,
      "name": "Neha"
    }

This creates a clear relationship between the creation operation and the resulting resource.

---

# 36. Structured API Errors

A robust API should distinguish the HTTP status from application-specific error information.

Example:

    HTTP 422

    {
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "One or more fields are invalid.",
        "details": [
          {
            "field": "email",
            "reason": "invalid format"
          }
        ],
        "request_id": "req-8f21"
      }
    }

The HTTP status tells the client the broad protocol-level result.

The application error code gives the client a stable domain-specific identifier.

The human-readable message is intended for diagnostics or display where appropriate.

The request ID allows support and engineering teams to correlate the client response with server-side logs.

---

# 37. Error Messages and Security

Production error messages should be informative without exposing sensitive implementation details.

Do not expose:

- Passwords
- API keys
- Access tokens
- Database credentials
- SQL statements
- Internal stack traces
- Internal filesystem paths
- Private infrastructure information

Instead:

Client response:

    {
      "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected server error occurred.",
        "request_id": "req-123"
      }
    }

Server logs can contain controlled diagnostic information associated with the request ID.

---

# 38. Retryable Errors

Some failures may be transient.

Typical retry candidates include:

- 408
- 429
- 500
- 502
- 503
- 504

But status code alone is not enough to determine whether retrying is safe.

Consider:

1. Is the operation idempotent?
2. Could the retry duplicate a side effect?
3. Is `Retry-After` present?
4. Is the failure temporary?
5. Is the dependency overloaded?
6. Should exponential backoff be used?
7. Should jitter be added?

Blind retries can make an outage worse.

---

# 39. Exponential Backoff

A common retry pattern is exponential backoff:

    delay = base × 2^attempt

For example, with a base delay of 0.5 seconds:

| Attempt | Approximate Delay |
|---:|---:|
| 0 | 0.5 s |
| 1 | 1.0 s |
| 2 | 2.0 s |
| 3 | 4.0 s |
| 4 | 8.0 s |
| 5 | 16.0 s |

Production implementations commonly add jitter.

Jitter prevents thousands of clients from retrying at exactly the same time after a common failure.

A maximum delay should also be imposed.

---

# 40. Rate Limiting

Rate limiting controls how much traffic a client can generate.

For example:

    Limit: 100 requests
    Remaining: 0
    Reset: future timestamp

When the limit is exceeded:

    429 Too Many Requests

may be returned.

A `Retry-After` header can communicate when a retry is appropriate.

Rate limiting can protect:

- API servers
- Authentication endpoints
- Databases
- Expensive computational services
- External dependencies

---

# 41. Content Negotiation

The `Accept` header tells the server what response representations the client can accept.

Example:

    Accept: application/json

If the server supports JSON, it may return JSON.

A client might send:

    Accept: text/html, application/json

A server can select a supported representation.

If none of the requested representations can be supplied, `406 Not Acceptable` can be appropriate.

---

# 42. Content-Type

`Content-Type` describes the media type of the request body.

Example:

    Content-Type: application/json

For JSON:

    {
      "name": "Asha"
    }

If an endpoint only accepts JSON and receives XML:

    Content-Type: application/xml

the server can return:

    415 Unsupported Media Type

This should be distinguished from validation errors.

---

# 43. 408 vs 504

These statuses describe different timeout locations.

### 408 Request Timeout

The server did not receive a complete request from the client within an acceptable period.

### 504 Gateway Timeout

A gateway or proxy did not receive a timely response from an upstream server.

Conceptually:

    Client -> Server

    client-side request timeout at server
    -> 408

versus:

    Client -> Gateway -> Application

    gateway waits too long for application
    -> 504

---

# 44. Proxy and Gateway Architecture

Modern applications frequently have multiple HTTP layers:

    Client
       |
       v
    CDN
       |
       v
    Load Balancer
       |
       v
    API Gateway
       |
       v
    Application
       |
       v
    Database / External Services

This architecture explains why status codes such as `502`, `503`, and `504` are important.

A gateway can observe failures that the application itself does not directly control.

---

# 45. Circuit Breakers and 503

A circuit breaker can stop an application from repeatedly calling a failing dependency.

A simplified state model is:

    CLOSED
       |
       | repeated failures
       v
    OPEN
       |
       | recovery period
       v
    HALF_OPEN
       |
       | successful test
       v
    CLOSED

If a service intentionally rejects traffic because a dependency is unavailable, `503 Service Unavailable` can be appropriate.

This is often preferable to allowing all requests to wait until they time out.

---

# 46. Status Codes and Observability

Status codes are important monitoring signals.

Useful metrics include:

- Request count
- Status-code distribution
- 2xx rate
- 4xx rate
- 5xx rate
- Individual status-code counts
- Latency
- Response size
- Dependency latency
- Retry count
- Rate-limit events

Different patterns can indicate different problems.

### Rising 404 rate

Possible causes:

- Broken client links
- Incorrect API paths
- Client deployment error
- Deleted resources

### Rising 429 rate

Possible causes:

- Traffic increase
- Aggressive clients
- Incorrect rate-limit configuration

### Rising 500 rate

Possible causes:

- Application regression
- Unhandled exception
- Database problem
- Programming defect

### Rising 502/504 rate

Possible causes:

- Dependency failures
- Network problems
- Proxy configuration
- Slow upstream services

---

# 47. Status Code as an API Contract

An API should treat status codes as part of its contract.

For example:

    GET /users/{id}

may define:

    200 -> user found
    404 -> user not found
    401 -> authentication required
    403 -> access denied
    429 -> rate limit exceeded
    500 -> unexpected server failure

Clients can then implement deterministic behavior.

Automated tests should verify these contracts.

The Python script demonstrates this with status assertions and endpoint contracts.

---

# 48. Status-Code Anti-Patterns

## Returning 200 for Every Result

Bad design:

    HTTP 200

with:

    {
      "success": false,
      "error": "User not found"
    }

This forces clients to inspect the body to determine whether the HTTP operation succeeded.

A more conventional API response is:

    404 Not Found

with an appropriate error body.

---

## Returning 500 for Invalid Input

If a client sends an invalid email address, the server did not necessarily fail.

The client supplied invalid data.

A 4xx response is normally more appropriate.

---

## Using 401 for Authorization Failures

If authentication succeeded but the user lacks permission, `403` generally communicates the situation more accurately.

---

## Using 404 for Everything

Returning `404` for every failure destroys useful semantic distinctions.

A client cannot tell whether:

- Authentication failed
- Permission was denied
- Validation failed
- The resource is missing
- The server failed

Precise status codes make client behavior easier.

---

## Exposing Internal Errors

Returning a Python traceback, SQL query, or database error to a client is dangerous.

Return a safe error representation and log detailed diagnostics internally.

---

# 49. HTTP Status Codes Are Not Business State

HTTP status and application state should not be confused.

Suppose a report is generated asynchronously.

The HTTP operation can return:

    202 Accepted

while the application state is:

    processing

The response may contain:

    {
      "job_id": "job-123",
      "state": "processing"
    }

The status code describes what happened to the HTTP request.

The body describes the application's domain state.

---

# 50. Choosing an Appropriate Status Code

A practical decision process is:

### Step 1: Did the request succeed?

If yes, consider:

- 200
- 201
- 202
- 204

### Step 2: Was the client redirected?

Consider:

- 301
- 302
- 303
- 307
- 308

### Step 3: Is the request invalid?

Consider:

- 400
- 415
- 422

### Step 4: Is authentication missing or invalid?

Use:

- 401

### Step 5: Is access forbidden?

Use:

- 403

### Step 6: Does the resource exist?

If not:

- 404
- potentially 410

### Step 7: Is there a resource-state conflict?

Consider:

- 409
- 412

### Step 8: Has the client exceeded a limit?

Use:

- 429

### Step 9: Did the server fail?

Consider:

- 500
- 502
- 503
- 504

---

# 51. Practical Status-Code Reference

| Scenario | Recommended Code |
|---|---:|
| Successful GET | 200 |
| Successful generic operation | 200 |
| Resource created | 201 |
| Accepted asynchronous job | 202 |
| Successful operation with no body | 204 |
| Permanent redirect | 301 |
| Temporary redirect | 302 |
| See another resource | 303 |
| Cached representation unchanged | 304 |
| Temporary redirect preserving method | 307 |
| Permanent redirect preserving method | 308 |
| Malformed request | 400 |
| Missing/invalid authentication | 401 |
| Insufficient permission | 403 |
| Resource unavailable | 404 |
| Unsupported method | 405 |
| Unacceptable representation | 406 |
| Request timeout | 408 |
| State conflict | 409 |
| Resource permanently removed | 410 |
| Failed precondition | 412 |
| Request too large | 413 |
| Unsupported request media type | 415 |
| Semantic validation failure | 422 |
| Rate limit exceeded | 429 |
| Unexpected server failure | 500 |
| Functionality not implemented | 501 |
| Invalid upstream response | 502 |
| Service temporarily unavailable | 503 |
| Upstream timeout | 504 |

---

# 52. Testing with cURL

cURL is useful for directly inspecting HTTP behavior.

## Include Response Headers

    curl -i https://example.com/api/users/42

The `-i` option includes response headers.

---

## Verbose HTTP Debugging

    curl -v https://example.com/api/users/42

The `-v` option provides detailed connection and protocol information.

It is particularly useful for diagnosing:

- TLS issues
- Redirects
- Request headers
- Response headers
- Connection problems

---

## Follow Redirects

    curl -i -L https://example.com/old-path

The `-L` option instructs cURL to follow redirects.

Without it, cURL can show the redirect response itself.

---

## POST JSON

A typical JSON request is:

    curl -i -X POST https://example.com/api/users \
      -H "Content-Type: application/json" \
      -d '{"name":"Asha","email":"asha@example.com"}'

Important elements:

- `-X POST` selects the method
- `-H` adds a header
- `-d` supplies the request body
- `-i` displays the response headers

---

## Inspect Only the Status Code

A useful diagnostic pattern is:

    curl -s -o /dev/null -w "%{http_code}\n" https://example.com/health

This suppresses the response body and prints the HTTP status code.

---

# 53. Postman Workflow

Postman provides a graphical interface for constructing and inspecting HTTP requests.

A request commonly contains:

- Method
- URL
- Query parameters
- Authorization
- Headers
- Body

The response inspection area commonly provides:

- Status
- Response body
- Response headers
- Response time
- Response size
- Cookies

A practical debugging workflow is:

1. Confirm the HTTP method.
2. Confirm the URL.
3. Check path parameters.
4. Check query parameters.
5. Check authorization.
6. Check request headers.
7. Check `Content-Type`.
8. Check the request body.
9. Send the request.
10. Read the status code first.
11. Inspect response headers.
12. Inspect the response body.
13. Compare the result with the API contract.
14. Reduce the request to a minimal test if the problem remains unclear.

Status assertions can also be automated in Postman tests.

Conceptually, a test may assert that a successful endpoint returns `200`.

---

# 54. Python HTTP Client Demonstration

The script uses Python's standard-library `urllib.request`.

This avoids requiring third-party dependencies.

The example demonstrates an important distinction.

## HTTPError

An `HTTPError` occurs when the server returned an HTTP response such as:

    404
    500
    503

The client successfully reached an HTTP server and received a response.

## URLError

A `URLError` can represent a network-level problem where the client could not obtain the expected HTTP response.

Possible causes include:

- DNS failure
- Connection failure
- Network problem

This distinction is important for application error handling.

An HTTP 404 is fundamentally different from being unable to contact the server.

---

# 55. Local HTTP Server

The Python script creates a small HTTP server using:

- `http.server`
- `BaseHTTPRequestHandler`
- `HTTPServer`

The server demonstrates:

    GET /health
        -> 200

    GET /users/1
        -> 200

    GET /users/999
        -> 404

    POST /users
        -> 201 for valid data

    POST /users
        -> 400 for malformed JSON

    POST /users
        -> 415 for unsupported media type

    POST /users
        -> 422 for semantic validation failure

    PATCH /users/1
        -> 405

    GET /redirect
        -> 301

    GET /error
        -> 500

This makes the concepts executable instead of purely theoretical.

---

# 56. Validation and Status Codes

The script validates a user payload using rules such as:

- Name must be a non-empty string.
- Email must contain an `@`.
- Age must be an integer.
- Age must be at least 18.

This demonstrates the difference between syntactic validity and semantic validity.

For example:

    {
      "name": "Ravi",
      "email": "invalid",
      "age": 16
    }

is valid JSON.

It is not valid according to the application's user rules.

The example therefore uses:

    422 Unprocessable Content

---

# 57. Request Size Validation

Servers should protect themselves against excessively large request bodies.

A simplified policy might be:

    if Content-Length > maximum:
        return 413

This should ideally happen before expensive parsing or business processing.

Request-size limits can be enforced at multiple layers:

- Reverse proxy
- API gateway
- Web server
- Application server
- Individual endpoint

The effective limit is often determined by the smallest configured limit in the request path.

---

# 58. Performance Considerations

Status codes themselves impose negligible computational overhead.

Performance concerns generally involve the processing required to produce the response.

Examples:

### Fast 404

A missing resource can be detected through an indexed database lookup.

### Slow 500

A request may perform several expensive operations before an unexpected exception occurs.

### Fast 503

A service can immediately reject traffic when overloaded rather than allowing every request to consume resources.

### Slow 504

A gateway may spend several seconds waiting for an unavailable dependency before returning a timeout.

Performance analysis should therefore consider:

- Latency
- Database time
- Dependency time
- Connection-pool usage
- Retry volume
- Response size
- CPU usage
- Memory usage

---

# 59. Security Considerations

HTTP status handling has security implications.

## Authentication Leakage

A system should avoid revealing unnecessary information about protected resources.

For example, returning different responses for:

    resource exists but user lacks access

versus:

    resource does not exist

may allow attackers to discover sensitive identifiers.

Some systems intentionally use `404` to conceal protected resources.

---

## Rate Limiting

`429` can help protect sensitive endpoints such as:

- Login
- Password reset
- OTP verification
- Expensive searches
- Large data exports

---

## Request Size Limits

`413` helps prevent oversized requests from consuming excessive memory or processing capacity.

---

## Error Disclosure

Never expose sensitive internal information through `500` responses.

A safe error response should contain enough information for the client to understand the problem without revealing internal architecture.

---

# 60. Production Error Handling

Production APIs should separate three concerns:

## HTTP Semantics

Examples:

    404
    409
    422
    503

## Application Error Codes

Examples:

    USER_NOT_FOUND
    DUPLICATE_USERNAME
    VALIDATION_ERROR
    PAYMENT_DECLINED

## Diagnostic Information

Examples:

- Stack trace
- Database exception
- Internal service name
- Dependency failure
- Request metadata

Diagnostic information belongs primarily in controlled server-side logs.

A request ID can connect the client-visible error to internal diagnostics.

---

# 61. Request IDs

A production API may return:

    {
      "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected server error occurred.",
        "request_id": "req-123"
      }
    }

The server can log:

    request_id=req-123
    endpoint=/users/42
    status=500
    dependency=database
    duration_ms=142

This allows an operator to investigate the failure without exposing the underlying technical details to the client.

---

# 62. Testing Status-Code Contracts

Status codes should be tested like other API behavior.

For example:

    GET /health -> 200

    GET /users/999 -> 404

    POST /users with valid data -> 201

    POST /users with invalid fields -> 422

    PATCH /users/1 when unsupported -> 405

Contract tests reduce accidental API behavior changes.

A status code should not change merely because an internal implementation was refactored.

---

# 63. Edge Cases

## Repeated DELETE

Possible policies include:

    First DELETE -> 204
    Second DELETE -> 404

or:

    First DELETE -> 204
    Second DELETE -> 204

Either can be defensible depending on API semantics.

Consistency is critical.

---

## Asynchronous Processing

When work has been accepted but not completed:

    202 Accepted

is often more expressive than:

    200 OK

with an ambiguous body.

---

## Cached Resources

If the resource has not changed:

    304 Not Modified

is more meaningful than:

    200 OK

with an empty response body.

---

## Unsupported Methods

If the resource exists but the method does not:

    405 Method Not Allowed

is more precise than a generic `404`.

---

## Unknown Status Codes

Clients should generally understand status classes even if they do not recognize every specific code.

For example, an unknown `4xx` status should still be treated as a client-error class.

An unknown `5xx` status should still be treated as a server-error class.

This is one reason why the first digit is important.

---

# 64. Why 418 Is Not a General Error Code

`418 I'm a Teapot` is a famous humorous status code associated with an April Fools' specification.

It is not an appropriate replacement for ordinary API errors.

The broader lesson is that status codes should be chosen according to their semantics rather than their memorability.

---

# 65. API Consistency

A technically valid status code can still create a poor API if it is used inconsistently.

For example, suppose one endpoint uses:

    404 -> missing resource

while another endpoint returns:

    200 -> {"error": "not found"}

Clients now need endpoint-specific logic.

A coherent API might establish conventions such as:

    200 -> normal success
    201 -> creation
    202 -> asynchronous acceptance
    204 -> success without content
    400 -> malformed request
    401 -> authentication failure
    403 -> authorization refusal
    404 -> missing resource
    409 -> state conflict
    415 -> unsupported request media type
    422 -> validation failure
    429 -> rate limit
    500 -> unexpected server failure
    502 -> upstream failure
    503 -> temporary unavailability
    504 -> upstream timeout

These conventions should be documented and tested.

---

# 66. Status Codes and Distributed Systems

In distributed systems, an HTTP request may cross several components:

    Client
      |
      v
    CDN
      |
      v
    Load Balancer
      |
      v
    API Gateway
      |
      v
    Service A
      |
      v
    Service B
      |
      v
    Database

The final status code may represent a failure observed by an intermediary rather than a direct application exception.

For example:

- `502` may indicate an invalid response from Service B.
- `504` may indicate Service A waited too long for Service B.
- `503` may indicate Service A deliberately rejected traffic because Service B is unavailable.

Understanding the request path is essential when debugging 5xx responses.

---

# 67. Practical Debugging Strategy

When an API request fails, use a systematic approach.

## First: Check the Status

Do not start by reading hundreds of lines of response data.

Determine:

    4xx?
    5xx?
    3xx?
    2xx?

## Second: Check the Method

A correct URL with an incorrect method can produce:

    405

## Third: Check Authentication

Missing or invalid credentials can produce:

    401

## Fourth: Check Authorization

A valid identity without sufficient permission can produce:

    403

## Fifth: Check Resource Existence

A missing resource can produce:

    404

## Sixth: Check Headers

Especially:

    Authorization
    Content-Type
    Accept
    If-Match
    If-None-Match

## Seventh: Check the Body

For JSON APIs, verify:

- Valid JSON
- Required fields
- Correct data types
- Valid domain values

## Eighth: Check Dependencies

For 502, 503, and 504, investigate:

- Upstream services
- Network connectivity
- Timeouts
- Load balancers
- Service health

---

# 68. Status-Code Decision Matrix

| Question | Likely Code |
|---|---:|
| Did the operation succeed normally? | 200 |
| Did it create a resource? | 201 |
| Was it accepted for asynchronous processing? | 202 |
| Did it succeed without content? | 204 |
| Did the URI permanently change? | 301 |
| Is the representation cached and unchanged? | 304 |
| Is the request malformed? | 400 |
| Is authentication missing or invalid? | 401 |
| Is the user authenticated but forbidden? | 403 |
| Is the target resource unavailable? | 404 |
| Is the method unsupported? | 405 |
| Is there a current-state conflict? | 409 |
| Did a supplied precondition fail? | 412 |
| Is the request too large? | 413 |
| Is the request media type unsupported? | 415 |
| Did semantic validation fail? | 422 |
| Was the rate limit exceeded? | 429 |
| Did the application unexpectedly fail? | 500 |
| Did an upstream return an invalid response? | 502 |
| Is the service temporarily unavailable? | 503 |
| Did a gateway time out waiting for upstream? | 504 |

---

# 69. The Most Important Distinctions

The following pairs are particularly important in API development.

| Distinction | Key Idea |
|---|---|
| 200 vs 201 | Successful operation vs resource creation |
| 200 vs 204 | Response representation vs no response body |
| 301 vs 302 | Permanent vs temporary redirect |
| 302 vs 307 | Legacy redirect behavior vs explicit method preservation |
| 307 vs 308 | Temporary vs permanent method-preserving redirect |
| 304 vs 200 | Cache validation vs complete representation |
| 400 vs 422 | Malformed request vs semantic validation failure |
| 401 vs 403 | Authentication vs authorization |
| 404 vs 410 | Not available vs deliberately permanently removed |
| 409 vs 412 | Application state conflict vs failed HTTP precondition |
| 415 vs 422 | Unsupported media type vs invalid content |
| 429 vs 503 | Client rate limit vs service availability |
| 502 vs 504 | Invalid upstream response vs upstream timeout |
| 503 vs 504 | Service unavailable vs gateway waiting for upstream |

---

# 70. Complete Status-Code Mental Model

A compact mental model is:

    1xx
        "I received the request and processing continues."

    2xx
        "The requested operation succeeded."

    3xx
        "The client may need to take another action or use another resource."

    4xx
        "The request cannot be fulfilled because of a client-side condition."

    5xx
        "The server failed to fulfill an otherwise processable request."

Then refine the decision using the specific status semantics.

For example:

    4xx
      |
      +-- Authentication? --------> 401
      |
      +-- Authorization? ---------> 403
      |
      +-- Missing resource? ------> 404
      |
      +-- Method unsupported? ----> 405
      |
      +-- State conflict? --------> 409
      |
      +-- Media type? ------------> 415
      |
      +-- Validation? ------------> 422
      |
      +-- Rate limit? ------------> 429

And:

    5xx
      |
      +-- Unexpected application failure -> 500
      |
      +-- Invalid upstream response ------> 502
      |
      +-- Temporary unavailable ----------> 503
      |
      +-- Upstream timeout ---------------> 504

---

# 71. Scope of the Python Script

The Python study file implements the concepts directly through executable code.

It includes:

- HTTP status classification
- Status-code descriptions
- 1xx examples
- 2xx examples
- 3xx examples
- 4xx examples
- 5xx examples
- 401 vs 403
- 400 vs 422
- 404 vs 410
- 409 vs 412
- HTTP methods
- Idempotency
- Conditional requests
- ETags
- 304 behavior
- Structured API errors
- Retry classification
- Exponential backoff
- Rate-limit modeling
- Content negotiation
- Content-Type validation
- Optimistic concurrency
- Location headers
- A local HTTP server
- Python HTTP client requests
- Error handling with `HTTPError` and `URLError`
- cURL command examples
- Postman testing concepts
- Status assertions
- API contract modeling
- Security considerations
- Observability
- Proxy and gateway scenarios
- Circuit-breaker concepts
- Edge cases
- Automated self-tests

The script uses Python's standard library and is designed to run as a standalone educational program.

---

# 72. Real-World Relevance

HTTP status codes are foundational to:

- REST APIs
- Web applications
- Mobile backends
- Microservices
- API gateways
- Reverse proxies
- Load balancers
- CDN architectures
- Authentication systems
- Payment systems
- Distributed systems
- Monitoring systems
- Automated testing
- Integration platforms

A status code is not merely an error number. It is part of the contract between an HTTP client and server.

Correct status-code selection improves:

- Client implementation
- Error handling
- Retry behavior
- Monitoring
- Debugging
- API consistency
- Security
- Interoperability
- Operational visibility

The most effective API designs use status codes precisely, consistently, and together with clear headers and structured response bodies.
