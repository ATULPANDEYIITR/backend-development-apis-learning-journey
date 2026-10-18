from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Iterable, TypeVar
from uuid import UUID, uuid4
from datetime import datetime, timezone


# Service Layer Architecture separates responsibilities:
# Controller -> Service -> Repository
# Domain objects enforce business invariants rather than HTTP or database concerns.


class DomainError(Exception):
    """Base class for business-rule violations."""


class NotFoundError(DomainError):
    """Raised when a requested aggregate does not exist."""


class ValidationError(DomainError):
    """Raised when an input violates a domain invariant."""


class ConflictError(DomainError):
    """Raised when an operation conflicts with current state."""


class OrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class OrderLine:
    product_id: UUID
    quantity: int
    unit_price: int  # Store money as the smallest currency unit.

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValidationError("Order quantity must be positive.")
        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")

    @property
    def subtotal(self) -> int:
        return self.quantity * self.unit_price


@dataclass
class Order:
    id: UUID
    customer_id: UUID
    status: OrderStatus = OrderStatus.DRAFT
    lines: list[OrderLine] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_line(self, line: OrderLine) -> None:
        if self.status is not OrderStatus.DRAFT:
            raise ConflictError("Only draft orders can be modified.")

        for existing in self.lines:
            if existing.product_id == line.product_id:
                raise ConflictError("Product already exists in this order.")

        self.lines.append(line)

    def remove_line(self, product_id: UUID) -> None:
        if self.status is not OrderStatus.DRAFT:
            raise ConflictError("Only draft orders can be modified.")

        original_count = len(self.lines)
        self.lines = [
            line for line in self.lines if line.product_id != product_id
        ]

        if len(self.lines) == original_count:
            raise NotFoundError("Order line does not exist.")

    def total(self) -> int:
        return sum(line.subtotal for line in self.lines)

    def confirm(self) -> None:
        if self.status is not OrderStatus.DRAFT:
            raise ConflictError("Only draft orders can be confirmed.")
        if not self.lines:
            raise ValidationError("An order must contain at least one line.")

        self.status = OrderStatus.CONFIRMED

    def cancel(self) -> None:
        if self.status is OrderStatus.CANCELLED:
            raise ConflictError("Order is already cancelled.")

        if self.status is OrderStatus.CONFIRMED:
            # A real system could require a cancellation policy,
            # payment reversal, or fulfillment check here.
            raise ConflictError(
                "Confirmed orders require cancellation-policy processing."
            )

        self.status = OrderStatus.CANCELLED


@dataclass(frozen=True)
class Product:
    id: UUID
    name: str
    price: int
    active: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Product name cannot be empty.")
        if self.price < 0:
            raise ValidationError("Product price cannot be negative.")


T = TypeVar("T")


class Repository(Generic[T]):
    """
    Repository abstracts persistence.

    The service layer depends on this contract instead of knowing whether
    records live in memory, PostgreSQL, an API, or another storage system.
    """

    def get(self, entity_id: UUID) -> T | None:
        raise NotImplementedError

    def save(self, entity: T) -> None:
        raise NotImplementedError

    def list_all(self) -> list[T]:
        raise NotImplementedError


class InMemoryRepository(Repository[T]):
    def __init__(self) -> None:
        self._records: dict[UUID, T] = {}

    def get(self, entity_id: UUID) -> T | None:
        return self._records.get(entity_id)

    def save(self, entity: T) -> None:
        entity_id = getattr(entity, "id", None)
        if not isinstance(entity_id, UUID):
            raise ValidationError("Persisted entities require UUID identifiers.")
        self._records[entity_id] = entity

    def list_all(self) -> list[T]:
        return list(self._records.values())


class ProductRepository(InMemoryRepository[Product]):
    def find_active(self, product_id: UUID) -> Product | None:
        product = self.get(product_id)
        if product is not None and product.active:
            return product
        return None


class OrderRepository(InMemoryRepository[Order]):
    def find_by_customer(self, customer_id: UUID) -> list[Order]:
        return [
            order
            for order in self.list_all()
            if order.customer_id == customer_id
        ]


@dataclass(frozen=True)
class CreateOrderCommand:
    customer_id: UUID


@dataclass(frozen=True)
class AddOrderLineCommand:
    order_id: UUID
    product_id: UUID
    quantity: int


class OrderService:
    """
    The service coordinates a use case.

    It validates application-level input, loads required domain objects,
    invokes domain behavior, and persists the resulting aggregate.
    It does not know anything about HTTP status codes or SQL statements.
    """

    def __init__(
        self,
        orders: OrderRepository,
        products: ProductRepository,
    ) -> None:
        self.orders = orders
        self.products = products

    def create_order(self, command: CreateOrderCommand) -> Order:
        if not isinstance(command.customer_id, UUID):
            raise ValidationError("customer_id must be a UUID.")

        order = Order(id=uuid4(), customer_id=command.customer_id)
        self.orders.save(order)
        return order

    def add_line(self, command: AddOrderLineCommand) -> Order:
        if command.quantity <= 0:
            raise ValidationError("Quantity must be positive.")

        order = self.orders.get(command.order_id)
        if order is None:
            raise NotFoundError("Order does not exist.")

        product = self.products.find_active(command.product_id)
        if product is None:
            raise NotFoundError("Active product does not exist.")

        order.add_line(
            OrderLine(
                product_id=product.id,
                quantity=command.quantity,
                unit_price=product.price,
            )
        )
        self.orders.save(order)
        return order

    def confirm_order(self, order_id: UUID) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise NotFoundError("Order does not exist.")

        order.confirm()
        self.orders.save(order)
        return order

    def cancel_order(self, order_id: UUID) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise NotFoundError("Order does not exist.")

        order.cancel()
        self.orders.save(order)
        return order

    def customer_orders(self, customer_id: UUID) -> list[Order]:
        return self.orders.find_by_customer(customer_id)


class OrderController:
    """
    A controller represents the delivery boundary.

    In a web application, these methods would translate HTTP requests into
    commands and domain exceptions into HTTP responses. The controller does
    not calculate order totals or decide whether an order may be confirmed.
    """

    def __init__(self, service: OrderService) -> None:
        self.service = service

    def post_order(self, payload: dict) -> dict:
        try:
            customer_id = UUID(str(payload["customer_id"]))
            order = self.service.create_order(
                CreateOrderCommand(customer_id=customer_id)
            )
            return {
                "status": 201,
                "body": self._serialize(order),
            }
        except (KeyError, ValueError, ValidationError) as exc:
            return {"status": 400, "body": {"error": str(exc)}}
        except DomainError as exc:
            return {"status": 409, "body": {"error": str(exc)}}

    def post_line(self, payload: dict) -> dict:
        try:
            command = AddOrderLineCommand(
                order_id=UUID(str(payload["order_id"])),
                product_id=UUID(str(payload["product_id"])),
                quantity=int(payload["quantity"]),
            )
            order = self.service.add_line(command)
            return {
                "status": 200,
                "body": self._serialize(order),
            }
        except (KeyError, ValueError, ValidationError) as exc:
            return {"status": 400, "body": {"error": str(exc)}}
        except NotFoundError as exc:
            return {"status": 404, "body": {"error": str(exc)}}
        except ConflictError as exc:
            return {"status": 409, "body": {"error": str(exc)}}

    def post_confirm(self, order_id: str) -> dict:
        try:
            order = self.service.confirm_order(UUID(order_id))
            return {"status": 200, "body": self._serialize(order)}
        except ValueError as exc:
            return {"status": 400, "body": {"error": str(exc)}}
        except NotFoundError as exc:
            return {"status": 404, "body": {"error": str(exc)}}
        except ConflictError as exc:
            return {"status": 409, "body": {"error": str(exc)}}

    @staticmethod
    def _serialize(order: Order) -> dict:
        return {
            "id": str(order.id),
            "customer_id": str(order.customer_id),
            "status": order.status.value,
            "lines": [
                {
                    "product_id": str(line.product_id),
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "subtotal": line.subtotal,
                }
                for line in order.lines
            ],
            "total": order.total(),
        }


def demonstrate_basic_domain_logic() -> None:
    product_id = uuid4()
    customer_id = uuid4()

    order = Order(id=uuid4(), customer_id=customer_id)
    order.add_line(
        OrderLine(
            product_id=product_id,
            quantity=2,
            unit_price=1500,
        )
    )

    print("Domain total:", order.total())
    order.confirm()
    print("Domain status:", order.status.value)

    try:
        order.add_line(
            OrderLine(
                product_id=uuid4(),
                quantity=1,
                unit_price=500,
            )
        )
    except ConflictError as exc:
        print("Expected domain rejection:", exc)


def demonstrate_layered_application() -> None:
    products = ProductRepository()
    orders = OrderRepository()

    product_id = uuid4()
    customer_id = uuid4()

    products.save(
        Product(
            id=product_id,
            name="Mechanical Keyboard",
            price=8500,
        )
    )

    service = OrderService(orders, products)
    controller = OrderController(service)

    created = controller.post_order(
        {"customer_id": str(customer_id)}
    )
    print("Create response:", created)

    order_id = created["body"]["id"]

    line_response = controller.post_line(
        {
            "order_id": order_id,
            "product_id": str(product_id),
            "quantity": 2,
        }
    )
    print("Line response:", line_response)

    confirmation = controller.post_confirm(order_id)
    print("Confirmation response:", confirmation)

    invalid_change = controller.post_line(
        {
            "order_id": order_id,
            "product_id": str(uuid4()),
            "quantity": 1,
        }
    )
    print("Invalid post-confirmation change:", invalid_change)


def demonstrate_service_testability() -> None:
    """
    The service can be tested without an HTTP server or PostgreSQL.
    Repositories provide deterministic persistence doubles.
    """

    products = ProductRepository()
    orders = OrderRepository()

    product_id = uuid4()
    customer_id = uuid4()

    products.save(
        Product(
            id=product_id,
            name="USB-C Dock",
            price=12000,
        )
    )

    service = OrderService(orders, products)
    order = service.create_order(
        CreateOrderCommand(customer_id=customer_id)
    )

    service.add_line(
        AddOrderLineCommand(
            order_id=order.id,
            product_id=product_id,
            quantity=1,
        )
    )

    assert order.total() == 12000
    service.confirm_order(order.id)
    assert order.status is OrderStatus.CONFIRMED

    print("Service-level test passed.")


if __name__ == "__main__":
    print("=== Domain logic ===")
    demonstrate_basic_domain_logic()

    print("\n=== Controller / Service / Repository flow ===")
    demonstrate_layered_application()

    print("\n=== Service testability ===")
    demonstrate_service_testability()
