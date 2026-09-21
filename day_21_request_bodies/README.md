# Request Bodies with FastAPI and Pydantic

## Topic

This project studies HTTP request bodies with a focus on JSON payloads, Pydantic models, nested objects, and the distinction between required and optional fields.

The three implementations approach the same subject from different perspectives:

- Python demonstrates FastAPI request-body handling and Pydantic validation.
- JavaScript demonstrates how a client constructs, sends, parses, and validates JSON request bodies.
- C++ develops an industry-style order-processing case study using explicit domain models and validation.

The central idea is that a request body is not merely data received by a server. It is part of an API contract. A well-designed API defines the expected structure, validates incoming values, separates schema validation from business rules, and prevents untrusted client data from being treated as authoritative application state.

---

## HTTP request bodies

An HTTP request can carry information in several places.

A request such as `POST /orders` can contain:

- a URL path
- query parameters
- HTTP headers
- a request body

For a JSON API, the request body commonly contains structured application data.

A conceptual request may look like:

`POST /orders`

with the header:

`Content-Type: application/json`

and a body containing an object with fields such as `customer_id`, `shipping_address`, `items`, and `payment_method`.

The `Content-Type` header identifies the representation used for the body. For JSON APIs, `application/json` is the standard media type.

The server must not assume that the body is valid simply because the client sent JSON. Valid JSON syntax and valid application data are different things.

For example, this can be valid JSON:

`{"age": -500}`

but an application that requires an adult customer's age may reject it.

---

## JSON request bodies

JSON represents several fundamental data types:

- object
- array
- string
- number
- boolean
- null

A JSON object maps naturally to a Python dictionary.

For example:

`{"name": "Atul", "age": 30}`

corresponds conceptually to:

`{"name": "Atul", "age": 30}`

in Python.

A nested JSON object is represented by another object:

`{"address": {"city": "Lucknow", "country": "India"}}`

An array contains an ordered collection:

`{"items": [{"product_id": 101}, {"product_id": 102}]}`

These structures make JSON particularly suitable for API request bodies because real application requests frequently contain nested entities and collections.

---

## Why request-body validation is necessary

A client controls the request it sends. The server controls whether that request is acceptable.

A client may send:

- a missing field
- an unexpected field
- the wrong data type
- an empty string
- a negative number
- an excessively large number
- an empty array
- malformed nested data
- an invalid enum value
- a value that violates a business rule

The server therefore needs multiple levels of validation.

A useful conceptual sequence is:

1. Parse the request body.
2. Confirm that the body is structurally valid.
3. Validate required fields.
4. Validate field types.
5. Validate field constraints.
6. Validate nested objects.
7. Validate collections.
8. Validate relationships between fields.
9. Apply business rules.
10. Apply authentication and authorization.
11. Perform the requested operation.

Pydantic is particularly useful for the schema-validation portion of this process.

---

## Pydantic models

A Pydantic model defines the expected structure of data.

The Python implementation contains a simple model:

`BasicUser`

with fields:

`name: str`

and:

`age: int`

Creating the model with valid values produces a validated Python object.

If an invalid value is supplied, Pydantic raises a `ValidationError`.

This is important because the application code does not have to manually perform every basic type check.

A Pydantic model can therefore act as an executable description of an API's expected input structure.

---

## FastAPI request bodies

FastAPI integrates directly with Pydantic models.

A function such as:

`def create_user(request: UserCreate)`

tells FastAPI that `request` should be populated from the request body and validated against the `UserCreate` model.

The general process is:

1. The HTTP request reaches FastAPI.
2. FastAPI identifies the declared request-body model.
3. The body is parsed.
4. Pydantic validates the resulting data.
5. If validation succeeds, the endpoint receives the model instance.
6. If validation fails, FastAPI returns an HTTP validation response instead of calling the endpoint normally.

This keeps endpoint functions focused on application behavior rather than repeating low-level validation code.

---

## Required fields

A required field must be supplied by the client.

In Pydantic:

`name: str`

means that `name` is required.

If the request does not contain `name`, validation fails.

This is appropriate when an operation cannot be meaningfully performed without that value.

Examples of commonly required fields include:

- customer identifiers
- product identifiers
- usernames
- required addresses
- order items
- payment methods

The exact decision depends on the API contract.

---

## Optional fields

Optional fields require careful attention because "optional" and "nullable" are not exactly the same concept.

Consider:

`phone: str | None`

This says that `phone` may contain a string or `None`, but the field itself can still be required depending on the model declaration.

By contrast:

`phone: str | None = None`

gives the field a default value and makes it optional to supply.

This distinction is important for API design.

There are at least three meaningful states to consider:

1. Field is present with a normal value.
2. Field is present with `null`.
3. Field is absent.

An API should define whether those states have different meanings.

The Python implementation demonstrates this distinction with `RequiredVsOptionalExample`.

The JavaScript implementation demonstrates the related distinction between a missing property, whose value is `undefined`, and a property explicitly assigned `null`.

---

## Default values

A field can have a default.

For example:

`phone: str | None = None`

means that if the caller does not supply `phone`, the model receives `None`.

Another example in the Python implementation is:

`country: str = Field(default="India")`

This is useful when the API has a meaningful default that is safe to apply automatically.

Defaults should not be used merely to hide missing information. If the caller must explicitly provide a value for correctness, the field should remain required.

---

## Field constraints

Pydantic's `Field()` allows additional rules to be expressed close to the field declaration.

Examples in the Python implementation include:

`min_length`

`max_length`

`ge`

`le`

`gt`

and:

`decimal_places`

These rules can express constraints such as:

- string length
- minimum numeric value
- maximum numeric value
- strictly positive values
- decimal precision

For example:

`age: int = Field(ge=18, le=120)`

defines an acceptable numeric range.

This is more precise than merely declaring:

`age: int`

because the type alone does not describe the complete business requirement.

---

## Type validation

A type annotation communicates the expected data type.

Examples include:

`str`

`int`

`bool`

`date`

`datetime`

`Decimal`

`list[OrderItem]`

and another Pydantic model such as:

`Address`

Type validation reduces ambiguity between the client and server.

The Python implementation also demonstrates strict validation:

`quantity: int = Field(strict=True)`

Strict validation can reject a string such as `"10"` instead of treating it as an integer.

Normal Pydantic validation may perform controlled conversions in situations where the input is compatible with the declared type.

The appropriate choice depends on the API contract.

---

## Nested objects

Real request bodies frequently contain objects inside objects.

An order may contain a shipping address.

A customer may contain contact information.

A financial transaction may contain payer and beneficiary information.

The Python implementation represents this relationship with:

`Customer`

containing:

`address: Address`

The resulting request body conceptually contains:

`address: { street, city, state, postal_code }`

Pydantic validates the nested object independently and as part of the parent model.

This creates a reusable model structure.

For example, `ShippingAddress` can be used as a component of an order model rather than repeating every address field inside the order definition.

---

## Lists of nested objects

A request body can contain a collection of nested models.

The order example uses:

`items: list[ProductLine]`

Each element must satisfy the `ProductLine` model.

This allows a request to represent:

- one customer
- one shipping address
- many products
- one payment method
- one optional coupon

Nested collections are common in APIs for orders, invoices, portfolios, batches, transactions, permissions, and other domains.

The Python implementation also limits the number of items with:

`Field(min_length=1, max_length=100)`

This expresses both a minimum and maximum collection size.

---

## Enumerated values

Some fields should accept only a defined set of values.

The Python implementation defines:

`PaymentMethod`

with:

- `card`
- `upi`
- `bank_transfer`

An enumeration prevents arbitrary values such as `cash`, `unknown`, or `something_else` from silently becoming valid payment methods.

The C++ implementation provides equivalent explicit parsing with `PaymentMethod`.

The JavaScript implementation uses a `Set` containing the permitted strings.

The underlying concept is the same: the API contract should restrict the field to known values.

---

## Custom field validation

Basic type validation is not sufficient for every field.

The Python implementation contains a custom validator for `sku`.

It:

1. removes surrounding whitespace
2. converts the value to uppercase
3. checks that it starts with `SKU-`
4. rejects values that are too short

This demonstrates an important difference between type validation and domain-specific validation.

A string can be a perfectly valid Python `str` and still be an invalid SKU.

Custom validators are appropriate for rules that belong directly to the field.

---

## Model-level validation

Some rules involve more than one field.

The Python implementation uses `model_validator()` for cross-field rules.

The `DateRangeRequest` example verifies that:

`end_date >= start_date`

The order example also checks a relationship between:

`payment_method`

and:

`coupon_code`

The rule is that the `CASHONLY` coupon cannot be used with card payment.

This type of rule cannot be adequately represented by validating each field independently.

A useful distinction is:

- Field validator: one field's value
- Model validator: relationship among multiple fields
- Business service: broader application behavior, especially operations involving databases or external systems

---

## Business validation versus schema validation

Schema validation asks:

"Does this request have the correct structure and acceptable values?"

Business validation asks:

"Is this operation allowed according to the application's actual rules?"

For example:

`quantity > 0`

is a straightforward field constraint.

But:

"The customer cannot purchase more units than the inventory currently contains"

is usually a business rule because it depends on external application state.

Similarly:

"The customer may modify only their own order"

is an authorization rule, not a request-body schema rule.

A robust API keeps these concerns conceptually separate.

---

## Serialization

Serialization converts an application object into a transferable representation.

The Python implementation demonstrates:

`model_dump()`

which produces a dictionary.

It also demonstrates:

`model_dump_json()`

which produces JSON text.

Deserialization or validation performs the reverse conceptual operation: incoming structured data becomes an application model.

The JavaScript implementation demonstrates:

`JSON.stringify()`

for converting a JavaScript object into JSON text.

It uses:

`JSON.parse()`

to convert JSON text back into JavaScript data.

---

## Python implementation

The Python implementation is the most direct representation of FastAPI request-body concepts.

### Basic models

`BasicUser` demonstrates the simplest request-body schema.

### Required and optional values

`RequiredVsOptionalExample` demonstrates the distinction between nullable and genuinely optional fields.

### Field constraints

`RegistrationRequest` demonstrates minimum lengths, maximum lengths, numeric ranges, and email validation.

### Nested objects

`Customer` contains an `Address`.

### Nested lists

`ShoppingOrder` contains a list of `OrderItem` objects.

### Enumerations

`PaymentRequest` restricts the payment method to a defined set.

### Custom validation

`ProductCreateRequest` validates and normalizes a SKU.

### Model-level validation

`DateRangeRequest` and `OrderCreateRequest` demonstrate cross-field rules.

### Extra fields

The Python implementation demonstrates three explicit policies:

- `extra="ignore"`
- `extra="forbid"`
- `extra="allow"`

These policies should be selected deliberately according to the API contract.

### Partial updates

`UserUpdate` demonstrates a PATCH-style model where fields are optional.

The use of:

`model_dump(exclude_unset=True)`

is particularly important because it preserves the distinction between a field that was not supplied and a field that was explicitly supplied.

### FastAPI endpoints

The application defines endpoints for:

- user creation
- order creation
- user updates
- payment creation

The order endpoint also uses `response_model=OrderResponse`.

---

## JavaScript implementation

The JavaScript implementation focuses on the client and application-level perspective.

### JSON serialization

`JSON.stringify()` turns JavaScript objects into JSON request bodies.

### JSON parsing

`JSON.parse()` converts JSON text into JavaScript values.

### Manual validation

JavaScript does not automatically enforce an API schema merely because a value is an object.

The example therefore explicitly validates:

- required properties
- types
- ranges
- nested objects
- arrays
- array sizes
- payment methods

This illustrates why schema-validation systems are valuable in larger applications.

### Nested request bodies

`validateAddress()` validates an address nested inside a customer object.

### Collections

`validateOrder()` validates an array of order items.

### Partial updates

`applyPartialUpdate()` demonstrates a PATCH-style update where only supplied properties are changed.

### fetch()

`sendJsonRequest()` shows how a browser or Node.js client can send JSON using:

`Content-Type: application/json`

and:

`JSON.stringify(body)`

### Asynchronous behavior

The network examples use `async` and `await`.

`sendRequestWithTimeout()` also uses `AbortController` to cancel an operation that takes too long.

---

## C++ case study

The C++ implementation models an order-management service.

The scenario is intentionally more substantial than an isolated syntax demonstration.

A client submits an order containing:

- customer ID
- shipping address
- multiple products
- quantities
- prices
- payment method
- optional coupon

The system validates the request before accepting it.

### `ValidationResult`

This class-like structure collects validation failures instead of stopping at the first error.

This is useful for API validation because a client can receive multiple useful errors in one response.

### `ShippingAddress`

This is a nested request model.

It validates:

- recipient name
- street
- city
- state
- postal code
- country

### `ProductLine`

This represents one item inside the order's `items` collection.

It validates:

- positive product ID
- non-empty product name
- positive quantity
- maximum quantity
- positive price

### `OrderRequest`

This is the root request model.

It combines the nested address, item collection, payment method, and optional coupon.

It also demonstrates cross-field business validation.

### `std::optional`

C++ does not have Pydantic's optional-field syntax.

The case study uses:

`std::optional<std::string>`

to represent a value that may be absent.

This is an explicit representation of optional state.

### Money

The C++ implementation stores monetary values as integer paise.

For example:

`₹24.99`

is represented internally as:

`2499`

This avoids many of the precision problems associated with binary floating-point arithmetic for ordinary monetary calculations.

### `OrderService`

The service validates the request and constructs an `AcceptedOrder` only after validation succeeds.

This separates input validation from the resulting accepted domain state.

---

## Required versus optional fields across the three languages

The same conceptual distinction appears differently in each implementation.

| Concept | Python/Pydantic | JavaScript | C++ |
|---|---|---|---|
| Required string | `name: str` | Explicit property check | `std::string` plus validation |
| Nullable value | `str | None` | `null` | `std::optional<T>` can represent absence, while a separate design can represent explicit null |
| Optional value | `str | None = None` | Property may be absent | `std::optional<T>` |
| Nested object | Pydantic model | JavaScript object | Struct/class |
| Collection | `list[Model]` | Array | `std::vector<Model>` |
| Enumeration | `Enum` | `Set` or controlled values | `enum class` |
| Constraints | `Field()` | Explicit validation functions | Explicit validation functions |
| Cross-field validation | `model_validator()` | Validation function | Model/service validation |

The important point is not the syntax. The underlying API design problem is the same.

---

## Missing versus null

A request may distinguish between a missing property and an explicit null value.

For example:

`{"phone": null}`

is different from:

`{}`

depending on the API contract.

This distinction becomes particularly important for update operations.

Suppose a profile contains:

`phone = "+91-9876543210"`

A PATCH request with:

`{"phone": null}`

might mean:

"Remove the phone number."

A PATCH request with:

`{}`

might mean:

"Do not change the phone number."

Pydantic's `exclude_unset=True` is useful for preserving this distinction during partial updates.

---

## Create models versus update models

A common API design mistake is to use the same request model for every operation.

Creation and modification often have different requirements.

For example, creating a user may require:

- username
- email
- display name
- age

A partial update may allow only:

- display name
- email
- age

The Python implementation therefore uses separate:

`UserCreate`

and:

`UserUpdate`

models.

This produces a clearer API contract.

---

## Response models

Request models describe incoming data.

Response models describe outgoing data.

These responsibilities should not automatically be combined.

For example, a user-creation request might contain a password, while a public response should not expose that password.

The Python implementation uses:

`OrderResponse`

to explicitly define the order information returned by the API.

This creates a boundary between input data and output data.

---

## Extra fields

An API must decide what happens when a client supplies fields that are not part of the documented request model.

Possible strategies include:

### Ignore

Unknown fields are discarded.

This can make clients more tolerant but can also hide client-side mistakes.

### Forbid

Unknown fields cause validation failure.

This creates a stricter contract and can reveal client bugs earlier.

### Allow

Unknown fields are retained.

This can be useful for intentionally extensible structures but should be used carefully because arbitrary client-controlled data can complicate validation and downstream processing.

The Python implementation demonstrates all three policies explicitly.

---

## Validation errors

A useful validation system should communicate:

- which field failed
- why it failed
- what kind of value was expected

The Python/FastAPI implementation returns structured validation information.

The C++ implementation stores multiple error messages in `ValidationResult`.

The JavaScript implementation collects validation errors into arrays.

For nested data, error locations are especially useful.

For example:

`items[2].quantity`

is much more informative than simply saying:

`invalid request`

---

## Edge cases demonstrated

The implementations cover several important edge cases.

### Missing required field

A required field is absent.

### Null value

A field receives `null` where a normal value is required.

### Empty string

A string exists but contains no meaningful content.

### Empty collection

An order contains zero items even though at least one item is required.

### Negative quantity

A numeric field violates its lower bound.

### Excessively large quantity

A valid integer exceeds the application's permitted range.

### Invalid enumeration

A payment method is outside the supported set.

### Invalid nested object

An address contains missing or invalid fields.

### Invalid cross-field combination

A coupon and payment method conflict with one another.

### Unexpected fields

The request contains properties outside the declared schema.

---

## Common mistakes

### Treating JSON parsing as validation

JSON parsing answers whether the body is syntactically valid JSON.

It does not answer whether the application should accept the data.

### Making everything optional

If every field is optional, the API contract becomes weak and invalid states become easier to create.

### Confusing nullable and optional

A nullable field can accept `null`.

An optional field does not have to be supplied.

These are related but different concepts.

### Trusting client-supplied prices

A client may submit:

`unit_price = 1`

even if the server's actual catalog price is ₹2,499.

The server should use authoritative pricing data when the server owns the price.

### Trusting client permissions

A request containing:

`is_admin: true`

must not automatically grant administrative privileges.

Authorization must be determined by trusted server-side identity and policy.

### Using one model for every purpose

Input, output, database, and internal domain objects may have different responsibilities.

### Performing expensive operations in validators

Validation should generally be predictable and focused.

Database queries, external API calls, and other expensive or side-effecting operations are usually better handled in service/application layers.

### Forgetting collection limits

An API that accepts unlimited nested arrays can receive unnecessarily large requests.

Collection size limits provide a clear contract and reduce resource consumption.

---

## Business rules versus validation rules

Consider these two rules:

`quantity must be greater than zero`

and:

`customer cannot purchase more units than available inventory`

The first can normally be represented as a schema constraint.

The second depends on current application state.

This difference is fundamental.

### Schema validation

Examples:

- type
- required field
- minimum length
- maximum length
- numeric range
- nested structure
- enum value

### Business validation

Examples:

- inventory availability
- account balance
- order ownership
- coupon eligibility
- transaction limits
- state transitions

### Authorization

Examples:

- whether the authenticated user owns the resource
- whether the user has administrative permission
- whether the operation is allowed for the user's role

These layers should not be treated as interchangeable.

---

## Security considerations

Request-body validation is an important security control, but it is not a complete security system.

Important practices include:

- Validate all client-controlled input.
- Restrict string lengths.
- Restrict collection sizes.
- Validate numeric ranges.
- Restrict enumerated values.
- Reject impossible structures.
- Do not trust client-supplied prices when authoritative prices exist on the server.
- Do not use request fields to grant permissions.
- Keep authentication separate from request validation.
- Keep authorization separate from request validation.
- Avoid exposing sensitive input in responses.
- Avoid logging secrets or complete sensitive request bodies unnecessarily.
- Use HTTPS for production communication.
- Apply appropriate request-size limits.
- Consider rate limiting for public APIs.

Validation protects the application's input boundary. Authentication determines who the caller is. Authorization determines what that caller may do.

---

## Performance considerations

Request validation consumes CPU and memory because incoming data must be parsed, inspected, converted, and sometimes normalized.

For normal API workloads, this processing is part of establishing a reliable contract.

Performance considerations include:

- limit maximum request-body size
- limit maximum array sizes
- limit string lengths
- avoid unnecessary repeated validation
- avoid expensive I/O inside validators
- avoid unnecessarily large response models
- avoid serializing data that clients do not need
- benchmark representative workloads
- measure actual application performance before changing validation behavior

The C++ implementation includes a local validation benchmark using an order containing 100 items.

That benchmark demonstrates the cost of repeatedly traversing a structured object, but it should not be interpreted as a production HTTP benchmark. Real API performance also includes network, HTTP parsing, JSON parsing, authentication, database operations, concurrency, allocation, and operating-system overhead.

---

## Monetary values

Money deserves special consideration.

Python's `Decimal` is used in the order examples because decimal arithmetic is more appropriate than ordinary binary floating-point arithmetic for many financial calculations.

JavaScript's `Number` is a binary floating-point representation. The JavaScript implementation therefore rounds its demonstration result to two decimal places and explicitly notes that production financial applications can use integer minor units or a suitable decimal arithmetic solution.

The C++ case study uses integer paise.

For example:

`₹2499.00`

becomes:

`249900` paise.

The broader principle is to choose a monetary representation deliberately rather than assuming floating-point arithmetic is automatically suitable for financial data.

---

## Pydantic model composition

The Python implementation demonstrates model composition.

`OrderCreateRequest` contains:

`ShippingAddress`

and:

`ProductLine`

The latter is itself repeated inside a list.

This creates a hierarchy:

`OrderCreateRequest`

contains:

`ShippingAddress`

and:

`list[ProductLine]`

This composition is valuable because individual models can represent coherent concepts and then be reused as building blocks.

---

## Request-body design principles

A well-designed request body should have:

- a clear structure
- explicit required fields
- deliberately chosen optional fields
- sensible defaults
- constrained values
- predictable nested structures
- controlled collections
- clear enumerations
- meaningful validation errors
- a separation between schema and business rules
- a separation between input and output contracts

The schema should represent what the endpoint genuinely needs rather than exposing the entire internal database model.

---

## Python, JavaScript, and C++ perspectives

### Python

Python with FastAPI and Pydantic provides a compact way to express request schemas and validation rules.

The type annotations and Pydantic models closely correspond to the API contract.

FastAPI then connects those models to HTTP endpoint behavior.

This makes Python particularly useful for demonstrating the relationship between API endpoints and declarative request schemas.

### JavaScript

JavaScript demonstrates the client perspective particularly well.

The `fetch()` API shows how a browser or Node.js program constructs a JSON request and sends it to a server.

The examples also demonstrate that ordinary JavaScript objects do not automatically enforce the server's schema.

### C++

C++ demonstrates how the same concepts can be implemented explicitly at the domain-model and service level.

The case study uses structs, classes, `std::vector`, `std::optional`, `enum class`, validation results, and integer-based money representation.

This makes the architectural boundaries particularly visible.

---

## Practical request lifecycle

A typical JSON request-body lifecycle can be understood as:

1. The client creates an application object.
2. The client serializes it to JSON.
3. The client sends it using HTTP.
4. The server receives the request.
5. The server checks the media type and request limits.
6. The server parses the JSON.
7. The server validates the root structure.
8. The schema validates individual fields.
9. Nested objects and arrays are validated.
10. Cross-field constraints are checked.
11. Business rules are evaluated.
12. Authentication and authorization are enforced.
13. The application performs the requested operation.
14. A response model defines the returned representation.
15. The server serializes the response.

The request body therefore represents one stage in a larger application pipeline.

---

## Important distinction: validation does not equal authorization

A request can be perfectly valid according to its schema and still be forbidden.

For example, this request may be structurally valid:

`{"order_id": 9001, "status": "cancelled"}`

The server may still reject it if the authenticated user does not own order `9001` or lacks permission to cancel it.

Pydantic can validate the structure.

It cannot, by itself, decide whether a particular authenticated user has permission to perform an operation.

That decision belongs to the application's authorization logic.

---

## Important distinction: validation does not equal persistence

A Pydantic model is not automatically a database record.

A request model describes accepted input.

The application may then:

- check current database state
- apply business rules
- calculate authoritative values
- create a database record
- trigger an external operation
- return a response model

Keeping these responsibilities distinct reduces coupling between the API boundary and the persistence layer.

---

## Production considerations

A production request-body implementation should consider:

- request size limits
- timeout policies
- authentication
- authorization
- rate limiting
- structured validation errors
- logging
- monitoring
- sensitive-data handling
- database constraints
- transaction boundaries
- idempotency for operations where duplicate requests matter
- versioning of public API contracts
- backwards compatibility
- response filtering
- appropriate status codes
- schema documentation

FastAPI's request models form only one component of this larger system.

---

## HTTP status codes in the examples

The Python FastAPI demonstration shows successful and invalid requests.

Typical API behavior includes:

`200 OK`

for successful operations where an existing resource is returned or updated.

`201 Created`

is commonly appropriate when a new resource is successfully created.

`400 Bad Request`

can represent malformed requests in some API designs.

`422 Unprocessable Content`

is commonly associated with validation failures in FastAPI's request-validation behavior.

The exact status-code policy should be consistent across an API.

---

## Relationship between the implementations

The three programs intentionally do not duplicate every example.

The Python implementation concentrates on:

- Pydantic
- FastAPI
- declarative models
- nested schemas
- validation
- serialization
- response models
- API testing

The JavaScript implementation concentrates on:

- JSON serialization
- JSON parsing
- client-side request construction
- `fetch()`
- asynchronous requests
- request cancellation
- explicit validation
- partial updates

The C++ implementation concentrates on:

- explicit domain models
- validation architecture
- nested data structures
- `std::optional`
- enumerations
- monetary representation
- service-layer processing
- performance measurement
- industry-style order processing

Together they demonstrate that request-body design is a language-independent API engineering problem, while each language provides different mechanisms for expressing the solution.

---

## File structure

A practical project can contain:

- `request_bodies.py`
- `request-bodies.js`
- `request_bodies.cpp`
- `README.md`

The Python file contains the FastAPI application and executable demonstrations.

The JavaScript file contains client-side and application-level demonstrations.

The C++ file contains the order-processing case study.

This README documents the concepts represented by all three implementations.

---

## Key conceptual distinctions

| Concept | Meaning |
|---|---|
| JSON parsing | Converts JSON text into structured data |
| Request body | Data carried inside an HTTP request |
| Schema validation | Checks whether data follows the declared structure |
| Required field | Must be supplied |
| Nullable field | May contain `null` |
| Optional field | May be omitted |
| Default | Value used when a field is not supplied |
| Nested object | Object contained inside another object |
| Nested collection | Array containing structured objects |
| Field constraint | Rule applied to one field |
| Model validation | Rule involving multiple fields |
| Business rule | Application-specific domain requirement |
| Authentication | Establishes caller identity |
| Authorization | Determines what the caller may do |
| Serialization | Converts application data into a transferable representation |
| Deserialization | Converts external representation into application data |
| Response model | Defines the public structure of returned data |

Understanding these distinctions prevents many common API design errors.

---

## Technical outcome represented by the code

The Python implementation demonstrates how FastAPI and Pydantic turn a JSON request body into a strongly defined application model.

The JavaScript implementation demonstrates how clients create and transmit the same kind of structured body and why client-side validation does not replace server-side validation.

The C++ implementation demonstrates how the same principles can be implemented explicitly through domain structures, validation functions, service logic, optional values, enumerations, collections, and deterministic money representation.

The common architectural principle is that external request data should cross into application logic through a deliberate validation boundary rather than being trusted implicitly.
