#include <algorithm>
#include <cctype>
#include <exception>
#include <functional>
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
    FastAPI Introduction: C++ Technical Case Study
    =================================================

    This program models a realistic API gateway for a small product service.

    It focuses on the same architectural concepts used by FastAPI:

        application instance
        route registration
        HTTP methods
        path operations
        path parameters
        query parameters
        validation
        status codes
        error handling
        separation of routing and business logic
        dependency-like request context
        route specificity
        performance considerations

    The program does not depend on an external HTTP framework. It simulates
    request dispatch so the architecture can be studied with standard C++17.

    Compile:

        g++ -std=c++17 -O2 fastapi_introduction.cpp -o fastapi_introduction

    Run:

        ./fastapi_introduction
*/


// ============================================================================
// 1. HTTP PRIMITIVES
// ============================================================================

enum class HttpMethod {
    GET,
    POST,
    PUT,
    PATCH,
    DELETE_METHOD
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
        case HttpMethod::DELETE_METHOD:
            return "DELETE";
    }

    return "UNKNOWN";
}


std::optional<HttpMethod> parseMethod(const std::string& value) {
    if (value == "GET") {
        return HttpMethod::GET;
    }

    if (value == "POST") {
        return HttpMethod::POST;
    }

    if (value == "PUT") {
        return HttpMethod::PUT;
    }

    if (value == "PATCH") {
        return HttpMethod::PATCH;
    }

    if (value == "DELETE") {
        return HttpMethod::DELETE_METHOD;
    }

    return std::nullopt;
}


// ============================================================================
// 2. REQUEST AND RESPONSE MODELS
// ============================================================================

struct HttpRequest {
    HttpMethod method;
    std::string path;
    std::map<std::string, std::string> query;
    std::map<std::string, std::string> headers;
    std::string body;
};


struct HttpResponse {
    int statusCode = 200;
    std::string contentType = "application/json";
    std::string body;
};


class HttpException : public std::runtime_error {
public:
    HttpException(int statusCode, const std::string& message)
        : std::runtime_error(message),
          statusCode_(statusCode) {}

    int statusCode() const noexcept {
        return statusCode_;
    }

private:
    int statusCode_;
};


// ============================================================================
// 3. PRODUCT DOMAIN MODEL
// ============================================================================

struct Product {
    int id;
    std::string name;
    double price;
    bool inStock;
};


std::string productToJson(const Product& product) {
    std::ostringstream output;

    output << std::fixed << std::setprecision(2);
    output << "{";
    output << "\"id\":" << product.id << ",";
    output << "\"name\":\"" << product.name << "\",";
    output << "\"price\":" << product.price << ",";
    output << "\"in_stock\":" << (product.inStock ? "true" : "false");
    output << "}";

    return output.str();
}


// ============================================================================
// 4. INPUT VALIDATION
// ============================================================================

int parsePositiveInteger(
    const std::string& rawValue,
    const std::string& fieldName
) {
    if (rawValue.empty()) {
        throw HttpException(
            400,
            fieldName + " cannot be empty"
        );
    }

    std::size_t position = 0;

    try {
        int value = std::stoi(
            rawValue,
            &position
        );

        if (position != rawValue.size()) {
            throw HttpException(
                422,
                fieldName + " must contain only digits"
            );
        }

        if (value <= 0) {
            throw HttpException(
                422,
                fieldName + " must be greater than zero"
            );
        }

        return value;
    } catch (const std::invalid_argument&) {
        throw HttpException(
            422,
            fieldName + " is not a valid integer"
        );
    } catch (const std::out_of_range&) {
        throw HttpException(
            422,
            fieldName + " is outside the supported integer range"
        );
    }
}


double parsePositivePrice(
    const std::string& rawValue
) {
    try {
        std::size_t position = 0;

        double value = std::stod(
            rawValue,
            &position
        );

        if (position != rawValue.size()) {
            throw HttpException(
                422,
                "price must be numeric"
            );
        }

        if (!std::isfinite(value) || value <= 0.0) {
            throw HttpException(
                422,
                "price must be a finite positive number"
            );
        }

        return value;
    } catch (const std::invalid_argument&) {
        throw HttpException(
            422,
            "price must be numeric"
        );
    } catch (const std::out_of_range&) {
        throw HttpException(
            422,
            "price is outside the supported range"
        );
    }
}


// ============================================================================
// 5. SIMPLE JSON FIELD EXTRACTION
// ============================================================================

std::optional<std::string> extractJsonString(
    const std::string& body,
    const std::string& field
) {
    const std::string pattern =
        "\"" + field + "\"\\s*:\\s*\"([^\"]*)\"";

    std::regex expression(pattern);
    std::smatch match;

    if (std::regex_search(body, match, expression)) {
        return match[1].str();
    }

    return std::nullopt;
}


std::optional<std::string> extractJsonNumber(
    const std::string& body,
    const std::string& field
) {
    const std::string pattern =
        "\"" + field + "\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)";

    std::regex expression(pattern);
    std::smatch match;

    if (std::regex_search(body, match, expression)) {
        return match[1].str();
    }

    return std::nullopt;
}


/*
    This is deliberately not a complete JSON parser. It is sufficient for this
    educational case study. Production systems should use a standards-compliant
    JSON library rather than regular expressions for arbitrary JSON documents.
*/


// ============================================================================
// 6. PRODUCT REQUEST VALIDATION
// ============================================================================

Product parseProductRequest(
    const std::string& body,
    int id
) {
    const auto name =
        extractJsonString(body, "name");

    const auto price =
        extractJsonNumber(body, "price");

    if (!name.has_value()) {
        throw HttpException(
            422,
            "name is required"
        );
    }

    if (name->empty()) {
        throw HttpException(
            422,
            "name cannot be empty"
        );
    }

    if (!price.has_value()) {
        throw HttpException(
            422,
            "price is required"
        );
    }

    const double parsedPrice =
        parsePositivePrice(*price);

    return Product{
        id,
        *name,
        parsedPrice,
        true
    };
}


// ============================================================================
// 7. REPOSITORY LAYER
// ============================================================================

class ProductRepository {
public:
    std::optional<Product> findById(int id) const {
        const auto iterator =
            products_.find(id);

        if (iterator == products_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    Product save(const Product& product) {
        products_[product.id] = product;
        return product;
    }

    bool erase(int id) {
        return products_.erase(id) > 0;
    }

    int nextId() const {
        int highest = 0;

        for (const auto& [id, product] : products_) {
            highest = std::max(
                highest,
                id
            );
        }

        return highest + 1;
    }

    std::vector<Product> all() const {
        std::vector<Product> result;

        for (const auto& [id, product] : products_) {
            result.push_back(product);
        }

        return result;
    }

private:
    std::map<int, Product> products_;
};


// ============================================================================
// 8. SERVICE LAYER
// ============================================================================

class ProductService {
public:
    explicit ProductService(ProductRepository& repository)
        : repository_(repository) {}

    Product getProduct(int id) const {
        const auto product =
            repository_.findById(id);

        if (!product.has_value()) {
            throw HttpException(
                404,
                "Product not found"
            );
        }

        return *product;
    }

    Product createProduct(
        const std::string& body
    ) {
        const int id =
            repository_.nextId();

        Product product =
            parseProductRequest(
                body,
                id
            );

        return repository_.save(product);
    }

    Product replaceProduct(
        int id,
        const std::string& body
    ) {
        // A PUT operation requires the target resource to exist in this
        // case study. The exact semantics should be defined by the API.
        getProduct(id);

        Product product =
            parseProductRequest(
                body,
                id
            );

        return repository_.save(product);
    }

    void deleteProduct(int id) {
        getProduct(id);

        if (!repository_.erase(id)) {
            throw HttpException(
                500,
                "Failed to delete product"
            );
        }
    }

private:
    ProductRepository& repository_;
};


// ============================================================================
// 9. PATH MATCHING
// ============================================================================

struct PathMatch {
    bool matched = false;
    std::map<std::string, std::string> parameters;
};


std::vector<std::string> splitPath(
    const std::string& path
) {
    std::vector<std::string> segments;
    std::stringstream stream(path);
    std::string segment;

    while (std::getline(stream, segment, '/')) {
        if (!segment.empty()) {
            segments.push_back(segment);
        }
    }

    return segments;
}


PathMatch matchPath(
    const std::string& templatePath,
    const std::string& actualPath
) {
    const auto templateSegments =
        splitPath(templatePath);

    const auto actualSegments =
        splitPath(actualPath);

    if (templateSegments.size() != actualSegments.size()) {
        return {};
    }

    PathMatch result;
    result.matched = true;

    for (std::size_t index = 0;
         index < templateSegments.size();
         ++index) {

        const std::string& expected =
            templateSegments[index];

        const std::string& actual =
            actualSegments[index];

        if (
            expected.size() >= 2 &&
            expected.front() == '{' &&
            expected.back() == '}'
        ) {
            const std::string parameterName =
                expected.substr(
                    1,
                    expected.size() - 2
                );

            result.parameters[
                parameterName
            ] = actual;

            continue;
        }

        if (expected != actual) {
            return {};
        }
    }

    return result;
}


// ============================================================================
// 10. ROUTE DEFINITION
// ============================================================================

using Endpoint =
    std::function<HttpResponse(
        const HttpRequest&,
        const std::map<std::string, std::string>&
    )>;


struct Route {
    HttpMethod method;
    std::string path;
    Endpoint endpoint;
    std::string name;
};


// ============================================================================
// 11. APPLICATION INSTANCE
// ============================================================================

class Application {
public:
    Application(
        std::string name,
        std::string version
    )
        : name_(std::move(name)),
          version_(std::move(version)) {}

    void addRoute(
        HttpMethod method,
        const std::string& path,
        const std::string& name,
        Endpoint endpoint
    ) {
        routes_.push_back(
            Route{
                method,
                path,
                std::move(endpoint),
                name
            }
        );
    }

    const std::vector<Route>& routes() const {
        return routes_;
    }

    HttpResponse dispatch(
        const HttpRequest& request
    ) const {
        for (const Route& route : routes_) {
            if (route.method != request.method) {
                continue;
            }

            const PathMatch match =
                matchPath(
                    route.path,
                    request.path
                );

            if (!match.matched) {
                continue;
            }

            return route.endpoint(
                request,
                match.parameters
            );
        }

        throw HttpException(
            404,
            "Route not found"
        );
    }

    const std::string& name() const {
        return name_;
    }

    const std::string& version() const {
        return version_;
    }

private:
    std::string name_;
    std::string version_;
    std::vector<Route> routes_;
};


// ============================================================================
// 12. RESPONSE HELPERS
// ============================================================================

HttpResponse jsonResponse(
    int statusCode,
    const std::string& body
) {
    return HttpResponse{
        statusCode,
        "application/json",
        body
    };
}


HttpResponse errorResponse(
    int statusCode,
    const std::string& message
) {
    return jsonResponse(
        statusCode,
        "{\"detail\":\"" + message + "\"}"
    );
}


// ============================================================================
// 13. DEPENDENCY-LIKE REQUEST CONTEXT
// ============================================================================

struct RequestContext {
    std::string requestId;
    std::string authenticatedUser;
    bool authenticated = false;
};


RequestContext buildRequestContext(
    const HttpRequest& request
) {
    RequestContext context;

    auto requestId =
        request.headers.find("X-Request-ID");

    if (requestId != request.headers.end()) {
        context.requestId = requestId->second;
    } else {
        context.requestId = "generated-request-id";
    }

    auto authorization =
        request.headers.find("Authorization");

    if (
        authorization != request.headers.end() &&
        authorization->second == "Bearer demo-token"
    ) {
        context.authenticated = true;
        context.authenticatedUser = "demo-user";
    }

    return context;
}


// ============================================================================
// 14. AUTHORIZATION CHECK
// ============================================================================

void requireAuthentication(
    const RequestContext& context
) {
    if (!context.authenticated) {
        throw HttpException(
            401,
            "Authentication required"
        );
    }
}


// ============================================================================
// 15. APPLICATION CONSTRUCTION
// ============================================================================

Application buildApplication(
    ProductService& productService
) {
    Application app(
        "Product Management API",
        "1.0.0"
    );

    // ------------------------------------------------------------------------
    // GET /
    // ------------------------------------------------------------------------

    app.addRoute(
        HttpMethod::GET,
        "/",
        "root",
        [](const HttpRequest&, const auto&) {
            return jsonResponse(
                200,
                "{\"message\":\"Product API is running\"}"
            );
        }
    );

    // ------------------------------------------------------------------------
    // GET /health
    // ------------------------------------------------------------------------

    app.addRoute(
        HttpMethod::GET,
        "/health",
        "health_check",
        [](const HttpRequest&, const auto&) {
            return jsonResponse(
                200,
                "{\"status\":\"ok\"}"
            );
        }
    );

    // ------------------------------------------------------------------------
    // GET /products/{product_id}
    // ------------------------------------------------------------------------

    app.addRoute(
        HttpMethod::GET,
        "/products/{product_id}",
        "get_product",
        [&productService](
            const HttpRequest&,
            const auto& parameters
        ) {
            const int productId =
                parsePositiveInteger(
                    parameters.at("product_id"),
                    "product_id"
                );

            const Product product =
                productService.getProduct(
                    productId
                );

            return jsonResponse(
                200,
                productToJson(product)
            );
        }
    );

    // ------------------------------------------------------------------------
    // POST /products
    // ------------------------------------------------------------------------

    app.addRoute(
        HttpMethod::POST,
        "/products",
        "create_product",
        [&productService](
            const HttpRequest& request,
            const auto&
        ) {
            const Product product =
                productService.createProduct(
                    request.body
                );

            return jsonResponse(
                201,
                productToJson(product)
            );
        }
    );

    // ------------------------------------------------------------------------
    // PUT /products/{product_id}
    // ------------------------------------------------------------------------

    app.addRoute(
        HttpMethod::PUT,
        "/products/{product_id}",
        "replace_product",
        [&productService](
            const HttpRequest& request,
            const auto& parameters
        ) {
            const int productId =
                parsePositiveInteger(
                    parameters.at("product_id"),
                    "product_id"
                );

            const Product product =
                productService.replaceProduct(
                    productId,
                    request.body
                );

            return jsonResponse(
                200,
                productToJson(product)
            );
        }
    );

    // ------------------------------------------------------------------------
    // DELETE /products/{product_id}
    // ------------------------------------------------------------------------

    app.addRoute(
        HttpMethod::DELETE_METHOD,
        "/products/{product_id}",
        "delete_product",
        [&productService](
            const HttpRequest&,
            const auto& parameters
        ) {
            const int productId =
                parsePositiveInteger(
                    parameters.at("product_id"),
                    "product_id"
                );

            productService.deleteProduct(
                productId
            );

            return jsonResponse(
                200,
                "{\"message\":\"Product deleted\"}"
            );
        }
    );

    return app;
}


// ============================================================================
// 16. REQUEST DISPATCH WRAPPER
// ============================================================================

HttpResponse handleRequest(
    const Application& app,
    const HttpRequest& request
) {
    try {
        const RequestContext context =
            buildRequestContext(request);

        /*
            In a production system, authorization requirements would be
            attached to selected routes or routers rather than globally.
            This example only demonstrates how reusable request context can
            participate in request processing.
        */

        if (
            request.path == "/admin/products" &&
            !context.authenticated
        ) {
            requireAuthentication(context);
        }

        return app.dispatch(request);
    } catch (const HttpException& error) {
        return errorResponse(
            error.statusCode(),
            error.what()
        );
    } catch (const std::exception& error) {
        // Do not expose internal implementation details in a real production
        // response. Log the exception internally and return a generic message.
        return errorResponse(
            500,
            "Internal server error"
        );
    }
}


// ============================================================================
// 17. RESPONSE DISPLAY
// ============================================================================

void printResponse(
    const HttpRequest& request,
    const HttpResponse& response
) {
    std::cout
        << methodToString(request.method)
        << " "
        << request.path
        << " -> "
        << response.statusCode
        << " "
        << response.body
        << "\n";
}


// ============================================================================
// 18. ROUTE TABLE
// ============================================================================

void printRoutes(
    const Application& app
) {
    std::cout
        << "\nRegistered routes for "
        << app.name()
        << " "
        << app.version()
        << ":\n";

    for (const Route& route : app.routes()) {
        std::cout
            << "  "
            << methodToString(route.method)
            << " "
            << std::left
            << std::setw(32)
            << route.path
            << " "
            << route.name
            << "\n";
    }
}


// ============================================================================
// 19. QUERY PARAMETER DEMONSTRATION
// ============================================================================

std::string getQueryParameter(
    const HttpRequest& request,
    const std::string& key,
    const std::string& defaultValue = ""
) {
    const auto iterator =
        request.query.find(key);

    if (iterator == request.query.end()) {
        return defaultValue;
    }

    return iterator->second;
}


HttpResponse searchProducts(
    const HttpRequest& request
) {
    const std::string query =
        getQueryParameter(
            request,
            "q",
            ""
        );

    const std::string limit =
        getQueryParameter(
            request,
            "limit",
            "10"
        );

    const int parsedLimit =
        parsePositiveInteger(
            limit,
            "limit"
        );

    if (parsedLimit > 100) {
        throw HttpException(
            422,
            "limit cannot exceed 100"
        );
    }

    std::ostringstream output;

    output
        << "{"
        << "\"query\":\""
        << query
        << "\","
        << "\"limit\":"
        << parsedLimit
        << "}";

    return jsonResponse(
        200,
        output.str()
    );
}


// ============================================================================
// 20. SEARCH ROUTE
// ============================================================================

Application addSearchRoute(
    Application app
) {
    app.addRoute(
        HttpMethod::GET,
        "/search",
        "search_products",
        [](const HttpRequest& request, const auto&) {
            return searchProducts(request);
        }
    );

    return app;
}


// ============================================================================
// 21. ROUTE ORDERING CASE
// ============================================================================

void demonstrateRouteOrdering() {
    Application app(
        "Ordering Demo",
        "1.0.0"
    );

    app.addRoute(
        HttpMethod::GET,
        "/users/{user_id}",
        "dynamic_user",
        [](const HttpRequest&, const auto& parameters) {
            return jsonResponse(
                200,
                "{\"matched\":\"dynamic\",\"value\":\"" +
                    parameters.at("user_id") +
                    "\"}"
            );
        }
    );

    app.addRoute(
        HttpMethod::GET,
        "/users/me",
        "current_user",
        [](const HttpRequest&, const auto&) {
            return jsonResponse(
                200,
                "{\"matched\":\"static\"}"
            );
        }
    );

    const HttpRequest request{
        HttpMethod::GET,
        "/users/me",
        {},
        {},
        ""
    };

    std::cout
        << "\nRoute ordering demonstration:\n";

    printResponse(
        request,
        handleRequest(
            app,
            request
        )
    );

    /*
        Because this educational router checks routes in registration order,
        /users/{user_id} captures "me".

        A production routing system can implement explicit specificity rules,
        but developers should still avoid ambiguous path designs.
    */
}


// ============================================================================
// 22. API TEST CASES
// ============================================================================

void runCaseStudyTests(
    const Application& app
) {
    std::cout
        << "\nCase study tests:\n";

    const std::vector<HttpRequest> requests{
        {
            HttpMethod::GET,
            "/",
            {},
            {},
            ""
        },
        {
            HttpMethod::GET,
            "/health",
            {},
            {},
            ""
        },
        {
            HttpMethod::GET,
            "/products/1",
            {},
            {},
            ""
        },
        {
            HttpMethod::GET,
            "/products/999",
            {},
            {},
            ""
        },
        {
            HttpMethod::GET,
            "/products/abc",
            {},
            {},
            ""
        },
        {
            HttpMethod::POST,
            "/products",
            {},
            {},
            "{\"name\":\"Webcam\",\"price\":79.99}"
        },
        {
            HttpMethod::POST,
            "/products",
            {},
            {},
            "{\"name\":\"\",\"price\":-5}"
        },
        {
            HttpMethod::PUT,
            "/products/1",
            {},
            {},
            "{\"name\":\"Mechanical Keyboard\",\"price\":89.99}"
        },
        {
            HttpMethod::DELETE_METHOD,
            "/products/2",
            {},
            {},
            ""
        },
        {
            HttpMethod::GET,
            "/missing",
            {},
            {},
            ""
        }
    };

    for (const auto& request : requests) {
        const HttpResponse response =
            handleRequest(
                app,
                request
            );

        printResponse(
            request,
            response
        );
    }
}


// ============================================================================
// 23. QUERY PARAMETER TEST
// ============================================================================

void runQueryTest() {
    Application app(
        "Query Demo",
        "1.0.0"
    );

    app.addRoute(
        HttpMethod::GET,
        "/search",
        "search",
        [](const HttpRequest& request, const auto&) {
            return searchProducts(request);
        }
    );

    const HttpRequest request{
        HttpMethod::GET,
        "/search",
        {
            {"q", "keyboard"},
            {"limit", "5"}
        },
        {},
        ""
    };

    std::cout
        << "\nQuery parameter test:\n";

    printResponse(
        request,
        handleRequest(
            app,
            request
        )
    );
}


// ============================================================================
// 24. PERFORMANCE DISCUSSION
// ============================================================================

void explainPerformance() {
    std::cout
        << R"(
Performance considerations:

1. Route lookup
   A simple vector scan is approximately O(R) per request, where R is the
   number of registered routes.

2. Parameter parsing
   Conversion and validation add CPU work, but request latency is often
   dominated by network and external I/O in real services.

3. Repository lookup
   std::map provides O(log N) lookup. An unordered_map can provide expected
   O(1) lookup when ordering is not required.

4. JSON parsing
   The demonstration parser is intentionally simple. Production JSON parsing
   should use a dedicated parser.

5. Database access
   Database latency can dominate the request path. Connection pooling and
   efficient queries are usually more important than micro-optimizing endpoint
   functions.

6. Concurrency
   A production HTTP server needs a concurrency model capable of handling
   multiple requests safely.

FastAPI uses an ASGI architecture and can use asynchronous endpoints for
non-blocking I/O. The exact performance profile depends on the workload,
server configuration, application code, and external services.
)"
        << "\n";
}


// ============================================================================
// 25. SECURITY DISCUSSION
// ============================================================================

void explainSecurity() {
    std::cout
        << R"(
Security considerations:

- Treat every HTTP parameter as untrusted input.
- Validate path parameters and query parameters.
- Validate request bodies using explicit schemas.
- Authenticate users before protected operations.
- Authorize access to individual resources.
- Do not expose internal exceptions or stack traces.
- Use HTTPS in production.
- Protect credentials and tokens.
- Use parameterized database queries.
- Limit request body sizes where appropriate.
- Apply rate limiting to sensitive or expensive operations.
- Log security-relevant events without leaking secrets.

Authentication answers "Who are you?"
Authorization answers "Are you allowed to perform this operation?"

They should not be treated as the same control.
)"
        << "\n";
}


// ============================================================================
// 26. COMPLEXITY DEMONSTRATION
// ============================================================================

void demonstrateComplexity() {
    constexpr int routeCount = 1000;

    std::vector<Route> routes;

    routes.reserve(routeCount);

    for (int index = 0; index < routeCount; ++index) {
        routes.push_back(
            Route{
                HttpMethod::GET,
                "/generated/" + std::to_string(index),
                [](const HttpRequest&, const auto&) {
                    return jsonResponse(
                        200,
                        "{\"status\":\"matched\"}"
                    );
                },
                "generated_route"
            }
        );
    }

    HttpRequest target{
        HttpMethod::GET,
        "/generated/999",
        {},
        {},
        ""
    };

    std::size_t inspected = 0;

    for (const auto& route : routes) {
        ++inspected;

        if (
            route.method == target.method &&
            matchPath(
                route.path,
                target.path
            ).matched
        ) {
            break;
        }
    }

    std::cout
        << "\nComplexity demonstration:\n"
        << "Routes: "
        << routeCount
        << "\n"
        << "Routes inspected: "
        << inspected
        << "\n"
        << "Simple linear routing is O(R).\n";
}


// ============================================================================
// 27. ARCHITECTURAL EXPLANATION
// ============================================================================

void explainArchitecture() {
    std::cout
        << R"(
Architecture represented by this case study:

    Client
       |
       v
    HTTP server
       |
       v
    Application instance
       |
       v
    Router
       |
       v
    Path operation / endpoint
       |
       +--> request validation
       |
       +--> request context
       |
       +--> authentication
       |
       v
    Service layer
       |
       v
    Repository layer
       |
       v
    Data store

The FastAPI equivalent places the application instance at the center of the
ASGI application and uses decorators such as @app.get() and @app.post() to
register path operations.

The C++ implementation separates those ideas explicitly because C++ does not
provide the same Python decorator mechanism in this example.
)"
        << "\n";
}


// ============================================================================
// 28. MAIN PROGRAM
// ============================================================================

int main() {
    std::cout
        << "FastAPI concepts through a C++ API case study\n";

    ProductRepository repository;

    repository.save(
        Product{
            1,
            "Keyboard",
            49.99,
            true
        }
    );

    repository.save(
        Product{
            2,
            "Monitor",
            199.99,
            true
        }
    );

    ProductService service(
        repository
    );

    Application app =
        buildApplication(
            service
        );

    app = addSearchRoute(
        std::move(app)
    );

    printRoutes(app);

    runCaseStudyTests(app);

    runQueryTest();

    demonstrateRouteOrdering();

    explainArchitecture();

    explainPerformance();

    explainSecurity();

    demonstrateComplexity();

    std::cout
        << "\nCase study completed successfully.\n";

    return 0;
}
