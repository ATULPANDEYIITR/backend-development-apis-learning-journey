#include <algorithm>
#include <ctime>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>

enum class SameSite {
    Strict,
    Lax,
    None
};

std::string sameSiteName(SameSite value) {
    switch (value) {
        case SameSite::Strict: return "Strict";
        case SameSite::Lax: return "Lax";
        case SameSite::None: return "None";
    }
    throw std::logic_error("Unknown SameSite policy");
}

struct CookiePolicy {
    std::string name;
    bool secure;
    bool httpOnly;
    SameSite sameSite;
    std::string path;
    int maxAge;

    CookiePolicy(
        std::string cookieName,
        bool useSecure,
        bool useHttpOnly,
        SameSite site,
        std::string cookiePath = "/",
        int lifetime = 1800
    )
        : name(std::move(cookieName)),
          secure(useSecure),
          httpOnly(useHttpOnly),
          sameSite(site),
          path(std::move(cookiePath)),
          maxAge(lifetime) {
        if (name.empty() || name.find_first_of(" \t\r\n;=") != std::string::npos) {
            throw std::invalid_argument("Invalid cookie name");
        }
        if (path.empty() || path.front() != '/' ||
            path.find_first_of(";\r\n") != std::string::npos) {
            throw std::invalid_argument("Invalid cookie path");
        }
        if (maxAge < 0) {
            throw std::invalid_argument("Cookie lifetime cannot be negative");
        }
        if (sameSite == SameSite::None && !secure) {
            throw std::invalid_argument("SameSite=None requires Secure");
        }
    }

    std::string setCookieHeader(const std::string& value) const {
        if (value.empty() || value.find_first_of(";\r\n") != std::string::npos) {
            throw std::invalid_argument("Invalid cookie value");
        }

        std::string result = name + "=" + value +
            "; Path=" + path +
            "; Max-Age=" + std::to_string(maxAge) +
            "; SameSite=" + sameSiteName(sameSite);

        if (httpOnly) result += "; HttpOnly";
        if (secure) result += "; Secure";
        return result;
    }
};

struct BrowserRequestContext {
    bool crossSite;
    bool topLevelNavigation;
    std::string method;
    bool isTls;
};

bool cookieWouldBeSent(
    const CookiePolicy& policy,
    const BrowserRequestContext& context
) {
    std::string method = context.method;
    std::transform(
        method.begin(), method.end(), method.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::toupper(character));
        }
    );

    if (policy.secure && !context.isTls) return false;
    if (!context.crossSite) return true;

    if (policy.sameSite == SameSite::Strict) return false;

    if (policy.sameSite == SameSite::Lax) {
        return context.topLevelNavigation &&
            (method == "GET" || method == "HEAD");
    }

    return policy.sameSite == SameSite::None && policy.secure;
}

std::string htmlEscape(const std::string& input) {
    std::string output;
    output.reserve(input.size());

    for (char character : input) {
        switch (character) {
            case '&': output += "&amp;"; break;
            case '<': output += "&lt;"; break;
            case '>': output += "&gt;"; break;
            case '"': output += "&quot;"; break;
            case '\'': output += "&#39;"; break;
            default: output += character;
        }
    }
    return output;
}

struct Session {
    std::string id;
    std::string userId;
    std::string csrfToken;
    std::time_t expiresAt;
    bool revoked = false;
};

class SessionStore {
private:
    std::unordered_map<std::string, Session> sessions;

public:
    void add(Session session) {
        if (session.id.empty() || session.userId.empty() ||
            session.csrfToken.empty()) {
            throw std::invalid_argument("Incomplete session");
        }

        if (!sessions.emplace(session.id, std::move(session)).second) {
            throw std::invalid_argument("Duplicate session identifier");
        }
    }

    const Session* find(const std::string& sessionId) const {
        auto iterator = sessions.find(sessionId);
        if (iterator == sessions.end()) return nullptr;
        return &iterator->second;
    }

    void revoke(const std::string& sessionId) {
        auto iterator = sessions.find(sessionId);
        if (iterator != sessions.end()) {
            iterator->second.revoked = true;
        }
    }
};

struct Request {
    std::string sessionId;
    std::string csrfToken;
    std::string origin;
    std::string method;
};

bool isStateChangingMethod(std::string method) {
    std::transform(
        method.begin(), method.end(), method.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::toupper(character));
        }
    );

    return method == "POST" || method == "PUT" ||
        method == "PATCH" || method == "DELETE";
}

/*
 * Educational comparison only. Standard C++ does not guarantee constant-time
 * string comparison. Production code should use an audited cryptographic
 * library's constant-time comparison primitive.
 */
bool constantTimeCompareForDemonstration(
    const std::string& left,
    const std::string& right
) {
    const std::size_t maxLength = std::max(left.size(), right.size());
    unsigned int difference =
        static_cast<unsigned int>(left.size() ^ right.size());

    for (std::size_t index = 0; index < maxLength; ++index) {
        const unsigned char a =
            index < left.size() ? static_cast<unsigned char>(left[index]) : 0;
        const unsigned char b =
            index < right.size() ? static_cast<unsigned char>(right[index]) : 0;
        difference |= static_cast<unsigned int>(a ^ b);
    }

    return difference == 0;
}

class CsrfGuard {
private:
    const SessionStore& sessions;
    std::string expectedOrigin;

public:
    CsrfGuard(const SessionStore& store, std::string applicationOrigin)
        : sessions(store), expectedOrigin(std::move(applicationOrigin)) {
        if (expectedOrigin.rfind("https://", 0) != 0 ||
            expectedOrigin.find_first_of(" \t\r\n") != std::string::npos) {
            throw std::invalid_argument("Expected origin must be HTTPS");
        }
    }

    const Session& verify(const Request& request) const {
        if (!isStateChangingMethod(request.method)) {
            throw std::runtime_error("State-changing method required");
        }

        const Session* session = sessions.find(request.sessionId);
        if (session == nullptr || session->revoked) {
            throw std::runtime_error("Unknown or revoked session");
        }

        if (session->expiresAt <= std::time(nullptr)) {
            throw std::runtime_error("Session has expired");
        }

        if (request.origin != expectedOrigin) {
            throw std::runtime_error("Origin validation failed");
        }

        if (!constantTimeCompareForDemonstration(
                session->csrfToken, request.csrfToken)) {
            throw std::runtime_error("CSRF token validation failed");
        }

        return *session;
    }
};

class CommentStore {
private:
    std::unordered_map<int, std::string> comments;
    int nextId = 1;

public:
    int add(const std::string& content) {
        if (content.empty() || content.size() > 5000) {
            throw std::invalid_argument("Comment is empty or too large");
        }
        if (content.find('\0') != std::string::npos) {
            throw std::invalid_argument("Comment contains a null character");
        }

        const int id = nextId++;
        comments.emplace(id, content);
        return id;
    }

    std::string render(int id) const {
        auto iterator = comments.find(id);
        if (iterator == comments.end()) {
            throw std::out_of_range("Comment does not exist");
        }

        return "<article>" + htmlEscape(iterator->second) + "</article>";
    }

    const std::string& raw(int id) const {
        auto iterator = comments.find(id);
        if (iterator == comments.end()) {
            throw std::out_of_range("Comment does not exist");
        }
        return iterator->second;
    }
};

std::string renderReflectedQuery(const std::string& query) {
    if (query.empty() || query.size() > 5000) {
        throw std::invalid_argument("Invalid search query length");
    }

    return "<p>Search results for: " + htmlEscape(query) + "</p>";
}

int main() {
    try {
        const CookiePolicy cookie(
            "__Host-session", true, true, SameSite::Lax
        );

        // This fixed value is test data, not a production token-generation method.
        const Session session{
            "session-demo-01",
            "customer-402",
            "csrf-demo-token-01",
            std::time(nullptr) + 1800,
            false
        };

        SessionStore sessionStore;
        sessionStore.add(session);

        std::cout << "COOKIE POLICY\n"
                  << cookie.setCookieHeader(session.id) << "\n\n";

        std::cout << "SAMESITE EVALUATION\n";
        std::cout << "Cross-site POST: "
                  << std::boolalpha
                  << cookieWouldBeSent(cookie, {
                         true, false, "POST", true
                     })
                  << '\n';

        std::cout << "Cross-site top-level GET: "
                  << cookieWouldBeSent(cookie, {
                         true, true, "GET", true
                     })
                  << "\n\n";

        const std::string untrusted =
            "<script>alert('untrusted')</script>";

        std::cout << "REFLECTED XSS DEFENSE\n"
                  << renderReflectedQuery(untrusted) << "\n\n";

        CommentStore comments;
        CsrfGuard guard(sessionStore, "https://portal.example.test");

        Request validRequest{
            session.id,
            session.csrfToken,
            "https://portal.example.test",
            "POST"
        };

        const Session& authenticated = guard.verify(validRequest);
        const int commentId = comments.add(untrusted);

        std::cout << "STORED XSS DEFENSE\n";
        std::cout << "Author: " << authenticated.userId << '\n';
        std::cout << "Raw stored input: " << comments.raw(commentId) << '\n';
        std::cout << "Rendered output: " << comments.render(commentId) << "\n\n";

        std::cout << "CSRF VALIDATION\n";

        Request invalidToken = validRequest;
        invalidToken.csrfToken = "incorrect";

        try {
            guard.verify(invalidToken);
            throw std::logic_error("Invalid token was accepted");
        } catch (const std::runtime_error& error) {
            std::cout << "Invalid token rejected: " << error.what() << '\n';
        }

        Request foreignOrigin = validRequest;
        foreignOrigin.origin = "https://attacker.example";

        try {
            guard.verify(foreignOrigin);
            throw std::logic_error("Foreign origin was accepted");
        } catch (const std::runtime_error& error) {
            std::cout << "Foreign origin rejected: " << error.what() << '\n';
        }

        sessionStore.revoke(session.id);
        try {
            guard.verify(validRequest);
            throw std::logic_error("Revoked session was accepted");
        } catch (const std::runtime_error& error) {
            std::cout << "Revoked session rejected: " << error.what() << '\n';
        }

        std::cout << "\nAll demonstration checks completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Application error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
