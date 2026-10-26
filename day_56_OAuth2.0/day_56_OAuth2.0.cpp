#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class TokenStatus {
    Active,
    Revoked
};

enum class ReviewDecision {
    Pending,
    Approved,
    Denied
};

enum class MergeDecision {
    Eligible,
    Blocked
};

struct Client {
    std::string id;
    std::set<std::string> redirectUris;
    std::set<std::string> allowedScopes;
    bool confidential{false};
    std::string clientSecret;
};

struct AuthorizationCode {
    std::string value;
    std::string clientId;
    std::string redirectUri;
    std::string subject;
    std::set<std::string> scopes;
    std::string pkceChallenge;
    std::chrono::system_clock::time_point expiresAt;
    bool used{false};
};

struct AccessToken {
    std::string value;
    std::string clientId;
    std::string subject;
    std::set<std::string> scopes;
    std::chrono::system_clock::time_point expiresAt;
    TokenStatus status{TokenStatus::Active};
};

struct RefreshToken {
    std::string value;
    std::string clientId;
    std::string subject;
    std::set<std::string> scopes;
    std::chrono::system_clock::time_point expiresAt;
    TokenStatus status{TokenStatus::Active};
};

struct Resource {
    std::string id;
    std::string owner;
    std::string requiredScope;
    std::map<std::string, std::string> attributes;
};

class OAuthException : public std::runtime_error {
public:
    explicit OAuthException(const std::string& message)
        : std::runtime_error(message) {}
};

class TokenGenerator {
private:
    std::mt19937_64 engine;

public:
    TokenGenerator()
        : engine(std::random_device{}()) {}

    std::string next() {
        std::uniform_int_distribution<std::uint64_t> distribution;
        const auto a = distribution(engine);
        const auto b = distribution(engine);

        return std::to_string(a) + "-" + std::to_string(b);
    }
};

class AuthorizationServer {
private:
    std::unordered_map<std::string, Client> clients;
    std::unordered_map<std::string, AuthorizationCode> codes;
    std::unordered_map<std::string, AccessToken> accessTokens;
    std::unordered_map<std::string, RefreshToken> refreshTokens;
    TokenGenerator generator;

    static std::chrono::system_clock::time_point now() {
        return std::chrono::system_clock::now();
    }

    static bool containsAll(
        const std::set<std::string>& allowed,
        const std::set<std::string>& requested
    ) {
        return std::all_of(
            requested.begin(),
            requested.end(),
            [&](const std::string& value) {
                return allowed.contains(value);
            }
        );
    }

    void authenticateClient(
        const Client& client,
        const std::string& suppliedSecret
    ) const {
        if (!client.confidential) {
            return;
        }

        if (client.clientSecret != suppliedSecret) {
            throw OAuthException("invalid client credentials");
        }
    }

public:
    void registerClient(const Client& client) {
        if (client.id.empty()) {
            throw OAuthException("client identifier is required");
        }

        if (client.redirectUris.empty()) {
            throw OAuthException("client requires a redirect URI");
        }

        if (client.allowedScopes.empty()) {
            throw OAuthException("client requires at least one scope");
        }

        if (client.confidential && client.clientSecret.empty()) {
            throw OAuthException(
                "confidential client requires a credential"
            );
        }

        clients[client.id] = client;
    }

    std::string authorize(
        const std::string& clientId,
        const std::string& redirectUri,
        const std::string& subject,
        const std::set<std::string>& scopes,
        const std::string& pkceChallenge
    ) {
        auto clientIt = clients.find(clientId);

        if (clientIt == clients.end()) {
            throw OAuthException("unknown client");
        }

        const Client& client = clientIt->second;

        if (!client.redirectUris.contains(redirectUri)) {
            throw OAuthException("unregistered redirect URI");
        }

        if (subject.empty()) {
            throw OAuthException("resource owner is required");
        }

        if (pkceChallenge.empty()) {
            throw OAuthException("PKCE challenge is required");
        }

        if (scopes.empty() || !containsAll(client.allowedScopes, scopes)) {
            throw OAuthException("requested scope is not permitted");
        }

        AuthorizationCode code{
            generator.next(),
            clientId,
            redirectUri,
            subject,
            scopes,
            pkceChallenge,
            now() + std::chrono::minutes(2),
            false
        };

        codes.emplace(code.value, code);

        return code.value;
    }

    std::pair<AccessToken, RefreshToken> exchangeCode(
        const std::string& clientId,
        const std::string& codeValue,
        const std::string& redirectUri,
        const std::string& verifier,
        const std::string& clientSecret
    ) {
        auto clientIt = clients.find(clientId);

        if (clientIt == clients.end()) {
            throw OAuthException("unknown client");
        }

        authenticateClient(clientIt->second, clientSecret);

        auto codeIt = codes.find(codeValue);

        if (codeIt == codes.end()) {
            throw OAuthException("authorization code is invalid");
        }

        AuthorizationCode& code = codeIt->second;

        if (code.used) {
            throw OAuthException("authorization code has already been used");
        }

        if (now() >= code.expiresAt) {
            throw OAuthException("authorization code has expired");
        }

        if (code.clientId != clientId ||
            code.redirectUri != redirectUri) {
            throw OAuthException("authorization request mismatch");
        }

        /*
         * A production implementation would compute the RFC 7636
         * S256 transformation using a cryptographic library. This case
         * study keeps the comparison explicit and deterministic.
         */
        if (verifier.empty() ||
            code.pkceChallenge != ("S256:" + verifier)) {
            throw OAuthException("PKCE verification failed");
        }

        code.used = true;

        AccessToken access{
            generator.next(),
            clientId,
            code.subject,
            code.scopes,
            now() + std::chrono::minutes(15),
            TokenStatus::Active
        };

        RefreshToken refresh{
            generator.next(),
            clientId,
            code.subject,
            code.scopes,
            now() + std::chrono::hours(24),
            TokenStatus::Active
        };

        accessTokens.emplace(access.value, access);
        refreshTokens.emplace(refresh.value, refresh);

        return {access, refresh};
    }

    AccessToken validate(
        const std::string& tokenValue,
        const std::string& requiredScope
    ) const {
        auto tokenIt = accessTokens.find(tokenValue);

        if (tokenIt == accessTokens.end()) {
            throw OAuthException("unknown access token");
        }

        const AccessToken& token = tokenIt->second;

        if (token.status == TokenStatus::Revoked) {
            throw OAuthException("access token is revoked");
        }

        if (now() >= token.expiresAt) {
            throw OAuthException("access token has expired");
        }

        if (!token.scopes.contains(requiredScope)) {
            throw OAuthException("insufficient scope");
        }

        return token;
    }

    std::pair<AccessToken, RefreshToken> refresh(
        const std::string& clientId,
        const std::string& refreshValue,
        const std::string& clientSecret
    ) {
        auto clientIt = clients.find(clientId);

        if (clientIt == clients.end()) {
            throw OAuthException("unknown client");
        }

        authenticateClient(clientIt->second, clientSecret);

        auto refreshIt = refreshTokens.find(refreshValue);

        if (refreshIt == refreshTokens.end()) {
            throw OAuthException("unknown refresh token");
        }

        RefreshToken& oldToken = refreshIt->second;

        if (oldToken.status == TokenStatus::Revoked) {
            throw OAuthException("refresh token has already been rotated");
        }

        if (now() >= oldToken.expiresAt) {
            throw OAuthException("refresh token has expired");
        }

        if (oldToken.clientId != clientId) {
            throw OAuthException("refresh token client mismatch");
        }

        // Rotation prevents repeated use of a previously presented token.
        oldToken.status = TokenStatus::Revoked;

        AccessToken access{
            generator.next(),
            clientId,
            oldToken.subject,
            oldToken.scopes,
            now() + std::chrono::minutes(15),
            TokenStatus::Active
        };

        RefreshToken refresh{
            generator.next(),
            clientId,
            oldToken.subject,
            oldToken.scopes,
            now() + std::chrono::hours(24),
            TokenStatus::Active
        };

        accessTokens.emplace(access.value, access);
        refreshTokens.emplace(refresh.value, refresh);

        return {access, refresh};
    }

    void revokeAccessToken(const std::string& tokenValue) {
        auto tokenIt = accessTokens.find(tokenValue);

        if (tokenIt != accessTokens.end()) {
            tokenIt->second.status = TokenStatus::Revoked;
        }
    }
};

class ResourceServer {
private:
    AuthorizationServer& authorizationServer;
    std::unordered_map<std::string, Resource> resources;

public:
    explicit ResourceServer(AuthorizationServer& server)
        : authorizationServer(server) {}

    void addResource(const Resource& resource) {
        if (resources.contains(resource.id)) {
            throw OAuthException("duplicate resource");
        }

        resources.emplace(resource.id, resource);
    }

    std::map<std::string, std::string> read(
        const std::string& token,
        const std::string& resourceId
    ) {
        auto resourceIt = resources.find(resourceId);

        if (resourceIt == resources.end()) {
            throw OAuthException("resource does not exist");
        }

        const Resource& resource = resourceIt->second;

        AccessToken accessToken =
            authorizationServer.validate(
                token,
                resource.requiredScope
            );

        if (accessToken.subject != resource.owner) {
            throw OAuthException(
                "token subject is not authorized for resource"
            );
        }

        return resource.attributes;
    }
};

void printResource(
    const std::map<std::string, std::string>& resource
) {
    for (const auto& [key, value] : resource) {
        std::cout << "  " << key << ": " << value << '\n';
    }
}

int main() {
    try {
        AuthorizationServer authorizationServer;

        authorizationServer.registerClient(Client{
            "inventory-console",
            {"https://inventory.example.test/callback"},
            {"inventory:read", "profile:read"},
            true,
            "managed-server-secret"
        });

        ResourceServer resourceServer(authorizationServer);

        resourceServer.addResource(Resource{
            "inventory:alice",
            "alice",
            "inventory:read",
            {
                {"sku", "SKU-1001"},
                {"quantity", "42"},
                {"warehouse", "LKO-01"}
            }
        });

        /*
         * The simplified PKCE representation is deliberately explicit:
         * the authorization request stores "S256:" + verifier.
         * A production implementation must calculate the RFC 7636
         * base64url(SHA-256(verifier)) value with a vetted crypto library.
         */
        const std::string verifier = "high-entropy-client-verifier";
        const std::string challenge = "S256:" + verifier;

        std::string code = authorizationServer.authorize(
            "inventory-console",
            "https://inventory.example.test/callback",
            "alice",
            {"inventory:read"},
            challenge
        );

        auto [accessToken, refreshToken] =
            authorizationServer.exchangeCode(
                "inventory-console",
                code,
                "https://inventory.example.test/callback",
                verifier,
                "managed-server-secret"
            );

        std::cout << "Protected resource:\n";
        printResource(
            resourceServer.read(
                accessToken.value,
                "inventory:alice"
            )
        );

        auto [newAccess, newRefresh] =
            authorizationServer.refresh(
                "inventory-console",
                refreshToken.value,
                "managed-server-secret"
            );

        std::cout << "\nRefresh token rotation succeeded: "
                  << std::boolalpha
                  << (newRefresh.value != refreshToken.value)
                  << '\n';

        try {
            authorizationServer.refresh(
                "inventory-console",
                refreshToken.value,
                "managed-server-secret"
            );
        } catch (const OAuthException& ex) {
            std::cout << "Refresh replay rejected: "
                      << ex.what() << '\n';
        }

        authorizationServer.revokeAccessToken(newAccess.value);

        try {
            resourceServer.read(
                newAccess.value,
                "inventory:alice"
            );
        } catch (const OAuthException& ex) {
            std::cout << "Revoked access token rejected: "
                      << ex.what() << '\n';
        }

        try {
            authorizationServer.authorize(
                "inventory-console",
                "https://evil.example.test/callback",
                "alice",
                {"inventory:read"},
                challenge
            );
        } catch (const OAuthException& ex) {
            std::cout << "Unregistered redirect rejected: "
                      << ex.what() << '\n';
        }

        try {
            authorizationServer.authorize(
                "inventory-console",
                "https://inventory.example.test/callback",
                "alice",
                {"admin:write"},
                challenge
            );
        } catch (const OAuthException& ex) {
            std::cout << "Unauthorized scope rejected: "
                      << ex.what() << '\n';
        }

    } catch (const std::exception& ex) {
        std::cerr << "Fatal OAuth workflow failure: "
                  << ex.what() << '\n';
        return 1;
    }

    return 0;
}
