import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

public class ApiSecurityGovernance {

    enum PullRequestState {
        DRAFT, OPEN, CLOSED, MERGED
    }

    enum ReviewState {
        COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED
    }

    enum CheckState {
        PENDING, PASSED, FAILED
    }

    enum Severity {
        LOW, MEDIUM, HIGH, CRITICAL
    }

    enum SecurityCategory {
        BROKEN_AUTHORIZATION,
        EXCESSIVE_DATA_EXPOSURE,
        INJECTION,
        SSRF,
        SECURITY_MISCONFIGURATION
    }

    record User(
        String username,
        String team,
        boolean administrator
    ) {
        public User {
            requireText(username, "username");
            requireText(team, "team");
        }
    }

    record Commit(
        String sha,
        User author,
        String message,
        List<String> files
    ) {
        public Commit {
            requireText(sha, "sha");
            Objects.requireNonNull(author, "author");
            requireText(message, "message");
            if (files == null || files.isEmpty()) {
                throw new ValidationException(
                    "A commit must contain at least one file."
                );
            }
            files = List.copyOf(files);
        }
    }

    record StatusCheck(
        String name,
        CheckState state,
        String details
    ) {
        public StatusCheck {
            requireText(name, "name");
            Objects.requireNonNull(state, "state");
            requireText(details, "details");
        }
    }

    record SecurityFinding(
        SecurityCategory category,
        Severity severity,
        String endpoint,
        String description
    ) {
        public SecurityFinding {
            Objects.requireNonNull(category, "category");
            Objects.requireNonNull(severity, "severity");
            requireText(endpoint, "endpoint");
            requireText(description, "description");
        }

        boolean blocksMerge() {
            return severity == Severity.HIGH ||
                   severity == Severity.CRITICAL;
        }
    }

    record ReviewComment(
        User reviewer,
        String file,
        int line,
        String body,
        boolean resolved
    ) {
        public ReviewComment {
            Objects.requireNonNull(reviewer, "reviewer");
            requireText(file, "file");
            if (line < 1) {
                throw new ValidationException(
                    "Line must be positive."
                );
            }
            requireText(body, "body");
        }

        ReviewComment resolve() {
            return new ReviewComment(
                reviewer,
                file,
                line,
                body,
                true
            );
        }
    }

    record Review(
        User reviewer,
        ReviewState state,
        String reviewedCommit,
        List<ReviewComment> comments
    ) {
        public Review {
            Objects.requireNonNull(reviewer, "reviewer");
            Objects.requireNonNull(state, "state");
            requireText(reviewedCommit, "reviewedCommit");
            comments = comments == null
                ? List.of()
                : List.copyOf(comments);
        }
    }

    record Branch(
        String name,
        String headSha,
        boolean protectedBranch
    ) {
        public Branch {
            requireText(name, "name");
            requireText(headSha, "headSha");
        }
    }

    record BranchProtectionPolicy(
        int requiredApprovals,
        Set<String> requiredChecks,
        boolean requireConversationResolution,
        boolean requireCodeOwnerReview,
        boolean requireLinearHistory,
        boolean allowForcePush,
        boolean allowBranchDeletion,
        boolean administratorsCanBypass
    ) {
        public BranchProtectionPolicy {
            if (requiredApprovals < 1) {
                throw new ValidationException(
                    "At least one approval is required."
                );
            }

            requiredChecks = Set.copyOf(requiredChecks);

            if (administratorsCanBypass && !requireLinearHistory) {
                throw new ValidationException(
                    "Administrator bypass cannot weaken a "
                    + "linear-history policy."
                );
            }
        }

        static BranchProtectionPolicy strictApiPolicy() {
            return new BranchProtectionPolicy(
                2,
                Set.of(
                    "unit-tests",
                    "api-security-scan",
                    "authorization-tests"
                ),
                true,
                true,
                true,
                false,
                false,
                false
            );
        }
    }

    static final class PullRequest {
        private final int number;
        private final User author;
        private final String title;
        private final String sourceBranch;
        private final String targetBranch;
        private final List<Commit> commits = new ArrayList<>();
        private final List<Review> reviews = new ArrayList<>();
        private final List<ReviewComment> comments = new ArrayList<>();
        private final Map<String, StatusCheck> checks =
            new LinkedHashMap<>();
        private final List<SecurityFinding> findings =
            new ArrayList<>();

        private PullRequestState state;
        private String baseSha;
        private String headSha;
        private String mergeSha;

        PullRequest(
            int number,
            User author,
            String title,
            String sourceBranch,
            String targetBranch,
            String baseSha,
            String headSha,
            boolean draft
        ) {
            this.number = number;
            this.author = author;
            this.title = title;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.baseSha = baseSha;
            this.headSha = headSha;
            this.state = draft
                ? PullRequestState.DRAFT
                : PullRequestState.OPEN;
        }

        void addCommit(Commit commit) {
            if (state != PullRequestState.OPEN &&
                state != PullRequestState.DRAFT) {
                throw new DomainException(
                    "Cannot add a commit in state " + state
                );
            }

            commits.add(commit);
            headSha = commit.sha();

            // An approval is a decision about a specific commit.
            // A new commit requires reviewers to reassess the change.
            List<Review> staleReviews = reviews.stream()
                .map(review ->
                    review.state() == ReviewState.APPROVED
                        ? new Review(
                            review.reviewer(),
                            ReviewState.DISMISSED,
                            review.reviewedCommit(),
                            review.comments()
                        )
                        : review
                )
                .toList();

            reviews.clear();
            reviews.addAll(staleReviews);
        }

        void addCheck(StatusCheck check) {
            checks.put(check.name(), check);
        }

        void addFinding(SecurityFinding finding) {
            findings.add(finding);
        }

        void addReview(Review review) {
            if (state != PullRequestState.OPEN) {
                throw new DomainException(
                    "Reviews require an open Pull Request."
                );
            }

            if (review.reviewer().equals(author)) {
                throw new DomainException(
                    "Self-approval is forbidden."
                );
            }

            reviews.add(review);
            comments.addAll(review.comments());
        }

        void resolveComment(User reviewer, String file, int line) {
            for (int i = 0; i < comments.size(); i++) {
                ReviewComment comment = comments.get(i);

                if (comment.reviewer().equals(reviewer) &&
                    comment.file().equals(file) &&
                    comment.line() == line) {

                    comments.set(i, comment.resolve());
                    return;
                }
            }

            throw new DomainException(
                "Review conversation not found."
            );
        }

        int number() {
            return number;
        }

        User author() {
            return author;
        }

        String title() {
            return title;
        }

        String sourceBranch() {
            return sourceBranch;
        }

        String targetBranch() {
            return targetBranch;
        }

        List<Commit> commits() {
            return Collections.unmodifiableList(commits);
        }

        List<Review> reviews() {
            return Collections.unmodifiableList(reviews);
        }

        List<ReviewComment> comments() {
            return Collections.unmodifiableList(comments);
        }

        Map<String, StatusCheck> checks() {
            return Collections.unmodifiableMap(checks);
        }

        List<SecurityFinding> findings() {
            return Collections.unmodifiableList(findings);
        }

        PullRequestState state() {
            return state;
        }

        void state(PullRequestState state) {
            this.state = state;
        }

        String baseSha() {
            return baseSha;
        }

        void baseSha(String baseSha) {
            this.baseSha = baseSha;
        }

        String headSha() {
            return headSha;
        }

        String mergeSha() {
            return mergeSha;
        }

        void mergeSha(String mergeSha) {
            this.mergeSha = mergeSha;
        }
    }

    record EligibilityResult(
        boolean eligible,
        List<String> reasons
    ) {}

    interface ReviewPolicy {
        EligibilityResult evaluate(
            PullRequest pullRequest,
            Branch targetBranch
        );
    }

    static final class ApiSecurityReviewPolicy
        implements ReviewPolicy {

        private final BranchProtectionPolicy protection;
        private final Map<String, Set<User>> codeOwners;

        ApiSecurityReviewPolicy(
            BranchProtectionPolicy protection,
            Map<String, Set<User>> codeOwners
        ) {
            this.protection = protection;
            this.codeOwners = Map.copyOf(codeOwners);
        }

        @Override
        public EligibilityResult evaluate(
            PullRequest pullRequest,
            Branch targetBranch
        ) {
            List<String> reasons = new ArrayList<>();

            if (pullRequest.state() != PullRequestState.OPEN) {
                reasons.add(
                    "Pull Request is " +
                    pullRequest.state().name().toLowerCase()
                );
            }

            if (targetBranch.protectedBranch()) {
                if (!pullRequest.baseSha()
                    .equals(targetBranch.headSha())) {
                    reasons.add(
                        "Pull Request base is stale."
                    );
                }

                for (String required :
                    protection.requiredChecks()) {

                    StatusCheck check =
                        pullRequest.checks().get(required);

                    if (check == null ||
                        check.state() != CheckState.PASSED) {
                        reasons.add(
                            "Required check is not passing: " +
                            required
                        );
                    }
                }

                if (protection.requireConversationResolution()) {
                    long unresolved = pullRequest.comments()
                        .stream()
                        .filter(comment -> !comment.resolved())
                        .count();

                    if (unresolved > 0) {
                        reasons.add(
                            unresolved +
                            " review conversation(s) unresolved."
                        );
                    }
                }

                pullRequest.findings()
                    .stream()
                    .filter(SecurityFinding::blocksMerge)
                    .map(finding ->
                        finding.category().name() +
                        " " +
                        finding.severity().name() +
                        " finding at " +
                        finding.endpoint()
                    )
                    .forEach(reasons::add);

                Set<User> approvals =
                    currentApprovals(pullRequest);

                if (approvals.size() <
                    protection.requiredApprovals()) {
                    reasons.add(
                        approvals.size() +
                        " current approval(s); " +
                        protection.requiredApprovals() +
                        " required."
                    );
                }

                if (protection.requireCodeOwnerReview() &&
                    !hasCodeOwnerApproval(
                        pullRequest,
                        approvals
                    )) {
                    reasons.add(
                        "API security code-owner approval is missing."
                    );
                }
            }

            return new EligibilityResult(
                reasons.isEmpty(),
                List.copyOf(reasons)
            );
        }

        private Set<User> currentApprovals(
            PullRequest pullRequest
        ) {
            Map<User, Review> latest = new HashMap<>();

            for (Review review : pullRequest.reviews()) {
                if (review.reviewer().equals(
                    pullRequest.author()
                )) {
                    continue;
                }

                if (review.state() == ReviewState.DISMISSED) {
                    latest.remove(review.reviewer());
                } else {
                    latest.put(
                        review.reviewer(),
                        review
                    );
                }
            }

            return latest.values()
                .stream()
                .filter(review ->
                    review.state() == ReviewState.APPROVED &&
                    review.reviewedCommit().equals(
                        pullRequest.headSha()
                    )
                )
                .map(Review::reviewer)
                .collect(Collectors.toSet());
        }

        private boolean hasCodeOwnerApproval(
            PullRequest pullRequest,
            Set<User> approvals
        ) {
            Set<User> owners = new HashSet<>();

            for (Commit commit : pullRequest.commits()) {
                for (String file : commit.files()) {
                    codeOwners.forEach((prefix, ownerSet) -> {
                        if (file.startsWith(prefix)) {
                            owners.addAll(ownerSet);
                        }
                    });
                }
            }

            return owners.isEmpty() ||
                owners.stream().anyMatch(approvals::contains);
        }
    }

    static final class RepositoryGovernanceService {
        private final Map<String, Branch> branches =
            new LinkedHashMap<>();
        private final Map<Integer, PullRequest> pullRequests =
            new LinkedHashMap<>();
        private final BranchProtectionPolicy policy;
        private final ReviewPolicy reviewPolicy;
        private int nextPrNumber = 1;

        RepositoryGovernanceService(
            BranchProtectionPolicy policy,
            ReviewPolicy reviewPolicy
        ) {
            this.policy = policy;
            this.reviewPolicy = reviewPolicy;
        }

        void addBranch(Branch branch) {
            if (branches.containsKey(branch.name())) {
                throw new ValidationException(
                    "Branch already exists."
                );
            }
            branches.put(branch.name(), branch);
        }

        PullRequest createPullRequest(
            User author,
            String title,
            String source,
            String target,
            boolean draft
        ) {
            Branch sourceBranch = branches.get(source);
            Branch targetBranch = branches.get(target);

            if (sourceBranch == null ||
                targetBranch == null) {
                throw new ValidationException(
                    "Both branches must exist."
                );
            }

            if (source.equals(target)) {
                throw new ValidationException(
                    "Source and target branches must differ."
                );
            }

            PullRequest pullRequest =
                new PullRequest(
                    nextPrNumber++,
                    author,
                    title,
                    source,
                    target,
                    targetBranch.headSha(),
                    sourceBranch.headSha(),
                    draft
                );

            pullRequests.put(
                pullRequest.number(),
                pullRequest
            );

            return pullRequest;
        }

        String merge(PullRequest pullRequest) {
            Branch target =
                branches.get(pullRequest.targetBranch());

            if (target == null) {
                throw new ValidationException(
                    "Target branch does not exist."
                );
            }

            EligibilityResult result =
                reviewPolicy.evaluate(
                    pullRequest,
                    target
                );

            if (!result.eligible()) {
                throw new MergeBlockedException(
                    result.reasons()
                );
            }

            String mergeSha = Integer.toHexString(
                Objects.hash(
                    pullRequest.number(),
                    pullRequest.headSha(),
                    target.headSha()
                )
            );

            branches.put(
                target.name(),
                new Branch(
                    target.name(),
                    mergeSha,
                    target.protectedBranch()
                )
            );

            pullRequest.mergeSha(mergeSha);
            pullRequest.state(PullRequestState.MERGED);

            return mergeSha;
        }
    }

    static class DomainException extends RuntimeException {
        DomainException(String message) {
            super(message);
        }
    }

    static class ValidationException extends DomainException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class MergeBlockedException extends DomainException {
        MergeBlockedException(List<String> reasons) {
            super(
                "Merge blocked:\n- " +
                String.join("\n- ", reasons)
            );
        }
    }

    static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new ValidationException(
                field + " must not be blank."
            );
        }
    }

    public static void main(String[] args) {
        User developer =
            new User("developer", "backend", false);

        User backendReviewer =
            new User("backend-reviewer", "backend", false);

        User securityLead =
            new User("security-lead", "security", false);

        BranchProtectionPolicy policy =
            BranchProtectionPolicy.strictApiPolicy();

        Map<String, Set<User>> codeOwners =
            Map.of(
                "api/",
                Set.of(securityLead),
                "auth/",
                Set.of(securityLead)
            );

        ReviewPolicy reviewPolicy =
            new ApiSecurityReviewPolicy(
                policy,
                codeOwners
            );

        RepositoryGovernanceService service =
            new RepositoryGovernanceService(
                policy,
                reviewPolicy
            );

        service.addBranch(
            new Branch(
                "main",
                "main-001",
                true
            )
        );

        service.addBranch(
            new Branch(
                "feature/authz",
                "feature-001",
                false
            )
        );

        PullRequest pr =
            service.createPullRequest(
                developer,
                "Enforce object-level authorization",
                "feature/authz",
                "main",
                false
            );

        pr.addCommit(
            new Commit(
                "commit-001",
                developer,
                "Add tenant ownership checks",
                List.of(
                    "api/orders.java",
                    "auth/authorization.java"
                )
            )
        );

        pr.addFinding(
            new SecurityFinding(
                SecurityCategory.BROKEN_AUTHORIZATION,
                Severity.LOW,
                "GET /api/orders/{id}",
                "Ownership is verified before object access."
            )
        );

        for (String check : policy.requiredChecks()) {
            pr.addCheck(
                new StatusCheck(
                    check,
                    CheckState.PASSED,
                    "Passed."
                )
            );
        }

        pr.addReview(
            new Review(
                backendReviewer,
                ReviewState.APPROVED,
                pr.headSha(),
                List.of(
                    new ReviewComment(
                        backendReviewer,
                        "api/orders.java",
                        58,
                        "Verify the tenant comes from "
                            + "the authenticated principal.",
                        false
                    )
                )
            )
        );

        pr.addReview(
            new Review(
                securityLead,
                ReviewState.APPROVED,
                pr.headSha(),
                List.of()
            )
        );

        try {
            service.merge(pr);
        } catch (MergeBlockedException exception) {
            System.out.println(
                "Expected unresolved-conversation block:"
            );
            System.out.println(exception.getMessage());
            System.out.println();
        }

        pr.resolveComment(
            backendReviewer,
            "api/orders.java",
            58
        );

        String mergeSha = service.merge(pr);

        System.out.println("Merged Pull Request");
        System.out.println("Number: #" + pr.number());
        System.out.println("State: " + pr.state());
        System.out.println("Merge SHA: " + mergeSha);
        System.out.println("Timestamp: " + Instant.now());
        System.out.println();

        service.addBranch(
            new Branch(
                "feature/ssrf",
                "feature-002",
                false
            )
        );

        PullRequest blocked =
            service.createPullRequest(
                developer,
                "Add outbound webhook testing",
                "feature/ssrf",
                "main",
                false
            );

        blocked.addCommit(
            new Commit(
                "commit-002",
                developer,
                "Add URL fetch endpoint",
                List.of("api/webhook.java")
            )
        );

        blocked.addFinding(
            new SecurityFinding(
                SecurityCategory.SSRF,
                Severity.HIGH,
                "POST /api/webhooks/test",
                "Untrusted URL can access private network targets."
            )
        );

        for (String check : policy.requiredChecks()) {
            blocked.addCheck(
                new StatusCheck(
                    check,
                    CheckState.PASSED,
                    "Passed."
                )
            );
        }

        blocked.addReview(
            new Review(
                securityLead,
                ReviewState.APPROVED,
                blocked.headSha(),
                List.of()
            )
        );

        blocked.addReview(
            new Review(
                backendReviewer,
                ReviewState.APPROVED,
                blocked.headSha(),
                List.of()
            )
        );

        try {
            service.merge(blocked);
        } catch (MergeBlockedException exception) {
            System.out.println(
                "Expected high-severity security block:"
            );
            System.out.println(exception.getMessage());
        }
    }
}
