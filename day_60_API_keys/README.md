# API Key Lifecycle Management

## Domain Scope

An API key is a credential that allows a client application or service to authenticate to an API. A typical key contains a public identifier and a secret component. The identifier locates the stored credential record. The secret proves possession of the credential.

This implementation covers five connected lifecycle operations:

| Operation | Purpose | Security requirement |
|---|---|---|
| Generation | Create a new credential | Use cryptographically secure random bytes |
| Storage | Retain information needed to verify a credential | Store a keyed verifier, not the plaintext secret |
| Validation | Determine whether a supplied credential is acceptable | Verify the secret, lifecycle state, expiration, and permissions |
| Rotation | Replace an existing credential | Issue a replacement and revoke the old credential consistently |
| Revocation | Permanently disable a credential | Reject subsequent use and preserve an audit record |

The implementations use a credential format similar to `ak_live_<key-id>.<secret>`. The key ID is a public lookup identifier. The secret is the confidential authentication material.

The five implementations use the same basic lifecycle rules but different engineering approaches. Python uses transactional SQLite storage, JavaScript uses an event-driven in-memory vault, C++17 uses an OpenSSL-backed concurrent service, Java 17 models an enterprise service with explicit domain types and policies, and PostgreSQL provides relational persistence and database-level enforcement.

## Security Model

### Credential generation

An API key must contain enough unpredictable entropy to resist guessing and brute-force attacks. All implementations use 32 random bytes for the secret, representing 256 bits of generated secret material.

The secret is encoded for transport:

| Implementation | Secret encoding | Random generator |
|---|---|---|
| Python | URL-safe Base64 without padding | `secrets.token_urlsafe` |
| JavaScript | Base64 URL encoding | Node.js `crypto.randomBytes` |
| C++17 | Hexadecimal | OpenSSL `RAND_bytes` |
| Java 17 | Base64 URL encoding | `SecureRandom` |
| PostgreSQL | Supplied by the application | Generated outside the database |

The public key ID is a separate random 64-bit identifier represented by 16 lowercase hexadecimal characters. It supports record lookup but does not authenticate a request.

A credential should be displayed to its owner only when issued or rotated. A service should never retrieve the original secret from its storage layer because it should not retain that secret.

### HMAC verifier storage

The implementations use HMAC-SHA-256 with a separate pepper.

The application calculates:

\[
V = \operatorname{HMAC}_{SHA256}(P,S)
\]

Where:

- \(V\) is the stored verifier.
- \(P\) is a secret pepper.
- \(S\) is the API key secret.

The pepper must be protected separately from the credential database. A database copy alone should not provide everything required to verify a guessed secret.

During authentication, the application retrieves the verifier associated with the public key ID, calculates a candidate HMAC using the supplied secret, and compares the two values. The comparison must use a constant-time comparison function.

The verifier is not encryption. It cannot be decoded to recover the original secret. Encryption would be necessary if a system had a legitimate requirement to recover and redistribute a secret, which these implementations deliberately avoid.

The pepper must be stable across application restarts when persisted verifier records are used. A randomly generated process-local pepper is suitable only for demonstrations or temporary in-memory operation.

### Authentication and authorization are separate

A valid API key does not automatically grant every operation.

Authentication establishes that the caller possesses an active credential. Authorization checks whether the credential has the scope required by the requested operation.

A key containing `inventory:read` should not be accepted for `billing:write`. The implementations also recognize a wildcard scope, `*`, for cases where an explicitly broad grant is required. Such grants should be restricted because they provide wider access than individual scopes.

The validation sequence is:

1. Parse the credential structure.
2. Extract the public key ID and secret.
3. Locate the stored verifier.
4. Recompute HMAC using the protected pepper.
5. Compare verifier values in constant time.
6. Reject revoked credentials.
7. Reject expired credentials.
8. Check owner and principal status where supported.
9. Check the required scope.
10. Record successful use without exposing the secret.

Malformed credentials and incorrect secrets are rejected. A caller should receive an appropriately generic authentication failure rather than detailed information that reveals whether a particular key ID exists.

## Lifecycle Operations

### Generation

Generation creates a random identifier and secret, calculates the HMAC verifier, and records ownership, label, scopes, and expiration.

The returned object contains the plaintext token only because the issuing caller must deliver it securely to the owner. The database or in-memory record stores the verifier and metadata instead.

Validation includes constraints on:

- Owner and label length.
- Scope names and scope count.
- Expiration values.
- Maximum credential lifetime.
- Public identifier format.
- Verifier length.
- Duplicate scope assignments.

The Python and PostgreSQL models require at least one scope. All implementations reject malformed scope names.

### Storage

Storage must retain enough information to validate credentials and administer their lifecycle without retaining the original token.

The stored record contains:

| Field | Purpose |
|---|---|
| `key_id` | Public identifier used for lookup |
| `owner` | Service or principal responsible for the credential |
| `label` | Operational description |
| `verifier` | HMAC-SHA-256 verifier |
| `scopes` | Granted permissions |
| `status` | Active or revoked |
| `created_at` | Issuance timestamp |
| `expires_at` | Optional expiration timestamp |
| `last_used_at` | Most recent successful use |
| `revoked_at` | Revocation timestamp |
| `rotated_from` | Previous key in the rotation chain |

Audit events record lifecycle activity such as issuance, rotation, and revocation. They must not contain plaintext tokens, secret components, or verifier values.

The database and pepper have different security roles. The database holds verifiers and operational records. The pepper belongs in a protected secret-management system with access restricted to the authentication service.

### Validation

Validation has two independent dimensions:

**Credential validity:** Does the supplied secret match the stored verifier, and is the credential active and unexpired?

**Permission validity:** Does the credential contain the scope required by the requested operation?

A successful result must satisfy both dimensions. This prevents a valid but insufficiently privileged key from being accepted for an unrelated operation.

Typical failure decisions are:

| Condition | Decision |
|---|---|
| Invalid token format | `malformed_token` |
| Unknown key or incorrect secret | `invalid_credentials` |
| Revoked credential | `revoked` |
| Expired credential | `expired` |
| Missing permission | `insufficient_scope` |
| Invalid requested scope | `invalid_scope` |
| All requirements satisfied | `accepted` |

Expired keys can remain stored for audit and administrative reporting. Expiration is an eligibility condition rather than a requirement to immediately delete a record.

### Rotation

Rotation replaces an existing credential with a new independently generated credential.

The replacement inherits the previous key's owner, label, and scopes. Its expiration is either explicitly specified or derived from the remaining lifetime of the old key, depending on the implementation.

The intended sequence is:

    Authenticate old key
           |
           v
    Confirm old key is active
           |
           v
    Generate replacement secret
           |
           v
    Calculate replacement verifier
           |
           v
    Store replacement credential
           |
           v
    Revoke previous credential
           |
           v
    Return replacement secret once

Rotation should be atomic from the perspective of concurrent requests. A partially completed rotation could leave an old credential active without a usable replacement, or create multiple valid credentials unintentionally.

The Python SQLite implementation performs replacement insertion and previous-key revocation inside one transaction. The JavaScript and Java services serialize lifecycle mutations. The C++ implementation protects mutations with a mutex. PostgreSQL locks the old credential row and performs replacement issuance and revocation within the calling transaction.

The application must deliver the new secret securely. It must not place the token in ordinary logs, metrics, audit events, or exception messages.

### Revocation

Revocation permanently changes an active key to a revoked state. The implementations reject subsequent validation attempts.

Revocation is idempotent: revoking an already revoked key does not reactivate it or create a second state transition. Python, JavaScript, Java, and C++ return a result indicating whether a new revocation occurred. PostgreSQL returns a Boolean result.

A revoked key cannot transition back to active. Recovery requires issuing a new credential.

Revocation is appropriate when:

- A key is suspected to have leaked.
- A service or integration is retired.
- An owner loses authorization.
- A credential is no longer needed.
- An incident response process requires immediate credential invalidation.

Revocation should also be considered when an owner is deactivated. The principal's active state and the individual key's status are separate conditions, so a key belonging to a disabled owner should not remain usable merely because its own record says active.

## Implementation Architecture

### Python: Transactional SQLite service

The Python implementation is a self-contained lifecycle manager using standard-library facilities.

| Mechanism | Implementation role |
|---|---|
| `secrets` | Random identifiers and secret components |
| `hmac` and `hashlib` | HMAC-SHA-256 verifiers and constant-time comparison |
| `sqlite3` | Persistent relational storage when configured |
| `dataclasses` | Immutable issuance, validation, and metadata results |
| `threading.RLock` | Serialized access to the SQLite connection |
| Transaction adapter | Commit on success and rollback on exceptions |
| JSON | Safe audit-event details |

`APIKeyStore` owns the SQLite connection and enforces lifecycle operations. The schema separates key metadata, scopes, and audit events into three tables.

The `api_keys` table stores the verifier and lifecycle timestamps. `api_key_scopes` normalizes permission assignments, while `api_key_events` records issuance, rotation, and revocation activity.

`BEGIN IMMEDIATE` serializes SQLite write transactions. This is important for rotation because replacement insertion and old-key revocation must not be separated by another write operation.

The public methods are:

| Method | Behavior |
|---|---|
| `issue` | Validates input, generates a key, stores its verifier and scopes |
| `validate` | Checks verifier, state, expiration, and requested scope |
| `rotate` | Creates a replacement and revokes the old key transactionally |
| `revoke` | Permanently disables a key |
| `metadata` | Retrieves non-secret administrative information |
| `audit_events` | Retrieves lifecycle history |

The demonstration defaults to an in-memory database and a random process-local pepper. Persistent operation uses `API_KEY_DB` and requires a stable `API_KEY_PEPPER` environment variable. The pepper must be stored outside the database and protected from unauthorized application and operator access.

For a persistent local database, configure `API_KEY_DB` with a filesystem path and `API_KEY_PEPPER` with a secret containing at least 32 bytes. The default in-memory configuration can be executed without environment variables.

The SQLite implementation is suitable for a contained service or a single-process deployment. A multi-instance production service should use a database service with an appropriate transaction and concurrency model.

### JavaScript: Event-driven asynchronous vault

The JavaScript implementation models an event-driven credential service.

It uses Node.js built-in cryptographic and event facilities:

| Mechanism | Implementation role |
|---|---|
| `crypto.randomBytes` | Secure random generation |
| `crypto.createHmac` | HMAC verifier calculation |
| `crypto.timingSafeEqual` | Constant-time verifier comparison |
| `Map` | Credential and owner-policy storage |
| `Set` | Scope management |
| `EventEmitter` | Lifecycle event publication |
| `AsyncMutex` | Serialization of asynchronous mutations |
| `Promise` | Asynchronous service interface |

The vault keeps credential records in a private `Map`. The stored object contains verifier bytes and metadata but not the original token.

`AsyncMutex` creates a serialized execution path for issuance, validation, rotation, and revocation. This prevents concurrent asynchronous calls from interleaving lifecycle state changes.

The event system emits metadata-only events. An event includes the operation, key ID, owner, actor, timestamp, and safe relationship information. It does not include token or verifier material.

The optional owner-policy map limits the scopes that can be issued to a principal. This is an issuance-time authorization check, distinct from the scope verification performed during request validation.

The JavaScript implementation is deliberately in-memory. Restarting the process removes its credential records. It is an event-driven service model rather than a durable production repository.

### C++17: OpenSSL-backed vault

The C++ implementation presents the lifecycle from a systems-programming perspective.

It uses explicit domain structures and a vault class:

- `IssuedKey` represents the one-time issuance result.
- `KeyMetadata` represents a sanitized administrative record.
- `ValidationResult` represents an authorization decision.
- `AuditEvent` represents lifecycle history.
- `KeyRecord` is the internal stored representation.
- `KeyStatus` separates active and revoked states.
- `Decision` distinguishes validation outcomes.

OpenSSL provides cryptographic facilities. `RAND_bytes` supplies secure random bytes, `HMAC` computes the keyed SHA-256 verifier, and `CRYPTO_memcmp` compares verifier values without an ordinary early-exit byte comparison.

The `APIKeyVault` protects its records and event history with a mutex. Validation updates the last-used timestamp only after credential, expiration, state, and scope checks succeed.

`std::optional` represents an expiration or rotation origin that may not exist. `std::set` provides unique scopes, while `std::unordered_map` provides average constant-time key lookup.

The C++ implementation stores records in process memory. It does not provide durable persistence or distributed locking. An enterprise deployment would use a durable repository and a concurrency mechanism that covers all participating service instances.

OpenSSL is a deliberate dependency because secure random generation and HMAC are cryptographic operations. Replacing these facilities with `std::rand`, `std::hash`, or a custom digest would not provide an equivalent security guarantee.

Compile the program with a C++17 compiler and OpenSSL development libraries. A typical Linux build command is:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic api_key_lifecycle.cpp -o api_key_lifecycle -lcrypto -pthread`

### Java 17: Enterprise domain and policy service

The Java implementation separates domain types, principal policy, persistence abstraction, and lifecycle behavior.

| Component | Responsibility |
|---|---|
| `KeyStatus` | Explicit credential state |
| `KeyPolicy` | Maximum lifetime and expiration requirements |
| `PrincipalDirectory` | Owner status and permitted scopes |
| `StaticPrincipalDirectory` | Immutable demonstration policy |
| `KeyRepository` | Storage contract |
| `InMemoryKeyRepository` | Demonstration repository |
| `StoredKey` | Internal credential state |
| `APIKeyService` | Issuance, validation, rotation, and revocation |

Java records represent immutable request results, metadata, policies, and audit events. The internal `StoredKey` class keeps mutable lifecycle state while protecting verifier bytes from external modification.

`PrincipalDirectory` separates identity and scope policy from key management. The issuance service checks that the owner is active and that requested scopes are allowed. This prevents a caller from creating a credential with permissions outside the owner's policy.

`KeyRepository` is an interface rather than a hard-coded storage dependency. The demonstration uses an in-memory implementation, but the contract provides a boundary for a durable database repository.

The service methods are synchronized because the demonstration repository is local to one process. A distributed deployment requires transaction isolation or equivalent concurrency control shared by all service instances.

The Java implementation uses a fresh `Mac` instance for HMAC operations. Cryptographic provider objects should not be shared concurrently without an explicit thread-safety guarantee.

The `MessageDigest.isEqual` method performs verifier comparison. Secret arrays are cloned when stored and when accessed through internal repository operations.

The policy requires an expiration date and limits credential lifetime to the configured maximum. This is an explicit enterprise policy choice. A system that needs non-expiring keys can use a different policy, but such keys require additional operational controls.

## PostgreSQL Relational Model

The PostgreSQL script models persistent key management through separate tables and database functions.

### Entity relationships

    principals
        |
        | 1
        |
        | many
        v
    api_keys
        |
        | 1
        |
        +---------- many ---------> api_key_scopes
        |
        |
        +---------- many ---------> api_key_events
        |
        |
        +---------- optional ------> api_keys
                                    rotated_from relationship

`principals` identifies service and integration owners. `api_keys` contains the verifier and lifecycle state. `api_key_scopes` records permissions. `api_key_events` stores lifecycle audit information.

The self-referencing `rotated_from` foreign key connects a replacement credential to its predecessor. The relationship makes rotation history queryable without retaining old plaintext secrets.

### Constraints and indexes

The schema enforces:

- Unique public key identifiers.
- Valid key identifier formats.
- Required owners.
- Fixed-length verifier values.
- Valid lifecycle states.
- Consistent revocation timestamps.
- Future expiration at issuance.
- Valid scope names.
- Unique scope assignments per credential.
- Valid event types and structured event details.

The state trigger prevents verifier, public identity, owner, creation time, and rotation origin from changing after issuance. It also prevents a revoked key from being reactivated.

The audit trigger records issuance and revocation transitions. Ordinary deletion of key records and audit records is blocked. Administrative retention and archival procedures must be designed separately rather than silently deleting lifecycle history.

Indexes support the main access patterns:

| Index | Query pattern |
|---|---|
| Owner and creation time | Administrative key inventory |
| Active expiration | Expiration monitoring |
| Scope and key ID | Permission lookup |
| Key ID and event time | Chronological audit retrieval |

The inventory views exclude verifier bytes. They expose metadata required by service administrators without exposing authentication material.

### Database function responsibilities

| Function | Responsibility |
|---|---|
| `issue_api_key` | Validates ownership and scopes, then inserts the key and scope records |
| `get_api_key_verifier` | Provides restricted verifier retrieval for the trusted authentication service |
| `evaluate_key_eligibility` | Evaluates status, expiration, owner state, and permission |
| `record_successful_key_use` | Records successful use after external cryptographic verification |
| `revoke_api_key` | Revokes a credential and records its state transition |
| `rotate_api_key` | Creates a replacement, copies scopes, and revokes the old key |

The database does not generate a secret token or independently perform its cryptographic verification. Secret generation and HMAC calculation occur in the trusted application. This division prevents database functions from becoming a source of plaintext credentials and allows constant-time comparison in an application cryptographic library.

`get_api_key_verifier` is a privileged boundary. Its result must remain inside the authentication service. Production deployment must grant execution only to a restricted service role.

`record_successful_key_use` assumes the application has already verified the secret. The function rechecks key state, expiration, principal status, and scope while updating the last-used timestamp. A successful database update is not a substitute for verifying the supplied secret.

`rotate_api_key` locks the old row with `FOR UPDATE`. It calls the issuance function to create the replacement, then revokes the previous credential. The caller's transaction provides atomicity: either the replacement and revocation both commit or neither does.

### Audit and reporting

`api_key_inventory` provides a sanitized administrative inventory. `api_key_usage_report` aggregates key counts by owner, including usable, revoked, and expired credentials.

The audit table provides chronological events with actor identity and structured details. The implementation deliberately does not write secrets or verifier bytes into audit data.

The sample data includes:

- Active service principals.
- An inactive integration principal.
- Keys with separate scope sets.
- An expired credential.
- A rejected issuance attempt for an inactive owner.
- Successful and unsuccessful permission checks.
- A replacement credential.
- Permanent revocation.
- Audit and inventory reporting.

The example verifier values are sample data only. They do not represent usable API keys.

## Lifecycle State and Failure Handling

The implementations use two stored states: active and revoked. Expiration is evaluated using a timestamp rather than requiring a background task to change the stored state.

| Condition | Stored state | Validation result |
|---|---|---|
| Newly issued and not expired | Active | Eligible if secret and scope are valid |
| Secret does not match | Active or revoked | Invalid credentials |
| Expiration time has passed | Active | Expired |
| Explicitly revoked | Revoked | Revoked |
| Requested scope is absent | Active | Insufficient scope |
| Owner is inactive | Active | Ineligible where owner policy is checked |

This model keeps an important distinction: expiration is time-dependent, while revocation is an explicit and irreversible state transition.

A record can be active in storage but ineligible because its expiration timestamp has passed. Administrative reports should therefore distinguish stored state from current usability.

### Operational failure cases

**Lost secret:** The original token cannot be recovered from the verifier. Issue a replacement and revoke the old key when its identity is known.

**Incorrect secret:** Reject authentication without returning the stored verifier or revealing unnecessary information about the key record.

**Expired credential:** Reject the request even if the secret matches. Rotation should not silently turn an expired credential into a valid one unless an explicit administrative reissuance process authorizes it.

**Concurrent rotation:** Ensure that only one replacement operation succeeds for a given active key. Transactional row locking or serialized state changes are necessary.

**Repeated revocation:** Treat it as an idempotent operation. Do not transition the credential back to active.

**Insufficient scope:** Reject the requested operation while retaining the ability to use the key for its permitted operations.

**Inactive owner:** Reject credentials belonging to a disabled service or integration, even when their individual key records remain active.

**Database or service failure:** Fail closed. A system should not accept a credential merely because it cannot reach the verifier store or determine current revocation state.

## Testing Coverage

The executable demonstrations verify the principal lifecycle paths.

| Test case | Expected behavior |
|---|---|
| Issue an authorized key | One-time token and public key ID returned |
| Validate the correct secret | Accepted |
| Request a granted scope | Accepted |
| Request an ungranted scope | Insufficient scope |
| Supply malformed token text | Malformed token |
| Supply an incorrect secret | Invalid credentials |
| Rotate an active key | New key issued and old key revoked |
| Validate the old token after rotation | Revoked |
| Validate the replacement token | Accepted within its policy |
| Revoke the replacement | Revoked |
| Validate after revocation | Rejected |
| Repeat revocation | No second state transition |
| Request invalid expiration | Issuance or rotation rejected |
| Request invalid scope | Issuance or validation rejected |
| Use an inactive owner | Issuance rejected where owner policy is enforced |

The source implementations include executable assertions or exception-based checks for these conditions. The PostgreSQL script includes queries and controlled failure demonstrations that can be inspected using the returned results and notices.

## Performance and Scaling Considerations

Credential validation requires a key lookup and a small number of comparisons. With a suitable key-ID index, lookup in a relational database is generally efficient.

The most important performance considerations are operational rather than cryptographic:

- Avoid retrieving every key record for each request.
- Index public identifiers and active expiration scans.
- Keep scope sets normalized in relational storage.
- Avoid writing a full audit event for every successful request unless the audit policy requires it.
- Update last-used timestamps at an appropriate frequency to limit write contention.
- Cache carefully only when revocation propagation and cache invalidation are defined.
- Avoid logging credential material as part of request tracing.

The in-memory JavaScript, C++17, and Java implementations use hash-based collections for average constant-time lookup. Their process-local storage limits durability and horizontal scaling. The Python SQLite model benefits from indexed lookups but is not a distributed key store.

The PostgreSQL implementation provides persistent records and transactional lifecycle operations. For high-volume deployments, usage telemetry can be separated from lifecycle audit records to prevent frequent validation writes from overwhelming administrative history.

## Security and Production Boundaries

The source files implement core credential lifecycle mechanisms, but an enterprise deployment needs additional operational controls.

| Control | Required operational behavior |
|---|---|
| Pepper management | Store outside the credential database; restrict access |
| Transport security | Use TLS for client and service communication |
| Secret delivery | Display the new secret once through a protected channel |
| Logging | Redact tokens, secrets, verifiers, and authentication headers |
| Scope governance | Grant the minimum permissions needed |
| Rotation policy | Define maximum key age and replacement procedures |
| Revocation response | Provide an incident process for immediate invalidation |
| Access control | Restrict issuance, verifier retrieval, rotation, and revocation |
| Audit retention | Protect lifecycle history from unauthorized modification |
| Backups | Protect database backups and pepper backups independently |
| Failure behavior | Reject authentication when authoritative validation is unavailable |

The database schema is not a complete identity-management platform. Production systems must also authenticate operators, authorize management actions, manage service identities, define retention rules, and protect database roles.

The in-memory implementations are executable technical models rather than distributed persistence services. The SQLite version is suitable for a local demonstration or contained deployment. The PostgreSQL model illustrates a more durable service boundary, with application-side cryptographic verification and database-side state enforcement.

## Execution Requirements

| Deliverable | Runtime | External dependency |
|---|---|---|
| Python | Python 3.9 or later | None |
| JavaScript | Node.js 18 or later | None |
| C++17 | C++17 compiler | OpenSSL development libraries |
| Java | Java 17 or later | None |
| PostgreSQL | PostgreSQL 15 or later | PostgreSQL server |

The Python, JavaScript, and Java implementations use in-memory defaults for standalone execution. The C++ implementation also keeps records in process memory. The PostgreSQL implementation creates its own schema, tables, functions, triggers, sample records, views, and demonstration queries.

The PostgreSQL file begins by dropping the `api_key_mgmt` schema. It is intended for an isolated learning database because executing it again replaces that schema and its contents.

## Technical Distinctions

The implementations deliberately separate several concepts that are often combined incorrectly:

| Concept | Meaning |
|---|---|
| Key ID | Public record identifier |
| Secret | Random confidential credential component |
| Verifier | Keyed digest used to verify the secret |
| Pepper | Secret cryptographic value protected outside the database |
| Scope | Permission associated with a credential |
| Expiration | Time after which a credential is no longer eligible |
| Revocation | Permanent administrative invalidation |
| Rotation | Replacement of an existing credential |
| Last use | Timestamp of the most recent successful validation |
| Audit event | Record of a lifecycle operation |

A public key ID is not a credential by itself. A stored verifier is not the original secret. Authentication is not authorization. Expiration is not revocation. Rotation is not merely issuing another key: it requires a controlled transition between the old and replacement credentials.

These distinctions determine how the five implementations generate credentials, store verifiers, evaluate access, preserve lifecycle history, and handle failures.
