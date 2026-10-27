# OpenID Connect Identity Workflow

## Scope

This project models OpenID Connect as an identity layer built on OAuth 2.0 concepts. The implementations separate authentication from authorization and distinguish the main OIDC artifacts:

- Identity Provider
- OpenID Connect client
- Authorization request
- `state`
- `nonce`
- Authorization code
- PKCE
- ID token
- Access token
- UserInfo endpoint
- Subject identifier
- Issuer
- Audience
- Authentication session
- Provider discovery metadata
- Client redirect URI registration

The central workflow is:

Identity Provider
→ Authorization Request
→ User Authentication
→ Authorization Code
→ Token Endpoint
→ ID Token + Access Token
→ ID Token Validation
→ UserInfo
→ Application Session

The examples use a controlled enterprise portal scenario. The domain is intentionally focused on identity and authentication rather than implementing a general OAuth authorization server.

## OpenID Connect Identity Layer

OpenID Connect adds an identity protocol on top of OAuth 2.0. OAuth provides a framework for delegated access to resources. OpenID Connect defines how a client obtains authenticated identity information about the end user.

The `openid` scope identifies an authorization request as an OpenID Connect request.

The most important distinction in the implementation is:

| Artifact | Primary purpose |
|---|---|
| Authorization Code | Short-lived credential exchanged at the token endpoint |
| ID Token | Cryptographically protected statement about authentication |
| Access Token | Credential used to access protected resources such as UserInfo |
| UserInfo | Endpoint returning claims associated with the authenticated subject |
| `state` | Correlates the authorization response with the initiating client session |
| `nonce` | Binds the authentication response to the client-generated authentication request |
| Issuer | Identifies the OpenID Provider |
| Audience | Identifies the intended client |
| Subject | Stable provider-scoped identifier for the user |

An ID token is not a replacement for an access token. The ID token communicates authentication information to the client. The access token is presented to a protected resource.

## Provider and Client Roles

The implementations model two distinct parties.

The OpenID Provider authenticates the user, issues authorization codes, creates tokens, and exposes UserInfo.

The relying party or OpenID Connect client starts the authentication transaction, validates the returned ID token, verifies the response state, and creates its own application session.

The provider simulator intentionally keeps the protocol mechanics visible. Production systems would normally use standardized JWT signing algorithms and public-key discovery rather than the simplified signing representation used by the executable demonstrations.

## Authorization Code Flow

The implemented flow uses the authorization-code pattern:

1. The client creates a cryptographically unpredictable `state`.
2. The client creates a cryptographically unpredictable `nonce`.
3. The client registers a precise HTTPS redirect URI.
4. The client requests the `openid` scope.
5. The provider authenticates the user.
6. The provider creates a short-lived authorization code.
7. The client exchanges the code at the token endpoint.
8. The provider returns an ID token and access token.
9. The client validates the ID token.
10. The client can use the access token for UserInfo.
11. The application establishes its local authenticated session.

The authorization code is intentionally short-lived and single-use in the models.

## State Protection

`state` protects the authorization response correlation.

The client stores its generated value before redirecting the user. The returned value must exactly match the stored value.

The Python, JavaScript, C++17, and Java implementations demonstrate rejection when the returned state is not the value associated with the authentication transaction.

This check is separate from ID-token signature validation. A correctly signed ID token does not make an authorization response safe if the response is attached to the wrong browser session.

## Nonce Protection

The `nonce` binds the ID token to the authentication request.

The client generates the nonce and retains it during the authentication transaction. The returned ID token must contain the expected nonce.

The implementations reject a token when the nonce differs.

The nonce therefore addresses a different security property from `state`:

| Mechanism | Validation target |
|---|---|
| `state` | Authorization response and client session correlation |
| `nonce` | ID token and authentication request correlation |

Keeping these controls separate avoids treating them as interchangeable.

## ID Token

The ID token is the core OpenID Connect identity artifact.

The examples validate these important claims:

- `iss`
- `sub`
- `aud`
- `iat`
- `exp`
- `nonce`

`iss` must identify the expected OpenID Provider.

`sub` identifies the authenticated subject.

`aud` must identify the client for which the token was issued.

`iat` identifies the token issuance time.

`exp` limits token validity.

`nonce` binds the token to the initiating authentication request.

The client must validate these claims rather than simply decoding the token payload.

The Python and JavaScript examples implement a self-contained HMAC-based simulation so that token-signing mechanics can be demonstrated without external packages. The C++ and Java implementations use a deliberately visible token representation for the same reason.

Real OpenID Connect deployments should use the provider's published JWKS and a supported asymmetric algorithm such as RS256 or ES256 when the provider configuration requires it. Public-key verification allows the relying party to validate signatures without possessing the provider's private signing key.

## UserInfo

UserInfo is a protected resource associated with the authenticated subject.

The implementations return:

- `sub`
- `name`
- `preferred_username`
- `email`
- `email_verified`

The `sub` claim is the primary identity binding. Applications should not assume that an email address is an immutable identity identifier.

The database model separates the provider's subject from the user's email address for this reason.

## Provider Discovery

The PostgreSQL model stores provider metadata:

- Issuer
- Authorization endpoint
- Token endpoint
- UserInfo endpoint
- JWKS URI

The issuer is constrained to HTTPS.

The metadata represents the information a client would obtain from OpenID Connect discovery and provider configuration. The executable language examples use fixed configuration so the authentication mechanics remain visible without requiring network access.

## Redirect URI Validation

Redirect URI registration is modeled explicitly.

The client owns a set of registered HTTPS redirect URIs. The authorization request must use a registered URI.

This prevents a client from arbitrarily selecting an endpoint to which an authorization response may be sent.

The PostgreSQL schema stores redirect URIs independently from client registration so that one client can have multiple controlled callback endpoints.

The database applies an HTTPS constraint at the schema level.

## PKCE

PKCE adds a proof mechanism to the authorization-code exchange.

The Python implementation generates a verifier and derives an S256 challenge. The JavaScript implementation provides the same mechanism using Node.js cryptographic primitives.

The authorization code records the challenge and challenge method. The token exchange requires the verifier when a challenge was supplied.

The JavaScript implementation uses `crypto.timingSafeEqual` when comparing the calculated challenge with the stored value.

The Python implementation uses `hmac.compare_digest` for security-sensitive comparisons.

The database represents PKCE fields with constraints that require an S256 method to have an associated challenge.

## Python Implementation

The Python file models the provider and client as separate classes.

### Provider model

`OIDCProviderSimulator` manages:

- registered users
- authorization codes
- authorization requests
- token creation
- UserInfo

`AuthorizationCode` stores the client, subject, redirect URI, nonce, PKCE challenge, expiration, and consumption state.

The code is marked consumed before the token response is returned. This prevents the same authorization code from being exchanged repeatedly.

### Client model

`OIDCClient` maintains the authentication transaction state and validates:

- issuer
- audience
- nonce
- expiration
- issued-at time
- token structure
- signing algorithm
- signature

The Python implementation also demonstrates explicit failure handling for invalid state and authorization parameters.

### Python-specific mechanisms

The implementation uses:

- `dataclass`
- `Enum`
- dictionaries
- sets
- exceptions
- `secrets`
- `hashlib`
- `hmac`
- Base64 URL encoding
- JSON
- executable assertions

The standard library is sufficient for the demonstration.

## JavaScript Implementation

The JavaScript implementation treats the authentication process as an event-oriented asynchronous workflow.

The `OIDCProvider` manages users and authorization codes using `Map`.

The `OIDCClient` stores authentication transaction values in a `Map` representing client session state.

The `authenticate` method uses asynchronous operations to model the boundaries that normally exist between a browser, identity provider, token endpoint, and UserInfo resource.

### JavaScript-specific security controls

Node.js `crypto` provides:

- secure random values
- SHA-256
- HMAC
- constant-time signature comparison

The implementation explicitly validates the JWT structure before processing claims.

The provider also validates the redirect URI and required `openid` scope before creating an authorization code.

## C++17 Implementation

The C++17 program is designed as a compact identity workflow engine.

Its main domain types are:

- `User`
- `Client`
- `AuthorizationRequest`
- `AuthorizationCode`
- `IdTokenClaims`

`OIDCProvider` owns provider-side state, while `OIDCClient` owns client-side authentication state.

The program uses:

- `std::unordered_map` for provider state
- `std::set` for scopes and registered values
- `std::optional`-style domain thinking through explicit validation
- strongly typed `enum class`
- exceptions
- `std::chrono`
- `std::random_device`
- deterministic workflow objects

The implementation validates issuer, redirect URI, client identity, scopes, authorization-code lifetime, state, nonce, audience, and expiration.

The token representation is intentionally simplified so the complete program remains dependency-free. It should not be interpreted as a production JWT implementation.

## Java 17 Implementation

The Java implementation uses explicit enterprise domain types.

The main records are:

- `User`
- `ClientRegistration`
- `AuthorizationRequest`
- `IdTokenClaims`
- `TokenResponse`

The `OIDCProvider` manages provider state.

`EnterpriseTokenValidator` implements the `TokenValidator` interface and isolates token validation policy from the authentication workflow.

`AuthenticationService` owns the application-side authentication state transition:

`CREATED → AUTHENTICATED`

or:

`CREATED → REJECTED`

Java records provide immutable representations for configuration and claims. Collections are defensively copied through `Set.copyOf`.

Custom exceptions distinguish protocol and policy failures from ordinary application errors.

## PostgreSQL Implementation

The PostgreSQL model represents the identity system relationally.

The principal relationships are:

`Provider → Client → Redirect URI`

`Provider → User`

`Client → Scopes`

`Client → Authentication Session`

`Authentication Session → Authorization Code`

`Client + User → Access Token`

`Client + User → ID Token Event`

`Access Token → UserInfo Request`

The schema contains explicit primary keys, foreign keys, unique constraints, check constraints, indexes, triggers, functions, views, transactions, and sample data.

### Provider tables

`oidc_providers` stores discovery-related provider metadata.

The schema requires HTTPS for the provider endpoints.

### Client tables

`oidc_clients` represents relying-party registration.

`redirect_uris` stores the registered callback endpoints.

`client_scopes` maps clients to permitted scopes.

Confidential clients must have a stored secret hash.

### Identity tables

`oidc_users` stores provider-scoped subject identifiers and user claims.

The `(provider_id, subject)` uniqueness rule prevents two identities from sharing the same subject within one provider.

Email is also unique within a provider in the demonstration model.

### Authentication sessions

`authentication_sessions` records the client-side transaction context.

It stores:

- state
- nonce
- client
- user
- creation time
- expiration time
- completion time
- authentication status

The trigger validates that an active client has at least one registered redirect URI.

### Authorization codes

`authorization_codes` represents short-lived exchange credentials.

The table records:

- code hash
- client
- user
- redirect URI
- nonce
- PKCE challenge
- challenge method
- issuance time
- expiration
- consumption time
- status

The `consume_authorization_code` function performs an atomic state transition from `ISSUED` to `CONSUMED`.

This is important because authorization-code consumption is a state change, not merely a read.

### Access tokens

`access_tokens` records access-token state using a hash rather than storing a demonstration token in plaintext.

The table associates the token with a client and user and records expiration and revocation state.

### ID-token events

`id_token_events` records identity-token issuance metadata.

The database stores issuer, audience, subject, nonce, timestamps, and signing algorithm.

The table is an audit-oriented representation. It does not attempt to perform JWT cryptographic verification inside PostgreSQL.

## Database Integrity

The schema uses database constraints for rules that should not depend solely on application code.

Examples include:

- HTTPS endpoint requirements
- HTTPS redirect URIs
- client-secret requirements
- expiration ordering
- supported signing algorithms
- PKCE challenge relationships
- provider/client foreign keys
- unique provider subjects
- unique redirect URI registration
- unique token hashes
- unique authentication states

The trigger and stored function add workflow-level enforcement.

## Transactional Authorization-Code Exchange

The SQL demonstration inserts an authentication session and authorization code inside a transaction.

The code is then consumed through `consume_authorization_code`.

The function updates the code only when:

- the hash matches
- the client matches
- the redirect URI matches
- the code is still issued
- the code has not expired

The update returns the authenticated user and nonce.

This pattern makes the code transition atomic and prevents an ordinary read-then-update sequence from leaving a larger race window.

## Failure Conditions

The implementations intentionally reject several unsafe conditions.

| Failure | Result |
|---|---|
| Missing `state` | Authorization request rejected |
| Missing `nonce` | Authorization request rejected |
| Unknown client | Authorization request rejected |
| Unregistered redirect URI | Authorization request rejected |
| Missing `openid` scope | Request rejected |
| Unknown authorization code | Token exchange rejected |
| Expired authorization code | Token exchange rejected |
| Reused authorization code | Token exchange rejected |
| PKCE verifier mismatch | Token exchange rejected |
| State mismatch | Client authentication rejected |
| Issuer mismatch | ID token rejected |
| Audience mismatch | ID token rejected |
| Nonce mismatch | ID token rejected |
| Expired ID token | ID token rejected |
| Future-issued token | ID token rejected |
| Unknown UserInfo subject | UserInfo request rejected |

These are distinct validation layers. Passing one layer does not imply that another layer is safe.

## Security Design

The examples apply several security principles.

### Cryptographically random transaction values

`state`, `nonce`, authorization codes, and access tokens use secure random generation in the language implementations.

### HTTPS

Provider metadata and redirect URIs are constrained to HTTPS.

### Short-lived authorization codes

Authorization codes expire quickly and are marked consumed after exchange.

### Exact redirect URI validation

The callback URI is checked against registered client configuration.

### Audience validation

The ID token must be intended for the actual client.

### Issuer validation

The ID token must originate from the configured OpenID Provider.

### Nonce validation

The client verifies that the ID token belongs to the authentication transaction it initiated.

### Constant-time comparisons

The Python and JavaScript implementations use constant-time comparison primitives for security-sensitive values where appropriate.

### Secret handling

The PostgreSQL model stores client secret material as a hash representation rather than a plaintext client secret.

Production systems should also protect signing keys, rotate keys, use secure secret storage, enforce TLS certificate validation, implement token revocation policy where required, and follow the provider's published signing configuration.

## Performance Considerations

The provider implementations use hash-based collections for user and authorization-code lookup.

Expected lookup behavior is approximately constant time for the common in-memory maps, subject to normal hash-table behavior.

The PostgreSQL design adds indexes for the access patterns that matter:

- provider and email lookup
- client authentication sessions
- client/status/expiration authorization-code queries
- user/status/expiration token queries
- subject-based ID-token audit queries

Indexes are not added indiscriminately because every index increases write and storage overhead.

The authorization-code exchange is modeled as a targeted update rather than a broad scan.

## Production Boundary

These files are executable learning artifacts rather than complete production identity providers.

The largest intentional simplification is cryptographic token representation in the C++ and Java examples and HMAC signing in the Python and JavaScript demonstrations.

A production OpenID Connect implementation should normally rely on a standards-compliant provider or carefully implemented protocol library and should validate the provider's discovery metadata, JWKS, signing algorithm, key identifier, issuer, audience, nonce, token timestamps, and other protocol requirements according to the selected flow.

The database should support auditability and transactional state management but should not be treated as a replacement for a dedicated identity provider.

## Educational Distinctions

The project keeps four identity mechanisms separate:

| Mechanism | Responsibility |
|---|---|
| OpenID Connect | Defines authentication and identity semantics |
| Authorization Code | Carries the short-lived result of the authorization step to the token endpoint |
| ID Token | Communicates authenticated identity information to the client |
| Access Token | Authorizes access to protected resources |
| UserInfo | Returns claims about the authenticated subject |
| Application Session | Represents the application's own authenticated state |

The separation is important because an application should not infer that possession of one artifact automatically establishes every other security property.

## Implemented Relationship

The complete technical model is:

`Provider Discovery`
→ `Client Registration`
→ `Authorization Request`
→ `state + nonce`
→ `User Authentication`
→ `Authorization Code`
→ `PKCE Verification`
→ `Token Endpoint`
→ `ID Token + Access Token`
→ `Issuer/Audience/Nonce/Time Validation`
→ `UserInfo`
→ `Application Authentication Session`

The five implementations represent the same identity concepts through different engineering perspectives while retaining explicit protocol boundaries and failure conditions.
