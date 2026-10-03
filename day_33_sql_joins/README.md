# SQL Joins: Relational Matching and Multi-Table Query Design

SQL joins combine rows from two or more relations according to a matching condition or, in the case of a `CROSS JOIN`, without a matching condition. They are central to relational database work because useful information is commonly distributed across normalized tables.

This project studies six join forms:

- `INNER JOIN`
- `LEFT JOIN`
- `RIGHT JOIN`
- `FULL OUTER JOIN`
- `CROSS JOIN`
- Self joins

The three implementations use the same broad relational ideas from different perspectives. Python provides a transparent executable model of join mechanics and performance. JavaScript uses `Map`, event-driven execution, asynchronous validation, and functional data transformation. C++ presents a commerce reporting case study with typed domain objects, hash indexes, optional values, composite keys, validation, and explicit data relationships.

The focus is on understanding what rows a join produces, why rows can disappear or multiply, how unmatched rows are represented, and how join choices affect data quality and query design.

## Relational Foundation

A relation can be viewed as a set or multiset of rows with named attributes. A join combines tuples from two relations when a join predicate is satisfied.

Consider two relations:

`customers(customer_id, name)`

`orders(order_id, customer_id, amount)`

The `customer_id` attribute connects the relations. A customer may have many orders, while an order normally belongs to one customer. This is a one-to-many relationship.

A join does not simply "attach one object to another." It produces rows according to matching combinations. If one customer matches three orders, that customer participates in three output rows.

This distinction becomes particularly important when an aggregation is performed after a join. An incorrectly chosen join or an unexpectedly many-to-many relationship can multiply rows and therefore distort totals.

## Join Keys and Matching

An equality join commonly has a predicate equivalent to:

`customers.customer_id = orders.customer_id`

The two columns do not need to have the same name, but their values must be compatible for the comparison.

A join key can also contain several attributes. For example:

`warehouse_id = warehouse_id AND product_id = product_id`

This is a composite-key relationship. Joining inventory only on `product_id` would be incorrect if the same product exists in multiple warehouses.

The Python implementation demonstrates composite keys using tuples. The JavaScript implementation builds a serialized compound key. The C++ implementation defines a dedicated `WarehouseProductKey` type with a custom hash function.

## INNER JOIN

An `INNER JOIN` returns only combinations for which the join condition matches.

Conceptually:

`A INNER JOIN B ON A.key = B.key`

If a customer has no matching order, that customer does not appear in the customer/order inner join.

Likewise, an order whose `customer_id` does not exist in the customer relation disappears from the result.

This makes `INNER JOIN` useful when the result should represent only relationships that exist on both sides.

The Python `inner_join()` function builds a dictionary-based index for the right relation. Importantly, the dictionary value is a list. A key can have multiple matching rows, and every valid combination must be emitted.

The JavaScript implementation uses `Map` for the same reason. The C++ implementation uses `unordered_map` where the customer key is expected to be unique.

### One-to-many multiplication

Suppose customer `1` has two orders:

`customer 1 -> order 101`

`customer 1 -> order 102`

An inner join produces two rows containing customer `1`.

This is not an implementation error. It is the expected result of relational matching.

For a general equality join, if a key occurs `m` times on the left and `n` times on the right, that key can contribute `m × n` rows to the inner join.

## LEFT JOIN

A `LEFT JOIN` preserves every row from the left relation.

Conceptually:

`A LEFT JOIN B ON A.key = B.key`

When a left row has matching right rows, those combinations are emitted normally.

When it has no matching right row, the left row still appears, while the right-side attributes become SQL `NULL`.

This makes `LEFT JOIN` appropriate when the left relation defines the population that must remain visible.

For example, a customer reporting query may need to show customers who have never placed an order. An inner join would remove them. A left join retains them.

The Python implementation explicitly creates a `None`-valued right side for an unmatched customer. The JavaScript implementation uses `null`. The C++ case study uses `std::optional<Order>` so the absence of an order is represented explicitly rather than through a fabricated `Order` object.

### Typical LEFT JOIN reporting pattern

A common requirement is:

`Show every customer and their total order value, including customers whose total is zero.`

The appropriate relational structure is a left join followed by aggregation.

The Python `customer_order_totals()` function initializes a total for every customer and adds order amounts only when an order exists.

The C++ `calculateCustomerTotals()` function performs the same business operation using typed objects and `std::optional`.

The important point is that the outer join establishes the population before the aggregation is performed.

## RIGHT JOIN

A `RIGHT JOIN` preserves every row from the right relation.

Conceptually:

`A RIGHT JOIN B ON A.key = B.key`

It is logically equivalent to reversing the inputs of a left join:

`B LEFT JOIN A ON B.key = A.key`

The Python implementation deliberately demonstrates this relationship. It performs a left join with reversed inputs and restores the original aliases in the result.

The JavaScript implementation uses the same transformation.

The C++ implementation instead makes the preservation requirement explicit by iterating over every order and looking up its customer.

A right join can therefore be useful when the right relation represents the population that must not disappear. In practice, query authors frequently rewrite a right join as a left join by changing table order because left joins are often easier to read consistently.

## FULL OUTER JOIN

A `FULL OUTER JOIN` preserves unmatched rows from both relations.

Conceptually:

`A FULL OUTER JOIN B ON A.key = B.key`

It produces:

- matching combinations
- left-only rows with right-side `NULL`
- right-only rows with left-side `NULL`

This makes a full join particularly useful for reconciliation.

In the sample commerce data, one order references customer `9`, while no customer `9` exists. A customer such as `Nisha` has no order. A full outer join exposes both conditions in the same result.

The Python implementation tracks individual right-side rows that have participated in matches. This matters when multiple rows share a join key. Tracking only the key would not be sufficient to determine which physical rows remain unmatched.

The JavaScript implementation uses a `Set` of original right-row indexes for the same reason.

The C++ implementation tracks matched order IDs in an `unordered_set`.

## CROSS JOIN

A `CROSS JOIN` does not use a matching predicate.

It produces the Cartesian product:

`A CROSS JOIN B`

If relation `A` contains `m` rows and relation `B` contains `n` rows, the result contains:

`m × n`

rows.

The Python implementation creates all customer/department combinations for the selected sample.

The JavaScript implementation uses `flatMap()` to express the same Cartesian expansion.

The C++ case study uses regions and notification types. Each region is paired with each notification policy.

A cross join should therefore be deliberate. It is appropriate when every combination has meaning, such as generating combinations of regions and notification categories for a policy matrix. It can become expensive when both input relations are large.

An accidental Cartesian product is often caused by a missing or incorrect join condition.

## Self Joins

A self join joins a relation with itself.

The table is conceptually given two roles, such as:

`employees AS employee`

and

`employees AS manager`

The relationship can then be expressed as:

`employee.manager_id = manager.employee_id`

This is useful for hierarchical data stored in a single table.

The employee relation in this project contains:

`employee_id`

`employee_name`

`manager_id`

`department`

An employee's `manager_id` points back to another employee's `employee_id`.

The Python `self_join()` function indexes the same employee collection and assigns `employee` and `manager` aliases.

The JavaScript version does the same with a `Map`.

The C++ case study represents `managerId` as `std::optional<int>`. A missing manager ID identifies a top-level employee, while a non-null ID that cannot be resolved represents a broken relationship.

Self joins can also be used for other same-table relationships, including predecessor/successor records, parent/child entities, referral relationships, and comparison of rows within the same business entity.

## NULL and Unmatched Rows

Outer joins introduce `NULL` when one side of the relationship has no corresponding row.

`NULL` is not the same as an ordinary empty string, zero, or false value.

SQL also uses three-valued logic. A comparison involving `NULL` generally produces `UNKNOWN`, rather than ordinary `TRUE` or `FALSE`.

This matters when nullable columns participate in join conditions and filters.

The Python program explicitly discusses the distinction between Python `None` and SQL `NULL`. Its dictionary-based model is intended to expose join mechanics, not to reproduce every detail of SQL's three-valued logic.

The C++ implementation uses `std::optional` to distinguish a missing relation from an existing object.

## Filtering and Outer Joins

A common outer-join error occurs when a right-side condition is applied after the join.

Suppose the intended requirement is:

`Show every customer, but only attach orders worth at least 1500.`

A conceptual approach is to restrict the eligible orders before matching.

If instead the query performs a left join and then applies:

`WHERE order.amount >= 1500`

the rows whose order side is `NULL` fail that condition. Customers without qualifying orders disappear.

The Python implementation contains both behaviors:

`filter_after_left_join()`

and

`left_join_with_right_condition()`

The distinction is not merely stylistic. It changes the population represented by the result.

The exact SQL formulation can use a predicate in the `ON` clause when the intention is to restrict matches while retaining unmatched left rows.

## Join Cardinality

Join cardinality describes how many output rows a join produces.

A one-to-one join may preserve approximately one row per matching key.

A one-to-many join expands rows on the one side.

A many-to-many join can expand output dramatically.

For a particular key:

`left occurrences × right occurrences`

determines the number of matching combinations contributed by that key.

The Python program's `cardinality_report()` calculates this relationship directly.

The JavaScript `cardinality()` function performs the same analysis using `Map` counts.

Understanding cardinality is essential when joining tables before aggregation. If an order is accidentally matched to several product records because the product key is not unique, a later `SUM(order.amount)` can count the same order multiple times.

## Composite Keys

A join key can consist of multiple attributes.

The inventory example uses:

`(warehouse, product_id)`

A request for:

`(LKO, 501)`

must match inventory for product `501` in the `LKO` warehouse, not inventory for product `501` in every warehouse.

The Python implementation represents this naturally as a tuple.

The JavaScript implementation uses a serialized compound key.

The C++ implementation introduces `WarehouseProductKey` and `WarehouseProductHash`. This illustrates an important systems-level concern: when a composite key is used in a hash index, equality and hashing must agree.

A production database can enforce composite uniqueness through a composite primary key or unique constraint. The same uniqueness assumption should be reflected in application-side indexes when correctness depends on it.

## Referential Integrity

Joins can reveal data-quality problems that database constraints are intended to prevent.

The sample data intentionally contains:

`order_id = 106`

with:

`customer_id = 9`

while no customer with ID `9` exists.

An inner join silently excludes the orphaned order from its result.

A right join or full outer join exposes it.

The Python program validates the foreign-key relationship and reports the unmatched customer ID.

The JavaScript program performs asynchronous foreign-key validation and returns the invalid IDs.

The C++ case study uses `findOrphanOrders()` to identify the affected order.

In a production relational database, a foreign key can prevent such a record from being inserted in the first place. Join-based reconciliation remains useful when importing external data, checking legacy records, or identifying relationships that were not enforced historically.

## Python Implementation

The Python file is an executable relational join laboratory.

Its central functions are:

- `inner_join()` for matching rows only
- `left_join()` for preserving the left relation
- `right_join()` implemented through reversed left-join semantics
- `full_join()` for two-sided reconciliation
- `cross_join()` for Cartesian products
- `self_join()` for relationships within one relation

The implementation uses dictionaries and lists to model indexes and duplicate matches.

It also includes:

- composite-key joins
- join cardinality analysis
- customer order aggregation
- foreign-key validation
- outer-join filter behavior
- SQL-like missing-value discussion
- nested-loop versus indexed equality joins
- a multi-table customer/order/product report

The performance demonstration contrasts a direct nested-loop implementation with an indexed equality join. The nested-loop approach performs approximately `m × n` comparisons, while a hash-indexed approach can approach linear work in the number of input rows for suitable equality joins.

This is an educational model rather than a SQL query optimizer. Actual database engines have additional choices involving indexes, statistics, memory, sorting, hash tables, merge operations, and physical execution plans.

## JavaScript Implementation

The JavaScript file approaches joins as executable data-processing operations.

`Map` is used as the primary hash-index structure. Each key maps to an array of rows so one-to-many relationships are not accidentally collapsed.

The implementation includes:

- `innerJoin()`
- `leftJoin()`
- `rightJoin()`
- `fullJoin()`
- `crossJoin()`
- `selfJoin()`
- composite-key matching
- cardinality analysis
- outer-join filtering behavior
- aggregation
- referential-integrity validation

It also demonstrates JavaScript-specific execution patterns.

The `JoinWorkflow` class extends `EventTarget` and emits `join:start`, `join:complete`, and `join:error` events. This models a join as a component inside an event-driven data-processing pipeline.

`validateForeignKeysAsync()` uses asynchronous execution without requiring an external dependency. In a real application, the same boundary could surround an asynchronous database or API request.

The use of `flatMap()` in the cross join emphasizes that every left-side item produces a collection of right-side combinations.

## C++ Case Study

The C++ program models a commerce reporting engine using strongly typed structures.

Its domain entities include:

`Customer`

`Order`

`Product`

`Employee`

`Region`

The join engine is designed around concrete business operations rather than isolated language syntax.

The customer/order case demonstrates all three common relationship states:

- an order with a valid customer
- a customer with no orders
- an order whose customer reference is invalid

The full join therefore acts as a reconciliation mechanism.

The employee case demonstrates a self join where `managerId` references another `Employee`.

The inventory case demonstrates why composite business identity matters. The `(warehouse, productId)` pair is represented as a dedicated C++ type and used in an `unordered_map`.

The program uses `std::optional` to represent the absence of an outer-join match. This is preferable to inventing an object with fake values because the distinction between "no related row" and "a real row whose values happen to be empty" is significant.

The three-table report demonstrates a sequence of joins:

`customers -> orders -> products`

The aggregation stage then calculates customer order totals while retaining customers who have no orders.

## Join Comparison

| Join | Matching rows | Unmatched left rows | Unmatched right rows | Typical purpose |
|---|---|---|---|---|
| `INNER JOIN` | Yes | Removed | Removed | Work only with established relationships |
| `LEFT JOIN` | Yes | Preserved | Right side becomes `NULL` | Preserve a complete left-side population |
| `RIGHT JOIN` | Yes | Left side becomes `NULL` | Preserved | Preserve a complete right-side population |
| `FULL OUTER JOIN` | Yes | Preserved | Preserved | Reconciliation and gap detection |
| `CROSS JOIN` | No predicate | All combinations | All combinations | Explicit Cartesian combinations |
| Self join | Depends on predicate | Depends on join type | Depends on join type | Hierarchies and same-table relationships |

`RIGHT JOIN` and `LEFT JOIN` are structurally symmetric. The important distinction is which relation is preserved.

A self join is not a separate mathematical join algorithm. It is a join in which both logical inputs originate from the same relation.

## Join Strategy and Performance

The simplest implementation of an equality join compares every left row with every right row.

For `m` left rows and `n` right rows, this nested-loop strategy has:

`O(m × n)`

comparison complexity.

The Python program implements this directly as `nested_loop_inner_join()`.

An indexed equality join can build a hash table keyed by the join attribute and then probe it for each left row. Under suitable assumptions, expected work approaches:

`O(m + n)`

with additional memory required for the index.

The Python dictionary, JavaScript `Map`, and C++ `unordered_map` implementations demonstrate this general technique.

This does not mean a database always chooses a hash join. A database optimizer may select among nested-loop joins, index-assisted nested loops, hash joins, merge joins, or other strategies based on relation sizes, indexes, statistics, sorting, available memory, and estimated selectivity.

## Performance Implications of Each Join

`INNER JOIN` can often be selective because unmatched rows are discarded.

`LEFT JOIN` must preserve the left population, so the execution strategy must account for left-side rows without matches.

`FULL OUTER JOIN` has additional work because unmatched rows from both inputs must be retained.

`CROSS JOIN` inherently produces a Cartesian product and therefore has potentially quadratic output growth when both sides grow together.

Self joins can become expensive when a table is large, especially when the relationship produces many matches.

Many-to-many joins deserve particular attention because output size can be substantially larger than either input relation.

## Common Failure Modes

### Accidental Cartesian products

A missing join predicate can produce a Cartesian product when the intended query was a relationship join.

The result can contain vastly more rows than expected and can create incorrect aggregates.

### Joining on an incomplete key

Joining inventory only on `product_id` when warehouse identity is also required can associate a request with the wrong physical inventory record.

### Losing unmatched rows

Replacing a required left join with an inner join removes entities without related records.

This is particularly common in reports that are supposed to include inactive customers, departments without employees, or products without sales.

### Filtering the nullable side incorrectly

A `WHERE` predicate on a right-side column after a left join can remove the NULL-extended rows and change the effective population.

### Ignoring duplicate keys

If a supposedly unique relation contains duplicates, a join can multiply rows unexpectedly.

Application-side indexes that map a key to a single row can also silently discard matches if uniqueness was assumed incorrectly.

### Aggregating after an unintended many-to-many join

A sum, count, or average calculated after row multiplication can produce incorrect business metrics.

The correct solution is often to verify relationship cardinality and aggregate at the appropriate relational level.

### Treating NULL as an ordinary value

SQL `NULL` represents missing or unknown information and follows three-valued logic. It should not be treated as equivalent to zero, an empty string, or a normal key value.

## Data Modeling and Join Design

Good join behavior depends heavily on data modeling.

Primary keys provide stable row identity.

Foreign keys express relationships between relations.

Unique constraints establish assumptions that affect join cardinality.

Composite keys identify entities whose identity depends on multiple attributes.

Indexes can make frequently executed equality joins substantially more efficient.

Normalization commonly separates customers, orders, products, employees, and other entities into distinct relations. Joins then reconstruct the related information required by a report or application operation.

Denormalization can reduce some join requirements but introduces other concerns such as duplicated information and update consistency. Join design therefore cannot be separated completely from schema design.

## Debugging Join Results

When a join returns an unexpected number of rows, inspect the relationship before changing the query.

Useful checks include:

- Count rows in each input relation.
- Count distinct join-key values.
- Identify duplicate key values.
- Find left-only keys.
- Find right-only keys.
- Calculate expected one-to-one, one-to-many, or many-to-many cardinality.
- Inspect rows where an outer join produced `NULL`.
- Check whether a filter is applied before or after the join.
- Verify that every component of a composite key participates in the predicate.
- Compare the joined row count with a deliberately small known dataset.

The Python cardinality report and the C++ orphan-order validation provide executable versions of several of these checks.

## Security and Operational Considerations

Joins themselves are not an authorization mechanism.

A query that correctly joins customer and order data can still expose records to an unauthorized user if application-level access rules are missing.

When SQL is constructed dynamically, join logic should be parameterized rather than assembled through unsafe string concatenation. User-controlled values should not be inserted directly into SQL syntax.

Large cross joins and uncontrolled many-to-many joins can create denial-of-service-like resource consumption through excessive CPU, memory, temporary storage, or network transfer.

Production systems should therefore consider query limits, appropriate indexes, execution plans, statistics, pagination where suitable, and access controls around sensitive relations.

## Practical Relationship Between the Join Types

The join types answer different population questions.

An inner join asks:

`Which combinations exist on both sides?`

A left join asks:

`What does the complete left population look like when related information is attached where available?`

A right join asks the equivalent question with the right population preserved.

A full outer join asks:

`Which relationships exist, and which records appear only on one side?`

A cross join asks:

`What are all possible combinations between these two relations?`

A self join asks:

`How are rows within this relation related to other rows in the same relation?`

These questions are related, but they are not interchangeable. Selecting the correct join depends on which rows the result is required to preserve and what relationship the data model actually represents.
