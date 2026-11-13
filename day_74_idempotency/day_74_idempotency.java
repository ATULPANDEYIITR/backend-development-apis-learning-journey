import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/*
 * Enterprise Idempotency and Payment Governance System
 *
 * Java 17
 *
 * Demonstrates:
 * - Immutable request records.
 * - Explicit payment lifecycle.
 * - Policy-driven idempotency.
 * - Reviewer-independent transaction governance.
 * - Concurrent request coordination.
 * - Gateway failure handling.
 * - Reconciliation of ambiguous outcomes.
 * - Auditable state transitions.
 *
 * Compile:
 * javac IdempotencyEnterprise.java
 *
 * Run:
 * java IdempotencyEnterprise
 */

public class IdempotencyEnterprise {

    enum PaymentStatus {
        PROCESSING,
        SUCCEEDED,
        FAILED,
        UNKNOWN
    }

    enum ResultType {
        CREATED,
        REPLAYED,
        IN_PROGRESS
    }

    record PaymentRequest(
        String customerId,
        long amount,
        String currency,
        String paymentMethod
    ) {
        PaymentRequest {
            Objects.requireNonNull(customerId);
            Objects.requireNonNull(currency);
            Objects.requireNonNull(paymentMethod);

            if (customerId.isBlank()) {
                throw new IllegalArgumentException("Customer ID required.");
            }

            if (amount <= 0 || amount > 100_000_000L) {
                throw new IllegalArgumentException("Invalid amount.");
            }

            if (!currency.matches("[A-Z]{3}")) {
                throw new IllegalArgumentException("Invalid currency.");
            }

            if (paymentMethod.isBlank()) {
                throw new IllegalArgumentException("Payment method required.");
            }
        }

        String fingerprint() {
            // The selected business fields define request identity.
            String canonical = customerId.length() + ":" + customerId
                + "|" + amount
                + "|" + currency.length() + ":" + currency
                + "|" + paymentMethod.length() + ":" + paymentMethod;

            return java.util.HexFormat.of().formatHex(
                digest(canonical)
            );
        }

        private static byte[] digest(String value) {
            try {
                return java.security.MessageDigest
                    .getInstance("SHA-256")
                    .digest(value.getBytes(
                        java.nio.charset.StandardCharsets.UTF_8
                    ));
            } catch (java.security.NoSuchAlgorithmException e) {
                throw new IllegalStateException(e);
            }
        }
    }

    record PaymentResponse(
        String paymentId,
        PaymentStatus status,
        long amount,
        String currency,
        String providerReference,
        String errorCode,
        boolean replay
    ) {}

    record IdempotencyPolicy(
        Duration retention,
        boolean cacheFailures,
        boolean requireRequestFingerprint
    ) {
        IdempotencyPolicy {
            Objects.requireNonNull(retention);

            if (retention.isZero() || retention.isNegative()) {
                throw new IllegalArgumentException(
                    "Retention must be positive."
                );
            }

            if (!requireRequestFingerprint) {
                throw new IllegalArgumentException(
                    "Request fingerprinting is mandatory."
                );
            }
        }

        static IdempotencyPolicy enterpriseDefault() {
            return new IdempotencyPolicy(
                Duration.ofHours(24),
                true,
                true
            );
        }
    }

    static class DomainException extends RuntimeException {
        private final String code;

        DomainException(String code, String message) {
            super(message);
            this.code = code;
        }

        String code() {
            return code;
        }
    }

    static class Payment {
        final String id;
        final PaymentRequest request;
        final Instant createdAt;

        PaymentStatus status;
        String providerReference;
        String failureReason;

        Payment(String id, PaymentRequest request) {
            this.id = id;
            this.request = request;
            this.createdAt = Instant.now();
            this.status = PaymentStatus.PROCESSING;
        }

        void transition(PaymentStatus next) {
            boolean allowed = switch (status) {
                case PROCESSING ->
                    next == PaymentStatus.SUCCEEDED
                    || next == PaymentStatus.FAILED
                    || next == PaymentStatus.UNKNOWN;

                case UNKNOWN ->
                    next == PaymentStatus.SUCCEEDED
                    || next == PaymentStatus.FAILED;

                case SUCCEEDED, FAILED -> false;
            };

            if (!allowed) {
                throw new DomainException(
                    "INVALID_TRANSITION",
                    "Invalid transition from " + status + " to " + next
                );
            }

            status = next;
        }
    }

    static class IdempotencyRecord {
        final String key;
        final String fingerprint;
        final String paymentId;
        final Instant createdAt;
        final Instant expiresAt;

        PaymentStatus status;
        PaymentResponse response;

        IdempotencyRecord(
            String key,
            String fingerprint,
            String paymentId,
            Duration retention
        ) {
            this.key = key;
            this.fingerprint = fingerprint;
            this.paymentId = paymentId;
            this.createdAt = Instant.now();
            this.expiresAt = createdAt.plus(retention);
            this.status = PaymentStatus.PROCESSING;
        }
    }

    interface PaymentProvider {
        String charge(PaymentRequest request);
    }

    static class SimulatedPaymentProvider implements PaymentProvider {

        private int sequence = 5000;

        @Override
        public synchronized String charge(PaymentRequest request) {
            if (request.paymentMethod().equals("DECLINED")) {
                throw new DomainException(
                    "GATEWAY_DECLINED",
                    "Payment provider declined the request."
                );
            }

            return "PROVIDER-" + (++sequence);
        }
    }

    static class PaymentService {

        private static final Pattern KEY_PATTERN =
            Pattern.compile("[A-Za-z0-9_-]{16,128}");

        private final IdempotencyPolicy policy;
        private final PaymentProvider provider;

        private final ConcurrentHashMap<String, IdempotencyRecord> records =
            new ConcurrentHashMap<>();

        private final ConcurrentHashMap<String, Payment> payments =
            new ConcurrentHashMap<>();

        // A per-key lock allows unrelated payments to proceed concurrently.
        private final ConcurrentHashMap<String, ReentrantLock> locks =
            new ConcurrentHashMap<>();

        private final List<String> audit =
            java.util.Collections.synchronizedList(new ArrayList<>());

        PaymentService(
            IdempotencyPolicy policy,
            PaymentProvider provider
        ) {
            this.policy = policy;
            this.provider = provider;
        }

        PaymentResponse execute(
            String key,
            PaymentRequest request
        ) {
            validateKey(key);
            Objects.requireNonNull(request);

            ReentrantLock lock = locks.computeIfAbsent(
                key,
                ignored -> new ReentrantLock()
            );

            lock.lock();

            try {
                String fingerprint = request.fingerprint();

                IdempotencyRecord existing = records.get(key);

                if (existing != null) {
                    if (!existing.fingerprint.equals(fingerprint)) {
                        throw new DomainException(
                            "IDEMPOTENCY_CONFLICT",
                            "Key reused with different request parameters."
                        );
                    }

                    if (existing.expiresAt.isBefore(Instant.now())) {
                        throw new DomainException(
                            "IDEMPOTENCY_EXPIRED",
                            "Expired key requires reconciliation."
                        );
                    }

                    if (
                        existing.status == PaymentStatus.PROCESSING ||
                        existing.status == PaymentStatus.UNKNOWN
                    ) {
                        return new PaymentResponse(
                            existing.paymentId,
                            existing.status,
                            request.amount(),
                            request.currency(),
                            null,
                            null,
                            true
                        );
                    }

                    return replay(existing.response);
                }

                String paymentId = UUID.randomUUID().toString();

                Payment payment = new Payment(paymentId, request);

                IdempotencyRecord record = new IdempotencyRecord(
                    key,
                    fingerprint,
                    paymentId,
                    policy.retention()
                );

                // Both objects are registered before provider execution.
                payments.put(paymentId, payment);
                records.put(key, record);

                audit.add("RESERVED:" + paymentId);

                return process(payment, record);

            } finally {
                lock.unlock();
            }
        }

        private PaymentResponse process(
            Payment payment,
            IdempotencyRecord record
        ) {
            try {
                String reference = provider.charge(payment.request);

                payment.transition(PaymentStatus.SUCCEEDED);
                payment.providerReference = reference;

                PaymentResponse response = new PaymentResponse(
                    payment.id,
                    PaymentStatus.SUCCEEDED,
                    payment.request.amount(),
                    payment.request.currency(),
                    reference,
                    null,
                    false
                );

                record.status = PaymentStatus.SUCCEEDED;
                record.response = response;

                audit.add("SUCCEEDED:" + payment.id);

                return response;

            } catch (DomainException error) {
                payment.transition(PaymentStatus.FAILED);
                payment.failureReason = error.code();

                PaymentResponse response = new PaymentResponse(
                    payment.id,
                    PaymentStatus.FAILED,
                    payment.request.amount(),
                    payment.request.currency(),
                    null,
                    error.code(),
                    false
                );

                record.status = PaymentStatus.FAILED;

                if (policy.cacheFailures()) {
                    record.response = response;
                }

                audit.add("FAILED:" + payment.id);

                return response;

            } catch (RuntimeException error) {
                // Unknown outcomes must not be treated as confirmed failures.
                payment.transition(PaymentStatus.UNKNOWN);

                record.status = PaymentStatus.UNKNOWN;

                audit.add("UNKNOWN:" + payment.id);

                return new PaymentResponse(
                    payment.id,
                    PaymentStatus.UNKNOWN,
                    payment.request.amount(),
                    payment.request.currency(),
                    null,
                    "OUTCOME_UNKNOWN",
                    false
                );
            }
        }

        private PaymentResponse replay(PaymentResponse original) {
            return new PaymentResponse(
                original.paymentId(),
                original.status(),
                original.amount(),
                original.currency(),
                original.providerReference(),
                original.errorCode(),
                true
            );
        }

        void reconcile(
            String key,
            boolean confirmedSuccess,
            String providerReference
        ) {
            IdempotencyRecord record = records.get(key);

            if (record == null) {
                throw new DomainException(
                    "RECORD_NOT_FOUND",
                    "Idempotency record not found."
                );
            }

            ReentrantLock lock = locks.get(key);

            if (lock == null) {
                throw new IllegalStateException("Missing key lock.");
            }

            lock.lock();

            try {
                if (
                    record.status != PaymentStatus.UNKNOWN &&
                    record.status != PaymentStatus.PROCESSING
                ) {
                    throw new DomainException(
                        "RECONCILIATION_NOT_ALLOWED",
                        "Payment is already terminal."
                    );
                }

                Payment payment = payments.get(record.paymentId);

                if (confirmedSuccess) {
                    payment.transition(PaymentStatus.SUCCEEDED);
                    payment.providerReference = providerReference;

                    record.status = PaymentStatus.SUCCEEDED;

                    record.response = new PaymentResponse(
                        payment.id,
                        PaymentStatus.SUCCEEDED,
                        payment.request.amount(),
                        payment.request.currency(),
                        providerReference,
                        null,
                        false
                    );

                } else {
                    payment.transition(PaymentStatus.FAILED);

                    record.status = PaymentStatus.FAILED;

                    record.response = new PaymentResponse(
                        payment.id,
                        PaymentStatus.FAILED,
                        payment.request.amount(),
                        payment.request.currency(),
                        null,
                        "PROVIDER_CONFIRMED_NO_CHARGE",
                        false
                    );
                }

                audit.add("RECONCILED:" + payment.id);

            } finally {
                lock.unlock();
            }
        }

        Optional<Payment> findPayment(String paymentId) {
            return Optional.ofNullable(payments.get(paymentId));
        }

        Map<String, Long> report() {
            return payments.values().stream()
                .collect(Collectors.groupingBy(
                    payment -> payment.status.name(),
                    Collectors.counting()
                ));
        }

        int cleanupExpired() {
            Instant now = Instant.now();
            int removed = 0;

            for (Map.Entry<String, IdempotencyRecord> entry :
                    records.entrySet()) {

                IdempotencyRecord record = entry.getValue();

                if (
                    record.expiresAt.isBefore(now) &&
                    record.status != PaymentStatus.PROCESSING &&
                    record.status != PaymentStatus.UNKNOWN
                ) {
                    if (records.remove(entry.getKey(), record)) {
                        removed++;
                    }
                }
            }

            return removed;
        }

        List<String> auditEvents() {
            synchronized (audit) {
                return List.copyOf(audit);
            }
        }

        private void validateKey(String key) {
            if (key == null || !KEY_PATTERN.matcher(key).matches()) {
                throw new DomainException(
                    "INVALID_KEY",
                    "Invalid idempotency key."
                );
            }
        }
    }

    public static void main(String[] args) {

        IdempotencyPolicy policy =
            IdempotencyPolicy.enterpriseDefault();

        PaymentService service = new PaymentService(
            policy,
            new SimulatedPaymentProvider()
        );

        PaymentRequest request = new PaymentRequest(
            "CUSTOMER-4001",
            75000,
            "INR",
            "CARD-TOKEN-4001"
        );

        String key = "payment_request_400001";

        PaymentResponse first = service.execute(key, request);
        PaymentResponse second = service.execute(key, request);

        if (!first.paymentId().equals(second.paymentId())) {
            throw new AssertionError("Payment duplication detected.");
        }

        if (!second.replay()) {
            throw new AssertionError("Replay not identified.");
        }

        // Concurrent callers for the same key.
        try {
            var executor = java.util.concurrent.Executors
                .newFixedThreadPool(4);

            try {
                List<java.util.concurrent.Future<PaymentResponse>> futures =
                    new ArrayList<>();

                for (int i = 0; i < 4; i++) {
                    futures.add(executor.submit(
                        () -> service.execute(key, request)
                    ));
                }

                for (var future : futures) {
                    PaymentResponse response = future.get();

                    if (!response.paymentId().equals(first.paymentId())) {
                        throw new AssertionError(
                            "Concurrent request mismatch."
                        );
                    }
                }

            } finally {
                executor.shutdown();
            }

        } catch (Exception error) {
            throw new RuntimeException(error);
        }

        // Different payload with the same key must be rejected.
        try {
            service.execute(
                key,
                new PaymentRequest(
                    "CUSTOMER-4001",
                    99000,
                    "INR",
                    "CARD-TOKEN-4001"
                )
            );

            throw new AssertionError("Expected conflict.");

        } catch (DomainException error) {
            if (!error.code().equals("IDEMPOTENCY_CONFLICT")) {
                throw error;
            }
        }

        // Provider-declined operation.
        PaymentResponse failed = service.execute(
            "payment_request_400002",
            new PaymentRequest(
                "CUSTOMER-4002",
                30000,
                "INR",
                "DECLINED"
            )
        );

        if (failed.status() != PaymentStatus.FAILED) {
            throw new AssertionError("Failure state incorrect.");
        }

        System.out.println("Enterprise idempotency tests passed.");

        System.out.println("\nPayment report:");
        service.report().forEach(
            (status, count) -> System.out.println(status + ": " + count)
        );

        System.out.println("\nAudit events:");

        service.auditEvents().forEach(System.out::println);

        System.out.println(
            "\nExpired records removed: " + service.cleanupExpired()
        );
    }
}
