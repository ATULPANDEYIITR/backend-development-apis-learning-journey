"use strict";

/**
 * API Response Design
 * Event-driven response processing and policy evaluation.
 * Runtime: Node.js 18+
 */

const { randomUUID } = require("node:crypto");
const { performance } = require("node:perf_hooks");
const { EventEmitter } = require("node:events");

const HTTP = Object.freeze({
    OK: 200,
    CREATED: 201,
    NO_CONTENT: 204,
    BAD_REQUEST: 400,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    CONFLICT: 409,
    UNPROCESSABLE: 422,
    RATE_LIMITED: 429,
    INTERNAL_ERROR: 500,
    UNAVAILABLE: 503
});

const ERROR_CODES = Object.freeze({
    VALIDATION_ERROR: "VALIDATION_ERROR",
    RESOURCE_NOT_FOUND: "RESOURCE_NOT_FOUND",
    CONFLICT: "CONFLICT",
    UNAUTHORIZED: "UNAUTHORIZED",
    FORBIDDEN: "FORBIDDEN",
    RATE_LIMITED: "RATE_LIMITED",
    INTERNAL_ERROR: "INTERNAL_ERROR",
    SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE"
});

class APIException extends Error {
    constructor(code, message, status, details = [], retryable = false) {
        super(message);
        this.name = "APIException";
        this.code = code;
        this.status = status;
        this.details = details;
        this.retryable = retryable;
    }
}

class ResponseEnvelope {
    constructor({ success, data = null, error = null, metadata }) {
        if (typeof success !== "boolean") {
            throw new TypeError("success must be boolean");
        }

        if (!metadata || typeof metadata !== "object") {
            throw new TypeError("metadata is required");
        }

        if (success && error !== null) {
            throw new Error("Successful response cannot contain an error");
        }

        if (!success && (error === null || data !== null)) {
            throw new Error("Failed response requires error and null data");
        }

        this.success = success;
        this.data = data;
        this.error = error;
        this.metadata = Object.freeze({ ...metadata });
        Object.freeze(this);
    }

    toJSON() {
        return {
            success: this.success,
            data: this.data,
            error: this.error,
            metadata: this.metadata
        };
    }
}

class ResponseBuilder {
    static metadata(requestId, startedAt, options = {}) {
        return {
            request_id: requestId,
            timestamp: new Date().toISOString(),
            api_version: "v1",
            duration_ms: Number(
                (performance.now() - startedAt).toFixed(3)
            ),
            pagination: options.pagination ?? null,
            links: options.links ?? {}
        };
    }

    static success(data, requestId, startedAt, options = {}) {
        return new ResponseEnvelope({
            success: true,
            data,
            error: null,
            metadata: this.metadata(requestId, startedAt, options)
        });
    }

    static failure(exception, requestId, startedAt) {
        return new ResponseEnvelope({
            success: false,
            data: null,
            error: {
                code: exception.code,
                message: exception.message,
                details: exception.details,
                retryable: exception.retryable
            },
            metadata: this.metadata(requestId, startedAt)
        });
    }
}

class ProductStore {
    #products = new Map();

    constructor() {
        this.#products.set(101, {
            id: 101,
            name: "Enterprise Laptop",
            price: 85000,
            currency: "INR",
            version: 1
        });

        this.#products.set(102, {
            id: 102,
            name: "Network Firewall",
            price: 125000,
            currency: "INR",
            version: 1
        });

        this.#products.set(103, {
            id: 103,
            name: "Secure Storage",
            price: 45000,
            currency: "INR",
            version: 1
        });
    }

    get(id) {
        const product = this.#products.get(id);

        if (!product) {
            throw new APIException(
                ERROR_CODES.RESOURCE_NOT_FOUND,
                "Product does not exist.",
                HTTP.NOT_FOUND
            );
        }

        return { ...product };
    }

    list(page, pageSize) {
        if (
            !Number.isSafeInteger(page) ||
            !Number.isSafeInteger(pageSize) ||
            page < 1 ||
            pageSize < 1 ||
            pageSize > 100
        ) {
            throw new APIException(
                ERROR_CODES.VALIDATION_ERROR,
                "Invalid pagination parameters.",
                HTTP.BAD_REQUEST,
                [{
                    field: "page_size",
                    reason: "Page must be positive and page size must be 1-100."
                }]
            );
        }

        const products = [...this.#products.values()]
            .sort((a, b) => a.id - b.id);

        const offset = (page - 1) * pageSize;

        return {
            items: products.slice(offset, offset + pageSize),
            total: products.length
        };
    }

    updatePrice(id, newPrice, expectedVersion) {
        if (
            typeof newPrice !== "number" ||
            !Number.isFinite(newPrice) ||
            newPrice <= 0
        ) {
            throw new APIException(
                ERROR_CODES.VALIDATION_ERROR,
                "Price must be a positive finite number.",
                HTTP.BAD_REQUEST
            );
        }

        const current = this.get(id);

        if (current.version !== expectedVersion) {
            throw new APIException(
                ERROR_CODES.CONFLICT,
                "The resource has changed.",
                HTTP.CONFLICT,
                [{
                    expected_version: expectedVersion,
                    actual_version: current.version
                }]
            );
        }

        const updated = {
            ...current,
            price: Math.round(newPrice * 100) / 100,
            version: current.version + 1
        };

        this.#products.set(id, updated);
        return { ...updated };
    }
}

class APIController extends EventEmitter {
    constructor(store) {
        super();
        this.store = store;
    }

    async handle(operation, options = {}) {
        const requestId = randomUUID();
        const startedAt = performance.now();

        try {
            // Promise-based execution supports asynchronous handlers.
            const data = await Promise.resolve().then(operation);

            const envelope = ResponseBuilder.success(
                data,
                requestId,
                startedAt,
                options
            );

            this.emit("response:success", {
                requestId,
                status: HTTP.OK
            });

            return {
                status: HTTP.OK,
                body: envelope.toJSON()
            };
        } catch (error) {
            const normalized = error instanceof APIException
                ? error
                : new APIException(
                    ERROR_CODES.INTERNAL_ERROR,
                    "An unexpected server error occurred.",
                    HTTP.INTERNAL_ERROR
                );

            // Log internal details separately from the public response.
            if (!(error instanceof APIException)) {
                console.error("Internal request failure:", requestId, error);
            }

            const envelope = ResponseBuilder.failure(
                normalized,
                requestId,
                startedAt
            );

            this.emit("response:error", {
                requestId,
                code: normalized.code,
                status: normalized.status
            });

            return {
                status: normalized.status,
                body: envelope.toJSON()
            };
        }
    }

    getProduct(id) {
        return this.handle(() => this.store.get(id));
    }

    listProducts(page = 1, pageSize = 10) {
        return this.handle(
            () => {
                const result = this.store.list(page, pageSize);
                const totalPages = Math.ceil(result.total / pageSize);

                return {
                    items: result.items,
                    pagination: {
                        page,
                        page_size: pageSize,
                        total_items: result.total,
                        total_pages: totalPages,
                        has_next: page < totalPages,
                        has_previous: page > 1
                    }
                };
            },
            {
                links: {
                    self: `/api/v1/products?page=${page}`,
                    first: "/api/v1/products?page=1"
                }
            }
        );
    }

    updatePrice(id, price, version) {
        return this.handle(
            () => this.store.updatePrice(id, price, version)
        );
    }
}

function assertEnvelope(response) {
    const body = response.body;

    const expectedKeys = [
        "success",
        "data",
        "error",
        "metadata"
    ];

    const actualKeys = Object.keys(body).sort();

    if (
        JSON.stringify(actualKeys) !==
        JSON.stringify(expectedKeys.sort())
    ) {
        throw new Error("Unexpected response envelope structure");
    }

    if (typeof body.success !== "boolean") {
        throw new Error("Invalid success field");
    }

    if (body.success && body.error !== null) {
        throw new Error("Success/error invariant violated");
    }

    if (!body.success && (body.error === null || body.data !== null)) {
        throw new Error("Failure/data invariant violated");
    }

    if (
        !body.metadata.request_id ||
        !body.metadata.timestamp ||
        !body.metadata.api_version
    ) {
        throw new Error("Required response metadata missing");
    }
}

async function main() {
    const store = new ProductStore();
    const controller = new APIController(store);

    controller.on("response:success", event => {
        console.log("SUCCESS EVENT:", event);
    });

    controller.on("response:error", event => {
        console.log("ERROR EVENT:", event);
    });

    const scenarios = [
        ["Retrieve product", () => controller.getProduct(101)],
        ["Missing product", () => controller.getProduct(999)],
        ["List products", () => controller.listProducts(1, 2)],
        ["Invalid pagination", () => controller.listProducts(0, 10)],
        ["Update price", () => controller.updatePrice(101, 89000, 1)],
        ["Stale version", () => controller.updatePrice(101, 92000, 1)]
    ];

    for (const [name, execute] of scenarios) {
        const response = await execute();

        assertEnvelope(response);

        console.log(`\n${"=".repeat(60)}`);
        console.log(name);
        console.log("HTTP:", response.status);
        console.log(JSON.stringify(response.body, null, 2));
    }

    const finalProduct = store.get(101);

    if (finalProduct.version !== 2) {
        throw new Error("Optimistic concurrency verification failed");
    }

    console.log("\nAll response and concurrency checks passed.");
}

main().catch(error => {
    console.error("Fatal application failure:", error);
    process.exitCode = 1;
});
