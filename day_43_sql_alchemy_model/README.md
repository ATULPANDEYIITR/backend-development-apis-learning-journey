# SQLAlchemy Models: Declarative Models, Columns, Primary Keys, Relationships

## Scope

This learning artifact focuses on SQLAlchemy's declarative ORM model layer and uses a repository-governance domain to make the model mechanics concrete.

The domain contains repositories, branches, Pull Requests, users, commits, reviewers, reviews, review comments, status checks, and branch-protection policies. These entities provide distinct relationship patterns without reducing SQLAlchemy to a collection of generic syntax examples.

The central idea is that a SQLAlchemy declarative model maps a Python class to a relational table. `mapped_column()` describes individual database columns, while `relationship()` describes how mapped objects navigate associations represented by foreign keys or association tables.

The implementations deliberately separate these concerns:

| Model concept | Repository-governance example |
| --- | --- |
| Declarative class | `Repository`, `Branch`, `PullRequest`, `User` |
| Primary key | `id` or `*_id` columns |
| Foreign key | `PullRequest.author_id` and branch/repository references |
| One-to-many | Repository to branches |
| One-to-one | Branch to branch-protection policy |
| Many-to-many | Pull Requests to assigned reviewers |
| Child collection | Pull Request commits and reviews |
| Association table | `pull_request_reviewers` |
| Constraints | Unique identifiers, nullable rules, and database relationships |
| ORM navigation | `pull_request.author`, `pull_request.reviews`, `repository.branches` |

## Declarative Model Architecture

Modern SQLAlchemy 2.x declarative mapping commonly starts with a class derived from `DeclarativeBase`.

The Python implementation defines:

`class Base(DeclarativeBase): pass`

Mapped classes inherit from this base. SQLAlchemy collects their mapping information in `Base.metadata`.

`Base.metadata.create_all(engine)` then uses that metadata to create the tables represented by the mapped classes.

This is different from manually writing SQL for every table operation. The model definition becomes the Python representation of the relational schema, while SQLAlchemy's engine and ORM machinery translate object-oriented operations into SQL.

The model is still relational. A Python relationship is not itself a database column. The database relationship is represented by foreign keys or association tables, and SQLAlchemy uses `relationship()` to expose that structure as convenient Python object navigation.

## Columns

The Python implementation uses SQLAlchemy 2.x typed mappings such as:

`id: Mapped[int] = mapped_column(Integer, primary_key=True)`

This declaration expresses several facts simultaneously:

- `id` is a Python attribute.
- `Mapped[int]` communicates the mapped Python type.
- `mapped_column()` creates the column mapping.
- `Integer` describes the SQL column type.
- `primary_key=True` identifies the column as part of the table's primary key.

String attributes use declarations such as:

`username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)`

The database therefore receives a constrained string column rather than an unconstrained Python attribute.

The distinction between Python-level typing and database-level constraints matters. A type annotation communicates how the application expects the value to be represented. `nullable=False`, `unique=True`, foreign keys, and database constraints establish relational integrity.

## Primary Keys

A primary key uniquely identifies a row.

The example uses integer primary keys for users, repositories, branches, Pull Requests, commits, reviews, and protection policies.

For example, `User.id` identifies one user while `PullRequest.id` identifies one Pull Request. A Pull Request's `author_id` does not duplicate the user's complete data. It stores the foreign-key identity that points toward the user row.

This produces a normal relational structure:

`users.id -> pull_requests.author_id`

The ORM turns that foreign-key relationship into an object-level relationship through:

`author: Mapped["User"] = relationship(...)`

Consequently, application code can use `pull_request.author.username` rather than manually joining user rows for every object navigation operation.

## Foreign Keys and Relationships

Foreign keys establish database-level references.

A Pull Request has:

`author_id -> users.id`

A branch has:

`repository_id -> repositories.id`

A commit has:

`pull_request_id -> pull_requests.id`

A review has both:

`pull_request_id -> pull_requests.id`

and:

`reviewer_id -> users.id`

The corresponding `relationship()` definitions provide the object-level representation.

For example, `Repository.branches` is a collection because one repository can contain many branches.

The relationship is configured with:

`relationship(back_populates="repository")`

The reverse side on `Branch` points back to the repository.

This creates bidirectional ORM navigation:

`repository.branches`

and:

`branch.repository`

The two attributes represent different directions through the same relational relationship.

## One-to-Many Relationships

The repository model contains a clear one-to-many relationship.

One repository can contain many branches:

`Repository -> Branch`

The foreign key is stored on `branches.repository_id`.

The ORM side is represented by a collection on `Repository`:

`branches: Mapped[List["Branch"]]`

and a scalar relationship on `Branch`:

`repository: Mapped["Repository"]`

This distinction is important. The parent side represents a collection because several rows can refer to the same parent. The child side represents one repository because each branch belongs to one repository in this model.

The same pattern appears between:

- Repository and Pull Requests
- Pull Request and commits
- Pull Request and reviews
- Review and review comments

Each relationship expresses a different domain ownership boundary.

## One-to-One Relationship

Branch protection is modeled as a one-to-one relationship.

A branch has at most one `BranchProtection` object:

`protection_policy: Mapped[Optional["BranchProtection"]]`

The database column `branch_id` in `branch_protection` is unique. That uniqueness is essential because a normal foreign key alone would permit multiple protection rows for the same branch.

The combination of:

`ForeignKey("branches.id")`

and:

`unique=True`

therefore enforces the intended one-to-one structure.

The Python `uselist=False` relationship configuration tells SQLAlchemy that the branch should expose a scalar protection object rather than a collection.

This is a useful distinction between database cardinality and ORM presentation.

## Many-to-Many Relationships

A Pull Request can have several assigned reviewers, and a reviewer can participate in many Pull Requests.

That is a many-to-many relationship:

`PullRequest <-> User`

It requires an association table:

`pull_request_reviewers`

The association table contains:

`pull_request_id`

and:

`reviewer_id`

Together these columns form the primary key.

SQLAlchemy maps this table using:

`secondary=pull_request_reviewers`

The Pull Request therefore exposes:

`reviewers`

while the user exposes:

`assigned_pull_requests`

This design is preferable to putting a single reviewer ID on the Pull Request because the domain explicitly permits multiple reviewers.

When the association itself needs business attributes, such as assignment role, assignment timestamp, reviewer priority, or assignment reason, a dedicated association object is generally more expressive than a simple `secondary` table.

## Relationships Versus Columns

A common modeling mistake is to treat `relationship()` as a replacement for a foreign-key column.

They serve different purposes.

A declaration such as:

`author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))`

represents the relational key.

A declaration such as:

`author: Mapped["User"] = relationship(...)`

represents ORM navigation.

The foreign key tells the database how rows are connected. The relationship tells SQLAlchemy how application objects should navigate that connection.

Both are needed for a conventional ORM mapping.

## Cascading Behavior

The example uses:

`cascade="all, delete-orphan"`

for child collections such as Pull Request reviews and commits.

This expresses an ownership-oriented ORM rule. When the parent object is removed through the configured ORM relationship, child objects can be managed as dependent objects.

Cascade behavior requires deliberate modeling. It should not be added automatically to every relationship. A review that belongs exclusively to one Pull Request can reasonably behave like a child object, while an independently meaningful user should not normally be deleted merely because a Pull Request disappears.

Database-level `ON DELETE` behavior and ORM-level cascade behavior are related but not identical mechanisms. Production models should choose them according to transaction ownership and deletion semantics.

## SQLAlchemy 2.x Query Style

The Python implementation uses the SQLAlchemy 2.x pattern:

`statement = select(PullRequest).where(PullRequest.state == "open")`

followed by:

`session.scalars(statement).all()`

This is preferable to treating the ORM as a separate legacy query language.

The query explicitly targets mapped classes and attributes. SQLAlchemy translates the expression into SQL appropriate for the configured database dialect.

Relationship navigation can then operate on the resulting objects:

`pull_request.reviews`

or:

`pull_request.author.username`

The application works with domain objects while SQLAlchemy handles relational persistence.

## Python Implementation

The Python implementation builds an executable model containing:

- `User` for repository participants and reviewers.
- `Repository` for the container of branches and Pull Requests.
- `Branch` for source and target branch identities.
- `PullRequest` for proposed repository changes.
- `Commit` for commits associated with a Pull Request.
- `Review` for reviewer decisions.
- `BranchProtection` for protected-target policy.

The example intentionally includes multiple relationship types rather than demonstrating only simple columns.

The Pull Request model contains two distinct relationships to users. `author` represents the person who created the Pull Request, while `reviewers` represents assigned reviewers. This distinction is important because the same `User` entity participates in different roles within the domain.

The review collection demonstrates child-object navigation. The reviewer relationship demonstrates a many-to-many assignment model.

The example also uses an in-memory SQLite database so that the program can execute without a separate database server. The declarative definitions themselves are not tied to SQLite. The same model style can be used with PostgreSQL by changing the SQLAlchemy database URL and installing the appropriate PostgreSQL driver.

## JavaScript Implementation

The JavaScript file does not attempt to translate SQLAlchemy syntax into JavaScript.

JavaScript does not contain SQLAlchemy's Python ORM machinery, so the implementation instead models the conceptual structure that an ORM must manage.

`Entity` establishes identifier validation. `Repository`, `Branch`, `PullRequest`, `Commit`, `Review`, and `BranchProtection` represent domain entities and their relationships.

The implementation makes relationship ownership explicit through IDs and collections.

For example, a Pull Request stores `authorId`, while its review collection contains review objects referencing reviewer IDs. This makes the distinction between an entity identifier and an object relationship visible without pretending that JavaScript classes are SQLAlchemy mappings.

The `MergePolicy` class then uses those model relationships to evaluate whether the current Pull Request state satisfies the branch-protection requirements.

The JavaScript implementation also demonstrates an important ORM-adjacent concept: object state is not automatically equivalent to database integrity. A real ORM application must still validate references, enforce database constraints, and handle concurrent changes correctly.

## C++ Case Study

The C++ program models a repository-governance engine around a protected `main` branch.

The central `PullRequest` class stores:

- the author identity,
- source branch,
- target branch,
- commits,
- assigned reviewers,
- reviews,
- status checks.

The `RepositoryGovernanceEngine` evaluates those relationships against a `BranchProtectionPolicy`.

This case study provides a different perspective from SQLAlchemy. Instead of concentrating on Python-to-database mapping, it treats the domain model as a strongly typed in-memory system.

The review collection uses `ReviewState`, allowing the model to distinguish `Approved` from `ChangesRequested`. A `set<int>` prevents the same reviewer from being counted multiple times as an independent approval.

The status-check evaluation uses a required-check set. A required check that is missing is treated as a governance failure, rather than being silently considered successful.

The case study therefore demonstrates why the underlying data model matters. A model that stores only a Pull Request title and author cannot accurately evaluate approval policy. The relationships and state objects are necessary because governance decisions depend on them.

## Java Enterprise Model

The Java implementation uses Java 17 features to represent the same domain with explicit domain types.

Records are used for immutable value-like entities such as `User`, `Commit`, `Review`, and `StatusCheck`. Enums model finite workflow states such as `ReviewState` and `PullRequestState`.

`BranchProtectionPolicy` encapsulates policy configuration rather than scattering policy values across conditional statements.

`PullRequest` owns its commits, reviews, status checks, and assigned reviewer identifiers. Methods such as `assignReviewer()`, `addReview()`, and `merge()` validate state transitions at the domain boundary.

`MergeEligibilityService` performs policy evaluation separately from the Pull Request entity. This separation keeps repository governance rules from becoming tightly coupled to the object's storage representation.

The Java model therefore illustrates a useful distinction between persistence-oriented entities and domain services. A SQLAlchemy model may represent database persistence while additional application services enforce more complex business rules.

## SQL Data Model

The SQL script creates a PostgreSQL-compatible schema named `repository_governance`.

The relational model contains:

`users`

Stores repository participants.

`repositories`

Stores repository identities.

`branches`

Associates branches with repositories and prevents duplicate branch names within one repository.

`branch_protection_policies`

Stores protection requirements for protected branches. A unique `branch_id` makes the relationship one-to-one.

`pull_requests`

Stores Pull Request identity, author, source branch, target branch, title, description, and lifecycle state.

`commits`

Stores commits associated with Pull Requests.

`pull_request_reviewers`

Implements the Pull Request-to-reviewer many-to-many relationship.

`reviews`

Stores reviewer decisions such as approval and requested changes.

`review_comments`

Stores inline review discussions and resolution state.

`status_checks`

Stores required automation results.

`merge_events`

Stores successful merge records and the selected merge strategy.

The schema therefore represents the relational structures that the Python ORM classes abstract.

## Database Constraints

The SQL implementation deliberately puts integrity rules into the database.

Primary keys prevent ambiguous row identity.

Foreign keys prevent references to nonexistent parent records.

Unique constraints prevent duplicate usernames, emails, repository names, branch names within a repository, and duplicate status-check names for one Pull Request.

Check constraints restrict enumerated states and validate values such as approval counts and commit SHA formatting.

These constraints matter because application validation alone is not sufficient in a multi-user system. Another transaction, service, script, or administrative operation may access the same database.

The database should enforce rules that are fundamental to data integrity.

## Review Assignment Integrity

The SQL trigger `prevent_author_reviewer_assignment()` prevents the Pull Request author from being assigned as a reviewer.

The `validate_review_reviewer()` trigger checks that a reviewer was actually assigned to the Pull Request before a review can be stored.

These rules demonstrate a database-level distinction between:

- a person existing in the `users` table,
- a person being assigned to a Pull Request,
- a person submitting a review,
- a review being an approval.

A foreign key alone can verify that the user exists. It cannot express every domain rule concerning reviewer eligibility.

## Merge Eligibility View

The `merge_eligibility` view combines Pull Request state, commit presence, reviewer decisions, status checks, and branch protection policy.

The view calculates:

- approval count,
- whether changes were requested,
- commit count,
- passing status-check count,
- incomplete or failed status checks,
- current merge eligibility.

This demonstrates an important relational modeling principle: business decisions can be derived from normalized entities rather than stored redundantly as an uncontrolled Boolean.

If an approval changes, a status check fails, or a Pull Request changes state, the computed eligibility can change without requiring an independently maintained `is_mergeable` column.

## Relationship Cardinality

The complete model contains several different cardinalities.

Repository-to-branch is one-to-many because one repository owns many branches.

Repository-to-Pull Request is one-to-many because one repository can contain many Pull Requests.

Pull Request-to-commit is one-to-many because a Pull Request can contain multiple commits.

Pull Request-to-review is one-to-many because multiple reviewers can submit review records.

User-to-Pull Request reviewer assignment is many-to-many because one reviewer can participate in many Pull Requests and each Pull Request can have several reviewers.

Branch-to-protection policy is one-to-one because the model permits at most one protection policy per branch.

Understanding cardinality before writing `relationship()` declarations prevents many ORM design errors.

## Common Modeling Errors

### Confusing a foreign key with a relationship

A foreign-key column stores relational identity. A `relationship()` attribute provides ORM navigation. Removing one without understanding the other can produce an incomplete mapping.

### Using one reviewer column for multiple reviewers

A single `reviewer_id` on `pull_requests` cannot represent a Pull Request with multiple assigned reviewers. A many-to-many association table is appropriate when reviewer assignment is independently related to both Pull Requests and users.

### Omitting uniqueness from a one-to-one design

A foreign key alone does not guarantee one-to-one cardinality. Multiple rows can point to the same parent unless uniqueness is enforced.

### Storing derived state without a clear ownership model

A database column such as `merge_eligible` can become stale when reviews or status checks change. Derived eligibility is often safer when calculated from authoritative state.

### Treating ORM validation as database integrity

Python validation protects operations that pass through the application. Database constraints protect the database regardless of which client performs the operation.

### Overusing cascade deletion

Cascades should reflect ownership. Deleting a Pull Request should not automatically delete an independent user merely because the user participated in the Pull Request.

## Performance Considerations

Relationships can create large object graphs if they are loaded without considering query behavior.

A repository containing thousands of Pull Requests should not automatically load every Pull Request, every review, every commit, and every reviewer whenever the repository object is retrieved.

Query strategy matters. SQLAlchemy provides lazy loading, eager loading, joined loading, and select-in loading patterns that allow an application to choose how related records are fetched.

Indexes should be created according to actual query patterns. Foreign-key columns frequently used for joins and filters are common index candidates, although the database optimizer and workload should guide the final design.

The SQL implementation indexes Pull Request state, review state, status checks, commits, and review-comment resolution because these fields participate directly in governance queries.

## Transactions and Consistency

The SQL script demonstrates a transaction around merge state and merge-event creation.

A merge operation is not merely an update to a Pull Request state. A consistent implementation may need to change several related records atomically.

If the Pull Request becomes `merged` but the corresponding merge event is not recorded because of a failure, the repository history can become inconsistent.

Transactions allow related changes to succeed or fail together.

The same principle applies when SQLAlchemy's `Session` is used. The session coordinates pending changes and transaction boundaries, while the database ultimately provides the transactional guarantees.

## Production Considerations

A production SQLAlchemy model should be designed around the actual database dialect and migration strategy.

`Base.metadata.create_all()` is useful for a self-contained demonstration and simple environments, but mature applications generally use schema migrations so that changes can be reviewed, versioned, and applied incrementally.

Relationship loading should be selected according to expected access patterns.

Database constraints should remain authoritative for fundamental integrity rules.

Application-level domain services should handle policies that require richer business context.

Concurrency must also be considered. Two reviewers or automation systems can change related records at nearly the same time. Merge eligibility should therefore be evaluated in a transactionally safe workflow rather than treated as a permanently cached property.

The most important design boundary is between the Python object model and the relational model. SQLAlchemy makes the two models work together, but it does not eliminate the need to understand either side.
