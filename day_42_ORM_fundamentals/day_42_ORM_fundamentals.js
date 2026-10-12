"use strict";

/*
 * ORM Fundamentals in JavaScript
 *
 * This implementation models a small ORM layer using Node.js standard
 * JavaScript features. It focuses on identity maps, model metadata,
 * relationships, lifecycle events, dirty tracking, validation, and
 * query-to-object mapping without requiring an external ORM package.
 *
 * The persistence adapter is intentionally in-memory. Its purpose is to show
 * how an ORM converts relational-style records into domain objects and back.
 */

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

class PersistenceError extends Error {
    constructor(message) {
        super(message);
        this.name = "PersistenceError";
    }
}

class EventBus {
    constructor() {
        this.listeners = new Map();
    }

    on(eventName, listener) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }
        this.listeners.get(eventName).push(listener);
    }

    emit(eventName, payload) {
        for (const listener of this.listeners.get(eventName) ?? []) {
            listener(payload);
        }
    }
}

class InMemoryStore {
    constructor() {
        this.tables = new Map();
        this.sequences = new Map();
    }

    createTable(name) {
        this.tables.set(name, new Map());
        this.sequences.set(name, 0);
    }

    insert(tableName, row) {
        const table = this.tables.get(tableName);
        if (!table) {
            throw new PersistenceError(`Unknown table: ${tableName}`);
        }

        const id = ++this.sequences.get(tableName);
        const storedRow = { ...row, id };
        table.set(id, storedRow);
        return { ...storedRow };
    }

    update(tableName, id, changes) {
        const table = this.tables.get(tableName);
        const existing = table?.get(id);

        if (!existing) {
            throw new PersistenceError(
                `Cannot update missing ${tableName}#${id}`
            );
        }

        const updated = { ...existing, ...changes, id };
        table.set(id, updated);
        return { ...updated };
    }

    findById(tableName, id) {
        const row = this.tables.get(tableName)?.get(id);
        return row ? { ...row } : null;
    }

    find(tableName, predicate = () => true) {
        const table = this.tables.get(tableName);
        if (!table) {
            throw new PersistenceError(`Unknown table: ${tableName}`);
        }

        return [...table.values()]
            .filter(predicate)
            .map(row => ({ ...row }));
    }
}

const ORM_METADATA = {
    User: {
        table: "users",
        columns: ["name", "email"]
    },
    Order: {
        table: "orders",
        columns: ["userId", "status", "createdAt"]
    },
    Product: {
        table: "products",
        columns: ["name", "price"]
    },
    OrderItem: {
        table: "orderItems",
        columns: ["orderId", "productId", "quantity", "unitPrice"]
    }
};

class Model {
    constructor(data = {}) {
        this.id = data.id ?? null;
        this._original = { ...data };
        Object.assign(this, data);
    }

    get metadata() {
        return ORM_METADATA[this.constructor.name];
    }

    validate() {
        throw new Error("Model validation must be implemented by subclasses");
    }

    dirtyFields() {
        const dirty = {};

        for (const field of this.metadata.columns) {
            if (this[field] !== this._original[field]) {
                dirty[field] = this[field];
            }
        }

        return dirty;
    }

    markClean() {
        this._original = this.toRecord();
    }

    toRecord() {
        const record = {};

        for (const field of this.metadata.columns) {
            record[field] = this[field];
        }

        return record;
    }
}

class User extends Model {
    constructor(data = {}) {
        super(data);
        this.name = data.name ?? "";
        this.email = data.email ?? "";
    }

    validate() {
        if (!this.name.trim()) {
            throw new ValidationError("User name is required");
        }

        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.email)) {
            throw new ValidationError("User email is invalid");
        }
    }
}

class Product extends Model {
    constructor(data = {}) {
        super(data);
        this.name = data.name ?? "";
        this.price = Number(data.price ?? 0);
    }

    validate() {
        if (!this.name.trim()) {
            throw new ValidationError("Product name is required");
        }

        if (!Number.isFinite(this.price) || this.price < 0) {
            throw new ValidationError("Product price must be non-negative");
        }
    }
}

class OrderItem extends Model {
    constructor(data = {}) {
        super(data);
        this.orderId = data.orderId ?? null;
        this.productId = data.productId ?? null;
        this.quantity = Number(data.quantity ?? 0);
        this.unitPrice = Number(data.unitPrice ?? 0);
    }

    validate() {
        if (!Number.isInteger(this.quantity) || this.quantity <= 0) {
            throw new ValidationError("Order quantity must be a positive integer");
        }

        if (!Number.isFinite(this.unitPrice) || this.unitPrice < 0) {
            throw new ValidationError("Unit price cannot be negative");
        }
    }
}

class Order extends Model {
    constructor(data = {}) {
        super(data);
        this.userId = data.userId ?? null;
        this.status = data.status ?? "PENDING";
        this.createdAt = data.createdAt ?? new Date().toISOString();
        this.items = data.items ?? [];
    }

    validate() {
        const allowed = new Set([
            "PENDING",
            "PAID",
            "SHIPPED",
            "CANCELLED"
        ]);

        if (!allowed.has(this.status)) {
            throw new ValidationError(`Invalid order status: ${this.status}`);
        }

        if (!Number.isInteger(this.userId) || this.userId <= 0) {
            throw new ValidationError("A valid userId is required");
        }

        for (const item of this.items) {
            item.validate();
        }
    }

    total() {
        return this.items.reduce(
            (sum, item) => sum + item.quantity * item.unitPrice,
            0
        );
    }
}

class Session {
    constructor(store, events) {
        this.store = store;
        this.events = events;
        this.identityMap = new Map();
        this.pending = [];
    }

    key(ModelClass, id) {
        return `${ModelClass.name}:${id}`;
    }

    add(model) {
        model.validate();
        this.pending.push(model);
        this.events.emit("entity.pending", {
            type: model.constructor.name
        });
    }

    save(model) {
        model.validate();

        const metadata = model.metadata;
        const record = model.toRecord();

        if (model.id === null) {
            const inserted = this.store.insert(metadata.table, record);
            model.id = inserted.id;
            this.identityMap.set(
                this.key(model.constructor, model.id),
                model
            );

            this.events.emit("entity.inserted", {
                type: model.constructor.name,
                id: model.id
            });
        } else {
            const changes = model.dirtyFields();

            if (Object.keys(changes).length > 0) {
                this.store.update(metadata.table, model.id, changes);
                this.events.emit("entity.updated", {
                    type: model.constructor.name,
                    id: model.id,
                    changes
                });
            }
        }

        model.markClean();
        return model;
    }

    commit() {
        try {
            for (const model of this.pending) {
                this.save(model);

                if (model instanceof Order) {
                    for (const item of model.items) {
                        item.orderId = model.id;
                        this.save(item);
                    }
                }
            }

            this.pending.length = 0;
            this.events.emit("transaction.committed", {});
        } catch (error) {
            this.pending.length = 0;
            this.events.emit("transaction.failed", {
                message: error.message
            });
            throw error;
        }
    }

    get(ModelClass, id) {
        const key = this.key(ModelClass, id);

        if (this.identityMap.has(key)) {
            return this.identityMap.get(key);
        }

        const metadata = ORM_METADATA[ModelClass.name];
        const record = this.store.findById(metadata.table, id);

        if (!record) {
            return null;
        }

        const model = new ModelClass(record);
        model.markClean();
        this.identityMap.set(key, model);
        return model;
    }

    query(ModelClass, predicate) {
        const metadata = ORM_METADATA[ModelClass.name];

        return this.store
            .find(metadata.table, predicate)
            .map(record => {
                const existing = this.get(ModelClass, record.id);

                if (existing) {
                    return existing;
                }

                const model = new ModelClass(record);
                model.markClean();
                this.identityMap.set(
                    this.key(ModelClass, model.id),
                    model
                );
                return model;
            });
    }
}

function createDatabase() {
    const store = new InMemoryStore();

    for (const table of [
        "users",
        "products",
        "orders",
        "orderItems"
    ]) {
        store.createTable(table);
    }

    return store;
}

function attachDiagnostics(events) {
    events.on("entity.pending", event => {
        console.log(`Pending entity: ${event.type}`);
    });

    events.on("entity.inserted", event => {
        console.log(`Inserted ${event.type}#${event.id}`);
    });

    events.on("entity.updated", event => {
        console.log(
            `Updated ${event.type}#${event.id}:`,
            event.changes
        );
    });

    events.on("transaction.committed", () => {
        console.log("Transaction committed");
    });

    events.on("transaction.failed", event => {
        console.log(`Transaction failed: ${event.message}`);
    });
}

function loadOrderGraph(session, orderId) {
    const order = session.get(Order, orderId);

    if (!order) {
        return null;
    }

    order.items = session.query(
        OrderItem,
        item => item.orderId === order.id
    );

    for (const item of order.items) {
        item.product = session.get(Product, item.productId);
    }

    order.user = session.get(User, order.userId);

    return order;
}

function demonstrateRelationshipMapping(session) {
    const user = new User({
        name: "Atul Pandey",
        email: "atul@example.com"
    });

    session.add(user);

    const product = new Product({
        name: "Engineering Laptop",
        price: 85000
    });

    session.add(product);
    session.commit();

    const order = new Order({
        userId: user.id,
        status: "PENDING"
    });

    order.items.push(
        new OrderItem({
            productId: product.id,
            quantity: 1,
            unitPrice: product.price
        })
    );

    session.add(order);
    session.commit();

    return {
        user,
        product,
        order
    };
}

function demonstrateDirtyTracking(session, productId) {
    const product = session.get(Product, productId);

    console.log("\nDirty tracking before change:", product.dirtyFields());

    product.price = 82000;

    console.log("Dirty tracking after change:", product.dirtyFields());

    session.save(product);

    console.log("Dirty tracking after save:", product.dirtyFields());
}

function demonstrateIdentityMap(session, userId) {
    const first = session.get(User, userId);
    const second = session.get(User, userId);

    console.log("\nIdentity map:");
    console.log("Same object instance:", first === second);
}

function demonstrateValidation(session) {
    console.log("\nValidation:");

    try {
        session.add(
            new Product({
                name: "Invalid Product",
                price: -100
            })
        );
        session.commit();
    } catch (error) {
        console.log(`${error.name}: ${error.message}`);
    }
}

function main() {
    console.log("ORM Fundamentals: JavaScript object-relational mapping");

    const store = createDatabase();
    const events = new EventBus();
    attachDiagnostics(events);

    const session = new Session(store, events);
    const { user, product, order } =
        demonstrateRelationshipMapping(session);

    demonstrateIdentityMap(session, user.id);
    demonstrateDirtyTracking(session, product.id);
    demonstrateValidation(session);

    const loadedOrder = loadOrderGraph(session, order.id);

    console.log("\nObject graph reconstructed from relational-style records:");
    console.log(
        JSON.stringify(
            {
                orderId: loadedOrder.id,
                customer: loadedOrder.user.name,
                product: loadedOrder.items[0].product.name,
                total: loadedOrder.total()
            },
            null,
            2
        )
    );

    console.log("\nORM-specific tradeoff:");
    console.log(
        "Object navigation is convenient for domain operations, but the ORM " +
        "must still manage identity, relationship loading, persistence state, " +
        "validation, and the translation between records and objects."
    );
}

main();
