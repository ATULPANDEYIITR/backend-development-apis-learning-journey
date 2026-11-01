#include <algorithm>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
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

enum class CheckState {
    Pending,
    Passed,
    Failed
};

enum class Severity {
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4
};

enum class SecurityCategory {
    BrokenAuthorization,
    ExcessiveDataExposure,
    Injection,
    SSRF,
    SecurityMisconfiguration
};

std::string toString(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft: return "draft";
        case PullRequestState::Open: return "open";
        case PullRequestState::Closed: return "closed";
        case PullRequestState::Merged: return "merged";
    }
    return "unknown";
}

std::string toString(ReviewState state) {
    switch (state) {
        case ReviewState::Commented: return "commented";
        case ReviewState::Approved: return "approved";
        case ReviewState::ChangesRequested: return "changes_requested";
        case ReviewState::Dismissed: return "dismissed";
    }
    return "unknown";
}

std::string toString(CheckState state) {
    switch (state) {
        case CheckState::Pending: return "pending";
        case CheckState::Passed: return "passed";
        case CheckState::Failed: return "failed";
    }
    return "unknown";
}

std::string toString(Severity severity) {
    switch (severity) {
        case Severity::Low: return "low";
        case Severity::Medium: return "medium";
        case Severity::High: return "high";
        case Severity::Critical: return "critical";
    }
    return "unknown";
}

std::string toString(SecurityCategory category) {
    switch (category) {
        case SecurityCategory::BrokenAuthorization:
            return "broken_authorization";
        case SecurityCategory::ExcessiveDataExposure:
            return "excessive_data_exposure";
        case SecurityCategory::Injection:
            return "injection";
        case SecurityCategory::SSRF:
            return "ssrf";
        case SecurityCategory::SecurityMisconfiguration:
            return "security_misconfiguration";
    }
    return "unknown";
}

struct User {
    std::string username;
    std::string team;
    bool administrator{false};
};

struct Commit {
    std::string sha;
    std::string author;
    std::string message;
    std::vector<std::string> files;
};

struct ReviewComment {
    std::string reviewer;
    std::string file;
    int line{};
    std::string body;
    bool resolved{false};
};

struct Review {
    std::string reviewer;
    ReviewState state;
    std::string reviewedCommit;
    std::vector<ReviewComment> comments;
};

struct StatusCheck {
    std::string name;
    CheckState state;
    std::string details;
};

struct SecurityFinding {
    SecurityCategory category;
    Severity severity;
    std::string endpoint;
    std::string description;

    bool blocking() const {
        return severity == Severity::High ||
               severity == Severity::Critical;
    }
};

struct Branch {
    std::string name;
    std::string head;
    bool protectedBranch{false};
};

struct BranchProtection {
    int requiredApprovals{2};
    std::set<std::string> requiredChecks{
        "unit-tests",
        "api-security-scan",
        "authorization-tests"
    };
    bool requireConversationResolution{true};
    bool requireCodeOwnerReview{true};
    bool requireLinearHistory{true};
    bool allowForcePush{false};
    bool allowBranchDeletion{false};
    bool administratorsCanBypass{false};
};

struct PullRequest {
    int number{};
    std::string title;
    std::string author;
    std::string sourceBranch;
    std::string targetBranch;
    std::string baseCommit;
    std::string headCommit;
    PullRequestState state{PullRequestState::Open};
    bool draft{false};
    std::vector<Commit> commits;
    std::vector<Review> reviews;
    std::vector<ReviewComment> comments;
    std::vector<StatusCheck> checks;
    std::vector<SecurityFinding> findings;
    std::string mergeCommit;
};

struct EligibilityResult {
    bool eligible{false};
    std::vector<std::string> reasons;
};

class RepositoryException : public std::runtime_error {
public:
    explicit RepositoryException(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationException : public RepositoryException {
public:
    explicit ValidationException(const std::string& message)
        : RepositoryException(message) {}
};

class MergeBlockedException : public RepositoryException {
public:
    explicit MergeBlockedException(const std::vector<std::string>& reasons)
        : RepositoryException(format(reasons)) {}

private:
    static std::string format(const std::vector<std::string>& reasons) {
        std::ostringstream output;
        output << "Merge blocked:";
        for (const auto& reason : reasons) {
            output << "\n- " << reason;
        }
        return output.str();
    }
};

class SecurityPolicy {
public:
    std::vector<std::string> evaluate(
        const std::vector<SecurityFinding>& findings) const {

        std::vector<std::string> failures;

        for (const auto& finding : findings) {
            if (finding.blocking()) {
                failures.push_back(
                    toString(finding.category) + " " +
                    toString(finding.severity) +
                    " finding at " + finding.endpoint
                );
            }
        }

        return failures;
    }
};

class MergeEligibilityEngine {
public:
    MergeEligibilityEngine(
        BranchProtection protection,
        std::map<std::string, std::set<std::string>> codeOwners)
        : protection_(std::move(protection)),
          codeOwners_(std::move(codeOwners)) {}

    EligibilityResult evaluate(
        const PullRequest& pr,
        const Branch& target) const {

        EligibilityResult result;
        result.eligible = true;

        if (pr.state != PullRequestState::Open) {
            result.reasons.push_back(
                "Pull Request is " + toString(pr.state) + "."
            );
        }

        if (pr.draft) {
            result.reasons.push_back(
                "Draft Pull Requests cannot be merged."
            );
        }

        if (target.protectedBranch) {
            if (pr.baseCommit != target.head) {
                result.reasons.push_back(
                    "Pull Request base is stale."
                );
            }

            std::set<std::string> passedChecks;
            for (const auto& check : pr.checks) {
                if (check.state == CheckState::Passed) {
                    passedChecks.insert(check.name);
                }
            }

            for (const auto& required : protection_.requiredChecks) {
                if (!passedChecks.count(required)) {
                    result.reasons.push_back(
                        "Required check is not passing: " + required
                    );
                }
            }

            if (protection_.requireConversationResolution) {
                const auto unresolved = std::count_if(
                    pr.comments.begin(),
                    pr.comments.end(),
                    [](const ReviewComment& comment) {
                        return !comment.resolved;
                    }
                );

                if (unresolved > 0) {
                    result.reasons.push_back(
                        std::to_string(unresolved) +
                        " review conversation(s) remain unresolved."
                    );
                }
            }

            const auto securityFailures =
                securityPolicy_.evaluate(pr.findings);

            result.reasons.insert(
                result.reasons.end(),
                securityFailures.begin(),
                securityFailures.end()
            );

            const auto approvals = currentApprovals(pr);

            if (static_cast<int>(approvals.size()) <
                protection_.requiredApprovals) {
                result.reasons.push_back(
                    std::to_string(approvals.size()) +
                    " eligible approval(s); " +
                    std::to_string(protection_.requiredApprovals) +
                    " required."
                );
            }

            if (protection_.requireCodeOwnerReview &&
                !hasCodeOwnerApproval(pr, approvals)) {
                result.reasons.push_back(
                    "API code-owner approval is missing."
                );
            }
        }

        result.eligible = result.reasons.empty();
        return result;
    }

private:
    std::set<std::string> currentApprovals(
        const PullRequest& pr) const {

        std::map<std::string, Review> latest;

        for (const auto& review : pr.reviews) {
            if (review.reviewer == pr.author) {
                continue;
            }

            if (review.state == ReviewState::Dismissed) {
                latest.erase(review.reviewer);
                continue;
            }

            latest[review.reviewer] = review;
        }

        std::set<std::string> approvals;

        for (const auto& [reviewer, review] : latest) {
            if (review.state == ReviewState::Approved &&
                review.reviewedCommit == pr.headCommit) {
                approvals.insert(reviewer);
            }
        }

        return approvals;
    }

    bool hasCodeOwnerApproval(
        const PullRequest& pr,
        const std::set<std::string>& approvals) const {

        std::set<std::string> owners;

        for (const auto& commit : pr.commits) {
            for (const auto& file : commit.files) {
                for (const auto& [prefix, ownerSet] : codeOwners_) {
                    if (file.rfind(prefix, 0) == 0) {
                        owners.insert(
                            ownerSet.begin(),
                            ownerSet.end()
                        );
                    }
                }
            }
        }

        for (const auto& owner : owners) {
            if (approvals.count(owner)) {
                return true;
            }
        }

        return owners.empty();
    }

    BranchProtection protection_;
    std::map<std::string, std::set<std::string>> codeOwners_;
    SecurityPolicy securityPolicy_;
};

class Repository {
public:
    explicit Repository(std::string name)
        : name_(std::move(name)) {}

    void addBranch(
        const std::string& name,
        const std::string& head,
        bool protectedBranch) {

        if (branches_.count(name)) {
            throw ValidationException(
                "Branch already exists: " + name
            );
        }

        branches_.emplace(
            name,
            Branch{name, head, protectedBranch}
        );
    }

    PullRequest& createPullRequest(
        const std::string& author,
        const std::string& title,
        const std::string& source,
        const std::string& target,
        bool draft = false) {

        if (!branches_.count(source) ||
            !branches_.count(target)) {
            throw ValidationException(
                "Both source and target branches must exist."
            );
        }

        if (source == target) {
            throw ValidationException(
                "Source and target branches must differ."
            );
        }

        auto& targetBranch = branches_.at(target);
        auto& sourceBranch = branches_.at(source);

        PullRequest pr;
        pr.number = nextPrNumber_++;
        pr.title = title;
        pr.author = author;
        pr.sourceBranch = source;
        pr.targetBranch = target;
        pr.baseCommit = targetBranch.head;
        pr.headCommit = sourceBranch.head;
        pr.state = draft
            ? PullRequestState::Draft
            : PullRequestState::Open;
        pr.draft = draft;

        auto [iterator, inserted] =
            pullRequests_.emplace(pr.number, std::move(pr));

        if (!inserted) {
            throw RepositoryException(
                "Could not create Pull Request."
            );
        }

        return iterator->second;
    }

    Commit addCommit(
        PullRequest& pr,
        const std::string& author,
        const std::string& message,
        const std::vector<std::string>& files) {

        if (pr.state != PullRequestState::Open &&
            pr.state != PullRequestState::Draft) {
            throw ValidationException(
                "Commits cannot be added to this Pull Request."
            );
        }

        if (files.empty()) {
            throw ValidationException(
                "A commit must contain at least one file."
            );
        }

        std::string sha =
            std::to_string(pr.number) +
            author +
            message +
            pr.headCommit;

        Commit commit{
            simpleHash(sha),
            author,
            message,
            files
        };

        pr.commits.push_back(commit);
        pr.headCommit = commit.sha;

        for (auto& review : pr.reviews) {
            if (review.state == ReviewState::Approved) {
                review.state = ReviewState::Dismissed;
            }
        }

        return commit;
    }

    void addCheck(
        PullRequest& pr,
        const std::string& name,
        CheckState state,
        const std::string& details) {

        auto iterator = std::find_if(
            pr.checks.begin(),
            pr.checks.end(),
            [&](const StatusCheck& check) {
                return check.name == name;
            }
        );

        StatusCheck check{name, state, details};

        if (iterator == pr.checks.end()) {
            pr.checks.push_back(std::move(check));
        } else {
            *iterator = std::move(check);
        }
    }

    void addReview(
        PullRequest& pr,
        const std::string& reviewer,
        ReviewState state,
        const std::string& body = "",
        const std::string& file = "",
        int line = 0) {

        if (pr.state != PullRequestState::Open) {
            throw ValidationException(
                "Reviews require an open Pull Request."
            );
        }

        if (reviewer == pr.author) {
            throw ValidationException(
                "Self-approval is not permitted."
            );
        }

        Review review{
            reviewer,
            state,
            pr.headCommit,
            {}
        };

        if (!body.empty()) {
            if (file.empty() || line < 1) {
                throw ValidationException(
                    "A review comment requires a file and positive line."
                );
            }

            ReviewComment comment{
                reviewer,
                file,
                line,
                body,
                false
            };

            review.comments.push_back(comment);
            pr.comments.push_back(comment);
        }

        pr.reviews.push_back(std::move(review));
    }

    void resolveComment(
        PullRequest& pr,
        const std::string& reviewer,
        const std::string& file,
        int line) {

        auto iterator = std::find_if(
            pr.comments.begin(),
            pr.comments.end(),
            [&](ReviewComment& comment) {
                return comment.reviewer == reviewer &&
                       comment.file == file &&
                       comment.line == line;
            }
        );

        if (iterator == pr.comments.end()) {
            throw ValidationException(
                "Review conversation not found."
            );
        }

        iterator->resolved = true;
    }

    void addFinding(
        PullRequest& pr,
        SecurityCategory category,
        Severity severity,
        const std::string& endpoint,
        const std::string& description) {

        pr.findings.push_back({
            category,
            severity,
            endpoint,
            description
        });
    }

    std::string merge(PullRequest& pr) {
        auto targetIterator =
            branches_.find(pr.targetBranch);

        if (targetIterator == branches_.end()) {
            throw ValidationException(
                "Target branch does not exist."
            );
        }

        MergeEligibilityEngine engine(
            protection_,
            codeOwners_
        );

        const auto result =
            engine.evaluate(pr, targetIterator->second);

        if (!result.eligible) {
            throw MergeBlockedException(result.reasons);
        }

        const std::string mergeSha = simpleHash(
            name_ +
            std::to_string(pr.number) +
            pr.headCommit +
            targetIterator->second.head
        );

        targetIterator->second.head = mergeSha;
        pr.mergeCommit = mergeSha;
        pr.state = PullRequestState::Merged;

        return mergeSha;
    }

    const BranchProtection& protection() const {
        return protection_;
    }

private:
    static std::string simpleHash(const std::string& input) {
        std::size_t value = std::hash<std::string>{}(input);
        std::ostringstream output;
        output << std::hex << value;
        return output.str().substr(0, 12);
    }

    std::string name_;
    int nextPrNumber_{1};
    std::map<std::string, Branch> branches_;
    std::map<int, PullRequest> pullRequests_;

    BranchProtection protection_;

    std::map<std::string, std::set<std::string>> codeOwners_{
        {"api/", {"security-lead"}},
        {"auth/", {"security-lead"}}
    };
};

void demonstrateSuccessfulMerge() {
    Repository repository("payments-api");

    repository.addBranch(
        "main",
        "main-001",
        true
    );

    repository.addBranch(
        "feature/authz",
        "feature-001",
        false
    );

    auto& pr = repository.createPullRequest(
        "developer",
        "Enforce object authorization",
        "feature/authz",
        "main"
    );

    repository.addCommit(
        pr,
        "developer",
        "Add tenant ownership validation",
        {
            "api/orders.cpp",
            "auth/policy.cpp",
            "tests/authorization.cpp"
        }
    );

    repository.addFinding(
        pr,
        SecurityCategory::BrokenAuthorization,
        Severity::Low,
        "GET /api/orders/{id}",
        "Ownership is verified before object serialization."
    );

    for (const auto& check : repository.protection().requiredChecks) {
        repository.addCheck(
            pr,
            check,
            CheckState::Passed,
            "Passed."
        );
    }

    repository.addReview(
        pr,
        "backend-reviewer",
        ReviewState::Approved,
        "Authorization path reviewed."
    );

    repository.addReview(
        pr,
        "security-lead",
        ReviewState::Approved,
        "API security controls reviewed."
    );

    const std::string mergeSha =
        repository.merge(pr);

    std::cout
        << "Successful merge\n"
        << "PR: #" << pr.number << "\n"
        << "State: " << toString(pr.state) << "\n"
        << "Merge commit: " << mergeSha << "\n\n";
}

void demonstrateConversationBlock() {
    Repository repository("identity-api");

    repository.addBranch(
        "main",
        "main-100",
        true
    );

    repository.addBranch(
        "feature/ssrf",
        "feature-100",
        false
    );

    auto& pr = repository.createPullRequest(
        "developer",
        "Restrict outbound API requests",
        "feature/ssrf",
        "main"
    );

    repository.addCommit(
        pr,
        "developer",
        "Validate outbound destinations",
        {"api/http_client.cpp"}
    );

    for (const auto& check : repository.protection().requiredChecks) {
        repository.addCheck(
            pr,
            check,
            CheckState::Passed,
            "Passed."
        );
    }

    repository.addReview(
        pr,
        "security-lead",
        ReviewState::Approved,
        "Check DNS rebinding handling.",
        "api/http_client.cpp",
        72
    );

    repository.addReview(
        pr,
        "backend-reviewer",
        ReviewState::Approved
    );

    try {
        repository.merge(pr);
    } catch (const MergeBlockedException& error) {
        std::cout
            << "Expected conversation block:\n"
            << error.what()
            << "\n\n";
    }

    repository.resolveComment(
        pr,
        "security-lead",
        "api/http_client.cpp",
        72
    );

    std::cout
        << "After resolving the conversation: "
        << repository.merge(pr)
        << "\n\n";
}

void demonstrateSecurityBlock() {
    Repository repository("public-api");

    repository.addBranch(
        "main",
        "main-200",
        true
    );

    repository.addBranch(
        "feature/webhook",
        "feature-200",
        false
    );

    auto& pr = repository.createPullRequest(
        "developer",
        "Add webhook testing endpoint",
        "feature/webhook",
        "main"
    );

    repository.addCommit(
        pr,
        "developer",
        "Add URL fetch endpoint",
        {"api/webhook.cpp"}
    );

    repository.addFinding(
        pr,
        SecurityCategory::SSRF,
        Severity::High,
        "POST /api/webhooks/test",
        "User-controlled destination can reach private network ranges."
    );

    for (const auto& check : repository.protection().requiredChecks) {
        repository.addCheck(
            pr,
            check,
            CheckState::Passed,
            "Review checks completed."
        );
    }

    repository.addReview(
        pr,
        "security-lead",
        ReviewState::Approved
    );

    repository.addReview(
        pr,
        "backend-reviewer",
        ReviewState::Approved
    );

    try {
        repository.merge(pr);
    } catch (const MergeBlockedException& error) {
        std::cout
            << "Expected security block:\n"
            << error.what()
            << "\n\n";
    }
}

int main() {
    try {
        demonstrateSuccessfulMerge();
        demonstrateConversationBlock();
        demonstrateSecurityBlock();

        std::cout
            << "Governance engine completed successfully.\n";
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';
        return 1;
    }

    return 0;
}
