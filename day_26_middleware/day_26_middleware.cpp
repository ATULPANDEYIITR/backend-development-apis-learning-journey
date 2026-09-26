/*
 * Middleware Case Study
 *
 * Scenario:
 *   A production-style API gateway receives HTTP-like requests for an
 *   internal employee service. Before business logic executes, the request
 *   passes through a configurable middleware pipeline.
 *
 * Demonstrated concepts:
 *   - request lifecycle
 *   - middleware composition
 *   - request enrichment
 *   - authentication
 *   - authorization
 *   - validation
 *   - rate limiting
 *   - response interception
 *   - security headers
 *   - response envelopes
 *   - error handling
 *   - metrics
 *   - caching
 *   - short-circuiting
 *   - ordering
 *   - complexity and design trade-offs
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic middleware_case_study.cpp -o middleware_case_study
 *
 * Run:
 *   ./middleware_case_study
 */

#include <algorithm>
#include <chrono>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>


// ============================================================================
// 1. REQUEST
// ============================================================================

struct Request {
    std::string method;
    std::string path;

    // HTTP header names are technically case-insensitive. This small case
    // study normalizes the headers supplied by the caller.
    std::unordered_map<std::string, std::string> headers;

    std::unordered_map<std::string, std::string> query;

    // Middleware can attach internal metadata without changing the external
    // API contract.
    std::unordered_map<std::string, std::string> state;

    std::string body;

    std::string header(const std::string& name) const {
        auto it = headers.find(normalize(name));

        if (it == headers.end()) {
            return "";
        }

        return it->second;
    }

    static std::string normalize(std::string value) {
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
};


// ============================================================================
// 2. RESPONSE
// ============================================================================

struct Response {
    int statusCode = 200;

    std::unordered_map<std::string, std::string> headers;

    std::string body;
};


// ============================================================================
// 3. HANDLER AND MIDDLEWARE TYPES
// ============================================================================

using Handler = std::function<Response(Request&)>;

using Middleware = std::function<Response(Request&, const Handler&)>;


// ============================================================================
// 4. SIMPLE APPLICATION
// ============================================================================

Response employeeApplication(Request& request) {
    if (request.path == "/") {
        return {
            200,
            {{"Content-Type", "application/json"}},
            R"({"message":"Employee API"})"
        };
    }

    if (request.path == "/employees") {
        return {
            200,
            {{"Content-Type", "application/json"}},
            R"({"employees":[{"id":1,"name":"Asha"},{"id":2,"name":"Rahul"}]})"
        };
    }

    if (request.path == "/employees/1") {
        return {
            200,
            {{"Content-Type", "application/json"}},
            R"({"id":1,"name":"Asha","department":"Engineering"})"
        };
    }

    if (request.path == "/missing") {
        return {
            404,
            {{"Content-Type", "application/json"}},
            R"({"error":"Resource not found"})"
        };
    }

    if (request.path == "/error") {
        throw std::runtime_error("Simulated application failure");
    }

    return {
        404,
        {{"Content-Type", "application/json"}},
        R"({"error":"Unknown route"})"
    };
}


// ============================================================================
// 5. REQUEST ID MIDDLEWARE
// ============================================================================

class RequestIdMiddleware {
private:
    unsigned long long counter_ = 0;

public:
    Response operator()(Request& request, const Handler& next) {
        std::string supplied = request.header("X-Request-ID");

        if (supplied.empty()) {
            ++counter_;
            supplied = "request-" + std::to_string(counter_);
        }

        request.state["request_id"] = supplied;

        Response response = next(request);

        response.headers["X-Request-ID"] = supplied;

        return response;
    }
};


// ============================================================================
// 6. LOGGING MIDDLEWARE
// ============================================================================

class LoggingMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        std::cout
            << "[request] "
            << request.method
            << " "
            << request.path
            << "\n";

        Response response = next(request);

        std::cout
            << "[response] "
            << response.statusCode
            << "\n";

        return response;
    }
};


// ============================================================================
// 7. VALIDATION MIDDLEWARE
// ============================================================================

class ValidationMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        if (request.method.empty()) {
            return badRequest("HTTP method is required");
        }

        if (request.path.empty() || request.path.front() != '/') {
            return badRequest("Path must begin with /");
        }

        std::string contentLength = request.header("Content-Length");

        if (!contentLength.empty()) {
            try {
                long long length = std::stoll(contentLength);

                if (length < 0) {
                    return badRequest(
                        "Content-Length cannot be negative"
                    );
                }
            } catch (const std::exception&) {
                return badRequest("Invalid Content-Length");
            }
        }

        return next(request);
    }

private:
    static Response badRequest(const std::string& message) {
        return {
            400,
            {{"Content-Type", "application/json"}},
            "{\"error\":\"" + message + "\"}"
        };
    }
};


// ============================================================================
// 8. AUTHENTICATION
// ============================================================================

class AuthenticationMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        std::string token = request.header("Authorization");

        if (token == "Bearer demo-user-token") {
            request.state["user_id"] = "101";
            request.state["role"] = "user";
            request.state["authenticated"] = "true";
        } else if (token == "Bearer demo-admin-token") {
            request.state["user_id"] = "1";
            request.state["role"] = "admin";
            request.state["authenticated"] = "true";
        } else {
            request.state["authenticated"] = "false";
        }

        return next(request);
    }
};


// ============================================================================
// 9. AUTHORIZATION
// ============================================================================

class AdminAuthorizationMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        if (request.state["authenticated"] != "true") {
            return {
                401,
                {{"WWW-Authenticate", "Bearer"}},
                R"({"error":"Authentication required"})"
            };
        }

        if (request.state["role"] != "admin") {
            return {
                403,
                {},
                R"({"error":"Insufficient permissions"})"
            };
        }

        return next(request);
    }
};


// ============================================================================
// 10. RATE LIMITER
// ============================================================================

class RateLimitMiddleware {
private:
    std::size_t limit_;
    std::unordered_map<std::string, std::size_t> counts_;

public:
    explicit RateLimitMiddleware(std::size_t limit)
        : limit_(limit) {
        if (limit_ == 0) {
            throw std::invalid_argument(
                "Rate limit must be greater than zero"
            );
        }
    }

    Response operator()(Request& request, const Handler& next) {
        std::string client =
            request.header("X-Client-ID");

        if (client.empty()) {
            client = "anonymous";
        }

        std::size_t count = ++counts_[client];

        if (count > limit_) {
            return {
                429,
                {{"Retry-After", "60"}},
                R"({"error":"Rate limit exceeded"})"
            };
        }

        Response response = next(request);

        response.headers["X-RateLimit-Limit"] =
            std::to_string(limit_);

        response.headers["X-RateLimit-Remaining"] =
            std::to_string(limit_ - count);

        return response;
    }
};


// ============================================================================
// 11. SECURITY RESPONSE INTERCEPTION
// ============================================================================

class SecurityHeadersMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        Response response = next(request);

        // The response exists now, so middleware can modify it before the
        // server sends it to the client.
        response.headers["X-Content-Type-Options"] = "nosniff";
        response.headers["X-Frame-Options"] = "DENY";
        response.headers["Referrer-Policy"] =
            "strict-origin-when-cross-origin";

        return response;
    }
};


// ============================================================================
// 12. RESPONSE ENVELOPE
// ============================================================================

class ResponseEnvelopeMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        Response response = next(request);

        // This case study uses JSON strings rather than a JSON dependency.
        // The transformation therefore adds metadata around the original
        // payload in a deliberately simple representation.
        std::ostringstream envelope;

        envelope
            << "{"
            << "\"status\":\""
            << (response.statusCode < 400 ? "success" : "error")
            << "\","
            << "\"request_id\":\""
            << request.state["request_id"]
            << "\","
            << "\"payload\":"
            << response.body
            << "}";

        response.body = envelope.str();

        return response;
    }
};


// ============================================================================
// 13. TIMING MIDDLEWARE
// ============================================================================

class TimingMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        const auto start =
            std::chrono::steady_clock::now();

        Response response = next(request);

        const auto end =
            std::chrono::steady_clock::now();

        const auto elapsed =
            std::chrono::duration<double, std::milli>(
                end - start
            ).count();

        std::ostringstream value;
        value << std::fixed << std::setprecision(3)
              << elapsed;

        response.headers["X-Response-Time-Ms"] =
            value.str();

        return response;
    }
};


// ============================================================================
// 14. ERROR-HANDLING MIDDLEWARE
// ============================================================================

class ErrorHandlingMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        try {
            return next(request);
        } catch (const std::exception& exception) {
            // The detailed exception is logged server-side. It is not exposed
            // to the client because implementation details can reveal
            // sensitive information.
            std::cerr
                << "[internal error] "
                << exception.what()
                << "\n";

            return {
                500,
                {{"Content-Type", "application/json"}},
                R"({"error":"Internal server error"})"
            };
        }
    }
};


// ============================================================================
// 15. MAINTENANCE / SHORT-CIRCUIT MIDDLEWARE
// ============================================================================

class MaintenanceMiddleware {
public:
    Response operator()(Request& request, const Handler& next) {
        if (request.path == "/maintenance") {
            // next() is deliberately not called.
            return {
                503,
                {{"Retry-After", "60"}},
                R"({"error":"Service temporarily unavailable"})"
            };
        }

        return next(request);
    }
};


// ============================================================================
// 16. METRICS
// ============================================================================

class MetricsMiddleware {
private:
    std::size_t totalRequests_ = 0;
    std::map<int, std::size_t> statusCounts_;
    std::map<std::string, std::size_t> pathCounts_;

public:
    Response operator()(Request& request, const Handler& next) {
        ++totalRequests_;
        ++pathCounts_[request.path];

        Response response = next(request);

        ++statusCounts_[response.statusCode];

        return response;
    }

    void printReport() const {
        std::cout << "\nMETRICS\n";
        std::cout
            << "Total requests: "
            << totalRequests_
            << "\n";

        std::cout << "Status counts:\n";

        for (const auto& [status, count] : statusCounts_) {
            std::cout
                << "  "
                << status
                << ": "
                << count
                << "\n";
        }

        std::cout << "Path counts:\n";

        for (const auto& [path, count] : pathCounts_) {
            std::cout
                << "  "
                << path
                << ": "
                << count
                << "\n";
        }
    }
};


// ============================================================================
// 17. MIDDLEWARE COMPOSITION
// ============================================================================

Handler compose(
    const std::vector<Middleware>& middlewares,
    Handler finalHandler
) {
    Handler current = std::move(finalHandler);

    /*
     * If the vector contains A, B, C, the final handler becomes:
     *
     * A(B(C(application)))
     *
     * The reverse construction is what creates the desired nesting.
     */
    for (
        auto middleware = middlewares.rbegin();
        middleware != middlewares.rend();
        ++middleware
    ) {
        Handler downstream = current;

        current =
            [middleware, downstream](Request& request) -> Response {
                return (*middleware)(request, downstream);
            };
    }

    return current;
}


// ============================================================================
// 18. RESPONSE DISPLAY
// ============================================================================

void printResponse(const Response& response) {
    std::cout << "Status: "
              << response.statusCode
              << "\n";

    std::cout << "Headers:\n";

    for (const auto& [name, value] : response.headers) {
        std::cout
            << "  "
            << name
            << ": "
            << value
            << "\n";
    }

    std::cout
        << "Body: "
        << response.body
        << "\n";
}


// ============================================================================
// 19. COMPLETE EMPLOYEE API
// ============================================================================

void demonstrateCompleteSystem() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "COMPLETE EMPLOYEE API PIPELINE\n"
        << "============================================================\n";

    RequestIdMiddleware requestId;
    LoggingMiddleware logging;
    ValidationMiddleware validation;
    AuthenticationMiddleware authentication;
    SecurityHeadersMiddleware security;
    TimingMiddleware timing;
    ErrorHandlingMiddleware errors;
    MaintenanceMiddleware maintenance;
    RateLimitMiddleware limiter(5);
    MetricsMiddleware metrics;
    ResponseEnvelopeMiddleware envelope;

    /*
     * Ordering is intentional:
     *
     * error handling is outermost so it can catch failures below it.
     * request IDs are established early for tracing.
     * validation rejects malformed requests before business logic.
     * authentication establishes identity.
     * rate limiting protects downstream resources.
     * response middleware runs while the response unwinds.
     */
    std::vector<Middleware> middlewares = {
        [&errors](Request& r, const Handler& n) {
            return errors(r, n);
        },
        [&requestId](Request& r, const Handler& n) {
            return requestId(r, n);
        },
        [&logging](Request& r, const Handler& n) {
            return logging(r, n);
        },
        [&validation](Request& r, const Handler& n) {
            return validation(r, n);
        },
        [&authentication](Request& r, const Handler& n) {
            return authentication(r, n);
        },
        [&maintenance](Request& r, const Handler& n) {
            return maintenance(r, n);
        },
        [&limiter](Request& r, const Handler& n) {
            return limiter(r, n);
        },
        [&metrics](Request& r, const Handler& n) {
            return metrics(r, n);
        },
        [&timing](Request& r, const Handler& n) {
            return timing(r, n);
        },
        [&security](Request& r, const Handler& n) {
            return security(r, n);
        },
        [&envelope](Request& r, const Handler& n) {
            return envelope(r, n);
        }
    };

    Handler pipeline =
        compose(middlewares, employeeApplication);

    Request request{
        "GET",
        "/employees",
        {
            {"x-client-id", "client-1"},
            {"accept", "application/json"}
        },
        {},
        {},
        ""
    };

    Response response = pipeline(request);

    printResponse(response);

    metrics.printReport();
}


// ============================================================================
// 20. AUTHORIZATION CASE STUDY
// ============================================================================

void demonstrateAuthorization() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "AUTHENTICATION AND AUTHORIZATION\n"
        << "============================================================\n";

    AuthenticationMiddleware authentication;
    AdminAuthorizationMiddleware authorization;

    Handler pipeline = compose(
        {
            [&authentication](Request& r, const Handler& n) {
                return authentication(r, n);
            },
            [&authorization](Request& r, const Handler& n) {
                return authorization(r, n);
            }
        },
        employeeApplication
    );

    Request normalUser{
        "GET",
        "/employees",
        {
            {"authorization", "Bearer demo-user-token"}
        }
    };

    Response denied = pipeline(normalUser);

    std::cout
        << "Normal user -> "
        << denied.statusCode
        << "\n";

    Request adminUser{
        "GET",
        "/employees",
        {
            {"authorization", "Bearer demo-admin-token"}
        }
    };

    Response allowed = pipeline(adminUser);

    std::cout
        << "Admin user -> "
        << allowed.statusCode
        << "\n";
}


// ============================================================================
// 21. ERROR CASE
// ============================================================================

void demonstrateErrorHandling() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "ERROR HANDLING\n"
        << "============================================================\n";

    ErrorHandlingMiddleware errors;
    RequestIdMiddleware requestId;

    Handler pipeline = compose(
        {
            [&errors](Request& r, const Handler& n) {
                return errors(r, n);
            },
            [&requestId](Request& r, const Handler& n) {
                return requestId(r, n);
            }
        },
        employeeApplication
    );

    Request request{
        "GET",
        "/error"
    };

    Response response = pipeline(request);

    printResponse(response);
}


// ============================================================================
// 22. SHORT-CIRCUIT CASE
// ============================================================================

void demonstrateShortCircuiting() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "SHORT-CIRCUITING\n"
        << "============================================================\n";

    MaintenanceMiddleware maintenance;
    LoggingMiddleware logging;

    Handler pipeline = compose(
        {
            [&maintenance](Request& r, const Handler& n) {
                return maintenance(r, n);
            },
            [&logging](Request& r, const Handler& n) {
                return logging(r, n);
            }
        },
        employeeApplication
    );

    Request request{
        "GET",
        "/maintenance"
    };

    Response response = pipeline(request);

    /*
     * Logging does not execute because maintenance middleware returned
     * immediately. This illustrates how middleware can protect downstream
     * components from receiving a request.
     */
    printResponse(response);
}


// ============================================================================
// 23. ORDER CASE
// ============================================================================

void demonstrateOrder() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "ORDERING\n"
        << "============================================================\n";

    std::vector<std::string> events;

    Middleware a =
        [&events](Request& request, const Handler& next) {
            events.push_back("A before");
            Response response = next(request);
            events.push_back("A after");
            return response;
        };

    Middleware b =
        [&events](Request& request, const Handler& next) {
            events.push_back("B before");
            Response response = next(request);
            events.push_back("B after");
            return response;
        };

    Handler endpoint =
        [&events](Request&) {
            events.push_back("endpoint");

            return Response{
                200,
                {},
                R"({"ok":true})"
            };
        };

    Handler pipeline = compose(
        {a, b},
        endpoint
    );

    Request request{"GET", "/order"};

    pipeline(request);

    for (const auto& event : events) {
        std::cout << event << "\n";
    }
}


// ============================================================================
// 24. SIMPLE TESTS
// ============================================================================

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(
            "TEST FAILED: " + message
        );
    }
}

void runTests() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "SELF-TESTS\n"
        << "============================================================\n";

    {
        RequestIdMiddleware requestId;

        Handler pipeline = compose(
            {
                [&requestId](Request& r, const Handler& n) {
                    return requestId(r, n);
                }
            },
            employeeApplication
        );

        Request request{"GET", "/"};
        Response response = pipeline(request);

        require(
            request.state.contains("request_id"),
            "request ID should be created"
        );

        require(
            response.headers.contains("X-Request-ID"),
            "response should contain request ID"
        );

        std::cout << "PASS: request ID\n";
    }

    {
        MaintenanceMiddleware maintenance;

        Handler downstream =
            [](Request&) {
                throw std::runtime_error(
                    "downstream should not execute"
                );
            };

        Handler pipeline = compose(
            {
                [&maintenance](Request& r, const Handler& n) {
                    return maintenance(r, n);
                }
            },
            downstream
        );

        Request request{
            "GET",
            "/maintenance"
        };

        Response response = pipeline(request);

        require(
            response.statusCode == 503,
            "maintenance should return 503"
        );

        std::cout << "PASS: short-circuiting\n";
    }

    {
        RateLimitMiddleware limiter(2);

        Handler pipeline = compose(
            {
                [&limiter](Request& r, const Handler& n) {
                    return limiter(r, n);
                }
            },
            employeeApplication
        );

        Request first{
            "GET",
            "/",
            {{"x-client-id", "test-client"}}
        };

        Request second{
            "GET",
            "/",
            {{"x-client-id", "test-client"}}
        };

        Request third{
            "GET",
            "/",
            {{"x-client-id", "test-client"}}
        };

        require(
            pipeline(first).statusCode == 200,
            "first request should pass"
        );

        require(
            pipeline(second).statusCode == 200,
            "second request should pass"
        );

        require(
            pipeline(third).statusCode == 429,
            "third request should be rejected"
        );

        std::cout << "PASS: rate limiting\n";
    }

    {
        Response response =
            employeeApplication(
                *new Request{"GET", "/missing"}
            );

        require(
            response.statusCode == 404,
            "missing endpoint should return 404"
        );

        std::cout << "PASS: 404 handling\n";
    }
}


// ============================================================================
// 25. COMPLEXITY AND DESIGN NOTES
// ============================================================================

void printTechnicalNotes() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "TECHNICAL NOTES\n"
        << "============================================================\n";

    std::cout
        << "Pipeline composition: O(M) construction for M middleware components.\n"
        << "Pipeline execution: O(M + application work).\n"
        << "Hash-map request lookup: average O(1).\n"
        << "Rate-limit lookup: average O(1) per request.\n"
        << "Metrics map lookup: O(log N) because std::map is ordered.\n"
        << "Middleware overhead is normally proportional to the number of layers.\n"
        << "Process-local rate limiting does not coordinate multiple server instances.\n"
        << "Thread-safe shared middleware state requires synchronization or a\n"
        << "concurrency-safe data structure in a multithreaded server.\n"
        << "Response transformations must preserve required HTTP semantics.\n";
}


// ============================================================================
// 26. MAIN
// ============================================================================

int main() {
    try {
        demonstrateCompleteSystem();
        demonstrateAuthorization();
        demonstrateErrorHandling();
        demonstrateShortCircuiting();
        demonstrateOrder();
        runTests();
        printTechnicalNotes();

        std::cout
            << "\n"
            << "CASE STUDY COMPLETE\n";

        return 0;
    } catch (const std::exception& exception) {
        std::cerr
            << "Fatal error: "
            << exception.what()
            << "\n";

        return 1;
    }
}
