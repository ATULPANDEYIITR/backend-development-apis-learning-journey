import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.HashMap;
import java.util.HashSet;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

/*
 * JAVA 17 ASYNCHRONOUS ENTERPRISE PROCESSING
 *
 * Implements:
 * - CompletableFuture
 * - ExecutorService
 * - ScheduledExecutorService
 * - Asynchronous service orchestration
 * - Bounded thread pools
 * - Retry policies
 * - Timeout management
 * - Cancellation
 * - Workflow dependencies
 * - Producer-consumer processing
 * - Exception propagation
 * - Graceful resource shutdown
 */

public class AsyncEnterprise {

    // ========================================================
    // 1. DOMAIN TYPES
    // ========================================================

    enum JobStatus {
        PENDING,
        RUNNING,
        COMPLETED,
        FAILED,
        CANCELLED
    }

    record Job(
        int id,
        String description,
        int durationMillis,
        boolean shouldFail
    ) {
        Job {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Job ID must be positive"
                );
            }

            if (description == null || description.isBlank()) {
                throw new IllegalArgumentException(
                    "Description is required"
                );
            }

            if (durationMillis < 0) {
                throw new IllegalArgumentException(
                    "Duration cannot be negative"
                );
            }
        }
    }

    record JobResult(
        int id,
        JobStatus status,
        String message,
        long durationMillis
    ) {}

    static final class JobProcessingException
        extends RuntimeException {

        JobProcessingException(String message) {
            super(message);
        }
    }


    // ========================================================
    // 2. EXECUTOR FACTORY
    // ========================================================

    static ExecutorService createExecutor(
        int threadCount,
        String prefix
    ) {

        if (threadCount < 1) {
            throw new IllegalArgumentException(
                "Thread count must be positive"
            );
        }

        AtomicInteger counter = new AtomicInteger();

        ThreadFactory factory = runnable -> {
            Thread thread = new Thread(
                runnable,
                prefix + "-" + counter.incrementAndGet()
            );

            thread.setDaemon(false);

            return thread;
        };

        return Executors.newFixedThreadPool(
            threadCount,
            factory
        );
    }


    // ========================================================
    // 3. ASYNCHRONOUS JOB SERVICE
    // ========================================================

    static final class JobService {

        private final ExecutorService executor;

        JobService(ExecutorService executor) {
            this.executor = Objects.requireNonNull(executor);
        }

        CompletableFuture<JobResult> process(Job job) {

            return CompletableFuture.supplyAsync(() -> {

                long start = System.nanoTime();

                try {
                    Thread.sleep(job.durationMillis());

                    if (job.shouldFail()) {
                        throw new JobProcessingException(
                            "Job " + job.id() + " failed"
                        );
                    }

                    long elapsed =
                        TimeUnit.NANOSECONDS.toMillis(
                            System.nanoTime() - start
                        );

                    return new JobResult(
                        job.id(),
                        JobStatus.COMPLETED,
                        "Processed successfully",
                        elapsed
                    );

                } catch (InterruptedException exception) {

                    Thread.currentThread().interrupt();

                    throw new CompletionException(exception);
                }

            }, executor);
        }
    }


    // ========================================================
    // 4. COMPLETABLE FUTURE
    // ========================================================

    static void demonstrateCompletableFuture(
        ExecutorService executor
    ) throws Exception {

        System.out.println("\n1. COMPLETABLE FUTURE");

        CompletableFuture<String> future =
            CompletableFuture.supplyAsync(() -> {

                sleep(200);

                return "Data retrieved";

            }, executor);

        CompletableFuture<String> transformed =
            future.thenApply(String::toUpperCase);

        System.out.println(transformed.get());
    }


    // ========================================================
    // 5. PARALLEL SERVICE ORCHESTRATION
    // ========================================================

    static void demonstrateParallelExecution(
        ExecutorService executor
    ) throws Exception {

        System.out.println("\n2. PARALLEL EXECUTION");

        CompletableFuture<Integer> serviceA =
            CompletableFuture.supplyAsync(() -> {
                sleep(200);
                return 100;
            }, executor);

        CompletableFuture<Integer> serviceB =
            CompletableFuture.supplyAsync(() -> {
                sleep(300);
                return 200;
            }, executor);

        CompletableFuture<Integer> combined =
            serviceA.thenCombine(
                serviceB,
                Integer::sum
            );

        System.out.println(
            "Combined result: " + combined.get()
        );
    }


    // ========================================================
    // 6. FAILURE RECOVERY
    // ========================================================

    static void demonstrateFailureRecovery(
        ExecutorService executor
    ) throws Exception {

        System.out.println("\n3. FAILURE RECOVERY");

        CompletableFuture<String> operation =
            CompletableFuture.supplyAsync(() -> {

                throw new JobProcessingException(
                    "Primary service unavailable"
                );

            }, executor);

        CompletableFuture<String> recovered =
            operation.exceptionally(error -> {
                System.out.println(
                    "Recovered from: " + error.getMessage()
                );

                return "Fallback response";
            });

        System.out.println(recovered.get());
    }


    // ========================================================
    // 7. ASYNCHRONOUS JOB BATCH
    // ========================================================

    static void demonstrateJobBatch(
        ExecutorService executor
    ) throws Exception {

        System.out.println("\n4. JOB BATCH PROCESSING");

        JobService service = new JobService(executor);

        List<Job> jobs = List.of(
            new Job(1, "Data extraction", 150, false),
            new Job(2, "Data validation", 200, false),
            new Job(3, "Data transformation", 100, false),
            new Job(4, "Report generation", 120, true),
            new Job(5, "Data publication", 180, false)
        );

        List<CompletableFuture<JobResult>> futures =
            jobs.stream()
                .map(service::process)
                .toList();

        CompletableFuture<Void> all =
            CompletableFuture.allOf(
                futures.toArray(new CompletableFuture[0])
            );

        all.handle((ignored, error) -> null).get();

        for (int i = 0; i < futures.size(); i++) {

            try {
                System.out.println(futures.get(i).join());

            } catch (CompletionException exception) {
                System.out.println(
                    "Job failed: " + jobs.get(i).id()
                );
            }
        }
    }


    // ========================================================
    // 8. TIMEOUT MANAGEMENT
    // ========================================================

    static void demonstrateTimeout(
        ExecutorService executor
    ) {

        System.out.println("\n5. TIMEOUT MANAGEMENT");

        CompletableFuture<String> operation =
            CompletableFuture.supplyAsync(() -> {

                sleep(1000);

                return "Completed";

            }, executor);

        try {

            String result = operation.get(
                200,
                TimeUnit.MILLISECONDS
            );

            System.out.println(result);

        } catch (TimeoutException exception) {

            operation.cancel(true);

            System.out.println("Operation timed out");

        } catch (
            InterruptedException |
            ExecutionException exception
        ) {

            Thread.currentThread().interrupt();

            System.out.println(exception.getMessage());
        }
    }


    // ========================================================
    // 9. RETRY SERVICE
    // ========================================================

    static final class RetryService {

        private final ScheduledExecutorService scheduler;

        RetryService(ScheduledExecutorService scheduler) {
            this.scheduler = scheduler;
        }

        CompletableFuture<String> execute(
            Supplier<String> operation,
            int maxAttempts,
            long initialDelayMillis
        ) {

            if (maxAttempts < 1 || initialDelayMillis < 0) {
                throw new IllegalArgumentException(
                    "Invalid retry configuration"
                );
            }

            CompletableFuture<String> result =
                new CompletableFuture<>();

            attempt(
                operation,
                maxAttempts,
                initialDelayMillis,
                1,
                result
            );

            return result;
        }

        private void attempt(
            Supplier<String> operation,
            int maxAttempts,
            long delay,
            int attempt,
            CompletableFuture<String> result
        ) {

            if (result.isDone()) {
                return;
            }

            try {

                String value = operation.get();

                result.complete(value);

            } catch (RuntimeException exception) {

                if (attempt >= maxAttempts) {
                    result.completeExceptionally(exception);
                    return;
                }

                long nextDelay = Math.multiplyExact(
                    delay,
                    2
                );

                scheduler.schedule(
                    () -> attempt(
                        operation,
                        maxAttempts,
                        nextDelay,
                        attempt + 1,
                        result
                    ),
                    delay,
                    TimeUnit.MILLISECONDS
                );
            }
        }
    }


    static void demonstrateRetry() throws Exception {

        System.out.println("\n6. RETRY MANAGEMENT");

        ScheduledExecutorService scheduler =
            Executors.newScheduledThreadPool(1);

        try {

            AtomicInteger attempts = new AtomicInteger();

            RetryService retry = new RetryService(scheduler);

            CompletableFuture<String> result = retry.execute(
                () -> {

                    int count = attempts.incrementAndGet();

                    if (count < 3) {
                        throw new JobProcessingException(
                            "Temporary failure"
                        );
                    }

                    return "Recovered successfully";
                },
                3,
                100
            );

            System.out.println(result.get());

            System.out.println(
                "Attempts: " + attempts.get()
            );

        } finally {
            shutdown(scheduler);
        }
    }


    // ========================================================
    // 10. PRODUCER-CONSUMER
    // ========================================================

    static void demonstrateProducerConsumer()
        throws Exception {

        System.out.println("\n7. PRODUCER-CONSUMER");

        BlockingQueue<Integer> queue =
            new ArrayBlockingQueue<>(3);

        int stopSignal = -1;

        ExecutorService executor =
            Executors.newFixedThreadPool(2);

        try {

            Future<?> producer = executor.submit(() -> {

                try {

                    for (int i = 1; i <= 8; i++) {
                        queue.put(i);
                        System.out.println("Produced: " + i);
                    }

                    queue.put(stopSignal);

                } catch (InterruptedException exception) {
                    Thread.currentThread().interrupt();
                }
            });

            Future<?> consumer = executor.submit(() -> {

                try {

                    while (true) {

                        int item = queue.take();

                        if (item == stopSignal) {
                            break;
                        }

                        System.out.println(
                            "Consumed: " + item
                        );
                    }

                } catch (InterruptedException exception) {
                    Thread.currentThread().interrupt();
                }
            });

            producer.get();
            consumer.get();

        } finally {
            shutdown(executor);
        }
    }


    // ========================================================
    // 11. DEPENDENCY WORKFLOW
    // ========================================================

    static void demonstrateDependencies(
        ExecutorService executor
    ) throws Exception {

        System.out.println("\n8. DEPENDENCY WORKFLOW");

        CompletableFuture<List<Integer>> extraction =
            CompletableFuture.supplyAsync(() -> {
                sleep(100);
                return List.of(10, 20, 30);
            }, executor);

        CompletableFuture<Boolean> validation =
            extraction.thenApply(records ->
                records.stream().allMatch(value -> value > 0)
            );

        CompletableFuture<Integer> aggregation =
            extraction.thenCombine(
                validation,
                (records, valid) -> {

                    if (!valid) {
                        throw new JobProcessingException(
                            "Validation failed"
                        );
                    }

                    return records.stream()
                        .mapToInt(Integer::intValue)
                        .sum();
                }
            );

        System.out.println(
            "Aggregate: " + aggregation.get()
        );
    }


    // ========================================================
    // 12. CANCELLATION
    // ========================================================

    static void demonstrateCancellation(
        ExecutorService executor
    ) {

        System.out.println("\n9. TASK CANCELLATION");

        Future<?> task = executor.submit(() -> {

            try {

                while (!Thread.currentThread().isInterrupted()) {
                    Thread.sleep(100);
                }

            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
            }
        });

        sleep(200);

        boolean cancelled = task.cancel(true);

        System.out.println("Cancellation requested: " + cancelled);
    }


    // ========================================================
    // 13. APPLICATION TESTS
    // ========================================================

    static void runTests(
        ExecutorService executor
    ) throws Exception {

        System.out.println("\n10. VALIDATION TESTS");

        CompletableFuture<Integer> first =
            CompletableFuture.supplyAsync(() -> 10, executor);

        CompletableFuture<Integer> second =
            CompletableFuture.supplyAsync(() -> 20, executor);

        int result = first.thenCombine(
            second,
            Integer::sum
        ).get();

        if (result != 30) {
            throw new AssertionError(
                "Combination test failed"
            );
        }

        Set<Integer> unique = new HashSet<>(
            List.of(1, 2, 2, 3)
        );

        if (unique.size() != 3) {
            throw new AssertionError(
                "Collection test failed"
            );
        }

        System.out.println("All Java assertions passed");
    }


    // ========================================================
    // 14. RESOURCE SHUTDOWN
    // ========================================================

    static void shutdown(ExecutorService executor) {

        executor.shutdown();

        try {

            if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                executor.shutdownNow();

                if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                    System.err.println(
                        "Executor did not terminate"
                    );
                }
            }

        } catch (InterruptedException exception) {

            executor.shutdownNow();

            Thread.currentThread().interrupt();
        }
    }


    static void sleep(long milliseconds) {

        try {
            Thread.sleep(milliseconds);

        } catch (InterruptedException exception) {

            Thread.currentThread().interrupt();

            throw new CompletionException(exception);
        }
    }


    // ========================================================
    // 15. APPLICATION ENTRY POINT
    // ========================================================

    public static void main(String[] args) {

        ExecutorService executor = createExecutor(
            4,
            "async-worker"
        );

        long start = System.nanoTime();

        try {

            demonstrateCompletableFuture(executor);

            demonstrateParallelExecution(executor);

            demonstrateFailureRecovery(executor);

            demonstrateJobBatch(executor);

            demonstrateTimeout(executor);

            demonstrateRetry();

            demonstrateProducerConsumer();

            demonstrateDependencies(executor);

            demonstrateCancellation(executor);

            runTests(executor);

            System.out.println(
                "\nAll demonstrations completed"
            );

        } catch (Exception exception) {

            System.err.println(
                "Application failure: " + exception.getMessage()
            );

        } finally {

            shutdown(executor);

            long elapsed = TimeUnit.NANOSECONDS.toMillis(
                System.nanoTime() - start
            );

            System.out.println(
                "Total execution time: " + elapsed + "ms"
            );
        }
    }
}
