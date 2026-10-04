"""
Database Constraints: PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK, DEFAULT

A self-contained SQLite demonstration progressing from basic constraint behavior
to a realistic order-management schema, validation failures, transactions,
schema inspection, and constraint-aware data processing.

SQLite is used because it is part of Python's standard library and enforces all
six requested constraint types without external dependencies.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator


DATABASE = ":memory:"


@dataclass(frozen=True)
class Product:
    name: str
    sku: str
    price: float
    stock: int


class ConstraintDemo:
    """Build and operate a small relational system whose integrity is enforced by SQL."""

    def __init__(self, database: str = DATABASE) -> None:
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row

        # SQLite does not enforce foreign keys unless the connection enables them.
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    def create_schema(self) -> None:
        """Create tables containing all requested constraint types."""

        self.connection.executescript(
            """
            DROP TABLE IF EXISTS order_items;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS products;
            DROP TABLE IF EXISTS customers;

            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                age INTEGER CHECK (age >= 18),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'suspended'))
            );

            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price REAL NOT NULL CHECK (price > 0),
                stock INTEGER NOT NULL DEFAULT 0
                    CHECK (stock >= 0)
            );

            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                order_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (order_status IN ('pending', 'paid', 'cancelled')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            );

            CREATE TABLE order_items (
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1
                    CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price > 0),

                PRIMARY KEY (order_id, product_id),

                FOREIGN KEY (order_id)
                    REFERENCES orders(order_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(product_id)
                    ON DELETE RESTRICT
            );
            """
        )
        self.connection.commit()

    def demonstrate_primary_key(self) -> None:
        print("\n=== PRIMARY KEY ===")
        print("A primary key uniquely identifies a row.")

        self.connection.execute(
            """
            INSERT INTO customers (email, full_name, age)
            VALUES (?, ?, ?)
            """,
            ("alice@example.com", "Alice Rao", 29),
        )

        customer = self.connection.execute(
            "SELECT customer_id, email FROM customers WHERE email = ?",
            ("alice@example.com",),
        ).fetchone()

        print(f"Generated customer_id: {customer['customer_id']}")

        print(
            "SQLite INTEGER PRIMARY KEY is backed by SQLite's row identifier behavior "
            "when no explicit value is supplied."
        )

    def demonstrate_not_null(self) -> None:
        print("\n=== NOT NULL ===")

        try:
            self.connection.execute(
                """
                INSERT INTO customers (email, full_name, age)
                VALUES (?, ?, ?)
                """,
                ("missing-name@example.com", None, 31),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(f"Rejected missing required value: {error}")

    def demonstrate_unique(self) -> None:
        print("\n=== UNIQUE ===")

        try:
            self.connection.execute(
                """
                INSERT INTO customers (email, full_name, age)
                VALUES (?, ?, ?)
                """,
                ("alice@example.com", "Another Alice", 34),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(f"Rejected duplicate email: {error}")

        print(
            "UNIQUE prevents two non-NULL values from occupying the same constrained "
            "key. Here email is also NOT NULL, so every customer must have a unique email."
        )

    def demonstrate_check(self) -> None:
        print("\n=== CHECK ===")

        try:
            self.connection.execute(
                """
                INSERT INTO products (sku, name, price, stock)
                VALUES (?, ?, ?, ?)
                """,
                ("BAD-001", "Invalid Product", -25.0, 5),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(f"Rejected invalid price: {error}")

        try:
            self.connection.execute(
                """
                INSERT INTO customers (email, full_name, age)
                VALUES (?, ?, ?)
                """,
                ("minor@example.com", "Invalid Customer", 15),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(f"Rejected invalid age: {error}")

    def demonstrate_default(self) -> None:
        print("\n=== DEFAULT ===")

        self.connection.execute(
            """
            INSERT INTO products (sku, name, price)
            VALUES (?, ?, ?)
            """,
            ("KB-001", "Mechanical Keyboard", 89.99),
        )
        self.connection.commit()

        product = self.connection.execute(
            "SELECT sku, stock FROM products WHERE sku = ?",
            ("KB-001",),
        ).fetchone()

        print(f"Stock omitted by caller; database supplied default: {product['stock']}")

        self.connection.execute(
            """
            INSERT INTO customers (email, full_name, age)
            VALUES (?, ?, ?)
            """,
            ("bob@example.com", "Bob Singh", 41),
        )
        self.connection.commit()

        customer = self.connection.execute(
            "SELECT email, status FROM customers WHERE email = ?",
            ("bob@example.com",),
        ).fetchone()

        print(f"Status omitted by caller; database supplied default: {customer['status']}")

    def demonstrate_foreign_key(self) -> None:
        print("\n=== FOREIGN KEY ===")

        try:
            self.connection.execute(
                """
                INSERT INTO orders (customer_id)
                VALUES (999999)
                """
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(f"Rejected order referencing nonexistent customer: {error}")

        print(
            "The foreign key keeps orders connected to real customers and prevents "
            "orphaned child records."
        )

    def seed_products(self) -> None:
        products = [
            Product("Laptop", "LT-100", 1299.00, 10),
            Product("Monitor", "MN-200", 349.00, 20),
            Product("Keyboard", "KB-300", 89.00, 50),
        ]

        self.connection.executemany(
            """
            INSERT INTO products (name, sku, price, stock)
            VALUES (?, ?, ?, ?)
            """,
            [(p.name, p.sku, p.price, p.stock) for p in products],
        )
        self.connection.commit()

    def get_customer_id(self, email: str) -> int:
        row = self.connection.execute(
            "SELECT customer_id FROM customers WHERE email = ?",
            (email,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Customer does not exist: {email}")

        return int(row["customer_id"])

    def get_product(self, sku: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT product_id, sku, name, price, stock
            FROM products
            WHERE sku = ?
            """,
            (sku,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Product does not exist: {sku}")

        return row

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """
        A failed multi-table operation is rolled back as one unit.

        Constraints protect individual statements, while the transaction protects
        the consistency of the complete business operation.
        """
        try:
            self.connection.execute("BEGIN")
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def create_order(
        self,
        customer_email: str,
        items: list[tuple[str, int]],
    ) -> int:
        """Create an order only when all referenced products and quantities are valid."""

        if not items:
            raise ValueError("An order must contain at least one product.")

        customer_id = self.get_customer_id(customer_email)

        with self.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders (customer_id)
                VALUES (?)
                """,
                (customer_id,),
            )
            order_id = int(cursor.lastrowid)

            for sku, quantity in items:
                if quantity <= 0:
                    raise ValueError("Quantity must be greater than zero.")

                product = self.get_product(sku)

                if product["stock"] < quantity:
                    raise ValueError(
                        f"Insufficient stock for {sku}: "
                        f"requested={quantity}, available={product['stock']}"
                    )

                connection.execute(
                    """
                    INSERT INTO order_items (
                        order_id,
                        product_id,
                        quantity,
                        unit_price
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        product["product_id"],
                        quantity,
                        product["price"],
                    ),
                )

                connection.execute(
                    """
                    UPDATE products
                    SET stock = stock - ?
                    WHERE product_id = ?
                    """,
                    (quantity, product["product_id"]),
                )

        return order_id

    def show_order(self, order_id: int) -> None:
        rows = self.connection.execute(
            """
            SELECT
                o.order_id,
                c.email AS customer_email,
                o.order_status,
                o.created_at,
                p.sku,
                p.name,
                oi.quantity,
                oi.unit_price,
                oi.quantity * oi.unit_price AS line_total
            FROM orders AS o
            JOIN customers AS c
                ON c.customer_id = o.customer_id
            JOIN order_items AS oi
                ON oi.order_id = o.order_id
            JOIN products AS p
                ON p.product_id = oi.product_id
            WHERE o.order_id = ?
            ORDER BY oi.product_id
            """,
            (order_id,),
        ).fetchall()

        print(f"\nOrder {order_id}")

        total = 0.0
        for row in rows:
            total += row["line_total"]
            print(
                f"  {row['sku']} | {row['name']} | "
                f"quantity={row['quantity']} | "
                f"unit_price={row['unit_price']:.2f} | "
                f"line_total={row['line_total']:.2f}"
            )

        if rows:
            print(f"  Total: {total:.2f}")

    def demonstrate_composite_primary_key(self) -> None:
        print("\n=== COMPOSITE PRIMARY KEY ===")

        customer_id = self.get_customer_id("alice@example.com")
        order_id = self.create_order(
            "alice@example.com",
            [("MN-200", 1)],
        )

        product = self.get_product("MN-200")

        try:
            self.connection.execute(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    quantity,
                    unit_price
                )
                VALUES (?, ?, ?, ?)
                """,
                (order_id, product["product_id"], 1, product["price"]),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(
                "Duplicate order/product combination rejected by composite PRIMARY KEY:"
            )
            print(f"  {error}")

        print(f"Customer involved: {customer_id}")
        print(f"Order created: {order_id}")

    def demonstrate_cascading_and_restrict_behavior(self) -> None:
        print("\n=== FOREIGN KEY DELETE RULES ===")

        bob_id = self.get_customer_id("bob@example.com")

        try:
            self.connection.execute(
                "DELETE FROM customers WHERE customer_id = ?",
                (bob_id,),
            )
            self.connection.commit()
            print("Bob was deleted because he has no dependent orders.")
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(f"Customer deletion rejected: {error}")

        alice_id = self.get_customer_id("alice@example.com")

        try:
            self.connection.execute(
                "DELETE FROM customers WHERE customer_id = ?",
                (alice_id,),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            print(
                "Alice cannot be deleted while an order references her because "
                "the customer foreign key uses ON DELETE RESTRICT."
            )
            print(f"  {error}")

    def inspect_constraints(self) -> None:
        print("\n=== SCHEMA INSPECTION ===")

        tables = ["customers", "products", "orders", "order_items"]

        for table in tables:
            print(f"\nTable: {table}")

            columns = self.connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()

            for column in columns:
                print(
                    f"  column={column['name']!r}, "
                    f"type={column['type']}, "
                    f"not_null={bool(column['notnull'])}, "
                    f"default={column['dflt_value']!r}, "
                    f"primary_key_position={column['pk']}"
                )

            foreign_keys = self.connection.execute(
                f"PRAGMA foreign_key_list({table})"
            ).fetchall()

            for foreign_key in foreign_keys:
                print(
                    f"  foreign_key: {foreign_key['table']}."
                    f"{foreign_key['to']} <- {foreign_key['from']} "
                    f"(on_delete={foreign_key['on_delete']})"
                )

    def show_current_state(self) -> None:
        print("\n=== CURRENT DATA ===")

        for table in ("customers", "products", "orders", "order_items"):
            rows = self.connection.execute(f"SELECT * FROM {table}").fetchall()
            print(f"\n{table}: {len(rows)} row(s)")

            for row in rows:
                print(" ", dict(row))

    def demonstrate_transaction_rollback(self) -> None:
        print("\n=== TRANSACTION + CONSTRAINT FAILURE ===")

        before = self.connection.execute(
            "SELECT stock FROM products WHERE sku = ?",
            ("LT-100",),
        ).fetchone()["stock"]

        try:
            with self.transaction() as connection:
                product = self.get_product("LT-100")

                connection.execute(
                    """
                    UPDATE products
                    SET stock = stock - 2
                    WHERE product_id = ?
                    """,
                    (product["product_id"],),
                )

                # This intentionally violates CHECK(quantity > 0).
                connection.execute(
                    """
                    INSERT INTO order_items (
                        order_id,
                        product_id,
                        quantity,
                        unit_price
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (1, product["product_id"], 0, product["price"]),
                )
        except sqlite3.IntegrityError as error:
            after = self.connection.execute(
                "SELECT stock FROM products WHERE sku = ?",
                ("LT-100",),
            ).fetchone()["stock"]

            print(f"Constraint failure: {error}")
            print(f"Stock before failed transaction: {before}")
            print(f"Stock after rollback: {after}")
            print(
                "The stock update was rolled back together with the invalid "
                "order-item insertion."
            )

    def run(self) -> None:
        self.create_schema()
        self.demonstrate_primary_key()
        self.demonstrate_not_null()
        self.demonstrate_unique()
        self.demonstrate_check()
        self.demonstrate_default()
        self.seed_products()
        self.demonstrate_foreign_key()

        print("\n=== VALID ORDER WORKFLOW ===")
        order_id = self.create_order(
            "alice@example.com",
            [
                ("LT-100", 1),
                ("KB-300", 2),
            ],
        )
        self.show_order(order_id)

        self.demonstrate_composite_primary_key()
        self.demonstrate_transaction_rollback()
        self.demonstrate_cascading_and_restrict_behavior()
        self.inspect_constraints()
        self.show_current_state()


def main() -> None:
    demo = ConstraintDemo()

    try:
        demo.run()
    finally:
        demo.close()


if __name__ == "__main__":
    main()
