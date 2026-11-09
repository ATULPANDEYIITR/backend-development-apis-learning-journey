/*
 * Secure API Project
 * C++17 repository-independent API security and authorization engine.
 *
 * Features:
 * - Authentication state
 * - User and credential modeling
 * - Role-based authorization
 * - Permission evaluation
 * - Resource ownership
 * - Security policies
 * - Sliding-window rate limiting
 * - Token revocation
 * - Audit events
 * - Request validation
 * - Merge-free, explicit security decision pipeline
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic secure_api.cpp -o secure_api
 */

#include <algorithm>
#include <chrono>
#include <cctype>
#include <deque>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

// ---------------------------------------------------------
// Domain Types
// ---------------------------------------------------------

enum class Role {
    ADMIN,
    EDITOR,
    VIEWER
};

enum class HTTPMethod {
    GET,
    POST,
    PUT,
    PATCH,
    DELETE
};

enum class Decision {
    ALLOW,
    DENY
};

enum class AccountStatus {
    ACTIVE,
    SUSPENDED,
    DISABLED
};

enum class TokenStatus {
    VALID,
    EXPIRED,
    REVOKED,
    INVALID
};

struct User {
    std::string id;
    std::string username;
    std::set<Role> roles;
    AccountStatus status = AccountStatus::ACTIVE;
};

struct AccessToken {
    std::string tokenId;
    std::string userId;
    long long issuedAt;
    long long expiresAt;
    TokenStatus status = TokenStatus::VALID;
};

struct APIRequest {
    HTTPMethod method;
    std::string path;
    std::string userId;
    std::string tokenId;
    std::string clientId;
    std::string resourceId;
    std::size_t bodySize = 0;
};

struct Resource {
    std::string id;
    std::string ownerId;
    std::string content;
};

struct SecurityPolicy {
    int requestsPerWindow = 10;
    int windowSeconds = 60;
    std::size_t maximumBodySize = 16384;
    bool requireAuthentication = true;
    bool denyInactiveAccounts = true;
    bool enforceOwnership = true;
};

struct SecurityAudit {
    std::string event;
    std::string userId;
    std::string resource;
    Decision decision;
    std::string reason;
};

// ---------------------------------------------------------
// Utility Functions
// ---------------------------------------------------------

long long currentTimestamp() {
    using namespace std::chrono;

    return duration_cast<seconds>(
        system_clock::now().time_since_epoch()
    ).count();
}

std::string roleName(Role role) {
    switch (role) {
        case Role::ADMIN: return "ADMIN";
        case Role::EDITOR: return "EDITOR";
        case Role::VIEWER: return "VIEWER";
    }

    return "UNKNOWN";
}

std::string decisionName(Decision decision) {
    return decision == Decision::ALLOW ? "ALLOW" : "DENY";
}

bool validIdentifier(const std::string& value) {
    if (value.empty() || value.size() > 64) {
        return false;
    }

    return std::all_of(
        value.begin(),
        value.end(),
        [](unsigned char c) {
            return std::isalnum(c) || c == '_' || c == '-';
        }
    );
}

// ---------------------------------------------------------
// Permission Registry
// ---------------------------------------------------------

class PermissionRegistry {
private:
    std::map<Role, std::set<std::string>> permissions;

public:
    PermissionRegistry() {
        permissions[Role::ADMIN] = {
            "users:read",
            "users:create",
            "users:update",
            "users:delete",
            "reports:read",
            "system:manage"
        };

        permissions[Role::EDITOR] = {
            "users:read",
            "users:update",
            "reports:read"
        };

        permissions[Role::VIEWER] = {
            "users:read",
            "reports:read"
        };
    }

    bool hasPermission(
        const User& user,
        const std::string& permission
    ) const {

        for (Role role : user.roles) {
            auto iterator = permissions.find(role);

            if (
                iterator != permissions.end() &&
                iterator->second.count(permission) > 0
            ) {
                return true;
            }
        }

        return false;
    }

    std::set<std::string> getPermissions(const User& user) const {
        std::set<std::string> result;

        for (Role role : user.roles) {
            auto iterator = permissions.find(role);

            if (iterator != permissions.end()) {
                result.insert(
                    iterator->second.begin(),
                    iterator->second.end()
                );
            }
        }

        return result;
    }
};

// ---------------------------------------------------------
// User Directory
// ---------------------------------------------------------

class UserDirectory {
private:
    std::unordered_map<std::string, User> users;
    std::unordered_map<std::string, std::string> usernameIndex;

public:
    void addUser(const User& user) {
        if (
            !validIdentifier(user.id) ||
            !validIdentifier(user.username) ||
            user.roles.empty()
        ) {
            throw std::invalid_argument("Invalid user record.");
        }

        if (users.count(user.id) ||
            usernameIndex.count(user.username)) {
            throw std::invalid_argument("Duplicate user.");
        }

        users.emplace(user.id, user);
        usernameIndex.emplace(user.username, user.id);
    }

    const User* find(const std::string& id) const {
        auto iterator = users.find(id);

        if (iterator == users.end()) {
            return nullptr;
        }

        return &iterator->second;
    }

    void updateStatus(
        const std::string& id,
        AccountStatus status
    ) {
        auto iterator = users.find(id);

        if (iterator == users.end()) {
            throw std::invalid_argument("User does not exist.");
        }

        iterator->second.status = status;
    }

    std::size_t size() const {
        return users.size();
    }
};

// ---------------------------------------------------------
// Token Registry
// ---------------------------------------------------------

class TokenRegistry {
private:
    std::unordered_map<std::string, AccessToken> tokens;

public:
    void issue(const AccessToken& token) {
        if (
            token.tokenId.empty() ||
            token.userId.empty() ||
            token.expiresAt <= token.issuedAt
        ) {
            throw std::invalid_argument("Invalid token.");
        }

        if (tokens.count(token.tokenId)) {
            throw std::invalid_argument("Duplicate token.");
        }

        tokens.emplace(token.tokenId, token);
    }

    TokenStatus validate(
        const std::string& tokenId,
        const std::string& userId
    ) const {

        auto iterator = tokens.find(tokenId);

        if (iterator == tokens.end()) {
            return TokenStatus::INVALID;
        }

        const AccessToken& token = iterator->second;

        if (token.userId != userId) {
            return TokenStatus::INVALID;
        }

        if (token.status == TokenStatus::REVOKED) {
            return TokenStatus::REVOKED;
        }

        if (token.expiresAt <= currentTimestamp()) {
            return TokenStatus::EXPIRED;
        }

        return TokenStatus::VALID;
    }

    void revoke(const std::string& tokenId) {
        auto iterator = tokens.find(tokenId);

        if (iterator == tokens.end()) {
            throw std::invalid_argument("Token not found.");
        }

        iterator->second.status = TokenStatus::REVOKED;
    }
};

// ---------------------------------------------------------
// Resource Repository
// ---------------------------------------------------------

class ResourceRepository {
private:
    std::unordered_map<std::string, Resource> resources;

public:
    void add(const Resource& resource) {
        if (
            !validIdentifier(resource.id) ||
            resource.ownerId.empty() ||
            resource.content.size() > 5000
        ) {
            throw std::invalid_argument("Invalid resource.");
        }

        if (resources.count(resource.id)) {
            throw std::invalid_argument("Duplicate resource.");
        }

        resources.emplace(resource.id, resource);
    }

    const Resource* find(const std::string& id) const {
        auto iterator = resources.find(id);

        return iterator == resources.end()
            ? nullptr
            : &iterator->second;
    }

    std::size_t size() const {
        return resources.size();
    }
};

// ---------------------------------------------------------
// Sliding-Window Rate Limiter
// ---------------------------------------------------------

class RateLimiter {
private:
    int maximumRequests;
    int windowSeconds;

    std::unordered_map<
        std::string,
        std::deque<long long>
    > history;

public:
    RateLimiter(int limit, int window)
        : maximumRequests(limit),
          windowSeconds(window) {

        if (limit <= 0 || window <= 0) {
            throw std::invalid_argument(
                "Invalid rate limiter configuration."
            );
        }
    }

    bool allow(const std::string& clientId) {
        if (clientId.empty()) {
            return false;
        }

        const long long now = currentTimestamp();

        auto& requests = history[clientId];

        while (
            !requests.empty() &&
            now - requests.front() >= windowSeconds
        ) {
            requests.pop_front();
        }

        if (
            requests.size() >=
            static_cast<std::size_t>(maximumRequests)
        ) {
            return false;
        }

        requests.push_back(now);

        return true;
    }
};

// ---------------------------------------------------------
// Audit Service
// ---------------------------------------------------------

class AuditService {
private:
    std::vector<SecurityAudit> events;

public:
    void record(const SecurityAudit& event) {
        events.push_back(event);
    }

    void print() const {
        std::cout << "\nSECURITY AUDIT\n";

        for (const auto& event : events) {
            std::cout
                << "Event: " << event.event
                << " | User: " << event.userId
                << " | Resource: " << event.resource
                << " | Decision: " << decisionName(event.decision)
                << " | Reason: " << event.reason
                << '\n';
        }
    }

    std::size_t count(Decision decision) const {
        return std::count_if(
            events.begin(),
            events.end(),
            [decision](const SecurityAudit& event) {
                return event.decision == decision;
            }
        );
    }
};

// ---------------------------------------------------------
// Security Decision
// ---------------------------------------------------------

struct SecurityResult {
    Decision decision;
    int statusCode;
    std::string reason;
};

// ---------------------------------------------------------
// API Security Engine
// ---------------------------------------------------------

class SecureAPIEngine {
private:
    UserDirectory users;
    TokenRegistry tokens;
    ResourceRepository resources;
    PermissionRegistry permissionRegistry;
    RateLimiter rateLimiter;
    SecurityPolicy policy;
    AuditService audit;

public:
    explicit SecureAPIEngine(
        SecurityPolicy securityPolicy = SecurityPolicy{}
    )
        : rateLimiter(
            securityPolicy.requestsPerWindow,
            securityPolicy.windowSeconds
        ),
          policy(securityPolicy) {}

    void registerUser(const User& user) {
        users.addUser(user);
    }

    void registerToken(const AccessToken& token) {
        tokens.issue(token);
    }

    void registerResource(const Resource& resource) {
        resources.add(resource);
    }

    SecurityResult evaluate(const APIRequest& request) {
        SecurityResult result{
            Decision::DENY,
            403,
            "Access denied."
        };

        auto finish = [&](Decision decision,
                          int status,
                          const std::string& reason) {

            result = {decision, status, reason};

            audit.record({
                "API_REQUEST",
                request.userId,
                request.path,
                decision,
                reason
            });

            return result;
        };

        if (
            request.path.empty() ||
            request.path.size() > 256 ||
            request.bodySize > policy.maximumBodySize
        ) {
            return finish(
                Decision::DENY,
                413,
                "Invalid request path or oversized body."
            );
        }

        if (!rateLimiter.allow(request.clientId)) {
            return finish(
                Decision::DENY,
                429,
                "Rate limit exceeded."
            );
        }

        if (policy.requireAuthentication) {
            if (
                request.userId.empty() ||
                request.tokenId.empty()
            ) {
                return finish(
                    Decision::DENY,
                    401,
                    "Authentication required."
                );
            }
        }

        const User* user = users.find(request.userId);

        if (!user) {
            return finish(
                Decision::DENY,
                401,
                "Unknown account."
            );
        }

        if (
            policy.denyInactiveAccounts &&
            user->status != AccountStatus::ACTIVE
        ) {
            return finish(
                Decision::DENY,
                401,
                "Account is not active."
            );
        }

        const TokenStatus tokenStatus = tokens.validate(
            request.tokenId,
            request.userId
        );

        if (tokenStatus != TokenStatus::VALID) {
            return finish(
                Decision::DENY,
                401,
                "Token is invalid, expired, or revoked."
            );
        }

        // Resolve endpoint policy separately from authentication.
        std::string requiredPermission;

        if (request.path == "/api/users") {
            if (request.method == HTTPMethod::GET) {
                requiredPermission = "users:read";
            } else if (request.method == HTTPMethod::POST) {
                requiredPermission = "users:create";
            } else if (request.method == HTTPMethod::DELETE) {
                requiredPermission = "users:delete";
            }
        } else if (request.path == "/api/admin") {
            requiredPermission = "system:manage";
        } else if (request.path == "/api/reports") {
            requiredPermission = "reports:read";
        } else if (request.path == "/api/resources") {
            requiredPermission = "resources:read";
        }

        if (requiredPermission.empty()) {
            return finish(
                Decision::DENY,
                404,
                "Unknown endpoint or unsupported method."
            );
        }

        if (
            !permissionRegistry.hasPermission(
                *user,
                requiredPermission
            )
        ) {
            return finish(
                Decision::DENY,
                403,
                "Required permission not granted."
            );
        }

        // Resource-level authorization is distinct from RBAC.
        if (request.path == "/api/resources") {
            const Resource* resource = resources.find(
                request.resourceId
            );

            if (!resource) {
                return finish(
                    Decision::DENY,
                    404,
                    "Resource does not exist."
                );
            }

            if (
                policy.enforceOwnership &&
                resource->ownerId != user->id &&
                !permissionRegistry.hasPermission(
                    *user,
                    "system:manage"
                )
            ) {
                return finish(
                    Decision::DENY,
                    403,
                    "Resource ownership policy denied access."
                );
            }
        }

        return finish(
            Decision::ALLOW,
            200,
            "All security policies satisfied."
        );
    }

    const AuditService& getAudit() const {
        return audit;
    }

    void printState() const {
        std::cout
            << "\nRepository-independent API security engine"
            << "\nUsers: " << users.size()
            << "\nResources: " << resources.size()
            << '\n';
    }
};

// ---------------------------------------------------------
// Demonstration
// ---------------------------------------------------------

int main() {
    try {
        SecurityPolicy policy;

        policy.requestsPerWindow = 10;
        policy.windowSeconds = 60;
        policy.maximumBodySize = 16384;

        SecureAPIEngine engine(policy);

        User admin{
            "U001",
            "administrator",
            {Role::ADMIN},
            AccountStatus::ACTIVE
        };

        User editor{
            "U002",
            "content_editor",
            {Role::EDITOR},
            AccountStatus::ACTIVE
        };

        User viewer{
            "U003",
            "analyst",
            {Role::VIEWER},
            AccountStatus::ACTIVE
        };

        engine.registerUser(admin);
        engine.registerUser(editor);
        engine.registerUser(viewer);

        const long long now = currentTimestamp();

        engine.registerToken({
            "T_ADMIN",
            "U001",
            now,
            now + 900
        });

        engine.registerToken({
            "T_EDITOR",
            "U002",
            now,
            now + 900
        });

        engine.registerToken({
            "T_VIEWER",
            "U003",
            now,
            now + 900
        });

        engine.registerResource({
            "DOC001",
            "U002",
            "Confidential project document"
        });

        std::vector<APIRequest> requests = {
            {
                HTTPMethod::GET,
                "/api/admin",
                "U001",
                "T_ADMIN",
                "client-admin",
                "",
                128
            },
            {
                HTTPMethod::GET,
                "/api/admin",
                "U003",
                "T_VIEWER",
                "client-viewer",
                "",
                128
            },
            {
                HTTPMethod::GET,
                "/api/users",
                "U002",
                "T_EDITOR",
                "client-editor",
                "",
                128
            },
            {
                HTTPMethod::GET,
                "/api/resources",
                "U002",
                "T_EDITOR",
                "client-editor",
                "DOC001",
                128
            },
            {
                HTTPMethod::GET,
                "/api/resources",
                "U003",
                "T_VIEWER",
                "client-viewer",
                "DOC001",
                128
            },
            {
                HTTPMethod::GET,
                "/api/admin",
                "U003",
                "INVALID_TOKEN",
                "client-invalid",
                "",
                128
            },
            {
                HTTPMethod::GET,
                "/api/admin",
                "U001",
                "T_ADMIN",
                "client-large",
                "",
                20000
            }
        };

        std::cout << "SECURE API POLICY EVALUATION\n\n";

        int allowed = 0;
        int denied = 0;

        for (const auto& request : requests) {
            SecurityResult result = engine.evaluate(request);

            std::cout
                << std::left
                << std::setw(22) << request.path
                << std::setw(16) << request.userId
                << std::setw(10) << decisionName(result.decision)
                << "HTTP " << result.statusCode
                << " | " << result.reason
                << '\n';

            if (result.decision == Decision::ALLOW) {
                ++allowed;
            } else {
                ++denied;
            }
        }

        engine.printState();
        engine.getAudit().print();

        std::cout
            << "\nAllowed requests: " << allowed
            << "\nDenied requests: " << denied
            << "\nAudit events: "
            << engine.getAudit().count(Decision::ALLOW)
            + engine.getAudit().count(Decision::DENY)
            << '\n';

        if (allowed != 3 || denied != 4) {
            throw std::runtime_error(
                "Unexpected security evaluation results."
            );
        }

        std::cout << "\nAll policy evaluation tests passed.\n";

    } catch (const std::exception& error) {
        std::cerr
            << "Application failure: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
