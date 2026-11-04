#!/usr/bin/env python3
"""
CORS Policy Engine and HTTP Request Simulator.

Demonstrates:
- Same-origin policy
- Simple and preflight requests
- Origin validation
- Allowed methods and headers
- Credential handling
- Wildcard restrictions
- Preflight caching
- Security validation
- Request auditing
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlsplit


class CorsError(Exception):
    """Base exception for CORS policy failures."""


class InvalidOriginError(CorsError):
    pass


class PolicyError(CorsError):
    pass


class RequestType(Enum):
    SIMPLE = "simple"
    PREFLIGHT = "preflight"
    ACTUAL = "actual"


@dataclass(frozen=True)
class Origin:
    scheme: str
    host: str
    port: Optional[int]

    @classmethod
    def parse(cls, value: str) -> "Origin":
        if not isinstance(value, str) or not value:
            raise InvalidOriginError("Origin must be a non-empty string.")

        if value == "null":
            raise InvalidOriginError("Opaque null origins are not accepted.")

        if value.strip() != value or any(ord(c) < 32 for c in value):
            raise InvalidOriginError("Invalid origin formatting.")

        parsed = urlsplit(value)

        if parsed.scheme not in {"http", "https"}:
            raise InvalidOriginError("Only HTTP and HTTPS origins are supported.")

        if not parsed.netloc or parsed.username or parsed.password:
            raise InvalidOriginError("Invalid origin authority.")

        if parsed.path or parsed.query or parsed.fragment:
            raise InvalidOriginError("An origin cannot contain a path or query.")

        try:
            port = parsed.port
        except ValueError as exc:
            raise InvalidOriginError("Invalid port.") from exc

        host = parsed.hostname

        if not host:
            raise InvalidOriginError("Missing hostname.")

        host = host.lower()

        if host.endswith("."):
            host = host[:-1]

        if not host:
            raise InvalidOriginError("Invalid hostname.")

        if port is not None and not 1 <= port <= 65535:
            raise InvalidOriginError("Port must be between 1 and 65535.")

        if (parsed.scheme == "http" and port == 80):
            port = None
        elif parsed.scheme == "https" and port == 443:
            port = None

        return cls(parsed.scheme, host, port)

    def __str__(self) -> str:
        authority = self.host

        if ":" in self.host and not self.host.startswith("["):
            authority = f"[{self.host}]"

        if self.port is not None:
            authority += f":{self.port}"

        return f"{self.scheme}://{authority}"


@dataclass
class CorsPolicy:
    allowed_origins: set[str]
    allowed_methods: set[str] = field(
        default_factory=lambda: {"GET", "POST", "PUT", "DELETE"}
    )
    allowed_headers: set[str] = field(
        default_factory=lambda: {"content-type", "authorization"}
    )
    exposed_headers: set[str] = field(
        default_factory=lambda: {"x-request-id"}
    )
    allow_credentials: bool = False
    max_age: int = 600
    allow_private_network: bool = False

    def __post_init__(self):
        if not 0 <= self.max_age <= 86400:
            raise PolicyError("Max age must be between 0 and 86400 seconds.")

        self.allowed_methods = {
            method.upper() for method in self.allowed_methods
        }

        self.allowed_headers = {
            header.lower() for header in self.allowed_headers
        }

        self.exposed_headers = {
            header.lower() for header in self.exposed_headers
        }

        if "*" in self.allowed_origins and self.allow_credentials:
            raise PolicyError(
                "Wildcard origins cannot be combined with credentials."
            )

        for origin in self.allowed_origins:
            if origin != "*":
                Origin.parse(origin)

    def resolve_origin(self, origin: str) -> Optional[str]:
        parsed = str(Origin.parse(origin))

        if "*" in self.allowed_origins and not self.allow_credentials:
            return "*"

        if parsed in self.allowed_origins:
            return parsed

        return None


@dataclass
class CorsRequest:
    origin: Optional[str]
    method: str
    headers: dict[str, str] = field(default_factory=dict)
    with_credentials: bool = False
    requested_method: Optional[str] = None
    requested_headers: list[str] = field(default_factory=list)
    private_network_request: bool = False


@dataclass
class CorsResponse:
    status: int
    headers: dict[str, str]
    allowed: bool
    message: str

    def to_dict(self):
        return {
            "status": self.status,
            "allowed": self.allowed,
            "message": self.message,
            "headers": self.headers,
        }


class PreflightCache:
    """In-memory cache for successful preflight decisions."""

    def __init__(self):
        self._entries: dict[tuple, float] = {}

    def contains(self, key: tuple) -> bool:
        expiry = self._entries.get(key)

        if expiry is None:
            return False

        if expiry <= time.monotonic():
            del self._entries[key]
            return False

        return True

    def store(self, key: tuple, max_age: int):
        if max_age > 0:
            self._entries[key] = time.monotonic() + max_age

    def clear(self):
        self._entries.clear()


class CorsEngine:
    SIMPLE_METHODS = {"GET", "HEAD", "POST"}

    SIMPLE_HEADERS = {
        "accept",
        "accept-language",
        "content-language",
        "content-type",
    }

    SAFE_CONTENT_TYPES = {
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    }

    def __init__(self, policy: CorsPolicy):
        self.policy = policy
        self.cache = PreflightCache()
        self.audit_log: list[dict] = []

    def _audit(self, request: CorsRequest, decision: str):
        self.audit_log.append({
            "origin": request.origin,
            "method": request.method,
            "decision": decision,
            "timestamp": time.time(),
        })

    @classmethod
    def is_simple_request(cls, request: CorsRequest) -> bool:
        if request.method.upper() not in cls.SIMPLE_METHODS:
            return False

        for name, value in request.headers.items():
            normalized = name.lower()

            if normalized in cls.SIMPLE_HEADERS:
                if normalized == "content-type":
                    media_type = value.split(";")[0].strip().lower()

                    if media_type not in cls.SAFE_CONTENT_TYPES:
                        return False
            elif normalized not in {
                "accept-charset",
                "content-language",
                "dpr",
                "downlink",
                "save-data",
                "viewport-width",
                "width",
            }:
                return False

        return True

    def _response_headers(self, origin: str) -> dict[str, str]:
        headers = {
            "Access-Control-Allow-Origin": origin,
        }

        if self.policy.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        if origin != "*":
            headers["Vary"] = "Origin"

        if self.policy.exposed_headers:
            headers["Access-Control-Expose-Headers"] = ", ".join(
                sorted(self.policy.exposed_headers)
            )

        return headers

    def process(self, request: CorsRequest) -> CorsResponse:
        method = request.method.upper()

        if not re.fullmatch(r"[A-Z]+", method):
            raise CorsError("Invalid HTTP method.")

        if not request.origin:
            self._audit(request, "same-origin-or-no-origin")
            return CorsResponse(
                200, {}, True, "No CORS processing required."
            )

        try:
            allowed_origin = self.policy.resolve_origin(request.origin)
        except InvalidOriginError as exc:
            self._audit(request, "invalid-origin")
            return CorsResponse(403, {}, False, str(exc))

        if allowed_origin is None:
            self._audit(request, "origin-denied")
            return CorsResponse(
                403, {}, False, "Origin is not allowed."
            )

        if request.with_credentials and not self.policy.allow_credentials:
            self._audit(request, "credentials-denied")
            return CorsResponse(
                403, {}, False, "Credentials are not allowed."
            )

        headers = self._response_headers(allowed_origin)

        if method == "OPTIONS" and request.requested_method:
            return self._handle_preflight(
                request, allowed_origin, headers
            )

        if method not in self.policy.allowed_methods:
            self._audit(request, "method-denied")
            return CorsResponse(
                405, {}, False, "HTTP method is not allowed."
            )

        self._audit(request, "allowed")

        return CorsResponse(
            200, headers, True, "CORS request allowed."
        )

    def _handle_preflight(
        self,
        request: CorsRequest,
        allowed_origin: str,
        headers: dict[str, str],
    ) -> CorsResponse:

        requested_method = request.requested_method.upper()

        requested_headers = {
            header.strip().lower()
            for header in request.requested_headers
            if header.strip()
        }

        if not re.fullmatch(r"[A-Z]+", requested_method):
            return CorsResponse(
                400, {}, False, "Invalid requested method."
            )

        if not requested_headers.issubset(self.policy.allowed_headers):
            self._audit(request, "preflight-header-denied")
            return CorsResponse(
                403, {}, False, "Requested headers are not allowed."
            )

        if requested_method not in self.policy.allowed_methods:
            self._audit(request, "preflight-method-denied")
            return CorsResponse(
                403, {}, False, "Requested method is not allowed."
            )

        if (
            request.private_network_request
            and not self.policy.allow_private_network
        ):
            self._audit(request, "private-network-denied")
            return CorsResponse(
                403, {}, False, "Private network access is not allowed."
            )

        key = (
            allowed_origin,
            requested_method,
            tuple(sorted(requested_headers)),
            request.with_credentials,
            request.private_network_request,
        )

        if self.cache.contains(key):
            self._audit(request, "preflight-cache-hit")
            return CorsResponse(
                204, headers, True, "Cached preflight accepted."
            )

        headers.update({
            "Access-Control-Allow-Methods": ", ".join(
                sorted(self.policy.allowed_methods)
            ),
            "Access-Control-Allow-Headers": ", ".join(
                sorted(requested_headers)
            ),
            "Access-Control-Max-Age": str(self.policy.max_age),
        })

        if request.private_network_request:
            headers["Access-Control-Allow-Private-Network"] = "true"

        self.cache.store(key, self.policy.max_age)
        self._audit(request, "preflight-accepted")

        return CorsResponse(
            204, headers, True, "Preflight accepted."
        )


def demonstrate():
    policy = CorsPolicy(
        allowed_origins={
            "https://app.example.com",
            "https://admin.example.com",
        },
        allowed_methods={"GET", "POST", "PUT", "DELETE"},
        allowed_headers={
            "content-type",
            "authorization",
            "x-request-id",
        },
        exposed_headers={"x-request-id"},
        allow_credentials=True,
        max_age=600,
    )

    engine = CorsEngine(policy)

    scenarios = [
        (
            "Simple GET",
            CorsRequest(
                origin="https://app.example.com",
                method="GET",
            ),
        ),
        (
            "Preflight POST",
            CorsRequest(
                origin="https://app.example.com",
                method="OPTIONS",
                requested_method="POST",
                requested_headers=["content-type", "authorization"],
                with_credentials=True,
            ),
        ),
        (
            "Disallowed origin",
            CorsRequest(
                origin="https://attacker.example.net",
                method="GET",
            ),
        ),
        (
            "Disallowed method",
            CorsRequest(
                origin="https://app.example.com",
                method="PATCH",
            ),
        ),
        (
            "Preflight with forbidden header",
            CorsRequest(
                origin="https://app.example.com",
                method="OPTIONS",
                requested_method="POST",
                requested_headers=["x-unknown-header"],
            ),
        ),
        (
            "Credential request",
            CorsRequest(
                origin="https://admin.example.com",
                method="GET",
                with_credentials=True,
            ),
        ),
    ]

    for name, request in scenarios:
        response = engine.process(request)
        print(f"\n{name}")
        print(json.dumps(response.to_dict(), indent=2))

    print("\nAudit statistics:")

    allowed = sum(
        entry["decision"] in {
            "allowed",
            "preflight-accepted",
            "preflight-cache-hit",
            "same-origin-or-no-origin",
        }
        for entry in engine.audit_log
    )

    denied = len(engine.audit_log) - allowed

    print({
        "total": len(engine.audit_log),
        "allowed": allowed,
        "denied": denied,
    })

    # Canonical origin normalization.
    assert str(Origin.parse("https://APP.EXAMPLE.COM:443")) == (
        "https://app.example.com"
    )

    # Wildcard and credential combination must be rejected.
    try:
        CorsPolicy(
            allowed_origins={"*"},
            allow_credentials=True,
        )
        raise AssertionError("Invalid wildcard policy was accepted.")
    except PolicyError:
        pass

    # Simple requests do not require preflight.
    assert CorsEngine.is_simple_request(
        CorsRequest(
            origin="https://app.example.com",
            method="GET",
        )
    )

    # Authorization is not a CORS-safelisted request header.
    assert not CorsEngine.is_simple_request(
        CorsRequest(
            origin="https://app.example.com",
            method="GET",
            headers={"Authorization": "Bearer token"},
        )
    )

    print("\nAll assertions passed.")


if __name__ == "__main__":
    demonstrate()
