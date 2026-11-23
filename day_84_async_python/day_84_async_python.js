"use strict";

/*
 * ASYNC JAVASCRIPT: EVENT-DRIVEN CONCURRENCY AND TASK SCHEDULING
 *
 * Requirements: Node.js 18+
 *
 * Demonstrates:
 * - Promises and async/await
 * - Microtask execution
 * - Promise.all and Promise.allSettled
 * - Promise.race
 * - AbortController
 * - Bounded concurrency
 * - Event-driven scheduling
 * - Producer-consumer processing
 * - Retry policies
 * - Timeouts
 * - Task dependency execution
 * - Resource cleanup
 * - Failure isolation
 */

const { performance } = require("node:perf_hooks");
const { EventEmitter } = require("node:events");


// ============================================================
// 1. UTILITIES
// ============================================================

const sleep = (milliseconds, signal) => {
    return new Promise((resolve, reject) => {
        if (signal?.aborted) {
            reject(new Error("Operation aborted"));
            return;
        }

        const timer = setTimeout(() => {
            cleanup();
            resolve();
        }, milliseconds);

        function onAbort() {
            clearTimeout(timer);
            cleanup();
            reject(new Error("Operation aborted"));
        }

        function cleanup() {
            signal?.removeEventListener("abort", onAbort);
        }

        signal?.addEventListener("abort", onAbort, {
            once: true
        });
    });
};


function validatePositiveInteger(value, name) {
    if (!Number.isInteger(value) || value < 1) {
        throw new RangeError(`${name} must be a positive integer`);
    }
}


// ============================================================
// 2. BASIC ASYNC FUNCTIONS
// ============================================================

async function asynchronousTask(name, duration) {
    console.log(`Starting ${name}`);

    await sleep(duration);

    console.log(`Completed ${name}`);

    return `${name} finished`;
}


async function demonstrateAsyncAwait() {
    console.log("\n1. ASYNC/AWAIT");

    const result = await asynchronousTask("Task A", 200);

    console.log(result);
}


// ============================================================
// 3. PROMISE CONCURRENCY
// ============================================================

async function demonstratePromises() {
    console.log("\n2. PROMISE CONCURRENCY");

    const start = performance.now();

    const results = await Promise.all([
        asynchronousTask("A", 300),
        asynchronousTask("B", 200),
        asynchronousTask("C", 100)
    ]);

    console.log(results);

    console.log(
        `Elapsed: ${((performance.now() - start) / 1000).toFixed(3)}s`
    );
}


// ============================================================
// 4. FAILURE ISOLATION
// ============================================================

async function demonstrateAllSettled() {
    console.log("\n3. FAILURE ISOLATION");

    const operations = [
        Promise.resolve("Operation A"),
        Promise.reject(new Error("Operation B failed")),
        Promise.resolve("Operation C")
    ];

    const results = await Promise.allSettled(operations);

    for (const result of results) {
        if (result.status === "fulfilled") {
            console.log("Success:", result.value);
        } else {
            console.log("Failure:", result.reason.message);
        }
    }
}


// ============================================================
// 5. TIMEOUTS
// ============================================================

async function withTimeout(operation, milliseconds) {
    validatePositiveInteger(milliseconds, "Timeout");

    const controller = new AbortController();

    let timer;

    const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => {
            controller.abort();
            reject(new Error("Operation timed out"));
        }, milliseconds);
    });

    try {
        return await Promise.race([
            operation(controller.signal),
            timeout
        ]);
    } finally {
        clearTimeout(timer);
    }
}


async function demonstrateTimeout() {
    console.log("\n4. TIMEOUT MANAGEMENT");

    try {
        await withTimeout(
            async signal => {
                await sleep(1000, signal);
                return "Completed";
            },
            200
        );
    } catch (error) {
        console.log(error.message);
    }
}


// ============================================================
// 6. BOUNDED CONCURRENCY SCHEDULER
// ============================================================

class AsyncScheduler {

    constructor(maxConcurrency = 3) {
        validatePositiveInteger(
            maxConcurrency,
            "Maximum concurrency"
        );

        this.maxConcurrency = maxConcurrency;
        this.active = 0;
        this.queue = [];
        this.closed = false;
        this.completed = 0;
        this.failed = 0;
    }

    submit(operation) {
        if (this.closed) {
            return Promise.reject(
                new Error("Scheduler is closed")
            );
        }

        if (typeof operation !== "function") {
            return Promise.reject(
                new TypeError("Operation must be a function")
            );
        }

        return new Promise((resolve, reject) => {
            this.queue.push({
                operation,
                resolve,
                reject
            });

            this.drain();
        });
    }

    drain() {
        while (
            !this.closed &&
            this.active < this.maxConcurrency &&
            this.queue.length > 0
        ) {
            const task = this.queue.shift();

            this.active++;

            Promise.resolve()
                .then(task.operation)
                .then(result => {
                    this.completed++;
                    task.resolve(result);
                })
                .catch(error => {
                    this.failed++;
                    task.reject(error);
                })
                .finally(() => {
                    this.active--;
                    this.drain();
                });
        }
    }

    close() {
        this.closed = true;

        const error = new Error("Scheduler closed before execution");

        for (const task of this.queue.splice(0)) {
            task.reject(error);
        }
    }

    get metrics() {
        return Object.freeze({
            active: this.active,
            queued: this.queue.length,
            completed: this.completed,
            failed: this.failed
        });
    }
}


async function demonstrateScheduler() {
    console.log("\n5. BOUNDED CONCURRENCY");

    const scheduler = new AsyncScheduler(2);

    const tasks = Array.from({ length: 6 }, (_, index) => {
        return scheduler.submit(async () => {
            await sleep(150);

            return `Job ${index + 1} completed`;
        });
    });

    const results = await Promise.all(tasks);

    console.log(results);
    console.log("Metrics:", scheduler.metrics);

    scheduler.close();
}


// ============================================================
// 7. ABORT CONTROLLER AND CANCELLATION
// ============================================================

async function cancellableTask(signal) {
    let iteration = 0;

    while (!signal.aborted) {
        await sleep(100, signal);
        iteration++;
        console.log("Iteration:", iteration);
    }

    return iteration;
}


async function demonstrateCancellation() {
    console.log("\n6. CANCELLATION");

    const controller = new AbortController();

    const task = cancellableTask(controller.signal);

    await sleep(350);

    controller.abort();

    try {
        await task;
    } catch (error) {
        console.log("Cancelled:", error.message);
    }
}


// ============================================================
// 8. EVENT-DRIVEN ARCHITECTURE
// ============================================================

class JobEventBus extends EventEmitter {

    publish(event, payload) {
        if (typeof event !== "string" || !event.trim()) {
            throw new TypeError("Event name is required");
        }

        this.emit(event, Object.freeze({ ...payload }));
    }
}


async function demonstrateEventBus() {
    console.log("\n7. EVENT-DRIVEN EXECUTION");

    const bus = new JobEventBus();

    bus.on("job:completed", job => {
        console.log("Completion event:", job.id);
    });

    bus.on("job:failed", job => {
        console.log("Failure event:", job.id);
    });

    bus.publish("job:completed", {
        id: 101,
        status: "completed"
    });

    bus.publish("job:failed", {
        id: 102,
        status: "failed"
    });
}


// ============================================================
// 9. PRODUCER-CONSUMER WITH ASYNC ITERATION
// ============================================================

async function* jobProducer(count) {
    for (let id = 1; id <= count; id++) {
        await sleep(50);

        yield {
            id,
            payload: id * 10
        };
    }
}


async function demonstrateAsyncIterator() {
    console.log("\n8. ASYNCHRONOUS ITERATION");

    for await (const job of jobProducer(5)) {
        console.log("Received:", job);
    }
}


// ============================================================
// 10. RETRY WITH EXPONENTIAL BACKOFF
// ============================================================

async function retry(
    operation,
    {
        attempts = 3,
        initialDelay = 100,
        retryable = error => error.retryable === true
    } = {}
) {
    validatePositiveInteger(attempts, "Attempts");

    if (!Number.isFinite(initialDelay) || initialDelay < 0) {
        throw new RangeError("Invalid retry delay");
    }

    for (let attempt = 1; attempt <= attempts; attempt++) {
        try {
            return await operation(attempt);
        } catch (error) {
            if (
                attempt === attempts ||
                !retryable(error)
            ) {
                throw error;
            }

            await sleep(initialDelay * 2 ** (attempt - 1));
        }
    }

    throw new Error("Retry policy exhausted");
}


async function demonstrateRetry() {
    console.log("\n9. RETRY MANAGEMENT");

    let attempts = 0;

    const result = await retry(
        async () => {
            attempts++;

            if (attempts < 3) {
                const error = new Error("Temporary failure");
                error.retryable = true;
                throw error;
            }

            return "Recovered";
        }
    );

    console.log(result);
    console.log("Attempts:", attempts);
}


// ============================================================
// 11. DEPENDENCY-AWARE TASK EXECUTION
// ============================================================

class WorkflowEngine {

    constructor() {
        this.tasks = new Map();
    }

    add(name, dependencies, operation) {
        if (this.tasks.has(name)) {
            throw new Error(`Duplicate task: ${name}`);
        }

        if (typeof operation !== "function") {
            throw new TypeError("Task operation must be a function");
        }

        this.tasks.set(name, {
            dependencies: [...dependencies],
            operation
        });
    }

    validate() {
        for (const [name, task] of this.tasks) {
            for (const dependency of task.dependencies) {
                if (!this.tasks.has(dependency)) {
                    throw new Error(
                        `Unknown dependency ${dependency} for ${name}`
                    );
                }
            }
        }

        const visited = new Set();
        const visiting = new Set();

        const visit = name => {
            if (visiting.has(name)) {
                throw new Error("Workflow dependency cycle detected");
            }

            if (visited.has(name)) {
                return;
            }

            visiting.add(name);

            for (const dependency of this.tasks.get(name).dependencies) {
                visit(dependency);
            }

            visiting.delete(name);
            visited.add(name);
        };

        for (const name of this.tasks.keys()) {
            visit(name);
        }
    }

    async execute() {
        this.validate();

        const results = new Map();
        const promises = new Map();

        const run = name => {
            if (promises.has(name)) {
                return promises.get(name);
            }

            const task = this.tasks.get(name);

            const promise = Promise.all(
                task.dependencies.map(run)
            ).then(async () => {
                const dependencies = Object.fromEntries(
                    task.dependencies.map(dependency => [
                        dependency,
                        results.get(dependency)
                    ])
                );

                const result = await task.operation(dependencies);

                results.set(name, result);

                return result;
            });

            promises.set(name, promise);

            return promise;
        };

        await Promise.all(
            [...this.tasks.keys()].map(run)
        );

        return results;
    }
}


async function demonstrateWorkflow() {
    console.log("\n10. DEPENDENCY-AWARE WORKFLOW");

    const workflow = new WorkflowEngine();

    workflow.add("fetch", [], async () => {
        await sleep(100);
        return [10, 20, 30];
    });

    workflow.add("validate", ["fetch"], async dependencies => {
        return dependencies.fetch.every(Number.isFinite);
    });

    workflow.add("aggregate", ["fetch", "validate"], async dependencies => {
        if (!dependencies.validate) {
            throw new Error("Input validation failed");
        }

        return dependencies.fetch.reduce(
            (total, value) => total + value,
            0
        );
    });

    const results = await workflow.execute();

    console.log(Object.fromEntries(results));
}


// ============================================================
// 12. RESOURCE MANAGEMENT
// ============================================================

class AsyncResource {

    constructor() {
        this.open = false;
    }

    async acquire() {
        if (this.open) {
            throw new Error("Resource already acquired");
        }

        await sleep(50);
        this.open = true;
    }

    async release() {
        if (this.open) {
            this.open = false;
            console.log("Resource released");
        }
    }

    async execute() {
        if (!this.open) {
            throw new Error("Resource is not available");
        }

        await sleep(50);
        return "Execution successful";
    }
}


async function demonstrateResourceManagement() {
    console.log("\n11. RESOURCE MANAGEMENT");

    const resource = new AsyncResource();

    try {
        await resource.acquire();

        console.log(await resource.execute());

    } finally {
        await resource.release();
    }
}


// ============================================================
// 13. EVENT LOOP ORDER
// ============================================================

async function demonstrateEventLoop() {
    console.log("\n12. EVENT LOOP ORDER");

    console.log("Synchronous: 1");

    setTimeout(() => {
        console.log("Timer callback: 4");
    }, 0);

    Promise.resolve().then(() => {
        console.log("Promise microtask: 3");
    });

    console.log("Synchronous: 2");

    await sleep(20);
}


// ============================================================
// 14. APPLICATION TESTS
// ============================================================

async function runTests() {

    const scheduler = new AsyncScheduler(2);

    const results = await Promise.all([
        scheduler.submit(async () => 10),
        scheduler.submit(async () => 20),
        scheduler.submit(async () => 30)
    ]);

    console.assert(
        results.reduce((a, b) => a + b, 0) === 60,
        "Scheduler test failed"
    );

    scheduler.close();

    const workflow = new WorkflowEngine();

    workflow.add("first", [], async () => 5);

    workflow.add("second", ["first"], async dependency => {
        return dependency.first * 2;
    });

    const output = await workflow.execute();

    console.assert(
        output.get("second") === 10,
        "Workflow test failed"
    );

    const cyclic = new WorkflowEngine();

    cyclic.add("A", ["B"], async () => 1);
    cyclic.add("B", ["A"], async () => 2);

    let cycleDetected = false;

    try {
        cyclic.validate();
    } catch {
        cycleDetected = true;
    }

    console.assert(cycleDetected, "Cycle detection failed");

    console.log("All JavaScript assertions passed");
}


// ============================================================
// 15. APPLICATION ENTRY POINT
// ============================================================

async function main() {

    const start = performance.now();

    try {
        await demonstrateAsyncAwait();
        await demonstratePromises();
        await demonstrateAllSettled();
        await demonstrateTimeout();
        await demonstrateScheduler();
        await demonstrateCancellation();
        await demonstrateEventBus();
        await demonstrateAsyncIterator();
        await demonstrateRetry();
        await demonstrateWorkflow();
        await demonstrateResourceManagement();
        await demonstrateEventLoop();

        await runTests();

    } finally {
        console.log(
            `Total runtime: ${(
                (performance.now() - start) / 1000
            ).toFixed(3)}s`
        );
    }
}


main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
