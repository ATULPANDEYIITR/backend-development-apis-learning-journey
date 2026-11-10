/*
 * API PAGINATION ENTERPRISE GOVERNANCE SYSTEM
 *
 * Offset Pagination, Cursor Pagination, and Keyset Pagination.
 *
 * Java 17
 * Standard library only.
 *
 * Features:
 * - Enterprise repository and service architecture.
 * - Immutable domain records.
 * - Explicit pagination policies.
 * - Signed cursor tokens.
 * - Repository version checks.
 * - Deterministic composite sorting.
 * - Forward and backward keyset navigation.
 * - Structured error handling.
 * - Snapshot consistency validation.
 * - Metrics and execution reporting.
 */

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.GeneralSecurityException;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.time.Instant;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

// ============================================================
// 1. MAIN APPLICATION
// ============================================================

public class Main {

    public static void main(String[] args) {

        try {
            ProductRepository repository =
                SampleData.createRepository();

            byte[] secret = (
                "enterprise-pagination-secret-2026-" +
                "secure-key-material"
            ).getBytes(StandardCharsets.UTF_8);

            CursorService cursorService =
                new CursorService(secret);

            PaginationPolicy policy =
                new PaginationPolicy(10, 50);

            PaginationService service =
                new PaginationService(
                    repository,
                    cursorService,
                    policy
                );

            PaginationTests.run(service);

            System.out.println("\nOFFSET PAGINATION");

            PageResult<Product> offset =
                service.offset(
                    new OffsetRequest(2, 5, null)
                );

            printResult(offset);

            System.out.println("\nCURSOR PAGINATION");

            PageResult<Product> cursor =
                service.cursor(
                    new CursorRequest(5, null, null)
                );

            printResult(cursor);

            if (cursor.nextCursor() != null) {
                PageResult<Product> next =
                    service.cursor(
                        new CursorRequest(
                            5,
                            cursor.nextCursor(),
                            null
                        )
                    );

                System.out.println("\nNext cursor page");
                printResult(next);
            }

            System.out.println("\nKEYSET PAGINATION");

            PageResult<Product> keyset =
                service.keyset(
                    new KeysetRequest(
                        5,
                        null,
                        null,
                        null,
                        SortDirection.ASC
                    )
                );

            printResult(keyset);

            if (!keyset.items().isEmpty()) {
                Product last =
                    keyset.items().get(
                        keyset.items().size() - 1
                    );

                PageResult<Product> next =
                    service.keyset(
                        new KeysetRequest(
                            5,
                            last.createdAt(),
                            last.id(),
                            null,
                            SortDirection.ASC
                        )
                    );

                System.out.println("\nNext keyset page");
                printResult(next);
            }

        } catch (PaginationException exception) {
            System.err.println(
                "Pagination error: " + exception.getMessage()
            );
            System.exit(1);
        }
    }

    private static void printResult(
        PageResult<Product> result
    ) {
        System.out.println("Strategy: " + result.strategy());
        System.out.println("Records: " + result.items().size());
        System.out.println("Total: " + result.totalItems());
        System.out.println("Has next: " + result.hasNext());
        System.out.println("Has previous: " + result.hasPrevious());
        System.out.println(
            "Execution: " + result.executionMs() + " ms"
        );

        result.items().forEach(product ->
            System.out.println(
                product.id() + " | " +
                product.name() + " | " +
                product.category() + " | " +
                product.createdAt()
            )
        );

        if (result.nextCursor() != null) {
            System.out.println(
                "Next cursor: " + result.nextCursor()
            );
        }
    }
}

// ============================================================
// 2. ENUMS
// ============================================================

enum PaginationStrategy {
    OFFSET,
    CURSOR,
    KEYSET
}

enum SortDirection {
    ASC,
    DESC
}

enum ProductStatus {
    ACTIVE,
    INACTIVE
}

// ============================================================
// 3. DOMAIN RECORDS
// ============================================================

record Product(
    long id,
    String name,
    String category,
    double price,
    Instant createdAt,
    ProductStatus status
) {
    Product {
        if (id <= 0) {
            throw new PaginationException("Invalid product ID.");
        }

        if (name == null || name.isBlank()) {
            throw new PaginationException("Product name is required.");
        }

        if (
            category == null ||
            category.isBlank()
        ) {
            throw new PaginationException("Category is required.");
        }

        if (!Double.isFinite(price) || price < 0) {
            throw new PaginationException("Invalid price.");
        }

        Objects.requireNonNull(createdAt);
        Objects.requireNonNull(status);
    }
}

record OffsetRequest(
    int page,
    int pageSize,
    String category
) {}

record CursorRequest(
    int pageSize,
    String cursor,
    String category
) {}

record KeysetRequest(
    int pageSize,
    Instant lastCreatedAt,
    Long lastId,
    String category,
    SortDirection direction
) {}

record CursorPosition(
    Instant createdAt,
    long id
) {}

record CursorPayload(
    CursorPosition position,
    long repositoryVersion,
    Instant expiresAt,
    String filterFingerprint,
    PaginationStrategy strategy
) {}

record PageResult<T>(
    List<T> items,
    PaginationStrategy strategy,
    int pageSize,
    Long totalItems,
    boolean hasNext,
    boolean hasPrevious,
    String nextCursor,
    long executionMs
) {
    PageResult {
        items = List.copyOf(items);
    }
}

// ============================================================
// 4. EXCEPTIONS
// ============================================================

class PaginationException extends RuntimeException {

    PaginationException(String message) {
        super(message);
    }

    PaginationException(String message, Throwable cause) {
        super(message, cause);
    }
}

class InvalidCursorException extends PaginationException {

    InvalidCursorException(String message) {
        super(message);
    }
}

class StaleCursorException extends PaginationException {

    StaleCursorException(String message) {
        super(message);
    }
}

// ============================================================
// 5. REPOSITORY INTERFACE
// ============================================================

interface Repository<T> {

    List<T> findAll();

    long version();

    void insert(T entity);

    void delete(long id);
}

// ============================================================
// 6. PRODUCT REPOSITORY
// ============================================================

final class ProductRepository
    implements Repository<Product> {

    private final Map<Long, Product> products =
        new ConcurrentHashMap<>();

    private final AtomicLong version =
        new AtomicLong(1);

    @Override
    public synchronized void insert(Product product) {

        Objects.requireNonNull(product);

        if (products.putIfAbsent(product.id(), product) != null) {
            throw new PaginationException(
                "Duplicate product ID."
            );
        }

        version.incrementAndGet();
    }

    public synchronized void update(Product product) {

        if (!products.containsKey(product.id())) {
            throw new PaginationException(
                "Product not found."
            );
        }

        products.put(product.id(), product);
        version.incrementAndGet();
    }

    @Override
    public synchronized void delete(long id) {

        if (products.remove(id) != null) {
            version.incrementAndGet();
        }
    }

    @Override
    public synchronized List<Product> findAll() {
        return List.copyOf(products.values());
    }

    @Override
    public long version() {
        return version.get();
    }
}

// ============================================================
// 7. PAGINATION POLICY
// ============================================================

final class PaginationPolicy {

    private final int defaultPageSize;
    private final int maximumPageSize;

    PaginationPolicy(
        int defaultPageSize,
        int maximumPageSize
    ) {
        if (
            defaultPageSize < 1 ||
            maximumPageSize < defaultPageSize ||
            maximumPageSize > 100
        ) {
            throw new PaginationException(
                "Invalid pagination policy."
            );
        }

        this.defaultPageSize = defaultPageSize;
        this.maximumPageSize = maximumPageSize;
    }

    int resolvePageSize(int requested) {

        int size = requested == 0
            ? defaultPageSize
            : requested;

        if (size < 1 || size > maximumPageSize) {
            throw new PaginationException(
                "Page size violates repository policy."
            );
        }

        return size;
    }
}

// ============================================================
// 8. CURSOR SERVICE
// ============================================================

final class CursorService {

    private static final Duration CURSOR_TTL =
        Duration.ofMinutes(30);

    private final byte[] secret;

    CursorService(byte[] secret) {
        if (secret == null || secret.length < 32) {
            throw new PaginationException(
                "Cursor secret must contain at least 32 bytes."
            );
        }

        this.secret = secret.clone();
    }

    private byte[] sign(String payload) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");

            mac.init(
                new SecretKeySpec(secret, "HmacSHA256")
            );

            return mac.doFinal(
                payload.getBytes(StandardCharsets.UTF_8)
            );

        } catch (GeneralSecurityException exception) {
            throw new PaginationException(
                "Cursor signing failed.",
                exception
            );
        }
    }

    String encode(CursorPayload payload) {

        String body = String.join(
            "|",
            payload.position().createdAt().toString(),
            Long.toString(payload.position().id()),
            Long.toString(payload.repositoryVersion()),
            Long.toString(payload.expiresAt().getEpochSecond()),
            payload.filterFingerprint(),
            payload.strategy().name()
        );

        String encodedBody = Base64.getUrlEncoder()
            .withoutPadding()
            .encodeToString(
                body.getBytes(StandardCharsets.UTF_8)
            );

        String signature = Base64.getUrlEncoder()
            .withoutPadding()
            .encodeToString(sign(encodedBody));

        return encodedBody + "." + signature;
    }

    CursorPayload decode(String token) {

        if (token == null || token.length() > 4096) {
            throw new InvalidCursorException(
                "Invalid cursor size."
            );
        }

        String[] parts = token.split("\\.", -1);

        if (parts.length != 2) {
            throw new InvalidCursorException(
                "Malformed cursor."
            );
        }

        byte[] expected = sign(parts[0]);

        byte[] actual;

        try {
            actual = Base64.getUrlDecoder().decode(parts[1]);
        } catch (IllegalArgumentException exception) {
            throw new InvalidCursorException(
                "Malformed cursor signature."
            );
        }

        if (!MessageDigest.isEqual(expected, actual)) {
            throw new InvalidCursorException(
                "Cursor authentication failed."
            );
        }

        try {
            String body = new String(
                Base64.getUrlDecoder().decode(parts[0]),
                StandardCharsets.UTF_8
            );

            String[] fields = body.split("\\|", -1);

            if (fields.length != 6) {
                throw new InvalidCursorException(
                    "Invalid cursor fields."
                );
            }

            CursorPayload payload = new CursorPayload(
                new CursorPosition(
                    Instant.parse(fields[0]),
                    Long.parseLong(fields[1])
                ),
                Long.parseLong(fields[2]),
                Instant.ofEpochSecond(
                    Long.parseLong(fields[3])
                ),
                fields[4],
                PaginationStrategy.valueOf(fields[5])
            );

            if (payload.position().id() <= 0) {
                throw new InvalidCursorException(
                    "Invalid cursor position."
                );
            }

            if (payload.expiresAt().isBefore(Instant.now())) {
                throw new InvalidCursorException(
                    "Cursor expired."
                );
            }

            return payload;

        } catch (InvalidCursorException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new InvalidCursorException(
                "Unable to decode cursor."
            );
        }
    }

    static Instant expirationTime() {
        return Instant.now().plus(CURSOR_TTL);
    }
}

// ============================================================
// 9. PAGINATION SERVICE
// ============================================================

final class PaginationService {

    private final ProductRepository repository;
    private final CursorService cursorService;
    private final PaginationPolicy policy;

    private static final Comparator<Product> ASCENDING =
        Comparator.comparing(Product::createdAt)
            .thenComparingLong(Product::id);

    PaginationService(
        ProductRepository repository,
        CursorService cursorService,
        PaginationPolicy policy
    ) {
        this.repository = repository;
        this.cursorService = cursorService;
        this.policy = policy;
    }

    private List<Product> filtered(
        String category
    ) {
        return repository.findAll()
            .stream()
            .filter(p ->
                p.status() == ProductStatus.ACTIVE
            )
            .filter(p ->
                category == null ||
                p.category().equalsIgnoreCase(category)
            )
            .sorted(ASCENDING)
            .collect(Collectors.toCollection(ArrayList::new));
    }

    private String fingerprint(String category) {
        try {
            String normalized = category == null
                ? ""
                : category.trim().toLowerCase(Locale.ROOT);

            byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(
                    normalized.getBytes(StandardCharsets.UTF_8)
                );

            return Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(digest);

        } catch (GeneralSecurityException exception) {
            throw new PaginationException(
                "Filter fingerprint generation failed.",
                exception
            );
        }
    }

    // --------------------------------------------------------
    // OFFSET PAGINATION
    // --------------------------------------------------------

    PageResult<Product> offset(OffsetRequest request) {

        long started = System.nanoTime();

        Objects.requireNonNull(request);

        int pageSize = policy.resolvePageSize(
            request.pageSize()
        );

        if (request.page() < 1) {
            throw new PaginationException(
                "Page must be positive."
            );
        }

        long offset = (long) (request.page() - 1) * pageSize;

        if (offset > Integer.MAX_VALUE) {
            throw new PaginationException(
                "Offset exceeds supported in-memory range."
            );
        }

        List<Product> products = filtered(
            request.category()
        );

        int begin = Math.min(
            (int) offset,
            products.size()
        );

        int end = Math.min(
            begin + pageSize,
            products.size()
        );

        List<Product> items = products.subList(begin, end);

        boolean hasNext = end < products.size();

        return new PageResult<>(
            items,
            PaginationStrategy.OFFSET,
            pageSize,
            (long) products.size(),
            hasNext,
            request.page() > 1 && begin > 0,
            null,
            elapsed(started)
        );
    }

    // --------------------------------------------------------
    // CURSOR PAGINATION
    // --------------------------------------------------------

    PageResult<Product> cursor(CursorRequest request) {

        long started = System.nanoTime();

        Objects.requireNonNull(request);

        int pageSize = policy.resolvePageSize(
            request.pageSize()
        );

        List<Product> products = filtered(
            request.category()
        );

        String filter = fingerprint(request.category());

        long currentVersion = repository.version();

        CursorPosition boundary = null;

        if (request.cursor() != null) {

            CursorPayload payload = cursorService.decode(
                request.cursor()
            );

            if (payload.strategy() != PaginationStrategy.CURSOR) {
                throw new InvalidCursorException(
                    "Cursor strategy mismatch."
                );
            }

            if (!payload.filterFingerprint().equals(filter)) {
                throw new InvalidCursorException(
                    "Cursor filter mismatch."
                );
            }

            if (payload.repositoryVersion() != currentVersion) {
                throw new StaleCursorException(
                    "Dataset changed. Restart pagination."
                );
            }

            boundary = payload.position();
        }

        final CursorPosition finalBoundary = boundary;

        List<Product> remaining = products.stream()
            .filter(product ->
                finalBoundary == null ||
                ASCENDING.compare(
                    product,
                    new Product(
                        finalBoundary.id(),
                        "Boundary",
                        "Boundary",
                        0,
                        finalBoundary.createdAt(),
                        ProductStatus.ACTIVE
                    )
                ) > 0
            )
            .collect(Collectors.toCollection(ArrayList::new));

        boolean hasNext = remaining.size() > pageSize;

        List<Product> items = new ArrayList<>(
            remaining.subList(
                0,
                Math.min(pageSize, remaining.size())
            )
        );

        String nextCursor = null;

        if (hasNext && !items.isEmpty()) {
            Product last = items.get(items.size() - 1);

            nextCursor = cursorService.encode(
                new CursorPayload(
                    new CursorPosition(
                        last.createdAt(),
                        last.id()
                    ),
                    currentVersion,
                    CursorService.expirationTime(),
                    filter,
                    PaginationStrategy.CURSOR
                )
            );
        }

        return new PageResult<>(
            items,
            PaginationStrategy.CURSOR,
            pageSize,
            null,
            hasNext,
            request.cursor() != null,
            nextCursor,
            elapsed(started)
        );
    }

    // --------------------------------------------------------
    // KEYSET PAGINATION
    // --------------------------------------------------------

    PageResult<Product> keyset(KeysetRequest request) {

        long started = System.nanoTime();

        Objects.requireNonNull(request);
        Objects.requireNonNull(request.direction());

        int pageSize = policy.resolvePageSize(
            request.pageSize()
        );

        boolean hasTimestamp = request.lastCreatedAt() != null;
        boolean hasId = request.lastId() != null;

        if (hasTimestamp != hasId) {
            throw new PaginationException(
                "Both keyset boundary fields are required."
            );
        }

        if (hasId && request.lastId() <= 0) {
            throw new PaginationException(
                "Keyset ID must be positive."
            );
        }

        List<Product> products = filtered(
            request.category()
        );

        if (request.direction() == SortDirection.DESC) {
            Collections.reverse(products);
        }

        List<Product> remaining = products.stream()
            .filter(product -> {
                if (!hasTimestamp) {
                    return true;
                }

                int comparison =
                    ASCENDING.compare(
                        product,
                        new Product(
                            request.lastId(),
                            "Boundary",
                            "Boundary",
                            0,
                            request.lastCreatedAt(),
                            ProductStatus.ACTIVE
                        )
                    );

                return request.direction() == SortDirection.ASC
                    ? comparison > 0
                    : comparison < 0;
            })
            .collect(Collectors.toCollection(ArrayList::new));

        boolean hasNext = remaining.size() > pageSize;

        List<Product> items = new ArrayList<>(
            remaining.subList(
                0,
                Math.min(pageSize, remaining.size())
            )
        );

        return new PageResult<>(
            items,
            PaginationStrategy.KEYSET,
            pageSize,
            null,
            hasNext,
            hasTimestamp,
            null,
            elapsed(started)
        );
    }

    private static long elapsed(long started) {
        return Duration.ofNanos(
            System.nanoTime() - started
        ).toMillis();
    }
}

// ============================================================
// 10. SAMPLE DATA
// ============================================================

final class SampleData {

    private SampleData() {}

    static ProductRepository createRepository() {

        ProductRepository repository =
            new ProductRepository();

        String[] categories = {
            "Electronics",
            "Books",
            "Furniture",
            "Software"
        };

        Instant base = Instant.parse(
            "2026-01-01T00:00:00Z"
        );

        for (long i = 1; i <= 40; i++) {

            Product product = new Product(
                i,
                "Product " + i,
                categories[(int) ((i - 1) % 4)],
                100 + i * 25,
                base.plusSeconds((i / 2) * 60),
                i % 13 == 0
                    ? ProductStatus.INACTIVE
                    : ProductStatus.ACTIVE
            );

            repository.insert(product);
        }

        return repository;
    }
}

// ============================================================
// 11. TESTING
// ============================================================

final class PaginationTests {

    private PaginationTests() {}

    static void run(PaginationService service) {

        PageResult<Product> first =
            service.offset(
                new OffsetRequest(1, 5, null)
            );

        PageResult<Product> second =
            service.offset(
                new OffsetRequest(2, 5, null)
            );

        if (first.items().size() != 5) {
            throw new AssertionError("Offset test failed.");
        }

        if (
            first.items().get(4).id() ==
            second.items().get(0).id()
        ) {
            throw new AssertionError("Offset pages overlap.");
        }

        PageResult<Product> cursorFirst =
            service.cursor(
                new CursorRequest(5, null, null)
            );

        if (cursorFirst.nextCursor() == null) {
            throw new AssertionError("Cursor was not created.");
        }

        PageResult<Product> cursorSecond =
            service.cursor(
                new CursorRequest(
                    5,
                    cursorFirst.nextCursor(),
                    null
                )
            );

        Set<Long> ids = cursorFirst.items()
            .stream()
            .map(Product::id)
            .collect(Collectors.toSet());

        if (
            cursorSecond.items()
                .stream()
                .anyMatch(p -> ids.contains(p.id()))
        ) {
            throw new AssertionError("Cursor pages overlap.");
        }

        PageResult<Product> keysetFirst =
            service.keyset(
                new KeysetRequest(
                    5,
                    null,
                    null,
                    null,
                    SortDirection.ASC
                )
            );

        Product last = keysetFirst.items().get(4);

        PageResult<Product> keysetSecond =
            service.keyset(
                new KeysetRequest(
                    5,
                    last.createdAt(),
                    last.id(),
                    null,
                    SortDirection.ASC
                )
            );

        if (
            keysetSecond.items()
                .stream()
                .anyMatch(p -> ids.contains(p.id()))
        ) {
            throw new AssertionError("Keyset pages overlap.");
        }

        boolean invalidRejected = false;

        try {
            service.offset(
                new OffsetRequest(0, 5, null)
            );
        } catch (PaginationException exception) {
            invalidRejected = true;
        }

        if (!invalidRejected) {
            throw new AssertionError(
                "Invalid page was accepted."
            );
        }

        System.out.println(
            "All Java 17 pagination tests passed."
        );
    }
}
