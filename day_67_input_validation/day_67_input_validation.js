"use strict";

/*
 * Input Validation Engine
 * Node.js 18+
 *
 * Demonstrates:
 * - Schema-driven validation
 * - Type and boundary checks
 * - Sanitization and normalization
 * - Malicious input detection
 * - Asynchronous request processing
 * - Rate limiting
 * - Validation policy management
 * - Safe failure handling
 */

const crypto = require("node:crypto");

class ValidationError extends Error {
    constructor(issues) {
        super("Input validation failed");
        this.name = "ValidationError";
        this.issues = issues;
    }
}

class RequestError extends Error {
    constructor(message, statusCode = 400) {
        super(message);
        this.name = "RequestError";
        this.statusCode = statusCode;
    }
}

const ValidationType = Object.freeze({
    REQUIRED: "REQUIRED",
    TYPE: "TYPE",
    FORMAT: "FORMAT",
    BOUNDARY: "BOUNDARY",
    SECURITY: "SECURITY",
    UNKNOWN_FIELD: "UNKNOWN_FIELD"
});

class Sanitizer {
    static normalize(value) {
        if (typeof value !== "string") {
            return value;
        }

        return value
            .normalize("NFC")
            .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "")
            .trim();
    }

    static escapeHtml(value) {
        const entities = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;"
        };

        return value.replace(/[&<>"']/g, char => entities[char]);
    }

    static inspect(value) {
        if (typeof value !== "string") {
            return [];
        }

        const rules = [
            {
                name: "SQL injection indicator",
                regex: /\bUNION\s+SELECT\b|\bDROP\s+TABLE\b|--\s|;\s*DELETE\b/i
            },
            {
                name: "Script injection indicator",
                regex: /<\s*script\b|javascript\s*:/i
            },
            {
                name: "Path traversal indicator",
                regex: /\.\.[/\\]/
            },
            {
                name: "Command substitution indicator",
                regex: /\$\([^)]*\)|`[^`]*`/
            },
            {
                name: "Null byte",
                regex: /\x00/
            }
        ];

        return rules
            .filter(rule => rule.regex.test(value))
            .map(rule => rule.name);
    }
}

class SchemaValidator {
    constructor(schema, options = {}) {
        this.schema = schema;
        this.rejectUnknown = options.rejectUnknown !== false;
    }

    validate(input) {
        const issues = [];
        const output = Object.create(null);

        if (
            input === null ||
            typeof input !== "object" ||
            Array.isArray(input)
        ) {
            return {
                valid: false,
                data: {},
                issues: [{
                    field: "$",
                    type: ValidationType.TYPE,
                    message: "Expected a JSON object."
                }]
            };
        }

        if (this.rejectUnknown) {
            for (const key of Object.keys(input)) {
                if (!Object.hasOwn(this.schema, key)) {
                    issues.push({
                        field: key,
                        type: ValidationType.UNKNOWN_FIELD,
                        message: "Unknown field is not permitted."
                    });
                }
            }
        }

        for (const [field, rule] of Object.entries(this.schema)) {
            if (!Object.hasOwn(input, field)) {
                if (rule.required !== false) {
                    issues.push({
                        field,
                        type: ValidationType.REQUIRED,
                        message: "Required field is missing."
                    });
                }
                continue;
            }

            let value = input[field];

            if (!this.matchesType(value, rule.type)) {
                issues.push({
                    field,
                    type: ValidationType.TYPE,
                    message: `Expected ${rule.type}.`
                });
                continue;
            }

            if (typeof value === "number" && !Number.isFinite(value)) {
                issues.push({
                    field,
                    type: ValidationType.FORMAT,
                    message: "Number must be finite."
                });
                continue;
            }

            if (rule.sanitize && typeof value === "string") {
                value = Sanitizer.normalize(value);
            }

            if (typeof value === "string") {
                if (
                    rule.minLength !== undefined &&
                    value.length < rule.minLength
                ) {
                    issues.push({
                        field,
                        type: ValidationType.BOUNDARY,
                        message: `Minimum length is ${rule.minLength}.`
                    });
                }

                if (
                    rule.maxLength !== undefined &&
                    value.length > rule.maxLength
                ) {
                    issues.push({
                        field,
                        type: ValidationType.BOUNDARY,
                        message: `Maximum length is ${rule.maxLength}.`
                    });
                }

                if (rule.pattern && !rule.pattern.test(value)) {
                    issues.push({
                        field,
                        type: ValidationType.FORMAT,
                        message: "String format is invalid."
                    });
                }

                const suspicious = Sanitizer.inspect(value);

                if (suspicious.length > 0) {
                    issues.push({
                        field,
                        type: ValidationType.SECURITY,
                        message: suspicious.join(", ")
                    });
                }
            }

            if (typeof value === "number") {
                if (
                    rule.minimum !== undefined &&
                    value < rule.minimum
                ) {
                    issues.push({
                        field,
                        type: ValidationType.BOUNDARY,
                        message: `Minimum value is ${rule.minimum}.`
                    });
                }

                if (
                    rule.maximum !== undefined &&
                    value > rule.maximum
                ) {
                    issues.push({
                        field,
                        type: ValidationType.BOUNDARY,
                        message: `Maximum value is ${rule.maximum}.`
                    });
                }
            }

            if (
                rule.allowed &&
                !rule.allowed.includes(value)
            ) {
                issues.push({
                    field,
                    type: ValidationType.FORMAT,
                    message: "Value is not permitted."
                });
            }

            if (rule.validate && !rule.validate(value)) {
                issues.push({
                    field,
                    type: ValidationType.FORMAT,
                    message: "Custom validation failed."
                });
            }

            output[field] = value;
        }

        return {
            valid: issues.length === 0,
            data: issues.length === 0 ? output : {},
            issues
        };
    }

    matchesType(value, type) {
        switch (type) {
            case "string":
                return typeof value === "string";

            case "number":
                return typeof value === "number" &&
                    Number.isFinite(value);

            case "integer":
                return Number.isSafeInteger(value);

            case "boolean":
                return typeof value === "boolean";

            case "array":
                return Array.isArray(value);

            case "object":
                return value !== null &&
                    typeof value === "object" &&
                    !Array.isArray(value);

            default:
                return false;
        }
    }
}

class SlidingWindowRateLimiter {
    constructor(maxRequests, windowMilliseconds) {
        this.maxRequests = maxRequests;
        this.windowMilliseconds = windowMilliseconds;
        this.requests = new Map();
    }

    allow(key, now = Date.now()) {
        const previous = this.requests.get(key) || [];

        const active = previous.filter(
            timestamp => now - timestamp < this.windowMilliseconds
        );

        if (active.length >= this.maxRequests) {
            this.requests.set(key, active);
            return false;
        }

        active.push(now);
        this.requests.set(key, active);

        return true;
    }

    cleanup(now = Date.now()) {
        for (const [key, timestamps] of this.requests) {
            const active = timestamps.filter(
                timestamp => now - timestamp < this.windowMilliseconds
            );

            if (active.length === 0) {
                this.requests.delete(key);
            } else {
                this.requests.set(key, active);
            }
        }
    }
}

class RegistrationService {
    constructor() {
        this.users = new Map();

        this.validator = new SchemaValidator({
            username: {
                type: "string",
                minLength: 3,
                maxLength: 20,
                sanitize: true,
                pattern: /^[A-Za-z][A-Za-z0-9_]*$/,
                validate: value => /^[A-Za-z][A-Za-z0-9_]{2,19}$/.test(value)
            },
            email: {
                type: "string",
                minLength: 6,
                maxLength: 254,
                sanitize: true,
                validate: value =>
                    /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$/.test(value)
            },
            age: {
                type: "integer",
                minimum: 18,
                maximum: 120
            },
            role: {
                type: "string",
                allowed: ["user", "analyst", "administrator"]
            },
            active: {
                type: "boolean"
            }
        });

        this.limiter = new SlidingWindowRateLimiter(5, 60_000);
    }

    async register(rawBody, clientId) {
        if (!this.limiter.allow(clientId)) {
            throw new RequestError("Rate limit exceeded.", 429);
        }

        if (typeof rawBody !== "string") {
            throw new RequestError("Request body must be text.");
        }

        if (Buffer.byteLength(rawBody, "utf8") > 16_384) {
            throw new RequestError("Request body exceeds 16 KB.");
        }

        let payload;

        try {
            payload = JSON.parse(rawBody);
        } catch {
            throw new RequestError("Malformed JSON.");
        }

        const result = this.validator.validate(payload);

        if (!result.valid) {
            throw new ValidationError(result.issues);
        }

        const { username, email, age, role, active } = result.data;

        if (this.users.has(username)) {
            throw new RequestError("Username already exists.", 409);
        }

        // Simulate asynchronous persistence.
        await new Promise(resolve => setImmediate(resolve));

        // Recheck uniqueness after asynchronous work.
        if (this.users.has(username)) {
            throw new RequestError("Username already exists.", 409);
        }

        const user = Object.freeze({
            id: crypto.randomUUID(),
            username,
            email,
            age,
            role,
            active,
            createdAt: new Date().toISOString()
        });

        this.users.set(username, user);

        return {
            status: "accepted",
            user
        };
    }
}

async function runTests() {
    const validator = new SchemaValidator({
        quantity: {
            type: "integer",
            minimum: 1,
            maximum: 100
        },
        description: {
            type: "string",
            minLength: 3,
            maxLength: 100,
            sanitize: true
        }
    });

    console.assert(
        validator.validate({
            quantity: 10,
            description: " Valid input "
        }).valid
    );

    console.assert(
        !validator.validate({
            quantity: 0,
            description: "Valid"
        }).valid
    );

    console.assert(
        !validator.validate({
            quantity: 10.5,
            description: "Valid"
        }).valid
    );

    console.assert(
        !validator.validate({
            quantity: 10,
            description: "<script>alert(1)</script>"
        }).valid
    );

    console.assert(
        !validator.validate({
            quantity: 10,
            description: "Valid",
            extra: true
        }).valid
    );

    console.assert(
        !validator.validate(null).valid
    );

    const limiter = new SlidingWindowRateLimiter(2, 1000);

    console.assert(limiter.allow("client", 1000));
    console.assert(limiter.allow("client", 1100));
    console.assert(!limiter.allow("client", 1200));
    console.assert(limiter.allow("client", 2100));

    console.log("Automated validation tests passed.");
}

async function main() {
    const service = new RegistrationService();

    const validPayload = {
        username: "secure_user",
        email: "user@example.com",
        age: 25,
        role: "analyst",
        active: true
    };

    const scenarios = [
        ["Valid request", validPayload],
        ["Invalid age", {
            ...validPayload,
            username: "invalid_age",
            age: 15
        }],
        ["Wrong data type", {
            ...validPayload,
            username: "wrong_type",
            age: "25"
        }],
        ["SQL injection", {
            ...validPayload,
            username: "sql_user",
            email: "x@example.com",
            role: "user",
            active: true,
            extra: "' UNION SELECT * FROM users --"
        }],
        ["Unknown field", {
            ...validPayload,
            username: "extra_user",
            isAdmin: true
        }],
        ["Invalid email", {
            ...validPayload,
            username: "bad_email",
            email: "invalid"
        }]
    ];

    for (const [name, payload] of scenarios) {
        console.log(`\n--- ${name} ---`);

        try {
            const result = await service.register(
                JSON.stringify(payload),
                `client-${name}`
            );

            console.log(JSON.stringify(result, null, 2));
        } catch (error) {
            if (error instanceof ValidationError) {
                console.log(
                    JSON.stringify(error.issues, null, 2)
                );
            } else {
                console.log(
                    `${error.name}: ${error.message}`
                );
            }
        }
    }

    try {
        await service.register('{"username":', "malformed-client");
    } catch (error) {
        console.log("\nMalformed JSON:", error.message);
    }

    await runTests();
}

main().catch(error => {
    console.error("Unexpected application failure:", error);
    process.exitCode = 1;
});
