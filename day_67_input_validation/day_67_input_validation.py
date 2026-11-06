#!/usr/bin/env python3
"""
Input Validation: Schema validation, sanitization, boundary validation,
malicious input detection, and secure request processing.

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)
logger = logging.getLogger("input_validation")


class ValidationCategory(Enum):
    REQUIRED = "required"
    TYPE = "type"
    FORMAT = "format"
    BOUNDARY = "boundary"
    SECURITY = "security"
    UNKNOWN_FIELD = "unknown_field"


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    category: ValidationCategory
    message: str


class InputValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__(
            "; ".join(f"{i.field}: {i.message}" for i in issues)
        )


@dataclass(frozen=True)
class FieldSchema:
    expected_type: type | tuple[type, ...]
    required: bool = True
    minimum: int | float | None = None
    maximum: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    allowed_values: set[Any] | None = None
    sanitize: bool = False
    validator: Callable[[Any], bool] | None = None


@dataclass
class ValidationResult:
    valid: bool
    sanitized_data: dict[str, Any] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)


class InputSanitizer:
    """Normalize text and remove unsafe control characters."""

    @staticmethod
    def normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFC", value)

        # Remove control characters except ordinary whitespace.
        normalized = "".join(
            char for char in normalized
            if char in "\t\n\r" or unicodedata.category(char) != "Cc"
        )

        return normalized.strip()

    @staticmethod
    def sanitize_html_text(value: str) -> str:
        """
        Escape HTML metacharacters for safe text output.
        This is not a replacement for context-aware output encoding.
        """
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
        }

        return "".join(replacements.get(char, char) for char in value)

    @staticmethod
    def detect_suspicious_input(value: str) -> list[str]:
        patterns = {
            "SQL injection indicator": r"(?i)(\bUNION\s+SELECT\b|\bDROP\s+TABLE\b|--\s|;\s*DELETE\b)",
            "Script injection indicator": r"(?i)<\s*script\b|javascript\s*:",
            "Path traversal indicator": r"\.\.[/\\]",
            "Null byte": r"\x00",
            "Command substitution indicator": r"\$\([^)]*\)|`[^`]*`",
        }

        return [
            name for name, pattern in patterns.items()
            if re.search(pattern, value)
        ]


class SchemaValidator:
    def __init__(
        self,
        schema: dict[str, FieldSchema],
        reject_unknown_fields: bool = True,
    ):
        self.schema = schema
        self.reject_unknown_fields = reject_unknown_fields

    def validate(self, payload: Any) -> ValidationResult:
        issues: list[ValidationIssue] = []
        sanitized: dict[str, Any] = {}

        if not isinstance(payload, dict):
            return ValidationResult(
                False,
                issues=[
                    ValidationIssue(
                        "$",
                        ValidationCategory.TYPE,
                        "Request body must be a JSON object."
                    )
                ]
            )

        if self.reject_unknown_fields:
            for key in payload:
                if key not in self.schema:
                    issues.append(
                        ValidationIssue(
                            str(key),
                            ValidationCategory.UNKNOWN_FIELD,
                            "Unknown field is not permitted."
                        )
                    )

        for name, rules in self.schema.items():
            if name not in payload:
                if rules.required:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.REQUIRED,
                            "Field is required."
                        )
                    )
                continue

            value = payload[name]

            # Prevent bool from passing integer validation in Python.
            if rules.expected_type is int and isinstance(value, bool):
                type_valid = False
            elif isinstance(rules.expected_type, tuple) and int in rules.expected_type:
                type_valid = isinstance(value, rules.expected_type) and not (
                    isinstance(value, bool)
                    and rules.expected_type == (int, float)
                )
            else:
                type_valid = isinstance(value, rules.expected_type)

            if not type_valid:
                issues.append(
                    ValidationIssue(
                        name,
                        ValidationCategory.TYPE,
                        "Value has an incorrect data type."
                    )
                )
                continue

            if isinstance(value, float) and not math.isfinite(value):
                issues.append(
                    ValidationIssue(
                        name,
                        ValidationCategory.FORMAT,
                        "Non-finite numeric values are not permitted."
                    )
                )
                continue

            if isinstance(value, str) and rules.sanitize:
                value = InputSanitizer.normalize_text(value)

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if rules.minimum is not None and value < rules.minimum:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.BOUNDARY,
                            f"Value must be at least {rules.minimum}."
                        )
                    )

                if rules.maximum is not None and value > rules.maximum:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.BOUNDARY,
                            f"Value must not exceed {rules.maximum}."
                        )
                    )

            if isinstance(value, str):
                if rules.min_length is not None and len(value) < rules.min_length:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.BOUNDARY,
                            f"Minimum length is {rules.min_length}."
                        )
                    )

                if rules.max_length is not None and len(value) > rules.max_length:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.BOUNDARY,
                            f"Maximum length is {rules.max_length}."
                        )
                    )

                if rules.pattern and not re.fullmatch(rules.pattern, value):
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.FORMAT,
                            "Value does not match the required format."
                        )
                    )

                suspicious = InputSanitizer.detect_suspicious_input(value)

                if suspicious:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.SECURITY,
                            "Potentially malicious input detected: "
                            + ", ".join(suspicious)
                        )
                    )

            if rules.allowed_values is not None:
                if value not in rules.allowed_values:
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.FORMAT,
                            "Value is not in the permitted set."
                        )
                    )

            if rules.validator is not None:
                try:
                    if not rules.validator(value):
                        issues.append(
                            ValidationIssue(
                                name,
                                ValidationCategory.FORMAT,
                                "Custom validation failed."
                            )
                        )
                except (ValueError, TypeError, OverflowError):
                    issues.append(
                        ValidationIssue(
                            name,
                            ValidationCategory.FORMAT,
                            "Custom validation could not process the value."
                        )
                    )

            sanitized[name] = value

        return ValidationResult(
            valid=not issues,
            sanitized_data=sanitized if not issues else {},
            issues=issues,
        )


def valid_email(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",
            value
        )
    )


def valid_username(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,19}", value))


def valid_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


class RequestProcessor:
    """Simulates a secure registration API."""

    def __init__(self):
        self.schema = SchemaValidator({
            "username": FieldSchema(
                str,
                min_length=3,
                max_length=20,
                pattern=r"[A-Za-z][A-Za-z0-9_]*",
                sanitize=True,
                validator=valid_username,
            ),
            "email": FieldSchema(
                str,
                min_length=6,
                max_length=254,
                sanitize=True,
                validator=valid_email,
            ),
            "age": FieldSchema(
                int,
                minimum=18,
                maximum=120,
            ),
            "role": FieldSchema(
                str,
                allowed_values={"user", "analyst", "administrator"},
            ),
            "registration_date": FieldSchema(
                str,
                pattern=r"\d{4}-\d{2}-\d{2}",
                validator=valid_iso_date,
            ),
            "active": FieldSchema(bool),
            "phone": FieldSchema(
                str,
                required=False,
                min_length=10,
                max_length=15,
                pattern=r"\+?[0-9]+",
            ),
        })

        self.registered_users: dict[str, dict[str, Any]] = {}

    def process(self, raw_body: str) -> dict[str, Any]:
        if not isinstance(raw_body, str):
            raise ValueError("Request body must be text.")

        if len(raw_body.encode("utf-8")) > 16_384:
            raise ValueError("Request body exceeds the 16 KB limit.")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed JSON request.") from exc

        result = self.schema.validate(payload)

        if not result.valid:
            raise InputValidationError(result.issues)

        username = result.sanitized_data["username"]

        if username in self.registered_users:
            raise ValueError("Username already exists.")

        # Store only validated values.
        record = {
            **result.sanitized_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.registered_users[username] = record

        return {
            "status": "accepted",
            "user": record,
        }


def print_result(title: str, operation: Callable[[], Any]) -> None:
    print(f"\n--- {title} ---")

    try:
        print(json.dumps(operation(), indent=2))
    except InputValidationError as exc:
        for issue in exc.issues:
            print(
                f"[{issue.category.value.upper()}] "
                f"{issue.field}: {issue.message}"
            )
    except (ValueError, TypeError) as exc:
        print(f"[REJECTED] {exc}")


def run_tests() -> None:
    validator = SchemaValidator({
        "quantity": FieldSchema(int, minimum=1, maximum=100),
        "description": FieldSchema(
            str,
            min_length=3,
            max_length=100,
            sanitize=True,
        ),
    })

    assert validator.validate({
        "quantity": 10,
        "description": "  Secure input  ",
    }).valid

    assert not validator.validate({
        "quantity": 0,
        "description": "Valid",
    }).valid

    assert not validator.validate({
        "quantity": True,
        "description": "Valid",
    }).valid

    assert not validator.validate({
        "quantity": 10,
        "description": "<script>alert(1)</script>",
    }).valid

    assert not validator.validate({
        "quantity": 10,
        "description": "Valid",
        "unexpected": "value",
    }).valid

    assert not validator.validate({
        "quantity": 10.5,
        "description": "Valid",
    }).valid

    assert not validator.validate(None).valid

    assert InputSanitizer.normalize_text("  Hello  ") == "Hello"

    assert "&lt;script&gt;" == InputSanitizer.sanitize_html_text(
        "<script>"
    )

    print("\nAll automated assertions passed.")


def main() -> None:
    processor = RequestProcessor()

    valid_request = {
        "username": "secure_user",
        "email": "user@example.com",
        "age": 25,
        "role": "analyst",
        "registration_date": "2026-11-06",
        "active": True,
        "phone": "+919876543210",
    }

    print_result(
        "Valid registration",
        lambda: processor.process(json.dumps(valid_request))
    )

    invalid_requests = [
        (
            "Boundary violation",
            {
                **valid_request,
                "age": 15,
                "username": "young_user",
            }
        ),
        (
            "Wrong data type",
            {
                **valid_request,
                "age": "twenty-five",
                "username": "typed_user",
            }
        ),
        (
            "Malicious SQL input",
            {
                **valid_request,
                "username": "sql_user",
                "email": "x@example.com",
                "role": "user",
                "registration_date": "2026-11-06",
                "description": "' UNION SELECT * FROM users --",
            }
        ),
        (
            "Unknown field",
            {
                **valid_request,
                "username": "extra_user",
                "is_admin": True,
            }
        ),
        (
            "Invalid email",
            {
                **valid_request,
                "username": "bad_email",
                "email": "not-an-email",
            }
        ),
    ]

    for title, payload in invalid_requests:
        print_result(
            title,
            lambda p=payload: processor.process(json.dumps(p))
        )

    print_result(
        "Malformed JSON",
        lambda: processor.process('{"username":')
    )

    print_result(
        "Oversized request",
        lambda: processor.process(' ' * 16_385)
    )

    print_result(
        "Duplicate username",
        lambda: processor.process(json.dumps(valid_request))
    )

    print_result(
        "Security output encoding",
        lambda: {
            "escaped": InputSanitizer.sanitize_html_text(
                '<img src=x onerror="alert(1)">'
            )
        }
    )

    run_tests()


if __name__ == "__main__":
    main()
