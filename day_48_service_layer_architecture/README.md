# Service Layer Architecture

## Scope

Service layer architecture separates an application's delivery mechanism, use-case coordination, persistence mechanism, and business rules.

This implementation treats four responsibilities as distinct:

| Layer | Primary responsibility | What it should not own |
|---|---|---|
| Controller | Translate external requests and responses | Core business rules or SQL |
| Service | Coordinate application use cases | HTTP formatting or persistence implementation details |
| Repository | Persist and retrieve domain data | Business decisions about domain behavior |
| Domain logic | Protect business invariants and state transitions | HTTP, database connections, or transport concerns |

The separation is useful because a business operation such as confirming an order should remain valid whether the caller is an HTTP endpoint, a scheduled job, a command-line interface, or another internal service.

The examples use order management because it provides concrete state transitions, persistence needs, validation rules, and aggregate behavior without introducing unrelated framework dependencies.

## Architectural Boundary

A typical request follows this direction:

`HTTP request -> Controller -> Service -> Repository -> Database`

The business decision flows in the other direction through domain objects:

`Controller -> Service -> Domain behavior`

The repository supplies data required by the service, but it should not decide whether a draft order may be confirmed. That decision belongs to the domain model or to an application policy when the rule is explicitly an application-level concern.

The controller is the outermost boundary. It understands request fields, response status codes, serialization, and transport-specific error mapping.

The service represents a use case such as `createOrder`, `addLine`, or `confirmOrder`. It coordinates several dependencies when one business operation requires them.

The repository provides persistence-oriented operations such as `findById` and `save`. A service can therefore depend on an interface rather than directly constructing SQL connections.

The domain object contains rules that must remain true independently of storage and transport. In the examples, an order cannot be modified after confirmation, an order cannot be confirmed without lines, and duplicate products are rejected within the order.

## Controllers

A controller is an adapter between an external protocol and the application.

In the Python implementation, `OrderController.post_order`, `post_line`, and `post_confirm` translate dictionaries into service commands and translate domain exceptions into response dictionaries.

The controller does not calculate an order total. It does not decide whether an order is draft or confirmed. It does not search a product table directly.

The JavaScript controller follows the same architectural boundary while using asynchronous methods appropriate for Node.js. `toHttpResponse` centralizes translation of domain failures into transport responses.

The C++ controller demonstrates the same boundary without requiring an HTTP framework. It converts service exceptions into HTTP-like status output to make the separation visible.

The Java controller produces a small `Response` value containing a status and body. This keeps transport formatting out of `OrderService`.

A useful controller is intentionally thin. Thin does not mean that the controller has no responsibility. It validates transport shape, performs authentication or authorization checks when appropriate for the boundary, invokes the correct use case, and maps application outcomes into the protocol used by the caller.

## Services

A service coordinates a use case.

For example, adding a product to an order requires more than a single domain method:

`OrderService.add_line` first retrieves the order, then retrieves the active product, creates an order line using the persisted product price, invokes the domain object's `add_line`, and persists the changed aggregate.

This is service-level orchestration.

The service does not need to know whether the repository uses PostgreSQL, an in-memory dictionary, a remote persistence API, or another mechanism.

The Python implementation uses `CreateOrderCommand` and `AddOrderLineCommand` to make use-case inputs explicit. This avoids passing HTTP-shaped dictionaries deep into the application.

The JavaScript implementation uses asynchronous repository methods and publishes domain-oriented events after successful operations. The controller does not need to know that confirmation produced an audit event.

The Java implementation uses immutable command records. `OrderService` depends on repository interfaces, allowing the domain workflow to be tested against in-memory implementations.

A service should not become a replacement for the domain model. A common failure is to place every business rule inside a large `OrderService` while reducing domain entities to passive data structures. This produces procedural business logic that becomes difficult to protect when another entry point bypasses that particular service method.

## Repository Pattern

A repository abstracts persistence for a domain-oriented collection or aggregate.

The examples use methods such as `findById`, `save`, `findActive`, and `findByCustomer`.

The repository should answer persistence questions:

- Can this order be retrieved?
- Can this product be saved?
- Which active product has this identifier?
- Which orders belong to this customer?

It should not answer domain questions such as whether a confirmed order may be modified. The domain object answers that question.

The Python implementation uses generic `Repository[T]` and an in-memory implementation. `ProductRepository.find_active` adds a persistence-oriented query for active products.

The JavaScript implementation uses asynchronous repositories even though the demonstration uses memory. This mirrors the shape of real Node.js persistence APIs without requiring a database package.

The C++ implementation defines a templated repository abstraction and concrete in-memory repositories. The service therefore has no direct dependency on `std::unordered_map`.

The Java implementation uses `Repository<T>` and `ProductRepository` interfaces. `Optional<T>` makes absence explicit instead of using null as the normal repository result.

In a production system, a repository implementation may contain SQL, ORM operations, connection handling, mapping between database rows and domain objects, and transaction participation. Those details remain outside the controller.

## Domain Logic

Domain logic is the most important distinction in this architecture.

The `Order` domain object owns the state transition from `DRAFT` to `CONFIRMED`. It checks that at least one line exists and refuses illegal transitions.

The order also prevents modification after confirmation.

These are not controller rules. They are not PostgreSQL-specific rules. They are business invariants.

The same principle appears in all four language implementations:

- Python `Order.confirm` rejects empty orders and illegal states.
- JavaScript `Order.confirm` performs the state transition and protects the invariant.
- C++ `Order::confirm` owns the transition and uses exceptions for invalid states.
- Java `Order.confirm` protects the same domain invariant while `OrderLine` validates its own value constraints.

The architecture therefore avoids a dangerous situation in which one HTTP endpoint validates a rule while another entry point accidentally bypasses it.

## Relationship Between the Layers

The layers are related but not interchangeable.

A controller is about delivery.

A service is about application use-case orchestration.

A repository is about persistence access.

Domain logic is about business correctness.

For example, confirming an order can be modeled as:

`POST /orders/{id}/confirm`

The controller receives the request and extracts the identifier.

The service loads the order through the repository.

The domain object evaluates whether the transition is legal.

The service persists the changed aggregate.

The controller converts the successful result into an HTTP response.

If confirmation fails because the order is already confirmed, the domain raises a conflict. The controller can translate that into an HTTP 409 without knowing the internal rule that caused it.

## Python Implementation

The Python program provides a complete in-memory application.

`Order`, `OrderLine`, and `Product` are domain structures. `Order` contains the state machine for draft, confirmed, and cancelled orders.

`OrderRepository` and `ProductRepository` provide persistence abstractions.

`OrderService` coordinates product lookup, order creation, line creation, confirmation, and cancellation.

`OrderController` models a delivery boundary by converting payload dictionaries into commands and exceptions into status/body responses.

The script also demonstrates service-level testability. `demonstrate_service_testability` exercises the service without an HTTP server and without PostgreSQL. The same application service can therefore be tested independently of the delivery mechanism.

Money is represented as integer cents rather than binary floating-point values. This avoids common currency rounding problems.

The Python implementation also explicitly rejects invalid quantities, negative prices, duplicate products, nonexistent products, and modifications to confirmed orders.

## JavaScript Implementation

The JavaScript implementation uses Node.js-specific asynchronous behavior and an event-driven design.

Repositories expose `async` methods. This gives the service the same asynchronous boundary that a real database repository would have.

`EventEmitter` provides a lightweight event mechanism. Successful order confirmation publishes an `order.confirmed` event. An audit subscriber can respond without coupling the controller to audit behavior.

The domain model uses JavaScript classes and explicit validation. `Object.freeze` is used when publishing event payloads so subscribers cannot accidentally mutate the event object itself.

The implementation also considers JavaScript's numeric limitations. Currency is represented with safe integer values and checked using `Number.isSafeInteger`. A production implementation dealing with values outside this range could use `BigInt` or a decimal representation appropriate to financial calculations.

The asynchronous service boundary demonstrates why a repository can be replaced by a PostgreSQL implementation without changing the controller's responsibility.

## C++ Case Study

The C++ program models the same architectural problem from a systems-oriented perspective.

`Order` is the aggregate that protects state transitions. Its `addLine`, `confirm`, and `cancel` methods prevent invalid operations.

The repository abstraction is represented by a templated `Repository<T>` interface. Concrete repositories use `std::unordered_map` for deterministic in-memory persistence.

The service owns references to repository abstractions and coordinates the application workflow.

The controller catches domain-specific exceptions and translates them into HTTP-like responses.

The C++ implementation pays particular attention to numeric correctness. Order quantities and prices use integer cents, and `OrderLine::subtotal` checks for integer overflow before multiplication. Aggregate totals also guard against overflow.

This is important in systems code because an arithmetic failure can otherwise become memory corruption, incorrect billing, or another serious production defect depending on how the result is used.

The implementation also separates ownership clearly. Repository instances live in `main`, while the service and controller receive references to them. The service does not construct or destroy the persistence infrastructure.

## Java Enterprise Model

The Java implementation emphasizes explicit domain types and dependency inversion.

`OrderStatus` is an enum rather than a free-form string. This constrains the state space and makes illegal status values difficult to represent.

`Product` and command objects use Java records where immutable value semantics are appropriate.

`Order` remains a class because its state changes through controlled domain methods. The private `status` and `lines` fields cannot be changed directly by callers.

`OrderService` depends on repository interfaces rather than concrete storage classes.

The controller handles transport-level response mapping. `Response` provides a small immutable representation of the result.

The Java implementation uses `Optional` for repository lookups. Missing persistence records are therefore explicitly represented and converted into `NotFoundException` at the service boundary.

`Math.multiplyExact` and `Math.addExact` detect arithmetic overflow instead of silently producing an incorrect monetary total.

## PostgreSQL Data Model

The SQL implementation represents the persistence side of the same domain.

`customers` stores customer identity.

`products` stores product definitions, prices, and activation status.

`orders` represents the aggregate root and uses the `order_status` enum to constrain legal persisted states.

`order_lines` represents products belonging to an order.

Foreign keys maintain relationships. The unique constraint on `(order_id, product_id)` prevents the same product from appearing twice within one order.

The `orders` table also uses a check constraint to make timestamp fields consistent with the order state. A confirmed order requires `confirmed_at`, while a cancelled order requires `cancelled_at`.

This demonstrates an important principle: application-domain rules should not rely exclusively on application code when the database can enforce a critical integrity invariant.

## Transactions and State Changes

The SQL script uses a transaction when creating an order and its initial line.

This matters because an order and its lines form a related unit of work. If the line insertion fails, a real application should not leave an incomplete aggregate unless that incomplete state is explicitly part of the domain model.

The `confirm_order` PostgreSQL function locks the selected order with `FOR UPDATE` before examining and changing its state.

That lock matters when concurrent requests could attempt to confirm or otherwise modify the same aggregate.

The function also checks that at least one line exists before changing the status.

The trigger protecting order-line modifications adds another database-level defense. It prevents direct persistence operations from changing lines after an order leaves the draft state.

The application service remains responsible for orchestration, but persistence integrity does not depend entirely on every caller behaving correctly.

## Read Models and Queries

The `order_totals` view provides a read-oriented representation containing the customer code, order state, line count, and calculated total.

This separates a common reporting/read concern from the write-side aggregate representation.

The view does not replace domain logic. Its purpose is efficient relational retrieval.

The active-product query corresponds to the repository's `findActiveById` behavior.

The draft-order query can identify aggregates that remain editable.

These examples demonstrate that repositories can expose domain-relevant persistence operations without forcing controllers to construct SQL statements.

## Edge Cases

A robust service layer must handle failure states explicitly.

An order that does not exist produces a not-found condition rather than a null dereference.

A nonexistent or inactive product cannot be added.

A non-positive quantity is rejected before persistence.

An order without lines cannot be confirmed.

A confirmed order cannot be modified.

An already cancelled order cannot be cancelled again.

A confirmed order cannot be cancelled through the simple cancellation operation because a real system may require payment reversal, fulfillment cancellation, or another coordinated workflow.

Duplicate order products are rejected by the domain model and protected by the SQL unique constraint.

Arithmetic overflow is explicitly considered in the C++ and Java implementations, while JavaScript checks the safe integer range.

## Error Boundaries

Error handling should reflect the layer where the failure occurs.

A malformed transport payload belongs near the controller boundary.

A missing database record is a repository result that the service may translate into a domain/application exception.

An illegal state transition belongs to domain logic.

A database constraint violation belongs to the persistence boundary and should be mapped into an application-level outcome rather than leaked directly to an HTTP client.

The controller then converts known application failures into protocol-specific responses such as 400, 404, or 409.

Unexpected infrastructure failures should generally become a generic server error rather than exposing SQL statements, stack traces, credentials, or internal implementation details.

## Dependency Direction

A strong service-layer design controls dependency direction.

The controller depends on the service.

The service depends on repository abstractions.

The domain should not depend on HTTP request classes, SQL drivers, or controller classes.

Concrete persistence implementations depend on the repository contract.

This makes replacement and testing easier.

For example, an in-memory repository can support service tests without requiring a live PostgreSQL instance. A PostgreSQL repository can later implement the same interface without changing the domain object's state-transition rules.

## Performance Considerations

Layering does not automatically make an application fast.

A poorly implemented repository can create an N+1 query problem by loading every line separately.

A service that repeatedly retrieves the same aggregate can create unnecessary database round trips.

The PostgreSQL example therefore creates indexes on customer lookups, order-line retrieval, and active products.

Repository methods should match actual access patterns rather than exposing arbitrary persistence primitives.

For read-heavy applications, dedicated queries or read models can avoid loading an entire aggregate when only a projection is required.

For write operations, transaction boundaries should cover the complete use case when several persistence operations must succeed together.

## Concurrency

Service-layer correctness must account for concurrent requests.

Two requests might attempt to confirm the same order at approximately the same time.

The domain model protects state transitions within one loaded instance, but concurrent database transactions can still race.

The PostgreSQL `confirm_order` function uses row locking before checking and changing the order state. This makes the state transition atomic relative to other transactions using the same locking strategy.

A production implementation may also use optimistic locking with a version column. In that model, an update succeeds only when the version observed during the read still matches the version in the database.

The correct strategy depends on contention, transaction duration, failure semantics, and database capabilities.

## Security Considerations

Controllers should authenticate the caller before invoking protected use cases and authorize access to the specific aggregate.

A customer should not be able to provide another customer's order identifier and retrieve or modify it merely because the identifier is syntactically valid.

Repository queries should use parameterized statements rather than string concatenation when a real SQL repository is implemented.

Domain validation should reject impossible values early, but validation is not a replacement for authorization.

Error responses should not expose SQL details, database schema information, stack traces, credentials, or internal infrastructure identifiers.

For monetary operations, integer or decimal-safe representations should be used instead of binary floating-point calculations.

## Common Architectural Mistakes

Putting business rules in controllers creates duplicated behavior when the same use case gains another entry point.

Putting SQL directly in controllers couples the delivery mechanism to persistence and makes application logic difficult to test.

Turning the service into a large class containing every business rule produces a transaction-script style system where domain entities become passive data holders.

Making repositories responsible for business decisions mixes persistence concerns with domain policy.

Creating repositories for every trivial table without identifying aggregate boundaries can produce excessive data-access calls and unclear transactional behavior.

Using generic methods such as `saveAnything` everywhere can also hide important persistence semantics. Repository contracts should express meaningful operations for the application's access patterns.

## Practical Boundary Test

A useful architectural test is to ask whether each class could change for a different reason.

A controller should change when the transport contract changes.

A repository implementation should change when persistence technology or query strategy changes.

A service should change when the application use case changes.

A domain object should change when a business invariant or domain rule changes.

If adding a REST endpoint requires rewriting domain rules, the boundaries are probably too tightly coupled.

If replacing PostgreSQL requires changing the domain model, persistence concerns have leaked inward.

If a new command-line interface requires duplicating confirmation rules from the HTTP controller, business logic has been placed in the wrong layer.

## Production Considerations

A production implementation normally adds transaction management, authentication and authorization, structured logging, observability, retry policies for transient infrastructure failures, database connection pooling, migration management, audit events, idempotency where appropriate, and automated tests.

Those capabilities should be attached to the appropriate architectural boundary rather than placed indiscriminately inside controllers or domain objects.

The central design remains the separation of responsibilities: controllers translate delivery concerns, services coordinate use cases, repositories isolate persistence, and domain logic protects business correctness.
