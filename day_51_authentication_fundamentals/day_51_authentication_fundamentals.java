import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

public class AuthenticationFundamentals {

    enum AccountStatus {
        ACTIVE,
        LOCKED,
        DISABLED
    }

    enum SessionStatus {
        ACTIVE,
        REVOKED,
        EXPIRED
    }

    enum Role {
        USER,
        ADMINISTRATOR,
        AUDITOR
    }

    static final class AuthenticationException extends Exception {
        AuthenticationException(String message) {
            super(message);
        }
    }

    static final class AuthorizationException extends Exception {
        AuthorizationException(String message) {
            super(message);
        }
    }

    record PasswordRecord(
        String algorithm,
        byte[] salt,
        byte[] verifier,
        int iterations
    ) {
        PasswordRecord {
            Objects.requireNonNull(algorithm);
            Objects.requireNonNull(salt);
            Objects.requireNonNull(verifier);
        }
    }

    record Identity(
        long id,
        String username,
        PasswordRecord credential,
        Set<Role> roles,
        AccountStatus status,
        int failedAttempts
    ) {
        Identity {
            roles = Collections.unmodifiableSet(EnumSet.copyOf(roles));
        }

        Identity withFailedAttempts(int value) {
            return new Identity(
                id,
                username,
                credential,
                roles,
                value >= 5 ? AccountStatus.LOCKED : status,
                value
            );
        }

        Identity withRoles(Set<Role> updatedRoles) {
            return new Identity(
                id,
                username,
                credential,
                updatedRoles,
                status,
                failedAttempts
            );
        }
    }

    record Session(
        String token,
        long identityId,
        Instant createdAt,
        Instant expiresAt,
        SessionStatus status
    ) {
        Session revoke() {
            return new Session(
                token,
                identityId,
                createdAt,
                expiresAt,
                SessionStatus.REVOKED
            );
        }

        Session expire() {
            return new Session(
                token,
                identityId,
                createdAt,
                expiresAt,
                SessionStatus.EXPIRED
            );
        }
    }

    interface PasswordVerifier {
        PasswordRecord create(String password);

        boolean matches(String password, PasswordRecord record);
    }

    static final class Pbkdf2PasswordVerifier
        implements PasswordVerifier {

        private static final int ITERATIONS = 210_000;

        @Override
        public PasswordRecord create(String password) {
            if (password == null || password.length() < 12) {
                throw new IllegalArgumentException(
                    "Password must contain at least 12 characters."
                );
            }

            byte[] salt = UUID.randomUUID()
                .toString()
                .getBytes(java.nio.charset.StandardCharsets.UTF_8);

            byte[] verifier = derive(password, salt, ITERATIONS);

            return new PasswordRecord(
                "PBKDF2-HMAC-SHA256",
                salt,
                verifier,
                ITERATIONS
            );
        }

        @Override
        public boolean matches(
            String password,
            PasswordRecord record
        ) {
            byte[] candidate = derive(
                password,
                record.salt(),
                record.iterations()
            );

            return java.security.MessageDigest.isEqual(
                candidate,
                record.verifier()
            );
        }

        private byte[] derive(
            String password,
            byte[] salt,
            int iterations
        ) {
            try {
                var specification =
                    new javax.crypto.spec.PBEKeySpec(
                        password.toCharArray(),
                        salt,
                        iterations,
                        256
                    );

                var factory =
                    javax.crypto.SecretKeyFactory.getInstance(
                        "PBKDF2WithHmacSHA256"
                    );

                return factory.generateSecret(specification)
                    .getEncoded();

            } catch (java.security.GeneralSecurityException ex) {
                throw new IllegalStateException(
                    "Password derivation failed.",
                    ex
                );
            }
        }
    }

    static final class RepositoryService {

        private final Map<String, Identity> identities = new HashMap<>();
        private final Map<String, Session> sessions = new HashMap<>();
        private final PasswordVerifier passwordVerifier =
            new Pbkdf2PasswordVerifier();

        private long nextIdentityId = 1;
        private final Duration sessionLifetime =
            Duration.ofMinutes(30);

        Identity register(
            String username,
            String password,
            Set<Role> roles
        ) {
            String normalized = username.trim().toLowerCase();

            if (normalized.isBlank()) {
                throw new IllegalArgumentException(
                    "Username cannot be empty."
                );
            }

            if (identities.containsKey(normalized)) {
                throw new IllegalArgumentException(
                    "Username already exists."
                );
            }

            if (roles.isEmpty()) {
                throw new IllegalArgumentException(
                    "An identity must have at least one role."
                );
            }

            Identity identity = new Identity(
                nextIdentityId++,
                normalized,
                passwordVerifier.create(password),
                roles,
                AccountStatus.ACTIVE,
                0
            );

            identities.put(normalized, identity);
            return identity;
        }

        Session authenticate(
            String username,
            String password
        ) throws AuthenticationException {
            String normalized = username.trim().toLowerCase();

            Identity identity = identities.get(normalized);

            if (identity == null) {
                throw new AuthenticationException(
                    "Invalid credentials."
                );
            }

            if (identity.status() != AccountStatus.ACTIVE) {
                throw new AuthenticationException(
                    "Account is not active."
                );
            }

            if (!passwordVerifier.matches(
                password,
                identity.credential()
            )) {
                Identity failed = identity.withFailedAttempts(
                    identity.failedAttempts() + 1
                );

                identities.put(normalized, failed);

                throw new AuthenticationException(
                    "Invalid credentials."
                );
            }

            identities.put(
                normalized,
                new Identity(
                    identity.id(),
                    identity.username(),
                    identity.credential(),
                    identity.roles(),
                    identity.status(),
                    0
                )
            );

            Instant now = Instant.now();

            Session session = new Session(
                UUID.randomUUID().toString(),
                identity.id(),
                now,
                now.plus(sessionLifetime),
                SessionStatus.ACTIVE
            );

            sessions.put(session.token(), session);
            return session;
        }

        Identity authenticateSession(
            String token
        ) throws AuthenticationException {
            Session session = sessions.get(token);

            if (session == null) {
                throw new AuthenticationException(
                    "Unknown session."
                );
            }

            if (session.status() != SessionStatus.ACTIVE) {
                throw new AuthenticationException(
                    "Session is not active."
                );
            }

            if (Instant.now().isAfter(session.expiresAt())) {
                sessions.put(token, session.expire());

                throw new AuthenticationException(
                    "Session has expired."
                );
            }

            Optional<Identity> identity = identities.values()
                .stream()
                .filter(candidate ->
                    candidate.id() == session.identityId())
                .findFirst();

            if (identity.isEmpty() ||
                identity.get().status() != AccountStatus.ACTIVE) {
                throw new AuthenticationException(
                    "Identity is not active."
                );
            }

            return identity.get();
        }

        Identity authorize(
            String token,
            Role requiredRole
        ) throws AuthenticationException, AuthorizationException {
            Identity identity = authenticateSession(token);

            if (!identity.roles().contains(requiredRole)) {
                throw new AuthorizationException(
                    "Required role is missing: " + requiredRole
                );
            }

            return identity;
        }

        void revoke(String token) {
            Session session = sessions.get(token);

            if (session != null) {
                sessions.put(token, session.revoke());
            }
        }
    }

    public static void main(String[] args) {
        try {
            RepositoryService repository = new RepositoryService();

            Identity alice = repository.register(
                "alice",
                "CorrectHorseBattery9!",
                EnumSet.of(Role.USER)
            );

            Session session = repository.authenticate(
                alice.username(),
                "CorrectHorseBattery9!"
            );

            Identity authenticated =
                repository.authenticateSession(session.token());

            System.out.println(
                "Authenticated identity: " +
                authenticated.username()
            );

            try {
                repository.authorize(
                    session.token(),
                    Role.ADMINISTRATOR
                );
            } catch (AuthorizationException ex) {
                System.out.println(
                    "Authorization denied: " +
                    ex.getMessage()
                );
            }

            Identity promoted = authenticated.withRoles(
                EnumSet.of(Role.USER, Role.ADMINISTRATOR)
            );

            System.out.println(
                "Role policy updated for: " +
                promoted.username()
            );

            System.out.println(
                "Administrator authorization: " +
                repository.authorize(
                    session.token(),
                    Role.ADMINISTRATOR
                ).username()
            );

            repository.revoke(session.token());

            try {
                repository.authenticateSession(session.token());
            } catch (AuthenticationException ex) {
                System.out.println(
                    "Revoked session rejected: " +
                    ex.getMessage()
                );
            }

            for (int attempt = 1; attempt <= 5; attempt++) {
                try {
                    repository.authenticate(
                        "alice",
                        "incorrect-password"
                    );
                } catch (AuthenticationException ex) {
                    System.out.println(
                        "Failed authentication attempt " +
                        attempt +
                        ": " +
                        ex.getMessage()
                    );
                }
            }

        } catch (Exception ex) {
            System.err.println(
                "Application failure: " +
                ex.getMessage()
            );
        }
    }
}
