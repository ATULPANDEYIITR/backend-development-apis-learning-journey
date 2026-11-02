#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

enum class ReviewState {
    Pending,
    Approved,
    ChangesRequested,
    Dismissed
};

enum class CheckState {
    Pending,
    Passed,
    Failed
};

enum class MergeStrategy {
    MergeCommit,
    Squash,
    Rebase
};

struct Review {
    std::string reviewer;
    ReviewState state;
    bool eligible;
};

struct StatusCheck {
    std::string name;
    CheckState state;
    bool required;
};

struct BranchProtection {
    bool protected_branch = true;
    bool require_pull_request = true;
    bool require_approvals = true;
    int required_approvals = 2;
    bool require_all_conversations_resolved = true;
    bool require_status_checks = true;
    bool restrict_direct_push = true;
    bool restrict_force_push = true;
    bool restrict_deletion = true;
    bool require_linear_history = false;
};

struct PullRequest {
    int id{};
    std::string source_branch;
    std::string target_branch;
    std::vector<std::string> commits;
    std::vector<Review> reviews;
    std::vector<StatusCheck> checks;
    int unresolved_conversations{};
    bool draft{};
    bool open{true};
    bool has_conflicts{};
    bool source_synchronized{true};
};

struct EligibilityResult {
    bool eligible{};
    std::vector<std::string> reasons;
};

class GovernanceError : public std::runtime_error {
public:
    explicit GovernanceError(const std::string& message)
        : std::runtime_error(message) {}
};

class Repository {
private:
    std::string name_;
    std::map<std::string, BranchProtection> protections_;
    std::set<std::string> maintainers_;

public:
    explicit Repository(std::string name)
        : name_(std::move(name)) {}

    void protectBranch(const std::string& branch, BranchProtection policy) {
        if (branch.empty()) {
            throw GovernanceError("branch name cannot be empty");
        }
        protections_[branch] = policy;
    }

    void addMaintainer(const std::string& user) {
        if (user.empty()) {
            throw GovernanceError("maintainer name cannot be empty");
        }
        maintainers_.insert(user);
    }

    bool isMaintainer(const std::string& user) const {
        return maintainers_.contains(user);
    }

    const BranchProtection* protectionFor(
        const std::string& branch) const {

        auto it = protections_.find(branch);

        if (it == protections_.end()) {
            return nullptr;
        }

        return &it->second;
    }
};

class MergeEligibilityEngine {
private:
    static int countValidApprovals(const PullRequest& pr) {
        std::set<std::string> uniqueApprovers;

        for (const auto& review : pr.reviews) {
            if (review.eligible &&
                review.state == ReviewState::Approved) {
                uniqueApprovers.insert(review.reviewer);
            }
        }

        return static_cast<int>(uniqueApprovers.size());
    }

public:
    EligibilityResult evaluate(
        const PullRequest& pr,
        const Repository& repository) const {

        EligibilityResult result;

        if (!pr.open) {
            result.reasons.push_back("pull request is closed");
        }

        if (pr.draft) {
            result.reasons.push_back("pull request is still a draft");
        }

        if (pr.commits.empty()) {
            result.reasons.push_back("pull request contains no commits");
        }

        if (pr.source_branch.empty() || pr.target_branch.empty()) {
            result.reasons.push_back("source and target branches are required");
        }

        const BranchProtection* policy =
            repository.protectionFor(pr.target_branch);

        if (policy == nullptr) {
            result.reasons.push_back(
                "target branch has no explicit protection policy");
            result.eligible = result.reasons.empty();
            return result;
        }

        if (policy->require_pull_request && pr.id <= 0) {
            result.reasons.push_back("valid pull request identifier required");
        }

        if (pr.has_conflicts) {
            result.reasons.push_back("merge conflicts must be resolved");
        }

        if (!pr.source_synchronized) {
            result.reasons.push_back(
                "source branch is behind the protected target branch");
        }

        if (policy->require_all_conversations_resolved &&
            pr.unresolved_conversations > 0) {
            result.reasons.push_back(
                "unresolved review conversations remain");
        }

        if (policy->require_approvals) {
            const int approvals = countValidApprovals(pr);

            if (approvals < policy->required_approvals) {
                result.reasons.push_back(
                    "required eligible approvals are missing");
            }
        }

        if (policy->require_status_checks) {
            for (const auto& check : pr.checks) {
                if (check.required &&
                    check.state != CheckState::Passed) {
                    result.reasons.push_back(
                        "required status check failed or is pending: " +
                        check.name);
                }
            }
        }

        if (result.reasons.empty()) {
            result.eligible = true;
        }

        return result;
    }
};

static std::string stateName(ReviewState state) {
    switch (state) {
        case ReviewState::Pending:
            return "PENDING";
        case ReviewState::Approved:
            return "APPROVED";
        case ReviewState::ChangesRequested:
            return "CHANGES_REQUESTED";
        case ReviewState::Dismissed:
            return "DISMISSED";
    }
    return "UNKNOWN";
}

static void printEligibility(
    const PullRequest& pr,
    const EligibilityResult& result) {

    std::cout << "\nPull Request #" << pr.id << '\n';
    std::cout << "Eligible: "
              << std::boolalpha
              << result.eligible << '\n';

    if (!result.eligible) {
        for (const auto& reason : result.reasons) {
            std::cout << "  - " << reason << '\n';
        }
    }
}

static PullRequest buildPullRequest() {
    PullRequest pr;

    pr.id = 184;
    pr.source_branch = "feature/prepared-statements";
    pr.target_branch = "main";

    pr.commits = {
        "a18f2c1",
        "b91d7aa",
        "c72e031"
    };

    pr.reviews = {
        {"security-reviewer", ReviewState::Approved, true},
        {"database-reviewer", ReviewState::Approved, true},
        {"external-contributor", ReviewState::Approved, false},
        {"application-owner", ReviewState::ChangesRequested, true}
    };

    pr.checks = {
        {"unit-tests", CheckState::Passed, true},
        {"static-analysis", CheckState::Passed, true},
        {"sql-injection-regression", CheckState::Passed, true},
        {"documentation", CheckState::Pending, false}
    };

    pr.unresolved_conversations = 0;
    pr.draft = false;
    pr.open = true;
    pr.has_conflicts = false;
    pr.source_synchronized = true;

    return pr;
}

static void demonstratePolicyChange(
    PullRequest pr,
    const Repository& repository,
    const MergeEligibilityEngine& engine) {

    pr.unresolved_conversations = 1;

    auto result = engine.evaluate(pr, repository);
    printEligibility(pr, result);

    pr.unresolved_conversations = 0;
    pr.source_synchronized = false;

    result = engine.evaluate(pr, repository);
    printEligibility(pr, result);
}

int main() {
    try {
        Repository repository("secure-data-service");

        repository.addMaintainer("release-manager");
        repository.addMaintainer("security-lead");

        BranchProtection mainPolicy;

        mainPolicy.protected_branch = true;
        mainPolicy.require_pull_request = true;
        mainPolicy.require_approvals = true;
        mainPolicy.required_approvals = 2;
        mainPolicy.require_all_conversations_resolved = true;
        mainPolicy.require_status_checks = true;
        mainPolicy.restrict_direct_push = true;
        mainPolicy.restrict_force_push = true;
        mainPolicy.restrict_deletion = true;
        mainPolicy.require_linear_history = false;

        repository.protectBranch("main", mainPolicy);

        PullRequest pr = buildPullRequest();

        MergeEligibilityEngine engine;

        std::cout << "Repository governance: secure-data-service\n";
        std::cout << "Target branch: main\n";

        auto result = engine.evaluate(pr, repository);
        printEligibility(pr, result);

        std::cout << "\nReview states:\n";
        for (const auto& review : pr.reviews) {
            std::cout << "  "
                      << review.reviewer
                      << ": "
                      << stateName(review.state)
                      << ", eligible="
                      << std::boolalpha
                      << review.eligible
                      << '\n';
        }

        demonstratePolicyChange(pr, repository, engine);

        std::cout << "\nSecurity model:\n";
        std::cout << "  SQL construction is outside the trust boundary.\n";
        std::cout << "  Application data must reach database APIs as bound values.\n";
        std::cout << "  Branch governance prevents an unreviewed security change\n";
        std::cout << "  from reaching the protected branch.\n";

        std::cout << "\nComplexity:\n";
        std::cout << "  Review evaluation: O(R log R) because approvers are deduplicated\n";
        std::cout << "  with an ordered set; status checks: O(C).\n";
        std::cout << "  The engine uses immutable policy decisions during evaluation.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}
