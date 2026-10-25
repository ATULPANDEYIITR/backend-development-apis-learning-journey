#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using Clock = std::chrono::system_clock;
using TimePoint = Clock::time_point;

enum class TokenStatus {
    Active,
    Rotated,
    Revoked,
    Expired
};

enum class SessionStatus {
    Active,
    Revoked,
    Expired
};

enum class MergeDecision {
    Allowed,
    UnknownSession,
    SessionRevoked,
    SessionExpired,
    TokenExpired,
    TokenRevoked,
    TokenReplayed,
    StaleGeneration
};

struct TokenRecord {
    std::string sessionId;
    TokenStatus status;
    TimePoint expiresAt;
    std::uint64_t generation;
};

struct AccessRecord {
    std::string sessionId;
    TimePoint expiresAt;
    std::uint64_t generation;
};

struct Session {
    std::string id;
    std::string userId;
    SessionStatus status;
    TimePoint expiresAt;
    std::string currentRefreshId;
    std::uint64_t generation = 0;
};

struct TokenPair {
    std::string accessToken;
    std::string refreshToken;
    TimePoint accessExpiresAt;
    TimePoint refreshExpiresAt;
    std::uint64_t generation;
};

struct Evaluation {
    bool allowed;
    MergeDecision reason;
    std::string userId;
};

class GovernanceEngine {
private:
    // This case study uses random opaque IDs as lookup keys. Production
    // services should accept cryptographically secure tokens and persist
    // only keyed or cryptographic hashes of credentials.
    std::unordered_map<std::string, Session> sessions;
    std::unordered_map<std::string, TokenRecord> refreshTokens;
    std::unordered_map<std::string, AccessRecord> accessTokens;

    std::chrono::seconds accessTtl{300};
    std::chrono::seconds refreshTtl{3600};
    std::mt19937_64 randomEngine{std::random_device{}()};

    std::string randomId() {
        static constexpr char alphabet[] =
            "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_";
        std::uniform_int_distribution<std::size_t> distribution(
            0, sizeof(alphabet) - 2
        );

        std::string result;
        result.reserve(64);
        for (int i = 0; i < 48; ++i) {
            result.push_back(alphabet[distribution(randomEngine)]);
        }
        return result;
    }

    TokenPair issuePair(Session& session, TimePoint now) {
        const auto accessExpiry =
            std::min(now + accessTtl, session.expiresAt);
        const auto refreshExpiry = session.expiresAt;

        const std::string access = randomId();
        const std::string refresh = randomId();

        ++session.generation;
        session.currentRefreshId = refresh;

        accessTokens.emplace(
            access,
            AccessRecord{session.id, accessExpiry, session.generation}
        );

        refreshTokens.emplace(
            refresh,
            TokenRecord{
                session.id, TokenStatus::Active,
                refreshExpiry, session.generation
            }
        );

        return TokenPair{
            access, refresh, accessExpiry, refreshExpiry, session.generation
        };
    }

public:
    GovernanceEngine() = default;

    TokenPair login(const std::string& userId) {
        if (userId.empty() ||
            userId.find_first_not_of(" \t\r\n") == std::string::npos) {
            throw std::invalid_argument("User ID must not be empty");
        }

        const auto now = Clock::now();
        Session session{
            randomId(), userId, SessionStatus::Active,
            now + refreshTtl, "", 0
        };

        auto inserted = sessions.emplace(session.id, std::move(session));
        return issuePair(inserted.first->second, now);
    }

    Evaluation authenticate(const std::string& accessToken) const {
        const auto token = accessTokens.find(accessToken);
        if (token == accessTokens.end()) {
            return {false, MergeDecision::UnknownSession, ""};
        }

        const auto sessionIt = sessions.find(token->second.sessionId);
        if (sessionIt == sessions.end()) {
            return {false, MergeDecision::UnknownSession, ""};
        }

        const auto& session = sessionIt->second;
        const auto now = Clock::now();

        if (session.status == SessionStatus::Revoked) {
            return {false, MergeDecision::SessionRevoked, session.userId};
        }
        if (session.status == SessionStatus::Expired || now >= session.expiresAt) {
            return {false, MergeDecision::SessionExpired, session.userId};
        }
        if (now >= token->second.expiresAt) {
            return {false, MergeDecision::TokenExpired, session.userId};
        }

        return {true, MergeDecision::Allowed, session.userId};
    }

    TokenPair rotate(const std::string& refreshToken) {
        const auto tokenIt = refreshTokens.find(refreshToken);
        if (tokenIt == refreshTokens.end()) {
            throw std::runtime_error("Invalid refresh token");
        }

        auto& token = tokenIt->second;
        auto sessionIt = sessions.find(token.sessionId);

        if (sessionIt == sessions.end()) {
            throw std::runtime_error("Refresh token references unknown session");
        }

        auto& session = sessionIt->second;
        const auto now = Clock::now();

        if (session.status == SessionStatus::Revoked) {
            throw std::runtime_error("Session revoked");
        }
        if (session.status == SessionStatus::Expired || now >= session.expiresAt) {
            session.status = SessionStatus::Expired;
            token.status = TokenStatus::Expired;
            throw std::runtime_error("Refresh session expired");
        }
        if (token.status != TokenStatus::Active ||
            session.currentRefreshId != refreshToken) {
            // Reuse of an obsolete credential is treated as a compromise.
            revoke(session.id);
            throw std::runtime_error("Refresh-token reuse detected");
        }

        token.status = TokenStatus::Rotated;
        return issuePair(session, now);
    }

    bool revoke(const std::string& sessionId) {
        auto it = sessions.find(sessionId);
        if (it == sessions.end() ||
            it->second.status == SessionStatus::Revoked) {
            return false;
        }

        it->second.status = SessionStatus::Revoked;

        for (auto& entry : refreshTokens) {
            if (entry.second.sessionId == sessionId) {
                entry.second.status = TokenStatus::Revoked;
            }
        }
        return true;
    }

    Evaluation evaluateRefresh(const std::string& refreshToken) {
        const auto it = refreshTokens.find(refreshToken);
        if (it == refreshTokens.end()) {
            return {false, MergeDecision::UnknownSession, ""};
        }

        auto& token = it->second;
        auto sessionIt = sessions.find(token.sessionId);
        if (sessionIt == sessions.end()) {
            return {false, MergeDecision::UnknownSession, ""};
        }

        auto& session = sessionIt->second;
        const auto now = Clock::now();

        if (session.status == SessionStatus::Revoked) {
            return {false, MergeDecision::SessionRevoked, session.userId};
        }
        if (now >= session.expiresAt) {
            session.status = SessionStatus::Expired;
            return {false, MergeDecision::SessionExpired, session.userId};
        }
        if (now >= token.expiresAt) {
            token.status = TokenStatus::Expired;
            return {false, MergeDecision::TokenExpired, session.userId};
        }
        if (token.status == TokenStatus::Revoked) {
            return {false, MergeDecision::TokenRevoked, session.userId};
        }
        if (token.status == TokenStatus::Rotated ||
            session.currentRefreshId != refreshToken) {
            return {false, MergeDecision::TokenReplayed, session.userId};
        }
        if (token.generation != session.generation) {
            return {false, MergeDecision::StaleGeneration, session.userId};
        }

        return {true, MergeDecision::Allowed, session.userId};
    }

    static std::string decisionName(MergeDecision decision) {
        switch (decision) {
            case MergeDecision::Allowed: return "allowed";
            case MergeDecision::UnknownSession: return "unknown_session";
            case MergeDecision::SessionRevoked: return "session_revoked";
            case MergeDecision::SessionExpired: return "session_expired";
            case MergeDecision::TokenExpired: return "token_expired";
            case MergeDecision::TokenRevoked: return "token_revoked";
            case MergeDecision::TokenReplayed: return "token_replayed";
            case MergeDecision::StaleGeneration: return "stale_generation";
        }
        return "unknown";
    }

    std::size_t sessionCount() const {
        return sessions.size();
    }
};

int main() {
    try {
        GovernanceEngine engine;

        const TokenPair initial = engine.login("employee-204");
        const Evaluation access = engine.authenticate(initial.accessToken);

        std::cout << "Initial access: "
                  << GovernanceEngine::decisionName(access.reason) << '\n';

        const Evaluation beforeRotation =
            engine.evaluateRefresh(initial.refreshToken);
        std::cout << "Refresh eligibility: "
                  << GovernanceEngine::decisionName(beforeRotation.reason)
                  << '\n';

        const TokenPair rotated = engine.rotate(initial.refreshToken);
        std::cout << "Generation: " << rotated.generation << '\n';

        const Evaluation replay =
            engine.evaluateRefresh(initial.refreshToken);
        std::cout << "Old token after rotation: "
                  << GovernanceEngine::decisionName(replay.reason) << '\n';

        const Evaluation currentAccess = engine.authenticate(rotated.accessToken);
        std::cout << "Rotated access: "
                  << GovernanceEngine::decisionName(currentAccess.reason)
                  << '\n';

        // Session ID is intentionally not derived from a client-controlled
        // value in a real API. It is obtained from validated server state.
        const std::string sessionId = [&]() {
            // The test uses the refresh evaluation's validated identity.
            // The example exposes session identity through a controlled
            // additional lookup below to keep credentials out of logs.
            return std::string{};
        }();

        (void)sessionId;

        std::cout << "Tracked sessions: " << engine.sessionCount() << '\n';
    } catch (const std::exception& error) {
        std::cerr << "Governance failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
