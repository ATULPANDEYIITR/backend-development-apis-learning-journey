import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

public class JwtAuthenticationDemo {

    enum TokenType {
        ACCESS
    }

    enum ReviewDecision {
        PENDING,
        APPROVED,
        CHANGES_REQUESTED,
        REJECTED
    }

    enum CheckState {
        PENDING,
        PASSED,
        FAILED
    }

    enum PullRequestState {
        DRAFT,
        OPEN,
        CLOSED,
        MERGED
    }

    record User(
        String id,
        String username,
        Set<String> roles,
        Set<String> scopes,
        boolean active
    ) {
        User {
            Objects.requireNonNull(id);
            Objects.requireNonNull(username);
            roles = Set.copyOf(roles);
            scopes = Set.copyOf(scopes);
        }
    }

    record Review(
        String reviewer,
        ReviewDecision decision,
        boolean stale
    ) {}

    record StatusCheck(
        String name,
        CheckState state
    ) {}

    record BranchProtectionPolicy(
        String branch,
        int requiredApprovals,
        boolean requireStatusChecks,
        boolean restrictDirectPush,
        boolean restrictForcePush,
        boolean requireConversationResolution,
        boolean requireLinearHistory,
        Set<String> eligibleReviewers,
        Set<String> requiredChecks
    ) {
        BranchProtectionPolicy {
            if (branch == null || branch.isBlank()) {
                throw new IllegalArgumentException(
                    "Protected branch is required"
                );
            }

            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "Required approvals cannot be negative"
                );
            }

            eligibleReviewers = Set.copyOf(eligibleReviewers);
            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    record PullRequest(
        int number,
        String author,
        String sourceBranch,
        String targetBranch,
        PullRequestState state,
        boolean draft,
        List<String> commits,
        List<Review> reviews,
        List<StatusCheck> checks,
        int unresolvedConversations,
        boolean hasConflicts
    ) {}

    record EligibilityResult(
        boolean eligible,
        List<String> reasons
    ) {}

    static final class TokenValidationException
        extends RuntimeException {

        TokenValidationException(String message) {
            super(message);
        }
    }

    static final class JwtService {
        private final byte[] secret;
        private final String issuer;
        private final String audience;
        private final long lifetimeSeconds;
        private final Base64.Encoder encoder =
            Base64.getUrlEncoder().withoutPadding();
        private final Base64.Decoder decoder =
            Base64.getUrlDecoder();

        JwtService(
            byte[] secret,
            String issuer,
            String audience,
            long lifetimeSeconds
        ) {
            if (secret.length < 32) {
                throw new IllegalArgumentException(
                    "JWT secret must contain at least 32 bytes"
                );
            }

            if (lifetimeSeconds <= 0) {
                throw new IllegalArgumentException(
                    "JWT lifetime must be positive"
                );
            }

            this.secret = secret.clone();
            this.issuer = issuer;
            this.audience = audience;
            this.lifetimeSeconds = lifetimeSeconds;
        }

        String issueAccessToken(User user) {
            long now = System.currentTimeMillis() / 1000;

            String header =
                "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";

            String scope = user.scopes()
                .stream()
                .sorted()
                .collect(Collectors.joining(" "));

            String roles = user.roles()
                .stream()
                .sorted()
                .map(role -> "\"" + escape(role) + "\"")
                .collect(Collectors.joining(","));

            String payload =
                "{"
                + "\"iss\":\"" + escape(issuer) + "\","
                + "\"sub\":\"" + escape(user.id()) + "\","
                + "\"aud\":\"" + escape(audience) + "\","
                + "\"iat\":" + now + ","
                + "\"nbf\":" + now + ","
                + "\"exp\":" + (now + lifetimeSeconds) + ","
                + "\"jti\":\"" + randomId() + "\","
                + "\"typ\":\"" + TokenType.ACCESS.name().toLowerCase() + "\","
                + "\"roles\":[" + roles + "],"
                + "\"scope\":\"" + escape(scope) + "\""
                + "}";

            String encodedHeader =
                encoder.encodeToString(
                    header.getBytes(StandardCharsets.UTF_8)
                );

            String encodedPayload =
                encoder.encodeToString(
                    payload.getBytes(StandardCharsets.UTF_8)
                );

            String input = encodedHeader + "." + encodedPayload;
            String signature = sign(input);

            return input + "." + signature;
        }

        void validateAccessToken(
            String token,
            String requiredScope
        ) {
            String[] parts = token.split("\\.", -1);

            if (parts.length != 3) {
                throw new TokenValidationException(
                    "JWT must contain three segments"
                );
            }

            String payloadJson = new String(
                decoder.decode(parts[1]),
                StandardCharsets.UTF_8
            );

            if (!parts[0].contains("\"alg\":\"HS256\"") ||
                !parts[0].contains("\"typ\":\"JWT\"")) {
                throw new TokenValidationException(
                    "Unsupported JWT header"
                );
            }

            String expectedSignature = sign(
                parts[0] + "." + parts[1]
            );

            if (!MessageDigest.isEqual(
                expectedSignature.getBytes(StandardCharsets.US_ASCII),
                parts[2].getBytes(StandardCharsets.US_ASCII)
            )) {
                throw new TokenValidationException(
                    "Invalid signature"
                );
            }

            requireClaim(payloadJson, "\"iss\":\"" + issuer + "\"");
            requireClaim(payloadJson, "\"aud\":\"" + audience + "\"");
            requireClaim(payloadJson, "\"typ\":\"access\"");

            long now = System.currentTimeMillis() / 1000;

            long nbf = numericClaim(payloadJson, "\"nbf\":");
            long exp = numericClaim(payloadJson, "\"exp\":");
            long iat = numericClaim(payloadJson, "\"iat\":");

            if (iat > now + 30) {
                throw new TokenValidationException(
                    "Token issued in the future"
                );
            }

            if (nbf > now) {
                throw new TokenValidationException(
                    "Token is not active"
                );
            }

            if (exp <= now) {
                throw new TokenValidationException(
                    "Token has expired"
                );
            }

            if (exp <= iat) {
                throw new TokenValidationException(
                    "Invalid token lifetime"
                );
            }

            if (requiredScope != null &&
                !scopeContains(payloadJson, requiredScope)) {
                throw new TokenValidationException(
                    "Required scope is missing"
                );
            }
        }

        private boolean scopeContains(
            String payload,
            String requiredScope
        ) {
            String marker = "\"scope\":\"";
            int start = payload.indexOf(marker);

            if (start < 0) {
                return false;
            }

            start += marker.length();
            int end = payload.indexOf('"', start);

            if (end < 0) {
                return false;
            }

            Set<String> scopes = Set.of(
                payload.substring(start, end).split(" ")
            );

            return scopes.contains(requiredScope);
        }

        private long numericClaim(
            String payload,
            String marker
        ) {
            int start = payload.indexOf(marker);

            if (start < 0) {
                throw new TokenValidationException(
                    "Missing numeric claim"
                );
            }

            start += marker.length();
            int end = start;

            while (end < payload.length() &&
                   Character.isDigit(payload.charAt(end))) {
                end++;
            }

            try {
                return Long.parseLong(
                    payload.substring(start, end)
                );
            } catch (NumberFormatException ex) {
                throw new TokenValidationException(
                    "Invalid numeric claim"
                );
            }
        }

        private void requireClaim(
            String payload,
            String claim
        ) {
            if (!payload.contains(claim)) {
                throw new TokenValidationException(
                    "Required claim is missing or invalid"
                );
            }
        }

        private String sign(String input) {
            try {
                var mac = javax.crypto.Mac.getInstance("HmacSHA256");
                mac.init(
                    new javax.crypto.spec.SecretKeySpec(
                        secret,
                        "HmacSHA256"
                    )
                );

                return encoder.encodeToString(
                    mac.doFinal(
                        input.getBytes(StandardCharsets.US_ASCII)
                    )
                );
            } catch (Exception ex) {
                throw new IllegalStateException(
                    "Unable to sign JWT",
                    ex
                );
            }
        }

        private String randomId() {
            byte[] bytes = new byte[18];
            new SecureRandom().nextBytes(bytes);
            return encoder.encodeToString(bytes);
        }

        private String escape(String value) {
            return value.replace("\\", "\\\\")
                        .replace("\"", "\\\"");
        }
    }

    static final class MergeEligibilityService {
        private final Map<String, BranchProtectionPolicy> policies =
            new HashMap<>();

        void registerPolicy(BranchProtectionPolicy policy) {
            policies.put(policy.branch(), policy);
        }

        EligibilityResult evaluate(PullRequest pr) {
            var reasons = new java.util.ArrayList<String>();

            if (pr.state() != PullRequestState.OPEN) {
                reasons.add("Pull Request is not open");
            }

            if (pr.draft()) {
                reasons.add("Draft Pull Request cannot merge");
            }

            if (pr.sourceBranch().equals(pr.targetBranch())) {
                reasons.add("Source and target branches must differ");
            }

            if (pr.commits().isEmpty()) {
                reasons.add("Pull Request contains no commits");
            }

            if (pr.hasConflicts()) {
                reasons.add("Merge conflicts remain");
            }

            BranchProtectionPolicy policy =
                policies.get(pr.targetBranch());

            if (policy == null) {
                return new EligibilityResult(
                    reasons.isEmpty(),
                    List.copyOf(reasons)
                );
            }

            if (policy.requireConversationResolution() &&
                pr.unresolvedConversations() > 0) {
                reasons.add("Unresolved conversations remain");
            }

            Set<String> approvedReviewers = pr.reviews()
                .stream()
                .filter(review ->
                    review.decision() == ReviewDecision.APPROVED &&
                    !review.stale() &&
                    policy.eligibleReviewers()
                        .contains(review.reviewer())
                )
                .map(Review::reviewer)
                .collect(Collectors.toSet());

            boolean changesRequested = pr.reviews()
                .stream()
                .anyMatch(review ->
                    review.decision() ==
                    ReviewDecision.CHANGES_REQUESTED
                );

            if (changesRequested) {
                reasons.add("Changes have been requested");
            }

            if (approvedReviewers.size() <
                policy.requiredApprovals()) {
                reasons.add(
                    "Required approvals are not satisfied"
                );
            }

            if (policy.requireStatusChecks()) {
                Map<String, CheckState> checks =
                    pr.checks()
                      .stream()
                      .collect(Collectors.toMap(
                          StatusCheck::name,
                          StatusCheck::state,
                          (first, second) -> second
                      ));

                for (String required :
                    policy.requiredChecks()) {
                    if (!checks.containsKey(required)) {
                        reasons.add(
                            "Missing status check: " + required
                        );
                    } else if (
                        checks.get(required) != CheckState.PASSED
                    ) {
                        reasons.add(
                            "Failed status check: " + required
                        );
                    }
                }
            }

            return new EligibilityResult(
                reasons.isEmpty(),
                List.copyOf(reasons)
            );
        }
    }

    public static void main(String[] args) {
        SecureRandom random = new SecureRandom();
        byte[] secret = new byte[32];
        random.nextBytes(secret);

        User alice = new User(
            "user-100",
            "alice",
            Set.of("developer"),
            Set.of("orders:read", "profile:read"),
            true
        );

        JwtService jwt = new JwtService(
            secret,
            "https://auth.example.internal",
            "orders-api",
            900
        );

        String accessToken = jwt.issueAccessToken(alice);

        jwt.validateAccessToken(
            accessToken,
            "orders:read"
        );

        System.out.println("JWT validation succeeded.");

        try {
            jwt.validateAccessToken(
                accessToken,
                "orders:write"
            );
        } catch (TokenValidationException ex) {
            System.out.println(
                "Authorization failure: " + ex.getMessage()
            );
        }

        BranchProtectionPolicy policy =
            new BranchProtectionPolicy(
                "main",
                2,
                true,
                true,
                true,
                true,
                true,
                Set.of("reviewer-1", "reviewer-2"),
                Set.of("unit-tests", "security-scan")
            );

        PullRequest pr = new PullRequest(
            42,
            "alice",
            "feature/jwt-authentication",
            "main",
            PullRequestState.OPEN,
            false,
            List.of("abc123", "def456"),
            List.of(
                new Review(
                    "reviewer-1",
                    ReviewDecision.APPROVED,
                    false
                ),
                new Review(
                    "reviewer-2",
                    ReviewDecision.APPROVED,
                    false
                )
            ),
            List.of(
                new StatusCheck(
                    "unit-tests",
                    CheckState.PASSED
                ),
                new StatusCheck(
                    "security-scan",
                    CheckState.PASSED
                )
            ),
            0,
            false
        );

        MergeEligibilityService governance =
            new MergeEligibilityService();

        governance.registerPolicy(policy);

        EligibilityResult result =
            governance.evaluate(pr);

        System.out.println(
            "Merge eligible: " + result.eligible()
        );

        result.reasons().forEach(
            reason -> System.out.println(" - " + reason)
        );
    }
}
