# Dependency Injection: Dependencies, Reusable Logic, Dependency Chains, and Database Dependencies

## 1. Topic Introduction

Dependency Injection (DI) is a software design technique in which an object receives the components it needs from an external source instead of constructing those components internally.

A **dependency** is another object, service, function, resource, or component required by a class or function to perform its work.

For example, an order-processing service may need:

- A user repository
- A product repository
- An order repository
- A database
- A payment gateway
- A notification service
- An audit logger
- A validator
- A clock
- A cache

Without dependency injection, the order service may construct all of these objects itself. That creates strong coupling between business logic and infrastructure.

With dependency injection, the service receives these dependencies from outside.

Conceptually:

`OrderService -> PaymentGateway`

becomes:

`OrderService -> IPaymentGateway <- StripePaymentGateway`

The order service depends on the required behavior rather than on one particular implementation.

The three implementations in this study demonstrate the same underlying architectural principle using different language features:

- Python uses protocols, abstract base classes, constructor injection, functions, test doubles, and a small service container.
- JavaScript uses classes, first-class functions, asynchronous services, runtime validation, repositories, and a small dependency container.
- C++ develops a complete order-processing system using interfaces, references, smart pointers, repositories, dependency chains, database abstractions, test doubles, and explicit ownership.

---

## 2. Dependency Fundamentals

A dependency exists whenever one component requires another component.

Consider a service that sends email.

A tightly coupled design creates the email sender internally:

`WelcomeService -> creates EmailSender`

The service now knows:

1. The concrete class to instantiate.
2. How that dependency is constructed.
3. Which implementation is being used.
4. Potentially, how the external system operates.

The Python and JavaScript implementations first demonstrate this design through `WelcomeService` and `TightlyCoupledWelcomeService`.

The problem is not that direct construction is always wrong. Small applications and simple objects can legitimately construct their own uncomplicated dependencies. The architectural problem appears when business logic becomes responsible for creating and configuring many infrastructure components.

---

## 3. What Dependency Injection Changes

Dependency injection changes the responsibility for object construction.

Instead of:

`Service -> new Dependency()`

the relationship becomes:

`Composition Root -> Dependency`

and:

`Composition Root -> Service(Dependency)`

The service uses the dependency but does not decide which concrete implementation should be constructed.

This creates a useful separation:

- **Business logic** decides what must happen.
- **Infrastructure** performs external operations.
- **Composition** connects concrete implementations to business logic.

---

## 4. Core Terminology

### Dependency

A component required by another component.

Examples include:

- Repository
- Logger
- Database connection
- Payment gateway
- HTTP client
- Clock
- Cache
- File system abstraction
- Notification service

### Dependent

The component that requires another component.

If `OrderService` needs `PaymentService`, then `OrderService` is the dependent.

### Injection

The act of supplying a dependency from outside the dependent component.

### Dependency Graph

A graph showing relationships between components.

For example:

`OrderService -> PaymentService -> PaymentGateway`

and:

`OrderService -> OrderRepository -> Database`

This is a dependency chain.

### Abstraction

A contract describing behavior without requiring the consumer to know the concrete implementation.

Examples:

- Python `Protocol`
- Python abstract base class
- JavaScript object contract
- C++ abstract class with pure virtual functions

### Composition Root

The location where concrete application components are assembled.

For example:

`Database`

is created first, then:

`Repository(Database)`

then:

`Service(Repository)`

The application boundary owns this construction process.

### Test Double

A substitute dependency used during testing.

Examples:

- Fake payment gateway
- Recording notification sender
- In-memory repository
- Fake clock

---

## 5. Why Reusable Logic Matters

Dependency injection is closely connected to reusable logic.

Suppose a notification service only needs a `send()` operation. It should not need to know whether that operation is implemented by:

- SMTP
- An HTTP email provider
- A console logger
- A test recorder
- A queue
- A mock service

The reusable business logic can therefore work with the required behavior.

Python demonstrates this through the `MessageSender` protocol.

JavaScript demonstrates it through objects implementing `send()`.

C++ demonstrates it through `INotificationService`.

The result is a common architectural pattern:

`Business Service -> Required Behavior`

instead of:

`Business Service -> Specific Infrastructure`

---

## 6. Constructor Injection

Constructor injection supplies required dependencies through the constructor.

Python:

`InjectedWelcomeService(sender)`

JavaScript:

`new WelcomeService(sender)`

C++:

`OrderService(...dependencies...)`

Constructor injection is usually appropriate when a dependency is required for the object to operate correctly.

Its major advantages are:

- The dependency is visible.
- The object can validate it during construction.
- The object cannot normally exist without required dependencies.
- Tests can provide substitutes easily.
- Configuration is explicit.

Constructor injection also makes dependency counts visible. If a class requires ten dependencies, that may indicate that its responsibilities should be reconsidered.

---

## 7. Method Injection

Method injection supplies a dependency only to an operation that needs it.

The Python implementation contains `ReportApplication.run()`, which receives a `ReportGenerator`.

Method injection can be useful when:

- The dependency is required only for one operation.
- Different calls may use different implementations.
- Keeping the dependency as object state would be unnecessary.

It is less suitable when the dependency is fundamental to the entire object's identity.

---

## 8. Setter or Property Injection

A dependency can also be assigned after construction.

The Python `ConfigurableLogger` demonstrates this approach.

This can be appropriate for optional dependencies, but it introduces a lifecycle concern: the object may exist temporarily without a dependency that some operation expects.

Required dependencies are generally easier to reason about when injected through construction.

---

## 9. Function Injection

Functions can themselves be dependencies.

The Python implementation uses:

`Callable[[int], int]`

The JavaScript implementation uses:

`Calculator(operation)`

with injected functions such as:

`addition`

and:

`multiplication`

This is especially useful when the dependency is simple behavior rather than a stateful service.

Examples include:

- Comparators
- Validation rules
- Transformation functions
- Pricing algorithms
- Retry policies
- Serialization functions
- Authorization rules

Function injection is often simpler than introducing a class when only one operation is required.

---

## 10. Dependency Inversion

Dependency inversion means that high-level business logic should not be forced to depend directly on low-level infrastructure details.

Instead, both can depend on an abstraction appropriate to the business requirement.

For example:

`OrderService -> PostgreSQL`

creates direct infrastructure coupling.

A more flexible structure is:

`OrderService -> IOrderRepository`

and:

`PostgreSQLOrderRepository -> IOrderRepository`

The business service knows the repository contract. The infrastructure implementation satisfies that contract.

This is particularly important when the system must support:

- Multiple database systems
- Testing without a database
- Local development
- Offline processing
- Different cloud providers
- Different external payment providers

---

## 11. Python Implementation

The Python implementation begins with a tightly coupled `WelcomeService`.

`WelcomeService` constructs `EmailSender` internally.

The injected version uses:

`InjectedWelcomeService(sender)`

The service therefore does not need to know how the sender is created.

### Python Protocols

The Python `Protocol` mechanism allows structural interfaces.

`MessageSender` specifies that an object should provide:

`send(recipient, message)`

Both `ConsoleSender` and `RecordingSender` satisfy the required behavior.

This allows business code to work with different implementations without requiring a shared inheritance hierarchy.

### Abstract Base Classes

Python also demonstrates `UserRepository` using `ABC`.

This creates an explicit interface-like contract:

`find_email(user_id)`

Two implementations are provided:

- `InMemoryUserRepository`
- `DatabaseUserRepository`

The notification service can use either.

---

## 12. Python Database Dependency

The Python example creates an SQLite in-memory database.

The database structure contains a `users` table with:

- `id`
- `email`

`DatabaseUserRepository` receives a `sqlite3.Connection`.

The dependency chain is:

`UserNotificationService`

to:

`UserRepository`

to:

`DatabaseUserRepository`

to:

`sqlite3.Connection`

The important point is that the notification service does not directly execute SQL.

The repository owns the persistence-specific operation.

This separation makes the business service easier to test.

---

## 13. Python Testability

The `RecordingSender` is a test double.

Instead of sending a real message, it records:

`recipient`

and:

`message`

Tests can then verify behavior without external infrastructure.

The test suite uses Python's standard `unittest` library.

Tests demonstrate:

- Existing users are notified.
- Unknown users are not notified.
- Database repositories retrieve data correctly.
- Fake clocks make timestamps deterministic.
- Invalid payments are rejected.

Dependency injection is particularly valuable here because tests can control the environment.

---

## 14. Dependency Chains

Real systems rarely have only one dependency.

Consider:

`RegistrationService`

which requires:

- `UserRepository`
- `UserValidator`
- `AuditLogger`
- `MessageSender`

The repository may itself require:

- Database connection

The resulting graph can be represented as:

`RegistrationService -> UserRepository -> Database`

and:

`RegistrationService -> MessageSender`

and:

`RegistrationService -> UserValidator`

and:

`RegistrationService -> AuditLogger`

This is a dependency graph.

A dependency chain becomes difficult to manage when:

- Components construct each other recursively.
- Circular dependencies appear.
- Lifetimes are inconsistent.
- Configuration is scattered.
- Ownership is unclear.

---

## 15. Circular Dependencies

A circular dependency has a graph such as:

`A -> B -> A`

A larger example might be:

`OrderService -> CustomerService -> OrderService`

Circular dependencies create problems with:

- Construction order
- Object lifetime
- Testing
- Responsibility boundaries
- Initialization
- Maintenance

A common solution is to introduce a more focused abstraction or move shared behavior into a third component.

The goal is not merely to eliminate cycles mechanically. The goal is to improve the responsibility boundaries that caused the cycle.

---

## 16. Composition Root

The composition root is where concrete implementations are assembled.

The Python `compose_application()` function demonstrates this.

It selects:

- Database
- Repository
- Notification sender
- Payment gateway
- Clock

and passes them into application services.

The JavaScript `composeApplication()` performs the same architectural role.

The C++ `ApplicationWithValidator` goes further by explicitly owning the constructed objects.

A useful design principle is:

> Construct infrastructure near the application boundary and inject it into business components.

This keeps construction decisions out of core business logic.

---

## 17. Dependency Containers

A dependency container automates dependency construction.

The Python and JavaScript examples include intentionally small containers.

The basic process is:

1. Register a dependency.
2. Register a factory for another dependency.
3. Resolve the higher-level service.
4. The container creates the required dependency chain.

For example:

`notificationService`

can resolve:

`repository`

and:

`sender`

automatically.

Containers can become useful in large applications, but they are not automatically superior to manual composition.

A container can also make dependencies less visible if used excessively.

Manual construction is often clearer when the dependency graph is small.

---

## 18. Dependency Lifetimes

A dependency has a lifetime describing how long an instance remains available.

Common lifetime categories are:

### Transient

A new instance is created each time it is requested.

Useful for stateless, inexpensive objects.

### Singleton

One instance is reused for the application or container lifetime.

Useful for some stateless infrastructure and shared resources, but shared mutable state must be considered carefully.

### Scoped

One instance exists for a defined scope such as a request.

This is common in web applications.

### Resource-Owned Lifetime

Some resources should be tied to explicit ownership.

Examples include:

- Database connections
- File handles
- Network sockets
- Transactions

C++ makes ownership especially explicit through RAII and smart pointers.

---

## 19. JavaScript Implementation

The JavaScript implementation demonstrates dependency injection using normal language features.

JavaScript does not require a special DI syntax.

Objects can be passed directly to constructors.

Functions can also be passed directly.

This is possible because functions are first-class values.

### Repository Injection

`InMemoryUserRepository` implements:

`findEmail(userId)`

`DatabaseUserRepository` uses a database abstraction.

The notification service only requires the repository behavior.

This makes the same business service usable with either implementation.

---

## 20. Asynchronous Dependencies

JavaScript applications frequently interact with asynchronous resources.

Examples include:

- Databases
- HTTP APIs
- Payment providers
- Message queues
- File systems

The JavaScript `AsyncPaymentGateway` demonstrates an asynchronous dependency.

`PaymentService` does not implement the gateway itself.

It receives the gateway and awaits its `charge()` operation.

This keeps asynchronous infrastructure separate from the business-level payment operation.

---

## 21. JavaScript Runtime Validation

JavaScript is dynamically typed, so dependency contracts may not be enforced statically.

`StrictNotificationService` performs runtime validation.

It checks that:

- A repository exists.
- A sender exists.
- The sender exposes `send()`.
- The repository exposes `findEmail()`.

This illustrates an important distinction between JavaScript and C++.

C++ can use compile-time interface checking through inheritance and virtual functions.

JavaScript often discovers contract violations at runtime unless a separate static type system is used.

---

## 22. JavaScript Testing

The JavaScript implementation contains simple assertion functions rather than requiring a third-party test framework.

`RecordingSender` captures calls.

`FakeClock` provides deterministic timestamps.

These demonstrate a central benefit of dependency injection:

External effects can be replaced with predictable test doubles.

---

## 23. C++ Industry-Style Case Study

The C++ program models an order-processing system.

The system contains:

- Users
- Products
- Orders
- Database
- Repositories
- Payment gateway
- Notification service
- Audit logger
- Validator
- Order service

The central operation is:

`OrderService::placeOrder()`

It performs the following sequence:

1. Validate the order.
2. Find the user.
3. Find every product.
4. Calculate the total.
5. Process payment.
6. Persist the order.
7. Record an audit event.
8. Notify the user.

This is substantially closer to an industry service than an isolated dependency example.

---

## 24. C++ Database Dependency

`IDatabase` represents the database contract.

It exposes operations for:

- Finding users
- Finding products
- Saving orders

`InMemoryDatabase` provides a concrete implementation.

The repositories receive the database through constructor injection.

For example:

`DatabaseUserRepository(IDatabase& database)`

The repository therefore does not need to know how the database is implemented.

A production implementation could replace the in-memory database with a real SQL database adapter without changing the high-level order service interface.

---

## 25. Repository Pattern

The repository separates persistence operations from business logic.

The case study defines:

- `IUserRepository`
- `IProductRepository`
- `IOrderRepository`

Concrete database repositories implement those contracts.

The advantage is separation of responsibilities.

`OrderService` is responsible for order processing.

The repositories are responsible for persistence access.

The database is responsible for storing and retrieving data.

---

## 26. Payment Dependency

The payment system is represented by:

`IPaymentGateway`

The concrete test implementation is:

`FakePaymentGateway`

`PaymentService` receives an `IPaymentGateway`.

This creates:

`PaymentService -> IPaymentGateway`

instead of:

`PaymentService -> SpecificPaymentProvider`

A real system could implement the interface with a provider-specific adapter.

The order-processing business logic would not need to know provider-specific details.

---

## 27. Notification Dependency

`INotificationService` represents notification behavior.

`ConsoleNotificationService` is the production-style demonstration implementation.

`RecordingNotificationService` is a test double.

The same `OrderService` works with both.

This is a direct demonstration of substitutability.

---

## 28. C++ Ownership and Lifetimes

C++ requires careful attention to object lifetime.

The case study uses:

`std::unique_ptr`

for owned application components.

References are used when a service borrows a dependency that is owned elsewhere.

For example:

`IDatabase&`

means that the repository does not own the database.

The application composition layer owns the database.

This separation avoids unnecessary copies and clarifies ownership.

A critical rule is that a referenced dependency must outlive the object using the reference.

---

## 29. Why C++ Makes Lifetime Design Important

In a garbage-collected language, object lifetime is largely managed automatically.

C++ provides more direct control.

That means DI design must consider:

- Ownership
- Borrowing
- Destruction order
- Shared ownership
- Resource cleanup
- Dangling references

RAII is particularly useful because resources can be tied to object lifetime.

`std::unique_ptr` is generally preferable to raw owning pointers when exclusive ownership is intended.

`std::shared_ptr` should be used only when shared ownership is genuinely required.

---

## 30. Dependency Chain in the C++ Case Study

The complete chain is:

`OrderService`

depends on:

`IUserRepository`

which depends on:

`IDatabase`

`OrderService` also depends on:

`IProductRepository`

which depends on:

`IDatabase`

`OrderService` also depends on:

`IOrderRepository`

which depends on:

`IDatabase`

Other dependencies are:

`OrderService -> INotificationService`

`OrderService -> IAuditLogger`

`OrderService -> PaymentService`

and:

`PaymentService -> IPaymentGateway`

This demonstrates that dependencies are not necessarily one level deep.

A service may depend on another service whose own implementation depends on infrastructure.

---

## 31. Error Handling

Dependency injection does not eliminate errors.

It changes where dependencies come from.

The implementations demonstrate failures including:

- Unknown user
- Unknown product
- Invalid order
- Invalid quantity
- Invalid payment amount
- Payment gateway failure
- Duplicate order
- Missing dependency configuration

The business service converts infrastructure and validation failures into appropriate operation results while recording audit information.

Production systems may use richer domain-specific exceptions, error types, result objects, or transaction management.

---

## 32. Database Transactions

The example uses an in-memory database and therefore does not implement real database transactions.

A production order system would normally need to consider transaction boundaries.

For example:

1. Calculate order.
2. Authorize or capture payment.
3. Persist order.
4. Publish an event.

These operations may involve different systems and cannot necessarily be made atomic with one database transaction.

This creates architectural concerns such as:

- Transaction boundaries
- Idempotency
- Retry behavior
- Payment reconciliation
- Partial failures
- Eventual consistency

Dependency injection can make these concerns easier to isolate because database and payment components can be represented by separate abstractions.

DI itself does not solve distributed transactions.

---

## 33. Edge Cases Demonstrated

The implementations intentionally cover edge cases.

### Unknown user

The repository returns no user.

The order or notification operation fails without performing unnecessary downstream work.

### Unknown product

The product repository returns no product.

The order cannot be calculated correctly.

### Empty order

Validation rejects an order without items.

### Zero quantity

Validation rejects a quantity that is not positive.

### Negative payment

Payment validation rejects non-positive amounts.

### Payment failure

The payment gateway can deliberately fail.

This makes failure behavior testable without depending on a real provider.

### Duplicate order

The in-memory database rejects an order ID that already exists.

---

## 34. Common Mistakes

### Constructing infrastructure inside business classes

Example:

`this.database = new Database()`

inside every business service.

This creates unnecessary coupling.

### Injecting concrete infrastructure everywhere

Using an abstraction only helps when the abstraction represents behavior that the consumer actually needs.

### Creating excessive interfaces

Not every class requires an interface.

An abstraction is useful when it provides meaningful substitution, isolation, architectural separation, or testing value.

### Overusing dependency containers

A container can hide where objects come from.

Manual construction is often easier to understand for small dependency graphs.

### Circular dependencies

Cycles make construction and ownership difficult.

### Incorrect lifetimes

A short-lived dependency should not be retained by a long-lived object unless its lifetime is intentionally extended.

### Shared mutable singletons

A singleton containing mutable state can create concurrency and testing problems.

### Interfaces that are too large

An interface should expose the behavior required by its consumer rather than unrelated operations.

---

## 35. Dependency Injection vs Direct Construction

| Characteristic | Direct Construction | Dependency Injection |
|---|---|---|
| Construction location | Inside consumer | Outside consumer |
| Coupling | Often stronger | Usually lower |
| Testing | Can be harder | Usually easier |
| Replacement | Requires code changes | Often configuration change |
| Complexity | Low for simple systems | Can increase architectural complexity |
| Visibility | Concrete dependency is obvious | Dependency is explicit through injection |
| Infrastructure isolation | Limited | Stronger |
| Suitable for | Small/simple objects | Complex services and infrastructure |

Neither approach is universally correct.

A simple value object does not necessarily benefit from DI.

A service that communicates with a database or payment provider often benefits significantly from explicit dependency boundaries.

---

## 36. Dependency Injection vs Dependency Inversion

These terms are related but not identical.

**Dependency Injection** is a technique for supplying dependencies from outside a component.

**Dependency Inversion** is an architectural principle that encourages high-level policy to avoid depending directly on low-level implementation details.

Dependency injection can be used to implement dependency inversion.

For example:

`OrderService(IPaymentGateway)`

uses dependency injection.

The architectural decision that `OrderService` should depend on the payment behavior abstraction rather than a particular provider reflects dependency inversion.

---

## 37. Dependency Injection vs Service Locator

A service locator provides a central mechanism from which components retrieve dependencies.

For example, a class may call:

`container.resolve("database")`

from inside its business method.

Dependency injection normally makes the dependency explicit:

`new Service(database)`

The latter makes the dependency visible in the constructor.

Service locators can reduce constructor complexity but may hide dependencies.

The small containers in this study are intentionally kept at the composition boundary rather than making business classes retrieve their own services.

---

## 38. Dependency Injection and Database Architecture

Database dependencies commonly appear in several layers:

`Business Service -> Repository -> Database Adapter -> Database`

For example:

`OrderService`

depends on:

`IOrderRepository`

which is implemented by:

`DatabaseOrderRepository`

which depends on:

`IDatabase`

which is implemented by:

`PostgreSQLDatabase`

or another database adapter.

This architecture separates:

- Business rules
- Persistence operations
- Database-specific mechanisms

A repository should not automatically become a dumping ground for every database operation. Its interface should represent meaningful persistence behavior required by the application.

---

## 39. Performance Considerations

Dependency injection introduces some architectural overhead.

Possible costs include:

- Additional object construction
- Interface or virtual dispatch
- Indirection
- Container resolution
- Memory for object graphs

In many business applications, these costs are small compared with:

- Database latency
- Network latency
- Disk I/O
- External API calls
- Serialization
- Encryption
- Large computations

C++ makes the runtime cost of virtual dispatch particularly relevant for high-frequency, performance-sensitive paths.

Performance should therefore be measured rather than assumed.

The C++ program includes a small timing example.

The correct optimization strategy is to preserve clear architecture unless profiling demonstrates that dependency indirection is actually a bottleneck.

---

## 40. Security Considerations

Dependency injection does not automatically make software secure.

It can support security by making security-sensitive components replaceable and testable.

Examples include injected:

- Authorization services
- Authentication providers
- Encryption services
- Secret managers
- Audit loggers
- Input validators
- Database access layers

Database dependencies require particular care.

Parameterized queries should be used instead of constructing SQL by string concatenation.

The Python database example uses:

`WHERE id = ?`

with a parameter tuple.

This helps prevent SQL injection in the demonstrated database operation.

Production database implementations should also use:

- Least-privilege database accounts
- Secure credential storage
- Connection security
- Transaction management
- Input validation
- Audit controls

---

## 41. Configuration and Environment Separation

Dependency injection allows environment-specific infrastructure to be selected at the composition boundary.

For example:

Development:

`InMemoryDatabase`

Testing:

`TestDatabase`

Production:

`PostgreSQLDatabase`

The business service can remain unchanged.

Similarly:

Testing:

`RecordingSender`

Production:

`EmailSender`

This reduces the need for business classes to contain environment-specific conditionals.

---

## 42. Testing Strategy

A well-designed dependency graph allows each component to be tested independently.

Examples from these implementations include:

- Fake database
- In-memory repository
- Recording sender
- Fake payment gateway
- Fake clock

A unit test can then verify business rules without requiring:

- Real email
- Real payment processing
- Real database
- Real clock
- Network access

Integration tests can separately verify the real infrastructure adapters.

This separation is important because unit and integration tests answer different questions.

---

## 43. Production Considerations

A production dependency-injection architecture should consider:

- Configuration validation
- Dependency lifetimes
- Resource ownership
- Thread safety
- Connection pooling
- Transaction boundaries
- Retry policies
- Timeout policies
- Circuit breakers
- Logging
- Monitoring
- Metrics
- Security
- Secret management
- Graceful shutdown
- Failure isolation

Dependency injection provides boundaries for these components but does not implement these operational concerns automatically.

---

## 44. Architectural Design Principles

A strong dependency design generally follows these principles:

1. Keep business logic independent of infrastructure where practical.
2. Inject required dependencies explicitly.
3. Keep abstractions small and focused.
4. Centralize composition.
5. Use test doubles for external effects.
6. Choose lifetimes deliberately.
7. Avoid circular dependencies.
8. Avoid unnecessary global state.
9. Avoid containers when simple manual composition is clearer.
10. Measure performance before optimizing abstraction overhead.
11. Keep database-specific logic outside business services.
12. Treat external systems as failure-prone dependencies.

---

## 45. What the Python Implementation Demonstrates

The Python script focuses on language-level flexibility and testability.

Important examples include:

- Tight coupling
- Constructor injection
- Method injection
- Setter-style injection
- Function injection
- `Protocol`
- Abstract base classes
- In-memory repository
- SQLite repository
- Dependency chains
- Composition root
- Fake clock
- Optional cache
- Dependency container
- Dependency lifetimes
- Error handling
- Unit tests
- Performance timing

Python's dynamic nature makes it particularly convenient to substitute objects and functions during testing.

---

## 46. What the JavaScript Implementation Demonstrates

The JavaScript file focuses on runtime object composition and application-level behavior.

Important examples include:

- Constructor injection
- Function injection
- Repository abstraction
- Database simulation
- Asynchronous dependencies
- Payment gateway injection
- Fake clock
- Cache dependency
- Runtime dependency validation
- Dependency container
- Object lifecycles
- Unit-style assertions
- Composition root

JavaScript's first-class functions and flexible object model make function and object injection natural.

Asynchronous dependency handling is especially important for web and server-side applications.

---

## 47. What the C++ Implementation Demonstrates

The C++ program focuses on explicit architecture, contracts, ownership, and a realistic business case.

The order-processing system contains:

- Database abstraction
- Repositories
- Payment gateway
- Notification service
- Audit logger
- Validator
- Order service
- Test doubles
- Manual composition
- Smart pointers
- References
- Error handling
- Edge cases
- Performance measurement

C++ makes dependency lifetime and ownership especially visible.

The case study therefore demonstrates not only injection but also the relationship between DI and resource management.

---

## 48. Practical Applications

Dependency injection is useful in systems containing replaceable or external components.

Examples include:

### Web applications

`Controller -> Service -> Repository -> Database`

### Financial applications

`TradeService -> MarketDataProvider`

`TradeService -> RiskEngine`

`TradeService -> BrokerGateway`

### E-commerce

`OrderService -> PaymentGateway`

`OrderService -> InventoryRepository`

`OrderService -> NotificationService`

### Cybersecurity

`SecurityService -> ThreatIntelProvider`

`SecurityService -> AuditLogger`

`SecurityService -> IdentityProvider`

### Data processing

`Pipeline -> Parser`

`Pipeline -> Validator`

`Pipeline -> Storage`

### Machine learning systems

`PredictionService -> ModelProvider`

`PredictionService -> FeatureStore`

`PredictionService -> MetricsCollector`

---

## 49. Important Distinction: Dependency Injection Is Not Dependency Creation

DI does not eliminate object creation.

The application still needs to create concrete objects.

The difference is where creation happens.

Without DI:

`Service creates dependency`

With DI:

`Composition layer creates dependency`

and:

`Composition layer gives dependency to service`

The responsibility has moved.

---

## 50. Important Distinction: Abstraction Is Not the Same as Injection

A class can use an abstraction without using dependency injection.

A class can also receive a concrete object through injection.

For example:

`Service(ConcreteDatabase)`

is still injection.

But it is more tightly coupled to that concrete type.

A stronger design may be:

`Service(IDatabase)`

The two concepts are therefore related but separate:

- Injection controls how dependencies are supplied.
- Abstraction controls what the consumer depends on.

---

## 51. Important Distinction: Reusability vs Abstraction

Reusable code does not require an interface for every component.

A pure function such as:

`calculateTotal(items)`

may already be highly reusable.

Adding an interface solely to create abstraction can increase complexity without providing meaningful value.

Good DI design asks:

- Does the dependency need replacement?
- Does it represent infrastructure?
- Does testing benefit from substitution?
- Does the abstraction clarify architecture?
- Is there a genuine variation in implementation?

---

## 52. Final Architectural Model

A mature dependency-injection architecture can be visualized as:

`Composition Root`

creates:

`Infrastructure`

and:

`Application Services`

and connects them through:

`Abstractions`

The business layer then operates through those abstractions.

A representative system is:

`Composition Root`

`-> Database`

`-> Repository`

`-> Payment Gateway`

`-> Notification Service`

`-> Audit Logger`

`-> Validator`

`-> Order Service`

The important architectural boundary is that the order service does not need to know how the concrete infrastructure was constructed.

This separation improves testability, substitution, maintainability, and control over application composition while requiring deliberate decisions about abstraction, ownership, lifetimes, complexity, and performance.
