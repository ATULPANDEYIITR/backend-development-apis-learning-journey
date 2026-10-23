#!/usr/bin/env python3
"""
JWT Fundamentals: structure, claims, expiration, signing, verification,
validation, key handling, and a small token-authentication workflow.

This implementation uses only the Python standard library. It implements
HMAC-SHA256 JWTs directly so the underlying mechanism is visible.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Mapping


class JWTError(Exception):
    """Base exception for JWT failures."""


class JWTFormatError(JWTError):
    """Raised when a token has an invalid JWT structure."""


class JWTSignatureError(JWTError):
    """Raised when a JWT signature does not verify."""


class JWTClaimsError(JWTError):
    """Raised when registered claims are invalid."""


def b64url_encode(value: bytes) -> str:
    """Encode bytes using JWT's unpadded Base64URL representation."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    """Decode unpadded Base64URL safely."""
    if not value or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for character in value):
        raise JWTFormatError("Invalid Base64URL data")

    padding = "=" * (-len(value) % 4)

    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, binascii.Error) as exc:
        raise JWTFormatError("Invalid Base64URL encoding") from exc


def compact_json(value: Mapping[str, Any]) -> bytes:
    """Serialize JWT objects deterministically enough for signing."""
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def parse_json_segment(segment: str) -> dict[str, Any]:
    try:
        raw = b64url_decode(segment)
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JWTFormatError("JWT JSON segment is invalid") from exc

    if not isinstance(value, dict):
        raise JWTFormatError("JWT header and payload must be JSON objects")

    return value


@dataclass(frozen=True)
class JWTSettings:
    issuer: str
    audience: str
    algorithm: str = "HS256"
    clock_skew_seconds: int = 30


class HMACJWT:
    """Minimal HS256 JWT implementation for learning and controlled examples."""

    def __init__(self, secret: bytes, settings: JWTSettings):
        if settings.algorithm != "HS256":
            raise ValueError("This implementation supports HS256 only")

        if len(secret) < 32:
            raise ValueError("HS256 secret must contain at least 32 bytes")

        self._secret = secret
        self.settings = settings

    def _sign(self, signing_input: bytes) -> bytes:
        return hmac.new(
            self._secret,
            signing_input,
            hashlib.sha256,
        ).digest()

    def encode(
        self,
        subject: str,
        roles: list[str],
        lifetime_seconds: int = 900,
        extra_claims: Mapping[str, Any] | None = None,
    ) -> str:
        if not subject:
            raise ValueError("Subject cannot be empty")

        if lifetime_seconds <= 0:
            raise ValueError("Token lifetime must be positive")

        now = int(time.time())

        header = {
            "alg": self.settings.algorithm,
            "typ": "JWT",
        }

        payload: dict[str, Any] = {
            "iss": self.settings.issuer,
            "sub": subject,
            "aud": self.settings.audience,
            "iat": now,
            "exp": now + lifetime_seconds,
            "jti": secrets.token_urlsafe(18),
            "roles": sorted(set(roles)),
        }

        if extra_claims:
            forbidden = {"iss", "sub", "aud", "iat", "exp", "jti"}
            if forbidden.intersection(extra_claims):
                raise ValueError("Registered claims cannot be overwritten")
            payload.update(extra_claims)

        encoded_header = b64url_encode(compact_json(header))
        encoded_payload = b64url_encode(compact_json(payload))

        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = self._sign(signing_input)

        return f"{encoded_header}.{encoded_payload}.{b64url_encode(signature)}"

    def decode_and_verify(self, token: str) -> dict[str, Any]:
        parts = token.split(".")

        if len(parts) != 3:
            raise JWTFormatError("JWT must contain exactly three segments")

        encoded_header, encoded_payload, encoded_signature = parts

        header = parse_json_segment(encoded_header)
        payload = parse_json_segment(encoded_payload)

        if header.get("typ") != "JWT":
            raise JWTFormatError("Unexpected JWT type")

        # Never accept an algorithm supplied by an untrusted token.
        if header.get("alg") != self.settings.algorithm:
            raise JWTFormatError("Unexpected signing algorithm")

        supplied_signature = b64url_decode(encoded_signature)
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected_signature = self._sign(signing_input)

        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise JWTSignatureError("JWT signature verification failed")

        self._validate_claims(payload)
        return payload

    def _validate_claims(self, payload: Mapping[str, Any]) -> None:
        required = ("iss", "sub", "aud", "iat", "exp", "jti")

        for claim in required:
            if claim not in payload:
                raise JWTClaimsError(f"Missing required claim: {claim}")

        if payload["iss"] != self.settings.issuer:
            raise JWTClaimsError("Issuer does not match")

        if payload["sub"] == "":
            raise JWTClaimsError("Subject cannot be empty")

        audience = payload["aud"]
        if isinstance(audience, str):
            valid_audience = audience == self.settings.audience
        elif isinstance(audience, list):
            valid_audience = self.settings.audience in audience
        else:
            valid_audience = False

        if not valid_audience:
            raise JWTClaimsError("Audience does not match")

        for claim in ("iat", "exp"):
            if not isinstance(payload[claim], int):
                raise JWTClaimsError(f"{claim} must be an integer")

        now = int(time.time())
        skew = self.settings.clock_skew_seconds

        if payload["iat"] > now + skew:
            raise JWTClaimsError("Token was issued in the future")

        if payload["exp"] <= now - skew:
            raise JWTClaimsError("Token has expired")

        if not isinstance(payload["jti"], str) or not payload["jti"]:
            raise JWTClaimsError("Invalid JWT ID")


class TokenRevocationList:
    """Simple in-memory revocation store for stateful logout/revocation."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, jti: str) -> None:
        self._revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked


class AuthenticationService:
    """Combines cryptographic verification with application authorization."""

    def __init__(self, jwt: HMACJWT, revocations: TokenRevocationList):
        self.jwt = jwt
        self.revocations = revocations

    def authenticate(self, token: str, required_role: str | None = None) -> dict[str, Any]:
        claims = self.jwt.decode_and_verify(token)

        if self.revocations.is_revoked(claims["jti"]):
            raise JWTClaimsError("Token has been revoked")

        roles = claims.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise JWTClaimsError("Invalid roles claim")

        if required_role is not None and required_role not in roles:
            raise PermissionError(f"Required role '{required_role}' is missing")

        return claims


def show_structure(token: str) -> None:
    """Display the three JWT compact-serialization components."""
    header, payload, signature = token.split(".")

    print("\nJWT structure")
    print("Header   :", header)
    print("Payload  :", payload)
    print("Signature:", signature)

    print("\nDecoded header")
    print(json.dumps(parse_json_segment(header), indent=2))

    print("\nDecoded payload")
    print(json.dumps(parse_json_segment(payload), indent=2))


def demonstrate_tampering(jwt: HMACJWT, token: str) -> None:
    """Modify the payload while retaining the original signature."""
    header, payload, signature = token.split(".")
    claims = parse_json_segment(payload)
    claims["roles"] = ["admin"]

    tampered_payload = b64url_encode(compact_json(claims))
    tampered_token = f"{header}.{tampered_payload}.{signature}"

    try:
        jwt.decode_and_verify(tampered_token)
    except JWTError as exc:
        print("\nTampering rejected:", exc)


def main() -> None:
    # In production, load a high-entropy secret from a secret manager or
    # environment configuration rather than embedding it in source code.
    secret = secrets.token_bytes(32)

    settings = JWTSettings(
        issuer="repository-api",
        audience="repository-client",
        algorithm="HS256",
        clock_skew_seconds=30,
    )

    jwt = HMACJWT(secret, settings)
    revocations = TokenRevocationList()
    auth = AuthenticationService(jwt, revocations)

    access_token = jwt.encode(
        subject="user-1042",
        roles=["developer", "reviewer"],
        lifetime_seconds=300,
        extra_claims={
            "email_verified": True,
            "scope": "repository:read repository:write",
        },
    )

    print("Issued JWT:")
    print(access_token)

    show_structure(access_token)

    authenticated_claims = auth.authenticate(
        access_token,
        required_role="reviewer",
    )

    print("\nAuthentication succeeded")
    print(json.dumps(authenticated_claims, indent=2))

    demonstrate_tampering(jwt, access_token)

    # Revocation is separate from JWT signature verification. A valid
    # signature does not automatically mean that a token must remain usable.
    revocations.revoke(authenticated_claims["jti"])

    try:
        auth.authenticate(access_token)
    except JWTError as exc:
        print("\nRevoked token rejected:", exc)

    # Invalid tokens should fail closed.
    for invalid_token in ("not-a-jwt", "a.b.c", ""):
        try:
            auth.authenticate(invalid_token)
        except JWTError as exc:
            print(f"Invalid token rejected ({invalid_token!r}): {exc}")
        except Exception as exc:
            print(f"Unexpected authentication failure: {exc}")


if __name__ == "__main__":
    main()
