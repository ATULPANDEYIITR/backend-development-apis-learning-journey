#!/usr/bin/env python3
"""
Idempotency Engineering: Safe API Retries and Payment Workflows

Demonstrates:
- Idempotency keys and request fingerprinting.
- Duplicate request detection.
- Concurrent request protection.
- Payment state transitions.
- Cached responses and retry behavior.
- Key expiration and validation.
- Failure handling and transactional simulation.

Run: python idempotency.py
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class PaymentStatus(str, Enum):
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class IdempotencyError(Exception):
    pass


class InvalidRequest(IdempotencyError):
    pass


class KeyConflict(IdempotencyError):
    pass


class RequestInProgress(IdempotencyError):
    pass


class KeyExpired(IdempotencyError):
    pass


@dataclass(frozen=True)
class PaymentRequest:
    customer_id: str
    amount: int
    currency: str
    payment_method: str

    def validate(self) -> None:
        if not self.customer_id.strip():
            raise InvalidRequest("Customer ID is required.")

        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise InvalidRequest("Amount must be an integer in minor units.")

        if self.amount <= 0 or self.amount > 100_000_000:
            raise InvalidRequest("Amount is outside the permitted range.")

        if not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise InvalidRequest("Currency must be a three-letter uppercase code.")

        if not self.payment_method.strip():
            raise InvalidRequest("Payment method is required.")

    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "customer_id": self.customer_id,
                "amount": self.amount,
                "currency": self.currency,
                "payment_method": self.payment_method,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class Payment:
    payment_id: str
    customer_id: str
    amount: int
    currency: str
    status: PaymentStatus
    created_at: datetime
    failure_reason: str | None = None


@dataclass
class IdempotencyRecord:
    key: str
    fingerprint: str
    status: PaymentStatus
    response: dict[str, Any] | None
    expires_at: datetime
    created_at: datetime
    payment_id: str | None = None


class PaymentProcessor:
    """
    In-memory reference implementation.

    A single lock protects the idempotency registry and payment state.
    Production systems should use database transactions and unique
    constraints rather than relying on process-local synchronization.
    """

    def __init__(self, retention_hours: int = 24):
        if retention_hours <= 0:
            raise ValueError("Retention must be positive.")

        self.retention = timedelta(hours=retention_hours)
        self.records: dict[str, IdempotencyRecord] = {}
        self.payments: dict[str, Payment] = {}
        self.lock = threading.RLock()
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def validate_key(key: str) -> None:
        if not isinstance(key, str):
            raise InvalidRequest("Idempotency key must be a string.")

        if not 16 <= len(key) <= 128:
            raise InvalidRequest("Key length must be between 16 and 128.")

        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise InvalidRequest("Key contains unsupported characters.")

    def _record_event(self, event: str, key: str, payment_id: str | None):
        self.events.append({
            "event": event,
            "key_hash": hashlib.sha256(key.encode()).hexdigest()[:16],
            "payment_id": payment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def create_payment(
        self,
        key: str,
        request: PaymentRequest,
        simulate_failure: bool = False,
    ) -> dict[str, Any]:

        self.validate_key(key)
        request.validate()

        fingerprint = request.fingerprint()
        now = datetime.now(timezone.utc)

        with self.lock:

            existing = self.records.get(key)

            if existing:
                if existing.fingerprint != fingerprint:
                    raise KeyConflict(
                        "The same idempotency key was used with a different request."
                    )

                if existing.expires_at <= now:
                    raise KeyExpired(
                        "Idempotency key has expired. Reconcile before creating a new operation."
                    )

                if existing.status == PaymentStatus.PROCESSING:
                    raise RequestInProgress("Payment is still processing.")

                self._record_event("REPLAY", key, existing.payment_id)

                return {
                    **existing.response,
                    "idempotent_replay": True,
                }

            payment_id = str(uuid.uuid4())

            payment = Payment(
                payment_id=payment_id,
                customer_id=request.customer_id,
                amount=request.amount,
                currency=request.currency,
                status=PaymentStatus.PROCESSING,
                created_at=now,
            )

            record = IdempotencyRecord(
                key=key,
                fingerprint=fingerprint,
                status=PaymentStatus.PROCESSING,
                response=None,
                expires_at=now + self.retention,
                created_at=now,
                payment_id=payment_id,
            )

            # Reserve the key before executing the operation.
            self.records[key] = record
            self.payments[payment_id] = payment

            self._record_event("PAYMENT_RESERVED", key, payment_id)

            try:
                # Simulates a payment gateway response.
                if simulate_failure:
                    raise RuntimeError("Payment gateway declined the operation.")

                payment.status = PaymentStatus.SUCCEEDED

                response = {
                    "payment_id": payment_id,
                    "customer_id": request.customer_id,
                    "amount": request.amount,
                    "currency": request.currency,
                    "status": PaymentStatus.SUCCEEDED.value,
                    "idempotent_replay": False,
                }

                record.status = PaymentStatus.SUCCEEDED
                record.response = response

                self._record_event("PAYMENT_SUCCEEDED", key, payment_id)

                return response

            except Exception as exc:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = str(exc)

                response = {
                    "payment_id": payment_id,
                    "customer_id": request.customer_id,
                    "amount": request.amount,
                    "currency": request.currency,
                    "status": PaymentStatus.FAILED.value,
                    "error": "PAYMENT_FAILED",
                    "idempotent_replay": False,
                }

                record.status = PaymentStatus.FAILED
                record.response = response

                self._record_event("PAYMENT_FAILED", key, payment_id)

                return response

    def get_payment(self, payment_id: str) -> Payment | None:
        with self.lock:
            return self.payments.get(payment_id)

    def cleanup_expired(self) -> int:
        """
        Remove expired terminal records.

        Processing records are retained for reconciliation.
        A real system must not blindly delete records while a
        payment provider may still be processing the operation.
        """
        now = datetime.now(timezone.utc)

        with self.lock:
            expired = [
                key
                for key, record in self.records.items()
                if record.expires_at <= now
                and record.status != PaymentStatus.PROCESSING
            ]

            for key in expired:
                del self.records[key]

            return len(expired)

    def report(self) -> dict[str, int]:
        with self.lock:
            counts = {status.value: 0 for status in PaymentStatus}

            for payment in self.payments.values():
                counts[payment.status.value] += 1

            return counts


def run_tests() -> None:
    processor = PaymentProcessor()

    request = PaymentRequest(
        customer_id="CUSTOMER-1001",
        amount=12500,
        currency="INR",
        payment_method="CARD-TOKEN-001",
    )

    key = "payment_request_100001"

    # First request creates the payment.
    first = processor.create_payment(key, request)

    assert first["status"] == "SUCCEEDED"
    assert first["idempotent_replay"] is False

    # Retry returns the original result.
    second = processor.create_payment(key, request)

    assert second["payment_id"] == first["payment_id"]
    assert second["idempotent_replay"] is True

    # Same key with a different payload must fail.
    modified = PaymentRequest(
        customer_id="CUSTOMER-1001",
        amount=20000,
        currency="INR",
        payment_method="CARD-TOKEN-001",
    )

    try:
        processor.create_payment(key, modified)
        raise AssertionError("Expected key conflict.")
    except KeyConflict:
        pass

    # A failed payment is also recorded and replayed.
    failed = processor.create_payment(
        "payment_request_100002",
        request,
        simulate_failure=True,
    )

    assert failed["status"] == "FAILED"

    failed_retry = processor.create_payment(
        "payment_request_100002",
        request,
    )

    assert failed_retry["payment_id"] == failed["payment_id"]
    assert failed_retry["status"] == "FAILED"

    # Invalid amounts are rejected before reservation.
    try:
        invalid = PaymentRequest(
            customer_id="CUSTOMER-1001",
            amount=-100,
            currency="INR",
            payment_method="CARD-TOKEN-001",
        )
        processor.create_payment("payment_request_100003", invalid)
        raise AssertionError("Expected validation failure.")
    except InvalidRequest:
        pass

    print("All idempotency tests passed.")
    print("\nPayment report:")

    for status, count in processor.report().items():
        print(f"{status}: {count}")

    print("\nRecorded events:")

    for event in processor.events:
        print(json.dumps(event, indent=2))


if __name__ == "__main__":
    run_tests()
