#!/usr/bin/env python3
"""
Indexing laboratory: B-tree, hash, composite, partial indexes, and selectivity.

This self-contained program uses SQLite's built-in database engine so it can run
without third-party packages. SQLite supports B-tree indexes and partial indexes;
its hash-index equivalent is modeled explicitly so the program can demonstrate
the data-structure and selectivity decisions without pretending that SQLite has
a native hash index.

The program combines:
- conceptual index structures
- a working SQLite workload
- query-plan inspection with EXPLAIN QUERY PLAN
- composite-index behavior
- partial-index behavior
- selectivity calculations
- a Python hash-index simulation
- validation and benchmarking
"""

from __future__ import annotations

import random
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable


SEED = 42


@dataclass(frozen=True)
class QueryResult:
    description: str
    row_count: int
    elapsed_ms: float
    plan: tuple[str, ...]


def heading(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def explain_query(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple = (),
) -> tuple[str, ...]:
    rows = connection.execute(
        "EXPLAIN QUERY PLAN " + sql,
        parameters,
    ).fetchall()
    return tuple(str(row[-1]) for row in rows)


def timed_query(
    connection: sqlite3.Connection,
    description: str,
    sql: str,
    parameters: tuple = (),
) -> QueryResult:
    start = time.perf_counter()
    rows = connection.execute(sql, parameters).fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000
    plan = explain_query(connection, sql, parameters)
    return QueryResult(description, len(rows), elapsed_ms, plan)


def print_result(result: QueryResult) -> None:
    print(f"\n{result.description}")
    print(f"Rows returned: {result.row_count}")
    print(f"Elapsed: {result.elapsed_ms:.3f} ms")
    print("Plan:")
    for line in result.plan:
        print(f"  {line}")


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = MEMORY")
    connection.execute("PRAGMA synchronous = OFF")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            country TEXT NOT NULL,
            customer_tier TEXT NOT NULL
                CHECK (customer_tier IN ('standard', 'premium', 'enterprise'))
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL
                REFERENCES customers(customer_id),
            order_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
            region TEXT NOT NULL,
            order_date TEXT NOT NULL,
            total_cents INTEGER NOT NULL CHECK (total_cents >= 0)
        );

        CREATE TABLE support_events (
            event_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL
                REFERENCES customers(customer_id),
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        """
    )


def populate_data(
    connection: sqlite3.Connection,
    customer_count: int = 20_000,
    order_count: int = 100_000,
    event_count: int = 50_000,
) -> None:
    rng = random.Random(SEED)

    countries = ["IN", "US", "DE", "GB", "SG", "AU", "CA", "FR"]
    tiers = ["standard", "premium", "enterprise"]
    regions = ["north", "south", "east", "west"]
    statuses = ["pending", "paid", "shipped", "cancelled"]
    event_types = ["login", "password_reset", "invoice", "shipment", "support"]

    customers = []
    for customer_id in range(1, customer_count + 1):
        country = rng.choices(
            countries,
            weights=[40, 18, 10, 8, 6, 5, 7, 6],
        )[0]
        tier = rng.choices(
            tiers,
            weights=[75, 22, 3],
        )[0]
        customers.append(
            (
                customer_id,
                f"customer{customer_id}@example.test",
                country,
                tier,
            )
        )

    connection.executemany(
        """
        INSERT INTO customers(customer_id, email, country, customer_tier)
        VALUES (?, ?, ?, ?)
        """,
        customers,
    )

    orders = []
    for order_id in range(1, order_count + 1):
        customer_id = rng.randint(1, customer_count)
        status = rng.choices(
            statuses,
            weights=[8, 28, 45, 19],
        )[0]
        region = rng.choice(regions)

        year = rng.choice([2024, 2025, 2026])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)

        order_date = f"{year:04d}-{month:02d}-{day:02d}"
        total_cents = rng.randint(500, 500_000)

        orders.append(
            (
                order_id,
                customer_id,
                f"ORD-{order_id:08d}",
                status,
                region,
                order_date,
                total_cents,
            )
        )

    connection.executemany(
        """
        INSERT INTO orders(
            order_id,
            customer_id,
            order_number,
            status,
            region,
            order_date,
            total_cents
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )

    events = []
    for event_id in range(1, event_count + 1):
        customer_id = rng.randint(1, customer_count)
        event_type = rng.choice(event_types)
        year = rng.choice([2025, 2026])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        hour = rng.randint(0, 23)

        created_at = (
            f"{year:04d}-{month:02d}-{day:02d}"
            f"T{hour:02d}:00:00"
        )

        events.append(
            (
                event_id,
                customer_id,
                event_type,
                created_at,
                '{"source":"demo"}',
            )
        )

    connection.executemany(
        """
        INSERT INTO support_events(
            event_id,
            customer_id,
            event_type,
            created_at,
            payload
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        events,
    )

    connection.commit()


def demonstrate_btree(connection: sqlite3.Connection) -> None:
    heading("B-tree index: equality, range predicates, and ordering")

    connection.execute(
        "CREATE INDEX idx_orders_order_date ON orders(order_date)"
    )

    equality = timed_query(
        connection,
        "B-tree equality lookup",
        """
        SELECT order_id, order_date, total_cents
        FROM orders
        WHERE order_date = ?
        """,
        ("2026-06-15",),
    )
    print_result(equality)

    range_query = timed_query(
        connection,
        "B-tree range lookup",
        """
        SELECT order_id, order_date, total_cents
        FROM orders
        WHERE order_date >= ? AND order_date < ?
        ORDER BY order_date
        LIMIT 20
        """,
        ("2026-06-01", "2026-07-01"),
    )
    print_result(range_query)

    print(
        "\nA B-tree keeps indexed keys in an ordered structure, so it is "
        "naturally useful for equality, range, and ordered-access patterns."
    )


def demonstrate_hash_concept() -> None:
    heading("Hash index concept: direct equality lookup")

    customer_ids = range(1, 20_001)
    hash_index: dict[str, list[int]] = defaultdict(list)

    for customer_id in customer_ids:
        email = f"customer{customer_id}@example.test"
        hash_index[email].append(customer_id)

    target = "customer17000@example.test"
    matches = hash_index.get(target, [])

    print(f"Hash lookup for {target}: {matches}")
    print(
        "A hash index maps a key to a bucket and is primarily designed for "
        "equality predicates. It does not provide the ordered traversal "
        "semantics that make a B-tree useful for ranges."
    )

    try:
        hash_index["customer17000@example.test"].append("invalid")
    except AttributeError:
        print("Unexpected mutation was rejected.")

    print(
        "The simulation deliberately stores bucket values rather than "
        "assuming every key is unique. Real indexes must account for "
        "duplicate keys and collisions."
    )


def demonstrate_composite_index(connection: sqlite3.Connection) -> None:
    heading("Composite index: equality plus range and the leftmost prefix")

    connection.execute(
        """
        CREATE INDEX idx_orders_region_status_date
        ON orders(region, status, order_date)
        """
    )

    exact_prefix = timed_query(
        connection,
        "Composite lookup using region + status",
        """
        SELECT order_id, order_date, total_cents
        FROM orders
        WHERE region = ? AND status = ?
        ORDER BY order_date
        LIMIT 25
        """,
        ("south", "paid"),
    )
    print_result(exact_prefix)

    range_suffix = timed_query(
        connection,
        "Composite lookup using all three columns",
        """
        SELECT order_id, order_date, total_cents
        FROM orders
        WHERE region = ?
          AND status = ?
          AND order_date >= ?
          AND order_date < ?
        ORDER BY order_date
        LIMIT 25
        """,
        ("south", "paid", "2026-01-01", "2027-01-01"),
    )
    print_result(range_suffix)

    leading_column = timed_query(
        connection,
        "Composite lookup using only the leading column",
        """
        SELECT order_id, region, status
        FROM orders
        WHERE region = ?
        LIMIT 25
        """,
        ("south",),
    )
    print_result(leading_column)

    suffix_only = timed_query(
        connection,
        "Suffix-only predicate: less aligned with the composite index",
        """
        SELECT order_id, region, status
        FROM orders
        WHERE status = ?
        LIMIT 25
        """,
        ("paid",),
    )
    print_result(suffix_only)

    print(
        "\nColumn order matters. The index begins with region, then status, "
        "then order_date. Predicates that constrain the leading columns "
        "usually obtain more direct benefit than a predicate on status alone."
    )


def demonstrate_partial_index(connection: sqlite3.Connection) -> None:
    heading("Partial index: index only rows needed by a recurring workload")

    connection.execute(
        """
        CREATE INDEX idx_pending_orders_date
        ON orders(order_date)
        WHERE status = 'pending'
        """
    )

    pending_query = timed_query(
        connection,
        "Query matching the partial-index predicate",
        """
        SELECT order_id, customer_id, order_date
        FROM orders
        WHERE status = 'pending'
          AND order_date >= ?
        ORDER BY order_date
        LIMIT 30
        """,
        ("2026-10-01",),
    )
    print_result(pending_query)

    shipped_query = timed_query(
        connection,
        "Query outside the partial-index predicate",
        """
        SELECT order_id, customer_id, order_date
        FROM orders
        WHERE status = 'shipped'
          AND order_date >= ?
        ORDER BY order_date
        LIMIT 30
        """,
        ("2026-10-01",),
    )
    print_result(shipped_query)

    print(
        "\nA partial index contains only rows satisfying its predicate. "
        "That reduces index size when the indexed subset is substantially "
        "smaller than the table and the application repeatedly queries that "
        "subset."
    )


def distinct_count(
    connection: sqlite3.Connection,
    column: str,
) -> tuple[int, int]:
    total = connection.execute(
        f"SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    distinct = connection.execute(
        f"SELECT COUNT(DISTINCT {column}) FROM orders"
    ).fetchone()[0]

    return total, distinct


def demonstrate_selectivity(connection: sqlite3.Connection) -> None:
    heading("Index selectivity: measuring how discriminating a column is")

    for column in ("status", "region", "customer_id", "order_date"):
        total, distinct = distinct_count(connection, column)
        selectivity = distinct / total if total else 0
        print(
            f"{column:12s} rows={total:7d} "
            f"distinct={distinct:7d} "
            f"distinct/rows={selectivity:.6f}"
        )

    status_distribution = connection.execute(
        """
        SELECT status, COUNT(*)
        FROM orders
        GROUP BY status
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()

    print("\nStatus distribution:")
    for status, count in status_distribution:
        print(f"  {status:10s} {count:7d}")

    print(
        "\nSelectivity is workload-dependent. A low-cardinality column such "
        "as status may identify a large fraction of the table and can be a "
        "weak standalone index candidate. A high-cardinality column such as "
        "customer_id usually narrows a lookup much more effectively."
    )


def demonstrate_covering_style_query(connection: sqlite3.Connection) -> None:
    heading("Composite index used to support a reporting query")

    connection.execute(
        """
        CREATE INDEX idx_orders_customer_date_total
        ON orders(customer_id, order_date, total_cents)
        """
    )

    result = timed_query(
        connection,
        "Customer history ordered by date",
        """
        SELECT order_date, total_cents
        FROM orders
        WHERE customer_id = ?
        ORDER BY order_date DESC
        LIMIT 15
        """,
        (17000,),
    )
    print_result(result)

    print(
        "\nIncluding projected columns in an index can reduce table lookups "
        "for some engines and workloads. The exact covering-index behavior "
        "is database-engine specific, so production decisions should use "
        "the target engine's execution plans."
    )


def demonstrate_constraint_index(connection: sqlite3.Connection) -> None:
    heading("Indexes created by uniqueness constraints")

    connection.execute(
        """
        CREATE UNIQUE INDEX idx_support_event_identity
        ON support_events(customer_id, event_type, created_at)
        """
    )

    duplicate = (
        1,
        "login",
        "2026-01-01T00:00:00",
    )

    connection.execute(
        """
        INSERT INTO support_events(
            customer_id, event_type, created_at, payload
        )
        VALUES (?, ?, ?, ?)
        """,
        (*duplicate, '{"source":"constraint-demo"}'),
    )

    try:
        connection.execute(
            """
            INSERT INTO support_events(
                customer_id, event_type, created_at, payload
            )
            VALUES (?, ?, ?, ?)
            """,
            (*duplicate, '{"source":"duplicate"}'),
        )
    except sqlite3.IntegrityError as exc:
        print("Duplicate rejected by unique index:", exc)
        connection.rollback()

    print(
        "Indexes can enforce integrity as well as accelerate reads. "
        "A uniqueness rule belongs in the database when duplicate values "
        "would violate the domain invariant."
    )


def demonstrate_statistics(connection: sqlite3.Connection) -> None:
    heading("Frequency distribution and selectivity-aware reasoning")

    rows = connection.execute(
        """
        SELECT status, region, COUNT(*) AS row_count
        FROM orders
        GROUP BY status, region
        ORDER BY row_count DESC
        """
    ).fetchall()

    print("Largest status/region groups:")
    for status, region, count in rows[:8]:
        print(f"  status={status:10s} region={region:6s} rows={count}")

    status_counts = Counter(
        row[0]
        for row in connection.execute("SELECT status FROM orders")
    )

    total = sum(status_counts.values())
    probabilities = [
        count / total
        for count in status_counts.values()
        if count
    ]

    entropy = -sum(p * __import__("math").log2(p) for p in probabilities)

    print(f"\nStatus distribution entropy: {entropy:.3f} bits")
    print(
        "Distribution statistics help explain why cardinality alone is not "
        "enough. Two columns can have the same number of distinct values "
        "while their value frequencies produce very different workloads."
    )


def demonstrate_edge_cases(connection: sqlite3.Connection) -> None:
    heading("Validation, edge cases, and common indexing mistakes")

    invalid_date = ""
    try:
        if not invalid_date:
            raise ValueError("A date predicate must not be empty.")
    except ValueError as exc:
        print("Application validation:", exc)

    print(
        "\nCommon mistakes demonstrated conceptually:"
        "\n- indexing every column without measuring workload"
        "\n- placing low-selectivity columns first in composite indexes"
        "\n- creating a partial index whose predicate does not match queries"
        "\n- expecting a B-tree to behave like a hash table"
        "\n- ignoring write overhead and index storage"
        "\n- evaluating plans without realistic data distribution"
        "\n- using functions on indexed columns without considering sargability"
    )

    function_query = timed_query(
        connection,
        "Expression predicate example",
        """
        SELECT order_id
        FROM orders
        WHERE substr(order_date, 1, 7) = ?
        LIMIT 20
        """,
        ("2026-06",),
    )
    print_result(function_query)

    print(
        "\nWrapping an indexed column in an expression can prevent a normal "
        "column index from being used effectively. Expression indexes are "
        "an engine-specific alternative when this access pattern is stable."
    )


def compare_index_storage(connection: sqlite3.Connection) -> None:
    heading("Index inventory")

    indexes = connection.execute(
        """
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type = 'index'
        ORDER BY tbl_name, name
        """
    ).fetchall()

    for name, table, definition in indexes:
        print(f"\n{name}")
        print(f"  table: {table}")
        print(f"  definition: {definition}")


def run_transaction_demo(connection: sqlite3.Connection) -> None:
    heading("Transaction and index-maintenance cost")

    connection.execute("BEGIN")
    try:
        connection.execute(
            """
            INSERT INTO orders(
                customer_id,
                order_number,
                status,
                region,
                order_date,
                total_cents
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                17000,
                "ORD-TRANSACTION-DEMO",
                "pending",
                "south",
                "2026-10-07",
                12500,
            ),
        )

        row = connection.execute(
            """
            SELECT order_id, status, order_date
            FROM orders
            WHERE order_number = ?
            """,
            ("ORD-TRANSACTION-DEMO",),
        ).fetchone()

        print("Inserted row inside transaction:", row)
        connection.rollback()
        print("Transaction rolled back; index entries are restored with table state.")
    except Exception:
        connection.rollback()
        raise


def run() -> None:
    connection = create_connection()

    try:
        create_schema(connection)
        populate_data(connection)

        heading("Indexing laboratory")
        print(
            "Dataset: 20,000 customers, 100,000 orders, and 50,000 events."
        )
        print(
            "The same workload is used to make index decisions observable "
            "through query plans."
        )

        demonstrate_btree(connection)
        demonstrate_hash_concept()
        demonstrate_composite_index(connection)
        demonstrate_partial_index(connection)
        demonstrate_selectivity(connection)
        demonstrate_covering_style_query(connection)
        demonstrate_constraint_index(connection)
        demonstrate_statistics(connection)
        demonstrate_edge_cases(connection)
        compare_index_storage(connection)
        run_transaction_demo(connection)

        heading("Final engineering observations")
        print(
            "B-tree indexes are the general-purpose choice for ordered access, "
            "ranges, equality, and many ORDER BY patterns."
        )
        print(
            "Hash indexes are specialized for equality access and do not "
            "provide the same ordering semantics as B-trees."
        )
        print(
            "Composite indexes encode a multi-column access path; column "
            "order determines which predicates can use the leading portion."
        )
        print(
            "Partial indexes are valuable when a stable, frequently queried "
            "subset is much smaller than the complete table."
        )
        print(
            "Selectivity must be evaluated with actual data distribution and "
            "real query predicates rather than guessed from column names."
        )
        print(
            "Every index improves some reads at the cost of storage and "
            "maintenance work during INSERT, UPDATE, and DELETE operations."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    run()
