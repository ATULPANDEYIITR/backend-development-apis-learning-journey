#!/usr/bin/env python3
"""Refresh-token lifecycle simulator using only the Python standard library."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import unittest
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Callable


class TokenError(Exception):
    """Base class for authentication-token failures."""


class InvalidToken(TokenError):
    pass


class ExpiredToken(TokenError):
    pass


class RevokedToken(TokenError):
    pass


class ReplayDetected(TokenError):
    pass


class SessionStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_at: float
    refresh_expires_at: float


@dataclass
class RefreshSession:
    session_id: str
    user_id: str
    current_refresh_hash: str
    created_at: float
    expires_at: float
    status: SessionStatus = SessionStatus.ACTIVE
    generation: int = 0
    previous_refresh_hashes: set[str] = field(default_factory=set)
    revoked_at: float | None = None


class TokenService:
    """
    In-memory demonstration of opaque access and refresh tokens.

    Only token hashes are stored. Production systems should use durable,
    transactional storage and authenticated transport.
    """

    def __init__(
        self,
        access_ttl: int = 300,
        refresh_ttl: int = 86400,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if access_ttl <= 0 or refresh_ttl <= access_ttl:
            raise ValueError("TTLs must be positive; refresh TTL must exceed access TTL")
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.clock = clock
        self._lock = RLock()
        self._sessions: dict[str, RefreshSession] = {}
        self._access_tokens: dict[str, tuple[str, float]] = {}
        self._revoked_refresh_hashes: set[str] = set()

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(48)

    def _issue_pair(self, session: RefreshSession) -> TokenPair:
        now = self.clock()
        access = self._new_token()
        refresh = self._new_token()
        refresh_hash = self._hash(refresh)

        session.current_refresh_hash = refresh_hash
        self._access_tokens[self._hash(access)] = (
            session.session_id,
            now + self.access_ttl,
        )

        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=now + self.access_ttl,
            refresh_expires_at=session.expires_at,
        )

    def login(self, user_id: str) -> TokenPair:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")

        with self._lock:
            now = self.clock()
            session = RefreshSession(
                session_id=secrets.token_urlsafe(18),
                user_id=user_id.strip(),
                current_refresh_hash="",
                created_at=now,
                expires_at=now + self.refresh_ttl,
            )
            self._sessions[session.session_id] = session
            return self._issue_pair(session)

    def authenticate_access(self, access_token: str) -> str:
        if not isinstance(access_token, str) or not access_token:
            raise InvalidToken("Access token is missing")

        with self._lock:
            record = self._access_tokens.get(self._hash(access_token))
            if record is None:
                raise InvalidToken("Access token is unknown")

            session_id, expires_at = record
            session = self._sessions.get(session_id)

            if session is None:
                raise InvalidToken("Session does not exist")
            if session.status is SessionStatus.REVOKED:
                raise RevokedToken("Session has been revoked")
            if self.clock() >= expires_at:
                raise ExpiredToken("Access token has expired")
            if self.clock() >= session.expires_at:
                raise ExpiredToken("Session has expired")

            return session.user_id

    def refresh(self, refresh_token: str) -> TokenPair:
        if not isinstance(refresh_token, str) or not refresh_token:
            raise InvalidToken("Refresh token is missing")

        supplied_hash = self._hash(refresh_token)

        with self._lock:
            if supplied_hash in self._revoked_refresh_hashes:
                raise ReplayDetected("A revoked refresh token was reused")

            session = next(
                (
                    item
                    for item in self._sessions.values()
                    if hmac.compare_digest(
                        item.current_refresh_hash, supplied_hash
                    )
                ),
                None,
            )

            if session is None:
                raise InvalidToken("Refresh token is invalid")

            now = self.clock()

            if session.status is SessionStatus.REVOKED:
                raise RevokedToken("Session has been revoked")

            if now >= session.expires_at:
                session.status = SessionStatus.EXPIRED
                raise ExpiredToken("Refresh session has expired")

            # Rotation and replacement occur under one lock. A production
            # implementation must enforce this atomically in the database.
            self._revoked_refresh_hashes.add(supplied_hash)
            session.previous_refresh_hashes.add(supplied_hash)
            session.generation += 1
            return self._issue_pair(session)

    def revoke_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.status is SessionStatus.REVOKED:
                return False

            session.status = SessionStatus.REVOKED
            session.revoked_at = self.clock()
            self._revoked_refresh_hashes.add(session.current_refresh_hash)
            return True

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        supplied_hash = self._hash(refresh_token)

        with self._lock:
            for session in self._sessions.values():
                if hmac.compare_digest(
                    session.current_refresh_hash, supplied_hash
                ):
                    return self.revoke_session(session.session_id)

            return supplied_hash in self._revoked_refresh_hashes

    def session_for_access(self, access_token: str) -> str:
        self.authenticate_access(access_token)
        return self._access_tokens[self._hash(access_token)][0]

    def audit_snapshot(self) -> list[dict[str, object]]:
        with self._lock:
            return [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "status": s.status.value,
                    "generation": s.generation,
                    "expires_at": s.expires_at,
                }
                for s in self._sessions.values()
            ]


def demonstration() -> None:
    service = TokenService(access_ttl=300, refresh_ttl=3600)

    first = service.login("user-1042")
    print("Authenticated user:", service.authenticate_access(first.access_token))

    second = service.refresh(first.refresh_token)
    print("Rotated refresh token:", first.refresh_token != second.refresh_token)

    try:
        service.refresh(first.refresh_token)
    except ReplayDetected as exc:
        print("Replay protection:", exc)

    session_id = service.session_for_access(second.access_token)
    service.revoke_session(session_id)

    try:
        service.authenticate_access(second.access_token)
    except RevokedToken as exc:
        print("Revocation enforced:", exc)

    print("Audit:", service.audit_snapshot())


class TokenServiceTests(unittest.TestCase):
    def test_rotation_and_replay(self) -> None:
        service = TokenService()
        first = service.login("alice")
        second = service.refresh(first.refresh_token)
        self.assertNotEqual(first.refresh_token, second.refresh_token)
        with self.assertRaises(ReplayDetected):
            service.refresh(first.refresh_token)

    def test_revocation(self) -> None:
        service = TokenService()
        pair = service.login("bob")
        session_id = service.session_for_access(pair.access_token)
        service.revoke_session(session_id)
        with self.assertRaises(RevokedToken):
            service.authenticate_access(pair.access_token)

    def test_validation(self) -> None:
        with self.assertRaises(ValueError):
            TokenService(access_ttl=0)
        with self.assertRaises(ValueError):
            TokenService().login("  ")


if __name__ == "__main__":
    demonstration()
    unittest.main(argv=["refresh_tokens.py"], exit=False)
