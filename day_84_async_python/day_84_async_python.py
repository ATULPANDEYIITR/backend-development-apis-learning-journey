#!/usr/bin/env python3
"""
ASYNC PYTHON: COROUTINES, EVENT LOOPS, CONCURRENCY AND TASK MANAGEMENT

Requirements:
    Python 3.11+

Run:
    python async_python.py

Demonstrates:
    - Synchronous versus asynchronous execution
    - Coroutines and await
    - Event loop management
    - asyncio.create_task()
    - asyncio.gather()
    - asyncio.TaskGroup
    - asyncio.Semaphore
    - asyncio.Queue
    - asyncio.Lock
    - asyncio.Event
    - Timeouts and cancellation
    - Exception handling
    - Asynchronous generators
    - Async context managers
    - Bounded concurrency
    - Producer-consumer architecture
    - Performance measurement
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Callable, Any


# ============================================================
# 1. DOMAIN MODEL
# ============================================================

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    job_id: int
    duration: float
    should_fail: bool = False
    status: JobStatus = JobStatus.PENDING
    result: str | None = None
    error: str | None = None
    attempts: int = 0


@dataclass
class ExecutionReport:
    total: int
    completed: int
    failed: int
    cancelled: int
    elapsed_seconds: float
    results: list[str] = field(default_factory=list)


# ============================================================
# 2. SYNCHRONOUS EXECUTION
# ============================================================

def synchronous_task(name: str, duration: float) -> str:
    """Blocking operation that prevents other tasks from running."""
    time.sleep(duration)
    return f"{name} completed"


def demonstrate_synchronous_execution() -> None:
    print("\n1. SYNCHRONOUS EXECUTION")

    start = time.perf_counter()

    for name in ("A", "B", "C"):
        print(synchronous_task(name, 0.1))

    print(f"Elapsed: {time.perf_counter() - start:.3f}s")


# ============================================================
# 3. COROUTINES AND AWAIT
# ============================================================

async def asynchronous_task(name: str, duration: float) -> str:
    """
    A coroutine suspends at await, allowing the event loop
    to execute another ready coroutine.
    """
    print(f"Starting {name}")
    await asyncio.sleep(duration)
    print(f"Finished {name}")

    return f"{name} completed"


async def demonstrate_coroutines() -> None:
    print("\n2. COROUTINES AND AWAIT")

    result = await asynchronous_task("Coroutine A", 0.3)
    print(result)


# ============================================================
# 4. CONCURRENT EXECUTION WITH GATHER
# ============================================================

async def demonstrate_gather() -> None:
    print("\n3. CONCURRENT EXECUTION WITH GATHER")

    start = time.perf_counter()

    results = await asyncio.gather(
        asynchronous_task("Task A", 0.5),
        asynchronous_task("Task B", 0.3),
        asynchronous_task("Task C", 0.2),
    )

    print("Results:", results)
    print(f"Elapsed: {time.perf_counter() - start:.3f}s")


# ============================================================
# 5. TASK CREATION AND TASKGROUP
# ============================================================

async def demonstrate_tasks() -> None:
    print("\n4. TASK CREATION AND TASKGROUP")

    task = asyncio.create_task(
        asynchronous_task("Background task", 0.2)
    )

    print("Task created:", task.get_name())

    await task

    async with asyncio.TaskGroup() as group:
        group.create_task(asynchronous_task("Group A", 0.2))
        group.create_task(asynchronous_task("Group B", 0.3))

    print("All TaskGroup tasks completed")


# ============================================================
# 6. BOUNDED CONCURRENCY
# ============================================================

class JobProcessor:

    def __init__(self, max_concurrency: int = 3):
        if max_concurrency < 1:
            raise ValueError("Concurrency must be positive")

        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.completed = 0
        self.failed = 0
        self.lock = asyncio.Lock()

    async def process(self, job: Job) -> str:
        async with self.semaphore:
            job.status = JobStatus.RUNNING
            job.attempts += 1

            try:
                await asyncio.sleep(job.duration)

                if job.should_fail:
                    raise RuntimeError(
                        f"Job {job.job_id} encountered an error"
                    )

                job.result = f"Job {job.job_id} processed"
                job.status = JobStatus.COMPLETED

                async with self.lock:
                    self.completed += 1

                return job.result

            except asyncio.CancelledError:
                job.status = JobStatus.CANCELLED
                raise

            except Exception as exc:
                job.error = str(exc)
                job.status = JobStatus.FAILED

                async with self.lock:
                    self.failed += 1

                raise


async def demonstrate_bounded_concurrency() -> None:
    print("\n5. BOUNDED CONCURRENCY")

    processor = JobProcessor(max_concurrency=2)

    jobs = [
        Job(1, 0.3),
        Job(2, 0.2),
        Job(3, 0.4),
        Job(4, 0.1),
        Job(5, 0.2),
    ]

    start = time.perf_counter()

    results = await asyncio.gather(
        *(processor.process(job) for job in jobs)
    )

    print("Results:", results)
    print("Completed:", processor.completed)
    print("Failed:", processor.failed)
    print(f"Elapsed: {time.perf_counter() - start:.3f}s")


# ============================================================
# 7. ERROR HANDLING AND RETURN_EXCEPTIONS
# ============================================================

async def unreliable_operation(job_id: int) -> str:
    await asyncio.sleep(0.1)

    if job_id % 2 == 0:
        raise ValueError(f"Invalid job: {job_id}")

    return f"Job {job_id} successful"


async def demonstrate_error_handling() -> None:
    print("\n6. ASYNCHRONOUS ERROR HANDLING")

    results = await asyncio.gather(
        *(unreliable_operation(i) for i in range(1, 5)),
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, BaseException):
            print("Handled error:", result)
        else:
            print("Success:", result)


# ============================================================
# 8. TIMEOUTS
# ============================================================

async def slow_operation() -> str:
    await asyncio.sleep(2)
    return "Operation completed"


async def demonstrate_timeout() -> None:
    print("\n7. TIMEOUT MANAGEMENT")

    try:
        async with asyncio.timeout(0.5):
            result = await slow_operation()
            print(result)

    except TimeoutError:
        print("Operation exceeded its deadline")


# ============================================================
# 9. TASK CANCELLATION
# ============================================================

async def cancellable_operation() -> None:
    try:
        while True:
            print("Working...")
            await asyncio.sleep(0.2)

    except asyncio.CancelledError:
        print("Cancellation received; cleaning up")
        raise


async def demonstrate_cancellation() -> None:
    print("\n8. TASK CANCELLATION")

    task = asyncio.create_task(cancellable_operation())

    await asyncio.sleep(0.5)

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        print("Task cancelled successfully")


# ============================================================
# 10. ASYNC QUEUE: PRODUCER-CONSUMER
# ============================================================

STOP = object()


async def producer(
    queue: asyncio.Queue,
    count: int
) -> None:
    for number in range(count):
        await queue.put(number)
        print(f"Produced: {number}")

    await queue.put(STOP)


async def consumer(
    queue: asyncio.Queue,
    consumer_id: int
) -> list[int]:

    processed = []

    while True:
        item = await queue.get()

        try:
            if item is STOP:
                return processed

            await asyncio.sleep(0.1)
            processed.append(item)

            print(f"Consumer {consumer_id}: {item}")

        finally:
            queue.task_done()


async def demonstrate_producer_consumer() -> None:
    print("\n9. PRODUCER-CONSUMER ARCHITECTURE")

    queue = asyncio.Queue(maxsize=3)

    producer_task = asyncio.create_task(
        producer(queue, 8)
    )

    consumer_task = asyncio.create_task(
        consumer(queue, 1)
    )

    await producer_task
    await consumer_task
    await queue.join()

    print("Queue processing completed")


# ============================================================
# 11. LOCKS AND SHARED STATE
# ============================================================

class AsyncBankAccount:

    def __init__(self, balance: float):
        if balance < 0:
            raise ValueError("Initial balance cannot be negative")

        self.balance = balance
        self.lock = asyncio.Lock()

    async def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Deposit must be positive")

        async with self.lock:
            current = self.balance
            await asyncio.sleep(0)
            self.balance = current + amount

            return self.balance

    async def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Withdrawal must be positive")

        async with self.lock:
            if amount > self.balance:
                raise ValueError("Insufficient funds")

            self.balance -= amount
            return self.balance


async def demonstrate_lock() -> None:
    print("\n10. LOCKS AND SHARED STATE")

    account = AsyncBankAccount(1000)

    await asyncio.gather(
        account.deposit(100),
        account.deposit(200),
        account.deposit(300),
    )

    print("Final balance:", account.balance)

    try:
        await account.withdraw(5000)
    except ValueError as exc:
        print("Transaction rejected:", exc)


# ============================================================
# 12. EVENT-BASED COORDINATION
# ============================================================

async def worker(
    ready: asyncio.Event,
    worker_id: int
) -> str:

    print(f"Worker {worker_id} waiting")

    await ready.wait()

    await asyncio.sleep(0.1)

    return f"Worker {worker_id} released"


async def demonstrate_event() -> None:
    print("\n11. EVENT-BASED COORDINATION")

    ready = asyncio.Event()

    tasks = [
        asyncio.create_task(worker(ready, i))
        for i in range(3)
    ]

    await asyncio.sleep(0.3)

    ready.set()

    results = await asyncio.gather(*tasks)

    print(results)


# ============================================================
# 13. ASYNCHRONOUS GENERATORS
# ============================================================

async def generate_records(count: int) -> AsyncIterator[dict[str, int]]:
    for number in range(count):
        await asyncio.sleep(0.05)
        yield {
            "id": number,
            "value": number * number,
        }


async def demonstrate_async_generator() -> None:
    print("\n12. ASYNCHRONOUS GENERATORS")

    async for record in generate_records(5):
        print(record)


# ============================================================
# 14. ASYNCHRONOUS CONTEXT MANAGERS
# ============================================================

class AsyncResource:

    async def __aenter__(self):
        print("Resource acquired")
        await asyncio.sleep(0.1)
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        print("Resource released")
        await asyncio.sleep(0.1)
        return False

    async def execute(self) -> str:
        await asyncio.sleep(0.1)
        return "Resource operation completed"


async def demonstrate_context_manager() -> None:
    print("\n13. ASYNCHRONOUS CONTEXT MANAGER")

    async with AsyncResource() as resource:
        print(await resource.execute())


# ============================================================
# 15. RETRY WITH EXPONENTIAL BACKOFF
# ============================================================

async def retry_operation(
    operation: Callable[[], Any],
    attempts: int = 3,
    initial_delay: float = 0.1,
) -> Any:

    if attempts < 1:
        raise ValueError("At least one attempt is required")

    if initial_delay < 0:
        raise ValueError("Delay cannot be negative")

    for attempt in range(attempts):
        try:
            return await operation()

        except asyncio.CancelledError:
            raise

        except (ValueError, ConnectionError):
            if attempt == attempts - 1:
                raise

            await asyncio.sleep(
                initial_delay * (2 ** attempt)
            )


async def demonstrate_retry() -> None:
    print("\n14. RETRY AND EXPONENTIAL BACKOFF")

    state = {"attempts": 0}

    async def unstable_service() -> str:
        state["attempts"] += 1

        if state["attempts"] < 3:
            raise ConnectionError("Temporary service failure")

        return "Service recovered"

    result = await retry_operation(
        unstable_service,
        attempts=3,
    )

    print(result)
    print("Attempts:", state["attempts"])


# ============================================================
# 16. ASYNC BATCH PROCESSING
# ============================================================

async def fetch_record(record_id: int) -> dict[str, Any]:
    await asyncio.sleep(random.uniform(0.05, 0.2))

    return {
        "id": record_id,
        "value": record_id * 10,
        "processed": True,
    }


async def batch_processor(
    record_ids: list[int],
    concurrency: int = 5,
) -> list[dict[str, Any]]:

    if concurrency < 1:
        raise ValueError("Concurrency must be positive")

    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_fetch(record_id: int):
        async with semaphore:
            return await fetch_record(record_id)

    tasks = [
        bounded_fetch(record_id)
        for record_id in record_ids
    ]

    return await asyncio.gather(*tasks)


async def demonstrate_batch_processing() -> None:
    print("\n15. BATCH PROCESSING")

    records = await batch_processor(
        list(range(1, 11)),
        concurrency=3,
    )

    for record in records:
        print(record)


# ============================================================
# 17. MAIN EXECUTION
# ============================================================

async def main() -> None:

    await demonstrate_coroutines()
    await demonstrate_gather()
    await demonstrate_tasks()
    await demonstrate_bounded_concurrency()
    await demonstrate_error_handling()
    await demonstrate_timeout()
    await demonstrate_cancellation()
    await demonstrate_producer_consumer()
    await demonstrate_lock()
    await demonstrate_event()
    await demonstrate_async_generator()
    await demonstrate_context_manager()
    await demonstrate_retry()
    await demonstrate_batch_processing()

    print("\nAll demonstrations completed")


# ============================================================
# 18. EXECUTABLE TESTS
# ============================================================

async def run_tests() -> None:

    assert await asynchronous_task("Test", 0) == "Test completed"

    account = AsyncBankAccount(100)

    await asyncio.gather(
        account.deposit(10),
        account.deposit(20),
    )

    assert account.balance == 130

    processor = JobProcessor(2)

    job = Job(100, 0)

    assert await processor.process(job) == "Job 100 processed"
    assert job.status == JobStatus.COMPLETED

    records = await batch_processor([1, 2, 3], 2)

    assert len(records) == 3
    assert records[0]["value"] == 10

    print("\nAll assertions passed")


if __name__ == "__main__":

    async def application() -> None:
        start = time.perf_counter()

        try:
            await main()
            await run_tests()

        finally:
            elapsed = time.perf_counter() - start
            print(f"\nTotal execution time: {elapsed:.3f}s")

    asyncio.run(application())
