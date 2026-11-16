"""
Redis Caching: Cache-Aside, Write-Through, TTL, and Cache Invalidation.

Self-contained simulation of Redis caching using Python's standard library.
The implementation includes expiration, concurrency control, cache metrics,
source-of-truth storage, invalidation, and failure handling.

Run:
    python redis_caching.py
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("redis-caching")


class CacheStrategy(Enum):
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"


class CacheError(Exception):
    """Base exception for cache-related failures."""


class CacheUnavailable(CacheError):
    """Raised when the cache service is unavailable."""


class ValidationError(CacheError):
    """Raised when cache input is invalid."""


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    expires_at: Optional[float]
    version: int = 1

    def is_expired(self, current_time: float) -> bool:
        return (
            self.expires_at is not None
            and current_time >= self.expires_at
        )


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    invalidations: int = 0
    expirations: int = 0
    errors: int = 0
    origin_reads: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class RedisCacheSimulator:
    """
    Thread-safe in-memory Redis-style cache.

    TTL is measured using monotonic time to avoid system-clock changes.
    A production Redis deployment should use native Redis expiration.
    """

    def __init__(self, default_ttl: int = 30):
        if default_ttl <= 0:
            raise ValidationError("Default TTL must be positive.")

        self.default_ttl = default_ttl
        self._data: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._available = True
        self.metrics = CacheMetrics()

    def set_available(self, available: bool) -> None:
        with self._lock:
            self._available = available

    def _check_available(self) -> None:
        if not self._available:
            self.metrics.errors += 1
            raise CacheUnavailable("Cache service is unavailable.")

    @staticmethod
    def validate_key(key: str) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValidationError("Cache key cannot be empty.")

        if len(key) > 512:
            raise ValidationError("Cache key exceeds 512 characters.")

        if any(ord(char) < 32 for char in key):
            raise ValidationError("Cache key contains control characters.")

    def get(self, key: str) -> Optional[Any]:
        self.validate_key(key)

        with self._lock:
            self._check_available()
            entry = self._data.get(key)

            if entry is None:
                self.metrics.misses += 1
                return None

            if entry.is_expired(time.monotonic()):
                del self._data[key]
                self.metrics.expirations += 1
                self.metrics.misses += 1
                return None

            self.metrics.hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        version: int = 1
    ) -> None:
        self.validate_key(key)

        effective_ttl = self.default_ttl if ttl is None else ttl

        if effective_ttl <= 0:
            raise ValidationError("TTL must be positive.")

        if version < 1:
            raise ValidationError("Version must be positive.")

        with self._lock:
            self._check_available()

            now = time.monotonic()

            self._data[key] = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + effective_ttl,
                version=version
            )

            self.metrics.writes += 1

    def delete(self, key: str) -> bool:
        self.validate_key(key)

        with self._lock:
            self._check_available()

            deleted = self._data.pop(key, None) is not None

            if deleted:
                self.metrics.invalidations += 1

            return deleted

    def delete_pattern(self, prefix: str) -> int:
        """Delete matching keys without exposing unrestricted key access."""

        self.validate_key(prefix)

        with self._lock:
            self._check_available()

            matching = [
                key for key in self._data
                if key.startswith(prefix)
            ]

            for key in matching:
                del self._data[key]

            self.metrics.invalidations += len(matching)
            return len(matching)

    def cleanup_expired(self) -> int:
        with self._lock:
            self._check_available()

            now = time.monotonic()

            expired = [
                key for key, entry in self._data.items()
                if entry.is_expired(now)
            ]

            for key in expired:
                del self._data[key]

            self.metrics.expirations += len(expired)
            return len(expired)

    def export_metrics(self) -> dict[str, Any]:
        return {
            **asdict(self.metrics),
            "hit_rate": round(self.metrics.hit_rate, 4),
            "current_entries": len(self._data)
        }


class ProductRepository:
    """Represents the authoritative database."""

    def __init__(self):
        self._products: dict[int, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._next_id = 1
        self.read_count = 0

    def create(self, name: str, price: float) -> dict[str, Any]:
        if not name.strip():
            raise ValidationError("Product name is required.")

        if price < 0:
            raise ValidationError("Price cannot be negative.")

        with self._lock:
            product = {
                "id": self._next_id,
                "name": name,
                "price": round(price, 2),
                "version": 1
            }

            self._products[self._next_id] = product
            self._next_id += 1

            return product.copy()

    def get(self, product_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            self.read_count += 1
            product = self._products.get(product_id)

            return product.copy() if product else None

    def update(
        self,
        product_id: int,
        name: str,
        price: float
    ) -> Optional[dict[str, Any]]:
        if not name.strip() or price < 0:
            raise ValidationError("Invalid product update.")

        with self._lock:
            product = self._products.get(product_id)

            if product is None:
                return None

            product["name"] = name
            product["price"] = round(price, 2)
            product["version"] += 1

            return product.copy()

    def delete(self, product_id: int) -> bool:
        with self._lock:
            return self._products.pop(product_id, None) is not None


class CacheService:
    """
    Implements cache-aside and write-through strategies.

    Cache-aside:
        Read cache -> read database on miss -> populate cache.

    Write-through:
        Update database -> update cache.

    Cache invalidation is used after source changes when immediate
    consistency cannot be guaranteed by the selected write strategy.
    """

    def __init__(
        self,
        repository: ProductRepository,
        cache: RedisCacheSimulator
    ):
        self.repository = repository
        self.cache = cache
        self._key_locks: defaultdict[str, threading.Lock] = defaultdict(
            threading.Lock
        )

    @staticmethod
    def product_key(product_id: int) -> str:
        if product_id <= 0:
            raise ValidationError("Product ID must be positive.")

        return f"products:{product_id}"

    def get_product(
        self,
        product_id: int,
        strategy: CacheStrategy = CacheStrategy.CACHE_ASIDE
    ) -> Optional[dict[str, Any]]:
        key = self.product_key(product_id)

        try:
            cached = self.cache.get(key)

            if cached is not None:
                return cached

        except CacheUnavailable:
            logger.warning("Cache unavailable. Reading source database.")

            return self.repository.get(product_id)

        # Prevent multiple concurrent requests from loading the same key.
        with self._key_locks[key]:
            try:
                cached = self.cache.get(key)

                if cached is not None:
                    return cached

            except CacheUnavailable:
                return self.repository.get(product_id)

            self.cache.metrics.origin_reads += 1
            product = self.repository.get(product_id)

            if product is not None:
                try:
                    self.cache.set(
                        key,
                        product,
                        ttl=30,
                        version=product["version"]
                    )
                except CacheUnavailable:
                    logger.warning("Cache population failed.")

            return product

    def update_product(
        self,
        product_id: int,
        name: str,
        price: float,
        strategy: CacheStrategy
    ) -> Optional[dict[str, Any]]:
        updated = self.repository.update(product_id, name, price)

        if updated is None:
            return None

        key = self.product_key(product_id)

        if strategy == CacheStrategy.WRITE_THROUGH:
            try:
                self.cache.set(
                    key,
                    updated,
                    ttl=30,
                    version=updated["version"]
                )
            except CacheUnavailable:
                # Database remains authoritative. Invalidate when possible.
                logger.error(
                    "Write-through cache update failed for %s.",
                    key
                )

                try:
                    self.cache.delete(key)
                except CacheUnavailable:
                    logger.error("Cache invalidation also failed.")

        elif strategy == CacheStrategy.CACHE_ASIDE:
            try:
                self.cache.delete(key)
            except CacheUnavailable:
                logger.error(
                    "Cache invalidation failed for %s. "
                    "A stale entry may remain until expiration.",
                    key
                )

        else:
            raise ValidationError("Unsupported caching strategy.")

        return updated

    def delete_product(self, product_id: int) -> bool:
        deleted = self.repository.delete(product_id)

        if deleted:
            try:
                self.cache.delete(self.product_key(product_id))
            except CacheUnavailable:
                logger.error("Deletion invalidation failed.")

        return deleted


def save_metrics(
    metrics: dict[str, Any],
    filename: str = "redis_cache_metrics.json"
) -> None:
    """Persist operational metrics using an atomic file replacement."""

    destination = Path(filename)
    temporary = destination.with_suffix(".tmp")

    try:
        temporary.write_text(
            json.dumps(metrics, indent=4),
            encoding="utf-8"
        )
        temporary.replace(destination)

    except OSError as error:
        logger.error("Metrics persistence failed: %s", error)


def demonstrate() -> None:
    repository = ProductRepository()
    cache = RedisCacheSimulator(default_ttl=30)
    service = CacheService(repository, cache)

    print("\nREDIS CACHING DEMONSTRATION")
    print("=" * 55)

    # 1. Create authoritative source records.
    product = repository.create("Enterprise Laptop", 85000)
    product_id = product["id"]

    print("\n1. Created database record:")
    print(product)

    # 2. Cache-aside: initial database load.
    print("\n2. Cache-aside initial read:")
    first = service.get_product(product_id)
    print(first)

    # 3. Cache-aside: subsequent cache hit.
    print("\n3. Cache-aside repeated read:")
    second = service.get_product(product_id)
    print(second)

    # 4. Write-through: update database and cache.
    print("\n4. Write-through update:")
    updated = service.update_product(
        product_id,
        "Enterprise Laptop Pro",
        95000,
        CacheStrategy.WRITE_THROUGH
    )
    print(updated)

    print("\n5. Read after write-through:")
    print(service.get_product(product_id))

    # 6. Cache-aside invalidation.
    print("\n6. Cache-aside update and invalidation:")
    service.update_product(
        product_id,
        "Enterprise Laptop Ultra",
        105000,
        CacheStrategy.CACHE_ASIDE
    )
    print(service.get_product(product_id))

    # 7. Cache expiration demonstration.
    print("\n7. TTL expiration:")
    cache.set("temporary:session", {"user": "employee"}, ttl=1)
    print("Before expiration:", cache.get("temporary:session"))

    time.sleep(1.1)

    print("After expiration:", cache.get("temporary:session"))

    # 8. Cache failure and database fallback.
    print("\n8. Cache outage:")
    cache.set_available(False)

    fallback = service.get_product(product_id)
    print("Database fallback:", fallback)

    cache.set_available(True)

    # 9. Explicit invalidation.
    print("\n9. Explicit invalidation:")
    cache.set("products:999", {"id": 999}, ttl=30)
    print("Deleted:", cache.delete("products:999"))

    # 10. Source deletion.
    print("\n10. Product deletion:")
    print("Deleted:", service.delete_product(product_id))

    # 11. Operational metrics.
    print("\n11. Cache metrics:")
    metrics = cache.export_metrics()

    for key, value in metrics.items():
        print(f"{key}: {value}")

    save_metrics(metrics)

    # 12. Basic correctness assertions.
    assert repository.get(product_id) is None
    assert metrics["hits"] >= 1
    assert metrics["misses"] >= 1
    assert metrics["hit_rate"] >= 0

    print("\nAll demonstration assertions passed.")


if __name__ == "__main__":
    demonstrate()
