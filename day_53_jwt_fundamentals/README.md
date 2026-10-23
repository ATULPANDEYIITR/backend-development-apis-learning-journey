# JWT Fundamentals

## Scope

This artifact set implements the core mechanics of JSON Web Tokens (JWTs) as a security credential used between a client and an API.

The four central elements are:

| Element | Purpose |
|---|---|
| Header | Describes token metadata such as the token type and signing algorithm |
| Payload | Carries claims about the subject, issuer, audience, timing, identity, roles, and permissions |
| Signature | Provides integrity and authenticity when the verifier possesses the appropriate signing key |
| Expiration | Limits how long a token is accepted |

The implementations deliberately distinguish **encoding**, **integrity verification**, **claim validation**, **authentication**, **authorization**, and **revocation**. A token can have a structurally valid JWT representation while still being unacceptable to an application.

## JWT Compact Structure

A compact JWT normally has three Base64URL-encoded segments:

`header.payload.signature`

Conceptually:

`Header → Payload → Signature`

The header and payload are encoded JSON objects. Base64URL encoding does not provide confidentiality. Anyone who obtains a JWT can normally decode its header and payload without possessing the signing key.

The signature is calculated over the encoded header and encoded payload:

`signature = Sign(encodedHeader + "." + encodedPayload)`

For the symmetric HS256 examples, the same secret is used to produce and verify the HMAC-SHA-256 signature.

## Header

The implementations use a header equivalent to:

`{"alg":"HS256","typ":"JWT"}`

`alg` identifies the cryptographic algorithm expected by the token format. `typ` identifies the token as a JWT.

The verifier does not allow the incoming token to select an arbitrary cryptographic implementation. The configured server policy fixes the expected algorithm. This is important because treating an unverified `alg` value as trusted configuration can create serious authentication vulnerabilities.

The Python, JavaScript, C++, and Java implementations therefore compare the supplied algorithm against their configured policy before accepting the token.

## Payload and Claims

The payload contains claims.

The examples use these registered claims:

| Claim | Meaning | Validation |
|---|---|---|
| `iss` | Issuer | Must match the configured trusted issuer |
| `sub` | Subject | Identifies the authenticated principal |
| `aud` | Audience | Must identify the intended service |
| `iat` | Issued At | Must contain a valid timestamp |
| `exp` | Expiration Time | Token is rejected after the permitted time |
| `jti` | JWT ID | Uniquely identifies an issued token |

Application-specific claims are also represented:

- `roles` identifies application roles such as `developer` and `reviewer`.
- `scope` identifies permitted operations such as `repository:read` and `repository:write`.
- `email_verified` is shown in the Python and JavaScript examples as an application claim.

Registered claims are protected from accidental replacement when new claims are added. The implementations prevent an extension dictionary from overwriting security-sensitive fields such as `iss`, `sub`, `aud`, `iat`, `exp`, and `jti`.

## Expiration

Expiration is evaluated against Unix time.

The basic rule is:

`current_time >= exp → reject`

The examples also support bounded clock skew. A small tolerance can prevent valid credentials from being rejected solely because distributed systems have slightly different clocks.

Clock skew is not a replacement for correct time synchronization. Excessive skew weakens the meaning of expiration and should not be used as a general workaround for incorrect system clocks.

The Python implementation validates both `iat` and `exp`. JavaScript performs the same temporal validation. Java represents timestamps as epoch seconds, while PostgreSQL stores issuance and expiration as `TIMESTAMPTZ` values.

## Signature and Integrity

A JWT signature protects the signed representation from unauthorized modification.

For example, changing:

`"sub":"user-1042"`

to:

`"sub":"admin"`

without recomputing a valid signature causes verification to fail.

The Python implementation uses `hmac.compare_digest` for constant-time signature comparison. JavaScript uses `crypto.timingSafeEqual`. Java uses `MessageDigest.isEqual`.

The C++ program exposes signature verification as an explicit domain boundary and uses a standard-library-only structural signing abstraction. It intentionally documents that production C++ cryptographic implementations should use a vetted cryptographic library rather than implementing cryptographic primitives manually.

The PostgreSQL model does not attempt to reproduce JWT cryptography inside SQL. Instead, it stores token security state, claims, scopes, expiration, and revocation information that a database-backed authentication service can query.

## Authentication Versus Authorization

Authentication answers:

`Who is this principal?`

Authorization answers:

`Is this authenticated principal allowed to perform this operation?`

The implementations keep these responsibilities separate.

Signature verification establishes that the received token was produced with the expected signing key and has not been modified.

Claim validation establishes that the token belongs to the expected issuer and audience and is temporally valid.

Authorization evaluates application-specific claims such as roles and scopes.

For example, a valid token may contain:

`roles = developer, reviewer`

and:

`scope = repository:read repository:write`

A service can require the `reviewer` role and `repository:write` scope before allowing a repository modification.

Possessing a valid JWT does not automatically grant every operation supported by the API.

## Python Implementation

The Python file provides a complete dependency-free JWT workflow.

`b64url_encode` and `b64url_decode` implement the encoding used by compact JWT serialization. The JSON serializer produces compact representations for the header and payload.

`HMACJWT` owns token issuance and verification. Issuance creates the registered claims, generates a unique `jti`, calculates an HS256 signature, and joins the three compact segments.

Verification first checks the three-segment structure, parses the header and payload, enforces the configured algorithm, calculates the expected signature, compares signatures safely, and validates the registered claims.

`TokenRevocationList` demonstrates an important limitation of self-contained tokens. A valid signature does not automatically provide immediate server-side revocation. The example therefore maintains a revocation set keyed by `jti`.

`AuthenticationService` combines cryptographic verification, revocation checking, and role authorization.

The example deliberately tests tampering, revocation, malformed tokens, missing structure, and authorization requirements.

## JavaScript Implementation

The JavaScript implementation uses Node.js built-in cryptographic facilities and an asynchronous API boundary.

`crypto.createHmac` performs HS256 signing. `crypto.timingSafeEqual` compares signature bytes without using an ordinary early-exit string comparison.

`JWTService` is responsible for token construction and validation. `AuthenticationGateway` adds authorization and revocation state above the cryptographic layer.

`simulateApiRequest` introduces an asynchronous boundary using the Node.js event loop. A real service would use the same boundary to perform request parsing, authentication middleware, authorization, database access, and business processing.

The example also modifies the payload while retaining the original signature. Verification rejects the modified representation because the signature no longer corresponds to the signed header and payload.

## C++ Implementation

The C++ program models JWT processing as a repository API security engine.

`ProtectionPolicy` contains trusted issuer, audience, algorithm, clock-skew tolerance, required roles, and required scopes.

`Claims` is a domain structure containing the security-relevant state extracted from a token.

`SignatureEngine` isolates signing behavior from token parsing and policy evaluation. The example uses a deterministic dependency-free signing abstraction so that the complete program can compile with C++17 alone. The source explicitly treats this as a structural demonstration and identifies the need for a vetted cryptographic library in production.

`JWTToken` performs token construction, parsing, signature validation, and claim validation.

`GovernanceEngine` performs the application-level decision after token verification. It can revoke token identifiers and evaluate required roles and scopes.

This separation reflects a production architecture in which cryptographic verification, claim validation, and authorization policy are independent decisions.

## Java Enterprise Model

The Java implementation models authentication using immutable records and explicit failure types.

`JwtPolicy` defines trusted issuer, audience, algorithm, clock tolerance, required roles, and required scopes.

`UserIdentity` represents the principal from which an access token is issued.

`JwtClaims` represents validated token claims.

`AuthenticationFailure` gives callers explicit failure categories such as:

- `INVALID_SIGNATURE`
- `INVALID_ISSUER`
- `INVALID_AUDIENCE`
- `TOKEN_NOT_YET_VALID`
- `TOKEN_EXPIRED`
- `TOKEN_REVOKED`
- `MISSING_ROLE`
- `MISSING_SCOPE`

This makes failure handling more precise than returning an undifferentiated authentication error.

The Java implementation uses the standard JCA/JCE `HmacSHA256` implementation rather than writing HMAC itself. `MessageDigest.isEqual` is used for signature comparison.

`AuthenticationService` applies policy after cryptographic verification. Revocation is represented separately from expiration because those conditions have different meanings: expiration is time-driven, while revocation is an explicit security decision.

## PostgreSQL Model

The PostgreSQL implementation represents JWT-related security state as relational data.

The schema contains:

| Table | Responsibility |
|---|---|
| `applications` | Trusted issuer, audience, and algorithm configuration |
| `users` | Application identities |
| `roles` | Role definitions |
| `user_roles` | User-to-role relationships |
| `jwt_tokens` | Issued token lifecycle and expiration state |
| `token_scopes` | Permissions associated with a token |
| `jwt_claims` | Queryable claim representation |
| `required_claim_policies` | Required registered claims |
| `authorization_policies` | Role and scope requirements |

The database uses foreign keys to maintain relationships and check constraints to prevent invalid token lifecycle states.

A revoked token must have `revoked_at`. An active or expired token cannot have a revocation timestamp. A token must expire after it was issued.

## Token Lifecycle in PostgreSQL

The lifecycle can be represented as:

`issued → active → expired`

or:

`issued → active → revoked`

Expiration is determined by the `expires_at` timestamp. Explicit revocation changes the status to `revoked` and records the time at which the action occurred.

`mark_expired_tokens()` updates active tokens whose expiration time has passed.

`revoke_jwt()` performs an atomic state transition for an active token and raises an exception if the requested token is not active.

The transaction example demonstrates how a state-changing authentication operation can be committed atomically.

## JWT Claims in Relational Form

A JWT is optimized for transport, not relational querying.

The compact token can be transmitted in an HTTP authorization header, while a database can maintain server-side metadata such as:

- token identifier
- subject
- issued time
- expiration
- revocation state
- application
- scopes
- token hash

The `jwt_claims` table provides a queryable representation for auditing and reporting. It should not be interpreted as a replacement for cryptographic verification.

A database record saying that a token exists does not prove that an incoming compact JWT has a valid signature. Those are separate security questions.

## Required Claims and Validation

The schema stores required claim policy explicitly.

The seeded policy requires:

`iss`, `sub`, `aud`, `iat`, `exp`, and `jti`

The application implementations enforce the same concepts procedurally.

A robust verifier should validate more than JSON syntax. It should establish that:

- the token has the expected compact structure;
- the algorithm is allowed;
- the signature is valid;
- the issuer is trusted;
- the audience is intended for the service;
- the subject is valid;
- issuance time is acceptable;
- expiration has not passed;
- application-specific authorization requirements are satisfied.

## Revocation

JWTs are commonly described as stateless credentials because the verifier can validate a signed token without looking up every token in a database.

That does not mean every JWT system must be completely stateless.

The examples show a hybrid model in which:

`signature validity + claim validity + revocation state`

determine whether a credential is accepted.

A revocation list is useful when an application must immediately invalidate a credential before its natural expiration. The trade-off is additional server-side state and a lookup cost.

Short access-token lifetimes can reduce the impact of stolen credentials, while refresh-token systems can provide longer-lived sessions without making access tokens excessively long-lived.

## Security Boundaries

JWT payloads should not contain secrets merely because they are encoded.

Base64URL encoding is reversible. It does not encrypt the payload.

Sensitive information should not be placed in a JWT unless the architecture deliberately provides an appropriate confidentiality mechanism, such as encrypted tokens or another protected transport and storage design.

Signing keys require stronger protection than ordinary configuration values. They should be generated with sufficient entropy and stored using an appropriate secret-management mechanism.

The examples generate secrets programmatically for demonstration. Production services should not hard-code long-term signing secrets in source files.

## Algorithm Selection

The examples intentionally constrain the accepted algorithm to `HS256`.

A production implementation should make the allowed algorithm an explicit server-side policy.

The verifier should not accept an arbitrary algorithm simply because the incoming header contains that algorithm name.

Symmetric HMAC algorithms require the issuer and verifier to possess the same secret. Asymmetric algorithms such as RS256 or ES256 use separate private and public keys, which changes key-distribution and trust-boundary design.

The correct choice depends on the deployment architecture, key-management requirements, and trust relationships.

## Failure Conditions

Important failure cases represented in the implementations include:

| Failure | Reason for rejection |
|---|---|
| Wrong segment count | Token is not valid compact JWT serialization |
| Invalid Base64URL | Header, payload, or signature cannot be decoded |
| Invalid JSON | Header or payload is structurally invalid |
| Unexpected algorithm | Server policy does not permit the supplied algorithm |
| Invalid signature | Token contents cannot be authenticated |
| Issuer mismatch | Token was not issued by the expected authority |
| Audience mismatch | Token was not intended for this service |
| Future `iat` | Token appears to originate from an unacceptable future time |
| Expired `exp` | Token is outside its validity period |
| Revoked `jti` | Token was explicitly invalidated |
| Missing role | Authenticated user lacks the required application role |
| Missing scope | Authenticated token lacks the required operation |

Authentication systems should fail closed. An invalid or ambiguous credential should not be converted into an authenticated identity.

## Performance Considerations

JWT verification is primarily CPU work for cryptographic operations plus claim parsing.

The most important performance considerations are:

- avoid repeated verification of the same token within one request;
- keep access tokens reasonably small;
- avoid excessive custom claims;
- cache trusted public keys where appropriate for asymmetric algorithms;
- use indexed token identifiers when server-side revocation is required;
- index expiration and status when querying active credentials;
- avoid database lookups when the architecture genuinely permits stateless verification.

The PostgreSQL schema indexes active-token expiration and user/status combinations because those fields participate directly in lifecycle and administrative queries.

The `token_scopes` index supports scope-oriented authorization queries.

## Stateless Versus Stateful Decisions

A signed JWT can be verified without storing every issued token.

A stateful revocation model introduces a database or cache lookup but enables immediate invalidation.

The practical architecture can therefore be represented as:

`Client → JWT → Signature Verification → Claim Validation → Authorization`

or, when revocation is required:

`Client → JWT → Signature Verification → Claim Validation → Revocation Check → Authorization`

These are different operational models rather than interchangeable implementations.

## Practical Request Flow

A repository API request using the implemented model can follow this sequence:

`HTTP request`
→ `Authorization: Bearer <JWT>`
→ `parse compact token`
→ `validate header`
→ `verify signature`
→ `validate iss/sub/aud/iat/exp`
→ `check revocation`
→ `evaluate role`
→ `evaluate scope`
→ `execute protected operation`

The signature establishes token integrity and authenticity under the chosen key model.

Claims establish whether the credential is applicable to the current service and time.

Roles and scopes establish whether the authenticated principal may perform the requested operation.

Revocation introduces an explicit server-side security state.

## Design Boundaries

The implementations deliberately keep several concepts separate.

**JWT structure** concerns serialization into header, payload, and signature.

**Claims validation** concerns whether the token's statements satisfy trusted application rules.

**Signature verification** concerns integrity and authenticity.

**Expiration** concerns temporal validity.

**Authentication** establishes the principal represented by the credential.

**Authorization** determines whether that principal can perform an operation.

**Revocation** provides a mechanism for invalidating an otherwise cryptographically valid token.

Combining these into one undifferentiated "JWT check" makes security failures harder to diagnose and policy behavior harder to test.

## Limitations

The Python and JavaScript implementations implement HS256 directly to expose the mechanics without external dependencies. Production systems should generally use a mature, actively maintained JWT and cryptography library rather than maintaining security-critical cryptographic code themselves.

The C++ example intentionally uses a structural signing abstraction because standard C++17 does not provide a complete HMAC-SHA256 implementation. A production C++ service should replace that abstraction with a vetted cryptographic library.

The Java implementation uses the standard Java cryptography APIs and therefore demonstrates a production-oriented cryptographic boundary more directly.

The PostgreSQL implementation models JWT state and authorization metadata but does not replace application-layer cryptographic verification.

None of the examples treats a JWT as encrypted data. Confidentiality and integrity are separate security properties.

The examples also use short-lived access-token patterns and explicit revocation state without implementing a complete refresh-token protocol, key rotation service, distributed cache, or external identity provider. Those mechanisms belong to a larger authentication architecture rather than to the fundamental JWT representation itself.
