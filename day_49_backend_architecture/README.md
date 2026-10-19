# Backend Architecture: Layered Architecture, Modular Monolith, and Clean Architecture

## Scope

Backend architecture determines how responsibilities, dependencies, business rules, infrastructure, and deployment boundaries are arranged inside a software system.

This repository treats three related architectural approaches as distinct mechanisms:

| Architecture | Primary concern | Boundary being emphasized |
|---|---|---|
| Layered architecture | Separation of technical responsibilities | API, application, domain, infrastructure layers |
| Modular monolith | Separation of business capabilities within one deployment | Explicit business modules and their public interfaces |
| Clean architecture | Direction of dependencies around business policy | Inner domain/application policy isolated from external mechanisms |

These approaches are not mutually exclusive. A modular monolith can use layers inside each module, while clean-architecture dependency rules can govern the direction of dependencies inside those layers.

The central distinction is architectural intent. Layering organizes technical responsibilities. Modularization organizes business capabilities. Clean architecture controls dependency direction so that business policy is not owned by external frameworks or infrastructure.

## Core Architectural Relationships

A useful backend can be represented as a combination of boundaries rather than as a choice between three unrelated patterns.

    HTTP / API / Messaging
              |
              v
    Application Services
              |
              v
         Domain Policy
              ^
              |
       Ports / Interfaces
              ^
              |
    Infrastructure Adapters

The layered view explains where responsibilities live.

The modular-monolith view explains which business capability owns those responsibilities.

The clean-architecture view explains which direction dependencies are permitted to travel.

For example, a billing module can contain an API adapter, application service, domain rules, and infrastructure adapter. Another module can expose customer information through a controlled application service without directly accessing billing's persistence implementation.

## Layered Architecture

Layered architecture divides the backend according to technical responsibility.

### API Layer

The API layer handles delivery concerns such as HTTP requests, serialization, authentication middleware, request validation, and response formatting.

It should not contain core billing, ordering, or account policy. An HTTP controller should translate an incoming request into an application-level operation rather than deciding business rules itself.

A useful dependency direction is:

`API -> Application -> Domain`

Infrastructure is normally used by application-level orchestration or through explicit abstractions.

### Application Layer

The application layer coordinates use cases.

It determines the sequence in which domain operations, repositories, external services, and transactions are invoked. It should not become a second domain layer containing scattered business rules.

For example, an invoice use case can:

- Locate the customer.
- Verify that the customer is eligible.
- Invoke the invoice domain operation.
- Request payment authorization through a port.
- Persist the resulting state.

The application service coordinates these actions while domain objects retain rules that belong to the business itself.

### Domain Layer

The domain layer contains business policy that should remain meaningful even if the system changes its HTTP framework, database, cloud provider, or external payment vendor.

A rule such as "a suspended account cannot create a billable transaction" belongs closer to the domain than to an HTTP controller.

The Python, C++, and Java implementations represent domain state using concrete objects and validation rather than placing all rules in request handlers.

A particularly important boundary is that the domain should not need to know whether persistence uses PostgreSQL, an in-memory repository, a REST API, or a message broker.

### Infrastructure Layer

Infrastructure contains technical mechanisms such as database implementations, external payment adapters, filesystem access, message brokers, caches, and framework integrations.

Infrastructure is necessary, but it should not become the owner of business policy merely because it contains the concrete implementation.

The Python example uses `InMemoryCustomerRepository` and `FakePaymentGateway` to demonstrate this separation without requiring external packages.

## Modular Monolith

A modular monolith is a single deployable application whose internal structure is divided into explicit business modules.

It is not simply a large collection of packages.

A meaningful module owns a coherent business capability and exposes a controlled public interface.

The example systems use concepts such as:

- Customer or identity management.
- Billing.
- Orders.
- Payments.
- Auditing.

The important boundary is that the billing module should use a customer capability rather than reaching into the customer's private repository.

This distinction allows the application to remain one deployment while reducing accidental coupling.

### Module Ownership

A strong module owns its internal state.

For example:

`BillingModule -> AccountService`

is a controlled interaction.

Direct access such as:

`BillingModule -> AccountRepository.internalMap`

would weaken the boundary because billing now depends on another module's persistence representation.

The JavaScript implementation demonstrates this through `AccountModule`, `BillingModule`, and `AuditModule`. The modules share an `EventEmitter` for an application event without exposing each other's internal data structures.

### Public Interfaces

A modular monolith should expose a small public surface.

A module might expose:

`registerAccount(account)`

or:

`getAccountStatus(accountId)`

while keeping its repository, validation helpers, and internal data structures private.

This makes later refactoring easier because callers depend on business capabilities instead of storage details.

### Events Inside a Monolith

The JavaScript implementation uses Node.js `EventEmitter` to demonstrate an internal event boundary.

When billing completes, it emits a `billing.completed` event. The audit module consumes that event without requiring billing to know how audit records are stored.

This is different from distributed microservices. The modules still execute inside one Node.js process and do not require network communication.

## Clean Architecture

Clean architecture focuses strongly on dependency direction.

The key idea is that high-value business policy should not depend directly on lower-level implementation mechanisms.

A common dependency direction is:

`External Adapter -> Application Port -> Application/Domain Policy`

The concrete direction depends on the exact design, but the important rule is that infrastructure should implement an abstraction required by the inner policy rather than forcing the inner policy to import infrastructure.

### Ports and Adapters

A payment use case may require:

`PaymentGateway.authorize(amount)`

The use case does not need to know whether authorization is implemented by:

- A bank API.
- A payment processor SDK.
- A test double.
- A local simulator.

The concrete adapter implements the required capability.

Python represents this with `PaymentGateway` and `FakePaymentGateway`.

C++ represents it through the abstract `PaymentPort` and `SimulatedBankAdapter`.

Java represents it through `PaymentGateway` and `BankGatewayAdapter`.

These implementations are deliberately different in structure but demonstrate the same architectural relationship.

### Composition Boundary

Concrete dependencies should be assembled at the outer edge of the application.

The JavaScript `buildApplication()` function serves as a composition root. It constructs the repository, modules, event bus, payment adapter, and use cases.

This keeps infrastructure selection away from the domain policy.

A production application may perform the same assembly through a dependency-injection framework, configuration system, or explicit bootstrap code.

## Python Implementation

The Python program begins with an executable dependency graph.

`ArchitectureGraph` and `Dependency` represent layer relationships and reject prohibited dependencies such as a domain layer directly depending on infrastructure.

The layered example establishes:

`API -> Application`

and:

`Application -> Domain`

while rejecting:

`Domain -> Infrastructure`.

The program then builds a modular-monolith example around customers and orders. `CustomerService` provides the application-facing capability, while `InMemoryCustomerRepository` remains an infrastructure implementation.

The order service depends on the customer service instead of manipulating the customer repository directly. This demonstrates a module boundary based on a capability rather than a database structure.

The clean-architecture example introduces `PaymentGateway` as a port. `PaymentUseCase` performs domain validation and calls the gateway without knowing the implementation mechanism.

The script also includes executable validation tests covering dependency validity, domain validation, and invalid payment amounts.

The final architectural comparison highlights an important distinction: these approaches can coexist rather than being competing deployment models.

## JavaScript Implementation

The JavaScript program emphasizes Node.js-specific behavior.

`EventEmitter` is used to model internal application events. The billing module emits `billing.completed`, while the audit module subscribes to the event.

This demonstrates how modules can communicate without directly coupling their internal storage structures.

The JavaScript implementation also uses asynchronous methods to represent realistic repository and gateway boundaries. Even the in-memory repository uses `async` methods so the application service depends on a contract that could later be backed by an actual asynchronous database.

The clean-architecture portion validates the required shape of a payment adapter at runtime because JavaScript does not provide Java-style interface declarations.

The composition function assembles the modules and concrete adapters at the outer boundary.

Account suspension is also modeled as domain state. Billing and payment operations reject suspended accounts, demonstrating that business state must be enforced independently of the delivery mechanism.

## C++ Case Study

The C++ program models a payment platform transitioning from a technically layered monolith toward explicit module boundaries.

`ArchitecturePolicy` acts as an executable architectural rule set. It prevents domain code from directly depending on API or infrastructure layers.

`CustomerModule` owns customer state and exposes controlled operations.

`OrderModule` receives a `CustomerModule` reference and a `PaymentPort`. It validates order identity, amount, customer existence, and customer status before authorizing payment.

The use of `PaymentPort` is significant. The order module depends on the capability it needs, while `SimulatedBankAdapter` provides the concrete external implementation.

The program also handles a failure after order insertion by removing the in-memory order if payment authorization fails. This demonstrates a simplified consistency boundary and makes the failure behavior explicit.

C++ ownership and polymorphism are used only where they improve the architectural model. The abstract `PaymentPort` is not present merely to demonstrate inheritance. It represents a replaceable infrastructure boundary.

The case study also reports architectural dependencies and validates them before execution.

## Java Implementation

The Java implementation presents the same architectural principles through an enterprise-oriented domain model.

`Account`, `Invoice`, and `AccountStatus` provide explicit domain types. Java records are useful here because account and invoice identity/value information can be represented compactly while retaining validation in their constructors.

`AccountRepository` defines a persistence abstraction, while `InMemoryAccountRepository` supplies an infrastructure implementation.

`AccountService` provides application-level operations such as opening an account and requiring an active account.

`BillingModule` represents a business module that uses the account service rather than accessing the account repository directly.

The payment boundary is represented by `PaymentGateway`, implemented by `BankGatewayAdapter`.

`DependencyPolicy` provides an explicit architectural policy using Java collections and an `EnumMap`. It rejects forbidden relationships rather than relying solely on comments.

This structure demonstrates how Java's type system can make architectural concepts visible through interfaces, enums, records, collections, and explicit service boundaries.

## SQL Data Model

The PostgreSQL implementation treats architecture as data that can be inspected and constrained.

The `backend_module` table records business modules and their public APIs.

`architecture_dependency` records relationships between modules and architectural layers.

The database applies `CHECK` constraints to prevent domain-to-infrastructure and domain-to-API dependencies.

This is useful because an architectural rule that exists only in documentation can drift. A database constraint provides direct integrity enforcement for data represented in the model.

The operational domain contains:

- `account` for business state.
- `invoice` for billing records.
- `payment_port` for infrastructure capabilities.
- `payment_transaction` for external authorization results.
- `architectural_review` for governance of dependency decisions.

Foreign keys ensure that invoices reference real accounts and that payment transactions reference real invoices and payment ports.

Indexes target actual access patterns, such as finding dependencies by source module, retrieving invoices for an account, and locating payment transactions for an invoice.

The SQL script also demonstrates transactions. An invalid negative invoice amount is rejected by a database constraint and rolled back.

## Architecture Comparison

| Concern | Layered | Modular Monolith | Clean Architecture |
|---|---|---|---|
| Main boundary | Technical layer | Business module | Dependency direction |
| Primary benefit | Responsibility separation | Business ownership | Policy isolation |
| Typical unit | API/application/domain/infrastructure | Billing/orders/identity/payments | Domain/use case/port/adapter |
| Deployment implication | None by itself | Usually one deployable application | None by itself |
| Database access | Usually isolated below application | Ideally owned by module | Implemented by an outer adapter |
| External services | Infrastructure concern | Owned by relevant module | Adapter implementing an inward-facing port |
| Main failure mode | Layer leakage | Cross-module coupling | Dependency inversion failure |

These distinctions matter because a system can have one architecture style without necessarily satisfying the others.

A layered application can still have badly coupled business modules.

A modular monolith can still allow infrastructure dependencies to leak into domain code.

A clean-architecture implementation can still have poor module ownership.

The strongest designs treat these as separate architectural questions.

## Dependency Direction

Dependency direction is more important than the number of folders.

A structure such as:

`controllers/`

`services/`

`repositories/`

`models/`

does not automatically create a layered architecture.

The actual dependencies must respect the intended boundaries.

For example, if a domain service imports a PostgreSQL driver directly, the directory structure may look layered while the dependency graph is not.

The executable examples therefore validate relationships rather than merely displaying directory names.

## Edge Cases and Failure Modes

Architectural boundaries fail in predictable ways.

### Layer Leakage

A controller containing pricing, payment, or account-state policy becomes difficult to test independently and causes transport concerns to become business concerns.

### Repository Leakage

One module reaching directly into another module's repository exposes persistence details and creates coupling around implementation rather than business capability.

### Domain Infrastructure Dependency

A domain object that imports a database driver cannot be reused easily in another execution environment and becomes difficult to test without infrastructure.

### God Module

A modular monolith can still fail if one module owns unrelated business capabilities. A module boundary is useful only when ownership is coherent.

### False Abstraction

Adding interfaces everywhere without a meaningful substitution boundary increases complexity without improving architecture.

The examples use abstractions where a replacement boundary exists, such as payment gateways and repositories.

### Circular Dependencies

A module A depending on module B while module B depends directly on module A can make ownership unclear.

An event or explicitly defined shared application capability can sometimes remove such coupling, but events should not become an uncontrolled hidden dependency mechanism.

## Testing Architectural Rules

Architecture should be testable.

The Python implementation executes dependency checks directly.

The C++ implementation validates architectural dependencies before running the case study.

The Java implementation makes dependency policy executable through `DependencyPolicy`.

The SQL model expresses selected rules through database constraints.

These approaches address different layers of governance. Static architecture tests can detect dependency violations in source code, while database constraints protect persisted architectural metadata.

## Performance Considerations

Layering itself normally introduces negligible runtime cost when boundaries are implemented as ordinary in-process method calls.

The main performance risks come from inappropriate boundaries rather than from the concept of layering.

A modular monolith avoids network serialization, network latency, service discovery, and distributed transaction overhead that would appear if every module became an independent service.

Clean architecture can introduce additional interface dispatch, object construction, or mapping operations. These costs are usually small compared with database and network operations, but unnecessary abstraction can still increase complexity and allocation pressure.

Performance-sensitive systems should therefore measure actual bottlenecks rather than removing architectural boundaries based solely on theoretical call overhead.

## Security Considerations

Architecture contributes to security when boundaries prevent unauthorized access to sensitive capabilities.

A module should expose only the operations required by other modules.

For example, a billing module should not receive unrestricted access to another module's persistence layer merely because both execute inside one process.

Infrastructure adapters should also prevent secrets, tokens, and credentials from entering domain objects.

Authentication and authorization should be enforced at the appropriate application boundary, while domain rules should continue to enforce business validity. Authorization checks should not be treated as a replacement for domain invariants.

## Debugging and Observability

Architectural boundaries provide useful debugging points.

Application services can log use-case identifiers.

Module boundaries can record business events.

Infrastructure adapters can record external request identifiers and latency.

The JavaScript event-driven example demonstrates how a billing event can be observed by an audit module without tightly coupling the two implementations.

Observability should preserve the distinction between business events and infrastructure diagnostics. A database timeout is not itself a business event, while an invoice authorization may be a meaningful business event.

## Production Considerations

A practical backend can combine all three approaches.

A production billing backend might use a modular monolith as its deployment structure. Each business module can internally use layered responsibilities. Clean-architecture dependency rules can prevent the domain from importing database or external-service infrastructure.

The result can be represented as:

`One deployment`

containing:

`Identity Module | Billing Module | Order Module | Payment Module`

where each module contains boundaries such as:

`API -> Application -> Domain`

and external mechanisms enter through:

`Ports <- Infrastructure Adapters`

The important property is not the number of architectural patterns used. It is whether ownership, dependencies, business policy, and technical mechanisms remain understandable and enforceable as the backend grows.
