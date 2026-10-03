#!/usr/bin/env python3
"""
SQL JOINs: a self-contained executable study of relational joins.

This program models customers, orders, products, employees, and departments
with ordinary Python collections, then implements the behavior of:

- INNER JOIN
- LEFT JOIN
- RIGHT JOIN
- FULL OUTER JOIN
- CROSS JOIN
- SELF JOIN

The implementation intentionally exposes the matching logic instead of using
an SQL engine so that the relational behavior of each join is visible.

It also demonstrates:
- one-to-one and one-to-many relationships
- unmatched rows
- duplicate matches
- NULL-like missing values
- composite join keys
- filtering before versus after a join
- aggregation after a join
- validation
- join cardinality
- nested-loop and indexed join strategies
- common outer-join mistakes
- practical performance measurements
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Iterable, Sequence


NULL = None
Row = dict[str, Any]
Predicate = Callable[[Row, Row], bool]
KeyFunction = Callable[[Row], Any]


# ---------------------------------------------------------------------------
# Sample relational data
# ---------------------------------------------------------------------------

CUSTOMERS: list[Row] = [
    {"customer_id": 1, "name": "Asha", "city": "Lucknow"},
    {"customer_id": 2, "name": "Ravi", "city": "Delhi"},
    {"customer_id": 3, "name": "Meera", "city": "Mumbai"},
    {"customer_id": 4, "name": "Kabir", "city": "Pune"},
    {"customer_id": 5, "name": "Nisha", "city": "Jaipur"},
]

ORDERS: list[Row] = [
    {"order_id": 101, "customer_id": 1, "product_id": 501, "amount": 2400},
    {"order_id": 102, "customer_id": 1, "product_id": 502, "amount": 900},
    {"order_id": 103, "customer_id": 2, "product_id": 503, "amount": 1500},
    {"order_id": 104, "customer_id": 2, "product_id": 501, "amount": 3100},
    {"order_id": 105, "customer_id": 4, "product_id": 504, "amount": 700},
    {"order_id": 106, "customer_id": 9, "product_id": 501, "amount": 1200},
]

PRODUCTS: list[Row] = [
    {"product_id": 501, "product_name": "Laptop", "category": "Computers"},
    {"product_id": 502, "product_name": "Keyboard", "category": "Accessories"},
    {"product_id": 503, "product_name": "Monitor", "category": "Displays"},
    {"product_id": 504, "product_name": "Mouse", "category": "Accessories"},
    {"product_id": 505, "product_name": "Webcam", "category": "Accessories"},
]

DEPARTMENTS: list[Row] = [
    {"department_id": 10, "department_name": "Engineering"},
    {"department_id": 20, "department_name": "Finance"},
    {"department_id": 30, "department_name": "Operations"},
]

EMPLOYEES: list[Row] = [
    {"employee_id": 1, "employee_name": "Anika", "manager_id": None, "department_id": 10},
    {"employee_id": 2, "employee_name": "Bharat", "manager_id": 1, "department_id": 10},
    {"employee_id": 3, "employee_name": "Charu", "manager_id": 1, "department_id": 10},
    {"employee_id": 4, "employee_name": "Dev", "manager_id": 2, "department_id": 20},
    {"employee_id": 5, "employee_name": "Esha", "manager_id": 2, "department_id": 30},
    {"employee_id": 6, "employee_name": "Farhan", "manager_id": 99, "department_id": 30},
]


# ---------------------------------------------------------------------------
# Generic relational utilities
# ---------------------------------------------------------------------------

def prefixed(row: Row, prefix: str) -> Row:
    """Prefix columns so identically named columns remain distinguishable."""
    return {f"{prefix}.{key}": value for key, value in row.items()}


def merge_rows(left: Row | None, right: Row | None,
               left_prefix: str = "left",
               right_prefix: str = "right") -> Row:
    """
    Merge two rows into one result row.

    Missing outer-join sides are represented with None for every known column.
    This mirrors SQL NULL values produced by an outer join.
    """
    result: Row = {}

    if left is not None:
        result.update(prefixed(left, left_prefix))

    if right is not None:
        result.update(prefixed(right, right_prefix))

    return result


def null_columns(rows: Sequence[Row], prefix: str) -> Row:
    """Create the NULL side of an outer-join result."""
    if not rows:
        return {}
    return {f"{prefix}.{key}": NULL for key in rows[0]}


def print_rows(title: str, rows: Iterable[Row]) -> None:
    """Print a compact relational result."""
    rows = list(rows)
    print(f"\n{title}")
    print("-" * len(title))

    if not rows:
        print("(no rows)")
        return

    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)

    print(" | ".join(columns))
    print("-+-".join("-" * len(column) for column in columns))

    for row in rows:
        print(" | ".join(str(row.get(column, NULL)) for column in columns))


def validate_unique(rows: Sequence[Row], key: KeyFunction, table_name: str) -> None:
    """
    Validate a key expected to be unique.

    A SQL primary key or UNIQUE constraint prevents duplicate key values.
    This function demonstrates the application-side equivalent.
    """
    seen: set[Any] = set()

    for row in rows:
        value = key(row)
        if value in seen:
            raise ValueError(
                f"{table_name}: duplicate key detected for value {value!r}"
            )
        seen.add(value)


def validate_foreign_keys(
    child_rows: Sequence[Row],
    child_key: KeyFunction,
    parent_rows: Sequence[Row],
    parent_key: KeyFunction,
    relationship_name: str,
) -> list[Any]:
    """
    Return foreign-key values that have no corresponding parent.

    SQL databases normally enforce this with a FOREIGN KEY constraint.
    """
    parent_keys = {parent_key(row) for row in parent_rows}
    invalid = []

    for row in child_rows:
        value = child_key(row)
        if value not in parent_keys:
            invalid.append(value)

    if invalid:
        print(
            f"\nReferential-integrity warning for {relationship_name}: "
            f"unmatched values = {sorted(set(invalid))}"
        )

    return invalid


# ---------------------------------------------------------------------------
# INNER JOIN
# ---------------------------------------------------------------------------

def inner_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> list[Row]:
    """
    INNER JOIN returns only pairs for which the join keys match.

    The indexed implementation builds a lookup table for the right relation.
    If the right key is not unique, every matching right row is emitted.
    That is important because SQL joins operate on row combinations, not
    dictionary lookups that silently discard duplicates.
    """
    index: dict[Any, list[Row]] = defaultdict(list)

    for right in right_rows:
        index[right_key(right)].append(right)

    result: list[Row] = []

    for left in left_rows:
        matches = index.get(left_key(left), [])

        for right in matches:
            result.append(merge_rows(left, right))

    return result


# ---------------------------------------------------------------------------
# LEFT JOIN
# ---------------------------------------------------------------------------

def left_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> list[Row]:
    """
    LEFT JOIN preserves every row from the left relation.

    When a left row has no right-side match, right-side columns become NULL.
    """
    index: dict[Any, list[Row]] = defaultdict(list)

    for right in right_rows:
        index[right_key(right)].append(right)

    result: list[Row] = []

    for left in left_rows:
        matches = index.get(left_key(left), [])

        if matches:
            for right in matches:
                result.append(merge_rows(left, right))
        else:
            result.append(
                merge_rows(
                    left,
                    {key.removeprefix("right."): value for key, value
                     in null_columns(right_rows, "right").items()},
                )
            )

    return result


# ---------------------------------------------------------------------------
# RIGHT JOIN
# ---------------------------------------------------------------------------

def right_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> list[Row]:
    """
    RIGHT JOIN preserves every row from the right relation.

    It can be implemented by swapping the inputs of a LEFT JOIN, then
    restoring the original left/right output orientation.
    """
    swapped = left_join(
        right_rows,
        left_rows,
        right_key,
        left_key,
    )

    result: list[Row] = []

    for row in swapped:
        restored: Row = {}

        for key, value in row.items():
            if key.startswith("left."):
                restored[f"right.{key[5:]}"] = value
            elif key.startswith("right."):
                restored[f"left.{key[6:]}"] = value

        result.append(restored)

    return result


# ---------------------------------------------------------------------------
# FULL OUTER JOIN
# ---------------------------------------------------------------------------

def full_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> list[Row]:
    """
    FULL OUTER JOIN preserves unmatched rows from both relations.

    Matched rows are emitted once for every matching pair. A right-side row
    is tracked by its position rather than only by its key because multiple
    rows can legally share the same join key.
    """
    index: dict[Any, list[tuple[int, Row]]] = defaultdict(list)

    for right_index, right in enumerate(right_rows):
        index[right_key(right)].append((right_index, right))

    matched_right_indexes: set[int] = set()
    result: list[Row] = []

    for left in left_rows:
        matches = index.get(left_key(left), [])

        if matches:
            for right_index, right in matches:
                matched_right_indexes.add(right_index)
                result.append(merge_rows(left, right))
        else:
            result.append(
                merge_rows(
                    left,
                    {key.removeprefix("right."): value for key, value
                     in null_columns(right_rows, "right").items()},
                )
            )

    for right_index, right in enumerate(right_rows):
        if right_index not in matched_right_indexes:
            result.append(
                merge_rows(
                    {key.removeprefix("left."): value for key, value
                     in null_columns(left_rows, "left").items()},
                    right,
                )
            )

    return result


# ---------------------------------------------------------------------------
# CROSS JOIN
# ---------------------------------------------------------------------------

def cross_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
) -> list[Row]:
    """
    CROSS JOIN computes the Cartesian product.

    If the left relation has m rows and the right relation has n rows,
    the result contains m * n rows. No matching predicate is required.
    """
    return [
        merge_rows(left, right)
        for left in left_rows
        for right in right_rows
    ]


# ---------------------------------------------------------------------------
# SELF JOIN
# ---------------------------------------------------------------------------

def self_join(
    rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> list[Row]:
    """
    A self join joins a relation to itself.

    The two aliases are essential conceptually because the same table plays
    two different roles. Here employees are joined to employees so that an
    employee can be associated with their manager.
    """
    index: dict[Any, list[Row]] = defaultdict(list)

    for row in rows:
        index[right_key(row)].append(row)

    result: list[Row] = []

    for row in rows:
        matches = index.get(left_key(row), [])

        for manager in matches:
            result.append(
                merge_rows(row, manager, "employee", "manager")
            )

    return result


# ---------------------------------------------------------------------------
# A simpler nested-loop join for comparison
# ---------------------------------------------------------------------------

def nested_loop_inner_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> list[Row]:
    """
    Direct relational implementation.

    Every left row is compared with every right row. This has O(m*n)
    comparison complexity and is useful for teaching the fundamental join
    definition before introducing an index.
    """
    result: list[Row] = []

    for left in left_rows:
        for right in right_rows:
            if left_key(left) == right_key(right):
                result.append(merge_rows(left, right))

    return result


# ---------------------------------------------------------------------------
# Composite-key joins
# ---------------------------------------------------------------------------

def composite_key_join_demo() -> list[Row]:
    """
    Demonstrate a join where uniqueness depends on two columns.

    Real systems commonly use composite business keys such as
    (warehouse_id, product_id). A join on only one component can accidentally
    match records belonging to different entities.
    """
    inventory = [
        {"warehouse_id": "LKO", "product_id": 501, "quantity": 14},
        {"warehouse_id": "DEL", "product_id": 501, "quantity": 6},
        {"warehouse_id": "LKO", "product_id": 502, "quantity": 22},
    ]

    requests = [
        {"warehouse_id": "LKO", "product_id": 501, "request_id": "R1"},
        {"warehouse_id": "DEL", "product_id": 501, "request_id": "R2"},
        {"warehouse_id": "LKO", "product_id": 999, "request_id": "R3"},
    ]

    return left_join(
        requests,
        inventory,
        lambda row: (row["warehouse_id"], row["product_id"]),
        lambda row: (row["warehouse_id"], row["product_id"]),
    )


# ---------------------------------------------------------------------------
# Filter placement and outer joins
# ---------------------------------------------------------------------------

def filter_after_left_join(rows: Sequence[Row]) -> list[Row]:
    """
    Filtering a nullable right-side value after a LEFT JOIN can remove the
    NULL-extended rows and therefore change the effective behavior toward an
    INNER JOIN.

    This function deliberately demonstrates that behavior.
    """
    return [
        row for row in rows
        if row["right.category"] == "Accessories"
    ]


def left_join_with_right_condition(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
    right_condition: Predicate,
) -> list[Row]:
    """
    Apply a right-side condition during matching.

    Unmatched left rows are still preserved because the condition determines
    which right rows are eligible, rather than filtering the completed
    outer-join result.
    """
    eligible_right = [
        row for row in right_rows
        if right_condition({}, row)
    ]

    return left_join(left_rows, eligible_right, left_key, right_key)


# ---------------------------------------------------------------------------
# Aggregation over joined data
# ---------------------------------------------------------------------------

def customer_order_totals() -> list[Row]:
    """
    LEFT JOIN customers to orders, then aggregate order amounts.

    LEFT JOIN is important because customers without orders must remain in
    the result with a total of zero.
    """
    joined = left_join(
        CUSTOMERS,
        ORDERS,
        lambda row: row["customer_id"],
        lambda row: row["customer_id"],
    )

    totals: dict[int, float] = {
        customer["customer_id"]: 0
        for customer in CUSTOMERS
    }

    names: dict[int, str] = {
        customer["customer_id"]: customer["name"]
        for customer in CUSTOMERS
    }

    for row in joined:
        customer_id = row["left.customer_id"]
        amount = row["right.amount"]

        if amount is not None:
            totals[customer_id] += amount

    return [
        {
            "customer_id": customer_id,
            "customer_name": names[customer_id],
            "total_order_value": amount,
        }
        for customer_id, amount in totals.items()
    ]


# ---------------------------------------------------------------------------
# Join cardinality analysis
# ---------------------------------------------------------------------------

def cardinality_report(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: KeyFunction,
    right_key: KeyFunction,
) -> dict[str, Any]:
    """
    Explain the multiplicity of a join.

    A one-to-many relationship can expand rows. If one left key occurs twice
    and the same right key occurs three times, that key contributes 2*3=6
    output rows.
    """
    left_counts: dict[Any, int] = defaultdict(int)
    right_counts: dict[Any, int] = defaultdict(int)

    for row in left_rows:
        left_counts[left_key(row)] += 1

    for row in right_rows:
        right_counts[right_key(row)] += 1

    matched_pairs = sum(
        left_counts[key] * right_counts[key]
        for key in left_counts.keys() & right_counts.keys()
    )

    return {
        "left_rows": len(left_rows),
        "right_rows": len(right_rows),
        "matching_keys": len(left_counts.keys() & right_counts.keys()),
        "inner_join_rows": matched_pairs,
        "left_only_keys": len(left_counts.keys() - right_counts.keys()),
        "right_only_keys": len(right_counts.keys() - left_counts.keys()),
    }


# ---------------------------------------------------------------------------
# Performance comparison
# ---------------------------------------------------------------------------

def build_performance_data(size: int = 4000) -> tuple[list[Row], list[Row]]:
    """Build deterministic data large enough to expose indexing differences."""
    left = [
        {"id": index, "value": index * 2}
        for index in range(size)
    ]

    right = [
        {"id": index, "description": f"record-{index}"}
        for index in range(0, size, 2)
    ]

    return left, right


def benchmark_join_strategies() -> None:
    """
    Compare nested-loop matching with indexed matching.

    The indexed version generally approaches O(m+n) for hashable keys, while
    the nested-loop implementation performs O(m*n) comparisons. Actual SQL
    engines may choose hash joins, merge joins, nested-loop joins, indexes,
    statistics-driven plans, or combinations of these strategies.
    """
    left, right = build_performance_data()

    start = perf_counter()
    nested_result = nested_loop_inner_join(
        left,
        right,
        lambda row: row["id"],
        lambda row: row["id"],
    )
    nested_time = perf_counter() - start

    start = perf_counter()
    indexed_result = inner_join(
        left,
        right,
        lambda row: row["id"],
        lambda row: row["id"],
    )
    indexed_time = perf_counter() - start

    print("\nJoin performance experiment")
    print("---------------------------")
    print(f"Left rows: {len(left)}")
    print(f"Right rows: {len(right)}")
    print(f"Nested-loop output rows: {len(nested_result)}")
    print(f"Indexed output rows: {len(indexed_result)}")
    print(f"Nested-loop time: {nested_time:.6f} seconds")
    print(f"Indexed time:     {indexed_time:.6f} seconds")


# ---------------------------------------------------------------------------
# Practical business workflow
# ---------------------------------------------------------------------------

def customer_product_report() -> list[Row]:
    """
    Build a three-relation report:

    customers -> orders -> products

    The first join associates orders with customers. The second associates
    orders with products. Orders containing an unknown customer remain visible
    because the first relationship is evaluated with a RIGHT JOIN from the
    order perspective.
    """
    customer_order = left_join(
        CUSTOMERS,
        ORDERS,
        lambda row: row["customer_id"],
        lambda row: row["customer_id"],
    )

    valid_customer_orders = [
        row
        for row in customer_order
        if row["right.order_id"] is not None
    ]

    result: list[Row] = []

    for row in valid_customer_orders:
        order = {
            "order_id": row["right.order_id"],
            "customer_id": row["right.customer_id"],
            "product_id": row["right.product_id"],
            "amount": row["right.amount"],
        }

        product_matches = inner_join(
            [order],
            PRODUCTS,
            lambda item: item["product_id"],
            lambda item: item["product_id"],
        )

        for product_row in product_matches:
            result.append(
                {
                    "customer": row["left.name"],
                    "order_id": product_row["left.order_id"],
                    "product": product_row["right.product_name"],
                    "category": product_row["right.category"],
                    "amount": product_row["left.amount"],
                }
            )

    return result


# ---------------------------------------------------------------------------
# Validation and failure cases
# ---------------------------------------------------------------------------

def demonstrate_validation() -> None:
    """Show constraints that make joins reliable in production systems."""
    print("\nValidation")
    print("----------")

    validate_unique(
        CUSTOMERS,
        lambda row: row["customer_id"],
        "customers.customer_id",
    )

    validate_unique(
        PRODUCTS,
        lambda row: row["product_id"],
        "products.product_id",
    )

    invalid = validate_foreign_keys(
        ORDERS,
        lambda row: row["customer_id"],
        CUSTOMERS,
        lambda row: row["customer_id"],
        "orders.customer_id -> customers.customer_id",
    )

    if invalid:
        print(
            "The sample intentionally contains an order for customer_id=9. "
            "An INNER JOIN hides this unmatched order; a LEFT/FULL join can "
            "expose it for data-quality investigation."
        )


def demonstrate_null_semantics() -> None:
    """
    Show why SQL NULL requires special reasoning.

    Python None is used here as the closest representation. In SQL,
    NULL = NULL is not TRUE; it evaluates to UNKNOWN. A join condition using
    ordinary equality therefore does not match two NULL values.
    """
    rows_a = [
        {"id": 1, "value": "A"},
        {"id": None, "value": "missing-key"},
    ]

    rows_b = [
        {"id": 1, "description": "matched"},
        {"id": None, "description": "also-missing"},
    ]

    equality_join = inner_join(
        rows_a,
        rows_b,
        lambda row: row["id"],
        lambda row: row["id"],
    )

    print_rows(
        "Python equality model: None can compare equal",
        equality_join,
    )

    print(
        "\nImportant SQL distinction: SQL's NULL is not an ordinary value. "
        "A real SQL join must account for three-valued logic when nullable "
        "join keys are involved."
    )


# ---------------------------------------------------------------------------
# Main demonstration
# ---------------------------------------------------------------------------

def main() -> None:
    print("SQL JOIN laboratory")
    print("===================")

    print_rows(
        "INNER JOIN: customers with matching orders",
        inner_join(
            CUSTOMERS,
            ORDERS,
            lambda row: row["customer_id"],
            lambda row: row["customer_id"],
        ),
    )

    print_rows(
        "LEFT JOIN: every customer, including customers without orders",
        left_join(
            CUSTOMERS,
            ORDERS,
            lambda row: row["customer_id"],
            lambda row: row["customer_id"],
        ),
    )

    print_rows(
        "RIGHT JOIN: every order, including orders with unknown customers",
        right_join(
            CUSTOMERS,
            ORDERS,
            lambda row: row["customer_id"],
            lambda row: row["customer_id"],
        ),
    )

    print_rows(
        "FULL OUTER JOIN: all customers and all orders",
        full_join(
            CUSTOMERS,
            ORDERS,
            lambda row: row["customer_id"],
            lambda row: row["customer_id"],
        ),
    )

    print_rows(
        "CROSS JOIN: customers x departments",
        cross_join(CUSTOMERS[:2], DEPARTMENTS),
    )

    print_rows(
        "SELF JOIN: employees associated with their managers",
        self_join(
            EMPLOYEES,
            lambda row: row["manager_id"],
            lambda row: row["employee_id"],
        ),
    )

    print_rows(
        "Composite-key LEFT JOIN",
        composite_key_join_demo(),
    )

    customer_orders = left_join(
        CUSTOMERS,
        ORDERS,
        lambda row: row["customer_id"],
        lambda row: row["customer_id"],
    )

    print_rows(
        "LEFT JOIN followed by a right-side filter",
        filter_after_left_join(customer_orders),
    )

    print_rows(
        "LEFT JOIN with condition applied to eligible right rows",
        left_join_with_right_condition(
            CUSTOMERS,
            ORDERS,
            lambda row: row.get("customer_id"),
            lambda row: row.get("customer_id"),
            lambda _, right: right["amount"] >= 1500,
        ),
    )

    print_rows(
        "Customer order totals",
        customer_order_totals(),
    )

    print_rows(
        "Customer -> order -> product report",
        customer_product_report(),
    )

    print("\nJoin cardinality")
    print("----------------")
    report = cardinality_report(
        CUSTOMERS,
        ORDERS,
        lambda row: row["customer_id"],
        lambda row: row["customer_id"],
    )

    for key, value in report.items():
        print(f"{key}: {value}")

    demonstrate_validation()
    demonstrate_null_semantics()
    benchmark_join_strategies()

    print("\nPractical observations")
    print("----------------------")
    print(
        "INNER JOIN is appropriate when unmatched rows should disappear."
    )
    print(
        "LEFT JOIN is appropriate when the left relation defines the complete "
        "population that must remain visible."
    )
    print(
        "RIGHT JOIN preserves the right relation and is often rewritten as "
        "a LEFT JOIN by reversing table order."
    )
    print(
        "FULL OUTER JOIN is useful for reconciliation because it exposes "
        "records appearing on only one side."
    )
    print(
        "CROSS JOIN is intentionally combinatorial and should be used only "
        "when every left/right combination has meaning."
    )
    print(
        "SELF JOIN models relationships inside one relation, such as "
        "employee-to-manager hierarchies."
    )


if __name__ == "__main__":
    main()
