"use strict";

/*
 * CORS Policy Gateway
 *
 * Node.js 18+ implementation using the HTTP standard library.
 * Provides:
 * - Origin allowlisting
 * - Same-origin request handling
 * - OPTIONS preflight processing
 * - Credential-aware responses
 * - Preflight caching
 * - Security validation
 * - Request auditing
 * - A working HTTP server
 */

const http = require("node:http");
const { URL } = require("node:url");
const { randomUUID } = require("node:crypto");

class CorsError extends Error {
    constructor(message, status = 400) {
        super(message);
        this.name = "CorsError";
        this.status = status;
    }
}

function normalizeOrigin(value) {
    if (typeof value !== "string" || value.length === 0) {
        throw new CorsError("Origin must be a non-empty string.");
    }

    if (value !== value.trim() || /[\x00-\x20\x7f]/.test(value)) {
        throw new CorsError("Invalid origin formatting.");
    }

    if (value === "null") {
        throw new CorsError("Opaque origins are not accepted.");
    }

    let parsed;

    try {
        parsed = new URL(value);
    } catch {
        throw new CorsError("Invalid origin URL.");
    }

    if (!["http:", "https:"].includes(parsed.protocol)) {
        throw new CorsError("Only HTTP and HTTPS origins are supported.");
    }

    if (
        parsed.username ||
        parsed.password ||
        parsed.pathname !== "/" ||
        parsed.search ||
        parsed.hash
    ) {
        throw new CorsError("Origin must contain only scheme and authority.");
    }

    if (!parsed.hostname) {
        throw new CorsError("Missing hostname.");
    }

    return parsed.origin;
}

function parseTokenList(value, label) {
    if (typeof value !== "string" || value.length === 0) {
        return [];
    }

    const tokens = value.split(",").map(item => item.trim().toLowerCase());

    if (
        tokens.some(token =>
            !/^[!#$%&'*+\-.^_`|~0-9a-z]+$/.test(token)
        )
    ) {
        throw new CorsError(`Invalid ${label} token.`);
    }

    return [...new Set(tokens)];
}

class CorsPolicy {
    constructor({
        origins,
        methods = ["GET", "POST"],
        headers = ["content-type", "authorization"],
        exposedHeaders = ["x-request-id"],
        credentials = false,
        maxAge = 600,
        privateNetwork = false
    }) {
        if (!Array.isArray(origins) || origins.length === 0) {
            throw new CorsError("At least one origin policy is required.");
        }

        this.origins = new Set(
            origins.map(origin =>
                origin === "*" ? "*" : normalizeOrigin(origin)
            )
        );

        this.methods = new Set(
            methods.map(method => {
                const normalized = method.toUpperCase();

                if (!/^[A-Z]+$/.test(normalized)) {
                    throw new CorsError("Invalid allowed method.");
                }

                return normalized;
            })
        );

        this.headers = new Set(headers.map(h => h.toLowerCase()));
        this.exposedHeaders = [...new Set(
            exposedHeaders.map(h => h.toLowerCase())
        )];

        this.credentials = credentials;
        this.maxAge = maxAge;
        this.privateNetwork = privateNetwork;

        if (this.origins.has("*") && credentials) {
            throw new CorsError(
                "Wildcard origins cannot allow credentials."
            );
        }

        if (!Number.isInteger(maxAge) || maxAge < 0 || maxAge > 86400) {
            throw new CorsError("Invalid preflight cache duration.");
        }
    }

    resolveOrigin(origin) {
        const normalized = normalizeOrigin(origin);

        if (this.origins.has("*") && !this.credentials) {
            return "*";
        }

        return this.origins.has(normalized) ? normalized : null;
    }
}

class PreflightCache {
    constructor() {
        this.entries = new Map();
    }

    has(key) {
        const expires = this.entries.get(key);

        if (!expires) return false;

        if (expires <= Date.now()) {
            this.entries.delete(key);
            return false;
        }

        return true;
    }

    set(key, seconds) {
        if (seconds > 0) {
            this.entries.set(key, Date.now() + seconds * 1000);
        }
    }

    cleanup() {
        const now = Date.now();

        for (const [key, expiry] of this.entries) {
            if (expiry <= now) {
                this.entries.delete(key);
            }
        }
    }
}

class CorsGateway {
    constructor(policy) {
        this.policy = policy;
        this.cache = new PreflightCache();
        this.audit = [];
    }

    record(origin, method, decision) {
        this.audit.push({
            id: randomUUID(),
            origin,
            method,
            decision,
            timestamp: new Date().toISOString()
        });

        // Bound memory usage in long-running processes.
        if (this.audit.length > 10000) {
            this.audit.splice(0, 1000);
        }
    }

    responseHeaders(origin) {
        const headers = {
            "Access-Control-Allow-Origin": origin
        };

        if (this.policy.credentials) {
            headers["Access-Control-Allow-Credentials"] = "true";
        }

        if (origin !== "*") {
            headers["Vary"] = "Origin";
        }

        if (this.policy.exposedHeaders.length) {
            headers["Access-Control-Expose-Headers"] =
                this.policy.exposedHeaders.join(", ");
        }

        return headers;
    }

    evaluate(req) {
        const origin = req.headers.origin;
        const method = req.method.toUpperCase();

        if (!origin) {
            this.record(null, method, "same-origin-or-no-origin");
            return {
                allowed: true,
                status: 200,
                headers: {},
                message: "No CORS processing required."
            };
        }

        let resolved;

        try {
            resolved = this.policy.resolveOrigin(origin);
        } catch (error) {
            this.record(origin, method, "invalid-origin");

            return {
                allowed: false,
                status: 403,
                headers: {},
                message: error.message
            };
        }

        if (!resolved) {
            this.record(origin, method, "origin-denied");

            return {
                allowed: false,
                status: 403,
                headers: {},
                message: "Origin is not allowed."
            };
        }

        const credentialsRequested =
            req.headers["x-demo-credentials"] === "true";

        if (credentialsRequested && !this.policy.credentials) {
            this.record(origin, method, "credentials-denied");

            return {
                allowed: false,
                status: 403,
                headers: {},
                message: "Credentials are not allowed."
            };
        }

        const headers = this.responseHeaders(resolved);

        if (method === "OPTIONS") {
            return this.evaluatePreflight(req, resolved, headers);
        }

        if (!this.policy.methods.has(method)) {
            this.record(origin, method, "method-denied");

            return {
                allowed: false,
                status: 405,
                headers: {},
                message: "Method is not allowed."
            };
        }

        this.record(origin, method, "allowed");

        return {
            allowed: true,
            status: 200,
            headers,
            message: "CORS request accepted."
        };
    }

    evaluatePreflight(req, origin, headers) {
        const requestedMethod = req.headers[
            "access-control-request-method"
        ];

        // OPTIONS can also be an ordinary HTTP request.
        if (!requestedMethod) {
            return {
                allowed: true,
                status: 204,
                headers,
                message: "Ordinary OPTIONS request."
            };
        }

        const method = requestedMethod.toUpperCase();

        if (!/^[A-Z]+$/.test(method)) {
            return {
                allowed: false,
                status: 400,
                headers: {},
                message: "Invalid requested method."
            };
        }

        let requestedHeaders;

        try {
            requestedHeaders = parseTokenList(
                req.headers["access-control-request-headers"] || "",
                "request header"
            );
        } catch (error) {
            return {
                allowed: false,
                status: 400,
                headers: {},
                message: error.message
            };
        }

        const privateNetwork =
            req.headers["access-control-request-private-network"] === "true";

        if (!this.policy.methods.has(method)) {
            this.record(origin, "OPTIONS", "preflight-method-denied");

            return {
                allowed: false,
                status: 403,
                headers: {},
                message: "Requested method is not allowed."
            };
        }

        if (requestedHeaders.some(
            header => !this.policy.headers.has(header)
        )) {
            this.record(origin, "OPTIONS", "preflight-header-denied");

            return {
                allowed: false,
                status: 403,
                headers: {},
                message: "Requested headers are not allowed."
            };
        }

        if (privateNetwork && !this.policy.privateNetwork) {
            this.record(origin, "OPTIONS", "private-network-denied");

            return {
                allowed: false,
                status: 403,
                headers: {},
                message: "Private network access is not allowed."
            };
        }

        const credentialFlag =
            req.headers["x-demo-credentials"] === "true";

        const key = JSON.stringify([
            origin,
            method,
            requestedHeaders.sort(),
            credentialFlag,
            privateNetwork
        ]);

        if (this.cache.has(key)) {
            this.record(origin, "OPTIONS", "preflight-cache-hit");

            return {
                allowed: true,
                status: 204,
                headers,
                message: "Cached preflight accepted."
            };
        }

        headers["Access-Control-Allow-Methods"] =
            [...this.policy.methods].sort().join(", ");

        headers["Access-Control-Allow-Headers"] =
            requestedHeaders.join(", ");

        headers["Access-Control-Max-Age"] =
            String(this.policy.maxAge);

        if (privateNetwork) {
            headers["Access-Control-Allow-Private-Network"] = "true";
        }

        this.cache.set(key, this.policy.maxAge);
        this.record(origin, "OPTIONS", "preflight-accepted");

        return {
            allowed: true,
            status: 204,
            headers,
            message: "Preflight accepted."
        };
    }

    middleware(req, res, next) {
        const result = this.evaluate(req);

        // Always vary on Origin when responses can differ by origin.
        if (req.headers.origin && !result.headers["Vary"]) {
            result.headers["Vary"] = "Origin";
        }

        for (const [name, value] of Object.entries(result.headers)) {
            res.setHeader(name, value);
        }

        res.setHeader("X-Content-Type-Options", "nosniff");

        if (!result.allowed) {
            res.writeHead(result.status, {
                "Content-Type": "application/json"
            });

            res.end(JSON.stringify({
                error: result.message
            }));

            return;
        }

        if (req.method === "OPTIONS") {
            res.writeHead(204);
            res.end();
            return;
        }

        next();
    }
}

const policy = new CorsPolicy({
    origins: [
        "http://localhost:5173",
        "https://app.example.com",
        "https://admin.example.com"
    ],
    methods: ["GET", "POST", "PUT", "DELETE"],
    headers: ["content-type", "authorization", "x-request-id"],
    exposedHeaders: ["x-request-id"],
    credentials: true,
    maxAge: 600
});

const gateway = new CorsGateway(policy);

const server = http.createServer((req, res) => {
    gateway.middleware(req, res, () => {
        if (req.url === "/api/data" && req.method === "GET") {
            res.writeHead(200, {
                "Content-Type": "application/json"
            });

            res.end(JSON.stringify({
                service: "CORS Gateway",
                data: ["record-1", "record-2"],
                requestId: randomUUID()
            }));

            return;
        }

        if (req.url === "/api/data" && req.method === "POST") {
            let body = "";

            req.on("data", chunk => {
                body += chunk;

                if (body.length > 1024 * 1024) {
                    req.destroy();
                }
            });

            req.on("end", () => {
                try {
                    const payload = JSON.parse(body || "{}");

                    res.writeHead(201, {
                        "Content-Type": "application/json"
                    });

                    res.end(JSON.stringify({
                        message: "Record accepted.",
                        payload
                    }));
                } catch {
                    res.writeHead(400, {
                        "Content-Type": "application/json"
                    });

                    res.end(JSON.stringify({
                        error: "Invalid JSON."
                    }));
                }
            });

            return;
        }

        res.writeHead(404, {
            "Content-Type": "application/json"
        });

        res.end(JSON.stringify({
            error: "Route not found."
        }));
    });
});

server.listen(8080, "127.0.0.1", () => {
    console.log("CORS Gateway listening on http://127.0.0.1:8080");
    console.log("Allowed origins:", [...policy.origins]);
    console.log("Endpoints: GET /api/data, POST /api/data");
});

server.on("error", error => {
    console.error("HTTP server failure:", error.message);
    process.exitCode = 1;
});

function shutdown() {
    gateway.cache.cleanup();

    server.close(error => {
        if (error) {
            console.error(error);
            process.exitCode = 1;
        }

        process.exit();
    });
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
