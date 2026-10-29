#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

enum class Effect {
    Allow,
    Deny
};

enum class Decision {
    Allow,
    Deny
};

enum class ReviewMode {
    None,
    TrustedDevice,
    MfaRequired
};

struct User {
    std::string id;
    std::string department;
    std::unordered_set<std::string> roles;
    int clearance{};
    bool active{true};
};

struct Resource {
    std::string id;
    std::string type;
    std::string ownerDepartment;
    int classification{};
};

struct AccessRequest {
    const User* user{};
    const Resource* resource{};
    std::string action;
    std::string ipAddress;
    bool trustedDevice{};
    bool mfaVerified{};
    std::string environment;
    std::string emergencyTicket;
};

struct StatusCheck {
    std::string name;
    bool required{};
    bool passed{};
};

struct BranchProtection {
    std::string branchName;
    int requiredApprovals{};
    std::unordered_set<std::string> requiredChecks;
    bool restrictDirectPush{true};
    bool restrictForcePush{true};
    bool requireConversationResolution{true};
    bool requireLinearHistory{false};
};

struct PullRequest {
    int id{};
    std::string sourceBranch;
    std::string targetBranch;
    std::string authorId;
    std::vector<std::string> commits;
    bool draft{false};
    bool open{true};
    bool mergeable{true};
    bool conversationsResolved{true};
    std::vector<StatusCheck> checks;
};

enum class ReviewState {
    Commented,
    Approved,
    ChangesRequested,
    Dismissed
};

struct Review {
    std::string reviewerId;
    ReviewState state{ReviewState::Commented};
    bool stale{false};
    bool eligible{false};
    std::vector<std::string> comments;
};

class GovernanceError : public std::runtime_error {
public:
    explicit GovernanceError(const std::string& message)
        : std::runtime_error(message) {}
};

class MergeEligibilityEngine {
private:
    std::unordered_map<std::string, User> users;
    std::unordered_map<std::string, BranchProtection> protections;

    static bool hasRole(
        const User& user,
        const std::string& role
    ) {
        return user.roles.find(role) != user.roles.end();
    }

    static std::size_t countValidApprovals(
        const PullRequest& pr,
        const std::vector<Review>& reviews
    ) {
        std::unordered_set<std::string> uniqueApprovers;

        for (const auto& review : reviews) {
            if (
                review.state == ReviewState::Approved &&
                !review.stale &&
                review.eligible
            ) {
                uniqueApprovers.insert(review.reviewerId);
            }
        }

        return uniqueApprovers.size();
    }

    static bool requiredChecksPass(
        const PullRequest& pr,
        const BranchProtection& policy
    ) {
        for (const auto& required : policy.requiredChecks) {
            auto found = std::find_if(
                pr.checks.begin(),
                pr.checks.end(),
                [&](const StatusCheck& check) {
                    return check.name == required;
                }
            );

            if (found == pr.checks.end() || !found->passed) {
                return false;
            }
        }

        return true;
    }

public:
    void addUser(User user) {
        if (user.id.empty()) {
            throw GovernanceError("User identifier cannot be empty");
        }
        users[user.id] = std::move(user);
    }

    void protectBranch(BranchProtection policy) {
        if (policy.branchName.empty()) {
            throw GovernanceError("Protected branch must have a name");
        }
        if (policy.requiredApprovals < 0) {
            throw GovernanceError("Approval count cannot be negative");
        }
        protections[policy.branchName] = std::move(policy);
    }

    bool isReviewerEligible(
        const std::string& reviewerId,
        const PullRequest& pr
    ) const {
        const auto userIt = users.find(reviewerId);

        if (userIt == users.end()) {
            return false;
        }

        const User& reviewer = userIt->second;

        if (!reviewer.active) {
            return false;
        }

        // Authors are excluded from approval counting in this model.
        return reviewer.id != pr.authorId;
    }

    bool isMergeEligible(
        const PullRequest& pr,
        const std::vector<Review>& reviews
    ) const {
        if (!pr.open) {
            return false;
        }

        if (pr.draft) {
            return false;
        }

        if (!pr.mergeable) {
            return false;
        }

        if (pr.sourceBranch == pr.targetBranch) {
            return false;
        }

        auto protectionIt = protections.find(pr.targetBranch);
        if (protectionIt == protections.end()) {
            // Unprotected branches do not inherit protected-branch rules.
            return true;
        }

        const BranchProtection& policy = protectionIt->second;

        if (policy.requireConversationResolution &&
            !pr.conversationsResolved) {
            return false;
        }

        if (!requiredChecksPass(pr, policy)) {
            return false;
        }

        const auto approvals = countValidApprovals(pr, reviews);

        return approvals >= static_cast<std::size_t>(
            policy.requiredApprovals
        );
    }

    std::vector<std::string> explain(
        const PullRequest& pr,
        const std::vector<Review>& reviews
    ) const {
        std::vector<std::string> reasons;

        if (!pr.open) {
            reasons.emplace_back("Pull Request is closed");
        }

        if (pr.draft) {
            reasons.emplace_back("Pull Request is still a draft");
        }

        if (!pr.mergeable) {
            reasons.emplace_back("Branch state contains a merge conflict");
        }

        if (!pr.conversationsResolved) {
            reasons.emplace_back("Unresolved review conversations remain");
        }

        auto protectionIt = protections.find(pr.targetBranch);

        if (protectionIt != protections.end()) {
            const auto& policy = protectionIt->second;

            for (const auto& required : policy.requiredChecks) {
                auto found = std::find_if(
                    pr.checks.begin(),
                    pr.checks.end(),
                    [&](const StatusCheck& check) {
                        return check.name == required;
                    }
                );

                if (
                    found == pr.checks.end() ||
                    !found->passed
                ) {
                    reasons.push_back(
                        "Required status check failed or is missing: " +
                        required
                    );
                }
            }

            const auto approvals = countValidApprovals(
                pr,
                reviews
            );

            if (
                approvals <
                static_cast<std::size_t>(policy.requiredApprovals)
            ) {
                reasons.push_back(
                    "Required approvals not satisfied"
                );
            }
        }

        if (reasons.empty()) {
            reasons.emplace_back("All merge conditions satisfied");
        }

        return reasons;
    }
};

std::string decisionText(bool allowed) {
    return allowed ? "ALLOW" : "DENY";
}

void printEligibility(
    const MergeEligibilityEngine& engine,
    const PullRequest& pr,
    const std::vector<Review>& reviews
) {
    const bool eligible = engine.isMergeEligible(pr, reviews);

    std::cout
        << "PR #" << pr.id
        << " -> " << pr.targetBranch
        << ": " << decisionText(eligible)
        << '\n';

    for (const auto& reason : engine.explain(pr, reviews)) {
        std::cout << "  - " << reason << '\n';
    }
}

int main() {
    try {
        MergeEligibilityEngine engine;

        engine.addUser({
            "alice",
            "engineering",
            {"developer"},
            2,
            true
        });

        engine.addUser({
            "bob",
            "engineering",
            {"senior-reviewer"},
            3,
            true
        });

        engine.addUser({
            "carol",
            "security",
            {"security-reviewer"},
            4,
            true
        });

        engine.addUser({
            "dave",
            "engineering",
            {"developer"},
            2,
            false
        });

        engine.protectBranch({
            "main",
            2,
            {"ci/build", "security/scan"},
            true,
            true,
            true,
            true
        });

        PullRequest cleanPr{
            101,
            "feature/authorization",
            "main",
            "alice",
            {"a1b2c3", "d4e5f6"},
            false,
            true,
            true,
            true,
            {
                {"ci/build", true, true},
                {"security/scan", true, true}
            }
        };

        std::vector<Review> cleanReviews{
            {
                "bob",
                ReviewState::Approved,
                false,
                engine.isReviewerEligible("bob", cleanPr),
                {"Policy evaluation is bounded and auditable"}
            },
            {
                "carol",
                ReviewState::Approved,
                false,
                engine.isReviewerEligible("carol", cleanPr),
                {"Security conditions are satisfied"}
            }
        };

        printEligibility(engine, cleanPr, cleanReviews);

        PullRequest staleApprovalPr = cleanPr;
        staleApprovalPr.id = 102;

        std::vector<Review> staleReviews{
            {
                "bob",
                ReviewState::Approved,
                true,
                engine.isReviewerEligible("bob", staleApprovalPr),
                {"Approval predates the latest relevant change"}
            },
            {
                "carol",
                ReviewState::Approved,
                false,
                engine.isReviewerEligible("carol", staleApprovalPr),
                {"Security review remains current"}
            }
        };

        printEligibility(
            engine,
            staleApprovalPr,
            staleReviews
        );

        PullRequest failedChecksPr = cleanPr;
        failedChecksPr.id = 103;
        failedChecksPr.checks[1].passed = false;

        printEligibility(
            engine,
            failedChecksPr,
            cleanReviews
        );

        PullRequest conflictPr = cleanPr;
        conflictPr.id = 104;
        conflictPr.mergeable = false;

        printEligibility(
            engine,
            conflictPr,
            cleanReviews
        );

        PullRequest draftPr = cleanPr;
        draftPr.id = 105;
        draftPr.draft = true;

        printEligibility(
            engine,
            draftPr,
            cleanReviews
        );

        // Demonstrate that an inactive reviewer cannot create an approval.
        Review inactiveReviewer{
            "dave",
            ReviewState::Approved,
            false,
            engine.isReviewerEligible("dave", cleanPr),
            {"Inactive reviewer must not satisfy approval policy"}
        };

        std::cout
            << "\nInactive reviewer eligibility: "
            << std::boolalpha
            << inactiveReviewer.eligible
            << '\n';

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Governance engine failure: "
            << error.what()
            << '\n';
        return 1;
    }
}
