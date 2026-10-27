from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuthenticationError(Exception):
    """Raised when authentication or token validation fails."""


class TokenValidationError(AuthenticationError):
    """Raised when an ID token fails validation."""


class UserInfoError(AuthenticationError):
    """Raised when a UserInfo request is invalid."""


class TokenType(str, Enum):
    ID_TOKEN = "id_token"
    ACCESS_TOKEN = "access_token"


class ReviewState(str, Enum):
    PENDING = "pending"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def json_b64(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return b64url_encode(encoded)


@dataclass(frozen=True)
class OIDCProvider:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    signing_secret: bytes
    supported_scopes: frozenset[str] = frozenset({"openid", "profile", "email"})


@dataclass(frozen=True)
class ClientRegistration:
    client_id: str
    client_secret: bytes
    redirect_uris: frozenset[str]
    allowed_scopes: frozenset[str]


@dataclass
class AuthorizationRequest:
    state: str
    nonce: str
    client_id: str
    redirect_uri: str
    scope: frozenset[str]
    code_challenge: str | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class AuthorizationCode:
    value: str
    client_id: str
    subject: str
    redirect_uri: str
    scope: frozenset[str]
    nonce: str
    code_challenge: str | None
    expires_at: float
    consumed: bool = False


@dataclass(frozen=True)
class User:
    subject: str
    username: str
    email: str
    name: str
    email_verified: bool


class OIDCProviderSimulator:
    """
    Small OIDC provider simulation.

    The implementation uses HMAC-SHA256 to keep the example self-contained.
    Production OIDC deployments normally use asymmetric signing such as RS256
    or ES256 and publish public keys through JWKS.
    """

    def __init__(self, provider: OIDCProvider) -> None:
        self.provider = provider
        self.users: dict[str, User] = {}
        self.codes: dict[str, AuthorizationCode] = {}

    def register_user(self, user: User) -> None:
        if not user.subject or not user.email:
            raise ValueError("subject and email are required")
        self.users[user.subject] = user

    def authorize(
        self,
        request: AuthorizationRequest,
        authenticated_subject: str,
    ) -> str:
        self._validate_authorization_request(request)

        if authenticated_subject not in self.users:
            raise AuthenticationError("user is not authenticated")

        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(
            value=code,
            client_id=request.client_id,
            subject=authenticated_subject,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            nonce=request.nonce,
            code_challenge=request.code_challenge,
            expires_at=time.time() + 120,
        )

        return code

    def exchange_code(
        self,
        client: ClientRegistration,
        code_value: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, str]:
        code = self.codes.get(code_value)

        if code is None:
            raise AuthenticationError("authorization code is invalid")

        if code.consumed:
            raise AuthenticationError("authorization code was already consumed")

        if time.time() >= code.expires_at:
            raise AuthenticationError("authorization code expired")

        if code.client_id != client.client_id:
            raise AuthenticationError("client mismatch")

        if code.redirect_uri != redirect_uri:
            raise AuthenticationError("redirect URI mismatch")

        if code.code_challenge:
            if not code_verifier:
                raise AuthenticationError("PKCE verifier is required")
            calculated = b64url_encode(
                hashlib.sha256(code_verifier.encode("ascii")).digest()
            )
            if not hmac.compare_digest(calculated, code.code_challenge):
                raise AuthenticationError("PKCE verification failed")

        code.consumed = True

        issued_at = int(time.time())
        id_token = self._create_id_token(
            client_id=client.client_id,
            subject=code.subject,
            nonce=code.nonce,
            issued_at=issued_at,
        )

        return {
            "token_type": "Bearer",
            "access_token": secrets.token_urlsafe(32),
            "id_token": id_token,
            "expires_in": "3600",
        }

    def userinfo(self, access_token: str, subject: str) -> dict[str, Any]:
        if not access_token:
            raise UserInfoError("access token is required")

        user = self.users.get(subject)
        if not user:
            raise UserInfoError("user does not exist")

        return {
            "sub": user.subject,
            "name": user.name,
            "preferred_username": user.username,
            "email": user.email,
            "email_verified": user.email_verified,
        }

    def _validate_authorization_request(
        self,
        request: AuthorizationRequest,
    ) -> None:
        if not request.state:
            raise AuthenticationError("state is required")

        if not request.nonce:
            raise AuthenticationError("nonce is required")

        if request.client_id != "web-client":
            raise AuthenticationError("unknown client")

        if request.redirect_uri != "https://app.example.com/callback":
            raise AuthenticationError("unregistered redirect URI")

        if "openid" not in request.scope:
            raise AuthenticationError("openid scope is mandatory")

        if not request.scope.issubset(self.provider.supported_scopes):
            raise AuthenticationError("unsupported scope")

        if request.created_at < time.time() - 600:
            raise AuthenticationError("authorization request expired")

    def _create_id_token(
        self,
        client_id: str,
        subject: str,
        nonce: str,
        issued_at: int,
    ) -> str:
        header = {
            "alg": "HS256",
            "typ": "JWT",
        }
        payload = {
            "iss": self.provider.issuer,
            "sub": subject,
            "aud": client_id,
            "iat": issued_at,
            "exp": issued_at + 3600,
            "auth_time": issued_at,
            "nonce": nonce,
        }

        signing_input = f"{json_b64(header)}.{json_b64(payload)}"
        signature = hmac.new(
            self.provider.signing_secret,
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()

        return f"{signing_input}.{b64url_encode(signature)}"


class OIDCClient:
    def __init__(
        self,
        provider: OIDCProvider,
        registration: ClientRegistration,
    ) -> None:
        self.provider = provider
        self.registration = registration
        self.session: dict[str, Any] = {}

    def start_login(self) -> AuthorizationRequest:
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)

        request = AuthorizationRequest(
            state=state,
            nonce=nonce,
            client_id=self.registration.client_id,
            redirect_uri="https://app.example.com/callback",
            scope=frozenset({"openid", "profile", "email"}),
        )

        self.session["state"] = state
        self.session["nonce"] = nonce
        return request

    def finish_login(
        self,
        request: AuthorizationRequest,
        returned_state: str,
        token_response: dict[str, str],
    ) -> dict[str, Any]:
        if not hmac.compare_digest(
            request.state,
            returned_state,
        ):
            raise AuthenticationError("state validation failed")

        expected_nonce = self.session.get("nonce")
        if not expected_nonce:
            raise AuthenticationError("missing client nonce")

        claims = self.validate_id_token(
            token_response["id_token"],
            expected_nonce,
        )

        self.session["authenticated"] = True
        self.session["subject"] = claims["sub"]
        self.session["access_token"] = token_response["access_token"]

        return claims

    def validate_id_token(
        self,
        encoded_token: str,
        expected_nonce: str,
    ) -> dict[str, Any]:
        parts = encoded_token.split(".")
        if len(parts) != 3:
            raise TokenValidationError("invalid JWT structure")

        encoded_header, encoded_payload, encoded_signature = parts
        signing_input = f"{encoded_header}.{encoded_payload}"

        expected_signature = hmac.new(
            self.provider.signing_secret,
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()

        try:
            actual_signature = b64url_decode(encoded_signature)
            header = json.loads(b64url_decode(encoded_header))
            claims = json.loads(b64url_decode(encoded_payload))
        except (ValueError, json.JSONDecodeError) as exc:
            raise TokenValidationError("invalid token encoding") from exc

        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise TokenValidationError("unexpected token header")

        if not hmac.compare_digest(
            actual_signature,
            expected_signature,
        ):
            raise TokenValidationError("invalid token signature")

        now = int(time.time())

        if claims.get("iss") != self.provider.issuer:
            raise TokenValidationError("issuer mismatch")

        audience = claims.get("aud")
        if audience != self.registration.client_id:
            raise TokenValidationError("audience mismatch")

        if claims.get("nonce") != expected_nonce:
            raise TokenValidationError("nonce mismatch")

        if not isinstance(claims.get("sub"), str):
            raise TokenValidationError("invalid subject")

        if not isinstance(claims.get("exp"), int) or claims["exp"] <= now:
            raise TokenValidationError("token expired")

        if not isinstance(claims.get("iat"), int):
            raise TokenValidationError("invalid issued-at claim")

        if claims["iat"] > now + 60:
            raise TokenValidationError("token issued in the future")

        return claims


def make_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    challenge = b64url_encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    )
    return verifier, challenge


def run_successful_flow() -> None:
    provider = OIDCProvider(
        issuer="https://id.example.com",
        authorization_endpoint="https://id.example.com/authorize",
        token_endpoint="https://id.example.com/token",
        userinfo_endpoint="https://id.example.com/userinfo",
        jwks_uri="https://id.example.com/.well-known/jwks.json",
        signing_secret=b"development-only-signing-secret",
    )

    registration = ClientRegistration(
        client_id="web-client",
        client_secret=b"client-secret",
        redirect_uris=frozenset({"https://app.example.com/callback"}),
        allowed_scopes=frozenset({"openid", "profile", "email"}),
    )

    provider_simulator = OIDCProviderSimulator(provider)
    provider_simulator.register_user(
        User(
            subject="00u-1842",
            username="atul",
            email="atul@example.com",
            name="Atul Pandey",
            email_verified=True,
        )
    )

    client = OIDCClient(provider, registration)

    request = client.start_login()

    verifier, challenge = make_pkce_pair()
    request.code_challenge = challenge

    authorization_code = provider_simulator.authorize(
        request,
        authenticated_subject="00u-1842",
    )

    token_response = provider_simulator.exchange_code(
        registration,
        authorization_code,
        request.redirect_uri,
        verifier,
    )

    claims = client.finish_login(
        request,
        returned_state=request.state,
        token_response=token_response,
    )

    userinfo = provider_simulator.userinfo(
        token_response["access_token"],
        claims["sub"],
    )

    print("OIDC authentication succeeded")
    print("Subject:", claims["sub"])
    print("Issuer:", claims["iss"])
    print("Audience:", claims["aud"])
    print("UserInfo:", json.dumps(userinfo, indent=2))


def run_security_failures() -> None:
    provider = OIDCProvider(
        issuer="https://id.example.com",
        authorization_endpoint="https://id.example.com/authorize",
        token_endpoint="https://id.example.com/token",
        userinfo_endpoint="https://id.example.com/userinfo",
        jwks_uri="https://id.example.com/.well-known/jwks.json",
        signing_secret=b"secret",
    )

    registration = ClientRegistration(
        client_id="web-client",
        client_secret=b"secret",
        redirect_uris=frozenset({"https://app.example.com/callback"}),
        allowed_scopes=frozenset({"openid"}),
    )

    simulator = OIDCProviderSimulator(provider)
    simulator.register_user(
        User(
            subject="user-1",
            username="demo",
            email="demo@example.com",
            name="Demo User",
            email_verified=True,
        )
    )

    client = OIDCClient(provider, registration)
    request = client.start_login()

    try:
        simulator.authorize(
            AuthorizationRequest(
                state="",
                nonce=request.nonce,
                client_id=request.client_id,
                redirect_uri=request.redirect_uri,
                scope=request.scope,
            ),
            "user-1",
        )
    except AuthenticationError as exc:
        print("Expected validation failure:", exc)

    try:
        client.finish_login(
            request,
            returned_state="attacker-controlled-state",
            token_response={
                "access_token": "unused",
                "id_token": "invalid",
            },
        )
    except AuthenticationError as exc:
        print("Expected state failure:", exc)


def main() -> None:
    run_successful_flow()
    run_security_failures()

    # Basic executable assertions provide a low-cost regression check.
    provider = OIDCProvider(
        issuer="https://issuer.test",
        authorization_endpoint="https://issuer.test/authorize",
        token_endpoint="https://issuer.test/token",
        userinfo_endpoint="https://issuer.test/userinfo",
        jwks_uri="https://issuer.test/jwks",
        signing_secret=b"assertion-secret",
    )

    assert provider.issuer.startswith("https://")
    assert "openid" in provider.supported_scopes
    assert len(b64url_encode(b"test")) > 0

    print("Validation checks passed.")


if __name__ == "__main__":
    main()
