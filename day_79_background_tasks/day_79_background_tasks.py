#!/usr/bin/env python3
"""
Background Tasks: Asynchronous Jobs, Task Queues, and Worker Processes.

A self-contained background-task processing system demonstrating:
- Task creation, validation, scheduling, and lifecycle management.
- Priority-based task queues.
- Multiple worker processes simulated with threads.
- Retry policies, exponential backoff, and dead-letter queues.
- Task dependencies, idempotency, and concurrency control.
- Graceful worker shutdown and operational monitoring.

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
import heapq
import random

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from queue import PriorityQueue, Empty
from typing import Any, Callable, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
)
logger = logging.getLogger("background_tasks")


# ============================================================
# 1. DOMAIN TYPES
# ============================================================

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    CRITICAL = 1
    HIGH = 3
    NORMAL = 5
    LOW = 8


class TaskError(Exception):
    """Base exception for task processing."""


class TaskValidationError(TaskError):
    pass


class TaskNotFoundError(TaskError):
    pass


class InvalidTransitionError(TaskError):
    pass


class PermanentTaskError(TaskError):
    """An error that must not be retried."""


TERMINAL_STATES = {
    TaskStatus.COMPLETED,
    TaskStatus.DEAD_LETTER,
    TaskStatus.CANCELLED,
}


ALLOWED_TRANSITIONS = {
    TaskStatus.PENDING: {
        TaskStatus.QUEUED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.QUEUED: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.RETRY_WAIT,
        TaskStatus.FAILED,
        TaskStatus.DEAD_LETTER,
    },
    TaskStatus.RETRY_WAIT: {
        TaskStatus.QUEUED,
        TaskStatus.CANCELLED,
        TaskStatus.DEAD_LETTER,
    },
    TaskStatus.FAILED: {
        TaskStatus.QUEUED,
        TaskStatus.DEAD_LETTER,
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# 2. TASK DATA MODEL
# ============================================================

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_delay: float = 0.1
    max_delay: float = 10.0
    multiplier: float = 2.0

    def __post_init__(self):
        if self.max_attempts < 1:
            raise TaskValidationError("At least one attempt is required.")
        if self.initial_delay < 0 or self.max_delay < 0:
            raise TaskValidationError("Retry delays cannot be negative.")
        if self.multiplier < 1:
            raise TaskValidationError("Retry multiplier must be at least 1.")

    def delay(self, attempt: int) -> float:
        base = min(
            self.initial_delay * self.multiplier ** max(0, attempt - 1),
            self.max_delay,
        )
        return base * random.uniform(0.8, 1.2)


@dataclass
class Task:
    task_type: str
    payload: dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: Optional[str] = None
    dependencies: set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    scheduled_at: datetime = field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_id: Optional[str] = None
    version: int = 0

    def __post_init__(self):
        if not self.task_type or len(self.task_type) > 100:
            raise TaskValidationError("Invalid task type.")
        if not isinstance(self.payload, dict):
            raise TaskValidationError("Task payload must be a dictionary.")
        if len(self.dependencies) > 1000:
            raise TaskValidationError("Too many task dependencies.")

    def transition(self, new_status: TaskStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS.get(self.status, set()):
            raise InvalidTransitionError(
                f"Cannot transition from {self.status.value} "
                f"to {new_status.value}."
            )
        self.status = new_status
        self.updated_at = utc_now()
        self.version += 1


# ============================================================
# 3. TASK REGISTRY AND HANDLERS
# ============================================================

TaskHandler = Callable[[dict[str, Any]], Any]


class HandlerRegistry:
    """Only registered handlers can execute."""

    def __init__(self):
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        if not task_type or not callable(handler):
            raise TaskValidationError("Invalid handler registration.")
        if task_type in self._handlers:
            raise TaskValidationError(f"Handler already registered: {task_type}")
        self._handlers[task_type] = handler

    def get(self, task_type: str) -> TaskHandler:
        try:
            return self._handlers[task_type]
        except KeyError:
            raise TaskValidationError(
                f"No handler registered for {task_type}"
            ) from None


# ============================================================
# 4. TASK QUEUE
# ============================================================

class TaskQueue:
    """
    Lower numeric priority values execute first.
    Sequence numbers preserve FIFO ordering within a priority.
    """

    def __init__(self):
        self._queue = PriorityQueue()
        self._sequence = 0
        self._lock = threading.Lock()

    def enqueue(self, task: Task) -> None:
        with self._lock:
            self._sequence += 1
            self._queue.put((
                task.priority.value,
                self._sequence,
                task.task_id,
            ))

    def dequeue(self, timeout: float = 0.2) -> Optional[str]:
        try:
            _, _, task_id = self._queue.get(timeout=timeout)
            return task_id
        except Empty:
            return None

    def task_done(self) -> None:
        self._queue.task_done()

    def size(self) -> int:
        return self._queue.qsize()


# ============================================================
# 5. TASK STORE
# ============================================================

class TaskStore:
    """Thread-safe in-memory task persistence."""

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self.idempotency: dict[str, str] = {}
        self.lock = threading.RLock()

    def create(self, task: Task) -> Task:
        with self.lock:
            if task.idempotency_key:
                existing = self.idempotency.get(task.idempotency_key)
                if existing:
                    return self.tasks[existing]

            if task.task_id in self.tasks:
                raise TaskValidationError("Duplicate task ID.")

            for dependency in task.dependencies:
                if dependency not in self.tasks:
                    raise TaskValidationError(
                        f"Unknown dependency: {dependency}"
                    )

            self.tasks[task.task_id] = task

            if task.idempotency_key:
                self.idempotency[task.idempotency_key] = task.task_id

            return task

    def get(self, task_id: str) -> Task:
        with self.lock:
            if task_id not in self.tasks:
                raise TaskNotFoundError(task_id)
            return self.tasks[task_id]

    def all(self) -> list[Task]:
        with self.lock:
            return list(self.tasks.values())

    def dependencies_completed(self, task: Task) -> bool:
        with self.lock:
            return all(
                self.tasks[dependency].status == TaskStatus.COMPLETED
                for dependency in task.dependencies
            )


# ============================================================
# 6. BACKGROUND TASK ENGINE
# ============================================================

class BackgroundTaskEngine:

    def __init__(self):
        self.store = TaskStore()
        self.queue = TaskQueue()
        self.registry = HandlerRegistry()
        self.dead_letters: list[str] = []
        self.lock = threading.RLock()
        self.workers: list[threading.Thread] = []
        self.stop_event = threading.Event()
        self.metrics = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
            "dead_lettered": 0,
        }

    def register_handler(self, task_type: str, handler: TaskHandler):
        self.registry.register(task_type, handler)

    def submit(self, task: Task) -> Task:
        with self.lock:
            if task.scheduled_at > utc_now():
                self.store.create(task)
                self.metrics["submitted"] += 1
                return task

            task.transition(TaskStatus.QUEUED)
            stored = self.store.create(task)

            if stored is not task:
                return stored

            self.queue.enqueue(task)
            self.metrics["submitted"] += 1
            logger.info("Submitted task %s", task.task_id)
            return task

    def schedule_due_tasks(self):
        now = utc_now()

        for task in self.store.all():
            with self.lock:
                if task.status not in {
                    TaskStatus.PENDING,
                    TaskStatus.RETRY_WAIT,
                }:
                    continue

                if task.scheduled_at > now:
                    continue

                if not self.store.dependencies_completed(task):
                    continue

                task.transition(TaskStatus.QUEUED)
                self.queue.enqueue(task)

    def cancel(self, task_id: str):
        with self.lock:
            task = self.store.get(task_id)

            if task.status not in {
                TaskStatus.PENDING,
                TaskStatus.QUEUED,
                TaskStatus.RETRY_WAIT,
            }:
                raise InvalidTransitionError(
                    "Running or completed tasks cannot be cancelled."
                )

            task.transition(TaskStatus.CANCELLED)

    def process(self, task_id: str, worker_id: str):
        with self.lock:
            task = self.store.get(task_id)

            # A queued item may become obsolete after cancellation.
            if task.status != TaskStatus.QUEUED:
                return

            if not self.store.dependencies_completed(task):
                task.transition(TaskStatus.PENDING)
                return

            task.transition(TaskStatus.RUNNING)
            task.attempts += 1
            task.worker_id = worker_id
            task.started_at = utc_now()

        try:
            handler = self.registry.get(task.task_type)
            result = handler(task.payload)

            with self.lock:
                if task.status != TaskStatus.RUNNING:
                    return

                task.result = result
                task.completed_at = utc_now()
                task.transition(TaskStatus.COMPLETED)
                self.metrics["completed"] += 1

            logger.info("Completed task %s", task_id)

        except Exception as exc:
            with self.lock:
                if task.status != TaskStatus.RUNNING:
                    return

                task.error = f"{type(exc).__name__}: {exc}"

                permanent = isinstance(exc, PermanentTaskError)
                exhausted = task.attempts >= task.retry_policy.max_attempts

                if permanent or exhausted:
                    task.transition(TaskStatus.DEAD_LETTER)
                    self.dead_letters.append(task_id)
                    self.metrics["dead_lettered"] += 1
                    self.metrics["failed"] += 1
                    logger.error("Task %s entered dead-letter queue", task_id)
                else:
                    delay = task.retry_policy.delay(task.attempts)
                    task.scheduled_at = utc_now() + timedelta(seconds=delay)
                    task.transition(TaskStatus.RETRY_WAIT)
                    self.metrics["retried"] += 1
                    logger.warning(
                        "Task %s will retry in %.2f seconds",
                        task_id,
                        delay,
                    )

    def worker_loop(self, worker_id: str):
        while not self.stop_event.is_set():
            self.schedule_due_tasks()

            task_id = self.queue.dequeue(timeout=0.2)
            if task_id is None:
                continue

            try:
                self.process(task_id, worker_id)
            finally:
                self.queue.task_done()

    def start_workers(self, count: int = 2):
        if count < 1 or count > 100:
            raise ValueError("Worker count must be between 1 and 100.")

        if self.workers:
            raise RuntimeError("Workers have already been started.")

        self.stop_event.clear()

        for index in range(count):
            worker_id = f"worker-{index + 1}"
            worker = threading.Thread(
                target=self.worker_loop,
                args=(worker_id,),
                name=worker_id,
                daemon=True,
            )
            worker.start()
            self.workers.append(worker)

    def shutdown(self, timeout: float = 5.0):
        self.stop_event.set()

        for worker in self.workers:
            worker.join(timeout=timeout)

        still_running = [
            worker.name for worker in self.workers if worker.is_alive()
        ]

        if still_running:
            logger.warning("Workers did not stop: %s", still_running)

        self.workers.clear()

    def retry_dead_letter(self, task_id: str):
        with self.lock:
            task = self.store.get(task_id)

            if task.status != TaskStatus.DEAD_LETTER:
                raise InvalidTransitionError("Task is not dead-lettered.")

            if task.attempts >= task.retry_policy.max_attempts:
                raise TaskValidationError(
                    "Original retry limit has been exhausted."
                )

            task.error = None
            task.scheduled_at = utc_now()
            task.transition(TaskStatus.QUEUED)
            self.dead_letters.remove(task_id)
            self.queue.enqueue(task)

    def report(self) -> dict[str, Any]:
        tasks = self.store.all()

        counts = {
            status.value: sum(t.status == status for t in tasks)
            for status in TaskStatus
        }

        return {
            "metrics": dict(self.metrics),
            "queue_size": self.queue.size(),
            "dead_letters": list(self.dead_letters),
            "task_counts": counts,
            "total_tasks": len(tasks),
        }


# ============================================================
# 7. EXAMPLE TASK HANDLERS
# ============================================================

def generate_report(payload: dict[str, Any]) -> dict[str, Any]:
    report_name = payload.get("report_name")

    if not isinstance(report_name, str) or not report_name.strip():
        raise PermanentTaskError("A valid report name is required.")

    return {
        "report": report_name,
        "records_processed": 1250,
        "generated_at": utc_now().isoformat(),
    }


def send_notification(payload: dict[str, Any]) -> dict[str, Any]:
    recipient = payload.get("recipient")

    if not isinstance(recipient, str) or "@" not in recipient:
        raise PermanentTaskError("Invalid notification recipient.")

    return {
        "recipient": recipient,
        "delivery_status": "accepted",
    }


def unreliable_operation(payload: dict[str, Any]) -> dict[str, Any]:
    """Demonstrates retry behavior."""
    failures_remaining = payload.get("failures_remaining", 0)

    if failures_remaining > 0:
        payload["failures_remaining"] -= 1
        raise RuntimeError("Temporary service failure.")

    return {"status": "recovered"}


# ============================================================
# 8. OPERATIONAL MONITORING AND PERSISTENCE
# ============================================================

def export_report(engine: BackgroundTaskEngine, filename: str):
    """
    Export operational metadata.
    Avoid exporting confidential task payloads or credentials.
    """

    report = engine.report()

    with Path(filename).open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)


def print_task_report(engine: BackgroundTaskEngine):
    for task in engine.store.all():
        print(
            f"{task.task_id[:8]} | "
            f"{task.task_type:18} | "
            f"{task.status.value:12} | "
            f"attempts={task.attempts} | "
            f"worker={task.worker_id}"
        )


# ============================================================
# 9. EXECUTABLE DEMONSTRATION
# ============================================================

def main():
    engine = BackgroundTaskEngine()

    engine.register_handler("report", generate_report)
    engine.register_handler("notification", send_notification)
    engine.register_handler("unreliable", unreliable_operation)

    report_task = Task(
        task_type="report",
        payload={"report_name": "Monthly Operations"},
        priority=TaskPriority.HIGH,
        idempotency_key="report-month-2026-11",
    )

    engine.submit(report_task)

    notification_task = Task(
        task_type="notification",
        payload={"recipient": "operations@example.com"},
        priority=TaskPriority.NORMAL,
        dependencies={report_task.task_id},
    )

    engine.submit(notification_task)

    retry_task = Task(
        task_type="unreliable",
        payload={"failures_remaining": 1},
        priority=TaskPriority.LOW,
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
        ),
    )

    engine.submit(retry_task)

    # Duplicate submission returns the existing idempotent task.
    duplicate = engine.submit(
        Task(
            task_type="report",
            payload={"report_name": "Duplicate"},
            idempotency_key="report-month-2026-11",
        )
    )

    assert duplicate.task_id == report_task.task_id

    engine.start_workers(count=3)

    try:
        deadline = time.monotonic() + 8

        while time.monotonic() < deadline:
            statuses = [t.status for t in engine.store.all()]

            if (
                statuses.count(TaskStatus.COMPLETED) == 3
                and engine.queue.size() == 0
            ):
                break

            time.sleep(0.05)

    finally:
        engine.shutdown()

    print("\nTASK EXECUTION REPORT")
    print_task_report(engine)

    print("\nSYSTEM METRICS")
    print(json.dumps(engine.report(), indent=2))

    assert report_task.status == TaskStatus.COMPLETED
    assert notification_task.status == TaskStatus.COMPLETED
    assert retry_task.status == TaskStatus.COMPLETED
    assert retry_task.attempts == 2

    print("\nAll demonstration assertions passed.")


if __name__ == "__main__":
    main()
