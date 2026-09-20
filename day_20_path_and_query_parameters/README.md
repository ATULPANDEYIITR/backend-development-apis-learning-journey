<!-- File: README.md -->

# Path and Query Parameters

This repository is a practical educational project for understanding path parameters, query parameters, optional parameters, defaults, validation, filtering, and pagination in web APIs.

The main implementation uses FastAPI and Python. A browser interface demonstrates how JavaScript constructs query strings. A C++ implementation models the same parameter-processing concepts without requiring a web framework.

## Project purpose

An HTTP request can carry information in several places. Two of the most common mechanisms are:

- Path parameters identify a particular resource or hierarchical resource.
- Query parameters modify how a collection or operation is processed.

For example:

`GET /products/42`

The value `42` is a path parameter because it is part of the URL path.

`GET /products?category=electronics&limit=10`

The values `category=electronics` and `limit=10` are query parameters because they appear after `?`.

These mechanisms solve different problems and should be designed intentionally.

## Repository structure

`src/path_query_api/main.py` contains the FastAPI application, validation rules, sample data, and endpoints.

`tests/test_main.py` contains automated API tests covering valid requests, invalid values, defaults, boundaries, filtering, and combined parameters.

`web/index.html` contains the browser interface.

`web/style.css` contains the browser presentation.

`web/app.js` constructs query strings and calls the API asynchronously.

`cpp/main.cpp` demonstrates equivalent filtering and validation concepts using C++17.

`cpp/tests.cpp` contains executable C++ tests.

`cpp/CMakeLists.txt` defines the C++ build and test configuration.

`openapi.yaml` documents the API contract.

`Dockerfile` packages the Python API into a non-root container.

`compose.yaml` runs the API as a container service with a health check.

`.github/workflows/ci.yml` runs Python checks, C++ tests, and a Docker build.

## Prerequisites

Python 3.11 or newer is required for the Python implementation.

A modern web browser is required for the browser interface.

C++17 and CMake 3.20 or newer are required for the C++ implementation.

Docker is required for the container workflow.

Git is useful for version control but is not required to execute the source code.

## Installation

Create a virtual environment:

`python -m venv .venv`

On Windows PowerShell:

`.\.venv\Scripts\Activate.ps1`

On macOS or Linux:

`source .venv/bin/activate`

Install the dependencies:

`python -m pip install -r requirements.txt`

## Running the API

Start the development server from the repository root:

`uvicorn path_query_api.main:app --app-dir src --reload`

The API is available at:

`http://127.0.0.1:8000`

FastAPI also provides interactive API documentation at:

`http://127.0.0.1:8000/docs`

The generated OpenAPI document is available at:

`http://127.0.0.1:8000/openapi.json`

## Fundamental terminology

A URL can be viewed conceptually as:

`https://example.com/products/42?category=electronics&limit=10`

The scheme is `https`.

The host is `example.com`.

The path is `/products/42`.

The path parameter is `42` when the application defines the route as `/products/{product_id}`.

The query string is `category=electronics&limit=10`.

The query parameters are `category`, `electronics`, `limit`, and `10` when considered as key-value pairs.

The separator between the path and query string is `?`.

Multiple query parameters are separated by `&`.

A parameter name and its value are separated by `=`.

## Path parameters

A path parameter is embedded in the URL path and is normally used to identify a resource.

The endpoint:

`GET /products/{product_id}`

defines `product_id` as a path parameter.

A request such as:

`GET /products/3`

causes the framework to convert the string representation `3` into the declared Python integer type.

The application then searches for the product whose identifier is `3`.

Path parameters are appropriate when the value is essential to identifying the resource represented by the route.

For example:

`GET /products/3`

means one particular product.

A route such as:

`GET /products`

does not identify one particular product. It represents the product collection.

## Path parameter validation

The application declares:

`product_id: Annotated[int, Path(ge=1)]`

This performs two important operations.

First, the incoming value must be convertible to an integer.

Second, the integer must be greater than or equal to one.

Therefore:

`GET /products/3`

is valid.

`GET /products/0`

is rejected because zero violates the minimum.

`GET /products/abc`

is rejected because `abc` cannot be converted to an integer.

Framework-level validation prevents invalid input from reaching the normal application logic.

## Query parameters

Query parameters normally control how a request is processed without changing which collection endpoint is being addressed.

For example:

`GET /products?category=electronics`

requests products while applying a category filter.

Another request can be:

`GET /products?min_price=30&max_price=100`

The path remains `/products`, but the requested result changes according to the supplied query values.

Common uses include:

- filtering
- searching
- sorting
- pagination
- selecting optional behavior
- controlling result size
- specifying date ranges

## Optional query parameters

A query parameter is optional when a useful default behavior exists without it.

The `category` parameter is declared as nullable:

`category: str | None = None`

When the client calls:

`GET /products`

the value is `None`.

When the client calls:

`GET /products?category=electronics`

the value is `"electronics"`.

This distinction is important because optional parameters allow the same endpoint to support both a general collection request and a more specific filtered request.

## Default values

Defaults allow an endpoint to behave predictably when a client does not provide a value.

The `limit` parameter has a default of `5`.

Therefore:

`GET /products`

behaves as though the client had selected a result limit of five.

The `skip` parameter defaults to zero, meaning that pagination begins at the first matching item.

The `in_stock` parameter defaults to false, meaning the API does not apply the stock filter unless the client explicitly requests it.

Defaults should represent safe and useful normal behavior.

## Query validation

The project validates query parameters before using them.

`min_price` cannot be negative.

`max_price` cannot be negative.

`skip` cannot be negative.

`limit` must be between 1 and 20.

`search` must contain between 1 and 50 characters when supplied.

`category` must contain between 2 and 30 characters when supplied.

The application also performs cross-field validation:

`min_price <= max_price`

This rule cannot be expressed completely by validating either parameter independently. Both values have to be considered together.

For example:

`GET /products?min_price=100&max_price=30`

is rejected.

## Why validation matters

Validation protects application logic from malformed input.

Without validation, negative pagination offsets, unreasonable result sizes, invalid price ranges, or malformed identifiers could reach deeper parts of an application.

Validation also creates a clear API contract.

A client can determine which values are accepted instead of relying on undocumented behavior.

Validation should be applied at the boundary where external input enters the application.

## Combining path and query parameters

An endpoint can use both mechanisms:

`GET /categories/electronics/products?limit=2`

Here:

`electronics` is a path parameter.

`limit=2` is a query parameter.

The path determines the resource collection.

The query parameter controls how many matching resources are returned.

Another example is:

`GET /products/1/reviews?page=2&page_size=5`

`1` identifies the product.

`page` and `page_size` control review pagination.

## Pagination

Pagination prevents a collection endpoint from returning an unnecessarily large response.

This project uses two common parameters:

`skip`

and:

`limit`

For example:

`GET /products?skip=2&limit=3`

means:

- ignore the first two matching records
- return at most three records

The response also reports `total`, which tells the client how many records matched the filters before pagination.

The implementation applies filtering first and pagination second.

This ordering matters.

If pagination were performed before filtering, the returned page could contain fewer useful records than expected.

## Filtering

The collection endpoint supports several filters.

Category:

`GET /products?category=electronics`

Minimum price:

`GET /products?min_price=30`

Maximum price:

`GET /products?max_price=100`

Price range:

`GET /products?min_price=30&max_price=100`

Name search:

`GET /products?search=mouse`

Stock filter:

`GET /products?in_stock=true`

The filters can be combined.

For example:

`GET /products?category=electronics&min_price=30&in_stock=true&limit=5`

The server applies every supplied condition.

## URL encoding

Query parameter values are part of a URL, so characters with special meanings may need URL encoding.

For example, spaces may be encoded as `%20` or represented as `+` in common query-string encoding.

Client-side code should use `URLSearchParams` instead of manually concatenating unescaped values.

The browser implementation in `web/app.js` uses `URLSearchParams` for this reason.

## JavaScript implementation

The browser interface collects values from an HTML form.

The JavaScript code reads those values with `FormData`.

It then creates a `URLSearchParams` object.

Only values that the user supplied are added to the query string, except for the limit field whose form value is explicitly available.

The resulting URL might become:

`http://localhost:8000/products?category=electronics&limit=5`

The browser sends the request using `fetch`.

Because `fetch` is asynchronous, the function uses `async` and `await`.

The response is converted from JSON and rendered into the page.

HTTP errors are handled separately from successful responses.

## C++ implementation

The C++ program models the same concepts without depending on a web framework.

`Product` represents a resource.

`QueryParameters` represents optional query parameters.

`std::optional` is used for values that may not have been supplied.

For example, `min_price` can contain a number or contain no value.

The `validate_query` function performs input validation.

The `filter_products` function applies filters and pagination.

This illustrates that path and query parameter concepts are not limited to one programming language. They are HTTP/API design concepts that can be represented using different application architectures.

## Error handling

A missing product produces HTTP 404.

Invalid parameter values produce HTTP 422 through FastAPI's validation mechanism.

A logically invalid price range also produces HTTP 422.

A validation error should communicate enough information for a client to correct the request without exposing internal implementation details.

## HTTP status codes used by the project

`200 OK` indicates successful requests.

`404 Not Found` indicates that the requested product identifier does not exist.

`422 Unprocessable Entity` indicates that supplied parameter data does not satisfy the API validation rules.

The exact status-code policy of a larger API should be documented and applied consistently.

## Testing

Run the Python test suite with:

`pytest`

The tests cover:

- health checks
- successful path parameters
- missing resources
- path parameter boundaries
- default query values
- category filtering
- price filtering
- invalid price ranges
- boolean query parameters
- search parameters
- pagination
- maximum limits
- invalid pagination values
- combined path and query parameters
- nested resource parameters

Run formatting verification with:

`ruff format --check src tests`

Run linting with:

`ruff check src tests`

Apply formatting with:

`ruff format src tests`

## C++ build and tests

Configure the C++ project:

`cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release`

Build it:

`cmake --build cpp/build --parallel`

Run the C++ test suite:

`ctest --test-dir cpp/build --output-on-failure`

Run the demonstration executable:

`cpp/build/path_query_demo`

On Windows, the generated executable is normally located at:

`cpp/build/Debug/path_query_demo.exe`

for a Visual Studio generator.

## Browser interface

Start the API first:

`uvicorn path_query_api.main:app --app-dir src --reload`

Then serve the `web` directory through a local static server.

One simple Python command is:

`python -m http.server 5500 --directory web`

Open:

`http://127.0.0.1:5500`

The browser application assumes that the API is available at `http://localhost:8000`.

The API allows requests from the local browser only when the browser's request policy permits the connection. For a production frontend on a different origin, the API should explicitly configure CORS for the trusted frontend origin.

## Docker

Build the image:

`docker build -t path-query-api .`

Run the container:

`docker run --rm -p 8000:8000 path-query-api`

The API will then be available at:

`http://127.0.0.1:8000`

The container runs the application as a non-root user.

The image uses a Python slim base image and installs only the declared Python dependencies.

## Docker Compose

Start the service:

`docker compose up --build`

The Compose configuration publishes port 8000 and checks:

`/health`

for container health.

Stop the service:

`docker compose down`

## API examples

Retrieve a single product:

`GET /products/1`

Retrieve the default product collection:

`GET /products`

Filter by category:

`GET /products?category=electronics`

Filter by price:

`GET /products?min_price=30&max_price=100`

Search by product name:

`GET /products?search=keyboard`

Filter by stock:

`GET /products?in_stock=true`

Paginate:

`GET /products?skip=2&limit=3`

Combine filters:

`GET /products?category=electronics&min_price=30&max_price=100&in_stock=true&limit=5`

Use a category path parameter with a query parameter:

`GET /categories/electronics/products?limit=2`

Use nested resource parameters:

`GET /products/1/reviews?page=2&page_size=5`

## Example response

A request to:

`GET /products/1`

returns a structure equivalent to:

`{"id":1,"name":"Mechanical Keyboard","category":"electronics","price":89.99,"stock":24}`

A collection request returns a structure containing `items`, `total`, `skip`, and `limit`.

The collection response separates filtering from pagination metadata so clients can understand both the current page and the total number of matching records.

## Parameter design principles

A path parameter should generally be used when the value identifies the resource represented by the route.

A query parameter should generally be used when the value changes filtering, searching, pagination, sorting, or optional behavior for an existing resource collection.

For example:

`/products/25`

identifies product 25.

`/products?category=books`

filters the product collection.

This is a design convention rather than a limitation imposed by HTTP itself. API designs should remain consistent within a system.

## Optional versus required values

A required path parameter is part of the route definition.

`/products/{product_id}` cannot meaningfully identify one product without `product_id`.

Query parameters can be optional when the endpoint has a useful default behavior.

A query parameter can also be required when an operation has no sensible default. The correct choice depends on the API contract.

## Defaults versus omitted values

A default value is different from an explicitly supplied value.

For example, `limit=5` can produce the same effective result as omitting `limit` because the API's default is five.

By contrast, `in_stock=false` explicitly communicates a boolean choice even though it also matches the default behavior.

When designing APIs, defaults should be documented because clients may rely on them.

## Boundary conditions

Important boundaries include:

`limit=1`

`limit=20`

`skip=0`

`min_price=0`

`page=1`

Values immediately outside those boundaries are rejected.

Testing both sides of a validation boundary is important because an implementation can accidentally accept values that should be rejected or reject values that should be accepted.

## Common mistakes

Putting a resource identifier in a query string when the API convention expects a resource path can make routes inconsistent.

Using path parameters for every optional filter can produce unnecessary route combinations.

Accepting arbitrary pagination values can cause excessively large responses.

Failing to validate related parameters can allow contradictory requests such as a minimum price greater than a maximum price.

Manually concatenating query strings in JavaScript can produce incorrectly encoded URLs.

Treating query parameters as trusted input can expose downstream logic to invalid or unsafe values.

Using a default without documenting it can make client behavior difficult to understand.

## Performance considerations

The example dataset is intentionally small and stored in memory.

Filtering it requires scanning the collection, so the basic filtering operation has linear time complexity, O(n), with respect to the number of products.

Pagination after filtering does not eliminate the cost of scanning the source collection in this implementation.

A production database can use indexes to improve lookup and filtering for appropriate access patterns.

For large datasets, pagination should be designed together with database indexing, query planning, result-size limits, and stable ordering.

Offset pagination using `skip` and `limit` is simple, but very large offsets can become inefficient in some database systems. Cursor-based pagination is another design that can be appropriate for large or frequently changing datasets.

Performance characteristics depend on the storage engine, indexes, data distribution, query shape, and infrastructure.

## Security considerations

Path and query parameters are untrusted external input.

The application validates numeric ranges and string lengths before using them.

The API does not contain credentials or secrets.

Environment-specific secrets should not be committed to source control.

When parameters are used in database queries, parameterized queries should be used instead of string concatenation.

When parameters are used in shell commands, applications should avoid constructing commands from untrusted strings.

When parameters are used to select files, applications should prevent path traversal.

When parameters are used in HTML output, appropriate output encoding must be applied.

Validation is not a complete security boundary. Authorization must also be enforced when a parameter identifies a resource belonging to a particular user or tenant.

## Production considerations

A production API would normally replace the in-memory product list with persistent storage.

Database queries should perform filtering and pagination at the database layer rather than loading an unbounded dataset into application memory.

The API should define authentication and authorization rules when resources are protected.

CORS should be explicitly configured for trusted browser origins.

Rate limiting may be appropriate for public endpoints.

Structured logging and request identifiers can make API operations easier to diagnose.

Metrics should measure request counts, latency, error rates, and resource usage.

Health checks should distinguish between a process being alive and a service being ready to accept traffic.

API contracts should be versioned carefully when parameter names, defaults, validation rules, or response structures change.

## API contract

The authoritative endpoint definitions are also represented in `openapi.yaml`.

FastAPI generates an OpenAPI document from the Python application. The explicit `openapi.yaml` file provides a repository-level version that can be reviewed independently.

The API contract documents:

- parameter location
- required status
- data type
- minimum and maximum values
- defaults
- response structures
- HTTP status codes

Keeping implementation and API documentation synchronized is important because clients depend on the documented contract.

## Architecture

The project uses a small layered educational structure.

The HTTP layer is implemented by FastAPI.

Parameter parsing and validation occur at the API boundary.

The filtering logic operates on validated values.

The response model defines the shape of returned data.

The browser client constructs requests and displays responses.

The C++ implementation isolates parameter validation and filtering into reusable functions.

The automated tests verify externally visible API behavior and important validation rules.

The container packages the Python API for reproducible execution.

GitHub Actions verifies Python, C++, and Docker build integrity.

## Limitations

The product data is stored in memory, so changes are not persistent.

There is no authentication or authorization because the project focuses specifically on parameter handling.

The browser application assumes a local API origin and does not implement production CORS configuration.

The C++ program demonstrates parameter processing but does not implement an HTTP server.

The sample data is deliberately small and should not be interpreted as a benchmark for production database performance.

The API does not implement sorting because the central topic is path and query parameter handling, filtering, validation, defaults, and pagination.

## Real-world applications

Path parameters are common in product, user, order, account, document, repository, and device APIs.

Query parameters are common in search systems, catalog filtering, reporting APIs, analytics interfaces, pagination, dashboards, and administrative systems.

A typical enterprise endpoint can combine both mechanisms:

`GET /customers/42/orders?status=paid&limit=20`

The customer identifier selects the resource context.

The query parameters control which orders are returned and how many are included in the response.

The same design principles apply across languages and frameworks because the underlying concept is HTTP resource addressing and request parameter handling.
