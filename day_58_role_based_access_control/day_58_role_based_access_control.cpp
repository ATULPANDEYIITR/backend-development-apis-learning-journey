#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

enum class Role {
    User,
    Support,
    Manager,
    Admin
};

enum class Action {
    Read,
    Create,
    Update,
    Delete,
    Approve,
    Admin
};

enum class Decision {
    Allow,
    Deny
};

enum class Sensitivity {
    Normal,
    High,
    Critical
};

struct Permission {
    std::string resource;
    Action action;

    bool operator<(const Permission& other) const {
        if (resource != other.resource) {
            return resource < other.resource;
        }
        return static_cast<int>(action) < static_cast<int>(other.action);
    }

    bool operator==(const Permission& other) const {
        return resource == other.resource && action == other.action;
    }
};

struct Resource {
    std::string id;
    std::string type;
    std::string ownerId;
    Sensitivity sensitivity{Sensitivity::Normal};
};

struct User {
    std::string id;
    std::string username;
    std::set<Role> roles;
    bool active{true};
};

struct AuthorizationRequest {
    std::string userId;
    Action action;
    Resource resource;
};

struct AuthorizationResult {
    Decision decision;
    std::string reason;
    std::vector<std::string> matchedPermissions;
};

struct AuditEvent {
    std::string userId;
    std::string event;
    std::string detail;
};

std::string toString(Role role) {
    switch (role) {
        case Role::User: return "user";
        case Role::Support: return "support";
        case Role::Manager: return "manager";
        case Role::Admin: return "admin";
    }
    return "unknown";
}

std::string toString(Action action) {
    switch (action) {
        case Action::Read: return "read";
        case Action::Create: return "create";
        case Action::Update: return "update";
        case Action::Delete: return "delete";
        case Action::Approve: return "approve";
        case Action::Admin: return "admin";
    }
    return "unknown";
}

std::string toString(Decision decision) {
    return decision == Decision::Allow ? "ALLOW" : "DENY";
}

std::string permissionKey(const Permission& permission) {
    return permission.resource + ":" + toString(permission.action);
}

class RBACException : public std::runtime_error {
public:
    explicit RBACException(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationException : public RBACException {
public:
    explicit ValidationException(const std::string& message)
        : RBACException(message) {}
};

class AuthorizationException : public RBACException {
public:
    explicit AuthorizationException(const std::string& message)
        : RBACException(message) {}
};

class RBACEngine {
private:
    std::map<Role, std::set<Permission>> rolePermissions;
    std::map<std::string, User> users;
    std::vector<AuditEvent> auditEvents;

    User& requireUser(const std::string& userId) {
        auto it = users.find(userId);
        if (it == users.end()) {
            throw ValidationException("Unknown user: " + userId);
        }
        return it->second;
    }

    static bool ownershipPolicyApplies(
        const User& user,
        const AuthorizationRequest& request
    ) {
        return request.resource.ownerId == user.id &&
               (request.action == Action::Read ||
                request.action == Action::Update) &&
               (request.resource.type == "profile" ||
                request.resource.type == "document");
    }

    AuthorizationResult finish(
        const AuthorizationRequest& request,
        Decision decision,
        const std::string& reason,
        std::vector<std::string> matched
    ) {
        auditEvents.push_back({
            request.userId,
            "authorization",
            toString(request.action) + ":" +
                request.resource.type + ":" +
                toString(decision) + ":" +
                reason
        });

        return {decision, reason, std::move(matched)};
    }

public:
    void grant(Role role, const Permission& permission) {
        rolePermissions[role].insert(permission);
    }

    void addUser(const User& user) {
        if (user.id.empty() || user.username.empty()) {
            throw ValidationException("User identity is incomplete");
        }

        if (users.contains(user.id)) {
            throw ValidationException("Duplicate user: " + user.id);
        }

        for (Role role : user.roles) {
            if (!rolePermissions.contains(role)) {
                throw ValidationException(
                    "User contains an unknown role: " + toString(role)
                );
            }
        }

        users.emplace(user.id, user);
    }

    void assignRole(const std::string& userId, Role role) {
        User& user = requireUser(userId);

        if (!rolePermissions.contains(role)) {
            throw ValidationException("Unknown role");
        }

        user.roles.insert(role);

        auditEvents.push_back({
            userId,
            "role-assignment",
            "assigned=" + toString(role)
        });
    }

    void revokeRole(const std::string& userId, Role role) {
        User& user = requireUser(userId);
        user.roles.erase(role);

        auditEvents.push_back({
            userId,
            "role-revocation",
            "revoked=" + toString(role)
        });
    }

    AuthorizationResult authorize(
        const AuthorizationRequest& request
    ) {
        User& user = requireUser(request.userId);

        if (request.resource.id.empty() ||
            request.resource.type.empty()) {
            throw ValidationException("Resource identity is incomplete");
        }

        if (!user.active) {
            return finish(
                request,
                Decision::Deny,
                "User account is inactive",
                {}
            );
        }

        if (request.action == Action::Admin &&
            !user.roles.contains(Role::Admin)) {
            return finish(
                request,
                Decision::Deny,
                "Administrative action requires admin role",
                {}
            );
        }

        Permission requested{
            request.resource.type,
            request.action
        };

        std::vector<std::string> matches;

        for (Role role : user.roles) {
            const auto roleIt = rolePermissions.find(role);
            if (roleIt == rolePermissions.end()) {
                continue;
            }

            if (roleIt->second.contains(requested)) {
                matches.push_back(
                    toString(role) + ":" + permissionKey(requested)
                );
            }
        }

        if (!matches.empty()) {
            std::sort(matches.begin(), matches.end());

            return finish(
                request,
                Decision::Allow,
                "Explicit role permission matched",
                std::move(matches)
            );
        }

        if (ownershipPolicyApplies(user, request)) {
            return finish(
                request,
                Decision::Allow,
                "Ownership policy matched",
                {"ownership-policy"}
            );
        }

        return finish(
            request,
            Decision::Deny,
            "No applicable role permission or ownership policy",
            {}
        );
    }

    std::set<Permission> effectivePermissions(
        const std::string& userId
    ) {
        User& user = requireUser(userId);
        std::set<Permission> result;

        for (Role role : user.roles) {
            const auto roleIt = rolePermissions.find(role);
            if (roleIt == rolePermissions.end()) {
                continue;
            }

            result.insert(
                roleIt->second.begin(),
                roleIt->second.end()
            );
        }

        return result;
    }

    void setActive(const std::string& userId, bool active) {
        requireUser(userId).active = active;
    }

    const std::vector<AuditEvent>& auditLog() const {
        return auditEvents;
    }
};

void printResult(
    const AuthorizationRequest& request,
    const AuthorizationResult& result
) {
    std::cout
        << std::left
        << std::setw(4) << request.userId
        << std::setw(9) << toString(request.action)
        << std::setw(10) << request.resource.type
        << " -> "
        << std::setw(5) << toString(result.decision)
        << " | "
        << result.reason
        << '\n';
}

void runTests(RBACEngine& engine) {
    Resource profile{"p-test", "profile", "u1"};
    Resource ticket{"t-test", "ticket", "u2"};
    Resource system{"s-test", "system", "u4", Sensitivity::Critical};

    auto result1 = engine.authorize(
        {"u1", Action::Update, profile}
    );
    if (result1.decision != Decision::Allow) {
        throw std::runtime_error("User ownership test failed");
    }

    auto result2 = engine.authorize(
        {"u1", Action::Update, ticket}
    );
    if (result2.decision != Decision::Deny) {
        throw std::runtime_error("Unauthorized ticket update was allowed");
    }

    auto result3 = engine.authorize(
        {"u2", Action::Update, ticket}
    );
    if (result3.decision != Decision::Allow) {
        throw std::runtime_error("Support permission test failed");
    }

    auto result4 = engine.authorize(
        {"u2", Action::Admin, system}
    );
    if (result4.decision != Decision::Deny) {
        throw std::runtime_error("Administrative escalation was allowed");
    }

    auto result5 = engine.authorize(
        {"u4", Action::Admin, system}
    );
    if (result5.decision != Decision::Allow) {
        throw std::runtime_error("Admin permission test failed");
    }

    engine.setActive("u1", false);

    auto result6 = engine.authorize(
        {"u1", Action::Read, profile}
    );
    if (result6.decision != Decision::Deny) {
        throw std::runtime_error("Inactive user was allowed");
    }

    engine.setActive("u1", true);
}

RBACEngine buildEngine() {
    RBACEngine engine;

    engine.grant(Role::User, {"profile", Action::Read});
    engine.grant(Role::User, {"profile", Action::Update});

    engine.grant(Role::Support, {"profile", Action::Read});
    engine.grant(Role::Support, {"ticket", Action::Read});
    engine.grant(Role::Support, {"ticket", Action::Update});

    engine.grant(Role::Manager, {"profile", Action::Read});
    engine.grant(Role::Manager, {"ticket", Action::Read});
    engine.grant(Role::Manager, {"ticket", Action::Update});
    engine.grant(Role::Manager, {"ticket", Action::Approve});
    engine.grant(Role::Manager, {"report", Action::Read});

    engine.grant(Role::Admin, {"profile", Action::Read});
    engine.grant(Role::Admin, {"profile", Action::Update});
    engine.grant(Role::Admin, {"ticket", Action::Read});
    engine.grant(Role::Admin, {"ticket", Action::Update});
    engine.grant(Role::Admin, {"ticket", Action::Approve});
    engine.grant(Role::Admin, {"report", Action::Read});
    engine.grant(Role::Admin, {"system", Action::Admin});

    engine.addUser({
        "u1",
        "alice",
        {Role::User},
        true
    });

    engine.addUser({
        "u2",
        "bob",
        {Role::Support},
        true
    });

    engine.addUser({
        "u3",
        "carol",
        {Role::Manager},
        true
    });

    engine.addUser({
        "u4",
        "david",
        {Role::Admin},
        true
    });

    return engine;
}

int main() {
    try {
        RBACEngine engine = buildEngine();

        runTests(engine);

        Resource aliceProfile{
            "p-100",
            "profile",
            "u1"
        };

        Resource supportTicket{
            "t-200",
            "ticket",
            "u2"
        };

        Resource report{
            "r-300",
            "report",
            "u3",
            Sensitivity::High
        };

        Resource systemConfig{
            "s-400",
            "system",
            "u4",
            Sensitivity::Critical
        };

        std::vector<AuthorizationRequest> requests{
            {"u1", Action::Update, aliceProfile},
            {"u1", Action::Update, supportTicket},
            {"u2", Action::Update, supportTicket},
            {"u3", Action::Approve, supportTicket},
            {"u3", Action::Read, report},
            {"u2", Action::Admin, systemConfig},
            {"u4", Action::Admin, systemConfig}
        };

        for (const auto& request : requests) {
            printResult(
                request,
                engine.authorize(request)
            );
        }

        std::cout << "\nEffective permissions for carol:\n";

        for (const auto& permission :
             engine.effectivePermissions("u3")) {
            std::cout << "  "
                      << permissionKey(permission)
                      << '\n';
        }

        std::cout << "\nAudit events: "
                  << engine.auditLog().size()
                  << '\n';

        for (const auto& event : engine.auditLog()) {
            std::cout
                << "  "
                << event.userId
                << " | "
                << event.event
                << " | "
                << event.detail
                << '\n';
        }

        std::cout << "\nAll RBAC tests passed.\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "Fatal error: " << ex.what() << '\n';
        return 1;
    }
}
