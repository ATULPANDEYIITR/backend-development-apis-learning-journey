#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

enum class ReviewDecision {
    Pending,
    Approved,
    ChangesRequested,
    Rejected
};

enum class CheckState {
    Pending,
    Passed,
    Failed
};

enum class PullRequestState {
    Draft,
    Open,
    Closed,
    Merged
};

struct Commit {
    std::string id;
    std::string message;
};

struct Review {
    std::string reviewer;
    ReviewDecision decision;
    bool stale;
};

struct StatusCheck {
    std::string name;
    CheckState state;
};

struct BranchProtection {
    std::string branch;
    int requiredApprovals;
    bool requireStatusChecks;
    bool restrictDirectPush;
    bool restrictForcePush;
    bool requireConversationResolution;
    bool requireLinearHistory;
    std::set<std::string> eligibleReviewers;
    std::set<std::string> requiredChecks;
};

struct PullRequest {
    int number;
    std::string author;
    std::string sourceBranch;
    std::string targetBranch;
    PullRequestState state;
    bool draft;
    std::vector<Commit> commits;
    std::vector<Review> reviews;
    std::vector<StatusCheck> checks;
    int unresolvedConversations;
    bool hasConflicts;
};

struct EligibilityResult {
    bool eligible;
    std::vector<std::string> reasons;
};

class GovernanceEngine {
private:
    std::map<std::string, BranchProtection> protections;

    static bool containsReviewer(
        const std::set<std::string>& eligible,
        const std::string& reviewer
    ) {
        return eligible.find(reviewer) != eligible.end();
    }

public:
    void addProtection(const BranchProtection& policy) {
        if (policy.branch.empty()) {
            throw std::invalid_argument("Protected branch cannot be empty");
        }

        if (policy.requiredApprovals < 0) {
            throw std::invalid_argument(
                "Required approvals cannot be negative"
            );
        }

        protections[policy.branch] = policy;
    }

    EligibilityResult evaluate(const PullRequest& pr) const {
        EligibilityResult result{true, {}};

        if (pr.state != PullRequestState::Open) {
            result.eligible = false;
            result.reasons.push_back("Pull Request is not open");
        }

        if (pr.draft) {
            result.eligible = false;
            result.reasons.push_back("Draft Pull Request cannot merge");
        }

        if (pr.sourceBranch == pr.targetBranch) {
            result.eligible = false;
            result.reasons.push_back(
                "Source and target branches must differ"
            );
        }

        if (pr.commits.empty()) {
            result.eligible = false;
            result.reasons.push_back("Pull Request contains no commits");
        }

        if (pr.hasConflicts) {
            result.eligible = false;
            result.reasons.push_back("Merge conflicts must be resolved");
        }

        const auto policyIt = protections.find(pr.targetBranch);

        if (policyIt == protections.end()) {
            return result;
        }

        const BranchProtection& policy = policyIt->second;

        if (policy.requireConversationResolution &&
            pr.unresolvedConversations > 0) {
            result.eligible = false;
            result.reasons.push_back(
                "Unresolved review conversations remain"
            );
        }

        std::set<std::string> approvedReviewers;

        for (const Review& review : pr.reviews) {
            if (review.decision == ReviewDecision::Approved &&
                !review.stale &&
                containsReviewer(policy.eligibleReviewers, review.reviewer)) {
                approvedReviewers.insert(review.reviewer);
            }

            if (review.decision == ReviewDecision::ChangesRequested) {
                result.eligible = false;
                result.reasons.push_back(
                    "A reviewer has requested changes"
                );
            }
        }

        if (static_cast<int>(approvedReviewers.size()) <
            policy.requiredApprovals) {
            result.eligible = false;
            result.reasons.push_back(
                "Required number of current approvals is missing"
            );
        }

        if (policy.requireStatusChecks) {
            std::map<std::string, CheckState> checksByName;

            for (const StatusCheck& check : pr.checks) {
                checksByName[check.name] = check.state;
            }

            for (const std::string& required : policy.requiredChecks) {
                auto check = checksByName.find(required);

                if (check == checksByName.end()) {
                    result.eligible = false;
                    result.reasons.push_back(
                        "Required status check is missing: " + required
                    );
                } else if (check->second != CheckState::Passed) {
                    result.eligible = false;
                    result.reasons.push_back(
                        "Required status check has not passed: " + required
                    );
                }
            }
        }

        return result;
    }

    bool merge(
        PullRequest& pr,
        const std::string& actor
    ) const {
        const auto policyIt = protections.find(pr.targetBranch);

        if (policyIt != protections.end()) {
            const BranchProtection& policy = policyIt->second;

            if (policy.restrictDirectPush && actor.empty()) {
                return false;
            }
        }

        EligibilityResult result = evaluate(pr);

        if (!result.eligible) {
            return false;
        }

        pr.state = PullRequestState::Merged;
        return true;
    }
};

std::string decisionToString(ReviewDecision decision) {
    switch (decision) {
        case ReviewDecision::Pending:
            return "PENDING";
        case ReviewDecision::Approved:
            return "APPROVED";
        case ReviewDecision::ChangesRequested:
            return "CHANGES_REQUESTED";
        case ReviewDecision::Rejected:
            return "REJECTED";
    }

    return "UNKNOWN";
}

void printEligibility(const EligibilityResult& result) {
    std::cout << "Merge eligible: "
              << (result.eligible ? "YES" : "NO")
              << '\n';

    for (const auto& reason : result.reasons) {
        std::cout << " - " << reason << '\n';
    }
}

int main() {
    try {
        GovernanceEngine engine;

        BranchProtection mainPolicy{
            "main",
            2,
            true,
            true,
            true,
            true,
            true,
            {"reviewer-1", "reviewer-2", "security-team"},
            {"unit-tests", "security-scan"}
        };

        engine.addProtection(mainPolicy);

        PullRequest pr{
            101,
            "alice",
            "feature/jwt-authentication",
            "main",
            PullRequestState::Open,
            false,
            {
                {"a1b2c3", "Add access-token validation"},
                {"d4e5f6", "Protect orders endpoint"}
            },
            {
                {"reviewer-1", ReviewDecision::Approved, false},
                {"reviewer-2", ReviewDecision::Approved, false}
            },
            {
                {"unit-tests", CheckState::Passed},
                {"security-scan", CheckState::Passed}
            },
            0,
            false
        };

        std::cout << "Pull Request #" << pr.number << '\n';
        std::cout << "Source: " << pr.sourceBranch << '\n';
        std::cout << "Target: " << pr.targetBranch << '\n';

        EligibilityResult result = engine.evaluate(pr);
        printEligibility(result);

        bool merged = engine.merge(pr, "merge-bot");

        std::cout << "Merge operation: "
                  << (merged ? "SUCCESS" : "REJECTED")
                  << '\n';

        PullRequest failingPr = pr;
        failingPr.number = 102;
        failingPr.state = PullRequestState::Open;
        failingPr.hasConflicts = true;
        failingPr.draft = false;

        failingPr.reviews = {
            {"reviewer-1", ReviewDecision::Approved, false}
        };

        EligibilityResult failure =
            engine.evaluate(failingPr);

        std::cout << "\nPull Request #"
                  << failingPr.number
                  << " failure analysis\n";

        printEligibility(failure);

        if (failure.eligible) {
            throw std::runtime_error(
                "Conflicted Pull Request was incorrectly accepted"
            );
        }

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: "
                  << error.what()
                  << '\n';
        return 1;
    }
}
