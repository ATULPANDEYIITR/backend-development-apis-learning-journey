/*
 * API VERSIONING
 * URL VERSIONING, HEADER VERSIONING, BACKWARD COMPATIBILITY,
 * CONTENT NEGOTIATION, DEPRECATION, AND SUNSET STRATEGY
 *
 * Executable with a modern Node.js runtime:
 *     node api-versioning.js
 *
 * This file complements the Python study implementation by emphasizing
 * JavaScript objects, maps, functional transformations, asynchronous request
 * handling, and event-driven telemetry.
 */

"use strict";

// ============================================================================
// 1. BASIC VERSION REPRESENTATION
// ============================================================================

class ApiVersion {
    constructor(major) {
        if (!Number.isInteger(major) || major < 1) {
            throw new Error("API version must be a positive integer.");
        }

        this.major = major;
    }

    toString() {
        return `v${this.major}`;
    }
}

console.log("=== API VERSIONING FUNDAMENTALS ===");

const version1 = new ApiVersion(1);
const version2 = new ApiVersion(2);

console.log("Version 1:", version1.toString());
console.log("Version 2:", version2.toString());


// ============================================================================
// 2. URL VERSIONING
// ============================================================================

function parseUrlVersion(path) {
    const normalizedPath = path.replace(/\/+$/, "");
    const match = normalizedPath.match(
        /^\/api\/v([1-9][0-9]*)\/([A-Za-z0-9_-]+)$/
    );

    if (!match) {
        throw new Error(`Invalid API path: ${path}`);
    }

    return {
        version: new ApiVersion(Number(match[1])),
        resource: match[2]
    };
}

console.log("\n=== URL VERSIONING ===");

for (const path of [
    "/api/v1/users",
    "/api/v2/users",
    "/api/v12/orders"
]) {
    const parsed = parseUrlVersion(path);
    console.log(path, "=>", parsed.version.toString(), parsed.resource);
}

try {
    parseUrlVersion("/api/users");
} catch (error) {
    console.log("Rejected invalid path:", error.message);
}


// ============================================================================
// 3. CUSTOM HEADER VERSIONING
// ============================================================================

function parseApiVersionHeader(headers) {
    const value = headers["API-Version"] ?? headers["api-version"];

    if (value === undefined) {
        throw new Error("API-Version header is required.");
    }

    if (!/^[1-9][0-9]*$/.test(String(value))) {
        throw new Error("API-Version must be a positive integer.");
    }

    return new ApiVersion(Number(value));
}

console.log("\n=== HEADER VERSIONING ===");

console.log(
    parseApiVersionHeader({ "API-Version": "2" }).toString()
);

try {
    parseApiVersionHeader({ "API-Version": "abc" });
} catch (error) {
    console.log("Rejected invalid header:", error.message);
}


// ============================================================================
// 4. MEDIA-TYPE VERSIONING
// ============================================================================

function parseAcceptVersion(acceptHeader) {
    const pattern =
        /application\/vnd\.[a-z0-9.-]+\.[a-z0-9.-]+\+json\s*;\s*version=([1-9][0-9]*)/i;

    const match = String(acceptHeader).match(pattern);

    if (!match) {
        throw new Error(
            "Accept header does not contain a supported vendor version."
        );
    }

    return new ApiVersion(Number(match[1]));
}

console.log("\n=== MEDIA-TYPE VERSIONING ===");

console.log(
    parseAcceptVersion(
        "application/vnd.example.user+json;version=2"
    ).toString()
);


// ============================================================================
// 5. DOMAIN MODEL
// ============================================================================

const user = Object.freeze({
    id: 101,
    name: "Atul Pandey",
    email: "atul@example.com",
    phone: "+91-9000000000",
    active: true,
    createdAt: "2026-01-15T10:00:00Z"
});


// ============================================================================
// 6. VERSION-SPECIFIC RESPONSE REPRESENTATIONS
// ============================================================================

function serializeUserV1(currentUser) {
    // V1 deliberately exposes the legacy "name" and "active" field names.
    return {
        id: currentUser.id,
        name: currentUser.name,
        email: currentUser.email,
        active: currentUser.active
    };
}

function serializeUserV2(currentUser) {
    // V2 changes the public schema but keeps the same internal domain object.
    const nameParts = currentUser.name.split(/\s+/, 2);

    return {
        id: currentUser.id,
        first_name: nameParts[0],
        last_name: nameParts[1] ?? "",
        email: currentUser.email,
        phone: currentUser.phone,
        is_active: currentUser.active
    };
}

function serializeUserV3(currentUser) {
    const nameParts = currentUser.name.split(/\s+/, 2);

    return {
        id: currentUser.id,
        identity: {
            firstName: nameParts[0],
            lastName: nameParts[1] ?? ""
        },
        contact: {
            email: currentUser.email,
            phone: currentUser.phone
        },
        status: currentUser.active ? "active" : "inactive",
        createdAt: currentUser.createdAt
    };
}

const serializers = new Map([
    [1, serializeUserV1],
    [2, serializeUserV2],
    [3, serializeUserV3]
]);

function serializeForVersion(version, currentUser) {
    const serializer = serializers.get(version.major);

    if (!serializer) {
        throw new Error(`Unsupported API version: ${version}`);
    }

    return serializer(currentUser);
}

console.log("\n=== VERSIONED REPRESENTATIONS ===");

for (const major of [1, 2, 3]) {
    console.log(
        `V${major}:`,
        JSON.stringify(
            serializeForVersion(new ApiVersion(major), user),
            null,
            2
        )
    );
}


// ============================================================================
// 7. BREAKING CHANGE CLASSIFICATION
// ============================================================================

function classifyChange(description, breaking) {
    return {
        description,
        breaking
    };
}

const changes = [
    classifyChange("Add optional response field", false),
    classifyChange("Add new endpoint", false),
    classifyChange("Rename response field", true),
    classifyChange("Make optional request field mandatory", true),
    classifyChange("Change the meaning of an existing field", true),
    classifyChange("Remove an existing endpoint", true)
];

console.log("\n=== CHANGE CLASSIFICATION ===");

for (const change of changes) {
    console.log(
        `${change.breaking ? "BREAKING" : "NON-BREAKING"}: ${change.description}`
    );
}


// ============================================================================
// 8. BACKWARD-COMPATIBILITY CHECK
// ============================================================================

function containsRequiredFields(payload, requiredFields) {
    return requiredFields.every(
        fieldName => Object.prototype.hasOwnProperty.call(payload, fieldName)
    );
}

const oldRequiredFields = ["id", "name", "email", "active"];

const compatiblePayload = {
    id: 101,
    name: "Atul Pandey",
    email: "atul@example.com",
    active: true,
    phone: "+91-9000000000"
};

const incompatiblePayload = {
    id: 101,
    full_name: "Atul Pandey",
    email: "atul@example.com",
    active: true
};

console.log("\n=== BACKWARD COMPATIBILITY ===");

console.log(
    "Additional field:",
    containsRequiredFields(compatiblePayload, oldRequiredFields)
);

console.log(
    "Renamed field:",
    containsRequiredFields(incompatiblePayload, oldRequiredFields)
);


// ============================================================================
// 9. VERSION-SPECIFIC REQUEST VALIDATION
// ============================================================================

function validateUserV1(payload) {
    const errors = [];

    if (typeof payload.name !== "string" || payload.name.trim() === "") {
        errors.push("name must be a non-empty string");
    }

    if (
        typeof payload.email !== "string" ||
        !payload.email.includes("@")
    ) {
        errors.push("email must be a valid-looking email");
    }

    return errors;
}

function validateUserV2(payload) {
    const errors = [];

    for (const field of ["first_name", "last_name"]) {
        if (typeof payload[field] !== "string") {
            errors.push(`${field} must be a string`);
        }
    }

    if (
        typeof payload.email !== "string" ||
        !payload.email.includes("@")
    ) {
        errors.push("email must be a valid-looking email");
    }

    return errors;
}

console.log("\n=== VERSION-SPECIFIC VALIDATION ===");

console.log(
    "V1:",
    validateUserV1({
        name: "Jane Doe",
        email: "jane@example.com"
    })
);

console.log(
    "V2:",
    validateUserV2({
        first_name: "Jane",
        last_name: "Doe",
        email: "jane@example.com"
    })
);


// ============================================================================
// 10. ADAPTER PATTERN
// ============================================================================

function adaptV1ToInternal(payload) {
    const errors = validateUserV1(payload);

    if (errors.length > 0) {
        throw new Error(errors.join("; "));
    }

    const nameParts = payload.name.trim().split(/\s+/);

    return {
        firstName: nameParts[0],
        lastName: nameParts.slice(1).join(" "),
        email: payload.email.trim().toLowerCase()
    };
}

function adaptV2ToInternal(payload) {
    const errors = validateUserV2(payload);

    if (errors.length > 0) {
        throw new Error(errors.join("; "));
    }

    return {
        firstName: payload.first_name.trim(),
        lastName: payload.last_name.trim(),
        email: payload.email.trim().toLowerCase()
    };
}

console.log("\n=== COMPATIBILITY ADAPTERS ===");

console.log(
    "V1 canonical representation:",
    adaptV1ToInternal({
        name: "Jane Doe",
        email: "JANE@EXAMPLE.COM"
    })
);

console.log(
    "V2 canonical representation:",
    adaptV2ToInternal({
        first_name: "Jane",
        last_name: "Doe",
        email: "JANE@EXAMPLE.COM"
    })
);


// ============================================================================
// 11. VERSION-NEUTRAL DOMAIN SERVICE
// ============================================================================

class UserService {
    createUser(canonicalInput) {
        if (!canonicalInput.firstName) {
            throw new Error("First name cannot be empty.");
        }

        return {
            id: 1000,
            name: `${canonicalInput.firstName} ${canonicalInput.lastName}`.trim(),
            email: canonicalInput.email,
            active: true,
            createdAt: new Date().toISOString()
        };
    }
}

const userService = new UserService();

console.log("\n=== SHARED DOMAIN SERVICE ===");

console.log(
    userService.createUser(
        adaptV1ToInternal({
            name: "Jane Doe",
            email: "jane@example.com"
        })
    )
);

console.log(
    userService.createUser(
        adaptV2ToInternal({
            first_name: "John",
            last_name: "Smith",
            email: "john@example.com"
        })
    )
);


// ============================================================================
// 12. REQUEST DISPATCH
// ============================================================================

function handleUrlVersionedRequest(request) {
    try {
        const parsed = parseUrlVersion(request.path);

        if (request.method !== "GET" || parsed.resource !== "users") {
            return {
                status: 404,
                headers: {},
                body: { error: "Endpoint not found" }
            };
        }

        const body = serializeForVersion(parsed.version, user);

        return {
            status: 200,
            headers: {
                "Content-Type": "application/json",
                "API-Version": parsed.version.toString()
            },
            body
        };
    } catch (error) {
        return {
            status: 400,
            headers: {},
            body: { error: error.message }
        };
    }
}

console.log("\n=== URL REQUEST DISPATCH ===");

console.log(
    JSON.stringify(
        handleUrlVersionedRequest({
            method: "GET",
            path: "/api/v2/users",
            headers: {}
        }),
        null,
        2
    )
);


// ============================================================================
// 13. HEADER REQUEST DISPATCH
// ============================================================================

function handleHeaderVersionedRequest(request) {
    try {
        const version = parseApiVersionHeader(request.headers);
        const body = serializeForVersion(version, user);

        return {
            status: 200,
            headers: {
                "Content-Type": "application/json",
                "API-Version": version.toString(),
                "Vary": "API-Version"
            },
            body
        };
    } catch (error) {
        return {
            status: error.message.startsWith("Unsupported")
                ? 406
                : 400,
            headers: {},
            body: {
                error: error.message
            }
        };
    }
}

console.log("\n=== HEADER REQUEST DISPATCH ===");

console.log(
    JSON.stringify(
        handleHeaderVersionedRequest({
            method: "GET",
            path: "/api/users",
            headers: {
                "API-Version": "2"
            }
        }),
        null,
        2
    )
);


// ============================================================================
// 14. VERSION CONFLICT DETECTION
// ============================================================================

function selectConsistentVersion(urlVersion, headerVersion) {
    if (
        urlVersion &&
        headerVersion &&
        urlVersion.major !== headerVersion.major
    ) {
        throw new Error(
            "URL and header versions conflict."
        );
    }

    return urlVersion ?? headerVersion;
}

console.log("\n=== VERSION CONFLICT DETECTION ===");

console.log(
    "Same version:",
    selectConsistentVersion(
        new ApiVersion(2),
        new ApiVersion(2)
    ).toString()
);

try {
    selectConsistentVersion(
        new ApiVersion(1),
        new ApiVersion(2)
    );
} catch (error) {
    console.log("Rejected conflict:", error.message);
}


// ============================================================================
// 15. ACCEPT HEADER NEGOTIATION
// ============================================================================

function parseMediaTypeVersion(acceptHeader) {
    const matches = [...String(acceptHeader).matchAll(
        /application\/vnd\.[a-z0-9.-]+\.[a-z0-9.-]+\+json\s*;\s*version=([1-9][0-9]*)/gi
    )];

    if (matches.length === 0) {
        return null;
    }

    return new ApiVersion(Number(matches[0][1]));
}

function negotiateRepresentation(acceptHeader) {
    const explicitVersion = parseMediaTypeVersion(acceptHeader);

    if (explicitVersion) {
        return explicitVersion;
    }

    if (String(acceptHeader).includes("application/json")) {
        return new ApiVersion(2);
    }

    return null;
}

console.log("\n=== ACCEPT HEADER NEGOTIATION ===");

for (const accept of [
    "application/vnd.example.user+json;version=1",
    "application/vnd.example.user+json;version=3",
    "application/json",
    "text/plain"
]) {
    const negotiated = negotiateRepresentation(accept);
    console.log(
        accept,
        "=>",
        negotiated ? negotiated.toString() : "406 Not Acceptable"
    );
}


// ============================================================================
// 16. DEPRECATION LIFECYCLE
// ============================================================================

const lifecycle = new Map([
    [
        1,
        {
            state: "deprecated",
            successor: 2,
            deprecatedAt: "2026-06-01T00:00:00Z",
            sunsetAt: "2026-12-01T00:00:00Z",
            migrationUrl: "https://example.com/docs/migrate-v1-v2"
        }
    ],
    [
        2,
        {
            state: "supported",
            successor: 3
        }
    ],
    [
        3,
        {
            state: "current",
            successor: null
        }
    ]
]);

function getDeprecationHeaders(version) {
    const policy = lifecycle.get(version.major);

    if (!policy || policy.state !== "deprecated") {
        return {};
    }

    return {
        "Deprecation": "true",
        "Sunset": policy.sunsetAt,
        "Link": `<${policy.migrationUrl}>; rel="successor-version"`
    };
}

console.log("\n=== DEPRECATION HEADERS ===");

console.log(
    getDeprecationHeaders(new ApiVersion(1))
);

console.log(
    getDeprecationHeaders(new ApiVersion(3))
);


// ============================================================================
// 17. ASYNCHRONOUS VERSION-AWARE API
// ============================================================================

function delay(milliseconds) {
    return new Promise(resolve => {
        setTimeout(resolve, milliseconds);
    });
}

async function fetchUserFromRepository(userId) {
    // This simulates asynchronous database or service access.
    await delay(5);

    if (userId !== 101) {
        throw new Error("User not found");
    }

    return user;
}

async function getVersionedUser(userId, version) {
    const currentUser = await fetchUserFromRepository(userId);
    return serializeForVersion(version, currentUser);
}

console.log("\n=== ASYNCHRONOUS VERSION-AWARE SERVICE ===");

getVersionedUser(101, new ApiVersion(3))
    .then(result => {
        console.log("Async V3:", JSON.stringify(result, null, 2));
    })
    .catch(error => {
        console.error("Async request failed:", error.message);
    });


// ============================================================================
// 18. EVENT-DRIVEN USAGE TELEMETRY
// ============================================================================

class UsageTracker {
    constructor() {
        this.events = [];
    }

    record(event) {
        this.events.push({
            ...event,
            timestamp: new Date().toISOString()
        });
    }

    countsByVersion() {
        const counts = new Map();

        for (const event of this.events) {
            counts.set(
                event.version,
                (counts.get(event.version) ?? 0) + 1
            );
        }

        return Object.fromEntries(counts);
    }

    clientsUsingVersion(version) {
        return [
            ...new Set(
                this.events
                    .filter(event => event.version === version)
                    .map(event => event.clientId)
            )
        ].sort();
    }
}

const tracker = new UsageTracker();

console.log("\n=== VERSION USAGE TELEMETRY ===");

for (const event of [
    { clientId: "client-a", version: 1, status: 200 },
    { clientId: "client-a", version: 1, status: 200 },
    { clientId: "client-b", version: 2, status: 200 },
    { clientId: "client-c", version: 3, status: 200 },
    { clientId: "client-d", version: 1, status: 200 },
    { clientId: "client-b", version: 2, status: 200 }
]) {
    tracker.record(event);
}

console.log("Counts:", tracker.countsByVersion());
console.log("V1 clients:", tracker.clientsUsingVersion(1));


// ============================================================================
// 19. CACHE KEYS
// ============================================================================

function createCacheKey(path, version) {
    /*
     * URL versioning naturally separates URLs.
     * Header versioning requires cache configuration that considers the
     * version header, commonly through Vary or an equivalent cache key.
     */
    return `${path}|API-Version=${version.major}`;
}

console.log("\n=== CACHE IDENTITY ===");

console.log(createCacheKey("/api/users", new ApiVersion(1)));
console.log(createCacheKey("/api/users", new ApiVersion(2)));


// ============================================================================
// 20. ERROR CONTRACTS
// ============================================================================

function createErrorResponse(status, code, message, version) {
    const error = {
        code,
        message
    };

    if (version.major >= 2) {
        error.version = version.toString();
    }

    return {
        status,
        body: { error }
    };
}

console.log("\n=== ERROR CONTRACTS ===");

console.log(
    JSON.stringify(
        createErrorResponse(
            400,
            "INVALID_REQUEST",
            "The supplied request is invalid.",
            new ApiVersion(2)
        ),
        null,
        2
    )
);


// ============================================================================
// 21. DEPRECATION WARNING EVENT
// ============================================================================

class DeprecationEventEmitter {
    constructor() {
        this.listeners = new Map();
    }

    on(eventName, listener) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }

        this.listeners.get(eventName).push(listener);
    }

    emit(eventName, payload) {
        for (const listener of this.listeners.get(eventName) ?? []) {
            listener(payload);
        }
    }
}

const deprecationEvents = new DeprecationEventEmitter();

deprecationEvents.on("deprecated-api-used", event => {
    console.log(
        `Deprecation event: client=${event.clientId}, version=v${event.version}`
    );
});

console.log("\n=== DEPRECATION EVENTS ===");

deprecationEvents.emit("deprecated-api-used", {
    clientId: "client-a",
    version: 1
});


// ============================================================================
// 22. VERSION-AWARE MIDDLEWARE
// ============================================================================

function versionMiddleware(request) {
    let version;

    try {
        const urlVersion = request.path.includes("/api/v")
            ? parseUrlVersion(request.path).version
            : null;

        const headerVersion =
            request.headers["API-Version"] ||
            request.headers["api-version"]
                ? parseApiVersionHeader(request.headers)
                : null;

        version = selectConsistentVersion(urlVersion, headerVersion);

        if (!version) {
            version = new ApiVersion(2);
        }

        if (!serializers.has(version.major)) {
            return {
                status: 406,
                body: {
                    error: {
                        code: "UNSUPPORTED_API_VERSION",
                        message: `Version ${version} is not supported.`
                    }
                }
            };
        }

        return {
            status: 200,
            version,
            headers: {
                "API-Version": version.toString()
            }
        };
    } catch (error) {
        return {
            status: 400,
            body: {
                error: {
                    code: "INVALID_API_VERSION",
                    message: error.message
                }
            }
        };
    }
}

console.log("\n=== VERSION MIDDLEWARE ===");

console.log(
    versionMiddleware({
        path: "/api/v2/users",
        headers: {}
    })
);

console.log(
    versionMiddleware({
        path: "/api/v1/users",
        headers: {
            "API-Version": "2"
        }
    })
);


// ============================================================================
// 23. COMPATIBILITY MATRIX
// ============================================================================

const compatibilityMatrix = {
    "add-optional-response-field": {
        oldClientReadsNewResponse: true,
        explanation: "Tolerant clients can ignore unknown fields."
    },
    "rename-response-field": {
        oldClientReadsNewResponse: false,
        explanation: "The expected field no longer exists."
    },
    "remove-response-field": {
        oldClientReadsNewResponse: false,
        explanation: "Clients requiring that field can fail."
    },
    "add-new-endpoint": {
        oldClientReadsNewResponse: true,
        explanation: "Existing clients are unaffected if old endpoints remain."
    },
    "require-new-request-field": {
        oldClientReadsNewResponse: false,
        explanation: "Old requests no longer satisfy the contract."
    }
};

console.log("\n=== COMPATIBILITY MATRIX ===");

for (const [change, details] of Object.entries(compatibilityMatrix)) {
    console.log(
        change,
        "=>",
        details.oldClientReadsNewResponse
            ? "compatible"
            : "potentially breaking"
    );
}


// ============================================================================
// 24. SIMPLE CONTRACT TESTS
// ============================================================================

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function runContractTests() {
    console.log("\n=== CONTRACT TESTS ===");

    const v1 = serializeUserV1(user);
    assert("name" in v1, "V1 must expose name");
    assert("active" in v1, "V1 must expose active");
    assert(!("first_name" in v1), "V1 must not require V2 field names");

    const v2 = serializeUserV2(user);
    assert(v2.first_name === "Atul", "V2 first_name");
    assert(v2.last_name === "Pandey", "V2 last_name");
    assert("is_active" in v2, "V2 is_active");

    const v3 = serializeUserV3(user);
    assert(v3.identity.firstName === "Atul", "V3 first name");
    assert(v3.contact.email === user.email, "V3 email");

    assert(
        createCacheKey("/api/users", new ApiVersion(1)) !==
        createCacheKey("/api/users", new ApiVersion(2)),
        "Versioned cache keys must differ"
    );

    assert(
        getDeprecationHeaders(new ApiVersion(1)).Deprecation === "true",
        "V1 should be deprecated"
    );

    console.log("All contract tests passed.");
}

runContractTests();


// ============================================================================
// 25. PRODUCTION VERSIONING GOVERNANCE MODEL
// ============================================================================

class ApiCatalog {
    constructor() {
        this.endpoints = [];
    }

    register(endpoint) {
        if (!endpoint.method || !endpoint.path) {
            throw new Error("Endpoint requires method and path.");
        }

        if (!Array.isArray(endpoint.supportedVersions)) {
            throw new Error("supportedVersions must be an array.");
        }

        this.endpoints.push({
            method: endpoint.method.toUpperCase(),
            path: endpoint.path,
            supportedVersions: [...endpoint.supportedVersions],
            deprecatedVersions: [...(endpoint.deprecatedVersions ?? [])]
        });
    }

    find(method, path) {
        return this.endpoints.find(
            endpoint =>
                endpoint.method === method.toUpperCase() &&
                endpoint.path === path
        );
    }
}

const catalog = new ApiCatalog();

catalog.register({
    method: "GET",
    path: "/api/users",
    supportedVersions: [1, 2, 3],
    deprecatedVersions: [1]
});

catalog.register({
    method: "POST",
    path: "/api/users",
    supportedVersions: [1, 2],
    deprecatedVersions: [1]
});

console.log("\n=== API CATALOG ===");

console.log(JSON.stringify(catalog.endpoints, null, 2));


// ============================================================================
// 26. SAFE DEPRECATION DECISION DATA
// ============================================================================

function buildDeprecationRecord({
    version,
    successor,
    deprecatedAt,
    sunsetAt,
    migrationUrl
}) {
    const deprecatedDate = new Date(deprecatedAt);
    const sunsetDate = new Date(sunsetAt);

    if (
        Number.isNaN(deprecatedDate.getTime()) ||
        Number.isNaN(sunsetDate.getTime())
    ) {
        throw new Error("Deprecation dates must be valid dates.");
    }

    if (sunsetDate < deprecatedDate) {
        throw new Error("Sunset cannot precede deprecation.");
    }

    return Object.freeze({
        version,
        successor,
        deprecatedAt: deprecatedDate.toISOString(),
        sunsetAt: sunsetDate.toISOString(),
        migrationUrl
    });
}

console.log("\n=== DEPRECATION RECORD ===");

console.log(
    buildDeprecationRecord({
        version: 1,
        successor: 2,
        deprecatedAt: "2026-06-01T00:00:00Z",
        sunsetAt: "2026-12-01T00:00:00Z",
        migrationUrl: "https://example.com/docs/migrate-v1-v2"
    })
);


// ============================================================================
// 27. SECURITY CHECKS
// ============================================================================

function validateSecurityBoundary(request, version) {
    /*
     * Version selection is not authentication or authorization.
     * Every version must still pass the application's security controls.
     */
    const authenticated = request.authenticated === true;

    if (!authenticated) {
        return {
            allowed: false,
            reason: "Authentication required."
        };
    }

    if (version.major < 1) {
        return {
            allowed: false,
            reason: "Invalid version."
        };
    }

    return {
        allowed: true,
        reason: "Version selection passed basic security boundary checks."
    };
}

console.log("\n=== SECURITY BOUNDARY ===");

console.log(
    validateSecurityBoundary(
        { authenticated: false },
        new ApiVersion(2)
    )
);

console.log(
    validateSecurityBoundary(
        { authenticated: true },
        new ApiVersion(2)
    )
);


// ============================================================================
// 28. PERFORMANCE COMPARISON
// ============================================================================

function measureSerialization(serializer, iterations = 10000) {
    const start = process.hrtime.bigint();

    for (let index = 0; index < iterations; index += 1) {
        serializer(user);
    }

    const elapsedNanoseconds = process.hrtime.bigint() - start;

    return Number(elapsedNanoseconds) / 1_000_000;
}

console.log("\n=== PERFORMANCE ===");

for (const [major, serializer] of serializers.entries()) {
    console.log(
        `V${major}: ${measureSerialization(serializer).toFixed(3)} ms`
    );
}

console.log(
    "Performance depends more on transformation complexity, database access,",
    "serialization, and duplicated business logic than on version parsing alone."
);


// ============================================================================
// 29. ASYNC END-TO-END REQUEST
// ============================================================================

async function processRequest(request) {
    const middlewareResult = versionMiddleware(request);

    if (middlewareResult.status !== 200) {
        return middlewareResult;
    }

    const currentUser = await fetchUserFromRepository(101);

    const response = {
        status: 200,
        headers: {
            ...middlewareResult.headers,
            "Content-Type": "application/json"
        },
        body: serializeForVersion(
            middlewareResult.version,
            currentUser
        )
    };

    const deprecation = getDeprecationHeaders(
        middlewareResult.version
    );

    Object.assign(response.headers, deprecation);

    tracker.record({
        clientId: request.clientId ?? "unknown",
        version: middlewareResult.version.major,
        status: response.status
    });

    if (deprecation.Deprecation === "true") {
        deprecationEvents.emit("deprecated-api-used", {
            clientId: request.clientId ?? "unknown",
            version: middlewareResult.version.major
        });
    }

    return response;
}

console.log("\n=== END-TO-END ASYNCHRONOUS REQUEST ===");

processRequest({
    method: "GET",
    path: "/api/v1/users",
    headers: {},
    clientId: "client-a"
})
    .then(response => {
        console.log(
            JSON.stringify(response, null, 2)
        );

        console.log(
            "\nUpdated usage telemetry:",
            tracker.countsByVersion()
        );
    })
    .catch(error => {
        console.error("Request processing error:", error.message);
    });


// ============================================================================
// 30. DESIGN PRINCIPLES
// ============================================================================

console.log(`
=== CORE DESIGN PRINCIPLES ===

1. Treat each public API version as a contract.
2. Identify breaking changes explicitly.
3. Keep public representations separate from internal domain models.
4. Use adapters when old and new schemas differ.
5. Make version selection deterministic.
6. Reject conflicting version signals rather than silently guessing.
7. Account for caching when versioning is carried in headers.
8. Keep machine-readable error codes stable where practical.
9. Instrument usage by version and client.
10. Communicate deprecation clearly.
11. Give consumers a documented migration path.
12. Retire versions only according to an explicit lifecycle policy.
13. Apply authentication, authorization, validation, and monitoring to every version.
14. Test each supported contract independently.
15. Avoid creating versions for changes that can safely remain compatible.
`);

console.log("=== PROGRAM COMPLETE ===");
