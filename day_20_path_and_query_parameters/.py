# File: src/path_query_api/main.py

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Path, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Path and Query Parameters API",
    version="1.0.0",
    description=(
        "Educational API demonstrating path parameters, query parameters, "
        "optional parameters, defaults, validation, filtering, and pagination."
    ),
)


class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class ProductListResponse(BaseModel):
    items: list[Product]
    total: int
    skip: int
    limit: int


PRODUCTS = [
    Product(id=1, name="Mechanical Keyboard", category="electronics", price=89.99, stock=24),
    Product(id=2, name="Wireless Mouse", category="electronics", price=39.99, stock=51),
    Product(id=3, name="USB-C Hub", category="electronics", price=29.99, stock=37),
    Product(id=4, name="Notebook", category="stationery", price=5.49, stock=100),
    Product(id=5, name="Desk Lamp", category="home", price=44.99, stock=18),
    Product(id=6, name="Office Chair", category="furniture", price=219.99, stock=7),
    Product(id=7, name="Monitor Stand", category="furniture", price=59.99, stock=12),
    Product(id=8, name="Python Handbook", category="books", price=34.99, stock=31),
]


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint used by Docker and deployment checks."""
    return {"status": "ok"}


@app.get("/products/{product_id}", response_model=Product)
def get_product(
    product_id: Annotated[
        int,
        Path(
            ge=1,
            description="Unique product identifier supplied as part of the URL path.",
        ),
    ],
) -> Product:
    """
    Demonstrate a required path parameter.

    Example:
        GET /products/3
    """
    for product in PRODUCTS:
        if product.id == product_id:
            return product

    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Product not found")


@app.get("/products", response_model=ProductListResponse)
def list_products(
    category: Annotated[
        str | None,
        Query(
            default=None,
            min_length=2,
            max_length=30,
            description="Optional category filter.",
        ),
    ] = None,
    min_price: Annotated[
        float | None,
        Query(
            default=None,
            ge=0,
            description="Optional minimum product price.",
        ),
    ] = None,
    max_price: Annotated[
        float | None,
        Query(
            default=None,
            ge=0,
            description="Optional maximum product price.",
        ),
    ] = None,
    search: Annotated[
        str | None,
        Query(
            default=None,
            min_length=1,
            max_length=50,
            description="Optional case-insensitive name search.",
        ),
    ] = None,
    in_stock: Annotated[
        bool,
        Query(
            default=False,
            description="When true, return only products with stock greater than zero.",
        ),
    ] = False,
    skip: Annotated[
        int,
        Query(
            default=0,
            ge=0,
            description="Number of matching records to skip.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            default=5,
            ge=1,
            le=20,
            description="Maximum number of records to return.",
        ),
    ] = 5,
) -> ProductListResponse:
    """
    Demonstrate optional query parameters and default values.

    Examples:
        GET /products
        GET /products?category=electronics
        GET /products?min_price=30&max_price=100
        GET /products?in_stock=true
        GET /products?search=mouse
        GET /products?skip=2&limit=3

    Query parameters are independent of the path. They are normally used
    for filtering, sorting, searching, pagination, or changing the shape
    of a collection response.
    """
    from fastapi import HTTPException

    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=422,
            detail="min_price must be less than or equal to max_price",
        )

    normalized_category = category.lower() if category else None
    normalized_search = search.lower() if search else None

    filtered = PRODUCTS

    if normalized_category:
        filtered = [
            product
            for product in filtered
            if product.category.lower() == normalized_category
        ]

    if min_price is not None:
        filtered = [
            product for product in filtered if product.price >= min_price
        ]

    if max_price is not None:
        filtered = [
            product for product in filtered if product.price <= max_price
        ]

    if normalized_search:
        filtered = [
            product
            for product in filtered
            if normalized_search in product.name.lower()
        ]

    if in_stock:
        filtered = [
            product for product in filtered if product.stock > 0
        ]

    total = len(filtered)
    page = filtered[skip : skip + limit]

    return ProductListResponse(
        items=page,
        total=total,
        skip=skip,
        limit=limit,
    )


@app.get("/categories/{category}/products", response_model=list[Product])
def products_by_category(
    category: Annotated[
        str,
        Path(
            min_length=2,
            max_length=30,
            description="Category supplied as a required path parameter.",
        ),
    ],
    limit: Annotated[
        int,
        Query(
            default=10,
            ge=1,
            le=20,
            description="Optional maximum number of results.",
        ),
    ] = 10,
) -> list[Product]:
    """
    Demonstrate using a path parameter together with a query parameter.

    Example:
        GET /categories/electronics/products?limit=2
    """
    normalized_category = category.lower()

    return [
        product
        for product in PRODUCTS
        if product.category.lower() == normalized_category
    ][:limit]


@app.get("/products/{product_id}/reviews")
def get_product_reviews(
    product_id: Annotated[
        int,
        Path(ge=1, description="Product identifier."),
    ],
    page: Annotated[
        int,
        Query(default=1, ge=1, description="One-based review page number."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(default=10, ge=1, le=50, description="Reviews per page."),
    ] = 10,
) -> dict[str, object]:
    """
    Demonstrate nested resources.

    The path identifies which product's reviews are requested.
    Query parameters control pagination of those reviews.
    """
    return {
        "product_id": product_id,
        "page": page,
        "page_size": page_size,
        "message": "Review pagination parameters were accepted.",
    }
