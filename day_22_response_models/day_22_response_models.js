/*
 * FastAPI + Pydantic Response Models
 * ==================================
 *
 * This JavaScript file complements the Python implementation by showing
 * how response-model concepts appear on the consumer/application side.
 *
 * Demonstrations:
 * - JSON serialization
 * - JSON deserialization
 * - Response shaping
 * - Sensitive-field exclusion
 * - Optional-field omission
 * - Nested responses
 * - Response validation
 * - Runtime type checking
 * - Aliases
 * - Pagination
 * - Error handling
 * - Performance-aware transformation
 * - API client behavior
 *
 * Runtime:
 *     node response_models_fastapi.js
 */

"use strict";


// ============================================================================
// 1. BASIC JSON SERIALIZATION
// ============================================================================

function demonstrateJsonSerialization() {
    console.log("\n=== JSON Serialization ===");

    const user = {
        id: 1,
        username: "atul",
        email: "atul@example.com",
        isAdmin: true,
        createdAt: new Date().toISOString()
    };

    const jsonText = JSON.stringify(user);

    console.log("JavaScript object:");
    console.log(user);

    console.log("\nJSON string:");
    console.log(jsonText);

    const parsedObject = JSON.parse(jsonText);

    console.log("\nDeserialized JavaScript object:");
    console.log(parsedObject);
}


// ============================================================================
// 2. INTERNAL OBJECT VS PUBLIC RESPONSE
// ============================================================================

function toPublicUser(internalUser) {
    /*
     * This is the JavaScript equivalent of explicitly creating a public
     * response DTO/schema.
     *
     * Object destructuring prevents accidental copying of passwordHash.
     */
    const {
        id,
        username,
        email,
        isAdmin,
        createdAt
    } = internalUser;

    return {
        id,
        username,
        email,
        isAdmin,
        createdAt
    };
}


function demonstrateSensitiveFieldFiltering() {
    console.log("\n=== Sensitive Field Filtering ===");

    const internalUser = {
        id: 10,
        username: "security-user",
        email: "security@example.com",
        passwordHash: "DO-NOT-RETURN",
        isAdmin: false,
        createdAt: "2026-09-22T00:00:00Z",
        internalNote: "Private database information"
    };

    const publicUser = toPublicUser(internalUser);

    console.log("Internal object:");
    console.log(internalUser);

    console.log("\nPublic response:");
    console.log(publicUser);

    console.log("\nPassword hash present in public response:");
    console.log(Object.hasOwn(publicUser, "passwordHash"));
}


// ============================================================================
// 3. GENERIC FIELD FILTER
// ============================================================================

function pickFields(source, allowedFields) {
    const result = {};

    for (const field of allowedFields) {
        if (Object.hasOwn(source, field)) {
            result[field] = source[field];
        }
    }

    return result;
}


function demonstrateFieldSelection() {
    console.log("\n=== Generic Field Selection ===");

    const record = {
        id: 20,
        name: "Example",
        email: "example@example.com",
        passwordHash: "private",
        internalScore: 99,
        createdAt: "2026-09-22"
    };

    const publicRecord = pickFields(record, [
        "id",
        "name",
        "email",
        "createdAt"
    ]);

    console.log(publicRecord);
}


// ============================================================================
// 4. EXCLUDE NULL AND UNDEFINED
// ============================================================================

function removeNullAndUndefined(object) {
    return Object.fromEntries(
        Object.entries(object).filter(
            ([, value]) => value !== null && value !== undefined
        )
    );
}


function demonstrateOptionalFieldFiltering() {
    console.log("\n=== Optional Field Filtering ===");

    const profile = {
        id: 1,
        username: "optional-user",
        displayName: null,
        bio: undefined,
        avatarUrl: "https://example.com/avatar.png"
    };

    console.log("Original:");
    console.log(profile);

    console.log("\nWithout null/undefined fields:");
    console.log(removeNullAndUndefined(profile));
}


// ============================================================================
// 5. NESTED RESPONSE
// ============================================================================

function createCustomerResponse() {
    return {
        id: 1,
        name: "Example Customer",
        email: "customer@example.com",
        address: {
            street: "Knowledge Road",
            city: "Lucknow",
            state: "Uttar Pradesh",
            postalCode: "226001"
        }
    };
}


function demonstrateNestedResponse() {
    console.log("\n=== Nested Response ===");

    const customer = createCustomerResponse();

    console.log(JSON.stringify(customer, null, 2));

    console.log("\nNested city:");
    console.log(customer.address.city);
}


// ============================================================================
// 6. RESPONSE VALIDATION
// ============================================================================

function assertCondition(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}


function validateUserResponse(value) {
    assertCondition(
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value),
        "Response must be an object."
    );

    assertCondition(
        Number.isInteger(value.id),
        "id must be an integer."
    );

    assertCondition(
        typeof value.username === "string" &&
        value.username.length > 0,
        "username must be a non-empty string."
    );

    assertCondition(
        typeof value.email === "string" &&
        value.email.includes("@"),
        "email must contain @."
    );

    assertCondition(
        typeof value.isAdmin === "boolean",
        "isAdmin must be boolean."
    );

    return true;
}


function demonstrateResponseValidation() {
    console.log("\n=== Response Validation ===");

    const validResponse = {
        id: 1,
        username: "valid-user",
        email: "valid@example.com",
        isAdmin: false,
        createdAt: "2026-09-22T00:00:00Z"
    };

    console.log("Validating valid response:");

    try {
        validateUserResponse(validResponse);
        console.log("Valid response accepted.");
    } catch (error) {
        console.error(error.message);
    }

    const invalidResponse = {
        id: "not-an-integer",
        username: "",
        email: "invalid-email",
        isAdmin: "false"
    };

    console.log("\nValidating invalid response:");

    try {
        validateUserResponse(invalidResponse);
        console.log("Invalid response unexpectedly accepted.");
    } catch (error) {
        console.log("Rejected:", error.message);
    }
}


// ============================================================================
// 7. ARRAY RESPONSE VALIDATION
// ============================================================================

function validateUserListResponse(value) {
    assertCondition(
        Array.isArray(value),
        "Response must be an array."
    );

    value.forEach(validateUserResponse);

    return true;
}


function demonstrateArrayValidation() {
    console.log("\n=== Array Response Validation ===");

    const users = [
        {
            id: 1,
            username: "one",
            email: "one@example.com",
            isAdmin: false
        },
        {
            id: 2,
            username: "two",
            email: "two@example.com",
            isAdmin: true
        }
    ];

    validateUserListResponse(users);

    console.log("User array passed validation.");
}


// ============================================================================
// 8. DECIMAL/MONEY REPRESENTATION
// ============================================================================

function serializeMoney(amount) {
    /*
     * JavaScript Number uses IEEE-754 floating-point representation.
     * APIs dealing with exact financial values commonly use decimal strings
     * or integer minor units rather than relying on binary floating point.
     */
    return Number(amount).toFixed(2);
}


function demonstrateMoneySerialization() {
    console.log("\n=== Money Serialization ===");

    const product = {
        id: 100,
        name: "Engineering Laptop",
        price: "84999.90",
        currency: "INR",
        stockQuantity: 7
    };

    console.log("API price as received:");
    console.log(product.price);

    console.log("\nFormatted price:");
    console.log(serializeMoney(product.price));
}


// ============================================================================
// 9. COMPUTED RESPONSE FIELD
// ============================================================================

function calculateAvailability(stockQuantity) {
    if (stockQuantity === 0) {
        return "out_of_stock";
    }

    if (stockQuantity < 10) {
        return "low_stock";
    }

    return "available";
}


function createProductResponse(product) {
    return {
        ...product,
        availability: calculateAvailability(product.stockQuantity)
    };
}


function demonstrateComputedField() {
    console.log("\n=== Computed Response Field ===");

    const products = [
        {
            id: 1,
            name: "Laptop",
            price: "84999.90",
            stockQuantity: 7
        },
        {
            id: 2,
            name: "Cable",
            price: "499.00",
            stockQuantity: 0
        },
        {
            id: 3,
            name: "Monitor",
            price: "24999.00",
            stockQuantity: 50
        }
    ];

    const responses = products.map(createProductResponse);

    console.log(responses);
}


// ============================================================================
// 10. ALIAS TRANSFORMATION
// ============================================================================

function convertToApiCustomer(internalCustomer) {
    return {
        customerId: internalCustomer.id,
        fullName: internalCustomer.name,
        email: internalCustomer.email
    };
}


function demonstrateAliases() {
    console.log("\n=== API Naming Aliases ===");

    const internalCustomer = {
        id: 500,
        name: "Alias Customer",
        email: "alias@example.com"
    };

    const apiCustomer = convertToApiCustomer(internalCustomer);

    console.log(apiCustomer);
}


// ============================================================================
// 11. PAGINATED RESPONSE
// ============================================================================

function createPaginatedResponse(items, page, pageSize, total) {
    if (!Number.isInteger(page) || page < 1) {
        throw new Error("page must be an integer >= 1.");
    }

    if (
        !Number.isInteger(pageSize) ||
        pageSize < 1 ||
        pageSize > 100
    ) {
        throw new Error("pageSize must be between 1 and 100.");
    }

    if (!Number.isInteger(total) || total < 0) {
        throw new Error("total must be a non-negative integer.");
    }

    return {
        items,
        meta: {
            page,
            pageSize,
            total
        }
    };
}


function demonstratePagination() {
    console.log("\n=== Pagination ===");

    const response = createPaginatedResponse(
        [
            {
                id: 1,
                username: "one",
                email: "one@example.com",
                isAdmin: false
            }
        ],
        1,
        10,
        101
    );

    console.log(response);
}


// ============================================================================
// 12. RESPONSE ERROR MODEL
// ============================================================================

class ApiError extends Error {
    constructor(statusCode, message, details = null) {
        super(message);
        this.name = "ApiError";
        this.statusCode = statusCode;
        this.details = details;
    }

    toJSON() {
        return {
            success: false,
            error: {
                statusCode: this.statusCode,
                message: this.message,
                details: this.details
            }
        };
    }
}


function demonstrateErrorResponse() {
    console.log("\n=== Structured Error Response ===");

    const error = new ApiError(
        404,
        "User not found",
        {
            resource: "user",
            identifier: 999
        }
    );

    console.log(JSON.stringify(error, null, 2));
}


// ============================================================================
// 13. RESPONSE ENVELOPE
// ============================================================================

function createSuccessResponse(data, message = "Success") {
    return {
        success: true,
        message,
        data
    };
}


function demonstrateResponseEnvelope() {
    console.log("\n=== Response Envelope ===");

    const user = {
        id: 1,
        username: "enveloped",
        email: "enveloped@example.com",
        isAdmin: false
    };

    const response = createSuccessResponse(
        user,
        "User retrieved successfully"
    );

    console.log(response);
}


// ============================================================================
// 14. PARTIAL UPDATE RESPONSE
// ============================================================================

function createSparseUpdateResponse(source, fields) {
    return pickFields(source, fields);
}


function demonstrateSparseResponse() {
    console.log("\n=== Sparse Response ===");

    const user = {
        id: 1,
        username: "updated-user",
        email: "updated@example.com",
        displayName: "Updated Name",
        bio: "Updated biography"
    };

    const changedFields = createSparseUpdateResponse(
        user,
        ["username", "displayName"]
    );

    console.log(changedFields);
}


// ============================================================================
// 15. PERFORMANCE-AWARE FIELD SELECTION
// ============================================================================

function benchmarkFieldSelection() {
    console.log("\n=== Field Selection Performance Example ===");

    const largeObject = {};

    for (let index = 0; index < 100000; index += 1) {
        largeObject[`field${index}`] = index;
    }

    const fieldsNeeded = [
        "field1",
        "field500",
        "field1000",
        "field50000",
        "field99999"
    ];

    const start = performance.now();

    const selected = pickFields(
        largeObject,
        fieldsNeeded
    );

    const elapsed = performance.now() - start;

    console.log("Selected fields:", selected);
    console.log(`Selection time: ${elapsed.toFixed(3)} ms`);

    /*
     * Selecting a small explicit field set is generally preferable to
     * serializing a huge internal object and deleting unwanted properties
     * afterward.
     */
}


// ============================================================================
// 16. RESPONSE VALIDATION OF A TRANSACTION
// ============================================================================

function validateTransactionResponse(transaction) {
    assertCondition(
        Number.isInteger(transaction.id),
        "Transaction id must be an integer."
    );

    assertCondition(
        typeof transaction.amount === "string",
        "Transaction amount must be a decimal string."
    );

    assertCondition(
        /^\d+(\.\d{1,2})?$/.test(transaction.amount),
        "Transaction amount has an invalid decimal representation."
    );

    const allowedStatuses = new Set([
        "pending",
        "completed",
        "failed",
        "refunded"
    ]);

    assertCondition(
        allowedStatuses.has(transaction.status),
        "Transaction status is invalid."
    );

    return true;
}


function demonstrateTransactionValidation() {
    console.log("\n=== Transaction Response Validation ===");

    const transaction = {
        id: 900,
        amount: "1250.50",
        currency: "INR",
        status: "completed"
    };

    validateTransactionResponse(transaction);

    console.log("Transaction response accepted.");
}


// ============================================================================
// 17. ASYNCHRONOUS API CLIENT
// ============================================================================

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);

    let body;

    try {
        body = await response.json();
    } catch {
        throw new ApiError(
            response.status,
            "Server returned invalid JSON."
        );
    }

    if (!response.ok) {
        throw new ApiError(
            response.status,
            body?.detail ||
                body?.error?.message ||
                "API request failed.",
            body
        );
    }

    return body;
}


async function demonstrateAsyncApiClient() {
    console.log("\n=== Asynchronous API Client ===");

    console.log(
        "The function fetchJson() can consume the FastAPI endpoints."
    );

    /*
     * The request is intentionally not executed here because the Python
     * FastAPI server may not be running.
     *
     * Example:
     *
     * const user = await fetchJson(
     *     "http://127.0.0.1:8000/users/1"
     * );
     *
     * validateUserResponse(user);
     */
}


// ============================================================================
// 18. IMMUTABLE RESPONSE TRANSFORMATION
// ============================================================================

function transformUsersWithoutMutation(users) {
    return users.map((user) => ({
        id: user.id,
        username: user.username,
        email: user.email,
        isAdmin: user.isAdmin
    }));
}


function demonstrateImmutableTransformation() {
    console.log("\n=== Immutable Response Transformation ===");

    const internalUsers = [
        {
            id: 1,
            username: "one",
            email: "one@example.com",
            passwordHash: "private-one",
            isAdmin: false
        },
        {
            id: 2,
            username: "two",
            email: "two@example.com",
            passwordHash: "private-two",
            isAdmin: true
        }
    ];

    const publicUsers = transformUsersWithoutMutation(
        internalUsers
    );

    console.log("Internal:");
    console.log(internalUsers);

    console.log("\nPublic:");
    console.log(publicUsers);
}


// ============================================================================
// 19. EDGE CASES
// ============================================================================

function demonstrateEdgeCases() {
    console.log("\n=== Edge Cases ===");

    console.log("\nEmpty list:");
    console.log(
        createPaginatedResponse([], 1, 10, 0)
    );

    console.log("\nZero stock:");
    console.log(calculateAvailability(0));

    console.log("\nOne item in stock:");
    console.log(calculateAvailability(1));

    console.log("\nExactly ten items:");
    console.log(calculateAvailability(10));

    console.log("\nLarge stock:");
    console.log(calculateAvailability(1000000));

    console.log("\nInvalid pagination:");

    try {
        createPaginatedResponse([], 0, 10, 0);
    } catch (error) {
        console.log(error.message);
    }
}


// ============================================================================
// 20. COMPLETE DEMONSTRATION
// ============================================================================

async function main() {
    console.log("=".repeat(80));
    console.log("FASTAPI RESPONSE MODELS AND PYDANTIC CONCEPTS IN JAVASCRIPT");
    console.log("=".repeat(80));

    demonstrateJsonSerialization();
    demonstrateSensitiveFieldFiltering();
    demonstrateFieldSelection();
    demonstrateOptionalFieldFiltering();
    demonstrateNestedResponse();
    demonstrateResponseValidation();
    demonstrateArrayValidation();
    demonstrateMoneySerialization();
    demonstrateComputedField();
    demonstrateAliases();
    demonstratePagination();
    demonstrateErrorResponse();
    demonstrateResponseEnvelope();
    demonstrateSparseResponse();
    benchmarkFieldSelection();
    demonstrateTransactionValidation();
    await demonstrateAsyncApiClient();
    demonstrateImmutableTransformation();
    demonstrateEdgeCases();

    console.log("\n" + "=".repeat(80));
    console.log("JAVASCRIPT DEMONSTRATION COMPLETED");
    console.log("=".repeat(80));
}


main().catch((error) => {
    console.error("Unexpected application error:", error);
    process.exitCode = 1;
});
