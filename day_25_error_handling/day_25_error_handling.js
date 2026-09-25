"use strict";

/*
Error Handling in JavaScript

This file progresses from basic exceptions to custom errors, structured
application errors, asynchronous failures, HTTP-style errors, error
middleware, validation, retry classification, and a small service layer.

The file uses only standard JavaScript and Node.js APIs.
It can be executed with:

    node error_handling.js
*/

// =============================================================================
// 1. BASIC try / catch / finally
// =============================================================================

function basicTryCatch() {
    console.log("\n=== 1. Basic try / catch / finally ===");

    try {
        const result = 10 / 0;

        // JavaScript produces Infinity rather than throwing for division by zero.
        console.log("10 / 0 =", result);

        throw new Error("Demonstration error");
    } catch (error) {
        console.log("Caught:", error.name, "->", error.message);
    } finally {
        console.log("finally always executes after this try statement.");
    }
}


// =============================================================================
// 2. THROW
// =============================================================================

function validateAge(age) {
    if (typeof age !== "number" || Number.isNaN(age)) {
        throw new TypeError("age must be a valid number");
    }

    if (!Number.isInteger(age)) {
        throw new TypeError("age must be an integer");
    }

    if (age < 0 || age > 150) {
        throw new RangeError("age must be between 0 and 150");
    }

    return true;
}


function throwingErrors() {
    console.log("\n=== 2. Throwing errors ===");

    for (const age of [30, -5, "30", 200]) {
        try {
            validateAge(age);
            console.log("Accepted:", age);
        } catch (error) {
            console.log(
                "Rejected:",
                JSON.stringify(age),
                "->",
                error.name,
                "->",
                error.message
            );
        }
    }
}


// =============================================================================
// 3. BUILT-IN ERROR TYPES
// =============================================================================

function builtInErrors() {
    console.log("\n=== 3. Built-in Error types ===");

    const operations = [
        () => JSON.parse("{invalid json"),
        () => null.toString(),
        () => {
            throw new RangeError("Value is outside the supported range");
        },
    ];

    for (const operation of operations) {
        try {
            operation();
        } catch (error) {
            console.log(error.constructor.name, "->", error.message);
        }
    }
}


// =============================================================================
// 4. CUSTOM ERROR CLASSES
// =============================================================================

class ApplicationError extends Error {
    constructor(message, options = {}) {
        super(message, options);
        this.name = "ApplicationError";
        this.code = options.code ?? "APPLICATION_ERROR";
        this.statusCode = options.statusCode ?? 500;
        this.details = options.details ?? [];
    }
}


class ValidationError extends ApplicationError {
    constructor(message, details = []) {
        super(message, {
            code: "VALIDATION_ERROR",
            statusCode: 422,
            details,
        });

        this.name = "ValidationError";
    }
}


class NotFoundError extends ApplicationError {
    constructor(resource, identifier) {
        super(`${resource} ${identifier} was not found`, {
            code: "RESOURCE_NOT_FOUND",
            statusCode: 404,
            details: [
                {
                    resource,
                    identifier,
                },
            ],
        });

        this.name = "NotFoundError";
    }
}


class ConflictError extends ApplicationError {
    constructor(message, details = []) {
        super(message, {
            code: "CONFLICT",
            statusCode: 409,
            details,
        });

        this.name = "ConflictError";
    }
}


class AuthorizationError extends ApplicationError {
    constructor(message = "Access denied") {
        super(message, {
            code: "FORBIDDEN",
            statusCode: 403,
        });

        this.name = "AuthorizationError";
    }
}


function customErrors() {
    console.log("\n=== 4. Custom error classes ===");

    const errors = [
        new ValidationError("Email is invalid"),
        new NotFoundError("Customer", 999),
        new ConflictError("Username already exists"),
        new AuthorizationError(),
    ];

    for (const error of errors) {
        console.log(
            error.name,
            "|",
            error.code,
            "|",
            error.statusCode,
            "|",
            error.message
        );
    }
}


// =============================================================================
// 5. STRUCTURED ERRORS
// =============================================================================

function toStructuredError(error, requestId = "demo-request") {
    return {
        error: {
            code: error.code ?? "INTERNAL_SERVER_ERROR",
            message:
                error instanceof ApplicationError
                    ? error.message
                    : "An unexpected server error occurred.",
            status: error.statusCode ?? 500,
            requestId,
            details: error.details ?? [],
        },
    };
}


function structuredErrors() {
    console.log("\n=== 5. Structured errors ===");

    const error = new ValidationError(
        "Request validation failed",
        [
            {
                field: "email",
                code: "INVALID_FORMAT",
                message: "A valid email address is required.",
            },
            {
                field: "age",
                code: "MIN_VALUE",
                message: "Age must be at least 18.",
            },
        ]
    );

    console.log(JSON.stringify(toStructuredError(error), null, 2));
}


// =============================================================================
// 6. ERROR CAUSES
// =============================================================================

function parseInteger(value) {
    try {
        const number = Number(value);

        if (!Number.isInteger(number)) {
            throw new TypeError("Value is not an integer");
        }

        return number;
    } catch (cause) {
        // JavaScript supports the Error "cause" property for preserving
        // lower-level failure information while exposing a higher-level error.
        throw new ValidationError("Integer parsing failed", [
            {
                value,
                cause: cause.message,
            },
        ]);
    }
}


function errorCauseDemo() {
    console.log("\n=== 6. Error causes ===");

    try {
        parseInteger("abc");
    } catch (error) {
        console.log(error.name, "->", error.message);
        console.log("Structured cause:", error.details);
    }
}


// =============================================================================
// 7. ASYNCHRONOUS ERROR HANDLING
// =============================================================================

function delayedFailure() {
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            reject(
                new ApplicationError("Temporary service failure", {
                    code: "UPSTREAM_UNAVAILABLE",
                    statusCode: 503,
                })
            );
        }, 10);
    });
}


async function asynchronousErrors() {
    console.log("\n=== 7. Asynchronous errors ===");

    try {
        await delayedFailure();
    } catch (error) {
        console.log(
            "Async failure:",
            error.code,
            error.statusCode,
            error.message
        );
    }
}


// =============================================================================
// 8. PROMISE .catch()
// =============================================================================

function promiseCatchDemo() {
    console.log("\n=== 8. Promise catch ===");

    return Promise.reject(
        new ValidationError("Promise intentionally rejected")
    )
        .then(() => {
            console.log("This will not execute.");
        })
        .catch((error) => {
            console.log("Handled with .catch():", error.message);
        })
        .finally(() => {
            console.log("Promise cleanup completed.");
        });
}


// =============================================================================
// 9. VALIDATION
// =============================================================================

function validateCustomer(input) {
    const details = [];

    if (!input || typeof input !== "object") {
        throw new ValidationError("Customer must be an object");
    }

    if (
        typeof input.name !== "string" ||
        input.name.trim().length < 2
    ) {
        details.push({
            field: "name",
            code: "INVALID_NAME",
            message: "Name must contain at least two characters.",
        });
    }

    if (
        typeof input.age !== "number" ||
        !Number.isInteger(input.age) ||
        input.age < 18 ||
        input.age > 120
    ) {
        details.push({
            field: "age",
            code: "INVALID_AGE",
            message: "Age must be an integer between 18 and 120.",
        });
    }

    if (details.length > 0) {
        throw new ValidationError(
            "Customer validation failed",
            details
        );
    }

    return {
        name: input.name.trim(),
        age: input.age,
    };
}


function validationDemo() {
    console.log("\n=== 9. Validation ===");

    const inputs = [
        { name: "Atul", age: 30 },
        { name: "A", age: 12 },
        { name: "", age: 200 },
    ];

    for (const input of inputs) {
        try {
            console.log("Accepted:", validateCustomer(input));
        } catch (error) {
            console.log(
                "Rejected:",
                JSON.stringify(toStructuredError(error))
            );
        }
    }
}


// =============================================================================
// 10. HTTP-STYLE ERRORS
// =============================================================================

class HttpError extends ApplicationError {
    constructor(statusCode, code, message, details = []) {
        super(message, {
            code,
            statusCode,
            details,
        });

        this.name = "HttpError";
    }
}


function simulateHttpEndpoint(request) {
    if (!request.authorization) {
        throw new HttpError(
            401,
            "AUTHENTICATION_REQUIRED",
            "Authentication is required."
        );
    }

    if (request.authorization !== "Bearer demo-token") {
        throw new HttpError(
            403,
            "FORBIDDEN",
            "The supplied credentials are not permitted."
        );
    }

    if (request.method !== "GET") {
        throw new HttpError(
            405,
            "METHOD_NOT_ALLOWED",
            "Only GET is supported by this endpoint."
        );
    }

    return {
        status: 200,
        body: {
            data: {
                message: "Request succeeded.",
            },
        },
    };
}


function httpErrorDemo() {
    console.log("\n=== 10. HTTP-style errors ===");

    const requests = [
        {
            method: "GET",
            authorization: "",
        },
        {
            method: "GET",
            authorization: "Bearer wrong-token",
        },
        {
            method: "GET",
            authorization: "Bearer demo-token",
        },
    ];

    for (const request of requests) {
        try {
            console.log(simulateHttpEndpoint(request));
        } catch (error) {
            console.log(
                JSON.stringify(toStructuredError(error), null, 2)
            );
        }
    }
}


// =============================================================================
// 11. ERROR MAPPING
// =============================================================================

function mapErrorToHttpResponse(error, requestId) {
    if (error instanceof ValidationError) {
        return {
            status: 422,
            body: toStructuredError(error, requestId),
        };
    }

    if (error instanceof NotFoundError) {
        return {
            status: 404,
            body: toStructuredError(error, requestId),
        };
    }

    if (error instanceof ConflictError) {
        return {
            status: 409,
            body: toStructuredError(error, requestId),
        };
    }

    if (error instanceof AuthorizationError) {
        return {
            status: 403,
            body: toStructuredError(error, requestId),
        };
    }

    if (error instanceof HttpError) {
        return {
            status: error.statusCode,
            body: toStructuredError(error, requestId),
        };
    }

    // Never send internal exception messages to an untrusted client.
    return {
        status: 500,
        body: {
            error: {
                code: "INTERNAL_SERVER_ERROR",
                message: "An unexpected server error occurred.",
                requestId,
                details: [],
            },
        },
    };
}


function errorMappingDemo() {
    console.log("\n=== 11. Error-to-HTTP mapping ===");

    const errors = [
        new ValidationError("Invalid email"),
        new NotFoundError("Order", "ORD-404"),
        new ConflictError("Order already processed"),
        new Error("Database connection string should never be exposed"),
    ];

    for (const [index, error] of errors.entries()) {
        console.log(
            `Request ${index + 1}:`,
            JSON.stringify(
                mapErrorToHttpResponse(error, `req-${index + 1}`),
                null,
                2
            )
        );
    }
}


// =============================================================================
// 12. RETRY CLASSIFICATION
// =============================================================================

class RetryableError extends ApplicationError {
    constructor(message, details = []) {
        super(message, {
            code: "RETRYABLE_FAILURE",
            statusCode: 503,
            details,
        });

        this.name = "RetryableError";
    }
}


class NonRetryableError extends ApplicationError {
    constructor(message, details = []) {
        super(message, {
            code: "NON_RETRYABLE_FAILURE",
            statusCode: 400,
            details,
        });

        this.name = "NonRetryableError";
    }
}


function isRetryable(error) {
    return error instanceof RetryableError;
}


function retryDemo() {
    console.log("\n=== 12. Retry classification ===");

    const errors = [
        new RetryableError("Temporary database outage"),
        new NonRetryableError("Invalid customer identifier"),
        new ValidationError("Email is invalid"),
    ];

    for (const error of errors) {
        console.log(
            error.name,
            "-> retryable:",
            isRetryable(error)
        );
    }
}


// =============================================================================
// 13. EXPONENTIAL BACKOFF
// =============================================================================

function calculateBackoff(attempt, baseDelay = 100, maximumDelay = 5000) {
    if (!Number.isInteger(attempt) || attempt < 0) {
        throw new ValidationError("attempt must be a non-negative integer");
    }

    const delay = baseDelay * 2 ** attempt;

    // Jitter reduces synchronized retries from many clients.
    const jitter = Math.random() * baseDelay;

    return Math.min(delay + jitter, maximumDelay);
}


async function retry(operation, options = {}) {
    const maxAttempts = options.maxAttempts ?? 3;

    let attempt = 0;

    while (attempt < maxAttempts) {
        try {
            return await operation();
        } catch (error) {
            attempt += 1;

            if (!isRetryable(error) || attempt >= maxAttempts) {
                throw error;
            }

            const delay = calculateBackoff(attempt - 1);
            console.log(
                `Retry ${attempt}/${maxAttempts - 1} after ${Math.round(delay)} ms`
            );

            await new Promise((resolve) => setTimeout(resolve, delay));
        }
    }

    throw new Error("Retry loop ended unexpectedly");
}


async function retryDemoAsync() {
    console.log("\n=== 13. Retry with exponential backoff ===");

    let attempts = 0;

    try {
        const result = await retry(
            async () => {
                attempts += 1;

                if (attempts < 3) {
                    throw new RetryableError(
                        "Temporary upstream failure"
                    );
                }

                return {
                    success: true,
                    attempts,
                };
            },
            {
                maxAttempts: 4,
            }
        );

        console.log("Operation succeeded:", result);
    } catch (error) {
        console.log("Operation failed permanently:", error.message);
    }
}


// =============================================================================
// 14. SERVICE / REPOSITORY SEPARATION
// =============================================================================

class CustomerRepository {
    constructor() {
        this.customers = new Map([
            [1, { id: 1, name: "Atul", active: true }],
            [2, { id: 2, name: "Example User", active: true }],
        ]);
    }

    findById(id) {
        const customer = this.customers.get(id);

        if (!customer) {
            throw new NotFoundError("Customer", id);
        }

        return customer;
    }

    save(customer) {
        this.customers.set(customer.id, customer);
    }
}


class CustomerService {
    constructor(repository) {
        this.repository = repository;
    }

    deactivateCustomer(id) {
        const customer = this.repository.findById(id);

        if (!customer.active) {
            throw new ConflictError(
                "Customer is already inactive"
            );
        }

        customer.active = false;
        this.repository.save(customer);

        return customer;
    }
}


function serviceLayerDemo() {
    console.log("\n=== 14. Service/repository error separation ===");

    const service = new CustomerService(new CustomerRepository());

    for (const id of [1, 1, 999]) {
        try {
            console.log(
                "Result:",
                service.deactivateCustomer(id)
            );
        } catch (error) {
            console.log(
                JSON.stringify(
                    mapErrorToHttpResponse(error, `service-${id}`),
                    null,
                    2
                )
            );
        }
    }
}


// =============================================================================
// 15. GLOBAL PROCESS ERROR HANDLERS
// =============================================================================

function explainProcessHandlers() {
    console.log("\n=== 15. Node.js process-level error handling ===");

    console.log(
        "Node.js provides process-level events such as:",
        "uncaughtException and unhandledRejection."
    );

    console.log(
        "They should not replace local try/catch handling."
    );

    console.log(
        "After an uncaught exception, process state may be unsafe."
    );

    console.log(
        "Production systems should log the failure, stop safely when required,"
        + " and use an external supervisor to restart the process."
    );
}


// =============================================================================
// 16. ERROR SERIALIZATION
// =============================================================================

function serializeError(error) {
    return {
        name: error.name,
        code: error.code ?? "UNKNOWN",
        message:
            error instanceof ApplicationError
                ? error.message
                : "Unexpected internal failure",
        statusCode: error.statusCode ?? 500,
        details: error.details ?? [],
    };
}


function serializationDemo() {
    console.log("\n=== 16. Safe error serialization ===");

    const errors = [
        new ValidationError("Invalid input"),
        new Error("Sensitive internal implementation detail"),
    ];

    for (const error of errors) {
        console.log(JSON.stringify(serializeError(error), null, 2));
    }
}


// =============================================================================
// 17. PERFORMANCE CONSIDERATIONS
// =============================================================================

function performanceConsiderations() {
    console.log("\n=== 17. Performance considerations ===");

    console.log(
        "Exceptions are intended for exceptional control flow."
    );

    console.log(
        "Do not use throwing/catching repeatedly as a normal loop mechanism."
    );

    console.log(
        "Validate predictable conditions before entering expensive operations."
    );

    console.log(
        "Error construction captures stack information, which has a cost."
    );

    console.log(
        "Logging large stack traces or high-frequency failures can also be expensive."
    );
}


// =============================================================================
// 18. SECURITY CONSIDERATIONS
// =============================================================================

function securityConsiderations() {
    console.log("\n=== 18. Security considerations ===");

    const rules = [
        "Never expose passwords, tokens, API keys, or credentials in errors.",
        "Do not expose database connection strings.",
        "Do not expose internal filesystem paths unnecessarily.",
        "Do not expose stack traces to untrusted API clients.",
        "Use stable machine-readable error codes.",
        "Log diagnostic details on the server with appropriate access controls.",
        "Avoid returning raw third-party service errors directly to clients.",
        "Treat error messages as potentially sensitive output.",
    ];

    for (const rule of rules) {
        console.log("-", rule);
    }
}


// =============================================================================
// 19. MAIN
// =============================================================================

async function main() {
    basicTryCatch();
    throwingErrors();
    builtInErrors();
    customErrors();
    structuredErrors();
    errorCauseDemo();
    await asynchronousErrors();
    await promiseCatchDemo();
    validationDemo();
    httpErrorDemo();
    errorMappingDemo();
    retryDemo();
    await retryDemoAsync();
    serviceLayerDemo();
    explainProcessHandlers();
    serializationDemo();
    performanceConsiderations();
    securityConsiderations();

    console.log("\n=== Completed ===");
}


main().catch((error) => {
    /*
    This final boundary protects the top-level async function.

    It is not a substitute for handling errors where meaningful recovery,
    translation, logging, or response generation can happen.
    */
    console.error(
        "Fatal application error:",
        serializeError(error)
    );

    process.exitCode = 1;
});
