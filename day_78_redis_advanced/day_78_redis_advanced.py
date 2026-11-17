#!/usr/bin/env python3
"""
Redis Advanced: Pipelines, Transactions, Lua Scripts, and Distributed Locks.

Requirements:
    Python 3.10+
    Redis Server 6.2+

Run:
    python redis_advanced.py

Optional Redis connection:
    REDIS_HOST=localhost
    REDIS_PORT=6379
    REDIS_DB=0
    REDIS_PASSWORD=your_password

This implementation uses only the Python standard library.
It includes a minimal RESP2 client, pipeline execution, atomic
transactions, Lua scripting, and token-based distributed locks.
"""

from __future__ import annotations

import os
import socket
import time
import uuid
import random
import hashlib
import logging
import threading

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Sequence


# ---------------------------------------------------------
# Configuration and logging
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

LOGGER = logging.getLogger("redis_advanced")

HOST = os.getenv("REDIS_HOST", "localhost")
PORT = int(os.getenv("REDIS_PORT", "6379"))
DB = int(os.getenv("REDIS_DB", "0"))
PASSWORD = os.getenv("REDIS_PASSWORD")


# ---------------------------------------------------------
# Exceptions
# ---------------------------------------------------------

class RedisError(Exception):
    pass


class RedisConnectionError(RedisError):
    pass


class RedisResponseError(RedisError):
    pass


class RedisCommandError(RedisError):
    pass


class LockAcquisitionError(RedisError):
    pass


class LockOwnershipError(RedisError):
    pass


# ---------------------------------------------------------
# RESP2 protocol implementation
# ---------------------------------------------------------

class RESPClient:
    """
    Minimal Redis RESP2 client.

    Each command uses a fresh connection. This simplifies connection
    isolation and prevents concurrent operations from interleaving
    responses on a shared socket.

    Pipelines use one persistent connection for a batch.
    """

    def __init__(
        self,
        host: str = HOST,
        port: int = PORT,
        db: int = DB,
        password: Optional[str] = PASSWORD,
        timeout: float = 3.0
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.timeout = timeout

    @staticmethod
    def encode_command(parts: Sequence[Any]) -> bytes:
        encoded = [str(part).encode("utf-8") for part in parts]

        result = f"*{len(encoded)}\r\n".encode()

        for item in encoded:
            result += f"${len(item)}\r\n".encode()
            result += item + b"\r\n"

        return result

    @staticmethod
    def read_line(sock: socket.socket) -> bytes:
        result = bytearray()

        while True:
            byte = sock.recv(1)

            if not byte:
                raise RedisConnectionError("Connection closed")

            result.extend(byte)

            if result.endswith(b"\r\n"):
                return bytes(result[:-2])

    @classmethod
    def read_response(cls, sock: socket.socket) -> Any:
        prefix = sock.recv(1)

        if not prefix:
            raise RedisConnectionError("Redis returned an empty response")

        if prefix == b"+":
            return cls.read_line(sock).decode("utf-8")

        if prefix == b"-":
            message = cls.read_line(sock).decode("utf-8")
            raise RedisResponseError(message)

        if prefix == b":":
            return int(cls.read_line(sock))

        if prefix == b"$":
            length = int(cls.read_line(sock))

            if length == -1:
                return None

            data = bytearray()

            while len(data) < length + 2:
                chunk = sock.recv(length + 2 - len(data))

                if not chunk:
                    raise RedisConnectionError("Incomplete bulk response")

                data.extend(chunk)

            return bytes(data[:-2]).decode("utf-8")

        if prefix == b"*":
            count = int(cls.read_line(sock))

            if count == -1:
                return None

            return [
                cls.read_response(sock)
                for _ in range(count)
            ]

        raise RedisResponseError(f"Unknown RESP prefix: {prefix!r}")

    def connect(self) -> socket.socket:
        try:
            sock = socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout
            )
            sock.settimeout(self.timeout)

            if self.password:
                self.send_on_socket(sock, ["AUTH", self.password])

            if self.db:
                self.send_on_socket(sock, ["SELECT", self.db])

            return sock

        except (OSError, RedisError) as exc:
            raise RedisConnectionError(str(exc)) from exc

    def send_on_socket(
        self,
        sock: socket.socket,
        parts: Sequence[Any]
    ) -> Any:
        sock.sendall(self.encode_command(parts))
        return self.read_response(sock)

    def execute(self, *parts: Any) -> Any:
        sock = self.connect()

        try:
            return self.send_on_socket(sock, parts)
        finally:
            sock.close()

    def ping(self) -> bool:
        return self.execute("PING") == "PONG"


# ---------------------------------------------------------
# Pipeline implementation
# ---------------------------------------------------------

class Pipeline:
    """
    Sends multiple Redis commands over one connection.

    A normal pipeline reduces network round trips but does not
    guarantee atomic execution.
    """

    def __init__(self, client: RESPClient):
        self.client = client
        self.commands: list[Sequence[Any]] = []

    def add(self, *command: Any) -> "Pipeline":
        if not command:
            raise ValueError("Empty Redis command")

        self.commands.append(command)
        return self

    def execute(self) -> list[Any]:
        if not self.commands:
            return []

        sock = self.client.connect()

        try:
            payload = b"".join(
                self.client.encode_command(command)
                for command in self.commands
            )

            sock.sendall(payload)

            results = []

            for _ in self.commands:
                try:
                    results.append(
                        self.client.read_response(sock)
                    )
                except RedisResponseError as exc:
                    results.append(exc)

            return results

        except OSError as exc:
            raise RedisConnectionError(str(exc)) from exc

        finally:
            sock.close()
            self.commands.clear()


# ---------------------------------------------------------
# Redis transactions
# ---------------------------------------------------------

class Transaction:
    """
    MULTI / EXEC transaction.

    Redis executes queued commands atomically with respect to
    other clients. Runtime command errors do not roll back
    earlier successful commands.
    """

    def __init__(self, client: RESPClient):
        self.client = client
        self.commands: list[Sequence[Any]] = []

    def add(self, *command: Any) -> "Transaction":
        if not command:
            raise ValueError("Empty transaction command")

        self.commands.append(command)
        return self

    def execute(self) -> list[Any]:
        sock = self.client.connect()

        try:
            self.client.send_on_socket(sock, ["MULTI"])

            for command in self.commands:
                response = self.client.send_on_socket(
                    sock, command
                )

                if response != "QUEUED":
                    raise RedisCommandError(
                        f"Unexpected transaction response: {response}"
                    )

            return self.client.send_on_socket(sock, ["EXEC"])

        finally:
            sock.close()
            self.commands.clear()


# ---------------------------------------------------------
# Lua scripting
# ---------------------------------------------------------

INVENTORY_RESERVATION_SCRIPT = """
local stock = tonumber(redis.call('GET', KEYS[1]) or '0')
local quantity = tonumber(ARGV[1])

if not quantity or quantity <= 0 then
    return -1
end

if stock < quantity then
    return 0
end

redis.call('DECRBY', KEYS[1], quantity)

redis.call(
    'HSET',
    KEYS[2],
    'quantity', quantity,
    'status', 'reserved'
)

return stock - quantity
"""


class LuaScript:
    """
    Executes server-side Lua using EVALSHA.

    NOSCRIPT errors trigger EVAL fallback and SHA registration.
    """

    def __init__(self, client: RESPClient, source: str):
        self.client = client
        self.source = source
        self.sha = hashlib.sha1(
            source.encode("utf-8")
        ).hexdigest()

    def execute(
        self,
        keys: Sequence[str],
        args: Sequence[Any]
    ) -> Any:
        try:
            return self.client.execute(
                "EVALSHA",
                self.sha,
                len(keys),
                *keys,
                *args
            )

        except RedisResponseError as exc:
            if "NOSCRIPT" not in str(exc):
                raise

            return self.client.execute(
                "EVAL",
                self.source,
                len(keys),
                *keys,
                *args
            )


# ---------------------------------------------------------
# Distributed locking
# ---------------------------------------------------------

class LockState(Enum):
    ACQUIRED = "acquired"
    RELEASED = "released"
    FAILED = "failed"


@dataclass
class LockResult:
    state: LockState
    token: Optional[str]
    expires_at: Optional[float]


class DistributedLock:
    """
    Redis-based lease lock.

    Acquisition:
        SET lock_key unique_token NX PX lease_ms

    Release:
        Compare ownership token and delete atomically using Lua.

    A lock is a lease, not an unlimited guarantee of exclusive
    execution. Critical operations may also need fencing tokens.
    """

    RELEASE_SCRIPT = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end
    return 0
    """

    def __init__(
        self,
        client: RESPClient,
        key: str,
        lease_ms: int = 10000
    ):
        if lease_ms <= 0:
            raise ValueError("Lease must be positive")

        self.client = client
        self.key = key
        self.lease_ms = lease_ms
        self.token: Optional[str] = None

        self.release_script = LuaScript(
            client,
            self.RELEASE_SCRIPT
        )

    def acquire(
        self,
        retries: int = 3,
        delay: float = 0.1
    ) -> LockResult:

        if retries < 1 or delay < 0:
            raise ValueError("Invalid retry configuration")

        for attempt in range(retries):
            token = str(uuid.uuid4())

            result = self.client.execute(
                "SET",
                self.key,
                token,
                "NX",
                "PX",
                self.lease_ms
            )

            if result == "OK":
                self.token = token

                return LockResult(
                    LockState.ACQUIRED,
                    token,
                    time.time() + self.lease_ms / 1000
                )

            if attempt + 1 < retries:
                time.sleep(delay + random.uniform(0, delay))

        return LockResult(
            LockState.FAILED,
            None,
            None
        )

    def release(self) -> bool:
        if self.token is None:
            raise LockOwnershipError("No owned lock")

        result = self.release_script.execute(
            [self.key],
            [self.token]
        )

        if result == 1:
            self.token = None
            return True

        self.token = None
        return False

    def __enter__(self):
        result = self.acquire()

        if result.state != LockState.ACQUIRED:
            raise LockAcquisitionError(
                f"Unable to acquire {self.key}"
            )

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.token is not None:
            self.release()

        return False


# ---------------------------------------------------------
# Inventory service
# ---------------------------------------------------------

class InventoryService:

    def __init__(self, client: RESPClient):
        self.client = client

        self.reservation_script = LuaScript(
            client,
            INVENTORY_RESERVATION_SCRIPT
        )

    def initialize(self, product: str, stock: int) -> None:
        if stock < 0:
            raise ValueError("Stock cannot be negative")

        self.client.execute(
            "SET",
            f"inventory:{product}",
            stock
        )

    def reserve(
        self,
        product: str,
        order_id: str,
        quantity: int
    ) -> Any:

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        return self.reservation_script.execute(
            [
                f"inventory:{product}",
                f"reservation:{order_id}"
            ],
            [quantity]
        )


# ---------------------------------------------------------
# Demonstration workflows
# ---------------------------------------------------------

def demonstrate_pipeline(client: RESPClient) -> None:
    LOGGER.info("Running pipeline demonstration")

    pipeline = Pipeline(client)

    pipeline.add("SET", "analytics:visits", 100)
    pipeline.add("INCRBY", "analytics:visits", 25)
    pipeline.add("GET", "analytics:visits")
    pipeline.add("EXISTS", "analytics:visits")

    results = pipeline.execute()

    LOGGER.info("Pipeline results: %s", results)


def demonstrate_transaction(client: RESPClient) -> None:
    LOGGER.info("Running transaction demonstration")

    transaction = Transaction(client)

    transaction.add("SET", "account:A", 1000)
    transaction.add("SET", "account:B", 500)
    transaction.add("DECRBY", "account:A", 100)
    transaction.add("INCRBY", "account:B", 100)

    results = transaction.execute()

    LOGGER.info("Transaction results: %s", results)


def demonstrate_lua(client: RESPClient) -> None:
    LOGGER.info("Running Lua inventory reservation")

    inventory = InventoryService(client)

    inventory.initialize("laptop", 20)

    result = inventory.reserve(
        "laptop",
        "ORDER-1001",
        3
    )

    LOGGER.info("Remaining inventory: %s", result)


def demonstrate_distributed_lock(client: RESPClient) -> None:
    LOGGER.info("Running distributed lock demonstration")

    lock = DistributedLock(
        client,
        "locks:inventory-reconciliation",
        lease_ms=5000
    )

    result = lock.acquire(retries=3)

    if result.state != LockState.ACQUIRED:
        LOGGER.warning("Lock unavailable")
        return

    try:
        LOGGER.info("Critical section started")

        client.execute(
            "SET",
            "system:last_reconciliation",
            int(time.time())
        )

    finally:
        released = lock.release()
        LOGGER.info("Lock released: %s", released)


def demonstrate_expiration(client: RESPClient) -> None:
    client.execute(
        "SET",
        "session:temporary",
        "active",
        "EX",
        30
    )

    LOGGER.info(
        "Session TTL: %s",
        client.execute("TTL", "session:temporary")
    )


# ---------------------------------------------------------
# Application entry point
# ---------------------------------------------------------

def main() -> None:
    client = RESPClient()

    try:
        if not client.ping():
            raise RedisConnectionError("Redis health check failed")

        LOGGER.info("Connected to Redis")

        demonstrate_pipeline(client)
        demonstrate_transaction(client)
        demonstrate_lua(client)
        demonstrate_distributed_lock(client)
        demonstrate_expiration(client)

        LOGGER.info("All demonstrations completed")

    except (RedisError, OSError, ValueError) as exc:
        LOGGER.error("Execution failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
