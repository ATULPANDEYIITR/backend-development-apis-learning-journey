"use strict";

/*
 * Catalog Search Engine
 *
 * Demonstrates:
 * - Dynamic filter composition
 * - Search parameter validation
 * - Multi-field searching
 * - Stable sorting
 * - Pagination
 * - Event-driven search
 * - Asynchronous execution
 * - Query inspection
 * - Cancellation and failure handling
 *
 * Runtime: Node.js 18+
 */

const { EventEmitter } = require("node:events");
const assert = require("node:assert/strict");

class SearchError extends Error {
    constructor(message) {
        super(message);
        this.name = "SearchError";
    }
}

class ValidationError extends SearchError {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

const SORT_FIELDS = new Set([
    "id",
    "name",
    "category",
    "price",
    "rating",
    "createdAt"
]);

const DIRECTIONS = new Set(["asc", "desc"]);

const PRODUCTS = [
    {
        id: 1,
        name: "Laptop Pro",
        category: "Electronics",
        price: 95000,
        rating: 4.8,
        active: true,
        createdAt: "2026-01-10"
    },
    {
        id: 2,
        name: "Wireless Mouse",
        category: "Electronics",
        price: 1200,
        rating: 4.2,
        active: true,
        createdAt: "2026-02-15"
    },
    {
        id: 3,
        name: "Mechanical Keyboard",
        category: "Electronics",
        price: 4500,
        rating: 4.6,
        active: true,
        createdAt: "2026-03-01"
    },
    {
        id: 4,
        name: "Office Chair",
        category: "Furniture",
        price: 12500,
        rating: 4.3,
        active: true,
        createdAt: "2026-03-12"
    },
    {
        id: 5,
        name: "Standing Desk",
        category: "Furniture",
        price: 22000,
        rating: 4.7,
        active: true,
        createdAt: "2026-04-10"
    },
    {
        id: 6,
        name: "Old Monitor",
        category: "Electronics",
        price: 8000,
        rating: 3.5,
        active: false,
        createdAt: "2025-12-01"
    },
    {
        id: 7,
        name: "Notebook",
        category: "Stationery",
        price: 100,
        rating: 4.0,
        active: true,
        createdAt: "2026-05-01"
    },
    {
        id: 8,
        name: "Premium Headphones",
        category: "Electronics",
        price: 6500,
        rating: 4.9,
        active: true,
        createdAt: "2026-06-01"
    },
    {
        id: 9,
        name: "Desk Lamp",
        category: "Furniture",
        price: 1800,
        rating: 3.9,
        active: true,
        createdAt: "2026-06-15"
    },
    {
        id: 10,
        name: "USB Hub",
        category: "Electronics",
        price: 1500,
        rating: 4.1,
        active: true,
        createdAt: "2026-07-01"
    }
];

function normalizeText(value) {
    return String(value).trim().toLocaleLowerCase("en");
}

function validateCriteria(criteria) {
    if (!criteria || typeof criteria !== "object") {
        throw new ValidationError("Search criteria must be an object.");
    }

    const {
        keyword = "",
        category,
        minPrice,
        maxPrice,
        minRating,
        activeOnly = true,
        sortBy = "name",
        direction = "asc",
        limit = 10,
        offset = 0
    } = criteria;

    if (typeof keyword !== "string" || keyword.length > 100) {
        throw new ValidationError("Invalid keyword.");
    }

    if (
        category !== undefined &&
        (typeof category !== "string" || category.length > 80)
    ) {
        throw new ValidationError("Invalid category.");
    }

    for (const [name, value] of [
        ["minPrice", minPrice],
        ["maxPrice", maxPrice]
    ]) {
        if (
            value !== undefined &&
            (!Number.isFinite(value) || value < 0)
        ) {
            throw new ValidationError(`${name} must be non-negative.`);
        }
    }

    if (
        minPrice !== undefined &&
        maxPrice !== undefined &&
        minPrice > maxPrice
    ) {
        throw new ValidationError("Minimum price exceeds maximum price.");
    }

    if (
        minRating !== undefined &&
        (!Number.isFinite(minRating) ||
            minRating < 0 ||
            minRating > 5)
    ) {
        throw new ValidationError("Rating must be between 0 and 5.");
    }

    if (typeof activeOnly !== "boolean") {
        throw new ValidationError("activeOnly must be boolean.");
    }

    if (!SORT_FIELDS.has(sortBy)) {
        throw new ValidationError("Unsupported sorting field.");
    }

    if (!DIRECTIONS.has(direction)) {
        throw new ValidationError("Unsupported sorting direction.");
    }

    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
        throw new ValidationError("Limit must be between 1 and 100.");
    }

    if (!Number.isInteger(offset) || offset < 0) {
        throw new ValidationError("Offset cannot be negative.");
    }

    return {
        keyword: keyword.trim(),
        category: category?.trim(),
        minPrice,
        maxPrice,
        minRating,
        activeOnly,
        sortBy,
        direction,
        limit,
        offset
    };
}

class QueryBuilder {
    static build(criteria) {
        const filters = [];
        const parameters = [];

        if (criteria.activeOnly) {
            filters.push({
                name: "active",
                operator: "=",
                value: true
            });
        }

        if (criteria.keyword) {
            filters.push({
                name: "keyword",
                operator: "contains",
                value: criteria.keyword
            });
        }

        if (criteria.category) {
            filters.push({
                name: "category",
                operator: "=",
                value: criteria.category
            });
        }

        if (criteria.minPrice !== undefined) {
            filters.push({
                name: "price",
                operator: ">=",
                value: criteria.minPrice
            });
        }

        if (criteria.maxPrice !== undefined) {
            filters.push({
                name: "price",
                operator: "<=",
                value: criteria.maxPrice
            });
        }

        if (criteria.minRating !== undefined) {
            filters.push({
                name: "rating",
                operator: ">=",
                value: criteria.minRating
            });
        }

        for (const filter of filters) {
            parameters.push(filter.value);
        }

        return {
            filters,
            parameters,
            sort: {
                field: criteria.sortBy,
                direction: criteria.direction
            },
            pagination: {
                limit: criteria.limit,
                offset: criteria.offset
            }
        };
    }
}

class CatalogRepository {
    constructor(products) {
        this.products = products.map(product =>
            Object.freeze({ ...product })
        );
    }

    async execute(query, signal) {
        if (signal?.aborted) {
            throw new SearchError("Search was cancelled.");
        }

        // Simulates an asynchronous repository or database request.
        await new Promise(resolve => setImmediate(resolve));

        if (signal?.aborted) {
            throw new SearchError("Search was cancelled.");
        }

        let results = this.products;

        for (const filter of query.filters) {
            switch (filter.name) {
                case "active":
                    results = results.filter(
                        item => item.active === filter.value
                    );
                    break;

                case "keyword": {
                    const term = normalizeText(filter.value);

                    results = results.filter(item =>
                        normalizeText(item.name).includes(term) ||
                        normalizeText(item.category).includes(term)
                    );
                    break;
                }

                case "category":
                    results = results.filter(
                        item =>
                            normalizeText(item.category) ===
                            normalizeText(filter.value)
                    );
                    break;

                case "price":
                    results = results.filter(item =>
                        filter.operator === ">="
                            ? item.price >= filter.value
                            : item.price <= filter.value
                    );
                    break;

                case "rating":
                    results = results.filter(
                        item => item.rating >= filter.value
                    );
                    break;

                default:
                    throw new SearchError("Unknown query filter.");
            }
        }

        const total = results.length;
        const { field, direction } = query.sort;

        results = [...results].sort((a, b) => {
            const left = a[field];
            const right = b[field];

            let comparison;

            if (typeof left === "string") {
                comparison = left.localeCompare(right);
            } else {
                comparison = left - right;
            }

            if (comparison === 0) {
                return a.id - b.id;
            }

            return direction === "asc"
                ? comparison
                : -comparison;
        });

        const { offset, limit } = query.pagination;

        const page = results.slice(offset, offset + limit);

        return {
            results: page,
            total,
            limit,
            offset,
            hasNext: offset + page.length < total
        };
    }
}

class SearchEngine extends EventEmitter {
    constructor(repository) {
        super();
        this.repository = repository;
        this.requestCount = 0;
    }

    async search(criteria, options = {}) {
        const requestId = ++this.requestCount;

        try {
            const validated = validateCriteria(criteria);

            const query = QueryBuilder.build(validated);

            this.emit("search:started", {
                requestId,
                filters: query.filters.length
            });

            const result = await this.repository.execute(
                query,
                options.signal
            );

            this.emit("search:completed", {
                requestId,
                total: result.total,
                returned: result.results.length
            });

            return {
                requestId,
                ...result
            };

        } catch (error) {
            this.emit("search:failed", {
                requestId,
                message: error.message
            });

            if (error instanceof SearchError) {
                throw error;
            }

            throw new SearchError("Unexpected search failure.");
        }
    }

    async getAll(criteria, pageSize = 5) {
        if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
            throw new ValidationError("Invalid page size.");
        }

        const allResults = [];
        let offset = 0;

        while (true) {
            const result = await this.search({
                ...criteria,
                limit: pageSize,
                offset
            });

            allResults.push(...result.results);

            if (!result.hasNext) {
                break;
            }

            offset += pageSize;
        }

        return allResults;
    }
}

async function runTests(engine) {
    const electronics = await engine.search({
        category: "Electronics"
    });

    assert.equal(electronics.total, 6);

    const expensive = await engine.search({
        minPrice: 1000,
        maxPrice: 7000,
        minRating: 4,
        sortBy: "price",
        direction: "asc"
    });

    assert.ok(
        expensive.results.every(
            item =>
                item.price >= 1000 &&
                item.price <= 7000 &&
                item.rating >= 4
        )
    );

    const desks = await engine.search({
        keyword: "desk"
    });

    assert.equal(desks.total, 2);

    const firstPage = await engine.search({
        limit: 2,
        offset: 0
    });

    const secondPage = await engine.search({
        limit: 2,
        offset: 2
    });

    assert.notEqual(
        firstPage.results[0].id,
        secondPage.results[0].id
    );

    const all = await engine.getAll({}, 3);
    assert.equal(all.length, 9);

    await assert.rejects(
        engine.search({
            minPrice: 10000,
            maxPrice: 100
        }),
        ValidationError
    );

    await assert.rejects(
        engine.search({
            sortBy: "arbitrary_sql"
        }),
        ValidationError
    );

    await assert.rejects(
        engine.search({
            limit: 1000
        }),
        ValidationError
    );

    const controller = new AbortController();
    controller.abort();

    await assert.rejects(
        engine.search({}, { signal: controller.signal }),
        /cancelled/
    );

    console.log("All tests passed.");
}

async function main() {
    const repository = new CatalogRepository(PRODUCTS);
    const engine = new SearchEngine(repository);

    engine.on("search:started", event => {
        console.log(
            `[START] Request ${event.requestId}, filters=${event.filters}`
        );
    });

    engine.on("search:completed", event => {
        console.log(
            `[COMPLETE] Request ${event.requestId}, ` +
            `matched=${event.total}, returned=${event.returned}`
        );
    });

    engine.on("search:failed", event => {
        console.log(
            `[FAILED] Request ${event.requestId}: ${event.message}`
        );
    });

    try {
        console.log("\n1. Keyword search");

        console.log(
            JSON.stringify(
                await engine.search({
                    keyword: "keyboard"
                }),
                null,
                2
            )
        );

        console.log("\n2. Combined filtering");

        console.log(
            JSON.stringify(
                await engine.search({
                    category: "Electronics",
                    minPrice: 1000,
                    maxPrice: 10000,
                    minRating: 4,
                    sortBy: "rating",
                    direction: "desc"
                }),
                null,
                2
            )
        );

        console.log("\n3. Pagination");

        console.log(
            JSON.stringify(
                await engine.search({
                    sortBy: "price",
                    direction: "asc",
                    limit: 3,
                    offset: 0
                }),
                null,
                2
            )
        );

        console.log("\n4. Tests");

        await runTests(engine);

        console.log("\n5. Invalid filter");

        try {
            await engine.search({
                minRating: 9
            });
        } catch (error) {
            console.log(`Rejected: ${error.message}`);
        }

    } catch (error) {
        console.error("Application error:", error.message);
        process.exitCode = 1;
    }
}

if (require.main === module) {
    main();
}

module.exports = {
    SearchEngine,
    CatalogRepository,
    QueryBuilder,
    validateCriteria,
    ValidationError,
    SearchError
};
