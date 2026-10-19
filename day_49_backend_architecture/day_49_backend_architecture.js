"use strict";

/*
 * Backend Architecture laboratory
 *
 * This program uses JavaScript-specific event-driven behavior to model
 * architecture decisions rather than translating the Python examples.
 *
 * The three architecture styles represented here are:
 * - layered architecture: technical boundaries around HTTP, application,
 *   domain, and persistence concerns;
 * - modular monolith: independent business modules inside one Node.js process;
 * - clean architecture: use cases depend on ports while adapters depend inward.
 */

const EventEmitter = require("node:events");

class DomainError extends Error {}

class Account {
    constructor(id, owner, status = "ACTIVE") {
        if (!Number.isInteger(id) || id <= 0) {
            throw new DomainError("Account id must be a positive integer");
        }
        if (!owner.trim()) {
            throw new DomainError("Account owner cannot be empty");
        }

        this.id = id;
        this.owner = owner;
        this.status = status;
    }

    suspend() {
        if (this.status === "SUSPENDED") {
            throw new DomainError("Account is already suspended");
        }
        this.status = "SUSPENDED";
    }
}

/*
 * Repository is a persistence port. The domain object never imports a
 * database driver, HTTP library, or Node-specific storage implementation.
 */
class AccountRepository {
    async save() {
        throw new Error("save() must be implemented");
    }

    async findById() {
        throw new Error("findById() must be implemented");
    }
}

class MemoryAccountRepository extends AccountRepository {
    constructor() {
        super();
        this.records = new Map();
    }

    async save(account) {
        this.records.set(account.id, account);
    }

    async findById(id) {
        return this.records.get(id) ?? null;
    }
}

/*
 * Application service coordinates the use case. It does not decide how
 * persistence works.
 */
class AccountApplicationService {
    constructor(repository) {
        this.repository = repository;
    }

    async openAccount(account) {
        const existing = await this.repository.findById(account.id);
        if (existing) {
            throw new DomainError(`Account ${account.id} already exists`);
        }

        await this.repository.save(account);
        return account;
    }
}

/*
 * A modular monolith keeps modules inside one deployment while using an
 * explicit public API. The BillingModule does not manipulate AccountModule's
 * internal Map directly.
 */
class AccountModule {
    constructor() {
        this.repository = new MemoryAccountRepository();
        this.service = new AccountApplicationService(this.repository);
    }

    async register(account) {
        return this.service.openAccount(account);
    }

    async getAccount(id) {
        return this.repository.findById(id);
    }
}

class BillingModule {
    constructor(accountModule, eventBus) {
        this.accountModule = accountModule;
        this.eventBus = eventBus;
    }

    async charge(accountId, amount) {
        if (!Number.isFinite(amount) || amount <= 0) {
            throw new DomainError("Charge amount must be positive");
        }

        const account = await this.accountModule.getAccount(accountId);

        if (!account) {
            throw new DomainError("Billing cannot charge an unknown account");
        }

        if (account.status !== "ACTIVE") {
            throw new DomainError("Suspended accounts cannot be charged");
        }

        const receipt = {
            accountId,
            amount,
            receiptId: `R-${Date.now()}-${accountId}`
        };

        this.eventBus.emit("billing.completed", receipt);
        return receipt;
    }
}

/*
 * EventEmitter demonstrates a useful modular-monolith technique: a module
 * can publish a domain/application event without giving another module
 * direct access to its private implementation details.
 */
class AuditModule {
    constructor(eventBus) {
        this.entries = [];

        eventBus.on("billing.completed", (receipt) => {
            this.entries.push({
                type: "BILLING_COMPLETED",
                receiptId: receipt.receiptId,
                accountId: receipt.accountId
            });
        });
    }
}

/*
 * Clean architecture's inner policy owns the interface it needs. JavaScript
 * has no native interface keyword, so a contract is expressed through the
 * expected method shape and validated at composition time.
 */
class PaymentUseCase {
    constructor(paymentPort) {
        if (!paymentPort || typeof paymentPort.charge !== "function") {
            throw new TypeError("Payment adapter must implement charge()");
        }

        this.paymentPort = paymentPort;
    }

    async execute(account, amount) {
        if (account.status !== "ACTIVE") {
            throw new DomainError("Only active accounts can make payments");
        }

        if (!Number.isFinite(amount) || amount <= 0 || amount > 50000) {
            throw new DomainError("Payment amount is outside the allowed range");
        }

        return this.paymentPort.charge({
            accountId: account.id,
            amount
        });
    }
}

class PaymentGatewayAdapter {
    constructor() {
        this.sequence = 0;
    }

    async charge(request) {
        this.sequence += 1;

        return {
            transactionId: `TX-${this.sequence}`,
            accountId: request.accountId,
            amount: request.amount,
            state: "AUTHORIZED"
        };
    }
}

/*
 * This function acts as the composition root. Concrete infrastructure is
 * assembled here, keeping infrastructure choices away from the domain.
 */
async function buildApplication() {
    const eventBus = new EventEmitter();
    const accountModule = new AccountModule();
    const billingModule = new BillingModule(accountModule, eventBus);
    const auditModule = new AuditModule(eventBus);

    const paymentUseCase = new PaymentUseCase(
        new PaymentGatewayAdapter()
    );

    const account = new Account(42, "Nisha Sharma");
    await accountModule.register(account);

    const receipt = await billingModule.charge(42, 1800);
    const payment = await paymentUseCase.execute(account, 950);

    console.log("MODULAR MONOLITH");
    console.log("Account:", account);
    console.log("Billing receipt:", receipt);
    console.log("Audit records:", auditModule.entries);

    console.log("\nCLEAN ARCHITECTURE");
    console.log("Payment result:", payment);

    account.suspend();

    try {
        await billingModule.charge(42, 500);
    } catch (error) {
        console.log("Expected failure:", error.message);
    }

    try {
        await paymentUseCase.execute(account, 500);
    } catch (error) {
        console.log("Expected domain failure:", error.message);
    }
}

/*
 * A small dependency-boundary check demonstrates that architectural rules
 * can be tested as executable policy rather than left as documentation.
 */
function verifyDependencyRules() {
    const allowed = new Set([
        "api->application",
        "application->domain",
        "application->ports",
        "adapters->ports"
    ]);

    const forbidden = [
        "domain->database",
        "domain->http",
        "domain->framework"
    ];

    console.log("\nDEPENDENCY POLICY");
    for (const dependency of allowed) {
        console.log(`[ALLOW] ${dependency}`);
    }

    for (const dependency of forbidden) {
        if (allowed.has(dependency)) {
            throw new Error(`Boundary policy incorrectly allows ${dependency}`);
        }
        console.log(`[BLOCK] ${dependency}`);
    }
}

async function main() {
    verifyDependencyRules();
    await buildApplication();
}

main().catch((error) => {
    console.error("Application failure:", error.message);
    process.exitCode = 1;
});
