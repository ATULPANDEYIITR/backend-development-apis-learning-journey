#include <algorithm>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
    REST API Design Case Study

    Scenario:
    A company operates a project-management API. Clients can access users,
    projects, and tasks through resource-oriented HTTP endpoints.

    This C++17 program models a governance layer that determines how an HTTP
    request should be interpreted, validates resource relationships, performs
    CRUD operations, and constructs consistent responses.

    The implementation deliberately differs from a framework-oriented server:
    the focus is the internal design of a REST resource layer and the rules
    required to preserve HTTP semantics.
*/

using namespace std;


// -----------------------------------------------------------------------------
// HTTP primitives
// -----------------------------------------------------------------------------

enum class HttpMethod {
    GET,
    POST,
    PUT,
    PATCH,
    DELETE_,
    UNKNOWN
};

string methodToString(HttpMethod method) {
    switch (method) {
        case HttpMethod::GET:
            return "GET";
        case HttpMethod::POST:
            return "POST";
        case HttpMethod::PUT:
            return "PUT";
        case HttpMethod::PATCH:
            return "PATCH";
        case HttpMethod::DELETE_:
            return "DELETE";
        default:
            return "UNKNOWN";
    }
}

HttpMethod parseMethod(const string& method) {
    if (method == "GET") return HttpMethod::GET;
    if (method == "POST") return HttpMethod::POST;
    if (method == "PUT") return HttpMethod::PUT;
    if (method == "PATCH") return HttpMethod::PATCH;
    if (method == "DELETE") return HttpMethod::DELETE_;
    return HttpMethod::UNKNOWN;
}


enum class StatusCode {
    OK = 200,
    CREATED = 201,
    NO_CONTENT = 204,
    BAD_REQUEST = 400,
    UNAUTHORIZED = 401,
    FORBIDDEN = 403,
    NOT_FOUND = 404,
    METHOD_NOT_ALLOWED = 405,
    CONFLICT = 409,
    UNSUPPORTED_MEDIA_TYPE = 415,
    UNPROCESSABLE_ENTITY = 422,
    TOO_MANY_REQUESTS = 429,
    INTERNAL_SERVER_ERROR = 500,
    SERVICE_UNAVAILABLE = 503
};

int statusNumber(StatusCode status) {
    return static_cast<int>(status);
}

string statusText(StatusCode status) {
    switch (status) {
        case StatusCode::OK:
            return "OK";
        case StatusCode::CREATED:
            return "Created";
        case StatusCode::NO_CONTENT:
            return "No Content";
        case StatusCode::BAD_REQUEST:
            return "Bad Request";
        case StatusCode::UNAUTHORIZED:
            return "Unauthorized";
        case StatusCode::FORBIDDEN:
            return "Forbidden";
        case StatusCode::NOT_FOUND:
            return "Not Found";
        case StatusCode::METHOD_NOT_ALLOWED:
            return "Method Not Allowed";
        case StatusCode::CONFLICT:
            return "Conflict";
        case StatusCode::UNSUPPORTED_MEDIA_TYPE:
            return "Unsupported Media Type";
        case StatusCode::UNPROCESSABLE_ENTITY:
            return "Unprocessable Entity";
        case StatusCode::TOO_MANY_REQUESTS:
            return "Too Many Requests";
        case StatusCode::INTERNAL_SERVER_ERROR:
            return "Internal Server Error";
        case StatusCode::SERVICE_UNAVAILABLE:
            return "Service Unavailable";
        default:
            return "Unknown";
    }
}


// -----------------------------------------------------------------------------
// Request and response representations
// -----------------------------------------------------------------------------

struct HttpRequest {
    HttpMethod method;
    string path;
    string body;
    string contentType = "application/json";
};

struct HttpResponse {
    StatusCode status;
    map<string, string> headers;
    string body;
};


// -----------------------------------------------------------------------------
// Domain model
// -----------------------------------------------------------------------------

struct User {
    int id;
    string name;
    string email;
};

struct Project {
    int id;
    int ownerId;
    string name;
    string description;
};

struct Task {
    int id;
    int projectId;
    string title;
    string status;
};


// -----------------------------------------------------------------------------
// String and JSON-like helpers
// -----------------------------------------------------------------------------

string trim(const string& value) {
    const auto first = value.find_first_not_of(" \t\n\r");
    if (first == string::npos) {
        return "";
    }

    const auto last = value.find_last_not_of(" \t\n\r");
    return value.substr(first, last - first + 1);
}

string escapeJson(const string& value) {
    string result;

    for (char c : value) {
        switch (c) {
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
                result += c;
        }
    }

    return result;
}

string quote(const string& value) {
    return "\"" + escapeJson(value) + "\"";
}

string jsonStringField(
    const string& name,
    const string& value
) {
    return quote(name) + ":" + quote(value);
}

string jsonIntField(
    const string& name,
    int value
) {
    return quote(name) + ":" + to_string(value);
}

vector<string> splitPath(const string& path) {
    vector<string> parts;
    string current;

    for (char c : path) {
        if (c == '/') {
            if (!current.empty()) {
                parts.push_back(current);
                current.clear();
            }
        } else {
            current += c;
        }
    }

    if (!current.empty()) {
        parts.push_back(current);
    }

    return parts;
}

optional<int> parsePositiveId(const string& text) {
    if (text.empty()) {
        return nullopt;
    }

    for (char c : text) {
        if (!isdigit(static_cast<unsigned char>(c))) {
            return nullopt;
        }
    }

    try {
        const long long value = stoll(text);

        if (value <= 0 || value > 2147483647LL) {
            return nullopt;
        }

        return static_cast<int>(value);
    } catch (...) {
        return nullopt;
    }
}


// -----------------------------------------------------------------------------
// Response factory
// -----------------------------------------------------------------------------

class ResponseFactory {
public:
    static HttpResponse success(
        StatusCode status,
        const string& data,
        const string& location = ""
    ) {
        HttpResponse response{
            status,
            {
                {"Content-Type", "application/json"}
            },
            "{\"data\":" + data + "}"
        };

        if (!location.empty()) {
            response.headers["Location"] = location;
        }

        return response;
    }

    static HttpResponse noContent() {
        return HttpResponse{
            StatusCode::NO_CONTENT,
            {},
            ""
        };
    }

    static HttpResponse error(
        StatusCode status,
        const string& code,
        const string& message,
        const vector<string>& details = {}
    ) {
        ostringstream body;

        body << "{\"error\":{"
             << jsonStringField("code", code)
             << ","
             << jsonStringField("message", message);

        if (!details.empty()) {
            body << ",\"details\":[";

            for (size_t i = 0; i < details.size(); ++i) {
                if (i > 0) {
                    body << ",";
                }

                body << "{"
                     << jsonStringField("reason", details[i])
                     << "}";
            }

            body << "]";
        }

        body << "}}";

        return HttpResponse{
            status,
            {
                {"Content-Type", "application/problem+json"}
            },
            body.str()
        };
    }
};


// -----------------------------------------------------------------------------
// Request payload parser
// -----------------------------------------------------------------------------

class PayloadParser {
public:
    /*
        The case study intentionally avoids a third-party JSON dependency.
        The accepted payload format is a restricted object representation
        sufficient for the resource operations being demonstrated.

        A production implementation should use a standards-compliant JSON
        parser rather than regular expressions.
    */

    static optional<string> stringValue(
        const string& body,
        const string& field
    ) {
        const string pattern =
            "\"" + field + "\"\\s*:\\s*\"([^\"]*)\"";

        regex expression(pattern);
        smatch match;

        if (regex_search(body, match, expression)) {
            return match[1].str();
        }

        return nullopt;
    }

    static optional<int> integerValue(
        const string& body,
        const string& field
    ) {
        const string pattern =
            "\"" + field + "\"\\s*:\\s*(-?[0-9]+)";

        regex expression(pattern);
        smatch match;

        if (regex_search(body, match, expression)) {
            try {
                return stoi(match[1].str());
            } catch (...) {
                return nullopt;
            }
        }

        return nullopt;
    }
};


// -----------------------------------------------------------------------------
// Repository
// -----------------------------------------------------------------------------

class Repository {
private:
    unordered_map<int, User> users;
    unordered_map<int, Project> projects;
    unordered_map<int, Task> tasks;

    int nextUserId = 3;
    int nextProjectId = 103;
    int nextTaskId = 1004;

public:
    Repository() {
        users.emplace(
            1,
            User{
                1,
                "Atul Pandey",
                "atul@example.com"
            }
        );

        users.emplace(
            2,
            User{
                2,
                "Priya Sharma",
                "priya@example.com"
            }
        );

        projects.emplace(
            101,
            Project{
                101,
                1,
                "API Platform",
                "REST service architecture"
            }
        );

        projects.emplace(
            102,
            Project{
                102,
                1,
                "Reporting",
                "Operational reporting API"
            }
        );

        tasks.emplace(
            1001,
            Task{
                1001,
                101,
                "Define resources",
                "open"
            }
        );

        tasks.emplace(
            1002,
            Task{
                1002,
                101,
                "Validate payloads",
                "done"
            }
        );
    }

    const unordered_map<int, User>& getUsers() const {
        return users;
    }

    const unordered_map<int, Project>& getProjects() const {
        return projects;
    }

    const unordered_map<int, Task>& getTasks() const {
        return tasks;
    }

    User* findUser(int id) {
        auto iterator = users.find(id);

        if (iterator == users.end()) {
            return nullptr;
        }

        return &iterator->second;
    }

    Project* findProject(int id) {
        auto iterator = projects.find(id);

        if (iterator == projects.end()) {
            return nullptr;
        }

        return &iterator->second;
    }

    Task* findTask(int id) {
        auto iterator = tasks.find(id);

        if (iterator == tasks.end()) {
            return nullptr;
        }

        return &iterator->second;
    }

    bool emailExists(const string& email) const {
        for (const auto& [id, user] : users) {
            if (user.email == email) {
                return true;
            }
        }

        return false;
    }

    int createUser(string name, string email) {
        const int id = nextUserId++;

        users.emplace(
            id,
            User{id, move(name), move(email)}
        );

        return id;
    }

    int createProject(
        int ownerId,
        string name,
        string description
    ) {
        const int id = nextProjectId++;

        projects.emplace(
            id,
            Project{
                id,
                ownerId,
                move(name),
                move(description)
            }
        );

        return id;
    }

    int createTask(
        int projectId,
        string title,
        string status
    ) {
        const int id = nextTaskId++;

        tasks.emplace(
            id,
            Task{
                id,
                projectId,
                move(title),
                move(status)
            }
        );

        return id;
    }

    bool projectHasTasks(int projectId) const {
        return any_of(
            tasks.begin(),
            tasks.end(),
            [projectId](const auto& entry) {
                return entry.second.projectId == projectId;
            }
        );
    }

    vector<Project> projectsForUser(int userId) const {
        vector<Project> result;

        for (const auto& [id, project] : projects) {
            if (project.ownerId == userId) {
                result.push_back(project);
            }
        }

        return result;
    }

    vector<Task> tasksForProject(int projectId) const {
        vector<Task> result;

        for (const auto& [id, task] : tasks) {
            if (task.projectId == projectId) {
                result.push_back(task);
            }
        }

        return result;
    }

    bool eraseProject(int id) {
        return projects.erase(id) > 0;
    }

    bool eraseTask(int id) {
        return tasks.erase(id) > 0;
    }
};


// -----------------------------------------------------------------------------
// Serialization
// -----------------------------------------------------------------------------

string serialize(const User& user) {
    return "{"
        + jsonIntField("id", user.id)
        + ","
        + jsonStringField("name", user.name)
        + ","
        + jsonStringField("email", user.email)
        + "}";
}

string serialize(const Project& project) {
    return "{"
        + jsonIntField("id", project.id)
        + ","
        + jsonIntField("ownerId", project.ownerId)
        + ","
        + jsonStringField("name", project.name)
        + ","
        + jsonStringField("description", project.description)
        + "}";
}

string serialize(const Task& task) {
    return "{"
        + jsonIntField("id", task.id)
        + ","
        + jsonIntField("projectId", task.projectId)
        + ","
        + jsonStringField("title", task.title)
        + ","
        + jsonStringField("status", task.status)
        + "}";
}

template <typename T>
string serializeVector(const vector<T>& items) {
    ostringstream output;
    output << "[";

    for (size_t i = 0; i < items.size(); ++i) {
        if (i > 0) {
            output << ",";
        }

        output << serialize(items[i]);
    }

    output << "]";
    return output.str();
}


// -----------------------------------------------------------------------------
// Authorization
// -----------------------------------------------------------------------------

class AuthorizationService {
public:
    bool canModifyProject(
        const User& authenticatedUser,
        const Project& project
    ) const {
        return authenticatedUser.id == project.ownerId;
    }
};


// -----------------------------------------------------------------------------
// REST resource controller
// -----------------------------------------------------------------------------

class ProjectApi {
private:
    Repository& repository;
    AuthorizationService authorization;

    HttpResponse requireJson(const HttpRequest& request) const {
        if (request.contentType != "application/json") {
            return ResponseFactory::error(
                StatusCode::UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                "This endpoint requires application/json."
            );
        }

        return ResponseFactory::success(
            StatusCode::OK,
            "{}"
        );
    }

public:
    explicit ProjectApi(Repository& repository)
        : repository(repository) {}

    HttpResponse listUsers() {
        vector<User> users;

        for (const auto& [id, user] : repository.getUsers()) {
            users.push_back(user);
        }

        sort(
            users.begin(),
            users.end(),
            [](const User& left, const User& right) {
                return left.id < right.id;
            }
        );

        return ResponseFactory::success(
            StatusCode::OK,
            serializeVector(users)
        );
    }

    HttpResponse getUser(int userId) {
        User* user = repository.findUser(userId);

        if (user == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "USER_NOT_FOUND",
                "The requested user does not exist."
            );
        }

        return ResponseFactory::success(
            StatusCode::OK,
            serialize(*user)
        );
    }

    HttpResponse createUser(const HttpRequest& request) {
        if (request.contentType != "application/json") {
            return ResponseFactory::error(
                StatusCode::UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                "Expected application/json."
            );
        }

        const auto name =
            PayloadParser::stringValue(request.body, "name");

        const auto email =
            PayloadParser::stringValue(request.body, "email");

        vector<string> errors;

        if (!name.has_value() || trim(*name).empty()) {
            errors.push_back("name is required and must not be empty");
        }

        if (!email.has_value() || trim(*email).empty()) {
            errors.push_back("email is required and must not be empty");
        }

        if (!errors.empty()) {
            return ResponseFactory::error(
                StatusCode::UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "The user representation is invalid.",
                errors
            );
        }

        const string normalizedEmail = trim(*email);

        if (repository.emailExists(normalizedEmail)) {
            return ResponseFactory::error(
                StatusCode::CONFLICT,
                "EMAIL_ALREADY_EXISTS",
                "A user with this email already exists."
            );
        }

        const int id = repository.createUser(
            trim(*name),
            normalizedEmail
        );

        User* created = repository.findUser(id);

        return ResponseFactory::success(
            StatusCode::CREATED,
            serialize(*created),
            "/users/" + to_string(id)
        );
    }

    HttpResponse listUserProjects(int userId) {
        User* user = repository.findUser(userId);

        if (user == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "USER_NOT_FOUND",
                "The parent user does not exist."
            );
        }

        const vector<Project> projects =
            repository.projectsForUser(userId);

        return ResponseFactory::success(
            StatusCode::OK,
            serializeVector(projects)
        );
    }

    HttpResponse createUserProject(
        int userId,
        const HttpRequest& request
    ) {
        if (repository.findUser(userId) == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "USER_NOT_FOUND",
                "The parent user does not exist."
            );
        }

        if (request.contentType != "application/json") {
            return ResponseFactory::error(
                StatusCode::UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                "Expected application/json."
            );
        }

        const auto name =
            PayloadParser::stringValue(request.body, "name");

        const auto description =
            PayloadParser::stringValue(
                request.body,
                "description"
            );

        if (!name.has_value() || trim(*name).empty()) {
            return ResponseFactory::error(
                StatusCode::UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "Project name is required."
            );
        }

        const int projectId = repository.createProject(
            userId,
            trim(*name),
            description.has_value() ? trim(*description) : ""
        );

        Project* project = repository.findProject(projectId);

        return ResponseFactory::success(
            StatusCode::CREATED,
            serialize(*project),
            "/projects/" + to_string(projectId)
        );
    }

    HttpResponse getProject(int projectId) {
        Project* project =
            repository.findProject(projectId);

        if (project == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "The requested project does not exist."
            );
        }

        return ResponseFactory::success(
            StatusCode::OK,
            serialize(*project)
        );
    }

    HttpResponse deleteProject(
        int projectId,
        const User& authenticatedUser
    ) {
        Project* project =
            repository.findProject(projectId);

        if (project == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "The requested project does not exist."
            );
        }

        if (!authorization.canModifyProject(
            authenticatedUser,
            *project
        )) {
            return ResponseFactory::error(
                StatusCode::FORBIDDEN,
                "FORBIDDEN",
                "The authenticated user cannot modify this project."
            );
        }

        if (repository.projectHasTasks(projectId)) {
            return ResponseFactory::error(
                StatusCode::CONFLICT,
                "DEPENDENT_TASKS_EXIST",
                "The project cannot be deleted while tasks exist."
            );
        }

        repository.eraseProject(projectId);

        return ResponseFactory::noContent();
    }

    HttpResponse listProjectTasks(int projectId) {
        if (repository.findProject(projectId) == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "The parent project does not exist."
            );
        }

        const vector<Task> tasks =
            repository.tasksForProject(projectId);

        return ResponseFactory::success(
            StatusCode::OK,
            serializeVector(tasks)
        );
    }

    HttpResponse createProjectTask(
        int projectId,
        const HttpRequest& request
    ) {
        if (repository.findProject(projectId) == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "The parent project does not exist."
            );
        }

        if (request.contentType != "application/json") {
            return ResponseFactory::error(
                StatusCode::UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                "Expected application/json."
            );
        }

        const auto title =
            PayloadParser::stringValue(request.body, "title");

        const auto status =
            PayloadParser::stringValue(request.body, "status");

        if (!title.has_value() || trim(*title).empty()) {
            return ResponseFactory::error(
                StatusCode::UNPROCESSABLE_ENTITY,
                "VALIDATION_FAILED",
                "Task title is required."
            );
        }

        const string taskStatus =
            status.has_value()
                ? trim(*status)
                : "open";

        const vector<string> validStatuses{
            "open",
            "in_progress",
            "done"
        };

        if (
            find(
                validStatuses.begin(),
                validStatuses.end(),
                taskStatus
            ) == validStatuses.end()
        ) {
            return ResponseFactory::error(
                StatusCode::UNPROCESSABLE_ENTITY,
                "INVALID_TASK_STATUS",
                "Task status is not supported."
            );
        }

        const int taskId = repository.createTask(
            projectId,
            trim(*title),
            taskStatus
        );

        Task* task = repository.findTask(taskId);

        return ResponseFactory::success(
            StatusCode::CREATED,
            serialize(*task),
            "/tasks/" + to_string(taskId)
        );
    }

    HttpResponse patchTask(
        int taskId,
        const HttpRequest& request
    ) {
        Task* task = repository.findTask(taskId);

        if (task == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "TASK_NOT_FOUND",
                "The requested task does not exist."
            );
        }

        if (request.contentType != "application/json") {
            return ResponseFactory::error(
                StatusCode::UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                "Expected application/json."
            );
        }

        const auto title =
            PayloadParser::stringValue(request.body, "title");

        const auto status =
            PayloadParser::stringValue(request.body, "status");

        if (title.has_value()) {
            const string newTitle = trim(*title);

            if (newTitle.empty()) {
                return ResponseFactory::error(
                    StatusCode::UNPROCESSABLE_ENTITY,
                    "INVALID_TITLE",
                    "Task title cannot be empty."
                );
            }

            task->title = newTitle;
        }

        if (status.has_value()) {
            const vector<string> validStatuses{
                "open",
                "in_progress",
                "done"
            };

            const string newStatus = trim(*status);

            if (
                find(
                    validStatuses.begin(),
                    validStatuses.end(),
                    newStatus
                ) == validStatuses.end()
            ) {
                return ResponseFactory::error(
                    StatusCode::UNPROCESSABLE_ENTITY,
                    "INVALID_TASK_STATUS",
                    "Task status is not supported."
                );
            }

            task->status = newStatus;
        }

        return ResponseFactory::success(
            StatusCode::OK,
            serialize(*task)
        );
    }

    HttpResponse deleteTask(int taskId) {
        if (repository.findTask(taskId) == nullptr) {
            return ResponseFactory::error(
                StatusCode::NOT_FOUND,
                "TASK_NOT_FOUND",
                "The requested task does not exist."
            );
        }

        repository.eraseTask(taskId);

        return ResponseFactory::noContent();
    }
};


// -----------------------------------------------------------------------------
// API gateway/router
// -----------------------------------------------------------------------------

class ApiRouter {
private:
    Repository& repository;
    ProjectApi& api;

    HttpResponse unknownRoute() const {
        return ResponseFactory::error(
            StatusCode::NOT_FOUND,
            "ROUTE_NOT_FOUND",
            "No matching resource route exists."
        );
    }

public:
    ApiRouter(
        Repository& repository,
        ProjectApi& api
    )
        : repository(repository),
          api(api) {}

    HttpResponse dispatch(
        const HttpRequest& request,
        const User* authenticatedUser = nullptr
    ) {
        const vector<string> parts =
            splitPath(request.path);

        if (
            parts.size() == 1 &&
            parts[0] == "users"
        ) {
            if (request.method == HttpMethod::GET) {
                return api.listUsers();
            }

            if (request.method == HttpMethod::POST) {
                return api.createUser(request);
            }

            return ResponseFactory::error(
                StatusCode::METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "The /users collection does not support this method."
            );
        }

        if (
            parts.size() == 2 &&
            parts[0] == "users"
        ) {
            const auto userId =
                parsePositiveId(parts[1]);

            if (!userId.has_value()) {
                return ResponseFactory::error(
                    StatusCode::BAD_REQUEST,
                    "INVALID_IDENTIFIER",
                    "The user identifier is invalid."
                );
            }

            if (request.method == HttpMethod::GET) {
                return api.getUser(*userId);
            }

            return ResponseFactory::error(
                StatusCode::METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "The user item does not support this method."
            );
        }

        if (
            parts.size() == 3 &&
            parts[0] == "users" &&
            parts[2] == "projects"
        ) {
            const auto userId =
                parsePositiveId(parts[1]);

            if (!userId.has_value()) {
                return ResponseFactory::error(
                    StatusCode::BAD_REQUEST,
                    "INVALID_IDENTIFIER",
                    "The user identifier is invalid."
                );
            }

            if (request.method == HttpMethod::GET) {
                return api.listUserProjects(*userId);
            }

            if (request.method == HttpMethod::POST) {
                return api.createUserProject(
                    *userId,
                    request
                );
            }

            return ResponseFactory::error(
                StatusCode::METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "The nested project collection does not support this method."
            );
        }

        if (
            parts.size() == 2 &&
            parts[0] == "projects"
        ) {
            const auto projectId =
                parsePositiveId(parts[1]);

            if (!projectId.has_value()) {
                return ResponseFactory::error(
                    StatusCode::BAD_REQUEST,
                    "INVALID_IDENTIFIER",
                    "The project identifier is invalid."
                );
            }

            if (request.method == HttpMethod::GET) {
                return api.getProject(*projectId);
            }

            if (request.method == HttpMethod::DELETE_) {
                if (authenticatedUser == nullptr) {
                    return ResponseFactory::error(
                        StatusCode::UNAUTHORIZED,
                        "AUTHENTICATION_REQUIRED",
                        "Authentication is required."
                    );
                }

                return api.deleteProject(
                    *projectId,
                    *authenticatedUser
                );
            }

            return ResponseFactory::error(
                StatusCode::METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "Unsupported project operation."
            );
        }

        if (
            parts.size() == 3 &&
            parts[0] == "projects" &&
            parts[2] == "tasks"
        ) {
            const auto projectId =
                parsePositiveId(parts[1]);

            if (!projectId.has_value()) {
                return ResponseFactory::error(
                    StatusCode::BAD_REQUEST,
                    "INVALID_IDENTIFIER",
                    "The project identifier is invalid."
                );
            }

            if (request.method == HttpMethod::GET) {
                return api.listProjectTasks(*projectId);
            }

            if (request.method == HttpMethod::POST) {
                return api.createProjectTask(
                    *projectId,
                    request
                );
            }

            return ResponseFactory::error(
                StatusCode::METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "Unsupported task collection operation."
            );
        }

        if (
            parts.size() == 2 &&
            parts[0] == "tasks"
        ) {
            const auto taskId =
                parsePositiveId(parts[1]);

            if (!taskId.has_value()) {
                return ResponseFactory::error(
                    StatusCode::BAD_REQUEST,
                    "INVALID_IDENTIFIER",
                    "The task identifier is invalid."
                );
            }

            if (request.method == HttpMethod::PATCH) {
                return api.patchTask(
                    *taskId,
                    request
                );
            }

            if (request.method == HttpMethod::DELETE_) {
                return api.deleteTask(*taskId);
            }

            return ResponseFactory::error(
                StatusCode::METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "Unsupported task item operation."
            );
        }

        return unknownRoute();
    }
};


// -----------------------------------------------------------------------------
// Output helpers
// -----------------------------------------------------------------------------

void printResponse(
    const string& description,
    const HttpRequest& request,
    const HttpResponse& response
) {
    cout << "\n[" << description << "]\n";
    cout << methodToString(request.method)
         << " "
         << request.path
         << " -> "
         << statusNumber(response.status)
         << " "
         << statusText(response.status)
         << "\n";

    for (const auto& [name, value] : response.headers) {
        cout << name << ": " << value << "\n";
    }

    if (!response.body.empty()) {
        cout << response.body << "\n";
    }
}


// -----------------------------------------------------------------------------
// Design analysis
// -----------------------------------------------------------------------------

void printDesignAnalysis() {
    cout << "\nREST design analysis\n";
    cout << "===================\n";

    cout << R"(
Resource modeling:
  /users identifies a user collection.
  /users/{id} identifies one user.
  /users/{id}/projects identifies projects in the context of one user.
  /projects/{id} identifies a project independently of its parent.
  /projects/{id}/tasks identifies tasks belonging to a project.
  /tasks/{id} identifies a task independently once its identifier is known.

HTTP semantics:
  GET retrieves representations.
  POST creates subordinate resources.
  PUT is appropriate when the client sends a complete replacement.
  PATCH expresses partial modification.
  DELETE removes the addressed resource.

The URI is not an instruction such as /getProject or /deleteTask.
The resource path and HTTP method together express the operation.

Status-code separation:
  404 represents an absent addressed resource.
  405 represents an unsupported method for a known route.
  409 represents a state conflict, such as deleting a project that
      still owns tasks.
  422 represents a syntactically usable request whose supplied values
      fail domain validation.
  401 represents missing authentication.
  403 represents an authenticated principal that lacks permission.

Response design:
  Successful representations are returned beneath "data".
  Errors expose a machine-readable code and a human-readable message.
  Creation responses include Location so a client can address the
  newly created resource directly.
  204 deliberately has no representation body.

Nesting trade-off:
  Nested resources are useful when the relationship is meaningful to the
  operation. Excessive nesting increases URI complexity and forces clients
  to carry unnecessary ancestry information. The case study therefore
  supports both contextual nested collection paths and direct resource
  paths for independently addressable items.
)";
}


// -----------------------------------------------------------------------------
// Main case study
// -----------------------------------------------------------------------------

int main() {
    cout << "REST API Design Case Study\n";
    cout << "=========================\n";

    Repository repository;
    ProjectApi api(repository);
    ApiRouter router(repository, api);

    User* atul = repository.findUser(1);
    User* priya = repository.findUser(2);

    // Collection retrieval.
    HttpRequest listUsers{
        HttpMethod::GET,
        "/users",
        ""
    };

    printResponse(
        "Retrieve collection",
        listUsers,
        router.dispatch(listUsers)
    );

    // Item retrieval.
    HttpRequest getUser{
        HttpMethod::GET,
        "/users/1",
        ""
    };

    printResponse(
        "Retrieve item",
        getUser,
        router.dispatch(getUser)
    );

    // Creation demonstrates 201 and Location.
    HttpRequest createUser{
        HttpMethod::POST,
        "/users",
        R"({"name":"Meera Singh","email":"meera@example.com"})"
    };

    printResponse(
        "Create resource",
        createUser,
        router.dispatch(createUser)
    );

    // Nested resource creation demonstrates relationship validation.
    HttpRequest createProject{
        HttpMethod::POST,
        "/users/1/projects",
        R"({
            "name":"Security Gateway",
            "description":"API policy service"
        })"
    };

    printResponse(
        "Create nested resource",
        createProject,
        router.dispatch(createProject)
    );

    // Retrieve the nested collection after creation.
    HttpRequest listProjects{
        HttpMethod::GET,
        "/users/1/projects",
        ""
    };

    printResponse(
        "Retrieve nested collection",
        listProjects,
        router.dispatch(listProjects)
    );

    // Create a task under a project.
    HttpRequest createTask{
        HttpMethod::POST,
        "/projects/101/tasks",
        R"({
            "title":"Implement pagination",
            "status":"open"
        })"
    };

    printResponse(
        "Create task",
        createTask,
        router.dispatch(createTask)
    );

    // PATCH changes only supplied task fields.
    HttpRequest patchTask{
        HttpMethod::PATCH,
        "/tasks/1001",
        R"({"status":"in_progress"})"
    };

    printResponse(
        "Partial task modification",
        patchTask,
        router.dispatch(patchTask)
    );

    // Invalid status demonstrates semantic validation.
    HttpRequest invalidPatch{
        HttpMethod::PATCH,
        "/tasks/1001",
        R"({"status":"paused"})"
    };

    printResponse(
        "Invalid partial modification",
        invalidPatch,
        router.dispatch(invalidPatch)
    );

    // Deleting a project with dependent tasks demonstrates a state conflict.
    HttpRequest deleteProject{
        HttpMethod::DELETE_,
        "/projects/101",
        ""
    };

    printResponse(
        "Delete with dependency conflict",
        deleteProject,
        router.dispatch(deleteProject, atul)
    );

    // Authenticated but unauthorized deletion demonstrates 403.
    HttpRequest deleteReportingProject{
        HttpMethod::DELETE_,
        "/projects/102",
        ""
    };

    printResponse(
        "Authenticated user without permission",
        deleteReportingProject,
        router.dispatch(deleteReportingProject, priya)
    );

    // Missing authentication is different from authorization failure.
    printResponse(
        "Unauthenticated deletion",
        deleteReportingProject,
        router.dispatch(deleteReportingProject, nullptr)
    );

    // Unknown route.
    HttpRequest unknownRoute{
        HttpMethod::GET,
        "/customers/1",
        ""
    };

    printResponse(
        "Unknown resource route",
        unknownRoute,
        router.dispatch(unknownRoute)
    );

    // Known resource path with an unsupported method.
    HttpRequest unsupportedMethod{
        HttpMethod::PUT,
        "/users/1",
        R"({"name":"Replacement","email":"replacement@example.com"})"
    };

    printResponse(
        "Unsupported method",
        unsupportedMethod,
        router.dispatch(unsupportedMethod)
    );

    // Invalid identifier is a request-format problem rather than a
    // missing-resource result.
    HttpRequest invalidIdentifier{
        HttpMethod::GET,
        "/users/not-a-number",
        ""
    };

    printResponse(
        "Invalid identifier",
        invalidIdentifier,
        router.dispatch(invalidIdentifier)
    );

    // Wrong media type is handled before resource mutation.
    HttpRequest wrongMediaType{
        HttpMethod::POST,
        "/users",
        R"({"name":"Someone","email":"someone@example.com"})",
        "text/plain"
    };

    printResponse(
        "Unsupported request representation",
        wrongMediaType,
        router.dispatch(wrongMediaType)
    );

    printDesignAnalysis();

    cout << "\nC++ implementation characteristics\n";
    cout << "===================================\n";
    cout << "The repository uses unordered_map for average constant-time item lookup.\n";
    cout << "Collection responses are copied into vectors and sorted where stable\n";
    cout << "identifier ordering is useful for deterministic output.\n";
    cout << "The router parses URI structure before selecting a resource operation.\n";
    cout << "Authorization is kept separate from resource serialization and routing.\n";
    cout << "The example JSON parser is intentionally restricted; production systems\n";
    cout << "should use a standards-compliant parser and enforce request-size limits.\n";
    cout << "A real HTTP server would place transport concerns such as TLS, socket\n";
    cout << "handling, compression, authentication middleware, rate limiting, and\n";
    cout << "connection management outside these resource controllers.\n";

    return 0;
}
