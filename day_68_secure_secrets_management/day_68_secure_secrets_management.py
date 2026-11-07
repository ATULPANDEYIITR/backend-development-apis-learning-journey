#!/usr/bin/env python3
"""
Secure Secrets Management
Environment variables, credentials, secret rotation, and secret managers.

Standard-library-only educational implementation.
Python 3.10+
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string
import unittest

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol


# ============================================================
# 1. Domain types
# ============================================================

class SecretState(Enum):
    ACTIVE = "active"
    STAGED = "staged"
    RETIRED = "retired"
    REVOKED = "revoked"


class SecretError(Exception):
    """Base exception for secrets-management failures."""


class SecretNotFoundError(SecretError):
    pass


class SecretAccessError(SecretError):
    pass


class SecretValidationError(SecretError):
    pass


class SecretStateError(SecretError):
    pass


@dataclass(frozen=True)
class SecretMetadata:
    name: str
    version: int
    state: SecretState
    created_at: datetime
    expires_at: Optional[datetime] = None


@dataclass
class SecretVersion:
    metadata: SecretMetadata
    value: str = field(repr=False)


@dataclass(frozen=True)
class AuditEvent:
    timestamp: datetime
    actor: str
    action: str
    secret_name: str
    version: Optional[int]
    outcome: str


# ============================================================
# 2. Secret validation and fingerprints
# ============================================================

def validate_secret_name(name: str) -> None:
    if not name or len(name) > 128:
        raise SecretValidationError("Invalid secret name.")

    allowed = set(string.ascii_letters + string.digits + "_-.")
    if any(character not in allowed for character in name):
        raise SecretValidationError("Secret name contains invalid characters.")


def validate_secret_value(value: str) -> None:
    if not isinstance(value, str) or len(value) < 16:
        raise SecretValidationError(
            "Secret must contain at least 16 characters."
        )

    if len(value) > 8192:
        raise SecretValidationError("Secret exceeds maximum length.")


def fingerprint(value: str) -> str:
    """Create a non-reversible SHA-256 identifier for change detection."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_secret(length: int = 40) -> str:
    if length < 32 or length > 256:
        raise SecretValidationError("Length must be between 32 and 256.")

    alphabet = string.ascii_letters + string.digits + "-_!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ============================================================
# 3. Access-control policy
# ============================================================

@dataclass(frozen=True)
class AccessPolicy:
    permissions: dict[str, frozenset[str]]

    def authorize(self, actor: str, action: str) -> None:
        if action not in self.permissions.get(actor, frozenset()):
            raise SecretAccessError(
                f"Actor '{actor}' is not authorized for this operation."
            )


DEFAULT_POLICY = AccessPolicy(
    permissions={
        "application": frozenset({"read"}),
        "security-admin": frozenset(
            {"read", "create", "rotate", "revoke", "metadata"}
        ),
        "auditor": frozenset({"metadata"}),
        "rotation-service": frozenset({"read", "create", "rotate"}),
    }
)


# ============================================================
# 4. Secret manager interface
# ============================================================

class SecretProvider(Protocol):
    def get_secret(self, name: str, actor: str) -> str:
        ...

    def get_metadata(self, name: str) -> list[SecretMetadata]:
        ...


class InMemorySecretManager:
    """
    Simulates a versioned secret manager.

    Production implementations should use an authenticated,
    encrypted external secret manager with durable audit storage.
    """

    def __init__(self, policy: AccessPolicy = DEFAULT_POLICY):
        self._versions: dict[str, list[SecretVersion]] = {}
        self._policy = policy
        self._audit: list[AuditEvent] = []

    def _record(
        self,
        actor: str,
        action: str,
        name: str,
        version: Optional[int],
        outcome: str,
    ) -> None:
        self._audit.append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                actor=actor,
                action=action,
                secret_name=name,
                version=version,
                outcome=outcome,
            )
        )

    def _authorize(
        self,
        actor: str,
        action: str,
        name: str,
        version: Optional[int] = None,
    ) -> None:
        try:
            self._policy.authorize(actor, action)
        except SecretAccessError:
            self._record(actor, action, name, version, "denied")
            raise

    def create_secret(
        self,
        name: str,
        value: str,
        actor: str,
        expires_in_days: Optional[int] = None,
    ) -> SecretMetadata:

        self._authorize(actor, "create", name)
        validate_secret_name(name)
        validate_secret_value(value)

        if name in self._versions:
            raise SecretStateError("Secret already exists.")

        if expires_in_days is not None and expires_in_days <= 0:
            raise SecretValidationError("Expiry must be positive.")

        now = datetime.now(timezone.utc)
        expiry = (
            now + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        )

        metadata = SecretMetadata(
            name=name,
            version=1,
            state=SecretState.ACTIVE,
            created_at=now,
            expires_at=expiry,
        )

        self._versions[name] = [
            SecretVersion(metadata=metadata, value=value)
        ]

        self._record(actor, "create", name, 1, "success")
        return metadata

    def get_secret(self, name: str, actor: str) -> str:
        self._authorize(actor, "read", name)

        versions = self._versions.get(name)
        if not versions:
            self._record(actor, "read", name, None, "not_found")
            raise SecretNotFoundError(name)

        now = datetime.now(timezone.utc)

        active = next(
            (
                version
                for version in reversed(versions)
                if version.metadata.state == SecretState.ACTIVE
            ),
            None,
        )

        if active is None:
            raise SecretStateError("No active secret version.")

        expiry = active.metadata.expires_at
        if expiry is not None and now >= expiry:
            raise SecretStateError("Active secret has expired.")

        self._record(
            actor,
            "read",
            name,
            active.metadata.version,
            "success",
        )

        return active.value

    def stage_rotation(
        self,
        name: str,
        new_value: str,
        actor: str,
    ) -> SecretMetadata:

        self._authorize(actor, "rotate", name)
        validate_secret_name(name)
        validate_secret_value(new_value)

        versions = self._versions.get(name)
        if not versions:
            raise SecretNotFoundError(name)

        if any(
            item.metadata.state == SecretState.STAGED
            for item in versions
        ):
            raise SecretStateError("A rotation is already staged.")

        active = next(
            (
                item
                for item in reversed(versions)
                if item.metadata.state == SecretState.ACTIVE
            ),
            None,
        )

        if active is None:
            raise SecretStateError("No active version exists.")

        if hmac.compare_digest(
            fingerprint(active.value),
            fingerprint(new_value),
        ):
            raise SecretValidationError(
                "New secret must differ from the active secret."
            )

        version_number = max(
            item.metadata.version for item in versions
        ) + 1

        metadata = SecretMetadata(
            name=name,
            version=version_number,
            state=SecretState.STAGED,
            created_at=datetime.now(timezone.utc),
        )

        versions.append(
            SecretVersion(metadata=metadata, value=new_value)
        )

        self._record(
            actor,
            "stage_rotation",
            name,
            version_number,
            "success",
        )

        return metadata

    def activate_rotation(self, name: str, actor: str) -> SecretMetadata:
        self._authorize(actor, "rotate", name)

        versions = self._versions.get(name)
        if not versions:
            raise SecretNotFoundError(name)

        staged = next(
            (
                item
                for item in reversed(versions)
                if item.metadata.state == SecretState.STAGED
            ),
            None,
        )

        if staged is None:
            raise SecretStateError("No staged version exists.")

        active = next(
            (
                item
                for item in reversed(versions)
                if item.metadata.state == SecretState.ACTIVE
            ),
            None,
        )

        if active is not None:
            active.metadata = SecretMetadata(
                name=name,
                version=active.metadata.version,
                state=SecretState.RETIRED,
                created_at=active.metadata.created_at,
                expires_at=active.metadata.expires_at,
            )

        staged.metadata = SecretMetadata(
            name=name,
            version=staged.metadata.version,
            state=SecretState.ACTIVE,
            created_at=staged.metadata.created_at,
        )

        self._record(
            actor,
            "activate_rotation",
            name,
            staged.metadata.version,
            "success",
        )

        return staged.metadata

    def revoke_version(
        self,
        name: str,
        version_number: int,
        actor: str,
    ) -> None:

        self._authorize(actor, "revoke", name, version_number)

        versions = self._versions.get(name)
        if not versions:
            raise SecretNotFoundError(name)

        target = next(
            (
                item
                for item in versions
                if item.metadata.version == version_number
            ),
            None,
        )

        if target is None:
            raise SecretNotFoundError("Version not found.")

        if target.metadata.state == SecretState.ACTIVE:
            raise SecretStateError(
                "Cannot revoke the active version."
            )

        if target.metadata.state == SecretState.REVOKED:
            raise SecretStateError("Version is already revoked.")

        target.value = ""
        target.metadata = SecretMetadata(
            name=name,
            version=version_number,
            state=SecretState.REVOKED,
            created_at=target.metadata.created_at,
        )

        self._record(
            actor,
            "revoke",
            name,
            version_number,
            "success",
        )

    def get_metadata(self, name: str) -> list[SecretMetadata]:
        self._policy.authorize("auditor", "metadata")

        versions = self._versions.get(name)
        if not versions:
            raise SecretNotFoundError(name)

        return [item.metadata for item in versions]

    def audit_log(self) -> tuple[AuditEvent, ...]:
        return tuple(self._audit)


# ============================================================
# 5. Environment-variable configuration
# ============================================================

def load_environment_configuration(
    required_names: tuple[str, ...],
) -> dict[str, str]:

    configuration = {}

    for name in required_names:
        value = os.environ.get(name)

        if value is None or not value.strip():
            raise SecretValidationError(
                f"Required environment variable is missing: {name}"
            )

        configuration[name] = value

    return configuration


def validate_environment() -> None:
    """
    Check configuration without printing environment values.
    """
    forbidden_names = {
        "PASSWORD",
        "API_SECRET",
        "PRIVATE_KEY",
    }

    for name in forbidden_names:
        if name in os.environ and not os.environ[name].strip():
            raise SecretValidationError(
                f"Empty sensitive environment variable: {name}"
            )


# ============================================================
# 6. Rotation workflow
# ============================================================

def demonstrate_rotation() -> None:
    manager = InMemorySecretManager()

    initial_secret = generate_secret()
    metadata = manager.create_secret(
        name="payment-api",
        value=initial_secret,
        actor="security-admin",
        expires_in_days=90,
    )

    print("Created secret version:", metadata.version)

    # Application receives the secret only after authorization.
    retrieved = manager.get_secret(
        "payment-api",
        actor="application",
    )

    assert hmac.compare_digest(retrieved, initial_secret)

    new_secret = generate_secret()

    staged = manager.stage_rotation(
        "payment-api",
        new_secret,
        actor="rotation-service",
    )

    print("Staged version:", staged.version)

    # Integration tests should verify the new credential with
    # the downstream service before activation.
    activated = manager.activate_rotation(
        "payment-api",
        actor="security-admin",
    )

    print("Activated version:", activated.version)

    assert manager.get_secret(
        "payment-api",
        actor="application",
    ) == new_secret

    # Old credentials remain retired during the rollback window.
    manager.revoke_version(
        "payment-api",
        version_number=1,
        actor="security-admin",
    )

    print("Old version revoked.")

    for item in manager.get_metadata("payment-api"):
        print(
            f"Version {item.version}: {item.state.value}"
        )

    print("Audit events:", len(manager.audit_log()))


# ============================================================
# 7. Automated validation
# ============================================================

class SecretManagementTests(unittest.TestCase):

    def setUp(self):
        self.manager = InMemorySecretManager()
        self.manager.create_secret(
            "database-password",
            generate_secret(),
            "security-admin",
        )

    def test_create_and_read(self):
        value = self.manager.get_secret(
            "database-password",
            "application",
        )
        self.assertGreaterEqual(len(value), 16)

    def test_access_denied(self):
        with self.assertRaises(SecretAccessError):
            self.manager.get_secret(
                "database-password",
                "auditor",
            )

    def test_rotation(self):
        self.manager.stage_rotation(
            "database-password",
            generate_secret(),
            "rotation-service",
        )

        self.manager.activate_rotation(
            "database-password",
            "security-admin",
        )

        metadata = self.manager.get_metadata(
            "database-password"
        )

        self.assertEqual(
            metadata[-1].state,
            SecretState.ACTIVE,
        )

    def test_duplicate_creation(self):
        with self.assertRaises(SecretStateError):
            self.manager.create_secret(
                "database-password",
                generate_secret(),
                "security-admin",
            )

    def test_identical_rotation_rejected(self):
        current = self.manager.get_secret(
            "database-password",
            "security-admin",
        )

        with self.assertRaises(SecretValidationError):
            self.manager.stage_rotation(
                "database-password",
                current,
                "rotation-service",
            )

    def test_active_version_cannot_be_revoked(self):
        with self.assertRaises(SecretStateError):
            self.manager.revoke_version(
                "database-password",
                1,
                "security-admin",
            )

    def test_invalid_secret(self):
        with self.assertRaises(SecretValidationError):
            self.manager.create_secret(
                "weak-secret",
                "short",
                "security-admin",
            )


# ============================================================
# 8. Execution
# ============================================================

def main() -> None:
    print("SECURE SECRETS MANAGEMENT")
    print("=" * 45)

    validate_environment()
    demonstrate_rotation()

    print("\nRUNNING SECURITY TESTS")
    print("=" * 45)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        SecretManagementTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
