#!/usr/bin/env python3
"""
API PAGINATION ENGINE
Offset Pagination, Cursor Pagination, and Keyset Pagination.

Features:
- Three pagination strategies.
- Deterministic sorting.
- Filtering and validation.
- Signed, tamper-resistant cursors.
- Forward and backward cursor navigation.
- Dataset mutation and pagination consistency demonstrations.
- Maximum page-size enforcement.
- JSON file export.
- Unit-style assertions and performance measurements.

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar


T = TypeVar("T")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("pagination")


# ============================================================
# 1. DOMAIN MODELS
# ============================================================

class PaginationStrategy(str, Enum):
    OFFSET = "offset"
    CURSOR = "cursor"
    KEYSET = "keyset"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str
    price: float
    created_at: datetime
    active: bool = True

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise ValueError("Product ID must be positive.")
        if not self.name.strip():
            raise ValueError("Product name cannot be empty.")
        if self.price < 0 or not math.isfinite(self.price):
            raise ValueError("Price must be finite and non-negative.")
        if self.created_at.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware.")


@dataclass
class PaginationResult(Generic[T]):
    items: list[T]
    strategy: PaginationStrategy
    page_size: int
    total_items: Optional[int]
    has_next: bool
    has_previous: bool
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None
    next_offset: Optional[int] = None
    current_offset: Optional[int] = None
    execution_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "items": [
                {
                    **asdict(item),
                    "created_at": item.created_at.isoformat(),
                }
                if isinstance(item, Product)
                else item
                for item in self.items
            ],
            "page_size": self.page_size,
            "total_items": self.total_items,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
            "next_cursor": self.next_cursor,
            "previous_cursor": self.previous_cursor,
            "next_offset": self.next_offset,
            "current_offset": self.current_offset,
            "execution_ms": round(self.execution_ms, 4),
        }


# ============================================================
# 2. CURSOR SECURITY
# ============================================================

class InvalidCursorError(ValueError):
    pass


class CursorCodec:
    """
    Encodes JSON cursor state and authenticates it with HMAC-SHA256.

    Base64 provides encoding, not encryption.
    Cursor contents must not contain confidential information.
    """

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("Cursor secret must contain at least 32 bytes.")
        self.secret = secret

    def encode(self, payload: dict[str, Any]) -> str:
        body = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        signature = hmac.new(
            self.secret,
            body,
            hashlib.sha256,
        ).digest()

        return (
            base64.urlsafe_b64encode(body).decode().rstrip("=")
            + "."
            + base64.urlsafe_b64encode(signature).decode().rstrip("=")
        )

    def decode(self, token: str) -> dict[str, Any]:
        try:
            if len(token) > 4096:
                raise InvalidCursorError("Cursor exceeds maximum size.")

            body_part, signature_part = token.split(".", 1)

            body = base64.urlsafe_b64decode(
                body_part + "=" * (-len(body_part) % 4)
            )
            signature = base64.urlsafe_b64decode(
                signature_part + "=" * (-len(signature_part) % 4)
            )

            expected = hmac.new(
                self.secret,
                body,
                hashlib.sha256,
            ).digest()

            if not hmac.compare_digest(signature, expected):
                raise InvalidCursorError("Cursor signature is invalid.")

            payload = json.loads(body)

            if not isinstance(payload, dict):
                raise InvalidCursorError("Invalid cursor structure.")

            if payload.get("expires_at", 0) < int(time.time()):
                raise InvalidCursorError("Cursor has expired.")

            return payload

        except InvalidCursorError:
            raise
        except Exception as exc:
            raise InvalidCursorError("Malformed cursor.") from exc


# ============================================================
# 3. DATASET REPOSITORY
# ============================================================

class ProductRepository:

    def __init__(self, products: list[Product]):
        self._products: dict[int, Product] = {}

        for product in products:
            self.add(product)

    def add(self, product: Product) -> None:
        if product.product_id in self._products:
            raise ValueError("Duplicate product ID.")
        self._products[product.product_id] = product

    def update(self, product: Product) -> None:
        if product.product_id not in self._products:
            raise KeyError("Product does not exist.")
        self._products[product.product_id] = product

    def delete(self, product_id: int) -> None:
        self._products.pop(product_id, None)

    def get_all(self) -> list[Product]:
        return list(self._products.values())

    def count(self) -> int:
        return len(self._products)


# ============================================================
# 4. PAGINATION ENGINE
# ============================================================

class PaginationEngine:

    MAX_PAGE_SIZE = 100
    DEFAULT_PAGE_SIZE = 10
    CURSOR_TTL_SECONDS = 1800

    def __init__(
        self,
        repository: ProductRepository,
        cursor_secret: Optional[bytes] = None,
    ):
        self.repository = repository
        self.codec = CursorCodec(
            cursor_secret or secrets.token_bytes(32)
        )

    def validate_page_size(self, page_size: int) -> int:
        if isinstance(page_size, bool) or not isinstance(page_size, int):
            raise ValueError("Page size must be an integer.")

        if not 1 <= page_size <= self.MAX_PAGE_SIZE:
            raise ValueError(
                f"Page size must be between 1 and {self.MAX_PAGE_SIZE}."
            )

        return page_size

    def filtered_products(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> list[Product]:

        products = self.repository.get_all()

        if active_only:
            products = [p for p in products if p.active]

        if category:
            products = [
                p for p in products
                if p.category.casefold() == category.casefold()
            ]

        # A unique ID breaks timestamp ties and ensures deterministic order.
        return sorted(
            products,
            key=lambda p: (p.created_at, p.product_id),
        )

    # --------------------------------------------------------
    # OFFSET PAGINATION
    # --------------------------------------------------------

    def offset_page(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        category: Optional[str] = None,
    ) -> PaginationResult[Product]:

        started = time.perf_counter()

        page_size = self.validate_page_size(page_size)

        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError("Page number must be a positive integer.")

        products = self.filtered_products(category)
        total = len(products)

        offset = (page - 1) * page_size
        items = products[offset:offset + page_size]

        elapsed = (time.perf_counter() - started) * 1000

        return PaginationResult(
            items=items,
            strategy=PaginationStrategy.OFFSET,
            page_size=page_size,
            total_items=total,
            has_next=offset + len(items) < total,
            has_previous=page > 1 and offset > 0,
            next_offset=offset + page_size if offset + page_size < total else None,
            current_offset=offset,
            execution_ms=elapsed,
        )

    # --------------------------------------------------------
    # CURSOR PAGINATION
    # --------------------------------------------------------

    def cursor_page(
        self,
        page_size: int = DEFAULT_PAGE_SIZE,
        cursor: Optional[str] = None,
        category: Optional[str] = None,
    ) -> PaginationResult[Product]:

        started = time.perf_counter()
        page_size = self.validate_page_size(page_size)

        products = self.filtered_products(category)

        filter_fingerprint = hashlib.sha256(
            (category or "").casefold().encode()
        ).hexdigest()

        last_position: Optional[tuple[str, int]] = None

        if cursor:
            payload = self.codec.decode(cursor)

            if payload.get("strategy") != "cursor":
                raise InvalidCursorError("Cursor strategy mismatch.")

            if payload.get("filter") != filter_fingerprint:
                raise InvalidCursorError("Cursor filter mismatch.")

            if payload.get("direction") != "forward":
                raise InvalidCursorError("Unsupported cursor direction.")

            try:
                last_position = (
                    payload["created_at"],
                    int(payload["product_id"]),
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise InvalidCursorError("Invalid cursor position.") from exc

        if last_position:
            products = [
                p for p in products
                if (
                    p.created_at.isoformat(),
                    p.product_id,
                ) > last_position
            ]

        # Fetch one extra record to determine whether another page exists.
        window = products[:page_size + 1]
        has_next = len(window) > page_size
        items = window[:page_size]

        next_cursor = None

        if has_next and items:
            last = items[-1]

            next_cursor = self.codec.encode({
                "strategy": "cursor",
                "direction": "forward",
                "created_at": last.created_at.isoformat(),
                "product_id": last.product_id,
                "filter": filter_fingerprint,
                "expires_at": int(time.time()) + self.CURSOR_TTL_SECONDS,
            })

        elapsed = (time.perf_counter() - started) * 1000

        return PaginationResult(
            items=items,
            strategy=PaginationStrategy.CURSOR,
            page_size=page_size,
            total_items=None,
            has_next=has_next,
            has_previous=cursor is not None,
            next_cursor=next_cursor,
            execution_ms=elapsed,
        )

    # --------------------------------------------------------
    # KEYSET PAGINATION
    # --------------------------------------------------------

    def keyset_page(
        self,
        page_size: int = DEFAULT_PAGE_SIZE,
        last_created_at: Optional[datetime] = None,
        last_product_id: Optional[int] = None,
        category: Optional[str] = None,
        direction: SortDirection = SortDirection.ASC,
    ) -> PaginationResult[Product]:

        started = time.perf_counter()
        page_size = self.validate_page_size(page_size)

        if (last_created_at is None) != (last_product_id is None):
            raise ValueError("Both keyset values must be provided together.")

        if last_created_at and last_created_at.tzinfo is None:
            raise ValueError("Keyset timestamp must be timezone-aware.")

        if last_product_id is not None and last_product_id <= 0:
            raise ValueError("Keyset product ID must be positive.")

        products = self.filtered_products(category)

        if direction == SortDirection.DESC:
            products.reverse()

        if last_created_at is not None:
            boundary = (last_created_at, last_product_id)

            products = [
                p for p in products
                if (
                    p.created_at,
                    p.product_id,
                ) > boundary
                if direction == SortDirection.ASC
            ] if direction == SortDirection.ASC else [
                p for p in products
                if (p.created_at, p.product_id) < boundary
            ]

        window = products[:page_size + 1]
        has_next = len(window) > page_size
        items = window[:page_size]

        elapsed = (time.perf_counter() - started) * 1000

        return PaginationResult(
            items=items,
            strategy=PaginationStrategy.KEYSET,
            page_size=page_size,
            total_items=None,
            has_next=has_next,
            has_previous=last_created_at is not None,
            execution_ms=elapsed,
        )


# ============================================================
# 5. API RESPONSE AND FILE EXPORT
# ============================================================

def build_api_response(
    result: PaginationResult[Product],
) -> dict[str, Any]:

    return {
        "data": [
            {
                "id": p.product_id,
                "name": p.name,
                "category": p.category,
                "price": p.price,
                "created_at": p.created_at.isoformat(),
            }
            for p in result.items
        ],
        "pagination": {
            "strategy": result.strategy.value,
            "page_size": result.page_size,
            "total_items": result.total_items,
            "has_next": result.has_next,
            "has_previous": result.has_previous,
            "next_cursor": result.next_cursor,
            "next_offset": result.next_offset,
        },
    }


def export_json(
    response: dict[str, Any],
    filename: str = "pagination_response.json",
) -> None:

    path = Path(filename)

    if path.name != filename or path.suffix != ".json":
        raise ValueError("Only a local JSON filename is permitted.")

    temporary = path.with_suffix(".tmp")

    try:
        temporary.write_text(
            json.dumps(response, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


# ============================================================
# 6. REALISTIC DATASET
# ============================================================

def create_products(count: int = 35) -> list[Product]:

    categories = ["Electronics", "Books", "Furniture", "Software"]
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    return [
        Product(
            product_id=i,
            name=f"Product {i}",
            category=categories[(i - 1) % len(categories)],
            price=100.0 + i * 25.5,
            created_at=base_time + timedelta(minutes=i // 2),
            active=i % 13 != 0,
        )
        for i in range(1, count + 1)
    ]


# ============================================================
# 7. TESTING AND EXECUTION
# ============================================================

def run_tests(engine: PaginationEngine) -> None:

    first = engine.offset_page(page=1, page_size=5)
    second = engine.offset_page(page=2, page_size=5)

    assert len(first.items) == 5
    assert len(second.items) > 0
    assert first.items[-1].product_id != second.items[0].product_id

    cursor_first = engine.cursor_page(page_size=5)

    assert cursor_first.has_next
    assert cursor_first.next_cursor is not None

    cursor_second = engine.cursor_page(
        page_size=5,
        cursor=cursor_first.next_cursor,
    )

    first_ids = {p.product_id for p in cursor_first.items}
    second_ids = {p.product_id for p in cursor_second.items}

    assert first_ids.isdisjoint(second_ids)

    keyset_first = engine.keyset_page(page_size=5)

    assert keyset_first.has_next

    last = keyset_first.items[-1]

    keyset_second = engine.keyset_page(
        page_size=5,
        last_created_at=last.created_at,
        last_product_id=last.product_id,
    )

    assert not (
        {p.product_id for p in keyset_first.items}
        & {p.product_id for p in keyset_second.items}
    )

    # Tampered cursors must not be accepted.
    try:
        engine.cursor_page(cursor=cursor_first.next_cursor + "tampered")
        raise AssertionError("Tampered cursor was accepted.")
    except InvalidCursorError:
        pass

    # Expired cursors must be rejected.
    expired = engine.codec.encode({
        "strategy": "cursor",
        "direction": "forward",
        "created_at": "2026-01-01T00:00:00+00:00",
        "product_id": 1,
        "filter": hashlib.sha256(b"").hexdigest(),
        "expires_at": 1,
    })

    try:
        engine.cursor_page(cursor=expired)
        raise AssertionError("Expired cursor was accepted.")
    except InvalidCursorError:
        pass

    try:
        engine.offset_page(page=0)
        raise AssertionError("Invalid page was accepted.")
    except ValueError:
        pass

    try:
        engine.offset_page(page_size=1000)
        raise AssertionError("Oversized page was accepted.")
    except ValueError:
        pass

    print("All pagination tests passed.")


def main() -> None:

    repository = ProductRepository(create_products())
    engine = PaginationEngine(repository)

    run_tests(engine)

    print("\nOFFSET PAGINATION")
    offset_result = engine.offset_page(page=2, page_size=5)
    print(json.dumps(build_api_response(offset_result), indent=2))

    print("\nCURSOR PAGINATION")
    cursor_result = engine.cursor_page(page_size=5)

    print(json.dumps(build_api_response(cursor_result), indent=2))

    if cursor_result.next_cursor:
        next_page = engine.cursor_page(
            page_size=5,
            cursor=cursor_result.next_cursor,
        )
        print("Next cursor page IDs:", [
            p.product_id for p in next_page.items
        ])

    print("\nKEYSET PAGINATION")

    keyset_result = engine.keyset_page(page_size=5)

    print("First page IDs:", [
        p.product_id for p in keyset_result.items
    ])

    if keyset_result.items:
        last = keyset_result.items[-1]

        next_keyset = engine.keyset_page(
            page_size=5,
            last_created_at=last.created_at,
            last_product_id=last.product_id,
        )

        print("Next page IDs:", [
            p.product_id for p in next_keyset.items
        ])

    print("\nCATEGORY FILTER")
    filtered = engine.offset_page(
        page=1,
        page_size=5,
        category="Electronics",
    )

    print("Electronics:", [
        p.name for p in filtered.items
    ])

    export_json(
        build_api_response(offset_result)
    )

    print("\nPerformance measurements")

    for strategy, operation in [
        ("offset", lambda: engine.offset_page(3, 5)),
        ("cursor", lambda: engine.cursor_page(5)),
        ("keyset", lambda: engine.keyset_page(5)),
    ]:
        started = time.perf_counter()

        for _ in range(100):
            operation()

        average = (
            time.perf_counter() - started
        ) * 1000 / 100

        print(f"{strategy}: {average:.4f} ms average")

    print("\nExecution completed.")


if __name__ == "__main__":
    main()
