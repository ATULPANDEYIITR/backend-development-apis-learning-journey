"""
Error Handling: Exceptions, HTTPException, Custom Exceptions, Exception Handlers,
and Structured Errors

A comprehensive standalone study script.

Optional dependency:
    FastAPI and Uvicorn are used in the final web/API section because HTTPException
    and exception handlers are application-level HTTP concepts.

Install when running the API example:
    pip install fastapi uvicorn

Run the API:
    uvicorn error_handling_course:app --reload

The first sections use only Python's standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar
import json
import logging
import math
import re
import sys
import traceback


# =============================================================================
# 1. BASIC ERROR HANDLING
# =============================================================================

def section(title: str) -> None:
    """Print a visually consistent section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def basic_try_except() -> None:
    """
    try contains code that might fail.
    except handles a selected failure.
    """
    section("1. Basic try / except")

    numerator = 10
    denominator = 0

    try:
        result = numerator / denominator
        print(result)
    except ZeroDivisionError:
        print("A number cannot be divided by zero.")


def multiple_exception_types() -> None:
    section("2. Handling multiple exception types")

    examples = ["42", "not-a-number", None, "3.14"]

    for value in examples:
        try:
            number = int(value)
            print(f"{value!r} -> {number}")
        except ValueError:
            print(f"{value!r} cannot be converted to an integer.")
        except TypeError:
            print(f"{value!r} has an incompatible type.")


def exception_as_variable() -> None:
    section("3. Capturing the exception object")

    try:
        int("abc")
    except ValueError as error:
        print("Exception type:", type(error).__name__)
        print("Exception message:", str(error))


def else_and_finally() -> None:
    section("4. else and finally")

    try:
        value = int("100")
    except ValueError:
        print("Conversion failed.")
    else:
        print("Conversion succeeded:", value)
    finally:
        print("Cleanup code runs regardless of success or failure.")


# =============================================================================
# 2. RAISING EXCEPTIONS
# =============================================================================

def validate_age(age: int) -> None:
    """Raise an exception when the input violates the function's contract."""
    if not isinstance(age, int):
        raise TypeError("age must be an integer")

    if age < 0:
        raise ValueError("age cannot be negative")

    if age > 150:
        raise ValueError("age is outside the supported range")


def raising_exceptions() -> None:
    section("5. Raising exceptions")

    test_values = [25, -5, 200, "25"]

    for age in test_values:
        try:
            validate_age(age)
            print(f"Valid age: {age}")
        except (TypeError, ValueError) as error:
            print(f"Rejected {age!r}: {error}")


# =============================================================================
# 3. BUILT-IN EXCEPTIONS
# =============================================================================

def demonstrate_common_exceptions() -> None:
    section("6. Common built-in exceptions")

    operations: List[Callable[[], Any]] = [
        lambda: 10 / 0,
        lambda: int("abc"),
        lambda: [1, 2, 3][10],
        lambda: {"name": "Atul"}["missing"],
        lambda: (10).unknown_attribute,
    ]

    for operation in operations:
        try:
            print(operation())
        except Exception as error:
            print(type(error).__name__, "->", error)


# =============================================================================
# 4. EXCEPTION HIERARCHY
# =============================================================================

def exception_hierarchy_demo() -> None:
    section("7. Exception hierarchy")

    """
    Exception is the common base for most application-level exceptions.

    Examples:
        ValueError
        TypeError
        LookupError
            KeyError
            IndexError

    Avoid catching BaseException in normal application code because it also
    includes system-level control-flow exceptions such as KeyboardInterrupt.
    """

    print("ValueError subclass of Exception:",
          issubclass(ValueError, Exception))

    print("KeyError subclass of LookupError:",
          issubclass(KeyError, LookupError))

    print("KeyboardInterrupt subclass of Exception:",
          issubclass(KeyboardInterrupt, Exception))

    try:
        raise KeyError("customer_id")
    except LookupError:
        print("A lookup-related exception was handled.")


# =============================================================================
# 5. CUSTOM EXCEPTIONS
# =============================================================================

class ApplicationError(Exception):
    """Base class for expected application failures."""


class ValidationError(ApplicationError):
    """Input data does not satisfy application rules."""


class ResourceNotFoundError(ApplicationError):
    """Requested application resource does not exist."""


class ConflictError(ApplicationError):
    """Requested operation conflicts with current state."""


class AuthorizationError(ApplicationError):
    """Authenticated caller is not allowed to perform an operation."""


class PaymentError(ApplicationError):
    """Payment processing failed."""


def custom_exception_demo() -> None:
    section("8. Custom exceptions")

    def register_username(username: str) -> None:
        if not isinstance(username, str):
            raise ValidationError("username must be a string")

        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            raise ValidationError(
                "username must contain 3-20 letters, numbers, or underscores"
            )

        if username.lower() == "admin":
            raise ConflictError("username is reserved")

        print("Username accepted:", username)

    for username in ["Atul_123", "x", "admin", "bad-name"]:
        try:
            register_username(username)
        except ApplicationError as error:
            print(type(error).__name__, "->", error)


# =============================================================================
# 6. CUSTOM EXCEPTIONS WITH STRUCTURED DATA
# =============================================================================

@dataclass
class ErrorDetail:
    field: Optional[str]
    message: str
    code: str


class StructuredApplicationError(ApplicationError):
    """
    Application exception carrying machine-readable information.

    This is useful when an API must return predictable error objects instead
    of forcing clients to parse human-readable messages.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: Optional[List[ErrorDetail]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": [asdict(detail) for detail in self.details],
            }
        }


def structured_error_demo() -> None:
    section("9. Structured application errors")

    error = StructuredApplicationError(
        "Validation failed",
        code="VALIDATION_ERROR",
        status_code=422,
        details=[
            ErrorDetail("email", "Email address is required", "REQUIRED"),
            ErrorDetail("age", "Age must be at least 18", "MIN_VALUE"),
        ],
    )

    print(json.dumps(error.to_dict(), indent=2))


# =============================================================================
# 7. EXCEPTION CHAINING
# =============================================================================

def load_integer(raw_value: str) -> int:
    try:
        return int(raw_value)
    except ValueError as error:
        # "from error" preserves the original cause.
        raise ValidationError("The supplied value must be an integer") from error


def exception_chaining_demo() -> None:
    section("10. Exception chaining")

    try:
        load_integer("abc")
    except ValidationError as error:
        print("Application exception:", error)
        print("Original cause:", type(error.__cause__).__name__)
        print("Original message:", error.__cause__)


# =============================================================================
# 8. GOOD AND BAD CATCHING STRATEGIES
# =============================================================================

def broad_exception_catching_demo() -> None:
    section("11. Exception-catching strategy")

    try:
        result = 100 / 5
        print("Result:", result)
    except Exception as error:
        # Catch Exception only when there is a meaningful recovery or
        # translation strategy.
        print("Unexpected application error:", error)

    try:
        raise KeyboardInterrupt()
    except Exception:
        print("This line is not reached because KeyboardInterrupt does not
        inherit from Exception.")


# The previous demonstration cannot execute its print because the exception
# would escape. A safe version is provided below.

def safe_exception_hierarchy_demo() -> None:
    section("12. Exception hierarchy and system-control exceptions")

    try:
        raise KeyboardInterrupt()
    except BaseException as error:
        print("Caught explicitly for demonstration:",
              type(error).__name__)

    print(
        "In normal application code, do not use BaseException as a general "
        "catch-all."
    )


# =============================================================================
# 9. CONTEXT MANAGERS AND CLEANUP
# =============================================================================

class ManagedResource:
    """A small context-manager example demonstrating deterministic cleanup."""

    def __enter__(self) -> "ManagedResource":
        print("Resource acquired.")
        return self

    def __exit__(
        self,
        exception_type: Any,
        exception_value: Any,
        traceback_object: Any,
    ) -> bool:
        print("Resource released.")

        # False means an exception is not suppressed.
        return False

    def perform_operation(self) -> None:
        print("Performing operation...")
        raise RuntimeError("Resource operation failed")


def context_manager_demo() -> None:
    section("13. Cleanup with context managers")

    try:
        with ManagedResource() as resource:
            resource.perform_operation()
    except RuntimeError as error:
        print("Handled:", error)


# =============================================================================
# 10. ASSERTIONS VS VALIDATION
# =============================================================================

def assertion_demo() -> None:
    section("14. Assertions are not general input validation")

    value = 10

    # Assertions document internal invariants.
    # They should not be relied upon for validating untrusted user input.
    assert value > 0, "Internal invariant failed"

    print("Internal invariant is valid.")


# =============================================================================
# 11. DECORATOR-BASED EXCEPTION TRANSLATION
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def translate_errors(function: F) -> F:
    """
    Convert low-level implementation errors into an application-specific
    exception while retaining the original cause.
    """

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except (ValueError, TypeError) as error:
            raise ValidationError(
                f"Invalid value supplied to {function.__name__}"
            ) from error

    return wrapper  # type: ignore[return-value]


@translate_errors
def parse_percentage(value: str) -> float:
    percentage = float(value)

    if not 0 <= percentage <= 100:
        raise ValueError("percentage must be between 0 and 100")

    return percentage


def decorator_demo() -> None:
    section("15. Exception translation with decorators")

    for value in ["25.5", "150", "abc"]:
        try:
            print(value, "->", parse_percentage(value))
        except ValidationError as error:
            print(value, "->", type(error).__name__, error)


# =============================================================================
# 12. STRUCTURED ERROR RESPONSE MODEL
# =============================================================================

@dataclass
class ApiError:
    code: str
    message: str
    status: int
    request_id: str
    details: List[Dict[str, Any]]

    def to_response(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "status": self.status,
                "request_id": self.request_id,
                "details": self.details,
            }
        }


def structured_api_error_demo() -> None:
    section("16. Structured API error representation")

    response = ApiError(
        code="RESOURCE_NOT_FOUND",
        message="Customer was not found.",
        status=404,
        request_id="req-demo-001",
        details=[
            {
                "field": "customer_id",
                "value": "C-999",
                "reason": "No customer exists with this identifier.",
            }
        ],
    )

    print(json.dumps(response.to_response(), indent=2))


# =============================================================================
# 13. SAFE LOGGING
# =============================================================================

def logging_demo() -> None:
    section("17. Logging exceptions safely")

    logger = logging.getLogger("error-handling-demo")

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(levelname)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)

    try:
        {}["missing"]
    except KeyError:
        # exc_info=True records traceback information.
        # Never log passwords, access tokens, API keys, or other secrets.
        logger.exception("Customer lookup failed")


# =============================================================================
# 14. TRANSACTION-LIKE ERROR HANDLING
# =============================================================================

class InsufficientFundsError(PaymentError):
    """The account does not contain enough money."""


class Account:
    def __init__(self, account_id: str, balance: float) -> None:
        self.account_id = account_id
        self.balance = balance

    def debit(self, amount: float) -> None:
        if amount <= 0:
            raise ValidationError("debit amount must be positive")

        if amount > self.balance:
            raise InsufficientFundsError("insufficient funds")

        self.balance -= amount


def transfer_money(
    sender: Account,
    receiver: Account,
    amount: float,
) -> None:
    """
    A small transaction-style example.

    If the receiver operation fails after the sender is debited, the original
    sender state must be restored. Real financial systems require stronger
    transactional guarantees than this in-memory example.
    """
    original_sender_balance = sender.balance
    original_receiver_balance = receiver.balance

    try:
        sender.debit(amount)

        if receiver.account_id == "INVALID":
            raise ResourceNotFoundError("receiver account does not exist")

        receiver.balance += amount
    except Exception:
        sender.balance = original_sender_balance
        receiver.balance = original_receiver_balance
        raise


def transaction_demo() -> None:
    section("18. Transaction-style rollback")

    sender = Account("A-001", 1000)
    receiver = Account("INVALID", 100)

    try:
        transfer_money(sender, receiver, 250)
    except ApplicationError as error:
        print("Transfer failed:", type(error).__name__, error)

    print("Sender balance:", sender.balance)
    print("Receiver balance:", receiver.balance)


# =============================================================================
# 15. RETRYABLE VS NON-RETRYABLE ERRORS
# =============================================================================

class RetryableError(ApplicationError):
    """A temporary failure that may succeed when retried."""


class NonRetryableError(ApplicationError):
    """A permanent failure that should not be blindly retried."""


def classify_failure(error: Exception) -> str:
    if isinstance(error, RetryableError):
        return "retryable"
    if isinstance(error, NonRetryableError):
        return "non-retryable"
    return "unknown"


def retry_classification_demo() -> None:
    section("19. Retryable versus non-retryable errors")

    errors = [
        RetryableError("database temporarily unavailable"),
        NonRetryableError("invalid customer identifier"),
        ValueError("invalid local input"),
    ]

    for error in errors:
        print(type(error).__name__, "->", classify_failure(error))


# =============================================================================
# 16. FASTAPI HTTPException AND EXCEPTION HANDLERS
# =============================================================================

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Error Handling Demonstration API",
        version="1.0.0",
        description="Examples of HTTPException, custom exceptions, and handlers.",
    )

    class Customer(BaseModel):
        name: str = Field(min_length=2, max_length=100)
        age: int = Field(ge=18, le=120)

    CUSTOMERS: Dict[int, Dict[str, Any]] = {
        1: {"id": 1, "name": "Atul", "age": 30},
        2: {"id": 2, "name": "Example User", "age": 35},
    }

    class ApiNotFoundError(ApplicationError):
        def __init__(self, resource: str, identifier: Any) -> None:
            self.resource = resource
            self.identifier = identifier
            super().__init__(
                f"{resource} with identifier {identifier!r} was not found"
            )

    class ApiConflictError(ApplicationError):
        def __init__(self, message: str) -> None:
            super().__init__(message)

    @app.exception_handler(ApiNotFoundError)
    async def handle_api_not_found(
        request: Request,
        exc: ApiNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": str(exc),
                    "resource": exc.resource,
                    "identifier": exc.identifier,
                    "path": request.url.path,
                }
            },
        )

    @app.exception_handler(ApiConflictError)
    async def handle_api_conflict(
        request: Request,
        exc: ApiConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONFLICT",
                    "message": str(exc),
                    "path": request.url.path,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """
        Convert framework validation information into a stable API contract.

        The exact internal validation representation can change between
        framework versions, so the application can normalize it here.
        """
        details = []

        for item in exc.errors():
            details.append(
                {
                    "location": list(item.get("loc", [])),
                    "message": item.get("msg", "Invalid value"),
                    "type": item.get("type", "validation_error"),
                }
            )

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "path": request.url.path,
                    "details": details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Last-resort application boundary.

        The client receives a generic message rather than an internal
        traceback, SQL statement, filesystem path, secret, or stack detail.
        """
        logging.getLogger("api").exception(
            "Unhandled API exception on %s", request.url.path
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "path": request.url.path,
                }
            },
        )

    @app.get("/customers/{customer_id}")
    async def get_customer(customer_id: int) -> Dict[str, Any]:
        customer = CUSTOMERS.get(customer_id)

        if customer is None:
            # HTTPException is useful for direct HTTP-level failures.
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "CUSTOMER_NOT_FOUND",
                    "message": f"Customer {customer_id} does not exist.",
                },
            )

        return customer

    @app.post("/customers", status_code=201)
    async def create_customer(customer: Customer) -> Dict[str, Any]:
        new_id = max(CUSTOMERS) + 1

        if any(
            item["name"].casefold() == customer.name.casefold()
            for item in CUSTOMERS.values()
        ):
            raise ApiConflictError(
                f"Customer named {customer.name!r} already exists."
            )

        CUSTOMERS[new_id] = {
            "id": new_id,
            "name": customer.name,
            "age": customer.age,
        }

        return CUSTOMERS[new_id]

    @app.get("/customers/{customer_id}/custom-error")
    async def custom_not_found(customer_id: int) -> Dict[str, Any]:
        if customer_id not in CUSTOMERS:
            raise ApiNotFoundError("customer", customer_id)

        return CUSTOMERS[customer_id]

    @app.get("/http-exception")
    async def http_exception_example() -> None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": "This endpoint intentionally demonstrates HTTPException.",
            },
        )

    @app.get("/unexpected")
    async def unexpected_error_example() -> None:
        # The global Exception handler converts this into a safe 500 response.
        raise RuntimeError("Internal implementation failure")


else:
    app = None


# =============================================================================
# 17. HTTP ERROR DESIGN PRINCIPLES
# =============================================================================

def print_http_design_principles() -> None:
    section("20. HTTP error design principles")

    principles = [
        "400: request cannot be processed because the request is invalid.",
        "401: authentication is required or authentication failed.",
        "403: the caller is authenticated but not permitted.",
        "404: the requested resource does not exist.",
        "409: the request conflicts with current application state.",
        "422: syntactically valid request data fails validation rules.",
        "429: rate limit has been exceeded.",
        "500: unexpected server-side failure.",
        "503: service is temporarily unavailable.",
    ]

    for principle in principles:
        print("-", principle)

    print(
        "\nHTTP status codes communicate protocol-level meaning; the structured "
        "error body should communicate application-specific details."
    )


# =============================================================================
# 18. API ERROR RESPONSE CONTRACT
# =============================================================================

def example_error_contracts() -> None:
    section("21. Example structured error contracts")

    examples = [
        {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": [
                    {
                        "field": "email",
                        "code": "INVALID_FORMAT",
                        "message": "A valid email address is required.",
                    }
                ],
            }
        },
        {
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "Customer does not exist.",
                "details": [],
            }
        },
        {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": [],
            }
        },
    ]

    for example in examples:
        print(json.dumps(example, indent=2))


# =============================================================================
# 19. TESTABLE ERROR BEHAVIOR
# =============================================================================

def expect_exception(
    function: Callable[[], Any],
    expected_type: type[BaseException],
) -> None:
    """
    Tiny dependency-free testing helper.

    Production projects normally use a dedicated test framework, but the
    underlying idea is simple: an exception is part of observable behavior.
    """
    try:
        function()
    except expected_type:
        print(f"PASS: {expected_type.__name__} was raised.")
    except Exception as error:
        print(
            f"FAIL: expected {expected_type.__name__}, "
            f"got {type(error).__name__}."
        )
    else:
        print(f"FAIL: expected {expected_type.__name__}, but nothing was raised.")


def testing_exception_behavior() -> None:
    section("22. Testing exception behavior")

    expect_exception(
        lambda: validate_age(-1),
        ValueError,
    )

    expect_exception(
        lambda: validate_age("18"),  # type: ignore[arg-type]
        TypeError,
    )

    expect_exception(
        lambda: load_integer("not-an-integer"),
        ValidationError,
    )


# =============================================================================
# 20. COMPLETE SERVICE-LAYER EXAMPLE
# =============================================================================

@dataclass
class User:
    user_id: int
    email: str
    active: bool = True


class UserRepository:
    def __init__(self) -> None:
        self._users: Dict[int, User] = {
            1: User(1, "atul@example.com"),
            2: User(2, "user@example.com"),
        }

    def find(self, user_id: int) -> User:
        user = self._users.get(user_id)

        if user is None:
            raise ResourceNotFoundError(
                f"user {user_id} does not exist"
            )

        return user

    def save(self, user: User) -> None:
        self._users[user.user_id] = user


class UserService:
    """
    Business logic should not normally know about HTTP response formatting.

    It raises meaningful domain/application exceptions. A web layer can later
    translate those exceptions into HTTP status codes and structured JSON.
    """

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def deactivate_user(self, user_id: int) -> User:
        user = self.repository.find(user_id)

        if not user.active:
            raise ConflictError("user is already inactive")

        user.active = False
        self.repository.save(user)

        return user


def service_layer_demo() -> None:
    section("23. Separation between service errors and HTTP errors")

    service = UserService(UserRepository())

    for user_id in [1, 1, 999]:
        try:
            user = service.deactivate_user(user_id)
            print("Deactivated:", user)
        except ResourceNotFoundError as error:
            print("Domain error:", error)
        except ConflictError as error:
            print("Business conflict:", error)


# =============================================================================
# 21. MAIN STUDY RUNNER
# =============================================================================

def main() -> None:
    """
    Run the educational demonstrations.

    The FastAPI application is created at module level when FastAPI is
    installed. This main function demonstrates the concepts without starting
    a blocking web server.
    """
    demonstrations = [
        basic_try_except,
        multiple_exception_types,
        exception_as_variable,
        else_and_finally,
        raising_exceptions,
        demonstrate_common_exceptions,
        exception_hierarchy_demo,
        custom_exception_demo,
        structured_error_demo,
        exception_chaining_demo,
        safe_exception_hierarchy_demo,
        context_manager_demo,
        assertion_demo,
        decorator_demo,
        structured_api_error_demo,
        logging_demo,
        transaction_demo,
        retry_classification_demo,
        print_http_design_principles,
        example_error_contracts,
        testing_exception_behavior,
        service_layer_demo,
    ]

    for demonstration in demonstrations:
        try:
            demonstration()
        except Exception as error:
            # A demonstration should not prevent the remaining educational
            # sections from running. In production, decide explicitly whether
            # such failures should propagate, be logged, or be recovered from.
            print(
                f"\nDemonstration {demonstration.__name__} failed: "
                f"{type(error).__name__}: {error}"
            )

    section("24. FastAPI availability")

    if FASTAPI_AVAILABLE:
        print("FastAPI is installed.")
        print("API object is available as variable: app")
        print("Start with: uvicorn error_handling_course:app --reload")
        print("Useful endpoints:")
        print("  GET  /customers/1")
        print("  GET  /customers/999")
        print("  POST /customers")
        print("  GET  /customers/999/custom-error")
        print("  GET  /http-exception")
        print("  GET  /unexpected")
    else:
        print("FastAPI is not installed.")
        print(
            "The standard-library demonstrations are still fully usable. "
            "Install FastAPI and Uvicorn to execute the HTTPException/API section."
        )

    section("25. Key implementation rules demonstrated")

    rules = [
        "Catch specific exceptions when recovery or translation is possible.",
        "Use custom exceptions to represent meaningful application failures.",
        "Preserve low-level causes with exception chaining when translating errors.",
        "Separate domain/service errors from HTTP transport concerns.",
        "Use HTTPException for direct HTTP-level failures.",
        "Use custom exception handlers to normalize application errors.",
        "Return structured machine-readable error codes and details.",
        "Do not expose stack traces, secrets, SQL, filesystem paths, or internals.",
        "Log unexpected failures server-side with enough diagnostic context.",
        "Do not retry non-retryable validation or authorization failures blindly.",
        "Use transactions or durable consistency mechanisms for real financial operations.",
        "Treat error behavior as testable application behavior.",
    ]

    for index, rule in enumerate(rules, start=1):
        print(f"{index:02d}. {rule}")


if __name__ == "__main__":
    main()
