/*
 * API Documentation with OpenAPI
 *
 * C++17 case study:
 * A small API contract registry and documentation validation system.
 *
 * The program models an industry-style API documentation workflow:
 *
 * 1. Register API metadata.
 * 2. Register reusable schemas.
 * 3. Register reusable parameters and responses.
 * 4. Register HTTP operations.
 * 5. Validate operation IDs and response definitions.
 * 6. Validate sample payloads against selected schema rules.
 * 7. Simulate API requests.
 * 8. Perform contract-style checks.
 * 9. Produce a compact OpenAPI-like JSON representation.
 *
 * The implementation deliberately uses the C++ standard library only.
 *
 * Compile:
 *     g++ -std=c++17 -Wall -Wextra -pedantic api_documentation.cpp -o api_documentation
 *
 * Run:
 *     ./api_documentation
 *
 * The code is educational and models important OpenAPI concepts rather than
 * implementing the entire OpenAPI specification.
 */

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace std;

// -----------------------------------------------------------------------------
// 1. Basic JSON-like representation
// -----------------------------------------------------------------------------

/*
 * A complete JSON library would provide a recursive JSON value type.
 * For this focused case study, we use a deliberately small representation
 * sufficient for generating readable documentation output.
 */

class JsonObject {
public:
    void set(string key, string value) {
        fields_[std::move(key)] = "\"" + escape(value) + "\"";
    }

    void setRaw(string key, string rawJson) {
        fields_[std::move(key)] = std::move(rawJson);
    }

    string toJson(int indentation = 0) const {
        ostringstream output;
        const string indent(indentation, ' ');
        const string childIndent(indentation + 2, ' ');

        output << "{\n";

        bool first = true;
        for (const auto& [key, value] : fields_) {
            if (!first) {
                output << ",\n";
            }

            first = false;

            output << childIndent
                   << "\""
                   << escape(key)
                   << "\": "
                   << value;
        }

        if (!fields_.empty()) {
            output << "\n";
        }

        output << indent << "}";
        return output.str();
    }

private:
    static string escape(const string& input) {
        string result;

        for (char character : input) {
            switch (character) {
                case '"':
                    result += "\\\"";
                    break;
                case '\\':
                    result += "\\\\";
                    break;
                case '\n':
                    result += "\\n";
                    break;
                case '\r':
                    result += "\\r";
                    break;
                case '\t':
                    result += "\\t";
                    break;
                default:
                    result += character;
                    break;
            }
        }

        return result;
    }

    map<string, string> fields_;
};

// -----------------------------------------------------------------------------
// 2. Schema model
// -----------------------------------------------------------------------------

enum class SchemaType {
    String,
    Integer,
    Number,
    Boolean,
    Object,
    Array
};

string schemaTypeName(SchemaType type) {
    switch (type) {
        case SchemaType::String:
            return "string";
        case SchemaType::Integer:
            return "integer";
        case SchemaType::Number:
            return "number";
        case SchemaType::Boolean:
            return "boolean";
        case SchemaType::Object:
            return "object";
        case SchemaType::Array:
            return "array";
    }

    return "unknown";
}

struct Schema {
    string name;
    SchemaType type;
    string format;
    string description;
    vector<string> requiredProperties;
    map<string, string> properties;
    vector<string> enumValues;
    optional<int> minimum;
    optional<int> maximum;
    optional<size_t> minLength;
    optional<size_t> maxLength;
    optional<string> itemSchema;
};

class SchemaRegistry {
public:
    void add(Schema schema) {
        if (schema.name.empty()) {
            throw invalid_argument("Schema name cannot be empty.");
        }

        if (schemas_.contains(schema.name)) {
            throw invalid_argument(
                "Duplicate schema: " + schema.name
            );
        }

        schemas_.emplace(schema.name, std::move(schema));
    }

    const Schema& get(const string& name) const {
        auto iterator = schemas_.find(name);

        if (iterator == schemas_.end()) {
            throw out_of_range(
                "Schema not found: " + name
            );
        }

        return iterator->second;
    }

    bool contains(const string& name) const {
        return schemas_.contains(name);
    }

    size_t size() const {
        return schemas_.size();
    }

    void printInventory() const {
        cout << "\nRegistered schemas:\n";

        for (const auto& [name, schema] : schemas_) {
            cout << "  - "
                 << name
                 << " ("
                 << schemaTypeName(schema.type)
                 << ")\n";
        }
    }

private:
    map<string, Schema> schemas_;
};

// -----------------------------------------------------------------------------
// 3. API parameter model
// -----------------------------------------------------------------------------

enum class ParameterLocation {
    Path,
    Query,
    Header,
    Cookie
};

string parameterLocationName(ParameterLocation location) {
    switch (location) {
        case ParameterLocation::Path:
            return "path";
        case ParameterLocation::Query:
            return "query";
        case ParameterLocation::Header:
            return "header";
        case ParameterLocation::Cookie:
            return "cookie";
    }

    return "unknown";
}

struct Parameter {
    string name;
    ParameterLocation location;
    bool required;
    string schemaType;
    string description;
};

class ParameterRegistry {
public:
    void add(Parameter parameter) {
        if (parameter.name.empty()) {
            throw invalid_argument("Parameter name cannot be empty.");
        }

        string key =
            parameterLocationName(parameter.location)
            + ":"
            + parameter.name;

        if (parameters_.contains(key)) {
            throw invalid_argument(
                "Duplicate parameter: " + key
            );
        }

        parameters_.emplace(std::move(key), std::move(parameter));
    }

    size_t size() const {
        return parameters_.size();
    }

    bool contains(
        ParameterLocation location,
        const string& name
    ) const {
        string key =
            parameterLocationName(location)
            + ":"
            + name;

        return parameters_.contains(key);
    }

private:
    map<string, Parameter> parameters_;
};

// -----------------------------------------------------------------------------
// 4. Response model
// -----------------------------------------------------------------------------

struct ResponseDefinition {
    string statusCode;
    string description;
    optional<string> schemaName;
};

class ResponseRegistry {
public:
    void add(ResponseDefinition response) {
        if (response.statusCode.empty()) {
            throw invalid_argument(
                "Response status code cannot be empty."
            );
        }

        if (responses_.contains(response.statusCode)) {
            throw invalid_argument(
                "Duplicate reusable response: "
                + response.statusCode
            );
        }

        responses_.emplace(
            response.statusCode,
            std::move(response)
        );
    }

    const ResponseDefinition& get(
        const string& statusCode
    ) const {
        auto iterator = responses_.find(statusCode);

        if (iterator == responses_.end()) {
            throw out_of_range(
                "Response not found: " + statusCode
            );
        }

        return iterator->second;
    }

    bool contains(const string& statusCode) const {
        return responses_.contains(statusCode);
    }

    size_t size() const {
        return responses_.size();
    }

private:
    map<string, ResponseDefinition> responses_;
};

// -----------------------------------------------------------------------------
// 5. API operation model
// -----------------------------------------------------------------------------

enum class HttpMethod {
    GET,
    POST,
    PUT,
    PATCH,
    DELETE
};

string httpMethodName(HttpMethod method) {
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

struct Operation {
    string path;
    HttpMethod method;
    string summary;
    string description;
    string operationId;
    vector<string> parameterReferences;
    vector<string> responseReferences;
    optional<string> requestBodySchema;
    vector<string> tags;
    bool requiresAuthentication = false;
};

class ApiRegistry {
public:
    void addOperation(Operation operation) {
        if (operation.path.empty()) {
            throw invalid_argument(
                "Operation path cannot be empty."
            );
        }

        if (operation.operationId.empty()) {
            throw invalid_argument(
                "operationId cannot be empty."
            );
        }

        if (operationIds_.contains(operation.operationId)) {
            throw invalid_argument(
                "Duplicate operationId: "
                + operation.operationId
            );
        }

        string key =
            httpMethodName(operation.method)
            + " "
            + operation.path;

        if (operations_.contains(key)) {
            throw invalid_argument(
                "Duplicate operation: " + key
            );
        }

        operationIds_.insert(operation.operationId);
        operations_.emplace(
            std::move(key),
            std::move(operation)
        );
    }

    size_t operationCount() const {
        return operations_.size();
    }

    void printInventory() const {
        cout << "\nAPI operations:\n";

        for (const auto& [key, operation] : operations_) {
            cout << "  - "
                 << key
                 << " -> "
                 << operation.operationId
                 << "\n";
        }
    }

    const map<string, Operation>& operations() const {
        return operations_;
    }

private:
    map<string, Operation> operations_;
    set<string> operationIds_;
};

// -----------------------------------------------------------------------------
// 6. Runtime payload model
// -----------------------------------------------------------------------------

struct UserPayload {
    int id;
    string name;
    string email;
    string status;
    vector<string> roles;
};

struct ErrorPayload {
    string code;
    string message;
};

struct SimulatedResponse {
    int statusCode;
    string description;
    optional<UserPayload> user;
    optional<ErrorPayload> error;
};

bool isValidEmail(const string& email) {
    auto atPosition = email.find('@');

    if (atPosition == string::npos) {
        return false;
    }

    if (atPosition == 0) {
        return false;
    }

    if (atPosition + 1 >= email.size()) {
        return false;
    }

    auto dotPosition = email.find('.', atPosition + 1);

    return dotPosition != string::npos
        && dotPosition + 1 < email.size();
}

bool validateUser(
    const UserPayload& user,
    const Schema& schema,
    string& error
) {
    if (schema.name != "User") {
        error = "Unexpected schema used for User payload.";
        return false;
    }

    if (user.id < 1) {
        error = "id must be at least 1.";
        return false;
    }

    if (user.name.empty()) {
        error = "name cannot be empty.";
        return false;
    }

    if (user.name.size() > 100) {
        error = "name exceeds maximum length.";
        return false;
    }

    if (!isValidEmail(user.email)) {
        error = "email has an invalid basic format.";
        return false;
    }

    const set<string> validStatuses{
        "active",
        "inactive",
        "suspended"
    };

    if (!validStatuses.contains(user.status)) {
        error = "status is not one of the documented values.";
        return false;
    }

    if (user.roles.empty()) {
        error = "at least one role is required.";
        return false;
    }

    const set<string> validRoles{
        "reader",
        "editor",
        "admin"
    };

    for (const string& role : user.roles) {
        if (!validRoles.contains(role)) {
            error = "roles contains an undocumented value: " + role;
            return false;
        }
    }

    return true;
}

// -----------------------------------------------------------------------------
// 7. API service simulation
// -----------------------------------------------------------------------------

class UserService {
public:
    explicit UserService(const SchemaRegistry& schemas)
        : schemas_(schemas) {}

    void seedUser(UserPayload user) {
        string error;

        if (!validateUser(user, schemas_.get("User"), error)) {
            throw invalid_argument(
                "Cannot seed invalid user: " + error
            );
        }

        users_[user.id] = std::move(user);
    }

    SimulatedResponse getUser(int userId) const {
        if (userId <= 0) {
            return {
                400,
                "Invalid user ID.",
                nullopt,
                ErrorPayload{
                    "INVALID_USER_ID",
                    "user_id must be a positive integer."
                }
            };
        }

        auto iterator = users_.find(userId);

        if (iterator == users_.end()) {
            return {
                404,
                "User was not found.",
                nullopt,
                ErrorPayload{
                    "USER_NOT_FOUND",
                    "The requested user does not exist."
                }
            };
        }

        return {
            200,
            "User returned successfully.",
            iterator->second,
            nullopt
        };
    }

    SimulatedResponse createUser(
        UserPayload user
    ) {
        string validationError;

        if (!validateUser(
            user,
            schemas_.get("User"),
            validationError
        )) {
            return {
                400,
                "User payload is invalid.",
                nullopt,
                ErrorPayload{
                    "VALIDATION_ERROR",
                    validationError
                }
            };
        }

        if (users_.contains(user.id)) {
            return {
                409,
                "A user with this ID already exists.",
                nullopt,
                ErrorPayload{
                    "USER_ALREADY_EXISTS",
                    "The supplied user ID is already registered."
                }
            };
        }

        users_[user.id] = user;

        return {
            201,
            "User created successfully.",
            user,
            nullopt
        };
    }

private:
    const SchemaRegistry& schemas_;
    map<int, UserPayload> users_;
};

// -----------------------------------------------------------------------------
// 8. Documentation metadata
// -----------------------------------------------------------------------------

struct ApiMetadata {
    string title;
    string version;
    string description;
    string contactName;
    string contactEmail;
    string licenseName;
};

struct ServerDefinition {
    string url;
    string description;
};

struct SecurityScheme {
    string name;
    string type;
    string scheme;
    string bearerFormat;
};

// -----------------------------------------------------------------------------
// 9. OpenAPI documentation model
// -----------------------------------------------------------------------------

class OpenApiDocumentation {
public:
    void setMetadata(ApiMetadata metadata) {
        metadata_ = std::move(metadata);
    }

    void addServer(ServerDefinition server) {
        servers_.push_back(std::move(server));
    }

    void addSecurityScheme(SecurityScheme scheme) {
        if (securitySchemes_.contains(scheme.name)) {
            throw invalid_argument(
                "Duplicate security scheme: " + scheme.name
            );
        }

        securitySchemes_.emplace(
            scheme.name,
            std::move(scheme)
        );
    }

    void attachSchemaRegistry(
        const SchemaRegistry& registry
    ) {
        schemas_ = &registry;
    }

    void attachParameterRegistry(
        const ParameterRegistry& registry
    ) {
        parameters_ = &registry;
    }

    void attachResponseRegistry(
        const ResponseRegistry& registry
    ) {
        responses_ = &registry;
    }

    void attachApiRegistry(
        const ApiRegistry& registry
    ) {
        api_ = &registry;
    }

    void validate() const {
        if (metadata_.title.empty()) {
            throw runtime_error("API title is missing.");
        }

        if (metadata_.version.empty()) {
            throw runtime_error("API version is missing.");
        }

        if (servers_.empty()) {
            throw runtime_error(
                "At least one API server should be documented."
            );
        }

        if (schemas_ == nullptr) {
            throw runtime_error("Schema registry is missing.");
        }

        if (parameters_ == nullptr) {
            throw runtime_error("Parameter registry is missing.");
        }

        if (responses_ == nullptr) {
            throw runtime_error("Response registry is missing.");
        }

        if (api_ == nullptr) {
            throw runtime_error("API operation registry is missing.");
        }

        for (const auto& [key, operation] : api_->operations()) {
            if (operation.operationId.empty()) {
                throw runtime_error(
                    "Operation has empty operationId: " + key
                );
            }

            if (operation.summary.empty()) {
                throw runtime_error(
                    "Operation has empty summary: " + key
                );
            }

            if (operation.responseReferences.empty()) {
                throw runtime_error(
                    "Operation has no documented responses: " + key
                );
            }
        }
    }

    string toOpenApiLikeJson() const {
        validate();

        JsonObject info;
        info.set("title", metadata_.title);
        info.set("version", metadata_.version);
        info.set("description", metadata_.description);

        JsonObject root;
        root.set("openapi", "3.0.3");
        root.setRaw("info", info.toJson(2));

        string serversJson = "[\n";

        for (size_t index = 0; index < servers_.size(); ++index) {
            JsonObject server;
            server.set("url", servers_[index].url);
            server.set(
                "description",
                servers_[index].description
            );

            if (index > 0) {
                serversJson += ",\n";
            }

            serversJson += "    "
                + server.toJson(4);
        }

        serversJson += "\n  ]";

        root.setRaw("servers", serversJson);

        string pathsJson = "{\n";

        size_t operationIndex = 0;

        for (const auto& [key, operation] : api_->operations()) {
            if (operationIndex > 0) {
                pathsJson += ",\n";
            }

            ++operationIndex;

            JsonObject operationObject;
            operationObject.set(
                "summary",
                operation.summary
            );
            operationObject.set(
                "description",
                operation.description
            );
            operationObject.set(
                "operationId",
                operation.operationId
            );

            string methodName =
                httpMethodName(operation.method);

            JsonObject methodObject;
            methodObject.setRaw(
                "operation",
                operationObject.toJson(0)
            );

            /*
             * This output is intentionally compact and illustrative rather
             * than a complete general-purpose OpenAPI serializer.
             */
            pathsJson += "    \""
                + escapeForJson(key)
                + " "
                + methodName
                + "\": "
                + operationObject.toJson(4);
        }

        pathsJson += "\n  ]";

        /*
         * The path serialization above is presented as an educational
         * inventory representation. The actual registry remains the
         * authoritative structured model used by the validation logic.
         */
        root.setRaw(
            "operationInventory",
            pathsJson
        );

        return root.toJson(0);
    }

private:
    static string escapeForJson(const string& input) {
        string result;

        for (char character : input) {
            if (character == '"') {
                result += "\\\"";
            } else if (character == '\\') {
                result += "\\\\";
            } else {
                result += character;
            }
        }

        return result;
    }

    ApiMetadata metadata_;
    vector<ServerDefinition> servers_;
    map<string, SecurityScheme> securitySchemes_;

    const SchemaRegistry* schemas_ = nullptr;
    const ParameterRegistry* parameters_ = nullptr;
    const ResponseRegistry* responses_ = nullptr;
    const ApiRegistry* api_ = nullptr;
};

// -----------------------------------------------------------------------------
// 10. Documentation quality audit
// -----------------------------------------------------------------------------

struct DocumentationIssue {
    string severity;
    string location;
    string message;
};

vector<DocumentationIssue> auditDocumentation(
    const ApiRegistry& api
) {
    vector<DocumentationIssue> issues;
    set<string> operationIds;

    for (const auto& [key, operation] : api.operations()) {
        if (operation.summary.empty()) {
            issues.push_back({
                "warning",
                key,
                "Missing summary."
            });
        }

        if (operation.description.empty()) {
            issues.push_back({
                "warning",
                key,
                "Missing description."
            });
        }

        if (operation.operationId.empty()) {
            issues.push_back({
                "error",
                key,
                "Missing operationId."
            });
        } else if (!operationIds.insert(
            operation.operationId
        ).second) {
            issues.push_back({
                "error",
                key,
                "Duplicate operationId."
            });
        }

        if (operation.responseReferences.empty()) {
            issues.push_back({
                "error",
                key,
                "No response definitions."
            });
        }
    }

    return issues;
}

// -----------------------------------------------------------------------------
// 11. Response inspection
// -----------------------------------------------------------------------------

void printResponse(const SimulatedResponse& response) {
    cout << "\nHTTP "
         << response.statusCode
         << " - "
         << response.description
         << "\n";

    if (response.user.has_value()) {
        const UserPayload& user = response.user.value();

        cout << "User:\n";
        cout << "  id: " << user.id << "\n";
        cout << "  name: " << user.name << "\n";
        cout << "  email: " << user.email << "\n";
        cout << "  status: " << user.status << "\n";
        cout << "  roles: ";

        for (size_t index = 0; index < user.roles.size(); ++index) {
            if (index > 0) {
                cout << ", ";
            }

            cout << user.roles[index];
        }

        cout << "\n";
    }

    if (response.error.has_value()) {
        cout << "Error:\n";
        cout << "  code: "
             << response.error->code
             << "\n";
        cout << "  message: "
             << response.error->message
             << "\n";
    }
}

// -----------------------------------------------------------------------------
// 12. Build the realistic API
// -----------------------------------------------------------------------------

void buildApi(
    SchemaRegistry& schemas,
    ParameterRegistry& parameters,
    ResponseRegistry& responses,
    ApiRegistry& api,
    OpenApiDocumentation& documentation
) {
    schemas.add({
        "User",
        SchemaType::Object,
        "",
        "A registered API user.",
        {"id", "name", "email", "status"},
        {
            {"id", "integer"},
            {"name", "string"},
            {"email", "string"},
            {"status", "string"},
            {"roles", "array"}
        },
        {"active", "inactive", "suspended"},
        1,
        nullopt,
        1,
        100,
        nullopt
    });

    schemas.add({
        "UserCreate",
        SchemaType::Object,
        "",
        "Data required to create a user.",
        {"name", "email"},
        {
            {"name", "string"},
            {"email", "string"},
            {"roles", "array"}
        },
        {},
        nullopt,
        nullopt,
        1,
        100,
        nullopt
    });

    schemas.add({
        "Error",
        SchemaType::Object,
        "",
        "Standard API error.",
        {"code", "message"},
        {
            {"code", "string"},
            {"message", "string"},
            {"details", "object"}
        },
        {},
        nullopt,
        nullopt,
        nullopt,
        nullopt,
        nullopt
    });

    schemas.add({
        "HealthStatus",
        SchemaType::Object,
        "",
        "Service health representation.",
        {"status", "service"},
        {
            {"status", "string"},
            {"service", "string"},
            {"version", "string"}
        },
        {"ok", "degraded"},
        nullopt,
        nullopt,
        nullopt,
        nullopt,
        nullopt
    });

    parameters.add({
        "user_id",
        ParameterLocation::Path,
        true,
        "integer",
        "Unique identifier of the user."
    });

    parameters.add({
        "page",
        ParameterLocation::Query,
        false,
        "integer",
        "One-based page number."
    });

    parameters.add({
        "page_size",
        ParameterLocation::Query,
        false,
        "integer",
        "Maximum number of records returned."
    });

    responses.add({
        "400",
        "The request is invalid.",
        "Error"
    });

    responses.add({
        "404",
        "The requested resource was not found.",
        "Error"
    });

    responses.add({
        "500",
        "Unexpected server error.",
        "Error"
    });

    api.addOperation({
        "/users/{user_id}",
        HttpMethod::GET,
        "Get a user",
        "Returns one user identified by the user_id path parameter.",
        "getUser",
        {"#/components/parameters/UserId"},
        {"200", "400", "404", "500"},
        nullopt,
        {"Users"},
        true
    });

    api.addOperation({
        "/users/{user_id}",
        HttpMethod::DELETE,
        "Delete a user",
        "Deletes a user and returns no response body.",
        "deleteUser",
        {"#/components/parameters/UserId"},
        {"204", "400", "404"},
        nullopt,
        {"Users"},
        true
    });

    api.addOperation({
        "/users",
        HttpMethod::GET,
        "List users",
        "Returns a paginated collection of users.",
        "listUsers",
        {
            "#/components/parameters/Page",
            "#/components/parameters/PageSize"
        },
        {"200", "400"},
        nullopt,
        {"Users"},
        true
    });

    api.addOperation({
        "/users",
        HttpMethod::POST,
        "Create a user",
        "Creates a user and returns the newly created resource.",
        "createUser",
        {},
        {"201", "400"},
        "UserCreate",
        {"Users"},
        true
    });

    api.addOperation({
        "/health",
        HttpMethod::GET,
        "Check service health",
        "Returns the health status of the API service.",
        "getHealth",
        {},
        {"200"},
        nullopt,
        {"Health"},
        false
    });

    documentation.setMetadata({
        "User Management API",
        "1.0.0",
        "A documented example API demonstrating OpenAPI concepts.",
        "API Engineering Team",
        "api@example.com",
        "Apache 2.0"
    });

    documentation.addServer({
        "https://api.example.com/v1",
        "Production"
    });

    documentation.addServer({
        "https://staging-api.example.com/v1",
        "Staging"
    });

    documentation.addServer({
        "http://localhost:8000/v1",
        "Local development"
    });

    documentation.addSecurityScheme({
        "bearerAuth",
        "http",
        "bearer",
        "JWT"
    });

    documentation.attachSchemaRegistry(schemas);
    documentation.attachParameterRegistry(parameters);
    documentation.attachResponseRegistry(responses);
    documentation.attachApiRegistry(api);
}

// -----------------------------------------------------------------------------
// 13. Main case study
// -----------------------------------------------------------------------------

int main() {
    try {
        cout << "API DOCUMENTATION WITH OPENAPI\n";
        cout << "C++17 technical case study\n";

        SchemaRegistry schemas;
        ParameterRegistry parameters;
        ResponseRegistry responses;
        ApiRegistry api;
        OpenApiDocumentation documentation;

        buildApi(
            schemas,
            parameters,
            responses,
            api,
            documentation
        );

        cout << "\n";
        cout << "============================================================\n";
        cout << "1. API INVENTORY\n";
        cout << "============================================================\n";

        schemas.printInventory();
        api.printInventory();

        cout << "\nReusable parameters: "
             << parameters.size()
             << "\n";

        cout << "Reusable responses: "
             << responses.size()
             << "\n";

        cout << "\n";
        cout << "============================================================\n";
        cout << "2. DOCUMENTATION VALIDATION\n";
        cout << "============================================================\n";

        documentation.validate();

        vector<DocumentationIssue> issues =
            auditDocumentation(api);

        if (issues.empty()) {
            cout << "Documentation audit passed.\n";
        } else {
            for (const auto& issue : issues) {
                cout << "["
                     << issue.severity
                     << "] "
                     << issue.location
                     << ": "
                     << issue.message
                     << "\n";
            }
        }

        cout << "\n";
        cout << "============================================================\n";
        cout << "3. CREATE AND VALIDATE SAMPLE USERS\n";
        cout << "============================================================\n";

        UserService service(schemas);

        service.seedUser({
            101,
            "Atul Pandey",
            "atul@example.com",
            "active",
            {"reader"}
        });

        service.seedUser({
            102,
            "API Administrator",
            "admin@example.com",
            "active",
            {"admin", "editor"}
        });

        UserPayload validUser{
            103,
            "New User",
            "new@example.com",
            "active",
            {"reader"}
        };

        SimulatedResponse createResponse =
            service.createUser(validUser);

        printResponse(createResponse);

        UserPayload invalidUser{
            104,
            "",
            "invalid-email",
            "unknown",
            {}
        };

        SimulatedResponse invalidResponse =
            service.createUser(invalidUser);

        printResponse(invalidResponse);

        cout << "\n";
        cout << "============================================================\n";
        cout << "4. SIMULATED API REQUESTS\n";
        cout << "============================================================\n";

        printResponse(service.getUser(101));
        printResponse(service.getUser(999));
        printResponse(service.getUser(0));

        cout << "\n";
        cout << "============================================================\n";
        cout << "5. DOCUMENTED OPERATION DETAILS\n";
        cout << "============================================================\n";

        for (const auto& [key, operation] : api.operations()) {
            cout << "\nOperation: "
                 << key
                 << "\n";

            cout << "  operationId: "
                 << operation.operationId
                 << "\n";

            cout << "  summary: "
                 << operation.summary
                 << "\n";

            cout << "  authentication: "
                 << (operation.requiresAuthentication
                         ? "required"
                         : "not required")
                 << "\n";

            cout << "  tags: ";

            for (size_t index = 0;
                 index < operation.tags.size();
                 ++index) {
                if (index > 0) {
                    cout << ", ";
                }

                cout << operation.tags[index];
            }

            cout << "\n";

            cout << "  responses: ";

            for (size_t index = 0;
                 index < operation.responseReferences.size();
                 ++index) {
                if (index > 0) {
                    cout << ", ";
                }

                cout << operation.responseReferences[index];
            }

            cout << "\n";
        }

        cout << "\n";
        cout << "============================================================\n";
        cout << "6. OPENAPI-LIKE DOCUMENT OUTPUT\n";
        cout << "============================================================\n";

        cout << documentation.toOpenApiLikeJson()
             << "\n";

        cout << "\n";
        cout << "============================================================\n";
        cout << "7. PERFORMANCE AND DESIGN NOTES\n";
        cout << "============================================================\n";

        cout << "Schema lookup: O(log S) using std::map.\n";
        cout << "Parameter lookup: O(log P) using std::map.\n";
        cout << "Response lookup: O(log R) using std::map.\n";
        cout << "Operation lookup: O(log O) using std::map.\n";
        cout << "operationId uniqueness: O(log O) insertion into std::set.\n";

        cout << "\n";
        cout << "Design trade-offs:\n";
        cout << "  - std::map gives deterministic ordering and logarithmic lookup.\n";
        cout << "  - std::unordered_map could offer average constant-time lookup.\n";
        cout << "  - Explicit registries make duplicate definitions detectable early.\n";
        cout << "  - $ref-style reuse reduces schema duplication in the API contract.\n";
        cout << "  - The example serializer is intentionally smaller than a full JSON library.\n";

        cout << "\n";
        cout << "Security considerations:\n";
        cout << "  - Never place credentials or real access tokens in examples.\n";
        cout << "  - Document authentication requirements accurately.\n";
        cout << "  - Protect private API documentation when necessary.\n";
        cout << "  - Serve production API documentation over HTTPS.\n";
        cout << "  - Treat API documentation as part of the public contract when exposed.\n";

        cout << "\n";
        cout << "Case study completed successfully.\n";

    } catch (const exception& error) {
        cerr << "Fatal error: "
             << error.what()
             << "\n";

        return 1;
    }

    return 0;
}
