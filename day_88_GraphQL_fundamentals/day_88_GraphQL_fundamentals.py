"""
GraphQL Fundamentals: Schemas, Types, Queries, Mutations, and Resolvers

A self-contained GraphQL execution simulator using Python's standard library.

Features:
- Schema and object-type definitions
- Scalar and non-null type validation
- Query and mutation operations
- Resolver registration and execution
- Arguments and nested selections
- Field-level error handling
- Input validation
- Execution context
- Mutation state management
- Query complexity limits
- Execution tracing
- Unit-style assertions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
import json
import logging
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

logger = logging.getLogger("graphql")


# ---------------------------------------------------------
# 1. GraphQL type system
# ---------------------------------------------------------

class GraphQLScalar(Enum):
    STRING = "String"
    INTEGER = "Int"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    ID = "ID"


@dataclass(frozen=True)
class NonNull:
    inner: Any


@dataclass(frozen=True)
class ListType:
    inner: Any


@dataclass
class ObjectType:
    name: str
    fields: dict[str, "FieldDefinition"] = field(default_factory=dict)


@dataclass
class FieldDefinition:
    type: Any
    resolver: Callable | None = None
    description: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    user_id: str | None = None
    roles: set[str] = field(default_factory=set)
    request_id: str = "request-001"


class GraphQLError(Exception):
    def __init__(self, message: str, path: list | None = None):
        super().__init__(message)
        self.path = path or []


# ---------------------------------------------------------
# 2. Type validation
# ---------------------------------------------------------

def validate_value(value: Any, expected: Any, path: str = "value") -> None:
    if isinstance(expected, NonNull):
        if value is None:
            raise GraphQLError(f"{path} cannot be null")
        validate_value(value, expected.inner, path)
        return

    if value is None:
        return

    if isinstance(expected, ListType):
        if not isinstance(value, list):
            raise GraphQLError(f"{path} must be a list")

        for index, item in enumerate(value):
            validate_value(item, expected.inner, f"{path}[{index}]")
        return

    if isinstance(expected, ObjectType):
        if not isinstance(value, dict):
            raise GraphQLError(f"{path} must be an object")
        return

    checks = {
        GraphQLScalar.STRING: lambda v: isinstance(v, str),
        GraphQLScalar.INTEGER: lambda v: (
            isinstance(v, int) and not isinstance(v, bool)
        ),
        GraphQLScalar.FLOAT: lambda v: (
            isinstance(v, (int, float)) and not isinstance(v, bool)
        ),
        GraphQLScalar.BOOLEAN: lambda v: isinstance(v, bool),
        GraphQLScalar.ID: lambda v: isinstance(v, (str, int))
        and not isinstance(v, bool),
    }

    if expected not in checks:
        raise GraphQLError(f"Unsupported GraphQL type: {expected}")

    if not checks[expected](value):
        raise GraphQLError(
            f"{path} must be {expected.value}"
        )


# ---------------------------------------------------------
# 3. Domain model
# ---------------------------------------------------------

@dataclass
class User:
    id: str
    name: str
    email: str


@dataclass
class Product:
    id: str
    name: str
    price: float
    stock: int


@dataclass
class Order:
    id: str
    user_id: str
    product_id: str
    quantity: int
    status: str


class Store:
    def __init__(self):
        self.users = {
            "1": User("1", "Aarav Sharma", "aarav@example.com"),
            "2": User("2", "Meera Singh", "meera@example.com"),
        }

        self.products = {
            "101": Product("101", "Laptop", 75000.0, 8),
            "102": Product("102", "Keyboard", 2500.0, 20),
        }

        self.orders: dict[str, Order] = {}
        self.next_order_id = 1

    def create_order(
        self,
        user_id: str,
        product_id: str,
        quantity: int
    ) -> Order:

        if user_id not in self.users:
            raise GraphQLError("User does not exist")

        if product_id not in self.products:
            raise GraphQLError("Product does not exist")

        if quantity <= 0:
            raise GraphQLError("Quantity must be positive")

        product = self.products[product_id]

        if product.stock < quantity:
            raise GraphQLError("Insufficient inventory")

        # Update inventory and create the order as one operation.
        product.stock -= quantity

        order = Order(
            id=str(self.next_order_id),
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            status="CONFIRMED"
        )

        self.orders[order.id] = order
        self.next_order_id += 1

        return order


# ---------------------------------------------------------
# 4. GraphQL schema
# ---------------------------------------------------------

class GraphQLSchema:
    def __init__(self):
        self.types: dict[str, ObjectType] = {}
        self.query = ObjectType("Query")
        self.mutation = ObjectType("Mutation")

    def register_type(self, object_type: ObjectType):
        if object_type.name in self.types:
            raise GraphQLError(
                f"Duplicate type: {object_type.name}"
            )

        self.types[object_type.name] = object_type

    def validate_schema(self):
        for object_type in self.types.values():
            for field_name, definition in object_type.fields.items():
                if not field_name:
                    raise GraphQLError("Field names cannot be empty")

                for argument_name, argument_type in definition.arguments.items():
                    if not argument_name:
                        raise GraphQLError("Argument names cannot be empty")

                    if not isinstance(argument_type, (
                        GraphQLScalar, NonNull, ListType
                    )):
                        raise GraphQLError(
                            f"Invalid argument type: {argument_name}"
                        )


# ---------------------------------------------------------
# 5. GraphQL execution engine
# ---------------------------------------------------------

class GraphQLExecutor:
    def __init__(
        self,
        schema: GraphQLSchema,
        context: ExecutionContext,
        max_depth: int = 5,
        max_fields: int = 30
    ):
        self.schema = schema
        self.context = context
        self.max_depth = max_depth
        self.max_fields = max_fields
        self.field_count = 0

    def _resolve_field(
        self,
        source: Any,
        field_name: str,
        arguments: dict,
        definition: FieldDefinition
    ):
        resolver = definition.resolver

        if resolver is None:
            if isinstance(source, dict):
                return source.get(field_name)

            return getattr(source, field_name, None)

        return resolver(
            source,
            arguments,
            self.context
        )

    def _complete_value(
        self,
        value: Any,
        expected_type: Any,
        selection: dict | None,
        depth: int
    ):
        if isinstance(expected_type, NonNull):
            if value is None:
                raise GraphQLError("Non-null field returned null")

            return self._complete_value(
                value,
                expected_type.inner,
                selection,
                depth
            )

        if value is None:
            return None

        if isinstance(expected_type, ListType):
            if not isinstance(value, (list, tuple)):
                raise GraphQLError("Expected a list result")

            return [
                self._complete_value(
                    item,
                    expected_type.inner,
                    selection,
                    depth + 1
                )
                for item in value
            ]

        if isinstance(expected_type, ObjectType):
            if selection is None:
                raise GraphQLError(
                    f"Object {expected_type.name} requires a selection"
                )

            return self._execute_selection(
                value,
                expected_type,
                selection,
                depth + 1
            )

        if selection is not None:
            raise GraphQLError(
                "Scalar fields cannot have nested selections"
            )

        validate_value(value, expected_type)
        return value

    def _execute_selection(
        self,
        source: Any,
        object_type: ObjectType,
        selection: dict,
        depth: int
    ) -> dict:

        if depth > self.max_depth:
            raise GraphQLError("Maximum query depth exceeded")

        result = {}

        for field_name, field_request in selection.items():
            self.field_count += 1

            if self.field_count > self.max_fields:
                raise GraphQLError("Maximum field count exceeded")

            if field_name not in object_type.fields:
                raise GraphQLError(
                    f"Unknown field: {object_type.name}.{field_name}"
                )

            definition = object_type.fields[field_name]

            if isinstance(field_request, dict):
                arguments = field_request.get("args", {})
                nested_selection = field_request.get("select")
            else:
                arguments = {}
                nested_selection = None

            if not isinstance(arguments, dict):
                raise GraphQLError(
                    f"Arguments for {field_name} must be an object"
                )

            unknown_arguments = (
                set(arguments) - set(definition.arguments)
            )

            if unknown_arguments:
                raise GraphQLError(
                    f"Unknown arguments for {field_name}: "
                    f"{sorted(unknown_arguments)}"
                )

            for argument_name, argument_type in definition.arguments.items():
                if argument_name not in arguments:
                    if isinstance(argument_type, NonNull):
                        raise GraphQLError(
                            f"Missing required argument: {argument_name}"
                        )
                    continue

                validate_value(
                    arguments[argument_name],
                    argument_type,
                    argument_name
                )

            try:
                value = self._resolve_field(
                    source,
                    field_name,
                    arguments,
                    definition
                )

                result[field_name] = self._complete_value(
                    value,
                    definition.type,
                    nested_selection,
                    depth
                )

            except Exception as exc:
                raise GraphQLError(
                    f"Resolver failed for {field_name}: {exc}",
                    [field_name]
                ) from exc

        return result

    def execute(self, operation: str, selection: dict) -> dict:
        started = time.perf_counter()
        self.field_count = 0

        if not isinstance(selection, dict):
            return {
                "data": None,
                "errors": ["Selection must be an object"]
            }

        if operation == "query":
            root = self.schema.query
        elif operation == "mutation":
            root = self.schema.mutation
        else:
            return {
                "data": None,
                "errors": ["Operation must be query or mutation"]
            }

        try:
            data = self._execute_selection(
                None,
                root,
                selection,
                0
            )

            return {
                "data": data,
                "errors": [],
                "extensions": {
                    "fieldsExecuted": self.field_count,
                    "durationMs": round(
                        (time.perf_counter() - started) * 1000,
                        3
                    ),
                    "requestId": self.context.request_id
                }
            }

        except GraphQLError as exc:
            return {
                "data": None,
                "errors": [{
                    "message": str(exc),
                    "path": exc.path
                }]
            }


# ---------------------------------------------------------
# 6. Build application schema and resolvers
# ---------------------------------------------------------

def build_application():
    store = Store()
    schema = GraphQLSchema()

    user_type = ObjectType("User")
    product_type = ObjectType("Product")
    order_type = ObjectType("Order")

    user_type.fields = {
        "id": FieldDefinition(GraphQLScalar.ID),
        "name": FieldDefinition(GraphQLScalar.STRING),
        "email": FieldDefinition(GraphQLScalar.STRING),
    }

    product_type.fields = {
        "id": FieldDefinition(GraphQLScalar.ID),
        "name": FieldDefinition(GraphQLScalar.STRING),
        "price": FieldDefinition(GraphQLScalar.FLOAT),
        "stock": FieldDefinition(GraphQLScalar.INTEGER),
    }

    order_type.fields = {
        "id": FieldDefinition(GraphQLScalar.ID),
        "quantity": FieldDefinition(GraphQLScalar.INTEGER),
        "status": FieldDefinition(GraphQLScalar.STRING),
        "user": FieldDefinition(
            user_type,
            resolver=lambda order, args, ctx:
                store.users.get(order.user_id)
        ),
        "product": FieldDefinition(
            product_type,
            resolver=lambda order, args, ctx:
                store.products.get(order.product_id)
        ),
    }

    schema.register_type(user_type)
    schema.register_type(product_type)
    schema.register_type(order_type)

    schema.query.fields = {
        "users": FieldDefinition(
            ListType(user_type),
            resolver=lambda source, args, ctx:
                list(store.users.values())
        ),
        "user": FieldDefinition(
            user_type,
            resolver=lambda source, args, ctx:
                store.users.get(str(args["id"])),
            arguments={
                "id": NonNull(GraphQLScalar.ID)
            }
        ),
        "products": FieldDefinition(
            ListType(product_type),
            resolver=lambda source, args, ctx:
                list(store.products.values())
        ),
        "product": FieldDefinition(
            product_type,
            resolver=lambda source, args, ctx:
                store.products.get(str(args["id"])),
            arguments={
                "id": NonNull(GraphQLScalar.ID)
            }
        ),
        "orders": FieldDefinition(
            ListType(order_type),
            resolver=lambda source, args, ctx:
                list(store.orders.values())
        ),
    }

    def create_order_resolver(source, args, context):
        if context.user_id is None:
            raise GraphQLError("Authentication required")

        if "CUSTOMER" not in context.roles:
            raise GraphQLError("Customer role required")

        return store.create_order(
            str(args["userId"]),
            str(args["productId"]),
            args["quantity"]
        )

    schema.mutation.fields = {
        "createOrder": FieldDefinition(
            order_type,
            resolver=create_order_resolver,
            arguments={
                "userId": NonNull(GraphQLScalar.ID),
                "productId": NonNull(GraphQLScalar.ID),
                "quantity": NonNull(GraphQLScalar.INTEGER)
            }
        )
    }

    schema.validate_schema()

    return schema, store


# ---------------------------------------------------------
# 7. Demonstration and tests
# ---------------------------------------------------------

def main():
    schema, store = build_application()

    context = ExecutionContext(
        user_id="1",
        roles={"CUSTOMER"},
        request_id="req-graphql-001"
    )

    executor = GraphQLExecutor(schema, context)

    print("\nGRAPHQL FUNDAMENTALS DEMONSTRATION")

    print("\n1. QUERY: Retrieve products")

    product_query = {
        "products": {
            "select": {
                "id": None,
                "name": None,
                "price": None,
                "stock": None
            }
        }
    }

    query_result = executor.execute("query", product_query)
    print(json.dumps(query_result, indent=2))

    assert not query_result["errors"]
    assert len(query_result["data"]["products"]) == 2

    print("\n2. QUERY: Retrieve one user")

    user_query = {
        "user": {
            "args": {"id": "1"},
            "select": {
                "id": None,
                "name": None,
                "email": None
            }
        }
    }

    user_result = executor.execute("query", user_query)
    print(json.dumps(user_result, indent=2))

    assert user_result["data"]["user"]["name"] == "Aarav Sharma"

    print("\n3. MUTATION: Create an order")

    mutation = {
        "createOrder": {
            "args": {
                "userId": "1",
                "productId": "101",
                "quantity": 2
            },
            "select": {
                "id": None,
                "quantity": None,
                "status": None,
                "user": {
                    "select": {
                        "name": None
                    }
                },
                "product": {
                    "select": {
                        "name": None,
                        "price": None
                    }
                }
            }
        }
    }

    mutation_result = executor.execute("mutation", mutation)
    print(json.dumps(mutation_result, indent=2))

    assert not mutation_result["errors"]
    assert store.products["101"].stock == 6

    print("\n4. ERROR: Invalid quantity")

    invalid_mutation = {
        "createOrder": {
            "args": {
                "userId": "1",
                "productId": "101",
                "quantity": -1
            },
            "select": {
                "id": None
            }
        }
    }

    invalid_result = executor.execute(
        "mutation",
        invalid_mutation
    )

    print(json.dumps(invalid_result, indent=2))
    assert invalid_result["errors"]

    print("\n5. ERROR: Unknown field")

    invalid_query = {
        "unknownField": None
    }

    unknown_result = executor.execute("query", invalid_query)
    print(json.dumps(unknown_result, indent=2))

    assert unknown_result["errors"]

    print("\n6. ERROR: Missing required argument")

    missing_argument = {
        "user": {
            "select": {
                "id": None
            }
        }
    }

    missing_result = executor.execute(
        "query",
        missing_argument
    )

    print(json.dumps(missing_result, indent=2))
    assert missing_result["errors"]

    print("\n7. ERROR: Authentication")

    unauthenticated_executor = GraphQLExecutor(
        schema,
        ExecutionContext()
    )

    auth_result = unauthenticated_executor.execute(
        "mutation",
        mutation
    )

    print(json.dumps(auth_result, indent=2))
    assert auth_result["errors"]

    print("\n8. QUERY COMPLEXITY LIMIT")

    restricted_executor = GraphQLExecutor(
        schema,
        context,
        max_fields=1
    )

    complexity_result = restricted_executor.execute(
        "query",
        product_query
    )

    print(json.dumps(complexity_result, indent=2))
    assert complexity_result["errors"]

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
