"""
Database Fundamentals: tables, rows, columns, primary keys, and relationships.

This self-contained program uses Python's standard-library sqlite3 module to
build and inspect a small project-management database. It progresses from
basic relational concepts to constraints, relationships, joins, transactions,
validation, indexing, and integrity checks.

Run:
    python database_fundamentals.py
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator


DB_PATH = Path("database_fundamentals_demo.db")


@dataclass(frozen=True)
class Project:
    project_id: int
    name: str
    owner: str


@dataclass(frozen=True)
class Task:
    task_id: int
    project_id: int
    title: str
    status: str


def print_heading(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)


@contextmanager
def database_connection(path: str | Path = ":memory:") -> Iterator[sqlite3.Connection]:
    """
    Open a database connection and make foreign-key enforcement explicit.

    SQLite does not enable foreign-key enforcement automatically for every
    connection, so PRAGMA foreign_keys = ON is important when relationships
    are part of the design.
    """
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_schema(connection: sqlite3.Connection) -> None:
    """
    Create related tables.

    projects is the parent table. tasks is the child table and references
    projects(project_id) through a foreign key.
    """
    connection.executescript(
        """
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS projects;

        CREATE TABLE projects (
            project_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL
        );

        CREATE TABLE tasks (
            task_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in_progress', 'done')),
            due_date TEXT,
            FOREIGN KEY (project_id)
                REFERENCES projects(project_id)
                ON DELETE RESTRICT
                ON UPDATE CASCADE
        );
        """
    )


def show_table_structure(connection: sqlite3.Connection, table_name: str) -> None:
    """Inspect columns, types, nullability, and primary-key metadata."""
    print_heading(f"Table structure: {table_name}")

    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    for row in rows:
        print(
            f"column={row['name']!r:<15} "
            f"type={row['type']!r:<10} "
            f"not_null={bool(row['notnull'])!s:<5} "
            f"primary_key={bool(row['pk'])!s}"
        )


def insert_sample_data(connection: sqlite3.Connection) -> None:
    """Insert realistic rows while preserving the declared relationships."""
    projects = [
        ("Market Analytics", "Atul"),
        ("Asset Tracking", "Priya"),
        ("Research Portal", "Rahul"),
    ]

    connection.executemany(
        "INSERT INTO projects (name, owner) VALUES (?, ?)",
        projects,
    )

    tasks = [
        (1, "Design database schema", "done", "2026-10-03"),
        (1, "Build portfolio API", "in_progress", "2026-10-08"),
        (1, "Add risk calculations", "todo", "2026-10-12"),
        (2, "Register tracked assets", "done", "2026-10-04"),
        (2, "Implement movement history", "in_progress", "2026-10-11"),
        (3, "Import research records", "todo", "2026-10-15"),
    ]

    connection.executemany(
        """
        INSERT INTO tasks (project_id, title, status, due_date)
        VALUES (?, ?, ?, ?)
        """,
        tasks,
    )


def display_rows(connection: sqlite3.Connection, table_name: str) -> None:
    """Demonstrate that a table is a collection of rows made of named columns."""
    print_heading(f"Rows in {table_name}")

    rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()

    if not rows:
        print("(no rows)")
        return

    column_names = rows[0].keys()
    print(" | ".join(column_names))
    print("-" * 72)

    for row in rows:
        print(" | ".join(str(row[column]) for column in column_names))


def demonstrate_primary_key(connection: sqlite3.Connection) -> None:
    """
    A primary key identifies a row.

    Attempting to insert another project with the same project_id violates
    the uniqueness requirement of the primary key.
    """
    print_heading("Primary-key enforcement")

    try:
        connection.execute(
            """
            INSERT INTO projects (project_id, name, owner)
            VALUES (?, ?, ?)
            """,
            (1, "Duplicate Project", "Someone"),
        )
    except sqlite3.IntegrityError as error:
        print("Duplicate primary key rejected:", error)

    project = connection.execute(
        "SELECT project_id, name, owner FROM projects WHERE project_id = ?",
        (1,),
    ).fetchone()

    print("Existing row remains:", dict(project))


def demonstrate_foreign_key(connection: sqlite3.Connection) -> None:
    """
    A foreign key connects a child row to an existing parent row.

    project_id=999 does not identify an existing project, so the database
    rejects the task instead of allowing a dangling relationship.
    """
    print_heading("Foreign-key enforcement")

    try:
        connection.execute(
            """
            INSERT INTO tasks (project_id, title, status)
            VALUES (?, ?, ?)
            """,
            (999, "Task with invalid relationship", "todo"),
        )
    except sqlite3.IntegrityError as error:
        print("Invalid foreign key rejected:", error)


def demonstrate_one_to_many(connection: sqlite3.Connection) -> None:
    """
    One project can own many tasks.

    The relationship is represented by storing the parent's primary key in
    each child row. No project data has to be duplicated in every task row.
    """
    print_heading("One-to-many relationship")

    rows = connection.execute(
        """
        SELECT
            p.project_id,
            p.name AS project_name,
            t.task_id,
            t.title AS task_title,
            t.status
        FROM projects AS p
        LEFT JOIN tasks AS t
            ON t.project_id = p.project_id
        ORDER BY p.project_id, t.task_id
        """
    ).fetchall()

    for row in rows:
        print(
            f"project={row['project_id']} {row['project_name']!r} | "
            f"task={row['task_id']} {row['task_title']!r} | "
            f"status={row['status']}"
        )


def demonstrate_many_to_many(connection: sqlite3.Connection) -> None:
    """
    Many-to-many relationships require an associative table.

    Here, team members can work on many projects and each project can have
    many members. The membership table stores the two foreign keys.
    """
    print_heading("Many-to-many relationship")

    connection.executescript(
        """
        CREATE TABLE team_members (
            member_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE project_members (
            project_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (project_id, member_id),
            FOREIGN KEY (project_id)
                REFERENCES projects(project_id)
                ON DELETE CASCADE,
            FOREIGN KEY (member_id)
                REFERENCES team_members(member_id)
                ON DELETE CASCADE
        );
        """
    )

    connection.executemany(
        "INSERT INTO team_members (name) VALUES (?)",
        [("Atul",), ("Priya",), ("Rahul",)],
    )

    memberships = [
        (1, 1, "Product Owner"),
        (1, 2, "Data Engineer"),
        (2, 1, "System Designer"),
        (2, 2, "Operations"),
        (3, 1, "Research Lead"),
        (3, 3, "Analyst"),
    ]

    connection.executemany(
        """
        INSERT INTO project_members (project_id, member_id, role)
        VALUES (?, ?, ?)
        """,
        memberships,
    )

    rows = connection.execute(
        """
        SELECT
            p.name AS project,
            m.name AS member,
            pm.role
        FROM project_members AS pm
        JOIN projects AS p ON p.project_id = pm.project_id
        JOIN team_members AS m ON m.member_id = pm.member_id
        ORDER BY p.name, m.name
        """
    ).fetchall()

    for row in rows:
        print(
            f"{row['project']:<20} "
            f"{row['member']:<10} "
            f"role={row['role']}"
        )


def demonstrate_constraints(connection: sqlite3.Connection) -> None:
    """Show NOT NULL, UNIQUE, and CHECK constraints as database rules."""
    print_heading("Column constraints")

    invalid_operations = [
        (
            "NULL project name",
            """
            INSERT INTO projects (name, owner)
            VALUES (NULL, 'Atul')
            """,
            (),
        ),
        (
            "duplicate project name",
            """
            INSERT INTO projects (name, owner)
            VALUES (?, ?)
            """,
            ("Market Analytics", "New Owner"),
        ),
        (
            "invalid task status",
            """
            INSERT INTO tasks (project_id, title, status)
            VALUES (?, ?, ?)
            """,
            (1, "Broken status", "blocked_forever"),
        ),
    ]

    for description, sql, parameters in invalid_operations:
        try:
            connection.execute(sql, parameters)
        except sqlite3.IntegrityError as error:
            print(f"{description}: rejected -> {error}")


def demonstrate_updates_and_deletes(connection: sqlite3.Connection) -> None:
    """
    Updates change existing rows while preserving their identity.

    Deleting a parent project is restricted because tasks still reference it.
    This prevents accidental orphan records.
    """
    print_heading("Updates and relationship-aware deletes")

    connection.execute(
        """
        UPDATE tasks
        SET status = ?
        WHERE task_id = ?
        """,
        ("done", 2),
    )

    updated = connection.execute(
        "SELECT task_id, title, status FROM tasks WHERE task_id = 2"
    ).fetchone()

    print("Updated task:", dict(updated))

    try:
        connection.execute(
            "DELETE FROM projects WHERE project_id = ?",
            (1,),
        )
    except sqlite3.IntegrityError as error:
        print("Parent deletion rejected while children exist:", error)


def demonstrate_transaction(connection: sqlite3.Connection) -> None:
    """
    Transactions make multiple changes atomic.

    If a later operation fails, the explicit transaction is rolled back so
    the earlier successful operation is not left partially committed.
    """
    print_heading("Transaction and rollback")

    try:
        with connection:
            connection.execute(
                """
                INSERT INTO projects (name, owner)
                VALUES (?, ?)
                """,
                ("Temporary Migration Project", "Migration Service"),
            )

            connection.execute(
                """
                INSERT INTO tasks (project_id, title, status)
                VALUES (?, ?, ?)
                """,
                (9999, "This should fail", "todo"),
            )
    except sqlite3.IntegrityError as error:
        print("Transaction rolled back:", error)

    count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM projects
        WHERE name = 'Temporary Migration Project'
        """
    ).fetchone()["count"]

    print("Temporary project rows after rollback:", count)


def demonstrate_indexes_and_query_plan(connection: sqlite3.Connection) -> None:
    """
    An index can reduce lookup work for frequently filtered columns.

    Indexes consume storage and add write overhead, so they should support
    actual query patterns rather than being added indiscriminately.
    """
    print_heading("Indexing and query planning")

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_project_status
        ON tasks(project_id, status)
        """
    )

    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT task_id, title
        FROM tasks
        WHERE project_id = ? AND status = ?
        """,
        (1, "done"),
    ).fetchall()

    for row in plan:
        print("Query plan:", row["detail"])


def demonstrate_aggregation(connection: sqlite3.Connection) -> None:
    """Aggregate related rows to produce project-level operational metrics."""
    print_heading("Aggregating related rows")

    rows = connection.execute(
        """
        SELECT
            p.name,
            COUNT(t.task_id) AS task_count,
            SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
        FROM projects AS p
        LEFT JOIN tasks AS t
            ON t.project_id = p.project_id
        GROUP BY p.project_id, p.name
        ORDER BY p.project_id
        """
    ).fetchall()

    for row in rows:
        total = row["task_count"]
        done = row["done_count"]
        completion = (done / total * 100) if total else 0.0

        print(
            f"{row['name']}: {total} tasks, "
            f"{done} done, completion={completion:.1f}%"
        )


def demonstrate_null_and_missing_relationships(connection: sqlite3.Connection) -> None:
    """
    LEFT JOIN retains parent rows even when they have no matching child rows.

    This is different from an INNER JOIN, which returns only rows having a
    matching relationship on both sides.
    """
    print_heading("INNER JOIN versus LEFT JOIN")

    inner_rows = connection.execute(
        """
        SELECT p.name
        FROM projects AS p
        JOIN tasks AS t ON t.project_id = p.project_id
        GROUP BY p.project_id, p.name
        """
    ).fetchall()

    left_rows = connection.execute(
        """
        SELECT p.name, COUNT(t.task_id) AS task_count
        FROM projects AS p
        LEFT JOIN tasks AS t ON t.project_id = p.project_id
        GROUP BY p.project_id, p.name
        """
    ).fetchall()

    print("Projects appearing through INNER JOIN:")
    for row in inner_rows:
        print(" ", row["name"])

    print("Projects retained by LEFT JOIN:")
    for row in left_rows:
        print(" ", row["name"], "tasks=", row["task_count"])


def demonstrate_application_validation(connection: sqlite3.Connection) -> None:
    """
    Application validation provides clearer feedback before SQL execution.

    Database constraints remain necessary because application validation can
    be bypassed by another client, migration, script, or concurrent process.
    """
    print_heading("Application-level validation")

    allowed_statuses = {"todo", "in_progress", "done"}

    def create_task(project_id: int, title: str, status: str) -> int:
        if not isinstance(project_id, int) or project_id <= 0:
            raise ValueError("project_id must be a positive integer")

        if not title.strip():
            raise ValueError("title cannot be empty")

        if status not in allowed_statuses:
            raise ValueError(f"unsupported status: {status}")

        project_exists = connection.execute(
            "SELECT 1 FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()

        if project_exists is None:
            raise ValueError("project_id does not identify an existing project")

        cursor = connection.execute(
            """
            INSERT INTO tasks (project_id, title, status)
            VALUES (?, ?, ?)
            """,
            (project_id, title.strip(), status),
        )
        return int(cursor.lastrowid)

    try:
        task_id = create_task(3, "Validate imported research data", "todo")
        print("Validated task created with ID:", task_id)
    except (ValueError, sqlite3.IntegrityError) as error:
        print("Task creation failed:", error)


def demonstrate_sql_injection_safe_query(connection: sqlite3.Connection) -> None:
    """
    Parameterized queries keep user input separate from SQL structure.

    String concatenation is avoided even in a simple search operation.
    """
    print_heading("Safe parameterized querying")

    user_supplied_search = "Market' OR 1=1 --"

    rows = connection.execute(
        """
        SELECT project_id, name
        FROM projects
        WHERE name LIKE ?
        """,
        (f"%{user_supplied_search}%",),
    ).fetchall()

    print("Search matched rows:", [dict(row) for row in rows])


def demonstrate_database_metadata(connection: sqlite3.Connection) -> None:
    """Inspect SQLite's catalog to connect physical storage to logical tables."""
    print_heading("Database metadata")

    objects = connection.execute(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'index')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()

    for row in objects:
        print(f"{row['type']:<6} {row['name']}")


def demonstrate_dataclasses(connection: sqlite3.Connection) -> None:
    """Map database rows into typed Python objects for application code."""
    print_heading("Mapping relational rows to Python objects")

    project_rows = connection.execute(
        """
        SELECT project_id, name, owner
        FROM projects
        ORDER BY project_id
        """
    ).fetchall()

    projects = [
        Project(
            project_id=row["project_id"],
            name=row["name"],
            owner=row["owner"],
        )
        for row in project_rows
    ]

    task_rows = connection.execute(
        """
        SELECT task_id, project_id, title, status
        FROM tasks
        ORDER BY task_id
        """
    ).fetchall()

    tasks = [
        Task(
            task_id=row["task_id"],
            project_id=row["project_id"],
            title=row["title"],
            status=row["status"],
        )
        for row in task_rows
    ]

    print("Project objects:")
    for project in projects:
        print(" ", project)

    print("Task objects:")
    for task in tasks:
        print(" ", task)


def demonstrate_integrity_check(connection: sqlite3.Connection) -> None:
    """Ask the database engine to check its internal structural integrity."""
    print_heading("Database integrity check")

    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    print("integrity_check:", result)


def demonstrate_export(connection: sqlite3.Connection) -> None:
    """Export a relationship-aware report without introducing external packages."""
    print_heading("CSV-style report generation")

    output_path = Path("project_task_report.csv")

    rows = connection.execute(
        """
        SELECT
            p.project_id,
            p.name AS project,
            p.owner,
            t.task_id,
            t.title,
            t.status,
            t.due_date
        FROM projects AS p
        LEFT JOIN tasks AS t
            ON t.project_id = p.project_id
        ORDER BY p.project_id, t.task_id
        """
    ).fetchall()

    import csv

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["project_id", "project", "owner", "task_id", "title", "status", "due_date"]
        )

        for row in rows:
            writer.writerow(
                [
                    row["project_id"],
                    row["project"],
                    row["owner"],
                    row["task_id"],
                    row["title"],
                    row["status"],
                    row["due_date"],
                ]
            )

    print(f"Report written to {output_path.resolve()}")


def run() -> None:
    print_heading("Database Fundamentals Demonstration")
    print("Concepts: tables, rows, columns, primary keys, and relationships")
    print("Database engine: SQLite through Python's standard library")

    with database_connection() as connection:
        create_schema(connection)
        insert_sample_data(connection)

        show_table_structure(connection, "projects")
        show_table_structure(connection, "tasks")
        display_rows(connection, "projects")
        display_rows(connection, "tasks")

        demonstrate_primary_key(connection)
        demonstrate_foreign_key(connection)
        demonstrate_one_to_many(connection)
        demonstrate_many_to_many(connection)
        demonstrate_constraints(connection)
        demonstrate_updates_and_deletes(connection)
        demonstrate_transaction(connection)
        demonstrate_indexes_and_query_plan(connection)
        demonstrate_aggregation(connection)
        demonstrate_null_and_missing_relationships(connection)
        demonstrate_application_validation(connection)
        demonstrate_sql_injection_safe_query(connection)
        demonstrate_database_metadata(connection)
        demonstrate_dataclasses(connection)
        demonstrate_integrity_check(connection)
        demonstrate_export(connection)

    print_heading("Demonstration complete")


if __name__ == "__main__":
    run()
