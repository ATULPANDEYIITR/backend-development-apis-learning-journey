"use strict";

/*
 * Event-driven API key lifecycle manager.
 * Requires Node.js 18 or later. Uses only built-in modules.
 */

const {
    createHmac,
    randomBytes,
    timingSafeEqual
} = require("node:crypto");

const { EventEmitter } = require("node:events");

const TOKEN_PREFIX = "ak_live_";
const TOKEN_PATTERN = /^ak_live_([a-f0-9]{16})\.([A-Za-z0-9_-]{43})$/;
const SCOPE_PATTERN = /^[a-z][a-z0-9:_-]{0,63}$/;
const MAX_LIFETIME_MS = 365 * 24 * 60 * 60 * 1000;

class APIKeyError extends Error {
    constructor(message, code) {
        super(message);
        this.name = "APIKeyError";
        this.code = code;
    }
}

class ValidationError extends APIKeyError {
    constructor(message) {
        super(message, "VALIDATION_ERROR");
        this.name = "ValidationError";
    }
}

class KeyNotFoundError extends APIKeyError {
    constructor() {
        super("The requested key was not found.", "KEY_NOT_FOUND");
        this.name = "KeyNotFoundError";
    }
}

class KeyStateError extends APIKeyError {
    constructor(message) {
        super(message, "INVALID_KEY_STATE");
        this.name = "KeyStateError";
    }
}

/*
 * Serializes state-changing operations. This prevents rotation and
 * revocation from interleaving across asynchronous callers.
 */
class AsyncMutex {
    #tail = Promise.resolve();

    async runExclusive(operation) {
        const previous = this.#tail;
        let release;

        this.#tail = new Promise(resolve => {
            release = resolve;
        });

        await previous;

        try {
            return operation();
        } finally {
            release();
        }
    }
}

class APIKeyVault extends EventEmitter {
    #records = new Map();
    #events = [];
    #pepper;
    #mutex = new AsyncMutex();
    #clock;
    #ownerPolicies;

    constructor({
        pepper = randomBytes(32),
        clock = () => Date.now(),
        ownerPolicies = {}
    } = {}) {
        super();

        if (!Buffer.isBuffer(pepper) || pepper.length < 32) {
            throw new ValidationError("The pepper must contain at least 32 bytes.");
        }

        if (typeof clock !== "function") {
            throw new ValidationError("clock must be a function.");
        }

        this.#pepper = Buffer.from(pepper);
        this.#clock = clock;

        this.#ownerPolicies = new Map(
            Object.entries(ownerPolicies).map(([owner, scopes]) => [
                owner,
                new Set(scopes)
            ])
        );
    }

    #validateText(value, field, maximum = 120) {
        if (
            typeof value !== "string" ||
            value.trim().length === 0 ||
            value.trim().length > maximum
        ) {
            throw new ValidationError(
                `${field} must contain 1 to ${maximum} characters.`
            );
        }

        return value.trim();
    }

    #normalizeScopes(scopes) {
        if (!Array.isArray(scopes) || scopes.length === 0) {
            throw new ValidationError("At least one scope is required.");
        }

        const normalized = new Set(scopes);

        for (const scope of normalized) {
            if (typeof scope !== "string" || !SCOPE_PATTERN.test(scope)) {
                throw new ValidationError(`Invalid scope: ${String(scope)}`);
            }
        }

        return normalized;
    }

    #checkOwnerPolicy(owner, scopes) {
        const allowed = this.#ownerPolicies.get(owner);

        if (!allowed) {
            return;
        }

        for (const scope of scopes) {
            if (!allowed.has(scope) && !allowed.has("*")) {
                throw new ValidationError(
                    `Owner ${owner} is not permitted to receive scope ${scope}.`
                );
            }
        }
    }

    #digest(secret) {
        return createHmac("sha256", this.#pepper)
            .update(secret, "utf8")
            .digest();
    }

    #parseToken(token) {
        if (typeof token !== "string") {
            return null;
        }

        const match = TOKEN_PATTERN.exec(token);

        if (!match) {
            return null;
        }

        return {
            keyId: match[1],
            secret: match[2]
        };
    }

    #newMaterial() {
        const keyId = randomBytes(8).toString("hex");
        const secret = randomBytes(32).toString("base64url");

        return {
            keyId,
            token: `${TOKEN_PREFIX}${keyId}.${secret}`,
            digest: this.#digest(secret)
        };
    }

    #expiration(lifetimeMs) {
        if (lifetimeMs === null || lifetimeMs === undefined) {
            return null;
        }

        if (
            !Number.isSafeInteger(lifetimeMs) ||
            lifetimeMs <= 0 ||
            lifetimeMs > MAX_LIFETIME_MS
        ) {
            throw new ValidationError(
                "Lifetime must be a positive integer no greater than 365 days."
            );
        }

        return this.#clock() + lifetimeMs;
    }

    #recordEvent(type, record, actor, details = {}) {
        const event = Object.freeze({
            type,
            keyId: record.keyId,
            owner: record.owner,
            actor,
            timestamp: new Date(this.#clock()).toISOString(),
            details: Object.freeze({ ...details })
        });

        // Event payloads deliberately exclude tokens and verifier bytes.
        this.#events.push(event);
        this.emit("key-event", event);
    }

    #createRecord({
        owner,
        label,
        scopes,
        lifetimeMs,
        actor,
        rotatedFrom = null
    }) {
        const material = this.#newMaterial();
        const now = this.#clock();

        const record = {
            keyId: material.keyId,
            owner,
            label,
            digest: material.digest,
            scopes: new Set(scopes),
            status: "active",
            createdAt: now,
            expiresAt: this.#expiration(lifetimeMs),
            lastUsedAt: null,
            revokedAt: null,
            rotatedFrom
        };

        this.#records.set(record.keyId, record);

        this.#recordEvent("issued", record, actor, {
            rotatedFrom
        });

        // The plaintext token is returned once and is never stored.
        return Object.freeze({
            keyId: material.keyId,
            token: material.token
        });
    }

    async issue({
        owner,
        label,
        scopes,
        lifetimeMs = 90 * 24 * 60 * 60 * 1000,
        actor = "system"
    }) {
        owner = this.#validateText(owner, "owner");
        label = this.#validateText(label, "label");
        actor = this.#validateText(actor, "actor");

        const normalizedScopes = this.#normalizeScopes(scopes);
        this.#checkOwnerPolicy(owner, normalizedScopes);

        return this.#mutex.runExclusive(() => {
            return this.#createRecord({
                owner,
                label,
                scopes: normalizedScopes,
                lifetimeMs,
                actor
            });
        });
    }

    async validate(token, requiredScope) {
        if (
            typeof requiredScope !== "string" ||
            !SCOPE_PATTERN.test(requiredScope)
        ) {
            return Object.freeze({
                accepted: false,
                reason: "invalid_scope"
            });
        }

        const parsed = this.#parseToken(token);

        if (!parsed) {
            return Object.freeze({
                accepted: false,
                reason: "malformed_token"
            });
        }

        return this.#mutex.runExclusive(() => {
            const record = this.#records.get(parsed.keyId);

            if (!record) {
                return Object.freeze({
                    accepted: false,
                    reason: "invalid_credentials"
                });
            }

            const candidate = this.#digest(parsed.secret);

            if (!timingSafeEqual(candidate, record.digest)) {
                return Object.freeze({
                    accepted: false,
                    reason: "invalid_credentials"
                });
            }

            if (record.status !== "active") {
                return Object.freeze({
                    accepted: false,
                    reason: "revoked"
                });
            }

            const now = this.#clock();

            if (record.expiresAt !== null && record.expiresAt <= now) {
                return Object.freeze({
                    accepted: false,
                    reason: "expired"
                });
            }

            if (
                !record.scopes.has(requiredScope) &&
                !record.scopes.has("*")
            ) {
                return Object.freeze({
                    accepted: false,
                    reason: "insufficient_scope",
                    keyId: record.keyId
                });
            }

            record.lastUsedAt = now;

            return Object.freeze({
                accepted: true,
                reason: "accepted",
                keyId: record.keyId,
                owner: record.owner,
                scopes: Object.freeze([...record.scopes].sort())
            });
        });
    }

    async rotate(token, actor, lifetimeMs = undefined) {
        actor = this.#validateText(actor, "actor");

        const parsed = this.#parseToken(token);

        if (!parsed) {
            throw new ValidationError("The supplied token is malformed.");
        }

        return this.#mutex.runExclusive(() => {
            const oldRecord = this.#records.get(parsed.keyId);

            if (!oldRecord) {
                throw new KeyNotFoundError();
            }

            const candidate = this.#digest(parsed.secret);

            if (!timingSafeEqual(candidate, oldRecord.digest)) {
                throw new KeyNotFoundError();
            }

            if (oldRecord.status !== "active") {
                throw new KeyStateError("Only an active key can be rotated.");
            }

            const now = this.#clock();

            if (oldRecord.expiresAt !== null && oldRecord.expiresAt <= now) {
                throw new KeyStateError("An expired key cannot be rotated.");
            }

            const replacementLifetime =
                lifetimeMs === undefined
                    ? (
                        oldRecord.expiresAt === null
                            ? null
                            : oldRecord.expiresAt - now
                    )
                    : lifetimeMs;

            if (
                replacementLifetime !== null &&
                replacementLifetime <= 0
            ) {
                throw new ValidationError("The replacement key lifetime is invalid.");
            }

            // Both changes occur within one serialized operation.
            const replacement = this.#createRecord({
                owner: oldRecord.owner,
                label: oldRecord.label,
                scopes: oldRecord.scopes,
                lifetimeMs: replacementLifetime,
                actor,
                rotatedFrom: oldRecord.keyId
            });

            oldRecord.status = "revoked";
            oldRecord.revokedAt = now;

            this.#recordEvent("rotated", oldRecord, actor, {
                replacementKeyId: replacement.keyId
            });

            return replacement;
        });
    }

    async revoke(keyId, actor) {
        keyId = this.#validateText(keyId, "keyId", 32);
        actor = this.#validateText(actor, "actor");

        return this.#mutex.runExclusive(() => {
            const record = this.#records.get(keyId);

            if (!record) {
                throw new KeyNotFoundError();
            }

            if (record.status === "revoked") {
                return false;
            }

            record.status = "revoked";
            record.revokedAt = this.#clock();

            this.#recordEvent("revoked", record, actor);

            return true;
        });
    }

    metadata(keyId) {
        const record = this.#records.get(keyId);

        if (!record) {
            throw new KeyNotFoundError();
        }

        return Object.freeze({
            keyId: record.keyId,
            owner: record.owner,
            label: record.label,
            status: record.status,
            scopes: Object.freeze([...record.scopes].sort()),
            createdAt: new Date(record.createdAt).toISOString(),
            expiresAt:
                record.expiresAt === null
                    ? null
                    : new Date(record.expiresAt).toISOString(),
            lastUsedAt:
                record.lastUsedAt === null
                    ? null
                    : new Date(record.lastUsedAt).toISOString(),
            revokedAt:
                record.revokedAt === null
                    ? null
                    : new Date(record.revokedAt).toISOString(),
            rotatedFrom: record.rotatedFrom
        });
    }

    auditEvents(keyId) {
        return Object.freeze(
            this.#events
                .filter(event => event.keyId === keyId)
                .map(event => Object.freeze({
                    ...event,
                    details: Object.freeze({ ...event.details })
                }))
        );
    }
}

async function main() {
    const configuredPepper = process.env.API_KEY_PEPPER;

    // This fallback is process-local and suitable only for the demonstration.
    const pepper = configuredPepper
        ? Buffer.from(configuredPepper, "utf8")
        : randomBytes(32);

    const vault = new APIKeyVault({
        pepper,
        ownerPolicies: {
            "inventory-service": [
                "inventory:read",
                "inventory:update"
            ]
        }
    });

    vault.on("key-event", event => {
        console.log(
            `[audit] ${event.type} key=${event.keyId} actor=${event.actor}`
        );
    });

    const issued = await vault.issue({
        owner: "inventory-service",
        label: "warehouse integration",
        scopes: ["inventory:read", "inventory:update"],
        lifetimeMs: 30 * 24 * 60 * 60 * 1000,
        actor: "platform-admin"
    });

    console.log("\nIssued key ID:", issued.keyId);
    console.log("One-time token:", issued.token);

    const accepted = await vault.validate(
        issued.token,
        "inventory:read"
    );

    if (!accepted.accepted) {
        throw new Error("Expected valid credentials to be accepted.");
    }

    const denied = await vault.validate(
        issued.token,
        "billing:write"
    );

    if (denied.reason !== "insufficient_scope") {
        throw new Error("Expected an insufficient-scope decision.");
    }

    const replacement = await vault.rotate(
        issued.token,
        "security-admin",
        60 * 24 * 60 * 60 * 1000
    );

    const oldResult = await vault.validate(
        issued.token,
        "inventory:read"
    );

    if (oldResult.reason !== "revoked") {
        throw new Error("The previous key must be revoked after rotation.");
    }

    const replacementResult = await vault.validate(
        replacement.token,
        "inventory:read"
    );

    if (!replacementResult.accepted) {
        throw new Error("The replacement key should be active.");
    }

    await vault.revoke(replacement.keyId, "security-admin");

    const revokedResult = await vault.validate(
        replacement.token,
        "inventory:read"
    );

    if (revokedResult.reason !== "revoked") {
        throw new Error("Revoked credentials must be rejected.");
    }

    console.log("\nReplacement metadata:", vault.metadata(replacement.keyId));
    console.log("Replacement audit:", vault.auditEvents(replacement.keyId));
    console.log("\nAll lifecycle assertions passed.");
}

main().catch(error => {
    // Never print credential values or verifier data in error messages.
    console.error("API key demonstration failed:", error.message);
    process.exitCode = 1;
});
