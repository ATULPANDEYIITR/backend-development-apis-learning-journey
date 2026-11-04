# CORS: Cross-Origin Resource Sharing

## 1. Technical Scope

Cross-Origin Resource Sharing (CORS) is an HTTP-based mechanism that allows a web server to specify which browser origins can access its resources through cross-origin requests.

CORS extends the browser's Same-Origin Policy (SOP). It provides controlled exceptions to restrictions that would otherwise prevent JavaScript executing on one origin from accessing responses from another origin.

The implementations cover four connected areas:

1. Same-Origin Policy and origin identification.
2. Simple requests and preflight requests.
3. Allowed origins, methods and request headers.
4. Credential handling and security enforcement.

The implementations also demonstrate policy evaluation, caching, auditing, validation and enterprise configuration management.

## 2. Same-Origin Policy

The Same-Origin Policy is a browser security mechanism that restricts interactions between documents and resources belonging to different origins.

An origin is determined by three components:

- Scheme: HTTP or HTTPS.
- Host: Domain name or IP address.
- Port: Effective port number.

Two URLs have the same origin when all three components match after applicable default-port normalization.

| URL A | URL B | Same origin |
|---|---|---|
| `https://app.example.com/page1` | `https://app.example.com/page2` | Yes |
| `https://app.example.com` | `http://app.example.com` | No |
| `https://app.example.com` | `https://api.example.com` | No |
| `https://app.example.com` | `https://app.example.com:8443` | No |
| `http://localhost:5173` | `http://localhost:8000` | No |

A different path does not create a different origin. A different scheme, host or port does.

### 2.1 SOP and CORS distinction

SOP establishes the browser's cross-origin restrictions. CORS allows a server to communicate its cross-origin access policy through HTTP response headers.

CORS does not disable SOP. It defines which cross-origin responses a browser may expose to requesting JavaScript.

Important distinctions:

- Cross-origin embedding is not universally prohibited.
- Cross-origin navigation is generally permitted.
- Some cross-origin requests can be transmitted without granting JavaScript access to their responses.
- CORS controls browser access to responses; it is not a replacement for authentication or authorization.
- Non-browser clients are not automatically subject to browser CORS enforcement.

A server must independently authenticate users, authorize operations and validate incoming data.

## 3. CORS Request Classification

CORS requests are commonly divided into simple requests and requests requiring preflight.

### 3.1 Simple requests

A simple cross-origin request does not require a preliminary OPTIONS request.

The main conditions are:

| Property | Requirement |
|---|---|
| Method | GET, HEAD or POST |
| Author-defined request headers | Restricted to CORS-safelisted headers |
| Content-Type | Restricted to approved safelisted media types |
| Other restrictions | Safelisted header values must satisfy browser restrictions |

The safelisted Content-Type values are:

- `application/x-www-form-urlencoded`
- `multipart/form-data`
- `text/plain`

A request containing an `Authorization` header is not a simple request.

A POST request using `application/json` also requires preflight because that media type is not CORS-safelisted.

A simple request is not automatically authorized by the server. The server still processes authentication, authorization, validation and application-level security.

### 3.2 Preflight requests

A preflight request is an HTTP OPTIONS request automatically issued by the browser before certain cross-origin requests.

It asks whether the proposed request is permitted.

Example request:

| Header | Example value |
|---|---|
| Origin | `https://app.example.com` |
| Access-Control-Request-Method | `POST` |
| Access-Control-Request-Headers | `authorization, content-type` |

The server evaluates:

1. Whether the requesting origin is allowed.
2. Whether the requested method is permitted.
3. Whether the requested headers are permitted.
4. Whether credential-related restrictions are satisfied.
5. Whether additional private-network restrictions apply.

A successful preflight response can contain:

| Response header | Purpose |
|---|---|
| `Access-Control-Allow-Origin` | Identifies the permitted origin |
| `Access-Control-Allow-Methods` | Lists permitted methods |
| `Access-Control-Allow-Headers` | Lists permitted request headers |
| `Access-Control-Allow-Credentials` | Allows credentialed browser access |
| `Access-Control-Max-Age` | Specifies the preflight cache duration |
| `Vary: Origin` | Separates cache variants by requesting origin |

A successful preflight response normally uses HTTP status `204 No Content` or another successful 2xx response.

Preflight authorization does not itself execute the requested application operation. The browser sends the actual request separately.

### 3.3 Preflight processing sequence

    Browser application
          |
          | Cross-origin request requiring preflight
          v
    OPTIONS request
          |
          v
    Server CORS policy
          |
          +---- Origin validation
          |
          +---- Method validation
          |
          +---- Header validation
          |
          +---- Credential restrictions
          |
          v
    Preflight response
          |
          +---- Denied: Browser blocks actual request
          |
          +---- Allowed: Browser may send actual request
                              |
                              v
                        Actual request
                              |
                              v
                        Server processing
                              |
                              v
                        CORS response headers
                              |
                              v
                        Browser exposes response

## 4. Allowed Origins

An allowed origin identifies a browser origin that the server permits to access its resources.

An explicit allowlist is preferable for production applications.

Example configuration:

| Origin | Environment | Policy |
|---|---|---|
| `https://app.example.com` | Production | Allowed |
| `https://admin.example.com` | Production | Allowed |
| `http://localhost:5173` | Development | Allowed only in development |
| `https://attacker.example.net` | Untrusted | Denied |

### 4.1 Exact origin matching

Origin comparison must consider:

- Scheme.
- Hostname.
- Port.
- Default-port normalization.
- Invalid origin syntax.
- Opaque origins such as `null`.

The Python, C++ and Java implementations normalize origins before comparison. The JavaScript implementation uses the standard URL parser.

Origin validation should not use substring matching.

For example, accepting every origin containing `example.com` could accidentally authorize:

`https://example.com.attacker.net`

A valid allowlist comparison must use normalized origin values.

### 4.2 Wildcard origins

The response:

`Access-Control-Allow-Origin: *`

allows browser access from any origin for requests that do not use credentials.

A wildcard is unsuitable for credentialed CORS requests.

When credentials are permitted, the server must return the specific validated origin rather than `*`.

Wildcard origins should not be used as a substitute for environment-specific configuration.

### 4.3 Dynamic origin selection

Applications serving several approved frontend domains may evaluate the incoming Origin against an allowlist.

The server must never blindly reflect the incoming Origin header.

A secure process is:

1. Read the Origin header.
2. Validate its syntax.
3. Normalize the origin.
4. Compare it against approved origins.
5. Return the exact validated origin.
6. Reject unauthorized origins.

When responses vary by origin, `Vary: Origin` helps prevent shared caches from incorrectly reusing one origin's response for another.

## 5. Allowed Methods and Headers

### 5.1 Access-Control-Allow-Methods

This response header identifies methods that the browser may use in the cross-origin request.

Example:

`Access-Control-Allow-Methods: GET, POST, PUT, DELETE`

The method requested in the preflight must be permitted by the server policy.

The server should also enforce its normal application-level method restrictions.

### 5.2 Access-Control-Allow-Headers

This response header identifies non-safelisted request headers that the browser is permitted to send.

Example:

`Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID`

The preflight request communicates the requested header names through:

`Access-Control-Request-Headers`

The server compares those names against its allowed-header policy.

Header names are case-insensitive. Policy implementations normalize them to lowercase.

CORS does not permit arbitrary browser access to every HTTP header. Browser-managed forbidden request headers remain subject to browser restrictions.

### 5.3 Access-Control-Expose-Headers

Browsers expose only a defined set of response headers to cross-origin JavaScript by default.

The server can explicitly expose additional response headers:

`Access-Control-Expose-Headers: X-Request-ID`

This permits application JavaScript to inspect the specified response header.

It does not grant permission to send that header in a request. Request-header permission and response-header exposure are separate mechanisms.

## 6. Credentials

Credentials include browser-managed authentication information such as:

- Cookies.
- HTTP authentication information.
- Client certificates.

JavaScript Fetch and XMLHttpRequest use explicit credential settings to control whether credentials are included in cross-origin requests.

For Fetch, the relevant modes are:

| Mode | Behavior |
|---|---|
| `omit` | Never send credentials |
| `same-origin` | Send credentials only for same-origin requests |
| `include` | Include credentials for cross-origin requests when browser security rules permit |

A credentialed CORS response requires:

`Access-Control-Allow-Credentials: true`

The allowed origin must be an explicit origin, not `*`.

### 6.1 Credentialed request requirements

A typical credentialed CORS response uses:

- `Access-Control-Allow-Origin` with the exact approved origin.
- `Access-Control-Allow-Credentials: true`.

The server must also configure cookie attributes correctly.

Relevant cookie attributes include:

| Attribute | Security purpose |
|---|---|
| Secure | Restricts transmission to secure connections |
| HttpOnly | Prevents JavaScript from reading the cookie |
| SameSite | Controls cross-site cookie sending behavior |
| Path | Restricts the cookie's applicable request paths |
| Domain | Defines applicable hosts |

Cross-site cookies generally require `SameSite=None; Secure`.

CORS does not override browser third-party-cookie restrictions or SameSite rules.

CORS is also not a CSRF protection mechanism. Credentialed applications need appropriate CSRF defenses.

## 7. Preflight Caching

`Access-Control-Max-Age` specifies how long a successful preflight result may be cached by the browser.

Example:

`Access-Control-Max-Age: 600`

This requests a cache duration of 600 seconds, subject to browser-imposed limits.

Caching reduces repeated OPTIONS requests.

A preflight cache decision depends on the relevant origin, requested method, requested headers and credential-related context.

The implementations use composite cache keys to prevent unrelated preflight decisions from sharing authorization results.

Policy changes must invalidate or version relevant cached decisions. Browser caches may continue using previously cached results until their expiration or browser-specific invalidation.

The Java implementation includes policy versions in its cache key.

The Python, JavaScript and C++ implementations maintain bounded-lifetime in-memory decisions.

## 8. Python Implementation

The Python file models CORS as a policy evaluation system.

### 8.1 Domain objects

| Component | Responsibility |
|---|---|
| `Origin` | Parses and normalizes origins |
| `CorsPolicy` | Stores allowed origins, methods and headers |
| `CorsRequest` | Represents an incoming request |
| `CorsResponse` | Represents an authorization decision |
| `PreflightCache` | Stores successful preflight decisions |
| `CorsEngine` | Executes policy evaluation |

### 8.2 Evaluation workflow

The `CorsEngine.process()` method:

1. Validates the HTTP method.
2. Determines whether CORS processing is required.
3. Validates and normalizes the origin.
4. Checks credential permission.
5. Identifies OPTIONS preflight requests.
6. Validates requested methods and headers.
7. Evaluates private-network permission.
8. Creates appropriate response headers.
9. Records the decision in the audit log.

### 8.3 Validation and failure handling

The implementation rejects:

- Malformed origins.
- Unsupported schemes.
- Unauthorized origins.
- Unauthorized methods.
- Unapproved request headers.
- Credentialed requests under a non-credentialed policy.
- Wildcard origins combined with credentials.

The demonstration includes assertions for normalization, wildcard restrictions and simple-request classification.

The script uses only the Python standard library.

### 8.4 Performance

Origin and method allowlists use sets for average constant-time membership checks.

The preflight cache uses dictionary lookups.

Expired entries are removed when accessed. A production implementation should also introduce periodic cache cleanup and a bounded cache size.

## 9. JavaScript Implementation

The JavaScript implementation models a Node.js HTTP gateway.

It uses the Node.js HTTP and URL modules instead of external dependencies.

### 9.1 Architectural components

| Component | Responsibility |
|---|---|
| `CorsPolicy` | Validates gateway configuration |
| `PreflightCache` | Manages preflight expiration |
| `CorsGateway` | Evaluates incoming HTTP requests |
| `normalizeOrigin()` | Canonicalizes origin values |
| `parseTokenList()` | Validates requested header tokens |
| HTTP server | Exposes application endpoints |

### 9.2 Event-driven request handling

The gateway evaluates CORS before application route execution.

The middleware:

1. Evaluates the incoming request.
2. Writes the applicable CORS headers.
3. Rejects denied requests.
4. Terminates OPTIONS requests.
5. Passes permitted actual requests to application routes.

The application exposes:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/data` | GET | Returns sample application data |
| `/api/data` | POST | Accepts a JSON record |

The POST endpoint handles streamed request bodies and rejects malformed JSON.

### 9.3 Operational considerations

The implementation includes:

- UUID-based request identifiers in audit records.
- A bounded in-memory audit collection.
- Preflight cache expiration.
- HTTP server error handling.
- Graceful shutdown.
- JSON response formatting.
- A request body size limit.

The credential demonstration uses a custom `x-demo-credentials` header to simulate a policy input. It is not a browser's native credential mode and must not be interpreted as an actual browser credential implementation.

For a real HTTP gateway, credential behavior should be derived from the application's authentication configuration and the applicable request context.

## 10. C++17 Implementation

The C++ implementation provides a repository-independent policy evaluation engine for a realistic API gateway scenario.

### 10.1 Domain modeling

| Type | Responsibility |
|---|---|
| `Origin` | Represents a normalized origin |
| `Request` | Stores request attributes |
| `Response` | Stores the decision and response headers |
| `CorsPolicy` | Defines access rules |
| `AuditRecord` | Stores evaluation outcomes |
| `CorsGateway` | Enforces policy decisions |
| `Decision` | Enumerates authorization outcomes |

The implementation uses STL sets for allowlists and an ordered map for cached decisions.

### 10.2 Policy evaluation

The gateway distinguishes:

- Origin rejection.
- Method rejection.
- Header rejection.
- Credential rejection.
- Invalid requests.
- Private-network rejection.
- Successful authorization.

The preflight cache uses a composite key containing:

- Normalized origin.
- Requested method.
- Requested header set.
- Credential state.
- Private-network state.

This avoids reusing an authorization decision for a different request context.

### 10.3 Complexity considerations

Let:

- \(O\) represent the number of configured origins.
- \(M\) represent the number of allowed methods.
- \(H\) represent the number of allowed headers.
- \(R\) represent the number of requested headers.

Using ordered STL sets and maps:

| Operation | Typical complexity |
|---|---|
| Origin membership | \(O(\log O)\) |
| Method membership | \(O(\log M)\) |
| Individual header membership | \(O(\log H)\) |
| Preflight header validation | \(O(R\log H)\) |
| Cache lookup | \(O(\log C)\) |
| Audit insertion | Amortized \(O(1)\) |

Here, \(C\) is the number of cached decisions.

The implementation demonstrates policy behavior without opening a network socket. A production gateway would integrate this engine with an HTTP server and secure request parsing.

## 11. Java 17 Implementation

The Java implementation provides an enterprise-oriented governance service with immutable policy configuration and concurrent operational state.

### 11.1 Enterprise domain types

Java records model immutable request, response, audit and cache values.

The policy object defines:

- Policy identifier.
- Policy version.
- Allowed origins.
- Allowed methods.
- Allowed headers.
- Exposed response headers.
- Credential permission.
- Private-network permission.
- Preflight cache duration.
- Policy activation status.

### 11.2 Policy lifecycle

The `PolicyStatus` enumeration defines:

| State | Meaning |
|---|---|
| DRAFT | Configuration is being prepared |
| ACTIVE | Configuration is available for evaluation |
| DISABLED | Configuration cannot authorize requests |
| RETIRED | Configuration is no longer in service |

The demonstration uses an active policy.

A production policy-management service would control transitions, permissions, approvals and audit history independently of request evaluation.

### 11.3 Concurrency and auditability

The service uses:

- `ConcurrentHashMap` for concurrent preflight cache operations.
- `Collections.synchronizedList` for audit event storage.
- `AtomicLong` for decision counters.
- Immutable records for request and response data.
- Policy versioning to distinguish cache decisions from different configurations.

This design separates immutable policy configuration from mutable operational state.

### 11.4 Enterprise failure states

The service handles:

- Disabled policies.
- Invalid origins.
- Unauthorized origins.
- Unsupported methods.
- Unapproved headers.
- Credential policy violations.
- Private-network restrictions.
- Expired cache entries.

The cache key includes the policy version, preventing a cached decision from one policy version from being reused under another version.

The demonstration is a policy service, not a complete servlet or Spring Boot HTTP filter. Production deployment would connect the evaluation service to an HTTP request pipeline.

## 12. PostgreSQL Implementation

The SQL implementation models a relational CORS governance system.

It separates configuration, runtime requests and reporting.

### 12.1 Database relationship

    Applications
         |
         v
    CORS Policies
         |
         +---- Allowed Origins
         |
         +---- Allowed Methods
         |
         +---- Allowed Headers
         |
         +---- Exposed Headers
         |
         v
    CORS Requests
         |
         +---- Requested Headers
         |
         +---- Decision
         |
         +---- Response Status
         |
         +---- Decision Reason
         |
         v
    Reporting Views

A separate preflight cache table stores successful preflight authorization contexts.

### 12.2 Table responsibilities

| Table | Purpose |
|---|---|
| `applications` | Identifies applications and environments |
| `cors_policies` | Stores versioned CORS configurations |
| `allowed_origins` | Stores approved origins |
| `allowed_methods` | Stores permitted HTTP methods |
| `allowed_headers` | Stores permitted request headers |
| `exposed_headers` | Stores readable response headers |
| `cors_requests` | Stores request decisions |
| `requested_headers` | Stores requested header names |
| `preflight_cache` | Stores preflight cache records |

### 12.3 Database integrity

The database uses:

- Primary keys for entity identity.
- Foreign keys for policy relationships.
- Unique constraints to prevent duplicate configuration.
- Check constraints for policy values.
- Generated columns for wildcard identification.
- Constraint triggers for wildcard and credential consistency.
- Indexes for origin lookup, policy decisions and request reporting.

The `normalize_origin()` function performs database-level origin normalization and validation.

The `enforce_cors_policy_integrity()` constraint trigger prevents a wildcard origin from being combined with credential permission.

### 12.4 Evaluation function

`evaluate_cors_request()` evaluates:

1. Active policy availability.
2. Origin validity.
3. Origin allowlist membership.
4. Credential permission.
5. Private-network permission.
6. Preflight method permission.
7. Preflight header permission.
8. Actual HTTP method permission.

It returns a structured decision, HTTP status, allowed origin and reason.

### 12.5 Request logging procedure

`log_cors_request()` executes the evaluation function and persists the result.

It records:

- Application.
- Active policy.
- Original and normalized origin.
- HTTP method.
- Request type.
- Requested method.
- Credential state.
- Private-network state.
- Authorization decision.
- HTTP response status.
- Decision reason.
- Request processing duration.

Requested headers are maintained in a separate relational table.

### 12.6 Reporting and analytics

The `cors_request_report` view joins application metadata with request decisions.

The `cors_policy_eligibility` view evaluates policy configuration.

The supplied queries demonstrate:

- Request retrieval.
- Policy configuration validation.
- Decision aggregation.
- Average processing duration.
- Preflight evaluation.
- Rejected-origin analysis.
- Expired cache cleanup.

The database script requires PostgreSQL with support for generated columns, identity columns, JSONB and constraint triggers. The UUID generation function uses `gen_random_uuid()`.

The database models preflight cache records separately from the runtime in-memory caches. The SQL evaluation function does not automatically insert cache entries.

## 13. Security Considerations

### 13.1 CORS is not authentication

An allowed origin does not establish the identity of the user.

The server must independently verify authentication credentials and enforce authorization rules.

### 13.2 CORS is not authorization for non-browser clients

A command-line HTTP client, server-to-server application or malicious program can send an arbitrary Origin header.

CORS enforcement is primarily a browser security mechanism.

An API must not rely on CORS to prevent unauthorized direct HTTP requests.

### 13.3 Credentialed CORS

Credentialed requests require explicit origin permission and the correct credential response header.

Avoid broad credentialed origin policies.

Use secure cookie attributes, appropriate CSRF protection and application-level authorization.

### 13.4 Origin reflection

Never automatically copy an incoming Origin value into `Access-Control-Allow-Origin`.

Only return an origin after validating it against an explicit policy.

### 13.5 HTTP caching

Responses that depend on Origin should generally include:

`Vary: Origin`

This prevents shared caches from treating responses for different origins as interchangeable.

### 13.6 Preflight and actual request authorization

A successful preflight does not guarantee that the actual request will succeed.

The actual request must still undergo application-level validation and authorization.

### 13.7 Private network access

Private Network Access introduces additional browser security considerations for requests targeting private network resources.

Where applicable, the server must explicitly evaluate the relevant request headers and private-network policy.

Allowing private-network requests should require a deliberate security decision rather than a broad default.

### 13.8 Audit data

CORS logs should support detection of:

- Repeated unauthorized origins.
- Unexpected methods.
- Suspicious request headers.
- Credential policy violations.
- Unexpected changes in origin distribution.
- Abnormal preflight volumes.

Avoid recording cookies, authorization tokens, session identifiers or other sensitive credential values.

## 14. Implementation Comparison

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Primary perspective | Policy simulation | HTTP gateway | Governance engine | Enterprise policy service | Relational governance |
| Origin validation | Custom parser | URL parser | Custom parser | URI parser | SQL function |
| Preflight evaluation | Yes | Yes | Yes | Yes | Yes |
| Credential policy | Yes | Yes | Yes | Yes | Yes |
| Cache | Dictionary | Map | Ordered map | Concurrent map | Cache table |
| Audit | List | Bounded array | Vector | Concurrent collection | Relational records |
| Policy versioning | No | No | No | Yes | Yes |
| Network server | No | Yes | No | No | No |

## 15. Limitations and Production Boundaries

These implementations are educational policy engines and examples of CORS processing. They are not interchangeable with a complete production browser security implementation.

Important boundaries:

- Browsers implement the actual Same-Origin Policy and CORS protocol.
- Browser-specific preflight cache behavior may differ from application-level caches.
- The examples do not reproduce every Fetch specification validation rule.
- The JavaScript gateway uses a demonstration credential flag rather than native browser credential metadata.
- The C++ program models decisions but does not implement an HTTP server.
- The Java program models enterprise governance but does not provide a complete servlet integration.
- The SQL procedure records policy decisions but is not an HTTP gateway.
- In-memory audit collections require durable storage and retention controls in production.
- Origin parsing should use a rigorously tested standards-compliant implementation when handling arbitrary internet input.
- Reverse proxies, API gateways and application servers must avoid conflicting CORS configurations.

The central architectural distinction remains:

**SOP defines browser cross-origin restrictions. CORS communicates server-approved cross-origin access. Preflight validates certain proposed requests before transmission. Allowed origins, methods and headers define policy boundaries. Credential settings control cross-origin credentialed access.**
