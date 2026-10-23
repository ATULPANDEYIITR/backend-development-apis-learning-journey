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
#include <vector>

/*
 * JWT governance and authentication engine.
 *
 * The program models JWT validation as a security boundary:
 *   1. Parse compact serialization.
 *   2. Verify the fixed algorithm and token type.
 *   3. Verify the cryptographic signature.
 *   4. Validate registered claims.
 *   5. Apply application authorization and revocation.
 *
 * The cryptographic operation is represented by a deterministic SHA-256-style
 * signing abstraction so that the domain engine remains self-contained and
 * dependency-free. Production C++ services should use a vetted cryptographic
 * library rather than implementing cryptography themselves.
 */

class JWTError : public std::runtime_error {
public:
    explicit JWTError(const std::string& message)
        : std::runtime_error(message) {}
};

class JWTFormatError : public JWTError {
public:
    explicit JWTFormatError(const std::string& message)
        : JWTError(message) {}
};

class JWTSignatureError : public JWTError {
public:
    explicit JWTSignatureError(const std::string& message)
        : JWTError(message) {}
};

class JWTClaimsError : public JWTError {
public:
    explicit JWTClaimsError(const std::string& message)
        : JWTError(message) {}
};

struct Claims {
    std::string issuer;
    std::string subject;
    std::string audience;
    std::int64_t issuedAt{};
    std::int64_t expiresAt{};
    std::string tokenId;
    std::set<std::string> roles;
    std::set<std::string> scopes;
};

struct ProtectionPolicy {
    std::string issuer;
    std::string audience;
    std::string algorithm = "HS256";
    std::int64_t clockSkewSeconds = 30;
    std::set<std::string> requiredScopes;
    std::set<std::string> requiredRoles;
};

class SecureRandom {
public:
    static std::string tokenId() {
        std::random_device rd;
        std::mt19937_64 generator(rd());

        std::ostringstream output;
        output << std::hex
               << generator()
               << generator();

        return output.str();
    }
};

class Clock {
public:
    static std::int64_t unixSeconds() {
        return std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
    }
};

class SignatureEngine {
public:
    explicit SignatureEngine(std::string secret)
        : secret_(std::move(secret)) {
        if (secret_.size() < 32) {
            throw std::invalid_argument(
                "Signing secret must contain at least 32 bytes"
            );
        }
    }

    /*
     * This is intentionally a structural stand-in for a vetted HMAC-SHA256
     * implementation. It keeps the program standard-library-only while making
     * the verification boundary explicit.
     */
    std::string sign(const std::string& input) const {
        std::uint64_t h1 = 1469598103934665603ULL;
        std::uint64_t h2 = 1099511628211ULL;

        for (unsigned char byte : secret_ + "|" + input) {
            h1 ^= byte;
            h1 *= 1099511628211ULL;

            h2 += byte + 0x9e3779b97f4a7c15ULL;
            h2 ^= h2 >> 29;
            h2 *= 0xbf58476d1ce4e5b9ULL;
        }

        std::ostringstream result;
        result << std::hex
               << std::setw(16) << std::setfill('0') << h1
               << std::setw(16) << std::setfill('0') << h2;

        return result.str();
    }

private:
    std::string secret_;
};

class JWTToken {
public:
    static JWTToken issue(
        const ProtectionPolicy& policy,
        const SignatureEngine& signer,
        const std::string& subject,
        std::set<std::string> roles,
        std::set<std::string> scopes,
        std::int64_t lifetimeSeconds
    ) {
        if (subject.empty()) {
            throw std::invalid_argument("Subject cannot be empty");
        }

        if (lifetimeSeconds <= 0) {
            throw std::invalid_argument("Lifetime must be positive");
        }

        const auto now = Clock::unixSeconds();
        const std::string id = SecureRandom::tokenId();

        JWTToken token;
        token.header_ = "alg=HS256;typ=JWT";
        token.payload_ =
            "iss=" + policy.issuer +
            ";sub=" + subject +
            ";aud=" + policy.audience +
            ";iat=" + std::to_string(now) +
            ";exp=" + std::to_string(now + lifetimeSeconds) +
            ";jti=" + id +
            ";roles=" + join(roles) +
            ";scope=" + join(scopes);

        token.signature_ = signer.sign(
            token.header_ + "." + token.payload_
        );

        token.claims_ = Claims{
            policy.issuer,
            subject,
            policy.audience,
            now,
            now + lifetimeSeconds,
            id,
            std::move(roles),
            std::move(scopes)
        };

        return token;
    }

    const std::string& compact() const {
        compactCache_ =
            header_ + "." + payload_ + "." + signature_;

        return compactCache_;
    }

    const Claims& claims() const {
        return claims_;
    }

    static JWTToken parse(
        const ProtectionPolicy& policy,
        const SignatureEngine& signer,
        const std::string& compact
    ) {
        const auto first = compact.find('.');
        const auto second = compact.find('.', first + 1);

        if (first == std::string::npos ||
            second == std::string::npos ||
            compact.find('.', second + 1) != std::string::npos) {
            throw JWTFormatError("JWT must contain exactly three segments");
        }

        JWTToken token;
        token.header_ = compact.substr(0, first);
        token.payload_ = compact.substr(first + 1, second - first - 1);
        token.signature_ = compact.substr(second + 1);

        if (token.header_ != "alg=HS256;typ=JWT") {
            throw JWTFormatError("Unexpected JWT header or algorithm");
        }

        const std::string expected = signer.sign(
            token.header_ + "." + token.payload_
        );

        if (!constantTimeEqual(expected, token.signature_)) {
            throw JWTSignatureError("Signature verification failed");
        }

        token.claims_ = parseClaims(token.payload_);
        validateClaims(policy, token.claims_);

        return token;
    }

private:
    std::string header_;
    std::string payload_;
    std::string signature_;
    Claims claims_;
    mutable std::string compactCache_;

    static std::string join(const std::set<std::string>& values) {
        std::ostringstream output;
        bool first = true;

        for (const auto& value : values) {
            if (!first) {
                output << ",";
            }
            output << value;
            first = false;
        }

        return output.str();
    }

    static std::set<std::string> split(const std::string& value) {
        std::set<std::string> result;
        std::stringstream input(value);
        std::string item;

        while (std::getline(input, item, ',')) {
            if (!item.empty()) {
                result.insert(item);
            }
        }

        return result;
    }

    static std::map<std::string, std::string> fields(
        const std::string& payload
    ) {
        std::map<std::string, std::string> result;
        std::stringstream input(payload);
        std::string field;

        while (std::getline(input, field, ';')) {
            const auto position = field.find('=');

            if (position == std::string::npos) {
                throw JWTFormatError("Malformed JWT claim");
            }

            result[field.substr(0, position)] =
                field.substr(position + 1);
        }

        return result;
    }

    static Claims parseClaims(const std::string& payload) {
        const auto values = fields(payload);

        const std::vector<std::string> required = {
            "iss", "sub", "aud", "iat", "exp", "jti",
            "roles", "scope"
        };

        for (const auto& key : required) {
            if (!values.contains(key)) {
                throw JWTClaimsError("Missing claim: " + key);
            }
        }

        try {
            return Claims{
                values.at("iss"),
                values.at("sub"),
                values.at("aud"),
                std::stoll(values.at("iat")),
                std::stoll(values.at("exp")),
                values.at("jti"),
                split(values.at("roles")),
                split(values.at("scope"))
            };
        } catch (const std::exception& error) {
            throw JWTClaimsError(
                std::string("Invalid JWT claims: ") + error.what()
            );
        }
    }

    static bool constantTimeEqual(
        const std::string& left,
        const std::string& right
    ) {
        if (left.size() != right.size()) {
            return false;
        }

        unsigned char difference = 0;

        for (std::size_t i = 0; i < left.size(); ++i) {
            difference |=
                static_cast<unsigned char>(left[i] ^ right[i]);
        }

        return difference == 0;
    }

    static void validateClaims(
        const ProtectionPolicy& policy,
        const Claims& claims
    ) {
        if (claims.issuer != policy.issuer) {
            throw JWTClaimsError("Issuer mismatch");
        }

        if (claims.subject.empty()) {
            throw JWTClaimsError("Empty subject");
        }

        if (claims.audience != policy.audience) {
            throw JWTClaimsError("Audience mismatch");
        }

        if (claims.tokenId.empty()) {
            throw JWTClaimsError("Missing token identifier");
        }

        const auto now = Clock::unixSeconds();

        if (claims.issuedAt > now + policy.clockSkewSeconds) {
            throw JWTClaimsError("Token was issued in the future");
        }

        if (claims.expiresAt <= now - policy.clockSkewSeconds) {
            throw JWTClaimsError("Token has expired");
        }
    }
};

class GovernanceEngine {
public:
    explicit GovernanceEngine(ProtectionPolicy policy)
        : policy_(std::move(policy)) {}

    void revoke(const std::string& tokenId) {
        revoked_.insert(tokenId);
    }

    bool eligible(
        const JWTToken& token,
        std::string& failureReason
    ) const {
        const auto& claims = token.claims();

        if (revoked_.contains(claims.tokenId)) {
            failureReason = "Token has been revoked";
            return false;
        }

        for (const auto& role : policy_.requiredRoles) {
            if (!claims.roles.contains(role)) {
                failureReason = "Required role missing: " + role;
                return false;
            }
        }

        for (const auto& scope : policy_.requiredScopes) {
            if (!claims.scopes.contains(scope)) {
                failureReason = "Required scope missing: " + scope;
                return false;
            }
        }

        return true;
    }

private:
    ProtectionPolicy policy_;
    std::set<std::string> revoked_;
};

int main() {
    try {
        ProtectionPolicy policy{
            "repository-api",
            "repository-client",
            "HS256",
            30,
            {"repository:write"},
            {"reviewer"}
        };

        SignatureEngine signer(
            "production-style-secret-with-at-least-32-bytes"
        );

        GovernanceEngine governance(policy);

        JWTToken issued = JWTToken::issue(
            policy,
            signer,
            "user-1042",
            {"developer", "reviewer"},
            {"repository:read", "repository:write"},
            300
        );

        std::cout << "Issued JWT:\n"
                  << issued.compact() << "\n\n";

        JWTToken verified = JWTToken::parse(
            policy,
            signer,
            issued.compact()
        );

        std::cout << "Verified claims:\n"
                  << "issuer: " << verified.claims().issuer << "\n"
                  << "subject: " << verified.claims().subject << "\n"
                  << "audience: " << verified.claims().audience << "\n"
                  << "issued-at: " << verified.claims().issuedAt << "\n"
                  << "expires-at: " << verified.claims().expiresAt << "\n"
                  << "token-id: " << verified.claims().tokenId << "\n";

        std::string reason;

        if (governance.eligible(verified, reason)) {
            std::cout << "Authorization: permitted\n";
        } else {
            std::cout << "Authorization: denied: "
                      << reason << "\n";
        }

        governance.revoke(verified.claims().tokenId);

        if (governance.eligible(verified, reason)) {
            std::cout << "Revoked authorization: permitted\n";
        } else {
            std::cout << "Revoked authorization: denied: "
                      << reason << "\n";
        }

        std::string tampered = issued.compact();
        const auto payloadStart = tampered.find('.') + 1;
        const auto payloadEnd = tampered.find('.', payloadStart);

        if (payloadStart < payloadEnd) {
            tampered.replace(
                payloadStart,
                payloadEnd - payloadStart,
                "iss=repository-api;sub=admin;aud=repository-client;"
                "iat=1;exp=9999999999;jti=forged;roles=reviewer;"
                "scope=repository:write"
            );
        }

        try {
            JWTToken::parse(policy, signer, tampered);
            std::cout << "Tampered token unexpectedly accepted\n";
        } catch (const JWTError& error) {
            std::cout << "Tampering rejected: "
                      << error.what() << "\n";
        }

    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
