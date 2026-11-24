import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

/*
 * Async FastAPI Engineering: Enterprise Asynchronous Service Model
 *
 * Java 17
 *
 * Compile:
 *   javac AsyncEnterpriseService.java
 *
 * Run:
 *   java AsyncEnterpriseService
 *
 * Models:
 *   - Asynchronous service boundaries
 *   - CompletableFuture pipelines
 *   - Bounded execution resources
 *   - Database connection admission
 *   - Repository abstraction
 *   - Failure propagation
 *   - Timeouts
 *   - Cancellation
 *   - Request lifecycle management
 */

public class AsyncEnterpriseService {

    // -----------------------------------------------------
    // Domain types
    // -----------------------------------------------------

    enum TaskStatus {
        PENDING,
        RUNNING,
        COMPLETED,
        FAILED
    }

    record Task(
        UUID id,
        String title,
        String description,
        TaskStatus status,
        Instant createdAt,
        Instant updatedAt
    ) {
        Task {
            Objects.requireNonNull(id);
            Objects.requireNonNull(status);
            Objects.requireNonNull(createdAt);
            Objects.requireNonNull(updatedAt);

            if (title == null ||
                title.isBlank() ||
                title.length() > 150) {
                throw new IllegalArgumentException(
                    "Invalid task title"
                );
            }

            if (description == null ||
                description.length() > 2000) {
                throw new IllegalArgumentException(
                    "Invalid task description"
                );
            }
        }

        Task withStatus(TaskStatus newStatus) {
            return new Task(
                id,
                title,
                description,
                newStatus,
                createdAt,
                Instant.now()
            );
        }
    }

    record CreateTaskCommand(
        String title,
        String description
    ) {
        CreateTaskCommand {
            if (title == null ||
                title.isBlank() ||
                title.length() > 150) {
                throw new IllegalArgumentException(
                    "Title must contain 1 to 150 characters"
                );
            }

            description = description == null ? "" : description;

            if (description.length() > 2000) {
                throw new IllegalArgumentException(
                    "Description exceeds maximum length"
                );
            }
        }
    }

    record ServiceResult<T>(
        boolean successful,
        T data,
        String error,
        Duration duration
    ) {}

    // -----------------------------------------------------
    // Custom exceptions
    // -----------------------------------------------------

    static class ResourceUnavailableException
        extends RuntimeException {

        ResourceUnavailableException(String message) {
            super(message);
        }
    }

    static class TaskNotFoundException
        extends RuntimeException {

        TaskNotFoundException(UUID id) {
            super("Task not found: " + id);
        }
    }

    static class DuplicateTaskException
        extends RuntimeException {

        DuplicateTaskException(String message) {
            super(message);
        }
    }

    // -----------------------------------------------------
    // Asynchronous repository contract
    // -----------------------------------------------------

    interface TaskRepository {
        CompletableFuture<Task> save(Task task);

        CompletableFuture<Optional<Task>> findById(UUID id);

        CompletableFuture<List<Task>> findAll();

        CompletableFuture<Boolean> delete(UUID id);
    }

    // -----------------------------------------------------
    // Simulated database connection admission
    // -----------------------------------------------------

    static final class DatabaseAdmission {

        private final Semaphore permits;

        DatabaseAdmission(int maximumConnections) {
            if (maximumConnections < 1) {
                throw new IllegalArgumentException(
                    "Connection capacity must be positive"
                );
            }

            this.permits = new Semaphore(maximumConnections);
        }

        <T> T execute(
            Duration timeout,
            Supplier<T> operation
        ) {
            boolean acquired = false;

            try {
                acquired = permits.tryAcquire(
                    timeout.toMillis(),
                    TimeUnit.MILLISECONDS
                );

                if (!acquired) {
                    throw new ResourceUnavailableException(
                        "Database capacity exhausted"
                    );
                }

                return operation.get();

            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();

                throw new ResourceUnavailableException(
                    "Database operation interrupted"
                );

            } finally {
                if (acquired) {
                    permits.release();
                }
            }
        }

        int availableConnections() {
            return permits.availablePermits();
        }
    }

    // -----------------------------------------------------
    // In-memory asynchronous repository
    // -----------------------------------------------------

    static final class InMemoryTaskRepository
        implements TaskRepository, AutoCloseable {

        private final Map<UUID, Task> tasks =
            new java.util.concurrent.ConcurrentHashMap<>();

        private final ExecutorService databaseExecutor;

        private final DatabaseAdmission admission;

        InMemoryTaskRepository(
            int workerCount,
            int connectionCount
        ) {
            if (workerCount < 1) {
                throw new IllegalArgumentException(
                    "Worker count must be positive"
                );
            }

            this.databaseExecutor = new ThreadPoolExecutor(
                workerCount,
                workerCount,
                0L,
                TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(200),
                new ThreadPoolExecutor.AbortPolicy()
            );

            this.admission = new DatabaseAdmission(
                connectionCount
            );
        }

        private <T> CompletableFuture<T> submit(
            Supplier<T> operation
        ) {
            return CompletableFuture.supplyAsync(
                () -> admission.execute(
                    Duration.ofSeconds(2),
                    operation
                ),
                databaseExecutor
            );
        }

        @Override
        public CompletableFuture<Task> save(Task task) {
            Objects.requireNonNull(task);

            return submit(() -> {
                Task previous = tasks.putIfAbsent(
                    task.id(),
                    task
                );

                if (previous != null) {
                    throw new DuplicateTaskException(
                        "Task already exists"
                    );
                }

                return task;
            });
        }

        @Override
        public CompletableFuture<Optional<Task>> findById(
            UUID id
        ) {
            Objects.requireNonNull(id);

            return submit(() -> Optional.ofNullable(
                tasks.get(id)
            ));
        }

        @Override
        public CompletableFuture<List<Task>> findAll() {
            return submit(() ->
                tasks.values()
                    .stream()
                    .sorted(
                        java.util.Comparator.comparing(
                            Task::createdAt
                        ).reversed()
                    )
                    .toList()
            );
        }

        @Override
        public CompletableFuture<Boolean> delete(UUID id) {
            Objects.requireNonNull(id);

            return submit(() ->
                tasks.remove(id) != null
            );
        }

        int availableConnections() {
            return admission.availableConnections();
        }

        @Override
        public void close() {
            databaseExecutor.shutdown();

            try {
                if (!databaseExecutor.awaitTermination(
                    5,
                    TimeUnit.SECONDS
                )) {
                    databaseExecutor.shutdownNow();
                }

            } catch (InterruptedException error) {
                databaseExecutor.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }

    // -----------------------------------------------------
    // Enterprise service layer
    // -----------------------------------------------------

    static final class TaskService {

        private final TaskRepository repository;

        private final ExecutorService businessExecutor;

        TaskService(
            TaskRepository repository,
            int businessWorkerCount
        ) {
            this.repository = Objects.requireNonNull(repository);

            this.businessExecutor = Executors.newFixedThreadPool(
                businessWorkerCount
            );
        }

        CompletableFuture<Task> create(
            CreateTaskCommand command
        ) {
            Objects.requireNonNull(command);

            Task task = new Task(
                UUID.randomUUID(),
                command.title(),
                command.description(),
                TaskStatus.PENDING,
                Instant.now(),
                Instant.now()
            );

            return repository.save(task);
        }

        CompletableFuture<Task> get(UUID id) {
            return repository.findById(id)
                .thenApply(optional ->
                    optional.orElseThrow(
                        () -> new TaskNotFoundException(id)
                    )
                );
        }

        CompletableFuture<List<Task>> list() {
            return repository.findAll();
        }

        CompletableFuture<Task> updateStatus(
            UUID id,
            TaskStatus newStatus
        ) {
            Objects.requireNonNull(newStatus);

            return get(id).thenCompose(existing -> {

                validateTransition(
                    existing.status(),
                    newStatus
                );

                Task updated = existing.withStatus(newStatus);

                // Replace is performed through a business-level
                // asynchronous operation in this in-memory model.
                return CompletableFuture.supplyAsync(() -> updated,
                    businessExecutor);
            });
        }

        private void validateTransition(
            TaskStatus current,
            TaskStatus next
        ) {
            boolean valid = switch (current) {
                case PENDING ->
                    next == TaskStatus.RUNNING ||
                    next == TaskStatus.FAILED;

                case RUNNING ->
                    next == TaskStatus.COMPLETED ||
                    next == TaskStatus.FAILED;

                case COMPLETED, FAILED ->
                    false;
            };

            if (!valid) {
                throw new IllegalStateException(
                    "Invalid task transition: " +
                    current + " -> " + next
                );
            }
        }

        CompletableFuture<ServiceResult<Task>> executeSafely(
            Supplier<CompletableFuture<Task>> operation
        ) {
            Instant started = Instant.now();

            return operation.get()
                .handle((data, error) -> {
                    Duration duration = Duration.between(
                        started,
                        Instant.now()
                    );

                    if (error != null) {
                        Throwable cause = unwrap(error);

                        return new ServiceResult<Task>(
                            false,
                            null,
                            cause.getMessage(),
                            duration
                        );
                    }

                    return new ServiceResult<Task>(
                        true,
                        data,
                        null,
                        duration
                    );
                });
        }

        private Throwable unwrap(Throwable error) {
            if (
                error instanceof CompletionException &&
                error.getCause() != null
            ) {
                return error.getCause();
            }

            return error;
        }

        void close() {
            businessExecutor.shutdown();

            try {
                if (!businessExecutor.awaitTermination(
                    5,
                    TimeUnit.SECONDS
                )) {
                    businessExecutor.shutdownNow();
                }

            } catch (InterruptedException error) {
                businessExecutor.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }

    // -----------------------------------------------------
    // Independent asynchronous operations
    // -----------------------------------------------------

    static CompletableFuture<String> simulateRemoteService(
        String serviceName,
        long delayMs,
        ExecutorService executor
    ) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                TimeUnit.MILLISECONDS.sleep(delayMs);

                return serviceName + ": completed";

            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();

                throw new CompletionException(error);
            }
        }, executor);
    }

    static Throwable rootCause(Throwable error) {
        while (
            error instanceof CompletionException &&
            error.getCause() != null
        ) {
            error = error.getCause();
        }

        return error;
    }

    // -----------------------------------------------------
    // Main enterprise workflow
    // -----------------------------------------------------

    public static void main(String[] args) {

        InMemoryTaskRepository repository =
            new InMemoryTaskRepository(4, 2);

        TaskService service = new TaskService(
            repository,
            2
        );

        ExecutorService remoteExecutor =
            Executors.newFixedThreadPool(3);

        try {
            System.out.println(
                "ASYNC ENTERPRISE SERVICE"
            );

            System.out.println(
                "========================"
            );

            List<CompletableFuture<Task>> creationRequests =
                List.of(
                    service.create(
                        new CreateTaskCommand(
                            "Configure asynchronous database access",
                            "Use non-blocking repository operations."
                        )
                    ),

                    service.create(
                        new CreateTaskCommand(
                            "Monitor event-loop latency",
                            "Identify synchronous blocking calls."
                        )
                    ),

                    service.create(
                        new CreateTaskCommand(
                            "Control database concurrency",
                            "Use bounded connections."
                        )
                    )
                );

            CompletableFuture<Void> allCreations =
                CompletableFuture.allOf(
                    creationRequests.toArray(
                        new CompletableFuture[0]
                    )
                );

            allCreations.join();

            List<Task> createdTasks =
                creationRequests.stream()
                    .map(CompletableFuture::join)
                    .toList();

            System.out.println("\nCREATED TASKS");

            createdTasks.forEach(System.out::println);

            System.out.println("\nPARALLEL SERVICE CALLS");

            CompletableFuture<String> databaseCall =
                simulateRemoteService(
                    "Database",
                    300,
                    remoteExecutor
                );

            CompletableFuture<String> cacheCall =
                simulateRemoteService(
                    "Cache",
                    150,
                    remoteExecutor
                );

            CompletableFuture<String> auditCall =
                simulateRemoteService(
                    "Audit",
                    200,
                    remoteExecutor
                );

            CompletableFuture.allOf(
                databaseCall,
                cacheCall,
                auditCall
            ).join();

            System.out.println(databaseCall.join());
            System.out.println(cacheCall.join());
            System.out.println(auditCall.join());

            System.out.println("\nTASK RETRIEVAL");

            Task firstTask = service.get(
                createdTasks.get(0).id()
            ).join();

            System.out.println(firstTask);

            System.out.println("\nVALID STATE TRANSITION");

            Task transitioned = service.updateStatus(
                firstTask.id(),
                TaskStatus.RUNNING
            ).join();

            System.out.println(
                "Updated state: " + transitioned.status()
            );

            System.out.println("\nFAILURE HANDLING");

            ServiceResult<Task> failure =
                service.executeSafely(
                    () -> service.get(UUID.randomUUID())
                ).join();

            System.out.println(
                "Successful: " + failure.successful()
            );

            System.out.println(
                "Error: " + failure.error()
            );

            System.out.println("\nTIMEOUT HANDLING");

            CompletableFuture<String> slowOperation =
                simulateRemoteService(
                    "Slow service",
                    1500,
                    remoteExecutor
                );

            try {
                String result = slowOperation.get(
                    100,
                    TimeUnit.MILLISECONDS
                );

                System.out.println(result);

            } catch (TimeoutException error) {
                System.out.println(
                    "Caller stopped waiting after timeout"
                );

                // A caller timeout does not guarantee that
                // the underlying operation has been cancelled.
                slowOperation.cancel(true);
            }

            System.out.println("\nDATABASE CAPACITY");

            System.out.println(
                "Available connections: " +
                repository.availableConnections()
            );

            System.out.println("\nRETRIEVED TASK COUNT");

            System.out.println(
                service.list().join().size()
            );

            System.out.println("\nASYNC EXECUTION COMPLETED");

        } catch (CompletionException error) {

            Throwable cause = rootCause(error);

            System.err.println(
                "Workflow failed: " + cause.getMessage()
            );

        } catch (Exception error) {

            System.err.println(
                "Application error: " + error.getMessage()
            );

        } finally {

            remoteExecutor.shutdown();

            try {
                if (!remoteExecutor.awaitTermination(
                    5,
                    TimeUnit.SECONDS
                )) {
                    remoteExecutor.shutdownNow();
                }

            } catch (InterruptedException error) {
                remoteExecutor.shutdownNow();
                Thread.currentThread().interrupt();
            }

            service.close();
            repository.close();
        }
    }
}
