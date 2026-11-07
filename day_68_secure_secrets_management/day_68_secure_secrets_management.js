"use strict";

/**
 * Secure Secrets Management
 * Node.js 20+
 *
 * Covers environment configuration, access control,
 * asynchronous secret providers, versioned rotation,
 * validation, audit events, and failure handling.
 *
 * Run: node secure-secrets.js
 */

const crypto = require("node:crypto");
const assert = require("node:assert/strict");

// ============================================================
// 1. Domain errors and enumerations
// ============================================================

class SecretError extends Error {}
class SecretNotFoundError extends SecretError {}
class SecretAccessError extends SecretError {}
class SecretValidationError extends SecretError {}
class SecretStateError extends SecretError {}
class SecretProviderError extends SecretError {}

const SecretState = Object.freeze({
    ACTIVE: "ACTIVE",
    STAGED: "STAGED",
    RETIRED: "RETIRED",
    REVOKED: "REVOKED"
});

// ============================================================
// 2. Validation utilities
// ============================================================

function validateName(name) {
    if (
        typeof name !== "string" ||
        !/^[A-Za-z0-9_.-]{1,128}$/.test(name)
    ) {
        throw new SecretValidationError(
            "Invalid secret identifier."
        );
    }
}

function validateValue(value) {
    if (
        typeof value !== "string" ||
        value.length < 16 ||
        value.length > 8192
    ) {
        throw new SecretValidationError(
            "Secret length must be between 16 and 8192 characters."
        );
    }
}

function generateSecret(length = 48) {
    if (!Number.isInteger(length) || length < 32 || length > 256) {
        throw new SecretValidationError("Invalid generation length.");
    }

    const alphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_!@#$%";

    const bytes = crypto.randomBytes(length);

    return Array.from(
        bytes,
        byte => alphabet[byte % alphabet.length]
    ).join("");
}

function fingerprint(value) {
    return crypto
        .createHash("sha256")
        .update(value, "utf8")
        .digest("hex");
}

// ============================================================
// 3. Environment configuration
// ============================================================

function loadEnvironment(names, environment = process.env) {
    const result = Object.create(null);

    for (const name of names) {
        validateName(name);

        const value = environment[name];

        if (
            typeof value !== "string" ||
            value.trim().length === 0
        ) {
            throw new SecretValidationError(
                `Missing environment variable: ${name}`
            );
        }

        result[name] = value;
    }

    return Object.freeze(result);
}

function validateEnvironmentNames(environment = process.env) {
    const sensitivePatterns = [
        /PASSWORD/i,
        /SECRET/i,
        /PRIVATE_KEY/i,
        /TOKEN/i
    ];

    for (const name of Object.keys(environment)) {
        if (
            sensitivePatterns.some(pattern => pattern.test(name)) &&
            environment[name] === ""
        ) {
            throw new SecretValidationError(
                `Empty sensitive environment variable: ${name}`
            );
        }
    }
}

// ============================================================
// 4. Role-based access control
// ============================================================

class AccessController {
    constructor() {
        this.permissions = new Map([
            ["application", new Set(["read"])],
            [
                "security-admin",
                new Set([
                    "read",
                    "create",
                    "rotate",
                    "revoke",
                    "metadata"
                ])
            ],
            ["rotation-service", new Set(["read", "create", "rotate"])],
            ["auditor", new Set(["metadata"])]
        ]);
    }

    authorize(actor, action) {
        const allowed = this.permissions.get(actor);

        if (!allowed || !allowed.has(action)) {
            throw new SecretAccessError(
                `Access denied: ${actor} cannot ${action}.`
            );
        }
    }
}

// ============================================================
// 5. Asynchronous provider contract
// ============================================================

class SecretProvider {
    async getSecret(_name, _actor) {
        throw new Error("Provider method not implemented.");
    }

    async getMetadata(_name, _actor) {
        throw new Error("Provider method not implemented.");
    }
}

// ============================================================
// 6. In-memory versioned provider
// ============================================================

class InMemorySecretProvider extends SecretProvider {
    #records = new Map();
    #audit = [];
    #controller;

    constructor(controller = new AccessController()) {
        super();
        this.#controller = controller;
    }

    #authorize(actor, action, name, version = null) {
        try {
            this.#controller.authorize(actor, action);
        } catch (error) {
            this.#record(
                actor,
                action,
                name,
                version,
                "DENIED"
            );
            throw error;
        }
    }

    #record(actor, action, name, version, outcome) {
        this.#audit.push(
            Object.freeze({
                timestamp: new Date().toISOString(),
                actor,
                action,
                secretName: name,
                version,
                outcome
            })
        );
    }

    #getVersions(name) {
        const versions = this.#records.get(name);

        if (!versions) {
            throw new SecretNotFoundError(
                `Secret not found: ${name}`
            );
        }

        return versions;
    }

    async create(name, value, actor, expiresInDays = null) {
        this.#authorize(actor, "create", name);

        validateName(name);
        validateValue(value);

        if (this.#records.has(name)) {
            throw new SecretStateError(
                "Secret already exists."
            );
        }

        if (
            expiresInDays !== null &&
            (!Number.isInteger(expiresInDays) || expiresInDays <= 0)
        ) {
            throw new SecretValidationError(
                "Expiry must be a positive integer."
            );
        }

        const now = new Date();

        const record = {
            version: 1,
            value,
            state: SecretState.ACTIVE,
            createdAt: now.toISOString(),
            expiresAt: expiresInDays === null
                ? null
                : new Date(
                    now.getTime() + expiresInDays * 86400000
                ).toISOString()
        };

        this.#records.set(name, [record]);

        this.#record(actor, "CREATE", name, 1, "SUCCESS");

        return this.#metadata(record);
    }

    #metadata(record) {
        return Object.freeze({
            version: record.version,
            state: record.state,
            createdAt: record.createdAt,
            expiresAt: record.expiresAt
        });
    }

    async getSecret(name, actor) {
        this.#authorize(actor, "read", name);

        const versions = this.#getVersions(name);

        const active = versions.find(
            item => item.state === SecretState.ACTIVE
        );

        if (!active) {
            throw new SecretStateError(
                "No active secret version."
            );
        }

        if (
            active.expiresAt &&
            Date.now() >= Date.parse(active.expiresAt)
        ) {
            throw new SecretStateError("Secret has expired.");
        }

        this.#record(
            actor,
            "READ",
            name,
            active.version,
            "SUCCESS"
        );

        return active.value;
    }

    async stageRotation(name, value, actor) {
        this.#authorize(actor, "rotate", name);

        validateName(name);
        validateValue(value);

        const versions = this.#getVersions(name);

        if (
            versions.some(
                item => item.state === SecretState.STAGED
            )
        ) {
            throw new SecretStateError(
                "A rotation is already staged."
            );
        }

        const active = versions.find(
            item => item.state === SecretState.ACTIVE
        );

        if (!active) {
            throw new SecretStateError("No active version.");
        }

        if (
            crypto.timingSafeEqual(
                Buffer.from(fingerprint(active.value), "hex"),
                Buffer.from(fingerprint(value), "hex")
            )
        ) {
            throw new SecretValidationError(
                "New secret must differ from active secret."
            );
        }

        const version = Math.max(
            ...versions.map(item => item.version)
        ) + 1;

        const staged = {
            version,
            value,
            state: SecretState.STAGED,
            createdAt: new Date().toISOString(),
            expiresAt: null
        };

        versions.push(staged);

        this.#record(
            actor,
            "STAGE_ROTATION",
            name,
            version,
            "SUCCESS"
        );

        return this.#metadata(staged);
    }

    async activateRotation(name, actor) {
        this.#authorize(actor, "rotate", name);

        const versions = this.#getVersions(name);

        const staged = versions.find(
            item => item.state === SecretState.STAGED
        );

        if (!staged) {
            throw new SecretStateError(
                "No staged version exists."
            );
        }

        const active = versions.find(
            item => item.state === SecretState.ACTIVE
        );

        if (active) {
            active.state = SecretState.RETIRED;
        }

        staged.state = SecretState.ACTIVE;

        this.#record(
            actor,
            "ACTIVATE_ROTATION",
            name,
            staged.version,
            "SUCCESS"
        );

        return this.#metadata(staged);
    }

    async revoke(name, version, actor) {
        this.#authorize(actor, "revoke", name, version);

        const versions = this.#getVersions(name);

        const target = versions.find(
            item => item.version === version
        );

        if (!target) {
            throw new SecretNotFoundError(
                "Version does not exist."
            );
        }

        if (target.state === SecretState.ACTIVE) {
            throw new SecretStateError(
                "Cannot revoke the active version."
            );
        }

        if (target.state === SecretState.REVOKED) {
            throw new SecretStateError(
                "Version already revoked."
            );
        }

        // Clear the in-memory reference. JavaScript does not
        // guarantee secure memory erasure of immutable strings.
        target.value = "";
        target.state = SecretState.REVOKED;

        this.#record(
            actor,
            "REVOKE",
            name,
            version,
            "SUCCESS"
        );
    }

    async getMetadata(name, actor) {
        this.#authorize(actor, "metadata", name);

        return Object.freeze(
            this.#getVersions(name).map(item => this.#metadata(item))
        );
    }

    async getAuditLog(actor) {
        this.#authorize(actor, "metadata", "audit-log");
        return Object.freeze([...this.#audit]);
    }
}

// ============================================================
// 7. Rotation coordinator
// ============================================================

class RotationCoordinator {
    constructor(provider, verificationFunction) {
        this.provider = provider;
        this.verify = verificationFunction;
    }

    async rotate(name, actor = "security-admin") {
        const oldValue = await this.provider.getSecret(
            name,
            actor
        );

        const newValue = generateSecret();

        try {
            const staged = await this.provider.stageRotation(
                name,
                newValue,
                actor
            );

            // Verify the new credential with its downstream service
            // before changing the application's active version.
            const verified = await this.verify(newValue);

            if (!verified) {
                throw new SecretProviderError(
                    "Downstream credential verification failed."
                );
            }

            const activated = await this.provider.activateRotation(
                name,
                actor
            );

            return {
                previousValue: oldValue,
                newVersion: activated.version,
                state: activated.state,
                stagedVersion: staged.version
            };
        } catch (error) {
            // The staged version remains inactive if verification
            // or activation fails. Production systems should also
            // record the failure in durable audit storage.
            throw error;
        }
    }
}

// ============================================================
// 8. Application configuration
// ============================================================

class ApplicationConfiguration {
    constructor(environment) {
        this.databaseHost = environment.DATABASE_HOST;
        this.databasePort = Number(environment.DATABASE_PORT);

        if (
            !Number.isInteger(this.databasePort) ||
            this.databasePort < 1 ||
            this.databasePort > 65535
        ) {
            throw new SecretValidationError(
                "Invalid database port."
            );
        }

        Object.freeze(this);
    }
}

// ============================================================
// 9. Executable demonstration and tests
// ============================================================

async function main() {
    console.log("SECURE SECRETS MANAGEMENT");
    console.log("=".repeat(45));

    validateEnvironmentNames();

    // Test environment configuration without exposing values.
    const configuration = loadEnvironment(
        ["DATABASE_HOST", "DATABASE_PORT"],
        {
            DATABASE_HOST: "db.internal",
            DATABASE_PORT: "5432"
        }
    );

    const appConfig = new ApplicationConfiguration(configuration);

    assert.equal(appConfig.databasePort, 5432);

    const provider = new InMemorySecretProvider();

    await provider.create(
        "payment-gateway",
        generateSecret(),
        "security-admin",
        90
    );

    const initial = await provider.getSecret(
        "payment-gateway",
        "application"
    );

    assert.ok(initial.length >= 32);

    // Unauthorized access must fail.
    await assert.rejects(
        () => provider.getSecret(
            "payment-gateway",
            "auditor"
        ),
        SecretAccessError
    );

    const coordinator = new RotationCoordinator(
        provider,
        async value => value.length >= 32
    );

    const rotation = await coordinator.rotate(
        "payment-gateway"
    );

    assert.equal(rotation.state, SecretState.ACTIVE);

    const current = await provider.getSecret(
        "payment-gateway",
        "application"
    );

    assert.notEqual(current, initial);

    await provider.revoke(
        "payment-gateway",
        1,
        "security-admin"
    );

    const metadata = await provider.getMetadata(
        "payment-gateway",
        "auditor"
    );

    assert.equal(metadata.length, 2);
    assert.equal(metadata[0].state, SecretState.REVOKED);
    assert.equal(metadata[1].state, SecretState.ACTIVE);

    await assert.rejects(
        () => provider.stageRotation(
            "payment-gateway",
            "weak",
            "rotation-service"
        ),
        SecretValidationError
    );

    await assert.rejects(
        () => provider.revoke(
            "payment-gateway",
            2,
            "security-admin"
        ),
        SecretStateError
    );

    const audit = await provider.getAuditLog("auditor");

    console.log("Environment validation: PASSED");
    console.log("Access-control validation: PASSED");
    console.log("Credential rotation: PASSED");
    console.log("Previous version revocation: PASSED");
    console.log("Metadata validation: PASSED");
    console.log("Audit events:", audit.length);

    // Never log secret values, tokens, or credential contents.
    console.log("Active version:", rotation.newVersion);
    console.log("All checks completed.");
}

main().catch(error => {
    // Report error categories, not credential contents.
    console.error(
        "Secrets-management failure:",
        error.constructor.name,
        error.message
    );

    process.exitCode = 1;
});
