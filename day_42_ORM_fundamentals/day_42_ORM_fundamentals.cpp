#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * ORM Fundamentals: C++ repository inventory case study
 *
 * Scenario:
 * A development platform stores repositories, developers, and pull-request
 * metadata in relational tables. The C++ service exposes these records as
 * domain objects and evaluates relationships without hiding the distinction
 * between relational rows and object graphs.
 *
 * The program demonstrates:
 * - model-to-table mapping
 * - one-to-many and many-to-many relationships
 * - identity maps
 * - lazy-style relationship loading
 * - validation before persistence
 * - transaction-like unit-of-work behavior
 * - object/relational trade-offs
 */

enum class PullRequestState {
    Draft,
    Open,
    Merged,
    Closed
};

std::string stateName(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft:
            return "DRAFT";
        case PullRequestState::Open:
            return "OPEN";
        case PullRequestState::Merged:
            return "MERGED";
        case PullRequestState::Closed:
            return "CLOSED";
    }

    return "UNKNOWN";
}

struct Repository {
    int id;
    std::string name;
    std::string defaultBranch;
};

struct Developer {
    int id;
    std::string username;
    std::string email;
};

struct Commit {
    int id;
    int repositoryId;
    std::string hash;
    std::string message;
};

struct PullRequest {
    int id;
    int repositoryId;
    int authorId;
    std::string sourceBranch;
    std::string targetBranch;
    PullRequestState state;
    std::vector<int> commitIds;

    // The relationship is represented by foreign-key IDs rather than copied
    // Developer or Repository objects. This mirrors how normalized tables
    // avoid duplicating the referenced row.
};

class IdentityMap {
private:
    std::unordered_map<int, Repository> repositories;
    std::unordered_map<int, Developer> developers;
    std::unordered_map<int, PullRequest> pullRequests;

public:
    Repository& repository(const Repository& repository) {
        auto [it, inserted] = repositories.emplace(repository.id, repository);

        if (!inserted) {
            it->second = repository;
        }

        return it->second;
    }

    Developer& developer(const Developer& developer) {
        auto [it, inserted] = developers.emplace(developer.id, developer);

        if (!inserted) {
            it->second = developer;
        }

        return it->second;
    }

    PullRequest& pullRequest(const PullRequest& pullRequest) {
        auto [it, inserted] =
            pullRequests.emplace(pullRequest.id, pullRequest);

        if (!inserted) {
            it->second = pullRequest;
        }

        return it->second;
    }

    Repository* findRepository(int id) {
        auto it = repositories.find(id);
        return it == repositories.end() ? nullptr : &it->second;
    }

    Developer* findDeveloper(int id) {
        auto it = developers.find(id);
        return it == developers.end() ? nullptr : &it->second;
    }

    PullRequest* findPullRequest(int id) {
        auto it = pullRequests.find(id);
        return it == pullRequests.end() ? nullptr : &it->second;
    }
};

class RepositoryStore {
private:
    std::vector<Repository> repositories;
    std::vector<Developer> developers;
    std::vector<Commit> commits;
    std::vector<PullRequest> pullRequests;

public:
    void addRepository(const Repository& repository) {
        if (repository.name.empty()) {
            throw std::invalid_argument("Repository name cannot be empty");
        }

        if (repository.defaultBranch.empty()) {
            throw std::invalid_argument(
                "Repository default branch is required"
            );
        }

        repositories.push_back(repository);
    }

    void addDeveloper(const Developer& developer) {
        if (developer.username.empty()) {
            throw std::invalid_argument(
                "Developer username cannot be empty"
            );
        }

        developers.push_back(developer);
    }

    void addCommit(const Commit& commit) {
        if (commit.hash.size() < 7) {
            throw std::invalid_argument(
                "Commit hash is too short to represent a valid identifier"
            );
        }

        commits.push_back(commit);
    }

    void addPullRequest(const PullRequest& pullRequest) {
        if (pullRequest.sourceBranch.empty() ||
            pullRequest.targetBranch.empty()) {
            throw std::invalid_argument(
                "Both source and target branches are required"
            );
        }

        if (pullRequest.sourceBranch == pullRequest.targetBranch) {
            throw std::invalid_argument(
                "A pull request cannot target its own source branch"
            );
        }

        pullRequests.push_back(pullRequest);
    }

    const std::vector<Repository>& getRepositories() const {
        return repositories;
    }

    const std::vector<Developer>& getDevelopers() const {
        return developers;
    }

    const std::vector<Commit>& getCommits() const {
        return commits;
    }

    const std::vector<PullRequest>& getPullRequests() const {
        return pullRequests;
    }
};

class UnitOfWork {
private:
    RepositoryStore& store;
    std::vector<std::function<void()>> operations;

public:
    explicit UnitOfWork(RepositoryStore& store)
        : store(store) {}

    void addOperation(std::function<void()> operation) {
        operations.push_back(std::move(operation));
    }

    void commit() {
        // This is a teaching model of a unit-of-work. A production ORM would
        // coordinate a real database transaction and handle generated keys,
        // rollback, isolation, and database errors.
        try {
            for (auto& operation : operations) {
                operation();
            }

            operations.clear();
        } catch (...) {
            operations.clear();
            throw;
        }
    }
};

struct PullRequestView {
    PullRequest pullRequest;
    std::string repositoryName;
    std::string authorUsername;
    std::vector<Commit> commits;
};

class PullRequestMapper {
public:
    static PullRequestView hydrate(
        const PullRequest& pullRequest,
        const RepositoryStore& store,
        IdentityMap& identityMap
    ) {
        auto repositoryIt = std::find_if(
            store.getRepositories().begin(),
            store.getRepositories().end(),
            [&](const Repository& repository) {
                return repository.id == pullRequest.repositoryId;
            }
        );

        if (repositoryIt == store.getRepositories().end()) {
            throw std::runtime_error("Referenced repository does not exist");
        }

        auto developerIt = std::find_if(
            store.getDevelopers().begin(),
            store.getDevelopers().end(),
            [&](const Developer& developer) {
                return developer.id == pullRequest.authorId;
            }
        );

        if (developerIt == store.getDevelopers().end()) {
            throw std::runtime_error("Referenced developer does not exist");
        }

        Repository& repository = identityMap.repository(*repositoryIt);
        Developer& developer = identityMap.developer(*developerIt);

        std::vector<Commit> relatedCommits;

        for (int commitId : pullRequest.commitIds) {
            auto commitIt = std::find_if(
                store.getCommits().begin(),
                store.getCommits().end(),
                [&](const Commit& commit) {
                    return commit.id == commitId;
                }
            );

            if (commitIt == store.getCommits().end()) {
                throw std::runtime_error("Pull request references missing commit");
            }

            relatedCommits.push_back(*commitIt);
        }

        return {
            pullRequest,
            repository.name,
            developer.username,
            relatedCommits
        };
    }
};

class RepositoryReport {
public:
    static void print(
        const RepositoryStore& store,
        IdentityMap& identityMap
    ) {
        std::cout << "\nRepository object graph\n";

        for (const auto& pullRequest : store.getPullRequests()) {
            PullRequestView view =
                PullRequestMapper::hydrate(
                    pullRequest,
                    store,
                    identityMap
                );

            std::cout
                << "PR #" << view.pullRequest.id
                << " in " << view.repositoryName
                << " by @" << view.authorUsername
                << " (" << stateName(view.pullRequest.state) << ")\n";

            std::cout
                << "  " << view.pullRequest.sourceBranch
                << " -> " << view.pullRequest.targetBranch << "\n";

            for (const auto& commit : view.commits) {
                std::cout
                    << "  commit " << commit.hash
                    << ": " << commit.message << "\n";
            }
        }
    }
};

void demonstrateObjectRelationalTradeoff(
    const RepositoryStore& store
) {
    std::map<int, int> commitsPerPullRequest;

    for (const auto& pullRequest : store.getPullRequests()) {
        commitsPerPullRequest[pullRequest.id] =
            static_cast<int>(pullRequest.commitIds.size());
    }

    std::cout << "\nSet-oriented aggregate\n";

    for (const auto& [pullRequestId, count] : commitsPerPullRequest) {
        std::cout
            << "PR #" << pullRequestId
            << " contains " << count << " commit references\n";
    }

    std::cout
        << "\nThe aggregate is naturally expressed by scanning related "
           "records, while an ORM typically gives developers object navigation. "
           "For large reporting queries, direct relational operations can be "
           "more efficient than hydrating a large object graph.\n";

    std::cout
        << "Repository count: "
        << store.getRepositories().size()
        << ", developer count: "
        << store.getDevelopers().size()
        << ", pull-request count: "
        << store.getPullRequests().size()
        << "\n";
}

int main() {
    try {
        RepositoryStore store;

        UnitOfWork unitOfWork(store);

        unitOfWork.addOperation([&store]() {
            store.addRepository({
                1,
                "platform-api",
                "main"
            });
        });

        unitOfWork.addOperation([&store]() {
            store.addDeveloper({
                10,
                "atul",
                "atul@example.com"
            });
        });

        unitOfWork.addOperation([&store]() {
            store.addCommit({
                100,
                1,
                "a81f9c2",
                "Add repository persistence service"
            });

            store.addCommit({
                101,
                1,
                "b72de11",
                "Add validation for repository metadata"
            });
        });

        unitOfWork.addOperation([&store]() {
            store.addPullRequest({
                500,
                1,
                10,
                "feature/orm-mapping",
                "main",
                PullRequestState::Open,
                {100, 101}
            });
        });

        unitOfWork.commit();

        IdentityMap identityMap;

        RepositoryReport::print(store, identityMap);

        demonstrateObjectRelationalTradeoff(store);

        std::cout << "\nIdentity-map behavior\n";

        Repository* first = identityMap.findRepository(1);
        Repository* second = identityMap.findRepository(1);

        std::cout
            << "Repeated lookup returns the same in-memory repository object: "
            << std::boolalpha
            << (first == second)
            << "\n";

        std::cout
            << "\nORM design distinction\n"
            << "Relational storage represents repository relationships through "
               "foreign keys and join operations. The object model represents "
               "the same relationships through references, collections, and "
               "domain types. Mapping code is the boundary between those models.\n";
    }
    catch (const std::exception& error) {
        std::cerr
            << "Application failure: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
