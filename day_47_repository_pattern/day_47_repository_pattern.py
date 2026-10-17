from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
import json
import sqlite3
import tempfile


# Repository Pattern:
# The domain/service layer depends on a repository abstraction rather than
# directly depending on SQLite. This separates business rules from persistence.
@dataclass(frozen=True)
class User:
    user_id: int
    name: str
    email: str
    active: bool = True


class UserRepository(Protocol):
    def get_by_id(self, user_id: int) -> User | None:
        ...

    def get_by_email(self, email: str) -> User | None:
        ...

    def list_active(self) -> list[User]:
        ...

    def save(self, user: User) -> User:
        ...

    def delete(self, user_id: int) -> bool:
        ...


class InMemoryUserRepository:
    """Repository implementation useful for fast tests and local simulations."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id = 1

    def get_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return next(
            (user for user in self._users.values() if user.email == normalized),
            None,
        )

    def list_active(self) -> list[User]:
        return [user for user in self._users.values() if user.active]

    def save(self, user: User) -> User:
        if user.user_id == 0:
            user = User(
                self._next_id,
                user.name,
                user.email,
                user.active,
            )
            self._next_id += 1

        existing = self.get_by_email(user.email)
        if existing and existing.user_id != user.user_id:
            raise ValueError("Email address already belongs to another user")

        self._users[user.user_id] = user
        return user

    def delete(self, user_id: int) -> bool:
        return self._users.pop(user_id, None) is not None


class SQLiteUserRepository:
    """Persistent repository using the Python standard-library sqlite3 module."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK(length(trim(name)) >= 2),
                email TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
            )
            """
        )
        self._connection.commit()

    @staticmethod
    def _row_to_user(row: sqlite3.Row | None) -> User | None:
        if row is None:
            return None

        return User(
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            email=str(row["email"]),
            active=bool(row["active"]),
        )

    def get_by_id(self, user_id: int) -> User | None:
        row = self._connection.execute(
            "SELECT user_id, name, email, active FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return self._row_to_user(row)

    def get_by_email(self, email: str) -> User | None:
        row = self._connection.execute(
            "SELECT user_id, name, email, active FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        return self._row_to_user(row)

    def list_active(self) -> list[User]:
        rows = self._connection.execute(
            """
            SELECT user_id, name, email, active
            FROM users
            WHERE active = 1
            ORDER BY user_id
            """
        ).fetchall()
        return [self._row_to_user(row) for row in rows]  # type: ignore[misc]

    def save(self, user: User) -> User:
        normalized_email = user.email.strip().lower()

        if user.user_id == 0:
            cursor = self._connection.execute(
                """
                INSERT INTO users(name, email, active)
                VALUES (?, ?, ?)
                """,
                (user.name.strip(), normalized_email, int(user.active)),
            )
            self._connection.commit()
            return self.get_by_id(cursor.lastrowid)  # type: ignore[return-value]

        self._connection.execute(
            """
            UPDATE users
            SET name = ?, email = ?, active = ?
            WHERE user_id = ?
            """,
            (
                user.name.strip(),
                normalized_email,
                int(user.active),
                user.user_id,
            ),
        )
        self._connection.commit()
        saved = self.get_by_id(user.user_id)

        if saved is None:
            raise ValueError(f"User {user.user_id} does not exist")

        return saved

    def delete(self, user_id: int) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def close(self) -> None:
        self._connection.close()


class UserService:
    """
    Business logic depends only on UserRepository.

    The service does not know whether users are stored in memory, SQLite,
    PostgreSQL, an HTTP service, or another persistence mechanism.
    """

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register(self, name: str, email: str) -> User:
        clean_name = name.strip()
        clean_email = email.strip().lower()

        if len(clean_name) < 2:
            raise ValueError("Name must contain at least two characters")

        if "@" not in clean_email or "." not in clean_email.split("@")[-1]:
            raise ValueError("A valid email address is required")

        if self.repository.get_by_email(clean_email):
            raise ValueError("A user with this email already exists")

        return self.repository.save(
            User(
                user_id=0,
                name=clean_name,
                email=clean_email,
                active=True,
            )
        )

    def deactivate(self, user_id: int) -> User:
        user = self.repository.get_by_id(user_id)

        if user is None:
            raise LookupError("User does not exist")

        if not user.active:
            return user

        return self.repository.save(
            User(
                user_id=user.user_id,
                name=user.name,
                email=user.email,
                active=False,
            )
        )

    def export_active_users(self) -> str:
        records = [
            {
                **asdict(user),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
            for user in self.repository.list_active()
        ]
        return json.dumps(records, indent=2)


def demonstrate_repository_substitution() -> None:
    print("\n=== Repository abstraction with in-memory storage ===")

    repository = InMemoryUserRepository()
    service = UserService(repository)

    alice = service.register("Alice Rao", "ALICE@example.com")
    bob = service.register("Bob Singh", "bob@example.com")

    print(alice)
    print(bob)
    print(service.export_active_users())

    service.deactivate(alice.user_id)

    print("Active users after deactivation:")
    for user in repository.list_active():
        print(user)


def demonstrate_sqlite_repository() -> None:
    print("\n=== Same service with SQLite persistence ===")

    with tempfile.TemporaryDirectory() as directory:
        database_file = Path(directory) / "users.sqlite3"
        repository = SQLiteUserRepository(database_file)
        service = UserService(repository)

        created = service.register("Priya Sharma", "priya@example.com")
        service.register("Rahul Verma", "rahul@example.com")

        print("Created:", created)
        print("Lookup:", repository.get_by_email("PRIYA@example.com"))
        print("Active users:")
        for user in repository.list_active():
            print(user)

        service.deactivate(created.user_id)
        print("After deactivation:", repository.get_by_id(created.user_id))

        repository.close()


def demonstrate_failure_conditions() -> None:
    print("\n=== Validation and failure conditions ===")

    repository = InMemoryUserRepository()
    service = UserService(repository)

    service.register("Valid User", "valid@example.com")

    failures = [
        ("short name", lambda: service.register("A", "a@example.com")),
        ("bad email", lambda: service.register("Bad Email", "not-an-email")),
        (
            "duplicate email",
            lambda: service.register("Another User", "VALID@example.com"),
        ),
        ("missing user", lambda: service.deactivate(999)),
    ]

    for label, operation in failures:
        try:
            operation()
        except (ValueError, LookupError) as exc:
            print(f"{label}: {exc}")


def demonstrate_unit_test_without_database() -> None:
    """
    Dependency inversion makes the service testable without creating a database.

    A small fake repository records the behavior required by this particular
    test. This is useful when business rules need fast deterministic tests.
    """

    repository = InMemoryUserRepository()
    service = UserService(repository)

    user = service.register("Test User", "test@example.com")

    assert user.user_id == 1
    assert repository.get_by_email("test@example.com") == user

    print("\nRepository-independent service test passed")


def main() -> None:
    print("Repository Pattern: Data Access Abstraction and Separation of Concerns")
    demonstrate_repository_substitution()
    demonstrate_sqlite_repository()
    demonstrate_failure_conditions()
    demonstrate_unit_test_without_database()


if __name__ == "__main__":
    main()
