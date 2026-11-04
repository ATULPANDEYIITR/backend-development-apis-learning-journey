import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Pattern;

/**
 * Enterprise CORS Governance Service.
 *
 * Java 17 implementation featuring:
 * - Immutable policy configuration
 * - Domain-specific request and decision types
 * - Origin normalization
 * - Credential restrictions
 * - Preflight evaluation and caching
 * - Policy versioning
 * - Thread-safe audit events
 * - Enterprise policy validation
 */
public class CorsEnterprise {

    enum Decision {
        ALLOWED,
        ORIGIN_DENIED,
        METHOD_DENIED,
        HEADER_DENIED,
        CREDENTIALS_DENIED,
        PRIVATE_NETWORK_DENIED,
        INVALID_REQUEST
    }

    enum RequestKind {
        SIMPLE,
        PREFLIGHT,
        ACTUAL
    }

    enum PolicyStatus {
        ACTIVE,
        DISABLED
    }

    record Origin(String scheme, String host, Integer port) {

        private static final Pattern HOST_PATTERN =
            Pattern.compile(
                "^[a-zA-Z0-9.-]+$"
            );

        static Origin parse(String value) {
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException(
                    "Origin cannot be empty."
                );
            }

            if (value.equals("null") ||
                !value.equals(value.trim())) {
                throw new IllegalArgumentException(
                    "Opaque or malformed origin."
                );
            }

            if (value.contains("/") &&
                !value.matches("^https?://[^/]+$")) {
                throw new IllegalArgumentException(
                    "Origin cannot contain a path."
                );
            }

            java.net.URI uri;

            try {
                uri = java.net.URI.create(value);
            } catch (IllegalArgumentException exception) {
                throw new IllegalArgumentException(
                    "Invalid origin URI."
                );
            }

            String scheme = Optional.ofNullable(uri.getScheme())
                .orElse("")
                .toLowerCase(Locale.ROOT);

            if (!Set.of("http", "https").contains(scheme)) {
                throw new IllegalArgumentException(
                    "Unsupported origin scheme."
                );
            }

            if (uri.getRawUserInfo() != null ||
                uri.getRawQuery() != null ||
                uri.getRawFragment() != null ||
                uri.getRawPath() != null &&
                !uri.getRawPath().isEmpty()) {
                throw new IllegalArgumentException(
                    "Invalid origin components."
                );
            }

            String host = uri.getHost();

            if (host == null || host.isBlank()) {
                throw new IllegalArgumentException(
                    "Missing hostname."
                );
            }

            host = host.toLowerCase(Locale.ROOT);

            int port = uri.getPort();

            if (port == 0 || port > 65535 || port < -1) {
                throw new IllegalArgumentException(
                    "Invalid port."
                );
            }

            if ((scheme.equals("http") && port == 80) ||
                (scheme.equals("https") && port == 443)) {
                port = -1;
            }

            return new Origin(
                scheme,
                host,
                port == -1 ? null : port
            );
        }

        @Override
        public String toString() {
            String authority = host;

            if (port != null) {
                authority += ":" + port;
            }

            return scheme + "://" + authority;
        }
    }

    record CorsRequest(
        String origin,
        String method,
        Set<String> requestedHeaders,
        String requestedMethod,
        boolean credentials,
        boolean privateNetwork
    ) {
        CorsRequest {
            if (method == null || method.isBlank()) {
                throw new IllegalArgumentException(
                    "HTTP method is required."
                );
            }

            method = method.toUpperCase(Locale.ROOT);

            requestedHeaders = requestedHeaders == null
                ? Set.of()
                : requestedHeaders.stream()
                    .map(h -> h.toLowerCase(Locale.ROOT))
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());

            requestedMethod = requestedMethod == null
                ? null
                : requestedMethod.toUpperCase(Locale.ROOT);
        }

        RequestKind kind() {
            if (method.equals("OPTIONS") && requestedMethod != null) {
                return RequestKind.PREFLIGHT;
            }

            if (Set.of("GET", "HEAD", "POST").contains(method)) {
                return RequestKind.SIMPLE;
            }

            return RequestKind.ACTUAL;
        }
    }

    record CorsResponse(
        int status,
        Decision decision,
        Map<String, String> headers,
        String message
    ) {
        CorsResponse {
            headers = Collections.unmodifiableMap(
                new HashMap<>(headers)
            );
        }

        boolean allowed() {
            return decision == Decision.ALLOWED;
        }
    }

    record AuditEvent(
        UUID eventId,
        Instant timestamp,
        String origin,
        String method,
        Decision decision,
        String policyId,
        long policyVersion
    ) {}

    record PreflightKey(
        String origin,
        String method,
        Set<String> headers,
        boolean credentials,
        boolean privateNetwork,
        long policyVersion
    ) {}

    record CachedDecision(
        Instant expiresAt,
        Map<String, String> responseHeaders
    ) {}

    static final class CorsPolicy {
        private final String policyId;
        private final long version;
        private final Set<String> allowedOrigins;
        private final Set<String> allowedMethods;
        private final Set<String> allowedHeaders;
        private final Set<String> exposedHeaders;
        private final boolean credentials;
        private final boolean privateNetwork;
        private final int maxAge;
        private final PolicyStatus status;

        CorsPolicy(
            String policyId,
            long version,
            Set<String> origins,
            Set<String> methods,
            Set<String> headers,
            Set<String> exposedHeaders,
            boolean credentials,
            boolean privateNetwork,
            int maxAge,
            PolicyStatus status
        ) {
            if (policyId == null || policyId.isBlank()) {
                throw new IllegalArgumentException(
                    "Policy identifier is required."
                );
            }

            if (version < 1) {
                throw new IllegalArgumentException(
                    "Policy version must be positive."
                );
            }

            if (origins == null || origins.isEmpty()) {
                throw new IllegalArgumentException(
                    "At least one allowed origin is required."
                );
            }

            if (maxAge < 0 || maxAge > 86400) {
                throw new IllegalArgumentException(
                    "Invalid max-age."
                );
            }

            Set<String> normalizedOrigins = new HashSet<>();

            for (String origin : origins) {
                normalizedOrigins.add(
                    origin.equals("*")
                        ? "*"
                        : Origin.parse(origin).toString()
                );
            }

            if (normalizedOrigins.contains("*") && credentials) {
                throw new IllegalArgumentException(
                    "Wildcard origins cannot allow credentials."
                );
            }

            this.policyId = policyId;
            this.version = version;
            this.allowedOrigins = Set.copyOf(normalizedOrigins);

            this.allowedMethods = methods.stream()
                .map(m -> m.toUpperCase(Locale.ROOT))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());

            this.allowedHeaders = headers.stream()
                .map(h -> h.toLowerCase(Locale.ROOT))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());

            this.exposedHeaders = Set.copyOf(exposedHeaders);
            this.credentials = credentials;
            this.privateNetwork = privateNetwork;
            this.maxAge = maxAge;
            this.status = status;
        }
    }

    static final class CorsService {
        private final CorsPolicy policy;

        private final ConcurrentMap<
            PreflightKey,
            CachedDecision
        > cache = new ConcurrentHashMap<>();

        private final List<AuditEvent> audit =
            Collections.synchronizedList(new ArrayList<>());

        private final AtomicLong accepted =
            new AtomicLong();

        private final AtomicLong rejected =
            new AtomicLong();

        CorsService(CorsPolicy policy) {
            this.policy = policy;
        }

        private void record(
            CorsRequest request,
            Decision decision
        ) {
            audit.add(new AuditEvent(
                UUID.randomUUID(),
                Instant.now(),
                request.origin(),
                request.method(),
                decision,
                policy.policyId,
                policy.version
            ));

            if (decision == Decision.ALLOWED) {
                accepted.incrementAndGet();
            } else {
                rejected.incrementAndGet();
            }
        }

        private CorsResponse reject(
            CorsRequest request,
            int status,
            Decision decision,
            String message
        ) {
            record(request, decision);

            return new CorsResponse(
                status,
                decision,
                Map.of(),
                message
            );
        }

        private Map<String, String> responseHeaders(
            String origin
        ) {
            Map<String, String> headers = new HashMap<>();

            headers.put(
                "Access-Control-Allow-Origin",
                origin
            );

            if (policy.credentials) {
                headers.put(
                    "Access-Control-Allow-Credentials",
                    "true"
                );
            }

            if (!origin.equals("*")) {
                headers.put("Vary", "Origin");
            }

            if (!policy.exposedHeaders.isEmpty()) {
                headers.put(
                    "Access-Control-Expose-Headers",
                    String.join(", ", policy.exposedHeaders)
                );
            }

            return headers;
        }

        CorsResponse evaluate(CorsRequest request) {
            if (policy.status != PolicyStatus.ACTIVE) {
                return reject(
                    request,
                    403,
                    Decision.INVALID_REQUEST,
                    "CORS policy is disabled."
                );
            }

            if (request.origin() == null ||
                request.origin().isBlank()) {
                record(request, Decision.ALLOWED);

                return new CorsResponse(
                    200,
                    Decision.ALLOWED,
                    Map.of(),
                    "No CORS processing required."
                );
            }

            String normalized;

            try {
                normalized = Origin.parse(request.origin()).toString();
            } catch (IllegalArgumentException exception) {
                return reject(
                    request,
                    403,
                    Decision.INVALID_REQUEST,
                    exception.getMessage()
                );
            }

            String resolvedOrigin;

            if (policy.allowedOrigins.contains("*") &&
                !policy.credentials) {
                resolvedOrigin = "*";
            } else if (policy.allowedOrigins.contains(normalized)) {
                resolvedOrigin = normalized;
            } else {
                return reject(
                    request,
                    403,
                    Decision.ORIGIN_DENIED,
                    "Origin is not allowed."
                );
            }

            if (request.credentials() && !policy.credentials) {
                return reject(
                    request,
                    403,
                    Decision.CREDENTIALS_DENIED,
                    "Credentials are not allowed."
                );
            }

            Map<String, String> headers =
                responseHeaders(resolvedOrigin);

            if (request.kind() == RequestKind.PREFLIGHT) {
                return evaluatePreflight(
                    request,
                    resolvedOrigin,
                    headers
                );
            }

            if (!policy.allowedMethods.contains(request.method())) {
                return reject(
                    request,
                    405,
                    Decision.METHOD_DENIED,
                    "HTTP method is not allowed."
                );
            }

            record(request, Decision.ALLOWED);

            return new CorsResponse(
                200,
                Decision.ALLOWED,
                headers,
                "Request accepted."
            );
        }

        private CorsResponse evaluatePreflight(
            CorsRequest request,
            String origin,
            Map<String, String> headers
        ) {
            String requestedMethod = request.requestedMethod();

            if (requestedMethod == null ||
                !requestedMethod.matches("[A-Z]+")) {
                return reject(
                    request,
                    400,
                    Decision.INVALID_REQUEST,
                    "Invalid requested method."
                );
            }

            if (!policy.allowedMethods.contains(requestedMethod)) {
                return reject(
                    request,
                    403,
                    Decision.METHOD_DENIED,
                    "Requested method is not allowed."
                );
            }

            if (!policy.allowedHeaders.containsAll(
                request.requestedHeaders()
            )) {
                return reject(
                    request,
                    403,
                    Decision.HEADER_DENIED,
                    "Requested headers are not allowed."
                );
            }

            if (request.privateNetwork() &&
                !policy.privateNetwork) {
                return reject(
                    request,
                    403,
                    Decision.PRIVATE_NETWORK_DENIED,
                    "Private network access is not allowed."
                );
            }

            PreflightKey key = new PreflightKey(
                origin,
                requestedMethod,
                request.requestedHeaders(),
                request.credentials(),
                request.privateNetwork(),
                policy.version
            );

            CachedDecision cached = cache.get(key);

            if (cached != null &&
                cached.expiresAt().isAfter(Instant.now())) {
                record(request, Decision.ALLOWED);

                return new CorsResponse(
                    204,
                    Decision.ALLOWED,
                    cached.responseHeaders(),
                    "Cached preflight accepted."
                );
            }

            cache.remove(key);

            headers.put(
                "Access-Control-Allow-Methods",
                String.join(", ", policy.allowedMethods)
            );

            if (!request.requestedHeaders().isEmpty()) {
                headers.put(
                    "Access-Control-Allow-Headers",
                    String.join(", ", request.requestedHeaders())
                );
            }

            headers.put(
                "Access-Control-Max-Age",
                String.valueOf(policy.maxAge)
            );

            if (request.privateNetwork()) {
                headers.put(
                    "Access-Control-Allow-Private-Network",
                    "true"
                );
            }

            if (policy.maxAge > 0) {
                cache.put(
                    key,
                    new CachedDecision(
                        Instant.now().plusSeconds(policy.maxAge),
                        Map.copyOf(headers)
                    )
                );
            }

            record(request, Decision.ALLOWED);

            return new CorsResponse(
                204,
                Decision.ALLOWED,
                headers,
                "Preflight accepted."
            );
        }

        List<AuditEvent> getAudit() {
            synchronized (audit) {
                return List.copyOf(audit);
            }
        }

        Map<String, Long> statistics() {
            return Map.of(
                "accepted", accepted.get(),
                "rejected", rejected.get(),
                "total", accepted.get() + rejected.get()
            );
        }
    }

    public static void main(String[] args) {
        CorsPolicy policy = new CorsPolicy(
            "production-web-policy",
            1,
            Set.of(
                "https://app.example.com",
                "https://admin.example.com"
            ),
            Set.of("GET", "POST", "PUT", "DELETE"),
            Set.of("content-type", "authorization", "x-request-id"),
            Set.of("x-request-id"),
            true,
            false,
            600,
            PolicyStatus.ACTIVE
        );

        CorsService service = new CorsService(policy);

        List<CorsRequest> requests = List.of(
            new CorsRequest(
                "https://app.example.com",
                "GET",
                Set.of(),
                null,
                false,
                false
            ),
            new CorsRequest(
                "https://app.example.com",
                "OPTIONS",
                Set.of("authorization", "content-type"),
                "POST",
                true,
                false
            ),
            new CorsRequest(
                "https://attacker.example.net",
                "GET",
                Set.of(),
                null,
                false,
                false
            ),
            new CorsRequest(
                "https://app.example.com",
                "PATCH",
                Set.of(),
                null,
                false,
                false
            ),
            new CorsRequest(
                "https://app.example.com",
                "OPTIONS",
                Set.of("x-unknown-header"),
                "POST",
                false,
                false
            ),
            new CorsRequest(
                "https://admin.example.com",
                "OPTIONS",
                Set.of("authorization"),
                "PUT",
                true,
                false
            )
        );

        for (CorsRequest request : requests) {
            CorsResponse response = service.evaluate(request);

            System.out.println("\nRequest: " + request);
            System.out.println("Status: " + response.status());
            System.out.println("Decision: " + response.decision());
            System.out.println("Message: " + response.message());
            System.out.println("Headers: " + response.headers());
        }

        // Repeated preflight demonstrates cached policy evaluation.
        CorsRequest repeated = requests.get(1);

        CorsResponse cached = service.evaluate(repeated);

        System.out.println("\nRepeated preflight: " + cached.message());

        // The wildcard-plus-credentials combination is invalid.
        try {
            new CorsPolicy(
                "invalid-policy",
                1,
                Set.of("*"),
                Set.of("GET"),
                Set.of(),
                Set.of(),
                true,
                false,
                600,
                PolicyStatus.ACTIVE
            );

            throw new IllegalStateException(
                "Invalid wildcard policy was accepted."
            );
        } catch (IllegalArgumentException expected) {
            System.out.println(
                "\nPolicy validation: " + expected.getMessage()
            );
        }

        System.out.println("\nEnterprise statistics:");
        System.out.println(service.statistics());

        System.out.println("\nAudit events: " + service.getAudit().size());
    }
}
