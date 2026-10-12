import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/*
 * ORM Fundamentals
 *
 * Enterprise-oriented model for a procurement order service.
 *
 * The program uses explicit domain classes and an in-memory persistence layer
 * to make ORM concerns visible: model mapping, relationships, identity,
 * lifecycle state, validation, unit of work, and persistence boundaries.
 *
 * Java 17+.
 */

public class OrmFundamentals {

    enum OrderStatus {
        DRAFT,
        SUBMITTED,
        APPROVED,
        FULFILLED,
        CANCELLED
    }

    record Supplier(Long id, String name, String taxId) {
        public Supplier {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Supplier name is required");
            }
            if (taxId == null || taxId.isBlank()) {
                throw new IllegalArgumentException("Supplier tax ID is required");
            }
        }
    }

    record Product(Long id, String sku, String name) {
        public Product {
            if (sku == null || sku.isBlank()) {
                throw new IllegalArgumentException("Product SKU is required");
            }
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Product name is required");
            }
        }
    }

    static final class PurchaseLine {
        private final Long productId;
        private final int quantity;
        private final double unitPrice;

        PurchaseLine(Long productId, int quantity, double unitPrice) {
            if (productId == null) {
                throw new IllegalArgumentException("Product ID is required");
            }
            if (quantity <= 0) {
                throw new IllegalArgumentException(
                    "Purchase quantity must be positive"
                );
            }
            if (unitPrice < 0) {
                throw new IllegalArgumentException(
                    "Unit price cannot be negative"
                );
            }

            this.productId = productId;
            this.quantity = quantity;
            this.unitPrice = unitPrice;
        }

        Long productId() {
            return productId;
        }

        int quantity() {
            return quantity;
        }

        double unitPrice() {
            return unitPrice;
        }

        double lineTotal() {
            return quantity * unitPrice;
        }
    }

    static final class PurchaseOrder {
        private Long id;
        private final Long supplierId;
        private final Instant createdAt;
        private OrderStatus status;
        private final List<PurchaseLine> lines = new ArrayList<>();

        PurchaseOrder(Long supplierId) {
            this.supplierId = Objects.requireNonNull(
                supplierId,
                "Supplier ID is required"
            );
            this.createdAt = Instant.now();
            this.status = OrderStatus.DRAFT;
        }

        void addLine(PurchaseLine line) {
            if (status != OrderStatus.DRAFT) {
                throw new IllegalStateException(
                    "Lines cannot be changed after submission"
                );
            }

            lines.add(Objects.requireNonNull(line));
        }

        void submit() {
            if (lines.isEmpty()) {
                throw new IllegalStateException(
                    "An order cannot be submitted without lines"
                );
            }

            transitionTo(OrderStatus.SUBMITTED);
        }

        void approve() {
            transitionTo(OrderStatus.APPROVED);
        }

        void fulfill() {
            transitionTo(OrderStatus.FULFILLED);
        }

        void cancel() {
            if (status == OrderStatus.FULFILLED) {
                throw new IllegalStateException(
                    "Fulfilled orders cannot be cancelled"
                );
            }

            status = OrderStatus.CANCELLED;
        }

        private void transitionTo(OrderStatus target) {
            Map<OrderStatus, List<OrderStatus>> allowed =
                new EnumMap<>(OrderStatus.class);

            allowed.put(
                OrderStatus.DRAFT,
                List.of(OrderStatus.SUBMITTED, OrderStatus.CANCELLED)
            );
            allowed.put(
                OrderStatus.SUBMITTED,
                List.of(OrderStatus.APPROVED, OrderStatus.CANCELLED)
            );
            allowed.put(
                OrderStatus.APPROVED,
                List.of(OrderStatus.FULFILLED, OrderStatus.CANCELLED)
            );
            allowed.put(OrderStatus.FULFILLED, List.of());
            allowed.put(OrderStatus.CANCELLED, List.of());

            if (!allowed.get(status).contains(target)) {
                throw new IllegalStateException(
                    "Invalid order transition: "
                    + status
                    + " -> "
                    + target
                );
            }

            status = target;
        }

        Long id() {
            return id;
        }

        void assignId(Long id) {
            if (this.id != null) {
                throw new IllegalStateException(
                    "Persistent identity has already been assigned"
                );
            }

            this.id = id;
        }

        Long supplierId() {
            return supplierId;
        }

        Instant createdAt() {
            return createdAt;
        }

        OrderStatus status() {
            return status;
        }

        List<PurchaseLine> lines() {
            return List.copyOf(lines);
        }

        double total() {
            return lines.stream()
                .mapToDouble(PurchaseLine::lineTotal)
                .sum();
        }
    }

    interface Repository<T, ID> {
        T save(T entity);
        Optional<T> findById(ID id);
    }

    static final class InMemoryRepository<T> implements Repository<T, Long> {
        private final Map<Long, T> rows = new HashMap<>();
        private long nextId = 1;

        @Override
        public T save(T entity) {
            if (entity instanceof PurchaseOrder order) {
                if (order.id() == null) {
                    order.assignId(nextId++);
                }

                rows.put(order.id(), entity);
                return entity;
            }

            throw new IllegalArgumentException(
                "Unsupported persistent entity"
            );
        }

        @Override
        public Optional<T> findById(Long id) {
            return Optional.ofNullable(rows.get(id));
        }
    }

    static final class PersistenceContext {
        private final Map<String, Object> identityMap = new HashMap<>();
        private final List<Object> pendingInserts = new ArrayList<>();

        void persist(Object entity) {
            pendingInserts.add(entity);
        }

        void cache(String entityType, Long id, Object entity) {
            identityMap.put(entityType + ":" + id, entity);
        }

        Object cached(String entityType, Long id) {
            return identityMap.get(entityType + ":" + id);
        }

        List<Object> pendingInserts() {
            return List.copyOf(pendingInserts);
        }

        void clear() {
            pendingInserts.clear();
        }
    }

    static final class PurchaseOrderService {
        private final Repository<PurchaseOrder, Long> repository;
        private final PersistenceContext context;

        PurchaseOrderService(
            Repository<PurchaseOrder, Long> repository,
            PersistenceContext context
        ) {
            this.repository = repository;
            this.context = context;
        }

        PurchaseOrder createOrder(
            Supplier supplier,
            List<PurchaseLine> lines
        ) {
            Objects.requireNonNull(supplier);

            PurchaseOrder order = new PurchaseOrder(supplier.id());

            for (PurchaseLine line : lines) {
                order.addLine(line);
            }

            context.persist(order);

            PurchaseOrder saved = repository.save(order);

            context.cache(
                "PurchaseOrder",
                saved.id(),
                saved
            );

            context.clear();

            return saved;
        }

        PurchaseOrder load(Long id) {
            Object cached = context.cached("PurchaseOrder", id);

            if (cached instanceof PurchaseOrder order) {
                return order;
            }

            PurchaseOrder order = repository
                .findById(id)
                .orElseThrow(() ->
                    new IllegalArgumentException(
                        "Purchase order does not exist"
                    )
                );

            context.cache("PurchaseOrder", id, order);

            return order;
        }
    }

    public static void main(String[] args) {
        Supplier supplier = new Supplier(
            20L,
            "Industrial Components Ltd.",
            "GSTIN-29ABCDE1234F1Z5"
        );

        Product server = new Product(
            100L,
            "SRV-001",
            "Application Server"
        );

        Product monitor = new Product(
            101L,
            "MON-002",
            "Operations Monitor"
        );

        PurchaseLine serverLine = new PurchaseLine(
            server.id(),
            4,
            125000.00
        );

        PurchaseLine monitorLine = new PurchaseLine(
            monitor.id(),
            8,
            18000.00
        );

        InMemoryRepository<PurchaseOrder> repository =
            new InMemoryRepository<>();

        PersistenceContext context = new PersistenceContext();

        PurchaseOrderService service =
            new PurchaseOrderService(repository, context);

        PurchaseOrder order = service.createOrder(
            supplier,
            List.of(serverLine, monitorLine)
        );

        System.out.println("Enterprise ORM domain model");
        System.out.println("---------------------------");
        System.out.println("Order ID: " + order.id());
        System.out.println("Supplier ID: " + order.supplierId());
        System.out.println("Created: " + order.createdAt());
        System.out.println("Status: " + order.status());
        System.out.printf("Total: %.2f%n", order.total());

        order.submit();
        order.approve();

        System.out.println("\nState transitions");
        System.out.println("Status after approval: " + order.status());

        try {
            order.addLine(
                new PurchaseLine(
                    monitor.id(),
                    1,
                    18000
                )
            );
        } catch (IllegalStateException error) {
            System.out.println(
                "Rejected mutation after submission: "
                + error.getMessage()
            );
        }

        order.fulfill();

        System.out.println(
            "Final status: " + order.status()
        );

        PurchaseOrder firstLoad = service.load(order.id());
        PurchaseOrder secondLoad = service.load(order.id());

        System.out.println("\nPersistence context");
        System.out.println(
            "Repeated loads preserve object identity: "
            + (firstLoad == secondLoad)
        );

        try {
            order.cancel();
        } catch (IllegalStateException error) {
            System.out.println(
                "Rejected invalid state transition: "
                + error.getMessage()
            );
        }

        System.out.println(
            "\nRelational mapping boundary: supplierId and productId are "
            + "foreign-key values, while the Java domain exposes Supplier, "
            + "Product, PurchaseOrder, and PurchaseLine as separate domain types."
        );
    }
}
