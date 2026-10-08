# Query Optimization: EXPLAIN, EXPLAIN ANALYZE, Sequential Scans, Index Scans, and Query Planning

## Scope

This learning artifact treats query optimization as a database execution-planning problem rather than as a collection of isolated indexing rules.

The implementations focus on how a relational database decides how to execute a query, how cardinality estimates influence that decision, why a sequential scan can be correct, when an index scan becomes attractive, how composite and covering indexes affect access paths, and how `EXPLAIN` and `EXPLAIN ANALYZE` expose the difference between what the planner expected and what actually happened.

The examples use an order-management workload because it provides realistic filtering, joins, date ranges, aggregation, sorting, and data-distribution problems.

The six files deliberately approach the same optimization domain from different technical perspectives:

| Deliverable | Primary perspective |
|---|---|
| Python | Executable laboratory using the standard library, with plan inspection, measurements, selectivity analysis, and a PostgreSQL-style plan model |
| JavaScript | Event-driven query-planning model with explicit plan nodes, access-path selection, cardinality analysis, and sargability diagnostics |
| C++ | Performance-oriented optimization engine using explicit cost models, plan trees, indexes, joins, and cardinality reasoning |
| Java | Enterprise-oriented domain model using records, enums, validation, immutable collections, planning services, and explicit optimization policies |
| SQL | PostgreSQL execution environment with actual `EXPLAIN`, `EXPLAIN ANALYZE`, indexes, statistics, joins, aggregation, and plan diagnostics |
| README | Technical explanation connecting the implementations and the database concepts |

## Query Planning

A database does not normally execute SQL in the textual order in which it appears. The SQL statement expresses the required result, while the optimizer determines an execution strategy.

For a query against `orders`, the optimizer may need to answer questions such as:

- Should the table be read from beginning to end?
- Can an index locate a small qualifying subset?
- Can multiple predicates be represented efficiently by a composite index?
- Does the selected index contain all required output columns?
- Will a sort be necessary?
- Which table should be accessed first in a join?
- Should the join use nested-loop, hash, or another strategy?
- How many rows are expected after each operation?
- How expensive is the expected access path compared with alternatives?

The optimizer makes these decisions from available metadata, statistics, indexes, predicates, estimated cardinalities, and cost parameters.

The important distinction is between **logical SQL** and the **physical execution plan**. Two SQL statements can produce the same result while causing substantially different amounts of I/O, CPU work, memory consumption, and sorting.

## Cardinality Estimation

Cardinality is the number of rows expected at a particular point in a query plan.

Suppose an `orders` table contains 500,000 rows and the planner estimates that a predicate will return 500 rows. That estimate strongly influences the access-path decision.

An index-driven strategy may be attractive when only 500 rows are expected.

If the same predicate actually returns 300,000 rows, the original assumption is badly wrong. An index-driven strategy that looked inexpensive during planning may require many table-page visits during execution.

This is why `EXPLAIN ANALYZE` is particularly valuable. It allows estimated values to be compared with observed execution values.

A useful diagnostic pattern is:

`estimated rows` versus `actual rows`

A large mismatch does not automatically prove that an index is missing. It can indicate:

- stale statistics
- skewed data distribution
- correlated columns
- an unexpectedly common value
- an inaccurate selectivity assumption
- a predicate whose behavior differs from the planner's statistical model
- a join whose input cardinality was underestimated

A cardinality error can propagate upward. If an early plan node underestimates its output by a large factor, later join, aggregation, memory, and sorting decisions can also become inappropriate.

## EXPLAIN

PostgreSQL `EXPLAIN` displays the execution plan selected by the optimizer without executing the query.

A typical command is represented in the SQL deliverable as:

`EXPLAIN SELECT ...;`

Important information includes:

- plan-node type
- estimated startup cost
- estimated total cost
- estimated number of output rows
- estimated average row width
- relation or index involved
- filters and index conditions
- join strategy
- sort or aggregation operations

The cost values are planner estimates, not elapsed milliseconds.

A plan with a higher numerical cost is not necessarily slower in every environment. PostgreSQL's cost model is designed to compare candidate strategies under configured assumptions about CPU and I/O.

The correct interpretation is comparative: the optimizer uses cost estimates to decide which available plan appears cheapest.

## EXPLAIN ANALYZE

`EXPLAIN ANALYZE` executes the query and reports actual execution information.

The SQL implementation uses statements such as:

`EXPLAIN ANALYZE SELECT ...;`

This makes it possible to compare:

- estimated rows
- actual rows
- estimated operation cost
- actual timing
- loops
- buffer activity when `BUFFERS` is requested

The SQL script also demonstrates:

`EXPLAIN (ANALYZE, BUFFERS, VERBOSE) ...`

This is useful when a query appears slow because a plan node is performing substantially more physical work than expected.

A key diagnostic principle is that a plan should be evaluated as a tree. Looking only at the first line can hide the real cost. An apparently efficient index scan can feed a very expensive sort or join. A fast scan can also be followed by an aggregation over a much larger intermediate result.

`EXPLAIN ANALYZE` changes the situation compared with plain `EXPLAIN`: the statement actually executes. For production diagnostics, the operational effect of the query must therefore be considered before running it against large or modifying workloads.

## Sequential Scans

A sequential scan reads the table relation rather than locating rows through a secondary index.

A sequential scan is not inherently inefficient.

It can be the rational choice when a query needs a large proportion of the table. If 300,000 out of 500,000 rows qualify, using an index to locate those rows can introduce substantial additional heap access.

The PostgreSQL SQL example deliberately begins with a broad `status = 'DELIVERED'` query before adding secondary indexes. This makes the scan choice observable.

The Python and C++ implementations also model the same economic distinction: a table-wide scan has work proportional to the relation size, while an index strategy has startup and per-match costs.

The correct optimization question is therefore not:

> "Why did PostgreSQL use a sequential scan?"

The better question is:

> "Given the estimated result size, available indexes, physical storage, and other plan operations, why was the sequential scan considered cheaper?"

## Index Scans

An index scan navigates an index to locate qualifying entries and then retrieves the corresponding table rows when necessary.

An equality predicate such as:

`WHERE customer_id = 42`

can be highly selective when `customer_id` has many distinct values.

An index on `customer_id` gives the planner an ordered structure that can locate matching entries without examining every row in the table.

The SQL deliverable creates:

`idx_orders_customer_id`

and then uses `EXPLAIN` and `EXPLAIN ANALYZE` to inspect the resulting plan.

Index access is especially useful when:

- the predicate is selective
- the index matches the predicate
- the table is sufficiently large
- the projected rows are relatively few
- the physical access cost remains reasonable
- the query benefits from the index's ordering

An index does not guarantee an index scan. PostgreSQL can still choose a sequential scan if its estimates indicate that indexed access will cost more.

## Bitmap Access

PostgreSQL can use bitmap-based access when a predicate is selective enough to benefit from an index but produces enough rows that individually visiting heap rows is less attractive.

A bitmap approach separates the process into two broad stages:

- identify qualifying tuple locations through an index
- visit relevant heap pages using the collected locations

This can reduce inefficient random heap access.

The SQL script creates a status index and evaluates a predicate combining `status` with `total_amount`.

The exact plan depends on data distribution and planner cost assumptions. The important concept is that index usage is not limited to a simple one-row-at-a-time index scan.

## Index Only Scan

An Index Only Scan can satisfy a query from an index without fetching the corresponding table row for every result.

The SQL implementation demonstrates a covering index using PostgreSQL's `INCLUDE` facility:

`CREATE INDEX ... ON orders(customer_id, order_date) INCLUDE (total_amount, status);`

The search keys remain `customer_id` and `order_date`, while `total_amount` and `status` are available as payload columns.

Index-only execution also depends on PostgreSQL's visibility information. MVCC means that the database must still establish whether tuples are visible to the current transaction. The visibility map helps PostgreSQL determine when heap access can be avoided.

A covering index therefore has a specific purpose. It should not be treated as a universal solution because wider indexes consume storage and increase maintenance work for inserts, updates, vacuum activity, and index creation.

## Composite Indexes

A composite index contains multiple key columns.

The SQL implementation creates:

`idx_orders_customer_date ON orders(customer_id, order_date)`

for queries that combine customer equality with an order-date range.

This arrangement is appropriate for a workload shaped like:

`customer_id = 42`

followed by:

`order_date >= ... AND order_date < ...`

The order of columns matters.

A composite B-tree index is ordered by its leading key first. A query constrained on the leading column can generally exploit the index differently from a query that only constrains a later column.

This is why index design should begin with actual query patterns rather than with a rule such as "put the most selective column first" applied without workload analysis.

Equality predicates, range predicates, ordering requirements, join keys, and the actual workload frequency all influence a useful column order.

## Sargability

A predicate is commonly described as sargable when its structure allows the database to use an index efficiently for the relevant search condition.

Consider the difference between:

`order_date >= DATE '2026-01-01' AND order_date < DATE '2027-01-01'`

and:

`EXTRACT(YEAR FROM order_date) = 2026`

The first exposes the indexed `order_date` column directly as a range.

The second applies a function to the column. A normal index on `order_date` is not automatically an index on the extracted year expression.

The SQL, Python, JavaScript, and C++ implementations all distinguish direct predicates from expression-based predicates.

The appropriate rewrite is not always to remove a function blindly. If the expression itself is essential to the workload, a database may support an expression index. The optimization decision should be based on the actual query pattern.

## Sorting

An index can sometimes provide rows in a useful order, reducing or eliminating an explicit sort.

For example, an index beginning with `customer_id, order_date` naturally stores rows in customer and date order.

If a query requires an order that does not correspond to the selected access path, PostgreSQL may introduce a sort node.

Sorting can consume:

- CPU
- memory
- temporary storage when the operation exceeds available memory
- additional execution time for large intermediate result sets

The optimization target is not simply "remove every sort." A sort can be perfectly reasonable when the input is small. The objective is to understand why it exists and whether the workload makes its cost significant.

## Aggregation

The SQL implementation includes grouped revenue calculations:

`COUNT(*)`

and:

`SUM(total_amount)`

with grouping by customer.

Aggregation introduces another stage in the execution plan.

An efficient scan does not necessarily mean the query is cheap. If the scan produces a large intermediate result, aggregation can dominate the total work.

The plan must therefore be read from the leaves toward the root and from the input cardinalities into the operations that consume them.

## Join Planning

A join gives the optimizer another major decision.

The PostgreSQL implementation includes a customer-to-orders relationship through:

`customers.customer_id = orders.customer_id`

Possible strategies include nested-loop and hash-oriented plans, with PostgreSQL selecting based on estimated cardinalities, available indexes, join conditions, memory assumptions, and cost.

### Nested Loop

A nested-loop strategy can be effective when the outer relation is small and the inner relation can be searched efficiently.

An index on the inner table's join key can make repeated lookups practical.

The JavaScript, C++, and Java implementations model this relationship explicitly.

### Hash Join

A hash join can become attractive when the input relations are larger and equality-based matching can be performed by building a hash structure.

The important point is that a join strategy is not chosen because one algorithm is universally better. Cardinality and workload shape determine the trade-off.

## Statistics

The PostgreSQL planner does not execute every possible plan to discover which one is best. It estimates.

Statistics provide information about data distributions.

The SQL implementation queries `pg_stats` to expose information such as:

- `n_distinct`
- common values
- common-value frequencies
- histogram information

The SQL script also demonstrates changing a column's statistics target and running `ANALYZE`.

`ANALYZE` updates planner statistics.

This is important after substantial changes to the data distribution. A plan based on old statistics can become inappropriate even when the SQL and indexes have not changed.

## Data Skew

Uniform distributions are easier to estimate than highly skewed data.

Suppose most customers have a few dozen orders but one enterprise customer has hundreds of thousands.

A planner estimate based on an oversimplified distribution may expect a small result while the actual predicate returns a huge result.

That difference can change:

- sequential scan versus index access
- nested-loop versus hash join
- sort memory requirements
- aggregation cost
- total execution time

The Python, JavaScript, C++, and Java examples include explicit estimation-mismatch scenarios to make this behavior visible.

## Query Rewriting

Query rewriting should be evidence-driven.

A rewrite is useful when it changes the database's ability to execute the same logical requirement efficiently.

The SQL implementation contrasts:

`EXTRACT(YEAR FROM order_date) = 2026`

with the half-open range:

`order_date >= DATE '2026-01-01' AND order_date < DATE '2027-01-01'`

The range form preserves direct access to the indexed date column.

Half-open intervals are also useful because they avoid ambiguity around the end boundary.

The broader lesson is that SQL can be logically correct while still presenting a poor search shape to the optimizer.

## The Python Implementation

The Python file uses only the standard library.

Its database laboratory uses SQLite so the program can execute without an external database package or server. SQLite's plan terminology differs from PostgreSQL, so the program does not pretend that SQLite output is PostgreSQL output.

The Python implementation demonstrates:

- realistic customer and order data
- plan inspection through `EXPLAIN QUERY PLAN`
- repeated execution measurements
- selectivity calculation
- basic indexes
- composite indexes
- covering-index concepts
- joins
- aggregation
- sorting
- expression-based predicates
- a simplified cost model
- PostgreSQL-style plan nodes
- estimated-versus-actual row comparison
- statistics reasoning
- heuristic query diagnostics

The `PlanNode` model is deliberately separate from SQLite execution. This allows PostgreSQL concepts such as `Seq Scan`, `Index Scan`, and `Index Only Scan` to be discussed without incorrectly claiming that SQLite uses PostgreSQL's exact planner implementation.

## The JavaScript Implementation

The JavaScript file uses Node.js standard APIs and an event-driven architecture.

Its `QueryPlanner` separates planning from the `Query` representation. `PlanNode` represents an execution-plan tree rather than a flat string.

The implementation specifically demonstrates JavaScript-appropriate modeling through:

- classes
- constructor validation
- `Set`-based column coverage checks
- event handlers
- `performance.now()`
- immutable-style plan construction
- plan-tree traversal
- explicit access-path selection
- sargability analysis
- cardinality mismatch detection

The event bus demonstrates a useful distinction between query reception, plan generation, and execution measurement. This models how an application-side optimization service could emit diagnostic events without confusing those events with the database's actual optimizer.

The code intentionally uses a simplified cost function. It is useful for understanding the relationship between estimated rows and access-path choice but is not a reproduction of PostgreSQL's internal cost model.

## The C++ Case Study

The C++ program models a performance-oriented optimization engine for an enterprise order-reporting system.

Its main domain types are:

- `Predicate`
- `Index`
- `Query`
- `PlanNode`
- `QueryOptimizer`
- `PlanAnalyzer`
- `QueryDesignAnalyzer`

The `Index` abstraction distinguishes key columns from included columns and can determine whether a predicate can use the leading index key.

The `QueryOptimizer` compares sequential and index costs and can add sorting or join nodes to the plan tree.

The plan tree demonstrates an important optimization principle: the access path is only one component of total query cost.

A query can use an index and still be expensive because it requires a large sort or an inefficient join.

The C++ case study also models:

- selective customer lookups
- broad status filters
- composite indexes
- covering indexes
- nested-loop decisions
- hash-join decisions
- expression predicates
- cardinality estimation failures

C++ is particularly suitable for making the cost model explicit because the implementation can represent plan structures and numerical decisions without relying on a database server.

## The Java Enterprise Model

The Java implementation treats optimization as an enterprise service rather than as a collection of procedural examples.

The domain types distinguish:

- `PredicateType`
- `AccessPath`
- `JoinStrategy`
- `Predicate`
- `IndexDefinition`
- `QueryRequest`
- `PlanNode`

Java records provide compact immutable value objects for query requests, predicates, indexes, and plan nodes.

The `QueryPlanner` is responsible for selecting an access path and extending the plan when sorting or joins are required.

The `OptimizationService` interprets the resulting plan and compares estimated and actual cardinality.

This separation is important in larger systems because query construction, policy validation, plan evaluation, and operational reporting should not be forced into one large conditional method.

The program also models invalid requests through `InvalidQueryException`, making validation a domain concern rather than merely a logging operation.

## The PostgreSQL SQL Implementation

The SQL file is the most direct database implementation.

It creates:

- `customers`
- `orders`
- primary keys
- foreign keys
- check constraints
- indexes
- composite indexes
- covering indexes
- statistics

The sample data is generated through PostgreSQL's `generate_series`, which keeps the script reproducible without requiring an external CSV file.

The script then runs actual PostgreSQL operations involving:

- `EXPLAIN`
- `EXPLAIN ANALYZE`
- `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)`
- sequential scans
- index scans
- bitmap-oriented access
- index-only scan candidates
- composite indexes
- aggregation
- ordering
- joins
- parameterized statements
- `pg_stats`
- `ANALYZE`
- statistics targets

This file therefore provides the database-native counterpart to the planning models in the other implementations.

## Estimated Cost Versus Actual Time

A common mistake is to interpret PostgreSQL's cost numbers as milliseconds.

They are not.

A plan might contain values resembling:

`cost=0.42..120.55`

Those values are planner cost units.

With `EXPLAIN ANALYZE`, PostgreSQL also reports actual timing.

These values answer different questions:

| Value | Meaning |
|---|---|
| Cost | Planner's estimated relative execution expense |
| Rows | Estimated number of rows produced |
| Actual rows | Number of rows observed during execution |
| Actual time | Measured execution timing |
| Loops | Number of times a node executed |
| Buffers | Buffer/cache activity when requested |

A query optimization investigation should not compare a cost number directly to an actual millisecond value.

## Common Optimization Failure Modes

### Adding an index without measuring

An index consumes storage and increases write and maintenance work.

It may not be selected if the query returns too many rows.

The SQL examples intentionally show that an index does not force PostgreSQL to use it.

### Assuming sequential scans are bad

A sequential scan can be the cheapest plan for broad queries.

Replacing every sequential scan with an index can make a workload worse.

### Ignoring actual cardinality

If `EXPLAIN ANALYZE` reports actual rows dramatically different from estimated rows, the access path may be based on a false assumption.

Statistics should be investigated before changing unrelated SQL.

### Applying functions to indexed columns

A normal index on `order_date` does not automatically make `EXTRACT(YEAR FROM order_date)` searchable through that same index.

A range predicate or deliberately designed expression index may be more appropriate.

### Creating wide covering indexes indiscriminately

Covering indexes can reduce heap access, but every additional index column increases index size and maintenance cost.

The index should reflect a real workload.

### Optimizing only the scan node

A fast scan feeding an expensive sort, aggregation, or join can still produce a slow query.

The complete plan tree matters.

### Ignoring data distribution

A query that is fast for a rare customer may behave differently for a highly active customer.

Testing only one parameter value can hide skew-related problems.

## Performance Investigation Workflow

A disciplined investigation begins with the actual SQL and workload.

Inspect the plan using `EXPLAIN`.

Identify the major nodes:

- sequential scan
- index scan
- bitmap access
- index-only scan
- join
- sort
- aggregate

Then use `EXPLAIN ANALYZE` when safe and appropriate.

Compare estimated and actual row counts.

If they differ substantially, investigate statistics and data distribution.

If the estimates are reasonable, determine which plan node contributes the largest actual cost.

Only then evaluate a query rewrite, new index, statistics adjustment, or configuration change.

After changing the database design or SQL, run the plan again and compare the measured result with the original.

## Practical Interpretation of a Plan

A plan should be read as a tree.

The leaf nodes access base relations.

Intermediate nodes filter, join, aggregate, or sort data.

Parent nodes consume the output of child nodes.

If an early node unexpectedly produces 500,000 rows instead of 500, later operations can become expensive even if those later operations are individually implemented efficiently.

The most useful questions are:

- How many rows did the planner expect?
- How many rows actually appeared?
- Which node generated the unexpected volume?
- Why was that cardinality estimated incorrectly?
- Was the selected access path appropriate for the actual result size?
- Did a sort or aggregation consume the majority of the work?
- Did the join strategy match the real input sizes?
- Are statistics current?
- Does an existing index match the actual predicate shape?
- Does the index ordering support the requested ordering?
- Would a wider covering index materially reduce work?
- Does the proposed optimization improve the complete workload rather than one isolated query?

## Production Considerations

Query optimization must account for workload behavior rather than one benchmark execution.

A useful production assessment considers:

- read frequency
- write frequency
- table growth
- data distribution
- concurrency
- cache state
- transaction isolation
- maintenance overhead
- index storage
- statistics freshness
- representative parameter values
- execution-time variability

A query that improves from 800 milliseconds to 500 milliseconds but runs once per hour may matter less than a query that improves from 20 milliseconds to 8 milliseconds while running millions of times.

Similarly, an index that saves reads but substantially increases write cost may not be beneficial for a write-heavy workload.

## Security and Operational Safety

`EXPLAIN ANALYZE` executes the query.

That distinction matters operationally.

For a read-only diagnostic query, the execution may be acceptable. For a modifying statement, executing it merely to inspect performance can have side effects.

Production investigation should also consider:

- sensitive query parameters
- access permissions
- application-generated SQL
- accidental exposure of execution details
- expensive diagnostic queries
- transaction behavior
- resource consumption

The optimization process should never assume that an inspection command is automatically harmless simply because it contains the word `EXPLAIN`.

## Key Relationships

Query planning, sequential scans, index scans, and `EXPLAIN` describe different layers of the same optimization problem.

**Query planning** determines which physical strategy appears cheapest.

**Sequential scans** are one possible access path and can be optimal for broad workloads.

**Index scans** are another access path and can be attractive for selective predicates.

**`EXPLAIN`** reveals the planner's selected strategy and its estimates.

**`EXPLAIN ANALYZE`** executes the query and provides observed execution information that can be compared with those estimates.

**Statistics** connect the data distribution to planning decisions.

**Indexes** change the physical access paths available to the planner.

**Query shape** determines whether those indexes can actually be exploited.

The implementations preserve these distinctions instead of treating "use an index" as synonymous with "optimize the query."
