"use strict";

/*
 * MESSAGE QUEUE SYSTEM
 * Event-driven broker with producers, consumers, acknowledgments,
 * retry scheduling, dead-letter routing, and idempotency.
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library only.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");
const { setTimeout: sleep } = require("node:timers/promises");
const fs = require("node:fs/promises");

const MessageStatus = Object.freeze({
    READY: "READY",
    IN_FLIGHT: "IN_FLIGHT",
    ACKNOWLEDGED: "ACKNOWLEDGED",
    RETRY_PENDING: "RETRY_PENDING",
    DEAD_LETTERED: "DEAD_LETTERED"
});

class QueueError extends Error {}
class QueueCapacityError extends QueueError {}
class MessageNotFoundError extends QueueError {}
class AcknowledgmentError extends QueueError {}
class DuplicateMessageError extends QueueError {}

function validatePayload(payload) {
    if (
        payload === null ||
        typeof payload !== "object" ||
        Array.isArray(payload)
    ) {
        throw new TypeError("Message payload must be an object");
    }

    // JSON serialization also rejects circular structures and BigInt.
    const serialized = JSON.stringify(payload);

    if (serialized === undefined) {
        throw new TypeError("Payload cannot be serialized");
    }

    if (Buffer.byteLength(serialized, "utf8") > 1024 * 1024) {
        throw new RangeError("Message exceeds 1 MB");
    }

    return JSON.parse(serialized);
}

class Message {
    constructor({
        id = randomUUID(),
        payload,
        routingKey = "default",
        maxAttempts = 3
    }) {
        if (!id || typeof id !== "string") {
            throw new TypeError("Message ID must be a string");
        }

        if (!routingKey || typeof routingKey !== "string") {
            throw new TypeError("Routing key is required");
        }

        if (!Number.isInteger(maxAttempts) || maxAttempts < 1) {
            throw new RangeError("maxAttempts must be positive");
        }

        this.id = id;
        this.payload = validatePayload(payload);
        this.routingKey = routingKey;
        this.maxAttempts = maxAttempts;
        this.attempts = 0;
        this.status = MessageStatus.READY;
        this.createdAt = new Date().toISOString();
        this.availableAt = Date.now();
        this.consumerId = null;
        this.lastError = null;
        this.deliveredAt = null;
    }
}

class MessageQueue extends EventEmitter {
    constructor(name, {
        capacity = 1000,
        retryBaseDelay = 500,
        retryMaxDelay = 30000
    } = {}) {
        super();

        if (!name) throw new TypeError("Queue name is required");

        if (!Number.isInteger(capacity) || capacity < 1) {
            throw new RangeError("Invalid queue capacity");
        }

        this.name = name;
        this.capacity = capacity;
        this.retryBaseDelay = retryBaseDelay;
        this.retryMaxDelay = retryMaxDelay;

        this.ready = [];
        this.inFlight = new Map();
        this.retryWaiting = [];
        this.completed = [];
        this.deadLetters = [];

        this.metrics = {
            published: 0,
            delivered: 0,
            acknowledged: 0,
            retried: 0,
            failed: 0,
            rejected: 0,
            deadLettered: 0
        };

        this.closed = false;
    }

    get size() {
        return (
            this.ready.length +
            this.inFlight.size +
            this.retryWaiting.length
        );
    }

    assertOpen() {
        if (this.closed) {
            throw new QueueError(`Queue ${this.name} is closed`);
        }
    }

    publish(message) {
        this.assertOpen();

        if (!(message instanceof Message)) {
            throw new TypeError("Expected a Message instance");
        }

        if (this.size >= this.capacity) {
            this.metrics.rejected++;
            throw new QueueCapacityError(
                `Queue ${this.name} is full`
            );
        }

        const duplicate =
            this.ready.some(item => item.id === message.id) ||
            this.inFlight.has(message.id) ||
            this.retryWaiting.some(item => item.id === message.id) ||
            this.completed.some(item => item.id === message.id);

        if (duplicate) {
            throw new DuplicateMessageError(message.id);
        }

        message.status = MessageStatus.READY;
        this.ready.push(message);
        this.metrics.published++;

        this.emit("published", {
            queue: this.name,
            messageId: message.id
        });

        return message.id;
    }

    promoteRetries() {
        const now = Date.now();
        const remaining = [];

        for (const message of this.retryWaiting) {
            if (message.availableAt <= now) {
                message.status = MessageStatus.READY;
                this.ready.push(message);
                this.emit("retryReady", message.id);
            } else {
                remaining.push(message);
            }
        }

        this.retryWaiting = remaining;
    }

    receive(consumerId) {
        this.assertOpen();

        if (!consumerId) {
            throw new TypeError("Consumer ID is required");
        }

        this.promoteRetries();

        const message = this.ready.shift();

        if (!message) return null;

        message.status = MessageStatus.IN_FLIGHT;
        message.attempts++;
        message.consumerId = consumerId;
        message.deliveredAt = Date.now();

        this.inFlight.set(message.id, message);
        this.metrics.delivered++;

        this.emit("delivered", {
            messageId: message.id,
            consumerId,
            attempt: message.attempts
        });

        return message;
    }

    acknowledge(messageId, consumerId) {
        const message = this.inFlight.get(messageId);

        if (!message) {
            throw new MessageNotFoundError(messageId);
        }

        if (message.consumerId !== consumerId) {
            throw new AcknowledgmentError(
                "Consumer does not own this delivery"
            );
        }

        this.inFlight.delete(messageId);

        message.status = MessageStatus.ACKNOWLEDGED;
        message.acknowledgedAt = new Date().toISOString();
        message.consumerId = null;

        this.completed.push(message);
        this.metrics.acknowledged++;

        this.emit("acknowledged", message.id);
    }

    reject(messageId, consumerId, error, {
        requeue = true,
        delayMs
    } = {}) {
        const message = this.inFlight.get(messageId);

        if (!message) {
            throw new MessageNotFoundError(messageId);
        }

        if (message.consumerId !== consumerId) {
            throw new AcknowledgmentError(
                "Consumer does not own this delivery"
            );
        }

        this.inFlight.delete(messageId);

        message.consumerId = null;
        message.lastError = String(error);
        this.metrics.failed++;

        if (requeue && message.attempts < message.maxAttempts) {
            const exponentialDelay = Math.min(
                this.retryBaseDelay * 2 ** (message.attempts - 1),
                this.retryMaxDelay
            );

            const actualDelay = delayMs ?? exponentialDelay;

            if (!Number.isFinite(actualDelay) || actualDelay < 0) {
                throw new RangeError("Invalid retry delay");
            }

            message.availableAt = Date.now() + actualDelay;
            message.status = MessageStatus.RETRY_PENDING;

            this.retryWaiting.push(message);
            this.metrics.retried++;

            this.emit("retryScheduled", {
                messageId,
                delayMs: actualDelay
            });
        } else {
            this.deadLetter(message);
        }
    }

    deadLetter(message) {
        message.status = MessageStatus.DEAD_LETTERED;
        this.deadLetters.push(message);
        this.metrics.deadLettered++;

        this.emit("deadLettered", {
            messageId: message.id,
            reason: message.lastError
        });
    }

    recoverExpired(visibilityTimeoutMs) {
        if (
            !Number.isFinite(visibilityTimeoutMs) ||
            visibilityTimeoutMs <= 0
        ) {
            throw new RangeError("Invalid visibility timeout");
        }

        const now = Date.now();
        let recovered = 0;

        for (const [id, message] of this.inFlight) {
            if (now - message.deliveredAt < visibilityTimeoutMs) {
                continue;
            }

            this.inFlight.delete(id);
            message.consumerId = null;
            message.lastError = "Visibility timeout exceeded";

            if (message.attempts < message.maxAttempts) {
                message.status = MessageStatus.RETRY_PENDING;
                message.availableAt = now;
                this.retryWaiting.push(message);
                this.metrics.retried++;
            } else {
                this.deadLetter(message);
            }

            recovered++;
        }

        return recovered;
    }

    snapshot() {
        return {
            name: this.name,
            ready: this.ready.length,
            inFlight: this.inFlight.size,
            retryWaiting: this.retryWaiting.length,
            completed: this.completed.length,
            deadLetters: this.deadLetters.length,
            metrics: { ...this.metrics }
        };
    }

    close() {
        this.closed = true;
        this.emit("closed", this.name);
    }
}

class Broker extends EventEmitter {
    constructor() {
        super();
        this.queues = new Map();
    }

    declareQueue(name, options = {}) {
        if (this.queues.has(name)) {
            return this.queues.get(name);
        }

        const queue = new MessageQueue(name, options);

        queue.on("published", event => this.emit("published", event));
        queue.on("acknowledged", id => this.emit("acknowledged", id));
        queue.on("deadLettered", event => this.emit("deadLettered", event));

        this.queues.set(name, queue);
        this.emit("queueDeclared", name);

        return queue;
    }

    getQueue(name) {
        const queue = this.queues.get(name);

        if (!queue) {
            throw new QueueError(`Unknown queue: ${name}`);
        }

        return queue;
    }

    publish(queueName, options) {
        const queue = this.getQueue(queueName);
        return queue.publish(new Message(options));
    }

    snapshots() {
        return [...this.queues.values()].map(queue => queue.snapshot());
    }
}

class Producer {
    constructor(id, broker) {
        this.id = id;
        this.broker = broker;
    }

    async send(queueName, payload, routingKey = "default") {
        const messageId = this.broker.publish(queueName, {
            payload,
            routingKey
        });

        return {
            producerId: this.id,
            messageId,
            accepted: true
        };
    }
}

class Consumer {
    constructor(id, queue, handler) {
        this.id = id;
        this.queue = queue;
        this.handler = handler;
        this.running = false;
        this.stopped = false;
    }

    async processOne() {
        const message = this.queue.receive(this.id);

        if (!message) return false;

        try {
            await this.handler(message.payload, message);

            // ACK is sent only after successful application processing.
            this.queue.acknowledge(message.id, this.id);
        } catch (error) {
            this.queue.reject(
                message.id,
                this.id,
                error.message
            );
        }

        return true;
    }

    async start({
        concurrency = 1,
        pollIntervalMs = 100,
        maxIdlePolls = 5
    } = {}) {
        if (!Number.isInteger(concurrency) || concurrency < 1) {
            throw new RangeError("Invalid concurrency");
        }

        if (this.running) {
            throw new QueueError("Consumer is already running");
        }

        this.running = true;
        this.stopped = false;

        let idlePolls = 0;

        try {
            while (!this.stopped && idlePolls < maxIdlePolls) {
                const workers = Array.from(
                    { length: concurrency },
                    () => this.processOne()
                );

                const results = await Promise.all(workers);
                const processed = results.some(Boolean);

                if (processed) {
                    idlePolls = 0;
                } else {
                    idlePolls++;
                    await sleep(pollIntervalMs);
                }
            }
        } finally {
            this.running = false;
        }
    }

    stop() {
        this.stopped = true;
    }
}

class IdempotencyStore {
    constructor() {
        this.completedKeys = new Set();
    }

    async execute(key, operation) {
        if (!key) throw new TypeError("Idempotency key is required");

        if (this.completedKeys.has(key)) {
            return {
                duplicate: true,
                result: null
            };
        }

        const result = await operation();

        // Mark complete only after successful execution.
        this.completedKeys.add(key);

        return {
            duplicate: false,
            result
        };
    }
}

class PaymentService {
    constructor() {
        this.idempotency = new IdempotencyStore();
        this.processed = [];

    }

    async handle(payload) {
        const { transactionId, amount } = payload;

        if (
            typeof transactionId !== "string" ||
            transactionId.length === 0
        ) {
            throw new TypeError("Invalid transaction ID");
        }

        if (!Number.isFinite(amount) || amount <= 0) {
            throw new RangeError("Payment amount must be positive");
        }

        return this.idempotency.execute(
            transactionId,
            async () => {
                const payment = {
                    transactionId,
                    amount,
                    processedAt: new Date().toISOString()
                };

                this.processed.push(payment);
                return payment;
            }
        );
    }
}

async function demonstrate() {
    const broker = new Broker();

    broker.on("deadLettered", event => {
        console.error("Dead-letter event:", event);
    });

    broker.on("acknowledged", id => {
        console.log("ACK received:", id);
    });

    const payments = broker.declareQueue("payments", {
        capacity: 100,
        retryBaseDelay: 10,
        retryMaxDelay: 100
    });

    const producer = new Producer("payment-api", broker);
    const service = new PaymentService();

    const consumer = new Consumer(
        "payment-worker-01",
        payments,
        payload => service.handle(payload)
    );

    await producer.send("payments", {
        transactionId: "TX-1001",
        amount: 2500
    }, "payment.created");

    await producer.send("payments", {
        transactionId: "TX-1002",
        amount: 5000
    }, "payment.created");

    await producer.send("payments", {
        transactionId: "TX-1003",
        amount: -100
    }, "payment.created");

    // Process initial messages and retry failed deliveries.
    for (let attempt = 0; attempt < 3; attempt++) {
        await consumer.start({
            concurrency: 2,
            pollIntervalMs: 10,
            maxIdlePolls: 1
        });

        payments.promoteRetries();

        if (payments.size === 0) break;

        await sleep(20);
    }

    console.log("\nQUEUE METRICS");
    console.log(JSON.stringify(broker.snapshots(), null, 2));

    console.log("\nSUCCESSFUL PAYMENTS");
    console.log(service.processed);

    console.log("\nDEAD LETTERS");
    console.log(
        payments.deadLetters.map(message => ({
            id: message.id,
            attempts: message.attempts,
            error: message.lastError
        }))
    );

    await fs.writeFile(
        "queue-metrics.json",
        JSON.stringify(broker.snapshots(), null, 2),
        "utf8"
    );
}

async function demonstrateCapacity() {
    const queue = new MessageQueue("small", { capacity: 1 });

    queue.publish(new Message({
        id: "A",
        payload: { value: 1 }
    }));

    try {
        queue.publish(new Message({
            id: "B",
            payload: { value: 2 }
        }));
    } catch (error) {
        console.log("Capacity validation:", error.message);
    }
}

async function main() {
    try {
        await demonstrate();
        await demonstrateCapacity();
    } catch (error) {
        console.error("Application failure:", error);
        process.exitCode = 1;
    }
}

if (require.main === module) {
    main();
}

module.exports = {
    Message,
    MessageQueue,
    Broker,
    Producer,
    Consumer,
    IdempotencyStore,
    PaymentService,
    MessageStatus
};
