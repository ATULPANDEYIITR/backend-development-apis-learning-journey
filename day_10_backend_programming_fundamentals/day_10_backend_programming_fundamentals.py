"""
Backend Programming Fundamentals
=================================

A self-contained study script covering:

1. Variables and data types
2. Operators and expressions
3. Control flow
4. Functions
5. Scope and namespaces
6. Mutable and immutable objects
7. Modules
8. Packages
9. Imports and import mechanics
10. Exceptions and error handling
11. File handling
12. Paths and directories
13. JSON, CSV, and text files
14. Virtual environments and dependency concepts
15. Configuration management
16. Logging
17. Testing
18. Type hints and dataclasses
19. Iterators and generators
20. Decorators
21. Context managers
22. Object-oriented backend design
23. Validation
24. Repository/service patterns
25. Transaction-like file operations
26. Security considerations
27. Performance considerations
28. Production-oriented practices
29. An integrated backend-style mini application

The examples use only the Python standard library.
"""

from __future__ import annotations

import csv
import functools
import json
import logging
import math
import os
import re
import statistics
import sys
import tempfile
import time
import unittest
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator, Iterable, Iterator, Mapping, Sequence


# ============================================================================
# 1. VARIABLES
# ============================================================================

def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


section("1. Variables and basic values")

# A variable is a name bound to an object.
name = "Atul"
age = 30
height_m = 1.75
is_student = True
nothing = None

print(name, age, height_m, is_student, nothing)

# Python determines the type of the object at runtime.
print(type(name).__name__)
print(type(age).__name__)
print(type(height_m).__name__)
print(type(is_student).__name__)
print(type(nothing).__name__)

# Variables can be rebound to objects of different types.
value = 10
print(value)
value = "ten"
print(value)

# Multiple assignment.
first_name, last_name = "Atul", "Pandey"
print(first_name, last_name)

# Unpacking.
coordinates = (10, 20, 30)
x, y, z = coordinates
print(x, y, z)

# Extended unpacking.
head, *middle, tail = [1, 2, 3, 4, 5]
print(head, middle, tail)

# Constants are conventions rather than enforced language-level constants.
TAX_RATE = 0.18
MAX_RETRIES = 3
APPLICATION_NAME = "Backend Fundamentals"

print(TAX_RATE, MAX_RETRIES, APPLICATION_NAME)


# ============================================================================
# 2. CORE DATA TYPES
# ============================================================================

section("2. Core data types")

integer_value = 42
float_value = 3.14159
complex_value = 2 + 3j
boolean_value = True
string_value = "Backend Programming"
none_value = None

print(integer_value, float_value, complex_value)
print(boolean_value, string_value, none_value)

# Lists are ordered and mutable.
numbers = [10, 20, 30]
numbers.append(40)
numbers[0] = 99
print("List:", numbers)

# Tuples are ordered and immutable.
point = (10, 20)
print("Tuple:", point)

# Sets contain unique elements.
unique_numbers = {1, 2, 2, 3, 3}
print("Set:", unique_numbers)

# Dictionaries map keys to values.
user = {
    "id": 101,
    "name": "Atul",
    "active": True,
}
print("Dictionary:", user)

# Strings are immutable sequences.
message = "Python"
print(message[0], message[-1], message[1:4])

# Boolean values participate in logical expressions.
print(True and False)
print(True or False)
print(not True)


# ============================================================================
# 3. OPERATORS AND EXPRESSIONS
# ============================================================================

section("3. Operators and expressions")

a = 17
b = 5

print("Addition:", a + b)
print("Subtraction:", a - b)
print("Multiplication:", a * b)
print("Division:", a / b)
print("Floor division:", a // b)
print("Remainder:", a % b)
print("Power:", a ** b)

print("Equal:", a == b)
print("Not equal:", a != b)
print("Greater:", a > b)
print("Less or equal:", a <= b)

print("Logical:", a > 10 and b < 10)
print("Membership:", 5 in [1, 3, 5])
print("Identity:", None is None)

# Operator precedence matters.
result_1 = 2 + 3 * 4
result_2 = (2 + 3) * 4
print(result_1, result_2)

# Prefer parentheses when they make intent clearer.
total = (100 * 0.18) + 100
print("Total:", total)


# ============================================================================
# 4. CONTROL FLOW
# ============================================================================

section("4. Control flow")

score = 82

if score >= 90:
    grade = "A"
elif score >= 75:
    grade = "B"
elif score >= 60:
    grade = "C"
else:
    grade = "D"

print("Grade:", grade)

# for loops iterate over values.
for number in range(1, 6):
    print("Number:", number)

# while loops repeat while a condition is true.
counter = 0
while counter < 3:
    print("Counter:", counter)
    counter += 1

# break terminates the loop.
for number in range(10):
    if number == 3:
        break
    print("Break example:", number)

# continue skips the current iteration.
for number in range(5):
    if number == 2:
        continue
    print("Continue example:", number)

# Comprehensions are concise ways to construct collections.
squares = [number * number for number in range(6)]
even_squares = [number * number for number in range(10) if number % 2 == 0]
square_map = {number: number * number for number in range(5)}

print(squares)
print(even_squares)
print(square_map)


# ============================================================================
# 5. FUNCTIONS
# ============================================================================

section("5. Functions")

def greet(person: str, greeting: str = "Hello") -> str:
    """Return a greeting."""
    return f"{greeting}, {person}!"


print(greet("Atul"))
print(greet("Atul", "Good morning"))


def add(first: float, second: float) -> float:
    """Return the sum of two numbers."""
    return first + second


print("Addition:", add(10, 20))


def calculate_total(price: float, tax_rate: float = 0.18) -> float:
    """Calculate a price including tax."""
    if price < 0:
        raise ValueError("Price cannot be negative.")
    if tax_rate < 0:
        raise ValueError("Tax rate cannot be negative.")
    return price * (1 + tax_rate)


print("Total:", calculate_total(100))


# Positional-only parameters use /.
def divide(dividend: float, divisor: float, /) -> float:
    """Divide two numbers using positional-only parameters."""
    if divisor == 0:
        raise ZeroDivisionError("Divisor cannot be zero.")
    return dividend / divisor


print(divide(10, 2))


# Keyword-only parameters use *.
def create_user(name: str, *, active: bool = True) -> dict[str, Any]:
    """Create a simple user dictionary."""
    return {"name": name, "active": active}


print(create_user("Atul", active=False))


# *args collects positional arguments.
def sum_all(*numbers: float) -> float:
    return sum(numbers)


print(sum_all(1, 2, 3, 4))


# **kwargs collects keyword arguments.
def describe_user(**attributes: Any) -> dict[str, Any]:
    return attributes


print(describe_user(name="Atul", role="student"))


# Functions are first-class objects.
def apply_operation(
    first: float,
    second: float,
    operation: Callable[[float, float], float],
) -> float:
    return operation(first, second)


print(apply_operation(10, 5, add))
print(apply_operation(10, 5, lambda x, y: x * y))


# Returning multiple values uses tuple packing.
def min_max(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("At least one value is required.")
    return min(values), max(values)


minimum, maximum = min_max([5, 2, 9, 1])
print(minimum, maximum)


# ============================================================================
# 6. FUNCTION DESIGN AND MUTABILITY
# ============================================================================

section("6. Function arguments, mutability, and defaults")

# Python passes object references by assignment.
def append_item(items: list[int], item: int) -> None:
    items.append(item)


values = [1, 2]
append_item(values, 3)
print("Mutated list:", values)


# Avoid mutable default arguments.
def bad_append(item: int, items: list[int] = []) -> list[int]:
    items.append(item)
    return items


print("Mutable default demonstration:", bad_append(1))
print("Same default reused:", bad_append(2))


# Correct approach.
def safe_append(item: int, items: list[int] | None = None) -> list[int]:
    if items is None:
        items = []
    items.append(item)
    return items


print("Safe:", safe_append(1))
print("Safe:", safe_append(2))


# ============================================================================
# 7. SCOPE AND NAMESPACES
# ============================================================================

section("7. Scope and namespaces")

global_value = "global"


def demonstrate_scope() -> str:
    local_value = "local"
    return f"{global_value} + {local_value}"


print(demonstrate_scope())


def counter_factory() -> Callable[[], int]:
    count = 0

    def increment() -> int:
        nonlocal count
        count += 1
        return count

    return increment


counter = counter_factory()
print(counter())
print(counter())
print(counter())


# LEGB:
# Local -> Enclosing -> Global -> Built-in
def demonstrate_legb() -> str:
    value = "local"
    return value


value = "global"
print(demonstrate_legb())


# ============================================================================
# 8. CLASSES AND OBJECTS
# ============================================================================

section("8. Classes and objects")

class BankAccount:
    """Simple class demonstrating encapsulated state and behavior."""

    bank_name = "Example Bank"

    def __init__(self, owner: str, balance: float = 0.0) -> None:
        if not owner.strip():
            raise ValueError("Owner name cannot be empty.")
        if balance < 0:
            raise ValueError("Initial balance cannot be negative.")

        self.owner = owner
        self._balance = balance

    @property
    def balance(self) -> float:
        """Expose balance without allowing direct replacement."""
        return self._balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit must be positive.")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal must be positive.")
        if amount > self._balance:
            raise ValueError("Insufficient funds.")
        self._balance -= amount

    def __repr__(self) -> str:
        return f"BankAccount(owner={self.owner!r}, balance={self.balance:.2f})"


account = BankAccount("Atul", 1000)
account.deposit(500)
account.withdraw(250)
print(account)
print(account.balance)


# ============================================================================
# 9. DATACLASSES
# ============================================================================

section("9. Dataclasses")

@dataclass
class Product:
    """Structured application data with generated initialization methods."""

    product_id: int
    name: str
    price: float
    tags: list[str] = field(default_factory=list)

    def discounted_price(self, percentage: float) -> float:
        if not 0 <= percentage <= 100:
            raise ValueError("Discount must be between 0 and 100.")
        return self.price * (1 - percentage / 100)


product = Product(1, "Keyboard", 2500, ["hardware", "input"])
print(product)
print(product.discounted_price(10))
print(asdict(product))


# ============================================================================
# 10. MODULES
# ============================================================================

section("10. Modules")

# A module is a Python source file that provides reusable names.
#
# Typical structure:
#
# project/
#     app.py
#     calculations.py
#
# calculations.py:
#     def add(a, b):
#         return a + b
#
# app.py:
#     from calculations import add
#
# This script cannot create an external module requirement because it is
# intentionally self-contained, so the standard library is used to demonstrate
# real module imports.

print("math.pi:", math.pi)
print("statistics.mean:", statistics.mean([10, 20, 30]))
print("Current Python:", sys.version.split()[0])


# ============================================================================
# 11. IMPORT STYLES
# ============================================================================

section("11. Import styles")

import math as mathematics

print(mathematics.sqrt(81))

from pathlib import Path as FilePath

print(FilePath("."))

# Avoid wildcard imports such as:
#
# from math import *
#
# They make it difficult to know where names came from and can cause name
# collisions.


# ============================================================================
# 12. __name__ AND MODULE EXECUTION
# ============================================================================

section("12. __name__ and module execution")

def module_entry_point() -> None:
    print("This function represents the module's command-line entry point.")


if __name__ == "__main__":
    module_entry_point()

# When a file is executed directly, __name__ is "__main__".
# When imported, its __name__ normally becomes the module name.
# This prevents demonstration or command-line code from running unexpectedly
# during imports.


# ============================================================================
# 13. PACKAGES
# ============================================================================

section("13. Packages")

# A package is a directory containing Python modules organized as a unit.
#
# Example conceptual structure:
#
# backend_app/
#     __init__.py
#     users/
#         __init__.py
#         models.py
#         services.py
#     billing/
#         __init__.py
#         invoices.py
#
# Modern Python also supports namespace packages without __init__.py in
# appropriate situations. For traditional application packages, __init__.py
# remains useful for explicit package initialization and compatibility.


# ============================================================================
# 14. EXCEPTIONS
# ============================================================================

section("14. Exceptions")

def safe_division(first: float, second: float) -> float | None:
    try:
        return first / second
    except ZeroDivisionError:
        print("Cannot divide by zero.")
        return None


print(safe_division(10, 2))
print(safe_division(10, 0))


def convert_integer(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        print(f"Invalid integer: {value!r}")
        return None


print(convert_integer("123"))
print(convert_integer("abc"))


# Multiple exception types.
def parse_positive_integer(value: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Value must be an integer.") from exc

    if number <= 0:
        raise ValueError("Value must be positive.")

    return number


print(parse_positive_integer("10"))


# else runs only if no exception occurs.
# finally runs whether an exception occurred or not.
def exception_flow(value: str) -> int | None:
    try:
        number = int(value)
    except ValueError:
        print("Conversion failed.")
        return None
    else:
        print("Conversion succeeded.")
        return number
    finally:
        print("Cleanup/finalization step executed.")


print(exception_flow("42"))
print(exception_flow("bad"))


# Custom exceptions communicate domain-specific failures.
class InsufficientFundsError(Exception):
    """Raised when an account cannot cover a withdrawal."""


def withdraw_with_domain_error(balance: float, amount: float) -> float:
    if amount > balance:
        raise InsufficientFundsError(
            f"Requested {amount:.2f}, available {balance:.2f}."
        )
    return balance - amount


try:
    withdraw_with_domain_error(100, 150)
except InsufficientFundsError as exc:
    print("Domain error:", exc)


# Do not catch every exception indiscriminately.
#
# Bad:
#     try:
#         risky_operation()
#     except Exception:
#         pass
#
# Broad exception handling can hide programming defects.


# ============================================================================
# 15. ASSERTIONS
# ============================================================================

section("15. Assertions")

def percentage(value: float) -> float:
    assert 0 <= value <= 100, "Percentage must be between 0 and 100."
    return value


print(percentage(75))

# Assertions are useful for internal invariants and debugging.
# They should not replace user-input validation because Python can disable
# assertions with optimization flags.


# ============================================================================
# 16. FILE PATHS
# ============================================================================

section("16. File paths with pathlib")

current_directory = Path.cwd()
print("Current directory:", current_directory)

example_path = current_directory / "example" / "data.txt"
print("Constructed path:", example_path)

# pathlib avoids many platform-specific string manipulation problems.


# ============================================================================
# 17. TEXT FILE HANDLING
# ============================================================================

section("17. Text file handling")

with tempfile.TemporaryDirectory() as temporary_directory:
    directory = Path(temporary_directory)
    text_file = directory / "notes.txt"

    # "with" guarantees the file is closed after the block.
    text_file.write_text(
        "Backend programming\nFile handling\nPython\n",
        encoding="utf-8",
    )

    content = text_file.read_text(encoding="utf-8")
    print(content)

    lines = text_file.read_text(encoding="utf-8").splitlines()
    print("Lines:", lines)


# Explicit file modes:
#
# r  -> read
# w  -> write and replace existing content
# a  -> append
# x  -> create and fail if file exists
# b  -> binary mode
# t  -> text mode
# +  -> read and write


# ============================================================================
# 18. FILE HANDLES
# ============================================================================

section("18. File handles")

with tempfile.TemporaryDirectory() as temporary_directory:
    path = Path(temporary_directory) / "log.txt"

    with path.open("w", encoding="utf-8") as file:
        file.write("First line\n")
        file.write("Second line\n")

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            print(line.rstrip())


# ============================================================================
# 19. BINARY FILES
# ============================================================================

section("19. Binary files")

with tempfile.TemporaryDirectory() as temporary_directory:
    binary_path = Path(temporary_directory) / "data.bin"

    binary_data = bytes([0, 1, 2, 255])

    binary_path.write_bytes(binary_data)
    restored_data = binary_path.read_bytes()

    print("Binary data:", restored_data)


# ============================================================================
# 20. JSON
# ============================================================================

section("20. JSON file handling")

profile = {
    "id": 101,
    "name": "Atul",
    "skills": ["Python", "SQL"],
    "active": True,
}

json_text = json.dumps(profile, indent=2)
print(json_text)

restored_profile = json.loads(json_text)
print(restored_profile["name"])

with tempfile.TemporaryDirectory() as temporary_directory:
    json_path = Path(temporary_directory) / "profile.json"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(profile, file, indent=2)

    with json_path.open("r", encoding="utf-8") as file:
        loaded_profile = json.load(file)

    print("Loaded JSON:", loaded_profile)


# JSON supports common primitive structures, but not arbitrary Python objects.
# Dates, sets, custom classes, and other objects require explicit serialization.


# ============================================================================
# 21. CSV
# ============================================================================

section("21. CSV file handling")

with tempfile.TemporaryDirectory() as temporary_directory:
    csv_path = Path(temporary_directory) / "users.csv"

    rows = [
        {"id": 1, "name": "Atul", "role": "student"},
        {"id": 2, "name": "Riya", "role": "developer"},
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "name", "role"])
        writer.writeheader()
        writer.writerows(rows)

    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            print(row)


# ============================================================================
# 22. DIRECTORY OPERATIONS
# ============================================================================

section("22. Directory operations")

with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)

    (root / "logs").mkdir()
    (root / "data").mkdir()

    (root / "logs" / "app.log").write_text("log", encoding="utf-8")
    (root / "data" / "users.json").write_text("{}", encoding="utf-8")

    print("Directories:", [path.name for path in root.iterdir()])
    print("JSON files:", list(root.rglob("*.json")))


# ============================================================================
# 23. FILE SAFETY
# ============================================================================

section("23. File safety")

def safe_filename(filename: str) -> str:
    """
    Convert a user-supplied filename into a conservative filename.

    This prevents path separators and special traversal syntax from becoming
    part of a path. In a real application, authorization and storage policy
    must also be enforced.
    """
    filename = Path(filename).name
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename)

    if filename in {"", ".", ".."}:
        raise ValueError("Invalid filename.")

    return filename


print(safe_filename("../../private.txt"))
print(safe_filename("monthly report!.csv"))


# ============================================================================
# 24. ATOMIC FILE WRITES
# ============================================================================

section("24. Safer file updates")

def atomic_write_text(path: Path, content: str) -> None:
    """
    Write through a temporary file and replace the destination.

    This reduces the risk of leaving a partially written target if the process
    fails during the write.
    """
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    try:
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


with tempfile.TemporaryDirectory() as temporary_directory:
    target = Path(temporary_directory) / "settings.json"
    atomic_write_text(target, '{"enabled": true}')
    print(target.read_text(encoding="utf-8"))


# ============================================================================
# 25. ENVIRONMENT VARIABLES
# ============================================================================

section("25. Environment variables")

# Environment variables are useful for configuration that should vary between
# environments, such as ports and deployment-specific settings.

application_environment = os.getenv("APP_ENV", "development")
application_port = int(os.getenv("APP_PORT", "8000"))

print("Environment:", application_environment)
print("Port:", application_port)

# Never print secrets such as passwords or API keys in production logs.


# ============================================================================
# 26. CONFIGURATION
# ============================================================================

section("26. Configuration object")

@dataclass(frozen=True)
class AppConfig:
    environment: str
    port: int
    debug: bool

    @classmethod
    def from_environment(cls) -> "AppConfig":
        environment = os.getenv("APP_ENV", "development")
        port_text = os.getenv("APP_PORT", "8000")
        debug_text = os.getenv("APP_DEBUG", "false").lower()

        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("APP_PORT must be an integer.") from exc

        if not 1 <= port <= 65535:
            raise ValueError("APP_PORT must be between 1 and 65535.")

        debug = debug_text in {"1", "true", "yes", "on"}

        return cls(
            environment=environment,
            port=port,
            debug=debug,
        )


config = AppConfig.from_environment()
print(config)


# ============================================================================
# 27. VIRTUAL ENVIRONMENTS
# ============================================================================

section("27. Python environments")

# A virtual environment isolates a project's Python interpreter and installed
# dependencies from other projects.
#
# Typical command-line workflow:
#
# python -m venv .venv
#
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
#
# Windows Command Prompt:
# .venv\Scripts\activate
#
# Linux/macOS:
# source .venv/bin/activate
#
# Dependency installation:
# python -m pip install package_name
#
# Dependency export:
# python -m pip freeze > requirements.txt
#
# A project should generally pin or constrain dependencies deliberately rather
# than relying on whatever happens to be installed globally.


# ============================================================================
# 28. LOGGING
# ============================================================================

section("28. Logging")

logger = logging.getLogger("backend_fundamentals")
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    )
    logger.addHandler(console_handler)

logger.info("Application started.")
logger.warning("This is an example warning.")

# Logging levels commonly include DEBUG, INFO, WARNING, ERROR, and CRITICAL.
#
# Logging is preferable to scattered print statements in production systems
# because logging supports levels, handlers, formatting, filtering, and
# centralized collection.


# ============================================================================
# 29. ITERATORS
# ============================================================================

section("29. Iterators")

numbers_iterator = iter([10, 20, 30])

print(next(numbers_iterator))
print(next(numbers_iterator))
print(next(numbers_iterator))

try:
    print(next(numbers_iterator))
except StopIteration:
    print("Iterator is exhausted.")


# ============================================================================
# 30. GENERATORS
# ============================================================================

section("30. Generators")

def generate_numbers(limit: int) -> Generator[int, None, None]:
    """Generate numbers lazily instead of constructing the entire list."""
    for number in range(limit):
        yield number


generator = generate_numbers(5)

for number in generator:
    print(number)

# A generator can dramatically reduce memory use when processing large streams.
# It does not automatically make computation faster.


# ============================================================================
# 31. GENERATOR PIPELINES
# ============================================================================

section("31. Generator pipeline")

def read_lines(lines: Iterable[str]) -> Iterator[str]:
    for line in lines:
        yield line.strip()


def non_empty(lines: Iterable[str]) -> Iterator[str]:
    for line in lines:
        if line:
            yield line


raw_lines = [" Python ", "", " SQL ", " ", "Backend "]
clean_lines = non_empty(read_lines(raw_lines))

print(list(clean_lines))


# ============================================================================
# 32. DECORATORS
# ============================================================================

section("32. Decorators")

def log_calls(function: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a function while preserving metadata and logging its call."""

    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.info("Calling %s", function.__name__)
        result = function(*args, **kwargs)
        logger.info("Completed %s", function.__name__)
        return result

    return wrapper


@log_calls
def multiply(first: int, second: int) -> int:
    return first * second


print("Decorated result:", multiply(6, 7))


# Decorators can implement cross-cutting concerns such as logging, timing,
# caching, authorization checks, retries, or instrumentation.


# ============================================================================
# 33. PERFORMANCE MEASUREMENT
# ============================================================================

section("33. Performance measurement")

def benchmark(function: Callable[..., Any], *args: Any, **kwargs: Any) -> float:
    start = time.perf_counter()
    function(*args, **kwargs)
    return time.perf_counter() - start


def sum_loop(values: Sequence[int]) -> int:
    total = 0
    for value in values:
        total += value
    return total


def sum_builtin(values: Sequence[int]) -> int:
    return sum(values)


benchmark_data = list(range(100_000))

loop_time = benchmark(sum_loop, benchmark_data)
builtin_time = benchmark(sum_builtin, benchmark_data)

print(f"Loop time: {loop_time:.6f}s")
print(f"Built-in time: {builtin_time:.6f}s")

# Benchmarking must be performed with realistic workloads. One measurement is
# not enough for rigorous performance analysis.


# ============================================================================
# 34. CACHING
# ============================================================================

section("34. Function caching")

@functools.lru_cache(maxsize=128)
def fibonacci(number: int) -> int:
    if number < 0:
        raise ValueError("Number must be non-negative.")
    if number < 2:
        return number
    return fibonacci(number - 1) + fibonacci(number - 2)


print("Fibonacci:", fibonacci(30))
print("Cache information:", fibonacci.cache_info())


# Caching trades memory for reduced repeated computation.
# It is appropriate only when cached results remain valid for the required
# lifetime and inputs are suitable cache keys.


# ============================================================================
# 35. TYPE HINTS
# ============================================================================

section("35. Type hints")

def average(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot average an empty sequence.")
    return sum(values) / len(values)


print(average([10, 20, 30]))

# Type hints improve readability, tooling, static analysis, and API clarity.
# Python normally does not enforce annotations at runtime.


# ============================================================================
# 36. VALIDATION
# ============================================================================

section("36. Input validation")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> str:
    email = email.strip()

    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Invalid email address.")

    return email.lower()


print(validate_email("person@example.com"))

try:
    validate_email("invalid")
except ValueError as exc:
    print("Validation error:", exc)


# Validation should occur at trust boundaries. Data received from users,
# files, APIs, databases, and external systems should not automatically be
# considered valid.


# ============================================================================
# 37. SEPARATION OF RESPONSIBILITIES
# ============================================================================

section("37. Separation of responsibilities")

@dataclass
class UserRecord:
    user_id: int
    name: str
    email: str


class UserValidator:
    """Responsible for validating user input."""

    @staticmethod
    def validate(name: str, email: str) -> tuple[str, str]:
        clean_name = name.strip()

        if not clean_name:
            raise ValueError("Name cannot be empty.")

        clean_email = validate_email(email)
        return clean_name, clean_email


class UserRepository:
    """Responsible for persistence."""

    def __init__(self) -> None:
        self._users: dict[int, UserRecord] = {}

    def save(self, user: UserRecord) -> None:
        self._users[user.user_id] = user

    def get(self, user_id: int) -> UserRecord | None:
        return self._users.get(user_id)


class UserService:
    """Coordinates business rules between validation and persistence."""

    def __init__(
        self,
        repository: UserRepository,
        validator: UserValidator,
    ) -> None:
        self.repository = repository
        self.validator = validator

    def create_user(
        self,
        user_id: int,
        name: str,
        email: str,
    ) -> UserRecord:
        clean_name, clean_email = self.validator.validate(name, email)

        user = UserRecord(
            user_id=user_id,
            name=clean_name,
            email=clean_email,
        )

        self.repository.save(user)
        return user


repository = UserRepository()
validator = UserValidator()
service = UserService(repository, validator)

created_user = service.create_user(
    1,
    "  Atul Pandey ",
    "ATUL@example.com",
)

print(created_user)
print(repository.get(1))


# ============================================================================
# 38. JSON-BACKED REPOSITORY
# ============================================================================

section("38. JSON-backed persistence")

class JsonUserRepository:
    """Simple persistence example using a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, user: UserRecord) -> None:
        users = self._load()

        users[str(user.user_id)] = asdict(user)

        atomic_write_text(
            self.path,
            json.dumps(users, indent=2),
        )

    def get(self, user_id: int) -> UserRecord | None:
        users = self._load()
        raw_user = users.get(str(user_id))

        if raw_user is None:
            return None

        return UserRecord(
            user_id=int(raw_user["user_id"]),
            name=str(raw_user["name"]),
            email=str(raw_user["email"]),
        )

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        try:
            content = self.path.read_text(encoding="utf-8")
            if not content.strip():
                return {}
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Repository contains invalid JSON.") from exc

        if not isinstance(data, dict):
            raise ValueError("Repository root must be a JSON object.")

        return data


with tempfile.TemporaryDirectory() as temporary_directory:
    repository_path = Path(temporary_directory) / "users.json"
    json_repository = JsonUserRepository(repository_path)

    json_repository.save(created_user)

    print("Stored user:", json_repository.get(1))
    print("File content:")
    print(repository_path.read_text(encoding="utf-8"))


# ============================================================================
# 39. CONTEXT MANAGERS
# ============================================================================

section("39. Context managers")

class ManagedResource:
    """Demonstrates the context manager protocol."""

    def __enter__(self) -> "ManagedResource":
        print("Resource acquired.")
        return self

    def use(self) -> None:
        print("Resource is being used.")

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: Any,
    ) -> bool:
        print("Resource released.")
        return False


with ManagedResource() as resource:
    resource.use()


# Context managers are useful whenever setup and cleanup must be paired:
# files, locks, database connections, transactions, temporary resources, etc.


# ============================================================================
# 40. THREAD-SAFE-ISH IN-MEMORY COUNTER EXAMPLE
# ============================================================================

section("40. State management considerations")

class Inventory:
    """Simple inventory with explicit validation."""

    def __init__(self) -> None:
        self._stock: dict[str, int] = {}

    def add(self, product_name: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        self._stock[product_name] = self._stock.get(product_name, 0) + quantity

    def remove(self, product_name: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        available = self._stock.get(product_name, 0)

        if quantity > available:
            raise ValueError("Insufficient inventory.")

        self._stock[product_name] = available - quantity

    def quantity(self, product_name: str) -> int:
        return self._stock.get(product_name, 0)


inventory = Inventory()
inventory.add("Keyboard", 10)
inventory.remove("Keyboard", 3)
print("Keyboard stock:", inventory.quantity("Keyboard"))


# In concurrent applications, shared mutable state requires synchronization or
# a design that avoids unsafe shared mutation. This simple class does not claim
# to be thread-safe.


# ============================================================================
# 41. TESTING
# ============================================================================

section("41. Unit testing")

class TestBackendFundamentals(unittest.TestCase):
    def test_add(self) -> None:
        self.assertEqual(add(2, 3), 5)

    def test_divide(self) -> None:
        self.assertEqual(divide(10, 2), 5)

    def test_divide_by_zero(self) -> None:
        with self.assertRaises(ZeroDivisionError):
            divide(10, 0)

    def test_email_validation(self) -> None:
        self.assertEqual(
            validate_email(" USER@EXAMPLE.COM "),
            "user@example.com",
        )

    def test_invalid_email(self) -> None:
        with self.assertRaises(ValueError):
            validate_email("invalid")


# Run tests quietly so this educational script remains readable.
test_result = unittest.TextTestRunner(verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(TestBackendFundamentals)
)

print(
    f"Tests run: {test_result.testsRun}, "
    f"failures: {len(test_result.failures)}, "
    f"errors: {len(test_result.errors)}"
)


# ============================================================================
# 42. EDGE CASES
# ============================================================================

section("42. Edge cases")

def safe_average(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return statistics.mean(values)


print("Empty average:", safe_average([]))
print("Single-value average:", safe_average([42]))
print("Negative values:", safe_average([-10, -20]))
print("Mixed values:", safe_average([-10, 20]))


def safe_percentage_change(old: float, new: float) -> float:
    if old == 0:
        raise ValueError("Percentage change is undefined when the baseline is zero.")
    return ((new - old) / old) * 100


print("Percentage change:", safe_percentage_change(100, 120))

try:
    safe_percentage_change(0, 120)
except ValueError as exc:
    print("Edge-case validation:", exc)


# ============================================================================
# 43. COMMON BACKEND EXCEPTIONS
# ============================================================================

section("43. Common exception categories")

def exception_examples() -> None:
    examples = [
        ("TypeError", lambda: "5" + 10),  # type: ignore[operator]
        ("ValueError", lambda: int("not-a-number")),
        ("KeyError", lambda: {"name": "Atul"}["missing"]),
        ("IndexError", lambda: [1][5]),
        ("FileNotFoundError", lambda: Path("missing-file.txt").read_text()),
        ("ZeroDivisionError", lambda: 1 / 0),
    ]

    for name_, operation in examples:
        try:
            operation()
        except Exception as exc:
            print(name_, "->", type(exc).__name__)


exception_examples()


# ============================================================================
# 44. EXCEPTION CHAINING
# ============================================================================

section("44. Exception chaining")

def load_integer(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Cannot parse integer: {value!r}") from exc


try:
    load_integer("abc")
except ValueError as exc:
    print("Chained exception:", exc)
    print("Original cause:", exc.__cause__)


# ============================================================================
# 45. RESOURCE CLEANUP
# ============================================================================

section("45. Resource cleanup")

class TemporaryResource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True
        print("Resource closed.")


resource = TemporaryResource()

try:
    print("Using resource.")
finally:
    resource.close()

print("Closed:", resource.closed)


# Context managers are usually cleaner for reusable resource-management logic.


# ============================================================================
# 46. SERIALIZATION
# ============================================================================

section("46. Serialization")

@dataclass
class Order:
    order_id: int
    customer: str
    amount: float
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer": self.customer,
            "amount": self.amount,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Order":
        return cls(
            order_id=int(data["order_id"]),
            customer=str(data["customer"]),
            amount=float(data["amount"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
        )


order = Order(
    order_id=5001,
    customer="Atul",
    amount=1999.50,
    created_at=datetime.now(timezone.utc),
)

serialized_order = json.dumps(order.to_dict(), indent=2)
print(serialized_order)

restored_order = Order.from_dict(json.loads(serialized_order))
print(restored_order)


# ============================================================================
# 47. TIME AND DATETIME
# ============================================================================

section("47. Date and time")

now_utc = datetime.now(timezone.utc)
print("UTC:", now_utc.isoformat())

# Timezone-aware datetime values are generally preferable for backend systems
# because naive datetime values do not explicitly identify a timezone.


# ============================================================================
# 48. COMMAND-LINE ARGUMENTS
# ============================================================================

section("48. Command-line execution concepts")

# sys.argv contains command-line arguments.
print("Program arguments:", sys.argv)

# Production command-line applications commonly use argparse:
#
# import argparse
#
# parser = argparse.ArgumentParser()
# parser.add_argument("--name", required=True)
# args = parser.parse_args()
#
# print(args.name)
#
# argparse provides structured parsing, validation, help text, and errors.


# ============================================================================
# 49. PACKAGE DEPENDENCY MANAGEMENT
# ============================================================================

section("49. Dependency management concepts")

# The Python standard library is distributed with Python.
# Third-party packages are installed separately.
#
# Common project files:
#
# requirements.txt
# pyproject.toml
#
# pyproject.toml is the modern standard configuration file for many Python
# projects and can define project metadata, dependencies, build configuration,
# and tool configuration.
#
# Virtual environments isolate installed dependencies.
#
# Dependency pinning reduces unexpected changes, while controlled upgrades
# reduce security and compatibility risks.


# ============================================================================
# 50. IMPORT SIDE EFFECTS
# ============================================================================

section("50. Avoiding import side effects")

# Good module design generally keeps reusable definitions separate from actions.
#
# Preferred:
#
# def connect():
#     ...
#
# if __name__ == "__main__":
#     connect()
#
# Avoid performing expensive network calls, modifying files, or starting
# application services merely because another module imported a helper.


# ============================================================================
# 51. CIRCULAR IMPORTS
# ============================================================================

section("51. Circular imports")

# Circular import pattern:
#
# module_a imports module_b
# module_b imports module_a
#
# This can result in partially initialized modules and confusing import errors.
#
# Better designs usually move shared abstractions into a third module or change
# dependency direction.


# ============================================================================
# 52. PACKAGE ARCHITECTURE
# ============================================================================

section("52. Backend package architecture")

# A maintainable backend may separate responsibilities like this:
#
# application/
#     __init__.py
#     main.py
#     config.py
#     models.py
#     schemas.py
#     exceptions.py
#     repositories/
#         __init__.py
#         users.py
#     services/
#         __init__.py
#         users.py
#     utils/
#         __init__.py
#         validation.py
#
# The exact architecture depends on project size. Small projects should not
# introduce unnecessary layers merely to follow a pattern.


# ============================================================================
# 53. BUSINESS LOGIC AND ERROR BOUNDARIES
# ============================================================================

section("53. Business logic boundaries")

class DuplicateUserError(Exception):
    """Raised when an identifier is already registered."""


class ApplicationUserService:
    def __init__(self) -> None:
        self.users: dict[int, UserRecord] = {}

    def register(
        self,
        user_id: int,
        name: str,
        email: str,
    ) -> UserRecord:
        if user_id in self.users:
            raise DuplicateUserError(f"User {user_id} already exists.")

        clean_name, clean_email = UserValidator.validate(name, email)

        user = UserRecord(
            user_id=user_id,
            name=clean_name,
            email=clean_email,
        )

        self.users[user_id] = user
        return user


application_user_service = ApplicationUserService()

try:
    application_user_service.register(1, "Atul", "atul@example.com")
    application_user_service.register(1, "Another", "other@example.com")
except DuplicateUserError as exc:
    print("Business error:", exc)


# A backend boundary can translate internal exceptions into appropriate API
# responses, CLI errors, logs, or retry decisions.


# ============================================================================
# 54. RETRY CONCEPT
# ============================================================================

section("54. Controlled retry logic")

def retry(
    attempts: int,
    exceptions: tuple[type[BaseException], ...],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    if attempts < 1:
        raise ValueError("Attempts must be at least 1.")

    def decorator(
        function: Callable[..., Any],
    ) -> Callable[..., Any]:
        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: BaseException | None = None

            for attempt in range(attempts):
                try:
                    return function(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    logger.warning(
                        "Attempt %d/%d failed: %s",
                        attempt + 1,
                        attempts,
                        exc,
                    )

            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator


attempt_state = {"count": 0}


@retry(attempts=3, exceptions=(RuntimeError,))
def occasionally_fails() -> str:
    attempt_state["count"] += 1

    if attempt_state["count"] < 3:
        raise RuntimeError("Temporary failure.")

    return "Success"


print(occasionally_fails())


# Retry only failures that are plausibly temporary. Blind retries can worsen
# outages, duplicate operations, and overload dependencies.


# ============================================================================
# 55. IDEMPOTENCY
# ============================================================================

section("55. Idempotency")

class PaymentProcessor:
    """
    Demonstrates an in-memory idempotency-key concept.

    A real implementation should persist the key and result in durable storage.
    """

    def __init__(self) -> None:
        self._processed: dict[str, float] = {}

    def charge(self, idempotency_key: str, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Amount must be positive.")

        if idempotency_key in self._processed:
            return self._processed[idempotency_key]

        self._processed[idempotency_key] = amount
        return amount


processor = PaymentProcessor()

print(processor.charge("request-001", 100))
print(processor.charge("request-001", 100))


# Idempotency is important when clients retry requests after timeouts.


# ============================================================================
# 56. SECURITY: INPUT AND PATH VALIDATION
# ============================================================================

section("56. Security considerations")

def sanitize_log_value(value: str) -> str:
    """
    Reduce control characters before putting user-controlled data into logs.
    """
    return value.replace("\n", "\\n").replace("\r", "\\r")


user_supplied_value = "username\nFORGED LOG ENTRY"
print(sanitize_log_value(user_supplied_value))


# Important backend security principles:
#
# 1. Treat external input as untrusted.
# 2. Validate type, range, format, and business constraints.
# 3. Do not store passwords as plain text.
# 4. Do not hard-code secrets in source code.
# 5. Use least privilege for files, databases, and services.
# 6. Avoid unsafe dynamic execution such as eval() on user input.
# 7. Avoid shell command construction from untrusted strings.
# 8. Protect logs from leaking credentials and personal data.
# 9. Keep dependencies updated and controlled.
# 10. Separate development configuration from production secrets.


# ============================================================================
# 57. DANGEROUS EVAL EXPLANATION
# ============================================================================

section("57. Dynamic execution warning")

# Never treat user input as trusted Python code.
#
# Dangerous pattern:
#
# user_input = input()
# result = eval(user_input)
#
# eval() can execute Python expressions and should not be used to implement
# arbitrary user-controlled calculation or configuration.
#
# Prefer an explicit parser or a restricted data format such as JSON.


# ============================================================================
# 58. FILE RESOURCE LIMITS
# ============================================================================

section("58. Large-file processing")

def count_non_empty_lines(path: Path) -> int:
    """
    Process a file incrementally rather than loading it completely into memory.
    """
    count = 0

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                count += 1

    return count


with tempfile.TemporaryDirectory() as temporary_directory:
    large_file = Path(temporary_directory) / "records.txt"
    large_file.write_text(
        "record\n\nrecord\nrecord\n",
        encoding="utf-8",
    )

    print("Non-empty lines:", count_non_empty_lines(large_file))


# For large data:
# - stream when practical
# - avoid unnecessary copies
# - process records incrementally
# - choose appropriate data structures
# - measure before optimizing


# ============================================================================
# 59. MEMORY COMPLEXITY
# ============================================================================

section("59. Memory considerations")

def list_squares(limit: int) -> list[int]:
    return [number * number for number in range(limit)]


def generator_squares(limit: int) -> Iterator[int]:
    for number in range(limit):
        yield number * number


small_list = list_squares(10)
small_generator = generator_squares(10)

print("List:", small_list)
print("Generator:", list(small_generator))

# The list stores all generated values.
# The generator produces values lazily.
#
# This is a space trade-off, not an absolute performance rule.


# ============================================================================
# 60. BIG-O EXAMPLES
# ============================================================================

section("60. Basic algorithmic complexity")

def linear_search(values: Sequence[int], target: int) -> int | None:
    for index, value in enumerate(values):
        if value == target:
            return index
    return None


def constant_lookup(values: Mapping[str, int], key: str) -> int | None:
    return values.get(key)


data = list(range(100))
mapping = {str(number): number for number in data}

print(linear_search(data, 75))
print(constant_lookup(mapping, "75"))

# Linear search is O(n) in the typical case.
# Dictionary lookup is O(1) average-case under normal hashing assumptions.
#
# Real performance also depends on constants, memory access, workload, and
# implementation details.


# ============================================================================
# 61. DATA STRUCTURE CHOICE
# ============================================================================

section("61. Choosing data structures")

items = [1, 2, 3]
unique_items = {1, 2, 3}
key_value_items = {"id": 101}

print("List preserves order and supports indexing:", items)
print("Set supports uniqueness:", unique_items)
print("Dictionary maps keys to values:", key_value_items)


# ============================================================================
# 62. FILE LOCKING CONCEPT
# ============================================================================

section("62. Concurrent file access")

# Multiple processes writing the same file can corrupt data or overwrite each
# other's changes.
#
# Production systems requiring concurrent durable writes should generally use
# a database or an explicit locking/coordination mechanism rather than assuming
# that a simple file write is transactional across processes.


# ============================================================================
# 63. DATABASE BOUNDARY CONCEPT
# ============================================================================

section("63. Database boundary")

# A backend frequently separates:
#
# API/request layer
#       |
#       v
# validation
#       |
#       v
# service/business logic
#       |
#       v
# repository/data-access layer
#       |
#       v
# database
#
# The repository pattern can isolate persistence details from business logic.
# The best architecture depends on project complexity and requirements.


# ============================================================================
# 64. ENVIRONMENT-SPECIFIC BEHAVIOR
# ============================================================================

section("64. Development versus production")

def is_production(environment: str) -> bool:
    return environment.lower() == "production"


print("Production:", is_production(config.environment))

# Production systems commonly differ in:
# - debug settings
# - logging level
# - secret sources
# - database configuration
# - external service endpoints
# - resource limits
# - security controls
#
# Configuration should be explicit and validated at startup.


# ============================================================================
# 65. STARTUP VALIDATION
# ============================================================================

section("65. Configuration validation")

def validate_config(configuration: AppConfig) -> None:
    if configuration.environment not in {
        "development",
        "testing",
        "staging",
        "production",
    }:
        raise ValueError("Unsupported environment.")

    if configuration.port < 1 or configuration.port > 65535:
        raise ValueError("Invalid port.")


validate_config(config)
print("Configuration is valid.")


# ============================================================================
# 66. STRUCTURED APPLICATION ERROR
# ============================================================================

section("66. Structured application errors")

@dataclass
class ApplicationError(Exception):
    code: str
    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)


try:
    raise ApplicationError(
        code="USER_NOT_FOUND",
        message="The requested user does not exist.",
    )
except ApplicationError as exc:
    print("Error code:", exc.code)
    print("Error message:", exc.message)


# Structured errors allow an API or application boundary to distinguish between
# machine-readable error codes and human-readable messages.


# ============================================================================
# 67. CLEAN API-LIKE FUNCTION DESIGN
# ============================================================================

section("67. API-like function design")

@dataclass(frozen=True)
class CreateUserRequest:
    name: str
    email: str


@dataclass(frozen=True)
class CreateUserResponse:
    user_id: int
    name: str
    email: str


class UserApplication:
    def __init__(self) -> None:
        self._next_id = 1
        self._users: dict[int, UserRecord] = {}

    def create_user(
        self,
        request: CreateUserRequest,
    ) -> CreateUserResponse:
        name, email = UserValidator.validate(
            request.name,
            request.email,
        )

        user = UserRecord(
            user_id=self._next_id,
            name=name,
            email=email,
        )

        self._users[user.user_id] = user
        self._next_id += 1

        return CreateUserResponse(
            user_id=user.user_id,
            name=user.name,
            email=user.email,
        )


application = UserApplication()

response = application.create_user(
    CreateUserRequest(
        name="Atul",
        email="atul@example.com",
    )
)

print(response)


# ============================================================================
# 68. FUNCTIONAL STYLE
# ============================================================================

section("68. Functional-style building blocks")

def normalize_name(name: str) -> str:
    return " ".join(name.strip().split()).title()


def normalize_names(names: Iterable[str]) -> list[str]:
    return [normalize_name(name) for name in names]


names = ["  atul pandey ", "riya   sharma", "  JOHN DOE"]
print(normalize_names(names))


# Pure functions are easier to test because their output depends only on their
# inputs and they do not unexpectedly modify external state.


# ============================================================================
# 69. SIDE EFFECTS
# ============================================================================

section("69. Side effects")

def pure_add(first: int, second: int) -> int:
    return first + second


def write_message(path: Path, message: str) -> None:
    path.write_text(message, encoding="utf-8")


print(pure_add(2, 3))

with tempfile.TemporaryDirectory() as temporary_directory:
    side_effect_path = Path(temporary_directory) / "message.txt"
    write_message(side_effect_path, "Hello")
    print(side_effect_path.read_text(encoding="utf-8"))


# Database writes, file writes, network calls, logging, and global state changes
# are examples of side effects.


# ============================================================================
# 70. RESOURCE OWNERSHIP
# ============================================================================

section("70. Resource ownership")

class OwnedFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = None

    def __enter__(self) -> "OwnedFile":
        self._file = self.path.open("w", encoding="utf-8")
        return self

    def write(self, text: str) -> None:
        if self._file is None:
            raise RuntimeError("Resource is not open.")
        self._file.write(text)

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: Any,
    ) -> bool:
        if self._file is not None:
            self._file.close()
        self._file = None
        return False


with tempfile.TemporaryDirectory() as temporary_directory:
    owned_path = Path(temporary_directory) / "owned.txt"

    with OwnedFile(owned_path) as owned_file:
        owned_file.write("Managed resource.")

    print(owned_path.read_text(encoding="utf-8"))


# ============================================================================
# 71. DEBUGGING TECHNIQUES
# ============================================================================

section("71. Debugging")

def debug_calculation(price: float, quantity: int) -> float:
    subtotal = price * quantity
    tax = subtotal * 0.18
    total = subtotal + tax

    # Local variables make intermediate values inspectable during debugging.
    logger.debug(
        "price=%s quantity=%s subtotal=%s tax=%s total=%s",
        price,
        quantity,
        subtotal,
        tax,
        total,
    )

    return total


print(debug_calculation(100, 3))


# Practical debugging principles:
# - reproduce the failure
# - reduce it to the smallest useful example
# - inspect inputs and intermediate state
# - read the full traceback
# - identify the first meaningful failing operation
# - fix the underlying cause rather than suppressing the exception
# - add a regression test for the defect


# ============================================================================
# 72. TRACEBACK INTERPRETATION
# ============================================================================

section("72. Traceback interpretation")

def nested_failure() -> None:
    def level_two() -> None:
        raise RuntimeError("Demonstration failure.")

    level_two()


try:
    nested_failure()
except RuntimeError as exc:
    print("Captured:", exc)
    # A real traceback includes the chain of function calls that led to failure.


# ============================================================================
# 73. CLEANUP AFTER FAILURE
# ============================================================================

section("73. Cleanup after failure")

with tempfile.TemporaryDirectory() as temporary_directory:
    temporary_path = Path(temporary_directory) / "work.txt"

    try:
        temporary_path.write_text("work", encoding="utf-8")
        raise RuntimeError("Simulated failure.")
    except RuntimeError as exc:
        print("Failure handled:", exc)

    # TemporaryDirectory automatically removes its contents when the context
    # manager exits.


# ============================================================================
# 74. CONFIGURATION FILE
# ============================================================================

section("74. Configuration from JSON")

with tempfile.TemporaryDirectory() as temporary_directory:
    configuration_path = Path(temporary_directory) / "config.json"

    configuration_data = {
        "application": {
            "name": "BackendApp",
            "timeout_seconds": 10,
        },
        "features": {
            "metrics": True,
        },
    }

    configuration_path.write_text(
        json.dumps(configuration_data, indent=2),
        encoding="utf-8",
    )

    loaded_configuration = json.loads(
        configuration_path.read_text(encoding="utf-8")
    )

    print(loaded_configuration)


# Do not place production secrets in a source-controlled configuration file.


# ============================================================================
# 75. SECRET HANDLING
# ============================================================================

section("75. Secret handling")

def require_secret(environment_variable: str) -> str:
    value = os.getenv(environment_variable)

    if not value:
        raise RuntimeError(
            f"Required secret {environment_variable!r} is not configured."
        )

    return value


# Demonstration without requiring an actual secret:
os.environ["DEMO_SECRET"] = "example-only"
print("Secret configured:", bool(require_secret("DEMO_SECRET")))


# Never print or commit the secret itself.


# ============================================================================
# 76. PACKAGE INITIALIZATION CONCEPT
# ============================================================================

section("76. Package initialization")

# __init__.py can:
# - mark a traditional directory as a package
# - expose selected package-level names
# - initialize package-level state
#
# Avoid expensive initialization and surprising side effects in __init__.py.


# ============================================================================
# 77. PYTHON PATH
# ============================================================================

section("77. Module search path")

print("First import paths:")
for path_entry in sys.path[:5]:
    print(path_entry)

# Python searches locations in sys.path when resolving imports.
# Import errors can therefore arise from:
# - incorrect working directory
# - missing package installation
# - incorrect virtual environment
# - naming collisions
# - incorrect package structure


# ============================================================================
# 78. NAMING COLLISIONS
# ============================================================================

section("78. Import naming collisions")

# Avoid naming your own files after standard-library modules:
#
# math.py
# json.py
# logging.py
# pathlib.py
#
# Such names can shadow the intended standard-library modules and create
# confusing import behavior.


# ============================================================================
# 79. API CONTRACT VALIDATION
# ============================================================================

section("79. Contract validation")

@dataclass(frozen=True)
class ProductRequest:
    name: str
    price: float


def validate_product_request(request: ProductRequest) -> ProductRequest:
    name = request.name.strip()

    if not name:
        raise ValueError("Product name is required.")

    if not math.isfinite(request.price):
        raise ValueError("Price must be finite.")

    if request.price < 0:
        raise ValueError("Price cannot be negative.")

    return ProductRequest(name=name, price=request.price)


valid_product_request = validate_product_request(
    ProductRequest("Keyboard", 2500)
)

print(valid_product_request)


# ============================================================================
# 80. NUMERIC EDGE CASES
# ============================================================================

section("80. Numeric edge cases")

print("Infinity:", math.inf)
print("NaN:", math.nan)
print("Finite:", math.isfinite(100.0))
print("NaN is finite:", math.isfinite(math.nan))

try:
    validate_product_request(ProductRequest("Invalid", math.nan))
except ValueError as exc:
    print("Numeric validation:", exc)


# Floating-point arithmetic is not exact for many decimal fractions.
print("0.1 + 0.2 =", 0.1 + 0.2)
print("Rounded:", round(0.1 + 0.2, 10))

# Financial applications often require Decimal rather than binary floating
# point for monetary calculations.


# ============================================================================
# 81. DECIMAL
# ============================================================================

section("81. Decimal for monetary calculations")

from decimal import Decimal, ROUND_HALF_UP


price_decimal = Decimal("10.10")
tax_decimal = Decimal("0.18")

total_decimal = (price_decimal * (Decimal("1") + tax_decimal)).quantize(
    Decimal("0.01"),
    rounding=ROUND_HALF_UP,
)

print("Decimal total:", total_decimal)


# Decimal is preferable when exact decimal arithmetic and explicit rounding
# rules are required.


# ============================================================================
# 82. DATABASE-LIKE TRANSACTION CONCEPT
# ============================================================================

section("82. Transaction-style thinking")

class InMemoryTransaction:
    """
    Demonstrates commit/rollback thinking.

    It is not a replacement for a real database transaction.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self._original = state.copy()

    def commit(self) -> None:
        self._original = self.state.copy()

    def rollback(self) -> None:
        self.state.clear()
        self.state.update(self._original)


state = {"balance": 1000}
transaction = InMemoryTransaction(state)

try:
    state["balance"] -= 250
    if state["balance"] < 0:
        raise ValueError("Negative balance.")
    transaction.commit()
except Exception:
    transaction.rollback()

print("Committed state:", state)


# Real database transactions provide stronger atomicity, consistency,
# isolation, and durability guarantees.


# ============================================================================
# 83. TESTABLE FILE SERVICE
# ============================================================================

section("83. Testable file service")

class FileUserStore:
    """Small JSON store designed for dependency-free testing."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, user: UserRecord) -> None:
        data = {}

        if self.path.exists():
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )

        data[str(user.user_id)] = asdict(user)

        atomic_write_text(
            self.path,
            json.dumps(data, indent=2),
        )

    def get(self, user_id: int) -> UserRecord | None:
        if not self.path.exists():
            return None

        data = json.loads(self.path.read_text(encoding="utf-8"))
        raw = data.get(str(user_id))

        if raw is None:
            return None

        return UserRecord(
            user_id=int(raw["user_id"]),
            name=str(raw["name"]),
            email=str(raw["email"]),
        )


with tempfile.TemporaryDirectory() as temporary_directory:
    store = FileUserStore(Path(temporary_directory) / "users.json")
    store.save(created_user)

    loaded_user = store.get(created_user.user_id)
    print("Loaded:", loaded_user)


# ============================================================================
# 84. TESTABLE BUSINESS LOGIC
# ============================================================================

section("84. Business logic testing")

def calculate_discounted_total(
    price: Decimal,
    discount_percentage: Decimal,
) -> Decimal:
    if price < 0:
        raise ValueError("Price cannot be negative.")

    if not Decimal("0") <= discount_percentage <= Decimal("100"):
        raise ValueError("Discount must be between 0 and 100.")

    result = price * (
        Decimal("1") - discount_percentage / Decimal("100")
    )

    return result.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


print(
    calculate_discounted_total(
        Decimal("100.00"),
        Decimal("12.5"),
    )
)


# ============================================================================
# 85. LOGGING WITHOUT SENSITIVE DATA
# ============================================================================

section("85. Safe logging")

def log_user_action(user_id: int, action: str) -> None:
    logger.info(
        "user_id=%s action=%s",
        user_id,
        sanitize_log_value(action),
    )


log_user_action(101, "profile_updated")


# Avoid logging:
# - passwords
# - authentication tokens
# - API keys
# - full payment card numbers
# - unnecessary personal information


# ============================================================================
# 86. PRODUCTION ERROR HANDLING
# ============================================================================

section("86. Production-oriented error handling")

def production_style_operation(value: str) -> int:
    try:
        return parse_positive_integer(value)
    except ValueError:
        # Log enough operational context without exposing sensitive input.
        logger.warning("Input failed positive-integer validation.")
        raise


try:
    production_style_operation("-1")
except ValueError as exc:
    print("Expected application error:", exc)


# Error handling should distinguish:
# - expected validation failures
# - expected domain failures
# - transient infrastructure failures
# - unexpected programming defects


# ============================================================================
# 87. DEPENDENCY INJECTION
# ============================================================================

section("87. Dependency injection")

class Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    def __init__(self, fixed_time: datetime) -> None:
        self.fixed_time = fixed_time

    def now(self) -> datetime:
        return self.fixed_time


class TimestampedMessageService:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def create(self, message: str) -> dict[str, str]:
        return {
            "message": message,
            "created_at": self.clock.now().isoformat(),
        }


fixed_clock = FixedClock(
    datetime(2026, 1, 1, tzinfo=timezone.utc)
)

message_service = TimestampedMessageService(fixed_clock)

print(message_service.create("Test message"))


# Dependency injection makes code easier to test because dependencies can be
# replaced with deterministic implementations.


# ============================================================================
# 88. ABSTRACTION WITH PROTOCOL
# ============================================================================

section("88. Protocol-based dependency design")

from typing import Protocol


class UserStore(Protocol):
    def save(self, user: UserRecord) -> None:
        ...

    def get(self, user_id: int) -> UserRecord | None:
        ...


class MemoryUserStore:
    def __init__(self) -> None:
        self.users: dict[int, UserRecord] = {}

    def save(self, user: UserRecord) -> None:
        self.users[user.user_id] = user

    def get(self, user_id: int) -> UserRecord | None:
        return self.users.get(user_id)


class StoreBackedUserService:
    def __init__(self, store: UserStore) -> None:
        self.store = store

    def create(
        self,
        user_id: int,
        name: str,
        email: str,
    ) -> UserRecord:
        name, email = UserValidator.validate(name, email)

        user = UserRecord(user_id, name, email)
        self.store.save(user)
        return user


memory_store = MemoryUserStore()
store_service = StoreBackedUserService(memory_store)

print(
    store_service.create(
        10,
        "Test User",
        "test@example.com",
    )
)


# Protocols describe the operations required from an object without requiring
# a specific inheritance hierarchy.


# ============================================================================
# 89. ITERABLE API DESIGN
# ============================================================================

section("89. Iterable API design")

def batch_items(
    values: Iterable[Any],
    batch_size: int,
) -> Iterator[list[Any]]:
    if batch_size <= 0:
        raise ValueError("Batch size must be positive.")

    batch: list[Any] = []

    for value in values:
        batch.append(value)

        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


for batch in batch_items(range(10), 3):
    print(batch)


# Batching is useful when processing large collections while controlling memory
# consumption and downstream workload.


# ============================================================================
# 90. FILE ENCODING
# ============================================================================

section("90. Text encoding")

with tempfile.TemporaryDirectory() as temporary_directory:
    unicode_path = Path(temporary_directory) / "unicode.txt"

    unicode_path.write_text(
        "Python supports Unicode: café, भारत, 東京",
        encoding="utf-8",
    )

    print(unicode_path.read_text(encoding="utf-8"))


# Explicit UTF-8 encoding is preferable to relying on platform defaults when
# files are exchanged between environments.


# ============================================================================
# 91. FILE ERROR HANDLING
# ============================================================================

section("91. File error handling")

def read_required_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError("Required file does not exist.") from exc
    except PermissionError as exc:
        raise RuntimeError("Permission denied while reading file.") from exc
    except OSError as exc:
        raise RuntimeError("Operating-system file error.") from exc


try:
    read_required_file(Path("/path/that/does/not/exist"))
except RuntimeError as exc:
    print("File error:", exc)


# ============================================================================
# 92. FILE SIZE LIMIT
# ============================================================================

section("92. Defensive file processing")

def read_text_with_limit(path: Path, maximum_bytes: int = 1_000_000) -> str:
    if maximum_bytes <= 0:
        raise ValueError("Maximum size must be positive.")

    file_size = path.stat().st_size

    if file_size > maximum_bytes:
        raise ValueError("File is larger than the allowed limit.")

    return path.read_text(encoding="utf-8")


with tempfile.TemporaryDirectory() as temporary_directory:
    limited_path = Path(temporary_directory) / "small.txt"
    limited_path.write_text("small", encoding="utf-8")

    print(read_text_with_limit(limited_path))


# File-size limits can reduce memory exhaustion and resource-abuse risks.


# ============================================================================
# 93. APPLICATION ENTRY POINT
# ============================================================================

section("93. Application entry point")

def main() -> int:
    """
    Return a process exit status.

    Returning an integer makes command-line applications easier to integrate
    with operating systems and automation.
    """
    print("Backend fundamentals demonstration completed.")
    return 0


# The main function is invoked at the end so the script remains executable.
exit_code = main()
print("Exit code:", exit_code)


# ============================================================================
# 94. INTEGRATED MINI BACKEND
# ============================================================================

section("94. Integrated mini backend application")

@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    email: str


class CustomerRepository:
    """Persistence boundary for customers."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read_all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise RuntimeError("Customer database is invalid.") from exc

        if not isinstance(data, dict):
            raise RuntimeError("Customer database has invalid structure.")

        return data

    def save(self, customer: Customer) -> None:
        data = self._read_all()

        data[str(customer.customer_id)] = {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
        }

        atomic_write_text(
            self.path,
            json.dumps(data, indent=2),
        )

    def get(self, customer_id: int) -> Customer | None:
        data = self._read_all()
        raw = data.get(str(customer_id))

        if raw is None:
            return None

        return Customer(
            customer_id=int(raw["customer_id"]),
            name=str(raw["name"]),
            email=str(raw["email"]),
        )


class CustomerService:
    """Business layer for customer operations."""

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def create(
        self,
        customer_id: int,
        name: str,
        email: str,
    ) -> Customer:
        if self.repository.get(customer_id) is not None:
            raise DuplicateUserError(
                f"Customer {customer_id} already exists."
            )

        clean_name, clean_email = UserValidator.validate(
            name,
            email,
        )

        customer = Customer(
            customer_id=customer_id,
            name=clean_name,
            email=clean_email,
        )

        self.repository.save(customer)

        logger.info(
            "Customer created: id=%s",
            customer.customer_id,
        )

        return customer

    def find(self, customer_id: int) -> Customer:
        customer = self.repository.get(customer_id)

        if customer is None:
            raise ApplicationError(
                code="CUSTOMER_NOT_FOUND",
                message="Customer does not exist.",
            )

        return customer


with tempfile.TemporaryDirectory() as temporary_directory:
    database_path = Path(temporary_directory) / "customers.json"

    customer_repository = CustomerRepository(database_path)
    customer_service = CustomerService(customer_repository)

    customer = customer_service.create(
        1001,
        "  Atul Pandey ",
        "ATUL@EXAMPLE.COM",
    )

    print("Created customer:", customer)
    print("Found customer:", customer_service.find(1001))

    try:
        customer_service.create(
            1001,
            "Duplicate",
            "duplicate@example.com",
        )
    except DuplicateUserError as exc:
        print("Duplicate handled:", exc)


# ============================================================================
# 95. FINAL CONCEPTUAL CHECKS
# ============================================================================

section("95. Fundamental distinctions")

comparisons = {
    "list": "Ordered, mutable collection",
    "tuple": "Ordered, immutable collection",
    "set": "Unique elements, no positional indexing",
    "dict": "Key-value mapping",
    "module": "Python file containing reusable definitions",
    "package": "Organized collection of Python modules",
    "exception": "Object representing an abnormal execution condition",
    "generator": "Lazy iterator-producing function",
    "decorator": "Callable that modifies or wraps another callable",
    "context_manager": "Object controlling setup and cleanup around a block",
    "virtual_environment": "Isolated Python environment for a project",
}

for concept, description in comparisons.items():
    print(f"{concept}: {description}")


# ============================================================================
# 96. PRACTICAL BACKEND CHECKLIST
# ============================================================================

section("96. Practical backend checklist")

backend_principles = [
    "Validate external input.",
    "Keep business logic separate from persistence where complexity warrants it.",
    "Use specific exceptions for expected failures.",
    "Do not silently suppress unexpected exceptions.",
    "Use context managers for resources.",
    "Use pathlib for filesystem paths.",
    "Use explicit text encodings.",
    "Stream large files where appropriate.",
    "Do not hard-code secrets.",
    "Use environment-aware configuration.",
    "Use virtual environments for project isolation.",
    "Control and review dependencies.",
    "Use structured logging in production.",
    "Write tests for important behavior and edge cases.",
    "Measure performance before optimizing.",
    "Use Decimal when monetary precision requires it.",
    "Avoid unsafe dynamic code execution.",
    "Consider concurrency when state is shared.",
    "Use durable transactional storage when file persistence is insufficient.",
    "Keep module imports predictable and avoid circular dependencies.",
]

for principle in backend_principles:
    print("•", principle)


# ============================================================================
# SCRIPT COMPLETION
# ============================================================================

section("Backend Programming Fundamentals complete")

print(
    """
This executable study file demonstrated backend-oriented Python fundamentals
from variables and functions through modules, packages, exceptions, files,
environments, testing, security, performance, and application architecture.
"""
)
