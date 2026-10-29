# Attribute-Based Access Control: Policies, Attributes, and Contextual Authorization

## Scope

This project models Attribute-Based Access Control (ABAC) as a policy-driven authorization system. Authorization decisions are derived from attributes of the subject, resource, requested action, and request context rather than from a single role lookup.

The implementation treats four authorization dimensions separately:

| Dimension | Meaning |
|---|---|
| Subject attributes | Identity, department, roles, clearance, and account state |
| Resource attributes | Resource type, owner department, and classification |
| Action attributes | Requested operation such as `read`, `write`, or `delete` |
| Contextual attributes | Device trust, MFA status, IP address, country, environment, and emergency ticket |

The central model is:

`Subject + Resource + Action + Context + Policy Set -> Authorization Decision`

The default security posture is deny. An access request must satisfy an applicable allow policy and must not be blocked by a higher-priority or explicit deny condition.

## ABAC Domain Model

The repository implementations use a common conceptual model while emphasizing different engineering concerns.

```text
User
  |
  +-- identity attributes
  +-- department
  +-- roles
  +-- clearance
  +-- account status
          |
          v
Access Request
  |
  +-- Action
  +-- Resource
  +-- Request Context
          |
          +-- IP address
          +-- trusted device
          +-- MFA
          +-- country
          +-- environment
          +-- emergency ticket
          |
          v
Policy Evaluation
  |
  +-- attribute conditions
  +-- policy effect
  +-- priority
  +-- enabled state
          |
          v
Authorization Decision
  |
  +-- allow
  +-- deny
  +-- audit event
```

A role is only one attribute. ABAC does not require every decision to be role-based. A policy can combine a role with classification, device state, MFA, network location, or another contextual attribute.

## Policy Semantics

Each policy contains:

| Element | Purpose |
|---|---|
| Policy identifier | Stable reference for audit and administration |
| Effect | `allow` or `deny` |
| Priority | Determines precedence among applicable policies |
| Actions | Operations covered by the policy |
| Resource types | Resource categories covered by the policy |
| Conditions | Attribute predicates that must all evaluate successfully |
| Enabled state | Allows policy activation without deleting its definition |

The examples use a deny-by-default model.

A simplified evaluation sequence is:

```text
Validate request
      |
      v
Is subject active?
      |
      v
Evaluate applicable policies
      |
      +---- explicit deny ----> DENY
      |
      +---- no allow ----------> DENY
      |
      +---- allow -------------> ALLOW
```

The Python, JavaScript, and Java implementations explicitly record the matched policies and decision reason. This makes authorization behavior inspectable instead of reducing the result to an unexplained Boolean value.

## Subject Attributes

The sample subjects include:

- `analyst`
- `manager`
- `administrator`
- `incident_responder`
- department membership
- clearance level
- active or inactive account state

Clearance is modeled independently from role membership. A manager can possess the required role but still fail an authorization request if the requested resource is classified above the user's clearance.

The distinction is important because authentication identifies a subject while authorization evaluates whether that subject is permitted to perform a particular operation against a particular resource under current conditions.

## Resource Attributes

Resources contain:

- identifier
- resource type
- owner department
- classification level
- active state in the database model

The examples include ordinary reports, confidential reports, and production databases.

Classification is deliberately treated as a resource attribute rather than a property of a role. This allows the same user to receive different decisions for different resources.

For example:

```text
User clearance = 4

Report classification = 2
Result = potentially allowed

Report classification = 4
Result = potentially allowed when policy conditions pass

Database classification = 5
Result = denied when clearance is insufficient
```

## Contextual Authorization

Context changes the decision without changing the identity or resource.

The examples use:

- trusted device status
- MFA verification
- source IP address
- country
- environment
- emergency ticket

A manager reading a confidential report must satisfy both device-trust and MFA conditions. An incident responder can use an emergency policy only when an emergency ticket follows the expected `INC-######` format.

This illustrates a key ABAC property: authorization can depend on runtime circumstances.

## Python Implementation

The Python implementation is a complete in-memory policy engine.

### Domain classes

The implementation uses dataclasses for:

- `User`
- `Resource`
- `RequestContext`
- `Condition`
- `Policy`
- `AuditEvent`

Enums represent policy effects and authorization decisions.

The immutable `User`, `Resource`, `RequestContext`, `Condition`, and `Policy` records make policy evaluation predictable. Mutable audit state is maintained separately by `AuthorizationEngine`.

### Attribute resolution

Attributes are addressed through paths such as:

- `user.roles`
- `user.department`
- `resource.classification`
- `request.device_trusted`
- `request.mfa_verified`

The resolver separates the policy representation from the Python object layout and rejects missing attributes instead of silently treating them as authorized.

### Operators

The Python condition evaluator implements:

- equality
- inequality
- membership
- containment
- greater-than-or-equal
- less-than-or-equal
- regular-expression matching
- CIDR membership

CIDR evaluation uses the standard library `ipaddress` module. This avoids external networking dependencies.

### Validation

The engine validates:

- IP address syntax
- action presence
- user identifier
- resource identifier
- hour range
- active account state

Invalid requests raise explicit exceptions rather than becoming authorization successes.

### Audit trail

Every authorization result is converted into an `AuditEvent`.

An event records:

- timestamp
- user
- resource
- action
- decision
- matched policies
- decision reason

This separates authorization from auditing while allowing the same service to produce both results.

### Edge cases

The Python examples include:

- inactive users
- invalid IP addresses
- insufficient policy matches
- malformed emergency tickets
- restricted resources
- untrusted devices
- MFA requirements
- explicit deny policies

The default-deny behavior prevents an absent policy from becoming accidental access.

## JavaScript Implementation

The JavaScript implementation emphasizes an event-driven authorization service.

### Policy representation

`Policy` objects contain:

- effect
- priority
- action set
- resource-type set
- condition functions

JavaScript `Set` objects provide efficient membership checks for roles, actions, and resource types.

### Functional conditions

Conditions are represented as functions. The implementation includes reusable predicates for:

- equality
- collection membership
- numeric comparison
- regular expressions
- CIDR checks

This allows policy composition without introducing a dependency-heavy rule engine.

### Event-driven auditing

`AuthorizationEngine` extends Node.js `EventEmitter`.

After every decision, the service emits `authorizationDecision`. The audit subscriber receives the structured decision record without coupling the authorization algorithm directly to a particular logging destination.

This design can be extended to a file logger, centralized event stream, metrics collector, or security monitoring service without changing policy evaluation.

### Asynchronous service boundary

`authorize()` is asynchronous even though the sample policies are in memory. This represents a useful service boundary for production systems where policy evaluation may require asynchronous reads from a policy store, identity provider, cache, or external authorization service.

### Security handling

The implementation validates IPv4 input before CIDR evaluation and rejects malformed requests. It does not infer authorization from unvalidated user-controlled strings.

The emergency ticket condition uses an anchored regular expression:

`^INC-[0-9]{6}$`

This prevents a partial match from satisfying the emergency-access condition.

## C++17 Governance Engine

The C++17 implementation takes a different perspective. It models a repository governance and merge-eligibility engine rather than implementing a direct policy interpreter.

The domain includes:

- users
- Pull Requests
- branches
- branch protection
- reviews
- review states
- status checks
- merge eligibility

This makes repository governance a concrete policy-evaluation scenario.

### Merge eligibility

The engine evaluates:

1. Pull Request state
2. draft status
3. merge-conflict state
4. target-branch protection
5. unresolved conversations
6. required status checks
7. current approvals
8. reviewer eligibility
9. stale approvals

A protected branch requires all configured conditions to pass.

```text
Pull Request
      |
      +-- open?
      |
      +-- not draft?
      |
      +-- mergeable?
      |
      v
Protected target?
      |
      +-- no --> eligible
      |
      +-- yes
           |
           +-- conversations resolved?
           +-- required checks passing?
           +-- required approvals?
                    |
                    v
                eligible
```

### Reviewer eligibility

The engine rejects:

- inactive reviewers
- unknown reviewers
- Pull Request authors attempting to count as independent approvers

Approvals are counted uniquely by reviewer identity. Repeated approvals from the same reviewer cannot artificially increase the approval count.

### Stale approvals

A stale approval does not count toward the required approval total. This represents a common governance requirement where changes after a review can invalidate the assumptions behind a previous approval.

### Branch protection

The `BranchProtection` structure contains:

- target branch
- required approval count
- required status checks
- direct-push restriction
- force-push restriction
- conversation-resolution requirement
- linear-history requirement

The example focuses on merge eligibility rather than implementing a Git transport protocol. This keeps repository policy enforcement distinct from source-control mechanics.

## Java 17 Enterprise Model

The Java implementation models ABAC as an enterprise service layer.

### Domain types

Java records provide immutable domain representations for:

- `User`
- `Resource`
- `AccessContext`
- `Policy`
- `AuthorizationDecision`

The records validate their own fundamental invariants.

### Policy repository

`PolicyRepository` is an interface separating policy storage from authorization logic.

`InMemoryPolicyRepository` provides the executable sample implementation.

A production implementation could replace this repository with a database-backed or configuration-backed implementation without changing the authorization service contract.

### Predicate-based policies

Java's `Predicate<AccessContext>` represents policy conditions.

The implementation provides reusable predicates for:

- role membership
- department
- resource classification
- trusted devices
- MFA
- environment
- emergency tickets

A policy is therefore a collection of typed predicates combined through `allMatch`.

### Explicit failure types

`AuthorizationException` represents authorization and validation failures.

`PolicyConflictException` represents a policy-definition conflict where multiple highest-priority allow policies exist at the same priority in the sample engine.

Separating these failure types helps distinguish invalid authorization state from an ordinary deny result.

### Audit model

`AuthorizationDecision` records:

- decision timestamp
- subject
- resource
- action
- decision
- matched policy identifiers
- reason

The service exposes an immutable copy of its audit trail, preventing callers from mutating internal decision history.

## PostgreSQL Relational Model

The PostgreSQL implementation represents ABAC and repository governance as relational data.

### Core authorization tables

| Table | Responsibility |
|---|---|
| `users` | Subject identity and clearance |
| `roles` | Role definitions |
| `user_roles` | Subject-to-role relationships |
| `resources` | Protected objects and classifications |
| `actions` | Authorized operations |
| `policies` | Policy effects and priorities |
| `policy_actions` | Operations covered by policies |
| `policy_conditions` | Attribute predicates |
| `authorization_requests` | Incoming authorization requests |
| `authorization_decisions` | Decision and reason |
| `policy_decision_matches` | Policies associated with decisions |

This structure separates policy definitions from requests and decisions.

### Repository governance tables

The same database also models:

- repositories
- branches
- branch protection policies
- commits
- Pull Requests
- Pull Request commits
- reviewers
- reviews
- review comments
- status checks
- required status checks

This allows merge eligibility to be evaluated from persistent repository state.

### Database constraints

The schema uses:

- primary keys
- foreign keys
- unique constraints
- enum types
- check constraints
- cascading deletes
- indexes

Important rules are enforced at the database layer instead of relying exclusively on application code.

For example, an approval from the Pull Request author is rejected by `prevent_invalid_review()`.

### Indexing

Indexes target common lookup paths:

- user-role relationships
- resource type and classification
- enabled policies ordered by priority
- Pull Request review state
- status-check state
- authorization requests by user and time

The schema avoids indiscriminately indexing every column because indexes impose storage and write-maintenance costs.

## Transactional Authorization Recording

The SQL script demonstrates an atomic authorization audit transaction.

The transaction inserts an authorization request and its corresponding decision as one unit.

```text
BEGIN
  |
  +-- insert authorization request
  |
  +-- insert authorization decision
  |
COMMIT
```

If either operation fails, the transaction can be rolled back so that the audit trail does not contain an incomplete request or decision.

## Policy Evaluation in PostgreSQL

`evaluate_authorization()` demonstrates database-side authorization evaluation.

The function:

1. validates the user
2. validates the resource
3. validates the requested action
4. rejects inactive users
5. checks clearance
6. finds enabled policies
7. evaluates policy conditions
8. returns a decision
9. returns matched policy identifiers

The database therefore contains both policy data and executable decision logic.

For larger systems, application-side policy evaluation and database-side enforcement can be combined. Database constraints should remain responsible for invariants that must hold regardless of which application accesses the database.

## Security Model

The implementations use several security principles.

### Default deny

No matching allow policy results in denial.

This avoids treating missing policy configuration as permission.

### Explicit deny

A deny policy can override otherwise applicable access.

This is useful for conditions such as:

- restricted resources
- untrusted devices
- emergency situations that require stronger controls
- temporary security restrictions

### Least privilege

Policies grant specific operations against specific resource types under explicit conditions.

A user does not automatically receive every operation merely because a role is present.

### Context validation

Contextual attributes are validated before use.

Examples include:

- IP address syntax
- MFA state
- device trust
- environment
- emergency ticket format

### Auditability

Decisions include the reason and applicable policy identifiers. This supports investigation and policy debugging.

## Policy Conflict Handling

Policy conflicts require deterministic semantics.

The sample implementations use:

- explicit deny handling
- policy priority
- default deny
- conflict detection in selected cases

A production policy engine should document precedence rules before policies are deployed.

Potential precedence models include:

```text
Explicit deny
    >
Higher priority
    >
Specific policy
    >
General policy
    >
Default deny
```

The exact ordering is a governance decision and must remain consistent across services.

## Failure Modes

Important failure conditions represented in the implementations include:

| Failure | Result |
|---|---|
| Unknown user | Deny or validation failure |
| Inactive user | Deny |
| Unknown resource | Deny |
| Invalid action | Validation failure |
| Insufficient clearance | Deny |
| Missing MFA | No matching privileged policy |
| Untrusted device | Potential explicit deny |
| Invalid emergency ticket | No emergency authorization |
| Missing status check | Merge ineligible |
| Failed status check | Merge ineligible |
| Stale approval | Approval does not count |
| Inactive reviewer | Approval does not count |
| Self-approval | Rejected |
| Merge conflict | Merge ineligible |
| Draft Pull Request | Merge ineligible |
| Unresolved conversation | Merge ineligible on protected branch |

## Performance Considerations

Policy evaluation has two major costs:

1. finding applicable policies
2. evaluating their conditions

For an in-memory engine, policies can be indexed by action and resource type before condition evaluation.

For database-backed evaluation, indexes on policy activation, priority, action relationships, and frequently queried attributes reduce unnecessary scans.

Authorization decisions should not repeatedly perform expensive identity or policy lookups when the relevant information can safely be cached. Cache invalidation must be tied to policy and identity changes so that revoked permissions do not remain active longer than the security requirements allow.

Audit records can grow quickly. Production systems should therefore partition or archive audit data according to retention requirements while preserving sufficient information for security investigations.

## Pull Request, Code Review, Approvals, and Branch Protection

These repository concepts are related but represent different control layers.

### Pull Requests

A Pull Request is the workflow for proposing a set of changes from a source branch toward a target branch.

The domain represented in the C++ and PostgreSQL implementations includes:

- source branch
- target branch
- commits
- author
- draft state
- open or closed state
- mergeability
- conversations
- final merge eligibility

A Pull Request describes the proposed change and its lifecycle. It does not itself constitute an approval.

### Code Review

Code Review evaluates the proposed changes.

The data model represents:

- reviewer identity
- review state
- comments
- comment resolution
- reviewer eligibility
- stale reviews

Review comments can identify a problem without granting approval. A review can also request changes.

Review quality depends on the reviewer evaluating the relevant behavior, security implications, correctness, maintainability, and scope rather than merely producing an approval count.

### Approvals

An approval is a review decision indicating that a reviewer accepts the current state under the applicable review policy.

The model distinguishes current approvals from stale approvals.

Approval eligibility can depend on:

- active reviewer status
- reviewer identity
- independence from the author
- review state
- review freshness
- repository policy

Two approvals from the same reviewer do not provide the same independence as approvals from two eligible reviewers, so the examples count distinct reviewers.

### Branch Protection

Branch protection is repository-level enforcement.

It can require:

- minimum approvals
- passing status checks
- resolved conversations
- restricted direct pushes
- restricted force pushes
- linear history

Branch protection does not replace review. It enforces conditions after the review and automated-check state has been evaluated.

The relationship is:

```text
Pull Request
    |
    | proposes changes
    v
Code Review
    |
    | evaluates changes
    v
Approvals
    |
    | records review decisions
    v
Branch Protection
    |
    | enforces repository conditions
    v
Merge Eligibility
    |
    v
Merge
```

Keeping these layers distinct prevents a passing status check from being mistaken for a human approval and prevents an approval from being mistaken for permission to bypass branch protection.

## Implementation Comparison

| Implementation | Primary perspective | Important mechanism |
|---|---|---|
| Python | Policy simulation | Dataclasses, attribute resolution, condition evaluation, audit events |
| JavaScript | Event-driven authorization | `EventEmitter`, predicates, asynchronous service boundary |
| C++17 | Governance engine | Explicit merge-eligibility domain model and STL-based evaluation |
| Java 17 | Enterprise authorization service | Records, interfaces, predicates, repository abstraction, explicit exceptions |
| PostgreSQL | Persistent authorization and governance | Relational schema, constraints, triggers, functions, views, transactions |

## Practical Workflow

A request entering an ABAC system can follow this sequence:

```text
1. Authenticate subject
        |
2. Collect subject attributes
        |
3. Identify resource
        |
4. Identify requested action
        |
5. Collect contextual attributes
        |
6. Validate request attributes
        |
7. Select applicable policies
        |
8. Evaluate conditions
        |
9. Apply policy precedence
        |
10. Produce allow or deny
        |
11. Record audit event
```

The same structure can be applied to application APIs, administrative operations, data services, internal platforms, and repository governance.

## Limitations

The examples intentionally use deterministic in-memory policies or a compact relational policy representation.

A production authorization platform may require additional controls such as:

- policy versioning
- policy lifecycle approval
- distributed policy caching
- identity-provider integration
- attribute freshness guarantees
- revocation propagation
- centralized audit storage
- tamper-resistant audit records
- policy simulation before deployment
- administrative separation of duties
- formal policy testing
- high-availability policy distribution

The sample systems provide the core decision model without assuming a particular identity provider, cloud platform, source-control vendor, or deployment architecture.

## Key Distinctions

The central distinctions implemented throughout the project are:

| Concept | Question answered |
|---|---|
| Subject attributes | Who is requesting access and what properties does the subject have? |
| Resource attributes | What is being accessed and how sensitive is it? |
| Action | What operation is being requested? |
| Context | Under what circumstances is the request occurring? |
| Policy | What conditions determine the decision? |
| Review | What did a human reviewer decide about proposed changes? |
| Approval | Does an eligible reviewer approve the current change state? |
| Branch protection | What repository-level conditions must hold before merging? |
| Authorization decision | Is the requested operation permitted under the active policy set? |
| Audit event | What decision was made, why, and which policies contributed? |
