# JSON and Data Serialization

## 1. Topic Introduction

JSON, or JavaScript Object Notation, is a text-based data interchange format used to represent structured data. It is widely used for HTTP APIs, configuration files, application state, event messages, structured logs, data exchange, and persistence.

JSON is intentionally smaller in scope than a programming language's native object model. Its standard data model consists of objects, arrays, strings, numbers, booleans, and null.

This distinction is important when JSON is used to serialize application data. A Python program can represent concepts such as tuples, sets, dates, decimal numbers, byte sequences, enumerations, and class instances that do not have direct native JSON equivalents. Serialization therefore requires an explicit understanding of what information is preserved and what information is transformed or lost.

The accompanying Python script progresses from basic JSON syntax through serialization and deserialization, validation, custom encoding, numeric precision, Unicode, APIs, security, performance, testing, compatibility, and a complete order-serialization example.

---

## 2. JSON Data Model

JSON has six fundamental value categories.

| JSON concept | Example | Typical Python representation |
|---|---|---|
| Object | `{"name": "Alice"}` | `dict` |
| Array | `[1, 2, 3]` | `list` |
| String | `"hello"` | `str` |
| Number | `42`, `3.14` | `int`, `float` |
| Boolean | `true`, `false` | `True`, `False` |
| Null | `null` | `None` |

An object contains name/value pairs. An array contains an ordered sequence of values. Values can themselves be objects or arrays, allowing arbitrarily structured documents subject to implementation and resource limits.

A JSON document can therefore represent structures such as:

    {
      "employee": {
        "id": 101,
        "name": "Asha",
        "skills": ["Python", "SQL"],
        "address": {
          "city": "Lucknow",
          "country": "India"
        }
      }
    }

The important point is that JSON describes data rather than executable behavior.

---

## 3. JSON Syntax

### Objects

An object is enclosed in curly braces and contains key/value pairs:

    {"name": "Alice", "age": 30}

JSON object names are strings and therefore use double quotes.

### Arrays

An array is enclosed in square brackets:

    ["Python", "SQL", "JSON"]

Arrays preserve ordering.

### Strings

JSON strings use double quotes:

    "hello"

Special characters must be escaped when necessary. Common escapes include:

- `\"` for a quotation mark
- `\\` for a backslash
- `\n` for a newline
- `\r` for carriage return
- `\t` for a tab
- `\b` for backspace
- `\f` for form feed
- Unicode escape sequences such as `\uXXXX`

### Booleans

JSON uses lowercase:

    true
    false

Python instead uses:

    True
    False

### Null

JSON represents the absence of a value with:

    null

Python represents this concept with:

    None

### Numbers

JSON numbers can represent integers and fractional or exponential forms, subject to the format's grammar and the receiving implementation's numeric capabilities.

Examples include:

    0
    42
    -17
    3.14159
    1.2e3
    -2.5e-4

---

## 4. JSON Syntax Rules

Important rules demonstrated by the script include:

1. JSON strings use double quotes.
2. Object keys are strings.
3. Objects use `{` and `}`.
4. Arrays use `[` and `]`.
5. Members are separated with commas.
6. Key/value pairs use a colon.
7. JSON uses `true`, `false`, and `null`.
8. Standard JSON does not define comments.
9. Standard JSON does not allow trailing commas.
10. Control characters inside strings must be escaped.

Python's JSON parser raises `json.JSONDecodeError` when it encounters invalid JSON syntax.

The exception exposes useful information such as the error message, line, column, and character position.

---

## 5. Serialization

Serialization converts an in-memory representation into a representation suitable for storage or transmission.

The basic flow is:

    Python object
        |
        | serialization
        v
    JSON text
        |
        | network / file / database / message queue
        v
    JSON text
        |
        | deserialization
        v
    Python object

In Python, the primary JSON serialization functions are:

- `json.dumps()` converts a Python value to a JSON string.
- `json.dump()` writes a Python value directly to a file-like object.

Example:

    data = {"name": "Alice", "age": 30}
    text = json.dumps(data)

The result of `dumps()` is a Python string containing JSON text.

---

## 6. Deserialization

Deserialization performs the reverse conceptual operation.

Python provides:

- `json.loads()` for JSON text.
- `json.load()` for a file-like object containing JSON.

Example:

    text = '{"name": "Alice", "age": 30}'
    data = json.loads(text)

The resulting Python value is a dictionary.

Serialization and deserialization are often called encoding and decoding in the context of JSON.

---

## 7. Python-to-JSON Type Mapping

The standard Python JSON encoder naturally handles several common Python types.

Typical mappings are:

- `dict` → JSON object
- `list` → JSON array
- `tuple` → JSON array
- `str` → JSON string
- `int` → JSON number
- `float` → JSON number
- `True` → JSON `true`
- `False` → JSON `false`
- `None` → JSON `null`

The tuple mapping demonstrates an important limitation.

A Python tuple and list are distinct types:

    (1, 2, 3)
    [1, 2, 3]

When serialized as JSON, both can become:

    [1, 2, 3]

After deserialization, the JSON array becomes a Python list. Type identity has therefore been lost.

---

## 8. JSON Objects and Duplicate Keys

JSON objects are conceptually collections of name/value pairs.

An ambiguous document can contain duplicate names:

    {"role": "user", "role": "admin"}

Applications should not rely on duplicate-key behavior.

Python's standard JSON parser normally retains the last occurrence:

    {"role": "admin"}

The script also demonstrates `object_pairs_hook`, which can be used to inspect object members as ordered pairs and detect duplicate names.

Duplicate-key handling is especially important when multiple systems process the same document. If two parsers interpret duplicate fields differently, the producer and consumer can disagree about the meaning of the data.

Where duplicate keys would create security or correctness risks, an application should define and enforce an explicit policy.

---

## 9. Serialization Is Not Validation

One of the most important distinctions in JSON engineering is the difference between serialization and validation.

Serialization asks:

> Can this value be represented in JSON?

Validation asks:

> Does this data conform to the application's requirements?

For example:

    {"age": "thirty"}

is valid JSON.

It may still be invalid for an API whose contract requires `age` to be an integer.

Likewise:

    {
      "username": "",
      "age": -500,
      "email": "not-an-email"
    }

is valid JSON even though a particular application may reject every field.

JSON syntax validation is therefore only the first layer of validation.

---

## 10. Application-Level Validation

Application validation can check:

- Required fields
- Field types
- Numeric ranges
- String lengths
- Allowed values
- Array contents
- Nullability
- Relationships between fields
- Business rules

The script implements validators for user and product payloads using only the Python standard library.

A typical validation process is:

    JSON text
       |
       v
    Parse JSON
       |
       v
    Check root type
       |
       v
    Check required fields
       |
       v
    Check individual types
       |
       v
    Check ranges and business constraints
       |
       v
    Accept or reject

A parser should not be treated as a substitute for validation.

---

## 11. Schema Concepts

A schema formalizes the expected structure of JSON.

Common schema concepts include:

### `type`

Defines the expected JSON type.

Examples include:

- object
- array
- string
- number
- integer
- boolean
- null

### `properties`

Defines the fields of an object.

### `required`

Specifies fields that must be present.

### `items`

Defines the expected structure of array elements.

### `enum`

Restricts a value to a defined set of values.

### Numeric constraints

Examples include minimum and maximum values.

### String constraints

Examples include minimum length, maximum length, and pattern restrictions.

### `additionalProperties`

Controls whether properties outside the explicitly defined set are allowed.

A schema is a contract between producers and consumers. It is particularly useful for APIs and data pipelines because it makes assumptions explicit.

---

## 12. `null` Versus a Missing Field

These two JSON documents are not necessarily equivalent:

    {"nickname": null}

and:

    {}

The first explicitly contains a `nickname` field whose value is null.

The second does not contain the field at all.

This distinction matters in partial updates and APIs.

For example:

- Missing field could mean "leave the existing value unchanged."
- Null could mean "explicitly clear the existing value."

The correct interpretation is an API contract decision.

---

## 13. Custom Serialization

JSON has no built-in representation for many Python objects.

Examples include:

- `datetime`
- `date`
- `Decimal`
- `set`
- `bytes`
- custom classes
- many enumeration types

Python's `json.dumps()` provides the `default` parameter for custom conversion.

The script demonstrates an encoder that converts:

- `Employee` into a dictionary
- `set` into a sorted array
- `datetime` and `date` into ISO-formatted strings
- `Decimal` into strings
- UUID-like values into strings
- bytes into explicitly tagged Base64 objects

The design principle is explicit conversion.

A custom serializer should define how the source object's semantics map into the JSON data model rather than silently discarding important information.

---

## 14. Custom Deserialization

Serialization alone is not sufficient when an application needs to reconstruct rich domain objects.

A custom decoder can inspect parsed dictionaries and transform explicitly tagged representations.

The script uses a structure such as:

    {
      "__type__": "bytes",
      "encoding": "base64",
      "value": "..."
    }

The decoder recognizes this specific representation and reconstructs bytes.

A critical security rule is demonstrated in the implementation:

> Never reconstruct arbitrary classes from attacker-controlled type names.

An unsafe deserializer could allow external input to influence object construction or execution behavior.

Safe custom deserialization should use a small allowlist of known representations.

---

## 15. Dates and Times

JSON has no native date or timestamp type.

Dates and timestamps are commonly represented as strings.

ISO 8601 is a widely used representation, for example:

    2026-09-09T12:30:00+00:00

Python can generate this representation with:

    datetime.isoformat()

and parse it with:

    datetime.fromisoformat()

For event timestamps, timezone-aware timestamps are generally preferable because they identify an actual instant rather than relying on an unspecified local timezone.

An API contract should explicitly document:

- Timestamp format
- Timezone expectations
- Whether offsets are required
- Whether fractional seconds are supported
- Whether date-only values are permitted

---

## 16. Numbers and Floating-Point Precision

JSON's number syntax does not guarantee that every implementation represents numbers identically.

Different programming languages and runtimes can have different:

- Integer limits
- Floating-point implementations
- Precision behavior
- Overflow behavior

A well-known example is:

    0.1 + 0.2

in binary floating-point arithmetic. It does not necessarily produce exactly the mathematical value `0.3`.

The script demonstrates `math.isclose()` as a better approach for many floating-point comparisons.

For financial or other decimal-sensitive calculations, the data model should explicitly define how decimal values are represented.

---

## 17. NaN and Infinity

IEEE-754 floating-point systems support values such as:

- NaN
- Positive Infinity
- Negative Infinity

Strict JSON does not define these as ordinary JSON numbers.

Python's JSON implementation can emit non-standard representations by default in some situations, but:

    json.dumps(value, allow_nan=False)

can be used to enforce strict behavior and reject such values.

Interoperable systems should avoid assuming that non-standard numeric constants will be understood by other JSON implementations.

---

## 18. Decimal Values

Python's `Decimal` type is not directly JSON serializable.

A common mistake is to convert financial decimals to binary floating-point values without considering precision.

The script demonstrates two representations:

    {"amount": 10.1}

and:

    {"amount": "10.10"}

The string representation preserves the decimal textual form.

Another common strategy for money is to store an integer number of the smallest currency unit, such as paise or cents, when appropriate for the domain.

The correct approach depends on the API contract and financial requirements.

---

## 19. Parsing Numbers as `Decimal`

Python's decoder allows custom numeric parsing.

For example:

    json.loads(text, parse_float=Decimal)

causes floating-point JSON numbers to be parsed as `Decimal` instead of Python `float`.

This can be useful when exact decimal semantics are more important than native floating-point convenience.

The producer and consumer should still agree on the intended numeric semantics.

---

## 20. Encoding Options

Important `json.dumps()` options include:

### `indent`

Produces readable formatted JSON.

Useful for:

- Configuration files
- Debugging
- Human review
- Documentation

### `sort_keys`

Sorts dictionary keys.

Useful for:

- Deterministic output
- Snapshot testing
- Reproducible artifacts

### `ensure_ascii`

Controls whether non-ASCII characters are escaped.

Using:

    ensure_ascii=False

makes Unicode characters directly visible in the resulting string.

### `separators`

Can reduce unnecessary whitespace:

    separators=(",", ":")

This is useful when compactness matters.

### `allow_nan`

Controls Python's handling of NaN and infinity.

### `default`

Provides custom conversion logic for unsupported Python objects.

---

## 21. Loading Options

`json.loads()` provides several useful hooks.

### `parse_int`

Controls how JSON integers are converted.

### `parse_float`

Controls how JSON floating-point values are converted.

### `parse_constant`

Handles special constants accepted by Python's decoder that are outside strict JSON.

### `object_hook`

Receives parsed objects and can transform them.

### `object_pairs_hook`

Receives object members as pairs and is useful when member ordering or duplicate-key detection matters.

---

## 22. Unicode and Character Encoding

JSON supports Unicode text.

The script demonstrates English, Hindi, Japanese, and emoji data.

Two outputs can be produced:

- ASCII-escaped JSON
- JSON containing the Unicode characters directly

For example, with `ensure_ascii=False`, a value such as Hindi text can remain readable in the JSON document.

For files and network boundaries, UTF-8 is the usual encoding choice.

Python file operations should specify the encoding explicitly when deterministic behavior is important:

    open(..., encoding="utf-8")

or the equivalent `Path` methods.

---

## 23. JSON Object Keys

JSON object keys are strings.

Python dictionaries are more flexible and can use other hashable objects as keys.

Consequently, serialization can transform keys.

For example:

    {1: "value"}

can become an object whose key is represented textually.

This is an example of why a successful serialization round trip does not necessarily preserve every aspect of the original Python data structure.

There is an even earlier issue in Python itself:

    1 == True

is true, and both can therefore collide as dictionary keys.

Serialization cannot recover information that was already lost while constructing the Python dictionary.

---

## 24. String Escaping

JSON strings use escaping to represent characters that have structural significance or cannot appear literally in particular contexts.

The script demonstrates:

- Quotes
- Backslashes
- Newlines
- Tabs

The JSON encoder should normally be responsible for producing correct escaping rather than constructing JSON manually through string concatenation.

Manual construction can easily introduce:

- Missing escapes
- Invalid syntax
- Injection vulnerabilities
- Incorrect Unicode handling
- Broken quotes

Use a JSON serializer for JSON generation.

---

## 25. Deterministic JSON

Deterministic serialization is useful when the same logical structure should produce stable text.

A common configuration is:

    json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    )

This is useful for:

- Snapshot tests
- Reproducible files
- Stable comparisons
- Change detection

Stable `json.dumps()` output should not automatically be treated as a universal cryptographic canonicalization scheme. Cryptographic workflows require precisely specified canonicalization rules.

---

## 26. Round-Trip Serialization

A round trip means:

    Python object
        ->
    JSON
        ->
    Python object

For naturally JSON-compatible structures, a simple round trip can preserve equality:

    restored = json.loads(json.dumps(original))

The script tests this behavior.

A round trip should not automatically be interpreted as proof of complete type preservation.

For example:

    tuple -> JSON array -> list

The values may look equivalent while the Python types are different.

---

## 27. JSON Files

JSON is frequently used for:

- Application configuration
- Static metadata
- Export files
- Small datasets
- Test fixtures

Python provides both string-based and file-based APIs.

For example, conceptually:

    json.dump(data, file)

writes directly to a file, while:

    json.dumps(data)

first creates a string.

When reading files, explicit UTF-8 handling is useful:

    Path("config.json").read_text(encoding="utf-8")

---

## 28. JSON Lines / NDJSON

JSON Lines, commonly called NDJSON in some environments, stores one JSON value per line.

Example:

    {"event":"login","user_id":1}
    {"event":"purchase","user_id":2}
    {"event":"logout","user_id":1}

Each line is independently parsed.

This is useful for:

- Application logs
- Event streams
- Large datasets
- Batch processing
- Append-oriented storage

A JSON Lines file is not the same thing as a single JSON array.

A large standard JSON array generally requires the whole document to be parsed as one logical structure, while JSON Lines naturally supports record-by-record processing.

---

## 29. Large Documents and Streaming

The standard `json.loads()` approach normally materializes the parsed result in memory.

For very large documents, this can create substantial memory consumption.

Potential solutions include:

- JSON Lines
- Pagination
- Chunked APIs
- Incremental parsing
- Streaming parsers
- Server-side filtering
- Database queries that return only required records

The standard library's JSON implementation is convenient but is not a general-purpose incremental parser for arbitrary huge JSON streams.

Data architecture should therefore consider document size before choosing one large JSON document as the transport model.

---

## 30. Binary Data

JSON does not contain a native binary byte-string type.

When binary data must be embedded in JSON, Base64 is a common representation.

The process is:

    binary bytes
        ->
    Base64
        ->
    text
        ->
    JSON

Base64 increases the size of the data compared with the original binary representation.

For large binary objects, it can be preferable to store or transfer the binary separately and place a reference or identifier in the JSON document.

---

## 31. Enumerations

Python enumerations do not automatically correspond to a unique JSON type.

A common API representation is the enum's stable string value:

    {"status": "approved"}

The consumer can then map the value back to an enum.

Using stable semantic values is often preferable to exposing internal numeric enum positions, because numeric positions can change when the source code evolves.

---

## 32. Dataclasses

Python dataclasses provide structured domain objects but are not themselves JSON data types.

The script demonstrates:

    dataclasses.asdict()

to convert nested dataclass instances into dictionaries.

After conversion, the result can be serialized normally.

For deserialization, explicit reconstruction is often preferable because it gives the application a place to validate the input before constructing a trusted domain object.

---

## 33. JSON in Web APIs

JSON is particularly common in HTTP request and response bodies.

A response may contain:

    {
      "data": {
        "id": 7,
        "name": "Priya",
        "roles": ["user", "analyst"]
      },
      "meta": {
        "version": "1"
      }
    }

A production API should define:

- Request structure
- Response structure
- Required fields
- Optional fields
- Nullable fields
- Field types
- Numeric semantics
- Timestamp format
- Error structure
- Versioning behavior
- Unknown-field policy
- Size limits

JSON serialization does not provide authentication, authorization, encryption, or transport security. Those are separate system concerns.

---

## 34. Structured Error Responses

Machine-readable errors are easier to process when they contain stable codes.

For example:

    {
      "error": {
        "code": "INVALID_ARGUMENT",
        "message": "The age field must be an integer.",
        "field": "age"
      }
    }

The stable `code` can be used by software while `message` can be presented to humans.

Error contracts should avoid forcing clients to parse natural-language messages to determine program behavior.

---

## 35. Security: JSON Is Data, Not Code

JSON itself does not execute commands.

The script demonstrates parsing a string such as:

    {"command": "rm -rf /"}

with `json.loads()`. Parsing produces ordinary data.

The security risk appears when application code takes parsed data and passes it to another system unsafely.

Never use:

    eval()

as a JSON parser.

Never treat JSON as executable Python, JavaScript, shell commands, SQL, or another language.

Correct practice is:

1. Parse the JSON.
2. Validate its structure.
3. Validate its values.
4. Apply authorization rules.
5. Pass values to downstream operations using safe APIs.

---

## 36. Unsafe Object Reconstruction

A particularly important deserialization concern is arbitrary object reconstruction.

An unsafe design might allow a JSON field to name an arbitrary class and then attempt to instantiate that class dynamically.

This is dangerous because untrusted input could influence application behavior beyond the intended data model.

A safer approach is an explicit allowlist:

- Recognize only known tags.
- Validate the expected fields.
- Reject unknown types.
- Construct only explicitly supported domain objects.

The script's `custom_object_hook` follows this constrained approach.

---

## 37. Resource Exhaustion

A JSON document can be valid and still be dangerous to process.

Examples include:

- Extremely large arrays
- Extremely long strings
- Deeply nested structures
- Very large request bodies
- Huge numeric values
- Large numbers of object members

Production systems should establish appropriate limits for:

- Request body size
- Array length
- String length
- Object member count
- Nesting depth
- Processing time
- Memory consumption

These controls help prevent resource-exhaustion attacks and accidental overload.

---

## 38. Sensitive Data and Logging

JSON is frequently used for structured logging.

This is useful because fields can be indexed and queried individually.

A log event might contain:

    {
      "timestamp": "...",
      "level": "INFO",
      "event": "user_login",
      "user_id": 123,
      "success": true
    }

Structured logs should not contain unnecessary secrets.

Avoid logging:

- Passwords
- Authentication tokens
- Session cookies
- Private keys
- Unnecessary personal information
- Sensitive request headers

JSON makes data easy to structure, but it does not make sensitive data safe to store.

---

## 39. Performance Considerations

JSON performance depends on:

- Payload size
- Object count
- Array count
- Nesting depth
- String length
- Number of fields
- Encoder/decoder implementation
- CPU availability
- Memory availability
- Network bandwidth

Serialization performance should not be evaluated in isolation.

For an HTTP service, total latency can involve:

    serialization
    + compression
    + network transmission
    + parsing
    + application processing

A faster serializer may not improve total system performance if the primary bottleneck is network transfer or downstream computation.

---

## 40. Payload Size

JSON can be verbose because object property names are repeated.

Compact serialization can remove unnecessary whitespace:

    separators=(",", ":")

Compression can reduce the transmitted size substantially when data contains repeated structures or strings.

The script demonstrates gzip compression.

Compression itself has CPU costs, so production systems should consider:

- Payload size
- Compression ratio
- CPU cost
- Latency
- Client compatibility
- Whether the underlying data is already compressed

---

## 41. JSON Versus CSV

JSON is generally better for hierarchical or heterogeneous data.

CSV is particularly suitable for simple rectangular tables.

### JSON strengths

- Nested objects
- Arrays
- Explicit property names
- Multiple data types
- Natural API representation
- Heterogeneous structures

### JSON weaknesses

- More verbose
- Potentially higher parsing overhead
- Can require substantial memory for large documents

### CSV strengths

- Simple tabular format
- Compact for flat data
- Easy to use with spreadsheets

### CSV weaknesses

- Poor native representation for nested structures
- Limited type information
- Different escaping and dialect conventions

Neither format is universally better. The data shape and use case determine the appropriate representation.

---

## 42. JSON Versus Binary Serialization

The script compares JSON with several other formats.

### JSON

Human-readable, highly interoperable, text-based, and flexible.

### XML

Text-based and expressive, with features such as namespaces, but generally more verbose.

### CSV

Simple and efficient for flat tabular data.

### MessagePack

Binary and designed around a JSON-like data model.

### Protocol Buffers

Schema-driven binary serialization designed for compactness, performance, and strongly defined contracts.

### CBOR

A binary format based on a JSON-like data model with additional type capabilities.

The format should be selected based on:

- Interoperability
- Human readability
- Payload size
- Performance
- Schema requirements
- Compatibility requirements
- Data types
- Tooling
- Operational constraints

---

## 43. Schema Evolution

Data contracts evolve.

A producer may eventually add a new field:

    {
      "id": 1,
      "name": "Alice",
      "department": "Engineering"
    }

If consumers are designed to ignore unknown fields, adding optional information can be relatively safe.

Potentially breaking changes include:

- Renaming a field
- Removing a field
- Changing a field's type
- Changing an enum value
- Making an optional field required
- Changing nullability
- Changing the semantic meaning of an existing value

Backward and forward compatibility must therefore be designed rather than assumed.

---

## 44. Unknown Fields

An API needs an explicit policy for unknown fields.

Two broad strategies are:

### Ignore unknown fields

Useful when clients and servers need loose compatibility.

### Reject unknown fields

Useful when strict contracts are required and accidental fields should be detected immediately.

Neither policy is universally correct.

The important requirement is consistency and documentation.

---

## 45. JSON Limitations

JSON's simplicity creates several important limitations.

### Limited native type system

JSON does not directly represent:

- Dates
- Times
- Decimal types
- Sets
- Tuples
- Bytes
- Enums
- Arbitrary classes

These require conventions.

### Numeric interoperability

Different systems can have different numeric limits and precision.

### No comments

Standard JSON does not define a comment syntax.

### No schema enforcement

JSON syntax does not automatically validate business rules.

### No security properties

JSON provides no encryption, authentication, or authorization.

### No compression

Compression is a separate concern.

### Potential verbosity

Repeated property names can create significant overhead.

### Large-document memory consumption

Whole-document parsing can become expensive for very large inputs.

### Ambiguity without contracts

Nullability, duplicate keys, numeric precision, unknown fields, and timestamp interpretation require explicit agreements.

---

## 46. Common Mistakes

### Mistake 1: Using single quotes

This:

    {'name': 'Alice'}

is Python-style syntax, not standard JSON.

### Mistake 2: Using Python boolean names

JSON uses:

    true
    false

not:

    True
    False

### Mistake 3: Using `None`

JSON uses:

    null

### Mistake 4: Adding trailing commas

Standard JSON does not permit a trailing comma after the final member or array item.

### Mistake 5: Using comments

Comments are not part of standard JSON.

### Mistake 6: Constructing JSON manually

String concatenation is error-prone and can create escaping or injection problems.

Use a serializer.

### Mistake 7: Treating parsing as validation

Valid JSON can still violate application requirements.

### Mistake 8: Using `eval()`

JSON should be parsed as data.

### Mistake 9: Ignoring numeric precision

Numbers can have different representations and limits across systems.

### Mistake 10: Assuming round-trip type preservation

Tuples can become arrays and therefore lists after decoding.

### Mistake 11: Ignoring null versus missing

These states may have different business meanings.

### Mistake 12: Ignoring large-input risks

Valid JSON can still consume excessive memory or processing time.

---

## 47. Testing JSON Systems

A robust JSON implementation should test more than successful examples.

Important test categories include:

### Valid documents

- Empty objects
- Empty arrays
- Nested structures
- Unicode
- Numbers
- Booleans
- Null

### Invalid documents

- Missing quotes
- Invalid commas
- Invalid values
- Broken escaping
- Unexpected end of input

### Boundary values

- Zero
- Negative numbers
- Very large numbers
- Empty strings
- Maximum allowed strings
- Empty arrays
- Maximum allowed arrays

### Semantic validation

- Missing required fields
- Wrong types
- Invalid ranges
- Invalid enum values
- Invalid timestamps

### Compatibility

- Older payloads
- Newer payloads
- Unknown fields
- Nullable fields

### Security

- Oversized payloads
- Deep nesting
- Duplicate fields
- Malformed Base64
- Unexpected type tags

The script contains basic assertions for round-trip behavior, malformed JSON, and product validation.

---

## 48. Production Design Pattern

The integrated order example demonstrates a strong general pattern:

    Domain object
          |
          v
    Explicit JSON-compatible representation
          |
          v
    Serialization
          |
          v
    Storage / transport
          |
          v
    Deserialization
          |
          v
    Validation
          |
          v
    Domain object

This design makes the serialization boundary explicit.

For an order, the domain object contains Python `Decimal` and `datetime` values. The JSON representation converts those values into representations defined by the data contract.

The deserializer then validates the structure before constructing the domain object.

This is safer and easier to maintain than relying on implicit conversions of arbitrary objects.

---

## 49. Monetary Data

The order example uses:

    Decimal("1499.95")

rather than binary floating-point values for monetary calculations.

The serialized representation uses a string for the decimal amount.

The reason is that JSON has no native decimal type, while floating-point values may introduce binary representation issues.

The correct financial representation should be determined by the application's contract, but the key principle is to define monetary precision explicitly.

---

## 50. Timestamp Contracts

The order example stores its creation timestamp using ISO-formatted text.

The important considerations are:

- The timestamp represents an instant.
- Timezone information is retained.
- The consumer knows how to parse the representation.
- Invalid timestamps are rejected.

A production contract should not leave timestamp semantics ambiguous.

---

## 51. API Contract Design

A reliable JSON API should specify:

### Structure

What is the root object or array?

### Required fields

Which properties must exist?

### Optional fields

Which properties may be omitted?

### Nullability

Can a field explicitly contain `null`?

### Types

What JSON type is expected?

### Ranges

What numeric and string limits apply?

### Enumerations

Which values are valid?

### Unknown properties

Should extra fields be accepted or rejected?

### Versioning

How can the contract evolve without breaking consumers?

### Errors

How are validation and application errors represented?

### Limits

How large can requests and responses become?

### Security

What authentication, authorization, transport security, and logging rules apply?

JSON handles representation. The surrounding API architecture handles the rest.

---

## 52. Serialization and Interoperability

JSON's major advantage is broad interoperability.

A producer can be implemented in Python while consumers can be implemented in:

- Java
- JavaScript
- Go
- Rust
- C#
- Java
- PHP
- Ruby
- Kotlin
- Swift
- Other environments

The advantage depends on the producer and consumer agreeing on semantics.

A JSON document can be syntactically valid while still being incompatible because of differences in:

- Number ranges
- Decimal precision
- Date formats
- Enum values
- Null handling
- Required fields
- Duplicate keys
- Unknown properties

Interoperability therefore requires both a common syntax and a common contract.

---

## 53. Implementation Best Practices

1. Use `json.dumps()` or `json.dump()` for serialization.
2. Use `json.loads()` or `json.load()` for parsing.
3. Catch `json.JSONDecodeError` when processing untrusted JSON.
4. Validate semantic requirements after parsing.
5. Define schemas for important external contracts.
6. Use explicit conversion for unsupported domain types.
7. Use timezone-aware timestamps when representing instants.
8. Define monetary precision explicitly.
9. Set input size and resource limits.
10. Treat JSON as untrusted input at external boundaries.
11. Never use `eval()` as a JSON parser.
12. Avoid arbitrary object reconstruction.
13. Define nullability and missing-field behavior.
14. Define duplicate-key policy when ambiguity matters.
15. Test malformed and adversarial input.
16. Use compact serialization when bandwidth matters.
17. Consider compression for large textual payloads.
18. Prefer streaming or pagination for very large datasets.
19. Use deterministic serialization where reproducibility matters.
20. Select another serialization format when JSON's limitations become operationally significant.

---

## 54. Practical Applications

JSON is suitable for many real-world scenarios.

### REST and HTTP APIs

Requests and responses commonly use JSON because it is easy for clients and servers to exchange.

### Configuration

Applications can store settings in JSON files when the configuration structure is appropriately simple and the operational requirements fit the format.

### Structured logging

JSON allows logging systems to index and query individual fields.

### Event-driven systems

Events can use JSON payloads when interoperability and human readability are important.

### Data pipelines

JSON and JSON Lines can represent records flowing between services and processing systems.

### Browser and frontend applications

JSON is a common boundary between frontend applications and backend services.

### Export and import

Applications can use JSON as a portable representation of structured data.

---

## 55. When JSON Is a Poor Fit

JSON may not be ideal when:

- Extremely compact binary representation is required.
- Very high throughput is critical.
- Strong schema enforcement is required at the serialization layer.
- Large binary data is a primary payload.
- Specialized numeric or temporal types are essential.
- Very large datasets must be incrementally processed without an appropriate streaming design.
- Bandwidth is extremely constrained.
- The system already uses an efficient schema-driven binary protocol.

The correct choice depends on the system rather than on JSON being inherently superior or inferior.

---

## 56. Core Distinctions

| Concept | Meaning |
|---|---|
| JSON | A data interchange format |
| Serialization | Converting an in-memory representation into a storable/transmittable representation |
| Deserialization | Reconstructing an in-memory representation from serialized data |
| Parsing | Interpreting serialized text according to its syntax |
| Validation | Checking whether parsed data satisfies required constraints |
| Schema | A formal description of expected structure and constraints |
| Encoding | Representing data in a particular serialized form |
| Decoding | Interpreting an encoded representation |
| JSON object | Collection of string-named values |
| JSON array | Ordered collection of JSON values |
| JSON primitive | String, number, boolean, or null |
| JSON Lines | One JSON value per line |

Understanding these distinctions prevents many implementation mistakes.

---

## 57. Python Functions Demonstrated

The script uses the following important standard-library JSON functions and mechanisms:

- `json.dumps()`
- `json.dump()`
- `json.loads()`
- `json.load()`
- `json.JSONDecodeError`
- `object_hook`
- `object_pairs_hook`
- `parse_float`
- `default`
- `allow_nan`
- `sort_keys`
- `ensure_ascii`
- `indent`
- `separators`

It also uses related standard-library facilities such as:

- `dataclasses`
- `datetime`
- `decimal`
- `base64`
- `pathlib`
- `math`
- `gzip`
- `time`

These demonstrate that JSON handling is not limited to calling one parser. Reliable serialization involves type conversion, validation, error handling, security controls, testing, and system-level design.

---

## 58. Edge Cases Covered by the Script

The Python script explicitly demonstrates:

- Empty objects
- Empty arrays
- Null
- Zero
- Negative numbers
- Exponential notation
- Unicode
- Escaped strings
- Duplicate object keys
- Python tuple to JSON array conversion
- Python sets
- Dictionary key conversion
- Python key collisions
- NaN
- Infinity
- Floating-point precision
- Decimal values
- Dates
- Timestamps
- Bytes
- Base64
- Enums
- Dataclasses
- Missing versus null fields
- Large-document considerations
- Deterministic serialization
- Invalid JSON
- Application-level validation
- Structured errors
- API payload design
- Schema evolution
- Resource exhaustion
- Security-sensitive deserialization

These cases illustrate why JSON programming requires more than understanding its basic braces and brackets.

---

## 59. Conceptual Model

The most useful way to reason about JSON serialization is to separate four layers:

### Layer 1: Data model

What information does the application actually need to represent?

### Layer 2: JSON representation

How are those concepts mapped into objects, arrays, strings, numbers, booleans, and null?

### Layer 3: Contract

What fields, types, constraints, and compatibility rules must producers and consumers follow?

### Layer 4: Operational boundary

How are the JSON documents transported, stored, validated, secured, monitored, compressed, and versioned?

A technically correct JSON implementation must account for all four layers when JSON crosses a real application boundary.
