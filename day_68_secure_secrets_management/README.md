# Secure Secrets Management

## 1. Technical Scope

Secure Secrets Management concerns the controlled creation, storage, retrieval, distribution, rotation, and revocation of sensitive application credentials.

Secrets include:

- Database passwords
- API keys
- OAuth client secrets
- Access tokens
- Private keys
- Signing credentials
- Encryption keys
- Service-to-service authentication credentials

The implementations demonstrate four connected areas:

| Area | Purpose |
|---|---|
| Environment variables | Supply configuration to applications without embedding credentials in source code |
| Credential management | Control access to sensitive authentication material |
| Secret rotation | Replace credentials through controlled version transitions |
| Secret managers | Centralize protected storage, access policies, and lifecycle management |

The Python, JavaScript, C++17, and Java 17 programs implement in-memory educational secret managers. The PostgreSQL implementation provides relational lifecycle and governance management.

The implementations deliberately distinguish credential values from their metadata.

## 2. Fundamental Security Concepts

### 2.1 What is a secret?

A secret is sensitive information whose unauthorized disclosure or modification could compromise an application, system, service, or data resource.

A database password may allow access to confidential records. A payment-provider API key may permit financial transactions. A private signing key may allow an attacker to impersonate a trusted service.

Secret management therefore requires protection of three security properties:

- Confidentiality: unauthorized identities cannot retrieve secret values.
- Integrity: unauthorized identities cannot modify, replace, or revoke credentials.
- Availability: authorized applications can retrieve valid credentials when required.

### 2.2 Secrets versus ordinary configuration

Configuration describes how an application operates. Secrets authenticate or authorize access to protected resources.

| Configuration | Secret |
|---|---|
| Application port | Database password |
| Logging level | API key |
| Service hostname | OAuth client secret |
| Feature flag | Private signing key |
| Connection timeout | Access token |

Configuration may be stored in ordinary configuration files when appropriate. Sensitive authentication values require stronger protection.

### 2.3 Credentials and cryptographic keys

Credentials establish identity or authorize access.

Cryptographic keys have additional requirements concerning key generation, usage restrictions, cryptographic algorithms, storage, and lifecycle.

A database password, API token, encryption key, and TLS private key should not automatically share the same storage, rotation, or usage policies.

The programs model general-purpose credentials. They do not implement a complete cryptographic key-management system.

## 3. Environment Variables

### 3.1 Purpose

Environment variables provide configuration to a process through its execution environment.

They separate application configuration from source code and allow deployment environments to supply different settings.

Typical examples include:

- `DATABASE_HOST`
- `DATABASE_PORT`
- `DATABASE_PASSWORD`
- `PAYMENT_API_KEY`
- `OAUTH_CLIENT_SECRET`

The Python implementation uses `os.environ`, the JavaScript implementation uses `process.env`, and the Java implementation demonstrates configuration validation using a supplied environment map.

The C++ implementation focuses on lifecycle and access-control behavior rather than environment-variable integration.

### 3.2 Configuration validation

Applications should validate configuration before initializing dependent services.

Important checks include:

- Required variable exists.
- Value is not empty.
- Port numbers fall within valid ranges.
- Secret names follow an approved naming convention.
- Configuration belongs to the correct environment.
- Production credentials are not accidentally reused in development.

A missing credential should produce a controlled initialization failure rather than silently selecting an insecure default.

### 3.3 Environment-variable limitations

Environment variables are not themselves a secure secret manager.

Potential exposure paths include:

- Process inspection
- Diagnostic dumps
- Container inspection
- Crash reports
- Debugging tools
- Deployment configuration
- Child-process inheritance
- Misconfigured monitoring systems

They may also remain available throughout the lifetime of a process.

A production architecture should retrieve credentials from an authenticated secret provider and expose them to applications only when required.

## 4. Credential Storage and Secret Managers

### 4.1 Secret-manager architecture

A secret manager provides centralized control over sensitive credentials.

Its main responsibilities include:

- Secure credential storage
- Authentication of requesting identities
- Authorization of individual operations
- Version management
- Rotation workflows
- Expiry management
- Revocation
- Audit recording
- Integration with applications and deployment environments

A typical architecture is:

Application identity
    |
    v
Authentication
    |
    v
Authorization policy
    |
    v
Secret manager
    |
    v
Credential provider
    |
    v
Protected downstream service

The application should receive only the credentials it is authorized to access.

### 4.2 Secret-provider abstraction

The Java implementation defines a `SecretProvider` interface.

This separates application-facing operations from the storage implementation.

The Python implementation uses a `SecretProvider` protocol. The JavaScript implementation defines an asynchronous provider contract. The C++ implementation encapsulates provider behavior in `SecretManager`.

The same architectural principle applies across all four languages: application logic should depend on a defined secret-management interface rather than directly accessing internal storage.

### 4.3 Secret-manager storage

A production secret manager should provide appropriate protections such as:

- Encryption at rest
- TLS-protected communication
- Strong identity authentication
- Fine-grained authorization
- Protected key-encryption keys
- Version history
- Auditable access
- Replication and recovery
- Emergency credential revocation

Encryption at rest does not independently guarantee secure secret management. Access to encryption keys, application identities, and administrative interfaces must also be controlled.

### 4.4 Metadata and secret values

Secret metadata describes a credential without exposing its actual value.

Typical metadata includes:

| Field | Purpose |
|---|---|
| Secret name | Identifies the credential |
| Version number | Identifies a particular credential version |
| Provider reference | Identifies the external storage location |
| State | Describes lifecycle status |
| Created timestamp | Records creation time |
| Expiry timestamp | Defines validity limits |
| Owner | Identifies operational responsibility |
| Fingerprint | Supports change identification |

The PostgreSQL design stores provider references and metadata rather than plaintext credential values.

This separation reduces the risk of exposing credentials through ordinary database queries, backups, and reporting systems.

## 5. Access Control and Credential Permissions

### 5.1 Role-based access control

Role-Based Access Control assigns permissions through roles.

The implementations define four example identities:

| Role | Permitted operations |
|---|---|
| Application | Read authorized credentials |
| Security administrator | Read, create, rotate, revoke, inspect metadata |
| Rotation service | Read, create, and rotate |
| Auditor | Inspect metadata |

An auditor can examine lifecycle records without retrieving credential contents.

The Python `AccessPolicy`, JavaScript `AccessController`, C++ `AccessControl`, and Java `AccessPolicy` implement this separation.

### 5.2 Authentication versus authorization

Authentication establishes the identity of the requester.

Authorization determines whether that identity can perform a particular operation.

For example:

1. An application authenticates using its workload identity.
2. The secret manager identifies the application.
3. The access policy evaluates the requested secret and operation.
4. The provider permits or rejects the request.
5. The outcome is recorded in the audit system.

The educational implementations simulate identity-based authorization. They do not implement production identity federation, workload authentication, or network security.

### 5.3 Least privilege

Least privilege means granting only the permissions necessary for a specific operational responsibility.

An application that only retrieves a database password should not receive permission to create, rotate, or revoke that password.

Similarly, a monitoring service should generally receive metadata access rather than unrestricted credential access.

The access-control models demonstrate operation-specific permission checks.

## 6. Credential Lifecycle

A credential should have a defined lifecycle.

The implementations use four states:

| State | Meaning |
|---|---|
| `ACTIVE` | Current credential authorized for normal retrieval |
| `STAGED` | Replacement credential created but not activated |
| `RETIRED` | Previous credential retained temporarily for rollback |
| `REVOKED` | Credential permanently disabled in the lifecycle model |

### 6.1 Lifecycle transitions

The supported transitions are:

STAGED -> ACTIVE

STAGED -> REVOKED

ACTIVE -> RETIRED

ACTIVE -> REVOKED

RETIRED -> REVOKED

A revoked version cannot be restored through ordinary lifecycle operations.

A new credential must be created when a replacement is necessary.

The implementations prevent multiple active versions and multiple staged versions for the same secret.

The PostgreSQL implementation reinforces these conditions through partial unique indexes.

### 6.2 Credential creation

The creation workflow includes:

1. Validate the secret identifier.
2. Validate credential length.
3. Authenticate and authorize the requesting identity.
4. Generate or receive a credential securely.
5. Store the credential in the protected provider.
6. Create version metadata.
7. Record the operation.

The examples use cryptographically oriented random generators or standard-library secure random facilities for credential generation.

The in-memory implementations are educational simulations, not substitutes for encrypted persistent storage.

## 7. Secret Rotation

### 7.1 Purpose

Secret rotation replaces an existing credential with a new credential.

Rotation limits the period during which a potentially exposed credential remains valid.

It also supports scheduled credential renewal, personnel changes, incident response, and compliance requirements.

Rotation should be controlled rather than implemented as an uncontrolled password replacement.

### 7.2 Rotation workflow

The implementations follow this process:

1. Identify the active credential.
2. Generate a replacement credential.
3. Create a staged version.
4. Verify the replacement against the downstream service.
5. Activate the replacement.
6. Retain the old version temporarily.
7. Revoke the old version after the rollback period.
8. Record the completed operation.

State progression:

ACTIVE VERSION 1
       |
       v
CREATE VERSION 2
       |
       v
STAGED VERSION 2
       |
       v
DOWNSTREAM VERIFICATION
       |
       v
ACTIVATE VERSION 2
       |
       +---- VERSION 1 becomes RETIRED
       |
       v
ROLLBACK WINDOW
       |
       v
REVOKE VERSION 1

### 7.3 Why staging matters

Immediately replacing an active credential can cause service interruption if the replacement is invalid.

Staging separates credential creation from activation.

The replacement can be tested before production applications begin using it.

The JavaScript `RotationCoordinator`, Java `RotationService`, C++ `RotationCoordinator`, and Python `stage_rotation` and `activate_rotation` methods demonstrate this separation.

### 7.4 Downstream verification

A credential is not operationally valid merely because it was successfully generated.

The replacement must be tested against the actual resource that accepts it.

Examples include:

- Authenticating to a database.
- Calling an authenticated payment endpoint.
- Establishing an authenticated service connection.
- Verifying a certificate or signing-key integration.

The language implementations use verification callbacks or simulated checks.

A production implementation must perform real downstream verification using protected communication channels.

### 7.5 Rollback and revocation

The retired credential provides a temporary rollback option when the replacement causes operational problems.

Rollback must be controlled by policy.

Once the previous credential is revoked at the provider, the application must not assume it can restore that credential.

Revocation should include provider-side invalidation, not merely a local metadata update.

### 7.6 Failed rotation

A rotation may fail because of:

- Invalid replacement credentials
- Downstream authentication failures
- Provider connectivity problems
- Insufficient permissions
- Concurrent rotation requests
- Expired credentials
- Approval failures

A failed verification should not activate the replacement.

The existing active credential should remain usable until a controlled activation succeeds or another incident-response action is required.

The SQL implementation models explicit rotation states and records verification outcomes.

## 8. Credential Expiry and Rotation Policies

Credential expiry and rotation intervals are related but distinct.

**Expiry** defines when a credential is no longer valid.

**Rotation interval** defines when a credential should be replaced under an operational policy.

A credential may have a 90-day rotation interval and a provider-enforced expiry of 120 days.

The application should initiate rotation before the expiry deadline.

The Python implementation uses `datetime` and `timedelta`. JavaScript uses `Date`. C++ uses the standard time facilities. Java uses `Instant` and `ChronoUnit`.

The SQL implementation stores `rotation_interval_days` and `expires_at` independently.

An operational monitoring process should detect:

- Expired active credentials
- Credentials approaching expiry
- Credentials exceeding their rotation interval
- Secrets without active versions
- Incomplete rotation requests
- Failed downstream verification

## 9. Python Implementation

The Python file provides a class-oriented lifecycle simulation.

### Main components

| Component | Responsibility |
|---|---|
| `SecretState` | Defines lifecycle states |
| `SecretMetadata` | Stores non-sensitive version metadata |
| `SecretVersion` | Holds a version and its in-memory credential |
| `AccessPolicy` | Evaluates operation permissions |
| `InMemorySecretManager` | Controls storage and lifecycle |
| `SecretProvider` | Defines the provider contract |
| `AuditEvent` | Records operations without credential contents |
| `RotationCoordinator` concepts | Represent controlled rotation operations |

### Python-specific decisions

- Dataclasses provide structured metadata.
- Enums prevent arbitrary lifecycle-state strings.
- Dictionaries support direct secret lookup.
- Lists maintain version history.
- Sets represent permission collections.
- Exceptions distinguish access, state, and validation failures.
- `unittest` validates important security behavior.
- `secrets` generates unpredictable credentials.
- `hmac.compare_digest` provides constant-time comparison for equal-length fingerprints.

Expected validation includes successful retrieval, denied auditor access, duplicate creation rejection, invalid rotation rejection, and active-version revocation prevention.

Run the program using Python 3.10 or later.

## 10. JavaScript Implementation

The JavaScript file presents an asynchronous service-oriented model.

### Main components

| Component | Responsibility |
|---|---|
| `AccessController` | Evaluates permissions |
| `SecretProvider` | Defines asynchronous provider operations |
| `InMemorySecretProvider` | Maintains credential versions |
| `RotationCoordinator` | Coordinates staged rotation and verification |
| `ApplicationConfiguration` | Validates runtime configuration |

### JavaScript-specific decisions

- `Map` maintains secret collections.
- `Set` stores role permissions.
- Private class fields protect internal storage from ordinary external access.
- Promises support asynchronous provider operations.
- `async` and `await` express ordered rotation operations.
- `Object.freeze` protects returned metadata structures.
- Node.js `crypto` provides secure random generation and cryptographic fingerprints.
- `assert` validates behavior.

The JavaScript design treats the secret provider as an asynchronous boundary.

This is important because real secret-manager operations involve network requests, authentication, timeouts, retries, and service failures.

The implementation does not log credential contents.

Run using Node.js 20 or later.

## 11. C++17 Implementation

The C++ program models credential lifecycle management using domain-oriented classes.

### Main components

| Component | Responsibility |
|---|---|
| `SecretManager` | Controls credential lifecycle |
| `AccessControl` | Enforces role permissions |
| `SecretVersion` | Represents a credential version |
| `SecretMetadata` | Stores version information |
| `RotationCoordinator` | Performs controlled activation |
| `AuditEvent` | Records operational events |

### C++17-specific decisions

- `enum class` provides strongly typed states and actions.
- `struct` defines domain records.
- `map` provides indexed secret storage.
- `vector` maintains version history.
- `set` represents permission collections.
- `optional` models optional expiry timestamps.
- STL algorithms support state lookup and validation.
- Custom exceptions distinguish operational failures.
- `random_device` and a random engine generate demonstration credentials.

The implementation uses standard strings for simplicity. Standard C++ strings do not guarantee secure memory erasure.

The example overwrites the old string contents before clearing the value, but this is not a guarantee against compiler copies, allocator behavior, memory snapshots, or operating-system inspection.

Production implementations require carefully selected secure-memory handling and an external protected secret provider.

Compile with C++17.

## 12. Java 17 Implementation

The Java program models an enterprise credential-management service.

### Main components

| Component | Responsibility |
|---|---|
| `SecretProvider` | Defines provider operations |
| `EnterpriseSecretManager` | Manages versioned credentials |
| `AccessPolicy` | Evaluates role permissions |
| `SecretVersion` | Stores a credential version |
| `RotationService` | Coordinates rotation |
| `CredentialVerifier` | Defines downstream verification |
| `EnvironmentConfiguration` | Validates configuration |
| `AuditEvent` | Records management operations |

### Java-specific decisions

- Records provide immutable metadata structures.
- Interfaces separate provider contracts from implementation.
- Enums define permitted states and actions.
- Collections maintain versions and permissions.
- Streams perform metadata filtering and aggregation.
- Generics provide typed collections.
- Custom exceptions identify failure conditions.
- `ReentrantReadWriteLock` separates concurrent reads from exclusive modifications.
- `SecureRandom` generates credentials.
- `char[]` permits temporary credential buffers to be overwritten.

The read-write lock protects in-memory state during concurrent operations.

The implementation also clears temporary character arrays after use. Java does not guarantee that every internal copy of a credential is erased, so this technique reduces some exposure without providing complete memory protection.

The example uses Java 17 standard-library functionality and does not require third-party dependencies.

## 13. PostgreSQL Implementation

The SQL file implements relational management of secret metadata and operational workflows.

It deliberately does not store plaintext credentials.

### 13.1 Database entities

| Table | Responsibility |
|---|---|
| `principals` | Application, human, and service identities |
| `secret_providers` | External secret-provider inventory |
| `secrets` | Secret identifiers and provider references |
| `secret_versions` | Credential version lifecycle |
| `access_roles` | Defined security roles |
| `role_permissions` | Role-level permissions |
| `principal_roles` | Identity-to-role assignments |
| `secret_access_grants` | Secret-specific permissions |
| `rotation_requests` | Rotation workflow |
| `rotation_verifications` | Downstream verification records |
| `secret_audit_events` | Security and operational audit records |

### 13.2 Referential integrity

Primary keys identify records.

Foreign keys connect credentials to providers, owners, versions, requests, and principals.

Unique constraints prevent duplicate secret identifiers, duplicate version numbers, and duplicate provider references.

Check constraints validate allowed values and lifecycle metadata.

Partial unique indexes enforce at most one active version and at most one staged version for a secret.

These constraints provide database-level protection even when multiple application processes interact with the same data.

### 13.3 Lifecycle triggers

The `enforce_secret_version_transition` trigger validates state changes.

It prevents modification of revoked versions and rejects unsupported lifecycle transitions.

The `enforce_rotation_transition` trigger restricts rotation requests to permitted workflow states.

These mechanisms protect database consistency independently of application-level validation.

### 13.4 Access-control function

`has_secret_permission` evaluates whether an enabled principal has an unexpired grant for a particular secret and operation.

The function checks:

- Principal identity
- Secret identity
- Requested operation
- Grant status
- Grant expiry
- Principal status

The SQL function demonstrates permission evaluation. Production deployment must also enforce appropriate PostgreSQL roles, row-level security where suitable, and provider-side authorization.

### 13.5 Rotation procedure

`activate_secret_rotation` performs controlled activation.

It:

- Locks the rotation request.
- Checks the current workflow state.
- Requires independent approval.
- Verifies the new version is staged.
- Verifies the previous version is active.
- Retires the previous version.
- Activates the replacement.
- Marks the rotation request as activated.
- Records an audit event.

The procedure uses row-level locking to reduce concurrent activation conflicts.

### 13.6 Views and reporting

`secret_rotation_status` classifies credentials as current, expired, due for rotation, or not active.

`expiring_secrets` identifies active credentials approaching expiry.

Additional queries provide:

- Secret inventory
- Version history
- Permission evaluation
- Lifecycle aggregation
- Rotation request reporting
- Audit reporting
- Principal activity
- Failed verification identification
- Governance health assessment

### 13.7 Transaction boundaries

The script demonstrates transactions, savepoints, rollback, and stored procedures.

A significant architectural limitation is that a PostgreSQL transaction cannot automatically commit an operation performed by an independent external secret manager.

For example, activating a credential in a provider and updating a PostgreSQL record are separate operations.

Production systems should use an idempotent workflow with durable operation records, retry handling, and reconciliation.

## 14. Security Design Decisions

### 14.1 Never hardcode credentials

Credentials should not be embedded in:

- Source code
- Git repositories
- Container images
- Application configuration committed to version control
- Build logs
- Test reports
- Documentation
- Error messages

A leaked credential should be treated as compromised and replaced through a controlled incident-response process.

### 14.2 Avoid logging sensitive information

Audit events should record operational metadata, not secret values.

Useful audit fields include:

- Requesting identity
- Secret identifier
- Operation
- Version
- Timestamp
- Result
- Correlation identifier
- Source information

The implementations deliberately exclude credential contents from their audit records.

### 14.3 Protect development and production separately

Development, testing, staging, and production should use separate credentials and provider access policies.

A developer credential should not grant access to production resources.

The PostgreSQL `environment` field explicitly models this distinction.

### 14.4 Handle compromised credentials

An incident-response workflow should include:

1. Identify the affected secret.
2. Determine which applications and resources use it.
3. Restrict unauthorized access.
4. Generate replacement credentials.
5. Verify the replacements.
6. Update dependent applications.
7. Activate replacements.
8. Revoke compromised credentials.
9. Review audit events.
10. Investigate the original exposure.

Emergency revocation may require immediate invalidation rather than waiting for the normal rotation window.

### 14.5 Protect secret-manager access

A secret manager itself is a high-value security target.

Its protection should include authenticated workloads, least-privilege policies, administrator separation, network restrictions, encrypted communication, audit monitoring, and controlled recovery procedures.

## 15. Edge Cases and Failure Handling

| Scenario | Expected behavior |
|---|---|
| Missing environment variable | Reject configuration initialization |
| Empty credential | Reject credential creation |
| Invalid secret identifier | Reject the request |
| Duplicate secret creation | Reject duplicate creation |
| Unauthorized retrieval | Deny access and record the attempt |
| Missing secret | Return a controlled not-found failure |
| Expired active credential | Reject retrieval |
| Duplicate staged rotation | Reject concurrent staging |
| Identical replacement credential | Reject rotation |
| Failed downstream verification | Keep the previous credential active |
| Activation without staging | Reject activation |
| Revocation of active version | Reject revocation |
| Repeated revocation | Reject invalid state transition |
| Expired access grant | Deny access |
| Concurrent activation | Serialize or reject competing changes |
| Provider failure | Preserve a recoverable workflow state |

The in-memory examples do not implement distributed locking, durable recovery, network retries, or provider reconciliation. Those responsibilities belong to a production implementation.

## 16. Performance and Operational Considerations

### Secret lookup

The Python dictionary, JavaScript `Map`, and C++ `map` provide indexed secret lookup.

The Java implementation uses a hash-based collection.

These approaches avoid repeatedly scanning an entire inventory for a named secret.

### Version history

Version history is maintained separately from active credential retrieval.

Production systems should retain only the history required by operational, security, and regulatory policies.

### Audit volume

Secret access can generate substantial audit activity.

A production audit system should consider:

- Time-based partitioning
- Retention policies
- Indexed timestamps
- Aggregation
- Restricted audit access
- External archival
- Tamper detection

### Concurrent rotation

Two independent rotation processes must not activate competing versions simultaneously.

The implementations use local state protection, database constraints, or row-level locking to demonstrate concurrency control.

A distributed implementation also needs provider-side concurrency controls and idempotent requests.

### Availability

A secret manager outage can interrupt application startup or credential renewal.

Production applications should define appropriate caching, retry, timeout, and emergency-access policies.

Any cache must have a controlled lifetime and must not permit indefinitely using revoked or expired credentials.

## 17. Implementation Comparison

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Environment validation | Yes | Yes | Limited | Yes | Metadata model |
| Secret generation | Yes | Yes | Yes | Yes | External provider |
| Access control | Yes | Yes | Yes | Yes | Permission functions |
| Version management | Yes | Yes | Yes | Yes | Relational tables |
| Staged rotation | Yes | Yes | Yes | Yes | Yes |
| Activation | Yes | Yes | Yes | Yes | Stored procedure |
| Revocation | Yes | Yes | Yes | Yes | Lifecycle model |
| Expiry validation | Yes | Yes | Yes | Yes | Views |
| Audit records | Yes | Yes | Yes | Yes | Audit table |
| Automated validation | unittest | assert | Runtime checks | Runtime checks | Constraints and queries |
| Persistent credential storage | No | No | No | No | No plaintext storage |

## 18. Execution Requirements

| Deliverable | Requirement | Execution |
|---|---|---|
| Python | Python 3.10+ | `python secure_secrets.py` |
| JavaScript | Node.js 20+ | `node secure-secrets.js` |
| C++17 | C++17 compiler | `g++ -std=c++17 -Wall -Wextra -pedantic secure_secrets.cpp -o secure_secrets` |
| Java | Java 17 JDK | `javac SecureSecrets.java` followed by `java SecureSecrets` |
| PostgreSQL | PostgreSQL 15+ | Execute the SQL script using an authorized database connection |

All four application implementations use standard-library functionality.

The PostgreSQL script creates its own schema, domain types, tables, indexes, functions, procedures, triggers, sample records, and validation queries.

## 19. Production Limitations

These implementations demonstrate secret-management mechanisms and lifecycle behavior. They are not complete production secret-management platforms.

Important limitations include:

- In-memory implementations lose their state when the process terminates.
- Demonstration providers do not encrypt persistent credential storage.
- Authentication is simulated through predefined application identities.
- Production identity federation and workload authentication are not implemented.
- Real provider-side credential verification requires service integration.
- Network security and TLS configuration are outside the examples.
- Secure memory handling cannot be guaranteed by ordinary immutable strings.
- Audit storage requires additional tamper-resistant infrastructure.
- Distributed rotation requires idempotency and reconciliation.
- Provider-side revocation must be implemented independently of local state transitions.
- Database permissions and external provider policies must be configured separately.

The central architectural distinction is that an application should consume credentials through an authorized provider interface, while credential lifecycle, storage protection, access decisions, and audit responsibilities remain controlled by dedicated security components.
