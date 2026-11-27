"use strict";

/*
 * GraphQL Fundamentals
 * Node.js implementation of schemas, types, queries,
 * mutations, asynchronous resolvers, and execution policies.
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const { randomUUID } = require("node:crypto");
const { performance } = require("node:perf_hooks");

// ---------------------------------------------------------
// 1. GraphQL type definitions
// ---------------------------------------------------------

const Scalar = Object.freeze({
    STRING: "String",
    INT: "Int",
    FLOAT: "Float",
    BOOLEAN: "Boolean",
    ID: "ID"
});

class NonNullType {
    constructor(inner) {
        this.inner = inner;
    }
}

class ListType {
    constructor(inner) {
        this.inner = inner;
    }
}

class ObjectType {
    constructor(name, fields = {}) {
        this.name = name;
        this.fields = new Map(Object.entries(fields));
    }

    addField(name, definition) {
        if (this.fields.has(name)) {
            throw new Error(`Duplicate field: ${name}`);
        }

        this.fields.set(name, definition);
    }
}

class FieldDefinition {
    constructor({
        type,
        resolver = null,
        arguments: args = {},
        description = ""
    }) {
        this.type = type;
        this.resolver = resolver;
        this.arguments = new Map(Object.entries(args));
        this.description = description;
    }
}

class GraphQLError extends Error {
    constructor(message, path = []) {
        super(message);
        this.name = "GraphQLError";
        this.path = path;
    }
}

// ---------------------------------------------------------
// 2. Scalar validation
// ---------------------------------------------------------

function validateValue(value, expected, path = "value") {
    if (expected instanceof NonNullType) {
        if (value === null || value === undefined) {
            throw new GraphQLError(`${path} cannot be null`);
        }

        return validateValue(value, expected.inner, path);
    }

    if (value === null || value === undefined) {
        return;
    }

    if (expected instanceof ListType) {
        if (!Array.isArray(value)) {
            throw new GraphQLError(`${path} must be an array`);
        }

        value.forEach((item, index) =>
            validateValue(item, expected.inner, `${path}[${index}]`)
        );

        return;
    }

    if (expected instanceof ObjectType) {
        if (typeof value !== "object" || Array.isArray(value)) {
            throw new GraphQLError(`${path} must be an object`);
        }

        return;
    }

    const validators = {
        [Scalar.STRING]: value => typeof value === "string",
        [Scalar.INT]: value =>
            Number.isInteger(value) &&
            value >= -2147483648 &&
            value <= 2147483647,
        [Scalar.FLOAT]: value =>
            typeof value === "number" && Number.isFinite(value),
        [Scalar.BOOLEAN]: value => typeof value === "boolean",
        [Scalar.ID]: value =>
            typeof value === "string" ||
            Number.isSafeInteger(value)
    };

    if (!validators[expected]) {
        throw new GraphQLError(`Unknown scalar: ${expected}`);
    }

    if (!validators[expected](value)) {
        throw new GraphQLError(`${path} must be ${expected}`);
    }
}

// ---------------------------------------------------------
// 3. Schema registry
// ---------------------------------------------------------

class GraphQLSchema {
    constructor(query, mutation, types = []) {
        this.query = query;
        this.mutation = mutation;
        this.types = new Map();

        for (const type of types) {
            if (this.types.has(type.name)) {
                throw new GraphQLError(
                    `Duplicate type: ${type.name}`
                );
            }

            this.types.set(type.name, type);
        }

        this.validate();
    }

    validate() {
        if (!(this.query instanceof ObjectType)) {
            throw new GraphQLError("A Query root is required");
        }

        for (const type of this.types.values()) {
            for (const [fieldName, definition] of type.fields) {
                if (!fieldName || !(definition instanceof FieldDefinition)) {
                    throw new GraphQLError("Invalid field definition");
                }
            }
        }
    }
}

// ---------------------------------------------------------
// 4. Repository domain and asynchronous storage
// ---------------------------------------------------------

class InventoryStore {
    constructor() {
        this.users = new Map([
            ["1", {
                id: "1",
                name: "Aarav Sharma",
                email: "aarav@example.com"
            }],
            ["2", {
                id: "2",
                name: "Meera Singh",
                email: "meera@example.com"
            }]
        ]);

        this.products = new Map([
            ["101", {
                id: "101",
                name: "Laptop",
                price: 75000,
                stock: 8
            }],
            ["102", {
                id: "102",
                name: "Keyboard",
                price: 2500,
                stock: 20
            }]
        ]);

        this.orders = new Map();
        this.nextId = 1;
    }

    async getProduct(id) {
        return this.products.get(String(id)) ?? null;
    }

    async getUser(id) {
        return this.users.get(String(id)) ?? null;
    }

    async getProducts() {
        return Array.from(this.products.values());
    }

    async createOrder(input) {
        const { userId, productId, quantity } = input;

        const user = await this.getUser(userId);
        const product = await this.getProduct(productId);

        if (!user) {
            throw new GraphQLError("User does not exist");
        }

        if (!product) {
            throw new GraphQLError("Product does not exist");
        }

        if (!Number.isInteger(quantity) || quantity <= 0) {
            throw new GraphQLError("Invalid quantity");
        }

        // JavaScript executes this synchronous critical section
        // without interleaving another event-loop callback.
        if (product.stock < quantity) {
            throw new GraphQLError("Insufficient inventory");
        }

        product.stock -= quantity;

        const order = Object.freeze({
            id: String(this.nextId++),
            userId: user.id,
            productId: product.id,
            quantity,
            status: "CONFIRMED",
            createdAt: new Date().toISOString()
        });

        this.orders.set(order.id, order);

        return order;
    }
}

// ---------------------------------------------------------
// 5. Resolver context
// ---------------------------------------------------------

class RequestContext {
    constructor({
        userId = null,
        roles = [],
        requestId = randomUUID()
    } = {}) {
        this.userId = userId;
        this.roles = new Set(roles);
        this.requestId = requestId;
    }

    hasRole(role) {
        return this.roles.has(role);
    }
}

// ---------------------------------------------------------
// 6. GraphQL executor
// ---------------------------------------------------------

class GraphQLExecutor {
    constructor(schema, context, options = {}) {
        this.schema = schema;
        this.context = context;
        this.maxDepth = options.maxDepth ?? 5;
        this.maxFields = options.maxFields ?? 30;
    }

    async execute(operation, selection) {
        const started = performance.now();
        let fieldCount = 0;

        const root = operation === "query"
            ? this.schema.query
            : operation === "mutation"
                ? this.schema.mutation
                : null;

        if (!root) {
            return {
                data: null,
                errors: [{
                    message: "Unsupported operation"
                }]
            };
        }

        try {
            if (
                !selection ||
                typeof selection !== "object" ||
                Array.isArray(selection)
            ) {
                throw new GraphQLError("Invalid selection");
            }

            const data = await this.executeSelection(
                null,
                root,
                selection,
                0,
                () => ++fieldCount
            );

            return {
                data,
                errors: [],
                extensions: {
                    requestId: this.context.requestId,
                    fieldsExecuted: fieldCount,
                    durationMs: Number(
                        (performance.now() - started).toFixed(3)
                    )
                }
            };
        } catch (error) {
            return {
                data: null,
                errors: [{
                    message: error.message,
                    path: error.path ?? []
                }]
            };
        }
    }

    async executeSelection(
        source,
        objectType,
        selection,
        depth,
        increment
    ) {
        if (depth > this.maxDepth) {
            throw new GraphQLError("Maximum query depth exceeded");
        }

        const output = {};

        for (const [fieldName, request] of Object.entries(selection)) {
            if (increment() > this.maxFields) {
                throw new GraphQLError("Maximum field count exceeded");
            }

            const definition = objectType.fields.get(fieldName);

            if (!definition) {
                throw new GraphQLError(
                    `Unknown field: ${objectType.name}.${fieldName}`,
                    [fieldName]
                );
            }

            const args = request?.args ?? {};
            const nested = request?.select ?? null;

            if (
                !args ||
                typeof args !== "object" ||
                Array.isArray(args)
            ) {
                throw new GraphQLError("Arguments must be an object");
            }

            for (const key of Object.keys(args)) {
                if (!definition.arguments.has(key)) {
                    throw new GraphQLError(
                        `Unknown argument: ${key}`
                    );
                }
            }

            for (const [key, expected] of definition.arguments) {
                if (!Object.hasOwn(args, key)) {
                    validateValue(undefined, expected, key);
                } else {
                    validateValue(args[key], expected, key);
                }
            }

            try {
                const value = definition.resolver
                    ? await definition.resolver(source, args, this.context)
                    : source?.[fieldName] ?? null;

                output[fieldName] = await this.completeValue(
                    value,
                    definition.type,
                    nested,
                    depth,
                    increment
                );
            } catch (error) {
                throw new GraphQLError(
                    `Resolver error in ${fieldName}: ${error.message}`,
                    [fieldName]
                );
            }
        }

        return output;
    }

    async completeValue(value, type, selection, depth, increment) {
        if (type instanceof NonNullType) {
            if (value === null || value === undefined) {
                throw new GraphQLError("Non-null field returned null");
            }

            return this.completeValue(
                value,
                type.inner,
                selection,
                depth,
                increment
            );
        }

        if (value === null || value === undefined) {
            return null;
        }

        if (type instanceof ListType) {
            if (!Array.isArray(value)) {
                throw new GraphQLError("Expected list result");
            }

            return Promise.all(
                value.map(item =>
                    this.completeValue(
                        item,
                        type.inner,
                        selection,
                        depth + 1,
                        increment
                    )
                )
            );
        }

        if (type instanceof ObjectType) {
            if (!selection) {
                throw new GraphQLError(
                    `${type.name} requires a selection set`
                );
            }

            return this.executeSelection(
                value,
                type,
                selection,
                depth + 1,
                increment
            );
        }

        if (selection) {
            throw new GraphQLError(
                "Scalar fields cannot contain selections"
            );
        }

        validateValue(value, type);
        return value;
    }
}

// ---------------------------------------------------------
// 7. Application schema and resolver registration
// ---------------------------------------------------------

function createApplication() {
    const store = new InventoryStore();

    const User = new ObjectType("User", {
        id: new FieldDefinition({ type: Scalar.ID }),
        name: new FieldDefinition({ type: Scalar.STRING }),
        email: new FieldDefinition({ type: Scalar.STRING })
    });

    const Product = new ObjectType("Product", {
        id: new FieldDefinition({ type: Scalar.ID }),
        name: new FieldDefinition({ type: Scalar.STRING }),
        price: new FieldDefinition({ type: Scalar.FLOAT }),
        stock: new FieldDefinition({ type: Scalar.INT })
    });

    const Order = new ObjectType("Order", {
        id: new FieldDefinition({ type: Scalar.ID }),
        quantity: new FieldDefinition({ type: Scalar.INT }),
        status: new FieldDefinition({ type: Scalar.STRING }),

        user: new FieldDefinition({
            type: User,
            resolver: order => store.getUser(order.userId)
        }),

        product: new FieldDefinition({
            type: Product,
            resolver: order => store.getProduct(order.productId)
        })
    });

    const Query = new ObjectType("Query", {
        products: new FieldDefinition({
            type: new ListType(Product),
            resolver: () => store.getProducts()
        }),

        product: new FieldDefinition({
            type: Product,
            arguments: {
                id: new NonNullType(Scalar.ID)
            },
            resolver: (_, args) => store.getProduct(args.id)
        }),

        user: new FieldDefinition({
            type: User,
            arguments: {
                id: new NonNullType(Scalar.ID)
            },
            resolver: (_, args) => store.getUser(args.id)
        }),

        orders: new FieldDefinition({
            type: new ListType(Order),
            resolver: async () => Array.from(store.orders.values())
        })
    });

    const Mutation = new ObjectType("Mutation", {
        createOrder: new FieldDefinition({
            type: Order,

            arguments: {
                userId: new NonNullType(Scalar.ID),
                productId: new NonNullType(Scalar.ID),
                quantity: new NonNullType(Scalar.INT)
            },

            resolver: async (_, args, context) => {
                if (!context.userId) {
                    throw new GraphQLError("Authentication required");
                }

                if (!context.hasRole("CUSTOMER")) {
                    throw new GraphQLError("Customer role required");
                }

                if (context.userId !== String(args.userId)) {
                    throw new GraphQLError("Cannot order for another user");
                }

                return store.createOrder(args);
            }
        })
    });

    const schema = new GraphQLSchema(
        Query,
        Mutation,
        [User, Product, Order]
    );

    return { schema, store };
}

// ---------------------------------------------------------
// 8. Event-driven request processing
// ---------------------------------------------------------

class GraphQLGateway {
    constructor(executor) {
        this.executor = executor;
        this.listeners = new Map();
    }

    on(event, listener) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }

        this.listeners.get(event).add(listener);
    }

    emit(event, payload) {
        for (const listener of this.listeners.get(event) ?? []) {
            listener(payload);
        }
    }

    async handle(operation, selection) {
        const requestId = this.executor.context.requestId;

        this.emit("request:start", {
            requestId,
            operation
        });

        const result = await this.executor.execute(
            operation,
            selection
        );

        this.emit("request:complete", {
            requestId,
            success: result.errors.length === 0,
            result
        });

        return result;
    }
}

// ---------------------------------------------------------
// 9. Demonstration and tests
// ---------------------------------------------------------

async function main() {
    const { schema, store } = createApplication();

    const context = new RequestContext({
        userId: "1",
        roles: ["CUSTOMER"]
    });

    const executor = new GraphQLExecutor(schema, context, {
        maxDepth: 5,
        maxFields: 30
    });

    const gateway = new GraphQLGateway(executor);

    gateway.on("request:start", event => {
        console.log(
            `\nREQUEST START: ${event.operation} ${event.requestId}`
        );
    });

    gateway.on("request:complete", event => {
        console.log(
            `REQUEST COMPLETE: success=${event.success}`
        );
    });

    console.log("\n1. QUERY PRODUCTS");

    const query = await gateway.handle("query", {
        products: {
            select: {
                id: null,
                name: null,
                price: null,
                stock: null
            }
        }
    });

    console.log(JSON.stringify(query, null, 2));
    console.assert(query.errors.length === 0);
    console.assert(query.data.products.length === 2);

    console.log("\n2. QUERY ONE USER");

    const userResult = await gateway.handle("query", {
        user: {
            args: { id: "1" },
            select: {
                name: null,
                email: null
            }
        }
    });

    console.log(JSON.stringify(userResult, null, 2));

    console.log("\n3. MUTATION CREATE ORDER");

    const mutation = await gateway.handle("mutation", {
        createOrder: {
            args: {
                userId: "1",
                productId: "101",
                quantity: 2
            },
            select: {
                id: null,
                status: null,
                user: {
                    select: {
                        name: null
                    }
                },
                product: {
                    select: {
                        name: null,
                        stock: null
                    }
                }
            }
        }
    });

    console.log(JSON.stringify(mutation, null, 2));

    console.assert(mutation.errors.length === 0);
    console.assert(store.products.get("101").stock === 6);

    console.log("\n4. MUTATION VALIDATION FAILURE");

    const invalid = await gateway.handle("mutation", {
        createOrder: {
            args: {
                userId: "1",
                productId: "101",
                quantity: -3
            },
            select: {
                id: null
            }
        }
    });

    console.log(JSON.stringify(invalid, null, 2));
    console.assert(invalid.errors.length > 0);

    console.log("\n5. UNKNOWN FIELD FAILURE");

    const unknown = await gateway.handle("query", {
        invalidField: null
    });

    console.log(JSON.stringify(unknown, null, 2));
    console.assert(unknown.errors.length > 0);

    console.log("\n6. AUTHORIZATION FAILURE");

    const anonymous = new GraphQLExecutor(
        schema,
        new RequestContext()
    );

    const unauthorized = await anonymous.execute("mutation", {
        createOrder: {
            args: {
                userId: "1",
                productId: "102",
                quantity: 1
            },
            select: {
                id: null
            }
        }
    });

    console.log(JSON.stringify(unauthorized, null, 2));
    console.assert(unauthorized.errors.length > 0);

    console.log("\n7. OWNERSHIP FAILURE");

    const anotherUser = new GraphQLExecutor(
        schema,
        new RequestContext({
            userId: "2",
            roles: ["CUSTOMER"]
        })
    );

    const ownershipFailure = await anotherUser.execute(
        "mutation",
        {
            createOrder: {
                args: {
                    userId: "1",
                    productId: "102",
                    quantity: 1
                },
                select: {
                    id: null
                }
            }
        }
    );

    console.log(JSON.stringify(ownershipFailure, null, 2));
    console.assert(ownershipFailure.errors.length > 0);

    console.log("\nAll JavaScript tests completed.");
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
