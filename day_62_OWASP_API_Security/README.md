# OWASP API Security and Repository Governance

## Scope

This learning artifact models API security as an engineering control that must be evaluated during repository change management.

The five source files use the same core domain while giving each language a different implementation perspective:

| File | Engineering perspective |
|---|---|
| Python | Repository workflow simulation and merge-policy evaluation |
| JavaScript | Event-driven security and policy evaluation |
| C++17 | Repository governance and merge-eligibility engine |
| Java 17 | Enterprise domain model with explicit policies and state transitions |
| PostgreSQL | Relational representation of repository governance, reviews, security findings, and merge eligibility |

The API security model focuses on five concrete failure classes:

- Broken authorization
- Excessive data exposure
- Injection
- Server-Side Request Forgery (SSRF)
- Security misconfiguration

The repository model keeps four related concepts distinct:

```text
Pull Request
    |
    v
Proposed change
    |
    v
Code Review
    |
    v
Review decisions
    |
    v
Approvals
    |
    v
Branch Protection
    |
    v
Merge Eligibility
    |
    v
Merge
```

The relationship is intentional. A Pull Request proposes a change. Code Review evaluates that change. Approvals record review decisions. Branch Protection enforces repository-level conditions before the change can be merged.

API security findings are evaluated as part of the merge decision rather than being treated as unrelated documentation.

---

## API Security Model

The implementation uses five API security categories.

| Category | Example failure | Repository control |
|---|---|---|
| Broken authorization | User accesses another tenant's object | Authorization tests and security review |
| Excessive data exposure | Endpoint returns fields not required by the client | Response-schema review |
| Injection | Untrusted input reaches a query or interpreter | Security scanning and review |
| SSRF | User-controlled URL reaches an internal service | Outbound-request validation |
| Security misconfiguration | Unsafe production API settings remain enabled | Security checks and protected-branch policy |

The model treats high and critical findings as merge-blocking conditions until they are resolved.

Low-severity findings can be recorded without automatically preventing a merge. This separates security observation from security enforcement.

---

## Pull Requests

A Pull Request is represented as a proposed change from a source branch to a target branch.

The model records:

- Pull Request number
- title
- author
- source branch
- target branch
- base commit
- current head commit
- state
- draft status
- commits
- reviews
- status checks
- review conversations
- security findings
- merge commit

A source branch contains the proposed implementation. The target branch represents the branch that will receive the change if the repository policy permits merging.

The base commit is important because a Pull Request can become stale. If the target branch moves after the Pull Request was created, the reviewed base may no longer represent the current target state.

The Python, C++17, Java, and PostgreSQL implementations explicitly compare the Pull Request base SHA with the current target-branch SHA. A mismatch blocks a protected-branch merge until synchronization occurs.

### Pull Request lifecycle

```yaml
Draft
  |
  v
Open
  |
  +----> Closed
  |
  v
Reviewed
  |
  v
Eligible
  |
  v
Merged
```

A closed Pull Request can be reopened in the Python model. A merged Pull Request cannot be returned to an open state.

Draft Pull Requests remain visible for collaboration but are explicitly excluded from merge eligibility.

### Commits and changesets

Each Pull Request can contain multiple commits. The current head SHA identifies the exact version under review.

This matters for approvals. An approval for commit `A` should not automatically authorize a later commit `B` that was never reviewed.

The Python, JavaScript, C++17, and Java 17 implementations invalidate or dismiss previous approvals when a new commit is added. The PostgreSQL model stores `reviewed_head_sha` so queries can distinguish current approvals from stale approvals.

---

## Code Review

Code Review is the evaluation mechanism applied to a proposed change.

It is distinct from the Pull Request itself. The Pull Request provides the workflow container, while reviews record technical evaluation.

The implementations support review states such as:

- Commented
- Approved
- Changes requested
- Dismissed

A review can contain inline comments associated with:

- reviewer
- file path
- line number
- comment text
- resolution state

### Review scope

The model uses realistic review criteria for API security changes:

| Review criterion | Example question |
|---|---|
| Authorization | Can one tenant access another tenant's object? |
| Data exposure | Does the response expose fields the client does not require? |
| Injection | Does untrusted input reach a database or interpreter unsafely? |
| SSRF | Can an attacker make the server contact internal destinations? |
| Configuration | Are unsafe API settings enabled in the deployment environment? |
| Regression | Do existing authorization and security tests still pass? |

The reviewer is responsible for assessing the implementation, not merely confirming that the Pull Request exists.

### Review conversations

Inline comments create conversations that may require resolution.

The source implementations intentionally include a scenario in which approvals exist but an unresolved security conversation prevents merging.

This demonstrates an important distinction:

```yaml
Approval exists
        |
        v
Review decision recorded
        |
        v
Conversation unresolved
        |
        v
Protected branch still blocks merge
```

Resolving a conversation does not itself create an approval. It removes one repository-policy obstacle.

### Review failure modes

The model handles several review failures:

- Self-approval
- Approval on an outdated commit
- Dismissed approval
- Unresolved conversation
- Missing required reviewer
- Missing code-owner approval
- Review submitted after the Pull Request is no longer open

These controls prevent the review record from becoming a weak administrative checkbox.

---

## Approvals

An approval is a review decision stating that the reviewer accepts the reviewed state of the change.

The implementations distinguish approval from merge eligibility.

An approval can be valid as a review decision while the Pull Request remains unmergeable because:

- required checks are failing
- a security finding is blocking the merge
- the base branch is stale
- a conversation remains unresolved
- the required number of approvals has not been reached
- a required code owner has not approved

### Current versus stale approvals

The reviewed commit SHA is central to approval validity.

For example:

```less
Commit A
  |
  +--> Reviewer approves A
  |
  v
Commit B added
  |
  v
Approval for A becomes stale
  |
  v
Reviewer must reassess B
```

This is implemented directly in Python, JavaScript, C++, and Java. PostgreSQL stores the reviewed SHA and uses it when calculating current approvals.

### Eligible reviewers

Self-approval is prohibited.

The approval engine also excludes dismissed reviews and ignores approvals associated with an outdated head commit.

Code-owner review is treated separately from the numeric approval requirement. A Pull Request modifying API or authentication code can require approval from a designated security owner even when enough ordinary reviewers have approved it.

This prevents a repository from satisfying a numeric review threshold without receiving the specialized security review required for sensitive code.

### Dismissed approvals

A dismissed approval is not counted as a current approval.

Dismissal can occur when:

- the review is explicitly dismissed
- a new commit invalidates the reviewed state
- repository policy requires reassessment

The implementation uses the latest review state for each reviewer rather than counting every historical approval.

---

## Branch Protection

Branch Protection is repository-level enforcement.

It is not a review and it is not an approval.

The model uses protected branches to enforce conditions such as:

- required status checks
- required approvals
- code-owner approval
- conversation resolution
- linear history
- direct-push restrictions
- force-push restrictions
- branch deletion restrictions
- administrator bypass policy

A protected branch therefore acts as the final policy boundary before merge.

### Required status checks

The sample policy requires:

- `unit-tests`
- `api-security-scan`
- `authorization-tests`

All required checks must pass.

A Pull Request with two passing checks and one failed check remains ineligible.

The JavaScript implementation uses a `Map` for current check state. The Python implementation stores checks as structured objects. C++ uses STL containers, Java uses collections, and PostgreSQL uses a normalized `status_check` table.

### Direct pushes

The governance model assumes that protected branches should receive changes through the controlled Pull Request path rather than arbitrary direct pushes.

This is particularly important for security-sensitive API code because bypassing review can bypass:

- authorization testing
- security scanning
- code-owner review
- required approvals
- conversation resolution

### Force pushes

The sample branch policy disables force pushes.

Force pushing a protected branch can rewrite history that other engineers have already reviewed. The policy therefore treats history integrity as a repository governance concern.

### Branch deletion

Protected branches also restrict deletion.

A default or production branch represents an important repository control boundary and should not be removable through an ordinary feature workflow.

### Linear history

The policy records a linear-history requirement.

The source implementations treat this as a governance property rather than trying to emulate every Git object operation. The database stores the policy so the repository control plane can enforce the requirement.

### Administrator behavior

Administrator status is represented explicitly.

The policy also contains an administrator-bypass flag. The sample configuration disables bypass because a security-sensitive repository should not silently weaken protected-branch rules merely because the actor has administrative privileges.

---

## API Security During Repository Change

The practical workflow combines the four governance concepts with API security.

```sql
Developer
    |
    v
Feature branch
    |
    v
Pull Request
    |
    +-----------------------+
    |                       |
    v                       v
Code Review            Automated checks
    |                       |
    v                       +--> Unit tests
Approvals                  +--> Authorization tests
    |                       +--> API security scan
    v
Security findings
    |
    +--> Low/medium: review and disposition
    |
    +--> High/critical: block merge
    |
    v
Branch Protection
    |
    v
Merge eligibility
    |
    v
Protected target branch
```

This structure prevents the security categories from being confused with repository mechanisms.

Broken authorization is a security defect.

An approval is a review decision.

A status check is an automated result.

Branch Protection is the enforcement policy.

A Pull Request is the change-management workflow that brings those elements together.

---

## Broken Authorization

Broken authorization occurs when the API fails to enforce whether an authenticated principal is allowed to perform an operation on a particular resource.

A common object-level example is:

`GET /api/orders/{id}`

Authentication establishes who the caller is. Authorization must establish whether that caller may access the requested order.

The source implementations record broken-authorization findings against endpoints and integrate them into merge eligibility.

The realistic control is tenant or object ownership validation before serialization.

The key distinction is:

```kotlin
Authentication
    |
    v
Who is the caller?
    |
    v
Authorization
    |
    v
Can this caller access this object?
```

The review process therefore checks authorization behavior rather than treating successful authentication as sufficient.

---

## Excessive Data Exposure

Excessive data exposure occurs when an endpoint returns more information than the client legitimately needs.

The repository model treats response-schema changes as security-sensitive.

A reviewer should examine:

- returned fields
- internal identifiers
- administrative attributes
- tenant information
- credentials or tokens
- operational metadata
- fields not required by the consuming client

The appropriate control is deliberate response shaping rather than assuming that hiding a field in a user interface provides protection.

The governance model allows such findings to be recorded against the Pull Request and reviewed before merge.

---

## Injection

Injection occurs when attacker-controlled input crosses a boundary into a parser, interpreter, query language, command processor, or similar execution mechanism without adequate separation or validation.

The repository workflow treats injection controls as part of API security checks.

The relevant review questions include:

- Where does the input originate?
- Which component parses it?
- Is parameterization used?
- Is input validation appropriate to the expected data type?
- Can validation be bypassed through alternate encodings?
- Does the API pass the value to another subsystem?

A passing unit-test suite alone does not prove that an injection risk is absent. The security scan and focused review provide separate controls.

---

## SSRF

Server-Side Request Forgery occurs when an attacker can influence a server-side request destination in a way that permits access to unintended resources.

The JavaScript, C++17, Java, Python, and PostgreSQL scenarios represent SSRF as a security finding associated with an outbound-request endpoint.

A high-severity SSRF finding blocks merge.

Relevant controls include:

- validating outbound destinations
- restricting allowed schemes
- preventing access to private network ranges
- restricting metadata-service destinations
- controlling redirects
- validating the final destination after resolution
- applying network-level egress restrictions

The repository control does not claim that a review alone prevents SSRF. It ensures that identified SSRF risk becomes a merge-blocking repository condition.

---

## Security Misconfiguration

Security misconfiguration covers unsafe deployment or API settings.

Examples include:

- debug behavior exposed in production
- overly permissive CORS configuration
- unnecessary API endpoints
- weak transport requirements
- verbose error responses
- unsafe default settings
- missing security headers where relevant
- unnecessary administrative interfaces

The repository model represents misconfiguration findings in the same security-finding structure while keeping the category distinct from authorization, data exposure, injection, and SSRF.

---

## Python Implementation

The Python implementation is a complete in-memory repository workflow.

Its main domain types are:

- `Repository`
- `Branch`
- `PullRequest`
- `Commit`
- `Review`
- `ReviewComment`
- `StatusCheck`
- `SecurityFinding`
- `BranchProtection`
- `MergeEligibility`

`dataclass` objects provide explicit domain records, while enums prevent uncontrolled string states.

The `Repository` class manages lifecycle operations such as Pull Request creation, commit addition, review submission, synchronization, comment resolution, and merge.

The `MergeEligibility` class separates policy evaluation from repository state mutation.

A notable implementation detail is approval invalidation after a new commit. This models the difference between an approval of a particular commit and an unconditional approval of every future change.

The script also prints a structured repository governance report using the standard-library `json` module.

No third-party dependency is required.

---

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library features and emphasizes event-driven behavior.

`EventEmitter` represents repository events such as:

- security finding creation
- review submission
- Pull Request merge

The event model separates state mutation from observers that may log, audit, or trigger additional processing.

`Map` is used for current status-check state and reviewer decisions. `Set` represents approval and code-owner collections.

The asynchronous `runSecurityPipeline` function represents an automated validation stage without requiring external npm packages.

Security findings have explicit severity values. High and critical findings become blocking conditions.

The implementation also demonstrates an unresolved review conversation blocking an otherwise well-reviewed Pull Request.

---

## C++17 Implementation

The C++17 implementation is designed as a repository governance engine.

It uses:

- `struct` for domain records
- `enum class` for controlled states
- STL containers for branches, reviews, findings, and checks
- custom exceptions for validation and merge failures
- a dedicated `MergeEligibilityEngine`
- explicit security-policy evaluation

The `MergeEligibilityEngine` does not mutate repository state while evaluating a Pull Request. This separation makes the policy engine easier to reason about and reduces accidental state changes during validation.

The implementation checks:

1. Pull Request state
2. draft status
3. stale base branch
4. required status checks
5. unresolved conversations
6. high and critical security findings
7. current approvals
8. code-owner approval

The merge operation occurs only after the policy engine returns an eligible result.

This architecture is suitable for a repository control-plane service where policy evaluation should be independently testable from repository mutation.

---

## Java 17 Implementation

The Java implementation uses an enterprise-oriented domain model.

Records represent immutable value objects such as:

- `User`
- `Commit`
- `StatusCheck`
- `SecurityFinding`
- `ReviewComment`
- `Review`
- `Branch`
- `BranchProtectionPolicy`
- `EligibilityResult`

The mutable `PullRequest` aggregate controls changes to its own workflow state.

`ReviewPolicy` provides an interface for policy evaluation. `ApiSecurityReviewPolicy` implements the repository's security-aware merge policy.

`RepositoryGovernanceService` owns repository-level operations.

The design separates:

```yaml
Domain values
    |
    v
Pull Request aggregate
    |
    v
Review policy
    |
    v
Governance service
    |
    v
Merge
```

Custom exceptions represent validation and merge-policy failures.

The policy uses immutable sets for required checks and code-owner definitions, reducing accidental modification of security rules during normal workflow execution.

---

## PostgreSQL Implementation

The PostgreSQL implementation provides a normalized relational representation of the complete workflow.

Core entities include:

- repositories
- users
- branches
- commits
- changed files
- Pull Requests
- Pull Request commits
- reviews
- review comments
- status checks
- security findings
- branch protection policies
- required checks
- code-owner rules
- approval requirements

Foreign keys maintain relationships between these entities.

Check constraints enforce local invariants such as positive review-comment line numbers and non-empty branch and commit values.

Unique constraints prevent duplicate repository names, branch names within a repository, commit SHAs within a repository, and repeated status checks for the same Pull Request.

Partial indexing is used for unresolved review comments because unresolved conversations are a common merge-eligibility query.

### Database-level enforcement

The `prevent_self_approval` trigger prevents a Pull Request author from recording an approval for their own Pull Request.

The merge-state trigger ensures that a Pull Request marked as merged contains a merge commit SHA.

The `resolve_review_comment` function provides an explicit state transition for resolving a review conversation.

### Merge eligibility function

`merge_eligibility` evaluates:

- Pull Request state
- target branch freshness
- required status checks
- code-owner approval
- unresolved conversations
- current approvals
- unresolved high and critical security findings

It returns a Boolean eligibility result and a human-readable reason.

This places important repository policy logic near the data that it governs.

### Transactional merge

The final transaction updates the Pull Request and target branch together.

The intent is:

```sql
BEGIN
  |
  +--> verify eligibility
  |
  +--> mark Pull Request merged
  |
  +--> advance protected branch
  |
COMMIT
```

If the transaction fails, PostgreSQL can roll back the state changes rather than leaving the Pull Request and target branch inconsistent.

---

## Merge Eligibility Rules

The five implementations converge on the same policy model.

For a protected branch, a Pull Request is eligible only when the required conditions are satisfied.

| Condition | Purpose |
|---|---|
| Open Pull Request | Prevent invalid lifecycle transitions |
| Not draft | Prevent unfinished changes from merging |
| Current base | Ensure the reviewed target state is current |
| Required checks passing | Enforce automated validation |
| Required approvals | Enforce human review threshold |
| Current approvals | Prevent stale approval reuse |
| Code-owner approval | Require specialized security review |
| Conversations resolved | Prevent unresolved review concerns |
| No blocking security finding | Prevent known high-risk API defects |
| Protected-branch rules satisfied | Enforce repository governance |

The policy is intentionally conjunctive. Meeting one condition does not compensate for failure of another.

---

## Edge Cases

### Stale Pull Request

A Pull Request is opened against commit `A`.

The target branch advances to commit `B`.

The Pull Request still references `A` as its base.

The implementation blocks the merge until the Pull Request is synchronized with the target branch.

### New commit after approval

A reviewer approves commit `A`.

The author pushes commit `B`.

The approval is no longer considered current.

The reviewer must review `B`.

### Unresolved conversation

Required reviewers approve the Pull Request, but an inline security comment remains unresolved.

Branch Protection blocks the merge.

### High-severity security finding

All required checks and reviews pass, but the security scan identifies a high-severity SSRF issue.

The Pull Request remains unmergeable.

### Self-approval

The Pull Request author attempts to approve their own change.

The Python, JavaScript, Java, and PostgreSQL models reject or exclude that approval.

### Missing code owner

The Pull Request changes API security code but lacks approval from the designated security owner.

The protected-branch policy blocks the merge even if the numeric approval threshold has otherwise been met.

### Draft Pull Request

A draft can contain commits and reviews but cannot be merged until its lifecycle state changes to open.

---

## Security and Governance Boundaries

The implementation intentionally keeps the following boundaries separate:

| Mechanism | Question answered |
|---|---|
| Pull Request | What change is being proposed? |
| Code Review | Has the implementation been technically evaluated? |
| Approval | Which reviewer accepted the reviewed state? |
| Status Check | Did an automated control pass? |
| Security Finding | What API security risk was identified? |
| Branch Protection | Which repository conditions must hold? |
| Merge Eligibility | Are all required conditions currently satisfied? |
| Merge | Was the change actually incorporated? |

This separation prevents repository workflow concepts from being confused with API vulnerability categories.

---

## Performance Considerations

The in-memory implementations use maps and sets for frequent lookups of:

- branches
- Pull Requests
- status checks
- reviewers
- approvals
- code owners

Approval calculation is based on the latest review for each reviewer rather than scanning every historical review as an independent approval.

The PostgreSQL implementation uses indexes for repository and Pull Request state lookups, status checks, security findings, and unresolved conversations.

The database model deliberately avoids indiscriminate indexing. Every index has a relationship to a lookup used by workflow or reporting operations.

The merge-eligibility operation is bounded by the Pull Request's associated reviews, checks, comments, findings, and changed files.

---

## Security Considerations of the Governance Model

Repository governance does not replace secure API implementation.

It provides enforcement around the development process.

The model reduces the chance that known security defects are merged by requiring explicit checks and review decisions.

Important controls include:

- least-privilege reviewer roles
- code-owner review for sensitive paths
- protection of default branches
- stale-approval invalidation
- automated security checks
- unresolved-conversation blocking
- high and critical finding blocking
- audit-friendly state records
- transactional database updates
- explicit merge eligibility

The governance layer should itself be protected against unauthorized policy changes. In a production implementation, policy configuration would require appropriate administrative authorization and auditing.

---

## Practical Workflow

A realistic API security Pull Request follows this sequence:

```sql
Feature implementation
        |
        v
Security-focused tests
        |
        v
Pull Request opened
        |
        +--> Unit tests
        |
        +--> Authorization tests
        |
        +--> API security scan
        |
        v
Code Review
        |
        +--> Inline security discussions
        |
        +--> Code-owner review
        |
        v
Approvals
        |
        v
Conversation resolution
        |
        v
Branch Protection evaluation
        |
        +--> stale base?
        +--> missing checks?
        +--> missing approvals?
        +--> stale approvals?
        +--> blocking finding?
        +--> unresolved discussion?
        |
        v
Merge eligible
        |
        v
Protected branch updated
```

This workflow makes API security part of the normal software delivery control path rather than a separate activity performed only after implementation.

---

## Terminology Distinctions

**Pull Request:** A repository workflow object representing proposed changes between branches.

**Code Review:** Technical evaluation of the proposed changes.

**Approval:** A review decision associated with a specific reviewed commit.

**Status Check:** An automated result associated with the Pull Request.

**Branch Protection:** Repository policy that determines which conditions must be satisfied before a protected branch can receive a merge.

**Security Finding:** A recorded API security issue associated with a proposed change.

**Merge Eligibility:** The current result of evaluating repository and security policy against the current Pull Request state.

**Stale Approval:** An approval associated with an older commit than the current Pull Request head.

**Code Owner:** A designated reviewer responsible for sensitive paths or components.

**Review Conversation:** A review comment and its resolution state, which can independently affect merge eligibility.

---

## Implementation Coverage

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Pull Request lifecycle | Yes | Yes | Yes | Yes | Yes |
| Branch state | Yes | Yes | Yes | Yes | Yes |
| Commit tracking | Yes | Yes | Yes | Yes | Yes |
| Reviews | Yes | Yes | Yes | Yes | Yes |
| Approvals | Yes | Yes | Yes | Yes | Yes |
| Stale approvals | Yes | Yes | Yes | Yes | Yes |
| Review conversations | Yes | Yes | Yes | Yes | Yes |
| Status checks | Yes | Yes | Yes | Yes | Yes |
| Branch protection | Yes | Yes | Yes | Yes | Yes |
| Code-owner policy | Yes | Yes | Yes | Yes | Yes |
| API security findings | Yes | Yes | Yes | Yes | Yes |
| Merge eligibility | Yes | Yes | Yes | Yes | Yes |
| Database constraints | No | No | No | No | Yes |
| Database triggers | No | No | No | No | Yes |
| Transactional merge | Simulated | Simulated | Simulated | Service-level | Yes |
| Event-driven processing | No | Yes | No | No | No |

---

## Technical Limitations

The implementations model repository governance and API security policy rather than implementing a complete Git hosting service.

They do not attempt to reproduce:

- Git object storage
- remote Git transport
- full diff parsing
- real CI infrastructure
- production identity federation
- real network egress enforcement
- complete API gateway behavior
- complete vulnerability scanning engines
- provider-specific repository administration APIs

The security findings are represented as domain records. A production platform would populate those records from real static analysis, dynamic testing, dependency analysis, authorization tests, gateway controls, or human review.

The branch-protection model represents the policy decisions explicitly so that the important engineering relationships can be evaluated without depending on a particular hosting provider's API.

The source files are therefore executable governance models rather than replacements for a complete Git hosting platform or API security gateway.
