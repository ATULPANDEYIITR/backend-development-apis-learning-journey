"use strict";

/*
 * Async FastAPI: Event-Driven Client and Concurrency Controller
 *
 * Runtime: Node.js 20+
 *
 * Run:
 *   node async_client.js
 *
 * Optional:
 *   API_BASE_URL=http://127.0.0.1:8000 node async_client.js
 *
 * This implementation focuses on asynchronous HTTP communication,
 * bounded concurrency, retries, cancellation and event-loop behavior.
 */

const { performance } = require("node:perf_hooks");
const { randomUUID } = require("node:crypto");
const { EventEmitter } = require("node:events");

// ---------------------------------------------------------
// Configuration
// ---------------------------------------------------------

const CONFIG = Object.freeze({
    baseUrl: process.env.API_BASE_URL || "http://127.0.0.1:8000",
    concurrency: 5,
    timeoutMs: 5000,
    maxRetries: 2,
    retryDelayMs: 300,
    maxBatchSize: 100
});

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

// ---------------------------------------------------------
// Domain errors
// ---------------------------------------------------------

class ApiError extends Error {
    constructor(message, statusCode = 0, retryable = false) {
        super(message);
        this.name = "ApiError";
        this.statusCode = statusCode;
        this.retryable = retryable;
    }
}

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

// ---------------------------------------------------------
// Input validation
// ---------------------------------------------------------

function validateTask(task) {
    if (!task || typeof task !== "object") {
        throw new ValidationError("Task must be an object");
    }

    if (
        typeof task.title !== "string" ||
        task.title.trim().length < 3 ||
        task.title.length > 150
    ) {
        throw new ValidationError(
            "Title must contain between 3 and 150 characters"
        );
    }

    if (
        task.description !== undefined &&
        (
            typeof task.description !== "string" ||
            task.description.length > 2000
        )
    ) {
        throw new ValidationError("Invalid task description");
    }

    return {
        title: task.title.trim(),
        description: task.description || ""
    };
}

// ---------------------------------------------------------
// Asynchronous API client
// ---------------------------------------------------------

class AsyncFastAPIClient {
    constructor(baseUrl, timeoutMs = 5000) {
        this.baseUrl = new URL(baseUrl);
        this.timeoutMs = timeoutMs;
        this.events = new EventEmitter();

        this.events.setMaxListeners(100);
    }

    async request(path, options = {}) {
        const url = new URL(path, this.baseUrl);

        const {
            method = "GET",
            body,
            headers = {},
            signal,
            timeoutMs = this.timeoutMs
        } = options;

        const controller = new AbortController();

        const timer = setTimeout(
            () => controller.abort(
                new Error("Request timed out")
            ),
            timeoutMs
        );

        const onAbort = () => controller.abort(signal.reason);

        if (signal) {
            if (signal.aborted) {
                controller.abort(signal.reason);
            } else {
                signal.addEventListener("abort", onAbort, {
                    once: true
                });
            }
        }

        const requestId = randomUUID();

        const started = performance.now();

        this.events.emit("request:start", {
            requestId,
            method,
            path
        });

        try {
            const response = await fetch(url, {
                method,
                headers: {
                    "Content-Type": "application/json",
                    "X-Request-ID": requestId,
                    ...headers
                },
                body: body === undefined
                    ? undefined
                    : JSON.stringify(body),
                signal: controller.signal
            });

            const text = await response.text();

            let data = null;

            if (text) {
                try {
                    data = JSON.parse(text);
                } catch {
                    throw new ApiError(
                        "Server returned invalid JSON",
                        response.status,
                        false
                    );
                }
            }

            if (!response.ok) {
                throw new ApiError(
                    data?.detail || `HTTP ${response.status}`,
                    response.status,
                    [408, 429, 500, 502, 503, 504].includes(
                        response.status
                    )
                );
            }

            this.events.emit("request:success", {
                requestId,
                durationMs: performance.now() - started
            });

            return data;

        } catch (error) {
            if (controller.signal.aborted) {
                throw new ApiError(
                    "Request cancelled or timed out",
                    0,
                    true
                );
            }

            if (error instanceof ApiError) {
                throw error;
            }

            throw new ApiError(
                `Network failure: ${error.message}`,
                0,
                true
            );

        } finally {
            clearTimeout(timer);

            if (signal) {
                signal.removeEventListener("abort", onAbort);
            }

            this.events.emit("request:finish", {
                requestId,
                durationMs: performance.now() - started
            });
        }
    }

    async requestWithRetry(path, options = {}) {
        let attempt = 0;

        while (true) {
            try {
                return await this.request(path, options);

            } catch (error) {
                if (
                    !(error instanceof ApiError) ||
                    !error.retryable ||
                    attempt >= CONFIG.maxRetries
                ) {
                    throw error;
                }

                // Exponential backoff with randomized jitter.
                const delay =
                    CONFIG.retryDelayMs * (2 ** attempt) *
                    (0.5 + Math.random());

                await sleep(delay);

                attempt++;
            }
        }
    }

    async health() {
        return this.request("/health");
    }

    async createTask(task) {
        const payload = validateTask(task);

        return this.requestWithRetry("/tasks", {
            method: "POST",
            body: payload,
            headers: {
                "Idempotency-Key": randomUUID()
            }
        });
    }

    async getTask(id) {
        if (typeof id !== "string" || !id.trim()) {
            throw new ValidationError("Task ID is required");
        }

        return this.request(`/tasks/${encodeURIComponent(id)}`);
    }

    async listTasks({
        limit = 20,
        offset = 0,
        taskStatus
    } = {}) {
        if (
            !Number.isInteger(limit) ||
            limit < 1 ||
            limit > 100
        ) {
            throw new ValidationError("Invalid pagination limit");
        }

        if (!Number.isInteger(offset) || offset < 0) {
            throw new ValidationError("Invalid pagination offset");
        }

        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset)
        });

        if (taskStatus) {
            params.set("task_status", taskStatus);
        }

        return this.request(`/tasks?${params}`);
    }

    async updateTask(id, changes) {
        if (!changes || typeof changes !== "object") {
            throw new ValidationError("Invalid update payload");
        }

        return this.request(`/tasks/${encodeURIComponent(id)}`, {
            method: "PATCH",
            body: changes
        });
    }

    async deleteTask(id) {
        return this.request(`/tasks/${encodeURIComponent(id)}`, {
            method: "DELETE"
        });
    }
}

// ---------------------------------------------------------
// Bounded asynchronous worker pool
// ---------------------------------------------------------

class AsyncWorkerPool {
    constructor(concurrency = 5) {
        if (!Number.isInteger(concurrency) || concurrency < 1) {
            throw new ValidationError("Invalid concurrency limit");
        }

        this.concurrency = concurrency;
        this.active = 0;
        this.completed = 0;
        this.failed = 0;
    }

    async run(items, operation) {
        if (!Array.isArray(items)) {
            throw new ValidationError("Items must be an array");
        }

        if (items.length > CONFIG.maxBatchSize) {
            throw new ValidationError("Batch exceeds maximum size");
        }

        const results = new Array(items.length);
        let nextIndex = 0;

        const worker = async () => {
            while (true) {
                const index = nextIndex++;

                if (index >= items.length) {
                    return;
                }

                this.active++;

                try {
                    results[index] = await operation(items[index], index);
                    this.completed++;

                } catch (error) {
                    results[index] = {
                        error: error.message,
                        failed: true
                    };

                    this.failed++;

                } finally {
                    this.active--;
                }
            }
        };

        const workerCount = Math.min(
            this.concurrency,
            items.length
        );

        await Promise.all(
            Array.from(
                { length: workerCount },
                () => worker()
            )
        );

        return {
            results,
            statistics: {
                completed: this.completed,
                failed: this.failed,
                concurrency: this.concurrency
            }
        };
    }
}

// ---------------------------------------------------------
// Request cancellation
// ---------------------------------------------------------

async function demonstrateCancellation(client) {
    const controller = new AbortController();

    const promise = client.request("/demo/offloaded-blocking", {
        signal: controller.signal,
        timeoutMs: 10000
    });

    setTimeout(() => {
        controller.abort();
    }, 100);

    try {
        await promise;
    } catch (error) {
        console.log("Cancellation demonstration:", error.message);
    }
}

// ---------------------------------------------------------
// Event-loop demonstration
// ---------------------------------------------------------

async function demonstrateEventLoop() {
    console.log("\nEvent-loop scheduling demonstration");

    const started = performance.now();

    const tasks = Array.from({ length: 5 }, async (_, index) => {
        await sleep(100);

        return {
            task: index + 1,
            completed: true
        };
    });

    const results = await Promise.all(tasks);

    console.log({
        results,
        elapsedMs: Math.round(performance.now() - started)
    });

    console.log(
        "The timers yield control instead of blocking the event loop."
    );
}

// ---------------------------------------------------------
// Event-driven monitoring
// ---------------------------------------------------------

function configureMonitoring(client) {
    client.events.on("request:start", event => {
        console.log(
            `[START] ${event.method} ${event.path} ${event.requestId}`
        );
    });

    client.events.on("request:success", event => {
        console.log(
            `[SUCCESS] ${event.requestId} ` +
            `${event.durationMs.toFixed(2)}ms`
        );
    });

    client.events.on("request:finish", event => {
        if (event.durationMs > 2000) {
            console.warn(
                `[SLOW REQUEST] ${event.requestId}`
            );
        }
    });
}

// ---------------------------------------------------------
// Application workflow
// ---------------------------------------------------------

async function main() {
    const client = new AsyncFastAPIClient(
        CONFIG.baseUrl,
        CONFIG.timeoutMs
    );

    configureMonitoring(client);

    try {
        console.log("\nChecking API health");

        console.log(await client.health());

        const tasks = [
            {
                title: "Implement asynchronous database access",
                description: "Use a shared connection pool."
            },
            {
                title: "Measure event-loop latency",
                description: "Identify blocking operations."
            },
            {
                title: "Implement request cancellation",
                description: "Handle abandoned client requests."
            },
            {
                title: "Configure connection limits",
                description: "Prevent database overload."
            }
        ];

        console.log("\nCreating tasks");

        const creationPool = new AsyncWorkerPool(
            CONFIG.concurrency
        );

        const created = await creationPool.run(
            tasks,
            task => client.createTask(task)
        );

        console.log(created);

        const validTasks = created.results.filter(
            item => item && !item.failed && item.id
        );

        console.log("\nRetrieving created tasks");

        const retrievalPool = new AsyncWorkerPool(3);

        const retrieved = await retrievalPool.run(
            validTasks,
            task => client.getTask(task.id)
        );

        console.log(retrieved);

        console.log("\nRetrieving aggregate task list");

        console.log(
            await client.listTasks({
                limit: 20,
                offset: 0
            })
        );

        console.log("\nDemonstrating asynchronous scheduling");

        await demonstrateEventLoop();

        console.log("\nDemonstrating cancellation");

        await demonstrateCancellation(client);

    } catch (error) {
        console.error("Application failure:", error.message);
        process.exitCode = 1;
    }
}

main();
