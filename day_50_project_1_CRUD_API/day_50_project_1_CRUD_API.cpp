#include <algorithm>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

enum class PullRequestState {
    Draft,
    Open,
    Closed,
    Merged
};

enum class ReviewState {
    Commented,
    Approved,
    ChangesRequested,
    Dismissed
};

enum class MergeStrategy {
    Merge,
    Squash,
    Rebase
};

struct Reviewer {
    int id;
    std::string username;
    bool eligible;
};

struct Review {
    int reviewerId;
    ReviewState state;
    bool stale;
    std::vector<std::string> unresolvedComments;
};

struct StatusCheck {
    std::string name;
    bool passed;
};

struct PullRequest {
    int id;
    std::string sourceBranch;
    std::string targetBranch;
    PullRequestState state;
    MergeStrategy strategy;
    int commitCount;
    std::vector<Review> reviews;
    std::vector<StatusCheck> checks;
};

struct BranchProtection {
    int requiredReviews = 1;
    bool requireStatusChecks = true;
    bool requireConversationResolution = true;
    bool restrictDirectPush = true;
    bool restrictForcePush = true;
    bool restrictDeletion = true;
    bool requireLinearHistory = false;
};

struct Repository {
    std::string name;
    std::string defaultBranch;
    std::set<std::string> protectedBranches;
    BranchProtection protection;
};

struct MergeDecision {
    bool eligible;
    std::vector<std::string> reasons;
};

class GovernanceEngine {
public:
    GovernanceEngine(Repository repository,
                     std::map<int, Reviewer> reviewers)
        : repository_(std::move(repository)),
          reviewers_(std::move(reviewers)) {}

    MergeDecision evaluate(const PullRequest& pr) const {
        std::vector<std::string> reasons;

        if (pr.state != PullRequestState::Open) {
            reasons.push_back("Pull Request is not open");
        }

        if (pr.sourceBranch == pr.targetBranch) {
            reasons.push_back("source and target branches are identical");
        }

        const bool protectedTarget =
            repository_.protectedBranches.count(pr.targetBranch) > 0;

        if (!protectedTarget) {
            return {reasons.empty(), reasons};
        }

        const auto& policy = repository_.protection;

        if (policy.requireStatusChecks) {
            if (pr.checks.empty()) {
                reasons.push_back("required status checks have not run");
            } else {
                for (const auto& check : pr.checks) {
                    if (!check.passed) {
                        reasons.push_back("status check failed: " + check.name);
                    }
                }
            }
        }

        std::set<int> validApprovers;
        bool changesRequested = false;
        bool unresolvedConversation = false;

        for (const auto& review : pr.reviews) {
            if (review.stale || review.state == ReviewState::Dismissed) {
                continue;
            }

            if (!review.unresolvedComments.empty()) {
                unresolvedConversation = true;
            }

            if (review.state == ReviewState::ChangesRequested) {
                changesRequested = true;
            }

            if (review.state == ReviewState::Approved) {
                auto reviewer = reviewers_.find(review.reviewerId);

                if (reviewer != reviewers_.end() && reviewer->second.eligible) {
                    validApprovers.insert(review.reviewerId);
                }
            }
        }

        if (changesRequested) {
            reasons.push_back("an active reviewer requested changes");
        }

        if (static_cast<int>(validApprovers.size()) < policy.requiredReviews) {
            reasons.push_back(
                "insufficient eligible approvals: " +
                std::to_string(validApprovers.size()) + "/" +
                std::to_string(policy.requiredReviews)
            );
        }

        if (policy.requireConversationResolution && unresolvedConversation) {
            reasons.push_back("unresolved review conversations remain");
        }

        if (policy.requireLinearHistory &&
            pr.strategy == MergeStrategy::Merge) {
            reasons.push_back("merge strategy may violate linear-history policy");
        }

        if (pr.commitCount <= 0) {
            reasons.push_back("Pull Request contains no commits");
        }

        return {reasons.empty(), reasons};
    }

private:
    Repository repository_;
    std::map<int, Reviewer> reviewers_;
};

static std::string stateName(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft: return "draft";
        case PullRequestState::Open: return "open";
        case PullRequestState::Closed: return "closed";
        case PullRequestState::Merged: return "merged";
    }
    return "unknown";
}

static void printDecision(const MergeDecision& decision) {
    std::cout << "Merge eligible: "
              << (decision.eligible ? "yes" : "no") << '\n';

    for (const auto& reason : decision.reasons) {
        std::cout << "  - " << reason << '\n';
    }
}

int main() {
    Repository repository{
        "payments-service",
        "main",
        {"main"},
        BranchProtection{
            2,
            true,
            true,
            true,
            true,
            true,
            true
        }
    };

    std::map<int, Reviewer> reviewers{
        {101, {101, "alice", true}},
        {102, {102, "bob", true}},
        {103, {103, "contractor", false}}
    };

    GovernanceEngine engine(repository, reviewers);

    PullRequest pullRequest{
        501,
        "feature/idempotency",
        "main",
        PullRequestState::Open,
        MergeStrategy::Squash,
        4,
        {
            {
                101,
                ReviewState::Approved,
                false,
                {}
            },
            {
                102,
                ReviewState::Approved,
                false,
                {}
            },
            {
                103,
                ReviewState::Approved,
                false,
                {}
            }
        },
        {
            {"build", true},
            {"unit-tests", true},
            {"security-scan", true}
        }
    };

    std::cout << "Repository: " << repository.name << '\n';
    std::cout << "Pull Request state: "
              << stateName(pullRequest.state) << '\n';

    auto decision = engine.evaluate(pullRequest);
    printDecision(decision);

    std::cout << "\nFailure scenario:\n";

    pullRequest.reviews[1].stale = true;
    pullRequest.checks[1].passed = false;
    pullRequest.reviews[0].unresolvedComments.push_back(
        "Explain the retry boundary"
    );

    decision = engine.evaluate(pullRequest);
    printDecision(decision);

    // The engine counts unique eligible reviewers rather than approval records.
    // This prevents duplicate approvals from satisfying a required-review count.
    // Stale approvals remain stored for auditability but cannot authorize merging.
    return 0;
}
