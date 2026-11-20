from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable


# ============================================================
# EVENT-DRIVEN ARCHITECTURE
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("event_architecture")


class EventError(Exception):
    """Base exception for event-processing failures."""


class SchemaValidationError(EventError):
    pass


class DuplicateEventError(EventError):
    pass


class ConsumerError(EventError):
    pass


class EventStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    CONSUMED = "CONSUMED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True)
class EventSchema:
    name: str
    version: int
    required_fields: dict[str, type]
    optional_fields: dict[str, type] = field(default_factory=dict)

    def validate(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise SchemaValidationError("Payload must be an object")

        for key, expected_type in self.required_fields.items():
            if key not in payload:
                raise SchemaValidationError(
                    f"Missing required field: {key}"
                )

            value = payload[key]

            # bool is a subclass of int in Python.
            if expected_type is int and isinstance(value, bool):
                raise SchemaValidationError(
                    f"Invalid type for {key}: expected integer"
                )

            if not isinstance(value, expected_type):
                raise SchemaValidationError(
                    f"Invalid type for {key}: expected "
                    f"{expected_type.__name__}"
                )

        allowed = set(self.required_fields) | set(
            self.optional_fields
        )

        unknown = set(payload) - allowed

        if unknown:
            raise SchemaValidationError(
                f"Unknown fields: {sorted(unknown)}"
            )

        for key, expected_type in self.optional_fields.items():
            if key in payload and not isinstance(
                payload[key], expected_type
            ):
                raise SchemaValidationError(
                    f"Invalid optional field: {key}"
                )


@dataclass
class Event:
    event_id: str
    event_type: str
    version: int
    producer: str
    payload: dict[str, Any]
    occurred_at: str
    correlation_id: str
    status: EventStatus = EventStatus.PENDING
    attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass
class Delivery:
    event: Event
    consumer: str
    attempts: int = 0
    last_error: str | None = None


# ============================================================
# SCHEMA REGISTRY
# ============================================================

class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[tuple[str, int], EventSchema] = {}

    def register(self, schema: EventSchema) -> None:
        key = (schema.name, schema.version)

        if key in self._schemas:
            raise EventError(f"Schema already registered: {key}")

        self._schemas[key] = schema

    def validate(
        self,
        event_type: str,
        version: int,
        payload: dict[str, Any]
    ) -> None:
        schema = self._schemas.get((event_type, version))

        if schema is None:
            raise SchemaValidationError(
                f"Unknown schema: {event_type} v{version}"
            )

        schema.validate(payload)


# ============================================================
# EVENT BROKER
# ============================================================

class EventBroker:
    def __init__(
        self,
        registry: SchemaRegistry,
        max_retries: int = 3
    ):
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.registry = registry
        self.max_retries = max_retries

        self.events: dict[str, Event] = {}
        self.subscriptions: dict[
            str, list[tuple[str, Callable[[Event], None]]]
        ] = defaultdict(list)

        self.processed: set[tuple[str, str]] = set()
        self.dead_letters: deque[Delivery] = deque()

        self._lock = threading.RLock()

    def subscribe(
        self,
        event_type: str,
        consumer_name: str,
        handler: Callable[[Event], None]
    ) -> None:
        if not callable(handler):
            raise ValueError("Consumer handler must be callable")

        with self._lock:
            subscriptions = self.subscriptions[event_type]

            if any(name == consumer_name for name, _ in subscriptions):
                raise EventError(
                    f"Duplicate subscription: {consumer_name}"
                )

            subscriptions.append((consumer_name, handler))

    def publish(
        self,
        event_type: str,
        producer: str,
        payload: dict[str, Any],
        version: int = 1,
        correlation_id: str | None = None,
        event_id: str | None = None
    ) -> Event:

        self.registry.validate(event_type, version, payload)

        identifier = event_id or str(uuid.uuid4())

        with self._lock:
            if identifier in self.events:
                raise DuplicateEventError(
                    f"Duplicate event ID: {identifier}"
                )

            event = Event(
                event_id=identifier,
                event_type=event_type,
                version=version,
                producer=producer,
                payload=payload.copy(),
                occurred_at=datetime.now(
                    timezone.utc
                ).isoformat(),
                correlation_id=correlation_id or str(uuid.uuid4()),
                status=EventStatus.PUBLISHED
            )

            self.events[identifier] = event

        logger.info(
            "Published %s from %s",
            event_type,
            producer
        )

        return event

    def dispatch(self, event_id: str) -> dict[str, str]:
        with self._lock:
            event = self.events.get(event_id)

            if event is None:
                raise EventError("Event does not exist")

            subscribers = list(
                self.subscriptions.get(event.event_type, [])
            )

        results = {}

        for consumer_name, handler in subscribers:
            delivery_key = (event_id, consumer_name)

            with self._lock:
                if delivery_key in self.processed:
                    results[consumer_name] = "ALREADY_PROCESSED"
                    continue

            delivery = Delivery(
                event=event,
                consumer=consumer_name
            )

            success = False

            for attempt in range(self.max_retries + 1):
                delivery.attempts = attempt + 1

                try:
                    handler(event)

                    with self._lock:
                        self.processed.add(delivery_key)

                    success = True
                    results[consumer_name] = "CONSUMED"

                    logger.info(
                        "Consumer %s processed %s",
                        consumer_name,
                        event_id
                    )
                    break

                except Exception as exc:
                    delivery.last_error = str(exc)

                    logger.warning(
                        "Consumer %s failed on attempt %s: %s",
                        consumer_name,
                        attempt + 1,
                        exc
                    )

                    if attempt < self.max_retries:
                        time.sleep(min(0.05 * (2 ** attempt), 1.0))

            if not success:
                with self._lock:
                    event.status = EventStatus.DEAD_LETTER
                    self.dead_letters.append(delivery)

                results[consumer_name] = "DEAD_LETTER"

        if not subscribers:
            results["broker"] = "NO_SUBSCRIBERS"

        return results

    def replay(self, event_id: str, consumer_name: str) -> str:
        with self._lock:
            event = self.events.get(event_id)

            if event is None:
                raise EventError("Event does not exist")

            subscriptions = list(
                self.subscriptions.get(event.event_type, [])
            )

            handler = next(
                (
                    callback
                    for name, callback in subscriptions
                    if name == consumer_name
                ),
                None
            )

            if handler is None:
                raise EventError("Consumer is not subscribed")

            self.processed.discard((event_id, consumer_name))

        result = self.dispatch(event_id)
        return result[consumer_name]

    def metrics(self) -> dict[str, int]:
        with self._lock:
            return {
                "published": len(self.events),
                "processed_deliveries": len(self.processed),
                "dead_letters": len(self.dead_letters),
                "subscribers": sum(
                    len(items)
                    for items in self.subscriptions.values()
                )
            }

    def export_events(self, filename: str) -> None:
        """Write an audit snapshot using atomic file replacement."""
        path = Path(filename)
        temporary = path.with_suffix(path.suffix + ".tmp")

        with self._lock:
            data = [
                event.to_dict()
                for event in self.events.values()
            ]

        temporary.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )

        temporary.replace(path)


# ============================================================
# EVENT PRODUCERS
# ============================================================

class OrderService:
    def __init__(self, broker: EventBroker):
        self.broker = broker

    def create_order(
        self,
        order_id: str,
        customer_id: str,
        amount: float
    ) -> Event:

        if not order_id or not customer_id:
            raise ValueError("Order and customer IDs are required")

        if not isinstance(amount, (int, float)):
            raise ValueError("Amount must be numeric")

        if isinstance(amount, bool) or amount <= 0:
            raise ValueError("Amount must be positive")

        return self.broker.publish(
            event_type="OrderCreated",
            producer="OrderService",
            payload={
                "order_id": order_id,
                "customer_id": customer_id,
                "amount": float(amount)
            }
        )


# ============================================================
# EVENT CONSUMERS
# ============================================================

class InventoryConsumer:
    def __init__(self):
        self.reserved_orders: set[str] = set()

    def handle(self, event: Event) -> None:
        order_id = event.payload["order_id"]

        if order_id in self.reserved_orders:
            return

        self.reserved_orders.add(order_id)

        logger.info("Inventory reserved for %s", order_id)


class PaymentConsumer:
    def __init__(self):
        self.payments: dict[str, float] = {}

    def handle(self, event: Event) -> None:
        order_id = event.payload["order_id"]

        if order_id in self.payments:
            return

        amount = event.payload["amount"]

        self.payments[order_id] = amount

        logger.info(
            "Payment recorded for %s: %.2f",
            order_id,
            amount
        )


class NotificationConsumer:
    def __init__(self):
        self.notifications: list[str] = []

    def handle(self, event: Event) -> None:
        message = (
            f"Order {event.payload['order_id']} created"
        )

        self.notifications.append(message)


# ============================================================
# EVENT ROUTING AND WORKFLOW
# ============================================================

def build_application():
    registry = SchemaRegistry()

    registry.register(
        EventSchema(
            name="OrderCreated",
            version=1,
            required_fields={
                "order_id": str,
                "customer_id": str,
                "amount": float
            }
        )
    )

    broker = EventBroker(registry, max_retries=2)

    inventory = InventoryConsumer()
    payment = PaymentConsumer()
    notification = NotificationConsumer()

    broker.subscribe(
        "OrderCreated",
        "InventoryService",
        inventory.handle
    )

    broker.subscribe(
        "OrderCreated",
        "PaymentService",
        payment.handle
    )

    broker.subscribe(
        "OrderCreated",
        "NotificationService",
        notification.handle
    )

    return (
        broker,
        OrderService(broker),
        inventory,
        payment,
        notification
    )


def run_tests() -> None:
    broker, orders, inventory, payments, notifications = (
        build_application()
    )

    event = orders.create_order(
        "ORD-1001",
        "CUST-501",
        2499.50
    )

    result = broker.dispatch(event.event_id)

    assert result == {
        "InventoryService": "CONSUMED",
        "PaymentService": "CONSUMED",
        "NotificationService": "CONSUMED"
    }

    assert "ORD-1001" in inventory.reserved_orders
    assert payments.payments["ORD-1001"] == 2499.50
    assert len(notifications.notifications) == 1

    # Repeated dispatch does not repeat successful deliveries.
    result = broker.dispatch(event.event_id)

    assert all(
        value == "ALREADY_PROCESSED"
        for value in result.values()
    )

    # Invalid payload must be rejected before publication.
    try:
        broker.publish(
            "OrderCreated",
            "TestProducer",
            {"order_id": "ORD-2"}
        )
        raise AssertionError("Invalid payload was accepted")
    except SchemaValidationError:
        pass

    # Unknown schema must be rejected.
    try:
        broker.publish(
            "UnknownEvent",
            "TestProducer",
            {}
        )
        raise AssertionError("Unknown event was accepted")
    except SchemaValidationError:
        pass

    # Failed consumer is isolated and routed to the dead-letter queue.
    def failing_consumer(event: Event) -> None:
        raise RuntimeError("Downstream service unavailable")

    broker.subscribe(
        "OrderCreated",
        "UnhealthyService",
        failing_consumer
    )

    second_event = orders.create_order(
        "ORD-1002",
        "CUST-502",
        1200.00
    )

    result = broker.dispatch(second_event.event_id)

    assert result["UnhealthyService"] == "DEAD_LETTER"
    assert len(broker.dead_letters) == 1

    print("\nEVENT ARCHITECTURE TEST RESULTS")
    print(json.dumps(broker.metrics(), indent=2))

    print("\nDELIVERY RESULTS")
    print(json.dumps(result, indent=2))

    print("\nPAYMENT RECORDS")
    print(json.dumps(payments.payments, indent=2))

    broker.export_events("event_audit.json")


if __name__ == "__main__":
    run_tests()
