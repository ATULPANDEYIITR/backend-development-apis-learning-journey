from __future__ import annotations

import json
import logging
import sqlite3
import unittest
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("catalog_search")


class SearchError(Exception):
    """Base exception for search operations."""


class ValidationError(SearchError):
    """Raised when search parameters are invalid."""


class SortField(str, Enum):
    NAME = "name"
    PRICE = "price"
    CATEGORY = "category"
    RATING = "rating"
    CREATED_AT = "created_at"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class SearchCriteria:
    keyword: Optional[str] = None
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    active_only: bool = True
    sort_by: SortField = SortField.NAME
    direction: SortDirection = SortDirection.ASC
    limit: int = 10
    offset: int = 0


@dataclass
class Product:
    id: int
    name: str
    category: str
    price: float
    rating: float
    active: bool
    created_at: str


class CatalogDatabase:
    """SQLite repository with parameterized dynamic query construction."""

    ALLOWED_COLUMNS = {
        "name": "name",
        "price": "price",
        "category": "category",
        "rating": "rating",
        "created_at": "created_at"
    }

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                rating REAL NOT NULL CHECK(rating BETWEEN 0 AND 5),
                active INTEGER NOT NULL CHECK(active IN (0, 1)),
                created_at TEXT NOT NULL
            )
        """)

        self.connection.execute("""
            CREATE INDEX idx_products_category
            ON products(category)
        """)

        self.connection.execute("""
            CREATE INDEX idx_products_price
            ON products(price)
        """)

        self.connection.execute("""
            CREATE INDEX idx_products_active_category
            ON products(active, category)
        """)

        self.connection.execute("""
            CREATE INDEX idx_products_rating
            ON products(rating)
        """)

        self.connection.executemany("""
            INSERT INTO products
            (id, name, category, price, rating, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (1, "Laptop Pro", "Electronics", 95000, 4.8, 1, "2026-01-10"),
            (2, "Wireless Mouse", "Electronics", 1200, 4.2, 1, "2026-02-15"),
            (3, "Mechanical Keyboard", "Electronics", 4500, 4.6, 1, "2026-03-01"),
            (4, "Office Chair", "Furniture", 12500, 4.3, 1, "2026-03-12"),
            (5, "Standing Desk", "Furniture", 22000, 4.7, 1, "2026-04-10"),
            (6, "Old Monitor", "Electronics", 8000, 3.5, 0, "2025-12-01"),
            (7, "Notebook", "Stationery", 100, 4.0, 1, "2026-05-01"),
            (8, "Premium Headphones", "Electronics", 6500, 4.9, 1, "2026-06-01"),
            (9, "Desk Lamp", "Furniture", 1800, 3.9, 1, "2026-06-15"),
            (10, "USB Hub", "Electronics", 1500, 4.1, 1, "2026-07-01")
        ])

        self.connection.commit()

    @staticmethod
    def validate(criteria: SearchCriteria) -> None:
        if not isinstance(criteria.sort_by, SortField):
            raise ValidationError("Invalid sorting field.")

        if not isinstance(criteria.direction, SortDirection):
            raise ValidationError("Invalid sorting direction.")

        if criteria.limit < 1 or criteria.limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

        if criteria.offset < 0:
            raise ValidationError("Offset cannot be negative.")

        for field, value in (
            ("minimum price", criteria.min_price),
            ("maximum price", criteria.max_price)
        ):
            if value is not None and value < 0:
                raise ValidationError(f"{field} cannot be negative.")

        if (
            criteria.min_price is not None
            and criteria.max_price is not None
            and criteria.min_price > criteria.max_price
        ):
            raise ValidationError("Minimum price exceeds maximum price.")

        if criteria.min_rating is not None:
            if not 0 <= criteria.min_rating <= 5:
                raise ValidationError("Rating must be between 0 and 5.")

        if criteria.keyword is not None and len(criteria.keyword) > 100:
            raise ValidationError("Keyword exceeds 100 characters.")

        if criteria.category is not None and len(criteria.category) > 80:
            raise ValidationError("Category exceeds 80 characters.")

    def build_query(
        self,
        criteria: SearchCriteria
    ) -> tuple[str, list[Any]]:
        """Build SQL structure dynamically while binding all user values."""

        self.validate(criteria)

        conditions = []
        parameters: list[Any] = []

        if criteria.active_only:
            conditions.append("active = ?")
            parameters.append(1)

        if criteria.keyword:
            conditions.append(
                "(LOWER(name) LIKE LOWER(?) OR LOWER(category) LIKE LOWER(?))"
            )
            pattern = f"%{criteria.keyword.strip()}%"
            parameters.extend([pattern, pattern])

        if criteria.category:
            conditions.append("LOWER(category) = LOWER(?)")
            parameters.append(criteria.category.strip())

        if criteria.min_price is not None:
            conditions.append("price >= ?")
            parameters.append(criteria.min_price)

        if criteria.max_price is not None:
            conditions.append("price <= ?")
            parameters.append(criteria.max_price)

        if criteria.min_rating is not None:
            conditions.append("rating >= ?")
            parameters.append(criteria.min_rating)

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        # Identifiers and directions are selected only from trusted enums.
        sort_column = self.ALLOWED_COLUMNS[criteria.sort_by.value]
        direction = criteria.direction.value.upper()

        sql = f"""
            SELECT *
            FROM products
            {where_clause}
            ORDER BY {sort_column} {direction}, id ASC
            LIMIT ? OFFSET ?
        """

        parameters.extend([criteria.limit, criteria.offset])

        return sql, parameters

    def search(
        self,
        criteria: SearchCriteria
    ) -> dict[str, Any]:
        sql, parameters = self.build_query(criteria)

        count_sql = "SELECT COUNT(*) FROM products"
        count_parameters = parameters[:-2]

        where_clause = sql.split("ORDER BY")[0]
        count_sql = (
            "SELECT COUNT(*) FROM products "
            + where_clause.split("FROM products", 1)[1]
        )

        try:
            rows = self.connection.execute(sql, parameters).fetchall()
            total = self.connection.execute(
                count_sql, count_parameters
            ).fetchone()[0]

            products = [dict(row) for row in rows]

            return {
                "results": products,
                "total": total,
                "limit": criteria.limit,
                "offset": criteria.offset,
                "has_next": criteria.offset + len(products) < total
            }

        except sqlite3.Error:
            logger.exception("Database search failed.")
            raise SearchError("Unable to execute catalog search.")

    def close(self) -> None:
        self.connection.close()


class SearchService:
    """Application-level search operations."""

    def __init__(self, repository: CatalogDatabase):
        self.repository = repository

    def search(self, **kwargs: Any) -> dict[str, Any]:
        try:
            if "sort_by" in kwargs:
                kwargs["sort_by"] = SortField(kwargs["sort_by"])

            if "direction" in kwargs:
                kwargs["direction"] = SortDirection(kwargs["direction"])

            criteria = SearchCriteria(**kwargs)
            return self.repository.search(criteria)

        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        except TypeError as exc:
            raise ValidationError("Invalid search parameter.") from exc

    def search_all_pages(
        self,
        keyword: Optional[str] = None,
        page_size: int = 5
    ) -> list[dict[str, Any]]:
        if not 1 <= page_size <= 100:
            raise ValidationError("Invalid page size.")

        results = []
        offset = 0

        while True:
            response = self.search(
                keyword=keyword,
                limit=page_size,
                offset=offset
            )

            results.extend(response["results"])

            if not response["has_next"]:
                break

            offset += page_size

        return results


def run_tests(service: SearchService) -> None:
    """Verify filtering, sorting, pagination and validation."""

    result = service.search(category="Electronics")

    assert result["total"] == 6
    assert all(
        item["category"] == "Electronics"
        for item in result["results"]
    )

    result = service.search(
        min_price=1000,
        max_price=7000,
        min_rating=4.0,
        sort_by="price",
        direction="asc"
    )

    assert all(
        1000 <= item["price"] <= 7000
        and item["rating"] >= 4.0
        for item in result["results"]
    )

    result = service.search(keyword="desk")

    assert result["total"] == 2

    first_page = service.search(limit=2, offset=0)
    second_page = service.search(limit=2, offset=2)

    assert len(first_page["results"]) == 2
    assert first_page["results"][0]["id"] != (
        second_page["results"][0]["id"]
    )

    all_results = service.search_all_pages(page_size=3)
    assert len(all_results) == 9

    try:
        service.search(min_price=10000, max_price=100)
        raise AssertionError("Invalid price range was accepted.")
    except ValidationError:
        pass

    try:
        service.search(sort_by="untrusted_column")
        raise AssertionError("Invalid sorting field was accepted.")
    except ValidationError:
        pass

    try:
        service.search(limit=1000)
        raise AssertionError("Invalid page size was accepted.")
    except ValidationError:
        pass

    logger.info("All tests passed.")


def main() -> None:
    database = CatalogDatabase()
    service = SearchService(database)

    try:
        print("\n1. Basic keyword search")

        response = service.search(keyword="keyboard")

        print(json.dumps(response, indent=2))

        print("\n2. Multiple filters with descending sorting")

        response = service.search(
            category="Electronics",
            min_price=1000,
            max_price=10000,
            min_rating=4.0,
            sort_by="rating",
            direction="desc",
            limit=5
        )

        print(json.dumps(response, indent=2))

        print("\n3. Pagination")

        response = service.search(
            sort_by="price",
            direction="asc",
            limit=3,
            offset=0
        )

        print(json.dumps(response, indent=2))

        print("\n4. Combined search and sorting")

        response = service.search(
            keyword="desk",
            active_only=True,
            sort_by="price",
            direction="desc"
        )

        print(json.dumps(response, indent=2))

        print("\n5. Automated validation")

        run_tests(service)

        print("\n6. Invalid query demonstration")

        try:
            service.search(min_rating=8)
        except ValidationError as error:
            print(f"Validation rejected: {error}")

        print("\n7. Query plan")

        criteria = SearchCriteria(
            category="Electronics",
            min_price=1000
        )

        sql, parameters = database.build_query(criteria)

        plan = database.connection.execute(
            "EXPLAIN QUERY PLAN " + sql,
            parameters
        ).fetchall()

        for item in plan:
            print(dict(item))

    finally:
        database.close()


if __name__ == "__main__":
    main()
