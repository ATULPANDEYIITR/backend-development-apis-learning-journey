"use strict";

/*
 * WSGI and ASGI are Python interfaces, so JavaScript cannot implement WSGI
 * or ASGI directly. This file uses JavaScript's own server/event-loop model
 * to demonstrate the same architectural ideas:
 *
 * - synchronous vs asynchronous execution
 * - event loops
 * - blocking vs non-blocking work
 * - middleware
 * - routing
 * - streaming
 * - WebSocket-style event handling
 * - concurrency limits
 * - timeouts
 * - graceful shutdown
 * - worker/process architecture
 *
 * It requires only Node.js built-in modules.
 */

const http = require("node:http");
const { Worker, isMainThread, parentPort, workerData } = require("node:worker_threads");
const { performance } = require("node:perf_hooks");

// ============================================================
// 1. BASIC HTTP APPLICATION MODEL
// ============================================================

function basicHandler(request, response) {
    /*
     * Node's HTTP API is not WSGI or ASGI.
     * The important architectural similarity is that a server invokes
     * application-level request handling after receiving an HTTP request.
     */
    response.writeHead(200, {
        "Content-Type": "text/plain; charset=utf-8"
    });

    response.end(`Node HTTP response for ${request.url}\n`);
}

function demonstrateBasicHandler() {
    console.log("\n=== 1. BASIC HTTP APPLICATION MODEL ===");
    console.log("Node provides an event-driven HTTP server.");
    console.log("Python WSGI and ASGI define different application interfaces.");
}

// ============================================================
// 2. SYNCHRONOUS VS ASYNCHRONOUS EXECUTION
// ============================================================

function blockingDelay(milliseconds) {
    /*
     * This intentionally blocks the JavaScript event-loop thread.
     * It should not be used in ordinary request handlers.
     */
    const started = performance.now();

    while (performance.now() - started < milliseconds) {
        // Busy wait.
    }
}

function demonstrateBlockingBehavior() {
    console.log("\n=== 2. BLOCKING EVENT-LOOP WORK ===");

    const started = performance.now();

    blockingDelay(50);

    console.log(
        `Blocking operation elapsed: ${(performance.now() - started).toFixed(2)} ms`
    );

    console.log(
        "A blocking operation prevents unrelated event-loop callbacks from progressing."
    );
}

async function nonBlockingDelay(milliseconds) {
    return new Promise(resolve => {
        setTimeout(resolve, milliseconds);
    });
}

async function demonstrateNonBlockingBehavior() {
    console.log("\n=== 3. NON-BLOCKING I/O ===");

    const started = performance.now();

    await Promise.all([
        nonBlockingDelay(50),
        nonBlockingDelay(50),
        nonBlockingDelay(50)
    ]);

    console.log(
        `Three overlapping waits: ${(performance.now() - started).toFixed(2)} ms`
    );

    console.log(
        "Waiting does not occupy the JavaScript event-loop thread."
    );
}

// ============================================================
// 3. ASYNC ERROR HANDLING
// ============================================================

async function unreliableOperation() {
    await nonBlockingDelay(10);

    if (Math.random() < 0.5) {
        throw new Error("Simulated downstream failure");
    }

    return "success";
}

async function demonstrateErrorHandling() {
    console.log("\n=== 4. ASYNC ERROR HANDLING ===");

    try {
        const result = await unreliableOperation();
        console.log(result);
    } catch (error) {
        console.log("Handled:", error.message);
    }
}

// ============================================================
// 4. TIMEOUT
// ============================================================

function withTimeout(promise, milliseconds) {
    return Promise.race([
        promise,
        new Promise((_, reject) => {
            setTimeout(
                () => reject(new Error("Operation timed out")),
                milliseconds
            );
        })
    ]);
}

async function demonstrateTimeout() {
    console.log("\n=== 5. TIMEOUT ===");

    try {
        const result = await withTimeout(
            nonBlockingDelay(100).then(() => "completed"),
            30
        );

        console.log(result);
    } catch (error) {
        console.log(error.message);
    }
}

// ============================================================
// 5. ROUTER
// ============================================================

class Router {
    constructor() {
        this.routes = new Map();
    }

    add(method, path, handler) {
        this.routes.set(`${method.toUpperCase()} ${path}`, handler);
    }

    match(method, path) {
        return this.routes.get(
            `${method.toUpperCase()} ${path}`
        );
    }
}

async function healthHandler(request, response) {
    response.writeHead(200, {
        "Content-Type": "application/json"
    });

    response.end(
        JSON.stringify({
            status: "ok"
        })
    );
}

async function usersHandler(request, response) {
    const parsed = new URL(
        request.url,
        `http://${request.headers.host || "localhost"}`
    );

    const name = parsed.searchParams.get("name");
    const ageText = parsed.searchParams.get("age");

    if (!name || !ageText) {
        response.writeHead(400, {
            "Content-Type": "application/json"
        });

        response.end(
            JSON.stringify({
                error: "name and age are required"
            })
        );

        return;
    }

    const age = Number(ageText);

    if (!Number.isInteger(age) || age < 0 || age > 150) {
        response.writeHead(400, {
            "Content-Type": "application/json"
        });

        response.end(
            JSON.stringify({
                error: "age must be an integer between 0 and 150"
            })
        );

        return;
    }

    response.writeHead(200, {
        "Content-Type": "application/json"
    });

    response.end(
        JSON.stringify({
            name,
            age
        })
    );
}

// ============================================================
// 6. MIDDLEWARE
// ============================================================

function createMiddlewareStack(middlewares, finalHandler) {
    /*
     * Middleware composes request processing around the final handler.
     * This is conceptually similar to WSGI and ASGI middleware.
     */
    return async function execute(request, response) {
        let index = -1;

        async function dispatch(position) {
            if (position <= index) {
                throw new Error("next() called multiple times");
            }

            index = position;

            const middleware = middlewares[position];

            if (!middleware) {
                return finalHandler(request, response);
            }

            return middleware(
                request,
                response,
                () => dispatch(position + 1)
            );
        }

        return dispatch(0);
    };
}

async function loggingMiddleware(request, response, next) {
    const started = performance.now();

    await next();

    console.log(
        `${request.method} ${request.url} ${(performance.now() - started).toFixed(2)} ms`
    );
}

async function securityHeadersMiddleware(request, response, next) {
    /*
     * Headers should be selected according to the actual deployment and
     * security policy. This example demonstrates the middleware mechanism.
     */
    response.setHeader("X-Content-Type-Options", "nosniff");
    await next();
}

// ============================================================
// 7. BODY LIMITING
// ============================================================

function readRequestBody(request, maximumBytes = 1024 * 1024) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        let totalBytes = 0;

        request.on("data", chunk => {
            totalBytes += chunk.length;

            if (totalBytes > maximumBytes) {
                reject(new Error("Request body too large"));
                request.destroy();
                return;
            }

            chunks.push(chunk);
        });

        request.on("end", () => {
            resolve(Buffer.concat(chunks));
        });

        request.on("error", reject);
    });
}

// ============================================================
// 8. CONCURRENCY LIMITER
// ============================================================

class ConcurrencyLimiter {
    constructor(limit) {
        if (!Number.isInteger(limit) || limit < 1) {
            throw new Error("Concurrency limit must be positive");
        }

        this.limit = limit;
        this.active = 0;
        this.queue = [];
    }

    async run(task) {
        if (this.active >= this.limit) {
            await new Promise(resolve => {
                this.queue.push(resolve);
            });
        }

        this.active += 1;

        try {
            return await task();
        } finally {
            this.active -= 1;

            const next = this.queue.shift();

            if (next) {
                next();
            }
        }
    }
}

async function demonstrateConcurrencyLimiter() {
    console.log("\n=== 6. CONCURRENCY LIMITING ===");

    const limiter = new ConcurrencyLimiter(2);

    const tasks = Array.from({ length: 6 }, (_, index) =>
        limiter.run(async () => {
            console.log(`Started task ${index}`);
            await nonBlockingDelay(20);
            console.log(`Finished task ${index}`);
            return index;
        })
    );

    console.log("Results:", await Promise.all(tasks));
}

// ============================================================
// 9. STREAMING
// ============================================================

function demonstrateStreamingConcept() {
    console.log("\n=== 7. HTTP STREAMING ===");

    console.log(
        "A response can be emitted incrementally instead of constructing one enormous buffer."
    );

    console.log(
        "Streaming is useful for large downloads, generated content, and long-running responses."
    );
}

// ============================================================
// 10. SERVER-SENT EVENT STYLE STREAM
// ============================================================

function sseHandler(request, response) {
    response.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive"
    });

    let counter = 0;

    const timer = setInterval(() => {
        counter += 1;

        response.write(
            `data: ${JSON.stringify({
                counter,
                timestamp: new Date().toISOString()
            })}\n\n`
        );

        if (counter === 3) {
            clearInterval(timer);
            response.end();
        }
    }, 20);

    request.on("close", () => {
        clearInterval(timer);
    });
}

// ============================================================
// 11. WEBSOCKET CONCEPT
// ============================================================

class WebSocketLikeSession {
    constructor() {
        this.connected = false;
    }

    accept() {
        this.connected = true;
        return {
            type: "websocket.accept"
        };
    }

    receive(text) {
        if (!this.connected) {
            throw new Error("WebSocket is not connected");
        }

        return {
            type: "websocket.receive",
            text
        };
    }

    send(text) {
        if (!this.connected) {
            throw new Error("WebSocket is not connected");
        }

        return {
            type: "websocket.send",
            text
        };
    }

    close(code = 1000) {
        this.connected = false;

        return {
            type: "websocket.close",
            code
        };
    }
}

function demonstrateWebSocketEventModel() {
    console.log("\n=== 8. WEBSOCKET EVENT MODEL ===");

    const session = new WebSocketLikeSession();

    console.log(session.accept());
    console.log(session.receive("hello"));
    console.log(session.send("echo: hello"));
    console.log(session.close());
}

// ============================================================
// 12. APPLICATION FACTORY
// ============================================================

function createApplication(config) {
    /*
     * Factories allow configuration and dependencies to be constructed before
     * the server starts processing requests.
     */
    return {
        config,

        async handle(request, response) {
            response.writeHead(200, {
                "Content-Type": "application/json"
            });

            response.end(
                JSON.stringify({
                    service: config.name,
                    environment: config.environment
                })
            );
        }
    };
}

function demonstrateApplicationFactory() {
    console.log("\n=== 9. APPLICATION FACTORY ===");

    const application = createApplication({
        name: "educational-service",
        environment: "production"
    });

    console.log(application.config);
}

// ============================================================
// 13. CPU-BOUND WORK AND WORKER THREADS
// ============================================================

function expensiveCalculation(number) {
    let result = 0;

    for (let value = 0; value < number; value += 1) {
        result += value * value;
    }

    return result;
}

function runCPUWorkInWorker(number) {
    return new Promise((resolve, reject) => {
        const worker = new Worker(__filename, {
            workerData: number
        });

        worker.once("message", resolve);
        worker.once("error", reject);
    });
}

async function demonstrateWorkerThread() {
    console.log("\n=== 10. CPU-BOUND WORK ===");

    const result = await runCPUWorkInWorker(100000);

    console.log("Worker result:", result);

    console.log(
        "Worker threads can keep expensive computation away from the main event-loop thread."
    );
}

// ============================================================
// 14. DATABASE-STYLE ASYNC ACCESS
// ============================================================

async function fakeDatabaseQuery(userId) {
    /*
     * A real async database driver performs network I/O while allowing other
     * event-loop tasks to make progress.
     */
    await nonBlockingDelay(20);

    return {
        userId,
        name: `User-${userId}`
    };
}

async function demonstrateDatabaseConcurrency() {
    console.log("\n=== 11. CONCURRENT I/O ===");

    const started = performance.now();

    const users = await Promise.all(
        [1, 2, 3, 4, 5].map(fakeDatabaseQuery)
    );

    console.log(users);
    console.log(
        `Elapsed: ${(performance.now() - started).toFixed(2)} ms`
    );
}

// ============================================================
// 15. TIMEOUT AND CANCELLATION
// ============================================================

async function cancellableOperation(signal) {
    return new Promise((resolve, reject) => {
        if (signal.aborted) {
            reject(new Error("Operation aborted"));
            return;
        }

        const timer = setTimeout(
            () => resolve("completed"),
            100
        );

        signal.addEventListener(
            "abort",
            () => {
                clearTimeout(timer);
                reject(new Error("Operation aborted"));
            },
            { once: true }
        );
    });
}

async function demonstrateCancellation() {
    console.log("\n=== 12. CANCELLATION ===");

    const controller = new AbortController();

    const operation = cancellableOperation(controller.signal);

    setTimeout(() => controller.abort(), 20);

    try {
        console.log(await operation);
    } catch (error) {
        console.log(error.message);
    }
}

// ============================================================
// 16. OBSERVABILITY
// ============================================================

class Metrics {
    constructor() {
        this.requests = 0;
        this.errors = 0;
        this.latencies = [];
    }

    recordRequest(elapsedMilliseconds, failed = false) {
        this.requests += 1;

        if (failed) {
            this.errors += 1;
        }

        this.latencies.push(elapsedMilliseconds);
    }

    report() {
        const sorted = [...this.latencies].sort((a, b) => a - b);

        const percentile = p => {
            if (sorted.length === 0) {
                return 0;
            }

            const index = Math.min(
                sorted.length - 1,
                Math.ceil((p / 100) * sorted.length) - 1
            );

            return sorted[index];
        };

        return {
            requests: this.requests,
            errors: this.errors,
            errorRate:
                this.requests === 0
                    ? 0
                    : this.errors / this.requests,
            p50Milliseconds: percentile(50),
            p95Milliseconds: percentile(95),
            p99Milliseconds: percentile(99)
        };
    }
}

function demonstrateMetrics() {
    console.log("\n=== 13. OBSERVABILITY ===");

    const metrics = new Metrics();

    [5, 8, 11, 20, 50, 100].forEach((latency, index) => {
        metrics.recordRequest(latency, index === 4);
    });

    console.log(metrics.report());
}

// ============================================================
// 17. GRACEFUL SHUTDOWN
// ============================================================

class ApplicationLifecycle {
    constructor() {
        this.acceptingRequests = false;
        this.resourcesOpen = false;
    }

    async startup() {
        this.resourcesOpen = true;
        this.acceptingRequests = true;
    }

    async shutdown() {
        this.acceptingRequests = false;

        /*
         * Real systems should allow in-flight work to finish according to
         * their configured graceful-shutdown policy.
         */
        await nonBlockingDelay(10);

        this.resourcesOpen = false;
    }
}

async function demonstrateLifecycle() {
    console.log("\n=== 14. LIFECYCLE ===");

    const lifecycle = new ApplicationLifecycle();

    await lifecycle.startup();

    console.log({
        acceptingRequests: lifecycle.acceptingRequests,
        resourcesOpen: lifecycle.resourcesOpen
    });

    await lifecycle.shutdown();

    console.log({
        acceptingRequests: lifecycle.acceptingRequests,
        resourcesOpen: lifecycle.resourcesOpen
    });
}

// ============================================================
// 18. PROXY AND TRUSTED HEADERS
// ============================================================

function explainProxySecurity() {
    console.log("\n=== 15. REVERSE PROXY SECURITY ===");

    console.log(
        "Forwarded headers must not be trusted merely because a client supplied them."
    );

    console.log(
        "A deployment should define which proxy networks are trusted before deriving scheme or client identity from proxy headers."
    );
}

// ============================================================
// 19. REQUEST SIZE VALIDATION
// ============================================================

function validateContentLength(headers, maximumBytes) {
    const raw = headers["content-length"];

    if (raw === undefined) {
        return true;
    }

    const size = Number(raw);

    if (!Number.isSafeInteger(size) || size < 0) {
        throw new Error("Invalid Content-Length");
    }

    if (size > maximumBytes) {
        throw new Error("Request body exceeds configured limit");
    }

    return true;
}

function demonstrateRequestValidation() {
    console.log("\n=== 16. REQUEST VALIDATION ===");

    const headers = {
        "content-length": "500"
    };

    try {
        validateContentLength(headers, 1024);
        console.log("Request accepted");
    } catch (error) {
        console.log("Request rejected:", error.message);
    }
}

// ============================================================
// 20. HTTP SERVER ASSEMBLY
// ============================================================

function createHttpApplication() {
    const router = new Router();

    router.add("GET", "/health", healthHandler);
    router.add("GET", "/users", usersHandler);
    router.add("GET", "/events", sseHandler);

    const notFoundHandler = async (request, response) => {
        response.writeHead(404, {
            "Content-Type": "application/json"
        });

        response.end(
            JSON.stringify({
                error: "Not Found"
            })
        );
    };

    const routedHandler = async (request, response) => {
        const pathname = new URL(
            request.url,
            `http://${request.headers.host || "localhost"}`
        ).pathname;

        const handler = router.match(
            request.method,
            pathname
        );

        if (!handler) {
            await notFoundHandler(request, response);
            return;
        }

        await handler(request, response);
    };

    return createMiddlewareStack(
        [
            loggingMiddleware,
            securityHeadersMiddleware
        ],
        routedHandler
    );
}

function createServer() {
    const application = createHttpApplication();

    return http.createServer(async (request, response) => {
        try {
            validateContentLength(
                request.headers,
                1024 * 1024
            );

            await application(request, response);
        } catch (error) {
            if (!response.headersSent) {
                response.writeHead(
                    error.message === "Request body exceeds configured limit"
                        ? 413
                        : 500,
                    {
                        "Content-Type": "application/json"
                    }
                );
            }

            if (!response.writableEnded) {
                response.end(
                    JSON.stringify({
                        error: error.message
                    })
                );
            }
        }
    });
}

// ============================================================
// 21. WORKER PROCESS ARCHITECTURE
// ============================================================

function explainWorkerArchitecture() {
    console.log("\n=== 17. MULTI-PROCESS ARCHITECTURE ===");

    console.log(`
Conceptual production architecture:

Reverse proxy
      |
      +---- process 1 -> event loop -> application
      +---- process 2 -> event loop -> application
      +---- process 3 -> event loop -> application
      +---- process 4 -> event loop -> application

Multiple processes can use multiple CPU cores and provide process isolation.
Each process has its own memory space.

This is conceptually similar to using multiple application workers in a
Python deployment managed by a process manager such as Gunicorn.
`);
}

// ============================================================
// 22. WSGI/ASGI ARCHITECTURAL COMPARISON
// ============================================================

function comparePythonInterfaces() {
    console.log("\n=== 18. WSGI AND ASGI ===");

    const comparison = [
        ["Interface", "WSGI callable", "ASGI callable"],
        ["Request model", "Environment mapping", "Scope + receive events"],
        ["Response model", "Iterable bytes", "send events"],
        ["Primary execution", "Synchronous", "Async-capable"],
        ["WebSockets", "Not native", "Native protocol model"],
        ["Lifespan", "Not core", "Supported"],
        ["Streaming", "Iterable-based", "Event/message-based"],
    ];

    for (const row of comparison) {
        console.log(row.join(" | "));
    }
}

// ============================================================
// 23. COMPLETE EDUCATIONAL CASE STUDY
// ============================================================

class Service {
    constructor() {
        this.metrics = new Metrics();
        this.lifecycle = new ApplicationLifecycle();
        this.limiter = new ConcurrencyLimiter(10);
    }

    async processUser(userId) {
        return this.limiter.run(async () => {
            const started = performance.now();

            try {
                const user = await fakeDatabaseQuery(userId);

                this.metrics.recordRequest(
                    performance.now() - started
                );

                return user;
            } catch (error) {
                this.metrics.recordRequest(
                    performance.now() - started,
                    true
                );

                throw error;
            }
        });
    }

    async startup() {
        await this.lifecycle.startup();
    }

    async shutdown() {
        await this.lifecycle.shutdown();
    }
}

async function demonstrateCompleteService() {
    console.log("\n=== 19. COMPLETE SERVICE CASE STUDY ===");

    const service = new Service();

    await service.startup();

    const users = await Promise.all(
        Array.from(
            { length: 20 },
            (_, index) => service.processUser(index + 1)
        )
    );

    console.log("Users:", users.length);
    console.log("Metrics:", service.metrics.report());

    await service.shutdown();
}

// ============================================================
// 24. PRODUCTION CONSIDERATIONS
// ============================================================

function explainProductionConsiderations() {
    console.log("\n=== 20. PRODUCTION CONSIDERATIONS ===");

    const considerations = [
        "Use a production process manager or orchestration platform.",
        "Do not use development reload mode as ordinary production scaling.",
        "Keep blocking work away from the event loop.",
        "Use timeouts for downstream calls.",
        "Bound concurrency and request sizes.",
        "Configure graceful shutdown.",
        "Monitor latency, errors, CPU, memory, and connection counts.",
        "Protect forwarded headers and proxy trust configuration.",
        "Use TLS at an appropriate edge or server boundary.",
        "Use authentication and authorization at the application level.",
        "Choose worker counts based on measurement and resource constraints.",
        "Ensure database pools are compatible with total application concurrency."
    ];

    for (const item of considerations) {
        console.log("-", item);
    }
}

// ============================================================
// 25. MAIN
// ============================================================

async function main() {
    if (!isMainThread) {
        const result = expensiveCalculation(workerData);

        parentPort.postMessage(result);
        return;
    }

    console.log("=".repeat(72));
    console.log("WSGI AND ASGI: JAVASCRIPT ARCHITECTURAL STUDY");
    console.log("=".repeat(72));

    demonstrateBasicHandler();
    demonstrateBlockingBehavior();
    await demonstrateNonBlockingBehavior();
    await demonstrateErrorHandling();
    await demonstrateTimeout();
    await demonstrateConcurrencyLimiter();
    demonstrateStreamingConcept();
    demonstrateWebSocketEventModel();
    demonstrateApplicationFactory();
    await demonstrateWorkerThread();
    await demonstrateDatabaseConcurrency();
    await demonstrateCancellation();
    demonstrateMetrics();
    await demonstrateLifecycle();
    explainProxySecurity();
    demonstrateRequestValidation();
    explainWorkerArchitecture();
    comparePythonInterfaces();
    await demonstrateCompleteService();
    explainProductionConsiderations();

    console.log("\n=== SERVER EXAMPLE ===");
    console.log(
        "Run this file and uncomment the server startup section if you want to expose the HTTP example."
    );

    /*
     * Uncomment to run:
     *
     * const server = createServer();
     * server.listen(3000, "127.0.0.1", () => {
     *     console.log("Listening on http://127.0.0.1:3000");
     * });
     *
     * process.on("SIGTERM", async () => {
     *     server.close(() => process.exit(0));
     * });
     */
}

main().catch(error => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
