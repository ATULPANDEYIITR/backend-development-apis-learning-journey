import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

public class SqlInjectionGovernanceDemo {

    enum ReviewState {
        PENDING,
        APPROVED,
        CHANGES_REQUESTED,
        DISMISSED
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
        long id,
        String username,
        String role
    ) {
        User {
            if (username == null || username.isBlank()) {
                throw new IllegalArgumentException("username is required");
            }
        }
    }

    record Review(
        User reviewer,
        ReviewState state,
        boolean eligible
    ) {}

    record StatusCheck(
        String name,
        CheckState state,
        boolean required
    ) {}

    record BranchProtectionPolicy(
        String branch,
        int requiredApprovals,
        boolean requirePullRequest,
        boolean requireResolvedConversations,
        boolean requirePassingChecks,
        boolean restrictDirectPush,
        boolean restrictForcePush,
        boolean restrictDeletion
    ) {
        BranchProtectionPolicy {
            if (branch == null || branch.isBlank()) {
                throw new IllegalArgumentException("protected branch is required");
            }
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "required approvals cannot be negative"
                );
            }
        }
    }

    record PullRequest(
        long id,
        String sourceBranch,
        String targetBranch,
        List<String> commits,
        List<Review> reviews,
        List<StatusCheck> checks,
        int unresolvedConversations,
        PullRequestState state,
        boolean mergeConflict,
        boolean sourceSynchronized
    ) {
        PullRequest {
            commits = List.copyOf(commits);
            reviews = List.copyOf(reviews);
            checks = List.copyOf(checks);

            if (id <= 0) {
                throw new IllegalArgumentException("invalid pull request id");
            }
            if (sourceBranch == null || sourceBranch.isBlank()) {
                throw new IllegalArgumentException("source branch is required");
            }
            if (targetBranch == null || targetBranch.isBlank()) {
                throw new IllegalArgumentException("target branch is required");
            }
            if (unresolvedConversations < 0) {
                throw new IllegalArgumentException(
                    "conversation count cannot be negative"
                );
            }
        }
    }

    record EligibilityDecision(
        boolean eligible,
        List<String> blockers,
        Instant evaluatedAt
    ) {}

    static final class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    static final class AuthenticationException extends RuntimeException {
        AuthenticationException() {
            super("invalid credentials");
        }
    }

    /*
     * This is an ORM-like query object.
     *
     * SQL text contains only fixed structure. Values are held in a separate
     * immutable collection. A real JDBC adapter would pass these values to
     * PreparedStatement.setString(), never concatenate them into SQL.
     */
    record ParameterizedQuery(
        String sql,
        List<Object> parameters
    ) {
        ParameterizedQuery {
            Objects.requireNonNull(sql);
            parameters = List.copyOf(parameters);
        }
    }

    interface UserRepository {
        User findByUsername(String username);

        User authenticate(String username, String password);
    }

    static final class InMemoryUserRepository implements UserRepository {
        private final Map<String, UserCredential> users = new HashMap<>();

        private record UserCredential(
            User user,
            String password
        ) {}

        InMemoryUserRepository() {
            users.put(
                "alice",
                new UserCredential(
                    new User(1, "alice", "user"),
                    "AlicePass!23"
                )
            );

            users.put(
                "admin",
                new UserCredential(
                    new User(2, "admin", "admin"),
                    "AdminPass!23"
                )
            );
        }

        @Override
        public User findByUsername(String username) {
            String safeUsername = validateUsername(username);

            ParameterizedQuery query = new ParameterizedQuery(
                "SELECT id, username, role FROM users WHERE username = ?",
                List.of(safeUsername)
            );

            logQuery(query);

            UserCredential credential = users.get(safeUsername);
            return credential == null ? null : credential.user();
        }

        @Override
        public User authenticate(String username, String password) {
            String safeUsername = validateUsername(username);

            ParameterizedQuery query = new ParameterizedQuery(
                """
                SELECT id, username, role
                FROM users
                WHERE username = ?
                  AND password = ?
                """,
                List.of(safeUsername, password)
            );

            logQueryWithoutSecrets(query);

            UserCredential credential = users.get(safeUsername);

            if (credential == null ||
                !credential.password().equals(password)) {
                throw new AuthenticationException();
            }

            return credential.user();
        }

        private static String validateUsername(String username) {
            if (username == null) {
                throw new ValidationException("username is required");
            }

            String value = username.trim();

            if (value.isEmpty()) {
                throw new ValidationException("username cannot be empty");
            }

            if (value.length() > 80) {
                throw new ValidationException("username is too long");
            }

            return value;
        }

        private static void logQuery(ParameterizedQuery query) {
            System.out.println("[ORM QUERY] " + query.sql());
            System.out.println("[PARAMETER COUNT] " +
                query.parameters().size());
        }

        private static void logQueryWithoutSecrets(
            ParameterizedQuery query
        ) {
            System.out.println("[ORM QUERY] " + query.sql());
            System.out.println(
                "[PARAMETERS] username=<bound>, password=<redacted>"
            );
        }
    }

    static final class MergeEligibilityService {
        EligibilityDecision evaluate(
            PullRequest pullRequest,
            BranchProtectionPolicy policy
        ) {
            List<String> blockers = new ArrayList<>();

            if (!pullRequest.targetBranch().equals(policy.branch())) {
                blockers.add("target branch is not covered by this policy");
            }

            if (policy.requirePullRequest() &&
                pullRequest.state() != PullRequestState.OPEN) {
                blockers.add("pull request must be open");
            }

            if (pullRequest.commits().isEmpty()) {
                blockers.add("pull request has no commits");
            }

            if (pullRequest.mergeConflict()) {
                blockers.add("merge conflicts must be resolved");
            }

            if (!pullRequest.sourceSynchronized()) {
                blockers.add("source branch is not synchronized");
            }

            if (policy.requireResolvedConversations() &&
                pullRequest.unresolvedConversations() > 0) {
                blockers.add("unresolved review conversations exist");
            }

            Set<Long> eligibleApprovers = pullRequest.reviews()
                .stream()
                .filter(Review::eligible)
                .filter(review ->
                    review.state() == ReviewState.APPROVED
                )
                .map(review -> review.reviewer().id())
                .collect(Collectors.toCollection(HashSet::new));

            if (eligibleApprovers.size() < policy.requiredApprovals()) {
                blockers.add(
                    "required eligible approvals are missing"
                );
            }

            if (policy.requirePassingChecks()) {
                pullRequest.checks()
                    .stream()
                    .filter(StatusCheck::required)
                    .filter(check -> check.state() != CheckState.PASSED)
                    .forEach(check ->
                        blockers.add(
                            "required check is not passing: " +
                            check.name()
                        )
                    );
            }

            return new EligibilityDecision(
                blockers.isEmpty(),
                List.copyOf(blockers),
                Instant.now()
            );
        }
    }

    static final class GovernanceService {
        private final UserRepository userRepository;
        private final MergeEligibilityService eligibilityService;

        GovernanceService(
            UserRepository userRepository,
            MergeEligibilityService eligibilityService
        ) {
            this.userRepository = userRepository;
            this.eligibilityService = eligibilityService;
        }

        User authenticate(String username, String password) {
            return userRepository.authenticate(username, password);
        }

        EligibilityDecision canMerge(
            PullRequest pullRequest,
            BranchProtectionPolicy policy
        ) {
            return eligibilityService.evaluate(pullRequest, policy);
        }
    }

    private static PullRequest buildPullRequest(
        User securityReviewer,
        User databaseReviewer,
        User externalReviewer
    ) {
        return new PullRequest(
            501,
            "feature/prepared-statements",
            "main",
            List.of("a1", "b2", "c3"),
            List.of(
                new Review(
                    securityReviewer,
                    ReviewState.APPROVED,
                    true
                ),
                new Review(
                    databaseReviewer,
                    ReviewState.APPROVED,
                    true
                ),
                new Review(
                    externalReviewer,
                    ReviewState.APPROVED,
                    false
                )
            ),
            List.of(
                new StatusCheck(
                    "unit-tests",
                    CheckState.PASSED,
                    true
                ),
                new StatusCheck(
                    "sql-injection-regression",
                    CheckState.PASSED,
                    true
                ),
                new StatusCheck(
                    "documentation",
                    CheckState.PENDING,
                    false
                )
            ),
            0,
            PullRequestState.OPEN,
            false,
            true
        );
    }

    private static void printDecision(EligibilityDecision decision) {
        System.out.println("\nMerge eligible: " + decision.eligible());
        System.out.println("Evaluated at: " + decision.evaluatedAt());

        if (!decision.blockers().isEmpty()) {
            System.out.println("Blockers:");
            decision.blockers().forEach(
                blocker -> System.out.println("  - " + blocker)
            );
        }
    }

    public static void main(String[] args) {
        UserRepository repository = new InMemoryUserRepository();

        GovernanceService service = new GovernanceService(
            repository,
            new MergeEligibilityService()
        );

        System.out.println("SQL injection protection with ORM-style binding");

        User admin = service.authenticate("admin", "AdminPass!23");
        System.out.println(
            "[AUTHENTICATED] " +
            admin.username() +
            " / " +
            admin.role()
        );

        try {
            service.authenticate(
                "' OR '1'='1",
                "incorrect"
            );
        } catch (AuthenticationException exception) {
            System.out.println(
                "[INJECTION-LIKE INPUT] treated as a username value"
            );
        }

        User securityReviewer =
            new User(10, "security-reviewer", "security");

        User databaseReviewer =
            new User(11, "database-reviewer", "database");

        User externalReviewer =
            new User(12, "external", "contributor");

        PullRequest pullRequest = buildPullRequest(
            securityReviewer,
            databaseReviewer,
            externalReviewer
        );

        BranchProtectionPolicy policy =
            new BranchProtectionPolicy(
                "main",
                2,
                true,
                true,
                true,
                true,
                true,
                true
            );

        EligibilityDecision decision =
            service.canMerge(pullRequest, policy);

        printDecision(decision);

        PullRequest blockedPullRequest = new PullRequest(
            pullRequest.id(),
            pullRequest.sourceBranch(),
            pullRequest.targetBranch(),
            pullRequest.commits(),
            pullRequest.reviews(),
            pullRequest.checks(),
            1,
            PullRequestState.OPEN,
            false,
            true
        );

        System.out.println(
            "\nAfter an unresolved review conversation:"
        );

        printDecision(
            service.canMerge(blockedPullRequest, policy)
        );

        System.out.println("\nSecurity boundaries:");
        System.out.println(
            "- validation checks application-level input rules"
        );
        System.out.println(
            "- parameter binding prevents input from becoming SQL syntax"
        );
        System.out.println(
            "- ORM/repository code centralizes database access"
        );
        System.out.println(
            "- least-privilege database roles reduce blast radius"
        );
        System.out.println(
            "- branch protection can prevent insecure database changes"
        );
    }
}
