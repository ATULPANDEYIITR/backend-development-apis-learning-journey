#include <algorithm>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class PullRequestState {
    Draft,
    Open,
    Approved,
    Blocked,
    Merged,
    Closed
};

struct PullRequest {
    int id;
    std::string title;
    std::string author;
    std::string sourceBranch;
    std::string targetBranch;
    PullRequestState state;
    int changedFiles;
};

struct Review {
    std::string reviewer;
    bool approved;
    bool requestedChanges;
};

struct BranchPolicy {
    std::string branchName;
    int requiredApprovals;
    bool requirePassingChecks;
    bool prohibitDirectPush;
    bool prohibitForcePush;
};

class PullRequestRepository {
public:
    virtual ~PullRequestRepository() = default;

    virtual std::optional<PullRequest> findById(int id) const = 0;
    virtual void save(const PullRequest& request) = 0;
    virtual std::vector<PullRequest> findOpenForBranch(
        const std::string& targetBranch
    ) const = 0;
};

class MemoryPullRequestRepository final : public PullRequestRepository {
private:
    std::unordered_map<int, PullRequest> requests;

public:
    std::optional<PullRequest> findById(int id) const override {
        auto iterator = requests.find(id);

        if (iterator == requests.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    void save(const PullRequest& request) override {
        requests[request.id] = request;
    }

    std::vector<PullRequest> findOpenForBranch(
        const std::string& targetBranch
    ) const override {
        std::vector<PullRequest> result;

        for (const auto& [id, request] : requests) {
            if (request.targetBranch == targetBranch &&
                (request.state == PullRequestState::Open ||
                 request.state == PullRequestState::Approved ||
                 request.state == PullRequestState::Blocked)) {
                result.push_back(request);
            }
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const PullRequest& left, const PullRequest& right) {
                return left.id < right.id;
            }
        );

        return result;
    }
};

class MergeEligibilityEngine {
private:
    static int approvalCount(
        const std::vector<Review>& reviews,
        const std::string& author
    ) {
        int count = 0;

        for (const Review& review : reviews) {
            // Self-approval is rejected because approval must represent
            // independent review of the proposed change.
            if (review.approved && review.reviewer != author) {
                ++count;
            }
        }

        return count;
    }

public:
    static bool canMerge(
        const PullRequest& request,
        const BranchPolicy& policy,
        const std::vector<Review>& reviews,
        bool ciPassing,
        bool mergeConflict
    ) {
        if (request.state == PullRequestState::Draft) {
            return false;
        }

        if (request.state == PullRequestState::Merged ||
            request.state == PullRequestState::Closed) {
            return false;
        }

        if (mergeConflict) {
            return false;
        }

        for (const Review& review : reviews) {
            if (review.requestedChanges) {
                return false;
            }
        }

        if (approvalCount(reviews, request.author) <
            policy.requiredApprovals) {
            return false;
        }

        if (policy.requirePassingChecks && !ciPassing) {
            return false;
        }

        return true;
    }
};

class PullRequestService {
private:
    PullRequestRepository& repository;

public:
    explicit PullRequestService(PullRequestRepository& repository)
        : repository(repository) {}

    void open(
        int id,
        const std::string& title,
        const std::string& author,
        const std::string& source,
        const std::string& target,
        int changedFiles
    ) {
        if (title.empty() || source.empty() || target.empty()) {
            throw std::invalid_argument(
                "Pull Request title and branches are required"
            );
        }

        if (source == target) {
            throw std::invalid_argument(
                "Source and target branches must be different"
            );
        }

        if (changedFiles <= 0) {
            throw std::invalid_argument(
                "A Pull Request must contain at least one changed file"
            );
        }

        if (repository.findById(id).has_value()) {
            throw std::invalid_argument(
                "Pull Request ID already exists"
            );
        }

        repository.save({
            id,
            title,
            author,
            source,
            target,
            PullRequestState::Open,
            changedFiles
        });
    }

    void markApproved(int id) {
        auto request = repository.findById(id);

        if (!request) {
            throw std::out_of_range("Pull Request does not exist");
        }

        if (request->state != PullRequestState::Open) {
            throw std::logic_error(
                "Only an open Pull Request can become approved"
            );
        }

        request->state = PullRequestState::Approved;
        repository.save(*request);
    }

    bool merge(
        int id,
        const BranchPolicy& policy,
        const std::vector<Review>& reviews,
        bool ciPassing,
        bool mergeConflict
    ) {
        auto request = repository.findById(id);

        if (!request) {
            throw std::out_of_range("Pull Request does not exist");
        }

        if (!MergeEligibilityEngine::canMerge(
                *request,
                policy,
                reviews,
                ciPassing,
                mergeConflict)) {
            return false;
        }

        request->state = PullRequestState::Merged;
        repository.save(*request);
        return true;
    }
};

int main() {
    MemoryPullRequestRepository repository;
    PullRequestService service(repository);

    const BranchPolicy mainPolicy{
        "main",
        2,
        true,
        true,
        true
    };

    service.open(
        101,
        "Improve payment validation",
        "developer-a",
        "feature/payment-validation",
        "main",
        7
    );

    std::vector<Review> reviews{
        {"reviewer-a", true, false},
        {"reviewer-b", true, false}
    };

    const bool mergedWithoutCI = service.merge(
        101,
        mainPolicy,
        reviews,
        false,
        false
    );

    std::cout << "Merge with failing CI: "
              << (mergedWithoutCI ? "allowed" : "blocked")
              << '\n';

    const bool merged = service.merge(
        101,
        mainPolicy,
        reviews,
        true,
        false
    );

    std::cout << "Merge with required approvals and passing CI: "
              << (merged ? "allowed" : "blocked")
              << '\n';

    auto storedRequest = repository.findById(101);

    if (storedRequest) {
        std::cout << "Final Pull Request state: ";

        switch (storedRequest->state) {
            case PullRequestState::Draft:
                std::cout << "Draft";
                break;
            case PullRequestState::Open:
                std::cout << "Open";
                break;
            case PullRequestState::Approved:
                std::cout << "Approved";
                break;
            case PullRequestState::Blocked:
                std::cout << "Blocked";
                break;
            case PullRequestState::Merged:
                std::cout << "Merged";
                break;
            case PullRequestState::Closed:
                std::cout << "Closed";
                break;
        }

        std::cout << '\n';
    }

    /*
     * The service never knows how Pull Requests are persisted.
     * Replacing MemoryPullRequestRepository with a database-backed repository
     * changes the data-access layer without changing merge policy logic.
     */
    return 0;
}
