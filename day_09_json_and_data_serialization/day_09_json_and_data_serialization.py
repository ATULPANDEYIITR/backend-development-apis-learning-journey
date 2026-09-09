"""
JSON AND DATA SERIALIZATION
===========================

A self-contained study script covering JSON syntax, objects, arrays, primitive
values, serialization, deserialization, JSON limitations, validation,
custom encoding/decoding, interoperability, edge cases, security, performance,
testing, and production-oriented practices.

Run:
    python json_and_serialization.py

The script uses only Python's standard library.
"""

from __future__ import annotations

import base64
import json
import math
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# ============================================================================

def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def explain_fundamentals() -> None:
    section("1. JSON FUNDAMENTALS")

    print(
        """
JSON stands for JavaScript Object Notation. It is a text-based data
interchange format. Despite its historical relationship with JavaScript,
JSON is language-independent and is commonly used by APIs, configuration
systems, databases, logs, message queues, and files.

JSON has six structural/value categories:

1. Object       -> collection of key/value pairs
2. Array        -> ordered collection of values
3. String       -> Unicode text
4. Number       -> integer or fractional numeric value
5. Boolean      -> true or false
6. Null         -> null

A JSON document must have one valid JSON value at its root. In modern JSON,
that root may be an object, array, string, number, boolean, or null.

Python has corresponding concepts, but the mappings are not perfectly
identical.
"""
    )

    python_to_json = {
        "Python dict": "JSON object",
        "Python list/tuple": "JSON array",
        "Python str": "JSON string",
        "Python int/float": "JSON number",
        "Python True/False": "JSON true/false",
        "Python None": "JSON null",
    }

    for python_type, json_type in python_to_json.items():
        print(f"{python_type:<24} -> {json_type}")


# ============================================================================
# 2. JSON SYNTAX
# ============================================================================

def demonstrate_json_syntax() -> None:
    section("2. JSON SYNTAX")

    subsection("2.1 JSON object")

    object_text = '{"name":"Atul","age":33,"active":true,"middle_name":null}'
    print("JSON:", object_text)
    print("Parsed:", json.loads(object_text))

    subsection("2.2 JSON array")

    array_text = '["Python", "SQL", "JSON", 2026, true, null]'
    print("JSON:", array_text)
    print("Parsed:", json.loads(array_text))

    subsection("2.3 Nested structures")

    nested_text = """
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
    """

    parsed = json.loads(nested_text)
    print(json.dumps(parsed, indent=2))

    subsection("2.4 Important syntax rules")

    rules = [
        "Object keys must be JSON strings.",
        "Double quotes are required for JSON strings.",
        "Objects use curly braces: { }.",
        "Arrays use square brackets: [ ].",
        "Object members use key:value syntax.",
        "Members are separated with commas.",
        "JSON uses true, false, and null in lowercase.",
        "Trailing commas are not valid standard JSON.",
        "Comments are not part of standard JSON.",
        "JSON whitespace is generally insignificant outside strings.",
    ]

    for number, rule in enumerate(rules, 1):
        print(f"{number}. {rule}")

    subsection("2.5 Invalid JSON examples")

    invalid_examples = [
        "{'name': 'Alice'}",                 # Single quotes.
        '{"name": "Alice",}',                # Trailing comma.
        '{name: "Alice"}',                   # Unquoted key.
        '{"active": True}',                 # Python boolean spelling.
        '{"value": NaN}',                   # Non-standard JSON numeric value.
        '{"text": "line\nbreak"}',          # Unescaped control character.
    ]

    for text in invalid_examples:
        try:
            json.loads(text)
            print("Unexpectedly accepted:", repr(text))
        except json.JSONDecodeError as exc:
            print(f"Rejected: {text!r}")
            print(f"  Error: {exc.msg} at line {exc.lineno}, column {exc.colno}")


# ============================================================================
# 3. PRIMITIVE VALUES
# ============================================================================

def demonstrate_primitives() -> None:
    section("3. JSON PRIMITIVE VALUES")

    values = [
        '"hello"',
        "42",
        "-17",
        "3.14159",
        "true",
        "false",
        "null",
    ]

    for text in values:
        value = json.loads(text)
        print(f"{text:<12} -> Python value={value!r}, type={type(value).__name__}")

    subsection("3.1 Strings and escaping")

    data = {
        "newline": "first line\nsecond line",
        "quote": 'She said "hello".',
        "backslash": r"C:\Users\Alice",
        "unicode": "भारत • 日本 • العربية • café",
        "emoji": "Python 🐍",
    }

    encoded = json.dumps(data, ensure_ascii=False, indent=2)
    print(encoded)

    subsection("3.2 Numbers")

    numeric_values = [0, 1, -1, 42, 3.14, 1e6, -2.5e-4]

    for value in numeric_values:
        text = json.dumps(value)
        parsed = json.loads(text)
        print(f"{value!r:>12} -> {text:<12} -> {parsed!r}")

    subsection("3.3 JSON null")

    parsed_null = json.loads("null")
    print("JSON null becomes Python:", parsed_null, type(parsed_null).__name__)


# ============================================================================
# 4. PYTHON TO JSON MAPPING
# ============================================================================

def demonstrate_python_json_mapping() -> None:
    section("4. PYTHON VALUES AND JSON VALUES")

    values = {
        "dictionary": {"a": 1, "b": 2},
        "list": [1, 2, 3],
        "tuple": (1, 2, 3),
        "string": "hello",
        "integer": 100,
        "float": 3.5,
        "boolean": True,
        "none": None,
    }

    for name, value in values.items():
        serialized = json.dumps(value)
        restored = json.loads(serialized)
        print(
            f"{name:<12} Python={value!r:<25} "
            f"JSON={serialized:<25} restored={restored!r}"
        )

    print(
        """
Important distinction:
A tuple is not a native JSON type. Python's json module serializes a tuple
as a JSON array, so the tuple/list distinction is lost during serialization.
"""
    )


# ============================================================================
# 5. SERIALIZATION
# ============================================================================

def demonstrate_serialization() -> None:
    section("5. SERIALIZATION")

    print(
        """
Serialization converts an in-memory data structure into a representation
that can be stored or transmitted.

Python object
      |
      | json.dumps()
      v
JSON text
      |
      | network/file/database
      v
JSON text
      |
      | json.loads()
      v
Python object

The term "serialization" is broader than JSON. JSON is one serialization
format. Other formats include XML, CSV, MessagePack, Protocol Buffers,
CBOR, and language-specific binary formats.
"""
    )

    user = {
        "id": 1001,
        "name": "Ravi",
        "roles": ["analyst", "manager"],
        "active": True,
    }

    compact = json.dumps(user)
    pretty = json.dumps(user, indent=2)
    deterministic = json.dumps(user, sort_keys=True)

    print("Compact:")
    print(compact)

    print("\nPretty:")
    print(pretty)

    print("\nSorted keys:")
    print(deterministic)


# ============================================================================
# 6. dumps VS dump
# ============================================================================

def demonstrate_dump_variants() -> None:
    section("6. json.dumps() VS json.dump()")

    data = {
        "application": "serialization-demo",
        "version": 1,
        "items": ["a", "b", "c"],
    }

    json_text = json.dumps(data)
    print("dumps() returns a string:")
    print(repr(json_text))

    output_path = Path("json_demo_output.json")

    try:
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        print("\ndump() writes directly to a file:")
        print(output_path.read_text(encoding="utf-8"))
    finally:
        if output_path.exists():
            output_path.unlink()


# ============================================================================
# 7. DESERIALIZATION
# ============================================================================

def demonstrate_deserialization() -> None:
    section("7. DESERIALIZATION")

    json_document = """
    {
        "id": 500,
        "name": "Meera",
        "score": 97.5,
        "verified": true,
        "tags": ["python", "json"],
        "manager": null
    }
    """

    data = json.loads(json_document)

    print("Root type:", type(data).__name__)
    print("ID:", data["id"])
    print("Name:", data["name"])
    print("First tag:", data["tags"][0])
    print("Manager:", data["manager"])


# ============================================================================
# 8. SAFE PARSING AND VALIDATION
# ============================================================================

def parse_json_safely(text: str) -> Any | None:
    """Parse JSON while converting syntax errors into a controlled result."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"Invalid JSON: {exc.msg}; "
            f"line={exc.lineno}, column={exc.colno}, position={exc.pos}"
        )
        return None


def demonstrate_validation() -> None:
    section("8. PARSING, VALIDATION, AND ERROR HANDLING")

    valid = '{"name": "Alice", "age": 30}'
    invalid = '{"name": "Alice", "age": }'

    print("Valid input:")
    print(parse_json_safely(valid))

    print("\nInvalid input:")
    print(parse_json_safely(invalid))

    print(
        """
Syntax validation and semantic validation are different.

Syntax validation asks:
    "Is this valid JSON?"

Semantic validation asks:
    "Does the JSON have the structure and values my application requires?"

For example, this is valid JSON:
    {"age": "thirty"}

But it may violate an application's rule that age must be an integer.
"""
    )


# ============================================================================
# 9. STRUCTURAL VALIDATION WITHOUT THIRD-PARTY PACKAGES
# ============================================================================

def validate_user_payload(payload: Any) -> tuple[bool, list[str]]:
    """Perform simple application-level validation."""
    errors: list[str] = []

    if not isinstance(payload, dict):
        return False, ["Root value must be a JSON object."]

    required_fields = {"id", "name", "age", "roles"}

    missing = required_fields - payload.keys()
    for field in sorted(missing):
        errors.append(f"Missing required field: {field}")

    if "id" in payload and not isinstance(payload["id"], int):
        errors.append("'id' must be an integer.")

    if "name" in payload and not isinstance(payload["name"], str):
        errors.append("'name' must be a string.")

    if "age" in payload:
        if not isinstance(payload["age"], int) or isinstance(payload["age"], bool):
            errors.append("'age' must be an integer.")
        elif not 0 <= payload["age"] <= 150:
            errors.append("'age' must be between 0 and 150.")

    if "roles" in payload:
        if not isinstance(payload["roles"], list):
            errors.append("'roles' must be an array.")
        elif not all(isinstance(role, str) for role in payload["roles"]):
            errors.append("Every role must be a string.")

    return not errors, errors


def demonstrate_application_validation() -> None:
    section("9. APPLICATION-LEVEL JSON VALIDATION")

    examples = [
        {
            "id": 1,
            "name": "Asha",
            "age": 29,
            "roles": ["admin"],
        },
        {
            "id": "1",
            "name": "Asha",
            "age": 29,
            "roles": ["admin"],
        },
        {
            "id": 2,
            "name": "Bob",
            "age": 220,
            "roles": [],
        },
        {
            "id": 3,
            "name": "Cara",
            "age": 30,
            "roles": [123],
        },
    ]

    for payload in examples:
        valid, errors = validate_user_payload(payload)
        print("\nPayload:", payload)
        print("Valid:", valid)
        if errors:
            for error in errors:
                print(" -", error)


# ============================================================================
# 10. JSON OBJECT SEMANTICS
# ============================================================================

def demonstrate_object_behavior() -> None:
    section("10. JSON OBJECTS: IMPORTANT SEMANTICS")

    print(
        """
JSON objects are conceptually collections of name/value pairs.

Typical application assumptions:
    {"id": 1, "name": "Alice"}

Important issue: duplicate object names.

The JSON specification does not give portable application semantics to
duplicate names. Different parsers may handle them differently. Python's
standard json parser keeps the last value by default.
"""
    )

    duplicate = '{"role":"user","role":"admin"}'
    parsed = json.loads(duplicate)

    print("Input:", duplicate)
    print("Python result:", parsed)

    subsection("Detecting duplicate keys")

    duplicates: list[str] = []

    def detect_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, value in pairs:
            if key in result:
                duplicates.append(key)
            result[key] = value

        return result

    parsed = json.loads(duplicate, object_pairs_hook=detect_duplicates)

    print("Parsed:", parsed)
    print("Duplicate keys detected:", duplicates)


# ============================================================================
# 11. ORDER, IDENTITY, AND TYPE INFORMATION
# ============================================================================

def demonstrate_information_loss() -> None:
    section("11. INFORMATION LOSS DURING JSON SERIALIZATION")

    original = {
        "tuple": (1, 2, 3),
        "set": {"red", "green", "blue"},
    }

    print(
        """
JSON does not have native representations for Python sets, tuples, or
arbitrary class instances. A serialization design therefore needs to decide
how such values should be represented.
"""
    )

    tuple_value = (1, 2, 3)
    tuple_json = json.dumps(tuple_value)
    tuple_restored = json.loads(tuple_json)

    print("Original tuple:", tuple_value, type(tuple_value).__name__)
    print("JSON:", tuple_json)
    print("Restored:", tuple_restored, type(tuple_restored).__name__)

    print("\nSet cannot be serialized directly:")
    try:
        json.dumps(original["set"])
    except TypeError as exc:
        print("TypeError:", exc)

    print(
        """
A serialization format can preserve only information that the format can
represent. JSON arrays preserve ordering, but they do not inherently encode
whether the source was a list, tuple, or another sequence.
"""
    )


# ============================================================================
# 12. CUSTOM SERIALIZATION WITH default=
# ============================================================================

@dataclass
class Employee:
    employee_id: int
    name: str
    department: str


def custom_default_encoder(value: Any) -> Any:
    """Convert selected non-native Python objects into JSON-compatible values."""
    if isinstance(value, Employee):
        return {
            "employee_id": value.employee_id,
            "name": value.name,
            "department": value.department,
        }

    if isinstance(value, set):
        # Sort for deterministic output. This requires comparable values.
        return sorted(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        # String representation preserves decimal digits exactly.
        return str(value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, bytes):
        # JSON cannot contain arbitrary binary data. Base64 is a common
        # transport representation when binary data must travel inside JSON.
        return {
            "__type__": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(value).decode("ascii"),
        }

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class UUID:
    """
    Minimal UUID-like demonstration class.

    The script intentionally avoids importing uuid.UUID directly into the
    custom type checks so the example remains explicit about custom objects.
    """

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def demonstrate_custom_encoder() -> None:
    section("12. CUSTOM JSON SERIALIZATION")

    employee = Employee(101, "Neha", "Engineering")

    data = {
        "employee": employee,
        "skills": {"Python", "SQL", "JSON"},
        "created_at": datetime(2026, 9, 9, 12, 30, tzinfo=timezone.utc),
        "amount": Decimal("1234.5678"),
        "request_id": UUID(str(uuid.uuid4())),
        "binary": b"hello",
    }

    serialized = json.dumps(
        data,
        default=custom_default_encoder,
        indent=2,
        ensure_ascii=False,
    )

    print(serialized)


# ============================================================================
# 13. CUSTOM DESERIALIZATION
# ============================================================================

def custom_object_hook(value: dict[str, Any]) -> Any:
    """
    Reconstruct selected application objects from explicitly tagged JSON.

    Security principle:
    Only reconstruct known, explicitly supported types. Never deserialize
    arbitrary classes based on attacker-controlled class names.
    """
    if (
        value.get("__type__") == "bytes"
        and value.get("encoding") == "base64"
        and isinstance(value.get("value"), str)
    ):
        try:
            return base64.b64decode(value["value"], validate=True)
        except ValueError as exc:
            raise ValueError("Invalid base64 data") from exc

    return value


def demonstrate_custom_decoding() -> None:
    section("13. CUSTOM JSON DESERIALIZATION")

    encoded = {
        "name": "document.bin",
        "data": {
            "__type__": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(b"secure example").decode("ascii"),
        },
    }

    text = json.dumps(encoded, indent=2)
    decoded = json.loads(text, object_hook=custom_object_hook)

    print("JSON:")
    print(text)
    print("\nDecoded:")
    print(decoded)
    print("Decoded data type:", type(decoded["data"]).__name__)


# ============================================================================
# 14. DATES AND TIMES
# ============================================================================

def demonstrate_datetime_serialization() -> None:
    section("14. DATES AND TIMES")

    moment = datetime.now(timezone.utc)
    today = date.today()

    print("Python datetime:", moment)
    print("ISO 8601 representation:", moment.isoformat())
    print("Python date:", today)
    print("ISO 8601 date:", today.isoformat())

    payload = {
        "created_at": moment.isoformat(),
        "business_date": today.isoformat(),
    }

    text = json.dumps(payload)
    restored = json.loads(text)

    print("\nJSON:", text)
    print(
        """
JSON stores these values as strings. The receiving system must know the
contract and parse the strings according to an agreed format.

Timezone-aware timestamps are preferable for event timestamps because they
avoid ambiguity about the intended instant.
"""
    )

    restored_datetime = datetime.fromisoformat(restored["created_at"])
    restored_date = date.fromisoformat(restored["business_date"])

    print("Restored datetime:", restored_datetime)
    print("Restored date:", restored_date)


# ============================================================================
# 15. FLOATING-POINT EDGE CASES
# ============================================================================

def demonstrate_numeric_edge_cases() -> None:
    section("15. NUMERIC EDGE CASES")

    values = [
        float("nan"),
        float("inf"),
        float("-inf"),
        0.1 + 0.2,
    ]

    print(
        """
IEEE-754 floating-point values such as NaN and Infinity are problematic
because they are outside strict JSON number semantics.
"""
    )

    for value in values:
        try:
            print("Default encoding:", value, "->", json.dumps(value))
        except ValueError as exc:
            print("Rejected:", value, exc)

    print("\nStrict JSON encoding with allow_nan=False:")

    for value in values:
        try:
            print(value, "->", json.dumps(value, allow_nan=False))
        except ValueError as exc:
            print(value, "-> ValueError:", exc)

    print("\nFloating-point precision:")
    print("0.1 + 0.2 =", 0.1 + 0.2)
    print("Exact equality with 0.3:", (0.1 + 0.2) == 0.3)
    print("math.isclose:", math.isclose(0.1 + 0.2, 0.3))


# ============================================================================
# 16. DECIMAL HANDLING
# ============================================================================

def demonstrate_decimal_handling() -> None:
    section("16. DECIMAL VALUES AND JSON")

    amount = Decimal("10.10")

    print("Decimal:", amount)

    try:
        json.dumps({"amount": amount})
    except TypeError as exc:
        print("Default serializer:", exc)

    as_number = json.dumps({"amount": float(amount)})
    as_string = json.dumps({"amount": str(amount)})

    print("As floating-point number:", as_number)
    print("As string:", as_string)

    print(
        """
For financial values, converting Decimal to binary floating point can
introduce representation concerns. A JSON API may represent monetary values
as a decimal string, or as an integer number of the smallest currency unit,
according to the system's contract.
"""
    )


# ============================================================================
# 17. PARSE NUMBERS WITH DECIMAL
# ============================================================================

def demonstrate_parse_float() -> None:
    section("17. PRECISE NUMBER PARSING")

    text = '{"price": 10.10, "tax": 0.075}'

    normal = json.loads(text)
    precise = json.loads(text, parse_float=Decimal)

    print("Normal parsing:")
    print(normal)
    print(type(normal["price"]).__name__)

    print("\nDecimal parsing:")
    print(precise)
    print(type(precise["price"]).__name__)


# ============================================================================
# 18. JSON ENCODING OPTIONS
# ============================================================================

def demonstrate_encoding_options() -> None:
    section("18. IMPORTANT json.dumps() OPTIONS")

    data = {
        "b": 2,
        "a": 1,
        "message": "नमस्ते",
        "items": [1, 2, 3],
    }

    examples = {
        "default": json.dumps(data),
        "pretty": json.dumps(data, indent=2, ensure_ascii=False),
        "sorted": json.dumps(data, sort_keys=True),
        "compact": json.dumps(data, separators=(",", ":")),
        "ascii": json.dumps(data, ensure_ascii=True),
    }

    for name, value in examples.items():
        print(f"\n{name}:")
        print(value)

    print(
        """
Key options:

indent
    Human-readable formatting.

sort_keys
    Deterministic key ordering, useful for snapshots and reproducible output.

ensure_ascii
    Controls whether non-ASCII characters are escaped.

separators
    Controls punctuation spacing and can reduce output size.

allow_nan
    Controls handling of non-standard NaN/Infinity representations.

default
    Provides a conversion hook for unsupported Python objects.
"""
    )


# ============================================================================
# 19. JSON LOAD OPTIONS
# ============================================================================

def demonstrate_load_options() -> None:
    section("19. IMPORTANT json.loads() OPTIONS")

    text = '{"small": 1.25, "large": 9007199254740993}'

    default_result = json.loads(text)
    decimal_result = json.loads(text, parse_float=Decimal)

    print("Default:", default_result)
    print("parse_float=Decimal:", decimal_result)

    print(
        """
Other useful parsing hooks include:

parse_int
    Custom handling of JSON integers.

parse_float
    Custom handling of JSON floating-point numbers.

parse_constant
    Handling of non-standard constants accepted by Python's decoder.

object_hook
    Transform parsed objects after their key/value pairs have been decoded.

object_pairs_hook
    Receive object members in pair order and can detect duplicate keys.
"""
    )


# ============================================================================
# 20. JSON FILE HANDLING
# ============================================================================

def demonstrate_json_files() -> None:
    section("20. JSON FILES")

    configuration = {
        "application": {
            "name": "Example Service",
            "debug": False,
            "workers": 4,
        },
        "features": ["search", "reporting"],
    }

    path = Path("example_config.json")

    try:
        path.write_text(
            json.dumps(configuration, indent=2),
            encoding="utf-8",
        )

        loaded = json.loads(path.read_text(encoding="utf-8"))

        print("Written configuration:")
        print(path.read_text(encoding="utf-8"))
        print("\nLoaded object:")
        print(loaded)
    finally:
        if path.exists():
            path.unlink()


# ============================================================================
# 21. JSON LINES
# ============================================================================

def demonstrate_json_lines() -> None:
    section("21. JSON LINES / NDJSON CONCEPT")

    records = [
        {"event": "login", "user_id": 1},
        {"event": "purchase", "user_id": 2, "amount": 250},
        {"event": "logout", "user_id": 1},
    ]

    text = "\n".join(json.dumps(record) for record in records)

    print(text)

    print("\nRead record by record:")
    for line in text.splitlines():
        record = json.loads(line)
        print(record)

    print(
        """
JSON Lines stores one complete JSON value per line. It is useful for logs,
stream processing, append-oriented datasets, and large collections where
loading an entire JSON array into memory would be undesirable.

A JSON Lines file is not the same thing as one standard JSON document.
"""
    )


# ============================================================================
# 22. STREAMING CONSIDERATIONS
# ============================================================================

def demonstrate_streaming_concept() -> None:
    section("22. STREAMING AND MEMORY")

    records = [{"id": number, "value": number * 10} for number in range(5)]

    whole_document = json.dumps(records)
    print("Whole JSON array:", whole_document)

    print(
        """
json.loads() normally parses the complete JSON text into an in-memory
Python structure. For very large documents, memory consumption can become
significant.

Possible strategies include:

1. JSON Lines / NDJSON.
2. Incremental parsing with a suitable streaming parser.
3. Pagination at the API level.
4. Chunked transport.
5. Database-side filtering.
6. Avoiding unnecessary materialization of large nested structures.

The standard library json module does not provide a general SAX-style
incremental parser for arbitrary JSON documents.
"""
    )


# ============================================================================
# 23. SERIALIZATION IS NOT VALIDATION
# ============================================================================

def demonstrate_serialization_vs_validation() -> None:
    section("23. SERIALIZATION IS NOT VALIDATION")

    payload = {
        "username": "",
        "age": -500,
        "email": "not-an-email",
    }

    serialized = json.dumps(payload)

    print("Serialization succeeds:")
    print(serialized)

    print(
        """
json.dumps() answers:
    "Can this Python object be represented as JSON?"

It does not answer:
    "Is this data acceptable for my business rules?"

Validation belongs to the application or schema layer.
"""
    )


# ============================================================================
# 24. SCHEMA-STYLE VALIDATION
# ============================================================================

def validate_product(payload: Any) -> tuple[bool, list[str]]:
    """A small schema-like validator implemented with the standard library."""
    errors: list[str] = []

    if not isinstance(payload, dict):
        return False, ["Product must be an object."]

    expected_types = {
        "id": int,
        "name": str,
        "price": (int, float),
        "tags": list,
    }

    for field, expected_type in expected_types.items():
        if field not in payload:
            errors.append(f"Missing field: {field}")
            continue

        value = payload[field]

        # bool is a subclass of int in Python, so explicitly reject it when
        # an actual integer is required.
        if field == "id" and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            errors.append("id must be an integer.")

        elif field == "price" and (
            not isinstance(value, (int, float)) or isinstance(value, bool)
        ):
            errors.append("price must be numeric.")

        elif field in {"name", "tags"} and not isinstance(value, expected_type):
            errors.append(f"{field} has the wrong type.")

    if isinstance(payload.get("name"), str) and not payload["name"].strip():
        errors.append("name cannot be empty.")

    if isinstance(payload.get("price"), (int, float)):
        if not math.isfinite(payload["price"]):
            errors.append("price must be finite.")
        elif payload["price"] < 0:
            errors.append("price cannot be negative.")

    if isinstance(payload.get("tags"), list):
        if not all(isinstance(tag, str) for tag in payload["tags"]):
            errors.append("Every tag must be a string.")

    return not errors, errors


def demonstrate_schema_style_validation() -> None:
    section("24. SCHEMA-STYLE VALIDATION")

    product = {
        "id": 100,
        "name": "Keyboard",
        "price": 1499.0,
        "tags": ["electronics", "input"],
    }

    valid, errors = validate_product(product)

    print("Valid:", valid)
    print("Errors:", errors)


# ============================================================================
# 25. JSON SCHEMA CONCEPTS
# ============================================================================

def explain_schema_concept() -> None:
    section("25. JSON SCHEMA CONCEPT")

    print(
        """
A schema describes the expected structure and constraints of JSON data.

Typical schema concepts include:

type
    object, array, string, number, integer, boolean, null

properties
    Defines fields of an object.

required
    Lists fields that must be present.

items
    Defines the expected structure of array elements.

enum
    Restricts a value to a known set.

minimum / maximum
    Numeric constraints.

minLength / maxLength
    String constraints.

pattern
    Regular-expression constraints for strings.

additionalProperties
    Controls whether unknown object properties are permitted.

A schema is a contract. It can be used to validate requests and responses,
document APIs, generate client/server artifacts, and detect incompatible
changes.
"""
    )


# ============================================================================
# 26. DATACLASSES
# ============================================================================

@dataclass
class Address:
    city: str
    country: str


@dataclass
class Person:
    person_id: int
    name: str
    address: Address


def demonstrate_dataclasses() -> None:
    section("26. DATACLASSES AND JSON")

    person = Person(
        person_id=10,
        name="Anil",
        address=Address(city="Lucknow", country="India"),
    )

    # dataclasses.asdict() converts nested dataclasses into dictionaries.
    serializable = asdict(person)
    text = json.dumps(serializable, indent=2)

    print("Dataclass:")
    print(person)
    print("\nDictionary:")
    print(serializable)
    print("\nJSON:")
    print(text)

    print(
        """
The JSON module does not automatically know the semantics of arbitrary
dataclasses. asdict() is one explicit conversion strategy.

Deserialization should also be explicit when strong domain objects are
required.
"""
    )


# ============================================================================
# 27. ENUMS
# ============================================================================

class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def demonstrate_enums() -> None:
    section("27. ENUMS AND JSON")

    status = Status.APPROVED

    try:
        json.dumps({"status": status})
    except TypeError as exc:
        print("Default:", exc)

    encoded = json.dumps({"status": status.value})
    print("Recommended explicit representation:", encoded)

    restored = json.loads(encoded)
    restored_status = Status(restored["status"])

    print("Restored enum:", restored_status)


# ============================================================================
# 28. SECURITY: JSON IS DATA, NOT CODE
# ============================================================================

def demonstrate_security() -> None:
    section("28. SECURITY CONSIDERATIONS")

    print(
        """
JSON parsing should treat incoming content as untrusted data.

Important security practices:

1. Never execute JSON as source code.
2. Never use eval() to parse JSON.
3. Validate types, lengths, ranges, and required fields.
4. Apply request-size limits.
5. Limit nesting depth where appropriate.
6. Reject duplicate keys if they create security ambiguity.
7. Avoid unsafe object reconstruction.
8. Treat URLs, HTML, SQL fragments, shell commands, and filenames as data
   requiring context-specific validation.
9. Do not assume valid JSON is trustworthy JSON.
10. Protect sensitive information before logging or storing it.
"""
    )

    malicious-looking_string = '{"command": "rm -rf /"}'
    parsed = json.loads(malicious-looking_string)

    print("JSON parsing produces data only:")
    print(parsed)

    print(
        """
Parsing does not execute the string. The danger begins when application
code incorrectly passes untrusted values into another interpreter or
dangerous operation.
"""
    )


# ============================================================================
# 29. RESOURCE EXHAUSTION
# ============================================================================

def demonstrate_resource_limits() -> None:
    section("29. RESOURCE-EXHAUSTION RISKS")

    print(
        """
A JSON document can be syntactically valid while being expensive to process.

Examples include:

- Extremely large strings.
- Extremely large arrays.
- Deeply nested objects.
- Huge numbers.
- Large request bodies.
- Repeated data causing memory pressure.

Production systems should establish limits such as:

- Maximum request body size.
- Maximum string length.
- Maximum array length.
- Maximum object member count.
- Maximum nesting depth.
- Maximum processing time where applicable.

These limits should be enforced before or during parsing when practical.
"""
    )

    small_document = json.dumps({"items": list(range(10))})
    print("Example small document:", small_document)


# ============================================================================
# 30. UNICODE
# ============================================================================

def demonstrate_unicode() -> None:
    section("30. UNICODE AND ENCODING")

    data = {
        "english": "Hello",
        "hindi": "नमस्ते",
        "japanese": "こんにちは",
        "emoji": "🚀",
    }

    ascii_safe = json.dumps(data)
    unicode_preserved = json.dumps(data, ensure_ascii=False)

    print("ensure_ascii=True:")
    print(ascii_safe)

    print("\nensure_ascii=False:")
    print(unicode_preserved)

    print(
        """
JSON text is Unicode-oriented. When JSON is transmitted or stored, an
encoding such as UTF-8 is normally used. Python file operations should make
the encoding explicit when predictable cross-platform behavior matters.
"""
    )


# ============================================================================
# 31. KEY TYPES
# ============================================================================

def demonstrate_key_conversion() -> None:
    section("31. JSON OBJECT KEYS AND PYTHON DICTIONARIES")

    data = {
        1: "integer key",
        True: "boolean key",
        None: "none key",
        "normal": "string key",
    }

    text = json.dumps(data)
    restored = json.loads(text)

    print("Original:", data)
    print("JSON:", text)
    print("Restored:", restored)

    print(
        """
JSON object names are strings. Python dictionaries can use keys of types
that JSON cannot represent as object names. Serialization can therefore
change key types.

This is a common source of information loss.
"""
    )


# ============================================================================
# 32. KEY COLLISION EDGE CASE
# ============================================================================

def demonstrate_key_collision() -> None:
    section("32. PYTHON KEY COLLISIONS BEFORE JSON SERIALIZATION")

    data = {
        1: "integer",
        True: "boolean",
    }

    print("Python dictionary:", data)
    print(
        """
Python considers 1 and True equal as dictionary keys because:
    1 == True

Therefore the dictionary itself has already lost one value before JSON
serialization occurs.
"""
    )

    print("JSON:", json.dumps(data))


# ============================================================================
# 33. CHARACTER ESCAPING
# ============================================================================

def demonstrate_escaping() -> None:
    section("33. JSON STRING ESCAPING")

    value = 'Quote: " ; slash: \\ ; newline:\n ; tab:\t'

    text = json.dumps(value)

    print("Python string:")
    print(repr(value))

    print("\nJSON string:")
    print(text)

    print("\nRestored:")
    print(repr(json.loads(text)))


# ============================================================================
# 34. CANONICAL / DETERMINISTIC JSON
# ============================================================================

def demonstrate_deterministic_serialization() -> None:
    section("34. DETERMINISTIC SERIALIZATION")

    payload = {
        "z": 3,
        "a": 1,
        "m": 2,
    }

    first = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    second = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    print("First:", first)
    print("Second:", second)
    print("Identical:", first == second)

    print(
        """
Deterministic output is useful for:

- Snapshot tests.
- Stable logs.
- Hashing workflows where the serialization rules are explicitly defined.
- Reproducible artifacts.
- Change detection.

A stable json.dumps configuration does not automatically make a document
cryptographically canonical under every external JSON canonicalization
standard. Cryptographic use cases require an explicitly specified
canonicalization scheme.
"""
    )


# ============================================================================
# 35. ROUND-TRIP TEST
# ============================================================================

def demonstrate_round_trip() -> None:
    section("35. ROUND-TRIP SERIALIZATION")

    original = {
        "id": 42,
        "name": "Round Trip",
        "active": True,
        "items": [1, 2, 3],
        "metadata": None,
    }

    text = json.dumps(original)
    restored = json.loads(text)

    print("Original:", original)
    print("JSON:", text)
    print("Restored:", restored)
    print("Equal:", original == restored)


# ============================================================================
# 36. ROUND-TRIP LIMITATIONS
# ============================================================================

def demonstrate_round_trip_limitations() -> None:
    section("36. ROUND-TRIP DOES NOT GUARANTEE TYPE IDENTITY")

    examples = {
        "tuple": (1, 2),
        "integer": 10,
        "float": 10.0,
    }

    for name, original in examples.items():
        text = json.dumps(original)
        restored = json.loads(text)

        print(
            f"{name:<10} original_type={type(original).__name__:<8} "
            f"restored_type={type(restored).__name__:<8} "
            f"equal={original == restored}"
        )

    print(
        """
Equality can survive while type identity does not.

For example:
    (1, 2) != [1, 2]

but the tuple becomes an array and is restored as a list.

A serialization contract must define which distinctions matter.
"""
    )


# ============================================================================
# 37. API REQUEST/RESPONSE MODEL
# ============================================================================

def build_api_response(user_id: int, name: str, roles: list[str]) -> dict[str, Any]:
    """Build an API response using JSON-compatible domain data."""
    return {
        "data": {
            "id": user_id,
            "name": name,
            "roles": roles,
        },
        "meta": {
            "version": "1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def demonstrate_api_payload() -> None:
    section("37. JSON IN WEB APIs")

    response = build_api_response(
        user_id=7,
        name="Priya",
        roles=["user", "analyst"],
    )

    print(json.dumps(response, indent=2, ensure_ascii=False))

    print(
        """
A production API contract should define:

- Root structure.
- Required and optional fields.
- Field types.
- Nullability.
- Allowed enum values.
- Timestamp format.
- Number precision.
- Error format.
- Unknown-field behavior.
- Versioning strategy.
- Size limits.
- Authentication and authorization independently from serialization.
"""
    )


# ============================================================================
# 38. PATCH-LIKE NULL VS ABSENCE DISTINCTION
# ============================================================================

def demonstrate_null_vs_missing() -> None:
    section("38. NULL VS MISSING FIELD")

    payload_a = '{"nickname": null}'
    payload_b = '{}'

    a = json.loads(payload_a)
    b = json.loads(payload_b)

    print("Payload A:", a)
    print("Payload B:", b)

    print(
        """
These can have different business meanings.

Field absent:
    "The client did not provide a value."

Field present with null:
    "The client explicitly provided no value."

An API must define whether this distinction matters.
"""
    )


# ============================================================================
# 39. BACKWARD AND FORWARD COMPATIBILITY
# ============================================================================

def demonstrate_compatibility() -> None:
    section("39. SCHEMA EVOLUTION AND COMPATIBILITY")

    old_payload = {
        "id": 1,
        "name": "Alice",
    }

    new_payload = {
        "id": 1,
        "name": "Alice",
        "department": "Engineering",
    }

    print("Old payload:", json.dumps(old_payload))
    print("New payload:", json.dumps(new_payload))

    print(
        """
Adding an optional field is often less disruptive than changing or removing
an existing field, but compatibility depends on the consumers.

Potentially breaking changes include:

- Changing a field's type.
- Renaming a field.
- Changing an enum value.
- Changing number semantics.
- Making an optional field mandatory.
- Changing nullability.
- Changing the meaning of an existing value.

Compatibility should be defined explicitly for every API or data pipeline.
"""
    )


# ============================================================================
# 40. ERROR PAYLOAD DESIGN
# ============================================================================

def demonstrate_error_payload() -> None:
    section("40. STRUCTURED ERROR RESPONSES")

    error = {
        "error": {
            "code": "INVALID_ARGUMENT",
            "message": "The age field must be an integer.",
            "field": "age",
        }
    }

    print(json.dumps(error, indent=2))

    print(
        """
Structured errors are easier for machines to process than free-form error
strings. A useful error contract generally separates a stable machine code
from a human-readable message.
"""
    )


# ============================================================================
# 41. JSON AND BINARY DATA
# ============================================================================

def demonstrate_binary_data() -> None:
    section("41. BINARY DATA")

    binary = b"\x00\x01\x02hello"

    try:
        json.dumps({"data": binary})
    except TypeError as exc:
        print("Direct binary serialization fails:", exc)

    encoded = base64.b64encode(binary).decode("ascii")
    payload = {"encoding": "base64", "data": encoded}

    text = json.dumps(payload)
    restored = base64.b64decode(json.loads(text)["data"])

    print("JSON:", text)
    print("Restored bytes:", restored)

    print(
        """
Base64 increases payload size compared with raw binary. If a system handles
large binary objects, a binary protocol or separate object storage may be
more appropriate than embedding the bytes in JSON.
"""
    )


# ============================================================================
# 42. JSON VS CSV
# ============================================================================

def compare_json_csv() -> None:
    section("42. JSON VS CSV")

    print(
        """
JSON:
    Strengths:
        - Nested structures.
        - Explicit field names.
        - Multiple data types.
        - Natural representation for APIs.
        - Good for heterogeneous records.

    Weaknesses:
        - More verbose than compact tabular formats.
        - Parsing can require substantial memory.
        - Less efficient than specialized binary formats.

CSV:
    Strengths:
        - Simple tabular representation.
        - Compact for flat data.
        - Widely supported by spreadsheet tools.

    Weaknesses:
        - Poor representation of nested data.
        - Type information is limited.
        - Escaping and dialect differences can create interoperability issues.
"""
    )


# ============================================================================
# 43. JSON VS BINARY SERIALIZATION
# ============================================================================

def compare_serialization_formats() -> None:
    section("43. JSON VS OTHER SERIALIZATION FORMATS")

    formats = {
        "JSON": "Human-readable, broadly interoperable, flexible, text-based.",
        "XML": "Text-based, highly expressive, verbose, supports namespaces.",
        "CSV": "Simple tabular text format, weak for nested structures.",
        "MessagePack": "Binary representation with JSON-like data model.",
        "Protocol Buffers": "Schema-driven binary format optimized for compactness and performance.",
        "CBOR": "Binary format designed around a JSON-like data model with richer types.",
    }

    for name, description in formats.items():
        print(f"{name:<18} {description}")

    print(
        """
Format choice is a system-design decision.

JSON is often a strong default for public APIs and interoperability.
Binary schema-driven formats can be preferable for high-throughput,
low-latency, bandwidth-sensitive, or strongly typed internal systems.
"""
    )


# ============================================================================
# 44. PERFORMANCE
# ============================================================================

def benchmark_json() -> None:
    section("44. BASIC PERFORMANCE CONSIDERATIONS")

    payload = {
        "users": [
            {
                "id": index,
                "name": f"user-{index}",
                "active": index % 2 == 0,
                "scores": [index, index + 1, index + 2],
            }
            for index in range(1000)
        ]
    }

    start = time.perf_counter()
    text = json.dumps(payload, separators=(",", ":"))
    encode_time = time.perf_counter() - start

    start = time.perf_counter()
    restored = json.loads(text)
    decode_time = time.perf_counter() - start

    print(f"JSON size: {len(text):,} characters")
    print(f"Serialization time: {encode_time:.6f} seconds")
    print(f"Deserialization time: {decode_time:.6f} seconds")
    print(f"Round-trip equality: {payload == restored}")

    print(
        """
Performance depends on:

- Payload size.
- Nesting depth.
- Number of objects.
- String sizes.
- Numeric complexity.
- Encoder/decoder implementation.
- Network bandwidth.
- Compression.
- CPU and memory constraints.

Do not optimize based only on serialization speed. In network systems,
payload size, network latency, compression cost, parsing cost, and downstream
processing all contribute to total latency.
"""
    )


# ============================================================================
# 45. COMPRESSION
# ============================================================================

def demonstrate_compression() -> None:
    section("45. JSON AND COMPRESSION")

    import gzip

    payload = {
        "records": [
            {
                "id": index,
                "description": "Repeated descriptive text " * 5,
                "status": "active",
            }
            for index in range(500)
        ]
    }

    text = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(text)

    print(f"Uncompressed bytes: {len(text):,}")
    print(f"Gzip bytes:         {len(compressed):,}")

    print(
        """
JSON is text-heavy, so general-purpose compression can substantially reduce
wire size when data contains repeated field names or values.

Compression has CPU cost and may have diminishing returns for already
compressed content.
"""
    )


# ============================================================================
# 46. LOGGING
# ============================================================================

def demonstrate_structured_logging() -> None:
    section("46. JSON FOR STRUCTURED LOGGING")

    log_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "event": "user_login",
        "user_id": 123,
        "success": True,
    }

    print(json.dumps(log_event, separators=(",", ":")))

    print(
        """
Structured JSON logs allow logging systems to filter and aggregate fields
without scraping human-readable sentences.

Sensitive values such as passwords, access tokens, session cookies, and
unnecessary personal information should not be logged.
"""
    )


# ============================================================================
# 47. COMMAND-LINE INPUT SAFETY
# ============================================================================

def parse_json_argument(text: str) -> Any:
    """Parse a JSON argument without executing it."""
    return json.loads(text)


def demonstrate_cli_style_parsing() -> None:
    section("47. JSON FROM COMMAND-LINE INPUT")

    sample = '{"operation":"create","name":"report"}'
    result = parse_json_argument(sample)

    print("Input:", sample)
    print("Parsed:", result)

    print(
        """
Command-line JSON should be treated as untrusted input when supplied by
another user or process. Catch JSONDecodeError and validate the resulting
structure before performing operations.
"""
    )


# ============================================================================
# 48. FILE ENCODING ERRORS
# ============================================================================

def demonstrate_file_encoding() -> None:
    section("48. FILE ENCODING PRACTICES")

    path = Path("unicode_example.json")

    payload = {"message": "नमस्ते दुनिया"}

    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        content = path.read_text(encoding="utf-8")
        print(content)
    finally:
        if path.exists():
            path.unlink()

    print(
        """
Explicit UTF-8 handling makes the intended text encoding clear and avoids
platform-dependent assumptions.
"""
    )


# ============================================================================
# 49. TESTING JSON CODE
# ============================================================================

def test_round_trip() -> None:
    data = {
        "name": "test",
        "values": [1, 2, 3],
        "active": True,
        "nothing": None,
    }

    assert json.loads(json.dumps(data)) == data


def test_invalid_json() -> None:
    try:
        json.loads('{"broken": }')
    except json.JSONDecodeError:
        return

    raise AssertionError("Invalid JSON should have raised JSONDecodeError")


def test_product_validation() -> None:
    valid, errors = validate_product(
        {
            "id": 1,
            "name": "Book",
            "price": 100,
            "tags": ["education"],
        }
    )

    assert valid
    assert errors == []


def run_tests() -> None:
    section("49. BASIC TESTS")

    tests = [
        test_round_trip,
        test_invalid_json,
        test_product_validation,
    ]

    passed = 0

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
        passed += 1

    print(f"\n{passed}/{len(tests)} tests passed.")


# ============================================================================
# 50. COMMON MISTAKES
# ============================================================================

def demonstrate_common_mistakes() -> None:
    section("50. COMMON MISTAKES")

    mistakes = [
        (
            "Using single quotes as JSON syntax",
            "JSON strings and object names require double quotes."
        ),
        (
            "Using Python True/False/None in JSON",
            "JSON uses true/false/null."
        ),
        (
            "Assuming serialization validates business rules",
            "Serialization and validation solve different problems."
        ),
        (
            "Calling eval() on JSON",
            "JSON must be parsed as data, not executed as code."
        ),
        (
            "Assuming arbitrary Python objects serialize automatically",
            "JSON supports a limited data model."
        ),
        (
            "Ignoring numeric precision",
            "Different languages and runtimes can represent numbers differently."
        ),
        (
            "Ignoring null versus missing",
            "The distinction can matter in APIs and partial updates."
        ),
        (
            "Ignoring duplicate object keys",
            "Ambiguous duplicates can cause interoperability and security problems."
        ),
        (
            "Loading enormous JSON documents without limits",
            "Large payloads can cause memory and availability problems."
        ),
        (
            "Embedding large binary objects directly in JSON",
            "Base64 adds size overhead and may be operationally inefficient."
        ),
    ]

    for mistake, correction in mistakes:
        print(f"\nMistake: {mistake}")
        print(f"Practice: {correction}")


# ============================================================================
# 51. PRODUCTION CHECKLIST
# ============================================================================

def print_production_checklist() -> None:
    section("51. PRODUCTION JSON CHECKLIST")

    checklist = [
        "Define a stable JSON contract.",
        "Validate syntax and application semantics.",
        "Document required, optional, and nullable fields.",
        "Define numeric precision and range expectations.",
        "Define timestamp and timezone conventions.",
        "Define unknown-field behavior.",
        "Define duplicate-key policy where relevant.",
        "Set request and response size limits.",
        "Avoid unsafe object reconstruction.",
        "Never execute JSON as code.",
        "Avoid logging secrets and unnecessary sensitive data.",
        "Use explicit UTF-8 handling for files and text boundaries.",
        "Use compact JSON where wire size matters.",
        "Use compression where appropriate.",
        "Use streaming or pagination for large datasets.",
        "Test malformed, boundary, and adversarial inputs.",
        "Test compatibility between producer and consumer versions.",
        "Use deterministic output where reproducibility matters.",
        "Choose a binary format when JSON is not operationally appropriate.",
    ]

    for index, item in enumerate(checklist, 1):
        print(f"{index:02d}. {item}")


# ============================================================================
# 52. INTEGRATED MINI PROJECT
# ============================================================================

@dataclass
class OrderItem:
    product_id: int
    quantity: int
    unit_price: Decimal


@dataclass
class Order:
    order_id: int
    customer_name: str
    items: list[OrderItem]
    created_at: datetime


def serialize_order(order: Order) -> str:
    """Convert an Order domain object into a documented JSON representation."""
    payload = {
        "order_id": order.order_id,
        "customer_name": order.customer_name,
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat(),
    }

    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )


def deserialize_order(text: str) -> Order:
    """Validate and reconstruct an Order from its JSON representation."""
    payload = json.loads(text)

    if not isinstance(payload, dict):
        raise ValueError("Order must be a JSON object.")

    required = {"order_id", "customer_name", "items", "created_at"}

    if set(payload) != required:
        missing = required - set(payload)
        extra = set(payload) - required

        details = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if extra:
            details.append(f"unexpected={sorted(extra)}")

        raise ValueError("Invalid order fields: " + ", ".join(details))

    if not isinstance(payload["order_id"], int):
        raise ValueError("order_id must be an integer.")

    if not isinstance(payload["customer_name"], str):
        raise ValueError("customer_name must be a string.")

    if not isinstance(payload["items"], list):
        raise ValueError("items must be an array.")

    items: list[OrderItem] = []

    for index, item in enumerate(payload["items"]):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index}] must be an object.")

        required_item_fields = {"product_id", "quantity", "unit_price"}

        if set(item) != required_item_fields:
            raise ValueError(f"Invalid fields in items[{index}].")

        if (
            not isinstance(item["product_id"], int)
            or isinstance(item["product_id"], bool)
        ):
            raise ValueError(f"items[{index}].product_id must be an integer.")

        if (
            not isinstance(item["quantity"], int)
            or isinstance(item["quantity"], bool)
            or item["quantity"] <= 0
        ):
            raise ValueError(
                f"items[{index}].quantity must be a positive integer."
            )

        if not isinstance(item["unit_price"], str):
            raise ValueError(f"items[{index}].unit_price must be a string.")

        try:
            unit_price = Decimal(item["unit_price"])
        except Exception as exc:
            raise ValueError(
                f"items[{index}].unit_price must be a valid decimal."
            ) from exc

        if not unit_price.is_finite() or unit_price < 0:
            raise ValueError(
                f"items[{index}].unit_price must be finite and non-negative."
            )

        items.append(
            OrderItem(
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=unit_price,
            )
        )

    try:
        created_at = datetime.fromisoformat(payload["created_at"])
    except ValueError as exc:
        raise ValueError("created_at must be a valid ISO 8601 timestamp.") from exc

    return Order(
        order_id=payload["order_id"],
        customer_name=payload["customer_name"],
        items=items,
        created_at=created_at,
    )


def calculate_order_total(order: Order) -> Decimal:
    """Calculate a monetary total using Decimal instead of float."""
    total = Decimal("0")

    for item in order.items:
        total += item.unit_price * item.quantity

    return total


def demonstrate_integrated_project() -> None:
    section("52. INTEGRATED PROJECT: ORDER SERIALIZATION")

    order = Order(
        order_id=5001,
        customer_name="Rahul",
        items=[
            OrderItem(101, 2, Decimal("1499.95")),
            OrderItem(202, 1, Decimal("799.50")),
        ],
        created_at=datetime.now(timezone.utc),
    )

    text = serialize_order(order)

    print("Serialized order:")
    print(text)

    restored = deserialize_order(text)

    print("\nRestored domain object:")
    print(restored)

    print("\nOrder total:")
    print(calculate_order_total(restored))

    print(
        """
This example demonstrates an important production pattern:

Domain model
    ->
Explicit JSON-compatible representation
    ->
JSON serialization
    ->
Transport/storage
    ->
JSON parsing
    ->
Validation
    ->
Domain model

The conversion boundary is explicit rather than relying on accidental
serialization behavior.
"""
    )


# ============================================================================
# 53. EDGE CASE COLLECTION
# ============================================================================

def demonstrate_edge_cases() -> None:
    section("53. IMPORTANT EDGE CASES")

    cases = [
        ("empty object", "{}"),
        ("empty array", "[]"),
        ("null", "null"),
        ("zero", "0"),
        ("negative number", "-1"),
        ("scientific notation", "1.2e3"),
        ("empty string", '""'),
        ("unicode", '"नमस्ते"'),
        ("nested empty values", '{"a":[],"b":{},"c":null}'),
    ]

    for name, text in cases:
        value = json.loads(text)
        print(f"{name:<24} {text:<35} -> {value!r}")


# ============================================================================
# 54. JSON LIMITATIONS
# ============================================================================

def explain_limitations() -> None:
    section("54. JSON LIMITATIONS")

    limitations = [
        (
            "Limited native types",
            "No native date, time, decimal, set, bytes, tuple, enum, or class type."
        ),
        (
            "No comments",
            "Standard JSON does not define comments."
        ),
        (
            "Number interoperability",
            "Different systems may have different integer ranges and floating-point behavior."
        ),
        (
            "Potential verbosity",
            "Repeated field names can create substantial text overhead."
        ),
        (
            "No schema enforcement by itself",
            "JSON syntax does not specify application-level validation rules."
        ),
        (
            "No built-in encryption",
            "JSON does not provide confidentiality or authentication."
        ),
        (
            "No built-in compression",
            "Compression is a separate transport/storage concern."
        ),
        (
            "No executable behavior",
            "JSON represents data and does not define application semantics by itself."
        ),
        (
            "Large-document memory costs",
            "Whole-document parsing can require significant memory."
        ),
        (
            "Potential ambiguity",
            "Duplicate keys, numeric precision, nullability, and unknown fields require contracts."
        ),
    ]

    for limitation, explanation in limitations:
        print(f"\n{limitation}")
        print(f"  {explanation}")


# ============================================================================
# 55. FINAL CONCEPT MAP
# ============================================================================

def print_concept_map() -> None:
    section("55. CONCEPT MAP")

    print(
        """
JSON
|
+-- Syntax
|   +-- Object
|   +-- Array
|   +-- String
|   +-- Number
|   +-- Boolean
|   +-- Null
|
+-- Serialization
|   +-- Python -> JSON text
|   +-- dumps()
|   +-- dump()
|   +-- Custom encoding
|
+-- Deserialization
|   +-- JSON text -> Python
|   +-- loads()
|   +-- load()
|   +-- Custom decoding
|
+-- Validation
|   +-- Syntax validation
|   +-- Structural validation
|   +-- Semantic validation
|   +-- Schema contracts
|
+-- Interoperability
|   +-- Unicode
|   +-- Numeric precision
|   +-- Dates/times
|   +-- Null vs missing
|   +-- Duplicate keys
|
+-- Engineering
|   +-- APIs
|   +-- Files
|   +-- Logs
|   +-- Configuration
|   +-- Data pipelines
|
+-- Production concerns
    +-- Security
    +-- Resource limits
    +-- Performance
    +-- Compatibility
    +-- Deterministic output
    +-- Testing
    +-- Format selection
"""
    )


# ============================================================================
# 56. MAIN PROGRAM
# ============================================================================

def main() -> None:
    """Run the complete educational demonstration."""
    print("JSON AND DATA SERIALIZATION")
    print("Python Standard Library Study Script")
    print(f"Python version: {sys.version.split()[0]}")

    explain_fundamentals()
    demonstrate_json_syntax()
    demonstrate_primitives()
    demonstrate_python_json_mapping()
    demonstrate_serialization()
    demonstrate_dump_variants()
    demonstrate_deserialization()
    demonstrate_validation()
    demonstrate_application_validation()
    demonstrate_object_behavior()
    demonstrate_information_loss()
    demonstrate_custom_encoder()
    demonstrate_custom_decoding()
    demonstrate_datetime_serialization()
    demonstrate_numeric_edge_cases()
    demonstrate_decimal_handling()
    demonstrate_parse_float()
    demonstrate_encoding_options()
    demonstrate_load_options()
    demonstrate_json_files()
    demonstrate_json_lines()
    demonstrate_streaming_concept()
    demonstrate_serialization_vs_validation()
    demonstrate_schema_style_validation()
    explain_schema_concept()
    demonstrate_dataclasses()
    demonstrate_enums()
    demonstrate_security()
    demonstrate_resource_limits()
    demonstrate_unicode()
    demonstrate_key_conversion()
    demonstrate_key_collision()
    demonstrate_escaping()
    demonstrate_deterministic_serialization()
    demonstrate_round_trip()
    demonstrate_round_trip_limitations()
    demonstrate_api_payload()
    demonstrate_null_vs_missing()
    demonstrate_compatibility()
    demonstrate_error_payload()
    demonstrate_binary_data()
    compare_json_csv()
    compare_serialization_formats()
    benchmark_json()
    demonstrate_compression()
    demonstrate_structured_logging()
    demonstrate_cli_style_parsing()
    demonstrate_file_encoding()
    run_tests()
    demonstrate_common_mistakes()
    print_production_checklist()
    demonstrate_integrated_project()
    demonstrate_edge_cases()
    explain_limitations()
    print_concept_map()


if __name__ == "__main__":
    main()
