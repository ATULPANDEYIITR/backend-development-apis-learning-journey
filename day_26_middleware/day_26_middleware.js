/*
 * Middleware: request lifecycle, response interception, and custom middleware.
 *
 * This file is executable with modern Node.js and uses only built-in
 * JavaScript functionality.
 *
 * The core pipeline is:
 *
 * Request
 *   -> middleware
 *   -> middleware
 *   -> application
 *   -> response middleware
 *   -> response
 *
 * JavaScript middleware is particularly common in event-driven HTTP servers,
 * where middleware functions can wrap asynchronous application handlers.
 */

"use strict";

// ============================================================================
// 1. REQUEST AND RESPONSE OBJECTS
// ============================================================================

class Request {
    constructor({
        method = "GET",
        path = "/",
        headers = {},
        query = {},
        body = null
    } = {}) {
        this.method = method;
        this.path = path;
        this.headers = { ...headers };
        this.query = { ...query };
        this.body = body;

        // Middleware can attach contextual information without modifying the
        // public request shape.
        this.state = {};
    }

    getHeader(name, defaultValue = undefined) {
        const wanted = name.toLowerCase();

        for (const [key, value] of Object.entries(this.headers)) {
            if (key.toLowerCase() === wanted) {
                return value;
            }
        }

        return defaultValue;
    }
}

class Response {
    constructor({
        statusCode = 200,
        headers = {},
        body = null
    } = {}) {
        this.statusCode = statusCode;
        this.headers = { ...headers };
        this.body = body;
    }
}


// ============================================================================
// 2. BASIC APPLICATION HANDLER
// ============================================================================

async function application(request) {
    if (request.path === "/") {
        return new Response({
            body: {
                message: "Application response",
                path: request.path
            }
        });
    }

    if (request.path === "/users") {
        return new Response({
            body: {
                users: [
                    { id: 1, name: "Asha" },
                    { id: 2, name: "Rahul" }
                ]
            }
        });
    }

    if (request.path === "/missing") {
        return new Response({
            statusCode: 404,
            body: { error: "Resource not found" }
        });
    }

    if (request.path === "/error") {
        throw new Error("Demonstration application failure");
    }

    return new Response({
        body: {
            message: "Generic endpoint",
            path: request.path
        }
    });
}


// ============================================================================
// 3. BASIC SYNCHRONOUS-STYLE MIDDLEWARE
// ============================================================================

async function loggingMiddleware(request, next) {
    console.log(`[logging] incoming ${request.method} ${request.path}`);

    const response = await next();

    console.log(`[logging] outgoing ${response.statusCode}`);

    return response;
}


// ============================================================================
// 4. REQUEST ID MIDDLEWARE
// ============================================================================

function generateRequestId() {
    // Modern Node.js provides crypto.randomUUID().
    return globalThis.crypto?.randomUUID?.() ??
        `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function requestIdMiddleware(request, next) {
    const requestId =
        request.getHeader("X-Request-ID") ||
        generateRequestId();

    request.state.requestId = requestId;

    const response = await next();

    response.headers["X-Request-ID"] = requestId;

    return response;
}


// ============================================================================
// 5. RESPONSE INTERCEPTION
// ============================================================================

async function securityHeadersMiddleware(request, next) {
    const response = await next();

    // This code executes after the endpoint has produced a response.
    response.headers["X-Content-Type-Options"] = "nosniff";
    response.headers["X-Frame-Options"] = "DENY";
    response.headers["Referrer-Policy"] =
        "strict-origin-when-cross-origin";

    return response;
}


// ============================================================================
// 6. SHORT-CIRCUITING
// ============================================================================

async function maintenanceMiddleware(request, next) {
    // Not calling next() prevents downstream execution.
    if (request.path === "/maintenance") {
        return new Response({
            statusCode: 503,
            body: {
                error: "Service temporarily unavailable"
            }
        });
    }

    return next();
}


// ============================================================================
// 7. VALIDATION MIDDLEWARE
// ============================================================================

async function validationMiddleware(request, next) {
    if (!request.method) {
        return new Response({
            statusCode: 400,
            body: { error: "HTTP method is required" }
        });
    }

    if (!request.path.startsWith("/")) {
        return new Response({
            statusCode: 400,
            body: { error: "Path must begin with /" }
        });
    }

    const contentLength = request.getHeader("Content-Length");

    if (contentLength !== undefined) {
        const numericLength = Number(contentLength);

        if (!Number.isInteger(numericLength) || numericLength < 0) {
            return new Response({
                statusCode: 400,
                body: {
                    error: "Invalid Content-Length"
                }
            });
        }
    }

    return next();
}


// ============================================================================
// 8. AUTHENTICATION
// ============================================================================

async function authenticationMiddleware(request, next) {
    const authorization = request.getHeader("Authorization");

    if (authorization === "Bearer demo-user-token") {
        request.state.user = {
            id: 101,
            name: "Demo User",
            roles: ["user"]
        };
    } else {
        request.state.user = null;
    }

    return next();
}


async function protectedEndpoint(request) {
    if (!request.state.user) {
        return new Response({
            statusCode: 401,
            headers: {
                "WWW-Authenticate": "Bearer"
            },
            body: {
                error: "Authentication required"
            }
        });
    }

    return new Response({
        body: {
            message: "Protected resource",
            user: request.state.user
        }
    });
}


// ============================================================================
// 9. AUTHORIZATION
// ============================================================================

async function adminAuthorizationMiddleware(request, next) {
    const user = request.state.user;

    if (!user) {
        return new Response({
            statusCode: 401,
            body: {
                error: "Authentication required"
            }
        });
    }

    if (!user.roles.includes("admin")) {
        return new Response({
            statusCode: 403,
            body: {
                error: "Insufficient permissions"
            }
        });
    }

    return next();
}


// ============================================================================
// 10. TIMING MIDDLEWARE
// ============================================================================

async function timingMiddleware(request, next) {
    const start = process.hrtime.bigint();

    const response = await next();

    const elapsedNanoseconds =
        process.hrtime.bigint() - start;

    const elapsedMilliseconds =
        Number(elapsedNanoseconds) / 1_000_000;

    response.headers["X-Response-Time-Ms"] =
        elapsedMilliseconds.toFixed(3);

    console.log(
        `[timing] ${request.path}: ` +
        `${elapsedMilliseconds.toFixed(3)} ms`
    );

    return response;
}


// ============================================================================
// 11. ERROR-HANDLING MIDDLEWARE
// ============================================================================

async function errorHandlingMiddleware(request, next) {
    try {
        return await next();
    } catch (error) {
        // Internal details should be logged securely on the server but not
        // returned directly to an untrusted client.
        console.error(
            `[error] request ${request.state.requestId ?? "unknown"}:`,
            error.message
        );

        return new Response({
            statusCode: 500,
            body: {
                error: "Internal server error",
                requestId: request.state.requestId ?? null
            }
        });
    }
}


// ============================================================================
// 12. RESPONSE ENVELOPE
// ============================================================================

async function responseEnvelopeMiddleware(request, next) {
    const response = await next();

    if (
        response.body !== null &&
        typeof response.body === "object" &&
        !Array.isArray(response.body)
    ) {
        response.body = {
            status: response.statusCode < 400
                ? "success"
                : "error",
            data: response.body,
            requestId: request.state.requestId ?? null
        };
    }

    return response;
}


// ============================================================================
// 13. CUSTOM CLASS-BASED MIDDLEWARE
// ============================================================================

class RateLimitMiddleware {
    constructor(limit = 3) {
        if (!Number.isInteger(limit) || limit <= 0) {
            throw new Error("Rate limit must be a positive integer");
        }

        this.limit = limit;
        this.counts = new Map();
    }

    async handle(request, next) {
        const clientId =
            request.getHeader("X-Client-ID") ||
            "anonymous";

        const count = (this.counts.get(clientId) || 0) + 1;
        this.counts.set(clientId, count);

        if (count > this.limit) {
            return new Response({
                statusCode: 429,
                headers: {
                    "Retry-After": "60"
                },
                body: {
                    error: "Rate limit exceeded",
                    limit: this.limit
                }
            });
        }

        const response = await next();

        response.headers["X-RateLimit-Limit"] =
            String(this.limit);

        response.headers["X-RateLimit-Remaining"] =
            String(Math.max(0, this.limit - count));

        return response;
    }
}


// ============================================================================
// 14. CACHE MIDDLEWARE
// ============================================================================

class CacheMiddleware {
    constructor(ttlMilliseconds = 10_000) {
        this.ttlMilliseconds = ttlMilliseconds;
        this.cache = new Map();
    }

    makeKey(request) {
        const query = Object.entries(request.query)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, value]) => `${key}=${value}`)
            .join("&");

        return `${request.method}:${request.path}?${query}`;
    }

    async handle(request, next) {
        if (request.method.toUpperCase() !== "GET") {
            return next();
        }

        const key = this.makeKey(request);
        const now = Date.now();
        const cached = this.cache.get(key);

        if (cached && now - cached.timestamp < this.ttlMilliseconds) {
            cached.response.headers["X-Cache"] = "HIT";
            return cached.response;
        }

        if (cached) {
            this.cache.delete(key);
        }

        const response = await next();

        if (response.statusCode === 200) {
            this.cache.set(key, {
                timestamp: now,
                response
            });

            response.headers["X-Cache"] = "MISS";
        }

        return response;
    }
}


// ============================================================================
// 15. MIDDLEWARE COMPOSITION
// ============================================================================

function compose(middlewares, finalHandler) {
    /*
     * A middleware receives a next function rather than a response directly.
     *
     * [A, B, C] becomes:
     *
     * A -> B -> C -> handler
     *
     * The response unwinds:
     *
     * handler -> C -> B -> A
     */
    return async function composedHandler(request) {
        let index = -1;

        async function dispatch(position) {
            if (position <= index) {
                throw new Error("next() called more than once");
            }

            index = position;

            const middleware = position === middlewares.length
                ? null
                : middlewares[position];

            if (!middleware) {
                return finalHandler(request);
            }

            return middleware(
                request,
                () => dispatch(position + 1)
            );
        }

        return dispatch(0);
    };
}


// ============================================================================
// 16. ADAPTER FOR CLASS-BASED MIDDLEWARE
// ============================================================================

function useClassMiddleware(instance) {
    return (request, next) => instance.handle(request, next);
}


// ============================================================================
// 17. SAFE LOGGING
// ============================================================================

function safeHeaders(headers) {
    const sensitive = new Set([
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key"
    ]);

    return Object.fromEntries(
        Object.entries(headers).map(([key, value]) => [
            key,
            sensitive.has(key.toLowerCase())
                ? "[REDACTED]"
                : value
        ])
    );
}


// ============================================================================
// 18. METRICS MIDDLEWARE
// ============================================================================

class MetricsMiddleware {
    constructor() {
        this.totalRequests = 0;
        this.statusCounts = new Map();
        this.pathCounts = new Map();
    }

    async handle(request, next) {
        this.totalRequests++;

        this.pathCounts.set(
            request.path,
            (this.pathCounts.get(request.path) || 0) + 1
        );

        const response = await next();

        this.statusCounts.set(
            response.statusCode,
            (this.statusCounts.get(response.statusCode) || 0) + 1
        );

        return response;
    }

    report() {
        return {
            totalRequests: this.totalRequests,
            statusCounts: Object.fromEntries(this.statusCounts),
            pathCounts: Object.fromEntries(this.pathCounts)
        };
    }
}


// ============================================================================
// 19. CONTENT NEGOTIATION
// ============================================================================

async function contentNegotiationMiddleware(request, next) {
    const response = await next();
    const accept = request.getHeader("Accept", "application/json");

    if (
        accept.includes("application/json") ||
        accept.includes("*/*")
    ) {
        response.headers["Content-Type"] = "application/json";
    } else {
        response.headers["Content-Type"] =
            "application/octet-stream";
    }

    return response;
}


// ============================================================================
// 20. COMPLETE PIPELINE
// ============================================================================

async function demonstrateCompletePipeline() {
    console.log("\n" + "=".repeat(72));
    console.log("COMPLETE MIDDLEWARE PIPELINE");
    console.log("=".repeat(72));

    const rateLimiter = new RateLimitMiddleware(5);
    const cache = new CacheMiddleware(5_000);
    const metrics = new MetricsMiddleware();

    const pipeline = compose(
        [
            errorHandlingMiddleware,
            requestIdMiddleware,
            loggingMiddleware,
            validationMiddleware,
            timingMiddleware,
            maintenanceMiddleware,
            useClassMiddleware(rateLimiter),
            useClassMiddleware(metrics),
            useClassMiddleware(cache),
            securityHeadersMiddleware,
            contentNegotiationMiddleware,
            responseEnvelopeMiddleware
        ],
        application
    );

    const request = new Request({
        method: "GET",
        path: "/users",
        headers: {
            "X-Client-ID": "client-1",
            "Accept": "application/json"
        }
    });

    const response = await pipeline(request);

    console.log("Status:", response.statusCode);
    console.log("Headers:", response.headers);
    console.log("Body:", JSON.stringify(response.body, null, 2));
    console.log("Metrics:", metrics.report());

    return pipeline;
}


// ============================================================================
// 21. ORDER DEMONSTRATION
// ============================================================================

async function demonstrateOrder() {
    console.log("\n" + "=".repeat(72));
    console.log("MIDDLEWARE ORDER");
    console.log("=".repeat(72));

    const events = [];

    async function middlewareA(request, next) {
        events.push("A before");
        const response = await next();
        events.push("A after");
        return response;
    }

    async function middlewareB(request, next) {
        events.push("B before");
        const response = await next();
        events.push("B after");
        return response;
    }

    async function endpoint() {
        events.push("endpoint");
        return new Response({
            body: { ok: true }
        });
    }

    const pipeline = compose(
        [middlewareA, middlewareB],
        endpoint
    );

    await pipeline(new Request({
        path: "/order"
    }));

    console.log(events.join("\n"));
}


// ============================================================================
// 22. ERROR HANDLING DEMONSTRATION
// ============================================================================

async function demonstrateErrors() {
    console.log("\n" + "=".repeat(72));
    console.log("ERROR HANDLING");
    console.log("=".repeat(72));

    const pipeline = compose(
        [
            errorHandlingMiddleware,
            requestIdMiddleware
        ],
        application
    );

    const response = await pipeline(
        new Request({
            method: "GET",
            path: "/error"
        })
    );

    console.log(response.statusCode);
    console.log(response.body);
}


// ============================================================================
// 23. SHORT-CIRCUITING DEMONSTRATION
// ============================================================================

async function demonstrateShortCircuiting() {
    console.log("\n" + "=".repeat(72));
    console.log("SHORT-CIRCUITING");
    console.log("=".repeat(72));

    const pipeline = compose(
        [
            maintenanceMiddleware,
            loggingMiddleware
        ],
        application
    );

    const normal = await pipeline(
        new Request({ path: "/" })
    );

    const maintenance = await pipeline(
        new Request({ path: "/maintenance" })
    );

    console.log("Normal:", normal.statusCode);
    console.log("Maintenance:", maintenance.statusCode);
}


// ============================================================================
// 24. AUTHENTICATION / AUTHORIZATION DEMONSTRATION
// ============================================================================

async function demonstrateAuthorization() {
    console.log("\n" + "=".repeat(72));
    console.log("AUTHENTICATION AND AUTHORIZATION");
    console.log("=".repeat(72));

    const pipeline = compose(
        [
            authenticationMiddleware,
            adminAuthorizationMiddleware
        ],
        protectedEndpoint
    );

    const response = await pipeline(
        new Request({
            method: "GET",
            path: "/admin",
            headers: {
                Authorization: "Bearer demo-user-token"
            }
        })
    );

    console.log(response.statusCode, response.body);
}


// ============================================================================
// 25. TESTS
// ============================================================================

async function runTests() {
    console.log("\n" + "=".repeat(72));
    console.log("SELF-TESTS");
    console.log("=".repeat(72));

    {
        const pipeline = compose(
            [requestIdMiddleware],
            application
        );

        const request = new Request({
            path: "/"
        });

        const response = await pipeline(request);

        console.assert(
            Boolean(request.state.requestId),
            "Request ID should exist"
        );

        console.assert(
            response.headers["X-Request-ID"] ===
            request.state.requestId,
            "Response should contain request ID"
        );

        console.log("PASS: request ID");
    }

    {
        const pipeline = compose(
            [maintenanceMiddleware],
            async () => {
                throw new Error("Downstream should not run");
            }
        );

        const response = await pipeline(
            new Request({
                path: "/maintenance"
            })
        );

        console.assert(
            response.statusCode === 503,
            "Maintenance should return 503"
        );

        console.log("PASS: short-circuit");
    }

    {
        const limiter = new RateLimitMiddleware(2);

        const pipeline = compose(
            [useClassMiddleware(limiter)],
            application
        );

        const createRequest = () => new Request({
            path: "/",
            headers: {
                "X-Client-ID": "test-client"
            }
        });

        console.assert(
            (await pipeline(createRequest())).statusCode === 200
        );

        console.assert(
            (await pipeline(createRequest())).statusCode === 200
        );

        console.assert(
            (await pipeline(createRequest())).statusCode === 429
        );

        console.log("PASS: rate limiting");
    }

    {
        const response = await application(
            new Request({
                path: "/missing"
            })
        );

        console.assert(
            response.statusCode === 404,
            "Missing resource should return 404"
        );

        console.log("PASS: 404 response");
    }

    {
        const headers = safeHeaders({
            Authorization: "secret",
            Accept: "application/json"
        });

        console.assert(
            headers.Authorization === "[REDACTED]"
        );

        console.assert(
            headers.Accept === "application/json"
        );

        console.log("PASS: safe logging");
    }
}


// ============================================================================
// 26. MAIN
// ============================================================================

async function main() {
    await demonstrateCompletePipeline();
    await demonstrateOrder();
    await demonstrateErrors();
    await demonstrateShortCircuiting();
    await demonstrateAuthorization();
    await runTests();

    console.log("\n" + "=".repeat(72));
    console.log("STUDY COMPLETE");
    console.log("=".repeat(72));
}

main().catch((error) => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
