/**
 * Backend Project Structure
 * =========================
 *
 * This JavaScript file complements the Python implementation by focusing
 * on JavaScript's module system, asynchronous service/repository behavior,
 * dependency injection, configuration, validation, errors, and HTTP-like
 * request handling.
 *
 * The program uses only built-in JavaScript/Node.js capabilities.
 *
 * Run with:
 *     node backend_project_structure.js
 *
 * No external npm package is required.
 */

"use strict";

// ============================================================================
// 1. MODULE-ORIENTED THINKING
// ============================================================================

/*
A production JavaScript backend is commonly divided into files such as:

    src/
      app.js
      config.js

      routes/
        taskRoutes.js

      controllers/
        taskController.js

      services/
        taskService.js

      repositories/
        taskRepository.js

      models/
        task.js

      utils/
        validation.js

This single file simulates those boundaries with classes and functions.

The important idea is not the folder name. The important idea is that each
component has a clear responsibility.
*/


// ============================================================================
// 2. CONFIGURATION
// ============================================================================

class Config {
    constructor(environment = process.env.NODE_ENV || "development") {
        this.environment = environment;
        this.port = Number(process.env.PORT || 3000);
        this.maxTitleLength = Number(
            process.env.MAX_TITLE_LENGTH || 100
        );
        this.databaseUrl =
            process.env.DATABASE_URL || "memory://tasks";
        this.logLevel =
            process.env.LOG_LEVEL || "info";
    }

    validate() {
        if (!Number.isInteger(this.port) || this.port <= 0) {
            throw new Error("PORT must be a positive integer");
        }

        if (
            !Number.isInteger(this.maxTitleLength) ||
            this.maxTitleLength <= 0
        ) {
            throw new Error(
                "MAX_TITLE_LENGTH must be a positive integer"
            );
        }

        if (
            this.environment === "production" &&
            this.databaseUrl.startsWith("memory://")
        ) {
            throw new Error(
                "Production should use a persistent database"
            );
        }
    }
}


// ============================================================================
// 3. DOMAIN MODEL
// ============================================================================

const TaskStatus = Object.freeze({
    PENDING: "pending",
    COMPLETED: "completed",
});

class Task {
    constructor({ id, title, ownerId, status = TaskStatus.PENDING }) {
        this.id = id;
        this.title = title;
        this.ownerId = ownerId;
        this.status = status;
        this.createdAt = new Date();
    }

    complete() {
        if (this.status === TaskStatus.COMPLETED) {
            throw new ConflictError("Task is already completed");
        }

        this.status = TaskStatus.COMPLETED;
    }
}


// ============================================================================
// 4. APPLICATION ERRORS
// ============================================================================

class ApplicationError extends Error {
    constructor(message, statusCode = 500) {
        super(message);
        this.name = this.constructor.name;
        this.statusCode = statusCode;
    }
}

class ValidationError extends ApplicationError {
    constructor(message) {
        super(message, 400);
    }
}

class NotFoundError extends ApplicationError {
    constructor(message) {
        super(message, 404);
    }
}

class AuthorizationError extends ApplicationError {
    constructor(message) {
        super(message, 403);
    }
}

class ConflictError extends ApplicationError {
    constructor(message) {
        super(message, 409);
    }
}


// ============================================================================
// 5. UTILITY FUNCTIONS
// ============================================================================

function normalizeTitle(title, maximumLength) {
    if (typeof title !== "string") {
        throw new ValidationError("Title must be a string");
    }

    // Collapse repeated whitespace and trim the boundary.
    const normalized = title.trim().replace(/\s+/g, " ");

    if (normalized.length === 0) {
        throw new ValidationError("Title cannot be empty");
    }

    if (normalized.length > maximumLength) {
        throw new ValidationError(
            `Title cannot exceed ${maximumLength} characters`
        );
    }

    return normalized;
}

function validatePositiveInteger(value, fieldName) {
    if (!Number.isInteger(value) || value <= 0) {
        throw new ValidationError(
            `${fieldName} must be a positive integer`
        );
    }
}


// ============================================================================
// 6. REPOSITORY
// ============================================================================

class TaskRepository {
    /*
    The repository owns persistence concerns.

    An asynchronous interface is used even though this implementation is
    in memory. That makes the calling service compatible with a future
    database repository where operations naturally return Promises.
    */

    constructor() {
        this.tasks = new Map();
        this.nextId = 1;
    }

    async create(task) {
        task.id = this.nextId;
        this.nextId += 1;

        this.tasks.set(task.id, task);

        return task;
    }

    async findById(id) {
        return this.tasks.get(id) || null;
    }

    async findByOwner(ownerId) {
        return [...this.tasks.values()]
            .filter((task) => task.ownerId === ownerId);
    }

    async update(task) {
        if (!this.tasks.has(task.id)) {
            throw new NotFoundError("Task does not exist");
        }

        this.tasks.set(task.id, task);

        return task;
    }

    async delete(id) {
        return this.tasks.delete(id);
    }
}


// ============================================================================
// 7. SERVICE LAYER
// ============================================================================

class TaskService {
    /*
    The service layer coordinates business rules.

    Notice that the constructor receives the repository rather than creating
    one internally. This is dependency injection.
    */

    constructor({ repository, config }) {
        this.repository = repository;
        this.config = config;
    }

    async createTask(ownerId, title) {
        validatePositiveInteger(ownerId, "ownerId");

        const normalizedTitle = normalizeTitle(
            title,
            this.config.maxTitleLength
        );

        const task = new Task({
            id: 0,
            title: normalizedTitle,
            ownerId,
        });

        return this.repository.create(task);
    }

    async getTask(actorId, taskId) {
        validatePositiveInteger(actorId, "actorId");
        validatePositiveInteger(taskId, "taskId");

        const task = await this.repository.findById(taskId);

        if (!task) {
            throw new NotFoundError("Task not found");
        }

        this.ensureOwner(actorId, task);

        return task;
    }

    async listTasks(actorId) {
        validatePositiveInteger(actorId, "actorId");

        return this.repository.findByOwner(actorId);
    }

    async completeTask(actorId, taskId) {
        const task = await this.getTask(actorId, taskId);

        task.complete();

        return this.repository.update(task);
    }

    async deleteTask(actorId, taskId) {
        const task = await this.getTask(actorId, taskId);

        const deleted = await this.repository.delete(task.id);

        if (!deleted) {
            throw new NotFoundError("Task was already deleted");
        }
    }

    ensureOwner(actorId, task) {
        if (actorId !== task.ownerId) {
            throw new AuthorizationError(
                "Actor is not allowed to access this task"
            );
        }
    }
}


// ============================================================================
// 8. CONTROLLER LAYER
// ============================================================================

class TaskController {
    constructor(service) {
        this.service = service;
    }

    async create(request) {
        try {
            const task = await this.service.createTask(
                request.ownerId,
                request.title
            );

            return {
                status: 201,
                body: this.serialize(task),
            };
        } catch (error) {
            return this.handleError(error);
        }
    }

    async get(actorId, taskId) {
        try {
            const task = await this.service.getTask(
                actorId,
                taskId
            );

            return {
                status: 200,
                body: this.serialize(task),
            };
        } catch (error) {
            return this.handleError(error);
        }
    }

    async complete(actorId, taskId) {
        try {
            const task = await this.service.completeTask(
                actorId,
                taskId
            );

            return {
                status: 200,
                body: this.serialize(task),
            };
        } catch (error) {
            return this.handleError(error);
        }
    }

    async delete(actorId, taskId) {
        try {
            await this.service.deleteTask(actorId, taskId);

            return {
                status: 204,
                body: null,
            };
        } catch (error) {
            return this.handleError(error);
        }
    }

    serialize(task) {
        return {
            id: task.id,
            title: task.title,
            ownerId: task.ownerId,
            status: task.status,
            createdAt: task.createdAt.toISOString(),
        };
    }

    handleError(error) {
        if (error instanceof ApplicationError) {
            return {
                status: error.statusCode,
                body: {
                    error: error.message,
                },
            };
        }

        // Do not expose arbitrary internal errors to clients.
        return {
            status: 500,
            body: {
                error: "Internal server error",
            },
        };
    }
}


// ============================================================================
// 9. ASYNCHRONOUS BEHAVIOR
// ============================================================================

async function demonstrateAsyncFlow(controller) {
    console.log("\n--- Asynchronous service flow ---");

    const created = await controller.create({
        ownerId: 42,
        title: "  Build   a   backend   module  ",
    });

    console.log("Create:", created);

    const taskId = created.body.id;

    const fetched = await controller.get(42, taskId);

    console.log("Get:", fetched);

    const completed = await controller.complete(42, taskId);

    console.log("Complete:", completed);

    const secondCompletion = await controller.complete(
        42,
        taskId
    );

    console.log("Second completion:", secondCompletion);
}


// ============================================================================
// 10. CONCURRENCY AND Promise.all
// ============================================================================

async function demonstrateParallelOperations(controller) {
    console.log("\n--- Parallel asynchronous operations ---");

    /*
    Promise.all allows independent asynchronous operations to run together.

    A real service might use this for independent data retrieval operations.
    It should not be used blindly when operations depend on each other or
    when running them simultaneously would overload a downstream system.
    */

    const requests = [
        controller.create({
            ownerId: 7,
            title: "Task A",
        }),
        controller.create({
            ownerId: 7,
            title: "Task B",
        }),
        controller.create({
            ownerId: 7,
            title: "Task C",
        }),
    ];

    const results = await Promise.all(requests);

    console.log(results);
}


// ============================================================================
// 11. VALIDATION EDGE CASES
// ============================================================================

async function demonstrateValidation(controller) {
    console.log("\n--- Validation edge cases ---");

    const cases = [
        {
            ownerId: 1,
            title: "",
        },
        {
            ownerId: 1,
            title: "       ",
        },
        {
            ownerId: 1,
            title: "This title is intentionally much too long",
        },
        {
            ownerId: 0,
            title: "Valid title",
        },
    ];

    for (const request of cases) {
        const response = await controller.create(request);
        console.log(response);
    }
}


// ============================================================================
// 12. AUTHORIZATION BOUNDARY
// ============================================================================

async function demonstrateAuthorization(controller) {
    console.log("\n--- Authorization boundary ---");

    const created = await controller.create({
        ownerId: 100,
        title: "Private task",
    });

    const taskId = created.body.id;

    const unauthorized = await controller.get(200, taskId);

    console.log("Unauthorized request:", unauthorized);
}


// ============================================================================
// 13. FEATURE-BASED ORGANIZATION
// ============================================================================

/*
A layered structure groups code by technical responsibility:

    controllers/
    services/
    repositories/
    models/

A feature-oriented structure can group related code:

    tasks/
        taskController.js
        taskService.js
        taskRepository.js
        taskModel.js

    users/
        userController.js
        userService.js
        userRepository.js
        userModel.js

Neither organization is universally correct.

Layer-oriented organization can make architectural boundaries obvious.

Feature-oriented organization can make large domains easier to navigate
because all task-related files are close together.

The best choice depends on domain size and how independently features evolve.
*/


// ============================================================================
// 14. DEPENDENCY INJECTION WITH A FAKE REPOSITORY
// ============================================================================

class FakeTaskRepository {
    constructor() {
        this.createdTasks = [];
    }

    async create(task) {
        task.id = this.createdTasks.length + 1;
        this.createdTasks.push(task);
        return task;
    }

    async findById(id) {
        return (
            this.createdTasks.find((task) => task.id === id) ||
            null
        );
    }

    async findByOwner(ownerId) {
        return this.createdTasks.filter(
            (task) => task.ownerId === ownerId
        );
    }

    async update(task) {
        const index = this.createdTasks.findIndex(
            (stored) => stored.id === task.id
        );

        if (index === -1) {
            throw new NotFoundError("Task does not exist");
        }

        this.createdTasks[index] = task;

        return task;
    }

    async delete(id) {
        const originalLength = this.createdTasks.length;

        this.createdTasks = this.createdTasks.filter(
            (task) => task.id !== id
        );

        return this.createdTasks.length !== originalLength;
    }
}

async function demonstrateDependencyInjection(config) {
    console.log("\n--- Dependency injection with a fake repository ---");

    const fakeRepository = new FakeTaskRepository();

    const service = new TaskService({
        repository: fakeRepository,
        config,
    });

    const task = await service.createTask(
        55,
        "Service test"
    );

    console.log(task);

    /*
    The same service code works with TaskRepository or FakeTaskRepository.
    The service cares about the required repository behavior, not its
    concrete storage mechanism.
    */
}


// ============================================================================
// 15. STARTUP / COMPOSITION ROOT
// ============================================================================

function createApplication() {
    /*
    Application startup is where concrete implementations are assembled.

        configuration
             |
        repository
             |
         service
             |
        controller

    This prevents lower-level components from having to know how the entire
    application is constructed.
    */

    const config = new Config();

    config.validate();

    const repository = new TaskRepository();

    const service = new TaskService({
        repository,
        config,
    });

    const controller = new TaskController(service);

    return {
        config,
        repository,
        service,
        controller,
    };
}


// ============================================================================
// 16. PERFORMANCE CONSIDERATIONS
// ============================================================================

async function demonstratePerformance() {
    console.log("\n--- Performance considerations ---");

    const repository = new TaskRepository();

    const start = process.hrtime.bigint();

    for (let index = 1; index <= 10000; index += 1) {
        await repository.create(
            new Task({
                id: 0,
                title: `Task ${index}`,
                ownerId: index % 100,
            })
        );
    }

    const elapsedNanoseconds =
        process.hrtime.bigint() - start;

    console.log(
        `10,000 in-memory inserts: ${
            Number(elapsedNanoseconds) / 1_000_000
        } ms`
    );

    /*
    Map lookup by key is generally O(1) average time.

    findByOwner() scans the collection and is O(n).

    A production database would normally use indexes for frequently queried
    fields such as owner_id.

    Performance should be measured against realistic workloads rather than
    inferred solely from source code.
    */
}


// ============================================================================
// 17. COMMON BACKEND DESIGN MISTAKES
// ============================================================================

function printDesignRules() {
    console.log(
        `
--- Design rules ---

1. Keep configuration centralized.
2. Keep controllers thin.
3. Put business rules in services or domain objects.
4. Keep persistence logic inside repositories/data-access components.
5. Keep utilities generic and small.
6. Avoid exposing database objects directly as public API contracts.
7. Validate external input at system boundaries.
8. Enforce authorization independently from validation.
9. Do not expose internal stack traces to clients in production.
10. Do not hard-code credentials.
11. Avoid circular module dependencies.
12. Do not create abstractions without a useful reason.
13. Prefer explicit dependencies over hidden global state.
14. Test business rules independently from HTTP and database infrastructure.
15. Choose a structure that matches the scale and domain of the system.
`
    );
}


// ============================================================================
// 18. SIMPLE TEST RUNNER
// ============================================================================

async function runTest(name, testFunction) {
    try {
        await testFunction();
        console.log(`PASS: ${name}`);
        return true;
    } catch (error) {
        console.error(`FAIL: ${name}`);
        console.error(error);
        return false;
    }
}

async function runTests(config) {
    console.log("\n--- Tests ---");

    let passed = 0;
    let failed = 0;

    const tests = [
        [
            "normalizes title",
            async () => {
                const repository = new TaskRepository();

                const service = new TaskService({
                    repository,
                    config,
                });

                const task = await service.createTask(
                    1,
                    "  hello    world  "
                );

                if (task.title !== "hello world") {
                    throw new Error(
                        "Title was not normalized"
                    );
                }
            },
        ],
        [
            "rejects empty title",
            async () => {
                const repository = new TaskRepository();

                const service = new TaskService({
                    repository,
                    config,
                });

                let rejected = false;

                try {
                    await service.createTask(1, " ");
                } catch (error) {
                    rejected = error instanceof ValidationError;
                }

                if (!rejected) {
                    throw new Error(
                        "Expected ValidationError"
                    );
                }
            },
        ],
        [
            "prevents cross-owner access",
            async () => {
                const repository = new TaskRepository();

                const service = new TaskService({
                    repository,
                    config,
                });

                const task = await service.createTask(
                    10,
                    "Private"
                );

                let rejected = false;

                try {
                    await service.getTask(20, task.id);
                } catch (error) {
                    rejected =
                        error instanceof AuthorizationError;
                }

                if (!rejected) {
                    throw new Error(
                        "Expected AuthorizationError"
                    );
                }
            },
        ],
        [
            "rejects duplicate completion",
            async () => {
                const repository = new TaskRepository();

                const service = new TaskService({
                    repository,
                    config,
                });

                const task = await service.createTask(
                    10,
                    "Complete"
                );

                await service.completeTask(10, task.id);

                let rejected = false;

                try {
                    await service.completeTask(
                        10,
                        task.id
                    );
                } catch (error) {
                    rejected =
                        error instanceof ConflictError;
                }

                if (!rejected) {
                    throw new Error(
                        "Expected ConflictError"
                    );
                }
            },
        ],
    ];

    for (const [name, testFunction] of tests) {
        if (await runTest(name, testFunction)) {
            passed += 1;
        } else {
            failed += 1;
        }
    }

    console.log(
        `Tests: ${passed + failed}, Passed: ${passed}, Failed: ${failed}`
    );
}


// ============================================================================
// 19. PROGRAM ENTRY POINT
// ============================================================================

async function main() {
    console.log("=".repeat(72));
    console.log("BACKEND PROJECT STRUCTURE - JAVASCRIPT STUDY PROGRAM");
    console.log("=".repeat(72));

    const application = createApplication();

    await demonstrateAsyncFlow(application.controller);
    await demonstrateParallelOperations(application.controller);
    await demonstrateValidation(application.controller);
    await demonstrateAuthorization(application.controller);
    await demonstrateDependencyInjection(application.config);
    await demonstratePerformance();
    await runTests(application.config);

    printDesignRules();

    console.log("\nProgram complete.");
}

main().catch((error) => {
    console.error("Application startup failed:", error.message);
    process.exitCode = 1;
});
