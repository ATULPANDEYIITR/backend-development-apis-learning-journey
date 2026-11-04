#include <algorithm>
#include <cctype>
#include <chrono>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using namespace std;

enum class RequestKind {
    Simple,
    Preflight,
    Actual
};

enum class Decision {
    Allowed,
    OriginDenied,
    MethodDenied,
    HeaderDenied,
    CredentialsDenied,
    InvalidRequest,
    PrivateNetworkDenied
};

struct Origin {
    string scheme;
    string host;
    optional<int> port;

    string toString() const {
        string result = scheme + "://";

        if (host.find(':') != string::npos &&
            host.front() != '[') {
            result += "[" + host + "]";
        } else {
            result += host;
        }

        if (port.has_value()) {
            result += ":" + to_string(port.value());
        }

        return result;
    }

    static Origin parse(const string& value) {
        if (value.empty() || value == "null") {
            throw invalid_argument("Invalid or opaque origin.");
        }

        size_t separator = value.find("://");

        if (separator == string::npos) {
            throw invalid_argument("Missing origin scheme.");
        }

        string scheme = value.substr(0, separator);
        transform(
            scheme.begin(), scheme.end(),
            scheme.begin(), ::tolower
        );

        if (scheme != "http" && scheme != "https") {
            throw invalid_argument("Unsupported origin scheme.");
        }

        string authority = value.substr(separator + 3);

        if (authority.empty() ||
            authority.find_first_of("/?#@") != string::npos) {
            throw invalid_argument("Invalid origin authority.");
        }

        string host;
        optional<int> port;

        if (authority.front() == '[') {
            size_t close = authority.find(']');

            if (close == string::npos) {
                throw invalid_argument("Invalid IPv6 hostname.");
            }

            host = authority.substr(1, close - 1);

            string remainder = authority.substr(close + 1);

            if (!remainder.empty()) {
                if (remainder.front() != ':') {
                    throw invalid_argument("Invalid authority.");
                }

                port = parsePort(remainder.substr(1));
            }
        } else {
            size_t colon = authority.rfind(':');

            if (colon != string::npos) {
                if (authority.find(':') != colon) {
                    throw invalid_argument("IPv6 must be bracketed.");
                }

                host = authority.substr(0, colon);
                port = parsePort(authority.substr(colon + 1));
            } else {
                host = authority;
            }
        }

        if (host.empty()) {
            throw invalid_argument("Missing hostname.");
        }

        transform(
            host.begin(), host.end(),
            host.begin(), ::tolower
        );

        if (host.back() == '.') {
            host.pop_back();
        }

        if (host.empty()) {
            throw invalid_argument("Invalid hostname.");
        }

        if ((scheme == "http" && port == 80) ||
            (scheme == "https" && port == 443)) {
            port.reset();
        }

        return {scheme, host, port};
    }

private:
    static int parsePort(const string& text) {
        if (text.empty()) {
            throw invalid_argument("Empty port.");
        }

        int value = 0;

        for (char c : text) {
            if (!isdigit(static_cast<unsigned char>(c))) {
                throw invalid_argument("Invalid port.");
            }

            value = value * 10 + (c - '0');

            if (value > 65535) {
                throw invalid_argument("Port out of range.");
            }
        }

        if (value < 1) {
            throw invalid_argument("Port out of range.");
        }

        return value;
    }
};

struct Request {
    string origin;
    string method;
    set<string> requestedHeaders;
    string requestedMethod;
    bool credentials = false;
    bool privateNetwork = false;
};

struct Response {
    int status;
    Decision decision;
    map<string, string> headers;
    string message;

    bool allowed() const {
        return decision == Decision::Allowed;
    }
};

struct AuditRecord {
    string origin;
    string method;
    Decision decision;
};

struct CorsPolicy {
    set<string> allowedOrigins;
    set<string> allowedMethods;
    set<string> allowedHeaders;
    set<string> exposedHeaders;

    bool allowCredentials = false;
    bool allowPrivateNetwork = false;
    int maxAge = 600;

    void validate() const {
        if (allowedOrigins.empty()) {
            throw invalid_argument("No origins configured.");
        }

        if (maxAge < 0 || maxAge > 86400) {
            throw invalid_argument("Invalid max-age.");
        }

        if (allowedOrigins.count("*") && allowCredentials) {
            throw invalid_argument(
                "Wildcard origin cannot allow credentials."
            );
        }

        for (const string& origin : allowedOrigins) {
            if (origin != "*") {
                Origin::parse(origin);
            }
        }
    }
};

class CorsGateway {
private:
    CorsPolicy policy;

    using CacheKey = tuple<
        string, string, set<string>, bool, bool
    >;

    map<CacheKey, chrono::steady_clock::time_point> cache;
    vector<AuditRecord> audit;

    void record(
        const Request& request,
        Decision decision
    ) {
        audit.push_back({
            request.origin,
            request.method,
            decision
        });
    }

    map<string, string> buildHeaders(
        const string& origin
    ) const {
        map<string, string> headers;

        headers["Access-Control-Allow-Origin"] = origin;

        if (policy.allowCredentials) {
            headers["Access-Control-Allow-Credentials"] = "true";
        }

        if (origin != "*") {
            headers["Vary"] = "Origin";
        }

        if (!policy.exposedHeaders.empty()) {
            string result;

            for (const auto& header : policy.exposedHeaders) {
                if (!result.empty()) result += ", ";
                result += header;
            }

            headers["Access-Control-Expose-Headers"] = result;
        }

        return headers;
    }

    Response denied(
        const Request& request,
        int status,
        Decision decision,
        const string& message
    ) {
        record(request, decision);

        return {
            status,
            decision,
            {},
            message
        };
    }

public:
    explicit CorsGateway(CorsPolicy configuration)
        : policy(std::move(configuration)) {
        policy.validate();
    }

    Response evaluate(const Request& request) {
        if (request.origin.empty()) {
            record(request, Decision::Allowed);

            return {
                200,
                Decision::Allowed,
                {},
                "No CORS processing required."
            };
        }

        Origin parsed;

        try {
            parsed = Origin::parse(request.origin);
        } catch (const exception& error) {
            return denied(
                request,
                403,
                Decision::InvalidRequest,
                error.what()
            );
        }

        string normalized = parsed.toString();
        string resolved;

        if (policy.allowedOrigins.count("*") &&
            !policy.allowCredentials) {
            resolved = "*";
        } else if (policy.allowedOrigins.count(normalized)) {
            resolved = normalized;
        } else {
            return denied(
                request,
                403,
                Decision::OriginDenied,
                "Origin is not allowed."
            );
        }

        if (request.credentials && !policy.allowCredentials) {
            return denied(
                request,
                403,
                Decision::CredentialsDenied,
                "Credentials are not allowed."
            );
        }

        string method = request.method;
        transform(
            method.begin(), method.end(),
            method.begin(), ::toupper
        );

        auto headers = buildHeaders(resolved);

        if (method == "OPTIONS" &&
            !request.requestedMethod.empty()) {
            return preflight(
                request,
                resolved,
                std::move(headers)
            );
        }

        if (!policy.allowedMethods.count(method)) {
            return denied(
                request,
                405,
                Decision::MethodDenied,
                "HTTP method is not allowed."
            );
        }

        record(request, Decision::Allowed);

        return {
            200,
            Decision::Allowed,
            std::move(headers),
            "Request accepted."
        };
    }

    Response preflight(
        const Request& request,
        const string& origin,
        map<string, string> headers
    ) {
        string method = request.requestedMethod;

        transform(
            method.begin(), method.end(),
            method.begin(), ::toupper
        );

        if (method.empty() ||
            !all_of(
                method.begin(),
                method.end(),
                [](unsigned char c) { return isalpha(c); }
            )) {
            return denied(
                request,
                400,
                Decision::InvalidRequest,
                "Invalid requested method."
            );
        }

        if (!policy.allowedMethods.count(method)) {
            return denied(
                request,
                403,
                Decision::MethodDenied,
                "Requested method is not allowed."
            );
        }

        for (const auto& header : request.requestedHeaders) {
            if (!policy.allowedHeaders.count(header)) {
                return denied(
                    request,
                    403,
                    Decision::HeaderDenied,
                    "Requested header is not allowed."
                );
            }
        }

        if (request.privateNetwork &&
            !policy.allowPrivateNetwork) {
            return denied(
                request,
                403,
                Decision::PrivateNetworkDenied,
                "Private network access is not allowed."
            );
        }

        CacheKey key = {
            origin,
            method,
            request.requestedHeaders,
            request.credentials,
            request.privateNetwork
        };

        auto now = chrono::steady_clock::now();
        auto entry = cache.find(key);

        if (entry != cache.end() && entry->second > now) {
            record(request, Decision::Allowed);

            return {
                204,
                Decision::Allowed,
                std::move(headers),
                "Cached preflight accepted."
            };
        }

        cache.erase(key);

        string methods;
        for (const auto& allowed : policy.allowedMethods) {
            if (!methods.empty()) methods += ", ";
            methods += allowed;
        }

        string requested;
        for (const auto& header : request.requestedHeaders) {
            if (!requested.empty()) requested += ", ";
            requested += header;
        }

        headers["Access-Control-Allow-Methods"] = methods;
        headers["Access-Control-Allow-Headers"] = requested;
        headers["Access-Control-Max-Age"] =
            to_string(policy.maxAge);

        if (request.privateNetwork) {
            headers["Access-Control-Allow-Private-Network"] = "true";
        }

        if (policy.maxAge > 0) {
            cache[key] = now + chrono::seconds(policy.maxAge);
        }

        record(request, Decision::Allowed);

        return {
            204,
            Decision::Allowed,
            std::move(headers),
            "Preflight accepted."
        };
    }

    void printAudit() const {
        cout << "\nAudit records: " << audit.size() << "\n";

        for (const auto& item : audit) {
            cout << item.origin << " | "
                 << item.method << " | "
                 << static_cast<int>(item.decision)
                 << '\n';
        }
    }
};

string decisionName(Decision decision) {
    switch (decision) {
        case Decision::Allowed: return "ALLOWED";
        case Decision::OriginDenied: return "ORIGIN_DENIED";
        case Decision::MethodDenied: return "METHOD_DENIED";
        case Decision::HeaderDenied: return "HEADER_DENIED";
        case Decision::CredentialsDenied: return "CREDENTIALS_DENIED";
        case Decision::InvalidRequest: return "INVALID_REQUEST";
        case Decision::PrivateNetworkDenied:
            return "PRIVATE_NETWORK_DENIED";
    }

    return "UNKNOWN";
}

void printResponse(
    const string& scenario,
    const Response& response
) {
    cout << "\n" << scenario << '\n';
    cout << "HTTP Status: " << response.status << '\n';
    cout << "Decision: " << decisionName(response.decision) << '\n';
    cout << "Message: " << response.message << '\n';

    for (const auto& [name, value] : response.headers) {
        cout << name << ": " << value << '\n';
    }
}

int main() {
    try {
        CorsPolicy policy;

        policy.allowedOrigins = {
            "https://app.example.com",
            "https://admin.example.com"
        };

        policy.allowedMethods = {
            "GET", "POST", "PUT", "DELETE"
        };

        policy.allowedHeaders = {
            "content-type",
            "authorization",
            "x-request-id"
        };

        policy.exposedHeaders = {
            "x-request-id"
        };

        policy.allowCredentials = true;
        policy.maxAge = 600;

        CorsGateway gateway(policy);

        vector<pair<string, Request>> scenarios = {
            {
                "Allowed GET",
                {
                    "https://app.example.com",
                    "GET"
                }
            },
            {
                "Allowed POST preflight",
                {
                    "https://app.example.com",
                    "OPTIONS",
                    {"authorization", "content-type"},
                    "POST",
                    true
                }
            },
            {
                "Unauthorized origin",
                {
                    "https://malicious.example.net",
                    "GET"
                }
            },
            {
                "Unsupported PATCH",
                {
                    "https://app.example.com",
                    "PATCH"
                }
            },
            {
                "Forbidden request header",
                {
                    "https://app.example.com",
                    "OPTIONS",
                    {"x-dangerous-header"},
                    "POST"
                }
            },
            {
                "Credentials disabled request",
                {
                    "https://app.example.com",
                    "GET",
                    {},
                    "",
                    false
                }
            }
        };

        for (const auto& [name, request] : scenarios) {
            printResponse(name, gateway.evaluate(request));
        }

        // Repeat the preflight to demonstrate cache behavior.
        Request repeated = {
            "https://app.example.com",
            "OPTIONS",
            {"authorization", "content-type"},
            "POST",
            true
        };

        printResponse(
            "Repeated preflight",
            gateway.evaluate(repeated)
        );

        // Origin normalization.
        Origin normalized = Origin::parse(
            "HTTPS://APP.EXAMPLE.COM:443"
        );

        if (normalized.toString() != "https://app.example.com") {
            throw runtime_error("Origin normalization failed.");
        }

        gateway.printAudit();

        cout << "\nAll C++17 checks completed.\n";

    } catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
