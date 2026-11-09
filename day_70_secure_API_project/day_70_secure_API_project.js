"use strict";

/*
 * Secure API Project
 *
 * Event-driven security gateway using Node.js standard libraries.
 * Features:
 * - Password hashing
 * - Signed bearer tokens
 * - Authentication middleware
 * - Role and permission evaluation
 * - Asynchronous request processing
 * - Sliding-window rate limiting
 * - Input validation
 * - Security event auditing
 * - Account deactivation and token revocation
 *
 * Runtime: Node.js 18+
 * No npm dependencies.
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");
const EventEmitter = require("node:events");

// -------------------------------------------------------
// Configuration
// -------------------------------------------------------

const CONFIG = Object.freeze({
    tokenLifetimeSeconds: 900,
    passwordIterations: 310000,
    rateLimit: 20,
    rateWindowMs: 60000,
    maximumBodyBytes: 16384,
    auditFile: path.join(process.cwd(), "secure-api-audit.jsonl")
});

const ROLE_PERMISSIONS = Object.freeze({
    admin: new Set([
        "users:read",
        "users:create",
        "users:update",
        "users:delete",
        "reports:read",
        "system:manage"
    ]),

    editor: new Set([
        "users:read",
        "users:update",
        "reports:read"
    ]),

    viewer: new Set([
        "users:read",
        "reports:read"
    ])
});

// -------------------------------------------------------
// Errors
// -------------------------------------------------------

class SecurityError extends Error {
    constructor(message, statusCode = 400) {
        super(message);
        this.name = this.constructor.name;
        this.statusCode = statusCode;
    }
}

class AuthenticationError extends SecurityError {
    constructor(message = "Authentication required.") {
        super(message, 401);
    }
}

class AuthorizationError extends SecurityError {
    constructor(message = "Insufficient permissions.") {
        super(message, 403);
    }
}

class ValidationError extends SecurityError {
    constructor(message) {
        super(message, 400);
    }
}

class RateLimitError extends SecurityError {
    constructor() {
        super("Request rate limit exceeded.", 429);
    }
}

// -------------------------------------------------------
// Utility Functions
// -------------------------------------------------------

function base64url(value) {
    return Buffer.from(value).toString("base64url");
}

function safeEqual(left, right) {
    const a = Buffer.from(left);
    const b = Buffer.from(right);

    return a.length === b.length &&
        crypto.timingSafeEqual(a, b);
}

function validateIdentifier(value) {
    return typeof value === "string" &&
        /^[a-zA-Z0-9_-]{3,64}$/.test(value);
}

// -------------------------------------------------------
// Password Service
// -------------------------------------------------------

class PasswordService {
    static validate(password) {
        if (
            typeof password !== "string" ||
            password.length < 12 ||
            password.length > 256 ||
            !/[A-Z]/.test(password) ||
            !/[a-z]/.test(password) ||
            !/[0-9]/.test(password) ||
            !/[^a-zA-Z0-9]/.test(password)
        ) {
            throw new ValidationError(
                "Password must contain uppercase, lowercase, " +
                "numeric and special characters and be at least 12 characters."
            );
        }
    }

    static async hash(password) {
        this.validate(password);

        const salt = crypto.randomBytes(16);

        const derivedKey = await new Promise((resolve, reject) => {
            crypto.pbkdf2(
                password,
                salt,
                CONFIG.passwordIterations,
                32,
                "sha256",
                (error, key) => {
                    if (error) reject(error);
                    else resolve(key);
                }
            );
        });

        return {
            salt: salt.toString("hex"),
            passwordHash: derivedKey.toString("hex")
        };
    }

    static async verify(password, user) {
        const derivedKey = await new Promise((resolve, reject) => {
            crypto.pbkdf2(
                password,
                Buffer.from(user.salt, "hex"),
                CONFIG.passwordIterations,
                32,
                "sha256",
                (error, key) => {
                    if (error) reject(error);
                    else resolve(key);
                }
            );
        });

        return safeEqual(
            derivedKey.toString("hex"),
            user.passwordHash
        );
    }
}

// -------------------------------------------------------
// User Repository
// -------------------------------------------------------

class UserRepository {
    constructor() {
        this.users = new Map();
        this.usernames = new Map();
    }

    async create(username, password, roles = ["viewer"]) {
        if (!validateIdentifier(username)) {
            throw new ValidationError("Invalid username.");
        }

        const normalized = username.toLowerCase();

        if (this.usernames.has(normalized)) {
            throw new ValidationError("Username already exists.");
        }

        if (
            !Array.isArray(roles) ||
            roles.length === 0 ||
            !roles.every(role => ROLE_PERMISSIONS[role])
        ) {
            throw new ValidationError("Invalid role assignment.");
        }

        const credentials = await PasswordService.hash(password);

        const user = Object.freeze({
            id: crypto.randomUUID(),
            username,
            ...credentials,
            roles: Object.freeze([...new Set(roles)]),
            active: true,
            createdAt: new Date().toISOString()
        });

        this.users.set(user.id, user);
        this.usernames.set(normalized, user.id);

        return user;
    }

    findByUsername(username) {
        const id = this.usernames.get(username.toLowerCase());
        return id ? this.users.get(id) : null;
    }

    findById(id) {
        return this.users.get(id) || null;
    }

    deactivate(id) {
        const user = this.findById(id);

        if (!user) {
            throw new ValidationError("User does not exist.");
        }

        const updated = Object.freeze({
            ...user,
            active: false
        });

        this.users.set(id, updated);

        return updated;
    }
}

// -------------------------------------------------------
// Token Service
// -------------------------------------------------------

class TokenService {
    constructor(secret) {
        if (!Buffer.isBuffer(secret) || secret.length < 32) {
            throw new Error("Signing key must contain at least 32 bytes.");
        }

        this.secret = secret;
        this.revoked = new Set();
    }

    sign(payload) {
        const encoded = base64url(
            JSON.stringify(payload)
        );

        const signature = crypto
            .createHmac("sha256", this.secret)
            .update(encoded)
            .digest("hex");

        return `${encoded}.${signature}`;
    }

    issue(user) {
        const now = Math.floor(Date.now() / 1000);

        const payload = {
            sub: user.id,
            iat: now,
            exp: now + CONFIG.tokenLifetimeSeconds,
            jti: crypto.randomUUID(),
            roles: user.roles
        };

        return {
            accessToken: this.sign(payload),
            tokenType: "Bearer",
            expiresIn: CONFIG.tokenLifetimeSeconds
        };
    }

    verify(token) {
        if (
            typeof token !== "string" ||
            token.length > 4096 ||
            this.revoked.has(token)
        ) {
            throw new AuthenticationError("Invalid or revoked token.");
        }

        const parts = token.split(".");

        if (parts.length !== 2) {
            throw new AuthenticationError("Malformed token.");
        }

        const [encoded, suppliedSignature] = parts;

        const expectedSignature = crypto
            .createHmac("sha256", this.secret)
            .update(encoded)
            .digest("hex");

        if (!safeEqual(suppliedSignature, expectedSignature)) {
            throw new AuthenticationError("Invalid token signature.");
        }

        let payload;

        try {
            payload = JSON.parse(
                Buffer.from(encoded, "base64url").toString("utf8")
            );
        } catch {
            throw new AuthenticationError("Invalid token payload.");
        }

        const now = Math.floor(Date.now() / 1000);

        if (
            !payload ||
            typeof payload !== "object" ||
            Array.isArray(payload) ||
            typeof payload.sub !== "string" ||
            typeof payload.jti !== "string" ||
            !Number.isSafeInteger(payload.iat) ||
            !Number.isSafeInteger(payload.exp) ||
            payload.exp <= now ||
            payload.iat > now + 30 ||
            payload.exp - payload.iat > CONFIG.tokenLifetimeSeconds ||
            !Array.isArray(payload.roles) ||
            !payload.roles.every(role => ROLE_PERMISSIONS[role])
        ) {
            throw new AuthenticationError("Expired or invalid token.");
        }

        return payload;
    }

    revoke(token) {
        this.verify(token);
        this.revoked.add(token);
    }
}

// -------------------------------------------------------
// Authentication
// -------------------------------------------------------

class AuthenticationService {
    constructor(users, tokens) {
        this.users = users;
        this.tokens = tokens;
        this.failures = new Map();
    }

    async login(username, password) {
        if (
            typeof username !== "string" ||
            typeof password !== "string"
        ) {
            throw new AuthenticationError("Invalid credentials.");
        }

        const key = username.toLowerCase().slice(0, 64);
        const now = Date.now();

        const history = (this.failures.get(key) || [])
            .filter(timestamp => now - timestamp < 300000);

        if (history.length >= 5) {
            throw new AuthenticationError(
                "Too many authentication attempts."
            );
        }

        const user = this.users.findByUsername(username);

        if (
            !user ||
            !user.active ||
            !(await PasswordService.verify(password, user))
        ) {
            history.push(now);
            this.failures.set(key, history);

            throw new AuthenticationError("Invalid credentials.");
        }

        this.failures.delete(key);

        return this.tokens.issue(user);
    }

    authenticate(authorizationHeader) {
        if (
            typeof authorizationHeader !== "string" ||
            !authorizationHeader.startsWith("Bearer ")
        ) {
            throw new AuthenticationError();
        }

        const token = authorizationHeader.slice(7);
        const payload = this.tokens.verify(token);
        const user = this.users.findById(payload.sub);

        if (!user || !user.active) {
            throw new AuthenticationError("Account unavailable.");
        }

        return { user, token, payload };
    }
}

// -------------------------------------------------------
// Authorization Service
// -------------------------------------------------------

class AuthorizationService {
    static getPermissions(user) {
        const permissions = new Set();

        for (const role of user.roles) {
            for (const permission of ROLE_PERMISSIONS[role] || []) {
                permissions.add(permission);
            }
        }

        return permissions;
    }

    static require(user, permission) {
        if (!user.active) {
            throw new AuthorizationError();
        }

        const permissions = this.getPermissions(user);

        if (!permissions.has(permission)) {
            throw new AuthorizationError();
        }
    }

    static canAccessResource(user, resource) {
        if (!user.active || !resource) {
            return false;
        }

        return user.id === resource.ownerId ||
            this.getPermissions(user).has("system:manage");
    }
}

// -------------------------------------------------------
// Sliding Window Rate Limiter
// -------------------------------------------------------

class RateLimiter {
    constructor(limit, windowMs) {
        this.limit = limit;
        this.windowMs = windowMs;
        this.requests = new Map();
    }

    check(clientId) {
        const now = Date.now();

        const timestamps = (
            this.requests.get(clientId) || []
        ).filter(timestamp => now - timestamp < this.windowMs);

        if (timestamps.length >= this.limit) {
            throw new RateLimitError();
        }

        timestamps.push(now);
        this.requests.set(clientId, timestamps);
    }

    cleanup() {
        const now = Date.now();

        for (const [client, timestamps] of this.requests) {
            const active = timestamps.filter(
                timestamp => now - timestamp < this.windowMs
            );

            if (active.length === 0) {
                this.requests.delete(client);
            } else {
                this.requests.set(client, active);
            }
        }
    }
}

// -------------------------------------------------------
// Request Validation
// -------------------------------------------------------

class RequestValidator {
    static validateBody(body) {
        if (
            body === null ||
            typeof body !== "object" ||
            Array.isArray(body)
        ) {
            throw new ValidationError("JSON object required.");
        }

        const serialized = JSON.stringify(body);

        if (
            Buffer.byteLength(serialized, "utf8") >
            CONFIG.maximumBodyBytes
        ) {
            throw new ValidationError("Request body too large.");
        }
    }

    static validateUser(body) {
        this.validateBody(body);

        const allowed = new Set([
            "username",
            "password",
            "email"
        ]);

        for (const key of Object.keys(body)) {
            if (!allowed.has(key)) {
                throw new ValidationError("Unexpected field.");
            }
        }

        if (!validateIdentifier(body.username)) {
            throw new ValidationError("Invalid username.");
        }

        if (
            typeof body.email !== "string" ||
            body.email.length > 254 ||
            !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email)
        ) {
            throw new ValidationError("Invalid email.");
        }

        PasswordService.validate(body.password);
    }
}

// -------------------------------------------------------
// Audit Event System
// -------------------------------------------------------

class AuditService extends EventEmitter {
    constructor(file) {
        super();
        this.file = file;
        this.queue = Promise.resolve();

        this.on("security-event", event => {
            this.queue = this.queue.then(async () => {
                const record = JSON.stringify(event) + "\n";

                await fs.appendFile(
                    this.file,
                    record,
                    { mode: 0o600 }
                );
            });
        });
    }

    record(type, userId, resource, result, details) {
        this.emit("security-event", {
            eventId: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            type,
            userId,
            resource: String(resource).slice(0, 256),
            result,
            details: String(details).slice(0, 256)
        });
    }

    async flush() {
        await this.queue;
    }
}

// -------------------------------------------------------
// Secure API Gateway
// -------------------------------------------------------

class SecureAPIGateway {
    constructor(secret) {
        this.users = new UserRepository();
        this.tokens = new TokenService(secret);

        this.authentication = new AuthenticationService(
            this.users,
            this.tokens
        );

        this.rateLimiter = new RateLimiter(
            CONFIG.rateLimit,
            CONFIG.rateWindowMs
        );

        this.audit = new AuditService(CONFIG.auditFile);
        this.resources = new Map();
    }

    async handle(request) {
        let userId = "anonymous";

        try {
            this.rateLimiter.check(request.clientId || "unknown");

            RequestValidator.validateBody(
                request.body || {}
            );

            if (
                request.method === "GET" &&
                request.path === "/health"
            ) {
                return {
                    status: 200,
                    body: { status: "healthy" }
                };
            }

            const context = this.authentication.authenticate(
                request.authorization
            );

            const { user, token } = context;
            userId = user.id;

            if (
                request.method === "GET" &&
                request.path === "/api/users"
            ) {
                AuthorizationService.require(user, "users:read");

                const users = [...this.users.users.values()]
                    .filter(item => item.active)
                    .map(item => ({
                        id: item.id,
                        username: item.username,
                        roles: item.roles
                    }));

                this.audit.record(
                    "USER_LIST",
                    userId,
                    request.path,
                    "SUCCESS",
                    "User listing accessed."
                );

                return {
                    status: 200,
                    body: { users }
                };
            }

            if (
                request.method === "GET" &&
                request.path === "/api/admin"
            ) {
                AuthorizationService.require(user, "system:manage");

                return {
                    status: 200,
                    body: { message: "Administrative access granted." }
                };
            }

            if (
                request.method === "POST" &&
                request.path === "/api/logout"
            ) {
                this.tokens.revoke(token);

                this.audit.record(
                    "LOGOUT",
                    userId,
                    request.path,
                    "SUCCESS",
                    "Access token revoked."
                );

                return {
                    status: 200,
                    body: { message: "Logged out." }
                };
            }

            this.audit.record(
                "API_ACCESS",
                userId,
                request.path,
                "DENIED",
                "Unknown route."
            );

            return {
                status: 404,
                body: { error: "Resource not found." }
            };

        } catch (error) {
            const status = error instanceof SecurityError
                ? error.statusCode
                : 500;

            this.audit.record(
                "SECURITY_FAILURE",
                userId,
                request.path || "unknown",
                "FAILURE",
                error.message
            );

            if (!(error instanceof SecurityError)) {
                console.error("Unexpected API error:", error);
            }

            return {
                status,
                body: {
                    error: error instanceof SecurityError
                        ? error.message
                        : "Internal server error."
                }
            };
        }
    }
}

// -------------------------------------------------------
// Demonstration
// -------------------------------------------------------

async function main() {
    const gateway = new SecureAPIGateway(
        crypto.randomBytes(32)
    );

    const admin = await gateway.users.create(
        "administrator",
        "AdminSecure#2026",
        ["admin"]
    );

    await gateway.users.create(
        "analyst",
        "AnalystSecure#2026",
        ["viewer"]
    );

    const adminLogin = await gateway.authentication.login(
        "administrator",
        "AdminSecure#2026"
    );

    const viewerLogin = await gateway.authentication.login(
        "analyst",
        "AnalystSecure#2026"
    );

    const adminAuthorization =
        `Bearer ${adminLogin.accessToken}`;

    const viewerAuthorization =
        `Bearer ${viewerLogin.accessToken}`;

    const health = await gateway.handle({
        method: "GET",
        path: "/health",
        clientId: "127.0.0.1",
        body: {}
    });

    const adminResponse = await gateway.handle({
        method: "GET",
        path: "/api/admin",
        authorization: adminAuthorization,
        clientId: "127.0.0.1",
        body: {}
    });

    const deniedResponse = await gateway.handle({
        method: "GET",
        path: "/api/admin",
        authorization: viewerAuthorization,
        clientId: "127.0.0.2",
        body: {}
    });

    const usersResponse = await gateway.handle({
        method: "GET",
        path: "/api/users",
        authorization: adminAuthorization,
        clientId: "127.0.0.1",
        body: {}
    });

    console.log("Health:", health);
    console.log("Admin:", adminResponse);
    console.log("Viewer:", deniedResponse);
    console.log("Users:", usersResponse);

    console.assert(health.status === 200);
    console.assert(adminResponse.status === 200);
    console.assert(deniedResponse.status === 403);
    console.assert(usersResponse.status === 200);

    const logout = await gateway.handle({
        method: "POST",
        path: "/api/logout",
        authorization: viewerAuthorization,
        clientId: "127.0.0.2",
        body: {}
    });

    console.assert(logout.status === 200);

    const revoked = await gateway.handle({
        method: "GET",
        path: "/api/users",
        authorization: viewerAuthorization,
        clientId: "127.0.0.2",
        body: {}
    });

    console.assert(revoked.status === 401);

    gateway.users.deactivate(admin.id);

    const inactive = await gateway.handle({
        method: "GET",
        path: "/api/admin",
        authorization: adminAuthorization,
        clientId: "127.0.0.1",
        body: {}
    });

    console.assert(inactive.status === 401);

    await gateway.audit.flush();

    console.log("All security checks completed.");
}

main().catch(error => {
    console.error("Application startup failed:", error);
    process.exitCode = 1;
});
