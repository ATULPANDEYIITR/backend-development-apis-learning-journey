/*
 * Web Servers: C++17 technical case study
 *
 * Case study:
 * A reverse-proxy gateway sits between Internet clients and a
 * cluster of application servers.
 *
 * The program models:
 * - HTTP request/response structures
 * - routing
 * - static-resource classification
 * - backend servers
 * - round-robin load balancing
 * - health checks
 * - request validation
 * - response caching
 * - security headers
 * - request logging
 * - failure handling
 * - complexity and operational statistics
 *
 * It uses only the C++17 standard library.
 */

#include <algorithm>
#include <chrono>
#include <cctype>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using Clock = std::chrono::steady_clock;


// ============================================================
// HTTP DATA MODEL
// ============================================================

struct HttpRequest {
    std::string method;
    std::string path;
    std::map<std::string, std::string> headers;
    std::string body;
};

struct HttpResponse {
    int statusCode = 500;
    std::map<std::string, std::string> headers;
    std::string body;
};


// ============================================================
// UTILITY FUNCTIONS
// ============================================================

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

std::string statusText(int statusCode) {
    switch (statusCode) {
        case 200: return "OK";
        case 400: return "Bad Request";
        case 403: return "Forbidden";
        case 404: return "Not Found";
        case 502: return "Bad Gateway";
        case 503: return "Service Unavailable";
        default: return "Internal Server Error";
    }
}

void addSecurityHeaders(HttpResponse& response) {
    response.headers["X-Content-Type-Options"] = "nosniff";
    response.headers["X-Frame-Options"] = "DENY";
    response.headers["Referrer-Policy"] =
        "strict-origin-when-cross-origin";
    response.headers["Content-Security-Policy"] =
        "default-src 'self'";
}


// ============================================================
// APPLICATION SERVER
// ============================================================

class ApplicationServer {
public:
    HttpResponse handle(const HttpRequest& request) {
        // Reject methods the application does not understand.
        if (request.method != "GET") {
            return {
                400,
                {{"Content-Type", "text/plain"}},
                "Only GET is supported by this case study"
            };
        }

        // Dynamic application endpoint.
        if (request.path.rfind("/api/hello", 0) == 0) {
            return handleHello(request);
        }

        // A real application server would have many more routes.
        return {
            404,
            {{"Content-Type", "text/plain"}},
            "Application route not found"
        };
    }

private:
    HttpResponse handleHello(const HttpRequest& request) {
        const std::string prefix = "/api/hello";

        std::string name = "world";
        const auto questionMark = request.path.find('?');

        if (questionMark != std::string::npos) {
            const std::string query =
                request.path.substr(questionMark + 1);

            const std::string key = "name=";
            const auto position = query.find(key);

            if (position != std::string::npos) {
                name = query.substr(position + key.size());

                // Very small validation example.
                // Production applications should use robust URL decoding.
                if (name.size() > 100) {
                    return {
                        400,
                        {{"Content-Type", "text/plain"}},
                        "Name is too long"
                    };
                }
            }
        }

        return {
            200,
            {{"Content-Type", "text/plain"}},
            "Hello, " + name + "!"
        };
    }
};


// ============================================================
// STATIC RESOURCE CLASSIFIER
// ============================================================

class StaticResourceService {
public:
    bool isStaticPath(const std::string& path) const {
        static const std::vector<std::string> extensions = {
            ".html", ".css", ".js", ".png", ".jpg", ".svg", ".ico"
        };

        const auto queryPosition = path.find('?');
        const std::string cleanPath =
            path.substr(0, queryPosition);

        for (const auto& extension : extensions) {
            if (cleanPath.size() >= extension.size() &&
                cleanPath.compare(
                    cleanPath.size() - extension.size(),
                    extension.size(),
                    extension
                ) == 0) {
                return true;
            }
        }

        return false;
    }

    HttpResponse serve(const std::string& path) const {
        // This case study does not read arbitrary filesystem paths.
        // That avoids turning a teaching program into an unsafe
        // unrestricted file server.
        return {
            200,
            {
                {"Content-Type", "text/plain"},
                {"Cache-Control", "public, max-age=3600"}
            },
            "Static resource: " + path
        };
    }
};


// ============================================================
// BACKEND SERVER
// ============================================================

class BackendServer {
public:
    BackendServer(
        std::string serverName,
        std::shared_ptr<ApplicationServer> applicationServer
    )
        : name_(std::move(serverName)),
          application_(std::move(applicationServer)) {}

    HttpResponse handle(const HttpRequest& request) {
        if (!healthy_) {
            throw std::runtime_error(
                name_ + " is unhealthy"
            );
        }

        ++requestCount_;
        return application_->handle(request);
    }

    bool healthCheck() const {
        return healthy_;
    }

    void setHealthy(bool healthy) {
        healthy_ = healthy;
    }

    const std::string& name() const {
        return name_;
    }

    std::size_t requestCount() const {
        return requestCount_;
    }

private:
    std::string name_;
    std::shared_ptr<ApplicationServer> application_;
    bool healthy_ = true;
    std::size_t requestCount_ = 0;
};


// ============================================================
// TTL CACHE
// ============================================================

struct CacheEntry {
    HttpResponse response;
    Clock::time_point expiresAt;
};

class ResponseCache {
public:
    explicit ResponseCache(
        std::chrono::milliseconds ttl
    )
        : ttl_(ttl) {}

    std::optional<HttpResponse> get(
        const std::string& key
    ) {
        const auto iterator = entries_.find(key);

        if (iterator == entries_.end()) {
            return std::nullopt;
        }

        if (Clock::now() >= iterator->second.expiresAt) {
            entries_.erase(iterator);
            return std::nullopt;
        }

        return iterator->second.response;
    }

    void put(
        const std::string& key,
        const HttpResponse& response
    ) {
        entries_[key] = CacheEntry{
            response,
            Clock::now() + ttl_
        };
    }

private:
    std::chrono::milliseconds ttl_;
    std::unordered_map<std::string, CacheEntry> entries_;
};


// ============================================================
// REVERSE PROXY
// ============================================================

class ReverseProxy {
public:
    explicit ReverseProxy(
        std::vector<std::shared_ptr<BackendServer>> backends
    )
        : backends_(std::move(backends)),
          cache_(std::chrono::seconds(5)) {

        if (backends_.empty()) {
            throw std::invalid_argument(
                "Reverse proxy requires at least one backend"
            );
        }
    }

    HttpResponse handle(const HttpRequest& request) {
        validateRequest(request);

        // Static content can be handled at the edge instead of
        // consuming application-server capacity.
        if (staticResources_.isStaticPath(request.path)) {
            HttpResponse response =
                staticResources_.serve(request.path);

            addSecurityHeaders(response);
            response.headers["X-Route"] = "static";
            return response;
        }

        // Only cache selected safe GET responses.
        if (request.method == "GET") {
            const auto cached = cache_.get(request.path);

            if (cached.has_value()) {
                HttpResponse response = *cached;
                response.headers["X-Cache"] = "HIT";
                return response;
            }
        }

        auto backend = selectBackend();

        if (!backend) {
            return {
                503,
                {{"Content-Type", "text/plain"}},
                "No healthy application server"
            };
        }

        HttpRequest forwarded = request;

        // The proxy can provide forwarding metadata.
        forwarded.headers["X-Forwarded-Proto"] = "http";
        forwarded.headers["X-Forwarded-Host"] =
            getHeader(request, "Host").value_or("unknown");

        try {
            auto start = Clock::now();

            HttpResponse response = backend->handle(forwarded);

            const auto elapsed =
                std::chrono::duration_cast<
                    std::chrono::microseconds
                >(Clock::now() - start).count();

            addSecurityHeaders(response);

            response.headers["X-Backend"] = backend->name();
            response.headers["X-Cache"] = "MISS";
            response.headers["X-Processing-Time-Us"] =
                std::to_string(elapsed);

            // Cache only successful GET responses.
            if (
                request.method == "GET" &&
                response.statusCode == 200
            ) {
                cache_.put(request.path, response);
            }

            return response;
        }
        catch (const std::exception& error) {
            return {
                502,
                {{"Content-Type", "text/plain"}},
                std::string("Bad Gateway: ") + error.what()
            };
        }
    }

private:
    static std::optional<std::string> getHeader(
        const HttpRequest& request,
        const std::string& name
    ) {
        const auto target = toLower(name);

        for (const auto& [key, value] : request.headers) {
            if (toLower(key) == target) {
                return value;
            }
        }

        return std::nullopt;
    }

    void validateRequest(
        const HttpRequest& request
    ) const {
        if (request.method.empty()) {
            throw std::invalid_argument(
                "HTTP method cannot be empty"
            );
        }

        if (request.path.empty() ||
            request.path.front() != '/') {
            throw std::invalid_argument(
                "Request path must start with /"
            );
        }

        // Prevent an obvious traversal form at this proxy layer.
        if (
            request.path.find("..") != std::string::npos
        ) {
            throw std::invalid_argument(
                "Potential path traversal rejected"
            );
        }

        if (request.body.size() > 1024 * 1024) {
            throw std::invalid_argument(
                "Request body exceeds 1 MiB demonstration limit"
            );
        }
    }

    std::shared_ptr<BackendServer> selectBackend() {
        const std::size_t count = backends_.size();

        for (std::size_t attempt = 0; attempt < count; ++attempt) {
            const std::size_t index =
                (nextIndex_ + attempt) % count;

            if (backends_[index]->healthCheck()) {
                nextIndex_ = (index + 1) % count;
                return backends_[index];
            }
        }

        return nullptr;
    }

    std::vector<std::shared_ptr<BackendServer>> backends_;
    std::size_t nextIndex_ = 0;
    ResponseCache cache_;
    StaticResourceService staticResources_;
};


// ============================================================
// ACCESS LOGGING
// ============================================================

void logRequest(
    const HttpRequest& request,
    const HttpResponse& response
) {
    std::cout
        << "[ACCESS] "
        << request.method
        << " "
        << request.path
        << " -> "
        << response.statusCode
        << " "
        << statusText(response.statusCode);

    const auto backend =
        response.headers.find("X-Backend");

    if (backend != response.headers.end()) {
        std::cout
            << " backend=" << backend->second;
    }

    const auto cache =
        response.headers.find("X-Cache");

    if (cache != response.headers.end()) {
        std::cout
            << " cache=" << cache->second;
    }

    std::cout << '\n';
}


// ============================================================
// CASE-STUDY SCENARIO
// ============================================================

void runCaseStudy() {
    std::cout
        << "WEB SERVER / REVERSE PROXY CASE STUDY\n\n";

    auto application =
        std::make_shared<ApplicationServer>();

    std::vector<std::shared_ptr<BackendServer>> backends;

    backends.push_back(
        std::make_shared<BackendServer>(
            "app-1",
            application
        )
    );

    backends.push_back(
        std::make_shared<BackendServer>(
            "app-2",
            application
        )
    );

    backends.push_back(
        std::make_shared<BackendServer>(
            "app-3",
            application
        )
    );

    ReverseProxy proxy(backends);

    std::vector<HttpRequest> requests = {
        {"GET", "/index.html", {{"Host", "example.test"}}, ""},
        {"GET", "/api/hello?name=Atul", {{"Host", "example.test"}}, ""},
        {"GET", "/api/hello?name=backend-test", {{"Host", "example.test"}}, ""},
        {"GET", "/style.css", {{"Host", "example.test"}}, ""},
        {"GET", "/api/hello?name=cache", {{"Host", "example.test"}}, ""},
        {"GET", "/api/hello?name=cache", {{"Host", "example.test"}}, ""}
    };

    std::cout << "Initial traffic:\n";

    for (const auto& request : requests) {
        HttpResponse response = proxy.handle(request);
        logRequest(request, response);
        std::cout << "Body: " << response.body << "\n\n";
    }

    std::cout
        << "Simulating backend failure: app-2\n";

    backends[1]->setHealthy(false);

    for (int index = 0; index < 5; ++index) {
        HttpRequest request{
            "GET",
            "/api/hello?name=after-failure-" +
                std::to_string(index),
            {{"Host", "example.test"}},
            ""
        };

        HttpResponse response = proxy.handle(request);
        logRequest(request, response);
    }

    std::cout
        << "\nSimulating total backend failure:\n";

    backends[0]->setHealthy(false);
    backends[2]->setHealthy(false);

    HttpRequest unavailableRequest{
        "GET",
        "/api/hello?name=unavailable",
        {{"Host", "example.test"}},
        ""
    };

    HttpResponse unavailable =
        proxy.handle(unavailableRequest);

    logRequest(unavailableRequest, unavailable);
    std::cout << "Body: " << unavailable.body << "\n";

    std::cout << "\nRestoring app-1:\n";

    backends[0]->setHealthy(true);

    HttpResponse recovered =
        proxy.handle(unavailableRequest);

    logRequest(unavailableRequest, recovered);
    std::cout << "Body: " << recovered.body << "\n";

    std::cout << "\nBackend request counts:\n";

    for (const auto& backend : backends) {
        std::cout
            << backend->name()
            << ": "
            << backend->requestCount()
            << '\n';
    }
}


// ============================================================
// COMPLEXITY DISCUSSION
// ============================================================

void printComplexity() {
    std::cout
        << "\nCOMPLEXITY AND DESIGN NOTES\n"
        << "Backend selection scans at most N backends: O(N).\n"
        << "Round-robin state makes ordinary selection O(1), "
           "while health filtering can require O(N).\n"
        << "The cache uses unordered_map lookup, expected O(1).\n"
        << "The case study uses shared application state to keep "
           "the demonstration compact.\n"
        << "A real deployment normally runs independent application "
           "processes or containers.\n";
}


// ============================================================
// MAIN
// ============================================================

int main() {
    try {
        runCaseStudy();
        printComplexity();

        std::cout
            << "\nARCHITECTURE\n"
            << "Client -> Reverse Proxy -> Application Servers\n"
            << "                      -> Cache\n"
            << "                      -> Application Logic\n"
            << "\nThe reverse proxy is the controlled entry point. "
               "It can route traffic, reject malformed requests, "
               "serve static resources, add headers, cache safe "
               "responses, and avoid unhealthy backends.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal configuration or runtime error: "
            << error.what()
            << '\n';

        return 1;
    }
}
