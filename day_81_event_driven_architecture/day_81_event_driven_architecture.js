"use strict";

/**
 * Event-Driven Architecture
 *
 * Features:
 * - Event producers and consumers
 * - Versioned event schemas
 * - Asynchronous event processing
 * - Consumer groups
 * - Independent subscriptions
 * - Idempotent delivery
 * - Retry with exponential backoff
 * - Dead-letter handling
 * - Event filtering
 * - Correlation IDs
 * - Event replay
 * - Graceful shutdown
 *
 * Runtime: Node.js 18+
 */

const { randomUUID } = require("node:crypto");
const fs = require("node:fs/promises");
const { EventEmitter } = require("node:events");

// ============================================================
// ERRORS
// ============================================================

class EventError extends Error {}
class SchemaError extends EventError {}
class DuplicateEventError extends EventError {}
class ConsumerError extends EventError {}

// ============================================================
// EVENT SCHEMA REGISTRY
// ============================================================

class SchemaRegistry {
    constructor() {
        this.schemas = new Map();
    }

    register(name, version, definition) {
        if (!name || !Number.isInteger(version) || version < 1) {
            throw new SchemaError("Invalid schema identity");
        }

        const key = `${name}:v${version}`;

        if (this.schemas.has(key)) {
            throw new SchemaError(`Schema already exists: ${key}`);
        }

        this.schemas.set(key, Object.freeze({
            required: { ...definition.required },
            optional: { ...definition.optional }
        }));
    }

    validate(name, version, payload) {
        const schema = this.schemas.get(`${name}:v${version}`);

        if (!schema) {
            throw new SchemaError(
                `Unknown event schema: ${name} v${version}`
            );
        }

        if (
            payload === null ||
            typeof payload !== "object" ||
            Array.isArray(payload)
        ) {
            throw new SchemaError("Payload must be an object");
        }

        const allowed = new Set([
            ...Object.keys(schema.required),
            ...Object.keys(schema.optional)
        ]);

        for (const key of Object.keys(payload)) {
            if (!allowed.has(key)) {
                throw new SchemaError(`Unexpected field: ${key}`);
            }
        }

        const validateFields = (fields, required) => {
            for (const [key, type] of Object.entries(fields)) {
                if (!Object.hasOwn(payload, key)) {
                    if (required) {
                        throw new SchemaError(
                            `Missing required field: ${key}`
                        );
                    }
                    continue;
                }

                const value = payload[key];

                if (
                    type === "number" &&
                    typeof value === "number" &&
                    !Number.isFinite(value)
                ) {
                    throw new SchemaError(
                        `Invalid numeric value: ${key}`
                    );
                }

                if (typeof value !== type) {
                    throw new SchemaError(
                        `Invalid type for ${key}: expected ${type}`
                    );
                }
            }
        };

        validateFields(schema.required, true);
        validateFields(schema.optional, false);
    }
}

// ============================================================
// EVENT FACTORY
// ============================================================

class EventFactory {
    constructor(registry) {
        this.registry = registry;
    }

    create({
        type,
        version = 1,
        producer,
        payload,
        correlationId = randomUUID(),
        eventId = randomUUID()
    }) {
        if (!producer || !type) {
            throw new EventError(
                "Event type and producer are required"
            );
        }

        this.registry.validate(type, version, payload);

        return Object.freeze({
            eventId,
            type,
            version,
            producer,
            payload: structuredClone(payload),
            correlationId,
            occurredAt: new Date().toISOString()
        });
    }
}

// ============================================================
// EVENT BROKER
// ============================================================

class EventBroker extends EventEmitter {
    constructor({
        registry,
        maxRetries = 3,
        retryDelayMs = 50,
        concurrency = 4
    }) {
        super();

        if (
            !Number.isInteger(maxRetries) ||
            maxRetries < 0 ||
            !Number.isInteger(concurrency) ||
            concurrency < 1
        ) {
            throw new EventError("Invalid broker configuration");
        }

        this.factory = new EventFactory(registry);
        this.maxRetries = maxRetries;
        this.retryDelayMs = retryDelayMs;
        this.concurrency = concurrency;

        this.subscriptions = new Map();
        this.events = new Map();
        this.processed = new Set();
        this.deadLetters = [];
        this.inFlight = new Set();
        this.closed = false;
    }

    subscribe({
        eventType,
        consumerName,
        handler,
        filter = () => true
    }) {
        if (this.closed) {
            throw new EventError("Broker is closed");
        }

        if (
            typeof handler !== "function" ||
            typeof filter !== "function"
        ) {
            throw new EventError("Invalid consumer configuration");
        }

        if (!this.subscriptions.has(eventType)) {
            this.subscriptions.set(eventType, new Map());
        }

        const group = this.subscriptions.get(eventType);

        if (group.has(consumerName)) {
            throw new EventError(
                `Duplicate consumer: ${consumerName}`
            );
        }

        group.set(consumerName, { handler, filter });

        this.emit("subscribed", {
            eventType,
            consumerName
        });
    }

    publish(input) {
        if (this.closed) {
            throw new EventError("Broker is closed");
        }

        const event = this.factory.create(input);

        if (this.events.has(event.eventId)) {
            throw new DuplicateEventError(
                `Duplicate event ID: ${event.eventId}`
            );
        }

        this.events.set(event.eventId, event);

        this.emit("published", event);

        return event;
    }

    async retry(handler, event, consumerName) {
        let lastError;

        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                await handler(event);

                return {
                    success: true,
                    attempts: attempt + 1
                };
            } catch (error) {
                lastError = error;

                this.emit("retry", {
                    eventId: event.eventId,
                    consumerName,
                    attempt: attempt + 1,
                    error: error.message
                });

                if (attempt < this.maxRetries) {
                    const delay = Math.min(
                        this.retryDelayMs * (2 ** attempt),
                        2000
                    );

                    await new Promise(resolve =>
                        setTimeout(resolve, delay)
                    );
                }
            }
        }

        return {
            success: false,
            attempts: this.maxRetries + 1,
            error: lastError
        };
    }

    async deliver(event, consumerName, subscription) {
        const key = `${event.eventId}:${consumerName}`;

        if (this.processed.has(key)) {
            return "ALREADY_PROCESSED";
        }

        if (!subscription.filter(event)) {
            return "FILTERED";
        }

        const result = await this.retry(
            subscription.handler,
            event,
            consumerName
        );

        if (result.success) {
            this.processed.add(key);

            this.emit("consumed", {
                eventId: event.eventId,
                consumerName,
                attempts: result.attempts
            });

            return "CONSUMED";
        }

        const record = {
            event,
            consumerName,
            attempts: result.attempts,
            error: result.error.message,
            failedAt: new Date().toISOString()
        };

        this.deadLetters.push(record);

        this.emit("deadLetter", record);

        return "DEAD_LETTER";
    }

    async dispatch(eventId) {
        if (this.closed) {
            throw new EventError("Broker is closed");
        }

        const event = this.events.get(eventId);

        if (!event) {
            throw new EventError("Event not found");
        }

        const subscribers =
            this.subscriptions.get(event.type);

        if (!subscribers || subscribers.size === 0) {
            return { broker: "NO_SUBSCRIBERS" };
        }

        const results = {};

        // Independent consumers are dispatched concurrently.
        const deliveries = [...subscribers.entries()].map(
            async ([name, subscription]) => {
                const result = await this.deliver(
                    event,
                    name,
                    subscription
                );

                results[name] = result;
            }
        );

        await Promise.all(deliveries);

        return results;
    }

    async replay(eventId, consumerName) {
        const event = this.events.get(eventId);

        if (!event) {
            throw new EventError("Event not found");
        }

        const subscriptions =
            this.subscriptions.get(event.type);

        const subscription =
            subscriptions?.get(consumerName);

        if (!subscription) {
            throw new EventError("Consumer not found");
        }

        const key = `${eventId}:${consumerName}`;

        this.processed.delete(key);

        return this.deliver(
            event,
            consumerName,
            subscription
        );
    }

    async publishBatch(inputs) {
        if (!Array.isArray(inputs)) {
            throw new EventError("Batch must be an array");
        }

        const events = inputs.map(input =>
            this.factory.create(input)
        );

        const identifiers = new Set();

        for (const event of events) {
            if (
                this.events.has(event.eventId) ||
                identifiers.has(event.eventId)
            ) {
                throw new DuplicateEventError(
                    `Duplicate batch event: ${event.eventId}`
                );
            }

            identifiers.add(event.eventId);
        }

        // Validate the entire batch before changing broker state.
        for (const event of events) {
            this.events.set(event.eventId, event);
            this.emit("published", event);
        }

        return events;
    }

    metrics() {
        return {
            published: this.events.size,
            consumed: this.processed.size,
            deadLetters: this.deadLetters.length,
            eventTypes: this.subscriptions.size
        };
    }

    async saveAudit(filename) {
        const snapshot = {
            generatedAt: new Date().toISOString(),
            events: [...this.events.values()],
            metrics: this.metrics(),
            deadLetters: this.deadLetters
        };

        const temporary = `${filename}.tmp`;

        await fs.writeFile(
            temporary,
            JSON.stringify(snapshot, null, 2),
            { encoding: "utf8", flag: "w" }
        );

        await fs.rename(temporary, filename);
    }

    close() {
        this.closed = true;
        this.emit("closed");
    }
}

// ============================================================
// DOMAIN SERVICES
// ============================================================

class OrderProducer {
    constructor(broker) {
        this.broker = broker;
    }

    createOrder(orderId, customerId, amount) {
        if (
            !orderId ||
            !customerId ||
            typeof amount !== "number" ||
            !Number.isFinite(amount) ||
            amount <= 0
        ) {
            throw new EventError("Invalid order details");
        }

        return this.broker.publish({
            type: "OrderCreated",
            producer: "OrderService",
            version: 1,
            payload: {
                orderId,
                customerId,
                amount
            }
        });
    }
}

class InventoryService {
    constructor() {
        this.reservations = new Map();
    }

    async handle(event) {
        const orderId = event.payload.orderId;

        if (this.reservations.has(orderId)) {
            return;
        }

        this.reservations.set(orderId, {
            reserved: true,
            timestamp: Date.now()
        });
    }
}

class PaymentService {
    constructor() {
        this.transactions = new Map();
    }

    async handle(event) {
        const { orderId, amount } = event.payload;

        if (this.transactions.has(orderId)) {
            return;
        }

        this.transactions.set(orderId, {
            amount,
            status: "AUTHORIZED"
        });
    }
}

class NotificationService {
    constructor() {
        this.messages = [];
    }

    async handle(event) {
        this.messages.push(
            `Order ${event.payload.orderId} created`
        );
    }
}

// ============================================================
// APPLICATION AND TESTS
// ============================================================

async function main() {
    const registry = new SchemaRegistry();

    registry.register("OrderCreated", 1, {
        required: {
            orderId: "string",
            customerId: "string",
            amount: "number"
        },
        optional: {
            channel: "string"
        }
    });

    const broker = new EventBroker({
        registry,
        maxRetries: 2,
        retryDelayMs: 10,
        concurrency: 4
    });

    const inventory = new InventoryService();
    const payments = new PaymentService();
    const notifications = new NotificationService();

    broker.on("published", event => {
        console.log(`PUBLISHED: ${event.eventId}`);
    });

    broker.on("deadLetter", record => {
        console.error(
            `DEAD LETTER: ${record.consumerName}`
        );
    });

    broker.subscribe({
        eventType: "OrderCreated",
        consumerName: "Inventory",
        handler: event => inventory.handle(event)
    });

    broker.subscribe({
        eventType: "OrderCreated",
        consumerName: "Payments",
        handler: event => payments.handle(event)
    });

    broker.subscribe({
        eventType: "OrderCreated",
        consumerName: "Notifications",
        handler: event => notifications.handle(event)
    });

    const producer = new OrderProducer(broker);

    const event = producer.createOrder(
        "ORD-2001",
        "CUST-100",
        4599.99
    );

    const result = await broker.dispatch(event.eventId);

    console.log("\nDELIVERY RESULTS");
    console.log(result);

    if (
        result.Inventory !== "CONSUMED" ||
        result.Payments !== "CONSUMED" ||
        result.Notifications !== "CONSUMED"
    ) {
        throw new ConsumerError("Expected consumers to succeed");
    }

    // Idempotent redispatch.
    const repeated = await broker.dispatch(event.eventId);

    if (
        !Object.values(repeated).every(
            value => value === "ALREADY_PROCESSED"
        )
    ) {
        throw new Error("Idempotency test failed");
    }

    // Event filtering.
    broker.subscribe({
        eventType: "OrderCreated",
        consumerName: "LargeOrders",
        filter: event => event.payload.amount >= 10000,
        handler: async () => {
            console.log("Large order detected");
        }
    });

    const filtered = await broker.dispatch(event.eventId);

    if (filtered.LargeOrders !== "FILTERED") {
        throw new Error("Filter test failed");
    }

    // Retry and dead-letter behavior.
    broker.subscribe({
        eventType: "OrderCreated",
        consumerName: "UnhealthyConsumer",
        handler: async () => {
            throw new Error("Downstream unavailable");
        }
    });

    const second = producer.createOrder(
        "ORD-2002",
        "CUST-101",
        1200
    );

    const failed = await broker.dispatch(second.eventId);

    if (failed.UnhealthyConsumer !== "DEAD_LETTER") {
        throw new Error("Dead-letter test failed");
    }

    console.log("\nMETRICS");
    console.log(broker.metrics());

    await broker.saveAudit("event_audit.json");

    console.log("\nAUDIT FILE WRITTEN");

    broker.close();
}

main().catch(error => {
    console.error("APPLICATION FAILURE:", error);
    process.exitCode = 1;
});
