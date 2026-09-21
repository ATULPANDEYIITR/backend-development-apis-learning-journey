"""
Request Bodies with FastAPI and Pydantic
========================================

This standalone study script teaches:

1. HTTP request bodies
2. JSON request bodies
3. FastAPI request-body handling
4. Pydantic models
5. Required and optional fields
6. Default values
7. Type validation and coercion
8. Nested objects
9. Lists of nested objects
10. Field constraints
11. Custom validation
12. Model-level validation
13. Strict validation
14. Extra-field handling
15. Partial-update models
16. Serialization and deserialization
17. Response models
18. Validation errors
19. Security considerations
20. Testing request bodies
21. Practical API design
22. Advanced Pydantic concepts
23. A progressively developed order-management API

Install:
    python -m pip install fastapi uvicorn pydantic

Run the API:
    uvicorn request_bodies:app --reload

Interactive documentation:
    http://127.0.0.1:8000/docs

This file intentionally combines executable demonstrations with comments.
The examples are designed to remain understandable to a beginner while
progressing toward production-oriented API design.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

try:
    from fastapi import FastAPI, HTTPException, status
    from fastapi.testclient import TestClient
    from pydantic import (
        BaseModel,
        ConfigDict,
        EmailStr,
        Field,
        ValidationError,
        field_validator,
        model_validator,
    )
except ImportError as exc:
    raise SystemExit(
        "Required packages are missing. Install them with:\n"
        "python -m pip install fastapi uvicorn pydantic[email] httpx"
    ) from exc


# ============================================================================
# SECTION 1: THE BASIC IDEA OF A REQUEST BODY
# ============================================================================

"""
An HTTP request can contain information in several places.

Example:

POST /users/42?notify=true

Headers:
    Content-Type: application/json

Body:
    {
        "name": "Atul",
        "email": "atul@example.com"
    }

The body is the data sent to the server.

JSON is one of the most common formats for API request bodies because it
represents strings, numbers, booleans, arrays, null values, and objects.

A JSON object maps naturally to a Python dictionary:

JSON:
    {"name": "Atul", "age": 30}

Python:
    {"name": "Atul", "age": 30}

FastAPI can read JSON request bodies and validate them against Pydantic models.
"""


def demonstrate_raw_json_structure() -> None:
    """Show how common JSON values map to Python values."""

    example_request_body = {
        "name": "Atul",
        "age": 30,
        "active": True,
        "skills": ["Python", "SQL", "Git"],
        "profile": {
            "city": "Lucknow",
            "country": "India",
        },
        "middle_name": None,
    }

    print("\n=== Raw JSON-like Python structure ===")
    for field_name, value in example_request_body.items():
        print(f"{field_name}: {value!r} -> Python type: {type(value).__name__}")


# ============================================================================
# SECTION 2: SIMPLE PYDANTIC MODELS
# ============================================================================

class BasicUser(BaseModel):
    """
    A Pydantic model describes the expected shape of input data.

    A field without a default value is required.

    name: str
    age: int

    Both fields must be supplied by the caller.
    """

    name: str
    age: int


def demonstrate_basic_model() -> None:
    print("\n=== Basic Pydantic model ===")

    user = BasicUser(name="Atul", age=30)

    print("Parsed object:", user)
    print("Name:", user.name)
    print("Age:", user.age)

    # model_dump() converts the validated Pydantic object into a dictionary.
    print("Dictionary:", user.model_dump())

    # model_dump_json() creates JSON text.
    print("JSON:", user.model_dump_json())

    print("\nInvalid input:")

    try:
        BasicUser(name="Atul", age="not-a-number")
    except ValidationError as error:
        print(error)


# ============================================================================
# SECTION 3: REQUIRED VS OPTIONAL FIELDS
# ============================================================================

class RequiredVsOptionalExample(BaseModel):
    """
    Important distinction:

    name: str
        Required.

    nickname: str | None
        Required but allowed to contain None.

    phone: str | None = None
        Optional because it has a default value of None.

    This distinction matters in API design.
    """

    name: str
    nickname: str | None
    phone: str | None = None


def demonstrate_required_vs_optional() -> None:
    print("\n=== Required vs optional fields ===")

    # nickname must be supplied even though None is allowed.
    valid = RequiredVsOptionalExample(
        name="Atul",
        nickname=None,
    )
    print(valid.model_dump())

    # phone is genuinely optional because it has a default.
    valid_without_phone = RequiredVsOptionalExample(
        name="Atul",
        nickname="AP",
    )
    print(valid_without_phone.model_dump())

    try:
        RequiredVsOptionalExample(name="Atul")
    except ValidationError as error:
        print("\nMissing required nickname:")
        print(error)


# ============================================================================
# SECTION 4: FIELD CONSTRAINTS
# ============================================================================

class RegistrationRequest(BaseModel):
    """
    Field() adds validation rules to individual fields.
    """

    username: str = Field(
        min_length=3,
        max_length=30,
        description="Unique public username",
    )

    age: int = Field(
        ge=18,
        le=120,
        description="User age",
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


def demonstrate_field_constraints() -> None:
    print("\n=== Field constraints ===")

    valid = RegistrationRequest(
        username="atulpandey",
        age=30,
        email="atul@example.com",
        password="StrongPass123",
    )
    print(valid.model_dump())

    try:
        RegistrationRequest(
            username="x",
            age=12,
            email="not-an-email",
            password="123",
        )
    except ValidationError as error:
        print("\nMultiple validation failures:")
        print(error)


# ============================================================================
# SECTION 5: NESTED OBJECTS
# ============================================================================

class Address(BaseModel):
    street: str
    city: str
    state: str
    postal_code: str


class Customer(BaseModel):
    """
    address is another Pydantic model.

    This creates a nested JSON structure:

    {
        "name": "Atul",
        "address": {
            "street": "MG Road",
            "city": "Lucknow",
            "state": "Uttar Pradesh",
            "postal_code": "226001"
        }
    }
    """

    name: str
    email: EmailStr
    address: Address


def demonstrate_nested_objects() -> None:
    print("\n=== Nested object ===")

    customer = Customer(
        name="Atul",
        email="atul@example.com",
        address={
            "street": "MG Road",
            "city": "Lucknow",
            "state": "Uttar Pradesh",
            "postal_code": "226001",
        },
    )

    print(customer)
    print("City:", customer.address.city)
    print("Nested dictionary:")
    print(customer.model_dump())


# ============================================================================
# SECTION 6: LISTS OF NESTED OBJECTS
# ============================================================================

class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)


class ShoppingOrder(BaseModel):
    customer_id: int
    items: list[OrderItem]
    notes: str | None = None


def demonstrate_nested_lists() -> None:
    print("\n=== List of nested objects ===")

    order = ShoppingOrder(
        customer_id=1001,
        items=[
            {
                "product_id": 501,
                "quantity": 2,
                "unit_price": "499.99",
            },
            {
                "product_id": 502,
                "quantity": 1,
                "unit_price": "1299.00",
            },
        ],
    )

    print(order)
    print("First product:", order.items[0].product_id)
    print("Total item count:", sum(item.quantity for item in order.items))


# ============================================================================
# SECTION 7: ENUMS
# ============================================================================

class PaymentMethod(str, Enum):
    card = "card"
    upi = "upi"
    bank_transfer = "bank_transfer"


class PaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    reference: str | None = None


def demonstrate_enum_validation() -> None:
    print("\n=== Enum validation ===")

    payment = PaymentRequest(
        amount="1500.50",
        method="upi",
    )
    print(payment)
    print("Stored method:", payment.method.value)

    try:
        PaymentRequest(
            amount=100,
            method="cash",
        )
    except ValidationError as error:
        print("\nInvalid payment method:")
        print(error)


# ============================================================================
# SECTION 8: CUSTOM FIELD VALIDATORS
# ============================================================================

class ProductCreateRequest(BaseModel):
    name: str
    sku: str
    quantity: int = Field(ge=0)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        """
        Custom validation runs after Pydantic has identified the field
        as a string.

        Normalizing data can be useful when the API has a defined policy
        for accepted input.
        """

        normalized = value.strip().upper()

        if not normalized.startswith("SKU-"):
            raise ValueError("SKU must start with 'SKU-'")

        if len(normalized) < 8:
            raise ValueError("SKU is too short")

        return normalized


def demonstrate_custom_validator() -> None:
    print("\n=== Custom field validator ===")

    product = ProductCreateRequest(
        name="Laptop",
        sku=" sku-10001 ",
        quantity=5,
    )

    print(product)
    print("Normalized SKU:", product.sku)

    try:
        ProductCreateRequest(
            name="Laptop",
            sku="INVALID",
            quantity=5,
        )
    except ValidationError as error:
        print("\nInvalid SKU:")
        print(error)


# ============================================================================
# SECTION 9: MODEL-LEVEL VALIDATION
# ============================================================================

class DateRangeRequest(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


def demonstrate_model_validation() -> None:
    print("\n=== Model-level validation ===")

    request = DateRangeRequest(
        start_date="2026-09-01",
        end_date="2026-09-21",
    )
    print(request)

    try:
        DateRangeRequest(
            start_date="2026-09-21",
            end_date="2026-09-01",
        )
    except ValidationError as error:
        print("\nInvalid date range:")
        print(error)


# ============================================================================
# SECTION 10: STRICTNESS
# ============================================================================

class NormalNumericRequest(BaseModel):
    quantity: int


class StrictNumericRequest(BaseModel):
    quantity: int = Field(strict=True)


def demonstrate_strict_validation() -> None:
    print("\n=== Normal vs strict validation ===")

    normal = NormalNumericRequest(quantity="10")
    print("Normal model accepts string representation:", normal.quantity)

    try:
        StrictNumericRequest(quantity="10")
    except ValidationError as error:
        print("Strict model rejects the string:")
        print(error)


# ============================================================================
# SECTION 11: EXTRA FIELDS
# ============================================================================

class IgnoreExtraModel(BaseModel):
    """
    Extra fields are ignored by default in common Pydantic configurations.
    """

    model_config = ConfigDict(extra="ignore")

    name: str


class ForbidExtraModel(BaseModel):
    """
    Rejecting unknown fields can make API contracts stricter.
    """

    model_config = ConfigDict(extra="forbid")

    name: str


class AllowExtraModel(BaseModel):
    """
    Extra fields are retained explicitly when extra="allow" is selected.
    """

    model_config = ConfigDict(extra="allow")

    name: str


def demonstrate_extra_fields() -> None:
    print("\n=== Extra-field behavior ===")

    input_data = {
        "name": "Atul",
        "unexpected": "value",
    }

    ignored = IgnoreExtraModel.model_validate(input_data)
    print("Ignored:", ignored.model_dump())

    try:
        ForbidExtraModel.model_validate(input_data)
    except ValidationError as error:
        print("Forbidden:")
        print(error)

    allowed = AllowExtraModel.model_validate(input_data)
    print("Allowed:", allowed.model_dump())


# ============================================================================
# SECTION 12: SERIALIZATION AND DESERIALIZATION
# ============================================================================

class InvoiceRequest(BaseModel):
    invoice_number: str
    amount: Decimal
    issued_on: date
    paid: bool = False


def demonstrate_serialization() -> None:
    print("\n=== Serialization and deserialization ===")

    invoice = InvoiceRequest(
        invoice_number="INV-1001",
        amount="12500.75",
        issued_on="2026-09-21",
    )

    dictionary = invoice.model_dump()
    json_text = invoice.model_dump_json()

    print("Pydantic object:", invoice)
    print("Dictionary:", dictionary)
    print("JSON text:", json_text)

    reconstructed = InvoiceRequest.model_validate(dictionary)
    print("Reconstructed object:", reconstructed)


# ============================================================================
# SECTION 13: PARTIAL UPDATE MODELS
# ============================================================================

class UserCreate(BaseModel):
    username: str = Field(min_length=3)
    email: EmailStr
    display_name: str
    age: int = Field(ge=18)


class UserUpdate(BaseModel):
    """
    Update models often make fields optional.

    This does NOT necessarily mean the same fields are optional when creating
    a user. Create and update operations can have different contracts.
    """

    username: str | None = Field(default=None, min_length=3)
    email: EmailStr | None = None
    display_name: str | None = None
    age: int | None = Field(default=None, ge=18)


def demonstrate_partial_updates() -> None:
    print("\n=== Partial update ===")

    update = UserUpdate(display_name="Atul Pandey")

    print("Input:", update.model_dump())
    print("Only supplied values:", update.model_dump(exclude_unset=True))

    existing_user = {
        "username": "atul",
        "email": "atul@example.com",
        "display_name": "Old Name",
        "age": 30,
    }

    existing_user.update(update.model_dump(exclude_unset=True))

    print("After PATCH-style update:", existing_user)


# ============================================================================
# SECTION 14: COMPLETE DOMAIN MODELS
# ============================================================================

class ShippingAddress(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=100)
    street: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=3, max_length=20)
    country: str = Field(default="India", min_length=2, max_length=100)


class ProductLine(BaseModel):
    product_id: int = Field(gt=0)
    product_name: str = Field(min_length=1, max_length=150)
    quantity: int = Field(gt=0, le=1000)
    unit_price: Decimal = Field(gt=0, decimal_places=2)


class OrderCreateRequest(BaseModel):
    """
    A realistic nested request body.

    The expected JSON structure is conceptually:

        {
            "customer_id": 1001,
            "shipping_address": {
                ...
            },
            "items": [
                {
                    "product_id": 10,
                    "product_name": "Keyboard",
                    "quantity": 2,
                    "unit_price": "999.00"
                }
            ],
            "payment_method": "upi",
            "coupon_code": "SAVE10"
        }
    """

    customer_id: int = Field(gt=0)
    shipping_address: ShippingAddress
    items: list[ProductLine] = Field(min_length=1, max_length=100)
    payment_method: PaymentMethod
    coupon_code: str | None = Field(default=None, max_length=50)

    @field_validator("coupon_code")
    @classmethod
    def normalize_coupon(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().upper()

        if normalized == "":
            return None

        return normalized

    @model_validator(mode="after")
    def validate_order(self) -> "OrderCreateRequest":
        """
        Cross-field validation belongs at the model level.

        Here the rule is that the order must contain at least one item.
        Field(min_length=1) already enforces it, so this validator demonstrates
        where business rules involving multiple fields can live.
        """

        if self.payment_method == PaymentMethod.card and self.coupon_code == "CASHONLY":
            raise ValueError(
                "Coupon CASHONLY cannot be used with card payments"
            )

        return self


def calculate_order_subtotal(order: OrderCreateRequest) -> Decimal:
    """Calculate money using Decimal instead of binary floating point."""

    subtotal = Decimal("0.00")

    for item in order.items:
        subtotal += item.unit_price * item.quantity

    return subtotal.quantize(Decimal("0.01"))


def demonstrate_complete_order_model() -> None:
    print("\n=== Complete nested order model ===")

    payload = {
        "customer_id": 1001,
        "shipping_address": {
            "recipient_name": "Atul Pandey",
            "street": "MG Road",
            "city": "Lucknow",
            "state": "Uttar Pradesh",
            "postal_code": "226001",
            "country": "India",
        },
        "items": [
            {
                "product_id": 101,
                "product_name": "Mechanical Keyboard",
                "quantity": 2,
                "unit_price": "2499.00",
            },
            {
                "product_id": 102,
                "product_name": "Mouse",
                "quantity": 1,
                "unit_price": "1299.00",
            },
        ],
        "payment_method": "upi",
        "coupon_code": " save10 ",
    }

    order = OrderCreateRequest.model_validate(payload)

    print(order)
    print("Normalized coupon:", order.coupon_code)
    print("Subtotal:", calculate_order_subtotal(order))
    print("Serialized:")
    print(order.model_dump_json())


# ============================================================================
# SECTION 15: RESPONSE MODELS
# ============================================================================

class OrderResponse(BaseModel):
    order_id: int
    customer_id: int
    status: Literal["pending", "confirmed", "cancelled"]
    subtotal: Decimal
    created_at: datetime


def demonstrate_response_model() -> None:
    print("\n=== Response model ===")

    response = OrderResponse(
        order_id=9001,
        customer_id=1001,
        status="confirmed",
        subtotal="6297.00",
        created_at=datetime.now(),
    )

    print(response.model_dump())
    print(response.model_dump_json())


# ============================================================================
# SECTION 16: FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Request Body Learning API",
    version="1.0.0",
    description=(
        "Educational API demonstrating JSON request bodies, "
        "Pydantic models, nested objects, and required/optional fields."
    ),
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Request body learning API",
        "docs": "/docs",
    }


@app.post("/users")
def create_user(request: UserCreate) -> dict[str, Any]:
    """
    FastAPI recognizes request: UserCreate as a request body.

    FastAPI:
        1. Reads the incoming JSON body.
        2. Converts it into the Pydantic model.
        3. Validates the fields.
        4. Calls this function only when validation succeeds.
    """

    return {
        "message": "User accepted",
        "user": request.model_dump(),
    }


@app.post("/orders", response_model=OrderResponse)
def create_order(request: OrderCreateRequest) -> OrderResponse:
    """
    A nested JSON body becomes a nested Pydantic object.

    The response_model ensures the response follows the declared response
    contract.
    """

    subtotal = calculate_order_subtotal(request)

    return OrderResponse(
        order_id=9001,
        customer_id=request.customer_id,
        status="confirmed",
        subtotal=subtotal,
        created_at=datetime.now(),
    )


@app.patch("/users/{user_id}")
def update_user(user_id: int, request: UserUpdate) -> dict[str, Any]:
    """
    PATCH commonly uses a partial-update model.

    exclude_unset=True distinguishes:
        field not supplied
    from:
        field supplied with a value such as None
    """

    return {
        "user_id": user_id,
        "changes": request.model_dump(exclude_unset=True),
    }


@app.post("/payments")
def create_payment(request: PaymentRequest) -> dict[str, Any]:
    return {
        "accepted": True,
        "payment": request.model_dump(mode="json"),
    }


# ============================================================================
# SECTION 17: VALIDATION THROUGH FASTAPI'S TEST CLIENT
# ============================================================================

def demonstrate_fastapi_requests() -> None:
    """
    TestClient lets us exercise the API without starting a separate server.

    It is useful for automated API tests and educational demonstrations.
    """

    print("\n=== FastAPI request-body testing ===")

    client = TestClient(app)

    valid_response = client.post(
        "/users",
        json={
            "username": "atul",
            "email": "atul@example.com",
            "display_name": "Atul Pandey",
            "age": 30,
        },
    )

    print("Valid status:", valid_response.status_code)
    print("Valid response:", valid_response.json())

    invalid_response = client.post(
        "/users",
        json={
            "username": "a",
            "email": "invalid",
            "display_name": "Atul",
            "age": 15,
        },
    )

    print("\nInvalid status:", invalid_response.status_code)
    print("Validation response:")
    print(invalid_response.json())

    order_response = client.post(
        "/orders",
        json={
            "customer_id": 1001,
            "shipping_address": {
                "recipient_name": "Atul Pandey",
                "street": "MG Road",
                "city": "Lucknow",
                "state": "Uttar Pradesh",
                "postal_code": "226001",
                "country": "India",
            },
            "items": [
                {
                    "product_id": 101,
                    "product_name": "Keyboard",
                    "quantity": 2,
                    "unit_price": "2499.00",
                }
            ],
            "payment_method": "upi",
        },
    )

    print("\nOrder status:", order_response.status_code)
    print("Order response:", order_response.json())


# ============================================================================
# SECTION 18: EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n=== Edge cases ===")

    cases = {
        "missing_required_field": {
            "username": "atul",
            "email": "atul@example.com",
            "display_name": "Atul",
            # age intentionally missing
        },
        "null_required_field": {
            "username": "atul",
            "email": "atul@example.com",
            "display_name": "Atul",
            "age": None,
        },
        "empty_list": {
            "customer_id": 1,
            "shipping_address": {
                "recipient_name": "Atul",
                "street": "MG Road",
                "city": "Lucknow",
                "state": "UP",
                "postal_code": "226001",
            },
            "items": [],
            "payment_method": "upi",
        },
        "negative_quantity": {
            "product_id": 1,
            "product_name": "Keyboard",
            "quantity": -2,
            "unit_price": "100.00",
        },
    }

    for name, data in cases.items():
        print(f"\nCase: {name}")

        try:
            if name in {"missing_required_field", "null_required_field"}:
                UserCreate.model_validate(data)
            elif name == "empty_list":
                OrderCreateRequest.model_validate(data)
            else:
                ProductLine.model_validate(data)

            print("Accepted")
        except ValidationError as error:
            print("Rejected")
            print(error.errors())


# ============================================================================
# SECTION 19: COMMON API DESIGN MISTAKES
# ============================================================================

def demonstrate_common_mistakes() -> None:
    print("\n=== Common mistakes ===")

    print(
        """
1. Treating every field as optional.
   This weakens the API contract.

2. Confusing:
       field: str | None
   with:
       field: str | None = None

   The first allows null but still requires the field.
   The second makes the field optional.

3. Using float for financial amounts.
   Decimal is generally safer for monetary calculations.

4. Trusting the client.
   Request-body validation does not replace authorization or server-side
   business rules.

5. Accepting arbitrary extra fields without considering the API contract.

6. Using one model for every operation.
   Create, update, internal database, and public response models can have
   different responsibilities.

7. Returning sensitive request fields.
   A password may be accepted as input but should not normally appear in
   the response.

8. Performing database or external-service work inside validators when the
   operation has side effects or expensive I/O.

9. Forgetting nested validation.
   A valid outer object does not make malformed nested objects valid.

10. Assuming a valid JSON shape means valid business data.
    Syntax validation and business validation are different layers.
"""
    )


# ============================================================================
# SECTION 20: SECURITY CONSIDERATIONS
# ============================================================================

def demonstrate_security_principles() -> None:
    print("\n=== Security principles ===")

    principles = [
        "Validate all client-controlled input.",
        "Use minimum required fields.",
        "Restrict string lengths to reduce abuse and accidental oversized input.",
        "Use strict types when accepting coercion would create ambiguity.",
        "Do not trust customer_id, price, discount, or permission fields supplied by clients.",
        "Authorize the authenticated user before changing protected resources.",
        "Never expose passwords, tokens, secrets, or internal fields in responses.",
        "Apply rate limits and request-size limits at the appropriate infrastructure layer.",
        "Treat validation as input protection, not as a complete security system.",
        "Log validation failures carefully without storing sensitive request bodies unnecessarily.",
    ]

    for number, principle in enumerate(principles, start=1):
        print(f"{number}. {principle}")


# ============================================================================
# SECTION 21: PERFORMANCE CONSIDERATIONS
# ============================================================================

def demonstrate_performance_concepts() -> None:
    print("\n=== Performance considerations ===")

    print(
        """
Pydantic validation adds processing work because the incoming data must be
checked and transformed.

For ordinary API workloads, validation is usually a valuable trade-off.

Performance considerations include:

- Avoid unnecessarily huge nested request bodies.
- Limit list sizes with Field(min_length=..., max_length=...).
- Limit string lengths.
- Avoid repeated validation of the same object when it is unnecessary.
- Avoid expensive database queries inside field validators.
- Separate pure validation from I/O-heavy business operations.
- Use appropriate response models to avoid serializing unnecessary data.
- Benchmark real workloads before removing validation for performance reasons.
"""
    )


# ============================================================================
# SECTION 22: ARCHITECTURAL DISTINCTION
# ============================================================================

def explain_validation_layers() -> None:
    print("\n=== Validation layers ===")

    layers = [
        (
            "JSON syntax",
            "Can the body be parsed as JSON?",
        ),
        (
            "Schema validation",
            "Does the structure match the Pydantic model?",
        ),
        (
            "Field validation",
            "Are individual values within allowed constraints?",
        ),
        (
            "Cross-field validation",
            "Are related fields logically consistent?",
        ),
        (
            "Business rules",
            "Is this operation allowed according to application rules?",
        ),
        (
            "Authorization",
            "Is the current user permitted to perform the operation?",
        ),
        (
            "Persistence constraints",
            "Can the validated operation safely be stored?",
        ),
    ]

    for layer, explanation in layers:
        print(f"{layer}: {explanation}")


# ============================================================================
# SECTION 23: MAIN STUDY RUNNER
# ============================================================================

def main() -> None:
    """
    Running this file directly executes the learning demonstrations.

    Starting it through Uvicorn imports the same module and exposes `app`.
    """

    print("=" * 80)
    print("FASTAPI REQUEST BODIES AND PYDANTIC STUDY SCRIPT")
    print("=" * 80)

    demonstrate_raw_json_structure()
    demonstrate_basic_model()
    demonstrate_required_vs_optional()
    demonstrate_field_constraints()
    demonstrate_nested_objects()
    demonstrate_nested_lists()
    demonstrate_enum_validation()
    demonstrate_custom_validator()
    demonstrate_model_validation()
    demonstrate_strict_validation()
    demonstrate_extra_fields()
    demonstrate_serialization()
    demonstrate_partial_updates()
    demonstrate_complete_order_model()
    demonstrate_response_model()
    demonstrate_fastapi_requests()
    demonstrate_edge_cases()
    demonstrate_common_mistakes()
    demonstrate_security_principles()
    demonstrate_performance_concepts()
    explain_validation_layers()

    print("\n=== API availability ===")
    print("FastAPI application object: app")
    print("Start with:")
    print("uvicorn request_bodies:app --reload")


if __name__ == "__main__":
    main()
