"use strict";

/*
 * Dependency Injection in JavaScript
 *
 * This file progresses from direct dependencies to injected services,
 * dependency chains, database-like repositories, factories, async
 * dependencies, caching, lifecycle management, testing, and a
 * production-style composition root.
 *
 * Runtime:
 *     Node.js 18+
 *
 * No external packages are required.
 */

// ============================================================================
// 1. DIRECT DEPENDENCY
// ============================================================================

class EmailSender {
    send(recipient, message) {
        console.log(`[EMAIL] To=${recipient}: ${message}`);
    }
}

class TightlyCoupledWelcomeService {
    constructor() {
        // The service creates its own dependency.
        // This makes replacement and testing harder.
        this.sender = new EmailSender();
    }

    welcome(recipient) {
        this.sender.send(recipient, "Welcome to the application.");
    }
}

function demonstrateTightCoupling() {
    console.log("\n=== 1. Tight Coupling ===");
    new TightlyCoupledWelcomeService().welcome("alice@example.com");
}

// ============================================================================
// 2. CONSTRUCTOR INJECTION
// ============================================================================

class ConsoleSender {
    send(recipient, message) {
        console.log(`[CONSOLE] To=${recipient}: ${message}`);
    }
}

class RecordingSender {
    constructor() {
        this.messages = [];
    }

    send(recipient, message) {
        this.messages.push({ recipient, message });
    }
}

class WelcomeService {
    constructor(sender) {
        // Required dependency is supplied by the caller.
        this.sender = sender;
    }

    welcome(recipient) {
        this.sender.send(recipient, "Welcome to the application.");
    }
}

function demonstrateConstructorInjection() {
    console.log("\n=== 2. Constructor Injection ===");

    const productionService = new WelcomeService(new ConsoleSender());
    productionService.welcome("bob@example.com");

    const recordingSender = new RecordingSender();
    const testService = new WelcomeService(recordingSender);

    testService.welcome("test@example.com");
    console.log("Recorded message:", recordingSender.messages);
}

// ============================================================================
// 3. FUNCTION DEPENDENCY INJECTION
// ============================================================================

class Calculator {
    constructor(operation) {
        // Functions are first-class values in JavaScript.
        // A function can therefore be a dependency.
        this.operation = operation;
    }

    execute(a, b) {
        return this.operation(a, b);
    }
}

const addition = (a, b) => a + b;
const multiplication = (a, b) => a * b;

function demonstrateFunctionInjection() {
    console.log("\n=== 3. Function Injection ===");

    const addCalculator = new Calculator(addition);
    const multiplyCalculator = new Calculator(multiplication);

    console.log("Addition:", addCalculator.execute(5, 3));
    console.log("Multiplication:", multiplyCalculator.execute(5, 3));
}

// ============================================================================
// 4. REPOSITORY ABSTRACTION
// ============================================================================

class InMemoryUserRepository {
    constructor(users) {
        this.users = new Map(Object.entries(users));
    }

    async findEmail(userId) {
        return this.users.get(String(userId)) ?? null;
    }
}

class UserNotificationService {
    constructor(repository, sender) {
        this.repository = repository;
        this.sender = sender;
    }

    async notify(userId, message) {
        const email = await this.repository.findEmail(userId);

        if (email === null) {
            return false;
        }

        this.sender.send(email, message);
        return true;
    }
}

async function demonstrateRepositoryInjection() {
    console.log("\n=== 4. Repository Injection ===");

    const repository = new InMemoryUserRepository({
        1: "alice@example.com",
        2: "bob@example.com"
    });

    const service = new UserNotificationService(
        repository,
        new ConsoleSender()
    );

    console.log(
        "Notification result:",
        await service.notify(1, "Your report is ready.")
    );

    console.log(
        "Unknown user:",
        await service.notify(999, "This is not sent.")
    );
}

// ============================================================================
// 5. DATABASE-LIKE DEPENDENCY
// ============================================================================

class FakeDatabase {
    constructor(initialRows = []) {
        this.rows = [...initialRows];
    }

    async query(sql, parameters = []) {
        /*
         * This is deliberately a small database simulation.
         * The business service does not depend on its implementation.
         */
        if (!sql.includes("SELECT email FROM users WHERE id = ?")) {
            throw new Error("Unsupported query in this demonstration.");
        }

        const id = parameters[0];
        const row = this.rows.find(user => user.id === id);

        return row ? [row] : [];
    }
}

class DatabaseUserRepository {
    constructor(database) {
        this.database = database;
    }

    async findEmail(userId) {
        const rows = await this.database.query(
            "SELECT email FROM users WHERE id = ?",
            [userId]
        );

        return rows.length > 0 ? rows[0].email : null;
    }
}

async function demonstrateDatabaseDependency() {
    console.log("\n=== 5. Database Dependency ===");

    const database = new FakeDatabase([
        { id: 1, email: "db-alice@example.com" },
        { id: 2, email: "db-bob@example.com" }
    ]);

    const repository = new DatabaseUserRepository(database);
    const service = new UserNotificationService(
        repository,
        new ConsoleSender()
    );

    await service.notify(1, "Loaded through a database repository.");
}

// ============================================================================
// 6. DEPENDENCY CHAINS
// ============================================================================

class UserValidator {
    validate(userId, email) {
        if (!Number.isInteger(userId) || userId <= 0) {
            throw new Error("User ID must be a positive integer.");
        }

        if (!email.includes("@")) {
            throw new Error("Email address is invalid.");
        }
    }
}

class AuditLogger {
    record(event) {
        console.log(`[AUDIT] ${event}`);
    }
}

class RegistrationService {
    /*
     * Dependency graph:
     *
     * RegistrationService
     *   -> UserRepository
     *   -> UserValidator
     *   -> AuditLogger
     *   -> MessageSender
     *
     * Dependencies can themselves contain dependencies.
     */

    constructor(repository, validator, auditLogger, sender) {
        this.repository = repository;
        this.validator = validator;
        this.auditLogger = auditLogger;
        this.sender = sender;
    }

    async register(userId, email) {
        try {
            this.validator.validate(userId, email);

            if (await this.repository.findEmail(userId) !== null) {
                throw new Error("User already exists.");
            }

            this.auditLogger.record(`Registered user ${userId}`);
            this.sender.send(email, "Registration successful.");

            return true;
        } catch (error) {
            this.auditLogger.record(`Registration failed: ${error.message}`);
            return false;
        }
    }
}

async function demonstrateDependencyChain() {
    console.log("\n=== 6. Dependency Chain ===");

    const repository = new InMemoryUserRepository({
        1: "existing@example.com"
    });

    const service = new RegistrationService(
        repository,
        new UserValidator(),
        new AuditLogger(),
        new ConsoleSender()
    );

    console.log("New user:", await service.register(2, "new@example.com"));
    console.log("Duplicate:", await service.register(1, "existing@example.com"));
    console.log("Invalid:", await service.register(-1, "bad@example.com"));
}

// ============================================================================
// 7. ASYNC DEPENDENCY
// ============================================================================

class AsyncPaymentGateway {
    constructor(shouldFail = false) {
        this.shouldFail = shouldFail;
    }

    async charge(amount) {
        if (!Number.isFinite(amount) || amount <= 0) {
            throw new Error("Payment amount must be positive.");
        }

        await new Promise(resolve => setTimeout(resolve, 5));

        if (this.shouldFail) {
            throw new Error("Payment gateway unavailable.");
        }

        return `PAY-${Math.round(amount * 100)}`;
    }
}

class PaymentService {
    constructor(paymentGateway) {
        this.paymentGateway = paymentGateway;
    }

    async pay(amount) {
        try {
            return await this.paymentGateway.charge(amount);
        } catch (error) {
            console.error(`[PAYMENT ERROR] ${error.message}`);
            return null;
        }
    }
}

async function demonstrateAsyncInjection() {
    console.log("\n=== 7. Asynchronous Dependency ===");

    const successfulService = new PaymentService(
        new AsyncPaymentGateway()
    );

    console.log("Payment:", await successfulService.pay(49.99));
    console.log("Invalid payment:", await successfulService.pay(0));

    const failingService = new PaymentService(
        new AsyncPaymentGateway(true)
    );

    console.log("Failed payment:", await failingService.pay(20));
}

// ============================================================================
// 8. CLOCK DEPENDENCY
// ============================================================================

class SystemClock {
    now() {
        return Date.now();
    }
}

class FakeClock {
    constructor(timestamp) {
        this.timestamp = timestamp;
    }

    now() {
        return this.timestamp;
    }
}

class SessionService {
    constructor(clock) {
        this.clock = clock;
    }

    createSession(userId) {
        return {
            userId,
            createdAt: this.clock.now()
        };
    }
}

function demonstrateClockInjection() {
    console.log("\n=== 8. Deterministic Time ===");

    const service = new SessionService(
        new FakeClock(1700000000000)
    );

    console.log(service.createSession(10));
}

// ============================================================================
// 9. CACHE DEPENDENCY
// ============================================================================

class MemoryCache {
    constructor() {
        this.values = new Map();
    }

    get(key) {
        return this.values.get(key);
    }

    set(key, value) {
        this.values.set(key, value);
    }
}

class CachedUserService {
    constructor(repository, cache = null) {
        this.repository = repository;
        this.cache = cache;
    }

    async findEmail(userId) {
        const key = `user:${userId}`;

        if (this.cache) {
            const cachedValue = this.cache.get(key);

            if (typeof cachedValue === "string") {
                console.log(`[CACHE HIT] ${key}`);
                return cachedValue;
            }
        }

        const email = await this.repository.findEmail(userId);

        if (email !== null && this.cache) {
            this.cache.set(key, email);
        }

        return email;
    }
}

async function demonstrateCaching() {
    console.log("\n=== 9. Optional Cache Dependency ===");

    const repository = new InMemoryUserRepository({
        1: "cached@example.com"
    });

    const service = new CachedUserService(
        repository,
        new MemoryCache()
    );

    console.log(await service.findEmail(1));
    console.log(await service.findEmail(1));
}

// ============================================================================
// 10. SIMPLE DEPENDENCY CONTAINER
// ============================================================================

class ServiceContainer {
    constructor() {
        this.factories = new Map();
        this.singletons = new Map();
    }

    registerSingleton(name, factory) {
        this.factories.set(name, factory);
    }

    resolve(name) {
        if (this.singletons.has(name)) {
            return this.singletons.get(name);
        }

        const factory = this.factories.get(name);

        if (!factory) {
            throw new Error(`Service '${name}' is not registered.`);
        }

        const instance = factory(this);
        this.singletons.set(name, instance);

        return instance;
    }
}

async function demonstrateContainer() {
    console.log("\n=== 10. Dependency Container ===");

    const container = new ServiceContainer();

    container.registerSingleton(
        "repository",
        () => new InMemoryUserRepository({
            1: "container@example.com"
        })
    );

    container.registerSingleton(
        "sender",
        () => new ConsoleSender()
    );

    container.registerSingleton(
        "notificationService",
        c => new UserNotificationService(
            c.resolve("repository"),
            c.resolve("sender")
        )
    );

    const service = container.resolve("notificationService");

    await service.notify(
        1,
        "Resolved through a dependency container."
    );
}

// ============================================================================
// 11. OBJECT LIFECYCLES
// ============================================================================

class RequestContext {
    constructor(requestId) {
        this.requestId = requestId;
    }
}

function demonstrateLifecycles() {
    console.log("\n=== 11. Dependency Lifecycles ===");

    const singletonLogger = new AuditLogger();

    const requestOne = new RequestContext("REQ-001");
    const requestTwo = new RequestContext("REQ-002");

    singletonLogger.record(`Handling ${requestOne.requestId}`);
    singletonLogger.record(`Handling ${requestTwo.requestId}`);

    console.log(
        "Different request objects:",
        requestOne !== requestTwo
    );
}

// ============================================================================
// 12. VALIDATION OF DEPENDENCY CONFIGURATION
// ============================================================================

function requireDependency(value, dependencyName) {
    if (value === null || value === undefined) {
        throw new TypeError(
            `Required dependency '${dependencyName}' was not supplied.`
        );
    }

    return value;
}

class StrictNotificationService {
    constructor(repository, sender) {
        this.repository = requireDependency(repository, "repository");
        this.sender = requireDependency(sender, "sender");

        if (typeof this.sender.send !== "function") {
            throw new TypeError("sender must expose send().");
        }

        if (typeof this.repository.findEmail !== "function") {
            throw new TypeError("repository must expose findEmail().");
        }
    }

    async notify(userId, message) {
        const email = await this.repository.findEmail(userId);

        if (!email) {
            return false;
        }

        this.sender.send(email, message);
        return true;
    }
}

async function demonstrateValidation() {
    console.log("\n=== 12. Dependency Validation ===");

    try {
        new StrictNotificationService(null, new ConsoleSender());
    } catch (error) {
        console.log("Expected configuration error:", error.message);
    }
}

// ============================================================================
// 13. UNIT-STYLE TESTS WITHOUT A FRAMEWORK
// ============================================================================

function assertEqual(actual, expected, message) {
    if (actual !== expected) {
        throw new Error(
            `${message}: expected ${expected}, received ${actual}`
        );
    }
}

function assertDeepEqual(actual, expected, message) {
    const actualJson = JSON.stringify(actual);
    const expectedJson = JSON.stringify(expected);

    if (actualJson !== expectedJson) {
        throw new Error(
            `${message}: expected ${expectedJson}, received ${actualJson}`
        );
    }
}

async function runTests() {
    console.log("\n=== 13. Tests ===");

    const repository = new InMemoryUserRepository({
        1: "test@example.com"
    });

    const sender = new RecordingSender();

    const service = new UserNotificationService(
        repository,
        sender
    );

    assertEqual(
        await service.notify(1, "Hello"),
        true,
        "Existing user should be notified"
    );

    assertDeepEqual(
        sender.messages,
        [
            {
                recipient: "test@example.com",
                message: "Hello"
            }
        ],
        "Sender should receive the expected message"
    );

    assertEqual(
        await service.notify(999, "Missing"),
        false,
        "Missing user should not be notified"
    );

    const sessionService = new SessionService(
        new FakeClock(123)
    );

    assertDeepEqual(
        sessionService.createSession(7),
        {
            userId: 7,
            createdAt: 123
        },
        "Injected clock should make the test deterministic"
    );

    console.log("All tests passed.");
}

// ============================================================================
// 14. PRODUCTION-STYLE COMPOSITION ROOT
// ============================================================================

function composeApplication(environment = "production") {
    /*
     * Concrete dependencies are assembled at the application boundary.
     * Business services remain unaware of infrastructure construction.
     */

    const database = new FakeDatabase([
        { id: 1, email: "production@example.com" }
    ]);

    const repository = new DatabaseUserRepository(database);
    const sender =
        environment === "test"
            ? new RecordingSender()
            : new ConsoleSender();

    const paymentGateway = new AsyncPaymentGateway();
    const clock =
        environment === "test"
            ? new FakeClock(1700000000000)
            : new SystemClock();

    return {
        notificationService: new UserNotificationService(
            repository,
            sender
        ),
        paymentService: new PaymentService(paymentGateway),
        sessionService: new SessionService(clock)
    };
}

async function demonstrateCompleteComposition() {
    console.log("\n=== 14. Complete Application Composition ===");

    const application = composeApplication();

    await application.notificationService.notify(
        1,
        "Your account is active."
    );

    console.log(
        "Payment ID:",
        await application.paymentService.pay(125.50)
    );

    console.log(
        "Session:",
        application.sessionService.createSession(1)
    );
}

// ============================================================================
// 15. PERFORMANCE CONSIDERATIONS
// ============================================================================

function directOperation(value) {
    return value * 2;
}

function demonstratePerformance() {
    console.log("\n=== 15. Performance Considerations ===");

    const values = Array.from({ length: 100000 }, (_, index) => index);

    const start = process.hrtime.bigint();

    const results = values.map(directOperation);

    const elapsedNanoseconds = process.hrtime.bigint() - start;

    console.log("Processed:", results.length);
    console.log("First result:", results[0]);
    console.log(
        "Elapsed milliseconds:",
        Number(elapsedNanoseconds) / 1_000_000
    );

    console.log(
        "A small abstraction boundary usually costs much less than "
        + "database, network, disk, or external API operations."
    );
}

// ============================================================================
// 16. MAIN
// ============================================================================

async function main() {
    console.log("=".repeat(78));
    console.log("DEPENDENCY INJECTION: COMPLETE JAVASCRIPT STUDY");
    console.log("=".repeat(78));

    demonstrateTightCoupling();
    demonstrateConstructorInjection();
    demonstrateFunctionInjection();

    await demonstrateRepositoryInjection();
    await demonstrateDatabaseDependency();
    await demonstrateDependencyChain();
    await demonstrateAsyncInjection();

    demonstrateClockInjection();
    await demonstrateCaching();
    await demonstrateContainer();
    demonstrateLifecycles();
    await demonstrateValidation();
    await runTests();
    await demonstrateCompleteComposition();

    demonstratePerformance();

    console.log("\nStudy execution completed successfully.");
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
