#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace security {

using Clock = std::chrono::system_clock;
using TimePoint = Clock::time_point;

constexpr std::size_t DIGEST_SIZE = 32;
constexpr auto MAX_LIFETIME = std::chrono::hours(24 * 365);

enum class KeyStatus {
    Active,
    Revoked
};

enum class Decision {
    Accepted,
    MalformedToken,
    InvalidCredentials,
    Revoked,
    Expired,
    InsufficientScope
};

struct IssuedKey {
    std::string keyId;
    std::string token;

    // Prevent accidental disclosure through ordinary stream output.
    friend std::ostream& operator<<(std::ostream& out, const IssuedKey& key) {
        return out << "IssuedKey{keyId=" << key.keyId
                   << ", token=<redacted>}";
    }
};

struct ValidationResult {
    Decision decision;
    std::string keyId;
    std::string owner;

    bool accepted() const {
        return decision == Decision::Accepted;
    }
};

struct KeyMetadata {
    std::string keyId;
    std::string owner;
    std::string label;
    KeyStatus status;
    std::set<std::string> scopes;
    TimePoint createdAt;
    std::optional<TimePoint> expiresAt;
    std::optional<TimePoint> lastUsedAt;
    std::optional<TimePoint> revokedAt;
    std::optional<std::string> rotatedFrom;
};

struct AuditEvent {
    std::string eventType;
    std::string keyId;
    std::string actor;
    TimePoint occurredAt;
    std::string relatedKeyId;
};

/*
 * OpenSSL supplies cryptographically secure random bytes and HMAC.
 * The program does not invent a custom digest algorithm.
 */
class Cryptography {
public:
    static std::vector<unsigned char> randomBytes(std::size_t count) {
        if (count == 0 || count > 4096) {
            throw std::invalid_argument("Invalid random byte count.");
        }

        std::vector<unsigned char> output(count);

        if (RAND_bytes(output.data(), static_cast<int>(count)) != 1) {
            throw std::runtime_error("OpenSSL secure random generation failed.");
        }

        return output;
    }

    static std::string toHex(const std::vector<unsigned char>& bytes) {
        std::ostringstream output;
        output << std::hex << std::setfill('0');

        for (unsigned char byte : bytes) {
            output << std::setw(2) << static_cast<unsigned int>(byte);
        }

        return output.str();
    }

    static std::array<unsigned char, DIGEST_SIZE> hmacSha256(
        const std::string& pepper,
        const std::string& secret
    ) {
        std::array<unsigned char, DIGEST_SIZE> digest{};
        unsigned int digestLength = 0;

        unsigned char* result = HMAC(
            EVP_sha256(),
            pepper.data(),
            static_cast<int>(pepper.size()),
            reinterpret_cast<const unsigned char*>(secret.data()),
            secret.size(),
            digest.data(),
            &digestLength
        );

        if (result == nullptr || digestLength != DIGEST_SIZE) {
            throw std::runtime_error("HMAC-SHA-256 calculation failed.");
        }

        return digest;
    }

    static bool constantTimeEqual(
        const std::array<unsigned char, DIGEST_SIZE>& left,
        const std::array<unsigned char, DIGEST_SIZE>& right
    ) {
        return CRYPTO_memcmp(left.data(), right.data(), DIGEST_SIZE) == 0;
    }
};

std::string formatTime(const TimePoint& point) {
    const std::time_t value = Clock::to_time_t(point);
    std::tm utc{};

#ifdef _WIN32
    gmtime_s(&utc, &value);
#else
    gmtime_r(&value, &utc);
#endif

    std::ostringstream output;
    output << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return output.str();
}

std::string decisionName(Decision decision) {
    switch (decision) {
        case Decision::Accepted: return "accepted";
        case Decision::MalformedToken: return "malformed_token";
        case Decision::InvalidCredentials: return "invalid_credentials";
        case Decision::Revoked: return "revoked";
        case Decision::Expired: return "expired";
        case Decision::InsufficientScope: return "insufficient_scope";
    }

    return "unknown";
}

class APIKeyVault {
private:
    struct KeyRecord {
        std::string keyId;
        std::string owner;
        std::string label;
        std::array<unsigned char, DIGEST_SIZE> verifier{};
        KeyStatus status = KeyStatus::Active;
        std::set<std::string> scopes;
        TimePoint createdAt;
        std::optional<TimePoint> expiresAt;
        std::optional<TimePoint> lastUsedAt;
        std::optional<TimePoint> revokedAt;
        std::optional<std::string> rotatedFrom;
    };

    struct ParsedToken {
        std::string keyId;
        std::string secret;
    };

    std::unordered_map<std::string, KeyRecord> records_;
    std::vector<AuditEvent> events_;
    std::string pepper_;
    mutable std::mutex mutex_;

    static bool validText(
        const std::string& value,
        std::size_t maximum = 120
    ) {
        return !value.empty() && value.size() <= maximum;
    }

    static bool validScope(const std::string& scope) {
        if (scope.empty() || scope.size() > 64 ||
            scope.front() < 'a' || scope.front() > 'z') {
            return false;
        }

        return std::all_of(
            scope.begin(),
            scope.end(),
            [](unsigned char character) {
                return (character >= 'a' && character <= 'z') ||
                       (character >= '0' && character <= '9') ||
                       character == ':' || character == '_' ||
                       character == '-';
            }
        );
    }

    static bool isHex(const std::string& value) {
        return std::all_of(
            value.begin(),
            value.end(),
            [](unsigned char character) {
                return (character >= '0' && character <= '9') ||
                       (character >= 'a' && character <= 'f');
            }
        );
    }

    static std::optional<ParsedToken> parseToken(const std::string& token) {
        const std::string prefix = "ak_live_";

        if (token.rfind(prefix, 0) != 0) {
            return std::nullopt;
        }

        const std::size_t separator = token.find('.', prefix.size());

        if (separator == std::string::npos) {
            return std::nullopt;
        }

        const std::string keyId = token.substr(
            prefix.size(),
            separator - prefix.size()
        );

        const std::string secret = token.substr(separator + 1);

        // This implementation represents 256-bit secrets as 64 hex characters.
        if (keyId.size() != 16 || !isHex(keyId) ||
            secret.size() != 64 || !isHex(secret)) {
            return std::nullopt;
        }

        return ParsedToken{keyId, secret};
    }

    void validateScopes(const std::set<std::string>& scopes) const {
        if (scopes.empty()) {
            throw std::invalid_argument("At least one scope is required.");
        }

        for (const auto& scope : scopes) {
            if (!validScope(scope)) {
                throw std::invalid_argument("An API key scope is invalid.");
            }
        }
    }

    void recordEvent(
        const std::string& eventType,
        const KeyRecord& record,
        const std::string& actor,
        const std::string& relatedKeyId = ""
    ) {
        events_.push_back({
            eventType,
            record.keyId,
            actor,
            Clock::now(),
            relatedKeyId
        });
    }

    IssuedKey issueInternal(
        const std::string& owner,
        const std::string& label,
        const std::set<std::string>& scopes,
        std::optional<TimePoint> expiresAt,
        const std::string& actor,
        std::optional<std::string> rotatedFrom
    ) {
        const auto idBytes = Cryptography::randomBytes(8);
        const auto secretBytes = Cryptography::randomBytes(32);

        const std::string keyId = Cryptography::toHex(idBytes);
        const std::string secret = Cryptography::toHex(secretBytes);
        const std::string token = "ak_live_" + keyId + "." + secret;

        KeyRecord record;
        record.keyId = keyId;
        record.owner = owner;
        record.label = label;
        record.verifier = Cryptography::hmacSha256(pepper_, secret);
        record.status = KeyStatus::Active;
        record.scopes = scopes;
        record.createdAt = Clock::now();
        record.expiresAt = expiresAt;
        record.rotatedFrom = rotatedFrom;

        records_.emplace(keyId, std::move(record));
        recordEvent("issued", records_.at(keyId), actor);

        return IssuedKey{keyId, token};
    }

public:
    explicit APIKeyVault(std::optional<std::string> configuredPepper = std::nullopt) {
        if (configuredPepper.has_value()) {
            if (configuredPepper->size() < 32) {
                throw std::invalid_argument(
                    "The configured pepper must contain at least 32 bytes."
                );
            }

            pepper_ = *configuredPepper;
        } else {
            // A process-local pepper permits the standalone demonstration.
            // Persistent deployments must inject a stable secret-manager value.
            pepper_ = Cryptography::toHex(Cryptography::randomBytes(32));
        }
    }

    IssuedKey issue(
        const std::string& owner,
        const std::string& label,
        const std::set<std::string>& scopes,
        std::optional<std::chrono::seconds> lifetime,
        const std::string& actor
    ) {
        if (!validText(owner) || !validText(label) || !validText(actor)) {
            throw std::invalid_argument("Owner, label, and actor are required.");
        }

        validateScopes(scopes);

        std::optional<TimePoint> expiresAt;

        if (lifetime.has_value()) {
            if (lifetime->count() <= 0 ||
                *lifetime > MAX_LIFETIME) {
                throw std::invalid_argument(
                    "Lifetime must be positive and no greater than 365 days."
                );
            }

            expiresAt = Clock::now() + *lifetime;
        }

        std::lock_guard<std::mutex> lock(mutex_);

        return issueInternal(
            owner,
            label,
            scopes,
            expiresAt,
            actor,
            std::nullopt
        );
    }

    ValidationResult validate(
        const std::string& token,
        const std::string& requiredScope
    ) {
        if (!validScope(requiredScope)) {
            return {Decision::InsufficientScope, "", ""};
        }

        const auto parsed = parseToken(token);

        if (!parsed.has_value()) {
            return {Decision::MalformedToken, "", ""};
        }

        const auto candidate = Cryptography::hmacSha256(
            pepper_,
            parsed->secret
        );

        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = records_.find(parsed->keyId);

        if (iterator == records_.end()) {
            return {Decision::InvalidCredentials, parsed->keyId, ""};
        }

        KeyRecord& record = iterator->second;

        if (!Cryptography::constantTimeEqual(candidate, record.verifier)) {
            return {Decision::InvalidCredentials, parsed->keyId, ""};
        }

        if (record.status != KeyStatus::Active) {
            return {Decision::Revoked, record.keyId, record.owner};
        }

        const TimePoint now = Clock::now();

        if (record.expiresAt.has_value() && *record.expiresAt <= now) {
            return {Decision::Expired, record.keyId, record.owner};
        }

        if (!record.scopes.count(requiredScope) &&
            !record.scopes.count("*")) {
            return {Decision::InsufficientScope, record.keyId, record.owner};
        }

        record.lastUsedAt = now;

        return {Decision::Accepted, record.keyId, record.owner};
    }

    IssuedKey rotate(
        const std::string& oldToken,
        const std::string& actor,
        std::optional<std::chrono::seconds> replacementLifetime = std::nullopt
    ) {
        if (!validText(actor)) {
            throw std::invalid_argument("Actor is required.");
        }

        const auto parsed = parseToken(oldToken);

        if (!parsed.has_value()) {
            throw std::invalid_argument("The supplied token is malformed.");
        }

        const auto candidate = Cryptography::hmacSha256(
            pepper_,
            parsed->secret
        );

        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = records_.find(parsed->keyId);

        if (iterator == records_.end() ||
            !Cryptography::constantTimeEqual(
                candidate,
                iterator->second.verifier
            )) {
            throw std::runtime_error("The supplied key could not be authenticated.");
        }

        KeyRecord& oldRecord = iterator->second;

        if (oldRecord.status != KeyStatus::Active) {
            throw std::logic_error("Only an active key can be rotated.");
        }

        const TimePoint now = Clock::now();

        if (oldRecord.expiresAt.has_value() && *oldRecord.expiresAt <= now) {
            throw std::logic_error("An expired key cannot be rotated.");
        }

        std::optional<TimePoint> newExpiration;

        if (replacementLifetime.has_value()) {
            if (replacementLifetime->count() <= 0 ||
                *replacementLifetime > MAX_LIFETIME) {
                throw std::invalid_argument("Invalid replacement lifetime.");
            }

            newExpiration = now + *replacementLifetime;
        } else {
            // Without an explicit replacement lifetime, preserve the old expiry.
            newExpiration = oldRecord.expiresAt;
        }

        const std::string oldKeyId = oldRecord.keyId;
        const auto newScopes = oldRecord.scopes;
        const auto owner = oldRecord.owner;
        const auto label = oldRecord.label;

        IssuedKey replacement = issueInternal(
            owner,
            label,
            newScopes,
            newExpiration,
            actor,
            oldKeyId
        );

        // The mutex makes replacement creation and old-key revocation atomic
        // from the perspective of callers using this vault instance.
        oldRecord.status = KeyStatus::Revoked;
        oldRecord.revokedAt = now;

        recordEvent(
            "rotated",
            oldRecord,
            actor,
            replacement.keyId
        );

        return replacement;
    }

    bool revoke(const std::string& keyId, const std::string& actor) {
        if (!validText(keyId, 32) || !validText(actor)) {
            throw std::invalid_argument("A key ID and actor are required.");
        }

        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = records_.find(keyId);

        if (iterator == records_.end()) {
            throw std::out_of_range("The requested key does not exist.");
        }

        KeyRecord& record = iterator->second;

        if (record.status == KeyStatus::Revoked) {
            return false;
        }

        record.status = KeyStatus::Revoked;
        record.revokedAt = Clock::now();

        recordEvent("revoked", record, actor);

        return true;
    }

    KeyMetadata metadata(const std::string& keyId) const {
        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = records_.find(keyId);

        if (iterator == records_.end()) {
            throw std::out_of_range("The requested key does not exist.");
        }

        const KeyRecord& record = iterator->second;

        return {
            record.keyId,
            record.owner,
            record.label,
            record.status,
            record.scopes,
            record.createdAt,
            record.expiresAt,
            record.lastUsedAt,
            record.revokedAt,
            record.rotatedFrom
        };
    }

    std::vector<AuditEvent> auditEvents(const std::string& keyId) const {
        std::lock_guard<std::mutex> lock(mutex_);

        std::vector<AuditEvent> result;

        std::copy_if(
            events_.begin(),
            events_.end(),
            std::back_inserter(result),
            [&keyId](const AuditEvent& event) {
                return event.keyId == keyId;
            }
        );

        return result;
    }
};

} // namespace security

int main() {
    try {
        using namespace security;
        using namespace std::chrono_literals;

        APIKeyVault vault;

        IssuedKey original = vault.issue(
            "inventory-service",
            "warehouse integration",
            {"inventory:read", "inventory:update"},
            30 * 24h,
            "platform-admin"
        );

        std::cout << "Issued: " << original << '\n';
        std::cout << "One-time token: " << original.token << "\n\n";

        const auto valid = vault.validate(
            original.token,
            "inventory:read"
        );

        if (!valid.accepted()) {
            throw std::runtime_error("Expected the original key to be accepted.");
        }

        std::cout << "Valid credential: "
                  << decisionName(valid.decision) << '\n';

        const auto scopeDenied = vault.validate(
            original.token,
            "billing:write"
        );

        if (scopeDenied.decision != Decision::InsufficientScope) {
            throw std::runtime_error("Expected a scope denial.");
        }

        std::cout << "Scope decision: "
                  << decisionName(scopeDenied.decision) << '\n';

        IssuedKey replacement = vault.rotate(
            original.token,
            "security-admin",
            60 * 24h
        );

        const auto oldResult = vault.validate(
            original.token,
            "inventory:read"
        );

        if (oldResult.decision != Decision::Revoked) {
            throw std::runtime_error("Rotation did not revoke the old key.");
        }

        const auto replacementResult = vault.validate(
            replacement.token,
            "inventory:read"
        );

        if (!replacementResult.accepted()) {
            throw std::runtime_error("Replacement key was not accepted.");
        }

        std::cout << "\nReplacement: " << replacement << '\n';
        std::cout << "Replacement token: " << replacement.token << '\n';

        vault.revoke(replacement.keyId, "security-admin");

        const auto revokedResult = vault.validate(
            replacement.token,
            "inventory:read"
        );

        if (revokedResult.decision != Decision::Revoked) {
            throw std::runtime_error("Revocation did not block the key.");
        }

        const auto information = vault.metadata(replacement.keyId);

        std::cout << "\nReplacement metadata\n"
                  << "Key ID: " << information.keyId << '\n'
                  << "Owner: " << information.owner << '\n'
                  << "Status: "
                  << (
                      information.status == KeyStatus::Active
                          ? "active"
                          : "revoked"
                  )
                  << '\n'
                  << "Last used: "
                  << (
                      information.lastUsedAt.has_value()
                          ? formatTime(*information.lastUsedAt)
                          : "never"
                  )
                  << '\n';

        std::cout << "\nAudit events\n";

        for (const auto& event : vault.auditEvents(replacement.keyId)) {
            std::cout << event.eventType
                      << " by " << event.actor
                      << " at " << formatTime(event.occurredAt)
                      << '\n';
        }

        std::cout << "\nAll lifecycle assertions passed.\n";

    } catch (const std::exception& error) {
        std::cerr << "API key lifecycle failure: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
