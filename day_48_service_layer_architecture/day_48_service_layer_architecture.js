"use strict";

/*
 * Service Layer Architecture in Node.js:
 *
 * Controller:
 *   Translates transport input into application commands and formats output.
 *
 * Service:
 *   Coordinates a complete use case and transaction-like workflow.
 *
 * Repository:
 *   Owns persistence operations.
 *
 * Domain logic:
 *   Owns rules that must remain true regardless of HTTP, storage, or UI.
 *
 * This example deliberately uses an event-driven Node.js style. The service
 * publishes domain events after successful state changes, while the
 * controller remains unaware of persistence details.
 */

const { randomUUID } = require("crypto");
const { EventEmitter } = require("events");

class DomainError extends Error {
    constructor(message, code = "DOMAIN_ERROR") {
        super(message);
        this.name = "DomainError";
        this.code = code;
    }
}

class NotFoundError extends DomainError {
    constructor(message) {
        super(message, "NOT_FOUND");
        this.name = "NotFoundError";
    }
}

class ValidationError extends DomainError {
    constructor(message) {
        super(message, "VALIDATION_ERROR");
        this.name = "ValidationError";
    }
}

class ConflictError extends DomainError {
    constructor(message) {
        super(message, "CONFLICT");
        this.name = "ConflictError";
    }
}

const OrderStatus = Object.freeze({
    DRAFT: "draft",
    CONFIRMED: "confirmed",
    CANCELLED: "cancelled"
});

class OrderLine {
    constructor(productId, quantity, unitPrice) {
        if (!productId) {
            throw new ValidationError("productId is required");
        }

        if (!Number.isInteger(quantity) || quantity <= 0) {
            throw new ValidationError("quantity must be a positive integer");
        }

        if (!Number.isSafeInteger(unitPrice) || unitPrice < 0) {
            throw new ValidationError(
                "unitPrice must be a non-negative safe integer"
            );
        }

        this.productId = productId;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
    }

    get subtotal() {
        const subtotal = this.quantity * this.unitPrice;

        // Money calculations should not silently exceed JavaScript's exact
        // integer range. Production systems can use BigInt or a decimal type.
        if (!Number.isSafeInteger(subtotal)) {
            throw new ValidationError("Order line amount exceeds safe integer range");
        }

        return subtotal;
    }
}

class Order {
    constructor(customerId) {
        if (!customerId) {
            throw new ValidationError("customerId is required");
        }

        this.id = randomUUID();
        this.customerId = customerId;
        this.status = OrderStatus.DRAFT;
        this.lines = [];
        this.createdAt = new Date();
    }

    addLine(line) {
        if (this.status !== OrderStatus.DRAFT) {
            throw new ConflictError("Only draft orders can be modified");
        }

        if (this.lines.some(existing => existing.productId === line.productId)) {
            throw new ConflictError("The product already exists in the order");
        }

        this.lines.push(line);
    }

    total() {
        return this.lines.reduce(
            (sum, line) => sum + line.subtotal,
            0
        );
    }

    confirm() {
        if (this.status !== OrderStatus.DRAFT) {
            throw new ConflictError("Only draft orders can be confirmed");
        }

        if (this.lines.length === 0) {
            throw new ValidationError(
                "An order must contain at least one line before confirmation"
            );
        }

        this.status = OrderStatus.CONFIRMED;
    }

    cancel() {
        if (this.status === OrderStatus.CANCELLED) {
            throw new ConflictError("Order is already cancelled");
        }

        if (this.status === OrderStatus.CONFIRMED) {
            throw new ConflictError(
                "Confirmed orders require a separate cancellation workflow"
            );
        }

        this.status = OrderStatus.CANCELLED;
    }
}

class InMemoryRepository {
    constructor() {
        this.records = new Map();
    }

    async getById(id) {
        return this.records.get(id) ?? null;
    }

    async save(entity) {
        if (!entity?.id) {
            throw new ValidationError("Persisted entities require an id");
        }

        this.records.set(entity.id, entity);
        return entity;
    }

    async delete(id) {
        return this.records.delete(id);
    }

    async list() {
        return [...this.records.values()];
    }
}

class ProductRepository extends InMemoryRepository {
    async findActiveById(productId) {
        const product = await this.getById(productId);

        if (!product || product.active !== true) {
            return null;
        }

        return product;
    }
}

class OrderRepository extends InMemoryRepository {
    async findByCustomer(customerId) {
        const orders = await this.list();
        return orders.filter(order => order.customerId === customerId);
    }
}

class OrderEventBus extends EventEmitter {
    publish(eventName, payload) {
        this.emit(eventName, Object.freeze({
            ...payload,
            occurredAt: new Date()
        }));
    }
}

class OrderService {
    constructor({ orderRepository, productRepository, eventBus }) {
        this.orderRepository = orderRepository;
        this.productRepository = productRepository;
        this.eventBus = eventBus;
    }

    async createOrder(customerId) {
        if (typeof customerId !== "string" || customerId.trim() === "") {
            throw new ValidationError("customerId must be a non-empty string");
        }

        const order = new Order(customerId.trim());
        await this.orderRepository.save(order);

        this.eventBus.publish("order.created", {
            orderId: order.id,
            customerId: order.customerId
        });

        return order;
    }

    async addProduct(orderId, productId, quantity) {
        const order = await this.orderRepository.getById(orderId);

        if (!order) {
            throw new NotFoundError("Order not found");
        }

        const product = await this.productRepository.findActiveById(productId);

        if (!product) {
            throw new NotFoundError("Active product not found");
        }

        const line = new OrderLine(
            product.id,
            quantity,
            product.price
        );

        order.addLine(line);
        await this.orderRepository.save(order);

        this.eventBus.publish("order.line_added", {
            orderId: order.id,
            productId: product.id,
            quantity
        });

        return order;
    }

    async confirmOrder(orderId) {
        const order = await this.orderRepository.getById(orderId);

        if (!order) {
            throw new NotFoundError("Order not found");
        }

        order.confirm();
        await this.orderRepository.save(order);

        this.eventBus.publish("order.confirmed", {
            orderId: order.id,
            total: order.total()
        });

        return order;
    }

    async cancelOrder(orderId) {
        const order = await this.orderRepository.getById(orderId);

        if (!order) {
            throw new NotFoundError("Order not found");
        }

        order.cancel();
        await this.orderRepository.save(order);

        this.eventBus.publish("order.cancelled", {
            orderId: order.id
        });

        return order;
    }
}

class OrderController {
    constructor(orderService) {
        this.orderService = orderService;
    }

    async create(requestBody) {
        try {
            const order = await this.orderService.createOrder(
                requestBody.customerId
            );

            return {
                status: 201,
                body: this.serialize(order)
            };
        } catch (error) {
            return this.toHttpResponse(error);
        }
    }

    async addProduct(requestBody) {
        try {
            const order = await this.orderService.addProduct(
                requestBody.orderId,
                requestBody.productId,
                requestBody.quantity
            );

            return {
                status: 200,
                body: this.serialize(order)
            };
        } catch (error) {
            return this.toHttpResponse(error);
        }
    }

    async confirm(orderId) {
        try {
            const order = await this.orderService.confirmOrder(orderId);

            return {
                status: 200,
                body: this.serialize(order)
            };
        } catch (error) {
            return this.toHttpResponse(error);
        }
    }

    toHttpResponse(error) {
        if (error instanceof ValidationError) {
            return { status: 400, body: { error: error.message } };
        }

        if (error instanceof NotFoundError) {
            return { status: 404, body: { error: error.message } };
        }

        if (error instanceof ConflictError) {
            return { status: 409, body: { error: error.message } };
        }

        console.error("Unexpected application error:", error);

        return {
            status: 500,
            body: { error: "Internal server error" }
        };
    }

    serialize(order) {
        return {
            id: order.id,
            customerId: order.customerId,
            status: order.status,
            total: order.total(),
            lines: order.lines.map(line => ({
                productId: line.productId,
                quantity: line.quantity,
                unitPrice: line.unitPrice,
                subtotal: line.subtotal
            }))
        };
    }
}

async function runExample() {
    const productRepository = new ProductRepository();
    const orderRepository = new OrderRepository();
    const eventBus = new OrderEventBus();

    // Event subscribers belong outside the controller. This allows auditing,
    // notifications, or analytics to react without coupling them to HTTP code.
    eventBus.on("order.confirmed", event => {
        console.log(
            `Audit event: order ${event.orderId} confirmed for ${event.total} cents`
        );
    });

    const keyboardId = randomUUID();

    await productRepository.save({
        id: keyboardId,
        name: "Mechanical Keyboard",
        price: 8500,
        active: true
    });

    const orderService = new OrderService({
        orderRepository,
        productRepository,
        eventBus
    });

    const controller = new OrderController(orderService);

    const created = await controller.create({
        customerId: "customer-42"
    });

    console.log("Created:", created);

    const orderId = created.body.id;

    const added = await controller.addProduct({
        orderId,
        productId: keyboardId,
        quantity: 2
    });

    console.log("Added:", added);

    const confirmed = await controller.confirm(orderId);
    console.log("Confirmed:", confirmed);

    // This demonstrates why business invariants remain in the domain rather
    // than being implemented only as controller checks.
    const rejected = await controller.addProduct({
        orderId,
        productId: randomUUID(),
        quantity: 1
    });

    console.log("Rejected:", rejected);
}

runExample().catch(error => {
    console.error("Fatal application error:", error);
    process.exitCode = 1;
});
