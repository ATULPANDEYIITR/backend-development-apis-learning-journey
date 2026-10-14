# SQLAlchemy Queries: SELECT, Filtering, Joins, Ordering, Aggregation, Pagination

## Scope

This project studies relational querying through SQLAlchemy ORM query construction, with particular attention to `SELECT`, filtering, joins, ordering, aggregation, and pagination.

The examples use a small employee-management domain containing departments, employees, projects, and employee-project assignments. The domain is intentionally relational so that query behavior can be examined through entity relationships rather than isolated SQL expressions.

The six query areas have distinct responsibilities:

- **SELECT** determines which entities or columns are returned.
- **Filtering** restricts rows according to predicates.
- **Joins** combine related relational entities.
- **Ordering** determines deterministic result order.
- **Aggregation** calculates values such as count, average, minimum, maximum, and sum.
- **Pagination** returns a controlled subset of an ordered result set.

The implementations show how these concepts interact without treating them as interchangeable operations.

## Relational Model

The model contains five logical components.

| Entity | Purpose | Important relationship |
|---|---|---|
| `Department` | Organizational grouping | One department has many employees |
| `Employee` | Primary business entity | Each employee belongs to one department |
| `Project` | Work or delivery unit | Projects can contain many employees |
| `EmployeeProject` | Association table | Implements employee-project many-to-many relationships |
| `Project` status | Project lifecycle state | Used by existence and filtering queries |

The employee table contains salary, joining date, department membership, and contact information. The project table contains budget and status. The association table prevents duplicate employee-project assignments through a composite primary key.

The same logical relationships appear in the SQLAlchemy, SQL, C++, Java, and JavaScript implementations, but each implementation uses mechanisms appropriate to its own environment.

## SQLAlchemy Environment

The Python implementation uses SQLAlchemy 2.x-style ORM querying and an in-memory SQLite database.

The database is created with:

`create_engine("sqlite+pysqlite:///:memory:")`

The ORM model uses declarative mappings with `DeclarativeBase`, `Mapped`, and `mapped_column`. Relationships are represented with SQLAlchemy's `relationship()` construct.

The database is populated before the query demonstrations run, making the Python file executable without requiring an externally running PostgreSQL server.

PostgreSQL remains a useful production target. The query expressions demonstrated here are largely database-independent, while actual SQL generation and some advanced functions can vary by dialect.

## SELECT Queries

The simplest ORM query uses:

`select(Employee)`

This asks SQLAlchemy to construct a statement that returns complete `Employee` ORM objects.

The Python implementation also demonstrates column projection:

`select(Employee.name, Employee.email, Employee.salary)`

Projection matters when the application does not need the complete entity. Returning only required columns can reduce transferred data and simplify the result shape.

The distinction is important:

- `select(Employee)` represents an entity-oriented result.
- `select(Employee.name, Employee.salary)` represents a column-oriented projection.

The script converts the latter into application-level dictionaries and typed dataclass objects.

The SQL implementation mirrors the same distinction with `SELECT *`-style entity retrieval versus explicitly selected columns.

## Filtering

SQLAlchemy represents predicates as Python expressions that become SQL conditions.

For example:

`select(Employee).where(Employee.salary >= Decimal("110000.00"))`

represents a database-level filter rather than retrieving all employees and filtering them in Python.

The Python implementation demonstrates:

- minimum salary conditions
- salary ranges
- department membership
- string pattern matching
- combined `AND` conditions
- alternative `OR` conditions
- dynamically assembled predicates

The use of SQLAlchemy expressions is preferable to constructing SQL text by concatenating user-provided values. Bound parameters allow the database driver to handle values without treating them as SQL syntax.

The dynamic query function accepts optional filters and adds only the predicates that were requested. This pattern is useful for search endpoints where a client may provide several optional filters.

## Filtering and Relationships

A filter can depend on a related entity.

The implementation uses department relationships to find employees belonging to particular departments. An explicit join can also be used:

`select(Employee).join(Employee.department).where(Department.name == "Security")`

This expresses the relationship in the query itself.

The important distinction is that the filter is still a filtering operation, while the join supplies the relational path needed to evaluate the department condition.

## INNER JOIN

The employee-department relationship is one-to-many:

`Department -> Employee`

An employee stores `department_id`, while the department owns the referenced organizational record.

SQLAlchemy can express the relationship through:

`join(Employee.department)`

and select values from both sides:

`select(Employee.name, Department.name.label("department"))`

The resulting rows contain employee and department information without requiring the application to manually match foreign-key identifiers.

The SQL implementation exposes the relational mechanism directly:

`INNER JOIN departments AS d ON d.id = e.department_id`

An inner join returns employees for which the matching department exists.

The database foreign key constraint makes that relationship mandatory in this model.

## Many-to-Many Joins

Employees and projects have a many-to-many relationship.

An employee can participate in multiple projects, and a project can contain multiple employees. A direct foreign key on either table would not model this relationship correctly.

The association table:

`employee_projects(employee_id, project_id)`

connects both sides.

SQLAlchemy can navigate this relationship through:

`Project.employees`

The query:

`select(Project.name, Employee.name).join(Project.employees)`

allows the ORM to construct the required relational joins.

The SQL implementation explicitly traverses:

`projects -> employee_projects -> employees`

This distinction is important because many-to-many queries frequently produce more rows than the number of entities involved. One employee appearing in three projects produces three relationship rows.

## Ordering

Ordering is represented in SQLAlchemy with `order_by()`.

The Python implementation demonstrates:

`order_by(desc(Employee.salary), asc(Employee.name))`

Salary is the primary ordering criterion, while employee name acts as a deterministic tie-breaker.

Deterministic ordering is especially important for pagination. If records are paginated without a stable ordering, the database does not guarantee that successive requests will observe a consistent sequence.

The SQL implementation uses:

`ORDER BY salary DESC, name ASC`

The same principle appears in the C++ and Java implementations through comparator logic.

## Aggregation

Aggregation changes the purpose of a query from returning individual rows to calculating values across rows.

The Python implementation uses SQLAlchemy's `func`:

`func.count(Employee.id)`

`func.avg(Employee.salary)`

`func.min(Employee.salary)`

`func.max(Employee.salary)`

`func.sum(Employee.salary)`

These expressions are translated into database aggregation functions.

The global employee query calculates:

- number of employees
- total salary
- average salary
- minimum salary
- maximum salary

The calculation occurs in the database rather than requiring the complete employee table to be transferred into Python.

This distinction becomes increasingly important for large datasets.

## GROUP BY

Department-level reporting uses grouping.

The SQLAlchemy query selects department information together with aggregate expressions and then uses:

`group_by(Department.id, Department.name)`

Each department becomes an aggregation group.

The result can contain:

- department name
- employee count
- average salary
- highest salary

`HAVING` is used when the condition applies to an aggregate group rather than an individual row.

For example, a condition on `AVG(salary)` belongs in `HAVING`, not `WHERE`.

`WHERE` restricts rows before grouping.

`HAVING` restricts groups after aggregation.

This distinction is fundamental to relational query construction.

## Subqueries

The Python implementation calculates the company-wide average salary as a scalar subquery and then selects employees whose salary is above that value.

The conceptual SQL is:

`WHERE salary > (SELECT AVG(salary) FROM employees)`

The subquery produces one value that becomes part of the outer query's predicate.

This is different from calculating the average in application code and then inserting that value into a second query. Keeping the calculation in the database allows the operation to be expressed as one relational statement.

## EXISTS

The project example demonstrates a different type of relational question:

"Does this employee have at least one active project?"

The SQLAlchemy relationship expression:

`Employee.projects.any(Project.status == "active")`

represents an existence test.

The SQL version uses `EXISTS`.

`EXISTS` is appropriate when the application needs to know whether a matching relationship exists and does not need every matching relationship row returned.

This can be preferable to a join when the requested result is still one row per employee and duplicate rows from multiple matching projects would otherwise need to be removed.

## Pagination

The Python implementation demonstrates limit-offset pagination:

`limit(page_size).offset(offset)`

The offset is calculated as:

`(page - 1) * page_size`

For example, page 2 with a page size of 3 starts after the first three records.

Pagination is not simply a slicing operation. A production query should normally combine pagination with deterministic ordering:

`order_by(Employee.id).limit(page_size).offset(offset)`

The SQL implementation demonstrates the equivalent:

`ORDER BY id LIMIT 3 OFFSET 3`

The example also performs a separate `COUNT(*)` query so an API can expose both the current page and the total matching record count.

## Pagination Validation

The reusable Python pagination function rejects:

- page numbers below 1
- page sizes below 1
- page sizes above the configured maximum

This validation protects the query layer from invalid parameters and prevents excessively large page requests.

A maximum page size is particularly useful for API endpoints because an unrestricted client could request a very large result set and create unnecessary database and application load.

## Query Composition

The Python implementation builds dynamic conditions as SQLAlchemy expressions.

A query can begin with:

`select(Employee).join(Employee.department)`

and then conditionally add:

`where(Department.name == department_name)`

or:

`where(Employee.salary >= minimum_salary)`

This style allows a repository or service layer to compose a query from independently validated conditions.

The important design property is that the application constructs a structured query expression rather than manually assembling SQL source code.

## Generated SQL

The Python script includes a query-inspection function that compiles a SQLAlchemy statement for debugging.

The demonstration uses `literal_binds` only to make the generated statement readable during inspection.

Production applications should not manually interpolate values into SQL strings. SQLAlchemy's normal parameter-binding behavior should remain responsible for values supplied to statements.

Generated SQL inspection is useful when diagnosing:

- unexpected joins
- missing filters
- incorrect ordering
- inefficient projections
- incorrect pagination
- aggregation behavior
- dialect-specific SQL

## Python Implementation

The Python program is the primary ORM demonstration.

Its model contains `Department`, `Employee`, `Project`, and `EmployeeProject`. Relationships represent the database structure, while `select()` constructs SQLAlchemy 2.x-style statements.

The implementation progresses from simple entity selection to column projections, conditional filtering, relationship joins, many-to-many traversal, ordering, aggregation, grouped reporting, pagination, subqueries, existence tests, dynamic query construction, transaction handling, and generated-SQL inspection.

The `EmployeeSummary` dataclass demonstrates an additional application-layer pattern: a query can return a narrow projection and transform it into a stable typed result object rather than exposing the complete ORM entity.

## JavaScript Implementation

The JavaScript program approaches the same relational operations as an explicit query-processing pipeline.

It implements:

- projection
- predicate filtering
- ordering
- inner joins
- many-to-many traversal
- grouping
- aggregation
- pagination
- dynamic filters
- existence checks
- validation

The implementation deliberately uses JavaScript collections rather than pretending that JavaScript has SQLAlchemy. This makes the relational stages visible and provides a useful conceptual comparison with the ORM implementation.

The `innerJoin()` function builds an index on the right-hand input before matching rows. This is more representative of an efficient join implementation than repeatedly scanning the complete right-hand collection for every left-hand row.

The query pipeline also shows the conceptual sequence:

`JOIN -> WHERE -> SELECT -> ORDER BY -> LIMIT`

That sequence helps distinguish query construction stages even though an actual database optimizer may execute the operations in a different physical order.

## C++ Case Study

The C++ program models a query engine around the same relational employee domain.

It uses:

- `std::vector` for relation-like collections
- `std::unordered_map` for lookup indexes
- `std::map` for grouped aggregation
- `std::set` for existence membership
- algorithms such as `copy_if`, `sort`, `accumulate`, and `remove_if`

The employee-department join builds a department index first. This illustrates why database indexes can materially affect join performance.

The aggregation implementation groups employees by department and calculates count, sum, minimum, maximum, and average salary.

The pagination implementation validates page and page-size constraints before calculating the requested range.

The final complex query combines join, filtering, ordering, projection, and pagination to model the type of multi-stage query that an application repository could expose as an API operation.

## Java Implementation

The Java program uses records for immutable domain representations.

`Department`, `Employee`, `Project`, `EmployeeProject`, and `EmployeeDepartmentView` represent the relational entities and projected result.

Java Streams are used for filtering, sorting, grouping, aggregation, and existence tests.

`BigDecimal` is used for salary values rather than binary floating-point arithmetic. This avoids the representation issues that can occur when monetary values are stored as `double`.

The `Page<T>` record gives pagination a typed result containing:

- current records
- page number
- page size
- total records
- total pages

The `SortField` enum prevents arbitrary sort-field strings from reaching the sorting logic. This is a useful application-layer validation pattern for APIs that expose sorting controls.

## SQL Implementation

The SQL script is PostgreSQL-compatible and creates the relational model directly.

The database constraints include:

- primary keys
- unique employee emails
- foreign keys
- salary validation
- project-status validation
- composite uniqueness for employee-project assignments

Indexes are added to foreign-key and frequently queried columns such as department identifiers, salary, joining date, and project identifiers.

The script demonstrates:

- basic `SELECT`
- projections
- `WHERE`
- `IN`
- `ILIKE`
- `INNER JOIN`
- many-to-many joins
- `ORDER BY`
- global aggregation
- `GROUP BY`
- `HAVING`
- subqueries
- `EXISTS`
- `LIMIT`
- `OFFSET`
- total-count queries
- combined reporting queries
- transaction boundaries
- database-level integrity enforcement

The SQL file is intentionally executable rather than a collection of pseudo-SQL fragments.

## Relationship Between the Query Operations

The operations answer different questions.

A `SELECT` determines what information is requested.

A `WHERE` condition determines which rows qualify.

A `JOIN` determines which related relations participate in the result.

`ORDER BY` determines result sequence.

Aggregation transforms multiple rows into calculated values.

`GROUP BY` creates independent aggregation groups.

Pagination limits the visible portion of an ordered result.

These operations can appear in the same statement without becoming the same operation. For example, an employee directory query can join employees to departments, filter by department and salary, order by salary, and paginate the final result.

## Query Shape and Result Shape

A complete ORM entity has a different result shape from a column projection.

For example:

`select(Employee)`

produces ORM-managed employee objects.

By contrast:

`select(Employee.name, Department.name)`

produces rows containing selected values.

This distinction affects memory usage, serialization, API response design, and application architecture.

A repository method should therefore select the smallest useful result shape rather than automatically retrieving complete entities for every operation.

## Performance Considerations

Database-side filtering is preferable to retrieving every row and filtering in application memory.

Database-side aggregation avoids transferring all source rows when only a summary is required.

Indexes can accelerate selective filters and joins, although an index is not automatically beneficial for every query. Index maintenance consumes storage and can increase the cost of writes.

Large offset-based pagination can become expensive because the database may need to locate and skip many earlier rows.

Stable ordering is necessary for predictable pagination.

Joins should be supported by appropriate foreign-key indexes when query volume and database execution plans justify them.

The SQLAlchemy statement itself is not the complete performance model. Actual performance depends on the generated SQL, database dialect, indexes, cardinality, query planner, data distribution, network cost, and transaction behavior.

## Security Considerations

Structured SQLAlchemy expressions should be preferred to manually concatenated SQL strings when values originate from users.

User-controlled sorting should be mapped to an explicit allowlist of model columns rather than passed directly into SQL text.

The Java implementation demonstrates this principle with `SortField`.

Pagination parameters should have upper bounds.

Filtering parameters should be validated before they are used to construct application behavior.

Database constraints should enforce important invariants independently of application validation because multiple applications or processes may write to the same database.

Sensitive columns should not be selected merely because they are available in the ORM model.

## Debugging Query Behavior

When a query returns unexpected results, inspect each logical stage.

Check the selected columns or entities first.

Then verify filter predicates.

Inspect joins and relationship paths.

Verify the ordering criteria.

For aggregation, verify grouping columns and distinguish `WHERE` from `HAVING`.

For pagination, verify ordering, page size, offset calculation, and total-count behavior.

SQLAlchemy's compiled statement inspection can help reveal whether the generated SQL matches the intended relational operation.

Database-side query plans should be examined when a logically correct query performs poorly.

## Edge Cases

The examples explicitly address several important boundary conditions.

An employee may belong to a department but have no project assignment. A project may have several employees, causing a many-to-many join to produce multiple rows for the same employee.

Aggregation must account for empty input when an application expects a result even when no rows qualify.

Pagination must handle a page beyond the final page without producing an invalid collection range.

A page size should have an application-defined upper bound.

A sorting parameter should be constrained to supported fields.

A missing relationship can change the result of an inner join because unmatched rows are excluded.

An existence query can return one employee even when that employee has several matching related records, which distinguishes `EXISTS` from directly returning all matching join rows.

## Common Query Design Errors

Filtering after retrieving an unnecessarily large dataset wastes database and application resources.

Using pagination without deterministic ordering can cause unstable page boundaries.

Using `WHERE` for an aggregate condition such as `AVG(salary) > 100000` is incorrect because aggregate results are evaluated after row filtering and grouping.

Using an inner join when unmatched parent records must remain visible can unintentionally remove rows.

Returning every ORM column when an endpoint needs only two fields increases result width unnecessarily.

Allowing arbitrary client-controlled sort expressions can create unsafe query construction or unexpected database behavior.

Assuming that ORM relationship navigation always produces the most efficient SQL can hide expensive joins or result expansion.

## Transaction Behavior

The Python implementation includes a transaction example where a new employee is inserted after verifying the target department.

The SQL script demonstrates the equivalent operation using `BEGIN` and `COMMIT`.

Transactions matter when a query and a write form one logical operation. If the operation fails before commit, the database can roll back the transaction instead of leaving a partially completed state.

Read queries do not automatically require an explicit application-managed transaction for every use case, but transaction boundaries become important when several database changes must succeed or fail together.

## Database Integrity

Application code can validate data before writing it, but database constraints provide a second and authoritative integrity layer.

The SQL model prevents:

- duplicate employee emails
- negative salaries
- invalid project statuses
- references to nonexistent departments
- references to nonexistent employees or projects
- duplicate employee-project assignments

These constraints are separate from SQLAlchemy query construction. SQLAlchemy can express and execute queries, but relational integrity ultimately belongs to the database schema.

## Practical API Query Pattern

A realistic employee-search endpoint can conceptually expose parameters such as department, minimum salary, maximum salary, sort field, page, and page size.

The SQLAlchemy service can translate those validated parameters into a statement containing:

`SELECT`

followed by relationship joins where necessary, optional `WHERE` predicates, deterministic `ORDER BY`, and bounded `LIMIT/OFFSET`.

A separate count statement can provide pagination metadata.

This pattern separates request validation from query construction while keeping filtering, sorting, and pagination at the database layer.

## Query Complexity Perspective

For a simple indexed lookup, a database can often locate records efficiently without scanning the complete relation.

A join can range from inexpensive indexed lookups to expensive large relation operations depending on cardinality and available indexes.

Aggregation may require scanning qualifying rows and grouping them.

Offset pagination can become increasingly costly for deep pages because rows before the requested offset still have to be considered.

These are not properties of SQLAlchemy alone. SQLAlchemy constructs statements; the database optimizer determines the physical execution strategy.

## Implementation Comparison

| Area | Python | JavaScript | C++ | Java | SQL |
|---|---|---|---|---|---|
| SELECT | SQLAlchemy `select()` | Projection functions | Collection projection | Stream projection | `SELECT` |
| Filtering | `.where()` expressions | `filter()` predicates | `copy_if()` | Stream `filter()` | `WHERE` |
| Joins | ORM relationships and `join()` | Indexed `innerJoin()` | Hash-style lookup index | Maps plus streams | `JOIN` |
| Ordering | `order_by()` | Sorting functions | `std::sort` | `Comparator` | `ORDER BY` |
| Aggregation | `func.count`, `func.avg` | Grouping and reducers | `map` and accumulation | `groupingBy` and reduction | `GROUP BY` |
| Pagination | `limit()` and `offset()` | Array slicing | Validated ranges | Generic `Page<T>` | `LIMIT/OFFSET` |

The implementations are intentionally not literal translations. Each one emphasizes mechanisms natural to its own environment while preserving the same relational ideas.

## Execution

The Python implementation requires SQLAlchemy:

`pip install sqlalchemy`

Then run the Python file with Python 3.

The C++ implementation requires a C++17-or-later compiler.

The Java implementation requires Java 17 or later.

The JavaScript implementation requires a modern Node.js runtime.

The SQL implementation is designed for PostgreSQL.

The Python database is intentionally in-memory, so running the script creates its schema and sample data from scratch.

## Technical Boundary

SQLAlchemy is an ORM and SQL toolkit, not a replacement for understanding relational query semantics.

The most important skill demonstrated by these artifacts is the ability to map an application requirement to the correct relational operation.

"Return employees" is a selection problem.

"Return employees earning at least 100000" adds filtering.

"Return employee names with department names" requires a join.

"Return highest-paid employees first" requires ordering.

"Return average salary by department" requires grouping and aggregation.

"Return records 21 through 30 in a stable sequence" introduces pagination.

Real applications frequently combine these operations in one query, which is why understanding their individual roles is necessary before composing them into a reliable SQLAlchemy query.
