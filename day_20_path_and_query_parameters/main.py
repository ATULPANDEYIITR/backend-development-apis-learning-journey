# File: tests/test_main.py

from fastapi.testclient import TestClient

from path_query_api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_required_path_parameter_returns_product() -> None:
    response = client.get("/products/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_path_parameter_not_found() -> None:
    response = client.get("/products/999")

    assert response.status_code == 404


def test_path_parameter_must_be_positive() -> None:
    response = client.get("/products/0")

    assert response.status_code == 422


def test_default_query_parameters() -> None:
    response = client.get("/products")

    assert response.status_code == 200
    body = response.json()

    assert body["skip"] == 0
    assert body["limit"] == 5
    assert len(body["items"]) == 5


def test_category_query_parameter() -> None:
    response = client.get("/products?category=electronics")

    assert response.status_code == 200

    for product in response.json()["items"]:
        assert product["category"] == "electronics"


def test_price_range_query_parameters() -> None:
    response = client.get("/products?min_price=30&max_price=100")

    assert response.status_code == 200

    for product in response.json()["items"]:
        assert 30 <= product["price"] <= 100


def test_invalid_price_range() -> None:
    response = client.get("/products?min_price=100&max_price=30")

    assert response.status_code == 422
    assert "min_price must be less than or equal to max_price" in response.text


def test_boolean_query_parameter() -> None:
    response = client.get("/products?in_stock=true")

    assert response.status_code == 200

    for product in response.json()["items"]:
        assert product["stock"] > 0


def test_search_query_parameter() -> None:
    response = client.get("/products?search=mouse")

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Wireless Mouse"


def test_pagination_query_parameters() -> None:
    response = client.get("/products?skip=1&limit=2")

    assert response.status_code == 200
    body = response.json()

    assert body["skip"] == 1
    assert body["limit"] == 2
    assert len(body["items"]) == 2


def test_limit_upper_boundary() -> None:
    response = client.get("/products?limit=20")

    assert response.status_code == 200


def test_limit_above_allowed_maximum() -> None:
    response = client.get("/products?limit=21")

    assert response.status_code == 422


def test_negative_skip_is_rejected() -> None:
    response = client.get("/products?skip=-1")

    assert response.status_code == 422


def test_path_and_query_parameters_together() -> None:
    response = client.get("/categories/electronics/products?limit=2")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all(item["category"] == "electronics" for item in response.json())


def test_nested_resource_parameters() -> None:
    response = client.get("/products/1/reviews?page=2&page_size=5")

    assert response.status_code == 200
    assert response.json() == {
        "product_id": 1,
        "page": 2,
        "page_size": 5,
        "message": "Review pagination parameters were accepted.",
    }
