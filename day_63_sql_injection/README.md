# SQL Injection: Parameterized Queries and ORM Protection

## Scope

This implementation set models SQL injection as a database-boundary security problem. The central distinction is between SQL syntax and application data.

A vulnerable application constructs SQL by combining trusted query text with untrusted input:

`SELECT ... WHERE username = '` + user_input + `'`

A protected application keeps the SQL structure fixed and transmits the input as a bound parameter:

`SELECT ... WHERE username = ?`

The five implementations approach the same security boundary from different engineering perspectives.

## Security Model

SQL injection occurs when data supplied by an application can alter the SQL statement interpreted by the database.

The relevant trust boundary is:

`Untrusted Input → Validation → Data-Access Layer → Parameter Binding → Database`

Validation is useful but is not the primary SQL injection defense. A username may be syntactically valid for the application and still contain characters that would be dangerous if inserted into SQL text. Parameterization prevents those characters from becoming SQL syntax.

The implementation separates four mechanisms:

| Mechanism | Purpose |
|---|---|
| Input validation | Enforces application-level domain rules |
| Parameterized queries | Separates SQL structure from values |
| ORM/repository abstraction | Centralizes and standardizes database access |
| Database privileges | Limits damage if an application-level control fails |

## Injection Mechanism

The Python implementation contains an intentionally unsafe function that constructs a SQL statement through string interpolation. It is paired with a parameterized implementation so the difference is executable rather than merely descriptive.

The unsafe path allows input to become part of the SQL statement. The safe path sends SQL text and values separately.

The JavaScript implementation models the same distinction with `ParameterizedQuery`. Its `text` field contains fixed SQL and its `values` field contains user-controlled data. This represents the interface expected from a real parameterized database driver without requiring an external npm package.

The C++ and Java implementations focus on governance and repository boundaries. They treat secure database access as part of a larger engineering workflow where database changes must pass review, security checks, and branch policies.

## Parameterized Queries

Parameterization changes the interpretation boundary.

For a safe lookup, the SQL statement contains a placeholder:

`WHERE username = $1`

The username is supplied separately:

`["alice"]`

An input such as `' OR '1'='1` therefore remains a string value. It is not parsed as an additional SQL predicate.

The PostgreSQL implementation uses both `PREPARE` and `EXECUTE` to demonstrate this separation directly. The prepared statement has a fixed query structure and accepts a text parameter.

The Python implementation uses SQLite's parameter binding with `?` placeholders. The JavaScript model uses `$1` placeholders. These differences reflect the conventions of different database interfaces while preserving the same security property.

## ORM Protection

An ORM does not automatically make every application safe. Protection depends on how the ORM constructs database queries.

Safe ORM behavior generally means:

- values are represented as parameters
- query structure is controlled by the application or ORM
- generated SQL uses bound variables
- raw SQL interfaces are used carefully
- dynamic identifiers are validated separately from dynamic values
- database permissions remain restricted

The Python `UserRepository`, JavaScript `UserQuery`, and Java repository model place database access behind repository methods.

The important architectural boundary is:

`Application Service → Repository / ORM → Parameterized Database Operation`

A repository reduces the number of locations where SQL can be constructed and makes unsafe string concatenation easier to detect during review.

## Python Implementation

The Python program uses `sqlite3`, which is part of the standard library.

It contains:

- `dataclass` domain modeling
- enumerated query modes
- input validation
- custom exceptions
- password hashing for the demonstration domain
- unsafe SQL construction for contrast
- parameterized SQL
- a repository abstraction
- service-layer authentication
- constant-time password-hash comparison
- query-plan inspection
- assertions through executable validation paths
- explicit database cleanup

The unsafe function is intentionally isolated. It demonstrates why interpolating user-controlled data into SQL is dangerous without making unsafe construction the application's normal path.

The repository uses parameter binding and keeps the SQL statement independent from the username.

The example also demonstrates that parameterization does not prevent ordinary indexing. The username column receives an index after the protected query has been established.

## JavaScript Implementation

The JavaScript program uses Node.js standard-library modules only.

Its main design is event-driven:

`User Input → Query Builder → Repository → Database Adapter → Audit Event`

`ParameterizedQuery` is immutable. The SQL text and values are held separately.

`UserQuery.byUsername()` and `UserQuery.byCredentials()` provide ORM-style query construction. The `InMemoryDatabase` models the database adapter and rejects execution of objects that are not parameterized query objects.

`SecurityAudit` uses `EventEmitter` to represent asynchronous security-event processing. Audit records contain usernames and event categories but deliberately exclude passwords.

The example also demonstrates that an injection-like username is treated as an ordinary lookup value and does not alter the query structure.

## C++17 Governance Engine

The C++ implementation treats SQL injection protection as part of repository governance.

The domain contains:

- pull requests
- commits
- reviews
- reviewer eligibility
- status checks
- protected branches
- approval requirements
- merge conflicts
- source-branch synchronization
- unresolved conversations
- merge eligibility

The `MergeEligibilityEngine` evaluates all required conditions before a protected branch can accept a change.

Eligible approvals are deduplicated with an ordered `set`, so the same reviewer cannot satisfy the approval requirement multiple times.

The engine distinguishes:

- an approved review
- an eligible reviewer
- a passing automated check
- a resolved conversation
- a synchronized source branch
- a final merge decision

This is important for database-security changes because a parameterized query can still be incorrectly implemented, incompletely reviewed, or later replaced with unsafe raw SQL.

## Java 17 Enterprise Model

The Java implementation represents an enterprise-oriented service boundary.

Java records provide immutable domain values for users, reviews, checks, policies, pull requests, and eligibility decisions.

The repository abstraction separates authentication from application services. The `ParameterizedQuery` record models the key ORM/JDBC boundary:

`SQL Text + Bound Parameters`

The `MergeEligibilityService` evaluates protected-branch requirements using collections and streams. Eligible reviewer identities are deduplicated with a `HashSet`.

The policy model explicitly represents:

- required approvals
- required pull requests
- resolved review conversations
- passing status checks
- direct-push restrictions
- force-push restrictions
- branch deletion restrictions

The Java program also models failure states instead of treating every request as successful. Invalid credentials and blocked merges are represented by explicit exceptions and eligibility blockers.

## PostgreSQL Relational Model

The PostgreSQL implementation provides the most complete persistent representation.

The main relationships are:

`Repository`
→ `Branches`
→ `Pull Requests`
→ `Commits`

`Pull Request`
→ `Reviews`
→ `Review Comments`

`Pull Request`
→ `Status Checks`

`Protected Branch`
→ `Branch Protection Policy`

`Pull Request + Policy + Reviews + Checks`
→ `Merge Eligibility`

`Eligible Pull Request`
→ `Merge Record`

The database contains primary keys, foreign keys, uniqueness rules, check constraints, partial indexes, views, SQL functions, a trigger, prepared statements, transactional merge recording, and audit records.

The trigger prevents a pull request from associating branches belonging to different repositories.

The `merge_eligibility()` function evaluates branch policy, pull-request state, approvals, synchronization, unresolved discussions, and required status checks.

The `record_merge()` function performs eligibility validation, records the merge, changes pull-request state, and creates an audit event.

These operations occur within a transaction when invoked by the demonstrated `BEGIN` and `COMMIT` block.

## Input Validation Versus SQL Injection Defense

These controls have different responsibilities.

| Control | Protects against |
|---|---|
| Username length validation | Invalid application input |
| Empty-value rejection | Invalid application state |
| Parameter binding | Data being interpreted as SQL syntax |
| ORM/repository boundary | Unsafe database-access patterns |
| Least-privilege database account | Excessive database impact |
| Generic authentication errors | Information leakage |
| Security review | Unsafe implementation changes |
| Automated SQL-injection tests | Regression of database-boundary controls |

A validation rule such as "username must be at most 80 characters" does not replace parameterization.

Likewise, escaping quotes manually is weaker than using the database driver's parameter-binding mechanism because SQL syntax can contain many context-sensitive constructs.

## Review and Governance Workflow

A security-sensitive database change follows a controlled path:

`Feature Branch`
→ `Pull Request`
→ `Code Review`
→ `Security Review`
→ `Automated Checks`
→ `Approval Requirements`
→ `Protected Branch`
→ `Merge`

The four concepts have distinct roles:

| Concept | Function |
|---|---|
| Pull Request | Proposes a change from a source branch to a target branch |
| Code Review | Evaluates the implementation and discusses defects |
| Approvals | Records explicit reviewer decisions |
| Branch Protection | Enforces repository-level conditions before merge |

An approval is not equivalent to branch protection. An approval is one review decision. Branch protection determines whether the repository permits the resulting change to be merged.

## Failure Conditions

The implementations explicitly account for several failure states:

- empty usernames
- excessively long usernames
- invalid credentials
- injection-like input
- missing reviewers
- ineligible reviewers
- duplicate reviewers
- insufficient approvals
- unresolved conversations
- failed required status checks
- pending required status checks
- merge conflicts
- stale source branches
- closed pull requests
- missing commits
- invalid branch relationships
- unauthorized merge conditions

The PostgreSQL model also prevents invalid cross-repository branch relationships through a database trigger rather than relying solely on application code.

## Performance Considerations

Parameterized queries do not inherently require inefficient access paths.

The Python implementation creates an index on `username` and inspects the resulting query plan.

The PostgreSQL model indexes:

- pull-request target branch and state
- review state by pull request
- unresolved review comments
- required status checks

The partial indexes are deliberately limited to frequently evaluated subsets such as unresolved comments and required checks.

The C++ engine uses an ordered set to deduplicate eligible reviewers. The Java implementation uses a hash set for the same logical operation.

The PostgreSQL eligibility function performs aggregation close to the data, reducing the amount of raw workflow data that an application must retrieve before evaluating merge conditions.

## Security Considerations

The implementations enforce the following principles:

- Never concatenate untrusted values into SQL statements.
- Prefer native parameter-binding APIs.
- Keep database access behind a repository or ORM boundary.
- Validate input according to application rules.
- Do not rely on validation as the SQL injection defense.
- Do not expose raw SQL errors to clients.
- Do not log passwords or password-equivalent secrets.
- Use least-privilege database accounts.
- Review changes that modify database access code.
- Require automated security checks for protected branches.
- Treat raw-SQL escape hatches as security-sensitive.
- Keep database state transitions transactional.

Dynamic SQL identifiers require special treatment. A parameter placeholder normally represents a value, not a table name, column name, or SQL keyword. If an application must select an identifier dynamically, it should select from an allowlist of known identifiers rather than attempting to parameterize the identifier as a normal value.

## Important Distinctions

SQL injection and authentication failure are different problems.

A request with an invalid password should fail authentication. It should not be able to change the SQL query used to perform authentication.

Parameterization protects query interpretation. Password hashing protects stored credentials. Branch protection controls how security-sensitive code reaches a repository. These mechanisms operate at different layers and should not be substituted for one another.

Similarly, an ORM is an abstraction layer, not a security guarantee. An ORM that generates parameterized queries provides a strong default, while raw SQL interfaces, dynamic fragments, unsafe query builders, and incorrectly constructed native queries can reintroduce the vulnerability.

## Executable File Roles

| File | Primary role |
|---|---|
| Python | End-to-end executable demonstration using SQLite, validation, repository access, and parameter binding |
| JavaScript | Event-driven ORM-style query model with parameter separation and audit events |
| C++17 | Repository governance and merge-eligibility engine |
| Java 17 | Enterprise domain model with repositories, immutable records, policy services, and state validation |
| PostgreSQL | Persistent relational model with constraints, indexes, views, functions, triggers, prepared statements, transactions, and audit records |
| README.md | Technical description of the implemented security mechanisms and their relationships |

## Operational Boundary

The safest architecture keeps the database boundary narrow:

`HTTP/API Input`
→ `Application Validation`
→ `Service`
→ `Repository / ORM`
→ `Parameterized Query`
→ `Least-Privilege Database Role`
→ `Database`

Security-sensitive changes should pass through:

`Feature Branch`
→ `Pull Request`
→ `Review`
→ `Required Checks`
→ `Required Approvals`
→ `Protected Branch`
→ `Merge`

This separates data validation, SQL parameterization, application architecture, and repository governance while allowing them to reinforce one another.
