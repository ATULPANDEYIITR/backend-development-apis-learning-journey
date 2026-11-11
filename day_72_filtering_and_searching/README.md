# Filtering and Searching

## 1. Technical Scope

Filtering and searching are mechanisms for retrieving relevant records from a larger dataset using user-defined conditions.

A search operation can combine several independent requirements:

- Text-based keyword matching.
- Exact category matching.
- Numeric ranges.
- Minimum rating requirements.
- Boolean conditions.
- Sorting.
- Pagination.
- Dynamic query construction.

The implementations use an electronic product catalog to demonstrate these operations across Python, JavaScript, C++17, Java 17, and PostgreSQL.

The central engineering problem is to transform search parameters into a valid, efficient, deterministic retrieval operation without exposing the application to invalid inputs or unsafe query construction.

## 2. Filtering and Searching Concepts

### 2.1 Filtering

Filtering reduces a dataset by retaining records that satisfy specified conditions.

For example, a catalog containing 1,000 products might be filtered using:

- Category = Electronics.
- Price >= 1,000.
- Price <= 10,000.
- Rating >= 4.0.
- Active = TRUE.

Each condition eliminates records that do not satisfy the requirement.

The implementations primarily use AND semantics. A record must satisfy every active filter.

For a record \(x\), the combined filtering condition is:

\[
F(x)=f_1(x)\land f_2(x)\land \cdots \land f_n(x)
\]

A record is included only when the resulting expression evaluates to true.

### 2.2 Searching

Searching identifies records matching a textual or structured query.

The implementations support keyword matching against product names and categories or descriptions.

For example, searching for `desk` can return:

- Standing Desk.
- Desk Lamp.

Text matching is case-insensitive.

The distinction is important:

| Operation | Purpose | Example |
|---|---|---|
| Filtering | Apply structured conditions | Price between 1,000 and 10,000 |
| Searching | Find textual matches | Name contains keyboard |
| Sorting | Establish result order | Rating descending |
| Pagination | Retrieve a subset | Records 11–20 |
| Aggregation | Calculate dataset statistics | Average price by category |

Searching and filtering can operate together in one retrieval operation.

### 2.3 Search Parameters

Search parameters represent the conditions supplied by a user or application.

The catalog implementations use the following parameter model:

| Parameter | Type | Purpose |
|---|---|---|
| keyword | String | Text matching |
| category | String or identifier | Category restriction |
| minPrice | Numeric | Minimum acceptable price |
| maxPrice | Numeric | Maximum acceptable price |
| minRating | Numeric | Minimum rating |
| activeOnly | Boolean | Exclude inactive records |
| sortBy | Allowlisted field | Select sorting attribute |
| direction | ASC or DESC | Select sorting direction |
| limit | Integer | Maximum records returned |
| offset | Integer | Number of records skipped |

Parameters are optional unless required by a particular operation.

An absent minimum price must not be interpreted as zero unless the business rule explicitly defines that behavior.

### 2.4 Sorting

Sorting determines the order in which matching records are returned.

Two principal directions are supported:

- ASC: ascending order.
- DESC: descending order.

Examples:

| Attribute | ASC | DESC |
|---|---|---|
| Price | Lowest first | Highest first |
| Rating | Lowest first | Highest first |
| Name | Alphabetical | Reverse alphabetical |
| Creation date | Oldest first | Newest first |

Sorting must occur after filtering and before pagination.

A secondary ordering by product ID provides deterministic ordering when multiple records have equal primary sort values.

Without a deterministic tie-breaker, records with equal sorting values may appear in different positions between requests.

### 2.5 Pagination

Pagination divides a large result set into smaller retrieval units.

The implementations use limit-offset pagination.

\[
\text{Page Start}=\text{Offset}
\]

\[
\text{Page End}=\text{Offset}+\text{Limit}
\]

For example:

| Page | Limit | Offset |
|---|---:|---:|
| 1 | 10 | 0 |
| 2 | 10 | 10 |
| 3 | 10 | 20 |

The total matching record count is calculated independently of the number of records returned on the current page.

An empty page does not necessarily mean that the search condition was invalid. It can indicate that the requested offset exceeds the available result count.

## 3. Dynamic Query Construction

Dynamic query construction creates a query structure based on the search parameters actually supplied.

Consider a request containing:

- Category = Electronics.
- Minimum price = 1,000.
- Maximum price = 10,000.
- Minimum rating = 4.0.
- Sort by rating descending.

The application constructs the equivalent logical operation:

\[
\begin{aligned}
&\text{Active} = TRUE\\
&\land\ \text{Category} = \text{Electronics}\\
&\land\ \text{Price} \geq 1000\\
&\land\ \text{Price} \leq 10000\\
&\land\ \text{Rating} \geq 4.0
\end{aligned}
\]

The sorting and pagination operations are then applied to the matching records.

### 3.1 Conditional Query Components

A dynamic query builder should add only the conditions required by the request.

| Supplied parameter | Query component |
|---|---|
| Keyword | Text matching condition |
| Category | Category equality condition |
| Minimum price | Lower price boundary |
| Maximum price | Upper price boundary |
| Minimum rating | Rating threshold |
| Sort field | Allowlisted ordering expression |
| Direction | Validated ordering direction |
| Limit and offset | Pagination expressions |

This avoids constructing separate hardcoded queries for every possible filter combination.

### 3.2 Parameterized Values

User-provided values must be bound as parameters rather than inserted directly into SQL strings.

Unsafe construction:

- Concatenating a search term into a SQL statement.
- Inserting user-provided category names directly into SQL syntax.
- Accepting arbitrary column names or sorting expressions.

Safe construction separates SQL structure from user data.

The Python implementation uses SQLite parameter binding.

The PostgreSQL implementation uses `EXECUTE ... USING`.

The JavaScript implementation creates structured filter objects rather than executable SQL strings.

Column names and sort directions require special handling because SQL parameters cannot generally replace identifiers. These values must come from strict allowlists.

### 3.3 Search Complexity

For an in-memory dataset containing \(n\) records:

| Operation | Typical complexity |
|---|---|
| Linear filtering | \(O(n)\) |
| Multiple independent filters | \(O(kn)\) |
| Sorting matching records | \(O(m\log m)\) |
| Pagination extraction | \(O(p)\) |
| Full retrieval | \(O(n)\) |

Where:

- \(n\) is the total number of records.
- \(k\) is the number of filtering conditions.
- \(m\) is the number of matching records.
- \(p\) is the number of records returned.

Database performance differs because indexes, query planning, data distribution, and disk operations affect execution cost.

## 4. Python Implementation

### 4.1 Architecture

The Python implementation uses three principal components:

| Component | Responsibility |
|---|---|
| `Product` | Represents a catalog record |
| `CatalogDatabase` | Manages SQLite storage and query construction |
| `SearchService` | Validates application requests and coordinates searching |

`SearchCriteria` is an immutable dataclass that represents the complete search request.

`SortField` and `SortDirection` are enumerations that restrict sorting choices.

### 4.2 Dynamic SQL Construction

The `build_query()` method constructs SQL conditions according to supplied parameters.

It maintains two separate structures:

- SQL conditions.
- Parameter values.

This separation prevents user input from becoming executable SQL syntax.

The sorting column is selected from an allowlist.

The method returns the SQL statement and its parameter collection.

### 4.3 Validation

Validation rejects:

- Negative prices.
- Minimum prices exceeding maximum prices.
- Ratings outside the 0–5 range.
- Invalid sorting fields.
- Invalid sorting directions.
- Negative offsets.
- Limits outside the supported range.
- Excessively long search terms.

The application raises domain-specific exceptions instead of silently changing invalid parameters.

### 4.4 Query Inspection

The implementation uses SQLite's `EXPLAIN QUERY PLAN` to inspect the database's execution strategy.

This helps identify whether an index is being considered and whether a query requires additional optimization.

The script also includes assertions for keyword matching, combined filters, sorting, pagination, and invalid requests.

## 5. JavaScript Implementation

### 5.1 Event-Driven Search Architecture

The JavaScript implementation uses an asynchronous repository and an event-driven search service.

Its main components are:

| Component | Responsibility |
|---|---|
| `CatalogRepository` | Executes searches against the catalog |
| `QueryBuilder` | Converts validated parameters into structured filters |
| `SearchEngine` | Coordinates validation, execution, and events |
| `validateCriteria()` | Checks request parameters |

### 5.2 Structured Query Representation

Instead of constructing SQL strings, the query builder creates structured filter objects.

Each filter contains:

- Field name.
- Comparison operator.
- Comparison value.

The repository evaluates these objects using JavaScript operations.

This approach separates the search request from the storage implementation.

### 5.3 Asynchronous Execution

The repository exposes an asynchronous `execute()` method.

This models an application that retrieves records from an external database or service.

The search engine emits three events:

| Event | Meaning |
|---|---|
| `search:started` | A validated search begins |
| `search:completed` | Search execution succeeds |
| `search:failed` | Search execution fails |

The implementation also accepts an `AbortSignal` to reject cancelled requests.

In production systems, cancellation must also be propagated to the underlying database or network request. Checking the signal alone cannot terminate an operation that does not support cancellation.

### 5.4 Search Consistency

The repository creates immutable product objects and returns sorted copies rather than modifying the original catalog.

This prevents sorting operations from changing the source dataset.

The implementation uses a stable, deterministic tie-breaker based on product ID.

## 6. C++17 Implementation

### 6.1 Domain Model

The C++ implementation uses explicit domain structures:

- `Product`
- `SearchCriteria`
- `SearchResult`

`ProductCatalog` manages the product collection and provides search functionality.

The design separates filtering, sorting, validation, and result extraction into individual operations.

### 6.2 Predicate-Based Filtering

The `matches()` method evaluates the complete set of filtering requirements for an individual product.

The search method evaluates every product and adds matching records to a separate result collection.

The original catalog is not modified.

### 6.3 Comparator-Based Sorting

The `compare()` method supports multiple sorting attributes.

The implementation uses the C++ Standard Library's sorting algorithms.

A product ID tie-breaker ensures deterministic ordering.

### 6.4 State Management

The catalog maintains its records in a vector.

The `addProduct()` method validates new records and prevents duplicate identifiers.

Search operations are read-only.

The separation between source records and filtered results avoids accidental mutation during retrieval.

### 6.5 Edge Cases

The implementation explicitly handles:

- No matching records.
- Offsets beyond the available records.
- Duplicate identifiers.
- Invalid price ranges.
- Invalid ratings.
- Empty search results.
- Invalid pagination limits.

The in-memory approach is appropriate for demonstrating search algorithms. Large datasets would require an indexed storage engine or a dedicated search infrastructure.

## 7. Java 17 Implementation

### 7.1 Enterprise-Oriented Architecture

The Java implementation separates application policy from search execution.

| Component | Responsibility |
|---|---|
| `Product` record | Immutable product representation |
| `SearchCriteria` record | Validated search parameters |
| `SearchResponse` record | Immutable retrieval result |
| `SearchRepository` | Repository abstraction |
| `InMemoryProductRepository` | Sample repository implementation |
| `SearchPolicy` | Search validation policy |
| `SearchService` | Filtering, sorting, pagination, and auditing |

Records reduce unnecessary mutable state and make the domain model explicit.

### 7.2 Predicate Composition

The service constructs individual predicates for each active condition.

The predicates are combined using logical AND semantics.

This allows the search service to support different combinations of optional filters without creating a separate method for every combination.

### 7.3 Comparator Construction

The comparator is selected according to the requested sorting field.

The direction is then applied, followed by a product ID tie-breaker.

This provides consistent result ordering.

### 7.4 Audit Records

Each completed search produces a `SearchAudit` record.

The audit contains:

- Operation name.
- Number of applied filters.
- Matching record count.
- Execution status.

This is useful for measuring search behavior and investigating application issues.

Production implementations should record execution duration, request identity, authorization context, and relevant error classifications without storing sensitive search content unnecessarily.

## 8. PostgreSQL Implementation

### 8.1 Relational Model

The PostgreSQL implementation uses four principal tables.

| Table | Purpose |
|---|---|
| `categories` | Stores product categories |
| `products` | Stores searchable product records |
| `search_requests` | Records search parameters |
| `search_audit` | Stores execution results and metrics |

The relationship is:

    Categories
        |
        | One-to-Many
        |
    Products

    Search Requests
        |
        | One-to-Many
        |
    Search Audit

Foreign keys enforce referential integrity.

Check constraints enforce numeric boundaries and valid search configuration.

### 8.2 Search Function

`search_products()` performs dynamic database searching.

Its responsibilities include:

- Validating search parameters.
- Constructing conditional predicates.
- Selecting an approved sorting column.
- Validating the sorting direction.
- Binding user values.
- Applying pagination.
- Returning the total matching count.

The function uses `COUNT(*) OVER()` to calculate the total matching count independently of pagination.

When the requested page contains no records, the function returns no rows, so the total count is not available from that result alone. A separate count query is necessary if the application must report the total for an empty or out-of-range page.

### 8.3 Database Indexing

Indexes are provided for frequently queried attributes.

| Index | Purpose |
|---|---|
| Category index | Category-based filtering |
| Active and category index | Common combined conditions |
| Price index | Numeric range filtering |
| Rating index | Rating-based filtering |
| Creation timestamp index | Date-based sorting |
| GIN tag index | Array-based tag searching |
| Trigram indexes | Substring text matching |

Indexes are not automatically beneficial for every query.

Their usefulness depends on table size, selectivity, query frequency, and data distribution.

Additional indexes increase storage requirements and the cost of insertions and updates.

The trigram extension requires appropriate database permissions.

### 8.4 Reporting and Aggregation

The `product_search_report` view provides category-level statistics.

It calculates:

- Total products.
- Active products.
- Average price.
- Average rating.
- Minimum price.
- Maximum price.

The CTE demonstrates ranking products within individual categories.

The audit queries measure search activity by user.

### 8.5 Transactions and Failure Handling

The procedure registers search parameters and records execution metrics.

These operations execute within the caller's transaction.

A failed statement can therefore roll back the associated request and audit changes.

The script also demonstrates savepoints and rollback.

Invalid search parameters raise PostgreSQL exceptions rather than producing silently incorrect results.

## 9. Relationship Between Filtering, Searching, Sorting, and Pagination

These mechanisms are separate stages of a retrieval pipeline.

    User Search Parameters
              |
              v
       Input Validation
              |
              v
       Query Construction
              |
              v
        Text Searching
              |
              v
          Filtering
              |
              v
           Sorting
              |
              v
          Pagination
              |
              v
       Search Response
              |
              v
       Audit and Reporting

Their order has practical consequences.

- Searching identifies textual matches.
- Filtering applies structured restrictions.
- Sorting determines the order of the remaining records.
- Pagination selects the requested portion of the ordered result.
- Aggregation calculates statistics over the relevant dataset.

Applying pagination before sorting can produce inconsistent pages.

Applying pagination before filtering can produce incomplete or incorrect results.

## 10. Important Edge Cases

| Scenario | Expected behavior |
|---|---|
| Empty keyword | Do not apply a keyword condition |
| Missing minimum price | Do not impose a lower price boundary |
| Missing maximum price | Do not impose an upper price boundary |
| Minimum exceeds maximum | Reject the request |
| Negative price | Reject the request |
| Rating above 5 | Reject the request |
| Invalid sorting field | Reject the request |
| Invalid direction | Reject the request |
| Zero limit | Reject the request |
| Negative offset | Reject the request |
| No matches | Return an empty result |
| Offset exceeds total | Return an empty page |
| Equal sorting values | Apply a deterministic tie-breaker |
| Inactive product | Exclude when active-only filtering is enabled |
| Malicious search text | Treat it as data, not executable SQL |

## 11. Security Considerations

Search functionality accepts externally supplied parameters and must enforce strict input handling.

Important controls include:

- Parameterized database queries.
- Sorting field allowlists.
- Sorting direction allowlists.
- Numeric boundary validation.
- Maximum keyword lengths.
- Maximum page sizes.
- Restricted database permissions.
- Error handling that avoids exposing database internals.
- Authorization checks before retrieving protected records.
- Query execution limits for expensive searches.

A valid search query is not necessarily an authorized query.

Applications must enforce access restrictions independently of the search filters.

For example, filtering by an employee identifier must not allow a user to retrieve another employee's restricted records.

## 12. Performance and Scalability

### In-Memory Search

Python, JavaScript, C++, and Java use in-memory catalog data.

These implementations demonstrate the logical search pipeline without requiring a running database server.

Their main limitations are memory consumption, linear scanning, and the absence of persistent storage.

### Database Search

PostgreSQL provides indexed retrieval and database-level execution planning.

For larger datasets, optimization should consider:

- Index selectivity.
- Composite index ordering.
- Query execution plans.
- Text-search indexing.
- Connection pooling.
- Result-set size.
- Concurrent searches.
- Pagination consistency.

Offset pagination becomes expensive when offsets are very large because the database may still need to identify and skip preceding records.

Keyset pagination can improve deep-page retrieval by using the last observed sorting values as the next-page boundary.

For example, a price-and-ID cursor can use:

- Last returned price.
- Last returned product ID.

This approach requires a consistent ordering and suitable indexes.

## 13. Implementation Comparison

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Main model | SQLite repository | Event-driven repository | In-memory catalog | Enterprise service | Relational database |
| Filtering | SQL conditions | Structured predicates | Predicate evaluation | Predicate composition | SQL predicates |
| Searching | Parameterized SQL | String matching | Case-insensitive matching | Stream predicates | ILIKE |
| Sorting | Allowlisted SQL | Comparator | STL sorting | Comparator | ORDER BY |
| Pagination | LIMIT/OFFSET | Array slicing | Vector extraction | List slicing | LIMIT/OFFSET |
| Validation | Dataclass and service | Validation function | Validation method | Record and policy | Constraints and function |
| Audit | Logging | Events | Console diagnostics | Audit records | Audit tables |

## 14. Execution

### Python

Run the script using Python 3:

`python catalog_search.py`

The implementation uses the Python standard library and SQLite.

### JavaScript

Run using Node.js 18 or later:

`node catalog_search.js`

No third-party packages are required.

### C++17

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic catalog_search.cpp -o catalog_search`

Run:

`./catalog_search`

### Java 17

Compile:

`javac CatalogSearch.java`

Run:

`java -ea CatalogSearch`

The assertions are enabled with `-ea`.

### PostgreSQL

Execute the SQL script using a PostgreSQL database account with permission to create schemas, tables, functions, procedures, indexes, and the `pg_trgm` extension.

The script recreates the `catalog_search` schema, so existing objects in that schema are removed.

## 15. Practical Applications

The implemented search model applies to:

- E-commerce product catalogs.
- Inventory management systems.
- Employee directories.
- Document repositories.
- Financial transaction reporting.
- Research publication databases.
- Asset management platforms.
- Customer relationship management systems.
- Enterprise reporting applications.

The same retrieval architecture can be extended with date ranges, multiple categories, exclusion filters, tag matching, weighted search, full-text ranking, geographic restrictions, and role-based visibility rules.

The essential design requirement remains the separation of validated search parameters, query construction, filtering logic, deterministic sorting, pagination, and access control.
