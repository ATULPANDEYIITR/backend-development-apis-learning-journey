# FastAPI introduction

## Topic

This study covers the foundations of FastAPI with emphasis on:

- FastAPI architecture
- the application instance
- routes
- decorators
- path operations
- HTTP methods
- path parameters
- query parameters
- request validation
- request bodies
- response models
- dependencies
- routing organization
- OpenAPI documentation
- synchronous and asynchronous path operations
- error handling
- security
- performance
- production-oriented architecture

The three implementations approach the subject differently. Python demonstrates the actual FastAPI programming model. JavaScript models the underlying web and routing ideas through a small executable HTTP service. C++ develops a more explicit industry-style API architecture using standard library components.

## FastAPI architecture

FastAPI is a Python web framework designed for building APIs. It is based on the ASGI application model.

A simplified request lifecycle is:

Client → ASGI server → FastAPI application → router → path operation → validation and dependencies → application logic → response serialization → ASGI server → client

An ASGI server such as Uvicorn provides the server-side execution environment. The FastAPI application receives requests through the ASGI interface and uses its routing and validation facilities to determine which Python function should process each request.

FastAPI builds on Starlette for core web functionality and Pydantic for data validation and serialization.

The architecture separates several responsibilities:

- the server handles network and protocol communication
- the application instance owns the API configuration
- routing determines which operation handles a request
- path operations define endpoint behavior
- validation converts and checks incoming data
- dependencies provide reusable request-scoped functionality
- application and service layers implement business rules
- persistence layers communicate with databases or other storage systems

This separation becomes increasingly important as an API grows.

## The application instance

The basic FastAPI application begins with:

`app = FastAPI()`

`FastAPI()` creates an application object. The object becomes the central registration point for API behavior.

Typical configuration can include:

`app = FastAPI(title="Product API", version="1.0.0")`

The application instance can contain or coordinate:

- routes
- path operations
- routers
- dependencies
- middleware
- exception handlers
- metadata
- OpenAPI configuration
- lifecycle behavior

The Python implementation creates a real FastAPI application instance when the package is installed and registers multiple operations against it.

The application is then capable of being served by an ASGI server such as Uvicorn.

For example, a module containing an object named `app` can normally be served with:

`uvicorn fastapi_introduction:app --reload`

The important distinction is that `app` is an object representing the web application. It is not the same thing as an individual endpoint.

## Routes

A route describes how an HTTP request is mapped to an operation.

Examples include:

- `GET /`
- `GET /users`
- `GET /users/{user_id}`
- `POST /products`
- `PUT /products/{product_id}`
- `DELETE /products/{product_id}`

A route contains two particularly important pieces:

- an HTTP method
- a URL path pattern

The Python implementation registers routes with decorators such as `@app.get("/")`, `@app.post("/products")`, and `@app.delete("/products/{product_id}")`.

The application can expose multiple operations using the same path with different HTTP methods. For example, `GET /products` and `POST /products` represent different path operations even though the URL path is identical.

## Decorators

FastAPI makes extensive use of Python decorators.

A typical declaration is:

`@app.get("/users/{user_id}")`

followed by:

`def get_user(user_id: int):`

Python decorator syntax is conceptually related to:

`function = decorator(function)`

The decorator receives the function and can register metadata about it.

FastAPI's route decorators do considerably more than the small educational decorator demonstrated in the Python script. They associate the endpoint function with information such as:

- HTTP method
- URL path
- endpoint function
- request parameters
- validation rules
- dependencies
- response configuration
- documentation metadata

This allows FastAPI to inspect the Python function and build an API contract from its declaration.

## Path operations

A path operation combines an HTTP method, a path, and a Python callable.

For example:

`@app.get("/products/{product_id}")`

with:

`def get_product(product_id: int):`

defines a GET path operation.

Common FastAPI decorators include:

- `@app.get()`
- `@app.post()`
- `@app.put()`
- `@app.patch()`
- `@app.delete()`
- `@app.options()`
- `@app.head()`

The HTTP method describes the intended interaction.

GET is commonly used to retrieve information.

POST is commonly used to create resources or initiate server-side operations.

PUT is commonly used for replacement or complete updates.

PATCH is commonly used for partial updates.

DELETE is commonly used to remove a resource.

The precise semantics should be defined by the API contract rather than inferred solely from the function name.

## Path parameters

A path parameter is embedded directly into the URL.

Example:

`/products/{product_id}`

A request such as:

`/products/42`

provides `42` as the value of `product_id`.

FastAPI can use a type annotation to validate and convert the value:

`def get_product(product_id: int):`

The declared type means the endpoint expects an integer.

A request containing a value that cannot be interpreted as the required type is rejected during validation rather than being passed to the endpoint as an arbitrary string.

The Python study script demonstrates integer and floating-point path parameters.

The C++ case study implements explicit conversion with `parsePositiveInteger()` to show what type conversion and validation conceptually accomplish.

## Query parameters

Query parameters appear after `?` in a URL.

Example:

`/search?q=keyboard&limit=5`

Here:

- `q` is `keyboard`
- `limit` is `5`

A FastAPI endpoint can declare:

`def search_products(q: str | None = None, limit: int = 10):`

The function signature communicates the expected request structure.

Path and query parameters serve different roles.

A path parameter often identifies a specific resource:

`/products/42`

A query parameter often modifies retrieval:

`/products?category=monitors&limit=20`

The JavaScript implementation demonstrates query parsing with the standard `URL` and `URLSearchParams` APIs. The C++ implementation uses a map of query values and explicitly validates the `limit` parameter.

## Request bodies

POST, PUT, and PATCH operations commonly receive structured request bodies.

The Python implementation uses a Pydantic model:

`class Product(BaseModel):`

with fields such as:

`name: str`

and:

`price: float`

Constraints can also be specified. The example requires the product name to have an acceptable length and the price to be greater than zero.

A request body therefore becomes more than an unvalidated dictionary. The model provides a defined structure and validation contract.

This is an important FastAPI feature because API input validation becomes closely connected to Python type declarations.

The JavaScript implementation performs equivalent validation manually. The C++ implementation extracts selected fields and validates them explicitly.

The three approaches demonstrate an important difference:

- FastAPI and Pydantic integrate validation into the framework's request-processing model.
- JavaScript can implement validation through functions or external validation libraries.
- C++ requires explicit implementation or a suitable framework/library for equivalent behavior.

## Type annotations and validation

FastAPI uses Python type annotations as part of its API definition.

Consider:

`def get_product(product_id: int):`

The annotation provides information about the expected data type.

The same principle applies to query parameters and request models.

Validation may include:

- type conversion
- required fields
- optional fields
- numeric ranges
- string length
- structured models
- nested models
- enumeration values
- custom validation rules

The distinction between type declaration and business validation is important.

A type annotation such as `int` answers a structural question: what kind of value is expected?

A business rule such as "the product ID must refer to an existing product" is application logic.

A rule such as "only the owner can update this product" is authorization logic.

These concerns should not be treated as interchangeable.

## HTTP errors and status codes

APIs communicate results using HTTP status codes.

Common examples include:

- `200 OK`
- `201 Created`
- `204 No Content`
- `400 Bad Request`
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `409 Conflict`
- `422 Unprocessable Content`
- `500 Internal Server Error`

The Python implementation uses `HTTPException` for a missing resource.

For example, an endpoint can raise an HTTP 404 error when the requested product does not exist.

The C++ case study defines an `HttpException` class containing both a status code and an error message. The request dispatcher catches this exception and creates a JSON error response.

The JavaScript implementation follows a similar model by attaching `statusCode` to an `Error` object.

The purpose of status codes is to communicate the category of the result to the client. Error response bodies can provide additional structured information.

## CRUD path operations

The Python implementation contains a small in-memory product service with operations corresponding to:

- create
- read
- update
- delete

The routes include:

`POST /store/products`

`GET /store/products/{product_id}`

`PUT /store/products/{product_id}`

`DELETE /store/products/{product_id}`

The example uses a Python dictionary as a simple store.

This is appropriate for an educational demonstration but is not a durable production database.

The C++ case study develops the same product domain more explicitly. Its `ProductRepository` manages storage, while `ProductService` contains application-level operations.

This separation allows routing code to remain focused on HTTP concerns.

## Response models

FastAPI supports response models that describe the expected output structure.

For example:

`@app.get("/products/{product_id}", response_model=ProductResponse)`

The `ProductResponse` model can define fields such as:

`id: int`

`name: str`

`price: float`

Response models provide a documented output contract and allow FastAPI and Pydantic to validate and serialize response data.

They are particularly useful when an internal database model contains fields that should not be exposed publicly.

The Python implementation demonstrates a `ProductResponse` model to make this distinction explicit.

## Dependency injection

FastAPI provides dependency injection through `Depends`.

A dependency can provide reusable functionality such as:

- authentication information
- database sessions
- configuration
- pagination parameters
- reusable validation
- authorization checks
- request-scoped services

A conceptual example is:

`def get_current_user():`

followed by:

`def profile(user = Depends(get_current_user)):`

FastAPI resolves the dependency before calling the path operation.

The Python implementation includes an application-context dependency.

Dependency injection is useful because common functionality does not have to be manually repeated inside every endpoint.

It also improves testability by making dependencies replaceable.

## APIRouter

A small API can place all routes directly on the application instance.

A larger API benefits from route grouping.

FastAPI provides `APIRouter`.

For example:

`router = APIRouter(prefix="/api/products", tags=["products"])`

Operations can then be registered on that router.

The application can include the router with:

`app.include_router(router)`

This creates a useful architectural boundary between the main application object and groups of related endpoints.

Typical groups might include:

- users
- authentication
- products
- orders
- payments
- administration

The Python implementation creates a product router with a prefix and tag.

## OpenAPI and automatic documentation

FastAPI automatically generates an OpenAPI schema from the registered application.

Common endpoints include:

`/openapi.json`

`/docs`

`/redoc`

The OpenAPI document describes the API in machine-readable form.

Information can include:

- paths
- methods
- parameters
- request bodies
- response models
- status codes
- validation rules
- tags
- metadata

The documentation interface makes it possible to inspect and test many API operations during development.

This is one of the important consequences of FastAPI's declaration-oriented design. Route decorators, Python annotations, and Pydantic models contain enough information for the framework to generate a significant portion of the API contract automatically.

## Route metadata

FastAPI allows metadata to be attached to operations.

The Python implementation demonstrates:

- `tags`
- `summary`
- `description`
- `response_description`

Metadata can improve generated documentation without changing the underlying business behavior.

For larger APIs, consistent naming and tagging make generated documentation easier to navigate.

## Route ordering and specificity

Consider these two routes:

`/users/me`

and:

`/users/{user_id}`

Both can potentially match `/users/me` in a simple routing model.

The static route represents a fixed resource while the dynamic route treats `me` as a parameter value.

Route definitions therefore need to be designed carefully.

The Python study script explains this distinction, and both the JavaScript and C++ implementations include routing demonstrations.

A good API avoids unnecessary ambiguity between static and parameterized paths.

## Synchronous path operations

A synchronous FastAPI endpoint can be declared with:

`def endpoint():`

FastAPI can execute synchronous endpoint functions within its supported execution model.

Synchronous code is often suitable when the implementation uses blocking operations and does not require an asynchronous programming model.

The key consideration is the behavior of the underlying operations rather than treating synchronous code as inherently inferior.

## Asynchronous path operations

An asynchronous endpoint can be declared with:

`async def endpoint():`

An asynchronous operation is useful when it performs non-blocking I/O through awaitable libraries.

The Python implementation contains an asynchronous endpoint.

The JavaScript implementation uses:

`async function`

and:

`await`

to demonstrate the analogous asynchronous programming model.

Async programming does not automatically make every computation faster. It is especially valuable for workloads involving many concurrent I/O operations.

CPU-heavy work requires different considerations.

A blocking operation inside an asynchronous execution path can reduce the advantages of the event-driven model.

## Python implementation

The Python script is the primary FastAPI implementation.

It covers:

- HTTP fundamentals
- application creation
- decorators
- route registration
- GET operations
- POST operations
- PUT operations
- DELETE operations
- path parameters
- query parameters
- request models
- response models
- validation
- HTTP exceptions
- dependency injection
- APIRouter
- metadata
- OpenAPI concepts
- asynchronous endpoints
- route inspection
- layered architecture
- testing
- security
- performance considerations

It also includes an educational mini-router.

The mini-router is intentionally simpler than FastAPI. Its purpose is to make route registration and path matching visible at the Python level.

The real FastAPI routes demonstrate the actual framework API.

The script is designed to remain useful even when FastAPI is not installed. Its conceptual simulations can still run, while the real FastAPI application becomes available after installing FastAPI.

## JavaScript implementation

The JavaScript file complements the Python implementation rather than attempting to reproduce FastAPI itself.

It demonstrates:

- HTTP request structure
- route registration
- handler functions
- decorator-style registration
- path parameter extraction
- query parameter parsing
- input validation
- asynchronous functions
- application objects
- request dispatch
- CRUD behavior
- HTTP errors
- a working Node.js HTTP server
- performance measurement
- security considerations

The `Router` class stores method, path, and handler information.

The `Application` class acts as a small application instance.

This provides a useful conceptual comparison with:

`app = FastAPI()`

The JavaScript server uses Node's built-in `http` module, avoiding an external framework.

The JavaScript route syntax uses `:userId` to represent a path parameter because that notation is common in JavaScript routing systems. FastAPI uses `{user_id}`.

## C++ case study

The C++ program models a product management API.

The simulated system provides:

- `GET /`
- `GET /health`
- `GET /products/{product_id}`
- `POST /products`
- `PUT /products/{product_id}`
- `DELETE /products/{product_id}`
- `GET /search`

The architecture is divided into several components.

### HttpRequest

`HttpRequest` represents incoming HTTP data.

It contains:

- HTTP method
- path
- query parameters
- headers
- body

This makes the boundary between the HTTP layer and application logic explicit.

### HttpResponse

`HttpResponse` represents:

- status code
- content type
- response body

This mirrors the information an API needs to return to a client.

### Product

`Product` represents the domain entity.

It contains:

- ID
- name
- price
- stock state

### ProductRepository

`ProductRepository` handles storage operations.

It supports:

- finding a product
- saving a product
- deleting a product
- generating an ID
- retrieving all products

The repository is deliberately independent of routing.

### ProductService

`ProductService` contains application-level operations.

It handles:

- retrieving products
- creating products
- replacing products
- deleting products

The service depends on the repository rather than directly implementing HTTP routing.

### Application

The `Application` class represents the central application instance.

It stores a collection of `Route` objects and provides:

`addRoute()`

and:

`dispatch()`

This models the fundamental relationship between an application object and its registered path operations.

### Route

A `Route` contains:

- HTTP method
- path template
- endpoint function
- route name

The endpoint is represented with `std::function`.

This allows different handler functions to be stored behind a common callable interface.

## C++ path matching

The C++ implementation uses path templates such as:

`/products/{product_id}`

The matching function compares the path segments.

A segment enclosed in braces is treated as a parameter.

For:

`/products/{product_id}`

and:

`/products/42`

the matcher extracts:

`product_id = "42"`

The value is then converted and validated by:

`parsePositiveInteger()`

The implementation intentionally keeps this routing mechanism small so that the algorithm is easy to inspect.

A production HTTP router would normally need additional features such as:

- more sophisticated path matching
- URL decoding
- route precedence
- middleware
- wildcard paths
- host-based routing
- HTTP protocol integration
- efficient route lookup

## Query parameter handling

The C++ search endpoint accepts query values through the request's `query` map.

For example:

`q=keyboard`

and:

`limit=5`

The program validates the limit and rejects values above the configured maximum.

The same conceptual operation appears in the Python and JavaScript implementations.

The Python version uses FastAPI's function-signature inspection and validation facilities.

The JavaScript version reads values from `URL.searchParams`.

The C++ version accesses the request map explicitly.

## Validation and error handling

Input validation is performed at several boundaries.

The C++ implementation validates:

- missing values
- empty names
- invalid integers
- invalid prices
- non-positive values
- excessive query limits
- nonexistent products

The Python implementation uses FastAPI and Pydantic for structural validation and explicit application checks.

The JavaScript implementation performs equivalent validation using ordinary functions and JavaScript exceptions.

A consistent API should distinguish malformed or invalid input from internal failures.

For example:

A nonexistent product can produce `404`.

An invalid numeric parameter can produce a validation-related `4xx` response.

An unexpected server failure should normally produce `500`.

The exact status-code contract should be documented by the API.

## Authentication and authorization

The Python study script distinguishes authentication from authorization.

Authentication establishes identity.

Authorization determines whether the identified caller has permission to perform an operation.

The C++ case study includes a small request-context model with an authorization header.

It recognizes:

`Bearer demo-token`

as a demonstration credential.

This is intentionally not a production authentication system.

A real application would require secure identity management, credential handling, token validation, expiration, revocation strategy where applicable, authorization rules, and protected transport.

The example exists to demonstrate where authentication and authorization can fit into request processing.

## Security considerations

FastAPI routes form an external input boundary.

Security practices should include:

- validating path parameters
- validating query parameters
- validating request bodies
- authenticating protected endpoints
- authorizing resource access
- avoiding excessive error disclosure
- using HTTPS
- protecting credentials and secrets
- applying appropriate rate limits
- restricting request sizes where necessary
- using parameterized database queries
- keeping dependencies and libraries maintained
- logging security events without logging sensitive credentials

Validation is not equivalent to authorization.

An integer ID may be structurally valid while still referring to a resource the caller is not allowed to access.

A well-designed endpoint checks both data validity and access permissions when appropriate.

## Performance considerations

A simple router that scans every route has approximately O(R) dispatch cost, where R is the number of registered routes.

The C++ program explicitly demonstrates this behavior.

Real frameworks use more sophisticated routing mechanisms and optimizations. Application performance is also influenced by many factors outside route matching.

Important sources of latency can include:

- network communication
- TLS
- request parsing
- validation
- JSON serialization
- database queries
- external API calls
- file access
- application-level algorithms
- middleware
- logging

For I/O-heavy APIs, database and external-service latency can dominate the total request time.

For CPU-heavy endpoints, computation and serialization may become more significant.

Asynchronous execution is useful when non-blocking I/O can be performed concurrently. It is not a universal solution for CPU-bound work.

## Layered architecture

A production-oriented FastAPI project can separate:

- application setup
- routers
- schemas
- services
- repositories
- dependencies
- models
- tests

A possible conceptual structure is:

`app/main.py`

`app/routers/products.py`

`app/schemas/products.py`

`app/services/products.py`

`app/repositories/products.py`

`app/dependencies/database.py`

`app/dependencies/auth.py`

`app/tests/test_products.py`

The exact structure should match application complexity.

The key architectural principle is separation of concerns.

An endpoint should not become the entire application.

A route should primarily connect an HTTP request to appropriate application behavior.

## Path operation design

A good path operation should have a clear contract.

For example:

`GET /products/{product_id}`

communicates that the operation retrieves a product identified by its ID.

The implementation should then:

- validate the ID
- locate the resource
- enforce authorization if necessary
- return an appropriate response
- return a suitable error if the resource does not exist

The endpoint should avoid accumulating unrelated responsibilities.

Business rules can be placed in a service layer.

Database access can be placed in a repository or data-access layer.

Reusable request behavior can be provided through dependencies.

## Common mistakes

### Confusing a route with an endpoint function

A route is the HTTP method and path mapping.

The endpoint is the callable that processes the matched request.

They work together but are not the same concept.

### Forgetting path parameter alignment

If the route is:

`/users/{user_id}`

the function should expose a corresponding `user_id` parameter.

A mismatch can prevent the framework from correctly connecting the URL parameter to the function.

### Treating every input as trusted

HTTP clients can send unexpected values.

Path, query, header, and body data should be validated.

### Blocking asynchronous operations

An `async` endpoint does not make a blocking database or network call non-blocking.

The libraries used inside an asynchronous path must support the intended execution model.

### Putting all business logic inside endpoints

Large endpoints become difficult to test and maintain.

Service and repository layers can reduce this coupling.

### Returning inappropriate status codes

An endpoint should communicate whether an operation succeeded, failed because of client input, failed because a resource was absent, or failed because of an unexpected server condition.

### Using an in-memory dictionary as production storage

The educational Python implementation uses an in-memory dictionary.

This is useful for learning but has no durable persistence and is unsuitable for a production data store.

## Important distinctions

| Concept | Meaning |
|---|---|
| Application instance | The central FastAPI application object |
| Route | A mapping involving an HTTP method and path |
| Path operation | HTTP method + path + endpoint callable |
| Path parameter | Variable embedded in the URL path |
| Query parameter | Parameter supplied in the URL query string |
| Request body | Structured data sent with a request |
| Response model | Declared structure for returned data |
| Dependency | Reusable functionality resolved for an operation |
| Router | Component for organizing related routes |
| ASGI server | Server environment that communicates with the ASGI application |
| OpenAPI | Machine-readable description of the API |
| Authentication | Establishing caller identity |
| Authorization | Determining caller permissions |

## Python, JavaScript, and C++ comparison

### Python

Python is the most direct language for this topic because FastAPI itself is a Python framework.

The Python implementation demonstrates actual FastAPI constructs, including:

- `FastAPI()`
- `@app.get()`
- `@app.post()`
- `@app.put()`
- `@app.delete()`
- `BaseModel`
- `HTTPException`
- `Depends`
- `APIRouter`
- `Query`
- `Path`
- response models
- asynchronous endpoints

Python's type annotations integrate closely with FastAPI's validation and documentation mechanisms.

### JavaScript

JavaScript is useful for understanding the broader web-programming concepts around FastAPI.

The implementation demonstrates:

- HTTP handlers
- route registration
- URL parsing
- path parameters
- query parameters
- JSON bodies
- asynchronous functions
- application objects
- dispatch
- HTTP status handling

The JavaScript example uses Node's built-in HTTP server so that the request-processing path can be observed without relying on a third-party framework.

### C++

C++ exposes architectural details more explicitly.

The case study separates:

- HTTP request representation
- response representation
- route definitions
- application instance
- path matching
- validation
- authentication context
- service layer
- repository layer

This makes it useful for studying how an API framework abstracts routing and request processing.

## Production considerations

A production FastAPI application normally needs more than a collection of endpoint functions.

Relevant concerns include:

- persistent database integration
- connection pooling
- authentication
- authorization
- structured logging
- configuration management
- secret management
- error handling
- request validation
- response validation
- testing
- observability
- health checks
- deployment configuration
- dependency management
- API versioning where appropriate
- rate limiting where required
- security headers and transport security
- monitoring

The correct architecture depends on application size and requirements.

A small internal API may need only a few routers and services.

A large public API may require several architectural boundaries and operational controls.

## Testing

The Python script contains basic assertions for route matching and validation.

The JavaScript file includes tests for:

- path parameter extraction
- route mismatch
- integer validation
- invalid input handling

The C++ program executes multiple HTTP request scenarios, including:

- successful GET requests
- missing resources
- malformed path parameters
- successful creation
- invalid creation
- updates
- deletion
- missing routes
- query parameters

Important API tests should cover both valid and invalid requests.

A route that only works for the happy path is not adequately tested.

## Real-world relevance

FastAPI's application, route, decorator, and path-operation model is directly relevant to API development.

A real API might expose operations such as:

`GET /customers/{customer_id}`

`POST /orders`

`GET /orders/{order_id}`

`PATCH /orders/{order_id}`

`DELETE /sessions/{session_id}`

The same architectural pattern applies across domains such as:

- financial services
- e-commerce
- education
- analytics
- enterprise software
- data platforms
- machine-learning services
- internal business systems
- automation systems

The specific business logic changes, but the fundamental request-to-route-to-operation relationship remains central.

## Key implementation relationships

The most important relationships demonstrated by the three files are:

`FastAPI()` → application instance

`@app.get()` → route registration

`"/products/{product_id}"` → path template

`product_id: int` → typed path parameter

`Query(...)` → validated query parameter

`BaseModel` → structured request or response model

`Depends(...)` → dependency injection

`APIRouter` → route organization

`HTTPException` → HTTP-aware error handling

`async def` → asynchronous path operation

`/docs` and `/openapi.json` → generated API documentation and contract

The JavaScript and C++ implementations reproduce the underlying ideas manually so the abstractions provided by FastAPI become easier to understand.

## Limitations of the demonstrations

The educational router implementations are intentionally smaller than FastAPI.

They do not reproduce the complete behavior of:

- Starlette routing
- ASGI
- Pydantic
- OpenAPI generation
- dependency graphs
- middleware
- exception handlers
- content negotiation
- advanced route matching
- production HTTP protocol handling

The C++ JSON parsing logic is deliberately limited and should not be treated as a general-purpose JSON parser.

The in-memory repositories are demonstrations rather than durable persistence systems.

The authentication example is a conceptual demonstration and is not suitable as a production security mechanism.

These limitations are intentional because the purpose is to expose the core architecture rather than reproduce an entire production framework from scratch.
