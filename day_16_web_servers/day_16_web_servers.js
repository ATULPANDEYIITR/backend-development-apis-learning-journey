/*
 * Web Servers: JavaScript study implementation
 *
 * Demonstrates:
 * - HTTP server fundamentals
 * - Static files
 * - Dynamic application routes
 * - Reverse-proxy concepts
 * - Load balancing
 * - Middleware
 * - Security headers
 * - Caching
 * - Timeouts
 * - Error handling
 * - Logging
 *
 * Uses only Node.js built-in modules.
 */

"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");
const crypto = require("crypto");


// ============================================================
// 1. BASIC HTTP CONCEPTS
// ============================================================

function demonstrateHttpStructure() {
    const request = {
        method: "GET",
        path: "/index.html",
        headers: {
            host: "example.test",
            accept: "text/html"
        }
    };

    const response = {
        statusCode: 200,
        headers: {
            "content-type": "text/html; charset=utf-8"
        },
        body: "<h1>Hello</h1>"
    };

    console.log("\n=== HTTP structure ===");
    console.log("Request:", request);
    console.log("Response:", response);
}


// ============================================================
// 2. APPLICATION SERVER
// ============================================================

class ApplicationServer {
    async handle(request) {
        const url = new URL(
            request.url,
            `http://${request.headers.host || "localhost"}`
        );

        if (request.method === "GET" && url.pathname === "/") {
            return {
                statusCode: 200,
                headers: { "content-type": "text/plain; charset=utf-8" },
                body: "Application server is running"
            };
        }

        if (request.method === "GET" && url.pathname === "/api/hello") {
            const name = url.searchParams.get("name") || "world";

            if (name.length > 100) {
                return {
                    statusCode: 400,
                    headers: { "content-type": "text/plain; charset=utf-8" },
                    body: "Name is too long"
                };
            }

            return {
                statusCode: 200,
                headers: { "content-type": "application/json" },
                body: JSON.stringify({
                    message: `Hello, ${name}!`,
                    timestamp: new Date().toISOString()
                })
            };
        }

        return {
            statusCode: 404,
            headers: { "content-type": "text/plain; charset=utf-8" },
            body: "Route not found"
        };
    }
}


// ============================================================
// 3. STATIC FILE SERVICE
// ============================================================

const MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg"
};

class StaticFileService {
    constructor(rootDirectory) {
        this.rootDirectory = path.resolve(rootDirectory);
    }

    resolveSafePath(urlPath) {
        // Decode URL components before checking the filesystem path.
        const decodedPath = decodeURIComponent(urlPath);

        // Remove the leading URL slash.
        const relativePath = decodedPath.replace(/^[/\\]+/, "");

        const candidate = path.resolve(
            this.rootDirectory,
            relativePath
        );

        // path.relative() lets us detect traversal outside the root.
        const relative = path.relative(
            this.rootDirectory,
            candidate
        );

        if (
            relative.startsWith("..") ||
            path.isAbsolute(relative)
        ) {
            return null;
        }

        return candidate;
    }

    async serve(urlPath) {
        const filePath = this.resolveSafePath(urlPath);

        if (!filePath) {
            return {
                statusCode: 403,
                headers: { "content-type": "text/plain; charset=utf-8" },
                body: "Forbidden"
            };
        }

        try {
            const statistics = await fs.promises.stat(filePath);

            if (!statistics.isFile()) {
                return {
                    statusCode: 404,
                    headers: { "content-type": "text/plain; charset=utf-8" },
                    body: "Not Found"
                };
            }

            const body = await fs.promises.readFile(filePath);
            const extension = path.extname(filePath).toLowerCase();

            return {
                statusCode: 200,
                headers: {
                    "content-type":
                        MIME_TYPES[extension] ||
                        "application/octet-stream",
                    "content-length": String(body.length)
                },
                body
            };
        } catch (error) {
            if (error.code === "ENOENT") {
                return {
                    statusCode: 404,
                    headers: {
                        "content-type": "text/plain; charset=utf-8"
                    },
                    body: "Not Found"
                };
            }

            return {
                statusCode: 500,
                headers: {
                    "content-type": "text/plain; charset=utf-8"
                },
                body: "Internal Server Error"
            };
        }
    }
}


// ============================================================
// 4. CACHE
// ============================================================

class TTLCache {
    constructor(ttlMilliseconds = 5000) {
        this.ttlMilliseconds = ttlMilliseconds;
        this.entries = new Map();
    }

    get(key) {
        const entry = this.entries.get(key);

        if (!entry) {
            return null;
        }

        if (Date.now() >= entry.expiresAt) {
            this.entries.delete(key);
            return null;
        }

        return entry.value;
    }

    set(key, value) {
        this.entries.set(key, {
            value,
            expiresAt: Date.now() + this.ttlMilliseconds
        });
    }
}


// ============================================================
// 5. BACKEND AND REVERSE PROXY
// ============================================================

class BackendServer {
    constructor(name, application) {
        this.name = name;
        this.application = application;
        this.healthy = true;
        this.requestCount = 0;
    }

    async handle(request) {
        if (!this.healthy) {
            throw new Error(`${this.name} is unhealthy`);
        }

        this.requestCount++;
        return this.application.handle(request);
    }
}

class ReverseProxy {
    constructor(backends) {
        if (!Array.isArray(backends) || backends.length === 0) {
            throw new Error("A reverse proxy requires at least one backend");
        }

        this.backends = backends;
        this.nextIndex = 0;
        this.cache = new TTLCache(3000);
    }

    selectBackend() {
        const healthyBackends = this.backends.filter(
            backend => backend.healthy
        );

        if (healthyBackends.length === 0) {
            return null;
        }

        const backend =
            healthyBackends[this.nextIndex % healthyBackends.length];

        this.nextIndex++;
        return backend;
    }

    async handle(request) {
        // Cache only an explicitly selected public GET endpoint.
        const cacheKey = `${request.method}:${request.url}`;

        if (request.method === "GET") {
            const cached = this.cache.get(cacheKey);

            if (cached) {
                return {
                    ...cached,
                    headers: {
                        ...cached.headers,
                        "x-cache": "HIT"
                    }
                };
            }
        }

        const backend = this.selectBackend();

        if (!backend) {
            return {
                statusCode: 503,
                headers: {
                    "content-type": "text/plain; charset=utf-8"
                },
                body: "No healthy backend"
            };
        }

        // X-Forwarded-* headers communicate proxy information
        // to the application layer.
        const forwardedRequest = {
            ...request,
            headers: {
                ...request.headers,
                "x-forwarded-for":
                    request.headers["x-forwarded-for"] ||
                    request.socket?.remoteAddress ||
                    "unknown",
                "x-forwarded-proto": "http",
                "x-forwarded-host": request.headers.host || "unknown"
            }
        };

        try {
            const response = await withTimeout(
                backend.handle(forwardedRequest),
                3000
            );

            const proxiedResponse = {
                ...response,
                headers: {
                    ...response.headers,
                    "x-backend": backend.name,
                    "via": "educational-reverse-proxy",
                    "x-cache": "MISS"
                }
            };

            if (request.method === "GET" && response.statusCode === 200) {
                this.cache.set(cacheKey, proxiedResponse);
            }

            return proxiedResponse;
        } catch (error) {
            return {
                statusCode: 502,
                headers: {
                    "content-type": "text/plain; charset=utf-8"
                },
                body: `Bad Gateway: ${error.message}`
            };
        }
    }
}


// ============================================================
// 6. TIMEOUTS
// ============================================================

function withTimeout(promise, milliseconds) {
    let timer;

    const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => {
            reject(new Error("Backend request timed out"));
        }, milliseconds);
    });

    return Promise.race([promise, timeout])
        .finally(() => clearTimeout(timer));
}


// ============================================================
// 7. SECURITY HEADERS
// ============================================================

function addSecurityHeaders(response) {
    return {
        ...response,
        headers: {
            ...response.headers,
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "referrer-policy": "strict-origin-when-cross-origin",
            "content-security-policy": "default-src 'self'"
        }
    };
}


// ============================================================
// 8. REQUEST LOGGING
// ============================================================

function logRequest(request, response, durationMilliseconds) {
    // A real production logger should emit structured JSON and
    // should never log passwords, session tokens, or authorization headers.
    console.log(JSON.stringify({
        timestamp: new Date().toISOString(),
        method: request.method,
        url: request.url,
        status: response.statusCode,
        durationMs: Number(durationMilliseconds.toFixed(2))
    }));
}


// ============================================================
// 9. REAL NODE.JS HTTP SERVER
// ============================================================

function createServer() {
    const application = new ApplicationServer();

    const backends = [
        new BackendServer("app-1", application),
        new BackendServer("app-2", application),
        new BackendServer("app-3", application)
    ];

    const proxy = new ReverseProxy(backends);

    return http.createServer(async (request, response) => {
        const start = process.hrtime.bigint();

        try {
            let result = await proxy.handle(request);
            result = addSecurityHeaders(result);

            response.writeHead(
                result.statusCode,
                result.headers
            );

            response.end(result.body);

            const elapsed =
                Number(process.hrtime.bigint() - start) / 1_000_000;

            logRequest(request, result, elapsed);
        } catch (error) {
            response.writeHead(500, {
                "content-type": "text/plain; charset=utf-8"
            });
            response.end("Internal Server Error");

            console.error("Unhandled server error:", error);
        }
    });
}


// ============================================================
// 10. CONCEPTUAL DEMONSTRATIONS
// ============================================================

async function demonstrateProxy() {
    const application = new ApplicationServer();

    const backends = [
        new BackendServer("app-1", application),
        new BackendServer("app-2", application),
        new BackendServer("app-3", application)
    ];

    const proxy = new ReverseProxy(backends);

    console.log("\n=== Reverse proxy ===");

    for (let index = 0; index < 6; index++) {
        const request = {
            method: "GET",
            url: `/api/hello?name=user-${index}`,
            headers: {
                host: "example.test"
            }
        };

        const result = await proxy.handle(request);

        console.log(
            `request=${index + 1}`,
            `status=${result.statusCode}`,
            `backend=${result.headers["x-backend"] || "cache"}`
        );
    }

    console.log("\n=== Health failure ===");

    backends[1].healthy = false;
    backends[2].healthy = false;

    const result = await proxy.handle({
        method: "GET",
        url: "/api/hello?name=survivor",
        headers: { host: "example.test" }
    });

    console.log(result.statusCode, result.body);
}


// ============================================================
// 11. CRYPTOGRAPHIC REQUEST ID
// ============================================================

function demonstrateRequestId() {
    // Request IDs make distributed logs easier to correlate.
    // Random UUIDs are identifiers, not authentication credentials.
    const requestId = crypto.randomUUID();

    console.log("\n=== Request correlation ===");
    console.log("Request ID:", requestId);
}


// ============================================================
// 12. MAIN
// ============================================================

async function main() {
    demonstrateHttpStructure();

    console.log("\n=== Architectural roles ===");
    console.log("Web server: HTTP boundary and static-content delivery");
    console.log("Reverse proxy: receives and forwards client traffic");
    console.log("Application server: executes business/application logic");
    console.log("Load balancer: distributes requests among backends");
    console.log("Cache: reuses eligible responses");

    await demonstrateProxy();
    demonstrateRequestId();

    if (process.env.RUN_HTTP_SERVER === "1") {
        const server = createServer();

        server.listen(8080, "127.0.0.1", () => {
            console.log(
                "\nNode HTTP server running at http://127.0.0.1:8080"
            );
            console.log("Press Ctrl+C to stop.");
        });
    } else {
        console.log(
            "\nSet RUN_HTTP_SERVER=1 to start the local HTTP server."
        );
    }
}

main().catch(error => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
