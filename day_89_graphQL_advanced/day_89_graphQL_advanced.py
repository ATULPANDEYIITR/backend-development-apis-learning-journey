from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable
import json
import logging
import time


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("graphql_advanced")


# ============================================================
# GRAPHQL ADVANCED EXECUTION MODEL
# Nested Queries, Fragments, Variables, Authorization, N+1
# ============================================================

class GraphQLError(Exception):
    """Base exception for GraphQL execution failures."""


class ValidationError(GraphQLError):
    pass


class AuthorizationError(GraphQLError):
    pass


class AuthenticationError(GraphQLError):
    pass


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    USER = "USER"
    GUEST = "GUEST"


@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str
    role: UserRole
    active: bool = True


@dataclass(frozen=True)
class Post:
    id: int
    title: str
    body: str
    author_id: int
    published: bool


@dataclass(frozen=True)
class Comment:
    id: int
    post_id: int
    author_id: int
    content: str


@dataclass
class RequestContext:
    user: User | None
    request_id: str
    loaders: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Variable:
    name: str


@dataclass
class Selection:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    children: list["Selection"] = field(default_factory=list)
    alias: str | None = None


@dataclass
class Fragment:
    name: str
    type_condition: str
    selections: list[Selection]


@dataclass
class Operation:
    selections: list[Selection]
    variables: dict[str, Any] = field(default_factory=dict)
    fragments: dict[str, Fragment] = field(default_factory=dict)


# ============================================================
# REPOSITORY DATA
# ============================================================

class Repository:
    def __init__(self):
        self.users = {
            1: User(1, "Atul", "atul@example.com", UserRole.ADMIN),
            2: User(2, "Rahul", "rahul@example.com", UserRole.EDITOR),
            3: User(3, "Priya", "priya@example.com", UserRole.USER),
        }

        self.posts = {
            101: Post(101, "GraphQL Architecture",
                      "Schema design and nested execution.", 1, True),
            102: Post(102, "DataLoader Optimization",
                      "Efficient batching and caching.", 2, True),
            103: Post(103, "Private Draft",
                      "Unpublished engineering notes.", 1, False),
        }

        self.comments = {
            1001: Comment(1001, 101, 2, "Excellent explanation."),
            1002: Comment(1002, 101, 3, "Useful implementation."),
            1003: Comment(1003, 102, 1, "Batching reduces database calls."),
        }

        self.database_queries = 0

    def get_user(self, user_id: int) -> User | None:
        self.database_queries += 1
        return self.users.get(user_id)

    def get_post(self, post_id: int) -> Post | None:
        self.database_queries += 1
        return self.posts.get(post_id)

    def get_posts(self, published_only: bool = True) -> list[Post]:
        self.database_queries += 1
        return [
            post for post in self.posts.values()
            if not published_only or post.published
        ]

    def get_comments_by_post_ids(
        self, post_ids: Iterable[int]
    ) -> dict[int, list[Comment]]:
        ids = set(post_ids)
        self.database_queries += 1

        result = defaultdict(list)

        for comment in self.comments.values():
            if comment.post_id in ids:
                result[comment.post_id].append(comment)

        return dict(result)


# ============================================================
# AUTHORIZATION
# ============================================================

class AuthorizationService:

    @staticmethod
    def require_authenticated(context: RequestContext) -> User:
        if context.user is None or not context.user.active:
            raise AuthenticationError("Authentication required.")

        return context.user

    @staticmethod
    def require_role(
        context: RequestContext,
        allowed_roles: set[UserRole]
    ) -> User:
        user = AuthorizationService.require_authenticated(context)

        if user.role not in allowed_roles:
            raise AuthorizationError(
                f"Role {user.role.value} is not authorized."
            )

        return user

    @staticmethod
    def can_read_post(user: User | None, post: Post) -> bool:
        if post.published:
            return True

        return (
            user is not None
            and user.active
            and (
                user.role == UserRole.ADMIN
                or user.id == post.author_id
            )
        )

    @staticmethod
    def can_read_email(
        context: RequestContext,
        target: User
    ) -> bool:
        if context.user is None or not context.user.active:
            return False

        return (
            context.user.role == UserRole.ADMIN
            or context.user.id == target.id
        )


# ============================================================
# DATALOADER
# ============================================================

class DataLoader:
    """
    Collects keys and resolves them in one batch.

    Without batching, resolving comments for N posts can cause
    N database calls.

    With batching, the same operation needs one batch query.
    """

    def __init__(
        self,
        batch_function: Callable[[list[int]], dict[int, Any]]
    ):
        self.batch_function = batch_function
        self.cache: dict[int, Any] = {}
        self.pending: list[int] = []

    def load(self, key: int) -> Any:
        if key in self.cache:
            return self.cache[key]

        self.pending.append(key)
        return None

    def dispatch(self) -> None:
        if not self.pending:
            return

        keys = list(dict.fromkeys(self.pending))
        self.pending.clear()

        results = self.batch_function(keys)

        for key in keys:
            self.cache[key] = results.get(key, [])

    def get(self, key: int) -> Any:
        if key not in self.cache:
            raise GraphQLError("DataLoader key was not dispatched.")

        return self.cache[key]

    def clear(self) -> None:
        self.cache.clear()
        self.pending.clear()


# ============================================================
# GRAPHQL-LIKE SCHEMA AND RESOLVERS
# ============================================================

class GraphQLService:

    def __init__(self, repository: Repository):
        self.repository = repository

        self.field_definitions = {
            "Query": {"posts", "post", "me", "user"},
            "Post": {"id", "title", "body", "published", "author", "comments"},
            "User": {"id", "name", "email", "role", "posts"},
            "Comment": {"id", "content", "author"},
        }

    def validate_field(self, parent_type: str, field_name: str) -> None:
        if field_name not in self.field_definitions.get(parent_type, set()):
            raise ValidationError(
                f"Unknown field '{field_name}' on type '{parent_type}'."
            )

    def resolve_root(
        self,
        selection: Selection,
        arguments: dict[str, Any],
        context: RequestContext
    ) -> Any:

        name = selection.name

        if name == "posts":
            published_only = arguments.get("publishedOnly", True)

            if not isinstance(published_only, bool):
                raise ValidationError("publishedOnly must be Boolean.")

            if not published_only:
                AuthorizationService.require_role(
                    context, {UserRole.ADMIN, UserRole.EDITOR}
                )

            return self.repository.get_posts(published_only)

        if name == "post":
            post_id = arguments.get("id")

            if not isinstance(post_id, int) or isinstance(post_id, bool):
                raise ValidationError("post requires an integer id.")

            post = self.repository.get_post(post_id)

            if post is not None and not AuthorizationService.can_read_post(
                context.user, post
            ):
                raise AuthorizationError("Access to this post is denied.")

            return post

        if name == "me":
            return AuthorizationService.require_authenticated(context)

        if name == "user":
            AuthorizationService.require_role(
                context, {UserRole.ADMIN}
            )

            user_id = arguments.get("id")

            if not isinstance(user_id, int) or isinstance(user_id, bool):
                raise ValidationError("user requires an integer id.")

            return self.repository.get_user(user_id)

        raise ValidationError(f"Unsupported root field: {name}")

    def resolve_nested(
        self,
        parent: Any,
        field_name: str,
        context: RequestContext
    ) -> Any:

        if isinstance(parent, Post):
            if field_name == "id":
                return parent.id
            if field_name == "title":
                return parent.title
            if field_name == "body":
                return parent.body
            if field_name == "published":
                return parent.published
            if field_name == "author":
                return self.repository.users.get(parent.author_id)
            if field_name == "comments":
                loader = context.loaders["comments"]
                loader.load(parent.id)
                return ("BATCHED", parent.id)

        if isinstance(parent, User):
            if field_name == "id":
                return parent.id
            if field_name == "name":
                return parent.name
            if field_name == "role":
                return parent.role.value
            if field_name == "email":
                if not AuthorizationService.can_read_email(context, parent):
                    raise AuthorizationError("Email access denied.")
                return parent.email
            if field_name == "posts":
                return [
                    post for post in self.repository.posts.values()
                    if post.author_id == parent.id
                    and post.published
                ]

        if isinstance(parent, Comment):
            if field_name == "id":
                return parent.id
            if field_name == "content":
                return parent.content
            if field_name == "author":
                return self.repository.users.get(parent.author_id)

        raise ValidationError(
            f"Cannot resolve field '{field_name}'."
        )

    @staticmethod
    def resolve_value(value: Any, variables: dict[str, Any]) -> Any:
        if isinstance(value, Variable):
            if value.name not in variables:
                raise ValidationError(
                    f"Missing variable '${value.name}'."
                )
            return variables[value.name]

        if isinstance(value, dict):
            return {
                key: GraphQLService.resolve_value(item, variables)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                GraphQLService.resolve_value(item, variables)
                for item in value
            ]

        return value

    def expand_fragments(
        self,
        selections: list[Selection],
        fragments: dict[str, Fragment],
        parent_type: str,
        stack: tuple[str, ...] = ()
    ) -> list[Selection]:

        expanded = []

        for selection in selections:
            if selection.name.startswith("..."):
                fragment_name = selection.name[3:]

                if fragment_name not in fragments:
                    raise ValidationError(
                        f"Unknown fragment: {fragment_name}"
                    )

                if fragment_name in stack:
                    raise ValidationError("Circular fragment detected.")

                fragment = fragments[fragment_name]

                if fragment.type_condition != parent_type:
                    continue

                expanded.extend(
                    self.expand_fragments(
                        fragment.selections,
                        fragments,
                        parent_type,
                        stack + (fragment_name,)
                    )
                )
            else:
                expanded.append(selection)

        return expanded

    def project_many(
        self,
        objects: list[Any],
        selections: list[Selection],
        parent_type: str,
        operation: Operation,
        context: RequestContext
    ) -> list[dict[str, Any]]:

        expanded = self.expand_fragments(
            selections, operation.fragments, parent_type
        )

        # Resolve sibling fields across all parent objects before
        # dispatching loaders. This is the batching boundary.
        raw_values = []

        for obj in objects:
            row = {}

            for selection in expanded:
                self.validate_field(parent_type, selection.name)

                value = self.resolve_nested(
                    obj, selection.name, context
                )

                row[selection.alias or selection.name] = (
                    selection, value
                )

            raw_values.append(row)

        for loader in context.loaders.values():
            loader.dispatch()

        results = []

        for row in raw_values:
            output = {}

            for output_name, (selection, value) in row.items():
                if (
                    isinstance(value, tuple)
                    and value[0] == "BATCHED"
                ):
                    value = context.loaders["comments"].get(value[1])

                if selection.children:
                    child_type = {
                        "author": "User",
                        "comments": "Comment",
                        "posts": "Post",
                    }.get(selection.name)

                    if child_type is None:
                        raise ValidationError(
                            f"Field '{selection.name}' cannot have children."
                        )

                    if isinstance(value, list):
                        output[output_name] = self.project_many(
                            value,
                            selection.children,
                            child_type,
                            operation,
                            context
                        )
                    elif value is None:
                        output[output_name] = None
                    else:
                        output[output_name] = self.project_many(
                            [value],
                            selection.children,
                            child_type,
                            operation,
                            context
                        )[0]
                else:
                    if isinstance(value, (User, Post, Comment)):
                        raise ValidationError(
                            f"Field '{selection.name}' requires child selections."
                        )

                    output[output_name] = value

            results.append(output)

        return results

    def execute(
        self,
        operation: Operation,
        context: RequestContext
    ) -> dict[str, Any]:

        started = time.perf_counter()

        try:
            if len(operation.selections) > 30:
                raise ValidationError("Operation exceeds field limit.")

            context.loaders["comments"] = DataLoader(
                self.repository.get_comments_by_post_ids
            )

            data = {}

            for selection in operation.selections:
                self.validate_field("Query", selection.name)

                arguments = self.resolve_value(
                    selection.arguments, operation.variables
                )

                value = self.resolve_root(
                    selection, arguments, context
                )

                if selection.children:
                    if value is None:
                        data[selection.alias or selection.name] = None
                    elif isinstance(value, list):
                        data[selection.alias or selection.name] = (
                            self.project_many(
                                value,
                                selection.children,
                                "Post",
                                operation,
                                context
                            )
                        )
                    else:
                        root_type = (
                            "User" if isinstance(value, User) else "Post"
                        )

                        data[selection.alias or selection.name] = (
                            self.project_many(
                                [value],
                                selection.children,
                                root_type,
                                operation,
                                context
                            )[0]
                        )
                else:
                    if isinstance(value, (User, Post, Comment)):
                        raise ValidationError(
                            f"Field '{selection.name}' requires selections."
                        )

                    data[selection.alias or selection.name] = value

            return {
                "data": data,
                "extensions": {
                    "databaseQueries": self.repository.database_queries,
                    "durationMs": round(
                        (time.perf_counter() - started) * 1000, 3
                    ),
                    "requestId": context.request_id,
                },
            }

        except GraphQLError as exc:
            logger.warning(
                "GraphQL request %s failed: %s",
                context.request_id,
                exc
            )

            return {
                "data": None,
                "errors": [{"message": str(exc)}],
            }


# ============================================================
# SAMPLE OPERATION
# ============================================================

def build_demo_operation() -> Operation:

    post_fragment = Fragment(
        name="PostDetails",
        type_condition="Post",
        selections=[
            Selection("id"),
            Selection("title"),
            Selection(
                "author",
                children=[
                    Selection("name"),
                ]
            ),
            Selection(
                "comments",
                children=[
                    Selection("id"),
                    Selection("content"),
                    Selection(
                        "author",
                        children=[Selection("name")]
                    ),
                ]
            ),
        ],
    )

    return Operation(
        selections=[
            Selection(
                "posts",
                arguments={"publishedOnly": Variable("published")},
                children=[
                    Selection("...PostDetails"),
                ],
            ),
            Selection(
                "me",
                children=[
                    Selection("id"),
                    Selection("name"),
                ],
            ),
        ],
        variables={"published": True},
        fragments={"PostDetails": post_fragment},
    )


# ============================================================
# EXECUTION AND TESTING
# ============================================================

def main() -> None:
    repository = Repository()
    service = GraphQLService(repository)

    admin = repository.users[1]

    context = RequestContext(
        user=admin,
        request_id="req-graphql-001"
    )

    operation = build_demo_operation()
    response = service.execute(operation, context)

    print("\nGRAPHQL RESPONSE")
    print(json.dumps(response, indent=2))

    assert response["data"] is not None
    assert len(response["data"]["posts"]) == 2

    # Two published posts must use one comments batch query.
    assert repository.database_queries == 2

    print("\nBATCHING TEST PASSED")
    print("Database queries:", repository.database_queries)

    # Authorization failure.
    guest_context = RequestContext(
        user=repository.users[3],
        request_id="req-graphql-002"
    )

    unauthorized_operation = Operation(
        selections=[
            Selection(
                "user",
                arguments={"id": 1},
                children=[Selection("email")]
            )
        ]
    )

    denied = service.execute(
        unauthorized_operation, guest_context
    )

    assert denied["data"] is None
    assert "errors" in denied

    print("\nAUTHORIZATION TEST PASSED")

    # Missing variable failure.
    invalid_operation = Operation(
        selections=[Selection("post", arguments={
            "id": Variable("missing")
        }, children=[Selection("title")])],
        variables={}
    )

    invalid = service.execute(invalid_operation, context)

    assert "errors" in invalid

    print("VARIABLE VALIDATION TEST PASSED")

    # Invalid field failure.
    invalid_field = Operation(
        selections=[
            Selection("posts", children=[
                Selection("unknownField")
            ])
        ]
    )

    invalid_result = service.execute(invalid_field, context)

    assert "errors" in invalid_result

    print("SCHEMA VALIDATION TEST PASSED")


if __name__ == "__main__":
    main()
