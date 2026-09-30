# REST API Design: Resource Naming, Nesting, CRUD Conventions, Status Codes, and Response Structures

## Scope

This project studies REST API design through five tightly connected concerns:

- resource naming
- resource nesting
- CRUD conventions expressed through HTTP methods
- HTTP status-code semantics
- consistent response structures

The three implementations model the same broad domain, but they use different technical approaches. The Python program implements a complete in-memory REST service with explicit routing and resource operations. The JavaScript program emphasizes asynchronous request handling, URL parsing, event-driven observability, and collection query processing. The C++ program presents a resource-governance case study with explicit HTTP types, repository boundaries, authorization, routing, validation, and response construction.

The central design principle is that a URI identifies a resource, while the HTTP method supplies the operation semantics.

For example:

`GET /users/42`

addresses user 42 and requests its representation.

`PATCH /users/42`

addresses the same resource but requests a partial modification.

`DELETE /users/42`

addresses the same resource but requests its removal.

The path does not need to become `/getUser`, `/updateUser`, or `/deleteUser`. Those operation names belong in HTTP semantics rather than in the resource identifier.

---

## Resource Naming

REST resource paths should describe domain resources rather than application functions.

A resource-oriented design in this project uses paths such as:

- `/users`
- `/users/{user_id}`
- `/projects/{project_id}`
- `/tasks/{task_id}`
- `/users/{user_id}/projects`
- `/projects/{project_id}/tasks`

The nouns represent collections or individual resources. The identifier distinguishes one member of a collection.

The Python router explicitly maps `/users`, `/users/{id}`, `/projects/{id}`, and `/tasks/{id}` to different resource operations. Its audit function also detects paths containing common verb-like segments such as `/users/create`, illustrating why paths such as `/users/create` are less appropriate than `POST /users`.

The JavaScript implementation uses a `Route` class whose patterns contain resource-oriented path components such as `:userId` and `:orderId`. JavaScript's `URL` class is used to separate the path from query parameters.

The C++ router performs the same conceptual separation using path segments. It converts identifiers to typed integers before invoking resource controllers, preventing an arbitrary string from being silently treated as a valid numeric resource identifier.

### Collections and members

A collection endpoint represents a set of resources:

`GET /users`

A member endpoint represents one resource:

`GET /users/17`

The distinction matters because the expected response shape and operation differ. A collection normally returns an array or collection representation, while a member returns one resource representation.

Creating a member normally targets the collection:

`POST /users`

The server determines the new identifier and returns the created representation.

Retrieving an existing member targets that member:

`GET /users/17`

This separation prevents clients from constructing function-oriented URLs for ordinary CRUD operations.

---

## Resource Nesting

Nesting expresses a meaningful relationship between resources.

The project-management model contains these relationships:

`/users/{user_id}/projects`

means projects associated with a particular user.

`/projects/{project_id}/tasks`

means tasks associated with a particular project.

The parent segment provides context rather than merely increasing URI depth.

### When nesting is useful

A nested collection is particularly useful when the parent relationship is important to the operation.

For example:

`GET /users/1/projects`

asks specifically for projects belonging to user 1.

The Python implementation verifies that the parent user exists before returning the project collection. The JavaScript implementation does the same for `/users/:userId/orders`. The C++ controller validates the parent resource before constructing the nested collection response.

This prevents a nested lookup from silently behaving as though the parent did not matter.

### Direct resource addressing

The implementations also provide direct resource paths:

`GET /projects/101`

and:

`GET /tasks/1001`

Once a child resource has its own stable identifier, clients do not necessarily need to carry the complete ancestry in every request.

This produces a useful distinction:

`/users/1/projects` is a relationship-oriented collection.

`/projects/101` is an independently addressable project resource.

`/projects/101/tasks` is a relationship-oriented task collection.

`/tasks/1001` is an independently addressable task resource.

This avoids excessively deep paths such as:

`/users/1/projects/101/tasks/1001`

when the task can already be uniquely identified by `1001`.

### Nesting trade-offs

Nesting can make relationships explicit, but excessive nesting creates practical costs:

- Every request carries more ancestor identifiers.
- Routers become more complicated.
- Authorization checks may need to validate several resources.
- Clients need to know the complete parent hierarchy.
- Moving a resource to a different parent can make deeply nested URLs unstable.

The implementations therefore use nesting mainly for collection relationships and direct resource paths for independently addressable resources.

---

## CRUD Conventions and HTTP Methods

CRUD describes application-level operations:

| CRUD operation | Common HTTP method | Typical target |
|---|---|---|
| Create | POST | Collection |
| Read | GET | Collection or member |
| Replace | PUT | Member |
| Partially modify | PATCH | Member |
| Delete | DELETE | Member |

These mappings are conventions based on HTTP semantics rather than arbitrary controller naming.

### GET

`GET` retrieves a representation.

Examples:

`GET /users`

`GET /users/1`

`GET /projects/101/tasks`

A GET request should not be designed to mutate server state. This property also makes GET suitable for caching and safe retrieval.

The Python implementation's GET operations only read repository state. The JavaScript implementation returns asynchronously retrieved representations. The C++ router directs GET requests to retrieval methods.

### POST

`POST` is used for creating a subordinate resource when the server controls resource creation semantics.

Example:

`POST /users`

with a representation containing a name and email.

The server assigns an identifier and returns `201 Created`.

For a nested collection:

`POST /projects/101/tasks`

creates a task belonging to project 101.

The Python and C++ implementations return a `Location` header pointing to the new resource. This gives the client a canonical URI for subsequent requests.

### PUT

PUT is appropriate when the client supplies a complete replacement representation for an addressed resource.

For example:

`PUT /projects/101`

can mean that the supplied representation becomes the complete representation of project 101.

The Python implementation distinguishes PUT from PATCH. Its PUT path invokes the update operation with `partial=False`, which means fields omitted from a replacement representation can be treated differently from fields omitted from a partial update.

PUT is also defined with idempotent semantics. Repeating the same valid replacement request should leave the resource in the same intended state.

### PATCH

PATCH represents partial modification.

The Python task service accepts:

`PATCH /tasks/1001`

with only:

`{"status": "in_progress"}`

The title remains unchanged.

The C++ implementation follows the same principle. It only changes the fields that appear in the request representation.

PATCH is therefore different from PUT. A partial document should not automatically be interpreted as a complete replacement.

### DELETE

DELETE targets an existing resource for removal.

A successful deletion with no representation body can return:

`204 No Content`

The Python task deletion and C++ task deletion both use this form.

A DELETE request can still fail because of current resource state. The C++ project case demonstrates this with a project that still has dependent tasks.

Deleting the project would violate the modeled dependency rule, so the service returns `409 Conflict` rather than silently deleting the parent.

---

## Idempotency and Method Selection

Idempotency concerns whether repeating an equivalent request has the same intended effect as performing it once.

GET is safe and idempotent in normal REST semantics.

PUT is idempotent when implemented as a complete replacement.

DELETE is generally modeled as idempotent because repeated deletion attempts do not create additional deletion effects, although the response to a subsequent request may differ if the resource no longer exists.

POST is normally not idempotent. Repeating:

`POST /orders`

may create multiple orders.

This distinction matters for retries. A client, proxy, or infrastructure layer may retry a request after a network failure without knowing whether the server processed the original request.

The Python implementation explicitly contrasts replacement-style PUT behavior with creation-oriented POST behavior. In production systems, APIs that need safe retry behavior for creation commonly introduce an application-level idempotency mechanism, such as an idempotency key, with carefully defined persistence and replay semantics.

---

## Query Parameters and Collection Retrieval

Query parameters are appropriate when the client is modifying how a collection is retrieved rather than identifying a different resource hierarchy.

Examples include:

`GET /projects?owner=atul@example.com`

`GET /projects?search=api`

`GET /projects?limit=20&offset=40`

The Python implementation contains a collection filtering function supporting owner filtering, textual search, limit, and offset.

The JavaScript implementation uses the standard `URL` class and extracts query parameters independently from the pathname. Its pagination validation enforces:

- a minimum limit of 1
- a maximum limit of 100
- a non-negative offset

This demonstrates an important distinction between resource identity and retrieval controls.

A query parameter such as `limit=20` does not create a new resource named `limit`. It changes how the collection representation is selected.

---

## HTTP Status Codes

Status codes communicate the broad outcome of a request. They should not be selected merely because a particular number is commonly seen in APIs.

### Successful responses

`200 OK` is appropriate when the operation succeeds and a representation is returned.

The implementations use 200 for resource retrieval and successful modifications that return the modified representation.

`201 Created` indicates that a new resource was successfully created.

The Python, JavaScript, and C++ implementations use 201 for creation operations and provide a `Location` header pointing to the newly created resource.

`204 No Content` indicates successful processing without a response representation.

The deletion operations use 204 when there is no useful response body.

`202 Accepted` can be appropriate when a request has been accepted for asynchronous processing but has not completed. It is different from 201 because acceptance does not mean the requested resource has already been created.

### Client-side request problems

`400 Bad Request` is suitable when the request itself cannot be processed as a valid request.

The C++ implementation uses 400 for malformed numeric resource identifiers such as:

`GET /users/not-a-number`

This differs from:

`GET /users/999`

where the identifier is structurally valid but the resource does not exist.

`401 Unauthorized` indicates that authentication is required or credentials are not acceptable for the protected operation.

The C++ project deletion case explicitly demonstrates missing authentication.

`403 Forbidden` represents an authenticated caller that is not permitted to perform the operation.

The C++ implementation demonstrates this by authenticating a user who does not own a particular project and returning 403 when that user attempts a protected modification.

`404 Not Found` represents an absent resource or route.

The implementations distinguish missing users, projects, tasks, and unknown routes.

`405 Method Not Allowed` means the resource route is known but the requested HTTP method is not supported there.

For example, the Python router rejects an unsupported PUT operation on `/users/1`, while the C++ router applies the same distinction.

`409 Conflict` represents a conflict between the requested operation and the current resource state.

The project deletion case is a concrete example. The project exists, the authenticated user has authority over it, but dependent tasks prevent deletion.

`415 Unsupported Media Type` indicates that the server does not support the request representation's media type.

The C++ case study checks for `application/json` on operations that consume JSON request bodies.

`422 Unprocessable Content` is useful for a syntactically processable representation whose semantic values fail validation.

Examples include:

- an empty required name
- an invalid email
- an unsupported task status
- an invalid positive amount

`429 Too Many Requests` is commonly used when rate limiting prevents a client from continuing at the current request rate. The example implementations document the status but do not implement a rate limiter because rate limiting is a transport and policy concern rather than a core CRUD mechanism.

### Server-side failures

`500 Internal Server Error` represents an unexpected server-side failure.

The JavaScript implementation catches unexpected handler exceptions and converts them into a generic 500 response instead of exposing internal exception details.

`503 Service Unavailable` is appropriate when a service is temporarily unable to handle requests, such as during controlled service unavailability or a dependency outage.

Neither 500 nor 503 should be used as a generic substitute for client validation errors.

---

## Response Structures

A predictable response structure reduces the amount of special-case logic required by clients.

The successful implementations generally use:

`{"data": ...}`

The Python implementation also places timestamp and message information under `meta`.

The JavaScript implementation adds a request identifier and, for collection responses, pagination metadata.

A collection can therefore conceptually look like:

`{"data":[...],"meta":{"pagination":{"limit":20,"offset":0,"total":125}}}`

This separates the collection itself from information describing the retrieval operation.

### Error structure

The implementations use an error object with a machine-readable code and human-readable message.

A validation error can contain field-specific details:

`{"error":{"code":"VALIDATION_FAILED","message":"...","details":[...]}}`

This distinction is important because clients should not have to parse human-readable sentences to determine why a request failed.

A code such as `USER_NOT_FOUND` is more stable for client logic than matching the text of an error message.

### Location on creation

Creation responses in the Python and C++ implementations use the `Location` header.

For example:

`Location: /users/3`

This communicates the canonical URI of the newly created resource without forcing the client to infer it from an identifier.

### Empty responses

A 204 response intentionally has no response representation.

The Python and C++ implementations therefore return an empty body for successful DELETE operations.

Clients should not assume that every successful operation returns JSON.

---

## Python Implementation

The Python program is a complete in-memory REST API simulation.

Its domain contains:

- `User`
- `Project`
- `Task`

The `Repository` class separates persistence-like operations from HTTP behavior. Although it uses dictionaries instead of a database, the boundary mirrors the architecture of a real service where controllers should not directly contain SQL or persistence details.

`RestApiService` implements resource behavior. It provides operations for:

- listing and creating users
- retrieving users
- listing projects for a user
- creating projects beneath a user
- retrieving, replacing, and partially updating projects
- deleting projects
- listing tasks for a project
- creating tasks
- retrieving tasks
- partially updating tasks
- deleting tasks

The `Router` maps HTTP methods and URI patterns to those operations.

This is particularly important for understanding the relationship between URI and method. `/projects/101` remains the resource address while GET, PUT, PATCH, and DELETE select different operations on that address.

### Python validation

The Python program validates:

- required fields
- string types
- empty names
- email structure
- task status values
- duplicate email conflicts
- parent resource existence

The validation result uses 422 when the request structure can be processed but its values violate domain rules.

The duplicate email case returns 409 because the request conflicts with an already existing resource state rather than merely failing a field-format check.

### Python dependency conflict

A project cannot be deleted while tasks still belong to it.

The program detects dependent task identifiers before deletion and returns 409.

This demonstrates why status-code selection should reflect the reason an operation cannot proceed.

---

## JavaScript Implementation

The JavaScript program takes a different architectural approach.

It uses Node.js standard-library capabilities:

- `URL` for request URL parsing
- `Map` for in-memory resource storage
- `EventEmitter` for lifecycle events
- `crypto.randomUUID()` for request identifiers
- `async` and `await` for asynchronous service behavior

The `ResourceStore` represents persistence. The service layer performs resource operations, while the route class handles method and URI matching.

### URL parsing

A `RequestContext` separates:

- HTTP method
- pathname
- query parameters
- request body
- request identifier

This makes it possible to handle:

`GET /users?name=atul&limit=10&offset=0`

without treating `name`, `limit`, and `offset` as part of the resource path.

### Asynchronous resource handling

The service methods are asynchronous even though the underlying store is in memory.

This models the execution shape of real Node.js applications where handlers commonly await:

- database queries
- cache operations
- remote services
- file operations
- authentication providers

The REST semantics do not change merely because the implementation is asynchronous.

### Event-driven observability

The JavaScript service emits:

- `request.received`
- `request.completed`
- `request.failed`

These events provide an observability boundary without embedding logging statements into every domain operation.

The generated request identifier is also propagated into response metadata, giving operators and clients a common correlation value.

---

## C++ Case Study

The C++ program models a project-management API as a resource-governance system.

Its architecture is divided into:

`HttpRequest`

represents the incoming HTTP request.

`HttpResponse`

represents status, headers, and body.

`Repository`

owns domain state and provides lookup, creation, filtering, and deletion operations.

`ProjectApi`

implements resource behavior and validation.

`AuthorizationService`

determines whether an authenticated user can modify a project.

`ApiRouter`

matches HTTP methods and path structures before invoking the appropriate controller operation.

`ResponseFactory`

centralizes response construction.

This separation keeps HTTP routing, persistence-like operations, authorization, and response formatting from collapsing into one large function.

### C++ resource model

The case study uses:

- users
- projects
- tasks

A project belongs to a user through `ownerId`.

A task belongs to a project through `projectId`.

The router exposes both nested relationship paths and direct resource paths.

Examples include:

`/users/1/projects`

`/projects/101`

`/projects/101/tasks`

`/tasks/1001`

### C++ authorization boundary

Authorization is deliberately separate from routing.

The C++ implementation checks whether the authenticated user's identifier matches the project's owner identifier before permitting a project deletion.

This produces three distinct states:

- no authenticated user: 401
- authenticated user without permission: 403
- authenticated user with permission but blocked by dependent state: 409

These are materially different conditions and should not be collapsed into a generic failure.

### C++ dependency handling

The project resource cannot be deleted while tasks reference it.

The repository exposes `projectHasTasks()` to check the current state before deletion.

This illustrates a common API design issue: a valid resource operation can still be rejected because the requested transition conflicts with related state.

---

## Validation Boundaries

Validation should occur at multiple levels.

### URI validation

The router verifies that identifiers have the expected structure.

For numeric identifiers, the C++ implementation rejects non-numeric values before performing repository lookup.

This distinguishes:

`/users/not-a-number`

from:

`/users/999`

The first contains an invalid identifier representation. The second contains a valid identifier for a resource that does not exist.

### Representation validation

Request bodies are checked for required and semantically valid fields.

Examples:

- user names cannot be empty
- email values must have a valid basic structure
- task status must be from the supported state set
- monetary totals must be positive in the JavaScript order example

### Relationship validation

Nested endpoints verify that the parent resource exists.

A request to:

`POST /users/999/projects`

should not create a project that references a nonexistent parent.

The implementations therefore perform parent lookup before creation.

### State validation

Some operations depend on current state.

The project deletion example is state validation rather than representation validation because the project itself may be perfectly valid while deletion is currently blocked by dependent tasks.

---

## Common Design Mistakes

### Verbs in resource paths

Paths such as:

`/getUsers`

`/createUser`

`/deleteProject`

mix operation names with resource identity.

A resource-oriented design instead uses:

`GET /users`

`POST /users`

`DELETE /projects/{id}`

The HTTP method already expresses the intended operation.

### Inconsistent singular and plural conventions

Using `/user/1` for one resource and `/users` for the collection is not inherently impossible, but inconsistent naming increases client complexity.

The implementations use plural collection nouns consistently:

`/users`

`/projects`

`/tasks`

with member identifiers appended to those collections.

### Returning 200 for every outcome

A service that returns HTTP 200 for validation failures, missing resources, and conflicts forces clients to inspect application-specific fields before determining whether the request succeeded.

The examples use status codes to communicate the broad outcome at the HTTP layer and structured error codes to communicate application-level details.

### Confusing 401 and 403

401 concerns authentication.

403 concerns authorization after the caller is authenticated.

The C++ implementation keeps these decisions separate.

### Confusing 404 and 422

A missing resource is not the same as an invalid representation.

`GET /users/999` can produce 404.

`POST /users` with an invalid email can produce 422.

### Overusing nested resources

A deeply nested URL can expose relationships but become difficult to maintain.

The project-management model therefore uses nested collection endpoints for contextual retrieval while allowing direct task and project addressing.

### Treating PUT as PATCH

A request to PUT a resource should be designed around replacement semantics.

A request to PATCH a resource should describe a partial change.

Treating them as interchangeable makes retry behavior and client expectations ambiguous.

### Leaking internal exceptions

The JavaScript implementation catches unexpected handler failures and returns a generic server error rather than exposing internal exception details.

Production APIs should log diagnostic information internally while keeping externally visible error messages controlled.

---

## Security Considerations

REST resource design does not replace authentication or authorization.

An endpoint can have a perfectly designed URI while still exposing unauthorized data.

The C++ case study therefore places authorization between resource identification and mutation.

Security-sensitive APIs should also consider:

- TLS for protecting credentials and data in transit
- strict request-size limits
- schema validation
- authentication token validation
- authorization at the resource level
- protection against object-level authorization failures
- rate limiting
- audit logging
- controlled error messages
- input normalization
- safe handling of identifiers
- prevention of accidental mass assignment

The response structure should not expose database exceptions, stack traces, credentials, internal tokens, or other implementation details.

The C++ program intentionally uses a very small regular-expression-based payload parser only to keep the case study self-contained. A production C++ JSON API should use a standards-compliant JSON implementation with appropriate limits and validation.

---

## Performance Considerations

Resource-oriented design does not automatically determine performance.

The Python and JavaScript examples use in-memory collections, while the C++ repository uses hash maps for efficient average-case item lookup.

Collection operations have different characteristics. Searching an entire collection for a filter may be linear in the number of resources unless the persistence layer has a suitable index.

For example:

`GET /projects?owner=...`

can become expensive if the database must scan every project.

A production database would normally index fields used frequently for filtering, joins, sorting, or authorization checks.

Pagination also prevents a collection endpoint from attempting to return an unbounded number of resources.

The JavaScript implementation limits `limit` to 100. This is both a performance control and a resource-exhaustion safeguard.

Response size can also be affected by representation design. Returning every related object recursively can produce large payloads and circular relationship problems. The examples return explicit resource representations instead of automatically embedding entire resource graphs.

---

## Debugging and Observability

REST failures are easier to diagnose when the system preserves the distinction between:

- route matching
- identifier parsing
- authentication
- authorization
- representation validation
- business-state validation
- persistence failure
- unexpected server failure

The JavaScript implementation demonstrates request correlation through `requestId`.

A production API can propagate a similar identifier through:

`client -> gateway -> API service -> database/remote dependency`

This allows operators to associate a client-visible failure with internal logs without exposing sensitive diagnostic information in the response.

The C++ implementation also prints the HTTP method, path, status, headers, and body for each case, making the mapping from request to response explicit.

---

## Production Design Considerations

A production REST API normally separates transport, routing, application logic, persistence, and policy concerns.

A typical conceptual flow is:

`HTTP request`
→ `TLS / network layer`
→ `authentication`
→ `routing`
→ `input validation`
→ `authorization`
→ `application service`
→ `repository`
→ `database or external service`
→ `resource representation`
→ `HTTP response`

Resource naming belongs primarily to the routing and API-contract layer, while CRUD semantics belong to the HTTP interface and application behavior.

Status codes form a contract between the service and its clients.

Response structures form another contract. Changes to them should therefore be treated as compatibility-sensitive API changes.

Versioning strategy, pagination behavior, filtering rules, authentication mechanisms, rate limits, and error schemas should be explicitly documented when they become part of the public API contract.

---

## Technical Relationships

The concepts in this project should be understood as separate layers rather than interchangeable terminology.

**Resource naming** answers: what resource does this URI identify?

**Nesting** answers: what relationship or parent context does the URI express?

**CRUD conventions** answer: what operation does the HTTP method request against that resource?

**Status codes** answer: what was the broad outcome of processing the request?

**Response structures** answer: how is the resulting representation or failure information communicated to the client?

A well-designed endpoint combines these layers.

For example:

`POST /users/1/projects`

can be interpreted as:

- `users` identifies the user collection
- `1` identifies the parent user
- `projects` identifies the subordinate project collection
- `POST` requests creation
- `201 Created` communicates successful creation
- `Location` identifies the newly created project
- `data` contains the resulting project representation
- `meta` can contain request or pagination information where appropriate

That relationship is the central design pattern demonstrated across all three implementations.
