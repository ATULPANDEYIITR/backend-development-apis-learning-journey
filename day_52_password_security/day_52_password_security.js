"use strict";

const crypto = require("node:crypto");

const PASSWORD_POLICY = Object.freeze({
    algorithm: "scrypt",
    saltBytes: 16,
    keyBytes: 32,
    cost: 1 << 15,
    blockSize: 8,
    parallelization: 1,
    maxPasswordBytes: 1024
});

function validatePassword(password) {
    if (typeof password !== "string") {
        throw new TypeError("Password must be a string.");
    }

    if (password.length === 0) {
        throw new Error("Password cannot be empty.");
    }

    if (Buffer.byteLength(password, "utf8") > PASSWORD_POLICY.maxPasswordBytes) {
        throw new Error("Password is too large.");
    }
}

function scryptAsync(password, salt, keyBytes) {
    return new Promise((resolve, reject) => {
        crypto.scrypt(
            password,
            salt,
            keyBytes,
            {
                N: PASSWORD_POLICY.cost,
                r: PASSWORD_POLICY.blockSize,
                p: PASSWORD_POLICY.parallelization,
                maxmem: 64 * 1024 * 1024
            },
            (error, derivedKey) => {
                if (error) {
                    reject(error);
                    return;
                }

                resolve(derivedKey);
            }
        );
    });
}

async function hashPassword(password) {
    validatePassword(password);

    const salt = crypto.randomBytes(PASSWORD_POLICY.saltBytes);
    const derivedKey = await scryptAsync(
        password,
        salt,
        PASSWORD_POLICY.keyBytes
    );

    return {
        algorithm: PASSWORD_POLICY.algorithm,
        salt: salt.toString("base64"),
        digest: derivedKey.toString("base64"),
        cost: PASSWORD_POLICY.cost,
        blockSize: PASSWORD_POLICY.blockSize,
        parallelization: PASSWORD_POLICY.parallelization
    };
}

function constantTimeEqual(a, b) {
    if (!Buffer.isBuffer(a) || !Buffer.isBuffer(b)) {
        return false;
    }

    if (a.length !== b.length) {
        return false;
    }

    return crypto.timingSafeEqual(a, b);
}

async function verifyPassword(password, record) {
    try {
        validatePassword(password);

        if (!record || record.algorithm !== PASSWORD_POLICY.algorithm) {
            return false;
        }

        const salt = Buffer.from(record.salt, "base64");
        const expected = Buffer.from(record.digest, "base64");

        if (salt.length < PASSWORD_POLICY.saltBytes) {
            return false;
        }

        const actual = await scryptAsync(password, salt, expected.length);

        return constantTimeEqual(actual, expected);
    } catch {
        return false;
    }
}

function needsRehash(record) {
    return (
        !record ||
        record.algorithm !== PASSWORD_POLICY.algorithm ||
        record.cost !== PASSWORD_POLICY.cost ||
        record.blockSize !== PASSWORD_POLICY.blockSize ||
        record.parallelization !== PASSWORD_POLICY.parallelization
    );
}

async function authenticate(password, record) {
    const valid = await verifyPassword(password, record);

    if (!valid) {
        return {
            authenticated: false,
            reason: "Invalid credentials"
        };
    }

    return {
        authenticated: true,
        rehashRecommended: needsRehash(record)
    };
}

async function main() {
    const password = "CorrectHorseBatteryStaple!2026";

    const record = await hashPassword(password);

    console.log("Stored password record:");
    console.log(record);

    console.log("\nAuthentication:");

    console.log(
        "Correct password:",
        await authenticate(password, record)
    );

    console.log(
        "Incorrect password:",
        await authenticate("CorrectHorseBatteryStaple!2025", record)
    );

    const secondRecord = await hashPassword(password);

    console.log("\nUnique salts:");
    console.log("Salts differ:", record.salt !== secondRecord.salt);
    console.log("Digests differ:", record.digest !== secondRecord.digest);

    console.log("\nBrute-force resistance:");
    const candidates = [
        "password",
        "123456",
        "qwerty",
        "letmein",
        password
    ];

    for (const candidate of candidates) {
        const result = await verifyPassword(candidate, record);
        console.log(`${candidate}: ${result ? "accepted" : "rejected"}`);
    }
}

main().catch((error) => {
    console.error("Password-security demonstration failed:", error.message);
    process.exitCode = 1;
});
