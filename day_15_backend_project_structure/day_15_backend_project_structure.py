"""
Backend Project Structure
=========================

Topic:
    Application layers, modules, packages, configuration, services, utilities

This file is a standalone study program. It demonstrates how a backend
application can be organized from a small script into a maintainable,
layered application.

The examples intentionally use only the Python standard library so the
file can be executed without installing third-party packages.

The case study models a small task-management backend and demonstrates:

    1. Application layers
    2. Modules and packages
    3. Configuration management
    4. Service classes
    5. Utility functions
    6. Repository/data-access boundaries
    7. Domain models
    8. Validation
    9. Dependency injection
    10. Error handling
    11. Logging
    12. Testing
    13. Security boundaries
    14. Performance considerations
    15. Production-oriented design decisions

Run:
    python backend_project_structure.py
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sys
import time
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Iterable, List, Optional, Protocol, Sequence


# ============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# ============================================================================

"""
A backend project is easier to maintain when responsibilities are separated.

Important terms:

Application:
    The complete backend system.

Layer:
    A logical boundary grouping code by responsibility.

Module:
    Usually a Python file containing related definitions.

Package:
    A directory that groups related modules.

Configuration:
    Values controlling application behavior, such as environment, database
    location, logging level, or security settings.

Service:
    Application/business logic that coordinates operations.

Repository:
    An abstraction around persistence or data access.

Utility:
    A small reusable operation that is not specific to one business workflow.

Domain model:
    An object representing a business concept.

Dependency:
    A component another component needs to perform its job.

Dependency injection:
    Providing dependencies from outside instead of constructing them inside
    the component.

Separation of concerns:
    Keeping unrelated responsibilities in different components.

Cohesion:
    How strongly the responsibilities inside one module belong together.

Coupling:
    How strongly one module depends on another.

A good backend structure generally tries to increase cohesion and reduce
unnecessary coupling.
"""


# ============================================================================
# 2. A SIMPLE UNSTRUCTURED APPLICATION
# ============================================================================

def simple_create_task(title: str, tasks: list[dict]) -> dict:
    """
    A small application can begin as one function.

    This is easy to understand, but the function mixes validation,
    business rules, persistence, and response construction.
    """
    title = title.strip()

    if not title:
        raise ValueError("Task title cannot be empty")

    if len(title) > 100:
        raise ValueError("Task title is too long")

    task = {
        "id": len(tasks) + 1,
        "title": title,
        "completed": False,
    }

    tasks.append(task)
    return task


def demonstrate_unstructured_application() -> None:
    tasks: list[dict] = []

    print("\n--- Small unstructured application ---")

    print(simple_create_task("Learn backend structure", tasks))
    print(simple_create_task("Practice service design", tasks))

    print("Stored tasks:", tasks)


# ============================================================================
# 3. WHY LAYERS BECOME USEFUL
# ============================================================================

"""
As an application grows, responsibilities can be separated into layers.

A common conceptual architecture is:

    Presentation / API
            |
            v
    Application / Service
            |
            v
    Repository / Data Access
            |
            v
    Database

Domain models and configuration support these layers.

Utilities should remain focused. A utility should not silently become a
second service layer containing unrelated business rules.

A typical project might eventually look like:

    backend/
        app/
            __init__.py
            main.py
            config.py

            api/
                __init__.py
                routes.py

            domain/
                __init__.py
                models.py

            services/
                __init__.py
                task_service.py

            repositories/
                __init__.py
                task_repository.py

            utilities/
                __init__.py
                text.py
                security.py

            tests/
                test_services.py

The exact names are not mandatory. The important principle is responsibility.
"""


# ============================================================================
# 4. DOMAIN MODEL
# ============================================================================

class TaskStatus(str, Enum):
    """Explicit domain states prevent scattered string literals."""

    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class Task:
    """
    Domain object.

    A domain model represents the data and identity of a business concept.
    It does not need to know how the object is stored in a database.
    """

    id: int
    title: str
    owner_id: int
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED


# ============================================================================
# 5. CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class Settings:
    """
    Central application configuration.

    Configuration is separated from business logic so deployment-specific
    values do not have to be scattered throughout the source code.
    """

    app_name: str
    environment: str
    debug: bool
    log_level: str
    database_url: str
    secret_key: str
    max_title_length: int

    @classmethod
    def from_environment(cls) -> "Settings":
        """
        Read configuration from environment variables.

        Environment variables are common in deployed applications because
        secrets and deployment-specific settings should not be committed
        directly to source control.
        """

        environment = os.getenv("APP_ENV", "development").lower()

        debug_default = "true" if environment == "development" else "false"

        return cls(
            app_name=os.getenv("APP_NAME", "Task Management Backend"),
            environment=environment,
            debug=os.getenv("APP_DEBUG", debug_default).lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            database_url=os.getenv(
                "DATABASE_URL",
                "memory://tasks",
            ),
            secret_key=os.getenv(
                "APP_SECRET_KEY",
                "development-only-secret",
            ),
            max_title_length=int(
                os.getenv("MAX_TITLE_LENGTH", "100")
            ),
        )

    def validate(self) -> None:
        """
        Validate configuration at startup.

        Failing fast is usually better than discovering invalid
        configuration during a user request.
        """

        if self.environment == "production":
            if self.debug:
                raise ValueError(
                    "Debug mode must not be enabled in production"
                )

            if self.secret_key == "development-only-secret":
                raise ValueError(
                    "A production secret key must be configured"
                )

        if self.max_title_length <= 0:
            raise ValueError("MAX_TITLE_LENGTH must be positive")


# ============================================================================
# 6. APPLICATION EXCEPTIONS
# ============================================================================

class ApplicationError(Exception):
    """Base class for expected application-level errors."""


class ValidationError(ApplicationError):
    """Raised when input violates application rules."""


class NotFoundError(ApplicationError):
    """Raised when an expected entity does not exist."""


class AuthorizationError(ApplicationError):
    """Raised when an actor cannot perform an operation."""


class ConflictError(ApplicationError):
    """Raised when an operation conflicts with current state."""


# ============================================================================
# 7. VALIDATION UTILITY
# ============================================================================

class ValidationUtils:
    """
    Small, reusable validation helpers.

    Utilities should generally remain independent from business workflows.
    """

    @staticmethod
    def normalize_title(title: str, maximum_length: int) -> str:
        if not isinstance(title, str):
            raise ValidationError("Title must be a string")

        normalized = " ".join(title.split())

        if not normalized:
            raise ValidationError("Title cannot be empty")

        if len(normalized) > maximum_length:
            raise ValidationError(
                f"Title cannot exceed {maximum_length} characters"
            )

        return normalized

    @staticmethod
    def validate_positive_integer(value: int, field_name: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(f"{field_name} must be an integer")

        if value <= 0:
            raise ValidationError(f"{field_name} must be positive")


# ============================================================================
# 8. SECURITY UTILITY
# ============================================================================

class SecurityUtils:
    """
    Security-related helper functions.

    These functions demonstrate boundaries between generic security
    operations and application-specific authorization rules.
    """

    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> str:
        """
        Demonstration password hashing using the standard library.

        PBKDF2 deliberately performs repeated hashing to make password
        guessing more expensive.

        In a production application, use a security library specifically
        designed and maintained for password storage when possible.
        """

        if len(password) < 8:
            raise ValidationError(
                "Password must contain at least 8 characters"
            )

        if salt is None:
            salt = secrets.token_bytes(16)

        derived_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200_000,
        )

        return (
            f"pbkdf2_sha256$200000$"
            f"{salt.hex()}${derived_key.hex()}"
        )

    @staticmethod
    def verify_password(password: str, encoded_hash: str) -> bool:
        try:
            algorithm, iterations, salt_hex, expected_hex = (
                encoded_hash.split("$")
            )

            if algorithm != "pbkdf2_sha256":
                return False

            derived_key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )

            return hmac.compare_digest(
                derived_key.hex(),
                expected_hex,
            )
        except (ValueError, TypeError):
            return False


# ============================================================================
# 9. REPOSITORY INTERFACE
# ============================================================================

class TaskRepository(Protocol):
    """
    Protocol defining what the service expects from persistence.

    The service does not need to know whether data comes from memory,
    PostgreSQL, SQLite, MongoDB, or another system.
    """

    def create(self, task: Task) -> Task:
        ...

    def get_by_id(self, task_id: int) -> Optional[Task]:
        ...

    def list_by_owner(self, owner_id: int) -> List[Task]:
        ...

    def update(self, task: Task) -> Task:
        ...

    def delete(self, task_id: int) -> bool:
        ...


# ============================================================================
# 10. IN-MEMORY REPOSITORY
# ============================================================================

class InMemoryTaskRepository:
    """
    Concrete repository implementation.

    This is useful for learning and testing because it requires no database.
    """

    def __init__(self) -> None:
        self._tasks: Dict[int, Task] = {}
        self._next_id = 1

    def create(self, task: Task) -> Task:
        task.id = self._next_id
        self._next_id += 1

        self._tasks[task.id] = task
        return task

    def get_by_id(self, task_id: int) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_by_owner(self, owner_id: int) -> List[Task]:
        return [
            task
            for task in self._tasks.values()
            if task.owner_id == owner_id
        ]

    def update(self, task: Task) -> Task:
        if task.id not in self._tasks:
            raise NotFoundError("Task does not exist")

        self._tasks[task.id] = task
        return task

    def delete(self, task_id: int) -> bool:
        return self._tasks.pop(task_id, None) is not None


# ============================================================================
# 11. SERVICE LAYER
# ============================================================================

class TaskService:
    """
    Application/business service.

    This layer coordinates validation, authorization, repository operations,
    and business rules.

    The service receives its repository through dependency injection.
    """

    def __init__(
        self,
        repository: TaskRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.settings = settings

    def create_task(self, owner_id: int, title: str) -> Task:
        ValidationUtils.validate_positive_integer(
            owner_id,
            "owner_id",
        )

        normalized_title = ValidationUtils.normalize_title(
            title,
            self.settings.max_title_length,
        )

        task = Task(
            id=0,
            title=normalized_title,
            owner_id=owner_id,
        )

        return self.repository.create(task)

    def get_task(self, actor_id: int, task_id: int) -> Task:
        ValidationUtils.validate_positive_integer(
            actor_id,
            "actor_id",
        )

        ValidationUtils.validate_positive_integer(
            task_id,
            "task_id",
        )

        task = self.repository.get_by_id(task_id)

        if task is None:
            raise NotFoundError("Task not found")

        self._ensure_owner(actor_id, task)

        return task

    def list_tasks(self, actor_id: int) -> List[Task]:
        ValidationUtils.validate_positive_integer(
            actor_id,
            "actor_id",
        )

        return self.repository.list_by_owner(actor_id)

    def complete_task(self, actor_id: int, task_id: int) -> Task:
        task = self.get_task(actor_id, task_id)

        if task.status == TaskStatus.COMPLETED:
            raise ConflictError("Task is already completed")

        task.status = TaskStatus.COMPLETED

        return self.repository.update(task)

    def delete_task(self, actor_id: int, task_id: int) -> None:
        task = self.get_task(actor_id, task_id)

        if not self.repository.delete(task.id):
            raise NotFoundError("Task was already deleted")

    @staticmethod
    def _ensure_owner(actor_id: int, task: Task) -> None:
        if task.owner_id != actor_id:
            raise AuthorizationError(
                "The actor does not own this task"
            )


# ============================================================================
# 12. PRESENTATION/API-LIKE LAYER
# ============================================================================

class TaskController:
    """
    A small presentation-layer simulation.

    A real HTTP controller would receive an HTTP request and return an HTTP
    response. Here we use dictionaries to keep the example dependency-free.
    """

    def __init__(self, service: TaskService) -> None:
        self.service = service

    def create(self, request: dict) -> dict:
        try:
            task = self.service.create_task(
                owner_id=request["owner_id"],
                title=request["title"],
            )

            return {
                "status": 201,
                "data": self._serialize(task),
            }

        except KeyError as error:
            return {
                "status": 400,
                "error": f"Missing field: {error.args[0]}",
            }

        except ValidationError as error:
            return {
                "status": 400,
                "error": str(error),
            }

    def get(self, actor_id: int, task_id: int) -> dict:
        try:
            task = self.service.get_task(
                actor_id,
                task_id,
            )

            return {
                "status": 200,
                "data": self._serialize(task),
            }

        except NotFoundError as error:
            return {
                "status": 404,
                "error": str(error),
            }

        except AuthorizationError as error:
            return {
                "status": 403,
                "error": str(error),
            }

    @staticmethod
    def _serialize(task: Task) -> dict:
        return {
            "id": task.id,
            "title": task.title,
            "owner_id": task.owner_id,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
        }


# ============================================================================
# 13. LOGGING CONFIGURATION
# ============================================================================

def configure_logging(settings: Settings) -> None:
    """
    Logging configuration belongs near application startup rather than
    being repeated independently inside every service.
    """

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


logger = logging.getLogger("backend.study")


# ============================================================================
# 14. APPLICATION COMPOSITION ROOT
# ============================================================================

class Application:
    """
    The composition root constructs the application's dependencies.

    This is an important architectural boundary.

    Business classes do not construct their own repository. The application
    decides which repository implementation to use.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        repository = InMemoryTaskRepository()

        service = TaskService(
            repository=repository,
            settings=settings,
        )

        self.task_controller = TaskController(service)


def demonstrate_layered_application() -> None:
    print("\n--- Layered application ---")

    settings = Settings.from_environment()
    settings.validate()
    configure_logging(settings)

    application = Application(settings)

    controller = application.task_controller

    response = controller.create(
        {
            "owner_id": 101,
            "title": "  Learn   layered   backend architecture  ",
        }
    )

    print("Create response:")
    print(response)

    task_id = response["data"]["id"]

    print("\nGet response:")
    print(controller.get(101, task_id))

    print("\nUnauthorized get response:")
    print(controller.get(999, task_id))


# ============================================================================
# 15. SERVICE WITH A SECOND REPOSITORY IMPLEMENTATION
# ============================================================================

class RecordingTaskRepository(InMemoryTaskRepository):
    """
    Test-oriented repository.

    Because the service depends on the repository interface rather than a
    concrete database, another implementation can be substituted.
    """

    def __init__(self) -> None:
        super().__init__()
        self.operations: List[str] = []

    def create(self, task: Task) -> Task:
        self.operations.append("create")
        return super().create(task)

    def update(self, task: Task) -> Task:
        self.operations.append("update")
        return super().update(task)

    def delete(self, task_id: int) -> bool:
        self.operations.append("delete")
        return super().delete(task_id)


def demonstrate_dependency_injection() -> None:
    print("\n--- Dependency injection ---")

    settings = Settings(
        app_name="Test",
        environment="test",
        debug=True,
        log_level="WARNING",
        database_url="memory://test",
        secret_key="test-secret",
        max_title_length=100,
    )

    repository = RecordingTaskRepository()

    service = TaskService(
        repository=repository,
        settings=settings,
    )

    task = service.create_task(
        owner_id=5,
        title="Dependency injection",
    )

    service.complete_task(5, task.id)

    print("Repository operations:", repository.operations)


# ============================================================================
# 16. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n--- Edge cases ---")

    settings = Settings(
        app_name="Edge Case Demo",
        environment="test",
        debug=True,
        log_level="WARNING",
        database_url="memory://test",
        secret_key="test-secret",
        max_title_length=20,
    )

    service = TaskService(
        repository=InMemoryTaskRepository(),
        settings=settings,
    )

    cases = [
        ("empty title", 1, "   "),
        ("too long", 1, "This title is definitely too long"),
        ("invalid owner", 0, "Valid title"),
    ]

    for name, owner_id, title in cases:
        try:
            service.create_task(owner_id, title)
        except ApplicationError as error:
            print(f"{name}: {error}")

    task = service.create_task(1, "Important task")

    service.complete_task(1, task.id)

    try:
        service.complete_task(1, task.id)
    except ConflictError as error:
        print("duplicate completion:", error)

    try:
        service.get_task(2, task.id)
    except AuthorizationError as error:
        print("unauthorized access:", error)

    try:
        service.get_task(1, 9999)
    except NotFoundError as error:
        print("missing task:", error)


# ============================================================================
# 17. SECURITY EXAMPLE
# ============================================================================

def demonstrate_security_utility() -> None:
    print("\n--- Security utility ---")

    password = "correct-horse-battery"

    encoded = SecurityUtils.hash_password(password)

    print("Stored password representation:")
    print(encoded)

    print(
        "Correct password:",
        SecurityUtils.verify_password(password, encoded),
    )

    print(
        "Wrong password:",
        SecurityUtils.verify_password("wrong-password", encoded),
    )

    """
    Security principles demonstrated:

    - Do not store plaintext passwords.
    - Generate a unique random salt.
    - Use constant-time comparison when comparing sensitive derived values.
    - Keep secrets out of source control.
    - Avoid returning sensitive implementation details to API clients.

    Authentication and authorization are different concerns.

    Authentication asks:
        "Who is this actor?"

    Authorization asks:
        "Is this actor allowed to perform this operation?"

    TaskService demonstrates authorization through ownership checks.
    """


# ============================================================================
# 18. CONFIGURATION SAFETY EXAMPLE
# ============================================================================

def demonstrate_configuration_validation() -> None:
    print("\n--- Configuration validation ---")

    production_settings = Settings(
        app_name="Production Backend",
        environment="production",
        debug=True,
        log_level="INFO",
        database_url="postgresql://database.example/app",
        secret_key="development-only-secret",
        max_title_length=100,
    )

    try:
        production_settings.validate()
    except ValueError as error:
        print("Rejected unsafe configuration:", error)


# ============================================================================
# 19. PERFORMANCE DISCUSSION THROUGH EXECUTABLE MEASUREMENT
# ============================================================================

def measure_repository_lookup() -> None:
    """
    This demonstrates measurement rather than assuming performance.

    The dictionary lookup by ID is approximately O(1) average time.

    Listing tasks by owner scans all stored tasks in this simple repository,
    which is O(n).

    A real database can use an index on owner_id to avoid scanning every row.
    """

    repository = InMemoryTaskRepository()

    for owner_id in range(1, 101):
        for number in range(20):
            repository.create(
                Task(
                    id=0,
                    title=f"Task {owner_id}-{number}",
                    owner_id=owner_id,
                )
            )

    start = time.perf_counter()

    for _ in range(10_000):
        repository.get_by_id(1)

    id_lookup_duration = time.perf_counter() - start

    start = time.perf_counter()

    for _ in range(100):
        repository.list_by_owner(50)

    owner_list_duration = time.perf_counter() - start

    print("\n--- Simple performance measurement ---")
    print(
        f"10,000 ID lookups: "
        f"{id_lookup_duration:.6f} seconds"
    )
    print(
        f"100 owner scans: "
        f"{owner_list_duration:.6f} seconds"
    )


# ============================================================================
# 20. TESTING
# ============================================================================

class TaskServiceTests(unittest.TestCase):
    """
    Unit tests target the service layer directly.

    This is easier than testing the entire application stack for every rule.
    """

    def setUp(self) -> None:
        self.settings = Settings(
            app_name="Tests",
            environment="test",
            debug=True,
            log_level="WARNING",
            database_url="memory://tests",
            secret_key="test-secret",
            max_title_length=100,
        )

        self.repository = InMemoryTaskRepository()

        self.service = TaskService(
            repository=self.repository,
            settings=self.settings,
        )

    def test_create_task_normalizes_title(self) -> None:
        task = self.service.create_task(
            1,
            "  hello    world  ",
        )

        self.assertEqual(task.title, "hello world")
        self.assertEqual(task.owner_id, 1)

    def test_empty_title_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create_task(1, " ")

    def test_task_can_be_completed(self) -> None:
        task = self.service.create_task(1, "Finish unit test")

        completed = self.service.complete_task(1, task.id)

        self.assertEqual(
            completed.status,
            TaskStatus.COMPLETED,
        )

    def test_second_completion_is_conflict(self) -> None:
        task = self.service.create_task(1, "Complete once")

        self.service.complete_task(1, task.id)

        with self.assertRaises(ConflictError):
            self.service.complete_task(1, task.id)

    def test_other_user_cannot_access_task(self) -> None:
        task = self.service.create_task(1, "Private task")

        with self.assertRaises(AuthorizationError):
            self.service.get_task(2, task.id)

    def test_missing_task_is_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.get_task(1, 999)

    def test_delete_task(self) -> None:
        task = self.service.create_task(1, "Delete me")

        self.service.delete_task(1, task.id)

        with self.assertRaises(NotFoundError):
            self.service.get_task(1, task.id)


def run_tests() -> None:
    print("\n--- Unit tests ---")

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TaskServiceTests
    )

    result = unittest.TextTestRunner(
        verbosity=1,
    ).run(suite)

    print(
        f"Tests run: {result.testsRun}, "
        f"failures: {len(result.failures)}, "
        f"errors: {len(result.errors)}"
    )


# ============================================================================
# 21. ARCHITECTURAL COMPARISON
# ============================================================================

def print_architectural_comparison() -> None:
    print(
        """
--- Architectural comparison ---

Small script:
    main.py
    Everything may be in one file.
    Advantage: simple.
    Disadvantage: responsibility boundaries disappear quickly.

Modular application:
    modules split by responsibility.
    Advantage: easier navigation and testing.
    Risk: too many tiny modules can make the system harder to understand.

Layered application:
    API -> Service -> Repository.
    Advantage: clear responsibility boundaries.
    Risk: excessive layering can create unnecessary indirection.

Feature-oriented application:
    tasks/
        routes.py
        service.py
        repository.py
        models.py

    users/
        routes.py
        service.py
        repository.py
        models.py

    Advantage:
        Related code stays close to the feature.

    Risk:
        Shared concepts can become duplicated if boundaries are poorly chosen.

The best structure depends on application size, team size, deployment model,
domain complexity, and expected change.
"""
    )


# ============================================================================
# 22. COMMON ARCHITECTURAL MISTAKES
# ============================================================================

def print_common_mistakes() -> None:
    print(
        """
--- Common mistakes ---

1. One giant file:
   Routes, database queries, validation, business rules, and configuration
   all live together.

2. Service classes that contain everything:
   A service should not become an enormous replacement for the entire
   application.

3. Utilities containing business rules:
   A generic helper should not silently decide business policy.

4. Configuration scattered everywhere:
   Reading environment variables from dozens of modules makes behavior
   difficult to reason about.

5. Hard-coded secrets:
   Credentials and private keys should not be committed to source control.

6. Circular imports:
   Usually indicate dependencies between modules are poorly arranged.

7. Importing infrastructure into domain code unnecessarily:
   Pure domain logic is easier to test and reuse.

8. Over-abstraction:
   Creating interfaces for every single function can add complexity
   without providing meaningful flexibility.

9. Under-abstraction:
   Direct database access from every route couples the entire application
   to persistence details.

10. Ignoring boundaries:
    A clean directory structure is not enough. The code must also respect
    the responsibilities represented by the directories.
"""
    )


# ============================================================================
# 23. MAIN PROGRAM
# ============================================================================

def main() -> None:
    print("=" * 72)
    print("BACKEND PROJECT STRUCTURE STUDY PROGRAM")
    print("=" * 72)

    demonstrate_unstructured_application()
    demonstrate_layered_application()
    demonstrate_dependency_injection()
    demonstrate_edge_cases()
    demonstrate_security_utility()
    demonstrate_configuration_validation()
    measure_repository_lookup()
    print_architectural_comparison()
    print_common_mistakes()
    run_tests()

    print("\n--- Study program complete ---")


if __name__ == "__main__":
    main()
