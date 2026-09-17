/*
 * WSGI and ASGI architectural case study in C++17.
 *
 * WSGI and ASGI are Python application-server interfaces, so this program
 * does not implement those Python protocols. Instead, it models the same
 * server architecture in a strongly typed, systems-oriented environment.
 *
 * Case study:
 *     A production-style gateway serving an application with:
 *     - HTTP request parsing
 *     - routing
 *     - validation
 *     - middleware
 *     - worker threads
 *     - bounded concurrency
 *     - asynchronous task simulation
 *     - connection/request limits
 *     - metrics
 *     - graceful shutdown
 *     - CPU-bound work
 *     - security-aware proxy handling
 *
 * Compile:
 *     g++ -std=c++17 -O2 -pthread main.cpp -o server_case_study
 */

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdlib>
#include <functional>
#include <future>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;

// ============================================================
// 1. REQUEST AND RESPONSE MODELS
// ============================================================

struct HttpRequest {
    std::string method;
    std::string path;
    std::string query;
    std::unordered_map<std::string, std::string> headers;
    std::string body;
};

struct HttpResponse {
    int status = 200;
    std::unordered_map<std::string, std::string> headers;
    std::string body;
};

struct User {
    std::string name;
    int age = 0;
};

// ============================================================
// 2. METRICS
// ============================================================

class Metrics {
private:
    mutable std::mutex mutex_;
    std::size_t requests_ = 0;
    std::size_t errors_ = 0;
    std::vector<double> latenciesMs_;

public:
    void record(double latencyMs, bool failed) {
        std::lock_guard<std::mutex> lock(mutex_);

        ++requests_;
        if (failed) {
            ++errors_;
        }

        latenciesMs_.push_back(latencyMs);
    }

    void print() const {
        std::lock_guard<std::mutex> lock(mutex_);

        if (latenciesMs_.empty()) {
            std::cout << "No metrics recorded.\n";
            return;
        }

        std::vector<double> values = latenciesMs_;
        std::sort(values.begin(), values.end());

        const auto percentile = [&](double p) {
            const std::size_t index = static_cast<std::size_t>(
                p * static_cast<double>(values.size() - 1)
            );

            return values[index];
        };

        double total = 0.0;

        for (double value : values) {
            total += value;
        }

        std::cout << "Requests: " << requests_ << "\n";
        std::cout << "Errors: " << errors_ << "\n";
        std::cout << "Mean latency: "
                  << total / static_cast<double>(values.size())
                  << " ms\n";
        std::cout << "P50 latency: "
                  << percentile(0.50)
                  << " ms\n";
        std::cout << "P95 latency: "
                  << percentile(0.95)
                  << " ms\n";
        std::cout << "P99 latency: "
                  << percentile(0.99)
                  << " ms\n";
    }
};

// ============================================================
// 3. INPUT VALIDATION
// ============================================================

std::optional<User> validateUser(const HttpRequest& request,
                                 std::string& error) {
    auto nameIterator = request.headers.find("x-user-name");
    auto ageIterator = request.headers.find("x-user-age");

    if (nameIterator == request.headers.end() ||
        ageIterator == request.headers.end()) {
        error = "x-user-name and x-user-age are required";
        return std::nullopt;
    }

    const std::string& name = nameIterator->second;
    const std::string& ageText = ageIterator->second;

    if (name.empty() || name.size() > 100) {
        error = "invalid user name";
        return std::nullopt;
    }

    int age = 0;

    try {
        std::size_t consumed = 0;
        age = std::stoi(ageText, &consumed);

        if (consumed != ageText.size()) {
            error = "age must be an integer";
            return std::nullopt;
        }
    } catch (const std::exception&) {
        error = "age must be an integer";
        return std::nullopt;
    }

    if (age < 0 || age > 150) {
        error = "age must be between 0 and 150";
        return std::nullopt;
    }

    return User{name, age};
}

// ============================================================
// 4. QUERY PARSING
// ============================================================

std::unordered_map<std::string, std::string>
parseQuery(const std::string& query) {
    std::unordered_map<std::string, std::string> result;

    std::stringstream stream(query);
    std::string pair;

    while (std::getline(stream, pair, '&')) {
        const std::size_t equals = pair.find('=');

        if (equals == std::string::npos) {
            result[pair] = "";
            continue;
        }

        result[pair.substr(0, equals)] =
            pair.substr(equals + 1);
    }

    return result;
}

// ============================================================
// 5. ROUTER
// ============================================================

using Handler = std::function<HttpResponse(const HttpRequest&)>;

class Router {
private:
    std::map<std::pair<std::string, std::string>, Handler> routes_;

public:
    void addRoute(
        const std::string& method,
        const std::string& path,
        Handler handler
    ) {
        routes_[{method, path}] = std::move(handler);
    }

    HttpResponse dispatch(const HttpRequest& request) const {
        auto iterator = routes_.find(
            {request.method, request.path}
        );

        if (iterator == routes_.end()) {
            return HttpResponse{
                404,
                {{"Content-Type", "text/plain"}},
                "Not Found"
            };
        }

        return iterator->second(request);
    }
};

// ============================================================
// 6. MIDDLEWARE MODEL
// ============================================================

using Middleware = std::function<HttpResponse(
    const HttpRequest&,
    const std::function<HttpResponse(const HttpRequest&)>&
)>;

class MiddlewareStack {
private:
    std::vector<Middleware> middleware_;
    Handler finalHandler_;

public:
    explicit MiddlewareStack(Handler finalHandler)
        : finalHandler_(std::move(finalHandler)) {}

    void add(Middleware middleware) {
        middleware_.push_back(std::move(middleware));
    }

    HttpResponse execute(const HttpRequest& request) const {
        std::function<HttpResponse(std::size_t)> dispatch;

        dispatch = [&](std::size_t index) -> HttpResponse {
            if (index == middleware_.size()) {
                return finalHandler_(request);
            }

            return middleware_[index](
                request,
                [&](const HttpRequest&) {
                    return dispatch(index + 1);
                }
            );
        };

        return dispatch(0);
    }
};

// ============================================================
// 7. BOUNDED THREAD POOL
// ============================================================

class ThreadPool {
private:
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;

    mutable std::mutex mutex_;
    std::condition_variable condition_;

    bool stopping_ = false;

public:
    explicit ThreadPool(std::size_t workerCount) {
        if (workerCount == 0) {
            throw std::invalid_argument(
                "worker count must be greater than zero"
            );
        }

        for (std::size_t i = 0; i < workerCount; ++i) {
            workers_.emplace_back([this] {
                while (true) {
                    std::function<void()> task;

                    {
                        std::unique_lock<std::mutex> lock(mutex_);

                        condition_.wait(
                            lock,
                            [this] {
                                return stopping_ || !tasks_.empty();
                            }
                        );

                        if (stopping_ && tasks_.empty()) {
                            return;
                        }

                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }

                    try {
                        task();
                    } catch (const std::exception& exception) {
                        std::cerr
                            << "Worker task error: "
                            << exception.what()
                            << "\n";
                    }
                }
            });
        }
    }

    ~ThreadPool() {
        shutdown();
    }

    void submit(std::function<void()> task) {
        {
            std::lock_guard<std::mutex> lock(mutex_);

            if (stopping_) {
                throw std::runtime_error(
                    "cannot submit after shutdown"
                );
            }

            tasks_.push(std::move(task));
        }

        condition_.notify_one();
    }

    void shutdown() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            stopping_ = true;
        }

        condition_.notify_all();

        for (auto& worker : workers_) {
            if (worker.joinable()) {
                worker.join();
            }
        }

        workers_.clear();
    }
};

// ============================================================
// 8. CONNECTION LIMITER
// ============================================================

class ConnectionLimiter {
private:
    std::size_t maximum_;
    std::size_t active_ = 0;

    std::mutex mutex_;
    std::condition_variable condition_;

public:
    explicit ConnectionLimiter(std::size_t maximum)
        : maximum_(maximum) {
        if (maximum == 0) {
            throw std::invalid_argument(
                "maximum connection count must be positive"
            );
        }
    }

    void acquire() {
        std::unique_lock<std::mutex> lock(mutex_);

        condition_.wait(
            lock,
            [this] {
                return active_ < maximum_;
            }
        );

        ++active_;
    }

    void release() {
        {
            std::lock_guard<std::mutex> lock(mutex_);

            if (active_ == 0) {
                throw std::logic_error(
                    "connection release without acquisition"
                );
            }

            --active_;
        }

        condition_.notify_one();
    }
};

// ============================================================
// 9. RAII CONNECTION GUARD
// ============================================================

class ConnectionGuard {
private:
    ConnectionLimiter& limiter_;

public:
    explicit ConnectionGuard(ConnectionLimiter& limiter)
        : limiter_(limiter) {
        limiter_.acquire();
    }

    ~ConnectionGuard() {
        limiter_.release();
    }

    ConnectionGuard(const ConnectionGuard&) = delete;
    ConnectionGuard& operator=(const ConnectionGuard&) = delete;
};

// ============================================================
// 10. APPLICATION SERVICE
// ============================================================

class UserService {
private:
    std::mutex mutex_;
    std::unordered_map<int, User> users_;

public:
    UserService() {
        users_.emplace(1, User{"Atul", 30});
        users_.emplace(2, User{"Priya", 28});
        users_.emplace(3, User{"Rahul", 35});
    }

    std::optional<User> findUser(int id) const {
        std::lock_guard<std::mutex> lock(mutex_);

        auto iterator = users_.find(id);

        if (iterator == users_.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    void addUser(int id, User user) {
        std::lock_guard<std::mutex> lock(mutex_);

        if (users_.find(id) != users_.end()) {
            throw std::invalid_argument(
                "user ID already exists"
            );
        }

        users_.emplace(id, std::move(user));
    }
};

// ============================================================
// 11. APPLICATION CONTROLLER
// ============================================================

class Application {
private:
    Router router_;
    MiddlewareStack middleware_;
    UserService userService_;
    Metrics metrics_;
    ConnectionLimiter connectionLimiter_;

public:
    Application()
        : middleware_(
              [this](const HttpRequest& request) {
                  return router_.dispatch(request);
              }
          ),
          connectionLimiter_(4) {
        configureRoutes();
        configureMiddleware();
    }

    void configureRoutes() {
        router_.addRoute(
            "GET",
            "/health",
            [](const HttpRequest&) {
                return HttpResponse{
                    200,
                    {{"Content-Type", "application/json"}},
                    R"({"status":"ok"})"
                };
            }
        );

        router_.addRoute(
            "GET",
            "/users",
            [this](const HttpRequest& request) {
                return handleUsers(request);
            }
        );

        router_.addRoute(
            "POST",
            "/users",
            [this](const HttpRequest& request) {
                return handleCreateUser(request);
            }
        );
    }

    void configureMiddleware() {
        middleware_.add(
            [](const HttpRequest& request,
               const std::function<HttpResponse(
                   const HttpRequest&)>& next) {
                /*
                 * Middleware can inspect requests before delegating.
                 */
                if (request.body.size() > 1024 * 1024) {
                    return HttpResponse{
                        413,
                        {{"Content-Type", "text/plain"}},
                        "Request body too large"
                    };
                }

                return next(request);
            }
        );

        middleware_.add(
            [](const HttpRequest& request,
               const std::function<HttpResponse(
                   const HttpRequest&)>& next) {
                /*
                 * Security policy should be adapted to the real deployment.
                 */
                HttpResponse response = next(request);

                response.headers[
                    "X-Content-Type-Options"
                ] = "nosniff";

                return response;
            }
        );
    }

    HttpResponse handleUsers(const HttpRequest& request) {
        const auto query = parseQuery(request.query);

        auto iterator = query.find("id");

        if (iterator == query.end()) {
            return HttpResponse{
                400,
                {{"Content-Type", "text/plain"}},
                "id is required"
            };
        }

        int id = 0;

        try {
            std::size_t consumed = 0;
            id = std::stoi(iterator->second, &consumed);

            if (consumed != iterator->second.size()) {
                throw std::invalid_argument("invalid integer");
            }
        } catch (const std::exception&) {
            return HttpResponse{
                400,
                {{"Content-Type", "text/plain"}},
                "id must be an integer"
            };
        }

        auto user = userService_.findUser(id);

        if (!user) {
            return HttpResponse{
                404,
                {{"Content-Type", "text/plain"}},
                "User not found"
            };
        }

        std::ostringstream body;

        body << "{"
             << R"("id":)"
             << id
             << R"(,"name":")"
             << user->name
             << R"(","age":)"
             << user->age
             << "}";

        return HttpResponse{
            200,
            {{"Content-Type", "application/json"}},
            body.str()
        };
    }

    HttpResponse handleCreateUser(
        const HttpRequest& request
    ) {
        std::string error;

        auto user = validateUser(request, error);

        if (!user) {
            return HttpResponse{
                400,
                {{"Content-Type", "text/plain"}},
                error
            };
        }

        /*
         * This example uses a deterministic demonstration ID.
         * Production applications would use an appropriate database-generated
         * identifier or another collision-resistant strategy.
         */
        try {
            userService_.addUser(100, *user);
        } catch (const std::exception& exception) {
            return HttpResponse{
                409,
                {{"Content-Type", "text/plain"}},
                exception.what()
            };
        }

        return HttpResponse{
            201,
            {{"Content-Type", "application/json"}},
            R"({"created":true})"
        };
    }

    HttpResponse handle(
        const HttpRequest& request
    ) {
        ConnectionGuard connection(connectionLimiter_);

        const auto started = Clock::now();

        bool failed = false;

        try {
            HttpResponse response =
                middleware_.execute(request);

            failed = response.status >= 500;

            const auto finished = Clock::now();

            const double elapsed =
                std::chrono::duration<double, std::milli>(
                    finished - started
                ).count();

            metrics_.record(elapsed, failed);

            return response;
        } catch (...) {
            failed = true;

            const auto finished = Clock::now();

            const double elapsed =
                std::chrono::duration<double, std::milli>(
                    finished - started
                ).count();

            metrics_.record(elapsed, true);

            throw;
        }
    }

    void printMetrics() const {
        metrics_.print();
    }
};

// ============================================================
// 12. CPU-BOUND WORK
// ============================================================

std::uint64_t cpuBoundCalculation(std::uint64_t number) {
    std::uint64_t result = 0;

    for (std::uint64_t value = 0; value < number; ++value) {
        result += value * value;
    }

    return result;
}

// ============================================================
// 13. PROXY SECURITY
// ============================================================

class ProxyTrustPolicy {
private:
    std::vector<std::string> trustedProxies_;

public:
    explicit ProxyTrustPolicy(
        std::vector<std::string> trustedProxies
    )
        : trustedProxies_(std::move(trustedProxies)) {}

    bool isTrusted(const std::string& address) const {
        return std::find(
            trustedProxies_.begin(),
            trustedProxies_.end(),
            address
        ) != trustedProxies_.end();
    }
};

// ============================================================
// 14. REQUEST PROCESSING CASE STUDY
// ============================================================

void runRequestCaseStudy(Application& application) {
    std::cout << "\n=== REQUEST CASE STUDY ===\n";

    std::vector<HttpRequest> requests = {
        {
            "GET",
            "/health",
            "",
            {},
            ""
        },
        {
            "GET",
            "/users",
            "id=1",
            {},
            ""
        },
        {
            "GET",
            "/users",
            "id=999",
            {},
            ""
        },
        {
            "GET",
            "/users",
            "id=not-number",
            {},
            ""
        },
        {
            "POST",
            "/users",
            "",
            {
                {"x-user-name", "Neha"},
                {"x-user-age", "31"}
            },
            ""
        }
    };

    for (const auto& request : requests) {
        HttpResponse response = application.handle(request);

        std::cout
            << request.method
            << " "
            << request.path
            << " -> "
            << response.status
            << " | "
            << response.body
            << "\n";
    }
}

// ============================================================
// 15. CONCURRENT REQUEST CASE STUDY
// ============================================================

void runConcurrentRequests(
    Application& application
) {
    std::cout << "\n=== CONCURRENT REQUEST CASE STUDY ===\n";

    ThreadPool pool(4);

    std::atomic<int> completed{0};

    for (int i = 0; i < 20; ++i) {
        pool.submit(
            [&application, &completed, i] {
                HttpRequest request{
                    "GET",
                    "/users",
                    "id=" + std::to_string((i % 3) + 1),
                    {},
                    ""
                };

                HttpResponse response =
                    application.handle(request);

                if (response.status == 200) {
                    ++completed;
                }
            }
        );
    }

    /*
     * The pool destructor waits for all queued tasks to complete.
     * This is a simple educational synchronization strategy.
     */
    pool.shutdown();

    std::cout
        << "Successful concurrent requests: "
        << completed.load()
        << "\n";
}

// ============================================================
// 16. WORKER MODEL EXPLANATION
// ============================================================

void explainWorkerArchitecture() {
    std::cout << R"(
=== WORKER ARCHITECTURE ===

Python WSGI:

    reverse proxy
          |
      WSGI server
      /    |    \
 process process process
      \    |    /
       WSGI app

Python ASGI:

    reverse proxy
          |
      ASGI server
      /    |    \
 process process process
      |      |      |
   event  event   event
   loop   loop    loop
      \      |      /
        ASGI app

A deployment using Gunicorn can manage multiple worker processes.
An ASGI deployment can use an appropriate Uvicorn worker implementation under
Gunicorn, depending on the installed versions and supported integration.

This C++ case study models worker concurrency with threads. Threads share the
process address space, while separate processes provide stronger memory
isolation and can independently use CPU cores.
)";
}

// ============================================================
// 17. SYNCHRONOUS VS ASYNCHRONOUS TRADE-OFFS
// ============================================================

void explainExecutionModels() {
    std::cout << R"(
=== EXECUTION MODELS ===

Synchronous:
    request A -> wait -> response A -> request B

Threaded:
    worker 1 -> request A
    worker 2 -> request B
    worker 3 -> request C

Event-driven:
    event loop -> task A waits for I/O
               -> task B progresses
               -> task C progresses
               -> task A resumes

Process-based:
    process 1 -> application instance
    process 2 -> application instance
    process 3 -> application instance

Important distinction:

Concurrency is not identical to parallelism.

An event loop can handle many concurrent I/O operations without executing all
CPU instructions simultaneously.

Multiple processes or suitable CPU execution resources can provide actual
parallel CPU execution.
)";
}

// ============================================================
// 18. ASGI-LIKE EVENT MODEL
// ============================================================

enum class EventType {
    HttpRequest,
    HttpResponseStart,
    HttpResponseBody,
    WebSocketConnect,
    WebSocketReceive,
    WebSocketSend,
    WebSocketClose
};

struct Event {
    EventType type;
    std::string data;
};

class EventApplication {
public:
    std::vector<Event> handle(
        const std::vector<Event>& incoming
    ) {
        std::vector<Event> outgoing;

        for (const Event& event : incoming) {
            if (event.type == EventType::HttpRequest) {
                outgoing.push_back(
                    {
                        EventType::HttpResponseStart,
                        "200 OK"
                    }
                );

                outgoing.push_back(
                    {
                        EventType::HttpResponseBody,
                        "Hello from event-driven application"
                    }
                );
            }

            if (event.type == EventType::WebSocketConnect) {
                outgoing.push_back(
                    {
                        EventType::WebSocketSend,
                        "accepted"
                    }
                );
            }

            if (event.type == EventType::WebSocketReceive) {
                outgoing.push_back(
                    {
                        EventType::WebSocketSend,
                        "echo: " + event.data
                    }
                );
            }
        }

        return outgoing;
    }
};

void demonstrateEventModel() {
    std::cout << "\n=== EVENT MODEL ===\n";

    EventApplication application;

    std::vector<Event> events = {
        {EventType::HttpRequest, "GET /"},
        {EventType::WebSocketConnect, ""},
        {EventType::WebSocketReceive, "hello"}
    };

    for (const auto& event : application.handle(events)) {
        std::cout << event.data << "\n";
    }
}

// ============================================================
// 19. EDGE CASES
// ============================================================

void demonstrateEdgeCases(Application& application) {
    std::cout << "\n=== EDGE CASES ===\n";

    std::vector<HttpRequest> cases = {
        {"GET", "/missing", "", {}, ""},
        {"GET", "/users", "id=", {}, ""},
        {"GET", "/users", "id=-1", {}, ""},
        {"POST", "/users", "", {}, ""},
        {
            "POST",
            "/users",
            "",
            {
                {"x-user-name", ""},
                {"x-user-age", "30"}
            },
            ""
        },
        {
            "POST",
            "/users",
            "",
            {
                {"x-user-name", "Valid"},
                {"x-user-age", "151"}
            },
            ""
        }
    };

    for (const auto& request : cases) {
        HttpResponse response = application.handle(request);

        std::cout
            << request.method
            << " "
            << request.path
            << " -> "
            << response.status
            << " | "
            << response.body
            << "\n";
    }
}

// ============================================================
// 20. PERFORMANCE COMPLEXITY
// ============================================================

void explainComplexity() {
    std::cout << R"(
=== COMPLEXITY ===

Route lookup:
    std::map is approximately O(log R), where R is the number of routes.

Hash-based user lookup:
    std::unordered_map is average O(1), with worst-case O(N).

Thread-pool task submission:
    The queue insertion is O(1) under normal queue semantics.

Sorting latency measurements:
    O(N log N).

CPU example:
    cpuBoundCalculation(N) is O(N).

Theoretical complexity does not capture network latency, cache behavior,
lock contention, context switching, memory allocation, kernel scheduling,
serialization, or external service latency.
)";
}

// ============================================================
// 21. GRACEFUL SHUTDOWN
// ============================================================

class Lifecycle {
private:
    std::atomic<bool> accepting_{false};

public:
    void startup() {
        accepting_.store(true);
        std::cout << "Application startup complete.\n";
    }

    void beginShutdown() {
        accepting_.store(false);
        std::cout
            << "Application stopped accepting new requests.\n";
    }

    bool acceptingRequests() const {
        return accepting_.load();
    }
};

void demonstrateGracefulShutdown() {
    std::cout << "\n=== GRACEFUL SHUTDOWN ===\n";

    Lifecycle lifecycle;

    lifecycle.startup();

    std::cout
        << "Accepting: "
        << std::boolalpha
        << lifecycle.acceptingRequests()
        << "\n";

    lifecycle.beginShutdown();

    std::cout
        << "Accepting: "
        << lifecycle.acceptingRequests()
        << "\n";
}

// ============================================================
// 22. PRODUCTION CONFIGURATION
// ============================================================

struct ServerConfiguration {
    std::size_t workers = 4;
    std::size_t maximumConnections = 1000;
    std::size_t maximumRequestBytes = 1024 * 1024;
    int requestTimeoutSeconds = 30;
};

void validateConfiguration(
    const ServerConfiguration& configuration
) {
    if (configuration.workers == 0) {
        throw std::invalid_argument(
            "worker count must be positive"
        );
    }

    if (configuration.maximumConnections == 0) {
        throw std::invalid_argument(
            "connection limit must be positive"
        );
    }

    if (configuration.maximumRequestBytes == 0) {
        throw std::invalid_argument(
            "request size limit must be positive"
        );
    }

    if (configuration.requestTimeoutSeconds <= 0) {
        throw std::invalid_argument(
            "request timeout must be positive"
        );
    }
}

void demonstrateConfiguration() {
    std::cout << "\n=== SERVER CONFIGURATION ===\n";

    ServerConfiguration configuration;

    validateConfiguration(configuration);

    std::cout
        << "Workers: "
        << configuration.workers
        << "\n";

    std::cout
        << "Maximum connections: "
        << configuration.maximumConnections
        << "\n";

    std::cout
        << "Maximum request bytes: "
        << configuration.maximumRequestBytes
        << "\n";

    std::cout
        << "Request timeout: "
        << configuration.requestTimeoutSeconds
        << " seconds\n";
}

// ============================================================
// 23. MAIN
// ============================================================

int main() {
    try {
        std::cout
            << "============================================================\n"
            << "WSGI AND ASGI: C++ ARCHITECTURAL CASE STUDY\n"
            << "============================================================\n";

        explainWorkerArchitecture();
        explainExecutionModels();

        demonstrateConfiguration();

        Application application;

        runRequestCaseStudy(application);
        runConcurrentRequests(application);

        demonstrateEventModel();

        demonstrateEdgeCases(application);

        std::cout << "\n=== CPU-BOUND CASE ===\n";

        const auto started = Clock::now();

        const std::uint64_t result =
            cpuBoundCalculation(100000);

        const auto finished = Clock::now();

        const double elapsed =
            std::chrono::duration<double, std::milli>(
                finished - started
            ).count();

        std::cout
            << "CPU result: "
            << result
            << "\n";

        std::cout
            << "CPU elapsed: "
            << std::fixed
            << std::setprecision(3)
            << elapsed
            << " ms\n";

        ProxyTrustPolicy proxyPolicy(
            {"127.0.0.1", "::1"}
        );

        std::cout
            << "\nTrusted proxy 127.0.0.1: "
            << proxyPolicy.isTrusted("127.0.0.1")
            << "\n";

        std::cout
            << "Untrusted proxy 10.0.0.5: "
            << proxyPolicy.isTrusted("10.0.0.5")
            << "\n";

        demonstrateGracefulShutdown();

        std::cout << "\n=== APPLICATION METRICS ===\n";
        application.printMetrics();

        explainComplexity();

        std::cout << R"(
=== PRODUCTION DESIGN PRINCIPLES ===

1. Select WSGI for conventional synchronous Python applications where its
   model matches the workload.

2. Select ASGI when asynchronous I/O, long-lived connections, WebSockets,
   or other event-driven protocol behavior is important.

3. Uvicorn is an ASGI server runtime.

4. Gunicorn is commonly used as a process manager and worker manager. It can
   be combined with an appropriate Uvicorn ASGI worker implementation.

5. Worker count should be selected using CPU, memory, I/O, database capacity,
   latency, and load-test evidence.

6. Blocking operations should not monopolize an asynchronous event loop.

7. Resource limits, timeouts, graceful shutdown, and observability are
   fundamental production controls.

8. Security is an application and infrastructure concern in addition to the
   server interface itself.
)";

        return EXIT_SUCCESS;
    } catch (const std::exception& exception) {
        std::cerr
            << "Fatal error: "
            << exception.what()
            << "\n";

        return EXIT_FAILURE;
    }
}
