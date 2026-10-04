/*
 * Database Constraints: PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK, DEFAULT
 *
 * This Node.js file implements a constraint-aware relational workflow without
 * requiring an external npm package. It uses an in-memory relational model to
 * make the behavior explicit while preserving database-style enforcement rules.
 *
 * The implementation focuses on JavaScript-specific behavior:
 * - classes and Maps for indexed relational state
 * - event-driven lifecycle notifications
 * - validation before state mutation
 * - transaction snapshots and rollback
 * - asynchronous workflow through async functions
 */

"use strict";

const EventEmitter = require("node:events");

class ConstraintError extends Error {
    constructor(message, constraintType) {
        super(message);
        this.name = "ConstraintError";
        this.constraintType = constraintType;
    }
}

class RepositoryEventBus extends EventEmitter {}

class ConstraintDatabase {
    constructor() {
        this.customers = new Map();
        this.products = new Map();
        this.orders = new Map();
        this.orderItems = new Map();

        this.customerIdSequence = 1;
        this.productIdSequence = 1;
        this.orderIdSequence = 1;

        this.events = new RepositoryEventBus();

        // UNIQUE constraints require an index separate from the row storage.
        this.customerEmailIndex = new Map();
        this.productSkuIndex = new Map();
    }

    emit(eventName, payload) {
        this.events.emit(eventName, Object.freeze({ ...payload }));
    }

    allocateId(sequenceName) {
        const id = this[sequenceName];
        this[sequenceName] += 1;
        return id;
    }

    createCustomer({ email, fullName, age, status = "active" }) {
        // NOT NULL constraints reject null and undefined values.
        if (email === null || email === undefined) {
            throw new ConstraintError(
                "customers.email cannot be NULL",
                "NOT NULL"
            );
        }

        if (fullName === null || fullName === undefined) {
            throw new ConstraintError(
                "customers.fullName cannot be NULL",
                "NOT NULL"
            );
        }

        // UNIQUE is enforced using an explicit lookup index.
        if (this.customerEmailIndex.has(email)) {
            throw new ConstraintError(
                `Customer email already exists: ${email}`,
                "UNIQUE"
            );
        }

        // CHECK constraints encode domain rules at the data boundary.
        if (!Number.isInteger(age) || age < 18) {
            throw new ConstraintError(
                "customers.age must be an integer greater than or equal to 18",
                "CHECK"
            );
        }

        if (!["active", "suspended"].includes(status)) {
            throw new ConstraintError(
                "customers.status must be active or suspended",
                "CHECK"
            );
        }

        const customerId = this.allocateId("customerIdSequence");

        const customer = Object.freeze({
            customerId,
            email,
            fullName,
            age,
            status
        });

        this.customers.set(customerId, customer);
        this.customerEmailIndex.set(email, customerId);

        this.emit("customer.created", {
            customerId,
            email
        });

        return customerId;
    }

    createProduct({ sku, name, price, stock = 0 }) {
        if (!sku || !name) {
            throw new ConstraintError(
                "products.sku and products.name are required",
                "NOT NULL"
            );
        }

        if (this.productSkuIndex.has(sku)) {
            throw new ConstraintError(
                `Product SKU already exists: ${sku}`,
                "UNIQUE"
            );
        }

        if (!Number.isFinite(price) || price <= 0) {
            throw new ConstraintError(
                "products.price must be greater than zero",
                "CHECK"
            );
        }

        if (!Number.isInteger(stock) || stock < 0) {
            throw new ConstraintError(
                "products.stock must be a non-negative integer",
                "CHECK"
            );
        }

        const productId = this.allocateId("productIdSequence");

        const product = Object.freeze({
            productId,
            sku,
            name,
            price,
            stock
        });

        this.products.set(productId, product);
        this.productSkuIndex.set(sku, productId);

        return productId;
    }

    findCustomerByEmail(email) {
        const customerId = this.customerEmailIndex.get(email);

        if (customerId === undefined) {
            throw new ConstraintError(
                `Referenced customer does not exist: ${email}`,
                "FOREIGN KEY"
            );
        }

        return this.customers.get(customerId);
    }

    findProductBySku(sku) {
        const productId = this.productSkuIndex.get(sku);

        if (productId === undefined) {
            throw new ConstraintError(
                `Referenced product does not exist: ${sku}`,
                "FOREIGN KEY"
            );
        }

        return this.products.get(productId);
    }

    updateProductStock(productId, newStock) {
        if (!Number.isInteger(newStock) || newStock < 0) {
            throw new ConstraintError(
                "products.stock must satisfy CHECK(stock >= 0)",
                "CHECK"
            );
        }

        const oldProduct = this.products.get(productId);

        if (!oldProduct) {
            throw new ConstraintError(
                `Product ${productId} does not exist`,
                "FOREIGN KEY"
            );
        }

        const updatedProduct = Object.freeze({
            ...oldProduct,
            stock: newStock
        });

        this.products.set(productId, updatedProduct);
    }

    makeOrderItemKey(orderId, productId) {
        // This models a composite PRIMARY KEY(order_id, product_id).
        return `${orderId}:${productId}`;
    }

    createOrder(customerEmail, requestedItems) {
        const customer = this.findCustomerByEmail(customerEmail);

        if (!Array.isArray(requestedItems) || requestedItems.length === 0) {
            throw new ConstraintError(
                "An order requires at least one item",
                "CHECK"
            );
        }

        const orderId = this.allocateId("orderIdSequence");

        const order = Object.freeze({
            orderId,
            customerId: customer.customerId,
            status: "pending", // DEFAULT
            createdAt: new Date().toISOString()
        });

        const stagedItems = [];
        const stagedProducts = new Map();

        /*
         * Stage every change before committing it. This gives the JavaScript
         * model transaction-like behavior: a failed constraint does not leave
         * half an order in the in-memory database.
         */
        for (const requestedItem of requestedItems) {
            const { sku, quantity } = requestedItem;

            if (!Number.isInteger(quantity) || quantity <= 0) {
                throw new ConstraintError(
                    "order_items.quantity must satisfy CHECK(quantity > 0)",
                    "CHECK"
                );
            }

            const product = this.findProductBySku(sku);
            const currentStock =
                stagedProducts.get(product.productId) ?? product.stock;

            if (currentStock < quantity) {
                throw new ConstraintError(
                    `Insufficient stock for ${sku}: requested ${quantity}, available ${currentStock}`,
                    "CHECK"
                );
            }

            const key = this.makeOrderItemKey(orderId, product.productId);

            // Composite PRIMARY KEY uniqueness.
            if (this.orderItems.has(key) || stagedItems.some(item => item.key === key)) {
                throw new ConstraintError(
                    `Duplicate order/product pair: ${key}`,
                    "PRIMARY KEY"
                );
            }

            stagedItems.push({
                key,
                orderId,
                productId: product.productId,
                quantity,
                unitPrice: product.price
            });

            stagedProducts.set(
                product.productId,
                currentStock - quantity
            );
        }

        // Commit only after all constraints have passed.
        this.orders.set(orderId, order);

        for (const item of stagedItems) {
            this.orderItems.set(item.key, Object.freeze(item));
        }

        for (const [productId, newStock] of stagedProducts) {
            this.updateProductStock(productId, newStock);
        }

        this.emit("order.created", {
            orderId,
            customerId: customer.customerId,
            itemCount: stagedItems.length
        });

        return orderId;
    }

    deleteProduct(productId) {
        // ON DELETE RESTRICT behavior: referenced products cannot be removed.
        for (const item of this.orderItems.values()) {
            if (item.productId === productId) {
                throw new ConstraintError(
                    `Product ${productId} is referenced by order ${item.orderId}`,
                    "FOREIGN KEY"
                );
            }
        }

        const product = this.products.get(productId);

        if (!product) {
            return false;
        }

        this.products.delete(productId);
        this.productSkuIndex.delete(product.sku);
        return true;
    }

    snapshot() {
        return {
            customers: structuredClone([...this.customers]),
            products: structuredClone([...this.products]),
            orders: structuredClone([...this.orders]),
            orderItems: structuredClone([...this.orderItems]),
            customerIdSequence: this.customerIdSequence,
            productIdSequence: this.productIdSequence,
            orderIdSequence: this.orderIdSequence
        };
    }

    restore(snapshot) {
        this.customers = new Map(snapshot.customers);
        this.products = new Map(snapshot.products);
        this.orders = new Map(snapshot.orders);
        this.orderItems = new Map(snapshot.orderItems);

        this.customerIdSequence = snapshot.customerIdSequence;
        this.productIdSequence = snapshot.productIdSequence;
        this.orderIdSequence = snapshot.orderIdSequence;

        this.customerEmailIndex = new Map(
            [...this.customers.values()].map(customer => [
                customer.email,
                customer.customerId
            ])
        );

        this.productSkuIndex = new Map(
            [...this.products.values()].map(product => [
                product.sku,
                product.productId
            ])
        );
    }

    transaction(operation) {
        const before = this.snapshot();

        try {
            return operation();
        } catch (error) {
            this.restore(before);
            throw error;
        }
    }

    describeConstraintModel() {
        return {
            customers: {
                primaryKey: "customerId",
                unique: ["email"],
                notNull: ["email", "fullName", "age", "status"],
                check: [
                    "age >= 18",
                    "status IN ('active', 'suspended')"
                ],
                defaults: {
                    status: "active"
                }
            },
            products: {
                primaryKey: "productId",
                unique: ["sku"],
                notNull: ["sku", "name", "price", "stock"],
                check: [
                    "price > 0",
                    "stock >= 0"
                ],
                defaults: {
                    stock: 0
                }
            },
            orders: {
                primaryKey: "orderId",
                foreignKeys: ["customerId -> customers.customerId"],
                defaults: {
                    status: "pending",
                    createdAt: "current timestamp"
                }
            },
            orderItems: {
                compositePrimaryKey: ["orderId", "productId"],
                foreignKeys: [
                    "orderId -> orders.orderId",
                    "productId -> products.productId"
                ],
                check: ["quantity > 0", "unitPrice > 0"]
            }
        };
    }
}

async function main() {
    const database = new ConstraintDatabase();

    database.events.on("customer.created", event => {
        console.log(
            `[event] customer.created customerId=${event.customerId} email=${event.email}`
        );
    });

    database.events.on("order.created", event => {
        console.log(
            `[event] order.created orderId=${event.orderId} items=${event.itemCount}`
        );
    });

    console.log("=== DATABASE CONSTRAINT MODEL ===");
    console.dir(database.describeConstraintModel(), { depth: null });

    console.log("\n=== DEFAULT AND VALID INSERTS ===");

    const aliceId = database.createCustomer({
        email: "alice@example.com",
        fullName: "Alice Rao",
        age: 29
        // status omitted: DEFAULT 'active'
    });

    const laptopId = database.createProduct({
        sku: "LT-100",
        name: "Developer Laptop",
        price: 1299,
        stock: 5
    });

    const monitorId = database.createProduct({
        sku: "MN-200",
        name: "4K Monitor",
        price: 349,
        stock: 10
    });

    console.log(`Alice customerId=${aliceId}`);
    console.log(`Laptop productId=${laptopId}`);
    console.log(`Monitor productId=${monitorId}`);

    console.log("\n=== CONSTRAINT FAILURES ===");

    const attempts = [
        {
            name: "duplicate UNIQUE email",
            operation: () =>
                database.createCustomer({
                    email: "alice@example.com",
                    fullName: "Duplicate Alice",
                    age: 32
                })
        },
        {
            name: "CHECK age",
            operation: () =>
                database.createCustomer({
                    email: "minor@example.com",
                    fullName: "Invalid Customer",
                    age: 16
                })
        },
        {
            name: "CHECK product price",
            operation: () =>
                database.createProduct({
                    sku: "BAD-PRICE",
                    name: "Invalid Product",
                    price: 0,
                    stock: 1
                })
        },
        {
            name: "NOT NULL email",
            operation: () =>
                database.createCustomer({
                    email: null,
                    fullName: "Missing Email",
                    age: 30
                })
        },
        {
            name: "FOREIGN KEY customer",
            operation: () =>
                database.createOrder("missing@example.com", [
                    { sku: "LT-100", quantity: 1 }
                ])
        }
    ];

    for (const attempt of attempts) {
        try {
            attempt.operation();
        } catch (error) {
            console.log(
                `${attempt.name}: rejected by ${error.constraintType} -> ${error.message}`
            );
        }
    }

    console.log("\n=== ASYNCHRONOUS ORDER WORKFLOW ===");

    await new Promise(resolve => setTimeout(resolve, 10));

    const orderId = database.createOrder("alice@example.com", [
        { sku: "LT-100", quantity: 1 },
        { sku: "MN-200", quantity: 2 }
    ]);

    console.log(`Created order ${orderId}`);

    console.log("\n=== TRANSACTION ROLLBACK ===");

    const stockBefore = database.products.get(laptopId).stock;

    try {
        database.transaction(() => {
            database.updateProductStock(laptopId, stockBefore - 1);

            // Invalid quantity triggers CHECK and causes restoration of the snapshot.
            database.createOrder("alice@example.com", [
                { sku: "LT-100", quantity: 0 }
            ]);
        });
    } catch (error) {
        const stockAfter = database.products.get(laptopId).stock;

        console.log(`Operation rejected by ${error.constraintType}`);
        console.log(`Stock before transaction: ${stockBefore}`);
        console.log(`Stock after rollback: ${stockAfter}`);
    }

    console.log("\n=== FOREIGN KEY RESTRICT ===");

    try {
        database.deleteProduct(laptopId);
    } catch (error) {
        console.log(
            `Product deletion rejected by ${error.constraintType}: ${error.message}`
        );
    }

    console.log("\n=== FINAL RELATIONAL STATE ===");

    console.log("Customers:");
    console.table([...database.customers.values()]);

    console.log("Products:");
    console.table([...database.products.values()]);

    console.log("Orders:");
    console.table([...database.orders.values()]);

    console.log("Order items:");
    console.table([...database.orderItems.values()]);
}

main().catch(error => {
    console.error("Fatal application error:", error);
    process.exitCode = 1;
});
