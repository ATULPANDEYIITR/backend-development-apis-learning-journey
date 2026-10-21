#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

enum class AccountStatus {
    Active,
    Locked,
    Disabled
};

enum class SessionStatus {
    Active,
    Revoked,
    Expired
};

struct Credential {
    std::string salt;
    std::string verifier;
    std::uint32_t iterations;
};

struct User {
    int id;
    std::string username;
    Credential credential;
    std::unordered_set<std::string> roles;
    AccountStatus status;
    int failedAttempts;
};

struct Session {
    std::string id;
    int userId;
    std::chrono::system_clock::time_point createdAt;
    std::chrono::system_clock::time_point expiresAt;
    SessionStatus status;
};

class AuthenticationException : public std::runtime_error {
public:
    explicit AuthenticationException(const std::string& message)
        : std::runtime_error(message) {}
};

class AuthorizationException : public std::runtime_error {
public:
    explicit AuthorizationException(const std::string& message)
        : std::runtime_error(message) {}
};

class Repository {
private:
    std::unordered_map<std::string, User> users_;
    std::unordered_map<std::string, Session> sessions_;
    int nextUserId_ = 1;

    static std::string randomHex(std::size_t bytes) {
        std::random_device device;
        std::mt19937 generator(device());
        std::uniform_int_distribution<int> distribution(0, 255);

        std::ostringstream output;
        output << std::hex << std::setfill('0');

        for (std::size_t i = 0; i < bytes; ++i) {
            output << std::setw(2) << distribution(generator);
        }

        return output.str();
    }

    // This is a deterministic demonstration verifier, not a production
    // password hashing implementation. Production systems should use a
    // vetted password KDF such as Argon2id, scrypt, or PBKDF2.
    static std::string demoKdf(
        const std::string& password,
        const std::string& salt,
        std::uint32_t iterations
    ) {
        std::uint64_t state = 1469598103934665603ULL;

        auto mix = [&state](unsigned char value) {
            state ^= value;
            state *= 1099511628211ULL;
        };

        for (std::uint32_t round = 0; round < iterations / 1000 + 1; ++round) {
            for (unsigned char value : password) {
                mix(value);
            }

            for (unsigned char value : salt) {
                mix(value);
            }
        }

        std::ostringstream output;
        output << std::hex << state;
        return output.str();
    }

    static bool constantTimeEqual(
        const std::string& left,
        const std::string& right
    ) {
        std::size_t difference = left.size() ^ right.size();
        const std::size_t common = std::min(left.size(), right.size());

        for (std::size_t i = 0; i < common; ++i) {
            difference |=
                static_cast<unsigned char>(left[i]) ^
                static_cast<unsigned char>(right[i]);
        }

        return difference == 0;
    }

    User& findUserById(int userId) {
        for (auto& [username, user] : users_) {
            if (user.id == userId) {
                return user;
            }
        }

        throw AuthenticationException("Session references an unknown identity.");
    }

public:
    User& registerUser(
        const std::string& username,
        const std::string& password,
        const std::unordered_set<std::string>& roles
    ) {
        if (username.empty()) {
            throw std::invalid_argument("Username cannot be empty.");
        }

        if (password.size() < 12) {
            throw std::invalid_argument(
                "Password must contain at least 12 characters."
            );
        }

        if (users_.contains(username)) {
            throw std::invalid_argument("Username already exists.");
        }

        Credential credential;
        credential.salt = randomHex(16);
        credential.iterations = 210000;
        credential.verifier =
            demoKdf(password, credential.salt, credential.iterations);

        User user{
            nextUserId_++,
            username,
            credential,
            roles,
            AccountStatus::Active,
            0
        };

        auto [iterator, inserted] = users_.emplace(username, std::move(user));

        if (!inserted) {
            throw std::runtime_error("Identity creation failed.");
        }

        return iterator->second;
    }

    Session authenticate(
        const std::string& username,
        const std::string& password
    ) {
        auto iterator = users_.find(username);

        if (iterator == users_.end()) {
            throw AuthenticationException("Invalid credentials.");
        }

        User& user = iterator->second;

        if (user.status != AccountStatus::Active) {
            throw AuthenticationException("Account is not active.");
        }

        const std::string candidate =
            demoKdf(
                password,
                user.credential.salt,
                user.credential.iterations
            );

        if (!constantTimeEqual(candidate, user.credential.verifier)) {
            ++user.failedAttempts;

            if (user.failedAttempts >= 5) {
                user.status = AccountStatus::Locked;
            }

            throw AuthenticationException("Invalid credentials.");
        }

        user.failedAttempts = 0;

        const auto now = std::chrono::system_clock::now();

        Session session{
            randomHex(32),
            user.id,
            now,
            now + std::chrono::minutes(30),
            SessionStatus::Active
        };

        sessions_.emplace(session.id, session);
        return session;
    }

    User& authenticateSession(const std::string& sessionId) {
        auto iterator = sessions_.find(sessionId);

        if (iterator == sessions_.end()) {
            throw AuthenticationException("Unknown session.");
        }

        Session& session = iterator->second;

        if (session.status != SessionStatus::Active) {
            throw AuthenticationException("Session is not active.");
        }

        if (std::chrono::system_clock::now() >= session.expiresAt) {
            session.status = SessionStatus::Expired;
            throw AuthenticationException("Session has expired.");
        }

        User& user = findUserById(session.userId);

        if (user.status != AccountStatus::Active) {
            throw AuthenticationException("Identity is not active.");
        }

        return user;
    }

    User& authorize(
        const std::string& sessionId,
        const std::string& requiredRole
    ) {
        User& user = authenticateSession(sessionId);

        if (!user.roles.contains(requiredRole)) {
            throw AuthorizationException(
                "Identity lacks required role: " + requiredRole
            );
        }

        return user;
    }

    void revokeSession(const std::string& sessionId) {
        auto iterator = sessions_.find(sessionId);

        if (iterator != sessions_.end()) {
            iterator->second.status = SessionStatus::Revoked;
        }
    }
};

static void showAuthenticationFlow(Repository& repository) {
    std::cout << "=== Authentication and Identity ===\n";

    User& alice = repository.registerUser(
        "alice",
        "CorrectHorseBattery9!",
        {"user"}
    );

    Session session = repository.authenticate(
        alice.username,
        "CorrectHorseBattery9!"
    );

    User& authenticated = repository.authenticateSession(session.id);

    std::cout
        << "Authenticated identity: "
        << authenticated.username
        << '\n';

    std::cout
        << "Session identifier prefix: "
        << session.id.substr(0, 12)
        << "...\n";

    std::cout << "\n=== Authorization ===\n";

    try {
        repository.authorize(session.id, "administrator");
    } catch (const AuthorizationException& exception) {
        std::cout
            << "Access denied: "
            << exception.what()
            << '\n';
    }

    authenticated.roles.insert("administrator");

    User& authorized =
        repository.authorize(session.id, "administrator");

    std::cout
        << "Administrator access granted to "
        << authorized.username
        << '\n';

    repository.revokeSession(session.id);

    try {
        repository.authenticateSession(session.id);
    } catch (const AuthenticationException& exception) {
        std::cout
            << "Revoked session rejected: "
            << exception.what()
            << '\n';
    }
}

static void showLockout(Repository& repository) {
    std::cout << "\n=== Account Lockout ===\n";

    repository.registerUser(
        "locked-user",
        "VeryStrongPassword9!",
        {"user"}
    );

    for (int attempt = 1; attempt <= 5; ++attempt) {
        try {
            repository.authenticate(
                "locked-user",
                "wrong-password"
            );
        } catch (const AuthenticationException& exception) {
            std::cout
                << "Attempt "
                << attempt
                << ": "
                << exception.what()
                << '\n';
        }
    }
}

int main() {
    try {
        Repository repository;

        showAuthenticationFlow(repository);
        showLockout(repository);

        std::cout
            << "\nThe system separates identity, authentication, "
               "session state, and authorization decisions.\n";

    } catch (const std::exception& exception) {
        std::cerr
            << "Fatal error: "
            << exception.what()
            << '\n';

        return 1;
    }

    return 0;
}
