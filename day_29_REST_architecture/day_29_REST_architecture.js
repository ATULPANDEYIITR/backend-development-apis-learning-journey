/*
 * REST Architecture: Resources, Representations, Statelessness,
 * and Uniform Interface
 *
 * Self-contained JavaScript demonstration.
 *
 * The implementation focuses on application-level REST concepts:
 * - resource-oriented URLs
 * - representations
 * - HTTP method semantics
 * - stateless request processing
 * - uniform interface
 * - validation
 * - content negotiation
 * - ETags and conditional requests
 * - hypermedia links
 * - pagination
 * - optimistic concurrency
 * - error representations
 * - asynchronous application behavior
 *
 * Run with:
 *   node rest-architecture.js
 */

"use strict";

// ============================================================================
// 1. FUNDAMENTAL REST CONCEPTS
// ============================================================================

function printConcepts() {
    const concepts = {
        Resource:
            "A conceptual entity identified by a URI, such as /books/42.",
        Representation:
            "A transferable format describing a resource, such as JSON.",
        Statelessness:
            "Each request contains the information required to process it.",
        UniformInterface:
            "Clients use consistent resource identifiers, representations, " +
            "messages, and links.",
        Idempotency:
            "Repeating an operation has the same intended state effect " +
            "as performing it once for an idempotent HTTP method.",
        SafeMethod:
            "A method intended to retrieve information without requesting " +
            "a state change."
    };

    console.log("=".repeat(80));
    console.log("REST ARCHITECTURE FUNDAMENTALS");
    console.log("=".repeat(80));

    for (const [name, definition] of Object.entries(concepts)) {
        console.log(`${name}: ${definition}`);
    }

    console.log();
}


// ============================================================================
// 2. RESOURCE CLASS
// ============================================================================

class Book {
    constructor({ id, title, author, year, genre }) {
        this.id = id;
        this.title = title;
        this.author = author;
        this.year = year;
        this.genre = genre;
        this.version = 1;
        this.createdAt = new Date().toISOString();
        this.updatedAt = this.createdAt;
    }

    toRepresentation(baseUrl) {
        return {
            id: this.id,
            title: this.title,
            author: this.author,
            year: this.year,
            genre: this.genre,
            links: {
                self: `${baseUrl}/books/${this.id}`,
                collection: `${baseUrl}/books`
            }
        };
    }
}


// ============================================================================
// 3. RESOURCE STORE
// ============================================================================

class BookStore {
    constructor() {
        this.books = new Map();
        this.nextId = 1;
    }

    list() {
        return [...this.books.values()].sort((a, b) => a.id - b.id);
    }

    get(id) {
        return this.books.get(id) ?? null;
    }

    create(data) {
        const book = new Book({
            id: this.nextId++,
            ...data
        });

        this.books.set(book.id, book);
        return book;
    }

    replace(id, data) {
        const book = this.get(id);

        if (!book) {
            return null;
        }

        book.title = data.title;
        book.author = data.author;
        book.year = data.year;
        book.genre = data.genre;
        book.version += 1;
        book.updatedAt = new Date().toISOString();

        return book;
    }

    patch(id, changes) {
        const book = this.get(id);

        if (!book) {
            return null;
        }

        for (const field of ["title", "author", "year", "genre"]) {
            if (Object.hasOwn(changes, field)) {
                book[field] = changes[field];
            }
        }

        book.version += 1;
        book.updatedAt = new Date().toISOString();

        return book;
    }

    delete(id) {
        return this.books.delete(id);
    }
}


// ============================================================================
// 4. VALIDATION
// ============================================================================

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

const allowedFields = new Set([
    "title",
    "author",
    "year",
    "genre"
]);

function validateBookPayload(payload, { partial = false } = {}) {
    if (
        payload === null ||
        typeof payload !== "object" ||
        Array.isArray(payload)
    ) {
        throw new ValidationError("Request body must be a JSON object.");
    }

    const keys = Object.keys(payload);

    for (const key of keys) {
        if (!allowedFields.has(key)) {
            throw new ValidationError(`Unknown field: ${key}`);
        }
    }

    if (!partial) {
        for (const field of allowedFields) {
            if (!Object.hasOwn(payload, field)) {
                throw new ValidationError(`Missing field: ${field}`);
            }
        }
    } else if (keys.length === 0) {
        throw new ValidationError("PATCH requires at least one field.");
    }

    if (Object.hasOwn(payload, "title")) {
        if (
            typeof payload.title !== "string" ||
            payload.title.trim().length === 0
        ) {
            throw new ValidationError("title must be a non-empty string.");
        }
    }

    if (Object.hasOwn(payload, "author")) {
        if (
            typeof payload.author !== "string" ||
            payload.author.trim().length === 0
        ) {
            throw new ValidationError("author must be a non-empty string.");
        }
    }

    if (Object.hasOwn(payload, "genre")) {
        if (
            typeof payload.genre !== "string" ||
            payload.genre.trim().length === 0
        ) {
            throw new ValidationError("genre must be a non-empty string.");
        }
    }

    if (Object.hasOwn(payload, "year")) {
        if (
            !Number.isInteger(payload.year) ||
            payload.year <= 0 ||
            payload.year > 3000
        ) {
            throw new ValidationError(
                "year must be an integer between 1 and 3000."
            );
        }
    }

    return payload;
}


// ============================================================================
// 5. REPRESENTATION HASHING
// ============================================================================

function stableStringify(value) {
    /*
     * JSON.stringify preserves insertion order, but ETag generation benefits
     * from deterministic key ordering. This recursive function creates a
     * canonical representation for this educational example.
     */
    if (value === null || typeof value !== "object") {
        return JSON.stringify(value);
    }

    if (Array.isArray(value)) {
        return `[${value.map(stableStringify).join(",")}]`;
    }

    return `{${Object.keys(value)
        .sort()
        .map(
            key =>
                `${JSON.stringify(key)}:${stableStringify(value[key])}`
        )
        .join(",")}}`;
}

async function sha256(text) {
    /*
     * Web Crypto is available in modern Node.js releases.
     * Hashing the representation gives a useful strong validator for this
     * demonstration.
     */
    const data = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest("SHA-256", data);

    return [...new Uint8Array(digest)]
        .map(byte => byte.toString(16).padStart(2, "0"))
        .join("");
}

async function calculateEtag(book, baseUrl) {
    const representation = book.toRepresentation(baseUrl);
    const canonical = stableStringify(representation);
    const digest = await sha256(canonical);

    return `"${digest}"`;
}


// ============================================================================
// 6. REST APPLICATION
// ============================================================================

class RestApplication {
    constructor(baseUrl = "http://localhost:8000") {
        this.baseUrl = baseUrl.replace(/\/$/, "");
        this.store = new BookStore();
    }

    seed() {
        this.store.create({
            title: "The Pragmatic Programmer",
            author: "Andrew Hunt",
            year: 1999,
            genre: "software"
        });

        this.store.create({
            title: "Clean Architecture",
            author: "Robert C. Martin",
            year: 2017,
            genre: "software"
        });

        this.store.create({
            title: "Designing Data-Intensive Applications",
            author: "Martin Kleppmann",
            year: 2017,
            genre: "data"
        });
    }

    response(status, body, headers = {}) {
        return {
            status,
            headers: {
                "Content-Type": "application/json; charset=utf-8",
                ...headers
            },
            body
        };
    }

    error(status, code, message, headers = {}) {
        return this.response(
            status,
            {
                error: {
                    code,
                    message
                }
            },
            headers
        );
    }

    async request({
        method,
        path,
        query = {},
        body = undefined,
        headers = {}
    }) {
        const normalizedMethod = method.toUpperCase();
        const normalizedHeaders = Object.fromEntries(
            Object.entries(headers).map(([key, value]) => [
                key.toLowerCase(),
                value
            ])
        );

        if (path === "/") {
            return this.response(200, {
                service: "REST Book API",
                links: {
                    books: `${this.baseUrl}/books`
                }
            });
        }

        if (path === "/books") {
            return this.handleCollection(
                normalizedMethod,
                query,
                body
            );
        }

        const match = path.match(/^\/books\/(\d+)$/);

        if (match) {
            return this.handleBook(
                normalizedMethod,
                Number(match[1]),
                body,
                normalizedHeaders
            );
        }

        return this.error(
            404,
            "not_found",
            "The requested resource does not exist."
        );
    }

    async handleCollection(method, query, body) {
        if (method === "GET") {
            const limit = Number(query.limit ?? 20);
            const offset = Number(query.offset ?? 0);

            if (
                !Number.isInteger(limit) ||
                limit < 1 ||
                limit > 100
            ) {
                return this.error(
                    400,
                    "invalid_query",
                    "limit must be an integer between 1 and 100."
                );
            }

            if (!Number.isInteger(offset) || offset < 0) {
                return this.error(
                    400,
                    "invalid_query",
                    "offset must be a non-negative integer."
                );
            }

            let books = this.store.list();

            if (query.author) {
                books = books.filter(
                    book =>
                        book.author.toLowerCase() ===
                        String(query.author).toLowerCase()
                );
            }

            if (query.genre) {
                books = books.filter(
                    book =>
                        book.genre.toLowerCase() ===
                        String(query.genre).toLowerCase()
                );
            }

            const total = books.length;
            const page = books.slice(offset, offset + limit);

            const representation = {
                items: page.map(book =>
                    book.toRepresentation(this.baseUrl)
                ),
                pagination: {
                    offset,
                    limit,
                    count: page.length,
                    total
                },
                links: {
                    self: `${this.baseUrl}/books?offset=${offset}&limit=${limit}`
                }
            };

            if (offset + limit < total) {
                representation.links.next =
                    `${this.baseUrl}/books?offset=${offset + limit}&limit=${limit}`;
            }

            if (offset > 0) {
                const previousOffset = Math.max(offset - limit, 0);

                representation.links.previous =
                    `${this.baseUrl}/books?offset=${previousOffset}&limit=${limit}`;
            }

            return this.response(200, representation, {
                "Cache-Control": "no-cache"
            });
        }

        if (method === "POST") {
            try {
                const payload = validateBookPayload(body);

                const book = this.store.create({
                    title: payload.title.trim(),
                    author: payload.author.trim(),
                    year: payload.year,
                    genre: payload.genre.trim()
                });

                return this.response(
                    201,
                    book.toRepresentation(this.baseUrl),
                    {
                        Location: `${this.baseUrl}/books/${book.id}`,
                        "ETag": await calculateEtag(
                            book,
                            this.baseUrl
                        )
                    }
                );
            } catch (error) {
                if (error instanceof ValidationError) {
                    return this.error(
                        400,
                        "invalid_representation",
                        error.message
                    );
                }

                throw error;
            }
        }

        return this.error(
            405,
            "method_not_allowed",
            "Method not allowed.",
            {
                Allow: "GET, POST"
            }
        );
    }

    async handleBook(method, id, body, headers) {
        const book = this.store.get(id);

        if (method === "GET") {
            if (!book) {
                return this.error(
                    404,
                    "not_found",
                    "Book does not exist."
                );
            }

            const etag = await calculateEtag(book, this.baseUrl);

            if (headers["if-none-match"] === etag) {
                return {
                    status: 304,
                    headers: {
                        ETag: etag
                    },
                    body: null
                };
            }

            return this.response(
                200,
                book.toRepresentation(this.baseUrl),
                {
                    ETag: etag,
                    "Cache-Control": "max-age=60"
                }
            );
        }

        if (method === "PUT") {
            if (!book) {
                return this.error(
                    404,
                    "not_found",
                    "Book does not exist."
                );
            }

            const currentEtag = await calculateEtag(
                book,
                this.baseUrl
            );

            if (
                headers["if-match"] &&
                headers["if-match"] !== currentEtag
            ) {
                return this.error(
                    412,
                    "precondition_failed",
                    "The representation changed before replacement."
                );
            }

            try {
                const payload = validateBookPayload(body);

                const updated = this.store.replace(id, {
                    title: payload.title.trim(),
                    author: payload.author.trim(),
                    year: payload.year,
                    genre: payload.genre.trim()
                });

                return this.response(
                    200,
                    updated.toRepresentation(this.baseUrl),
                    {
                        ETag: await calculateEtag(
                            updated,
                            this.baseUrl
                        )
                    }
                );
            } catch (error) {
                if (error instanceof ValidationError) {
                    return this.error(
                        400,
                        "invalid_representation",
                        error.message
                    );
                }

                throw error;
            }
        }

        if (method === "PATCH") {
            if (!book) {
                return this.error(
                    404,
                    "not_found",
                    "Book does not exist."
                );
            }

            const currentEtag = await calculateEtag(
                book,
                this.baseUrl
            );

            if (
                headers["if-match"] &&
                headers["if-match"] !== currentEtag
            ) {
                return this.error(
                    412,
                    "precondition_failed",
                    "The representation changed before the patch."
                );
            }

            try {
                const payload = validateBookPayload(body, {
                    partial: true
                });

                const normalized = { ...payload };

                for (const field of ["title", "author", "genre"]) {
                    if (Object.hasOwn(normalized, field)) {
                        normalized[field] = normalized[field].trim();
                    }
                }

                const updated = this.store.patch(id, normalized);

                return this.response(
                    200,
                    updated.toRepresentation(this.baseUrl),
                    {
                        ETag: await calculateEtag(
                            updated,
                            this.baseUrl
                        )
                    }
                );
            } catch (error) {
                if (error instanceof ValidationError) {
                    return this.error(
                        400,
                        "invalid_patch",
                        error.message
                    );
                }

                throw error;
            }
        }

        if (method === "DELETE") {
            /*
             * DELETE is idempotent at the resource-state level.
             * A second deletion does not introduce another state transition.
             */
            if (!book) {
                return {
                    status: 204,
                    headers: {},
                    body: null
                };
            }

            const currentEtag = await calculateEtag(
                book,
                this.baseUrl
            );

            if (
                headers["if-match"] &&
                headers["if-match"] !== currentEtag
            ) {
                return this.error(
                    412,
                    "precondition_failed",
                    "The representation changed before deletion."
                );
            }

            this.store.delete(id);

            return {
                status: 204,
                headers: {},
                body: null
            };
        }

        return this.error(
            405,
            "method_not_allowed",
            "Method not allowed.",
            {
                Allow: "GET, PUT, PATCH, DELETE"
            }
        );
    }
}


// ============================================================================
// 7. ASYNCHRONOUS HTTP CLIENT EXAMPLE
// ============================================================================

async function fetchRepresentation(url) {
    /*
     * fetch() is asynchronous because network operations should not block
     * JavaScript's main execution thread.
     *
     * The demonstration does not call an external service. Instead, this
     * function illustrates how an actual application could separate transport
     * from resource-processing logic.
     */
    const response = await fetch(url, {
        headers: {
            Accept: "application/json"
        }
    });

    if (!response.ok) {
        throw new Error(
            `HTTP ${response.status}: ${response.statusText}`
        );
    }

    return response.json();
}


// ============================================================================
// 8. CONTENT NEGOTIATION
// ============================================================================

function selectRepresentation(acceptHeader) {
    /*
     * A REST API can support multiple representations. HTTP clients can use
     * Accept to communicate which media types they prefer.
     */
    const accept = (acceptHeader || "").toLowerCase();

    if (accept.includes("application/json")) {
        return "application/json";
    }

    if (accept.includes("application/xml")) {
        return "application/xml";
    }

    if (accept.includes("*/*") || accept.trim() === "") {
        return "application/json";
    }

    return null;
}


// ============================================================================
// 9. DEMONSTRATIONS
// ============================================================================

async function demonstrateResources() {
    const app = new RestApplication();
    app.seed();

    console.log("=".repeat(80));
    console.log("RESOURCE INTERACTIONS");
    console.log("=".repeat(80));

    let result = await app.request({
        method: "GET",
        path: "/books"
    });

    console.log("GET /books");
    console.log("Status:", result.status);
    console.log(JSON.stringify(result.body, null, 2));
    console.log();

    result = await app.request({
        method: "GET",
        path: "/books",
        query: {
            genre: "software",
            limit: 1
        }
    });

    console.log("GET /books?genre=software&limit=1");
    console.log("Status:", result.status);
    console.log(JSON.stringify(result.body, null, 2));
    console.log();

    result = await app.request({
        method: "POST",
        path: "/books",
        body: {
            title: "RESTful Web Services",
            author: "Leonard Richardson",
            year: 2007,
            genre: "web"
        }
    });

    console.log("POST /books");
    console.log("Status:", result.status);
    console.log("Location:", result.headers.Location);
    console.log(JSON.stringify(result.body, null, 2));
    console.log();

    const createdId = result.body.id;

    result = await app.request({
        method: "GET",
        path: `/books/${createdId}`
    });

    console.log(`GET /books/${createdId}`);
    console.log("Status:", result.status);
    console.log("ETag:", result.headers.ETag);
    console.log(JSON.stringify(result.body, null, 2));
    console.log();

    const etag = result.headers.ETag;

    result = await app.request({
        method: "GET",
        path: `/books/${createdId}`,
        headers: {
            "If-None-Match": etag
        }
    });

    console.log("Conditional GET");
    console.log("Status:", result.status);
    console.log("Body:", result.body);
    console.log();

    result = await app.request({
        method: "PATCH",
        path: `/books/${createdId}`,
        headers: {
            "If-Match": etag
        },
        body: {
            genre: "web-architecture"
        }
    });

    console.log("PATCH /books/{id}");
    console.log("Status:", result.status);
    console.log(JSON.stringify(result.body, null, 2));
    console.log();

    result = await app.request({
        method: "DELETE",
        path: `/books/${createdId}`
    });

    console.log("DELETE /books/{id}");
    console.log("Status:", result.status);
    console.log("Body:", result.body);
    console.log();
}


async function demonstrateConcurrency() {
    const app = new RestApplication();
    app.seed();

    const initial = await app.request({
        method: "GET",
        path: "/books/1"
    });

    const staleEtag = initial.headers.ETag;

    await app.request({
        method: "PATCH",
        path: "/books/1",
        headers: {
            "If-Match": staleEtag
        },
        body: {
            genre: "client-b"
        }
    });

    const staleUpdate = await app.request({
        method: "PATCH",
        path: "/books/1",
        headers: {
            "If-Match": staleEtag
        },
        body: {
            genre: "client-a"
        }
    });

    console.log("=".repeat(80));
    console.log("OPTIMISTIC CONCURRENCY");
    console.log("=".repeat(80));
    console.log("Stale update status:", staleUpdate.status);
    console.log(JSON.stringify(staleUpdate.body, null, 2));
    console.log();
}


function demonstrateMethodProperties() {
    const methods = {
        GET: {
            safe: true,
            idempotent: true,
            purpose: "Retrieve a representation"
        },
        HEAD: {
            safe: true,
            idempotent: true,
            purpose: "Retrieve response metadata without a response body"
        },
        POST: {
            safe: false,
            idempotent: false,
            purpose: "Submit data for resource-specific processing"
        },
        PUT: {
            safe: false,
            idempotent: true,
            purpose: "Replace a representation at a known target URI"
        },
        PATCH: {
            safe: false,
            idempotent: "Not inherently",
            purpose: "Apply partial modifications"
        },
        DELETE: {
            safe: false,
            idempotent: true,
            purpose: "Remove a resource"
        }
    };

    console.log("=".repeat(80));
    console.log("HTTP METHOD SEMANTICS");
    console.log("=".repeat(80));

    console.table(methods);
    console.log();
}


function demonstrateStatelessness() {
    const requests = [
        {
            method: "GET",
            path: "/books/1",
            authorization: "Bearer example-token"
        },
        {
            method: "GET",
            path: "/books/2",
            authorization: "Bearer example-token"
        }
    ];

    console.log("=".repeat(80));
    console.log("STATELESS REQUESTS");
    console.log("=".repeat(80));

    for (const request of requests) {
        console.log(JSON.stringify(request, null, 2));
    }

    console.log(
        "\nNeither request needs a hidden 'current book' server session."
    );
    console.log();
}


function demonstrateSecurity() {
    const securityControls = [
        "Use HTTPS/TLS.",
        "Authenticate protected requests.",
        "Authorize each resource operation.",
        "Validate path, query, and body input.",
        "Apply request-size and rate limits.",
        "Do not expose secrets in representations.",
        "Avoid leaking internal errors.",
        "Configure CORS intentionally.",
        "Log security-sensitive operations safely.",
        "Do not trust client-supplied authorization claims without verification."
    ];

    console.log("=".repeat(80));
    console.log("SECURITY CONSIDERATIONS");
    console.log("=".repeat(80));

    securityControls.forEach((control, index) => {
        console.log(`${index + 1}. ${control}`);
    });

    console.log();
}


async function main() {
    printConcepts();
    demonstrateMethodProperties();
    demonstrateStatelessness();

    console.log(
        "Content negotiation:",
        selectRepresentation("application/json, application/xml;q=0.8")
    );

    console.log();

    await demonstrateResources();
    await demonstrateConcurrency();
    demonstrateSecurity();

    console.log("=".repeat(80));
    console.log("JavaScript REST demonstrations completed.");
    console.log("=".repeat(80));
}


main().catch(error => {
    console.error("Application error:", error);
    process.exitCode = 1;
});
