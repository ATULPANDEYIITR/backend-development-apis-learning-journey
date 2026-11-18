import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.PriorityBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.LongAdder;
import java.util.function.Function;
import java.util.stream.Collectors;

/*
 * Enterprise Background Task Management System
 *
 * Java 17
 *
 * Includes:
 * - Immutable task definitions.
 * - Explicit task lifecycle transitions.
 * - Asynchronous worker execution.
 * - Priority scheduling.
 * - Retry and failure policies.
 * - Dependency management.
 * - Idempotency.
 * - Dead-letter processing.
 * - Enterprise metrics.
 * - Graceful executor shutdown.
 */

// ============================================================
// 1. DOMAIN EXCEPTIONS
// ============================================================

class TaskException extends RuntimeException {
    TaskException(String message) {
        super(message);
    }

    TaskException(String message, Throwable cause) {
        super(message, cause);
    }
}

class PermanentTaskException extends TaskException {
    PermanentTaskException(String message) {
        super(message);
    }
}

class InvalidTaskStateException extends TaskException {
    InvalidTaskStateException(String message) {
        super(message);
    }
}

// ============================================================
// 2. DOMAIN ENUMS
// ============================================================

enum TaskStatus {
    PENDING,
    QUEUED,
    RUNNING,
    RETRY_WAIT,
    COMPLETED,
    FAILED,
    DEAD_LETTER,
    CANCELLED
}

enum TaskPriority {
    CRITICAL(1),
    HIGH(3),
    NORMAL(5),
    LOW(8);

    private final int weight;

    TaskPriority(int weight) {
        this.weight = weight;
    }

    public int weight() {
        return weight;
    }
}

enum FailureDisposition {
    RETRY,
    DEAD_LETTER
}

// ============================================================
// 3. RETRY POLICY
// ============================================================

record RetryPolicy(
    int maxAttempts,
    long initialDelayMillis,
    long maxDelayMillis,
    double multiplier
) {
    public RetryPolicy {
        if (maxAttempts < 1 ||
            initialDelayMillis < 0 ||
            maxDelayMillis < 0 ||
            multiplier < 1.0) {
            throw new IllegalArgumentException(
                "Invalid retry policy."
            );
        }
    }

    public long delayFor(int attempt) {
        double delay = initialDelayMillis *
            Math.pow(multiplier, Math.max(0, attempt - 1));

        return Math.min((long) delay, maxDelayMillis);
    }
}

// ============================================================
// 4. TASK DEFINITION
// ============================================================

record TaskDefinition(
    String type,
    Map<String, String> payload,
    TaskPriority priority,
    RetryPolicy retryPolicy,
    String idempotencyKey,
    Set<String> dependencies,
    Instant scheduledAt
) {
    public TaskDefinition {
        if (type == null || type.isBlank() || type.length() > 100) {
            throw new IllegalArgumentException("Invalid task type.");
        }

        payload = Map.copyOf(Objects.requireNonNull(payload));
        dependencies = Set.copyOf(
            Objects.requireNonNull(dependencies)
        );

        Objects.requireNonNull(priority);
        Objects.requireNonNull(retryPolicy);
        Objects.requireNonNull(scheduledAt);
    }
}

// ============================================================
// 5. TASK ENTITY
// ============================================================

final class Task {

    private final String id;
    private final TaskDefinition definition;
    private final Instant createdAt;

    private TaskStatus status;
    private int attempts;
    private String workerId;
    private String error;
    private String result;
    private Instant completedAt;
    private long version;

    Task(TaskDefinition definition) {
        this.id = UUID.randomUUID().toString();
        this.definition = definition;
        this.createdAt = Instant.now();
        this.status = TaskStatus.PENDING;
        this.attempts = 0;
        this.version = 0;
    }

    public synchronized void transition(TaskStatus next) {
        boolean valid = switch (status) {
            case PENDING ->
                next == TaskStatus.QUEUED ||
                next == TaskStatus.CANCELLED;

            case QUEUED ->
                next == TaskStatus.RUNNING ||
                next == TaskStatus.CANCELLED;

            case RUNNING ->
                next == TaskStatus.COMPLETED ||
                next == TaskStatus.RETRY_WAIT ||
                next == TaskStatus.FAILED ||
                next == TaskStatus.DEAD_LETTER;

            case RETRY_WAIT ->
                next == TaskStatus.QUEUED ||
                next == TaskStatus.CANCELLED ||
                next == TaskStatus.DEAD_LETTER;

            case FAILED ->
                next == TaskStatus.QUEUED ||
                next == TaskStatus.DEAD_LETTER;

            default -> false;
        };

        if (!valid) {
            throw new InvalidTaskStateException(
                "Invalid transition: " + status + " -> " + next
            );
        }

        status = next;
        version++;
    }

    public synchronized void begin(String worker) {
        transition(TaskStatus.RUNNING);
        attempts++;
        workerId = worker;
    }

    public synchronized void complete(String output) {
        result = output;
        completedAt = Instant.now();
        transition(TaskStatus.COMPLETED);
    }

    public synchronized void fail(String message) {
        error = message;
    }

    public synchronized void prepareRetry() {
        transition(TaskStatus.RETRY_WAIT);
    }

    public synchronized void clearError() {
        error = null;
    }

    public String id() {
        return id;
    }

    public TaskDefinition definition() {
        return definition;
    }

    public synchronized TaskStatus status() {
        return status;
    }

    public synchronized int attempts() {
        return attempts;
    }

    public synchronized String result() {
        return result;
    }

    public synchronized String error() {
        return error;
    }

    public synchronized String workerId() {
        return workerId;
    }

    public synchronized long version() {
        return version;
    }

    public Instant createdAt() {
        return createdAt;
    }

    public synchronized Instant completedAt() {
        return completedAt;
    }
}

// ============================================================
// 6. TASK HANDLER CONTRACT
// ============================================================

@FunctionalInterface
interface TaskHandler {
    String execute(Map<String, String> payload) throws Exception;
}

final class HandlerRegistry {

    private final Map<String, TaskHandler> handlers =
        new ConcurrentHashMap<>();

    public void register(String type, TaskHandler handler) {
        Objects.requireNonNull(handler);

        if (type == null || type.isBlank()) {
            throw new IllegalArgumentException("Invalid task type.");
        }

        if (handlers.putIfAbsent(type, handler) != null) {
            throw new TaskException("Duplicate handler: " + type);
        }
    }

    public TaskHandler get(String type) {
        TaskHandler handler = handlers.get(type);

        if (handler == null) {
            throw new TaskException(
                "No registered handler for " + type
            );
        }

        return handler;
    }
}

// ============================================================
// 7. PRIORITY QUEUE
// ============================================================

record QueueEntry(
    String taskId,
    int priority,
    long sequence
) implements Comparable<QueueEntry> {

    @Override
    public int compareTo(QueueEntry other) {
        int comparison = Integer.compare(
            priority,
            other.priority
        );

        if (comparison != 0) {
            return comparison;
        }

        return Long.compare(sequence, other.sequence);
    }
}

final class TaskQueue {

    private final BlockingQueue<QueueEntry> queue =
        new PriorityBlockingQueue<>();

    private final AtomicInteger sequence = new AtomicInteger();

    public void enqueue(Task task) {
        queue.offer(new QueueEntry(
            task.id(),
            task.definition().priority().weight(),
            sequence.getAndIncrement()
        ));
    }

    public Optional<String> poll(long timeoutMillis)
        throws InterruptedException {

        QueueEntry entry = queue.poll(
            timeoutMillis,
            TimeUnit.MILLISECONDS
        );

        return Optional.ofNullable(
            entry == null ? null : entry.taskId()
        );
    }

    public int size() {
        return queue.size();
    }
}

// ============================================================
// 8. FAILURE POLICY
// ============================================================

final class FailurePolicy {

    public FailureDisposition evaluate(
        Task task,
        Exception error
    ) {
        if (error instanceof PermanentTaskException) {
            return FailureDisposition.DEAD_LETTER;
        }

        if (
            task.attempts() >=
            task.definition().retryPolicy().maxAttempts()
        ) {
            return FailureDisposition.DEAD_LETTER;
        }

        return FailureDisposition.RETRY;
    }
}

// ============================================================
// 9. TASK REPOSITORY
// ============================================================

final class TaskRepository {

    private final Map<String, Task> tasks =
        new ConcurrentHashMap<>();

    private final Map<String, String> idempotency =
        new ConcurrentHashMap<>();

    public synchronized Task save(Task task) {
        String key = task.definition().idempotencyKey();

        if (key != null && !key.isBlank()) {
            String existingId = idempotency.get(key);

            if (existingId != null) {
                return get(existingId);
            }
        }

        for (String dependency : task.definition().dependencies()) {
            if (!tasks.containsKey(dependency)) {
                throw new TaskException(
                    "Unknown dependency: " + dependency
                );
            }
        }

        tasks.put(task.id(), task);

        if (key != null && !key.isBlank()) {
            idempotency.put(key, task.id());
        }

        return task;
    }

    public Task get(String id) {
        Task task = tasks.get(id);

        if (task == null) {
            throw new TaskException("Task not found: " + id);
        }

        return task;
    }

    public List<Task> all() {
        return new ArrayList<>(tasks.values());
    }

    public boolean dependenciesCompleted(Task task) {
        return task.definition().dependencies()
            .stream()
            .map(this::get)
            .allMatch(t -> t.status() == TaskStatus.COMPLETED);
    }
}

// ============================================================
// 10. OPERATIONAL METRICS
// ============================================================

final class TaskMetrics {

    private final LongAdder submitted = new LongAdder();
    private final LongAdder completed = new LongAdder();
    private final LongAdder failed = new LongAdder();
    private final LongAdder retried = new LongAdder();
    private final LongAdder deadLettered = new LongAdder();

    void submitted() { submitted.increment(); }
    void completed() { completed.increment(); }
    void failed() { failed.increment(); }
    void retried() { retried.increment(); }
    void deadLettered() { deadLettered.increment(); }

    public Map<String, Long> snapshot() {
        return Map.of(
            "submitted", submitted.sum(),
            "completed", completed.sum(),
            "failed", failed.sum(),
            "retried", retried.sum(),
            "deadLettered", deadLettered.sum()
        );
    }
}

// ============================================================
// 11. BACKGROUND TASK SERVICE
// ============================================================

final class BackgroundTaskService implements AutoCloseable {

    private final TaskRepository repository = new TaskRepository();
    private final TaskQueue queue = new TaskQueue();
    private final HandlerRegistry handlers = new HandlerRegistry();
    private final FailurePolicy failurePolicy = new FailurePolicy();
    private final TaskMetrics metrics = new TaskMetrics();

    private final Set<String> deadLetters =
        ConcurrentHashMap.newKeySet();

    private final ExecutorService scheduler =
        Executors.newSingleThreadExecutor();

    private final ExecutorService workers;

    private final AtomicBoolean accepting =
        new AtomicBoolean(true);

    private final AtomicBoolean started =
        new AtomicBoolean(false);

    private final int workerCount;

    BackgroundTaskService(int workerCount) {
        if (workerCount < 1 || workerCount > 100) {
            throw new IllegalArgumentException(
                "Invalid worker count."
            );
        }

        this.workerCount = workerCount;
        this.workers = Executors.newFixedThreadPool(workerCount);
    }

    public void register(String type, TaskHandler handler) {
        handlers.register(type, handler);
    }

    public Task submit(TaskDefinition definition) {
        if (!accepting.get()) {
            throw new TaskException("Service is shutting down.");
        }

        Task task = new Task(definition);
        Task stored = repository.save(task);

        if (stored != task) {
            return stored;
        }

        metrics.submitted();

        if (!definition.scheduledAt().isAfter(Instant.now())) {
            enqueue(task);
        }

        return task;
    }

    private void enqueue(Task task) {
        if (!accepting.get()) return;

        TaskStatus state = task.status();

        if (
            state != TaskStatus.PENDING &&
            state != TaskStatus.RETRY_WAIT
        ) {
            return;
        }

        if (!repository.dependenciesCompleted(task)) {
            return;
        }

        task.transition(TaskStatus.QUEUED);
        queue.enqueue(task);
    }

    public void start() {
        if (!started.compareAndSet(false, true)) {
            throw new TaskException("Service already started.");
        }

        scheduler.submit(() -> {
            while (accepting.get()) {
                try {
                    scheduleDueTasks();
                    dispatchAvailable();
                    Thread.sleep(20);
                } catch (InterruptedException error) {
                    Thread.currentThread().interrupt();
                    break;
                } catch (RuntimeException error) {
                    System.err.println(
                        "Scheduler error: " + error.getMessage()
                    );
                }
            }
        });
    }

    private void scheduleDueTasks() {
        Instant now = Instant.now();

        for (Task task : repository.all()) {
            if (
                !task.definition().scheduledAt().isAfter(now) &&
                (
                    task.status() == TaskStatus.PENDING ||
                    task.status() == TaskStatus.RETRY_WAIT
                )
            ) {
                enqueue(task);
            }
        }
    }

    private void dispatchAvailable() {
        for (int i = 0; i < workerCount; i++) {
            Optional<String> next;

            try {
                next = queue.poll(0);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
                return;
            }

            if (next.isEmpty()) return;

            String taskId = next.get();

            workers.submit(() -> execute(taskId));
        }
    }

    private void execute(String taskId) {
        Task task = repository.get(taskId);

        if (task.status() != TaskStatus.QUEUED) {
            return;
        }

        if (!repository.dependenciesCompleted(task)) {
            return;
        }

        String worker = Thread.currentThread().getName();

        task.begin(worker);

        try {
            TaskHandler handler =
                handlers.get(task.definition().type());

            String result = handler.execute(
                task.definition().payload()
            );

            task.complete(result);
            metrics.completed();

            // A successful dependency may unblock waiting tasks.
            scheduleDueTasks();

        } catch (Exception error) {
            handleFailure(task, error);
        }
    }

    private void handleFailure(Task task, Exception error) {
        task.fail(error.getMessage());

        FailureDisposition disposition =
            failurePolicy.evaluate(task, error);

        if (disposition == FailureDisposition.DEAD_LETTER) {
            task.transition(TaskStatus.DEAD_LETTER);

            deadLetters.add(task.id());
            metrics.failed();
            metrics.deadLettered();

            return;
        }

        task.prepareRetry();
        metrics.retried();

        long delay = task.definition()
            .retryPolicy()
            .delayFor(task.attempts());

        // Scheduled retry is kept outside the worker thread.
        scheduler.submit(() -> {
            try {
                Thread.sleep(delay);

                if (accepting.get()) {
                    enqueue(task);
                }
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
            }
        });
    }

    public void cancel(String taskId) {
        Task task = repository.get(taskId);

        if (
            task.status() != TaskStatus.PENDING &&
            task.status() != TaskStatus.QUEUED &&
            task.status() != TaskStatus.RETRY_WAIT
        ) {
            throw new InvalidTaskStateException(
                "Task cannot be cancelled."
            );
        }

        task.transition(TaskStatus.CANCELLED);
    }

    public List<Task> deadLetterTasks() {
        return deadLetters.stream()
            .map(repository::get)
            .collect(Collectors.toUnmodifiableList());
    }

    public Map<String, Long> report() {
        Map<String, Long> states = repository.all()
            .stream()
            .collect(Collectors.groupingBy(
                task -> task.status().name(),
                Collectors.counting()
            ));

        System.out.println("TASK STATES: " + states);

        return metrics.snapshot();
    }

    @Override
    public void close() {
        if (!accepting.compareAndSet(true, false)) return;

        scheduler.shutdown();

        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }

            workers.shutdown();

            if (!workers.awaitTermination(10, TimeUnit.SECONDS)) {
                workers.shutdownNow();
            }

        } catch (InterruptedException error) {
            scheduler.shutdownNow();
            workers.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    public TaskRepository repository() {
        return repository;
    }
}

// ============================================================
// 12. EXECUTABLE ENTERPRISE SCENARIO
// ============================================================

public class BackgroundTasks {

    private static TaskDefinition definition(
        String type,
        Map<String, String> payload,
        TaskPriority priority,
        String idempotencyKey,
        Set<String> dependencies
    ) {
        return new TaskDefinition(
            type,
            payload,
            priority,
            new RetryPolicy(3, 100, 1000, 2.0),
            idempotencyKey,
            dependencies,
            Instant.now()
        );
    }

    public static void main(String[] args) throws Exception {

        try (BackgroundTaskService service =
                 new BackgroundTaskService(3)) {

            service.register("report", payload -> {
                String name = payload.get("name");

                if (name == null || name.isBlank()) {
                    throw new PermanentTaskException(
                        "Report name is required."
                    );
                }

                Thread.sleep(60);

                return "Report generated: " + name;
            });

            service.register("notification", payload -> {
                String email = payload.get("email");

                if (
                    email == null ||
                    !email.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")
                ) {
                    throw new PermanentTaskException(
                        "Invalid email address."
                    );
                }

                return "Notification accepted for " + email;
            });

            AtomicInteger failures = new AtomicInteger();

            service.register("external-service", payload -> {
                if (failures.getAndIncrement() == 0) {
                    throw new RuntimeException(
                        "Temporary service failure."
                    );
                }

                return "External service recovered.";
            });

            Task report = service.submit(definition(
                "report",
                Map.of("name", "Monthly Operations"),
                TaskPriority.HIGH,
                "monthly-report-2026-11",
                Set.of()
            ));

            Task notification = service.submit(definition(
                "notification",
                Map.of("email", "operations@example.com"),
                TaskPriority.NORMAL,
                null,
                Set.of(report.id())
            ));

            Task external = service.submit(definition(
                "external-service",
                Map.of(),
                TaskPriority.LOW,
                null,
                Set.of()
            ));

            // Verify idempotent task creation.
            Task duplicate = service.submit(definition(
                "report",
                Map.of("name", "Duplicate"),
                TaskPriority.NORMAL,
                "monthly-report-2026-11",
                Set.of()
            ));

            if (!duplicate.id().equals(report.id())) {
                throw new AssertionError("Idempotency failed.");
            }

            service.start();

            long deadline = System.currentTimeMillis() + 6000;

            while (System.currentTimeMillis() < deadline) {
                boolean completed =
                    report.status() == TaskStatus.COMPLETED &&
                    notification.status() == TaskStatus.COMPLETED &&
                    external.status() == TaskStatus.COMPLETED;

                if (completed) break;

                Thread.sleep(25);
            }

            if (
                report.status() != TaskStatus.COMPLETED ||
                notification.status() != TaskStatus.COMPLETED ||
                external.status() != TaskStatus.COMPLETED ||
                external.attempts() != 2
            ) {
                throw new AssertionError(
                    "Enterprise task validation failed."
                );
            }

            System.out.println("\nTASK DETAILS");

            for (Task task : service.repository().all()) {
                System.out.printf(
                    "%s | %s | %s | attempts=%d | worker=%s%n",
                    task.id(),
                    task.definition().type(),
                    task.status(),
                    task.attempts(),
                    task.workerId()
                );
            }

            System.out.println("\nMETRICS");
            System.out.println(service.report());

            System.out.println("\nAll Java 17 assertions passed.");
        }
    }
}
