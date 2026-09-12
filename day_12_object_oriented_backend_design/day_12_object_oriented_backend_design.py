"""
Object-Oriented Backend Design
===============================

A comprehensive, executable study file covering:

- Classes and objects
- Constructors and object state
- Instance, class, and static methods
- Encapsulation
- Properties and validation
- Abstraction
- Abstract base classes
- Inheritance
- Method overriding
- Polymorphism
- Duck typing
- Composition
- Aggregation
- Association
- Dependency injection
- Interfaces through protocols
- Dataclasses
- Enums
- Exceptions
- Repository and service layers
- Domain models
- Backend-oriented architecture
- SOLID design principles
- Coupling and cohesion
- Dependency inversion
- Testing and mocking concepts
- Serialization
- Validation
- Transactions and unit-of-work concepts
- Logging
- Security considerations
- Performance considerations
- Common mistakes and design trade-offs

The examples use only Python's standard library.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    ClassVar,
    Iterable,
    Iterator,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
)
import hashlib
import hmac
import json
import logging
import math
import time
import uuid


# ============================================================================
# 1. FUNDAMENTAL OBJECT-ORIENTED CONCEPTS
# ============================================================================

print("\n" + "=" * 80)
print("1. FUNDAMENTAL OBJECT-ORIENTED CONCEPTS")
print("=" * 80)


class User:
    """
    A class is a blueprint describing data and behavior.

    Each object created from this class is an instance.
    """

    def __init__(self, username: str, email: str) -> None:
        self.username = username
        self.email = email

    def describe(self) -> str:
        return f"{self.username} <{self.email}>"


user_a = User("alice", "alice@example.com")
user_b = User("bob", "bob@example.com")

print("Class:", User.__name__)
print("Object:", user_a.describe())
print("Another object:", user_b.describe())
print("Different objects:", user_a is not user_b)


# Instance attributes belong to individual objects.
user_a.email = "alice@new-example.com"

print("Alice email:", user_a.email)
print("Bob email remains:", user_b.email)


# ============================================================================
# 2. INSTANCE METHODS, CLASS METHODS, AND STATIC METHODS
# ============================================================================

print("\n" + "=" * 80)
print("2. INSTANCE, CLASS, AND STATIC METHODS")
print("=" * 80)


class Account:
    """
    Demonstrates the three common method categories.

    Instance method:
        Receives self and works with object state.

    Class method:
        Receives cls and works with class-level state or alternative
        constructors.

    Static method:
        Receives neither self nor cls automatically. It is logically
        associated with the class but does not require object/class state.
    """

    bank_name: ClassVar[str] = "Example Bank"

    def __init__(self, owner: str, balance: float = 0.0) -> None:
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit must be positive.")
        self.balance += amount

    @classmethod
    def from_string(cls, value: str) -> "Account":
        """
        Alternative constructor.

        Example:
            Account.from_string("alice,1500")
        """
        owner, balance_text = value.split(",", maxsplit=1)
        return cls(owner.strip(), float(balance_text))

    @staticmethod
    def is_valid_amount(amount: float) -> bool:
        return math.isfinite(amount) and amount > 0


account = Account.from_string("alice,1500")
account.deposit(250)

print("Owner:", account.owner)
print("Balance:", account.balance)
print("Bank:", Account.bank_name)
print("Valid amount:", Account.is_valid_amount(100))


# ============================================================================
# 3. ENCAPSULATION
# ============================================================================

print("\n" + "=" * 80)
print("3. ENCAPSULATION")
print("=" * 80)


class BankAccount:
    """
    Encapsulation means keeping internal state and its rules together.

    Python does not enforce traditional private fields as strictly as some
    languages. A leading underscore communicates that an attribute is
    implementation-oriented and should not normally be manipulated directly.

    Name-mangling with __ is stronger syntactically, but it is not a security
    mechanism.
    """

    def __init__(self, owner: str, opening_balance: float = 0.0) -> None:
        self.owner = owner
        self._balance = 0.0
        self.__audit_token = uuid.uuid4().hex
        self.deposit(opening_balance) if opening_balance else None

    @property
    def balance(self) -> float:
        """Read-only public access to internal balance."""
        return self._balance

    def deposit(self, amount: float) -> None:
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Deposit must be a positive finite number.")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Withdrawal must be a positive finite number.")
        if amount > self._balance:
            raise ValueError("Insufficient balance.")
        self._balance -= amount

    def audit_identity(self) -> str:
        return self.__audit_token


secure_account = BankAccount("alice", 1000)
secure_account.deposit(200)
secure_account.withdraw(150)

print("Encapsulated balance:", secure_account.balance)

try:
    secure_account.withdraw(5000)
except ValueError as error:
    print("Controlled error:", error)


# ============================================================================
# 4. PROPERTIES AND VALIDATED STATE
# ============================================================================

print("\n" + "=" * 80)
print("4. PROPERTIES")
print("=" * 80)


class Product:
    """
    A property allows an attribute-like interface while executing validation
    or other logic behind the scenes.
    """

    def __init__(self, name: str, price: float) -> None:
        self.name = name
        self.price = price

    @property
    def price(self) -> float:
        return self._price

    @price.setter
    def price(self, value: float) -> None:
        if not math.isfinite(value):
            raise ValueError("Price must be finite.")
        if value < 0:
            raise ValueError("Price cannot be negative.")
        self._price = round(value, 2)


product = Product("Keyboard", 2499.999)
print("Validated price:", product.price)

try:
    product.price = -10
except ValueError as error:
    print("Validation error:", error)


# ============================================================================
# 5. INHERITANCE
# ============================================================================

print("\n" + "=" * 80)
print("5. INHERITANCE")
print("=" * 80)


class Animal:
    def __init__(self, name: str) -> None:
        self.name = name

    def speak(self) -> str:
        return "Some sound"


class Dog(Animal):
    def speak(self) -> str:
        return f"{self.name} says woof"


class Cat(Animal):
    def speak(self) -> str:
        return f"{self.name} says meow"


dog = Dog("Buddy")
cat = Cat("Milo")

print(dog.speak())
print(cat.speak())
print("Dog is Animal:", isinstance(dog, Animal))


# ============================================================================
# 6. super() AND COOPERATIVE INHERITANCE
# ============================================================================

print("\n" + "=" * 80)
print("6. super()")
print("=" * 80)


class Employee:
    def __init__(self, name: str) -> None:
        self.name = name

    def describe(self) -> str:
        return f"Employee: {self.name}"


class Developer(Employee):
    def __init__(self, name: str, language: str) -> None:
        super().__init__(name)
        self.language = language

    def describe(self) -> str:
        return f"{super().describe()}, language: {self.language}"


developer = Developer("Priya", "Python")
print(developer.describe())


# ============================================================================
# 7. METHOD OVERRIDING
# ============================================================================

print("\n" + "=" * 80)
print("7. METHOD OVERRIDING")
print("=" * 80)


class Notification:
    def send(self, recipient: str, message: str) -> str:
        return f"Generic notification to {recipient}: {message}"


class EmailNotification(Notification):
    def send(self, recipient: str, message: str) -> str:
        return f"Email sent to {recipient}: {message}"


class SMSNotification(Notification):
    def send(self, recipient: str, message: str) -> str:
        return f"SMS sent to {recipient}: {message}"


for notification in (
    EmailNotification(),
    SMSNotification(),
):
    print(notification.send("user@example.com", "Account updated"))


# ============================================================================
# 8. POLYMORPHISM
# ============================================================================

print("\n" + "=" * 80)
print("8. POLYMORPHISM")
print("=" * 80)


def notify_user(
    notification: Notification,
    recipient: str,
    message: str,
) -> str:
    """
    The function depends on behavior, not on the concrete subclass.

    The same function works with different notification implementations.
    """
    return notification.send(recipient, message)


notifications: list[Notification] = [
    EmailNotification(),
    SMSNotification(),
]

for service in notifications:
    print(notify_user(service, "customer@example.com", "Order shipped"))


# ============================================================================
# 9. DUCK TYPING
# ============================================================================

print("\n" + "=" * 80)
print("9. DUCK TYPING")
print("=" * 80)


class PushNotification:
    def send(self, recipient: str, message: str) -> str:
        return f"Push notification to {recipient}: {message}"


def deliver(
    sender: Any,
    recipient: str,
    message: str,
) -> str:
    """
    Python often uses duck typing.

    If an object provides the required behavior, it can be used even if it
    does not inherit from a particular base class.
    """
    return sender.send(recipient, message)


print(deliver(PushNotification(), "user-42", "New login detected"))


# ============================================================================
# 10. ABSTRACTION WITH ABSTRACT BASE CLASSES
# ============================================================================

print("\n" + "=" * 80)
print("10. ABSTRACTION")
print("=" * 80)


class PaymentProcessor(ABC):
    """
    An abstract class defines a contract for concrete implementations.

    It prevents creation of a processor that has not supplied the required
    payment behavior.
    """

    @abstractmethod
    def pay(self, amount: float) -> str:
        """Process a payment and return a transaction identifier."""
        raise NotImplementedError


class CardPaymentProcessor(PaymentProcessor):
    def pay(self, amount: float) -> str:
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        transaction_id = f"CARD-{uuid.uuid4().hex[:10]}"
        return transaction_id


class WalletPaymentProcessor(PaymentProcessor):
    def pay(self, amount: float) -> str:
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        transaction_id = f"WALLET-{uuid.uuid4().hex[:10]}"
        return transaction_id


for processor in (
    CardPaymentProcessor(),
    WalletPaymentProcessor(),
):
    print("Transaction:", processor.pay(500))


# ============================================================================
# 11. COMPOSITION
# ============================================================================

print("\n" + "=" * 80)
print("11. COMPOSITION")
print("=" * 80)


class Engine:
    def start(self) -> str:
        return "Engine started"


class Car:
    """
    Car HAS-A Engine.

    Composition models a whole object using other objects as components.
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def start(self) -> str:
        return self.engine.start()


car = Car(Engine())
print(car.start())


# ============================================================================
# 12. COMPOSITION VERSUS INHERITANCE
# ============================================================================

print("\n" + "=" * 80)
print("12. COMPOSITION VERSUS INHERITANCE")
print("=" * 80)


class Logger:
    def log(self, message: str) -> str:
        return f"[LOG] {message}"


class OrderService:
    """
    OrderService does not inherit from Logger.

    It uses a Logger because logging is a capability it needs, not an
    identity relationship.
    """

    def __init__(self, logger: Logger) -> None:
        self.logger = logger

    def create_order(self, order_id: str) -> str:
        return self.logger.log(f"Created order {order_id}")


order_service = OrderService(Logger())
print(order_service.create_order("ORD-1001"))


# ============================================================================
# 13. AGGREGATION
# ============================================================================

print("\n" + "=" * 80)
print("13. AGGREGATION")
print("=" * 80)


@dataclass
class TeamMember:
    name: str
    role: str


class Team:
    """
    A Team aggregates TeamMember objects.

    The members can conceptually exist independently of this Team.
    """

    def __init__(
        self,
        name: str,
        members: Iterable[TeamMember],
    ) -> None:
        self.name = name
        self.members = list(members)

    def roster(self) -> list[str]:
        return [
            f"{member.name} ({member.role})"
            for member in self.members
        ]


alice = TeamMember("Alice", "Developer")
bob = TeamMember("Bob", "Tester")

team = Team("Platform", [alice, bob])
print(team.roster())


# ============================================================================
# 14. ASSOCIATION
# ============================================================================

print("\n" + "=" * 80)
print("14. ASSOCIATION")
print("=" * 80)


@dataclass
class Customer:
    customer_id: str
    name: str


@dataclass
class Invoice:
    invoice_id: str
    customer: Customer
    amount: float


customer = Customer("C-100", "Ravi")
invoice = Invoice("INV-100", customer, 7500)

print(
    f"Invoice {invoice.invoice_id} belongs to "
    f"{invoice.customer.name}"
)


# ============================================================================
# 15. DATACLASSES FOR DOMAIN MODELS
# ============================================================================

print("\n" + "=" * 80)
print("15. DATACLASSES")
print("=" * 80)


@dataclass
class Address:
    city: str
    country: str


@dataclass
class CustomerProfile:
    customer_id: str
    name: str
    email: str
    address: Address
    active: bool = True
    tags: list[str] = field(default_factory=list)


profile = CustomerProfile(
    customer_id="CUS-1",
    name="Neha",
    email="neha@example.com",
    address=Address("Lucknow", "India"),
    tags=["premium", "verified"],
)

print(asdict(profile))


# ============================================================================
# 16. ENUMS FOR CONTROLLED DOMAIN VALUES
# ============================================================================

print("\n" + "=" * 80)
print("16. ENUMS")
print("=" * 80)


class OrderStatus(Enum):
    CREATED = "created"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


status = OrderStatus.CREATED

print(status)
print(status.value)


# ============================================================================
# 17. DOMAIN MODEL WITH BUSINESS RULES
# ============================================================================

print("\n" + "=" * 80)
print("17. DOMAIN MODEL")
print("=" * 80)


@dataclass
class OrderItem:
    product_name: str
    unit_price: float
    quantity: int

    def __post_init__(self) -> None:
        if not self.product_name.strip():
            raise ValueError("Product name cannot be empty.")
        if self.unit_price < 0:
            raise ValueError("Unit price cannot be negative.")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive.")

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.quantity, 2)


class Order:
    """
    A domain object owns rules directly related to its state.

    This prevents business invariants from being scattered across unrelated
    controllers or database code.
    """

    VALID_TRANSITIONS: ClassVar[dict[OrderStatus, set[OrderStatus]]] = {
        OrderStatus.CREATED: {
            OrderStatus.PAID,
            OrderStatus.CANCELLED,
        },
        OrderStatus.PAID: {
            OrderStatus.SHIPPED,
            OrderStatus.CANCELLED,
        },
        OrderStatus.SHIPPED: set(),
        OrderStatus.CANCELLED: set(),
    }

    def __init__(
        self,
        order_id: str,
        customer_id: str,
        items: Sequence[OrderItem],
    ) -> None:
        if not items:
            raise ValueError("An order requires at least one item.")

        self.order_id = order_id
        self.customer_id = customer_id
        self.items = list(items)
        self.status = OrderStatus.CREATED
        self.created_at = datetime.now(timezone.utc)

    @property
    def total(self) -> float:
        return round(
            sum(item.subtotal for item in self.items),
            2,
        )

    def change_status(self, new_status: OrderStatus) -> None:
        allowed = self.VALID_TRANSITIONS[self.status]
        if new_status not in allowed:
            raise ValueError(
                f"Cannot change order from "
                f"{self.status.value} to {new_status.value}."
            )
        self.status = new_status


order = Order(
    "ORD-200",
    "CUS-1",
    [
        OrderItem("Laptop", 75000, 1),
        OrderItem("Mouse", 1500, 2),
    ],
)

print("Order total:", order.total)
order.change_status(OrderStatus.PAID)
print("Status:", order.status.value)


# ============================================================================
# 18. PROTOCOLS AS STRUCTURAL INTERFACES
# ============================================================================

print("\n" + "=" * 80)
print("18. PROTOCOLS")
print("=" * 80)


class OrderRepository(Protocol):
    """
    A Protocol defines the behavior required by a dependency.

    A concrete implementation does not have to inherit from this protocol.
    """

    def save(self, order: Order) -> None:
        ...

    def get(self, order_id: str) -> Optional[Order]:
        ...


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)


repository: OrderRepository = InMemoryOrderRepository()
repository.save(order)

print("Stored order:", repository.get("ORD-200"))


# ============================================================================
# 19. SERVICE LAYER AND DEPENDENCY INJECTION
# ============================================================================

print("\n" + "=" * 80)
print("19. SERVICE LAYER AND DEPENDENCY INJECTION")
print("=" * 80)


class NotificationSender(Protocol):
    def send(self, recipient: str, message: str) -> None:
        ...


class ConsoleNotificationSender:
    def send(self, recipient: str, message: str) -> None:
        print(f"Notification -> {recipient}: {message}")


class OrderService:
    """
    The service receives dependencies rather than constructing them internally.

    This is dependency injection.

    Benefits:
    - easier testing
    - lower coupling
    - easier replacement of infrastructure
    - clearer ownership of dependencies
    """

    def __init__(
        self,
        repository: OrderRepository,
        notifier: NotificationSender,
    ) -> None:
        self.repository = repository
        self.notifier = notifier

    def create(
        self,
        customer_id: str,
        recipient: str,
        items: Sequence[OrderItem],
    ) -> Order:
        order = Order(
            order_id=f"ORD-{uuid.uuid4().hex[:8]}",
            customer_id=customer_id,
            items=items,
        )

        self.repository.save(order)

        self.notifier.send(
            recipient,
            f"Order {order.order_id} created.",
        )

        return order


service = OrderService(
    repository=InMemoryOrderRepository(),
    notifier=ConsoleNotificationSender(),
)

created_order = service.create(
    customer_id="CUS-9",
    recipient="customer@example.com",
    items=[OrderItem("Monitor", 18000, 1)],
)

print("Created:", created_order.order_id)


# ============================================================================
# 20. FACTORY PATTERN
# ============================================================================

print("\n" + "=" * 80)
print("20. FACTORY")
print("=" * 80)


class Report(ABC):
    @abstractmethod
    def generate(self, data: dict[str, Any]) -> str:
        raise NotImplementedError


class JSONReport(Report):
    def generate(self, data: dict[str, Any]) -> str:
        return json.dumps(data, indent=2)


class TextReport(Report):
    def generate(self, data: dict[str, Any]) -> str:
        return "\n".join(
            f"{key}: {value}"
            for key, value in data.items()
        )


class ReportFactory:
    """
    A factory centralizes creation decisions.

    It prevents callers from repeatedly duplicating construction logic.
    """

    @staticmethod
    def create(format_name: str) -> Report:
        normalized = format_name.strip().lower()

        if normalized == "json":
            return JSONReport()

        if normalized == "text":
            return TextReport()

        raise ValueError(f"Unsupported report format: {format_name}")


for format_name in ("json", "text"):
    report = ReportFactory.create(format_name)
    print(report.generate({"status": "success", "count": 3}))


# ============================================================================
# 21. STRATEGY PATTERN
# ============================================================================

print("\n" + "=" * 80)
print("21. STRATEGY PATTERN")
print("=" * 80)


class DiscountStrategy(Protocol):
    def calculate(self, subtotal: float) -> float:
        ...


class NoDiscount:
    def calculate(self, subtotal: float) -> float:
        return 0.0


class PercentageDiscount:
    def __init__(self, percentage: float) -> None:
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100.")
        self.percentage = percentage

    def calculate(self, subtotal: float) -> float:
        return round(subtotal * self.percentage / 100, 2)


class Checkout:
    """
    Checkout delegates discount behavior to an injected strategy.

    New discount policies can be introduced without rewriting Checkout.
    """

    def __init__(self, strategy: DiscountStrategy) -> None:
        self.strategy = strategy

    def final_amount(self, subtotal: float) -> float:
        if subtotal < 0:
            raise ValueError("Subtotal cannot be negative.")

        discount = self.strategy.calculate(subtotal)

        if discount < 0 or discount > subtotal:
            raise ValueError("Invalid discount result.")

        return round(subtotal - discount, 2)


print(
    "No discount:",
    Checkout(NoDiscount()).final_amount(1000),
)

print(
    "20% discount:",
    Checkout(PercentageDiscount(20)).final_amount(1000),
)


# ============================================================================
# 22. TEMPLATE METHOD WITH ABSTRACT BASE CLASS
# ============================================================================

print("\n" + "=" * 80)
print("22. TEMPLATE METHOD")
print("=" * 80)


class DataImporter(ABC):
    """
    The algorithm structure is fixed in the base class while specific steps
    are implemented by subclasses.
    """

    def import_data(self, raw_data: str) -> list[str]:
        cleaned = self.clean(raw_data)
        parsed = self.parse(cleaned)
        return self.validate(parsed)

    def clean(self, raw_data: str) -> str:
        return raw_data.strip()

    @abstractmethod
    def parse(self, cleaned_data: str) -> list[str]:
        raise NotImplementedError

    def validate(self, values: list[str]) -> list[str]:
        return [value for value in values if value]


class CSVImporter(DataImporter):
    def parse(self, cleaned_data: str) -> list[str]:
        return [
            value.strip()
            for value in cleaned_data.split(",")
        ]


class LineImporter(DataImporter):
    def parse(self, cleaned_data: str) -> list[str]:
        return [
            line.strip()
            for line in cleaned_data.splitlines()
        ]


print(CSVImporter().import_data(" a, b, c "))
print(LineImporter().import_data("a\nb\nc"))


# ============================================================================
# 23. MULTIPLE INHERITANCE AND MRO
# ============================================================================

print("\n" + "=" * 80)
print("23. MULTIPLE INHERITANCE AND METHOD RESOLUTION ORDER")
print("=" * 80)


class TimestampMixin:
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class IdentifierMixin:
    def identifier(self) -> str:
        return uuid.uuid4().hex[:12]


class AuditRecord(
    TimestampMixin,
    IdentifierMixin,
):
    def describe(self) -> str:
        return f"{self.identifier()} at {self.timestamp()}"


audit_record = AuditRecord()

print(audit_record.describe())
print(
    "MRO:",
    [
        cls.__name__
        for cls in AuditRecord.__mro__
    ],
)


# ============================================================================
# 24. DIAMOND INHERITANCE AND COOPERATIVE super()
# ============================================================================

print("\n" + "=" * 80)
print("24. COOPERATIVE MULTIPLE INHERITANCE")
print("=" * 80)


class Root:
    def process(self) -> list[str]:
        return ["Root"]


class Left(Root):
    def process(self) -> list[str]:
        return ["Left"] + super().process()


class Right(Root):
    def process(self) -> list[str]:
        return ["Right"] + super().process()


class Combined(Left, Right):
    def process(self) -> list[str]:
        return ["Combined"] + super().process()


combined = Combined()

print("Processing chain:", combined.process())
print(
    "MRO:",
    [cls.__name__ for cls in Combined.__mro__],
)


# ============================================================================
# 25. SOLID: SINGLE RESPONSIBILITY PRINCIPLE
# ============================================================================

print("\n" + "=" * 80)
print("25. SOLID: SINGLE RESPONSIBILITY")
print("=" * 80)


class InvoiceCalculator:
    def calculate_total(self, items: Sequence[OrderItem]) -> float:
        return round(sum(item.subtotal for item in items), 2)


class InvoiceFormatter:
    def format(self, total: float) -> str:
        return f"Invoice total: ₹{total:,.2f}"


calculator = InvoiceCalculator()
formatter = InvoiceFormatter()

invoice_total = calculator.calculate_total(
    [
        OrderItem("Keyboard", 2000, 2),
        OrderItem("Mouse", 1000, 1),
    ]
)

print(formatter.format(invoice_total))


# ============================================================================
# 26. OPEN/CLOSED PRINCIPLE
# ============================================================================

print("\n" + "=" * 80)
print("26. OPEN/CLOSED PRINCIPLE")
print("=" * 80)


class TaxPolicy(Protocol):
    def calculate(self, amount: float) -> float:
        ...


class GSTTaxPolicy:
    def __init__(self, rate: float) -> None:
        if not 0 <= rate <= 100:
            raise ValueError("Tax rate must be between 0 and 100.")
        self.rate = rate

    def calculate(self, amount: float) -> float:
        return round(amount * self.rate / 100, 2)


class ZeroTaxPolicy:
    def calculate(self, amount: float) -> float:
        return 0.0


class TaxedInvoice:
    def __init__(self, policy: TaxPolicy) -> None:
        self.policy = policy

    def total_with_tax(self, amount: float) -> float:
        return round(
            amount + self.policy.calculate(amount),
            2,
        )


print(
    "GST total:",
    TaxedInvoice(GSTTaxPolicy(18)).total_with_tax(1000),
)

print(
    "Zero-tax total:",
    TaxedInvoice(ZeroTaxPolicy()).total_with_tax(1000),
)


# ============================================================================
# 27. LISKOV SUBSTITUTION PRINCIPLE
# ============================================================================

print("\n" + "=" * 80)
print("27. LISKOV SUBSTITUTION")
print("=" * 80)


class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        raise NotImplementedError


class Rectangle(Shape):
    def __init__(self, width: float, height: float) -> None:
        if width < 0 or height < 0:
            raise ValueError("Dimensions cannot be negative.")
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height


class Circle(Shape):
    def __init__(self, radius: float) -> None:
        if radius < 0:
            raise ValueError("Radius cannot be negative.")
        self.radius = radius

    def area(self) -> float:
        return math.pi * self.radius ** 2


def print_area(shape: Shape) -> None:
    print(f"Area: {shape.area():.2f}")


for shape in (
    Rectangle(10, 5),
    Circle(5),
):
    print_area(shape)


# ============================================================================
# 28. INTERFACE SEGREGATION
# ============================================================================

print("\n" + "=" * 80)
print("28. INTERFACE SEGREGATION")
print("=" * 80)


class Reader(Protocol):
    def read(self) -> str:
        ...


class Writer(Protocol):
    def write(self, value: str) -> None:
        ...


class InMemoryDocument:
    def __init__(self) -> None:
        self.content = ""

    def read(self) -> str:
        return self.content

    def write(self, value: str) -> None:
        self.content = value


def consume_document(reader: Reader) -> str:
    return reader.read()


def update_document(writer: Writer, value: str) -> None:
    writer.write(value)


document = InMemoryDocument()
update_document(document, "Backend design")
print(consume_document(document))


# ============================================================================
# 29. DEPENDENCY INVERSION
# ============================================================================

print("\n" + "=" * 80)
print("29. DEPENDENCY INVERSION")
print("=" * 80)


class PaymentGateway(Protocol):
    def charge(self, amount: float) -> str:
        ...


class MockPaymentGateway:
    def charge(self, amount: float) -> str:
        return f"MOCK-{uuid.uuid4().hex[:8]}"


class PaymentService:
    """
    High-level business logic depends on an abstraction.

    It does not depend directly on a concrete payment vendor.
    """

    def __init__(self, gateway: PaymentGateway) -> None:
        self.gateway = gateway

    def collect(self, amount: float) -> str:
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        return self.gateway.charge(amount)


payment_service = PaymentService(MockPaymentGateway())
print("Payment reference:", payment_service.collect(2500))


# ============================================================================
# 30. IMMUTABLE DOMAIN VALUE OBJECT
# ============================================================================

print("\n" + "=" * 80)
print("30. IMMUTABLE VALUE OBJECT")
print("=" * 80)


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "INR"

    def __post_init__(self) -> None:
        if not math.isfinite(self.amount):
            raise ValueError("Money amount must be finite.")
        if len(self.currency) != 3:
            raise ValueError("Currency must be a three-letter code.")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Currencies must match.")
        return Money(
            round(self.amount + other.amount, 2),
            self.currency,
        )


money_a = Money(100)
money_b = Money(250)
money_c = money_a.add(money_b)

print("Money:", money_c)

try:
    money_a.amount = 500
except Exception as error:
    print("Immutable object:", type(error).__name__)


# ============================================================================
# 31. CUSTOM EXCEPTIONS
# ============================================================================

print("\n" + "=" * 80)
print("31. DOMAIN EXCEPTIONS")
print("=" * 80)


class DomainError(Exception):
    """Base class for expected business-rule errors."""


class InsufficientStockError(DomainError):
    pass


class ProductNotFoundError(DomainError):
    pass


class Inventory:
    def __init__(self) -> None:
        self._stock: dict[str, int] = {}

    def add(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        self._stock[sku] = self._stock.get(sku, 0) + quantity

    def reserve(self, sku: str, quantity: int) -> None:
        if sku not in self._stock:
            raise ProductNotFoundError(sku)

        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        if quantity > self._stock[sku]:
            raise InsufficientStockError(
                f"Requested {quantity}, "
                f"available {self._stock[sku]}"
            )

        self._stock[sku] -= quantity


inventory = Inventory()
inventory.add("SKU-1", 10)

try:
    inventory.reserve("SKU-1", 20)
except InsufficientStockError as error:
    print("Business error:", error)


# ============================================================================
# 32. REPOSITORY PATTERN
# ============================================================================

print("\n" + "=" * 80)
print("32. REPOSITORY PATTERN")
print("=" * 80)


@dataclass
class UserEntity:
    user_id: str
    email: str
    active: bool = True


class UserRepository(Protocol):
    def add(self, user: UserEntity) -> None:
        ...

    def find(self, user_id: str) -> Optional[UserEntity]:
        ...

    def delete(self, user_id: str) -> None:
        ...


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, UserEntity] = {}

    def add(self, user: UserEntity) -> None:
        self._users[user.user_id] = user

    def find(self, user_id: str) -> Optional[UserEntity]:
        return self._users.get(user_id)

    def delete(self, user_id: str) -> None:
        self._users.pop(user_id, None)


user_repository: UserRepository = InMemoryUserRepository()

backend_user = UserEntity(
    user_id="U-1",
    email="backend@example.com",
)

user_repository.add(backend_user)

print("Repository lookup:", user_repository.find("U-1"))


# ============================================================================
# 33. APPLICATION SERVICE
# ============================================================================

print("\n" + "=" * 80)
print("33. APPLICATION SERVICE")
print("=" * 80)


class UserRegistrationService:
    """
    Application services coordinate domain operations and infrastructure.

    They should generally orchestrate rather than contain every business rule.
    """

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register(self, email: str) -> UserEntity:
        normalized = email.strip().lower()

        if "@" not in normalized:
            raise ValueError("Invalid email.")

        user = UserEntity(
            user_id=f"U-{uuid.uuid4().hex[:8]}",
            email=normalized,
        )

        self.repository.add(user)
        return user


registration_service = UserRegistrationService(
    InMemoryUserRepository()
)

registered = registration_service.register(
    "Example@EMAIL.COM"
)

print("Registered:", registered)


# ============================================================================
# 34. UNIT OF WORK CONCEPT
# ============================================================================

print("\n" + "=" * 80)
print("34. UNIT OF WORK")
print("=" * 80)


class UnitOfWork(Protocol):
    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def execute_transaction(
    operation: Callable[[], None],
    unit_of_work: UnitOfWork,
) -> None:
    """
    This demonstrates transaction orchestration.

    A production database transaction would delegate actual atomicity to
    the database or transaction manager.
    """
    try:
        operation()
        unit_of_work.commit()
    except Exception:
        unit_of_work.rollback()
        raise


uow = InMemoryUnitOfWork()

execute_transaction(
    lambda: print("Transactional operation executed"),
    uow,
)

print("Committed:", uow.committed)


# ============================================================================
# 35. SERIALIZATION
# ============================================================================

print("\n" + "=" * 80)
print("35. SERIALIZATION")
print("=" * 80)


@dataclass
class APIUser:
    user_id: str
    name: str
    email: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


api_user = APIUser(
    user_id="U-100",
    name="Aman",
    email="aman@example.com",
)

json_payload = api_user.to_json()

print("JSON:", json_payload)


# ============================================================================
# 36. VALIDATION AT BOUNDARIES
# ============================================================================

print("\n" + "=" * 80)
print("36. INPUT VALIDATION")
print("=" * 80)


class RegistrationInput:
    """
    Boundary validation protects domain code from malformed external input.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        self.email = self._validate_email(raw.get("email"))
        self.age = self._validate_age(raw.get("age"))

    @staticmethod
    def _validate_email(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Email must be a string.")

        email = value.strip().lower()

        if not email or "@" not in email:
            raise ValueError("Invalid email.")

        return email

    @staticmethod
    def _validate_age(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Age must be an integer.")

        if not 13 <= value <= 120:
            raise ValueError("Age must be between 13 and 120.")

        return value


valid_input = RegistrationInput(
    {
        "email": "PERSON@EXAMPLE.COM",
        "age": 30,
    }
)

print(valid_input.email, valid_input.age)


# ============================================================================
# 37. SECURITY: PASSWORD HASHING
# ============================================================================

print("\n" + "=" * 80)
print("37. SECURITY: PASSWORD HASHING")
print("=" * 80)


class PasswordHasher:
    """
    Demonstrates a standard-library password hashing concept.

    PBKDF2 deliberately performs repeated hashing to make password guessing
    more expensive.

    Production systems should use a password-hashing library designed for
    password storage and select parameters appropriate for the environment.
    """

    ITERATIONS = 300_000
    SALT_SIZE = 16

    @classmethod
    def hash_password(
        cls,
        password: str,
    ) -> tuple[str, str]:
        if not password:
            raise ValueError("Password cannot be empty.")

        salt = hashlib.sha256(
            uuid.uuid4().bytes
        ).digest()[: cls.SALT_SIZE]

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
        )

        return (
            salt.hex(),
            digest.hex(),
        )

    @classmethod
    def verify_password(
        cls,
        password: str,
        salt_hex: str,
        digest_hex: str,
    ) -> bool:
        salt = bytes.fromhex(salt_hex)

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
        )

        return hmac.compare_digest(
            candidate.hex(),
            digest_hex,
        )


salt, password_hash = PasswordHasher.hash_password("correct-password")

print(
    "Correct password:",
    PasswordHasher.verify_password(
        "correct-password",
        salt,
        password_hash,
    ),
)

print(
    "Incorrect password:",
    PasswordHasher.verify_password(
        "wrong-password",
        salt,
        password_hash,
    ),
)


# ============================================================================
# 38. SECURITY: AUTHORIZATION
# ============================================================================

print("\n" + "=" * 80)
print("38. AUTHORIZATION")
print("=" * 80)


class Role(Enum):
    USER = "user"
    ADMIN = "admin"


@dataclass
class AuthenticatedUser:
    user_id: str
    role: Role


def require_admin(user: AuthenticatedUser) -> None:
    if user.role is not Role.ADMIN:
        raise PermissionError("Administrator privileges required.")


admin = AuthenticatedUser("U-ADMIN", Role.ADMIN)
normal_user = AuthenticatedUser("U-USER", Role.USER)

require_admin(admin)
print("Admin authorization succeeded.")

try:
    require_admin(normal_user)
except PermissionError as error:
    print("Authorization denied:", error)


# ============================================================================
# 39. DECORATOR FOR CROSS-CUTTING BEHAVIOR
# ============================================================================

print("\n" + "=" * 80)
print("39. DECORATORS")
print("=" * 80)


Function = TypeVar("Function", bound=Callable[..., Any])


def measure_time(function: Function) -> Function:
    """
    Decorators can add behavior around existing functions.

    The implementation uses functools.wraps to preserve useful metadata.
    """

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = function(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(
            f"{function.__name__} executed in "
            f"{elapsed:.6f} seconds"
        )
        return result

    return wrapper  # type: ignore[return-value]


@measure_time
def calculate_sum(limit: int) -> int:
    return sum(range(limit))


print("Calculated:", calculate_sum(100_000))


# ============================================================================
# 40. ITERATORS AND LAZY PROCESSING
# ============================================================================

print("\n" + "=" * 80)
print("40. ITERATORS")
print("=" * 80)


class OrderStream:
    """
    A generator-style iterator can process records lazily.

    This matters when a backend handles a large number of records.
    """

    def __init__(self, orders: Iterable[Order]) -> None:
        self.orders = orders

    def paid_orders(self) -> Iterator[Order]:
        for current_order in self.orders:
            if current_order.status is OrderStatus.PAID:
                yield current_order


stream_orders = [
    order,
    created_order,
]

paid_order_stream = OrderStream(stream_orders).paid_orders()

for paid_order in paid_order_stream:
    print("Paid order:", paid_order.order_id)


# ============================================================================
# 41. CACHING WITH COMPOSITION
# ============================================================================

print("\n" + "=" * 80)
print("41. CACHING")
print("=" * 80)


class ProductRepository(Protocol):
    def get_price(self, product_id: str) -> float:
        ...


class SlowProductRepository:
    def __init__(self) -> None:
        self.calls = 0

    def get_price(self, product_id: str) -> float:
        self.calls += 1
        return {
            "P1": 1000.0,
            "P2": 2500.0,
        }[product_id]


class CachedProductRepository:
    """
    Decorator-like composition adds caching without modifying the original
    repository.
    """

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository
        self.cache: dict[str, float] = {}

    def get_price(self, product_id: str) -> float:
        if product_id not in self.cache:
            self.cache[product_id] = self.repository.get_price(product_id)

        return self.cache[product_id]


slow_repository = SlowProductRepository()
cached_repository = CachedProductRepository(slow_repository)

print(cached_repository.get_price("P1"))
print(cached_repository.get_price("P1"))
print("Underlying calls:", slow_repository.calls)


# ============================================================================
# 42. EVENT-DRIVEN DESIGN
# ============================================================================

print("\n" + "=" * 80)
print("42. DOMAIN EVENTS")
print("=" * 80)


@dataclass(frozen=True)
class OrderCreatedEvent:
    order_id: str
    customer_id: str
    occurred_at: datetime


class EventHandler(Protocol):
    def handle(self, event: OrderCreatedEvent) -> None:
        ...


class AuditEventHandler:
    def handle(self, event: OrderCreatedEvent) -> None:
        print(
            "Audit event:",
            event.order_id,
            event.occurred_at.isoformat(),
        )


class EventBus:
    def __init__(
        self,
        handlers: Sequence[EventHandler],
    ) -> None:
        self.handlers = list(handlers)

    def publish(self, event: OrderCreatedEvent) -> None:
        for handler in self.handlers:
            handler.handle(event)


event_bus = EventBus([AuditEventHandler()])

event_bus.publish(
    OrderCreatedEvent(
        order_id=created_order.order_id,
        customer_id=created_order.customer_id,
        occurred_at=datetime.now(timezone.utc),
    )
)


# ============================================================================
# 43. LOGGING
# ============================================================================

print("\n" + "=" * 80)
print("43. LOGGING")
print("=" * 80)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("backend_demo")


class AuditedService:
    def execute(self, operation: str) -> str:
        logger.info("Executing operation=%s", operation)
        result = f"completed:{operation}"
        logger.info("Operation completed")
        return result


print(AuditedService().execute("create-order"))


# ============================================================================
# 44. ERROR HANDLING STRATEGY
# ============================================================================

print("\n" + "=" * 80)
print("44. ERROR HANDLING")
print("=" * 80)


def divide_numbers(left: float, right: float) -> float:
    if not math.isfinite(left) or not math.isfinite(right):
        raise ValueError("Inputs must be finite.")

    if right == 0:
        raise ZeroDivisionError("Cannot divide by zero.")

    return left / right


try:
    print("10 / 2 =", divide_numbers(10, 2))
except (ValueError, ZeroDivisionError) as error:
    logger.error("Calculation failed: %s", error)


try:
    divide_numbers(10, 0)
except ZeroDivisionError as error:
    print("Expected error:", error)


# ============================================================================
# 45. CONTEXT MANAGER FOR RESOURCE OWNERSHIP
# ============================================================================

print("\n" + "=" * 80)
print("45. CONTEXT MANAGERS")
print("=" * 80)


class ManagedResource:
    def __enter__(self) -> "ManagedResource":
        print("Resource acquired")
        return self

    def execute(self) -> str:
        return "Resource operation"

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> bool:
        print("Resource released")
        return False


with ManagedResource() as resource:
    print(resource.execute())


# ============================================================================
# 46. ENTITY IDENTITY VERSUS VALUE EQUALITY
# ============================================================================

print("\n" + "=" * 80)
print("46. IDENTITY AND EQUALITY")
print("=" * 80)


class Entity:
    def __init__(self, entity_id: str, name: str) -> None:
        self.entity_id = entity_id
        self.name = name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented

        return self.entity_id == other.entity_id

    def __hash__(self) -> int:
        return hash(self.entity_id)


entity_a = Entity("1", "First")
entity_b = Entity("1", "Renamed")

print("Same identity:", entity_a == entity_b)
print("Same object:", entity_a is entity_b)


# ============================================================================
# 47. CLASS VARIABLES VERSUS INSTANCE VARIABLES
# ============================================================================

print("\n" + "=" * 80)
print("47. CLASS VERSUS INSTANCE STATE")
print("=" * 80)


class Connection:
    active_connections: ClassVar[int] = 0

    def __init__(self, name: str) -> None:
        self.name = name
        Connection.active_connections += 1

    def close(self) -> None:
        if self.name is not None:
            Connection.active_connections -= 1
            self.name = None


connection_a = Connection("A")
connection_b = Connection("B")

print(
    "Active connections:",
    Connection.active_connections,
)

connection_a.close()

print(
    "After closing one:",
    Connection.active_connections,
)


# ============================================================================
# 48. __repr__, __str__, AND DEBUGGING
# ============================================================================

print("\n" + "=" * 80)
print("48. OBJECT REPRESENTATION")
print("=" * 80)


class DebugUser:
    def __init__(self, user_id: str, email: str) -> None:
        self.user_id = user_id
        self.email = email

    def __repr__(self) -> str:
        return (
            f"DebugUser("
            f"user_id={self.user_id!r}, "
            f"email={self.email!r})"
        )

    def __str__(self) -> str:
        return f"{self.user_id}: {self.email}"


debug_user = DebugUser("U-1", "debug@example.com")

print("repr:", repr(debug_user))
print("str:", str(debug_user))


# ============================================================================
# 49. BACKEND CONTROLLER-SERVICE-REPOSITORY SEPARATION
# ============================================================================

print("\n" + "=" * 80)
print("49. BACKEND LAYERED DESIGN")
print("=" * 80)


@dataclass
class CreateOrderRequest:
    customer_id: str
    recipient: str
    items: list[OrderItem]


class OrderController:
    """
    A controller should deal with transport concerns such as HTTP requests
    and responses.

    Here it is simulated with plain Python dictionaries.
    """

    def __init__(self, service: OrderService) -> None:
        self.service = service

    def create_order(
        self,
        request: CreateOrderRequest,
    ) -> dict[str, Any]:
        created = self.service.create(
            customer_id=request.customer_id,
            recipient=request.recipient,
            items=request.items,
        )

        return {
            "order_id": created.order_id,
            "status": created.status.value,
            "total": created.total,
        }


controller_repository = InMemoryOrderRepository()

controller_service = OrderService(
    repository=controller_repository,
    notifier=ConsoleNotificationSender(),
)

controller = OrderController(controller_service)

response = controller.create_order(
    CreateOrderRequest(
        customer_id="CUS-CONTROLLER",
        recipient="api@example.com",
        items=[
            OrderItem("Server", 50000, 1),
        ],
    )
)

print("Controller response:", response)


# ============================================================================
# 50. TRANSACTIONAL SERVICE WITH FAILURE HANDLING
# ============================================================================

print("\n" + "=" * 80)
print("50. TRANSACTIONAL APPLICATION SERVICE")
print("=" * 80)


class TransactionalOrderService:
    def __init__(
        self,
        repository: OrderRepository,
        notifier: NotificationSender,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.repository = repository
        self.notifier = notifier
        self.unit_of_work = unit_of_work

    def create(
        self,
        customer_id: str,
        recipient: str,
        items: Sequence[OrderItem],
        fail_after_save: bool = False,
    ) -> Order:
        try:
            new_order = Order(
                order_id=f"ORD-{uuid.uuid4().hex[:8]}",
                customer_id=customer_id,
                items=items,
            )

            self.repository.save(new_order)

            if fail_after_save:
                raise RuntimeError("Simulated downstream failure.")

            self.notifier.send(
                recipient,
                f"Order {new_order.order_id} created.",
            )

            self.unit_of_work.commit()
            return new_order

        except Exception:
            self.unit_of_work.rollback()
            raise


transactional_uow = InMemoryUnitOfWork()

transactional_service = TransactionalOrderService(
    repository=InMemoryOrderRepository(),
    notifier=ConsoleNotificationSender(),
    unit_of_work=transactional_uow,
)

try:
    transactional_service.create(
        customer_id="CUS-TX",
        recipient="transaction@example.com",
        items=[OrderItem("SSD", 7000, 1)],
        fail_after_save=True,
    )
except RuntimeError as error:
    print("Transaction failed:", error)

print("Rollback executed:", transactional_uow.rolled_back)


# ============================================================================
# 51. TEST DOUBLE FOR UNIT TESTING
# ============================================================================

print("\n" + "=" * 80)
print("51. TEST DOUBLES")
print("=" * 80)


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, recipient: str, message: str) -> None:
        self.messages.append((recipient, message))


fake_notifier = FakeNotifier()
test_repository = InMemoryOrderRepository()

test_service = OrderService(
    repository=test_repository,
    notifier=fake_notifier,
)

test_order = test_service.create(
    customer_id="TEST-CUSTOMER",
    recipient="test@example.com",
    items=[OrderItem("Test Item", 100, 1)],
)

assert test_repository.get(test_order.order_id) is test_order
assert len(fake_notifier.messages) == 1
assert fake_notifier.messages[0][0] == "test@example.com"

print("Service test passed.")


# ============================================================================
# 52. ASSERTIONS FOR DOMAIN INVARIANTS
# ============================================================================

print("\n" + "=" * 80)
print("52. ASSERTIONS")
print("=" * 80)


assert OrderItem("Item", 100, 2).subtotal == 200
assert Money(100).add(Money(50)).amount == 150
assert Checkout(NoDiscount()).final_amount(1000) == 1000
assert TaxedInvoice(GSTTaxPolicy(18)).total_with_tax(1000) == 1180

print("Domain assertions passed.")


# ============================================================================
# 53. PERFORMANCE: O(1) LOOKUP VERSUS O(N) SEARCH
# ============================================================================

print("\n" + "=" * 80)
print("53. PERFORMANCE CONSIDERATIONS")
print("=" * 80)


def find_with_list(
    records: list[dict[str, Any]],
    target_id: str,
) -> Optional[dict[str, Any]]:
    for record in records:
        if record["id"] == target_id:
            return record
    return None


def build_index(
    records: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        record["id"]: record
        for record in records
    }


records = [
    {"id": str(number), "value": number * 10}
    for number in range(1000)
]

index = build_index(records)

print("List search:", find_with_list(records, "999"))
print("Dictionary lookup:", index.get("999"))

print(
    "Conceptual complexity:",
    "list search O(n), dictionary lookup average O(1)",
)


# ============================================================================
# 54. PERFORMANCE: OBJECT CREATION AND RESPONSIBILITY
# ============================================================================

print("\n" + "=" * 80)
print("54. PERFORMANCE AND DESIGN TRADE-OFFS")
print("=" * 80)


@dataclass
class LightweightRecord:
    value: int


def create_records(count: int) -> list[LightweightRecord]:
    return [
        LightweightRecord(number)
        for number in range(count)
    ]


start = time.perf_counter()
records_created = create_records(10_000)
elapsed = time.perf_counter() - start

print("Objects created:", len(records_created))
print(f"Creation time: {elapsed:.6f} seconds")


# ============================================================================
# 55. CIRCULAR DEPENDENCY PROBLEM
# ============================================================================

print("\n" + "=" * 80)
print("55. AVOIDING CIRCULAR DEPENDENCIES")
print("=" * 80)


class AuditLogger:
    def record(self, message: str) -> None:
        print("AUDIT:", message)


class UserApplicationService:
    """
    The service receives a logger rather than constructing a class that
    might itself depend on the service.

    Explicit dependency direction helps prevent circular dependencies.
    """

    def __init__(self, logger: AuditLogger) -> None:
        self.logger = logger

    def deactivate(self, user: UserEntity) -> None:
        user.active = False
        self.logger.record(
            f"User {user.user_id} deactivated"
        )


user_to_deactivate = UserEntity(
    "U-DEACTIVATE",
    "user@example.com",
)

UserApplicationService(AuditLogger()).deactivate(
    user_to_deactivate
)

print("Active:", user_to_deactivate.active)


# ============================================================================
# 56. OVER-INHERITANCE WARNING
# ============================================================================

print("\n" + "=" * 80)
print("56. OVER-INHERITANCE")
print("=" * 80)


class BasicReport:
    def render(self, value: str) -> str:
        return value


class TimestampedReport(BasicReport):
    def render(self, value: str) -> str:
        return (
            f"{datetime.now(timezone.utc).isoformat()} "
            f"{super().render(value)}"
        )


class UppercaseTimestampedReport(TimestampedReport):
    def render(self, value: str) -> str:
        return super().render(value).upper()


print(
    UppercaseTimestampedReport().render(
        "Inheritance chain"
    )
)

print(
    "Deep inheritance can increase coupling; composition can often express "
    "optional behavior more clearly."
)


# ============================================================================
# 57. COMPOSITION FOR OPTIONAL FEATURES
# ============================================================================

print("\n" + "=" * 80)
print("57. COMPOSITION FOR OPTIONAL FEATURES")
print("=" * 80)


class Formatter(Protocol):
    def format(self, value: str) -> str:
        ...


class PlainFormatter:
    def format(self, value: str) -> str:
        return value


class UppercaseFormatter:
    def format(self, value: str) -> str:
        return value.upper()


class ReportService:
    def __init__(self, formatter: Formatter) -> None:
        self.formatter = formatter

    def render(self, value: str) -> str:
        return self.formatter.format(value)


print(
    ReportService(PlainFormatter()).render(
        "normal output"
    )
)

print(
    ReportService(UppercaseFormatter()).render(
        "transformed output"
    )
)


# ============================================================================
# 58. POLYMORPHIC COLLECTION PROCESSING
# ============================================================================

print("\n" + "=" * 80)
print("58. POLYMORPHIC COLLECTIONS")
print("=" * 80)


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, value: str) -> None:
        raise NotImplementedError


class MemoryStorage(Storage):
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def save(self, key: str, value: str) -> None:
        self.data[key] = value


class SecondaryMemoryStorage(Storage):
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def save(self, key: str, value: str) -> None:
        self.data[key] = value


def persist_all(
    storages: Iterable[Storage],
    key: str,
    value: str,
) -> None:
    for storage in storages:
        storage.save(key, value)


primary_storage = MemoryStorage()
secondary_storage = SecondaryMemoryStorage()

persist_all(
    [primary_storage, secondary_storage],
    "status",
    "active",
)

print(primary_storage.data)
print(secondary_storage.data)


# ============================================================================
# 59. OBJECT LIFECYCLE
# ============================================================================

print("\n" + "=" * 80)
print("59. OBJECT LIFECYCLE")
print("=" * 80)


class LifecycleObject:
    def __new__(cls, *args: Any, **kwargs: Any) -> "LifecycleObject":
        print("__new__: allocating object")
        return super().__new__(cls)

    def __init__(self, value: str) -> None:
        print("__init__: initializing object")
        self.value = value

    def __del__(self) -> None:
        """
        __del__ should not be used as the primary mechanism for deterministic
        resource management. Context managers are generally safer.
        """
        pass


lifecycle_object = LifecycleObject("example")
print("Value:", lifecycle_object.value)


# ============================================================================
# 60. __slots__ FOR SPECIALIZED MEMORY-SENSITIVE OBJECTS
# ============================================================================

print("\n" + "=" * 80)
print("60. __slots__")
print("=" * 80)


class CompactRecord:
    """
    __slots__ can reduce per-instance memory overhead by avoiding a normal
    instance __dict__.

    It should be used intentionally because it changes some normal Python
    object behavior.
    """

    __slots__ = ("identifier", "value")

    def __init__(self, identifier: str, value: int) -> None:
        self.identifier = identifier
        self.value = value


compact = CompactRecord("R-1", 100)

print(compact.identifier, compact.value)

try:
    compact.extra = "not allowed"
except AttributeError as error:
    print("Slots restriction:", error)


# ============================================================================
# 61. GENERIC REPOSITORY CONCEPT
# ============================================================================

print("\n" + "=" * 80)
print("61. GENERIC DESIGN")
print("=" * 80)


EntityType = TypeVar("EntityType")


class GenericMemoryRepository:
    def __init__(self) -> None:
        self._data: dict[str, EntityType] = {}

    def save(self, entity_id: str, entity: EntityType) -> None:
        self._data[entity_id] = entity

    def get(self, entity_id: str) -> Optional[EntityType]:
        return self._data.get(entity_id)

    def all(self) -> list[EntityType]:
        return list(self._data.values())


generic_repository: GenericMemoryRepository[UserEntity] = (
    GenericMemoryRepository()
)

generic_repository.save(
    "U-GENERIC",
    UserEntity(
        "U-GENERIC",
        "generic@example.com",
    ),
)

print(generic_repository.all())


# ============================================================================
# 62. COMMAND OBJECT
# ============================================================================

print("\n" + "=" * 80)
print("62. COMMAND OBJECT")
print("=" * 80)


@dataclass(frozen=True)
class CreateUserCommand:
    email: str
    name: str


class CommandHandler:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def handle(self, command: CreateUserCommand) -> UserEntity:
        user = UserEntity(
            user_id=f"U-{uuid.uuid4().hex[:8]}",
            email=command.email.strip().lower(),
        )

        self.repository.add(user)

        return user


command_handler = CommandHandler(
    InMemoryUserRepository()
)

command_result = command_handler.handle(
    CreateUserCommand(
        email="command@example.com",
        name="Command User",
    )
)

print(command_result)


# ============================================================================
# 63. READ MODEL AND QUERY SERVICE
# ============================================================================

print("\n" + "=" * 80)
print("63. QUERY SERVICE")
print("=" * 80)


class UserQueryService:
    """
    Query-oriented code can expose read-specific views rather than returning
    mutable domain objects directly.
    """

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def get_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        user = self.repository.find(user_id)

        if user is None:
            return None

        return {
            "id": user.user_id,
            "email": user.email,
            "active": user.active,
        }


query_repository = InMemoryUserRepository()
query_repository.add(
    UserEntity(
        "U-QUERY",
        "query@example.com",
    )
)

query_service = UserQueryService(query_repository)

print(query_service.get_profile("U-QUERY"))


# ============================================================================
# 64. IDEMPOTENCY
# ============================================================================

print("\n" + "=" * 80)
print("64. IDEMPOTENCY")
print("=" * 80)


class IdempotentOperationService:
    """
    An idempotency key allows a retried request to return the original result
    instead of executing the same logical operation repeatedly.

    Real distributed systems normally persist idempotency keys durably.
    """

    def __init__(self) -> None:
        self._results: dict[str, str] = {}

    def execute(self, idempotency_key: str) -> str:
        if idempotency_key in self._results:
            return self._results[idempotency_key]

        result = f"operation-{uuid.uuid4().hex[:8]}"
        self._results[idempotency_key] = result

        return result


idempotent_service = IdempotentOperationService()

first_result = idempotent_service.execute("REQUEST-1")
second_result = idempotent_service.execute("REQUEST-1")

print("Same result:", first_result == second_result)


# ============================================================================
# 65. CONCURRENCY DESIGN CONSIDERATIONS
# ============================================================================

print("\n" + "=" * 80)
print("65. CONCURRENCY AND SHARED STATE")
print("=" * 80)


class Counter:
    """
    A simple object with explicit state.

    In a real multithreaded backend, shared mutable state requires appropriate
    synchronization or an architecture that avoids unsafe sharing.
    """

    def __init__(self) -> None:
        self.value = 0

    def increment(self) -> None:
        self.value += 1


counter = Counter()

for _ in range(1000):
    counter.increment()

print("Counter:", counter.value)


# ============================================================================
# 66. SERIALIZATION SAFETY
# ============================================================================

print("\n" + "=" * 80)
print("66. SERIALIZATION SAFETY")
print("=" * 80)


safe_payload = {
    "user_id": "U-1",
    "roles": ["user"],
}

encoded = json.dumps(safe_payload)
decoded = json.loads(encoded)

print("Encoded:", encoded)
print("Decoded:", decoded)

print(
    "JSON data is generally preferable to unsafe deserialization mechanisms "
    "when handling untrusted external input."
)


# ============================================================================
# 67. BOUNDARY ADAPTER
# ============================================================================

print("\n" + "=" * 80)
print("67. ADAPTER PATTERN")
print("=" * 80)


class LegacyPaymentAPI:
    def make_payment(self, rupees: int) -> str:
        return f"LEGACY-{rupees}-{uuid.uuid4().hex[:6]}"


class ModernPaymentGateway(PaymentGateway):
    """
    The adapter translates the application's expected interface into the
    legacy dependency's interface.
    """

    def __init__(self, legacy_api: LegacyPaymentAPI) -> None:
        self.legacy_api = legacy_api

    def charge(self, amount: float) -> str:
        if amount != int(amount):
            raise ValueError(
                "Legacy API accepts whole rupee amounts only."
            )

        return self.legacy_api.make_payment(int(amount))


adapted_gateway = ModernPaymentGateway(LegacyPaymentAPI())

print(
    PaymentService(adapted_gateway).collect(1500)
)


# ============================================================================
# 68. FACADE PATTERN
# ============================================================================

print("\n" + "=" * 80)
print("68. FACADE PATTERN")
print("=" * 80)


class InventorySystem:
    def reserve(self, item: str) -> None:
        print(f"Inventory reserved: {item}")


class PaymentSystem:
    def charge(self, amount: float) -> None:
        print(f"Payment charged: {amount}")


class ShippingSystem:
    def schedule(self, item: str) -> None:
        print(f"Shipping scheduled: {item}")


class CheckoutFacade:
    """
    A facade provides one simpler operation over several subsystems.
    """

    def __init__(
        self,
        inventory: InventorySystem,
        payment: PaymentSystem,
        shipping: ShippingSystem,
    ) -> None:
        self.inventory = inventory
        self.payment = payment
        self.shipping = shipping

    def checkout(self, item: str, amount: float) -> None:
        self.inventory.reserve(item)
        self.payment.charge(amount)
        self.shipping.schedule(item)


CheckoutFacade(
    InventorySystem(),
    PaymentSystem(),
    ShippingSystem(),
).checkout("Laptop", 75000)


# ============================================================================
# 69. OBJECT CALLOUT: __call__
# ============================================================================

print("\n" + "=" * 80)
print("69. CALLABLE OBJECTS")
print("=" * 80)


class TaxCalculator:
    def __init__(self, rate: float) -> None:
        if not 0 <= rate <= 1:
            raise ValueError("Rate must be between 0 and 1.")
        self.rate = rate

    def __call__(self, amount: float) -> float:
        return round(amount * self.rate, 2)


calculate_tax = TaxCalculator(0.18)

print("Tax:", calculate_tax(1000))


# ============================================================================
# 70. CONTEXT-SPECIFIC POLYMORPHISM
# ============================================================================

print("\n" + "=" * 80)
print("70. POLYMORPHIC PRICING")
print("=" * 80)


class PricingRule(Protocol):
    def price(self, base_price: float) -> float:
        ...


class StandardPricing:
    def price(self, base_price: float) -> float:
        return base_price


class PremiumPricing:
    def price(self, base_price: float) -> float:
        return round(base_price * 0.9, 2)


class EnterprisePricing:
    def price(self, base_price: float) -> float:
        return round(base_price * 0.8, 2)


def quote(
    rule: PricingRule,
    base_price: float,
) -> float:
    return rule.price(base_price)


for pricing_rule in (
    StandardPricing(),
    PremiumPricing(),
    EnterprisePricing(),
):
    print("Quote:", quote(pricing_rule, 10000))


# ============================================================================
# 71. EDGE CASES IN DOMAIN DESIGN
# ============================================================================

print("\n" + "=" * 80)
print("71. EDGE CASES")
print("=" * 80)


edge_cases = [
    ("zero quantity", lambda: OrderItem("X", 10, 0)),
    ("negative price", lambda: OrderItem("X", -1, 1)),
    ("empty name", lambda: OrderItem("", 10, 1)),
    ("negative discount", lambda: PercentageDiscount(-5)),
    ("invalid currency", lambda: Money(100, "IN")),
]

for description, operation in edge_cases:
    try:
        operation()
    except ValueError as error:
        print(f"{description}: rejected -> {error}")


# ============================================================================
# 72. COMMON DESIGN MISTAKE: GOD OBJECT
# ============================================================================

print("\n" + "=" * 80)
print("72. GOD OBJECT WARNING")
print("=" * 80)

print(
    "A class that validates requests, performs database operations, "
    "sends email, calculates pricing, formats HTTP responses, logs "
    "everything, and controls authentication has excessive responsibility."
)

print(
    "Prefer cohesive classes with explicit dependencies and well-defined "
    "boundaries."
)


# ============================================================================
# 73. COMMON DESIGN MISTAKE: ANEMIC DOMAIN MODEL
# ============================================================================

print("\n" + "=" * 80)
print("73. ANEMIC DOMAIN MODEL WARNING")
print("=" * 80)


@dataclass
class AnemicOrder:
    total: float
    status: str


print(
    "A data-only object can be appropriate for transport data, but domain "
    "objects with important invariants often benefit from owning their rules."
)

print(
    "The earlier Order class demonstrates behavior-rich domain modeling."
)


# ============================================================================
# 74. COMMON DESIGN MISTAKE: LEAKING INFRASTRUCTURE
# ============================================================================

print("\n" + "=" * 80)
print("74. INFRASTRUCTURE BOUNDARIES")
print("=" * 80)


class DomainOrderSummary:
    """
    A domain-facing structure should not need to know SQL cursor internals,
    HTTP request objects, framework-specific response objects, or vendor SDK
    details.
    """

    def __init__(
        self,
        order_id: str,
        total: float,
    ) -> None:
        self.order_id = order_id
        self.total = total


summary = DomainOrderSummary(
    order_id=order.order_id,
    total=order.total,
)

print(summary.order_id, summary.total)


# ============================================================================
# 75. DEPENDENCY GRAPH
# ============================================================================

print("\n" + "=" * 80)
print("75. DEPENDENCY DIRECTION")
print("=" * 80)

print(
    "A maintainable backend commonly keeps dependency direction explicit:"
)
print(
    "Controller -> Application Service -> Domain abstractions -> "
    "Infrastructure implementations"
)

print(
    "Dependency inversion allows the service layer to depend on interfaces "
    "rather than concrete database or vendor classes."
)


# ============================================================================
# 76. SMALL COHESIVE SERVICE
# ============================================================================

print("\n" + "=" * 80)
print("76. COHESION")
print("=" * 80)


class EmailAddress:
    """
    A small value object keeps email-specific rules together.
    """

    def __init__(self, value: str) -> None:
        normalized = value.strip().lower()

        if not normalized or "@" not in normalized:
            raise ValueError("Invalid email address.")

        self._value = normalized

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value


email_address = EmailAddress("USER@EXAMPLE.COM")

print("Normalized email:", email_address)


# ============================================================================
# 77. EXPLICIT DEPENDENCY GRAPH WITH CONSTRUCTION ROOT
# ============================================================================

print("\n" + "=" * 80)
print("77. COMPOSITION ROOT")
print("=" * 80)


def build_application() -> OrderController:
    """
    A composition root creates concrete infrastructure and wires dependencies.

    Application code can then operate against abstractions.
    """

    repository = InMemoryOrderRepository()
    notifier = ConsoleNotificationSender()

    service = OrderService(
        repository=repository,
        notifier=notifier,
    )

    return OrderController(service)


application_controller = build_application()

application_response = application_controller.create_order(
    CreateOrderRequest(
        customer_id="CUS-ROOT",
        recipient="root@example.com",
        items=[
            OrderItem("Router", 4000, 1),
        ],
    )
)

print(application_response)


# ============================================================================
# 78. SIMPLE BACKEND REQUEST PIPELINE
# ============================================================================

print("\n" + "=" * 80)
print("78. BACKEND REQUEST PIPELINE")
print("=" * 80)


@dataclass
class Request:
    method: str
    path: str
    body: dict[str, Any]


@dataclass
class Response:
    status_code: int
    body: dict[str, Any]


class RequestValidator:
    def validate(self, request: Request) -> None:
        if request.method != "POST":
            raise ValueError("Only POST is supported.")

        if request.path != "/orders":
            raise ValueError("Unsupported path.")

        if "customer_id" not in request.body:
            raise ValueError("customer_id is required.")


class BackendApplication:
    def __init__(
        self,
        validator: RequestValidator,
        controller: OrderController,
    ) -> None:
        self.validator = validator
        self.controller = controller

    def handle(self, request: Request) -> Response:
        try:
            self.validator.validate(request)

            items = [
                OrderItem(
                    product_name=item["product_name"],
                    unit_price=float(item["unit_price"]),
                    quantity=int(item["quantity"]),
                )
                for item in request.body["items"]
            ]

            result = self.controller.create_order(
                CreateOrderRequest(
                    customer_id=request.body["customer_id"],
                    recipient=request.body["recipient"],
                    items=items,
                )
            )

            return Response(
                status_code=201,
                body=result,
            )

        except (ValueError, KeyError) as error:
            return Response(
                status_code=400,
                body={"error": str(error)},
            )


backend_application = BackendApplication(
    validator=RequestValidator(),
    controller=build_application(),
)

request = Request(
    method="POST",
    path="/orders",
    body={
        "customer_id": "CUS-HTTP",
        "recipient": "http@example.com",
        "items": [
            {
                "product_name": "Keyboard",
                "unit_price": 2500,
                "quantity": 2,
            }
        ],
    },
)

response = backend_application.handle(request)

print("HTTP-like status:", response.status_code)
print("HTTP-like body:", response.body)


# ============================================================================
# 79. TESTING FAILURE CASES
# ============================================================================

print("\n" + "=" * 80)
print("79. FAILURE-CASE TESTING")
print("=" * 80)


def test_order_cannot_be_shipped_before_payment() -> None:
    test_order = Order(
        "ORD-TEST",
        "CUS-TEST",
        [OrderItem("Item", 100, 1)],
    )

    try:
        test_order.change_status(OrderStatus.SHIPPED)
    except ValueError:
        return

    raise AssertionError(
        "Order should not ship before payment."
    )


def test_inventory_rejects_excess_reservation() -> None:
    test_inventory = Inventory()
    test_inventory.add("SKU", 2)

    try:
        test_inventory.reserve("SKU", 3)
    except InsufficientStockError:
        return

    raise AssertionError(
        "Inventory should reject excessive reservations."
    )


test_order_cannot_be_shipped_before_payment()
test_inventory_rejects_excess_reservation()

print("Failure-case tests passed.")


# ============================================================================
# 80. DESIGN DECISION MATRIX
# ============================================================================

print("\n" + "=" * 80)
print("80. DESIGN DECISION MATRIX")
print("=" * 80)

design_decisions = {
    "Inheritance": "Use for a genuine substitutable is-a relationship.",
    "Composition": "Use to assemble behavior from collaborating objects.",
    "Encapsulation": "Use to protect invariants and control state changes.",
    "Abstraction": "Use to define stable contracts behind implementation details.",
    "Polymorphism": "Use when different implementations share a usable behavior.",
    "Repository": "Use to isolate persistence concerns from application logic.",
    "Dependency injection": "Use to make dependencies explicit and replaceable.",
    "Protocol": "Use when behavior-based interfaces are preferable.",
    "Dataclass": "Use for concise data-oriented models and value objects.",
    "Factory": "Use when object creation has meaningful selection logic.",
    "Strategy": "Use when an algorithm or policy varies independently.",
}

for concept, guidance in design_decisions.items():
    print(f"{concept}: {guidance}")


# ============================================================================
# 81. FINAL INTEGRATED EXAMPLE
# ============================================================================

print("\n" + "=" * 80)
print("81. INTEGRATED OBJECT-ORIENTED BACKEND DESIGN")
print("=" * 80)


class ProductCatalog(Protocol):
    def find_price(self, product_name: str) -> float:
        ...


class InMemoryProductCatalog:
    def __init__(self) -> None:
        self._prices = {
            "Laptop": 75000.0,
            "Mouse": 1500.0,
            "Keyboard": 2500.0,
        }

    def find_price(self, product_name: str) -> float:
        try:
            return self._prices[product_name]
        except KeyError as error:
            raise ProductNotFoundError(product_name) from error


@dataclass(frozen=True)
class PlaceOrderCommand:
    customer_id: str
    recipient: str
    product_name: str
    quantity: int


class IntegratedOrderService:
    """
    Integrated example showing:

    - dependency injection
    - protocols
    - domain objects
    - composition
    - validation
    - repository abstraction
    - notification abstraction
    - application-service orchestration
    """

    def __init__(
        self,
        catalog: ProductCatalog,
        repository: OrderRepository,
        notifier: NotificationSender,
    ) -> None:
        self.catalog = catalog
        self.repository = repository
        self.notifier = notifier

    def place_order(
        self,
        command: PlaceOrderCommand,
    ) -> Order:
        if command.quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        price = self.catalog.find_price(
            command.product_name
        )

        item = OrderItem(
            product_name=command.product_name,
            unit_price=price,
            quantity=command.quantity,
        )

        new_order = Order(
            order_id=f"ORD-{uuid.uuid4().hex[:8]}",
            customer_id=command.customer_id,
            items=[item],
        )

        self.repository.save(new_order)

        self.notifier.send(
            command.recipient,
            f"Order {new_order.order_id} "
            f"created for ₹{new_order.total:,.2f}.",
        )

        return new_order


integrated_repository = InMemoryOrderRepository()
integrated_notifier = ConsoleNotificationSender()
integrated_catalog = InMemoryProductCatalog()

integrated_service = IntegratedOrderService(
    catalog=integrated_catalog,
    repository=integrated_repository,
    notifier=integrated_notifier,
)

integrated_order = integrated_service.place_order(
    PlaceOrderCommand(
        customer_id="CUS-INTEGRATED",
        recipient="integrated@example.com",
        product_name="Laptop",
        quantity=1,
    )
)

print(
    "Integrated order:",
    integrated_order.order_id,
    integrated_order.total,
)


# ============================================================================
# 82. FINAL VALIDATION OF KEY OOP PRINCIPLES
# ============================================================================

print("\n" + "=" * 80)
print("82. PRINCIPLE VALIDATION")
print("=" * 80)

principle_checks = {
    "Class and object": isinstance(user_a, User),
    "Inheritance": isinstance(dog, Animal),
    "Encapsulation": secure_account.balance >= 0,
    "Abstraction": isinstance(
        CardPaymentProcessor(),
        PaymentProcessor,
    ),
    "Polymorphism": all(
        isinstance(item, Notification)
        for item in notifications
    ),
    "Composition": isinstance(car.engine, Engine),
    "Dependency injection": isinstance(
        service.repository,
        InMemoryOrderRepository,
    ),
    "Domain validation": order.total > 0,
    "Repository abstraction": repository.get("ORD-200") is order,
    "Immutable value object": Money(10).amount == 10,
}

for principle, passed in principle_checks.items():
    print(f"{principle}: {'PASS' if passed else 'FAIL'}")


# ============================================================================
# 83. PRACTICAL PRODUCTION CHECKLIST
# ============================================================================

print("\n" + "=" * 80)
print("83. PRODUCTION DESIGN CHECKLIST")
print("=" * 80)

production_checklist = [
    "Keep domain rules close to the domain objects that own them.",
    "Prefer composition when behavior is assembled rather than inherited.",
    "Use inheritance only when substitutability is genuinely valid.",
    "Depend on abstractions when infrastructure may vary.",
    "Inject database, messaging, payment, and external-service dependencies.",
    "Validate untrusted input at application boundaries.",
    "Use explicit domain exceptions for expected business failures.",
    "Do not expose secrets, passwords, or sensitive internal state in logs.",
    "Use secure password hashing rather than storing plaintext passwords.",
    "Use transactions for operations that require atomicity.",
    "Design retryable operations with idempotency where appropriate.",
    "Keep controllers thin and application services focused.",
    "Keep repositories focused on persistence rather than business rules.",
    "Measure performance before introducing unnecessary optimization.",
    "Avoid giant classes, deep inheritance trees, and circular dependencies.",
    "Write tests for both successful paths and business-rule failures.",
]

for item in production_checklist:
    print("[ ]", item)


# ============================================================================
# 84. END OF STUDY SCRIPT
# ============================================================================

print("\n" + "=" * 80)
print("OBJECT-ORIENTED BACKEND DESIGN STUDY COMPLETE")
print("=" * 80)

print(
    """
The executable examples above demonstrate how classes, inheritance,
composition, abstraction, encapsulation, and polymorphism combine with
backend-oriented architectural techniques.

The central design goal is not to maximize the number of classes. It is to
create clear responsibilities, controlled dependencies, strong domain
invariants, replaceable infrastructure, testable application logic, and
behavior that remains understandable as a backend grows.
"""
)
