import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class CatalogSearch {

    enum SortField {
        ID,
        NAME,
        CATEGORY,
        PRICE,
        RATING
    }

    enum SortDirection {
        ASC,
        DESC
    }

    enum SearchStatus {
        SUCCESS,
        EMPTY,
        REJECTED
    }

    record Product(
        int id,
        String name,
        String category,
        double price,
        double rating,
        boolean active
    ) {
        Product {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Product ID must be positive."
                );
            }

            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Product name is required."
                );
            }

            if (category == null || category.isBlank()) {
                throw new IllegalArgumentException(
                    "Category is required."
                );
            }

            if (!Double.isFinite(price) || price < 0) {
                throw new IllegalArgumentException(
                    "Invalid price."
                );
            }

            if (!Double.isFinite(rating) ||
                rating < 0 ||
                rating > 5) {
                throw new IllegalArgumentException(
                    "Rating must be between 0 and 5."
                );
            }
        }
    }

    record SearchCriteria(
        String keyword,
        String category,
        Double minPrice,
        Double maxPrice,
        Double minRating,
        boolean activeOnly,
        SortField sortField,
        SortDirection direction,
        int limit,
        int offset
    ) {
        SearchCriteria {
            keyword = keyword == null ? "" : keyword.trim();

            Objects.requireNonNull(sortField);
            Objects.requireNonNull(direction);

            if (keyword.length() > 100) {
                throw new IllegalArgumentException(
                    "Keyword exceeds 100 characters."
                );
            }

            if (category != null && category.length() > 80) {
                throw new IllegalArgumentException(
                    "Category exceeds 80 characters."
                );
            }

            if (minPrice != null &&
                (!Double.isFinite(minPrice) || minPrice < 0)) {
                throw new IllegalArgumentException(
                    "Invalid minimum price."
                );
            }

            if (maxPrice != null &&
                (!Double.isFinite(maxPrice) || maxPrice < 0)) {
                throw new IllegalArgumentException(
                    "Invalid maximum price."
                );
            }

            if (minPrice != null && maxPrice != null &&
                minPrice > maxPrice) {
                throw new IllegalArgumentException(
                    "Minimum price exceeds maximum price."
                );
            }

            if (minRating != null &&
                (!Double.isFinite(minRating) ||
                 minRating < 0 ||
                 minRating > 5)) {
                throw new IllegalArgumentException(
                    "Rating must be between 0 and 5."
                );
            }

            if (limit < 1 || limit > 100) {
                throw new IllegalArgumentException(
                    "Limit must be between 1 and 100."
                );
            }

            if (offset < 0) {
                throw new IllegalArgumentException(
                    "Offset cannot be negative."
                );
            }
        }
    }

    record SearchResponse(
        SearchStatus status,
        List<Product> results,
        long total,
        int limit,
        int offset,
        boolean hasNext,
        List<String> appliedFilters
    ) {
        SearchResponse {
            results = List.copyOf(results);
            appliedFilters = List.copyOf(appliedFilters);
        }
    }

    record SearchAudit(
        String operation,
        int filtersApplied,
        long matchedRecords,
        SearchStatus status
    ) {}

    interface SearchRepository {
        List<Product> findAll();
    }

    static class InMemoryProductRepository
        implements SearchRepository {

        private final List<Product> products;

        InMemoryProductRepository() {
            products = List.of(
                new Product(1, "Laptop Pro", "Electronics", 95000, 4.8, true),
                new Product(2, "Wireless Mouse", "Electronics", 1200, 4.2, true),
                new Product(3, "Mechanical Keyboard", "Electronics", 4500, 4.6, true),
                new Product(4, "Office Chair", "Furniture", 12500, 4.3, true),
                new Product(5, "Standing Desk", "Furniture", 22000, 4.7, true),
                new Product(6, "Old Monitor", "Electronics", 8000, 3.5, false),
                new Product(7, "Notebook", "Stationery", 100, 4.0, true),
                new Product(8, "Premium Headphones", "Electronics", 6500, 4.9, true),
                new Product(9, "Desk Lamp", "Furniture", 1800, 3.9, true),
                new Product(10, "USB Hub", "Electronics", 1500, 4.1, true)
            );
        }

        @Override
        public List<Product> findAll() {
            return products;
        }
    }

    static class SearchPolicy {

        private final Set<SortField> allowedFields =
            Set.of(
                SortField.ID,
                SortField.NAME,
                SortField.CATEGORY,
                SortField.PRICE,
                SortField.RATING
            );

        void validate(SearchCriteria criteria) {
            Objects.requireNonNull(criteria);

            if (!allowedFields.contains(criteria.sortField())) {
                throw new IllegalArgumentException(
                    "Sorting field is not permitted."
                );
            }
        }
    }

    static class SearchService {

        private final SearchRepository repository;
        private final SearchPolicy policy;
        private final List<SearchAudit> auditLog =
            new ArrayList<>();

        SearchService(
            SearchRepository repository,
            SearchPolicy policy
        ) {
            this.repository = repository;
            this.policy = policy;
        }

        private static String normalize(String value) {
            return value.toLowerCase(Locale.ROOT);
        }

        private Predicate<Product> buildPredicate(
            SearchCriteria criteria,
            List<String> appliedFilters
        ) {
            List<Predicate<Product>> predicates =
                new ArrayList<>();

            if (criteria.activeOnly()) {
                predicates.add(Product::active);
                appliedFilters.add("active = true");
            }

            if (!criteria.keyword().isBlank()) {
                String keyword = normalize(criteria.keyword());

                predicates.add(product ->
                    normalize(product.name()).contains(keyword) ||
                    normalize(product.category()).contains(keyword)
                );

                appliedFilters.add("keyword contains");
            }

            if (criteria.category() != null &&
                !criteria.category().isBlank()) {

                String category = normalize(criteria.category());

                predicates.add(product ->
                    normalize(product.category()).equals(category)
                );

                appliedFilters.add("category equals");
            }

            if (criteria.minPrice() != null) {
                predicates.add(product ->
                    product.price() >= criteria.minPrice()
                );

                appliedFilters.add("price >= minimum");
            }

            if (criteria.maxPrice() != null) {
                predicates.add(product ->
                    product.price() <= criteria.maxPrice()
                );

                appliedFilters.add("price <= maximum");
            }

            if (criteria.minRating() != null) {
                predicates.add(product ->
                    product.rating() >= criteria.minRating()
                );

                appliedFilters.add("rating >= minimum");
            }

            // AND semantics: every predicate must match.
            return predicates.stream()
                .reduce(product -> true, Predicate::and);
        }

        private Comparator<Product> getComparator(
            SearchCriteria criteria
        ) {
            Comparator<Product> comparator = switch (
                criteria.sortField()
            ) {
                case ID -> Comparator.comparingInt(Product::id);

                case NAME -> Comparator.comparing(
                    product -> normalize(product.name())
                );

                case CATEGORY -> Comparator.comparing(
                    product -> normalize(product.category())
                );

                case PRICE -> Comparator.comparingDouble(
                    Product::price
                );

                case RATING -> Comparator.comparingDouble(
                    Product::rating
                );
            };

            if (criteria.direction() == SortDirection.DESC) {
                comparator = comparator.reversed();
            }

            // Stable deterministic tie-breaker.
            return comparator.thenComparingInt(Product::id);
        }

        SearchResponse search(SearchCriteria criteria) {
            policy.validate(criteria);

            List<String> appliedFilters = new ArrayList<>();

            try {
                Predicate<Product> predicate =
                    buildPredicate(criteria, appliedFilters);

                List<Product> matched = repository.findAll()
                    .stream()
                    .filter(predicate)
                    .sorted(getComparator(criteria))
                    .collect(Collectors.toList());

                long total = matched.size();

                int start = Math.min(
                    criteria.offset(),
                    matched.size()
                );

                int end = Math.min(
                    start + criteria.limit(),
                    matched.size()
                );

                List<Product> page = List.copyOf(
                    matched.subList(start, end)
                );

                SearchStatus status = page.isEmpty()
                    ? SearchStatus.EMPTY
                    : SearchStatus.SUCCESS;

                SearchResponse response = new SearchResponse(
                    status,
                    page,
                    total,
                    criteria.limit(),
                    criteria.offset(),
                    end < total,
                    appliedFilters
                );

                auditLog.add(new SearchAudit(
                    "CATALOG_SEARCH",
                    appliedFilters.size(),
                    total,
                    status
                ));

                return response;

            } catch (RuntimeException exception) {
                auditLog.add(new SearchAudit(
                    "CATALOG_SEARCH",
                    appliedFilters.size(),
                    0,
                    SearchStatus.REJECTED
                ));

                throw exception;
            }
        }

        List<Product> searchAllPages(
            SearchCriteria original,
            int pageSize
        ) {
            if (pageSize < 1 || pageSize > 100) {
                throw new IllegalArgumentException(
                    "Invalid page size."
                );
            }

            List<Product> allResults = new ArrayList<>();
            int offset = 0;

            while (true) {
                SearchCriteria pageCriteria = new SearchCriteria(
                    original.keyword(),
                    original.category(),
                    original.minPrice(),
                    original.maxPrice(),
                    original.minRating(),
                    original.activeOnly(),
                    original.sortField(),
                    original.direction(),
                    pageSize,
                    offset
                );

                SearchResponse response = search(pageCriteria);

                allResults.addAll(response.results());

                if (!response.hasNext()) {
                    break;
                }

                offset += pageSize;
            }

            return List.copyOf(allResults);
        }

        List<SearchAudit> getAuditLog() {
            return List.copyOf(auditLog);
        }
    }

    private static SearchCriteria defaults() {
        return new SearchCriteria(
            "",
            null,
            null,
            null,
            null,
            true,
            SortField.NAME,
            SortDirection.ASC,
            10,
            0
        );
    }

    private static void printResponse(SearchResponse response) {
        System.out.printf(
            "%-5s %-25s %-16s %-12s %-8s%n",
            "ID", "NAME", "CATEGORY", "PRICE", "RATING"
        );

        System.out.println("-".repeat(72));

        for (Product product : response.results()) {
            System.out.printf(
                "%-5d %-25s %-16s %-12.2f %-8.1f%n",
                product.id(),
                product.name(),
                product.category(),
                product.price(),
                product.rating()
            );
        }

        System.out.printf(
            "Status: %s | Total: %d | Returned: %d | Has next: %s%n%n",
            response.status(),
            response.total(),
            response.results().size(),
            response.hasNext()
        );
    }

    private static void runTests(SearchService service) {
        SearchCriteria electronics = new SearchCriteria(
            "",
            "Electronics",
            null,
            null,
            null,
            true,
            SortField.NAME,
            SortDirection.ASC,
            10,
            0
        );

        assert service.search(electronics).total() == 6;

        SearchCriteria priceFilter = new SearchCriteria(
            "",
            null,
            1000.0,
            7000.0,
            4.0,
            true,
            SortField.PRICE,
            SortDirection.ASC,
            10,
            0
        );

        SearchResponse priceResults = service.search(priceFilter);

        assert priceResults.results().stream().allMatch(
            product ->
                product.price() >= 1000 &&
                product.price() <= 7000 &&
                product.rating() >= 4
        );

        SearchCriteria keyword = new SearchCriteria(
            "desk",
            null,
            null,
            null,
            null,
            true,
            SortField.NAME,
            SortDirection.ASC,
            10,
            0
        );

        assert service.search(keyword).total() == 2;

        SearchCriteria firstPageCriteria = new SearchCriteria(
            "",
            null,
            null,
            null,
            null,
            true,
            SortField.ID,
            SortDirection.ASC,
            2,
            0
        );

        SearchResponse first = service.search(firstPageCriteria);

        SearchCriteria secondPageCriteria = new SearchCriteria(
            "",
            null,
            null,
            null,
            null,
            true,
            SortField.ID,
            SortDirection.ASC,
            2,
            2
        );

        SearchResponse second = service.search(secondPageCriteria);

        assert first.results().get(0).id() !=
            second.results().get(0).id();

        assert service.searchAllPages(
            defaults(), 3
        ).size() == 9;

        SearchCriteria noMatches = new SearchCriteria(
            "not-present",
            null,
            null,
            null,
            null,
            true,
            SortField.NAME,
            SortDirection.ASC,
            10,
            0
        );

        assert service.search(noMatches).status() ==
            SearchStatus.EMPTY;

        boolean rejected = false;

        try {
            new SearchCriteria(
                "",
                null,
                10000.0,
                100.0,
                null,
                true,
                SortField.NAME,
                SortDirection.ASC,
                10,
                0
            );
        } catch (IllegalArgumentException exception) {
            rejected = true;
        }

        assert rejected;

        System.out.println("All automated tests passed.\n");
    }

    public static void main(String[] args) {
        try {
            SearchRepository repository =
                new InMemoryProductRepository();

            SearchPolicy policy = new SearchPolicy();

            SearchService service =
                new SearchService(repository, policy);

            System.out.println(
                "ENTERPRISE CATALOG FILTERING AND SEARCH"
            );

            System.out.println("\n1. Keyword search");

            printResponse(service.search(
                new SearchCriteria(
                    "keyboard",
                    null,
                    null,
                    null,
                    null,
                    true,
                    SortField.NAME,
                    SortDirection.ASC,
                    10,
                    0
                )
            ));

            System.out.println("2. Combined filters");

            printResponse(service.search(
                new SearchCriteria(
                    "",
                    "Electronics",
                    1000.0,
                    10000.0,
                    4.0,
                    true,
                    SortField.RATING,
                    SortDirection.DESC,
                    5,
                    0
                )
            ));

            System.out.println("3. Price sorting");

            printResponse(service.search(
                new SearchCriteria(
                    "",
                    null,
                    null,
                    null,
                    null,
                    true,
                    SortField.PRICE,
                    SortDirection.ASC,
                    3,
                    0
                )
            ));

            System.out.println("4. Empty result");

            printResponse(service.search(
                new SearchCriteria(
                    "unavailable-product",
                    null,
                    null,
                    null,
                    null,
                    true,
                    SortField.NAME,
                    SortDirection.ASC,
                    10,
                    0
                )
            ));

            System.out.println("5. Automated tests");

            runTests(service);

            System.out.println("6. Full paginated retrieval");

            List<Product> all = service.searchAllPages(
                defaults(),
                3
            );

            System.out.println(
                "Retrieved active products: " + all.size()
            );

            System.out.println("\n7. Search audit");

            for (SearchAudit audit : service.getAuditLog()) {
                System.out.println(audit);
            }

            System.out.println("\n8. Invalid parameter");

            try {
                new SearchCriteria(
                    "",
                    null,
                    null,
                    null,
                    8.0,
                    true,
                    SortField.NAME,
                    SortDirection.ASC,
                    10,
                    0
                );
            } catch (IllegalArgumentException exception) {
                System.out.println(
                    "Rejected: " + exception.getMessage()
                );
            }

        } catch (Exception exception) {
            System.err.println(
                "Application failure: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
