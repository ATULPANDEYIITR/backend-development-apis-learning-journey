#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import sqlite3
from typing import Any


class QueryMode(Enum):
    VULNERABLE = "vulnerable"
    PARAMETERIZED = "parameterized"


class AuthenticationError(Exception):
    pass


class ValidationError(Exception):
    pass


@dataclass(frozen=True)
class User:
    user_id: int
    username: str
    password_hash: str
    role: str


def hash_password(password: str) -> str:
    salt = b"sql-injection-demo-fixed-salt"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return digest.hex()


def create_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'admin'))
        )
        """
    )

    users = [
        (1, "alice", hash_password("AlicePass!23"), "user"),
        (2, "bob", hash_password("BobPass!23"), "user"),
        (3, "admin", hash_password("AdminPass!23"), "admin"),
    ]

    connection.executemany(
        """
        INSERT INTO users(user_id, username, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        users,
    )
    connection.commit()
    return connection


def validate_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValidationError("username must be a string")

    username = username.strip()

    if not username:
        raise ValidationError("username cannot be empty")

    if len(username) > 80:
        raise ValidationError("username is too long")

    return username


def vulnerable_login(
    connection: sqlite3.Connection,
    username: str,
    password: str,
) -> list[tuple[Any, ...]]:
    """
    Deliberately unsafe construction used only to show the failure mechanism.
    User-controlled text becomes part of SQL syntax.
    """
    sql = (
        "SELECT user_id, username, role "
        "FROM users "
        f"WHERE username = '{username}' "
        f"AND password_hash = '{hash_password(password)}'"
    )

    print("\n[UNSAFE SQL]")
    print(sql)

    try:
        return connection.execute(sql).fetchall()
    except sqlite3.Error as exc:
        print(f"SQL error: {exc}")
        return []


def parameterized_login(
    connection: sqlite3.Connection,
    username: str,
    password: str,
) -> list[tuple[Any, ...]]:
    """
    Values are transmitted separately from SQL syntax.
    The database never interprets username as SQL grammar.
    """
    username = validate_username(username)

    sql = (
        "SELECT user_id, username, role "
        "FROM users "
        "WHERE username = ? AND password_hash = ?"
    )

    parameters = (username, hash_password(password))

    print("\n[SAFE SQL]")
    print(sql)
    print(f"[BOUND PARAMETERS] username={username!r}, password=<redacted>")

    return connection.execute(sql, parameters).fetchall()


class UserRepository:
    """
    Small repository abstraction representing an ORM-style data-access layer.

    The important property is not the class name. It is that SQL text and
    user-controlled values remain separate all the way to execute().
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_username(self, username: str) -> User | None:
        username = validate_username(username)

        row = self.connection.execute(
            """
            SELECT user_id, username, password_hash, role
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if row is None:
            return None

        return User(*row)


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def authenticate(self, username: str, password: str) -> User:
        user = self.repository.find_by_username(username)

        if user is None:
            raise AuthenticationError("invalid credentials")

        supplied_hash = hash_password(password)

        if not hmac.compare_digest(user.password_hash, supplied_hash):
            raise AuthenticationError("invalid credentials")

        return user


def demonstrate_parameter_binding(connection: sqlite3.Connection) -> None:
    normal_result = parameterized_login(
        connection,
        "alice",
        "AlicePass!23",
    )

    print(f"[NORMAL LOGIN RESULT] {normal_result}")

    injection_text = "' OR '1'='1"

    print("\n[INJECTION-LIKE INPUT]")
    print(f"username={injection_text!r}")

    safe_result = parameterized_login(
        connection,
        injection_text,
        "wrong-password",
    )

    print(f"[SAFE RESULT] {safe_result}")


def demonstrate_repository(connection: sqlite3.Connection) -> None:
    repository = UserRepository(connection)
    service = UserService(repository)

    authenticated = service.authenticate("admin", "AdminPass!23")
    print(
        "\n[ORM-STYLE REPOSITORY]",
        f"authenticated={authenticated.username!r}",
        f"role={authenticated.role!r}",
    )

    try:
        service.authenticate("admin", "wrong-password")
    except AuthenticationError as exc:
        print(f"[AUTHENTICATION FAILURE] {exc}")


def demonstrate_input_validation(connection: sqlite3.Connection) -> None:
    print("\n[VALIDATION TEST]")

    invalid_inputs = ["", "   ", "x" * 81]

    for value in invalid_inputs:
        try:
            parameterized_login(connection, value, "anything")
        except ValidationError as exc:
            print(f"Rejected {value!r}: {exc}")


def inspect_query_plan(connection: sqlite3.Connection) -> None:
    """
    Query planning demonstrates that parameterization does not prevent
    normal indexing. The index is created for a legitimate lookup workload.
    """
    connection.execute(
        "CREATE INDEX idx_users_username ON users(username)"
    )

    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT user_id, username, role
        FROM users
        WHERE username = ?
        """,
        ("alice",),
    ).fetchall()

    print("\n[QUERY PLAN]")
    for row in plan:
        print(row)


def main() -> None:
    connection = create_database()

    try:
        # This call illustrates why string concatenation is unsafe.
        vulnerable_login(
            connection,
            "alice",
            "AlicePass!23",
        )

        demonstrate_parameter_binding(connection)
        demonstrate_repository(connection)
        demonstrate_input_validation(connection)
        inspect_query_plan(connection)

        print("\n[SECURITY CONTROLS]")
        print("1. Keep SQL syntax separate from user-controlled values.")
        print("2. Use parameterized queries at the database boundary.")
        print("3. Validate input for domain correctness, not as the SQL defense.")
        print("4. Use least-privilege database accounts.")
        print("5. Do not expose SQL errors to untrusted clients.")
        print("6. Store password hashes rather than plaintext passwords.")
        print("7. Keep ORM-generated SQL parameterized.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
