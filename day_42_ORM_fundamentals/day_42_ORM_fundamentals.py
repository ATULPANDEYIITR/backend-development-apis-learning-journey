"""
ORM Fundamentals
================
A self-contained ORM-style learning implementation using only Python's standard
library. The program demonstrates models, mappings, relationships, identity
handling, persistence, querying, validation, transactions, and ORM tradeoffs.

The implementation deliberately uses sqlite3 directly so the mechanics normally
hidden by an ORM remain visible.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class User:
    id: Optional[int]
    name: str
    email: str

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("User name cannot be empty")
        if "@" not in self.email or "." not in self.email.split("@")[-1]:
            raise ValueError("User email is invalid")


@dataclass
class Address:
    id: Optional[int]
    user_id: int
    city: str
    country: str

    def validate(self) -> None:
        if not self.city.strip() or not self.country.strip():
            raise ValueError("City and country are required")


@dataclass
class Product:
    id: Optional[int]
    name: str
    price: float

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Product name cannot be empty")
        if self.price < 0:
            raise ValueError("Product price cannot be negative")


@dataclass
class OrderItem:
    id: Optional[int]
    order_id: int
    product_id: int
    quantity: int
    unit_price: float

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.unit_price < 0:
            raise ValueError("Unit price cannot be negative")


@dataclass
class Order:
    id: Optional[int]
    user_id: int
    status: str
    created_at: str
    items: list[OrderItem] = field(default_factory=list)

    VALID_STATUSES = {"PENDING", "PAID", "SHIPPED", "CANCELLED"}

    def validate(self) -> None:
        if self.status not in self.VALID_STATUSES:
            raise ValueError(f"Unsupported order status: {self.status}")


class Session:
    """
    A small ORM-like session.

    The identity map ensures that repeated reads of the same row during a
    session return the same Python object. This is one of the useful behaviors
    real ORM sessions commonly provide.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.identity_map: dict[tuple[type, int], Any] = {}
        self.new_objects: list[Any] = []

    def add(self, obj: Any) -> None:
        if not hasattr(obj, "id"):
            raise TypeError("Only mapped objects can be persisted")
        self.new_objects.append(obj)

    def get_user(self, user_id: int) -> Optional[User]:
        key = (User, user_id)
        if key in self.identity_map:
            return self.identity_map[key]

        row = self.connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        user = User(row["id"], row["name"], row["email"])
        self.identity_map[key] = user
        return user

    def get_product(self, product_id: int) -> Optional[Product]:
        key = (Product, product_id)
        if key in self.identity_map:
            return self.identity_map[key]

        row = self.connection.execute(
            "SELECT id, name, price FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        if row is None:
            return None

        product = Product(row["id"], row["name"], row["price"])
        self.identity_map[key] = product
        return product

    def commit(self) -> None:
        """
        Persist pending objects.

        Real ORMs often translate object state into INSERT/UPDATE statements.
        Here that mapping is intentionally visible.
        """
        try:
            for obj in self.new_objects:
                if isinstance(obj, User):
                    obj.validate()
                    cursor = self.connection.execute(
                        "INSERT INTO users(name, email) VALUES (?, ?)",
                        (obj.name, obj.email),
                    )
                    obj.id = cursor.lastrowid
                    self.identity_map[(User, obj.id)] = obj

                elif isinstance(obj, Address):
                    obj.validate()
                    self.connection.execute(
                        """
                        INSERT INTO addresses(user_id, city, country)
                        VALUES (?, ?, ?)
                        """,
                        (obj.user_id, obj.city, obj.country),
                    )

                elif isinstance(obj, Product):
                    obj.validate()
                    cursor = self.connection.execute(
                        "INSERT INTO products(name, price) VALUES (?, ?)",
                        (obj.name, obj.price),
                    )
                    obj.id = cursor.lastrowid
                    self.identity_map[(Product, obj.id)] = obj

                elif isinstance(obj, Order):
                    obj.validate()
                    cursor = self.connection.execute(
                        """
                        INSERT INTO orders(user_id, status, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (obj.user_id, obj.status, obj.created_at),
                    )
                    obj.id = cursor.lastrowid

                    for item in obj.items:
                        item.order_id = obj.id
                        item.validate()
                        self.connection.execute(
                            """
                            INSERT INTO order_items
                                (order_id, product_id, quantity, unit_price)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                item.order_id,
                                item.product_id,
                                item.quantity,
                                item.unit_price,
                            ),
                        )

                else:
                    raise TypeError(f"Unsupported mapped type: {type(obj).__name__}")

            self.connection.commit()
            self.new_objects.clear()

        except Exception:
            self.connection.rollback()
            raise

    def rollback(self) -> None:
        self.connection.rollback()
        self.new_objects.clear()


class Database:
    """Creates a relational schema representing the object model."""

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.create_schema()

    def create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                city TEXT NOT NULL,
                country TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL CHECK (price >= 0)
            );

            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('PENDING', 'PAID', 'SHIPPED', 'CANCELLED')),
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price >= 0),
                FOREIGN KEY (order_id) REFERENCES orders(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE INDEX idx_orders_user_id ON orders(user_id);
            CREATE INDEX idx_order_items_order_id ON order_items(order_id);
            CREATE INDEX idx_order_items_product_id ON order_items(product_id);
            """
        )
        self.connection.commit()


def create_demo_data(session: Session) -> User:
    user = User(None, "Atul Pandey", "atul@example.com")
    session.add(user)
    session.commit()

    address = Address(None, user.id, "Lucknow", "India")
    session.add(address)

    laptop = Product(None, "Engineering Laptop", 85000.00)
    keyboard = Product(None, "Mechanical Keyboard", 6500.00)
    session.add(laptop)
    session.add(keyboard)
    session.commit()

    order = Order(
        None,
        user.id,
        "PENDING",
        utc_now(),
        items=[
            OrderItem(None, 0, laptop.id, 1, laptop.price),
            OrderItem(None, 0, keyboard.id, 2, keyboard.price),
        ],
    )
    session.add(order)
    session.commit()

    return user


def load_order_graph(
    connection: sqlite3.Connection,
    order_id: int,
) -> Optional[dict[str, Any]]:
    """
    Explicitly reconstructs an object graph from relational rows.

    The JOIN produces flat relational data. The application groups those rows
    into one order containing products, which illustrates object-relational
    impedance: relational tables and object graphs represent relationships
    differently.
    """
    rows = connection.execute(
        """
        SELECT
            o.id AS order_id,
            o.status,
            o.created_at,
            u.id AS user_id,
            u.name AS user_name,
            p.id AS product_id,
            p.name AS product_name,
            oi.quantity,
            oi.unit_price
        FROM orders o
        JOIN users u ON u.id = o.user_id
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON p.id = oi.product_id
        WHERE o.id = ?
        ORDER BY oi.id
        """,
        (order_id,),
    ).fetchall()

    if not rows:
        return None

    first = rows[0]
    return {
        "id": first["order_id"],
        "status": first["status"],
        "created_at": first["created_at"],
        "user": {
            "id": first["user_id"],
            "name": first["user_name"],
        },
        "items": [
            {
                "product_id": row["product_id"],
                "product": row["product_name"],
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "line_total": row["quantity"] * row["unit_price"],
            }
            for row in rows
        ],
    }


def demonstrate_relationships(connection: sqlite3.Connection, user_id: int) -> None:
    print("\nRelationship mapping")

    row = connection.execute(
        """
        SELECT u.name, a.city, a.country
        FROM users u
        LEFT JOIN addresses a ON a.user_id = u.id
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()

    print(f"One-to-one: {row['name']} -> {row['city']}, {row['country']}")

    orders = connection.execute(
        """
        SELECT o.id, o.status, COUNT(oi.id) AS item_count
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.user_id = ?
        GROUP BY o.id, o.status
        """,
        (user_id,),
    ).fetchall()

    for order in orders:
        print(
            f"One-to-many: user {user_id} -> "
            f"order {order['id']} with {order['item_count']} items"
        )

    product_count = connection.execute(
        """
        SELECT COUNT(DISTINCT product_id)
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.user_id = ?
        """,
        (user_id,),
    ).fetchone()[0]

    print(
        f"Many-to-many: users and products are connected through "
        f"orders/order_items; this user has ordered {product_count} distinct products."
    )


def demonstrate_transaction_failure(session: Session) -> None:
    print("\nTransaction and validation behavior")

    invalid_product = Product(None, "Invalid Product", -50)
    session.add(invalid_product)

    try:
        session.commit()
    except ValueError as exc:
        print(f"Rejected invalid object before persistence: {exc}")
        session.rollback()

    connection = session.connection

    try:
        connection.execute(
            """
            INSERT INTO addresses(user_id, city, country)
            VALUES (?, ?, ?)
            """,
            (999999, "Unknown", "Unknown"),
        )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        print(f"Database rejected invalid foreign key: {exc}")


def demonstrate_identity_map(session: Session, user_id: int) -> None:
    first = session.get_user(user_id)
    second = session.get_user(user_id)

    print("\nIdentity map behavior")
    print(f"Objects contain the same database identity: {first.id == second.id}")
    print(f"Objects are the same in-memory instance: {first is second}")


def demonstrate_orm_tradeoffs(connection: sqlite3.Connection) -> None:
    print("\nORM tradeoff demonstration")

    row = connection.execute(
        """
        SELECT
            p.name,
            SUM(oi.quantity) AS units_sold,
            SUM(oi.quantity * oi.unit_price) AS revenue
        FROM products p
        JOIN order_items oi ON oi.product_id = p.id
        JOIN orders o ON o.id = oi.order_id
        WHERE o.status <> 'CANCELLED'
        GROUP BY p.id, p.name
        ORDER BY revenue DESC
        """
    ).fetchall()

    for item in row:
        print(
            f"{item['name']}: {item['units_sold']} units, "
            f"revenue={item['revenue']:.2f}"
        )

    print(
        "\nThe object model is convenient for domain behavior, while SQL remains "
        "strong for joins, aggregation, constraints, and set-oriented reporting."
    )


def main() -> None:
    print("ORM Fundamentals: explicit object-relational mapping")

    database = Database()
    session = Session(database.connection)

    user = create_demo_data(session)

    demonstrate_identity_map(session, user.id)
    demonstrate_relationships(database.connection, user.id)

    order_id = database.connection.execute(
        "SELECT id FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user.id,),
    ).fetchone()["id"]

    graph = load_order_graph(database.connection, order_id)
    print("\nLoaded object graph")
    print(graph)

    demonstrate_transaction_failure(session)
    demonstrate_orm_tradeoffs(database.connection)

    print("\nORM fundamentals demonstrated:")
    print("- Models map application objects to relational tables.")
    print("- Scalar attributes map to table columns.")
    print("- Foreign keys represent relationships between models.")
    print("- A session can maintain object identity.")
    print("- Transactions protect multi-row persistence operations.")
    print("- Database constraints remain necessary even when validation exists in code.")
    print("- ORM convenience does not eliminate the need to understand SQL.")


if __name__ == "__main__":
    main()
