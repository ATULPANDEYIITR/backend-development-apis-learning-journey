import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Enterprise-oriented API key lifecycle service.
 *
 * Java 17 or later. Uses only JDK classes.
 */
public class ApiKeyLifecycle {

    private static final Pattern KEY_PATTERN = Pattern.compile(
        "^ak_live_([a-f0-9]{16})\\.([A-Za-z0-9_-]{43})$"
    );

    private static final Pattern SCOPE_PATTERN = Pattern.compile(
        "^[a-z][a-z0-9:_-]{0,63}$"
    );

    private static final Duration MAX_LIFETIME = Duration.ofDays(365);
    private static final SecureRandom RANDOM = new SecureRandom();

    enum KeyStatus {
        ACTIVE,
        REVOKED
    }

    record IssuedKey(String keyId, String token) {
        @Override
        public String toString() {
            return "IssuedKey[keyId=" + keyId + ", token=<redacted>]";
        }
    }

    record ValidationResult(
        boolean accepted,
        String reason,
        String keyId,
        String owner
    ) {}

    record KeyMetadata(
        String keyId,
        String owner,
        String label,
        KeyStatus status,
        Set<String> scopes,
        Instant createdAt,
        Instant expiresAt,
        Instant lastUsedAt,
        Instant revokedAt,
        String rotatedFrom
    ) {}

    record AuditEvent(
        String eventType,
        String keyId,
        String actor,
        Instant occurredAt,
        String relatedKeyId
    ) {}

    record KeyPolicy(
        Duration maximumLifetime,
        boolean requireExpiration
    ) {
        KeyPolicy {
            if (
                maximumLifetime == null ||
                maximumLifetime.isNegative() ||
                maximumLifetime.isZero() ||
                maximumLifetime.compareTo(MAX_LIFETIME) > 0
            ) {
                throw new IllegalArgumentException("Invalid maximum key lifetime.");
            }
        }
    }

    static final class KeyLifecycleException extends RuntimeException {
        KeyLifecycleException(String message) {
            super(message);
        }
    }

    static final class KeyNotFoundException extends KeyLifecycleException {
        KeyNotFoundException() {
            super("The requested API key could not be found or authenticated.");
        }
    }

    static final class KeyStateException extends KeyLifecycleException {
        KeyStateException(String message) {
            super(message);
        }
    }

    interface PrincipalDirectory {
        Set<String> allowedScopes(String principalId);
        boolean isActive(String principalId);
    }

    static final class StaticPrincipalDirectory implements PrincipalDirectory {
        private final Map<String, Set<String>> policies;

        StaticPrincipalDirectory(Map<String, Set<String>> policies) {
            Map<String, Set<String>> copied = new HashMap<>();

            policies.forEach((principal, scopes) ->
                copied.put(principal, Set.copyOf(scopes))
            );

            this.policies = Collections.unmodifiableMap(copied);
        }

        @Override
        public Set<String> allowedScopes(String principalId) {
            return policies.getOrDefault(principalId, Set.of());
        }

        @Override
        public boolean isActive(String principalId) {
            return policies.containsKey(principalId);
        }
    }

    /*
     * Internal record. The verifier array is copied on construction and is
     * never included in public metadata or audit events.
     */
    static final class StoredKey {
        private final String keyId;
        private final String owner;
        private final String label;
        private final byte[] verifier;
        private final Set<String> scopes;
        private final Instant createdAt;
        private final Instant expiresAt;
        private final String rotatedFrom;

        private KeyStatus status;
        private Instant lastUsedAt;
        private Instant revokedAt;

        StoredKey(
            String keyId,
            String owner,
            String label,
            byte[] verifier,
            Set<String> scopes,
            Instant createdAt,
            Instant expiresAt,
            String rotatedFrom
        ) {
            this.keyId = keyId;
            this.owner = owner;
            this.label = label;
            this.verifier = verifier.clone();
            this.scopes = Set.copyOf(scopes);
            this.createdAt = createdAt;
            this.expiresAt = expiresAt;
            this.rotatedFrom = rotatedFrom;
            this.status = KeyStatus.ACTIVE;
        }

        byte[] verifierCopy() {
            return verifier.clone();
        }

        KeyMetadata metadata() {
            return new KeyMetadata(
                keyId,
                owner,
                label,
                status,
                scopes,
                createdAt,
                expiresAt,
                lastUsedAt,
                revokedAt,
                rotatedFrom
            );
        }
    }

    interface KeyRepository {
        Optional<StoredKey> find(String keyId);
        void save(StoredKey key);
        List<StoredKey> findAll();
    }

    /*
     * Repository abstraction keeps key lifecycle rules independent of the
     * storage implementation. This implementation is intentionally in-memory.
     */
    static final class InMemoryKeyRepository implements KeyRepository {
        private final Map<String, StoredKey> records = new HashMap<>();

        @Override
        public synchronized Optional<StoredKey> find(String keyId) {
            return Optional.ofNullable(records.get(keyId));
        }

        @Override
        public synchronized void save(StoredKey key) {
            records.put(key.keyId, key);
        }

        @Override
        public synchronized List<StoredKey> findAll() {
            return new ArrayList<>(records.values());
        }
    }

    static final class APIKeyService {
        private final KeyRepository repository;
        private final PrincipalDirectory principals;
        private final KeyPolicy policy;
        private final byte[] pepper;
        private final List<AuditEvent> events = new ArrayList<>();

        APIKeyService(
            KeyRepository repository,
            PrincipalDirectory principals,
            KeyPolicy policy,
            byte[] pepper
        ) {
            if (pepper == null || pepper.length < 32) {
                throw new IllegalArgumentException(
                    "The pepper must contain at least 32 bytes."
                );
            }

            this.repository = repository;
            this.principals = principals;
            this.policy = policy;
            this.pepper = pepper.clone();
        }

        private static String requiredText(
            String value,
            String field,
            int maximum
        ) {
            if (
                value == null ||
                value.isBlank() ||
                value.trim().length() > maximum
            ) {
                throw new IllegalArgumentException(
                    field + " must contain 1 to " + maximum + " characters."
                );
            }

            return value.trim();
        }

        private static Set<String> normalizeScopes(Set<String> scopes) {
            if (scopes == null || scopes.isEmpty()) {
                throw new IllegalArgumentException("At least one scope is required.");
            }

            Set<String> normalized = scopes.stream()
                .map(scope -> requiredText(scope, "scope", 64))
                .collect(Collectors.toUnmodifiableSet());

            for (String scope : normalized) {
                if (!SCOPE_PATTERN.matcher(scope).matches()) {
                    throw new IllegalArgumentException("Invalid scope: " + scope);
                }
            }

            return normalized;
        }

        private void validateLifetime(Duration lifetime) {
            if (lifetime == null) {
                if (policy.requireExpiration()) {
                    throw new IllegalArgumentException(
                        "The policy requires an expiration time."
                    );
                }
                return;
            }

            if (
                lifetime.isNegative() ||
                lifetime.isZero() ||
                lifetime.compareTo(policy.maximumLifetime()) > 0
            ) {
                throw new IllegalArgumentException(
                    "Lifetime exceeds the configured key policy."
                );
            }
        }

        private byte[] digest(String secret) {
            try {
                Mac mac = Mac.getInstance("HmacSHA256");
                mac.init(new SecretKeySpec(pepper, "HmacSHA256"));

                return mac.doFinal(
                    secret.getBytes(StandardCharsets.UTF_8)
                );
            } catch (Exception exception) {
                throw new IllegalStateException(
                    "HMAC initialization failed.",
                    exception
                );
            }
        }

        private static String randomHex(int byteCount) {
            byte[] bytes = new byte[byteCount];
            RANDOM.nextBytes(bytes);

            StringBuilder output = new StringBuilder(byteCount * 2);

            for (byte value : bytes) {
                output.append(String.format("%02x", value & 0xff));
            }

            return output.toString();
        }

        private static String randomSecret() {
            byte[] secret = new byte[32];
            RANDOM.nextBytes(secret);

            return Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(secret);
        }

        private static ParsedToken parseToken(String token) {
            if (token == null) {
                return null;
            }

            var matcher = KEY_PATTERN.matcher(token);

            if (!matcher.matches()) {
                return null;
            }

            return new ParsedToken(matcher.group(1), matcher.group(2));
        }

        private record ParsedToken(String keyId, String secret) {}

        private void addEvent(
            String eventType,
            StoredKey key,
            String actor,
            String relatedKeyId
        ) {
            events.add(new AuditEvent(
                eventType,
                key.keyId,
                actor,
                Instant.now(),
                relatedKeyId
            ));
        }

        private IssuedKey issueInternal(
            String owner,
            String label,
            Set<String> scopes,
            Instant expiresAt,
            String actor,
            String rotatedFrom
        ) {
            String keyId = randomHex(8);
            String secret = randomSecret();
            String token = "ak_live_" + keyId + "." + secret;

            StoredKey stored = new StoredKey(
                keyId,
                owner,
                label,
                digest(secret),
                scopes,
                Instant.now(),
                expiresAt,
                rotatedFrom
            );

            repository.save(stored);
            addEvent("issued", stored, actor, rotatedFrom);

            return new IssuedKey(keyId, token);
        }

        private StoredKey authenticate(ParsedToken parsed) {
            StoredKey key = repository.find(parsed.keyId())
                .orElseThrow(KeyNotFoundException::new);

            byte[] candidate = digest(parsed.secret());

            if (!MessageDigest.isEqual(candidate, key.verifierCopy())) {
                throw new KeyNotFoundException();
            }

            return key;
        }

        public synchronized IssuedKey issue(
            String owner,
            String label,
            Set<String> requestedScopes,
            Duration lifetime,
            String actor
        ) {
            owner = requiredText(owner, "owner", 120);
            label = requiredText(label, "label", 120);
            actor = requiredText(actor, "actor", 120);

            Set<String> scopes = normalizeScopes(requestedScopes);
            validateLifetime(lifetime);

            if (!principals.isActive(owner)) {
                throw new IllegalArgumentException("The owner is not active.");
            }

            Set<String> allowedScopes = principals.allowedScopes(owner);

            if (
                !allowedScopes.contains("*") &&
                !allowedScopes.containsAll(scopes)
            ) {
                throw new IllegalArgumentException(
                    "The owner is not authorized for all requested scopes."
                );
            }

            Instant expiresAt = lifetime == null
                ? null
                : Instant.now().plus(lifetime);

            return issueInternal(
                owner,
                label,
                scopes,
                expiresAt,
                actor,
                null
            );
        }

        public synchronized ValidationResult validate(
            String token,
            String requiredScope
        ) {
            if (
                requiredScope == null ||
                !SCOPE_PATTERN.matcher(requiredScope).matches()
            ) {
                return new ValidationResult(
                    false, "invalid_scope", null, null
                );
            }

            ParsedToken parsed = parseToken(token);

            if (parsed == null) {
                return new ValidationResult(
                    false, "malformed_token", null, null
                );
            }

            final StoredKey key;

            try {
                key = authenticate(parsed);
            } catch (KeyNotFoundException exception) {
                return new ValidationResult(
                    false, "invalid_credentials", null, null
                );
            }

            if (key.status != KeyStatus.ACTIVE) {
                return new ValidationResult(
                    false, "revoked", key.keyId, key.owner
                );
            }

            if (
                key.expiresAt != null &&
                !key.expiresAt.isAfter(Instant.now())
            ) {
                return new ValidationResult(
                    false, "expired", key.keyId, key.owner
                );
            }

            if (
                !key.scopes.contains(requiredScope) &&
                !key.scopes.contains("*")
            ) {
                return new ValidationResult(
                    false, "insufficient_scope", key.keyId, key.owner
                );
            }

            key.lastUsedAt = Instant.now();

            return new ValidationResult(
                true, "accepted", key.keyId, key.owner
            );
        }

        public synchronized IssuedKey rotate(
            String oldToken,
            String actor,
            Duration replacementLifetime
        ) {
            actor = requiredText(actor, "actor", 120);

            ParsedToken parsed = parseToken(oldToken);

            if (parsed == null) {
                throw new IllegalArgumentException("The supplied token is malformed.");
            }

            StoredKey oldKey = authenticate(parsed);

            if (oldKey.status != KeyStatus.ACTIVE) {
                throw new KeyStateException("Only an active key can be rotated.");
            }

            Instant now = Instant.now();

            if (
                oldKey.expiresAt != null &&
                !oldKey.expiresAt.isAfter(now)
            ) {
                throw new KeyStateException("An expired key cannot be rotated.");
            }

            Duration effectiveLifetime;

            if (replacementLifetime != null) {
                effectiveLifetime = replacementLifetime;
            } else if (oldKey.expiresAt != null) {
                effectiveLifetime = Duration.between(now, oldKey.expiresAt);
            } else {
                effectiveLifetime = null;
            }

            validateLifetime(effectiveLifetime);

            Instant newExpiration = effectiveLifetime == null
                ? null
                : now.plus(effectiveLifetime);

            IssuedKey replacement = issueInternal(
                oldKey.owner,
                oldKey.label,
                oldKey.scopes,
                newExpiration,
                actor,
                oldKey.keyId
            );

            oldKey.status = KeyStatus.REVOKED;
            oldKey.revokedAt = now;

            addEvent(
                "rotated",
                oldKey,
                actor,
                replacement.keyId()
            );

            return replacement;
        }

        public synchronized boolean revoke(String keyId, String actor) {
            keyId = requiredText(keyId, "keyId", 32);
            actor = requiredText(actor, "actor", 120);

            StoredKey key = repository.find(keyId)
                .orElseThrow(KeyNotFoundException::new);

            if (key.status == KeyStatus.REVOKED) {
                return false;
            }

            key.status = KeyStatus.REVOKED;
            key.revokedAt = Instant.now();

            addEvent("revoked", key, actor, null);

            return true;
        }

        public synchronized KeyMetadata metadata(String keyId) {
            return repository.find(keyId)
                .orElseThrow(KeyNotFoundException::new)
                .metadata();
        }

        public synchronized List<AuditEvent> auditEvents(String keyId) {
            return events.stream()
                .filter(event -> event.keyId().equals(keyId))
                .toList();
        }

        public synchronized List<KeyMetadata> inventory() {
            return repository.findAll().stream()
                .map(StoredKey::metadata)
                .toList();
        }
    }

    public static void main(String[] args) {
        try {
            byte[] pepper = new byte[32];

            String configuredPepper = System.getenv("API_KEY_PEPPER");

            if (configuredPepper != null && !configuredPepper.isBlank()) {
                pepper = configuredPepper.getBytes(StandardCharsets.UTF_8);

                if (pepper.length < 32) {
                    throw new IllegalArgumentException(
                        "API_KEY_PEPPER must contain at least 32 bytes."
                    );
                }
            } else {
                // Process-local key for this executable demonstration only.
                RANDOM.nextBytes(pepper);
            }

            PrincipalDirectory directory = new StaticPrincipalDirectory(
                Map.of(
                    "inventory-service",
                    Set.of("inventory:read", "inventory:update")
                )
            );

            KeyRepository repository = new InMemoryKeyRepository();

            APIKeyService service = new APIKeyService(
                repository,
                directory,
                new KeyPolicy(Duration.ofDays(365), true),
                pepper
            );

            IssuedKey original = service.issue(
                "inventory-service",
                "warehouse integration",
                Set.of("inventory:read", "inventory:update"),
                Duration.ofDays(30),
                "platform-admin"
            );

            System.out.println("Issued key ID: " + original.keyId());
            System.out.println("One-time token: " + original.token());

            ValidationResult accepted = service.validate(
                original.token(),
                "inventory:read"
            );

            if (!accepted.accepted()) {
                throw new IllegalStateException("Expected a valid key.");
            }

            ValidationResult denied = service.validate(
                original.token(),
                "billing:write"
            );

            if (!"insufficient_scope".equals(denied.reason())) {
                throw new IllegalStateException("Expected a scope denial.");
            }

            IssuedKey replacement = service.rotate(
                original.token(),
                "security-admin",
                Duration.ofDays(60)
            );

            ValidationResult oldResult = service.validate(
                original.token(),
                "inventory:read"
            );

            if (!"revoked".equals(oldResult.reason())) {
                throw new IllegalStateException(
                    "The old key must be revoked after rotation."
                );
            }

            ValidationResult replacementResult = service.validate(
                replacement.token(),
                "inventory:read"
            );

            if (!replacementResult.accepted()) {
                throw new IllegalStateException(
                    "The replacement key should be accepted."
                );
            }

            service.revoke(replacement.keyId(), "security-admin");

            ValidationResult revoked = service.validate(
                replacement.token(),
                "inventory:read"
            );

            if (!"revoked".equals(revoked.reason())) {
                throw new IllegalStateException(
                    "The revoked key must be rejected."
                );
            }

            System.out.println("\nReplacement metadata:");
            System.out.println(service.metadata(replacement.keyId()));

            System.out.println("\nReplacement audit events:");
            service.auditEvents(replacement.keyId())
                .forEach(System.out::println);

            System.out.println("\nAll lifecycle assertions passed.");

        } catch (Exception exception) {
            // Do not include API key values in operational error messages.
            System.err.println(
                "API key lifecycle failure: " + exception.getMessage()
            );
            System.exit(1);
        }
    }
}
