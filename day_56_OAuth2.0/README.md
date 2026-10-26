# OAuth 2.0 Authorization Workflow and Governance Model

## Scope

This project models OAuth 2.0 as a delegation framework for controlled access to protected resources.

The implementations use the following relationship:

`Resource Owner → Client → Authorization Server → Access Token → Resource Server`

The central distinction is between **authorization**, **token issuance**, and **resource access**:

- The **resource owner** controls access to protected data.
- The **client** requests delegated access.
- The **authorization server** authenticates the authorization request, obtains consent or an equivalent authorization decision, and issues tokens.
- The **access token** represents the delegated authorization granted to the client.
- The **resource server** validates the access token and enforces the required scope.

OAuth 2.0 is an authorization framework. It is not itself a general-purpose identity protocol.

## Core Domain Model

    Resource Owner
          |
          | authorizes
          v
        Client
          |
          | authorization request
          v
    Authorization Server
          |
          | authorization code
          v
        Client
          |
          | code + PKCE verifier
          v
    Authorization Server
          |
          | access token + refresh token
          v
    Resource Server
          |
          | validates token + scope
          v
    Protected Resource

The authorization server and resource server have different responsibilities. A resource server should not infer authorization merely from the fact that a client is registered. It should evaluate the presented access token and the permissions represented by its scopes.

## Authorization Flows

The implementations focus on the authorization code flow with PKCE.

A typical sequence is:

1. The client identifies itself and supplies a registered redirect URI.
2. The client requests a bounded set of scopes.
3. The authorization server validates the client, redirect URI, requested scopes, and PKCE challenge.
4. The authorization server issues a short-lived authorization code.
5. The client sends the code and PKCE verifier to the token endpoint.
6. The authorization server verifies the code, client identity where applicable, redirect URI, expiration, and PKCE proof.
7. The authorization code becomes single-use.
8. The authorization server issues an access token and, where appropriate, a refresh token.
9. The client presents the access token to the resource server.
10. The resource server validates token state, expiration, and required scope.

The code and token are separate credentials with different lifetimes and purposes.

## Clients

The model distinguishes public and confidential clients.

A confidential client can authenticate to the authorization server because it can maintain credentials in a protected server-side environment.

A public client cannot safely depend on a client secret being kept confidential. The Python, JavaScript, C++17, and Java 17 implementations therefore make PKCE a central part of the authorization-code exchange.

Client registration contains:

| Attribute | Purpose |
|---|---|
| Client ID | Identifies the application |
| Client type | Distinguishes public and confidential clients |
| Redirect URIs | Defines permitted authorization response destinations |
| Allowed scopes | Limits permissions that the client may request |
| Client credential | Authenticates a confidential client |

Redirect URI validation is a security boundary. An authorization response must not be sent to an arbitrary URI supplied during a request.

## Scopes

Scopes represent delegated permissions.

Examples used by the implementations include:

- `profile:read`
- `orders:read`
- `account:read`
- `transaction:read`
- `admin:write`

A client may only request scopes that it is registered to use.

The implementations deliberately reject an authorization request for `admin:write` when the client has only been granted `profile:read` or `orders:read`.

This implements a least-privilege boundary:

`Registered Permissions ⊇ Requested Permissions ⊇ Granted Permissions`

The resource server then performs the final resource-level check:

`Granted Scope ⊇ Required Resource Scope`

Possessing an access token does not automatically grant access to every resource.

## Authorization Server

The authorization server is responsible for issuing and managing authorization artifacts.

The Python implementation uses:

- `dataclass` domain objects
- Dictionaries for token and client state
- Sets for scopes
- Exceptions for OAuth failures
- `secrets` for high-entropy token values
- `hashlib` and `base64` for the PKCE S256 calculation
- Token expiration timestamps
- Refresh-token rotation
- Explicit revocation

The JavaScript implementation adds an event-driven audit model through `EventEmitter`. Authorization-code issuance, token issuance, refresh rotation, and revocation produce structured audit events.

The C++17 implementation emphasizes explicit classes, STL containers, value-oriented state, validation functions, and exception-based failure handling.

The Java 17 implementation models the authorization domain with records, interfaces, immutable sets, policy objects, custom exceptions, and explicit state replacement for token rotation.

## Authorization Codes

Authorization codes are short-lived credentials intended for exchange at the token endpoint.

A valid authorization code is associated with:

- Client ID
- Resource owner
- Redirect URI
- Requested scopes
- PKCE challenge
- Expiration time

The implementations enforce several properties:

| Condition | Result |
|---|---|
| Unknown code | Rejected |
| Expired code | Rejected |
| Already consumed code | Rejected |
| Client mismatch | Rejected |
| Redirect URI mismatch | Rejected |
| Incorrect PKCE verifier | Rejected |
| Valid code and verifier | Token issuance |

Single-use behavior is important because replaying an authorization code could otherwise allow another party to obtain tokens.

The PostgreSQL implementation uses `SELECT ... FOR UPDATE` during code consumption so concurrent requests cannot successfully consume the same authorization code.

## PKCE

PKCE binds the authorization request to the later token exchange.

The conceptual relationship is:

`code_challenge = BASE64URL(SHA-256(code_verifier))`

The client sends the challenge during authorization and later sends the verifier to the token endpoint.

The authorization server independently derives the expected challenge and compares it with the stored value.

The Python implementation performs the S256 calculation with the standard library.

The JavaScript implementation uses Node.js `crypto`.

The Java and C++ implementations use explicit deterministic representations to keep their standalone examples dependency-free. Their comments identify where a production implementation must use a vetted cryptographic implementation of the RFC 7636 S256 transformation.

## Access Tokens

An access token is presented to a resource server when requesting protected data.

The implementations treat access tokens as opaque values stored by the authorization server.

Each token has:

- Client identity
- Resource-owner identity
- Scopes
- Expiration
- Active or revoked state

A resource server validates:

1. Token existence.
2. Token state.
3. Token expiration.
4. Required scope.
5. Resource ownership or subject authorization.

A valid token with insufficient scope must not be accepted.

## Resource Server

The resource server is distinct from the authorization server.

Its main responsibility is protecting application resources.

For example:

    GET protected account
            |
            v
    Validate access token
            |
            +-- invalid/revoked --> reject
            |
            v
    Check expiration
            |
            +-- expired ---------> reject
            |
            v
    Check required scope
            |
            +-- missing ---------> reject
            |
            v
    Check resource authorization
            |
            +-- unauthorized ----> reject
            |
            v
    Return protected resource

The resource server does not treat client registration as sufficient authorization.

The required permission is attached to the protected resource itself. This prevents a broad assumption that every token issued to a client can access every resource.

## Refresh Tokens

Refresh tokens allow a client to obtain a new access token without repeating the complete authorization interaction.

The model uses refresh-token rotation:

1. The client presents the current refresh token.
2. The authorization server validates the client where appropriate.
3. The refresh token is checked for existence, state, expiration, and client association.
4. The old refresh token is revoked.
5. A new access token is issued.
6. A new refresh token is issued.
7. Reuse of the previous refresh token is rejected.

This reduces the value of a replayed refresh token.

Refresh tokens should receive stronger protection than ordinary access tokens because their lifetime is longer.

## Revocation

Revocation changes a token from an active state to a revoked state.

A revoked access token must fail resource-server validation even when its original expiration time has not been reached.

The Python, JavaScript, C++17, Java 17, and PostgreSQL implementations all represent token state explicitly.

The PostgreSQL schema adds a trigger preventing a revoked token from being changed back to `active`.

## Python Implementation

The Python program models the OAuth lifecycle with explicit domain classes:

| Component | Implementation |
|---|---|
| Client | `Client` dataclass |
| Authorization code | `AuthorizationCode` dataclass |
| Access token | `AccessToken` dataclass |
| Refresh token | `RefreshToken` dataclass |
| Authorization server | `AuthorizationServer` |
| Resource server | `ResourceServer` |
| Token generation | `secrets` |
| PKCE | `hashlib` and URL-safe Base64 |
| Failure handling | Custom exceptions |

The demonstration executes authorization, token exchange, protected-resource access, refresh rotation, replay detection, revocation, redirect URI validation, and scope validation.

The implementation also checks the resource-owner identity before returning the protected resource.

## JavaScript Implementation

The JavaScript implementation emphasizes asynchronous and event-driven behavior.

Its `OAuthAudit` class extends `EventEmitter` so authorization events can be consumed independently from the core authorization logic.

The resource server exposes an asynchronous resource operation. The asynchronous boundary models the type of separation found in a real service architecture where token validation and resource retrieval may involve network operations.

JavaScript `Map` and `Set` objects represent:

- Registered clients
- Authorization codes
- Access tokens
- Refresh tokens
- Scopes
- Resources

Node.js `crypto` supplies random token material, SHA-256, and timing-safe comparisons.

The demonstration covers successful authorization, resource access, refresh-token rotation, replay rejection, revocation, unregistered redirect URI rejection, and unauthorized-scope rejection.

## C++17 Implementation

The C++ implementation is organized as a repository-independent governance engine for OAuth authorization state.

The main classes are:

- `AuthorizationServer`
- `ResourceServer`
- `TokenGenerator`

The implementation uses:

- `unordered_map` for indexed state
- `set` for scope collections
- `map` for resource attributes
- `enum class` for explicit state
- Exceptions for invalid authorization transitions
- `chrono` for expiration handling
- Structured objects for clients, codes, tokens, and resources

The server validates client registration, redirect URIs, scopes, PKCE input, client authentication, authorization-code state, token expiration, token scope, resource ownership, refresh-token rotation, and revocation.

The C++ implementation keeps the cryptographic PKCE calculation visibly separated from the domain logic and explicitly identifies the need for a production cryptographic library.

## Java 17 Implementation

The Java implementation emphasizes enterprise domain modeling.

Records represent immutable domain data:

- `Client`
- `AuthorizationCode`
- `AccessToken`
- `RefreshToken`
- `ProtectedResource`
- `TokenPair`

The `Policy` interface separates authorization rules from the authorization service.

`LeastPrivilegePolicy` enforces the relationship between client permissions and requested scopes.

The authorization service manages state transitions and uses replacement of immutable records when a token changes from active to revoked.

Custom `OAuthException` instances provide explicit OAuth error categories.

This separation makes policy behavior independently testable and allows enterprise applications to replace or extend policy objects without embedding every rule inside one service class.

## PostgreSQL Model

The PostgreSQL implementation treats OAuth state as relational data.

The principal entities are:

    oauth_client
         |
         +-- redirect_uri
         |
         +-- client_scope
         |
         +-- authorization_code
         |       |
         |       +-- authorization_code_scope
         |
         +-- access_token
         |       |
         |       +-- access_token_scope
         |
         +-- refresh_token
                 |
                 +-- refresh_token_scope

    resource_owner
         |
         +-- protected_resource

    oauth_client
         |
         +-- status_check
         |
         +-- oauth_audit_event

Foreign keys enforce relationships.

Unique constraints prevent duplicate client identifiers, redirect registrations within a client, token hashes, and scope associations.

Check constraints enforce client-secret requirements and status values.

Indexes support common lookup paths for active tokens, refresh tokens, authorization-code expiration, protected-resource scope, and client audit history.

## Database-Level Authorization

The database contains three important authorization functions.

`consume_authorization_code` performs transactional code consumption and uses row locking to prevent concurrent replay.

`evaluate_access_token` evaluates whether a token:

- Exists
- Is active
- Has not expired
- Belongs to the required resource owner
- Contains the required scope

The resulting Boolean is a resource-server authorization decision.

`validate_authorization_code_redirect_uri` ensures that a token request cannot introduce an unregistered redirect URI.

The database therefore does not merely store OAuth data. It enforces selected security invariants.

## Token State

The relational model represents token state explicitly:

| State | Meaning |
|---|---|
| `active` | Token may be considered for authorization |
| `revoked` | Token must not authorize access |

Expiration is separate from state.

A token can be technically `active` while already expired. Resource-server evaluation checks both conditions.

This distinction is important because lifecycle state and temporal validity are different properties.

## Security Controls

The implementations model several important controls.

### Redirect URI validation

Redirect URIs are compared against registered client values.

An arbitrary redirect URI is rejected.

### PKCE

The authorization-code exchange requires proof that the client possesses the original verifier.

### Least privilege

Clients cannot request scopes outside their registered permissions.

### Short authorization-code lifetime

Authorization codes have a short lifetime and are single-use.

### Access-token expiration

Access tokens have a relatively short lifetime.

### Refresh-token rotation

A successful refresh invalidates the previous refresh token.

### Revocation

Explicitly revoked tokens cannot authorize resource access.

### Client authentication

Confidential clients authenticate at the token endpoint.

### Constant-time credential comparison

The Python and JavaScript implementations use timing-aware comparisons where appropriate for secret material.

### Auditability

The JavaScript event model and PostgreSQL audit table provide mechanisms for recording important authorization events.

## Failure Conditions

The model intentionally exercises failure states rather than only successful requests.

| Failure | Enforcement point |
|---|---|
| Unknown client | Authorization server |
| Inactive client | Authorization server/database |
| Unregistered redirect URI | Authorization server/database trigger |
| Empty scope | Authorization policy |
| Unauthorized scope | Client-scope policy |
| Expired authorization code | Token endpoint |
| Replayed authorization code | Token endpoint/database transaction |
| Incorrect PKCE verifier | Token endpoint |
| Invalid client credentials | Token endpoint |
| Expired access token | Resource server |
| Revoked access token | Resource server |
| Missing required scope | Resource server |
| Wrong resource owner | Resource server |
| Expired refresh token | Token endpoint |
| Replayed refresh token | Refresh-token rotation |

## Performance Considerations

The in-memory implementations use maps keyed by client IDs, codes, and token values. This provides average constant-time lookup for the principal state operations.

Scope collections use sets, making membership checks efficient and avoiding duplicate permissions.

The PostgreSQL implementation adds indexes only to common lookup paths. Token validation can use indexes on token identifiers and state, while authorization-code expiration can use its own index for lifecycle maintenance.

Database locking is intentionally limited to authorization-code consumption. The lock protects a state transition that must be atomic.

Large production deployments would normally avoid scanning every token during request processing. Expired-token cleanup and archival should be handled separately from the hot authorization path.

## Security and Production Boundaries

These programs are executable learning implementations, not complete production identity infrastructure.

A production OAuth deployment must use vetted cryptographic primitives, secure secret storage, TLS, carefully configured redirect URIs, secure browser storage patterns, appropriate token lifetimes, robust client authentication, monitoring, key management, and a well-defined token validation architecture.

Opaque tokens can be validated through server-side state. JWT access tokens can instead be self-contained and validated through issuer, audience, signature, expiration, and related claims. The choice changes the operational model and should not be made solely for convenience.

Access tokens should be transmitted only over protected channels.

Authorization servers should not place access tokens into URLs.

Refresh tokens require stronger protection because they normally have a longer validity period.

Scopes should express bounded permissions rather than becoming an uncontrolled substitute for application-specific authorization rules.

## Relationship Between the Components

The five implementations preserve the same conceptual separation while using different engineering techniques.

    Client Registration
           |
           v
    Authorization Request
           |
           +--> Redirect URI validation
           |
           +--> Scope validation
           |
           +--> PKCE challenge
           |
           v
    Authorization Code
           |
           +--> short lifetime
           +--> single use
           |
           v
    Token Endpoint
           |
           +--> client authentication
           +--> redirect URI validation
           +--> PKCE verification
           |
           v
    Access Token + Refresh Token
           |
           +--------------------+
           |                    |
           v                    v
    Resource Server       Refresh Endpoint
           |                    |
           v                    +--> rotate refresh token
    Scope + State                |
    + Expiration                 v
           |               New token pair
           v
    Protected Resource

The critical architectural boundary is that token issuance and resource authorization are different operations.

The authorization server decides what delegation is represented by a token.

The resource server decides whether the presented token satisfies the requirements for a particular protected resource.

## Practical Distinctions

### Authorization Code

A short-lived artifact exchanged for tokens.

It is not normally presented to the resource server.

### Access Token

A credential used to access protected resources.

Its permissions are represented by scopes and its validity is constrained by expiration and revocation.

### Refresh Token

A credential used to obtain a new access token.

It normally has a longer lifetime and requires stronger protection.

### Scope

A delegated permission such as `profile:read` or `orders:read`.

It is not automatically equivalent to a complete business authorization decision.

### Client

The application acting on behalf of the resource owner.

Its registration defines what OAuth interactions it is permitted to perform.

### Authorization Server

The authority responsible for issuing authorization artifacts and tokens.

### Resource Server

The service hosting protected resources and enforcing access-token authorization.

## Learning Focus

The implementations are designed to make the following relationships explicit:

`Client Registration → Authorization Request → Authorization Code → Token Exchange → Access Token → Scope Validation → Resource Access`

and:

`Refresh Token → Rotation → New Access Token → Revocation of Previous Refresh Token`

The Python implementation emphasizes standard-library modeling and executable validation.

The JavaScript implementation emphasizes asynchronous resource access and event-driven auditing.

The C++17 implementation emphasizes explicit stateful classes, STL data structures, and low-level lifecycle control.

The Java 17 implementation emphasizes immutable domain records, policy interfaces, and enterprise service boundaries.

The PostgreSQL implementation emphasizes relational integrity, transactional state transitions, database functions, triggers, reporting views, and authorization queries.

Together, the implementations preserve the same OAuth 2.0 security model while demonstrating how the model changes when represented through different programming and persistence paradigms.
