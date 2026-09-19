/**
 * FastAPI Routing Companion
 *
 * This JavaScript file complements the Python FastAPI implementation by
 * demonstrating the HTTP concepts from the client side.
 *
 * It uses only built-in browser/Node.js capabilities.
 *
 * Browser:
 *   Open this file from a web page or adapt the examples to a frontend.
 *
 * Node.js:
 *   node fastapi-routing.js
 *
 * Expected FastAPI server:
 *   http://127.0.0.1:8000
 */

"use strict";

// ============================================================================
// 1. HTTP METHOD SEMANTICS
// ============================================================================

const HTTP_METHODS = {
    GET: "Retrieve a representation.",
    POST: "Create a resource or trigger an operation.",
    PUT: "Replace a resource representation.",
    PATCH: "Partially modify a resource.",
    DELETE: "Remove a resource."
};

function explainHttpMethods() {
    console.log("\nHTTP method semantics:");

    for (const [method, meaning] of Object.entries(HTTP_METHODS)) {
        console.log(`${method.padEnd(7)} -> ${meaning}`);
    }
}


// ============================================================================
// 2. URL ROUTING CONCEPTS
// ============================================================================

function buildUserUrl(baseUrl, userId) {
    // encodeURIComponent prevents special characters from being interpreted
    // as part of the URL structure.
    return `${baseUrl}/api/users/${encodeURIComponent(userId)}`;
}

function buildSearchUrl(baseUrl, query, page = 1, pageSize = 10) {
    // URLSearchParams correctly handles spaces, &, ?, and other characters.
    const parameters = new URLSearchParams({
        q: query,
        page: String(page),
        page_size: String(pageSize)
    });

    return `${baseUrl}/search?${parameters.toString()}`;
}

function demonstrateUrls() {
    const baseUrl = "http://127.0.0.1:8000";

    console.log("\nURL examples:");
    console.log(buildUserUrl(baseUrl, 42));
    console.log(buildSearchUrl(baseUrl, "fastapi routing", 2, 20));
}


// ============================================================================
// 3. GENERIC FETCH HELPER
// ============================================================================

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            Accept: "application/json",
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {})
        }
    });

    const contentType = response.headers.get("content-type") || "";

    let data = null;

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        const text = await response.text();
        data = text || null;
    }

    if (!response.ok) {
        const detail =
            typeof data === "object" && data !== null
                ? JSON.stringify(data)
                : String(data ?? "Request failed");

        throw new Error(
            `HTTP ${response.status} ${response.statusText}: ${detail}`
        );
    }

    return data;
}


// ============================================================================
// 4. GET COLLECTION
// ============================================================================

async function listUsers(baseUrl, limit = 20, offset = 0) {
    const parameters = new URLSearchParams({
        limit: String(limit),
        offset: String(offset)
    });

    return requestJson(`${baseUrl}/api/users?${parameters}`);
}


// ============================================================================
// 5. GET SINGLE RESOURCE
// ============================================================================

async function getUser(baseUrl, userId) {
    if (!Number.isInteger(userId) || userId < 1) {
        throw new TypeError("userId must be a positive integer");
    }

    return requestJson(buildUserUrl(baseUrl, userId));
}


// ============================================================================
// 6. POST
// ============================================================================

async function createUser(baseUrl, user) {
    // POST sends a representation in the request body.
    return requestJson(`${baseUrl}/api/users`, {
        method: "POST",
        body: JSON.stringify(user)
    });
}


// ============================================================================
// 7. PUT
// ============================================================================

async function replaceUser(baseUrl, userId, completeUser) {
    // PUT sends a complete replacement representation.
    return requestJson(buildUserUrl(baseUrl, userId), {
        method: "PUT",
        body: JSON.stringify(completeUser)
    });
}


// ============================================================================
// 8. PATCH
// ============================================================================

async function patchUser(baseUrl, userId, changes) {
    // PATCH sends only fields that should change.
    if (Object.keys(changes).length === 0) {
        throw new Error("PATCH requires at least one field");
    }

    return requestJson(buildUserUrl(baseUrl, userId), {
        method: "PATCH",
        body: JSON.stringify(changes)
    });
}


// ============================================================================
// 9. DELETE
// ============================================================================

async function deleteUser(baseUrl, userId) {
    const response = await fetch(buildUserUrl(baseUrl, userId), {
        method: "DELETE",
        headers: {
            Accept: "application/json"
        }
    });

    // FastAPI's DELETE endpoint returns 204 No Content, so attempting
    // response.json() would be incorrect.
    if (!response.ok) {
        const text = await response.text();
        throw new Error(
            `Delete failed: HTTP ${response.status} ${text}`
        );
    }

    return {
        deleted: true,
        status: response.status
    };
}


// ============================================================================
// 10. SAFE ERROR HANDLING
// ============================================================================

async function demonstrateErrorHandling(baseUrl) {
    try {
        await getUser(baseUrl, 999999);
    } catch (error) {
        // Network failures and HTTP failures both arrive here because the
        // requestJson helper converts non-2xx responses into exceptions.
        console.error("\nExpected request error:");
        console.error(error.message);
    }
}


// ============================================================================
// 11. PATCH MERGE SEMANTICS
// ============================================================================

function applyPatch(original, changes) {
    // Object spread creates a new object instead of mutating the original.
    // This is useful for predictable state management.
    return {
        ...original,
        ...changes
    };
}

function demonstratePatchMerge() {
    const originalUser = {
        id: 10,
        name: "Ada Lovelace",
        email: "ada@example.com",
        age: 28
    };

    const changes = {
        age: 29
    };

    const updatedUser = applyPatch(originalUser, changes);

    console.log("\nPATCH-style local merge:");
    console.log("Original:", originalUser);
    console.log("Changes:", changes);
    console.log("Updated:", updatedUser);
}


// ============================================================================
// 12. REQUEST VALIDATION
// ============================================================================

function validateUserInput(user) {
    const errors = [];

    if (typeof user.name !== "string" || user.name.trim().length < 2) {
        errors.push("name must contain at least two characters");
    }

    if (
        typeof user.email !== "string" ||
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(user.email)
    ) {
        errors.push("email must have a basic valid email format");
    }

    if (
        !Number.isInteger(user.age) ||
        user.age < 13 ||
        user.age > 120
    ) {
        errors.push("age must be an integer from 13 through 120");
    }

    return errors;
}

function demonstrateValidation() {
    const validUser = {
        name: "Alan Turing",
        email: "alan@example.com",
        age: 32
    };

    const invalidUser = {
        name: "",
        email: "invalid",
        age: 200
    };

    console.log("\nClient-side validation:");
    console.log("Valid:", validateUserInput(validUser));
    console.log("Invalid:", validateUserInput(invalidUser));
}


// ============================================================================
// 13. IDEMPOTENCY CONCEPT
// ============================================================================

function describeIdempotency() {
    console.log("\nIdempotency considerations:");

    console.log(
        "GET should be safe and idempotent when designed according to HTTP semantics."
    );

    console.log(
        "PUT is intended to be idempotent: repeating the same replacement should leave the resource in the same state."
    );

    console.log(
        "DELETE is generally designed to be idempotent even if later requests return 404."
    );

    console.log(
        "POST is generally not idempotent: repeating the same request can create multiple resources."
    );

    console.log(
        "PATCH may or may not be idempotent depending on the operation."
    );
}


// ============================================================================
// 14. ROUTE-PARAMETER ENCODING
// ============================================================================

function demonstrateParameterEncoding() {
    const rawValues = [
        "simple-id",
        "hello world",
        "A/B",
        "name?value=1",
        "100%complete"
    ];

    console.log("\nPath parameter encoding:");

    for (const value of rawValues) {
        console.log({
            original: value,
            encoded: encodeURIComponent(value)
        });
    }
}


// ============================================================================
// 15. QUERY PARAMETER EDGE CASES
// ============================================================================

function demonstrateQueryParameters() {
    const parameters = new URLSearchParams();

    parameters.set("q", "FastAPI routing & validation");
    parameters.set("page", "2");
    parameters.set("page_size", "20");

    console.log("\nEncoded query string:");
    console.log(parameters.toString());

    console.log("\nDecoded query values:");
    console.log({
        q: parameters.get("q"),
        page: Number(parameters.get("page")),
        pageSize: Number(parameters.get("page_size"))
    });
}


// ============================================================================
// 16. CONCURRENCY AND ASYNC BEHAVIOR
// ============================================================================

async function fetchMultipleUsers(baseUrl, userIds) {
    // Promise.all starts independent requests concurrently rather than
    // waiting for each request to finish before starting the next one.
    const requests = userIds.map((userId) =>
        getUser(baseUrl, userId)
    );

    return Promise.all(requests);
}

async function demonstrateConcurrentRequests(baseUrl) {
    try {
        const users = await fetchMultipleUsers(baseUrl, [1, 2]);
        console.log("\nConcurrent GET results:");
        console.log(users);
    } catch (error) {
        console.error("Concurrent request failed:", error.message);
    }
}


// ============================================================================
// 17. TIMEOUT WITH ABORTCONTROLLER
// ============================================================================

async function requestWithTimeout(url, options = {}, timeoutMs = 5000) {
    const controller = new AbortController();

    const timeoutId = setTimeout(() => {
        controller.abort();
    }, timeoutMs);

    try {
        return await requestJson(url, {
            ...options,
            signal: controller.signal
        });
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error(`Request exceeded ${timeoutMs} ms`);
        }

        throw error;
    } finally {
        clearTimeout(timeoutId);
    }
}


// ============================================================================
// 18. CRUD WORKFLOW
// ============================================================================

async function demonstrateCrudWorkflow(baseUrl) {
    const candidate = {
        name: "Grace Hopper",
        email: `grace-${Date.now()}@example.com`,
        age: 40
    };

    const validationErrors = validateUserInput(candidate);

    if (validationErrors.length > 0) {
        throw new Error(validationErrors.join("; "));
    }

    console.log("\nCRUD workflow:");

    const created = await createUser(baseUrl, candidate);
    console.log("POST created:", created);

    const createdId = created.user.id;

    const fetched = await getUser(baseUrl, createdId);
    console.log("GET fetched:", fetched);

    const replacement = {
        name: candidate.name,
        email: candidate.email,
        age: 41
    };

    const replaced = await replaceUser(
        baseUrl,
        createdId,
        replacement
    );

    console.log("PUT replaced:", replaced);

    const patched = await patchUser(
        baseUrl,
        createdId,
        { age: 42 }
    );

    console.log("PATCH changed:", patched);

    const deletion = await deleteUser(baseUrl, createdId);
    console.log("DELETE result:", deletion);
}


// ============================================================================
// 19. HTTP STATUS CODES
// ============================================================================

function explainStatusCodes() {
    const statusCodes = {
        200: "Successful request with a response body.",
        201: "Resource successfully created.",
        204: "Successful request with no response body.",
        400: "Malformed or invalid client request.",
        401: "Authentication is required or invalid.",
        403: "Authenticated client is not authorized.",
        404: "Requested resource does not exist.",
        409: "Request conflicts with current resource state.",
        422: "Request validation failed.",
        500: "Unexpected server-side failure."
    };

    console.log("\nCommon status codes:");

    for (const [code, meaning] of Object.entries(statusCodes)) {
        console.log(`${code}: ${meaning}`);
    }
}


// ============================================================================
// 20. PERFORMANCE CONSIDERATIONS
// ============================================================================

function explainPerformance() {
    console.log("\nPerformance considerations:");

    console.log(
        "HTTP routing itself is usually inexpensive compared with database, network, or external-service latency."
    );

    console.log(
        "Avoid unnecessary sequential requests when independent operations can run concurrently."
    );

    console.log(
        "Use pagination instead of returning unbounded collections."
    );

    console.log(
        "Validate input early to avoid unnecessary downstream work."
    );

    console.log(
        "Use database indexes for frequently queried resource identifiers and filters."
    );

    console.log(
        "Avoid making CPU-heavy synchronous work block an asynchronous application."
    );
}


// ============================================================================
// 21. SECURITY CONSIDERATIONS
// ============================================================================

function explainSecurity() {
    console.log("\nSecurity considerations:");

    console.log(
        "Never treat route parameters as trusted input."
    );

    console.log(
        "Validate request bodies and query parameters."
    );

    console.log(
        "Authenticate protected endpoints."
    );

    console.log(
        "Authorize access to individual resources; knowing an ID does not prove ownership."
    );

    console.log(
        "Use HTTPS in production."
    );

    console.log(
        "Avoid exposing stack traces or internal implementation details."
    );

    console.log(
        "Apply rate limiting where abuse or resource exhaustion is possible."
    );

    console.log(
        "Do not place secrets in URLs because URLs may be logged or retained."
    );
}


// ============================================================================
// 22. MAIN DEMONSTRATION
// ============================================================================

async function main() {
    const baseUrl = "http://127.0.0.1:8000";

    console.log("=".repeat(72));
    console.log("FASTAPI ROUTING JAVASCRIPT COMPANION");
    console.log("=".repeat(72));

    explainHttpMethods();
    demonstrateUrls();
    demonstratePatchMerge();
    demonstrateValidation();
    describeIdempotency();
    demonstrateParameterEncoding();
    demonstrateQueryParameters();
    explainStatusCodes();
    explainPerformance();
    explainSecurity();

    // The following calls require the FastAPI application to be running.
    // They are intentionally optional so the file remains useful as a
    // standalone study file even when the server is unavailable.

    if (process.env.RUN_API_DEMO === "true") {
        try {
            await demonstrateErrorHandling(baseUrl);
            await demonstrateConcurrentRequests(baseUrl);
            await demonstrateCrudWorkflow(baseUrl);
        } catch (error) {
            console.error("\nAPI demonstration failed:");
            console.error(error.message);
        }
    } else {
        console.log(
            "\nSet RUN_API_DEMO=true to execute requests against the FastAPI server."
        );
    }
}


main().catch((error) => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
