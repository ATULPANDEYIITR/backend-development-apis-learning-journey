from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class TokenValidationError(AuthenticationError):
    """Raised when a JWT is malformed, invalid, or expired."""


class AuthorizationError(AuthenticationError):
    """Raised when an authenticated identity lacks permission."""


class TokenType(Enum):
    ACCESS = "access"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise TokenValidationError("Invalid Base64URL encoding") from exc


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class JWTManager:
    """
    Small HS256 JWT implementation using only the Python standard library.

    Production systems should normally use a maintained JWT library and
    asymmetric signing such as RS256 or ES256 when multiple services verify
    tokens without sharing the signing secret.
    """

    def __init__(
        self,
        secret: bytes,
        issuer: str,
        audience: str,
        access_ttl_seconds: int = 900,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("Signing secret must contain at least 32 bytes")
        if access_ttl_seconds <= 0:
            raise ValueError("Token lifetime must be positive")

        self.secret = secret
        self.issuer = issuer
        self.audience = audience
        self.access_ttl_seconds = access_ttl_seconds

    def issue_access_token(
        self,
        subject: str,
        roles: list[str],
        scopes: list[str],
    ) -> str:
        if not subject.strip():
            raise ValueError("Subject cannot be empty")
        if not roles:
            raise ValueError("At least one role is required")

        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": subject,
            "aud": self.audience,
            "iat": now,
            "nbf": now,
            "exp": now + self.access_ttl_seconds,
            "jti": secrets.token_urlsafe(18),
            "typ": TokenType.ACCESS.value,
            "roles": sorted(set(roles)),
            "scope": " ".join(sorted(set(scopes))),
        }

        header = {
            "alg": "HS256",
            "typ": "JWT",
        }

        encoded_header = _b64url_encode(_canonical_json(header))
        encoded_payload = _b64url_encode(_canonical_json(payload))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")

        signature = hmac.new(
            self.secret,
            signing_input,
            hashlib.sha256,
        ).digest()

        return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"

    def validate_access_token(
        self,
        token: str,
        required_scope: str | None = None,
    ) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenValidationError("JWT must contain three segments")

        encoded_header, encoded_payload, encoded_signature = parts

        try:
            header = json.loads(_b64url_decode(encoded_header))
            payload = json.loads(_b64url_decode(encoded_payload))
            signature = _b64url_decode(encoded_signature)
        except json.JSONDecodeError as exc:
            raise TokenValidationError("JWT contains invalid JSON") from exc

        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise TokenValidationError("Unsupported JWT header")

        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected_signature = hmac.new(
            self.secret,
            signing_input,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(signature, expected_signature):
            raise TokenValidationError("Invalid token signature")

        now = int(time.time())

        required_claims = ("iss", "sub", "aud", "iat", "nbf", "exp", "jti", "typ")
        missing = [claim for claim in required_claims if claim not in payload]
        if missing:
            raise TokenValidationError(f"Missing claims: {missing}")

        if payload["iss"] != self.issuer:
            raise TokenValidationError("Invalid issuer")

        audience = payload["aud"]
        if audience != self.audience:
            raise TokenValidationError("Invalid audience")

        if payload["typ"] != TokenType.ACCESS.value:
            raise TokenValidationError("Token is not an access token")

        try:
            issued_at = int(payload["iat"])
            not_before = int(payload["nbf"])
            expires_at = int(payload["exp"])
        except (TypeError, ValueError) as exc:
            raise TokenValidationError("Invalid numeric time claim") from exc

        if issued_at > now + 30:
            raise TokenValidationError("Token issued in the future")

        if not_before > now:
            raise TokenValidationError("Token is not active yet")

        if expires_at <= now:
            raise TokenValidationError("Token has expired")

        if expires_at <= issued_at:
            raise TokenValidationError("Invalid token lifetime")

        roles = payload.get("roles")
        scope_string = payload.get("scope", "")

        if not isinstance(roles, list) or not all(
            isinstance(role, str) and role for role in roles
        ):
            raise TokenValidationError("Invalid roles claim")

        if not isinstance(scope_string, str):
            raise TokenValidationError("Invalid scope claim")

        scopes = set(scope_string.split()) if scope_string else set()

        if required_scope and required_scope not in scopes:
            raise AuthorizationError(
                f"Required scope '{required_scope}' is missing"
            )

        payload["roles"] = roles
        payload["scopes"] = sorted(scopes)
        return payload


@dataclass(frozen=True)
class User:
    user_id: str
    username: str
    password_hash: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    active: bool = True


class UserStore:
    """In-memory user store for the runnable example."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def add_user(
        self,
        username: str,
        password: str,
        roles: list[str],
        scopes: list[str],
    ) -> User:
        if username in self._users:
            raise ValueError("Username already exists")
        if len(password) < 12:
            raise ValueError("Password must contain at least 12 characters")

        salt = secrets.token_bytes(16)
        password_hash = self._hash_password(password, salt)
        user = User(
            user_id=secrets.token_urlsafe(12),
            username=username,
            password_hash=f"{_b64url_encode(salt)}:{_b64url_encode(password_hash)}",
            roles=tuple(sorted(set(roles))),
            scopes=tuple(sorted(set(scopes))),
        )
        self._users[username] = user
        return user

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            310_000,
        )

    def authenticate(self, username: str, password: str) -> User:
        user = self._users.get(username)
        if user is None or not user.active:
            raise AuthenticationError("Invalid credentials")

        salt_text, digest_text = user.password_hash.split(":", 1)
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(digest_text)
        actual = self._hash_password(password, salt)

        if not hmac.compare_digest(actual, expected):
            raise AuthenticationError("Invalid credentials")

        return user


@dataclass
class Request:
    path: str
    method: str
    headers: dict[str, str]
    body: dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    status: int
    body: dict[str, Any]


class AuthenticationService:
    def __init__(self, users: UserStore, jwt: JWTManager) -> None:
        self.users = users
        self.jwt = jwt

    def login(self, username: str, password: str) -> Response:
        try:
            user = self.users.authenticate(username, password)
            token = self.jwt.issue_access_token(
                user.user_id,
                list(user.roles),
                list(user.scopes),
            )
            return Response(
                200,
                {
                    "access_token": token,
                    "token_type": "Bearer",
                    "expires_in": self.jwt.access_ttl_seconds,
                },
            )
        except AuthenticationError:
            return Response(401, {"error": "invalid_credentials"})

    def protected_route(
        self,
        request: Request,
        required_scope: str,
    ) -> Response:
        authorization = request.headers.get("Authorization", "")

        if not authorization.startswith("Bearer "):
            return Response(
                401,
                {
                    "error": "missing_bearer_token",
                    "message": "Authorization header must use Bearer authentication",
                },
            )

        token = authorization[7:].strip()

        try:
            claims = self.jwt.validate_access_token(
                token,
                required_scope=required_scope,
            )
        except TokenValidationError:
            return Response(401, {"error": "invalid_token"})
        except AuthorizationError:
            return Response(403, {"error": "insufficient_scope"})

        return Response(
            200,
            {
                "message": "Protected resource accessed",
                "subject": claims["sub"],
                "scope": claims["scopes"],
            },
        )


def demonstrate() -> None:
    signing_secret = secrets.token_bytes(32)

    jwt = JWTManager(
        secret=signing_secret,
        issuer="https://auth.example.internal",
        audience="orders-api",
        access_ttl_seconds=900,
    )

    users = UserStore()
    user = users.add_user(
        username="alice",
        password="correct-horse-battery-staple",
        roles=["customer"],
        scopes=["orders:read", "profile:read"],
    )

    auth = AuthenticationService(users, jwt)

    login = auth.login(
        "alice",
        "correct-horse-battery-staple",
    )

    print("Login status:", login.status)
    assert login.status == 200

    token = login.body["access_token"]

    request = Request(
        path="/orders",
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = auth.protected_route(request, "orders:read")
    print("Protected route:", response.status, response.body)
    assert response.status == 200

    denied = auth.protected_route(request, "orders:write")
    print("Insufficient scope:", denied.status, denied.body)
    assert denied.status == 403

    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    tampered_response = auth.protected_route(
        Request(
            path="/orders",
            method="GET",
            headers={"Authorization": f"Bearer {tampered}"},
        ),
        "orders:read",
    )
    print("Tampered token:", tampered_response.status)
    assert tampered_response.status == 401

    malformed = auth.protected_route(
        Request(
            path="/orders",
            method="GET",
            headers={"Authorization": "Basic abc123"},
        ),
        "orders:read",
    )
    print("Wrong authentication scheme:", malformed.status)
    assert malformed.status == 401

    print(
        "Demonstration completed at",
        datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    demonstrate()
