# Authentication Fundamentals

## Scope

This project models the foundations of application authentication without treating identity, credentials, sessions, and authorization as the same mechanism.

The central relationship is:

Identity → Credential Verification → Authentication → Session → Authorization

An identity answers **who the account represents**.

Authentication answers **whether the presented credentials establish that identity**.

A session represents an authenticated state that can be reused across requests for a limited period.

Authorization answers **what an authenticated identity is permitted to do**.

These boundaries matter because successfully proving an identity does not automatically grant access to every protected operation.

| Concern | Primary question | Example mechanism |
|---|---|---|
| Identity | Which account is being referenced? | User ID and username |
| Credential | What secret or authenticator proves the identity? | Password-derived verifier |
| Authentication | Did the supplied credential authenticate the identity? | Password verification |
| Session | Is authenticated state still valid? | Session identifier and expiration |
| Authorization | Is the authenticated identity allowed to perform an action? | Role membership |

## Authentication Model

The implementations use a password-based authentication model.

A password should not be stored as plaintext. The Python and Java implementations use PBKDF2-HMAC-SHA256 with a unique salt and a deliberately expensive work factor. The JavaScript implementation uses Node.js `crypto.pbkdf2Sync`.

The C++ implementation contains a deliberately marked demonstration KDF because the C++17 standard library does not provide a production password-hashing primitive. A production C++ service should use a vetted cryptographic library rather than replacing a password KDF with an application-defined construction.

The credential representation is conceptually:

`password + unique salt + work factor → password-derived verifier`

Authentication then derives a verifier from the supplied password and compares it with the stored verifier.

The stored credential record contains a salt and verifier rather than the original password.

## Identity and Account State

Account identity is represented separately from authentication state.

An account can be:

- `active`
- `locked`
- `disabled`

A locked account can result from repeated failed authentication attempts.

A disabled account may be intentionally prevented from authenticating even when its credential is correct.

The account state therefore participates in authentication decisions but is not itself a credential.

The Python implementation uses the `User` dataclass. JavaScript uses an object-based domain representation. C++ uses `User` as a value type managed by a repository. Java uses an immutable `Identity` record and explicit state transitions.

## Sessions

A successful authentication creates a session.

The session contains:

- a random session identifier
- the authenticated identity
- creation time
- expiration time
- session status

A session is not a replacement for identity. It is an authenticated-state reference associated with an identity.

The session lifecycle is:

`Created → Active → Expired`

or:

`Created → Active → Revoked`

Expiration occurs when the current time passes the session's expiration timestamp.

Revocation is explicit and invalidates the session before natural expiration.

The examples reject sessions that are:

- unknown
- revoked
- expired
- associated with a disabled or locked identity

Short-lived sessions reduce the period during which a stolen session identifier can remain useful. Real systems can also use secure cookie attributes, TLS, session rotation, CSRF protections where applicable, device/session management, and server-side revocation.

## Authentication and Authorization Are Different

A successful authentication does not mean that every protected operation is allowed.

For example:

`alice + valid password → authenticated`

does not imply:

`alice → administrator operation allowed`

The second decision requires authorization data.

The examples model roles such as:

- `user`
- `administrator`
- `auditor`

An identity can authenticate successfully while lacking the role required for a protected operation.

This distinction prevents a common architectural error where authentication success is incorrectly treated as universal permission.

## Python Implementation

The Python implementation models a complete authentication service with explicit domain objects.

`PasswordRecord` stores the credential-verification parameters.

`User` stores identity, account state, roles, and failed authentication attempts.

`Session` stores authenticated state and its lifetime.

`PasswordHasher` encapsulates PBKDF2 password derivation and constant-time comparison through `hmac.compare_digest`.

`AuthenticationService` owns:

- identity registration
- credential verification
- failed-attempt tracking
- account lockout
- session issuance
- session validation
- logout
- role authorization

The script also demonstrates an expired session without waiting for the real clock. The expiration timestamp is moved into the past so the failure path can be exercised deterministically.

The credential store demonstrates the intended storage boundary: a salted password-derived verifier is retained rather than a plaintext password.

## JavaScript Implementation

The JavaScript implementation uses Node.js rather than browser APIs so cryptographic operations can be performed through the standard `crypto` module.

`CredentialService` uses:

`crypto.pbkdf2Sync`

for password verification.

The implementation uses `Map` for identity and session lookup and `Set` for roles.

The authentication service separates:

`register()`

from:

`authenticate()`

and from:

`authenticateRequest()`

This makes the difference between initial credential authentication and subsequent session validation explicit.

`simulateProtectedRequest()` adds an asynchronous application boundary. It represents a protected operation that must first authenticate the session and then verify the required role.

The service also demonstrates session revocation and account lockout.

## C++ Implementation

The C++ program models authentication as a repository-oriented service.

The repository owns identity and session state and exposes operations for:

- registration
- credential verification
- session creation
- session authentication
- role authorization
- session revocation

`unordered_map` provides average constant-time lookup by username or session identifier.

`unordered_set` represents roles.

The implementation uses a constant-time string comparison function when comparing demonstration credential verifiers.

The C++ standard library does not provide a complete production password-hashing framework. The program therefore explicitly labels its internal KDF as a demonstration mechanism. This avoids presenting an application-defined hashing routine as a security primitive.

The design decision is important: cryptographic correctness should come from a vetted implementation rather than from a custom security algorithm.

## Java Implementation

The Java implementation uses domain-oriented types suitable for an enterprise service.

The main domain types are:

- `Identity`
- `Session`
- `PasswordRecord`
- `Role`
- `AccountStatus`
- `SessionStatus`

Java records provide compact immutable value objects.

The `PasswordVerifier` interface separates the authentication service from the password-derivation implementation.

`Pbkdf2PasswordVerifier` uses Java's standard cryptographic APIs:

`SecretKeyFactory`

with:

`PBKDF2WithHmacSHA256`

The `Identity` record models state changes through methods such as `withFailedAttempts()` and `withRoles()` rather than exposing mutable fields directly.

This creates an explicit domain transition model:

`ACTIVE → LOCKED`

after repeated authentication failures.

Authorization is represented as a separate service operation. The authentication service first validates the session and then checks whether the required `Role` exists in the identity's role set.

## PostgreSQL Model

The PostgreSQL implementation represents authentication as relational state.

The principal tables are:

| Table | Responsibility |
|---|---|
| `users` | Identity and account state |
| `credentials` | Password-verification metadata |
| `roles` | Defined authorization roles |
| `user_roles` | Identity-to-role relationship |
| `sessions` | Authenticated session state |
| `login_events` | Authentication audit history |
| `authorization_audit` | Authorization decisions |

The schema deliberately does not store plaintext passwords.

`credentials.user_id` is unique so an identity has one current credential record in this model.

Foreign keys preserve relationships between identities, credentials, roles, sessions, and audit records.

Check constraints enforce valid state values.

Indexes target actual lookup patterns:

`idx_sessions_user_active` supports session validation by identity and active state.

`idx_login_events_username_time` supports recent authentication-event lookup for a username.

`idx_authorization_user_time` supports authorization-audit retrieval by identity and time.

## Database-Level Authentication Rules

The `record_failed_login()` function records a failed authentication event and increments the identity's failure counter.

Once the failure count reaches five, the account is changed to `locked`.

This is intentionally implemented inside the database workflow so the login event and account-state change can remain consistent.

The `authorize_session()` function first checks:

- session existence
- active session state
- session expiration
- active account state

Only after authentication state is valid does it check the requested role.

This reproduces the conceptual boundary:

`authenticated session → authorization evaluation`

A revoked session cannot regain access simply because the underlying user has the required role.

## Auditability

Authentication and authorization produce different types of audit evidence.

`login_events` records authentication outcomes.

Examples include:

- successful login
- invalid credentials
- unknown identity

`authorization_audit` records permission decisions.

This distinction is useful during security investigations because a successful login and an authorization denial answer different questions.

A system can therefore show:

`Authentication succeeded`

while separately recording:

`Authorization denied because required role was absent`

## Failure Conditions

The implementations explicitly handle several failure conditions.

### Invalid credentials

The password verifier rejects the supplied credential.

The caller receives a generic authentication failure rather than a detailed message indicating whether the username or password was incorrect.

This reduces account-enumeration information.

### Repeated failures

Failed attempts are counted.

After the configured threshold, the account is locked.

Real production systems should consider distributed rate limiting, IP and device signals, alerting, credential-stuffing defenses, recovery workflows, and denial-of-service risks before relying on a simple per-account counter.

### Expired sessions

An expired session is rejected even if the identity itself remains active.

### Revoked sessions

Logout or administrative revocation invalidates an otherwise unexpired session.

### Disabled identities

A valid session should not remain usable indefinitely after the associated identity is disabled. The examples check account state during session authentication.

### Missing authorization role

A successfully authenticated identity can still be rejected because the required role is absent.

## Security Considerations

Passwords should never be logged, displayed, or stored in plaintext.

Password verification should use a dedicated password KDF with an appropriate work factor. The exact work factor should be selected through current security guidance and performance testing rather than copied blindly from an example.

Authentication endpoints should use encrypted transport.

Session identifiers should be generated using a cryptographically secure random source.

Session identifiers should not be placed in URLs because URLs can leak through logs, browser history, referrers, and monitoring systems.

For browser applications, session cookies should normally use appropriate `Secure`, `HttpOnly`, and `SameSite` settings.

Credential and session secrets should not appear in application logs.

Authentication failures should be monitored without turning audit records into a source of sensitive credential information.

Authorization checks should be performed server-side. Hiding an interface element is not an authorization mechanism.

## State Relationships

The complete conceptual flow is:

`Identity`

↓

`Credential Verification`

↓

`Authentication Decision`

↓

`Authenticated Session`

↓

`Authorization Decision`

↓

`Protected Resource`

A failure at one stage should not silently become success at another stage.

For example:

`Invalid credential → no authenticated session`

`Expired session → no authenticated request`

`Authenticated session + missing role → authorization denied`

`Revoked session + correct role → authorization denied`

This separation is the central architectural principle represented by all five implementations.

## Practical Trade-offs

In-memory repositories are useful for demonstrating state transitions but do not provide persistence, horizontal scalability, distributed session coordination, or durable audit storage.

Database-backed sessions provide centralized state but introduce database availability and latency considerations.

Server-side sessions make revocation straightforward because the server controls session state.

Stateless tokens can reduce server-side session storage but introduce different concerns around expiration, revocation, key management, replay, and token scope.

Role-based authorization is simple for many applications, but complex enterprise systems may require additional attributes, resource ownership rules, contextual conditions, or policy engines.

Authentication strength and authorization complexity are separate dimensions. Strong authentication does not compensate for incorrect authorization rules, and elaborate authorization policies do not compensate for weak credential protection.
