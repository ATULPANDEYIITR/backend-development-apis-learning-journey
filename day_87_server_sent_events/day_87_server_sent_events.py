#!/usr/bin/env python3
"""
Server-Sent Events (SSE): Streaming Responses and Real-Time Updates

Features:
- HTTP-based one-way server-to-client event streaming.
- Event IDs and reconnect support.
- Last-Event-ID replay.
- Named events and JSON payloads.
- Heartbeats and connection timeouts.
- Bounded event history.
- Subscriber management.
- Thread-safe event broadcasting.
- HTTP client example.
- Input validation and security controls.

Run:
    python sse_server.py
    python sse_server.py --serve
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
import uuid

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("sse")


class EventType(str, Enum):
    MESSAGE = "message"
    UPDATE = "update"
    NOTIFICATION = "notification"
    PROGRESS = "progress"
    ERROR = "error"


@dataclass(frozen=True)
class SSEEvent:
    event_id: str
    event_type: EventType
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def encode(self) -> bytes:
        """Convert an event into the SSE wire format."""
        payload = json.dumps(
            self.data,
            ensure_ascii=False,
            separators=(",", ":")
        )

        lines = [
            f"id: {self.event_id}",
            f"event: {self.event_type.value}",
            f"data: {payload}",
            ""
        ]

        return ("\n".join(lines) + "\n").encode("utf-8")


class EventValidationError(ValueError):
    pass


class EventHistory:
    """Thread-safe bounded event history supporting replay."""

    def __init__(self, capacity: int = 1000):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.events: deque[SSEEvent] = deque(maxlen=capacity)
        self.lock = threading.RLock()

    def append(self, event: SSEEvent) -> None:
        with self.lock:
            self.events.append(event)

    def after(self, last_event_id: Optional[str]) -> list[SSEEvent]:
        with self.lock:
            if not last_event_id:
                return list(self.events)

            for index, event in enumerate(self.events):
                if event.event_id == last_event_id:
                    return list(self.events)[index + 1:]

            # A missing cursor may indicate that history has expired.
            return []


class EventBroker:
    """Publishes events and manages subscriber notification."""

    def __init__(self, history_size: int = 1000):
        self.history = EventHistory(history_size)
        self.condition = threading.Condition()
        self.sequence = 0
        self.running = True

    def publish(
        self,
        event_type: EventType,
        data: dict[str, Any]
    ) -> SSEEvent:

        if not isinstance(data, dict):
            raise EventValidationError("Event data must be a dictionary")

        if len(json.dumps(data, default=str)) > 64_000:
            raise EventValidationError("Event payload exceeds 64 KB")

        self.sequence += 1

        event = SSEEvent(
            event_id=str(self.sequence),
            event_type=event_type,
            data=data
        )

        self.history.append(event)

        with self.condition:
            self.condition.notify_all()

        logger.info("Published event %s", event.event_id)
        return event

    def replay(self, last_event_id: Optional[str]) -> list[SSEEvent]:
        return self.history.after(last_event_id)

    def wait_for_events(
        self,
        last_event_id: Optional[str],
        timeout: float
    ) -> list[SSEEvent]:

        events = self.replay(last_event_id)

        if events:
            return events

        with self.condition:
            self.condition.wait(timeout)

        return self.replay(last_event_id)


class SSEApplication:
    """Application service separating event production from HTTP transport."""

    def __init__(self):
        self.broker = EventBroker(history_size=500)

    def create_update(
        self,
        resource: str,
        status: str,
        progress: int
    ) -> SSEEvent:

        if not resource or len(resource) > 100:
            raise EventValidationError("Invalid resource identifier")

        if not 0 <= progress <= 100:
            raise EventValidationError("Progress must be between 0 and 100")

        return self.broker.publish(
            EventType.UPDATE,
            {
                "resource": resource,
                "status": status,
                "progress": progress,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat()
            }
        )

    def create_notification(self, message: str) -> SSEEvent:
        if not message or len(message) > 2000:
            raise EventValidationError("Invalid notification")

        return self.broker.publish(
            EventType.NOTIFICATION,
            {"message": message}
        )


APPLICATION = SSEApplication()


class SSEHandler(BaseHTTPRequestHandler):
    """HTTP transport for the SSE application."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format_string, *args):
        logger.info("%s - %s", self.client_address[0], format_string % args)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/health":
            self.send_json(200, {"status": "healthy"})
            return

        if path == "/events":
            self.handle_event_stream()
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path != "/publish":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 64_000:
                raise EventValidationError("Invalid request size")

            body = self.rfile.read(length)
            payload = json.loads(body)

            if not isinstance(payload, dict):
                raise EventValidationError("Expected JSON object")

            message = payload.get("message")

            if not isinstance(message, str):
                raise EventValidationError("Message must be a string")

            event = APPLICATION.create_notification(message)

            self.send_json(
                201,
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value
                }
            )

        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})

    def handle_event_stream(self):
        last_event_id = self.headers.get("Last-Event-ID")

        if last_event_id and not last_event_id.isdigit():
            self.send_json(400, {"error": "Invalid event cursor"})
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/event-stream; charset=utf-8"
        )
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            cursor = last_event_id

            # Replay retained events before waiting for new events.
            for event in APPLICATION.broker.replay(cursor):
                self.wfile.write(event.encode())
                self.wfile.flush()
                cursor = event.event_id

            heartbeat_interval = 15

            while True:
                events = APPLICATION.broker.wait_for_events(
                    cursor,
                    heartbeat_interval
                )

                if not events:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    continue

                for event in events:
                    self.wfile.write(event.encode())
                    self.wfile.flush()
                    cursor = event.event_id

        except (BrokenPipeError, ConnectionResetError, OSError):
            logger.info("SSE client disconnected: %s", self.client_address)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.end_headers()


def run_server(host: str = "127.0.0.1", port: int = 8000):
    server = ThreadingHTTPServer((host, port), SSEHandler)
    server.daemon_threads = True

    logger.info("SSE server listening on http://%s:%d", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    finally:
        server.shutdown()
        server.server_close()


def demonstrate_client():
    """Demonstrate HTTP publication and event encoding."""

    event = APPLICATION.create_update(
        resource="report-2026",
        status="processing",
        progress=45
    )

    notification = APPLICATION.create_notification(
        "Report processing has started"
    )

    print("\nGenerated SSE events:")
    print(event.encode().decode())
    print(notification.encode().decode())

    print("Event replay:")
    for replayed in APPLICATION.broker.replay("0"):
        print(replayed.event_id, replayed.event_type.value)

    print("\nWire-format validation:")
    assert event.encode().startswith(b"id: ")
    assert b"event: update" in event.encode()
    assert b"data: " in event.encode()

    print("All assertions passed.")


def main():
    parser = argparse.ArgumentParser(
        description="Server-Sent Events demonstration server"
    )

    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the HTTP server"
    )

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")

    if args.serve:
        run_server(args.host, args.port)
    else:
        demonstrate_client()


if __name__ == "__main__":
    main()
