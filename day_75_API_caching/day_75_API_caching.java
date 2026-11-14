import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Enterprise API Cache Management System.
 *
 * Models HTTP representation caching, freshness, conditional requests,
 * ETag validation, security isolation, cache policies and invalidation.
 */
public class ApiCachingEnterprise {

    enum CacheState {
        HIT,
        MISS,
        REVALIDATED,
        BYPASS,
        EXPIRED
    }

    static class CacheException extends RuntimeException {
        CacheException(String message) {
            super(message);
        }
    }

    static class PolicyValidationException extends CacheException {
        PolicyValidationException(String message) {
            super(message);
        }
    }

    record CachePolicy(
        Integer maxAge,
        Integer sMaxAge,
        boolean noStore,
        boolean noCache,
        boolean isPrivate,
        boolean isPublic,
        boolean mustRevalidate,
        boolean immutable
    ) {
        int lifetime(boolean shared) {
            if (shared && sMaxAge != null) {
                return sMaxAge;
            }

            return maxAge == null ? 0 : maxAge;
        }

        static CachePolicy parse(String header) {
            if (header == null) header = "";

            if (header.length() > 4096) {
                throw new PolicyValidationException(
                    "Cache-Control exceeds maximum size"
                );
            }

            Map<String, String> directives = new HashMap<>();

            for (String item : header.split(",")) {
                String[] parts = item.trim().split("=", 2);

                String key = parts[0].trim().toLowerCase(Locale.ROOT);

                if (!key.matches("[a-z][a-z0-9-]*")) {
                    throw new PolicyValidationException(
                        "Invalid directive: " + key
                    );
                }

                String value = parts.length == 2
                    ? parts[1].trim().replace("\"", "")
                    : "true";

                if (directives.putIfAbsent(key, value) != null) {
                    throw new PolicyValidationException(
                        "Duplicate directive: " + key
                    );
                }
            }

            return new CachePolicy(
                parseInteger(directives, "max-age"),
                parseInteger(directives, "s-maxage"),
                directives.containsKey("no-store"),
                directives.containsKey("no-cache"),
                directives.containsKey("private"),
                directives.containsKey("public"),
                directives.containsKey("must-revalidate"),
                directives.containsKey("immutable")
            );
        }

        private static Integer parseInteger(
            Map<String, String> directives,
            String key
        ) {
            if (!directives.containsKey(key)) return null;

            try {
                int value = Integer.parseInt(directives.get(key));

                if (value < 0) {
                    throw new NumberFormatException();
                }

                return value;
            } catch (NumberFormatException exception) {
                throw new PolicyValidationException(
                    "Invalid numeric directive: " + key
                );
            }
        }
    }

    record Resource(
        String path,
        String body,
        long modifiedAt
    ) {
        Resource {
            if (path == null || !path.startsWith("/")) {
                throw new IllegalArgumentException("Invalid path");
            }

            Objects.requireNonNull(body);
        }
    }

    record HttpResponse(
        int status,
        String body,
        Map<String, String> headers
    ) {
        HttpResponse {
            headers = Collections.unmodifiableMap(
                new HashMap<>(headers)
            );
        }
    }

    record CacheKey(
        String resource,
        String principal,
        Map<String, String> varyValues
    ) {
        CacheKey {
            varyValues = Map.copyOf(varyValues);
        }
    }

    record CacheRequest(
        String path,
        String principal,
        boolean authenticated,
        boolean forceRevalidation,
        String requestCacheControl,
        Map<String, String> headers
    ) {
        CacheRequest {
            if (path == null || !path.startsWith("/")) {
                throw new IllegalArgumentException("Invalid path");
            }

            if (principal == null || principal.isBlank()) {
                principal = "anonymous";
            }

            headers = Map.copyOf(headers);
        }
    }

    record CacheResult(
        HttpResponse response,
        CacheState state
    ) {}

    static final class OriginService {
        private final Map<String, Resource> resources =
            new ConcurrentHashMap<>();

        private final AtomicInteger requestCount =
            new AtomicInteger();

        void publish(String path, String body) {
            resources.put(
                path,
                new Resource(path, body, Instant.now().getEpochSecond())
            );
        }

        CompletableFuture<HttpResponse> fetch(
            String path,
            Map<String, String> requestHeaders
        ) {
            return CompletableFuture.supplyAsync(() -> {
                requestCount.incrementAndGet();

                Resource resource = resources.get(path);

                if (resource == null) {
                    return new HttpResponse(
                        404,
                        "{\"error\":\"Not found\"}",
                        Map.of()
                    );
                }

                String etag = createETag(resource.body());

                Map<String, String> headers = Map.of(
                    "ETag", etag,
                    "Last-Modified", Long.toString(resource.modifiedAt()),
                    "Cache-Control", "public, max-age=30, s-maxage=60, must-revalidate",
                    "Content-Type", "application/json"
                );

                String inm = findHeader(
                    requestHeaders,
                    "if-none-match"
                );

                if (inm != null && etagMatches(inm, etag)) {
                    return new HttpResponse(304, null, headers);
                }

                return new HttpResponse(
                    200,
                    resource.body(),
                    headers
                );
            });
        }

        int requests() {
            return requestCount.get();
        }
    }

    static final class CacheEntry {
        final HttpResponse response;
        final String etag;
        final CachePolicy policy;
        final long storedAt;
        final long initialAge;

        CacheEntry(
            HttpResponse response,
            CachePolicy policy
        ) {
            this.response = response;
            this.policy = policy;
            this.etag = response.headers().get("ETag");
            this.storedAt = System.nanoTime();
            this.initialAge = 0;
        }

        long age() {
            return initialAge +
                (System.nanoTime() - storedAt) / 1_000_000_000L;
        }

        boolean fresh(boolean shared) {
            return age() < policy.lifetime(shared)
                && !policy.noCache();
        }
    }

    interface CachePolicyEvaluator {
        boolean mayStore(
            CacheRequest request,
            HttpResponse response,
            CachePolicy policy
        );
    }

    static final class EnterprisePolicy
        implements CachePolicyEvaluator {

        @Override
        public boolean mayStore(
            CacheRequest request,
            HttpResponse response,
            CachePolicy policy
        ) {
            if (response.status() != 200) return false;

            if (policy.noStore()) return false;

            if (!request.authenticated()) return false;

            if (policy.isPrivate()) return false;

            return true;
        }
    }

    static final class CacheService {
        private final OriginService origin;
        private final CachePolicyEvaluator evaluator;
        private final boolean shared;

        private final LinkedHashMap<CacheKey, CacheEntry> entries =
            new LinkedHashMap<>(32, 0.75f, true);

        private final ConcurrentHashMap<
            String,
            CompletableFuture<CacheResult>
        > inFlight = new ConcurrentHashMap<>();

        private final int capacity;

        CacheService(
            OriginService origin,
            CachePolicyEvaluator evaluator,
            int capacity,
            boolean shared
        ) {
            this.origin = Objects.requireNonNull(origin);
            this.evaluator = Objects.requireNonNull(evaluator);

            if (capacity < 1) {
                throw new IllegalArgumentException(
                    "Capacity must be positive"
                );
            }

            this.capacity = capacity;
            this.shared = shared;
        }

        private CacheKey key(CacheRequest request) {
            String principal = shared
                ? "shared"
                : request.principal();

            return new CacheKey(
                request.path(),
                principal,
                Map.of()
            );
        }

        private synchronized CacheEntry lookup(CacheKey key) {
            return entries.get(key);
        }

        private synchronized void store(
            CacheKey key,
            CacheEntry entry
        ) {
            entries.put(key, entry);

            while (entries.size() > capacity) {
                CacheKey oldest = entries.keySet()
                    .iterator()
                    .next();

                entries.remove(oldest);
            }
        }

        private synchronized void remove(CacheKey key) {
            entries.remove(key);
        }

        CompletableFuture<CacheResult> request(
            CacheRequest request
        ) {
            if (!request.authenticated()) {
                return origin.fetch(
                    request.path(),
                    request.headers()
                ).thenApply(response ->
                    new CacheResult(response, CacheState.BYPASS)
                );
            }

            if ("no-store".equalsIgnoreCase(
                request.requestCacheControl()
            )) {
                return origin.fetch(
                    request.path(),
                    request.headers()
                ).thenApply(response ->
                    new CacheResult(response, CacheState.BYPASS)
                );
            }

            CacheKey key = key(request);

            CacheEntry existing = lookup(key);

            if (existing != null &&
                existing.fresh(shared) &&
                !request.forceRevalidation()) {

                return CompletableFuture.completedFuture(
                    new CacheResult(
                        existing.response,
                        CacheState.HIT
                    )
                );
            }

            // Atomic request registration prevents duplicate origin work.
            return inFlight.computeIfAbsent(
                request.path() + ":" + key.principal(),
                ignored -> load(request, key, existing)
                    .whenComplete((result, error) ->
                        inFlight.remove(
                            request.path() + ":" + key.principal()
                        )
                    )
            );
        }

        private CompletableFuture<CacheResult> load(
            CacheRequest request,
            CacheKey key,
            CacheEntry previous
        ) {
            Map<String, String> conditional =
                new HashMap<>(request.headers());

            if (previous != null && previous.etag != null) {
                conditional.put(
                    "If-None-Match",
                    previous.etag
                );
            }

            return origin.fetch(
                request.path(),
                conditional
            ).thenApply(response -> {
                if (response.status() == 304 && previous != null) {
                    Map<String, String> merged =
                        new HashMap<>(previous.response.headers());

                    merged.putAll(response.headers());

                    HttpResponse refreshed = new HttpResponse(
                        200,
                        previous.response.body(),
                        merged
                    );

                    CachePolicy policy = CachePolicy.parse(
                        merged.get("Cache-Control")
                    );

                    CacheEntry updated = new CacheEntry(
                        refreshed,
                        policy
                    );

                    if (evaluator.mayStore(
                        request,
                        refreshed,
                        policy
                    )) {
                        store(key, updated);
                    } else {
                        remove(key);
                    }

                    return new CacheResult(
                        refreshed,
                        CacheState.REVALIDATED
                    );
                }

                if (response.status() == 200) {
                    CachePolicy policy = CachePolicy.parse(
                        response.headers().get("Cache-Control")
                    );

                    if (evaluator.mayStore(
                        request,
                        response,
                        policy
                    )) {
                        store(key, new CacheEntry(response, policy));
                    }
                }

                return new CacheResult(
                    response,
                    CacheState.MISS
                );
            });
        }

        synchronized int invalidate(String path) {
            int previousSize = entries.size();

            entries.keySet().removeIf(
                key -> key.resource().equals(path)
            );

            return previousSize - entries.size();
        }

        synchronized int size() {
            return entries.size();
        }
    }

    static String createETag(String body) {
        try {
            MessageDigest digest =
                MessageDigest.getInstance("SHA-256");

            byte[] hash = digest.digest(
                body.getBytes(StandardCharsets.UTF_8)
            );

            StringBuilder result = new StringBuilder("\"");

            for (byte value : hash) {
                result.append(
                    String.format("%02x", value & 0xff)
                );
            }

            return result.append("\"").toString();

        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }

    static boolean etagMatches(String supplied, String current) {
        if (supplied == null) return false;

        if (supplied.trim().equals("*")) return true;

        String target = current.replaceFirst("^W/", "");

        for (String candidate : supplied.split(",")) {
            if (candidate.trim().replaceFirst("^W/", "")
                .equals(target)) {
                return true;
            }
        }

        return false;
    }

    static String findHeader(
        Map<String, String> headers,
        String name
    ) {
        return headers.entrySet()
            .stream()
            .filter(entry ->
                entry.getKey().equalsIgnoreCase(name)
            )
            .map(Map.Entry::getValue)
            .findFirst()
            .orElse(null);
    }

    public static void main(String[] args) {
        OriginService origin = new OriginService();

        origin.publish(
            "/api/employees/2001",
            "{\"id\":2001,\"department\":\"Engineering\",\"active\":true}"
        );

        CacheService cache = new CacheService(
            origin,
            new EnterprisePolicy(),
            100,
            true
        );

        CacheRequest request = new CacheRequest(
            "/api/employees/2001",
            "employee-service",
            true,
            false,
            "",
            Map.of("Accept", "application/json")
        );

        System.out.println("ENTERPRISE API CACHE SYSTEM");
        System.out.println("============================");

        try {
            CacheResult first = cache.request(request).join();

            System.out.println(
                "First request: " + first.state()
            );

            CacheResult second = cache.request(request).join();

            System.out.println(
                "Second request: " + second.state()
            );

            CacheRequest forced = new CacheRequest(
                request.path(),
                request.principal(),
                true,
                true,
                "",
                request.headers()
            );

            CacheResult third = cache.request(forced).join();

            System.out.println(
                "Conditional request: " + third.state()
            );

            System.out.println(
                "Origin request count: " + origin.requests()
            );

            System.out.println(
                "Cache entries: " + cache.size()
            );

            System.out.println(
                "Invalidated entries: " +
                cache.invalidate("/api/employees/2001")
            );

            System.out.println(
                "Entries after invalidation: " + cache.size()
            );

            System.out.println("\nCache-Control evaluation");

            CachePolicy policy = CachePolicy.parse(
                "public, max-age=60, s-maxage=120, must-revalidate"
            );

            System.out.println(
                "Shared lifetime: " + policy.lifetime(true)
            );

            System.out.println("\nETag validation");

            String tag = createETag("{\"version\":1}");

            System.out.println(
                "ETag: " + tag +
                " | Match: " + etagMatches("W/" + tag, tag)
            );

            try {
                CachePolicy.parse("max-age=-5");
            } catch (PolicyValidationException exception) {
                System.out.println(
                    "Rejected policy: " + exception.getMessage()
                );
            }

        } catch (CompletionException exception) {
            System.err.println(
                "Request failure: " + exception.getCause()
            );
        }
    }
}
