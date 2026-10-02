#!/usr/bin/env python3
"""
SQL Fundamentals: SELECT, INSERT, UPDATE, DELETE, WHERE, ORDER BY, GROUP BY

A self-contained SQLite laboratory that progresses from basic relational
operations to grouped reporting, parameterized queries, transactions,
constraints, validation, query plans, and practical data-management rules.

SQLite is part of Python's standard library, so no third-party package is
required.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DATABASE_FILE = Path("sql_fundamentals_lab.sqlite3")


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    city: str
    segment: str


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str
    unit_price: float
    stock: int


def connect_database(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open SQLite and configure row access plus foreign-key enforcement."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection):
    """
    Provide an explicit transaction boundary.

    If any operation fails, the entire transaction is rolled back. This is
    especially important when several INSERT/UPDATE/DELETE statements must
    succeed or fail together.
    """
    try:
        connection.execute("BEGIN")
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def create_schema(connection: sqlite3.Connection) -> None:
    """Create a small sales database with constraints and useful indexes."""
    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            segment TEXT NOT NULL
                CHECK (segment IN ('Consumer', 'Business', 'Enterprise'))
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            stock INTEGER NOT NULL CHECK (stock >= 0)
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('Pending', 'Paid', 'Shipped', 'Cancelled')),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            PRIMARY KEY (order_id, product_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
                ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE INDEX idx_customers_city ON customers(city);
        CREATE INDEX idx_orders_customer ON orders(customer_id);
        CREATE INDEX idx_orders_status ON orders(status);
        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_order_items_product ON order_items(product_id);
        """
    )


def seed_data(connection: sqlite3.Connection) -> None:
    """Insert realistic demonstration records using parameterized statements."""
    customers = [
        (1, "Aarav Mehta", "Lucknow", "Consumer"),
        (2, "Neha Sharma", "Delhi", "Business"),
        (3, "Rohan Verma", "Bengaluru", "Enterprise"),
        (4, "Isha Kapoor", "Mumbai", "Consumer"),
        (5, "Kabir Singh", "Lucknow", "Business"),
        (6, "Maya Rao", "Hyderabad", "Enterprise"),
    ]

    products = [
        (1, "Mechanical Keyboard", "Computing", 4500.00, 40),
        (2, "USB-C Dock", "Computing", 7200.00, 25),
        (3, "Noise Cancelling Headphones", "Audio", 9800.00, 18),
        (4, "Webcam", "Video", 3200.00, 30),
        (5, "Monitor Arm", "Accessories", 4100.00, 22),
        (6, "Laptop Stand", "Accessories", 2600.00, 35),
    ]

    orders = [
        (1001, 1, "2026-09-01", "Paid"),
        (1002, 2, "2026-09-03", "Shipped"),
        (1003, 3, "2026-09-04", "Paid"),
        (1004, 1, "2026-09-07", "Cancelled"),
        (1005, 4, "2026-09-09", "Shipped"),
        (1006, 5, "2026-09-12", "Paid"),
        (1007, 6, "2026-09-14", "Pending"),
        (1008, 2, "2026-09-18", "Shipped"),
    ]

    order_items = [
        (1001, 1, 1, 4500.00),
        (1001, 6, 2, 2600.00),
        (1002, 2, 1, 7200.00),
        (1002, 4, 2, 3200.00),
        (1003, 3, 2, 9800.00),
        (1003, 5, 1, 4100.00),
        (1004, 1, 1, 4500.00),
        (1005, 4, 1, 3200.00),
        (1005, 6, 1, 2600.00),
        (1006, 2, 2, 7200.00),
        (1006, 5, 2, 4100.00),
        (1007, 3, 1, 9800.00),
        (1008, 2, 1, 7200.00),
        (1008, 6, 3, 2600.00),
    ]

    with transaction(connection):
        connection.executemany(
            "INSERT INTO customers (customer_id, name, city, segment) VALUES (?, ?, ?, ?)",
            customers,
        )
        connection.executemany(
            """
            INSERT INTO products (product_id, name, category, unit_price, stock)
            VALUES (?, ?, ?, ?, ?)
            """,
            products,
        )
        connection.executemany(
            """
            INSERT INTO orders (order_id, customer_id, order_date, status)
            VALUES (?, ?, ?, ?)
            """,
            orders,
        )
        connection.executemany(
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            """,
            order_items,
        )


def print_rows(title: str, rows: Iterable[sqlite3.Row]) -> None:
    """Display query results without requiring an external table package."""
    rows = list(rows)
    print(f"\n--- {title} ---")
    if not rows:
        print("(no rows)")
        return

    columns = rows[0].keys()
    print(" | ".join(columns))
    print("-" * (len(" | ".join(columns)) + 4))
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:,.2f}")
            else:
                values.append(str(value))
        print(" | ".join(values))


def demonstrate_select(connection: sqlite3.Connection) -> None:
    """
    SELECT reads data without changing the stored rows.

    Projection chooses columns, while aliases make result sets easier to
    understand. DISTINCT removes duplicate result values.
    """
    rows = connection.execute(
        """
        SELECT customer_id, name, city
        FROM customers
        """
    ).fetchall()
    print_rows("Basic SELECT", rows)

    rows = connection.execute(
        """
        SELECT name AS customer, segment AS customer_segment
        FROM customers
        """
    ).fetchall()
    print_rows("SELECT with aliases", rows)

    rows = connection.execute(
        """
        SELECT DISTINCT city
        FROM customers
        """
    ).fetchall()
    print_rows("DISTINCT cities", rows)

    rows = connection.execute(
        """
        SELECT product_id, name, unit_price, stock
        FROM products
        WHERE unit_price >= ?
        """
        ,
        (4000,),
    ).fetchall()
    print_rows("SELECT with a parameter", rows)


def demonstrate_insert(connection: sqlite3.Connection) -> None:
    """
    INSERT creates rows.

    The first operation inserts one customer. The second demonstrates a
    multi-row insert. Parameters keep values separate from SQL text.
    """
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO customers (customer_id, name, city, segment)
            VALUES (?, ?, ?, ?)
            """,
            (7, "Sara Khan", "Pune", "Consumer"),
        )

        connection.executemany(
            """
            INSERT INTO products (product_id, name, category, unit_price, stock)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (7, "Desk Lamp", "Accessories", 1800.00, 50),
                (8, "Ethernet Adapter", "Computing", 1400.00, 45),
            ],
        )

    print_rows(
        "Rows created by INSERT",
        connection.execute(
            """
            SELECT customer_id, name, city
            FROM customers
            WHERE customer_id = ?
            """,
            (7,),
        ),
    )


def demonstrate_update(connection: sqlite3.Connection) -> None:
    """
    UPDATE changes existing rows.

    A WHERE clause is deliberately used. Without it, every row in the target
    table would be eligible for modification.
    """
    with transaction(connection):
        cursor = connection.execute(
            """
            UPDATE products
            SET stock = stock + ?
            WHERE category = ? AND stock < ?
            """,
            (10, "Accessories", 30),
        )

    print(f"\nUPDATE changed {cursor.rowcount} product row(s).")
    print_rows(
        "Updated accessory inventory",
        connection.execute(
            """
            SELECT name, stock
            FROM products
            WHERE category = ?
            ORDER BY stock DESC, name ASC
            """,
            ("Accessories",),
        ),
    )


def demonstrate_delete(connection: sqlite3.Connection) -> None:
    """
    DELETE removes rows.

    The demonstration first creates an intentionally temporary customer and
    then deletes it using a precise primary-key predicate.
    """
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO customers (customer_id, name, city, segment)
            VALUES (?, ?, ?, ?)
            """,
            (99, "Temporary Customer", "Test City", "Consumer"),
        )

        cursor = connection.execute(
            "DELETE FROM customers WHERE customer_id = ?",
            (99,),
        )

    print(f"\nDELETE removed {cursor.rowcount} row(s).")
    remaining = connection.execute(
        "SELECT COUNT(*) AS count FROM customers WHERE customer_id = ?",
        (99,),
    ).fetchone()["count"]
    print(f"Temporary customer remaining: {remaining}")


def demonstrate_where(connection: sqlite3.Connection) -> None:
    """
    WHERE restricts rows before they are returned or modified.

    AND, OR, IN, BETWEEN, LIKE, and NULL-aware predicates solve different
    filtering requirements.
    """
    rows = connection.execute(
        """
        SELECT name, city, segment
        FROM customers
        WHERE city = ? AND segment IN (?, ?)
        """,
        ("Lucknow", "Consumer", "Business"),
    ).fetchall()
    print_rows("WHERE with AND and IN", rows)

    rows = connection.execute(
        """
        SELECT name, unit_price
        FROM products
        WHERE unit_price BETWEEN ? AND ?
        ORDER BY unit_price
        """,
        (3000, 8000),
    ).fetchall()
    print_rows("WHERE with BETWEEN", rows)

    rows = connection.execute(
        """
        SELECT name
        FROM customers
        WHERE name LIKE ?
        """,
        ("%a%",),
    ).fetchall()
    print_rows("WHERE with LIKE", rows)

    null_rows = connection.execute(
        """
        SELECT order_id, status
        FROM orders
        WHERE status IS NULL
        """
    ).fetchall()
    print_rows("NULL requires IS NULL rather than = NULL", null_rows)


def demonstrate_order_by(connection: sqlite3.Connection) -> None:
    """
    ORDER BY controls result ordering.

    Sorting can use multiple keys. DESC applies to the first key while ASC
    gives a deterministic secondary order.
    """
    rows = connection.execute(
        """
        SELECT name, category, unit_price
        FROM products
        ORDER BY unit_price DESC, name ASC
        """
    ).fetchall()
    print_rows("Products ordered by price descending", rows)

    rows = connection.execute(
        """
        SELECT order_id, order_date, status
        FROM orders
        ORDER BY order_date DESC
        LIMIT ?
        """,
        (3,),
    ).fetchall()
    print_rows("Three most recent orders", rows)


def demonstrate_group_by(connection: sqlite3.Connection) -> None:
    """
    GROUP BY turns individual rows into groups for aggregate calculations.

    WHERE filters source rows before grouping. HAVING filters groups after the
    aggregate values have been calculated.
    """
    rows = connection.execute(
        """
        SELECT
            status,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY status
        ORDER BY order_count DESC, status ASC
        """
    ).fetchall()
    print_rows("Order count by status", rows)

    rows = connection.execute(
        """
        SELECT
            p.category,
            COUNT(*) AS line_count,
            SUM(oi.quantity) AS units_sold,
            ROUND(SUM(oi.quantity * oi.unit_price), 2) AS gross_value
        FROM order_items AS oi
        JOIN products AS p
            ON p.product_id = oi.product_id
        JOIN orders AS o
            ON o.order_id = oi.order_id
        WHERE o.status IN ('Paid', 'Shipped')
        GROUP BY p.category
        HAVING SUM(oi.quantity) >= ?
        ORDER BY gross_value DESC
        """,
        (2,),
    ).fetchall()
    print_rows("Grouped category sales", rows)


def demonstrate_customer_report(connection: sqlite3.Connection) -> None:
    """
    A realistic reporting query combines filtering, joins, aggregation,
    grouping, HAVING, and ordering.

    Cancelled orders are excluded before totals are calculated.
    """
    rows = connection.execute(
        """
        SELECT
            c.customer_id,
            c.name,
            c.city,
            COUNT(DISTINCT o.order_id) AS completed_orders,
            ROUND(SUM(oi.quantity * oi.unit_price), 2) AS customer_value
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status IN ('Paid', 'Shipped')
        GROUP BY c.customer_id, c.name, c.city
        HAVING customer_value >= ?
        ORDER BY customer_value DESC, c.name ASC
        """,
        (10000,),
    ).fetchall()
    print_rows("Customers with at least 10,000 of completed order value", rows)


def demonstrate_parameterization(connection: sqlite3.Connection) -> None:
    """
    Parameters are data, not SQL syntax.

    Concatenating untrusted input into SQL can change the meaning of a query.
    SQLite's parameter binding prevents that class of injection for values.
    """
    requested_city = "Lucknow"
    rows = connection.execute(
        """
        SELECT customer_id, name, city
        FROM customers
        WHERE city = ?
        ORDER BY name
        """,
        (requested_city,),
    ).fetchall()
    print_rows("Safe parameterized search", rows)

    malicious_text = "' OR 1=1 --"
    rows = connection.execute(
        """
        SELECT customer_id, name
        FROM customers
        WHERE name = ?
        """,
        (malicious_text,),
    ).fetchall()
    print_rows("Malicious-looking input treated as ordinary data", rows)


def demonstrate_transactions(connection: sqlite3.Connection) -> None:
    """
    Transactions protect multi-statement changes.

    This transaction intentionally fails after changing stock. The rollback
    means the earlier UPDATE does not remain in the database.
    """
    original_stock = connection.execute(
        "SELECT stock FROM products WHERE product_id = ?",
        (1,),
    ).fetchone()["stock"]

    try:
        with transaction(connection):
            connection.execute(
                """
                UPDATE products
                SET stock = stock - ?
                WHERE product_id = ? AND stock >= ?
                """,
                (3, 1, 3),
            )

            connection.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                (999999, 1, 3, 4500.00),
            )
    except sqlite3.IntegrityError as exc:
        print(f"\nTransaction rolled back after expected failure: {exc}")

    current_stock = connection.execute(
        "SELECT stock FROM products WHERE product_id = ?",
        (1,),
    ).fetchone()["stock"]

    print(f"Stock before failed transaction: {original_stock}")
    print(f"Stock after failed transaction:  {current_stock}")


def demonstrate_validation_and_constraints(connection: sqlite3.Connection) -> None:
    """
    Database constraints form a second line of defense after application
    validation. A CHECK constraint prevents invalid inventory from being stored.
    """
    try:
        connection.execute(
            """
            INSERT INTO products (product_id, name, category, unit_price, stock)
            VALUES (?, ?, ?, ?, ?)
            """,
            (500, "Invalid Product", "Computing", -1, 10),
        )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        print(f"\nConstraint rejected invalid product: {exc}")

    try:
        connection.execute(
            """
            INSERT INTO customers (customer_id, name, city, segment)
            VALUES (?, ?, ?, ?)
            """,
            (501, "Invalid Segment Customer", "Delhi", "Unknown"),
        )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        print(f"Constraint rejected invalid segment: {exc}")


def demonstrate_update_safety(connection: sqlite3.Connection) -> None:
    """
    A practical safety check verifies the affected-row count before committing
    a sensitive UPDATE. The operation intentionally targets one product.
    """
    product_id = 8
    new_price = 1550.00

    with transaction(connection):
        cursor = connection.execute(
            """
            UPDATE products
            SET unit_price = ?
            WHERE product_id = ?
            """,
            (new_price, product_id),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly one product update, got {cursor.rowcount}"
            )

    print_rows(
        "Safely updated product",
        connection.execute(
            """
            SELECT product_id, name, unit_price
            FROM products
            WHERE product_id = ?
            """,
            (product_id,),
        ),
    )


def demonstrate_query_plan(connection: sqlite3.Connection) -> None:
    """
    EXPLAIN QUERY PLAN reveals how SQLite intends to execute a query.

    Indexes can reduce the amount of data SQLite must scan, but indexes also
    consume storage and impose write-maintenance work.
    """
    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT order_id, customer_id, order_date
        FROM orders
        WHERE customer_id = ?
        ORDER BY order_date
        """,
        (2,),
    ).fetchall()

    print_rows("Query plan for an indexed customer lookup", plan)


def demonstrate_safe_dynamic_order(connection: sqlite3.Connection) -> None:
    """
    SQL parameters bind values, not identifiers such as column names.

    When a user needs selectable sorting, map a small trusted set of logical
    names to hard-coded SQL expressions instead of concatenating arbitrary text.
    """
    allowed_sort_columns = {
        "name": "name",
        "price": "unit_price",
        "stock": "stock",
    }

    requested_sort = "price"
    sort_expression = allowed_sort_columns.get(requested_sort)

    if sort_expression is None:
        raise ValueError("Unsupported sort option")

    query = f"""
        SELECT product_id, name, unit_price, stock
        FROM products
        ORDER BY {sort_expression} DESC
    """

    rows = connection.execute(query).fetchall()
    print_rows("Safely selected dynamic sort column", rows)


def demonstrate_delete_cascade(connection: sqlite3.Connection) -> None:
    """
    Foreign-key cascade behavior is demonstrated with a temporary order.

    Deleting the order automatically deletes its dependent order_items rows,
    while product records remain because their foreign key is restrictive.
    """
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO orders (order_id, customer_id, order_date, status)
            VALUES (?, ?, ?, ?)
            """,
            (9000, 1, "2026-10-01", "Cancelled"),
        )
        connection.execute(
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            """,
            (9000, 1, 1, 4500.00),
        )

        before = connection.execute(
            "SELECT COUNT(*) AS count FROM order_items WHERE order_id = ?",
            (9000,),
        ).fetchone()["count"]

        connection.execute(
            "DELETE FROM orders WHERE order_id = ?",
            (9000,),
        )

        after = connection.execute(
            "SELECT COUNT(*) AS count FROM order_items WHERE order_id = ?",
            (9000,),
        ).fetchone()["count"]

    print(f"\nDependent rows before DELETE: {before}")
    print(f"Dependent rows after DELETE:  {after}")


def run_learning_sequence(connection: sqlite3.Connection) -> None:
    print("=" * 72)
    print("SQL FUNDAMENTALS LAB")
    print("SELECT | INSERT | UPDATE | DELETE | WHERE | ORDER BY | GROUP BY")
    print("=" * 72)

    demonstrate_select(connection)
    demonstrate_insert(connection)
    demonstrate_update(connection)
    demonstrate_delete(connection)
    demonstrate_where(connection)
    demonstrate_order_by(connection)
    demonstrate_group_by(connection)
    demonstrate_customer_report(connection)
    demonstrate_parameterization(connection)
    demonstrate_transactions(connection)
    demonstrate_validation_and_constraints(connection)
    demonstrate_update_safety(connection)
    demonstrate_query_plan(connection)
    demonstrate_safe_dynamic_order(connection)
    demonstrate_delete_cascade(connection)


def main() -> None:
    """
    Use an in-memory database by default so execution leaves no persistent
    files behind. Set PERSIST_TO_DISK to True when a local SQLite database is
    useful for inspection.
    """
    persist_to_disk = False
    database_path = DATABASE_FILE if persist_to_disk else ":memory:"

    connection = connect_database(database_path)

    try:
        create_schema(connection)
        seed_data(connection)
        run_learning_sequence(connection)
        print("\nSQL laboratory completed successfully.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
