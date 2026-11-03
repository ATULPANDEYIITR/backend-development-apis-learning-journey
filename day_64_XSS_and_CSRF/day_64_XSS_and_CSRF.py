#!/usr/bin/env python3
"""Defensive XSS, CSRF, cookie, and SameSite security demonstration."""

from __future__ import annotations

import html
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Optional
from urllib.parse import urlsplit


class SecurityError(Exception):
    """Raised when a security policy rejects a request."""


class SameSite(str, Enum):
    STRICT = "Strict"
    LAX = "Lax"
    NONE = "None"


@dataclass(frozen=True)
class CookiePolicy:
    name: str
    secure: bool = True
    http_only: bool = True
    same_site: SameSite = SameSite.LAX
    path: str = "/"
    max_age: int = 1800

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", self.name):
            raise ValueError("Invalid cookie name")
        if not self.path.startswith("/") or ";" in self.path:
            raise ValueError("Cookie path must be an absolute path")
        if self.max_age < 0:
            raise ValueError("Cookie max_age cannot be negative")
        if self.same_site is SameSite.NONE and not self.secure:
            raise ValueError("SameSite=None requires Secure")

    def set_cookie_header(self, value: str) -> str:
        if not value or any(char in value for char in "\r\n;"):
            raise ValueError("Invalid cookie value")

        parts = [
            f"{self.name}={value}",
            f"Path={self.path}",
            f"Max-Age={self.max_age}",
            f"SameSite={self.same_site.value}",
        ]
        if self.http_only:
            parts.append("HttpOnly")
        if self.secure:
            parts.append("Secure")
        return "; ".join(parts)


@dataclass(frozen=True)
class BrowserRequestContext:
    cross_site: bool
    top_level_navigation: bool
    method: str
    is_tls: bool


def cookie_would_be_sent(
    policy: CookiePolicy,
    context: BrowserRequestContext,
) -> bool:
    """Approximate browser SameSite behavior for common request scenarios."""
    method = context.method.upper()

    if policy.secure and not context.is_tls:
        return False

    if not context.cross_site:
        return True

    if policy.same_site is SameSite.STRICT:
        return False

    if policy.same_site is SameSite.LAX:
        # Lax permits cross-site top-level safe navigation.
        return context.top_level_navigation and method in {"GET", "HEAD"}

    # SameSite=None permits cross-site use, but requires Secure.
    return policy.same_site is SameSite.NONE and policy.secure


@dataclass
class WebSession:
    session_id: str
    user_id: str
    csrf_token: str
    expires_at: datetime
    revoked: bool = False


class SessionStore:
    """Server-side session storage; the browser receives only the session ID."""

    def __init__(self) -> None:
        self._sessions: Dict[str, WebSession] = {}

    def issue(self, user_id: str, lifetime_minutes: int = 30) -> WebSession:
        if not user_id.strip():
            raise ValueError("User ID is required")
        if lifetime_minutes <= 0:
            raise ValueError("Session lifetime must be positive")

        session = WebSession(
            session_id=secrets.token_urlsafe(32),
            user_id=user_id,
            csrf_token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=lifetime_minutes),
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[WebSession]:
        return self._sessions.get(session_id)

    def revoke(self, session_id: str) -> None:
        session = self.get(session_id)
        if session is not None:
            session.revoked = True


def is_canonical_https_origin(origin: str) -> bool:
    """Reject paths, credentials, query strings, fragments, and non-HTTPS origins."""
    try:
        parsed = urlsplit(origin)
        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and parsed.username is None
            and parsed.password is None
            and parsed.path == ""
            and parsed.query == ""
            and parsed.fragment == ""
            and parsed.netloc == parsed.netloc.lower()
        )
    except ValueError:
        return False


class WebSecurityLab:
    STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app_origin: str, max_input_length: int = 5000) -> None:
        if not is_canonical_https_origin(app_origin):
            raise ValueError("Application origin must be a canonical HTTPS origin")
        if max_input_length < 1:
            raise ValueError("Input length limit must be positive")

        self.app_origin = app_origin
        self.max_input_length = max_input_length
        self.sessions = SessionStore()
        self.comments: Dict[str, str] = {}

    @staticmethod
    def _validate_text(value: str, limit: int) -> None:
        if not isinstance(value, str):
            raise ValueError("Input must be text")
        if not value.strip():
            raise ValueError("Input cannot be empty")
        if len(value) > limit:
            raise ValueError(f"Input exceeds {limit} characters")
        if "\x00" in value:
            raise ValueError("Null characters are not permitted")

    def render_reflected_query(self, query: str) -> str:
        """Encode reflected input for an HTML text-node context."""
        self._validate_text(query, self.max_input_length)
        safe_query = html.escape(query, quote=True)
        return (
            "<!doctype html><html><body>"
            f"<p>Search results for: {safe_query}</p>"
            "</body></html>"
        )

    def add_comment(
        self,
        session_id: str,
        csrf_token: str,
        request_origin: str,
        method: str,
        comment: str,
    ) -> str:
        """Validate a state-changing request, then store untrusted text unchanged."""
        self._validate_text(comment, self.max_input_length)

        if method.upper() not in self.STATE_CHANGING_METHODS:
            raise SecurityError("A state-changing HTTP method is required")

        session = self.sessions.get(session_id)
        now = datetime.now(timezone.utc)

        if session is None or session.revoked or session.expires_at <= now:
            raise SecurityError("Session is missing, expired, or revoked")

        if request_origin != self.app_origin:
            raise SecurityError("Request Origin does not match the application origin")

        if not isinstance(csrf_token, str) or not hmac.compare_digest(
            session.csrf_token, csrf_token
        ):
            raise SecurityError("CSRF token validation failed")

        comment_id = str(uuid.uuid4())
        self.comments[comment_id] = comment
        return comment_id

    def render_stored_comment(self, comment_id: str) -> str:
        """Encode stored content every time it crosses into an HTML response."""
        try:
            raw_comment = self.comments[comment_id]
        except KeyError as exc:
            raise KeyError("Comment does not exist") from exc

        return f"<article>{html.escape(raw_comment, quote=True)}</article>"

    @staticmethod
    def response_security_headers() -> Dict[str, str]:
        return {
            "Content-Security-Policy": (
                "default-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Cache-Control": "no-store",
        }


def run_demo() -> None:
    app = WebSecurityLab("https://app.example.test")
    session = app.sessions.issue("user-1042")

    cookie_policy = CookiePolicy(
        name="__Host-session",
        secure=True,
        http_only=True,
        same_site=SameSite.LAX,
    )

    print("COOKIE")
    print(cookie_policy.set_cookie_header(session.session_id))

    cross_site_post = BrowserRequestContext(
        cross_site=True,
        top_level_navigation=False,
        method="POST",
        is_tls=True,
    )
    cross_site_get = BrowserRequestContext(
        cross_site=True,
        top_level_navigation=True,
        method="GET",
        is_tls=True,
    )
    print("SameSite=Lax cross-site POST:", cookie_would_be_sent(
        cookie_policy, cross_site_post
    ))
    print("SameSite=Lax cross-site top-level GET:", cookie_would_be_sent(
        cookie_policy, cross_site_get
    ))

    attack_like_input = '<script>alert("untrusted")</script>'

    print("\nREFLECTED XSS")
    reflected_response = app.render_reflected_query(attack_like_input)
    assert "<script>" not in reflected_response
    assert "&lt;script&gt;" in reflected_response
    print(reflected_response)

    print("\nSTORED XSS")
    comment_id = app.add_comment(
        session.session_id,
        session.csrf_token,
        "https://app.example.test",
        "POST",
        attack_like_input,
    )
    stored_response = app.render_stored_comment(comment_id)
    assert "<script>" not in stored_response
    assert "&lt;script&gt;" in stored_response
    print("Stored raw input:", app.comments[comment_id])
    print("Rendered output:", stored_response)

    print("\nCSRF VALIDATION")
    cases = [
        ("invalid token", "wrong-token", "https://app.example.test"),
        ("foreign origin", session.csrf_token, "https://attacker.example"),
    ]

    for label, token, origin in cases:
        try:
            app.add_comment(
                session.session_id,
                token,
                origin,
                "POST",
                "This request must be rejected",
            )
            raise AssertionError(f"{label} was unexpectedly accepted")
        except SecurityError as error:
            print(f"{label}: rejected ({error})")

    valid_id = app.add_comment(
        session.session_id,
        session.csrf_token,
        "https://app.example.test",
        "POST",
        "A valid comment",
    )
    print("Valid request accepted:", valid_id)

    print("\nSECURITY HEADERS")
    for name, value in app.response_security_headers().items():
        print(f"{name}: {value}")

    # Output encoding is context-specific. HTML text encoding is not a
    # substitute for safe URL, JavaScript, CSS, or DOM API handling.
    try:
        CookiePolicy(
            name="session",
            secure=False,
            same_site=SameSite.NONE,
        )
    except ValueError as error:
        print("\nInvalid cookie policy rejected:", error)

    print("\nAll security assertions passed.")


if __name__ == "__main__":
    run_demo()
