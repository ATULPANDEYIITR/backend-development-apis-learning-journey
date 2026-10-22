import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordRecord:
    algorithm: str
    salt: str
    digest: str
    iterations: int
    key_length: int


class PasswordSecurity:
    """
    Password storage model using PBKDF2-HMAC-SHA256.

    The password is never stored directly. A unique random salt is generated
    for every password, and the password-derived key is stored instead.
    """

    ALGORITHM = "PBKDF2-HMAC-SHA256"
    ITERATIONS = 600_000
    SALT_LENGTH = 16
    KEY_LENGTH = 32
    MAX_PASSWORD_LENGTH = 1024

    @classmethod
    def validate_password(cls, password: str) -> None:
        if not isinstance(password, str):
            raise TypeError("Password must be a string.")

        if not password:
            raise ValueError("Password cannot be empty.")

        if len(password) > cls.MAX_PASSWORD_LENGTH:
            raise ValueError("Password exceeds the maximum supported length.")

    @classmethod
    def hash_password(cls, password: str) -> PasswordRecord:
        cls.validate_password(password)

        salt = secrets.token_bytes(cls.SALT_LENGTH)

        derived_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
            dklen=cls.KEY_LENGTH,
        )

        return PasswordRecord(
            algorithm=cls.ALGORITHM,
            salt=base64.b64encode(salt).decode("ascii"),
            digest=base64.b64encode(derived_key).decode("ascii"),
            iterations=cls.ITERATIONS,
            key_length=cls.KEY_LENGTH,
        )

    @classmethod
    def verify_password(
        cls,
        password: str,
        record: PasswordRecord,
    ) -> bool:
        try:
            cls.validate_password(password)

            if record.algorithm != cls.ALGORITHM:
                return False

            salt = base64.b64decode(record.salt, validate=True)
            expected = base64.b64decode(record.digest, validate=True)

            if len(salt) < 16:
                return False

            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                record.iterations,
                dklen=record.key_length,
            )

            # Constant-time comparison reduces timing leakage.
            return hmac.compare_digest(actual, expected)

        except (ValueError, TypeError):
            return False

    @classmethod
    def needs_rehash(cls, record: PasswordRecord) -> bool:
        return (
            record.algorithm != cls.ALGORITHM
            or record.iterations < cls.ITERATIONS
            or record.key_length != cls.KEY_LENGTH
        )


def demonstrate_brute_force_resistance() -> None:
    """
    Demonstrates why a password database should contain derived keys rather
    than plaintext passwords. PBKDF2 intentionally makes each guess costly.
    """

    common_passwords = [
        "password",
        "123456",
        "qwerty",
        "letmein",
        "CorrectHorseBatteryStaple!2026",
    ]

    record = PasswordSecurity.hash_password(
        "CorrectHorseBatteryStaple!2026"
    )

    print("Stored password record:")
    print(f"  algorithm : {record.algorithm}")
    print(f"  salt      : {record.salt}")
    print(f"  digest    : {record.digest}")
    print(f"  iterations: {record.iterations}")
    print(f"  key length: {record.key_length}")

    print("\nAuthentication attempts:")

    for candidate in common_passwords:
        accepted = PasswordSecurity.verify_password(candidate, record)
        print(f"  {candidate!r:35} -> {'accepted' if accepted else 'rejected'}")

    print("\nRehash required:", PasswordSecurity.needs_rehash(record))


def demonstrate_unique_salts() -> None:
    password = "same-password"

    first = PasswordSecurity.hash_password(password)
    second = PasswordSecurity.hash_password(password)

    print("\nUnique salt demonstration:")
    print("  Same password:", password)
    print("  First salt:   ", first.salt)
    print("  Second salt:  ", second.salt)
    print("  Salts differ: ", first.salt != second.salt)
    print("  Digests differ:", first.digest != second.digest)


def main() -> None:
    demonstrate_brute_force_resistance()
    demonstrate_unique_salts()

    print("\nValidation and failure cases:")

    for invalid_password in ["", None]:
        try:
            PasswordSecurity.hash_password(invalid_password)
        except (ValueError, TypeError) as exc:
            print(f"  Invalid password rejected: {exc}")

    record = PasswordSecurity.hash_password("ProductionPassword!2026")

    print(
        "  Correct password:",
        PasswordSecurity.verify_password("ProductionPassword!2026", record),
    )
    print(
        "  Incorrect password:",
        PasswordSecurity.verify_password("ProductionPassword!2025", record),
    )


if __name__ == "__main__":
    main()
