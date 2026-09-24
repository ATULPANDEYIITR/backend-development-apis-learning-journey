# Pydantic Deep Dive

## Topic scope

This study examines Pydantic 2.x as a runtime data-validation and data-modeling system. The implementations focus on `BaseModel`, `Field`, field validators, model validators, nested models, constrained values, custom validation, serialization, schema generation, strict validation, configuration, and production-oriented validation boundaries.

The Python implementation is the primary Pydantic implementation. The JavaScript implementation models equivalent validation patterns using standard JavaScript because Pydantic itself is a Python library. The C++ implementation develops an industry-style order-validation boundary using the C++17 standard library.

## Pydantic and runtime validation

Python type annotations normally describe the intended structure of data, but ordinary Python type hints do not automatically validate arbitrary runtime input.

Pydantic adds a runtime validation layer. A Pydantic model receives input, validates and converts supported values, applies constraints, executes custom validation logic, and produces a structured Python object.

A typical conceptual flow is:

`untrusted input → validation → normalized model → application logic → serialization`

This separation is important because application code should not have to repeatedly check whether every incoming value has the expected structure.

Pydantic is particularly useful at boundaries such as:

- HTTP API requests
- configuration data
- database-adjacent data transfer objects
- event payloads
- command objects
- structured files
- external service responses
- message queues
- application settings

Validation is not a replacement for authentication, authorization, secure database access, output encoding, or other security controls.

## BaseModel

`BaseModel` is the central abstraction used to define structured Pydantic models.

The Python implementation begins with simple models such as `User`, `Product`, `Account`, and `Profile`.

For example, the `User` model declares `name: str` and `age: int`. Constructing the model creates an object whose fields have been processed according to Pydantic's validation rules.

The important distinction is between:

- a Python type annotation
- a Pydantic model
- runtime input
- validated model state

A model can be created using ordinary keyword arguments:

`User(name="Atul", age=30)`

Existing data can also be passed through `model_validate()`:

`User.model_validate({"name": "Atul", "age": 30})`

JSON input can be processed with `model_validate_json()`.

## ValidationError

Invalid input raises `ValidationError`.

A validation error is structured rather than being only a single message. `error.errors()` returns information about each failure, including its location, error type, and human-readable message.

The Python implementation deliberately prints:

- `loc`
- `type`
- `msg`

This is useful for APIs because clients can receive precise information about which part of a request failed.

Nested validation also produces paths that identify where the failure occurred.

For example, a postal-code problem inside a customer's address is conceptually different from an invalid customer identifier. Structured error locations preserve that distinction.

## Field

`Field()` adds constraints and metadata to model fields.

The Python implementation uses constraints such as:

- `gt`: greater than
- `ge`: greater than or equal to
- `lt`: less than
- `le`: less than or equal to
- `min_length`
- `max_length`
- `pattern`
- `max_digits`
- `decimal_places`
- `description`
- `alias`
- `default`
- `default_factory`

Examples from the implementation include:

`age: int = Field(ge=18, le=120)`

and:

`sku: str = Field(pattern=r"^[A-Z]{3}-\d{4}$")`

These constraints allow many common validation rules to remain declarative rather than being implemented manually inside business logic.

## Required fields, nullable fields, and defaults

A field that permits `None` is not necessarily optional in the sense of being omittable.

The implementation demonstrates:

`nickname: str | None`

and:

`bio: str | None = None`

The first form permits `None` but still requires the field to be supplied. The second supplies a default, so omission is permitted.

This distinction is important when designing API contracts.

## Constrained values

Constraints can be attached directly to fields or expressed through `Annotated`.

The Python implementation defines reusable types such as:

`PositiveInt = Annotated[int, Field(gt=0)]`

and:

`Percentage = Annotated[float, Field(ge=0, le=100)]`

This approach makes domain rules reusable.

A model can then declare:

`quantity: PositiveInt`

instead of repeating the same constraint every time.

## Field validators

`@field_validator` is used when validation or transformation applies to one or more individual fields.

The registration example demonstrates three common uses:

- trimming and normalizing a username
- normalizing an email address
- enforcing password length

A field validator can therefore perform both validation and normalization.

A validator should generally remain focused on the field or fields it is responsible for. Rules that depend on relationships between several fields belong more naturally in a model validator.

## Before and after validation

Pydantic supports validator modes that affect when custom validation executes.

The `Measurement` example uses:

`mode="before"`

to process raw input before normal Pydantic type validation.

It also uses:

`mode="after"`

to validate the already parsed Python value.

This distinction matters when the custom logic needs to inspect raw representations or needs the guarantees provided by normal type parsing.

A `before` validator is useful for input normalization and migration of legacy payload formats. An `after` validator is useful when the custom rule should operate on a value that has already been converted to its declared Python type.

## Model validators

`@model_validator` handles rules involving the complete model.

The `DateRange` model checks that `end_date` is not earlier than `start_date`.

The `Payment` model checks relationships between:

- amount
- currency
- payment method
- transaction reference

The `LoanApplication` model demonstrates another cross-field business rule involving annual income, requested amount, employment type, and term.

These rules cannot be represented adequately by validating each field independently because their meaning depends on multiple values simultaneously.

## Before model validators

A `mode="before"` model validator receives the raw model input.

The `FlexibleUser` example supports a legacy `user_name` input and converts it to the current `username` field.

This pattern can be useful when migrating API contracts, although input compatibility should be deliberate because accepting multiple representations increases the number of states a system must maintain.

## Nested models

Pydantic models can contain other Pydantic models.

The Python implementation creates:

- `Address`
- `Customer`
- `LineItem`
- `ShoppingOrder`
- `Category`

`Customer` contains an `Address`.

`ShoppingOrder` contains a `Customer` and a list of `LineItem` objects.

This provides composition rather than putting every field into one large model.

Nested models improve separation of concerns because each component can own its own validation rules.

## Lists of nested models

A declaration such as:

`items: list[LineItem]`

means that each item is expected to satisfy the `LineItem` model.

The `ShoppingOrder` example demonstrates nested collection validation and also calculates a derived subtotal.

This is representative of API payloads in which an outer request contains a collection of structured objects.

## Recursive models

The `Category` model contains:

`children: list[Category]`

This creates a recursive data structure.

Recursive models are useful for:

- category trees
- organizational hierarchies
- file structures
- dependency trees
- nested comments
- abstract syntax trees

The important design issue is that recursive data must have a sensible termination structure when serialized or processed.

## Default values and default_factory

The `Session` example uses `default_factory` for generated values.

`default_factory=uuid4` creates a fresh identifier for each model instance.

`default_factory=list` creates a fresh list for each instance.

For generated or mutable defaults, `default_factory` makes the intended per-instance behavior explicit.

## Configuration with ConfigDict

Pydantic model behavior can be controlled through `ConfigDict`.

The implementation demonstrates:

`extra="forbid"`

`extra="ignore"`

`extra="allow"`

and:

`validate_assignment=True`

`extra="forbid"` is useful for strict API contracts because unexpected fields are rejected.

`extra="ignore"` discards unknown fields.

`extra="allow"` preserves additional data.

The correct policy depends on the boundary being modeled. A public API with a strict contract may prefer rejection, while a deliberately extensible payload may need another policy.

`validate_assignment=True` causes later attribute assignment to pass through validation.

## Strict validation

Pydantic can perform normal type parsing or stricter type validation.

The implementation demonstrates `StrictInt`, `StrictFloat`, `StrictBool`, and `StrictStr`.

For example, a normal integer field may accept a string representation in contexts where Pydantic's conversion rules permit it, while `StrictInt` requires an actual integer.

A model can also use:

`ConfigDict(strict=True)`

Strictness is valuable when implicit conversion could hide input mistakes or when the external contract requires exact types.

The trade-off is that strict validation can reject inputs that could otherwise be safely converted.

## Aliases

API naming conventions frequently differ from Python naming conventions.

The `APIUser` model demonstrates aliases such as:

`user_id: int = Field(alias="userId")`

This allows Python code to use `user_id` while accepting or producing an API representation using `userId`.

`populate_by_name=True` allows the model to work with the declared Python name as well.

Aliases are especially useful when integrating Python systems with external APIs using naming conventions such as camelCase.

## Serialization

The Python implementation uses:

- `model_dump()`
- `model_dump_json()`

These convert validated model state into dictionary or JSON representations.

`by_alias=True` allows serialized output to use aliases.

Serialization should be considered separately from validation. A model can be valid internally while requiring a different representation at an external boundary.

## JSON Schema

Pydantic can generate JSON Schema through:

`model_json_schema()`

The Python implementation generates a schema for the nested `ShoppingOrder` model and inspects its top-level properties.

JSON Schema describes structural expectations such as:

- object properties
- required fields
- primitive types
- constraints
- nested definitions

This makes Pydantic models useful in API systems where a machine-readable contract is valuable.

## TypeAdapter

`TypeAdapter` validates types that do not need to be represented as a complete `BaseModel`.

The Python implementation uses a `TypeAdapter` for a constrained list of positive integers.

This is useful for data such as:

- lists
- dictionaries
- unions
- scalar constrained types
- other type expressions

A reusable adapter should be created once when it will be used repeatedly in performance-sensitive code rather than reconstructed unnecessarily inside a hot loop.

## Computed fields

The `Rectangle` and `LineItem` examples use `computed_field`.

A computed field represents a value derived from other model state.

Examples include:

- rectangle area
- rectangle perimeter
- line-item total
- order subtotal

A computed field should not be confused with stored input. It is derived from the model's existing state.

## Custom validation

Built-in constraints cannot represent every domain rule.

The implementation therefore demonstrates custom validators for:

- usernames
- email structure
- phone numbers
- coupon normalization
- password matching
- duplicate product detection
- date relationships
- payment rules

Custom validation should express business requirements clearly and should avoid mixing unrelated concerns.

For example, a password equality rule belongs in a model validator because it depends on two fields.

## Validation context

The `ContextAwareUser` example demonstrates validation context.

The validator receives context containing reserved usernames.

This allows a validation rule to use information that is external to the individual field value.

Context can be useful for environment-dependent or request-dependent rules, but such rules should remain understandable and deterministic enough for testing.

## Discriminated unions

The transaction example models two different payment structures:

- card payment
- bank payment

The discriminator is `method`.

A discriminated union allows the input structure to determine which model applies.

This is preferable to a large model containing many optional fields when the input naturally represents one of several distinct variants.

## Generic models

`APIResponse[T]` demonstrates generic model design.

The model defines:

- `success`
- `data`
- `message`

The `data` field can be parameterized with another model.

This pattern is useful for standardized API response envelopes where the payload type changes between endpoints.

## model_construct

The Python implementation deliberately contrasts normal construction with:

`model_construct()`

Normal model creation performs validation.

`model_construct()` bypasses normal validation and therefore must not be treated as a general replacement for validation.

It can be appropriate for trusted, already validated data in specialized circumstances.

Using it on untrusted input defeats the purpose of a validation boundary.

## Error inspection

The implementation uses `error.errors()` and `error.error_count()`.

Structured errors are particularly valuable in API applications because an application can transform them into a response containing field-level problems rather than exposing only one generic failure.

The nested order example can produce locations conceptually similar to:

`shipping_address.postal_code`

or:

`items[0].quantity`

Precise locations make debugging and client-side error presentation easier.

## Python implementation

The Python file is the primary demonstration of Pydantic itself.

It covers:

- `BaseModel`
- `Field`
- constrained values
- `Annotated`
- `field_validator`
- `model_validator`
- before and after validation
- nested models
- recursive models
- lists of nested models
- `ConfigDict`
- strict types
- aliases
- serialization
- JSON Schema
- `TypeAdapter`
- validation context
- discriminated unions
- generic models
- computed fields
- `model_construct`
- structured errors
- executable tests
- production-oriented API models

The `CreateOrderRequest` model is particularly representative of an API validation boundary. It validates the customer identifier, nested shipping address, product collection, coupon code, unknown fields, and duplicate products.

## JavaScript implementation

The JavaScript file does not attempt to reproduce Pydantic internally.

Instead, it demonstrates why a JavaScript client or service may need a validation layer that conceptually corresponds to a Pydantic model on the Python side.

The implementation includes:

- primitive validators
- minimum and maximum lengths
- numeric constraints
- regular-expression constraints
- nested validation
- collection validation
- normalization
- cross-field rules
- strict type checks
- unknown-field rejection
- discriminated unions
- serialization
- schema representation
- structured validation errors
- executable assertions

The JavaScript model architecture uses a `ValidationModel` base class and model-specific `validate()` methods.

The `CreateOrderRequest` implementation mirrors the central Python API example while using JavaScript-native data structures.

The architectural lesson is important: client-side validation and server-side validation can use similar rules, but the server-side validation boundary remains authoritative.

## C++ case study

The C++ program models a realistic order-management API boundary.

The scenario accepts:

- customer ID
- shipping address
- product requests
- optional coupon code

The system validates those values before creating an internal `Order`.

### Major components

`ValidationError` stores:

- path
- error type
- message

`ValidationException` carries a collection of validation errors.

`Address` validates and normalizes address data.

`ProductRequest` validates product identifiers and quantities.

`CreateOrderRequest` combines the nested address and product collection and applies model-level business rules.

`Order` represents a validated domain object and calculates total units.

### Nested validation

`CreateOrderRequest` contains an `Address` and a collection of `ProductRequest` objects.

This corresponds to Pydantic nested models.

Each component validates its own invariants before the outer object is accepted.

### Constrained values

The C++ implementation expresses constraints through explicit validation logic.

Examples include:

- customer ID greater than zero
- quantity greater than zero
- quantity no greater than 1000
- product collection containing at least one item
- maximum collection size
- six-digit postal code
- coupon length limits

Unlike Pydantic's declarative `Field` syntax, the C++ standard library does not provide a direct equivalent of Pydantic's model declaration system, so these rules are represented through explicit functions and constructors.

### Custom validation

The C++ implementation performs domain-specific validation for:

- duplicate product IDs
- coupon normalization
- postal code structure
- address fields
- request relationships

This demonstrates the same conceptual distinction between simple field constraints and model-level rules.

### Normalization

Input strings are passed through `trim()`.

Coupon codes are normalized with `toUpper()`.

This means the internal model receives a canonical representation rather than repeatedly processing formatting differences throughout the business logic.

### Error aggregation

Rather than stopping at the first problem, validation functions collect multiple `ValidationError` objects.

This resembles Pydantic's structured validation output.

For example, a request can contain both an invalid customer ID and an invalid product quantity, allowing the caller to receive multiple errors at once.

### Performance considerations

Duplicate product detection uses `std::unordered_set`.

Average duplicate detection is approximately O(n), compared with O(n²) for a naive pairwise comparison.

For a collection of `n` products:

- validation of each independent product is approximately O(n)
- duplicate detection with a hash set is approximately O(n) average case
- serialization is approximately O(n) in the amount of output produced

Memory usage for duplicate detection is approximately O(n).

The exact performance characteristics depend on the implementation, input distribution, allocation behavior, and workload.

## Important distinctions

### Validation versus normalization

Validation asks whether data satisfies a rule.

Normalization transforms acceptable data into a canonical representation.

For example, trimming `"  save20  "` and converting it to `"SAVE20"` is normalization.

Rejecting a coupon containing fewer than three characters is validation.

The two operations can occur in the same validation boundary but represent different responsibilities.

### Field validation versus model validation

Field validation concerns one or more individual fields in isolation.

Model validation concerns relationships between fields.

`age >= 18` is a field-level constraint.

`end_date >= start_date` is a model-level relationship.

`password == password_confirmation` is a model-level relationship.

### Coercion versus strict validation

Normal Pydantic validation may perform useful conversions.

Strict validation intentionally reduces or removes such conversions.

Coercion is convenient for ordinary API input but can hide incorrect types.

Strict validation is useful when type fidelity is part of the contract.

The appropriate choice depends on the data boundary.

### Validation versus security

Validation can reject malformed or unexpected input.

It does not establish identity.

It does not establish permissions.

It does not prevent every injection attack.

It does not replace secure database access.

It does not replace output encoding.

It does not replace rate limiting.

A validated string can still represent a value that a user is not authorized to submit.

## Edge cases

The implementations explicitly examine several edge cases:

- negative numbers
- zero values
- empty strings
- missing required fields
- nullable fields
- invalid postal codes
- malformed email structures
- duplicate products
- unexpected fields
- invalid enum values
- invalid discriminated-union variants
- mismatched passwords
- invalid date ranges
- mutable collection defaults
- validation bypass through `model_construct`

Edge cases matter because validation code often appears correct when tested only with normal input.

## Common mistakes

### Treating type hints as runtime validation

A type annotation alone does not provide the complete validation behavior supplied by a Pydantic model.

### Assuming nullable means optional

`str | None` allows `None`, but a field without a default may still be required.

### Putting all validation in one large validator

Large validators become difficult to test and maintain.

Field-specific rules are generally clearer in field validators or `Field` constraints. Cross-field rules belong in model validators.

### Using model_construct on untrusted input

`model_construct()` bypasses normal validation and should therefore not be used as an unvalidated input pathway.

### Allowing unknown fields unintentionally

An API may silently accept misspelled or obsolete fields if its extra-field policy is too permissive.

For strict contracts, `extra="forbid"` can expose these problems early.

### Confusing client-side validation with server-side trust

JavaScript validation can improve user experience, but a server must validate the incoming request independently.

A client can be modified or bypassed.

### Writing overly broad custom validators

A custom validator should have a clear responsibility. When unrelated business rules accumulate inside one function, failures become harder to understand and tests become less precise.

## Limitations

Pydantic validates data according to declared models and custom rules, but it does not automatically understand every business rule.

A model does not automatically know:

- whether a user is authorized
- whether a product actually exists in a database
- whether an account has sufficient funds
- whether a coupon is currently active
- whether an external service is available
- whether a particular business action is legally permitted

Those concerns generally require application services, databases, external systems, or other domain components.

Validation also does not guarantee that data remains valid after model creation if mutable state is modified in ways that bypass configured assignment validation.

## Best practices

Keep validation models close to the boundary where external data enters the application.

Use `Field` for declarative constraints that naturally belong to individual fields.

Use `Annotated` for reusable constrained types.

Use `field_validator` for field-specific normalization and validation.

Use `model_validator` for relationships between fields.

Use nested models when a payload contains meaningful substructures.

Use `extra="forbid"` when silently accepting unknown API fields would be undesirable.

Use strict types when implicit conversion could create ambiguity.

Use `default_factory` for generated mutable values and per-instance collections.

Inspect structured `ValidationError` data when building API error responses.

Keep business rules understandable and testable.

Avoid using validation models as a substitute for the entire domain model when the application's domain contains behavior and persistence concerns that should remain separate.

## Performance considerations

Pydantic validation has computational cost because input must be inspected, converted where applicable, and checked against constraints.

Useful design considerations include:

- validate once at the boundary rather than repeatedly validating the same trusted object
- reuse `TypeAdapter` instances when repeatedly validating the same type
- avoid unnecessary model reconstruction
- use efficient data structures for custom collection-level rules
- avoid expensive external operations inside ordinary field validators
- keep validation logic deterministic where practical
- benchmark real workloads before optimizing

The C++ case study demonstrates why data structures matter. A hash set provides average O(n) duplicate detection, while naive pairwise comparison is O(n²).

The Python model hierarchy also separates nested validation into focused components, making both reasoning and testing more manageable.

## Security considerations

Validation is a security-relevant boundary but is not a complete security mechanism.

Useful validation practices include:

- constrain input lengths
- reject malformed structures
- reject unexpected fields when appropriate
- validate numeric ranges
- validate enumerated values
- normalize values consistently
- avoid accepting unnecessarily broad input formats
- avoid logging sensitive values
- avoid treating validated input as automatically authorized input

The Python example explicitly states that validation does not replace authentication, authorization, output encoding, rate limiting, or parameterized database access.

The JavaScript example demonstrates strict type validation because JavaScript's dynamic typing can otherwise permit values that are semantically different from the intended API contract.

The C++ example demonstrates explicit input rejection before constructing domain objects.

## Production implementation considerations

A production Pydantic architecture often benefits from distinguishing several layers:

`transport input → Pydantic request model → application service → domain logic → persistence`

The request model should describe what the external interface accepts.

The application service should coordinate operations.

The domain layer should enforce business invariants that require domain behavior or external state.

Persistence models should reflect database concerns rather than being forced to serve every purpose.

This separation prevents a validation schema from becoming an uncontrolled mixture of HTTP, database, authorization, and business logic.

## Python, JavaScript, and C++ comparison

| Concern | Python with Pydantic | JavaScript companion | C++ case study |
| --- | --- | --- | --- |
| Runtime type validation | Native Pydantic support | Explicit validators | Explicit validators |
| Declarative field constraints | `Field` and `Annotated` | Validator functions | Validation functions |
| Nested models | `BaseModel` composition | Model classes | C++ classes |
| Field validators | `field_validator` | Field-specific functions | Class validation functions |
| Cross-field validation | `model_validator` | Model `validate()` | Request-level validation |
| Structured errors | `ValidationError` | Error arrays | `ValidationException` |
| Serialization | `model_dump`, JSON methods | `JSON.stringify` | Explicit serialization |
| JSON Schema | Native schema generation | Manually represented schema | No native Pydantic-equivalent |
| Strictness | Strict types and configuration | Explicit type checks | Static and runtime checks |
| Generic structures | Generic Pydantic models | JavaScript object patterns | C++ templates where appropriate |
| Primary purpose in this study | Actual Pydantic implementation | Client/application validation architecture | Industry-style systems case study |

## Real-world relevance

The central concepts apply to many systems that exchange structured data.

An API endpoint receiving an order request can use a Pydantic request model to verify:

- required fields exist
- identifiers have valid ranges
- strings meet length restrictions
- nested addresses have valid structures
- collections contain valid elements
- values belong to permitted sets
- related fields satisfy business rules

Once validation succeeds, application logic can work with a known structure instead of repeatedly handling malformed raw input.

The same architecture appears in configuration processing, event consumers, ETL boundaries, service integrations, and data ingestion systems.

## Relationship between the three implementations

The Python implementation demonstrates the actual Pydantic mechanisms.

The JavaScript implementation demonstrates how similar validation concepts can be applied at another application boundary and why a frontend or JavaScript service may need compatible validation rules.

The C++ implementation demonstrates how the architectural principles can be implemented without Pydantic itself, using typed classes, explicit validation functions, structured errors, and standard-library data structures.

The three implementations therefore represent the same broad architectural problem from different technical perspectives:

`external data → constrained structure → validation → normalized representation → application logic`

The specific mechanisms differ, but the separation between untrusted input and trusted application state remains the central design principle.
