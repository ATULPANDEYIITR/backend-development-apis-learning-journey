"""
FastAPI Routing: GET, POST, PUT, PATCH, DELETE, and Route Parameters

A self-contained study program demonstrating FastAPI routing from beginner
through advanced concepts.

Run:
    pip install fastapi uvicorn
    python fastapi_routing.py

Then open:
    http://127.0.0.1:8000
    http://127.0.0.1:8000/docs
    http://127.0.0.1:8000/redoc
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# 1. APPLICATION CREATION
# ============================================================================

app = FastAPI(
    title="FastAPI Routing Laboratory",
    description=(
        "A comprehensive demonstration of FastAPI HTTP routing, route "
        "parameters, request validation, status codes, and CRUD operations."
    ),
    version="1.0.0",
)


# ============================================================================
# 2. BASIC ROUTING
# ============================================================================

@app.get("/")
def root() -> dict[str, str]:
    """A simple GET route."""
    return {
        "message": "FastAPI routing laboratory",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    """A common production-style health endpoint."""
    return {"status": "healthy"}


# ============================================================================
# 3. ROUTE PARAMETERS
# ============================================================================

@app.get("/users/{user_id}")
def get_user(user_id: int) -> dict[str, Any]:
    """
    Demonstrates a required path parameter.

    FastAPI converts the textual URL segment into an integer because the
    function annotation says user_id: int.
    """
    return {
        "user_id": user_id,
        "message": f"Requested user {user_id}",
    }


@app.get("/products/{product_id}")
def get_product(
    product_id: int = Path(
        ...,
        ge=1,
        description="Positive numeric product identifier",
    ),
) -> dict[str, Any]:
    """
    Path validation prevents invalid identifiers such as zero or negatives.
    """
    return {
        "product_id": product_id,
        "message": "Product identifier is valid",
    }


@app.get("/articles/{slug}")
def get_article(slug: str) -> dict[str, str]:
    """String route parameters can represent slugs or resource names."""
    return {
        "slug": slug,
        "normalized_slug": slug.lower(),
    }


# ============================================================================
# 4. ROUTE PARAMETERS AND QUERY PARAMETERS
# ============================================================================

@app.get("/search")
def search_products(
    q: str = Query(..., min_length=2, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    """
    Query parameters are different from route parameters.

    Example:
        /search?q=laptop&page=2&page_size=20
    """
    return {
        "query": q,
        "page": page,
        "page_size": page_size,
    }


@app.get("/users")
def list_users(
    active: bool | None = Query(
        None,
        description="Optional active-status filter",
    ),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Demonstrates optional query parameters and bounded pagination.
    """
    return {
        "active": active,
        "limit": limit,
        "message": "User collection endpoint",
    }


# ============================================================================
# 5. PYDANTIC REQUEST MODELS
# ============================================================================

class UserCreate(BaseModel):
    """Request body for creating a user."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=200)
    age: int = Field(..., ge=13, le=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    """Request body for a complete PUT replacement."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=200)
    age: int = Field(..., ge=13, le=120)


class UserPatch(BaseModel):
    """
    Request body for a partial PATCH update.

    Every field is optional because PATCH changes only the supplied fields.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=2, max_length=100)
    email: str | None = Field(None, min_length=5, max_length=200)
    age: int | None = Field(None, ge=13, le=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class ProductCreate(BaseModel):
    """Request model for a product."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)
    price: float = Field(..., gt=0)
    category: str = Field(..., min_length=2, max_length=50)


# ============================================================================
# 6. IN-MEMORY DATA STORE
# ============================================================================

@dataclass
class UserRecord:
    """Internal representation of a user."""

    id: int
    name: str
    email: str
    age: int


users: dict[int, UserRecord] = {
    1: UserRecord(1, "Ada Lovelace", "ada@example.com", 28),
    2: UserRecord(2, "Alan Turing", "alan@example.com", 32),
}

next_user_id = 3


def serialize_user(user: UserRecord) -> dict[str, Any]:
    """Convert a dataclass object into a JSON-compatible dictionary."""
    return asdict(user)


def find_user_or_404(user_id: int) -> UserRecord:
    """Centralized resource lookup."""
    user = users.get(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} was not found",
        )

    return user


# ============================================================================
# 7. POST: CREATE A RESOURCE
# ============================================================================

@app.post(
    "/api/users",
    status_code=status.HTTP_201_CREATED,
)
def create_user(payload: UserCreate) -> dict[str, Any]:
    """
    POST normally creates a new resource.

    The request body is parsed and validated by Pydantic.
    """
    global next_user_id

    for existing_user in users.values():
        if existing_user.email == payload.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

    user = UserRecord(
        id=next_user_id,
        name=payload.name,
        email=payload.email,
        age=payload.age,
    )

    users[next_user_id] = user
    next_user_id += 1

    return {
        "message": "User created",
        "user": serialize_user(user),
    }


# ============================================================================
# 8. GET: READ A COLLECTION
# ============================================================================

@app.get("/api/users")
def list_all_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    GET collection endpoint.

    offset and limit provide simple pagination.
    """
    records = list(users.values())
    selected = records[offset : offset + limit]

    return {
        "count": len(selected),
        "total": len(records),
        "offset": offset,
        "limit": limit,
        "items": [serialize_user(user) for user in selected],
    }


# ============================================================================
# 9. GET: READ A SINGLE RESOURCE
# ============================================================================

@app.get("/api/users/{user_id}")
def read_user(user_id: int) -> dict[str, Any]:
    """Retrieve one resource using a path parameter."""
    user = find_user_or_404(user_id)

    return {
        "user": serialize_user(user),
    }


# ============================================================================
# 10. PUT: COMPLETE REPLACEMENT
# ============================================================================

@app.put("/api/users/{user_id}")
def replace_user(
    user_id: int,
    payload: UserUpdate,
) -> dict[str, Any]:
    """
    PUT represents replacement of the resource representation.

    The complete UserUpdate model is required.
    """
    existing_user = find_user_or_404(user_id)

    if (
        payload.email != existing_user.email
        and any(
            user.email == payload.email and user.id != user_id
            for user in users.values()
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another user already uses this email",
        )

    replaced_user = UserRecord(
        id=existing_user.id,
        name=payload.name,
        email=payload.email.lower(),
        age=payload.age,
    )

    users[user_id] = replaced_user

    return {
        "message": "User replaced",
        "user": serialize_user(replaced_user),
    }


# ============================================================================
# 11. PATCH: PARTIAL UPDATE
# ============================================================================

@app.patch("/api/users/{user_id}")
def patch_user(
    user_id: int,
    payload: UserPatch,
) -> dict[str, Any]:
    """
    PATCH changes only the fields supplied by the client.

    model_dump(exclude_unset=True) is important: it distinguishes an omitted
    field from a field explicitly provided in the request.
    """
    existing_user = find_user_or_404(user_id)

    changes = payload.model_dump(exclude_unset=True)

    if "email" in changes:
        new_email = changes["email"]

        if new_email != existing_user.email and any(
            user.email == new_email and user.id != user_id
            for user in users.values()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another user already uses this email",
            )

    updated_user = UserRecord(
        id=existing_user.id,
        name=changes.get("name", existing_user.name),
        email=changes.get("email", existing_user.email),
        age=changes.get("age", existing_user.age),
    )

    users[user_id] = updated_user

    return {
        "message": "User partially updated",
        "changed_fields": list(changes.keys()),
        "user": serialize_user(updated_user),
    }


# ============================================================================
# 12. DELETE: REMOVE A RESOURCE
# ============================================================================

@app.delete(
    "/api/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user(user_id: int) -> Response:
    """
    DELETE removes a resource.

    A 204 response intentionally contains no response body.
    """
    find_user_or_404(user_id)
    del users[user_id]

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# 13. ROUTE ORDER AND STATIC PATHS
# ============================================================================

@app.get("/reports/latest")
def latest_report() -> dict[str, str]:
    """
    Static route.

    Defining explicit static routes separately helps avoid ambiguous route
    matching when dynamic parameters are also present.
    """
    return {"report": "latest"}


@app.get("/reports/{report_id}")
def report_by_id(report_id: int) -> dict[str, Any]:
    """Dynamic report route."""
    return {
        "report_id": report_id,
        "message": "Report selected by numeric identifier",
    }


# ============================================================================
# 14. ENUM-LIKE VALIDATION
# ============================================================================

@app.get("/orders/{order_id}")
def get_order(
    order_id: int = Path(..., ge=1),
    status_filter: Literal["pending", "paid", "cancelled"] | None = Query(
        None,
        alias="status",
    ),
) -> dict[str, Any]:
    """
    Literal restricts the query parameter to a known set of values.
    """
    return {
        "order_id": order_id,
        "status": status_filter,
    }


# ============================================================================
# 15. NESTED RESOURCE ROUTING
# ============================================================================

@app.get("/users/{user_id}/orders")
def list_user_orders(user_id: int) -> dict[str, Any]:
    """
    Nested routes express a relationship between resources.

    This example does not require a database, so it returns illustrative
    order records based on the requested user.
    """
    find_user_or_404(user_id)

    return {
        "user_id": user_id,
        "orders": [
            {
                "id": f"{user_id}-1001",
                "amount": 149.99,
            },
            {
                "id": f"{user_id}-1002",
                "amount": 79.50,
            },
        ],
    }


# ============================================================================
# 16. PRODUCT CRUD
# ============================================================================

products: dict[int, dict[str, Any]] = {
    1: {"id": 1, "name": "Keyboard", "price": 49.99, "category": "hardware"},
    2: {"id": 2, "name": "Monitor", "price": 299.99, "category": "hardware"},
}

next_product_id = 3


@app.post("/api/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate) -> dict[str, Any]:
    """Create a product."""
    global next_product_id

    product = {
        "id": next_product_id,
        "name": payload.name,
        "price": payload.price,
        "category": payload.category,
    }

    products[next_product_id] = product
    next_product_id += 1

    return product


@app.get("/api/products/{product_id}")
def read_product(product_id: int) -> dict[str, Any]:
    """Read a product."""
    product = products.get(product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return product


# ============================================================================
# 17. CUSTOM VALIDATION ERROR HANDLER
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    FastAPI automatically returns validation errors.

    This handler demonstrates how an application can standardize its error
    response format while preserving useful validation details.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "validation_error",
            "path": str(request.url.path),
            "method": request.method,
            "details": exc.errors(),
        },
    )


# ============================================================================
# 18. ROUTING CONCEPTS AS PURE PYTHON
# ============================================================================

def classify_http_method(method: str) -> str:
    """
    A language-level model of common HTTP method semantics.

    This function does not perform HTTP routing itself. It helps separate
    application concepts from FastAPI's routing machinery.
    """
    normalized = method.upper()

    meanings = {
        "GET": "retrieve a representation",
        "POST": "create or trigger an operation",
        "PUT": "replace a representation",
        "PATCH": "partially modify a representation",
        "DELETE": "remove a representation",
    }

    return meanings.get(normalized, "method not covered by this laboratory")


def demonstrate_method_semantics() -> None:
    """Print a compact conceptual reference."""
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    print("\nHTTP method semantics:")
    for method in methods:
        print(f"  {method:<7} -> {classify_http_method(method)}")


# ============================================================================
# 19. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    """Show validation-oriented edge cases without starting a server."""
    examples = [
        "",
        "   ",
        "user@example.com",
        "USER@EXAMPLE.COM",
    ]

    print("\nNormalization examples:")
    for value in examples:
        print(f"  {value!r} -> {value.strip().lower()!r}")

    print("\nImportant routing edge cases:")
    print("  /users/12       -> integer route parameter")
    print("  /users/abc      -> validation error for an integer parameter")
    print("  /api/users/999  -> resource lookup can return 404")
    print("  /search?q=x     -> query validation can reject too-short values")
    print("  /api/users      -> collection endpoint")
    print("  /api/users/1    -> item endpoint")


# ============================================================================
# 20. TESTABLE BUSINESS LOGIC
# ============================================================================

def apply_patch(
    original: dict[str, Any],
    changes: dict[str, Any],
) -> dict[str, Any]:
    """
    Generic partial-update helper.

    Keeping transformation logic separate from the HTTP layer makes it easier
    to unit-test independently.
    """
    result = original.copy()

    for field_name, value in changes.items():
        if field_name not in original:
            raise KeyError(f"Unknown field: {field_name}")

        result[field_name] = value

    return result


def demonstrate_patch_logic() -> None:
    original = {
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "age": 40,
    }

    changes = {
        "age": 41,
    }

    print("\nPartial update:")
    print("  Before:", original)
    print("  Changes:", changes)
    print("  After:", apply_patch(original, changes))


# ============================================================================
# 21. BASIC UNIT-STYLE ASSERTIONS
# ============================================================================

def run_local_checks() -> None:
    """Small dependency-free checks for core concepts."""
    assert classify_http_method("GET").startswith("retrieve")
    assert classify_http_method("post").startswith("create")
    assert classify_http_method("PUT").startswith("replace")
    assert classify_http_method("PATCH").startswith("partially")
    assert classify_http_method("DELETE").startswith("remove")

    original = {"name": "Ada", "age": 30}
    updated = apply_patch(original, {"age": 31})

    assert updated["name"] == "Ada"
    assert updated["age"] == 31
    assert original["age"] == 30

    try:
        apply_patch(original, {"unknown": "value"})
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown fields should be rejected")

    print("\nLocal checks: PASSED")


# ============================================================================
# 22. PRODUCTION DESIGN NOTES
# ============================================================================

def print_production_considerations() -> None:
    """Print concise engineering considerations."""
    considerations = [
        "Use routers to split large APIs into maintainable modules.",
        "Use request/response models to define explicit API contracts.",
        "Use appropriate HTTP status codes.",
        "Validate path, query, header, cookie, and body inputs.",
        "Keep business logic separate from route handlers.",
        "Use a database instead of in-memory dictionaries for persistence.",
        "Use authentication and authorization for protected resources.",
        "Avoid leaking internal exception details to clients.",
        "Add structured logging, metrics, tracing, and automated tests.",
        "Consider idempotency, concurrency, transactions, and race conditions.",
    ]

    print("\nProduction considerations:")
    for item in considerations:
        print(f"  - {item}")


# ============================================================================
# 23. MAIN ENTRY POINT
# ============================================================================

def main() -> None:
    """
    The script can be executed directly for a study-mode demonstration.

    To run the actual FastAPI server, use:
        uvicorn fastapi_routing:app --reload
    """
    print("=" * 72)
    print("FASTAPI ROUTING LABORATORY")
    print("=" * 72)

    demonstrate_method_semantics()
    demonstrate_edge_cases()
    demonstrate_patch_logic()
    run_local_checks()
    print_production_considerations()

    print("\nAvailable API routes:")
    for route in app.routes:
        methods = ", ".join(sorted(route.methods or []))
        print(f"  {methods:<18} {route.path}")

    print("\nServer command:")
    print("  uvicorn fastapi_routing:app --reload")

    print("\nInteractive documentation:")
    print("  http://127.0.0.1:8000/docs")


if __name__ == "__main__":
    main()
