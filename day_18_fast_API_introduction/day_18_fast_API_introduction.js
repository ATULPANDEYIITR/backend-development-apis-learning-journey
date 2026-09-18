/**
 * FastAPI Introduction
 * =====================
 *
 * JavaScript companion file for:
 *   FastAPI architecture
 *   application instance
 *   routes
 *   decorators
 *   path operations
 *
 * This file focuses on the JavaScript concepts that help explain HTTP,
 * routing, request handling, asynchronous execution, validation, and API
 * architecture around a FastAPI service.
 *
 * It runs without external npm packages:
 *
 *     node fastapi_introduction.js
 *
 * The built-in http module is used to create a small API server so the
 * relationship between a web server, routes, path parameters, query
 * parameters, and handlers can be observed directly.
 */

"use strict";

const http = require("node:http");
const { URL } = require("node:url");


// ============================================================================
// 1. HTTP FOUNDATIONS
// ============================================================================

console.log("=".repeat(78));
console.log("FASTAPI INTRODUCTION - JAVASCRIPT COMPANION");
console.log("=".repeat(78));

function explainHttpRequest() {
    const request = {
        method: "GET",
        path: "/users/42",
        query: {
            active: "true"
        },
        headers: {
            accept: "application/json"
        }
    };

    const response = {
        statusCode: 200,
        headers: {
            "content-type": "application/json"
        },
        body: {
            id: 42,
            name: "Ada"
        }
    };

    console.log("\n--- HTTP request ---");
    console.log(JSON.stringify(request, null, 2));

    console.log("\n--- HTTP response ---");
    console.log(JSON.stringify(response, null, 2));
}

explainHttpRequest();


// ============================================================================
// 2. JAVASCRIPT FUNCTIONS AS ENDPOINT HANDLERS
// ============================================================================

function helloWorld() {
    return {
        message: "Hello from a JavaScript HTTP handler"
    };
}

function getUser(userId) {
    return {
        id: Number(userId),
        name: "Example User"
    };
}

console.log("\n--- Basic handlers ---");
console.log(helloWorld());
console.log(getUser("42"));


// ============================================================================
// 3. ROUTE REGISTRATION
// ============================================================================

class Router {
    constructor() {
        this.routes = [];
    }

    register(method, path, handler) {
        this.routes.push({
            method: method.toUpperCase(),
            path,
            handler
        });
    }

    get(path, handler) {
        this.register("GET", path, handler);
    }

    post(path, handler) {
        this.register("POST", path, handler);
    }

    put(path, handler) {
        this.register("PUT", path, handler);
    }

    patch(path, handler) {
        this.register("PATCH", path, handler);
    }

    delete(path, handler) {
        this.register("DELETE", path, handler);
    }

    listRoutes() {
        return [...this.routes];
    }
}

const router = new Router();

router.get("/", () => ({
    message: "API is running"
}));

router.get("/health", () => ({
    status: "ok"
}));

router.get("/users/:userId", ({ params }) => ({
    id: Number(params.userId),
    name: "Example User"
}));

router.post("/users", ({ body }) => ({
    message: "User received",
    user: body
}));

console.log("\n--- Registered JavaScript routes ---");
console.table(
    router.listRoutes().map(route => ({
        method: route.method,
        path: route.path,
        handler: route.handler.name || "anonymous"
    }))
);


// ============================================================================
// 4. DECORATOR-STYLE REGISTRATION CONCEPT
// ============================================================================

function registerGetRoute(targetRouter, path) {
    return function endpointDecorator(handler) {
        targetRouter.get(path, handler);
        return handler;
    };
}

const decoratorRouter = new Router();

const getStatus = registerGetRoute(
    decoratorRouter,
    "/status"
)(function getStatus() {
    return {
        status: "available"
    };
});

console.log("\n--- Decorator-style registration ---");
console.log(getStatus());
console.log(decoratorRouter.listRoutes());

/*
FastAPI uses Python decorator syntax such as:

    @app.get("/status")
    def get_status():
        ...

JavaScript does not use Python's decorator syntax here. The example above
models the same underlying idea:

    route metadata + HTTP method + path + handler function

are registered together.
*/


// ============================================================================
// 5. PATH PARAMETER EXTRACTION
// ============================================================================

function compileRoutePath(pathPattern) {
    const parameterNames = [];

    const escaped = pathPattern
        .split("/")
        .map(segment => {
            if (
                segment.startsWith(":") &&
                segment.length > 1
            ) {
                const parameterName = segment.slice(1);
                parameterNames.push(parameterName);
                return "([^/]+)";
            }

            return segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        })
        .join("/");

    return {
        regex: new RegExp(`^${escaped}$`),
        parameterNames
    };
}

function matchRoutePath(pathPattern, actualPath) {
    const compiled = compileRoutePath(pathPattern);
    const match = compiled.regex.exec(actualPath);

    if (!match) {
        return null;
    }

    const params = {};

    compiled.parameterNames.forEach((name, index) => {
        params[name] = decodeURIComponent(match[index + 1]);
    });

    return params;
}

console.log("\n--- Path matching ---");
console.log(
    matchRoutePath(
        "/users/:userId",
        "/users/42"
    )
);

console.log(
    matchRoutePath(
        "/orders/:orderId/items/:itemId",
        "/orders/10/items/55"
    )
);

console.log(
    matchRoutePath(
        "/users/:userId",
        "/products/42"
    )
);


// ============================================================================
// 6. REQUEST URL PARSING
// ============================================================================

function parseRequestUrl(requestUrl) {
    const parsedUrl = new URL(
        requestUrl,
        "http://localhost"
    );

    const query = {};

    for (const [key, value] of parsedUrl.searchParams.entries()) {
        query[key] = value;
    }

    return {
        path: parsedUrl.pathname,
        query
    };
}

console.log("\n--- URL parsing ---");
console.log(
    parseRequestUrl(
        "/products/42?limit=5&active=true"
    )
);


// ============================================================================
// 7. QUERY PARAMETERS
// ============================================================================

function searchProducts({ query }) {
    const limit = query.limit
        ? Number(query.limit)
        : 10;

    return {
        search: query.q ?? null,
        limit
    };
}

console.log("\n--- Query parameters ---");
console.log(
    searchProducts({
        query: {
            q: "keyboard",
            limit: "5"
        }
    })
);


// ============================================================================
// 8. VALIDATION
// ============================================================================

function validatePositiveInteger(value, fieldName = "value") {
    const number = Number(value);

    if (!Number.isInteger(number)) {
        throw new TypeError(
            `${fieldName} must be an integer`
        );
    }

    if (number <= 0) {
        throw new RangeError(
            `${fieldName} must be greater than zero`
        );
    }

    return number;
}

console.log("\n--- Validation ---");

for (const value of ["10", "1", "0", "abc"]) {
    try {
        console.log(
            value,
            "->",
            validatePositiveInteger(value, "userId")
        );
    } catch (error) {
        console.log(
            value,
            "->",
            `${error.name}: ${error.message}`
        );
    }
}


// ============================================================================
// 9. REQUEST BODY VALIDATION
// ============================================================================

function validateProduct(product) {
    if (!product || typeof product !== "object") {
        throw new TypeError(
            "Product body must be an object"
        );
    }

    if (
        typeof product.name !== "string" ||
        product.name.trim().length === 0
    ) {
        throw new TypeError(
            "Product name must be a non-empty string"
        );
    }

    const price = Number(product.price);

    if (!Number.isFinite(price) || price <= 0) {
        throw new RangeError(
            "Product price must be a positive number"
        );
    }

    return {
        name: product.name.trim(),
        price
    };
}

console.log("\n--- Product body validation ---");

console.log(
    validateProduct({
        name: "Monitor",
        price: 199.99
    })
);

try {
    validateProduct({
        name: "",
        price: -5
    });
} catch (error) {
    console.log(
        `${error.name}: ${error.message}`
    );
}


// ============================================================================
// 10. ASYNC PATH OPERATION CONCEPT
// ============================================================================

function delay(milliseconds) {
    return new Promise(resolve => {
        setTimeout(resolve, milliseconds);
    });
}

async function asynchronousHandler() {
    await delay(10);

    return {
        mode: "async",
        message: "Asynchronous operation completed"
    };
}

console.log("\n--- Asynchronous handler ---");

asynchronousHandler()
    .then(result => {
        console.log(result);
    })
    .catch(error => {
        console.error(error);
    });

/*
FastAPI supports:

    async def endpoint():
        ...

JavaScript uses:

    async function endpoint() {
        await ...
    }

Both models support asynchronous I/O, but their surrounding runtime and
framework architecture differ.
*/


// ============================================================================
// 11. APPLICATION INSTANCE
// ============================================================================

class Application {
    constructor(options = {}) {
        this.name = options.name ?? "JavaScript API";
        this.version = options.version ?? "1.0.0";
        this.router = new Router();
    }

    get(path, handler) {
        this.router.get(path, handler);
        return this;
    }

    post(path, handler) {
        this.router.post(path, handler);
        return this;
    }

    put(path, handler) {
        this.router.put(path, handler);
        return this;
    }

    delete(path, handler) {
        this.router.delete(path, handler);
        return this;
    }

    listRoutes() {
        return this.router.listRoutes();
    }
}

const app = new Application({
    name: "FastAPI Concepts API",
    version: "1.0.0"
});

app.get("/", () => ({
    message: "Application instance is running"
}));

app.get("/health", () => ({
    status: "ok"
}));

app.get("/products/:productId", ({ params }) => ({
    productId: validatePositiveInteger(
        params.productId,
        "productId"
    )
}));

console.log("\n--- Application instance ---");
console.log({
    name: app.name,
    version: app.version,
    routes: app.listRoutes().length
});


// ============================================================================
// 12. ROUTE DISPATCH
// ============================================================================

function dispatch(routerObject, method, path, request = {}) {
    const normalizedMethod = method.toUpperCase();

    for (const route of routerObject.listRoutes()) {
        if (route.method !== normalizedMethod) {
            continue;
        }

        const params = matchRoutePath(
            route.path,
            path
        );

        if (params === null) {
            continue;
        }

        return route.handler({
            ...request,
            params
        });
    }

    const error = new Error(
        `No route for ${normalizedMethod} ${path}`
    );

    error.statusCode = 404;
    throw error;
}

console.log("\n--- Route dispatch ---");

console.log(
    dispatch(
        app.router,
        "GET",
        "/health"
    )
);

console.log(
    dispatch(
        app.router,
        "GET",
        "/products/25"
    )
);

try {
    dispatch(
        app.router,
        "GET",
        "/unknown"
    );
} catch (error) {
    console.log(
        `${error.statusCode}: ${error.message}`
    );
}


// ============================================================================
// 13. CRUD CASE STUDY
// ============================================================================

const products = new Map([
    [
        1,
        {
            id: 1,
            name: "Keyboard",
            price: 49.99
        }
    ],
    [
        2,
        {
            id: 2,
            name: "Monitor",
            price: 199.99
        }
    ]
]);

let nextProductId = 3;

function createProduct(product) {
    const validated = validateProduct(product);

    const record = {
        id: nextProductId++,
        ...validated
    };

    products.set(record.id, record);

    return record;
}

function findProduct(productId) {
    const id = validatePositiveInteger(
        productId,
        "productId"
    );

    const product = products.get(id);

    if (!product) {
        const error = new Error(
            "Product not found"
        );

        error.statusCode = 404;
        throw error;
    }

    return product;
}

function updateProduct(productId, product) {
    const existing = findProduct(productId);
    const validated = validateProduct(product);

    const updated = {
        ...existing,
        ...validated
    };

    products.set(existing.id, updated);

    return updated;
}

function deleteProduct(productId) {
    const existing = findProduct(productId);
    products.delete(existing.id);

    return true;
}

console.log("\n--- CRUD case study ---");

console.log(
    "Created:",
    createProduct({
        name: "Webcam",
        price: 79.99
    })
);

console.log(
    "Found:",
    findProduct(1)
);

console.log(
    "Updated:",
    updateProduct(1, {
        name: "Mechanical Keyboard",
        price: 89.99
    })
);

console.log(
    "Deleted:",
    deleteProduct(2)
);


// ============================================================================
// 14. ROUTE-SPECIFIC CRUD APPLICATION
// ============================================================================

const crudApp = new Application({
    name: "Product Service",
    version: "1.0.0"
});

crudApp.get(
    "/products/:productId",
    ({ params }) => findProduct(params.productId)
);

crudApp.post(
    "/products",
    ({ body }) => createProduct(body)
);

crudApp.put(
    "/products/:productId",
    ({ params, body }) => updateProduct(
        params.productId,
        body
    )
);

crudApp.delete(
    "/products/:productId",
    ({ params }) => {
        deleteProduct(params.productId);

        return {
            message: "Product deleted"
        };
    }
);

console.log("\n--- CRUD routes ---");
console.table(
    crudApp.listRoutes().map(route => ({
        method: route.method,
        path: route.path
    }))
);


// ============================================================================
// 15. ROUTE ORDERING
// ============================================================================

const orderingRouter = new Router();

orderingRouter.get(
    "/users/:userId",
    ({ params }) => ({
        matched: "dynamic user",
        userId: params.userId
    })
);

orderingRouter.get(
    "/users/me",
    () => ({
        matched: "current user"
    })
);

console.log("\n--- Route ordering ---");

console.log(
    "With dynamic route registered first:",
    dispatch(
        orderingRouter,
        "GET",
        "/users/me"
    )
);

/*
Many routers consider registration order when two patterns can match the same
URL. A robust router may apply additional specificity rules, but applications
should still avoid ambiguous route designs.

FastAPI applications should define overlapping static and dynamic paths
carefully.
*/


// ============================================================================
// 16. ERROR RESPONSES
// ============================================================================

function makeHttpError(statusCode, detail) {
    const error = new Error(detail);
    error.statusCode = statusCode;
    return error;
}

function safeDispatch(routerObject, method, path, request = {}) {
    try {
        return {
            statusCode: 200,
            body: dispatch(
                routerObject,
                method,
                path,
                request
            )
        };
    } catch (error) {
        return {
            statusCode: error.statusCode ?? 500,
            body: {
                detail: error.message
            }
        };
    }
}

console.log("\n--- Safe dispatch ---");

console.log(
    safeDispatch(
        crudApp.router,
        "GET",
        "/products/1"
    )
);

console.log(
    safeDispatch(
        crudApp.router,
        "GET",
        "/products/999999"
    )
);


// ============================================================================
// 17. HTTP SERVER
// ============================================================================

function readJsonBody(request) {
    return new Promise((resolve, reject) => {
        let rawBody = "";

        request.on("data", chunk => {
            rawBody += chunk;
        });

        request.on("end", () => {
            if (!rawBody.trim()) {
                resolve({});
                return;
            }

            try {
                resolve(JSON.parse(rawBody));
            } catch {
                const error = new Error(
                    "Request body is not valid JSON"
                );

                error.statusCode = 400;
                reject(error);
            }
        });

        request.on("error", reject);
    });
}

async function handleHttpRequest(request, response) {
    const parsedUrl = new URL(
        request.url,
        "http://localhost"
    );

    const method = request.method.toUpperCase();
    const path = parsedUrl.pathname;

    const query = {};

    for (const [key, value] of parsedUrl.searchParams.entries()) {
        query[key] = value;
    }

    let body = {};

    if (
        method === "POST" ||
        method === "PUT" ||
        method === "PATCH"
    ) {
        try {
            body = await readJsonBody(request);
        } catch (error) {
            response.writeHead(
                error.statusCode ?? 400,
                {
                    "content-type": "application/json"
                }
            );

            response.end(
                JSON.stringify({
                    detail: error.message
                })
            );

            return;
        }
    }

    try {
        const result = dispatch(
            crudApp.router,
            method,
            path,
            {
                query,
                body
            }
        );

        response.writeHead(
            200,
            {
                "content-type": "application/json"
            }
        );

        response.end(
            JSON.stringify(result)
        );
    } catch (error) {
        response.writeHead(
            error.statusCode ?? 500,
            {
                "content-type": "application/json"
            }
        );

        response.end(
            JSON.stringify({
                detail: error.message
            })
        );
    }
}


// ============================================================================
// 18. SERVER STARTUP
// ============================================================================

const PORT = 3001;

function startServer() {
    const server = http.createServer(
        handleHttpRequest
    );

    server.listen(PORT, () => {
        console.log(
            `\nJavaScript demonstration API listening on http://127.0.0.1:${PORT}`
        );
        console.log(
            "Example:"
        );
        console.log(
            `  http://127.0.0.1:${PORT}/products/1`
        );
        console.log(
            "Stop with Ctrl+C."
        );
    });

    return server;
}

/*
The server is intentionally started only when this file is executed directly.
This makes the module safer to import from another script.
*/

if (require.main === module) {
    startServer();
}


// ============================================================================
// 19. PERFORMANCE CONSIDERATIONS
// ============================================================================

function benchmarkRouting(iterations = 10000) {
    const start = process.hrtime.bigint();

    for (let index = 0; index < iterations; index += 1) {
        matchRoutePath(
            "/users/:userId/orders/:orderId",
            "/users/42/orders/99"
        );
    }

    const end = process.hrtime.bigint();

    const milliseconds =
        Number(end - start) / 1_000_000;

    console.log("\n--- Routing benchmark ---");
    console.log(
        `${iterations} matches: ${milliseconds.toFixed(3)} ms`
    );

    console.log(
        "This measures the educational router, not FastAPI."
    );
}

benchmarkRouting();


// ============================================================================
// 20. SECURITY CONSIDERATIONS
// ============================================================================

function securityChecklist() {
    const checklist = [
        "Treat path, query, headers, and body data as untrusted.",
        "Validate types and ranges.",
        "Authenticate protected operations.",
        "Authorize access to individual resources.",
        "Do not expose stack traces to clients.",
        "Use HTTPS in production.",
        "Protect secrets with environment or secret-management mechanisms.",
        "Use parameterized database queries.",
        "Apply appropriate request-size limits.",
        "Consider rate limiting for sensitive endpoints."
    ];

    console.log("\n--- Security checklist ---");

    for (const item of checklist) {
        console.log(`- ${item}`);
    }
}

securityChecklist();


// ============================================================================
// 21. FASTAPI AND JAVASCRIPT CONCEPTUAL MAPPING
// ============================================================================

const conceptualMapping = [
    {
        concept: "Application",
        fastapi: "FastAPI()",
        javascript: "new Application()"
    },
    {
        concept: "GET operation",
        fastapi: "@app.get('/users')",
        javascript: "app.get('/users', handler)"
    },
    {
        concept: "Path parameter",
        fastapi: "/users/{user_id}",
        javascript: "/users/:userId"
    },
    {
        concept: "Query parameter",
        fastapi: "limit: int = 10",
        javascript: "URL.searchParams"
    },
    {
        concept: "Request body",
        fastapi: "Pydantic model",
        javascript: "parsed JSON object"
    },
    {
        concept: "Async handler",
        fastapi: "async def",
        javascript: "async function"
    },
    {
        concept: "HTTP error",
        fastapi: "HTTPException",
        javascript: "Error + statusCode"
    }
];

console.log("\n--- Conceptual mapping ---");
console.table(conceptualMapping);


// ============================================================================
// 22. TESTS
// ============================================================================

function assertEqual(actual, expected, message) {
    if (
        JSON.stringify(actual) !==
        JSON.stringify(expected)
    ) {
        throw new Error(
            message ??
            `Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
        );
    }
}

function runTests() {
    console.log("\n--- Tests ---");

    assertEqual(
        matchRoutePath(
            "/users/:userId",
            "/users/42"
        ),
        {
            userId: "42"
        },
        "Path parameter should be extracted"
    );

    assertEqual(
        matchRoutePath(
            "/users/:userId",
            "/products/42"
        ),
        null,
        "Unrelated path should not match"
    );

    assertEqual(
        validatePositiveInteger("10"),
        10,
        "String integer should convert to number"
    );

    let validationFailed = false;

    try {
        validatePositiveInteger("invalid");
    } catch {
        validationFailed = true;
    }

    assertEqual(
        validationFailed,
        true,
        "Invalid integer should fail validation"
    );

    console.log("All JavaScript study tests passed.");
}

runTests();


// ============================================================================
// 23. ARCHITECTURAL NOTES
// ============================================================================

console.log(
    `
--- Architectural notes ---

FastAPI is an ASGI framework written for Python.

The key architectural relationship is:

HTTP request
    -> ASGI server
    -> FastAPI application
    -> router
    -> path operation
    -> dependencies and validation
    -> application logic
    -> serialized response

This JavaScript implementation intentionally models the same high-level
relationship using classes, functions, route registration, URL parsing,
validation, asynchronous functions, and Node's HTTP server.

The implementations are conceptually related but are not interchangeable.
FastAPI provides its own routing, validation, OpenAPI generation, dependency
injection, exception handling, and ASGI integration.
`
);
