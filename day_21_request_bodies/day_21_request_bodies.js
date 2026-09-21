/*
 * Request Bodies, JSON, Validation, Nested Objects and Optional Fields
 * ====================================================================
 *
 * This JavaScript file complements the Python/FastAPI implementation.
 *
 * It demonstrates:
 * - JSON request bodies
 * - JSON.stringify()
 * - JSON.parse()
 * - fetch()
 * - Content-Type
 * - required versus optional fields
 * - nested objects
 * - arrays of nested objects
 * - client-side validation
 * - server-style validation
 * - partial updates
 * - error handling
 * - response processing
 * - AbortController
 * - asynchronous API calls
 * - payload size and performance considerations
 *
 * Run:
 *     node request-bodies.js
 *
 * No external npm packages are required.
 */

"use strict";


// ============================================================================
// SECTION 1: BASIC JSON REQUEST BODY
// ============================================================================

function demonstrateBasicJson() {
    console.log("\n=== Basic JSON request body ===");

    const requestBody = {
        name: "Atul",
        age: 30,
        active: true,
        skills: ["Python", "JavaScript", "C++"],
        profile: {
            city: "Lucknow",
            country: "India"
        }
    };

    // JSON.stringify converts a JavaScript value into JSON text.
    const jsonText = JSON.stringify(requestBody);

    console.log("JavaScript object:", requestBody);
    console.log("JSON text:", jsonText);

    // JSON.parse converts JSON text back into JavaScript data.
    const parsedBody = JSON.parse(jsonText);

    console.log("Parsed object:", parsedBody);
    console.log("Nested city:", parsedBody.profile.city);
}


// ============================================================================
// SECTION 2: REQUIRED AND OPTIONAL FIELDS
// ============================================================================

function validateUserBody(body) {
    const errors = [];

    // JavaScript does not automatically enforce required properties.
    // The application must explicitly validate them.

    if (typeof body !== "object" || body === null || Array.isArray(body)) {
        return ["Request body must be a JSON object."];
    }

    if (!Object.hasOwn(body, "username")) {
        errors.push("username is required.");
    } else if (typeof body.username !== "string") {
        errors.push("username must be a string.");
    } else if (body.username.trim().length < 3) {
        errors.push("username must contain at least 3 characters.");
    }

    if (!Object.hasOwn(body, "email")) {
        errors.push("email is required.");
    } else if (typeof body.email !== "string") {
        errors.push("email must be a string.");
    }

    if (!Object.hasOwn(body, "age")) {
        errors.push("age is required.");
    } else if (!Number.isInteger(body.age)) {
        errors.push("age must be an integer.");
    } else if (body.age < 18 || body.age > 120) {
        errors.push("age must be between 18 and 120.");
    }

    // displayName is optional.
    if (
        Object.hasOwn(body, "displayName") &&
        body.displayName !== null &&
        typeof body.displayName !== "string"
    ) {
        errors.push("displayName must be a string or null.");
    }

    return errors;
}


function demonstrateRequiredOptional() {
    console.log("\n=== Required versus optional fields ===");

    const validUser = {
        username: "atul",
        email: "atul@example.com",
        age: 30
    };

    console.log("Valid user errors:", validateUserBody(validUser));

    const invalidUser = {
        username: "a",
        email: "not-an-email",
        age: 15
    };

    console.log("Invalid user errors:", validateUserBody(invalidUser));

    /*
     * Important JavaScript distinction:
     *
     * property absent:
     *     body.phone === undefined
     *
     * property explicitly null:
     *     body.phone === null
     *
     * These may have different meanings in an API contract.
     */

    const withoutPhone = {
        username: "atul"
    };

    const withNullPhone = {
        username: "atul",
        phone: null
    };

    console.log("Missing phone:", withoutPhone.phone);
    console.log("Null phone:", withNullPhone.phone);
}


// ============================================================================
// SECTION 3: NESTED OBJECT VALIDATION
// ============================================================================

function validateAddress(address) {
    const errors = [];

    if (typeof address !== "object" || address === null || Array.isArray(address)) {
        return ["address must be an object."];
    }

    const requiredFields = [
        "street",
        "city",
        "state",
        "postalCode"
    ];

    for (const field of requiredFields) {
        if (!Object.hasOwn(address, field)) {
            errors.push(`address.${field} is required.`);
        } else if (typeof address[field] !== "string") {
            errors.push(`address.${field} must be a string.`);
        }
    }

    return errors;
}


function validateCustomer(body) {
    const errors = validateUserBody(body);

    if (!Object.hasOwn(body, "address")) {
        errors.push("address is required.");
    } else {
        errors.push(...validateAddress(body.address));
    }

    return errors;
}


function demonstrateNestedObjects() {
    console.log("\n=== Nested objects ===");

    const customer = {
        username: "atul",
        email: "atul@example.com",
        age: 30,
        address: {
            street: "MG Road",
            city: "Lucknow",
            state: "Uttar Pradesh",
            postalCode: "226001"
        }
    };

    console.log("Customer validation:", validateCustomer(customer));
    console.log("Nested city:", customer.address.city);
}


// ============================================================================
// SECTION 4: ARRAYS OF NESTED OBJECTS
// ============================================================================

function validateOrderItem(item, index) {
    const errors = [];

    if (typeof item !== "object" || item === null || Array.isArray(item)) {
        return [`items[${index}] must be an object.`];
    }

    if (!Number.isInteger(item.productId) || item.productId <= 0) {
        errors.push(`items[${index}].productId must be a positive integer.`);
    }

    if (!Number.isInteger(item.quantity) || item.quantity <= 0) {
        errors.push(`items[${index}].quantity must be a positive integer.`);
    }

    if (
        typeof item.unitPrice !== "number" ||
        !Number.isFinite(item.unitPrice) ||
        item.unitPrice <= 0
    ) {
        errors.push(`items[${index}].unitPrice must be a positive number.`);
    }

    return errors;
}


function validateOrder(body) {
    const errors = [];

    if (!Number.isInteger(body.customerId) || body.customerId <= 0) {
        errors.push("customerId must be a positive integer.");
    }

    if (!Array.isArray(body.items)) {
        errors.push("items must be an array.");
        return errors;
    }

    if (body.items.length === 0) {
        errors.push("items must contain at least one item.");
    }

    if (body.items.length > 100) {
        errors.push("items cannot contain more than 100 elements.");
    }

    body.items.forEach((item, index) => {
        errors.push(...validateOrderItem(item, index));
    });

    return errors;
}


function calculateOrderTotal(order) {
    /*
     * JavaScript Number is a binary floating-point type.
     *
     * For a production financial system, monetary values can instead be
     * represented as integer minor units such as paise/cents, or handled
     * with a decimal arithmetic library.
     *
     * This demonstration rounds to two decimal places for display.
     */

    const total = order.items.reduce(
        (sum, item) => sum + item.quantity * item.unitPrice,
        0
    );

    return Math.round((total + Number.EPSILON) * 100) / 100;
}


function demonstrateNestedArrays() {
    console.log("\n=== Arrays of nested objects ===");

    const order = {
        customerId: 1001,
        items: [
            {
                productId: 101,
                productName: "Keyboard",
                quantity: 2,
                unitPrice: 2499
            },
            {
                productId: 102,
                productName: "Mouse",
                quantity: 1,
                unitPrice: 1299
            }
        ]
    };

    console.log("Validation:", validateOrder(order));
    console.log("Order total:", calculateOrderTotal(order));
}


// ============================================================================
// SECTION 5: NORMALIZATION
// ============================================================================

function normalizeCouponCode(couponCode) {
    if (couponCode === undefined || couponCode === null) {
        return null;
    }

    const normalized = String(couponCode).trim().toUpperCase();

    return normalized === "" ? null : normalized;
}


function demonstrateNormalization() {
    console.log("\n=== Input normalization ===");

    console.log(normalizeCouponCode(" save10 "));
    console.log(normalizeCouponCode(""));
    console.log(normalizeCouponCode(null));
    console.log(normalizeCouponCode(undefined));
}


// ============================================================================
// SECTION 6: SERVER-SIDE REQUEST PROCESSING MODEL
// ============================================================================

function processOrderRequest(rawBody) {
    /*
     * This function models the stages a backend should perform.
     *
     * 1. Parse JSON.
     * 2. Check that the root structure is valid.
     * 3. Validate required fields.
     * 4. Validate nested objects.
     * 5. Validate arrays.
     * 6. Apply normalization.
     * 7. Apply business rules.
     * 8. Construct the internal representation.
     */

    let body;

    try {
        body = typeof rawBody === "string"
            ? JSON.parse(rawBody)
            : rawBody;
    } catch {
        return {
            success: false,
            status: 400,
            errors: ["Request body contains invalid JSON."]
        };
    }

    if (
        typeof body !== "object" ||
        body === null ||
        Array.isArray(body)
    ) {
        return {
            success: false,
            status: 422,
            errors: ["Request body must be a JSON object."]
        };
    }

    const errors = validateOrder(body);

    if (errors.length > 0) {
        return {
            success: false,
            status: 422,
            errors
        };
    }

    const paymentMethod = body.paymentMethod;

    const allowedPaymentMethods = new Set([
        "card",
        "upi",
        "bank_transfer"
    ]);

    if (!allowedPaymentMethods.has(paymentMethod)) {
        errors.push("paymentMethod is invalid.");
    }

    const couponCode = normalizeCouponCode(body.couponCode);

    if (
        paymentMethod === "card" &&
        couponCode === "CASHONLY"
    ) {
        errors.push(
            "CASHONLY cannot be used with card payments."
        );
    }

    if (errors.length > 0) {
        return {
            success: false,
            status: 422,
            errors
        };
    }

    return {
        success: true,
        status: 200,
        order: {
            customerId: body.customerId,
            items: body.items,
            paymentMethod,
            couponCode,
            total: calculateOrderTotal(body)
        }
    };
}


function demonstrateRequestProcessing() {
    console.log("\n=== Request processing pipeline ===");

    const validBody = {
        customerId: 1001,
        items: [
            {
                productId: 101,
                productName: "Keyboard",
                quantity: 2,
                unitPrice: 2499
            }
        ],
        paymentMethod: "upi",
        couponCode: " save10 "
    };

    console.log(processOrderRequest(JSON.stringify(validBody)));

    console.log(
        processOrderRequest("{ invalid json")
    );

    console.log(
        processOrderRequest({
            customerId: -10,
            items: [],
            paymentMethod: "cash"
        })
    );
}


// ============================================================================
// SECTION 7: PATCH-STYLE PARTIAL UPDATES
// ============================================================================

function applyPartialUpdate(existingUser, updateBody) {
    /*
     * Only supplied properties are changed.
     *
     * This is conceptually similar to:
     *     Pydantic model_dump(exclude_unset=True)
     *
     * The server must still validate every supplied property.
     */

    const errors = [];

    if (Object.hasOwn(updateBody, "displayName")) {
        if (
            updateBody.displayName !== null &&
            typeof updateBody.displayName !== "string"
        ) {
            errors.push("displayName must be a string or null.");
        }
    }

    if (Object.hasOwn(updateBody, "age")) {
        if (
            !Number.isInteger(updateBody.age) ||
            updateBody.age < 18
        ) {
            errors.push("age must be an integer >= 18.");
        }
    }

    if (errors.length > 0) {
        return {
            success: false,
            errors
        };
    }

    const updatedUser = {
        ...existingUser,
        ...updateBody
    };

    return {
        success: true,
        user: updatedUser
    };
}


function demonstratePartialUpdate() {
    console.log("\n=== Partial update ===");

    const existingUser = {
        username: "atul",
        email: "atul@example.com",
        displayName: "Old Name",
        age: 30
    };

    console.log(
        applyPartialUpdate(
            existingUser,
            {
                displayName: "Atul Pandey"
            }
        )
    );

    console.log(
        applyPartialUpdate(
            existingUser,
            {
                age: 15
            }
        )
    );
}


// ============================================================================
// SECTION 8: FETCH REQUEST
// ============================================================================

async function sendJsonRequest(url, body) {
    /*
     * fetch() sends the request body.
     *
     * Content-Type tells the server how the body is encoded.
     *
     * JSON.stringify() is necessary because fetch expects a body
     * representation, not a JavaScript object as JSON automatically.
     */

    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify(body)
    });

    const responseText = await response.text();

    let responseData;

    try {
        responseData = JSON.parse(responseText);
    } catch {
        responseData = {
            raw: responseText
        };
    }

    if (!response.ok) {
        const error = new Error(
            `HTTP request failed with status ${response.status}`
        );

        error.status = response.status;
        error.response = responseData;

        throw error;
    }

    return responseData;
}


// ============================================================================
// SECTION 9: TIMEOUT AND ABORTING REQUESTS
// ============================================================================

async function sendRequestWithTimeout(url, body, timeoutMilliseconds = 5000) {
    const controller = new AbortController();

    const timeoutId = setTimeout(
        () => controller.abort(),
        timeoutMilliseconds
    );

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(body),
            signal: controller.signal
        });

        if (!response.ok) {
            throw new Error(`Server returned HTTP ${response.status}`);
        }

        return await response.json();
    } finally {
        clearTimeout(timeoutId);
    }
}


// ============================================================================
// SECTION 10: ERROR CLASSIFICATION
// ============================================================================

function classifyRequestError(error) {
    if (error.name === "AbortError") {
        return "The request timed out or was aborted.";
    }

    if (error instanceof TypeError) {
        return "A network or fetch-level error occurred.";
    }

    if (typeof error.status === "number") {
        if (error.status === 400) {
            return "The server rejected malformed request syntax.";
        }

        if (error.status === 422) {
            return "The server rejected the request because validation failed.";
        }

        if (error.status >= 500) {
            return "The server reported an internal error.";
        }

        return `The server returned HTTP ${error.status}.`;
    }

    return "An unexpected error occurred.";
}


// ============================================================================
// SECTION 11: EDGE CASES
// ============================================================================

function demonstrateEdgeCases() {
    console.log("\n=== Edge cases ===");

    const cases = [
        {
            name: "missing field",
            body: {
                customerId: 1001,
                items: []
            }
        },
        {
            name: "null body",
            body: null
        },
        {
            name: "array instead of object",
            body: []
        },
        {
            name: "empty items",
            body: {
                customerId: 1001,
                items: []
            }
        },
        {
            name: "negative quantity",
            body: {
                customerId: 1001,
                items: [
                    {
                        productId: 10,
                        quantity: -1,
                        unitPrice: 100
                    }
                ]
            }
        },
        {
            name: "zero price",
            body: {
                customerId: 1001,
                items: [
                    {
                        productId: 10,
                        quantity: 1,
                        unitPrice: 0
                    }
                ]
            }
        }
    ];

    for (const testCase of cases) {
        console.log(
            testCase.name,
            processOrderRequest(testCase.body)
        );
    }
}


// ============================================================================
// SECTION 12: PERFORMANCE CONSIDERATIONS
// ============================================================================

function demonstratePerformanceConsiderations() {
    console.log("\n=== Performance considerations ===");

    const largeOrder = {
        customerId: 1001,
        items: []
    };

    for (let index = 1; index <= 100; index += 1) {
        largeOrder.items.push({
            productId: index,
            productName: `Product ${index}`,
            quantity: 1,
            unitPrice: 100
        });
    }

    const start = performance.now();

    const result = processOrderRequest(largeOrder);

    const elapsed = performance.now() - start;

    console.log("Validation successful:", result.success);
    console.log("Items processed:", largeOrder.items.length);
    console.log("Processing time in this local demonstration:", `${elapsed.toFixed(3)} ms`);

    /*
     * Real production measurements should use representative payloads,
     * realistic concurrency, network latency, server hardware, and database
     * behavior. A microbenchmark like this is not an API performance test.
     */
}


// ============================================================================
// SECTION 13: SECURITY CONSIDERATIONS
// ============================================================================

function demonstrateSecurityConsiderations() {
    console.log("\n=== Security considerations ===");

    const principles = [
        "Never trust values merely because they arrived as valid JSON.",
        "Validate types, ranges, lengths, and nested structures.",
        "Use authorization checks independently from schema validation.",
        "Do not allow clients to choose privileged fields such as isAdmin.",
        "Do not trust client-supplied prices when the server owns product pricing.",
        "Limit request sizes and array lengths.",
        "Avoid exposing passwords, tokens, and internal identifiers unnecessarily.",
        "Treat unknown fields deliberately rather than accidentally.",
        "Do not log complete sensitive request bodies without a valid reason.",
        "Use HTTPS for production API traffic."
    ];

    principles.forEach((principle, index) => {
        console.log(`${index + 1}. ${principle}`);
    });
}


// ============================================================================
// SECTION 14: COMPLETE DEMONSTRATION
// ============================================================================

async function main() {
    console.log("=".repeat(80));
    console.log("JSON REQUEST BODY AND VALIDATION STUDY");
    console.log("=".repeat(80));

    demonstrateBasicJson();
    demonstrateRequiredOptional();
    demonstrateNestedObjects();
    demonstrateNestedArrays();
    demonstrateNormalization();
    demonstrateRequestProcessing();
    demonstratePartialUpdate();
    demonstrateEdgeCases();
    demonstratePerformanceConsiderations();
    demonstrateSecurityConsiderations();

    console.log("\n=== Network example ===");
    console.log(
        "sendJsonRequest(url, body) is ready to send a JSON POST request."
    );

    console.log("\n=== Timeout example ===");
    console.log(
        "sendRequestWithTimeout(url, body, 5000) uses AbortController."
    );

    console.log("\n=== Error classification example ===");
    console.log(
        classifyRequestError(
            Object.assign(
                new Error("Validation failed"),
                { status: 422 }
            )
        )
    );

    /*
     * The network functions are intentionally not called automatically.
     * Calling them would require a live server and would make this study
     * file dependent on external network state.
     */
}

main().catch((error) => {
    console.error("Unexpected program failure:", error);
    process.exitCode = 1;
});
