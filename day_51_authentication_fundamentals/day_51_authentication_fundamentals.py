from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import pbkdf2_hmac, sha256
import base64
import hmac
import secrets
import time
from typing import Dict, Optional, Set, Tuple


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class AccountStatus(Enum):
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


class SessionStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PasswordRecord:
    algorithm: str
    salt: bytes
    digest: bytes
    iterations: int


@dataclass
class User:
    user_id: int
    username: str
    password: PasswordRecord
    roles: Set[str] = field(default_factory=set)
    status: AccountStatus = AccountStatus.ACTIVE
    failed_attempts: int = 0


@dataclass
class Session:
    session_id: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    status: SessionStatus = SessionStatus.ACTIVE


class PasswordHasher:
    ALGORITHM = "PBKDF2-HMAC-SHA256"
    ITERATIONS = 210_000

    @classmethod
    def hash_password(cls, password: str) -> PasswordRecord:
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError("Password must contain at least 12 characters.")

        salt = secrets.token_bytes(16)
        digest = pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
        )
        return PasswordRecord(
            cls.ALGORITHM,
            salt,
            digest,
            cls.ITERATIONS,
        )

    @classmethod
    def verify(cls, password: str, record: PasswordRecord) -> bool:
        candidate = pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            record.salt,
            record.iterations,
        )
        return hmac.compare_digest(candidate, record.digest)


class AuthenticationService:
    def __init__(self, session_minutes: int = 30, max_failures: int = 5):
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.next_user_id = 1
        self.session_minutes = session_minutes
        self.max_failures = max_failures

    def register(
        self,
        username: str,
        password: str,
        roles: Optional[Set[str]] = None,
    ) -> User:
        normalized = username.strip().lower()

        if not normalized:
            raise ValueError("Username cannot be empty.")

        if normalized in self.users:
            raise ValueError("Username already exists.")

        user = User(
            user_id=self.next_user_id,
            username=normalized,
            password=PasswordHasher.hash_password(password),
            roles=set(roles or set()),
        )
        self.users[normalized] = user
        self.next_user_id += 1
        return user

    def authenticate(self, username: str, password: str) -> Session:
        normalized = username.strip().lower()
        user = self.users.get(normalized)

        if user is None:
            # Avoid revealing whether an account exists to callers.
            raise AuthenticationError("Invalid credentials.")

        if user.status != AccountStatus.ACTIVE:
            raise AuthenticationError("Account is not active.")

        if not PasswordHasher.verify(password, user.password):
            user.failed_attempts += 1

            if user.failed_attempts >= self.max_failures:
                user.status = AccountStatus.LOCKED

            raise AuthenticationError("Invalid credentials.")

        user.failed_attempts = 0

        now = datetime.now(timezone.utc)
        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user.user_id,
            created_at=now,
            expires_at=now + timedelta(minutes=self.session_minutes),
        )
        self.sessions[session.session_id] = session
        return session

    def get_user_from_session(self, session_id: str) -> User:
        session = self.sessions.get(session_id)

        if session is None:
            raise AuthenticationError("Invalid session.")

        if session.status != SessionStatus.ACTIVE:
            raise AuthenticationError("Session is not active.")

        now = datetime.now(timezone.utc)

        if now >= session.expires_at:
            session.status = SessionStatus.EXPIRED
            raise AuthenticationError("Session has expired.")

        for user in self.users.values():
            if user.user_id == session.user_id:
                if user.status != AccountStatus.ACTIVE:
                    raise AuthenticationError("Account is not active.")
                return user

        raise AuthenticationError("Session references an unknown user.")

    def logout(self, session_id: str) -> None:
        session = self.sessions.get(session_id)

        if session is not None:
            session.status = SessionStatus.REVOKED

    def authorize(self, session_id: str, required_role: str) -> User:
        user = self.get_user_from_session(session_id)

        if required_role not in user.roles:
            raise AuthorizationError(
                f"Role '{required_role}' is required."
            )

        return user


class CredentialStore:
    """
    Demonstrates why plaintext credentials should not be stored.
    A password-derived verifier is stored instead.
    """

    def __init__(self):
        self.records: Dict[str, PasswordRecord] = {}

    def add(self, username: str, password: str) -> None:
        self.records[username] = PasswordHasher.hash_password(password)

    def verify(self, username: str, password: str) -> bool:
        record = self.records.get(username)
        return record is not None and PasswordHasher.verify(password, record)


def demonstrate_authentication(service: AuthenticationService) -> None:
    print("\n=== Identity and Credential Verification ===")

    alice = service.register(
        "Alice",
        "CorrectHorseBattery9!",
        {"user"},
    )
    print(f"Created identity: {alice.username}")

    session = service.authenticate(
        "alice",
        "CorrectHorseBattery9!",
    )

    print("Authentication succeeded.")
    print(f"Session issued: {session.session_id[:12]}...")

    authenticated_user = service.get_user_from_session(session.session_id)
    print(f"Authenticated identity: {authenticated_user.username}")


def demonstrate_authorization(service: AuthenticationService, session_id: str) -> None:
    print("\n=== Authentication vs Authorization ===")

    try:
        service.authorize(session_id, "administrator")
    except AuthorizationError as exc:
        print(f"Authentication succeeded, authorization failed: {exc}")

    service.users["alice"].roles.add("administrator")
    authorized_user = service.authorize(session_id, "administrator")
    print(f"Authorization succeeded for: {authorized_user.username}")


def demonstrate_lockout(service: AuthenticationService) -> None:
    print("\n=== Failed Authentication and Account Lockout ===")

    service.register(
        "locked-user",
        "VeryStrongPassword9!",
        {"user"},
    )

    for attempt in range(1, 6):
        try:
            service.authenticate("locked-user", "wrong-password")
        except AuthenticationError as exc:
            print(f"Attempt {attempt}: {exc}")

    print(
        "Account status:",
        service.users["locked-user"].status.value,
    )


def demonstrate_expiration() -> None:
    print("\n=== Session Expiration ===")

    service = AuthenticationService(session_minutes=1)
    service.register("temporary", "TemporaryPassword9!", {"user"})
    session = service.authenticate("temporary", "TemporaryPassword9!")

    # Simulate an expired session without waiting for real time.
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    try:
        service.get_user_from_session(session.session_id)
    except AuthenticationError as exc:
        print(f"Expired session rejected: {exc}")


def demonstrate_password_verifier() -> None:
    print("\n=== Credential Storage ===")

    store = CredentialStore()
    store.add("alice", "CorrectHorseBattery9!")

    print("Correct password:", store.verify("alice", "CorrectHorseBattery9!"))
    print("Incorrect password:", store.verify("alice", "wrong-password"))

    stored = store.records["alice"]
    print("Stored algorithm:", stored.algorithm)
    print("Stored value is a salted password-derived verifier.")
    print("Plaintext password is not stored.")


def main() -> None:
    service = AuthenticationService(
        session_minutes=30,
        max_failures=5,
    )

    demonstrate_authentication(service)

    alice_session = next(
        session
        for session in service.sessions.values()
        if session.user_id == service.users["alice"].user_id
    )

    demonstrate_authorization(service, alice_session.session_id)
    demonstrate_lockout(service)
    demonstrate_expiration()
    demonstrate_password_verifier()

    service.logout(alice_session.session_id)

    try:
        service.get_user_from_session(alice_session.session_id)
    except AuthenticationError as exc:
        print("\nRevoked session rejected:", exc)


if __name__ == "__main__":
    main()
