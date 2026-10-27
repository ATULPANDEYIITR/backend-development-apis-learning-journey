#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
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
#include <vector>

enum class ReviewState {
    Draft,
    Submitted,
    Authenticated,
    Failed
};

enum class TokenType {
    IdToken,
    AccessToken
};

struct User {
    std::string subject;
    std::string username;
    std::string email;
    std::string name;
    bool emailVerified;
};

struct Client {
    std::string clientId;
    std::string clientSecret;
    std::set<std::string> redirectUris;
    std::set<std::string> scopes;
};

struct AuthorizationRequest {
    std::string state;
    std::string nonce;
    std::string clientId;
    std::string redirectUri;
    std::set<std::string> scopes;
    std::string codeChallenge;
};

struct AuthorizationCode {
    std::string code;
    std::string clientId;
    std::string subject;
    std::string redirectUri;
    std::string nonce;
    std::string codeChallenge;
    std::chrono::system_clock::time_point expiresAt;
    bool consumed{false};
};

struct IdTokenClaims {
    std::string issuer;
    std::string subject;
    std::string audience;
    std::string nonce;
    std::int64_t issuedAt;
    std::int64_t expiresAt;
};

class OIDCException : public std::runtime_error {
public:
    explicit OIDCException(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationException : public OIDCException {
public:
    explicit ValidationException(const std::string& message)
        : OIDCException(message) {}
};

class OIDCProvider {
private:
    std::string issuer_;
    std::string signingKey_;
    std::unordered_map<std::string, User> users_;
    std::unordered_map<std::string, AuthorizationCode> codes_;

    static std::string randomToken(std::size_t length) {
        static constexpr char alphabet[] =
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

        std::random_device rd;
        std::mt19937 generator(rd());
        std::uniform_int_distribution<std::size_t> distribution(
            0,
            sizeof(alphabet) - 2
        );

        std::string result;
        result.reserve(length);

        for (std::size_t i = 0; i < length; ++i) {
            result += alphabet[distribution(generator)];
        }

        return result;
    }

    static std::int64_t unixTime() {
        return std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
    }

public:
    OIDCProvider(
        std::string issuer,
        std::string signingKey
    )
        : issuer_(std::move(issuer)),
          signingKey_(std::move(signingKey)) {
        if (issuer_.rfind("https://", 0) != 0) {
            throw ValidationException("OIDC issuer must use HTTPS");
        }
    }

    void registerUser(User user) {
        if (user.subject.empty() || user.email.empty()) {
            throw ValidationException(
                "subject and email are required"
            );
        }

        users_[user.subject] = std::move(user);
    }

    std::string authorize(
        const AuthorizationRequest& request,
        const std::string& authenticatedSubject
    ) {
        if (request.state.empty() || request.nonce.empty()) {
            throw ValidationException(
                "state and nonce are required"
            );
        }

        if (request.clientId != "enterprise-web") {
            throw ValidationException("unknown client");
        }

        if (request.redirectUri !=
            "https://portal.example.com/oidc/callback") {
            throw ValidationException("unregistered redirect URI");
        }

        if (!request.scopes.contains("openid")) {
            throw ValidationException(
                "openid scope is mandatory"
            );
        }

        static const std::set<std::string> supported{
            "openid", "profile", "email"
        };

        for (const auto& scope : request.scopes) {
            if (!supported.contains(scope)) {
                throw ValidationException(
                    "unsupported scope: " + scope
                );
            }
        }

        if (!users_.contains(authenticatedSubject)) {
            throw ValidationException(
                "provider authentication required"
            );
        }

        const std::string code = randomToken(48);

        codes_[code] = AuthorizationCode{
            code,
            request.clientId,
            authenticatedSubject,
            request.redirectUri,
            request.nonce,
            request.codeChallenge,
            std::chrono::system_clock::now() +
                std::chrono::seconds(120),
            false
        };

        return code;
    }

    std::pair<std::string, std::string> exchangeCode(
        const Client& client,
        const std::string& code,
        const std::string& redirectUri,
        const std::string& codeVerifier
    ) {
        auto iterator = codes_.find(code);

        if (iterator == codes_.end()) {
            throw ValidationException(
                "authorization code does not exist"
            );
        }

        AuthorizationCode& authorization = iterator->second;

        if (authorization.consumed) {
            throw ValidationException(
                "authorization code already consumed"
            );
        }

        if (std::chrono::system_clock::now() >=
            authorization.expiresAt) {
            throw ValidationException(
                "authorization code expired"
            );
        }

        if (authorization.clientId != client.clientId) {
            throw ValidationException("client mismatch");
        }

        if (authorization.redirectUri != redirectUri) {
            throw ValidationException(
                "redirect URI mismatch"
            );
        }

        // This simplified case uses the verifier as a required
        // proof when a PKCE challenge was supplied.
        if (!authorization.codeChallenge.empty() &&
            codeVerifier.empty()) {
            throw ValidationException(
                "PKCE verifier required"
            );
        }

        authorization.consumed = true;

        const std::int64_t now = unixTime();

        std::ostringstream token;
        token << "OIDC-HS256-SIMULATED|"
              << issuer_ << "|"
              << authorization.subject << "|"
              << client.clientId << "|"
              << authorization.nonce << "|"
              << now << "|"
              << now + 3600;

        const std::string idToken = token.str();
        const std::string accessToken = randomToken(48);

        return {idToken, accessToken};
    }

    const User& userInfo(
        const std::string& accessToken,
        const std::string& subject
    ) const {
        if (accessToken.empty()) {
            throw ValidationException(
                "access token is required"
            );
        }

        auto iterator = users_.find(subject);

        if (iterator == users_.end()) {
            throw ValidationException(
                "subject does not exist"
            );
        }

        return iterator->second;
    }

    const std::string& issuer() const {
        return issuer_;
    }
};

class MergeStyleTokenParser {
public:
    static IdTokenClaims parse(
        const std::string& token
    ) {
        std::vector<std::string> fields;
        std::stringstream stream(token);
        std::string field;

        while (std::getline(stream, field, '|')) {
            fields.push_back(field);
        }

        if (fields.size() != 7 ||
            fields[0] != "OIDC-HS256-SIMULATED") {
            throw ValidationException(
                "malformed ID token"
            );
        }

        try {
            return IdTokenClaims{
                fields[1],
                fields[2],
                fields[3],
                fields[4],
                std::stoll(fields[5]),
                std::stoll(fields[6])
            };
        } catch (const std::exception&) {
            throw ValidationException(
                "invalid numeric ID token claim"
            );
        }
    }
};

class OIDCClient {
private:
    Client client_;
    const OIDCProvider& provider_;
    std::string state_;
    std::string nonce_;
    bool authenticated_{false};

    static std::string randomValue() {
        std::random_device rd;
        std::mt19937_64 engine(rd());
        std::uniform_int_distribution<std::uint64_t> distribution;

        std::ostringstream output;
        output << std::hex << distribution(engine)
               << distribution(engine);

        return output.str();
    }

public:
    OIDCClient(
        Client client,
        const OIDCProvider& provider
    )
        : client_(std::move(client)),
          provider_(provider) {}

    AuthorizationRequest createRequest() {
        state_ = randomValue();
        nonce_ = randomValue();

        return AuthorizationRequest{
            state_,
            nonce_,
            client_.clientId,
            "https://portal.example.com/oidc/callback",
            {"openid", "profile", "email"},
            randomValue()
        };
    }

    void validateIdToken(
        const std::string& token,
        const std::string& returnedState
    ) {
        if (returnedState != state_) {
            throw ValidationException(
                "state validation failed"
            );
        }

        const IdTokenClaims claims =
            MergeStyleTokenParser::parse(token);

        const std::int64_t now =
            std::chrono::duration_cast<std::chrono::seconds>(
                std::chrono::system_clock::now()
                    .time_since_epoch()
            ).count();

        if (claims.issuer != provider_.issuer()) {
            throw ValidationException("issuer mismatch");
        }

        if (claims.audience != client_.clientId) {
            throw ValidationException("audience mismatch");
        }

        if (claims.nonce != nonce_) {
            throw ValidationException("nonce mismatch");
        }

        if (claims.expiresAt <= now) {
            throw ValidationException("ID token expired");
        }

        if (claims.issuedAt > now + 60) {
            throw ValidationException(
                "ID token issued too far in the future"
            );
        }

        if (claims.subject.empty()) {
            throw ValidationException(
                "subject claim is missing"
            );
        }

        authenticated_ = true;
    }

    bool authenticated() const {
        return authenticated_;
    }

    const Client& client() const {
        return client_;
    }
};

int main() {
    try {
        OIDCProvider provider(
            "https://identity.example.com",
            "server-signing-key"
        );

        provider.registerUser(User{
            "usr-1001",
            "atul",
            "atul@example.com",
            "Atul Pandey",
            true
        });

        Client client{
            "enterprise-web",
            "client-secret",
            {"https://portal.example.com/oidc/callback"},
            {"openid", "profile", "email"}
        };

        OIDCClient oidcClient(client, provider);

        AuthorizationRequest request =
            oidcClient.createRequest();

        const std::string code =
            provider.authorize(request, "usr-1001");

        auto tokens = provider.exchangeCode(
            client,
            code,
            request.redirectUri,
            "pkce-verifier"
        );

        oidcClient.validateIdToken(
            tokens.first,
            request.state
        );

        const User& user =
            provider.userInfo(tokens.second, "usr-1001");

        std::cout << "Authentication succeeded\n";
        std::cout << "Subject: " << user.subject << '\n';
        std::cout << "Username: " << user.username << '\n';
        std::cout << "Email verified: "
                  << std::boolalpha
                  << user.emailVerified << '\n';

        try {
            oidcClient.validateIdToken(
                tokens.first,
                "attacker-state"
            );
        } catch (const OIDCException& error) {
            std::cout
                << "Expected state failure: "
                << error.what() << '\n';
        }

        try {
            provider.authorize(
                AuthorizationRequest{
                    "",
                    request.nonce,
                    request.clientId,
                    request.redirectUri,
                    {"openid"},
                    ""
                },
                "usr-1001"
            );
        } catch (const OIDCException& error) {
            std::cout
                << "Expected authorization failure: "
                << error.what() << '\n';
        }

        std::cout << "OIDC governance simulation completed.\n";
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what() << '\n';
        return 1;
    }

    return 0;
}
