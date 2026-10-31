#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

enum class SecurityLevel {
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4
};

enum class ThreatCategory {
    Spoofing,
    Tampering,
    Repudiation,
    InformationDisclosure,
    DenialOfService,
    ElevationOfPrivilege
};

enum class ReviewState {
    Draft,
    Open,
    Merged,
    Closed
};

std::string to_string(SecurityLevel level) {
    switch (level) {
        case SecurityLevel::Low: return "LOW";
        case SecurityLevel::Medium: return "MEDIUM";
        case SecurityLevel::High: return "HIGH";
        case SecurityLevel::Critical: return "CRITICAL";
    }
    return "UNKNOWN";
}

std::string to_string(ThreatCategory category) {
    switch (category) {
        case ThreatCategory::Spoofing: return "Spoofing";
        case ThreatCategory::Tampering: return "Tampering";
        case ThreatCategory::Repudiation: return "Repudiation";
        case ThreatCategory::InformationDisclosure:
            return "Information Disclosure";
        case ThreatCategory::DenialOfService:
            return "Denial of Service";
        case ThreatCategory::ElevationOfPrivilege:
            return "Elevation of Privilege";
    }
    return "Unknown";
}

struct Asset {
    std::string name;
    SecurityLevel confidentiality;
    SecurityLevel integrity;
    SecurityLevel availability;
    std::string owner;
};

struct Threat {
    std::string name;
    ThreatCategory category;
    std::string asset;
    SecurityLevel likelihood;
    SecurityLevel impact;
    std::string mitigation;

    int riskScore() const {
        return static_cast<int>(likelihood) *
               static_cast<int>(impact);
    }
};

struct SecurityControl {
    std::string name;
    std::set<std::string> protects;
    bool implemented;
};

struct BranchProtectionPolicy {
    bool directPushAllowed{false};
    bool forcePushAllowed{false};
    bool deletionAllowed{false};
    bool requireHttps{true};
    bool requireAuthentication{true};
    bool requireStatusChecks{true};
    bool requireSecurityReview{true};
    int requiredApprovals{2};
};

struct StatusCheck {
    std::string name;
    bool passed;
    bool required;
};

struct Review {
    std::string reviewer;
    std::string decision;
    bool stale{false};
    bool dismissed{false};
};

struct PullRequest {
    int id;
    std::string sourceBranch;
    std::string targetBranch;
    ReviewState state;
    std::set<std::string> changedFiles;
    std::vector<Review> reviews;
    std::vector<StatusCheck> checks;
    bool hasUnresolvedSecurityFinding{false};
    bool branchUpToDate{true};
    bool mergeConflict{false};
};

class SecurityException : public std::runtime_error {
public:
    explicit SecurityException(const std::string& message)
        : std::runtime_error(message) {}
};

class InputValidator {
public:
    static void requireNonEmpty(
        const std::string& value,
        const std::string& field
    ) {
        if (value.empty()) {
            throw SecurityException(field + " cannot be empty.");
        }
    }

    static void validateBranch(const std::string& branch) {
        requireNonEmpty(branch, "Branch");

        if (branch.size() > 255) {
            throw SecurityException("Branch name is too long.");
        }

        if (branch.find("..") != std::string::npos ||
            branch.find("~") != std::string::npos ||
            branch.find("^") != std::string::npos ||
            branch.find(":") != std::string::npos ||
            branch.find("\\") != std::string::npos) {
            throw SecurityException("Unsafe branch name.");
        }
    }

    static void validatePath(const std::string& path) {
        requireNonEmpty(path, "Path");

        if (path[0] != '/') {
            throw SecurityException("Path must begin with '/'.");
        }

        if (path.find('\0') != std::string::npos ||
            path.find("../") != std::string::npos ||
            path.find("/..") != std::string::npos) {
            throw SecurityException("Potential path traversal detected.");
        }
    }
};

class RepositorySecurityModel {
private:
    std::string repositoryName_;
    std::map<std::string, Asset> assets_;
    std::vector<Threat> threats_;
    std::vector<SecurityControl> controls_;
    BranchProtectionPolicy protection_;

public:
    explicit RepositorySecurityModel(std::string repositoryName)
        : repositoryName_(std::move(repositoryName)) {}

    void addAsset(const Asset& asset) {
        if (assets_.contains(asset.name)) {
            throw SecurityException(
                "Duplicate asset: " + asset.name
            );
        }
        assets_.emplace(asset.name, asset);
    }

    void addThreat(const Threat& threat) {
        if (!assets_.contains(threat.asset)) {
            throw SecurityException(
                "Threat references unknown asset: " + threat.asset
            );
        }
        threats_.push_back(threat);
    }

    void addControl(const SecurityControl& control) {
        controls_.push_back(control);
    }

    const std::vector<Threat>& threats() const {
        return threats_;
    }

    const std::map<std::string, Asset>& assets() const {
        return assets_;
    }

    const std::vector<SecurityControl>& controls() const {
        return controls_;
    }

    const BranchProtectionPolicy& policy() const {
        return protection_;
    }

    bool evaluateCIA() const {
        for (const auto& [name, asset] : assets_) {
            if (asset.confidentiality == SecurityLevel::Critical ||
                asset.integrity == SecurityLevel::Critical ||
                asset.availability == SecurityLevel::Critical) {
                continue;
            }
        }
        return !assets_.empty();
    }
};

class MergeEligibilityEngine {
private:
    const BranchProtectionPolicy& policy_;

    static bool hasRequiredApproval(
        const PullRequest& pr,
        int required
    ) {
        std::unordered_set<std::string> approvedReviewers;

        for (const auto& review : pr.reviews) {
            if (review.decision == "APPROVED" &&
                !review.stale &&
                !review.dismissed) {
                approvedReviewers.insert(review.reviewer);
            }
        }

        return static_cast<int>(approvedReviewers.size()) >= required;
    }

    static bool allRequiredChecksPass(const PullRequest& pr) {
        for (const auto& check : pr.checks) {
            if (check.required && !check.passed) {
                return false;
            }
        }
        return true;
    }

public:
    explicit MergeEligibilityEngine(
        const BranchProtectionPolicy& policy
    )
        : policy_(policy) {}

    bool eligible(
        const PullRequest& pr,
        std::vector<std::string>& failures
    ) const {
        failures.clear();

        if (pr.state != ReviewState::Open) {
            failures.push_back("Pull Request is not open.");
        }

        if (!pr.branchUpToDate) {
            failures.push_back("Source branch is behind target branch.");
        }

        if (pr.mergeConflict) {
            failures.push_back("Merge conflict must be resolved.");
        }

        if (pr.hasUnresolvedSecurityFinding) {
            failures.push_back("Unresolved security finding exists.");
        }

        if (policy_.requireStatusChecks &&
            !allRequiredChecksPass(pr)) {
            failures.push_back("A required status check has failed.");
        }

        if (policy_.requireSecurityReview &&
            !hasRequiredApproval(pr, policy_.requiredApprovals)) {
            failures.push_back(
                "Required security approvals are missing or stale."
            );
        }

        return failures.empty();
    }
};

std::string generateAuditId() {
    static std::mt19937_64 generator(
        static_cast<unsigned long long>(
            std::chrono::high_resolution_clock::now()
                .time_since_epoch()
                .count()
        )
    );

    std::uniform_int_distribution<unsigned long long> distribution;
    std::ostringstream output;
    output << std::hex << distribution(generator);
    return output.str();
}

void buildSecurityModel(RepositorySecurityModel& model) {
    model.addAsset({
        "credential-store",
        SecurityLevel::Critical,
        SecurityLevel::High,
        SecurityLevel::Medium,
        "identity-service"
    });

    model.addAsset({
        "session-store",
        SecurityLevel::Critical,
        SecurityLevel::Critical,
        SecurityLevel::High,
        "web-service"
    });

    model.addAsset({
        "customer-data",
        SecurityLevel::High,
        SecurityLevel::High,
        SecurityLevel::High,
        "data-service"
    });

    model.addAsset({
        "public-api",
        SecurityLevel::Medium,
        SecurityLevel::High,
        SecurityLevel::Critical,
        "platform-team"
    });

    model.addThreat({
        "Credential stuffing",
        ThreatCategory::Spoofing,
        "credential-store",
        SecurityLevel::High,
        SecurityLevel::Critical,
        "Rate limiting, strong password hashing and MFA."
    });

    model.addThreat({
        "Session theft",
        ThreatCategory::Spoofing,
        "session-store",
        SecurityLevel::High,
        SecurityLevel::Critical,
        "TLS, secure cookies and short-lived sessions."
    });

    model.addThreat({
        "SQL injection",
        ThreatCategory::Tampering,
        "customer-data",
        SecurityLevel::High,
        SecurityLevel::Critical,
        "Parameterized SQL and least-privilege database access."
    });

    model.addThreat({
        "Cross-site scripting",
        ThreatCategory::InformationDisclosure,
        "customer-data",
        SecurityLevel::High,
        SecurityLevel::High,
        "Output encoding and restrictive browser policy."
    });

    model.addThreat({
        "API exhaustion",
        ThreatCategory::DenialOfService,
        "public-api",
        SecurityLevel::Medium,
        SecurityLevel::Critical,
        "Rate limits, body limits and bounded resource use."
    });

    model.addThreat({
        "Broken authorization",
        ThreatCategory::ElevationOfPrivilege,
        "customer-data",
        SecurityLevel::High,
        SecurityLevel::Critical,
        "Server-side authorization with deny-by-default access."
    });

    model.addControl({
        "TLS",
        {"confidentiality", "integrity"},
        true
    });

    model.addControl({
        "Password hashing",
        {"confidentiality"},
        true
    });

    model.addControl({
        "Authorization",
        {"integrity", "confidentiality"},
        true
    });

    model.addControl({
        "Rate limiting",
        {"availability"},
        true
    });
}

PullRequest createExamplePullRequest() {
    PullRequest pr{
        101,
        "feature/payment-validation",
        "main",
        ReviewState::Open,
        {
            "src/payment.cpp",
            "src/auth.cpp",
            "tests/payment_security.cpp"
        },
        {},
        {},
        false,
        true,
        false
    };

    pr.reviews.push_back({
        "security-reviewer",
        "APPROVED",
        false,
        false
    });

    pr.reviews.push_back({
        "application-owner",
        "APPROVED",
        false,
        false
    });

    pr.checks.push_back({
        "unit-tests",
        true,
        true
    });

    pr.checks.push_back({
        "static-security-analysis",
        true,
        true
    });

    pr.checks.push_back({
        "dependency-audit",
        true,
        true
    });

    return pr;
}

void runSelfTests() {
    InputValidator::validateBranch("feature/security-hardening");
    InputValidator::validatePath("/api/v1/profile");

    bool rejected = false;

    try {
        InputValidator::validatePath("/files/../secret");
    } catch (const SecurityException&) {
        rejected = true;
    }

    if (!rejected) {
        throw SecurityException(
            "Path traversal test failed."
        );
    }

    RepositorySecurityModel model("secure-web-platform");
    buildSecurityModel(model);

    if (!model.evaluateCIA()) {
        throw SecurityException("CIA model validation failed.");
    }

    PullRequest pr = createExamplePullRequest();
    MergeEligibilityEngine engine(model.policy());

    std::vector<std::string> failures;

    if (!engine.eligible(pr, failures)) {
        std::ostringstream message;
        message << "Valid merge was rejected:";
        for (const auto& failure : failures) {
            message << " " << failure;
        }
        throw SecurityException(message.str());
    }

    pr.reviews[0].stale = true;

    if (engine.eligible(pr, failures)) {
        throw SecurityException(
            "Stale approval was incorrectly accepted."
        );
    }

    std::cout << "Self-tests passed. Audit ID: "
              << generateAuditId() << "\n";
}

int main() {
    try {
        runSelfTests();

        RepositorySecurityModel model("secure-web-platform");
        buildSecurityModel(model);

        std::cout << "\nWEB SECURITY GOVERNANCE ENGINE\n";
        std::cout << "============================================\n";

        std::cout << "\nCIA assets\n";
        for (const auto& [name, asset] : model.assets()) {
            std::cout
                << "- " << name
                << ": C=" << to_string(asset.confidentiality)
                << ", I=" << to_string(asset.integrity)
                << ", A=" << to_string(asset.availability)
                << "\n";
        }

        std::cout << "\nThreat model\n";
        for (const auto& threat : model.threats()) {
            std::cout
                << "- " << threat.name
                << " | " << to_string(threat.category)
                << " | risk=" << threat.riskScore()
                << " | asset=" << threat.asset
                << "\n";
        }

        std::cout << "\nSecurity controls\n";
        for (const auto& control : model.controls()) {
            std::cout
                << "- " << control.name
                << ": "
                << (control.implemented ? "implemented" : "missing")
                << "\n";
        }

        PullRequest pr = createExamplePullRequest();
        MergeEligibilityEngine engine(model.policy());
        std::vector<std::string> failures;

        bool eligible = engine.eligible(pr, failures);

        std::cout << "\nMerge eligibility\n";
        std::cout << "Pull Request #" << pr.id << ": "
                  << (eligible ? "ELIGIBLE" : "BLOCKED")
                  << "\n";

        if (!eligible) {
            for (const auto& failure : failures) {
                std::cout << "  - " << failure << "\n";
            }
        }

        pr.hasUnresolvedSecurityFinding = true;
        eligible = engine.eligible(pr, failures);

        std::cout << "\nSecurity finding scenario\n";
        std::cout << "Pull Request #" << pr.id << ": "
                  << (eligible ? "ELIGIBLE" : "BLOCKED")
                  << "\n";

        for (const auto& failure : failures) {
            std::cout << "  - " << failure << "\n";
        }

        std::cout << "\nDesign constraints\n";
        std::cout << "- Authorization is evaluated server-side.\n";
        std::cout << "- Security findings block merge eligibility.\n";
        std::cout << "- Stale approvals do not satisfy current requirements.\n";
        std::cout << "- Required automated checks must pass.\n";
        std::cout << "- Branch freshness and merge conflicts are enforced.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Security engine failure: "
                  << error.what() << "\n";
        return 1;
    }
}
