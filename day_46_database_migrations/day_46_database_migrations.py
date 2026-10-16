from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


MigrationFunction = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up: MigrationFunction
    down: MigrationFunction


class MigrationError(RuntimeError):
    """Raised when a migration cannot be safely applied or reverted."""


class MigrationRunner:
    """
    Small migration engine backed by SQLite.

    The engine keeps migration history in the database itself. A migration is
    considered applied only after its SQL work and history-record insertion
    succeed in the same transaction.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._ensure_history_table()

    def _ensure_history_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    @staticmethod
    def _checksum(migration: Migration) -> str:
        source = (
            f"{migration.version}:{migration.name}:"
            f"{migration.up.__module__}.{migration.up.__qualname__}"
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def applied_versions(self) -> list[int]:
        rows = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        return [row["version"] for row in rows]

    def history(self) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT version, name, checksum, applied_at
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def validate_history(self, migrations: Iterable[Migration]) -> None:
        definitions = {migration.version: migration for migration in migrations}

        for row in self.connection.execute(
            "SELECT version, name, checksum FROM schema_migrations"
        ):
            migration = definitions.get(row["version"])
            if migration is None:
                raise MigrationError(
                    f"Database contains unknown migration {row['version']}."
                )

            expected_checksum = self._checksum(migration)
            if row["checksum"] != expected_checksum:
                raise MigrationError(
                    f"Migration {row['version']} was modified after application."
                )

            if row["name"] != migration.name:
                raise MigrationError(
                    f"Migration {row['version']} has a different name."
                )

    def migrate(self, migrations: Iterable[Migration], target: int | None = None) -> None:
        ordered = sorted(migrations, key=lambda item: item.version)
        self.validate_history(ordered)

        applied = set(self.applied_versions())
        pending = [
            migration
            for migration in ordered
            if migration.version not in applied
            and (target is None or migration.version <= target)
        ]

        for migration in pending:
            self._apply_one(migration)

    def _apply_one(self, migration: Migration) -> None:
        if self.connection.in_transaction:
            raise MigrationError("A migration cannot begin while another transaction is active.")

        try:
            self.connection.execute("BEGIN")
            migration.up(self.connection)
            self.connection.execute(
                """
                INSERT INTO schema_migrations
                    (version, name, checksum, applied_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    self._checksum(migration),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.connection.commit()
            print(f"Applied migration {migration.version}: {migration.name}")
        except Exception as exc:
            self.connection.rollback()
            raise MigrationError(
                f"Migration {migration.version} failed and was rolled back."
            ) from exc

    def rollback_last(self, migrations: Iterable[Migration]) -> None:
        ordered = {migration.version: migration for migration in migrations}
        history = self.history()

        if not history:
            raise MigrationError("No applied migration exists to roll back.")

        latest = history[-1]
        migration = ordered.get(latest["version"])

        if migration is None:
            raise MigrationError(
                f"Rollback definition for migration {latest['version']} is missing."
            )

        self.validate_history(ordered.values())

        try:
            self.connection.execute("BEGIN")
            migration.down(self.connection)
            self.connection.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,),
            )
            self.connection.commit()
            print(f"Rolled back migration {migration.version}: {migration.name}")
        except Exception as exc:
            self.connection.rollback()
            raise MigrationError(
                f"Rollback of migration {migration.version} failed."
            ) from exc


def migration_001_create_customers_up(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def migration_001_create_customers_down(db: sqlite3.Connection) -> None:
    db.execute("DROP TABLE customers")


def migration_002_add_status_up(db: sqlite3.Connection) -> None:
    db.execute(
        """
        ALTER TABLE customers
        ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
        """
    )


def migration_002_add_status_down(db: sqlite3.Connection) -> None:
    # SQLite cannot directly DROP COLUMN on older versions. Modern SQLite
    # supports it, so the migration explicitly requires that capability.
    db.execute("ALTER TABLE customers DROP COLUMN status")


def migration_003_create_orders_up(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
            state TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX idx_orders_customer_id
        ON orders(customer_id)
        """
    )


def migration_003_create_orders_down(db: sqlite3.Connection) -> None:
    db.execute("DROP INDEX IF EXISTS idx_orders_customer_id")
    db.execute("DROP TABLE orders")


def migration_004_normalize_customer_names_up(db: sqlite3.Connection) -> None:
    """
    A data migration: normalize existing names before adding a stricter
    application convention. The operation is deliberately idempotent.
    """
    rows = db.execute("SELECT id, full_name FROM customers").fetchall()
    for row in rows:
        normalized = " ".join(row[1].strip().split())
        db.execute(
            "UPDATE customers SET full_name = ? WHERE id = ?",
            (normalized, row[0]),
        )


def migration_004_normalize_customer_names_down(db: sqlite3.Connection) -> None:
    # Data normalization is intentionally not reversed because the original
    # whitespace cannot be reconstructed from normalized data.
    pass


def migration_005_add_customer_external_id_up(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE customers ADD COLUMN external_id TEXT")
    db.execute(
        """
        CREATE UNIQUE INDEX ux_customers_external_id
        ON customers(external_id)
        WHERE external_id IS NOT NULL
        """
    )


def migration_005_add_customer_external_id_down(db: sqlite3.Connection) -> None:
    db.execute("DROP INDEX IF EXISTS ux_customers_external_id")
    db.execute("ALTER TABLE customers DROP COLUMN external_id")


MIGRATIONS = [
    Migration(
        1,
        "create_customers",
        migration_001_create_customers_up,
        migration_001_create_customers_down,
    ),
    Migration(
        2,
        "add_customer_status",
        migration_002_add_status_up,
        migration_002_add_status_down,
    ),
    Migration(
        3,
        "create_orders",
        migration_003_create_orders_up,
        migration_003_create_orders_down,
    ),
    Migration(
        4,
        "normalize_customer_names",
        migration_004_normalize_customer_names_up,
        migration_004_normalize_customer_names_down,
    ),
    Migration(
        5,
        "add_customer_external_id",
        migration_005_add_customer_external_id_up,
        migration_005_add_customer_external_id_down,
    ),
]


def seed_business_data(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT INTO customers (id, email, full_name)
        VALUES (?, ?, ?)
        """,
        (1, "ada@example.com", "  Ada   Lovelace  "),
    )
    db.execute(
        """
        INSERT INTO customers (id, email, full_name)
        VALUES (?, ?, ?)
        """,
        (2, "grace@example.com", "Grace Hopper"),
    )
    db.execute(
        """
        INSERT INTO orders
            (id, customer_id, amount_cents, state, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1001, 1, 12999, "paid", "2026-10-16T08:00:00+00:00"),
    )
    db.commit()


def print_schema(db: sqlite3.Connection) -> None:
    print("\nCurrent schema:")
    tables = db.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    for table in tables:
        print(f"\n[{table['name']}]")
        columns = db.execute(
            f"PRAGMA table_info({table['name']})"
        ).fetchall()
        for column in columns:
            print(
                f"  {column['name']} {column['type']}"
                f" NOT NULL={bool(column['notnull'])}"
                f" DEFAULT={column['dflt_value']}"
            )


def demonstrate_failed_migration(db: sqlite3.Connection) -> None:
    """
    A failed migration must leave both schema and migration history unchanged.
    """
    def broken_up(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE migration_failure_demo (
                id INTEGER PRIMARY KEY
            )
            """
        )
        raise RuntimeError("Simulated deployment failure")

    def broken_down(connection: sqlite3.Connection) -> None:
        connection.execute("DROP TABLE migration_failure_demo")

    broken = Migration(
        99,
        "demonstrate_transaction_rollback",
        broken_up,
        broken_down,
    )

    runner = MigrationRunner(db)
    before = runner.applied_versions()

    try:
        runner.migrate([*MIGRATIONS, broken])
    except MigrationError as exc:
        print(f"\nExpected failure: {exc}")

    after = runner.applied_versions()
    table_exists = db.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'migration_failure_demo'
        """
    ).fetchone()[0]

    print(f"History unchanged after failure: {before == after}")
    print(f"Failed table exists: {bool(table_exists)}")


def demonstrate_checksum_protection(db: sqlite3.Connection) -> None:
    runner = MigrationRunner(db)

    tampered = Migration(
        2,
        "add_customer_status",
        lambda connection: connection.execute(
            "ALTER TABLE customers ADD COLUMN tampered TEXT"
        ),
        migration_002_add_status_down,
    )

    try:
        runner.validate_history([MIGRATIONS[0], tampered, *MIGRATIONS[2:]])
    except MigrationError as exc:
        print(f"\nChecksum protection detected drift: {exc}")


def main() -> None:
    db = sqlite3.connect(":memory:")

    try:
        runner = MigrationRunner(db)

        print("Applying schema migrations...")
        runner.migrate(MIGRATIONS)

        print("\nMigration history:")
        for record in runner.history():
            print(
                f"  v{record['version']} | {record['name']} | "
                f"{record['applied_at']}"
            )

        seed_business_data(db)

        print_schema(db)

        print("\nMigrated business data:")
        customers = db.execute(
            """
            SELECT id, email, full_name, status
            FROM customers
            ORDER BY id
            """
        ).fetchall()
        for customer in customers:
            print(dict(customer))

        orders = db.execute(
            """
            SELECT o.id, c.email, o.amount_cents, o.state
            FROM orders AS o
            JOIN customers AS c ON c.id = o.customer_id
            ORDER BY o.id
            """
        ).fetchall()
        for order in orders:
            print(dict(order))

        demonstrate_failed_migration(db)
        demonstrate_checksum_protection(db)

        print("\nRolling back the latest migration...")
        runner.rollback_last(MIGRATIONS)
        print(f"Applied versions after rollback: {runner.applied_versions()}")

        print("\nRe-applying the latest migration...")
        runner.migrate(MIGRATIONS)
        print(f"Applied versions: {runner.applied_versions()}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
