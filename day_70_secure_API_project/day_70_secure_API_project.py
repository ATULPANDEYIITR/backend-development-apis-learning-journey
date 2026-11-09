#!/usr/bin/env python3
"""
Secure API Project
Authentication, authorization, access control, token management,
rate limiting, input validation, audit logging, and security testing.

Python 3.10+
Standard-library only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

APP_NAME = "SecureAPI"
TOKEN_LIFETIME = 900
PASSWORD_ITERATIONS = 310_000
MAX_REQUEST_BODY = 16_384
AUDIT_FILE = Path("secure_api_audit.jsonl")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger(APP_NAME)


# ---------------------------------------------------------
# Domain Types
# ---------------------------------------------------------

class Role(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class SecurityError(Exception):
    pass


class AuthenticationError(SecurityError):
    pass


class AuthorizationError(SecurityError):
    pass


class ValidationError(SecurityError):
    pass


class RateLimitError(SecurityError):
    pass


@dataclass(frozen=True)
class User:
    user_id: str
    username: str
    password_hash: str
    salt: str
    roles: frozenset[Role]
    active: bool = True


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_at: int
    user_id: str


@dataclass
class APIRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: dict[str, Any] = field(default_factory=dict)
    client_ip: str = "127.0.0.1"


@dataclass
class APIResponse:
    status: int
    body: dict[str, Any]


@dataclass(frozen=True)
class AuditEvent:
    timestamp: float
    event_type: str
    user_id: str
    resource: str
    result: str
    details: str


# ---------------------------------------------------------
# Password Security
# ---------------------------------------------------------

class PasswordManager:
    """PBKDF2 password hashing with independent random salts."""

    @staticmethod
    def validate_password(password: str) -> None:
        if not isinstance(password, str) or len(password) < 12:
            raise ValidationError(
                "Password must contain at least 12 characters."
            )

        if len(password) > 256:
            raise ValidationError("Password exceeds maximum length.")

        if not any(c.isupper() for c in password):
            raise ValidationError("Password requires an uppercase character.")

        if not any(c.islower() for c in password):
            raise ValidationError("Password requires a lowercase character.")

        if not any(c.isdigit() for c in password):
            raise ValidationError("Password requires a digit.")

        if not any(not c.isalnum() for c in password):
            raise ValidationError("Password requires a special character.")

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        PasswordManager.validate_password(password)

        salt = salt or secrets.token_hex(16)

        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            PASSWORD_ITERATIONS
        )

        return derived.hex(), salt

    @staticmethod
    def verify_password(password: str, user: User) -> bool:
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(user.salt),
            PASSWORD_ITERATIONS
        )

        return hmac.compare_digest(
            derived.hex(),
            user.password_hash
        )


# ---------------------------------------------------------
# User Repository
# ---------------------------------------------------------

class UserRepository:
    def __init__(self):
        self.users: dict[str, User] = {}
        self.username_index: dict[str, str] = {}

    def create_user(
        self,
        username: str,
        password: str,
        roles: set[Role]
    ) -> User:

        if not username or len(username) > 64:
            raise ValidationError("Invalid username.")

        if not username.replace("_", "").isalnum():
            raise ValidationError("Username contains invalid characters.")

        normalized = username.lower()

        if normalized in self.username_index:
            raise ValidationError("Username already exists.")

        if not roles:
            raise ValidationError("At least one role is required.")

        password_hash, salt = PasswordManager.hash_password(password)

        user = User(
            user_id=secrets.token_hex(12),
            username=username,
            password_hash=password_hash,
            salt=salt,
            roles=frozenset(roles)
        )

        self.users[user.user_id] = user
        self.username_index[normalized] = user.user_id

        return user

    def find_by_username(self, username: str) -> User | None:
        user_id = self.username_index.get(username.lower())
        return self.users.get(user_id) if user_id else None

    def find_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def deactivate(self, user_id: str) -> None:
        user = self.users.get(user_id)

        if user:
            self.users[user_id] = User(
                user_id=user.user_id,
                username=user.username,
                password_hash=user.password_hash,
                salt=user.salt,
                roles=user.roles,
                active=False
            )


# ---------------------------------------------------------
# Token Management
# ---------------------------------------------------------

class TokenManager:
    """
    HMAC-signed bearer tokens.

    This is a compact educational token format. Production systems
    should generally use a maintained OAuth 2.0/OIDC implementation.
    """

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("Signing secret must contain at least 32 bytes.")

        self.secret = secret
        self.revoked_tokens: set[str] = set()

    def _sign(self, payload: bytes) -> str:
        return hmac.new(
            self.secret,
            payload,
            hashlib.sha256
        ).hexdigest()

    def issue(self, user: User) -> AccessToken:
        now = int(time.time())

        payload = {
            "sub": user.user_id,
            "iat": now,
            "exp": now + TOKEN_LIFETIME,
            "jti": secrets.token_hex(16),
            "roles": sorted(role.value for role in user.roles)
        }

        encoded = secrets.base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode().rstrip("=")

        signature = self._sign(encoded.encode())

        token = f"{encoded}.{signature}"

        return AccessToken(
            token=token,
            expires_at=payload["exp"],
            user_id=user.user_id
        )

    def verify(self, token: str) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 4096:
            raise AuthenticationError("Invalid bearer token.")

        if token in self.revoked_tokens:
            raise AuthenticationError("Token has been revoked.")

        try:
            encoded, supplied_signature = token.split(".", 1)

            expected_signature = self._sign(encoded.encode())

            if not hmac.compare_digest(
                supplied_signature,
                expected_signature
            ):
                raise AuthenticationError("Invalid token signature.")

            padded = encoded + "=" * (-len(encoded) % 4)

            payload = json.loads(
                secrets.base64.urlsafe_b64decode(padded).decode()
            )

            if not isinstance(payload, dict):
                raise AuthenticationError("Invalid token payload.")

            required = {"sub", "iat", "exp", "jti", "roles"}

            if not required.issubset(payload):
                raise AuthenticationError("Incomplete token payload.")

            if type(payload["iat"]) is not int:
                raise AuthenticationError("Invalid token issue time.")

            if type(payload["exp"]) is not int:
                raise AuthenticationError("Invalid token expiration.")

            if payload["iat"] > int(time.time()) + 30:
                raise AuthenticationError("Invalid token issue time.")

            if payload["exp"] <= int(time.time()):
                raise AuthenticationError("Token expired.")

            if payload["exp"] - payload["iat"] > TOKEN_LIFETIME:
                raise AuthenticationError("Invalid token lifetime.")

            if not isinstance(payload["roles"], list):
                raise AuthenticationError("Invalid token roles.")

            return payload

        except AuthenticationError:
            raise
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise AuthenticationError("Malformed bearer token.") from None

    def revoke(self, token: str) -> None:
        self.revoked_tokens.add(token)


# ---------------------------------------------------------
# Authentication Service
# ---------------------------------------------------------

class AuthenticationService:
    def __init__(
        self,
        users: UserRepository,
        tokens: TokenManager
    ):
        self.users = users
        self.tokens = tokens
        self.failed_attempts: dict[str, deque[float]] = defaultdict(deque)

    def login(self, username: str, password: str) -> AccessToken:
        key = username.lower()[:64]
        now = time.time()

        attempts = self.failed_attempts[key]

        while attempts and now - attempts[0] > 300:
            attempts.popleft()

        if len(attempts) >= 5:
            raise AuthenticationError("Too many login attempts.")

        user = self.users.find_by_username(username)

        if (
            user is None
            or not user.active
            or not PasswordManager.verify_password(password, user)
        ):
            attempts.append(now)
            raise AuthenticationError("Invalid username or password.")

        self.failed_attempts.pop(key, None)

        return self.tokens.issue(user)

    def authenticate(self, authorization: str) -> User:
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("Bearer token required.")

        token = authorization[7:]

        payload = self.tokens.verify(token)

        user = self.users.find_by_id(payload["sub"])

        if user is None or not user.active:
            raise AuthenticationError("Account unavailable.")

        return user

    def logout(self, authorization: str) -> None:
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("Bearer token required.")

        token = authorization[7:]

        self.tokens.verify(token)
        self.tokens.revoke(token)


# ---------------------------------------------------------
# Role-Based Access Control
# ---------------------------------------------------------

class AuthorizationService:
    """
    RBAC maps roles to permissions.

    Access is denied by default when no role grants the permission.
    """

    ROLE_PERMISSIONS = {
        Role.ADMIN: {
            "users:read",
            "users:create",
            "users:update",
            "users:delete",
            "reports:read",
            "system:manage"
        },
        Role.EDITOR: {
            "users:read",
            "users:update",
            "reports:read"
        },
        Role.VIEWER: {
            "users:read",
            "reports:read"
        }
    }

    @classmethod
    def has_permission(
        cls,
        user: User,
        permission: str
    ) -> bool:

        if not user.active:
            return False

        granted = set()

        for role in user.roles:
            granted.update(cls.ROLE_PERMISSIONS.get(role, set()))

        return permission in granted

    @classmethod
    def require_permission(
        cls,
        user: User,
        permission: str
    ) -> None:

        if not cls.has_permission(user, permission):
            raise AuthorizationError(
                f"Permission denied: {permission}"
            )


# ---------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------

class RateLimiter:
    """In-memory sliding-window rate limiter."""

    def __init__(self, limit: int = 20, window: int = 60):
        self.limit = limit
        self.window = window
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_id: str) -> None:
        now = time.monotonic()

        timestamps = self.requests[client_id]

        while timestamps and now - timestamps[0] >= self.window:
            timestamps.popleft()

        if len(timestamps) >= self.limit:
            raise RateLimitError("Request rate limit exceeded.")

        timestamps.append(now)


# ---------------------------------------------------------
# Input Validation
# ---------------------------------------------------------

class InputValidator:
    @staticmethod
    def validate_user_payload(payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be an object.")

        if len(payload) > 3:
            raise ValidationError("Unexpected request fields.")

        allowed = {"username", "password", "email"}

        if set(payload) - allowed:
            raise ValidationError("Unknown request fields.")

        username = payload.get("username")
        email = payload.get("email")
        password = payload.get("password")

        if not isinstance(username, str) or not 3 <= len(username) <= 64:
            raise ValidationError("Invalid username.")

        if not username.replace("_", "").isalnum():
            raise ValidationError("Invalid username characters.")

        if not isinstance(email, str) or len(email) > 254:
            raise ValidationError("Invalid email.")

        if email.count("@") != 1 or "." not in email.split("@")[1]:
            raise ValidationError("Invalid email format.")

        if not isinstance(password, str):
            raise ValidationError("Password must be a string.")

        PasswordManager.validate_password(password)

    @staticmethod
    def validate_request_size(body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")

        if len(encoded) > MAX_REQUEST_BODY:
            raise ValidationError("Request body too large.")


# ---------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------

class AuditLogger:
    def __init__(self, path: Path):
        self.path = path

    def record(self, event: AuditEvent) -> None:
        # Restrict permissions where supported by the operating system.
        fd = None

        try:
            import os

            fd = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600
            )

            with os.fdopen(fd, "a", encoding="utf-8") as file:
                fd = None
                file.write(json.dumps(asdict(event)) + "\n")

        except OSError:
            logger.exception("Audit persistence failed.")
            raise

        finally:
            if fd is not None:
                import os
                os.close(fd)


# ---------------------------------------------------------
# API Application
# ---------------------------------------------------------

class SecureAPI:
    def __init__(self, signing_secret: bytes):
        self.users = UserRepository()
        self.tokens = TokenManager(signing_secret)

        self.authentication = AuthenticationService(
            self.users,
            self.tokens
        )

        self.authorization = AuthorizationService()
        self.rate_limiter = RateLimiter()
        self.audit = AuditLogger(AUDIT_FILE)

        self.resources: dict[str, dict[str, Any]] = {}

    def _audit(
        self,
        event_type: str,
        user_id: str,
        resource: str,
        result: str,
        details: str
    ) -> None:

        self.audit.record(
            AuditEvent(
                timestamp=time.time(),
                event_type=event_type,
                user_id=user_id,
                resource=resource,
                result=result,
                details=details[:256]
            )
        )

    def register(self, username: str, password: str) -> User:
        return self.users.create_user(
            username,
            password,
            {Role.VIEWER}
        )

    def create_resource(
        self,
        user: User,
        resource_id: str,
        content: str
    ) -> dict[str, Any]:

        self.authorization.require_permission(
            user,
            "system:manage"
        )

        if not resource_id or len(resource_id) > 64:
            raise ValidationError("Invalid resource identifier.")

        if not isinstance(content, str) or len(content) > 5000:
            raise ValidationError("Invalid resource content.")

        if resource_id in self.resources:
            raise ValidationError("Resource already exists.")

        resource = {
            "resource_id": resource_id,
            "content": content,
            "owner_id": user.user_id
        }

        self.resources[resource_id] = resource

        self._audit(
            "RESOURCE_CREATED",
            user.user_id,
            resource_id,
            "SUCCESS",
            "Resource created."
        )

        return resource

    def handle(self, request: APIRequest) -> APIResponse:
        user_id = "anonymous"

        try:
            method = HTTPMethod(request.method.upper())

            self.rate_limiter.check(request.client_ip)

            InputValidator.validate_request_size(request.body)

            if request.path == "/health" and method == HTTPMethod.GET:
                return APIResponse(
                    200,
                    {"status": "healthy", "service": APP_NAME}
                )

            user = self.authentication.authenticate(
                request.headers.get("Authorization", "")
            )

            user_id = user.user_id

            if request.path == "/api/users" and method == HTTPMethod.GET:
                self.authorization.require_permission(
                    user,
                    "users:read"
                )

                result = [
                    {
                        "user_id": item.user_id,
                        "username": item.username,
                        "roles": sorted(
                            role.value for role in item.roles
                        )
                    }
                    for item in self.users.users.values()
                    if item.active
                ]

                self._audit(
                    "USER_LIST",
                    user_id,
                    "/api/users",
                    "SUCCESS",
                    "User list accessed."
                )

                return APIResponse(200, {"users": result})

            if request.path == "/api/admin" and method == HTTPMethod.GET:
                self.authorization.require_permission(
                    user,
                    "system:manage"
                )

                return APIResponse(
                    200,
                    {"message": "Administrative access granted."}
                )

            self._audit(
                "API_ACCESS",
                user_id,
                request.path,
                "DENIED",
                "Route not found or method unsupported."
            )

            return APIResponse(404, {"error": "Resource not found."})

        except AuthenticationError as exc:
            status = 401
            message = str(exc)

        except AuthorizationError:
            status = 403
            message = "Insufficient permissions."

        except RateLimitError:
            status = 429
            message = "Too many requests."

        except ValidationError as exc:
            status = 400
            message = str(exc)

        except ValueError:
            status = 405
            message = "HTTP method not supported."

        except Exception:
            logger.exception("Unexpected API failure.")
            status = 500
            message = "Internal server error."

        self._audit(
            "API_ACCESS",
            user_id,
            request.path[:256],
            "FAILURE",
            message
        )

        return APIResponse(status, {"error": message})


# ---------------------------------------------------------
# Demonstration and Security Tests
# ---------------------------------------------------------

def main() -> None:
    api = SecureAPI(secrets.token_bytes(32))

    admin = api.users.create_user(
        "administrator",
        "AdminSecure#2026",
        {Role.ADMIN}
    )

    viewer = api.users.create_user(
        "analyst",
        "AnalystSecure#2026",
        {Role.VIEWER}
    )

    admin_token = api.authentication.login(
        "administrator",
        "AdminSecure#2026"
    )

    viewer_token = api.authentication.login(
        "analyst",
        "AnalystSecure#2026"
    )

    admin_headers = {
        "Authorization": f"Bearer {admin_token.token}"
    }

    viewer_headers = {
        "Authorization": f"Bearer {viewer_token.token}"
    }

    print("\nSECURE API DEMONSTRATION")

    health = api.handle(
        APIRequest(
            method="GET",
            path="/health",
            headers={}
        )
    )

    print("Health:", health.status, health.body)

    authorized = api.handle(
        APIRequest(
            method="GET",
            path="/api/admin",
            headers=admin_headers
        )
    )

    print("Admin access:", authorized.status, authorized.body)

    forbidden = api.handle(
        APIRequest(
            method="GET",
            path="/api/admin",
            headers=viewer_headers
        )
    )

    print("Viewer admin access:", forbidden.status, forbidden.body)

    listing = api.handle(
        APIRequest(
            method="GET",
            path="/api/users",
            headers=admin_headers
        )
    )

    print("User listing:", listing.status)

    assert health.status == 200
    assert authorized.status == 200
    assert forbidden.status == 403
    assert listing.status == 200

    # Invalid credentials must not authenticate.
    try:
        api.authentication.login(
            "administrator",
            "IncorrectPassword#2026"
        )
        raise AssertionError("Invalid password was accepted.")
    except AuthenticationError:
        print("Invalid password correctly rejected.")

    # Revoked tokens cannot be reused.
    api.authentication.logout(viewer_headers["Authorization"])

    revoked = api.handle(
        APIRequest(
            method="GET",
            path="/api/users",
            headers=viewer_headers
        )
    )

    assert revoked.status == 401
    print("Revoked token correctly rejected.")

    # Inactive accounts cannot continue accessing protected routes.
    api.users.deactivate(admin.user_id)

    inactive = api.handle(
        APIRequest(
            method="GET",
            path="/api/admin",
            headers=admin_headers
        )
    )

    assert inactive.status == 401
    print("Inactive account correctly rejected.")

    print("\nAll security assertions passed.")


if __name__ == "__main__":
    main()
