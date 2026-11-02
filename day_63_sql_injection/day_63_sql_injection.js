"use strict";

const crypto = require("node:crypto");
const EventEmitter = require("node:events");

class ValidationError extends Error {}
class AuthenticationError extends Error {}

function hashPassword(password) {
    return crypto
        .createHash("sha256")
        .update(`application-demo:${password}`, "utf8")
        .digest("hex");
}

function validateUsername(username) {
    if (typeof username !== "string") {
        throw new ValidationError("username must be a string");
    }

    const value = username.trim();

    if (value.length === 0) {
        throw new ValidationError("username cannot be empty");
    }

    if (value.length > 80) {
        throw new ValidationError("username is too long");
    }

    return value;
}

/*
 * This compiler models the essential ORM behavior:
 * SQL structure is emitted separately from values.
 *
 * The database adapter would receive:
 *   text   -> SQL containing $1, $2, ...
 *   values -> user-controlled data
 *
 * A value containing quotes or SQL operators therefore remains data.
 */
class ParameterizedQuery {
    constructor(text, values) {
        this.text = text;
        this.values = Object.freeze([...values]);
    }
}

class UserQuery {
    static byCredentials(username, password) {
        const safeUsername = validateUsername(username);

        return new ParameterizedQuery(
            `
            SELECT user_id, username, role
            FROM users
            WHERE username = $1
              AND password_hash = $2
            `.trim(),
            [safeUsername, hashPassword(password)]
        );
    }

    static byUsername(username) {
        const safeUsername = validateUsername(username);

        return new ParameterizedQuery(
            `
            SELECT user_id, username, password_hash, role
            FROM users
            WHERE username = $1
            `.trim(),
            [safeUsername]
        );
    }
}

class InMemoryDatabase {
    constructor() {
        this.users = new Map([
            [
                "alice",
                {
                    user_id: 1,
                    username: "alice",
                    password_hash: hashPassword("AlicePass!23"),
                    role: "user",
                },
            ],
            [
                "bob",
                {
                    user_id: 2,
                    username: "bob",
                    password_hash: hashPassword("BobPass!23"),
                    role: "user",
                },
            ],
            [
                "admin",
                {
                    user_id: 3,
                    username: "admin",
                    password_hash: hashPassword("AdminPass!23"),
                    role: "admin",
                },
            ],
        ]);
    }

    async execute(query) {
        if (!(query instanceof ParameterizedQuery)) {
            throw new TypeError("database execution requires a parameterized query");
        }

        const username = query.values[0];
        const user = this.users.get(username);

        if (!user) {
            return [];
        }

        if (query.values.length === 2) {
            const suppliedHash = query.values[1];

            if (suppliedHash !== user.password_hash) {
                return [];
            }
        }

        return [{ ...user }];
    }
}

class UserRepository {
    constructor(database) {
        this.database = database;
    }

    async findByUsername(username) {
        const query = UserQuery.byUsername(username);
        const rows = await this.database.execute(query);
        return rows[0] ?? null;
    }

    async authenticate(username, password) {
        const query = UserQuery.byCredentials(username, password);
        const rows = await this.database.execute(query);

        if (rows.length === 0) {
            throw new AuthenticationError("invalid credentials");
        }

        return rows[0];
    }
}

class SecurityAudit extends EventEmitter {
    record(event, details) {
        /*
         * Audit records intentionally exclude passwords and raw secrets.
         * The event emitter also keeps policy logging independent from
         * repository implementation.
         */
        this.emit("security-event", {
            timestamp: new Date().toISOString(),
            event,
            details,
        });
    }
}

async function demonstrate(repository, audit) {
    const normalUser = await repository.authenticate(
        "alice",
        "AlicePass!23"
    );

    audit.record("authentication.success", {
        username: normalUser.username,
        role: normalUser.role,
    });

    console.log("[AUTHENTICATED]", normalUser);

    const injectionLikeInput = "' OR '1'='1";

    try {
        await repository.authenticate(
            injectionLikeInput,
            "wrong-password"
        );
    } catch (error) {
        if (!(error instanceof AuthenticationError)) {
            throw error;
        }

        audit.record("authentication.failure", {
            reason: "invalid credentials",
        });

        console.log("[INJECTION-LIKE INPUT] rejected as ordinary data");
    }

    const generatedQuery = UserQuery.byUsername(injectionLikeInput);

    console.log("\n[ORM-STYLE QUERY]");
    console.log(generatedQuery.text);
    console.log("[BOUND VALUES]", generatedQuery.values);

    try {
        await repository.authenticate("admin", "wrong-password");
    } catch (error) {
        console.log("[EXPECTED FAILURE]", error.message);
    }
}

async function main() {
    const database = new InMemoryDatabase();
    const repository = new UserRepository(database);
    const audit = new SecurityAudit();

    audit.on("security-event", (event) => {
        console.log("[AUDIT]", JSON.stringify(event));
    });

    console.log("[SQL INJECTION CONTROLS]");
    console.log("SQL syntax is fixed before user values are bound.");
    console.log("Validation enforces application rules but is not the SQL-injection defense.");
    console.log("The repository is the database boundary.");

    await demonstrate(repository, audit);

    console.log("\n[UNSAFE PATTERN]");
    console.log("Never construct SQL with:");
    console.log("SELECT ... WHERE username = '" + "USER_INPUT" + "'");

    console.log("\n[SAFE PATTERN]");
    console.log("Use placeholders such as $1 and pass values separately.");

    console.log("\n[PRODUCTION CONTROLS]");
    console.log("- Parameterized queries for every dynamic value.");
    console.log("- ORM query APIs that preserve parameter binding.");
    console.log("- Least-privilege database roles.");
    console.log("- Generic authentication failure messages.");
    console.log("- Security audit events without secrets.");
    console.log("- Input validation for domain correctness.");
    console.log("- Restricted database error exposure.");
}

main().catch((error) => {
    console.error("[FATAL]", error.message);
    process.exitCode = 1;
});
