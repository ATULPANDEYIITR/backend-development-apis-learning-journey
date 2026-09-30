#!/usr/bin/env python3
"""
REST API Design: resource naming, nesting, CRUD conventions, status codes,
and response structures.

This self-contained script builds a small in-memory REST API design simulator.
It demonstrates how HTTP methods map to resource operations, how resource
identifiers and nested resources should be modeled, how validation affects
status codes, and how consistent response envelopes improve API clients.

No external packages are required.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http import HTTPStatus
import json
import re
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Response structures
# ---------------------------------------------------------------------------

@dataclass
class ApiResponse:
    """Represents the parts of an HTTP response relevant to an API client."""

    status: int
    body: dict[str, Any]
    headers: dict[str, str]

    def to_json(self) -> str:
        return json.dumps(self.body, indent=2, sort_keys=True)


def success_response(
    status: HTTPStatus,
    data: Any,
    *,
    message: str | None = None,
) -> ApiResponse:
    """
    Use a predictable response envelope.

    The payload separates the actual resource data from metadata. This makes
    it easier for clients to add pagination or request identifiers later
    without changing the resource representation itself.
    """
    body: dict[str, Any] = {
        "data": data,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    if message:
        body["meta"]["message"] = message

    return ApiResponse(
        status=status,
        body=body,
        headers={
            "Content-Type": "application/json",
        },
    )


def error_response(
    status: HTTPStatus,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
) -> ApiResponse:
    """
    Keep errors structurally different from successful resource responses.

    Validation errors can carry field-level details while authentication,
    authorization, or not-found errors can remain concise.
    """
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }

    if details:
        error["details"] = details

    return ApiResponse(
        status=status,
        body={
            "error": error,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
        headers={
            "Content-Type": "application/problem+json",
        },
    )


# ---------------------------------------------------------------------------
# Domain resources
# ---------------------------------------------------------------------------

@dataclass
class User:
    id: int
    name: str
    email: str


@dataclass
class Project:
    id: int
    user_id: int
    name: str
    description: str


@dataclass
class Task:
    id: int
    project_id: int
    title: str
    status: str


# ---------------------------------------------------------------------------
# In-memory repository
# ---------------------------------------------------------------------------

class Repository:
    """
    Stores users, projects, and tasks.

    A real service would normally replace this class with a database
    repository. The important REST design distinction remains the same:
    persistence mechanics are separate from URI and HTTP semantics.
    """

    def __init__(self) -> None:
        self.users: dict[int, User] = {
            1: User(1, "Atul Pandey", "atul@example.com"),
            2: User(2, "Priya Sharma", "priya@example.com"),
        }

        self.projects: dict[int, Project] = {
            101: Project(
                101,
                1,
                "API Platform",
                "REST API design laboratory",
            ),
            102: Project(
                102,
                1,
                "Analytics",
                "Operational reporting service",
            ),
        }

        self.tasks: dict[int, Task] = {
            1001: Task(1001, 101, "Design resource model", "open"),
            1002: Task(1002, 101, "Document status codes", "done"),
            1003: Task(1003, 102, "Define reporting endpoint", "open"),
        }

        self.next_user_id = 3
        self.next_project_id = 103
        self.next_task_id = 1004


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def user_to_dict(user: User) -> dict[str, Any]:
    return asdict(user)


def project_to_dict(project: Project) -> dict[str, Any]:
    return asdict(project)


def task_to_dict(task: Task) -> dict[str, Any]:
    return asdict(task)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ALLOWED_TASK_STATUSES = {"open", "in_progress", "done"}


def validate_user_payload(
    payload: dict[str, Any],
    *,
    partial: bool,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    required = {"name", "email"}

    if not partial:
        missing = required - payload.keys()
        for field in sorted(missing):
            errors.append({
                "field": field,
                "reason": "required",
            })

    if "name" in payload:
        if not isinstance(payload["name"], str):
            errors.append({
                "field": "name",
                "reason": "must be a string",
            })
        elif not payload["name"].strip():
            errors.append({
                "field": "name",
                "reason": "must not be empty",
            })

    if "email" in payload:
        if not isinstance(payload["email"], str):
            errors.append({
                "field": "email",
                "reason": "must be a string",
            })
        elif not EMAIL_PATTERN.match(payload["email"]):
            errors.append({
                "field": "email",
                "reason": "must be a valid email address",
            })

    return errors


def validate_project_payload(
    payload: dict[str, Any],
    *,
    partial: bool,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    if not partial and "name" not in payload:
        errors.append({
            "field": "name",
            "reason": "required",
        })

    if "name" in payload:
        if not isinstance(payload["name"], str):
            errors.append({
                "field": "name",
                "reason": "must be a string",
            })
        elif not payload["name"].strip():
            errors.append({
                "field": "name",
                "reason": "must not be empty",
            })

    if "description" in payload and not isinstance(
        payload["description"], str
    ):
        errors.append({
            "field": "description",
            "reason": "must be a string",
        })

    return errors


def validate_task_payload(
    payload: dict[str, Any],
    *,
    partial: bool,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    if not partial and "title" not in payload:
        errors.append({
            "field": "title",
            "reason": "required",
        })

    if "title" in payload:
        if not isinstance(payload["title"], str):
            errors.append({
                "field": "title",
                "reason": "must be a string",
            })
        elif not payload["title"].strip():
            errors.append({
                "field": "title",
                "reason": "must not be empty",
            })

    if "status" in payload:
        if payload["status"] not in ALLOWED_TASK_STATUSES:
            errors.append({
                "field": "status",
                "reason": (
                    "must be one of "
                    + ", ".join(sorted(ALLOWED_TASK_STATUSES))
                ),
            })

    return errors


# ---------------------------------------------------------------------------
# HTTP method semantics
# ---------------------------------------------------------------------------

def explain_http_semantics() -> None:
    print("\nHTTP method semantics")
    print("---------------------")

    methods = {
        "GET": (
            "Retrieve a resource or collection. It should not mutate "
            "server state and is safe and cache-friendly."
        ),
        "POST": (
            "Create a subordinate resource or trigger a non-idempotent "
            "operation represented by the target resource."
        ),
        "PUT": (
            "Replace the target representation. Repeating the same valid "
            "request should result in the same intended resource state."
        ),
        "PATCH": (
            "Partially modify a resource. Only supplied fields are changed."
        ),
        "DELETE": (
            "Remove the addressed resource. A successful deletion commonly "
            "uses 204 No Content."
        ),
    }

    for method, description in methods.items():
        print(f"{method:7} {description}")


# ---------------------------------------------------------------------------
# Status code demonstration
# ---------------------------------------------------------------------------

def explain_status_codes() -> None:
    print("\nStatus code semantics")
    print("---------------------")

    examples = {
        200: "Successful retrieval or successful update with a response body.",
        201: "Resource successfully created.",
        202: "Request accepted for asynchronous processing.",
        204: "Successful operation with no response body.",
        400: "Malformed request or invalid request syntax.",
        401: "Authentication is required or credentials are invalid.",
        403: "The caller is authenticated but not allowed to perform it.",
        404: "The addressed resource does not exist.",
        405: "The resource exists conceptually, but the HTTP method is unsupported.",
        409: "The requested state conflicts with current server state.",
        415: "The request media type is unsupported.",
        422: "The request is syntactically valid but fails semantic validation.",
        429: "The client has exceeded a rate limit.",
        500: "Unexpected server-side failure.",
        503: "The service is temporarily unavailable.",
    }

    for code, description in examples.items():
        phrase = HTTPStatus(code).phrase
        print(f"{code} {phrase}: {description}")


# ---------------------------------------------------------------------------
# REST API service
# ---------------------------------------------------------------------------

class RestApiService:
    """
    Implements REST-style operations over users, projects, and tasks.

    URI relationships are deliberate:

        /users
        /users/{user_id}
        /users/{user_id}/projects
        /users/{user_id}/projects/{project_id}
        /projects/{project_id}/tasks
        /projects/{project_id}/tasks/{task_id}

    The nesting expresses ownership/context without turning every resource
    into an unnecessarily deep URI.
    """

    def __init__(self, repository: Repository) -> None:
        self.db = repository

    # -----------------------------------------------------------------------
    # User collection
    # -----------------------------------------------------------------------

    def list_users(self) -> ApiResponse:
        users = [user_to_dict(user) for user in self.db.users.values()]
        return success_response(HTTPStatus.OK, users)

    def get_user(self, user_id: int) -> ApiResponse:
        user = self.db.users.get(user_id)

        if user is None:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "USER_NOT_FOUND",
                f"User {user_id} does not exist.",
            )

        return success_response(
            HTTPStatus.OK,
            user_to_dict(user),
        )

    def create_user(self, payload: dict[str, Any]) -> ApiResponse:
        errors = validate_user_payload(payload, partial=False)

        if errors:
            return error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "The user payload failed validation.",
                details=errors,
            )

        email = payload["email"].lower().strip()

        if any(user.email.lower() == email for user in self.db.users.values()):
            return error_response(
                HTTPStatus.CONFLICT,
                "EMAIL_ALREADY_EXISTS",
                "A user with this email already exists.",
            )

        user = User(
            id=self.db.next_user_id,
            name=payload["name"].strip(),
            email=email,
        )

        self.db.users[user.id] = user
        self.db.next_user_id += 1

        return ApiResponse(
            status=HTTPStatus.CREATED,
            body={
                "data": user_to_dict(user),
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "User created.",
                },
            },
            headers={
                "Content-Type": "application/json",
                "Location": f"/users/{user.id}",
            },
        )

    # -----------------------------------------------------------------------
    # Project collection nested beneath a user
    # -----------------------------------------------------------------------

    def list_user_projects(self, user_id: int) -> ApiResponse:
        if user_id not in self.db.users:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "USER_NOT_FOUND",
                f"User {user_id} does not exist.",
            )

        projects = [
            project_to_dict(project)
            for project in self.db.projects.values()
            if project.user_id == user_id
        ]

        return success_response(HTTPStatus.OK, projects)

    def create_user_project(
        self,
        user_id: int,
        payload: dict[str, Any],
    ) -> ApiResponse:
        if user_id not in self.db.users:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "USER_NOT_FOUND",
                f"User {user_id} does not exist.",
            )

        errors = validate_project_payload(payload, partial=False)

        if errors:
            return error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "The project payload failed validation.",
                details=errors,
            )

        project = Project(
            id=self.db.next_project_id,
            user_id=user_id,
            name=payload["name"].strip(),
            description=payload.get("description", "").strip(),
        )

        self.db.projects[project.id] = project
        self.db.next_project_id += 1

        return ApiResponse(
            status=HTTPStatus.CREATED,
            body={
                "data": project_to_dict(project),
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
            headers={
                "Content-Type": "application/json",
                "Location": f"/projects/{project.id}",
            },
        )

    def get_project(
        self,
        project_id: int,
    ) -> ApiResponse:
        project = self.db.projects.get(project_id)

        if project is None:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "PROJECT_NOT_FOUND",
                f"Project {project_id} does not exist.",
            )

        return success_response(
            HTTPStatus.OK,
            project_to_dict(project),
        )

    def update_project(
        self,
        project_id: int,
        payload: dict[str, Any],
        *,
        partial: bool,
    ) -> ApiResponse:
        project = self.db.projects.get(project_id)

        if project is None:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "PROJECT_NOT_FOUND",
                f"Project {project_id} does not exist.",
            )

        errors = validate_project_payload(
            payload,
            partial=partial,
        )

        if errors:
            return error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "The project payload failed validation.",
                details=errors,
            )

        if "name" in payload:
            project.name = payload["name"].strip()

        if "description" in payload:
            project.description = payload["description"].strip()
        elif not partial:
            project.description = ""

        return success_response(
            HTTPStatus.OK,
            project_to_dict(project),
            message="Project updated.",
        )

    def delete_project(self, project_id: int) -> ApiResponse:
        project = self.db.projects.get(project_id)

        if project is None:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "PROJECT_NOT_FOUND",
                f"Project {project_id} does not exist.",
            )

        dependent_task_ids = [
            task_id
            for task_id, task in self.db.tasks.items()
            if task.project_id == project_id
        ]

        if dependent_task_ids:
            return error_response(
                HTTPStatus.CONFLICT,
                "PROJECT_HAS_TASKS",
                "The project cannot be deleted while tasks still exist.",
                details=[
                    {
                        "field": "tasks",
                        "reason": "remove dependent resources first",
                        "count": len(dependent_task_ids),
                    }
                ],
            )

        del self.db.projects[project_id]

        return ApiResponse(
            status=HTTPStatus.NO_CONTENT,
            body={},
            headers={},
        )

    # -----------------------------------------------------------------------
    # Task collection nested beneath a project
    # -----------------------------------------------------------------------

    def list_project_tasks(self, project_id: int) -> ApiResponse:
        if project_id not in self.db.projects:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "PROJECT_NOT_FOUND",
                f"Project {project_id} does not exist.",
            )

        tasks = [
            task_to_dict(task)
            for task in self.db.tasks.values()
            if task.project_id == project_id
        ]

        return success_response(HTTPStatus.OK, tasks)

    def create_project_task(
        self,
        project_id: int,
        payload: dict[str, Any],
    ) -> ApiResponse:
        if project_id not in self.db.projects:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "PROJECT_NOT_FOUND",
                f"Project {project_id} does not exist.",
            )

        errors = validate_task_payload(payload, partial=False)

        if errors:
            return error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "The task payload failed validation.",
                details=errors,
            )

        task = Task(
            id=self.db.next_task_id,
            project_id=project_id,
            title=payload["title"].strip(),
            status=payload.get("status", "open"),
        )

        self.db.tasks[task.id] = task
        self.db.next_task_id += 1

        return ApiResponse(
            status=HTTPStatus.CREATED,
            body={
                "data": task_to_dict(task),
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
            headers={
                "Content-Type": "application/json",
                "Location": f"/tasks/{task.id}",
            },
        )

    def get_task(self, task_id: int) -> ApiResponse:
        task = self.db.tasks.get(task_id)

        if task is None:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "TASK_NOT_FOUND",
                f"Task {task_id} does not exist.",
            )

        return success_response(
            HTTPStatus.OK,
            task_to_dict(task),
        )

    def patch_task(
        self,
        task_id: int,
        payload: dict[str, Any],
    ) -> ApiResponse:
        task = self.db.tasks.get(task_id)

        if task is None:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "TASK_NOT_FOUND",
                f"Task {task_id} does not exist.",
            )

        errors = validate_task_payload(payload, partial=True)

        if errors:
            return error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "The task patch failed validation.",
                details=errors,
            )

        if "title" in payload:
            task.title = payload["title"].strip()

        if "status" in payload:
            task.status = payload["status"]

        return success_response(
            HTTPStatus.OK,
            task_to_dict(task),
        )

    def delete_task(self, task_id: int) -> ApiResponse:
        if task_id not in self.db.tasks:
            return error_response(
                HTTPStatus.NOT_FOUND,
                "TASK_NOT_FOUND",
                f"Task {task_id} does not exist.",
            )

        del self.db.tasks[task_id]

        return ApiResponse(
            status=HTTPStatus.NO_CONTENT,
            body={},
            headers={},
        )


# ---------------------------------------------------------------------------
# URI design and routing
# ---------------------------------------------------------------------------

class Router:
    """
    A small URI router used to show that the URI identifies a resource while
    the HTTP method supplies the operation semantics.
    """

    def __init__(self, api: RestApiService) -> None:
        self.api = api

    def dispatch(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> ApiResponse:
        body = body or {}
        method = method.upper()

        # Collection resource: /users
        if path == "/users":
            if method == "GET":
                return self.api.list_users()
            if method == "POST":
                return self.api.create_user(body)
            return error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "This method is not supported for /users.",
            )

        # Item resource: /users/{id}
        match = re.fullmatch(r"/users/(\d+)", path)
        if match:
            user_id = int(match.group(1))

            if method == "GET":
                return self.api.get_user(user_id)

            return error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "This method is not supported for this user resource.",
            )

        # Nested collection: /users/{id}/projects
        match = re.fullmatch(r"/users/(\d+)/projects", path)
        if match:
            user_id = int(match.group(1))

            if method == "GET":
                return self.api.list_user_projects(user_id)

            if method == "POST":
                return self.api.create_user_project(user_id, body)

            return error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "This method is not supported for this project collection.",
            )

        # Project item: /projects/{id}
        match = re.fullmatch(r"/projects/(\d+)", path)
        if match:
            project_id = int(match.group(1))

            if method == "GET":
                return self.api.get_project(project_id)

            if method == "PUT":
                return self.api.update_project(
                    project_id,
                    body,
                    partial=False,
                )

            if method == "PATCH":
                return self.api.update_project(
                    project_id,
                    body,
                    partial=True,
                )

            if method == "DELETE":
                return self.api.delete_project(project_id)

            return error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "Unsupported project method.",
            )

        # Nested task collection: /projects/{id}/tasks
        match = re.fullmatch(r"/projects/(\d+)/tasks", path)
        if match:
            project_id = int(match.group(1))

            if method == "GET":
                return self.api.list_project_tasks(project_id)

            if method == "POST":
                return self.api.create_project_task(project_id, body)

            return error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "Unsupported task collection method.",
            )

        # Task item: /tasks/{id}
        match = re.fullmatch(r"/tasks/(\d+)", path)
        if match:
            task_id = int(match.group(1))

            if method == "GET":
                return self.api.get_task(task_id)

            if method == "PATCH":
                return self.api.patch_task(task_id, body)

            if method == "DELETE":
                return self.api.delete_task(task_id)

            return error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "Unsupported task method.",
            )

        return error_response(
            HTTPStatus.NOT_FOUND,
            "ROUTE_NOT_FOUND",
            f"No resource route exists for {path}.",
        )


# ---------------------------------------------------------------------------
# Query parameters and collection design
# ---------------------------------------------------------------------------

def demonstrate_collection_queries() -> None:
    """
    Shows how collection filtering and pagination can be represented.

    Query parameters modify retrieval criteria. They do not need to become
    additional path segments such as /projects/open/tasks.
    """

    projects = [
        {
            "id": 101,
            "name": "API Platform",
            "owner": "atul@example.com",
        },
        {
            "id": 102,
            "name": "Analytics",
            "owner": "atul@example.com",
        },
        {
            "id": 103,
            "name": "Billing",
            "owner": "priya@example.com",
        },
    ]

    def filter_projects(
        items: list[dict[str, Any]],
        *,
        owner: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        result = items

        if owner:
            result = [
                item for item in result
                if item["owner"].lower() == owner.lower()
            ]

        if search:
            term = search.casefold()
            result = [
                item for item in result
                if term in item["name"].casefold()
            ]

        total = len(result)
        page = result[offset:offset + limit]

        return {
            "data": page,
            "meta": {
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        }

    print("\nCollection filtering and pagination")
    print("------------------------------------")
    print(
        json.dumps(
            filter_projects(
                projects,
                owner="atul@example.com",
                search="api",
                limit=10,
            ),
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# Idempotency demonstration
# ---------------------------------------------------------------------------

def demonstrate_idempotency() -> None:
    """
    PUT is modeled as a replacement operation, while POST creates a new
    resource each time unless the application deliberately introduces an
    idempotency mechanism.
    """

    print("\nIdempotency considerations")
    print("-------------------------")

    replacement = {
        "id": 101,
        "name": "API Platform",
        "description": "REST API design laboratory",
    }

    first_put = replacement.copy()
    second_put = replacement.copy()

    print("Repeated PUT representations are equal:", first_put == second_put)
    print(
        "POST creation requests normally create distinct resources unless "
        "the service provides an idempotency strategy."
    )


# ---------------------------------------------------------------------------
# Error handling demonstration
# ---------------------------------------------------------------------------

def demonstrate_failure_modes(router: Router) -> None:
    print("\nFailure conditions")
    print("------------------")

    cases = [
        (
            "GET",
            "/users/999",
            None,
        ),
        (
            "POST",
            "/users",
            {
                "name": "",
                "email": "not-an-email",
            },
        ),
        (
            "POST",
            "/users",
            {
                "name": "Duplicate",
                "email": "ATUL@EXAMPLE.COM",
            },
        ),
        (
            "DELETE",
            "/projects/101",
            None,
        ),
        (
            "GET",
            "/does-not-exist",
            None,
        ),
        (
            "PATCH",
            "/tasks/1001",
            {
                "status": "invalid-state",
            },
        ),
        (
            "PUT",
            "/users/1",
            {
                "name": "Not Supported",
            },
        ),
    ]

    for method, path, payload in cases:
        response = router.dispatch(method, path, payload)

        print(
            f"\n{method} {path} -> "
            f"{response.status} {HTTPStatus(response.status).phrase}"
        )
        print(response.to_json())


# ---------------------------------------------------------------------------
# End-to-end workflow
# ---------------------------------------------------------------------------

def demonstrate_normal_workflow(router: Router) -> None:
    print("\nNormal REST resource workflow")
    print("-----------------------------")

    operations: list[
        tuple[str, str, dict[str, Any] | None]
    ] = [
        ("GET", "/users", None),
        (
            "POST",
            "/users",
            {
                "name": "Meera Singh",
                "email": "meera@example.com",
            },
        ),
        ("GET", "/users/1/projects", None),
        (
            "POST",
            "/users/1/projects",
            {
                "name": "Security Gateway",
                "description": "API gateway policy service",
            },
        ),
        ("GET", "/projects/103/tasks", None),
        (
            "POST",
            "/projects/103/tasks",
            {
                "title": "Define authentication policy",
            },
        ),
        (
            "PATCH",
            "/tasks/1004",
            {
                "status": "in_progress",
            },
        ),
        ("GET", "/tasks/1004", None),
        ("DELETE", "/tasks/1004", None),
        ("GET", "/tasks/1004", None),
    ]

    for method, path, payload in operations:
        response = router.dispatch(method, path, payload)

        print(
            f"\n{method} {path} -> "
            f"{response.status} {HTTPStatus(response.status).phrase}"
        )

        if response.status != HTTPStatus.NO_CONTENT:
            print(response.to_json())


# ---------------------------------------------------------------------------
# REST design audit
# ---------------------------------------------------------------------------

@dataclass
class Endpoint:
    method: str
    path: str
    purpose: str


def audit_resource_design(endpoints: list[Endpoint]) -> None:
    """
    Performs lightweight design checks.

    These checks are intentionally conservative. REST API quality cannot be
    completely determined from URI strings, but obvious violations such as
    verbs embedded in resource paths can be detected automatically.
    """

    print("\nREST endpoint design audit")
    print("--------------------------")

    suspicious_verbs = {
        "create",
        "get",
        "fetch",
        "update",
        "delete",
        "remove",
        "list",
        "add",
    }

    for endpoint in endpoints:
        path_parts = {
            part.casefold()
            for part in endpoint.path.split("/")
            if part
        }

        embedded_verbs = path_parts & suspicious_verbs

        if embedded_verbs:
            print(
                f"WARNING: {endpoint.method} {endpoint.path} "
                f"contains verb-like path segments: "
                f"{sorted(embedded_verbs)}"
            )
        else:
            print(
                f"OK:      {endpoint.method:6} "
                f"{endpoint.path:35} {endpoint.purpose}"
            )


# ---------------------------------------------------------------------------
# Security-aware design notes expressed through executable policy checks
# ---------------------------------------------------------------------------

class AuthorizationPolicy:
    """
    Demonstrates authorization as a separate decision from resource lookup.

    A 404 can sometimes intentionally conceal resource existence in a
    security-sensitive service. This example keeps the distinction explicit:
    authentication and authorization should not be confused with validation.
    """

    def can_modify_project(
        self,
        authenticated_user_id: int | None,
        project: Project,
    ) -> bool:
        if authenticated_user_id is None:
            return False

        return authenticated_user_id == project.user_id


def demonstrate_authorization(router: Router, repository: Repository) -> None:
    print("\nAuthorization boundary")
    print("----------------------")

    policy = AuthorizationPolicy()
    project = repository.projects[101]

    decisions = [
        (None, project),
        (1, project),
        (2, project),
    ]

    for user_id, target in decisions:
        allowed = policy.can_modify_project(user_id, target)
        principal = "anonymous" if user_id is None else str(user_id)
        print(
            f"User {principal} modifying project {target.id}: "
            f"{'allowed' if allowed else 'denied'}"
        )

    # The router is intentionally separate from authorization. In a production
    # service, authentication middleware would establish identity and an
    # authorization layer would evaluate whether that identity may act.
    response = router.dispatch("GET", "/projects/101")
    print(
        "Resource lookup remains independent of the authorization decision:",
        response.status == HTTPStatus.OK,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("REST API Design Demonstration")
    print("=============================")

    explain_http_semantics()
    explain_status_codes()

    repository = Repository()
    service = RestApiService(repository)
    router = Router(service)

    demonstrate_normal_workflow(router)
    demonstrate_failure_modes(router)
    demonstrate_collection_queries()
    demonstrate_idempotency()

    endpoints = [
        Endpoint("GET", "/users", "retrieve user collection"),
        Endpoint("POST", "/users", "create a user"),
        Endpoint("GET", "/users/{id}", "retrieve one user"),
        Endpoint("GET", "/users/{id}/projects", "retrieve projects owned by a user"),
        Endpoint("POST", "/users/{id}/projects", "create a project for a user"),
        Endpoint("GET", "/projects/{id}", "retrieve one project"),
        Endpoint("PUT", "/projects/{id}", "replace a project"),
        Endpoint("PATCH", "/projects/{id}", "partially modify a project"),
        Endpoint("DELETE", "/projects/{id}", "delete a project"),
        Endpoint("GET", "/projects/{id}/tasks", "retrieve project tasks"),
        Endpoint("POST", "/projects/{id}/tasks", "create a task in a project"),
        Endpoint("GET", "/tasks/{id}", "retrieve one task"),
        Endpoint("PATCH", "/tasks/{id}", "change selected task fields"),
        Endpoint("DELETE", "/tasks/{id}", "delete a task"),
        Endpoint("POST", "/users/create", "intentionally suspicious verb-oriented path"),
    ]

    audit_resource_design(endpoints)
    demonstrate_authorization(router, repository)

    print("\nDesign observations")
    print("-------------------")
    print(
        "Resource names identify nouns; HTTP methods express the intended "
        "operation."
    )
    print(
        "Nested paths are used when the parent relationship provides useful "
        "context, while direct item paths remain available when the child "
        "has its own stable identity."
    )
    print(
        "POST returns 201 with a Location header for newly created resources."
    )
    print(
        "PUT replaces a representation, PATCH changes selected fields, and "
        "DELETE can return 204 when there is no response body."
    )
    print(
        "Validation, missing resources, conflicts, unsupported methods, and "
        "authorization are different failure categories and should not be "
        "collapsed into one generic error."
    )


if __name__ == "__main__":
    main()
