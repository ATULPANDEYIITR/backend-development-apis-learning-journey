# API Versioning: URL Versioning, Header Versioning, Backward Compatibility, and Deprecation Strategy

## 1. Topic Introduction

API versioning is the controlled evolution of an API contract while managing the effect of changes on existing consumers.

An API is a contract between a provider and its consumers. The contract includes much more than endpoint URLs. It can include:

- HTTP methods
- URL structure
- request parameters
- request body fields
- response fields
- data types
- status codes
- error formats
- authentication behavior
- authorization rules
- pagination semantics
- filtering behavior
- sorting rules
- rate-limit behavior
- caching behavior
- documented side effects

A change is significant when an existing consumer that previously followed the documented contract can no longer interact with the newer implementation correctly.

API versioning provides an explicit compatibility boundary.

The implementations in this topic use a user-management API as the central example. The internal user model contains a stable set of properties, while V1, V2, and V3 expose different public representations.

The three implementations deliberately use different strengths:

- Python provides a broad educational implementation containing parsing, routing, adapters, lifecycle modeling, telemetry, testing, and governance.
- JavaScript demonstrates version-aware application behavior, asynchronous processing, event-driven telemetry, Maps, objects, and request middleware.
- C++ develops a more structured industry-style case study using classes, strong data structures, exceptions, a service layer, a version registry, controllers, validation, and explicit lifecycle management.

---

## 2. Fundamental Terminology

### API Provider

The server or service exposing the API.

### API Consumer

An application, service, mobile application, browser application, partner integration, or other client that calls the API.

### API Contract

The externally observable behavior that a consumer depends upon.

For example, if V1 promises:

- `id`
- `name`
- `email`
- `active`

then removing `name` is a contract change even if the underlying database remains unchanged.

### API Version

A named compatibility boundary such as `v1`, `v2`, or `v3`.

### Breaking Change

A change that can cause a previously valid client to fail or behave incorrectly.

Examples include:

- renaming a required response field
- removing a response field that consumers require
- changing the type of an existing field incompatibly
- changing the meaning of an existing field
- making an optional request property mandatory
- removing an endpoint
- changing documented semantics in an incompatible way

### Non-Breaking Change

A change that can normally be introduced without requiring existing consumers to change.

Typical examples include:

- adding a new endpoint
- adding an optional request property
- adding a response field when clients tolerate unknown fields
- improving internal implementation without changing the contract

Compatibility depends on the actual contract and client behavior. An apparently harmless change can become breaking if clients rely on behavior that was not properly documented or if their parsers are not tolerant of additional fields.

---

## 3. Why API Versioning Is Needed

Consider an original API response:

`{"id":101,"name":"Atul Pandey","email":"atul@example.com","active":true}`

A newer design may want to expose:

`{"id":101,"first_name":"Atul","last_name":"Pandey","email":"atul@example.com","phone":"+91-9000000000","is_active":true}`

The second representation is structurally different.

A client written for V1 expects `name` and `active`. A client written for V2 expects `first_name`, `last_name`, and `is_active`.

Replacing V1 with V2 without a compatibility strategy can break existing consumers.

Versioning makes the distinction explicit:

`/api/v1/users`

and:

`/api/v2/users`

The server can then select a representation appropriate to the requested contract.

---

## 4. Core API Versioning Strategies

There are several common mechanisms.

### 4.1 URL Versioning

The version appears in the URL:

`/api/v1/users`

`/api/v2/users`

`/api/v3/users`

#### Advantages

- Highly visible
- Easy to understand
- Easy to route
- Easy to test manually
- Easy to distinguish in logs
- URLs themselves identify the contract

#### Trade-offs

- The version becomes part of the URL
- Multiple URLs represent different versions of what may conceptually be the same resource
- Documentation and routing must account for multiple paths

The Python, JavaScript, and C++ implementations all demonstrate URL parsing.

---

### 4.2 Custom Header Versioning

The version can be sent in a request header:

`API-Version: 2`

The URL can remain:

`/api/users`

The server determines the contract from the header.

#### Advantages

- URLs remain stable
- Version selection is separated from the resource path
- Routing can remain resource-oriented

#### Trade-offs

- The version is less visible
- Developers may overlook the header
- Caches must account for the version header
- Infrastructure must preserve the header correctly

The Python, JavaScript, and C++ implementations demonstrate custom header selection.

---

### 4.3 Media-Type Versioning

A client can request a representation using the `Accept` header:

`Accept: application/vnd.example.user+json;version=2`

This approach treats the version as part of representation negotiation.

The Python implementation includes a parser for this form and demonstrates simplified content negotiation.

A real implementation must account for HTTP content-negotiation details such as:

- multiple media types
- parameters
- wildcards
- quality values
- default behavior
- unsupported representations

The example intentionally uses a simplified parser rather than pretending to implement the entire HTTP specification.

---

## 5. Comparing Versioning Mechanisms

| Mechanism | Example | Main Characteristic | Important Consideration |
|---|---|---|---|
| URL | `/api/v2/users` | Explicit and visible | Version becomes part of the URL |
| Custom header | `API-Version: 2` | Stable URL | Cache must consider the header |
| Media type | `Accept: application/vnd.example.user+json;version=2` | Representation negotiation | More complex parsing and infrastructure |

There is no universal versioning mechanism that fits every API.

The important engineering questions are:

- How will clients request a version?
- How will gateways route it?
- How will caches distinguish representations?
- How will documentation expose it?
- How will monitoring identify it?
- How will incompatible versions be retired?

---

## 6. Python Implementation

The Python implementation is the broadest educational implementation.

### 6.1 Version Model

`ApiVersion` represents a major API version.

The class validates that versions are positive and provides a readable representation such as `v1`.

This prevents invalid values from silently becoming routing decisions.

### 6.2 URL Parsing

`parse_url_version()` recognizes paths such as:

`/api/v1/users`

and returns both the version and resource.

It rejects malformed paths such as:

`/api/users`

This is important because routing should not silently infer a version when the contract requires explicit versioning.

### 6.3 Header Parsing

`parse_version_header()` reads:

`API-Version: 2`

and validates that the value represents a positive integer.

### 6.4 Media-Type Parsing

`parse_accept_version()` extracts the version from a vendor-specific media type.

This demonstrates how version negotiation can be placed inside the `Accept` header.

### 6.5 Versioned Serializers

The Python file implements:

- `serialize_user_v1()`
- `serialize_user_v2()`
- `serialize_user_v3()`

All three use the same internal `User` object.

This is an important architectural distinction.

The internal model does not need to become identical to every public API contract.

Instead:

`Internal Model -> Version-Specific Representation`

This is commonly preferable to storing public API version concepts throughout domain logic.

---

## 7. Version-Specific Representations

### V1

V1 returns:

- `id`
- `name`
- `email`
- `active`

### V2

V2 returns:

- `id`
- `first_name`
- `last_name`
- `email`
- `phone`
- `is_active`

### V3

V3 nests related information:

- `identity`
- `contact`
- `status`
- `createdAt`

This demonstrates that API versions can change structure rather than merely changing a version number.

---

## 8. Breaking Change Analysis

The Python implementation explicitly classifies examples.

### Usually Non-Breaking

Adding an optional response field can be compatible when consumers correctly ignore unknown fields.

Adding a new endpoint does not affect clients using existing endpoints.

Adding an optional request field can be compatible when existing requests remain valid.

### Potentially Breaking

Renaming:

`name`

to:

`full_name`

is breaking for a consumer that reads `name`.

Changing:

`active: true`

into:

`status: "active"`

can also be breaking because the representation and type have changed.

Changing an optional request field into a mandatory field means old requests may no longer satisfy the contract.

Removing an endpoint is a direct contract change.

---

## 9. Backward Compatibility

Backward compatibility means a newer server or system can continue to correctly support an older contract.

For example:

V1 client -> V1 contract -> newer server

can remain supported while:

V2 client -> V2 contract -> newer server

uses the newer representation.

A common mistake is assuming that a newer representation automatically remains compatible with an older client.

It does not.

Compatibility must be evaluated against actual contract expectations.

---

## 10. The Tolerant Reader Principle

A tolerant client can often ignore unknown response fields.

Suppose V1 returns:

`{"id":101,"name":"Atul Pandey","email":"atul@example.com","active":true}`

A newer compatible representation might add:

`"phone":"+91-9000000000"`

A client that only reads the fields it needs may continue working.

This is one reason adding optional response fields is often less disruptive than renaming or removing fields.

Client behavior still matters. A client that rejects unknown properties may not tolerate such an addition.

---

## 11. Compatibility Adapters

A strong architectural pattern is to translate each public version into a canonical internal representation.

The Python implementation uses:

`adapt_v1_user_request_to_internal()`

and:

`adapt_v2_user_request_to_internal()`

The JavaScript implementation uses:

`adaptV1ToInternal()`

and:

`adaptV2ToInternal()`

The C++ implementation uses:

`adaptV1Request()`

and:

`adaptV2Request()`

The adapters transform different public contracts into a common internal structure:

- `firstName`
- `lastName`
- `email`

The domain service can then work with the canonical representation.

Conceptually:

`V1 Request -> V1 Adapter -> Canonical Model -> Domain Service`

and:

`V2 Request -> V2 Adapter -> Canonical Model -> Domain Service`

This prevents API version details from spreading throughout business logic.

---

## 12. Why Shared Domain Logic Matters

Suppose three API versions independently implement account creation.

Without a shared service, the system can become:

`V1 Business Logic`

`V2 Business Logic`

`V3 Business Logic`

Over time these implementations may behave differently.

A more maintainable design can be:

`V1 Adapter -> Shared Domain Service`

`V2 Adapter -> Shared Domain Service`

`V3 Adapter -> Shared Domain Service`

This does not mean every version should always share exactly the same implementation. When semantics genuinely differ, separate behavior may be required.

The key principle is to avoid duplicating business rules merely because public schemas differ.

---

## 13. Version Routing

The Python `VersionRouter` maps major versions to serializer functions.

Conceptually:

- V1 -> `serialize_user_v1`
- V2 -> `serialize_user_v2`
- V3 -> `serialize_user_v3`

An unsupported version raises `UnsupportedVersionError`.

This is preferable to silently falling back to an arbitrary implementation.

A production API should define the status code and error contract for unsupported versions.

---

## 14. Missing Version Behavior

An API must decide what happens when the client does not specify a version.

Possible policies include:

- require an explicit version
- use a documented default
- infer a version from another mechanism
- route to a compatibility version

The Python and JavaScript examples demonstrate an explicit default policy.

The C++ case study defaults to V2 when no version is provided.

A default should be deliberate and documented. Silent upgrades can cause unexpected representation changes for consumers.

---

## 15. Conflicting Version Signals

A request could theoretically contain both:

`/api/v1/users`

and:

`API-Version: 2`

The system must define which source takes precedence.

The implementations choose a conservative policy: reject the conflict.

This avoids silently selecting a version the caller may not have intended.

Other architectures may establish a formal precedence rule, but it must be consistent and documented.

---

## 16. Error Contracts

The implementations demonstrate machine-readable error codes such as:

`INVALID_REQUEST`

`UNSUPPORTED_API_VERSION`

`UNAUTHORIZED`

`NOT_FOUND`

Clients should generally use documented error codes rather than matching exact human-readable messages.

For example, this is fragile:

`if message == "The supplied request is invalid."`

A more stable strategy is:

`if error.code == "INVALID_REQUEST"`

Human-readable messages can then evolve without forcing clients to change.

---

## 17. Deprecation

Deprecation is different from immediate removal.

A deprecated API remains available while consumers are informed that they should migrate.

A typical lifecycle can be:

`Current -> Supported -> Deprecated -> Sunset`

The exact states and names can vary between organizations.

### Deprecation Should Communicate

A useful deprecation policy identifies:

- affected version
- deprecation date
- successor version
- migration documentation
- sunset date where applicable
- affected consumers
- migration expectations

The Python, JavaScript, and C++ implementations model this information explicitly.

---

## 18. Deprecation Headers

The examples generate headers such as:

`Deprecation: true`

and:

`Sunset: 2026-12-01T00:00:00Z`

They also demonstrate a `Link` header pointing toward migration information.

Headers alone are not a complete migration strategy.

They should be combined with appropriate API documentation, communication, telemetry, and organizational processes.

---

## 19. Sunset

Sunset represents the point at which an API version is scheduled to stop being served.

A sound retirement process should consider:

- actual traffic
- active consumers
- contractual commitments
- service-level agreements
- partner dependencies
- migration status
- security concerns
- operational readiness
- documentation status

A version should not be considered safe to retire merely because a newer version exists.

---

## 20. Consumer Telemetry

The Python and JavaScript implementations include usage tracking.

The C++ implementation contains `UsageTracker`.

Telemetry records information such as:

- client ID
- version
- endpoint or request
- status code

This enables questions such as:

- How much traffic still uses V1?
- Which clients still use V1?
- Are migration efforts reducing V1 traffic?
- Are deprecated versions generating unusual errors?
- Which clients need migration attention?

Version-level traffic alone may not be enough. Client-level information is often important when determining whether a version is still actively consumed.

---

## 21. Deprecation Strategy

A practical lifecycle can contain these stages.

### Stage 1: Design the Successor

Define the new contract and identify incompatible changes.

### Stage 2: Implement the New Version

Implement the new contract without accidentally changing the old contract.

### Stage 3: Test Compatibility

Verify that existing V1 behavior remains correct.

### Stage 4: Release the New Version

Make V2 available while V1 remains supported.

### Stage 5: Announce Deprecation

Clearly document:

- V1 status
- V2 availability
- migration differences
- timeline
- sunset date where applicable

### Stage 6: Measure Usage

Use telemetry to identify remaining V1 consumers.

### Stage 7: Assist Migration

Provide version-specific migration information and address remaining technical dependencies.

### Stage 8: Verify Retirement Conditions

Check usage and organizational obligations.

### Stage 9: Sunset

Disable V1 according to the published policy.

### Stage 10: Remove Retired Code

Remove routing, serializers, adapters, tests, and infrastructure that are no longer required.

---

## 22. JavaScript Implementation

The JavaScript implementation focuses on application-level behavior.

### Version Objects

`ApiVersion` represents a version and validates its value.

### Maps

The serializer registry uses a JavaScript `Map`:

`1 -> serializeUserV1`

`2 -> serializeUserV2`

`3 -> serializeUserV3`

This demonstrates a clean runtime dispatch structure.

### Object-Based Representations

JavaScript objects naturally model JSON-style API representations.

V1, V2, and V3 can therefore be demonstrated directly without external libraries.

### Async Behavior

`fetchUserFromRepository()` simulates asynchronous data access.

`getVersionedUser()` waits for the data and then applies the requested representation.

This is relevant because production APIs often involve asynchronous database, network, or service operations.

### Event-Driven Telemetry

`DeprecationEventEmitter` demonstrates how an application can emit an event when deprecated API usage occurs.

A production system could connect such events to a larger observability system.

---

## 23. JavaScript Middleware

The JavaScript file contains `versionMiddleware()`.

Its responsibilities include:

1. inspect the URL
2. inspect the API-Version header
3. detect conflicts
4. select a version
5. verify that the version is supported
6. attach the selected version to request-processing state

This resembles middleware found in server-side JavaScript applications.

The middleware should remain focused on version selection rather than business logic.

---

## 24. C++ Case Study

The C++ implementation models a more structured service architecture.

The central scenario is a user-management API with three public representations.

Major components include:

- `ApiVersion`
- `ApiRequest`
- `ApiResponse`
- `User`
- `UserV1Response`
- `UserV2Response`
- `UserV3Response`
- `UserRepresentationService`
- `VersionRegistry`
- `UsageTracker`
- `UserService`
- `UserApiController`

This separates responsibilities.

---

## 25. C++ Domain Model

The internal `User` contains:

- ID
- first name
- last name
- email
- phone
- active state
- creation timestamp

This model does not contain properties such as:

`name`

or:

`is_active`

because those are public representation decisions.

The representation service translates the internal model into the required public contract.

---

## 26. C++ V1 Representation

V1 exposes:

- `id`
- `name`
- `email`
- `active`

The internal first and last names are combined into a single public `name`.

This is a concrete example of backward compatibility through representation translation.

---

## 27. C++ V2 Representation

V2 exposes:

- `id`
- `first_name`
- `last_name`
- `email`
- `phone`
- `is_active`

The internal representation already has separate names, so V2 serialization is direct.

The field `active` is renamed to `is_active`.

This is precisely the kind of public contract change that can require versioning.

---

## 28. C++ V3 Representation

V3 nests data into:

`identity`

and:

`contact`

It also uses:

`status`

and:

`createdAt`

This demonstrates that an API version can represent a more significant schema evolution than a simple field rename.

---

## 29. C++ Version Registry

`VersionRegistry` stores lifecycle information for supported versions.

The case study registers:

- V1 as deprecated
- V2 as supported
- V3 as current

The registry provides a central place to determine whether a version can still be served.

This is more scalable than scattering version checks throughout unrelated controller code.

---

## 30. C++ Controller

`UserApiController` coordinates:

1. security validation
2. version support validation
3. user retrieval
4. version-specific serialization
5. lifecycle headers
6. telemetry recording
7. error handling

The controller does not implement the domain model itself.

That separation reduces coupling.

---

## 31. C++ Request Flow

The C++ case study follows this general flow:

`HTTP Request`

↓

`Version Resolution`

↓

`Authentication Check`

↓

`Version Registry`

↓

`User Service`

↓

`Version-Specific Representation`

↓

`Deprecation Headers`

↓

`Telemetry`

↓

`HTTP Response`

This is a useful architectural pattern for understanding where versioning logic belongs.

---

## 32. URL and Header Conflict Handling

The C++ program rejects requests where:

`URL = v1`

but:

`API-Version = 2`

The reason is deterministic behavior.

Without a documented rule, different components could interpret the request differently.

For example:

- gateway chooses V1
- application chooses V2
- cache uses only the URL
- logging records only the header

Such inconsistencies can create difficult debugging and security problems.

---

## 33. Caching Considerations

Caching is especially important for header-based versioning.

Suppose both clients request:

`/api/users`

Client A sends:

`API-Version: 1`

Client B sends:

`API-Version: 2`

If a cache keys only on the URL, the representations can collide.

The implementations therefore demonstrate version-aware cache keys such as:

`/api/users|API-Version=1`

and:

`/api/users|API-Version=2`

In real HTTP infrastructure, the cache configuration must correctly account for the selected request headers, commonly through appropriate `Vary` behavior or an equivalent cache-key mechanism.

---

## 34. Performance Considerations

Version parsing itself is usually inexpensive compared with major application costs.

Important sources of version-related overhead can include:

- extra serialization
- schema transformations
- database queries for legacy fields
- compatibility adapters
- duplicate business logic
- additional testing
- additional documentation
- cache fragmentation
- increased operational complexity

The Python and JavaScript implementations include simple serialization benchmarks.

The C++ implementation documents approximate complexity.

### Version Lookup

The C++ `std::map` registry provides approximately:

`O(log V)`

lookup, where `V` is the number of registered versions.

### User Lookup

The C++ user service uses `std::unordered_map`, giving expected:

`O(1)`

lookup for a user ID.

### Serialization

Serialization is approximately:

`O(S)`

where `S` represents the amount of response data processed.

### Telemetry Aggregation

Processing `E` telemetry events is approximately:

`O(E)`

for a complete aggregation pass.

These are conceptual complexity measures. Real performance also depends on memory access, serialization libraries, network I/O, database access, logging, and runtime characteristics.

---

## 35. Security Considerations

API versioning is not a security boundary by itself.

Every API version should receive appropriate:

- authentication
- authorization
- input validation
- output filtering
- rate limiting
- monitoring
- auditing
- security testing

Legacy APIs can become security risks when they remain active for long periods without receiving appropriate maintenance.

A deprecated API should not automatically be treated as less trusted.

The server must continue to enforce security requirements for every supported version.

---

## 36. Legacy Security Risk

A common operational problem is maintaining an old version only for compatibility while allowing its security controls to diverge from newer versions.

Examples include:

- old authorization rules
- outdated input validation
- old password behavior
- legacy sensitive fields
- outdated rate limits
- obsolete authentication mechanisms

Compatibility should not mean indefinite acceptance of insecure behavior.

When a legacy behavior cannot safely be maintained, its retirement requirements should be addressed explicitly.

---

## 37. Common Mistakes

### Mistake 1: Versioning Every Small Change

Not every change needs a new major API version.

If a change is compatible, introducing another version can increase unnecessary complexity.

### Mistake 2: Treating Renaming as Harmless

Changing:

`name`

to:

`full_name`

is not harmless for clients that consume `name`.

### Mistake 3: Duplicating Business Logic

Creating completely separate business implementations for every API version can produce inconsistent behavior.

Adapters can often isolate contract differences.

### Mistake 4: Ignoring Caches

Header-based versioning without cache awareness can cause one representation to be returned to a client requesting another.

### Mistake 5: Silent Version Changes

Unexpectedly changing the default version can alter response schemas without explicit client migration.

### Mistake 6: Removing a Deprecated Version Too Quickly

Deprecation is not the same as retirement.

Usage and contractual obligations must be considered.

### Mistake 7: Relying on Error Messages

Clients should not normally parse arbitrary human-readable error messages.

Stable error codes are preferable.

### Mistake 8: Ignoring Version Conflicts

When URL and header signals disagree, the behavior should be explicitly defined.

### Mistake 9: Forgetting Documentation

A versioning mechanism is ineffective if consumers cannot understand:

- what changed
- why it changed
- how to migrate
- when the old version will retire

### Mistake 10: Assuming New Fields Are Always Safe

Some clients reject unknown response fields.

Compatibility should therefore be evaluated against actual consumer behavior.

---

## 38. Edge Cases

### Unsupported Version

A client requests V99 while the server supports only V1 through V3.

The server should return a documented client error rather than silently using another version.

### Malformed Version

Examples include:

`API-Version: abc`

or:

`/api/vx/users`

These should fail validation.

### Missing Version

The server must follow its documented default or require explicit versioning.

### Conflicting Version Signals

A request specifies V1 in the URL and V2 in the header.

The implementations reject this conflict.

### Single-Word Names

The Python implementation handles a name such as:

`Atul`

without assuming that a last name exists.

### Empty Names

Request validation rejects empty names.

### Invalid Email

The examples use a basic validation rule requiring an `@` character.

A production system may require stronger validation appropriate to its actual contract.

### Retired Version

A version marked as sunset should not continue being routed accidentally.

---

## 39. Exceptions and Limitations

API versioning cannot solve every compatibility problem.

A version boundary does not automatically preserve:

- undocumented behavior
- undocumented error ordering
- timing expectations
- client-specific assumptions
- external dependencies
- database semantics
- authentication compatibility
- third-party integrations

Versioning also creates costs.

Supporting V1, V2, and V3 simultaneously can require:

- more code
- more tests
- more documentation
- more monitoring
- more infrastructure
- more operational decisions

The objective is controlled evolution, not unlimited accumulation of old versions.

---

## 40. API Versioning and Feature Flags

API versions and feature flags serve different purposes.

### API Version

Defines a public contract.

Example:

`/api/v2/users`

### Feature Flag

Controls a behavior or rollout independently of the public API contract.

A feature flag can be useful for:

- gradual internal rollout
- experimentation
- operational control
- enabling a capability for selected users

A feature flag should not be used as an unclear substitute for a public breaking-contract boundary.

Likewise, creating an entire API version for every internal experiment can create unnecessary contract complexity.

---

## 41. API Versioning and Semantic Versioning

API major versions and software semantic versions are related concepts but should not automatically be treated as identical.

A software package may use:

`2.7.4`

while a public HTTP API may use:

`v2`

The API's major version normally communicates an externally meaningful compatibility boundary.

Internal application releases can occur independently.

For example:

`API v2`

could be implemented by many internal application releases without changing the public API contract.

---

## 42. Testing Strategy

A versioned API should have a contract test suite for every supported version.

Tests should verify:

### Routing

- valid version routes correctly
- malformed versions fail
- unsupported versions fail

### Request Validation

- required fields are enforced
- optional fields remain optional when documented
- incompatible requests are rejected

### Response Shape

- V1 has its documented fields
- V2 has its documented fields
- V3 has its documented structure

### Compatibility

- old contracts remain available while supported
- adapters translate old requests correctly

### Lifecycle

- deprecated versions expose the intended warnings
- sunset versions are not served

### Security

- authentication applies to every version
- authorization applies to every version
- sensitive data does not leak through legacy representations

### Caching

- different versions cannot collide in caches

The Python implementation uses `unittest` for automated checks.

The JavaScript implementation provides explicit contract assertions.

The C++ implementation uses a complete executable case study with validation and controlled error paths.

---

## 43. Observability

Version information should be visible in operational data.

Useful dimensions include:

- API version
- endpoint
- client
- status code
- latency
- error code
- request volume
- deprecation usage

For example:

`client-a -> v1 -> GET /users -> 200`

can be much more useful for migration management than simply knowing that:

`GET /users -> 200`

occurred.

Observability helps distinguish active legacy consumers from inactive or historical records.

---

## 44. Documentation Requirements

Each supported version should have clearly documented:

- endpoints
- request schemas
- response schemas
- error codes
- authentication requirements
- authorization behavior
- pagination
- filtering
- rate limits
- version-selection mechanism
- deprecation state
- migration information

A deprecated version should clearly identify its successor where one exists.

---

## 45. Production Architecture

A practical architecture can separate concerns as follows:

`Version Resolver`

determines which contract applies.

↓

`Authentication`

verifies the caller.

↓

`Authorization`

determines whether the caller can perform the operation.

↓

`Request Adapter`

converts the public request into a canonical form.

↓

`Domain Service`

executes business logic.

↓

`Response Mapper`

converts the internal result into the selected public representation.

↓

`Lifecycle Middleware`

adds deprecation information where applicable.

↓

`Telemetry`

records version and consumer information.

This architecture limits the spread of version-specific logic.

---

## 46. Implementation Correspondence

### Python

The Python implementation demonstrates:

- version objects
- URL parsing
- custom headers
- media-type versioning
- response serializers
- request validation
- adapters
- shared domain services
- version routing
- deprecation lifecycle
- deprecation headers
- telemetry
- cache keys
- error contracts
- conflict detection
- automated tests
- governance checks
- production checklist

### JavaScript

The JavaScript implementation demonstrates:

- JavaScript classes
- `Map`
- object-based JSON representations
- URL parsing
- custom header parsing
- media-type parsing
- adapters
- asynchronous data access
- Promises
- `async` and `await`
- event-driven deprecation telemetry
- middleware-style version resolution
- contract assertions
- cache keys
- lifecycle records

### C++

The C++ implementation demonstrates:

- strong class-based modeling
- exceptions
- `std::map`
- `std::unordered_map`
- `std::optional`
- `std::set`
- regular expressions
- request and response structures
- version registries
- domain services
- controllers
- serializers
- validation
- adapters
- telemetry
- security checks
- lifecycle policies
- complexity considerations
- end-to-end request processing

---

## 47. Important Architectural Distinction

One of the most important ideas demonstrated by all three implementations is the separation between:

`Public API Contract`

and:

`Internal Domain Model`

The API contract can evolve independently of the internal representation.

For example:

V1:

`name`

V2:

`first_name + last_name`

V3:

`identity.firstName + identity.lastName`

The internal model can still contain:

`firstName`

and:

`lastName`

This reduces coupling.

The public API should not be forced to expose the internal database schema directly.

---

## 48. Deprecation Governance

Deprecation should be treated as a lifecycle-management problem rather than simply a code annotation.

A governance record can contain:

- version
- lifecycle state
- release date
- deprecation date
- sunset date
- successor
- migration documentation
- consumer usage
- ownership
- operational status

The Python and C++ implementations model these concepts explicitly.

This creates a record that can be inspected independently of individual request handlers.

---

## 49. When to Create a New Version

A new API version is generally relevant when the public contract must change incompatibly.

Examples include:

- removing required response properties
- renaming required fields
- changing data types incompatibly
- changing request requirements
- changing documented semantics
- changing endpoint behavior in a way that existing consumers cannot safely absorb

A compatible change may not require a new version.

The engineering decision should be based on contract compatibility rather than the size of the internal code change.

---

## 50. Version Proliferation

Every additional version increases the maintenance surface.

If three versions are active, the organization may need to maintain:

- three response contracts
- multiple request schemas
- multiple tests
- multiple documentation sets
- multiple migration paths
- multiple monitoring dimensions

If every small feature creates another version, the number of contracts can grow rapidly.

This is why compatibility discipline is important.

---

## 51. Migration Metrics

Useful migration measurements include:

`V1 request percentage`

`V1 active clients`

`V1 requests per endpoint`

`V1 error rate`

`V2 adoption`

`V3 adoption`

`Requests after deprecation`

These measurements can be used to identify remaining dependencies.

A traffic graph showing declining V1 usage is descriptive operational evidence. It does not by itself establish that retirement is appropriate because contractual and security requirements may still apply.

---

## 52. Security and Deprecation Interaction

A deprecated version may remain available for a migration period, but it should not become an unmaintained security exception.

Important controls include:

- security patches
- authentication
- authorization
- input validation
- output filtering
- logging
- monitoring
- abuse detection
- rate limiting

If a legacy contract contains an unsafe behavior that cannot be maintained securely, the retirement process must account for that constraint explicitly.

---

## 53. Performance and Operational Cost

Supporting several versions creates more than CPU overhead.

The operational costs can include:

- additional deployment paths
- more test combinations
- more documentation
- larger observability datasets
- more cache variants
- more support cases
- more compatibility code
- more security-review scope

The best architecture therefore keeps version-specific logic near the API boundary wherever practical.

---

## 54. Practical Request Flow

For a V1 URL-versioned request:

`GET /api/v1/users`

the conceptual flow is:

1. Parse V1.
2. Authenticate the caller.
3. Check whether V1 is supported.
4. Execute domain logic.
5. Serialize using the V1 contract.
6. Add deprecation headers if V1 is deprecated.
7. Record telemetry.
8. Return the response.

For V2:

`GET /api/v2/users`

the same domain operation can produce a different representation.

For header versioning:

`GET /api/users`

with:

`API-Version: 2`

the version is selected from the request header instead.

---

## 55. Production Checklist

A production API versioning implementation should explicitly define:

- What constitutes a breaking change
- How versions are selected
- How missing versions behave
- How unsupported versions behave
- How conflicting version signals behave
- Which versions are supported
- Which versions are deprecated
- Which versions are scheduled for sunset
- How compatibility is tested
- How caches distinguish representations
- How errors are represented
- How authentication applies across versions
- How authorization applies across versions
- How consumer usage is measured
- How migration documentation is maintained
- How deprecation is communicated
- How sunset dates are managed
- How contractual obligations are checked
- How retired versions are removed

---

## 56. Key Technical Relationships

The major concepts are connected:

`API Versioning`

defines the contract boundary.

`Backward Compatibility`

controls whether old consumers can continue using the service.

`Adapters`

translate incompatible public contracts into shared internal representations.

`Deprecation`

communicates that an older contract should be replaced.

`Telemetry`

measures which consumers still depend on that contract.

`Sunset`

defines the planned retirement point.

`Testing`

protects each supported contract.

`Security`

ensures that every supported contract remains subject to appropriate controls.

`Caching`

ensures different representations do not collide.

Together these concepts form an API lifecycle rather than isolated version-numbering techniques.
