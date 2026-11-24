"""
Async FastAPI: Asynchronous Endpoints, Database Operations and Blocking Pitfalls

Requirements:
    pip install fastapi uvicorn asyncpg pydantic

PostgreSQL:
    CREATE DATABASE async_fastapi_db;

Run:
    uvicorn async_fastapi:app --reload

Environment:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/async_fastapi_db
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

import asyncpg

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("async_fastapi")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/async_fastapi_db",
)

DB_MIN_CONNECTIONS = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
DB_MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "10"))

REQUEST_TIMEOUT = 5.0
MAX_CONCURRENT_OPERATIONS = 20


# ---------------------------------------------------------
# Domain models
# ---------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=2000)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    task_status: Optional[TaskStatus] = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    task_status: TaskStatus
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------
# Database schema
# ---------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    task_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    idempotency_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_task_status CHECK (
        task_status IN ('pending', 'running', 'completed', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
ON tasks (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tasks_status_created
ON tasks (task_status, created_at DESC);
"""


# ---------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Create one shared asynchronous connection pool.

    The pool is initialized once when the application starts
    and closed when the application shuts down.
    """

    logger.info("Starting asynchronous application")

    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=DB_MIN_CONNECTIONS,
        max_size=DB_MAX_CONNECTIONS,
        command_timeout=REQUEST_TIMEOUT,
    )

    try:
        async with pool.acquire() as connection:
            await connection.execute(CREATE_TABLE_SQL)

        app.state.db_pool = pool
        app.state.operation_semaphore = asyncio.Semaphore(
            MAX_CONCURRENT_OPERATIONS
        )

        logger.info("Database connection pool initialized")

        yield

    finally:
        await pool.close()
        logger.info("Database connection pool closed")


app = FastAPI(
    title="Async FastAPI Engineering",
    description=(
        "Asynchronous endpoints, non-blocking database "
        "operations and concurrency management."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Request middleware
# ---------------------------------------------------------

@app.middleware("http")
async def request_monitoring(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()

    request.state.request_id = request_id

    try:
        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        return response

    finally:
        elapsed = time.perf_counter() - started

        logger.info(
            "request_id=%s method=%s path=%s duration=%.4fs",
            request_id,
            request.method,
            request.url.path,
            elapsed,
        )


# ---------------------------------------------------------
# Database access
# ---------------------------------------------------------

async def get_connection_pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "db_pool", None)

    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection pool unavailable",
        )

    return pool


async def fetch_task(
    pool: asyncpg.Pool,
    task_id: uuid.UUID,
) -> Optional[asyncpg.Record]:

    async with pool.acquire() as connection:
        return await connection.fetchrow(
            """
            SELECT id, title, description, task_status,
                   created_at, updated_at
            FROM tasks
            WHERE id = $1
            """,
            task_id,
        )


def record_to_response(record: asyncpg.Record) -> TaskResponse:
    return TaskResponse(
        id=record["id"],
        title=record["title"],
        description=record["description"],
        task_status=record["task_status"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


# ---------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "runtime": "asynchronous",
        "timestamp": datetime.now(timezone.utc),
    }


@app.get("/health/database")
async def database_health(request: Request):
    pool = await get_connection_pool(request)

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with pool.acquire() as connection:
                result = await connection.fetchval("SELECT 1")

        return {
            "database": "connected",
            "result": result,
            "pool_size": pool.get_size(),
            "pool_idle": pool.get_idle_size(),
        }

    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Database health check timed out",
        )

    except asyncpg.PostgresError:
        logger.exception("Database health check failed")

        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )


# ---------------------------------------------------------
# Create task
# ---------------------------------------------------------

@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    payload: TaskCreate,
    request: Request,
    response: Response,
    idempotency_key: Annotated[
        Optional[str],
        Field(max_length=100),
    ] = None,
):
    pool = await get_connection_pool(request)

    task_id = uuid.uuid4()

    try:
        async with request.app.state.operation_semaphore:
            async with pool.acquire() as connection:
                async with connection.transaction():

                    if idempotency_key:
                        existing = await connection.fetchrow(
                            """
                            SELECT id, title, description,
                                   task_status, created_at, updated_at
                            FROM tasks
                            WHERE idempotency_key = $1
                            """,
                            idempotency_key,
                        )

                        if existing:
                            response.status_code = status.HTTP_200_OK
                            return record_to_response(existing)

                    record = await connection.fetchrow(
                        """
                        INSERT INTO tasks (
                            id, title, description, idempotency_key
                        )
                        VALUES ($1, $2, $3, $4)
                        RETURNING id, title, description,
                                  task_status, created_at, updated_at
                        """,
                        task_id,
                        payload.title,
                        payload.description,
                        idempotency_key,
                    )

        return record_to_response(record)

    except asyncpg.UniqueViolationError:
        # Handles concurrent requests using the same idempotency key.
        if idempotency_key:
            existing = await fetch_by_idempotency_key(
                pool,
                idempotency_key,
            )

            if existing:
                response.status_code = status.HTTP_200_OK
                return record_to_response(existing)

        raise HTTPException(
            status_code=409,
            detail="Duplicate task identifier",
        )

    except TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Operation timed out",
        )

    except asyncpg.PostgresError:
        logger.exception("Task creation failed")

        raise HTTPException(
            status_code=503,
            detail="Database operation failed",
        )


async def fetch_by_idempotency_key(
    pool: asyncpg.Pool,
    key: str,
):
    async with pool.acquire() as connection:
        return await connection.fetchrow(
            """
            SELECT id, title, description, task_status,
                   created_at, updated_at
            FROM tasks
            WHERE idempotency_key = $1
            """,
            key,
        )


# ---------------------------------------------------------
# Retrieve one task
# ---------------------------------------------------------

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    request: Request,
):
    pool = await get_connection_pool(request)

    try:
        async with pool.acquire() as connection:
            record = await connection.fetchrow(
                """
                SELECT id, title, description, task_status,
                       created_at, updated_at
                FROM tasks
                WHERE id = $1
                """,
                task_id,
            )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return record_to_response(record)

    except asyncpg.PostgresError:
        logger.exception("Task retrieval failed")

        raise HTTPException(
            status_code=503,
            detail="Database operation failed",
        )


# ---------------------------------------------------------
# Retrieve multiple tasks
# ---------------------------------------------------------

@app.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    task_status: Optional[TaskStatus] = None,
):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail="Limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=422,
            detail="Offset cannot be negative",
        )

    pool = await get_connection_pool(request)

    try:
        async with pool.acquire() as connection:

            records = await connection.fetch(
                """
                SELECT id, title, description, task_status,
                       created_at, updated_at
                FROM tasks
                WHERE ($1::VARCHAR IS NULL OR task_status = $1)
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                task_status.value if task_status else None,
                limit,
                offset,
            )

            total = await connection.fetchval(
                """
                SELECT COUNT(*)
                FROM tasks
                WHERE ($1::VARCHAR IS NULL OR task_status = $1)
                """,
                task_status.value if task_status else None,
            )

        return TaskListResponse(
            items=[record_to_response(r) for r in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    except asyncpg.PostgresError:
        logger.exception("Task listing failed")

        raise HTTPException(
            status_code=503,
            detail="Database operation failed",
        )


# ---------------------------------------------------------
# Update task with optimistic concurrency control
# ---------------------------------------------------------

@app.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    request: Request,
):
    pool = await get_connection_pool(request)

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No update fields supplied",
        )

    allowed_fields = {
        "title",
        "description",
        "task_status",
    }

    if not set(updates).issubset(allowed_fields):
        raise HTTPException(
            status_code=400,
            detail="Invalid update field",
        )

    assignments = []
    values = [task_id]

    # Only fixed, explicitly permitted column names enter SQL.
    for field, value in updates.items():
        if isinstance(value, Enum):
            value = value.value

        values.append(value)

        assignments.append(
            f"{field} = ${len(values)}"
        )

    assignments.append("updated_at = NOW()")

    query = f"""
        UPDATE tasks
        SET {", ".join(assignments)}
        WHERE id = $1
        RETURNING id, title, description, task_status,
                  created_at, updated_at
    """

    try:
        async with pool.acquire() as connection:
            record = await connection.fetchrow(
                query,
                *values,
            )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return record_to_response(record)

    except asyncpg.PostgresError:
        logger.exception("Task update failed")

        raise HTTPException(
            status_code=503,
            detail="Database operation failed",
        )


# ---------------------------------------------------------
# Delete task
# ---------------------------------------------------------

@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    request: Request,
):
    pool = await get_connection_pool(request)

    try:
        async with pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM tasks WHERE id = $1",
                task_id,
            )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return Response(status_code=204)

    except asyncpg.PostgresError:
        logger.exception("Task deletion failed")

        raise HTTPException(
            status_code=503,
            detail="Database operation failed",
        )


# ---------------------------------------------------------
# Concurrent I/O demonstration
# ---------------------------------------------------------

async def simulated_io_operation(
    operation_id: int,
    delay: float,
) -> dict:
    if not 0 <= delay <= 10:
        raise ValueError("Delay must be between 0 and 10 seconds")

    started = time.perf_counter()

    # asyncio.sleep releases the event loop while waiting.
    await asyncio.sleep(delay)

    return {
        "operation_id": operation_id,
        "duration": round(time.perf_counter() - started, 4),
    }


@app.get("/demo/concurrent-io")
async def concurrent_io(count: int = 5):
    if not 1 <= count <= 20:
        raise HTTPException(
            status_code=422,
            detail="Count must be between 1 and 20",
        )

    started = time.perf_counter()

    results = await asyncio.gather(
        *[
            simulated_io_operation(i, 1.0)
            for i in range(count)
        ]
    )

    return {
        "operations": results,
        "total_elapsed_seconds": round(
            time.perf_counter() - started,
            4,
        ),
    }


# ---------------------------------------------------------
# Blocking operation demonstration
# ---------------------------------------------------------

def blocking_file_operation() -> dict:
    """
    Represents synchronous file or legacy-library work.

    Calling this function directly inside an async endpoint
    would block the event loop.
    """

    time.sleep(2)

    return {
        "operation": "blocking_file_operation",
        "completed": True,
    }


@app.get("/demo/offloaded-blocking")
async def offloaded_blocking():
    started = time.perf_counter()

    # Run synchronous work in a worker thread.
    result = await run_in_threadpool(
        blocking_file_operation
    )

    return {
        **result,
        "elapsed_seconds": round(
            time.perf_counter() - started,
            4,
        ),
        "execution": "threadpool",
    }


@app.get("/demo/blocking-pitfall")
async def blocking_pitfall():
    """
    Educational endpoint.

    This intentionally blocks the event loop.
    Never use this pattern in production.
    """

    started = time.perf_counter()

    time.sleep(2)

    return {
        "warning": "The event loop was blocked",
        "elapsed_seconds": round(
            time.perf_counter() - started,
            4,
        ),
    }


# ---------------------------------------------------------
# Parallel database operations
# ---------------------------------------------------------

@app.get("/demo/parallel-database")
async def parallel_database(request: Request):
    pool = await get_connection_pool(request)

    async def count_tasks(task_state: str) -> int:
        async with pool.acquire() as connection:
            return await connection.fetchval(
                """
                SELECT COUNT(*)
                FROM tasks
                WHERE task_status = $1
                """,
                task_state,
            )

    try:
        pending, running, completed, failed = await asyncio.gather(
            count_tasks("pending"),
            count_tasks("running"),
            count_tasks("completed"),
            count_tasks("failed"),
        )

        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total": pending + running + completed + failed,
        }

    except asyncpg.PostgresError:
        logger.exception("Parallel database query failed")

        raise HTTPException(
            status_code=503,
            detail="Database query failed",
        )


# ---------------------------------------------------------
# Application entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "async_fastapi:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
