# ORM Fundamentals

## Scope

Object-Relational Mapping, or ORM, is the application-layer technique of representing relational database records as domain objects and translating changes to those objects back into database operations.

The central problem is not simply "how to save an object." A relational database represents data through tables, rows, columns, primary keys, foreign keys, constraints, joins, and set-oriented queries. An application often represents the same domain through objects containing attributes, methods, references, and collections.

ORM exists at the boundary between those representations.

This implementation set uses a procurement and commerce-oriented domain to keep that distinction concrete. The Python implementation exposes the mapping mechanics directly, the JavaScript implementation focuses on object lifecycle and event-driven persistence behavior, the C++ implementation models a repository system and object graph hydration, the Java implementation models an enterprise purchase-order domain, and the SQL implementation exposes the relational side of the same fundamental problem.

## ORM terminology

| ORM concept | Relational representation | Object representation |
|---|---|---|
| Model/entity | Table | Class or domain type |
| Attribute | Column | Object field/property |
| Object identity | Primary key | Object identifier |
| Relationship | Foreign key | Reference or collection |
| One-to-one | Unique foreign key | Single related object |
| One-to-many | Foreign key on child | Collection of child objects |
| Many-to-many | Junction table | Collections on both sides |
| Persistence | `INSERT`, `UPDATE`, `DELETE` | Saving object state |
| Query | SQL result set | Objects or projections |
| Constraint | Database constraint | Validation or domain rule |
| Session/context | Transaction and identity scope | Managed object lifecycle |

The important distinction is that these pairs are related but not identical. A foreign key is not itself an object reference. A table row is not automatically equivalent to a complete domain object. ORM mapping supplies the translation rules.

## Models and mappings

A model describes a domain entity that needs persistent identity.

The Python program contains `User`, `Address`, `Product`, `Order`, and `OrderItem`. The SQL schema represents these concepts as separate tables.

For example, the Python `Product` contains:

- an `id` corresponding to the relational primary key
- a `name` corresponding to a text column
- a `price` corresponding to a numeric column

The explicit `Session.commit()` implementation demonstrates the mapping rather than hiding it. A `Product` object is translated into an `INSERT INTO products` operation, and the generated database identity is assigned back to the Python object.

A real ORM performs this mapping automatically according to model metadata, configuration, conventions, annotations, or declarative mappings.

## Relationships

Relationships are where object and relational representations become more visibly different.

### One-to-one

The Python schema maps a user to an address through `addresses.user_id`.

The `UNIQUE` constraint on that foreign key ensures that one user cannot have multiple address rows in that particular model.

The object-oriented representation can treat the address as a single related object, while the database represents the relationship using two rows connected by a foreign key.

### One-to-many

An order contains multiple order items.

Relationally, `order_items.order_id` points to `orders.id`. The parent does not need to store an array inside the database row.

The Python `Order` instead exposes `items` as a list. The mapping process therefore converts multiple child rows into a collection belonging to one object.

This is a fundamental ORM operation: multiple relational rows become one object graph.

### Many-to-many

Products and orders have a many-to-many relationship in the business sense.

An order can contain many products, and a product can appear in many orders. The relational model does not store a list of product IDs in the order table. It uses `order_items` as an association structure.

The association also carries additional information such as quantity and unit price. That makes the junction entity more than a simple many-to-many link.

## Identity

Database identity normally comes from a primary key.

The Python `Session` maintains an identity map keyed by model type and database ID. Loading the same user twice within the session returns the same in-memory object.

The JavaScript implementation uses a similar `identityMap`, while the Java implementation uses a `PersistenceContext`.

Identity management matters because two independent in-memory objects representing the same database row can produce confusing behavior.

For example, if two objects represent `Product#15`, changing one object does not automatically change the other unless the persistence context coordinates their identity.

An ORM session therefore commonly has responsibilities beyond simply executing SQL. It can track which objects are new, modified, unchanged, or removed.

## Object state and persistence

An ORM must distinguish application state from database state.

The JavaScript implementation demonstrates dirty tracking through `dirtyFields()`. The model remembers its original persistent values and compares them with its current values.

If a product's price changes from `85000` to `82000`, the session can determine that `price` is the changed field rather than blindly replacing every property.

This distinction becomes important for:

- update efficiency
- optimistic concurrency
- auditing
- transaction handling
- detecting accidental changes
- deciding whether an SQL `UPDATE` is necessary

Real ORM implementations can provide much more sophisticated state tracking.

## Session and persistence context

A session or persistence context provides a scope in which ORM-managed objects live.

The Python `Session` contains an identity map and a list of pending objects.

The Java implementation separates the persistence context from the repository. The context stores object identity, while the repository represents persistence operations.

These are conceptually different responsibilities.

A repository answers questions such as "load this entity" or "save this entity."

A persistence context answers questions such as "is this entity already managed in this context?"

The distinction becomes particularly important in larger applications where transactions, caching, lazy relationships, and change tracking interact.

## Python implementation

The Python program uses `sqlite3`, `dataclasses`, and explicit SQL instead of an external ORM package.

That design is intentional. It makes the mechanism visible.

`Database.create_schema()` establishes:

- users
- addresses
- products
- orders
- order items

The foreign keys demonstrate relational relationships, while the dataclasses demonstrate domain models.

`Session.get_user()` and `Session.get_product()` implement object loading. The identity map prevents repeated loads of the same identity from creating separate instances.

`Session.commit()` shows how an ORM translates different model types into persistence operations.

`load_order_graph()` demonstrates the reverse direction. A SQL join produces flat rows, and application code reconstructs an order containing product information and line items.

The function makes the object-relational impedance mismatch particularly clear: SQL naturally produces rows, while application code often wants a nested graph.

The Python implementation also validates objects before persistence and enables SQLite foreign-key enforcement.

## JavaScript implementation

The JavaScript program approaches ORM behavior through model metadata and an event-driven persistence layer.

`ORM_METADATA` maps model names to table names and persistent fields.

The base `Model` provides:

- metadata access
- serialization into records
- dirty-field detection
- clean-state tracking

`User`, `Product`, `OrderItem`, and `Order` provide domain-specific validation.

The `EventBus` introduces a JavaScript-specific design dimension. Persistence events such as `entity.inserted`, `entity.updated`, and `transaction.committed` can be observed without embedding all behavior directly inside the persistence code.

This resembles the event-driven integration patterns commonly used in Node.js applications.

The in-memory store is not intended to replace a database. Its purpose is to expose ORM responsibilities without introducing an external dependency.

The `loadOrderGraph()` function reconstructs an object graph by resolving the order, its items, each product, and its user through the session.

## C++ case study

The C++ implementation models a repository platform.

A `Repository` contains repository-level identity and configuration. `Developer` represents a user of the development platform. `Commit` represents a repository change record, and `PullRequest` connects a repository and developer while retaining references to commits.

The relationships are stored as integer IDs, which correspond to foreign keys in a relational design.

`IdentityMap` provides an object identity cache. Repeated requests for the same repository ID return the same in-memory object.

`PullRequestMapper::hydrate()` is the mapping boundary. It resolves repository and developer identifiers and loads referenced commits before producing a `PullRequestView`.

This is a useful representation of hydration: relational identifiers are transformed into a richer application-level object graph.

The C++ example also includes a small `UnitOfWork`. It demonstrates the idea that multiple persistence operations can be coordinated as one logical operation. The example is deliberately not presented as a substitute for a database transaction. A production implementation would need actual transactional database semantics, rollback guarantees, isolation, generated-key management, and database error handling.

The report section illustrates another ORM tradeoff. Object navigation is convenient for domain behavior, while relational engines are often stronger for large set-oriented aggregates and reporting queries.

## Java enterprise model

The Java program models a procurement workflow involving suppliers, products, purchase orders, and purchase-order lines.

`Supplier` and `Product` are immutable records. This is appropriate for data whose identity and core attributes should not be casually mutated.

`PurchaseOrder` is a richer domain object because its behavior includes state transitions.

The order can move through:

`DRAFT -> SUBMITTED -> APPROVED -> FULFILLED`

Cancellation is permitted from appropriate states, while fulfilled orders cannot be cancelled.

This demonstrates an important ORM design principle: not every rule belongs in the mapping layer.

An ORM can persist a `PurchaseOrder`, but the domain object can still own business invariants. The persistence layer should not become the only place where domain meaning exists.

`PurchaseLine` represents the relationship between an order and a product while adding quantity and price attributes.

The Java `Repository<T, ID>` interface separates persistence operations from the domain model. `PersistenceContext` separately handles managed identity.

This separation resembles enterprise persistence architectures in which domain behavior, repositories, transactions, and persistence contexts have different responsibilities.

## SQL data model

The PostgreSQL script represents the relational side of ORM explicitly.

The main tables are:

- `suppliers`
- `products`
- `purchase_orders`
- `purchase_order_lines`

`purchase_orders.supplier_id` creates the supplier-to-order relationship.

`purchase_order_lines.order_id` creates the order-to-line relationship.

`purchase_order_lines.product_id` creates the line-to-product relationship.

The resulting relational structure avoids storing arrays of objects directly in an ordinary normalized row.

The `order_totals` view demonstrates a database-side projection. Rather than loading every order line into application memory and calculating totals there, the database can aggregate the information using `SUM()`.

This is an important ORM tradeoff: object-oriented access is useful for domain behavior, but complex aggregation can be better expressed as SQL.

## Constraints belong at the database boundary too

Application validation is not enough.

The SQL schema uses:

- primary keys for identity
- foreign keys for referential integrity
- unique constraints for uniqueness
- check constraints for valid numeric values
- status constraints for permitted order states
- indexes for commonly accessed relationships

For example, `quantity > 0` is enforced in the database.

That means a second application, a script, an administrative operation, or a future service cannot insert a negative quantity merely because it bypassed application-level validation.

The application and database therefore have complementary responsibilities.

Application validation can provide domain-friendly error messages and prevent invalid work early.

Database constraints provide a final integrity boundary.

## ORM advantages

ORM can significantly reduce repetitive persistence code.

Developers can work with domain objects instead of manually writing every basic `INSERT`, `UPDATE`, and `SELECT`.

Relationship navigation can become more natural. An order can expose a collection of order lines rather than requiring every caller to manually write a join.

ORMs can also centralize:

- identity handling
- parameter binding
- change tracking
- transaction coordination
- relationship mapping
- validation hooks
- query construction
- schema migration integration

The value is greatest when the application's domain model and persistence model have substantial structure that would otherwise produce repetitive mapping code.

## ORM tradeoffs

ORM does not remove database complexity.

It can introduce another abstraction layer that developers must understand.

A query that appears simple in application code may result in several SQL queries. Relationship loading can therefore create performance problems.

A common example is the N+1 query problem. An application loads one collection of orders and then separately queries the supplier for each order. The code can look object-oriented and clean while producing many database round trips.

Large object graphs can also consume substantial memory.

Another tradeoff is that ORM abstractions may not naturally express every database operation. Window functions, specialized indexes, recursive queries, database-specific features, analytical aggregation, and carefully tuned SQL can require direct SQL or ORM escape mechanisms.

The appropriate goal is not to eliminate SQL knowledge. A strong ORM implementation still requires understanding the relational database beneath it.

## Lazy and eager relationship loading

Relationship loading strategy determines when related data is retrieved.

With eager loading, related objects are loaded as part of the initial operation or an explicitly coordinated query.

With lazy loading, related data is retrieved when the application first accesses the relationship.

Lazy loading can reduce unnecessary data retrieval when a relationship is never used.

It can also create hidden database activity. Accessing a property may unexpectedly execute a query, which makes performance less obvious.

The C++ `PullRequestMapper` makes relationship hydration explicit instead of hiding it. The Python `load_order_graph()` likewise makes the SQL join visible.

The advantage of explicit loading is predictability. The disadvantage is that more mapping code becomes visible to the developer.

## Transactions

A transaction should preserve the logical integrity of a unit of work.

Creating an order can involve:

- creating the order
- creating multiple order lines
- updating related inventory
- writing audit information

If only part of that operation succeeds, the system can be left inconsistent unless the database transaction rolls back.

The Python session rolls back when persistence raises an exception.

The SQL script uses explicit `BEGIN`, `COMMIT`, and `ROLLBACK` statements.

The C++ and Java examples model unit-of-work and persistence-context concepts but deliberately do not claim to implement full database transaction semantics.

A production ORM must coordinate its unit of work with a real database transaction.

## Common mapping problems

### N+1 queries

A parent collection is loaded with one query, followed by one query per parent for a relationship.

The object model looks convenient, but the database may receive hundreds or thousands of queries.

The solution is usually explicit eager loading, joins, batching, prefetching, or a projection designed for the required screen or operation.

### Over-fetching

An entity may contain many fields and relationships even when a request needs only a few values.

Loading the complete object graph can waste network bandwidth, database work, and memory.

Projections or specialized queries can be more appropriate for read-heavy operations.

### Under-fetching

The opposite problem occurs when the application repeatedly retrieves missing related information.

This creates additional round trips and can make performance unpredictable.

### Impedance mismatch

Relational databases use tables and joins, while object models use references, inheritance, encapsulation, and collections.

ORM is fundamentally concerned with translating between these models.

The mismatch does not disappear simply because an ORM hides the SQL.

## Security considerations

ORMs commonly parameterize generated queries, which reduces the risk of SQL injection when developers use ORM query APIs correctly.

That does not make an application automatically secure.

Security still requires:

- authorization checks
- correct tenant filtering
- safe raw SQL handling
- protection of sensitive fields
- appropriate database permissions
- transaction boundaries
- validation of externally supplied identifiers

A model's validation rules are not an authorization system.

A user being able to load an entity does not necessarily mean the user is permitted to modify it.

## Performance considerations

The important performance variables are not limited to ORM execution speed.

Database round trips often matter more than object construction.

Indexes should support real access patterns. The SQL implementation indexes foreign-key columns and common status access because those relationships are used by queries.

Large collections should not be loaded unnecessarily.

Aggregations can often be performed efficiently in SQL rather than transferring every row to the application.

Caching can reduce repeated reads, but stale data and invalidation become important concerns.

Identity maps are generally scoped to a persistence context rather than treated as an unlimited global cache.

## Testing considerations

ORM-backed applications need more than unit tests for model methods.

A domain unit test can verify that an order rejects invalid state transitions.

Persistence tests should verify that:

- mappings use the correct columns
- relationships load correctly
- foreign keys are respected
- constraints reject invalid states
- transactions roll back correctly
- generated identities are handled correctly
- queries return the intended rows

Database integration tests are particularly important for behavior that depends on database-specific constraints, transactions, indexes, or SQL semantics.

## Practical distinction between the five implementations

| Implementation | Primary technical emphasis |
|---|---|
| Python | Explicit object-to-row mapping, identity map, relationships, validation, transactions |
| JavaScript | Model metadata, dirty tracking, event-driven persistence, object graph loading |
| C++ | Repository object graph, identity map, hydration, unit of work, mapping boundary |
| Java | Enterprise domain model, immutable records, state transitions, repository and persistence context |
| SQL | Tables, keys, relationships, constraints, indexes, views, transactions, database enforcement |

The implementations deliberately do not perform the same job in different syntax.

The Python program makes basic ORM mechanics visible.

The JavaScript program shows how an ORM-style lifecycle can interact with event-driven application architecture.

The C++ program treats mapping as an explicit boundary between relational identity and a richer object graph.

The Java program emphasizes domain modeling and stateful enterprise behavior around persistence.

The SQL script represents the relational system that all of these object models ultimately need to respect.

## The central relationship

A useful mental model is:

`Relational schema -> mapping rules -> domain objects -> application behavior`

and, during persistence:

`Domain object changes -> unit of work -> SQL operations -> relational constraints`

Pulling these layers apart helps clarify ORM's real role.

An ORM is not a database.

It is not a replacement for SQL.

It is not a substitute for domain modeling.

It is a persistence abstraction that coordinates object identity, mapping, relationships, change tracking, and database operations while allowing application code to work primarily with domain-oriented representations.
