from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set, List, Optional, Iterable
import logging
import secrets
import hashlib


class RoleName(str, Enum):
    USER = "user"
    SUPPORT = "support"
    MANAGER = "manager"
    ADMIN = "admin"


class Action(str, Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    ADMIN = "admin"


class AccessDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class Permission:
    resource: str
    action: Action

    def key(self) -> str:
        return f"{self.resource}:{self.action.value}"


@dataclass
class Role:
    name: RoleName
    permissions: Set[Permission] = field(default_factory=set)

    def grant(self, permission: Permission) -> None:
        self.permissions.add(permission)

    def revoke(self, permission: Permission) -> None:
        self.permissions.discard(permission)


@dataclass
class User:
    user_id: str
    username: str
    password_hash: str
    roles: Set[RoleName] = field(default_factory=set)
    active: bool = True


@dataclass(frozen=True)
class Resource:
    resource_id: str
    resource_type: str
    owner_id: str
    sensitivity: str = "normal"


@dataclass(frozen=True)
class AuthorizationRequest:
    user_id: str
    action: Action
    resource: Resource


@dataclass(frozen=True)
class AuthorizationResult:
    decision: AccessDecision
    reason: str
    matched_permissions: tuple[str, ...] = ()


class RBACError(Exception):
    """Base exception for RBAC domain failures."""


class ValidationError(RBACError):
    pass


class AuthenticationError(RBACError):
    pass


class AuthorizationError(RBACError):
    pass


class RBACSystem:
    """
    In-memory RBAC engine.

    The engine separates:
    - authentication: identifying an active user
    - role assignment: mapping users to roles
    - permissions: mapping roles to resource/action pairs
    - authorization: evaluating a request
    - ownership policy: allowing users to manage resources they own
    """

    def __init__(self) -> None:
        self.roles: Dict[RoleName, Role] = {}
        self.users: Dict[str, User] = {}
        self.audit_log: List[dict] = []
        self.logger = logging.getLogger("rbac")

    def add_role(self, role: Role) -> None:
        if role.name in self.roles:
            raise ValidationError(f"Role already exists: {role.name.value}")
        self.roles[role.name] = role

    def add_user(self, user: User) -> None:
        if user.user_id in self.users:
            raise ValidationError(f"User already exists: {user.user_id}")
        if not user.username.strip():
            raise ValidationError("Username cannot be empty")
        unknown_roles = user.roles - set(self.roles)
        if unknown_roles:
            names = ", ".join(role.value for role in unknown_roles)
            raise ValidationError(f"Unknown roles: {names}")
        self.users[user.user_id] = user

    def assign_role(self, user_id: str, role_name: RoleName) -> None:
        user = self._get_user(user_id)
        if role_name not in self.roles:
            raise ValidationError(f"Unknown role: {role_name.value}")
        user.roles.add(role_name)
        self._audit(
            "role_assignment",
            user_id,
            f"assigned:{role_name.value}",
        )

    def revoke_role(self, user_id: str, role_name: RoleName) -> None:
        user = self._get_user(user_id)
        user.roles.discard(role_name)
        self._audit(
            "role_revocation",
            user_id,
            f"revoked:{role_name.value}",
        )

    def authenticate(self, username: str, password: str) -> User:
        for user in self.users.values():
            if user.username == username:
                if not user.active:
                    raise AuthenticationError("Account is inactive")
                if not self._verify_password(password, user.password_hash):
                    raise AuthenticationError("Invalid credentials")
                self._audit("authentication", user.user_id, "success")
                return user

        raise AuthenticationError("Invalid credentials")

    def authorize(
        self,
        request: AuthorizationRequest,
        *,
        raise_on_deny: bool = False,
    ) -> AuthorizationResult:
        user = self._get_user(request.user_id)

        if not user.active:
            result = AuthorizationResult(
                AccessDecision.DENY,
                "User account is inactive",
            )
            return self._finish_authorization(request, result, raise_on_deny)

        if not request.resource.resource_id.strip():
            raise ValidationError("Resource ID cannot be empty")

        if (
            request.action == Action.ADMIN
            and RoleName.ADMIN not in user.roles
        ):
            result = AuthorizationResult(
                AccessDecision.DENY,
                "Administrative action requires the admin role",
            )
            return self._finish_authorization(request, result, raise_on_deny)

        matched: List[str] = []

        for role_name in user.roles:
            role = self.roles.get(role_name)
            if role is None:
                continue

            permission = Permission(
                request.resource.resource_type,
                request.action,
            )

            if permission in role.permissions:
                matched.append(f"{role_name.value}:{permission.key()}")

        if matched:
            result = AuthorizationResult(
                AccessDecision.ALLOW,
                "Explicit role permission matched",
                tuple(sorted(matched)),
            )
            return self._finish_authorization(request, result, raise_on_deny)

        # Ownership is a separate policy from RBAC permissions.
        # It permits ordinary users to update their own resources only
        # when the resource type explicitly supports that behavior.
        if (
            request.resource.owner_id == user.user_id
            and request.action in {Action.READ, Action.UPDATE}
            and request.resource.resource_type in {"profile", "document"}
        ):
            result = AuthorizationResult(
                AccessDecision.ALLOW,
                "Ownership policy matched",
                ("ownership-policy",),
            )
            return self._finish_authorization(request, result, raise_on_deny)

        result = AuthorizationResult(
            AccessDecision.DENY,
            "No applicable role permission or ownership policy",
        )
        return self._finish_authorization(request, result, raise_on_deny)

    def effective_permissions(self, user_id: str) -> Set[Permission]:
        user = self._get_user(user_id)
        permissions: Set[Permission] = set()

        for role_name in user.roles:
            role = self.roles.get(role_name)
            if role:
                permissions.update(role.permissions)

        return permissions

    def _finish_authorization(
        self,
        request: AuthorizationRequest,
        result: AuthorizationResult,
        raise_on_deny: bool,
    ) -> AuthorizationResult:
        self._audit(
            "authorization",
            request.user_id,
            f"{request.action.value}:{request.resource.resource_type}"
            f":{result.decision.value}:{result.reason}",
        )

        if raise_on_deny and result.decision == AccessDecision.DENY:
            raise AuthorizationError(result.reason)

        return result

    def _get_user(self, user_id: str) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise ValidationError(f"Unknown user: {user_id}")
        return user

    def _audit(self, event: str, user_id: str, detail: str) -> None:
        self.audit_log.append(
            {
                "event": event,
                "user_id": user_id,
                "detail": detail,
            }
        )

    @staticmethod
    def hash_password(password: str) -> str:
        if len(password) < 12:
            raise ValidationError("Password must contain at least 12 characters")

        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200_000,
        )
        return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, stored: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = stored.split("$")
            if algorithm != "pbkdf2_sha256":
                return False

            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )

            return secrets.compare_digest(candidate.hex(), digest_hex)
        except (ValueError, TypeError):
            return False


def build_demo_system() -> RBACSystem:
    system = RBACSystem()

    permissions = {
        RoleName.USER: [
            Permission("profile", Action.READ),
            Permission("profile", Action.UPDATE),
        ],
        RoleName.SUPPORT: [
            Permission("profile", Action.READ),
            Permission("ticket", Action.READ),
            Permission("ticket", Action.UPDATE),
        ],
        RoleName.MANAGER: [
            Permission("profile", Action.READ),
            Permission("ticket", Action.READ),
            Permission("ticket", Action.UPDATE),
            Permission("ticket", Action.APPROVE),
            Permission("report", Action.READ),
        ],
        RoleName.ADMIN: [
            Permission("profile", Action.READ),
            Permission("profile", Action.UPDATE),
            Permission("ticket", Action.READ),
            Permission("ticket", Action.UPDATE),
            Permission("ticket", Action.APPROVE),
            Permission("report", Action.READ),
            Permission("system", Action.ADMIN),
        ],
    }

    for role_name, role_permissions in permissions.items():
        role = Role(role_name)
        for permission in role_permissions:
            role.grant(permission)
        system.add_role(role)

    passwords = {
        "u1": "UserPassword!2026",
        "u2": "SupportPassword!2026",
        "u3": "ManagerPassword!2026",
        "u4": "AdminPassword!2026",
    }

    users = [
        User(
            "u1",
            "alice",
            system.hash_password(passwords["u1"]),
            {RoleName.USER},
        ),
        User(
            "u2",
            "bob",
            system.hash_password(passwords["u2"]),
            {RoleName.SUPPORT},
        ),
        User(
            "u3",
            "carol",
            system.hash_password(passwords["u3"]),
            {RoleName.MANAGER},
        ),
        User(
            "u4",
            "david",
            system.hash_password(passwords["u4"]),
            {RoleName.ADMIN},
        ),
    ]

    for user in users:
        system.add_user(user)

    return system


def run_examples(system: RBACSystem) -> None:
    resources = {
        "alice_profile": Resource("p-100", "profile", "u1"),
        "bob_ticket": Resource("t-200", "ticket", "u2"),
        "financial_report": Resource("r-300", "report", "u3", "high"),
        "system_config": Resource("s-400", "system", "u4", "critical"),
    }

    checks = [
        AuthorizationRequest("u1", Action.UPDATE, resources["alice_profile"]),
        AuthorizationRequest("u1", Action.UPDATE, resources["bob_ticket"]),
        AuthorizationRequest("u2", Action.UPDATE, resources["bob_ticket"]),
        AuthorizationRequest("u3", Action.APPROVE, resources["bob_ticket"]),
        AuthorizationRequest("u3", Action.READ, resources["financial_report"]),
        AuthorizationRequest("u2", Action.ADMIN, resources["system_config"]),
        AuthorizationRequest("u4", Action.ADMIN, resources["system_config"]),
    ]

    for request in checks:
        result = system.authorize(request)
        print(
            f"{request.user_id:>2} "
            f"{request.action.value:>8} "
            f"{request.resource.resource_type:>8} -> "
            f"{result.decision.value.upper():<5} | {result.reason}"
        )

    print("\nAuthentication:")
    authenticated = system.authenticate("alice", "UserPassword!2026")
    print(f"Authenticated: {authenticated.username}")

    try:
        system.authenticate("alice", "incorrect-password")
    except AuthenticationError as exc:
        print(f"Rejected login: {exc}")

    print("\nEffective permissions for carol:")
    for permission in sorted(
        system.effective_permissions("u3"),
        key=lambda item: item.key(),
    ):
        print(f"  {permission.key()}")

    print("\nAudit events:")
    for event in system.audit_log:
        print(f"  {event}")


def run_self_tests(system: RBACSystem) -> None:
    profile = Resource("p-test", "profile", "u1")
    ticket = Resource("t-test", "ticket", "u2")
    system_config = Resource("s-test", "system", "u4")

    assert system.authorize(
        AuthorizationRequest("u1", Action.UPDATE, profile)
    ).decision == AccessDecision.ALLOW

    assert system.authorize(
        AuthorizationRequest("u1", Action.UPDATE, ticket)
    ).decision == AccessDecision.DENY

    assert system.authorize(
        AuthorizationRequest("u2", Action.UPDATE, ticket)
    ).decision == AccessDecision.ALLOW

    assert system.authorize(
        AuthorizationRequest("u2", Action.ADMIN, system_config)
    ).decision == AccessDecision.DENY

    assert system.authorize(
        AuthorizationRequest("u4", Action.ADMIN, system_config)
    ).decision == AccessDecision.ALLOW

    system.users["u1"].active = False
    assert system.authorize(
        AuthorizationRequest("u1", Action.READ, profile)
    ).decision == AccessDecision.DENY
    system.users["u1"].active = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rbac = build_demo_system()
    run_self_tests(rbac)
    run_examples(rbac)
