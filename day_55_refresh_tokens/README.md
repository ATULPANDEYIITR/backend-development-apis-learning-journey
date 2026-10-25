# Refresh Token Lifecycle and Authentication Governance

## 1. System Overview

Refresh-token management separates short-lived API authorization from the ability to obtain new access credentials. This separation limits how long a stolen access token remains usable while allowing an authenticated session to continue without requiring the user to enter credentials repeatedly.

The implementations model opaque access and refresh tokens, session state, expiration, rotation, revocation, reuse detection, audit events, and policy enforcement.

### Core responsibilities

| Component | Responsibility |
|---|---|
| Access token | Authorizes requests until its expiration or the associated session is revoked |
| Refresh token | Requests a replacement token pair when the current refresh credential is valid |
| Token rotation | Replaces the current refresh token and invalidates its predecessor |
| Session | Groups credentials under a user identity and a maximum lifetime |
| Revocation | Prevents a session or refresh credential from continuing to authorize operations |
| Reuse detection | Identifies attempts to use a refresh token that has already been consumed |
| Token policy | Defines token lifetimes and behavior when reuse is detected |
| Audit record | Captures security-relevant lifecycle events without recording raw credentials |

## 2. Access Tokens and Refresh Tokens

Access tokens and refresh tokens serve different purposes and should not be treated as interchangeable credentials.

### Access tokens

An access token is presented to a protected API. The server validates the credential and its associated session before allowing the operation.

The implementations use a short access-token lifetime, typically five minutes. The actual expiration is the earlier of the access-token expiration and the session expiration.

An expired access token must not authorize a request. The client can request a replacement pair using its current refresh token, provided that the refresh session remains valid.

### Refresh tokens

A refresh token is presented to the authentication service rather than used as a general API authorization credential. It can establish a new access-token lifetime, making it more powerful over the course of a session.

The examples use opaque, randomly generated credentials. The server stores token hashes as lookup keys rather than storing the raw refresh credentials.

A refresh token must be rejected when it is unknown, expired, revoked, rotated, or inconsistent with the current session generation.

### Comparison

| Property | Access token | Refresh token |
|---|---|---|
| Main purpose | Authorize API requests | Obtain replacement credentials |
| Typical lifetime | Minutes | Hours or days |
| Rotation | Reissued during refresh | Replaced on every successful rotation |
| Storage | Protected client storage | Especially protected client storage |
| Server-side state | May be tracked for revocation | Must track current generation and lifecycle |
| Reuse implications | Depends on token design | Reuse of a consumed token can indicate credential theft |

## 3. Token Lifecycle

A typical lifecycle follows these transitions:

    User authentication
           |
           v
    Create authenticated session
           |
           v
    Issue access token + refresh token
           |
           v
    Access token authorizes requests
           |
           +---- Access token expires
           |             |
           |             v
           |      Validate refresh token
           |             |
           |             v
           |      Consume old refresh token
           |             |
           |             v
           |      Issue replacement token pair
           |             |
           |             +---- Repeat while session remains valid
           |
           +---- Logout or security event
                         |
                         v
                  Revoke session

The session has its own maximum lifetime. Refreshing credentials does not extend that absolute expiration in these implementations.

A session can also become expired or revoked independently of an individual access token.

## 4. Refresh-Token Rotation

Rotation issues a new refresh token whenever the current refresh token is successfully exchanged. The predecessor becomes unusable.

For a session with generation \(g\), a successful rotation produces generation \(g+1\).

The essential invariants are:

- Only one refresh token is current for a session.
- The presented token must match the current refresh-token hash.
- The token must be active and unexpired.
- Its generation must match the session generation.
- The previous token must be marked as consumed before the replacement becomes current.
- The rotation must be atomic.

If two requests attempt to rotate the same token concurrently, only one may succeed. A database implementation must enforce this using transactions and row locks or an equivalent concurrency-control mechanism.

### Reuse detection

Suppose a client successfully rotates token R1 into token R2. A subsequent attempt to exchange R1 must fail.

The examples can treat this event as a potential compromise. When the configured policy requires revocation, the associated session is revoked and its refresh-token family is invalidated.

Reuse detection is a security signal, not definitive proof of theft. Network retries, concurrent browser requests, and clients with multiple workers can accidentally reuse credentials. Clients should coordinate refresh operations and handle failed exchanges without repeatedly submitting an obsolete token.

## 5. Expiration and Revocation

Expiration and revocation have different causes.

**Expiration** is time-based. A token or session becomes unusable when its expiration time is reached.

**Revocation** is an explicit security decision. A user logout, administrator action, compromised credential, or reuse-detection event can invalidate a session before its scheduled expiration.

The session-level revocation model also invalidates access tokens associated with that session when the authorization service checks session state.

This requires a server-side state lookup or a distributed revocation mechanism. A completely stateless access-token validator cannot immediately observe a server-side revocation unless an additional mechanism communicates the change.

Revoking a refresh token alone does not automatically invalidate every independently issued access token unless the system explicitly connects the two operations.

## 6. Python Implementation

The Python file implements an in-memory `TokenService` using standard-library components.

### Design

- `TokenPair` is an immutable data class containing both credentials and their expiration timestamps.
- `RefreshSession` tracks the user, current refresh-token hash, generation, expiration, and revocation state.
- `SessionStatus` defines active, revoked, and expired session states.
- `TokenService` manages login, access authentication, rotation, revocation, and audit snapshots.
- `RLock` protects shared state during concurrent operations.
- `secrets.token_urlsafe` generates opaque credentials.
- SHA-256 hashes provide lookup keys without retaining raw credentials.
- `unittest` verifies rotation, reuse rejection, revocation, and input validation.

The demonstration authenticates a user, rotates a refresh token, attempts to reuse its predecessor, and revokes the resulting session.

### Limitations

The in-memory dictionaries are not durable. Restarting the process loses all sessions and token records. The global lock serializes operations within a single process, but it does not coordinate multiple server instances.

The refresh lookup also scans sessions to find the matching hash, giving it linear lookup complexity in the number of sessions. A production implementation would maintain a dedicated hash-to-session index or use a database index.

## 7. JavaScript Implementation

The JavaScript file provides an event-driven token ledger for Node.js.

### Design

- `EventEmitter` publishes structured audit events.
- `Map` stores sessions, refresh-token records, and access-token records.
- Node.js cryptographic functions generate random tokens, hashes, and session identifiers.
- `exclusive()` serializes mutations within the current process.
- `refresh()` validates the current credential, records rotation, and detects reuse.
- `policyReport()` evaluates whether a session remains eligible for continued use.
- `revokeSession()` invalidates the session and its refresh-token records.

The event stream captures session creation, refresh rotation, expiration, revocation, and replay detection. Audit records contain identifiers and lifecycle metadata rather than raw credentials.

The process-local promise queue is suitable for a small demonstration but is not a distributed locking mechanism. A production service requires database transactions or another coordination mechanism that works across application instances.

## 8. C++17 Implementation

The C++ program models a token-governance engine with explicit session and token states.

### Design

- `Session` represents an authenticated session.
- `TokenRecord` tracks refresh-token state and generation.
- `AccessRecord` records access-token expiration.
- `TokenPair` groups issued credentials and their lifetime metadata.
- `Evaluation` reports whether a token operation is allowed and why.
- `GovernanceEngine` handles issuance, authentication, rotation, and revocation.
- STL unordered maps provide average constant-time credential lookups.

The engine evaluates invalid credentials, expired sessions, revoked sessions, token reuse, and stale generations through explicit decision codes.

This implementation emphasizes domain modeling and explicit eligibility decisions. Its opaque identifiers are suitable for illustrating state transitions, but the random-number engine used in the example is not cryptographically secure. A real authentication service must use a cryptographically secure random generator and must never expose raw tokens in logs.

## 9. Java 17 Implementation

The Java program uses an enterprise-oriented domain model with explicit policies and service boundaries.

### Domain types

| Type | Responsibility |
|---|---|
| `Session` | Stores identity, lifetime, state, and current generation |
| `TokenRecord` | Represents the state and expiration of an issued credential |
| `TokenPair` | Immutable result of token issuance or rotation |
| `Principal` | Represents an authenticated user and session |
| `TokenPolicy` | Defines token lifetimes and reuse behavior |
| `StandardTokenPolicy` | Validates the configured lifetime relationship |
| `AuthenticationException` | Communicates typed authentication failures |
| `PolicyResult` | Reports token eligibility and its reason |

`TokenService` coordinates issuance, authentication, rotation, revocation, and audit collection. A `ReentrantLock` protects shared in-memory state, and `Clock` makes time-dependent behavior explicit.

The reuse policy determines whether an obsolete refresh token causes session-wide revocation. The implementation also checks token generation, rather than relying solely on a token's stored status.

Java's immutable records are used for result objects and policy configuration. The service still requires persistent transactional storage when deployed across multiple application instances.

## 10. PostgreSQL Implementation

The SQL file represents token lifecycle behavior in a relational database. It targets PostgreSQL 15 or later and uses PostgreSQL-specific types, functions, partial indexes, row locks, and PL/pgSQL.

### Relational model

    app_users
       |
       v
    auth_sessions
       |
       +---- access_tokens
       |
       +---- refresh_tokens ---- replaced_by
       |
       +---- token_audit

    token_policy
       |
       +---- session creation and token issuance rules

### Important database structures

**`app_users`** stores user identities and account enablement.

**`auth_sessions`** stores session status, maximum expiration, current generation, and current refresh-token hash.

**`refresh_tokens`** preserves token history, including rotation status, consumption time, generation, and replacement relationships.

**`access_tokens`** stores access-token hashes and expiration timestamps.

**`token_policy`** defines access and refresh lifetimes and whether refresh-token reuse should trigger revocation.

**`token_audit`** records lifecycle events for operational investigation.

The `one_active_refresh_per_session` partial unique index prevents multiple active refresh tokens from being stored for one session.

### Transactional rotation

`rotate_refresh_token` locks the associated session using `FOR UPDATE`, reloads the refresh-token record, verifies its current state, and checks expiration and generation.

A successful rotation marks the predecessor as rotated, inserts replacement credentials, links the old token to the new token, increments the session generation, and records an audit event.

These changes occur within the caller's transaction. If the operation raises an exception, its changes must be rolled back to avoid leaving a partially completed rotation.

The `protect_refresh_token_history` trigger prevents changes to immutable token identity fields and rejects invalid finalized-state transitions.

### Access authentication

`authenticate_access` returns an authenticated identity only when the access token exists, remains unexpired, belongs to an active session, and is associated with an enabled user.

The function returns no rows for invalid credentials. Callers must interpret an empty result as authentication failure.

### Reporting

The SQL includes queries for:

- Active-session reporting and token counts.
- Access-token authentication.
- Session status and expiration.
- Refresh-token generations and replacement relationships.
- Audit-event aggregation.
- Detection of active sessions without exactly one active refresh token.

The example credentials in the SQL are test values, not secure production credentials. Application code must generate tokens using a cryptographically secure random generator and supply only the corresponding hashes to the database.

## 11. Security and Operational Considerations

### Credential storage

Refresh tokens are bearer credentials: possession can be sufficient to use them. Protect them from browser scripts, application logs, analytics, URLs, and untrusted storage.

For browser applications, appropriately configured `HttpOnly`, `Secure`, and `SameSite` cookies can reduce credential exposure. Cookie-based authentication also requires a deliberate CSRF defense. Mobile and desktop clients require platform-appropriate secure storage.

### Hashing and token generation

Use cryptographically secure random generation for opaque credentials. A token hash is useful only if the token has sufficient randomness to resist guessing. Low-entropy credentials require different protections.

Do not store raw refresh tokens in databases or write them to logs. Hashes should be compared and managed through carefully controlled authentication operations.

### Concurrency and retries

Concurrent refresh requests can cause legitimate clients to submit a token that has already been rotated. Coordinate refresh operations per session, make state changes atomic, and design client retries carefully.

Reuse detection policies should consider the consequences of legitimate races and stolen-token scenarios. A grace period, if supported, must be designed to avoid accidentally allowing a compromised credential to remain usable.

### Distributed deployment

A production deployment may have several authentication servers. Process-local locks do not protect shared state across those servers. Database transactions, row locks, unique constraints, and consistent session lookups provide stronger coordination.

### Revocation latency

Immediate revocation requires protected operations to observe current session state. Caching active-session decisions improves performance but can introduce a delay before revocation takes effect.

Short access-token lifetimes limit exposure when an access token cannot be revoked immediately. The chosen balance depends on security requirements and request volume.

### Audit quality

Audit events should capture event type, session identity, generation, timestamp, and relevant non-secret metadata. They should not include raw access tokens, raw refresh tokens, passwords, or other credentials.

Production audit records should be access-controlled, monitored for suspicious activity, and retained according to operational and legal requirements.

## 12. Implementation Boundaries

These files are learning implementations rather than complete production identity providers.

- Python, JavaScript, and Java use process-local state and do not provide durable distributed session management.
- The C++ example illustrates governance decisions but does not provide a production-grade credential store.
- PostgreSQL supplies transactional persistence and relational constraints, but application-side cryptographic generation, authorization, secure transport, and database permissions remain necessary.
- The examples use opaque tokens. JWT-based systems require additional signature, issuer, audience, algorithm, and claim validation controls.
- Refresh-token rotation does not replace user authentication, account-disable checks, session policy, or authorization checks for individual API operations.

The central design requirement is to treat token issuance, rotation, expiration, and revocation as coordinated security state transitions rather than independent credential-generation operations.
