# SQL Fundamentals: SELECT, INSERT, UPDATE, DELETE, WHERE, ORDER BY, GROUP BY

## Scope

This repository studies the core SQL operations used to read, create, modify, remove, filter, sort, and aggregate relational data:

- `SELECT` retrieves data and controls which columns appear in a result.
- `INSERT` creates new rows.
- `UPDATE` changes existing rows.
- `DELETE` removes existing rows.
- `WHERE` restricts which source rows participate in a read or modification.
- `ORDER BY` determines result ordering.
- `GROUP BY` transforms individual rows into groups that can be summarized with aggregate functions.

The three implementations use deliberately different approaches. The Python program executes real SQL against SQLite. The JavaScript program builds a JavaScript-side relational model and focuses on query reasoning, validation, asynchronous execution, and transaction-style state management. The C++ program presents a strongly typed commerce data model in which SQL operations are represented by C++ algorithms, predicates, collections, and integrity checks.

The central distinction is that these operations have different responsibilities. `WHERE` decides which rows qualify. `ORDER BY` decides the sequence of an already selected result. `GROUP BY` changes the shape of the data by forming groups for aggregation. `INSERT`, `UPDATE`, and `DELETE` modify stored state, while `SELECT` is primarily a read operation.

---

## Relational Case Study

The implementations use a small commerce system containing:

- `customers` for customer identity, city, and business segment.
- `products` for product names, categories, prices, and inventory.
- `orders` for customer orders, dates, and order status.
- `order_items` for the products and quantities belonging to each order.

The relationships are:

    customers
        |
        | customer_id
        v
      orders
        |
        | order_id
        v
    order_items
        |
        | product_id
        v
     products

This structure makes the fundamentals concrete. A customer can have multiple orders. An order can contain multiple products through `order_items`. A product can appear in many order items.

The design also creates realistic reporting questions. A system can ask which customers live in Lucknow, which products cost at least a particular amount, which orders are newest, how many orders exist for each status, or how much completed sales value belongs to each product category.

---

## SELECT

`SELECT` retrieves rows from one or more tables and determines the columns returned to the caller.

A basic query is:

    SELECT customer_id, name, city
    FROM customers;

The database does not need to return every stored column. This is called projection: the query chooses the attributes required by the result.

Aliases can make reports easier to consume:

    SELECT
        name AS customer,
        segment AS customer_segment
    FROM customers;

`DISTINCT` removes duplicate result values:

    SELECT DISTINCT city
    FROM customers;

The important distinction is that `SELECT` describes the requested result. It does not, by itself, modify the underlying rows.

The Python implementation executes these statements against SQLite and prints their actual result sets. The JavaScript implementation uses `selectRows()` as a projection mechanism and separates projection from filtering and sorting. The C++ implementation uses a templated predicate-based selection method that returns copies of matching product records.

---

## INSERT

`INSERT` adds rows to a table.

A single-row insertion has the form:

    INSERT INTO customers (customer_id, name, city, segment)
    VALUES (?, ?, ?, ?);

The Python program uses SQLite parameter binding for the values. This prevents application data from being interpreted as SQL syntax.

The commerce model also demonstrates why validation matters before insertion. A customer must have a valid segment, a product cannot have a negative price or negative stock, and identifiers must satisfy the model's uniqueness rules.

A multi-row insertion can be performed efficiently with repeated parameterized executions rather than constructing SQL text from untrusted values.

The JavaScript implementation makes these constraints explicit through `validateCustomer()` and `validateProduct()`. The C++ implementation performs equivalent validation through typed domain methods before modifying its vectors.

`INSERT` therefore has two separate concerns:

- Construct a new valid row.
- Preserve the integrity rules that make the row meaningful within the database.

---

## UPDATE

`UPDATE` modifies existing rows.

For example:

    UPDATE products
    SET stock = stock + 10
    WHERE category = 'Accessories'
      AND stock < 30;

The `WHERE` clause is critical. Without it, every row in `products` would be eligible for the update.

An update can also calculate a new value from the old value. `stock = stock + 10` does not require the application to first retrieve the stock, calculate it in application code, and then write it back.

The Python program demonstrates this pattern directly against SQLite and checks the number of affected rows. The JavaScript implementation uses `updateProducts()` with a predicate and validates the candidate product state before committing it to the in-memory model. The C++ implementation constructs a proposed `Product` object, validates it, and only then replaces the existing object.

This separation is important in production systems. A modification should be narrowly scoped and should have explicit expectations about how many rows it is allowed to affect.

---

## DELETE

`DELETE` removes rows.

A precise deletion looks like:

    DELETE FROM customers
    WHERE customer_id = ?;

A missing `WHERE` clause has a radically different effect:

    DELETE FROM customers;

That statement makes every row in the table eligible for deletion.

The examples intentionally avoid destructive deletion of important historical records. Instead, they demonstrate a temporary customer and a referential-integrity failure when an attempt is made to delete a product that is referenced by order items.

This illustrates an important relational principle: deletion is not simply removal from a collection. Relationships between tables can impose constraints on whether a row may be removed.

The Python schema uses a foreign key from `order_items.product_id` to `products.product_id`. The C++ case study explicitly checks for dependent order items before permitting product deletion.

---

## WHERE

`WHERE` determines which rows qualify for a query or data modification.

Common predicates include:

    WHERE city = 'Lucknow'

    WHERE unit_price >= 4000

    WHERE segment IN ('Business', 'Enterprise')

    WHERE unit_price BETWEEN 3000 AND 8000

    WHERE name LIKE '%a%'

Multiple predicates can be combined:

    WHERE city = 'Lucknow'
      AND segment IN ('Consumer', 'Business');

`AND` requires both conditions to be true. `OR` allows either condition to be true. Parentheses should be used when a condition mixes `AND` and `OR` and the intended precedence needs to be explicit.

`IN` is useful when a value is compared against a finite set. `BETWEEN` expresses an inclusive range in standard SQL. `LIKE` performs pattern matching, with `%` representing an arbitrary sequence of characters in the common SQL pattern syntax.

`NULL` requires special treatment. A predicate such as:

    WHERE city = NULL

does not test for a null value correctly. SQL uses three-valued logic, so null represents an unknown or absent value rather than an ordinary value. The correct form is:

    WHERE city IS NULL

and:

    WHERE city IS NOT NULL

The Python program explicitly demonstrates `IS NULL`, while the JavaScript model shows the corresponding `null` comparison in JavaScript.

`WHERE` has another critical role: it applies to data-changing statements as well as reads. A careless `UPDATE` or `DELETE` can therefore be more damaging than a poorly filtered `SELECT`.

---

## ORDER BY

`ORDER BY` controls the order of rows in the result.

For descending product price:

    SELECT name, unit_price
    FROM products
    ORDER BY unit_price DESC;

Multiple sort keys establish deterministic ordering:

    ORDER BY unit_price DESC, name ASC;

The database first compares `unit_price`. When two products have the same price, `name` provides the secondary ordering.

Ordering is different from filtering. `WHERE` determines which rows are present. `ORDER BY` determines how those rows are arranged.

The Python program uses both primary and secondary ordering and demonstrates `LIMIT` for a small recent-orders result. The JavaScript implementation uses comparator functions such as `ascending()` and `descending()`. The C++ program uses `std::sort()` with explicit tie-breaking by product name.

A production application should avoid assuming that rows have a meaningful natural order when no `ORDER BY` clause is specified. If a stable presentation order matters, the query should state it explicitly.

---

## GROUP BY

`GROUP BY` changes the shape of a result by collecting rows with equal grouping values.

For example:

    SELECT
        status,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY status;

The individual orders are no longer presented as one row per order. Instead, the query produces one result row for each distinct status.

Aggregate functions make grouping useful:

- `COUNT()` counts rows.
- `SUM()` adds numeric values.
- `AVG()` calculates an average.
- `MIN()` finds the smallest value.
- `MAX()` finds the largest value.

A sales report can group order items by product category:

    SELECT
        p.category,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.quantity * oi.unit_price) AS gross_value
    FROM order_items AS oi
    JOIN products AS p
        ON p.product_id = oi.product_id
    JOIN orders AS o
        ON o.order_id = oi.order_id
    WHERE o.status IN ('Paid', 'Shipped')
    GROUP BY p.category
    ORDER BY gross_value DESC;

This query demonstrates a useful relationship between the fundamental clauses.

`WHERE` removes cancelled and pending orders before aggregation. `GROUP BY` then forms category groups. `SUM()` calculates values inside those groups. `ORDER BY` sorts the resulting category report.

The Python implementation executes this type of report directly in SQLite. The JavaScript implementation creates groups using `Map` and calculates aggregate values from each group. The C++ implementation uses `std::map` to accumulate category totals.

---

## WHERE Versus HAVING

`WHERE` and `HAVING` are not interchangeable.

`WHERE` filters source rows before grouping. `HAVING` filters groups after aggregation.

For example:

    SELECT
        p.category,
        SUM(oi.quantity) AS units_sold
    FROM order_items AS oi
    JOIN products AS p
        ON p.product_id = oi.product_id
    GROUP BY p.category
    HAVING SUM(oi.quantity) >= 3;

A condition on an individual source row generally belongs in `WHERE`. A condition on an aggregate result generally belongs in `HAVING`.

The Python program demonstrates `HAVING` through a minimum unit threshold. The JavaScript implementation explicitly labels its equivalent operation as a post-group filtering stage. This distinction matters because moving an aggregate condition into an earlier filtering stage can change the meaning of the report.

---

## Query Processing Relationship

A useful conceptual model for a grouped query is:

    FROM / JOIN
        |
        v
    WHERE
        |
        v
    GROUP BY
        |
        v
    aggregate calculations
        |
        v
    HAVING
        |
        v
    SELECT
        |
        v
    ORDER BY
        |
        v
    final result

This is a conceptual processing model rather than a claim about the exact internal execution plan used by every database engine.

It explains why SQL clauses have different responsibilities. A query that filters cancelled orders before calculating sales is different from a query that calculates totals first and attempts to remove cancelled data later.

Database optimizers may transform the physical execution plan while preserving the logical result defined by the SQL statement.

---

## Python Implementation

The Python file uses the standard-library `sqlite3` module, so it can execute real SQL without a third-party dependency.

The database schema contains primary keys, foreign keys, `CHECK` constraints, `NOT NULL` requirements, unique product names, and indexes.

The program demonstrates:

- Real `SELECT` statements against SQLite.
- Parameterized `INSERT` statements.
- Predicate-scoped `UPDATE` statements.
- Controlled `DELETE` behavior.
- `WHERE` predicates using equality, ranges, membership, and pattern matching.
- `ORDER BY` with multiple sort keys.
- `GROUP BY` with `COUNT()` and `SUM()`.
- `HAVING` on aggregate results.
- Joins between customers, orders, order items, and products.
- Parameter binding for safe values.
- Transaction rollback after an intentional foreign-key failure.
- Database-level validation through `CHECK` constraints.
- A query plan inspection using `EXPLAIN QUERY PLAN`.
- Safe dynamic ordering through a whitelist rather than arbitrary SQL identifier interpolation.
- Foreign-key cascade behavior for dependent order items.

The default database is in memory, which keeps the demonstration self-contained and prevents an execution from unexpectedly leaving a database file behind. The script contains an explicit switch for persistent local storage when database inspection is desired.

The transaction helper uses `BEGIN`, `COMMIT`, and `ROLLBACK`. The failed transaction demonstrates that a successful earlier statement does not necessarily mean the complete business operation should be committed.

---

## JavaScript Implementation

The JavaScript file does not simply reproduce the Python SQL strings. It implements the relational concepts as JavaScript operations.

Its core structures are arrays of typed-looking records representing customers, products, orders, and order items.

`selectRows()` represents projection. `where()` represents predicate-based filtering. `orderBy()` accepts comparator functions, making the sorting mechanism natural to JavaScript. `groupBy()` uses `Map`, which provides a direct representation of groups keyed by category or status.

The program also includes validation functions for customers, products, and orders. This is important because an application-side representation still needs domain constraints even when the actual production database would enforce them again.

The JavaScript implementation demonstrates a join-like traversal for customer sales reporting. It follows customer-to-order and order-to-item relationships rather than pretending that unrelated arrays automatically form a relational result.

The asynchronous example uses `Promise` and `setImmediate()` to model the boundary encountered when a Node.js application calls an asynchronous database driver.

The transaction example uses a cloned working state. Changes are applied to the working copy and only become authoritative if all validation steps succeed. The intentionally invalid referenced order causes the operation to roll back.

Dynamic sorting is handled through a fixed mapping:

    {
        name: ...,
        price: ...,
        stock: ...
    }

This reflects an important SQL application rule. Query parameters are appropriate for values, but they do not normally turn arbitrary user input into a column identifier. If a user interface offers a finite list of sort choices, the application should map those choices to trusted SQL expressions or trusted query-builder constructs.

---

## C++ Case Study

The C++ implementation models a commerce database as a strongly typed `SalesDatabase`.

Its containers are:

- `std::vector<Customer>` for customer rows.
- `std::vector<Product>` for product rows.
- `std::vector<Order>` for orders.
- `std::vector<OrderItem>` for order lines.

The class validates records before insertion. Primary-key-like uniqueness is checked explicitly, while foreign-key relationships are verified when orders and order items are inserted.

The `selectProducts()` method accepts a predicate. This corresponds to the row-selection role of a SQL `WHERE` clause while returning a separate result collection.

`updateProducts()` constructs a candidate product state before replacing the stored record. This makes the validation boundary explicit and avoids partially updating an invalid object.

`deleteProduct()` checks for dependent order items before removing a product. The case study therefore treats historical order data as a relational dependency rather than as unrelated collections.

`groupSalesByCategory()` uses a `std::map` keyed by product category. Each qualifying order item contributes quantity and monetary value to its category. Cancelled and pending orders are skipped before aggregation, matching the logical role of `WHERE` before `GROUP BY`.

`customerSalesReport()` performs a multi-table reporting operation. It traverses completed orders, finds their customers, accumulates order identifiers and sales values, applies a minimum-value threshold, and sorts the resulting report by sales value.

The case study therefore demonstrates how SQL's relational operations can be understood as general data-processing concepts even when the final implementation uses a different programming language and storage abstraction.

---

## Aggregate Reporting

The sales data makes `GROUP BY` more useful than a simple count.

For a category report, each order item contributes:

    units = quantity

    value = quantity * unit_price

Grouping those rows by category gives a business-level view rather than an order-line-level view.

The calculation also demonstrates why historical line-item prices are useful. The `order_items` table stores `unit_price` separately from the current `products.unit_price`. If the product price changes later, historical sales should not silently change because a current catalog price was substituted for the price actually recorded on the order.

That design decision is directly related to reporting correctness. Aggregation is only meaningful when the underlying rows represent the intended business event.

---

## Data Modification Safety

`SELECT` mistakes are usually visible as incorrect result sets. `UPDATE` and `DELETE` mistakes can alter stored information.

A practical safety pattern is to develop the predicate as a `SELECT` first:

    SELECT product_id, name, stock
    FROM products
    WHERE category = 'Accessories'
      AND stock < 30;

After verifying the target rows, the same predicate can be used in an update:

    UPDATE products
    SET stock = stock + 10
    WHERE category = 'Accessories'
      AND stock < 30;

For particularly sensitive operations, the application can also verify the affected-row count. The Python implementation demonstrates this with an expected single-row product update.

Transactions provide a second layer of protection when multiple modifications belong to one business operation.

---

## Parameterized Queries

Values supplied by an application should be bound as parameters rather than concatenated into SQL text.

Unsafe construction conceptually looks like:

    SELECT *
    FROM customers
    WHERE name = '...user input...';

when the application builds the complete SQL string by concatenation.

A malicious value can then change the structure of the SQL statement.

The safe form uses a placeholder:

    SELECT customer_id, name
    FROM customers
    WHERE name = ?;

The database driver receives the SQL structure separately from the value.

The Python implementation demonstrates this directly with SQLite parameters. The JavaScript implementation explains the same boundary when it models interactive filtering. The C++ implementation does not construct SQL strings at all, which removes SQL string-injection concerns from that particular in-memory layer, although a real C++ application using a database driver would still need parameter binding.

Parameterization does not eliminate every security problem. Applications still need authorization, input validation, appropriate database permissions, safe handling of credentials, and careful control over dynamically constructed identifiers or clauses.

---

## Transactions

A transaction groups changes into a unit of work.

A typical inventory operation may involve:

- reducing product stock;
- creating an order;
- creating order items;
- recording a payment or order state.

If a later operation fails after an earlier modification has succeeded, committing only the earlier modification can leave inconsistent business state.

The Python program intentionally performs a stock update followed by an invalid order-item insertion. SQLite rejects the foreign-key reference, and the transaction rolls back the preceding stock change.

The JavaScript program models the same atomicity idea with a working copy. The C++ implementation concentrates on validation and object-state integrity rather than attempting to emulate a full database transaction engine.

A real database remains responsible for transaction isolation, durability, locking behavior, crash recovery, and other storage-engine concerns.

---

## Constraints and Data Quality

SQL fundamentals are not limited to writing clauses. Correct query results depend on the quality of the stored data.

The Python schema demonstrates:

    PRIMARY KEY
    NOT NULL
    UNIQUE
    CHECK
    FOREIGN KEY

For example, product stock is constrained to non-negative values:

    CHECK (stock >= 0)

Customer segments are constrained to a defined set:

    CHECK (segment IN ('Consumer', 'Business', 'Enterprise'))

Foreign keys prevent references to missing parent rows when foreign-key enforcement is enabled.

Application validation and database constraints serve different roles. Application validation can produce immediate, user-friendly errors. Database constraints protect the stored data even if another application, script, migration, or administrative process writes to the database.

A production system should not assume that application-level checks alone are sufficient.

---

## Performance Considerations

A basic SQL query can be logically correct while still performing poorly on a large dataset.

The Python schema includes indexes for common lookup paths such as:

- customer references in orders;
- order status;
- order date;
- product references in order items;
- customer city.

Indexes can make selective searches faster because the database can avoid scanning every row. They are not free. Indexes consume storage and can increase the work required by `INSERT`, `UPDATE`, and `DELETE`.

The Python implementation uses `EXPLAIN QUERY PLAN` to expose SQLite's chosen strategy for an indexed lookup.

`ORDER BY` can also have performance implications, particularly when the database must sort a large intermediate result. Grouping and aggregation can require substantial work when the source tables contain many rows.

Performance should therefore be evaluated against realistic data volumes rather than inferred solely from a small development dataset.

---

## Common Mistakes

### Omitting WHERE from UPDATE

    UPDATE products
    SET unit_price = 1000;

This makes every product eligible for the change.

A scoped update should state its intended predicate explicitly.

### Omitting WHERE from DELETE

    DELETE FROM orders;

This makes every order eligible for deletion.

A deletion should be treated as a high-risk data modification, particularly when historical data is involved.

### Using = with NULL

    WHERE city = NULL

does not correctly test for SQL null values. Use `IS NULL` or `IS NOT NULL`.

### Confusing WHERE and HAVING

A row-level condition belongs naturally in `WHERE`. A condition involving an aggregate such as `SUM()` generally belongs in `HAVING`.

### Assuming natural row order

Without `ORDER BY`, an application should not depend on a particular row sequence.

### Sorting without a tie-breaker

If two rows have equal primary sort values, adding a secondary key can make presentation deterministic.

### Concatenating user input into SQL

Values should be bound as parameters. Arbitrary user input should not become executable SQL syntax.

### Updating from a stale read

Reading a value, calculating a replacement in application code, and then writing it back can create race conditions in concurrent applications. Database-side expressions and appropriate transactions can reduce this risk.

### Treating current product price as historical order price

Sales records should preserve the price associated with the transaction when historical financial reporting depends on it.

---

## Practical SQL Patterns

### Filter products by price

    SELECT product_id, name, unit_price
    FROM products
    WHERE unit_price >= 4000
    ORDER BY unit_price DESC;

### Find customers in selected segments

    SELECT customer_id, name, city, segment
    FROM customers
    WHERE city = 'Lucknow'
      AND segment IN ('Consumer', 'Business')
    ORDER BY name ASC;

### Count orders by status

    SELECT status, COUNT(*) AS order_count
    FROM orders
    GROUP BY status
    ORDER BY order_count DESC;

### Calculate category sales

    SELECT
        p.category,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.quantity * oi.unit_price) AS sales_value
    FROM order_items AS oi
    JOIN products AS p
        ON p.product_id = oi.product_id
    JOIN orders AS o
        ON o.order_id = oi.order_id
    WHERE o.status IN ('Paid', 'Shipped')
    GROUP BY p.category
    HAVING SUM(oi.quantity) >= 2
    ORDER BY sales_value DESC;

### Increase inventory for a narrow target

    UPDATE products
    SET stock = stock + 10
    WHERE category = 'Accessories'
      AND stock < 30;

### Remove a specifically identified temporary record

    DELETE FROM customers
    WHERE customer_id = 99;

These patterns show how the clauses interact without treating them as interchangeable.

---

## Operational Boundaries

SQL syntax alone does not define the complete behavior of a production data system.

A production implementation also needs decisions about:

- transaction boundaries;
- concurrent modifications;
- database isolation;
- user authorization;
- connection management;
- migration strategy;
- backup and recovery;
- auditing of sensitive data changes;
- index maintenance;
- query monitoring;
- error reporting;
- retention requirements.

The educational implementations deliberately keep those concerns small enough to inspect while still showing where the boundaries occur.

The Python program reaches closest to a real database because it executes SQLite SQL. The JavaScript and C++ programs expose the underlying relational reasoning without requiring external database drivers.

---

## File Relationship

The three source files are complementary rather than copies.

| File | Primary technical perspective |
| --- | --- |
| Python | Executes real SQL with SQLite, transactions, constraints, parameters, joins, grouping, and query-plan inspection |
| JavaScript | Models relational operations with arrays, predicates, `Map`, comparator functions, promises, validation, and transaction-style state snapshots |
| C++ | Implements a strongly typed commerce data model with vectors, predicates, maps, sets, validation, referential checks, aggregation, and sorting |

The same commerce scenario appears across the files so that the SQL concepts remain comparable, but each implementation emphasizes mechanisms native to its language.

---

## Technical Distinctions

`SELECT` answers the question: which data should the result contain?

`INSERT` answers: which new row should be created?

`UPDATE` answers: which existing rows should change, and what should their new values be?

`DELETE` answers: which existing rows should be removed?

`WHERE` answers: which rows qualify?

`ORDER BY` answers: in what sequence should qualifying result rows appear?

`GROUP BY` answers: which rows belong to the same aggregate group?

The clauses become particularly powerful when combined. A reporting query can first restrict source rows with `WHERE`, group the remaining rows with `GROUP BY`, calculate aggregates, remove groups with `HAVING`, and then order the final report with `ORDER BY`.

Understanding those distinct responsibilities is more important than memorizing isolated query forms because real SQL work normally combines several of these mechanisms in a single statement.
