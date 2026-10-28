"use strict";

/*
 * Role-Based Access Control engine.
 *
 * The implementation deliberately separates:
 *   1. authentication,
 *   2. role membership,
 *   3. permissions,
 *   4. resource authorization,
 *   5. ownership policy,
 *   6. audit events.
 *
 * Runtime: Node.js 18+
 */

const crypto = require("node:crypto");
const EventEmitter = require("node:events");

const Action = Object.freeze({
    READ: "read",
    CREATE: "create",
    UPDATE: "update",
    DELETE: "delete",
    APPROVE: "approve",
    ADMIN: "admin"
});

const Decision = Object.freeze({
    ALLOW: "allow",
    DENY: "deny"
});

const Roles = Object.freeze({
    USER: "user",
    SUPPORT: "support",
    MANAGER: "manager",
    ADMIN: "admin"
});

class RBACError extends Error {}
class ValidationError extends RBACError {}
class AuthenticationError extends RBACError {}
class AuthorizationError extends RBACError {}

function permissionKey(resource, action) {
    if (!resource || !action) {
        throw new ValidationError("Resource and action are required");
    }
    return `${resource}:${action}`;
}

function hashPassword(password) {
    if (typeof password !== "string" || password.length < 12) {
        throw new ValidationError(
            "Password must contain at least 12 characters"
        );
    }

    const salt = crypto.randomBytes(16);
    const derived = crypto.pbkdf2Sync(
        password,
        salt,
        200000,
        32,
        "sha256"
    );

    return [
        "pbkdf2_sha256",
        "200000",
        salt.toString("hex"),
        derived.toString("hex")
    ].join("$");
}

function verifyPassword(password, storedHash) {
    try {
        const [algorithm, iterationsText, saltHex, digestHex] =
            storedHash.split("$");

        if (algorithm !== "pbkdf2_sha256") {
            return false;
        }

        const candidate = crypto.pbkdf2Sync(
            password,
            Buffer.from(saltHex, "hex"),
            Number(iterationsText),
            32,
            "sha256"
        );

        const expected = Buffer.from(digestHex, "hex");

        return (
            candidate.length === expected.length &&
            crypto.timingSafeEqual(candidate, expected)
        );
    } catch {
        return false;
    }
}

class Role {
    constructor(name) {
        if (!name) {
            throw new ValidationError("Role name is required");
        }

        this.name = name;
        this.permissions = new Set();
    }

    grant(resource, action) {
        this.permissions.add(permissionKey(resource, action));
        return this;
    }

    revoke(resource, action) {
        this.permissions.delete(permissionKey(resource, action));
        return this;
    }
}

class User {
    constructor({ id, username, passwordHash, roles = [], active = true }) {
        if (!id || !username || !passwordHash) {
            throw new ValidationError(
                "User id, username, and password hash are required"
            );
        }

        this.id = id;
        this.username = username;
        this.passwordHash = passwordHash;
        this.roles = new Set(roles);
        this.active = active;
    }
}

class Resource {
    constructor({ id, type, ownerId, sensitivity = "normal" }) {
        if (!id || !type || !ownerId) {
            throw new ValidationError(
                "Resource id, type, and ownerId are required"
            );
        }

        this.id = id;
        this.type = type;
        this.ownerId = ownerId;
        this.sensitivity = sensitivity;
    }
}

class AuthorizationRequest {
    constructor({ userId, action, resource }) {
        if (!userId || !action || !resource) {
            throw new ValidationError(
                "Authorization request is incomplete"
            );
        }

        this.userId = userId;
        this.action = action;
        this.resource = resource;
    }
}

class RBACEngine extends EventEmitter {
    constructor() {
        super();
        this.roles = new Map();
        this.users = new Map();
        this.auditEvents = [];
    }

    addRole(role) {
        if (this.roles.has(role.name)) {
            throw new ValidationError(`Role already exists: ${role.name}`);
        }

        this.roles.set(role.name, role);
    }

    addUser(user) {
        if (this.users.has(user.id)) {
            throw new ValidationError(`User already exists: ${user.id}`);
        }

        for (const role of user.roles) {
            if (!this.roles.has(role)) {
                throw new ValidationError(`Unknown role: ${role}`);
            }
        }

        this.users.set(user.id, user);
    }

    assignRole(userId, roleName) {
        const user = this.requireUser(userId);

        if (!this.roles.has(roleName)) {
            throw new ValidationError(`Unknown role: ${roleName}`);
        }

        user.roles.add(roleName);

        this.audit(
            "role-assigned",
            userId,
            `role=${roleName}`
        );
    }

    revokeRole(userId, roleName) {
        const user = this.requireUser(userId);
        user.roles.delete(roleName);

        this.audit(
            "role-revoked",
            userId,
            `role=${roleName}`
        );
    }

    authenticate(username, password) {
        for (const user of this.users.values()) {
            if (user.username !== username) {
                continue;
            }

            if (!user.active) {
                throw new AuthenticationError("Account is inactive");
            }

            if (!verifyPassword(password, user.passwordHash)) {
                throw new AuthenticationError("Invalid credentials");
            }

            this.audit("authentication", user.id, "success");
            return user;
        }

        throw new AuthenticationError("Invalid credentials");
    }

    authorize(request) {
        const user = this.requireUser(request.userId);

        if (!user.active) {
            return this.finish(
                request,
                Decision.DENY,
                "User account is inactive",
                []
            );
        }

        if (
            request.action === Action.ADMIN &&
            !user.roles.has(Roles.ADMIN)
        ) {
            return this.finish(
                request,
                Decision.DENY,
                "Administrative action requires admin role",
                []
            );
        }

        const matched = [];

        for (const roleName of user.roles) {
            const role = this.roles.get(roleName);
            if (!role) {
                continue;
            }

            const key = permissionKey(
                request.resource.type,
                request.action
            );

            if (role.permissions.has(key)) {
                matched.push(`${roleName}:${key}`);
            }
        }

        if (matched.length > 0) {
            return this.finish(
                request,
                Decision.ALLOW,
                "Explicit role permission matched",
                matched.sort()
            );
        }

        /*
         * Ownership is intentionally not converted into a role.
         * It is a separate policy because ownership depends on
         * the resource instance, not only its resource type.
         */
        const ownershipAllowed =
            request.resource.ownerId === user.id &&
            [Action.READ, Action.UPDATE].includes(request.action) &&
            ["profile", "document"].includes(request.resource.type);

        if (ownershipAllowed) {
            return this.finish(
                request,
                Decision.ALLOW,
                "Ownership policy matched",
                ["ownership-policy"]
            );
        }

        return this.finish(
            request,
            Decision.DENY,
            "No applicable permission or ownership policy",
            []
        );
    }

    finish(request, decision, reason, matched) {
        const result = Object.freeze({
            decision,
            reason,
            matchedPermissions: Object.freeze([...matched])
        });

        this.audit(
            "authorization",
            request.userId,
            `${request.action}:${request.resource.type}:${decision}:${reason}`
        );

        return result;
    }

    effectivePermissions(userId) {
        const user = this.requireUser(userId);
        const permissions = new Set();

        for (const roleName of user.roles) {
            const role = this.roles.get(roleName);
            if (!role) {
                continue;
            }

            for (const permission of role.permissions) {
                permissions.add(permission);
            }
        }

        return [...permissions].sort();
    }

    audit(event, userId, detail) {
        const record = Object.freeze({
            timestamp: new Date().toISOString(),
            event,
            userId,
            detail
        });

        this.auditEvents.push(record);
        this.emit("audit", record);
    }

    requireUser(userId) {
        const user = this.users.get(userId);

        if (!user) {
            throw new ValidationError(`Unknown user: ${userId}`);
        }

        return user;
    }
}

function buildSystem() {
    const engine = new RBACEngine();

    const userRole = new Role(Roles.USER)
        .grant("profile", Action.READ)
        .grant("profile", Action.UPDATE);

    const supportRole = new Role(Roles.SUPPORT)
        .grant("profile", Action.READ)
        .grant("ticket", Action.READ)
        .grant("ticket", Action.UPDATE);

    const managerRole = new Role(Roles.MANAGER)
        .grant("profile", Action.READ)
        .grant("ticket", Action.READ)
        .grant("ticket", Action.UPDATE)
        .grant("ticket", Action.APPROVE)
        .grant("report", Action.READ);

    const adminRole = new Role(Roles.ADMIN)
        .grant("profile", Action.READ)
        .grant("profile", Action.UPDATE)
        .grant("ticket", Action.READ)
        .grant("ticket", Action.UPDATE)
        .grant("ticket", Action.APPROVE)
        .grant("report", Action.READ)
        .grant("system", Action.ADMIN);

    for (const role of [
        userRole,
        supportRole,
        managerRole,
        adminRole
    ]) {
        engine.addRole(role);
    }

    const credentials = [
        ["u1", "alice", "UserPassword!2026", [Roles.USER]],
        ["u2", "bob", "SupportPassword!2026", [Roles.SUPPORT]],
        ["u3", "carol", "ManagerPassword!2026", [Roles.MANAGER]],
        ["u4", "david", "AdminPassword!2026", [Roles.ADMIN]]
    ];

    for (const [id, username, password, roles] of credentials) {
        engine.addUser(
            new User({
                id,
                username,
                passwordHash: hashPassword(password),
                roles
            })
        );
    }

    return engine;
}

function runTests(engine) {
    const profile = new Resource({
        id: "p-1",
        type: "profile",
        ownerId: "u1"
    });

    const ticket = new Resource({
        id: "t-1",
        type: "ticket",
        ownerId: "u2"
    });

    const systemConfig = new Resource({
        id: "s-1",
        type: "system",
        ownerId: "u4",
        sensitivity: "critical"
    });

    console.assert(
        engine.authorize(
            new AuthorizationRequest({
                userId: "u1",
                action: Action.UPDATE,
                resource: profile
            })
        ).decision === Decision.ALLOW
    );

    console.assert(
        engine.authorize(
            new AuthorizationRequest({
                userId: "u1",
                action: Action.UPDATE,
                resource: ticket
            })
        ).decision === Decision.DENY
    );

    console.assert(
        engine.authorize(
            new AuthorizationRequest({
                userId: "u2",
                action: Action.UPDATE,
                resource: ticket
            })
        ).decision === Decision.ALLOW
    );

    console.assert(
        engine.authorize(
            new AuthorizationRequest({
                userId: "u2",
                action: Action.ADMIN,
                resource: systemConfig
            })
        ).decision === Decision.DENY
    );

    console.assert(
        engine.authorize(
            new AuthorizationRequest({
                userId: "u4",
                action: Action.ADMIN,
                resource: systemConfig
            })
        ).decision === Decision.ALLOW
    );

    engine.users.get("u1").active = false;

    console.assert(
        engine.authorize(
            new AuthorizationRequest({
                userId: "u1",
                action: Action.READ,
                resource: profile
            })
        ).decision === Decision.DENY
    );

    engine.users.get("u1").active = true;
}

function main() {
    const engine = buildSystem();

    engine.on("audit", event => {
        if (event.event === "authorization") {
            console.log(
                `[AUDIT] ${event.userId} ${event.detail}`
            );
        }
    });

    runTests(engine);

    const resources = {
        profile: new Resource({
            id: "p-100",
            type: "profile",
            ownerId: "u1"
        }),
        ticket: new Resource({
            id: "t-200",
            type: "ticket",
            ownerId: "u2"
        }),
        report: new Resource({
            id: "r-300",
            type: "report",
            ownerId: "u3",
            sensitivity: "high"
        }),
        system: new Resource({
            id: "s-400",
            type: "system",
            ownerId: "u4",
            sensitivity: "critical"
        })
    };

    const requests = [
        ["u1", Action.UPDATE, resources.profile],
        ["u1", Action.UPDATE, resources.ticket],
        ["u2", Action.UPDATE, resources.ticket],
        ["u3", Action.APPROVE, resources.ticket],
        ["u3", Action.READ, resources.report],
        ["u2", Action.ADMIN, resources.system],
        ["u4", Action.ADMIN, resources.system]
    ];

    for (const [userId, action, resource] of requests) {
        const result = engine.authorize(
            new AuthorizationRequest({
                userId,
                action,
                resource
            })
        );

        console.log(
            `${userId} ${action} ${resource.type} -> ` +
            `${result.decision.toUpperCase()} (${result.reason})`
        );
    }

    console.log("\nEffective permissions for carol:");
    console.log(engine.effectivePermissions("u3"));

    console.log("\nAuthentication:");
    console.log(
        `Authenticated as ${engine.authenticate(
            "alice",
            "UserPassword!2026"
        ).username}`
    );

    try {
        engine.authenticate("alice", "wrong-password");
    } catch (error) {
        if (error instanceof AuthenticationError) {
            console.log(`Rejected login: ${error.message}`);
        } else {
            throw error;
        }
    }

    console.log(`\nAudit events recorded: ${engine.auditEvents.length}`);
}

main();
