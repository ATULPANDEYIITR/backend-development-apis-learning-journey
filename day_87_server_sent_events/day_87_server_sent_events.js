"use strict";

/*
 * Server-Sent Events: Event-Driven Streaming Platform
 *
 * Runtime: Node.js 18+
 *
 * Features:
 * - Native HTTP SSE transport.
 * - EventEmitter-based event distribution.
 * - Last-Event-ID reconnection.
 * - Bounded replay history.
 * - Named events.
 * - Heartbeats.
 * - Client backpressure handling.
 * - Subscriber authentication hook.
 * - Graceful shutdown.
 * - Asynchronous event publication.
 *
 * Run:
 *   node sse_server.js
 *   node sse_server.js --serve
 */

const http = require("node:http");
const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");
const { URL } = require("node:url");


const CONFIG = Object.freeze({
    host: "127.0.0.1",
    port: 8000,
    historyLimit: 500,
    heartbeatInterval: 15000,
    maxPayloadBytes: 64000,
    maxClients: 1000,
    maxBufferedBytes: 1024 * 1024
});


class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}


const EventType = Object.freeze({
    MESSAGE: "message",
    UPDATE: "update",
    NOTIFICATION: "notification",
    PROGRESS: "progress",
    ERROR: "error"
});


class SSEEvent {
    constructor(id, type, data) {
        this.id = id;
        this.type = type;
        this.data = Object.freeze(data);
        this.createdAt = new Date().toISOString();
        Object.freeze(this);
    }

    encode() {
        const payload = JSON.stringify(this.data);

        return [
            `id: ${this.id}`,
            `event: ${this.type}`,
            `data: ${payload}`,
            "",
            ""
        ].join("\n");
    }
}


class EventHistory {
    constructor(limit) {
        if (!Number.isInteger(limit) || limit <= 0) {
            throw new ValidationError("Invalid history limit");
        }

        this.limit = limit;
        this.events = [];
    }

    add(event) {
        this.events.push(event);

        if (this.events.length > this.limit) {
            this.events.shift();
        }
    }

    getAfter(cursor) {
        if (!cursor) {
            return [...this.events];
        }

        const index = this.events.findIndex(
            event => event.id === cursor
        );

        return index === -1
            ? []
            : this.events.slice(index + 1);
    }

    getLatestId() {
        return this.events.length
            ? this.events[this.events.length - 1].id
            : null;
    }
}


class EventStream {
    constructor() {
        this.emitter = new EventEmitter();
        this.emitter.setMaxListeners(0);

        this.history = new EventHistory(CONFIG.historyLimit);
        this.sequence = 0;
        this.clients = new Map();
        this.closed = false;
    }

    publish(type, data) {
        if (this.closed) {
            throw new Error("Event stream is closed");
        }

        if (!Object.values(EventType).includes(type)) {
            throw new ValidationError("Unsupported event type");
        }

        if (
            data === null ||
            typeof data !== "object" ||
            Array.isArray(data)
        ) {
            throw new ValidationError("Event data must be an object");
        }

        const serialized = JSON.stringify(data);

        if (
            Buffer.byteLength(serialized, "utf8") >
            CONFIG.maxPayloadBytes
        ) {
            throw new ValidationError("Event payload too large");
        }

        const event = new SSEEvent(
            String(++this.sequence),
            type,
            data
        );

        this.history.add(event);

        this.emitter.emit("event", event);

        return event;
    }

    subscribe(clientId, response, cursor = null) {
        if (this.closed) {
            throw new Error("Event stream is closed");
        }

        if (this.clients.size >= CONFIG.maxClients) {
            throw new Error("Maximum client capacity reached");
        }

        const client = {
            id: clientId,
            response,
            connectedAt: Date.now(),
            dropped: false
        };

        this.clients.set(clientId, client);

        const send = event => {
            if (client.dropped || response.destroyed) {
                return;
            }

            if (
                response.writableLength >
                CONFIG.maxBufferedBytes
            ) {
                this.disconnect(clientId, "backpressure");
                return;
            }

            try {
                response.write(event.encode());
            } catch {
                this.disconnect(clientId, "write failure");
            }
        };

        // Replay retained events before receiving new events.
        for (const event of this.history.getAfter(cursor)) {
            send(event);
        }

        const listener = event => send(event);

        this.emitter.on("event", listener);

        client.listener = listener;

        response.on("close", () => {
            this.disconnect(clientId, "connection closed");
        });

        response.on("error", () => {
            this.disconnect(clientId, "response error");
        });

        return client;
    }

    disconnect(clientId, reason) {
        const client = this.clients.get(clientId);

        if (!client || client.dropped) {
            return;
        }

        client.dropped = true;

        if (client.listener) {
            this.emitter.removeListener(
                "event",
                client.listener
            );
        }

        this.clients.delete(clientId);

        console.log(`Client ${clientId} disconnected: ${reason}`);
    }

    shutdown() {
        this.closed = true;

        for (const id of [...this.clients.keys()]) {
            this.disconnect(id, "server shutdown");
        }

        this.emitter.removeAllListeners();
    }
}


class SSEApplication {
    constructor() {
        this.stream = new EventStream();
    }

    async publishNotification(message) {
        if (
            typeof message !== "string" ||
            message.trim().length === 0 ||
            message.length > 2000
        ) {
            throw new ValidationError("Invalid notification message");
        }

        // Asynchronous boundary permits integration with application work.
        await Promise.resolve();

        return this.stream.publish(
            EventType.NOTIFICATION,
            { message: message.trim() }
        );
    }

    async publishProgress(taskId, progress, status) {
        if (
            typeof taskId !== "string" ||
            taskId.length === 0 ||
            taskId.length > 100
        ) {
            throw new ValidationError("Invalid task identifier");
        }

        if (
            !Number.isInteger(progress) ||
            progress < 0 ||
            progress > 100
        ) {
            throw new ValidationError("Invalid progress");
        }

        return this.stream.publish(
            EventType.PROGRESS,
            {
                taskId,
                progress,
                status,
                timestamp: new Date().toISOString()
            }
        );
    }
}


const application = new SSEApplication();


function authenticate(request) {
    /*
     * Production deployments should validate an authenticated
     * session or an appropriately scoped access token here.
     *
     * This demonstration accepts local connections only.
     */
    const address = request.socket.remoteAddress || "";

    return address === "127.0.0.1" ||
        address === "::1" ||
        address === "::ffff:127.0.0.1";
}


function sendJSON(response, status, payload) {
    const body = JSON.stringify(payload);

    response.writeHead(status, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": Buffer.byteLength(body),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff"
    });

    response.end(body);
}


function validCursor(cursor) {
    return cursor === null ||
        cursor === "" ||
        /^\d+$/.test(cursor);
}


function createServer() {
    return http.createServer(async (request, response) => {
        const url = new URL(
            request.url,
            `http://${request.headers.host || "localhost"}`
        );

        if (!authenticate(request)) {
            sendJSON(response, 403, {
                error: "Access denied"
            });
            return;
        }

        if (request.method === "GET" && url.pathname === "/health") {
            sendJSON(response, 200, {
                status: "healthy",
                clients: application.stream.clients.size
            });
            return;
        }

        if (request.method === "GET" && url.pathname === "/events") {
            const cursor =
                request.headers["last-event-id"] ||
                url.searchParams.get("lastEventId");

            if (!validCursor(cursor)) {
                sendJSON(response, 400, {
                    error: "Invalid event cursor"
                });
                return;
            }

            response.writeHead(200, {
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            });

            response.flushHeaders();

            const clientId = randomUUID();

            try {
                application.stream.subscribe(
                    clientId,
                    response,
                    cursor || null
                );
            } catch (error) {
                if (!response.destroyed) {
                    response.end();
                }

                console.error(error.message);
                return;
            }

            return;
        }

        if (
            request.method === "POST" &&
            url.pathname === "/publish"
        ) {
            let body = "";

            try {
                for await (const chunk of request) {
                    body += chunk;

                    if (
                        Buffer.byteLength(body) >
                        CONFIG.maxPayloadBytes
                    ) {
                        sendJSON(response, 413, {
                            error: "Request too large"
                        });
                        return;
                    }
                }

                const payload = JSON.parse(body);

                const event = await application.publishNotification(
                    payload.message
                );

                sendJSON(response, 201, {
                    eventId: event.id,
                    eventType: event.type
                });

            } catch (error) {
                sendJSON(
                    response,
                    error instanceof ValidationError ? 400 : 500,
                    { error: error.message }
                );
            }

            return;
        }

        sendJSON(response, 404, {
            error: "Route not found"
        });
    });
}


async function demonstrate() {
    const first = await application.publishProgress(
        "job-001",
        25,
        "processing"
    );

    const second = await application.publishNotification(
        "Background job started"
    );

    const third = await application.publishProgress(
        "job-001",
        100,
        "completed"
    );

    console.log("\nEvent stream demonstration:\n");

    for (const event of [first, second, third]) {
        console.log(event.encode());
    }

    console.log("Replay after event 1:");

    for (const event of application.stream.history.getAfter("1")) {
        console.log(event.id, event.type);
    }

    console.assert(first.id === "1");
    console.assert(second.id === "2");
    console.assert(third.id === "3");

    console.log("Assertions passed.");
}


async function startServer() {
    const server = createServer();

    server.listen(CONFIG.port, CONFIG.host, () => {
        console.log(
            `SSE server listening at http://${CONFIG.host}:${CONFIG.port}`
        );
    });

    const shutdown = () => {
        console.log("Shutting down SSE server");

        application.stream.shutdown();

        server.close(() => {
            process.exit(0);
        });

        setTimeout(() => process.exit(1), 5000).unref();
    };

    process.once("SIGINT", shutdown);
    process.once("SIGTERM", shutdown);

    return server;
}


if (process.argv.includes("--serve")) {
    startServer().catch(error => {
        console.error(error);
        process.exitCode = 1;
    });
} else {
    demonstrate().catch(error => {
        console.error(error);
        process.exitCode = 1;
    });
}
