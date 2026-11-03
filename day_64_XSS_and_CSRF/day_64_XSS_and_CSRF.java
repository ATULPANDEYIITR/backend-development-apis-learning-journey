import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public class WebSecurityEnterprise {

    enum SameSite {
        STRICT("Strict"),
        LAX("Lax"),
        NONE("None");

        private final String headerValue;

        SameSite(String headerValue) {
            this.headerValue = headerValue;
        }

        public String headerValue() {
            return headerValue;
        }
    }

    record CookiePolicy(
        String name,
        boolean secure,
        boolean httpOnly,
        SameSite sameSite,
        String path,
        int maxAgeSeconds
    ) {
        CookiePolicy {
            if (name == null || !name.matches("[!#$%&'*+.^_`|~0-9A-Za-z-]+")) {
                throw new IllegalArgumentException("Invalid cookie name");
            }
            if (sameSite == null) {
                throw new IllegalArgumentException("SameSite policy is required");
            }
            if (path == null || !path.startsWith("/") || path.contains(";")) {
                throw new IllegalArgumentException("Invalid cookie path");
            }
            if (maxAgeSeconds < 0) {
                throw new IllegalArgumentException("Cookie lifetime cannot be negative");
            }
            if (sameSite == SameSite.NONE && !secure) {
                throw new IllegalArgumentException("SameSite=None requires Secure");
            }
        }

        String toSetCookieHeader(String value) {
            if (value == null || value.isBlank() ||
                value.contains(";") || value.contains("\r") || value.contains("\n")) {
                throw new IllegalArgumentException("Invalid cookie value");
            }

            StringBuilder header = new StringBuilder()
                .append(name).append('=').append(value)
                .append("; Path=").append(path)
                .append("; Max-Age=").append(maxAgeSeconds)
                .append("; SameSite=").append(sameSite.headerValue());

            if (httpOnly) header.append("; HttpOnly");
            if (secure) header.append("; Secure");
            return header.toString();
        }
    }

    record BrowserContext(
        boolean crossSite,
        boolean topLevelNavigation,
        String method,
        boolean tls
    ) {}

    static boolean cookieWouldBeSent(
        CookiePolicy policy,
        BrowserContext context
    ) {
        String method = context.method().toUpperCase();

        if (policy.secure() && !context.tls()) return false;
        if (!context.crossSite()) return true;

        return switch (policy.sameSite()) {
            case STRICT -> false;
            case LAX -> context.topLevelNavigation()
                && Set.of("GET", "HEAD").contains(method);
            case NONE -> policy.secure();
        };
    }

    record WebSession(
        String sessionId,
        String userId,
        String csrfToken,
        Instant expiresAt,
        boolean revoked
    ) {}

    record Comment(
        long id,
        String userId,
        String rawBody,
        Instant createdAt
    ) {}

    record MutationRequest(
        String sessionId,
        String csrfToken,
        String origin,
        String method
    ) {}

    record SecurityDecision(boolean accepted, String reason) {}

    static class InvalidRequestException extends RuntimeException {
        InvalidRequestException(String message) {
            super(message);
        }
    }

    static class SessionService {
        private final Map<String, WebSession> sessions =
            new ConcurrentHashMap<>();
        private final SecureRandom secureRandom = new SecureRandom();
        private final Duration lifetime;

        SessionService(Duration lifetime) {
            if (lifetime == null || lifetime.isZero() || lifetime.isNegative()) {
                throw new IllegalArgumentException("Session lifetime must be positive");
            }
            this.lifetime = lifetime;
        }

        private String secureToken(int byteCount) {
            byte[] bytes = new byte[byteCount];
            secureRandom.nextBytes(bytes);
            return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        }

        WebSession issue(String userId) {
            if (userId == null || userId.isBlank()) {
                throw new IllegalArgumentException("User ID is required");
            }

            WebSession session = new WebSession(
                secureToken(32),
                userId,
                secureToken(32),
                Instant.now().plus(lifetime),
                false
            );

            sessions.put(session.sessionId(), session);
            return session;
        }

        WebSession find(String sessionId) {
            return sessions.get(sessionId);
        }

        boolean revoke(String sessionId) {
            WebSession current = sessions.get(sessionId);
            if (current == null) return false;

            sessions.replace(
                sessionId,
                current,
                new WebSession(
                    current.sessionId(),
                    current.userId(),
                    current.csrfToken(),
                    current.expiresAt(),
                    true
                )
            );
            return true;
        }
    }

    static class CsrfPolicy {
        private static final Set<String> STATE_CHANGING_METHODS =
            Set.of("POST", "PUT", "PATCH", "DELETE");

        private final String applicationOrigin;
        private final SessionService sessions;

        CsrfPolicy(String applicationOrigin, SessionService sessions) {
            this.applicationOrigin = validateCanonicalOrigin(applicationOrigin);
            this.sessions = sessions;
        }

        private static String validateCanonicalOrigin(String origin) {
            try {
                URI uri = URI.create(origin);
                if (!"https".equals(uri.getScheme())
                    || uri.getHost() == null
                    || uri.getRawUserInfo() != null
                    || (uri.getRawPath() != null && !uri.getRawPath().isEmpty())
                    || uri.getRawQuery() != null
                    || uri.getRawFragment() != null
                    || !uri.toString().equals(origin)) {
                    throw new IllegalArgumentException("Expected a canonical HTTPS origin");
                }
                return origin;
            } catch (IllegalArgumentException exception) {
                throw new IllegalArgumentException(
                    "Invalid application origin", exception
                );
            }
        }

        SecurityDecision evaluate(MutationRequest request) {
            String method = request.method().toUpperCase();

            if (!STATE_CHANGING_METHODS.contains(method)) {
                return new SecurityDecision(false, "state-changing method required");
            }

            WebSession session = sessions.find(request.sessionId());
            if (session == null || session.revoked()
                || !session.expiresAt().isAfter(Instant.now())) {
                return new SecurityDecision(false, "missing, expired, or revoked session");
            }

            if (!applicationOrigin.equals(request.origin())) {
                return new SecurityDecision(false, "origin mismatch");
            }

            if (request.csrfToken() == null ||
                !MessageDigest.isEqual(
                    session.csrfToken().getBytes(StandardCharsets.UTF_8),
                    request.csrfToken().getBytes(StandardCharsets.UTF_8)
                )) {
                return new SecurityDecision(false, "CSRF token mismatch");
            }

            return new SecurityDecision(true, "accepted");
        }

        WebSession requireValid(MutationRequest request) {
            SecurityDecision decision = evaluate(request);
            if (!decision.accepted()) {
                throw new InvalidRequestException(
                    "Request rejected: " + decision.reason()
                );
            }
            return sessions.find(request.sessionId());
        }
    }

    static class HtmlOutputEncoder {
        static String encodeText(String input) {
            if (input == null) {
                throw new IllegalArgumentException("HTML input cannot be null");
            }

            StringBuilder output = new StringBuilder(input.length() + 32);
            for (char character : input.toCharArray()) {
                switch (character) {
                    case '&' -> output.append("&amp;");
                    case '<' -> output.append("&lt;");
                    case '>' -> output.append("&gt;");
                    case '"' -> output.append("&quot;");
                    case '\'' -> output.append("&#39;");
                    default -> output.append(character);
                }
            }
            return output.toString();
        }
    }

    static class CommentRepository {
        private final Map<Long, Comment> comments = new ConcurrentHashMap<>();
        private final AtomicLong sequence = new AtomicLong(1);

        Comment save(String userId, String body) {
            long id = sequence.getAndIncrement();
            Comment comment = new Comment(id, userId, body, Instant.now());
            comments.put(id, comment);
            return comment;
        }

        Comment find(long id) {
            return comments.get(id);
        }

        String render(long id) {
            Comment comment = find(id);
            if (comment == null) {
                throw new IllegalArgumentException("Comment not found");
            }

            // Raw text remains in storage; encode at the HTML response boundary.
            return "<article>" +
                HtmlOutputEncoder.encodeText(comment.rawBody()) +
                "</article>";
        }
    }

    static class WebSecurityService {
        private static final int MAX_INPUT_LENGTH = 5000;

        private final SessionService sessions;
        private final CsrfPolicy csrfPolicy;
        private final CommentRepository comments;

        WebSecurityService(
            SessionService sessions,
            CsrfPolicy csrfPolicy,
            CommentRepository comments
        ) {
            this.sessions = sessions;
            this.csrfPolicy = csrfPolicy;
            this.comments = comments;
        }

        String renderSearch(String query) {
            validateInput(query, "Search query");
            return "<p>Search results for: " +
                HtmlOutputEncoder.encodeText(query) +
                "</p>";
        }

        Comment submitComment(MutationRequest request, String body) {
            validateInput(body, "Comment");

            WebSession session = csrfPolicy.requireValid(request);
            return comments.save(session.userId(), body);
        }

        private static void validateInput(String input, String label) {
            if (input == null || input.isBlank()
                || input.length() > MAX_INPUT_LENGTH
                || input.indexOf('\0') >= 0) {
                throw new IllegalArgumentException(
                    label + " is empty, invalid, or too large"
                );
            }
        }

        Map<String, String> responseHeaders() {
            return Map.of(
                "Content-Security-Policy",
                "default-src 'self'; object-src 'none'; base-uri 'self'; " +
                "frame-ancestors 'none'; form-action 'self'",
                "X-Content-Type-Options", "nosniff",
                "Referrer-Policy", "strict-origin-when-cross-origin",
                "Cache-Control", "no-store"
            );
        }
    }

    public static void main(String[] args) {
        try {
            SessionService sessions = new SessionService(Duration.ofMinutes(30));
            CsrfPolicy csrfPolicy = new CsrfPolicy(
                "https://enterprise.example.test",
                sessions
            );
            CommentRepository repository = new CommentRepository();
            WebSecurityService service = new WebSecurityService(
                sessions,
                csrfPolicy,
                repository
            );

            WebSession session = sessions.issue("employee-701");

            CookiePolicy cookie = new CookiePolicy(
                "__Host-session",
                true,
                true,
                SameSite.LAX,
                "/",
                1800
            );

            System.out.println("COOKIE HEADER");
            System.out.println(cookie.toSetCookieHeader(session.sessionId()));

            System.out.println("\nSAMESITE POLICY");
            System.out.println("Cross-site POST: " + cookieWouldBeSent(
                cookie, new BrowserContext(true, false, "POST", true)
            ));
            System.out.println("Cross-site top-level GET: " + cookieWouldBeSent(
                cookie, new BrowserContext(true, true, "GET", true)
            ));

            String untrusted = "<img src=x onerror=\"alert(1)\">";

            System.out.println("\nREFLECTED XSS");
            System.out.println(service.renderSearch(untrusted));

            MutationRequest validRequest = new MutationRequest(
                session.sessionId(),
                session.csrfToken(),
                "https://enterprise.example.test",
                "POST"
            );

            System.out.println("\nSTORED XSS");
            Comment saved = service.submitComment(validRequest, untrusted);
            System.out.println("Raw stored content: " + saved.rawBody());
            System.out.println("Rendered content: " + repository.render(saved.id()));

            System.out.println("\nCSRF POLICY EVALUATION");
            SecurityDecision valid = csrfPolicy.evaluate(validRequest);
            System.out.println("Valid request: " + valid);

            MutationRequest wrongToken = new MutationRequest(
                session.sessionId(),
                "incorrect-token",
                "https://enterprise.example.test",
                "POST"
            );
            System.out.println("Wrong token: " + csrfPolicy.evaluate(wrongToken));

            MutationRequest wrongOrigin = new MutationRequest(
                session.sessionId(),
                session.csrfToken(),
                "https://external.example",
                "POST"
            );
            System.out.println("Wrong origin: " + csrfPolicy.evaluate(wrongOrigin));

            sessions.revoke(session.sessionId());
            System.out.println("Revoked session: " + csrfPolicy.evaluate(validRequest));

            System.out.println("\nSECURITY RESPONSE HEADERS");
            service.responseHeaders().forEach(
                (name, value) -> System.out.println(name + ": " + value)
            );

            try {
                new CookiePolicy(
                    "session", false, true, SameSite.NONE, "/", 1800
                );
                throw new IllegalStateException(
                    "An insecure SameSite=None cookie was accepted"
                );
            } catch (IllegalArgumentException expected) {
                System.out.println("\nInvalid cookie policy rejected: " +
                    expected.getMessage());
            }

        } catch (RuntimeException exception) {
            System.err.println("Application failure: " + exception.getMessage());
            System.exitCode = 1;
        }
    }
}
