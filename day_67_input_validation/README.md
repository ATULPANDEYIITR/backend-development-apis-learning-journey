# Input Validation

## 1. Overview

Input validation is the process of checking data before an application accepts, processes, stores, or uses it.

External input must be treated as untrusted, regardless of whether it originates from a browser, mobile application, API client, internal service, file upload, or database integration.

This project implements an enterprise input-validation workflow across Python, JavaScript, C++17, Java 17, and PostgreSQL.

The implementations cover four distinct technical areas:

| Area | Purpose |
|---|---|
| Schema validation | Verify the structure, fields, data types, and permitted attributes |
| Sanitization | Normalize or transform input for a specific processing or output context |
| Boundary validation | Enforce minimum, maximum, length, and range restrictions |
| Malicious input detection | Identify suspicious patterns and reject potentially dangerous requests |

These mechanisms operate together, but they are not interchangeable.

## 2. Input Validation Architecture

A secure input-processing workflow separates request reception, structural checks, field validation, security inspection, business rules, and persistence.

### Processing workflow

Request received
→ Request size check
→ JSON parsing
→ Schema validation
→ Type validation
→ Sanitization and normalization
→ Boundary validation
→ Format validation
→ Malicious input inspection
→ Business rule evaluation
→ Persistence
→ Audit and response

A request must not reach persistence when mandatory validation fails.

### Validation layers

| Layer | Main responsibility | Example |
|---|---|---|
| Transport | Restrict request size and encoding | Maximum 16 KB |
| Structural | Verify object structure | JSON object required |
| Schema | Verify fields and permitted attributes | Unknown fields rejected |
| Type | Verify actual data types | Age must be an integer |
| Boundary | Verify permitted ranges | Age between 18 and 120 |
| Format | Verify representation | Valid email address |
| Sanitization | Normalize data | Remove control characters |
| Security | Identify suspicious content | Script and traversal indicators |
| Business | Apply domain restrictions | Minimum supplier revenue |
| Persistence | Enforce stored-data integrity | Unique supplier code |

## 3. Schema Validation

Schema validation establishes the expected structure of an input object.

A schema defines:

- Field names.
- Required and optional attributes.
- Expected data types.
- Minimum and maximum lengths.
- Numeric restrictions.
- Regular-expression patterns.
- Permitted enumerated values.
- Custom validation rules.

### Required and optional fields

A required field must be supplied before processing can continue.

An optional field can be omitted without invalidating the request.

For example, a registration request may require:

| Field | Type | Requirement |
|---|---|---|
| username | String | Required |
| email | String | Required |
| age | Integer | Required |
| role | String | Required |
| active | Boolean | Required |
| phone | String | Optional |

Missing required fields produce validation errors.

An optional field that is supplied must still satisfy its validation rules.

### Unknown fields

An API should explicitly define how it handles unexpected attributes.

The implementations use strict schema policies that reject unknown fields.

For example, a registration request containing `is_admin` is rejected if the schema does not define that attribute.

This prevents accidental mass assignment, where an application binds untrusted attributes directly to privileged internal properties.

### Type validation

A value must have the expected type before further processing.

Examples:

- An integer field must not accept arbitrary text.
- A Boolean field must not accept the string `true`.
- An object field must not accept an array.
- A numeric field must reject `NaN` and infinity where applicable.

Language-specific behavior matters.

Python treats Boolean values as a subclass of integers. The Python implementation explicitly prevents `True` from passing integer validation.

JavaScript distinguishes integers from other numbers through `Number.isSafeInteger`.

C++17 uses a variant-based value representation to distinguish strings, integers, floating-point values, and Booleans.

Java uses explicit domain types and `BigDecimal` for financial values.

PostgreSQL uses JSONB type inspection before converting incoming JSON values.

## 4. Sanitization and Normalization

Sanitization transforms input into an accepted representation.

Normalization makes equivalent representations consistent.

The implementations demonstrate:

- Unicode NFC normalization where supported.
- Removal of selected control characters.
- Removal of unnecessary surrounding whitespace.
- HTML output escaping.
- Separate security inspection.

### Normalization

For example:

`"  Enterprise Supplier  "`

can become:

`"Enterprise Supplier"`

Unicode normalization helps maintain consistent text representation when equivalent characters have different underlying encodings.

### HTML escaping

HTML escaping converts special characters into their corresponding entities.

| Input character | Escaped representation |
|---|---|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&#x27;` |

A value such as `<script>` becomes text rather than an HTML element when inserted into an appropriately encoded HTML text context.

Escaping must match the output context. HTML text, HTML attributes, JavaScript strings, URLs, and CSS require different encoding rules.

### Sanitization is not validation

Sanitization and validation solve different problems.

| Sanitization | Validation |
|---|---|
| Transforms input | Determines whether input is acceptable |
| Normalizes representation | Enforces requirements |
| May remove selected characters | May reject invalid content |
| Does not establish business correctness | Establishes compliance with defined rules |

The implementations do not silently remove suspicious script or SQL patterns and then accept the request. They report suspicious content and reject the affected request.

This avoids treating a potentially malicious value as safe merely because it has been modified.

## 5. Boundary Validation

Boundary validation ensures that values remain within defined limits.

It applies to numeric values, strings, collections, and request payloads.

### Numeric boundaries

The Python registration example uses:

| Field | Minimum | Maximum |
|---|---:|---:|
| Age | 18 | 120 |

The C++ inventory example uses:

| Field | Minimum | Maximum |
|---|---:|---:|
| Quantity | 0 | 100,000 |
| Price | 0.01 | 10,000,000 |

The Java supplier example applies limits to workforce size and annual revenue.

### String boundaries

String restrictions prevent excessively short or long values.

Examples:

- Username: 3–20 characters.
- Email: 6–254 characters.
- Company name: 3–100 characters.
- Product description: maximum 80 characters.

### Request boundaries

Request-size restrictions should be enforced before expensive parsing or processing.

The Python and JavaScript implementations reject registration payloads larger than 16 KB.

Request-size restrictions help reduce resource-exhaustion risks, although they must be supplemented with limits on nesting depth, array length, processing time, and concurrent requests.

### Inclusive boundaries

A range from 1 to 100 normally includes both endpoints.

The following values are therefore evaluated as:

| Value | Result |
|---:|---|
| 0 | Rejected |
| 1 | Accepted |
| 50 | Accepted |
| 100 | Accepted |
| 101 | Rejected |

Boundary conditions should be tested explicitly because errors frequently occur at the minimum and maximum values.

## 6. Format Validation

Format validation verifies whether a value follows a defined representation.

The implementations use regular expressions for structured text fields.

### Email validation

The example applications validate email addresses using a restricted syntactic pattern.

This is a preliminary format check. It does not establish that an address exists or that the requester controls it.

Email ownership requires a separate verification workflow.

### Supplier code validation

The C++ and PostgreSQL implementations use supplier identifiers with the following structure:

`SUP-1001`

The accepted pattern is:

- Two to four uppercase letters.
- A hyphen.
- Three to eight digits.

A syntactically valid supplier code must still satisfy uniqueness constraints.

### Date validation

The Python implementation verifies ISO-style dates using `YYYY-MM-DD` and actual calendar-date parsing.

A matching regular expression alone cannot establish that a date is valid.

For example, `2026-02-31` has the correct textual structure but represents an invalid calendar date.

## 7. Malicious Input Detection

Malicious input detection examines submitted values for suspicious patterns.

The implementations cover common indicators associated with several attack categories.

### SQL injection

SQL injection occurs when untrusted input changes the meaning of a database query.

Example suspicious input:

`' UNION SELECT * FROM users --`

The implementations identify this pattern as a security indicator.

The primary database protection is parameterized SQL.

Input filtering alone cannot provide reliable SQL injection protection because SQL syntax is context-dependent and attack techniques vary.

### Cross-site scripting

Cross-site scripting occurs when untrusted content is interpreted as executable browser content.

Example:

`<script>alert(1)</script>`

Appropriate output encoding and safe DOM APIs are the primary controls.

The detection rules in the examples are supplementary indicators, not a complete XSS defense.

### Path traversal

Path traversal attempts to access files outside an intended directory.

Example:

`../../etc/passwd`

Applications handling filenames must resolve paths against an approved directory and verify that the resulting path remains inside the permitted location.

### Command injection

Command injection occurs when untrusted input influences an operating-system command.

The implementations identify command-substitution indicators such as:

- `$()`
- Backtick expressions.

Applications should avoid shell execution with untrusted values. Where process execution is necessary, use argument arrays and strict allowlists.

### Detection limitations

Regular expressions cannot identify every malicious request.

A request can be harmful without matching a known pattern. A legitimate value can also contain characters that resemble an attack.

Security detection must therefore be combined with:

- Context-aware output encoding.
- Parameterized database queries.
- Strict schema definitions.
- Least-privilege execution.
- Request-size restrictions.
- Authentication and authorization.
- Logging and monitoring.
- Appropriate business rules.

## 8. Python Implementation

The Python program models an API registration workflow using standard-library features.

### Main components

| Component | Responsibility |
|---|---|
| `FieldSchema` | Defines field-level validation requirements |
| `ValidationIssue` | Represents an individual validation failure |
| `ValidationResult` | Stores the result and sanitized data |
| `InputSanitizer` | Performs normalization, encoding, and inspection |
| `SchemaValidator` | Evaluates the request against the schema |
| `RequestProcessor` | Coordinates parsing, validation, uniqueness, and storage |

### Dataclasses and enums

`FieldSchema` uses a dataclass to define reusable field rules.

`ValidationCategory` provides explicit categories for validation failures.

This makes validation behavior easier to maintain than a collection of unrelated conditional statements.

### Custom exceptions

`InputValidationError` carries structured validation issues.

The caller can distinguish invalid input from malformed JSON, duplicate usernames, and request-size failures.

### Validation result

The validator returns:

- A Boolean indicating validity.
- Sanitized data when the entire request is valid.
- A list of validation issues.

The implementation does not expose partially validated data as accepted output.

### Testing

The script includes assertions for:

- Valid input.
- Minimum boundary violation.
- Boolean versus integer type handling.
- Script injection indicators.
- Unknown fields.
- Invalid numeric types.
- Null root values.
- HTML escaping.

## 9. JavaScript Implementation

The JavaScript program models an asynchronous registration service.

It uses Node.js standard-library capabilities.

### Main components

| Component | Responsibility |
|---|---|
| `Sanitizer` | Normalizes strings and identifies suspicious input |
| `SchemaValidator` | Performs schema and field validation |
| `SlidingWindowRateLimiter` | Limits request frequency |
| `RegistrationService` | Coordinates asynchronous registration |
| `ValidationError` | Carries structured validation issues |
| `RequestError` | Represents request-processing failures |

### Asynchronous processing

The registration method is asynchronous and simulates an asynchronous persistence operation.

It validates the request before storing a user record.

Uniqueness is checked again after the asynchronous operation to demonstrate the need for concurrency-aware state management.

In production, uniqueness must be enforced by a database constraint or an equivalent atomic persistence operation.

### Sliding-window rate limiting

The rate limiter records request timestamps for each client.

For every incoming request:

1. Expired timestamps are removed.
2. The number of active requests is evaluated.
3. Requests exceeding the configured limit are rejected.
4. Accepted requests are recorded.

The example permits five requests per client in a 60-second window.

This in-memory implementation is suitable for demonstrating the algorithm, but distributed deployments require shared rate-limit state and bounded storage.

## 10. C++17 Implementation

The C++ program implements an inventory-registration and stock-management system.

### Domain model

The program defines:

- `JsonValue` for typed input values.
- `FieldRule` for field constraints.
- `ValidationIssue` for structured failures.
- `ValidationResult` for validation outcomes.
- `Product` for inventory records.
- `InventoryService` for business operations.

### Variant-based typing

`std::variant` stores one of four supported value types:

- String.
- Integer.
- Floating-point number.
- Boolean.

The validator checks the active variant before performing type-specific operations.

This avoids unsafe assumptions about input values.

### Inventory registration

A product must satisfy:

| Field | Validation |
|---|---|
| SKU | Uppercase code pattern |
| Name | 3–80 characters |
| Quantity | 0–100,000 |
| Price | 0.01–10,000,000 |
| Category | Restricted permitted values |

The service stores a product only after validation succeeds.

Duplicate SKUs are rejected.

### Stock management

The `updateStock` operation checks whether the requested quantity change would produce a negative or excessively large inventory quantity.

It uses a wider integer type for intermediate arithmetic to avoid overflow during addition.

The existing stock value is updated only after the new value passes the boundary checks.

## 11. Java 17 Implementation

The Java program models supplier onboarding for an enterprise procurement platform.

### Domain components

| Component | Responsibility |
|---|---|
| `FieldRule` | Defines field constraints |
| `ValidationResult` | Represents validation output |
| `ValidationIssue` | Records individual errors |
| `SchemaValidator` | Performs structural and field validation |
| `SupplierPolicy` | Evaluates business eligibility |
| `SupplierService` | Manages registration and state transitions |
| `Supplier` | Immutable supplier record |

### Records and immutability

The implementation uses Java records for validation issues, validation results, field rules, and suppliers.

Records provide concise immutable data structures.

Collections are copied when records are constructed to prevent callers from modifying stored collection state through retained references.

### Financial validation

Annual revenue is represented by `BigDecimal`.

This avoids the binary floating-point precision problems associated with representing financial amounts using ordinary floating-point values.

### Business policy validation

Schema validity and business eligibility are separate stages.

A supplier may provide structurally correct information but still fail onboarding policy.

The example checks:

- Minimum employee count.
- Minimum annual revenue.
- Restricted-country policy.

### State transitions

Suppliers begin in the `PENDING` state.

An eligible pending supplier can be approved.

Repeated approval attempts are rejected.

The service uses synchronized methods to make its in-memory registration and state-transition operations atomic within one application instance.

A distributed production service would require transactional persistence and database-level concurrency controls.

## 12. PostgreSQL Implementation

The PostgreSQL script implements a relational validation workflow.

It uses JSONB for incoming request data and relational tables for validated supplier records.

### Database structure

The main relationships are:

Repositories are not required for this domain. The actual relationship is:

`Validation Request → Validation Errors`

`Validation Request → Supplier`

`Supplier → Country`

`Validation Policy → Field Rules`

### Main tables

| Table | Purpose |
|---|---|
| `validation_policies` | Stores configurable field-level policies |
| `countries` | Stores permitted and restricted countries |
| `suppliers` | Stores validated supplier records |
| `validation_requests` | Stores incoming request payloads |
| `validation_errors` | Stores individual validation failures |

### JSONB structural validation

The request table stores incoming JSONB payloads.

The validation procedure checks the expected keys and JSON types before converting values to PostgreSQL data types.

This ordering is important.

Directly casting an unverified JSON value can raise a database exception and interrupt processing.

### Constraints

The supplier table enforces:

- Primary key integrity.
- Supplier code uniqueness.
- Country foreign-key integrity.
- Supplier code format.
- Email format.
- Employee count boundaries.
- Annual revenue boundaries.

Database constraints provide a second layer of protection when requests reach persistence through different application paths.

### Triggers

Two triggers demonstrate database-level workflow enforcement.

`trg_request_processed_at` updates the processing timestamp when request status changes.

`trg_supplier_state_transition` prevents direct modification of a supplier's final approved or rejected state.

### Stored procedure

`validate_supplier_request` coordinates:

1. Request retrieval and row locking.
2. Unknown-field detection.
3. Required-field verification.
4. JSON type verification.
5. Text normalization.
6. Format checks.
7. Numeric boundary checks.
8. Malicious input inspection.
9. Duplicate supplier detection.
10. Business eligibility evaluation.
11. Supplier insertion.
12. Request status updates.

The procedure uses a transaction so that supplier insertion and request acceptance are committed together.

### Indexes

The script defines indexes for common access patterns.

| Index | Purpose |
|---|---|
| Supplier status | Filter suppliers by workflow state |
| Supplier country | Retrieve suppliers by country |
| Supplier creation time | Retrieve recently registered suppliers |
| Request status and time | Process pending requests |
| Request JSONB GIN | Support JSONB containment and key-oriented queries |
| Validation error request | Retrieve errors for an individual request |
| Validation error category | Analyze validation failures |
| Validation error severity | Monitor security and operational risks |

Indexes improve selected retrieval operations but introduce storage and write overhead.

Index design should reflect actual query patterns and data volume.

## 13. Validation Error Management

A validation failure should produce an actionable diagnostic without unnecessarily exposing sensitive information.

The implementations distinguish:

| Category | Meaning |
|---|---|
| REQUIRED | Mandatory value is missing |
| TYPE | Supplied value has an incorrect type |
| FORMAT | Value does not match the required representation |
| BOUNDARY | Value exceeds permitted limits |
| SECURITY | Suspicious input was detected |
| UNKNOWN_FIELD | Attribute is not part of the schema |
| BUSINESS_RULE | Value violates a domain policy |

### Error-handling principles

- Reject invalid requests before persistence.
- Return structured errors.
- Avoid exposing stack traces to external clients.
- Do not log passwords, authentication tokens, or unnecessary personal information.
- Separate internal diagnostics from public error messages.
- Retain sufficient audit information for investigation.
- Apply appropriate access controls to validation logs.

## 14. Edge Cases and Failure Handling

| Edge case | Expected behavior |
|---|---|
| Missing required attribute | Reject |
| Unknown attribute | Reject under strict schema policy |
| Null value | Reject when the field is mandatory |
| Wrong data type | Reject |
| Boolean supplied for integer field | Reject |
| NaN or infinity | Reject |
| Empty string | Apply minimum-length validation |
| Oversized request | Reject before expensive processing |
| Invalid JSON | Reject parsing |
| Invalid calendar date | Reject |
| Duplicate identifier | Reject through uniqueness enforcement |
| SQL injection indicator | Flag and reject |
| Script injection indicator | Flag and reject |
| Path traversal indicator | Flag and reject |
| Numeric overflow | Reject before persistence |
| Restricted country | Reject or route for compliance review |
| Repeated state transition | Reject invalid transition |

## 15. Performance and Security Considerations

### Performance

Schema validation should avoid unnecessary repeated processing.

Practical considerations include:

- Compile regular expressions once.
- Use hash-based lookups for allowed values.
- Bound request and collection sizes.
- Avoid expensive parsing of oversized inputs.
- Use database indexes for frequently queried fields.
- Avoid excessive database round trips.
- Limit validation error accumulation.
- Apply rate limiting to expensive endpoints.

For a request containing \(n\) fields and a schema containing \(m\) fields, the basic map-based validation approach is approximately \(O(n+m)\), excluding the cost of individual pattern matching and custom validators.

### Security

A production input-validation system should include:

- Server-side validation.
- Strict schema enforcement.
- Parameterized SQL.
- Context-aware output encoding.
- Authentication and authorization.
- Request-size and rate limits.
- Safe file handling.
- Least-privilege database permissions.
- Secure logging.
- Database constraints.
- Atomic persistence.
- Security monitoring.

Input validation does not replace authentication, authorization, encryption, or access control.

A valid input does not establish that a user is authorized to perform the requested operation.

## 16. Running the Implementations

| File | Runtime | Execution |
|---|---|---|
| Python | Python 3.10+ | `python input_validation.py` |
| JavaScript | Node.js 18+ | `node input_validation.js` |
| C++17 | C++17 compiler | `g++ -std=c++17 -O2 input_validation.cpp -o input_validation` followed by `./input_validation` |
| Java | Java 17 | `javac Main.java` followed by `java Main` |
| PostgreSQL | PostgreSQL 15+ | Execute the SQL script using `psql` |

The Python, JavaScript, C++, and Java programs use standard-library functionality without third-party dependencies.

The PostgreSQL script creates its own schema and database objects. It requires permission to create schemas, tables, functions, procedures, and triggers.

## 17. Implementation Comparison

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Schema validation | Yes | Yes | Yes | Yes | Yes |
| Type validation | Yes | Yes | Yes | Yes | Yes |
| Boundary validation | Yes | Yes | Yes | Yes | Yes |
| Sanitization | Yes | Yes | Yes | Yes | Yes |
| Security indicators | Yes | Yes | Yes | Yes | Yes |
| Custom errors | Yes | Yes | Yes | Yes | SQL exceptions |
| Business rules | Registration | Registration | Inventory | Supplier onboarding | Supplier onboarding |
| State management | User records | User records | Stock records | Supplier states | Request and supplier states |
| Persistence | In-memory | In-memory | In-memory | In-memory | Relational |
| Automated tests | Assertions | Assertions | Assertions | Assertions | Constraint and workflow checks |

## 18. Practical Design Distinctions

Four principles govern the architecture.

**Schema validation determines whether the request has an acceptable structure.**

**Sanitization transforms data into an appropriate representation for a defined processing or output context.**

**Boundary validation determines whether individual values fall within permitted limits.**

**Malicious input detection identifies suspicious patterns that require rejection, investigation, or additional security controls.**

Business validation is a separate layer that determines whether structurally valid data satisfies organizational requirements.

Persistence constraints provide another enforcement layer, protecting the integrity of stored information even when multiple application services interact with the same database.

A reliable validation architecture combines these controls rather than depending on a single filtering function.
