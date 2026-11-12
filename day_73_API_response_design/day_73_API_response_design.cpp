#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class ErrorCode {
    ValidationError,
    NotFound,
    Conflict,
    Forbidden,
    InternalError
};

string toString(ErrorCode code) {
    switch (code) {
        case ErrorCode::ValidationError: return "VALIDATION_ERROR";
        case ErrorCode::NotFound: return "RESOURCE_NOT_FOUND";
        case ErrorCode::Conflict: return "CONFLICT";
        case ErrorCode::Forbidden: return "FORBIDDEN";
        case ErrorCode::InternalError: return "INTERNAL_ERROR";
    }
    return "INTERNAL_ERROR";
}

struct APIError {
    ErrorCode code;
    string message;
    vector<string> details;
    bool retryable = false;
};

struct Metadata {
    string requestId;
    string timestamp;
    string apiVersion = "v1";
    double durationMs = 0;
    optional<string> correlationId;
};

template <typename T>
struct Response {
    bool success;
    optional<T> data;
    optional<APIError> error;
    Metadata metadata;

    Response(
        bool successful,
        optional<T> result,
        optional<APIError> failure,
        Metadata meta
    ) : success(successful),
        data(move(result)),
        error(move(failure)),
        metadata(move(meta)) {

        if (success && error.has_value()) {
            throw invalid_argument(
                "Successful response cannot contain an error"
            );
        }

        if (!success && (!error.has_value() || data.has_value())) {
            throw invalid_argument(
                "Failure response requires error and no data"
            );
        }
    }
};

class DomainException : public runtime_error {
public:
    ErrorCode code;
    vector<string> details;
    bool retryable;

    DomainException(
        ErrorCode errorCode,
        const string& message,
        vector<string> errorDetails = {},
        bool canRetry = false
    )
        : runtime_error(message),
          code(errorCode),
          details(move(errorDetails)),
          retryable(canRetry) {}
};

struct BranchPolicy {
    string branchName;
    int requiredApprovals = 2;
    vector<string> requiredChecks;
    bool restrictDirectPush = true;
    bool restrictForcePush = true;
    bool requireResolvedConversations = true;
    bool requireLinearHistory = false;
    bool administratorBypass = false;
};

enum class ReviewState {
    Pending,
    Approved,
    ChangesRequested,
    Dismissed
};

struct Review {
    string reviewer;
    ReviewState state;
    bool eligible;
    bool latest = true;
};

struct PullRequest {
    int id;
    string sourceBranch;
    string targetBranch;
    string author;
    bool draft = false;
    bool open = true;
    bool mergeConflict = false;
    bool sourceUpToDate = true;
    bool conversationsResolved = true;
    bool linearHistory = true;
    vector<Review> reviews;
    unordered_map<string, bool> statusChecks;
};

struct MergeDecision {
    bool eligible;
    vector<string> blockers;
};

class GovernanceEngine {
private:
    BranchPolicy policy;

public:
    explicit GovernanceEngine(BranchPolicy branchPolicy)
        : policy(move(branchPolicy)) {}

    MergeDecision evaluate(const PullRequest& pr) const {
        vector<string> blockers;

        if (!pr.open) {
            blockers.push_back("Pull Request is closed");
        }

        if (pr.draft) {
            blockers.push_back("Draft Pull Request cannot be merged");
        }

        if (pr.targetBranch != policy.branchName) {
            blockers.push_back("Target branch does not match policy");
        }

        if (pr.sourceBranch == pr.targetBranch) {
            blockers.push_back("Source and target branches must differ");
        }

        if (pr.mergeConflict) {
            blockers.push_back("Merge conflicts must be resolved");
        }

        if (!pr.sourceUpToDate) {
            blockers.push_back("Source branch must be synchronized");
        }

        if (
            policy.requireResolvedConversations &&
            !pr.conversationsResolved
        ) {
            blockers.push_back("Unresolved review conversations");
        }

        if (
            policy.requireLinearHistory &&
            !pr.linearHistory
        ) {
            blockers.push_back("Linear history requirement failed");
        }

        // Only the latest eligible review from each reviewer is counted.
        map<string, ReviewState> latestReviews;

        for (const auto& review : pr.reviews) {
            if (review.eligible && review.latest) {
                latestReviews[review.reviewer] = review.state;
            }
        }

        int approvals = 0;

        for (const auto& [reviewer, state] : latestReviews) {
            if (state == ReviewState::Approved) {
                ++approvals;
            }

            if (state == ReviewState::ChangesRequested) {
                blockers.push_back(
                    "Outstanding changes requested by " + reviewer
                );
            }
        }

        if (approvals < policy.requiredApprovals) {
            blockers.push_back(
                "Insufficient approvals: " +
                to_string(approvals) + "/" +
                to_string(policy.requiredApprovals)
            );
        }

        // Missing and failed checks are both blockers.
        for (const auto& check : policy.requiredChecks) {
            auto iterator = pr.statusChecks.find(check);

            if (iterator == pr.statusChecks.end()) {
                blockers.push_back("Missing status check: " + check);
            } else if (!iterator->second) {
                blockers.push_back("Failed status check: " + check);
            }
        }

        return {
            blockers.empty(),
            move(blockers)
        };
    }

    const BranchPolicy& getPolicy() const {
        return policy;
    }
};

class Repository {
private:
    unordered_map<string, BranchPolicy> policies;
    unordered_map<int, PullRequest> pullRequests;
    vector<string> auditLog;

public:
    void protectBranch(BranchPolicy policy) {
        if (policy.branchName.empty()) {
            throw invalid_argument("Branch name cannot be empty");
        }

        if (policy.requiredApprovals < 0) {
            throw invalid_argument("Approval count cannot be negative");
        }

        if (policy.requiredApprovals > 20) {
            throw invalid_argument("Approval count exceeds policy limit");
        }

        policies[policy.branchName] = move(policy);
    }

    void addPullRequest(PullRequest pr) {
        if (pr.id <= 0) {
            throw invalid_argument("Invalid Pull Request ID");
        }

        if (pr.sourceBranch.empty() || pr.targetBranch.empty()) {
            throw invalid_argument("Branch names are required");
        }

        if (pr.sourceBranch == pr.targetBranch) {
            throw invalid_argument("Source and target must differ");
        }

        if (!policies.count(pr.targetBranch)) {
            throw invalid_argument("Target branch has no governance policy");
        }

        if (pullRequests.count(pr.id)) {
            throw invalid_argument("Duplicate Pull Request ID");
        }

        pullRequests.emplace(pr.id, move(pr));
    }

    MergeDecision evaluate(int id) const {
        auto iterator = pullRequests.find(id);

        if (iterator == pullRequests.end()) {
            throw DomainException(
                ErrorCode::NotFound,
                "Pull Request does not exist"
            );
        }

        const PullRequest& pr = iterator->second;

        GovernanceEngine engine(policies.at(pr.targetBranch));
        return engine.evaluate(pr);
    }

    void merge(int id, const string& actor) {
        auto iterator = pullRequests.find(id);

        if (iterator == pullRequests.end()) {
            throw DomainException(
                ErrorCode::NotFound,
                "Pull Request does not exist"
            );
        }

        if (actor.empty()) {
            throw DomainException(
                ErrorCode::Forbidden,
                "Merge actor is required"
            );
        }

        PullRequest& pr = iterator->second;
        const BranchPolicy& policy = policies.at(pr.targetBranch);

        if (actor == pr.author) {
            throw DomainException(
                ErrorCode::Forbidden,
                "Pull Request author cannot merge their own changes"
            );
        }

        MergeDecision decision = evaluate(id);

        if (!decision.eligible) {
            string message = "Merge blocked: ";

            for (const auto& blocker : decision.blockers) {
                message += blocker + "; ";
            }

            throw DomainException(
                ErrorCode::Conflict,
                message
            );
        }

        if (policy.restrictDirectPush && actor.empty()) {
            throw DomainException(
                ErrorCode::Forbidden,
                "Invalid merge identity"
            );
        }

        pr.open = false;

        auditLog.push_back(
            "PR #" + to_string(id) +
            " merged into " + pr.targetBranch +
            " by " + actor
        );
    }

    void close(int id, const string& actor) {
        auto iterator = pullRequests.find(id);

        if (iterator == pullRequests.end()) {
            throw DomainException(
                ErrorCode::NotFound,
                "Pull Request does not exist"
            );
        }

        if (actor.empty()) {
            throw DomainException(
                ErrorCode::Forbidden,
                "Actor is required"
            );
        }

        if (!iterator->second.open) {
            throw DomainException(
                ErrorCode::Conflict,
                "Pull Request is already closed"
            );
        }

        iterator->second.open = false;
        auditLog.push_back(
            "PR #" + to_string(id) + " closed by " + actor
        );
    }

    const vector<string>& getAuditLog() const {
        return auditLog;
    }
};

void printDecision(
    int id,
    const MergeDecision& decision
) {
    cout << "\nPull Request #" << id << "\n";
    cout << "Merge eligible: "
         << (decision.eligible ? "YES" : "NO") << "\n";

    if (!decision.eligible) {
        cout << "Blocking conditions:\n";

        for (const auto& blocker : decision.blockers) {
            cout << " - " << blocker << "\n";
        }
    }
}

int main() {
    try {
        Repository repository;

        BranchPolicy mainPolicy;
        mainPolicy.branchName = "main";
        mainPolicy.requiredApprovals = 2;
        mainPolicy.requiredChecks = {
            "unit-tests",
            "security-scan",
            "integration-tests"
        };
        mainPolicy.restrictDirectPush = true;
        mainPolicy.restrictForcePush = true;
        mainPolicy.requireResolvedConversations = true;
        mainPolicy.requireLinearHistory = true;

        repository.protectBranch(mainPolicy);

        PullRequest validPR;
        validPR.id = 501;
        validPR.sourceBranch = "feature/api-response";
        validPR.targetBranch = "main";
        validPR.author = "developer-a";

        validPR.reviews = {
            {"reviewer-b", ReviewState::Approved, true, true},
            {"reviewer-c", ReviewState::Approved, true, true},
            {"reviewer-d", ReviewState::Pending, false, true}
        };

        validPR.statusChecks = {
            {"unit-tests", true},
            {"security-scan", true},
            {"integration-tests", true}
        };

        repository.addPullRequest(validPR);

        PullRequest blockedPR = validPR;
        blockedPR.id = 502;
        blockedPR.sourceBranch = "feature/incomplete";
        blockedPR.reviews = {
            {"reviewer-b", ReviewState::Approved, true, true}
        };
        blockedPR.statusChecks["security-scan"] = false;
        blockedPR.statusChecks.erase("integration-tests");
        blockedPR.conversationsResolved = false;

        repository.addPullRequest(blockedPR);

        PullRequest draftPR = validPR;
        draftPR.id = 503;
        draftPR.sourceBranch = "feature/draft";
        draftPR.draft = true;

        repository.addPullRequest(draftPR);

        printDecision(501, repository.evaluate(501));
        printDecision(502, repository.evaluate(502));
        printDecision(503, repository.evaluate(503));

        cout << "\nAttempting merge of PR #501...\n";
        repository.merge(501, "maintainer-x");
        cout << "Merge completed successfully.\n";

        cout << "\nAttempting merge of PR #502...\n";

        try {
            repository.merge(502, "maintainer-x");
        } catch (const DomainException& ex) {
            cout << "Merge rejected: " << ex.what() << "\n";
        }

        cout << "\nAudit log:\n";

        for (const auto& entry : repository.getAuditLog()) {
            cout << " - " << entry << "\n";
        }

        cout << "\nGovernance evaluation completed.\n";
    } catch (const exception& ex) {
        cerr << "Application failure: " << ex.what() << "\n";
        return 1;
    }

    return 0;
}
