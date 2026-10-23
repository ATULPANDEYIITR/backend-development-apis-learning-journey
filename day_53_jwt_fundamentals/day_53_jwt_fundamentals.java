import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Arrays;
import java.util.Base64;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Enterprise JWT authentication and authorization model.
 *
 * The program models:
 * - JWT header and payload claims
 * - token issuance
 * - signature verification
 * - expiration and clock skew
 * - issuer and audience validation
 * - scopes and roles
 * - token revocation
 * - explicit authentication failure states
 *
 * The signing implementation uses Java's standard HMAC-SHA256 API.
 */
public class JwtFundamentals {

    enum AuthenticationFailure {
        MALFORMED_TOKEN,
        INVALID_ALGORITHM,
        INVALID_SIGNATURE,
        INVALID_ISSUER,
        INVALID_AUDIENCE,
        INVALID_SUBJECT,
        TOKEN_NOT_YET_VALID,
        TOKEN_EXPIRED,
        TOKEN_REVOKED,
        MISSING_ROLE,
        MISSING_SCOPE
    }

    static final class AuthenticationException extends Exception {
        private final AuthenticationFailure failure;

        AuthenticationException(
                AuthenticationFailure failure,
                String message
        ) {
            super(message);
            this.failure = failure;
        }

        AuthenticationFailure failure() {
            return failure;
        }
    }

    record JwtPolicy(
            String issuer,
            String audience,
            String algorithm,
            long clockSkewSeconds,
            Set<String> requiredRoles,
            Set<String> requiredScopes
    ) {
        JwtPolicy {
            if (issuer == null || issuer.isBlank()) {
                throw new IllegalArgumentException("Issuer is required");
            }

            if (audience == null || audience.isBlank()) {
                throw new IllegalArgumentException("Audience is required");
            }

            if (!"HS256".equals(algorithm)) {
                throw new IllegalArgumentException(
                        "This implementation supports HS256 only"
                );
            }

            if (clockSkewSeconds < 0) {
                throw new IllegalArgumentException(
                        "Clock skew cannot be negative"
                );
            }

            requiredRoles = Set.copyOf(requiredRoles);
            requiredScopes = Set.copyOf(requiredScopes);
        }
    }

    record UserIdentity(
            String id,
            Set<String> roles,
            Set<String> scopes
    ) {
        UserIdentity {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException("User ID is required");
            }

            roles = Set.copyOf(roles);
            scopes = Set.copyOf(scopes);
        }
    }

    record JwtClaims(
            String issuer,
            String subject,
            String audience,
            long issuedAt,
            long expiresAt,
            String tokenId,
            Set<String> roles,
            Set<String> scopes
    ) {}

    record AuthenticatedPrincipal(
            String subject,
            Set<String> roles,
            Set<String> scopes,
            String tokenId
    ) {}

    static final class JwtToken {
        private final String compact;
        private final JwtClaims claims;

        JwtToken(String compact, JwtClaims claims) {
            this.compact = compact;
            this.claims = claims;
        }

        String compact() {
            return compact;
        }

        JwtClaims claims() {
            return claims;
        }
    }

    static final class JwtService {
        private final byte[] secret;
        private final JwtPolicy policy;
        private final SecureRandom random = new SecureRandom();

        JwtService(byte[] secret, JwtPolicy policy) {
            if (secret.length < 32) {
                throw new IllegalArgumentException(
                        "HMAC secret must contain at least 32 bytes"
                );
            }

            this.secret = secret.clone();
            this.policy = policy;
        }

        JwtToken issue(
                UserIdentity user,
                long lifetimeSeconds
        ) {
            if (lifetimeSeconds <= 0) {
                throw new IllegalArgumentException(
                        "Token lifetime must be positive"
                );
            }

            long now = Instant.now().getEpochSecond();

            String header =
                    "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";

            String tokenId = UUID.randomUUID().toString();

            String payload = String.format(
                    "{\"iss\":\"%s\",\"sub\":\"%s\",\"aud\":\"%s\","
                            + "\"iat\":%d,\"exp\":%d,\"jti\":\"%s\","
                            + "\"roles\":\"%s\",\"scope\":\"%s\"}",
                    escape(userValue(policy.issuer())),
                    escape(userValue(user.id())),
                    escape(userValue(policy.audience())),
                    now,
                    now + lifetimeSeconds,
                    tokenId,
                    escape(String.join(",", user.roles())),
                    escape(String.join(" ", user.scopes()))
            );

            String encodedHeader = encode(header);
            String encodedPayload = encode(payload);
            String input = encodedHeader + "." + encodedPayload;
            String signature = encode(sign(input));

            return new JwtToken(
                    input + "." + signature,
                    new JwtClaims(
                            policy.issuer(),
                            user.id(),
                            policy.audience(),
                            now,
                            now + lifetimeSeconds,
                            tokenId,
                            user.roles(),
                            user.scopes()
                    )
            );
        }

        JwtClaims verify(String token)
                throws AuthenticationException {
            String[] parts = token.split("\\.", -1);

            if (parts.length != 3) {
                throw new AuthenticationException(
                        AuthenticationFailure.MALFORMED_TOKEN,
                        "JWT must contain exactly three segments"
                );
            }

            String header = decode(parts[0]);
            String payload = decode(parts[1]);

            if (!header.contains("\"alg\":\"HS256\"")
                    || !header.contains("\"typ\":\"JWT\"")) {
                throw new AuthenticationException(
                        AuthenticationFailure.INVALID_ALGORITHM,
                        "Unexpected JWT header"
                );
            }

            byte[] expected = sign(parts[0] + "." + parts[1]);
            byte[] supplied = decodeBytes(parts[2]);

            if (!MessageDigest.isEqual(expected, supplied)) {
                throw new AuthenticationException(
                        AuthenticationFailure.INVALID_SIGNATURE,
                        "Signature verification failed"
                );
            }

            JwtClaims claims = parseClaims(payload);
            validateClaims(claims);

            return claims;
        }

        private JwtClaims parseClaims(String payload)
                throws AuthenticationException {
            try {
                String issuer = extract(payload, "iss");
                String subject = extract(payload, "sub");
                String audience = extract(payload, "aud");
                long issuedAt = Long.parseLong(
                        extract(payload, "iat")
                );
                long expiresAt = Long.parseLong(
                        extract(payload, "exp")
                );
                String tokenId = extract(payload, "jti");

                Set<String> roles = splitSet(
                        extract(payload, "roles"),
                        ","
                );

                Set<String> scopes = splitSet(
                        extract(payload, "scope"),
                        " "
                );

                return new JwtClaims(
                        issuer,
                        subject,
                        audience,
                        issuedAt,
                        expiresAt,
                        tokenId,
                        roles,
                        scopes
                );
            } catch (RuntimeException exception) {
                throw new AuthenticationException(
                        AuthenticationFailure.MALFORMED_TOKEN,
                        "Invalid JWT payload"
                );
            }
        }

        private void validateClaims(JwtClaims claims)
                throws AuthenticationException {
            long now = Instant.now().getEpochSecond();
            long skew = policy.clockSkewSeconds();

            if (!policy.issuer().equals(claims.issuer())) {
                throw new AuthenticationException(
                        AuthenticationFailure.INVALID_ISSUER,
                        "Issuer does not match"
                );
            }

            if (claims.subject() == null
                    || claims.subject().isBlank()) {
                throw new AuthenticationException(
                        AuthenticationFailure.INVALID_SUBJECT,
                        "Subject is empty"
                );
            }

            if (!policy.audience().equals(claims.audience())) {
                throw new AuthenticationException(
                        AuthenticationFailure.INVALID_AUDIENCE,
                        "Audience does not match"
                );
            }

            if (claims.issuedAt() > now + skew) {
                throw new AuthenticationException(
                        AuthenticationFailure.TOKEN_NOT_YET_VALID,
                        "Token was issued in the future"
                );
            }

            if (claims.expiresAt() <= now - skew) {
                throw new AuthenticationException(
                        AuthenticationFailure.TOKEN_EXPIRED,
                        "Token has expired"
                );
            }
        }

        private byte[] sign(String input) {
            try {
                var mac = javax.crypto.Mac.getInstance("HmacSHA256");
                mac.init(
                        new javax.crypto.spec.SecretKeySpec(
                                secret,
                                "HmacSHA256"
                        )
                );
                return mac.doFinal(
                        input.getBytes(StandardCharsets.UTF_8)
                );
            } catch (Exception exception) {
                throw new IllegalStateException(
                        "Unable to calculate JWT signature",
                        exception
                );
            }
        }

        private static String encode(String value) {
            return Base64.getUrlEncoder()
                    .withoutPadding()
                    .encodeToString(
                            value.getBytes(StandardCharsets.UTF_8)
                    );
        }

        private static String encode(byte[] value) {
            return Base64.getUrlEncoder()
                    .withoutPadding()
                    .encodeToString(value);
        }

        private static String decode(String value) {
            return new String(
                    decodeBytes(value),
                    StandardCharsets.UTF_8
            );
        }

        private static byte[] decodeBytes(String value) {
            return Base64.getUrlDecoder().decode(value);
        }

        private static String extract(
                String json,
                String name
        ) {
            String prefix = "\"" + name + "\":";
            int start = json.indexOf(prefix);

            if (start < 0) {
                throw new IllegalArgumentException(
                        "Missing claim " + name
                );
            }

            start += prefix.length();

            if (json.charAt(start) == '"') {
                start++;
                int end = json.indexOf('"', start);
                return json.substring(start, end);
            }

            int end = json.indexOf(',', start);
            if (end < 0) {
                end = json.indexOf('}', start);
            }

            return json.substring(start, end);
        }

        private static Set<String> splitSet(
                String value,
                String delimiter
        ) {
            if (value.isBlank()) {
                return Set.of();
            }

            return Set.copyOf(
                    Arrays.stream(value.split(
                                    java.util.regex.Pattern.quote(delimiter)
                            ))
                            .filter(item -> !item.isBlank())
                            .toList()
            );
        }

        private static String escape(String value) {
            return value
                    .replace("\\", "\\\\")
                    .replace("\"", "\\\"");
        }

        private static String userValue(String value) {
            return value;
        }
    }

    static final class AuthenticationService {
        private final JwtService jwtService;
        private final JwtPolicy policy;
        private final Set<String> revokedTokenIds =
                new HashSet<>();

        AuthenticationService(
                JwtService jwtService,
                JwtPolicy policy
        ) {
            this.jwtService = jwtService;
            this.policy = policy;
        }

        void revoke(String tokenId) {
            revokedTokenIds.add(tokenId);
        }

        AuthenticatedPrincipal authenticate(
                String token
        ) throws AuthenticationException {
            JwtClaims claims = jwtService.verify(token);

            if (revokedTokenIds.contains(claims.tokenId())) {
                throw new AuthenticationException(
                        AuthenticationFailure.TOKEN_REVOKED,
                        "Token has been revoked"
                );
            }

            for (String role : policy.requiredRoles()) {
                if (!claims.roles().contains(role)) {
                    throw new AuthenticationException(
                            AuthenticationFailure.MISSING_ROLE,
                            "Required role is missing: " + role
                    );
                }
            }

            for (String scope : policy.requiredScopes()) {
                if (!claims.scopes().contains(scope)) {
                    throw new AuthenticationException(
                            AuthenticationFailure.MISSING_SCOPE,
                            "Required scope is missing: " + scope
                    );
                }
            }

            return new AuthenticatedPrincipal(
                    claims.subject(),
                    claims.roles(),
                    claims.scopes(),
                    claims.tokenId()
            );
        }
    }

    public static void main(String[] args) {
        JwtPolicy policy = new JwtPolicy(
                "repository-api",
                "repository-client",
                "HS256",
                30,
                Set.of("reviewer"),
                Set.of("repository:write")
        );

        byte[] secret = new byte[32];
        new SecureRandom().nextBytes(secret);

        JwtService jwtService = new JwtService(secret, policy);
        AuthenticationService authentication =
                new AuthenticationService(jwtService, policy);

        UserIdentity user = new UserIdentity(
                "user-1042",
                Set.of("developer", "reviewer"),
                Set.of("repository:read", "repository:write")
        );

        JwtToken token = jwtService.issue(user, 300);

        System.out.println("Issued JWT:");
        System.out.println(token.compact());

        try {
            AuthenticatedPrincipal principal =
                    authentication.authenticate(token.compact());

            System.out.println("\nAuthentication succeeded");
            System.out.println("Subject: " + principal.subject());
            System.out.println("Roles: " + principal.roles());
            System.out.println("Scopes: " + principal.scopes());

            authentication.revoke(principal.tokenId());

            try {
                authentication.authenticate(token.compact());
            } catch (AuthenticationException exception) {
                System.out.println(
                        "\nRevocation rejected the token: "
                                + exception.failure()
                                + " - "
                                + exception.getMessage()
                );
            }

        } catch (AuthenticationException exception) {
            System.err.println(
                    "Authentication failed: "
                            + exception.failure()
                            + " - "
                            + exception.getMessage()
            );
        }

        String[] malformedTokens = {
                "",
                "not-a-jwt",
                "one.two",
                "one.two.three.four"
        };

        for (String malformed : malformedTokens) {
            try {
                jwtService.verify(malformed);
            } catch (AuthenticationException exception) {
                System.out.println(
                        "Rejected malformed token: "
                                + exception.failure()
                );
            }
        }
    }
}
