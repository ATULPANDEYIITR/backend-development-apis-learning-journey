import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;


public class RepositoryGovernanceDemo {

    enum PullRequestState {
        DRAFT,
        OPEN,
        CLOSED,
        MERGED
    }


    enum ReviewState {
        PENDING,
        COMMENTED,
        APPROVED,
        CHANGES_REQUESTED
    }


    enum StatusState {
        PENDING,
        PASSED,
        FAILED
    }


    record User(long id, String username, String email) {
        public User {
            if (id <= 0) {
                throw new IllegalArgumentException("User ID must be positive");
            }

            if (username == null || username.isBlank()) {
                throw new IllegalArgumentException(
                    "Username cannot be blank"
                );
            }

            if (email == null || !email.contains("@")) {
                throw new IllegalArgumentException(
                    "Invalid email address"
                );
            }
        }
    }


    record Commit(
        long id,
        String sha,
        String message
    ) {
        public Commit {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Commit ID must be positive"
                );
            }

            if (sha == null || !sha.matches("[0-9a-fA-F]{40}")) {
                throw new IllegalArgumentException(
                    "Commit SHA must contain 40 hexadecimal characters"
                );
            }
        }
    }


    record Review(
        long id,
        long reviewerId,
        ReviewState state,
        String body
    ) {
        public Review {
            Objects.requireNonNull(state, "Review state is required");
            body = body == null ? "" : body;
        }
    }


    record StatusCheck(
        String name,
        StatusState state
    ) {
        public StatusCheck {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Status check name cannot be blank"
                );
            }

            Objects.requireNonNull(state, "Status state is required");
        }
    }


    static final class BranchProtectionPolicy {
        private final int requiredApprovals;
        private final Set<String> requiredStatusChecks;
        private final boolean allowForcePush;
        private final boolean allowDeletion;
        private final boolean requireLinearHistory;

        BranchProtectionPolicy(
            int requiredApprovals,
            Set<String> requiredStatusChecks,
            boolean allowForcePush,
            boolean allowDeletion,
            boolean requireLinearHistory
        ) {
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "Required approvals cannot be negative"
                );
            }

            this.requiredApprovals = requiredApprovals;
            this.requiredStatusChecks =
                Set.copyOf(requiredStatusChecks);
            this.allowForcePush = allowForcePush;
            this.allowDeletion = allowDeletion;
            this.requireLinearHistory = requireLinearHistory;
        }

        int requiredApprovals() {
            return requiredApprovals;
        }

        Set<String> requiredStatusChecks() {
            return requiredStatusChecks;
        }

        boolean allowForcePush() {
            return allowForcePush;
        }

        boolean allowDeletion() {
            return allowDeletion;
        }

        boolean requireLinearHistory() {
            return requireLinearHistory;
        }
    }


    static final class Branch {
        private final String name;
        private final BranchProtectionPolicy protectionPolicy;

        Branch(
            String name,
            BranchProtectionPolicy protectionPolicy
        ) {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Branch name cannot be blank"
                );
            }

            this.name = name;
            this.protectionPolicy = protectionPolicy;
        }

        String name() {
            return name;
        }

        BranchProtectionPolicy protectionPolicy() {
            return protectionPolicy;
        }
    }


    static final class PullRequest {
        private final long id;
        private final User author;
        private final String title;
        private final String sourceBranch;
        private final String targetBranch;

        private PullRequestState state = PullRequestState.OPEN;

        private final List<Commit> commits = new ArrayList<>();
        private final List<Review> reviews = new ArrayList<>();
        private final List<StatusCheck> statusChecks =
            new ArrayList<>();
        private final Set<Long> assignedReviewerIds =
            new HashSet<>();

        PullRequest(
            long id,
            User author,
            String title,
            String sourceBranch,
            String targetBranch
        ) {
            if (sourceBranch.equals(targetBranch)) {
                throw new IllegalArgumentException(
                    "Source and target branches must differ"
                );
            }

            this.id = id;
            this.author = Objects.requireNonNull(author);
            this.title = Objects.requireNonNull(title);
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
        }

        void assignReviewer(User reviewer) {
            Objects.requireNonNull(reviewer);

            if (reviewer.id() == author.id()) {
                throw new IllegalArgumentException(
                    "Pull Request authors cannot approve their own changes"
                );
            }

            assignedReviewerIds.add(reviewer.id());
        }

        void addCommit(Commit commit) {
            commits.add(Objects.requireNonNull(commit));
        }

        void addReview(Review review) {
            if (!assignedReviewerIds.contains(review.reviewerId())) {
                throw new IllegalStateException(
                    "Reviewer is not assigned to this Pull Request"
                );
            }

            if (review.reviewerId() == author.id()) {
                throw new IllegalStateException(
                    "Self-review is not allowed"
                );
            }

            reviews.add(review);
        }

        void addStatusCheck(StatusCheck check) {
            statusChecks.add(Objects.requireNonNull(check));
        }

        long id() {
            return id;
        }

        String title() {
            return title;
        }

        String targetBranch() {
            return targetBranch;
        }

        List<Review> reviews() {
            return List.copyOf(reviews);
        }

        List<StatusCheck> statusChecks() {
            return List.copyOf(statusChecks);
        }

        List<Commit> commits() {
            return List.copyOf(commits);
        }

        Set<Long> assignedReviewerIds() {
            return Set.copyOf(assignedReviewerIds);
        }

        PullRequestState state() {
            return state;
        }

        void merge() {
            if (state != PullRequestState.OPEN) {
                throw new IllegalStateException(
                    "Only an open Pull Request can be merged"
                );
            }

            state = PullRequestState.MERGED;
        }
    }


    record MergeDecision(
        boolean eligible,
        List<String> reasons
    ) {}


    static final class MergeEligibilityService {

        MergeDecision evaluate(
            PullRequest pullRequest,
            Branch targetBranch
        ) {
            List<String> reasons = new ArrayList<>();

            if (pullRequest.state() != PullRequestState.OPEN) {
                reasons.add("Pull Request is not open");
            }

            if (pullRequest.commits().isEmpty()) {
                reasons.add("Pull Request has no commits");
            }

            BranchProtectionPolicy policy =
                targetBranch.protectionPolicy();

            if (policy == null) {
                reasons.add(
                    "Target branch has no protection policy"
                );

                return new MergeDecision(false, List.copyOf(reasons));
            }

            long approvals = pullRequest.reviews()
                .stream()
                .filter(review ->
                    review.state() == ReviewState.APPROVED
                )
                .map(Review::reviewerId)
                .distinct()
                .filter(pullRequest.assignedReviewerIds()::contains)
                .count();

            if (approvals < policy.requiredApprovals()) {
                reasons.add(
                    "Required approval threshold has not been met"
                );
            }

            boolean changesRequested = pullRequest.reviews()
                .stream()
                .anyMatch(review ->
                    review.state() == ReviewState.CHANGES_REQUESTED
                );

            if (changesRequested) {
                reasons.add(
                    "A reviewer has requested changes"
                );
            }

            Map<String, StatusState> statusByName =
                new HashMap<>();

            for (StatusCheck check : pullRequest.statusChecks()) {
                statusByName.put(check.name(), check.state());
            }

            for (String required :
                policy.requiredStatusChecks()) {

                StatusState state = statusByName.get(required);

                if (state != StatusState.PASSED) {
                    reasons.add(
                        "Required status check is not passing: "
                            + required
                    );
                }
            }

            return new MergeDecision(
                reasons.isEmpty(),
                List.copyOf(reasons)
            );
        }
    }


    public static void main(String[] args) {
        User alice = new User(
            1,
            "alice",
            "alice@example.com"
        );

        User bob = new User(
            2,
            "bob",
            "bob@example.com"
        );

        User carol = new User(
            3,
            "carol",
            "carol@example.com"
        );

        BranchProtectionPolicy policy =
            new BranchProtectionPolicy(
                2,
                Set.of("unit-tests", "security-scan"),
                false,
                false,
                true
            );

        Branch main = new Branch("main", policy);

        PullRequest pullRequest = new PullRequest(
            100,
            alice,
            "Add payment validation",
            "feature/payment-validation",
            "main"
        );

        pullRequest.assignReviewer(bob);
        pullRequest.assignReviewer(carol);

        pullRequest.addCommit(
            new Commit(
                500,
                "0123456789abcdef0123456789abcdef01234567",
                "Implement validation"
            )
        );

        pullRequest.addReview(
            new Review(
                900,
                bob.id(),
                ReviewState.APPROVED,
                "Validation looks correct."
            )
        );

        pullRequest.addReview(
            new Review(
                901,
                carol.id(),
                ReviewState.APPROVED,
                "Security requirements are covered."
            )
        );

        pullRequest.addStatusCheck(
            new StatusCheck(
                "unit-tests",
                StatusState.PASSED
            )
        );

        pullRequest.addStatusCheck(
            new StatusCheck(
                "security-scan",
                StatusState.PASSED
            )
        );

        MergeEligibilityService service =
            new MergeEligibilityService();

        MergeDecision decision =
            service.evaluate(pullRequest, main);

        System.out.println(
            "Pull Request: " + pullRequest.title()
        );

        System.out.println(
            "Merge eligible: " + decision.eligible()
        );

        decision.reasons().forEach(
            reason -> System.out.println("Reason: " + reason)
        );

        if (decision.eligible()) {
            pullRequest.merge();
            System.out.println(
                "State after merge: " + pullRequest.state()
            );
        }

        // A later status failure demonstrates that merge eligibility is a
        // policy decision based on the current state, not a permanent flag.
        pullRequest.addStatusCheck(
            new StatusCheck(
                "security-scan",
                StatusState.FAILED
            )
        );

        System.out.println(
            "Current merge state after failed security scan: "
                + service.evaluate(pullRequest, main).eligible()
        );

        // EnumSet is useful when an application needs efficient handling of
        // a finite set of known workflow states.
        Set<ReviewState> terminalReviewStates =
            EnumSet.of(
                ReviewState.APPROVED,
                ReviewState.CHANGES_REQUESTED
            );

        System.out.println(
            "Terminal review states: "
                + terminalReviewStates
        );
    }
}
