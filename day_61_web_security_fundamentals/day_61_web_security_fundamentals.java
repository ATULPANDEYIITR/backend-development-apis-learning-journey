import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;

public class WebSecurityGovernance {

    enum SecurityLevel {
        LOW(1),
        MEDIUM(2),
        HIGH(3),
        CRITICAL(4);

        private final int score;

        SecurityLevel(int score) {
            this.score = score;
        }

        public int score() {
            return score;
        }
    }

    enum ThreatCategory {
        SPOOFING,
        TAMPERING,
        REPUDIATION,
        INFORMATION_DISCLOSURE,
        DENIAL_OF_SERVICE,
        ELEVATION_OF_PRIVILEGE
    }

    enum ReviewDecision {
        APPROVED,
        CHANGES_REQUESTED,
        COMMENTED
    }

    enum PullRequestState {
        DRAFT,
        OPEN,
        MERGED,
        CLOSED
    }

    enum UserRole {
        DEVELOPER,
        SECURITY_REVIEWER,
        ADMINISTRATOR
    }

    record Asset(
        String name,
        SecurityLevel confidentiality,
        SecurityLevel integrity,
        SecurityLevel availability,
        String owner
    ) {
        Asset {
            requireText(name, "asset name");
            requireText(owner, "asset owner");
        }
    }

    record Threat(
        String name,
        ThreatCategory category,
        String asset,
        SecurityLevel likelihood,
        SecurityLevel impact,
        String mitigation
    ) {
        int riskScore() {
            return likelihood.score() * impact.score();
        }
    }

    record StatusCheck(
        String name,
        boolean required,
        boolean passed
    ) {}

    record Review(
        String reviewer,
        UserRole role,
        ReviewDecision decision,
        boolean stale,
        boolean dismissed
    ) {}

    record SecurityFinding(
        String identifier,
        String severity,
        boolean resolved
    ) {}

    record BranchProtectionPolicy(
        String branchName,
        int requiredApprovals,
        boolean requireSecurityReview,
        boolean requireStatusChecks,
        boolean requireUpToDateBranch,
        boolean allowForcePush,
        boolean allowDirectPush
    ) {
        BranchProtectionPolicy {
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "Required approvals cannot be negative."
                );
            }
        }
    }

    static final class SecurityValidationException
        extends RuntimeException {

        SecurityValidationException(String message) {
            super(message);
        }
    }

    static final class AuthenticationException
        extends RuntimeException {

        AuthenticationException(String message) {
            super(message);
        }
    }

    static final class AuthorizationException
        extends RuntimeException {

        AuthorizationException(String message) {
            super(message);
        }
    }

    static final class SecurityPolicyException
        extends RuntimeException {

        SecurityPolicyException(String message) {
            super(message);
        }
    }

    static final class User {
        private final String username;
        private final Set<UserRole> roles;

        User(String username, Set<UserRole> roles) {
            requireText(username, "username");
            this.username = username;
            this.roles = Set.copyOf(roles);
        }

        String username() {
            return username;
        }

        boolean hasRole(UserRole role) {
            return roles.contains(role);
        }
    }

    static final class Repository {
        private final String name;
        private final Map<String, Asset> assets = new HashMap<>();
        private final Map<String, BranchProtectionPolicy> policies =
            new HashMap<>();

        Repository(String name) {
            requireText(name, "repository name");
            this.name = name;
        }

        void addAsset(Asset asset) {
            if (assets.putIfAbsent(asset.name(), asset) != null) {
                throw new SecurityPolicyException(
                    "Duplicate asset: " + asset.name()
                );
            }
        }

        void protectBranch(BranchProtectionPolicy policy) {
            policies.put(policy.branchName(), policy);
        }

        BranchProtectionPolicy policyFor(String branch) {
            BranchProtectionPolicy policy = policies.get(branch);

            if (policy == null) {
                throw new SecurityPolicyException(
                    "No protection policy exists for branch " + branch
                );
            }

            return policy;
        }

        String name() {
            return name;
        }

        Map<String, Asset> assets() {
            return Map.copyOf(assets);
        }
    }

    static final class PullRequest {
        private final int id;
        private final User author;
        private final String sourceBranch;
        private final String targetBranch;
        private final Set<String> changedFiles;
        private final List<Review> reviews = new ArrayList<>();
        private final List<StatusCheck> checks = new ArrayList<>();
        private final List<SecurityFinding> findings = new ArrayList<>();

        private PullRequestState state = PullRequestState.OPEN;
        private boolean sourceBranchUpToDate = true;
        private boolean mergeConflict = false;

        PullRequest(
            int id,
            User author,
            String sourceBranch,
            String targetBranch,
            Set<String> changedFiles
        ) {
            if (id <= 0) {
                throw new SecurityValidationException(
                    "Pull Request ID must be positive."
                );
            }

            this.id = id;
            this.author = Objects.requireNonNull(author);
            validateBranch(sourceBranch);
            validateBranch(targetBranch);

            if (sourceBranch.equals(targetBranch)) {
                throw new SecurityValidationException(
                    "Source and target branches must differ."
                );
            }

            if (changedFiles.isEmpty()) {
                throw new SecurityValidationException(
                    "A Pull Request must contain changed files."
                );
            }

            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.changedFiles = Set.copyOf(changedFiles);
        }

        void addReview(Review review) {
            if (state != PullRequestState.OPEN) {
                throw new SecurityPolicyException(
                    "Reviews cannot be added to a closed Pull Request."
                );
            }
            reviews.add(review);
        }

        void addStatusCheck(StatusCheck check) {
            checks.add(check);
        }

        void addFinding(SecurityFinding finding) {
            findings.add(finding);
        }

        void setSourceBranchUpToDate(boolean value) {
            sourceBranchUpToDate = value;
        }

        void setMergeConflict(boolean value) {
            mergeConflict = value;
        }

        void setState(PullRequestState state) {
            this.state = Objects.requireNonNull(state);
        }

        int id() {
            return id;
        }

        String targetBranch() {
            return targetBranch;
        }

        PullRequestState state() {
            return state;
        }

        List<Review> reviews() {
            return List.copyOf(reviews);
        }

        List<StatusCheck> checks() {
            return List.copyOf(checks);
        }

        List<SecurityFinding> findings() {
            return List.copyOf(findings);
        }

        boolean sourceBranchUpToDate() {
            return sourceBranchUpToDate;
        }

        boolean mergeConflict() {
            return mergeConflict;
        }
    }

    static final class MergeEligibilityService {

        List<String> evaluate(
            PullRequest pullRequest,
            BranchProtectionPolicy policy
        ) {
            List<String> failures = new ArrayList<>();

            if (pullRequest.state() != PullRequestState.OPEN) {
                failures.add("Pull Request is not open.");
            }

            if (policy.requireUpToDateBranch()
                && !pullRequest.sourceBranchUpToDate()) {
                failures.add("Source branch is not synchronized.");
            }

            if (pullRequest.mergeConflict()) {
                failures.add("Merge conflict exists.");
            }

            boolean unresolvedSecurityFinding =
                pullRequest.findings()
                    .stream()
                    .anyMatch(finding -> !finding.resolved());

            if (unresolvedSecurityFinding) {
                failures.add("Unresolved security finding exists.");
            }

            if (policy.requireStatusChecks()) {
                boolean checksValid = pullRequest.checks()
                    .stream()
                    .filter(StatusCheck::required)
                    .allMatch(StatusCheck::passed);

                if (!checksValid) {
                    failures.add("Required status checks have failed.");
                }
            }

            if (policy.requireSecurityReview()) {
                long approvals = pullRequest.reviews()
                    .stream()
                    .filter(review ->
                        review.role() == UserRole.SECURITY_REVIEWER)
                    .filter(review ->
                        review.decision() == ReviewDecision.APPROVED)
                    .filter(review -> !review.stale())
                    .filter(review -> !review.dismissed())
                    .map(Review::reviewer)
                    .distinct()
                    .count();

                if (approvals < policy.requiredApprovals()) {
                    failures.add(
                        "Required security approvals are missing."
                    );
                }
            }

            return List.copyOf(failures);
        }

        boolean eligible(
            PullRequest pullRequest,
            BranchProtectionPolicy policy
        ) {
            return evaluate(pullRequest, policy).isEmpty();
        }
    }

    static final class SessionService {
        private final Map<String, User> sessions =
            new ConcurrentHashMap<>();

        String createSession(User user) {
            String token = UUID.randomUUID().toString()
                + UUID.randomUUID();

            sessions.put(token, user);
            return token;
        }

        User authenticate(String token) {
            User user = sessions.get(token);

            if (user == null) {
                throw new AuthenticationException(
                    "Invalid session."
                );
            }

            return user;
        }

        void revoke(String token) {
            sessions.remove(token);
        }
    }

    static final class LoginRateLimiter {
        private final int maximumAttempts;
        private final Duration window;
        private final Map<String, AttemptWindow> windows =
            new ConcurrentHashMap<>();

        LoginRateLimiter(int maximumAttempts, Duration window) {
            if (maximumAttempts <= 0 || window.isNegative()
                || window.isZero()) {
                throw new IllegalArgumentException(
                    "Invalid rate-limit configuration."
                );
            }

            this.maximumAttempts = maximumAttempts;
            this.window = window;
        }

        void check(String identity) {
            Instant now = Instant.now();

            windows.compute(identity, (key, previous) -> {
                if (previous == null
                    || Duration.between(
                        previous.startedAt,
                        now
                    ).compareTo(window) >= 0) {
                    return new AttemptWindow(now, 1);
                }

                if (previous.count >= maximumAttempts) {
                    throw new SecurityPolicyException(
                        "Authentication rate limit exceeded."
                    );
                }

                previous.count++;
                return previous;
            });
        }

        static final class AttemptWindow {
            private final Instant startedAt;
            private final AtomicInteger counter;
            private int count;

            AttemptWindow(Instant startedAt, int count) {
                this.startedAt = startedAt;
                this.count = count;
                this.counter = new AtomicInteger(count);
            }
        }
    }

    private static final Pattern USERNAME_PATTERN =
        Pattern.compile("^[A-Za-z0-9_.-]{3,32}$");

    private static void requireText(
        String value,
        String field
    ) {
        if (value == null || value.isBlank()) {
            throw new SecurityValidationException(
                field + " cannot be empty."
            );
        }
    }

    private static void validateBranch(String branch) {
        requireText(branch, "branch");

        if (branch.length() > 255
            || branch.contains("..")
            || branch.contains("~")
            || branch.contains("^")
            || branch.contains(":")
            || branch.contains("\\")) {
            throw new SecurityValidationException(
                "Unsafe branch name."
            );
        }
    }

    private static String validateUsername(String username) {
        requireText(username, "username");

        if (!USERNAME_PATTERN.matcher(username).matches()) {
            throw new SecurityValidationException(
                "Username contains invalid characters."
            );
        }

        return username;
    }

    private static Repository createRepository() {
        Repository repository =
            new Repository("secure-web-platform");

        repository.addAsset(
            new Asset(
                "credential-store",
                SecurityLevel.CRITICAL,
                SecurityLevel.HIGH,
                SecurityLevel.MEDIUM,
                "identity-service"
            )
        );

        repository.addAsset(
            new Asset(
                "session-store",
                SecurityLevel.CRITICAL,
                SecurityLevel.CRITICAL,
                SecurityLevel.HIGH,
                "web-service"
            )
        );

        repository.addAsset(
            new Asset(
                "customer-data",
                SecurityLevel.HIGH,
                SecurityLevel.HIGH,
                SecurityLevel.HIGH,
                "data-service"
            )
        );

        repository.protectBranch(
            new BranchProtectionPolicy(
                "main",
                2,
                true,
                true,
                true,
                false,
                false
            )
        );

        return repository;
    }

    private static PullRequest createPullRequest() {
        User author = new User(
            validateUsername("application-owner"),
            EnumSet.of(UserRole.DEVELOPER)
        );

        PullRequest pullRequest = new PullRequest(
            42,
            author,
            "feature/input-validation",
            "main",
            Set.of(
                "src/web/RequestValidator.java",
                "src/web/SecurityHeaders.java",
                "test/security/InputValidationTest.java"
            )
        );

        pullRequest.addReview(
            new Review(
                "security-analyst",
                UserRole.SECURITY_REVIEWER,
                ReviewDecision.APPROVED,
                false,
                false
            )
        );

        pullRequest.addReview(
            new Review(
                "application-security-lead",
                UserRole.SECURITY_REVIEWER,
                ReviewDecision.APPROVED,
                false,
                false
            )
        );

        pullRequest.addStatusCheck(
            new StatusCheck("unit-tests", true, true)
        );

        pullRequest.addStatusCheck(
            new StatusCheck(
                "dependency-security-scan",
                true,
                true
            )
        );

        pullRequest.addStatusCheck(
            new StatusCheck(
                "static-analysis",
                true,
                true
            )
        );

        pullRequest.addFinding(
            new SecurityFinding(
                "SEC-001",
                "MEDIUM",
                true
            )
        );

        return pullRequest;
    }

    private static void runSelfTests() {
        Repository repository = createRepository();
        PullRequest pullRequest = createPullRequest();

        MergeEligibilityService service =
            new MergeEligibilityService();

        BranchProtectionPolicy policy =
            repository.policyFor("main");

        if (!service.eligible(pullRequest, policy)) {
            throw new AssertionError(
                "Valid Pull Request was rejected: "
                + service.evaluate(pullRequest, policy)
            );
        }

        pullRequest.setSourceBranchUpToDate(false);

        if (service.eligible(pullRequest, policy)) {
            throw new AssertionError(
                "Out-of-date branch was incorrectly accepted."
            );
        }

        pullRequest.setSourceBranchUpToDate(true);

        pullRequest.addFinding(
            new SecurityFinding(
                "SEC-002",
                "HIGH",
                false
            )
        );

        if (service.eligible(pullRequest, policy)) {
            throw new AssertionError(
                "Unresolved security finding was accepted."
            );
        }

        SessionService sessions = new SessionService();

        User securityReviewer = new User(
            "security-analyst",
            EnumSet.of(UserRole.SECURITY_REVIEWER)
        );

        String session = sessions.createSession(securityReviewer);

        if (!sessions.authenticate(session)
            .username()
            .equals("security-analyst")) {
            throw new AssertionError(
                "Session authentication failed."
            );
        }

        sessions.revoke(session);

        try {
            sessions.authenticate(session);
            throw new AssertionError(
                "Revoked session remained valid."
            );
        } catch (AuthenticationException expected) {
            // Expected security failure.
        }

        System.out.println("All Java 17 security tests passed.");
    }

    public static void main(String[] args) {
        try {
            runSelfTests();

            Repository repository = createRepository();
            PullRequest pullRequest = createPullRequest();

            MergeEligibilityService service =
                new MergeEligibilityService();

            BranchProtectionPolicy policy =
                repository.policyFor("main");

            System.out.println(
                "WEB SECURITY ENTERPRISE GOVERNANCE MODEL"
            );
            System.out.println(
                "============================================"
            );

            System.out.println("\nRepository: "
                + repository.name());

            System.out.println("\nProtected branch: "
                + policy.branchName());

            System.out.println(
                "Required security approvals: "
                + policy.requiredApprovals()
            );

            System.out.println(
                "Required status checks: "
                + policy.requireStatusChecks()
            );

            System.out.println("\nCIA assets");

            repository.assets().values().forEach(asset ->
                System.out.printf(
                    "- %s: C=%s, I=%s, A=%s%n",
                    asset.name(),
                    asset.confidentiality(),
                    asset.integrity(),
                    asset.availability()
                )
            );

            List<String> failures =
                service.evaluate(pullRequest, policy);

            System.out.println("\nPull Request #"
                + pullRequest.id());

            if (failures.isEmpty()) {
                System.out.println(
                    "Merge eligibility: ALLOWED"
                );
            } else {
                System.out.println(
                    "Merge eligibility: BLOCKED"
                );

                failures.forEach(
                    failure -> System.out.println(
                        "  - " + failure
                    )
                );
            }

            System.out.println(
                "\nSecurity controls represented by the model:"
            );
            System.out.println(
                "- authenticated sessions"
            );
            System.out.println(
                "- explicit security-review roles"
            );
            System.out.println(
                "- required status checks"
            );
            System.out.println(
                "- stale-approval rejection"
            );
            System.out.println(
                "- unresolved-finding blocking"
            );
            System.out.println(
                "- branch freshness enforcement"
            );
            System.out.println(
                "- merge-conflict enforcement"
            );

        } catch (RuntimeException error) {
            System.err.println(
                "Security policy execution failed: "
                + error.getMessage()
            );
            System.exit(1);
        }
    }
}
