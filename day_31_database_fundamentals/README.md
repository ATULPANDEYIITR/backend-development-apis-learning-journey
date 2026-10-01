# Database Fundamentals

## Scope

This repository presents database fundamentals through a concrete project-management data model. The central model contains projects, tasks, team members, and project memberships. It is designed to make the relationships between database concepts visible in executable code rather than treating tables and keys as isolated definitions.

The three implementations approach the same subject from different technical perspectives:

- The Python program uses SQLite through the standard-library `sqlite3` module, allowing actual relational tables, constraints, foreign keys, joins, indexes, transactions, metadata inspection, and integrity checks.
- The JavaScript program builds an in-memory relational model with `Map` and `Set`, emphasizing application-side representation, validation, event-driven changes, relationship indexes, and transaction-style snapshots.
- The C++ program models a repository-management data layer with typed structures and standard-library containers. It focuses on explicit relational integrity, indexed lookup, join behavior, composite keys, aggregation, and atomic rollback.

The subject is deliberately centered on database concepts: tables, rows, columns, primary keys, foreign keys, and relationships.

## Relational Database Model

A relational database organizes information into tables. A table represents an entity or a relationship, while each row represents one occurrence of that entity or relationship.

For the project-management scenario, the primary entity tables are:

| Table | Meaning | Primary key |
|---|---|---|
| `projects` | A software or business project | `project_id` |
| `tasks` | Work associated with a project | `task_id` |
| `team_members` / `members` | People participating in projects | `member_id` |

The associative table `project_members` represents the relationship between projects and members. Its identity is formed by the combination of `project_id` and `member_id`.

This separation matters because a database should preserve distinct facts in appropriate structures. A task needs to identify its project, but it does not need to repeat the project's name and owner in every task row.

## Tables, Rows, and Columns

A table has a defined set of columns. Each column describes one attribute of the records stored in that table.

The Python `projects` table contains:

- `project_id`: numeric row identifier and primary key
- `name`: project name
- `owner`: project owner

The Python `tasks` table contains:

- `task_id`: task primary key
- `project_id`: reference to the parent project
- `title`: task description
- `status`: controlled task state
- `due_date`: optional date value

A row is one complete record. For example, a task row connects a task identifier, its project identifier, its title, its status, and its due date.

Columns also carry rules. The Python implementation uses `NOT NULL`, `UNIQUE`, and `CHECK` constraints. These constraints turn assumptions about valid data into database-enforced rules.

## Primary Keys

A primary key provides the identity of a row within a table.

The Python schema declares `project_id INTEGER PRIMARY KEY` and `task_id INTEGER PRIMARY KEY`. The C++ implementation models the same identity with the `id` field in `Project` and `Task`.

A primary key is important for more than simply generating an integer. Other records can reliably refer to a specific row through that identity.

The Python implementation explicitly attempts to insert another project with `project_id = 1`. SQLite rejects the operation because the primary-key value already belongs to an existing row.

Primary keys should be stable enough to serve as references. Application code should not normally use mutable descriptive values such as a project name as the identity of a related record.

## Foreign Keys and Referential Integrity

A foreign key connects a row in one table to a row in another table.

The central relationship is:

`tasks.project_id -> projects.project_id`

The `projects` table is the parent side, while `tasks` is the child side.

The Python schema declares the relationship explicitly with a foreign-key constraint and enables SQLite foreign-key enforcement for the connection. An attempted task referencing project `999` therefore fails because that project does not exist.

The C++ program performs an equivalent check before inserting a task. This is application-level enforcement rather than enforcement by a database engine, but the purpose is the same: prevent an orphan task.

A production relational database should normally enforce critical referential rules at the database layer. Application validation is still valuable because it can provide clearer error messages and reject bad input before a database request is attempted.

## One-to-Many Relationships

A one-to-many relationship means one parent row can be related to multiple child rows.

The project-management model contains this relationship:

`projects -> tasks`

One project can contain many tasks, while each task belongs to one project.

The relationship is represented by storing the parent primary key in the child table:

`tasks.project_id`

For example, several task rows can contain the same `project_id` while retaining different `task_id` values.

This structure avoids duplicating the project name and owner in every task. A query can recover the combined information through a join.

The Python `demonstrate_one_to_many()` function performs a SQL `LEFT JOIN`. The C++ `printOneToManyJoin()` method performs the equivalent relationship traversal manually.

## Many-to-Many Relationships

A many-to-many relationship occurs when multiple rows on both sides can be related to multiple rows on the other side.

Projects and team members provide the case study:

- A project can contain multiple members.
- A member can participate in multiple projects.

A single `member_id` column in `projects` cannot represent this relationship correctly because one project can have several members. A list of IDs stored in one ordinary column would also weaken relational constraints and make querying more complicated.

The solution is an associative table:

`project_members`

Its important columns are:

`project_id`, `member_id`, and `role`

The pair `(project_id, member_id)` forms a composite primary key. This prevents the same member from being assigned to the same project twice.

The role belongs to the relationship rather than necessarily to the member or project itself. The same member can therefore have different roles on different projects.

The Python implementation creates `team_members` and `project_members` in SQLite. The JavaScript implementation uses `projectMembers` as a `Map` keyed by the composite value. The C++ implementation uses `ProjectMember` rows and explicitly checks the composite key.

## Joins

A join combines rows from related tables based on a relationship condition.

A conceptual inner join between projects and tasks uses:

`projects.project_id = tasks.project_id`

An inner join returns only projects having matching tasks.

A left join starts with all project rows and retains a project even when no task matches it. The Python program demonstrates this distinction with both inner-join and left-join queries.

The C++ case study models left-join behavior by printing `(no tasks)` for a project without child records. This is especially useful for the `Empty Project` created near the end of the case study.

Joins are not simply a presentation feature. They allow normalized data to remain separated while still supporting application reports that need information from several related tables.

## Constraints and Data Validity

The Python implementation demonstrates three different forms of database constraint.

`NOT NULL` prevents a required column from being stored without a value.

`UNIQUE` prevents duplicate values where uniqueness is part of the data model. Project names and member names use this rule in the examples.

`CHECK` restricts values to an allowed condition. Task status is limited to `todo`, `in_progress`, and `done`.

The JavaScript and C++ implementations reproduce these rules explicitly because their in-memory models do not have a database engine enforcing them automatically.

This distinction is important: a JavaScript or C++ validation function is not equivalent to a database constraint when multiple clients or processes can modify the same persistent database. Database-level constraints provide a stronger integrity boundary.

## Updating Related Data

Updating a row does not normally change its primary-key identity.

The Python program changes a task's status through an `UPDATE` statement while retaining the same `task_id`.

The C++ program provides `updateTaskStatus()`, which validates the replacement status before modifying the existing task.

The JavaScript program emits a `task.updated` event containing both the previous and new status. This introduces an application-level concern that becomes important in larger systems: data changes may trigger secondary operations such as cache updates, audit records, notifications, or search-index synchronization.

## Delete Rules

Deleting a parent row can affect related child rows.

The Python schema uses:

`ON DELETE RESTRICT`

for the project-to-task relationship. Attempting to delete a project that still has tasks is therefore rejected.

This prevents dangling references.

Other database designs can deliberately choose different behaviors. For example, cascading deletion can be appropriate when child records have no independent meaning outside the parent. The correct behavior depends on the data lifecycle and business rules.

The C++ case study models restrictive deletion explicitly through `removeProject()`. It refuses to delete a project when a task still references it.

## Transactions

A transaction groups multiple database operations into an atomic unit.

The Python program demonstrates a transaction that first inserts a temporary project and then deliberately attempts to insert a task referencing a nonexistent project. The foreign-key failure causes the transaction to roll back, so the temporary project does not remain.

The JavaScript implementation provides a transaction-style snapshot mechanism using `structuredClone()`. If an operation throws an exception, the previous `Map` and `Set` state is restored.

The C++ implementation takes snapshots of its vectors, indexes, and ID counters. A failed operation restores the complete previous state.

The C++ and JavaScript approaches are educational models of atomicity. They do not replace a real database transaction system. A production database engine must coordinate transactions with concurrency, durability, locking or multi-version mechanisms, crash recovery, and persistent storage.

## Indexes

An index provides a data structure optimized for particular lookup patterns.

The Python program creates:

`idx_tasks_project_status ON tasks(project_id, status)`

It then uses `EXPLAIN QUERY PLAN` to show how SQLite can use the index for a query filtering by both project and status.

The JavaScript implementation maintains `tasksByProject`, mapping each project ID to a set of task IDs.

The C++ implementation maintains `taskIdsByProject_` using an `unordered_map<int, unordered_set<int>>`.

These examples demonstrate the same design principle from different perspectives: if the application repeatedly asks for all tasks belonging to a particular project, an index can avoid scanning every task.

Indexes are not free. They consume storage and require maintenance when rows are inserted, updated, or deleted. Adding indexes without considering actual query patterns can increase write cost without providing useful performance benefits.

## Aggregation

A relational system can summarize related rows rather than returning every individual record.

The Python program groups tasks by project and calculates:

- total tasks
- completed tasks
- completion percentage

The C++ case study performs the same type of aggregation with explicit loops and conditional counts.

The calculation is derived from the task rows rather than being stored redundantly on the project row. This reduces the risk of storing a project-level completion value that becomes inconsistent with its tasks.

In a production database, the equivalent SQL operation would commonly use `GROUP BY`, aggregate functions such as `COUNT`, and conditional expressions.

## Python Implementation

The Python implementation uses a real SQLite database connection and therefore demonstrates the relational model directly through SQL.

Its schema establishes a parent-child relationship between `projects` and `tasks`, then adds a many-to-many model through `team_members` and `project_members`.

The program also demonstrates several database-engine behaviors:

- `PRAGMA foreign_keys = ON` activates foreign-key enforcement for the SQLite connection.
- `PRAGMA table_info(...)` exposes table-column metadata.
- Primary-key duplication produces an `IntegrityError`.
- An invalid foreign key produces an `IntegrityError`.
- `CHECK`, `NOT NULL`, and `UNIQUE` constraints reject invalid rows.
- `JOIN` and `LEFT JOIN` recover related information without duplicating stored data.
- `CREATE INDEX` creates a composite lookup index.
- `EXPLAIN QUERY PLAN` exposes SQLite's query-planning decision.
- `PRAGMA integrity_check` validates database structural integrity.
- Parameterized SQL keeps supplied search text separate from SQL syntax.
- CSV output demonstrates how normalized relational data can be transformed into an external report.

The program uses `sqlite3.Row` so returned rows can be accessed by column name. It also maps selected database rows into Python `dataclass` objects, showing the boundary between relational records and application-domain objects.

The database is created in memory for the primary demonstration, while the export operation creates a CSV report in the current directory. The program therefore does not require an external database server or third-party package.

## JavaScript Implementation

The JavaScript implementation intentionally does not simply translate the Python SQL statements.

It models relational structures using JavaScript-native collections:

- `Map` stores rows by primary-key value.
- `Set` stores collections of related identifiers.
- `tasksByProject` acts as a relationship index.
- `projectMembers` uses a composite string key to represent a many-to-many association.
- Validation functions enforce data-model rules before insertion.
- `structuredClone()` provides an isolated state snapshot for transaction-style rollback.
- The event registry demonstrates how application code can react to changes without embedding every side effect inside the data operation.

The `projectTaskJoin()` function performs a relationship traversal corresponding to a left-join-like result. `membersForProject()` resolves the two foreign keys in the associative table to produce a many-to-many result.

`safeUserSearch()` illustrates the separation between data and query structure. The function does not concatenate user input into executable SQL. In a real SQL application, the corresponding principle is parameterized queries or prepared statements.

The JavaScript model is deliberately in memory. It teaches the data structures and application behavior without requiring a database package or server. It should not be interpreted as a replacement for a persistent relational database.

## C++ Case Study

The C++ program presents the project-management model as a typed repository data layer.

The four principal structures are:

`Project` represents a project table row.

`Task` represents a task table row and contains `projectId` as its foreign-key value.

`Member` represents a team-member row.

`ProjectMember` represents the associative table for the many-to-many project/member relationship.

The `Database` class owns these collections and exposes operations for inserting, updating, relating, querying, and validating records.

The case study includes explicit primary-key generation and uniqueness checks. `addTask()` validates the referenced project before inserting the child row. `addProjectMember()` validates both sides of the relationship and enforces the composite `(projectId, memberId)` key.

The `taskIdsByProject_` structure demonstrates an index that maps a parent key to related task IDs. `printIndexedLookup()` uses that index rather than scanning every task to discover the candidate task IDs.

`printOneToManyJoin()` demonstrates a project-to-task join. Its handling of projects with no tasks represents the important distinction between inner-join and left-join behavior.

`printManyToManyJoin()` resolves project-membership rows through both parent collections, showing why the associative table is required for a many-to-many relationship.

`printProjectStatistics()` demonstrates grouping and aggregation by project. It counts total, completed, in-progress, and todo tasks and calculates a derived completion percentage.

The transaction case study uses state snapshots. The program inserts a temporary project, then deliberately attempts an invalid task insertion. The failure restores the earlier state, demonstrating atomic behavior.

## Data Modeling Decisions

The model keeps project facts in `projects` and task facts in `tasks`.

Storing `project_name` and `owner` directly in every task would duplicate parent information. If the owner changed, multiple task rows could become inconsistent. Storing only the project key and resolving the project through a relationship avoids that duplication.

The task's `status` is stored on the task because it describes the state of that specific work item.

The member's identity belongs in the member table, while the member's role on a particular project belongs in `project_members`. This distinction is important because a person's role can vary by relationship.

The associative table also provides a natural location for additional relationship-specific attributes such as assignment date or allocation percentage if such information becomes part of the model.

## Null and Missing Data

A missing value and a missing relationship are different concepts.

The Python `due_date` column is nullable because a task may not yet have a known due date. This is distinct from an invalid `project_id`, which violates the relationship.

The left-join examples demonstrate another form of absence: a project may exist even when it has no task rows.

A database design should therefore distinguish:

- a value that is unknown or not supplied
- a row that does not exist
- a relationship that does not exist
- an invalid reference

Treating all four conditions as the same can produce incorrect queries and misleading application behavior.

## Common Modeling Mistakes

Duplicating parent attributes in child rows creates update anomalies. A task should normally reference its project rather than independently storing another copy of the project owner.

Using a descriptive value as the only relationship identifier can make relationships fragile when that value changes. A stable primary key is generally better suited for references.

Allowing arbitrary strings for controlled state values makes data quality dependent on every client. A database-level `CHECK`, enum-like database type, lookup table, or other explicit constraint can make the permitted state space enforceable.

Representing a many-to-many relationship as a comma-separated list of IDs inside one column makes referential integrity and querying difficult. An associative table provides explicit rows and foreign keys.

Relying only on application validation leaves a database vulnerable to invalid writes from other clients, scripts, administrative operations, or future application code. Important invariants should be enforced as close to the persistent data as practical.

Adding an index to every column can increase storage and write costs. Indexes should be connected to actual access patterns.

## Performance Considerations

Without an index, finding tasks for a project can require examining many task rows. The Python query planner demonstration and the JavaScript and C++ relationship indexes show why repeated access patterns can benefit from indexing.

A composite index such as `(project_id, status)` is particularly useful when queries commonly filter by both values. Index column order matters because the database can exploit the leading portion of a composite index more readily than an arbitrary suffix.

Joins also have performance characteristics. A relational database optimizer can select join algorithms and access paths based on table statistics and available indexes. The C++ program intentionally performs straightforward scans so that the relationship mechanism is visible, but a production system would rely on a database engine for query optimization.

Indexes should therefore be evaluated against real query workloads rather than treated as a universal performance solution.

## Security Considerations

SQL injection is fundamentally a separation problem: data supplied by a user must not become part of the SQL command structure.

The Python implementation uses parameterized SQL for user-supplied search text. A value such as `Market' OR 1=1 --` is passed as a parameter rather than concatenated into a SQL statement.

The JavaScript implementation demonstrates the same conceptual boundary through a safe in-memory search function.

Production database applications should also apply appropriate authorization controls. A database user that only needs to read reporting data should not automatically receive permission to modify schema or delete records.

Credentials, connection strings, and database secrets should not be embedded in source files. Production systems should use appropriate secret-management and environment-configuration mechanisms.

## Debugging and Failure Analysis

Database errors are often easier to diagnose when the failed operation is associated with a specific invariant.

A primary-key error indicates a row-identity conflict.

A unique constraint error indicates that a value required to be unique already exists.

A foreign-key error indicates that a referenced parent row is missing or that a relationship operation violates referential rules.

A check-constraint error indicates that a value does not satisfy the declared domain.

A transaction failure requires examining the complete unit of work because an earlier successful statement may have been rolled back along with the operation that failed.

The Python program deliberately triggers these failure conditions so that they can be observed rather than merely described.

## Production Considerations

The examples are intentionally small, but the same principles become more important as the amount of persistent data and the number of clients increase.

A production relational database should define its schema deliberately, enforce critical constraints, use transactions for related changes, and establish indexes based on measured query patterns.

Schema migrations should change table structures in controlled, versioned steps rather than relying on ad hoc manual edits.

Foreign-key behavior should match the lifecycle of the data. Restricting deletion protects historical records, while cascading deletion can be appropriate when child data has no independent value.

Connection management matters because production applications commonly use connection pools rather than opening a new database connection for every individual operation.

Concurrency also changes the problem. Two clients can read or modify related rows at the same time, so production systems need appropriate transaction isolation and conflict-handling strategies.

The examples use standard-library or language-native structures to keep the demonstrations self-contained. The Python SQLite implementation is the only one of the three that uses an actual relational database engine.

## Relationship Between the Implementations

The implementations share one logical data model but intentionally emphasize different mechanisms.

The Python program demonstrates what a relational database engine actually enforces. Its strongest focus is SQL schema definition, constraints, foreign keys, joins, transactions, indexes, query plans, and integrity checks.

The JavaScript program demonstrates how an application can represent relational concepts using native data structures and event-driven behavior. Its focus is the boundary between application objects and persistent data rules.

The C++ program demonstrates how a strongly typed system can model the same domain explicitly. Its focus is data structures, relationship traversal, validation, indexes, composite keys, aggregation, and transaction-style state restoration.

The common relationship is:

`projects.project_id`
→ `tasks.project_id`

and:

`projects.project_id`
→ `project_members.project_id`

`members.member_id`
→ `project_members.member_id`

These relationships are the foundation that connects the tables without collapsing separate entities into duplicated data.

## File Execution

The Python program can be executed with a standard Python 3 installation:

`python database_fundamentals.py`

The JavaScript program requires a modern Node.js runtime supporting `structuredClone()`:

`node database_fundamentals.js`

The C++ program requires a C++17-compatible compiler:

`g++ -std=c++17 -Wall -Wextra -pedantic database_fundamentals.cpp -o database_fundamentals`

The C++ executable can then be started with:

`./database_fundamentals`

On Windows with MinGW, the generated executable can be run as:

`database_fundamentals.exe`
