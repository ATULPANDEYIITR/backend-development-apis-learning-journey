#include <algorithm>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

enum class ReviewState {
    Pending,
    Commented,
    Approved,
    ChangesRequested
};

enum class PullRequestState {
    Draft,
    Open,
    Closed,
    Merged
};


struct User {
    int id;
    std::string username;
    std::string email;
};


struct Commit {
    int id;
    std::string sha;
    std::string message;
};


struct Review {
    int id;
    int reviewerId;
    ReviewState state;
    std::string comment;
};


struct StatusCheck {
    std::string name;
    bool passed;
};


struct BranchProtectionPolicy {
    int requiredApprovals = 1;
    std::set<std::string> requiredChecks;
    bool restrictDirectPushes = true;
    bool allowForcePush = false;
    bool allowDeletion = false;
    bool requireLinearHistory = false;
};


class PullRequest {
private:
    int id_;
    int authorId_;
    std::string title_;
    std::string sourceBranch_;
    std::string targetBranch_;
    PullRequestState state_;

    std::vector<Commit> commits_;
    std::vector<Review> reviews_;
    std::vector<StatusCheck> statusChecks_;
    std::set<int> assignedReviewers_;

public:
    PullRequest(
        int id,
        int authorId,
        std::string title,
        std::string sourceBranch,
        std::string targetBranch
    )
        : id_(id),
          authorId_(authorId),
          title_(std::move(title)),
          sourceBranch_(std::move(sourceBranch)),
          targetBranch_(std::move(targetBranch)),
          state_(PullRequestState::Open) {

        if (sourceBranch_ == targetBranch_) {
            throw std::invalid_argument(
                "A Pull Request cannot target the same branch it originates from"
            );
        }
    }

    int id() const {
        return id_;
    }

    int authorId() const {
        return authorId_;
    }

    const std::string& targetBranch() const {
        return targetBranch_;
    }

    void assignReviewer(int userId) {
        if (userId == authorId_) {
            throw std::invalid_argument(
                "The Pull Request author cannot be assigned as an approving reviewer"
            );
        }

        assignedReviewers_.insert(userId);
    }

    void addCommit(const Commit& commit) {
        if (commit.sha.size() != 40) {
            throw std::invalid_argument(
                "A Git commit SHA must contain 40 hexadecimal characters"
            );
        }

        commits_.push_back(commit);
    }

    void addReview(const Review& review) {
        if (!assignedReviewers_.contains(review.reviewerId)) {
            throw std::invalid_argument(
                "Reviewer must be explicitly assigned before submitting a review"
            );
        }

        if (review.reviewerId == authorId_) {
            throw std::invalid_argument(
                "Self-approval is not permitted"
            );
        }

        reviews_.push_back(review);
    }

    void addStatusCheck(const StatusCheck& check) {
        statusChecks_.push_back(check);
    }

    int countValidApprovals() const {
        // A reviewer counts once even if the reviewer submits several approvals.
        std::set<int> approvingReviewers;

        for (const auto& review : reviews_) {
            if (review.state == ReviewState::Approved) {
                approvingReviewers.insert(review.reviewerId);
            }
        }

        return static_cast<int>(approvingReviewers.size());
    }

    bool hasRequestedChanges() const {
        return std::any_of(
            reviews_.begin(),
            reviews_.end(),
            [](const Review& review) {
                return review.state == ReviewState::ChangesRequested;
            }
        );
    }

    bool requiredChecksPassed(
        const std::set<std::string>& requiredChecks
    ) const {
        for (const auto& required : requiredChecks) {
            auto found = std::find_if(
                statusChecks_.begin(),
                statusChecks_.end(),
                [&](const StatusCheck& check) {
                    return check.name == required;
                }
            );

            if (found == statusChecks_.end() || !found->passed) {
                return false;
            }
        }

        return true;
    }

    bool hasCommits() const {
        return !commits_.empty();
    }
};


struct MergeDecision {
    bool eligible;
    std::vector<std::string> reasons;
};


class RepositoryGovernanceEngine {
private:
    BranchProtectionPolicy policy_;

public:
    explicit RepositoryGovernanceEngine(BranchProtectionPolicy policy)
        : policy_(std::move(policy)) {}

    MergeDecision evaluate(const PullRequest& pullRequest) const {
        MergeDecision decision{true, {}};

        if (!pullRequest.hasCommits()) {
            decision.eligible = false;
            decision.reasons.push_back(
                "Pull Request contains no commits"
            );
        }

        if (
            pullRequest.countValidApprovals() <
            policy_.requiredApprovals
        ) {
            decision.eligible = false;
            decision.reasons.push_back(
                "Required approval threshold has not been met"
            );
        }

        if (pullRequest.hasRequestedChanges()) {
            decision.eligible = false;
            decision.reasons.push_back(
                "A reviewer has requested changes"
            );
        }

        if (
            !pullRequest.requiredChecksPassed(
                policy_.requiredChecks
            )
        ) {
            decision.eligible = false;
            decision.reasons.push_back(
                "At least one required status check has failed or is missing"
            );
        }

        return decision;
    }
};


std::string decisionText(const MergeDecision& decision) {
    if (decision.eligible) {
        return "MERGE ELIGIBLE";
    }

    return "MERGE BLOCKED";
}


int main() {
    try {
        User alice{
            1,
            "alice",
            "alice@example.com"
        };

        User bob{
            2,
            "bob",
            "bob@example.com"
        };

        User carol{
            3,
            "carol",
            "carol@example.com"
        };

        PullRequest pullRequest(
            100,
            alice.id,
            "Add payment validation",
            "feature/payment-validation",
            "main"
        );

        pullRequest.assignReviewer(bob.id);
        pullRequest.assignReviewer(carol.id);

        pullRequest.addCommit({
            500,
            "0123456789abcdef0123456789abcdef01234567",
            "Implement payment validation"
        });

        pullRequest.addReview({
            900,
            bob.id,
            ReviewState::Approved,
            "Validation rules are correct."
        });

        pullRequest.addReview({
            901,
            carol.id,
            ReviewState::Approved,
            "Security checks are adequate."
        });

        pullRequest.addStatusCheck({
            "unit-tests",
            true
        });

        pullRequest.addStatusCheck({
            "security-scan",
            true
        });

        BranchProtectionPolicy policy;
        policy.requiredApprovals = 2;
        policy.requiredChecks = {
            "unit-tests",
            "security-scan"
        };
        policy.restrictDirectPushes = true;
        policy.allowForcePush = false;
        policy.allowDeletion = false;
        policy.requireLinearHistory = true;

        RepositoryGovernanceEngine engine(policy);

        MergeDecision decision = engine.evaluate(pullRequest);

        std::cout << decisionText(decision) << '\n';

        for (const auto& reason : decision.reasons) {
            std::cout << "Reason: " << reason << '\n';
        }

        // The same governance engine detects a newly failed required check.
        pullRequest.addStatusCheck({
            "security-scan",
            false
        });

        MergeDecision blocked = engine.evaluate(pullRequest);

        std::cout << "\nAfter security scan failure:\n";
        std::cout << decisionText(blocked) << '\n';

        for (const auto& reason : blocked.reasons) {
            std::cout << "Reason: " << reason << '\n';
        }

    } catch (const std::exception& error) {
        std::cerr << "Validation failure: "
                  << error.what()
                  << '\n';

        return 1;
    }

    return 0;
}
