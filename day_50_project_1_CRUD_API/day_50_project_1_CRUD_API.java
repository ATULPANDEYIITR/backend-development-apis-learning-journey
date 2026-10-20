import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

public class RepositoryGovernance {

    enum PullRequestState {
        DRAFT, OPEN, CLOSED, MERGED
    }

    enum ReviewState {
        COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED
    }

    enum MergeStrategy {
        MERGE, SQUASH, REBASE
    }

    record Reviewer(
            int id,
            String username,
            boolean eligible
    ) {}

    record ReviewComment(
            int id,
            String author,
            String body,
            boolean resolved
    ) {
        ReviewComment {
            if (body == null || body.isBlank()) {
                throw new IllegalArgumentException("comment body is required");
            }
        }
    }

    record Review(
            Reviewer reviewer,
            ReviewState state,
            boolean stale,
            List<ReviewComment> comments
    ) {
        Review {
            comments = List.copyOf(comments == null ? List.of() : comments);
        }
    }

    record StatusCheck(
            String name,
            boolean passed
    ) {}

    record BranchProtectionPolicy(
            int requiredApprovals,
            boolean requireStatusChecks,
            boolean requireConversationResolution,
            boolean restrictDirectPush,
            boolean restrictForcePush,
            boolean restrictDeletion,
            boolean requireLinearHistory
    ) {
        BranchProtectionPolicy {
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException("requiredApprovals cannot be negative");
            }
        }
    }

    static final class PullRequest {
        private final int id;
        private final String sourceBranch;
        private final String targetBranch;
        private final MergeStrategy mergeStrategy;
        private final List<Review> reviews = new ArrayList<>();
        private final List<StatusCheck> statusChecks = new ArrayList<>();
        private PullRequestState state;
        private Instant updatedAt;

        PullRequest(
                int id,
                String sourceBranch,
                String targetBranch,
                MergeStrategy mergeStrategy
        ) {
            if (sourceBranch == null || sourceBranch.isBlank()) {
                throw new IllegalArgumentException("source branch is required");
            }

            if (targetBranch == null || targetBranch.isBlank()) {
                throw new IllegalArgumentException("target branch is required");
            }

            if (sourceBranch.equals(targetBranch)) {
                throw new IllegalArgumentException(
                        "source and target branches must differ"
                );
            }

            this.id = id;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.mergeStrategy = Objects.requireNonNull(mergeStrategy);
            this.state = PullRequestState.OPEN;
            this.updatedAt = Instant.now();
        }

        void addReview(Review review) {
            Objects.requireNonNull(review);
            reviews.add(review);
            updatedAt = Instant.now();
        }

        void addStatusCheck(StatusCheck check) {
            Objects.requireNonNull(check);
            statusChecks.add(check);
            updatedAt = Instant.now();
        }

        void merge() {
            if (state != PullRequestState.OPEN) {
                throw new IllegalStateException("only open Pull Requests can merge");
            }

            state = PullRequestState.MERGED;
            updatedAt = Instant.now();
        }

        int id() {
            return id;
        }

        String targetBranch() {
            return targetBranch;
        }

        MergeStrategy mergeStrategy() {
            return mergeStrategy;
        }

        PullRequestState state() {
            return state;
        }

        List<Review> reviews() {
            return List.copyOf(reviews);
        }

        List<StatusCheck> statusChecks() {
            return List.copyOf(statusChecks);
        }
    }

    record MergeDecision(
            boolean eligible,
            List<String> reasons
    ) {
        MergeDecision {
            reasons = List.copyOf(reasons);
        }
    }

    static final class MergeEligibilityService {

        MergeDecision evaluate(
                PullRequest pullRequest,
                BranchProtectionPolicy policy,
                Set<String> protectedBranches
        ) {
            List<String> reasons = new ArrayList<>();

            if (pullRequest.state() != PullRequestState.OPEN) {
                reasons.add("Pull Request is not open");
            }

            if (!protectedBranches.contains(pullRequest.targetBranch())) {
                return new MergeDecision(reasons.isEmpty(), reasons);
            }

            if (policy.requireStatusChecks()) {
                if (pullRequest.statusChecks().isEmpty()) {
                    reasons.add("required status checks have not run");
                } else {
                    pullRequest.statusChecks().stream()
                            .filter(check -> !check.passed())
                            .map(StatusCheck::name)
                            .forEach(name ->
                                    reasons.add("failed status check: " + name));
                }
            }

            Set<Integer> eligibleApprovers =
                    pullRequest.reviews().stream()
                            .filter(review ->
                                    review.state() == ReviewState.APPROVED &&
                                    !review.stale() &&
                                    review.reviewer().eligible())
                            .map(review -> review.reviewer().id())
                            .collect(Collectors.toSet());

            if (eligibleApprovers.size() < policy.requiredApprovals()) {
                reasons.add(
                        "required approvals: " +
                        policy.requiredApprovals() +
                        ", valid approvals: " +
                        eligibleApprovers.size()
                );
            }

            boolean changesRequested =
                    pullRequest.reviews().stream()
                            .anyMatch(review ->
                                    !review.stale() &&
                                    review.state() == ReviewState.CHANGES_REQUESTED);

            if (changesRequested) {
                reasons.add("an active reviewer requested changes");
            }

            if (policy.requireConversationResolution()) {
                boolean unresolved =
                        pullRequest.reviews().stream()
                                .filter(review -> !review.stale())
                                .flatMap(review -> review.comments().stream())
                                .anyMatch(comment -> !comment.resolved());

                if (unresolved) {
                    reasons.add("unresolved review conversations remain");
                }
            }

            if (policy.requireLinearHistory() &&
                    pullRequest.mergeStrategy() == MergeStrategy.MERGE) {
                reasons.add("merge commit is incompatible with linear-history policy");
            }

            return new MergeDecision(reasons.isEmpty(), reasons);
        }
    }

    static final class Repository {

        private final String name;
        private final String defaultBranch;
        private final Set<String> protectedBranches;
        private BranchProtectionPolicy policy;

        Repository(
                String name,
                String defaultBranch,
                Set<String> protectedBranches,
                BranchProtectionPolicy policy
        ) {
            this.name = Objects.requireNonNull(name);
            this.defaultBranch = Objects.requireNonNull(defaultBranch);
            this.protectedBranches = Set.copyOf(protectedBranches);
            this.policy = Objects.requireNonNull(policy);
        }

        BranchProtectionPolicy policy() {
            return policy;
        }

        void updatePolicy(BranchProtectionPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        String name() {
            return name;
        }

        Set<String> protectedBranches() {
            return protectedBranches;
        }
    }

    public static void main(String[] args) {
        Reviewer alice = new Reviewer(1, "alice", true);
        Reviewer bob = new Reviewer(2, "bob", true);
        Reviewer contractor = new Reviewer(3, "contractor", false);

        Repository repository = new Repository(
                "payments-service",
                "main",
                Set.of("main"),
                new BranchProtectionPolicy(
                        2,
                        true,
                        true,
                        true,
                        true,
                        true,
                        true
                )
        );

        PullRequest pullRequest = new PullRequest(
                1001,
                "feature/idempotency",
                "main",
                MergeStrategy.SQUASH
        );

        pullRequest.addStatusCheck(new StatusCheck("build", true));
        pullRequest.addStatusCheck(new StatusCheck("unit-tests", true));
        pullRequest.addStatusCheck(new StatusCheck("security-scan", true));

        pullRequest.addReview(
                new Review(
                        alice,
                        ReviewState.APPROVED,
                        false,
                        List.of()
                )
        );

        pullRequest.addReview(
                new Review(
                        bob,
                        ReviewState.APPROVED,
                        false,
                        List.of()
                )
        );

        // An approval from an ineligible reviewer cannot satisfy the policy.
        pullRequest.addReview(
                new Review(
                        contractor,
                        ReviewState.APPROVED,
                        false,
                        List.of()
                )
        );

        MergeEligibilityService service = new MergeEligibilityService();

        MergeDecision decision = service.evaluate(
                pullRequest,
                repository.policy(),
                repository.protectedBranches()
        );

        System.out.println("Repository: " + repository.name());
        System.out.println("Merge eligible: " + decision.eligible());

        if (!decision.eligible()) {
            decision.reasons().forEach(reason ->
                    System.out.println("Blocked: " + reason));
        } else {
            pullRequest.merge();
            System.out.println("Pull Request merged successfully.");
        }

        // Stale approvals demonstrate a state transition caused by a new changeset.
        PullRequest changedPullRequest = new PullRequest(
                1002,
                "feature/payment-retry",
                "main",
                MergeStrategy.SQUASH
        );

        changedPullRequest.addStatusCheck(new StatusCheck("build", true));
        changedPullRequest.addStatusCheck(new StatusCheck("unit-tests", true));

        changedPullRequest.addReview(
                new Review(
                        alice,
                        ReviewState.APPROVED,
                        true,
                        List.of()
                )
        );

        MergeDecision staleDecision = service.evaluate(
                changedPullRequest,
                repository.policy(),
                repository.protectedBranches()
        );

        System.out.println("\nChanged Pull Request merge eligible: "
                + staleDecision.eligible());

        staleDecision.reasons().forEach(reason ->
                System.out.println("Blocked: " + reason));
    }
}
