# Error Handling: Exceptions, HTTPException, Custom Exceptions, Exception Handlers, and Structured Errors

## 1. Topic Introduction

Error handling is the systematic process of detecting failures, representing them accurately, deciding whether they can be recovered from, and communicating them safely to the next layer of an application.

A production application can encounter many kinds of failures:

- Invalid user input
- Missing resources
- Authentication failures
- Authorization failures
- Business-rule conflicts
- Database failures
- Network failures
- File-system failures
- Timeouts
- External service failures
- Programming defects
- Unexpected runtime conditions

An error-handling design should answer several questions:

1. What failed?
2. Where did it fail?
3. Is the failure expected?
4. Can the operation be recovered or retried?
5. Which layer should handle the failure?
6. What information should be logged?
7. What information should be returned to the caller?
8. Which HTTP status code represents the failure when the application is an API?
9. How can clients reliably distinguish one failure from another?

The implementations in this topic demonstrate these questions using Python, JavaScript, and C++.

The Python implementation focuses heavily on exception semantics and web API handling with FastAPI. The JavaScript implementation emphasizes synchronous and asynchronous error propagation and HTTP-style error translation. The C++ implementation develops a complete order-processing case study using custom exception classes and structured HTTP-style responses.

---

## 2. Fundamental Terminology

### Exception

An exception is an object representing an abnormal condition that interrupts normal execution.

Examples include:

- Python `ValueError`
- Python `TypeError`
- JavaScript `TypeError`
- C++ `std::runtime_error`

An exception normally propagates upward through the call stack until code handles it.

### Throwing or Raising

Different languages use different terminology.

Python uses `raise`.

JavaScript uses `throw`.

C++ uses `throw`.

The basic idea is the same: signal that normal execution cannot continue at the current point.

### Catching or Handling

Python uses `try` and `except`.

JavaScript uses `try` and `catch`.

C++ uses `try` and `catch`.

A handler can:

- Recover from the failure
- Translate it
- Log it
- Return a structured response
- Clean up resources
- Re-raise it

### Exception Propagation

If an exception is not handled in the current function, it normally moves toward the caller.

For example:

`controller -> service -> repository`

A repository may encounter a missing record. The repository can raise an exception. The service can allow it to propagate. The controller or API boundary can translate it into an HTTP response.

### Exception Chaining

Exception chaining preserves the relationship between a high-level application error and its lower-level cause.

This is important when translating:

`ValueError -> ValidationError`

The higher-level exception provides an application-friendly meaning while the original exception remains available for diagnostics.

---

## 3. Python Exception Handling

The Python implementation begins with ordinary `try`, `except`, `else`, and `finally` statements.

The basic structure is:

`try` contains code that may fail.

`except` handles selected failures.

`else` executes when the `try` block succeeds.

`finally` executes regardless of success or failure.

The script demonstrates all four mechanisms.

### Specific exception handling

The script deliberately handles `ValueError`, `TypeError`, `KeyError`, `IndexError`, and `ZeroDivisionError` separately.

Specific handlers are preferable to an unnecessarily broad handler because they make the recovery policy explicit.

For example, invalid user input may be recoverable, while an unexpected programming defect may need to be logged and propagated.

---

## 4. Raising Exceptions in Python

The Python function `validate_age()` demonstrates explicit validation.

It raises:

- `TypeError` when the value has the wrong type
- `ValueError` when the value has the right general type but an invalid value

This distinction is useful.

For example:

`validate_age("25")`

has a type problem.

`validate_age(-5)`

has a value problem.

A good API can use these distinctions internally even if both are eventually translated into one structured validation response.

---

## 5. Python Exception Hierarchy

Python exceptions form an inheritance hierarchy.

Examples include:

- `Exception`
- `ValueError`
- `TypeError`
- `LookupError`
- `KeyError`
- `IndexError`

`KeyError` and `IndexError` are examples of lookup-related exceptions.

`KeyboardInterrupt` is not normally treated as an ordinary application exception because it inherits from `BaseException` rather than `Exception`.

This is one reason broad handlers should normally use:

`except Exception:`

rather than:

`except BaseException:`

A general `BaseException` handler can interfere with system-level control-flow events.

---

## 6. Custom Python Exceptions

The Python implementation defines:

- `ApplicationError`
- `ValidationError`
- `ResourceNotFoundError`
- `ConflictError`
- `AuthorizationError`
- `PaymentError`

A custom exception communicates application meaning more clearly than a generic exception.

For example:

`ResourceNotFoundError`

is more descriptive at the service layer than an arbitrary `RuntimeError`.

A common architecture is:

`Exception -> ApplicationError -> SpecificDomainError`

This allows code to catch either a specific failure or an entire family of application failures.

For example, code can catch `ValidationError` specifically, or `ApplicationError` when every expected application-level failure should be treated similarly.

---

## 7. Structured Custom Errors

The Python `StructuredApplicationError` contains:

- A human-readable message
- A machine-readable error code
- An HTTP-style status code
- Structured details

The resulting representation can contain information such as:

- Error code
- Message
- Field
- Validation reason

Structured errors are preferable to forcing clients to interpret arbitrary human-readable strings.

A client can reliably check:

`error.code == "VALIDATION_ERROR"`

instead of searching the message for words such as `"invalid"`.

---

## 8. Exception Chaining in Python

The Python `load_integer()` function demonstrates:

`raise ... from error`

This preserves the original exception as the cause of the higher-level exception.

A low-level conversion failure can therefore become a meaningful application error:

`ValueError`

becomes:

`ValidationError`

while retaining the original cause.

This is useful when application layers translate implementation-specific failures into domain-level failures.

---

## 9. Cleanup and `finally`

The `ManagedResource` example demonstrates deterministic cleanup.

The context manager uses:

`__enter__()`

and:

`__exit__()`

This is closely related to reliable resource management.

Typical production resources include:

- Files
- Database connections
- Locks
- Network resources
- Temporary resources

A failure should not leave resources permanently open or locked.

Python's `with` statement is therefore an important error-handling mechanism.

---

## 10. Assertions Versus Validation

The Python implementation includes an assertion demonstration.

Assertions are useful for expressing internal assumptions or invariants.

They should not normally be the primary mechanism for validating untrusted external input.

External input should be explicitly validated.

For example:

- HTTP request data
- User-provided files
- Query parameters
- Database records from untrusted sources
- External service responses

must be treated as data that requires validation.

---

## 11. Translating Exceptions

The Python decorator example demonstrates exception translation.

A low-level function may raise:

`ValueError`

The decorator converts that failure into:

`ValidationError`

This creates a boundary between implementation details and application semantics.

Exception translation is useful when a lower layer should not expose its implementation-specific exception types to higher layers.

---

## 12. Service-Layer Error Design

The Python implementation contains:

- `UserRepository`
- `UserService`

The repository is responsible for finding users.

The service is responsible for business operations such as deactivating a user.

The service raises:

- `ResourceNotFoundError`
- `ConflictError`

The service does not need to know that a web application may eventually convert those failures into HTTP 404 or 409 responses.

This separation reduces coupling.

A useful architectural flow is:

`HTTP layer -> service layer -> repository layer`

The HTTP layer understands HTTP.

The service layer understands business rules.

The repository layer understands persistence.

---

## 13. HTTP Errors

An HTTP API has two related but distinct concepts:

1. HTTP-level status
2. Application-level error information

For example:

`404`

communicates that a requested resource was not found.

An application-specific code such as:

`CUSTOMER_NOT_FOUND`

provides additional machine-readable meaning.

A structured response can therefore contain both.

The Python FastAPI implementation demonstrates this distinction.

---

## 14. HTTP Status Codes

The Python implementation documents common API statuses.

### 400 Bad Request

The request cannot be processed because it is invalid at the request level.

### 401 Unauthorized

Authentication is required or the supplied authentication credentials are invalid.

### 403 Forbidden

The caller is authenticated but does not have permission.

### 404 Not Found

The requested resource does not exist.

### 409 Conflict

The requested operation conflicts with current application state.

Examples include:

- Duplicate username
- Attempting to modify an already completed order
- State transition conflicts

### 422 Unprocessable Content

The request structure can be understood but its supplied data fails validation rules.

FastAPI commonly uses 422 for request validation failures.

### 429 Too Many Requests

A client has exceeded a rate limit.

### 500 Internal Server Error

An unexpected server-side failure occurred.

The client should normally receive a generic message rather than internal implementation details.

### 503 Service Unavailable

The service is temporarily unable to process the request.

It can be appropriate for temporary upstream or infrastructure failures.

---

## 15. FastAPI `HTTPException`

The Python implementation uses FastAPI's `HTTPException`.

For example, the customer endpoint raises an HTTP 404 when the requested customer does not exist.

`HTTPException` is useful when the endpoint itself knows that a particular HTTP response should be generated.

It should not necessarily be used throughout every business-logic layer.

A service layer can instead raise a domain-specific exception such as:

`ApiNotFoundError`

and an exception handler can translate it into HTTP.

This preserves separation between business logic and transport logic.

---

## 16. FastAPI Custom Exception Handlers

The Python API defines handlers for:

- `ApiNotFoundError`
- `ApiConflictError`
- `RequestValidationError`
- Generic `Exception`

An exception handler acts as a centralized translation mechanism.

For example:

`ApiNotFoundError -> HTTP 404`

and:

`ApiConflictError -> HTTP 409`

This prevents every endpoint from repeating the same response-generation code.

---

## 17. Global Exception Handling

A final generic exception handler is useful as a safety boundary.

Unexpected exceptions can contain:

- Stack traces
- Database information
- File-system paths
- Internal implementation details
- Sensitive configuration
- Third-party service responses

Returning those details directly to an API client creates information-disclosure risk.

The Python FastAPI implementation therefore logs the unexpected exception on the server and returns:

`INTERNAL_SERVER_ERROR`

with a generic message.

---

## 18. Request Validation

FastAPI can automatically validate request models using Pydantic.

The Python implementation defines a `Customer` model with:

- A name length constraint
- An age minimum
- An age maximum

Invalid input is intercepted by FastAPI's validation system.

The custom `RequestValidationError` handler then converts framework validation details into the application's structured error format.

This creates a stable external API contract even when internal validation details are framework-specific.

---

## 19. Structured API Errors

A robust API error should normally contain stable fields.

The Python implementation uses concepts such as:

- `code`
- `message`
- `status`
- `request_id`
- `details`

Example conceptual structure:

`error.code`

identifies the category.

`error.message`

provides a human-readable description.

`error.status`

communicates the HTTP-level status.

`error.request_id`

allows operators to correlate a client-visible error with server-side logs.

`error.details`

provides structured field or resource information.

---

## 20. Request IDs

A request ID is especially useful in distributed systems.

A client might receive:

`request_id = req-12345`

The server log can contain the same identifier.

This allows an operator to locate the relevant request without exposing sensitive diagnostic information to the client.

Request IDs should not themselves contain secrets.

---

## 21. JavaScript Error Objects

The JavaScript implementation begins with built-in errors such as:

- `TypeError`
- `RangeError`
- `Error`

JavaScript uses:

`throw`

to signal an exception and:

`catch`

to handle it.

JavaScript also supports:

`finally`

for cleanup.

The implementation demonstrates all three.

---

## 22. JavaScript Custom Error Classes

The JavaScript implementation defines:

- `ApplicationError`
- `ValidationError`
- `NotFoundError`
- `ConflictError`
- `AuthorizationError`
- `HttpError`

Custom classes carry additional fields:

- `code`
- `statusCode`
- `details`

This makes them useful as application-level error objects.

For example:

`new NotFoundError("Customer", 999)`

encodes both the resource type and identifier.

---

## 23. JavaScript Asynchronous Errors

Asynchronous JavaScript requires particular attention because failures can occur through:

- Promises
- `async`
- `await`
- Timers
- Network operations
- External services

The JavaScript implementation demonstrates:

`try { await operation(); } catch (error) { ... }`

This is an important pattern for asynchronous service code.

Promise-based code can also use:

`.catch()`

and:

`.finally()`

---

## 24. Promise Rejection

A rejected Promise represents asynchronous failure.

The implementation demonstrates:

`Promise.reject(...)`

followed by:

`.catch(...)`

A rejected Promise must be handled appropriately.

Unhandled Promise rejections can create difficult-to-diagnose application failures.

At the application boundary, a final `main().catch(...)` provides a last-resort safeguard.

---

## 25. JavaScript Error Causes

Modern JavaScript supports the `cause` option for `Error`.

The general idea is:

A low-level error becomes the cause of a higher-level error.

This is conceptually similar to Python exception chaining.

It is useful when an application wants to preserve diagnostic relationships while presenting a more meaningful abstraction to callers.

---

## 26. HTTP-Style Errors in JavaScript

JavaScript itself does not define a universal `HTTPException` equivalent for all environments.

Frameworks and libraries often provide their own abstractions.

The implementation therefore defines a self-contained:

`HttpError`

class.

It carries:

- HTTP status
- Application error code
- Message
- Structured details

This models the same architectural concept without requiring an external web framework.

---

## 27. HTTP Error Mapping

The JavaScript `mapErrorToHttpResponse()` function translates exceptions into response objects.

Examples include:

`ValidationError -> 422`

`NotFoundError -> 404`

`ConflictError -> 409`

`AuthorizationError -> 403`

Unknown errors become:

`500`

This centralized mapping is useful for HTTP services because business logic can raise meaningful exceptions while the HTTP layer controls the response format.

---

## 28. Retryable and Non-Retryable Errors

Not every error should be retried.

The JavaScript implementation defines:

- `RetryableError`
- `NonRetryableError`

A temporary upstream outage may be retryable.

Invalid input is generally not retryable without changing the input.

Repeatedly retrying permanent failures wastes resources and can amplify system load.

---

## 29. Exponential Backoff

The JavaScript implementation demonstrates exponential backoff.

The delay grows approximately according to:

`baseDelay * 2^attempt`

Random jitter is also added.

Jitter is important in distributed systems because many clients may otherwise retry at the same moment.

Without jitter, synchronized retries can create a secondary traffic spike after an outage.

---

## 30. Python, JavaScript, and C++ Comparison

| Concept | Python | JavaScript | C++ |
|---|---|---|---|
| Raise/throw | `raise` | `throw` | `throw` |
| Handle | `except` | `catch` | `catch` |
| Cleanup | `finally`, context managers | `finally` | RAII, destructors |
| Custom errors | Exception classes | Error subclasses | Exception subclasses |
| Async handling | `async` / `await` | `async` / `await`, Promises | Standard exceptions; concurrency model varies |
| HTTP framework example | FastAPI | HTTP-style self-contained model | HTTP-style service model |
| Structured errors | Dataclasses/dictionaries | Objects/classes | Structs/classes |
| Error hierarchy | Built into language | Prototype/class hierarchy | Class inheritance |
| Resource safety | Context managers | `finally`, resource APIs | RAII |

---

## 31. C++ Case Study

The C++ program models an order-processing service.

The scenario contains:

- Customers
- Products
- Inventory
- Orders
- Authentication
- Authorization
- Validation
- Business conflicts
- Structured API errors
- Transaction-style rollback

The architecture is divided into:

`CustomerRepository`

`ProductRepository`

`OrderRepository`

`OrderService`

`ErrorResponse`

This mirrors the separation commonly used in production service applications.

---

## 32. C++ Exception Hierarchy

The C++ case study defines:

`ApplicationException`

as the common application-level base.

Specialized exceptions include:

- `ValidationException`
- `AuthenticationException`
- `AuthorizationException`
- `NotFoundException`
- `ConflictException`
- `InsufficientInventoryException`

The base exception contains:

- Status code
- Error code
- Error details
- Human-readable message

This allows the HTTP-style boundary to handle the entire application exception family.

---

## 33. C++ Repository Layer

The repositories use standard library containers.

`unordered_map` is used for:

- Customers
- Products
- Orders

Average lookup complexity is approximately:

`O(1)`

for these hash-table operations.

The repositories raise `NotFoundException` when a requested resource does not exist.

This keeps lookup failures explicit.

---

## 34. C++ Validation

The order validation function checks:

- At least one item exists
- Product IDs are positive
- Quantities are positive
- Quantity limits are respected

Multiple validation errors can be collected into one structured exception.

This is useful for APIs because a client can receive several input problems in one response instead of correcting one field at a time.

---

## 35. Authentication and Authorization

The order service separates authentication from authorization.

Authentication answers:

"Who is making the request?"

Authorization answers:

"Is this actor allowed to perform the operation?"

The case study demonstrates both.

Missing or invalid credentials produce an authentication failure.

A valid customer without permission produces an authorization failure.

This distinction is important because 401 and 403 represent different concepts.

---

## 36. Transaction-Style Rollback

The order service changes inventory before saving the order.

If a later operation fails, the modified inventory is restored.

The C++ implementation uses:

`try`

followed by:

`catch (...)`

to restore the original inventory and rethrow the exception.

This demonstrates the principle of rollback.

The implementation is intentionally in-memory.

A production financial or inventory system should normally use database transactions, concurrency controls, locking, optimistic version checks, or another durable consistency mechanism.

---

## 37. Why `catch (...)` Is Different

C++ supports:

`catch (...)`

as a catch-all handler.

In the case study, it is used for transaction cleanup.

The exception is then rethrown with:

`throw;`

This is important.

A bare `throw;` preserves the currently handled exception.

By contrast, creating a new exception can change the original type and diagnostic context.

Catch-all handlers should be used carefully and for a clear purpose such as cleanup or a final process boundary.

---

## 38. Structured C++ Errors

The `ErrorResponse` structure contains:

- HTTP status
- Application error code
- Message
- Request ID
- Detailed validation information

The `toJson()` function creates a JSON-like representation using the standard library.

The case study avoids external JSON libraries to remain self-contained.

A production implementation should use a proper JSON library or framework when robust JSON serialization is required.

---

## 39. Edge Cases Demonstrated by the C++ Program

The case study exercises:

1. Missing authentication
2. Invalid authentication
3. Empty orders
4. Missing customers
5. Unauthorized customers
6. Missing products
7. Invalid quantities
8. Insufficient inventory
9. Successful orders

These cases demonstrate why error handling should be designed as part of the normal application architecture rather than added after the success path is complete.

---

## 40. Error Boundaries

An error boundary is a layer where errors are intentionally converted into another representation.

For an API, a typical flow is:

`Domain exception`

to:

`Service/application exception`

to:

`HTTP response`

For example:

`NotFoundException`

can become:

`404 RESOURCE_NOT_FOUND`

The client should not need to understand the internal class hierarchy.

---

## 41. Structured Errors Versus Free-Form Messages

A free-form error might be:

`Something went wrong`

This is difficult for clients to process reliably.

A structured error can contain:

`code = VALIDATION_ERROR`

`field = email`

`reason = INVALID_FORMAT`

This allows front-end applications, mobile applications, command-line clients, monitoring systems, and automated integrations to respond programmatically.

Human-readable messages remain useful, but they should not be the only machine-facing contract.

---

## 42. Exception Handling and Logging

Logging should provide enough information for diagnosis without exposing secrets.

Useful diagnostic information can include:

- Request ID
- Error class
- Endpoint
- Operation
- Timestamp
- Internal stack trace
- Relevant non-sensitive identifiers

Sensitive information should not be logged unnecessarily.

Examples of sensitive data include:

- Passwords
- Access tokens
- API keys
- Authentication cookies
- Private credentials
- Payment secrets

The Python implementation uses `logger.exception()` for unexpected failures.

---

## 43. Client Errors Versus Server Errors

A useful distinction is whether the client can correct the request.

Client-correctable examples:

- Invalid input
- Missing required field
- Unauthorized access
- Nonexistent resource
- State conflict

Server-side examples:

- Unexpected programming defect
- Corrupted internal state
- Unavailable infrastructure
- Unexpected database failure

The response strategy should reflect this distinction.

A client should receive useful corrective information for expected failures.

An unexpected internal failure should normally receive a generic safe message.

---

## 44. Common Mistakes

### Catching every exception immediately

A handler such as:

`except Exception: pass`

can silently hide serious failures.

### Empty catch blocks

Ignoring an error without documenting why it is safe can make failures extremely difficult to diagnose.

### Using exceptions for ordinary branching

Exceptions should not normally replace ordinary conditional logic when the condition is expected and frequent.

### Returning stack traces to clients

Stack traces are valuable to developers but can disclose implementation details to attackers.

### Exposing database errors

Raw database messages can reveal schema information or internal infrastructure.

### Retrying every failure

Validation, authorization, and other permanent failures usually should not be blindly retried.

### Using unstable messages as API contracts

Client software should generally rely on stable error codes rather than exact human-readable messages.

### Mixing HTTP logic into every service function

This creates tight coupling between business logic and a specific transport protocol.

---

## 45. Exception Handling and Security

Errors are part of the application's external attack surface.

An error response can accidentally reveal:

- Database table names
- SQL statements
- Internal hostnames
- File paths
- Framework versions
- Authentication details
- Debug information
- Secrets

A secure error architecture follows the principle of minimum necessary disclosure.

The server can retain detailed diagnostic information internally while exposing a controlled response externally.

---

## 46. Production Error-Handling Layers

A typical production application can use several layers.

### Layer 1: Input validation

Reject malformed or invalid input early.

### Layer 2: Authentication

Determine whether the caller is authenticated.

### Layer 3: Authorization

Determine whether the authenticated actor may perform the operation.

### Layer 4: Domain validation

Apply business rules.

### Layer 5: Infrastructure handling

Handle database, network, storage, and external service failures.

### Layer 6: Error translation

Convert internal exceptions into stable application errors.

### Layer 7: Transport response

Convert the application error into HTTP or another protocol representation.

### Layer 8: Logging and monitoring

Record sufficient diagnostic information for operations and debugging.

---

## 47. Error Codes

Error codes should be:

- Stable
- Specific
- Machine-readable
- Documented
- Independent of exact human-readable wording

Examples used by the implementations include:

- `VALIDATION_ERROR`
- `RESOURCE_NOT_FOUND`
- `CONFLICT`
- `FORBIDDEN`
- `AUTHENTICATION_REQUIRED`
- `INSUFFICIENT_INVENTORY`
- `INTERNAL_SERVER_ERROR`

A client can use these codes to implement deterministic behavior.

---

## 48. HTTPException Versus Custom Exceptions

`HTTPException` is directly connected to HTTP behavior.

A domain exception represents application meaning.

For example:

`CustomerNotFound`

is a domain/application concept.

`404`

is an HTTP transport concept.

Keeping these concepts separate is often beneficial.

A web boundary can translate:

`CustomerNotFound -> HTTP 404`

This makes the service layer easier to reuse in:

- HTTP APIs
- Command-line applications
- Background workers
- Message consumers
- Scheduled jobs
- Other service interfaces

---

## 49. Performance Considerations

Exception handling itself is not normally a reason to avoid well-designed error handling.

The important distinction is between exceptional failures and ordinary control flow.

If an application constantly throws exceptions as part of expected iteration, it may create unnecessary overhead and make the code harder to understand.

Performance concerns can also arise from:

- Constructing large error objects
- Capturing stack traces
- Logging high-frequency failures
- Serializing very large error details
- Repeated retries
- Excessive stack traces in distributed systems

The appropriate design is to validate predictable conditions normally and reserve exceptions for actual failure conditions or exceptional control paths.

---

## 50. Concurrency and Error Handling

The C++ inventory example illustrates an important limitation.

Checking inventory and decrementing it are not automatically atomic in a multi-threaded or multi-process environment.

Two requests could potentially observe the same inventory before either update is committed.

A production implementation may need:

- Database transactions
- Row-level locks
- Optimistic concurrency
- Version numbers
- Atomic update operations
- Idempotency mechanisms

Exception handling alone does not provide concurrency safety.

---

## 51. Idempotency and Errors

Network clients may retry requests when they receive:

- Timeouts
- 502
- 503
- Connection failures

If an operation creates an order, retrying blindly can create duplicate orders.

An idempotency key can allow the server to recognize that multiple requests represent the same logical operation.

This is especially important for:

- Payments
- Orders
- Transfers
- Reservations
- Resource creation

Error handling therefore interacts directly with API design and distributed-system reliability.

---

## 52. Testing Error Paths

Error paths should be tested explicitly.

Important test cases include:

- Valid input
- Missing input
- Invalid input
- Boundary values
- Missing resources
- Duplicate resources
- Unauthorized access
- Forbidden access
- Temporary failures
- Permanent failures
- Unexpected exceptions
- Retry exhaustion
- Transaction rollback
- Structured response format

The Python implementation includes a small dependency-free exception testing helper.

Production applications can use a full testing framework, but the underlying principle is the same: expected failures are part of observable behavior.

---

## 53. Python Implementation Responsibilities

The Python implementation demonstrates:

- Built-in exceptions
- Exception hierarchy
- `try`, `except`, `else`, `finally`
- Explicit `raise`
- Custom exception classes
- Structured exceptions
- Exception chaining
- Context managers
- Assertions
- Decorator-based exception translation
- Structured API errors
- Logging
- Transaction-style rollback
- Retry classification
- FastAPI `HTTPException`
- FastAPI custom exception handlers
- FastAPI validation handling
- Generic API exception handling
- Service/repository separation

FastAPI is used specifically because `HTTPException` and request exception handlers are central to the requested topic.

---

## 54. JavaScript Implementation Responsibilities

The JavaScript implementation demonstrates:

- Built-in `Error` classes
- `try`, `catch`, `finally`
- `throw`
- Custom error classes
- Structured errors
- Error causes
- Promises
- `async` and `await`
- Promise rejection handling
- HTTP-style errors
- Error-to-response mapping
- Retryable errors
- Exponential backoff
- Service/repository separation
- Safe serialization
- Process-level error-handling considerations

The implementation uses JavaScript's native capabilities rather than requiring a web framework.

---

## 55. C++ Implementation Responsibilities

The C++ implementation develops a realistic order-processing service.

It demonstrates:

- `std::exception`
- `std::runtime_error`
- Custom exception inheritance
- Structured error metadata
- Repository classes
- Service classes
- Validation
- Authentication
- Authorization
- Inventory processing
- Order creation
- Transaction-style rollback
- HTTP-style status mapping
- Structured response generation
- Edge-case processing
- Complexity analysis
- Security-aware error boundaries

The C++ design emphasizes explicit types, class-based architecture, standard-library containers, and deterministic resource and state management.

---

## 56. Important Distinctions

### Exception versus HTTP status

An exception is an application/runtime mechanism.

An HTTP status is a protocol-level response classification.

They can be mapped to each other, but they are not the same concept.

### Error message versus error code

A message is intended primarily for human understanding.

A code is intended for stable programmatic interpretation.

### Authentication versus authorization

Authentication identifies the caller.

Authorization determines what the caller may do.

### Retryable versus permanent failure

A retryable failure may succeed later.

A permanent failure normally requires changing the request or application state.

### Validation versus unexpected failure

Validation failures are expected and usually actionable.

Unexpected failures generally require server-side diagnosis.

### Domain error versus transport error

A domain error describes an application rule.

A transport error describes how that failure is represented through a protocol such as HTTP.

---

## 57. Practical API Error Contract

A consistent API can use a response structure containing:

`error.code`

Stable machine-readable identifier.

`error.message`

Human-readable description.

`error.status`

HTTP status associated with the response.

`error.request_id`

Identifier used to correlate client and server diagnostics.

`error.details`

Structured contextual information.

For example, a validation failure can identify several invalid fields in one response.

---

## 58. Error Handling Design Principles

A robust design generally follows these principles:

1. Catch errors where meaningful recovery or translation is possible.
2. Prefer specific exception types over unnecessary catch-all handling.
3. Use custom exceptions for meaningful application conditions.
4. Preserve low-level causes when translating errors.
5. Separate business logic from HTTP response generation.
6. Use structured error codes for machine-readable contracts.
7. Return appropriate HTTP status codes.
8. Keep internal diagnostics separate from public error messages.
9. Log unexpected failures with appropriate context.
10. Never log secrets unnecessarily.
11. Do not retry permanent failures blindly.
12. Use backoff and jitter for appropriate temporary failures.
13. Test both successful and failure paths.
14. Use transactions for operations that require atomic state changes.
15. Consider concurrency when multiple requests can modify shared state.
16. Treat error responses as part of the public API contract.
17. Avoid leaking implementation details.
18. Make failure behavior predictable and observable.
