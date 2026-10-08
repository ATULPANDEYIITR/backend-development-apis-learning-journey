#!/usr/bin/env python3
"""
Query Optimization Laboratory

This self-contained program demonstrates:
- query planning
- sequential scans
- index scans
- EXPLAIN-style plan inspection
- EXPLAIN ANALYZE-style execution measurement
- selectivity and cardinality
- composite and covering indexes
- predicate design
- join planning
- sorting and aggregation
- plan choice trade-offs
- stale statistics
- parameter-sensitive planning concepts
- practical optimization diagnostics

The executable demonstrations use SQLite from Python's standard library so that
the file runs without external packages. SQLite's EXPLAIN QUERY PLAN terminology
differs from PostgreSQL's EXPLAIN output, but the underlying optimization ideas
are directly comparable.

The program also contains a small PostgreSQL-oriented plan interpreter for
recognizing common PostgreSQL plan nodes such as Seq Scan, Index Scan,
Index Only Scan, Bitmap Heap Scan, Sort, Aggregate, and Nested Loop.
"""

from __future__ import annotations

import random
import sqlite3
import statistics
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def create_database() -> sqlite3.Connection:
    """Create a temporary in-memory database containing realistic order data."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region TEXT NOT NULL,
            customer_tier TEXT NOT NULL,
            active INTEGER NOT NULL CHECK (active IN (0, 1))
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total_amount REAL NOT NULL CHECK (total_amount >= 0),
            sales_channel TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
        """
    )

    regions = ["North", "South", "East", "West"]
    tiers = ["STANDARD", "PREMIUM", "ENTERPRISE"]
    statuses = ["PENDING", "SHIPPED", "DELIVERED", "CANCELLED"]
    channels = ["WEB", "MOBILE", "STORE", "PARTNER"]

    rng = random.Random(42)

    customers = []
    for customer_id in range(1, 501):
        customers.append(
            (
                customer_id,
                f"Customer {customer_id:04d}",
                regions[(customer_id - 1) % len(regions)],
                tiers[(customer_id * 7) % len(tiers)],
                1 if customer_id % 19 else 0,
            )
        )

    connection.executemany(
        """
        INSERT INTO customers
            (customer_id, customer_name, region, customer_tier, active)
        VALUES (?, ?, ?, ?, ?)
        """,
        customers,
    )

    orders = []
    for order_id in range(1, 100_001):
        customer_id = ((order_id * 37) % 500) + 1

        # Make a recent period contain enough variation to demonstrate
        # selective and non-selective predicates.
        year = 2024 + ((order_id // 30_000) % 3)
        month = ((order_id // 2500) % 12) + 1
        day = ((order_id // 80) % 28) + 1
        order_date = f"{year:04d}-{month:02d}-{day:02d}"

        status = statuses[(order_id * 13) % len(statuses)]
        amount = round(25 + rng.random() * 2500, 2)
        channel = channels[(order_id * 11) % len(channels)]

        orders.append(
            (
                order_id,
                customer_id,
                order_date,
                status,
                amount,
                channel,
            )
        )

    connection.executemany(
        """
        INSERT INTO orders
            (order_id, customer_id, order_date, status, total_amount, sales_channel)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        orders,
    )

    connection.commit()
    return connection


# ---------------------------------------------------------------------------
# EXPLAIN and EXPLAIN ANALYZE-style inspection
# ---------------------------------------------------------------------------

def explain_query(connection: sqlite3.Connection, sql: str, parameters=()) -> list[str]:
    """
    Display SQLite's query plan.

    SQLite uses EXPLAIN QUERY PLAN rather than PostgreSQL's EXPLAIN output.
    The important lesson is still the same: inspect the access path chosen
    before deciding whether an index or query rewrite is justified.
    """
    rows = connection.execute(
        "EXPLAIN QUERY PLAN " + sql,
        parameters,
    ).fetchall()

    details = []
    for row in rows:
        detail = str(row["detail"])
        details.append(detail)
        print(f"  {detail}")

    return details


def explain_analyze(
    connection: sqlite3.Connection,
    sql: str,
    parameters=(),
    repetitions: int = 5,
) -> tuple[float, int]:
    """
    Execute a query repeatedly and report observed runtime.

    This is an educational approximation of PostgreSQL EXPLAIN ANALYZE:
    PostgreSQL instruments the actual execution plan and reports node-level
    estimates versus actual rows and timing. Here we separately inspect the
    plan and measure the completed query from Python.
    """
    durations_ms = []
    row_count = 0

    for _ in range(repetitions):
        start = time.perf_counter()
        rows = connection.execute(sql, parameters).fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        durations_ms.append(elapsed)
        row_count = len(rows)

    average = statistics.mean(durations_ms)

    print(f"  Rows returned: {row_count}")
    print(f"  Average execution time: {average:.3f} ms")
    print(f"  Minimum execution time: {min(durations_ms):.3f} ms")
    print(f"  Maximum execution time: {max(durations_ms):.3f} ms")

    return average, row_count


def show_query(connection: sqlite3.Connection, title: str, sql: str, parameters=()):
    print(f"\n=== {title} ===")
    print("SQL:")
    print(sql.strip())
    print("\nPlan:")
    explain_query(connection, sql, parameters)
    print("\nObserved execution:")
    explain_analyze(connection, sql, parameters)


# ---------------------------------------------------------------------------
# Sequential scans versus index access
# ---------------------------------------------------------------------------

def demonstrate_sequential_scan(connection: sqlite3.Connection) -> None:
    """
    Show a query that can initially require a full table scan.

    A sequential scan examines rows without using an index on the filtered
    column. This can be reasonable when a large percentage of the table is
    required because following an index would cause many random table lookups.
    """
    sql = """
        SELECT order_id, customer_id, total_amount
        FROM orders
        WHERE status = ?
    """
    show_query(
        connection,
        "Sequential scan candidate",
        sql,
        ("DELIVERED",),
    )


def create_basic_index(connection: sqlite3.Connection) -> None:
    """
    Add an index that makes equality filtering on status searchable.

    An index is not automatically beneficial for every query. Its usefulness
    depends on selectivity, table size, data distribution, query shape, and
    the cost of retrieving the required rows.
    """
    connection.execute(
        "CREATE INDEX idx_orders_status ON orders(status)"
    )
    connection.commit()


def demonstrate_index_scan(connection: sqlite3.Connection) -> None:
    """
    Query a highly selective indexed value.

    SQLite may choose the index because the predicate is selective. PostgreSQL
    could represent the equivalent access path as an Index Scan or Bitmap Heap
    Scan depending on cost estimates and row distribution.
    """
    sql = """
        SELECT order_id, customer_id, total_amount
        FROM orders
        WHERE status = ? AND order_id = ?
    """
    show_query(
        connection,
        "Selective indexed lookup",
        sql,
        ("DELIVERED", 98765),
    )


# ---------------------------------------------------------------------------
# Selectivity and sargability
# ---------------------------------------------------------------------------

def demonstrate_selectivity(connection: sqlite3.Connection) -> None:
    """
    Compare a highly selective predicate with a broad predicate.

    Selectivity describes the fraction of rows expected to satisfy a predicate.
    A low fraction often makes index access attractive; a high fraction can make
    a sequential scan cheaper.
    """
    print("\n=== Selectivity ===")

    predicates = [
        ("Very selective", "WHERE order_id = ?", (98765,)),
        ("Moderately selective", "WHERE customer_id = ?", (17,)),
        ("Broad predicate", "WHERE status = ?", ("DELIVERED",)),
    ]

    total = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    for name, predicate, parameters in predicates:
        count = connection.execute(
            "SELECT COUNT(*) FROM orders " + predicate,
            parameters,
        ).fetchone()[0]

        selectivity = count / total
        print(
            f"{name}: rows={count:,}, "
            f"selectivity={selectivity:.4%}"
        )


def demonstrate_sargability(connection: sqlite3.Connection) -> None:
    """
    Show why applying a function to an indexed column can change index usage.

    A predicate such as LOWER(sales_channel) = 'web' may prevent a normal
    B-tree index on sales_channel from being used efficiently because the
    database must evaluate the expression rather than directly searching
    the indexed values.

    A range predicate on the raw date column is more directly searchable.
    """
    connection.execute(
        "CREATE INDEX idx_orders_channel ON orders(sales_channel)"
    )
    connection.execute(
        "CREATE INDEX idx_orders_date ON orders(order_date)"
    )
    connection.commit()

    function_predicate = """
        SELECT COUNT(*)
        FROM orders
        WHERE LOWER(sales_channel) = 'web'
    """

    range_predicate = """
        SELECT COUNT(*)
        FROM orders
        WHERE order_date >= '2025-01-01'
          AND order_date < '2026-01-01'
    """

    print("\n=== Sargability ===")
    print("Function applied to indexed column:")
    explain_query(connection, function_predicate)

    print("Range predicate on indexed column:")
    explain_query(connection, range_predicate)


# ---------------------------------------------------------------------------
# Composite indexes
# ---------------------------------------------------------------------------

def demonstrate_composite_index(connection: sqlite3.Connection) -> None:
    """
    Demonstrate an index whose column order follows a real query pattern.

    For queries filtering by customer_id and then restricting order_date,
    (customer_id, order_date) gives the database an ordered search structure
    matching both predicates.
    """
    connection.execute(
        """
        CREATE INDEX idx_orders_customer_date
        ON orders(customer_id, order_date)
        """
    )
    connection.commit()

    sql = """
        SELECT order_id, order_date, total_amount
        FROM orders
        WHERE customer_id = ?
          AND order_date >= ?
          AND order_date < ?
        ORDER BY order_date
    """

    show_query(
        connection,
        "Composite index for equality plus range",
        sql,
        (17, "2025-01-01", "2026-01-01"),
    )


# ---------------------------------------------------------------------------
# Covering-index concept
# ---------------------------------------------------------------------------

def demonstrate_covering_index(connection: sqlite3.Connection) -> None:
    """
    Demonstrate an index containing all columns needed by a query.

    A covering index can allow the database to satisfy the query from index
    entries without visiting the base table for every matching row.

    PostgreSQL calls this an Index Only Scan when visibility conditions also
    permit the heap access to be avoided.
    """
    connection.execute(
        """
        CREATE INDEX idx_orders_customer_covering
        ON orders(customer_id, order_date, total_amount)
        """
    )
    connection.commit()

    sql = """
        SELECT order_date, total_amount
        FROM orders
        WHERE customer_id = ?
          AND order_date >= ?
        ORDER BY order_date
    """

    show_query(
        connection,
        "Covering-index candidate",
        sql,
        (42, "2025-01-01"),
    )


# ---------------------------------------------------------------------------
# Sorting and aggregation
# ---------------------------------------------------------------------------

def demonstrate_sorting_and_aggregation(connection: sqlite3.Connection) -> None:
    """
    Show a grouped aggregate with an explicit ordering requirement.

    EXPLAIN output should be read as a plan tree rather than as a simple
    declaration that an index is always required. Aggregation and sorting can
    have their own memory and CPU costs.
    """
    sql = """
        SELECT customer_id,
               COUNT(*) AS order_count,
               ROUND(SUM(total_amount), 2) AS revenue
        FROM orders
        WHERE order_date >= ?
        GROUP BY customer_id
        ORDER BY revenue DESC
        LIMIT 10
    """

    show_query(
        connection,
        "Aggregation and ordering",
        sql,
        ("2025-01-01",),
    )


# ---------------------------------------------------------------------------
# Join planning
# ---------------------------------------------------------------------------

def demonstrate_join_plan(connection: sqlite3.Connection) -> None:
    """
    Demonstrate a join where an index on the child table can support lookup
    by the foreign-key column.

    Join planning depends on estimated row counts, available indexes, join
    predicates, and the relative costs of nested-loop, hash, or merge-style
    strategies in database systems that support those algorithms.
    """
    connection.execute(
        "CREATE INDEX idx_orders_customer_id ON orders(customer_id)"
    )
    connection.commit()

    sql = """
        SELECT c.region,
               c.customer_tier,
               COUNT(*) AS orders
        FROM customers AS c
        JOIN orders AS o
          ON o.customer_id = c.customer_id
        WHERE c.region = ?
          AND c.active = 1
        GROUP BY c.region, c.customer_tier
        ORDER BY orders DESC
    """

    show_query(
        connection,
        "Join and aggregation plan",
        sql,
        ("North",),
    )


# ---------------------------------------------------------------------------
# Query anti-patterns
# ---------------------------------------------------------------------------

def demonstrate_query_rewrites(connection: sqlite3.Connection) -> None:
    """
    Compare two logically similar date filters.

    A half-open range is often preferable to applying DATE() or another
    function to the indexed column because it preserves a direct range
    predicate over the stored values.
    """
    function_query = """
        SELECT COUNT(*)
        FROM orders
        WHERE substr(order_date, 1, 4) = ?
    """

    range_query = """
        SELECT COUNT(*)
        FROM orders
        WHERE order_date >= ?
          AND order_date < ?
    """

    print("\n=== Query rewrite comparison ===")

    print("Expression-based predicate:")
    explain_query(connection, function_query, ("2025",))

    print("Range predicate:")
    explain_query(connection, range_query, ("2025-01-01", "2026-01-01"))


# ---------------------------------------------------------------------------
# PostgreSQL plan model
# ---------------------------------------------------------------------------

@dataclass
class PlanNode:
    """
    Minimal PostgreSQL-like plan representation for educational reasoning.

    This does not execute SQL. It demonstrates the information a PostgreSQL
    EXPLAIN plan exposes and how plan nodes compose into a tree.
    """

    node_type: str
    estimated_rows: int
    actual_rows: int
    startup_cost: float
    total_cost: float
    actual_time_ms: float
    children: list["PlanNode"] = field(default_factory=list)

    def row_estimation_error(self) -> float:
        if self.estimated_rows == 0:
            return float("inf") if self.actual_rows else 0.0
        return self.actual_rows / self.estimated_rows

    def display(self, depth: int = 0) -> None:
        indentation = "  " * depth
        ratio = self.row_estimation_error()

        print(
            f"{indentation}{self.node_type}: "
            f"estimated={self.estimated_rows:,}, "
            f"actual={self.actual_rows:,}, "
            f"cost={self.startup_cost:.2f}..{self.total_cost:.2f}, "
            f"time={self.actual_time_ms:.3f} ms, "
            f"actual/estimated={ratio:.2f}x"
        )

        for child in self.children:
            child.display(depth + 1)


def demonstrate_postgresql_plan_model() -> None:
    """
    Illustrate the difference between estimated and actual execution data.

    A large actual/estimated ratio is a useful diagnostic signal. It can lead
    to poor join order, an unsuitable scan type, excessive memory use, or
    unexpectedly expensive operations. PostgreSQL normally gets estimates from
    table statistics maintained by ANALYZE.
    """
    print("\n=== PostgreSQL-style plan model ===")

    index_scan = PlanNode(
        node_type="Index Scan using idx_orders_customer_date on orders",
        estimated_rows=120,
        actual_rows=4_800,
        startup_cost=0.42,
        total_cost=92.00,
        actual_time_ms=7.83,
    )

    aggregate = PlanNode(
        node_type="Aggregate",
        estimated_rows=1,
        actual_rows=1,
        startup_cost=95.00,
        total_cost=96.50,
        actual_time_ms=8.21,
        children=[index_scan],
    )

    aggregate.display()

    print(
        "\nA severe estimate mismatch suggests that planner statistics may "
        "not describe the current data distribution accurately."
    )


# ---------------------------------------------------------------------------
# Lightweight cost model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CostDecision:
    strategy: str
    estimated_cost: float
    reason: str


def choose_scan_strategy(
    table_rows: int,
    estimated_matching_rows: int,
    index_startup_cost: float = 2.0,
    index_row_cost: float = 1.0,
    sequential_row_cost: float = 0.08,
) -> CostDecision:
    """
    Approximate the central planning trade-off between sequential and indexed
    access.

    This is intentionally not PostgreSQL's actual cost formula. It is a
    transparent teaching model showing why an optimizer considers both the
    fixed startup cost and the expected number of rows touched.
    """
    sequential_cost = table_rows * sequential_row_cost
    index_cost = index_startup_cost + estimated_matching_rows * index_row_cost

    if index_cost < sequential_cost:
        return CostDecision(
            "INDEX SCAN",
            index_cost,
            (
                f"Estimated {estimated_matching_rows:,} matching rows are "
                f"cheap enough for indexed access."
            ),
        )

    return CostDecision(
        "SEQUENTIAL SCAN",
        sequential_cost,
        (
            f"Estimated {estimated_matching_rows:,} matching rows make a "
            f"table scan cheaper in this simplified cost model."
        ),
    )


def demonstrate_cost_model() -> None:
    print("\n=== Simplified planner cost model ===")

    scenarios = [
        ("Highly selective", 1_000_000, 100),
        ("Moderately selective", 1_000_000, 10_000),
        ("Broad predicate", 1_000_000, 900_000),
    ]

    for name, rows, matches in scenarios:
        decision = choose_scan_strategy(rows, matches)
        print(
            f"{name}: {decision.strategy}, "
            f"estimated cost={decision.estimated_cost:,.2f}"
        )
        print(f"  {decision.reason}")


# ---------------------------------------------------------------------------
# Statistics and plan instability
# ---------------------------------------------------------------------------

@dataclass
class ColumnStatistics:
    distinct_values: int
    most_common_value_frequency: float
    estimated_rows: int


def estimate_equality_rows(
    stats: ColumnStatistics,
    value_is_most_common: bool,
) -> int:
    """
    Estimate rows for an equality predicate using deliberately simple
    statistics.

    Real PostgreSQL statistics are substantially richer. The point here is
    that a planner's decision is based on estimates, not on executing every
    possible plan first.
    """
    if value_is_most_common:
        return round(
            stats.estimated_rows * stats.most_common_value_frequency
        )

    return max(1, round(stats.estimated_rows / stats.distinct_values))


def demonstrate_statistics() -> None:
    print("\n=== Statistics influence planning ===")

    stats = ColumnStatistics(
        distinct_values=4,
        most_common_value_frequency=0.25,
        estimated_rows=100_000,
    )

    common_rows = estimate_equality_rows(stats, True)
    rare_rows = estimate_equality_rows(stats, False)

    print(f"Estimated rows for common value: {common_rows:,}")
    print(f"Estimated rows for non-common value: {rare_rows:,}")
    print(
        "If statistics are stale, the optimizer can choose an access path "
        "based on a substantially incorrect estimate."
    )


# ---------------------------------------------------------------------------
# Production-oriented diagnostics
# ---------------------------------------------------------------------------

def query_diagnostics(sql: str) -> list[str]:
    """
    Return practical diagnostics for a query string.

    This is intentionally heuristic. It does not replace EXPLAIN.
    """
    diagnostics = []
    normalized = " ".join(sql.lower().split())

    if "select *" in normalized:
        diagnostics.append(
            "Consider selecting only required columns to reduce row width and "
            "allow narrower or covering indexes to become useful."
        )

    if "order by" in normalized and "limit" not in normalized:
        diagnostics.append(
            "A large ORDER BY without LIMIT may require sorting many rows."
        )

    if " or " in normalized:
        diagnostics.append(
            "OR predicates can produce less predictable access paths; inspect "
            "the actual plan before rewriting."
        )

    if "function(" in normalized:
        diagnostics.append(
            "Check whether a function is being applied to an indexed column."
        )

    if "like '%" in normalized:
        diagnostics.append(
            "A leading wildcard in LIKE commonly prevents efficient B-tree "
            "prefix lookup."
        )

    if "join" in normalized and "on" not in normalized:
        diagnostics.append(
            "Verify that every join has an intentional join condition."
        )

    if not diagnostics:
        diagnostics.append(
            "No simple heuristic warning was detected. Use EXPLAIN and "
            "EXPLAIN ANALYZE for evidence."
        )

    return diagnostics


def demonstrate_diagnostics() -> None:
    sql = """
        SELECT *
        FROM orders
        WHERE sales_channel LIKE '%EB'
        ORDER BY total_amount DESC
    """

    print("\n=== Query diagnostics ===")
    print(sql.strip())

    for diagnostic in query_diagnostics(sql):
        print(f"- {diagnostic}")


# ---------------------------------------------------------------------------
# Main learning workflow
# ---------------------------------------------------------------------------

def main() -> None:
    print("QUERY OPTIMIZATION LABORATORY")
    print("=" * 80)
    print(
        "The demonstrations inspect plans, measure execution, and model "
        "planner decisions using realistic order data."
    )

    connection = create_database()

    try:
        demonstrate_sequential_scan(connection)
        create_basic_index(connection)
        demonstrate_index_scan(connection)
        demonstrate_selectivity(connection)
        demonstrate_sargability(connection)
        demonstrate_composite_index(connection)
        demonstrate_covering_index(connection)
        demonstrate_sorting_and_aggregation(connection)
        demonstrate_join_plan(connection)
        demonstrate_query_rewrites(connection)
        demonstrate_postgresql_plan_model()
        demonstrate_cost_model()
        demonstrate_statistics()
        demonstrate_diagnostics()

        print("\n=== Final diagnostic principle ===")
        print(
            "Do not optimize from intuition alone. Compare the query, "
            "the estimated plan, actual execution behavior, row estimates, "
            "indexes, and data distribution before changing the schema or SQL."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
