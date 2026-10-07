# Database Indexing: B-tree, Hash, Composite Indexes, Partial Indexes, and Selectivity

## Scope

This learning artifact treats database indexing as an access-path design problem rather than as a collection of index commands.

The central question is not simply whether a column can be indexed. The useful question is whether a particular index structure matches the predicates, ordering requirements, data distribution, and write workload of a real application.

The implementations use a commerce order workload containing customers, orders, dates, statuses, regions, and operational events. That workload makes the differences between ordered indexes, equality-oriented indexes, multi-column indexes, filtered indexes, and selectivity measurable.

The six deliverables deliberately use different technical perspectives:

| Deliverable | Primary technical perspective |
|---|---|
| Python | Executable indexing laboratory using SQLite query plans and an explicit hash-index simulation |
| JavaScript | Event-driven in-memory indexing model with JavaScript-specific data structures |
| C++ | Repository-style order analytics engine emphasizing data structures, lookup paths, and performance |
| Java | Enterprise domain model using records, enums, interfaces, collections, validation, and index services |
| SQL | PostgreSQL relational implementation with physical indexes, constraints, statistics, transactions, and `EXPLAIN` |
| README | Conceptual and implementation-level explanation of the complete indexing model |

## Indexing as an Access-Path Decision

A relational table is logically a set of rows. An index supplies an additional structure that lets the database locate qualifying rows without examining every table row in the same way as a full sequential scan.

An index is therefore an optimization structure layered over the logical relation.

The database must decide whether an index is worthwhile for a particular query. That decision depends on factors such as:

- predicate selectivity
- number of qualifying rows
- table size
- index size
- cached versus uncached pages
- ordering requirements
- available composite indexes
- statistics
- estimated random-access cost
- sequential-scan cost
- whether the query needs columns not available from the index
- current data distribution
- maintenance cost of keeping the index current

An index that is theoretically appropriate can still be ignored by an optimizer when a sequential scan is cheaper for a particular query.

## B-tree Indexes

A B-tree is an ordered index structure. In PostgreSQL, B-tree is the default index method because it supports a broad set of common relational access patterns.

A B-tree can support equality predicates such as:

`WHERE customer_id = 17000`

It can also support ranges such as:

`WHERE order_date >= DATE '2026-06-01' AND order_date < DATE '2026-07-01'`

The ordering property is important. Once the database finds the relevant portion of the key space, it can traverse neighboring keys in order.

B-trees are also useful when the query requires ordering that aligns with the index definition. For example, an index on `(order_date)` can naturally support access ordered by `order_date`.

This makes B-trees fundamentally different from an equality-oriented hash structure.

### Python demonstration

The Python implementation creates an `orders` table and builds a B-tree index on `order_date`. It then uses SQLite's `EXPLAIN QUERY PLAN` to expose the optimizer's selected access path.

The date equality query and date-range query demonstrate two different uses of the same ordered structure.

### C++ demonstration

The C++ case study uses `std::map` as an ordered model. Its `lower_bound` operations represent the key property of an ordered tree: a range can be located by finding its lower boundaries and traversing the ordered keys between them.

This is a conceptual model rather than a claim that `std::map` and a database B-tree have identical physical implementations.

## Hash Indexes

A hash index organizes keys according to a hash function and bucket structure.

Its natural access pattern is equality:

`WHERE customer_id = 17000`

A hash structure does not provide the same ordered key space as a B-tree. Consequently, a query asking for:

`WHERE customer_id BETWEEN 1000 AND 2000`

does not obtain the same natural range behavior from a hash structure.

The Python and JavaScript implementations explicitly model hash lookup with dictionaries or maps. The C++ and Java implementations use hash-based collections for equality-oriented access.

The PostgreSQL script creates an actual PostgreSQL hash index:

`CREATE INDEX idx_orders_customer_hash ON orders USING hash (customer_id);`

The presence of a hash index does not guarantee that PostgreSQL will select it. The optimizer evaluates the available paths and their estimated costs.

## B-tree Versus Hash

| Property | B-tree | Hash |
|---|---|---|
| Equality | Strong | Strong |
| Range predicates | Natural fit | Not a natural fit |
| Ordered traversal | Supported | Not supported |
| `ORDER BY` alignment | Often useful | Not useful |
| Typical role | General-purpose index | Specialized equality access |
| Key ordering | Maintained | Bucketed by hash |
| Composite access | Common | More specialized |

The choice should follow the workload rather than the name of the column.

For example, an order-date workload containing ranges and sorting strongly favors an ordered structure. An exact identifier lookup can be suitable for hash-style access.

## Composite Indexes

A composite index contains multiple columns in a defined order.

The C++ and Java examples model an index over:

`(region, status)`

The PostgreSQL implementation goes further with:

`(region, status, order_date)`

Column order is part of the access-path definition.

Consider:

`WHERE region = 'south' AND status = 'paid'`

This aligns with the leading columns of `(region, status, order_date)`.

A query that also constrains `order_date` can exploit the complete ordered key more directly:

`WHERE region = 'south' AND status = 'paid' AND order_date >= ...`

The important point is that a composite index is not equivalent to several unrelated single-column indexes. The database receives a particular multi-column ordering.

### The leftmost-prefix principle

For a composite index:

`(region, status, order_date)`

the leading portion begins with `region`.

A predicate on `region` aligns with the first indexed column.

A predicate on `region` plus `status` aligns with the first two columns.

A predicate on all three columns aligns with the complete key.

A predicate only on `status` does not have the same direct alignment because `status` is not the leading column.

This is why index column order must be derived from actual query patterns.

### Equality followed by range

A common design is:

`(tenant_id, status, created_at)`

where the first columns are equality predicates and the final column is a range or ordering predicate.

The order is not a universal rule, but it is a common pattern because it can narrow the relevant key region before traversing a range on the final indexed column.

## Partial Indexes

A partial index contains only rows satisfying a predicate.

The PostgreSQL implementation creates:

`CREATE INDEX idx_orders_pending_date ON orders USING btree (order_date) WHERE status = 'pending';`

The index therefore represents only pending orders.

A query such as:

`WHERE status = 'pending' AND order_date >= DATE '2026-10-01'`

matches the logical condition represented by the partial index.

A query asking for shipped orders cannot use that pending-only subset as its source because shipped rows are not members of the indexed population.

Partial indexes are especially useful when:

- a subset is much smaller than the table
- the subset is queried frequently
- the predicate is stable
- the query predicate matches the index predicate
- reducing index storage and maintenance is valuable

They are not automatically superior to complete indexes. The database must still evaluate whether the index provides a cheaper access path.

## Selectivity

Selectivity describes how strongly a predicate distinguishes a small subset of rows from the full relation.

Suppose a table contains 100,000 rows.

If a column has only four values and each value occurs roughly 25,000 times, a predicate on one value still matches a large part of the table.

A high-cardinality column such as `customer_id` can be much more selective when each customer owns relatively few orders.

A simple distinct-value ratio can be calculated as:

`number of distinct values / total number of rows`

The implementations calculate this ratio for:

- `status`
- `region`
- `customer_id`
- `order_date`

The ratio is useful as an initial diagnostic, but it is not a complete definition of query selectivity.

Frequency distribution matters.

For example, a four-value column could have a perfectly even distribution or a highly skewed distribution. Both have four distinct values, but a predicate on the dominant value behaves very differently from a predicate on a rare value.

## Selectivity Is Workload-Dependent

Index decisions should be based on predicates, not only column cardinality.

A status column might be a poor standalone index candidate if most queries retrieve a large fraction of the table.

The same status column can become useful inside a composite index when combined with a selective leading column.

A status predicate can also become highly useful as a partial-index condition when the indexed subset is small and frequently queried.

This creates three distinct questions:

- How many distinct values does the column have?
- How frequently does each value occur?
- What predicates does the application actually execute?

The SQL implementation exposes all three dimensions through aggregation and PostgreSQL statistics.

## Python Implementation

The Python program uses SQLite's standard library, avoiding third-party dependencies.

Its main components are:

### B-tree query plans

The script creates `idx_orders_order_date` and runs equality and range queries while inspecting `EXPLAIN QUERY PLAN`.

This makes the relationship between an ordered index and range access observable rather than merely descriptive.

### Hash simulation

SQLite does not expose a native hash-index feature equivalent to PostgreSQL's hash access method. The Python program therefore models a hash index with a dictionary.

The simulation emphasizes equality lookup and bucket behavior without incorrectly claiming that SQLite has a native hash index.

### Composite index

The script creates:

`idx_orders_region_status_date`

with the ordered columns:

`region, status, order_date`

It runs queries using the full leading prefix, all three columns, only the leading column, and a suffix-only predicate.

### Partial index

The SQLite database receives a partial index containing pending orders.

The script compares a query that matches the predicate with a query targeting shipped orders.

### Selectivity analysis

The program measures distinct counts and frequency distributions and calculates a simple distinct-to-row ratio.

### Edge conditions

The program demonstrates invalid input handling, duplicate protection, expression predicates, index inventory, and transactional rollback.

## JavaScript Implementation

The JavaScript implementation takes a different approach from the Python database laboratory.

It builds an event-driven in-memory indexing model using standard Node.js facilities.

### HashIndex

`HashIndex` stores buckets in a JavaScript `Map`.

A customer ID maps to a list of order IDs. This models the equality access pattern of a hash index.

### CompositeIndex

`CompositeIndex` combines multiple fields into a composite key.

The implementation explicitly validates the number of supplied key components, preventing accidental queries with incomplete key definitions.

### PartialIndex

`PartialIndex` accepts a predicate and stores only rows satisfying that predicate.

The pending-order index therefore contains only records for which:

`status === 'pending'`

### Event-driven maintenance

The `EventBus` models an application event such as `order.created`.

A listener updates a customer index when an order-created event arrives.

This is intentionally presented as an application-level simulation. In a real relational database, physical index maintenance belongs to the database engine and is transactionally coordinated with the table mutation.

### Selectivity

The JavaScript implementation calculates distinct-value ratios for the same domain fields while using JavaScript-specific `Map`, `Set`, class-private fields, asynchronous execution, and event handlers.

## C++ Case Study

The C++ program models an order analytics engine where different access paths serve different operational queries.

The core domain is an order service rather than a generic collection example.

### Ordered date access

`BTreeLikeDateIndex` uses `std::map<std::string, std::vector<int>>`.

Its `lower_bound` operations locate the beginning and end of a date interval.

This demonstrates why ordered structures are useful for range predicates.

### Hash customer access

`HashCustomerIndex` uses `std::unordered_map<int, std::vector<int>>`.

It provides direct equality-oriented lookup by customer ID.

The implementation stores vectors rather than assuming that one key always identifies exactly one order because a customer can own multiple orders.

### Composite access

`CompositeRegionStatusIndex` uses a pair:

`std::pair<std::string, std::string>`

as the logical composite key.

The case study therefore represents a real multi-dimensional workload:

`region + status`

rather than demonstrating composite keys as an isolated language feature.

### Partial access

`PartialPendingIndex` stores only orders whose status is `pending`.

This models the physical idea behind a partial index: rows outside the predicate are absent from that access path.

### Validation and failure behavior

The domain validates:

- positive identifiers
- non-empty regions
- supported dates
- non-negative amounts
- duplicate order IDs

An unknown order ID raises an exception because the service contract requests an entity that must exist.

An unknown customer does not raise an exception because an equality query can legitimately return zero rows.

## Java Implementation

The Java program models the same business domain using stronger enterprise-oriented domain abstractions.

### Immutable domain record

The `Order` record encapsulates an immutable order representation.

Its compact constructor validates identifiers, dates, regions, amounts, and status values.

This prevents malformed domain objects from entering the indexing service.

### Enum-based status

`OrderStatus` restricts status values to:

- `PENDING`
- `PAID`
- `SHIPPED`
- `CANCELLED`

This is safer than passing arbitrary strings throughout the application.

### Index interface

The `Index<K>` interface defines the common operations needed by index implementations.

`HashIndex`, `OrderedDateIndex`, and `CompositeIndex` provide distinct access behavior without pretending that their underlying structures have identical capabilities.

### Composite key

`RegionStatusKey` explicitly represents the two-column key.

This makes the distinction between:

`region`

and:

`region + status`

visible in the type system.

### Partial index

The `PartialIndex` stores a predicate and considers each order against that predicate.

The enterprise model therefore expresses the partial-index rule as an explicit object rather than hiding it in a query string.

### Indexing service

`IndexingService` owns the access structures and maps their candidate IDs back to immutable domain records.

This separation allows the example to demonstrate index selection independently from domain validation.

## SQL Data Model

The PostgreSQL implementation uses three main tables.

### customers

`customers` stores customer identity and segmentation.

The `email` column is unique, which allows PostgreSQL to enforce the uniqueness invariant through a unique index.

The `customer_tier` check constraint prevents unsupported tier values.

### orders

`orders` is the main indexing workload.

It contains:

- `order_id`
- `customer_id`
- `order_number`
- `status`
- `region`
- `order_date`
- `total_cents`

The table has foreign-key, uniqueness, check, and primary-key constraints.

### support_events

`support_events` provides an additional customer-linked workload and demonstrates indexing of a foreign-key relationship.

## SQL Index Design

The SQL script deliberately creates different index types for different access patterns.

### B-tree on order date

`idx_orders_order_date_btree` supports ordered date access.

It is appropriate for equality and range predicates involving `order_date`.

### Hash index on customer ID

`idx_orders_customer_hash` models PostgreSQL's hash access method.

The workload is equality-oriented:

`customer_id = 17000`

The execution plan remains authoritative because PostgreSQL can choose another path when its cost model says that path is cheaper.

### Composite B-tree

`idx_orders_region_status_date` represents a three-column access path.

The key order is:

`region -> status -> order_date`

This supports the corresponding predicate structure more directly than a suffix-only `status` predicate.

### Partial B-tree

`idx_orders_pending_date` contains only rows satisfying:

`status = 'pending'`

It is therefore specialized for operational pending-order queries.

### Covering-style index

`idx_orders_customer_date_covering` uses:

`customer_id, order_date`

as search keys and includes:

`total_cents, status`

as payload columns.

The SQL comments explain that `INCLUDE` columns are not additional ordering keys.

## Indexes Created by Constraints

Indexes are not always created manually.

Primary keys and unique constraints generally create supporting unique indexes in PostgreSQL.

The SQL script demonstrates this through the `customers.email` uniqueness rule and the table primary keys.

This distinction matters because an engineer should inspect existing indexes before creating another index that duplicates an already enforced access path.

## Transactions and Index Maintenance

The SQL script performs an insert inside a transaction and then rolls the transaction back.

The inserted row participates in the applicable index maintenance during the transaction.

When the transaction rolls back, the logical table change and its associated index changes are rolled back together.

This is important because an index cannot be treated as an independent cache that can safely diverge from the table.

## Statistics and the Query Optimizer

PostgreSQL uses statistics to estimate the number of rows matching predicates.

The SQL script runs:

`ANALYZE orders`

and queries `pg_stats` for fields such as:

- `customer_id`
- `status`
- `region`
- `order_date`

Statistics influence optimizer decisions.

If statistics are stale, the optimizer can estimate cardinality incorrectly and choose a poor plan.

This is why index analysis should include realistic data, current statistics, and actual execution plans.

## Composite Index Column Order

Consider:

`CREATE INDEX ... ON orders(region, status, order_date);`

The order is meaningful.

A query restricting `region` and `status` aligns with the first two key columns.

A query restricting `region`, `status`, and a date range can use the ordered date portion after narrowing the preceding dimensions.

A query restricting only `status` does not provide the same leading-key alignment.

This is why the index should be designed from query workload rather than from an arbitrary preference for one column over another.

## Partial Index Design

A partial index should have a predicate that corresponds to an actual workload.

The pending-order example works because the application can repeatedly ask for:

`status = 'pending'`

combined with a date condition.

A partial index becomes less useful if:

- the predicate matches a large majority of rows
- the application rarely queries that subset
- the query predicate does not imply the partial-index predicate
- the subset changes in a way that makes maintenance expensive
- a different existing index is already a better access path

The value of the partial index comes from narrowing the indexed population, not from the word "partial" itself.

## Common Indexing Mistakes

### Indexing every column

Each index consumes storage and creates maintenance work for inserts, deletes, and updates that affect indexed values.

A table with many unused indexes can become slower to write without receiving meaningful read benefits.

### Choosing a low-cardinality column blindly

A status column with four values does not automatically become a good standalone index.

If a value matches half of the table, the database may find a sequential scan cheaper.

### Ignoring data skew

Distinct-value counts do not reveal the complete distribution.

A column with four values can have a balanced distribution or a dominant value.

### Ignoring composite-column order

`(region, status)` and `(status, region)` are not interchangeable access paths.

The correct order depends on predicates, selectivity, equality conditions, range conditions, and ordering requirements.

### Creating a partial index without matching predicates

A partial index for pending rows does not directly serve a shipped-row query.

The application workload must actually target the subset.

### Measuring only query execution time

A query can be fast because data is already cached.

Index evaluation should consider execution plans, buffer behavior, realistic data volumes, concurrency, storage, write throughput, and representative workloads.

### Assuming an index will always be used

The optimizer is free to choose a sequential scan or another index when its cost model predicts a lower cost.

An index definition is an available access path, not a mandatory execution instruction.

## Query Sargability

A predicate is easier for a normal index to exploit when the database can compare the indexed column directly with a search value or range.

For example:

`order_date >= DATE '2026-01-01'`

is directly aligned with an index on `order_date`.

A transformed expression such as:

`EXTRACT(YEAR FROM order_date) = 2026`

changes the expression being evaluated.

The SQL implementation deliberately includes this query and comments on expression indexes as a possible specialized solution when the expression becomes a stable production workload.

The correct response is not to create an expression index for every function that appears in a query. The decision should follow measured workload evidence.

## Covering and Included Columns

Some database engines can answer a query using information stored in an index without visiting every corresponding table row.

PostgreSQL supports included columns through `INCLUDE`.

The SQL example uses:

`(customer_id, order_date) INCLUDE (total_cents, status)`

The search and ordering semantics come from `customer_id` and `order_date`.

The included columns provide additional payload.

Whether a query becomes an index-only scan still depends on PostgreSQL's visibility information, table changes, statistics, cost estimates, and the exact execution plan.

## Performance Considerations

An index has two broad cost dimensions.

### Read-side cost

A useful index can reduce the number of rows or pages that must be examined.

Ordered structures can also provide ordering without an additional sort when the requested order aligns with the index.

Composite indexes can reduce work when their leading columns correspond to selective predicates.

Partial indexes can reduce the physical population of an access path.

### Write-side cost

An inserted row may need to be represented in multiple indexes.

An update that changes an indexed value can require corresponding index maintenance.

A delete removes index entries.

Therefore an index should be evaluated as a read-versus-write trade-off rather than as a free optimization.

## Security and Correctness Considerations

Indexes do not replace authorization.

An index can accelerate a query but does not determine whether the requesting user is allowed to see a row.

Security predicates must remain part of the application's authorization and database access design.

Indexes can also indirectly affect information exposure through timing behavior, but ordinary index design should not be treated as an authorization mechanism.

Correctness rules that belong to the database should remain database constraints.

The SQL implementation therefore uses:

- primary keys
- unique constraints
- foreign keys
- check constraints

These prevent invalid states independently of application-level validation.

## Debugging Index Problems

When an expected index is not used, the first useful evidence is an execution plan.

In PostgreSQL, the SQL implementation uses:

`EXPLAIN (ANALYZE, BUFFERS, COSTS)`

This provides evidence about the actual execution path and resource behavior.

Useful questions include:

- Is the query actually selective?
- Are table statistics current?
- Does the predicate match the indexed columns?
- Is the composite index ordered correctly for the workload?
- Is the partial-index predicate implied by the query?
- Is the table small enough that a sequential scan is cheaper?
- Is an alternative index more useful?
- Is a sort still required?
- Is the query retrieving so many rows that random index access is expensive?
- Is a function or expression preventing ordinary index use?

The correct debugging process begins with evidence rather than with adding more indexes.

## Practical Indexing Rules Demonstrated by the Implementations

A B-tree is the broad default for ordered relational access because it supports equality, ranges, and ordered traversal.

A hash index is specialized around equality and should not be treated as a general replacement for a B-tree.

A composite index is an ordered multi-column access path, and the order of its columns is part of its behavior.

A partial index is a filtered physical access path that is most useful when its predicate corresponds to a frequent workload over a relatively small subset.

Selectivity is about how strongly a predicate narrows the relation. Distinct counts are useful evidence, but frequency distributions and real predicates provide a better picture.

Index usefulness must be demonstrated through realistic execution plans and workload measurements.

Index count should be constrained by actual read requirements because indexes also consume storage and increase write-maintenance work.

The database optimizer, not the source-code author's expectation, ultimately determines whether an available index becomes part of a particular execution plan.
