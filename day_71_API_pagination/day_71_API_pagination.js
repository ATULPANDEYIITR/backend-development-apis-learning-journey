"use strict";

/*
 * API PAGINATION ENGINE
 * Offset Pagination, Cursor Pagination, and Keyset Pagination.
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library.
 *
 * Engineering focus:
 * - Asynchronous repository operations.
 * - Event-driven pagination telemetry.
 * - Signed opaque cursors.
 * - Deterministic ordering.
 * - Policy-based pagination.
 * - Snapshot version checking.
 * - Forward and backward navigation.
 * - Input validation and structured errors.
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const { EventEmitter } = require("node:events");

// ==========================================================
// 1. CONSTANTS AND ERRORS
// ==========================================================

const Strategy = Object.freeze({
    OFFSET: "offset",
    CURSOR: "cursor",
    KEYSET: "keyset"
});

const MAX_PAGE_SIZE = 100;
const DEFAULT_PAGE_SIZE = 10;
const CURSOR_TTL_MS = 30 * 60 * 1000;

class PaginationError extends Error {
    constructor(message, code = "PAGINATION_ERROR") {
        super(message);
        this.name = "PaginationError";
        this.code = code;
    }
}

class InvalidCursorError extends PaginationError {
    constructor(message) {
        super(message, "INVALID_CURSOR");
        this.name = "InvalidCursorError";
    }
}

class StaleCursorError extends PaginationError {
    constructor(message) {
        super(message, "STALE_CURSOR");
        this.name = "StaleCursorError";
    }
}

// ==========================================================
// 2. VALIDATION
// ==========================================================

function validatePageSize(value) {
    if (
        !Number.isSafeInteger(value) ||
        value < 1 ||
        value > MAX_PAGE_SIZE
    ) {
        throw new PaginationError(
            `Page size must be between 1 and ${MAX_PAGE_SIZE}.`,
            "INVALID_PAGE_SIZE"
        );
    }

    return value;
}

function validatePage(value) {
    if (!Number.isSafeInteger(value) || value < 1) {
        throw new PaginationError(
            "Page must be a positive integer.",
            "INVALID_PAGE"
        );
    }

    return value;
}

function normalizeCategory(category) {
    if (category === undefined || category === null) {
        return null;
    }

    if (
        typeof category !== "string" ||
        category.trim().length === 0
    ) {
        throw new PaginationError("Invalid category filter.");
    }

    return category.trim().toLowerCase();
}

// ==========================================================
// 3. PRODUCT DOMAIN
// ==========================================================

class Product {
    constructor({
        id,
        name,
        category,
        price,
        createdAt,
        active = true
    }) {
        if (!Number.isSafeInteger(id) || id <= 0) {
            throw new PaginationError("Invalid product ID.");
        }

        if (typeof name !== "string" || !name.trim()) {
            throw new PaginationError("Product name is required.");
        }

        if (
            typeof price !== "number" ||
            !Number.isFinite(price) ||
            price < 0
        ) {
            throw new PaginationError("Invalid product price.");
        }

        const date = new Date(createdAt);

        if (Number.isNaN(date.getTime())) {
            throw new PaginationError("Invalid creation timestamp.");
        }

        this.id = id;
        this.name = name.trim();
        this.category = String(category).trim();
        this.price = price;
        this.createdAt = date.toISOString();
        this.active = Boolean(active);

        Object.freeze(this);
    }
}

// ==========================================================
// 4. ASYNCHRONOUS REPOSITORY
// ==========================================================

class ProductRepository extends EventEmitter {

    #products = new Map();
    #version = 1;

    constructor(products = []) {
        super();

        for (const product of products) {
            this.insert(product);
        }
    }

    get version() {
        return this.#version;
    }

    insert(product) {
        if (!(product instanceof Product)) {
            throw new TypeError("Expected Product instance.");
        }

        if (this.#products.has(product.id)) {
            throw new PaginationError("Duplicate product ID.");
        }

        this.#products.set(product.id, product);
        this.#version++;

        this.emit("product:inserted", {
            id: product.id,
            version: this.#version
        });
    }

    update(product) {
        if (!this.#products.has(product.id)) {
            throw new PaginationError("Product not found.");
        }

        this.#products.set(product.id, product);
        this.#version++;

        this.emit("product:updated", {
            id: product.id,
            version: this.#version
        });
    }

    delete(id) {
        if (!this.#products.delete(id)) {
            return false;
        }

        this.#version++;

        this.emit("product:deleted", {
            id,
            version: this.#version
        });

        return true;
    }

    async findAll() {
        // A real database implementation would use parameterized SQL.
        return Array.from(this.#products.values());
    }

    async count() {
        return this.#products.size;
    }
}

// ==========================================================
// 5. SIGNED CURSOR SERVICE
// ==========================================================

class CursorService {

    #secret;

    constructor(secret) {
        if (!Buffer.isBuffer(secret) || secret.length < 32) {
            throw new TypeError(
                "Cursor secret must be a Buffer of at least 32 bytes."
            );
        }

        this.#secret = Buffer.from(secret);
    }

    encode(payload) {
        const body = Buffer.from(
            JSON.stringify(payload)
        ).toString("base64url");

        const signature = crypto
            .createHmac("sha256", this.#secret)
            .update(body)
            .digest("base64url");

        return `${body}.${signature}`;
    }

    decode(token) {
        if (
            typeof token !== "string" ||
            token.length > 4096
        ) {
            throw new InvalidCursorError("Invalid cursor format.");
        }

        const parts = token.split(".");

        if (parts.length !== 2) {
            throw new InvalidCursorError("Malformed cursor.");
        }

        const [body, suppliedSignature] = parts;

        const expectedSignature = crypto
            .createHmac("sha256", this.#secret)
            .update(body)
            .digest();

        let actualSignature;

        try {
            actualSignature = Buffer.from(
                suppliedSignature,
                "base64url"
            );
        } catch {
            throw new InvalidCursorError("Invalid signature.");
        }

        if (
            actualSignature.length !== expectedSignature.length ||
            !crypto.timingSafeEqual(
                actualSignature,
                expectedSignature
            )
        ) {
            throw new InvalidCursorError(
                "Cursor authentication failed."
            );
        }

        let payload;

        try {
            payload = JSON.parse(
                Buffer.from(body, "base64url").toString("utf8")
            );
        } catch {
            throw new InvalidCursorError("Invalid cursor payload.");
        }

        if (
            !payload ||
            typeof payload !== "object" ||
            Array.isArray(payload)
        ) {
            throw new InvalidCursorError("Invalid cursor structure.");
        }

        if (
            !Number.isSafeInteger(payload.expiresAt) ||
            payload.expiresAt < Date.now()
        ) {
            throw new InvalidCursorError("Cursor expired.");
        }

        return payload;
    }
}

// ==========================================================
// 6. PAGINATION POLICY
// ==========================================================

class PaginationPolicy {

    constructor({
        defaultSize = DEFAULT_PAGE_SIZE,
        maximumSize = MAX_PAGE_SIZE,
        allowOffset = true,
        allowCursor = true,
        allowKeyset = true
    } = {}) {
        this.defaultSize = validatePageSize(defaultSize);
        this.maximumSize = validatePageSize(maximumSize);

        this.allowed = new Set();

        if (allowOffset) this.allowed.add(Strategy.OFFSET);
        if (allowCursor) this.allowed.add(Strategy.CURSOR);
        if (allowKeyset) this.allowed.add(Strategy.KEYSET);
    }

    validate(strategy, pageSize) {
        if (!this.allowed.has(strategy)) {
            throw new PaginationError(
                `Pagination strategy ${strategy} is disabled.`
            );
        }

        const size = validatePageSize(
            pageSize ?? this.defaultSize
        );

        if (size > this.maximumSize) {
            throw new PaginationError(
                "Requested page exceeds policy maximum."
            );
        }

        return size;
    }
}

// ==========================================================
// 7. PAGINATION SERVICE
// ==========================================================

class PaginationService extends EventEmitter {

    constructor(repository, cursorService, policy) {
        super();

        this.repository = repository;
        this.cursorService = cursorService;
        this.policy = policy;

        this.repository.on("product:inserted", event => {
            this.emit("repository:changed", event);
        });

        this.repository.on("product:deleted", event => {
            this.emit("repository:changed", event);
        });
    }

    async getOrderedProducts(category = null) {
        const normalized = normalizeCategory(category);

        const products = await this.repository.findAll();

        const filtered = products.filter(product =>
            product.active &&
            (
                normalized === null ||
                product.category.toLowerCase() === normalized
            )
        );

        return filtered.sort((a, b) =>
            a.createdAt.localeCompare(b.createdAt) ||
            a.id - b.id
        );
    }

    async execute(strategy, options = {}) {
        const pageSize = this.policy.validate(
            strategy,
            options.pageSize
        );

        const started = process.hrtime.bigint();

        let result;

        switch (strategy) {
            case Strategy.OFFSET:
                result = await this.offset(options, pageSize);
                break;

            case Strategy.CURSOR:
                result = await this.cursor(options, pageSize);
                break;

            case Strategy.KEYSET:
                result = await this.keyset(options, pageSize);
                break;

            default:
                throw new PaginationError(
                    "Unknown pagination strategy."
                );
        }

        const elapsedMs = Number(
            process.hrtime.bigint() - started
        ) / 1e6;

        result.executionMs = Number(elapsedMs.toFixed(4));

        this.emit("pagination:completed", {
            strategy,
            pageSize,
            executionMs: result.executionMs,
            returned: result.data.length
        });

        return result;
    }

    // OFFSET: convenient numbered pages with exact count.
    async offset(options, pageSize) {
        const page = validatePage(options.page ?? 1);

        const products = await this.getOrderedProducts(
            options.category
        );

        const total = products.length;
        const offset = (page - 1) * pageSize;

        if (!Number.isSafeInteger(offset)) {
            throw new PaginationError("Offset exceeds safe integer range.");
        }

        const data = products.slice(
            offset,
            offset + pageSize
        );

        return {
            strategy: Strategy.OFFSET,
            data,
            page,
            pageSize,
            total,
            totalPages: Math.ceil(total / pageSize),
            hasNext: offset + data.length < total,
            hasPrevious: page > 1 && offset > 0,
            nextOffset:
                offset + pageSize < total
                    ? offset + pageSize
                    : null
        };
    }

    // CURSOR: continuation token bound to filters and repository version.
    async cursor(options, pageSize) {
        const products = await this.getOrderedProducts(
            options.category
        );

        const filter = normalizeCategory(options.category) ?? "";

        const fingerprint = crypto
            .createHash("sha256")
            .update(filter)
            .digest("hex");

        const version = this.repository.version;

        let lastPosition = null;

        if (options.cursor) {
            const payload = this.cursorService.decode(
                options.cursor
            );

            if (
                payload.strategy !== Strategy.CURSOR ||
                payload.filter !== fingerprint
            ) {
                throw new InvalidCursorError(
                    "Cursor does not match this query."
                );
            }

            if (payload.version !== version) {
                throw new StaleCursorError(
                    "Dataset changed. Restart pagination."
                );
            }

            if (
                typeof payload.createdAt !== "string" ||
                !Number.isSafeInteger(payload.id)
            ) {
                throw new InvalidCursorError(
                    "Invalid cursor position."
                );
            }

            lastPosition = [
                payload.createdAt,
                payload.id
            ];
        }

        const remaining = lastPosition
            ? products.filter(product =>
                product.createdAt > lastPosition[0] ||
                (
                    product.createdAt === lastPosition[0] &&
                    product.id > lastPosition[1]
                )
            )
            : products;

        const window = remaining.slice(0, pageSize + 1);
        const hasNext = window.length > pageSize;
        const data = window.slice(0, pageSize);

        let nextCursor = null;

        if (hasNext && data.length) {
            const last = data[data.length - 1];

            nextCursor = this.cursorService.encode({
                strategy: Strategy.CURSOR,
                createdAt: last.createdAt,
                id: last.id,
                filter: fingerprint,
                version,
                expiresAt: Date.now() + CURSOR_TTL_MS
            });
        }

        return {
            strategy: Strategy.CURSOR,
            data,
            pageSize,
            total: null,
            hasNext,
            hasPrevious: Boolean(options.cursor),
            nextCursor
        };
    }

    // KEYSET: explicit composite boundary.
    async keyset(options, pageSize) {
        const products = await this.getOrderedProducts(
            options.category
        );

        const direction = options.direction ?? "asc";

        if (!["asc", "desc"].includes(direction)) {
            throw new PaginationError("Invalid sort direction.");
        }

        const hasTimestamp = options.lastCreatedAt !== undefined;
        const hasId = options.lastId !== undefined;

        if (hasTimestamp !== hasId) {
            throw new PaginationError(
                "Both keyset boundary fields are required."
            );
        }

        let boundary = null;

        if (hasTimestamp) {
            const timestamp = new Date(options.lastCreatedAt);

            if (
                Number.isNaN(timestamp.getTime()) ||
                !Number.isSafeInteger(options.lastId) ||
                options.lastId <= 0
            ) {
                throw new PaginationError("Invalid keyset boundary.");
            }

            boundary = [
                timestamp.toISOString(),
                options.lastId
            ];
        }

        const ordered = direction === "desc"
            ? [...products].reverse()
            : products;

        const remaining = boundary
            ? ordered.filter(product => {
                const comparison =
                    product.createdAt.localeCompare(boundary[0]) ||
                    Math.sign(product.id - boundary[1]);

                return direction === "asc"
                    ? comparison > 0
                    : comparison < 0;
            })
            : ordered;

        const window = remaining.slice(0, pageSize + 1);
        const hasNext = window.length > pageSize;
        const data = window.slice(0, pageSize);

        const last = data[data.length - 1];

        return {
            strategy: Strategy.KEYSET,
            data,
            pageSize,
            total: null,
            hasNext,
            hasPrevious: Boolean(boundary),
            nextBoundary: hasNext && last
                ? {
                    lastCreatedAt: last.createdAt,
                    lastId: last.id
                }
                : null
        };
    }
}

// ==========================================================
// 8. DATA GENERATION
// ==========================================================

function createDataset(count = 40) {
    const categories = [
        "Electronics",
        "Books",
        "Furniture",
        "Software"
    ];

    const products = [];

    for (let i = 1; i <= count; i++) {
        products.push(new Product({
            id: i,
            name: `Product ${i}`,
            category: categories[(i - 1) % categories.length],
            price: 100 + i * 25,
            createdAt: new Date(
                Date.UTC(2026, 0, 1, 0, Math.floor(i / 2))
            ),
            active: i % 13 !== 0
        }));
    }

    return products;
}

// ==========================================================
// 9. TESTS
// ==========================================================

async function runTests(service) {
    const offsetFirst = await service.execute(
        Strategy.OFFSET,
        { page: 1, pageSize: 5 }
    );

    const offsetSecond = await service.execute(
        Strategy.OFFSET,
        { page: 2, pageSize: 5 }
    );

    if (offsetFirst.data.length !== 5) {
        throw new Error("Offset test failed.");
    }

    if (offsetFirst.data.at(-1).id === offsetSecond.data[0].id) {
        throw new Error("Offset pages overlap.");
    }

    const cursorFirst = await service.execute(
        Strategy.CURSOR,
        { pageSize: 5 }
    );

    if (!cursorFirst.nextCursor) {
        throw new Error("Cursor generation failed.");
    }

    const cursorSecond = await service.execute(
        Strategy.CURSOR,
        {
            pageSize: 5,
            cursor: cursorFirst.nextCursor
        }
    );

    const firstIds = new Set(
        cursorFirst.data.map(p => p.id)
    );

    if (cursorSecond.data.some(p => firstIds.has(p.id))) {
        throw new Error("Cursor pages overlap.");
    }

    const keysetFirst = await service.execute(
        Strategy.KEYSET,
        { pageSize: 5 }
    );

    const last = keysetFirst.data.at(-1);

    const keysetSecond = await service.execute(
        Strategy.KEYSET,
        {
            pageSize: 5,
            lastCreatedAt: last.createdAt,
            lastId: last.id
        }
    );

    if (
        keysetSecond.data.some(p =>
            keysetFirst.data.some(first => first.id === p.id)
        )
    ) {
        throw new Error("Keyset pages overlap.");
    }

    try {
        await service.execute(
            Strategy.OFFSET,
            { page: 0, pageSize: 5 }
        );
        throw new Error("Invalid page was accepted.");
    } catch (error) {
        if (!(error instanceof PaginationError)) throw error;
    }

    console.log("All JavaScript pagination tests passed.");
}

// ==========================================================
// 10. EXECUTION
// ==========================================================

async function main() {
    const repository = new ProductRepository(
        createDataset()
    );

    const secret = crypto.randomBytes(32);

    const cursorService = new CursorService(secret);

    const policy = new PaginationPolicy({
        defaultSize: 10,
        maximumSize: 50
    });

    const service = new PaginationService(
        repository,
        cursorService,
        policy
    );

    service.on("pagination:completed", event => {
        console.log("Pagination event:", event);
    });

    service.on("repository:changed", event => {
        console.log("Repository mutation:", event);
    });

    await runTests(service);

    console.log("\nOFFSET PAGINATION");

    const offset = await service.execute(
        Strategy.OFFSET,
        { page: 2, pageSize: 5 }
    );

    console.log(offset);

    console.log("\nCURSOR PAGINATION");

    const cursor = await service.execute(
        Strategy.CURSOR,
        { pageSize: 5 }
    );

    console.log(cursor);

    if (cursor.nextCursor) {
        const next = await service.execute(
            Strategy.CURSOR,
            {
                pageSize: 5,
                cursor: cursor.nextCursor
            }
        );

        console.log(
            "Next cursor IDs:",
            next.data.map(p => p.id)
        );
    }

    console.log("\nKEYSET PAGINATION");

    const keyset = await service.execute(
        Strategy.KEYSET,
        { pageSize: 5 }
    );

    console.log(
        "First page:",
        keyset.data.map(p => p.id)
    );

    if (keyset.nextBoundary) {
        const next = await service.execute(
            Strategy.KEYSET,
            {
                pageSize: 5,
                ...keyset.nextBoundary
            }
        );

        console.log(
            "Next page:",
            next.data.map(p => p.id)
        );
    }

    const output = {
        generatedAt: new Date().toISOString(),
        pagination: offset
    };

    await fs.writeFile(
        "pagination-report.json",
        JSON.stringify(output, null, 2),
        { encoding: "utf8", mode: 0o600 }
    );

    console.log("\nReport written successfully.");
}

main().catch(error => {
    console.error({
        name: error.name,
        code: error.code ?? "UNEXPECTED_ERROR",
        message: error.message
    });

    process.exitCode = 1;
});
