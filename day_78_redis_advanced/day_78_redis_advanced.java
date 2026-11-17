import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Function;
import java.util.stream.Collectors;

/*
 * Redis Advanced Enterprise Governance Model
 *
 * Java 17
 *
 * Implements:
 * - Pipeline execution
 * - Transaction execution
 * - Atomic script evaluation
 * - Distributed lease locking
 * - Fencing tokens
 * - Inventory reservation
 * - Policy validation
 *
 * This is an executable in-memory domain model.
 * It demonstrates Redis execution semantics without
 * requiring an external Redis server.
 */

public class RedisAdvanced {

    // --------------------------------------------------
    // Exceptions
    // --------------------------------------------------

    static class RedisException extends RuntimeException {
        RedisException(String message) {
            super(message);
        }
    }

    static class ValidationException extends RedisException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class LockException extends RedisException {
        LockException(String message) {
            super(message);
        }
    }

    // --------------------------------------------------
    // Domain enums
    // --------------------------------------------------

    enum OperationType {
        READ,
        WRITE,
        INCREMENT,
        DELETE,
        SCRIPT
    }

    enum LockStatus {
        ACQUIRED,
        BUSY,
        RELEASED,
        NOT_OWNER
    }

    enum TransactionState {
        CREATED,
        QUEUED,
        EXECUTED,
        FAILED
    }

    // --------------------------------------------------
    // Immutable command model
    // --------------------------------------------------

    record RedisCommand(
        OperationType type,
        String key,
        String value,
        long amount
    ) {
        RedisCommand {
            Objects.requireNonNull(type);
            Objects.requireNonNull(key);

            if (key.isBlank()) {
                throw new ValidationException(
                    "Redis key cannot be empty"
                );
            }
        }

        static RedisCommand set(String key, String value) {
            return new RedisCommand(
                OperationType.WRITE,
                key,
                Objects.requireNonNull(value),
                0
            );
        }

        static RedisCommand get(String key) {
            return new RedisCommand(
                OperationType.READ,
                key,
                null,
                0
            );
        }

        static RedisCommand increment(
            String key,
            long amount
        ) {
            return new RedisCommand(
                OperationType.INCREMENT,
                key,
                null,
                amount
            );
        }

        static RedisCommand delete(String key) {
            return new RedisCommand(
                OperationType.DELETE,
                key,
                null,
                0
            );
        }
    }

    // --------------------------------------------------
    // Command result
    // --------------------------------------------------

    record CommandResult(
        boolean success,
        String value,
        String error
    ) {
        static CommandResult success(String value) {
            return new CommandResult(true, value, null);
        }

        static CommandResult failure(String error) {
            return new CommandResult(false, null, error);
        }
    }

    // --------------------------------------------------
    // Redis storage engine
    // --------------------------------------------------

    static class RedisStore {

        private record Entry(
            String value,
            long expiresAt
        ) {}

        private final Map<String, Entry> storage =
            new ConcurrentHashMap<>();

        private final AtomicLong fencingSequence =
            new AtomicLong();

        private static long now() {
            return System.nanoTime();
        }

        private void purge(String key) {
            Entry entry = storage.get(key);

            if (entry != null &&
                entry.expiresAt() != Long.MAX_VALUE &&
                now() >= entry.expiresAt()) {
                storage.remove(key, entry);
            }
        }

        public void set(String key, String value) {
            Objects.requireNonNull(value);

            storage.put(
                key,
                new Entry(value, Long.MAX_VALUE)
            );
        }

        public boolean setNX(
            String key,
            String value,
            Duration lease
        ) {
            validateLease(lease);

            purge(key);

            long expiresAt = Math.addExact(
                now(),
                lease.toNanos()
            );

            return storage.putIfAbsent(
                key,
                new Entry(value, expiresAt)
            ) == null;
        }

        public Optional<String> get(String key) {
            purge(key);

            Entry entry = storage.get(key);

            return entry == null
                ? Optional.empty()
                : Optional.of(entry.value());
        }

        public long incrementBy(
            String key,
            long amount
        ) {
            return storage.compute(key, (ignored, entry) -> {
                long current = 0;

                if (entry != null) {
                    if (entry.expiresAt() != Long.MAX_VALUE &&
                        now() >= entry.expiresAt()) {
                        entry = null;
                    }
                }

                if (entry != null) {
                    try {
                        current = Long.parseLong(entry.value());
                    } catch (NumberFormatException exception) {
                        throw new ValidationException(
                            "Stored value is not numeric"
                        );
                    }
                }

                long updated = Math.addExact(current, amount);

                return new Entry(updated + "",
                    Long.MAX_VALUE);
            }).expiresAt() == Long.MAX_VALUE
                ? Long.parseLong(get(key).orElseThrow())
                : 0;
        }

        public boolean delete(String key) {
            purge(key);
            return storage.remove(key) != null;
        }

        public boolean compareAndDelete(
            String key,
            String token
        ) {
            purge(key);

            Entry entry = storage.get(key);

            if (entry == null || !entry.value().equals(token)) {
                return false;
            }

            return storage.remove(key, entry);
        }

        public long nextFencingToken() {
            return fencingSequence.incrementAndGet();
        }

        public static void validateLease(Duration lease) {
            Objects.requireNonNull(lease);

            if (lease.isZero() || lease.isNegative()) {
                throw new ValidationException(
                    "Lease must be positive"
                );
            }
        }

        public int size() {
            return storage.size();
        }
    }

    // --------------------------------------------------
    // Pipeline service
    // --------------------------------------------------

    static class PipelineService {

        private final RedisStore store;
        private final List<RedisCommand> commands =
            new ArrayList<>();

        PipelineService(RedisStore store) {
            this.store = store;
        }

        public PipelineService add(RedisCommand command) {
            commands.add(Objects.requireNonNull(command));
            return this;
        }

        public List<CommandResult> execute() {
            List<CommandResult> results = new ArrayList<>();

            for (RedisCommand command : commands) {
                try {
                    results.add(
                        CommandExecutor.execute(store, command)
                    );
                } catch (RuntimeException exception) {
                    results.add(
                        CommandResult.failure(exception.getMessage())
                    );
                }
            }

            commands.clear();

            return List.copyOf(results);
        }
    }

    // --------------------------------------------------
    // Command executor
    // --------------------------------------------------

    static class CommandExecutor {

        static CommandResult execute(
            RedisStore store,
            RedisCommand command
        ) {
            return switch (command.type()) {
                case READ -> CommandResult.success(
                    store.get(command.key()).orElse("nil")
                );

                case WRITE -> {
                    store.set(command.key(), command.value());
                    yield CommandResult.success("OK");
                }

                case INCREMENT -> CommandResult.success(
                    Long.toString(
                        store.incrementBy(
                            command.key(),
                            command.amount()
                        )
                    )
                );

                case DELETE -> CommandResult.success(
                    store.delete(command.key())
                        ? "1"
                        : "0"
                );

                case SCRIPT -> throw new ValidationException(
                    "Script commands require ScriptService"
                );
            };
        }
    }

    // --------------------------------------------------
    // Transaction service
    // --------------------------------------------------

    static class TransactionService {

        private final RedisStore store;
        private final List<RedisCommand> commands =
            new ArrayList<>();

        private TransactionState state =
            TransactionState.CREATED;

        TransactionService(RedisStore store) {
            this.store = store;
        }

        public synchronized void queue(RedisCommand command) {
            if (state == TransactionState.EXECUTED ||
                state == TransactionState.FAILED) {
                throw new RedisException(
                    "Transaction is already completed"
                );
            }

            commands.add(command);
            state = TransactionState.QUEUED;
        }

        public synchronized List<CommandResult> execute() {
            if (state == TransactionState.EXECUTED) {
                throw new RedisException(
                    "Transaction cannot execute twice"
                );
            }

            List<CommandResult> results = new ArrayList<>();

            /*
             * The synchronized method prevents interleaving
             * among callers using this transaction object.
             *
             * A production Redis transaction obtains atomicity
             * from MULTI/EXEC on the Redis server.
             */

            for (RedisCommand command : commands) {
                try {
                    results.add(
                        CommandExecutor.execute(store, command)
                    );
                } catch (RuntimeException exception) {
                    results.add(
                        CommandResult.failure(exception.getMessage())
                    );
                }
            }

            state = TransactionState.EXECUTED;

            return List.copyOf(results);
        }

        public TransactionState state() {
            return state;
        }
    }

    // --------------------------------------------------
    // Script service
    // --------------------------------------------------

    interface AtomicScript<T> {
        T execute(RedisStore store);
    }

    static class ScriptService {

        private final RedisStore store;

        ScriptService(RedisStore store) {
            this.store = store;
        }

        public synchronized <T> T execute(
            AtomicScript<T> script
        ) {
            return script.execute(store);
        }

        public long reserveInventory(
            String inventoryKey,
            String reservationKey,
            long quantity
        ) {
            if (quantity <= 0) {
                return -1;
            }

            return execute(engine -> {
                long stock = Long.parseLong(
                    engine.get(inventoryKey).orElse("0")
                );

                if (stock < quantity) {
                    return 0L;
                }

                long remaining = engine.incrementBy(
                    inventoryKey,
                    -quantity
                );

                engine.set(
                    reservationKey,
                    quantity + ":reserved"
                );

                return remaining;
            });
        }
    }

    // --------------------------------------------------
    // Approval policy
    // --------------------------------------------------

    record ReviewPolicy(
        int requiredApprovals,
        Set<String> eligibleReviewers,
        boolean rejectAuthorApproval
    ) {
        ReviewPolicy {
            if (requiredApprovals < 1) {
                throw new ValidationException(
                    "At least one approval is required"
                );
            }

            eligibleReviewers = Set.copyOf(
                eligibleReviewers
            );
        }
    }

    static class ApprovalService {

        private final ReviewPolicy policy;

        ApprovalService(ReviewPolicy policy) {
            this.policy = policy;
        }

        public boolean isEligible(
            String author,
            String reviewer
        ) {
            if (policy.rejectAuthorApproval() &&
                author.equals(reviewer)) {
                return false;
            }

            return policy.eligibleReviewers().contains(reviewer);
        }

        public boolean approved(
            String author,
            Set<String> approvedReviewers
        ) {
            long valid = approvedReviewers.stream()
                .filter(reviewer -> isEligible(author, reviewer))
                .distinct()
                .count();

            return valid >= policy.requiredApprovals();
        }
    }

    // --------------------------------------------------
    // Distributed lock service
    // --------------------------------------------------

    record LockResult(
        LockStatus status,
        String token,
        long fencingToken
    ) {}

    static class DistributedLock {

        private final RedisStore store;
        private final String key;
        private final Duration lease;

        private String token;
        private long fencingToken;

        DistributedLock(
            RedisStore store,
            String key,
            Duration lease
        ) {
            this.store = store;
            this.key = key;
            this.lease = lease;

            RedisStore.validateLease(lease);
        }

        public synchronized LockResult acquire() {
            if (token != null) {
                throw new LockException(
                    "Lock instance already has an owner token"
                );
            }

            String candidate = UUID.randomUUID().toString();

            if (!store.setNX(key, candidate, lease)) {
                return new LockResult(
                    LockStatus.BUSY,
                    null,
                    0
                );
            }

            token = candidate;
            fencingToken = store.nextFencingToken();

            return new LockResult(
                LockStatus.ACQUIRED,
                token,
                fencingToken
            );
        }

        public synchronized LockStatus release() {
            if (token == null) {
                return LockStatus.NOT_OWNER;
            }

            boolean released = store.compareAndDelete(
                key,
                token
            );

            token = null;

            return released
                ? LockStatus.RELEASED
                : LockStatus.NOT_OWNER;
        }

        public long fencingToken() {
            return fencingToken;
        }
    }

    // --------------------------------------------------
    // Fencing-protected enterprise resource
    // --------------------------------------------------

    static class ProtectedResource {

        private long lastAcceptedToken;
        private String state = "UNINITIALIZED";

        public synchronized boolean update(
            long token,
            String newState
        ) {
            if (token <= lastAcceptedToken) {
                return false;
            }

            lastAcceptedToken = token;
            state = newState;

            return true;
        }

        public String state() {
            return state;
        }
    }

    // --------------------------------------------------
    // Enterprise workflow
    // --------------------------------------------------

    static class RepositoryWorkflow {

        private final RedisStore redis;
        private final ApprovalService approvals;

        RepositoryWorkflow(
            RedisStore redis,
            ApprovalService approvals
        ) {
            this.redis = redis;
            this.approvals = approvals;
        }

        public boolean process(
            String author,
            Set<String> reviewers,
            boolean checksPassed
        ) {
            if (!approvals.approved(author, reviewers)) {
                return false;
            }

            if (!checksPassed) {
                return false;
            }

            redis.set(
                "repository:last_merge",
                "approved-and-validated"
            );

            return true;
        }
    }

    // --------------------------------------------------
    // Main demonstration
    // --------------------------------------------------

    public static void main(String[] args) {

        RedisStore redis = new RedisStore();

        System.out.println("REDIS ADVANCED ENTERPRISE MODEL");

        // Pipeline.
        PipelineService pipeline =
            new PipelineService(redis);

        List<CommandResult> pipelineResults = pipeline
            .add(RedisCommand.set("requests", "100"))
            .add(RedisCommand.increment("requests", 50))
            .add(RedisCommand.get("requests"))
            .execute();

        System.out.println("\nPIPELINE");

        pipelineResults.forEach(System.out::println);

        // Transaction.
        TransactionService transaction =
            new TransactionService(redis);

        transaction.queue(
            RedisCommand.set("wallet:A", "1000")
        );

        transaction.queue(
            RedisCommand.set("wallet:B", "500")
        );

        transaction.queue(
            RedisCommand.increment("wallet:A", -100)
        );

        transaction.queue(
            RedisCommand.increment("wallet:B", 100)
        );

        System.out.println("\nTRANSACTION");

        transaction.execute().forEach(System.out::println);

        System.out.println(
            "Transaction state: " + transaction.state()
        );

        // Lua-style script.
        redis.set("inventory:laptop", "20");

        ScriptService scripts = new ScriptService(redis);

        long remaining = scripts.reserveInventory(
            "inventory:laptop",
            "reservation:ORDER-1001",
            5
        );

        System.out.println("\nLUA SCRIPT");

        System.out.println("Remaining inventory: " + remaining);

        // Approval policy.
        ReviewPolicy policy = new ReviewPolicy(
            2,
            Set.of("reviewer-A", "reviewer-B", "reviewer-C"),
            true
        );

        ApprovalService approvalService =
            new ApprovalService(policy);

        System.out.println("\nAPPROVAL POLICY");

        System.out.println(
            "Approved: " +
            approvalService.approved(
                "developer-A",
                Set.of("reviewer-A", "reviewer-B")
            )
        );

        // Distributed locks.
        System.out.println("\nDISTRIBUTED LOCKS");

        DistributedLock workerA = new DistributedLock(
            redis,
            "locks:payment",
            Duration.ofSeconds(5)
        );

        DistributedLock workerB = new DistributedLock(
            redis,
            "locks:payment",
            Duration.ofSeconds(5)
        );

        LockResult resultA = workerA.acquire();
        LockResult resultB = workerB.acquire();

        System.out.println("Worker A: " + resultA.status());
        System.out.println("Worker B: " + resultB.status());

        // Fencing.
        ProtectedResource resource = new ProtectedResource();

        boolean accepted = resource.update(
            resultA.fencingToken(),
            "PAYMENT_COMPLETED"
        );

        boolean staleAccepted = resource.update(
            resultA.fencingToken(),
            "STALE_UPDATE"
        );

        System.out.println("\nFENCING");

        System.out.println("Accepted: " + accepted);
        System.out.println("Stale accepted: " + staleAccepted);

        System.out.println(
            "Release: " + workerA.release()
        );

        // Integrated repository workflow.
        RepositoryWorkflow workflow = new RepositoryWorkflow(
            redis,
            approvalService
        );

        System.out.println("\nENTERPRISE WORKFLOW");

        System.out.println(
            "Merge eligible: " +
            workflow.process(
                "developer-A",
                Set.of("reviewer-A", "reviewer-B"),
                true
            )
        );

        System.out.println(
            "\nStored Redis keys: " + redis.size()
        );
    }
}
