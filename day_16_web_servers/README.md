# Web servers

## Introduction

A web server is software that receives HTTP requests and produces HTTP responses. Its responsibilities can range from serving static files to acting as a gateway between Internet clients and application servers.

A typical modern web architecture separates several concerns:

`Client → Reverse Proxy/Web Server → Application Server → Database`

The web server or reverse proxy forms the public-facing HTTP boundary. Static resources such as HTML, CSS, JavaScript, images, fonts, and downloadable files can often be served directly. Dynamic requests can be forwarded to an application server that executes business logic.

This separation improves maintainability, security, scalability, observability, and operational control.

The three implementations in this repository approach the subject from different perspectives:

- Python builds the concepts incrementally and includes a small working HTTP server.
- JavaScript uses Node.js to demonstrate asynchronous application handling, middleware-like processing, caching, and proxy behavior.
- C++ develops a more structured industry-style gateway case study using classes, interfaces between components, validation, load balancing, caching, failure handling, and operational statistics.

## Fundamental concepts

### HTTP

HTTP, or Hypertext Transfer Protocol, is the application-layer protocol commonly used for communication between web clients and servers.

A request normally contains:

- an HTTP method
- a target path or URL
- request headers
- an optional request body

A response normally contains:

- a status code
- response headers
- an optional response body

For example, a conceptual request is:

`GET /index.html`

A successful response might contain status `200`, a `Content-Type` header, and the contents of the requested document.

HTTP methods communicate the intended operation. Common methods include `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, and `OPTIONS`.

The examples in this repository primarily use `GET` because it makes the web-server and reverse-proxy concepts easy to isolate.

### HTTP status codes

Status codes communicate the result of a request.

Important examples include:

| Code | Meaning | Typical use |
|---|---|---|
| 200 | OK | Successful request |
| 201 | Created | Successful resource creation |
| 204 | No Content | Successful request without a response body |
| 301 | Moved Permanently | Permanent redirection |
| 302 | Found | Temporary redirection |
| 304 | Not Modified | Cached representation remains valid |
| 400 | Bad Request | Invalid request |
| 401 | Unauthorized | Authentication is required |
| 403 | Forbidden | Request is understood but refused |
| 404 | Not Found | Resource or route does not exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side failure |
| 502 | Bad Gateway | Proxy received an invalid upstream response or upstream failure |
| 503 | Service Unavailable | Service is temporarily unavailable |
| 504 | Gateway Timeout | Upstream did not respond within the gateway timeout |

The exact use of a status code depends on the architecture and semantics of the application.

## What a web server does

A web server can perform several responsibilities.

### Accept connections

The server listens on a network address and port. Conventional HTTP traffic uses port 80 and HTTPS commonly uses port 443.

A production server also manages:

- connection limits
- keep-alive connections
- request parsing
- TLS termination
- timeouts
- protocol versions
- worker processes or threads
- resource limits

### Parse HTTP

The server converts incoming bytes into structured HTTP requests.

A request contains information such as the method, path, headers, and body.

The Python implementation represents this concept using the `HttpRequest` dataclass.

The C++ implementation uses the `HttpRequest` structure.

### Route requests

A server decides what should handle a request.

Examples include:

- `/assets/app.js` → static file server
- `/images/logo.svg` → static file server
- `/api/users` → application server
- `/api/orders` → application server
- `/health` → health-check endpoint

Routing may happen at several layers.

### Serve static content

Static content does not require application code to calculate a result for every request.

Typical static resources include:

- HTML
- CSS
- JavaScript
- images
- fonts
- videos
- PDFs
- downloadable files

Static delivery can be highly optimized through caching, efficient file I/O, compression, content delivery networks, and operating-system mechanisms.

### Forward dynamic requests

A web server can forward requests to an application server.

For example:

`GET /api/users`

can travel through:

`Browser → Reverse Proxy → Application Server`

The application server might query a database, perform validation, execute business rules, and return JSON.

## Static files

Static file serving is one of the most fundamental web-server responsibilities.

A simple static-file request might be:

`GET /style.css`

The server maps the URL path to a file and sends the file contents with an appropriate media type.

Examples of media types include:

- `text/html`
- `text/css`
- `text/javascript`
- `application/json`
- `image/png`
- `image/jpeg`
- `image/svg+xml`
- `application/octet-stream`

The Python implementation uses `mimetypes.guess_type()` to determine a content type.

The JavaScript implementation uses a controlled MIME-type mapping.

The C++ implementation focuses on classifying static paths rather than reading arbitrary files.

## Static-file security

A static server must not blindly convert arbitrary URL strings into filesystem paths.

A dangerous request could attempt directory traversal:

`/../../secret.txt`

A safe implementation resolves the candidate path and verifies that the resulting filesystem location remains inside the configured document root.

The Python `StaticFileServer.resolve_safe_path()` method demonstrates this principle with `Path.resolve()` and `relative_to()`.

The JavaScript `StaticFileService.resolveSafePath()` performs an equivalent boundary check with `path.resolve()` and `path.relative()`.

The C++ case study deliberately avoids arbitrary filesystem access and treats static resources as controlled resources. This prevents the teaching implementation from becoming an unrestricted file server.

Other static-serving security considerations include:

- symbolic links
- encoded path separators
- percent-encoded traversal sequences
- hidden files
- file permissions
- unintended executable content
- MIME confusion
- directory listings
- sensitive configuration files
- backup files
- access-control rules

## Web server versus application server

The terms are related but describe different responsibilities.

A web server traditionally specializes in HTTP handling and static content. An application server executes application-specific logic.

In modern deployments, the boundary is not absolute. Many application frameworks contain HTTP servers, and many web servers can perform sophisticated routing and proxying.

The conceptual distinction remains useful:

| Component | Primary responsibility |
|---|---|
| Web server | HTTP handling and static delivery |
| Reverse proxy | Accept and forward client traffic |
| Application server | Execute application logic |
| Database | Persist application data |
| Cache | Reuse frequently accessed data |
| CDN | Distribute content geographically |
| Load balancer | Distribute traffic among servers |

## Application servers

An application server executes dynamic logic.

For example:

`GET /api/hello?name=Atul`

could be processed by application code that validates the name and constructs a response.

The Python `Application` class demonstrates route selection and query parsing.

The JavaScript `ApplicationServer` class performs the same conceptual role using asynchronous JavaScript.

The C++ `ApplicationServer` class provides a structured implementation with explicit validation and response construction.

Application-server responsibilities can include:

- authentication
- authorization
- input validation
- business rules
- database access
- transaction management
- serialization
- API responses
- background-job submission
- domain-specific calculations

## Reverse proxy

A reverse proxy is a server that receives requests from clients and forwards those requests to one or more backend servers.

The client communicates with the proxy rather than directly with the backend.

The conceptual architecture is:

`Client → Reverse Proxy → Backend`

The reverse proxy can provide a stable public endpoint while backend servers remain internal.

This creates an important architectural boundary.

A reverse proxy may perform:

- routing
- load balancing
- TLS termination
- access control
- request filtering
- rate limiting
- caching
- compression
- header manipulation
- observability
- health checking
- timeout enforcement

The Python `ReverseProxy`, JavaScript `ReverseProxy`, and C++ `ReverseProxy` classes all model these responsibilities.

## Reverse proxy versus forward proxy

A forward proxy generally acts on behalf of clients.

`Client → Forward Proxy → Internet Server`

A reverse proxy generally acts on behalf of servers.

`Internet Client → Reverse Proxy → Internal Server`

The direction of representation is the important conceptual distinction.

## Load balancing

When several application servers provide the same service, traffic can be distributed among them.

For example:

`Reverse Proxy → app-1`

`Reverse Proxy → app-2`

`Reverse Proxy → app-3`

The Python implementation uses round-robin selection.

The JavaScript implementation also selects among healthy backends.

The C++ implementation maintains a round-robin index and skips unhealthy backends.

### Round robin

Round robin distributes requests sequentially:

`app-1 → app-2 → app-3 → app-1 → app-2`

It is simple and predictable.

It does not automatically account for:

- backend CPU utilization
- memory pressure
- request cost
- connection count
- geographic distance
- application-specific workload

Other load-balancing approaches include:

- weighted round robin
- least connections
- least latency
- consistent hashing
- random selection
- hash-based routing

The appropriate strategy depends on workload and application architecture.

## Health checks

A proxy should avoid sending normal traffic to a backend known to be unavailable.

A health-check system may distinguish between:

- process is running
- port is accepting connections
- application is responding
- application dependencies are healthy

A health endpoint such as `/health` can provide an application-level signal.

The Python, JavaScript, and C++ implementations model backend health using a boolean state.

This is intentionally simpler than a real health-check system, but it demonstrates the central routing principle.

## Failure handling

Distributed systems must assume that components can fail.

A backend may:

- crash
- become overloaded
- stop responding
- return invalid data
- lose database connectivity
- become unreachable

The C++ case study demonstrates three situations:

1. all backends are healthy
2. one backend becomes unhealthy
3. all backends become unavailable

When no backend is healthy, the proxy returns `503 Service Unavailable`.

When a backend operation fails after selection, the proxy can produce a `502 Bad Gateway` response.

## Timeouts

A timeout limits how long one component waits for another.

Without appropriate timeouts, a slow dependency can consume threads, connections, memory, or event-loop capacity.

The JavaScript implementation provides `withTimeout()` to race an application operation against a timer.

The Python implementation discusses time measurement and production principles, while the C++ case study measures backend processing time.

Production timeout design commonly considers:

- connection timeout
- TLS handshake timeout
- request-header timeout
- request-body timeout
- upstream connection timeout
- upstream response timeout
- idle timeout

Timeout values should reflect real service-level requirements rather than arbitrary defaults.

## Retries

Retries can improve resilience when failures are temporary, but retries can also multiply load.

Suppose a proxy receives one request and retries a failed backend three times. A sudden failure can transform one incoming request into several backend requests.

Retries require careful consideration of:

- idempotency
- exponential backoff
- jitter
- maximum attempts
- timeout budgets
- failure classification

A `GET` request is generally easier to retry safely than a non-idempotent operation that creates a financial transaction.

## Caching

Caching stores reusable data so that future requests can avoid repeating expensive work.

A reverse proxy can cache eligible responses.

The Python implementation uses `ResponseCache`.

The JavaScript implementation uses `TTLCache`.

The C++ case study uses `ResponseCache` with an expiration time.

A cache entry contains a value and an expiration time.

The basic model is:

`request → cache lookup → hit or backend request`

A cache hit avoids backend work.

A cache miss requires the response to be generated and may then populate the cache.

Caching decisions require care. Personalized or security-sensitive responses should not be cached indiscriminately.

Important cache concepts include:

- TTL
- cache key
- freshness
- invalidation
- cache hit
- cache miss
- stale data
- cache-control directives
- private versus public responses

## Security headers

The examples add several common security headers.

`X-Content-Type-Options: nosniff` reduces certain MIME-sniffing behaviors.

`X-Frame-Options: DENY` prevents the document from being framed by browsers that honor the header.

`Referrer-Policy` controls referrer information.

`Content-Security-Policy` can restrict which resources a browser is permitted to load.

Security headers must be selected and configured according to the actual application. A restrictive policy can also break legitimate functionality if incorrectly configured.

## Request validation

A public server is a trust boundary.

Input must not automatically be considered safe because it arrived through HTTP.

The examples demonstrate validation for:

- request method
- request path
- path traversal
- name length
- body size

Production validation also commonly addresses:

- maximum URL length
- maximum header size
- content type
- JSON structure
- numeric ranges
- character encoding
- authentication
- authorization
- rate limits

Validation should occur before expensive processing.

## Headers

HTTP headers communicate metadata.

Request headers may include:

- `Host`
- `Accept`
- `Authorization`
- `Content-Type`
- `Content-Length`
- `User-Agent`
- `Cookie`

Proxy-related headers may include:

- `X-Forwarded-For`
- `X-Forwarded-Proto`
- `X-Forwarded-Host`

Modern deployments may also use the standardized `Forwarded` header.

Forwarded client information must be handled carefully. An application should not blindly trust arbitrary client-supplied forwarding headers when the network architecture does not establish which proxy is trusted.

## Python implementation

The Python script begins with explicit `HttpRequest` and `HttpResponse` structures.

The `StaticFileServer` class demonstrates:

- document roots
- path resolution
- traversal protection
- MIME detection
- `404 Not Found`
- `403 Forbidden`
- file-reading errors

The `Application` class demonstrates dynamic routing.

The `ReverseProxy` class demonstrates:

- backend selection
- health filtering
- round-robin distribution
- forwarding metadata
- upstream response handling
- backend identification

`ResponseCache` demonstrates TTL-based response reuse.

`add_security_headers()` demonstrates security-policy injection at the HTTP boundary.

`DemoRequestHandler` uses Python's standard-library `http.server` module to expose a real local HTTP endpoint.

The server is intentionally small. A production Internet-facing deployment requires significantly more operational and security controls.

### Running the Python implementation

Run:

`python web_servers.py`

The educational demonstrations execute immediately.

To start the real local HTTP server, set the environment variable `RUN_HTTP_SERVER=1`.

On Windows PowerShell:

`$env:RUN_HTTP_SERVER="1"; python web_servers.py`

The server listens on `127.0.0.1:8080`.

## JavaScript implementation

The JavaScript implementation uses Node.js built-in modules.

`ApplicationServer` demonstrates asynchronous application handling.

`StaticFileService` demonstrates:

- filesystem path resolution
- traversal protection
- MIME-type mapping
- asynchronous file access
- error classification

`TTLCache` demonstrates expiration-based caching.

`BackendServer` represents an individual application instance.

`ReverseProxy` coordinates the backend servers and performs:

- health-aware backend selection
- forwarding headers
- timeout handling
- caching
- error conversion
- backend identification

The JavaScript version is particularly useful for demonstrating event-driven server behavior. Node.js uses an event-driven architecture and can handle many I/O operations without assigning a dedicated thread to every request.

### Running the JavaScript implementation

Run:

`node web_servers.js`

The conceptual examples execute without opening a network port.

To start the HTTP server:

`RUN_HTTP_SERVER=1 node web_servers.js`

The server listens on `127.0.0.1:8080`.

## C++ case study

The C++ implementation models a gateway for a small application platform.

The system contains:

`Client → ReverseProxy → BackendServer instances`

The proxy also has access to a cache and static-resource service.

### Problem being modeled

An organization has an HTTP application that needs:

- multiple application instances
- static-resource delivery
- request routing
- backend health awareness
- caching
- request validation
- security headers
- failure handling
- operational statistics

Directly exposing every application server to clients would make the public architecture harder to control.

The reverse proxy therefore becomes the controlled entry point.

### Major components

`HttpRequest` represents an incoming HTTP request.

`HttpResponse` represents the result sent toward the client.

`ApplicationServer` implements dynamic application behavior.

`StaticResourceService` identifies static resources and models edge delivery.

`BackendServer` represents an application instance.

`ResponseCache` implements TTL-based caching.

`ReverseProxy` coordinates routing, validation, caching, backend selection, and failure handling.

`logRequest()` represents access logging.

### Request flow

A request enters the proxy.

The proxy first validates basic request properties.

If the request identifies a static resource, the static-resource component handles it.

Otherwise, a cache lookup may occur.

If there is no suitable cached response, the proxy selects a healthy backend.

The request is forwarded.

The backend produces a response.

The proxy adds security and routing metadata.

Eligible successful responses can enter the cache.

The final response is returned to the client.

### Backend failure

The case study deliberately changes backend health during execution.

When `app-2` becomes unhealthy, the proxy skips it.

When all backends become unhealthy, the proxy returns `503`.

When one backend is restored, requests can flow again.

This illustrates an important distributed-system principle: availability of the public endpoint depends on both the proxy and the health of the backend pool.

### C++ data structures

The backend pool uses `std::vector` because the system needs indexed round-robin selection.

The response cache uses `std::unordered_map` because cache keys require expected constant-time lookup.

`std::shared_ptr` is used to represent shared ownership of the application-server object in this compact case study.

`std::optional` represents the possibility that a cache lookup or backend selection produces no result.

## Important distinctions

### Static versus dynamic content

Static content can usually be delivered without executing application business logic.

Dynamic content depends on request information and application state.

Static:

`/assets/site.css`

Dynamic:

`/api/orders/123`

Static resources are often suitable for aggressive caching.

Dynamic responses require more careful caching decisions.

### Web server versus reverse proxy

A web server can directly serve content.

A reverse proxy receives requests on behalf of other servers and forwards them.

The same software product can perform both roles.

The distinction is based on function, not necessarily product name.

### Reverse proxy versus load balancer

A reverse proxy forwards requests.

A load balancer distributes requests among multiple servers.

A reverse proxy can therefore perform load-balancing functions, but the concepts are not identical.

### Proxy versus application server

A proxy generally should not need to implement domain business rules.

An application server should not normally be responsible for every concern of the public network boundary.

Separating these roles can make systems easier to operate and scale.

## Edge cases

Important edge cases include:

- nonexistent static files
- malformed paths
- traversal attempts
- unsupported methods
- oversized request bodies
- oversized query parameters
- missing headers
- unhealthy backends
- all backends unavailable
- expired cache entries
- backend timeouts
- invalid upstream responses
- cache keys containing user-specific data
- partially failed deployments

A production implementation must also account for malformed HTTP messages, slow clients, connection exhaustion, TLS failures, resource exhaustion, and dependency failures.

## Common mistakes

### Treating every request as application traffic

Serving static files through application code can waste application-server resources.

### Exposing backend servers unnecessarily

A reverse proxy is often used so internal application servers do not need to be directly exposed to the public network.

### Ignoring path traversal

A URL-to-filesystem mapping without boundary validation can expose files outside the intended document root.

### Caching everything

Caching an authenticated or personalized response as a public response can create serious information-disclosure problems.

### Retrying without limits

Unbounded retries can amplify an outage.

### Trusting forwarded headers blindly

Headers such as `X-Forwarded-For` should only be trusted according to the known proxy topology.

### Missing timeouts

A permanently waiting upstream request can consume resources indefinitely.

### Logging secrets

Access logs should not contain passwords, authentication tokens, session secrets, or unnecessary personal data.

### Using development servers in production

Development HTTP servers are designed for development and testing, not necessarily for Internet-scale production traffic.

## Performance considerations

Web-server performance depends on more than raw CPU speed.

Important variables include:

- network latency
- bandwidth
- request rate
- concurrency
- payload size
- TLS overhead
- connection reuse
- file-system performance
- application latency
- database latency
- cache hit ratio
- memory usage
- compression cost

Static assets can often be served more efficiently than dynamically generated responses.

Caching can reduce backend workload.

Connection reuse reduces repeated connection setup.

Load balancing can distribute work among multiple instances.

The Python benchmark is intentionally limited. It measures local function execution rather than actual network throughput.

The JavaScript implementation demonstrates an event-driven model but does not attempt to benchmark Node.js itself.

The C++ program reports architectural complexity and backend counts rather than claiming a particular production throughput.

Real performance measurements require representative workloads and controlled benchmarking.

## Complexity

For a backend pool of `N` servers, the C++ health-aware selection scans up to `N` entries in the worst case.

Therefore its worst-case selection complexity is `O(N)`.

The round-robin index itself is constant-time, but finding a healthy backend can require scanning the pool.

The cache uses `std::unordered_map`, whose expected lookup complexity is `O(1)`.

The Python and JavaScript cache structures similarly provide average constant-time key lookup under normal hash-table behavior.

Complexity alone does not determine production performance. Network I/O, memory allocation, serialization, TLS, operating-system scheduling, storage, and dependency latency can dominate execution time.

## Security considerations

A production web architecture should consider:

- HTTPS/TLS
- certificate management
- secure cookie attributes
- authentication
- authorization
- request-size limits
- rate limiting
- input validation
- path traversal
- MIME handling
- security headers
- CORS configuration
- CSRF protections where applicable
- SSRF protections where server-side URL fetching exists
- secret management
- access logging
- audit logging
- dependency security
- container and host isolation
- least privilege
- network segmentation

A reverse proxy can provide an important security boundary, but it does not replace application-level security.

Authentication and authorization must remain appropriate to the application's actual trust model.

## Production considerations

A production web-server architecture commonly needs:

- multiple application instances
- automated health checks
- controlled deployment procedures
- centralized logs
- metrics
- distributed tracing
- alerting
- TLS
- resource limits
- graceful shutdown
- connection management
- timeout policies
- controlled retry policies
- cache policies
- backup and recovery procedures
- capacity planning

A mature architecture often separates concerns into layers:

`Internet`

`↓`

`DNS`

`↓`

`CDN / Edge`

`↓`

`Reverse Proxy / Load Balancer`

`↓`

`Web Server / Static Content`

`↓`

`Application Servers`

`↓`

`Cache / Database / External Services`

The exact arrangement varies according to application requirements.

## Observability

The Python implementation logs method, path, status, and duration.

The JavaScript implementation emits structured JSON-style request information.

The C++ case study records the backend and cache state.

Useful production measurements include:

- request count
- request rate
- latency
- percentile latency
- error rate
- status-code distribution
- active connections
- cache hit ratio
- backend health
- CPU utilization
- memory utilization
- network throughput

Percentiles such as p50, p95, and p99 are often more informative than an arithmetic average because they reveal tail latency.

## Why the three languages demonstrate different aspects

Python makes architectural concepts easy to express because the standard library provides concise HTTP, filesystem, networking, timing, and data-structure APIs.

JavaScript demonstrates asynchronous server-side programming and event-driven I/O. Its `async` and `await` syntax makes asynchronous application and proxy operations explicit.

C++ makes system structure, ownership, data structures, explicit types, exceptions, and performance considerations more visible. The case study therefore emphasizes architectural modeling and implementation decisions.

The three implementations are intentionally related but not identical. Each illustrates the same web-server architecture through the strengths of its language and runtime.

## Practical applications

The concepts demonstrated here apply to:

- REST APIs
- web applications
- e-commerce platforms
- financial applications
- content platforms
- SaaS systems
- internal enterprise applications
- microservices
- static websites
- mobile application backends
- distributed services
- media delivery
- cloud-hosted applications

A small website may need only a web server and static files.

A large application may require several layers of reverse proxies, load balancers, application servers, caches, databases, queues, and observability systems.

The fundamental request flow remains the same:

`Client request → HTTP boundary → routing → application/static handling → HTTP response`

The architecture becomes more sophisticated as requirements for availability, performance, security, and scale increase.
