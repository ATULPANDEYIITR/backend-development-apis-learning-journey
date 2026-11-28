#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <variant>
#include <vector>

using namespace std;

// ============================================================
// ADVANCED GRAPHQL EXECUTION AND GOVERNANCE ENGINE
// C++17
//
// Demonstrates:
// - Nested query execution
// - Variables and fragments
// - Field validation
// - Role-based authorization
// - N+1 query detection
// - Batched data loading
// - Query complexity limits
// - Execution errors
// ============================================================

enum class Role {
    ADMIN,
    EDITOR,
    USER,
    GUEST
};

enum class ErrorCode {
    VALIDATION,
    AUTHENTICATION,
    AUTHORIZATION,
    EXECUTION
};

class GraphQLException : public runtime_error {
public:
    ErrorCode code;

    GraphQLException(const string& message, ErrorCode errorCode)
        : runtime_error(message), code(errorCode) {}
};

struct User {
    int id;
    string name;
    string email;
    Role role;
    bool active;
};

struct Post {
    int id;
    string title;
    string body;
    int authorId;
    bool published;
};

struct Comment {
    int id;
    int postId;
    int authorId;
    string content;
};

struct Context {
    optional<User> user;
    string requestId;
};

struct Selection {
    string field;
    string alias;
    map<string, string> arguments;
    vector<Selection> children;
};

struct Fragment {
    string name;
    string typeCondition;
    vector<Selection> selections;
};

struct Operation {
    vector<Selection> selections;
    map<string, string> variables;
    map<string, Fragment> fragments;
};

// ============================================================
// REPOSITORY
// ============================================================

class Repository {
private:
    unordered_map<int, User> users;
    unordered_map<int, Post> posts;
    vector<Comment> comments;

    size_t queryCount = 0;

public:
    Repository() {
        users.emplace(1, User{
            1, "Atul", "atul@example.com", Role::ADMIN, true
        });

        users.emplace(2, User{
            2, "Rahul", "rahul@example.com", Role::EDITOR, true
        });

        users.emplace(3, User{
            3, "Priya", "priya@example.com", Role::USER, true
        });

        posts.emplace(101, Post{
            101, "GraphQL Advanced", "Nested execution.", 1, true
        });

        posts.emplace(102, Post{
            102, "DataLoader", "Batching database access.", 2, true
        });

        posts.emplace(103, Post{
            103, "Private Draft", "Internal notes.", 1, false
        });

        comments.push_back({
            1001, 101, 2, "Excellent."
        });

        comments.push_back({
            1002, 101, 3, "Very informative."
        });

        comments.push_back({
            1003, 102, 1, "Batching is important."
        });
    }

    vector<Post> getPosts(bool publishedOnly) {
        ++queryCount;

        vector<Post> result;

        for (const auto& [id, post] : posts) {
            if (!publishedOnly || post.published) {
                result.push_back(post);
            }
        }

        sort(result.begin(), result.end(),
             [](const Post& a, const Post& b) {
                 return a.id < b.id;
             });

        return result;
    }

    optional<User> getUser(int id) {
        ++queryCount;

        auto it = users.find(id);

        if (it == users.end()) {
            return nullopt;
        }

        return it->second;
    }

    map<int, vector<Comment>> getCommentsBatch(
        const vector<int>& postIds
    ) {
        ++queryCount;

        unordered_set<int> requested(
            postIds.begin(), postIds.end()
        );

        map<int, vector<Comment>> result;

        for (int id : postIds) {
            result[id] = {};
        }

        for (const auto& comment : comments) {
            if (requested.count(comment.postId)) {
                result[comment.postId].push_back(comment);
            }
        }

        return result;
    }

    size_t getQueryCount() const {
        return queryCount;
    }
};

// ============================================================
// AUTHORIZATION
// ============================================================

class AuthorizationService {
public:
    static const User& requireAuthenticated(const Context& context) {
        if (!context.user.has_value() || !context.user->active) {
            throw GraphQLException(
                "Authentication required.",
                ErrorCode::AUTHENTICATION
            );
        }

        return context.user.value();
    }

    static void requireRole(
        const Context& context,
        const set<Role>& allowed
    ) {
        const User& user = requireAuthenticated(context);

        if (!allowed.count(user.role)) {
            throw GraphQLException(
                "Insufficient permissions.",
                ErrorCode::AUTHORIZATION
            );
        }
    }

    static bool canReadPost(
        const Context& context,
        const Post& post
    ) {
        if (post.published) {
            return true;
        }

        if (!context.user.has_value()) {
            return false;
        }

        const User& user = context.user.value();

        return user.active &&
            (user.role == Role::ADMIN ||
             user.id == post.authorId);
    }

    static bool canReadEmail(
        const Context& context,
        const User& target
    ) {
        if (!context.user.has_value()) {
            return false;
        }

        const User& current = context.user.value();

        return current.active &&
            (current.role == Role::ADMIN ||
             current.id == target.id);
    }
};

// ============================================================
// DATALOADER
// ============================================================

class CommentDataLoader {
private:
    Repository& repository;

    unordered_map<int, vector<Comment>> cache;

public:
    explicit CommentDataLoader(Repository& repo)
        : repository(repo) {}

    void loadBatch(const vector<int>& keys) {
        vector<int> missing;

        for (int key : keys) {
            if (!cache.count(key)) {
                missing.push_back(key);
            }
        }

        if (missing.empty()) {
            return;
        }

        sort(missing.begin(), missing.end());

        missing.erase(
            unique(missing.begin(), missing.end()),
            missing.end()
        );

        auto batch = repository.getCommentsBatch(missing);

        for (const auto& [id, comments] : batch) {
            cache[id] = comments;
        }
    }

    const vector<Comment>& get(int key) const {
        auto it = cache.find(key);

        if (it == cache.end()) {
            throw GraphQLException(
                "DataLoader key was not loaded.",
                ErrorCode::EXECUTION
            );
        }

        return it->second;
    }

    void clear() {
        cache.clear();
    }
};

// ============================================================
// QUERY COMPLEXITY
// ============================================================

class ComplexityAnalyzer {
private:
    size_t maximumCost;

    size_t calculateRecursive(
        const vector<Selection>& selections,
        const map<string, Fragment>& fragments,
        set<string>& visited
    ) const {
        size_t total = 0;

        for (const auto& selection : selections) {
            if (selection.field.rfind("...", 0) == 0) {
                string name = selection.field.substr(3);

                auto it = fragments.find(name);

                if (it == fragments.end()) {
                    throw GraphQLException(
                        "Unknown fragment: " + name,
                        ErrorCode::VALIDATION
                    );
                }

                if (visited.count(name)) {
                    throw GraphQLException(
                        "Circular fragment detected.",
                        ErrorCode::VALIDATION
                    );
                }

                visited.insert(name);

                total += calculateRecursive(
                    it->second.selections,
                    fragments,
                    visited
                );

                visited.erase(name);
                continue;
            }

            size_t multiplier =
                selection.field == "posts" ? 5 : 1;

            total += multiplier * (
                1 + calculateRecursive(
                    selection.children,
                    fragments,
                    visited
                )
            );
        }

        return total;
    }

public:
    explicit ComplexityAnalyzer(size_t maximum)
        : maximumCost(maximum) {}

    size_t validate(const Operation& operation) const {
        set<string> visited;

        size_t cost = calculateRecursive(
            operation.selections,
            operation.fragments,
            visited
        );

        if (cost > maximumCost) {
            throw GraphQLException(
                "Query complexity exceeds configured limit.",
                ErrorCode::VALIDATION
            );
        }

        return cost;
    }
};

// ============================================================
// EXECUTION ENGINE
// ============================================================

class GraphQLExecutor {
private:
    Repository& repository;
    CommentDataLoader commentLoader;
    ComplexityAnalyzer complexity;

    static const map<string, set<string>>& schema() {
        static const map<string, set<string>> definitions = {
            {"Query", {"posts", "me", "user"}},
            {"Post", {
                "id", "title", "body", "published",
                "author", "comments"
            }},
            {"User", {
                "id", "name", "email", "role", "posts"
            }},
            {"Comment", {
                "id", "content", "author"
            }}
        };

        return definitions;
    }

    static void validateField(
        const string& type,
        const string& field
    ) {
        auto typeIt = schema().find(type);

        if (typeIt == schema().end() ||
            !typeIt->second.count(field)) {
            throw GraphQLException(
                "Unknown field '" + field + "' on " + type,
                ErrorCode::VALIDATION
            );
        }
    }

    vector<Selection> expandFragments(
        const vector<Selection>& selections,
        const Operation& operation,
        const string& type,
        set<string>& visited
    ) const {
        vector<Selection> result;

        for (const auto& selection : selections) {
            if (selection.field.rfind("...", 0) == 0) {
                string name = selection.field.substr(3);

                auto it = operation.fragments.find(name);

                if (it == operation.fragments.end()) {
                    throw GraphQLException(
                        "Unknown fragment: " + name,
                        ErrorCode::VALIDATION
                    );
                }

                if (visited.count(name)) {
                    throw GraphQLException(
                        "Circular fragment detected.",
                        ErrorCode::VALIDATION
                    );
                }

                if (it->second.typeCondition != type) {
                    continue;
                }

                visited.insert(name);

                auto expanded = expandFragments(
                    it->second.selections,
                    operation,
                    type,
                    visited
                );

                result.insert(
                    result.end(),
                    expanded.begin(),
                    expanded.end()
                );

                visited.erase(name);
            } else {
                result.push_back(selection);
            }
        }

        return result;
    }

    string argument(
        const Selection& selection,
        const string& name,
        const Operation& operation
    ) const {
        auto it = selection.arguments.find(name);

        if (it == selection.arguments.end()) {
            throw GraphQLException(
                "Missing argument: " + name,
                ErrorCode::VALIDATION
            );
        }

        string value = it->second;

        if (!value.empty() && value[0] == '$') {
            string variableName = value.substr(1);

            auto variable = operation.variables.find(variableName);

            if (variable == operation.variables.end()) {
                throw GraphQLException(
                    "Missing variable: $" + variableName,
                    ErrorCode::VALIDATION
                );
            }

            return variable->second;
        }

        return value;
    }

    vector<Selection> getExpanded(
        const vector<Selection>& selections,
        const Operation& operation,
        const string& type
    ) const {
        set<string> visited;

        return expandFragments(
            selections, operation, type, visited
        );
    }

    vector<Post> resolvePosts(
        const Selection& selection,
        const Operation& operation,
        const Context& context
    ) {
        bool publishedOnly = true;

        auto it = selection.arguments.find("publishedOnly");

        if (it != selection.arguments.end()) {
            string value = argument(
                selection, "publishedOnly", operation
            );

            if (value == "false") {
                publishedOnly = false;
            } else if (value != "true") {
                throw GraphQLException(
                    "publishedOnly must be Boolean.",
                    ErrorCode::VALIDATION
                );
            }
        }

        if (!publishedOnly) {
            AuthorizationService::requireRole(
                context,
                {Role::ADMIN, Role::EDITOR}
            );
        }

        return repository.getPosts(publishedOnly);
    }

    string projectComment(
        const Comment& comment,
        const vector<Selection>& selections,
        const Operation& operation,
        const Context& context
    ) {
        auto expanded = getExpanded(
            selections, operation, "Comment"
        );

        vector<int> authorIds;

        for (const auto& selection : expanded) {
            validateField("Comment", selection.field);

            if (selection.field == "author") {
                authorIds.push_back(comment.authorId);
            }
        }

        // User records are available in the example repository.
        string output = "{";

        bool first = true;

        for (const auto& selection : expanded) {
            if (!first) output += ", ";
            first = false;

            string key = selection.alias.empty()
                ? selection.field : selection.alias;

            if (selection.field == "id") {
                output += "\"" + key + "\":" +
                    to_string(comment.id);
            } else if (selection.field == "content") {
                output += "\"" + key + "\":\"" +
                    comment.content + "\"";
            } else if (selection.field == "author") {
                if (!selection.children.empty()) {
                    output += "\"" + key + "\":{}";
                } else {
                    throw GraphQLException(
                        "author requires nested selections.",
                        ErrorCode::VALIDATION
                    );
                }
            }
        }

        output += "}";
        return output;
    }

    string projectPost(
        const Post& post,
        const vector<Selection>& selections,
        const Operation& operation,
        const Context& context
    ) {
        auto expanded = getExpanded(
            selections, operation, "Post"
        );

        string output = "{";
        bool first = true;

        for (const auto& selection : expanded) {
            validateField("Post", selection.field);

            if (!first) output += ", ";
            first = false;

            string key = selection.alias.empty()
                ? selection.field : selection.alias;

            if (selection.field == "id") {
                output += "\"" + key + "\":" +
                    to_string(post.id);
            } else if (selection.field == "title") {
                output += "\"" + key + "\":\"" +
                    post.title + "\"";
            } else if (selection.field == "published") {
                output += "\"" + key + "\":" +
                    string(post.published ? "true" : "false");
            } else if (selection.field == "body") {
                output += "\"" + key + "\":\"" +
                    post.body + "\"";
            } else if (selection.field == "comments") {
                if (selection.children.empty()) {
                    throw GraphQLException(
                        "comments requires nested selections.",
                        ErrorCode::VALIDATION
                    );
                }

                const auto& comments =
                    commentLoader.get(post.id);

                output += "\"" + key + "\":[";

                bool firstComment = true;

                for (const auto& comment : comments) {
                    if (!firstComment) output += ",";
                    firstComment = false;

                    output += projectComment(
                        comment,
                        selection.children,
                        operation,
                        context
                    );
                }

                output += "]";
            } else if (selection.field == "author") {
                if (selection.children.empty()) {
                    throw GraphQLException(
                        "author requires nested selections.",
                        ErrorCode::VALIDATION
                    );
                }

                output += "\"" + key + "\":{}";
            }
        }

        output += "}";
        return output;
    }

public:
    explicit GraphQLExecutor(Repository& repo)
        : repository(repo),
          commentLoader(repo),
          complexity(100) {}

    string execute(
        const Operation& operation,
        const Context& context
    ) {
        auto started = chrono::steady_clock::now();

        try {
            complexity.validate(operation);

            vector<Selection> root = getExpanded(
                operation.selections,
                operation,
                "Query"
            );

            // Collect post identifiers first. The batch loader
            // receives all parent keys before nested projection.
            vector<Post> posts;

            for (const auto& selection : root) {
                validateField("Query", selection.field);

                if (selection.field == "posts") {
                    posts = resolvePosts(
                        selection, operation, context
                    );
                }
            }

            vector<int> postIds;

            for (const auto& post : posts) {
                postIds.push_back(post.id);
            }

            commentLoader.loadBatch(postIds);

            string response = "{\"data\":{";
            bool first = true;

            for (const auto& selection : root) {
                if (!first) response += ",";
                first = false;

                string key = selection.alias.empty()
                    ? selection.field : selection.alias;

                if (selection.field == "posts") {
                    response += "\"" + key + "\":[";

                    bool firstPost = true;

                    for (const auto& post : posts) {
                        if (!AuthorizationService::canReadPost(
                            context, post
                        )) {
                            throw GraphQLException(
                                "Post access denied.",
                                ErrorCode::AUTHORIZATION
                            );
                        }

                        if (!firstPost) response += ",";
                        firstPost = false;

                        response += projectPost(
                            post,
                            selection.children,
                            operation,
                            context
                        );
                    }

                    response += "]";
                } else if (selection.field == "me") {
                    const User& user =
                        AuthorizationService::requireAuthenticated(
                            context
                        );

                    response += "\"" + key + "\":{\"id\":" +
                        to_string(user.id) +
                        ",\"name\":\"" + user.name + "\"}";
                } else if (selection.field == "user") {
                    AuthorizationService::requireRole(
                        context, {Role::ADMIN}
                    );

                    int id = stoi(argument(
                        selection, "id", operation
                    ));

                    auto user = repository.getUser(id);

                    if (!user.has_value()) {
                        response += "\"" + key + "\":null";
                    } else {
                        response += "\"" + key + "\":{\"id\":" +
                            to_string(user->id) +
                            ",\"name\":\"" + user->name + "\"}";
                    }
                }
            }

            response += "}}";

            commentLoader.clear();

            return response;

        } catch (const GraphQLException& error) {
            commentLoader.clear();

            return "{\"data\":null,\"errors\":[{\"message\":\"" +
                string(error.what()) + "\"}]}";
        } catch (const exception& error) {
            commentLoader.clear();

            return "{\"data\":null,\"errors\":[{\"message\":\"" +
                string(error.what()) + "\"}]}";
        }
    }
};

// ============================================================
// DEMONSTRATION
// ============================================================

int main() {
    try {
        Repository repository;
        GraphQLExecutor executor(repository);

        Context context{
            User{
                1,
                "Atul",
                "atul@example.com",
                Role::ADMIN,
                true
            },
            "request-cpp-001"
        };

        Fragment fragment{
            "PostDetails",
            "Post",
            {
                {"id", "", {}, {}},
                {"title", "", {}, {}},
                {"comments", "", {}, {
                    {"id", "", {}, {}},
                    {"content", "", {}, {}}
                }}
            }
        };

        Operation operation;

        operation.variables["published"] = "true";

        operation.fragments["PostDetails"] = fragment;

        Selection posts;
        posts.field = "posts";
        posts.arguments["publishedOnly"] = "$published";
        posts.children.push_back({
            "...PostDetails", "", {}, {}
        });

        Selection me;
        me.field = "me";
        me.children = {
            {"id", "", {}, {}},
            {"name", "", {}, {}}
        };

        operation.selections = {posts, me};

        cout << "GRAPHQL EXECUTION\n";
        cout << executor.execute(operation, context) << "\n";

        if (repository.getQueryCount() != 2) {
            throw runtime_error(
                "Expected one posts query and one comments batch query."
            );
        }

        cout << "\nDATALOADER TEST PASSED\n";
        cout << "Database queries: "
             << repository.getQueryCount() << "\n";

        // Unauthenticated access must fail.
        Context guest{
            nullopt,
            "request-cpp-002"
        };

        Operation unauthorized;
        unauthorized.selections = {me};

        string denied = executor.execute(
            unauthorized, guest
        );

        if (denied.find("\"errors\"") == string::npos) {
            throw runtime_error(
                "Authentication test failed."
            );
        }

        cout << "AUTHENTICATION TEST PASSED\n";

        // Invalid field must fail schema validation.
        Operation invalid;
        invalid.selections = {
            {"posts", "", {}, {
                {"invalidField", "", {}, {}}
            }}
        };

        string invalidResult = executor.execute(
            invalid, context
        );

        if (invalidResult.find("\"errors\"") == string::npos) {
            throw runtime_error(
                "Schema validation test failed."
            );
        }

        cout << "SCHEMA VALIDATION TEST PASSED\n";

        // Fragment recursion must be rejected.
        Operation circular;
        circular.fragments["A"] = {
            "A", "Post", {
                {"...A", "", {}, {}}
            }
        };

        circular.selections = {
            {"posts", "", {}, {
                {"...A", "", {}, {}}
            }}
        };

        string circularResult = executor.execute(
            circular, context
        );

        if (circularResult.find("\"errors\"") == string::npos) {
            throw runtime_error(
                "Circular fragment test failed."
            );
        }

        cout << "FRAGMENT VALIDATION TEST PASSED\n";

        cout << "\nALL TESTS COMPLETED\n";

    } catch (const exception& error) {
        cerr << "Execution failed: "
             << error.what() << "\n";

        return 1;
    }

    return 0;
}
