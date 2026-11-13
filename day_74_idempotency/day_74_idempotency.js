"use strict";

/*
 * Idempotent Payment API
 *
 * Node.js 18+
 *
 * Features:
 * - Event-driven payment processing.
 * - Promise-based request coordination.
 * - Idempotency key registry.
 * - Request fingerprinting.
 * - Concurrent duplicate suppression.
 * - Cached success and failure results.
 * - Gateway timeout and failure handling.
 * - Expiration and reconciliation.
 */

const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");

class ApiError extends Error {
    constructor(message, code, statusCode = 400) {
        super(message);
        this.name = "ApiError";
        this.code = code;
        this.statusCode = statusCode;
    }
}

const PaymentStatus = Object.freeze({
    PROCESSING: "PROCESSING",
    SUCCEEDED: "SUCCEEDED",
    FAILED: "FAILED",
    UNKNOWN: "UNKNOWN"
});

function validateRequest(request) {
    if (!request || typeof request !== "object") {
        throw new ApiError("Request body is required.", "INVALID_BODY");
    }

    if (
        typeof request.customerId !== "string" ||
        request.customerId.trim().length === 0
    ) {
        throw new ApiError("Invalid customer ID.", "INVALID_CUSTOMER");
    }

    if (
        !Number.isSafeInteger(request.amount) ||
        request.amount <= 0 ||
        request.amount > 100000000
    ) {
        throw new ApiError("Invalid payment amount.", "INVALID_AMOUNT");
    }

    if (!/^[A-Z]{3}$/.test(request.currency)) {
        throw new ApiError("Invalid currency.", "INVALID_CURRENCY");
    }

    if (
        typeof request.paymentMethod !== "string" ||
        request.paymentMethod.length === 0
    ) {
        throw new ApiError("Payment method is required.", "INVALID_METHOD");
    }
}

function validateKey(key) {
    if (
        typeof key !== "string" ||
        key.length < 16 ||
        key.length > 128 ||
        !/^[A-Za-z0-9_-]+$/.test(key)
    ) {
        throw new ApiError(
            "Idempotency key must contain 16-128 valid characters.",
            "INVALID_IDEMPOTENCY_KEY"
        );
    }
}

function fingerprint(request) {
    // Explicit field selection prevents irrelevant input fields
    // from changing the business request identity.
    const canonical = JSON.stringify({
        customerId: request.customerId,
        amount: request.amount,
        currency: request.currency,
        paymentMethod: request.paymentMethod
    });

    return crypto.createHash("sha256")
        .update(canonical)
        .digest("hex");
}

class PaymentGateway {
    async charge(request) {
        // Simulated external payment provider.
        await new Promise(resolve => setTimeout(resolve, 30));

        if (request.simulateFailure) {
            throw new ApiError(
                "Gateway declined payment.",
                "GATEWAY_DECLINED",
                402
            );
        }

        return {
            providerReference: crypto.randomUUID(),
            approved: true
        };
    }
}

class IdempotencyService extends EventEmitter {
    constructor(options = {}) {
        super();

        this.retentionMs = options.retentionMs ?? 86400000;

        if (!Number.isSafeInteger(this.retentionMs) ||
            this.retentionMs <= 0) {
            throw new TypeError("Invalid retention period.");
        }

        this.gateway = options.gateway ?? new PaymentGateway();

        // Map provides constant-time average key lookup.
        this.records = new Map();
        this.payments = new Map();
    }

    async execute(key, request) {
        validateKey(key);
        validateRequest(request);

        const hash = fingerprint(request);
        const now = Date.now();

        const existing = this.records.get(key);

        if (existing) {
            if (existing.fingerprint !== hash) {
                throw new ApiError(
                    "Idempotency key reused with different parameters.",
                    "IDEMPOTENCY_CONFLICT",
                    409
                );
            }

            if (existing.expiresAt <= now) {
                throw new ApiError(
                    "Expired key requires payment reconciliation.",
                    "IDEMPOTENCY_EXPIRED",
                    409
                );
            }

            this.emit("duplicate", { keyHash: this.hashKey(key) });

            if (existing.status === PaymentStatus.PROCESSING) {
                // Concurrent callers await the original Promise.
                return {
                    ...await existing.promise,
                    idempotentReplay: true
                };
            }

            return {
                ...existing.response,
                idempotentReplay: true
            };
        }

        const paymentId = crypto.randomUUID();

        const payment = {
            paymentId,
            customerId: request.customerId,
            amount: request.amount,
            currency: request.currency,
            status: PaymentStatus.PROCESSING,
            createdAt: new Date().toISOString()
        };

        this.payments.set(paymentId, payment);

        const record = {
            fingerprint: hash,
            status: PaymentStatus.PROCESSING,
            paymentId,
            response: null,
            promise: null,
            createdAt: now,
            expiresAt: now + this.retentionMs
        };

        // Reserve synchronously before the first await.
        // JavaScript's event loop ensures another call cannot
        // interleave before this Map insertion completes.
        this.records.set(key, record);

        this.emit("payment:processing", {
            paymentId,
            keyHash: this.hashKey(key)
        });

        record.promise = this.processPayment(record, payment, request);

        return record.promise;
    }

    async processPayment(record, payment, request) {
        try {
            const gatewayResult = await this.gateway.charge(request);

            if (!gatewayResult.approved) {
                throw new ApiError(
                    "Payment not approved.",
                    "PAYMENT_NOT_APPROVED",
                    402
                );
            }

            payment.status = PaymentStatus.SUCCEEDED;
            payment.providerReference = gatewayResult.providerReference;

            const response = {
                paymentId: payment.paymentId,
                status: payment.status,
                amount: payment.amount,
                currency: payment.currency,
                idempotentReplay: false
            };

            record.status = PaymentStatus.SUCCEEDED;
            record.response = response;
            record.promise = null;

            this.emit("payment:succeeded", {
                paymentId: payment.paymentId
            });

            return response;

        } catch (error) {
            // Deterministic failures are cached. An ambiguous
            // provider timeout should instead enter UNKNOWN and
            // be reconciled before any new charge is attempted.
            const response = {
                paymentId: payment.paymentId,
                status: PaymentStatus.FAILED,
                errorCode: error.code ?? "PAYMENT_ERROR",
                idempotentReplay: false
            };

            payment.status = PaymentStatus.FAILED;
            record.status = PaymentStatus.FAILED;
            record.response = response;
            record.promise = null;

            this.emit("payment:failed", {
                paymentId: payment.paymentId,
                errorCode: response.errorCode
            });

            return response;
        }
    }

    hashKey(key) {
        return crypto.createHash("sha256")
            .update(key)
            .digest("hex")
            .slice(0, 16);
    }

    getPayment(paymentId) {
        const payment = this.payments.get(paymentId);

        if (!payment) {
            throw new ApiError("Payment not found.", "NOT_FOUND", 404);
        }

        return { ...payment };
    }

    cleanup() {
        const now = Date.now();
        let removed = 0;

        for (const [key, record] of this.records) {
            if (
                record.expiresAt <= now &&
                record.status !== PaymentStatus.PROCESSING &&
                record.status !== PaymentStatus.UNKNOWN
            ) {
                this.records.delete(key);
                removed++;
            }
        }

        return removed;
    }
}

async function main() {
    const service = new IdempotencyService();

    service.on("payment:processing", event => {
        console.log("Processing:", event.paymentId);
    });

    service.on("payment:succeeded", event => {
        console.log("Succeeded:", event.paymentId);
    });

    service.on("payment:failed", event => {
        console.log("Failed:", event.paymentId);
    });

    service.on("duplicate", () => {
        console.log("Duplicate request detected.");
    });

    const request = {
        customerId: "CUSTOMER-2001",
        amount: 25000,
        currency: "INR",
        paymentMethod: "CARD-TOKEN-2001"
    };

    const key = "payment_request_200001";

    // Two simultaneous requests share one payment operation.
    const [first, second] = await Promise.all([
        service.execute(key, request),
        service.execute(key, request)
    ]);

    if (first.paymentId !== second.paymentId) {
        throw new Error("Concurrent idempotency test failed.");
    }

    // A later retry returns the cached response.
    const third = await service.execute(key, request);

    if (third.paymentId !== first.paymentId) {
        throw new Error("Replay test failed.");
    }

    // Different parameters cannot reuse the same key.
    try {
        await service.execute(key, {
            ...request,
            amount: 50000
        });

        throw new Error("Expected idempotency conflict.");

    } catch (error) {
        if (error.code !== "IDEMPOTENCY_CONFLICT") {
            throw error;
        }

        console.log("Payload conflict correctly rejected.");
    }

    // Separate payment failure.
    const failed = await service.execute(
        "payment_request_200002",
        {
            ...request,
            simulateFailure: true
        }
    );

    console.log("\nPayment results:");
    console.log(JSON.stringify({ first, second, third, failed }, null, 2));

    console.log("\nPayment state:");
    console.log(service.getPayment(first.paymentId));

    console.log("\nExpired records removed:", service.cleanup());
}

main().catch(error => {
    console.error("Application failure:", error.message);
    process.exitCode = 1;
});
