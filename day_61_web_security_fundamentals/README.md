# Web Security Fundamentals

## Scope

This project models four connected security concerns in a web application:

1. The CIA triad establishes what must be protected.
2. Attack-surface analysis identifies exposed entry points, data stores, and trust boundaries.
3. Secure coding converts security requirements into validation, authentication, authorization, browser controls, and resource limits.
4. Threat modeling connects assets, threats, likelihood, impact, and mitigations.

The implementations deliberately use different engineering perspectives. Python provides a compact security simulation. JavaScript uses event-driven request and policy processing. C++17 implements a security governance and merge-eligibility engine. Java 17 models an enterprise security domain with explicit types and services. PostgreSQL provides persistent relational enforcement and reporting.

## Security Model

The central relationship is:

    Assets
       |
       v
    CIA requirements
       |
       v
    Attack surface
       |
       v
    Threats and abuse cases
       |
       v
    Security controls
       |
       v
    Validation and enforcement
       |
       v
    Security decision

The CIA triad is not a single control. It is a classification of security objectives.

| Property | Primary concern | Example web asset |
|---|---|---|
| Confidentiality | Prevent unauthorized disclosure | Customer records |
| Integrity | Prevent unauthorized modification | Account and transaction data |
| Availability | Keep authorized services usable | Public API |

An asset may require all three properties at different levels. A session token, for example, has especially high confidentiality and integrity requirements because disclosure or modification can enable account compromise.

## Attack Surface

An attack surface contains the places where an external or lower-trust component can interact with a system.

Typical components represented by the implementations include:

| Component | Security concern |
|---|---|
| Login endpoint | Credential attacks and authentication abuse |
| Profile endpoint | Authorization and input validation |
| Administrative endpoint | Privilege escalation |
| File or path input | Path traversal |
| Request body | Resource exhaustion |
| Session store | Session theft |
| Database | Injection and unauthorized data access |
| Audit log | Repudiation and forensic integrity |

The JavaScript implementation explicitly represents endpoints, data stores, and trust boundaries using `Map` and `Set` structures.

The important distinction is that an endpoint is an exposure point, while an asset is something valuable that requires protection. A threat connects the exposure to a possible adverse effect on an asset.

## Threat Modeling

The Python and C++ implementations use a lightweight STRIDE-oriented threat classification.

| Category | Security question |
|---|---|
| Spoofing | Can an attacker impersonate a user or service? |
| Tampering | Can data or requests be modified without authorization? |
| Repudiation | Can a security-relevant action lack reliable evidence? |
| Information Disclosure | Can protected information reach an unauthorized party? |
| Denial of Service | Can resources be exhausted or service availability degraded? |
| Elevation of Privilege | Can a lower-privileged actor obtain stronger permissions? |

Risk is represented as:

`risk score = likelihood × impact`

This is a prioritization mechanism rather than a complete quantitative risk model. A high score identifies threats that deserve stronger controls and deeper analysis.

The implementations explicitly model credential stuffing, session theft, SQL injection, cross-site scripting, API resource exhaustion, and broken access control.

## Secure Coding

Secure coding means enforcing security properties at the point where software handles untrusted input or performs security-sensitive operations.

### Input validation

The implementations validate:

- usernames
- request paths
- HTTP methods
- request body size
- branch names
- Pull Request state
- repository relationships
- security findings
- review states

Validation is performed before sensitive operations. Invalid input produces a controlled failure rather than being allowed to propagate into deeper application logic.

Validation is not treated as a replacement for output encoding, authorization, parameterized database access, or other controls.

### Path traversal

A path such as `/files/../secret` attempts to move outside an intended directory hierarchy.

The Python, JavaScript, and C++ implementations reject path traversal patterns before accepting a request.

The PostgreSQL model also constrains stored file paths associated with Pull Requests so invalid path representations are rejected at the database layer.

### Authentication

Authentication answers:

`Who is this user?`

The Python implementation uses salted PBKDF2-HMAC-SHA256 for password verification. The JavaScript implementation uses Node.js `crypto.pbkdf2`. Both use random salts and a deliberately high iteration count.

The implementations do not store plaintext passwords.

Session identifiers are generated from cryptographically secure random bytes. The application treats the session token as an opaque capability rather than embedding authorization information directly into a predictable identifier.

### Authorization

Authorization answers:

`Is this authenticated identity allowed to perform this operation?`

The Python application separates session authentication from administrator authorization.

The JavaScript service provides explicit role evaluation.

The Java implementation models roles as an enum and uses domain-level authorization checks.

The database model stores roles separately from users, allowing queries and constraints to distinguish identity from authorization.

A key security rule is that authorization must be evaluated server-side. Client-side controls can improve user experience but cannot enforce a security boundary.

## Browser Security Controls

The Python and JavaScript implementations generate security response headers.

| Header | Purpose |
|---|---|
| `Content-Security-Policy` | Restricts browser-executable content and reduces script injection exposure |
| `X-Content-Type-Options` | Prevents MIME-type sniffing |
| `X-Frame-Options` | Prevents framing by unauthorized pages |
| `Referrer-Policy` | Limits referrer information leakage |
| `Permissions-Policy` | Restricts browser capabilities |
| `Cache-Control: no-store` | Prevents inappropriate caching of sensitive responses |

The Content Security Policy uses a restrictive default policy and disables object embedding.

Security headers are defense-in-depth controls. They do not replace correct server-side validation or authorization.

## Rate Limiting and Availability

Availability is part of the CIA model.

The Python and JavaScript implementations use bounded request windows. Repeated requests from one client identity eventually produce a controlled rate-limit response.

Rate limiting helps with:

- credential stuffing
- repeated authentication failures
- request floods
- expensive endpoint abuse
- resource consumption

A production system normally needs distributed rate limiting when multiple application instances share traffic. An in-memory limiter is useful for a single-process model but does not provide global enforcement across a cluster.

Request body limits provide another availability control. A large body can consume memory, bandwidth, parsing time, or downstream resources even when the request is otherwise syntactically valid.

## Python Implementation

The Python file models the security domain using dataclasses, enums, exceptions, dictionaries, sets, and classes.

### Main components

`Asset` represents a protected resource and stores separate confidentiality, integrity, and availability requirements.

`Threat` stores a threat category, affected asset, likelihood, impact, and mitigation.

`ThreatModel` maintains the asset and threat relationships and calculates risk scores.

`PasswordHasher` implements salted PBKDF2 password hashing and constant-time digest comparison.

`SessionManager` creates opaque session tokens using secure random data.

`RateLimiter` maintains a bounded fixed-window request counter.

`InputValidator` centralizes username, email, and path validation.

`WebSecurityPolicy` produces browser-facing security headers.

`SecureWebApplication` combines authentication, authorization, rate limiting, request validation, audit logging, and controlled administrative behavior.

The `run_self_tests` function verifies password handling, authorization failure, successful administrative access, valid requests, path traversal rejection, request-size rejection, and incorrect-password rejection.

### Failure handling

Security-sensitive failures are represented by explicit exceptions:

- `InputValidationError`
- `AuthenticationError`
- `RateLimitExceeded`

The HTTP-style request handler converts these failures into bounded status results rather than exposing internal exceptions to callers.

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library functionality and an event-driven design.

### Domain structures

`Asset` and `Threat` represent the security model.

`AttackSurface` uses `Map` for endpoints and data stores and `Set` for trust boundaries.

`PasswordService` uses Node.js cryptographic primitives for PBKDF2.

`SessionStore` maintains opaque session identifiers.

`RateLimiter` manages request windows.

`InputPolicy` centralizes validation.

`SecurityHeaders` constructs response security headers.

`SecureWebService` extends `EventEmitter` so authentication and authorization failures can produce security events without coupling request processing to a specific logging implementation.

This event-driven separation is useful when security events must later feed audit logging, monitoring, alerting, or incident-response pipelines.

## C++17 Implementation

The C++17 program presents a repository-security governance case study.

The domain contains:

- security assets
- threats
- controls
- branch-protection policy
- Pull Requests
- reviews
- status checks
- security findings
- merge eligibility

This model connects web security to a realistic development-control workflow.

The `MergeEligibilityEngine` evaluates whether a Pull Request can be merged.

A Pull Request is blocked when:

- it is not open
- its source branch is behind
- a merge conflict exists
- an unresolved security finding exists
- a required status check fails
- required security approvals are missing
- an approval has become stale or has been dismissed

The C++ implementation uses STL containers such as `map`, `vector`, `set`, and `unordered_set`. It uses explicit enums for security levels, threat categories, and Pull Request states.

The design deliberately keeps policy evaluation separate from data representation. This makes the eligibility engine independently testable and allows repository policy to change without rewriting the Pull Request data structure.

## Java 17 Implementation

The Java implementation models an enterprise security governance service with explicit domain types.

Java records represent immutable security facts such as:

- assets
- threats
- reviews
- status checks
- security findings
- branch-protection policies

The `User` class represents identity and roles.

The `Repository` class owns repository security assets and branch policies.

The `PullRequest` class manages state and review-related evidence.

`MergeEligibilityService` evaluates repository policy against current Pull Request state.

`SessionService` provides opaque authentication sessions.

`LoginRateLimiter` represents authentication abuse controls.

The design separates:

`identity -> authentication -> authorization -> policy evaluation -> merge decision`

This separation prevents a successful login from being treated as automatic permission to perform every operation.

The model also treats stale approvals and dismissed approvals differently from active approvals. This matters because an approval may no longer represent the current state of the proposed changes.

## PostgreSQL Implementation

The PostgreSQL implementation provides persistent security state and database-level enforcement.

### Relational model

The principal relationship is:

    Repository
        |
        +-- Branch
        |     |
        |     +-- Branch Protection Policy
        |
        +-- Commit
        |
        +-- Pull Request
              |
              +-- Pull Request Commit
              +-- Pull Request File
              +-- Review
              |     |
              |     +-- Review Comment
              |
              +-- Status Check
              +-- Security Finding

Security analysis is represented separately:

    Repository
        |
        +-- Asset
              |
              +-- Threat

Users and roles are independent:

    User
      |
      +-- User Role

This prevents identity, repository state, review decisions, and security policy from being collapsed into one table.

### Constraints

The database enforces:

- unique repository names
- unique usernames and email addresses
- valid username patterns
- safe branch-name restrictions
- valid commit SHA formats
- source and target branch separation
- repository ownership of Pull Request branches
- non-negative file change counts
- valid review-comment sizes
- bounded approval requirements
- unique branch policies
- unique status-check names per Pull Request

Database constraints are important because application validation alone can be bypassed by another application, maintenance script, integration, or database client.

### Branch protection

`branch_protection_policy` stores repository-level enforcement rules.

It can require:

- status checks
- reviews
- a minimum number of approvals
- fresh approvals
- resolved review conversations
- an up-to-date source branch
- linear history

It can also prohibit:

- direct pushes
- force pushes
- branch deletion

The policy is attached to a branch rather than to an individual Pull Request. This reflects the distinction between proposed changes and repository governance.

### Merge eligibility

The `merge_eligibility` function evaluates the current state of a Pull Request against the target branch policy.

It checks:

1. Pull Request state
2. branch synchronization
3. merge conflicts
4. required status checks
5. unresolved security findings
6. unresolved review conversations
7. active security approvals

The function returns a boolean decision and a specific reason.

This allows reporting systems to distinguish a missing approval from a failed security check or unresolved finding.

### Trigger enforcement

The `prevent_protected_direct_merge` trigger applies database-level checks when a Pull Request changes to `MERGED`.

This prevents a client from simply changing the state column while bypassing the policy model.

The trigger checks branch freshness, conflicts, status checks, security findings, and active security approvals.

The audit trigger records Pull Request state transitions.

## Security Control Boundaries

Security mechanisms operate at different layers.

| Layer | Primary responsibility |
|---|---|
| Browser | Enforce browser-facing restrictions |
| HTTP service | Validate requests and enforce authentication |
| Application | Enforce authorization and business rules |
| Repository governance | Control how security-sensitive changes enter protected branches |
| Database | Enforce persistent integrity and workflow invariants |
| Audit system | Preserve evidence of security-relevant actions |

No single layer is sufficient.

For example, an application may reject unauthorized access, but a database constraint can still protect persistent relationships if another service attempts an invalid write.

## Pull Request and Security Workflow

A secure development workflow represented by the project is:

    Developer
       |
       v
    Feature Branch
       |
       v
    Pull Request
       |
       +----> Automated Status Checks
       |
       +----> Code Review
       |          |
       |          +----> Security Review
       |
       +----> Security Findings
       |
       v
    Branch Protection
       |
       v
    Merge Eligibility
       |
       v
    Merge

A Pull Request is the change-proposal mechanism.

Code review evaluates the proposed implementation.

Approvals record reviewer decisions.

Branch protection enforces repository-level requirements before merging.

These concepts interact, but they are not interchangeable.

## Review and Approval Semantics

A review is an evaluation of a change.

An approval is a particular review decision indicating that the reviewer accepts the current reviewed state.

A stale approval should not automatically remain valid after substantial changes because the reviewer may have approved an earlier version.

A dismissed approval is also excluded from the active approval count.

The implementations therefore evaluate approval state using several conditions rather than counting every historical `APPROVED` record.

The database records review history instead of overwriting previous decisions. This preserves auditability and allows the current effective decision to be computed from stored state.

## Failure Modes

Important failure conditions represented by the implementations include:

| Failure | Security effect | Control |
|---|---|---|
| Invalid credentials | Authentication abuse | Password hashing and rate limiting |
| Invalid session | Unauthorized access | Session validation |
| Missing role | Privilege escalation | Server-side authorization |
| Path traversal | File disclosure | Path validation |
| Oversized body | Resource exhaustion | Request-size limit |
| Failed status check | Unsafe change | Protected merge policy |
| Stale approval | Incorrect review assumption | Fresh approval requirement |
| Unresolved finding | Known vulnerability can enter protected branch | Merge blocker |
| Merge conflict | Unreviewed combined state | Branch synchronization |
| Unresolved conversation | Security concern remains open | Conversation requirement |

## Performance Considerations

The Python and JavaScript security simulations use in-memory maps for fast lookup. Their state is process-local and therefore unsuitable as the sole security store for horizontally scaled deployments.

The PostgreSQL model uses indexes where queries repeatedly filter on:

- Pull Request repository and state
- Pull Request target branch
- current review decisions
- unresolved comments
- open security findings
- audit events by repository and time

The database view aggregates Pull Request security information for reporting. Large installations would need careful query planning and possibly precomputed reporting structures.

Rate limiting becomes more complex in distributed environments because multiple application instances must share counters or use a consistent gateway-level policy.

## Security Considerations

The implementations intentionally demonstrate several defensive principles:

- never store plaintext passwords
- use cryptographically secure random session identifiers
- use constant-time comparison for password-derived values
- validate untrusted input
- enforce authorization on the server
- restrict request sizes
- apply rate limits
- use restrictive browser security headers
- separate security findings from review comments
- reject stale or dismissed approvals
- enforce branch policies at the persistence layer
- record security-relevant state transitions
- use least-privilege database access in the threat model

The examples are security models rather than complete production web frameworks. A deployed service would also require TLS configuration, secret management, centralized identity controls, secure cookie handling, CSRF protection where applicable, output encoding, parameterized database access, dependency management, logging protection, monitoring, incident response, and operational controls.

## Practical Distinctions

The four major concepts in the project can be kept distinct:

| Concept | Primary question |
|---|---|
| Attack surface | Where can interaction occur? |
| Secure coding | How should software safely process that interaction? |
| Threat modeling | What can go wrong, and what should mitigate it? |
| CIA triad | What security properties must be preserved? |

A secure design connects them rather than substituting one for another.

For example, a customer database may have high confidentiality and integrity requirements. Its attack surface includes authenticated API endpoints and database connections. Threat modeling identifies SQL injection and broken authorization. Secure coding applies parameterized queries and server-side authorization. Repository governance then helps ensure those controls are reviewed and verified before security-sensitive changes reach a protected branch.

## Implementation Comparison

| Implementation | Primary perspective | Key mechanisms |
|---|---|---|
| Python | Security simulation | Dataclasses, validation, hashing, sessions, threat model |
| JavaScript | Event-driven web service | Maps, Sets, Promises, crypto APIs, security events |
| C++17 | Governance engine | STL, policy evaluation, explicit state, merge eligibility |
| Java 17 | Enterprise domain model | Records, enums, services, immutable collections, policies |
| PostgreSQL | Persistent enforcement | Constraints, triggers, views, functions, indexes, transactions |

Each implementation models the same security principles at a different architectural boundary rather than mechanically reproducing the same program.

## Limitations

The in-memory authentication and rate-limiting implementations do not provide shared state across multiple processes.

The threat scores are prioritization values, not statistical probabilities.

The security headers demonstrate defensive browser policy but do not implement every browser security feature.

The database model demonstrates enforcement and reporting but does not replace application-level authorization.

The repository governance model represents security-oriented merge controls. It does not claim to implement every feature of a specific source-control platform.

The examples intentionally keep dependencies minimal so that the security mechanisms remain visible and testable.
