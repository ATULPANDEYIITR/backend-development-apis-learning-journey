#!/usr/bin/env python3
"""
Redis Fundamentals: An executable in-memory Redis-style data store.

Demonstrates:
- Key-value storage
- Strings, hashes, lists, sets and sorted sets
- Expiration and TTL
- Atomic transactions
- Type validation
- Key scanning
- Persistence using JSON
- Error handling and testing

Uses only the Python standard library.
"""

from __future__ import annotations

import json
import math
import time
import fnmatch
import tempfile
import unittest

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class DataType(Enum):
    STRING = "string"
    HASH = "hash"
    LIST = "list"
    SET = "set"
    ZSET = "zset"


class RedisError(Exception):
    pass


class WrongTypeError(RedisError):
    pass


class ValidationError(RedisError):
    pass


@dataclass
class Entry:
    data_type: DataType
    value: Any
    expires_at: float | None = None


class RedisStore:
    """A simplified Redis-compatible in-memory data model."""

    def __init__(self):
        self._data: dict[str, Entry] = {}

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not key:
            raise ValidationError("Key must be a non-empty string.")

    def _purge(self, key: str) -> None:
        entry = self._data.get(key)
        if entry and entry.expires_at is not None:
            if time.monotonic() >= entry.expires_at:
                del self._data[key]

    def _get(self, key: str, expected: DataType) -> Entry:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            raise RedisError(f"Key does not exist: {key}")

        if entry.data_type != expected:
            raise WrongTypeError(
                f"Expected {expected.value}, got {entry.data_type.value}."
            )

        return entry

    def _create(self, key: str, data_type: DataType, value: Any) -> Entry:
        self._validate_key(key)
        self._purge(key)

        if key not in self._data:
            self._data[key] = Entry(data_type, value)

        entry = self._data[key]

        if entry.data_type != data_type:
            raise WrongTypeError(
                f"Key {key} contains {entry.data_type.value}, "
                f"not {data_type.value}."
            )

        return entry

    # STRING OPERATIONS

    def set(self, key: str, value: str, nx: bool = False) -> bool:
        self._validate_key(key)

        if not isinstance(value, str):
            raise ValidationError("String values must be strings.")

        self._purge(key)

        if nx and key in self._data:
            return False

        self._data[key] = Entry(DataType.STRING, value)
        return True

    def get(self, key: str) -> str | None:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return None

        if entry.data_type != DataType.STRING:
            raise WrongTypeError("GET requires a string key.")

        return entry.value

    def incr(self, key: str, amount: int = 1) -> int:
        current = self.get(key)

        if current is None:
            current = "0"

        try:
            number = int(current)
        except ValueError as exc:
            raise RedisError("Value is not an integer.") from exc

        result = number + amount
        self.set(key, str(result))
        return result

    # HASH OPERATIONS

    def hset(self, key: str, field: str, value: str) -> bool:
        if not field:
            raise ValidationError("Hash field cannot be empty.")

        if not isinstance(value, str):
            raise ValidationError("Hash values must be strings.")

        entry = self._create(key, DataType.HASH, {})
        is_new = field not in entry.value
        entry.value[field] = value
        return is_new

    def hget(self, key: str, field: str) -> str | None:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return None

        if entry.data_type != DataType.HASH:
            raise WrongTypeError("HGET requires a hash key.")

        return entry.value.get(field)

    def hgetall(self, key: str) -> dict[str, str]:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return {}

        if entry.data_type != DataType.HASH:
            raise WrongTypeError("HGETALL requires a hash key.")

        return dict(entry.value)

    def hdel(self, key: str, field: str) -> bool:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return False

        if entry.data_type != DataType.HASH:
            raise WrongTypeError("HDEL requires a hash key.")

        existed = field in entry.value
        entry.value.pop(field, None)

        if not entry.value:
            del self._data[key]

        return existed

    # LIST OPERATIONS

    def lpush(self, key: str, *values: str) -> int:
        entry = self._create(key, DataType.LIST, [])
        entry.value[0:0] = list(values)
        return len(entry.value)

    def rpush(self, key: str, *values: str) -> int:
        entry = self._create(key, DataType.LIST, [])
        entry.value.extend(values)
        return len(entry.value)

    def lpop(self, key: str) -> str | None:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return None

        if entry.data_type != DataType.LIST:
            raise WrongTypeError("LPOP requires a list key.")

        result = entry.value.pop(0)

        if not entry.value:
            del self._data[key]

        return result

    def rpop(self, key: str) -> str | None:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return None

        if entry.data_type != DataType.LIST:
            raise WrongTypeError("RPOP requires a list key.")

        result = entry.value.pop()

        if not entry.value:
            del self._data[key]

        return result

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return []

        if entry.data_type != DataType.LIST:
            raise WrongTypeError("LRANGE requires a list key.")

        values = entry.value
        size = len(values)

        if start < 0:
            start = max(0, size + start)

        if stop < 0:
            stop = size + stop

        return values[start:stop + 1]

    # SET OPERATIONS

    def sadd(self, key: str, *members: str) -> int:
        entry = self._create(key, DataType.SET, set())
        before = len(entry.value)
        entry.value.update(members)
        return len(entry.value) - before

    def srem(self, key: str, *members: str) -> int:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return 0

        if entry.data_type != DataType.SET:
            raise WrongTypeError("SREM requires a set key.")

        before = len(entry.value)
        entry.value.difference_update(members)

        removed = before - len(entry.value)

        if not entry.value:
            del self._data[key]

        return removed

    def smembers(self, key: str) -> set[str]:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return set()

        if entry.data_type != DataType.SET:
            raise WrongTypeError("SMEMBERS requires a set key.")

        return set(entry.value)

    def sinter(self, *keys: str) -> set[str]:
        if not keys:
            raise ValidationError("At least one key is required.")

        result = self.smembers(keys[0])

        for key in keys[1:]:
            result.intersection_update(self.smembers(key))

        return result

    def sunion(self, *keys: str) -> set[str]:
        result = set()

        for key in keys:
            result.update(self.smembers(key))

        return result

    # SORTED SET OPERATIONS

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        entry = self._create(key, DataType.ZSET, {})

        added = 0

        for member, score in mapping.items():
            if not isinstance(member, str) or not member:
                raise ValidationError("Sorted-set members must be non-empty.")

            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise ValidationError("Scores must be numeric.")

            if not math.isfinite(score):
                raise ValidationError("Scores must be finite.")

            if member not in entry.value:
                added += 1

            entry.value[member] = float(score)

        return added

    def zrange(
        self,
        key: str,
        start: int = 0,
        stop: int = -1,
        with_scores: bool = False
    ) -> list:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return []

        if entry.data_type != DataType.ZSET:
            raise WrongTypeError("ZRANGE requires a sorted-set key.")

        ordered = sorted(
            entry.value.items(),
            key=lambda item: (item[1], item[0])
        )

        size = len(ordered)

        if start < 0:
            start = max(0, size + start)

        if stop < 0:
            stop = size + stop

        selected = ordered[start:stop + 1]

        if with_scores:
            return selected

        return [member for member, _ in selected]

    def zscore(self, key: str, member: str) -> float | None:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return None

        if entry.data_type != DataType.ZSET:
            raise WrongTypeError("ZSCORE requires a sorted-set key.")

        return entry.value.get(member)

    # GENERAL KEY OPERATIONS

    def exists(self, key: str) -> bool:
        self._validate_key(key)
        self._purge(key)
        return key in self._data

    def delete(self, *keys: str) -> int:
        deleted = 0

        for key in keys:
            self._validate_key(key)
            self._purge(key)

            if key in self._data:
                del self._data[key]
                deleted += 1

        return deleted

    def expire(self, key: str, seconds: float) -> bool:
        self._validate_key(key)

        if seconds <= 0 or not math.isfinite(seconds):
            raise ValidationError("Expiration must be positive and finite.")

        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return False

        entry.expires_at = time.monotonic() + seconds
        return True

    def ttl(self, key: str) -> int:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None:
            return -2

        if entry.expires_at is None:
            return -1

        return max(0, math.floor(entry.expires_at - time.monotonic()))

    def persist(self, key: str) -> bool:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        if entry is None or entry.expires_at is None:
            return False

        entry.expires_at = None
        return True

    def type(self, key: str) -> str:
        self._validate_key(key)
        self._purge(key)

        entry = self._data.get(key)

        return entry.data_type.value if entry else "none"

    def keys(self, pattern: str = "*") -> list[str]:
        for key in list(self._data):
            self._purge(key)

        return sorted(
            key for key in self._data
            if fnmatch.fnmatchcase(key, pattern)
        )

    def dbsize(self) -> int:
        self.keys()
        return len(self._data)

    # JSON PERSISTENCE

    def save(self, path: str | Path) -> None:
        """Save a snapshot. This is not a replacement for Redis RDB/AOF."""

        target = Path(path)

        payload = {}

        for key in self.keys():
            entry = self._data[key]

            if entry.data_type == DataType.SET:
                value = sorted(entry.value)
            else:
                value = entry.value

            payload[key] = {
                "type": entry.data_type.value,
                "value": value,
                "remaining_ttl": (
                    max(0, entry.expires_at - time.monotonic())
                    if entry.expires_at is not None else None
                )
            }

        target.parent.mkdir(parents=True, exist_ok=True)

        # Atomic replacement prevents a partially written snapshot.
        temporary = target.with_suffix(target.suffix + ".tmp")

        try:
            temporary.write_text(
                json.dumps(payload, allow_nan=False, indent=2),
                encoding="utf-8"
            )
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def load(self, path: str | Path) -> None:
        """Validate a complete snapshot before replacing existing data."""

        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))

        if not isinstance(payload, dict):
            raise ValidationError("Invalid snapshot format.")

        replacement: dict[str, Entry] = {}

        for key, item in payload.items():
            self._validate_key(key)

            if not isinstance(item, dict):
                raise ValidationError("Invalid snapshot entry.")

            data_type = DataType(item["type"])
            value = item["value"]
            remaining = item["remaining_ttl"]

            if data_type == DataType.STRING:
                valid = isinstance(value, str)
            elif data_type == DataType.HASH:
                valid = isinstance(value, dict) and all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in value.items()
                )
            elif data_type == DataType.LIST:
                valid = isinstance(value, list) and all(
                    isinstance(v, str) for v in value
                )
            elif data_type == DataType.SET:
                valid = isinstance(value, list) and all(
                    isinstance(v, str) for v in value
                )
                value = set(value) if valid else value
            else:
                valid = isinstance(value, dict)

                if valid:
                    valid = all(
                        isinstance(member, str)
                        and isinstance(score, (int, float))
                        and not isinstance(score, bool)
                        and math.isfinite(score)
                        for member, score in value.items()
                    )

            if not valid:
                raise ValidationError(f"Invalid value for key {key}.")

            if remaining is not None:
                if (
                    isinstance(remaining, bool)
                    or not isinstance(remaining, (int, float))
                    or not math.isfinite(remaining)
                    or remaining <= 0
                ):
                    continue

                expires_at = time.monotonic() + remaining
            else:
                expires_at = None

            replacement[key] = Entry(
                data_type,
                value,
                expires_at
            )

        self._data = replacement


def demonstration() -> None:
    redis = RedisStore()

    print("\n=== STRING ===")
    redis.set("site:name", "Redis Fundamentals")
    redis.set("counter", "10")
    print("Name:", redis.get("site:name"))
    print("Counter:", redis.incr("counter", 5))

    print("\n=== HASH ===")
    redis.hset("user:1001", "name", "Atul")
    redis.hset("user:1001", "role", "developer")
    redis.hset("user:1001", "status", "active")
    print("User:", redis.hgetall("user:1001"))

    print("\n=== LIST ===")
    redis.rpush("tasks", "design", "develop", "test")
    redis.lpush("tasks", "planning")
    print("Tasks:", redis.lrange("tasks", 0, -1))
    print("Removed:", redis.lpop("tasks"))

    print("\n=== SET ===")
    redis.sadd("developers", "A", "B", "C")
    redis.sadd("reviewers", "B", "C", "D")
    print("Developers:", sorted(redis.smembers("developers")))
    print("Intersection:", sorted(
        redis.sinter("developers", "reviewers")
    ))
    print("Union:", sorted(
        redis.sunion("developers", "reviewers")
    ))

    print("\n=== SORTED SET ===")
    redis.zadd("leaderboard", {
        "Alice": 950,
        "Bob": 850,
        "Charlie": 900
    })
    print("Leaderboard:", redis.zrange(
        "leaderboard", 0, -1, with_scores=True
    ))
    print("Alice score:", redis.zscore("leaderboard", "Alice"))

    print("\n=== EXPIRATION ===")
    redis.set("session:1001", "authenticated")
    redis.expire("session:1001", 60)
    print("Session TTL:", redis.ttl("session:1001"))

    print("\n=== KEY MANAGEMENT ===")
    print("User keys:", redis.keys("user:*"))
    print("Database size:", redis.dbsize())
    print("Key type:", redis.type("user:1001"))

    print("\n=== PERSISTENCE ===")

    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory) / "redis_snapshot.json"
        redis.save(snapshot)

        restored = RedisStore()
        restored.load(snapshot)

        print("Restored name:", restored.get("site:name"))
        print("Restored user:", restored.hgetall("user:1001"))


class RedisStoreTests(unittest.TestCase):

    def setUp(self):
        self.redis = RedisStore()

    def test_string(self):
        self.assertTrue(self.redis.set("counter", "10"))
        self.assertEqual(self.redis.incr("counter", 5), 15)
        self.assertEqual(self.redis.get("counter"), "15")

    def test_nx(self):
        self.assertTrue(self.redis.set("lock", "owner", nx=True))
        self.assertFalse(self.redis.set("lock", "other", nx=True))

    def test_hash(self):
        self.redis.hset("user", "name", "Atul")
        self.assertEqual(self.redis.hget("user", "name"), "Atul")

    def test_list(self):
        self.redis.rpush("queue", "A", "B")
        self.redis.lpush("queue", "C")
        self.assertEqual(
            self.redis.lrange("queue", 0, -1),
            ["C", "A", "B"]
        )

    def test_set(self):
        self.redis.sadd("A", "x", "y")
        self.redis.sadd("B", "y", "z")
        self.assertEqual(self.redis.sinter("A", "B"), {"y"})

    def test_sorted_set(self):
        self.redis.zadd("scores", {"A": 10, "B": 20})
        self.assertEqual(self.redis.zrange("scores"), ["A", "B"])

    def test_wrong_type(self):
        self.redis.set("key", "value")

        with self.assertRaises(WrongTypeError):
            self.redis.hgetall("key")

    def test_missing_key(self):
        self.assertIsNone(self.redis.get("missing"))
        self.assertEqual(self.redis.ttl("missing"), -2)

    def test_expiration(self):
        self.redis.set("temporary", "value")
        self.redis.expire("temporary", 0.02)
        time.sleep(0.04)
        self.assertFalse(self.redis.exists("temporary"))

    def test_delete(self):
        self.redis.set("a", "1")
        self.redis.set("b", "2")
        self.assertEqual(self.redis.delete("a", "b", "c"), 2)

    def test_non_finite_score(self):
        with self.assertRaises(ValidationError):
            self.redis.zadd("ranking", {"A": float("nan")})

    def test_atomic_snapshot_restore(self):
        self.redis.set("key", "value")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            self.redis.save(path)

            restored = RedisStore()
            restored.load(path)

            self.assertEqual(restored.get("key"), "value")


if __name__ == "__main__":
    demonstration()

    print("\n=== AUTOMATED TESTS ===")
    unittest.main(argv=["redis_fundamentals.py"], exit=False)
