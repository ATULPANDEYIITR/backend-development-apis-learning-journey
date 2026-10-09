/*
 * TransactionsAcid.java
 *
 * Java 17 enterprise-oriented transaction model.
 *
 * The program models a payment service with:
 * - explicit transaction boundaries
 * - atomic transfers
 * - consistency rules
 * - approval before commit
 * - rollback on failure
 * - savepoints
 * - immutable transaction results
 * - domain-specific exceptions
 * - repository-level transaction ownership
 */

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class TransactionsAcid {

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK
    }

    enum LedgerType {
        DEPOSIT,
        WITHDRAWAL,
        TRANSFER_OUT,
        TRANSFER_IN
    }

    static final class Account {
        private final long id;
        private final String owner;
        private long balanceCents;
        private boolean active;

        Account(long id, String owner, long balanceCents) {
            if (id <= 0) {
                throw new ConsistencyException("Account ID must be positive.");
            }

            if (balanceCents < 0) {
                throw new ConsistencyException(
                    "Initial balance cannot be negative."
                );
            }

            this.id = id;
            this.owner = Objects.requireNonNull(owner);
            this.balanceCents = balanceCents;
            this.active = true;
        }

        Account(Account source) {
            this.id = source.id;
            this.owner = source.owner;
            this.balanceCents = source.balanceCents;
            this.active = source.active;
        }

        long id() {
            return id;
        }

        String owner() {
            return owner;
        }

        long balanceCents() {
            return balanceCents;
        }

        boolean active() {
            return active;
        }

        void credit(long amountCents) {
            if (amountCents <= 0) {
                throw new ConsistencyException(
                    "Credit amount must be positive."
                );
            }

            balanceCents += amountCents;
        }

        void debit(long amountCents) {
            if (amountCents <= 0) {
                throw new ConsistencyException(
                    "Debit amount must be positive."
                );
            }

            if (balanceCents < amountCents) {
                throw new TransactionException(
                    "Insufficient funds for account " + id
                );
            }

            balanceCents -= amountCents;
        }
    }

    record LedgerEntry(
        String reference,
        long accountId,
        LedgerType type,
        long amountCents
    ) {
        LedgerEntry {
            Objects.requireNonNull(reference);
            Objects.requireNonNull(type);

            if (amountCents <= 0) {
                throw new ConsistencyException(
                    "Ledger amount must be positive."
                );
            }
        }
    }

    record TransactionResult(
        String reference,
        TransactionState state,
        String reason
    ) {}

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class ConsistencyException extends TransactionException {
        ConsistencyException(String message) {
            super(message);
        }
    }

    static final class DatabaseSnapshot {
        private final Map<Long, Account> accounts;
        private final List<LedgerEntry> ledger;

        DatabaseSnapshot(
            Map<Long, Account> accounts,
            List<LedgerEntry> ledger
        ) {
            this.accounts = deepCopyAccounts(accounts);
            this.ledger = new ArrayList<>(ledger);
        }

        private static Map<Long, Account> deepCopyAccounts(
            Map<Long, Account> source
        ) {
            Map<Long, Account> copy = new HashMap<>();

            for (Map.Entry<Long, Account> entry : source.entrySet()) {
                copy.put(entry.getKey(), new Account(entry.getValue()));
            }

            return copy;
        }
    }

    static final class Database {
        private final Map<Long, Account> accounts = new HashMap<>();
        private final List<LedgerEntry> ledger = new ArrayList<>();
        private boolean transactionActive;

        void addAccount(long id, String owner, long balanceCents) {
            if (accounts.containsKey(id)) {
                throw new ConsistencyException(
                    "Account already exists: " + id
                );
            }

            accounts.put(id, new Account(id, owner, balanceCents));
        }

        Account getAccount(long id) {
            Account account = accounts.get(id);

            if (account == null) {
                throw new ConsistencyException(
                    "Account does not exist: " + id
                );
            }

            if (!account.active()) {
                throw new ConsistencyException(
                    "Account is inactive: " + id
                );
            }

            return account;
        }

        DatabaseSnapshot snapshot() {
            return new DatabaseSnapshot(accounts, ledger);
        }

        void restore(DatabaseSnapshot snapshot) {
            accounts.clear();

            for (Map.Entry<Long, Account> entry : snapshot.accounts.entrySet()) {
                accounts.put(entry.getKey(), new Account(entry.getValue()));
            }

            ledger.clear();
            ledger.addAll(snapshot.ledger);
        }

        void validateConsistency() {
            for (Account account : accounts.values()) {
                if (account.balanceCents() < 0) {
                    throw new ConsistencyException(
                        "Negative balance detected for account " +
                        account.id()
                    );
                }
            }

            for (LedgerEntry entry : ledger) {
                if (!accounts.containsKey(entry.accountId())) {
                    throw new ConsistencyException(
                        "Ledger references unknown account."
                    );
                }
            }
        }

        void lock() {
            if (transactionActive) {
                throw new TransactionException(
                    "A transaction is already active."
                );
            }

            transactionActive = true;
        }

        void unlock() {
            transactionActive = false;
        }

        void addLedgerEntry(LedgerEntry entry) {
            ledger.add(entry);
        }

        void printAccounts(String title) {
            System.out.println("\n--- " + title + " ---");

            accounts.values().stream()
                .sorted((a, b) -> Long.compare(a.id(), b.id()))
                .forEach(account ->
                    System.out.printf(
                        "%d %-8s balance=%.2f active=%s%n",
                        account.id(),
                        account.owner(),
                        account.balanceCents() / 100.0,
                        account.active()
                    )
                );
        }

        void printLedger() {
            System.out.println("\n--- Ledger ---");

            ledger.forEach(entry ->
                System.out.printf(
                    "%s account=%d type=%s amount=%.2f%n",
                    entry.reference(),
                    entry.accountId(),
                    entry.type(),
                    entry.amountCents() / 100.0
                )
            );
        }
    }

    static final class Transaction implements AutoCloseable {
        private final Database database;
        private final DatabaseSnapshot original;
        private final String reference;
        private final Map<String, DatabaseSnapshot> savepoints =
            new HashMap<>();

        private TransactionState state = TransactionState.ACTIVE;

        Transaction(
            Database database,
            DatabaseSnapshot original,
            String reference
        ) {
            this.database = database;
            this.original = original;
            this.reference = reference;
        }

        private void requireActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active."
                );
            }
        }

        void deposit(long accountId, long amountCents) {
            requireActive();

            Account account = database.getAccount(accountId);
            account.credit(amountCents);

            database.addLedgerEntry(
                new LedgerEntry(
                    reference,
                    accountId,
                    LedgerType.DEPOSIT,
                    amountCents
                )
            );
        }

        void withdraw(long accountId, long amountCents) {
            requireActive();

            Account account = database.getAccount(accountId);
            account.debit(amountCents);

            database.addLedgerEntry(
                new LedgerEntry(
                    reference,
                    accountId,
                    LedgerType.WITHDRAWAL,
                    amountCents
                )
            );
        }

        void transfer(
            long sourceId,
            long targetId,
            long amountCents
        ) {
            requireActive();

            if (sourceId == targetId) {
                throw new ConsistencyException(
                    "Source and target accounts must differ."
                );
            }

            Account source = database.getAccount(sourceId);
            Account target = database.getAccount(targetId);

            source.debit(amountCents);
            target.credit(amountCents);

            database.addLedgerEntry(
                new LedgerEntry(
                    reference,
                    sourceId,
                    LedgerType.TRANSFER_OUT,
                    amountCents
                )
            );

            database.addLedgerEntry(
                new LedgerEntry(
                    reference,
                    targetId,
                    LedgerType.TRANSFER_IN,
                    amountCents
                )
            );
        }

        void createSavepoint(String name) {
            requireActive();

            if (name == null || name.isBlank()) {
                throw new TransactionException(
                    "Savepoint name cannot be blank."
                );
            }

            savepoints.put(name, database.snapshot());
        }

        void rollbackToSavepoint(String name) {
            requireActive();

            DatabaseSnapshot snapshot = savepoints.get(name);

            if (snapshot == null) {
                throw new TransactionException(
                    "Unknown savepoint: " + name
                );
            }

            database.restore(snapshot);
        }

        void releaseSavepoint(String name) {
            requireActive();
            savepoints.remove(name);
        }

        TransactionResult commit() {
            requireActive();

            database.validateConsistency();

            state = TransactionState.COMMITTED;
            database.unlock();

            return new TransactionResult(
                reference,
                state,
                "Transaction committed."
            );
        }

        TransactionResult rollback(String reason) {
            requireActive();

            database.restore(original);
            state = TransactionState.ROLLED_BACK;
            database.unlock();

            return new TransactionResult(
                reference,
                state,
                reason
            );
        }

        @Override
        public void close() {
            /*
             * AutoCloseable acts as a defensive transaction boundary. An
             * abandoned active transaction is rolled back rather than being
             * silently left open.
             */
            if (state == TransactionState.ACTIVE) {
                database.restore(original);
                state = TransactionState.ROLLED_BACK;
                database.unlock();
            }
        }
    }

    static final class PaymentService {
        private final Database database;

        PaymentService(Database database) {
            this.database = database;
        }

        TransactionResult transfer(
            long sourceId,
            long targetId,
            long amountCents,
            String reference
        ) {
            database.lock();

            Transaction transaction = new Transaction(
                database,
                database.snapshot(),
                reference
            );

            try (transaction) {
                transaction.transfer(
                    sourceId,
                    targetId,
                    amountCents
                );

                return transaction.commit();
            } catch (TransactionException error) {
                if (transaction.state == TransactionState.ACTIVE) {
                    return transaction.rollback(error.getMessage());
                }

                return new TransactionResult(
                    reference,
                    transaction.state,
                    error.getMessage()
                );
            }
        }

        TransactionResult transferWithOptionalOperation(
            long sourceId,
            long targetId,
            long amountCents,
            String reference
        ) {
            database.lock();

            Transaction transaction = new Transaction(
                database,
                database.snapshot(),
                reference
            );

            try (transaction) {
                transaction.transfer(
                    sourceId,
                    targetId,
                    amountCents
                );

                transaction.createSavepoint("optional");

                try {
                    transaction.withdraw(999999, 100);
                } catch (TransactionException error) {
                    transaction.rollbackToSavepoint("optional");
                }

                transaction.releaseSavepoint("optional");

                return transaction.commit();
            } catch (TransactionException error) {
                if (transaction.state == TransactionState.ACTIVE) {
                    return transaction.rollback(error.getMessage());
                }

                return new TransactionResult(
                    reference,
                    transaction.state,
                    error.getMessage()
                );
            }
        }
    }

    public static void main(String[] args) {
        Database database = new Database();

        database.addAccount(101, "Asha", 100_000);
        database.addAccount(102, "Ravi", 50_000);
        database.addAccount(103, "Meera", 0);

        database.printAccounts("Initial state");

        PaymentService paymentService = new PaymentService(database);

        TransactionResult successful =
            paymentService.transfer(
                101,
                102,
                12_550,
                "TRF-001"
            );

        System.out.println("\nSuccessful transaction:");
        System.out.println(successful);

        long sourceBefore =
            database.getAccount(101).balanceCents();

        TransactionResult failed =
            paymentService.transfer(
                101,
                102,
                9_999_999_99L,
                "TRF-FAILED"
            );

        System.out.println("\nFailed transaction:");
        System.out.println(failed);

        long sourceAfter =
            database.getAccount(101).balanceCents();

        System.out.println(
            "Source balance preserved after rollback: " +
            (sourceBefore == sourceAfter)
        );

        TransactionResult savepointResult =
            paymentService.transferWithOptionalOperation(
                102,
                103,
                5_000,
                "TRF-SAVEPOINT"
            );

        System.out.println("\nSavepoint transaction:");
        System.out.println(savepointResult);

        database.printAccounts("Final state");
        database.printLedger();

        System.out.println("\nACID interpretation:");
        System.out.println(
            "Atomicity: related account and ledger changes commit together."
        );
        System.out.println(
            "Consistency: domain invariants are checked before commit."
        );
        System.out.println(
            "Isolation: the transaction service controls concurrent writers."
        );
        System.out.println(
            "Durability: a real implementation persists committed state."
        );
    }
}
