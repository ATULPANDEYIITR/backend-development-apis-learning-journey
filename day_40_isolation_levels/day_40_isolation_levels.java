import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class TransactionIsolationEnterpriseDemo {

    enum IsolationLevel {
        READ_UNCOMMITTED,
        READ_COMMITTED,
        REPEATABLE_READ,
        SERIALIZABLE
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED
    }

    static final class SerializationFailure extends Exception {
        SerializationFailure(String message) {
            super(message);
        }
    }

    static final class ValidationException extends Exception {
        ValidationException(String message) {
            super(message);
        }
    }

    record Account(String id, String owner, long balance) {
        Account {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException("Account id is required");
            }

            if (owner == null || owner.isBlank()) {
                throw new IllegalArgumentException("Account owner is required");
            }

            if (balance < 0) {
                throw new IllegalArgumentException(
                    "Account balance cannot be negative"
                );
            }
        }

        Account withBalance(long newBalance) {
            return new Account(id, owner, newBalance);
        }
    }

    static final class Transaction {
        private final long id;
        private final IsolationLevel isolationLevel;
        private final Map<String, Long> snapshot;
        private final Map<String, Long> pendingWrites = new HashMap<>();
        private final Set<String> readSet = new HashSet<>();
        private final Set<String> writeSet = new HashSet<>();
        private TransactionState state = TransactionState.ACTIVE;

        Transaction(
            long id,
            IsolationLevel isolationLevel,
            Map<String, Long> snapshot
        ) {
            this.id = id;
            this.isolationLevel = isolationLevel;
            this.snapshot = Map.copyOf(snapshot);
        }

        long id() {
            return id;
        }

        IsolationLevel isolationLevel() {
            return isolationLevel;
        }

        TransactionState state() {
            return state;
        }

        void commitState() {
            state = TransactionState.COMMITTED;
        }

        void abortState() {
            state = TransactionState.ABORTED;
            pendingWrites.clear();
        }
    }

    interface IsolationPolicy {
        long read(
            Transaction transaction,
            String accountId,
            Map<String, Account> accounts,
            Map<Long, Transaction> transactions
        ) throws ValidationException;

        void validateCommit(
            Transaction transaction,
            Map<String, Account> accounts
        ) throws SerializationFailure;
    }

    static final class ReadUncommittedPolicy
        implements IsolationPolicy {

        @Override
        public long read(
            Transaction transaction,
            String accountId,
            Map<String, Account> accounts,
            Map<Long, Transaction> transactions
        ) throws ValidationException {

            requireAccount(accounts, accountId);
            transaction.readSet.add(accountId);

            if (transaction.pendingWrites.containsKey(accountId)) {
                return transaction.pendingWrites.get(accountId);
            }

            for (Transaction other : transactions.values()) {
                if (
                    other.id() != transaction.id()
                    && other.state() == TransactionState.ACTIVE
                    && other.pendingWrites.containsKey(accountId)
                ) {
                    return other.pendingWrites.get(accountId);
                }
            }

            return accounts.get(accountId).balance();
        }

        @Override
        public void validateCommit(
            Transaction transaction,
            Map<String, Account> accounts
        ) {
            // The deliberately weak policy has no snapshot validation.
        }
    }

    static final class ReadCommittedPolicy
        implements IsolationPolicy {

        @Override
        public long read(
            Transaction transaction,
            String accountId,
            Map<String, Account> accounts,
            Map<Long, Transaction> transactions
        ) throws ValidationException {

            requireAccount(accounts, accountId);
            transaction.readSet.add(accountId);

            if (transaction.pendingWrites.containsKey(accountId)) {
                return transaction.pendingWrites.get(accountId);
            }

            return accounts.get(accountId).balance();
        }

        @Override
        public void validateCommit(
            Transaction transaction,
            Map<String, Account> accounts
        ) {
            // Each read is based on currently committed state.
        }
    }

    static final class RepeatableReadPolicy
        implements IsolationPolicy {

        @Override
        public long read(
            Transaction transaction,
            String accountId,
            Map<String, Account> accounts,
            Map<Long, Transaction> transactions
        ) throws ValidationException {

            requireAccount(accounts, accountId);
            transaction.readSet.add(accountId);

            if (transaction.pendingWrites.containsKey(accountId)) {
                return transaction.pendingWrites.get(accountId);
            }

            return transaction.snapshot.get(accountId);
        }

        @Override
        public void validateCommit(
            Transaction transaction,
            Map<String, Account> accounts
        ) throws SerializationFailure {

            for (String accountId : transaction.writeSet) {
                long original = transaction.snapshot.get(accountId);
                long current = accounts.get(accountId).balance();

                if (original != current) {
                    throw new SerializationFailure(
                        "Repeatable-read write conflict on "
                        + accountId
                    );
                }
            }
        }
    }

    static final class SerializablePolicy
        implements IsolationPolicy {

        @Override
        public long read(
            Transaction transaction,
            String accountId,
            Map<String, Account> accounts,
            Map<Long, Transaction> transactions
        ) throws ValidationException {

            requireAccount(accounts, accountId);
            transaction.readSet.add(accountId);

            if (transaction.pendingWrites.containsKey(accountId)) {
                return transaction.pendingWrites.get(accountId);
            }

            return transaction.snapshot.get(accountId);
        }

        @Override
        public void validateCommit(
            Transaction transaction,
            Map<String, Account> accounts
        ) throws SerializationFailure {

            Set<String> observedKeys =
                new HashSet<>(transaction.readSet);

            observedKeys.addAll(transaction.writeSet);

            for (String accountId : observedKeys) {
                long original = transaction.snapshot.get(accountId);
                long current = accounts.get(accountId).balance();

                if (original != current) {
                    throw new SerializationFailure(
                        "Serializable conflict on "
                        + accountId
                        + ": snapshot="
                        + original
                        + ", current="
                        + current
                    );
                }
            }
        }
    }

    static final class TransactionManager {
        private final Map<String, Account> accounts = new HashMap<>();
        private final Map<Long, Transaction> transactions = new HashMap<>();
        private final Map<IsolationLevel, IsolationPolicy> policies =
            new EnumMap<>(IsolationLevel.class);

        private long nextTransactionId = 1;

        TransactionManager(List<Account> initialAccounts) {
            for (Account account : initialAccounts) {
                accounts.put(account.id(), account);
            }

            policies.put(
                IsolationLevel.READ_UNCOMMITTED,
                new ReadUncommittedPolicy()
            );
            policies.put(
                IsolationLevel.READ_COMMITTED,
                new ReadCommittedPolicy()
            );
            policies.put(
                IsolationLevel.REPEATABLE_READ,
                new RepeatableReadPolicy()
            );
            policies.put(
                IsolationLevel.SERIALIZABLE,
                new SerializablePolicy()
            );
        }

        Transaction begin(IsolationLevel isolationLevel) {
            Map<String, Long> snapshot = new HashMap<>();

            for (Account account : accounts.values()) {
                snapshot.put(account.id(), account.balance());
            }

            Transaction transaction =
                new Transaction(
                    nextTransactionId++,
                    isolationLevel,
                    snapshot
                );

            transactions.put(transaction.id(), transaction);
            return transaction;
        }

        long read(
            Transaction transaction,
            String accountId
        ) throws ValidationException {

            requireActive(transaction);

            return policies
                .get(transaction.isolationLevel())
                .read(
                    transaction,
                    accountId,
                    accounts,
                    transactions
                );
        }

        void write(
            Transaction transaction,
            String accountId,
            long newBalance
        ) throws ValidationException {

            requireActive(transaction);
            requireAccount(accounts, accountId);

            if (newBalance < 0) {
                throw new ValidationException(
                    "Negative balances are not permitted"
                );
            }

            transaction.pendingWrites.put(accountId, newBalance);
            transaction.writeSet.add(accountId);
        }

        void commit(Transaction transaction)
            throws ValidationException, SerializationFailure {

            requireActive(transaction);

            policies
                .get(transaction.isolationLevel())
                .validateCommit(transaction, accounts);

            for (
                Map.Entry<String, Long> entry :
                transaction.pendingWrites.entrySet()
            ) {
                Account current = accounts.get(entry.getKey());

                accounts.put(
                    entry.getKey(),
                    current.withBalance(entry.getValue())
                );
            }

            transaction.commitState();
        }

        void rollback(Transaction transaction)
            throws ValidationException {

            requireActive(transaction);
            transaction.abortState();
        }

        Map<String, Account> accounts() {
            return Map.copyOf(accounts);
        }

        private void requireActive(Transaction transaction)
            throws ValidationException {

            if (transaction.state() != TransactionState.ACTIVE) {
                throw new ValidationException(
                    "Transaction is "
                    + transaction.state()
                );
            }
        }

        private static void requireAccount(
            Map<String, Account> accounts,
            String accountId
        ) throws ValidationException {

            if (!accounts.containsKey(accountId)) {
                throw new ValidationException(
                    "Unknown account: " + accountId
                );
            }
        }
    }

    static final class PaymentService {
        private final TransactionManager manager;

        PaymentService(TransactionManager manager) {
            this.manager = manager;
        }

        void transfer(
            String source,
            String destination,
            long amount
        ) throws Exception {

            if (source.equals(destination)) {
                throw new ValidationException(
                    "Source and destination must differ"
                );
            }

            if (amount <= 0) {
                throw new ValidationException(
                    "Transfer amount must be positive"
                );
            }

            Transaction transaction =
                manager.begin(IsolationLevel.SERIALIZABLE);

            try {
                long sourceBalance =
                    manager.read(transaction, source);

                long destinationBalance =
                    manager.read(transaction, destination);

                if (sourceBalance < amount) {
                    throw new ValidationException(
                        "Insufficient funds"
                    );
                }

                manager.write(
                    transaction,
                    source,
                    sourceBalance - amount
                );

                manager.write(
                    transaction,
                    destination,
                    destinationBalance + amount
                );

                manager.commit(transaction);

                System.out.println(
                    "Committed transfer in transaction "
                    + transaction.id()
                );
            } catch (Exception error) {
                if (transaction.state() == TransactionState.ACTIVE) {
                    manager.rollback(transaction);
                }
                throw error;
            }
        }
    }

    private static void dirtyReadScenario() throws Exception {
        System.out.println("\n=== Dirty Read ===");

        TransactionManager manager =
            new TransactionManager(
                List.of(new Account("A-100", "Asha", 1000))
            );

        Transaction writer =
            manager.begin(IsolationLevel.READ_COMMITTED);

        Transaction reader =
            manager.begin(IsolationLevel.READ_UNCOMMITTED);

        manager.write(writer, "A-100", 250);

        long dirtyValue =
            manager.read(reader, "A-100");

        System.out.println(
            "Uncommitted value observed: " + dirtyValue
        );

        manager.rollback(writer);

        System.out.println(
            "Value after writer rollback: "
            + manager.read(reader, "A-100")
        );

        manager.rollback(reader);
    }

    private static void readCommittedScenario() throws Exception {
        System.out.println("\n=== READ COMMITTED ===");

        TransactionManager manager =
            new TransactionManager(
                List.of(new Account("A-100", "Asha", 1000))
            );

        Transaction reader =
            manager.begin(IsolationLevel.READ_COMMITTED);

        Transaction writer =
            manager.begin(IsolationLevel.READ_COMMITTED);

        long first =
            manager.read(reader, "A-100");

        manager.write(writer, "A-100", 1400);
        manager.commit(writer);

        long second =
            manager.read(reader, "A-100");

        System.out.println(
            "First read=" + first
            + ", second read=" + second
        );

        manager.rollback(reader);
    }

    private static void repeatableReadScenario() throws Exception {
        System.out.println("\n=== REPEATABLE READ ===");

        TransactionManager manager =
            new TransactionManager(
                List.of(new Account("A-100", "Asha", 1000))
            );

        Transaction reader =
            manager.begin(IsolationLevel.REPEATABLE_READ);

        Transaction writer =
            manager.begin(IsolationLevel.READ_COMMITTED);

        long first =
            manager.read(reader, "A-100");

        manager.write(writer, "A-100", 1800);
        manager.commit(writer);

        long second =
            manager.read(reader, "A-100");

        System.out.println(
            "Snapshot reads=" + first
            + " then " + second
        );

        manager.rollback(reader);
    }

    private static void serializableScenario() throws Exception {
        System.out.println("\n=== SERIALIZABLE ===");

        TransactionManager manager =
            new TransactionManager(
                List.of(
                    new Account("A-100", "Asha", 1000),
                    new Account("B-100", "Bharat", 1000)
                )
            );

        Transaction first =
            manager.begin(IsolationLevel.SERIALIZABLE);

        Transaction second =
            manager.begin(IsolationLevel.SERIALIZABLE);

        long total =
            manager.read(first, "A-100")
            + manager.read(first, "B-100");

        manager.write(second, "A-100", 1600);
        manager.commit(second);

        manager.write(first, "B-100", 2200);

        System.out.println(
            "Transaction first observed total=" + total
        );

        try {
            manager.commit(first);
        } catch (SerializationFailure error) {
            first.abortState();

            System.out.println(
                "Serialization failure: "
                + error.getMessage()
            );
        }
    }

    private static void printAccounts(
        Map<String, Account> accounts
    ) {
        accounts.values()
            .stream()
            .sorted((left, right) ->
                left.id().compareTo(right.id())
            )
            .forEach(account ->
                System.out.println(
                    account.id()
                    + " | "
                    + account.owner()
                    + " | balance="
                    + account.balance()
                )
            );
    }

    public static void main(String[] args) {
        try {
            System.out.println(
                "Enterprise Transaction Isolation Model"
            );

            dirtyReadScenario();
            readCommittedScenario();
            repeatableReadScenario();
            serializableScenario();

            System.out.println(
                "\n=== Enterprise Payment Workflow ==="
            );

            TransactionManager manager =
                new TransactionManager(
                    new ArrayList<>(
                        List.of(
                            new Account("A-100", "Asha", 5000),
                            new Account("B-100", "Bharat", 1500)
                        )
                    )
                );

            PaymentService paymentService =
                new PaymentService(manager);

            paymentService.transfer(
                "A-100",
                "B-100",
                750
            );

            printAccounts(manager.accounts());

            System.out.println(
                "\nThe domain model separates isolation policy "
                + "from transaction orchestration. This allows "
                + "visibility rules, conflict detection, and "
                + "business validation to remain independently testable."
            );
        } catch (Exception error) {
            System.err.println(
                "Application failure: "
                + error.getMessage()
            );
        }
    }
}
