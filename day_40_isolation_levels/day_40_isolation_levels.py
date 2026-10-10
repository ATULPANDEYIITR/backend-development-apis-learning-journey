from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class IsolationLevel(Enum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class Account:
    account_id: int
    owner: str
    balance: int


@dataclass
class Version:
    value: int
    transaction_id: int
    committed: bool


@dataclass
class Transaction:
    transaction_id: int
    isolation: IsolationLevel
    state: TransactionState = TransactionState.ACTIVE
    snapshot: Dict[int, int] = field(default_factory=dict)
    writes: Dict[int, int] = field(default_factory=dict)
    read_set: set[int] = field(default_factory=set)
    write_set: set[int] = field(default_factory=set)


class SerializationFailure(RuntimeError):
    pass


class LockConflict(RuntimeError):
    pass


class BankDatabase:
    """
    A deliberately small MVCC-style transaction simulator.

    It is not a replacement for PostgreSQL. Its purpose is to make the
    visibility rules of the four SQL isolation levels executable without
    requiring an external database server.
    """

    def __init__(self, accounts: List[Account]):
        self._accounts: Dict[int, Account] = {
            account.account_id: copy.deepcopy(account) for account in accounts
        }
        self._committed_versions: Dict[int, List[Version]] = {
            account.account_id: [
                Version(account.balance, transaction_id=0, committed=True)
            ]
            for account in accounts
        }
        self._transactions: Dict[int, Transaction] = {}
        self._next_transaction_id = 1
        self._lock = threading.RLock()

    def begin(self, isolation: IsolationLevel) -> Transaction:
        with self._lock:
            transaction_id = self._next_transaction_id
            self._next_transaction_id += 1

            snapshot = {
                account_id: versions[-1].value
                for account_id, versions in self._committed_versions.items()
            }

            transaction = Transaction(
                transaction_id=transaction_id,
                isolation=isolation,
                snapshot=snapshot,
            )
            self._transactions[transaction_id] = transaction
            return transaction

    def _require_active(self, transaction: Transaction) -> None:
        if transaction.state is not TransactionState.ACTIVE:
            raise RuntimeError(
                f"Transaction {transaction.transaction_id} is "
                f"{transaction.state.value.lower()}"
            )

    def _latest_committed_value(self, account_id: int) -> int:
        versions = self._committed_versions[account_id]
        for version in reversed(versions):
            if version.committed:
                return version.value
        raise RuntimeError("No committed version exists")

    def _read_value(
        self,
        transaction: Transaction,
        account_id: int,
    ) -> int:
        self._require_active(transaction)

        if account_id not in self._accounts:
            raise KeyError(f"Unknown account: {account_id}")

        transaction.read_set.add(account_id)

        if account_id in transaction.writes:
            return transaction.writes[account_id]

        if transaction.isolation is IsolationLevel.READ_UNCOMMITTED:
            # A real PostgreSQL database does not expose another transaction's
            # uncommitted writes at READ UNCOMMITTED. PostgreSQL treats that
            # requested level as READ COMMITTED. This simulator deliberately
            # supports dirty reads so the ANSI phenomenon can be demonstrated.
            for other in self._transactions.values():
                if (
                    other.transaction_id != transaction.transaction_id
                    and other.state is TransactionState.ACTIVE
                    and account_id in other.writes
                ):
                    return other.writes[account_id]

        if transaction.isolation is IsolationLevel.READ_COMMITTED:
            return self._latest_committed_value(account_id)

        return transaction.snapshot[account_id]

    def read_balance(self, transaction: Transaction, account_id: int) -> int:
        return self._read_value(transaction, account_id)

    def write_balance(
        self,
        transaction: Transaction,
        account_id: int,
        new_balance: int,
    ) -> None:
        self._require_active(transaction)

        if account_id not in self._accounts:
            raise KeyError(f"Unknown account: {account_id}")

        if new_balance < 0:
            raise ValueError("Account balance cannot become negative")

        transaction.writes[account_id] = new_balance
        transaction.write_set.add(account_id)

    def increment_balance(
        self,
        transaction: Transaction,
        account_id: int,
        amount: int,
    ) -> None:
        current = self.read_balance(transaction, account_id)
        new_balance = current + amount

        if new_balance < 0:
            raise ValueError("Account balance cannot become negative")

        self.write_balance(transaction, account_id, new_balance)

    def commit(self, transaction: Transaction) -> None:
        with self._lock:
            self._require_active(transaction)

            if transaction.isolation is IsolationLevel.SERIALIZABLE:
                self._validate_serializable(transaction)

            if transaction.isolation is IsolationLevel.REPEATABLE_READ:
                self._validate_repeatable_read(transaction)

            for account_id, value in transaction.writes.items():
                self._committed_versions[account_id].append(
                    Version(
                        value=value,
                        transaction_id=transaction.transaction_id,
                        committed=True,
                    )
                )
                self._accounts[account_id].balance = value

            transaction.state = TransactionState.COMMITTED

    def rollback(self, transaction: Transaction) -> None:
        with self._lock:
            self._require_active(transaction)
            transaction.writes.clear()
            transaction.state = TransactionState.ABORTED

    def _validate_repeatable_read(self, transaction: Transaction) -> None:
        """
        Snapshot isolation prevents ordinary non-repeatable reads in this
        simulator. A concurrent update to a row written by this transaction
        creates a write-write conflict that must not silently overwrite data.
        """
        for account_id in transaction.write_set:
            latest = self._latest_committed_value(account_id)
            original = transaction.snapshot[account_id]

            if latest != original:
                raise SerializationFailure(
                    f"Repeatable-read write conflict on account {account_id}: "
                    f"snapshot={original}, current={latest}"
                )

    def _validate_serializable(self, transaction: Transaction) -> None:
        """
        The simulator detects concurrent changes to data read by a serializable
        transaction. This models the essential behavior: a transaction that
        cannot be serialized safely must abort instead of producing a result
        equivalent to an impossible serial execution.
        """
        for account_id in transaction.read_set | transaction.write_set:
            current = self._latest_committed_value(account_id)
            snapshot = transaction.snapshot[account_id]

            if current != snapshot:
                raise SerializationFailure(
                    f"Serializable transaction {transaction.transaction_id} "
                    f"detected a concurrent change on account {account_id}: "
                    f"snapshot={snapshot}, current={current}"
                )

    def committed_balance(self, account_id: int) -> int:
        return self._latest_committed_value(account_id)

    def dump_state(self) -> Dict[int, int]:
        return {
            account_id: self._latest_committed_value(account_id)
            for account_id in sorted(self._accounts)
        }


def print_transaction_result(
    name: str,
    transaction: Transaction,
    values: Tuple[int, ...],
) -> None:
    print(
        f"{name:<28} "
        f"isolation={transaction.isolation.value:<16} "
        f"state={transaction.state.value:<10} "
        f"observations={values}"
    )


def demonstrate_dirty_read() -> None:
    print("\n=== Dirty Read ===")
    print(
        "The simulator intentionally exposes an uncommitted write at "
        "READ UNCOMMITTED."
    )

    db = BankDatabase([Account(1, "Asha", 1000)])

    writer = db.begin(IsolationLevel.READ_COMMITTED)
    reader = db.begin(IsolationLevel.READ_UNCOMMITTED)

    db.write_balance(writer, 1, 250)

    dirty_value = db.read_balance(reader, 1)
    print(f"Reader observes uncommitted balance: {dirty_value}")

    db.rollback(writer)
    committed_value = db.read_balance(reader, 1)

    print(f"After writer rollback, committed balance: {committed_value}")
    db.rollback(reader)


def demonstrate_read_committed_non_repeatable_read() -> None:
    print("\n=== READ COMMITTED and Non-Repeatable Read ===")

    db = BankDatabase([Account(1, "Asha", 1000)])

    reader = db.begin(IsolationLevel.READ_COMMITTED)
    writer = db.begin(IsolationLevel.READ_COMMITTED)

    first_read = db.read_balance(reader, 1)

    db.write_balance(writer, 1, 1300)
    db.commit(writer)

    second_read = db.read_balance(reader, 1)

    print_transaction_result(
        "READ COMMITTED reader",
        reader,
        (first_read, second_read),
    )

    print(
        "The same statement-level lookup can observe a newer committed "
        "value after another transaction commits."
    )

    db.rollback(reader)


def demonstrate_repeatable_read_snapshot() -> None:
    print("\n=== REPEATABLE READ Snapshot ===")

    db = BankDatabase([Account(1, "Asha", 1000)])

    reader = db.begin(IsolationLevel.REPEATABLE_READ)
    writer = db.begin(IsolationLevel.READ_COMMITTED)

    first_read = db.read_balance(reader, 1)

    db.write_balance(writer, 1, 1600)
    db.commit(writer)

    second_read = db.read_balance(reader, 1)

    print_transaction_result(
        "REPEATABLE READ reader",
        reader,
        (first_read, second_read),
    )

    db.rollback(reader)


def demonstrate_serializable_conflict() -> None:
    print("\n=== SERIALIZABLE Conflict Detection ===")

    db = BankDatabase(
        [
            Account(1, "Asha", 1000),
            Account(2, "Bharat", 1000),
        ]
    )

    transaction_a = db.begin(IsolationLevel.SERIALIZABLE)
    transaction_b = db.begin(IsolationLevel.SERIALIZABLE)

    total_a = (
        db.read_balance(transaction_a, 1)
        + db.read_balance(transaction_a, 2)
    )

    db.increment_balance(transaction_b, 1, 500)
    db.commit(transaction_b)

    db.write_balance(transaction_a, 2, 2000)

    print(f"Transaction A initially observed total: {total_a}")

    try:
        db.commit(transaction_a)
    except SerializationFailure as exc:
        transaction_a.state = TransactionState.ABORTED
        print(f"Serialization failure: {exc}")

    print(f"Final committed balances: {db.dump_state()}")


def demonstrate_lost_update_protection() -> None:
    print("\n=== Lost Update and Application-Level Read/Write ===")

    db = BankDatabase([Account(1, "Asha", 1000)])

    first = db.begin(IsolationLevel.REPEATABLE_READ)
    second = db.begin(IsolationLevel.REPEATABLE_READ)

    first_value = db.read_balance(first, 1)
    second_value = db.read_balance(second, 1)

    db.write_balance(first, 1, first_value + 100)
    db.commit(first)

    db.write_balance(second, 1, second_value + 200)

    try:
        db.commit(second)
    except SerializationFailure as exc:
        second.state = TransactionState.ABORTED
        print(f"Second transaction aborted instead of overwriting the first: {exc}")

    print(f"Final balance: {db.committed_balance(1)}")


def transfer(
    db: BankDatabase,
    transaction: Transaction,
    source_id: int,
    destination_id: int,
    amount: int,
) -> None:
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    if source_id == destination_id:
        raise ValueError("Source and destination accounts must differ")

    source_balance = db.read_balance(transaction, source_id)

    if source_balance < amount:
        raise ValueError(
            f"Insufficient funds in account {source_id}: "
            f"balance={source_balance}, requested={amount}"
        )

    destination_balance = db.read_balance(transaction, destination_id)

    db.write_balance(transaction, source_id, source_balance - amount)
    db.write_balance(
        transaction,
        destination_id,
        destination_balance + amount,
    )


def demonstrate_serializable_transfer() -> None:
    print("\n=== Serializable Transfer Workflow ===")

    db = BankDatabase(
        [
            Account(1, "Asha", 1000),
            Account(2, "Bharat", 500),
        ]
    )

    transaction = db.begin(IsolationLevel.SERIALIZABLE)

    try:
        transfer(db, transaction, 1, 2, 250)
        db.commit(transaction)
    except (ValueError, SerializationFailure):
        if transaction.state is TransactionState.ACTIVE:
            db.rollback(transaction)
        raise

    print(f"Balances after transfer: {db.dump_state()}")


def demonstrate_rollback() -> None:
    print("\n=== Rollback and Atomicity ===")

    db = BankDatabase(
        [
            Account(1, "Asha", 1000),
            Account(2, "Bharat", 500),
        ]
    )

    transaction = db.begin(IsolationLevel.READ_COMMITTED)

    try:
        transfer(db, transaction, 1, 2, 300)
        raise RuntimeError("Simulated downstream payment-service failure")
    except RuntimeError as exc:
        print(f"Failure: {exc}")
        db.rollback(transaction)

    print(f"Balances after rollback: {db.dump_state()}")


def demonstrate_validation_and_failure() -> None:
    print("\n=== Validation and Failure Conditions ===")

    db = BankDatabase([Account(1, "Asha", 1000)])

    transaction = db.begin(IsolationLevel.READ_COMMITTED)

    failures = [
        ("unknown account", lambda: db.read_balance(transaction, 999)),
        (
            "negative balance",
            lambda: db.write_balance(transaction, 1, -50),
        ),
        (
            "zero transfer",
            lambda: transfer(db, transaction, 1, 1, 0),
        ),
    ]

    for description, operation in failures:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            print(f"{description}: rejected -> {exc}")

    db.rollback(transaction)


def compare_isolation_levels() -> None:
    print("\n=== Isolation-Level Semantics ===")

    rows = [
        (
            IsolationLevel.READ_UNCOMMITTED,
            "May expose dirty data in this simulator; PostgreSQL maps it to READ COMMITTED.",
        ),
        (
            IsolationLevel.READ_COMMITTED,
            "Each statement sees data committed before that statement begins.",
        ),
        (
            IsolationLevel.REPEATABLE_READ,
            "The transaction reads from a stable snapshot in PostgreSQL.",
        ),
        (
            IsolationLevel.SERIALIZABLE,
            "The database must make committed transactions equivalent to a serial order.",
        ),
    ]

    for isolation, behavior in rows:
        print(f"{isolation.value:<18} {behavior}")


def explain_postgresql_specific_behavior() -> None:
    print("\n=== PostgreSQL-Specific Interpretation ===")
    print(
        "PostgreSQL accepts READ UNCOMMITTED syntax but provides "
        "READ COMMITTED semantics for it."
    )
    print(
        "PostgreSQL READ COMMITTED uses a statement snapshot, while "
        "REPEATABLE READ uses a transaction-level snapshot."
    )
    print(
        "PostgreSQL SERIALIZABLE uses Serializable Snapshot Isolation and "
        "can abort transactions with serialization failures."
    )
    print(
        "Applications must be prepared to retry transactions after "
        "serialization failures rather than treating them as ordinary input errors."
    )


def run_concurrent_demo() -> None:
    print("\n=== Threaded Scheduling Demonstration ===")

    db = BankDatabase([Account(1, "Asha", 1000)])
    barrier = threading.Barrier(2)
    observations: List[str] = []
    observation_lock = threading.Lock()

    def reader() -> None:
        transaction = db.begin(IsolationLevel.READ_COMMITTED)
        first = db.read_balance(transaction, 1)
        barrier.wait()

        time.sleep(0.02)

        second = db.read_balance(transaction, 1)

        with observation_lock:
            observations.append(
                f"reader: first={first}, second={second}"
            )

        db.rollback(transaction)

    def writer() -> None:
        transaction = db.begin(IsolationLevel.READ_COMMITTED)
        barrier.wait()

        db.write_balance(transaction, 1, 1200)
        db.commit(transaction)

    threads = [
        threading.Thread(target=reader),
        threading.Thread(target=writer),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    for observation in observations:
        print(observation)

    print(
        "Thread scheduling is nondeterministic; the important point is that "
        "READ COMMITTED can observe a later committed value."
    )


def main() -> None:
    print("Transaction Isolation Level Laboratory")
    print("=" * 44)

    compare_isolation_levels()
    explain_postgresql_specific_behavior()

    demonstrate_dirty_read()
    demonstrate_read_committed_non_repeatable_read()
    demonstrate_repeatable_read_snapshot()
    demonstrate_serializable_conflict()
    demonstrate_lost_update_protection()
    demonstrate_serializable_transfer()
    demonstrate_rollback()
    demonstrate_validation_and_failure()
    run_concurrent_demo()

    print("\n=== Final Design Guidance ===")
    print(
        "Choose the weakest isolation level that preserves the application's "
        "correctness invariant, and strengthen it when concurrent anomalies "
        "can violate that invariant."
    )
    print(
        "Keep transactions short. Long transactions retain snapshots or locks "
        "longer and can increase contention, blocking, and serialization failures."
    )
    print(
        "At SERIALIZABLE, implement bounded retry logic for transient "
        "serialization failures with idempotent transaction operations."
    )


if __name__ == "__main__":
    main()
