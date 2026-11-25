"use strict";

/*
 * WebSocket Real-Time Communication Client
 *
 * Runtime: Node.js 22+
 *
 * Features:
 * - Native WebSocket API
 * - Event-driven communication
 * - Connection lifecycle state machine
 * - Automatic reconnection with exponential backoff
 * - Heartbeat and timeout detection
 * - Message validation
 * - Bounded outbound queue
 * - Request-response correlation
 * - Graceful shutdown
 *
 * Run:
 *   node websocket_client.js
 *
 * Server:
 *   ws://127.0.0.1:8765
 */

const { randomUUID } = require("node:crypto");
const { EventEmitter } = require("node:events");


const STATES = Object.freeze({
    IDLE: "idle",
    CONNECTING: "connecting",
    OPEN: "open",
    RECONNECTING: "reconnecting",
    CLOSING: "closing",
    CLOSED: "closed",
    FAILED: "failed"
});

const DEFAULTS = Object.freeze({
    url: "ws://127.0.0.1:8765",
    maxRetries: 5,
    initialBackoff: 500,
    maximumBackoff: 15000,
    maximumQueue: 100,
    maximumMessageBytes: 1024 * 1024,
    heartbeatInterval: 20000,
    heartbeatTimeout: 10000
});


class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}


class ConnectionError extends Error {
    constructor(message) {
        super(message);
        this.name = "ConnectionError";
    }
}


class MessageQueue {

    constructor(maximumSize) {
        this.maximumSize = maximumSize;
        this.items = [];
    }

    enqueue(message) {
        if (this.items.length >= this.maximumSize) {
            throw new Error("Outbound queue capacity exceeded");
        }

        this.items.push(message);
    }

    dequeue() {
        return this.items.shift();
    }

    get size() {
        return this.items.length;
    }

    clear() {
        this.items.length = 0;
    }
}


class WebSocketClient extends EventEmitter {

    constructor(options = {}) {
        super();

        this.options = {
            ...DEFAULTS,
            ...options
        };

        this.validateOptions();

        this.state = STATES.IDLE;
        this.socket = null;

        this.queue = new MessageQueue(
            this.options.maximumQueue
        );

        this.retryCount = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.heartbeatDeadline = null;

        this.pendingRequests = new Map();

        this.intentionalShutdown = false;
        this.connectionGeneration = 0;

        this.metrics = {
            connections: 0,
            disconnections: 0,
            messagesReceived: 0,
            messagesSent: 0,
            failedMessages: 0,
            reconnections: 0
        };
    }

    validateOptions() {
        let parsed;

        try {
            parsed = new URL(this.options.url);
        } catch {
            throw new ValidationError("Invalid WebSocket URL");
        }

        if (!["ws:", "wss:"].includes(parsed.protocol)) {
            throw new ValidationError("Only ws and wss are supported");
        }

        for (const key of [
            "maxRetries",
            "initialBackoff",
            "maximumBackoff",
            "maximumQueue",
            "maximumMessageBytes",
            "heartbeatInterval",
            "heartbeatTimeout"
        ]) {
            if (
                !Number.isSafeInteger(this.options[key]) ||
                this.options[key] <= 0
            ) {
                throw new ValidationError(
                    `Invalid option: ${key}`
                );
            }
        }

        if (this.options.maximumBackoff <
            this.options.initialBackoff) {
            throw new ValidationError(
                "Maximum backoff must not be smaller than initial backoff"
            );
        }
    }

    transition(nextState) {

        const allowed = {
            idle: ["connecting", "closed"],
            connecting: ["open", "reconnecting", "closing", "failed"],
            open: ["reconnecting", "closing", "failed"],
            reconnecting: ["connecting", "closing", "failed"],
            closing: ["closed"],
            failed: ["connecting", "closing", "closed"],
            closed: []
        };

        if (!allowed[this.state].includes(nextState)) {
            throw new Error(
                `Invalid state transition: ${this.state} -> ${nextState}`
            );
        }

        const previous = this.state;
        this.state = nextState;

        this.emit("state", {
            previous,
            current: nextState,
            timestamp: Date.now()
        });
    }

    connect() {

        if (
            this.state === STATES.CLOSED ||
            this.state === STATES.CLOSING
        ) {
            throw new ConnectionError(
                "Cannot connect after shutdown"
            );
        }

        if (
            this.state === STATES.CONNECTING ||
            this.state === STATES.OPEN
        ) {
            return;
        }

        this.intentionalShutdown = false;

        this.transition(STATES.CONNECTING);

        const generation = ++this.connectionGeneration;

        let socket;

        try {
            socket = new WebSocket(this.options.url);
        } catch (error) {
            this.handleFailure(error, generation);
            return;
        }

        this.socket = socket;

        socket.addEventListener("open", () => {

            if (generation !== this.connectionGeneration) {
                socket.close();
                return;
            }

            if (this.state === STATES.RECONNECTING) {
                this.transition(STATES.CONNECTING);
            }

            this.transition(STATES.OPEN);

            this.retryCount = 0;
            this.metrics.connections++;

            this.emit("connected");

            this.startHeartbeat();
            this.flushQueue();
        });

        socket.addEventListener("message", event => {

            if (generation !== this.connectionGeneration) {
                return;
            }

            this.metrics.messagesReceived++;

            this.handleIncoming(event.data);
        });

        socket.addEventListener("error", error => {
            this.emit("error", error);
        });

        socket.addEventListener("close", event => {

            if (generation !== this.connectionGeneration) {
                return;
            }

            this.stopHeartbeat();

            this.metrics.disconnections++;

            this.rejectPendingRequests(
                new ConnectionError("Connection closed")
            );

            this.emit("disconnected", {
                code: event.code,
                reason: event.reason,
                clean: event.wasClean
            });

            if (this.intentionalShutdown) {
                if (this.state === STATES.CLOSING) {
                    this.transition(STATES.CLOSED);
                }
                return;
            }

            this.scheduleReconnect();
        });
    }

    handleIncoming(raw) {

        if (typeof raw !== "string") {
            this.emit("binary", raw);
            return;
        }

        let message;

        try {
            message = JSON.parse(raw);
        } catch {
            this.emit("protocolError", {
                reason: "Invalid JSON"
            });
            return;
        }

        if (
            message === null ||
            typeof message !== "object" ||
            Array.isArray(message)
        ) {
            this.emit("protocolError", {
                reason: "Expected an object"
            });
            return;
        }

        if (message.type === "pong") {
            this.heartbeatDeadline = null;
            this.emit("heartbeat");
            return;
        }

        if (message.type === "response" && message.requestId) {

            const pending = this.pendingRequests.get(
                message.requestId
            );

            if (pending) {
                clearTimeout(pending.timer);

                this.pendingRequests.delete(
                    message.requestId
                );

                pending.resolve(message.data);
            }
        }

        this.emit("message", message);
        this.emit(`event:${message.type}`, message);
    }

    serialize(message) {

        if (
            message === null ||
            typeof message !== "object" ||
            Array.isArray(message)
        ) {
            throw new ValidationError(
                "Messages must be objects"
            );
        }

        const serialized = JSON.stringify(message);

        if (
            Buffer.byteLength(serialized, "utf8") >
            this.options.maximumMessageBytes
        ) {
            throw new ValidationError(
                "Message exceeds maximum size"
            );
        }

        return serialized;
    }

    send(message) {

        const serialized = this.serialize(message);

        if (this.state === STATES.OPEN) {
            this.sendRaw(serialized);
            return;
        }

        if (
            this.state === STATES.CLOSED ||
            this.state === STATES.CLOSING ||
            this.state === STATES.FAILED
        ) {
            throw new ConnectionError(
                "Connection cannot accept messages"
            );
        }

        this.queue.enqueue(serialized);
    }

    sendRaw(serialized) {

        if (
            !this.socket ||
            this.socket.readyState !== WebSocket.OPEN
        ) {
            throw new ConnectionError(
                "Socket is not open"
            );
        }

        if (
            this.socket.bufferedAmount >
            this.options.maximumMessageBytes * 4
        ) {
            throw new ConnectionError(
                "Transport buffer limit exceeded"
            );
        }

        this.socket.send(serialized);

        this.metrics.messagesSent++;
    }

    flushQueue() {

        while (
            this.queue.size > 0 &&
            this.state === STATES.OPEN
        ) {
            const message = this.queue.dequeue();

            try {
                this.sendRaw(message);
            } catch (error) {
                this.metrics.failedMessages++;
                this.emit("sendError", error);
                break;
            }
        }
    }

    request(data, timeout = 5000) {

        if (this.state !== STATES.OPEN) {
            return Promise.reject(
                new ConnectionError(
                    "Requests require an open connection"
                )
            );
        }

        if (
            !Number.isSafeInteger(timeout) ||
            timeout <= 0
        ) {
            return Promise.reject(
                new ValidationError("Invalid request timeout")
            );
        }

        const requestId = randomUUID();

        return new Promise((resolve, reject) => {

            const timer = setTimeout(() => {
                this.pendingRequests.delete(requestId);

                reject(
                    new Error("Request timed out")
                );
            }, timeout);

            this.pendingRequests.set(requestId, {
                resolve,
                reject,
                timer
            });

            try {
                this.send({
                    type: "request",
                    requestId,
                    data
                });
            } catch (error) {
                clearTimeout(timer);
                this.pendingRequests.delete(requestId);
                reject(error);
            }
        });
    }

    startHeartbeat() {

        this.stopHeartbeat();

        this.heartbeatTimer = setInterval(() => {

            if (this.state !== STATES.OPEN) {
                return;
            }

            if (this.heartbeatDeadline !== null) {
                this.emit("heartbeatTimeout");

                this.socket.close(
                    4000,
                    "Heartbeat timeout"
                );

                return;
            }

            this.heartbeatDeadline =
                Date.now() + this.options.heartbeatTimeout;

            try {
                this.send({
                    type: "ping",
                    timestamp: Date.now()
                });
            } catch (error) {
                this.emit("error", error);
            }

        }, this.options.heartbeatInterval);
    }

    stopHeartbeat() {

        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }

        this.heartbeatDeadline = null;
    }

    handleFailure(error, generation) {

        if (generation !== this.connectionGeneration) {
            return;
        }

        this.emit("error", error);
        this.scheduleReconnect();
    }

    scheduleReconnect() {

        if (
            this.intentionalShutdown ||
            this.state === STATES.CLOSED ||
            this.state === STATES.CLOSING
        ) {
            return;
        }

        if (this.retryCount >= this.options.maxRetries) {
            this.transition(STATES.FAILED);

            this.emit("reconnectFailed");

            return;
        }

        if (this.state !== STATES.RECONNECTING) {
            this.transition(STATES.RECONNECTING);
        }

        const exponential = Math.min(
            this.options.initialBackoff *
                (2 ** this.retryCount),
            this.options.maximumBackoff
        );

        // Jitter prevents many clients from reconnecting simultaneously.
        const delay = Math.floor(
            exponential * (0.5 + Math.random() * 0.5)
        );

        this.retryCount++;
        this.metrics.reconnections++;

        this.emit("reconnecting", {
            attempt: this.retryCount,
            delay
        });

        this.reconnectTimer = setTimeout(() => {
            if (this.state === STATES.RECONNECTING) {
                this.connect();
            }
        }, delay);
    }

    rejectPendingRequests(error) {

        for (const pending of this.pendingRequests.values()) {
            clearTimeout(pending.timer);
            pending.reject(error);
        }

        this.pendingRequests.clear();
    }

    close(code = 1000, reason = "Normal shutdown") {

        if (this.state === STATES.CLOSED) {
            return;
        }

        this.intentionalShutdown = true;

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        this.stopHeartbeat();

        this.queue.clear();

        this.rejectPendingRequests(
            new ConnectionError("Client shutting down")
        );

        if (this.state === STATES.IDLE ||
            this.state === STATES.FAILED) {
            this.transition(STATES.CLOSED);
            return;
        }

        if (this.state !== STATES.CLOSING) {
            this.transition(STATES.CLOSING);
        }

        if (
            this.socket &&
            this.socket.readyState < WebSocket.CLOSING
        ) {
            this.socket.close(code, reason);
        } else {
            this.transition(STATES.CLOSED);
        }
    }

    getStatistics() {
        return {
            state: this.state,
            queuedMessages: this.queue.size,
            pendingRequests: this.pendingRequests.size,
            ...this.metrics
        };
    }
}


async function main() {

    const client = new WebSocketClient({
        url: DEFAULTS.url
    });

    client.on("state", event => {
        console.log("State:", event);
    });

    client.on("connected", () => {
        console.log("WebSocket connected");

        client.send({
            type: "echo",
            data: "Persistent connection established"
        });

        client.send({
            type: "metrics"
        });
    });

    client.on("message", message => {
        console.log("Received:", message);
    });

    client.on("reconnecting", event => {
        console.log("Reconnecting:", event);
    });

    client.on("disconnected", event => {
        console.log("Disconnected:", event);
    });

    client.on("protocolError", event => {
        console.error("Protocol error:", event);
    });

    client.on("error", error => {
        console.error("Connection error:", error.message);
    });

    client.on("reconnectFailed", () => {
        console.error("Maximum reconnection attempts reached");
    });

    process.on("SIGINT", () => {
        console.log("\nShutting down...");
        client.close();
    });

    client.connect();

    process.on("exit", () => {
        console.log(
            "Final statistics:",
            client.getStatistics()
        );
    });
}


if (typeof WebSocket === "undefined") {
    console.error(
        "This application requires Node.js 22+ with native WebSocket support."
    );
    process.exitCode = 1;
} else {
    main().catch(error => {
        console.error(error);
        process.exitCode = 1;
    });
}
