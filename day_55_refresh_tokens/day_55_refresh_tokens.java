import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Enterprise refresh-token lifecycle model.
 *
 * Compile: javac RefreshTokenGovernance.java
 * Run:     java RefreshTokenGovernance
 */
public class RefreshTokenGovernance {

    enum SessionState {
        ACTIVE, REVOKED, EXPIRED
    }

    enum TokenState {
        ACTIVE, ROTATED, REVOKED, EXPIRED
    }

    enum FailureCode {
        INVALID_TOKEN,
        EXPIRED_TOKEN,
        REVOKED_SESSION,
        TOKEN_REUSE,
        UNKNOWN_SESSION,
        INVALID_CONFIGURATION
    }

    static final class AuthenticationException extends RuntimeException {
        private final FailureCode code;

        AuthenticationException(FailureCode code, String message) {
            super(message);
            this.code = code;
        }

        FailureCode code() {
            return code;
        }
    }

    record TokenPair(
        String accessToken,
        String refreshToken,
        Instant accessExpiresAt,
        Instant refreshExpiresAt,
        long generation
    ) {}

    record Principal(String userId, String sessionId, Instant expiresAt) {}

    record AuditEvent(
        Instant timestamp,
        String eventType,
        String sessionId,
        long generation
    ) {}

    record PolicyResult(boolean allowed, String reason) {}

    static final class Session {
        private final String id;
        private final String userId;
        private final Instant createdAt;
        private final Instant expiresAt;
        private String currentRefreshHash;
        private SessionState state = SessionState.ACTIVE;
        private long generation;

        Session(String id, String userId, Instant createdAt, Instant expiresAt) {
            this.id = id;
            this.userId = userId;
            this.createdAt = createdAt;
            this.expiresAt = expiresAt;
        }
    }

    static final class TokenRecord {
        private final String sessionId;
        private final Instant expiresAt;
        private final long generation;
        private TokenState state;

        TokenRecord(
            String sessionId,
            Instant expiresAt,
            long generation,
            TokenState state
        ) {
            this.sessionId = sessionId;
            this.expiresAt = expiresAt;
            this.generation = generation;
            this.state = state;
        }
    }

    interface TokenPolicy {
        Duration accessLifetime();
        Duration refreshLifetime();
        boolean revokeSessionOnRefreshReuse();
    }

    record StandardTokenPolicy(
        Duration accessLifetime,
        Duration refreshLifetime,
        boolean revokeSessionOnRefreshReuse
    ) implements TokenPolicy {
        StandardTokenPolicy {
            Objects.requireNonNull(accessLifetime);
            Objects.requireNonNull(refreshLifetime);

            if (accessLifetime.isZero() || accessLifetime.isNegative()
                || refreshLifetime.compareTo(accessLifetime) <= 0) {
                throw new AuthenticationException(
                    FailureCode.INVALID_CONFIGURATION,
                    "Refresh lifetime must exceed positive access lifetime"
                );
            }
        }
    }

    static final class TokenService {
        private final Clock clock;
        private final TokenPolicy policy;
        private final SecureRandom secureRandom = new SecureRandom();
        private final ReentrantLock lock = new ReentrantLock();

        private final Map<String, Session> sessions = new HashMap<>();
        private final Map<String, TokenRecord> refreshTokens = new HashMap<>();
        private final Map<String, TokenRecord> accessTokens = new HashMap<>();
        private final List<AuditEvent> audit = new ArrayList<>();

        TokenService(Clock clock, TokenPolicy policy) {
            this.clock = Objects.requireNonNull(clock);
            this.policy = Objects.requireNonNull(policy);
        }

        private String newToken() {
            byte[] bytes = new byte[48];
            secureRandom.nextBytes(bytes);
            return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        }

        private String hash(String token) {
            try {
                var digest = java.security.MessageDigest.getInstance("SHA-256");
                byte[] result = digest.digest(
                    token.getBytes(java.nio.charset.StandardCharsets.UTF_8)
                );
                return java.util.HexFormat.of().formatHex(result);
            } catch (java.security.NoSuchAlgorithmException exception) {
                throw new IllegalStateException("SHA-256 unavailable", exception);
            }
        }

        private void recordEvent(String type, Session session) {
            // Never put raw bearer credentials into audit events.
            audit.add(new AuditEvent(
                clock.instant(), type, session.id, session.generation
            ));
        }

        TokenPair login(String userId) {
            if (userId == null || userId.isBlank()) {
                throw new IllegalArgumentException("User ID is required");
            }

            lock.lock();
            try {
                Instant now = clock.instant();
                Session session = new Session(
                    UUID.randomUUID().toString(),
                    userId.strip(),
                    now,
                    now.plus(policy.refreshLifetime())
                );
                sessions.put(session.id, session);
                TokenPair pair = issuePair(session, now);
                recordEvent("session.created", session);
                return pair;
            } finally {
                lock.unlock();
            }
        }

        private TokenPair issuePair(Session session, Instant now) {
            String access = newToken();
            String refresh = newToken();

            session.generation++;
            session.currentRefreshHash = hash(refresh);

            Instant accessExpiry = now.plus(policy.accessLifetime());
            if (accessExpiry.isAfter(session.expiresAt)) {
                accessExpiry = session.expiresAt;
            }

            accessTokens.put(
                hash(access),
                new TokenRecord(
                    session.id, accessExpiry, session.generation, TokenState.ACTIVE
                )
            );
            refreshTokens.put(
                session.currentRefreshHash,
                new TokenRecord(
                    session.id, session.expiresAt,
                    session.generation, TokenState.ACTIVE
                )
            );

            return new TokenPair(
                access, refresh, accessExpiry, session.expiresAt, session.generation
            );
        }

        Principal authenticateAccess(String token) {
            if (token == null || token.isBlank()) {
                throw new AuthenticationException(
                    FailureCode.INVALID_TOKEN, "Access token is missing"
                );
            }

            lock.lock();
            try {
                TokenRecord record = accessTokens.get(hash(token));
                if (record == null) {
                    throw new AuthenticationException(
                        FailureCode.INVALID_TOKEN, "Access token is invalid"
                    );
                }

                Session session = sessions.get(record.sessionId);
                if (session == null) {
                    throw new AuthenticationException(
                        FailureCode.UNKNOWN_SESSION, "Session does not exist"
                    );
                }
                if (session.state == SessionState.REVOKED) {
                    throw new AuthenticationException(
                        FailureCode.REVOKED_SESSION, "Session has been revoked"
                    );
                }

                Instant now = clock.instant();
                if (session.state == SessionState.EXPIRED
                    || !now.isBefore(session.expiresAt)
                    || !now.isBefore(record.expiresAt)) {
                    throw new AuthenticationException(
                        FailureCode.EXPIRED_TOKEN, "Access token has expired"
                    );
                }

                return new Principal(
                    session.userId, session.id, record.expiresAt
                );
            } finally {
                lock.unlock();
            }
        }

        TokenPair refresh(String rawRefreshToken) {
            if (rawRefreshToken == null || rawRefreshToken.isBlank()) {
                throw new AuthenticationException(
                    FailureCode.INVALID_TOKEN, "Refresh token is missing"
                );
            }

            lock.lock();
            try {
                String tokenHash = hash(rawRefreshToken);
                TokenRecord record = refreshTokens.get(tokenHash);

                if (record == null) {
                    throw new AuthenticationException(
                        FailureCode.INVALID_TOKEN, "Refresh token is invalid"
                    );
                }

                Session session = sessions.get(record.sessionId);
                if (session == null) {
                    throw new AuthenticationException(
                        FailureCode.UNKNOWN_SESSION, "Session does not exist"
                    );
                }
                if (session.state == SessionState.REVOKED) {
                    throw new AuthenticationException(
                        FailureCode.REVOKED_SESSION, "Session has been revoked"
                    );
                }

                Instant now = clock.instant();
                if (session.state == SessionState.EXPIRED
                    || !now.isBefore(session.expiresAt)
                    || !now.isBefore(record.expiresAt)) {
                    session.state = SessionState.EXPIRED;
                    record.state = TokenState.EXPIRED;
                    recordEvent("refresh.expired", session);
                    throw new AuthenticationException(
                        FailureCode.EXPIRED_TOKEN, "Refresh token has expired"
                    );
                }

                if (record.state != TokenState.ACTIVE
                    || !session.currentRefreshHash.equals(tokenHash)
                    || record.generation != session.generation) {
                    recordEvent("refresh.reuse_detected", session);

                    if (policy.revokeSessionOnRefreshReuse()) {
                        revokeSessionLocked(session);
                    }

                    throw new AuthenticationException(
                        FailureCode.TOKEN_REUSE,
                        "Refresh token is rotated, revoked, or stale"
                    );
                }

                record.state = TokenState.ROTATED;
                recordEvent("refresh.rotated", session);
                return issuePair(session, now);
            } finally {
                lock.unlock();
            }
        }

        private void revokeSessionLocked(Session session) {
            session.state = SessionState.REVOKED;

            for (TokenRecord record : refreshTokens.values()) {
                if (record.sessionId.equals(session.id)) {
                    record.state = TokenState.REVOKED;
                }
            }
            recordEvent("session.revoked", session);
        }

        boolean revokeSession(String sessionId) {
            lock.lock();
            try {
                Session session = sessions.get(sessionId);
                if (session == null || session.state == SessionState.REVOKED) {
                    return false;
                }
                revokeSessionLocked(session);
                return true;
            } finally {
                lock.unlock();
            }
        }

        PolicyResult evaluateRefresh(String rawRefreshToken) {
            if (rawRefreshToken == null || rawRefreshToken.isBlank()) {
                return new PolicyResult(false, "missing_token");
            }

            lock.lock();
            try {
                TokenRecord record = refreshTokens.get(hash(rawRefreshToken));
                if (record == null) {
                    return new PolicyResult(false, "invalid_token");
                }

                Session session = sessions.get(record.sessionId);
                if (session == null) {
                    return new PolicyResult(false, "unknown_session");
                }
                if (session.state != SessionState.ACTIVE) {
                    return new PolicyResult(false, session.state.name().toLowerCase());
                }
                if (!clock.instant().isBefore(session.expiresAt)
                    || !clock.instant().isBefore(record.expiresAt)) {
                    return new PolicyResult(false, "expired");
                }
                if (record.state != TokenState.ACTIVE
                    || !session.currentRefreshHash.equals(hash(rawRefreshToken))
                    || record.generation != session.generation) {
                    return new PolicyResult(false, "stale_or_reused_token");
                }

                return new PolicyResult(true, "eligible");
            } finally {
                lock.unlock();
            }
        }

        List<AuditEvent> auditSnapshot() {
            lock.lock();
            try {
                return Collections.unmodifiableList(new ArrayList<>(audit));
            } finally {
                lock.unlock();
            }
        }

        Optional<SessionState> sessionState(String sessionId) {
            lock.lock();
            try {
                Session session = sessions.get(sessionId);
                return session == null
                    ? Optional.empty()
                    : Optional.of(session.state);
            } finally {
                lock.unlock();
            }
        }
    }

    public static void main(String[] args) {
        TokenPolicy policy = new StandardTokenPolicy(
            Duration.ofMinutes(5),
            Duration.ofHours(8),
            true
        );

        TokenService service = new TokenService(Clock.systemUTC(), policy);

        TokenPair initial = service.login("employee-204");
        Principal principal = service.authenticateAccess(initial.accessToken());

        System.out.println("Authenticated principal: " + principal.userId());
        System.out.println(
            "Initial refresh eligibility: "
                + service.evaluateRefresh(initial.refreshToken())
        );

        TokenPair rotated = service.refresh(initial.refreshToken());
        System.out.println("Rotation generation: " + rotated.generation());

        try {
            service.refresh(initial.refreshToken());
        } catch (AuthenticationException exception) {
            System.out.println("Reuse rejected: " + exception.code());
        }

        System.out.println(
            "Session state after reuse: "
                + service.sessionState(principal.sessionId()).orElseThrow()
        );
        System.out.println("Audit events: " + service.auditSnapshot().size());
    }
}
