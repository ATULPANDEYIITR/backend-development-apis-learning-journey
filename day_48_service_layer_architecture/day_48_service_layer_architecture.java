import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/*
 * Enterprise service-layer example.
 *
 * Controller:
 *   Boundary adapter. It translates transport-oriented input and output.
 *
 * Service:
 *   Application orchestration. It coordinates repositories and domain
 *   operations without exposing persistence or HTTP details to the domain.
 *
 * Repository:
 *   Persistence abstraction. The service depends on interfaces so storage
 *   can be replaced without rewriting business rules.
 *
 * Domain:
 *   Order and OrderLine protect invariants and legal state transitions.
 *
 * Java 17 records are used for immutable commands and value-like responses.
 */

public class ServiceLayerArchitectureDemo {

    enum OrderStatus {
        DRAFT,
        CONFIRMED,
        CANCELLED
    }

    static class DomainException extends RuntimeException {
        DomainException(String message) {
            super(message);
        }
    }

    static class NotFoundException extends DomainException {
        NotFoundException(String message) {
            super(message);
        }
    }

    static class ValidationException extends DomainException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class ConflictException extends DomainException {
        ConflictException(String message) {
            super(message);
        }
    }

    record Product(
        String id,
        String name,
        long priceCents,
        boolean active
    ) {
        Product {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Product id is required");
            }

            if (name == null || name.isBlank()) {
                throw new ValidationException("Product name is required");
            }

            if (priceCents < 0) {
                throw new ValidationException(
                    "Product price cannot be negative"
                );
            }
        }
    }

    static final class OrderLine {
        private final String productId;
        private final int quantity;
        private final long unitPriceCents;

        OrderLine(
            String productId,
            int quantity,
            long unitPriceCents
        ) {
            if (productId == null || productId.isBlank()) {
                throw new ValidationException("Product id is required");
            }

            if (quantity <= 0) {
                throw new ValidationException(
                    "Quantity must be positive"
                );
            }

            if (unitPriceCents < 0) {
                throw new ValidationException(
                    "Unit price cannot be negative"
                );
            }

            this.productId = productId;
            this.quantity = quantity;
            this.unitPriceCents = unitPriceCents;
        }

        String productId() {
            return productId;
        }

        int quantity() {
            return quantity;
        }

        long subtotal() {
            return Math.multiplyExact(
                quantity,
                unitPriceCents
            );
        }
    }

    static final class Order {
        private final String id;
        private final String customerId;
        private final Instant createdAt;
        private final List<OrderLine> lines = new ArrayList<>();
        private OrderStatus status = OrderStatus.DRAFT;

        Order(String id, String customerId) {
            this.id = Objects.requireNonNull(id);
            this.customerId = Objects.requireNonNull(customerId);

            if (customerId.isBlank()) {
                throw new ValidationException(
                    "Customer id cannot be blank"
                );
            }

            this.createdAt = Instant.now();
        }

        String id() {
            return id;
        }

        String customerId() {
            return customerId;
        }

        OrderStatus status() {
            return status;
        }

        Instant createdAt() {
            return createdAt;
        }

        List<OrderLine> lines() {
            return List.copyOf(lines);
        }

        void addLine(OrderLine line) {
            if (status != OrderStatus.DRAFT) {
                throw new ConflictException(
                    "Only draft orders can be modified"
                );
            }

            boolean duplicate = lines.stream()
                .anyMatch(
                    existing ->
                        existing.productId().equals(line.productId())
                );

            if (duplicate) {
                throw new ConflictException(
                    "Product already exists in order"
                );
            }

            lines.add(line);
        }

        long totalCents() {
            long total = 0;

            for (OrderLine line : lines) {
                total = Math.addExact(
                    total,
                    line.subtotal()
                );
            }

            return total;
        }

        void confirm() {
            if (status != OrderStatus.DRAFT) {
                throw new ConflictException(
                    "Only draft orders can be confirmed"
                );
            }

            if (lines.isEmpty()) {
                throw new ValidationException(
                    "An order must contain at least one line"
                );
            }

            status = OrderStatus.CONFIRMED;
        }

        void cancel() {
            if (status == OrderStatus.CANCELLED) {
                throw new ConflictException(
                    "Order is already cancelled"
                );
            }

            if (status == OrderStatus.CONFIRMED) {
                throw new ConflictException(
                    "Confirmed orders require cancellation-policy processing"
                );
            }

            status = OrderStatus.CANCELLED;
        }
    }

    interface Repository<T> {
        Optional<T> findById(String id);

        void save(T entity);
    }

    interface ProductRepository extends Repository<Product> {
        Optional<Product> findActiveById(String id);
    }

    static final class InMemoryProductRepository
        implements ProductRepository {

        private final Map<String, Product> products =
            new ConcurrentHashMap<>();

        @Override
        public Optional<Product> findById(String id) {
            return Optional.ofNullable(products.get(id));
        }

        @Override
        public Optional<Product> findActiveById(String id) {
            return findById(id)
                .filter(Product::active);
        }

        @Override
        public void save(Product product) {
            products.put(product.id(), product);
        }
    }

    static final class InMemoryOrderRepository
        implements Repository<Order> {

        private final Map<String, Order> orders =
            new ConcurrentHashMap<>();

        @Override
        public Optional<Order> findById(String id) {
            return Optional.ofNullable(orders.get(id));
        }

        @Override
        public void save(Order order) {
            orders.put(order.id(), order);
        }
    }

    record CreateOrderCommand(String customerId) {
        CreateOrderCommand {
            if (customerId == null || customerId.isBlank()) {
                throw new ValidationException(
                    "Customer id is required"
                );
            }
        }
    }

    record AddLineCommand(
        String orderId,
        String productId,
        int quantity
    ) {
        AddLineCommand {
            if (orderId == null || orderId.isBlank()) {
                throw new ValidationException(
                    "Order id is required"
                );
            }

            if (productId == null || productId.isBlank()) {
                throw new ValidationException(
                    "Product id is required"
                );
            }

            if (quantity <= 0) {
                throw new ValidationException(
                    "Quantity must be positive"
                );
            }
        }
    }

    static final class OrderService {
        private final Repository<Order> orderRepository;
        private final ProductRepository productRepository;

        OrderService(
            Repository<Order> orderRepository,
            ProductRepository productRepository
        ) {
            this.orderRepository = orderRepository;
            this.productRepository = productRepository;
        }

        Order createOrder(CreateOrderCommand command) {
            String id = "ORD-" + System.nanoTime();

            Order order = new Order(
                id,
                command.customerId()
            );

            orderRepository.save(order);
            return order;
        }

        Order addLine(AddLineCommand command) {
            Order order = orderRepository
                .findById(command.orderId())
                .orElseThrow(
                    () -> new NotFoundException(
                        "Order does not exist"
                    )
                );

            Product product = productRepository
                .findActiveById(command.productId())
                .orElseThrow(
                    () -> new NotFoundException(
                        "Active product does not exist"
                    )
                );

            order.addLine(
                new OrderLine(
                    product.id(),
                    command.quantity(),
                    product.priceCents()
                )
            );

            orderRepository.save(order);
            return order;
        }

        Order confirm(String orderId) {
            Order order = orderRepository
                .findById(orderId)
                .orElseThrow(
                    () -> new NotFoundException(
                        "Order does not exist"
                    )
                );

            order.confirm();
            orderRepository.save(order);
            return order;
        }
    }

    static final class OrderController {
        private final OrderService service;

        OrderController(OrderService service) {
            this.service = service;
        }

        Response create(String customerId) {
            try {
                Order order = service.createOrder(
                    new CreateOrderCommand(customerId)
                );

                return Response.created(
                    serialize(order)
                );
            } catch (ValidationException error) {
                return Response.badRequest(error.getMessage());
            }
        }

        Response addLine(
            String orderId,
            String productId,
            int quantity
        ) {
            try {
                Order order = service.addLine(
                    new AddLineCommand(
                        orderId,
                        productId,
                        quantity
                    )
                );

                return Response.ok(serialize(order));
            } catch (NotFoundException error) {
                return Response.notFound(error.getMessage());
            } catch (ValidationException error) {
                return Response.badRequest(error.getMessage());
            } catch (ConflictException error) {
                return Response.conflict(error.getMessage());
            }
        }

        Response confirm(String orderId) {
            try {
                return Response.ok(
                    serialize(service.confirm(orderId))
                );
            } catch (NotFoundException error) {
                return Response.notFound(error.getMessage());
            } catch (ConflictException error) {
                return Response.conflict(error.getMessage());
            } catch (ValidationException error) {
                return Response.badRequest(error.getMessage());
            }
        }

        private Map<String, Object> serialize(Order order) {
            return Map.of(
                "id", order.id(),
                "customerId", order.customerId(),
                "status", order.status().name(),
                "totalCents", order.totalCents(),
                "lineCount", order.lines().size()
            );
        }
    }

    record Response(
        int status,
        Object body
    ) {
        static Response created(Object body) {
            return new Response(201, body);
        }

        static Response ok(Object body) {
            return new Response(200, body);
        }

        static Response badRequest(String message) {
            return new Response(400, Map.of("error", message));
        }

        static Response notFound(String message) {
            return new Response(404, Map.of("error", message));
        }

        static Response conflict(String message) {
            return new Response(409, Map.of("error", message));
        }
    }

    public static void main(String[] args) {
        ProductRepository products =
            new InMemoryProductRepository();

        Repository<Order> orders =
            new InMemoryOrderRepository();

        products.save(
            new Product(
                "P-KEYBOARD",
                "Mechanical Keyboard",
                8500,
                true
            )
        );

        OrderService service =
            new OrderService(orders, products);

        OrderController controller =
            new OrderController(service);

        Response created =
            controller.create("CUSTOMER-42");

        System.out.println("Create: " + created);

        String orderId =
            ((Map<?, ?>) created.body()).get("id").toString();

        Response added =
            controller.addLine(
                orderId,
                "P-KEYBOARD",
                2
            );

        System.out.println("Add line: " + added);

        Response confirmed =
            controller.confirm(orderId);

        System.out.println("Confirm: " + confirmed);

        Response invalid =
            controller.addLine(
                orderId,
                "P-KEYBOARD",
                1
            );

        System.out.println("Invalid state transition: " + invalid);
    }
}
