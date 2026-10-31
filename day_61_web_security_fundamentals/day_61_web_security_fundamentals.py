#!/usr/bin/env python3
"""
Web Security Fundamentals
CIA triad, attack surfaces, secure coding, and threat modeling.

The program models a small web application, identifies its attack surface,
evaluates threats using a lightweight STRIDE-style model, validates security
controls, and runs security-focused request simulations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
import hashlib
import hmac
import ipaddress
import re
import secrets
import time
from urllib.parse import urlparse


class SecurityLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ThreatCategory(Enum):
    SPOOFING = "Spoofing"
    TAMPERING = "Tampering"
    REPUDIATION = "Repudiation"
    INFORMATION_DISCLOSURE = "Information Disclosure"
    DENIAL_OF_SERVICE = "Denial of Service"
    ELEVATION_OF_PRIVILEGE = "Elevation of Privilege"


@dataclass(frozen=True)
class SecurityControl:
    name: str
    protects: tuple[str, ...]
    implemented: bool
    description: str


@dataclass(frozen=True)
class Asset:
    name: str
    confidentiality: SecurityLevel
    integrity: SecurityLevel
    availability: SecurityLevel
    owner: str


@dataclass(frozen=True)
class Threat:
    name: str
    category: ThreatCategory
    asset: str
    likelihood: SecurityLevel
    impact: SecurityLevel
    mitigation: str

    @property
    def risk_score(self) -> int:
        return self.likelihood.value * self.impact.value


@dataclass
class WebRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: str = ""
    client_ip: str = "127.0.0.1"


@dataclass
class SecurityResult:
    allowed: bool
    status_code: int
    reason: str
    headers: dict[str, str] = field(default_factory=dict)


class InputValidationError(ValueError):
    """Raised when application input violates security rules."""


class AuthenticationError(Exception):
    """Raised when authentication material is invalid."""


class RateLimitExceeded(Exception):
    """Raised when a client exceeds its request budget."""


class PasswordHasher:
    """
    Uses PBKDF2-HMAC-SHA256 from the Python standard library.

    A production application should use a dedicated password hashing library
    such as Argon2id when available. Plain SHA-256 is intentionally not used
    for password storage because it is too fast for password hashing.
    """

    ITERATIONS = 310_000
    SALT_BYTES = 16

    @classmethod
    def hash_password(cls, password: str) -> str:
        if not 12 <= len(password) <= 128:
            raise InputValidationError("Password must contain 12-128 characters.")

        salt = secrets.token_bytes(cls.SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
        )
        return (
            f"pbkdf2_sha256${cls.ITERATIONS}$"
            f"{salt.hex()}${digest.hex()}"
        )

    @classmethod
    def verify_password(cls, password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = encoded.split("$")
            if algorithm != "pbkdf2_sha256":
                return False

            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(candidate.hex(), digest_hex)
        except (ValueError, TypeError):
            return False


class SessionManager:
    """Creates high-entropy opaque session identifiers."""

    def __init__(self) -> None:
        self.sessions: dict[str, str] = {}

    def create(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = username
        return token

    def authenticate(self, token: str) -> str:
        username = self.sessions.get(token)
        if username is None:
            raise AuthenticationError("Invalid or expired session.")
        return username

    def revoke(self, token: str) -> None:
        self.sessions.pop(token, None)


class RateLimiter:
    """Simple fixed-window limiter suitable for simulation."""

    def __init__(self, limit: int = 5, window_seconds: int = 60) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate-limit values must be positive.")
        self.limit = limit
        self.window_seconds = window_seconds
        self.buckets: dict[str, tuple[int, float]] = {}

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        count, started = self.buckets.get(client_ip, (0, now))

        if now - started >= self.window_seconds:
            count, started = 0, now

        if count >= self.limit:
            raise RateLimitExceeded("Request rate exceeded.")

        self.buckets[client_ip] = (count + 1, started)


class InputValidator:
    USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

    @classmethod
    def username(cls, value: str) -> str:
        if not isinstance(value, str) or not cls.USERNAME.fullmatch(value):
            raise InputValidationError("Invalid username.")
        return value

    @staticmethod
    def email(value: str) -> str:
        if not isinstance(value, str) or len(value) > 254:
            raise InputValidationError("Invalid email.")

        if not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
            value,
        ):
            raise InputValidationError("Invalid email.")

        return value.lower()

    @staticmethod
    def safe_path(path: str) -> str:
        if not path.startswith("/") or "\x00" in path:
            raise InputValidationError("Invalid path.")

        parsed = urlparse(path)
        if parsed.scheme or parsed.netloc:
            raise InputValidationError("Absolute URLs are not accepted.")

        normalized = parsed.path
        if ".." in normalized.split("/"):
            raise InputValidationError("Path traversal is not permitted.")

        return path


class WebSecurityPolicy:
    """Centralizes security headers and browser-facing policy."""

    @staticmethod
    def response_headers() -> dict[str, str]:
        return {
            "Content-Security-Policy": (
                "default-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store",
        }

    @staticmethod
    def secure_cookie(name: str, value: str) -> str:
        return (
            f"{name}={value}; Path=/; HttpOnly; Secure; "
            "SameSite=Lax"
        )


class ThreatModel:
    def __init__(self) -> None:
        self.assets: dict[str, Asset] = {}
        self.threats: list[Threat] = []
        self.controls: list[SecurityControl] = []

    def add_asset(self, asset: Asset) -> None:
        if asset.name in self.assets:
            raise ValueError(f"Duplicate asset: {asset.name}")
        self.assets[asset.name] = asset

    def add_threat(self, threat: Threat) -> None:
        if threat.asset not in self.assets:
            raise ValueError(f"Unknown asset: {threat.asset}")
        self.threats.append(threat)

    def add_control(self, control: SecurityControl) -> None:
        self.controls.append(control)

    def high_risk_threats(self, minimum: int = 6) -> list[Threat]:
        return [t for t in self.threats if t.risk_score >= minimum]

    def coverage(self) -> dict[str, int]:
        return {
            control: sum(
                control in c.protects and c.implemented
                for c in self.controls
            )
            for control in (
                "confidentiality",
                "integrity",
                "availability",
                "authentication",
                "authorization",
            )
        }


class SecureWebApplication:
    """
    Small in-memory web application.

    The implementation intentionally separates:
    - input validation,
    - authentication,
    - authorization,
    - rate limiting,
    - security headers,
    - business operations.
    """

    def __init__(self) -> None:
        self.users: dict[str, str] = {}
        self.roles: dict[str, str] = {}
        self.sessions = SessionManager()
        self.rate_limiter = RateLimiter(limit=5)
        self.audit_log: list[dict[str, str]] = []

    def register(self, username: str, email: str, password: str) -> None:
        username = InputValidator.username(username)
        InputValidator.email(email)

        if username in self.users:
            raise InputValidationError("Username already exists.")

        self.users[username] = PasswordHasher.hash_password(password)
        self.roles[username] = "user"

    def login(
        self,
        username: str,
        password: str,
        client_ip: str = "127.0.0.1",
    ) -> str:
        self.rate_limiter.check(client_ip)

        username = InputValidator.username(username)
        stored = self.users.get(username)

        if stored is None or not PasswordHasher.verify_password(password, stored):
            self.audit_log.append(
                {
                    "event": "authentication_failure",
                    "username": username,
                    "ip": client_ip,
                }
            )
            raise AuthenticationError("Invalid credentials.")

        token = self.sessions.create(username)
        self.audit_log.append(
            {
                "event": "authentication_success",
                "username": username,
                "ip": client_ip,
            }
        )
        return token

    def admin_operation(self, token: str) -> str:
        username = self.sessions.authenticate(token)

        if self.roles.get(username) != "admin":
            self.audit_log.append(
                {
                    "event": "authorization_failure",
                    "username": username,
                }
            )
            raise AuthenticationError("Administrator role required.")

        self.audit_log.append(
            {
                "event": "admin_operation",
                "username": username,
            }
        )
        return "Administrative operation completed."

    def handle(self, request: WebRequest) -> SecurityResult:
        headers = WebSecurityPolicy.response_headers()

        try:
            self.rate_limiter.check(request.client_ip)
            InputValidator.safe_path(request.path)

            if request.method.upper() not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
            }:
                return SecurityResult(
                    False,
                    405,
                    "HTTP method not allowed.",
                    headers,
                )

            if len(request.body.encode("utf-8")) > 1_048_576:
                return SecurityResult(
                    False,
                    413,
                    "Request body is too large.",
                    headers,
                )

            return SecurityResult(
                True,
                200,
                "Request passed baseline security checks.",
                headers,
            )

        except RateLimitExceeded:
            return SecurityResult(
                False,
                429,
                "Too many requests.",
                headers,
            )
        except InputValidationError as exc:
            return SecurityResult(
                False,
                400,
                str(exc),
                headers,
            )

    def set_admin_for_demo(self, username: str) -> None:
        """Restricted to controlled test setup, not exposed as an HTTP endpoint."""
        if username not in self.users:
            raise KeyError(username)
        self.roles[username] = "admin"


def build_threat_model() -> ThreatModel:
    model = ThreatModel()

    model.add_asset(
        Asset(
            "user_credentials",
            SecurityLevel.CRITICAL,
            SecurityLevel.HIGH,
            SecurityLevel.MEDIUM,
            "identity-service",
        )
    )
    model.add_asset(
        Asset(
            "session_tokens",
            SecurityLevel.CRITICAL,
            SecurityLevel.CRITICAL,
            SecurityLevel.HIGH,
            "web-application",
        )
    )
    model.add_asset(
        Asset(
            "customer_records",
            SecurityLevel.HIGH,
            SecurityLevel.HIGH,
            SecurityLevel.HIGH,
            "data-service",
        )
    )
    model.add_asset(
        Asset(
            "web_api",
            SecurityLevel.MEDIUM,
            SecurityLevel.HIGH,
            SecurityLevel.CRITICAL,
            "platform-team",
        )
    )

    model.add_threat(
        Threat(
            "Credential stuffing",
            ThreatCategory.SPOOFING,
            "user_credentials",
            SecurityLevel.HIGH,
            SecurityLevel.CRITICAL,
            "Rate limiting, password hashing, MFA, breach-password screening.",
        )
    )
    model.add_threat(
        Threat(
            "Session theft",
            ThreatCategory.SPOOFING,
            "session_tokens",
            SecurityLevel.HIGH,
            SecurityLevel.CRITICAL,
            "Secure random tokens, HttpOnly/Secure cookies, TLS, rotation.",
        )
    )
    model.add_threat(
        Threat(
            "SQL injection",
            ThreatCategory.TAMPERING,
            "customer_records",
            SecurityLevel.HIGH,
            SecurityLevel.CRITICAL,
            "Parameterized queries, least-privilege database roles.",
        )
    )
    model.add_threat(
        Threat(
            "Cross-site scripting",
            ThreatCategory.INFORMATION_DISCLOSURE,
            "customer_records",
            SecurityLevel.HIGH,
            SecurityLevel.HIGH,
            "Contextual output encoding and restrictive CSP.",
        )
    )
    model.add_threat(
        Threat(
            "API resource exhaustion",
            ThreatCategory.DENIAL_OF_SERVICE,
            "web_api",
            SecurityLevel.MEDIUM,
            SecurityLevel.CRITICAL,
            "Rate limits, body limits, timeouts and bounded concurrency.",
        )
    )
    model.add_threat(
        Threat(
            "Broken access control",
            ThreatCategory.ELEVATION_OF_PRIVILEGE,
            "customer_records",
            SecurityLevel.HIGH,
            SecurityLevel.CRITICAL,
            "Server-side authorization and deny-by-default policies.",
        )
    )

    model.add_control(
        SecurityControl(
            "TLS",
            ("confidentiality", "integrity"),
            True,
            "Protects traffic from network interception and modification.",
        )
    )
    model.add_control(
        SecurityControl(
            "Secure password hashing",
            ("confidentiality", "authentication"),
            True,
            "Uses salted PBKDF2 with a high work factor.",
        )
    )
    model.add_control(
        SecurityControl(
            "Server-side authorization",
            ("authorization", "integrity"),
            True,
            "Checks roles after authentication.",
        )
    )
    model.add_control(
        SecurityControl(
            "Rate limiting",
            ("availability", "authentication"),
            True,
            "Limits repeated requests per client address.",
        )
    )
    model.add_control(
        SecurityControl(
            "Security headers",
            ("confidentiality", "integrity"),
            True,
            "Reduces browser-side attack exposure.",
        )
    )

    return model


def run_self_tests() -> None:
    assert PasswordHasher.verify_password(
        "CorrectHorseBatteryStaple!",
        PasswordHasher.hash_password("CorrectHorseBatteryStaple!"),
    )

    app = SecureWebApplication()
    app.register(
        "alice",
        "alice@example.com",
        "CorrectHorseBatteryStaple!",
    )

    token = app.login("alice", "CorrectHorseBatteryStaple!")
    assert app.sessions.authenticate(token) == "alice"

    try:
        app.admin_operation(token)
        raise AssertionError("Non-admin user was incorrectly authorized.")
    except AuthenticationError:
        pass

    app.set_admin_for_demo("alice")
    assert "completed" in app.admin_operation(token).lower()

    result = app.handle(
        WebRequest("GET", "/profile", {"Accept": "application/json"})
    )
    assert result.allowed
    assert result.status_code == 200
    assert "Content-Security-Policy" in result.headers

    traversal = app.handle(
        WebRequest("GET", "/files/../secrets", {})
    )
    assert not traversal.allowed
    assert traversal.status_code == 400

    oversized = app.handle(
        WebRequest("POST", "/upload", {}, "x" * 1_048_577)
    )
    assert not oversized.allowed
    assert oversized.status_code == 413

    assert not PasswordHasher.verify_password(
        "wrong-password",
        app.users["alice"],
    )


def print_report(model: ThreatModel) -> None:
    print("WEB SECURITY FUNDAMENTALS")
    print("=" * 70)

    print("\nCIA asset assessment")
    for asset in model.assets.values():
        print(
            f"- {asset.name}: "
            f"C={asset.confidentiality.name}, "
            f"I={asset.integrity.name}, "
            f"A={asset.availability.name}"
        )

    print("\nThreat model")
    for threat in sorted(
        model.threats,
        key=lambda item: item.risk_score,
        reverse=True,
    ):
        print(
            f"- {threat.name}: "
            f"{threat.category.value}, "
            f"risk={threat.risk_score}, "
            f"asset={threat.asset}"
        )

    print("\nImplemented controls")
    for control in model.controls:
        state = "implemented" if control.implemented else "missing"
        print(f"- {control.name}: {state}")

    print("\nControl coverage")
    for area, count in model.coverage().items():
        print(f"- {area}: {count} control(s)")

    print("\nHigh-risk threats")
    for threat in model.high_risk_threats():
        print(f"- {threat.name}: mitigate with {threat.mitigation}")


def main() -> None:
    run_self_tests()
    model = build_threat_model()
    print_report(model)

    print("\nSecure request simulation")
    app = SecureWebApplication()
    app.register(
        "security.user",
        "security.user@example.com",
        "LongRandomPassword!2026",
    )

    test_requests = [
        WebRequest("GET", "/dashboard", {}),
        WebRequest("POST", "/profile", {}, '{"displayName":"User"}'),
        WebRequest("GET", "/../../etc/passwd", {}),
        WebRequest("TRACE", "/debug", {}),
    ]

    for request in test_requests:
        result = app.handle(request)
        print(
            f"{request.method} {request.path} -> "
            f"{result.status_code}: {result.reason}"
        )


if __name__ == "__main__":
    main()
