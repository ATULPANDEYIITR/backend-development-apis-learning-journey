"""
FastAPI Introduction
====================

Topic:
FastAPI architecture, application instance, routes, decorators, and path operations.

This standalone study script teaches the subject from beginner concepts through
advanced implementation patterns. It uses FastAPI itself when available and also
contains a lightweight architecture simulation so that the core ideas remain
visible even when FastAPI is not installed.

Run:
    python fastapi_introduction.py

Optional installation:
    pip install fastapi uvicorn

Run the real API:
    uvicorn fastapi_introduction:app --reload

Then inspect:
    http://127.0.0.1:8000/
    http://127.0.0.1:8000/docs
    http://127.0.0.1:8000/redoc
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import json
import math
import re
import sys
import time
from urllib.parse import parse_qs, urlparse


# ============================================================================
# 1. BEGINNER CONCEPTS
# ============================================================================

print("=" * 78)
print("FASTAPI INTRODUCTION")
print("Architecture, application instance, routes, decorators, path operations")
print("=" * 78)


def explain_http_basics() -> None:
    """Demonstrate the HTTP concepts that FastAPI builds on."""
    print("\n--- HTTP foundations ---")

    request = {
        "method": "GET",
        "path": "/users/42",
        "headers": {"Accept": "application/json"},
        "query": {"active": "true"},
    }

    response = {
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "body": {"id": 42, "name": "Ada"},
    }

    print("Request:")
    print(json.dumps(request, indent=2))
    print("\nResponse:")
    print(json.dumps(response, indent=2))

    print(
        """
FastAPI receives HTTP requests and maps them to Python functions.

A route usually consists of:
    HTTP method + URL path + Python callable

Examples:
    GET    /users
    GET    /users/{user_id}
    POST   /users
    PUT    /users/{user_id}
    DELETE /users/{user_id}

The URL path identifies a resource or operation.
The HTTP method communicates the intended operation.
"""
    )


explain_http_basics()


# ============================================================================
# 2. ARCHITECTURE OVERVIEW
# ============================================================================

def explain_architecture() -> None:
    print("\n--- FastAPI architecture ---")
    print(
        """
A simplified request path is:

Client
  |
  v
ASGI server such as Uvicorn
  |
  v
FastAPI application instance
  |
  v
Routing system
  |
  v
Path operation function
  |
  +--> dependency resolution
  +--> parameter validation
  +--> application logic
  |
  v
Response serialization
  |
  v
ASGI server
  |
  v
Client

FastAPI is an ASGI web framework. It uses Starlette for core web behavior
such as routing and HTTP handling, and Pydantic for data validation and
serialization.

The application object is the central object on which routes, middleware,
exception handlers, startup/shutdown behavior, and other configuration are
registered.
"""
    )


explain_architecture()


# ============================================================================
# 3. OPTIONAL REAL FASTAPI IMPORT
# ============================================================================

try:
    from fastapi import FastAPI, HTTPException, Query, Path, Depends
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None
    HTTPException = None
    Query = None
    Path = None
    Depends = None
    BaseModel = object
    Field = None


print("\nFastAPI installed:", FASTAPI_AVAILABLE)


# ============================================================================
# 4. APPLICATION INSTANCE
# ============================================================================

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="FastAPI Introduction API",
        description=(
            "Educational API demonstrating application instances, routes, "
            "decorators, and path operations."
        ),
        version="1.0.0",
    )
else:
    app = None


def explain_application_instance() -> None:
    print("\n--- Application instance ---")
    print(
        """
The standard FastAPI starting point is:

    app = FastAPI()

`app` is an instance of the FastAPI application class.

Decorators such as:

    @app.get("/")
    @app.post("/items")
    @app.put("/items/{item_id}")
    @app.delete("/items/{item_id}")

register path operations with that application.

The object is not merely a collection of functions. It participates in
routing, OpenAPI schema generation, dependency management, exception
handling, middleware configuration, and ASGI request processing.
"""
    )

    if app is not None:
        print("Application type:", type(app).__name__)
        print("Application title:", app.title)
        print("Application version:", app.version)


explain_application_instance()


# ============================================================================
# 5. DECORATORS
# ============================================================================

def demonstrate_python_decorator() -> None:
    print("\n--- Python decorator mechanics ---")

    def announce(function: Callable[..., Any]) -> Callable[..., Any]:
        """A tiny decorator illustrating the mechanism behind @ syntax."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            print(f"Calling {function.__name__}")
            result = function(*args, **kwargs)
            print(f"Returned from {function.__name__}")
            return result

        return wrapper

    @announce
    def add_numbers(first: int, second: int) -> int:
        return first + second

    result = add_numbers(3, 4)
    print("Result:", result)

    print(
        """
Decorator syntax:

    @decorator
    def function():
        ...

is conceptually similar to:

    function = decorator(function)

FastAPI uses this mechanism to register functions as path operations.
The FastAPI decorator does much more than the simple decorator above:
it records the HTTP method, path, endpoint function, response information,
dependencies, metadata, and validation information.
"""
    )


demonstrate_python_decorator()


# ============================================================================
# 6. REAL FASTAPI ROUTES
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.get("/")
    def root() -> Dict[str, str]:
        """Basic GET path operation."""
        return {"message": "FastAPI is running"}


    @app.get("/health")
    def health_check() -> Dict[str, str]:
        """Health endpoint commonly used by deployment infrastructure."""
        return {"status": "ok"}


    @app.get("/hello/{name}")
    def hello_name(name: str) -> Dict[str, str]:
        """Path parameter example."""
        return {"message": f"Hello, {name}"}


    @app.get("/products/{product_id}")
    def get_product(product_id: int) -> Dict[str, Any]:
        """
        Path parameter with an integer annotation.

        FastAPI validates the incoming path value before calling this
        function. A request such as /products/abc produces a validation error
        rather than passing the string "abc" to this function.
        """
        return {
            "product_id": product_id,
            "product_type": type(product_id).__name__,
        }


    @app.get("/search")
    def search_products(
        q: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Query parameter example.

        Example:
            /search?q=laptop&limit=5
        """
        return {
            "query": q,
            "limit": limit,
        }


    # =========================================================================
    # 7. PATH OPERATION DECORATORS
    # =========================================================================

    class Product(BaseModel):
        name: str = Field(min_length=1, max_length=100)
        price: float = Field(gt=0)
        in_stock: bool = True


    @app.post("/products")
    def create_product(product: Product) -> Dict[str, Any]:
        """POST operation with a validated JSON request body."""
        return {
            "message": "Product accepted",
            "product": product.model_dump(),
        }


    @app.put("/products/{product_id}")
    def update_product(
        product_id: int,
        product: Product,
    ) -> Dict[str, Any]:
        """PUT combines a path parameter and request body."""
        return {
            "message": "Product updated",
            "product_id": product_id,
            "product": product.model_dump(),
        }


    @app.delete("/products/{product_id}")
    def delete_product(product_id: int) -> Dict[str, Any]:
        """DELETE operation."""
        return {
            "message": "Product deleted",
            "product_id": product_id,
        }


    @app.get("/products/{product_id}/reviews")
    def list_reviews(product_id: int) -> Dict[str, Any]:
        """Nested resource route."""
        return {
            "product_id": product_id,
            "reviews": [],
        }


# ============================================================================
# 8. ROUTE REPRESENTATION WITHOUT FASTAPI
# ============================================================================

@dataclass
class RouteDefinition:
    """Small educational model of a registered route."""

    method: str
    path: str
    endpoint_name: str


class MiniRouter:
    """
    A deliberately small router.

    This is not a replacement for FastAPI. It exists to make the relationship
    between decorators, registered routes, and request matching understandable.
    """

    def __init__(self) -> None:
        self.routes: List[RouteDefinition] = []

    def register(
        self,
        method: str,
        path: str,
        endpoint: Callable[..., Any],
    ) -> None:
        self.routes.append(
            RouteDefinition(
                method=method.upper(),
                path=path,
                endpoint_name=endpoint.__name__,
            )
        )

    def list_routes(self) -> List[RouteDefinition]:
        return list(self.routes)


mini_router = MiniRouter()


def mini_get(path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Educational equivalent of the basic idea behind @app.get."""

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        mini_router.register("GET", path, function)
        return function

    return decorator


@mini_get("/demo")
def demo_endpoint() -> Dict[str, str]:
    return {"message": "registered by a decorator"}


@mini_get("/demo/{item_id}")
def demo_item(item_id: int) -> Dict[str, int]:
    return {"item_id": item_id}


print("\n--- Mini router registrations ---")
for route in mini_router.list_routes():
    print(route)


# ============================================================================
# 9. ROUTE MATCHING
# ============================================================================

def compile_path_pattern(path: str) -> re.Pattern[str]:
    """
    Convert a simple FastAPI-like path into a regular expression.

    Examples:
        /users
        /users/{user_id}
        /orders/{order_id}/items/{item_id}

    This simplified implementation treats parameters as strings. Real
    frameworks have substantially more routing and conversion behavior.
    """
    parameter_names = re.findall(r"{([^{}]+)}", path)
    escaped = re.escape(path)

    for name in parameter_names:
        escaped = escaped.replace(r"\{" + name + r"\}", rf"(?P<{name}>[^/]+)")

    return re.compile("^" + escaped + "$")


def match_path(path_template: str, actual_path: str) -> Optional[Dict[str, str]]:
    pattern = compile_path_pattern(path_template)
    match = pattern.match(actual_path)

    if match is None:
        return None

    return match.groupdict()


print("\n--- Simplified path matching ---")
print(match_path("/users/{user_id}", "/users/42"))
print(match_path("/orders/{order_id}/items/{item_id}", "/orders/7/items/3"))
print(match_path("/users/{user_id}", "/products/42"))


# ============================================================================
# 10. PATH PARAMETERS
# ============================================================================

def convert_path_parameter(raw_value: str, expected_type: type) -> Any:
    """
    Demonstrate basic type conversion.

    FastAPI performs richer validation than this educational function.
    """
    if expected_type is int:
        try:
            return int(raw_value)
        except ValueError as exc:
            raise ValueError(f"Expected integer, received {raw_value!r}") from exc

    if expected_type is float:
        try:
            return float(raw_value)
        except ValueError as exc:
            raise ValueError(f"Expected number, received {raw_value!r}") from exc

    if expected_type is bool:
        normalized = raw_value.lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        raise ValueError(f"Expected boolean, received {raw_value!r}")

    return raw_value


print("\n--- Path parameter conversion ---")
for value in ["42", "100"]:
    print(value, "->", convert_path_parameter(value, int))

try:
    convert_path_parameter("abc", int)
except ValueError as error:
    print("Validation error:", error)


# ============================================================================
# 11. PATH PARAMETERS VERSUS QUERY PARAMETERS
# ============================================================================

def parse_request_url(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)

    query_parameters = {
        key: values[-1]
        for key, values in parse_qs(parsed.query).items()
    }

    return {
        "path": parsed.path,
        "query": query_parameters,
    }


print("\n--- Path versus query parameters ---")
request = parse_request_url("/products/42?include_reviews=true&limit=5")
print(json.dumps(request, indent=2))

print(
    """
Path:
    /products/42

Query string:
    ?include_reviews=true&limit=5

A path parameter is normally part of the resource identity:
    /products/{product_id}

A query parameter commonly modifies retrieval or filtering:
    /products?category=books&limit=20
"""
)


# ============================================================================
# 12. HTTP METHODS
# ============================================================================

def demonstrate_http_methods() -> None:
    print("\n--- Common path operation decorators ---")

    method_examples = {
        "@app.get": "Read or retrieve data",
        "@app.post": "Create a resource or trigger a server-side operation",
        "@app.put": "Replace or update a resource",
        "@app.patch": "Partially update a resource",
        "@app.delete": "Delete a resource",
        "@app.options": "Discover communication options",
        "@app.head": "Retrieve headers without a response body",
    }

    for decorator, meaning in method_examples.items():
        print(f"{decorator:<18} {meaning}")


demonstrate_http_methods()


# ============================================================================
# 13. REAL PATH OPERATION WITH ADVANCED VALIDATION
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.get("/numbers/{number}")
    def inspect_number(
        number: int,
    ) -> Dict[str, Any]:
        """Demonstrate derived values from a validated path parameter."""
        return {
            "number": number,
            "absolute": abs(number),
            "even": number % 2 == 0,
            "square": number * number,
        }


    @app.get("/math/{value}")
    def inspect_math(
        value: float,
    ) -> Dict[str, Any]:
        """Handle valid and invalid mathematical domains explicitly."""
        result: Dict[str, Any] = {
            "value": value,
            "square": value * value,
        }

        if value >= 0:
            result["square_root"] = math.sqrt(value)
        else:
            result["square_root"] = None

        return result


# ============================================================================
# 14. ROUTE ORDERING
# ============================================================================

def explain_route_ordering() -> None:
    print("\n--- Route ordering ---")
    print(
        """
Route specificity matters.

Consider:

    @app.get("/users/me")
    def current_user():
        ...

    @app.get("/users/{user_id}")
    def user(user_id: int):
        ...

A request for /users/me should reach the explicit /users/me route.

If a generic dynamic route is registered before a fixed route, routing systems
may consider the dynamic route first. Explicit routes should therefore be
placed carefully, particularly when static and parameterized paths overlap.
"""
    )


explain_route_ordering()


# ============================================================================
# 15. PATH OPERATION FUNCTION SIGNATURE
# ============================================================================

def explain_function_signature() -> None:
    print("\n--- Path operation function signature ---")
    print(
        """
FastAPI inspects the function signature.

Example concept:

    @app.get("/users/{user_id}")
    def get_user(
        user_id: int,
        include_orders: bool = False,
    ):
        ...

Here:
    user_id is inferred from the path because it appears in the path template.
    include_orders is inferred as a query parameter.
    int and bool annotations describe expected data types.
    Defaults affect whether parameters are required.

FastAPI uses type annotations as part of its API contract.
"""
    )


explain_function_signature()


# ============================================================================
# 16. STATUS CODES AND RESPONSE CONTROL
# ============================================================================

if FASTAPI_AVAILABLE:
    from fastapi import status

    @app.post("/status-example", status_code=status.HTTP_201_CREATED)
    def create_status_example() -> Dict[str, str]:
        return {"status": "created"}


    @app.get("/missing-resource/{resource_id}")
    def missing_resource(resource_id: int) -> Dict[str, Any]:
        if resource_id != 1:
            raise HTTPException(
                status_code=404,
                detail="Resource not found",
            )

        return {
            "resource_id": resource_id,
            "name": "Example",
        }


# ============================================================================
# 17. DEPENDENCY INJECTION
# ============================================================================

def explain_dependency_injection() -> None:
    print("\n--- Dependency injection ---")
    print(
        """
FastAPI supports dependency injection through Depends.

A dependency can provide reusable functionality such as:
    authentication context
    database sessions
    configuration
    pagination
    request-scoped services
    authorization checks

Conceptual example:

    def get_current_user():
        return {"id": 1}

    @app.get("/profile")
    def profile(user = Depends(get_current_user)):
        return user

The framework resolves the dependency before calling the endpoint.
"""
    )


explain_dependency_injection()


if FASTAPI_AVAILABLE:

    def get_application_context() -> Dict[str, str]:
        return {
            "service": "fastapi-introduction",
            "environment": "development",
        }


    @app.get("/context")
    def application_context(
        context: Dict[str, str] = Depends(get_application_context),
    ) -> Dict[str, Any]:
        return context


# ============================================================================
# 18. IN-MEMORY DATA STORE
# ============================================================================

products: Dict[int, Dict[str, Any]] = {
    1: {"id": 1, "name": "Keyboard", "price": 49.99},
    2: {"id": 2, "name": "Monitor", "price": 199.99},
}


def get_product_from_store(product_id: int) -> Dict[str, Any]:
    if product_id not in products:
        raise KeyError(f"Product {product_id} does not exist")

    return products[product_id]


if FASTAPI_AVAILABLE:

    @app.get("/store/products/{product_id}")
    def read_stored_product(product_id: int) -> Dict[str, Any]:
        try:
            return get_product_from_store(product_id)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )


# ============================================================================
# 19. CRUD PATH OPERATIONS
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.post("/store/products", status_code=201)
    def create_stored_product(product: Product) -> Dict[str, Any]:
        next_id = max(products.keys(), default=0) + 1

        record = {
            "id": next_id,
            **product.model_dump(),
        }

        products[next_id] = record
        return record


    @app.put("/store/products/{product_id}")
    def replace_stored_product(
        product_id: int,
        product: Product,
    ) -> Dict[str, Any]:
        if product_id not in products:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        record = {
            "id": product_id,
            **product.model_dump(),
        }

        products[product_id] = record
        return record


    @app.delete("/store/products/{product_id}", status_code=204)
    def remove_stored_product(product_id: int) -> None:
        if product_id not in products:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        del products[product_id]


# ============================================================================
# 20. ASYNC PATH OPERATIONS
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.get("/async-example")
    async def asynchronous_endpoint() -> Dict[str, Any]:
        """
        Async endpoints are appropriate when the operation performs
        non-blocking I/O through awaitable libraries.

        An async function should not call blocking operations directly on the
        event loop for significant durations.
        """
        return {
            "mode": "async",
            "message": "This endpoint is asynchronous",
        }


# ============================================================================
# 21. SYNCHRONOUS VERSUS ASYNCHRONOUS
# ============================================================================

def compare_sync_async() -> None:
    print("\n--- Synchronous versus asynchronous path operations ---")
    print(
        """
Synchronous:

    def endpoint():
        ...

Useful when:
    the implementation is simple or uses blocking libraries and the framework
    can execute the synchronous endpoint appropriately.

Asynchronous:

    async def endpoint():
        ...

Useful when:
    the endpoint performs non-blocking I/O with awaitable operations.

The important distinction is not that async automatically makes every program
faster. Async is primarily a concurrency model for efficiently handling
I/O-bound work when the underlying operations support non-blocking execution.
"""
    )


compare_sync_async()


# ============================================================================
# 22. OPENAPI AND AUTOMATIC DOCUMENTATION
# ============================================================================

def explain_openapi() -> None:
    print("\n--- OpenAPI and documentation ---")
    print(
        """
FastAPI can generate an OpenAPI schema from registered path operations,
function signatures, type annotations, request models, and response metadata.

Typical development endpoints are:

    /docs
    /redoc
    /openapi.json

The schema describes API operations in a machine-readable format.

This is useful for:
    API exploration
    client generation
    contract review
    testing
    documentation
"""
    )


explain_openapi()


# ============================================================================
# 23. INSPECT REGISTERED ROUTES
# ============================================================================

def show_real_routes() -> None:
    if app is None:
        print("\nFastAPI is not installed, so real route inspection is unavailable.")
        return

    print("\n--- Registered FastAPI routes ---")

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)

        if path is not None:
            print(
                f"path={path:<42} "
                f"methods={sorted(methods) if methods else []}"
            )


show_real_routes()


# ============================================================================
# 24. ROUTE METADATA
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.get(
        "/metadata-example",
        tags=["educational"],
        summary="Demonstrate route metadata",
        description="A path operation with OpenAPI metadata.",
        response_description="A JSON response containing a message.",
    )
    def metadata_example() -> Dict[str, str]:
        return {"message": "metadata registered"}


# ============================================================================
# 25. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n--- Important edge cases ---")

    cases = [
        "/users/42",
        "/users/abc",
        "/users/",
        "/users",
        "/users/42/orders",
        "/users/42?active=true",
    ]

    for value in cases:
        parsed = parse_request_url(value)
        print(f"{value:<30} -> path={parsed['path']!r}, query={parsed['query']}")


demonstrate_edge_cases()


# ============================================================================
# 26. VALIDATION EXAMPLES
# ============================================================================

def validate_positive_integer(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError("value must be an integer")

    if value <= 0:
        raise ValueError("value must be positive")

    return value


print("\n--- Validation examples ---")

for candidate in [1, 10, -1, 0]:
    try:
        print(candidate, "->", validate_positive_integer(candidate))
    except (TypeError, ValueError) as error:
        print(candidate, "-> error:", error)


# ============================================================================
# 27. PERFORMANCE CONSIDERATIONS
# ============================================================================

def benchmark_path_matching(iterations: int = 10_000) -> None:
    template = "/users/{user_id}/orders/{order_id}"
    actual = "/users/42/orders/900"

    start = time.perf_counter()

    for _ in range(iterations):
        match_path(template, actual)

    elapsed = time.perf_counter() - start

    print("\n--- Educational routing benchmark ---")
    print(f"Iterations: {iterations}")
    print(f"Elapsed:    {elapsed:.6f} seconds")

    print(
        """
This benchmark is only illustrative. It measures the tiny educational
regular-expression router, not FastAPI itself.

Production performance depends on:
    routing complexity
    serialization
    validation
    database latency
    network latency
    external APIs
    middleware
    application logic
    server configuration
"""
    )


benchmark_path_matching()


# ============================================================================
# 28. SECURITY CONSIDERATIONS
# ============================================================================

def explain_security() -> None:
    print("\n--- Security considerations ---")
    print(
        """
Path operations are part of an HTTP-facing system and should be treated as
untrusted input boundaries.

Important practices include:

    Validate path and query parameters.
    Validate request bodies.
    Authenticate protected endpoints.
    Authorize access to individual resources.
    Avoid exposing internal exception details.
    Apply appropriate rate limiting.
    Configure CORS intentionally.
    Use HTTPS in production.
    Keep secrets out of source code.
    Validate uploaded data where applicable.
    Use parameterized database queries.
    Avoid trusting client-provided ownership identifiers.

Validation answers:
    "Is this input structurally acceptable?"

Authorization answers:
    "Is this authenticated caller allowed to perform this operation?"

These are different security concerns.
"""
    )


explain_security()


# ============================================================================
# 29. COMMON MISTAKES
# ============================================================================

def print_common_mistakes() -> None:
    print("\n--- Common mistakes ---")

    mistakes = [
        (
            "Forgetting the leading slash",
            "Use @app.get('/users'), not an invalid route declaration."
        ),
        (
            "Path name mismatch",
            "If the route contains {user_id}, the function should receive user_id."
        ),
        (
            "Incorrect type assumptions",
            "Declare types that accurately describe accepted input."
        ),
        (
            "Blocking work inside async code",
            "Use non-blocking libraries or isolate blocking operations."
        ),
        (
            "Putting business logic everywhere",
            "Keep endpoints thin and move complex logic into service layers."
        ),
        (
            "Ignoring status codes",
            "Return HTTP status codes that communicate the operation result."
        ),
        (
            "Confusing authentication with authorization",
            "Identity and permission checks solve different problems."
        ),
        (
            "Using an in-memory store in production",
            "Use an appropriate persistent data store for durable data."
        ),
    ]

    for mistake, correction in mistakes:
        print(f"{mistake}: {correction}")


print_common_mistakes()


# ============================================================================
# 30. ARCHITECTURAL SEPARATION
# ============================================================================

class ProductRepository:
    """Repository layer: owns persistence-related operations."""

    def __init__(self) -> None:
        self._records: Dict[int, Dict[str, Any]] = {}

    def save(self, product_id: int, record: Dict[str, Any]) -> None:
        self._records[product_id] = record

    def find(self, product_id: int) -> Optional[Dict[str, Any]]:
        return self._records.get(product_id)


class ProductService:
    """Service layer: contains application/business logic."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def create(
        self,
        product_id: int,
        name: str,
        price: float,
    ) -> Dict[str, Any]:
        if not name.strip():
            raise ValueError("Product name cannot be empty")

        if price <= 0:
            raise ValueError("Product price must be positive")

        record = {
            "id": product_id,
            "name": name.strip(),
            "price": price,
        }

        self.repository.save(product_id, record)
        return record


repository = ProductRepository()
service = ProductService(repository)

print("\n--- Layered architecture example ---")
print(service.create(101, "Mechanical Keyboard", 129.99))


# ============================================================================
# 31. PRODUCTION-STYLE ENDPOINT STRUCTURE
# ============================================================================

def explain_production_structure() -> None:
    print("\n--- Production-oriented structure ---")
    print(
        """
A larger FastAPI service can separate responsibilities:

    app/
        main.py
        routers/
            users.py
            products.py
            orders.py
        schemas/
            users.py
            products.py
        services/
            users.py
            products.py
        repositories/
            users.py
            products.py
        dependencies/
            auth.py
            database.py
        models/
            users.py
            products.py
        tests/
            test_users.py
            test_products.py

The exact structure depends on application size and team conventions.

The important architectural idea is separation of concerns:
routing should connect HTTP requests to application behavior without becoming
the entire application.
"""
    )


explain_production_structure()


# ============================================================================
# 32. TESTING CONCEPTS
# ============================================================================

def test_path_matching() -> None:
    assert match_path("/users/{user_id}", "/users/42") == {"user_id": "42"}
    assert match_path("/users/{user_id}", "/products/42") is None
    assert match_path(
        "/orders/{order_id}/items/{item_id}",
        "/orders/8/items/9",
    ) == {
        "order_id": "8",
        "item_id": "9",
    }


def test_positive_integer_validation() -> None:
    assert validate_positive_integer(5) == 5

    try:
        validate_positive_integer(0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def run_tests() -> None:
    print("\n--- Built-in study tests ---")
    tests = [
        test_path_matching,
        test_positive_integer_validation,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")


run_tests()


# ============================================================================
# 33. CONCEPTUAL COMPARISON
# ============================================================================

def comparison_table() -> None:
    print("\n--- Related concepts ---")

    rows = [
        ("Application", "FastAPI()", "Central ASGI application object"),
        ("Route", "/users/{id}", "URL pattern registered with an endpoint"),
        ("Decorator", "@app.get(...)", "Registers/configures a path operation"),
        ("Path operation", "GET /users", "HTTP method + path + endpoint"),
        ("Path parameter", "{id}", "Variable embedded in the URL path"),
        ("Query parameter", "?limit=10", "Optional request modifiers"),
        ("Body model", "BaseModel", "Structured request data"),
        ("Dependency", "Depends(...)", "Reusable injected functionality"),
        ("ASGI server", "Uvicorn", "Runs the application and handles protocol I/O"),
        ("OpenAPI", "/openapi.json", "Machine-readable API description"),
    ]

    for concept, example, purpose in rows:
        print(f"{concept:<20} {example:<24} {purpose}")


comparison_table()


# ============================================================================
# 34. MINI APPLICATION SIMULATION
# ============================================================================

@dataclass
class SimulatedRequest:
    method: str
    path: str
    query: Dict[str, str]
    body: Optional[Dict[str, Any]] = None


@dataclass
class SimulatedResponse:
    status_code: int
    body: Dict[str, Any]


class ApplicationSimulator:
    """
    A compact educational model of an application instance.

    It demonstrates the relationship between route registration and request
    dispatch without depending on an actual HTTP server.
    """

    def __init__(self) -> None:
        self.routes: List[Dict[str, Any]] = []

    def add_route(
        self,
        method: str,
        path: str,
        endpoint: Callable[..., Dict[str, Any]],
    ) -> None:
        self.routes.append(
            {
                "method": method.upper(),
                "path": path,
                "endpoint": endpoint,
            }
        )

    def dispatch(self, request: SimulatedRequest) -> SimulatedResponse:
        for route in self.routes:
            if route["method"] != request.method.upper():
                continue

            parameters = match_path(route["path"], request.path)

            if parameters is None:
                continue

            endpoint = route["endpoint"]

            try:
                result = endpoint(**parameters)
                return SimulatedResponse(200, result)
            except Exception as error:
                return SimulatedResponse(
                    500,
                    {"detail": str(error)},
                )

        return SimulatedResponse(
            404,
            {"detail": "Route not found"},
        )


simulated_app = ApplicationSimulator()


def simulated_user(user_id: str) -> Dict[str, Any]:
    converted_id = convert_path_parameter(user_id, int)

    if converted_id <= 0:
        raise ValueError("user_id must be positive")

    return {
        "id": converted_id,
        "name": "Example User",
    }


simulated_app.add_route(
    "GET",
    "/users/{user_id}",
    simulated_user,
)

print("\n--- Application dispatch simulation ---")

for request in [
    SimulatedRequest("GET", "/users/25", {}),
    SimulatedRequest("GET", "/users/abc", {}),
    SimulatedRequest("POST", "/users/25", {}),
    SimulatedRequest("GET", "/missing", {}),
]:
    response = simulated_app.dispatch(request)
    print(request, "=>", response)


# ============================================================================
# 35. ADVANCED ROUTING OBSERVATIONS
# ============================================================================

def explain_advanced_routing() -> None:
    print("\n--- Advanced routing observations ---")
    print(
        """
Important routing topics in larger applications include:

    Static paths:
        /users/me

    Dynamic paths:
        /users/{user_id}

    Nested paths:
        /users/{user_id}/orders/{order_id}

    Router grouping:
        APIRouter can organize related path operations.

    Prefixes:
        A router can be mounted under a common prefix.

    Tags:
        Related operations can be grouped in generated documentation.

    Dependencies:
        Shared authorization, database, or request context can be attached
        to routers or individual operations.

    Response models:
        Output schemas can explicitly control and document responses.

    Exception handlers:
        Applications can translate exceptions into consistent HTTP responses.
"""
    )


explain_advanced_routing()


# ============================================================================
# 36. APIRouter EXAMPLE
# ============================================================================

if FASTAPI_AVAILABLE:
    from fastapi import APIRouter

    product_router = APIRouter(
        prefix="/api/products",
        tags=["products"],
    )


    @product_router.get("/{product_id}")
    def router_product(product_id: int) -> Dict[str, Any]:
        return {
            "product_id": product_id,
            "source": "APIRouter",
        }


    app.include_router(product_router)


# ============================================================================
# 37. RESPONSE MODELS
# ============================================================================

if FASTAPI_AVAILABLE:

    class ProductResponse(BaseModel):
        id: int
        name: str
        price: float


    @app.get(
        "/response-model-example/{product_id}",
        response_model=ProductResponse,
    )
    def response_model_example(product_id: int) -> ProductResponse:
        return ProductResponse(
            id=product_id,
            name="Example Product",
            price=10.50,
        )


# ============================================================================
# 38. OPTIONAL QUERY VALIDATION
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.get("/validated-search")
    def validated_search(
        q: str = Query(min_length=2, max_length=50),
        limit: int = Query(default=10, ge=1, le=100),
    ) -> Dict[str, Any]:
        return {
            "query": q,
            "limit": limit,
        }


# ============================================================================
# 39. OPTIONAL PATH VALIDATION
# ============================================================================

if FASTAPI_AVAILABLE:

    @app.get("/validated-products/{product_id}")
    def validated_product(
        product_id: int = Path(ge=1),
    ) -> Dict[str, int]:
        return {"product_id": product_id}


# ============================================================================
# 40. FINAL STUDY CHECKLIST
# ============================================================================

def study_checklist() -> None:
    print("\n--- Study checklist ---")

    concepts = [
        "Understand HTTP methods and URL paths.",
        "Understand that FastAPI() creates the application instance.",
        "Understand decorator-based route registration.",
        "Distinguish routes from path operation functions.",
        "Understand path parameters.",
        "Understand query parameters.",
        "Understand request bodies and Pydantic models.",
        "Understand type-driven validation.",
        "Understand status codes and HTTP errors.",
        "Understand dependency injection.",
        "Understand APIRouter.",
        "Understand OpenAPI and automatic documentation.",
        "Understand synchronous and asynchronous endpoints.",
        "Understand route ordering and specificity.",
        "Separate routing from business and persistence logic.",
        "Validate untrusted input.",
        "Test both successful and failing requests.",
        "Consider performance, security, and deployment constraints.",
    ]

    for index, concept in enumerate(concepts, start=1):
        print(f"{index:02d}. {concept}")


study_checklist()


print("\n" + "=" * 78)
print("Study script completed.")
print("=" * 78)

if not FASTAPI_AVAILABLE:
    print(
        "\nTo execute the actual FastAPI application, install FastAPI and "
        "Uvicorn with: pip install fastapi uvicorn"
    )
