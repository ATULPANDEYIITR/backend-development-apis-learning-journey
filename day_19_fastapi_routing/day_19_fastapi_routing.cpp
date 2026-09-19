/*
    FastAPI Routing C++ Case Study

    Scenario:
        A C++ client-side service component manages a local representation of
        users and communicates conceptually with a REST API exposing:

            GET     /api/users
            GET     /api/users/{id}
            POST    /api/users
            PUT     /api/users/{id}
            PATCH   /api/users/{id}
            DELETE  /api/users/{id}

    This program does not require an external HTTP library. It focuses on the
    system design, request modeling, route construction, validation, CRUD
    semantics, error handling, pagination, and client-side state transitions
    that surround a FastAPI routing API.

    Compile:
        g++ -std=c++17 -Wall -Wextra -pedantic fastapi_routing_case_study.cpp -o routing_case_study

    Run:
        ./routing_case_study
*/

#include <algorithm>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>


// ============================================================================
// 1. HTTP METHOD MODEL
// ============================================================================

enum class HttpMethod {
    GET,
    POST,
    PUT,
    PATCH,
    DELETE
};


std::string methodToString(HttpMethod method) {
    switch (method) {
        case HttpMethod::GET:
            return "GET";
        case HttpMethod::POST:
            return "POST";
        case HttpMethod::PUT:
            return "PUT";
        case HttpMethod::PATCH:
            return "PATCH";
        case HttpMethod::DELETE:
            return "DELETE";
    }

    return "UNKNOWN";
}


// ============================================================================
// 2. HTTP RESPONSE MODEL
// ============================================================================

struct HttpResponse {
    int statusCode;
    std::string body;

    bool isSuccess() const {
        return statusCode >= 200 && statusCode < 300;
    }
};


// ============================================================================
// 3. USER DOMAIN MODEL
// ============================================================================

struct User {
    int id;
    std::string name;
    std::string email;
    int age;
};


struct UserCreateRequest {
    std::string name;
    std::string email;
    int age;
};


struct UserReplaceRequest {
    std::string name;
    std::string email;
    int age;
};


struct UserPatchRequest {
    std::optional<std::string> name;
    std::optional<std::string> email;
    std::optional<int> age;
};


// ============================================================================
// 4. STRING UTILITIES
// ============================================================================

std::string trim(const std::string& value) {
    std::size_t start = 0;
    std::size_t end = value.size();

    while (start < end &&
           std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }

    while (end > start &&
           std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }

    return value.substr(start, end - start);
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


bool isValidEmail(const std::string& email) {
    const std::size_t at = email.find('@');
    const std::size_t dot = email.find('.', at == std::string::npos ? 0 : at);

    return at != std::string::npos &&
           dot != std::string::npos &&
           at > 0 &&
           dot > at + 1 &&
           dot + 1 < email.size();
}


// ============================================================================
// 5. URL PATH PARAMETER ENCODING
// ============================================================================

bool isUnreservedUrlCharacter(unsigned char character) {
    return std::isalnum(character) ||
           character == '-' ||
           character == '_' ||
           character == '.' ||
           character == '~';
}


std::string urlEncodePathParameter(const std::string& value) {
    static constexpr char HEX[] = "0123456789ABCDEF";

    std::string encoded;

    for (unsigned char character : value) {
        if (isUnreservedUrlCharacter(character)) {
            encoded += static_cast<char>(character);
        } else {
            encoded += '%';
            encoded += HEX[(character >> 4) & 0x0F];
            encoded += HEX[character & 0x0F];
        }
    }

    return encoded;
}


// ============================================================================
// 6. ROUTE BUILDER
// ============================================================================

class RouteBuilder {
public:
    explicit RouteBuilder(std::string baseUrl)
        : baseUrl_(std::move(baseUrl)) {}

    std::string collection(const std::string& resource) const {
        return baseUrl_ + "/" + resource;
    }

    std::string item(
        const std::string& resource,
        const std::string& identifier
    ) const {
        return collection(resource) + "/" +
               urlEncodePathParameter(identifier);
    }

private:
    std::string baseUrl_;
};


// ============================================================================
// 7. VALIDATION RESULT
// ============================================================================

class ValidationResult {
public:
    void addError(std::string message) {
        errors_.push_back(std::move(message));
    }

    bool valid() const {
        return errors_.empty();
    }

    const std::vector<std::string>& errors() const {
        return errors_;
    }

private:
    std::vector<std::string> errors_;
};


// ============================================================================
// 8. USER VALIDATOR
// ============================================================================

class UserValidator {
public:
    static ValidationResult validate(
        const UserCreateRequest& request
    ) {
        ValidationResult result;

        const std::string name = trim(request.name);
        const std::string email = toLower(trim(request.email));

        if (name.size() < 2 || name.size() > 100) {
            result.addError(
                "name must contain between 2 and 100 characters"
            );
        }

        if (!isValidEmail(email)) {
            result.addError("email has an invalid basic format");
        }

        if (request.age < 13 || request.age > 120) {
            result.addError("age must be between 13 and 120");
        }

        return result;
    }

    static ValidationResult validate(
        const UserReplaceRequest& request
    ) {
        UserCreateRequest equivalent{
            request.name,
            request.email,
            request.age
        };

        return validate(equivalent);
    }
};


// ============================================================================
// 9. IN-MEMORY API REPOSITORY
// ============================================================================

class UserRepository {
public:
    UserRepository()
        : nextId_(3) {
        users_.emplace(
            1,
            User{1, "Ada Lovelace", "ada@example.com", 28}
        );

        users_.emplace(
            2,
            User{2, "Alan Turing", "alan@example.com", 32}
        );
    }

    std::optional<User> find(int id) const {
        const auto iterator = users_.find(id);

        if (iterator == users_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    std::vector<User> all() const {
        std::vector<User> result;

        for (const auto& [id, user] : users_) {
            (void)id;
            result.push_back(user);
        }

        return result;
    }

    bool emailExists(
        const std::string& email,
        std::optional<int> excludedId = std::nullopt
    ) const {
        for (const auto& [id, user] : users_) {
            if (excludedId.has_value() && id == excludedId.value()) {
                continue;
            }

            if (user.email == email) {
                return true;
            }
        }

        return false;
    }

    User create(User user) {
        user.id = nextId_;
        ++nextId_;

        users_[user.id] = user;
        return user;
    }

    bool replace(int id, const User& user) {
        auto iterator = users_.find(id);

        if (iterator == users_.end()) {
            return false;
        }

        users_[id] = user;
        return true;
    }

    bool erase(int id) {
        return users_.erase(id) > 0;
    }

private:
    std::map<int, User> users_;
    int nextId_;
};


// ============================================================================
// 10. ROUTER-LIKE APPLICATION SERVICE
// ============================================================================

class UserApi {
public:
    UserApi()
        : repository_() {}

    HttpResponse getCollection(
        std::size_t limit,
        std::size_t offset
    ) const {
        const std::vector<User> users = repository_.all();

        if (offset > users.size()) {
            return {
                200,
                "[]"
            };
        }

        const std::size_t end =
            std::min(users.size(), offset + limit);

        std::ostringstream body;
        body << "[";

        for (std::size_t index = offset; index < end; ++index) {
            if (index > offset) {
                body << ",";
            }

            body << serialize(users[index]);
        }

        body << "]";

        return {
            200,
            body.str()
        };
    }


    HttpResponse getItem(int userId) const {
        const auto user = repository_.find(userId);

        if (!user.has_value()) {
            return {
                404,
                R"({"detail":"User not found"})"
            };
        }

        return {
            200,
            serialize(user.value())
        };
    }


    HttpResponse post(const UserCreateRequest& request) {
        const ValidationResult validation =
            UserValidator::validate(request);

        if (!validation.valid()) {
            return validationError(validation);
        }

        const std::string normalizedEmail =
            toLower(trim(request.email));

        if (repository_.emailExists(normalizedEmail)) {
            return {
                409,
                R"({"detail":"A user with this email already exists"})"
            };
        }

        User user{
            0,
            trim(request.name),
            normalizedEmail,
            request.age
        };

        const User created = repository_.create(user);

        return {
            201,
            serialize(created)
        };
    }


    HttpResponse put(
        int userId,
        const UserReplaceRequest& request
    ) {
        const ValidationResult validation =
            UserValidator::validate(request);

        if (!validation.valid()) {
            return validationError(validation);
        }

        const auto existing = repository_.find(userId);

        if (!existing.has_value()) {
            return {
                404,
                R"({"detail":"User not found"})"
            };
        }

        const std::string normalizedEmail =
            toLower(trim(request.email));

        if (repository_.emailExists(
                normalizedEmail,
                userId
            )) {
            return {
                409,
                R"({"detail":"Email already belongs to another user"})"
            };
        }

        User replacement{
            userId,
            trim(request.name),
            normalizedEmail,
            request.age
        };

        repository_.replace(userId, replacement);

        return {
            200,
            serialize(replacement)
        };
    }


    HttpResponse patch(
        int userId,
        const UserPatchRequest& request
    ) {
        const auto existing = repository_.find(userId);

        if (!existing.has_value()) {
            return {
                404,
                R"({"detail":"User not found"})"
            };
        }

        if (!request.name.has_value() &&
            !request.email.has_value() &&
            !request.age.has_value()) {
            return {
                400,
                R"({"detail":"PATCH requires at least one field"})"
            };
        }

        User updated = existing.value();

        if (request.name.has_value()) {
            const std::string normalizedName =
                trim(request.name.value());

            if (normalizedName.size() < 2 ||
                normalizedName.size() > 100) {
                return {
                    422,
                    R"({"detail":"Invalid name"})"
                };
            }

            updated.name = normalizedName;
        }

        if (request.email.has_value()) {
            const std::string normalizedEmail =
                toLower(trim(request.email.value()));

            if (!isValidEmail(normalizedEmail)) {
                return {
                    422,
                    R"({"detail":"Invalid email"})"
                };
            }

            if (repository_.emailExists(
                    normalizedEmail,
                    userId
                )) {
                return {
                    409,
                    R"({"detail":"Email already belongs to another user"})"
                };
            }

            updated.email = normalizedEmail;
        }

        if (request.age.has_value()) {
            const int age = request.age.value();

            if (age < 13 || age > 120) {
                return {
                    422,
                    R"({"detail":"Invalid age"})"
                };
            }

            updated.age = age;
        }

        repository_.replace(userId, updated);

        return {
            200,
            serialize(updated)
        };
    }


    HttpResponse deleteItem(int userId) {
        if (!repository_.find(userId).has_value()) {
            return {
                404,
                R"({"detail":"User not found"})"
            };
        }

        repository_.erase(userId);

        // A DELETE route commonly returns 204 when no response body is
        // necessary.
        return {
            204,
            ""
        };
    }


private:
    UserRepository repository_;


    static std::string escapeJson(const std::string& value) {
        std::string escaped;

        for (const char character : value) {
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


    static std::string serialize(const User& user) {
        std::ostringstream output;

        output << "{"
               << "\"id\":" << user.id << ","
               << "\"name\":\"" << escapeJson(user.name) << "\","
               << "\"email\":\"" << escapeJson(user.email) << "\","
               << "\"age\":" << user.age
               << "}";

        return output.str();
    }


    static HttpResponse validationError(
        const ValidationResult& validation
    ) {
        std::ostringstream body;

        body << R"({"detail":["))";

        for (std::size_t index = 0;
             index < validation.errors().size();
             ++index) {
            if (index > 0) {
                body << ",";
            }

            body << "\""
                 << validation.errors()[index]
                 << "\"";
        }

        body << "]}";

        return {
            422,
            body.str()
        };
    }
};


// ============================================================================
// 11. RESPONSE DISPLAY
// ============================================================================

void printResponse(
    const std::string& operation,
    const HttpResponse& response
) {
    std::cout << "\n"
              << operation
              << "\n"
              << "Status: "
              << response.statusCode
              << "\n";

    if (response.body.empty()) {
        std::cout << "Body: <empty>\n";
    } else {
        std::cout << "Body: "
                  << response.body
                  << "\n";
    }
}


// ============================================================================
// 12. ROUTING TABLE
// ============================================================================

struct RouteDefinition {
    HttpMethod method;
    std::string path;
    std::string purpose;
};


void printRoutingTable() {
    const std::vector<RouteDefinition> routes{
        {HttpMethod::GET, "/api/users", "List users"},
        {HttpMethod::GET, "/api/users/{user_id}", "Read one user"},
        {HttpMethod::POST, "/api/users", "Create user"},
        {HttpMethod::PUT, "/api/users/{user_id}", "Replace user"},
        {HttpMethod::PATCH, "/api/users/{user_id}", "Partially update user"},
        {HttpMethod::DELETE, "/api/users/{user_id}", "Delete user"}
    };

    std::cout << "\n"
              << "ROUTING TABLE\n"
              << "-------------\n";

    for (const auto& route : routes) {
        std::cout
            << std::left
            << std::setw(8)
            << methodToString(route.method)
            << std::setw(30)
            << route.path
            << route.purpose
            << "\n";
    }
}


// ============================================================================
// 13. ROUTE PARAMETER DEMONSTRATION
// ============================================================================

void demonstrateRouteParameters() {
    RouteBuilder builder("http://127.0.0.1:8000");

    std::cout << "\n"
              << "ROUTE PARAMETER EXAMPLES\n"
              << "------------------------\n";

    std::cout
        << builder.item("api/users", "42")
        << "\n";

    std::cout
        << builder.item("api/users", "hello world")
        << "\n";

    std::cout
        << builder.item("api/users", "A/B")
        << "\n";
}


// ============================================================================
// 14. COMPLETE CRUD CASE STUDY
// ============================================================================

void demonstrateCrud(UserApi& api) {
    std::cout << "\n"
              << "CRUD CASE STUDY\n"
              << "---------------\n";

    // POST creates a resource and returns 201.
    UserCreateRequest createRequest{
        "Grace Hopper",
        "grace@example.com",
        40
    };

    const HttpResponse created =
        api.post(createRequest);

    printResponse("POST /api/users", created);

    // GET retrieves the newly created resource.
    printResponse(
        "GET /api/users/3",
        api.getItem(3)
    );

    // PUT replaces the complete resource representation.
    UserReplaceRequest replacement{
        "Grace Hopper",
        "grace@example.com",
        41
    };

    printResponse(
        "PUT /api/users/3",
        api.put(3, replacement)
    );

    // PATCH modifies only one field.
    UserPatchRequest patchRequest;
    patchRequest.age = 42;

    printResponse(
        "PATCH /api/users/3",
        api.patch(3, patchRequest)
    );

    // DELETE removes the resource.
    printResponse(
        "DELETE /api/users/3",
        api.deleteItem(3)
    );

    // A second GET demonstrates the resulting 404.
    printResponse(
        "GET /api/users/3 after DELETE",
        api.getItem(3)
    );
}


// ============================================================================
// 15. VALIDATION AND FAILURE CONDITIONS
// ============================================================================

void demonstrateFailures(UserApi& api) {
    std::cout << "\n"
              << "FAILURE CONDITIONS\n"
              << "------------------\n";

    UserCreateRequest invalid{
        "",
        "not-an-email",
        200
    };

    printResponse(
        "POST invalid user",
        api.post(invalid)
    );

    UserPatchRequest emptyPatch;

    printResponse(
        "PATCH with no fields",
        api.patch(1, emptyPatch)
    );

    printResponse(
        "GET nonexistent user",
        api.getItem(9999)
    );

    UserCreateRequest duplicateEmail{
        "Another Ada",
        "ada@example.com",
        30
    };

    printResponse(
        "POST duplicate email",
        api.post(duplicateEmail)
    );
}


// ============================================================================
// 16. PAGINATION
// ============================================================================

void demonstratePagination(UserApi& api) {
    std::cout << "\n"
              << "PAGINATION\n"
              << "----------\n";

    printResponse(
        "GET /api/users?limit=1&offset=0",
        api.getCollection(1, 0)
    );

    printResponse(
        "GET /api/users?limit=1&offset=1",
        api.getCollection(1, 1)
    );

    printResponse(
        "GET /api/users?limit=100&offset=1000",
        api.getCollection(100, 1000)
    );
}


// ============================================================================
// 17. COMPLEXITY DISCUSSION
// ============================================================================

void printComplexityConsiderations() {
    std::cout << "\n"
              << "COMPLEXITY CONSIDERATIONS\n"
              << "-------------------------\n";

    std::cout
        << "The repository uses std::map, so lookup, insertion, and deletion "
        << "are O(log n).\n";

    std::cout
        << "Collection pagination over the complete map is O(n) in the number "
        << "of stored records.\n";

    std::cout
        << "A production database can use indexed primary keys to provide "
        << "efficient resource lookup at much larger scale.\n";

    std::cout
        << "HTTP/network/database latency generally dominates simple route "
        << "dispatch costs in API workloads.\n";

    std::cout
        << "Unbounded collection endpoints can cause memory, bandwidth, and "
        << "serialization problems, so pagination is important.\n";
}


// ============================================================================
// 18. DESIGN TRADE-OFFS
// ============================================================================

void printDesignTradeoffs() {
    std::cout << "\n"
              << "DESIGN TRADE-OFFS\n"
              << "-----------------\n";

    std::cout
        << "GET: safe retrieval, normally cache-friendly.\n";

    std::cout
        << "POST: suitable for creation, but repeated requests may create "
        << "multiple resources unless idempotency is explicitly designed.\n";

    std::cout
        << "PUT: complete replacement and normally idempotent.\n";

    std::cout
        << "PATCH: smaller partial changes, but semantics depend on the "
        << "chosen patch model.\n";

    std::cout
        << "DELETE: resource removal; repeated deletion may produce 404 even "
        << "though the desired end state is already achieved.\n";

    std::cout
        << "In-memory state is useful for demonstration but is not durable "
        << "across process restarts.\n";
}


// ============================================================================
// 19. SECURITY CONSIDERATIONS
// ============================================================================

void printSecurityConsiderations() {
    std::cout << "\n"
              << "SECURITY CONSIDERATIONS\n"
              << "-----------------------\n";

    std::cout
        << "Route parameters, query parameters, and request bodies are all "
        << "untrusted input.\n";

    std::cout
        << "Authentication establishes identity; authorization determines "
        << "whether that identity can access a particular resource.\n";

    std::cout
        << "An endpoint such as /users/{id} must not assume that possession "
        << "of an ID grants permission to read or modify that user.\n";

    std::cout
        << "HTTPS protects data in transit.\n";

    std::cout
        << "Production APIs should apply rate limits, structured logging, "
        << "safe error responses, and appropriate audit controls.\n";
}


// ============================================================================
// 20. MAIN
// ============================================================================

int main() {
    std::cout
        << "============================================================\n"
        << "FASTAPI ROUTING C++ CASE STUDY\n"
        << "============================================================\n";

    printRoutingTable();
    demonstrateRouteParameters();

    UserApi api;

    printResponse(
        "Initial GET /api/users",
        api.getCollection(20, 0)
    );

    demonstrateCrud(api);
    demonstrateFailures(api);
    demonstratePagination(api);
    printComplexityConsiderations();
    printDesignTradeoffs();
    printSecurityConsiderations();

    std::cout << "\n"
              << "Case study completed successfully.\n";

    return 0;
}
