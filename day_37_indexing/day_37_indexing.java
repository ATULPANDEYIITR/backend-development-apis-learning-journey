import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Random;
import java.util.Set;
import java.util.TreeMap;
import java.util.function.Function;
import java.util.stream.Collectors;

/*
 * Enterprise Repository Analytics Indexing Model
 *
 * This program models an enterprise order service whose read workload contains
 * exact customer lookups, date ranges, region/status searches, and operational
 * searches for pending orders.
 *
 * Java-specific design choices:
 * - records provide immutable domain data
 * - enums prevent invalid status values
 * - sealed-style policy separation is represented with explicit interfaces
 * - TreeMap models ordered B-tree-like access
 * - HashMap models equality-oriented hash access
 * - composite keys make multi-column access explicit
 * - PartialIndex owns its predicate rather than embedding it in callers
 * - IndexingService centralizes index selection and validation
 *
 * The structures model database concepts. A production database remains
 * responsible for physical index maintenance and optimizer decisions.
 */

public class IndexingEnterpriseDemo {

    enum OrderStatus {
        PENDING,
        PAID,
        SHIPPED,
        CANCELLED
    }

    record Order(
        int id,
        int customerId,
        String region,
        OrderStatus status,
        String orderDate,
        long totalCents
    ) {
        Order {
            if (id <= 0) {
                throw new IllegalArgumentException("Order ID must be positive");
            }
            if (customerId <= 0) {
                throw new IllegalArgumentException(
                    "Customer ID must be positive"
                );
            }
            if (region == null || region.isBlank()) {
                throw new IllegalArgumentException(
                    "Region must not be blank"
                );
            }
            if (orderDate == null || !orderDate.matches("\\d{4}-\\d{2}-\\d{2}")) {
                throw new IllegalArgumentException(
                    "Date must use ISO yyyy-MM-dd form"
                );
            }
            if (totalCents < 0) {
                throw new IllegalArgumentException(
                    "Order amount cannot be negative"
                );
            }
            Objects.requireNonNull(status, "Status is required");
        }
    }

    record RegionStatusKey(String region, OrderStatus status) {
        RegionStatusKey {
            Objects.requireNonNull(region, "Region is required");
            Objects.requireNonNull(status, "Status is required");
        }
    }

    record QueryResult(
        String accessPath,
        int candidateCount,
        int matchCount
    ) {}

    interface Index<K> {
        void add(K key, int orderId);

        List<Integer> lookup(K key);

        int distinctKeys();
    }

    static final class HashIndex<K> implements Index<K> {
        private final Map<K, List<Integer>> buckets = new HashMap<>();

        @Override
        public void add(K key, int orderId) {
            buckets.computeIfAbsent(key, ignored -> new ArrayList<>())
                .add(orderId);
        }

        @Override
        public List<Integer> lookup(K key) {
            return List.copyOf(
                buckets.getOrDefault(key, Collections.emptyList())
            );
        }

        @Override
        public int distinctKeys() {
            return buckets.size();
        }
    }

    static final class OrderedDateIndex implements Index<String> {
        private final TreeMap<String, List<Integer>> entries = new TreeMap<>();

        @Override
        public void add(String key, int orderId) {
            entries.computeIfAbsent(key, ignored -> new ArrayList<>())
                .add(orderId);
        }

        @Override
        public List<Integer> lookup(String key) {
            return List.copyOf(
                entries.getOrDefault(key, Collections.emptyList())
            );
        }

        public List<Integer> range(String startInclusive, String endExclusive) {
            return entries.subMap(
                    startInclusive,
                    true,
                    endExclusive,
                    false
                )
                .values()
                .stream()
                .flatMap(List::stream)
                .toList();
        }

        @Override
        public int distinctKeys() {
            return entries.size();
        }
    }

    static final class CompositeIndex<K> implements Index<K> {
        private final Map<K, List<Integer>> entries = new HashMap<>();

        @Override
        public void add(K key, int orderId) {
            entries.computeIfAbsent(key, ignored -> new ArrayList<>())
                .add(orderId);
        }

        @Override
        public List<Integer> lookup(K key) {
            return List.copyOf(
                entries.getOrDefault(key, Collections.emptyList())
            );
        }

        @Override
        public int distinctKeys() {
            return entries.size();
        }
    }

    static final class PartialIndex {
        private final Function<Order, Boolean> predicate;
        private final List<Integer> orderIds = new ArrayList<>();

        PartialIndex(Function<Order, Boolean> predicate) {
            this.predicate = Objects.requireNonNull(predicate);
        }

        void consider(Order order) {
            if (predicate.apply(order)) {
                orderIds.add(order.id());
            }
        }

        List<Integer> ids() {
            return List.copyOf(orderIds);
        }

        int size() {
            return orderIds.size();
        }
    }

    static final class IndexingService {
        private final Map<Integer, Order> ordersById;
        private final HashIndex<Integer> customerIndex;
        private final OrderedDateIndex dateIndex;
        private final CompositeIndex<RegionStatusKey> regionStatusIndex;
        private final PartialIndex pendingIndex;

        IndexingService(List<Order> orders) {
            this.ordersById = new HashMap<>();

            this.customerIndex = new HashIndex<>();
            this.dateIndex = new OrderedDateIndex();
            this.regionStatusIndex = new CompositeIndex<>();
            this.pendingIndex = new PartialIndex(
                order -> order.status() == OrderStatus.PENDING
            );

            for (Order order : orders) {
                if (ordersById.putIfAbsent(order.id(), order) != null) {
                    throw new IllegalArgumentException(
                        "Duplicate order ID: " + order.id()
                    );
                }

                customerIndex.add(order.customerId(), order.id());
                dateIndex.add(order.orderDate(), order.id());

                regionStatusIndex.add(
                    new RegionStatusKey(order.region(), order.status()),
                    order.id()
                );

                pendingIndex.consider(order);
            }
        }

        Order findOrder(int id) {
            Order order = ordersById.get(id);

            if (order == null) {
                throw new IllegalArgumentException(
                    "Order does not exist: " + id
                );
            }

            return order;
        }

        QueryResult findCustomerOrders(int customerId) {
            List<Integer> candidates = customerIndex.lookup(customerId);

            long matches = candidates.stream()
                .map(this::findOrder)
                .filter(order -> order.customerId() == customerId)
                .count();

            return new QueryResult(
                "Hash index on customer_id",
                candidates.size(),
                Math.toIntExact(matches)
            );
        }

        QueryResult findDateRange(
            String startInclusive,
            String endExclusive
        ) {
            List<Integer> candidates = dateIndex.range(
                startInclusive,
                endExclusive
            );

            long matches = candidates.stream()
                .map(this::findOrder)
                .filter(order ->
                    order.orderDate().compareTo(startInclusive) >= 0
                    && order.orderDate().compareTo(endExclusive) < 0
                )
                .count();

            return new QueryResult(
                "Ordered date index",
                candidates.size(),
                Math.toIntExact(matches)
            );
        }

        QueryResult findRegionStatus(
            String region,
            OrderStatus status
        ) {
            RegionStatusKey key = new RegionStatusKey(region, status);

            List<Integer> candidates = regionStatusIndex.lookup(key);

            long matches = candidates.stream()
                .map(this::findOrder)
                .filter(order ->
                    order.region().equals(region)
                    && order.status() == status
                )
                .count();

            return new QueryResult(
                "Composite index on (region, status)",
                candidates.size(),
                Math.toIntExact(matches)
            );
        }

        QueryResult findPendingOrders() {
            List<Integer> candidates = pendingIndex.ids();

            long matches = candidates.stream()
                .map(this::findOrder)
                .filter(order -> order.status() == OrderStatus.PENDING)
                .count();

            return new QueryResult(
                "Partial index WHERE status = PENDING",
                candidates.size(),
                Math.toIntExact(matches)
            );
        }

        void printIndexStatistics() {
            System.out.println("\nIndex statistics");
            System.out.println(
                "customer_id distinct keys: "
                + customerIndex.distinctKeys()
            );
            System.out.println(
                "order_date distinct keys: "
                + dateIndex.distinctKeys()
            );
            System.out.println(
                "region/status distinct keys: "
                + regionStatusIndex.distinctKeys()
            );
            System.out.println(
                "pending partial-index rows: "
                + pendingIndex.size()
            );
        }
    }

    static List<Order> generateOrders(int count) {
        Random random = new Random(42);

        String[] regions = {
            "north", "south", "east", "west"
        };

        OrderStatus[] statuses = OrderStatus.values();

        int[] weights = {
            8, 28, 45, 19
        };

        List<Order> orders = new ArrayList<>(count);

        for (int id = 1; id <= count; id++) {
            int customerId = 1 + random.nextInt(5000);
            String region = regions[random.nextInt(regions.length)];

            int ticket = random.nextInt(100);
            OrderStatus status;

            if (ticket < weights[0]) {
                status = statuses[0];
            } else if (ticket < weights[0] + weights[1]) {
                status = statuses[1];
            } else if (ticket < weights[0] + weights[1] + weights[2]) {
                status = statuses[2];
            } else {
                status = statuses[3];
            }

            int year = 2024 + random.nextInt(3);
            int month = 1 + random.nextInt(12);
            int day = 1 + random.nextInt(28);

            String date = String.format(
                "%04d-%02d-%02d",
                year,
                month,
                day
            );

            long amount = 500L + random.nextInt(499501);

            orders.add(
                new Order(
                    id,
                    customerId,
                    region,
                    status,
                    date,
                    amount
                )
            );
        }

        return orders;
    }

    static double selectivity(
        List<Order> orders,
        Function<Order, ?> extractor
    ) {
        if (orders.isEmpty()) {
            return 0.0;
        }

        Set<?> distinct = orders.stream()
            .map(extractor)
            .collect(Collectors.toSet());

        return (double) distinct.size() / orders.size();
    }

    static void printQueryResult(
        String description,
        QueryResult result
    ) {
        System.out.println("\n" + description);
        System.out.println("  access path: " + result.accessPath());
        System.out.println("  candidates:  " + result.candidateCount());
        System.out.println("  matches:     " + result.matchCount());
    }

    public static void main(String[] args) {
        List<Order> orders = generateOrders(100_000);
        IndexingService service = new IndexingService(orders);

        System.out.println("Enterprise Repository Analytics Indexing Model");
        System.out.println("Orders: " + orders.size());

        printQueryResult(
            "Exact customer lookup",
            service.findCustomerOrders(2500)
        );

        printQueryResult(
            "Date-range lookup",
            service.findDateRange(
                "2026-06-01",
                "2026-07-01"
            )
        );

        printQueryResult(
            "Composite region/status lookup",
            service.findRegionStatus(
                "south",
                OrderStatus.PAID
            )
        );

        printQueryResult(
            "Operational pending-order lookup",
            service.findPendingOrders()
        );

        service.printIndexStatistics();

        System.out.println("\nSelectivity");
        System.out.printf(
            "status:     %.6f%n",
            selectivity(orders, Order::status)
        );
        System.out.printf(
            "region:     %.6f%n",
            selectivity(orders, Order::region)
        );
        System.out.printf(
            "customerId: %.6f%n",
            selectivity(orders, Order::customerId)
        );
        System.out.printf(
            "orderDate:  %.6f%n",
            selectivity(orders, Order::orderDate)
        );

        System.out.println("\nFailure-state handling");

        try {
            service.findOrder(999_999_999);
        } catch (IllegalArgumentException exception) {
            System.out.println(
                "Unknown order rejected: " + exception.getMessage()
            );
        }

        try {
            new Order(
                100_001,
                2500,
                "south",
                OrderStatus.PAID,
                "invalid-date",
                1000
            );
        } catch (IllegalArgumentException exception) {
            System.out.println(
                "Invalid order rejected: " + exception.getMessage()
            );
        }

        System.out.println("\nDesign distinctions");
        System.out.println(
            "Hash access favors exact equality on a high-cardinality key."
        );
        System.out.println(
            "Ordered access favors ranges and ordered traversal."
        );
        System.out.println(
            "Composite access represents a multi-column predicate."
        );
        System.out.println(
            "Partial access stores only rows satisfying a stable predicate."
        );
        System.out.println(
            "Selectivity measures how strongly a predicate can narrow a relation."
        );
    }
}
