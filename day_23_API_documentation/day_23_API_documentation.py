"""
API Documentation with OpenAPI: schemas, operation IDs, metadata, Swagger UI,
and ReDoc.

This standalone study program builds an OpenAPI 3.0-style document from Python
data structures and then validates, inspects, renders, and tests important
parts of the document.

The examples intentionally avoid external packages so that the file can be
run with a standard Python installation:

    python api_documentation.py

The program teaches:
- API documentation fundamentals
- OpenAPI structure
- API metadata
- servers
- tags
- paths and operations
- HTTP methods
- operationId
- parameters
- request bodies
- reusable schemas
- JSON Schema concepts used by OpenAPI
- responses
- headers
- examples
- security schemes
- component reuse
- references
- validation
- Swagger UI and ReDoc integration concepts
- documentation quality
- versioning
- design and production considerations
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Basic terminology
# ---------------------------------------------------------------------------

def print_section(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_subsection(title: str) -> None:
    print("\n" + "-" * 72)
    print(title)
    print("-" * 72)


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=False)


def explain_basic_terms() -> None:
    print_section("1. API documentation fundamentals")

    terms = {
        "API": "A defined interface through which software components communicate.",
        "OpenAPI": (
            "A machine-readable specification format for describing HTTP APIs. "
            "OpenAPI documents commonly use JSON or YAML."
        ),
        "Swagger": (
            "A family of tools associated with OpenAPI. Swagger UI is commonly "
            "used to render interactive API documentation."
        ),
        "ReDoc": (
            "A documentation renderer that turns an OpenAPI document into a "
            "structured, readable web reference."
        ),
        "Schema": (
            "A description of the shape, type, constraints, and relationships "
            "of data used by an API."
        ),
        "operationId": (
            "A unique identifier for an API operation. It is useful for code "
            "generation, SDK method naming, testing, and tooling."
        ),
        "Metadata": (
            "Descriptive information about an API such as title, version, "
            "description, contact information, and license information."
        ),
        "Path": (
            "The URL path template, such as /users/{user_id}, associated with "
            "one or more HTTP operations."
        ),
        "Response": (
            "The documented HTTP result an API may return, identified by a "
            "status code such as 200, 201, 400, or 404."
        ),
    }

    for name, description in terms.items():
        print(f"{name:16} {description}")


# ---------------------------------------------------------------------------
# 2. OpenAPI schema building blocks
# ---------------------------------------------------------------------------

def build_basic_schema_examples() -> Dict[str, Any]:
    """
    Demonstrate common schema types.

    OpenAPI schemas are based heavily on JSON Schema concepts. The exact
    supported JSON Schema vocabulary depends on the OpenAPI version, so
    documentation should always state which OpenAPI version it targets.
    """
    return {
        "StringExample": {
            "type": "string",
            "description": "A non-empty human-readable name.",
            "minLength": 1,
            "maxLength": 100,
        },
        "IntegerExample": {
            "type": "integer",
            "format": "int64",
            "minimum": 1,
            "maximum": 1000000,
        },
        "BooleanExample": {
            "type": "boolean",
            "description": "Whether an account is active.",
        },
        "ArrayExample": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "EnumExample": {
            "type": "string",
            "enum": ["active", "inactive", "suspended"],
        },
        "ObjectExample": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer", "format": "int64"},
                "name": {"type": "string"},
            },
        },
    }


def demonstrate_schema_examples() -> None:
    print_section("2. Common OpenAPI schema structures")

    schemas = build_basic_schema_examples()

    for name, schema in schemas.items():
        print_subsection(name)
        print(pretty_json(schema))


# ---------------------------------------------------------------------------
# 3. A small JSON Schema-like validator
# ---------------------------------------------------------------------------

class SchemaValidationError(ValueError):
    """Raised when a demonstration payload violates a schema."""


def validate_schema(
    value: Any,
    schema: Dict[str, Any],
    path: str = "$",
) -> None:
    """
    Validate a practical subset of JSON Schema/OpenAPI schema rules.

    This is intentionally educational rather than a complete JSON Schema
    implementation. It demonstrates how documented constraints correspond
    to runtime validation.

    Supported examples include:
    - type
    - required
    - properties
    - items
    - enum
    - minimum / maximum
    - minLength / maxLength
    - pattern
    - minItems / maxItems
    - nullable-like handling through explicit None support
    - oneOf
    """
    if value is None:
        if schema.get("nullable") is True:
            return
        raise SchemaValidationError(f"{path}: null is not permitted")

    if "oneOf" in schema:
        successful = 0
        for candidate in schema["oneOf"]:
            try:
                validate_schema(value, candidate, path)
                successful += 1
            except SchemaValidationError:
                pass

        if successful != 1:
            raise SchemaValidationError(
                f"{path}: value must match exactly one oneOf schema"
            )
        return

    expected_type = schema.get("type")

    if expected_type == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path}: expected string")

        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaValidationError(
                f"{path}: string is shorter than minLength"
            )

        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaValidationError(
                f"{path}: string is longer than maxLength"
            )

        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise SchemaValidationError(
                f"{path}: string does not match pattern"
            )

    elif expected_type == "integer":
        # bool is a subclass of int in Python, but it should not count as an
        # integer for API validation purposes.
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected integer")

        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value is below minimum")

        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value exceeds maximum")

    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected number")

        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value is below minimum")

        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value exceeds maximum")

    elif expected_type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected boolean")

    elif expected_type == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path}: expected array")

        if "minItems" in schema and len(value) < schema["minItems"]:
            raise SchemaValidationError(f"{path}: too few items")

        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaValidationError(f"{path}: too many items")

        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema(item, item_schema, f"{path}[{index}]")

    elif expected_type == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path}: expected object")

        required = schema.get("required", [])
        for field_name in required:
            if field_name not in value:
                raise SchemaValidationError(
                    f"{path}: missing required property '{field_name}'"
                )

        properties = schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if field_name in value:
                validate_schema(
                    value[field_name],
                    field_schema,
                    f"{path}.{field_name}",
                )

    elif expected_type is not None:
        raise SchemaValidationError(
            f"{path}: unsupported demonstration schema type {expected_type!r}"
        )

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(
            f"{path}: value {value!r} is not one of {schema['enum']!r}"
        )


def demonstrate_runtime_validation() -> None:
    print_section("3. Documentation schemas and runtime validation")

    user_schema = {
        "type": "object",
        "required": ["id", "name", "email"],
        "properties": {
            "id": {"type": "integer", "minimum": 1},
            "name": {"type": "string", "minLength": 1},
            "email": {
                "type": "string",
                "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive"],
            },
        },
    }

    valid_user = {
        "id": 7,
        "name": "Atul",
        "email": "atul@example.com",
        "status": "active",
    }

    invalid_users = [
        {
            "id": 0,
            "name": "Atul",
            "email": "atul@example.com",
        },
        {
            "id": 7,
            "name": "",
            "email": "atul@example.com",
        },
        {
            "id": 7,
            "name": "Atul",
            "email": "not-an-email",
        },
        {
            "id": 7,
            "name": "Atul",
            "email": "atul@example.com",
            "status": "unknown",
        },
    ]

    print("Valid payload:")
    try:
        validate_schema(valid_user, user_schema)
        print("  ACCEPTED")
    except SchemaValidationError as error:
        print("  REJECTED:", error)

    print("\nInvalid payloads:")
    for payload in invalid_users:
        try:
            validate_schema(payload, user_schema)
            print("  ACCEPTED:", payload)
        except SchemaValidationError as error:
            print("  REJECTED:", error)


# ---------------------------------------------------------------------------
# 4. Reusable OpenAPI components
# ---------------------------------------------------------------------------

def ref(component_name: str) -> str:
    """Create a local OpenAPI JSON Reference."""
    return f"#/components/schemas/{component_name}"


def build_components() -> Dict[str, Any]:
    """
    Components are reusable definitions.

    Reuse prevents a large API document from duplicating the same schema
    repeatedly. $ref expresses that relationship.
    """
    return {
        "schemas": {
            "User": {
                "type": "object",
                "description": "A registered API user.",
                "required": ["id", "name", "email", "status"],
                "properties": {
                    "id": {
                        "type": "integer",
                        "format": "int64",
                        "minimum": 1,
                        "example": 101,
                    },
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                        "example": "Atul Pandey",
                    },
                    "email": {
                        "type": "string",
                        "format": "email",
                        "example": "atul@example.com",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "suspended"],
                        "example": "active",
                    },
                    "roles": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["reader", "editor", "admin"],
                        },
                        "minItems": 1,
                        "example": ["reader"],
                    },
                },
            },
            "UserCreate": {
                "type": "object",
                "required": ["name", "email"],
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                    },
                    "email": {
                        "type": "string",
                        "format": "email",
                    },
                    "roles": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["reader", "editor", "admin"],
                        },
                        "default": ["reader"],
                    },
                },
            },
            "Error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": {
                        "type": "string",
                        "example": "USER_NOT_FOUND",
                    },
                    "message": {
                        "type": "string",
                        "example": "The requested user does not exist.",
                    },
                    "details": {
                        "type": "object",
                        "additionalProperties": True,
                        "example": {},
                    },
                },
            },
            "HealthStatus": {
                "type": "object",
                "required": ["status", "service"],
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["ok", "degraded"],
                    },
                    "service": {
                        "type": "string",
                    },
                    "version": {
                        "type": "string",
                    },
                },
            },
        },
        "parameters": {
            "UserId": {
                "name": "user_id",
                "in": "path",
                "required": True,
                "description": "Unique identifier of the user.",
                "schema": {
                    "type": "integer",
                    "format": "int64",
                    "minimum": 1,
                },
                "example": 101,
            },
            "Page": {
                "name": "page",
                "in": "query",
                "required": False,
                "description": "One-based page number.",
                "schema": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                },
            },
            "PageSize": {
                "name": "page_size",
                "in": "query",
                "required": False,
                "description": "Maximum number of records returned.",
                "schema": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
            },
        },
        "responses": {
            "BadRequest": {
                "description": "The request is invalid.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": ref("Error")}
                    }
                },
            },
            "NotFound": {
                "description": "The requested resource was not found.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": ref("Error")}
                    }
                },
            },
            "ServerError": {
                "description": "An unexpected server error occurred.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": ref("Error")}
                    }
                },
            },
        },
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            },
        },
    }


# ---------------------------------------------------------------------------
# 5. Building operations
# ---------------------------------------------------------------------------

def json_content(schema: Dict[str, Any], example: Any = None) -> Dict[str, Any]:
    media_type: Dict[str, Any] = {"schema": schema}
    if example is not None:
        media_type["example"] = example

    return {
        "application/json": media_type
    }


def build_user_operations() -> Dict[str, Any]:
    return {
        "get": {
            "tags": ["Users"],
            "summary": "Get a user",
            "description": (
                "Returns one user identified by the user_id path parameter."
            ),
            "operationId": "getUser",
            "parameters": [
                {"$ref": "#/components/parameters/UserId"}
            ],
            "responses": {
                "200": {
                    "description": "User returned successfully.",
                    "content": json_content(
                        {"$ref": ref("User")},
                        {
                            "id": 101,
                            "name": "Atul Pandey",
                            "email": "atul@example.com",
                            "status": "active",
                            "roles": ["reader"],
                        },
                    ),
                },
                "400": {"$ref": "#/components/responses/BadRequest"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "500": {"$ref": "#/components/responses/ServerError"},
            },
            "security": [{"bearerAuth": []}],
        },
        "delete": {
            "tags": ["Users"],
            "summary": "Delete a user",
            "description": (
                "Deletes the user. A successful deletion returns no response body."
            ),
            "operationId": "deleteUser",
            "parameters": [
                {"$ref": "#/components/parameters/UserId"}
            ],
            "responses": {
                "204": {
                    "description": "User deleted successfully."
                },
                "400": {"$ref": "#/components/responses/BadRequest"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
            "security": [{"bearerAuth": []}],
        },
    }


def build_users_collection_operations() -> Dict[str, Any]:
    return {
        "get": {
            "tags": ["Users"],
            "summary": "List users",
            "description": (
                "Returns a paginated collection of users. Pagination prevents "
                "large collections from being transferred in one response."
            ),
            "operationId": "listUsers",
            "parameters": [
                {"$ref": "#/components/parameters/Page"},
                {"$ref": "#/components/parameters/PageSize"},
            ],
            "responses": {
                "200": {
                    "description": "Users returned successfully.",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["items", "page", "page_size"],
                                "properties": {
                                    "items": {
                                        "type": "array",
                                        "items": {"$ref": ref("User")},
                                    },
                                    "page": {
                                        "type": "integer",
                                        "minimum": 1,
                                    },
                                    "page_size": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 100,
                                    },
                                },
                            },
                            "example": {
                                "items": [
                                    {
                                        "id": 101,
                                        "name": "Atul Pandey",
                                        "email": "atul@example.com",
                                        "status": "active",
                                        "roles": ["reader"],
                                    }
                                ],
                                "page": 1,
                                "page_size": 20,
                            },
                        }
                    },
                },
                "400": {"$ref": "#/components/responses/BadRequest"},
            },
            "security": [{"bearerAuth": []}],
        },
        "post": {
            "tags": ["Users"],
            "summary": "Create a user",
            "description": (
                "Creates a user and returns the newly created resource."
            ),
            "operationId": "createUser",
            "requestBody": {
                "required": True,
                "description": "User information required for creation.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": ref("UserCreate")},
                        "example": {
                            "name": "New User",
                            "email": "new@example.com",
                            "roles": ["reader"],
                        },
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "User created successfully.",
                    "content": json_content({"$ref": ref("User")}),
                },
                "400": {"$ref": "#/components/responses/BadRequest"},
            },
            "security": [{"bearerAuth": []}],
        },
    }


# ---------------------------------------------------------------------------
# 6. Complete OpenAPI document
# ---------------------------------------------------------------------------

def build_openapi_document() -> Dict[str, Any]:
    """
    Construct an OpenAPI 3.0 document.

    Important structural relationships:

        openapi
        info
        servers
        tags
        paths
        components
            schemas
            parameters
            responses
            securitySchemes

    The specification is data. Swagger UI and ReDoc can consume the same data
    and turn it into human-readable documentation.
    """
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "User Management API",
            "version": "1.0.0",
            "description": (
                "A documented example API demonstrating OpenAPI metadata, "
                "schemas, operations, reusable components, and security."
            ),
            "contact": {
                "name": "API Engineering Team",
                "email": "api@example.com",
            },
            "license": {
                "name": "Apache 2.0",
            },
        },
        "externalDocs": {
            "description": "API engineering documentation",
            "url": "https://example.com/docs",
        },
        "servers": [
            {
                "url": "https://api.example.com/v1",
                "description": "Production",
            },
            {
                "url": "https://staging-api.example.com/v1",
                "description": "Staging",
            },
            {
                "url": "http://localhost:8000/v1",
                "description": "Local development",
            },
        ],
        "tags": [
            {
                "name": "Users",
                "description": "Operations for managing users.",
            },
            {
                "name": "Health",
                "description": "Service health information.",
            },
        ],
        "paths": {
            "/users": build_users_collection_operations(),
            "/users/{user_id}": build_user_operations(),
            "/health": {
                "get": {
                    "tags": ["Health"],
                    "summary": "Check service health",
                    "description": "Returns a lightweight service health document.",
                    "operationId": "getHealth",
                    "responses": {
                        "200": {
                            "description": "Service health returned.",
                            "content": json_content(
                                {"$ref": ref("HealthStatus")},
                                {
                                    "status": "ok",
                                    "service": "user-api",
                                    "version": "1.0.0",
                                },
                            ),
                        }
                    },
                }
            },
        },
        "components": build_components(),
        "security": [{"bearerAuth": []}],
    }


# ---------------------------------------------------------------------------
# 7. Document inspection and quality checks
# ---------------------------------------------------------------------------

def iter_operations(document: Dict[str, Any]) -> Iterable[
    Tuple[str, str, Dict[str, Any]]
]:
    """Yield path, HTTP method, and operation object."""
    http_methods = {
        "get", "post", "put", "patch", "delete", "head", "options", "trace"
    }

    for path, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() in http_methods:
                yield path, method.lower(), operation


def inspect_operation_ids(document: Dict[str, Any]) -> List[str]:
    ids = []

    for path, method, operation in iter_operations(document):
        operation_id = operation.get("operationId")

        if not operation_id:
            raise ValueError(
                f"Missing operationId for {method.upper()} {path}"
            )

        ids.append(operation_id)

    return ids


def validate_openapi_structure(document: Dict[str, Any]) -> List[str]:
    """
    Perform useful structural checks.

    This is not intended to replace a standards-compliant OpenAPI validator.
    A real production pipeline should use a validator that understands the
    exact OpenAPI version and its complete specification.
    """
    errors: List[str] = []

    if document.get("openapi") not in {"3.0.0", "3.0.1", "3.0.2", "3.0.3"}:
        errors.append("Unsupported or missing OpenAPI 3.0 version.")

    info = document.get("info")
    if not isinstance(info, dict):
        errors.append("info must be an object.")
    else:
        if not info.get("title"):
            errors.append("info.title is required.")
        if not info.get("version"):
            errors.append("info.version is required.")

    if not isinstance(document.get("paths"), dict):
        errors.append("paths must be an object.")

    operation_ids: Dict[str, str] = {}

    for path, method, operation in iter_operations(document):
        if not path.startswith("/"):
            errors.append(f"Path does not begin with '/': {path}")

        operation_id = operation.get("operationId")
        if not operation_id:
            errors.append(
                f"Missing operationId for {method.upper()} {path}"
            )
        elif operation_id in operation_ids:
            errors.append(
                "Duplicate operationId "
                f"{operation_id!r} used by {operation_ids[operation_id]} "
                f"and {method.upper()} {path}"
            )
        else:
            operation_ids[operation_id] = f"{method.upper()} {path}"

        responses = operation.get("responses")
        if not isinstance(responses, dict) or not responses:
            errors.append(
                f"{method.upper()} {path} must document at least one response."
            )

    components = document.get("components", {})
    schemas = components.get("schemas", {})
    if not isinstance(schemas, dict):
        errors.append("components.schemas must be an object.")

    return errors


def show_api_inventory(document: Dict[str, Any]) -> None:
    print_section("4. API inventory")

    print(f"OpenAPI version: {document['openapi']}")
    print(f"Title: {document['info']['title']}")
    print(f"API version: {document['info']['version']}")

    print("\nServers:")
    for server in document.get("servers", []):
        print(f"  - {server['description']}: {server['url']}")

    print("\nOperations:")
    for path, method, operation in iter_operations(document):
        print(
            f"  {method.upper():6} {path:22} "
            f"operationId={operation.get('operationId')}"
        )


# ---------------------------------------------------------------------------
# 8. JSON Pointer and $ref resolution
# ---------------------------------------------------------------------------

def resolve_local_ref(document: Dict[str, Any], reference: str) -> Any:
    """
    Resolve a local reference such as:

        #/components/schemas/User

    This demonstrates why $ref makes large API documents manageable.
    """
    if not reference.startswith("#/"):
        raise ValueError("This educational resolver supports only local $ref.")

    current: Any = document

    for token in reference[2:].split("/"):
        # JSON Pointer escapes:
        # ~1 represents "/" and ~0 represents "~".
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise KeyError(f"Unable to resolve reference token: {token}")
        current = current[token]

    return current


def demonstrate_refs(document: Dict[str, Any]) -> None:
    print_section("5. Reusable schemas and $ref")

    user_reference = document["paths"]["/users/{user_id}"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]["$ref"]

    resolved_schema = resolve_local_ref(document, user_reference)

    print("Reference:")
    print(f"  {user_reference}")

    print("\nResolved schema:")
    print(pretty_json(resolved_schema))


# ---------------------------------------------------------------------------
# 9. Examples of good and bad operation IDs
# ---------------------------------------------------------------------------

def demonstrate_operation_id_rules() -> None:
    print_section("6. operationId design")

    examples = {
        "good": [
            "getUser",
            "listUsers",
            "createUser",
            "deleteUser",
            "getHealth",
        ],
        "problematic": [
            "get",
            "operation1",
            "GET /users",
            "user",
            "thing",
        ],
    }

    print("Useful operationId characteristics:")
    print("  - unique within the API document")
    print("  - stable")
    print("  - descriptive")
    print("  - easy for code generators to turn into method names")
    print("  - not dependent on accidental wording in a UI")

    print("\nExamples:")
    for category, values in examples.items():
        print(f"  {category}:")
        for value in values:
            print(f"    - {value}")


# ---------------------------------------------------------------------------
# 10. HTTP method semantics
# ---------------------------------------------------------------------------

def demonstrate_http_semantics() -> None:
    print_section("7. HTTP method semantics")

    methods = [
        ("GET", "Retrieve a representation; normally safe and idempotent."),
        ("POST", "Submit data or request creation/action; generally not idempotent."),
        ("PUT", "Replace a resource representation; normally idempotent."),
        ("PATCH", "Partially modify a resource; idempotency depends on the design."),
        ("DELETE", "Remove a resource; normally treated as idempotent."),
        ("HEAD", "Retrieve response metadata without the response body."),
        ("OPTIONS", "Discover communication options supported by a target."),
    ]

    for method, meaning in methods:
        print(f"{method:8} {meaning}")


# ---------------------------------------------------------------------------
# 11. Parameters and request bodies
# ---------------------------------------------------------------------------

def demonstrate_parameter_locations() -> None:
    print_section("8. Parameter locations")

    parameters = {
        "path": {
            "name": "user_id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer"},
        },
        "query": {
            "name": "page",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "minimum": 1},
        },
        "header": {
            "name": "X-Request-ID",
            "in": "header",
            "required": False,
            "schema": {"type": "string"},
        },
        "cookie": {
            "name": "session_id",
            "in": "cookie",
            "required": False,
            "schema": {"type": "string"},
        },
    }

    for location, parameter in parameters.items():
        print(f"\n{location.upper()}:")
        print(pretty_json(parameter))

    print(
        "\nA request body is different from a parameter. "
        "It normally describes structured content sent with methods such as "
        "POST, PUT, and PATCH."
    )


# ---------------------------------------------------------------------------
# 12. Status codes
# ---------------------------------------------------------------------------

def demonstrate_status_codes() -> None:
    print_section("9. HTTP responses and status codes")

    status_codes = {
        "200": "Successful request with a response representation.",
        "201": "Resource successfully created.",
        "202": "Request accepted for asynchronous processing.",
        "204": "Successful request with no response body.",
        "400": "The request is invalid.",
        "401": "Authentication is required or invalid.",
        "403": "The authenticated caller is not allowed to perform the operation.",
        "404": "The requested resource does not exist.",
        "409": "The request conflicts with current resource state.",
        "422": "The server understands the request but rejects its content.",
        "429": "Too many requests according to a rate limit.",
        "500": "Unexpected server-side failure.",
        "503": "Service temporarily unavailable.",
    }

    for code, meaning in status_codes.items():
        print(f"{code}: {meaning}")


# ---------------------------------------------------------------------------
# 13. Security schemes
# ---------------------------------------------------------------------------

def demonstrate_security() -> None:
    print_section("10. API security documentation")

    schemes = {
        "API key": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        },
        "HTTP bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "Basic authentication": {
            "type": "http",
            "scheme": "basic",
        },
        "OAuth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://example.com/oauth/authorize",
                    "tokenUrl": "https://example.com/oauth/token",
                    "scopes": {
                        "users:read": "Read users",
                        "users:write": "Modify users",
                    },
                }
            },
        },
    }

    for name, scheme in schemes.items():
        print_subsection(name)
        print(pretty_json(scheme))

    print(
        "\nDocumentation describes how clients authenticate. "
        "Documentation itself does not enforce authentication."
    )


# ---------------------------------------------------------------------------
# 14. Swagger UI and ReDoc HTML generation
# ---------------------------------------------------------------------------

def create_swagger_ui_html(spec_url: str = "./openapi.json") -> str:
    """
    Generate a minimal HTML page that loads Swagger UI from a CDN.

    In a production system, the exact asset version should be pinned rather
    than depending blindly on an unversioned resource.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>User Management API - Swagger UI</title>
  <link rel="stylesheet"
        href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function () {{
      SwaggerUIBundle({{
        url: "{spec_url}",
        dom_id: "#swagger-ui"
      }});
    }};
  </script>
</body>
</html>
"""


def create_redoc_html(spec_url: str = "./openapi.json") -> str:
    """
    Generate a minimal ReDoc documentation page.

    Swagger UI emphasizes interactive exploration. ReDoc generally emphasizes
    structured reference-style presentation.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>User Management API - ReDoc</title>
</head>
<body>
  <redoc spec-url="{spec_url}"></redoc>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


def demonstrate_documentation_renderers(document: Dict[str, Any]) -> None:
    print_section("11. Swagger UI and ReDoc")

    swagger_html = create_swagger_ui_html()
    redoc_html = create_redoc_html()

    print("Swagger UI integration:")
    print("  - Browser loads the OpenAPI document.")
    print("  - Swagger UI renders operations, parameters, schemas, and responses.")
    print("  - Try-it-out functionality can send requests when configured.")

    print("\nGenerated Swagger UI page length:", len(swagger_html))
    print("Generated ReDoc page length:", len(redoc_html))

    # Keep a small excerpt visible without dumping a large HTML document.
    print("\nSwagger UI HTML excerpt:")
    print(swagger_html[:500] + "...")

    print("\nReDoc HTML excerpt:")
    print(redoc_html[:400] + "...")


# ---------------------------------------------------------------------------
# 15. Documentation quality analysis
# ---------------------------------------------------------------------------

@dataclass
class DocumentationIssue:
    severity: str
    location: str
    message: str


def audit_documentation(document: Dict[str, Any]) -> List[DocumentationIssue]:
    issues: List[DocumentationIssue] = []

    for path, method, operation in iter_operations(document):
        location = f"{method.upper()} {path}"

        if not operation.get("summary"):
            issues.append(
                DocumentationIssue(
                    "warning",
                    location,
                    "Missing concise summary.",
                )
            )

        if not operation.get("description"):
            issues.append(
                DocumentationIssue(
                    "warning",
                    location,
                    "Missing detailed description.",
                )
            )

        operation_id = operation.get("operationId")
        if not operation_id:
            issues.append(
                DocumentationIssue(
                    "error",
                    location,
                    "Missing operationId.",
                )
            )

        if not operation.get("responses"):
            issues.append(
                DocumentationIssue(
                    "error",
                    location,
                    "No responses documented.",
                )
            )

        for status_code, response in operation.get("responses", {}).items():
            if isinstance(response, dict):
                if not response.get("description"):
                    issues.append(
                        DocumentationIssue(
                            "warning",
                            f"{location} -> {status_code}",
                            "Response is missing description.",
                        )
                    )

    return issues


def demonstrate_documentation_audit(document: Dict[str, Any]) -> None:
    print_section("12. Documentation quality audit")

    issues = audit_documentation(document)

    if not issues:
        print("No documentation quality issues were found.")
        return

    for issue in issues:
        print(
            f"[{issue.severity.upper():7}] "
            f"{issue.location}: {issue.message}"
        )


# ---------------------------------------------------------------------------
# 16. API versioning
# ---------------------------------------------------------------------------

def demonstrate_versioning() -> None:
    print_section("13. API versioning")

    approaches = [
        (
            "URL versioning",
            "/v1/users",
            "Version is visible in the URL and easy for clients to understand.",
        ),
        (
            "Header versioning",
            "Accept: application/vnd.example.v1+json",
            "Version is expressed through HTTP headers.",
        ),
        (
            "Media-type versioning",
            "Accept: application/vnd.example.user-v1+json",
            "Different representations are negotiated through media types.",
        ),
    ]

    for approach, example, tradeoff in approaches:
        print(f"{approach}:")
        print(f"  Example: {example}")
        print(f"  Consideration: {tradeoff}\n")


# ---------------------------------------------------------------------------
# 17. Edge cases and subtle documentation problems
# ---------------------------------------------------------------------------

def demonstrate_edge_cases() -> None:
    print_section("14. Edge cases and subtle problems")

    cases = [
        (
            "Duplicate operationId",
            "Code generators may produce conflicting method names.",
        ),
        (
            "Undocumented error response",
            "Clients may not know how validation, authentication, or missing-resource failures are represented.",
        ),
        (
            "Schema differs from actual JSON",
            "Generated clients can become incorrect even though the documentation page looks valid.",
        ),
        (
            "Missing required path parameter",
            "A path template such as /users/{user_id} requires a matching path parameter definition.",
        ),
        (
            "Ambiguous nullable behavior",
            "Whether null is accepted must be documented explicitly according to the OpenAPI version and schema vocabulary.",
        ),
        (
            "Unstable operationId",
            "Changing operationId can change generated SDK method names and break downstream source code.",
        ),
        (
            "Incorrect security documentation",
            "A documented authentication mechanism must correspond to the actual server behavior.",
        ),
        (
            "Huge schemas",
            "Excessively large schemas make generated documentation difficult to navigate and clients harder to understand.",
        ),
        (
            "Examples that violate schemas",
            "Interactive documentation can show misleading examples if example payloads are inconsistent with their schemas.",
        ),
    ]

    for name, consequence in cases:
        print(f"{name}:")
        print(f"  {consequence}")


# ---------------------------------------------------------------------------
# 18. Performance and production considerations
# ---------------------------------------------------------------------------

def demonstrate_production_considerations() -> None:
    print_section("15. Performance and production considerations")

    considerations = [
        "Keep the OpenAPI document deterministic so diffs are meaningful.",
        "Reuse schemas with components and $ref instead of copying definitions.",
        "Avoid enormous examples that make documentation slow to load.",
        "Pin frontend documentation asset versions in production.",
        "Serve documentation over HTTPS.",
        "Do not expose internal credentials, tokens, database details, or secrets.",
        "Decide whether interactive request execution should be available in production.",
        "Ensure CORS configuration is compatible with the hosted documentation UI.",
        "Generate documentation from the same source used by the API when practical.",
        "Validate the specification in CI so documentation drift is detected before release.",
        "Treat the OpenAPI document as a versioned API contract.",
        "Review breaking changes before changing schemas, status codes, or operationIds.",
    ]

    for item in considerations:
        print(f"- {item}")


# ---------------------------------------------------------------------------
# 19. Contract testing demonstration
# ---------------------------------------------------------------------------

@dataclass
class SimulatedResponse:
    status_code: int
    body: Any


def simulate_get_user(user_id: int) -> SimulatedResponse:
    """
    A tiny simulated API endpoint.

    This is not an HTTP server. It demonstrates how an implementation can be
    checked against the documented response schemas.
    """
    if user_id <= 0:
        return SimulatedResponse(
            400,
            {
                "code": "INVALID_USER_ID",
                "message": "user_id must be positive",
                "details": {},
            },
        )

    if user_id == 404:
        return SimulatedResponse(
            404,
            {
                "code": "USER_NOT_FOUND",
                "message": "The requested user does not exist.",
                "details": {},
            },
        )

    return SimulatedResponse(
        200,
        {
            "id": user_id,
            "name": "Example User",
            "email": "example@example.com",
            "status": "active",
            "roles": ["reader"],
        },
    )


def demonstrate_contract_testing(document: Dict[str, Any]) -> None:
    print_section("16. Contract-oriented testing")

    get_user_operation = document["paths"]["/users/{user_id}"]["get"]
    response_schema = get_user_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    resolved_response_schema = resolve_local_ref(document, response_schema["$ref"])

    for user_id in [101, 404, 0]:
        response = simulate_get_user(user_id)
        print(
            f"\nGET /users/{user_id} -> HTTP {response.status_code}"
        )

        if response.status_code == 200:
            try:
                validate_schema(
                    response.body,
                    resolved_response_schema,
                )
                print("Response matches documented User schema.")
            except SchemaValidationError as error:
                print("Schema mismatch:", error)
        else:
            print("Error response:", pretty_json(response.body))


# ---------------------------------------------------------------------------
# 20. Schema evolution
# ---------------------------------------------------------------------------

def demonstrate_schema_evolution() -> None:
    print_section("17. Schema evolution")

    old_schema = {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
        },
    }

    additive_schema = {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "display_name": {"type": "string"},
        },
    }

    breaking_schema = {
        "type": "object",
        "required": ["id", "name", "email"],
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "email": {"type": "string", "format": "email"},
        },
    }

    print("Original required fields:", old_schema["required"])
    print("Additive change:", additive_schema["required"])
    print("Potentially breaking change:", breaking_schema["required"])

    print(
        "\nA new optional field can often be introduced without forcing existing "
        "clients to send it. Making a previously optional field required can "
        "break clients that still send the older representation."
    )


# ---------------------------------------------------------------------------
# 21. Main study program
# ---------------------------------------------------------------------------

def main() -> None:
    explain_basic_terms()
    demonstrate_schema_examples()
    demonstrate_runtime_validation()

    document = build_openapi_document()

    show_api_inventory(document)
    demonstrate_refs(document)
    demonstrate_operation_id_rules()
    demonstrate_http_semantics()
    demonstrate_parameter_locations()
    demonstrate_status_codes()
    demonstrate_security()
    demonstrate_documentation_renderers(document)
    demonstrate_documentation_audit(document)
    demonstrate_versioning()
    demonstrate_edge_cases()
    demonstrate_production_considerations()
    demonstrate_contract_testing(document)
    demonstrate_schema_evolution()

    print_section("18. Complete generated OpenAPI document")

    print(
        "The following JSON is suitable as the conceptual content of an "
        "openapi.json file:"
    )
    print(pretty_json(document))

    print_section("19. Final structural checks")

    errors = validate_openapi_structure(document)

    if errors:
        print("OpenAPI structure contains issues:")
        for error in errors:
            print("  -", error)
    else:
        print("Basic structural checks passed.")

    operation_ids = inspect_operation_ids(document)

    if len(operation_ids) == len(set(operation_ids)):
        print("All operationIds are unique.")
    else:
        print("Duplicate operationIds detected.")

    print("\nDocumented operations:", len(operation_ids))
    print("Reusable schemas:", len(document["components"]["schemas"]))
    print("Reusable parameters:", len(document["components"]["parameters"]))
    print("Reusable responses:", len(document["components"]["responses"]))
    print(
        "Security schemes:",
        len(document["components"]["securitySchemes"]),
    )

    print(
        "\nStudy note: an OpenAPI document describes an API contract. "
        "Swagger UI and ReDoc are consumers of that contract, while runtime "
        "validation and contract testing help keep implementation behavior "
        "aligned with the documented interface."
    )


if __name__ == "__main__":
    main()
