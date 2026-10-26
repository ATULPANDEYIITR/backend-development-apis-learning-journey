#!/usr/bin/env python3

"""
OAuth 2.0 authorization model.

The program models the core OAuth 2.0 roles and workflow:
- Authorization Server
- Resource Server
- Client
- Resource Owner
- Access tokens
- Refresh tokens
- Scopes
- Authorization code flow with PKCE
- Token validation
- Resource access
- Token refresh
- Revocation
- Security validation

This is a deterministic educational simulation. It does not implement an
internet-facing OAuth server and intentionally avoids real cryptographic
token signing libraries.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Optional, Set


class OAuthError(Exception):
    """Base OAuth failure."""


class InvalidRequest(OAuthError):
    pass


class InvalidClient(OAuthError):
    pass


class InvalidGrant(OAuthError):
    pass


class InvalidToken(OAuthError):
    pass


class InsufficientScope(OAuthError):
    pass


class TokenType(Enum):
    BEARER = "Bearer"


@dataclass(frozen=True)
class Client:
    client_id: str
    redirect_uris: FrozenSet[str]
    allowed_scopes: FrozenSet[str]
    is_confidential: bool = False
    client_secret: Optional[str] = None


@dataclass
class AuthorizationCode:
    code: str
    client_id: str
    redirect_uri: str
    resource_owner: str
    scopes: FrozenSet[str]
    code_challenge: str
    expires_at: float
    used: bool = False


@dataclass
class AccessToken:
    value: str
    client_id: str
    resource_owner: str
    scopes: FrozenSet[str]
    expires_at: float
    token_type: TokenType = TokenType.BEARER
    revoked: bool = False

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


@dataclass
class RefreshToken:
    value: str
    client_id: str
    resource_owner: str
    scopes: FrozenSet[str]
    expires_at: float
    revoked: bool = False

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


@dataclass
class Resource:
    resource_id: str
    owner: str
    fields: Dict[str, str]
    required_scope: str


class AuthorizationServer:
    """
    Stateful authorization server.

    Important security properties:
    - redirect URIs must be registered exactly
    - requested scopes are constrained by client registration
    - authorization codes are short-lived and single-use
    - PKCE verifier must match the authorization request
    - access and refresh tokens have independent expiration
    """

    def __init__(self, issuer: str):
        self.issuer = issuer
        self.clients: Dict[str, Client] = {}
        self.authorization_codes: Dict[str, AuthorizationCode] = {}
        self.access_tokens: Dict[str, AccessToken] = {}
        self.refresh_tokens: Dict[str, RefreshToken] = {}

    @staticmethod
    def _random_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def register_client(self, client: Client) -> None:
        if not client.client_id:
            raise InvalidClient("client_id is required")

        if not client.redirect_uris:
            raise InvalidClient("at least one redirect URI is required")

        if client.is_confidential and not client.client_secret:
            raise InvalidClient("confidential clients require a client secret")

        if not client.is_confidential and client.client_secret is not None:
            raise InvalidClient("public clients must not rely on a client secret")

        self.clients[client.client_id] = client

    def authorize(
        self,
        client_id: str,
        redirect_uri: str,
        resource_owner: str,
        requested_scopes: Set[str],
        code_challenge: str,
        lifetime_seconds: int = 120,
    ) -> str:
        client = self.clients.get(client_id)
        if client is None:
            raise InvalidClient("unknown client")

        if redirect_uri not in client.redirect_uris:
            raise InvalidRequest("redirect URI is not registered")

        if not resource_owner:
            raise InvalidRequest("resource owner is required")

        if not code_challenge:
            raise InvalidRequest("PKCE code_challenge is required")

        if not requested_scopes:
            raise InvalidRequest("at least one scope is required")

        if not requested_scopes.issubset(client.allowed_scopes):
            denied = requested_scopes - client.allowed_scopes
            raise InvalidRequest(f"client cannot request scopes: {sorted(denied)}")

        code = self._random_token()
        self.authorization_codes[code] = AuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            resource_owner=resource_owner,
            scopes=frozenset(requested_scopes),
            code_challenge=code_challenge,
            expires_at=time.time() + lifetime_seconds,
        )
        return code

    def exchange_code(
        self,
        client_id: str,
        code: str,
        redirect_uri: str,
        code_verifier: str,
        client_secret: Optional[str] = None,
    ) -> tuple[AccessToken, RefreshToken]:
        client = self.clients.get(client_id)
        if client is None:
            raise InvalidClient("unknown client")

        if client.is_confidential:
            if client_secret is None:
                raise InvalidClient("client authentication is required")
            if not hmac.compare_digest(client.client_secret or "", client_secret):
                raise InvalidClient("invalid client credentials")

        auth_code = self.authorization_codes.get(code)
        if auth_code is None:
            raise InvalidGrant("authorization code does not exist")

        if auth_code.used:
            raise InvalidGrant("authorization code has already been used")

        if time.time() >= auth_code.expires_at:
            raise InvalidGrant("authorization code has expired")

        if auth_code.client_id != client_id:
            raise InvalidGrant("authorization code belongs to another client")

        if auth_code.redirect_uri != redirect_uri:
            raise InvalidGrant("redirect URI mismatch")

        expected_challenge = self._pkce_challenge(code_verifier)
        if not hmac.compare_digest(expected_challenge, auth_code.code_challenge):
            raise InvalidGrant("PKCE verification failed")

        auth_code.used = True

        access_token = AccessToken(
            value=self._random_token(),
            client_id=client_id,
            resource_owner=auth_code.resource_owner,
            scopes=auth_code.scopes,
            expires_at=time.time() + 900,
        )

        refresh_token = RefreshToken(
            value=self._random_token(),
            client_id=client_id,
            resource_owner=auth_code.resource_owner,
            scopes=auth_code.scopes,
            expires_at=time.time() + 86400,
        )

        self.access_tokens[access_token.value] = access_token
        self.refresh_tokens[refresh_token.value] = refresh_token

        return access_token, refresh_token

    def refresh(
        self,
        client_id: str,
        refresh_token_value: str,
        requested_scopes: Optional[Set[str]] = None,
        client_secret: Optional[str] = None,
    ) -> tuple[AccessToken, RefreshToken]:
        client = self.clients.get(client_id)
        if client is None:
            raise InvalidClient("unknown client")

        if client.is_confidential:
            if client_secret is None:
                raise InvalidClient("client authentication is required")
            if not hmac.compare_digest(client.client_secret or "", client_secret):
                raise InvalidClient("invalid client credentials")

        old_refresh = self.refresh_tokens.get(refresh_token_value)
        if old_refresh is None or old_refresh.revoked:
            raise InvalidGrant("refresh token is invalid or revoked")

        if old_refresh.is_expired():
            raise InvalidGrant("refresh token has expired")

        if old_refresh.client_id != client_id:
            raise InvalidGrant("refresh token belongs to another client")

        scopes = old_refresh.scopes
        if requested_scopes is not None:
            if not requested_scopes.issubset(old_refresh.scopes):
                raise InvalidGrant("requested scope exceeds originally granted scope")
            scopes = frozenset(requested_scopes)

        # Refresh-token rotation reduces replay risk.
        old_refresh.revoked = True

        access_token = AccessToken(
            value=self._random_token(),
            client_id=client_id,
            resource_owner=old_refresh.resource_owner,
            scopes=scopes,
            expires_at=time.time() + 900,
        )

        new_refresh = RefreshToken(
            value=self._random_token(),
            client_id=client_id,
            resource_owner=old_refresh.resource_owner,
            scopes=scopes,
            expires_at=time.time() + 86400,
        )

        self.access_tokens[access_token.value] = access_token
        self.refresh_tokens[new_refresh.value] = new_refresh

        return access_token, new_refresh

    def revoke_access_token(self, token_value: str) -> None:
        token = self.access_tokens.get(token_value)
        if token:
            token.revoked = True

    def validate_access_token(
        self,
        token_value: str,
        required_scope: str,
    ) -> AccessToken:
        token = self.access_tokens.get(token_value)

        if token is None or token.revoked:
            raise InvalidToken("access token is invalid or revoked")

        if token.is_expired():
            raise InvalidToken("access token has expired")

        if required_scope not in token.scopes:
            raise InsufficientScope(
                f"required scope '{required_scope}' was not granted"
            )

        return token


class ResourceServer:
    """Resource server that trusts the authorization server's token validation."""

    def __init__(self, authorization_server: AuthorizationServer):
        self.authorization_server = authorization_server
        self.resources: Dict[str, Resource] = {}

    def add_resource(self, resource: Resource) -> None:
        if resource.resource_id in self.resources:
            raise ValueError("duplicate resource")

        self.resources[resource.resource_id] = resource

    def get_resource(self, token_value: str, resource_id: str) -> Dict[str, str]:
        resource = self.resources.get(resource_id)
        if resource is None:
            raise KeyError("resource does not exist")

        token = self.authorization_server.validate_access_token(
            token_value,
            resource.required_scope,
        )

        # Authorization is checked after token validity and scope validation.
        if token.resource_owner != resource.owner:
            raise OAuthError("token does not identify an authorized owner")

        return resource.fields.copy()


def generate_pkce_verifier() -> str:
    """Create a high-entropy PKCE verifier."""
    return secrets.token_urlsafe(48)


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def demonstrate() -> None:
    server = AuthorizationServer("https://auth.example.test")
    resource_server = ResourceServer(server)

    client = Client(
        client_id="web-dashboard",
        redirect_uris=frozenset({"https://app.example.test/callback"}),
        allowed_scopes=frozenset({"profile:read", "orders:read"}),
        is_confidential=True,
        client_secret="server-side-secret-rotate-this",
    )
    server.register_client(client)

    resource_server.add_resource(
        Resource(
            resource_id="profile:alice",
            owner="alice",
            fields={
                "name": "Alice",
                "department": "Engineering",
                "role": "Developer",
            },
            required_scope="profile:read",
        )
    )

    verifier = generate_pkce_verifier()
    challenge = pkce_challenge(verifier)

    # 1. Authorization endpoint creates a short-lived authorization code.
    code = server.authorize(
        client_id="web-dashboard",
        redirect_uri="https://app.example.test/callback",
        resource_owner="alice",
        requested_scopes={"profile:read"},
        code_challenge=challenge,
    )

    # 2. Token endpoint exchanges the code after PKCE and client validation.
    access_token, refresh_token = server.exchange_code(
        client_id="web-dashboard",
        code=code,
        redirect_uri="https://app.example.test/callback",
        code_verifier=verifier,
        client_secret="server-side-secret-rotate-this",
    )

    print("Authorization code exchanged successfully.")
    print("Granted scopes:", sorted(access_token.scopes))

    # 3. Resource server validates the access token and scope.
    profile = resource_server.get_resource(
        access_token.value,
        "profile:alice",
    )
    print("Protected resource:", profile)

    # 4. Demonstrate least privilege.
    try:
        resource_server.get_resource(
            access_token.value,
            "profile:alice",
        )
    except OAuthError as exc:
        print("Unexpected authorization failure:", exc)

    # 5. Refresh-token rotation.
    new_access, new_refresh = server.refresh(
        client_id="web-dashboard",
        refresh_token_value=refresh_token.value,
        client_secret="server-side-secret-rotate-this",
    )
    print("Refresh succeeded:", new_access.value != access_token.value)

    # Old refresh token must no longer work.
    try:
        server.refresh(
            client_id="web-dashboard",
            refresh_token_value=refresh_token.value,
            client_secret="server-side-secret-rotate-this",
        )
    except InvalidGrant as exc:
        print("Replay protection:", exc)

    # 6. Revoke the active access token.
    server.revoke_access_token(new_access.value)

    try:
        resource_server.get_resource(new_access.value, "profile:alice")
    except InvalidToken as exc:
        print("Revocation enforced:", exc)

    # 7. PKCE failure case.
    verifier2 = generate_pkce_verifier()
    code2 = server.authorize(
        client_id="web-dashboard",
        redirect_uri="https://app.example.test/callback",
        resource_owner="alice",
        requested_scopes={"profile:read"},
        code_challenge=pkce_challenge(verifier2),
    )

    try:
        server.exchange_code(
            client_id="web-dashboard",
            code=code2,
            redirect_uri="https://app.example.test/callback",
            code_verifier="wrong-verifier",
            client_secret="server-side-secret-rotate-this",
        )
    except InvalidGrant as exc:
        print("PKCE failure rejected:", exc)

    # 8. Redirect URI validation.
    try:
        server.authorize(
            client_id="web-dashboard",
            redirect_uri="https://evil.example.test/callback",
            resource_owner="alice",
            requested_scopes={"profile:read"},
            code_challenge=challenge,
        )
    except InvalidRequest as exc:
        print("Open redirect protection:", exc)

    # 9. Scope validation.
    try:
        server.authorize(
            client_id="web-dashboard",
            redirect_uri="https://app.example.test/callback",
            resource_owner="alice",
            requested_scopes={"admin:write"},
            code_challenge=challenge,
        )
    except InvalidRequest as exc:
        print("Least-privilege scope rejection:", exc)


if __name__ == "__main__":
    demonstrate()
