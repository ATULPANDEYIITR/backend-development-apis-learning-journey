# API Response Design: Envelopes, Metadata, Consistency, and Error Schemas

## 1. Technical Scope

API response design defines how a server communicates the outcome of a request to a client. It establishes a predictable structure for successful operations, failed operations, resource representations, diagnostic information, pagination, request identification, and consistency guarantees.

A response contract is an interface between independent software components. Its structure must remain understandable across different endpoints, API versions, client applications, and service implementations.

This implementation examines four connected areas:

1. Response envelopes define the common structure of API responses.
2. Response metadata communicates request context, execution information, pagination, and navigation.
3. Consistency mechanisms describe how clients interpret resource versions and data freshness.
4. Error schemas standardize failure communication and recovery decisions.

The five implementations use a product-management API as their working domain.

## 2. Response Envelope

A response envelope is a consistent outer structure that contains the result of an API operation.

The implemented response contract follows this conceptual structure:

- `success`: Indicates whether the operation succeeded.
- `data`: Contains the successful resource or collection.
- `error`: Contains structured failure information.
- `metadata`: Contains request and response context.

The principal relationship is:

`success = true` implies `error = null`.

`success = false` implies `data = null` and a populated error object.

These conditions prevent contradictory response states.

### 2.1 Successful responses

A successful product retrieval can contain:

- Product identifier
- Product name
- Price
- Currency
- Resource version

A collection response can contain an array of products together with pagination information.

A successful HTTP status does not necessarily mean that the response contains a non-empty collection. For example, a valid search can return an empty array with HTTP 200.

The envelope distinguishes operation success from the quantity of returned data.

### 2.2 Failed responses

A failed response contains a structured error object rather than an arbitrary string.

The error structure includes:

| Field | Purpose |
|---|---|
| `code` | Stable machine-readable error identifier |
| `message` | Human-readable explanation |
| `details` | Field-level or operation-specific information |
| `retryable` | Indicates whether retrying may be appropriate |

The machine-readable code is the principal contract for client-side error handling.

Human-readable messages may change to improve clarity. Clients should not depend on parsing message text to identify failure conditions.

### 2.3 Envelope invariants

The implementations enforce the following invariants:

| Condition | Expected behavior |
|---|---|
| Successful operation | Data may be present; error must be null |
| Failed operation | Error must be present; data must be null |
| Missing metadata | Response construction is rejected |
| Invalid error state | Response construction is rejected |
| Unexpected exception | A safe internal error is returned |
| Missing resource | A resource-not-found response is returned |
| Invalid input | A validation error is returned |

An API contract should enforce these rules at the response-construction boundary instead of relying on every endpoint developer to implement them independently.

## 3. Response Metadata

Metadata describes the context in which a response was generated. It is separate from the business resource returned in `data`.

The implementations use a common metadata structure.

| Field | Description |
|---|---|
| `request_id` | Unique identifier for an individual request |
| `timestamp` | Time at which the response was created |
| `api_version` | Contract version used by the endpoint |
| `duration_ms` | Server-side processing duration |
| `correlation_id` | Identifier connecting related operations |
| `pagination` | Collection navigation information |
| `links` | Related resource and navigation references |
| `consistency` | Declared consistency behavior |

### 3.1 Request identification

A request identifier distinguishes one API execution from another.

For example:

`GET /api/v1/products/101`

The server assigns a unique request identifier and includes it in the response metadata.

This identifier supports:

- Log correlation
- Production debugging
- Incident investigation
- Request tracing
- Support investigations
- Error-report correlation

A correlation identifier serves a different purpose. It can connect several requests involved in a single business operation.

For example, a procurement workflow might involve inventory, pricing, and payment services. Each service can generate a different request identifier while preserving a shared correlation identifier.

Request identifiers should not expose credentials, personal information, internal infrastructure details, or predictable security tokens.

### 3.2 Timestamps and duration

The timestamp communicates when the response was generated.

The implementations use UTC-compatible timestamps to avoid ambiguity across geographical regions.

`duration_ms` represents server-side processing time.

It should not be confused with total client-perceived latency, which can include:

- DNS resolution
- Network transmission
- TLS negotiation
- Proxy processing
- Client-side execution

Duration measurements are useful for operational monitoring but should not be treated as precise end-to-end performance measurements.

### 3.3 API version metadata

The API version identifies the contract used to interpret the response.

For example:

- `/api/v1/products`
- `/api/v2/products`

Versioning helps maintain compatibility when response structures evolve.

A breaking change to field names, field types, error semantics, or required response properties generally requires an explicit compatibility strategy.

Adding an optional field can be compatible when existing clients safely ignore unknown properties.

The Python, JavaScript, and Java implementations include a version identifier in their metadata. PostgreSQL maintains an API version registry and associates each request with a version.

## 4. Pagination Metadata and Navigation

Collection endpoints require a defined mechanism for retrieving large datasets.

The implementations use page-based pagination with the following fields:

| Field | Meaning |
|---|---|
| `page` | Current page number |
| `page_size` | Maximum number of records requested |
| `total_items` | Total matching records |
| `total_pages` | Number of available pages |
| `has_next` | Whether another page exists |
| `has_previous` | Whether an earlier page exists |

The number of pages is calculated as:

\[
\text{total pages} =
\left\lceil
\frac{\text{total items}}{\text{page size}}
\right\rceil
\]

For three records and a page size of two:

- Page one returns two records.
- Page two returns one record.
- Total pages equals two.

An empty collection has zero total pages in this implementation.

### 4.1 Pagination validation

The implemented validation rules include:

- Page numbers must be positive.
- Page sizes must be positive.
- Page sizes must not exceed the configured limit.
- Offset calculations must not overflow the supported integer range.
- Navigation metadata must agree with the calculated page count.

The Python, JavaScript, and Java implementations construct pagination information from the actual collection size.

The PostgreSQL implementation stores pagination metadata in a separate relational table associated with the response.

### 4.2 Navigation links

Navigation links can use relations such as:

- `self`
- `first`
- `previous`
- `next`
- `last`
- `related`

The database restricts stored link relations to an approved set.

Relative URLs are used in the SQL implementation. This avoids storing an untrusted absolute host supplied by a request.

Page-based pagination is suitable for small and moderately sized collections. For rapidly changing or very large datasets, cursor-based pagination can reduce problems caused by records being inserted or removed between requests.

## 5. Error Schema Design

Error schemas define how an API communicates unsuccessful operations.

A standardized error catalogue provides a stable relationship between error identifiers, HTTP status codes, severity, default messages, and retry behavior.

The implemented catalogue contains the following error categories.

| Error code | HTTP status | Meaning |
|---|---:|---|
| `VALIDATION_ERROR` | 400 | Request parameters or values are invalid |
| `UNAUTHORIZED` | 401 | Authentication is required or invalid |
| `FORBIDDEN` | 403 | The authenticated identity lacks permission |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource does not exist |
| `CONFLICT` | 409 | Requested operation conflicts with current state |
| `RATE_LIMITED` | 429 | Request rate exceeds the permitted limit |
| `INTERNAL_ERROR` | 500 | Unexpected server-side failure |
| `SERVICE_UNAVAILABLE` | 503 | Service is temporarily unavailable |

### 5.1 HTTP status and application error codes

HTTP status codes communicate the broad result of an HTTP operation.

Application error codes communicate the specific failure within the API domain.

For example, two endpoints can return HTTP 409 while using the same application error code for an optimistic concurrency conflict.

This separation allows generic HTTP clients to interpret status codes while application clients handle specific error conditions.

### 5.2 Validation errors

A validation error should identify the problematic field and the reason for rejection.

Example:

| Field | Reason |
|---|---|
| `price` | Price must be greater than zero |
| `page` | Page must be positive |
| `page_size` | Page size exceeds the permitted limit |

The implementations represent validation details as structured records or objects.

The PostgreSQL implementation stores them separately in `response_error_details`.

Rejected values must be handled carefully. Sensitive values, credentials, authentication tokens, and confidential personal information must not be copied into public error responses.

### 5.3 Retryable errors

A retryable flag indicates that a retry may be appropriate.

It does not guarantee that retrying will succeed.

For example:

- A temporary service outage may justify a retry.
- A rate-limit response may justify waiting for the permitted interval.
- A validation failure generally requires correcting the request.
- A missing resource generally requires changing the requested identifier.
- A version conflict requires retrieving the latest resource state.

Retry policies should use bounded attempts, exponential backoff, and jitter where appropriate.

Operations that modify resources may also require idempotency keys to prevent duplicate execution after uncertain network failures.

### 5.4 Internal error protection

Unexpected exceptions must not expose:

- Stack traces
- SQL statements
- Database credentials
- Internal hostnames
- File system paths
- Framework configuration
- Secret values

The Python, JavaScript, and Java services log internal diagnostic information separately and return a safe public error.

The SQL schema stores standardized errors without requiring the database to expose internal exception details to API consumers.

## 6. Consistency and Resource Versioning

Consistency describes how clients observe resource state across requests and concurrent operations.

The implementations distinguish strong and eventual consistency as response metadata values.

### 6.1 Strong consistency

Strong consistency indicates that a successful read reflects the latest committed state according to the service's consistency contract.

For example, after a product price update commits, a subsequent strongly consistent read should return the updated price.

A strong-consistency guarantee requires appropriate database and service architecture. Adding a metadata field alone does not establish the guarantee.

### 6.2 Eventual consistency

Eventual consistency permits a temporary difference between the latest committed state and a particular read result.

This can occur in:

- Read replicas
- Distributed caches
- Event-driven projections
- Asynchronous replication
- Search indexes

A client may temporarily receive an older representation.

The service should document the consistency behavior and, where necessary, provide mechanisms for tracking versions or waiting for an update to become visible.

### 6.3 Optimistic concurrency

Optimistic concurrency prevents one client from silently overwriting another client's changes.

The implementations associate each product with an integer version.

A client retrieves:

- Product identifier
- Current price
- Current version

It submits an update with the expected version.

The operation succeeds only when the stored version matches the supplied version.

The update then increments the version.

Example:

| Operation | Price | Version |
|---|---:|---:|
| Initial retrieval | 85,000 | 1 |
| First update | 89,000 | 2 |
| Stale update using version 1 | Rejected | 2 |

This prevents a stale update from replacing newer data.

In HTTP APIs, the same principle can be implemented using entity tags and conditional requests:

- `ETag` identifies a resource representation.
- `If-Match` specifies the expected representation.
- A failed precondition can return HTTP 412.

The implementations use HTTP 409 for the simulated application-level version conflict.

## 7. Implementation Architecture

The five source files demonstrate different engineering perspectives on the same response-design principles.

| File | Engineering perspective | Principal mechanisms |
|---|---|---|
| Python | Domain simulation | Dataclasses, enums, generics, exceptions, repository |
| JavaScript | Event-driven service | Promises, EventEmitter, Maps, private fields |
| C++17 | Policy-oriented processing | Domain structures, STL containers, governance checks |
| Java 17 | Enterprise service architecture | Records, interfaces, immutable metadata, service classes |
| PostgreSQL | Relational persistence | Constraints, functions, procedures, triggers, views |

### 7.1 Python implementation

The Python implementation uses a generic `APIResponse` dataclass to represent a response envelope.

`APIError` and `ResponseMetadata` provide separate domain structures.

`ProductRepository` maintains product state and performs version-checked updates.

`ResponseFactory` centralizes response construction.

`APIService` provides an execution boundary that distinguishes expected domain failures from unexpected exceptions.

The demonstration validates successful retrieval, missing resources, pagination, invalid input, successful updates, and stale-version conflicts.

Important design decisions include:

- Frozen dataclasses for immutable response structures.
- Enumerations for stable application error codes.
- Generic response typing.
- Standard-library JSON serialization.
- Explicit response invariant checks.
- Safe error normalization.

### 7.2 JavaScript implementation

The JavaScript implementation uses an event-driven controller.

`ResponseEnvelope` enforces response invariants and exposes a consistent JSON representation.

`ProductStore` uses a private `Map` to maintain resource state.

`APIController` processes asynchronous operations using Promises.

The controller emits separate success and failure events. These events can be connected to logging, metrics, or monitoring components.

The implementation uses:

- Private class fields for repository state.
- `Object.freeze` for response-level immutability.
- `randomUUID` for request identifiers.
- `performance.now` for duration measurements.
- `EventEmitter` for event-driven monitoring.
- Promise-based execution for asynchronous operation handling.

The implementation intentionally avoids unnecessary npm dependencies.

### 7.3 C++17 implementation

The C++17 program models a repository governance engine.

Its response-related structures separate:

- Success state
- Optional result data
- Optional structured error
- Request metadata

The generic `Response<T>` uses `std::optional` to represent the presence or absence of result and error information.

`DomainException` provides typed application failures.

The program uses STL containers and explicit validation to prevent inconsistent response states.

It also demonstrates the importance of validating data before constructing or returning a response.

### 7.4 Java 17 implementation

The Java implementation adopts an enterprise-oriented service architecture.

Its principal types include:

- `APIError`
- `ResponseMetadata`
- `APIResponse<T>`
- `Pagination`
- `Product`
- `ResponsePolicy`
- `ProductRepository`
- `ResponseFactory`
- `ProductService`

Java records provide concise immutable domain representations.

The repository interface separates persistence behavior from service behavior.

The response policy centralizes versioning, maximum page size, request identification, and default consistency.

The service layer handles domain exceptions separately from unexpected application failures.

Prices are represented in integer paise rather than floating-point values, avoiding binary floating-point rounding problems in monetary operations.

## 8. PostgreSQL Relational Model

The SQL implementation stores request execution, response structures, errors, pagination, and resource versioning in a relational schema named `api_design`.

### 8.1 Entity relationships

The primary data relationships are:

`API Version`
    |
    +---- API Request
              |
              +---- API Response
                         |
                         +---- Error Details
                         |
                         +---- Pagination
                         |
                         +---- Response Links

`API Client`
    |
    +---- API Request

`Error Catalogue`
    |
    +---- API Response

`Product`
    |
    +---- Product Update Audit

This model separates the request lifecycle from the product resource lifecycle.

### 8.2 Integrity constraints

The database uses:

- Primary keys for entity identity.
- Foreign keys for referential integrity.
- Unique constraints for request-response relationships.
- Check constraints for status and data relationships.
- Enumerated types for controlled values.
- Indexes for frequently queried attributes.

A response cannot be marked successful with a failure HTTP status or a populated error code.

A failed response cannot contain success data.

A response must reference an existing request.

These constraints protect persisted response records even when multiple application services access the database.

### 8.3 Functions and procedures

`complete_api_request` creates a response and updates request completion metadata within the calling transaction.

`update_product_price` performs an optimistic-concurrency update using the expected resource version.

If the resource does not exist, the function raises a not-found error.

If the resource exists but its version differs, it raises a serialization-style conflict using SQLSTATE `40001`.

### 8.4 Trigger-based auditing

The `audit_product_update` trigger detects changes to product prices.

It increments the version and records:

- Previous price
- New price
- Previous version
- New version
- Change timestamp

This keeps resource-version maintenance close to the database update operation.

The trigger does not increment the version when the price remains unchanged.

### 8.5 Views and reporting

`response_envelope_view` combines request, response, API version, and error catalogue information into a reusable representation.

`api_response_metrics` groups operational results by endpoint, response status, and HTTP status.

The reporting queries demonstrate:

- Response distribution
- Error frequency
- Average processing duration
- 95th-percentile processing duration
- Error severity
- Retryable error identification
- Consistency-level comparison

The SQL uses a CTE and window functions for ranked error reporting.

## 9. Response Contract and Workflow

A typical request-processing lifecycle is:

`Incoming Request`
       |
       v
`Request Identification`
       |
       v
`Authentication and Authorization`
       |
       v
`Input Validation`
       |
       v
`Business Operation`
       |
       +--------------------+
       |                    |
       v                    v
`Successful Result`   `Domain Failure`
       |                    |
       v                    v
`Build Data`          `Build Error`
       |                    |
       +---------+----------+
                 |
                 v
       `Attach Metadata`
                 |
                 v
       `Validate Envelope`
                 |
                 v
       `Serialize Response`
                 |
                 v
       `Record Operational Data`

The workflow separates business execution from response formatting.

A common response factory prevents different endpoints from implementing incompatible envelopes.

A centralized exception boundary prevents unexpected errors from becoming inconsistent public responses.

## 10. Security and Operational Considerations

### 10.1 Information disclosure

Error responses should contain only information required by the client.

Database exceptions, stack traces, credentials, and internal infrastructure details belong in protected diagnostic logs.

### 10.2 Request identifiers

Request and correlation identifiers improve observability.

They should be generated or validated by trusted infrastructure rather than accepted as unrestricted client-controlled values.

### 10.3 Metadata validation

Metadata should not become an uncontrolled extension point.

The implementations validate essential metadata structures and restrict database link relations.

Production systems should also limit metadata size and reject unsupported fields where strict contracts are required.

### 10.4 Idempotency

Retries of state-changing operations can produce duplicate side effects.

An idempotency key can associate repeated submissions with a previously recorded operation result.

The current examples demonstrate response consistency and optimistic concurrency but do not implement a distributed idempotency-key store.

### 10.5 Performance

Response design affects serialization cost, payload size, database access, and client processing.

Practical considerations include:

- Avoiding unnecessary metadata.
- Paginating large collections.
- Indexing frequently filtered database columns.
- Using structured error details rather than repeated diagnostic strings.
- Avoiding repeated database lookups during response construction.
- Using bounded response sizes.
- Measuring latency consistently.
- Applying cursor pagination to large, frequently changing collections.

### 10.6 Observability

Operational monitoring should distinguish:

- Client errors
- Server errors
- Transient failures
- Resource conflicts
- Validation failures
- Latency degradation
- Repeated request failures

A high response count alone does not indicate successful service operation.

Metrics should be interpreted with request volume, response status, latency, and error distribution.

## 11. Testing Scenarios and Expected Behavior

| Scenario | Expected HTTP status | Expected result |
|---|---:|---|
| Retrieve existing product | 200 | Success envelope |
| Retrieve missing product | 404 | Resource-not-found error |
| List valid collection | 200 | Data and pagination metadata |
| Submit invalid pagination | 400 | Validation error |
| Update with current version | 200 | Updated resource and incremented version |
| Update using stale version | 409 | Conflict error |
| Unexpected application exception | 500 | Safe internal error |
| Temporary service failure | 503 | Retryable service error |

The source implementations execute representative success and failure cases.

The PostgreSQL script also demonstrates persisted error records, validation queries, aggregation, transaction handling, and audit retrieval.

## 12. Limitations and Design Boundaries

The implementations are educational service models rather than complete HTTP server deployments.

The in-memory repositories do not provide durable storage or concurrent distributed transactions.

The event-driven JavaScript controller demonstrates asynchronous execution but does not implement a complete HTTP transport layer.

The C++17 program focuses on typed response-state modeling rather than a network server.

The Java implementation uses an in-memory repository and synchronized update methods instead of a distributed persistence layer.

The PostgreSQL script provides relational integrity and transactional operations, but authentication, authorization, connection pooling, and HTTP serialization remain application responsibilities.

The consistency metadata describes an intended service contract. It cannot independently guarantee replica synchronization or distributed consistency.

The examples use page-based pagination and integer resource versions. Production systems may require cursor pagination, entity tags, idempotency records, rate-limit policies, distributed tracing, and explicit API deprecation rules.

## 13. Key Technical Distinctions

| Concept | Responsibility | What it does not guarantee |
|---|---|---|
| Response envelope | Stable outer response structure | Business operation correctness |
| Response data | Returned business representation | Data freshness |
| Response metadata | Request and execution context | Distributed trace completeness |
| Pagination | Controlled collection retrieval | Snapshot consistency |
| Error schema | Standardized failure representation | Automatic recovery |
| HTTP status | Broad protocol-level outcome | Application-specific failure detail |
| Error code | Specific application failure classification | Client authorization |
| Resource version | Detection of stale updates | Global distributed consistency |
| Strong consistency declaration | Describes a consistency contract | Enforcement by metadata alone |
| Retryable flag | Indicates potential retry suitability | Idempotent execution |
| Correlation ID | Connects related operations | Authentication or authorization |

A reliable API response contract requires these elements to work together without combining their responsibilities.

The envelope establishes structure, metadata supplies context, consistency mechanisms describe resource-state behavior, and error schemas communicate failure conditions. Their separation makes API behavior easier to validate, maintain, monitor, and evolve.
