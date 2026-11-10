# API Pagination: Offset, Cursor and Keyset Pagination

## 1. Technical Scope

API pagination divides a large result set into smaller, manageable responses. Instead of returning every matching record in one request, an API returns a bounded collection and provides information that allows the client to retrieve subsequent records.

Pagination is important for:

- Large relational databases.
- Product catalogs.
- Transaction histories.
- Activity feeds.
- Audit logs.
- Search results.
- Enterprise reporting systems.
- High-volume public APIs.
- Distributed applications.

Three principal strategies are implemented:

| Strategy | Navigation mechanism | Typical use |
|---|---|---|
| Offset pagination | Record offset and page size | Numbered pages and administrative tables |
| Cursor pagination | Continuation token | Feeds and sequential API navigation |
| Keyset pagination | Last-seen ordering values | Large datasets and efficient sequential traversal |

The implementations use a product catalog containing product identifiers, names, categories, prices, timestamps and activity states.

The central engineering concern is maintaining predictable ordering, controlling query costs, validating pagination state and handling changes to the underlying dataset.

---

## 2. Fundamental Pagination Concepts

### 2.1 Page Size

Page size determines the maximum number of records returned in one response.

For example:

- Total matching products: 250
- Page size: 25
- Total pages: 10

A production API should impose a maximum page size. Unrestricted page sizes can increase database execution time, memory consumption, network transfer and application processing costs.

The implementations enforce configurable limits, with a default page size of 10 and a maximum of 100 in the primary examples.

### 2.2 Deterministic Ordering

Pagination requires a stable ordering rule.

Consider products ordered only by `created_at`. Multiple products may share the same timestamp. If the database returns those records in different orders across requests, records may be repeated or skipped.

A composite ordering key solves this problem:

`ORDER BY created_at ASC, product_id ASC`

The product identifier acts as a unique tie-breaker.

The corresponding comparison is:

`(created_at, product_id)`

This composite key is used throughout the cursor and keyset implementations.

### 2.3 Total Count

An API may return the total number of matching records.

A typical response contains:

| Field | Meaning |
|---|---|
| `data` | Records in the current response |
| `page_size` | Maximum requested records |
| `total_items` | Total matching records |
| `total_pages` | Number of available pages |
| `has_next` | Whether another page exists |
| `has_previous` | Whether a previous page exists |
| `next_cursor` | Continuation token |
| `next_boundary` | Last-seen ordering values |

Exact counts can be expensive for large filtered datasets. Cursor and keyset APIs often omit them to reduce database work.

---

## 3. Offset Pagination

### 3.1 Definition

Offset pagination identifies a result window using:

- Page number
- Page size
- Record offset

The offset is calculated as:

`offset = (page - 1) * page_size`

For example, with a page size of 10:

| Page | Offset | Returned positions |
|---|---:|---|
| 1 | 0 | 1–10 |
| 2 | 10 | 11–20 |
| 3 | 20 | 21–30 |
| 4 | 30 | 31–40 |

The SQL mechanism is:

`LIMIT 10 OFFSET 20`

### 3.2 Execution Workflow

1. Receive the requested page number.
2. Validate the page number and page size.
3. Apply the required filters.
4. Establish deterministic sorting.
5. Calculate the offset.
6. Retrieve the requested records.
7. Calculate the total count when required.
8. Return pagination metadata.

The Python implementation uses list slicing. JavaScript uses array slicing. C++ uses STL iterators. Java uses collection sublists. PostgreSQL uses `LIMIT` and `OFFSET`.

### 3.3 Advantages

- Easy to understand.
- Supports direct navigation to numbered pages.
- Compatible with conventional table interfaces.
- Simple client-side state.
- Supports exact total counts.
- Straightforward database implementation.

### 3.4 Limitations

Offset pagination becomes increasingly expensive when the offset grows.

For example:

`LIMIT 20 OFFSET 1000000`

The database may need to identify and discard a large number of preceding records before returning the requested page.

Another problem is dataset mutation.

Suppose the first page contains records 1–10. Before the second request, a new record is inserted at the beginning.

The second request may return records 10–19 instead of 11–20. Record 10 is repeated.

Deleting records before the offset can produce skipped records.

### 3.5 Appropriate Use

Offset pagination is appropriate for:

- Administrative dashboards.
- Search interfaces with numbered pages.
- Small and moderately sized datasets.
- Reporting interfaces requiring exact page counts.
- Applications where random page access is important.

It is less appropriate for continuously changing, very large datasets.

---

## 4. Cursor Pagination

### 4.1 Definition

Cursor pagination replaces the page number with a continuation token.

The token represents a position in an ordered result set. The client sends the token when requesting the next page.

A simplified workflow is:

1. Client requests the first page.
2. Server retrieves the first batch.
3. Server identifies the last returned record.
4. Server creates a continuation cursor.
5. Client sends the cursor in its next request.
6. Server validates the cursor.
7. Server retrieves records after the stored position.

A cursor is a continuation mechanism, not necessarily a database primary key.

### 4.2 Cursor Structure

The implementations use cursor information containing:

| Attribute | Purpose |
|---|---|
| Strategy | Identifies the pagination mechanism |
| Timestamp | Last-seen ordering timestamp |
| Product ID | Unique ordering tie-breaker |
| Filter fingerprint | Associates the cursor with its original filters |
| Dataset version | Detects relevant repository mutations |
| Expiration | Limits cursor lifetime |
| Signature | Detects token modification |

The cursor position uses the composite ordering key:

`(created_at, product_id)`

### 4.3 Cursor Encoding

The Python implementation serializes the cursor payload into JSON, encodes it using URL-safe Base64 and signs it with HMAC-SHA256.

The JavaScript implementation follows the same security principle using Node.js cryptographic functions.

The Java implementation uses the standard cryptographic API and `MessageDigest.isEqual` for signature comparison.

The C++ example provides a simplified demonstration signer. Its FNV-based hash is not cryptographically secure and must not be used for production authentication.

The PostgreSQL implementation stores a SHA-256 hash of the supplied cursor token instead of storing the raw token.

### 4.4 Cursor Validation

A cursor should be rejected when:

- Its structure is malformed.
- Its signature is invalid.
- Its expiration time has passed.
- Its pagination strategy is incorrect.
- Its filter fingerprint does not match.
- Its dataset version is stale.
- Its boundary values are invalid.

The cursor must be validated before it influences a database query.

### 4.5 Fetching an Extra Record

A useful implementation technique is retrieving one additional record.

For a requested page size of 10, the database retrieves 11 records.

- If 11 records are returned, another page exists.
- If 10 or fewer are returned, another page does not exist.

This avoids performing an additional exact-count query merely to calculate `has_next`.

### 4.6 Advantages

- Clients do not need to maintain page numbers.
- Sequential navigation is straightforward.
- Tokens can encapsulate pagination state.
- Suitable for feeds and continuously consumed datasets.
- Can avoid large offset calculations.
- Can bind navigation to a specific query.

### 4.7 Limitations

- Direct access to arbitrary page numbers is difficult.
- Cursor generation and validation introduce complexity.
- Cursor state requires versioning and expiration rules.
- Cursor tokens must be protected against tampering.
- Exact total counts are not naturally available.
- Cursor semantics depend on the underlying ordering and consistency model.

### 4.8 Appropriate Use

Cursor pagination is suitable for:

- Social activity feeds.
- Event streams.
- Notification histories.
- API integrations.
- Large sequential search results.
- Continuously consumed records.

---

## 5. Keyset Pagination

### 5.1 Definition

Keyset pagination retrieves records relative to the last record in the preceding page.

It uses actual ordering-column values rather than a numeric offset.

For ascending order:

`WHERE (created_at, product_id) > (:last_created_at, :last_product_id)`

The result is ordered using:

`ORDER BY created_at ASC, product_id ASC`

The database retrieves a bounded number of records.

### 5.2 Example

Suppose the previous page ended with:

| Product ID | Created timestamp |
|---:|---|
| 105 | 2026-01-01 10:00:00 |
| 106 | 2026-01-01 10:00:00 |
| 107 | 2026-01-01 10:02:00 |

The next request supplies the last composite key:

`(2026-01-01 10:02:00, 107)`

The next page selects records whose composite key is greater than that boundary.

The unique identifier resolves records sharing the same timestamp.

### 5.3 Ascending and Descending Navigation

For ascending navigation:

`(created_at, product_id) > (:timestamp, :id)`

For descending navigation:

`(created_at, product_id) < (:timestamp, :id)`

The ordering direction must match the comparison operator.

Incorrect combinations can cause records to repeat or disappear.

### 5.4 Database Indexing

Keyset pagination benefits from an index aligned with the filter and ordering columns.

For example:

`CREATE INDEX ON products (repository_id, created_at, product_id);`

For frequently filtered active products, a partial index can be used:

`CREATE INDEX ON products (repository_id, created_at, product_id) WHERE status = 'ACTIVE';`

For category-specific queries, the category column can be included before the ordering columns.

The actual index design should match the query predicates and execution plan.

### 5.5 Advantages

- Avoids increasingly large offsets.
- Supports efficient sequential navigation.
- Uses explicit ordering boundaries.
- Works well with indexed relational datasets.
- Reduces unnecessary scanning of earlier records.
- Supports stable ordering when a unique tie-breaker exists.

### 5.6 Limitations

- Direct arbitrary page navigation is difficult.
- The ordering columns must be suitable for comparison.
- Composite ordering must be implemented correctly.
- Changes to ordering values can affect navigation.
- Nullable ordering columns require explicit handling.
- Complex multi-column sorting requires corresponding boundary logic.

### 5.7 Appropriate Use

Keyset pagination is appropriate for:

- Large transaction histories.
- Audit records.
- Financial event tables.
- Enterprise reporting.
- High-volume product catalogs.
- Large database tables with indexed ordering columns.

---

## 6. Differences Between Cursor and Keyset Pagination

These approaches are related but not interchangeable.

Keyset pagination describes the record-selection technique. Cursor pagination describes a continuation interface that can carry the required position and other query state.

A cursor may internally represent a keyset boundary.

| Characteristic | Cursor Pagination | Keyset Pagination |
|---|---|---|
| Primary concept | Continuation token | Ordering boundary |
| Client state | Cursor token | Last-seen values or token |
| Query mechanism | Depends on cursor contents | Comparison against ordered keys |
| Arbitrary page navigation | Usually unavailable | Usually unavailable |
| Security | Token integrity must be considered | Boundary validation required |
| Database indexing | Depends on underlying query | Composite index is important |
| Expiration | Common for stateful cursors | Not inherently required |
| Query fingerprint | Useful for preventing misuse | Optional, depending on interface |
| Dataset version | Can be enforced through token state | Depends on consistency requirements |

A keyset query can operate without an opaque cursor. An opaque cursor can encapsulate a keyset boundary.

---

## 7. Dataset Mutation and Consistency

Pagination is affected by concurrent inserts, updates and deletions.

### 7.1 Offset Mutation

Offset pagination can return duplicate or missing records when earlier records are inserted or deleted between requests.

### 7.2 Cursor Mutation

The Python and C++ examples demonstrate cursor version validation. The JavaScript and Java implementations also compare repository versions.

The PostgreSQL implementation maintains a repository version that increments when product records change.

A cursor becomes stale when its stored version differs from the current repository version.

The application can then reject the cursor and request a new pagination session.

### 7.3 Keyset Mutation

Keyset pagination avoids many offset-related problems, but it does not automatically provide a complete database snapshot.

For example:

- A newly inserted record after the current boundary may appear in a later page.
- A record inserted before the boundary may not appear during the current traversal.
- A deleted record will no longer be returned.
- An update to an ordering field may move a record across the boundary.

A stable multi-request snapshot requires an explicit consistency design.

Possible approaches include:

- Database snapshot transactions where the operational model permits them.
- Immutable ordering fields.
- A fixed upper-bound timestamp or identifier.
- Snapshot identifiers.
- Versioned data.
- Materialized result sets.

A long-running database transaction should not be held open across ordinary HTTP requests without careful consideration of resource retention and transaction isolation.

### 7.4 Strict Versioning Trade-off

The demonstration implementations use strict dataset version checks for cursor validation.

This is easy to understand and prevents continued traversal after any repository mutation.

It can also invalidate a cursor because of an unrelated record update.

Large distributed applications may instead use a snapshot identifier, immutable ordering boundaries or a less restrictive consistency model.

---

## 8. API Request and Response Design

### 8.1 Offset API

Example request:

`GET /api/v1/products?page=2&page_size=10`

Example response structure:

| Field | Example |
|---|---|
| `page` | 2 |
| `page_size` | 10 |
| `total_items` | 100 |
| `total_pages` | 10 |
| `has_next` | true |
| `has_previous` | true |

### 8.2 Cursor API

Example request:

`GET /api/v1/products?limit=10&cursor=SIGNED_TOKEN`

The server validates the token and returns the next set of records.

Example response structure:

| Field | Purpose |
|---|---|
| `data` | Returned records |
| `has_next` | Indicates another page |
| `next_cursor` | Continuation token |
| `page_size` | Requested page size |

### 8.3 Keyset API

Example request:

`GET /api/v1/products?limit=10&last_created_at=2026-01-01T10:00:00Z&last_id=107`

The server applies the composite boundary and returns the following records.

A production API may expose these boundary values directly or place them inside a signed opaque token.

### 8.4 API Response Rules

A reliable pagination API should:

- Use consistent response structures.
- Validate all pagination parameters.
- Enforce maximum page sizes.
- Define deterministic ordering.
- Return a clear indication of additional records.
- Avoid exposing database credentials or signing secrets.
- Use parameterized database queries.
- Document filter and sorting behavior.
- Return appropriate client errors for invalid cursors.
- Avoid returning unnecessary exact counts.

---

## 9. Python Implementation

The Python program implements a complete in-memory pagination service.

### Main components

| Component | Responsibility |
|---|---|
| `Product` | Immutable product domain model |
| `ProductRepository` | Product storage and mutation |
| `PaginationEngine` | Executes all three pagination strategies |
| `CursorCodec` | Encodes, signs and validates cursor payloads |
| `PaginationResult` | Represents returned page metadata |
| `PaginationStrategy` | Identifies the pagination mechanism |
| `InvalidCursorError` | Handles malformed or invalid cursors |

### Offset implementation

The `offset_page()` method validates the requested page and calculates the record offset.

It sorts the dataset deterministically, applies the optional category filter and returns the requested slice.

The total record count is included.

### Cursor implementation

The `cursor_page()` method decodes the continuation token and checks:

- Signature validity.
- Expiration.
- Strategy.
- Filter fingerprint.
- Boundary values.

It retrieves one additional record to calculate `has_next`.

The cursor is bound to the filter used for the original request.

### Keyset implementation

The `keyset_page()` method compares the timestamp and product ID together.

It supports ascending and descending navigation and rejects incomplete boundary values.

### Security considerations

- HMAC-SHA256 protects cursor integrity.
- Constant-time signature comparison reduces timing leakage.
- Cursor expiration limits token lifetime.
- The signing secret must be securely managed.
- Base64 encoding does not provide confidentiality.
- Cursor contents must not contain sensitive information.

### Testing

The script validates:

- Page-size restrictions.
- Invalid page numbers.
- Cursor tampering.
- Cursor expiration.
- Filter mismatch.
- Non-overlapping pages.
- Continuation behavior.

The JSON export uses a temporary file followed by replacement to reduce the risk of partially written reports.

---

## 10. JavaScript Implementation

The JavaScript implementation emphasizes asynchronous services, event-driven operations and policy-based execution.

### Main components

| Component | Responsibility |
|---|---|
| `Product` | Validated product object |
| `ProductRepository` | Map-based data repository |
| `CursorService` | HMAC cursor encoding and decoding |
| `PaginationPolicy` | Enforces pagination limits |
| `PaginationService` | Executes pagination requests |
| `PaginationError` | Structured pagination failures |
| `EventEmitter` | Publishes repository and pagination events |

### Repository design

The repository uses a private `Map` keyed by product ID.

This provides direct lookup and prevents accidental exposure of internal storage.

Repository mutations increment a version counter and emit events.

### Asynchronous execution

Repository access methods return promises.

The pagination service uses asynchronous operations so the same interface can later be connected to a relational database or remote data service.

### Event-driven monitoring

The service emits:

- `pagination:completed`
- `repository:changed`
- `product:inserted`
- `product:updated`
- `product:deleted`

These events can support monitoring, application metrics and audit integration.

### Policy enforcement

The `PaginationPolicy` object determines:

- Default page size.
- Maximum page size.
- Enabled pagination strategies.

The policy separates application-level restrictions from pagination execution.

### Security considerations

The implementation uses Node.js cryptographic functions and timing-safe signature comparison.

The cursor contains a dataset version and filter fingerprint.

A production service should use a shared secret-management system, account for secret rotation and define a consistent versioning strategy across application instances.

---

## 11. C++17 Implementation

The C++ program models pagination as a repository-oriented domain engine.

### Main components

| Component | Responsibility |
|---|---|
| `Product` | Product domain structure |
| `ProductRepository` | Ordered product storage |
| `PaginationConfig` | Page-size and page-number validation |
| `CursorSigner` | Demonstration cursor serialization and integrity checking |
| `PaginationEngine` | Pagination algorithms |
| `PageRequest` | Offset request parameters |
| `PageResult` | Page result and metadata |
| `CursorPosition` | Composite keyset boundary |

### Data structures

The repository uses `std::map` for product storage.

The map provides predictable ID ordering and logarithmic lookup and insertion.

The pagination engine creates filtered vectors and sorts them by timestamp and product ID.

STL algorithms provide deterministic sorting and bounded result construction.

### Error handling

`PaginationException` handles:

- Invalid page sizes.
- Invalid page numbers.
- Offset overflow.
- Invalid product IDs.
- Duplicate products.
- Invalid cursor signatures.
- Cursor expiration.
- Stale repository versions.

### Cryptographic limitation

The C++ cursor signer is deliberately a simplified demonstration implementation.

Its FNV-1a hash does not provide cryptographic authentication.

It must be replaced by a vetted HMAC-SHA256 implementation before deployment in a production API.

The C++ implementation therefore demonstrates pagination mechanics and integrity-checking structure without claiming production-grade cryptographic security.

---

## 12. Java 17 Implementation

The Java program uses an enterprise-oriented service architecture.

### Main components

| Component | Responsibility |
|---|---|
| `Product` | Immutable product record |
| `Repository` | Repository contract |
| `ProductRepository` | Concurrent product storage |
| `PaginationPolicy` | Enterprise pagination restrictions |
| `CursorService` | Cryptographic token processing |
| `PaginationService` | Pagination execution |
| `PageResult` | Immutable result representation |
| `PaginationTests` | Validation of pagination behavior |

### Immutable domain model

Java records represent products, requests, cursor positions, cursor payloads and page results.

The compact constructor of `Product` validates incoming values.

`PageResult` uses `List.copyOf()` to prevent modification of the returned collection.

### Service separation

The repository manages product storage.

The policy manages permitted request sizes.

The cursor service handles token authentication.

The pagination service implements the three retrieval strategies.

This separation makes the implementation easier to test and maintain.

### Concurrency

The repository uses `ConcurrentHashMap` and `AtomicLong`.

These structures support concurrent access and version tracking.

The demonstration still uses synchronized repository methods to keep multi-step mutation and version updates consistent.

A production implementation should define transaction boundaries and snapshot behavior at the database layer.

### Security

The Java cursor implementation uses HMAC-SHA256.

`MessageDigest.isEqual()` is used for signature comparison.

The cursor also includes a filter fingerprint, repository version and expiration timestamp.

---

## 13. PostgreSQL Implementation

The PostgreSQL script models pagination using relational structures and executable SQL routines.

### Database relationship

    Repository State
          |
          v
       Products
          |
          v
    Pagination Policies
          |
          v
    Pagination Cursors
          |
          v
    Pagination Audit
          |
          v
    Reporting Views

### Main tables

| Table | Purpose |
|---|---|
| `repository_state` | Stores repository identity and dataset version |
| `products` | Stores product records |
| `pagination_policies` | Defines permitted strategies and page sizes |
| `pagination_cursors` | Stores cursor hashes and continuation boundaries |
| `pagination_audit` | Records pagination requests and execution metrics |

### Repository state

The `repository_state` table maintains a version number.

A product mutation increments this version through a trigger.

Cursor validation compares the stored version with the current version.

This detects changes that invalidate the demonstration's strict cursor consistency policy.

### Pagination policies

The `pagination_policies` table stores:

- Enabled pagination strategies.
- Default page size.
- Maximum page size.
- Cursor expiration duration.
- Exact-count permissions.

The `validate_page_size()` function centralizes page-size validation.

### Offset SQL function

`get_products_offset()`:

- Validates page number.
- Validates page size.
- Calculates the offset.
- Applies category filtering.
- Uses deterministic sorting.
- Calculates total records.
- Writes audit information.

Its query uses a CTE to separate filtering and counting.

### Keyset SQL function

`get_products_keyset()` uses PostgreSQL row comparisons.

The ascending condition is:

`(created_at, product_id) > (last_created_at, last_product_id)`

The descending condition uses the opposite comparison and sort direction.

The function returns one additional record so the application can determine whether another page exists.

### Cursor registration

`register_cursor()` stores a hash of the application-provided token.

It records:

- Repository identity.
- Strategy.
- Boundary timestamp.
- Boundary product ID.
- Filter fingerprint.
- Dataset version.
- Direction.
- Expiration time.

The application is responsible for generating and cryptographically signing the original token.

PostgreSQL's stored hash is used to locate the corresponding cursor record.

### Cursor validation

`validate_cursor()` checks:

- Whether the cursor exists.
- Whether it has expired.
- Whether its filters match.
- Whether the repository version remains valid.

It returns a structured validation result.

### Triggers

The `trg_product_version` trigger increments the repository version following product insertion, update or deletion.

This centralizes dataset version maintenance and avoids relying on individual application operations to update the counter.

### Indexing

The script creates indexes for:

- Repository and timestamp ordering.
- Category-specific ordering.
- Product status.
- Cursor expiration.
- Repository cursor versions.
- Pagination audit history.

Partial indexes reduce index storage and maintenance for queries that consistently retrieve active products.

### Views

`pagination_strategy_report` aggregates pagination activity by strategy.

`product_category_statistics` summarizes active products and price distributions.

### Performance analysis

The SQL script includes `EXPLAIN (ANALYZE, BUFFERS)` for an offset query and a keyset query.

These statements expose actual execution plans, buffer usage and execution time.

Performance conclusions should be based on the actual database, dataset size, index configuration and query plan rather than assumptions based only on the pagination strategy.

---

## 14. Performance Comparison

| Dimension | Offset | Cursor | Keyset |
|---|---|---|---|
| Initial implementation complexity | Low | Medium | Medium |
| Random page access | Yes | No, generally | No, generally |
| Exact total count | Straightforward | Optional | Optional |
| Large offsets | Expensive | Avoidable | Avoidable |
| Sequential traversal | Supported | Supported | Supported |
| Stable ordering required | Yes | Yes | Yes |
| Token management | No | Usually | Optional |
| Composite index importance | Useful | Depends on query | High |
| Mutation handling | Requires care | Requires explicit policy | Requires explicit policy |
| Best application fit | Numbered tables | Feeds | Large ordered datasets |

### Complexity considerations

Let:

- `N` represent the number of matching records.
- `k` represent the requested page size.
- `o` represent the requested offset.

For an already sorted array:

| Operation | Typical complexity |
|---|---|
| Offset array slicing | O(k), excluding filtering and sorting |
| Sorting an unsorted dataset | O(N log N) |
| Linear cursor boundary filtering | O(N) |
| Linear keyset boundary filtering | O(N) |
| Hash-map product lookup | Average O(1) |

These in-memory examples perform filtering and sorting to demonstrate the algorithms. Their complexity should not be confused with an indexed database query.

For an appropriately indexed relational database, keyset pagination can seek to a composite boundary and retrieve approximately `k` records, subject to query predicates, index selectivity and execution-plan behavior.

Offset pagination may need to process preceding index entries before reaching a large offset.

Cursor pagination inherits the performance characteristics of the database query represented by its token.

---

## 15. Security and Production Considerations

### 15.1 Parameterized Queries

Pagination parameters and filters must be passed as bound database parameters.

Dynamic SQL identifiers, sorting expressions and column names must be validated against explicit allowlists.

Unvalidated SQL string concatenation can introduce SQL injection vulnerabilities.

### 15.2 Page-Size Restrictions

The maximum page size must be enforced server-side.

Client-side validation alone does not protect database resources.

### 15.3 Cursor Integrity

A client must not be able to change the cursor boundary or other protected fields without detection.

HMAC signatures provide integrity and authenticity when the secret remains confidential.

Base64 is not encryption.

Sensitive cursor state should not be exposed merely because it is encoded.

### 15.4 Cursor Expiration

Cursor expiration limits how long an old continuation token remains usable.

The expiration duration should match the application's navigation and consistency requirements.

### 15.5 Secret Management

Signing keys should:

- Be stored outside source code.
- Be distributed securely across application instances.
- Support rotation.
- Never appear in logs.
- Be protected by access controls.

### 15.6 Rate Limiting

Pagination does not eliminate abusive API traffic.

Requests should be subject to authentication, authorization, rate limits and resource controls.

### 15.7 Query Monitoring

Useful monitoring fields include:

- Pagination strategy.
- Requested page size.
- Returned row count.
- Execution time.
- Filter category.
- Cursor validation failures.
- Stale cursor frequency.
- Database query latency.

Cursor tokens themselves should not be written into ordinary application logs.

### 15.8 Database Consistency

The application must explicitly choose whether pagination operates over:

- A changing live dataset.
- A fixed snapshot.
- A bounded time interval.
- A versioned dataset.

The choice affects whether records inserted or modified between requests should appear in the ongoing traversal.

### 15.9 Backward Navigation

Backward pagination requires an explicit ordering and boundary strategy.

For ascending results, a backward request generally selects records before the first record of the current page, retrieves them in reverse order and then restores the desired response order.

It should not be implemented by simply decrementing an arbitrary cursor value.

### 15.10 Operational Limits

Production implementations should also consider:

- Database connection pooling.
- Query timeouts.
- Maximum response payload size.
- Request cancellation.
- Cursor version compatibility.
- Distributed cache consistency.
- Database failover.
- Index maintenance.
- Audit retention.
- Concurrent record modifications.

---

## 16. Important Edge Cases

| Scenario | Expected behavior |
|---|---|
| Page number is zero | Reject request |
| Negative page size | Reject request |
| Page size exceeds maximum | Reject request |
| Empty result set | Return an empty collection |
| Final page contains fewer records | Set `has_next` to false |
| Timestamp values are identical | Use unique ID as tie-breaker |
| Cursor is malformed | Reject request |
| Cursor signature is invalid | Reject request |
| Cursor has expired | Reject or restart traversal |
| Cursor filter changes | Reject cursor |
| Repository version changes | Apply the selected consistency policy |
| Product is deleted | Follow the documented mutation policy |
| Ordering field changes | Account for movement across the boundary |
| Offset calculation overflows | Reject request |
| Keyset boundary is incomplete | Reject request |
| Unsupported sort direction | Reject request |
| Category does not exist | Return an empty collection |

---

## 17. Practical Selection Framework

| Application requirement | Preferred approach |
|---|---|
| Numbered administrative table | Offset |
| Small searchable catalog | Offset |
| Activity feed | Cursor |
| Notification stream | Cursor |
| Large financial transaction history | Keyset |
| Large audit-log table | Keyset |
| API integration with sequential traversal | Cursor |
| Direct navigation to page 50 | Offset |
| High-volume indexed dataset | Keyset |
| Opaque continuation interface | Cursor |

The choice should reflect actual navigation requirements, dataset size, consistency expectations and database indexing.

No single pagination strategy is universally optimal.
