#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * PostgreSQL Advanced Fundamentals: C++ Repository Metadata Case Study
 *
 * This program models a PostgreSQL-oriented repository metadata service.
 * It does not attempt to implement a PostgreSQL server in C++. Instead, it
 * focuses on the application-side structures that map naturally to:
 *
 *   UUIDs       -> opaque identifiers
 *   enums       -> strongly typed states
 *   arrays      -> ordered collections
 *   JSONB       -> flexible configuration documents
 *   sequences   -> monotonically allocated numeric identifiers
 *   schemas     -> logical database namespaces
 *   extensions  -> database capabilities such as pgcrypto
 *
 * The implementation uses C++17 standard-library facilities only.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic repository_governance.cpp -o repository_governance
 */

namespace postgres_lab {

enum class RepositoryState {
    Active,
    Archived
};

enum class ChangeState {
    Draft,
    Review,
    Approved,
    Merged,
    Closed
};

enum class Environment {
    Development,
    Staging,
    Production
};

std::string to_string(ChangeState state) {
    switch (state) {
        case ChangeState::Draft:
            return "draft";
        case ChangeState::Review:
            return "review";
        case ChangeState::Approved:
            return "approved";
        case ChangeState::Merged:
            return "merged";
        case ChangeState::Closed:
            return "closed";
    }

    throw std::logic_error("Unknown ChangeState");
}

std::string to_string(Environment environment) {
    switch (environment) {
        case Environment::Development:
            return "development";
        case Environment::Staging:
            return "staging";
        case Environment::Production:
            return "production";
    }

    throw std::logic_error("Unknown Environment");
}

class Uuid {
public:
    Uuid() : value_(generate()) {}

    explicit Uuid(std::string value) : value_(std::move(value)) {
        validate(value_);
    }

    const std::string& str() const {
        return value_;
    }

    bool operator==(const Uuid& other) const {
        return value_ == other.value_;
    }

private:
    std::string value_;

    static std::string generate() {
        static thread_local std::mt19937 generator(
            std::random_device{}()
        );

        std::uniform_int_distribution<int> distribution(0, 15);

        std::string value;
        value.reserve(36);

        for (int position = 0; position < 36; ++position) {
            if (position == 8 || position == 13 ||
                position == 18 || position == 23) {
                value.push_back('-');
                continue;
            }

            value.push_back("0123456789abcdef"[distribution(generator)]);
        }

        value[14] = '4';
        value[19] = "89ab"[distribution(generator) % 4];

        return value;
    }

    static void validate(const std::string& value) {
        if (value.size() != 36 ||
            value[8] != '-' ||
            value[13] != '-' ||
            value[18] != '-' ||
            value[23] != '-') {
            throw std::invalid_argument("Invalid UUID representation");
        }
    }
};

struct JsonValue {
    enum class Kind {
        String,
        Number,
        Boolean,
        Object,
        Array,
        Null
    };

    Kind kind;
    std::string scalar;
    std::map<std::string, JsonValue> object;
    std::vector<JsonValue> array;

    static JsonValue string(std::string value) {
        return {Kind::String, std::move(value), {}, {}};
    }

    static JsonValue number(std::int64_t value) {
        return {Kind::Number, std::to_string(value), {}, {}};
    }

    static JsonValue boolean(bool value) {
        return {Kind::Boolean, value ? "true" : "false", {}, {}};
    }

    static JsonValue null() {
        return {Kind::Null, "null", {}, {}};
    }

    static JsonValue objectValue(
        std::map<std::string, JsonValue> values
    ) {
        return {Kind::Object, {}, std::move(values), {}};
    }

    static JsonValue arrayValue(
        std::vector<JsonValue> values
    ) {
        return {Kind::Array, {}, {}, std::move(values)};
    }
};

std::string escapeJsonString(const std::string& value) {
    std::ostringstream output;

    for (char character : value) {
        switch (character) {
            case '"':
                output << "\\\"";
                break;
            case '\\':
                output << "\\\\";
                break;
            case '\n':
                output << "\\n";
                break;
            case '\r':
                output << "\\r";
                break;
            case '\t':
                output << "\\t";
                break;
            default:
                output << character;
        }
    }

    return output.str();
}

std::string jsonToString(const JsonValue& value) {
    switch (value.kind) {
        case JsonValue::Kind::String:
            return "\"" + escapeJsonString(value.scalar) + "\"";

        case JsonValue::Kind::Number:
        case JsonValue::Kind::Boolean:
        case JsonValue::Kind::Null:
            return value.scalar;

        case JsonValue::Kind::Array: {
            std::ostringstream output;
            output << "[";

            for (std::size_t index = 0; index < value.array.size(); ++index) {
                if (index != 0) {
                    output << ", ";
                }
                output << jsonToString(value.array[index]);
            }

            output << "]";
            return output.str();
        }

        case JsonValue::Kind::Object: {
            std::ostringstream output;
            output << "{";

            bool first = true;
            for (const auto& [key, nested] : value.object) {
                if (!first) {
                    output << ", ";
                }

                first = false;
                output << "\"" << escapeJsonString(key) << "\": "
                       << jsonToString(nested);
            }

            output << "}";
            return output.str();
        }
    }

    throw std::logic_error("Unsupported JSON value");
}

class Sequence {
public:
    Sequence(std::int64_t start, std::int64_t increment, std::size_t cache)
        : next_(start), increment_(increment), cache_(cache) {
        if (increment_ <= 0 || cache_ == 0) {
            throw std::invalid_argument(
                "Sequence increment must be positive and cache must be non-zero"
            );
        }
    }

    std::int64_t nextValue() {
        const auto current = next_;
        next_ += increment_;
        return current;
    }

    std::int64_t currentValue() const {
        return next_ - increment_;
    }

    std::size_t cacheSize() const {
        return cache_;
    }

private:
    std::int64_t next_;
    std::int64_t increment_;
    std::size_t cache_;
};

struct BranchPolicy {
    bool requireLinearHistory = false;
    bool allowForcePush = false;
    bool allowDeletion = false;
    std::size_t requiredApprovals = 1;
    std::set<std::string> requiredChecks;
};

struct Repository {
    Uuid id;
    std::int64_t databaseNumber;
    std::string name;
    RepositoryState state;
    Environment environment;
    std::vector<std::string> maintainers;
    std::map<std::string, std::string> scalarConfiguration;
    std::vector<std::string> protectedBranches;
    BranchPolicy policy;
};

struct ChangeRequest {
    Uuid id;
    std::int64_t databaseNumber;
    Uuid repositoryId;
    std::string title;
    std::string author;
    ChangeState state;
    std::vector<std::string> labels;
    JsonValue details;
    std::vector<std::string> commits;
    std::vector<std::string> approvals;
    std::map<std::string, bool> statusChecks;
};

class RepositoryService {
public:
    RepositoryService()
        : sequence_(10000, 1, 20) {}

    Repository createRepository(
        std::string name,
        Environment environment,
        std::vector<std::string> maintainers,
        BranchPolicy policy
    ) {
        if (name.empty()) {
            throw std::invalid_argument("Repository name cannot be empty");
        }

        if (maintainers.empty()) {
            throw std::invalid_argument(
                "A repository must have at least one maintainer"
            );
        }

        if (repositoryNames_.contains(name)) {
            throw std::invalid_argument(
                "Repository name already exists"
            );
        }

        Repository repository{
            Uuid{},
            sequence_.nextValue(),
            std::move(name),
            RepositoryState::Active,
            environment,
            std::move(maintainers),
            {},
            {"main"},
            std::move(policy)
        };

        repositoryNames_.insert(repository.name);
        repositories_.emplace(
            repository.id.str(),
            repository
        );

        return repository;
    }

    ChangeRequest createChange(
        const Repository& repository,
        std::string title,
        std::string author,
        std::vector<std::string> labels,
        JsonValue details
    ) {
        if (repository.state != RepositoryState::Active) {
            throw std::logic_error(
                "Changes cannot be created in an archived repository"
            );
        }

        if (title.size() < 5 || title.size() > 200) {
            throw std::invalid_argument(
                "Change title must contain between 5 and 200 characters"
            );
        }

        if (author.empty()) {
            throw std::invalid_argument("Author is required");
        }

        ChangeRequest change{
            Uuid{},
            sequence_.nextValue(),
            repository.id,
            std::move(title),
            std::move(author),
            ChangeState::Draft,
            std::move(labels),
            std::move(details),
            {},
            {},
            {}
        };

        changes_.emplace(change.id.str(), change);
        return change;
    }

    void addCommit(ChangeRequest& change, std::string commitHash) {
        if (change.state == ChangeState::Merged ||
            change.state == ChangeState::Closed) {
            throw std::logic_error(
                "Commits cannot be added to a terminal change"
            );
        }

        if (commitHash.size() < 7) {
            throw std::invalid_argument("Commit identifier is too short");
        }

        change.commits.push_back(std::move(commitHash));

        if (change.state == ChangeState::Draft) {
            change.state = ChangeState::Review;
        }
    }

    void recordCheck(
        ChangeRequest& change,
        std::string checkName,
        bool passed
    ) {
        if (checkName.empty()) {
            throw std::invalid_argument("Status check name is required");
        }

        change.statusChecks[std::move(checkName)] = passed;
    }

    void approve(ChangeRequest& change, const std::string& reviewer) {
        if (change.state != ChangeState::Review &&
            change.state != ChangeState::Approved) {
            throw std::logic_error(
                "Only changes under review can receive approvals"
            );
        }

        if (reviewer == change.author) {
            throw std::logic_error(
                "Self-approval is rejected by repository policy"
            );
        }

        if (std::find(
                change.approvals.begin(),
                change.approvals.end(),
                reviewer
            ) != change.approvals.end()) {
            throw std::logic_error(
                "Reviewer has already approved this change"
            );
        }

        change.approvals.push_back(reviewer);
        change.state = ChangeState::Approved;
    }

    bool isMergeEligible(
        const Repository& repository,
        const ChangeRequest& change,
        std::string& reason
    ) const {
        if (change.repositoryId.str() != repository.id.str()) {
            reason = "Change belongs to a different repository";
            return false;
        }

        if (change.state != ChangeState::Approved) {
            reason = "Change does not have the required state";
            return false;
        }

        if (change.commits.empty()) {
            reason = "Change contains no commits";
            return false;
        }

        if (change.approvals.size() < repository.policy.requiredApprovals) {
            reason = "Required approval count has not been reached";
            return false;
        }

        for (const auto& requiredCheck : repository.policy.requiredChecks) {
            const auto iterator = change.statusChecks.find(requiredCheck);

            if (iterator == change.statusChecks.end()) {
                reason = "Required status check is missing: " + requiredCheck;
                return false;
            }

            if (!iterator->second) {
                reason = "Required status check failed: " + requiredCheck;
                return false;
            }
        }

        reason = "All configured merge conditions passed";
        return true;
    }

    void merge(
        const Repository& repository,
        ChangeRequest& change
    ) {
        std::string reason;

        if (!isMergeEligible(repository, change, reason)) {
            throw std::logic_error(
                "Merge rejected: " + reason
            );
        }

        change.state = ChangeState::Merged;
    }

private:
    Sequence sequence_;
    std::unordered_map<std::string, Repository> repositories_;
    std::unordered_map<std::string, ChangeRequest> changes_;
    std::set<std::string> repositoryNames_;
};

void printChange(const ChangeRequest& change) {
    std::cout << "\nChange\n";
    std::cout << "  UUID: " << change.id.str() << "\n";
    std::cout << "  Database number: " << change.databaseNumber << "\n";
    std::cout << "  Title: " << change.title << "\n";
    std::cout << "  Author: " << change.author << "\n";
    std::cout << "  State: " << to_string(change.state) << "\n";
    std::cout << "  Labels: ";

    for (std::size_t index = 0; index < change.labels.size(); ++index) {
        if (index != 0) {
            std::cout << ", ";
        }
        std::cout << change.labels[index];
    }

    std::cout << "\n";
    std::cout << "  Commits: " << change.commits.size() << "\n";
    std::cout << "  Approvals: " << change.approvals.size() << "\n";
    std::cout << "  JSONB-like details: "
              << jsonToString(change.details) << "\n";
}

void demonstrateFailure(
    RepositoryService& service,
    const Repository& repository,
    ChangeRequest& change
) {
    std::string reason;

    if (!service.isMergeEligible(repository, change, reason)) {
        std::cout << "\nExpected merge rejection:\n";
        std::cout << "  " << reason << "\n";
    }
}

}  // namespace postgres_lab

int main() {
    using namespace postgres_lab;

    try {
        RepositoryService service;

        BranchPolicy productionPolicy;
        productionPolicy.requiredApprovals = 2;
        productionPolicy.requireLinearHistory = true;
        productionPolicy.allowForcePush = false;
        productionPolicy.allowDeletion = false;
        productionPolicy.requiredChecks = {
            "unit-tests",
            "integration-tests",
            "security-scan"
        };

        Repository repository = service.createRepository(
            "market-platform",
            Environment::Production,
            {"atul", "priya", "marco"},
            productionPolicy
        );

        JsonValue details = JsonValue::objectValue({
            {"risk", JsonValue::string("medium")},
            {"files_changed", JsonValue::number(14)},
            {"security_sensitive", JsonValue::boolean(true)},
            {
                "deployment",
                JsonValue::objectValue({
                    {"strategy", JsonValue::string("canary")},
                    {"region", JsonValue::string("ap-south-1")}
                })
            },
            {
                "labels",
                JsonValue::arrayValue({
                    JsonValue::string("database"),
                    JsonValue::string("security")
                })
            }
        });

        ChangeRequest change = service.createChange(
            repository,
            "Add PostgreSQL audit metadata",
            "atul",
            {"database", "security", "audit"},
            details
        );

        printChange(change);

        service.addCommit(
            change,
            "8f5a1c2d7e9b"
        );

        service.recordCheck(change, "unit-tests", true);
        service.recordCheck(change, "integration-tests", true);

        demonstrateFailure(service, repository, change);

        service.approve(change, "priya");

        std::string reason;

        if (!service.isMergeEligible(repository, change, reason)) {
            std::cout << "\nMerge still blocked:\n";
            std::cout << "  " << reason << "\n";
        }

        service.approve(change, "marco");

        service.recordCheck(change, "security-scan", true);

        if (service.isMergeEligible(repository, change, reason)) {
            std::cout << "\nMerge eligibility granted:\n";
            std::cout << "  " << reason << "\n";

            service.merge(repository, change);
        }

        printChange(change);

        std::cout << "\nPostgreSQL mapping decisions\n";
        std::cout << "  Schema: advanced_fundamentals_lab\n";
        std::cout << "  UUID: database-generated identity\n";
        std::cout << "  Sequence: human-readable numeric identifier\n";
        std::cout << "  Enum: controlled state values\n";
        std::cout << "  JSONB: flexible nested metadata\n";
        std::cout << "  Array: ordered multi-value attributes\n";
        std::cout << "  Extension: pgcrypto supplies UUID generation\n";

        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Fatal error: "
                  << exception.what()
                  << '\n';

        return 1;
    }
}
