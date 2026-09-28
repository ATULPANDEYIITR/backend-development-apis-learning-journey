/*
 * API VERSIONING CASE STUDY
 *
 * Scenario:
 *     A multi-client user-management API is evolving from V1 to V2 and V3.
 *
 * The program demonstrates:
 *     - URL versioning
 *     - Header versioning
 *     - Version negotiation
 *     - Backward compatibility
 *     - Version-specific serialization
 *     - Compatibility adapters
 *     - Shared domain services
 *     - Deprecation and sunset
 *     - Consumer telemetry
 *     - Validation
 *     - Error handling
 *     - Cache-key considerations
 *     - Security boundaries
 *     - Complexity and design trade-offs
 *
 * Compile:
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic api_versioning.cpp -o api_versioning
 *
 * Run:
 *     ./api_versioning
 */

#include <algorithm>
#include <chrono>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>


// ============================================================================
// 1. UTILITY FUNCTIONS
// ============================================================================

void printSection(const std::string& title) {
    std::cout << "\n"
              << std::string(78, '=')
              << "\n"
              << title
              << "\n"
              << std::string(78, '=')
              << "\n";
}

void printSubsection(const std::string& title) {
    std::cout << "\n"
              << std::string(78, '-')
              << "\n"
              << title
              << "\n"
              << std::string(78, '-')
              << "\n";
}

std::string toLower(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::tolower(character));
        }
    );

    return value;
}

bool startsWith(const std::string& value, const std::string& prefix) {
    return value.size() >= prefix.size() &&
           value.compare(0, prefix.size(), prefix) == 0;
}


// ============================================================================
// 2. DOMAIN EXCEPTIONS
// ============================================================================

class ApiException : public std::runtime_error {
public:
    explicit ApiException(const std::string& message)
        : std::runtime_error(message) {}
};

class InvalidVersionException : public ApiException {
public:
    explicit InvalidVersionException(const std::string& message)
        : ApiException(message) {}
};

class UnsupportedVersionException : public ApiException {
public:
    explicit UnsupportedVersionException(const std::string& message)
        : ApiException(message) {}
};

class ValidationException : public ApiException {
public:
    explicit ValidationException(const std::string& message)
        : ApiException(message) {}
};


// ============================================================================
// 3. API VERSION
// ============================================================================

class ApiVersion {
private:
    int major_;

public:
    explicit ApiVersion(int major) : major_(major) {
        if (major < 1) {
            throw InvalidVersionException(
                "API version must be positive."
            );
        }
    }

    int major() const {
        return major_;
    }

    std::string toString() const {
        return "v" + std::to_string(major_);
    }

    bool operator==(const ApiVersion& other) const {
        return major_ == other.major_;
    }

    bool operator<(const ApiVersion& other) const {
        return major_ < other.major_;
    }
};


// ============================================================================
// 4. REQUEST AND RESPONSE MODELS
// ============================================================================

struct ApiRequest {
    std::string method;
    std::string path;
    std::map<std::string, std::string> headers;
    std::string body;
    std::string clientId;
    bool authenticated{false};
};

struct ApiResponse {
    int statusCode;
    std::map<std::string, std::string> headers;
    std::string body;
};


// ============================================================================
// 5. DOMAIN MODEL
// ============================================================================

struct User {
    int id;
    std::string firstName;
    std::string lastName;
    std::string email;
    std::string phone;
    bool active;
    std::string createdAt;
};


// ============================================================================
// 6. VERSION-SPECIFIC RESPONSE DTOs
// ============================================================================

struct UserV1Response {
    int id;
    std::string name;
    std::string email;
    bool active;
};

struct UserV2Response {
    int id;
    std::string firstName;
    std::string lastName;
    std::string email;
    std::string phone;
    bool active;
};

struct UserV3Response {
    int id;
    std::string firstName;
    std::string lastName;
    std::string email;
    std::string phone;
    std::string status;
    std::string createdAt;
};


// ============================================================================
// 7. SERIALIZATION
// ============================================================================

std::string jsonEscape(const std::string& value) {
    std::string escaped;

    for (char character : value) {
        switch (character) {
            case '"':
                escaped += "\\\"";
                break;
            case '\\':
                escaped += "\\\\";
                break;
            case '\n':
                escaped += "\\n";
                break;
            case '\r':
                escaped += "\\r";
                break;
            case '\t':
                escaped += "\\t";
                break;
            default:
                escaped += character;
                break;
        }
    }

    return escaped;
}

std::string serialize(const UserV1Response& response) {
    std::ostringstream output;

    output << "{"
           << "\"id\":" << response.id << ","
           << "\"name\":\"" << jsonEscape(response.name) << "\","
           << "\"email\":\"" << jsonEscape(response.email) << "\","
           << "\"active\":" << (response.active ? "true" : "false")
           << "}";

    return output.str();
}

std::string serialize(const UserV2Response& response) {
    std::ostringstream output;

    output << "{"
           << "\"id\":" << response.id << ","
           << "\"first_name\":\"" << jsonEscape(response.firstName) << "\","
           << "\"last_name\":\"" << jsonEscape(response.lastName) << "\","
           << "\"email\":\"" << jsonEscape(response.email) << "\","
           << "\"phone\":\"" << jsonEscape(response.phone) << "\","
           << "\"is_active\":" << (response.active ? "true" : "false")
           << "}";

    return output.str();
}

std::string serialize(const UserV3Response& response) {
    std::ostringstream output;

    output << "{"
           << "\"id\":" << response.id << ","
           << "\"identity\":{"
           << "\"firstName\":\"" << jsonEscape(response.firstName) << "\","
           << "\"lastName\":\"" << jsonEscape(response.lastName) << "\""
           << "},"
           << "\"contact\":{"
           << "\"email\":\"" << jsonEscape(response.email) << "\","
           << "\"phone\":\"" << jsonEscape(response.phone) << "\""
           << "},"
           << "\"status\":\"" << jsonEscape(response.status) << "\","
           << "\"createdAt\":\"" << jsonEscape(response.createdAt) << "\""
           << "}";

    return output.str();
}


// ============================================================================
// 8. VERSIONED REPRESENTATION SERVICE
// ============================================================================

class UserRepresentationService {
public:
    UserV1Response toV1(const User& user) const {
        return UserV1Response{
            user.id,
            user.firstName + " " + user.lastName,
            user.email,
            user.active
        };
    }

    UserV2Response toV2(const User& user) const {
        return UserV2Response{
            user.id,
            user.firstName,
            user.lastName,
            user.email,
            user.phone,
            user.active
        };
    }

    UserV3Response toV3(const User& user) const {
        return UserV3Response{
            user.id,
            user.firstName,
            user.lastName,
            user.email,
            user.phone,
            user.active ? "active" : "inactive",
            user.createdAt
        };
    }

    std::string serializeForVersion(
        const User& user,
        const ApiVersion& version
    ) const {
        switch (version.major()) {
            case 1:
                return serialize(toV1(user));

            case 2:
                return serialize(toV2(user));

            case 3:
                return serialize(toV3(user));

            default:
                throw UnsupportedVersionException(
                    "No serializer exists for " + version.toString()
                );
        }
    }
};


// ============================================================================
// 9. URL VERSION PARSER
// ============================================================================

struct ParsedPath {
    ApiVersion version;
    std::string resource;
};

ParsedPath parseUrlVersion(const std::string& path) {
    static const std::regex pattern(
        R"(^/api/v([1-9][0-9]*)/([A-Za-z0-9_-]+)/*$)"
    );

    std::smatch match;

    if (!std::regex_match(path, match, pattern)) {
        throw InvalidVersionException(
            "Invalid versioned path: " + path
        );
    }

    const int versionNumber = std::stoi(match[1].str());

    return ParsedPath{
        ApiVersion(versionNumber),
        match[2].str()
    };
}


// ============================================================================
// 10. HEADER VERSION PARSER
// ============================================================================

ApiVersion parseHeaderVersion(
    const std::map<std::string, std::string>& headers
) {
    auto iterator = headers.find("API-Version");

    if (iterator == headers.end()) {
        iterator = headers.find("api-version");
    }

    if (iterator == headers.end()) {
        throw InvalidVersionException(
            "API-Version header is missing."
        );
    }

    const std::string& value = iterator->second;

    if (
        value.empty() ||
        !std::all_of(
            value.begin(),
            value.end(),
            [](unsigned char character) {
                return std::isdigit(character);
            }
        )
    ) {
        throw InvalidVersionException(
            "API-Version must be numeric."
        );
    }

    return ApiVersion(std::stoi(value));
}


// ============================================================================
// 11. VERSION CONSISTENCY
// ============================================================================

std::optional<ApiVersion> selectConsistentVersion(
    const std::optional<ApiVersion>& urlVersion,
    const std::optional<ApiVersion>& headerVersion
) {
    if (
        urlVersion.has_value() &&
        headerVersion.has_value() &&
        !(urlVersion.value() == headerVersion.value())
    ) {
        throw InvalidVersionException(
            "URL version and header version conflict."
        );
    }

    if (urlVersion.has_value()) {
        return urlVersion;
    }

    if (headerVersion.has_value()) {
        return headerVersion;
    }

    return std::nullopt;
}


// ============================================================================
// 12. VERSION POLICY
// ============================================================================

enum class Lifecycle {
    Current,
    Supported,
    Deprecated,
    Sunset
};

std::string lifecycleToString(Lifecycle lifecycle) {
    switch (lifecycle) {
        case Lifecycle::Current:
            return "current";
        case Lifecycle::Supported:
            return "supported";
        case Lifecycle::Deprecated:
            return "deprecated";
        case Lifecycle::Sunset:
            return "sunset";
    }

    return "unknown";
}

struct VersionPolicy {
    ApiVersion version;
    Lifecycle lifecycle;
    std::optional<ApiVersion> successor;
    std::string deprecatedAt;
    std::string sunsetAt;
    std::string migrationUrl;
};


// ============================================================================
// 13. VERSION REGISTRY
// ============================================================================

class VersionRegistry {
private:
    std::map<int, VersionPolicy> policies_;

public:
    void registerVersion(const VersionPolicy& policy) {
        policies_[policy.version.major()] = policy;
    }

    bool supports(const ApiVersion& version) const {
        auto iterator = policies_.find(version.major());

        if (iterator == policies_.end()) {
            return false;
        }

        return iterator->second.lifecycle != Lifecycle::Sunset;
    }

    std::optional<VersionPolicy> find(const ApiVersion& version) const {
        auto iterator = policies_.find(version.major());

        if (iterator == policies_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    std::vector<int> supportedVersions() const {
        std::vector<int> result;

        for (const auto& [major, policy] : policies_) {
            if (policy.lifecycle != Lifecycle::Sunset) {
                result.push_back(major);
            }
        }

        return result;
    }
};


// ============================================================================
// 14. DEPRECATION HEADERS
// ============================================================================

std::map<std::string, std::string> createDeprecationHeaders(
    const VersionPolicy& policy
) {
    std::map<std::string, std::string> headers;

    if (policy.lifecycle != Lifecycle::Deprecated) {
        return headers;
    }

    headers["Deprecation"] = "true";

    if (!policy.sunsetAt.empty()) {
        headers["Sunset"] = policy.sunsetAt;
    }

    if (!policy.migrationUrl.empty()) {
        std::ostringstream link;

        link << "<"
             << policy.migrationUrl
             << ">; rel=\"successor-version\"";

        headers["Link"] = link.str();
    }

    return headers;
}


// ============================================================================
// 15. CONSUMER TELEMETRY
// ============================================================================

struct UsageEvent {
    std::string clientId;
    int version;
    int statusCode;
};

class UsageTracker {
private:
    std::vector<UsageEvent> events_;

public:
    void record(const UsageEvent& event) {
        events_.push_back(event);
    }

    std::map<int, int> countByVersion() const {
        std::map<int, int> result;

        for (const auto& event : events_) {
            ++result[event.version];
        }

        return result;
    }

    std::set<std::string> clientsUsingVersion(int version) const {
        std::set<std::string> clients;

        for (const auto& event : events_) {
            if (event.version == version) {
                clients.insert(event.clientId);
            }
        }

        return clients;
    }
};


// ============================================================================
// 16. CACHE KEY
// ============================================================================

std::string createCacheKey(
    const std::string& path,
    const ApiVersion& version
) {
    /*
     * Header-based versioning requires cache awareness.
     *
     * A cache that keys only on /api/users could incorrectly reuse a V1
     * representation for a V2 client. In real HTTP systems, Vary and cache
     * configuration must reflect the version-selection mechanism.
     */
    return path + "|API-Version=" + std::to_string(version.major());
}


// ============================================================================
// 17. SECURITY BOUNDARY
// ============================================================================

bool authorizeRequest(
    const ApiRequest& request,
    const ApiVersion& version
) {
    /*
     * Version selection is not authentication.
     * Every API version still needs normal security controls.
     */
    if (!request.authenticated) {
        return false;
    }

    if (version.major() < 1) {
        return false;
    }

    return true;
}


// ============================================================================
// 18. USER SERVICE
// ============================================================================

class UserService {
private:
    std::unordered_map<int, User> users_;

public:
    void addUser(const User& user) {
        users_[user.id] = user;
    }

    User findUser(int userId) const {
        auto iterator = users_.find(userId);

        if (iterator == users_.end()) {
            throw ApiException("User not found.");
        }

        return iterator->second;
    }
};


// ============================================================================
// 19. REQUEST VALIDATION
// ============================================================================

void validateEmail(const std::string& email) {
    if (
        email.empty() ||
        email.find('@') == std::string::npos
    ) {
        throw ValidationException(
            "Email must be non-empty and contain '@'."
        );
    }
}

void validateV1CreateRequest(
    const std::string& name,
    const std::string& email
) {
    if (name.empty()) {
        throw ValidationException(
            "V1 name cannot be empty."
        );
    }

    validateEmail(email);
}

void validateV2CreateRequest(
    const std::string& firstName,
    const std::string& lastName,
    const std::string& email
) {
    if (firstName.empty()) {
        throw ValidationException(
            "V2 firstName cannot be empty."
        );
    }

    if (lastName.empty()) {
        throw ValidationException(
            "V2 lastName cannot be empty."
        );
    }

    validateEmail(email);
}


// ============================================================================
// 20. COMPATIBILITY ADAPTERS
// ============================================================================

struct CanonicalUserInput {
    std::string firstName;
    std::string lastName;
    std::string email;
};

CanonicalUserInput adaptV1Request(
    const std::string& name,
    const std::string& email
) {
    validateV1CreateRequest(name, email);

    std::istringstream input(name);
    std::string firstName;
    std::string word;
    std::vector<std::string> parts;

    while (input >> word) {
        parts.push_back(word);
    }

    if (parts.empty()) {
        throw ValidationException(
            "V1 name must contain at least one word."
        );
    }

    firstName = parts.front();

    std::string lastName;

    for (std::size_t index = 1; index < parts.size(); ++index) {
        if (!lastName.empty()) {
            lastName += " ";
        }

        lastName += parts[index];
    }

    return CanonicalUserInput{
        firstName,
        lastName,
        toLower(email)
    };
}

CanonicalUserInput adaptV2Request(
    const std::string& firstName,
    const std::string& lastName,
    const std::string& email
) {
    validateV2CreateRequest(firstName, lastName, email);

    return CanonicalUserInput{
        firstName,
        lastName,
        toLower(email)
    };
}


// ============================================================================
// 21. CREATE USER THROUGH SHARED DOMAIN LOGIC
// ============================================================================

User createUser(
    const CanonicalUserInput& input,
    int id
) {
    if (input.firstName.empty()) {
        throw ValidationException(
            "Canonical first name cannot be empty."
        );
    }

    return User{
        id,
        input.firstName,
        input.lastName,
        input.email,
        "",
        true,
        "2026-09-28T10:00:00Z"
    };
}


// ============================================================================
// 22. API CONTROLLER
// ============================================================================

class UserApiController {
private:
    const UserService& service_;
    const UserRepresentationService& representation_;
    const VersionRegistry& registry_;
    UsageTracker& tracker_;

public:
    UserApiController(
        const UserService& service,
        const UserRepresentationService& representation,
        const VersionRegistry& registry,
        UsageTracker& tracker
    )
        : service_(service),
          representation_(representation),
          registry_(registry),
          tracker_(tracker) {}

    ApiResponse getUser(
        const ApiRequest& request,
        const ApiVersion& version
    ) {
        if (!authorizeRequest(request, version)) {
            return ApiResponse{
                401,
                {{"Content-Type", "application/json"}},
                R"({"error":{"code":"UNAUTHORIZED","message":"Authentication required."}})"
            };
        }

        if (!registry_.supports(version)) {
            tracker_.record(
                UsageEvent{
                    request.clientId,
                    version.major(),
                    406
                }
            );

            return ApiResponse{
                406,
                {{"Content-Type", "application/json"}},
                R"({"error":{"code":"UNSUPPORTED_API_VERSION","message":"API version is not supported."}})"
            };
        }

        try {
            User user = service_.findUser(101);

            std::map<std::string, std::string> headers{
                {"Content-Type", "application/json"},
                {"API-Version", version.toString()}
            };

            auto policy = registry_.find(version);

            if (policy.has_value()) {
                auto lifecycleHeaders =
                    createDeprecationHeaders(policy.value());

                headers.insert(
                    lifecycleHeaders.begin(),
                    lifecycleHeaders.end()
                );
            }

            std::string body =
                representation_.serializeForVersion(user, version);

            tracker_.record(
                UsageEvent{
                    request.clientId,
                    version.major(),
                    200
                }
            );

            return ApiResponse{
                200,
                headers,
                body
            };
        } catch (const ApiException& exception) {
            tracker_.record(
                UsageEvent{
                    request.clientId,
                    version.major(),
                    404
                }
            );

            return ApiResponse{
                404,
                {{"Content-Type", "application/json"}},
                std::string(
                    R"({"error":{"code":"NOT_FOUND","message":")"
                ) + jsonEscape(exception.what()) +
                R"("}})"
            };
        }
    }
};


// ============================================================================
// 23. VERSION RESOLUTION
// ============================================================================

std::optional<ApiVersion> resolveRequestVersion(
    const ApiRequest& request
) {
    std::optional<ApiVersion> urlVersion;
    std::optional<ApiVersion> headerVersion;

    if (startsWith(request.path, "/api/v")) {
        try {
            urlVersion = parseUrlVersion(request.path).version;
        } catch (const InvalidVersionException&) {
            throw;
        }
    }

    auto headerIterator = request.headers.find("API-Version");

    if (headerIterator != request.headers.end()) {
        headerVersion = parseHeaderVersion(request.headers);
    }

    return selectConsistentVersion(
        urlVersion,
        headerVersion
    );
}


// ============================================================================
// 24. RESPONSE DISPLAY
// ============================================================================

void printResponse(const ApiResponse& response) {
    std::cout << "Status: " << response.statusCode << "\n";

    std::cout << "Headers:\n";

    for (const auto& [key, value] : response.headers) {
        std::cout << "  " << key << ": " << value << "\n";
    }

    std::cout << "Body:\n"
              << "  "
              << response.body
              << "\n";
}


// ============================================================================
// 25. END-TO-END PROCESSOR
// ============================================================================

ApiResponse processRequest(
    const ApiRequest& request,
    const UserApiController& controller
) {
    try {
        auto version = resolveRequestVersion(request);

        if (!version.has_value()) {
            /*
             * Defaulting to V2 is an explicit application policy.
             * A different system may require every request to specify a
             * version. The important property is deterministic behavior.
             */
            version = ApiVersion(2);
        }

        return const_cast<UserApiController&>(controller).getUser(
            request,
            version.value()
        );
    } catch (const InvalidVersionException& exception) {
        return ApiResponse{
            400,
            {{"Content-Type", "application/json"}},
            std::string(
                R"({"error":{"code":"INVALID_API_VERSION","message":")"
            ) + jsonEscape(exception.what()) +
            R"("}})"
        };
    } catch (const std::exception& exception) {
        return ApiResponse{
            500,
            {{"Content-Type", "application/json"}},
            std::string(
                R"({"error":{"code":"INTERNAL_ERROR","message":")"
            ) + jsonEscape(exception.what()) +
            R"("}})"
        };
    }
}


// ============================================================================
// 26. MAIN CASE STUDY
// ============================================================================

int main() {
    printSection("API VERSIONING CASE STUDY");

    // ------------------------------------------------------------------------
    // Establish version lifecycle.
    // ------------------------------------------------------------------------

    VersionRegistry registry;

    registry.registerVersion(
        VersionPolicy{
            ApiVersion(1),
            Lifecycle::Deprecated,
            ApiVersion(2),
            "2026-06-01T00:00:00Z",
            "2026-12-01T00:00:00Z",
            "https://example.com/docs/migrate-v1-v2"
        }
    );

    registry.registerVersion(
        VersionPolicy{
            ApiVersion(2),
            Lifecycle::Supported,
            ApiVersion(3),
            "",
            "",
            "https://example.com/docs/migrate-v2-v3"
        }
    );

    registry.registerVersion(
        VersionPolicy{
            ApiVersion(3),
            Lifecycle::Current,
            std::nullopt,
            "",
            "",
            ""
        }
    );

    printSubsection("Version Lifecycle");

    for (int version : registry.supportedVersions()) {
        auto policy = registry.find(ApiVersion(version));

        if (policy.has_value()) {
            std::cout
                << "V" << version
                << ": "
                << lifecycleToString(policy->lifecycle)
                << "\n";
        }
    }

    // ------------------------------------------------------------------------
    // Create domain service and realistic data.
    // ------------------------------------------------------------------------

    UserService userService;

    userService.addUser(
        User{
            101,
            "Atul",
            "Pandey",
            "atul@example.com",
            "+91-9000000000",
            true,
            "2026-01-15T10:00:00Z"
        }
    );

    UserRepresentationService representationService;
    UsageTracker tracker;

    UserApiController controller(
        userService,
        representationService,
        registry,
        tracker
    );

    // ------------------------------------------------------------------------
    // URL-versioned V1 request.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 1: URL Versioning, V1");

    ApiRequest v1Request{
        "GET",
        "/api/v1/users",
        {},
        "",
        "legacy-mobile-client",
        true
    };

    ApiResponse v1Response =
        processRequest(v1Request, controller);

    printResponse(v1Response);

    // ------------------------------------------------------------------------
    // URL-versioned V2 request.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 2: URL Versioning, V2");

    ApiRequest v2Request{
        "GET",
        "/api/v2/users",
        {},
        "",
        "web-client",
        true
    };

    ApiResponse v2Response =
        processRequest(v2Request, controller);

    printResponse(v2Response);

    // ------------------------------------------------------------------------
    // Header-versioned V3 request.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 3: Header Versioning, V3");

    ApiRequest v3HeaderRequest{
        "GET",
        "/api/users",
        {{"API-Version", "3"}},
        "",
        "partner-client",
        true
    };

    ApiResponse v3Response =
        processRequest(v3HeaderRequest, controller);

    printResponse(v3Response);

    // ------------------------------------------------------------------------
    // Missing version: explicit default policy.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 4: Missing Version");

    ApiRequest defaultRequest{
        "GET",
        "/api/users",
        {},
        "",
        "internal-client",
        true
    };

    ApiResponse defaultResponse =
        processRequest(defaultRequest, controller);

    printResponse(defaultResponse);

    // ------------------------------------------------------------------------
    // Conflicting URL and header versions.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 5: Conflicting Version Signals");

    ApiRequest conflictingRequest{
        "GET",
        "/api/v1/users",
        {{"API-Version", "2"}},
        "",
        "misconfigured-client",
        true
    };

    ApiResponse conflictingResponse =
        processRequest(conflictingRequest, controller);

    printResponse(conflictingResponse);

    // ------------------------------------------------------------------------
    // Unknown version.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 6: Unknown Version");

    ApiRequest unknownVersionRequest{
        "GET",
        "/api/v99/users",
        {},
        "",
        "experimental-client",
        true
    };

    ApiResponse unknownVersionResponse =
        processRequest(unknownVersionRequest, controller);

    printResponse(unknownVersionResponse);

    // ------------------------------------------------------------------------
    // Authentication failure.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 7: Authentication Failure");

    ApiRequest unauthenticatedRequest{
        "GET",
        "/api/v2/users",
        {},
        "",
        "anonymous-client",
        false
    };

    ApiResponse unauthenticatedResponse =
        processRequest(unauthenticatedRequest, controller);

    printResponse(unauthenticatedResponse);

    // ------------------------------------------------------------------------
    // Compatibility adapters.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 8: Backward-Compatible Request Adapters");

    try {
        CanonicalUserInput v1Input =
            adaptV1Request(
                "Jane Doe",
                "JANE@EXAMPLE.COM"
            );

        User createdFromV1 =
            createUser(v1Input, 200);

        std::cout
            << "V1 adapter produced canonical user: "
            << createdFromV1.firstName
            << " "
            << createdFromV1.lastName
            << ", "
            << createdFromV1.email
            << "\n";
    } catch (const ApiException& exception) {
        std::cout
            << "V1 creation failed: "
            << exception.what()
            << "\n";
    }

    try {
        CanonicalUserInput v2Input =
            adaptV2Request(
                "John",
                "Smith",
                "JOHN@EXAMPLE.COM"
            );

        User createdFromV2 =
            createUser(v2Input, 201);

        std::cout
            << "V2 adapter produced canonical user: "
            << createdFromV2.firstName
            << " "
            << createdFromV2.lastName
            << ", "
            << createdFromV2.email
            << "\n";
    } catch (const ApiException& exception) {
        std::cout
            << "V2 creation failed: "
            << exception.what()
            << "\n";
    }

    // ------------------------------------------------------------------------
    // Validation failure.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 9: Validation Failure");

    try {
        adaptV2Request(
            "",
            "Smith",
            "john@example.com"
        );
    } catch (const ValidationException& exception) {
        std::cout
            << "Correctly rejected invalid request: "
            << exception.what()
            << "\n";
    }

    // ------------------------------------------------------------------------
    // Cache behavior.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 10: Cache Keys");

    std::string cacheV1 =
        createCacheKey("/api/users", ApiVersion(1));

    std::string cacheV2 =
        createCacheKey("/api/users", ApiVersion(2));

    std::cout << "V1 cache key: " << cacheV1 << "\n";
    std::cout << "V2 cache key: " << cacheV2 << "\n";
    std::cout
        << "Keys are distinct: "
        << (cacheV1 != cacheV2 ? "yes" : "no")
        << "\n";

    // ------------------------------------------------------------------------
    // Consumer telemetry.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 11: Consumer Telemetry");

    std::map<int, int> requestCounts =
        tracker.countByVersion();

    for (const auto& [version, count] : requestCounts) {
        std::cout
            << "V" << version
            << " requests: "
            << count
            << "\n";
    }

    std::set<std::string> v1Clients =
        tracker.clientsUsingVersion(1);

    std::cout << "Clients using V1:\n";

    for (const auto& client : v1Clients) {
        std::cout << "  " << client << "\n";
    }

    // ------------------------------------------------------------------------
    // Deprecation policy inspection.
    // ------------------------------------------------------------------------

    printSubsection("Scenario 12: Deprecation Policy");

    auto v1Policy =
        registry.find(ApiVersion(1));

    if (v1Policy.has_value()) {
        std::cout
            << "V1 lifecycle: "
            << lifecycleToString(v1Policy->lifecycle)
            << "\n"
            << "Deprecated at: "
            << v1Policy->deprecatedAt
            << "\n"
            << "Sunset at: "
            << v1Policy->sunsetAt
            << "\n"
            << "Successor: "
            << (
                v1Policy->successor.has_value()
                    ? v1Policy->successor->toString()
                    : "none"
            )
            << "\n"
            << "Migration URL: "
            << v1Policy->migrationUrl
            << "\n";
    }

    // ------------------------------------------------------------------------
    // Complexity discussion.
    // ------------------------------------------------------------------------

    printSubsection("Complexity and Design Notes");

    std::cout
        << "Version lookup in VersionRegistry: O(log V) using std::map.\n"
        << "User lookup in UserService: expected O(1) using std::unordered_map.\n"
        << "Required-field validation: O(F), where F is the number of fields.\n"
        << "Serialization: O(S), where S is the response size.\n"
        << "Telemetry aggregation: O(E), where E is the number of recorded events.\n"
        << "URL parsing with regex depends on path length and regex processing.\n";

    std::cout
        << "\nArchitectural trade-offs:\n"
        << "  - URL versioning is explicit and easy to route.\n"
        << "  - Header versioning keeps URLs stable but requires cache awareness.\n"
        << "  - Media-type versioning provides content-negotiation semantics but\n"
        << "    introduces more parsing and infrastructure complexity.\n"
        << "  - Compatibility adapters reduce duplication between API contracts\n"
        << "    and the domain model.\n"
        << "  - Supporting more versions increases testing and operational cost.\n"
        << "  - Deprecation requires both communication and measurable migration data.\n";

    // ------------------------------------------------------------------------
    // Production checklist.
    // ------------------------------------------------------------------------

    printSubsection("Production Checklist");

    const std::vector<std::string> checklist{
        "Define breaking-change rules.",
        "Choose a primary version-selection mechanism.",
        "Document supported versions.",
        "Define missing-version behavior.",
        "Define unknown-version behavior.",
        "Keep domain logic independent from public API versions where practical.",
        "Use adapters for incompatible request and response schemas.",
        "Test every supported version.",
        "Test authentication and authorization for every version.",
        "Configure caches for the chosen version mechanism.",
        "Track traffic by client and version.",
        "Publish migration documentation.",
        "Communicate deprecation before retirement.",
        "Set and communicate a sunset date where appropriate.",
        "Verify remaining consumer usage before retirement.",
        "Remove retired routing and code deliberately."
    };

    for (std::size_t index = 0; index < checklist.size(); ++index) {
        std::cout
            << std::setw(2)
            << index + 1
            << ". "
            << checklist[index]
            << "\n";
    }

    printSection("CASE STUDY COMPLETE");

    std::cout
        << "The system uses version-specific contracts at the API boundary,\n"
        << "a shared internal user model, explicit compatibility adapters,\n"
        << "lifecycle metadata, telemetry, validation, security checks, and\n"
        << "version-aware response handling.\n";

    return 0;
}
