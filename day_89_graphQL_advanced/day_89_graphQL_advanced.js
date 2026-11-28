"use strict";

/*
 * ADVANCED GRAPHQL EXECUTION MODEL
 *
 * Features:
 * - Nested field resolution
 * - Fragments and fragment spreads
 * - Variables and argument validation
 * - Asynchronous resolvers
 * - Authentication and authorization
 * - DataLoader batching and caching
 * - Query complexity limits
 * - Error isolation
 * - Event-driven execution
 *
 * Runtime: Node.js 18+
 *
 * This executable model represents GraphQL operations as structured
 * documents. It focuses on execution semantics rather than parsing
 * GraphQL source text or implementing the complete GraphQL protocol.
 */

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");

// ============================================================
// ERRORS
// ============================================================

class GraphQLError extends Error {
    constructor(message, code = "GRAPHQL_ERROR") {
        super(message);
        this.name = "GraphQLError";
        this.code = code;
    }
}

class AuthenticationError extends GraphQLError {
    constructor() {
        super("Authentication required", "UNAUTHENTICATED");
    }
}

class AuthorizationError extends GraphQLError {
    constructor() {
        super("Insufficient permissions", "FORBIDDEN");
    }
}

class ValidationError extends GraphQLError {
    constructor(message) {
        super(message, "BAD_USER_INPUT");
    }
}

// ============================================================
// IN-MEMORY REPOSITORY
// ============================================================

class Repository {
    constructor() {
        this.users = new Map([
            [1, {
                id: 1,
                name: "Atul",
                email: "atul@example.com",
                role: "ADMIN"
            }],
            [2, {
                id: 2,
                name: "Rahul",
                email: "rahul@example.com",
                role: "EDITOR"
            }],
            [3, {
                id: 3,
                name: "Priya",
                email: "priya@example.com",
                role: "USER"
            }]
        ]);

        this.posts = new Map([
            [101, {
                id: 101,
                title: "GraphQL Nested Queries",
                authorId: 1,
                published: true
            }],
            [102, {
                id: 102,
                title: "DataLoader Patterns",
                authorId: 2,
                published: true
            }],
            [103, {
                id: 103,
                title: "Private Draft",
                authorId: 1,
                published: false
            }]
        ]);

        this.comments = [
            { id: 1001, postId: 101, authorId: 2, content: "Excellent." },
            { id: 1002, postId: 101, authorId: 3, content: "Very useful." },
            { id: 1003, postId: 102, authorId: 1, content: "Good approach." }
        ];

        this.queryCount = 0;
    }

    async findPosts(publishedOnly = true) {
        this.queryCount++;

        return [...this.posts.values()].filter(
            post => !publishedOnly || post.published
        );
    }

    async findUser(id) {
        this.queryCount++;
        return this.users.get(id) ?? null;
    }

    async findCommentsByPostIds(ids) {
        this.queryCount++;

        const requested = new Set(ids);
        const grouped = new Map();

        for (const id of requested) {
            grouped.set(id, []);
        }

        for (const comment of this.comments) {
            if (requested.has(comment.postId)) {
                grouped.get(comment.postId).push(comment);
            }
        }

        return grouped;
    }
}

// ============================================================
// ASYNCHRONOUS DATALOADER
// ============================================================

class DataLoader {
    constructor(batchFunction, maxBatchSize = 500) {
        if (typeof batchFunction !== "function") {
            throw new TypeError("batchFunction must be a function");
        }

        this.batchFunction = batchFunction;
        this.maxBatchSize = maxBatchSize;
        this.cache = new Map();
        this.pending = [];
        this.scheduled = false;
    }

    load(key) {
        if (!Number.isSafeInteger(key)) {
            return Promise.reject(
                new ValidationError("Loader key must be an integer")
            );
        }

        if (this.cache.has(key)) {
            return this.cache.get(key);
        }

        const promise = new Promise((resolve, reject) => {
            this.pending.push({ key, resolve, reject });
        });

        // Cache the promise immediately to deduplicate concurrent loads.
        this.cache.set(key, promise);

        if (!this.scheduled) {
            this.scheduled = true;
            queueMicrotask(() => this.dispatch());
        }

        return promise;
    }

    async dispatch() {
        this.scheduled = false;

        const batch = this.pending.splice(0);

        if (batch.length === 0) {
            return;
        }

        const uniqueKeys = [...new Set(batch.map(item => item.key))];

        try {
            const results = new Map();

            for (
                let offset = 0;
                offset < uniqueKeys.length;
                offset += this.maxBatchSize
            ) {
                const chunk = uniqueKeys.slice(
                    offset,
                    offset + this.maxBatchSize
                );

                const chunkResults = await this.batchFunction(chunk);

                for (const key of chunk) {
                    results.set(key, chunkResults.get(key) ?? []);
                }
            }

            for (const item of batch) {
                item.resolve(results.get(item.key));
            }
        } catch (error) {
            for (const item of batch) {
                this.cache.delete(item.key);
                item.reject(error);
            }
        }

        if (this.pending.length > 0 && !this.scheduled) {
            this.scheduled = true;
            queueMicrotask(() => this.dispatch());
        }
    }

    clear(key) {
        this.cache.delete(key);
        return this;
    }

    clearAll() {
        this.cache.clear();
        return this;
    }
}

// ============================================================
// AUTHORIZATION POLICY
// ============================================================

class AuthorizationPolicy {
    static authenticated(context) {
        if (!context.user || !context.user.active) {
            throw new AuthenticationError();
        }

        return context.user;
    }

    static requireRoles(context, roles) {
        const user = this.authenticated(context);

        if (!roles.includes(user.role)) {
            throw new AuthorizationError();
        }

        return user;
    }

    static canReadPost(context, post) {
        if (post.published) {
            return true;
        }

        const user = context.user;

        return Boolean(
            user &&
            user.active &&
            (user.role === "ADMIN" || user.id === post.authorId)
        );
    }

    static canReadEmail(context, target) {
        return Boolean(
            context.user &&
            context.user.active &&
            (
                context.user.role === "ADMIN" ||
                context.user.id === target.id
            )
        );
    }
}

// ============================================================
// QUERY COST ANALYSIS
// ============================================================

class ComplexityAnalyzer {
    constructor(maxCost = 100) {
        this.maxCost = maxCost;
    }

    calculate(selections, fragments = {}, stack = []) {
        let total = 0;

        for (const selection of selections) {
            if (selection.name.startsWith("...")) {
                const name = selection.name.slice(3);

                if (!fragments[name]) {
                    throw new ValidationError(
                        `Unknown fragment: ${name}`
                    );
                }

                if (stack.includes(name)) {
                    throw new ValidationError(
                        "Circular fragment detected"
                    );
                }

                total += this.calculate(
                    fragments[name].selections,
                    fragments,
                    [...stack, name]
                );

                continue;
            }

            const multiplier = selection.name === "posts" ? 5 : 1;

            total += multiplier * (
                1 + this.calculate(
                    selection.children ?? [],
                    fragments,
                    stack
                )
            );
        }

        return total;
    }

    validate(selections, fragments) {
        const cost = this.calculate(selections, fragments);

        if (cost > this.maxCost) {
            throw new ValidationError(
                `Query complexity ${cost} exceeds limit ${this.maxCost}`
            );
        }

        return cost;
    }
}

// ============================================================
// GRAPHQL EXECUTOR
// ============================================================

class GraphQLExecutor extends EventEmitter {
    constructor(repository) {
        super();

        this.repository = repository;
        this.complexity = new ComplexityAnalyzer(100);

        this.fields = {
            Query: ["posts", "me", "user"],
            Post: ["id", "title", "published", "author", "comments"],
            User: ["id", "name", "email", "role", "posts"],
            Comment: ["id", "content", "author"]
        };
    }

    createContext(user) {
        return {
            user,
            requestId: crypto.randomUUID(),
            loaders: {
                comments: new DataLoader(
                    ids => this.repository.findCommentsByPostIds(ids)
                )
            }
        };
    }

    resolveArguments(args, variables) {
        const resolve = value => {
            if (
                value &&
                typeof value === "object" &&
                !Array.isArray(value) &&
                Object.keys(value).length === 1 &&
                typeof value.$variable === "string"
            ) {
                const name = value.$variable;

                if (!(name in variables)) {
                    throw new ValidationError(
                        `Missing variable: $${name}`
                    );
                }

                return variables[name];
            }

            if (Array.isArray(value)) {
                return value.map(resolve);
            }

            if (value && typeof value === "object") {
                return Object.fromEntries(
                    Object.entries(value).map(
                        ([key, item]) => [key, resolve(item)]
                    )
                );
            }

            return value;
        };

        return resolve(args);
    }

    expandSelections(selections, fragments, type, stack = []) {
        const expanded = [];

        for (const selection of selections) {
            if (selection.name.startsWith("...")) {
                const name = selection.name.slice(3);
                const fragment = fragments[name];

                if (!fragment) {
                    throw new ValidationError(
                        `Fragment ${name} does not exist`
                    );
                }

                if (stack.includes(name)) {
                    throw new ValidationError(
                        "Circular fragment detected"
                    );
                }

                if (fragment.typeCondition === type) {
                    expanded.push(
                        ...this.expandSelections(
                            fragment.selections,
                            fragments,
                            type,
                            [...stack, name]
                        )
                    );
                }

                continue;
            }

            expanded.push(selection);
        }

        return expanded;
    }

    async resolveRoot(selection, args, context) {
        switch (selection.name) {
            case "posts": {
                const publishedOnly = args.publishedOnly ?? true;

                if (typeof publishedOnly !== "boolean") {
                    throw new ValidationError(
                        "publishedOnly must be Boolean"
                    );
                }

                if (!publishedOnly) {
                    AuthorizationPolicy.requireRoles(
                        context, ["ADMIN", "EDITOR"]
                    );
                }

                return this.repository.findPosts(publishedOnly);
            }

            case "me":
                return AuthorizationPolicy.authenticated(context);

            case "user": {
                AuthorizationPolicy.requireRoles(context, ["ADMIN"]);

                if (!Number.isSafeInteger(args.id)) {
                    throw new ValidationError(
                        "user.id must be an integer"
                    );
                }

                return this.repository.findUser(args.id);
            }

            default:
                throw new ValidationError(
                    `Unknown root field ${selection.name}`
                );
        }
    }

    async resolveField(parent, field, context) {
        if (parent.id === undefined) {
            throw new GraphQLError("Invalid parent object");
        }

        switch (field.name) {
            case "id":
            case "title":
            case "published":
            case "name":
            case "role":
            case "content":
                return parent[field.name];

            case "email":
                if (!AuthorizationPolicy.canReadEmail(context, parent)) {
                    throw new AuthorizationError();
                }
                return parent.email;

            case "author":
                return this.repository.users.get(parent.authorId) ?? null;

            case "comments":
                return context.loaders.comments.load(parent.id);

            case "posts":
                return [...this.repository.posts.values()].filter(
                    post => post.authorId === parent.id && post.published
                );

            default:
                throw new ValidationError(
                    `Unknown field: ${field.name}`
                );
        }
    }

    async project(value, selections, type, operation, context) {
        if (value === null || value === undefined) {
            return null;
        }

        if (Array.isArray(value)) {
            return Promise.all(
                value.map(item => this.project(
                    item, selections, type, operation, context
                ))
            );
        }

        const expanded = this.expandSelections(
            selections,
            operation.fragments ?? {},
            type
        );

        // Promise.all resolves sibling fields concurrently.
        // DataLoader collects their keys into shared batches.
        const entries = await Promise.all(
            expanded.map(async selection => {
                if (!this.fields[type]?.includes(selection.name)) {
                    throw new ValidationError(
                        `Unknown field ${selection.name} on ${type}`
                    );
                }

                const fieldValue = await this.resolveField(
                    value, selection, context
                );

                const outputName = selection.alias ?? selection.name;

                if (!selection.children?.length) {
                    if (
                        fieldValue !== null &&
                        typeof fieldValue === "object"
                    ) {
                        throw new ValidationError(
                            `${selection.name} requires nested selections`
                        );
                    }

                    return [outputName, fieldValue];
                }

                const childType = {
                    author: "User",
                    comments: "Comment",
                    posts: "Post"
                }[selection.name];

                if (!childType) {
                    throw new ValidationError(
                        `${selection.name} cannot contain nested selections`
                    );
                }

                return [
                    outputName,
                    await this.project(
                        fieldValue,
                        selection.children,
                        childType,
                        operation,
                        context
                    )
                ];
            })
        );

        return Object.fromEntries(entries);
    }

    async execute(operation, context) {
        const started = performance.now();

        try {
            if (!Array.isArray(operation.selections)) {
                throw new ValidationError(
                    "Operation selections are required"
                );
            }

            const cost = this.complexity.validate(
                operation.selections,
                operation.fragments ?? {}
            );

            const variables = operation.variables ?? {};
            const output = {};

            const rootResults = await Promise.all(
                operation.selections.map(async selection => {
                    if (!this.fields.Query.includes(selection.name)) {
                        throw new ValidationError(
                            `Unknown root field ${selection.name}`
                        );
                    }

                    const args = this.resolveArguments(
                        selection.arguments ?? {},
                        variables
                    );

                    const value = await this.resolveRoot(
                        selection, args, context
                    );

                    const rootType = selection.name === "me" ||
                        selection.name === "user" ? "User" : "Post";

                    if (!selection.children?.length) {
                        throw new ValidationError(
                            `${selection.name} requires selections`
                        );
                    }

                    return [
                        selection.alias ?? selection.name,
                        await this.project(
                            value,
                            selection.children,
                            rootType,
                            operation,
                            context
                        )
                    ];
                })
            );

            for (const [key, value] of rootResults) {
                output[key] = value;
            }

            const result = {
                data: output,
                extensions: {
                    requestId: context.requestId,
                    complexity: cost,
                    durationMs: Number(
                        (performance.now() - started).toFixed(3)
                    ),
                    databaseQueries: this.repository.queryCount
                }
            };

            this.emit("operation:completed", result);
            return result;

        } catch (error) {
            const result = {
                data: null,
                errors: [{
                    message: error.message,
                    code: error.code ?? "INTERNAL_ERROR"
                }]
            };

            this.emit("operation:failed", result);
            return result;
        }
    }
}

// ============================================================
// EXAMPLE OPERATION
// ============================================================

async function main() {
    const repository = new Repository();
    const executor = new GraphQLExecutor(repository);

    executor.on("operation:completed", result => {
        console.log(
            "Operation completed:",
            result.extensions.requestId
        );
    });

    executor.on("operation:failed", result => {
        console.error("Operation failed:", result.errors);
    });

    const operation = {
        variables: {
            published: true
        },

        fragments: {
            PostDetails: {
                typeCondition: "Post",
                selections: [
                    { name: "id" },
                    { name: "title" },
                    {
                        name: "author",
                        children: [
                            { name: "name" }
                        ]
                    },
                    {
                        name: "comments",
                        children: [
                            { name: "id" },
                            { name: "content" },
                            {
                                name: "author",
                                children: [
                                    { name: "name" }
                                ]
                            }
                        ]
                    }
                ]
            }
        },

        selections: [
            {
                name: "posts",
                arguments: {
                    publishedOnly: {
                        $variable: "published"
                    }
                },
                children: [
                    { name: "...PostDetails" }
                ]
            },
            {
                name: "me",
                children: [
                    { name: "id" },
                    { name: "name" }
                ]
            }
        ]
    };

    const admin = repository.users.get(1);
    const context = executor.createContext(admin);

    const result = await executor.execute(operation, context);

    console.log("\nGRAPHQL RESPONSE");
    console.log(JSON.stringify(result, null, 2));

    if (!result.data) {
        throw new Error("Demo operation failed");
    }

    if (result.data.posts.length !== 2) {
        throw new Error("Unexpected post count");
    }

    if (repository.queryCount !== 1) {
        throw new Error(
            `Expected one batched query, got ${repository.queryCount}`
        );
    }

    console.log("\nDATALOADER BATCHING TEST PASSED");

    // Authorization test.
    const guestContext = executor.createContext(
        repository.users.get(3)
    );

    const denied = await executor.execute({
        selections: [{
            name: "user",
            arguments: { id: 1 },
            children: [{ name: "email" }]
        }]
    }, guestContext);

    if (denied.errors?.[0]?.code !== "FORBIDDEN") {
        throw new Error("Authorization test failed");
    }

    console.log("AUTHORIZATION TEST PASSED");

    // Missing variable test.
    const missingVariable = await executor.execute({
        variables: {},
        selections: [{
            name: "posts",
            arguments: {
                publishedOnly: { $variable: "missing" }
            },
            children: [{ name: "id" }]
        }]
    }, context);

    if (!missingVariable.errors) {
        throw new Error("Variable validation test failed");
    }

    console.log("VARIABLE VALIDATION TEST PASSED");

    // Query complexity test.
    const limitedExecutor = new GraphQLExecutor(repository);
    limitedExecutor.complexity = new ComplexityAnalyzer(2);

    const rejected = await limitedExecutor.execute({
        selections: [{
            name: "posts",
            children: [{ name: "id" }]
        }]
    }, context);

    if (!rejected.errors) {
        throw new Error("Complexity validation test failed");
    }

    console.log("QUERY COMPLEXITY TEST PASSED");
}

main().catch(error => {
    console.error("Fatal execution error:", error.message);
    process.exitCode = 1;
});
