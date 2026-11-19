from __future__ import annotations

import json
import logging
import time
import uuid
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Optional


# ============================================================
# MESSAGE QUEUE SYSTEM
# Producers, Consumers, Brokers, Acknowledgments, and Retries
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("message-queue")


class MessageStatus(str, Enum):
    READY = "READY"
    IN_FLIGHT = "IN_FLIGHT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RETRY_PENDING = "RETRY_PENDING"
    DEAD_LETTERED = "DEAD_LETTERED"


class QueueError(Exception):
    pass


class QueueCapacityError(QueueError):
    pass


class MessageNotFoundError(QueueError):
    pass


class InvalidAcknowledgmentError(QueueError):
    pass


class DuplicateMessageError(QueueError):
    pass


@dataclass
class Message:
    message_id: str
    payload: dict[str, Any]
    routing_key: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: MessageStatus = MessageStatus.READY
    attempts: int = 0
    max_attempts: int = 3
    available_at: float = field(default_factory=time.time)
    consumer_id: Optional[str] = None
    last_error: Optional[str] = None
    acknowledged_at: Optional[str] = None

    def __post_init__(self):
        if not self.message_id:
            raise ValueError("Message ID cannot be empty")
        if not isinstance(self.payload, dict):
            raise TypeError("Payload must be a dictionary")
        if not self.routing_key:
            raise ValueError("Routing key cannot be empty")
        if self.max_attempts < 1:
            raise ValueError("Maximum attempts must be positive")


@dataclass
class QueueMetrics:
    published: int = 0
    delivered: int = 0
    acknowledged: int = 0
    retried: int = 0
    rejected: int = 0
    dead_lettered: int = 0
    processing_failures: int = 0


class MessageQueue:
    """A bounded FIFO queue with retry scheduling."""

    def __init__(self, name: str, capacity: int = 1000):
        if not name:
            raise ValueError("Queue name is required")
        if capacity < 1:
            raise ValueError("Queue capacity must be positive")

        self.name = name
        self.capacity = capacity
        self.ready = deque()
        self.in_flight: dict[str, Message] = {}
        self.retry_waiting: list[Message] = []
        self.dead_letters: list[Message] = []
        self.completed: list[Message] = []
        self.lock = RLock()
        self.metrics = QueueMetrics()

    def size(self) -> int:
        with self.lock:
            return (
                len(self.ready)
                + len(self.in_flight)
                + len(self.retry_waiting)
            )

    def publish(self, message: Message) -> None:
        with self.lock:
            if self.size() >= self.capacity:
                self.metrics.rejected += 1
                raise QueueCapacityError(
                    f"Queue {self.name} has reached capacity"
                )

            if any(
                item.message_id == message.message_id
                for item in self.ready
            ) or message.message_id in self.in_flight:
                raise DuplicateMessageError(message.message_id)

            message.status = MessageStatus.READY
            self.ready.append(message)
            self.metrics.published += 1

            logger.info(
                "Published message %s to %s",
                message.message_id,
                self.name
            )

    def promote_retries(self) -> None:
        """Move messages whose retry delay has expired into the ready queue."""
        with self.lock:
            now = time.time()
            pending = []

            for message in self.retry_waiting:
                if message.available_at <= now:
                    message.status = MessageStatus.READY
                    self.ready.append(message)
                else:
                    pending.append(message)

            self.retry_waiting = pending

    def receive(self, consumer_id: str) -> Optional[Message]:
        if not consumer_id:
            raise ValueError("Consumer ID is required")

        with self.lock:
            self.promote_retries()

            if not self.ready:
                return None

            message = self.ready.popleft()
            message.status = MessageStatus.IN_FLIGHT
            message.consumer_id = consumer_id
            message.attempts += 1

            self.in_flight[message.message_id] = message
            self.metrics.delivered += 1

            logger.info(
                "Delivered %s to %s (attempt %d)",
                message.message_id,
                consumer_id,
                message.attempts
            )

            return message

    def acknowledge(
        self,
        message_id: str,
        consumer_id: str
    ) -> None:
        with self.lock:
            message = self.in_flight.get(message_id)

            if message is None:
                raise MessageNotFoundError(message_id)

            if message.consumer_id != consumer_id:
                raise InvalidAcknowledgmentError(
                    "Only the current consumer may acknowledge this message"
                )

            del self.in_flight[message_id]

            message.status = MessageStatus.ACKNOWLEDGED
            message.acknowledged_at = datetime.now(
                timezone.utc
            ).isoformat()

            self.completed.append(message)
            self.metrics.acknowledged += 1

            logger.info("Acknowledged %s", message_id)

    def reject(
        self,
        message_id: str,
        consumer_id: str,
        error: str,
        retry_delay: float = 1.0,
        requeue: bool = True
    ) -> None:
        if retry_delay < 0:
            raise ValueError("Retry delay cannot be negative")

        with self.lock:
            message = self.in_flight.get(message_id)

            if message is None:
                raise MessageNotFoundError(message_id)

            if message.consumer_id != consumer_id:
                raise InvalidAcknowledgmentError(
                    "Consumer does not own this message"
                )

            del self.in_flight[message_id]

            message.last_error = error
            message.consumer_id = None
            self.metrics.processing_failures += 1

            if requeue and message.attempts < message.max_attempts:
                message.status = MessageStatus.RETRY_PENDING
                message.available_at = time.time() + retry_delay
                self.retry_waiting.append(message)
                self.metrics.retried += 1

                logger.warning(
                    "Scheduled retry for %s after %.2f seconds",
                    message_id,
                    retry_delay
                )
            else:
                message.status = MessageStatus.DEAD_LETTERED
                self.dead_letters.append(message)
                self.metrics.dead_lettered += 1

                logger.error(
                    "Message %s moved to dead-letter queue",
                    message_id
                )

    def recover_expired(
        self,
        visibility_timeout: float
    ) -> int:
        """
        Recover messages whose consumer visibility period has expired.

        A production broker would persist delivery timestamps and perform
        this operation using a background scheduler.
        """
        if visibility_timeout <= 0:
            raise ValueError("Visibility timeout must be positive")

        recovered = 0
        now = time.time()

        with self.lock:
            expired = [
                message
                for message in self.in_flight.values()
                if now - message.available_at >= visibility_timeout
            ]

            for message in expired:
                del self.in_flight[message.message_id]
                message.consumer_id = None

                if message.attempts < message.max_attempts:
                    message.status = MessageStatus.RETRY_PENDING
                    message.available_at = now
                    self.retry_waiting.append(message)
                    self.metrics.retried += 1
                else:
                    message.status = MessageStatus.DEAD_LETTERED
                    self.dead_letters.append(message)
                    self.metrics.dead_lettered += 1

                recovered += 1

        return recovered

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "queue": self.name,
                "ready": len(self.ready),
                "in_flight": len(self.in_flight),
                "retry_waiting": len(self.retry_waiting),
                "completed": len(self.completed),
                "dead_letters": len(self.dead_letters),
                "metrics": asdict(self.metrics)
            }


class Broker:
    """Routes messages to named queues."""

    def __init__(self):
        self.queues: dict[str, MessageQueue] = {}
        self.lock = RLock()

    def declare_queue(
        self,
        name: str,
        capacity: int = 1000
    ) -> MessageQueue:
        with self.lock:
            if name in self.queues:
                return self.queues[name]

            queue = MessageQueue(name, capacity)
            self.queues[name] = queue
            return queue

    def get_queue(self, name: str) -> MessageQueue:
        try:
            return self.queues[name]
        except KeyError:
            raise QueueError(f"Queue does not exist: {name}")

    def publish(
        self,
        queue_name: str,
        payload: dict[str, Any],
        routing_key: str,
        message_id: Optional[str] = None,
        max_attempts: int = 3
    ) -> str:
        message = Message(
            message_id=message_id or str(uuid.uuid4()),
            payload=payload,
            routing_key=routing_key,
            max_attempts=max_attempts
        )

        self.get_queue(queue_name).publish(message)
        return message.message_id


class Producer:
    def __init__(self, producer_id: str, broker: Broker):
        self.producer_id = producer_id
        self.broker = broker

    def send(
        self,
        queue_name: str,
        payload: dict[str, Any],
        routing_key: str = "default"
    ) -> str:
        return self.broker.publish(
            queue_name,
            payload,
            routing_key
        )


class Consumer:
    def __init__(
        self,
        consumer_id: str,
        broker: Broker,
        queue_name: str,
        handler: Callable[[dict[str, Any]], None]
    ):
        self.consumer_id = consumer_id
        self.queue = broker.get_queue(queue_name)
        self.handler = handler

    def consume_one(self, retry_delay: float = 0.5) -> bool:
        message = self.queue.receive(self.consumer_id)

        if message is None:
            return False

        try:
            self.handler(message.payload)

            # Acknowledge only after successful processing.
            self.queue.acknowledge(
                message.message_id,
                self.consumer_id
            )

        except Exception as exc:
            self.queue.reject(
                message.message_id,
                self.consumer_id,
                error=str(exc),
                retry_delay=retry_delay
            )

        return True


class IdempotentPaymentHandler:
    """
    Demonstrates application-level idempotency.

    Message delivery can occur more than once. The business operation
    therefore tracks processed transaction identifiers.
    """

    def __init__(self):
        self.processed_transactions: set[str] = set()
        self.total_processed = 0

    def __call__(self, payload: dict[str, Any]) -> None:
        transaction_id = payload.get("transaction_id")
        amount = payload.get("amount")

        if not transaction_id:
            raise ValueError("Missing transaction_id")

        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Invalid transaction amount")

        if transaction_id in self.processed_transactions:
            logger.info(
                "Duplicate business operation ignored: %s",
                transaction_id
            )
            return

        self.processed_transactions.add(transaction_id)
        self.total_processed += 1

        logger.info(
            "Payment processed: %s, amount=%s",
            transaction_id,
            amount
        )


def export_metrics(
    queues: list[MessageQueue],
    filename: str = "queue_metrics.json"
) -> None:
    """Write operational metrics without exposing message payloads."""
    report = [queue.snapshot() for queue in queues]

    Path(filename).write_text(
        json.dumps(report, indent=4),
        encoding="utf-8"
    )


def demonstrate_queue_system() -> None:
    broker = Broker()
    broker.declare_queue("payments", capacity=100)

    producer = Producer("payment-service", broker)
    handler = IdempotentPaymentHandler()

    consumer = Consumer(
        "payment-worker-01",
        broker,
        "payments",
        handler
    )

    producer.send(
        "payments",
        {
            "transaction_id": "TXN-1001",
            "amount": 2500
        },
        "payment.created"
    )

    producer.send(
        "payments",
        {
            "transaction_id": "TXN-1002",
            "amount": 5000
        },
        "payment.created"
    )

    # Invalid message demonstrates retry and dead-letter behavior.
    producer.send(
        "payments",
        {
            "transaction_id": "TXN-1003",
            "amount": -100
        },
        "payment.created"
    )

    queue = broker.get_queue("payments")

    # First successful processing.
    consumer.consume_one()

    # Second successful processing.
    consumer.consume_one()

    # Invalid message is retried until maximum attempts are exhausted.
    consumer.consume_one(retry_delay=0)
    consumer.consume_one(retry_delay=0)
    consumer.consume_one(retry_delay=0)

    print("\nQUEUE SNAPSHOT")
    print(json.dumps(queue.snapshot(), indent=4))

    print("\nPROCESSED BUSINESS TRANSACTIONS")
    print(handler.total_processed)

    print("\nDEAD LETTER MESSAGES")
    for message in queue.dead_letters:
        print(
            message.message_id,
            message.payload,
            message.last_error
        )

    export_metrics([queue])


def demonstrate_capacity_limit() -> None:
    queue = MessageQueue("limited", capacity=1)

    queue.publish(
        Message(
            "M-001",
            {"value": 1},
            "test"
        )
    )

    try:
        queue.publish(
            Message(
                "M-002",
                {"value": 2},
                "test"
            )
        )
    except QueueCapacityError as exc:
        print(f"Capacity protection: {exc}")


def demonstrate_invalid_acknowledgment() -> None:
    queue = MessageQueue("ack-test")

    queue.publish(
        Message(
            "M-ACK",
            {"value": 10},
            "test"
        )
    )

    queue.receive("worker-A")

    try:
        queue.acknowledge("M-ACK", "worker-B")
    except InvalidAcknowledgmentError as exc:
        print(f"Ownership validation: {exc}")

    queue.acknowledge("M-ACK", "worker-A")


if __name__ == "__main__":
    demonstrate_queue_system()
    demonstrate_capacity_limit()
    demonstrate_invalid_acknowledgment()
