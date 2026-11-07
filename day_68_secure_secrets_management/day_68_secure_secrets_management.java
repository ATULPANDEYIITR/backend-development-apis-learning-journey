import java.security.SecureRandom;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.regex.Pattern;

/**
 * Secure Secrets Management
 *
 * Enterprise scenario:
 * A financial services application manages database credentials
 * and payment-provider API credentials using controlled access,
 * secret versioning, rotation, expiry, and revocation.
 *
 * Java 17, standard library only.
 *
 * Compile:
 * javac SecureSecrets.java
 *
 * Run:
 * java SecureSecrets
 */
public class SecureSecrets {

    // ========================================================
    // 1. Domain types
    // ========================================================

    enum SecretState {
        ACTIVE,
        STAGED,
        RETIRED,
        REVOKED
    }

    enum Action {
        READ,
        CREATE,
        ROTATE,
        REVOKE,
        METADATA
    }

    enum RotationStatus {
        STAGED,
        VERIFIED,
        ACTIVATED,
        FAILED
    }

    // ========================================================
    // 2. Custom exceptions
    // ========================================================

    static class SecretException extends RuntimeException {
        SecretException(String message) {
            super(message);
        }
    }

    static class AccessDeniedException extends SecretException {
        AccessDeniedException(String message) {
            super(message);
        }
    }

    static class ValidationException extends SecretException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class StateException extends SecretException {
        StateException(String message) {
            super(message);
        }
    }

    static class NotFoundException extends SecretException {
        NotFoundException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 3. Immutable domain records
    // ========================================================

    record SecretMetadata(
        String name,
        int version,
        SecretState state,
        Instant createdAt,
        Instant expiresAt
    ) {
        SecretMetadata {
            Objects.requireNonNull(name);
            Objects.requireNonNull(state);
            Objects.requireNonNull(createdAt);

            if (version <= 0) {
                throw new ValidationException(
                    "Version must be positive."
                );
            }
        }
    }

    record AuditEvent(
        Instant timestamp,
        String actor,
        Action action,
        String secretName,
        Integer version,
        String outcome
    ) {}

    record RotationResult(
        String secretName,
        int previousVersion,
        int activeVersion,
        RotationStatus status
    ) {}

    // ========================================================
    // 4. Secret validation and generation
    // ========================================================

    static final class SecretUtilities {

        private static final Pattern NAME_PATTERN =
            Pattern.compile("[A-Za-z0-9_.-]{1,128}");

        private static final SecureRandom RANDOM =
            new SecureRandom();

        private static final char[] ALPHABET =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_!@#$%"
                .toCharArray();

        static void validateName(String name) {
            if (
                name == null ||
                !NAME_PATTERN.matcher(name).matches()
            ) {
                throw new ValidationException(
                    "Invalid secret identifier."
                );
            }
        }

        static void validateValue(char[] value) {
            if (
                value == null ||
                value.length < 16 ||
                value.length > 8192
            ) {
                throw new ValidationException(
                    "Secret length must be between 16 and 8192."
                );
            }
        }

        static char[] generateSecret(int length) {
            if (length < 32 || length > 256) {
                throw new ValidationException(
                    "Invalid generated secret length."
                );
            }

            char[] result = new char[length];

            for (int i = 0; i < length; i++) {
                result[i] = ALPHABET[
                    RANDOM.nextInt(ALPHABET.length)
                ];
            }

            return result;
        }

        static void clear(char[] value) {
            if (value != null) {
                java.util.Arrays.fill(value, '\0');
            }
        }
    }

    // ========================================================
    // 5. Access policy
    // ========================================================

    static final class AccessPolicy {

        private final Map<String, Set<Action>> permissions =
            new HashMap<>();

        AccessPolicy() {
            permissions.put(
                "application",
                Set.of(Action.READ)
            );

            permissions.put(
                "security-admin",
                Set.of(
                    Action.READ,
                    Action.CREATE,
                    Action.ROTATE,
                    Action.REVOKE,
                    Action.METADATA
                )
            );

            permissions.put(
                "rotation-service",
                Set.of(
                    Action.READ,
                    Action.CREATE,
                    Action.ROTATE
                )
            );

            permissions.put(
                "auditor",
                Set.of(Action.METADATA)
            );
        }

        void authorize(String actor, Action action) {
            Set<Action> allowed = permissions.get(actor);

            if (
                allowed == null ||
                !allowed.contains(action)
            ) {
                throw new AccessDeniedException(
                    "Operation is not permitted."
                );
            }
        }
    }

    // ========================================================
    // 6. Secret provider interface
    // ========================================================

    interface SecretProvider {

        void create(
            String name,
            char[] value,
            String actor,
            long expiryDays
        );

        char[] retrieve(String name, String actor);

        SecretMetadata stage(
            String name,
            char[] value,
            String actor
        );

        SecretMetadata activate(
            String name,
            String actor
        );

        void revoke(
            String name,
            int version,
            String actor
        );

        List<SecretMetadata> metadata(
            String name,
            String actor
        );
    }

    // ========================================================
    // 7. Versioned secret storage
    // ========================================================

    static final class SecretVersion {

        private final int version;
        private final Instant createdAt;
        private final Instant expiresAt;

        private SecretState state;
        private char[] value;

        SecretVersion(
            int version,
            char[] value,
            SecretState state,
            Instant expiresAt
        ) {
            this.version = version;
            this.value = value.clone();
            this.state = state;
            this.createdAt = Instant.now();
            this.expiresAt = expiresAt;
        }

        SecretMetadata metadata(String name) {
            return new SecretMetadata(
                name,
                version,
                state,
                createdAt,
                expiresAt
            );
        }

        void clearValue() {
            SecretUtilities.clear(value);
            value = new char[0];
        }

        char[] copyValue() {
            return value.clone();
        }
    }

    // ========================================================
    // 8. Enterprise secret manager
    // ========================================================

    static final class EnterpriseSecretManager
            implements SecretProvider {

        private final Map<String, List<SecretVersion>> storage =
            new HashMap<>();

        private final List<AuditEvent> audit =
            new ArrayList<>();

        private final AccessPolicy policy;

        private final ReentrantReadWriteLock lock =
            new ReentrantReadWriteLock();

        EnterpriseSecretManager(AccessPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        private void record(
            String actor,
            Action action,
            String name,
            Integer version,
            String outcome
        ) {
            audit.add(
                new AuditEvent(
                    Instant.now(),
                    actor,
                    action,
                    name,
                    version,
                    outcome
                )
            );
        }

        private void authorize(
            String actor,
            Action action,
            String name,
            Integer version
        ) {
            try {
                policy.authorize(actor, action);
            } catch (AccessDeniedException error) {
                record(
                    actor,
                    action,
                    name,
                    version,
                    "DENIED"
                );

                throw error;
            }
        }

        private List<SecretVersion> versions(String name) {
            List<SecretVersion> result = storage.get(name);

            if (result == null) {
                throw new NotFoundException(
                    "Secret does not exist."
                );
            }

            return result;
        }

        private SecretVersion findState(
            List<SecretVersion> versions,
            SecretState state
        ) {
            return versions.stream()
                .filter(item -> item.state == state)
                .findFirst()
                .orElse(null);
        }

        // ----------------------------------------------------
        // Create
        // ----------------------------------------------------

        @Override
        public void create(
            String name,
            char[] value,
            String actor,
            long expiryDays
        ) {
            authorize(actor, Action.CREATE, name, null);

            SecretUtilities.validateName(name);
            SecretUtilities.validateValue(value);

            if (expiryDays < 0) {
                throw new ValidationException(
                    "Expiry cannot be negative."
                );
            }

            lock.writeLock().lock();

            try {
                if (storage.containsKey(name)) {
                    throw new StateException(
                        "Secret already exists."
                    );
                }

                Instant expiry = expiryDays == 0
                    ? null
                    : Instant.now().plus(
                        expiryDays,
                        ChronoUnit.DAYS
                    );

                SecretVersion version = new SecretVersion(
                    1,
                    value,
                    SecretState.ACTIVE,
                    expiry
                );

                storage.put(
                    name,
                    new ArrayList<>(List.of(version))
                );

                record(
                    actor,
                    Action.CREATE,
                    name,
                    1,
                    "SUCCESS"
                );

            } finally {
                lock.writeLock().unlock();
            }
        }

        // ----------------------------------------------------
        // Retrieve active credential
        // ----------------------------------------------------

        @Override
        public char[] retrieve(String name, String actor) {
            authorize(actor, Action.READ, name, null);

            lock.readLock().lock();

            try {
                List<SecretVersion> list = versions(name);

                SecretVersion active = findState(
                    list,
                    SecretState.ACTIVE
                );

                if (active == null) {
                    throw new StateException(
                        "No active credential."
                    );
                }

                if (
                    active.expiresAt != null &&
                    !Instant.now().isBefore(active.expiresAt)
                ) {
                    throw new StateException(
                        "Credential has expired."
                    );
                }

                record(
                    actor,
                    Action.READ,
                    name,
                    active.version,
                    "SUCCESS"
                );

                return active.copyValue();

            } finally {
                lock.readLock().unlock();
            }
        }

        // ----------------------------------------------------
        // Stage replacement
        // ----------------------------------------------------

        @Override
        public SecretMetadata stage(
            String name,
            char[] value,
            String actor
        ) {
            authorize(actor, Action.ROTATE, name, null);

            SecretUtilities.validateValue(value);

            lock.writeLock().lock();

            try {
                List<SecretVersion> list = versions(name);

                if (
                    findState(list, SecretState.STAGED) != null
                ) {
                    throw new StateException(
                        "Rotation is already staged."
                    );
                }

                SecretVersion active = findState(
                    list,
                    SecretState.ACTIVE
                );

                if (active == null) {
                    throw new StateException(
                        "No active credential."
                    );
                }

                if (
                    java.util.Arrays.equals(
                        active.value,
                        value
                    )
                ) {
                    throw new ValidationException(
                        "Replacement must differ from active credential."
                    );
                }

                int nextVersion = list.stream()
                    .mapToInt(item -> item.version)
                    .max()
                    .orElse(0) + 1;

                SecretVersion staged = new SecretVersion(
                    nextVersion,
                    value,
                    SecretState.STAGED,
                    null
                );

                list.add(staged);

                record(
                    actor,
                    Action.ROTATE,
                    name,
                    nextVersion,
                    "STAGED"
                );

                return staged.metadata(name);

            } finally {
                lock.writeLock().unlock();
            }
        }

        // ----------------------------------------------------
        // Activate
        // ----------------------------------------------------

        @Override
        public SecretMetadata activate(
            String name,
            String actor
        ) {
            authorize(actor, Action.ROTATE, name, null);

            lock.writeLock().lock();

            try {
                List<SecretVersion> list = versions(name);

                SecretVersion staged = findState(
                    list,
                    SecretState.STAGED
                );

                if (staged == null) {
                    throw new StateException(
                        "No staged credential."
                    );
                }

                SecretVersion active = findState(
                    list,
                    SecretState.ACTIVE
                );

                if (active != null) {
                    active.state = SecretState.RETIRED;
                }

                staged.state = SecretState.ACTIVE;

                record(
                    actor,
                    Action.ROTATE,
                    name,
                    staged.version,
                    "ACTIVATED"
                );

                return staged.metadata(name);

            } finally {
                lock.writeLock().unlock();
            }
        }

        // ----------------------------------------------------
        // Revoke
        // ----------------------------------------------------

        @Override
        public void revoke(
            String name,
            int versionNumber,
            String actor
        ) {
            authorize(
                actor,
                Action.REVOKE,
                name,
                versionNumber
            );

            lock.writeLock().lock();

            try {
                List<SecretVersion> list = versions(name);

                SecretVersion target = list.stream()
                    .filter(item -> item.version == versionNumber)
                    .findFirst()
                    .orElseThrow(
                        () -> new NotFoundException(
                            "Version does not exist."
                        )
                    );

                if (target.state == SecretState.ACTIVE) {
                    throw new StateException(
                        "Cannot revoke the active credential."
                    );
                }

                if (target.state == SecretState.REVOKED) {
                    throw new StateException(
                        "Credential already revoked."
                    );
                }

                target.clearValue();
                target.state = SecretState.REVOKED;

                record(
                    actor,
                    Action.REVOKE,
                    name,
                    versionNumber,
                    "SUCCESS"
                );

            } finally {
                lock.writeLock().unlock();
            }
        }

        // ----------------------------------------------------
        // Metadata reporting
        // ----------------------------------------------------

        @Override
        public List<SecretMetadata> metadata(
            String name,
            String actor
        ) {
            authorize(
                actor,
                Action.METADATA,
                name,
                null
            );

            lock.readLock().lock();

            try {
                return versions(name).stream()
                    .map(item -> item.metadata(name))
                    .toList();

            } finally {
                lock.readLock().unlock();
            }
        }

        List<AuditEvent> auditLog(String actor) {
            authorize(
                actor,
                Action.METADATA,
                "audit-log",
                null
            );

            lock.readLock().lock();

            try {
                return Collections.unmodifiableList(
                    new ArrayList<>(audit)
                );

            } finally {
                lock.readLock().unlock();
            }
        }
    }

    // ========================================================
    // 9. Rotation policy
    // ========================================================

    interface CredentialVerifier {
        boolean verify(char[] candidate);
    }

    static final class RotationService {

        private final SecretProvider provider;
        private final CredentialVerifier verifier;

        RotationService(
            SecretProvider provider,
            CredentialVerifier verifier
        ) {
            this.provider = provider;
            this.verifier = verifier;
        }

        RotationResult rotate(
            String name,
            String actor
        ) {
            List<SecretMetadata> before = provider.metadata(
                name,
                "security-admin"
            );

            int previousVersion = before.stream()
                .filter(item -> item.state() == SecretState.ACTIVE)
                .mapToInt(SecretMetadata::version)
                .findFirst()
                .orElseThrow(
                    () -> new StateException(
                        "No active version."
                    )
                );

            char[] replacement =
                SecretUtilities.generateSecret(48);

            try {
                SecretMetadata staged = provider.stage(
                    name,
                    replacement,
                    actor
                );

                if (!verifier.verify(replacement)) {
                    throw new StateException(
                        "Downstream verification failed."
                    );
                }

                SecretMetadata activated = provider.activate(
                    name,
                    actor
                );

                return new RotationResult(
                    name,
                    previousVersion,
                    activated.version(),
                    RotationStatus.ACTIVATED
                );

            } finally {
                // The provider owns its cloned version.
                // Clear the caller's temporary character array.
                SecretUtilities.clear(replacement);
            }
        }
    }

    // ========================================================
    // 10. Environment configuration
    // ========================================================

    static final class EnvironmentConfiguration {

        private final String databaseHost;
        private final int databasePort;

        EnvironmentConfiguration(
            Map<String, String> environment
        ) {
            databaseHost = environment.get("DATABASE_HOST");

            String port = environment.get("DATABASE_PORT");

            if (
                databaseHost == null ||
                databaseHost.isBlank()
            ) {
                throw new ValidationException(
                    "DATABASE_HOST is required."
                );
            }

            try {
                databasePort = Integer.parseInt(port);

                if (
                    databasePort < 1 ||
                    databasePort > 65535
                ) {
                    throw new NumberFormatException();
                }

            } catch (NumberFormatException error) {
                throw new ValidationException(
                    "Invalid DATABASE_PORT."
                );
            }
        }

        String databaseHost() {
            return databaseHost;
        }

        int databasePort() {
            return databasePort;
        }
    }

    // ========================================================
    // 11. Executable validation
    // ========================================================

    static void require(
        boolean condition,
        String message
    ) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    public static void main(String[] args) {

        System.out.println("SECURE SECRETS MANAGEMENT");
        System.out.println("=".repeat(45));

        EnvironmentConfiguration config =
            new EnvironmentConfiguration(
                Map.of(
                    "DATABASE_HOST", "db.internal",
                    "DATABASE_PORT", "5432"
                )
            );

        require(
            config.databasePort() == 5432,
            "Configuration validation failed."
        );

        EnterpriseSecretManager manager =
            new EnterpriseSecretManager(
                new AccessPolicy()
            );

        char[] initial = SecretUtilities.generateSecret(48);

        manager.create(
            "payment-api",
            initial,
            "security-admin",
            90
        );

        SecretUtilities.clear(initial);

        char[] retrieved = manager.retrieve(
            "payment-api",
            "application"
        );

        require(
            retrieved.length >= 32,
            "Credential retrieval failed."
        );

        SecretUtilities.clear(retrieved);

        // An auditor cannot retrieve credential contents.
        try {
            manager.retrieve(
                "payment-api",
                "auditor"
            );

            throw new AssertionError(
                "Unauthorized read was accepted."
            );

        } catch (AccessDeniedException expected) {
            System.out.println(
                "Role enforcement: PASSED"
            );
        }

        RotationService rotationService =
            new RotationService(
                manager,
                candidate -> candidate.length >= 32
            );

        RotationResult result = rotationService.rotate(
            "payment-api",
            "security-admin"
        );

        require(
            result.status() == RotationStatus.ACTIVATED,
            "Rotation failed."
        );

        manager.revoke(
            "payment-api",
            result.previousVersion(),
            "security-admin"
        );

        List<SecretMetadata> metadata = manager.metadata(
            "payment-api",
            "auditor"
        );

        require(
            metadata.size() == 2,
            "Version count incorrect."
        );

        require(
            metadata.get(0).state() == SecretState.REVOKED,
            "Old credential was not revoked."
        );

        require(
            metadata.get(1).state() == SecretState.ACTIVE,
            "New credential is not active."
        );

        // Active credential revocation must fail.
        try {
            manager.revoke(
                "payment-api",
                result.activeVersion(),
                "security-admin"
            );

            throw new AssertionError(
                "Active credential was revoked."
            );

        } catch (StateException expected) {
            System.out.println(
                "Active-version protection: PASSED"
            );
        }

        System.out.println(
            "Configuration validation: PASSED"
        );

        System.out.println(
            "Credential rotation: PASSED"
        );

        System.out.println(
            "Version revocation: PASSED"
        );

        System.out.println(
            "Audit events: " +
            manager.auditLog("auditor").size()
        );

        System.out.println(
            "All enterprise checks passed."
        );
    }
}
