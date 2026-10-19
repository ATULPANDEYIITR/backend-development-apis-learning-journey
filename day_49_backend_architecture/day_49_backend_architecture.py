from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable


class Layer(str, Enum):
    API = "api"
    APPLICATION = "application"
    DOMAIN = "domain"
    INFRASTRUCTURE = "infrastructure"


class ArchitectureError(Exception):
    """Raised when an architectural dependency or registration rule is violated."""


class AuthorizationError(Exception):
    """Raised when an operation violates the application's architecture policy."""


@dataclass(frozen=True)
class Dependency:
    source: str
    target: str

    def validate(self) -> None:
        forbidden = {
            (Layer.DOMAIN.value, Layer.API.value),
            (Layer.DOMAIN.value, Layer.INFRASTRUCTURE.value),
            (Layer.APPLICATION.value, Layer.API.value),
        }
        if (self.source, self.target) in forbidden:
            raise ArchitectureError(
                f"Forbidden dependency: {self.source} -> {self.target}"
            )


@dataclass
class ArchitectureGraph:
    dependencies: list[Dependency] = field(default_factory=list)

    def add(self, source: Layer, target: Layer) -> None:
        dependency = Dependency(source.value, target.value)
        dependency.validate()
        self.dependencies.append(dependency)

    def validate(self) -> bool:
        for dependency in self.dependencies:
            dependency.validate()
        return True


def demonstrate_layered_architecture() -> ArchitectureGraph:
    """
    A layered architecture keeps responsibilities separated by technical layer.
    The dependency direction is intentionally toward lower-level services.
    """
    graph = ArchitectureGraph()

    graph.add(Layer.API, Layer.APPLICATION)
    graph.add(Layer.APPLICATION, Layer.DOMAIN)
    graph.add(Layer.APPLICATION, Layer.INFRASTRUCTURE)

    print("Layered architecture")
    print("  API -> Application")
    print("  Application -> Domain")
    print("  Application -> Infrastructure")
    print(f"  Valid dependency graph: {graph.validate()}")

    try:
        graph.add(Layer.DOMAIN, Layer.INFRASTRUCTURE)
    except ArchitectureError as exc:
        print(f"  Rejected dependency: {exc}")

    return graph


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    email: str

    def __post_init__(self) -> None:
        if self.customer_id <= 0:
            raise ValueError("customer_id must be positive")
        if not self.name.strip():
            raise ValueError("customer name cannot be empty")
        if "@" not in self.email:
            raise ValueError("customer email must contain '@'")


class CustomerRepository:
    """Repository abstraction used by the application layer."""

    def find_by_id(self, customer_id: int) -> Customer | None:
        raise NotImplementedError

    def save(self, customer: Customer) -> None:
        raise NotImplementedError


class InMemoryCustomerRepository(CustomerRepository):
    """Infrastructure implementation of the repository abstraction."""

    def __init__(self) -> None:
        self._customers: dict[int, Customer] = {}

    def find_by_id(self, customer_id: int) -> Customer | None:
        return self._customers.get(customer_id)

    def save(self, customer: Customer) -> None:
        self._customers[customer.customer_id] = customer


class CustomerService:
    """
    Application service.

    The service coordinates a use case but does not expose database details
    to callers. It depends on the repository contract rather than a concrete
    persistence mechanism.
    """

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def register_customer(self, customer: Customer) -> Customer:
        if self.repository.find_by_id(customer.customer_id) is not None:
            raise ValueError("customer already exists")

        self.repository.save(customer)
        return customer

    def get_customer(self, customer_id: int) -> Customer:
        customer = self.repository.find_by_id(customer_id)
        if customer is None:
            raise LookupError(f"customer {customer_id} does not exist")
        return customer


class ModularMonolith:
    """
    A modular monolith deploys as one process while keeping business areas
    internally separated. Modules communicate through explicit public services.
    """

    def __init__(self) -> None:
        self.customers = InMemoryCustomerRepository()
        self.customer_service = CustomerService(self.customers)

    def register_customer(self, customer: Customer) -> Customer:
        return self.customer_service.register_customer(customer)

    def find_customer(self, customer_id: int) -> Customer:
        return self.customer_service.get_customer(customer_id)


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    amount: float

    def __post_init__(self) -> None:
        if self.order_id <= 0 or self.customer_id <= 0:
            raise ValueError("identifiers must be positive")
        if self.amount <= 0:
            raise ValueError("order amount must be positive")


class OrderRepository:
    def save(self, order: Order) -> None:
        raise NotImplementedError

    def find(self, order_id: int) -> Order | None:
        raise NotImplementedError


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self.orders: dict[int, Order] = {}

    def save(self, order: Order) -> None:
        self.orders[order.order_id] = order

    def find(self, order_id: int) -> Order | None:
        return self.orders.get(order_id)


class OrderApplicationService:
    def __init__(
        self,
        customer_service: CustomerService,
        order_repository: OrderRepository,
    ) -> None:
        self.customer_service = customer_service
        self.order_repository = order_repository

    def create_order(self, order: Order) -> Order:
        self.customer_service.get_customer(order.customer_id)

        if self.order_repository.find(order.order_id):
            raise ValueError("order already exists")

        self.order_repository.save(order)
        return order


def demonstrate_modular_monolith() -> None:
    application = ModularMonolith()
    application.register_customer(
        Customer(101, "Asha Mehta", "asha@example.com")
    )

    order_repository = InMemoryOrderRepository()
    order_service = OrderApplicationService(
        application.customer_service,
        order_repository,
    )

    order = order_service.create_order(Order(5001, 101, 14999.0))

    print("\nModular monolith")
    print(f"  Customer module owns customer  : {order.customer_id}")
    print(f"  Order module owns order        : {order.order_id}")
    print(f"  Order amount                   : {order.amount:.2f}")

    try:
        order_service.create_order(Order(5002, 999, 500.0))
    except LookupError as exc:
        print(f"  Cross-module validation failed: {exc}")


class PaymentGateway:
    def charge(self, amount: float) -> str:
        raise NotImplementedError


class FakePaymentGateway(PaymentGateway):
    def charge(self, amount: float) -> str:
        if amount <= 0:
            raise ValueError("payment amount must be positive")
        return f"PAY-{int(amount * 100)}"


class PaymentDomain:
    """
    Domain logic has no knowledge of HTTP, databases, payment SDKs, or
    framework-specific objects.
    """

    @staticmethod
    def validate_amount(amount: float) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > 1_000_000:
            raise ValueError("amount exceeds domain transaction limit")


class PaymentUseCase:
    """
    Clean architecture application boundary.

    External systems are represented by ports. Concrete adapters are supplied
    from the composition root.
    """

    def __init__(self, gateway: PaymentGateway) -> None:
        self.gateway = gateway

    def execute(self, amount: float) -> str:
        PaymentDomain.validate_amount(amount)
        return self.gateway.charge(amount)


def demonstrate_clean_architecture() -> None:
    gateway = FakePaymentGateway()
    use_case = PaymentUseCase(gateway)
    transaction_id = use_case.execute(2750.50)

    print("\nClean architecture")
    print("  Domain       -> business rules only")
    print("  Application  -> use-case orchestration")
    print("  Adapter      -> payment gateway implementation")
    print(f"  Transaction  -> {transaction_id}")

    try:
        use_case.execute(0)
    except ValueError as exc:
        print(f"  Domain rejected invalid payment: {exc}")


@dataclass
class ArchitectureTest:
    name: str
    action: Callable[[], None]

    def run(self) -> bool:
        try:
            self.action()
            print(f"[PASS] {self.name}")
            return True
        except Exception as exc:
            print(f"[FAIL] {self.name}: {exc}")
            return False


def run_architecture_tests() -> None:
    graph = ArchitectureGraph()
    graph.add(Layer.API, Layer.APPLICATION)
    graph.add(Layer.APPLICATION, Layer.DOMAIN)

    tests = [
        ArchitectureTest(
            "valid layered dependency",
            lambda: graph.validate(),
        ),
        ArchitectureTest(
            "customer validation",
            lambda: Customer(1, "Ravi", "ravi@example.com"),
        ),
        ArchitectureTest(
            "payment domain rejects zero",
            lambda: _expect_value_error(
                lambda: PaymentDomain.validate_amount(0)
            ),
        ),
    ]

    passed = sum(test.run() for test in tests)
    print(f"Architecture tests passed: {passed}/{len(tests)}")


def _expect_value_error(action: Callable[[], None]) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("ValueError was expected")


def compare_architectures() -> None:
    print("\nArchitectural trade-offs")
    print("  Layered architecture : simple technical separation; dependencies")
    print("                          often follow layer boundaries.")
    print("  Modular monolith     : one deployment with explicit business modules.")
    print("                          It can enforce domain boundaries without")
    print("                          introducing distributed-system complexity.")
    print("  Clean architecture   : dependency direction points toward policy.")
    print("                          Infrastructure implements ports owned inward.")

    print("\nPerformance considerations")
    print("  Layer boundaries add little runtime cost when implemented as calls.")
    print("  Modular boundaries can reduce accidental cross-domain coupling.")
    print("  Clean architecture may introduce additional abstractions, but these")
    print("  can improve testing and replacement of external infrastructure.")

    print("\nProduction concerns")
    print("  Architectural rules should be checked in CI, not only documented.")
    print("  Dependency injection should compose concrete infrastructure at the edge.")
    print("  Modules should expose narrow public interfaces and protect internal state.")


def main() -> None:
    print("BACKEND ARCHITECTURE LABORATORY")
    print("=" * 32)

    demonstrate_layered_architecture()
    demonstrate_modular_monolith()
    demonstrate_clean_architecture()
    run_architecture_tests()
    compare_architectures()


if __name__ == "__main__":
    main()
