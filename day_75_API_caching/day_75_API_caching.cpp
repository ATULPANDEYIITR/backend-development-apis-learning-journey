#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class CacheResult {
    HIT,
    MISS,
    REVALIDATED,
    BYPASS
};

enum class CacheDirective {
    PUBLIC,
    PRIVATE,
    NO_STORE,
    NO_CACHE,
    MUST_REVALIDATE
};

struct CachePolicy {
    int maxAge = 0;
    int sMaxAge = -1;
    bool isPublic = false;
    bool isPrivate = false;
    bool noStore = false;
    bool noCache = false;
    bool mustRevalidate = false;

    int lifetime(bool shared) const {
        if (shared && sMaxAge >= 0) {
            return sMaxAge;
        }

        return maxAge;
    }

    static CachePolicy parse(const string& header) {
        if (header.size() > 4096) {
            throw invalid_argument("Cache-Control too large");
        }

        CachePolicy policy;
        istringstream stream(header);
        string token;

        while (getline(stream, token, ',')) {
            size_t start = token.find_first_not_of(" \t");
            size_t end = token.find_last_not_of(" \t");

            if (start == string::npos) continue;

            token = token.substr(start, end - start + 1);

            size_t position = token.find('=');

            string key = token.substr(0, position);
            string value = position == string::npos
                ? ""
                : token.substr(position + 1);

            transform(
                key.begin(), key.end(), key.begin(),
                [](unsigned char c) {
                    return static_cast<char>(tolower(c));
                }
            );

            auto parseAge = [&value]() {
                if (value.empty()) {
                    throw invalid_argument("Missing age value");
                }

                size_t used = 0;
                long long parsed = stoll(value, &used);

                if (used != value.size() || parsed < 0 ||
                    parsed > 2147483647LL) {
                    throw invalid_argument("Invalid cache age");
                }

                return static_cast<int>(parsed);
            };

            if (key == "max-age") {
                policy.maxAge = parseAge();
            } else if (key == "s-maxage") {
                policy.sMaxAge = parseAge();
            } else if (key == "public") {
                policy.isPublic = true;
            } else if (key == "private") {
                policy.isPrivate = true;
            } else if (key == "no-store") {
                policy.noStore = true;
            } else if (key == "no-cache") {
                policy.noCache = true;
            } else if (key == "must-revalidate") {
                policy.mustRevalidate = true;
            }
        }

        return policy;
    }
};

struct HTTPResponse {
    int status = 200;
    string body;
    string etag;
    string cacheControl;
    string lastModified;
};

struct BranchPolicy {
    bool protectedBranch = true;
    bool requireAuthentication = true;
    bool allowDirectPush = false;
    bool requireETag = true;
    bool allowStale = false;
};

struct CacheEntry {
    HTTPResponse response;
    chrono::steady_clock::time_point storedAt;
    int initialAge = 0;
    int freshness = 0;
    bool mustRevalidate = false;

    bool fresh() const {
        auto elapsed =
            chrono::duration_cast<chrono::seconds>(
                chrono::steady_clock::now() - storedAt
            ).count();

        return initialAge + elapsed < freshness;
    }
};

class OriginServer {
private:
    unordered_map<string, HTTPResponse> resources;
    int requestCount = 0;

public:
    void publish(
        const string& path,
        const string& body,
        const string& cacheControl
    ) {
        if (path.empty() || path[0] != '/') {
            throw invalid_argument("Invalid resource path");
        }

        HTTPResponse response;
        response.status = 200;
        response.body = body;
        response.cacheControl = cacheControl;
        response.etag = "\"" + to_string(
            hash<string>{}(body)
        ) + "\"";

        response.lastModified = "origin-version-1";

        resources[path] = response;
    }

    HTTPResponse fetch(
        const string& path,
        const string& ifNoneMatch = ""
    ) {
        requestCount++;

        auto it = resources.find(path);

        if (it == resources.end()) {
            return {404, "Not found", "", "", ""};
        }

        HTTPResponse response = it->second;

        if (!ifNoneMatch.empty() &&
            ifNoneMatch == response.etag) {
            response.status = 304;
            response.body.clear();
        }

        return response;
    }

    int requests() const {
        return requestCount;
    }
};

class CacheEngine {
private:
    struct Node {
        CacheEntry entry;
        list<string>::iterator position;
    };

    OriginServer& origin;
    BranchPolicy policy;
    size_t capacity;

    unordered_map<string, Node> entries;
    list<string> lru;

    void store(
        const string& key,
        const HTTPResponse& response
    ) {
        CachePolicy directives =
            CachePolicy::parse(response.cacheControl);

        if (directives.noStore) return;

        if (directives.isPrivate && policy.requireAuthentication) {
            return;
        }

        if (directives.noCache) {
            // Stored representation requires validation on every use.
        }

        if (entries.find(key) != entries.end()) {
            lru.erase(entries[key].position);
            entries.erase(key);
        }

        CacheEntry entry;
        entry.response = response;
        entry.storedAt = chrono::steady_clock::now();
        entry.freshness = directives.lifetime(true);
        entry.mustRevalidate = directives.mustRevalidate;

        lru.push_front(key);

        entries.emplace(
            key,
            Node{entry, lru.begin()}
        );

        while (entries.size() > capacity) {
            string oldest = lru.back();
            lru.pop_back();
            entries.erase(oldest);
        }
    }

public:
    CacheEngine(
        OriginServer& server,
        size_t maximumEntries,
        BranchPolicy branchPolicy
    ) : origin(server),
        policy(branchPolicy),
        capacity(maximumEntries) {

        if (capacity == 0) {
            throw invalid_argument("Capacity must be positive");
        }
    }

    pair<HTTPResponse, CacheResult> get(
        const string& path,
        bool authenticated = false,
        bool forceRevalidate = false
    ) {
        if (path.empty() || path[0] != '/') {
            throw invalid_argument("Invalid cache path");
        }

        if (policy.requireAuthentication && !authenticated) {
            return {
                origin.fetch(path),
                CacheResult::BYPASS
            };
        }

        auto found = entries.find(path);

        if (found != entries.end()) {
            CacheEntry& entry = found->second.entry;

            if (entry.fresh() && !forceRevalidate) {
                lru.erase(found->second.position);
                lru.push_front(path);
                found->second.position = lru.begin();

                return {
                    entry.response,
                    CacheResult::HIT
                };
            }

            if (entry.response.etag.empty() &&
                policy.requireETag) {
                return {
                    origin.fetch(path),
                    CacheResult::BYPASS
                };
            }

            HTTPResponse response = origin.fetch(
                path,
                entry.response.etag
            );

            if (response.status == 304) {
                entry.storedAt = chrono::steady_clock::now();

                CachePolicy directives =
                    CachePolicy::parse(response.cacheControl);

                entry.freshness = directives.lifetime(true);

                return {
                    entry.response,
                    CacheResult::REVALIDATED
                };
            }

            if (response.status == 200) {
                store(path, response);

                return {
                    response,
                    CacheResult::MISS
                };
            }

            return {response, CacheResult::BYPASS};
        }

        HTTPResponse response = origin.fetch(path);

        if (response.status == 200) {
            store(path, response);
        }

        return {response, CacheResult::MISS};
    }

    size_t invalidate(const string& path) {
        auto found = entries.find(path);

        if (found == entries.end()) return 0;

        lru.erase(found->second.position);
        entries.erase(found);

        return 1;
    }

    size_t size() const {
        return entries.size();
    }
};

string resultName(CacheResult result) {
    switch (result) {
        case CacheResult::HIT: return "HIT";
        case CacheResult::MISS: return "MISS";
        case CacheResult::REVALIDATED: return "REVALIDATED";
        case CacheResult::BYPASS: return "BYPASS";
    }

    return "UNKNOWN";
}

int main() {
    try {
        OriginServer origin;

        origin.publish(
            "/api/assets/1001",
            "{\"id\":1001,\"name\":\"Firewall\",\"stock\":25}",
            "public, max-age=60, s-maxage=120, must-revalidate"
        );

        origin.publish(
            "/api/assets/1002",
            "{\"id\":1002,\"name\":\"Gateway\",\"stock\":10}",
            "public, max-age=30"
        );

        BranchPolicy configuration;
        configuration.protectedBranch = true;
        configuration.requireAuthentication = true;
        configuration.allowDirectPush = false;
        configuration.requireETag = true;
        configuration.allowStale = false;

        CacheEngine cache(origin, 2, configuration);

        cout << "API CACHE GOVERNANCE ENGINE\n";
        cout << "===========================\n\n";

        auto first = cache.get("/api/assets/1001", true);

        cout << "First request: "
             << resultName(first.second)
             << " | HTTP " << first.first.status
             << '\n';

        auto second = cache.get("/api/assets/1001", true);

        cout << "Second request: "
             << resultName(second.second)
             << '\n';

        auto unauthenticated = cache.get(
            "/api/assets/1001",
            false
        );

        cout << "Unauthenticated request: "
             << resultName(unauthenticated.second)
             << '\n';

        auto third = cache.get(
            "/api/assets/1001",
            true,
            true
        );

        cout << "Conditional request: "
             << resultName(third.second)
             << '\n';

        cache.get("/api/assets/1002", true);

        cout << "Cached entries: "
             << cache.size() << '\n';

        cout << "Origin requests: "
             << origin.requests() << '\n';

        cout << "Invalidated entries: "
             << cache.invalidate("/api/assets/1001")
             << '\n';

        cout << "Entries after invalidation: "
             << cache.size() << '\n';

        cout << "\nCache-Control validation\n";

        CachePolicy policy = CachePolicy::parse(
            "public, max-age=300, s-maxage=600, must-revalidate"
        );

        cout << "Shared lifetime: "
             << policy.lifetime(true) << " seconds\n";

        try {
            CachePolicy::parse("max-age=-10");
        } catch (const exception& error) {
            cout << "Rejected invalid directive: "
                 << error.what() << '\n';
        }

        try {
            CacheEngine invalidCache(origin, 0, configuration);
        } catch (const exception& error) {
            cout << "Rejected invalid capacity: "
                 << error.what() << '\n';
        }

    } catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
