"""
Dependency Injection: Dependencies, Reusable Logic, Dependency Chains,
and Database Dependencies

A self-contained study program progressing from beginner concepts to
advanced dependency-injection patterns.

Run:
    python dependency_injection.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol
import sqlite3
import time
import unittest


# ============================================================================
# 1. FUNDAMENTALS: WHAT IS A DEPENDENCY?
# ============================================================================

class EmailSender:
    """A concrete service responsible for sending email."""

    def send(self, recipient: str, message: str) -> None:
        print(f"[EMAIL] To={recipient}: {message}")


class WelcomeService:
    """
    This class has a dependency on EmailSender.

    The dependency is created internally, which is called tight coupling.
    It works, but testing and replacing EmailSender becomes harder.
    """

    def __init__(self) -> None:
        self.email_sender = EmailSender()

    def welcome(self, recipient: str) -> None:
        self.email_sender.send(recipient, "Welcome to the application.")


def demonstrate_tight_coupling() -> None:
    print("\n=== 1. Tight Coupling ===")
    service = WelcomeService()
    service.welcome("alice@example.com")


# ============================================================================
# 2. BASIC DEPENDENCY INJECTION
# ============================================================================

class MessageSender(Protocol):
    """Structural interface: anything with send() satisfies this contract."""

    def send(self, recipient: str, message: str) -> None:
        ...


class ConsoleSender:
    def send(self, recipient: str, message: str) -> None:
        print(f"[CONSOLE] To={recipient}: {message}")


class RecordingSender:
    """Useful for tests because it records calls instead of performing I/O."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, recipient: str, message: str) -> None:
        self.messages.append((recipient, message))


class InjectedWelcomeService:
    """
    Constructor injection.

    The class receives the dependency instead of constructing it itself.
    """

    def __init__(self, sender: MessageSender) -> None:
        self.sender = sender

    def welcome(self, recipient: str) -> None:
        self.sender.send(recipient, "Welcome to the application.")


def demonstrate_constructor_injection() -> None:
    print("\n=== 2. Constructor Injection ===")

    production_service = InjectedWelcomeService(ConsoleSender())
    production_service.welcome("bob@example.com")

    fake_sender = RecordingSender()
    test_service = InjectedWelcomeService(fake_sender)
    test_service.welcome("test@example.com")

    print("Recorded test message:", fake_sender.messages)


# ============================================================================
# 3. DIFFERENT FORMS OF INJECTION
# ============================================================================

class ReportGenerator:
    """A reusable reporting component."""

    def generate(self, title: str, values: Iterable[int]) -> str:
        numbers = list(values)
        total = sum(numbers)
        return f"{title}: count={len(numbers)}, total={total}"


class ReportApplication:
    """
    Method injection:
    the dependency is supplied only to the operation that needs it.
    """

    def run(self, generator: ReportGenerator, values: list[int]) -> str:
        return generator.generate("Sales", values)


class ConfigurableLogger:
    """Setter/property-style injection can be useful for optional dependencies."""

    def __init__(self) -> None:
        self._logger: Callable[[str], None] | None = None

    def set_logger(self, logger: Callable[[str], None]) -> None:
        self._logger = logger

    def execute(self) -> None:
        if self._logger is not None:
            self._logger("Operation executed.")


def demonstrate_injection_forms() -> None:
    print("\n=== 3. Injection Forms ===")

    generator = ReportGenerator()
    application = ReportApplication()
    print(application.run(generator, [10, 20, 30]))

    logger = ConfigurableLogger()
    logger.set_logger(lambda message: print("[LOG]", message))
    logger.execute()


# ============================================================================
# 4. ABSTRACTIONS AND DEPENDENCY INVERSION
# ============================================================================

class UserRepository(ABC):
    """Abstraction used by business logic instead of a database implementation."""

    @abstractmethod
    def find_email(self, user_id: int) -> str | None:
        raise NotImplementedError


class InMemoryUserRepository(UserRepository):
    def __init__(self, users: dict[int, str]) -> None:
        self.users = users

    def find_email(self, user_id: int) -> str | None:
        return self.users.get(user_id)


class DatabaseUserRepository(UserRepository):
    """A database-backed implementation of the same abstraction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_email(self, user_id: int) -> str | None:
        cursor = self.connection.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None


class UserNotificationService:
    """
    High-level business logic depends on UserRepository abstraction.

    It does not know whether the data comes from memory, SQLite,
    PostgreSQL, an API, or another source.
    """

    def __init__(self, repository: UserRepository, sender: MessageSender) -> None:
        self.repository = repository
        self.sender = sender

    def notify(self, user_id: int, message: str) -> bool:
        email = self.repository.find_email(user_id)

        if email is None:
            return False

        self.sender.send(email, message)
        return True


def demonstrate_dependency_inversion() -> None:
    print("\n=== 4. Dependency Inversion ===")

    repository = InMemoryUserRepository(
        {
            1: "alice@example.com",
            2: "bob@example.com",
        }
    )
    sender = ConsoleSender()

    service = UserNotificationService(repository, sender)

    print("Notification successful:", service.notify(1, "Your report is ready."))
    print("Unknown user:", service.notify(999, "This will not be sent."))


# ============================================================================
# 5. DATABASE DEPENDENCIES
# ============================================================================

def create_database() -> sqlite3.Connection:
    """
    Creates an in-memory database.

    Using an in-memory database keeps the example self-contained and avoids
    external database files.
    """
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE
        )
        """
    )
    connection.executemany(
        "INSERT INTO users (id, email) VALUES (?, ?)",
        [
            (1, "alice@example.com"),
            (2, "bob@example.com"),
        ],
    )
    connection.commit()
    return connection


def demonstrate_database_dependency() -> None:
    print("\n=== 5. Database Dependency ===")

    connection = create_database()
    repository = DatabaseUserRepository(connection)
    sender = ConsoleSender()

    service = UserNotificationService(repository, sender)

    service.notify(1, "Database-backed notification.")
    service.notify(2, "Another database-backed notification.")

    connection.close()


# ============================================================================
# 6. DEPENDENCY CHAINS
# ============================================================================

class AuditLogger:
    def record(self, event: str) -> None:
        print(f"[AUDIT] {event}")


class UserValidator:
    def validate(self, user_id: int, email: str) -> None:
        if user_id <= 0:
            raise ValueError("User ID must be positive.")

        if "@" not in email:
            raise ValueError("Invalid email address.")


class RegistrationService:
    """
    Dependency graph:

        RegistrationService
             |
             +--> UserRepository
             |
             +--> UserValidator
             |
             +--> AuditLogger
             |
             +--> MessageSender

    Each dependency may itself have dependencies.
    """

    def __init__(
        self,
        repository: UserRepository,
        validator: UserValidator,
        audit_logger: AuditLogger,
        sender: MessageSender,
    ) -> None:
        self.repository = repository
        self.validator = validator
        self.audit_logger = audit_logger
        self.sender = sender

    def register(self, user_id: int, email: str) -> bool:
        try:
            self.validator.validate(user_id, email)

            if self.repository.find_email(user_id) is not None:
                raise ValueError("User already exists.")

            # A real implementation would persist the user here.
            self.audit_logger.record(f"Registered user {user_id}")
            self.sender.send(email, "Registration successful.")
            return True

        except ValueError as error:
            self.audit_logger.record(f"Registration failed: {error}")
            return False


def demonstrate_dependency_chain() -> None:
    print("\n=== 6. Dependency Chain ===")

    repository = InMemoryUserRepository({1: "existing@example.com"})
    validator = UserValidator()
    audit_logger = AuditLogger()
    sender = ConsoleSender()

    service = RegistrationService(
        repository=repository,
        validator=validator,
        audit_logger=audit_logger,
        sender=sender,
    )

    print("New user:", service.register(2, "new@example.com"))
    print("Duplicate:", service.register(1, "existing@example.com"))
    print("Invalid:", service.register(-5, "invalid@example.com"))


# ============================================================================
# 7. FACTORY-BASED COMPOSITION
# ============================================================================

@dataclass(frozen=True)
class ApplicationConfig:
    environment: str
    database_url: str


def build_application(config: ApplicationConfig) -> UserNotificationService:
    """
    Composition root.

    Object construction is centralized here instead of being scattered
    through business classes.
    """
    if config.database_url == ":memory:":
        connection = create_database()
    else:
        connection = sqlite3.connect(config.database_url)

    repository = DatabaseUserRepository(connection)

    if config.environment == "test":
        sender: MessageSender = RecordingSender()
    else:
        sender = ConsoleSender()

    return UserNotificationService(repository, sender)


def demonstrate_composition_root() -> None:
    print("\n=== 7. Composition Root ===")

    config = ApplicationConfig(
        environment="production",
        database_url=":memory:",
    )

    service = build_application(config)
    service.notify(1, "Created through centralized composition.")


# ============================================================================
# 8. FACTORIES AS DEPENDENCIES
# ============================================================================

class Clock(Protocol):
    def now(self) -> float:
        ...


class SystemClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    def __init__(self, fixed_time: float) -> None:
        self.fixed_time = fixed_time

    def now(self) -> float:
        return self.fixed_time


class SessionService:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def create_session(self, user_id: int) -> dict[str, float | int]:
        return {
            "user_id": user_id,
            "created_at": self.clock.now(),
        }


def demonstrate_testable_time() -> None:
    print("\n=== 8. Injecting Time ===")

    fake_clock = FakeClock(1_700_000_000.0)
    service = SessionService(fake_clock)

    session = service.create_session(10)
    print(session)


# ============================================================================
# 9. A SMALL SERVICE CONTAINER
# ============================================================================

class ServiceContainer:
    """
    A deliberately small dependency container.

    This demonstrates the mechanism without hiding the design behind
    a third-party dependency-injection framework.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[["ServiceContainer"], object]] = {}
        self._singletons: dict[str, object] = {}

    def register_singleton(
        self,
        name: str,
        factory: Callable[["ServiceContainer"], object],
    ) -> None:
        self._factories[name] = factory

    def resolve(self, name: str) -> object:
        if name in self._singletons:
            return self._singletons[name]

        if name not in self._factories:
            raise KeyError(f"No service registered: {name}")

        instance = self._factories[name](self)
        self._singletons[name] = instance
        return instance


def demonstrate_container() -> None:
    print("\n=== 9. Dependency Container ===")

    container = ServiceContainer()

    container.register_singleton(
        "sender",
        lambda _: ConsoleSender(),
    )

    container.register_singleton(
        "repository",
        lambda _: InMemoryUserRepository(
            {
                1: "container@example.com",
            }
        ),
    )

    container.register_singleton(
        "notification_service",
        lambda c: UserNotificationService(
            repository=c.resolve("repository"),  # type: ignore[arg-type]
            sender=c.resolve("sender"),          # type: ignore[arg-type]
        ),
    )

    service = container.resolve("notification_service")
    assert isinstance(service, UserNotificationService)

    service.notify(1, "Resolved through the container.")


# ============================================================================
# 10. VALIDATION AND ERROR HANDLING
# ============================================================================

class PaymentGateway(Protocol):
    def charge(self, amount: float) -> str:
        ...


class FakePaymentGateway:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def charge(self, amount: float) -> str:
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")

        if self.should_fail:
            raise RuntimeError("Payment gateway unavailable.")

        return f"PAYMENT-{int(amount * 100)}"


class PaymentService:
    def __init__(self, gateway: PaymentGateway) -> None:
        self.gateway = gateway

    def pay(self, amount: float) -> str | None:
        try:
            return self.gateway.charge(amount)
        except (ValueError, RuntimeError) as error:
            print("[PAYMENT ERROR]", error)
            return None


def demonstrate_error_handling() -> None:
    print("\n=== 10. Error Handling ===")

    service = PaymentService(FakePaymentGateway())
    print("Success:", service.pay(49.99))
    print("Invalid:", service.pay(0))

    failing_service = PaymentService(FakePaymentGateway(should_fail=True))
    print("Failure:", failing_service.pay(20))


# ============================================================================
# 11. CACHING AS AN OPTIONAL DEPENDENCY
# ============================================================================

class Cache(Protocol):
    def get(self, key: str) -> object | None:
        ...

    def set(self, key: str, value: object) -> None:
        ...


class InMemoryCache:
    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def get(self, key: str) -> object | None:
        return self._values.get(key)

    def set(self, key: str, value: object) -> None:
        self._values[key] = value


class CachedUserService:
    def __init__(
        self,
        repository: UserRepository,
        cache: Cache | None = None,
    ) -> None:
        self.repository = repository
        self.cache = cache

    def find_email(self, user_id: int) -> str | None:
        key = f"user:{user_id}"

        if self.cache is not None:
            cached = self.cache.get(key)
            if isinstance(cached, str):
                print("[CACHE HIT]", key)
                return cached

        email = self.repository.find_email(user_id)

        if email is not None and self.cache is not None:
            self.cache.set(key, email)

        return email


def demonstrate_optional_dependency() -> None:
    print("\n=== 11. Optional Dependency ===")

    repository = InMemoryUserRepository({1: "cached@example.com"})
    cache = InMemoryCache()

    service = CachedUserService(repository, cache)

    print(service.find_email(1))
    print(service.find_email(1))


# ============================================================================
# 12. DEPENDENCY LIFETIMES
# ============================================================================

class RequestContext:
    """Represents state that should exist only for one request."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id


class RequestService:
    def __init__(self, context: RequestContext) -> None:
        self.context = context

    def execute(self) -> None:
        print(f"Processing request {self.context.request_id}")


def demonstrate_lifetimes() -> None:
    print("\n=== 12. Dependency Lifetimes ===")

    singleton_logger = AuditLogger()

    request_one = RequestContext("REQ-001")
    request_two = RequestContext("REQ-002")

    RequestService(request_one).execute()
    RequestService(request_two).execute()

    singleton_logger.record("One logger instance can serve many requests.")

    print("Transient-like contexts:", request_one is not request_two)
    print("Shared logger:", singleton_logger)


# ============================================================================
# 13. CIRCULAR DEPENDENCIES
# ============================================================================

class CircularDependencyExample:
    """
    Circular dependency:

        A -> B -> A

    Such graphs make construction and ownership difficult.
    A better design usually introduces a third abstraction or changes
    responsibility boundaries.
    """

    pass


def demonstrate_circular_dependency_principle() -> None:
    print("\n=== 13. Circular Dependencies ===")
    print("Avoid dependency graphs containing A -> B -> A.")
    print("Prefer clear ownership and abstractions that break the cycle.")


# ============================================================================
# 14. TESTS
# ============================================================================

class DependencyInjectionTests(unittest.TestCase):
    def test_notification_uses_injected_sender(self) -> None:
        repository = InMemoryUserRepository({1: "alice@example.com"})
        sender = RecordingSender()
        service = UserNotificationService(repository, sender)

        result = service.notify(1, "Hello")

        self.assertTrue(result)
        self.assertEqual(
            sender.messages,
            [("alice@example.com", "Hello")],
        )

    def test_unknown_user_is_not_notified(self) -> None:
        repository = InMemoryUserRepository({})
        sender = RecordingSender()
        service = UserNotificationService(repository, sender)

        self.assertFalse(service.notify(99, "Hello"))
        self.assertEqual(sender.messages, [])

    def test_database_repository(self) -> None:
        connection = create_database()
        repository = DatabaseUserRepository(connection)

        self.assertEqual(
            repository.find_email(1),
            "alice@example.com",
        )
        self.assertIsNone(repository.find_email(999))
        connection.close()

    def test_fake_clock_makes_time_deterministic(self) -> None:
        service = SessionService(FakeClock(123.0))
        self.assertEqual(
            service.create_session(5),
            {
                "user_id": 5,
                "created_at": 123.0,
            },
        )

    def test_payment_validation(self) -> None:
        service = PaymentService(FakePaymentGateway())
        self.assertIsNone(service.pay(-10))


def run_tests() -> None:
    print("\n=== 14. Automated Tests ===")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        DependencyInjectionTests
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


# ============================================================================
# 15. PERFORMANCE DISCUSSION THROUGH EXECUTABLE COMPARISON
# ============================================================================

def direct_function(value: int) -> int:
    return value * 2


class FunctionService:
    def __init__(self, operation: Callable[[int], int]) -> None:
        self.operation = operation

    def execute(self, value: int) -> int:
        return self.operation(value)


def demonstrate_indirection_cost() -> None:
    print("\n=== 15. Dependency Indirection ===")

    service = FunctionService(direct_function)

    values = list(range(10_000))
    start = time.perf_counter()
    results = [service.execute(value) for value in values]
    elapsed = time.perf_counter() - start

    print("Processed:", len(results))
    print("First result:", results[0])
    print(f"Elapsed time: {elapsed:.6f} seconds")
    print(
        "DI introduces a small level of indirection; "
        "I/O, database, network, and business operations usually dominate."
    )


# ============================================================================
# 16. PRODUCTION-STYLE COMPOSITION
# ============================================================================

@dataclass
class Application:
    notification_service: UserNotificationService
    payment_service: PaymentService
    session_service: SessionService


def compose_application() -> Application:
    """
    A production-style composition function.

    Concrete infrastructure is selected at the boundary.
    Core services receive abstractions.
    """
    connection = create_database()
    repository = DatabaseUserRepository(connection)
    sender = ConsoleSender()
    payment_gateway = FakePaymentGateway()
    clock = SystemClock()

    return Application(
        notification_service=UserNotificationService(
            repository,
            sender,
        ),
        payment_service=PaymentService(
            payment_gateway,
        ),
        session_service=SessionService(
            clock,
        ),
    )


def demonstrate_complete_application() -> None:
    print("\n=== 16. Complete Composition ===")

    application = compose_application()

    application.notification_service.notify(
        1,
        "Your account is active.",
    )

    print(
        "Payment ID:",
        application.payment_service.pay(125.50),
    )

    print(
        "Session:",
        application.session_service.create_session(1),
    )


# ============================================================================
# 17. BEST-PRACTICE CHECKLIST AS DATA
# ============================================================================

BEST_PRACTICES = [
    "Inject dependencies instead of constructing infrastructure inside business logic.",
    "Depend on stable abstractions where substitution provides real value.",
    "Prefer constructor injection for required dependencies.",
    "Keep object composition at application boundaries.",
    "Use test doubles for external systems.",
    "Keep dependency graphs acyclic.",
    "Choose dependency lifetimes deliberately.",
    "Avoid service containers when manual composition is clearer.",
    "Validate configuration before constructing infrastructure.",
    "Keep interfaces focused on behavior actually required by consumers.",
    "Do not abstract every class merely because abstraction is possible.",
    "Consider startup, runtime, memory, and operational costs.",
]


def print_best_practices() -> None:
    print("\n=== 17. Best Practices ===")
    for index, practice in enumerate(BEST_PRACTICES, start=1):
        print(f"{index:02d}. {practice}")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    print("=" * 78)
    print("DEPENDENCY INJECTION: COMPLETE PYTHON STUDY")
    print("=" * 78)

    demonstrate_tight_coupling()
    demonstrate_constructor_injection()
    demonstrate_injection_forms()
    demonstrate_dependency_inversion()
    demonstrate_database_dependency()
    demonstrate_dependency_chain()
    demonstrate_composition_root()
    demonstrate_testable_time()
    demonstrate_container()
    demonstrate_error_handling()
    demonstrate_optional_dependency()
    demonstrate_lifetimes()
    demonstrate_circular_dependency_principle()
    run_tests()
    demonstrate_indirection_cost()
    demonstrate_complete_application()
    print_best_practices()

    print("\nStudy execution completed successfully.")


if __name__ == "__main__":
    main()
