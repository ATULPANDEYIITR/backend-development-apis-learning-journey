# HTTP Fundamentals

## HTTP Purpose, Requests, Responses, Methods, Headers, Body, Status Codes, and the HTTP Lifecycle

## 1. Introduction

HTTP stands for **Hypertext Transfer Protocol**. It is an application-layer protocol used to exchange representations of resources between clients and servers.

A client can be a:

- Web browser
- Mobile application
- Python program
- Command-line HTTP client
- Backend service
- API consumer
- Another server

A server can be:

- A web server
- An API server
- An application server
- A reverse proxy
- A gateway
- A load-balancing layer
- A CDN or caching intermediary

The fundamental HTTP interaction is:

Client → HTTP Request → Server

Server → HTTP Response → Client

The Python script associated with this README builds this model progressively. It begins with the basic request/response model and continues into methods, headers, bodies, status codes, caching, cookies, HTTPS, HTTP versions, connection management, error handling, security, and practical implementation.

---

## 2. What HTTP Actually Does

HTTP defines a structured way for communicating parties to exchange messages.

An HTTP interaction answers questions such as:

- What operation does the client want?
- Which resource is being targeted?
- What information does the client provide?
- What formats can the client accept?
- What happened when the server processed the request?
- What representation did the server return?
- Should the response be cached?
- Should the client store a cookie?
- Should the client retry?
- Has the resource changed since the client last retrieved it?

HTTP does not itself provide all of the networking infrastructure required for communication.

A simplified stack is:

- Application: HTTP
- Security: TLS when HTTPS is used
- Transport: TCP for traditional HTTP/1.1 and HTTP/2 deployments, or QUIC for HTTP/3
- Network: IP
- Name resolution: DNS

Understanding this separation is important because HTTP semantics and network transport are related but different concepts.

---

## 3. Client, Server, Resource, Request, and Response

### Client

The client initiates an HTTP interaction.

Examples include browsers, Python applications, mobile apps, and backend services.

### Server

The server receives requests, processes them, and produces responses.

### Resource

A resource is something identified by a URI. It might represent:

- A web page
- A user
- A product
- An image
- A document
- A database-backed API object
- A collection
- A dynamically generated result

### Request

The request expresses what the client wants the server to do or provide.

### Response

The response communicates the result of processing the request.

The response normally contains:

- A status code
- Response headers
- An optional response body

---

## 4. URI and URL Structure

A commonly encountered URL has the structure:

    scheme://authority/path?query#fragment

For example:

    https://api.example.com:8443/users/42?active=true&sort=name#profile

Its components include:

- Scheme: `https`
- Host: `api.example.com`
- Port: `8443`
- Path: `/users/42`
- Query: `active=true&sort=name`
- Fragment: `profile`

The fragment is generally processed by the user agent and is not sent to the server as part of a normal HTTP request.

### Scheme

The scheme identifies the protocol or access mechanism.

Examples include:

- `http`
- `https`

### Authority

The authority identifies the network destination, normally including the host and optionally a port.

### Path

The path identifies the resource or routing target.

### Query

The query carries parameters associated with the request target.

For example:

    /products?category=books&page=2

The server can parse these values as:

- `category = books`
- `page = 2`

### Fragment

A fragment identifies a secondary location within a representation.

For example:

    https://example.com/document#chapter3

The fragment is normally not included in the HTTP request sent to the server.

---

## 5. Percent Encoding

URLs cannot represent every character directly in every context.

Percent encoding allows characters to be represented using encoded byte values.

For example:

    HTTP fundamentals & APIs

can be percent-encoded into a form such as:

    HTTP%20fundamentals%20%26%20APIs

Python's `urllib.parse` utilities demonstrate parsing, encoding, and decoding in the script.

Correct URL construction matters because path segments, query parameters, fragments, and other URL components have different encoding rules.

A common mistake is to manually concatenate arbitrary strings into URLs without appropriate encoding.

---

## 6. What Happens Before an HTTP Request Reaches the Server

For an HTTPS request, the complete lifecycle can involve several stages.

### 1. URL construction

The application determines the target URL.

### 2. DNS resolution

The hostname is resolved to an IP address.

### 3. Connection establishment

The client establishes or reuses an appropriate network connection.

### 4. TLS negotiation

For HTTPS, TLS establishes an encrypted and authenticated communication channel.

### 5. HTTP request construction

The client creates the HTTP request.

### 6. Request transmission

The request headers and optional body are transmitted.

### 7. Server processing

The server parses and processes the request.

### 8. Response construction

The server creates an HTTP response.

### 9. Response transmission

The response is sent back to the client.

### 10. Client processing

The client interprets the status code, headers, and body.

### 11. Connection management

The connection may be reused or closed.

This lifecycle is one of the central concepts demonstrated by the Python script.

---

## 7. Structure of an HTTP Request

A simplified HTTP/1.1 request looks like this:

    GET /products?page=2 HTTP/1.1
    Host: example.com
    Accept: application/json
    User-Agent: StudyClient/1.0
    Connection: keep-alive

    [optional body]

An HTTP/1.x request contains:

1. Request line
2. Headers
3. Blank line
4. Optional body

The request line contains:

- Method
- Request target
- HTTP version

For example:

    GET /products HTTP/1.1

The blank line separates the header section from the optional body.

---

## 8. Structure of an HTTP Response

A simplified HTTP response looks like this:

    HTTP/1.1 200 OK
    Content-Type: text/plain; charset=utf-8
    Content-Length: 13

    Hello, client!

A response contains:

1. Status line
2. Headers
3. Blank line
4. Optional body

The status line contains:

- HTTP version
- Numeric status code
- Reason phrase

The status code is the important machine-readable component.

The reason phrase is secondary and should not be treated as a stable application contract.

---

## 9. HTTP Methods

HTTP methods communicate request semantics.

The script demonstrates the important methods.

### GET

GET is primarily used to retrieve a representation of a resource.

Example:

    GET /users/42

GET is defined as:

- Safe
- Idempotent

### HEAD

HEAD has semantics similar to GET but does not return the response content.

It can be useful for obtaining metadata such as:

- Content-Type
- Content-Length
- ETag
- Last-Modified

### POST

POST submits content to a target resource for processing.

Common uses include:

- Creating resources
- Submitting forms
- Triggering processing
- Executing operations whose semantics are defined by the target resource

POST is generally not idempotent.

### PUT

PUT generally represents creating or replacing the representation associated with a target resource.

PUT is idempotent.

### PATCH

PATCH applies partial modifications to a resource.

PATCH is not inherently idempotent, although a particular PATCH operation can be designed to behave idempotently.

### DELETE

DELETE requests removal of the target resource association.

DELETE is idempotent in HTTP semantics.

The responses to repeated DELETE requests can still differ.

### OPTIONS

OPTIONS asks about available communication options.

It is also important in browser CORS preflight behavior.

### TRACE

TRACE is primarily intended for diagnostic loop-back behavior.

It may be disabled in production environments when it is not required.

### CONNECT

CONNECT establishes a tunnel through an intermediary, commonly for HTTPS proxy tunneling.

---

## 10. Safe Methods

A method is **safe** when it is defined as primarily retrieving information or otherwise not requesting a state-changing operation on the target resource.

Common safe methods include:

- GET
- HEAD
- OPTIONS
- TRACE

Safe does not mean that absolutely nothing changes anywhere on the server.

For example, a GET request might produce:

- Access logs
- Metrics
- Cache updates
- Monitoring events

Safety refers to the intended semantics of the requested operation.

---

## 11. Idempotent Methods

A method is **idempotent** when making the same request multiple times has the same intended effect on the resource state as making it once.

Important examples include:

- GET
- HEAD
- PUT
- DELETE
- OPTIONS
- TRACE

Idempotency does not mean that every response must be identical.

For example, a DELETE operation could produce:

- 204 on one request
- 404 on a later request

The intended resource state can still be the same: the resource is absent.

---

## 12. Why Idempotency Matters for Retries

Consider:

    POST /payments

Suppose the server successfully processes a payment, but the client loses the connection before receiving the response.

The client cannot necessarily know whether the operation succeeded.

Blindly sending the POST again could create a duplicate payment.

This is why retry logic must consider:

- HTTP method
- Operation semantics
- Network failure
- HTTP status
- Request replayability
- Idempotency
- Server behavior

APIs that support idempotency keys can allow the server to recognize repeated attempts representing the same logical operation.

---

## 13. HTTP Headers

Headers carry metadata and control information.

Examples include:

- `Host`
- `User-Agent`
- `Accept`
- `Accept-Encoding`
- `Content-Type`
- `Content-Length`
- `Authorization`
- `Cookie`
- `If-None-Match`
- `If-Modified-Since`
- `ETag`
- `Cache-Control`
- `Location`
- `Set-Cookie`
- `WWW-Authenticate`

HTTP header field names are case-insensitive.

These are equivalent as field names:

    Content-Type
    content-type
    CONTENT-TYPE

Header values are a separate matter. Their syntax and case sensitivity depend on the individual header.

---

## 14. Host Header

The `Host` header identifies the target host in HTTP/1.1 requests.

For example:

    Host: api.example.com

One IP address can serve multiple domains through virtual hosting.

HTTPS also involves TLS-level mechanisms such as Server Name Indication, or SNI, which allows a server to select an appropriate certificate during TLS negotiation.

HTTP routing and TLS certificate selection are related but distinct layers.

---

## 15. User-Agent

The `User-Agent` header identifies the client software.

Example:

    User-Agent: HTTPStudyClient/1.0

Servers may use this information for:

- Diagnostics
- Compatibility behavior
- Analytics
- Logging

It should not normally be treated as a strong authentication mechanism because clients can generally control it.

---

## 16. Accept Header

The `Accept` header tells the server which response media types the client can process.

Example:

    Accept: application/json

A client can express multiple preferences:

    text/html;q=0.8, application/json;q=1.0, text/plain;q=0.5

The quality value indicates preference.

Content negotiation can involve:

- `Accept`
- `Accept-Language`
- `Accept-Encoding`

---

## 17. Content-Type

`Content-Type` describes the media type of a representation.

Examples:

    Content-Type: application/json

    Content-Type: text/html; charset=utf-8

    Content-Type: application/octet-stream

The server should not assume that a body is JSON merely because an endpoint looks like an API endpoint.

The declared content type should be validated and the content should be parsed appropriately.

---

## 18. Common Media Types

Important HTTP media types include:

### application/json

Used for JSON representations.

### text/html

Used for HTML.

### text/plain

Used for plain text.

### application/xml

Used for XML representations.

### application/octet-stream

Generic binary content.

### multipart/form-data

Used for multipart form submissions, including file uploads.

### application/x-www-form-urlencoded

Used for URL-encoded form data.

---

## 19. Request Body

An HTTP request can contain a body.

Common methods associated with request bodies include:

- POST
- PUT
- PATCH

The body may contain:

- JSON
- Form data
- XML
- Text
- Binary data
- Multipart content

For example:

    {
        "name": "Alice",
        "role": "developer"
    }

When the body is JSON, the request should normally include:

    Content-Type: application/json

The Python script serializes Python objects into JSON and calculates their byte length.

---

## 20. Response Body

A response body can contain:

- HTML
- JSON
- XML
- Text
- Images
- Audio
- Video
- Binary files

A response does not necessarily contain a body.

Examples include:

- HEAD responses
- 204 No Content
- 304 Not Modified

The client must interpret body behavior using the HTTP method, status code, headers, and protocol semantics.

---

## 21. Content-Length

`Content-Length` describes the body length in bytes when applicable.

For example:

    Content-Length: 13

A critical point is that HTTP lengths are byte-oriented.

For Unicode text:

    len("é")

does not necessarily equal:

    len("é".encode("utf-8"))

A character can require multiple bytes in UTF-8.

The Python script explicitly demonstrates the difference between character count and byte count.

---

## 22. Content-Encoding

`Content-Encoding` describes a transformation applied to the representation.

For example:

    Content-Encoding: gzip

The client can advertise supported encodings using:

    Accept-Encoding: gzip

These concepts must not be confused.

For example:

    Content-Type: application/json
    Content-Encoding: gzip

means that the underlying representation is JSON and gzip content coding has been applied.

---

## 23. Transfer Encoding

Transfer encoding concerns how HTTP/1.1 messages are transferred.

One important example is:

    Transfer-Encoding: chunked

Chunked transfer encoding sends a body in a sequence of chunks.

A simplified sequence is conceptually:

    chunk-size
    chunk-data
    chunk-size
    chunk-data
    0

The zero-sized chunk marks the end.

Transfer encoding and content encoding are different concepts.

Content encoding describes a representation transformation such as gzip.

Transfer encoding describes the transfer mechanism used by the HTTP message.

---

## 24. Chunked Transfer Encoding

The Python script implements a small educational chunked-body decoder.

This is useful for understanding why HTTP message parsing requires explicit framing.

Chunked data can contain:

- Chunk size
- Chunk data
- Optional chunk extensions
- Trailers
- Final zero-sized chunk

The parser in the script is intentionally simplified.

A production HTTP implementation should use a mature protocol parser rather than a handwritten educational parser.

---

## 25. Status Codes

HTTP status codes are grouped into five classes.

### 1xx

Informational responses.

### 2xx

Successful responses.

### 3xx

Redirection responses.

### 4xx

Client error responses.

### 5xx

Server error responses.

The numeric status code is the important machine-readable value.

---

## 26. Important 2xx Status Codes

### 200 OK

The request succeeded.

### 201 Created

A resource was successfully created.

### 202 Accepted

The request has been accepted for processing, but processing may not yet be complete.

This is useful for asynchronous operations.

### 204 No Content

The request succeeded and there is intentionally no response content.

### 206 Partial Content

The response contains a requested range of a representation.

---

## 27. Important 3xx Status Codes

### 301 Moved Permanently

Indicates permanent redirection.

### 302 Found

Indicates a temporary redirection.

### 303 See Other

Redirects the client to another resource.

### 304 Not Modified

Used with conditional requests when the cached representation can still be reused.

### 307 Temporary Redirect

Temporary redirect that preserves method semantics.

### 308 Permanent Redirect

Permanent redirect that preserves method semantics.

The distinction between 302/303 and 307/308 is especially important when request method and body preservation matter.

---

## 28. Important 4xx Status Codes

### 400 Bad Request

The request cannot be processed because it is malformed or invalid.

### 401 Unauthorized

Authentication is required or has failed.

The name can be misleading because the status is primarily associated with authentication.

### 403 Forbidden

The server understood the request but refuses to fulfill it.

### 404 Not Found

The target resource was not found or is intentionally undisclosed.

### 405 Method Not Allowed

The method is known but is not supported for the target resource.

The response should identify supported methods with an `Allow` header.

### 406 Not Acceptable

The server cannot provide an acceptable representation according to the request's content negotiation preferences.

### 409 Conflict

The request conflicts with the current resource state.

### 412 Precondition Failed

A request precondition evaluated to false.

### 413 Content Too Large

The request content exceeds a limit.

### 415 Unsupported Media Type

The server does not support the representation format supplied in the request.

### 422 Unprocessable Content

The content type can be understood, but the content cannot be processed because of semantic problems.

### 429 Too Many Requests

The client has exceeded a rate limit.

---

## 29. Important 5xx Status Codes

### 500 Internal Server Error

An unexpected server-side error occurred.

### 501 Not Implemented

The server does not support the functionality required to fulfill the request.

### 502 Bad Gateway

A gateway or proxy received an invalid response from an upstream server.

### 503 Service Unavailable

The server is temporarily unable to handle the request.

### 504 Gateway Timeout

A gateway or proxy did not receive a timely response from an upstream server.

---

## 30. HTTP Errors vs Network Errors

This distinction is critical.

An HTTP error means an HTTP response was successfully received.

For example:

    HTTP/1.1 404 Not Found

The HTTP communication itself worked.

A network error is different.

Examples include:

- DNS failure
- Connection refusal
- Connection timeout
- TLS failure
- Broken connection
- Routing failure

A robust client should distinguish these situations.

A 404 response is not equivalent to a timeout.

---

## 31. Cookies

Cookies provide a mechanism for storing state associated with HTTP interactions.

A server can send:

    Set-Cookie: session_id=abc123; Path=/; HttpOnly; Secure

The client can later send:

    Cookie: session_id=abc123

Important cookie attributes include:

### Secure

The cookie should only be transmitted over secure connections.

### HttpOnly

The cookie is not available to ordinary client-side JavaScript APIs.

### SameSite

Controls cross-site cookie sending behavior.

### Domain

Controls applicable hosts.

### Path

Controls applicable paths.

### Max-Age

Controls cookie lifetime in seconds.

### Expires

Specifies an expiration date.

Cookies are not automatically secure merely because they are cookies.

---

## 32. Authentication

Authentication asks:

> Who are you?

HTTP commonly carries authentication information using the `Authorization` header.

For example:

    Authorization: Bearer <token>

Another authentication scheme is Basic authentication.

Conceptually:

    Authorization: Basic <encoded-credentials>

Base64 is encoding, not encryption.

Sensitive authentication information should be protected using HTTPS.

---

## 33. Authorization

Authorization asks:

> Are you allowed to perform this operation?

Authentication and authorization should be treated as separate concepts.

A user may be authenticated but still lack permission to access a particular resource.

This distinction helps explain the difference between responses such as 401 and 403.

---

## 34. 401 vs 403

### 401 Unauthorized

Usually indicates that authentication is required or unsuccessful.

A server may include:

    WWW-Authenticate: Bearer

### 403 Forbidden

Indicates that the server refuses the request.

Applications should not treat the two statuses as interchangeable.

---

## 35. CORS

CORS stands for **Cross-Origin Resource Sharing**.

It is a browser security mechanism controlling whether scripts from one origin may access resources from another origin.

An origin is generally identified by:

    scheme + host + port

For example:

    https://app.example.com

and:

    https://api.example.com

are different origins.

CORS-related headers include:

- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Methods`
- `Access-Control-Allow-Headers`
- `Access-Control-Allow-Credentials`

Certain cross-origin browser requests can trigger an OPTIONS preflight request.

CORS is primarily a browser enforcement mechanism. A command-line HTTP client does not automatically apply browser CORS restrictions.

---

## 36. HTTP Caching

Caching allows previously retrieved representations to be reused.

Important caching mechanisms include:

- `Cache-Control`
- `ETag`
- `Last-Modified`
- `Expires`
- `If-None-Match`
- `If-Modified-Since`

Caching can reduce:

- Latency
- Bandwidth usage
- Server load
- Database load

Caching must be configured carefully because incorrect caching can expose stale or sensitive information.

---

## 37. Cache-Control

Important directives include:

### max-age

Defines a freshness lifetime in seconds.

Example:

    Cache-Control: max-age=60

### no-store

Indicates that the response should not be stored.

### no-cache

Indicates that stored content generally requires validation before reuse.

### private

Indicates that the response is intended for a private cache rather than shared caching.

### public

Allows shared caching when other requirements permit it.

### must-revalidate

Places additional requirements on reuse after freshness constraints are reached.

---

## 38. ETag

An ETag is a representation validator.

Example:

    ETag: "version-42"

A client can later send:

    If-None-Match: "version-42"

If the representation has not changed, the server can return:

    304 Not Modified

The client can then reuse its stored representation.

ETags can also be used for optimistic concurrency control.

---

## 39. Strong and Weak ETags

A strong ETag can indicate byte-level equivalence.

A weak ETag has the form:

    W/"value"

Weak validators indicate that semantic equivalence may be sufficient even when representations are not byte-for-byte identical.

This distinction matters when designing caching and conditional update behavior.

---

## 40. Conditional Requests

Conditional requests allow the client to make an operation dependent on the current state of a resource.

Important conditional headers include:

- `If-Match`
- `If-None-Match`
- `If-Modified-Since`
- `If-Unmodified-Since`

For example:

    If-Match: "version-5"

can mean that an update should proceed only if the current representation still matches version 5.

If the resource has already changed, the server can return:

    412 Precondition Failed

This helps prevent lost updates.

---

## 41. Range Requests

A client can request part of a resource using a `Range` header.

Example:

    Range: bytes=0-99

A server supporting this range can respond with:

    206 Partial Content

and potentially:

    Content-Range: bytes 0-99/1000

Range requests are useful for:

- Large downloads
- Resumable downloads
- Media delivery
- Partial retrieval

---

## 42. Redirects

Redirect responses normally include a `Location` header.

Example:

    Location: /login

The client can then make another request to the specified location.

Important redirect codes include:

- 301
- 302
- 303
- 307
- 308

The exact behavior matters when the original request uses a method such as POST.

---

## 43. HTTP/1.0

HTTP/1.0 is an older version of HTTP.

It generally used shorter-lived connections and did not provide the same persistent connection model that became standard with HTTP/1.1.

It established many of the foundational concepts still recognizable today:

- Request methods
- Status codes
- Headers
- Bodies
- Request/response structure

---

## 44. HTTP/1.1

HTTP/1.1 introduced or standardized important capabilities including:

- Persistent connections
- Host-based virtual hosting
- Chunked transfer encoding
- Extensive caching semantics
- Richer request and response behavior

HTTP/1.1 messages use a textual representation for the traditional request and response syntax.

---

## 45. Persistent Connections

A persistent connection allows multiple HTTP exchanges to use the same underlying connection when appropriate.

Without reuse, a simplified pattern is:

    connect
    request
    response
    close

Repeated many times, this creates additional connection setup overhead.

With reuse:

    connect
    request
    response
    request
    response
    request
    response
    close

Connection reuse can improve performance.

---

## 46. HTTP/2

HTTP/2 changes the wire representation while preserving familiar HTTP semantics.

Important HTTP/2 concepts include:

- Binary framing
- Streams
- Multiplexing
- Header compression
- Flow control

Multiple logical request/response exchanges can share one connection.

The application still works with familiar concepts such as:

- GET
- POST
- Headers
- Status codes
- Request bodies
- Response bodies

The major changes occur at the protocol framing and transport interaction level.

---

## 47. HTTP/3

HTTP/3 maps HTTP semantics onto QUIC.

QUIC uses UDP as its underlying transport protocol and provides transport functionality such as:

- Encryption
- Independent streams
- Connection migration
- Stream-oriented loss handling

HTTP/3 uses binary framing and does not use HTTP/1.1 chunked transfer encoding in the same manner.

HTTP/3 therefore changes the transport architecture while retaining HTTP request and response semantics.

---

## 48. TLS and HTTPS

HTTPS means HTTP carried through TLS.

TLS provides:

### Confidentiality

Helps prevent unauthorized parties from reading protected traffic.

### Integrity

Helps detect unauthorized modification of protected traffic.

### Server authentication

Certificates allow the client to authenticate the server identity under the TLS trust model.

HTTPS does not make the application automatically secure.

An HTTPS application can still contain:

- Broken authorization
- Injection vulnerabilities
- Cross-site scripting
- Cross-site request forgery
- Insecure session management
- Sensitive data exposure
- Business logic flaws

TLS protects the communication channel. It does not replace secure application design.

---

## 49. Python TLS Handling

The script demonstrates:

    ssl.create_default_context()

This creates a TLS context suitable for normal secure client behavior, including certificate verification.

Disabling certificate verification without a valid reason is dangerous because it can make the connection vulnerable to man-in-the-middle attacks.

---

## 50. HTTP Message Framing

The receiver must know where the HTTP message body ends.

For HTTP/1.x, message framing can involve:

- Request/response semantics
- `Content-Length`
- `Transfer-Encoding`
- Connection closure
- Status-code rules

Some responses do not have a message body.

This is one reason why parsing HTTP correctly is more complicated than simply reading bytes from a socket until the connection closes.

---

## 51. Raw TCP Sockets and HTTP

A TCP socket understands bytes, not HTTP concepts.

The socket does not inherently understand:

- GET
- POST
- HTTP/1.1
- Headers
- JSON
- Status codes

Those are application-level protocol concepts.

The Python script demonstrates sending a raw HTTP/1.1 request through a TCP socket.

This is useful for understanding the relationship between:

    TCP byte stream

and:

    HTTP message

---

## 52. Building a Raw HTTP Request

A simplified HTTP request consists of:

    METHOD TARGET VERSION
    Header: value
    Header: value

    body

The Python script contains a `build_http_request()` function that constructs a basic HTTP/1.1 request from:

- Method
- Target
- Headers
- Body

This demonstrates that HTTP ultimately becomes bytes transmitted over a connection.

---

## 53. Parsing HTTP Requests

The script contains a simple educational request parser.

It extracts:

- Method
- Target
- Version
- Headers
- Body

It also demonstrates that headers need to be separated from the body using the HTTP/1.x message delimiter.

This parser is intentionally incomplete.

A production HTTP parser needs to handle many additional rules and security considerations.

---

## 54. Why Handwritten HTTP Parsers Are Dangerous in Production

A real HTTP implementation must correctly handle:

- Message framing
- Transfer codings
- Header syntax
- Repeated headers
- Trailers
- Connection management
- Protocol versions
- Invalid input
- Size limits
- Parsing ambiguity
- Security edge cases
- Intermediary behavior

A handwritten parser can be useful for learning but should not replace a mature HTTP implementation in production.

---

## 55. Header Injection

HTTP/1.x uses CRLF sequences to delimit header lines.

A raw header value containing untrusted CRLF characters can potentially manipulate protocol structure in vulnerable implementations.

For example, an unsafe application might construct a header from user input without validation.

Secure applications should:

- Validate header names
- Reject CR and LF from untrusted header values
- Use mature HTTP libraries
- Avoid manual protocol construction in production

---

## 56. HTTP Request Smuggling

HTTP request smuggling can occur when different components interpret request boundaries differently.

A classic area of concern involves disagreement over:

- `Content-Length`
- `Transfer-Encoding`

For example, a proxy and origin server may parse the same bytes differently.

Potential consequences include:

- Request desynchronization
- Cache poisoning
- Routing manipulation
- Security-control bypasses

Consistent, hardened HTTP parsing across infrastructure is essential.

---

## 57. URL Path Security

A URL path should not automatically be treated as a safe filesystem path.

Security-sensitive path processing must consider:

- Percent encoding
- Dot segments
- Repeated separators
- Unicode normalization
- Filesystem behavior
- Authorization boundaries

The correct sequence of decoding and normalization operations can matter significantly.

---

## 58. Request Validation

A server should validate:

- Method
- Request target
- Headers
- Content-Type
- Content-Length
- Body size
- Body syntax
- Application-level data

For JSON, validation normally involves:

1. Confirming the media type.
2. Decoding bytes using the expected character encoding.
3. Parsing JSON.
4. Validating application-specific fields.

A valid JSON document can still contain invalid application data.

---

## 59. HTTP Errors vs Application Validation

Consider:

    POST /users

with:

    {
        "age": -5
    }

The HTTP message can be perfectly valid.

The JSON can also be syntactically valid.

The application can still reject the request because `age = -5` violates a business rule.

This demonstrates three separate layers:

1. HTTP syntax
2. Representation syntax
3. Application semantics

A successful HTTP-level parsing operation does not mean the application operation is valid.

---

## 60. API Response Design

HTTP status codes and response bodies have different roles.

The status code communicates the broad outcome.

The response body can communicate application-specific details.

For example:

    400 Bad Request

with a JSON body containing:

    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "The supplied name is invalid."
        }
    }

This allows clients to use the status code for broad handling while using the structured body for application-specific information.

---

## 61. Resource-Oriented API Design

A common HTTP API structure might look like:

    GET     /users
    GET     /users/42
    POST    /users
    PUT     /users/42
    PATCH   /users/42
    DELETE  /users/42

This approach uses HTTP method semantics to distinguish operations.

It avoids unnecessarily encoding every operation as an arbitrary POST action.

The exact design depends on the application, but understanding HTTP method semantics makes API design more predictable.

---

## 62. PUT vs PATCH

PUT generally represents replacement of the target resource representation.

Example:

    PUT /users/42

    {
        "name": "Alice",
        "email": "alice@example.com",
        "active": true
    }

PATCH generally represents partial modification.

Example:

    PATCH /users/42

    {
        "active": false
    }

PUT is idempotent.

PATCH is not inherently idempotent.

The actual behavior must be documented by the API.

---

## 63. DELETE Semantics

DELETE requests removal of a target resource association.

Possible successful responses include:

- 200 OK
- 202 Accepted
- 204 No Content

The appropriate response depends on whether the operation completed immediately, is asynchronous, and whether a representation is returned.

Repeated DELETE operations can have different status codes while still satisfying idempotency semantics.

---

## 64. POST Semantics

POST asks the target resource to process the supplied representation according to the resource's semantics.

Possible uses include:

- Resource creation
- Form submission
- Commands
- Triggering processing
- Operations requiring a request body

POST is not simply synonymous with "insert database row".

Its meaning depends on the resource and API contract.

---

## 65. Rate Limiting

APIs commonly use:

    429 Too Many Requests

when a client exceeds a configured rate limit.

The server may also provide:

    Retry-After

A client should respect such signals instead of immediately retrying repeatedly.

Rate limiting protects:

- CPU
- Memory
- Databases
- Authentication systems
- External services
- Expensive operations

---

## 66. Timeouts

HTTP clients should use explicit timeouts.

Important timeout categories include:

### Connection timeout

Maximum time allowed to establish a connection.

### Read timeout

Maximum time allowed while waiting for response data.

### Write timeout

Maximum time allowed while transmitting data.

### Total timeout

Maximum time allowed for the entire operation.

Timeouts prevent applications from waiting indefinitely for remote systems.

---

## 67. Retries

Retries can improve resilience against transient failures.

They can also make problems worse.

A retry strategy should consider:

- HTTP method
- Idempotency
- Status code
- Network failure
- Server overload
- Request replayability
- Backoff
- Jitter
- Rate limiting

Client errors such as malformed input generally should not be retried automatically.

---

## 68. Exponential Backoff

Exponential backoff increases the delay between retry attempts.

A conceptual sequence might be:

    0.5 seconds
    1 second
    2 seconds
    4 seconds
    8 seconds

The script implements a capped exponential backoff calculation.

Production systems often add random jitter so that many clients do not retry simultaneously after a shared failure.

---

## 69. Proxies

A forward proxy sits between a client and the internet:

    Client → Proxy → Internet

A reverse proxy sits in front of servers:

    Client → Reverse Proxy → Application Server

Reverse proxies can provide:

- Routing
- TLS termination
- Load balancing
- Caching
- Compression
- Rate limiting
- Access control
- Logging
- Observability

Intermediaries are an important part of modern HTTP architecture.

---

## 70. Forwarded Information

HTTP infrastructure may communicate intermediary information using headers such as:

- `Forwarded`
- `Via`

Applications must be careful with client-supplied forwarding information.

An application should only trust such metadata when the network architecture establishes which intermediaries are trusted.

---

## 71. HTTP Observability

Useful HTTP observability information can include:

- HTTP method
- Route
- Status code
- Request duration
- Response size
- Request ID
- Trace ID
- User agent
- Upstream service
- Cache result

Sensitive information should not be logged indiscriminately.

Examples requiring special care include:

- Authorization tokens
- Session cookies
- Passwords
- Personal information
- Payment information

---

## 72. Request IDs

A request identifier can correlate logs across multiple components.

A request might travel through:

    Client
    ↓
    Load balancer
    ↓
    Reverse proxy
    ↓
    API gateway
    ↓
    Application
    ↓
    Internal service

A shared request ID can make troubleshooting significantly easier.

Externally supplied identifiers should not automatically be trusted as security credentials.

---

## 73. Security Headers

Security-related response headers can strengthen browser security.

Examples include:

### Strict-Transport-Security

Encourages browsers to use HTTPS for a site after the policy is established.

### Content-Security-Policy

Controls permitted resource and script behavior.

### X-Content-Type-Options

Helps prevent MIME-type sniffing behavior.

### Referrer-Policy

Controls referrer information sent with requests.

Correct values depend on application architecture.

---

## 74. CSRF

Cross-Site Request Forgery occurs when a browser can be induced to send an authenticated request to a site where credentials such as cookies are automatically included.

Possible defenses include:

- SameSite cookie policies
- CSRF tokens
- Appropriate origin validation
- Appropriate referrer validation
- Suitable authentication architecture

CSRF and CORS are related to browser behavior but address different security problems.

---

## 75. XSS

Cross-Site Scripting occurs when untrusted content becomes executable script in a user's browser context.

HTTP transports the content but does not itself prevent XSS.

Common defenses include:

- Context-appropriate output encoding
- Safe templating
- Input validation
- Content Security Policy
- Avoiding unsafe HTML injection

---

## 76. HTTP and Backend Injection

HTTP can be the delivery mechanism for malicious input targeting backend components.

For example:

    HTTP request
        ↓
    Application
        ↓
    Database

HTTP-level validation alone cannot prevent SQL injection.

The backend must use secure database APIs, parameterized queries, and suitable validation.

---

## 77. Multipart Form Data

`multipart/form-data` allows a request body to contain multiple parts.

A multipart request uses a boundary to separate parts.

Each part can contain its own headers and content.

Multipart is commonly used for:

- Text fields
- File uploads
- Binary data
- Mixed form content

The Python script constructs a small conceptual multipart message to illustrate its structure.

---

## 78. Form URL Encoding

`application/x-www-form-urlencoded` encodes key-value pairs.

Example conceptual data:

    username=alice&topic=HTTP+fundamentals&page=1

It is commonly associated with traditional HTML forms.

It differs from `multipart/form-data`, especially when files or multiple independent content parts are involved.

---

## 79. HTTP Server Implementation in Python

The script uses Python's standard library to create a small HTTP server using:

- `BaseHTTPRequestHandler`
- `ThreadingHTTPServer`

The server demonstrates:

- GET
- POST
- OPTIONS
- JSON responses
- Query parameters
- 404 responses
- Redirect responses
- Content-Type
- Content-Length
- Method handling
- Body validation

The server is intentionally educational rather than production-ready.

---

## 80. HTTP Client Implementation in Python

The script demonstrates HTTP clients using the Python standard library.

It uses:

- `http.client.HTTPConnection`
- `urllib.request`
- `urllib.error`
- `ssl`

The examples show:

- GET requests
- POST requests
- Response status
- Response headers
- Response body
- HTTP errors
- Network errors
- Connection reuse
- HTTPS connection construction

---

## 81. HTTPConnection

Python's `HTTPConnection` exposes a lower-level HTTP client interface.

A request can be made with:

    connection.request(...)

The response can then be obtained using:

    connection.getresponse()

The response exposes:

- Status
- Reason
- Headers
- Body

This provides a useful bridge between raw HTTP concepts and higher-level client libraries.

---

## 82. urllib

Python's `urllib.request` provides a higher-level standard-library HTTP interface.

It can handle URL requests and expose responses through Python file-like interfaces.

It also provides error classes that allow applications to distinguish HTTP errors from URL/network-related errors.

---

## 83. HTTPSConnection

Python also provides `HTTPSConnection`.

It can be constructed using a secure TLS context.

The script uses:

    ssl.create_default_context()

This is preferable to disabling certificate validation.

---

## 84. HTTP Date

HTTP uses standardized date formats for headers such as:

- `Date`
- `Expires`
- `Last-Modified`
- `If-Modified-Since`

Python's standard library can format and parse these timestamps.

Correct timezone-aware datetime handling is important when comparing HTTP timestamps.

---

## 85. Content-Disposition

`Content-Disposition` can influence how a client handles a representation.

For example:

    Content-Disposition: attachment; filename="report.pdf"

Combined with:

    Content-Type: application/pdf

this can indicate that the representation is intended to be downloaded as a PDF file.

Filename handling should still be performed carefully to avoid unsafe path or filename behavior.

---

## 86. Asynchronous HTTP Operations

Not every operation can finish immediately.

For long-running operations, a server can return:

    202 Accepted

This indicates that the request has been accepted for processing but does not necessarily mean the operation is complete.

Examples include:

- Report generation
- Video processing
- Large exports
- Data imports
- Background jobs

Returning 200 for every operation can incorrectly imply that processing has already completed.

---

## 87. HTTP Streaming

HTTP responses can be streamed rather than generated as one complete body before transmission.

Streaming is useful for:

- Large files
- Event streams
- Long-running responses
- Progressive data generation

Server-Sent Events are one example of a streaming model using HTTP.

A common media type is:

    text/event-stream

---

## 88. WebSockets vs HTTP

HTTP is primarily structured around request/response interactions.

WebSocket is designed for long-lived bidirectional communication.

A WebSocket connection can begin with an HTTP-based handshake and then transition into WebSocket framing.

The protocols should not be treated as interchangeable.

HTTP is often appropriate for:

- Resource retrieval
- APIs
- CRUD operations
- Standard web communication

WebSocket is useful for:

- Bidirectional real-time communication
- Long-lived interactive connections
- Certain live collaboration systems
- Real-time messaging

---

## 89. Performance Considerations

HTTP performance can be affected by:

- DNS latency
- Connection establishment
- TLS handshake
- Server processing
- Database latency
- Payload size
- Network congestion
- Packet loss
- Compression
- Cache behavior
- Connection reuse

Performance techniques include:

- Persistent connections
- Connection pooling
- Caching
- Compression
- Efficient payload design
- HTTP/2 multiplexing
- HTTP/3 where appropriate
- CDN usage
- Asynchronous processing

Performance decisions should be based on measurements rather than assumptions.

---

## 90. Connection Reuse

Repeatedly establishing connections can introduce unnecessary overhead.

Connection reuse can reduce:

- Connection setup cost
- TLS negotiation overhead
- Latency

Modern HTTP systems can reuse connections extensively.

HTTP/2 and HTTP/3 extend this model with multiplexing and stream-based behavior.

---

## 91. HTTP and CDN Architecture

A modern request can involve several layers:

    Client
       ↓
    DNS
       ↓
    CDN
       ↓
    Load Balancer
       ↓
    Reverse Proxy
       ↓
    Application Server
       ↓
    Database / Services

HTTP headers, caching rules, status codes, and connection behavior operate across these layers.

This is why HTTP knowledge is important not only for frontend developers but also for backend, cloud, DevOps, security, and infrastructure engineering.

---

## 92. Common HTTP Mistakes

Important mistakes demonstrated or discussed by the script include:

- Treating every HTTP failure as a network failure
- Confusing 401 with authorization
- Using 200 for every application outcome
- Sending JSON without an appropriate Content-Type
- Confusing Content-Type with Content-Encoding
- Treating Content-Length as a character count
- Blindly retrying POST requests
- Disabling TLS certificate verification
- Logging Authorization headers
- Incorrectly caching sensitive information
- Writing production HTTP parsers from scratch
- Assuming browser CORS behavior applies to every HTTP client
- Assuming safe means absolutely no side effects
- Assuming idempotent means identical responses
- Treating URL paths as safe filesystem paths

---

## 93. HTTP Client Best Practices

A robust HTTP client should generally:

- Use explicit timeouts
- Use HTTPS for sensitive communication
- Validate TLS certificates
- Handle status codes intentionally
- Distinguish network failures from HTTP responses
- Retry only appropriate operations
- Use exponential backoff when appropriate
- Add jitter for distributed retry scenarios
- Respect rate limits
- Respect `Retry-After`
- Reuse connections when appropriate
- Limit response sizes
- Validate Content-Type
- Avoid logging credentials and tokens
- Use mature HTTP libraries

---

## 94. HTTP Server Best Practices

A robust HTTP server should generally:

- Validate methods
- Validate request targets
- Validate headers
- Validate Content-Type
- Validate request bodies
- Enforce request-size limits
- Use HTTPS appropriately
- Authenticate requests correctly
- Authorize operations separately
- Return meaningful status codes
- Configure caching intentionally
- Protect sensitive responses from unintended caching
- Rate-limit abusive operations
- Log useful information without leaking secrets
- Use mature HTTP parsing implementations
- Configure security headers appropriately
- Handle upstream failures and timeouts

---

## 95. HTTP and Security Boundaries

HTTP security requires understanding several different layers.

### Transport security

TLS protects communication in transit.

### Authentication

Determines the identity or credentials associated with a request.

### Authorization

Determines whether the requester is permitted to perform an operation.

### Application validation

Determines whether supplied data is valid.

### Session security

Controls how authenticated state is maintained.

### Browser security

Includes mechanisms such as CORS, CSRF defenses, and security response headers.

### Infrastructure security

Includes reverse proxies, gateways, firewalls, rate limiting, and traffic controls.

No single HTTP feature provides complete application security.

---

## 96. HTTP Lifecycle as a Complete Mental Model

The full model can be represented as:

    URL
     |
     v
    Client
     |
     | Method + Target + Headers + Optional Body
     v
    HTTP Request
     |
     v
    Intermediaries
     |
     v
    Server
     |
     | Status + Headers + Optional Body
     v
    HTTP Response
     |
     v
    Client

Before this exchange, the client may perform DNS resolution and establish a network connection.

For HTTPS, TLS is established as part of the secure communication process.

After the response, the client may:

- Parse the body
- Store cookies
- Cache the representation
- Follow a redirect
- Retry the operation
- Reuse the connection
- Close the connection

This lifecycle connects all of the individual HTTP concepts into one system.

---

## 97. Practical HTTP Debugging

When debugging an HTTP problem, examine the request and response systematically.

### URL

Check:

- Scheme
- Host
- Port
- Path
- Query
- Encoding

### Connection

Check:

- DNS
- Reachability
- Port
- Timeout
- TLS

### Request

Check:

- Method
- Target
- Headers
- Content-Type
- Content-Length
- Body

### Response

Check:

- Status code
- Headers
- Body
- Redirects
- Cache behavior

### Authentication

Check:

- Credentials
- Token
- Authentication scheme
- Expiration

### Authorization

Check:

- User permissions
- Resource permissions
- Requested operation

### Infrastructure

Check:

- Reverse proxy
- API gateway
- Load balancer
- CDN
- Firewall
- Upstream services

This structured approach prevents unrelated problems from being treated as the same type of failure.

---

## 98. HTTP Semantic Layers

HTTP can be understood through several layers.

### Message structure

The message contains:

- Request or response line
- Headers
- Optional body

### Method semantics

Methods communicate the intended operation.

### Status semantics

Status codes communicate the outcome.

### Representation metadata

Headers such as Content-Type and Content-Encoding describe representations.

### State mechanisms

Cookies and caching support stateful behavior around an otherwise stateless request/response protocol.

### Conditional behavior

ETags and conditional headers allow efficient retrieval and concurrency control.

### Transport

HTTP/1.1, HTTP/2, and HTTP/3 determine different wire and transport mechanisms.

### Security

HTTPS, authentication, authorization, cookies, browser security, and validation protect different aspects of the overall system.

---

## 99. Statelessness and HTTP

HTTP is fundamentally designed around independent request/response interactions.

The protocol does not require a server to retain conversational state between requests.

Applications can introduce state through mechanisms such as:

- Cookies
- Session identifiers
- Tokens
- Databases
- Caches
- Server-side session stores

This is why HTTP can support both simple stateless APIs and complex stateful web applications.

---

## 100. Why HTTP Knowledge Matters

HTTP is foundational to:

- Web development
- REST APIs
- Microservices
- Cloud systems
- Mobile applications
- DevOps
- Reverse proxies
- API gateways
- CDN architectures
- Application security
- Network troubleshooting
- Distributed systems

A developer who understands HTTP can reason about failures at a much deeper level than simply knowing that a browser returned an error page.

For example, knowing the difference between:

    401
    403
    404
    409
    429
    500
    502
    503
    504

allows an engineer to identify fundamentally different classes of problems.

Understanding:

    Content-Type
    Content-Length
    Transfer-Encoding
    Content-Encoding
    Cache-Control
    ETag
    Authorization
    Cookie
    Location

makes HTTP traffic much easier to inspect and debug.

Understanding:

    GET
    POST
    PUT
    PATCH
    DELETE
    HEAD
    OPTIONS

makes API behavior easier to design and reason about.

Understanding:

    HTTP/1.1
    HTTP/2
    HTTP/3
    TLS
    TCP
    QUIC

makes it possible to distinguish application-level semantics from transport-level implementation.

---

## 101. What the Python Script Demonstrates

The Python script provides executable demonstrations of:

- HTTP's client/server model
- URL parsing
- Query parameter parsing
- Percent encoding
- Raw HTTP requests
- Raw HTTP responses
- HTTP methods
- Safe methods
- Idempotent methods
- Request headers
- Response headers
- Request bodies
- Response bodies
- JSON serialization
- Media types
- Content negotiation
- Status codes
- HTTP lifecycle
- Persistent connections
- HTTP version concepts
- Chunked transfer encoding
- Content-Length
- Content-Encoding
- gzip compression
- Cookies
- Cache-Control
- ETags
- Conditional requests
- Redirects
- Authentication headers
- Authorization concepts
- CORS concepts
- Error classification
- Timeouts
- Retry behavior
- Exponential backoff
- Proxies
- Host headers
- HTTPS
- TLS contexts
- Request construction
- Request parsing
- Response construction
- Response parsing
- Content validation
- Content-Length validation
- HTTP dates
- Range requests
- Form encoding
- Multipart concepts
- A local HTTP server
- HTTP client requests
- POST processing
- OPTIONS handling
- Redirect handling
- Network versus HTTP errors
- Connection reuse
- Raw socket HTTP
- Header validation
- Header injection concerns
- URL security
- API response design
- Method routing
- Rate limiting
- Observability
- Request identifiers
- Cache simulation
- Conditional updates
- Security headers
- CSRF
- XSS
- HTTP request smuggling
- HTTP/2 concepts
- HTTP/3 concepts
- Streaming concepts
- WebSocket relationship
- Performance considerations
- Production best practices

The examples use the Python standard library wherever practical so that the HTTP concepts remain visible instead of being hidden behind a large framework.

---

## 102. Important Distinctions

The following distinctions are especially important.

| Concept A | Concept B | Key Difference |
|---|---|---|
| Authentication | Authorization | Identity vs permission |
| Content-Type | Content-Encoding | Representation format vs content transformation |
| Content-Length | Character count | Bytes vs characters |
| HTTP error | Network error | Received HTTP response vs communication failure |
| Safe | Idempotent | Safe operation semantics vs repeated-effect semantics |
| Cache-Control | ETag | Caching policy vs representation validator |
| 401 | 403 | Authentication challenge/failure vs refusal |
| 404 | 410 | Not found vs explicitly gone semantics |
| 301 | 307 | Permanent redirect with different method-preservation semantics |
| 302 | 307 | Temporary redirect with different method-preservation semantics |
| PUT | PATCH | Replacement vs partial modification |
| POST | PUT | Non-idempotent processing vs idempotent replacement semantics |
| HTTP/1.1 | HTTP/2 | Text-oriented HTTP/1.x framing vs binary multiplexed framing |
| HTTP/2 | HTTP/3 | TCP-based transport model vs QUIC-based transport |
| HTTP | HTTPS | HTTP semantics vs HTTP protected with TLS |
| CORS | CSRF | Browser cross-origin access control vs forged authenticated requests |
| Cookie | Session | Client-side state mechanism vs broader application state concept |
| Transfer-Encoding | Content-Encoding | Message transfer mechanism vs representation coding |
| URL fragment | Query | Fragment generally stays client-side; query is sent to the server |

---

## 103. Production Considerations

A production HTTP system requires more than correctly constructing a GET request.

It must account for:

- Timeouts
- Retries
- Connection pooling
- TLS verification
- Authentication
- Authorization
- Input validation
- Request-size limits
- Response-size limits
- Rate limiting
- Caching
- Compression
- Observability
- Error handling
- Security headers
- Proxy behavior
- Load balancing
- Protocol version negotiation
- Resource cleanup
- Concurrency
- Dependency failures

The HTTP protocol provides the foundation, while production engineering determines how that foundation is used safely and efficiently.

---

## 104. Central Mental Model

The most useful way to understand HTTP is not as a list of unrelated terms.

Think of an HTTP interaction as a structured exchange:

**The client identifies a target, chooses a method, provides metadata and optionally a body, and sends a request.**

**The server interprets the request, performs the appropriate operation, and returns a status, metadata, and optionally a representation.**

Around this basic exchange, additional mechanisms provide:

- Security through TLS
- State through cookies
- Efficiency through caching
- Conditional behavior through validators
- Content negotiation through Accept headers
- Redirection through 3xx responses
- Reliability through carefully designed retries
- Scalability through proxies, gateways, caching, and connection reuse
- Performance through HTTP/2 and HTTP/3
- Application behavior through APIs and resource semantics

The Python script demonstrates these mechanisms directly so that the relationship between HTTP concepts and actual transmitted data remains clear.
