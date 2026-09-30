#!/usr/bin/env node

/**
 * REST API Design: a JavaScript-specific event-driven API workflow model.
 *
 * This implementation complements the Python service by modeling a request
 * pipeline with middleware, events, route matching, collection queries,
 * response envelopes, validation, and asynchronous request processing.
 *
 * Run with:
 *   node rest_api_design.js
 */

"use strict";

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");


// -----------------------------------------------------------------------------
// Response helpers
// -----------------------------------------------------------------------------

function createSuccess(status, data, meta = {}) {
    return {
        status,
        headers: {
            "content-type": "application/json",
        },
        body: {
            data,
            meta: {
                requestId: meta.requestId ?? null,
                timestamp: new Date().toISOString(),
                ...meta,
            },
        },
    };
}

function createError(status, code, message, details = []) {
    return {
        status,
        headers: {
            "content-type": "application/problem+json",
        },
        body: {
            error: {
                code,
                message,
                ...(details.length > 0 ? { details } : {}),
            },
            meta: {
                timestamp: new Date().toISOString(),
            },
        },
    };
}


// -----------------------------------------------------------------------------
// Resource store
// -----------------------------------------------------------------------------

class ResourceStore {
    constructor() {
        this.users = new Map([
            [
                1,
                {
                    id: 1,
                    name: "Atul Pandey",
                    email: "atul@example.com",
                },
            ],
            [
                2,
                {
                    id: 2,
                    name: "Priya Sharma",
                    email: "priya@example.com",
                },
            ],
        ]);

        this.orders = new Map([
            [
                501,
                {
                    id: 501,
                    userId: 1,
                    status: "confirmed",
                    total: 1499,
                },
            ],
            [
                502,
                {
                    id: 502,
                    userId: 1,
                    status: "pending",
                    total: 799,
                },
            ],
        ]);

        this.nextUserId = 3;
        this.nextOrderId = 503;
    }

    async findUser(id) {
        return this.users.get(id) ?? null;
    }

    async listUsers({ limit, offset, name }) {
        let users = [...this.users.values()];

        if (name) {
            const search = name.toLocaleLowerCase();
            users = users.filter((user) =>
                user.name.toLocaleLowerCase().includes(search)
            );
        }

        const total = users.length;

        return {
            items: users.slice(offset, offset + limit),
            total,
        };
    }

    async createUser(user) {
        this.users.set(user.id, user);
        return user;
    }

    async listUserOrders(userId) {
        return [...this.orders.values()].filter(
            (order) => order.userId === userId
        );
    }

    async createOrder(order) {
        this.orders.set(order.id, order);
        return order;
    }

    async findOrder(id) {
        return this.orders.get(id) ?? null;
    }
}


// -----------------------------------------------------------------------------
// Validation
// -----------------------------------------------------------------------------

function validateUserInput(payload, { partial = false } = {}) {
    const errors = [];

    if (!partial && payload.name === undefined) {
        errors.push({
            field: "name",
            reason: "required",
        });
    }

    if (!partial && payload.email === undefined) {
        errors.push({
            field: "email",
            reason: "required",
        });
    }

    if (payload.name !== undefined) {
        if (typeof payload.name !== "string") {
            errors.push({
                field: "name",
                reason: "must be a string",
            });
        } else if (payload.name.trim().length === 0) {
            errors.push({
                field: "name",
                reason: "must not be empty",
            });
        }
    }

    if (payload.email !== undefined) {
        if (typeof payload.email !== "string") {
            errors.push({
                field: "email",
                reason: "must be a string",
            });
        } else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(payload.email)) {
            errors.push({
                field: "email",
                reason: "invalid email format",
            });
        }
    }

    return errors;
}

function validatePagination(query) {
    const errors = [];

    const limit = query.limit === undefined
        ? 20
        : Number.parseInt(query.limit, 10);

    const offset = query.offset === undefined
        ? 0
        : Number.parseInt(query.offset, 10);

    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
        errors.push({
            field: "limit",
            reason: "must be an integer between 1 and 100",
        });
    }

    if (!Number.isInteger(offset) || offset < 0) {
        errors.push({
            field: "offset",
            reason: "must be a non-negative integer",
        });
    }

    return {
        errors,
        limit,
        offset,
    };
}


// -----------------------------------------------------------------------------
// Route patterns
// -----------------------------------------------------------------------------

class Route {
    constructor(method, pattern, handler) {
        this.method = method.toUpperCase();
        this.pattern = pattern;
        this.handler = handler;
    }

    match(method, pathname) {
        if (method.toUpperCase() !== this.method) {
            return null;
        }

        const patternParts = this.pattern.split("/").filter(Boolean);
        const pathParts = pathname.split("/").filter(Boolean);

        if (patternParts.length !== pathParts.length) {
            return null;
        }

        const params = {};

        for (let index = 0; index < patternParts.length; index += 1) {
            const expected = patternParts[index];
            const actual = pathParts[index];

            if (expected.startsWith(":")) {
                const key = expected.slice(1);
                params[key] = decodeURIComponent(actual);
                continue;
            }

            if (expected !== actual) {
                return null;
            }
        }

        return params;
    }
}


// -----------------------------------------------------------------------------
// Request context
// -----------------------------------------------------------------------------

class RequestContext {
    constructor(method, url, body = {}) {
        const parsed = new URL(url, "https://api.example.test");

        this.method = method.toUpperCase();
        this.url = parsed;
        this.path = parsed.pathname;
        this.query = Object.fromEntries(parsed.searchParams.entries());
        this.body = body;
        this.requestId = randomUUID();
        this.user = null;
    }
}


// -----------------------------------------------------------------------------
// REST service
// -----------------------------------------------------------------------------

class RestService extends EventEmitter {
    constructor(store) {
        super();
        this.store = store;
        this.routes = [];
        this.registerRoutes();
    }

    addRoute(method, pattern, handler) {
        this.routes.push(new Route(method, pattern, handler));
    }

    registerRoutes() {
        this.addRoute(
            "GET",
            "/users",
            async (request) => this.listUsers(request)
        );

        this.addRoute(
            "POST",
            "/users",
            async (request) => this.createUser(request)
        );

        this.addRoute(
            "GET",
            "/users/:userId",
            async (request) => this.getUser(request)
        );

        this.addRoute(
            "GET",
            "/users/:userId/orders",
            async (request) => this.listUserOrders(request)
        );

        this.addRoute(
            "POST",
            "/users/:userId/orders",
            async (request) => this.createUserOrder(request)
        );

        this.addRoute(
            "GET",
            "/orders/:orderId",
            async (request) => this.getOrder(request)
        );
    }

    async handle(request) {
        this.emit("request.received", request);

        const matchingPath = this.routes.filter(
            (route) => route.match(request.method, request.path) !== null
        );

        const route = this.routes.find(
            (candidate) => candidate.match(request.method, request.path) !== null
        );

        if (!route) {
            // A known path with an unsupported method can be distinguished from
            // an entirely unknown path by checking path-only matches.
            const pathExists = matchingPath.length > 0;

            const response = pathExists
                ? createError(
                    405,
                    "METHOD_NOT_ALLOWED",
                    `Method ${request.method} is not supported for ${request.path}.`
                )
                : createError(
                    404,
                    "ROUTE_NOT_FOUND",
                    `No resource route exists for ${request.path}.`
                );

            this.emit("request.completed", {
                request,
                response,
            });

            return response;
        }

        request.params = route.match(request.method, request.path);

        try {
            const response = await route.handler(request);

            response.body.meta = {
                ...response.body.meta,
                requestId: request.requestId,
            };

            this.emit("request.completed", {
                request,
                response,
            });

            return response;
        } catch (error) {
            this.emit("request.failed", {
                request,
                error,
            });

            return createError(
                500,
                "INTERNAL_SERVER_ERROR",
                "The server encountered an unexpected failure."
            );
        }
    }

    async listUsers(request) {
        const pagination = validatePagination(request.query);

        if (pagination.errors.length > 0) {
            return createError(
                422,
                "INVALID_QUERY",
                "The collection query is invalid.",
                pagination.errors
            );
        }

        const result = await this.store.listUsers({
            limit: pagination.limit,
            offset: pagination.offset,
            name: request.query.name,
        });

        return createSuccess(
            200,
            result.items,
            {
                pagination: {
                    limit: pagination.limit,
                    offset: pagination.offset,
                    total: result.total,
                },
            }
        );
    }

    async getUser(request) {
        const userId = Number(request.params.userId);

        if (!Number.isSafeInteger(userId)) {
            return createError(
                400,
                "INVALID_IDENTIFIER",
                "The user identifier is invalid."
            );
        }

        const user = await this.store.findUser(userId);

        if (!user) {
            return createError(
                404,
                "USER_NOT_FOUND",
                `User ${userId} does not exist.`
            );
        }

        return createSuccess(200, user);
    }

    async createUser(request) {
        const errors = validateUserInput(request.body);

        if (errors.length > 0) {
            return createError(
                422,
                "VALIDATION_FAILED",
                "The user representation failed validation.",
                errors
            );
        }

        const normalizedEmail = request.body.email.trim().toLowerCase();

        for (const user of this.store.users.values()) {
            if (user.email.toLowerCase() === normalizedEmail) {
                return createError(
                    409,
                    "EMAIL_ALREADY_EXISTS",
                    "A user with this email already exists."
                );
            }
        }

        const user = {
            id: this.store.nextUserId++,
            name: request.body.name.trim(),
            email: normalizedEmail,
        };

        await this.store.createUser(user);

        return {
            ...createSuccess(
                201,
                user,
                {
                    message: "User created.",
                }
            ),
            headers: {
                "content-type": "application/json",
                location: `/users/${user.id}`,
            },
        };
    }

    async listUserOrders(request) {
        const userId = Number(request.params.userId);

        if (!Number.isSafeInteger(userId)) {
            return createError(
                400,
                "INVALID_IDENTIFIER",
                "The user identifier is invalid."
            );
        }

        const user = await this.store.findUser(userId);

        if (!user) {
            return createError(
                404,
                "USER_NOT_FOUND",
                `User ${userId} does not exist.`
            );
        }

        const orders = await this.store.listUserOrders(userId);

        return createSuccess(
            200,
            orders,
            {
                relationship: "orders belonging to the addressed user",
            }
        );
    }

    async createUserOrder(request) {
        const userId = Number(request.params.userId);

        if (!Number.isSafeInteger(userId)) {
            return createError(
                400,
                "INVALID_IDENTIFIER",
                "The user identifier is invalid."
            );
        }

        const user = await this.store.findUser(userId);

        if (!user) {
            return createError(
                404,
                "USER_NOT_FOUND",
                `User ${userId} does not exist.`
            );
        }

        const amount = Number(request.body.total);

        if (!Number.isFinite(amount) || amount <= 0) {
            return createError(
                422,
                "INVALID_ORDER_TOTAL",
                "Order total must be a positive number."
            );
        }

        const order = {
            id: this.store.nextOrderId++,
            userId,
            status: "pending",
            total: Number(amount.toFixed(2)),
        };

        await this.store.createOrder(order);

        return {
            ...createSuccess(
                201,
                order,
                {
                    message: "Order created.",
                }
            ),
            headers: {
                "content-type": "application/json",
                location: `/orders/${order.id}`,
            },
        };
    }

    async getOrder(request) {
        const orderId = Number(request.params.orderId);

        if (!Number.isSafeInteger(orderId)) {
            return createError(
                400,
                "INVALID_IDENTIFIER",
                "The order identifier is invalid."
            );
        }

        const order = await this.store.findOrder(orderId);

        if (!order) {
            return createError(
                404,
                "ORDER_NOT_FOUND",
                `Order ${orderId} does not exist.`
            );
        }

        return createSuccess(200, order);
    }
}


// -----------------------------------------------------------------------------
// Middleware pipeline
// -----------------------------------------------------------------------------

function withRequestLogging(service) {
    const originalHandle = service.handle.bind(service);

    service.handle = async (request) => {
        console.log(
            `[request] ${request.method} ${request.path} ` +
            `requestId=${request.requestId}`
        );

        const response = await originalHandle(request);

        console.log(
            `[response] ${response.status} ` +
            `requestId=${request.requestId}`
        );

        return response;
    };

    return service;
}


// -----------------------------------------------------------------------------
// Event-driven observability
// -----------------------------------------------------------------------------

function attachObservability(service) {
    service.on("request.received", (request) => {
        console.log(
            `[event] request.received ${request.method} ${request.path}`
        );
    });

    service.on("request.completed", ({ request, response }) => {
        console.log(
            `[event] request.completed ${request.requestId} -> ${response.status}`
        );
    });

    service.on("request.failed", ({ request, error }) => {
        console.error(
            `[event] request.failed ${request.requestId}: ${error.message}`
        );
    });
}


// -----------------------------------------------------------------------------
// Request execution helper
// -----------------------------------------------------------------------------

async function execute(service, method, url, body = {}) {
    const request = new RequestContext(method, url, body);
    const response = await service.handle(request);

    console.log(
        JSON.stringify(
            {
                method,
                url,
                status: response.status,
                headers: response.headers,
                body: response.body,
            },
            null,
            2
        )
    );

    return response;
}


// -----------------------------------------------------------------------------
// API design inspection
// -----------------------------------------------------------------------------

function inspectResourcePaths() {
    const endpoints = [
        ["GET", "/users"],
        ["POST", "/users"],
        ["GET", "/users/:userId"],
        ["GET", "/users/:userId/orders"],
        ["POST", "/users/:userId/orders"],
        ["GET", "/orders/:orderId"],
    ];

    console.log("\nResource-oriented route inspection");
    console.log("----------------------------------");

    for (const [method, path] of endpoints) {
        const hasVerbPathSegment = path
            .split("/")
            .filter(Boolean)
            .some((segment) =>
                [
                    "get",
                    "create",
                    "fetch",
                    "update",
                    "delete",
                    "remove",
                ].includes(segment.toLowerCase())
            );

        console.log(
            `${method.padEnd(6)} ${path.padEnd(30)} ` +
            `${hasVerbPathSegment ? "verb-oriented" : "resource-oriented"}`
        );
    }
}


// -----------------------------------------------------------------------------
// Demonstration of HTTP semantics
// -----------------------------------------------------------------------------

function printMethodSemantics() {
    console.log("\nHTTP method semantics");
    console.log("---------------------");

    const semantics = new Map([
        [
            "GET",
            "Read a representation without requesting a state mutation.",
        ],
        [
            "POST",
            "Create a subordinate resource or submit a non-idempotent action.",
        ],
        [
            "PUT",
            "Replace the addressed resource representation.",
        ],
        [
            "PATCH",
            "Apply a partial modification to the addressed resource.",
        ],
        [
            "DELETE",
            "Remove the addressed resource.",
        ],
    ]);

    for (const [method, description] of semantics) {
        console.log(`${method.padEnd(7)} ${description}`);
    }
}


// -----------------------------------------------------------------------------
// Main asynchronous scenario
// -----------------------------------------------------------------------------

async function main() {
    console.log("REST API Design Demonstration");
    console.log("=============================");

    printMethodSemantics();
    inspectResourcePaths();

    const store = new ResourceStore();
    const service = attachObservability(
        withRequestLogging(
            new RestService(store)
        )
    );

    await execute(
        service,
        "GET",
        "/users?name=atul&limit=10&offset=0"
    );

    await execute(
        service,
        "GET",
        "/users/1"
    );

    await execute(
        service,
        "GET",
        "/users/1/orders"
    );

    await execute(
        service,
        "POST",
        "/users",
        {
            name: "Meera Singh",
            email: "meera@example.com",
        }
    );

    await execute(
        service,
        "POST",
        "/users/1/orders",
        {
            total: 2499.5,
        }
    );

    await execute(
        service,
        "GET",
        "/orders/503"
    );

    // Invalid semantic data is represented separately from malformed routing.
    await execute(
        service,
        "POST",
        "/users",
        {
            name: "",
            email: "invalid",
        }
    );

    // The resource route exists, but this operation is not registered.
    await execute(
        service,
        "DELETE",
        "/users/1"
    );

    // A completely unknown URI is a different failure from an unsupported
    // method on a known resource.
    await execute(
        service,
        "GET",
        "/customers/999"
    );

    await execute(
        service,
        "GET",
        "/users?limit=1000"
    );

    console.log("\nJavaScript-specific design observations");
    console.log("---------------------------------------");
    console.log(
        "URL parsing separates path parameters from query parameters, " +
        "allowing filtering and pagination to remain collection concerns."
    );
    console.log(
        "Promises and async handlers model the asynchronous nature of real " +
        "database, cache, and network operations."
    );
    console.log(
        "EventEmitter provides an event-driven observability boundary without " +
        "mixing logging logic into every resource operation."
    );
    console.log(
        "The router identifies resources while handler methods implement " +
        "resource-specific behavior and response semantics."
    );
}

main().catch((error) => {
    console.error("Fatal application error:", error);
    process.exitCode = 1;
});
