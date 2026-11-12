import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Supplier;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Enterprise API Response Governance.
 *
 * Java 17, standard library only.
 */
public class Main {

    enum ErrorCode {
        VALIDATION_ERROR,
        RESOURCE_NOT_FOUND,
        CONFLICT,
        UNAUTHORIZED,
        FORBIDDEN,
        RATE_LIMITED,
        INTERNAL_ERROR,
        SERVICE_UNAVAILABLE
    }

    enum ConsistencyLevel {
        STRONG,
        EVENTUAL
    }

    record ErrorDetail(
        String field,
        String reason,
        Object rejectedValue
    ) {
        ErrorDetail {
            Objects.requireNonNull(field);
            Objects.requireNonNull(reason);
        }
    }

    record APIError(
        ErrorCode code,
        String message,
        List<ErrorDetail> details,
        boolean retryable
    ) {
        APIError {
            Objects.requireNonNull(code);
            Objects.requireNonNull(message);
            details = List.copyOf(details);
        }
    }

    record Pagination(
        int page,
        int pageSize,
        long totalItems,
        int totalPages,
        boolean hasNext,
        boolean hasPrevious
    ) {
        Pagination {
            if (page < 1 || pageSize < 1 || totalItems < 0) {
                throw new IllegalArgumentException(
                    "Invalid pagination values"
                );
            }

            if (totalPages < 0) {
                throw new IllegalArgumentException(
                    "Invalid total page count"
                );
            }
        }
    }

    record ResponseMetadata(
        String requestId,
        Instant timestamp,
        String apiVersion,
        long durationMs,
        String correlationId,
        ConsistencyLevel consistency,
        Pagination pagination,
        Map<String, String> links
    ) {
        ResponseMetadata {
            Objects.requireNonNull(requestId);
            Objects.requireNonNull(timestamp);
            Objects.requireNonNull(apiVersion);
            Objects.requireNonNull(consistency);

            links = Collections.unmodifiableMap(
                new LinkedHashMap<>(links)
            );
        }
    }

    record APIResponse<T>(
        boolean success,
        T data,
        APIError error,
        ResponseMetadata metadata
    ) {
        APIResponse {
            Objects.requireNonNull(metadata);

            if (success && error != null) {
                throw new IllegalArgumentException(
                    "Successful response cannot contain an error"
                );
            }

            if (!success && (error == null || data != null)) {
                throw new IllegalArgumentException(
                    "Failed response requires error and null data"
                );
            }
        }
    }

    static final class APIException extends RuntimeException {
        private final ErrorCode code;
        private final int httpStatus;
        private final List<ErrorDetail> details;
        private final boolean retryable;

        APIException(
            ErrorCode code,
            String message,
            int httpStatus,
            List<ErrorDetail> details,
            boolean retryable
        ) {
            super(message);
            this.code = code;
            this.httpStatus = httpStatus;
            this.details = List.copyOf(details);
            this.retryable = retryable;
        }

        ErrorCode code() {
            return code;
        }

        int httpStatus() {
            return httpStatus;
        }

        List<ErrorDetail> details() {
            return details;
        }

        boolean retryable() {
            return retryable;
        }
    }

    record Product(
        long id,
        String name,
        long pricePaise,
        String currency,
        long version
    ) {
        Product {
            if (id <= 0 || version <= 0) {
                throw new IllegalArgumentException(
                    "Invalid product identity or version"
                );
            }

            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Product name is required"
                );
            }

            if (pricePaise <= 0) {
                throw new IllegalArgumentException(
                    "Product price must be positive"
                );
            }

            if (!"INR".equals(currency)) {
                throw new IllegalArgumentException(
                    "Unsupported currency"
                );
            }
        }

        Product withPrice(long newPrice) {
            return new Product(
                id,
                name,
                newPrice,
                currency,
                version + 1
            );
        }
    }

    interface ProductRepository {
        Product findById(long id);

        List<Product> findAll();

        Product updatePrice(
            long id,
            long newPricePaise,
            long expectedVersion
        );
    }

    static final class InMemoryProductRepository
        implements ProductRepository {

        private final Map<Long, Product> products =
            new HashMap<>();

        InMemoryProductRepository() {
            products.put(
                101L,
                new Product(
                    101,
                    "Enterprise Laptop",
                    8_500_000,
                    "INR",
                    1
                )
            );

            products.put(
                102L,
                new Product(
                    102,
                    "Network Firewall",
                    12_500_000,
                    "INR",
                    1
                )
            );

            products.put(
                103L,
                new Product(
                    103,
                    "Secure Storage",
                    4_500_000,
                    "INR",
                    1
                )
            );
        }

        @Override
        public synchronized Product findById(long id) {
            Product product = products.get(id);

            if (product == null) {
                throw new APIException(
                    ErrorCode.RESOURCE_NOT_FOUND,
                    "Product does not exist.",
                    404,
                    List.of(),
                    false
                );
            }

            return product;
        }

        @Override
        public synchronized List<Product> findAll() {
            return products.values()
                .stream()
                .sorted(
                    java.util.Comparator.comparingLong(Product::id)
                )
                .toList();
        }

        @Override
        public synchronized Product updatePrice(
            long id,
            long newPricePaise,
            long expectedVersion
        ) {
            if (newPricePaise <= 0) {
                throw new APIException(
                    ErrorCode.VALIDATION_ERROR,
                    "Price must be positive.",
                    400,
                    List.of(
                        new ErrorDetail(
                            "price",
                            "Must be greater than zero",
                            newPricePaise
                        )
                    ),
                    false
                );
            }

            Product current = findById(id);

            if (current.version() != expectedVersion) {
                throw new APIException(
                    ErrorCode.CONFLICT,
                    "Resource version conflict.",
                    409,
                    List.of(
                        new ErrorDetail(
                            "version",
                            "Expected version does not match current version",
                            expectedVersion
                        )
                    ),
                    false
                );
            }

            Product updated = current.withPrice(newPricePaise);
            products.put(id, updated);
            return updated;
        }
    }

    record ResponsePolicy(
        String apiVersion,
        int maximumPageSize,
        boolean includeRequestId,
        ConsistencyLevel defaultConsistency
    ) {
        ResponsePolicy {
            if (
                apiVersion == null ||
                !Pattern.matches("v[1-9][0-9]*", apiVersion)
            ) {
                throw new IllegalArgumentException(
                    "Invalid API version"
                );
            }

            if (maximumPageSize < 1 || maximumPageSize > 1000) {
                throw new IllegalArgumentException(
                    "Invalid maximum page size"
                );
            }

            Objects.requireNonNull(defaultConsistency);
        }
    }

    static final class ResponseFactory {
        private final ResponsePolicy policy;
        private final AtomicLong requestCounter =
            new AtomicLong();

        ResponseFactory(ResponsePolicy policy) {
            this.policy = policy;
        }

        private ResponseMetadata metadata(
            long started,
            String correlationId,
            ConsistencyLevel consistency,
            Pagination pagination,
            Map<String, String> links
        ) {
            String requestId = policy.includeRequestId()
                ? UUID.randomUUID().toString()
                : "req-" + requestCounter.incrementAndGet();

            return new ResponseMetadata(
                requestId,
                Instant.now(),
                policy.apiVersion(),
                (System.nanoTime() - started) / 1_000_000,
                correlationId,
                consistency,
                pagination,
                links
            );
        }

        <T> APIResponse<T> success(
            T data,
            long started,
            String correlationId,
            ConsistencyLevel consistency,
            Pagination pagination,
            Map<String, String> links
        ) {
            return new APIResponse<>(
                true,
                data,
                null,
                metadata(
                    started,
                    correlationId,
                    consistency,
                    pagination,
                    links
                )
            );
        }

        APIResponse<Void> failure(
            APIException exception,
            long started,
            String correlationId
        ) {
            APIError error = new APIError(
                exception.code(),
                exception.getMessage(),
                exception.details(),
                exception.retryable()
            );

            return new APIResponse<>(
                false,
                null,
                error,
                metadata(
                    started,
                    correlationId,
                    policy.defaultConsistency(),
                    null,
                    Map.of()
                )
            );
        }

        int maximumPageSize() {
            return policy.maximumPageSize();
        }
    }

    record HttpResult<T>(
        int status,
        APIResponse<T> body
    ) {}

    static final class ProductService {
        private final ProductRepository repository;
        private final ResponseFactory responseFactory;

        ProductService(
            ProductRepository repository,
            ResponseFactory responseFactory
        ) {
            this.repository = repository;
            this.responseFactory = responseFactory;
        }

        private <T> HttpResult<T> execute(
            Supplier<T> operation,
            String correlationId
        ) {
            long started = System.nanoTime();

            try {
                T result = operation.get();

                return new HttpResult<>(
                    200,
                    responseFactory.success(
                        result,
                        started,
                        correlationId,
                        ConsistencyLevel.STRONG,
                        null,
                        Map.of()
                    )
                );
            } catch (APIException exception) {
                return new HttpResult<>(
                    exception.httpStatus(),
                    responseFactory.failure(
                        exception,
                        started,
                        correlationId
                    )
                );
            } catch (Exception exception) {
                // Internal messages must not leak through the public API.
                System.err.println(
                    "Internal service failure: " +
                    exception.getClass().getSimpleName()
                );

                APIException safeException = new APIException(
                    ErrorCode.INTERNAL_ERROR,
                    "An unexpected server error occurred.",
                    500,
                    List.of(),
                    false
                );

                return new HttpResult<>(
                    500,
                    responseFactory.failure(
                        safeException,
                        started,
                        correlationId
                    )
                );
            }
        }

        HttpResult<Product> getProduct(long id) {
            return execute(
                () -> repository.findById(id),
                "product-read"
            );
        }

        HttpResult<Map<String, Object>> listProducts(
            int page,
            int pageSize
        ) {
            return execute(
                () -> {
                    if (
                        page < 1 ||
                        pageSize < 1 ||
                        pageSize > responseFactory.maximumPageSize()
                    ) {
                        throw new APIException(
                            ErrorCode.VALIDATION_ERROR,
                            "Invalid pagination parameters.",
                            400,
                            List.of(
                                new ErrorDetail(
                                    "page",
                                    "Page must be positive",
                                    page
                                ),
                                new ErrorDetail(
                                    "pageSize",
                                    "Page size exceeds configured limit",
                                    pageSize
                                )
                            ),
                            false
                        );
                    }

                    List<Product> products = repository.findAll();

                    int offset = Math.multiplyExact(
                        page - 1,
                        pageSize
                    );

                    int from = Math.min(offset, products.size());
                    int to = Math.min(
                        from + pageSize,
                        products.size()
                    );

                    List<Product> items =
                        products.subList(from, to);

                    int totalPages = (int) Math.ceil(
                        (double) products.size() / pageSize
                    );

                    Pagination pagination = new Pagination(
                        page,
                        pageSize,
                        products.size(),
                        totalPages,
                        page < totalPages,
                        page > 1
                    );

                    Map<String, Object> result = new LinkedHashMap<>();
                    result.put("items", items);
                    result.put("pagination", pagination);

                    return result;
                },
                "product-list"
            );
        }

        HttpResult<Product> updatePrice(
            long id,
            long pricePaise,
            long expectedVersion
        ) {
            return execute(
                () -> repository.updatePrice(
                    id,
                    pricePaise,
                    expectedVersion
                ),
                "product-update"
            );
        }
    }

    static void printResult(
        String scenario,
        HttpResult<?> result
    ) {
        System.out.println("\n" + "=".repeat(65));
        System.out.println(scenario);
        System.out.println("HTTP status: " + result.status());
        System.out.println("Success: " + result.body().success());

        if (result.body().success()) {
            System.out.println("Data: " + result.body().data());
        } else {
            System.out.println("Error: " + result.body().error());
        }

        System.out.println(
            "Request ID: " +
            result.body().metadata().requestId()
        );

        System.out.println(
            "Consistency: " +
            result.body().metadata().consistency()
        );
    }

    public static void main(String[] args) {
        ResponsePolicy policy = new ResponsePolicy(
            "v1",
            100,
            true,
            ConsistencyLevel.STRONG
        );

        ResponseFactory factory = new ResponseFactory(policy);

        ProductRepository repository =
            new InMemoryProductRepository();

        ProductService service =
            new ProductService(repository, factory);

        printResult(
            "Successful retrieval",
            service.getProduct(101)
        );

        printResult(
            "Missing resource",
            service.getProduct(999)
        );

        printResult(
            "Paginated collection",
            service.listProducts(1, 2)
        );

        printResult(
            "Invalid pagination",
            service.listProducts(0, 500)
        );

        printResult(
            "Successful update",
            service.updatePrice(101, 8_900_000, 1)
        );

        printResult(
            "Stale version conflict",
            service.updatePrice(101, 9_200_000, 1)
        );

        Product updated = repository.findById(101);

        if (updated.version() != 2) {
            throw new IllegalStateException(
                "Optimistic concurrency test failed"
            );
        }

        System.out.println(
            "\nEnterprise API response checks passed."
        );
    }
}
