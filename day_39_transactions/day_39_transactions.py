"""
transactions_acid.py

A self-contained progression from basic database transaction concepts to
a realistic bank-transfer transaction simulator.

The executable examples focus on:
- ACID properties
- BEGIN / COMMIT / ROLLBACK semantics
- Atomicity
- Consistency
- Isolation
- Durability
- Validation and constraint enforcement
- Nested transaction-like savepoints
- Failure handling
- Concurrent transaction reasoning
- SQLite-backed transactions using Python's standard library
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


DB_FILE = Path(tempfile.gettempdir()) / "acid_transactions_demo.sqlite3"


def money(value: str | int | float | Decimal) -> Decimal:
    """Convert an input value into a two-decimal monetary amount."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    if amount < Decimal("0.00"):
        raise ValueError("Money cannot be negative.")
    return amount


def create_database(connection: sqlite3.Connection) -> None:
    """
    Create a small banking schema.

    SQLite CHECK constraints provide database-level consistency rules rather
    than relying only on application validation.
    """
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY,
            owner TEXT NOT NULL,
            balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS ledger (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL
                CHECK (transaction_type IN ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER_IN', 'TRANSFER_OUT')),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            reference TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );

        CREATE INDEX IF NOT EXISTS idx_ledger_account
        ON ledger(account_id);

        CREATE TABLE IF NOT EXISTS transaction_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            reference TEXT NOT NULL,
            outcome TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def reset_database(connection: sqlite3.Connection) -> None:
    """Reset demonstration data without leaving an open transaction."""
    connection.execute("DELETE FROM ledger")
    connection.execute("DELETE FROM transaction_audit")
    connection.execute("DELETE FROM accounts")
    connection.executemany(
        """
        INSERT INTO accounts(account_id, owner, balance_cents)
        VALUES (?, ?, ?)
        """,
        [
            (101, "Asha", 100_000),
            (102, "Ravi", 50_000),
            (103, "Meera", 0),
        ],
    )
    connection.commit()


def show_accounts(connection: sqlite3.Connection, title: str) -> None:
    print(f"\n--- {title} ---")
    rows = connection.execute(
        """
        SELECT account_id, owner, balance_cents, active
        FROM accounts
        ORDER BY account_id
        """
    ).fetchall()

    for account_id, owner, cents, active in rows:
        print(
            f"{account_id}: {owner:6} "
            f"balance={cents / 100:,.2f} "
            f"active={bool(active)}"
        )


def deposit(
    connection: sqlite3.Connection,
    account_id: int,
    amount: Decimal,
    reference: str,
) -> None:
    """Deposit money inside the caller's transaction."""
    cents = int(amount * 100)

    cursor = connection.execute(
        """
        UPDATE accounts
        SET balance_cents = balance_cents + ?
        WHERE account_id = ? AND active = 1
        """,
        (cents, account_id),
    )

    if cursor.rowcount != 1:
        raise ValueError(f"Active account {account_id} does not exist.")

    connection.execute(
        """
        INSERT INTO ledger(account_id, transaction_type, amount_cents, reference)
        VALUES (?, 'DEPOSIT', ?, ?)
        """,
        (account_id, cents, reference),
    )


def withdraw(
    connection: sqlite3.Connection,
    account_id: int,
    amount: Decimal,
    reference: str,
) -> None:
    """
    Withdraw money atomically.

    The WHERE clause makes insufficient funds a database-level operation
    failure: the balance can never become negative through this function.
    """
    cents = int(amount * 100)

    cursor = connection.execute(
        """
        UPDATE accounts
        SET balance_cents = balance_cents - ?
        WHERE account_id = ?
          AND active = 1
          AND balance_cents >= ?
        """,
        (cents, account_id, cents),
    )

    if cursor.rowcount != 1:
        raise ValueError(
            f"Withdrawal rejected for account {account_id}: "
            "account missing, inactive, or insufficient funds."
        )

    connection.execute(
        """
        INSERT INTO ledger(account_id, transaction_type, amount_cents, reference)
        VALUES (?, 'WITHDRAWAL', ?, ?)
        """,
        (account_id, cents, reference),
    )


def transfer(
    connection: sqlite3.Connection,
    source_id: int,
    target_id: int,
    amount: Decimal,
    reference: str,
) -> None:
    """
    Execute a complete transfer inside the caller's transaction.

    Both balance changes and both ledger entries belong to the same
    transaction. If either operation fails, the caller can roll back all work.
    """
    if source_id == target_id:
        raise ValueError("Source and target accounts must differ.")

    if amount <= Decimal("0.00"):
        raise ValueError("Transfer amount must be greater than zero.")

    cents = int(amount * 100)

    cursor = connection.execute(
        """
        UPDATE accounts
        SET balance_cents = balance_cents - ?
        WHERE account_id = ?
          AND active = 1
          AND balance_cents >= ?
        """,
        (cents, source_id, cents),
    )

    if cursor.rowcount != 1:
        raise ValueError(
            f"Transfer rejected: source account {source_id} "
            "does not have enough available balance."
        )

    cursor = connection.execute(
        """
        UPDATE accounts
        SET balance_cents = balance_cents + ?
        WHERE account_id = ? AND active = 1
        """,
        (cents, target_id),
    )

    if cursor.rowcount != 1:
        raise ValueError(f"Transfer rejected: target account {target_id} is invalid.")

    connection.execute(
        """
        INSERT INTO ledger(account_id, transaction_type, amount_cents, reference)
        VALUES (?, 'TRANSFER_OUT', ?, ?)
        """,
        (source_id, cents, reference),
    )

    connection.execute(
        """
        INSERT INTO ledger(account_id, transaction_type, amount_cents, reference)
        VALUES (?, 'TRANSFER_IN', ?, ?)
        """,
        (target_id, cents, reference),
    )


def demonstrate_commit(connection: sqlite3.Connection) -> None:
    print("\nACID example: successful transaction")

    connection.execute("BEGIN")
    try:
        deposit(connection, 103, money("250.00"), "DEP-001")
        connection.execute(
            """
            INSERT INTO transaction_audit(operation, reference, outcome)
            VALUES ('DEPOSIT', 'DEP-001', 'PENDING')
            """
        )
        connection.execute(
            """
            UPDATE transaction_audit
            SET outcome = 'COMMITTED'
            WHERE reference = 'DEP-001'
            """
        )
        connection.commit()
        print("COMMIT completed.")
    except Exception:
        connection.rollback()
        raise


def demonstrate_rollback(connection: sqlite3.Connection) -> None:
    print("\nAtomicity example: forced failure")

    before = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 101"
    ).fetchone()[0]

    connection.execute("BEGIN")

    try:
        withdraw(connection, 101, money("100.00"), "ROLLBACK-001")

        # This deliberately violates the positive-amount CHECK constraint.
        connection.execute(
            """
            INSERT INTO ledger(
                account_id, transaction_type, amount_cents, reference
            )
            VALUES (101, 'WITHDRAWAL', 0, 'ROLLBACK-001')
            """
        )

        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        print(f"Expected failure: {exc}")

    after = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 101"
    ).fetchone()[0]

    print(f"Balance before failed transaction: {before / 100:,.2f}")
    print(f"Balance after rollback:           {after / 100:,.2f}")
    assert before == after


def demonstrate_transfer_rollback(connection: sqlite3.Connection) -> None:
    print("\nAtomicity example: transfer with a failing second operation")

    before_source = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 101"
    ).fetchone()[0]
    before_target = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 102"
    ).fetchone()[0]

    connection.execute("BEGIN")

    try:
        # The source is debited first.
        cursor = connection.execute(
            """
            UPDATE accounts
            SET balance_cents = balance_cents - 10000
            WHERE account_id = 101 AND balance_cents >= 10000
            """
        )

        if cursor.rowcount != 1:
            raise ValueError("Source debit failed.")

        # Deliberately use an invalid target account.
        cursor = connection.execute(
            """
            UPDATE accounts
            SET balance_cents = balance_cents + 10000
            WHERE account_id = 999999
            """
        )

        if cursor.rowcount != 1:
            raise ValueError("Target credit failed.")

        connection.commit()
    except Exception as exc:
        connection.rollback()
        print(f"Expected failure: {exc}")

    after_source = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 101"
    ).fetchone()[0]
    after_target = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 102"
    ).fetchone()[0]

    assert before_source == after_source
    assert before_target == after_target
    print("Both accounts returned to their original state.")


def demonstrate_savepoint(connection: sqlite3.Connection) -> None:
    """
    Demonstrate partial rollback with SAVEPOINT.

    A savepoint is not the same as independently committing nested
    transactions. The outer transaction remains active.
    """
    print("\nSavepoint example")

    connection.execute("BEGIN")
    try:
        deposit(connection, 103, money("100.00"), "SAVEPOINT-VALID")

        connection.execute("SAVEPOINT optional_operation")

        try:
            withdraw(connection, 101, money("999999.00"), "SAVEPOINT-INVALID")
        except ValueError:
            connection.execute("ROLLBACK TO SAVEPOINT optional_operation")
            print("Optional operation rolled back to savepoint.")

        connection.execute("RELEASE SAVEPOINT optional_operation")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def demonstrate_consistency(connection: sqlite3.Connection) -> None:
    print("\nConsistency example")

    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            UPDATE accounts
            SET balance_cents = -1
            WHERE account_id = 101
            """
        )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        print(f"CHECK constraint prevented invalid state: {exc}")


def demonstrate_isolation_reasoning() -> None:
    """
    Explain isolation with two independent SQLite connections.

    SQLite serializes writers. The second writer waits or receives a locked
    error depending on timeout and journal configuration. The example uses
    WAL mode and a short timeout to make the database behavior observable.
    """
    print("\nIsolation example")

    connection_a = sqlite3.connect(DB_FILE, timeout=0.2, isolation_level=None)
    connection_b = sqlite3.connect(DB_FILE, timeout=0.2, isolation_level=None)

    try:
        connection_a.execute("PRAGMA journal_mode=WAL")
        connection_a.execute("BEGIN IMMEDIATE")

        connection_a.execute(
            """
            UPDATE accounts
            SET balance_cents = balance_cents + 500
            WHERE account_id = 103
            """
        )

        try:
            connection_b.execute("BEGIN IMMEDIATE")
            connection_b.execute(
                """
                UPDATE accounts
                SET balance_cents = balance_cents + 500
                WHERE account_id = 103
                """
            )
            connection_b.commit()
        except sqlite3.OperationalError as exc:
            connection_b.rollback()
            print(f"Concurrent writer was prevented while A held the write lock: {exc}")

        connection_a.rollback()
    finally:
        connection_a.close()
        connection_b.close()


def demonstrate_transaction_context_manager(connection: sqlite3.Connection) -> None:
    """
    sqlite3.Connection supports the context-manager protocol.

    A successful block is committed. An exception causes rollback.
    """
    print("\nPython transaction context-manager example")

    with connection:
        deposit(connection, 103, money("75.00"), "CTX-001")

    try:
        with connection:
            withdraw(connection, 101, money("25.00"), "CTX-ROLLBACK")
            raise RuntimeError("Application failure after database modification.")
    except RuntimeError as exc:
        print(f"Context manager rolled back after exception: {exc}")


def demonstrate_real_transfer(connection: sqlite3.Connection) -> None:
    print("\nReal transfer transaction")

    connection.execute("BEGIN")

    try:
        transfer(
            connection,
            source_id=101,
            target_id=102,
            amount=money("125.50"),
            reference="TRF-001",
        )
        connection.commit()
        print("Transfer committed successfully.")
    except Exception:
        connection.rollback()
        raise


def demonstrate_failed_transfer(connection: sqlite3.Connection) -> None:
    print("\nFailed transfer and rollback")

    source_before = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 101"
    ).fetchone()[0]
    target_before = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 102"
    ).fetchone()[0]

    connection.execute("BEGIN")

    try:
        transfer(
            connection,
            source_id=101,
            target_id=102,
            amount=money("9999999.99"),
            reference="TRF-FAILED",
        )
        connection.commit()
    except ValueError as exc:
        connection.rollback()
        print(f"Expected transfer failure: {exc}")

    source_after = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 101"
    ).fetchone()[0]
    target_after = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = 102"
    ).fetchone()[0]

    assert source_before == source_after
    assert target_before == target_after


def show_ledger(connection: sqlite3.Connection) -> None:
    print("\n--- Ledger ---")

    rows = connection.execute(
        """
        SELECT
            transaction_id,
            account_id,
            transaction_type,
            amount_cents,
            reference,
            created_at
        FROM ledger
        ORDER BY transaction_id
        """
    ).fetchall()

    for row in rows:
        print(row)


@dataclass(frozen=True)
class TransactionResult:
    reference: str
    committed: bool
    error: str | None = None


class TransactionService:
    """
    Application service that owns transaction boundaries.

    Domain functions perform database work, while this service decides when
    that work becomes durable.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def execute_transfer(
        self,
        source_id: int,
        target_id: int,
        amount: Decimal,
        reference: str,
    ) -> TransactionResult:
        try:
            self.connection.execute("BEGIN")

            transfer(
                self.connection,
                source_id,
                target_id,
                amount,
                reference,
            )

            self.connection.commit()
            return TransactionResult(reference, True)
        except Exception as exc:
            self.connection.rollback()
            return TransactionResult(reference, False, str(exc))


def cleanup_database() -> None:
    try:
        DB_FILE.unlink()
    except FileNotFoundError:
        pass


def main() -> None:
    cleanup_database()

    connection = sqlite3.connect(
        DB_FILE,
        isolation_level=None,
        timeout=5.0,
    )

    try:
        create_database(connection)
        reset_database(connection)

        show_accounts(connection, "Initial state")

        demonstrate_commit(connection)
        demonstrate_rollback(connection)
        demonstrate_transfer_rollback(connection)
        demonstrate_savepoint(connection)
        demonstrate_consistency(connection)
        demonstrate_transaction_context_manager(connection)
        demonstrate_real_transfer(connection)
        demonstrate_failed_transfer(connection)
        demonstrate_isolation_reasoning()

        service = TransactionService(connection)

        print("\nService-layer transaction example")
        result = service.execute_transfer(
            102,
            103,
            money("50.00"),
            "SERVICE-001",
        )
        print(result)

        show_accounts(connection, "Final state")
        show_ledger(connection)

        print("\nACID interpretation:")
        print("Atomicity    -> grouped changes commit together or roll back together.")
        print("Consistency  -> constraints prevent invalid database states.")
        print("Isolation    -> concurrent transactions are controlled by the database.")
        print("Durability   -> committed changes remain after the transaction completes.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
