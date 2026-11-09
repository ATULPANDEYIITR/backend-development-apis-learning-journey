# Secure API Project

## Project Description

This project implements a secure API architecture covering authentication, authorization, access control, token lifecycle management, request validation, rate limiting, resource ownership, and security auditing.

The implementations demonstrate how security controls operate together during an API request, from identity verification to the final access decision.

The project uses five independent implementations:

| File | Implementation | Primary Engineering Focus |
|---|---|---|
| `secure_api.py` | Python | Authentication services, token validation, RBAC, auditing and API simulation |
| `secure_api.js` | JavaScript | Asynchronous authentication, event-driven auditing and security middleware |
| `secure_api.cpp` | C++17 | Security decision engine and policy evaluation |
| `SecureApi.java` | Java 17 | Enterprise security services, domain modeling and explicit state transitions |
| `secure_api.sql` | PostgreSQL | Relational security architecture, integrity constraints, authorization queries and audit reporting |

Each implementation operates independently. They demonstrate related security principles through different programming and data-management approaches.

## 1. Secure API Architecture

A Secure API is an application programming interface designed to prevent unauthorized access, protect sensitive information, validate incoming requests, and maintain accountability for operations.

An API commonly exposes operations through HTTP methods:

| HTTP Method | Typical Operation | Example |
|---|---|---|
| GET | Retrieve information | Read user records |
| POST | Create information | Register a user |
| PUT | Replace an existing resource | Update a complete profile |
| PATCH | Partially modify a resource | Change an account setting |
| DELETE | Remove a resource | Delete an authorized record |

An endpoint should not automatically grant access simply because a request uses a valid HTTP method or reaches a valid URL.

Every protected operation must be evaluated against its authentication requirements, permissions, resource restrictions, and security policies.

### Security request lifecycle

The implementations follow this general sequence:

    Client Request
         |
         v
    Request Validation
         |
         v
    Rate Limit Evaluation
         |
         v
    Authentication
         |
         v
    Account Status Verification
         |
         v
    Token Validation
         |
         v
    Authorization
         |
         v
    Resource Ownership Check
         |
         v
    API Operation
         |
         v
    Security Audit
         |
         v
    HTTP Response

A request is rejected as soon as a mandatory security condition fails.

Authentication and authorization are separate decisions. A successfully authenticated user can still receive HTTP 403 when the required permission is unavailable.

## 2. Authentication

Authentication establishes the identity of the entity making an API request.

The API must verify that the supplied credentials correspond to a valid account before issuing an authenticated session or access token.

### 2.1 Username and password authentication

The Python, JavaScript, and Java implementations include password-hashing mechanisms.

Passwords must never be stored as readable plaintext.

The password verification workflow is:

1. The user submits a username and password.
2. The application retrieves the corresponding account.
3. The stored salt is retrieved.
4. The password-hashing function derives a candidate hash.
5. The candidate hash is compared with the stored hash.
6. Authentication succeeds only when the account is active and the hashes match.

The implementations use PBKDF2 with HMAC-SHA256 and independently generated random salts.

PBKDF2 repeatedly applies a cryptographic derivation operation to make password guessing more computationally expensive.

| Term | Meaning |
|---|---|
| Plaintext password | Original password supplied by the user |
| Salt | Random value used during password derivation |
| Password hash | Derived representation stored for verification |
| Iteration count | Number of derivation iterations |
| Password verification | Comparison of newly derived and stored hashes |

The PostgreSQL implementation stores `password_hash` and `password_salt`. Password derivation is performed by the application rather than by a database password field.

For production deployments, password hashing parameters should be reviewed against current security guidance. Argon2id is a suitable alternative where supported.

### 2.2 Password validation

The application implementations enforce password complexity requirements.

The demonstration policy requires:

- At least 12 characters.
- At least one uppercase character.
- At least one lowercase character.
- At least one numeric character.
- At least one special character.
- A maximum length of 256 characters.

Password complexity checks do not replace compromised-password screening, secure password recovery, multi-factor authentication, or account protection.

### 2.3 Authentication failures

Invalid credentials must not reveal whether the username or password was incorrect.

The implementations use generic credential failure messages.

Failed authentication attempts are tracked to demonstrate account-abuse protection.

Production implementations should combine throttling, progressive delays, account recovery controls, monitoring, and appropriate multi-factor authentication.

## 3. Access Tokens

An access token represents an authenticated session or authorization credential.

After successful authentication, the application issues a token that the client presents with subsequent protected requests.

The examples use HMAC-SHA256 signatures.

### 3.1 Token structure

The demonstration token contains:

| Field | Purpose |
|---|---|
| `sub` | Subject or user identifier |
| `iat` | Token issue time |
| `exp` | Token expiration time |
| `jti` | Unique token identifier |
| `roles` | Role information associated with issuance |

The token contains a signed payload. The signature allows the server to detect unauthorized modifications.

The demonstration token format is educational and is not a replacement for a standards-compliant OAuth 2.0 or OpenID Connect implementation.

Production deployments should use an established token format and maintained security libraries, with explicit issuer, audience, algorithm, key-rotation, and claim-validation policies.

### 3.2 Bearer authentication

Protected requests carry an access token in the HTTP authorization header.

The expected format is:

`Authorization: Bearer <access_token>`

The API validates the token before executing protected operations.

A bearer token must be treated as a credential. Anyone possessing an active token may be able to exercise its associated privileges.

Therefore:

- Always use HTTPS.
- Do not expose tokens in application logs.
- Do not place tokens in URLs.
- Use short access-token lifetimes.
- Store signing keys outside source control.
- Rotate cryptographic keys.
- Revoke tokens when necessary.

### 3.3 Token expiration and revocation

Expiration establishes the maximum validity period of a token.

Revocation invalidates a token before its expiration time.

These are different mechanisms.

| Mechanism | Purpose |
|---|---|
| Expiration | Automatically ends validity after a defined time |
| Revocation | Explicitly invalidates a previously issued token |
| Account deactivation | Prevents further authentication by an account |
| Account suspension | Temporarily restricts account access |
| Token verification | Checks token integrity and validity |

The Python and JavaScript implementations maintain revoked-token collections.

The Java implementation maintains token records and revocation state.

The PostgreSQL implementation stores token hashes, token status, issue time, expiration time, and revocation time.

A production distributed API should use shared token-revocation storage or another suitable centralized session-management mechanism. An in-memory revocation set is insufficient when multiple application instances must share revocation state.

## 4. Authorization

Authorization determines which operations an authenticated identity may perform.

A valid identity does not automatically receive unrestricted access.

The project uses Role-Based Access Control (RBAC).

### 4.1 Role-Based Access Control

RBAC assigns permissions to roles and assigns roles to users.

The demonstration contains three roles:

| Role | Access Level | Representative Permissions |
|---|---|---|
| Admin | Administrative | User management and system management |
| Editor | Restricted modification | User reading, user updating and report reading |
| Viewer | Read-only | User reading and report reading |

The authorization relationship is:

    User
      |
      v
    Assigned Roles
      |
      v
    Role-Permission Mapping
      |
      v
    Effective Permissions
      |
      v
    Authorization Decision

A user may possess multiple roles. Effective permissions are the union of permissions granted by those roles.

The system follows a deny-by-default approach. A permission that has not been explicitly granted is unavailable.

### 4.2 Permission naming

Permissions use the following naming convention:

`resource:action`

Examples:

| Permission | Meaning |
|---|---|
| `users:read` | Read user information |
| `users:create` | Create user records |
| `users:update` | Update user information |
| `users:delete` | Delete user records |
| `reports:read` | Read reports |
| `system:manage` | Perform administrative operations |

Permission checks are performed independently of the HTTP route definition.

This separation allows the same permission to be reused across multiple endpoints while maintaining a centralized authorization policy.

### 4.3 Authentication versus authorization

| Authentication | Authorization |
|---|---|
| Establishes identity | Determines permitted actions |
| Verifies credentials or tokens | Evaluates roles and permissions |
| Answers who is making the request | Answers what the requester can do |
| Common failure: HTTP 401 | Common failure: HTTP 403 |

An authenticated viewer attempting to access an administrative endpoint is an authorization failure, not an authentication failure.

## 5. Resource-Level Authorization

Role-based permissions alone are not sufficient for every API.

A user may possess permission to read documents but should not automatically receive access to every document.

Resource-level authorization evaluates access to a specific record.

The project implements ownership checks.

Each resource contains:

- A unique resource identifier.
- An owner identifier.
- Resource content.
- Resource metadata.

The access policy allows a request when:

1. The resource exists.
2. The user is active.
3. The user owns the resource, or has the administrative permission required to access another user's resource.

This prevents insecure direct object reference problems.

### Insecure Direct Object Reference

An insecure direct object reference occurs when an application exposes an object identifier and fails to verify whether the requester may access the corresponding object.

For example, changing a request from one document identifier to another must not automatically expose the second document.

Resource ownership must be checked on the server. Hiding identifiers in the client interface is not an authorization control.

## 6. API Security Controls

Authentication and authorization address identity and access decisions. Additional controls are needed to protect the API against abusive requests and malformed inputs.

### 6.1 Input validation

Every API request must be validated before its data is processed.

The implementations validate:

- Username format.
- Password requirements.
- Email structure.
- Request body type.
- Request body size.
- Supported HTTP methods.
- Endpoint paths.
- Resource identifiers.
- Unexpected input fields.

The JavaScript implementation uses structured objects and byte-length checks.

The Python implementation validates dictionaries and serialized request sizes.

The C++ implementation validates request metadata and resource identifiers.

The Java implementation uses immutable records and explicit validation methods.

PostgreSQL adds integrity checks through `CHECK`, `UNIQUE`, `NOT NULL`, and foreign-key constraints.

Input validation reduces malformed data and unexpected application states. It does not replace parameterized database queries, context-specific output encoding, or business-rule validation.

### 6.2 Request size restrictions

Large requests can consume excessive memory and processing resources.

The demonstration limits request bodies to 16,384 bytes.

Production systems should also impose:

- Maximum header sizes.
- Maximum URL lengths.
- Maximum upload sizes.
- JSON nesting limits.
- Request processing timeouts.
- Connection limits.
- Pagination limits.

Limits should be enforced at the reverse proxy, API gateway, and application layers where appropriate.

### 6.3 Rate limiting

Rate limiting restricts the number of requests a client can submit during a specified period.

The implementations demonstrate a sliding-window algorithm.

The algorithm maintains request timestamps for each client.

For a request arriving at time \(t\), the system:

1. Removes timestamps older than the configured window.
2. Counts the remaining timestamps.
3. Rejects the request when the configured maximum has been reached.
4. Otherwise records the new request.

For a limit of 20 requests in 60 seconds, the client cannot submit more than 20 accepted requests during the active window.

The sliding-window approach is more precise than a simple fixed-window counter around window boundaries.

| Limiting Strategy | Characteristics |
|---|---|
| Fixed window | Simple counters with fixed time intervals |
| Sliding window | Evaluates requests over a moving time interval |
| Token bucket | Allows controlled bursts while maintaining an average rate |
| Leaky bucket | Processes requests at a controlled output rate |

The examples use in-memory storage. Production environments with multiple application instances require a shared rate-limiting mechanism.

Rate limits should consider client IP, authenticated identity, endpoint sensitivity, and trusted gateway information. Client-supplied identity headers must not be trusted without verification.

### 6.4 Security auditing

Audit logging records security-relevant events.

The project records events such as:

- Successful authentication.
- Failed authentication.
- User access.
- Administrative access.
- Permission denial.
- Token revocation.
- Account deactivation.
- Resource access.

An audit event contains:

| Field | Description |
|---|---|
| Event identifier | Unique event reference |
| Timestamp | Event occurrence time |
| User identifier | Associated identity |
| Event type | Operation being recorded |
| Resource | Affected endpoint or resource |
| Decision | Allowed or denied |
| Severity | Security significance |
| Details | Structured event information |

The JavaScript implementation uses an event-driven audit service.

The Python implementation writes JSON Lines records.

The C++ implementation maintains structured audit events in memory.

The Java implementation uses immutable audit records.

PostgreSQL maintains a dedicated `security_audit` table and reporting views.

Audit logs should not contain plaintext passwords, complete bearer tokens, private keys, or other sensitive credentials.

Production systems should use append-only or externally protected storage, restricted access, retention policies, reliable delivery, and monitoring.

## 7. HTTP Security Responses

The API uses HTTP response codes to distinguish common request outcomes.

| Status | Meaning | Typical Situation |
|---|---|---|
| 200 | OK | Authorized request completed |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Authenticated user lacks permission |
| 404 | Not Found | Resource or endpoint does not exist |
| 413 | Content Too Large | Request exceeds configured size |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected application failure |

An API should return useful error information without exposing internal implementation details, cryptographic material, database errors, or stack traces.

For sensitive resources, applications should also consider whether returning 403 or 404 would disclose the existence of a protected object.

## 8. Python Implementation

**File:** `secure_api.py`

The Python implementation provides an executable API security simulation using standard-library modules.

### Main components

| Component | Responsibility |
|---|---|
| `PasswordManager` | Password validation and PBKDF2 derivation |
| `UserRepository` | User creation, retrieval and deactivation |
| `TokenManager` | Token signing, verification and revocation |
| `AuthenticationService` | Credential verification and account authentication |
| `AuthorizationService` | Role-based permission evaluation |
| `RateLimiter` | Sliding-window request restrictions |
| `InputValidator` | Request and user-input validation |
| `AuditLogger` | Persistent security event records |
| `SecureAPI` | API request processing and response generation |

### Implementation decisions

Dataclasses represent users, tokens, requests, responses, and audit events.

Enums define roles and HTTP methods.

Dictionaries provide indexed user and resource retrieval.

Sets represent permissions and revoked tokens.

Deques support efficient removal of expired rate-limit timestamps.

Exceptions distinguish authentication, authorization, validation, and rate-limit failures.

The script includes test assertions for:

- Public health access.
- Administrative authorization.
- Viewer access denial.
- User listing.
- Invalid password rejection.
- Token revocation.
- Inactive account rejection.

### Execution

Requirements:

- Python 3.10 or later.
- Standard library only.

Run the file using:

`python secure_api.py`

The script creates `secure_api_audit.jsonl` in the current working directory.

## 9. JavaScript Implementation

**File:** `secure_api.js`

The JavaScript implementation emphasizes asynchronous operations and event-driven security processing.

### Main components

| Component | Responsibility |
|---|---|
| `PasswordService` | Asynchronous password hashing and verification |
| `UserRepository` | Indexed account storage |
| `TokenService` | HMAC token generation and verification |
| `AuthenticationService` | Login and identity verification |
| `AuthorizationService` | Permission and resource policy evaluation |
| `RateLimiter` | Client request throttling |
| `RequestValidator` | Structured request validation |
| `AuditService` | Event-driven audit persistence |
| `SecureAPIGateway` | Central request-processing gateway |

### JavaScript-specific design

The implementation uses:

- `Map` for users and resources.
- `Set` for permissions and revoked tokens.
- `Promise` for asynchronous password derivation.
- `async` and `await` for authentication workflows.
- `EventEmitter` for security audit events.
- Node.js cryptographic functions for hashing and signatures.
- File-system promises for audit persistence.

The audit service serializes persistence operations through a promise queue. This prevents concurrent event handlers from independently starting writes through the same queue.

The implementation also distinguishes security exceptions from unexpected application failures.

### Execution

Requirements:

- Node.js 18 or later.
- No npm dependencies.

Run:

`node secure_api.js`

The program creates `secure-api-audit.jsonl` in the current working directory.

## 10. C++17 Implementation

**File:** `secure_api.cpp`

The C++ implementation concentrates on security decision evaluation.

Instead of implementing a complete HTTP server, it models the authorization and security engine that an API gateway or application service can invoke.

### Main components

| Component | Responsibility |
|---|---|
| `UserDirectory` | User identity and account state |
| `TokenRegistry` | Token validity and revocation |
| `PermissionRegistry` | Role-to-permission mapping |
| `ResourceRepository` | Resource ownership |
| `RateLimiter` | Request frequency evaluation |
| `AuditService` | Structured security decisions |
| `SecureAPIEngine` | Central policy evaluation |

### Decision pipeline

The engine evaluates:

1. Request structure.
2. Request body size.
3. Rate limits.
4. Authentication requirements.
5. User existence.
6. Account status.
7. Token validity.
8. Endpoint permission.
9. Resource ownership.

Each evaluation produces a `SecurityResult` containing a decision, HTTP status code, and explanation.

The permission registry uses ordered sets, while user and token directories use hash-based containers for efficient lookup.

The resource repository separates record retrieval from access policy evaluation.

### Execution

Requirements:

- C++17-compatible compiler.
- No external libraries.

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic secure_api.cpp -o secure_api`

Run:

`./secure_api`

On Windows:

`secure_api.exe`

The demonstration evaluates administrative access, viewer restrictions, editor permissions, resource ownership, invalid tokens, and oversized requests.

The implementation models token validity through a trusted token registry. It does not generate or cryptographically verify bearer tokens and must not be treated as a standalone production authentication server.

## 11. Java 17 Implementation

**File:** `SecureApi.java`

The Java implementation models an enterprise-oriented security service with explicit domain types and service boundaries.

### Main components

| Component | Responsibility |
|---|---|
| `UserRepository` | Account storage and account-state updates |
| `PasswordService` | Password hashing and verification |
| `TokenService` | Signed access-token management |
| `AuthenticationService` | Login and authentication |
| `RBACPolicy` | Role-based authorization |
| `ResourceRepository` | Resource persistence model |
| `RateLimiter` | Sliding-window request control |
| `AuditService` | Security event collection |
| `SecureAPIService` | API security orchestration |

### Enterprise design decisions

Java records provide compact immutable domain representations.

Interfaces separate authorization policy contracts from their implementation.

Enums represent roles, account statuses, token states, and security decisions.

Concurrent collections support shared application state in the demonstration.

The `SecureAPIService` coordinates independent services rather than placing all security logic inside a single method.

Account deactivation and token revocation are evaluated separately.

The implementation demonstrates:

- Administrative permission evaluation.
- Editor access to authorized operations.
- Viewer restrictions.
- Resource ownership.
- Invalid-token rejection.
- Missing authentication.
- Token revocation.
- Account suspension.
- Structured security auditing.

### Execution

Requirements:

- Java 17.
- No third-party dependencies.

Compile:

`javac SecureApi.java`

Run:

`java SecureApi`

## 12. PostgreSQL Implementation

**File:** `secure_api.sql`

The database implementation provides the relational model for an API security system.

It separates account information, role definitions, permissions, token state, API resources, rate limits, and security audit records.

### 12.1 Database relationship model

    USERS
      |
      +---- USER_ROLES
      |         |
      |         v
      |       ROLES
      |         |
      |         v
      |   ROLE_PERMISSIONS
      |         |
      |         v
      |    PERMISSIONS
      |
      +---- ACCESS_TOKENS
      |
      +---- API_RESOURCES
      |
      +---- SECURITY_AUDIT

    API_ENDPOINTS
      |
      v
    PERMISSIONS

    RATE_LIMIT_POLICIES
      |
      v
    RATE_LIMIT_EVENTS

### 12.2 Database tables

| Table | Purpose |
|---|---|
| `users` | User identities, password hashes and account status |
| `roles` | Available authorization roles |
| `permissions` | Individual permissions |
| `user_roles` | Many-to-many user and role mapping |
| `role_permissions` | Many-to-many role and permission mapping |
| `access_tokens` | Token hashes and lifecycle state |
| `api_resources` | Resource ownership and content |
| `api_endpoints` | Endpoint definitions and required permissions |
| `rate_limit_policies` | Rate-limiting configuration |
| `rate_limit_events` | Request-rate history |
| `security_audit` | Security event history |

### 12.3 Referential integrity

Foreign keys preserve relationships between users, roles, permissions, tokens, and resources.

Unique constraints prevent duplicate usernames, email addresses, role names, and permission identifiers.

Check constraints enforce valid account-related values, request limits, token lifetimes, and structured data requirements.

These controls protect the database against invalid states even when application-level validation is incomplete.

### 12.4 Database functions

| Function | Responsibility |
|---|---|
| `update_timestamp()` | Updates modification timestamps |
| `revoke_access_token()` | Revokes an active token |
| `validate_access_token()` | Evaluates token and account status |
| `has_permission()` | Determines whether a user has a permission |
| `can_access_resource()` | Checks resource ownership and administrative access |
| `evaluate_endpoint_access()` | Evaluates endpoint eligibility |
| `check_rate_limit()` | Applies a transactional rate limit |
| `write_security_audit()` | Inserts structured audit events |

The `deactivate_user` procedure performs administrative account deactivation and token revocation within a transaction.

### 12.5 Views

`security_audit_report` combines audit events with user information.

`user_permission_report` provides an effective permission reporting structure.

These views simplify reporting without duplicating the underlying security relationships.

### 12.6 Indexing

Indexes support frequent queries involving:

- Account status.
- User-role relationships.
- Role-permission relationships.
- Active tokens.
- Resource ownership.
- Audit events.
- Rate-limit history.

The partial index on active tokens reduces the indexed dataset when queries primarily target active sessions.

Index selection should be validated against actual query patterns using `EXPLAIN` and production workload measurements.

### 12.7 Transactions

The administrative workflow demonstrates transactional account deactivation.

The transaction updates the account status, revokes associated tokens, and records the administrative operation.

The demonstration uses `ROLLBACK` so the sample account remains unchanged.

This illustrates atomicity: either the related changes are committed together or they are rolled back together.

### 12.8 Execution

Requirements:

- PostgreSQL 15 or later.
- Permission to create schemas, tables, functions, procedures, and triggers.

Execute the complete SQL file against a development database.

The sample password hashes and token identifiers are synthetic. They are intended for relational modeling and query evaluation, not real authentication.

## 13. Security Policy Evaluation

The implementations distinguish multiple independent security decisions.

| Security Layer | Evaluation Question | Failure Response |
|---|---|---|
| Request validation | Is the request structurally valid? | 400 or 413 |
| Rate limiting | Has the request threshold been exceeded? | 429 |
| Authentication | Is the identity valid? | 401 |
| Account verification | Is the account active? | 401 |
| Token verification | Is the token valid and unrevoked? | 401 |
| Authorization | Does the identity possess the permission? | 403 |
| Ownership verification | May this identity access this resource? | 403 or 404 |
| Endpoint resolution | Does the endpoint exist? | 404 |
| Application processing | Can the operation be completed? | Appropriate application response |

A secure API must not collapse all these decisions into a single authentication check.

A user can be authenticated but lack authorization. A user can possess a role but fail a resource-ownership check. A token can be correctly signed but revoked. A request can be authenticated and authorized but still violate a rate limit.

These conditions require separate evaluations.

## 14. Security Threats and Mitigations

| Threat | Description | Relevant Control |
|---|---|---|
| Brute-force attacks | Repeated credential guessing | Login throttling and monitoring |
| Credential exposure | Unauthorized disclosure of passwords | Salted password hashing and TLS |
| Token theft | Unauthorized use of bearer credentials | HTTPS, short expiry and revocation |
| Token tampering | Modification of token contents | Cryptographic signatures |
| Privilege escalation | Unauthorized permission acquisition | RBAC and controlled role assignment |
| Broken object-level authorization | Access to another user's records | Resource ownership checks |
| Injection | Malicious input affecting database queries | Parameterized SQL and validation |
| Denial of service | Excessive request consumption | Rate limits and resource limits |
| Account takeover | Unauthorized account access | MFA and account protection |
| Audit manipulation | Unauthorized modification of security history | Restricted append-only audit storage |
| Sensitive data exposure | Disclosure of private information | Data minimization and access controls |
| Replay attacks | Reuse of captured requests or credentials | Nonces, expiration and operation-specific controls |

The project demonstrates selected application-level controls. It is not a complete implementation of every security measure listed.

## 15. Performance and Scalability

Security controls have computational and operational costs.

### Password hashing

PBKDF2 intentionally requires more computation than a general-purpose hash.

It should be performed asynchronously or in a suitably controlled execution environment to avoid exhausting application request-processing capacity.

### Token verification

HMAC verification requires cryptographic computation for each authenticated request.

Token validation should be efficient, and key rotation must be planned.

### Permission evaluation

A permission registry can avoid repeated database joins for frequently evaluated policies.

Distributed systems must still ensure that permission changes and account deactivation take effect according to the intended consistency requirements.

### Rate limiting

In-memory rate limiting is suitable for a single-process demonstration.

A distributed application requires shared state or a centralized gateway so that clients cannot bypass limits by distributing requests across application instances.

### Database indexing

Indexes reduce retrieval costs but introduce storage and write overhead.

Frequently queried columns should be indexed according to measured query behavior rather than indexed indiscriminately.

### Audit storage

Audit records can grow rapidly.

Production deployments should define retention, archival, access-control, and storage-capacity policies.

## 16. Important Production Limitations

The implementations are technical demonstrations of application security mechanisms. They should not be deployed as production security infrastructure without further engineering.

Important limitations include:

- The Python and JavaScript examples use simplified signed-token formats rather than complete OAuth 2.0 or OpenID Connect implementations.
- The C++ program models token state without cryptographic token verification.
- The Java demonstration uses an in-memory token registry.
- The JavaScript and Python audit implementations use local files.
- In-memory user repositories are not persistent databases.
- Rate limiters are not distributed.
- Refresh-token rotation is not implemented.
- Multi-factor authentication is not implemented.
- Password-reset workflows are not implemented.
- Cross-origin resource sharing policies are not implemented.
- CSRF protection for cookie-based authentication is not implemented.
- TLS termination and certificate management are external deployment responsibilities.
- Production secrets require secure storage, rotation, and restricted access.
- PostgreSQL sample credentials are synthetic.
- Database authorization functions do not independently secure an exposed API.

A production deployment should use established authentication standards, secure secret management, HTTPS, least-privilege database roles, centralized logging, monitored rate limiting, and automated security testing.

## 17. Implementation Comparison

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Password hashing | Yes | Yes | No | Yes | Stores derived values |
| Signed tokens | HMAC | HMAC | No | HMAC | Token metadata |
| Authentication | Yes | Yes | Token registry | Yes | Token validation |
| RBAC | Yes | Yes | Yes | Yes | Relational mappings |
| Resource ownership | Resource model | Resource model | Yes | Yes | Database function |
| Rate limiting | Sliding window | Sliding window | Sliding window | Sliding window | Transactional counters |
| Audit logging | JSON Lines | Event-driven | In-memory | Structured records | Persistent table |
| Account deactivation | Yes | Yes | Account state model | Yes | Stored procedure |
| Persistence | Local audit file | Local audit file | In-memory | In-memory | Relational database |

## 18. Testing Scenarios

The source files include demonstration cases for the following security conditions.

| Scenario | Expected Result |
|---|---|
| Active administrator with valid token accesses administration | Allowed |
| Viewer attempts administrative access | Denied |
| Editor reads an authorized user endpoint | Allowed |
| Editor accesses an owned resource | Allowed |
| Viewer attempts to access another user's resource | Denied |
| Request has no bearer token | Authentication rejected |
| Token signature is invalid | Authentication rejected |
| Token is expired | Authentication rejected |
| Token has been revoked | Authentication rejected |
| Account is suspended or disabled | Authentication rejected |
| Request body exceeds the configured maximum | Request rejected |
| Client exceeds the request threshold | Rate limited |
| Unknown endpoint is requested | Not found |
| User lacks a required permission | Authorization rejected |

The demonstrations use assertions, explicit policy decisions, database constraints, and validation queries to check expected outcomes.

## 19. Key Technical Distinctions

The central security mechanisms address different questions:

| Mechanism | Primary Responsibility |
|---|---|
| Authentication | Establish identity |
| Authorization | Determine permitted actions |
| RBAC | Associate permissions with roles |
| Resource ownership | Restrict access to specific records |
| Token signing | Protect token integrity |
| Token expiration | Limit credential lifetime |
| Token revocation | Invalidate credentials before expiration |
| Input validation | Reject malformed or unacceptable data |
| Rate limiting | Control request frequency |
| Audit logging | Record security-relevant activity |
| Database constraints | Preserve relational integrity |
| TLS | Protect data in transit |

A secure API depends on these mechanisms operating together. A valid token alone does not establish permission, a role alone does not establish resource ownership, and application-level checks alone do not guarantee database integrity.
