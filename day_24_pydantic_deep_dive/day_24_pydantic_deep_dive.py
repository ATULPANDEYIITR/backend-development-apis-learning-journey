"""
Pydantic Deep Dive
==================

Topic:
    BaseModel, Field, validators, nested models, constrained values,
    custom validation

This file is a self-contained study program for Pydantic 2.x.
Install:
    python -m pip install "pydantic>=2,<3"

The examples progress from basic model construction to nested models,
constrained values, field/model validators, reusable validation logic,
serialization, JSON Schema, strict validation, assignment validation,
generic models, computed fields, aliases, custom types, and a realistic
API-style validation case study.

The script intentionally prints demonstrations instead of relying only
on explanatory prose.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
    TypeAdapter,
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def show_validation_error(error: ValidationError) -> None:
    print("Validation failed:")
    for item in error.errors():
        print(
            f"  location={item['loc']!r}, "
            f"type={item['type']!r}, "
            f"message={item['msg']!r}"
        )


# ---------------------------------------------------------------------------
# 1. Absolute beginner: why Pydantic exists
# ---------------------------------------------------------------------------

section("1. Basic BaseModel")

class User(BaseModel):
    name: str
    age: int


user = User(name="Atul", age=30)
print(user)
print(user.name)
print(user.age)

# Pydantic parses compatible input types in many normal cases.
parsed_user = User(name="Riya", age="25")
print(parsed_user)
print(type(parsed_user.age))

# Invalid data raises ValidationError instead of silently creating
# an invalid model.
try:
    User(name="Riya", age="not-a-number")
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 2. BaseModel as a structured validation boundary
# ---------------------------------------------------------------------------

section("2. BaseModel as a validation boundary")

class Product(BaseModel):
    product_id: int
    name: str
    price: float
    available: bool = True


product = Product(
    product_id=101,
    name="Mechanical Keyboard",
    price=4999.50,
)

print(product)
print(product.model_dump())
print(product.model_dump_json())

# model_validate() accepts an existing dictionary-like object.
raw_product = {
    "product_id": 102,
    "name": "Monitor",
    "price": 15999,
}
product_from_mapping = Product.model_validate(raw_product)
print(product_from_mapping)

# model_validate_json() validates JSON input.
json_product = Product.model_validate_json(
    '{"product_id":103,"name":"Mouse","price":1299}'
)
print(json_product)


# ---------------------------------------------------------------------------
# 3. Field()
# ---------------------------------------------------------------------------

section("3. Field metadata, defaults, and constraints")

class Account(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=30,
        description="Unique public username",
    )
    age: int = Field(ge=18, le=120)
    balance: Decimal = Field(default=Decimal("0.00"), ge=0)
    email: str = Field(
        min_length=5,
        max_length=254,
        description="Account email address",
    )


account = Account(
    username="atul123",
    age=30,
    balance="1500.50",
    email="atul@example.com",
)
print(account)
print(account.model_dump())

for invalid_data in [
    {"username": "ab", "age": 30, "email": "a@b.com"},
    {"username": "validname", "age": 17, "email": "a@b.com"},
    {"username": "validname", "age": 30, "balance": -5, "email": "a@b.com"},
]:
    try:
        Account(**invalid_data)
    except ValidationError as error:
        show_validation_error(error)


# ---------------------------------------------------------------------------
# 4. Constrained values with Annotated
# ---------------------------------------------------------------------------

section("4. Constrained values with Annotated")

PositiveInt = Annotated[int, Field(gt=0)]
Percentage = Annotated[float, Field(ge=0, le=100)]
NonEmptyName = Annotated[str, Field(min_length=1, max_length=100)]

class Metrics(BaseModel):
    quantity: PositiveInt
    completion: Percentage
    label: NonEmptyName


print(Metrics(quantity=10, completion=72.5, label="Processing"))

try:
    Metrics(quantity=0, completion=101, label="")
except ValidationError as error:
    show_validation_error(error)

# Annotated aliases make constraints reusable without creating separate
# model classes.


# ---------------------------------------------------------------------------
# 5. Strings, numbers, collections, and multiple constraints
# ---------------------------------------------------------------------------

section("5. Common Field constraints")

class InventoryItem(BaseModel):
    sku: str = Field(pattern=r"^[A-Z]{3}-\d{4}$")
    quantity: int = Field(ge=0, le=100000)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    tags: list[str] = Field(min_length=1, max_length=10)
    dimensions: tuple[float, float, float]

item = InventoryItem(
    sku="CPU-2026",
    quantity=25,
    unit_price="14999.99",
    tags=["hardware", "cpu"],
    dimensions=(10.0, 20.0, 5.0),
)
print(item)

try:
    InventoryItem(
        sku="bad-sku",
        quantity=-1,
        unit_price="0",
        tags=[],
        dimensions=(1.0, 2.0),
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 6. Built-in useful types
# ---------------------------------------------------------------------------

section("6. Pydantic with standard Python types")

class Identity(BaseModel):
    identifier: UUID
    birth_date: date
    created_at: datetime


identity = Identity(
    identifier=str(uuid4()),
    birth_date="1995-08-20",
    created_at="2026-09-24T10:30:00",
)
print(identity)
print(type(identity.identifier))
print(type(identity.birth_date))
print(type(identity.created_at))


# ---------------------------------------------------------------------------
# 7. Enum and Literal
# ---------------------------------------------------------------------------

section("7. Enum and Literal")

class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


class OrderState(BaseModel):
    status: OrderStatus
    channel: Literal["web", "mobile", "api"]


print(OrderState(status="paid", channel="web"))
print(OrderState(status=OrderStatus.SHIPPED, channel="api"))

try:
    OrderState(status="unknown", channel="terminal")
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 8. Field validators
# ---------------------------------------------------------------------------

section("8. Field validators")

class Registration(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        # Validators can transform a value before it is stored.
        normalized = value.strip().lower()
        if " " in normalized:
            raise ValueError("username cannot contain spaces")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must contain @")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("password must contain at least 12 characters")
        return value


registration = Registration(
    username="  AtulPandey  ",
    email=" ATUL@EXAMPLE.COM ",
    password="correct-horse-123",
)
print(registration)

try:
    Registration(
        username="bad username",
        email="invalid",
        password="short",
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 9. before and after field validation
# ---------------------------------------------------------------------------

section("9. Field validator modes")

class Measurement(BaseModel):
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def normalize_raw_value(cls, value: Any) -> Any:
        # mode="before" sees the input before Pydantic's normal type parsing.
        if isinstance(value, str):
            return value.strip().replace(",", "")
        return value

    @field_validator("value", mode="after")
    @classmethod
    def ensure_reasonable_value(cls, value: float) -> float:
        # mode="after" sees the already parsed float.
        if value > 1_000_000:
            raise ValueError("measurement is too large")
        return value


print(Measurement(value=" 12,500.5 "))
print(Measurement(value=100))

try:
    Measurement(value="2,000,000")
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 10. Multiple fields and validation ordering
# ---------------------------------------------------------------------------

section("10. Validating multiple fields")

class Person(BaseModel):
    first_name: str
    last_name: str
    age: int

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_names(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("name cannot be empty")
        return cleaned.title()

    @field_validator("age")
    @classmethod
    def validate_age(cls, value: int) -> int:
        if value < 0:
            raise ValueError("age cannot be negative")
        return value


print(Person(first_name="  atul  ", last_name="  pandey ", age=30))


# ---------------------------------------------------------------------------
# 11. Model validators: relationships between fields
# ---------------------------------------------------------------------------

section("11. Model validators")

class DateRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_range(self) -> DateRange:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


print(DateRange(start_date="2026-09-01", end_date="2026-09-30"))

try:
    DateRange(start_date="2026-09-30", end_date="2026-09-01")
except ValidationError as error:
    show_validation_error(error)


class Payment(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: Literal["INR", "USD", "EUR"]
    payment_method: Literal["card", "bank_transfer", "cash"]
    reference: str | None = None

    @model_validator(mode="after")
    def validate_payment_rules(self) -> Payment:
        if self.payment_method == "bank_transfer" and not self.reference:
            raise ValueError(
                "bank transfers require a transaction reference"
            )
        if self.payment_method == "cash" and self.currency != "INR":
            raise ValueError("cash payments in this model must use INR")
        return self


print(
    Payment(
        amount="5000",
        currency="INR",
        payment_method="bank_transfer",
        reference="TXN-2026-001",
    )
)

try:
    Payment(
        amount="5000",
        currency="USD",
        payment_method="cash",
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 12. before model validators
# ---------------------------------------------------------------------------

section("12. Before model validation")

class FlexibleUser(BaseModel):
    username: str
    age: int

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_payload(cls, data: Any) -> Any:
        # before receives raw input. It is useful for migrations and
        # alternate input formats.
        if isinstance(data, dict):
            data = dict(data)
            if "user_name" in data and "username" not in data:
                data["username"] = data.pop("user_name")
        return data


print(FlexibleUser(user_name="legacy_user", age=35))


# ---------------------------------------------------------------------------
# 13. Nested models
# ---------------------------------------------------------------------------

section("13. Nested models")

class Address(BaseModel):
    street: str
    city: str
    postal_code: str = Field(pattern=r"^\d{6}$")


class Customer(BaseModel):
    customer_id: int
    name: str
    address: Address


customer = Customer(
    customer_id=1,
    name="Atul Pandey",
    address={
        "street": "Main Road",
        "city": "Lucknow",
        "postal_code": "226001",
    },
)

print(customer)
print(customer.address.city)
print(customer.model_dump())

try:
    Customer(
        customer_id=2,
        name="Invalid Customer",
        address={
            "street": "Somewhere",
            "city": "Lucknow",
            "postal_code": "bad",
        },
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 14. Lists of nested models
# ---------------------------------------------------------------------------

section("14. Collections of nested models")

class LineItem(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)

    @computed_field
    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class ShoppingOrder(BaseModel):
    order_id: str
    customer: Customer
    items: list[LineItem] = Field(min_length=1)

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0"))


order = ShoppingOrder(
    order_id="ORD-1001",
    customer=customer,
    items=[
        {
            "sku": "KEY-001",
            "quantity": 2,
            "unit_price": "2500.00",
        },
        {
            "sku": "MOU-001",
            "quantity": 1,
            "unit_price": "1200.00",
        },
    ],
)

print(order)
print("Subtotal:", order.subtotal)
print(order.model_dump())


# ---------------------------------------------------------------------------
# 15. Recursive nested structures
# ---------------------------------------------------------------------------

section("15. Recursive models")

class Category(BaseModel):
    name: str
    children: list[Category] = Field(default_factory=list)


catalog = Category(
    name="Electronics",
    children=[
        Category(
            name="Computers",
            children=[
                Category(name="Laptops"),
                Category(name="Desktops"),
            ],
        ),
        Category(name="Accessories"),
    ],
)

print(catalog.model_dump_json(indent=2))


# ---------------------------------------------------------------------------
# 16. Optional versus required
# ---------------------------------------------------------------------------

section("16. Required and optional fields")

class Profile(BaseModel):
    username: str
    nickname: str | None
    bio: str | None = None


# nickname is required even though None is allowed.
try:
    Profile(username="atul")
except ValidationError as error:
    show_validation_error(error)

print(Profile(username="atul", nickname=None))
print(Profile(username="atul", nickname="AP", bio=None))


# ---------------------------------------------------------------------------
# 17. Default factories
# ---------------------------------------------------------------------------

section("17. Default factories")

class Session(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    permissions: list[str] = Field(default_factory=list)


session_a = Session()
session_b = Session()

print(session_a)
print(session_b)
print(session_a.permissions is session_b.permissions)


# ---------------------------------------------------------------------------
# 18. Model configuration
# ---------------------------------------------------------------------------

section("18. ConfigDict")

class StrictRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    name: str
    quantity: int = Field(ge=0)


record = StrictRecord(name="  item  ", quantity=10)
print(record)

# validate_assignment makes later assignment go through validation.
try:
    record.quantity = -10
except ValidationError as error:
    show_validation_error(error)

# extra="forbid" rejects unknown input keys.
try:
    StrictRecord(name="item", quantity=1, unexpected=True)
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 19. Extra field policies
# ---------------------------------------------------------------------------

section("19. Extra field behavior")

class IgnoreExtras(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str


class AllowExtras(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str


class ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


print(IgnoreExtras(name="A", unknown=123))
print(AllowExtras(name="B", unknown=456))

try:
    ForbidExtras(name="C", unknown=789)
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 20. Strict validation
# ---------------------------------------------------------------------------

section("20. Strict types and strict model validation")

from pydantic import StrictBool, StrictFloat, StrictInt, StrictStr


class StrictTypesModel(BaseModel):
    quantity: StrictInt
    price: StrictFloat
    active: StrictBool
    code: StrictStr


print(
    StrictTypesModel(
        quantity=10,
        price=12.5,
        active=True,
        code="ABC",
    )
)

try:
    StrictTypesModel(
        quantity="10",
        price="12.5",
        active=1,
        code=123,
    )
except ValidationError as error:
    show_validation_error(error)


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)

    quantity: int
    active: bool


try:
    StrictModel(quantity="10", active="true")
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 21. Serialization and aliases
# ---------------------------------------------------------------------------

section("21. Serialization and aliases")

class APIUser(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )

    user_id: int = Field(alias="userId")
    display_name: str = Field(alias="displayName")
    email_address: str = Field(alias="emailAddress")


api_user = APIUser(
    userId=100,
    displayName="Atul Pandey",
    emailAddress="atul@example.com",
)

print(api_user)
print(api_user.model_dump())
print(api_user.model_dump(by_alias=True))
print(api_user.model_dump_json(by_alias=True))


# ---------------------------------------------------------------------------
# 22. JSON Schema
# ---------------------------------------------------------------------------

section("22. JSON Schema generation")

schema = ShoppingOrder.model_json_schema()

print("Schema title:", schema.get("title"))
print("Top-level keys:", sorted(schema.keys()))
print("Required fields:", schema.get("required"))
print("Property names:", list(schema.get("properties", {}).keys()))


# ---------------------------------------------------------------------------
# 23. TypeAdapter
# ---------------------------------------------------------------------------

section("23. TypeAdapter for validation outside BaseModel")

EmailList = Annotated[
    list[str],
    Field(min_length=1, max_length=5),
]

email_adapter = TypeAdapter(EmailList)

print(email_adapter.validate_python(["a@example.com", "b@example.com"]))

try:
    email_adapter.validate_python([])
except ValidationError as error:
    show_validation_error(error)

# TypeAdapter is useful when the validation target is a type rather than
# an entire model.


# ---------------------------------------------------------------------------
# 24. Custom validation with reusable Annotated logic
# ---------------------------------------------------------------------------

section("24. Reusable custom validation")

def normalize_code(value: str) -> str:
    cleaned = value.strip().upper()
    if not cleaned:
        raise ValueError("code cannot be empty")
    return cleaned


NormalizedCode = Annotated[str, Field(min_length=2)]

class CodeRecord(BaseModel):
    code: NormalizedCode

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return normalize_code(value)


print(CodeRecord(code="  ab-100  "))

try:
    CodeRecord(code=" ")
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 25. Validation of cross-field business rules
# ---------------------------------------------------------------------------

section("25. Cross-field business rules")

class LoanApplication(BaseModel):
    applicant_name: str = Field(min_length=2)
    annual_income: Decimal = Field(gt=0)
    requested_amount: Decimal = Field(gt=0)
    term_years: int = Field(ge=1, le=30)
    employment_type: Literal["salaried", "self_employed", "business"]

    @model_validator(mode="after")
    def validate_debt_capacity(self) -> LoanApplication:
        # This is an illustrative rule, not a financial underwriting model.
        maximum_amount = self.annual_income * Decimal("5")

        if self.requested_amount > maximum_amount:
            raise ValueError(
                "requested_amount exceeds the illustrative income limit"
            )

        if (
            self.employment_type == "salaried"
            and self.term_years > 20
        ):
            raise ValueError(
                "this example limits salaried applications to 20 years"
            )

        return self


print(
    LoanApplication(
        applicant_name="Atul Pandey",
        annual_income="1000000",
        requested_amount="4000000",
        term_years=15,
        employment_type="salaried",
    )
)

try:
    LoanApplication(
        applicant_name="Atul Pandey",
        annual_income="1000000",
        requested_amount="6000000",
        term_years=15,
        employment_type="salaried",
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 26. Validation context
# ---------------------------------------------------------------------------

section("26. Validation context")

class ContextAwareUser(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_against_context(
        cls,
        value: str,
        info: Any,
    ) -> str:
        reserved_names = set(info.context.get("reserved_names", []))
        normalized = value.strip().lower()

        if normalized in reserved_names:
            raise ValueError("username is reserved")

        return normalized


print(
    ContextAwareUser.model_validate(
        {"username": "NewUser"},
        context={"reserved_names": ["admin", "root"]},
    )
)

try:
    ContextAwareUser.model_validate(
        {"username": "Admin"},
        context={"reserved_names": ["admin", "root"]},
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 27. Custom types with Annotated and a validator function
# ---------------------------------------------------------------------------

section("27. Reusable domain types")

def validate_phone_number(value: str) -> str:
    cleaned = value.replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        raise ValueError("phone number must start with +")
    digits = cleaned[1:]
    if not digits.isdigit() or not 10 <= len(digits) <= 15:
        raise ValueError("phone number must contain 10 to 15 digits")
    return "+" + digits


PhoneNumber = Annotated[str, Field(min_length=11, max_length=16)]


class Contact(BaseModel):
    phone: PhoneNumber

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return validate_phone_number(value)


print(Contact(phone="+91 98765-43210"))

try:
    Contact(phone="98765")
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 28. Discriminated unions
# ---------------------------------------------------------------------------

section("28. Discriminated unions")

from typing import Union

class CardPayment(BaseModel):
    method: Literal["card"]
    card_last4: str = Field(pattern=r"^\d{4}$")


class BankPayment(BaseModel):
    method: Literal["bank"]
    account_reference: str = Field(min_length=4)


PaymentDetails = Annotated[
    Union[CardPayment, BankPayment],
    Field(discriminator="method"),
]


class Transaction(BaseModel):
    transaction_id: str
    payment: PaymentDetails


print(
    Transaction(
        transaction_id="TX-1",
        payment={
            "method": "card",
            "card_last4": "1234",
        },
    )
)

print(
    Transaction(
        transaction_id="TX-2",
        payment={
            "method": "bank",
            "account_reference": "ACC-001",
        },
    )
)

try:
    Transaction(
        transaction_id="TX-3",
        payment={
            "method": "card",
            "card_last4": "12",
        },
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 29. Generic models
# ---------------------------------------------------------------------------

section("29. Generic models")

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T
    message: str | None = None


UserResponse = APIResponse[APIUser]

response = UserResponse(
    success=True,
    data={
        "userId": 1,
        "displayName": "Atul",
        "emailAddress": "atul@example.com",
    },
)

print(response)
print(response.data)


# ---------------------------------------------------------------------------
# 30. Computed fields
# ---------------------------------------------------------------------------

section("30. Computed fields")

class Rectangle(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

    @computed_field
    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)


rectangle = Rectangle(width=10, height=5)
print("Area:", rectangle.area)
print("Perimeter:", rectangle.perimeter)
print(rectangle.model_dump())


# ---------------------------------------------------------------------------
# 31. Model construction versus validation
# ---------------------------------------------------------------------------

section("31. Validation versus model_construct")

class SafeModel(BaseModel):
    quantity: int = Field(gt=0)


safe = SafeModel(quantity=10)
print(safe)

# model_construct() bypasses validation. It is intended for trusted,
# already validated data and should not be treated as a shortcut for
# normal untrusted input validation.
unsafe = SafeModel.model_construct(quantity=-999)
print("Constructed without validation:", unsafe)


# ---------------------------------------------------------------------------
# 32. Error structure and programmatic inspection
# ---------------------------------------------------------------------------

section("32. Structured ValidationError")

try:
    ShoppingOrder(
        order_id="BAD",
        customer={
            "customer_id": 1,
            "name": "Customer",
            "address": {
                "street": "Street",
                "city": "Lucknow",
                "postal_code": "wrong",
            },
        },
        items=[
            {
                "sku": "X",
                "quantity": 0,
                "unit_price": "-1",
            }
        ],
    )
except ValidationError as error:
    print("Number of errors:", error.error_count())
    print("Structured errors:")
    for detail in error.errors():
        print(detail)


# ---------------------------------------------------------------------------
# 33. Realistic API request model
# ---------------------------------------------------------------------------

section("33. Industry-style API request validation")

class CustomerAddress(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    line1: str = Field(min_length=5, max_length=120)
    city: str = Field(min_length=2, max_length=60)
    state: str = Field(min_length=2, max_length=60)
    postal_code: str = Field(pattern=r"^\d{6}$")


class ProductRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    customer_id: int = Field(gt=0)
    shipping_address: CustomerAddress
    products: list[ProductRequest] = Field(min_length=1, max_length=100)
    coupon_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=30,
    )

    @field_validator("coupon_code")
    @classmethod
    def normalize_coupon(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()

    @model_validator(mode="after")
    def ensure_unique_products(self) -> CreateOrderRequest:
        product_ids = [item.product_id for item in self.products]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError("products must not contain duplicate product IDs")

        return self


valid_request = {
    "customer_id": 500,
    "shipping_address": {
        "line1": "12 Main Road",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "postal_code": "226001",
    },
    "products": [
        {"product_id": 101, "quantity": 2},
        {"product_id": 102, "quantity": 1},
    ],
    "coupon_code": " save20 ",
}

request = CreateOrderRequest.model_validate(valid_request)
print(request)
print(request.model_dump())


invalid_request = {
    "customer_id": -1,
    "shipping_address": {
        "line1": "X",
        "city": "L",
        "state": "U",
        "postal_code": "123",
    },
    "products": [
        {"product_id": 1, "quantity": 0},
        {"product_id": 1, "quantity": 5},
    ],
    "unknown_field": True,
}

try:
    CreateOrderRequest.model_validate(invalid_request)
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 34. Performance-oriented validation
# ---------------------------------------------------------------------------

section("34. Reusing TypeAdapter and models")

number_adapter = TypeAdapter(list[PositiveInt])

values = number_adapter.validate_python([1, 2, 3, 4, 5])
print(values)

# For repeated validation, construct the adapter once rather than creating
# a new TypeAdapter for every item in a hot loop.
for batch in ([1, 2, 3], [10, 20], [100]):
    print(number_adapter.validate_python(batch))


# ---------------------------------------------------------------------------
# 35. Common mistakes demonstrated
# ---------------------------------------------------------------------------

section("35. Common mistakes")

# Mistake 1: expecting Optional/union-with-None to automatically mean
# "optional field". A field with no default can still be required.
class RequiredNullable(BaseModel):
    value: str | None


try:
    RequiredNullable()
except ValidationError as error:
    show_validation_error(error)

# Mistake 2: using mutable defaults carelessly in ordinary Python classes.
# Pydantic handles model field defaults safely, and default_factory is the
# explicit, readable choice for generated collections.
class CorrectCollectionModel(BaseModel):
    values: list[int] = Field(default_factory=list)


a = CorrectCollectionModel()
b = CorrectCollectionModel()
a.values.append(1)

print("a.values:", a.values)
print("b.values:", b.values)

# Mistake 3: bypassing validation with model_construct() for untrusted data.
try:
    SafeModel(quantity=0)
except ValidationError as error:
    show_validation_error(error)

print("model_construct bypasses the normal validation pipeline.")


# ---------------------------------------------------------------------------
# 36. Security-oriented validation principles
# ---------------------------------------------------------------------------

section("36. Security considerations")

class SecureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    age: int = Field(ge=13, le=150)


print(SecureInput(username="safe_user-01", age=30))

try:
    SecureInput(
        username="<script>alert(1)</script>",
        age=30,
    )
except ValidationError as error:
    show_validation_error(error)

print(
    "Validation reduces malformed input, but it does not replace "
    "authentication, authorization, output encoding, rate limiting, "
    "database parameterization, or other security controls."
)


# ---------------------------------------------------------------------------
# 37. Production design example
# ---------------------------------------------------------------------------

section("37. Production-oriented model layering")

class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    price: Decimal = Field(gt=0, decimal_places=2)
    stock: int = Field(ge=0)


class ProductOutput(BaseModel):
    product_id: int
    name: str
    price: Decimal
    stock: int
    created_at: datetime


input_payload = {
    "name": "Laptop",
    "price": "79999.99",
    "stock": 15,
}

validated_input = ProductInput.model_validate(input_payload)

output = ProductOutput(
    product_id=1001,
    **validated_input.model_dump(),
    created_at=datetime.now(),
)

print("Validated input:", validated_input)
print("API output:", output.model_dump())


# ---------------------------------------------------------------------------
# 38. Testing validation behavior
# ---------------------------------------------------------------------------

section("38. Lightweight executable tests")

def test_valid_account() -> None:
    model = Account(
        username="valid_user",
        age=30,
        balance="100.00",
        email="user@example.com",
    )
    assert model.age == 30
    assert model.balance == Decimal("100.00")


def test_invalid_account_age() -> None:
    try:
        Account(
            username="valid_user",
            age=17,
            email="user@example.com",
        )
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError")


def test_nested_order_total() -> None:
    test_customer = Customer(
        customer_id=1,
        name="Test User",
        address={
            "street": "Main Street",
            "city": "Lucknow",
            "postal_code": "226001",
        },
    )

    test_order = ShoppingOrder(
        order_id="T-1",
        customer=test_customer,
        items=[
            {
                "sku": "A",
                "quantity": 2,
                "unit_price": "10.00",
            }
        ],
    )

    assert test_order.subtotal == Decimal("20.00")


test_valid_account()
test_invalid_account_age()
test_nested_order_total()
print("All executable assertions passed.")


# ---------------------------------------------------------------------------
# 39. A compact validation pipeline
# ---------------------------------------------------------------------------

section("39. Complete validation pipeline")

class RegistrationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    username: str = Field(
        min_length=3,
        max_length=30,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    email: str = Field(min_length=5, max_length=254)
    age: int = Field(ge=13, le=120)
    password: str = Field(min_length=12)
    password_confirmation: str = Field(min_length=12)

    @field_validator("username", "email")
    @classmethod
    def normalize_strings(cls, value: str) -> str:
        return value.lower()

    @field_validator("email")
    @classmethod
    def basic_email_check(cls, value: str) -> str:
        if value.count("@") != 1:
            raise ValueError("email must contain exactly one @")
        local_part, domain = value.split("@")
        if not local_part or "." not in domain:
            raise ValueError("email has an invalid basic structure")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> RegistrationRequest:
        if self.password != self.password_confirmation:
            raise ValueError("passwords do not match")
        return self


valid_registration = RegistrationRequest(
    username="Atul.Pandey",
    email="ATUL@EXAMPLE.COM",
    age=30,
    password="secure-password-2026",
    password_confirmation="secure-password-2026",
)

print(valid_registration.model_dump(exclude={"password", "password_confirmation"}))

try:
    RegistrationRequest(
        username="bad user",
        email="invalid",
        age=12,
        password="short",
        password_confirmation="different",
    )
except ValidationError as error:
    show_validation_error(error)


# ---------------------------------------------------------------------------
# 40. Final conceptual comparison
# ---------------------------------------------------------------------------

section("40. Core concepts demonstrated")

concepts = {
    "BaseModel": "Defines structured data models and validation boundaries.",
    "Field": "Adds defaults, constraints, metadata, aliases, and schema information.",
    "field_validator": "Validates or transforms individual fields.",
    "model_validator": "Validates relationships across multiple fields.",
    "Nested models": "Compose complex structures from smaller validated models.",
    "Annotated constraints": "Create reusable constrained domain types.",
    "ValidationError": "Provides structured information about invalid input.",
    "ConfigDict": "Controls model behavior such as extra fields and assignment validation.",
    "TypeAdapter": "Validates arbitrary Python types without requiring a BaseModel.",
    "computed_field": "Exposes derived values as model fields during serialization.",
    "model_dump": "Converts validated models into Python dictionaries.",
    "model_json_schema": "Produces JSON Schema describing the model.",
    "Strict validation": "Reduces implicit coercion when exact input types matter.",
}

for name, description in concepts.items():
    print(f"{name:24} -> {description}")


print("\nPydantic deep-dive execution completed successfully.")
