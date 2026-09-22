"""
FastAPI + Pydantic Response Models
===================================

A comprehensive executable study file covering:

- Response models
- Pydantic models
- FastAPI response_model
- Response validation
- Serialization
- Deserialization
- Field exclusion
- exclude_unset
- exclude_defaults
- exclude_none
- Nested response models
- Lists and generic-style responses
- ORM/object conversion with from_attributes
- Computed fields
- Field serializers
- Aliases
- Sensitive-field protection
- Response-model filtering
- Error handling
- Validation failures
- Testing
- Performance considerations
- Production-oriented design

Dependencies:
    pip install fastapi pydantic uvicorn

Run the API:
    python response_models_fastapi.py server

Run the educational demonstrations:
    python response_models_fastapi.py demo

Open API documentation after starting the server:
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationError,
    computed_field,
    field_serializer,
    model_validator,
)


# ============================================================================
# 1. BASIC PYDANTIC MODELS
# ============================================================================

class UserInternal(BaseModel):
    """
    Internal representation of a user.

    This model deliberately contains information that should NOT necessarily
    be returned to an API consumer.
    """

    id: int
    username: str
    email: EmailStr
    password_hash: str
    is_admin: bool = False
    created_at: datetime


class UserResponse(BaseModel):
    """
    Public response representation.

    Notice that password_hash does not exist here.

    This is safer than creating an internal model and attempting to remember
    manually which fields must be removed every time a response is returned.
    """

    id: int
    username: str
    email: EmailStr
    is_admin: bool
    created_at: datetime


# ============================================================================
# 2. RESPONSE MODEL WITH OPTIONAL FIELDS
# ============================================================================

class UserProfileResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


# ============================================================================
# 3. NESTED RESPONSE MODELS
# ============================================================================

class AddressResponse(BaseModel):
    street: str
    city: str
    state: str
    postal_code: str


class CustomerResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    address: AddressResponse


# ============================================================================
# 4. PRODUCT RESPONSE MODEL
# ============================================================================

class ProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    currency: str = "INR"
    stock_quantity: int = Field(ge=0)

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> str:
        """
        Decimal is converted into a JSON-safe string.

        This is useful when exact monetary representation matters.
        """
        return f"{value:.2f}"


# ============================================================================
# 5. COMPUTED FIELDS
# ============================================================================

class ProductWithStatusResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    stock_quantity: int

    @computed_field
    @property
    def availability(self) -> str:
        if self.stock_quantity == 0:
            return "out_of_stock"
        if self.stock_quantity < 10:
            return "low_stock"
        return "available"

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> str:
        return f"{value:.2f}"


# ============================================================================
# 6. ALIASES
# ============================================================================

class CustomerPublicResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    customer_id: int = Field(serialization_alias="customerId")
    full_name: str = Field(serialization_alias="fullName")
    email: EmailStr


# ============================================================================
# 7. ORM-STYLE OBJECT CONVERSION
# ============================================================================

class DatabaseUser:
    """
    Simple class representing an object returned by a database layer.

    It is intentionally not a Pydantic model.
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        email: str,
        is_admin: bool,
    ) -> None:
        self.id = user_id
        self.username = username
        self.email = email
        self.is_admin = is_admin


class ORMUserResponse(BaseModel):
    """
    from_attributes=True allows Pydantic to build this model from an object
    with matching attributes.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_admin: bool


# ============================================================================
# 8. RESPONSE WRAPPER
# ============================================================================

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T


class PaginationMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class PaginatedUsersResponse(BaseModel):
    items: list[UserResponse]
    meta: PaginationMeta


# ============================================================================
# 9. VALIDATED RESPONSE MODEL
# ============================================================================

class TransactionResponse(BaseModel):
    id: int
    amount: Decimal
    currency: str
    status: str

    @model_validator(mode="after")
    def validate_business_state(self) -> "TransactionResponse":
        """
        Response validation can catch impossible states before data reaches
        the client.

        A real application might have more sophisticated state rules.
        """
        valid_statuses = {"pending", "completed", "failed", "refunded"}

        if self.status not in valid_statuses:
            raise ValueError(f"Invalid transaction status: {self.status}")

        if self.amount < 0:
            raise ValueError("Transaction amount cannot be negative")

        return self

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return f"{value:.2f}"


# ============================================================================
# 10. FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Response Models and Serialization Study API",
    version="1.0.0",
    description=(
        "Educational API demonstrating FastAPI response models, "
        "Pydantic serialization, validation, and field exclusion."
    ),
)


# ============================================================================
# 11. SAMPLE INTERNAL DATA
# ============================================================================

INTERNAL_USERS = [
    UserInternal(
        id=1,
        username="atul",
        email="atul@example.com",
        password_hash="secret-hash-001",
        is_admin=True,
        created_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
    ),
    UserInternal(
        id=2,
        username="student",
        email="student@example.com",
        password_hash="secret-hash-002",
        is_admin=False,
        created_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
    ),
]

PROFILE = UserProfileResponse(
    id=1,
    username="atul",
    display_name="Atul Pandey",
)

PRODUCTS = [
    ProductResponse(
        id=101,
        name="Engineering Laptop",
        price=Decimal("84999.90"),
        stock_quantity=7,
    ),
    ProductResponse(
        id=102,
        name="USB Cable",
        price=Decimal("499.00"),
        stock_quantity=0,
    ),
]


# ============================================================================
# 12. BASIC RESPONSE_MODEL
# ============================================================================

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int) -> UserInternal:
    """
    FastAPI validates and serializes the returned object according to
    UserResponse.

    password_hash exists in the internal object but is absent from the
    declared response model.

    This demonstrates why response_model is important for API boundaries.
    """
    for user in INTERNAL_USERS:
        if user.id == user_id:
            return user

    raise HTTPException(status_code=404, detail="User not found")


# ============================================================================
# 13. RESPONSE MODEL WITH EXCLUDE_NONE
# ============================================================================

@app.get(
    "/profiles/{user_id}",
    response_model=UserProfileResponse,
    response_model_exclude_none=True,
)
def get_profile(user_id: int) -> UserProfileResponse:
    """
    None-valued optional fields are removed from the serialized response.
    """
    if user_id != PROFILE.id:
        raise HTTPException(status_code=404, detail="Profile not found")

    return PROFILE


# ============================================================================
# 14. NESTED RESPONSE
# ============================================================================

@app.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int) -> CustomerResponse:
    if customer_id != 1:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(
        id=1,
        name="Example Customer",
        email="customer@example.com",
        address=AddressResponse(
            street="10 Knowledge Road",
            city="Lucknow",
            state="Uttar Pradesh",
            postal_code="226001",
        ),
    )


# ============================================================================
# 15. PRODUCT SERIALIZATION
# ============================================================================

@app.get("/products", response_model=list[ProductResponse])
def get_products() -> list[ProductResponse]:
    """
    Returning a list of Pydantic response models.

    The Decimal serializer converts prices to strings.
    """
    return PRODUCTS


# ============================================================================
# 16. COMPUTED FIELD
# ============================================================================

@app.get(
    "/products/status",
    response_model=list[ProductWithStatusResponse],
)
def get_products_with_status() -> list[ProductWithStatusResponse]:
    return [
        ProductWithStatusResponse(
            id=product.id,
            name=product.name,
            price=product.price,
            stock_quantity=product.stock_quantity,
        )
        for product in PRODUCTS
    ]


# ============================================================================
# 17. ALIAS SERIALIZATION
# ============================================================================

@app.get(
    "/customers-public/{customer_id}",
    response_model=CustomerPublicResponse,
)
def get_public_customer(customer_id: int) -> CustomerPublicResponse:
    if customer_id != 1:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerPublicResponse(
        customer_id=1,
        full_name="Example Customer",
        email="customer@example.com",
    )


# ============================================================================
# 18. ORM-STYLE OBJECT
# ============================================================================

@app.get("/orm-users/{user_id}", response_model=ORMUserResponse)
def get_orm_user(user_id: int) -> ORMUserResponse:
    if user_id != 1:
        raise HTTPException(status_code=404, detail="User not found")

    database_object = DatabaseUser(
        user_id=1,
        username="database-user",
        email="database@example.com",
        is_admin=False,
    )

    return ORMUserResponse.model_validate(database_object)


# ============================================================================
# 19. GENERIC-STYLE API RESPONSE
# ============================================================================

@app.get(
    "/api/users",
    response_model=ApiResponse[list[UserResponse]],
)
def get_api_users() -> ApiResponse[list[UserResponse]]:
    public_users = [
        UserResponse.model_validate(user.model_dump())
        for user in INTERNAL_USERS
    ]

    return ApiResponse(
        success=True,
        message="Users retrieved successfully",
        data=public_users,
    )


# ============================================================================
# 20. PAGINATED RESPONSE
# ============================================================================

@app.get(
    "/users",
    response_model=PaginatedUsersResponse,
)
def list_users(
    page: int = 1,
    page_size: int = 10,
) -> PaginatedUsersResponse:
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")

    if not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=400,
            detail="page_size must be between 1 and 100",
        )

    start = (page - 1) * page_size
    end = start + page_size

    public_users = [
        UserResponse.model_validate(user.model_dump())
        for user in INTERNAL_USERS[start:end]
    ]

    return PaginatedUsersResponse(
        items=public_users,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=len(INTERNAL_USERS),
        ),
    )


# ============================================================================
# 21. TRANSACTION RESPONSE
# ============================================================================

@app.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
)
def get_transaction(transaction_id: int) -> TransactionResponse:
    if transaction_id != 1:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    return TransactionResponse(
        id=1,
        amount=Decimal("1250.50"),
        currency="INR",
        status="completed",
    )


# ============================================================================
# 22. DEMONSTRATING MODEL_SERIALIZATION
# ============================================================================

def demonstrate_serialization() -> None:
    print("\n=== Pydantic Serialization ===")

    user = UserInternal(
        id=50,
        username="serialization_user",
        email="serialization@example.com",
        password_hash="private-value",
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )

    print("\nPython object:")
    print(user)

    print("\nmodel_dump():")
    print(user.model_dump())

    print("\nmodel_dump_json():")
    print(user.model_dump_json())

    print("\nPublic response model:")
    public_user = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
    print(public_user.model_dump())


# ============================================================================
# 23. FIELD EXCLUSION
# ============================================================================

def demonstrate_exclusion() -> None:
    print("\n=== Field Exclusion ===")

    user = UserInternal(
        id=99,
        username="excluded_user",
        email="excluded@example.com",
        password_hash="must-not-leak",
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )

    print("\nOriginal:")
    print(user.model_dump())

    print("\nExclude password_hash:")
    print(user.model_dump(exclude={"password_hash"}))

    print("\nExclude multiple fields:")
    print(
        user.model_dump(
            exclude={
                "password_hash",
                "is_admin",
            }
        )
    )


# ============================================================================
# 24. EXCLUDE_NONE
# ============================================================================

def demonstrate_exclude_none() -> None:
    print("\n=== exclude_none ===")

    profile = UserProfileResponse(
        id=10,
        username="minimal",
        display_name=None,
        bio=None,
        avatar_url="https://example.com/avatar.png",
    )

    print("\nWithout exclusion:")
    print(profile.model_dump())

    print("\nWith exclude_none=True:")
    print(profile.model_dump(exclude_none=True))


# ============================================================================
# 25. EXCLUDE_DEFAULTS
# ============================================================================

def demonstrate_exclude_defaults() -> None:
    print("\n=== exclude_defaults ===")

    product = ProductResponse(
        id=1,
        name="Default Currency Product",
        price=Decimal("100.00"),
        stock_quantity=20,
    )

    print("\nNormal:")
    print(product.model_dump())

    print("\nexclude_defaults=True:")
    print(product.model_dump(exclude_defaults=True))


# ============================================================================
# 26. EXCLUDE_UNSET
# ============================================================================

class UpdateUserResponse(BaseModel):
    username: str | None = None
    display_name: str | None = None
    email: EmailStr | None = None


def demonstrate_exclude_unset() -> None:
    print("\n=== exclude_unset ===")

    update = UpdateUserResponse(username="new_name")

    print("\nAll model fields:")
    print(update.model_dump())

    print("\nOnly explicitly supplied fields:")
    print(update.model_dump(exclude_unset=True))


# ============================================================================
# 27. NESTED FIELD EXCLUSION
# ============================================================================

def demonstrate_nested_exclusion() -> None:
    print("\n=== Nested Field Exclusion ===")

    customer = CustomerResponse(
        id=1,
        name="Nested Customer",
        email="nested@example.com",
        address=AddressResponse(
            street="Example Street",
            city="Lucknow",
            state="Uttar Pradesh",
            postal_code="226001",
        ),
    )

    result = customer.model_dump(
        exclude={
            "address": {
                "postal_code",
            }
        }
    )

    print(result)


# ============================================================================
# 28. RESPONSE VALIDATION
# ============================================================================

def demonstrate_response_validation() -> None:
    print("\n=== Response Validation ===")

    valid_data = {
        "id": 10,
        "amount": "500.25",
        "currency": "INR",
        "status": "completed",
    }

    valid_transaction = TransactionResponse.model_validate(valid_data)
    print("\nValid response:")
    print(valid_transaction.model_dump())

    invalid_data = {
        "id": 11,
        "amount": "-500",
        "currency": "INR",
        "status": "unknown",
    }

    try:
        TransactionResponse.model_validate(invalid_data)
    except ValidationError as exc:
        print("\nInvalid response rejected:")
        print(exc)


# ============================================================================
# 29. ORM ATTRIBUTE CONVERSION
# ============================================================================

def demonstrate_from_attributes() -> None:
    print("\n=== from_attributes ===")

    database_user = DatabaseUser(
        user_id=500,
        username="orm_example",
        email="orm@example.com",
        is_admin=False,
    )

    response = ORMUserResponse.model_validate(database_user)

    print(response.model_dump())


# ============================================================================
# 30. SERIALIZATION TO JSON
# ============================================================================

def demonstrate_json_serialization() -> None:
    print("\n=== JSON Serialization ===")

    product = ProductWithStatusResponse(
        id=501,
        name="Serialized Product",
        price=Decimal("1999.95"),
        stock_quantity=5,
    )

    json_text = product.model_dump_json()

    print(json_text)

    parsed = json.loads(json_text)

    print("\nParsed JSON:")
    print(parsed)


# ============================================================================
# 31. ALIAS DEMONSTRATION
# ============================================================================

def demonstrate_aliases() -> None:
    print("\n=== Serialization Aliases ===")

    customer = CustomerPublicResponse(
        customer_id=100,
        full_name="Alias Customer",
        email="alias@example.com",
    )

    print(customer.model_dump())
    print(customer.model_dump(by_alias=True))


# ============================================================================
# 32. SECURITY-RELEVANT COMPARISON
# ============================================================================

def demonstrate_sensitive_field_protection() -> None:
    print("\n=== Sensitive Field Protection ===")

    internal = UserInternal(
        id=777,
        username="security_user",
        email="security@example.com",
        password_hash="VERY_SECRET_HASH",
        is_admin=True,
        created_at=datetime.now(timezone.utc),
    )

    print("\nInternal representation:")
    print(internal.model_dump())

    public = UserResponse(
        id=internal.id,
        username=internal.username,
        email=internal.email,
        is_admin=internal.is_admin,
        created_at=internal.created_at,
    )

    print("\nPublic representation:")
    print(public.model_dump())

    print(
        "\nThe password hash is absent because the public response contract "
        "does not contain that field."
    )


# ============================================================================
# 33. FASTAPI RESPONSE MODEL TESTS
# ============================================================================

def run_api_tests() -> None:
    print("\n=== FastAPI Response Tests ===")

    client = TestClient(app)

    response = client.get("/users/1")

    print("\nGET /users/1")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 200
    assert "password_hash" not in response.json()

    response = client.get("/users/999")

    print("\nGET /users/999")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 404

    response = client.get("/profiles/1")

    print("\nGET /profiles/1")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 200
    assert "bio" not in response.json()

    response = client.get("/products")

    print("\nGET /products")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 200
    assert isinstance(response.json(), list)

    response = client.get("/products/status")

    print("\nGET /products/status")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 200

    response = client.get("/customers-public/1")

    print("\nGET /customers-public/1")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert "customerId" in response.json()
    assert "fullName" in response.json()

    response = client.get("/users?page=1&page_size=1")

    print("\nGET /users?page=1&page_size=1")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 200

    response = client.get("/users?page=0")

    print("\nGET /users?page=0")
    print("Status:", response.status_code)
    print("JSON:", response.json())

    assert response.status_code == 400


# ============================================================================
# 34. RESPONSE-MODEL FILTERING EXPLANATION
# ============================================================================

def demonstrate_response_model_concept() -> None:
    print("\n=== Response Model Filtering ===")

    internal_dictionary = {
        "id": 1,
        "username": "filtered",
        "email": "filtered@example.com",
        "password_hash": "do-not-expose",
        "is_admin": True,
        "created_at": datetime.now(timezone.utc),
        "internal_note": "Private database note",
    }

    public_model = UserResponse.model_validate(internal_dictionary)

    print("\nInput contains extra/private fields:")
    print(internal_dictionary)

    print("\nResponse model contains only declared public fields:")
    print(public_model.model_dump())


# ============================================================================
# 35. COMMON MISTAKE: RETURNING INTERNAL DATA DIRECTLY
# ============================================================================

def demonstrate_bad_vs_good_design() -> None:
    print("\n=== Internal Model vs Public Response Model ===")

    internal = UserInternal(
        id=1,
        username="example",
        email="example@example.com",
        password_hash="private",
        is_admin=True,
        created_at=datetime.now(timezone.utc),
    )

    bad_output = internal.model_dump()

    good_output = UserResponse(
        id=internal.id,
        username=internal.username,
        email=internal.email,
        is_admin=internal.is_admin,
        created_at=internal.created_at,
    ).model_dump()

    print("\nPotentially unsafe internal serialization:")
    print(bad_output)

    print("\nExplicit public contract:")
    print(good_output)


# ============================================================================
# 36. RESPONSE MODEL DESIGN PRINCIPLES
# ============================================================================

def print_design_principles() -> None:
    principles = [
        "Treat response models as public API contracts.",
        "Do not expose database models blindly.",
        "Keep sensitive fields out of public response schemas.",
        "Use response_model to validate and shape FastAPI output.",
        "Use exclude_none when omission is preferable to JSON null values.",
        "Use exclude_unset when representing partial updates or sparse data.",
        "Use exclude_defaults when default-valued fields should be omitted.",
        "Use serializers for types that need a controlled wire representation.",
        "Use nested models for structured API responses.",
        "Use aliases when the external API naming convention differs from Python.",
        "Validate business invariants before data crosses the API boundary.",
        "Keep response schemas separate from persistence concerns when practical.",
    ]

    print("\n=== Response Model Design Principles ===")

    for number, principle in enumerate(principles, start=1):
        print(f"{number}. {principle}")


# ============================================================================
# 37. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n=== Edge Cases ===")

    print("\nEmpty optional response:")
    empty_profile = UserProfileResponse(id=1, username="empty")
    print(empty_profile.model_dump())
    print(empty_profile.model_dump(exclude_none=True))

    print("\nZero stock:")
    zero_stock = ProductWithStatusResponse(
        id=900,
        name="Unavailable",
        price=Decimal("10.00"),
        stock_quantity=0,
    )
    print(zero_stock.model_dump())

    print("\nLarge stock:")
    large_stock = ProductWithStatusResponse(
        id=901,
        name="Available",
        price=Decimal("10.00"),
        stock_quantity=1_000_000,
    )
    print(large_stock.model_dump())

    print("\nInvalid negative stock:")
    try:
        ProductResponse(
            id=902,
            name="Invalid",
            price=Decimal("10.00"),
            stock_quantity=-1,
        )
    except ValidationError as exc:
        print(exc)


# ============================================================================
# 38. COMPLETE EDUCATIONAL DEMONSTRATION
# ============================================================================

def run_demo() -> None:
    print("=" * 80)
    print("FASTAPI RESPONSE MODELS AND PYDANTIC SERIALIZATION")
    print("=" * 80)

    demonstrate_serialization()
    demonstrate_exclusion()
    demonstrate_exclude_none()
    demonstrate_exclude_defaults()
    demonstrate_exclude_unset()
    demonstrate_nested_exclusion()
    demonstrate_response_validation()
    demonstrate_from_attributes()
    demonstrate_json_serialization()
    demonstrate_aliases()
    demonstrate_sensitive_field_protection()
    demonstrate_response_model_concept()
    demonstrate_bad_vs_good_design()
    demonstrate_edge_cases()
    print_design_principles()
    run_api_tests()

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETED")
    print("=" * 80)


# ============================================================================
# 39. PROGRAM ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "demo"

    if mode == "demo":
        run_demo()

    elif mode == "server":
        import uvicorn

        uvicorn.run(
            "response_models_fastapi:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )

    elif mode == "test":
        run_api_tests()

    else:
        print("Usage:")
        print("  python response_models_fastapi.py demo")
        print("  python response_models_fastapi.py server")
        print("  python response_models_fastapi.py test")
