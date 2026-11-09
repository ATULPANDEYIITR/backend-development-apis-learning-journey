/*
 * Secure API Project
 *
 * Enterprise API security and governance model.
 *
 * Java 17
 * Standard library only.
 *
 * Features:
 * - User identity management
 * - PBKDF2 password hashing
 * - HMAC-signed bearer tokens
 * - Authentication service
 * - Role-based authorization
 * - Permission policies
 * - Resource ownership checks
 * - Account status management
 * - Token revocation
 * - Sliding-window rate limiting
 * - Request validation
 * - Security audit events
 * - Explicit API security decisions
 *
 * Compile:
 * javac SecureApi.java
 *
 * Run:
 * java SecureApi
 */

import javax.crypto.Mac;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;

import java.time.Instant;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.Deque;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

// ---------------------------------------------------------
// Application
// ---------------------------------------------------------

public class SecureApi {

    private static final SecureRandom RANDOM =
            new SecureRandom();

    private static final int PASSWORD_ITERATIONS = 310000;

    private static final int TOKEN_LIFETIME_SECONDS = 900;

    private static final int RATE_LIMIT = 20;

    private static final long RATE_WINDOW_MILLIS = 60000;

    private static final int MAX_BODY_BYTES = 16384;

    // -----------------------------------------------------
    // Enumerations
    // -----------------------------------------------------

    enum Role {
        ADMIN,
        EDITOR,
        VIEWER
    }

    enum AccountStatus {
        ACTIVE,
        SUSPENDED,
        DISABLED
    }

    enum TokenStatus {
        VALID,
        EXPIRED,
        REVOKED,
        INVALID
    }

    enum Decision {
        ALLOW,
        DENY
    }

    // -----------------------------------------------------
    // Exceptions
    // -----------------------------------------------------

    static class SecurityException extends RuntimeException {
        private final int statusCode;

        SecurityException(String message, int statusCode) {
            super(message);
            this.statusCode = statusCode;
        }

        int getStatusCode() {
            return statusCode;
        }
    }

    static class AuthenticationException extends SecurityException {
        AuthenticationException(String message) {
            super(message, 401);
        }
    }

    static class AuthorizationException extends SecurityException {
        AuthorizationException(String message) {
            super(message, 403);
        }
    }

    static class ValidationException extends SecurityException {
        ValidationException(String message) {
            super(message, 400);
        }
    }

    static class RateLimitException extends SecurityException {
        RateLimitException() {
            super("Request rate limit exceeded.", 429);
        }
    }

    // -----------------------------------------------------
    // Immutable Domain Records
    // -----------------------------------------------------

    record User(
            String id,
            String username,
            String passwordHash,
            String salt,
            Set<Role> roles,
            AccountStatus status
    ) {
        User {
            if (id == null || username == null ||
                    passwordHash == null || salt == null) {
                throw new ValidationException("Invalid user record.");
            }

            roles = Collections.unmodifiableSet(
                    roles.isEmpty()
                            ? EnumSet.noneOf(Role.class)
                            : EnumSet.copyOf(roles)
            );
        }

        User withStatus(AccountStatus newStatus) {
            return new User(
                    id,
                    username,
                    passwordHash,
                    salt,
                    roles,
                    newStatus
            );
        }
    }

    record AccessToken(
            String token,
            String userId,
            long issuedAt,
            long expiresAt,
            String tokenId
    ) {}

    record APIRequest(
            String method,
            String path,
            String authorization,
            String clientId,
            String resourceId,
            byte[] body
    ) {}

    record APIResponse(
            int statusCode,
            Map<String, Object> body
    ) {}

    record Resource(
            String id,
            String ownerId,
            String content
    ) {}

    record SecurityResult(
            Decision decision,
            int statusCode,
            String reason
    ) {}

    record AuditEvent(
            Instant timestamp,
            String eventType,
            String userId,
            String resource,
            Decision decision,
            String reason
    ) {}

    // -----------------------------------------------------
    // Password Service
    // -----------------------------------------------------

    static class PasswordService {

        static void validate(String password) {
            if (
                    password == null ||
                    password.length() < 12 ||
                    password.length() > 256 ||
                    !password.matches("(?s).*\\p{Lu}.*") ||
                    !password.matches("(?s).*\\p{Ll}.*") ||
                    !password.matches("(?s).*\\d.*") ||
                    !password.matches("(?s).*[^\\p{Alnum}].*")
            ) {
                throw new ValidationException(
                        "Password must contain uppercase, lowercase, " +
                        "numeric and special characters and be at least 12 characters."
                );
            }
        }

        static byte[] derive(String password, byte[] salt) {
            PBEKeySpec specification = new PBEKeySpec(
                    password.toCharArray(),
                    salt,
                    PASSWORD_ITERATIONS,
                    256
            );

            try {
                SecretKeyFactory factory =
                        SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");

                return factory.generateSecret(specification).getEncoded();

            } catch (Exception exception) {
                throw new IllegalStateException(
                        "Password hashing failed.",
                        exception
                );

            } finally {
                specification.clearPassword();
            }
        }

        static String encode(byte[] bytes) {
            return Base64.getEncoder().encodeToString(bytes);
        }

        static String hash(byte[] bytes) {
            return encode(bytes);
        }

        static boolean verify(String password, User user) {
            byte[] calculated = derive(
                    password,
                    Base64.getDecoder().decode(user.salt())
            );

            byte[] stored = Base64.getDecoder().decode(
                    user.passwordHash()
            );

            return MessageDigest.isEqual(calculated, stored);
        }
    }

    // -----------------------------------------------------
    // User Repository
    // -----------------------------------------------------

    static class UserRepository {

        private final Map<String, User> users =
                new ConcurrentHashMap<>();

        private final Map<String, String> usernameIndex =
                new ConcurrentHashMap<>();

        User create(
                String username,
                String password,
                Set<Role> roles
        ) {

            if (
                    username == null ||
                    !username.matches("[A-Za-z0-9_-]{3,64}")
            ) {
                throw new ValidationException("Invalid username.");
            }

            if (roles == null || roles.isEmpty()) {
                throw new ValidationException("At least one role is required.");
            }

            String normalized = username.toLowerCase();

            if (usernameIndex.containsKey(normalized)) {
                throw new ValidationException("Username already exists.");
            }

            PasswordService.validate(password);

            byte[] salt = new byte[16];
            RANDOM.nextBytes(salt);

            byte[] passwordHash = PasswordService.derive(
                    password,
                    salt
            );

            User user = new User(
                    UUID.randomUUID().toString(),
                    username,
                    PasswordService.hash(passwordHash),
                    PasswordService.encode(salt),
                    roles,
                    AccountStatus.ACTIVE
            );

            String previous = usernameIndex.putIfAbsent(
                    normalized,
                    user.id()
            );

            if (previous != null) {
                throw new ValidationException("Username already exists.");
            }

            users.put(user.id(), user);

            return user;
        }

        User findById(String id) {
            return users.get(id);
        }

        User findByUsername(String username) {
            String id = usernameIndex.get(
                    username.toLowerCase()
            );

            return id == null ? null : users.get(id);
        }

        List<User> findActiveUsers() {
            return users.values()
                    .stream()
                    .filter(user ->
                            user.status() == AccountStatus.ACTIVE)
                    .toList();
        }

        void updateStatus(String id, AccountStatus status) {
            users.compute(id, (key, user) -> {
                if (user == null) {
                    throw new ValidationException("User not found.");
                }

                return user.withStatus(status);
            });
        }
    }

    // -----------------------------------------------------
    // Token Service
    // -----------------------------------------------------

    static class TokenService {

        private final byte[] signingSecret;

        private final Map<String, AccessToken> issued =
                new ConcurrentHashMap<>();

        private final Set<String> revoked =
                ConcurrentHashMap.newKeySet();

        TokenService(byte[] secret) {
            if (secret == null || secret.length < 32) {
                throw new IllegalArgumentException(
                        "Signing secret must contain at least 32 bytes."
                );
            }

            signingSecret = secret.clone();
        }

        private String sign(String payload) {
            try {
                Mac mac = Mac.getInstance("HmacSHA256");

                mac.init(new SecretKeySpec(
                        signingSecret,
                        "HmacSHA256"
                ));

                return Base64.getUrlEncoder()
                        .withoutPadding()
                        .encodeToString(
                                mac.doFinal(
                                        payload.getBytes(StandardCharsets.UTF_8)
                                )
                        );

            } catch (Exception exception) {
                throw new IllegalStateException(
                        "Token signing failed.",
                        exception
                );
            }
        }

        AccessToken issue(User user) {
            long now = Instant.now().getEpochSecond();

            String tokenId = UUID.randomUUID().toString();

            long expires = now + TOKEN_LIFETIME_SECONDS;

            String payload = user.id() + "|" +
                    now + "|" +
                    expires + "|" +
                    tokenId;

            String encoded = Base64.getUrlEncoder()
                    .withoutPadding()
                    .encodeToString(
                            payload.getBytes(StandardCharsets.UTF_8)
                    );

            String token = encoded + "." + sign(encoded);

            AccessToken accessToken = new AccessToken(
                    token,
                    user.id(),
                    now,
                    expires,
                    tokenId
            );

            issued.put(tokenId, accessToken);

            return accessToken;
        }

        TokenStatus validate(
                String token,
                String expectedUserId
        ) {

            if (token == null || token.length() > 4096) {
                return TokenStatus.INVALID;
            }

            String[] parts = token.split("\\.", -1);

            if (parts.length != 2) {
                return TokenStatus.INVALID;
            }

            String expectedSignature = sign(parts[0]);

            if (!MessageDigest.isEqual(
                    expectedSignature.getBytes(StandardCharsets.UTF_8),
                    parts[1].getBytes(StandardCharsets.UTF_8)
            )) {
                return TokenStatus.INVALID;
            }

            try {
                String payload = new String(
                        Base64.getUrlDecoder().decode(parts[0]),
                        StandardCharsets.UTF_8
                );

                String[] values = payload.split("\\|", -1);

                if (values.length != 4) {
                    return TokenStatus.INVALID;
                }

                String userId = values[0];
                long issuedAt = Long.parseLong(values[1]);
                long expiresAt = Long.parseLong(values[2]);
                String tokenId = values[3];

                if (!userId.equals(expectedUserId)) {
                    return TokenStatus.INVALID;
                }

                if (revoked.contains(tokenId)) {
                    return TokenStatus.REVOKED;
                }

                AccessToken stored = issued.get(tokenId);

                if (stored == null || !stored.token().equals(token)) {
                    return TokenStatus.INVALID;
                }

                long now = Instant.now().getEpochSecond();

                if (
                        issuedAt > now + 30 ||
                        expiresAt <= issuedAt ||
                        expiresAt - issuedAt > TOKEN_LIFETIME_SECONDS
                ) {
                    return TokenStatus.INVALID;
                }

                if (expiresAt <= now) {
                    return TokenStatus.EXPIRED;
                }

                return TokenStatus.VALID;

            } catch (IllegalArgumentException exception) {
                return TokenStatus.INVALID;
            }
        }

        void revoke(String token) {
            String[] parts = token.split("\\.", -1);

            if (
                    parts.length != 2 ||
                    validate(
                            token,
                            issued.values()
                                    .stream()
                                    .filter(t -> t.token().equals(token))
                                    .map(AccessToken::userId)
                                    .findFirst()
                                    .orElse("")
                    ) != TokenStatus.VALID
            ) {
                throw new AuthenticationException("Invalid token.");
            }

            AccessToken stored = issued.values()
                    .stream()
                    .filter(t -> t.token().equals(token))
                    .findFirst()
                    .orElseThrow();

            revoked.add(stored.tokenId());
        }
    }

    // -----------------------------------------------------
    // Authentication Service
    // -----------------------------------------------------

    static class AuthenticationService {

        private final UserRepository users;
        private final TokenService tokens;

        private final Map<String, Deque<Long>> failures =
                new ConcurrentHashMap<>();

        AuthenticationService(
                UserRepository users,
                TokenService tokens
        ) {
            this.users = users;
            this.tokens = tokens;
        }

        AccessToken login(String username, String password) {
            if (username == null || password == null) {
                throw new AuthenticationException("Invalid credentials.");
            }

            long now = System.currentTimeMillis();

            Deque<Long> attempts = failures.computeIfAbsent(
                    username.toLowerCase(),
                    key -> new ArrayDeque<>()
            );

            synchronized (attempts) {
                while (
                        !attempts.isEmpty() &&
                        now - attempts.peekFirst() > 300000
                ) {
                    attempts.removeFirst();
                }

                if (attempts.size() >= 5) {
                    throw new AuthenticationException(
                            "Too many authentication attempts."
                    );
                }

                User user = users.findByUsername(username);

                if (
                        user == null ||
                        user.status() != AccountStatus.ACTIVE ||
                        !PasswordService.verify(password, user)
                ) {
                    attempts.addLast(now);

                    throw new AuthenticationException(
                            "Invalid username or password."
                    );
                }

                failures.remove(username.toLowerCase());

                return tokens.issue(user);
            }
        }
    }

    // -----------------------------------------------------
    // Authorization Policy
    // -----------------------------------------------------

    interface AccessPolicy {
        boolean allows(User user, String permission);
    }

    static class RBACPolicy implements AccessPolicy {

        private static final Map<Role, Set<String>> ROLE_PERMISSIONS =
                Map.of(
                        Role.ADMIN,
                        Set.of(
                                "users:read",
                                "users:create",
                                "users:update",
                                "users:delete",
                                "reports:read",
                                "system:manage",
                                "resources:read"
                        ),

                        Role.EDITOR,
                        Set.of(
                                "users:read",
                                "users:update",
                                "reports:read",
                                "resources:read"
                        ),

                        Role.VIEWER,
                        Set.of(
                                "users:read",
                                "reports:read"
                        )
                );

        @Override
        public boolean allows(User user, String permission) {
            if (user.status() != AccountStatus.ACTIVE) {
                return false;
            }

            return user.roles()
                    .stream()
                    .anyMatch(role ->
                            ROLE_PERMISSIONS.getOrDefault(
                                    role,
                                    Set.of()
                            ).contains(permission)
                    );
        }

        void require(User user, String permission) {
            if (!allows(user, permission)) {
                throw new AuthorizationException(
                        "Permission denied: " + permission
                );
            }
        }
    }

    // -----------------------------------------------------
    // Resource Repository
    // -----------------------------------------------------

    static class ResourceRepository {

        private final Map<String, Resource> resources =
                new ConcurrentHashMap<>();

        void create(Resource resource) {
            if (
                    resource.id() == null ||
                    !resource.id().matches("[A-Za-z0-9_-]{3,64}") ||
                    resource.content() == null ||
                    resource.content().length() > 5000
            ) {
                throw new ValidationException("Invalid resource.");
            }

            if (resources.putIfAbsent(
                    resource.id(),
                    resource
            ) != null) {
                throw new ValidationException("Duplicate resource.");
            }
        }

        Resource find(String id) {
            return resources.get(id);
        }
    }

    // -----------------------------------------------------
    // Rate Limiter
    // -----------------------------------------------------

    static class RateLimiter {

        private final int maximumRequests;
        private final long windowMillis;

        private final Map<String, Deque<Long>> requests =
                new ConcurrentHashMap<>();

        RateLimiter(int maximumRequests, long windowMillis) {
            if (maximumRequests <= 0 || windowMillis <= 0) {
                throw new IllegalArgumentException(
                        "Invalid rate limiter configuration."
                );
            }

            this.maximumRequests = maximumRequests;
            this.windowMillis = windowMillis;
        }

        boolean allow(String clientId) {
            if (clientId == null || clientId.isBlank()) {
                return false;
            }

            Deque<Long> timestamps = requests.computeIfAbsent(
                    clientId,
                    key -> new ArrayDeque<>()
            );

            synchronized (timestamps) {
                long now = System.currentTimeMillis();

                while (
                        !timestamps.isEmpty() &&
                        now - timestamps.peekFirst() >= windowMillis
                ) {
                    timestamps.removeFirst();
                }

                if (timestamps.size() >= maximumRequests) {
                    return false;
                }

                timestamps.addLast(now);

                return true;
            }
        }
    }

    // -----------------------------------------------------
    // Audit Service
    // -----------------------------------------------------

    static class AuditService {

        private final List<AuditEvent> events =
                Collections.synchronizedList(new ArrayList<>());

        void record(AuditEvent event) {
            events.add(event);
        }

        List<AuditEvent> getEvents() {
            synchronized (events) {
                return List.copyOf(events);
            }
        }

        long count(Decision decision) {
            return events.stream()
                    .filter(event -> event.decision() == decision)
                    .count();
        }
    }

    // -----------------------------------------------------
    // API Security Configuration
    // -----------------------------------------------------

    record SecurityConfiguration(
            boolean requireAuthentication,
            boolean enforceOwnership,
            int maximumBodyBytes
    ) {
        SecurityConfiguration {
            if (maximumBodyBytes <= 0) {
                throw new IllegalArgumentException(
                        "Invalid body size limit."
                );
            }
        }
    }

    // -----------------------------------------------------
    // API Security Service
    // -----------------------------------------------------

    static class SecureAPIService {

        private final UserRepository users;
        private final TokenService tokens;
        private final AuthenticationService authentication;
        private final RBACPolicy authorization;
        private final ResourceRepository resources;
        private final RateLimiter rateLimiter;
        private final AuditService audit;
        private final SecurityConfiguration configuration;

        SecureAPIService(byte[] signingSecret) {
            users = new UserRepository();

            tokens = new TokenService(signingSecret);

            authentication = new AuthenticationService(
                    users,
                    tokens
            );

            authorization = new RBACPolicy();

            resources = new ResourceRepository();

            rateLimiter = new RateLimiter(
                    RATE_LIMIT,
                    RATE_WINDOW_MILLIS
            );

            audit = new AuditService();

            configuration = new SecurityConfiguration(
                    true,
                    true,
                    MAX_BODY_BYTES
            );
        }

        User register(
                String username,
                String password,
                Set<Role> roles
        ) {
            return users.create(username, password, roles);
        }

        AccessToken login(String username, String password) {
            return authentication.login(username, password);
        }

        void addResource(Resource resource) {
            resources.create(resource);
        }

        private String permissionFor(APIRequest request) {
            return switch (request.path()) {
                case "/api/users" -> switch (request.method()) {
                    case "GET" -> "users:read";
                    case "POST" -> "users:create";
                    case "PUT", "PATCH" -> "users:update";
                    case "DELETE" -> "users:delete";
                    default -> null;
                };

                case "/api/admin" -> "system:manage";

                case "/api/reports" -> "reports:read";

                case "/api/resources" -> "resources:read";

                default -> null;
            };
        }

        SecurityResult evaluate(APIRequest request) {
            String userId = "anonymous";

            SecurityResult result;

            try {
                if (!rateLimiter.allow(request.clientId())) {
                    throw new RateLimitException();
                }

                byte[] body = request.body() == null
                        ? new byte[0]
                        : request.body();

                if (body.length > configuration.maximumBodyBytes()) {
                    throw new ValidationException(
                            "Request body too large."
                    );
                }

                if (
                        request.path() == null ||
                        request.path().length() > 256 ||
                        request.method() == null
                ) {
                    throw new ValidationException("Invalid request.");
                }

                if (
                        !configuration.requireAuthentication() &&
                        request.path().equals("/health")
                ) {
                    return record(
                            Decision.ALLOW,
                            200,
                            "Public health endpoint.",
                            userId,
                            request.path()
                    );
                }

                if (
                        request.authorization() == null ||
                        !request.authorization().startsWith("Bearer ")
                ) {
                    throw new AuthenticationException(
                            "Bearer token required."
                    );
                }

                String token = request.authorization().substring(7);

                String matchedUser = users.findActiveUsers()
                        .stream()
                        .filter(user ->
                                tokens.validate(token, user.id())
                                        == TokenStatus.VALID
                        )
                        .map(User::id)
                        .findFirst()
                        .orElse(null);

                if (matchedUser == null) {
                    throw new AuthenticationException(
                            "Invalid, expired, or revoked token."
                    );
                }

                userId = matchedUser;

                User user = users.findById(userId);

                if (
                        user == null ||
                        user.status() != AccountStatus.ACTIVE
                ) {
                    throw new AuthenticationException(
                            "Account unavailable."
                    );
                }

                String requiredPermission = permissionFor(request);

                if (requiredPermission == null) {
                    return record(
                            Decision.DENY,
                            404,
                            "Unknown route or unsupported method.",
                            userId,
                            request.path()
                    );
                }

                authorization.require(
                        user,
                        requiredPermission
                );

                // Ownership checks add resource-level authorization.
                if (request.path().equals("/api/resources")) {
                    Resource resource = resources.find(
                            request.resourceId()
                    );

                    if (resource == null) {
                        throw new ValidationException(
                                "Resource not found."
                        );
                    }

                    if (
                            configuration.enforceOwnership() &&
                            !resource.ownerId().equals(user.id()) &&
                            !authorization.allows(
                                    user,
                                    "system:manage"
                            )
                    ) {
                        throw new AuthorizationException(
                                "Resource ownership denied."
                        );
                    }
                }

                result = record(
                        Decision.ALLOW,
                        200,
                        "All security policies satisfied.",
                        userId,
                        request.path()
                );

            } catch (SecurityException exception) {
                result = record(
                        Decision.DENY,
                        exception.getStatusCode(),
                        exception.getMessage(),
                        userId,
                        request.path()
                );

            } catch (Exception exception) {
                System.err.println(
                        "Unexpected security failure: " +
                        exception.getMessage()
                );

                result = record(
                        Decision.DENY,
                        500,
                        "Internal server error.",
                        userId,
                        request.path()
                );
            }

            return result;
        }

        private SecurityResult record(
                Decision decision,
                int status,
                String reason,
                String userId,
                String resource
        ) {

            audit.record(
                    new AuditEvent(
                            Instant.now(),
                            "API_REQUEST",
                            userId,
                            resource,
                            decision,
                            reason
                    )
            );

            return new SecurityResult(
                    decision,
                    status,
                    reason
            );
        }

        AuditService audit() {
            return audit;
        }

        TokenService tokenService() {
            return tokens;
        }

        UserRepository userRepository() {
            return users;
        }
    }

    // -----------------------------------------------------
    // Demonstration
    // -----------------------------------------------------

    public static void main(String[] args) {

        byte[] signingSecret = new byte[32];
        RANDOM.nextBytes(signingSecret);

        SecureAPIService api = new SecureAPIService(
                signingSecret
        );

        User admin = api.register(
                "administrator",
                "AdminSecure#2026",
                EnumSet.of(Role.ADMIN)
        );

        User editor = api.register(
                "content_editor",
                "EditorSecure#2026",
                EnumSet.of(Role.EDITOR)
        );

        User viewer = api.register(
                "analyst",
                "AnalystSecure#2026",
                EnumSet.of(Role.VIEWER)
        );

        AccessToken adminToken = api.login(
                "administrator",
                "AdminSecure#2026"
        );

        AccessToken editorToken = api.login(
                "content_editor",
                "EditorSecure#2026"
        );

        AccessToken viewerToken = api.login(
                "analyst",
                "AnalystSecure#2026"
        );

        api.addResource(
                new Resource(
                        "DOC001",
                        editor.id(),
                        "Confidential project document"
                )
        );

        List<APIRequest> requests = List.of(

                new APIRequest(
                        "GET",
                        "/api/admin",
                        "Bearer " + adminToken.token(),
                        "client-admin",
                        null,
                        new byte[0]
                ),

                new APIRequest(
                        "GET",
                        "/api/admin",
                        "Bearer " + viewerToken.token(),
                        "client-viewer",
                        null,
                        new byte[0]
                ),

                new APIRequest(
                        "GET",
                        "/api/users",
                        "Bearer " + editorToken.token(),
                        "client-editor",
                        null,
                        new byte[0]
                ),

                new APIRequest(
                        "GET",
                        "/api/resources",
                        "Bearer " + editorToken.token(),
                        "client-editor",
                        "DOC001",
                        new byte[0]
                ),

                new APIRequest(
                        "GET",
                        "/api/resources",
                        "Bearer " + viewerToken.token(),
                        "client-viewer",
                        "DOC001",
                        new byte[0]
                ),

                new APIRequest(
                        "GET",
                        "/api/admin",
                        "Bearer invalid-token",
                        "client-invalid",
                        null,
                        new byte[0]
                ),

                new APIRequest(
                        "GET",
                        "/api/admin",
                        null,
                        "client-unauthenticated",
                        null,
                        new byte[0]
                )
        );

        System.out.println("SECURE API EVALUATION\n");

        int allowed = 0;
        int denied = 0;

        for (APIRequest request : requests) {

            SecurityResult result = api.evaluate(request);

            System.out.printf(
                    "%-20s HTTP %-3d %-6s %s%n",
                    request.path(),
                    result.statusCode(),
                    result.decision(),
                    result.reason()
            );

            if (result.decision() == Decision.ALLOW) {
                allowed++;
            } else {
                denied++;
            }
        }

        // Revocation immediately affects subsequent authentication.
        api.tokenService().revoke(viewerToken.token());

        SecurityResult revoked = api.evaluate(
                new APIRequest(
                        "GET",
                        "/api/users",
                        "Bearer " + viewerToken.token(),
                        "client-revoked",
                        null,
                        new byte[0]
                )
        );

        if (revoked.statusCode() != 401) {
            throw new IllegalStateException(
                    "Revoked token was accepted."
            );
        }

        // Account suspension independently invalidates access.
        api.userRepository().updateStatus(
                admin.id(),
                AccountStatus.SUSPENDED
        );

        SecurityResult suspended = api.evaluate(
                new APIRequest(
                        "GET",
                        "/api/admin",
                        "Bearer " + adminToken.token(),
                        "client-suspended",
                        null,
                        new byte[0]
                )
        );

        if (suspended.statusCode() != 401) {
            throw new IllegalStateException(
                    "Suspended account was accepted."
            );
        }

        System.out.println("\nSECURITY AUDIT");

        for (AuditEvent event : api.audit().getEvents()) {
            System.out.printf(
                    "%s | %s | %s | %s%n",
                    event.timestamp(),
                    event.userId(),
                    event.decision(),
                    event.reason()
            );
        }

        System.out.println("\nAllowed: " + allowed);
        System.out.println("Denied: " + denied);

        System.out.println(
                "Audit records: " +
                api.audit().getEvents().size()
        );

        if (allowed != 3 || denied != 4) {
            throw new IllegalStateException(
                    "Unexpected evaluation results."
            );
        }

        System.out.println(
                "\nAll enterprise security tests passed."
        );
    }
}
