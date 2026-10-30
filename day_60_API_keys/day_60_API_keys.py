#!/usr/bin/env python3
"""Secure API key lifecycle manager using SQLite and the Python standard library."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


KEY_PATTERN = re.compile(r"^ak_live_([a-f0-9]{16})\.([A-Za-z0-9_-]{43})$")
SCOPE_PATTERN = re.compile(r"^[a-z][a-z0-9:_-]{0,63}$")
MAX_LIFETIME = timedelta(days=365)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class APIKeyError(Exception):
    """Base exception for API key lifecycle failures."""


class InvalidInput(APIKeyError):
    """Raised when an API key request violates validation rules."""


class KeyNotFound(APIKeyError):
    """Raised when a requested key does not exist."""


class KeyStateError(APIKeyError):
    """Raised when an operation is invalid for the current key state."""


@dataclass(frozen=True)
class IssuedKey:
    key_id: str
    token: str

    def __repr__(self) -> str:
        return f"IssuedKey(key_id={self.key_id!r}, token='<redacted>')"


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    reason: str
    key_id: Optional[str] = None
    owner: Optional[str] = None
    scopes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class KeyMetadata:
    key_id: str
    owner: str
    label: str
    status: str
    scopes: frozenset[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    rotated_from: Optional[str]


class APIKeyStore:
    """
    SQLite-backed lifecycle manager.

    The database stores an HMAC-SHA-256 verifier, never the original token.
    The pepper must be protected separately from the database.
    """

    def __init__(self, database: str = ":memory:", pepper: Optional[bytes] = None):
        if pepper is None or len(pepper) < 32:
            raise InvalidInput("A pepper containing at least 32 bytes is required.")

        self._pepper = bytes(pepper)
        self._connection = sqlite3.connect(
            database,
            check_same_thread=False,
            isolation_level=None,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")

        if database != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")

        self._lock = threading.RLock()
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL CHECK(length(owner) BETWEEN 1 AND 120),
                    label TEXT NOT NULL CHECK(length(label) BETWEEN 1 AND 120),
                    verifier BLOB NOT NULL CHECK(length(verifier) = 32),
                    status TEXT NOT NULL CHECK(status IN ('active', 'revoked')),
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    last_used_at TEXT,
                    revoked_at TEXT,
                    rotated_from TEXT REFERENCES api_keys(key_id),
                    CHECK(expires_at IS NULL OR expires_at > created_at),
                    CHECK(
                        (status = 'active' AND revoked_at IS NULL)
                        OR
                        (status = 'revoked' AND revoked_at IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS api_key_scopes (
                    key_id TEXT NOT NULL REFERENCES api_keys(key_id),
                    scope TEXT NOT NULL CHECK(length(scope) BETWEEN 1 AND 64),
                    PRIMARY KEY (key_id, scope)
                );

                CREATE TABLE IF NOT EXISTS api_key_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL REFERENCES api_keys(key_id),
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_api_keys_owner
                    ON api_keys(owner, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_api_keys_expiration
                    ON api_keys(expires_at)
                    WHERE status = 'active';

                CREATE INDEX IF NOT EXISTS idx_api_key_events_key
                    ON api_key_events(key_id, occurred_at DESC);
                """
            )

    def _transaction(self):
        """Return a context manager that serializes SQLite write transactions."""
        return _SQLiteTransaction(self._connection, self._lock)

    def _digest(self, secret: str) -> bytes:
        return hmac.new(
            self._pepper,
            secret.encode("utf-8"),
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _validate_text(value: str, field: str, maximum: int = 120) -> str:
        if not isinstance(value, str):
            raise InvalidInput(f"{field} must be a string.")
        value = value.strip()
        if not value or len(value) > maximum:
            raise InvalidInput(f"{field} must contain 1 to {maximum} characters.")
        return value

    @staticmethod
    def _normalize_scopes(scopes) -> tuple[str, ...]:
        if isinstance(scopes, (str, bytes)):
            raise InvalidInput("Scopes must be an iterable of scope names.")

        normalized = sorted(set(scopes))
        if not normalized:
            raise InvalidInput("At least one scope is required.")

        for scope in normalized:
            if not isinstance(scope, str) or not SCOPE_PATTERN.fullmatch(scope):
                raise InvalidInput(f"Invalid scope: {scope!r}")

        return tuple(normalized)

    @staticmethod
    def _expiration(expires_in: Optional[timedelta]) -> Optional[datetime]:
        if expires_in is None:
            return None
        if not isinstance(expires_in, timedelta):
            raise InvalidInput("expires_in must be a datetime.timedelta.")
        if expires_in <= timedelta(0) or expires_in > MAX_LIFETIME:
            raise InvalidInput("Lifetime must be greater than zero and at most 365 days.")
        return utc_now() + expires_in

    @staticmethod
    def _parse_token(token: str) -> Optional[tuple[str, str]]:
        if not isinstance(token, str):
            return None
        match = KEY_PATTERN.fullmatch(token)
        if not match:
            return None
        return match.group(1), match.group(2)

    def _new_material(self) -> tuple[str, str, str, bytes]:
        key_id = secrets.token_hex(8)
        secret = secrets.token_urlsafe(32)
        token = f"ak_live_{key_id}.{secret}"
        return key_id, secret, token, self._digest(secret)

    def _insert_key(
        self,
        connection: sqlite3.Connection,
        owner: str,
        label: str,
        scopes: tuple[str, ...],
        expires_at: Optional[datetime],
        actor: str,
        rotated_from: Optional[str] = None,
    ) -> IssuedKey:
        key_id, _, token, verifier = self._new_material()
        now = utc_now()

        connection.execute(
            """
            INSERT INTO api_keys (
                key_id, owner, label, verifier, status,
                created_at, expires_at, rotated_from
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                key_id,
                owner,
                label,
                verifier,
                timestamp(now),
                timestamp(expires_at) if expires_at else None,
                rotated_from,
            ),
        )

        connection.executemany(
            "INSERT INTO api_key_scopes(key_id, scope) VALUES (?, ?)",
            [(key_id, scope) for scope in scopes],
        )

        connection.execute(
            """
            INSERT INTO api_key_events(key_id, event_type, actor, occurred_at, details)
            VALUES (?, 'issued', ?, ?, ?)
            """,
            (
                key_id,
                actor,
                timestamp(now),
                json.dumps({"rotated_from": rotated_from}),
            ),
        )

        return IssuedKey(key_id=key_id, token=token)

    def issue(
        self,
        owner: str,
        label: str,
        scopes,
        expires_in: Optional[timedelta] = timedelta(days=90),
        actor: str = "system",
    ) -> IssuedKey:
        owner = self._validate_text(owner, "owner")
        label = self._validate_text(label, "label")
        actor = self._validate_text(actor, "actor")
        normalized_scopes = self._normalize_scopes(scopes)
        expires_at = self._expiration(expires_in)

        with self._transaction() as connection:
            return self._insert_key(
                connection,
                owner,
                label,
                normalized_scopes,
                expires_at,
                actor,
            )

    def validate(self, token: str, required_scope: str) -> ValidationResult:
        if not isinstance(required_scope, str) or not SCOPE_PATTERN.fullmatch(required_scope):
            return ValidationResult(False, "invalid_scope")

        parsed = self._parse_token(token)
        if parsed is None:
            return ValidationResult(False, "malformed_token")

        key_id, secret = parsed
        candidate = self._digest(secret)

        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()

            if row is None:
                return ValidationResult(False, "invalid_credentials")

            # compare_digest avoids ordinary byte-by-byte comparison timing.
            if not hmac.compare_digest(candidate, bytes(row["verifier"])):
                return ValidationResult(False, "invalid_credentials")

            if row["status"] != "active":
                return ValidationResult(False, "revoked")

            expires_at = parse_timestamp(row["expires_at"])
            if expires_at is not None and expires_at <= utc_now():
                return ValidationResult(False, "expired")

            scopes = frozenset(
                item["scope"]
                for item in connection.execute(
                    "SELECT scope FROM api_key_scopes WHERE key_id = ?",
                    (key_id,),
                )
            )

            if required_scope not in scopes and "*" not in scopes:
                return ValidationResult(
                    False,
                    "insufficient_scope",
                    key_id=key_id,
                    owner=row["owner"],
                    scopes=scopes,
                )

            connection.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_id = ? AND status = 'active'",
                (timestamp(utc_now()), key_id),
            )

            return ValidationResult(
                True,
                "accepted",
                key_id=key_id,
                owner=row["owner"],
                scopes=scopes,
            )

    def rotate(
        self,
        token: str,
        actor: str,
        expires_in: Optional[timedelta] = None,
    ) -> IssuedKey:
        parsed = self._parse_token(token)
        if parsed is None:
            raise InvalidInput("The supplied token is malformed.")

        old_key_id, secret = parsed
        candidate = self._digest(secret)
        actor = self._validate_text(actor, "actor")

        with self._transaction() as connection:
            old = connection.execute(
                "SELECT * FROM api_keys WHERE key_id = ?",
                (old_key_id,),
            ).fetchone()

            if old is None or not hmac.compare_digest(candidate, bytes(old["verifier"])):
                raise KeyNotFound("The supplied key could not be authenticated.")

            if old["status"] != "active":
                raise KeyStateError("Only an active key can be rotated.")

            old_expiration = parse_timestamp(old["expires_at"])
            if old_expiration is not None and old_expiration <= utc_now():
                raise KeyStateError("An expired key cannot be rotated.")

            scopes = tuple(
                row["scope"]
                for row in connection.execute(
                    "SELECT scope FROM api_key_scopes WHERE key_id = ? ORDER BY scope",
                    (old_key_id,),
                )
            )

            new_expiration = (
                self._expiration(expires_in)
                if expires_in is not None
                else old_expiration
            )

            replacement = self._insert_key(
                connection,
                old["owner"],
                old["label"],
                scopes,
                new_expiration,
                actor,
                rotated_from=old_key_id,
            )

            revoked_at = timestamp(utc_now())
            connection.execute(
                """
                UPDATE api_keys
                SET status = 'revoked', revoked_at = ?
                WHERE key_id = ? AND status = 'active'
                """,
                (revoked_at, old_key_id),
            )

            connection.execute(
                """
                INSERT INTO api_key_events(key_id, event_type, actor, occurred_at, details)
                VALUES (?, 'rotated', ?, ?, ?)
                """,
                (
                    old_key_id,
                    actor,
                    revoked_at,
                    json.dumps({"replacement_key_id": replacement.key_id}),
                ),
            )

            return replacement

    def revoke(self, key_id: str, actor: str) -> bool:
        key_id = self._validate_text(key_id, "key_id", 32)
        actor = self._validate_text(actor, "actor")

        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()

            if row is None:
                raise KeyNotFound(f"Key {key_id} does not exist.")

            if row["status"] == "revoked":
                return False

            now = timestamp(utc_now())
            connection.execute(
                """
                UPDATE api_keys
                SET status = 'revoked', revoked_at = ?
                WHERE key_id = ? AND status = 'active'
                """,
                (now, key_id),
            )

            connection.execute(
                """
                INSERT INTO api_key_events(key_id, event_type, actor, occurred_at)
                VALUES (?, 'revoked', ?, ?)
                """,
                (key_id, actor, now),
            )

            return True

    def metadata(self, key_id: str) -> KeyMetadata:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()

            if row is None:
                raise KeyNotFound(f"Key {key_id} does not exist.")

            scopes = frozenset(
                item["scope"]
                for item in self._connection.execute(
                    "SELECT scope FROM api_key_scopes WHERE key_id = ?",
                    (key_id,),
                )
            )

            return KeyMetadata(
                key_id=row["key_id"],
                owner=row["owner"],
                label=row["label"],
                status=row["status"],
                scopes=scopes,
                created_at=parse_timestamp(row["created_at"]),
                expires_at=parse_timestamp(row["expires_at"]),
                last_used_at=parse_timestamp(row["last_used_at"]),
                revoked_at=parse_timestamp(row["revoked_at"]),
                rotated_from=row["rotated_from"],
            )

    def audit_events(self, key_id: str) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT event_type, actor, occurred_at, details
                FROM api_key_events
                WHERE key_id = ?
                ORDER BY event_id
                """,
                (key_id,),
            ).fetchall()

            return [
                {
                    "event": row["event_type"],
                    "actor": row["actor"],
                    "occurred_at": row["occurred_at"],
                    "details": json.loads(row["details"]),
                }
                for row in rows
            ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class _SQLiteTransaction:
    """Small transaction adapter that guarantees rollback on exceptions."""

    def __init__(self, connection: sqlite3.Connection, lock: threading.RLock):
        self.connection = connection
        self.lock = lock

    def __enter__(self):
        self.lock.acquire()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            return self.connection
        except Exception:
            self.lock.release()
            raise

    def __exit__(self, exception_type, exception, traceback):
        try:
            if exception_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.lock.release()
        return False


def run_demonstration() -> None:
    # A random pepper is appropriate for this in-memory demonstration.
    # Persistent deployments must supply a stable, externally protected pepper.
    configured_pepper = os.environ.get("API_KEY_PEPPER")
    database = os.environ.get("API_KEY_DB", ":memory:")

    if database != ":memory:" and not configured_pepper:
        raise RuntimeError(
            "Set API_KEY_PEPPER to a stable secret of at least 32 bytes "
            "when using a persistent database."
        )

    pepper = (
        configured_pepper.encode("utf-8")
        if configured_pepper
        else secrets.token_bytes(32)
    )

    store = APIKeyStore(database=database, pepper=pepper)

    try:
        issued = store.issue(
            owner="inventory-service",
            label="warehouse integration",
            scopes={"inventory:read", "inventory:update"},
            expires_in=timedelta(days=30),
            actor="platform-admin",
        )

        print("Issued key ID:", issued.key_id)
        print("One-time token:", issued.token)

        valid = store.validate(issued.token, "inventory:read")
        assert valid.accepted
        assert valid.owner == "inventory-service"

        denied = store.validate(issued.token, "billing:write")
        assert not denied.accepted
        assert denied.reason == "insufficient_scope"

        malformed = store.validate("not-a-key", "inventory:read")
        assert not malformed.accepted

        replacement = store.rotate(
            issued.token,
            actor="security-admin",
            expires_in=timedelta(days=60),
        )

        old_result = store.validate(issued.token, "inventory:read")
        assert not old_result.accepted
        assert old_result.reason == "revoked"

        new_result = store.validate(replacement.token, "inventory:read")
        assert new_result.accepted

        store.revoke(replacement.key_id, actor="security-admin")

        revoked_result = store.validate(replacement.token, "inventory:read")
        assert not revoked_result.accepted
        assert revoked_result.reason == "revoked"

        print("\nReplacement key ID:", replacement.key_id)
        print("Replacement metadata:", store.metadata(replacement.key_id))
        print("Audit events:", store.audit_events(replacement.key_id))
        print("\nAll lifecycle assertions passed.")

    finally:
        store.close()


if __name__ == "__main__":
    run_demonstration()
