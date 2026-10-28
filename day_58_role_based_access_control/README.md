# Role-Based Access Control

## Purpose

This project implements Role-Based Access Control (RBAC) as a concrete authorization domain.

The five source files model the same core security concepts from different engineering perspectives:

| File | Primary perspective | Main implementation |
|---|---|---|
| Python | Workflow simulation | In-memory RBAC authorization engine |
| JavaScript | Event-driven policy evaluation | Node.js RBAC engine with audit events |
| C++17 | Governance engine | Explicit role, permission, resource, and decision structures |
| Java 17 | Enterprise domain model | Records, services, policies, state, and validation |
| PostgreSQL | Relational security model | Users, roles, permissions, resources, decisions, functions, triggers, and reporting |

The implementations distinguish authentication from authorization. Authentication establishes which account is operating. RBAC authorization determines whether that account may perform a particular action on a particular resource.

## RBAC Model

The central relationship is:

`User → Role → Permission → Resource Action → Authorization Decision`

A user receives one or more roles. A role receives permissions. A permission describes an allowed action on a resource type.

For example:

`alice → user → profile:update → alice-profile → ALLOW`

A different request can produce:

`alice → user → ticket:update → bob-ticket → DENY`

The difference comes from the permission assigned to the role rather than from the identity of the resource alone.

## Roles

The implementations use four operational roles:

| Role | Purpose |
|---|---|
| `user` | Basic profile access |
| `support` | Ticket reading and updating |
| `manager` | Ticket approval and reporting |
| `admin` | Administrative system operations |

Roles are collections of permissions rather than direct collections of users.

This separation allows permissions to be changed at the role level without rewriting authorization logic for every individual user.

## Permissions

A permission is represented as a pair:

`resource_type + action`

The implemented actions are:

| Action | Meaning |
|---|---|
| `read` | Retrieve information |
| `create` | Create a resource |
| `update` | Modify an existing resource |
| `delete` | Remove a resource |
| `approve` | Authorize an operational decision |
| `admin` | Perform a privileged administrative operation |

The examples primarily exercise `read`, `update`, `approve`, and `admin`.

The distinction between a permission and a resource instance is important. `ticket:update` describes a capability. It does not by itself identify which ticket may be modified.

## Resource Authorization

A resource contains an identifier, resource type, owner, and sensitivity classification.

For example:

`bob-ticket → ticket → owner bob → normal`

An authorization request combines:

`user + action + resource`

The authorization engine then evaluates the request against the user's effective permissions.

A matching role permission produces an allow decision. If no permission matches, a separate ownership policy may apply for narrowly defined resource types.

## Ownership Policy

Ownership is intentionally modeled separately from RBAC.

A user may read or update their own `profile` or `document` even when the corresponding instance-specific decision cannot be represented by a simple role permission.

This distinction prevents the role model from becoming a mixture of two different authorization mechanisms:

- RBAC answers which capabilities a role provides.
- Ownership policy answers whether the requesting principal owns the particular resource.

The implementations restrict the ownership rule to `read` and `update` on `profile` and `document` resources.

Administrative actions never become available through ownership.

## Administrative Access

Administrative authorization is treated as a privileged operation.

The `admin` action requires membership in the `admin` role before ordinary permission matching can grant access.

This creates an explicit privilege boundary:

`ordinary role → ordinary resource operations`

`admin role → administrative system operations`

A support or manager account cannot obtain administrative access simply because it can modify operational resources.

## Python Implementation

The Python file uses dataclasses, enumerations, sets, dictionaries, exceptions, password hashing, validation, and assertions.

The `Permission` dataclass provides an immutable description of a resource-action pair. `Role` stores a set of permissions, while `User` stores role membership and account state.

`RBACSystem` manages:

- role registration
- user registration
- role assignment
- role revocation
- authentication
- authorization
- effective permission calculation
- audit events

The authorization method checks account state, administrative restrictions, role permissions, and the separate ownership policy.

Password handling uses PBKDF2-HMAC-SHA256 with a random salt and constant-time comparison. The source intentionally avoids storing plaintext passwords.

The executable test section verifies:

- successful ownership authorization
- rejection of unauthorized ticket modification
- support permissions
- rejection of unauthorized administration
- successful administrator access
- rejection of inactive users

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library functionality.

`Map` stores users and roles efficiently by identifier. `Set` represents role membership and permission collections without duplicate entries.

The engine extends `EventEmitter`. Authorization and role-management operations generate audit events that consumers can observe.

This makes the implementation suitable for event-driven application architectures where authorization decisions may need to feed logging, monitoring, or security-event pipelines.

Password processing uses Node.js `crypto.pbkdf2Sync` with random salts and a constant-time comparison.

The JavaScript implementation also freezes authorization results and audit records before exposing them to callers. This reduces accidental mutation of security-relevant decision data.

## C++17 Implementation

The C++ program treats RBAC as a repository-style governance engine.

Strongly typed enumerations represent:

- roles
- actions
- decisions
- resource sensitivity

STL maps and sets provide deterministic collections for roles, permissions, users, and effective privileges.

The `RBACEngine` evaluates authorization requests and records audit events. Permission matching is performed through ordered role and permission collections.

The implementation explicitly handles:

- unknown users
- incomplete resources
- inactive accounts
- administrative escalation
- explicit permission matches
- ownership rules
- role assignment
- role revocation

The use of `std::set` provides duplicate prevention and predictable permission aggregation. Permission lookup within a role has logarithmic complexity.

## Java 17 Implementation

The Java implementation uses an enterprise-oriented domain structure.

Records model immutable value objects:

- `Permission`
- `Resource`
- `AuthorizationRequest`
- `AuthorizationResult`
- `AuditEvent`

`UserAccount` represents mutable account state and role membership.

`AuthorizationPolicy` is an explicit policy interface. `OwnershipPolicy` implements the instance-level ownership rule without embedding that logic into the RBAC permission table.

`AuthorizationService` owns the authorization workflow and provides:

- role permission registration
- user registration
- role assignment
- role revocation
- authentication
- authorization
- effective permission calculation
- audit event generation

This design separates domain objects from the service that evaluates policies.

## PostgreSQL Model

The PostgreSQL implementation represents RBAC relationally.

The principal tables are:

| Table | Responsibility |
|---|---|
| `app_users` | User identities and account state |
| `roles` | Role definitions |
| `permissions` | Resource-action capabilities |
| `user_roles` | User-to-role assignments |
| `role_permissions` | Role-to-permission assignments |
| `resources` | Protected resource instances |
| `authorization_requests` | Requested authorization operations |
| `authorization_decisions` | Persisted evaluation results |
| `audit_events` | Security-relevant events |

The relationship is:

`app_users → user_roles → roles → role_permissions → permissions`

Resources are linked separately through ownership.

## Database Constraints

The database enforces important invariants using relational constraints.

Primary keys identify each domain entity.

Foreign keys prevent orphaned relationships.

Unique constraints prevent duplicate:

- usernames
- role names
- resource-action permissions
- user-role assignments
- role-permission assignments
- resource keys

Check constraints restrict valid actions, resource names, sensitivities, and authorization outcomes.

This prevents invalid security state from being represented only by application-level validation.

## Authorization Function

The PostgreSQL function `evaluate_authorization` performs the authorization workflow inside the database.

Its evaluation order is:

1. Validate that the user and resource exist.
2. Reject inactive accounts.
3. Apply the administrative-role requirement.
4. Search effective role permissions.
5. Apply the narrow ownership policy.
6. Deny the request when no applicable rule exists.

The function returns:

- decision
- reason
- matched role

Keeping the evaluation operation in PostgreSQL makes the authorization logic directly queryable for reporting and transactional workflows.

## Audit and Transactions

Authorization requests are persisted separately from their resulting decisions.

The authorization request trigger writes a security audit event whenever a decision is recorded.

The transactional example evaluates an operation and records both the request and decision within a single transaction.

This prevents the database from retaining an authorization request without its corresponding decision when the operation is performed through the supplied workflow.

## Effective Permissions

Effective permissions are the union of permissions supplied by all roles assigned to a user.

For example:

`manager = profile:read + ticket:read + ticket:update + ticket:approve + report:read`

If a user has multiple roles, the resulting permission set combines their permissions.

The source implementations use sets or equivalent structures so duplicate permissions do not create duplicate authorization capabilities.

## Failure Conditions

The implementations explicitly handle common failure conditions.

| Failure | Expected result |
|---|---|
| Unknown user | Validation failure or denial |
| Unknown role | Validation failure |
| Duplicate user | Validation failure |
| Duplicate role | Validation failure |
| Inactive account | Denial |
| Unauthorized resource action | Denial |
| Unauthorized administrative action | Denial |
| Missing resource identity | Validation failure |
| Invalid authentication | Authentication failure |
| Missing authorization reason in PostgreSQL | Database exception |

Security-sensitive failures are not converted into successful access decisions.

## Security Considerations

RBAC is an authorization model, not a complete security architecture.

The examples therefore keep several concerns separate.

### Authentication

Authentication establishes account identity. The Python and JavaScript examples demonstrate password verification mechanisms, while the Java enterprise example keeps credential handling separate from its authorization domain.

Production systems should use a dedicated identity and credential-management component rather than embedding real credentials in application source code.

### Least Privilege

Permissions should be assigned to roles according to the minimum capabilities required by that role.

A support role does not receive administrative permissions merely because it needs ticket modification.

### Privilege Separation

Administrative permissions are explicitly restricted to the `admin` role.

This prevents ordinary resource permissions from implicitly becoming system administration privileges.

### Account State

An inactive account is denied before normal permission evaluation.

This is important because removing access by deactivating an account should take effect regardless of how many roles remain associated with the account.

### Auditability

Authorization decisions and role changes are recorded in audit structures.

Useful audit information includes:

- requesting user
- operation
- resource type
- decision
- decision reason
- timestamp

Audit records should be protected from unauthorized modification in production systems.

### Password Protection

The Python and JavaScript examples demonstrate salted PBKDF2 password derivation rather than plaintext password storage.

Password verification uses constant-time comparison where applicable.

The PostgreSQL sample uses clearly artificial demonstration hashes rather than real credentials.

## Performance Considerations

The primary RBAC lookup path is:

`user → roles → permissions → requested resource/action`

In the in-memory implementations, hash-based collections provide approximately constant-time average membership checks.

The C++ implementation uses ordered sets, producing logarithmic membership operations while providing deterministic ordering.

The PostgreSQL implementation indexes the principal relationship tables used by permission evaluation.

The database indexes target:

- role lookup
- permission lookup
- resource ownership and type
- authorization requests by user and time
- audit events by user and event type

Indexes should remain tied to actual query patterns. Excessive indexing increases write cost and storage requirements.

## Role and Permission Distinction

A role is a named collection of capabilities.

A permission is an individual capability.

A user receives roles.

A role receives permissions.

Therefore:

`User → Role → Permission`

is different from:

`User → Permission`

The first structure provides centralized administration of capability groups and is the core reason RBAC scales better than manually assigning every permission to every user.

## Authorization Decision Flow

The implemented workflow can be represented as:

`Request`
`  ↓`
`Validate user and resource`
`  ↓`
`Check account state`
`  ↓`
`Check privileged-action requirement`
`  ↓`
`Evaluate role permissions`
`  ↓`
`Evaluate applicable ownership policy`
`  ↓`
`ALLOW or DENY`
`  ↓`
`Record audit information`

Each stage has a distinct purpose. A later policy does not silently replace an earlier security boundary.

## Practical Scenario

Consider four users:

| User | Role | Primary capability |
|---|---|---|
| Alice | User | Own profile access |
| Bob | Support | Ticket operations |
| Carol | Manager | Ticket approval and reports |
| David | Admin | System administration |

Alice can update her own profile but cannot update Bob's ticket.

Bob can update tickets but cannot perform system administration.

Carol can approve tickets and read reports but is not automatically an administrator.

David can perform system administration because the `admin` role contains the `system:admin` permission.

This illustrates the separation between ordinary application privileges and administrative privileges.

## Important Limitations

The implementations are educational domain models rather than complete identity-management platforms.

They do not implement:

- multi-factor authentication
- session management
- token rotation
- distributed policy synchronization
- hierarchical roles
- attribute-based access control
- time-based access policies
- network-level policy enforcement
- production secret management
- external identity providers

These omissions keep the central RBAC mechanisms explicit and testable.

The ownership policy is intentionally narrow. A production authorization model may require additional resource-specific policies, but such policies should be introduced explicitly rather than hidden inside generic role permissions.

## Conceptual Boundary

The project maintains a strict distinction between four related security concepts:

`Authentication`
`    ↓`
`Who is the principal?`

`Role Assignment`
`    ↓`
`Which role memberships does the principal have?`

`Permission Evaluation`
`    ↓`
`Which capabilities do those roles provide?`

`Resource Authorization`
`    ↓`
`Does this particular request satisfy the applicable rules?`

The final result is an authorization decision, not merely a statement that a user belongs to a role.

## Executable Scope

The Python script runs using the Python standard library.

The JavaScript file runs using Node.js standard-library modules.

The C++ program requires C++17 or later.

The Java program requires Java 17 or later.

The PostgreSQL script requires PostgreSQL features including PL/pgSQL, JSONB, identity columns, triggers, views, functions, CTEs, and transactional statements.
