"""
PYTHON FOR BACKEND DEVELOPMENT
Data Structures, Functions, Classes, Decorators, Iterators, Generators, and Typing

This is a self-contained study script that progresses from Python fundamentals
to backend-oriented design patterns. It uses only the Python standard library.

Run:
    python backend_python_fundamentals.py

The examples are intentionally executable. Most demonstrations print their
results so that the behavior can be observed directly.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache, wraps
from itertools import islice
from pathlib import Path
from time import perf_counter
from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Sequence,
    TypeAlias,
    TypeVar,
    TypedDict,
    cast,
    overload,
)
import math
import statistics
import time


# ============================================================================
# 1. BASIC PYTHON OBJECTS AND VARIABLES
# ============================================================================

def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    """Print a smaller heading."""
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def demonstrate_basic_types() -> None:
    section("1. Python objects, variables, and basic types")

    user_id = 101
    username = "atul"
    account_balance = 1250.75
    is_active = True
    nothing = None

    print("Integer:", user_id, type(user_id))
    print("String:", username, type(username))
    print("Float:", account_balance, type(account_balance))
    print("Boolean:", is_active, type(is_active))
    print("None:", nothing, type(nothing))

    # Python variables are references to objects.
    first_name = "Atul"
    second_name = first_name
    print("Same immutable string value:", first_name == second_name)

    # Strings are immutable, so operations create new strings.
    normalized_username = username.strip().lower()
    print("Normalized username:", normalized_username)

    # Truthiness is commonly used in backend validation.
    values = ["", [], {}, None, 0, False, "valid"]
    for value in values:
        print(repr(value), "is truthy:", bool(value))


# ============================================================================
# 2. LISTS
# ============================================================================

def demonstrate_lists() -> None:
    section("2. Lists")

    users = ["alice", "bob", "charlie"]
    users.append("diana")
    users.extend(["eve", "frank"])

    print("Users:", users)
    print("First:", users[0])
    print("Last:", users[-1])
    print("Slice:", users[1:4])

    users[1] = "robert"
    print("After replacement:", users)

    removed = users.pop()
    print("Removed:", removed)
    print("After pop:", users)

    # List comprehension is useful for transformation and filtering.
    active_users = [name for name in users if len(name) >= 5]
    print("Users with at least five characters:", active_users)

    # Avoid modifying a list while iterating over it.
    numbers = [1, 2, 3, 4, 5, 6]
    even_numbers = [number for number in numbers if number % 2 == 0]
    print("Filtered safely:", even_numbers)

    # Complexity considerations:
    # append() is amortized O(1)
    # indexed lookup is O(1)
    # membership testing with "in" is O(n)
    # insertion/removal near the beginning is O(n)


# ============================================================================
# 3. TUPLES
# ============================================================================

def demonstrate_tuples() -> None:
    section("3. Tuples")

    coordinates = (28.6139, 77.2090)
    print("Coordinates:", coordinates)

    latitude, longitude = coordinates
    print("Latitude:", latitude)
    print("Longitude:", longitude)

    # A one-element tuple requires a trailing comma.
    single_item_tuple = ("backend",)
    print("Single-item tuple:", single_item_tuple)

    # Tuples are immutable.
    # coordinates[0] = 0  # Would raise TypeError.

    # Tuples are useful for fixed structures and can be dictionary keys
    # when all contained values are hashable.
    locations = {
        (28.6139, 77.2090): "Delhi",
        (26.8467, 80.9462): "Lucknow",
    }
    print("Location lookup:", locations[(26.8467, 80.9462)])


# ============================================================================
# 4. DICTIONARIES
# ============================================================================

def demonstrate_dictionaries() -> None:
    section("4. Dictionaries")

    user = {
        "id": 101,
        "name": "Atul",
        "role": "developer",
        "active": True,
    }

    print("User:", user)
    print("Name:", user["name"])
    print("Safe lookup:", user.get("email", "not provided"))

    user["role"] = "backend developer"
    user["email"] = "user@example.com"
    user.pop("active")

    print("Updated user:", user)
    print("Keys:", list(user.keys()))
    print("Values:", list(user.values()))
    print("Items:", list(user.items()))

    # Dictionary comprehension.
    squares = {number: number * number for number in range(1, 6)}
    print("Squares:", squares)

    # Backend-style indexing.
    users_by_id = {
        101: {"name": "Atul"},
        102: {"name": "Riya"},
        103: {"name": "Aman"},
    }
    print("Indexed user:", users_by_id.get(102))

    # Membership checks keys by default.
    print("102 exists:", 102 in users_by_id)


# ============================================================================
# 5. SETS
# ============================================================================

def demonstrate_sets() -> None:
    section("5. Sets")

    requested_permissions = {"read", "write", "read"}
    print("Unique permissions:", requested_permissions)

    role_permissions = {"read", "write", "delete"}
    user_permissions = {"read", "write"}

    print("Can read:", "read" in user_permissions)
    print("Missing permissions:", role_permissions - user_permissions)
    print("Shared permissions:", role_permissions & user_permissions)
    print("All permissions:", role_permissions | user_permissions)
    print("Exactly same:", role_permissions == user_permissions)

    # Sets provide average O(1) membership testing.
    # They are excellent for permission checks, deduplication, and tags.


# ============================================================================
# 6. STACKS AND QUEUES
# ============================================================================

def demonstrate_stack_and_queue() -> None:
    section("6. Stacks and queues")

    # A list can implement a stack efficiently using append/pop at the end.
    stack: list[str] = []
    stack.append("request")
    stack.append("validation")
    stack.append("database")

    print("Stack:", stack)
    print("Popped:", stack.pop())
    print("Stack after pop:", stack)

    # deque is preferable for queues because left-side operations are O(1).
    request_queue: deque[str] = deque()
    request_queue.append("request-1")
    request_queue.append("request-2")
    request_queue.append("request-3")

    print("Queue:", request_queue)
    print("Processed:", request_queue.popleft())
    print("Queue after processing:", request_queue)


# ============================================================================
# 7. COLLECTIONS
# ============================================================================

def demonstrate_collections() -> None:
    section("7. Useful collection types")

    words = ["api", "api", "db", "cache", "api", "db"]
    counts = Counter(words)
    print("Counter:", counts)
    print("Most common:", counts.most_common(2))

    grouped_users: defaultdict[str, list[str]] = defaultdict(list)
    grouped_users["admin"].append("alice")
    grouped_users["admin"].append("bob")
    grouped_users["user"].append("charlie")
    print("Grouped users:", dict(grouped_users))

    # defaultdict avoids repetitive "if key does not exist" checks.


# ============================================================================
# 8. FUNCTIONS
# ============================================================================

def greet_user(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}."


def calculate_total(price: float, quantity: int = 1, tax_rate: float = 0.0) -> float:
    """Calculate a simple tax-inclusive total."""
    if quantity < 0:
        raise ValueError("quantity cannot be negative")
    if price < 0:
        raise ValueError("price cannot be negative")
    if tax_rate < 0:
        raise ValueError("tax_rate cannot be negative")

    subtotal = price * quantity
    tax = subtotal * tax_rate
    return subtotal + tax


def demonstrate_functions() -> None:
    section("8. Functions")

    print(greet_user("Atul"))
    print(calculate_total(100, 3, 0.18))

    # Positional and keyword arguments.
    print(calculate_total(price=250, quantity=2, tax_rate=0.05))

    # *args accepts variable positional arguments.
    def add_many(*numbers: float) -> float:
        return sum(numbers)

    print("add_many:", add_many(1, 2, 3, 4, 5))

    # **kwargs accepts variable keyword arguments.
    def build_query(**filters: Any) -> dict[str, Any]:
        return filters

    print("Query filters:", build_query(status="active", role="admin"))

    # Combining both.
    def audit_event(event: str, *details: str, **metadata: Any) -> dict[str, Any]:
        return {
            "event": event,
            "details": details,
            "metadata": metadata,
        }

    print(
        "Audit event:",
        audit_event(
            "login",
            "password",
            "mfa",
            user_id=101,
            source="web",
        ),
    )


# ============================================================================
# 9. FIRST-CLASS FUNCTIONS, LAMBDA, MAP, FILTER, REDUCE
# ============================================================================

def demonstrate_functional_features() -> None:
    section("9. Functions as objects")

    def apply_operation(
        value: float,
        operation: Callable[[float], float],
    ) -> float:
        return operation(value)

    def square(value: float) -> float:
        return value * value

    print("Function passed as argument:", apply_operation(5, square))
    print("Lambda:", apply_operation(5, lambda value: value + 10))

    numbers = [1, 2, 3, 4, 5]

    doubled = list(map(lambda number: number * 2, numbers))
    even = list(filter(lambda number: number % 2 == 0, numbers))

    print("map:", doubled)
    print("filter:", even)

    # Comprehensions are often clearer than map/filter for simple operations.
    print("Comprehension:", [number * 2 for number in numbers])


# ============================================================================
# 10. SCOPE AND CLOSURES
# ============================================================================

def demonstrate_scope_and_closure() -> None:
    section("10. Scope and closures")

    global_constant = 100

    def outer_function(multiplier: int) -> Callable[[int], int]:
        # multiplier is captured by the nested function.
        def inner_function(value: int) -> int:
            return value * multiplier

        return inner_function

    multiply_by_three = outer_function(3)
    print("Closure result:", multiply_by_three(10))
    print("Outer value:", global_constant)

    # A closure retains access to variables from its enclosing scope.
    def make_counter() -> Callable[[], int]:
        count = 0

        def increment() -> int:
            nonlocal count
            count += 1
            return count

        return increment

    counter = make_counter()
    print(counter())
    print(counter())
    print(counter())


# ============================================================================
# 11. RECURSION
# ============================================================================

def factorial_recursive(number: int) -> int:
    if number < 0:
        raise ValueError("factorial is undefined for negative integers")
    if number in (0, 1):
        return 1
    return number * factorial_recursive(number - 1)


def demonstrate_recursion() -> None:
    section("11. Recursion")

    print("5!:", factorial_recursive(5))

    # Recursion can be elegant for trees, but Python has a recursion-depth limit.
    # Iterative solutions are often safer for very deep input.


# ============================================================================
# 12. CLASSES AND OBJECTS
# ============================================================================

class User:
    """Basic domain object representing an application user."""

    account_type: ClassVar[str] = "standard"

    def __init__(self, user_id: int, name: str, email: str) -> None:
        self.user_id = user_id
        self.name = name
        self.email = email
        self._is_active = True

    def deactivate(self) -> None:
        self._is_active = False

    def activate(self) -> None:
        self._is_active = True

    @property
    def is_active(self) -> bool:
        return self._is_active

    def __repr__(self) -> str:
        return (
            f"User(user_id={self.user_id!r}, "
            f"name={self.name!r}, email={self.email!r})"
        )


def demonstrate_classes() -> None:
    section("12. Classes and objects")

    user = User(101, "Atul", "atul@example.com")
    print(user)
    print("Active:", user.is_active)

    user.deactivate()
    print("Active after deactivation:", user.is_active)

    print("Class attribute:", User.account_type)


# ============================================================================
# 13. ENCAPSULATION, PROPERTIES, CLASSMETHOD, STATICMETHOD
# ============================================================================

class BankAccount:
    """Demonstrates state management and controlled access."""

    bank_name: ClassVar[str] = "Example Bank"

    def __init__(self, owner: str, opening_balance: float = 0.0) -> None:
        if opening_balance < 0:
            raise ValueError("opening balance cannot be negative")

        self.owner = owner
        self._balance = opening_balance

    @property
    def balance(self) -> float:
        return self._balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("deposit must be positive")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("withdrawal must be positive")
        if amount > self._balance:
            raise ValueError("insufficient funds")
        self._balance -= amount

    @classmethod
    def from_string(cls, value: str) -> "BankAccount":
        owner, balance = value.split(":")
        return cls(owner.strip(), float(balance))

    @staticmethod
    def is_valid_owner_name(owner: str) -> bool:
        return bool(owner.strip())


def demonstrate_encapsulation() -> None:
    section("13. Encapsulation and class utilities")

    account = BankAccount("Atul", 1000)
    account.deposit(500)
    account.withdraw(250)

    print("Balance:", account.balance)
    print("Valid owner:", BankAccount.is_valid_owner_name("Atul"))

    parsed_account = BankAccount.from_string("Riya:750")
    print("Parsed account:", parsed_account.owner, parsed_account.balance)


# ============================================================================
# 14. INHERITANCE AND POLYMORPHISM
# ============================================================================

class AdminUser(User):
    """Specialized user with administrative privileges."""

    account_type: ClassVar[str] = "admin"

    def __init__(
        self,
        user_id: int,
        name: str,
        email: str,
        permissions: set[str] | None = None,
    ) -> None:
        super().__init__(user_id, name, email)
        self.permissions = permissions or set()

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


class GuestUser(User):
    """User with restricted access."""

    account_type: ClassVar[str] = "guest"

    def has_permission(self, permission: str) -> bool:
        return False


def demonstrate_inheritance_and_polymorphism() -> None:
    section("14. Inheritance and polymorphism")

    admin = AdminUser(
        1,
        "Alice",
        "alice@example.com",
        {"read", "write", "delete"},
    )
    guest = GuestUser(2, "Bob", "bob@example.com")

    for current_user in [admin, guest]:
        print(
            current_user.name,
            current_user.account_type,
            current_user.has_permission("delete"),
        )


# ============================================================================
# 15. DATACLASSES
# ============================================================================

@dataclass
class Product:
    """Compact representation of structured domain data."""

    product_id: int
    name: str
    price: float
    tags: list[str] = field(default_factory=list)

    def discounted_price(self, percentage: float) -> float:
        if not 0 <= percentage <= 100:
            raise ValueError("percentage must be between 0 and 100")
        return self.price * (1 - percentage / 100)


def demonstrate_dataclasses() -> None:
    section("15. Dataclasses")

    product = Product(
        product_id=501,
        name="Keyboard",
        price=2500.0,
        tags=["hardware", "input"],
    )

    print(product)
    print("Discounted:", product.discounted_price(10))


# ============================================================================
# 16. MAGIC METHODS / DUNDER METHODS
# ============================================================================

class Money:
    """Small value object demonstrating operator overloading."""

    def __init__(self, amount: float, currency: str = "INR") -> None:
        self.amount = float(amount)
        self.currency = currency

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return (
            self.amount == other.amount
            and self.currency == other.currency
        )

    def __repr__(self) -> str:
        return f"Money({self.amount:.2f}, {self.currency!r})"


def demonstrate_dunder_methods() -> None:
    section("16. Special methods")

    first = Money(100)
    second = Money(250)
    print("Addition:", first + second)
    print("Equality:", first == Money(100))


# ============================================================================
# 17. ABSTRACT INTERFACES AND PROTOCOLS
# ============================================================================

class LoggerProtocol(Protocol):
    def log(self, message: str) -> None:
        ...


class ConsoleLogger:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")


class MemoryLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        self.messages.append(message)


def process_request(
    logger: LoggerProtocol,
    request_name: str,
) -> str:
    logger.log(f"Processing {request_name}")
    return "success"


def demonstrate_protocols() -> None:
    section("17. Protocols and structural typing")

    console_logger = ConsoleLogger()
    memory_logger = MemoryLogger()

    print(process_request(console_logger, "GET /users"))
    print(process_request(memory_logger, "POST /users"))
    print("Stored messages:", memory_logger.messages)


# ============================================================================
# 18. ITERABLES AND ITERATORS
# ============================================================================

def demonstrate_iterables_and_iterators() -> None:
    section("18. Iterables and iterators")

    numbers = [10, 20, 30]

    # An iterable can produce an iterator.
    iterator = iter(numbers)

    print("First:", next(iterator))
    print("Second:", next(iterator))
    print("Third:", next(iterator))

    try:
        print(next(iterator))
    except StopIteration:
        print("Iterator is exhausted.")

    # for loops use the iterator protocol internally.
    for number in numbers:
        print("for-loop value:", number)

    # Strings, tuples, sets, dictionaries, files, and many other objects
    # are iterable.


# ============================================================================
# 19. CUSTOM ITERATOR
# ============================================================================

class Countdown:
    """Iterator that counts down from a starting integer."""

    def __init__(self, start: int) -> None:
        self.current = start

    def __iter__(self) -> "Countdown":
        return self

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration

        value = self.current
        self.current -= 1
        return value


def demonstrate_custom_iterator() -> None:
    section("19. Custom iterator")

    countdown = Countdown(5)

    for value in countdown:
        print(value)


# ============================================================================
# 20. GENERATORS
# ============================================================================

def number_generator(start: int, end: int) -> Iterator[int]:
    """Yield integers lazily."""
    for number in range(start, end + 1):
        yield number


def demonstrate_generators() -> None:
    section("20. Generators")

    generator = number_generator(1, 5)

    print("Generator object:", generator)

    for number in generator:
        print("Generated:", number)

    # Generator expressions are compact lazy pipelines.
    squares = (number * number for number in range(1, 6))

    print("First square:", next(squares))
    print("Remaining squares:", list(squares))

    # Generators are useful when processing large files, streams, database
    # records, or API results without loading everything into memory.


# ============================================================================
# 21. GENERATOR PIPELINES
# ============================================================================

def read_numbers() -> Iterator[int]:
    for number in range(1, 101):
        yield number


def filter_even(numbers: Iterable[int]) -> Iterator[int]:
    for number in numbers:
        if number % 2 == 0:
            yield number


def square_numbers(numbers: Iterable[int]) -> Iterator[int]:
    for number in numbers:
        yield number * number


def demonstrate_generator_pipeline() -> None:
    section("21. Lazy generator pipeline")

    pipeline = square_numbers(filter_even(read_numbers()))

    first_ten = list(islice(pipeline, 10))
    print("First ten results:", first_ten)


# ============================================================================
# 22. SEND, THROW, AND CLOSE IN GENERATORS
# ============================================================================

def accumulator() -> Iterator[int]:
    total = 0

    while True:
        incoming = yield total
        if incoming is None:
            return
        total += incoming


def demonstrate_advanced_generator_protocol() -> None:
    section("22. Advanced generator protocol")

    generator = accumulator()

    print("Initial:", next(generator))
    print("After 10:", generator.send(10))
    print("After 25:", generator.send(25))
    generator.close()

    # send(), throw(), and close() are advanced generator controls.
    # They are useful for specialized coroutine-style designs but are not
    # required for ordinary data streaming.


# ============================================================================
# 23. DECORATORS
# ============================================================================

def log_call(function: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that logs a function invocation."""

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        print(f"Calling {function.__name__}")
        result = function(*args, **kwargs)
        print(f"Finished {function.__name__}")
        return result

    return wrapper


@log_call
def multiply(a: int, b: int) -> int:
    return a * b


def demonstrate_decorators() -> None:
    section("23. Decorators")

    print("Result:", multiply(6, 7))

    # A decorator is a callable that receives a function/class and returns
    # a modified or replacement callable.


# ============================================================================
# 24. DECORATOR WITH PARAMETERS
# ============================================================================

def repeat(times: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that repeats a function call."""

    if times < 1:
        raise ValueError("times must be at least 1")

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = None
            for _ in range(times):
                result = function(*args, **kwargs)
            return result

        return wrapper

    return decorator


@repeat(3)
def say_backend() -> None:
    print("Backend")


def demonstrate_parameterized_decorator() -> None:
    section("24. Parameterized decorators")

    say_backend()


# ============================================================================
# 25. AUTHORIZATION DECORATOR
# ============================================================================

def require_role(required_role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Backend-style authorization decorator."""

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapper(user_role: str, *args: Any, **kwargs: Any) -> Any:
            if user_role != required_role:
                raise PermissionError(
                    f"Role '{required_role}' required; received '{user_role}'"
                )
            return function(user_role, *args, **kwargs)

        return wrapper

    return decorator


@require_role("admin")
def delete_user(user_role: str, user_id: int) -> str:
    return f"Deleted user {user_id}"


def demonstrate_authorization_decorator() -> None:
    section("25. Backend authorization decorator")

    print(delete_user("admin", 101))

    try:
        delete_user("guest", 101)
    except PermissionError as error:
        print("Authorization error:", error)


# ============================================================================
# 26. TIMING DECORATOR
# ============================================================================

def measure_time(function: Callable[..., Any]) -> Callable[..., Any]:
    """Measure execution time without changing the function's result."""

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        result = function(*args, **kwargs)
        elapsed = perf_counter() - started
        print(f"{function.__name__} took {elapsed:.6f} seconds")
        return result

    return wrapper


@measure_time
def compute_sum(limit: int) -> int:
    return sum(range(limit))


def demonstrate_timing_decorator() -> None:
    section("26. Timing decorator")
    print("Computed:", compute_sum(1_000_000))


# ============================================================================
# 27. CACHING AND MEMOIZATION
# ============================================================================

@lru_cache(maxsize=128)
def fibonacci(number: int) -> int:
    if number < 0:
        raise ValueError("number cannot be negative")
    if number < 2:
        return number
    return fibonacci(number - 1) + fibonacci(number - 2)


def demonstrate_caching() -> None:
    section("27. Caching and memoization")

    print("Fibonacci 30:", fibonacci(30))
    print("Cache information:", fibonacci.cache_info())

    # Caching can dramatically reduce repeated deterministic computation.
    # It must not be used blindly for values that become stale or depend on
    # hidden mutable state.


# ============================================================================
# 28. TYPE HINTS
# ============================================================================

UserRecord: TypeAlias = dict[str, Any]
UserID: TypeAlias = int


def find_user(
    users: Mapping[UserID, UserRecord],
    user_id: UserID,
) -> UserRecord | None:
    return users.get(user_id)


def average(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    return statistics.mean(values)


def demonstrate_type_hints() -> None:
    section("28. Type hints")

    users: dict[int, UserRecord] = {
        101: {"name": "Atul", "role": "developer"},
        102: {"name": "Riya", "role": "admin"},
    }

    print(find_user(users, 101))
    print("Average:", average([10.0, 20.0, 30.0]))

    # Type hints improve readability, editor support, static analysis, and
    # maintenance. Python normally does not enforce annotations at runtime.


# ============================================================================
# 29. OPTIONAL VALUES
# ============================================================================

def find_email(user: Mapping[str, Any]) -> str | None:
    value = user.get("email")

    if value is None:
        return None

    return str(value)


def demonstrate_optional_values() -> None:
    section("29. Optional values")

    print(find_email({"name": "Atul", "email": "atul@example.com"}))
    print(find_email({"name": "Anonymous"}))

    # None should be handled explicitly when absence has semantic meaning.


# ============================================================================
# 30. LITERAL, TYPEDDICT, AND STRUCTURED API DATA
# ============================================================================

UserStatus = Literal["active", "inactive", "suspended"]


class UserPayload(TypedDict):
    user_id: int
    name: str
    status: UserStatus


def create_user_payload(
    user_id: int,
    name: str,
    status: UserStatus,
) -> UserPayload:
    return {
        "user_id": user_id,
        "name": name,
        "status": status,
    }


def demonstrate_structured_typing() -> None:
    section("30. Literal and TypedDict")

    payload = create_user_payload(
        user_id=101,
        name="Atul",
        status="active",
    )

    print("Payload:", payload)


# ============================================================================
# 31. GENERIC TYPES
# ============================================================================

T = TypeVar("T")


class Repository(Generic[T]):
    """Simple in-memory generic repository."""

    def __init__(self) -> None:
        self._items: dict[int, T] = {}

    def save(self, item_id: int, item: T) -> None:
        self._items[item_id] = item

    def get(self, item_id: int) -> T | None:
        return self._items.get(item_id)

    def all(self) -> list[T]:
        return list(self._items.values())


def demonstrate_generics() -> None:
    section("31. Generics")

    user_repository = Repository[User]()
    user_repository.save(
        1,
        User(1, "Alice", "alice@example.com"),
    )

    print("Generic repository result:", user_repository.get(1))


# ============================================================================
# 32. OVERLOADS
# ============================================================================

@overload
def normalize_identifier(value: int) -> str:
    ...


@overload
def normalize_identifier(value: str) -> str:
    ...


def normalize_identifier(value: int | str) -> str:
    return str(value).strip().lower()


def demonstrate_overload() -> None:
    section("32. Function overloads")

    print(normalize_identifier(123))
    print(normalize_identifier(" ABC "))

    # @overload primarily communicates multiple accepted call signatures to
    # static type checkers. Runtime behavior comes from the implementation.


# ============================================================================
# 33. ANY, CAST, AND RUNTIME VALIDATION
# ============================================================================

def parse_id(raw_value: Any) -> int:
    """Convert an externally supplied value into an integer safely."""
    try:
        return int(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid user id") from error


def demonstrate_runtime_validation() -> None:
    section("33. Static typing versus runtime validation")

    print(parse_id("101"))

    try:
        parse_id("not-a-number")
    except ValueError as error:
        print("Validation error:", error)

    # Type hints do not protect a backend from malformed HTTP/JSON input.
    # External data still requires runtime validation.


# ============================================================================
# 34. CUSTOM COLLECTION WITH TYPING
# ============================================================================

class TypedStack(Generic[T]):
    """Generic LIFO stack."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("cannot pop from empty stack")
        return self._items.pop()

    def __len__(self) -> int:
        return len(self._items)


def demonstrate_typed_collection() -> None:
    section("34. Generic collection implementation")

    stack = TypedStack[str]()
    stack.push("authentication")
    stack.push("authorization")

    print("Length:", len(stack))
    print("Pop:", stack.pop())


# ============================================================================
# 35. ERROR HANDLING
# ============================================================================

class ValidationError(ValueError):
    """Raised when application input violates domain rules."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


def get_user_or_fail(
    users: Mapping[int, UserRecord],
    user_id: int,
) -> UserRecord:
    user = users.get(user_id)

    if user is None:
        raise NotFoundError(f"User {user_id} was not found")

    return user


def demonstrate_error_handling() -> None:
    section("35. Error handling")

    users = {101: {"name": "Atul"}}

    try:
        get_user_or_fail(users, 999)
    except NotFoundError as error:
        print("Not found:", error)
    except Exception as error:
        print("Unexpected error:", error)
    else:
        print("Operation succeeded.")
    finally:
        print("Cleanup can happen here.")


# ============================================================================
# 36. EXCEPTION CHAINING
# ============================================================================

def convert_price(raw_price: str) -> float:
    try:
        price = float(raw_price)
    except ValueError as error:
        raise ValidationError("price must be numeric") from error

    if price < 0:
        raise ValidationError("price cannot be negative")

    return price


def demonstrate_exception_chaining() -> None:
    section("36. Exception chaining")

    try:
        convert_price("invalid")
    except ValidationError as error:
        print("Application error:", error)
        print("Original cause:", repr(error.__cause__))


# ============================================================================
# 37. FILE ITERATION
# ============================================================================

def stream_lines(path: Path) -> Iterator[str]:
    """Yield file lines one at a time."""
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            yield line.rstrip("\n")


def demonstrate_file_iteration() -> None:
    section("37. Streaming files with iterators")

    temporary_path = Path("backend_python_demo.txt")

    temporary_path.write_text(
        "first request\n"
        "second request\n"
        "third request\n",
        encoding="utf-8",
    )

    try:
        for line in stream_lines(temporary_path):
            print("Streamed:", line)
    finally:
        temporary_path.unlink(missing_ok=True)

    # Reading line-by-line prevents unnecessarily loading a huge file into RAM.


# ============================================================================
# 38. BACKEND-STYLE SERVICE AND REPOSITORY DESIGN
# ============================================================================

@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    email: str


class CustomerRepository:
    """Persistence abstraction using memory instead of a real database."""

    def __init__(self) -> None:
        self._customers: dict[int, Customer] = {}

    def save(self, customer: Customer) -> Customer:
        self._customers[customer.customer_id] = customer
        return customer

    def get(self, customer_id: int) -> Customer | None:
        return self._customers.get(customer_id)

    def list_all(self) -> list[Customer]:
        return list(self._customers.values())


class CustomerService:
    """Business logic separated from storage logic."""

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def create_customer(
        self,
        customer_id: int,
        name: str,
        email: str,
    ) -> Customer:
        if not name.strip():
            raise ValidationError("name is required")

        if "@" not in email:
            raise ValidationError("invalid email")

        if self.repository.get(customer_id) is not None:
            raise ValidationError("customer already exists")

        customer = Customer(
            customer_id=customer_id,
            name=name.strip(),
            email=email.strip().lower(),
        )

        return self.repository.save(customer)


def demonstrate_backend_layers() -> None:
    section("38. Backend-style repository and service layers")

    repository = CustomerRepository()
    service = CustomerService(repository)

    customer = service.create_customer(
        1,
        "Atul Pandey",
        "ATUL@example.com",
    )

    print("Created:", customer)
    print("Stored:", repository.list_all())

    try:
        service.create_customer(
            1,
            "Another User",
            "another@example.com",
        )
    except ValidationError as error:
        print("Business validation:", error)


# ============================================================================
# 39. IMMUTABILITY AND FROZEN DATACLASSES
# ============================================================================

@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float


def demonstrate_immutability() -> None:
    section("39. Immutability")

    coordinate = Coordinate(26.8467, 80.9462)
    print("Coordinate:", coordinate)

    # Frozen dataclasses prevent normal attribute reassignment.
    # coordinate.latitude = 0  # Would raise FrozenInstanceError.


# ============================================================================
# 40. HASHING AND EQUALITY
# ============================================================================

@dataclass(frozen=True)
class ProductKey:
    product_id: int
    region: str


def demonstrate_hashing() -> None:
    section("40. Hashable objects")

    key = ProductKey(100, "IN")
    prices = {key: 2500.0}

    print("Hashable key lookup:", prices[key])

    # A hashable object can be used as a dictionary key or set member.
    # Mutable objects generally should not be used as keys if their equality
    # or hash-relevant state can change.


# ============================================================================
# 41. SORTING AND KEY FUNCTIONS
# ============================================================================

def demonstrate_sorting() -> None:
    section("41. Sorting")

    users = [
        {"name": "Alice", "age": 31},
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 29},
    ]

    sorted_by_age = sorted(users, key=lambda user: user["age"])
    sorted_by_name = sorted(users, key=lambda user: user["name"])

    print("By age:", sorted_by_age)
    print("By name:", sorted_by_name)

    # sorted() returns a new list.
    # list.sort() modifies the existing list and returns None.


# ============================================================================
# 42. ZIP, ENUMERATE, ANY, ALL
# ============================================================================

def demonstrate_builtin_iteration_helpers() -> None:
    section("42. Useful iteration helpers")

    names = ["Alice", "Bob", "Charlie"]
    roles = ["admin", "editor", "viewer"]

    for index, name in enumerate(names, start=1):
        print(index, name)

    for name, role in zip(names, roles):
        print(name, "=>", role)

    print("Any admin:", any(role == "admin" for role in roles))
    print("All strings:", all(isinstance(name, str) for name in names))


# ============================================================================
# 43. PATTERN: PAGINATION GENERATOR
# ============================================================================

def paginate(
    records: Sequence[T],
    page_size: int,
) -> Iterator[list[T]]:
    """Yield pages lazily."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    for start in range(0, len(records), page_size):
        yield list(records[start:start + page_size])


def demonstrate_pagination() -> None:
    section("43. Pagination with generators")

    records = list(range(1, 11))

    for page_number, page in enumerate(paginate(records, 3), start=1):
        print(f"Page {page_number}:", page)


# ============================================================================
# 44. PATTERN: RATE LIMITER
# ============================================================================

class SimpleRateLimiter:
    """Small in-memory fixed-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client_id: str) -> bool:
        now = time.monotonic()
        timestamps = self._requests[client_id]

        cutoff = now - self.window_seconds

        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        return True


def demonstrate_rate_limiter() -> None:
    section("44. Simple backend rate limiter")

    limiter = SimpleRateLimiter(max_requests=3, window_seconds=60)

    for attempt in range(5):
        print("Attempt", attempt + 1, "allowed:", limiter.allow("client-1"))

    # Production rate limiting normally requires a shared store when multiple
    # application instances are running. This example is intentionally local.


# ============================================================================
# 45. CONTEXT MANAGERS
# ============================================================================

class RequestContext:
    """Custom context manager for resource-like lifecycle handling."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id

    def __enter__(self) -> "RequestContext":
        print("Starting request:", self.request_id)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: Any,
    ) -> bool:
        print("Finishing request:", self.request_id)

        if exception_type is not None:
            print("Exception:", exception_value)

        # Returning False means exceptions are not suppressed.
        return False


def demonstrate_context_manager() -> None:
    section("45. Context managers")

    with RequestContext("REQ-001"):
        print("Handling request")


# ============================================================================
# 46. CONTEXT MANAGER FOR TIMING
# ============================================================================

class Timer:
    """Context manager for measuring a block."""

    def __enter__(self) -> "Timer":
        self.started = perf_counter()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: Any,
    ) -> bool:
        self.elapsed = perf_counter() - self.started
        print(f"Elapsed: {self.elapsed:.6f} seconds")
        return False


def demonstrate_timer_context_manager() -> None:
    section("46. Timing with a context manager")

    with Timer():
        sum(range(500_000))


# ============================================================================
# 47. DESCRIPTORS
# ============================================================================

class PositiveNumber:
    """Descriptor enforcing a positive numeric value."""

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self.private_name = f"_{name}"

    def __get__(
        self,
        instance: Any,
        owner: type[Any] | None = None,
    ) -> float | "PositiveNumber":
        if instance is None:
            return self
        return getattr(instance, self.private_name)

    def __set__(self, instance: Any, value: float) -> None:
        if value <= 0:
            raise ValueError("value must be positive")
        setattr(instance, self.private_name, float(value))


class Invoice:
    amount = PositiveNumber()

    def __init__(self, amount: float) -> None:
        self.amount = amount


def demonstrate_descriptors() -> None:
    section("47. Descriptors")

    invoice = Invoice(1000)
    print("Invoice amount:", invoice.amount)

    try:
        invoice.amount = -1
    except ValueError as error:
        print("Descriptor validation:", error)

    # Properties are simpler for many application-level use cases.
    # Descriptors become useful when behavior needs to be reused across
    # multiple attributes or classes.


# ============================================================================
# 48. METAPROGRAMMING WITH __init_subclass__
# ============================================================================

class PluginBase:
    """Automatically records subclasses."""

    registry: ClassVar[dict[str, type["PluginBase"]]] = {}

    def __init_subclass__(cls, *, plugin_name: str, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        PluginBase.registry[plugin_name] = cls


class JsonPlugin(PluginBase, plugin_name="json"):
    pass


class CsvPlugin(PluginBase, plugin_name="csv"):
    pass


def demonstrate_class_registration() -> None:
    section("48. Automatic class registration")

    print("Plugin registry:", PluginBase.registry)


# ============================================================================
# 49. PERFORMANCE: LIST VERSUS GENERATOR
# ============================================================================

def demonstrate_memory_and_performance() -> None:
    section("49. Performance and memory trade-offs")

    number_count = 100_000

    started = perf_counter()
    list_result = [number * number for number in range(number_count)]
    list_elapsed = perf_counter() - started

    started = perf_counter()
    generator_result = (number * number for number in range(number_count))
    generator_first_values = list(islice(generator_result, 5))
    generator_elapsed = perf_counter() - started

    print(f"List creation time: {list_elapsed:.6f} seconds")
    print(f"Generator setup + first values: {generator_elapsed:.6f} seconds")
    print("Generator first values:", generator_first_values)
    print("List holds all results; generator computes values lazily.")

    # This illustrates a trade-off rather than a universal winner.
    # Lists are appropriate when repeated access or complete materialization
    # is required. Generators are appropriate for streaming and large data.


# ============================================================================
# 50. DATA STRUCTURE COMPLEXITY
# ============================================================================

def demonstrate_complexity() -> None:
    section("50. Data structure complexity")

    print(
        "Typical average complexities:",
        "\n  list indexed access: O(1)",
        "\n  list membership: O(n)",
        "\n  dict lookup: O(1)",
        "\n  set membership: O(1)",
        "\n  deque append/popleft: O(1)",
        "\n  sorting: O(n log n)",
    )

    # Complexity is an abstraction. Actual performance also depends on
    # implementation details, memory locality, input size, and workload.


# ============================================================================
# 51. SECURITY: SAFE INPUT HANDLING
# ============================================================================

def demonstrate_safe_input_handling() -> None:
    section("51. Security-conscious Python")

    user_input = "101"

    # Prefer explicit parsing and validation.
    parsed_id = parse_id(user_input)
    print("Validated ID:", parsed_id)

    # Never use eval() to interpret untrusted input.
    #
    # unsafe = eval(user_input)
    #
    # eval() can execute arbitrary Python expressions and is inappropriate
    # for untrusted HTTP, JSON, form, or database-derived input.

    # Also avoid constructing SQL using string concatenation. Database
    # libraries should use parameterized queries.


# ============================================================================
# 52. BACKEND DATA VALIDATION
# ============================================================================

@dataclass
class RegistrationRequest:
    username: str
    age: int
    email: str

    def validate(self) -> None:
        if not self.username.strip():
            raise ValidationError("username is required")

        if not 13 <= self.age <= 120:
            raise ValidationError("age must be between 13 and 120")

        if "@" not in self.email:
            raise ValidationError("email must contain @")


def demonstrate_validation() -> None:
    section("52. Backend-style validation")

    request = RegistrationRequest(
        username="atul",
        age=30,
        email="atul@example.com",
    )

    request.validate()
    print("Registration request is valid.")

    invalid_request = RegistrationRequest(
        username="",
        age=5,
        email="invalid",
    )

    try:
        invalid_request.validate()
    except ValidationError as error:
        print("Invalid request:", error)


# ============================================================================
# 53. SERIALIZATION-STYLE TRANSFORMATION
# ============================================================================

def customer_to_dict(customer: Customer) -> dict[str, Any]:
    return {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "email": customer.email,
    }


def demonstrate_serialization() -> None:
    section("53. Serialization-style transformation")

    customer = Customer(
        customer_id=1,
        name="Atul",
        email="atul@example.com",
    )

    payload = customer_to_dict(customer)
    print("API-style payload:", payload)


# ============================================================================
# 54. DEPENDENCY INJECTION
# ============================================================================

class NotificationSender(Protocol):
    def send(self, recipient: str, message: str) -> None:
        ...


class ConsoleNotificationSender:
    def send(self, recipient: str, message: str) -> None:
        print(f"Notification to {recipient}: {message}")


class MemoryNotificationSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, recipient: str, message: str) -> None:
        self.sent.append((recipient, message))


class NotificationService:
    def __init__(self, sender: NotificationSender) -> None:
        self.sender = sender

    def notify_user(self, email: str, message: str) -> None:
        self.sender.send(email, message)


def demonstrate_dependency_injection() -> None:
    section("54. Dependency injection")

    production_like_sender = ConsoleNotificationSender()
    service = NotificationService(production_like_sender)

    service.notify_user(
        "atul@example.com",
        "Your account was updated.",
    )

    test_sender = MemoryNotificationSender()
    test_service = NotificationService(test_sender)

    test_service.notify_user(
        "test@example.com",
        "Test notification.",
    )

    print("Captured test notification:", test_sender.sent)


# ============================================================================
# 55. UNIT TESTING WITH STANDARD LIBRARY
# ============================================================================

def test_calculate_total() -> None:
    assert calculate_total(100, 2, 0.10) == 220.0


def test_factorial() -> None:
    assert factorial_recursive(5) == 120


def test_repository() -> None:
    repository = CustomerRepository()
    customer = Customer(1, "Test", "test@example.com")

    repository.save(customer)

    assert repository.get(1) == customer


def demonstrate_basic_testing() -> None:
    section("55. Basic executable tests")

    tests = [
        test_calculate_total,
        test_factorial,
        test_repository,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            passed += 1
            print(f"PASS: {test.__name__}")
        except AssertionError:
            print(f"FAIL: {test.__name__}")

    print(f"Passed {passed}/{len(tests)} tests.")

    # In a real project, unittest or pytest-style test organization provides
    # better discovery, fixtures, reporting, and isolation.


# ============================================================================
# 56. COMMON BACKEND PITFALL: MUTABLE DEFAULT ARGUMENTS
# ============================================================================

def unsafe_example_explained() -> None:
    section("56. Mutable default argument pitfall")

    # Do NOT write:
    #
    # def add_tag(tag: str, tags: list[str] = []) -> list[str]:
    #     tags.append(tag)
    #     return tags
    #
    # The same default list is reused between calls.

    def safe_add_tag(
        tag: str,
        tags: list[str] | None = None,
    ) -> list[str]:
        if tags is None:
            tags = []

        tags.append(tag)
        return tags

    print(safe_add_tag("api"))
    print(safe_add_tag("database"))


# ============================================================================
# 57. COMMON BACKEND PITFALL: LATE BINDING CLOSURES
# ============================================================================

def demonstrate_closure_late_binding() -> None:
    section("57. Closure late binding")

    functions_bad: list[Callable[[], int]] = []

    for number in range(3):
        functions_bad.append(lambda: number)

    print("Late-bound results:", [function() for function in functions_bad])

    # Default arguments can capture the current value.
    functions_good: list[Callable[[], int]] = []

    for number in range(3):
        functions_good.append(lambda number=number: number)

    print("Captured results:", [function() for function in functions_good])


# ============================================================================
# 58. COMMON BACKEND PITFALL: SHALLOW VERSUS DEEP COPY
# ============================================================================

def demonstrate_copy_behavior() -> None:
    section("58. Shallow versus deep copying")

    import copy

    original = {"settings": {"theme": "dark"}}
    shallow = copy.copy(original)
    deep = copy.deepcopy(original)

    shallow["settings"]["theme"] = "light"

    print("Original after shallow nested modification:", original)

    deep["settings"]["theme"] = "blue"

    print("Original after deep nested modification:", original)
    print("Deep copy:", deep)


# ============================================================================
# 59. NONE, FALSE, ZERO, EMPTY STRING
# ============================================================================

def demonstrate_none_and_truthiness() -> None:
    section("59. None and truthiness distinctions")

    values = {
        "none": None,
        "false": False,
        "zero": 0,
        "empty_string": "",
        "empty_list": [],
        "text": "0",
    }

    for name, value in values.items():
        print(name, repr(value), "truthy:", bool(value))

    # if value is None is preferable when specifically testing absence.
    # if not value also matches legitimate empty/zero/false values.


# ============================================================================
# 60. BACKEND-STYLE RESPONSE OBJECT
# ============================================================================

@dataclass
class ApiResponse(Generic[T]):
    status_code: int
    data: T | None = None
    error: str | None = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


def demonstrate_generic_api_response() -> None:
    section("60. Generic API response model")

    success = ApiResponse(
        status_code=200,
        data={"user_id": 101, "name": "Atul"},
    )

    failure = ApiResponse[dict[str, Any]](
        status_code=404,
        error="User not found",
    )

    print("Success:", success)
    print("Success OK:", success.ok)
    print("Failure:", failure)
    print("Failure OK:", failure.ok)


# ============================================================================
# 61. CACHING TRADE-OFF
# ============================================================================

class ProductService:
    """Example showing explicit cache state."""

    def __init__(self) -> None:
        self._database: dict[int, Product] = {}
        self._cache: dict[int, Product] = {}

    def save(self, product: Product) -> None:
        self._database[product.product_id] = product
        self._cache.pop(product.product_id, None)

    def get(self, product_id: int) -> Product | None:
        if product_id in self._cache:
            return self._cache[product_id]

        product = self._database.get(product_id)

        if product is not None:
            self._cache[product_id] = product

        return product


def demonstrate_cache_strategy() -> None:
    section("61. Application cache pattern")

    service = ProductService()
    product = Product(1, "Mouse", 1000)

    service.save(product)

    print("First read:", service.get(1))
    print("Second read:", service.get(1))

    # Caches reduce repeated expensive operations but introduce:
    # - stale data concerns
    # - invalidation complexity
    # - memory consumption
    # - consistency trade-offs


# ============================================================================
# 62. THREAD-SAFETY CONSIDERATIONS
# ============================================================================

def demonstrate_thread_safety_concept() -> None:
    section("62. Thread-safety considerations")

    print(
        "Shared mutable state requires synchronization when concurrent "
        "execution can modify it."
    )

    # This example does not start threads because the purpose is to show the
    # design concern. Python's GIL does not make arbitrary application logic
    # automatically thread-safe.
    #
    # Common tools include:
    # - threading.Lock
    # - queue.Queue
    # - immutable state
    # - external transactional stores


# ============================================================================
# 63. ASYNC CONCEPTUAL EXAMPLE
# ============================================================================

import asyncio


async def simulated_io_operation(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"{name} completed"


async def run_concurrent_io() -> list[str]:
    results = await asyncio.gather(
        simulated_io_operation("database", 0.05),
        simulated_io_operation("external API", 0.05),
        simulated_io_operation("cache", 0.05),
    )
    return list(results)


def demonstrate_async_concept() -> None:
    section("63. Async-compatible backend design")

    results = asyncio.run(run_concurrent_io())

    for result in results:
        print(result)

    # Async I/O is useful when tasks spend substantial time waiting on I/O.
    # CPU-heavy work generally requires a different concurrency strategy.


# ============================================================================
# 64. ITERABLE TYPE DESIGN
# ============================================================================

class UserCollection:
    """Custom collection that exposes iteration."""

    def __init__(self, users: Iterable[User]) -> None:
        self._users = list(users)

    def __iter__(self) -> Iterator[User]:
        return iter(self._users)

    def __len__(self) -> int:
        return len(self._users)

    def __contains__(self, user_id: object) -> bool:
        return any(
            isinstance(user_id, int) and user.user_id == user_id
            for user in self._users
        )


def demonstrate_custom_collection_protocols() -> None:
    section("64. Custom collection protocols")

    collection = UserCollection(
        [
            User(1, "Alice", "alice@example.com"),
            User(2, "Bob", "bob@example.com"),
        ]
    )

    print("Length:", len(collection))
    print("Contains user 2:", 2 in collection)

    for user in collection:
        print(user)


# ============================================================================
# 65. BACKEND PIPELINE WITH TYPING
# ============================================================================

Record: TypeAlias = dict[str, Any]


def normalize_records(records: Iterable[Record]) -> Iterator[Record]:
    for record in records:
        normalized = dict(record)
        normalized["name"] = str(normalized.get("name", "")).strip()
        yield normalized


def filter_active_records(records: Iterable[Record]) -> Iterator[Record]:
    for record in records:
        if record.get("active") is True:
            yield record


def project_names(records: Iterable[Record]) -> Iterator[str]:
    for record in records:
        yield str(record["name"])


def demonstrate_typed_pipeline() -> None:
    section("65. Typed data processing pipeline")

    records = [
        {"name": " Alice ", "active": True},
        {"name": " Bob ", "active": False},
        {"name": " Charlie ", "active": True},
    ]

    pipeline = project_names(
        filter_active_records(
            normalize_records(records)
        )
    )

    print("Active names:", list(pipeline))


# ============================================================================
# 66. DECORATOR STACKING
# ============================================================================

def uppercase_result(function: Callable[..., str]) -> Callable[..., str]:
    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        return function(*args, **kwargs).upper()

    return wrapper


@log_call
@uppercase_result
def service_message(name: str) -> str:
    return f"hello {name}"


def demonstrate_decorator_stacking() -> None:
    section("66. Stacking decorators")

    print(service_message("Atul"))

    # Decorators are applied from the bottom upward at definition time.
    # The call then passes through the resulting wrapper layers.


# ============================================================================
# 67. DECORATOR AND EXCEPTION SAFETY
# ============================================================================

def safe_log(function: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except Exception as error:
            print(
                f"ERROR in {function.__name__}: "
                f"{type(error).__name__}: {error}"
            )
            raise

    return wrapper


@safe_log
def risky_division(a: float, b: float) -> float:
    return a / b


def demonstrate_exception_logging_decorator() -> None:
    section("67. Exception-safe decorator")

    try:
        print(risky_division(10, 0))
    except ZeroDivisionError:
        print("Division failed as expected.")


# ============================================================================
# 68. PERFORMANCE OF DATA LOOKUPS
# ============================================================================

def demonstrate_lookup_design() -> None:
    section("68. Choosing data structures for lookup workloads")

    users = [
        {"id": number, "name": f"user-{number}"}
        for number in range(100_000)
    ]

    users_by_id = {user["id"]: user for user in users}

    target_id = 99_999

    started = perf_counter()
    list_match = next(
        (user for user in users if user["id"] == target_id),
        None,
    )
    list_elapsed = perf_counter() - started

    started = perf_counter()
    dict_match = users_by_id.get(target_id)
    dict_elapsed = perf_counter() - started

    print("List result:", list_match)
    print("Dictionary result:", dict_match)
    print(f"List search time: {list_elapsed:.8f} seconds")
    print(f"Dictionary lookup time: {dict_elapsed:.8f} seconds")

    # The exact timings vary by machine. The structural difference matters:
    # repeated list searches are O(n), while dictionary lookup is typically O(1).


# ============================================================================
# 69. DATA STRUCTURE SELECTION
# ============================================================================

def demonstrate_structure_selection() -> None:
    section("69. Practical data structure selection")

    examples = {
        "list": "ordered collection with indexed access",
        "tuple": "fixed immutable sequence",
        "dict": "key-value lookup",
        "set": "unique values and fast membership",
        "deque": "efficient queue or double-ended operations",
        "Counter": "frequency counting",
        "defaultdict": "grouping and default values",
    }

    for structure, purpose in examples.items():
        print(f"{structure:12} -> {purpose}")


# ============================================================================
# 70. BACKEND DESIGN: SEPARATION OF CONCERNS
# ============================================================================

class UserRepository:
    def __init__(self) -> None:
        self._users: dict[int, User] = {}

    def add(self, user: User) -> User:
        self._users[user.user_id] = user
        return user

    def find(self, user_id: int) -> User | None:
        return self._users.get(user_id)


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register(self, user: User) -> User:
        if self.repository.find(user.user_id):
            raise ValidationError("user already exists")

        if "@" not in user.email:
            raise ValidationError("invalid email")

        return self.repository.add(user)


def demonstrate_separation_of_concerns() -> None:
    section("70. Separation of concerns")

    repository = UserRepository()
    service = UserService(repository)

    user = service.register(
        User(
            101,
            "Atul",
            "atul@example.com",
        )
    )

    print("Registered:", user)

    # Repository concerns:
    #   storing and retrieving data.
    #
    # Service concerns:
    #   business rules and orchestration.
    #
    # An HTTP controller or route layer would normally translate HTTP input
    # into service calls and service results into HTTP responses.


# ============================================================================
# 71. PRODUCTION CONSIDERATIONS
# ============================================================================

def demonstrate_production_considerations() -> None:
    section("71. Production considerations")

    considerations = [
        "Validate all untrusted external input.",
        "Use precise exception handling.",
        "Do not expose internal exception details to clients.",
        "Use parameterized database queries.",
        "Keep secrets outside source code.",
        "Use structured logging for production diagnostics.",
        "Measure performance before optimizing.",
        "Choose data structures based on access patterns.",
        "Use generators for appropriate streaming workloads.",
        "Use type hints consistently in application boundaries.",
        "Separate transport, business, and persistence concerns.",
        "Design caches with explicit invalidation rules.",
        "Avoid unnecessary global mutable state.",
        "Test business rules independently.",
        "Consider concurrency and process boundaries.",
    ]

    for item in considerations:
        print("-", item)


# ============================================================================
# 72. INTEGRATED BACKEND-STYLE EXAMPLE
# ============================================================================

@dataclass(frozen=True)
class OrderItem:
    product_id: int
    quantity: int
    unit_price: float

    def total(self) -> float:
        if self.quantity <= 0:
            raise ValidationError("quantity must be positive")

        if self.unit_price < 0:
            raise ValidationError("unit price cannot be negative")

        return self.quantity * self.unit_price


@dataclass
class Order:
    order_id: int
    customer_id: int
    items: list[OrderItem]
    status: Literal["pending", "confirmed", "cancelled"] = "pending"

    def total(self) -> float:
        return sum(item.total() for item in self.items)

    def confirm(self) -> None:
        if not self.items:
            raise ValidationError("cannot confirm an empty order")

        if self.status != "pending":
            raise ValidationError("only pending orders can be confirmed")

        self.status = "confirmed"


class OrderRepository:
    def __init__(self) -> None:
        self._orders: dict[int, Order] = {}

    def save(self, order: Order) -> Order:
        self._orders[order.order_id] = order
        return order

    def get(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)


def audit_order(function: Callable[..., Order]) -> Callable[..., Order]:
    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Order:
        print("AUDIT: creating order")
        result = function(*args, **kwargs)
        print(
            f"AUDIT: order={result.order_id}, "
            f"total={result.total():.2f}"
        )
        return result

    return wrapper


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    @audit_order
    def create_order(
        self,
        order_id: int,
        customer_id: int,
        items: Iterable[OrderItem],
    ) -> Order:
        materialized_items = list(items)

        if not materialized_items:
            raise ValidationError("order must contain items")

        order = Order(
            order_id=order_id,
            customer_id=customer_id,
            items=materialized_items,
        )

        return self.repository.save(order)

    def confirm_order(self, order_id: int) -> Order:
        order = self.repository.get(order_id)

        if order is None:
            raise NotFoundError(f"Order {order_id} not found")

        order.confirm()
        return order


def demonstrate_integrated_backend_example() -> None:
    section("72. Integrated backend-style example")

    repository = OrderRepository()
    service = OrderService(repository)

    items = (
        OrderItem(product_id=1, quantity=2, unit_price=500),
        OrderItem(product_id=2, quantity=1, unit_price=1500),
    )

    order = service.create_order(
        order_id=9001,
        customer_id=101,
        items=items,
    )

    print("Order:", order)
    print("Order total:", order.total())

    confirmed_order = service.confirm_order(9001)
    print("Confirmed order status:", confirmed_order.status)


# ============================================================================
# 73. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    section("73. Important edge cases")

    cases = [
        ("empty list", []),
        ("zero", 0),
        ("negative", -10),
        ("empty string", ""),
        ("None", None),
    ]

    for label, value in cases:
        print(label, "=>", repr(value), "truthy:", bool(value))

    try:
        calculate_total(-10, 1)
    except ValueError as error:
        print("Negative price rejected:", error)

    try:
        paginate([1, 2, 3], 0)
    except ValueError as error:
        print("Invalid page size rejected:", error)

    try:
        average([])
    except ValueError as error:
        print("Empty average rejected:", error)


# ============================================================================
# 74. INTEGRATED STUDY EXERCISE
# ============================================================================

@dataclass(frozen=True)
class InventoryItem:
    sku: str
    name: str
    quantity: int
    price: float


class Inventory:
    """Small typed inventory service using a dictionary for O(1)-average lookup."""

    def __init__(self) -> None:
        self._items: dict[str, InventoryItem] = {}

    def add(self, item: InventoryItem) -> None:
        if item.quantity < 0:
            raise ValidationError("quantity cannot be negative")
        if item.price < 0:
            raise ValidationError("price cannot be negative")

        self._items[item.sku] = item

    def find(self, sku: str) -> InventoryItem | None:
        return self._items.get(sku)

    def low_stock(self, threshold: int) -> Iterator[InventoryItem]:
        for item in self._items.values():
            if item.quantity <= threshold:
                yield item

    def total_inventory_value(self) -> float:
        return sum(
            item.quantity * item.price
            for item in self._items.values()
        )


def demonstrate_integrated_inventory() -> None:
    section("74. Integrated inventory example")

    inventory = Inventory()

    inventory.add(InventoryItem("KB-001", "Keyboard", 4, 2500))
    inventory.add(InventoryItem("MS-001", "Mouse", 15, 1000))
    inventory.add(InventoryItem("HD-001", "Headset", 2, 3500))

    print("Keyboard:", inventory.find("KB-001"))
    print("Low-stock items:", list(inventory.low_stock(4)))
    print("Inventory value:", inventory.total_inventory_value())


# ============================================================================
# 75. FINAL SELF-CHECK
# ============================================================================

def run_self_check() -> None:
    section("75. Final self-check")

    checks: dict[str, bool] = {
        "list": isinstance([], list),
        "tuple": isinstance((), tuple),
        "dictionary": isinstance({}, dict),
        "set": isinstance(set(), set),
        "function": callable(calculate_total),
        "class": isinstance(User(1, "A", "a@example.com"), User),
        "iterator": hasattr(iter([]), "__next__"),
        "generator": hasattr(number_generator(1, 2), "__next__"),
        "decorator": callable(multiply),
        "typing": True,
    }

    for name, passed in checks.items():
        print(f"{name:12}: {'PASS' if passed else 'FAIL'}")


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main() -> None:
    """
    Execute all educational demonstrations in a controlled order.

    The script intentionally keeps demonstrations inside functions so the
    concepts are reusable and so importing the module does not execute them.
    """

    demonstrate_basic_types()
    demonstrate_lists()
    demonstrate_tuples()
    demonstrate_dictionaries()
    demonstrate_sets()
    demonstrate_stack_and_queue()
    demonstrate_collections()

    demonstrate_functions()
    demonstrate_functional_features()
    demonstrate_scope_and_closure()
    demonstrate_recursion()

    demonstrate_classes()
    demonstrate_encapsulation()
    demonstrate_inheritance_and_polymorphism()
    demonstrate_dataclasses()
    demonstrate_dunder_methods()
    demonstrate_protocols()

    demonstrate_iterables_and_iterators()
    demonstrate_custom_iterator()
    demonstrate_generators()
    demonstrate_generator_pipeline()
    demonstrate_advanced_generator_protocol()

    demonstrate_decorators()
    demonstrate_parameterized_decorator()
    demonstrate_authorization_decorator()
    demonstrate_timing_decorator()
    demonstrate_caching()

    demonstrate_type_hints()
    demonstrate_optional_values()
    demonstrate_structured_typing()
    demonstrate_generics()
    demonstrate_overload()
    demonstrate_runtime_validation()
    demonstrate_typed_collection()

    demonstrate_error_handling()
    demonstrate_exception_chaining()
    demonstrate_file_iteration()

    demonstrate_backend_layers()
    demonstrate_immutability()
    demonstrate_hashing()
    demonstrate_sorting()
    demonstrate_builtin_iteration_helpers()
    demonstrate_pagination()
    demonstrate_rate_limiter()

    demonstrate_context_manager()
    demonstrate_timer_context_manager()
    demonstrate_descriptors()
    demonstrate_class_registration()

    demonstrate_memory_and_performance()
    demonstrate_complexity()
    demonstrate_safe_input_handling()
    demonstrate_validation()
    demonstrate_serialization()
    demonstrate_dependency_injection()
    demonstrate_basic_testing()

    unsafe_example_explained()
    demonstrate_closure_late_binding()
    demonstrate_copy_behavior()
    demonstrate_none_and_truthiness()
    demonstrate_generic_api_response()
    demonstrate_cache_strategy()
    demonstrate_thread_safety_concept()
    demonstrate_async_concept()

    demonstrate_custom_collection_protocols()
    demonstrate_typed_pipeline()
    demonstrate_decorator_stacking()
    demonstrate_exception_logging_decorator()
    demonstrate_lookup_design()
    demonstrate_structure_selection()
    demonstrate_separation_of_concerns()
    demonstrate_production_considerations()

    demonstrate_integrated_backend_example()
    demonstrate_edge_cases()
    demonstrate_integrated_inventory()
    run_self_check()


if __name__ == "__main__":
    main()
