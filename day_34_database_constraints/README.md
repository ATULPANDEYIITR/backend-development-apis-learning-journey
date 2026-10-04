# Database Constraints: PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK, DEFAULT

## Purpose

Database constraints are declarative rules that restrict which states a relational database is allowed to store. They move important integrity guarantees from application code into the data model.

This repository presents six fundamental constraints through a coherent commerce scenario:

- `PRIMARY KEY` identifies rows and prevents duplicate primary-key values.
- `FOREIGN KEY` preserves relationships between parent and child tables.
- `UNIQUE` prevents duplicate values in a column or column combination that must remain distinct.
- `NOT NULL` prevents required attributes from being absent.
- `CHECK` restricts values according to a domain rule.
- `DEFAULT` supplies a value when an insert does not provide one.

The implementations use the same general relational scenario while approaching it differently. The Python program uses SQLite to demonstrate actual SQL enforcement. The JavaScript program models constraint enforcement explicitly with JavaScript collections, indexes, events, and transaction snapshots. The C++ program presents a typed repository-style case study in which constraints become application-level invariants.

## Relational Scenario

The system represents a small commerce platform containing customers, products, orders, and order items.

The logical relationships are:

    customers
        |
        | customer_id
        v
    orders
        |
        | order_id
        v
    order_items
        ^
        |
    product_id
        |
    products

A customer can have many orders. An order can contain many products. The `order_items` relationship connects orders to products and stores relationship-specific information such as quantity and the price captured for that order.

This structure gives each constraint a distinct responsibility instead of using constraints interchangeably.

## PRIMARY KEY

A `PRIMARY KEY` identifies a row within a table.

In the Python schema, `customers.customer_id`, `products.product_id`, and `orders.order_id` are primary keys. The database generates identifiers when the caller does not provide one.

The `order_items` table demonstrates a different design:

`PRIMARY KEY (order_id, product_id)`

This is a composite primary key. It means the same product cannot occur twice as separate rows within the same order. A quantity of two belongs to one order-item row rather than requiring two identical relationship rows.

A primary key provides identity and uniqueness together. It is different from a business-oriented `UNIQUE` constraint because the primary key represents the table's chosen row identity, while another unique constraint can enforce uniqueness for a separate business attribute.

The JavaScript implementation represents the composite key as a compound string such as `orderId:productId`. The C++ implementation uses a dedicated `CompositeKey` structure with a custom hash function so the relationship can be stored efficiently in an `unordered_map`.

### Important primary-key properties

A primary key should identify one logical row unambiguously.

A primary-key value cannot be duplicated.

A primary-key column is implicitly non-null in the relational model.

A composite primary key uses the combination of participating columns as the identity rather than treating either column independently as the complete identity.

## FOREIGN KEY

A `FOREIGN KEY` establishes a relationship between a child table and a referenced parent key.

The Python order table contains:

`FOREIGN KEY (customer_id) REFERENCES customers(customer_id)`

This means an order cannot refer to customer ID `999999` when that customer does not exist.

The order-item table contains two foreign keys:

`order_id -> orders.order_id`

and

`product_id -> products.product_id`

These relationships prevent orphaned order items.

Foreign-key enforcement is especially important because application code can contain race conditions, bugs, incomplete validation, or multiple entry points. A database constraint provides a lower-level integrity boundary.

SQLite requires foreign-key enforcement to be explicitly enabled for a connection. The Python program therefore executes `PRAGMA foreign_keys = ON`. Without that setting, foreign-key behavior would not provide the intended protection.

### Parent and child behavior

The Python schema uses `ON DELETE RESTRICT` for customer-to-order and product-to-order-item relationships.

A referenced customer therefore cannot simply be deleted while an order still depends on it.

The order-to-order-item relationship uses `ON DELETE CASCADE`. Deleting an order can therefore remove its dependent order-item rows automatically.

These actions are part of foreign-key behavior, not separate definitions of the foreign key itself. The chosen action determines what happens when a referenced parent row changes or is deleted.

## UNIQUE

A `UNIQUE` constraint prevents duplicate values for a constrained key.

The customer table declares email as unique:

`email TEXT NOT NULL UNIQUE`

The product table declares SKU as unique:

`sku TEXT NOT NULL UNIQUE`

These are business identifiers rather than the table's internal primary keys.

Two customers may not share the same email, and two products may not share the same SKU.

The distinction from `PRIMARY KEY` is important. A table can have one primary key but can have multiple unique constraints for different business rules.

The JavaScript implementation makes the indexing role visible through `customerEmailIndex` and `productSkuIndex`. This illustrates why uniqueness checking can be implemented efficiently using a lookup structure rather than scanning every record.

A real relational database normally maintains the required index structures internally when enforcing unique keys.

## NOT NULL

`NOT NULL` means a column must receive a value rather than SQL `NULL`.

The customer table requires:

-  email 
-  full name 
-  age 
-  status 

The product table requires:

-  SKU 
-  name 
-  price 
-  stock 

`NOT NULL` does not mean that every possible value is valid.

For example, an empty string may still be a non-null value. A negative price is also non-null. If the business rule is that price must be positive, `CHECK (price > 0)` is needed in addition to `NOT NULL`.

This distinction is fundamental:

`NOT NULL` answers whether a value may be absent.

`CHECK` answers whether a supplied value satisfies a domain rule.

## CHECK

`CHECK` expresses a condition that values must satisfy.

The Python schema contains rules such as:

`CHECK (age >= 18)`

`CHECK (price > 0)`

`CHECK (stock >= 0)`

`CHECK (quantity > 0)`

It also constrains controlled status values:

`CHECK (status IN ('active', 'suspended'))`

These constraints turn business-domain assumptions into database-enforced conditions.

For example, application code might accidentally attempt to store a product with a negative stock value. The `CHECK` constraint prevents that invalid state from being committed.

The JavaScript and C++ implementations reproduce these domain checks at their repository boundaries. This is not a claim that application validation replaces a real database constraint. Instead, it shows how the same invariant can be represented in an application layer while the database remains the authoritative persistence boundary in a production architecture.

### Designing CHECK expressions

A useful `CHECK` expression should describe a stable domain invariant.

Good examples include:

-  quantity must be positive 
-  price must be greater than zero 
-  stock cannot be negative 
-  age must meet a minimum requirement 
-  status must belong to an allowed state set 

A `CHECK` should not be used as a substitute for a relationship constraint. If validity depends on whether another table contains a row, a `FOREIGN KEY` is the appropriate relational mechanism.

## DEFAULT

A `DEFAULT` supplies a value when an insert does not explicitly provide one.

The customer table uses:

`status TEXT NOT NULL DEFAULT 'active'`

The product table uses:

`stock INTEGER NOT NULL DEFAULT 0`

The order table uses:

`order_status TEXT NOT NULL DEFAULT 'pending'`

and:

`created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Defaults are useful when the database has a natural value for a field and the caller does not need to specify that value every time.

A default does not validate arbitrary values supplied by the caller. If a caller explicitly provides an invalid status, the `CHECK` constraint still has to reject it.

This is why the constraints work together rather than replacing each other.

## Constraint Interaction

The six constraints solve different integrity problems.

| Constraint    | Main responsibility          | Commerce example                  |
| ------------- | ---------------------------- | --------------------------------- |
| `PRIMARY KEY` | Row identity                 | `customer_id`                     |
| `FOREIGN KEY` | Relationship integrity       | `orders.customer_id`              |
| `UNIQUE`      | Business-key uniqueness      | `customers.email`                 |
| `NOT NULL`    | Required value presence      | `products.name`                   |
| `CHECK`       | Domain validity              | `products.price > 0`              |
| `DEFAULT`     | Automatic value when omitted | `orders.order_status = 'pending'` |

Consider a new order.

The customer reference must satisfy the `FOREIGN KEY`.

The order receives its own `PRIMARY KEY`.

The order status can receive a `DEFAULT`.

An order item quantity must satisfy its `CHECK`.

The order-item combination can be protected by a composite `PRIMARY KEY`.

The product reference in the order item must satisfy another `FOREIGN KEY`.

The integrity of the final state comes from the combination of these rules.

## Python Implementation

The Python program uses the standard-library `sqlite3` module, making the examples executable without an external database driver.

The `ConstraintDemo` class creates four related tables:

- `customers` 
- `products` 
- `orders` 
- `order_items` 

The schema contains all six requested constraint types.

The program deliberately attempts invalid operations and catches `sqlite3.IntegrityError`. This makes database enforcement observable instead of merely describing it.

The Python implementation also demonstrates:

-  SQLite foreign-key activation with `PRAGMA foreign_keys = ON` 
-  generated integer primary keys 
-  composite primary keys 
-  unique email and SKU values 
-  required columns 
-  domain checks for age, price, stock, status, and quantity 
-  default status and stock values 
-  foreign-key rejection for nonexistent parents 
- `ON DELETE RESTRICT` 
- `ON DELETE CASCADE` 
-  schema inspection through SQLite `PRAGMA` statements 
-  transaction rollback 
-  stock changes combined with order creation 

The `transaction()` context manager is especially important in the order workflow. Constraint enforcement can reject one statement, but a business operation may consist of several statements. The transaction ensures that a failed operation does not leave half of the intended changes committed.

## JavaScript Implementation

The JavaScript implementation takes a complementary approach instead of translating the SQL program line by line.

`ConstraintDatabase` stores rows in `Map` objects and maintains secondary lookup maps for unique email and SKU values.

This makes several database concepts explicit:

- `Map` structures model keyed row storage. 
-  Secondary maps model efficient uniqueness indexes. 
- `ConstraintError` records which constraint rejected an operation. 
- `RepositoryEventBus` demonstrates event-driven reactions after successful changes. 
- `structuredClone()` provides transaction snapshots. 
- `transaction()` restores the previous state when an operation fails. 
-  asynchronous execution demonstrates how a database-oriented workflow can fit into Node.js application code. 

The order creation method stages order items and stock changes before committing them. This is important because a failure in the second or third item should not leave the first item committed independently.

The implementation also models `ON DELETE RESTRICT` behavior when attempting to delete a product referenced by an order item.

The JavaScript model is intentionally an educational relational engine rather than a replacement for a production database. A real application would normally delegate durable constraint enforcement to a relational database.

## C++ Case Study

The C++ program presents a typed commerce repository designed around explicit integrity invariants.

The `CommerceRepository` class maintains customers, products, orders, and order items in hash-based containers.

The case study uses:

- `std::unordered_map` for keyed entity storage 
-  secondary maps for unique email and SKU indexes 
- `std::unordered_map` with `CompositeKeyHash` for composite order-item identity 
- `std::optional` to distinguish omitted values from supplied values 
-  custom `ConstraintViolation` exceptions to classify integrity failures 
-  staged order creation to avoid partial state 
-  explicit foreign-key checks 
-  domain validation for `CHECK` semantics 
-  defaults through `std::optional::value_or` 

The `CompositeKey` type is particularly relevant to relational modeling. It represents the `PRIMARY KEY(order_id, product_id)` relationship directly rather than flattening the two values into an arbitrary string.

The repository also implements deletion restrictions. A customer or product that is still referenced by dependent records cannot be removed.

This case study illustrates how relational constraints can influence application architecture: repository methods become integrity boundaries, secondary indexes support uniqueness checks, and multi-record operations require atomic behavior.

## Transactional Integrity

Constraints and transactions solve different problems.

A constraint determines whether an individual database state is valid.

A transaction determines whether a group of changes becomes visible as one atomic operation.

Suppose an order contains a laptop and two monitors. The system needs to:

-  create the order 
-  create the order items 
-  reduce inventory 

If inventory is reduced successfully but a later order-item insert fails, committing the inventory change alone would produce an inconsistent business state.

The Python implementation demonstrates rollback with an intentionally invalid order-item quantity. The stock update occurs inside the same transaction as the invalid insert. When the constraint rejects the insert, the transaction rolls back the stock change as well.

The JavaScript implementation models the same principle through snapshots and restoration. The C++ implementation stages changes before committing them.

## Constraint Failure Modes

A database application should distinguish different integrity failures rather than treating every failed insert as an unexplained error.

A duplicate customer email indicates a `UNIQUE` violation.

A missing required customer name indicates a `NOT NULL` violation.

An underage customer indicates a `CHECK` violation.

An order referencing an unknown customer indicates a `FOREIGN KEY` violation.

A duplicate order/product relationship indicates a `PRIMARY KEY` violation.

An omitted order status does not represent an error because `DEFAULT` supplies `pending`.

This distinction matters for application behavior. A duplicate email might produce a user-facing conflict response, while a foreign-key failure could indicate stale application state or an invalid API request.

## Common Design Mistakes

### Using only application validation

Checking `price > 0` in a web application does not guarantee that every process writing to the database performs the same check.

Background jobs, scripts, administrative tools, imports, and other services may bypass the original validation path.

Database constraints provide protection at the persistence boundary.

### Treating NOT NULL as a general validation rule

`NOT NULL` only prevents null values. It does not establish that a string is non-empty, a number is positive, or a status is allowed.

Those requirements need appropriate `CHECK`, `UNIQUE`, or application rules.

### Using UNIQUE instead of a relationship

A unique customer identifier does not establish that an order references an existing customer.

That relationship is the responsibility of a `FOREIGN KEY`.

### Assuming DEFAULT validates supplied values

A default applies when a value is omitted. It does not automatically correct invalid values that the caller explicitly supplies.

`DEFAULT 'pending'` does not mean that an explicitly supplied status of `unknown` becomes `pending` if a `CHECK` constraint forbids `unknown`.

### Forgetting foreign-key enforcement

Database engines differ in how foreign keys are configured. SQLite in particular requires foreign-key enforcement to be enabled on the connection.

The Python program explicitly enables it.

### Creating constraints without considering existing data

Adding a constraint to an existing table requires the current data to satisfy the new rule. A migration can fail if existing rows contain duplicates, nulls, invalid values, or broken references.

Constraint changes should therefore be treated as schema migrations rather than isolated SQL edits.

## Performance Considerations

`PRIMARY KEY` and `UNIQUE` constraints generally require efficient lookup structures so the database can identify duplicate keys.

A `FOREIGN KEY` also affects write operations. When inserting or modifying a child row, the database may need to verify the referenced parent. When deleting or updating a parent, it may need to locate dependent child rows.

Indexes on foreign-key columns can therefore become important for large tables, especially for parent deletion and update operations.

`CHECK` constraints usually represent relatively inexpensive value-level predicates, but complex expressions should still be designed carefully.

`DEFAULT` values normally have little performance impact because they provide values during row creation.

The important performance principle is that integrity should not be removed simply because validation has a cost. Instead, indexes, query plans, batching, and schema design should be used to make enforcement efficient.

## Security Considerations

Constraints are not a replacement for authorization.

A `CHECK` constraint can prevent a negative price, but it does not determine whether a particular user is allowed to change that price.

A `FOREIGN KEY` can verify that an order references a real customer, but it does not determine whether the current application user is authorized to create an order for that customer.

A secure production system therefore separates concerns:

-  constraints protect data integrity 
-  authorization controls permitted actions 
-  authentication identifies the caller 
-  parameterized SQL prevents injection attacks 
-  transactions protect multi-step state changes 

The Python implementation uses parameterized SQL values rather than constructing SQL statements by concatenating user-controlled values.

## Debugging and Verification

Constraint failures should be reproduced with the smallest possible operation.

For a `UNIQUE` failure, inspect the existing value and its associated row.

For a `FOREIGN KEY` failure, verify both the child value and the referenced parent key.

For a `NOT NULL` failure, inspect whether the application omitted the field or explicitly supplied null.

For a `CHECK` failure, evaluate the constraint expression against the rejected value.

For a primary-key failure, determine whether the application generated a duplicate identity or duplicated a composite relationship.

For unexpected defaults, inspect whether the column was omitted from the insert or explicitly supplied.

The Python program uses SQLite `PRAGMA table_info()` and `PRAGMA foreign_key_list()` to expose schema metadata. This is useful when debugging the actual database definition rather than assuming the schema matches the application model.

## Production Considerations

Constraints should be designed together with the lifecycle of the data.

A production schema should define stable primary keys, identify genuine business uniqueness requirements, make required attributes explicit, encode durable domain invariants with `CHECK`, and use foreign keys for relationships that must remain valid.

Constraint names and migration strategy become important as schemas grow. A failed migration can affect deployment pipelines, and changing a constraint can require data cleanup before the new rule can be enabled.

Application code should still validate input for usability and early error reporting. Database constraints remain the final integrity boundary.

The strongest architecture is therefore layered rather than duplicated blindly: application validation can provide fast feedback, while relational constraints guarantee that invalid states cannot be persisted through another code path.

## Practical Relationship Between the Six Constraints

A realistic order insertion demonstrates how the rules cooperate:

The customer must already exist because `orders.customer_id` is a `FOREIGN KEY`.

The new order receives an identity through its `PRIMARY KEY`.

The order status can be omitted because `DEFAULT` supplies `pending`.

An order item must refer to a real product because `product_id` is a `FOREIGN KEY`.

The quantity cannot be zero or negative because of `CHECK`.

The order/product pair cannot be duplicated because of the composite `PRIMARY KEY`.

The captured unit price cannot be absent because it is `NOT NULL`, and it must be positive because of `CHECK`.

These rules are different layers of integrity. None of them should be treated as a generic substitute for another constraint type.

## Files

The Python source is a runnable SQLite demonstration that shows actual relational constraint enforcement and transaction behavior.

The JavaScript source models the same integrity principles through Node.js classes, `Map` indexes, events, staged mutations, and rollback snapshots.

The C++ source presents the topic as a typed repository and governance case study, including composite-key handling, secondary uniqueness indexes, foreign-key restrictions, validation, and staged commits.

Together, the three implementations show the same relational principles from database-native, application-runtime, and systems-programming perspectives.
