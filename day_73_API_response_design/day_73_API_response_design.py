#!/usr/bin/env python3
"""
API Response Design: Envelopes, Metadata, Consistency, and Error Schemas.

A self-contained API response simulation using only the Python standard library.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Any, Generic, TypeVar


T = TypeVar("T")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("api-response-design")


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


@dataclass(frozen=True)
class APIError:
    code: ErrorCode
    message: str
    details: tuple[dict[str, Any], ...] = ()
    retryable: bool = False


@dataclass(frozen=True)
class ResponseMetadata:
    request_id: str
    timestamp: str
    api_version: str
    duration_ms: float
    pagination: dict[str, Any] | None = None
    links: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class APIResponse(Generic[T]):
    success: bool
    data: T | None
    error: APIError | None
    metadata: ResponseMetadata

    def __post_init__(self) -> None:
        if self.success and self.error is not None:
            raise ValueError("Successful responses cannot contain errors.")
        if not self.success and self.error is None:
            raise ValueError("Failed responses must contain an error.")
        if not self.success and self.data is not None:
            raise ValueError("Failed responses cannot contain success data.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": (
                {
                    "code": self.error.code.value,
                    "message": self.error.message,
                    "details": list(self.error.details),
                    "retryable": self.error.retryable,
                }
                if self.error
                else None
            ),
            "metadata": asdict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            indent=2,
            default=str,
            ensure_ascii=False,
        )


class APIException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status: HTTPStatus,
        details: tuple[dict[str, Any], ...] = (),
        retryable: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details
        self.retryable = retryable


class ProductRepository:
    """In-memory repository demonstrating consistent resource operations."""

    def __init__(self):
        self._products: dict[int, dict[str, Any]] = {
            101: {
                "id": 101,
                "name": "Enterprise Laptop",
                "price": 85000.00,
                "currency": "INR",
                "version": 1,
            },
            102: {
                "id": 102,
                "name": "Network Firewall",
                "price": 125000.00,
                "currency": "INR",
                "version": 1,
            },
            103: {
                "id": 103,
                "name": "Secure Storage",
                "price": 45000.00,
                "currency": "INR",
                "version": 1,
            },
        }

    def get(self, product_id: int) -> dict[str, Any]:
        product = self._products.get(product_id)
        if product is None:
            raise APIException(
                ErrorCode.RESOURCE_NOT_FOUND,
                "Product does not exist.",
                HTTPStatus.NOT_FOUND,
            )
        return dict(product)

    def list(
        self,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise APIException(
                ErrorCode.VALIDATION_ERROR,
                "Invalid pagination parameters.",
                HTTPStatus.BAD_REQUEST,
                (
                    {
                        "field": "page_size",
                        "reason": "Must be between 1 and 100.",
                    },
                ),
            )

        products = sorted(
            self._products.values(),
            key=lambda item: item["id"],
        )
        start = (page - 1) * page_size
        return [
            dict(item)
            for item in products[start:start + page_size]
        ], len(products)

    def update_price(
        self,
        product_id: int,
        price: float,
        expected_version: int,
    ) -> dict[str, Any]:
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            raise APIException(
                ErrorCode.VALIDATION_ERROR,
                "Price must be numeric.",
                HTTPStatus.BAD_REQUEST,
            )

        if price <= 0:
            raise APIException(
                ErrorCode.VALIDATION_ERROR,
                "Price must be positive.",
                HTTPStatus.BAD_REQUEST,
            )

        product = self.get(product_id)

        # Optimistic concurrency prevents overwriting a newer version.
        if product["version"] != expected_version:
            raise APIException(
                ErrorCode.CONFLICT,
                "The resource has changed since it was retrieved.",
                HTTPStatus.CONFLICT,
                (
                    {
                        "field": "version",
                        "expected": expected_version,
                        "actual": product["version"],
                    },
                ),
            )

        product["price"] = round(float(price), 2)
        product["version"] += 1
        self._products[product_id] = product
        return dict(product)


class ResponseFactory:
    API_VERSION = "v1"

    @staticmethod
    def create_metadata(
        request_id: str,
        started_at: float,
        pagination: dict[str, Any] | None = None,
        links: dict[str, str] | None = None,
    ) -> ResponseMetadata:
        return ResponseMetadata(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            api_version=ResponseFactory.API_VERSION,
            duration_ms=round(
                (time.perf_counter() - started_at) * 1000,
                3,
            ),
            pagination=pagination,
            links=links or {},
        )

    @classmethod
    def success(
        cls,
        data: T,
        request_id: str,
        started_at: float,
        pagination: dict[str, Any] | None = None,
        links: dict[str, str] | None = None,
    ) -> APIResponse[T]:
        return APIResponse(
            success=True,
            data=data,
            error=None,
            metadata=cls.create_metadata(
                request_id,
                started_at,
                pagination,
                links,
            ),
        )

    @classmethod
    def failure(
        cls,
        exception: APIException,
        request_id: str,
        started_at: float,
    ) -> tuple[HTTPStatus, APIResponse[None]]:
        response = APIResponse(
            success=False,
            data=None,
            error=APIError(
                code=exception.code,
                message=exception.message,
                details=exception.details,
                retryable=exception.retryable,
            ),
            metadata=cls.create_metadata(
                request_id,
                started_at,
            ),
        )
        return exception.status, response


class APIService:
    def __init__(self, repository: ProductRepository):
        self.repository = repository

    def execute(
        self,
        operation,
    ) -> tuple[HTTPStatus, APIResponse[Any]]:
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())

        try:
            result = operation()
            return HTTPStatus.OK, ResponseFactory.success(
                result,
                request_id,
                started_at,
            )

        except APIException as exc:
            logger.warning(
                "Request %s failed: %s",
                request_id,
                exc.code.value,
            )
            return ResponseFactory.failure(
                exc,
                request_id,
                started_at,
            )

        except Exception:
            # Never expose internal exception messages or stack traces.
            logger.exception("Unexpected failure: %s", request_id)

            safe_error = APIException(
                ErrorCode.INTERNAL_ERROR,
                "An unexpected server error occurred.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return ResponseFactory.failure(
                safe_error,
                request_id,
                started_at,
            )

    def get_product(self, product_id: int):
        return self.execute(
            lambda: self.repository.get(product_id)
        )

    def list_products(self, page: int = 1, page_size: int = 10):
        started = time.perf_counter()
        request_id = str(uuid.uuid4())

        try:
            products, total = self.repository.list(page, page_size)
            pages = (total + page_size - 1) // page_size

            response = ResponseFactory.success(
                products,
                request_id,
                started,
                pagination={
                    "page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": pages,
                    "has_next": page < pages,
                    "has_previous": page > 1,
                },
                links={
                    "self": f"/api/v1/products?page={page}",
                    "first": "/api/v1/products?page=1",
                    "last": f"/api/v1/products?page={pages}",
                },
            )
            return HTTPStatus.OK, response

        except APIException as exc:
            return ResponseFactory.failure(
                exc,
                request_id,
                started,
            )

    def update_price(
        self,
        product_id: int,
        price: float,
        expected_version: int,
    ):
        return self.execute(
            lambda: self.repository.update_price(
                product_id,
                price,
                expected_version,
            )
        )


def validate_response(response: APIResponse[Any]) -> None:
    """Check response-envelope invariants."""
    serialized = response.to_dict()

    required = {"success", "data", "error", "metadata"}
    assert set(serialized) == required

    if serialized["success"]:
        assert serialized["error"] is None
    else:
        assert serialized["data"] is None
        assert serialized["error"] is not None

    metadata = serialized["metadata"]
    assert metadata["request_id"]
    assert metadata["api_version"]
    assert metadata["timestamp"]


def demonstrate() -> None:
    repository = ProductRepository()
    service = APIService(repository)

    scenarios = [
        (
            "Successful retrieval",
            service.get_product(101),
        ),
        (
            "Missing resource",
            service.get_product(999),
        ),
        (
            "Paginated collection",
            service.list_products(page=1, page_size=2),
        ),
        (
            "Invalid pagination",
            service.list_products(page=0, page_size=10),
        ),
        (
            "Successful price update",
            service.update_price(101, 89000, 1),
        ),
        (
            "Stale update conflict",
            service.update_price(101, 92000, 1),
        ),
    ]

    for description, (status, response) in scenarios:
        validate_response(response)
        print(f"\n{'=' * 65}")
        print(description)
        print("HTTP status:", status.value)
        print(response.to_json())

    # Verify that the successful update incremented the version.
    product = repository.get(101)
    assert product["version"] == 2
    assert product["price"] == 89000.0

    # Verify that an invalid envelope cannot be constructed.
    try:
        APIResponse(
            success=True,
            data={"id": 1},
            error=APIError(
                ErrorCode.INTERNAL_ERROR,
                "Invalid state",
            ),
            metadata=ResponseMetadata(
                request_id="test",
                timestamp=datetime.now(timezone.utc).isoformat(),
                api_version="v1",
                duration_ms=0,
            ),
        )
        raise AssertionError("Invalid response was accepted.")
    except ValueError:
        print("\nEnvelope invariant validation passed.")

    print("\nAll API response design checks passed.")


if __name__ == "__main__":
    demonstrate()
