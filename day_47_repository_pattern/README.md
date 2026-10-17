# Repository Pattern: Data Access Abstraction and Separation of Concerns

## Scope

The Repository Pattern places a deliberate abstraction between application or domain logic and the mechanism used to retrieve and persist data.

The central concern is not simply creating a class named `Repository`. The important design decision is that business code depends on an operation-oriented persistence contract instead of depending directly on SQL, an ORM, a file format, an HTTP client, or an in-memory collection.

The six artifacts model this separation from different technical perspectives:

| Artifact | Technical focus |
| --- | --- |
| Python | Repository interfaces, interchangeable storage implementations, service-layer validation, SQLite persistence, and testability |
| JavaScript | Promise-based data access, asynchronous repositories, repository substitution, and event-driven application integration |
| C++ | A repository-backed Pull Request governance case study with merge-eligibility rules |
| Java | Enterprise-oriented domain modeling, immutable records, repository contracts, service operations, and explicit persistence errors |
| PostgreSQL | Relational persistence, constraints, indexes, views, transactions, and database-level integrity |
| README | The architectural relationship between abstraction, persistence, domain behavior, and implementation trade-offs |

The examples deliberately use different domains where that creates a useful technical distinction rather than translating one implementation into five programming languages.

## Core Concept

A tightly coupled application might perform a database operation directly inside a business operation:

`registerCustomer()` → SQL statement → database

That structure makes the business operation responsible for both policy and persistence details.

The Repository Pattern introduces a boundary:

`application service` → `repository contract` → `repository implementation` → `data source`

The service determines what the application needs, such as finding a customer by identifier or saving a customer. The concrete repository determines how that request is fulfilled.

This produces separation of concerns:

- The domain or application service owns business rules.
- The repository contract defines the data-access capability required by the service.
- The concrete repository owns persistence mechanics.
- The database owns data integrity rules that belong naturally at the persistence boundary.
- Infrastructure-specific details remain outside business operations when the abstraction is designed correctly.

The pattern does not mean that every database query should be hidden behind a generic `getData()` method. A useful repository exposes operations meaningful to its domain.

## Repository Contract

The Python implementation defines `UserRepository` with operations such as `get_by_id()`, `get_by_email()`, `list_active()`, `save()`, and `delete()`.

Those operations describe what the service requires without specifying whether data comes from SQLite or memory.

The Java implementation expresses the same architectural idea through `CustomerRepository`. Its methods return domain-oriented objects and `Optional` values for operations where absence is expected.

The C++ implementation uses an abstract `PullRequestRepository`. Its contract is deliberately specific to the case study: retrieving a Pull Request, saving one, and finding open Pull Requests for a target branch.

The contract is therefore part of the architectural boundary. It should represent meaningful persistence capabilities rather than expose the internal structure of the database.

## Separation of Concerns

The Python `UserService` validates names and email addresses, checks whether an account already exists, and manages activation state. It does not issue SQL statements.

`SQLiteUserRepository` owns SQLite connection handling, row conversion, SQL statements, commits, and schema initialization.

`InMemoryUserRepository` implements the same repository contract without a database. This makes the service usable in fast tests without changing the business logic.

The separation is significant because the service can be evaluated independently of the persistence mechanism.

A change from SQLite to PostgreSQL should primarily require a change in infrastructure rather than a rewrite of the user-registration rules.

## Python Implementation

The Python program uses a `Protocol` to express the repository contract. This gives structural typing: an implementation is suitable when it provides the required operations.

`InMemoryUserRepository` stores users in a dictionary. Its purpose is not to imitate a relational database perfectly. It provides a lightweight repository implementation that is useful for local execution and testing.

`SQLiteUserRepository` demonstrates persistence using the standard-library `sqlite3` module. SQL parameters are supplied separately from SQL text, which avoids constructing queries through unsafe string interpolation.

`UserService` is deliberately unaware of SQLite. It receives a `UserRepository` during construction.

The script also demonstrates repository substitution. The same service is first used with an in-memory repository and then with SQLite.

This is a practical form of dependency inversion:

`UserService → UserRepository`

rather than:

`UserService → SQLiteUserRepository`

The difference matters when persistence requirements change.

The Python implementation also demonstrates validation failures, duplicate-email handling, missing-user handling, state changes, JSON reporting, and a test that does not require a database.

## JavaScript Implementation

The JavaScript artifact focuses on asynchronous data access.

`MemoryUserRepository` provides a local implementation, while `RemoteUserRepository` models an asynchronous remote persistence boundary. The simulated network delay is intentional because JavaScript applications frequently interact with persistence through asynchronous APIs.

Both implementations expose the same conceptual operations:

`findById()`, `findByEmail()`, `save()`, `listActive()`, and `delete()`.

`UserService` therefore does not need to know whether persistence is local or remote.

Promises are important in this representation. A repository method returning a Promise prevents the application layer from making an incorrect assumption that persistence is immediate.

The example also introduces `AuditEventBus`. The repository is responsible for persistence, while event publication is kept separate from the repository itself. This distinction prevents a repository from becoming an oversized infrastructure object responsible for persistence, auditing, messaging, notification, and business policy simultaneously.

## C++ Case Study: Pull Request Governance

The C++ implementation uses repository abstraction in a repository-development domain rather than a customer-management domain.

The system represents Pull Requests that target protected branches.

A Pull Request contains its identifier, title, author, source branch, target branch, lifecycle state, and number of changed files.

The `PullRequestRepository` abstract class separates Pull Request governance from persistence.

`MemoryPullRequestRepository` is the concrete implementation used by the executable. A production system could replace it with a database-backed implementation while retaining the merge-policy engine.

The `MergeEligibilityEngine` is intentionally separate from persistence. It evaluates whether a Pull Request can be merged based on:

- Pull Request lifecycle state
- required independent approvals
- requested changes
- passing continuous-integration checks
- merge conflicts
- the branch's governance policy

The policy requires two approvals, passing checks, and protected-branch controls.

The example specifically rejects self-approval. It also distinguishes a failing CI condition from a missing approval condition.

This demonstrates an important repository-design principle: storing data and deciding what the data means are different responsibilities.

The repository answers questions such as "what is Pull Request 101?"

The merge-eligibility engine answers the policy question "can Pull Request 101 be merged under this branch policy?"

## Java Enterprise Model

The Java program models customers using an immutable `record`.

`Customer` contains identity, name, email, and account status. State-changing operations such as `activate()` and `suspend()` return new `Customer` values instead of mutating the existing record.

`CustomerRepository` defines persistence operations with domain-specific names.

`InMemoryCustomerRepository` provides the concrete implementation. It also normalizes email addresses and detects duplicate business keys.

`CustomerService` represents an application service. It coordinates repository calls and applies state-transition rules.

The service rejects attempts to suspend a deleted customer and rejects attempts to reactivate a deleted customer. These are domain rules rather than persistence operations.

`RepositoryException` carries a typed error category. The application can therefore distinguish a duplicate-record conflict from a missing record without parsing error-message strings.

`CustomerReport` demonstrates a read-oriented use of the repository. The report requests active customers through the repository instead of reading the internal map directly.

## SQL Data Model

The PostgreSQL script demonstrates the persistence side of the pattern using database-native mechanisms.

The `customers` table contains:

- a generated primary key
- customer name
- normalized-business-key-compatible email storage
- account status
- creation timestamp
- update timestamp

The `status` column has a `CHECK` constraint restricting values to `ACTIVE`, `SUSPENDED`, and `DELETED`.

The name and email fields also have database-level validation constraints.

A unique index on `lower(email)` enforces case-insensitive uniqueness. This is important because application-level duplicate checks alone are subject to race conditions when concurrent transactions perform the same check.

The `customer_audit` table records status changes through a trigger.

The `active_customer_repository` view represents a reusable read boundary for active customers.

The transaction around the suspension operation demonstrates atomic state modification. The audit trigger runs as part of the same database transaction, so the state change and its corresponding audit record are committed together.

The script also includes `EXPLAIN` for the case-insensitive email lookup, connecting repository query design with database performance.

## Repository Versus Data Access Utility

A repository is more useful than a generic database utility when its operations correspond to a domain's persistence needs.

A low-level utility might expose:

`execute(sql, parameters)`

A repository can instead expose:

`findByEmail(email)`

The first leaks database mechanics into callers. The second expresses an application-relevant persistence operation.

This does not mean repositories should hide every query detail. Complex applications may need specialized query repositories, read models, specifications, or query services. The abstraction should remain honest about the data-access capability it provides.

## Repository Versus Service

The repository should not become the business service.

For example, checking whether an email already exists is a persistence query. Deciding that a registration should be rejected because the email already belongs to an account is an application or domain rule.

Likewise, retrieving a Pull Request is repository work. Determining whether the Pull Request satisfies the branch's merge policy is governance logic.

The boundary can be summarized as:

`Repository: retrieve and persist domain data`

`Service/domain logic: decide what operations are valid`

This distinction reduces the risk of repositories becoming procedural collections of unrelated business rules.

## Dependency Direction

A well-designed dependency relationship points inward toward stable abstractions.

The Python implementation makes this explicit:

`UserService → UserRepository`

`SQLiteUserRepository → SQLite`

The service does not need to know that SQLite exists.

The same principle appears in C++:

`PullRequestService → PullRequestRepository`

`MemoryPullRequestRepository → in-memory storage`

The concrete persistence mechanism is therefore replaceable at the boundary.

## Edge Cases

A repository design must define how absence is represented.

The Python examples use `None` for a missing entity.

The Java implementation uses `Optional<Customer>`.

The C++ implementation uses `std::optional<PullRequest>`.

These choices make absence explicit instead of returning an arbitrary empty object that could be confused with a real entity.

Duplicate business keys are another important edge case. Email is treated as a business key in the Python, JavaScript, Java, and PostgreSQL examples.

The PostgreSQL unique index is particularly important because application-level validation cannot by itself guarantee uniqueness under concurrent access.

State transitions are also validated. A deleted Java customer cannot be suspended or reactivated. The C++ Pull Request cannot be merged when it is still a draft, already merged, closed, blocked by requested changes, missing approvals, failing CI, or affected by a merge conflict.

## Transactions and Consistency

Repositories often participate in transactions, but the transaction boundary should normally correspond to an application operation rather than arbitrary individual repository calls.

The PostgreSQL example updates customer state inside a transaction. The audit trigger records the corresponding status change within that transaction.

If a larger business operation modifies multiple entities, the application may require a unit-of-work or transaction abstraction so that several repository operations share the same transactional boundary.

A repository that commits every individual method call can make larger atomic operations difficult to implement. Transaction ownership therefore needs to be an explicit architectural decision.

## Performance Considerations

Repository abstraction does not automatically make data access efficient.

A method such as `findByEmail()` should have an appropriate database index when the query is frequent.

The PostgreSQL implementation creates an index on `lower(email)` because the repository query also normalizes email with `lower()`.

Methods returning collections should avoid accidentally loading an unbounded data set. Large production repositories may require pagination, filtering, projections, streaming, or dedicated query models.

The C++ Pull Request repository returns only requests for a specified target branch. That is more precise than loading every Pull Request and filtering them elsewhere.

The repository contract can therefore influence performance by determining which query capabilities are available to the service.

## Testing Implications

Repository abstraction allows different kinds of tests.

A unit test can provide an in-memory implementation and exercise business rules without requiring a database.

Integration tests can execute the real repository against the actual database technology.

The distinction is valuable because an in-memory implementation does not perfectly reproduce database behavior. Unique constraints, transaction isolation, query plans, locking, and database-specific data types can only be validated reliably with the real persistence technology.

A strong test strategy therefore uses repository substitution for fast business-rule tests while retaining integration coverage for the concrete persistence implementation.

## Common Design Failures

A repository becomes problematic when it exposes infrastructure details everywhere. Returning raw database rows from every repository method forces application code to understand persistence structures.

Another failure occurs when one repository becomes a general-purpose object containing unrelated operations for every domain. A repository should normally have a coherent aggregate or domain responsibility.

The opposite problem is excessive abstraction. If a simple application gains multiple interfaces, adapters, factories, generic repositories, and mapping layers without a real change requirement, the abstraction can add complexity without providing useful separation.

A repository should exist because the boundary provides architectural value, not because every table must mechanically receive a repository class.

## Security Considerations

Repository boundaries are useful locations for consistent data-access controls, but they should not be treated as the only security layer.

Parameterized SQL is required when values enter SQL statements. The Python example passes values as SQLite parameters rather than constructing SQL with string concatenation.

Database constraints protect data integrity even when application code contains a defect.

Authorization is different from persistence. A repository can retrieve a record correctly while the caller is still unauthorized to perform an operation on that record. Authorization policy should therefore remain explicit in the application or domain architecture rather than being accidentally hidden inside generic data-access code.

Audit records can provide important accountability for sensitive state changes. The PostgreSQL trigger demonstrates this for customer status transitions.

## Practical Architecture

A maintainable application can organize the boundary conceptually as:

`Domain model`

`Application service`

`Repository interface`

`Repository implementation`

`Database or external data source`

The interface belongs close to the application or domain boundary when dependency inversion is the goal. The concrete implementation belongs to infrastructure.

The exact directory structure can vary, but the dependency direction should remain understandable.

For the examples in this repository:

`UserService` does not depend on `SQLiteUserRepository`.

`PullRequestService` does not depend on `MemoryPullRequestRepository`.

`CustomerService` does not depend on `InMemoryCustomerRepository`.

The concrete implementation is supplied from the composition point.

## Pull Request, Code Review, Approvals, and Branch Protection Relationship

The repository-development concepts represented in the broader technical case study have distinct responsibilities.

A Pull Request is the change-proposal workflow. It identifies a source branch, a target branch, a changeset, review activity, checks, and a possible merge.

Code Review evaluates the proposed changes. Reviewers inspect the changeset, leave inline or general comments, identify defects or risks, and may request changes.

An approval is a specific review decision. It is not synonymous with the entire review process. Repository policy can require one or more eligible approvals before merging.

Branch Protection is repository-level governance. It can require reviews, require status checks, restrict direct pushes, restrict force pushes, prevent branch deletion, or impose other merge conditions depending on the platform and configuration.

The relationship is therefore:

`Pull Request → proposed change`

`Code Review → technical evaluation`

`Approval → review decision`

`Branch Protection → repository governance enforcing merge conditions`

The C++ case study models this relationship through a repository abstraction for Pull Requests and a separate merge-eligibility engine. Persistence stores the state, while policy determines whether the state satisfies protected-branch requirements.

## Architectural Trade-Off

The primary benefit of the Repository Pattern is controlled dependency direction.

Business logic can remain independent from a particular storage technology, and testing can become easier because repositories can be replaced by deterministic implementations.

The cost is abstraction overhead. Every interface introduces another contract that must be designed, understood, tested, and maintained.

The pattern is strongest when persistence is complex, multiple storage implementations are plausible, domain logic needs to remain independent of infrastructure, or isolated business-rule testing has significant value.

It is less compelling when a small application has simple persistence and no meaningful separation is required.

The important design decision is therefore not "use repositories everywhere." It is to identify where data-access concerns and domain concerns should remain separate, then create an abstraction whose operations accurately represent that boundary.
