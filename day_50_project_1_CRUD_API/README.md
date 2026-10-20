# Repository Governance CRUD API

## Scope

This project implements a production-oriented CRUD API around repository governance rather than treating Pull Requests, code review, approvals, and branch protection as interchangeable concepts.

The central relationship is:

`Pull Request → proposes changes → Code Review evaluates changes → Approvals record review decisions → Branch Protection enforces merge conditions`

The five implementations use different perspectives:

| Implementation | Primary responsibility |
|---|---|
| Python | FastAPI CRUD API and repository workflow model |
| JavaScript | Asynchronous API client and event-driven governance workflow |
| C++17 | In-memory merge-eligibility and governance engine |
| Java 17 | Enterprise domain model and explicit policy service |
| PostgreSQL | Relational persistence, integrity rules, reporting, and merge evaluation |

The CRUD API uses repositories as the main aggregate and exposes Pull Requests, reviews, and branch-protection policies through related resources.

## Pull Requests

A Pull Request represents a proposed change from a source branch to a target branch.

The source and target branches have separate roles:

- The source branch contains the proposed changes.
- The target branch identifies where those changes are intended to land.
- Commits form the changeset represented by the Pull Request.
- A draft Pull Request represents work that is not yet ready for normal merge evaluation.
- An open Pull Request can receive reviews and status checks.
- A closed Pull Request cannot be merged.
- A merged Pull Request represents a completed integration.

The Python API validates that the source and target branches differ and that a Pull Request contains at least one commit. It also exposes CRUD operations for repositories and operations for creating and evaluating Pull Requests.

The JavaScript implementation treats Pull Request creation as an asynchronous API operation. Validation happens before network activity so invalid branch relationships and merge strategies are rejected locally.

The PostgreSQL model stores source branch, target branch, state, merge strategy, commit count, and timestamps as separate relational attributes.

### Base-branch synchronization and conflicts

A Pull Request is evaluated against its target branch. If the target branch advances after the Pull Request was created, the proposed changes may become stale or conflict with newer commits.

The database records head and base commit identifiers, allowing a production implementation to compare the Pull Request's known base with the current target branch. A conflict must be resolved in the source branch or through an explicitly controlled update before merge.

Reopening a closed Pull Request is a lifecycle operation rather than a new Pull Request. Its historical reviews and discussions should remain auditable while merge eligibility is recalculated.

## Code Review

Code review evaluates the technical correctness and maintainability of a proposed changeset.

A review is represented separately from the Pull Request itself. The review identifies:

- reviewer
- review state
- review submission
- stale status
- review discussion

The possible review states distinguish a comment from an approval or an explicit request for changes.

Inline comments are represented by a separate table in PostgreSQL. Each comment identifies the review, file path, line number, text, and resolution state.

This separation is important because a Pull Request can contain many reviews, while one review can contain multiple discussions.

### Review responsibilities

A reviewer should evaluate the actual changeset rather than merely confirm that a Pull Request exists.

Relevant review criteria include:

- correctness
- security impact
- regression risk
- test coverage
- maintainability
- API compatibility
- database integrity
- operational consequences
- consistency with repository policy

Review scope is separate from branch protection. A branch policy can require two approvals, but it does not determine whether a reviewer has technically evaluated every relevant change.

### Review discussions

A review comment can remain unresolved after the reviewer has submitted a decision.

The SQL model therefore distinguishes:

`review state != discussion resolution`

An approval does not automatically resolve every comment made during the review.

When conversation resolution is required by branch protection, unresolved comments can independently block a merge.

## Approvals

An approval is a specific review decision.

The implementations distinguish an approval from general review activity.

A valid approval requires:

- an existing Pull Request
- an existing reviewer
- reviewer eligibility
- approval state
- non-stale status

The C++ and Java implementations count unique eligible reviewer identifiers rather than approval records. This prevents multiple approval records from the same reviewer from incorrectly satisfying a policy requiring multiple reviewers.

For example, if two approvals belong to the same reviewer, they count as one eligible approval.

### Stale approvals

A stale approval remains useful for audit history but cannot satisfy the current merge policy.

A new changeset can invalidate an earlier approval because the reviewer approved an earlier state of the code. The Python API marks previous approvals from the same reviewer as stale when a new approval is submitted.

The PostgreSQL model stores `stale` explicitly rather than deleting the historical review.

### Dismissed approvals

Dismissal is also different from deletion.

A dismissed review remains part of the audit history but does not count as an active approval. This allows repository administrators to determine why a previously valid decision no longer affects merge eligibility.

### Reviewer eligibility

Reviewer eligibility is modeled independently from approval state.

A reviewer can exist in the repository database but be ineligible for satisfying the protection policy. This allows organizational rules such as team membership, repository permissions, or reviewer assignment policies to be evaluated separately from the stored review itself.

## Branch Protection

Branch protection is repository-level governance.

It does not perform the code review. It defines conditions that must be satisfied before changes can be merged into a protected branch.

The project models these controls:

| Policy | Purpose |
|---|---|
| Required reviews | Minimum valid approval count |
| Required status checks | Requires successful automated checks |
| Conversation resolution | Prevents unresolved review discussions |
| Direct-push restriction | Prevents normal changes from bypassing the Pull Request workflow |
| Force-push restriction | Protects branch history |
| Deletion restriction | Prevents accidental removal of protected branches |
| Linear-history requirement | Restricts merge strategies that introduce merge commits |
| Administrator bypass | Represents an explicit governance exception |

A protected branch is identified independently from the Pull Request. This allows the same Pull Request mechanics to operate against protected and unprotected branches.

## Merge Eligibility

Merge eligibility is the point where the four concepts interact.

The decision engine evaluates conditions in a defined order:

`Pull Request state`
→ `target branch protection`
→ `status checks`
→ `eligible approvals`
→ `active change requests`
→ `conversation resolution`
→ `merge strategy`

A failure produces a concrete reason rather than a generic "merge failed" response.

Examples include:

- Pull Request is not open.
- Required status checks have not run.
- A status check failed.
- Required approvals are missing.
- An active reviewer requested changes.
- An approval is stale.
- A reviewer is not eligible.
- Review conversations remain unresolved.
- The selected merge strategy conflicts with linear-history policy.

The FastAPI endpoint `/pull-requests/{pull_request_id}/merge-eligibility` exposes this calculation without modifying repository state.

The merge endpoint performs the same evaluation before changing the Pull Request to `merged`.

This separation prevents a client from treating an approval as automatic permission to merge.

## Python Implementation

The Python implementation is the primary CRUD API.

FastAPI provides:

- HTTP routing
- request validation
- response models
- dependency injection
- automatic API documentation
- HTTP status handling

Pydantic models validate repository and Pull Request input before it reaches the database layer.

SQLAlchemy provides the relational domain model:

`Repository → Branch`

`Repository → PullRequest → Review`

`PullRequest → StatusCheck`

`Repository → BranchProtection`

Relationships use foreign keys and cascading behavior appropriate to their ownership.

Repository deletion cascades to owned Pull Requests, branches, reviews, and status checks. Reviewer records are protected from deletion while referenced by reviews.

The merge operation returns HTTP `409 Conflict` when governance conditions prevent the operation. This communicates that the request is syntactically valid but conflicts with current repository state.

The API expects a PostgreSQL connection through `DATABASE_URL`. For a production deployment, schema evolution should be managed through Alembic migrations rather than automatic table creation.

## JavaScript Implementation

The JavaScript implementation does not reproduce the Python ORM model.

It acts as an asynchronous client for the API and demonstrates client-side workflow control.

`RepositoryGovernanceClient` handles:

- repository creation
- Pull Request creation
- protection configuration
- merge-eligibility retrieval
- merge requests

The `request` function centralizes HTTP error processing.

`ApiError` preserves the HTTP status so callers can distinguish validation failures, authorization failures, conflicts, and server errors.

`GovernanceEventBus` uses the browser-compatible `EventTarget` and `CustomEvent` interfaces to emit workflow events.

The example emits events for repository creation and merge blocking rather than coupling the workflow directly to console output.

Validation is performed before requests are sent. Server-side validation remains authoritative because client-side validation cannot enforce repository integrity by itself.

## C++ Implementation

The C++ program models governance as an in-memory policy engine.

Its principal responsibility is merge eligibility rather than CRUD transport.

`GovernanceEngine` evaluates a Pull Request against:

- protected branches
- required approval count
- reviewer eligibility
- stale approvals
- requested changes
- unresolved discussions
- status checks
- linear-history requirements
- commit availability

The engine stores reviewers in a map keyed by reviewer ID. Valid approvals are accumulated in a set so duplicate approvals from one reviewer cannot inflate the approval count.

This implementation makes the policy calculation independent from HTTP and database concerns.

The second evaluation deliberately introduces failures:

- one approval becomes stale
- one status check fails
- an unresolved discussion is added

The resulting decision contains multiple blocking reasons, illustrating why a production governance engine should report all material policy violations rather than stop at the first failure.

## Java Implementation

The Java implementation emphasizes explicit enterprise domain modeling.

Records are used for immutable value-oriented types such as:

- `Reviewer`
- `Review`
- `ReviewComment`
- `StatusCheck`
- `BranchProtectionPolicy`
- `MergeDecision`

`PullRequest` remains a mutable domain object because its lifecycle changes from open to merged and its review and status-check collections evolve over time.

`MergeEligibilityService` contains the policy evaluation independently of the Pull Request entity.

This separation makes policy behavior testable without requiring an HTTP server or database.

The model also represents review comments separately from review state. An approval therefore does not implicitly resolve every conversation.

The example includes an ineligible reviewer and a stale approval to demonstrate that stored review records and valid merge authorization are different concepts.

## PostgreSQL Implementation

The PostgreSQL script provides the relational persistence model.

Primary keys identify entities while foreign keys preserve relationships.

Important integrity rules include:

- repository names are unique
- branch names are unique within a repository
- source and target branches must differ
- Pull Requests require at least one commit
- reviewer usernames are unique
- review comments require positive line numbers
- branch protection has one policy per repository
- required approvals are bounded
- referenced reviewers cannot be deleted while their reviews remain

Indexes target actual access patterns:

- Pull Requests by repository and state
- reviews by Pull Request and review state
- status checks by Pull Request
- unresolved review comments

The `merge_eligibility` SQL function evaluates the current relational state using CTEs.

The CTEs separate:

- Pull Request state
- branch protection policy
- valid approval count
- failed status checks
- unresolved conversations
- active change requests

This makes the database capable of producing an auditable merge decision without depending on application-side state.

## CRUD Boundaries

The API follows resource boundaries instead of treating every operation as a generic database update.

| Operation | Resource | Purpose |
|---|---|---|
| POST | `/repositories` | Create repository |
| GET | `/repositories` | List repositories |
| GET | `/repositories/{id}` | Retrieve repository |
| PATCH | `/repositories/{id}` | Update repository |
| DELETE | `/repositories/{id}` | Delete repository |
| POST | `/repositories/{id}/pull-requests` | Create Pull Request |
| GET | `/repositories/{id}/pull-requests` | Query Pull Requests |
| POST | `/pull-requests/{id}/reviews` | Submit review |
| PUT | `/repositories/{id}/protection` | Configure branch policy |
| GET | `/pull-requests/{id}/merge-eligibility` | Evaluate governance |
| POST | `/pull-requests/{id}/merge` | Attempt controlled merge |

A merge is intentionally not modeled as an unrestricted update to the Pull Request state. The service first evaluates repository policy.

## Validation and Failure Conditions

Validation exists at multiple layers.

### API validation

Pydantic validates:

- string lengths
- branch names
- commit counts
- merge strategies
- approval ranges

### Domain validation

The application rejects:

- duplicate repository names
- identical source and target branches
- nonexistent repositories
- nonexistent reviewers
- ineligible reviewers
- invalid merge transitions

### Database validation

PostgreSQL enforces:

- uniqueness
- foreign-key integrity
- valid enumerated states
- positive commit counts
- valid line numbers
- valid protection ranges

The layered approach is deliberate. API validation provides useful client errors, domain validation protects business behavior, and database constraints remain the final integrity boundary.

## Performance Considerations

Repository queries are ordered and bounded to prevent unrestricted result retrieval.

The SQL indexes correspond to common governance queries rather than indexing every column.

Approval evaluation uses distinct reviewer identifiers because the required-review policy concerns independent reviewers rather than the number of review records.

The C++ engine uses hash/set-style membership semantics conceptually through `std::set`, making duplicate approval detection explicit.

For larger repositories, production implementations should paginate Pull Requests and reviews, avoid loading complete review histories for every request, and calculate governance state from only the relevant Pull Request.

Database connection pooling is configured in the Python SQLAlchemy engine to avoid opening a new PostgreSQL connection for every HTTP request.

## Security and Governance Considerations

Repository governance is security-sensitive because bypassing the merge policy can introduce unauthorized or unreviewed changes.

Production deployments should therefore enforce:

- authenticated API requests
- authorization checks for repository mutations
- reviewer permission verification
- protected administrative operations
- HTTPS
- secrets supplied through environment or secret-management systems
- audit logging for policy changes
- audit logging for approval dismissal
- audit logging for bypass operations
- transaction boundaries around state-changing operations

The sample code models policy decisions but does not provide an identity provider or complete authorization framework. Authentication and authorization should not be inferred merely from the presence of a reviewer record.

Administrator bypass is represented explicitly in the PostgreSQL policy model. A bypass should be treated as an auditable governance exception rather than silently ignoring branch protection.

## Transactional Behavior

The PostgreSQL script uses a transaction when approvals are made stale and the Pull Request timestamp is updated.

This is important because a changeset transition and the invalidation of prior approvals represent one logical governance event.

If one part of such an operation fails in production, the transaction should prevent a partially updated governance state.

Merge execution should use the same principle: eligibility should be checked against the state being modified, and the state transition should occur transactionally.

## API Documentation

FastAPI exposes OpenAPI documentation automatically from the declared routes and Pydantic schemas.

The API therefore documents:

- request structures
- response structures
- validation constraints
- HTTP methods
- error responses

The documentation reflects the actual CRUD and governance endpoints rather than requiring a separate manually maintained API description.
