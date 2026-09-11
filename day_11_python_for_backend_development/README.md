# Python for backend development

## Topic scope

This study file develops the Python concepts that form a practical foundation for backend development:

- Python data structures
- Functions
- Classes and objects
- Object-oriented programming
- Dataclasses
- Iterables and iterators
- Generators
- Decorators
- Type hints and typing
- Error handling
- Validation
- Backend-oriented service and repository design
- Dependency injection
- Performance considerations
- Security considerations
- Testing
- Concurrency and asynchronous I/O
- Common Python pitfalls
- Production-oriented design considerations

The Python script is executable and uses the standard library. Each section demonstrates a concept through working code rather than treating the subject as purely theoretical.

## Python's role in backend development

Backend software receives input, applies business rules, interacts with data stores and external services, and produces responses.

Python is well suited to this type of software because it provides:

- expressive syntax
- extensive standard-library support
- functions as first-class objects
- object-oriented programming
- generators and iterators
- strong support for data processing
- runtime exception handling
- optional static typing
- asynchronous programming facilities
- mature abstractions for application architecture

The language itself does not define a complete backend architecture. Backend applications normally combine Python language features with frameworks, database systems, networking libraries, deployment infrastructure, logging, testing, authentication, and observability.

The concepts in this script therefore focus on the Python language and the design principles that remain relevant across different backend technologies.

## Fundamental Python objects

Python variables reference objects.

Common built-in types include:

| Type | Typical backend use |
| --- | --- |
| `int` | IDs, counters, quantities |
| `float` | Approximate numerical calculations |
| `str` | Names, identifiers, messages |
| `bool` | Flags and conditions |
| `None` | Absence of a value |
| `list` | Ordered collections |
| `tuple` | Fixed sequences |
| `dict` | Key-value records and indexes |
| `set` | Unique values and membership checks |

Python is dynamically typed. A variable does not need a declared runtime type before it can reference an object.

Type annotations can describe the intended types without changing Python's fundamental runtime typing model.

## Lists

A list is an ordered, mutable sequence.

Typical operations include:

- indexing
- slicing
- replacement
- appending
- extending
- removing
- iteration
- filtering
- transformation

Lists are useful when order matters and the collection needs to change.

For example, a backend application may use a list to represent:

- search results
- ordered messages
- validation errors
- API response records
- items in an order

Important characteristics include:

- indexed access is typically O(1)
- membership testing is O(n)
- appending at the end is amortized O(1)
- insertion near the beginning is O(n)

A list is not automatically the best structure for every lookup problem. Repeated searches by identifier are generally better represented by a dictionary.

## Tuples

A tuple is an ordered immutable sequence.

Tuple unpacking allows multiple values to be assigned in one operation.

A tuple can represent a fixed group of related values, such as coordinates or a database-style composite key.

Tuples can also be dictionary keys when every contained value is hashable.

Immutability makes tuples useful when the collection should not be modified through normal tuple operations.

## Dictionaries

A dictionary stores key-value associations.

For example:

    user = {
        "id": 101,
        "name": "Atul",
        "role": "developer"
    }

Dictionaries are particularly important in backend programming because JSON-like request and response structures naturally map to Python dictionaries.

Common operations include:

- `get()`
- key assignment
- `pop()`
- `keys()`
- `values()`
- `items()`

Dictionary lookup has average-case O(1) complexity.

A dictionary can also act as an in-memory index:

    users_by_id[user_id]

This is substantially more efficient for repeated identifier lookups than scanning a list of records.

## Sets

A set contains unique hashable values.

Sets are useful for:

- permissions
- tags
- deduplication
- membership tests
- intersections
- unions
- differences

For example, authorization logic can compare a user's permissions with the permissions required for an operation.

Typical average-case membership testing is O(1).

Sets do not provide list-style indexing and should not be selected when positional ordering is the primary requirement.

## Stacks and queues

A stack follows last-in, first-out behavior.

A Python list can implement a stack efficiently with:

    append()
    pop()

A queue follows first-in, first-out behavior.

`collections.deque` is preferable for queue operations because adding or removing elements from either end is efficient.

Queues are useful for concepts such as:

- request processing
- background work
- event processing
- task scheduling

In a distributed production backend, an in-memory queue is often insufficient because multiple processes or machines may need to share the same work queue.

## Counter and defaultdict

`Counter` is useful for frequency counting.

For example, it can count:

- API endpoints
- words
- event types
- status values

`defaultdict` provides an automatic default value for missing keys and is particularly useful for grouping.

These structures reduce repetitive initialization logic.

## Functions

Functions package reusable behavior.

The script demonstrates:

- positional arguments
- keyword arguments
- default arguments
- variable positional arguments with `*args`
- variable keyword arguments with `**kwargs`
- return values
- validation
- exceptions
- type annotations

Functions should generally have one clear responsibility.

A backend service can be composed of functions that perform operations such as:

- validating input
- transforming records
- calculating business values
- checking permissions
- formatting responses

## Function arguments

A function can use required arguments:

    def greet_user(name: str) -> str:
        ...

Default arguments provide a value when the caller does not specify one.

Keyword arguments make calls explicit:

    calculate_total(price=250, quantity=2, tax_rate=0.05)

`*args` collects additional positional arguments.

`**kwargs` collects additional keyword arguments.

These mechanisms are powerful, but unrestricted `**kwargs` can make an API less explicit and harder to validate. It should be used where flexible keyword input is genuinely useful.

## First-class functions

Functions are objects in Python.

A function can therefore be:

- assigned to a variable
- passed to another function
- returned from a function
- stored in a collection

This property enables:

- callbacks
- decorators
- configurable operations
- functional pipelines
- strategy-style designs

The script demonstrates passing an operation into another function.

## Lambda functions

A lambda creates a small anonymous function.

They are useful for concise operations such as sorting:

    sorted(users, key=lambda user: user["age"])

A named function is normally clearer when the operation has significant logic or will be reused.

## Comprehensions

List and dictionary comprehensions provide concise ways to construct collections.

For example:

    squares = [number * number for number in numbers]

A comprehension is generally appropriate when the transformation remains easy to understand. Complex business logic should usually be placed in a named function.

## Scope and closures

Python resolves names according to its scope rules.

A nested function can retain access to variables from its enclosing function. This is called a closure.

Closures are useful for:

- decorators
- configurable functions
- encapsulated state
- callback factories

The script implements a counter using a closure and `nonlocal`.

Closures can also produce subtle behavior when loop variables are captured. Python's late-binding behavior means that a closure may evaluate a variable's final value rather than the value that existed during each loop iteration.

A default argument can be used to capture the current value in appropriate situations.

## Recursion

Recursion occurs when a function calls itself.

It is useful for naturally recursive structures such as trees and some algorithms.

The factorial example demonstrates the basic pattern.

Python has a recursion-depth limit, so recursion is not automatically suitable for deeply nested input. An iterative solution may be safer for large workloads.

## Classes and objects

A class defines a structure and behavior that objects can instantiate.

The `User` class demonstrates:

- constructor initialization
- instance attributes
- class attributes
- methods
- properties
- object representation

Objects are useful when data and related behavior naturally belong together.

Backend domain models frequently represent concepts such as:

- users
- orders
- products
- invoices
- accounts
- transactions

## Encapsulation

Python does not enforce traditional private fields in the same way as some languages.

A leading underscore conventionally communicates that an attribute is intended for internal use.

The `BankAccount` example stores its balance as `_balance` and exposes it through a property.

Encapsulation helps protect domain invariants.

For example, a bank account should not allow arbitrary negative withdrawals merely because another piece of code can reach its internal state.

## Properties

A property allows attribute-style access while executing method logic.

For example:

    account.balance

can call a getter internally.

Properties are useful when a value needs:

- validation
- calculated behavior
- controlled access
- compatibility with an attribute-style API

## Class methods and static methods

A class method receives the class as its first argument and is commonly used for alternate constructors.

The `BankAccount.from_string()` method is an example.

A static method does not receive an instance or class automatically. It is appropriate when a function logically belongs to a class namespace but does not need object or class state.

## Inheritance

Inheritance allows a class to specialize another class.

The script demonstrates:

- a base `User`
- an `AdminUser`
- a `GuestUser`

Inheritance can be useful when there is a genuine is-a relationship and meaningful shared behavior.

Deep inheritance hierarchies can make systems difficult to understand and modify. Composition is often preferable when behavior needs to be assembled from independent components.

## Polymorphism

Polymorphism allows different objects to be used through a common interface.

The administrative and guest users provide different permission behavior while participating in the same general user model.

This is valuable in backend design because services can depend on behavior rather than a specific concrete implementation.

## Dataclasses

`dataclasses.dataclass` reduces boilerplate for classes primarily representing data.

A dataclass can automatically provide methods such as:

- `__init__`
- `__repr__`
- equality behavior

The `Product`, `Customer`, `Order`, and other models demonstrate this style.

`field(default_factory=...)` is important when a mutable default such as a list is required. It creates a new collection for each object.

## Frozen dataclasses

A frozen dataclass prevents normal attribute reassignment.

This can be useful for value-like objects where mutation should not occur.

The script uses frozen dataclasses for entities such as `Customer`, `Coordinate`, and `OrderItem`.

Immutability reduces some categories of accidental state changes and can make objects easier to reason about.

## Special methods

Special methods are commonly recognized by double underscores.

Examples include:

- `__init__`
- `__repr__`
- `__eq__`
- `__add__`
- `__iter__`
- `__next__`
- `__len__`
- `__contains__`
- `__enter__`
- `__exit__`

They allow objects to participate naturally in Python language operations.

The `Money` class demonstrates operator overloading.

Operator overloading should preserve intuitive semantics. A class should not overload an operator in a way that surprises users of the class.

## Iterables

An iterable is an object that can provide its elements one at a time.

Common iterables include:

- lists
- tuples
- strings
- dictionaries
- sets
- files
- generators

The `for` statement works through Python's iteration protocol.

## Iterators

An iterator maintains traversal state and provides a `__next__()` method.

The `iter()` function obtains an iterator from an iterable.

Calling `next()` retrieves the next value.

When no values remain, the iterator raises `StopIteration`.

The custom `Countdown` class demonstrates the iterator protocol explicitly.

## Iterator protocol

The central iterator methods are:

    __iter__()
    __next__()

An iterator normally returns itself from `__iter__()`.

The iterator protocol is important because it allows Python's `for` loops and many built-in functions to work consistently with custom collections.

## Generators

A generator is a convenient way to create an iterator using `yield`.

For example, the script's number generator produces values lazily.

Unlike a list:

    [number * number for number in range(1000000)]

a generator expression:

    (number * number for number in range(1000000))

does not immediately construct the entire result collection.

This makes generators useful for:

- large files
- streaming records
- database result processing
- paginated data
- transformation pipelines
- event processing

Generators trade repeated materialization for lazy evaluation.

## Generator pipelines

Generators can be connected together.

The script uses:

- `read_numbers`
- `filter_even`
- `square_numbers`

to form a lazy processing pipeline.

This approach can process data incrementally rather than creating intermediate lists.

A pipeline can be especially useful when a dataset is too large to comfortably fit into memory.

## Generator protocol

Generators support more than simple `yield`.

Advanced generators can respond to:

- `send()`
- `throw()`
- `close()`

`send()` passes a value into a suspended generator.

`close()` terminates the generator.

These features support specialized coroutine-like designs. Ordinary data streaming usually only requires `yield`.

## Generators versus lists

Lists and generators serve different purposes.

| Requirement | List | Generator |
| --- | --- | --- |
| Immediate materialization | Good | No |
| Random indexing | Good | Not directly |
| Repeated iteration | Good | Usually requires recreation |
| Large streaming data | Memory-intensive | Good |
| Lazy evaluation | No | Yes |
| Complete dataset immediately available | Good | No |

Neither is universally better.

The correct choice depends on memory requirements, access patterns, and whether the data needs to exist simultaneously.

## Decorators

A decorator receives a callable and returns another callable.

Decorators allow behavior to be added without directly modifying the decorated function's implementation.

Common backend uses include:

- authorization
- logging
- timing
- caching
- validation
- tracing
- transaction handling

The `log_call` decorator demonstrates the basic structure.

## functools.wraps

A decorator wrapper should generally use `functools.wraps`.

Without `wraps`, metadata such as the original function's name and documentation can be lost.

The script uses:

    @wraps(function)

for its decorators.

This is an important implementation detail when building reusable decorators.

## Parameterized decorators

A decorator requiring configuration needs an additional layer.

The `repeat(times)` example illustrates the structure:

    decorator factory
        -> decorator
            -> wrapper

This pattern is useful for configurable behavior such as:

- role requirements
- retry counts
- rate limits
- feature flags
- logging configuration

## Authorization decorators

The `require_role` example demonstrates a simplified authorization boundary.

The decorator checks the caller's role before executing the protected function.

In production systems, authorization must be based on trusted authentication context rather than arbitrary user-controlled values. A real backend also needs careful handling of identity, roles, permissions, resource ownership, and audit requirements.

## Decorator stacking

Multiple decorators can be applied to the same function.

The order matters because decorators wrap the result of other decorators.

When decorators are stacked, the resulting execution path is layered.

This can be powerful, but excessive decorator layers can make control flow harder to understand and debug.

## Error handling

Backend programs must distinguish expected application errors from unexpected failures.

The script demonstrates:

- `try`
- `except`
- `else`
- `finally`
- custom exceptions
- exception chaining

A specific exception should normally be caught rather than using a broad `except Exception` unnecessarily.

Broad exception handling can hide programming errors and make debugging difficult.

## Custom exceptions

Custom exceptions communicate application-specific failure conditions.

The script defines:

- `ValidationError`
- `NotFoundError`

This makes the intent of error handling clearer.

A service can raise a domain-specific exception, while an HTTP layer can later translate that exception into an appropriate HTTP status and response structure.

## Exception chaining

Exception chaining preserves the original cause.

For example, a low-level conversion failure can become a domain-level validation error while retaining the original exception as its cause.

This is useful for debugging without exposing internal implementation details to end users.

## Runtime validation

Type hints do not validate incoming data.

External data can come from:

- HTTP requests
- JSON
- forms
- databases
- files
- environment variables
- message queues

All such inputs should be validated according to the application's domain rules.

The `parse_id` function demonstrates explicit runtime conversion.

## Type hints

Python type hints communicate intended types.

Examples include:

    name: str
    age: int
    price: float

and return annotations:

    def average(values: Sequence[float]) -> float:

Type annotations improve:

- readability
- editor support
- static analysis
- refactoring
- API documentation
- maintenance

They do not normally enforce types at runtime.

## Modern union syntax

The script uses:

    str | None

to indicate that a value may contain either a string or `None`.

This is the modern Python syntax for a union and is generally easier to read than older forms.

## Optional values

An optional value represents a value that may be absent.

For example:

    def find_email(user: Mapping[str, Any]) -> str | None:

The caller must account for both possibilities.

The distinction between absence and falsiness matters.

These values are all falsy:

- `None`
- `False`
- `0`
- `""`
- `[]`
- `{}`

If the application specifically needs to determine whether a value is absent, `value is None` is clearer than `if not value`.

## Literal

`Literal` restricts an annotated value to a specific set of possible values.

The script uses:

    Literal["active", "inactive", "suspended"]

This can improve static analysis for state fields and API-style structures.

It does not replace runtime validation.

## TypedDict

`TypedDict` describes the expected keys and value types of dictionary-shaped data.

It is useful when an application uses dictionaries to represent structured payloads.

Unlike a dataclass, a `TypedDict` is primarily a typing construct. At runtime it behaves as a dictionary structure rather than automatically enforcing the declared types.

## Generics

Generics allow reusable classes and functions to operate on different types while preserving type information.

The generic `Repository[T]` can be used with different domain objects.

For example:

    Repository[User]

and:

    Repository[Product]

can share the same repository implementation while maintaining meaningful type information.

Generics are particularly useful for reusable backend infrastructure such as:

- repositories
- response containers
- pagination objects
- caches
- queues
- collections

## Type variables

`TypeVar` represents a type parameter.

The script uses:

    T = TypeVar("T")

to connect input and output types in generic structures.

This is more precise than replacing everything with `Any`.

## Any

`Any` disables much of the benefit of static type checking for the affected value.

It is sometimes appropriate for genuinely dynamic data, but excessive use of `Any` weakens the type system.

External JSON-like data is often initially dynamic, but application boundaries can progressively validate and narrow its structure.

## Protocol

A `Protocol` describes behavior rather than requiring inheritance.

For example, a logger only needs to provide:

    log(message: str) -> None

Any compatible object can satisfy that interface structurally.

This supports loose coupling and dependency injection.

Protocols are especially useful for infrastructure dependencies such as:

- loggers
- notification senders
- storage providers
- payment gateways
- external service clients

## Function overloads

`@overload` communicates multiple supported call signatures to static type checkers.

The runtime implementation remains a normal Python function.

Overloads are useful when the relationship between input and output types is more specific than a single broad annotation can express.

## Repository pattern

The repository examples separate persistence concerns from business logic.

A repository is responsible for operations such as:

- save
- retrieve
- list
- delete

The repository does not need to know how a service's business rules work.

In the study script, repositories use dictionaries instead of a real database so that the concepts remain self-contained.

## Service layer

A service layer contains business logic.

For example, the customer service:

- validates required information
- checks whether an entity already exists
- normalizes input
- creates a domain object
- delegates storage to the repository

This separation prevents business rules from becoming tightly coupled to transport or persistence code.

## Separation of concerns

A backend application commonly contains conceptual layers such as:

    HTTP / API layer
        ↓
    service / business layer
        ↓
    repository / persistence layer
        ↓
    database or external storage

The exact architecture can differ, but separating responsibilities makes code easier to test and maintain.

The study script focuses on the service and repository concepts without requiring a web framework.

## Dependency injection

Dependency injection means supplying a component's dependencies from outside rather than having the component construct them internally.

The notification service receives a sender object.

This allows the same service to work with:

- a console sender
- a memory sender for testing
- a production email provider
- another implementation satisfying the protocol

Dependency injection improves testability and reduces coupling.

## Context managers

Context managers control resource lifecycles.

The common syntax is:

    with resource:
        ...

The context manager protocol uses:

    __enter__()
    __exit__()

Typical uses include:

- files
- database transactions
- locks
- timing
- temporary resources

The file examples in the script use `with` so that the file is closed reliably.

## File iteration

Files can be iterated line by line.

This is important for large files because reading the entire file into memory may be unnecessary.

The `stream_lines` generator combines:

- context management
- file iteration
- lazy generation

This is a useful pattern for backend data processing.

## Descriptors

Descriptors implement attribute access behavior through methods such as:

- `__get__`
- `__set__`
- `__delete__`

The `PositiveNumber` descriptor validates assignment.

Descriptors are part of Python's deeper object model and are involved in several built-in mechanisms.

Properties are generally simpler when only one class needs the behavior. Descriptors become useful when attribute behavior needs to be reusable or generalized.

## Class registration and metaprogramming

The `__init_subclass__` hook allows a base class to observe subclass creation.

The plugin example automatically registers subclasses.

This demonstrates a controlled form of metaprogramming.

Such mechanisms can be powerful but should be used carefully. Implicit registration can make program behavior harder to discover if overused.

## Common Python pitfall: mutable defaults

This pattern is dangerous:

    def add_tag(tag, tags=[]):
        ...

The default list is created once and reused across calls.

The safe pattern is:

    def add_tag(tag, tags=None):
        if tags is None:
            tags = []

This is one of the most important Python-specific edge cases for beginners.

## Common Python pitfall: late-binding closures

A lambda created inside a loop may capture the loop variable itself rather than a snapshot of its value.

As a result, multiple functions may produce the same final value.

A default argument can capture the current value:

    lambda number=number: number

This behavior is subtle and important when building callbacks or dynamically generated functions.

## Shallow and deep copying

A shallow copy duplicates the outer container but retains references to nested objects.

A deep copy recursively copies nested structures.

The distinction matters when working with:

- configuration dictionaries
- request data
- nested application state
- mutable domain structures

Deep copying can be expensive, so it should not be used indiscriminately.

## Caching

Caching avoids repeating expensive work.

The script demonstrates `functools.lru_cache`.

Caching is appropriate when a function is sufficiently deterministic and repeated calls benefit from stored results.

Caching introduces trade-offs:

- memory usage
- stale data
- invalidation complexity
- consistency problems

In distributed applications, cache design becomes more complex because multiple application instances may hold different state.

## Rate limiting

The example implements a simple fixed-window in-memory rate limiter.

A rate limiter restricts how frequently a client can perform an operation.

Rate limiting can protect:

- APIs
- authentication endpoints
- expensive operations
- public services

The example is intentionally simple.

A production application with multiple workers or servers generally requires shared state or an infrastructure-level mechanism so that clients cannot bypass limits by switching application instances.

## Performance considerations

Data structure choice affects performance.

Typical average-case characteristics include:

| Operation | Typical complexity |
| --- | --- |
| List indexed access | O(1) |
| List membership | O(n) |
| Dictionary lookup | O(1) |
| Set membership | O(1) |
| Deque append | O(1) |
| Deque left removal | O(1) |
| Sorting | O(n log n) |

These are general complexity characteristics rather than guarantees of identical wall-clock performance.

Actual performance depends on:

- input size
- hardware
- memory behavior
- implementation details
- workload patterns
- contention
- network and database latency

## Choosing a data structure

The appropriate structure depends on the access pattern.

Use a list when:

- order matters
- indexed access is useful
- sequential processing is expected

Use a tuple when:

- the sequence represents a fixed value
- mutation should not occur

Use a dictionary when:

- lookup is based on a key
- records need named fields
- indexing is important

Use a set when:

- uniqueness matters
- membership testing is frequent

Use a deque when:

- both ends of a sequence need efficient operations
- a queue is required

Use a generator when:

- data can be processed lazily
- complete materialization is unnecessary
- memory usage matters

## Security considerations

Python language features do not automatically make a backend secure.

Important practices include:

### Validate external input

Never assume HTTP, JSON, form, file, or message input is valid.

Convert and validate values before applying business logic.

### Avoid eval with untrusted data

`eval()` can execute arbitrary Python expressions.

It must not be used to interpret untrusted user input.

### Use parameterized database queries

Database statements should use the parameterization facilities of the database library rather than concatenating user input into SQL.

### Protect secrets

Passwords, API keys, database credentials, signing keys, and other secrets should not be hard-coded into source code.

### Control error exposure

Internal exceptions may contain implementation details that should not be returned directly to external clients.

A backend should translate internal failures into appropriate public error responses.

### Authorization must use trusted identity

A role value supplied by the client cannot be treated as proof of authorization.

Authentication establishes identity. Authorization determines what that identity is permitted to do.

## Asynchronous programming

The script includes a small asynchronous example using `asyncio`.

Asynchronous programming is particularly useful for I/O-bound workloads where a program spends significant time waiting for:

- network responses
- databases
- files
- external services

The example runs multiple simulated I/O operations concurrently.

Asynchronous programming is not automatically faster for CPU-heavy calculations. CPU-intensive workloads require appropriate approaches such as multiprocessing, optimized native libraries, or task distribution depending on the problem.

## Thread-safety

Concurrent execution can expose shared mutable state to race conditions.

The existence of Python's Global Interpreter Lock does not mean arbitrary application code is automatically thread-safe.

Shared state may require:

- locks
- thread-safe queues
- immutable data
- transactional storage
- external coordination

The correct strategy depends on the workload and execution model.

## Serialization

Backend applications frequently transform domain objects into API-compatible data structures.

The `customer_to_dict()` example converts a dataclass into a dictionary containing externally relevant fields.

Serialization should be deliberate.

Internal implementation state should not automatically become public API data.

A production serialization layer should define:

- exposed fields
- field names
- types
- optional values
- nested structures
- compatibility expectations

## API response models

The generic `ApiResponse[T]` class demonstrates a typed response structure containing:

- status code
- optional data
- optional error
- timestamp

Generic response models allow the data payload to preserve type information.

Real HTTP applications normally use the response and status mechanisms provided by their web framework, but the underlying data-modeling concepts remain applicable.

## Validation and domain rules

Validation can happen at multiple levels.

Syntax or structural validation checks whether the input has the expected shape.

Domain validation checks whether the value makes sense for the application's rules.

For example:

- an age may need to fall within an allowed range
- an order may require at least one item
- a quantity may need to be positive
- an email may need an accepted structure

The service layer is often responsible for business-level rules.

## Testing

The script includes executable assertions for:

- calculations
- factorial
- repository behavior

Automated tests should verify behavior rather than merely implementation details.

Backend tests commonly cover:

- successful operations
- invalid input
- missing resources
- authorization failures
- boundary conditions
- state transitions
- error handling

The most important edge cases should be tested explicitly.

## Edge cases

The script demonstrates cases involving:

- empty collections
- zero
- negative values
- empty strings
- `None`
- invalid identifiers
- invalid page sizes
- empty statistical input
- empty orders
- duplicate resources
- invalid states

Edge cases are particularly important in backend systems because external input is not guaranteed to be well behaved.

## Pagination

Pagination limits the amount of data returned or processed at one time.

The script implements a generator-based pagination function.

Pagination reduces the need to materialize a complete large result set in memory.

Real backend pagination also requires careful consideration of:

- stable ordering
- database indexes
- concurrent inserts and deletes
- offset-based pagination
- cursor-based pagination
- page-size limits

## Inventory example

The integrated inventory example combines several concepts:

- dataclasses
- dictionaries
- validation
- generators
- iteration
- type annotations
- calculated values

The dictionary provides efficient SKU-based lookup, while the generator provides lazy low-stock filtering.

This illustrates how individual Python language features can combine into a small domain-oriented component.

## Integrated order example

The order example combines:

- immutable order items
- mutable order state
- type-safe status values
- validation
- repositories
- services
- decorators
- iteration
- calculations
- exceptions

The repository stores orders, while the service controls creation and confirmation rules.

This illustrates separation between data persistence and business behavior.

## Backend-oriented design principles

Several principles recur throughout the script.

### Keep responsibilities clear

A function or class should have a focused responsibility.

### Prefer explicit validation

External data should not be trusted simply because it arrives in a Python dictionary.

### Select data structures according to access patterns

The choice between list, dictionary, set, deque, and generator should be based on required operations.

### Use abstractions where they reduce coupling

Protocols and dependency injection are valuable when components need replaceable implementations.

### Prefer simple designs

Advanced Python features such as descriptors and metaprogramming should be used when they solve a real problem rather than merely because they exist.

### Measure before optimizing

Performance assumptions should be verified with measurements and workload-specific profiling.

### Preserve useful type information

Type annotations should describe meaningful application boundaries rather than turning the entire program into `Any`.

### Handle errors deliberately

Expected application failures should be distinguishable from unexpected programming failures.

## Production considerations

A production backend built with Python requires concerns beyond the language itself.

Important areas include:

- input validation
- authentication
- authorization
- database transactions
- connection management
- logging
- monitoring
- tracing
- configuration
- secret management
- testing
- deployment
- concurrency
- caching
- rate limiting
- error handling
- resource management
- API compatibility
- performance measurement

The Python concepts in this script form the programming foundation for those larger systems.

## Important distinctions

### Iterable versus iterator

An iterable can provide an iterator.

An iterator maintains traversal state and produces values through `__next__()`.

A list is iterable but is not itself an iterator.

### Iterator versus generator

A generator is a convenient way to create an iterator using `yield`.

Custom iterators require explicit protocol implementation when that level of control is needed.

### Function versus decorator

A function performs an operation.

A decorator receives a callable and returns another callable that modifies or wraps behavior.

### Class versus object

A class defines structure and behavior.

An object is an instance of a class.

### Static typing versus runtime validation

Type annotations describe intended types and support tooling.

Runtime validation is still required for untrusted external input.

### List versus dictionary

A list is optimized for ordered sequential data and indexed access.

A dictionary is optimized for key-based lookup.

### Set versus dictionary

Both use hash-based lookup internally, but a set stores unique values while a dictionary stores key-value associations.

### Inheritance versus composition

Inheritance models specialization between classes.

Composition builds behavior by combining independent objects.

Composition is often easier to change when requirements evolve.

## Common mistakes

Common mistakes demonstrated or addressed by the script include:

- using a mutable default argument
- modifying collections while iterating over them
- confusing `None` with all falsy values
- using a list for repeated key-based searches
- assuming type hints perform runtime validation
- catching every exception indiscriminately
- exposing internal exceptions directly to clients
- using `eval()` on untrusted input
- assuming in-memory state works across multiple application instances
- using recursion for deeply nested input without considering recursion limits
- creating unnecessarily complex decorator chains
- overusing `Any`
- treating caching as free performance
- assuming the Global Interpreter Lock eliminates concurrency problems
- reading huge files entirely into memory when streaming is sufficient

## Relationship to backend development

The Python features studied here map directly to common backend responsibilities.

| Python concept | Backend relevance |
| --- | --- |
| Dictionaries | JSON-like data and indexes |
| Lists | Collections and response data |
| Sets | Permissions and uniqueness |
| Functions | Business operations |
| Classes | Domain models and services |
| Dataclasses | Structured application data |
| Decorators | Cross-cutting behavior |
| Iterators | Sequential processing |
| Generators | Streaming and memory-efficient pipelines |
| Type hints | Maintainable interfaces |
| Exceptions | Application failure handling |
| Protocols | Replaceable dependencies |
| Context managers | Resource lifecycle management |
| Generics | Reusable typed infrastructure |
| Async programming | Concurrent I/O |
| Testing | Verification of business behavior |

## Code organization

The script is intentionally organized into independent demonstrations and a `main()` function.

This structure illustrates an important Python practice:

- definitions are placed in functions and classes
- execution is controlled by `main()`
- the `if __name__ == "__main__":` guard prevents automatic execution when the file is imported

This pattern makes a module easier to reuse and test.

## Standard library usage

The script uses only Python's standard library, including modules such as:

- `collections`
- `dataclasses`
- `functools`
- `itertools`
- `pathlib`
- `statistics`
- `typing`
- `asyncio`
- `time`

These modules provide substantial functionality without requiring external packages.

The examples deliberately avoid framework-specific APIs so that the underlying Python concepts remain visible.

## Implementation considerations

The most important implementation lesson is that backend programming is not simply about writing functions that return values.

A backend component needs to account for:

- input shape
- valid and invalid states
- data structures
- object ownership
- error behavior
- resource lifetime
- performance
- security
- testability
- maintainability
- concurrency
- interfaces between components

Python's functions, classes, decorators, iterators, generators, and typing system provide mechanisms for expressing those concerns in a structured way.
