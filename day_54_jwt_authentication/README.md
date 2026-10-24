# JWT Authentication: Access Tokens, Token Validation, and Protected Routes

## Scope

This project models JWT-based authentication as a complete request-security workflow.

The central distinction is:

`Credentials` → `Authentication` → `Access Token` → `Token Validation` → `Authorization` → `Protected Resource`

The implementations focus on access tokens rather than treating JWTs as a generic data format. A token is useful only when its signature, claims, lifetime, issuer, audience, token type, and authorization information are validated before a protected operation is performed.

The five implementations use different engineering perspectives:

| File | Primary perspective | Main responsibility |
|---|---|---|
| Python | Authentication workflow model | Issues and validates access tokens and protects a route |
| JavaScript | Event-driven service model | Performs asynchronous login and request authorization |
| C++17 | Security policy engine | Evaluates repository-style policy objects for protected operations |
| Java 17 | Enterprise domain model | Separates token services, domain types, and authorization policy |
| PostgreSQL | Relational security model | Stores users, roles, scopes, tokens, routes, and audit events |

## Authentication Model

Authentication establishes who the caller is. Authorization determines what that authenticated identity may do.

A typical request sequence is:

    Client
      |
      | credentials
      v
    Authentication Service
      |
      | access token
      v
    Client
      |
      | Authorization: Bearer <token>
      v
    Protected Route
      |
      +--> Parse token
      |
      +--> Validate signature
      |
      +--> Validate claims
      |
      +--> Validate lifetime
      |
      +--> Resolve identity
      |
      +--> Check scope
      |
      v
    Protected Resource

A valid JWT does not automatically mean that every resource should be accessible. Authentication and authorization are separate decisions.

## JWT Structure

A compact JWT contains three Base64URL-encoded sections:

`header.payload.signature`

The header identifies the token format and signing algorithm. The payload contains claims. The signature protects the encoded header and payload against unauthorized modification.

The Python, JavaScript, and Java implementations explicitly validate the expected signing algorithm rather than accepting an algorithm supplied by an untrusted token.

The model uses HS256:

`HMAC-SHA256(secret, encoded-header + "." + encoded-payload)`

The signature must be calculated over exactly the encoded header and payload received by the verifier.

## Important Claims

The implementations use the following claims:

| Claim | Purpose |
|---|---|
| `iss` | Identifies the expected token issuer |
| `sub` | Identifies the authenticated subject |
| `aud` | Identifies the intended API or service |
| `iat` | Records token issuance time |
| `nbf` | Defines the earliest valid time |
| `exp` | Defines the expiration time |
| `jti` | Provides a unique token identifier |
| `typ` | Distinguishes an access token |
| `roles` | Represents coarse-grained roles |
| `scope` | Represents permissions granted to the token |

The verifier rejects tokens with missing required claims, an incorrect issuer, an incorrect audience, an unsupported token type, invalid time values, or an expired lifetime.

## Access Tokens

An access token represents delegated access for a limited period.

The Python implementation creates an access token containing a subject, roles, scopes, issuance time, activation time, expiration time, issuer, audience, token type, and unique identifier.

The JavaScript implementation performs the same security workflow while using Node.js cryptographic primitives and asynchronous login handling.

The Java implementation models the token operation through `JwtService` and immutable domain records.

Short access-token lifetimes reduce the useful lifetime of a stolen token. The example uses a 15-minute lifetime. Real systems should choose a lifetime according to the sensitivity of the protected service and the operational refresh strategy.

## Token Validation

Token validation occurs before protected business logic.

The validation sequence is:

    Receive Authorization header
              |
              v
    Require Bearer authentication
              |
              v
    Split JWT into three sections
              |
              v
    Decode header and payload
              |
              v
    Validate expected algorithm and type
              |
              v
    Recalculate signature
              |
              v
    Constant-time signature comparison
              |
              v
    Validate issuer and audience
              |
              v
    Validate iat, nbf, and exp
              |
              v
    Validate token type and authorization claims
              |
              v
    Execute protected operation

A token that fails cryptographic validation receives an authentication failure rather than being treated as an authenticated request.

The Python implementation uses `hmac.compare_digest`. JavaScript uses `crypto.timingSafeEqual`. Java uses `MessageDigest.isEqual`. These mechanisms avoid ordinary string comparison for signatures.

## Bearer Authentication

Protected requests use:

`Authorization: Bearer <access-token>`

The examples reject requests using another authentication scheme.

A bearer token must be treated as a credential. Possession of the token is sufficient to present it as the caller, so token exposure can lead directly to unauthorized access until the token expires or is otherwise invalidated.

Operational controls should therefore protect:

- TLS connections
- browser storage
- server logs
- reverse-proxy logs
- exception traces
- monitoring systems
- client-side application state

Tokens should not be written into ordinary application logs.

## Scopes and Protected Routes

Scopes provide fine-grained authorization.

Examples used in the project include:

| Scope | Protected capability |
|---|---|
| `orders:read` | Read orders |
| `orders:write` | Create or modify orders |
| `profile:read` | Read profile information |
| `admin:users` | Manage user accounts |

A token containing `orders:read` can satisfy a route requiring `orders:read`.

It does not satisfy `orders:write`.

This produces an important separation:

`Authentication` identifies the caller.

`Authorization` checks whether the caller is permitted to perform the requested operation.

## Python Implementation

The Python implementation is a complete standard-library model.

### JWTManager

`JWTManager` handles token creation and validation.

It performs:

- HS256 signing
- Base64URL processing
- claim construction
- issuer validation
- audience validation
- token-type validation
- timestamp validation
- scope validation
- constant-time signature comparison

The implementation deliberately rejects malformed tokens instead of attempting to repair them.

### UserStore

`UserStore` provides an in-memory user repository.

Passwords are not stored as plaintext. A random salt and PBKDF2-HMAC-SHA256 are used to derive the stored password representation.

The authentication process compares derived password values using a constant-time comparison.

### AuthenticationService

`AuthenticationService` connects credential authentication with access-token issuance.

It also models a protected route that:

1. Reads the Authorization header.
2. Requires the Bearer scheme.
3. Validates the JWT.
4. Checks a required scope.
5. Returns the protected resource only after successful authorization.

The demonstration tests successful access, insufficient scope, a modified token, and an invalid authentication scheme.

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library facilities.

### Cryptography

The implementation uses:

- `crypto.createHmac`
- `crypto.pbkdf2Sync`
- `crypto.randomBytes`
- `crypto.timingSafeEqual`

No third-party package is required.

### Event-Driven Service Boundary

The login method is asynchronous even though the demonstration uses an in-memory store. This creates a service boundary compatible with database-backed authentication or network-based identity services.

The request-processing model remains separate from token generation.

### Validation Behavior

The JavaScript implementation rejects:

- non-string tokens
- tokens without three JWT sections
- malformed JSON
- unsupported algorithms
- incorrect token types
- invalid signatures
- missing required claims
- invalid time claims
- future-issued tokens outside the accepted clock allowance
- inactive tokens
- expired tokens
- missing scopes

The distinction between authentication failure and authorization failure is represented by different error types.

## C++17 Implementation

The C++17 program provides a different perspective: a policy and merge-eligibility engine.

The domain contains:

- pull requests
- commits
- reviews
- status checks
- protected branches
- eligibility results

Although this model uses repository-governance concepts as its case study, its policy structure maps directly to protected-resource authorization.

A protected operation is accepted only when the relevant policy conditions are satisfied.

The engine evaluates:

- operation state
- draft state
- source and target separation
- presence of changes
- conflicts
- required approvals
- reviewer eligibility
- stale approvals
- requested changes
- required status checks
- unresolved conversations

The important security concept is that authorization is evaluated from authoritative state rather than from a caller-provided boolean such as `isAuthorized`.

## Java 17 Implementation

The Java implementation uses explicit domain modeling.

Records represent immutable data structures such as:

- `User`
- `Review`
- `StatusCheck`
- `BranchProtectionPolicy`
- `PullRequest`
- `EligibilityResult`

Enums represent controlled state values.

The `JwtService` is responsible for access-token operations. `MergeEligibilityService` is a separate policy component. This separation prevents authentication mechanics from becoming mixed with authorization policy.

The authorization model demonstrates how enterprise systems can make security decisions through explicit domain objects instead of scattering permission checks throughout application code.

The example also uses defensive copies and immutable collections where appropriate. This prevents callers from unexpectedly changing security-sensitive policy data after construction.

## PostgreSQL Implementation

The PostgreSQL script represents authentication as a relational security model.

The principal entities are:

    users
      |
      +---- user_roles ---- roles
      |
      +---- user_scopes --- scopes
      |
      +---- access_tokens
      |
      +---- authentication_events

    protected_routes
          |
          +---- required scope

This design separates identity, roles, scopes, tokens, routes, and audit information.

### Users

The `users` table stores identity state and a password representation.

A database record does not contain a plaintext password.

### Roles

Roles represent broader identity categories such as:

- customer
- support
- admin

Roles are useful for coarse-grained identity management.

### Scopes

Scopes represent specific API capabilities.

This makes route authorization more precise than using a single role value.

### Access Tokens

The database stores a token hash rather than the original bearer token.

The token table records:

- token identity
- subject
- token type
- issuance time
- expiration time
- revocation time
- current token status

The schema prevents invalid token periods through a check constraint.

A trigger also enforces consistency between token status and revocation time.

## Protected Routes

The `protected_routes` table associates an API route and HTTP method with an optional required scope.

Examples include:

| Route | Method | Required scope |
|---|---|---|
| `/orders` | GET | `orders:read` |
| `/orders` | POST | `orders:write` |
| `/profile` | GET | `profile:read` |
| `/admin/users` | GET | `admin:users` |

This keeps authorization requirements in data rather than hard-coding every rule into an application function.

## Database Authorization Functions

`has_user_scope` checks whether a user possesses a particular scope.

`token_is_valid` checks whether a token:

- exists
- is an access token
- is active
- has not been revoked
- is within its lifetime
- belongs to an active user

`can_access_route` combines token validity, user state, route state, and scope requirements.

This models authorization as a composition of independent conditions.

## Transactions and Audit Events

The PostgreSQL script records authentication and authorization events.

Examples include:

- successful login
- failed login
- token issuance
- granted access
- denied access

A transaction locks relevant token records before recording an authorization-related audit operation. This demonstrates how security-sensitive state changes can be grouped into an atomic database operation.

## Authentication Failure Versus Authorization Failure

These two outcomes should not be treated as identical internally.

| Condition | Typical HTTP result |
|---|---:|
| Missing token | 401 |
| Invalid signature | 401 |
| Expired token | 401 |
| Invalid issuer | 401 |
| Invalid audience | 401 |
| Disabled identity | 401 |
| Valid identity without required scope | 403 |

A `401 Unauthorized` response indicates that valid authentication has not been established.

A `403 Forbidden` response indicates that authentication exists but the requested operation is not permitted.

The exact public error body should avoid exposing unnecessary details that help attackers distinguish internal validation conditions.

## Token Expiration

Expiration is one of the primary controls limiting the impact of token theft.

The examples validate both:

`nbf <= current time`

and:

`current time < exp`

They also ensure that the expiration time follows the issuance time.

A production implementation should account for small clock differences between distributed systems. A limited clock-skew allowance can prevent unnecessary failures while still keeping token lifetimes controlled.

Large clock allowances weaken expiration guarantees and should be avoided.

## Revocation

JWT access tokens are often described as stateless because a verifier can validate the signature without querying the issuing service.

That does not mean revocation is impossible.

The PostgreSQL model adds a token registry containing token hashes and statuses. This permits explicit revocation.

The trade-off is architectural:

| Approach | Benefit | Cost |
|---|---|---|
| Pure signature validation | Low verification overhead | Immediate revocation is difficult |
| Token registry | Immediate revocation possible | Requires state lookup |
| Short-lived access tokens | Limits stolen-token lifetime | More frequent renewal |
| Refresh-session model | Supports longer user sessions | Requires secure refresh-token storage and rotation |

A system should choose the model according to its threat model and availability requirements.

## Password Authentication

JWTs do not replace password security.

Passwords must be processed separately from JWT signing.

The Python and JavaScript examples use PBKDF2-HMAC-SHA256 with a random salt for the demonstration user store.

Production password storage should use a modern password-hashing scheme configured according to current security guidance. Password verification should never compare plaintext passwords with stored plaintext values.

## Secret Management

The example implementations generate or receive signing secrets in application memory.

Production deployments should not hard-code signing secrets in source code.

Secrets should be stored in a protected secret-management system and rotated according to operational requirements.

For a multi-service environment, asymmetric signing can reduce the need to distribute one shared secret:

    Authorization Server
          |
          | private key
          v
        signs
          |
          v
       JWT access token
          |
          v
      API services
          |
          | public key
          v
       verifies

This architecture allows verifiers to possess a public key without possessing the private signing key.

## Algorithm Validation

The JWT header is attacker-controlled input.

A verifier must not blindly trust the algorithm declared by the token.

The examples explicitly require HS256.

Production systems should configure an explicit allow-list of algorithms and use a maintained JWT implementation that correctly handles cryptographic parsing, verification, and key management.

## Audience Validation

Signature validity alone does not prove that a token belongs to the current API.

The `aud` claim identifies the intended audience.

For example:

`orders-api`

A token issued for another service should not automatically be accepted by the orders service.

Audience validation is therefore an important defense against token reuse across unrelated services.

## Issuer Validation

The `iss` claim identifies the trusted token issuer.

The verifier compares it against its configured issuer.

This prevents a token signed with a trusted mechanism from being accepted merely because its structure and signature appear valid when it originated from an unexpected issuer.

## Protected Route Workflow

The complete authorization decision can be represented as:

    Request
       |
       v
    Bearer token present?
       |
       +-- No --> 401
       |
       v
    JWT structurally valid?
       |
       +-- No --> 401
       |
       v
    Signature valid?
       |
       +-- No --> 401
       |
       v
    Issuer and audience valid?
       |
       +-- No --> 401
       |
       v
    Token currently active?
       |
       +-- No --> 401
       |
       v
    User active?
       |
       +-- No --> 401
       |
       v
    Required scope present?
       |
       +-- No --> 403
       |
       v
    Protected resource

This sequence keeps authentication checks ahead of business authorization.

## Edge Cases

The implementations explicitly handle several failure conditions:

- empty subjects
- duplicate users
- weak demonstration passwords
- malformed JWTs
- incorrect segment counts
- invalid Base64URL data
- malformed JSON
- unsupported algorithms
- invalid token types
- missing claims
- future-issued tokens
- not-yet-active tokens
- expired tokens
- invalid token lifetimes
- altered signatures
- missing bearer authentication
- missing scopes
- disabled users
- revoked tokens
- failed protected-route requirements

These cases are important because authentication code operates directly on attacker-controlled input.

## Security Considerations

Important production controls include:

- Use HTTPS for all token transport.
- Never log complete bearer tokens.
- Keep access-token lifetimes limited.
- Validate issuer and audience.
- Allow only explicitly supported signing algorithms.
- Protect signing keys.
- Rotate signing keys with a controlled key-distribution strategy.
- Use secure password hashing.
- Avoid placing long-lived bearer tokens in browser-accessible storage when safer alternatives exist.
- Consider refresh-token rotation for persistent sessions.
- Apply authorization checks on every protected operation.
- Do not trust client-supplied roles or permissions.
- Validate token claims at the service boundary.
- Record security-relevant events without storing sensitive credentials.
- Keep clock synchronization reliable across services.

## Performance Considerations

JWT verification involves cryptographic computation.

For a symmetric HMAC signature, verification is generally efficient, but high-volume APIs can still incur meaningful CPU cost.

Database-backed revocation introduces network and database latency compared with purely local signature verification.

Useful indexes in the PostgreSQL model include:

- token hash uniqueness
- user and token status
- token expiration
- user and authentication-event time

The right architecture depends on traffic volume, revocation requirements, token lifetime, and the number of services participating in authentication.

## Design Boundaries

The project deliberately separates several concepts.

| Concept | Responsibility |
|---|---|
| Credential authentication | Establishes user identity |
| JWT issuance | Creates a signed access credential |
| JWT validation | Determines whether the credential is authentic and active |
| Scope evaluation | Determines whether the requested capability is granted |
| Protected route | Defines which operation requires authorization |
| Audit logging | Records important security events |
| Revocation | Invalidates otherwise cryptographically valid tokens |

Combining these responsibilities into one large authentication function makes security behavior harder to verify and maintain.

## Practical Request Example

A successful request conceptually follows:

    POST /login
          |
          v
    Credentials validated
          |
          v
    Access token issued
          |
          v
    GET /orders
    Authorization: Bearer <access-token>
          |
          v
    Signature + claims + lifetime validated
          |
          v
    orders:read scope verified
          |
          v
    HTTP 200 protected response

A request using the same token for an operation requiring `orders:write` fails authorization if that scope is absent.

## Limitations of the Demonstration

The implementations are intentionally self-contained and therefore simplify several production concerns.

The Python, JavaScript, and Java examples implement HS256 directly for educational clarity. Production services should normally use mature JWT libraries rather than maintaining custom cryptographic protocol code.

The in-memory user stores do not provide distributed identity management.

The PostgreSQL sample stores token hashes but does not implement a complete refresh-token rotation protocol.

The examples also do not implement key identifiers, asymmetric key rotation, multi-tenant issuer configuration, distributed session management, or a full HTTP framework.

These limitations keep the security mechanisms visible while preserving executable examples.

## Relationship Between the Five Implementations

The implementations are related but not translations of one another.

Python emphasizes the complete authentication workflow.

JavaScript emphasizes an asynchronous service boundary and Node.js cryptographic primitives.

C++17 emphasizes explicit policy evaluation and structured security decisions.

Java 17 emphasizes immutable domain types and enterprise-style service separation.

PostgreSQL emphasizes durable identity, authorization, token state, route policy, and security auditing.

Together they represent the same security boundary from different engineering perspectives without requiring one implementation to duplicate another.
