"use strict";

/*
 * Background Tasks
 * Asynchronous jobs, task queues, worker processes and policies.
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library only.
 *
 * Demonstrates:
 * - Event-driven task scheduling.
 * - Priority queues.
 * - Asynchronous workers.
 * - Promise-based execution.
 * - Retry and dead-letter policies.
 * - Idempotency.
 * - Task dependencies.
 * - Worker concurrency limits.
 * - Graceful shutdown.
 */

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");

// ============================================================
// 1. DOMAIN CONSTANTS
// ============================================================

const STATUS = Object.freeze({
    PENDING: "pending",
    QUEUED: "queued",
    RUNNING: "running",
    RETRY_WAIT: "retry_wait",
    COMPLETED: "completed",
    FAILED: "failed",
    DEAD_LETTER: "dead_letter",
    CANCELLED: "cancelled"
});

const PRIORITY = Object.freeze({
    CRITICAL: 1,
    HIGH: 3,
    NORMAL: 5,
    LOW: 8
});

const TERMINAL = new Set([
    STATUS.COMPLETED,
    STATUS.DEAD_LETTER,
    STATUS.CANCELLED
]);

const TRANSITIONS = Object.freeze({
    pending: new Set(["queued", "cancelled"]),
    queued: new Set(["running", "cancelled"]),
    running: new Set([
        "completed",
        "retry_wait",
        "failed",
        "dead_letter"
    ]),
    retry_wait: new Set(["queued", "cancelled", "dead_letter"]),
    failed: new Set(["queued", "dead_letter"])
});

class TaskError extends Error {}
class ValidationError extends TaskError {}
class InvalidTransitionError extends TaskError {}
class PermanentTaskError extends TaskError {}

// ============================================================
// 2. UTILITIES
// ============================================================

function sleep(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

function validateObject(value, field) {
    if (
        value === null ||
        typeof value !== "object" ||
        Array.isArray(value)
    ) {
        throw new ValidationError(`${field} must be an object.`);
    }
}

function validateRetryPolicy(policy) {
    const normalized = {
        maxAttempts: policy?.maxAttempts ?? 3,
        initialDelay: policy?.initialDelay ?? 100,
        maxDelay: policy?.maxDelay ?? 10000,
        multiplier: policy?.multiplier ?? 2
    };

    if (
        !Number.isInteger(normalized.maxAttempts) ||
        normalized.maxAttempts < 1 ||
        normalized.initialDelay < 0 ||
        normalized.maxDelay < 0 ||
        normalized.multiplier < 1
    ) {
        throw new ValidationError("Invalid retry policy.");
    }

    return Object.freeze(normalized);
}

// ============================================================
// 3. TASK ENTITY
// ============================================================

class Task {
    constructor({
        type,
        payload,
        priority = PRIORITY.NORMAL,
        retryPolicy = {},
        idempotencyKey = null,
        dependencies = [],
        scheduledAt = Date.now()
    }) {
        if (
            typeof type !== "string" ||
            !type.trim() ||
            type.length > 100
        ) {
            throw new ValidationError("Invalid task type.");
        }

        validateObject(payload, "payload");

        if (!Number.isInteger(priority) || priority < 1 || priority > 10) {
            throw new ValidationError("Priority must be between 1 and 10.");
        }

        if (!Array.isArray(dependencies)) {
            throw new ValidationError("Dependencies must be an array.");
        }

        this.id = crypto.randomUUID();
        this.type = type;
        this.payload = structuredClone(payload);
        this.priority = priority;
        this.retryPolicy = validateRetryPolicy(retryPolicy);
        this.idempotencyKey = idempotencyKey;
        this.dependencies = [...new Set(dependencies)];
        this.status = STATUS.PENDING;
        this.attempts = 0;
        this.result = null;
        this.error = null;
        this.workerId = null;
        this.createdAt = Date.now();
        this.updatedAt = Date.now();
        this.scheduledAt = scheduledAt;
        this.completedAt = null;
        this.version = 0;
    }

    transition(nextStatus) {
        if (!TRANSITIONS[this.status]?.has(nextStatus)) {
            throw new InvalidTransitionError(
                `Invalid transition: ${this.status} -> ${nextStatus}`
            );
        }

        this.status = nextStatus;
        this.updatedAt = Date.now();
        this.version++;
    }

    snapshot() {
        return {
            id: this.id,
            type: this.type,
            status: this.status,
            priority: this.priority,
            attempts: this.attempts,
            workerId: this.workerId,
            error: this.error,
            createdAt: this.createdAt,
            updatedAt: this.updatedAt,
            completedAt: this.completedAt,
            version: this.version
        };
    }
}

// ============================================================
// 4. BINARY HEAP PRIORITY QUEUE
// ============================================================

class PriorityTaskQueue {
    constructor() {
        this.heap = [];
        this.sequence = 0;
    }

    higherPriority(a, b) {
        if (a.priority !== b.priority) {
            return a.priority < b.priority;
        }

        return a.sequence < b.sequence;
    }

    push(taskId, priority) {
        const item = {
            taskId,
            priority,
            sequence: this.sequence++
        };

        this.heap.push(item);

        let index = this.heap.length - 1;

        while (index > 0) {
            const parent = Math.floor((index - 1) / 2);

            if (!this.higherPriority(this.heap[index], this.heap[parent])) {
                break;
            }

            [this.heap[index], this.heap[parent]] =
                [this.heap[parent], this.heap[index]];

            index = parent;
        }
    }

    pop() {
        if (this.heap.length === 0) {
            return null;
        }

        const result = this.heap[0];
        const last = this.heap.pop();

        if (this.heap.length > 0) {
            this.heap[0] = last;

            let index = 0;

            while (true) {
                const left = index * 2 + 1;
                const right = index * 2 + 2;
                let smallest = index;

                if (
                    left < this.heap.length &&
                    this.higherPriority(this.heap[left], this.heap[smallest])
                ) {
                    smallest = left;
                }

                if (
                    right < this.heap.length &&
                    this.higherPriority(this.heap[right], this.heap[smallest])
                ) {
                    smallest = right;
                }

                if (smallest === index) break;

                [this.heap[index], this.heap[smallest]] =
                    [this.heap[smallest], this.heap[index]];

                index = smallest;
            }
        }

        return result.taskId;
    }

    get size() {
        return this.heap.length;
    }
}

// ============================================================
// 5. TASK STORE
// ============================================================

class TaskStore {
    constructor() {
        this.tasks = new Map();
        this.idempotency = new Map();
    }

    create(task) {
        if (task.idempotencyKey) {
            const existingId = this.idempotency.get(task.idempotencyKey);

            if (existingId) {
                return this.get(existingId);
            }
        }

        if (this.tasks.has(task.id)) {
            throw new ValidationError("Duplicate task identifier.");
        }

        for (const dependency of task.dependencies) {
            if (!this.tasks.has(dependency)) {
                throw new ValidationError(
                    `Unknown dependency: ${dependency}`
                );
            }
        }

        this.tasks.set(task.id, task);

        if (task.idempotencyKey) {
            this.idempotency.set(task.idempotencyKey, task.id);
        }

        return task;
    }

    get(id) {
        const task = this.tasks.get(id);

        if (!task) {
            throw new ValidationError(`Task not found: ${id}`);
        }

        return task;
    }

    all() {
        return [...this.tasks.values()];
    }

    dependenciesCompleted(task) {
        return task.dependencies.every(
            id => this.get(id).status === STATUS.COMPLETED
        );
    }
}

// ============================================================
// 6. HANDLER REGISTRY
// ============================================================

class HandlerRegistry {
    constructor() {
        this.handlers = new Map();
    }

    register(type, handler) {
        if (typeof handler !== "function") {
            throw new ValidationError("Handler must be a function.");
        }

        if (this.handlers.has(type)) {
            throw new ValidationError(`Handler already exists: ${type}`);
        }

        this.handlers.set(type, handler);
    }

    get(type) {
        const handler = this.handlers.get(type);

        if (!handler) {
            throw new ValidationError(`Unknown task type: ${type}`);
        }

        return handler;
    }
}

// ============================================================
// 7. BACKGROUND TASK SERVICE
// ============================================================

class BackgroundTaskService extends EventEmitter {
    constructor({ concurrency = 3 } = {}) {
        super();

        if (!Number.isInteger(concurrency) || concurrency < 1) {
            throw new ValidationError("Invalid worker concurrency.");
        }

        this.store = new TaskStore();
        this.queue = new PriorityTaskQueue();
        this.registry = new HandlerRegistry();
        this.concurrency = concurrency;

        this.active = 0;
        this.sequence = 0;
        this.running = false;
        this.pumping = false;

        this.deadLetters = [];
        this.retryTimers = new Set();

        this.metrics = {
            submitted: 0,
            completed: 0,
            failed: 0,
            retried: 0,
            deadLettered: 0
        };
    }

    register(type, handler) {
        this.registry.register(type, handler);
    }

    submit(task) {
        const stored = this.store.create(task);

        if (stored !== task) {
            return stored;
        }

        this.metrics.submitted++;

        if (task.scheduledAt <= Date.now()) {
            this.enqueue(task);
        }

        this.emit("submitted", task.snapshot());

        return task;
    }

    enqueue(task) {
        if (TERMINAL.has(task.status)) return;

        if (
            task.status === STATUS.PENDING ||
            task.status === STATUS.RETRY_WAIT
        ) {
            if (!this.store.dependenciesCompleted(task)) {
                return;
            }

            task.transition(STATUS.QUEUED);
        }

        if (task.status !== STATUS.QUEUED) return;

        this.queue.push(task.id, task.priority);
        this.emit("queued", task.snapshot());

        this.pump();
    }

    start() {
        this.running = true;

        for (const task of this.store.all()) {
            if (
                task.status === STATUS.PENDING &&
                task.scheduledAt <= Date.now()
            ) {
                this.enqueue(task);
            }
        }

        this.pump();
    }

    pump() {
        if (!this.running || this.pumping) return;

        this.pumping = true;

        try {
            while (
                this.running &&
                this.active < this.concurrency &&
                this.queue.size > 0
            ) {
                const taskId = this.queue.pop();
                if (!taskId) break;

                const task = this.store.get(taskId);

                if (task.status !== STATUS.QUEUED) continue;

                this.active++;

                this.execute(task)
                    .catch(error => {
                        this.emit("workerError", error);
                    })
                    .finally(() => {
                        this.active--;
                        this.emit("capacityAvailable");
                        this.pump();
                    });
            }
        } finally {
            this.pumping = false;
        }
    }

    async execute(task) {
        if (!this.store.dependenciesCompleted(task)) {
            task.transition(STATUS.PENDING);
            return;
        }

        task.transition(STATUS.RUNNING);
        task.attempts++;
        task.workerId = `worker-${++this.sequence}`;

        this.emit("started", task.snapshot());

        try {
            const handler = this.registry.get(task.type);

            // Each attempt receives a fresh payload copy.
            const result = await handler(structuredClone(task.payload));

            if (task.status !== STATUS.RUNNING) return;

            task.result = result;
            task.completedAt = Date.now();
            task.transition(STATUS.COMPLETED);

            this.metrics.completed++;

            this.emit("completed", {
                task: task.snapshot(),
                result
            });

            // Tasks waiting on this task can now become eligible.
            for (const dependent of this.store.all()) {
                if (
                    dependent.dependencies.includes(task.id) &&
                    dependent.status === STATUS.PENDING
                ) {
                    this.enqueue(dependent);
                }
            }

        } catch (error) {
            await this.handleFailure(task, error);
        }
    }

    async handleFailure(task, error) {
        if (task.status !== STATUS.RUNNING) return;

        task.error = error.message || "Unknown task failure";

        const permanent = error instanceof PermanentTaskError;
        const exhausted =
            task.attempts >= task.retryPolicy.maxAttempts;

        if (permanent || exhausted) {
            task.transition(STATUS.DEAD_LETTER);

            this.deadLetters.push(task.id);
            this.metrics.failed++;
            this.metrics.deadLettered++;

            this.emit("deadLetter", task.snapshot());
            return;
        }

        task.transition(STATUS.RETRY_WAIT);
        this.metrics.retried++;

        const policy = task.retryPolicy;

        const baseDelay = Math.min(
            policy.initialDelay *
                Math.pow(policy.multiplier, task.attempts - 1),
            policy.maxDelay
        );

        const jitteredDelay =
            baseDelay * (0.8 + Math.random() * 0.4);

        task.scheduledAt = Date.now() + jitteredDelay;

        this.emit("retryScheduled", {
            task: task.snapshot(),
            delay: jitteredDelay
        });

        // Timers are tracked so shutdown can cancel them.
        const timer = setTimeout(() => {
            this.retryTimers.delete(timer);

            if (!this.running || task.status !== STATUS.RETRY_WAIT) {
                return;
            }

            this.enqueue(task);
        }, jitteredDelay);

        this.retryTimers.add(timer);
    }

    cancel(taskId) {
        const task = this.store.get(taskId);

        if (
            ![
                STATUS.PENDING,
                STATUS.QUEUED,
                STATUS.RETRY_WAIT
            ].includes(task.status)
        ) {
            throw new InvalidTransitionError(
                "Only waiting tasks can be cancelled."
            );
        }

        task.transition(STATUS.CANCELLED);
        this.emit("cancelled", task.snapshot());
    }

    async shutdown({ drain = true, timeout = 5000 } = {}) {
        this.running = false;

        for (const timer of this.retryTimers) {
            clearTimeout(timer);
        }

        this.retryTimers.clear();

        if (!drain) return;

        const deadline = Date.now() + timeout;

        while (this.active > 0 && Date.now() < deadline) {
            await sleep(20);
        }

        if (this.active > 0) {
            this.emit("shutdownTimeout", {
                activeWorkers: this.active
            });
        }
    }

    report() {
        const counts = Object.fromEntries(
            Object.values(STATUS).map(status => [
                status,
                this.store.all().filter(t => t.status === status).length
            ])
        );

        return {
            metrics: { ...this.metrics },
            states: counts,
            queueSize: this.queue.size,
            activeWorkers: this.active,
            deadLetters: [...this.deadLetters]
        };
    }
}

// ============================================================
// 8. SAMPLE HANDLERS
// ============================================================

async function generateReport(payload) {
    if (
        typeof payload.name !== "string" ||
        !payload.name.trim()
    ) {
        throw new PermanentTaskError("Invalid report name.");
    }

    await sleep(80);

    return {
        name: payload.name,
        recordsProcessed: 2500,
        generatedAt: new Date().toISOString()
    };
}

async function sendEmail(payload) {
    if (
        typeof payload.email !== "string" ||
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)
    ) {
        throw new PermanentTaskError("Invalid email address.");
    }

    await sleep(50);

    return {
        recipient: payload.email,
        status: "accepted"
    };
}

async function unreliableTask(payload) {
    if (payload.failuresRemaining > 0) {
        payload.failuresRemaining--;
        throw new Error("Temporary external service failure.");
    }

    return { status: "recovered" };
}

// ============================================================
// 9. EXECUTABLE EXAMPLE
// ============================================================

async function main() {
    const service = new BackgroundTaskService({
        concurrency: 3
    });

    service.register("report", generateReport);
    service.register("email", sendEmail);
    service.register("unreliable", unreliableTask);

    service.on("started", task => {
        console.log(`Started: ${task.type} (${task.id.slice(0, 8)})`);
    });

    service.on("completed", event => {
        console.log("Completed:", event.task.type);
    });

    service.on("retryScheduled", event => {
        console.log(
            `Retry ${event.task.attempts} in ${event.delay.toFixed(0)} ms`
        );
    });

    service.on("deadLetter", task => {
        console.error("Dead-lettered:", task.id);
    });

    const report = service.submit(new Task({
        type: "report",
        payload: { name: "Monthly Operations" },
        priority: PRIORITY.HIGH,
        idempotencyKey: "monthly-report-2026-11"
    }));

    const email = service.submit(new Task({
        type: "email",
        payload: { email: "operations@example.com" },
        dependencies: [report.id]
    }));

    const retry = service.submit(new Task({
        type: "unreliable",
        payload: { failuresRemaining: 1 },
        retryPolicy: {
            maxAttempts: 3,
            initialDelay: 100,
            maxDelay: 1000
        }
    }));

    const duplicate = service.submit(new Task({
        type: "report",
        payload: { name: "Duplicate" },
        idempotencyKey: "monthly-report-2026-11"
    }));

    if (duplicate.id !== report.id) {
        throw new Error("Idempotency test failed.");
    }

    service.start();

    try {
        const deadline = Date.now() + 5000;

        while (
            Date.now() < deadline &&
            [report, email, retry].some(
                task => task.status !== STATUS.COMPLETED
            )
        ) {
            await sleep(20);
        }

        if (
            [report, email, retry].some(
                task => task.status !== STATUS.COMPLETED
            )
        ) {
            throw new Error("Task execution timed out.");
        }
    } finally {
        await service.shutdown({
            drain: true,
            timeout: 3000
        });
    }

    console.log("\nFINAL TASK STATES");

    for (const task of service.store.all()) {
        console.log(task.snapshot());
    }

    console.log("\nOPERATIONAL METRICS");
    console.log(JSON.stringify(service.report(), null, 2));

    if (retry.attempts !== 2) {
        throw new Error("Retry assertion failed.");
    }

    console.log("\nAll JavaScript demonstrations passed.");
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
