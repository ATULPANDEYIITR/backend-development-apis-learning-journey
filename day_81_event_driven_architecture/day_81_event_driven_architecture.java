import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;
import java.util.function.Predicate;
import java.util.logging.Level;
import java.util.logging.Logger;

// ============================================================
// EVENT-DRIVEN ARCHITECTURE
// ============================================================

public class EventDrivenArchitecture {

    private static final Logger LOGGER =
            Logger.getLogger(EventDrivenArchitecture.class.getName());

    // ========================================================
    // CUSTOM EXCEPTIONS
    // ========================================================

    static class EventException extends RuntimeException {
        EventException(String message) {
            super(message);
        }

        EventException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static class SchemaException extends EventException {
        SchemaException(String message) {
            super(message);
        }
    }

    static class DuplicateEventException extends EventException {
        DuplicateEventException(String message) {
            super(message);
        }
    }

    // ========================================================
    // EVENT TYPES
    // ========================================================

    enum EventStatus {
        PENDING,
        PUBLISHED,
        CONSUMED,
        FAILED,
        DEAD_LETTER
    }

    enum DeliveryStatus {
        CONSUMED,
        ALREADY_PROCESSED,
        FILTERED,
        DEAD_LETTER
    }

    // ========================================================
    // EVENT SCHEMA
    // ========================================================

    record FieldDefinition(
            Class<?> type,
            boolean required
    ) {
        FieldDefinition {
            Objects.requireNonNull(type);
        }
    }

    static final class EventSchema {

        private final String name;
        private final int version;
        private final Map<String, FieldDefinition> fields;

        EventSchema(
                String name,
                int version,
                Map<String, FieldDefinition> fields
        ) {
            if (name == null || name.isBlank() || version < 1) {
                throw new SchemaException("Invalid schema identity");
            }

            this.name = name;
            this.version = version;
            this.fields = Map.copyOf(fields);
        }

        String name() {
            return name;
        }

        int version() {
            return version;
        }

        void validate(Map<String, Object> payload) {
            if (payload == null) {
                throw new SchemaException("Payload cannot be null");
            }

            for (String key : payload.keySet()) {
                if (!fields.containsKey(key)) {
                    throw new SchemaException(
                            "Unknown field: " + key
                    );
                }
            }

            for (var entry : fields.entrySet()) {
                String fieldName = entry.getKey();
                FieldDefinition definition = entry.getValue();

                Object value = payload.get(fieldName);

                if (value == null) {
                    if (definition.required()) {
                        throw new SchemaException(
                                "Missing field: " + fieldName
                        );
                    }
                    continue;
                }

                if (!definition.type().isInstance(value)) {
                    throw new SchemaException(
                            "Invalid type for " + fieldName
                    );
                }
            }
        }
    }

    // ========================================================
    // SCHEMA REGISTRY
    // ========================================================

    static final class SchemaRegistry {

        private final Map<String, EventSchema> schemas =
                new ConcurrentHashMap<>();

        void register(EventSchema schema) {
            String key = schema.name() + ":v" + schema.version();

            if (schemas.putIfAbsent(key, schema) != null) {
                throw new SchemaException(
                        "Schema already registered: " + key
                );
            }
        }

        void validate(
                String eventType,
                int version,
                Map<String, Object> payload
        ) {
            EventSchema schema = schemas.get(
                    eventType + ":v" + version
            );

            if (schema == null) {
                throw new SchemaException(
                        "Unknown schema: " + eventType
                );
            }

            schema.validate(payload);
        }
    }

    // ========================================================
    // EVENT DOMAIN MODEL
    // ========================================================

    record Event(
            UUID eventId,
            String eventType,
            int version,
            String producer,
            UUID correlationId,
            Map<String, Object> payload,
            Instant occurredAt
    ) {
        Event {
            Objects.requireNonNull(eventId);
            Objects.requireNonNull(eventType);
            Objects.requireNonNull(producer);
            Objects.requireNonNull(correlationId);
            Objects.requireNonNull(occurredAt);

            payload = Collections.unmodifiableMap(
                    new LinkedHashMap<>(payload)
            );
        }
    }

    record DeadLetter(
            Event event,
            String consumerName,
            int attempts,
            String error,
            Instant failedAt
    ) {}

    record DeliveryResult(
            String consumer,
            DeliveryStatus status,
            int attempts,
            String message
    ) {}

    // ========================================================
    // CONSUMER CONTRACT
    // ========================================================

    interface EventConsumer {
        void consume(Event event) throws Exception;
    }

    record Subscription(
            String consumerName,
            EventConsumer consumer,
            Predicate<Event> filter
    ) {
        Subscription {
            Objects.requireNonNull(consumerName);
            Objects.requireNonNull(consumer);
            Objects.requireNonNull(filter);
        }
    }

    // ========================================================
    // EVENT BROKER
    // ========================================================

    static final class EventBroker {

        private final SchemaRegistry registry;
        private final int maxRetries;

        private final Map<UUID, Event> events =
                new ConcurrentHashMap<>();

        private final Map<String, List<Subscription>> subscriptions =
                new ConcurrentHashMap<>();

        private final Set<String> processed =
                ConcurrentHashMap.newKeySet();

        private final List<DeadLetter> deadLetters =
                new CopyOnWriteArrayList<>();

        private volatile boolean closed;

        EventBroker(
                SchemaRegistry registry,
                int maxRetries
        ) {
            if (maxRetries < 0) {
                throw new IllegalArgumentException(
                        "Invalid retry configuration"
                );
            }

            this.registry = registry;
            this.maxRetries = maxRetries;
        }

        void subscribe(
                String eventType,
                Subscription subscription
        ) {
            ensureOpen();

            List<Subscription> list =
                    subscriptions.computeIfAbsent(
                            eventType,
                            ignored -> new CopyOnWriteArrayList<>()
                    );

            synchronized (list) {
                boolean duplicate = list.stream()
                        .anyMatch(existing ->
                                existing.consumerName().equals(
                                        subscription.consumerName()
                                )
                        );

                if (duplicate) {
                    throw new EventException(
                            "Duplicate consumer subscription"
                    );
                }

                list.add(subscription);
            }
        }

        Event publish(
                String eventType,
                int version,
                String producer,
                UUID correlationId,
                Map<String, Object> payload
        ) {
            ensureOpen();

            if (
                    eventType == null ||
                    eventType.isBlank() ||
                    producer == null ||
                    producer.isBlank()
            ) {
                throw new EventException(
                        "Invalid event metadata"
                );
            }

            registry.validate(eventType, version, payload);

            Event event = new Event(
                    UUID.randomUUID(),
                    eventType,
                    version,
                    producer,
                    correlationId,
                    payload,
                    Instant.now()
            );

            if (events.putIfAbsent(event.eventId(), event) != null) {
                throw new DuplicateEventException(
                        "Duplicate event identifier"
                );
            }

            LOGGER.info(
                    "Published " + event.eventType()
                            + " " + event.eventId()
            );

            return event;
        }

        List<DeliveryResult> dispatch(UUID eventId) {
            ensureOpen();

            Event event = events.get(eventId);

            if (event == null) {
                throw new EventException("Event not found");
            }

            List<Subscription> subscribers =
                    subscriptions.getOrDefault(
                            event.eventType(),
                            List.of()
                    );

            List<CompletableFuture<DeliveryResult>> tasks =
                    new ArrayList<>();

            for (Subscription subscription : subscribers) {
                tasks.add(
                        CompletableFuture.supplyAsync(
                                () -> deliver(event, subscription)
                        )
                );
            }

            // Wait for every independent consumer.
            CompletableFuture.allOf(
                    tasks.toArray(CompletableFuture[]::new)
            ).join();

            return tasks.stream()
                    .map(CompletableFuture::join)
                    .toList();
        }

        private DeliveryResult deliver(
                Event event,
                Subscription subscription
        ) {
            String consumerName = subscription.consumerName();

            String key = event.eventId() + ":" + consumerName;

            if (processed.contains(key)) {
                return new DeliveryResult(
                        consumerName,
                        DeliveryStatus.ALREADY_PROCESSED,
                        0,
                        "Previously consumed"
                );
            }

            if (!subscription.filter().test(event)) {
                return new DeliveryResult(
                        consumerName,
                        DeliveryStatus.FILTERED,
                        0,
                        "Event excluded by consumer filter"
                );
            }

            int attempts = 0;
            Exception lastError = null;

            for (int i = 0; i <= maxRetries; i++) {
                attempts++;

                try {
                    subscription.consumer().consume(event);

                    // Atomic set insertion protects duplicate delivery.
                    processed.add(key);

                    return new DeliveryResult(
                            consumerName,
                            DeliveryStatus.CONSUMED,
                            attempts,
                            "Successfully consumed"
                    );

                } catch (Exception exception) {
                    lastError = exception;

                    LOGGER.log(
                            Level.WARNING,
                            "Consumer failure: " + consumerName,
                            exception
                    );
                }
            }

            DeadLetter deadLetter = new DeadLetter(
                    event,
                    consumerName,
                    attempts,
                    lastError == null
                            ? "Unknown failure"
                            : lastError.getMessage(),
                    Instant.now()
            );

            deadLetters.add(deadLetter);

            return new DeliveryResult(
                    consumerName,
                    DeliveryStatus.DEAD_LETTER,
                    attempts,
                    deadLetter.error()
            );
        }

        DeliveryResult replay(
                UUID eventId,
                String consumerName
        ) {
            Event event = events.get(eventId);

            if (event == null) {
                throw new EventException("Event not found");
            }

            Subscription subscription =
                    subscriptions.getOrDefault(
                            event.eventType(),
                            List.of()
                    ).stream()
                    .filter(item ->
                            item.consumerName().equals(consumerName)
                    )
                    .findFirst()
                    .orElseThrow(() ->
                            new EventException("Consumer not found")
                    );

            processed.remove(eventId + ":" + consumerName);

            return deliver(event, subscription);
        }

        Map<String, Long> metrics() {
            Map<String, Long> result = new LinkedHashMap<>();

            result.put("published", (long) events.size());
            result.put("processed", (long) processed.size());
            result.put("deadLetters", (long) deadLetters.size());

            result.put(
                    "subscribers",
                    subscriptions.values().stream()
                            .mapToLong(List::size)
                            .sum()
            );

            return Map.copyOf(result);
        }

        List<DeadLetter> deadLetters() {
            return List.copyOf(deadLetters);
        }

        private void ensureOpen() {
            if (closed) {
                throw new EventException("Broker is closed");
            }
        }

        void close() {
            closed = true;
        }
    }

    // ========================================================
    // BUSINESS SERVICES
    // ========================================================

    static final class OrderProducer {

        private final EventBroker broker;

        OrderProducer(EventBroker broker) {
            this.broker = broker;
        }

        Event createOrder(
                String orderId,
                String customerId,
                double amount
        ) {
            if (
                    orderId == null ||
                    orderId.isBlank() ||
                    customerId == null ||
                    customerId.isBlank() ||
                    !Double.isFinite(amount) ||
                    amount <= 0
            ) {
                throw new EventException(
                        "Invalid order details"
                );
            }

            return broker.publish(
                    "OrderCreated",
                    1,
                    "OrderService",
                    UUID.randomUUID(),
                    Map.of(
                            "orderId", orderId,
                            "customerId", customerId,
                            "amount", amount
                    )
            );
        }
    }

    static final class InventoryService implements EventConsumer {

        private final Set<String> reservations =
                ConcurrentHashMap.newKeySet();

        @Override
        public void consume(Event event) {
            String orderId = (String) event.payload().get("orderId");

            reservations.add(orderId);
        }

        int reservationCount() {
            return reservations.size();
        }
    }

    static final class PaymentService implements EventConsumer {

        private final Map<String, Double> payments =
                new ConcurrentHashMap<>();

        @Override
        public void consume(Event event) {
            String orderId = (String) event.payload().get("orderId");

            double amount = (Double) event.payload().get("amount");

            payments.putIfAbsent(orderId, amount);
        }

        int paymentCount() {
            return payments.size();
        }
    }

    static final class NotificationService implements EventConsumer {

        private final List<String> messages =
                new CopyOnWriteArrayList<>();

        @Override
        public void consume(Event event) {
            messages.add(
                    "Order created: " +
                    event.payload().get("orderId")
            );
        }

        int notificationCount() {
            return messages.size();
        }
    }

    // ========================================================
    // APPLICATION
    // ========================================================

    public static void main(String[] args) {

        SchemaRegistry registry = new SchemaRegistry();

        Map<String, FieldDefinition> orderFields = Map.of(
                "orderId",
                new FieldDefinition(String.class, true),

                "customerId",
                new FieldDefinition(String.class, true),

                "amount",
                new FieldDefinition(Double.class, true)
        );

        registry.register(
                new EventSchema(
                        "OrderCreated",
                        1,
                        orderFields
                )
        );

        EventBroker broker = new EventBroker(
                registry,
                2
        );

        InventoryService inventory = new InventoryService();
        PaymentService payments = new PaymentService();
        NotificationService notifications =
                new NotificationService();

        broker.subscribe(
                "OrderCreated",
                new Subscription(
                        "InventoryService",
                        inventory,
                        event -> true
                )
        );

        broker.subscribe(
                "OrderCreated",
                new Subscription(
                        "PaymentService",
                        payments,
                        event -> true
                )
        );

        broker.subscribe(
                "OrderCreated",
                new Subscription(
                        "NotificationService",
                        notifications,
                        event -> true
                )
        );

        broker.subscribe(
                "OrderCreated",
                new Subscription(
                        "LargeOrderMonitor",
                        event -> LOGGER.info(
                                "Large order detected"
                        ),
                        event -> (Double) event.payload()
                                .get("amount") >= 10000
                )
        );

        // Simulate an unavailable downstream service.
        broker.subscribe(
                "OrderCreated",
                new Subscription(
                        "UnhealthyService",
                        event -> {
                            throw new EventException(
                                    "Downstream service unavailable"
                            );
                        },
                        event -> true
                )
        );

        OrderProducer producer = new OrderProducer(broker);

        Event event = producer.createOrder(
                "ORD-3001",
                "CUST-501",
                15000.50
        );

        System.out.println("\nFIRST DELIVERY");

        List<DeliveryResult> results =
                broker.dispatch(event.eventId());

        results.forEach(System.out::println);

        System.out.println("\nREPEATED DELIVERY");

        broker.dispatch(event.eventId())
                .forEach(System.out::println);

        // Invalid schema payload.
        try {
            broker.publish(
                    "OrderCreated",
                    1,
                    "OrderService",
                    UUID.randomUUID(),
                    Map.of("orderId", "INVALID")
            );
        } catch (SchemaException exception) {
            System.out.println(
                    "VALIDATION REJECTED: " +
                    exception.getMessage()
            );
        }

        System.out.println("\nBUSINESS STATE");

        System.out.println(
                "Reservations: " + inventory.reservationCount()
        );

        System.out.println(
                "Payments: " + payments.paymentCount()
        );

        System.out.println(
                "Notifications: " + notifications.notificationCount()
        );

        System.out.println("\nBROKER METRICS");

        broker.metrics().forEach(
                (key, value) ->
                        System.out.println(key + ": " + value)
        );

        System.out.println("\nDEAD LETTERS");

        broker.deadLetters().forEach(
                System.out::println
        );

        broker.close();
    }
}
