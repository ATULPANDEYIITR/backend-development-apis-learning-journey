import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;
import java.util.stream.Collectors;

/*
 * MESSAGE QUEUE ENTERPRISE PROCESSING SYSTEM
 *
 * Java 17
 * No third-party dependencies.
 *
 * Features:
 * - Broker and queue declaration
 * - Producer and consumer services
 * - Delivery ownership
 * - Explicit acknowledgments
 * - Negative acknowledgments
 * - Exponential retry scheduling
 * - Dead-letter processing
 * - Visibility timeout recovery
 * - Idempotent business operations
 * - Operational metrics
 */

public class MessageQueueEnterprise {

    enum MessageStatus {
        READY,
        IN_FLIGHT,
        ACKNOWLEDGED,
        RETRY_PENDING,
        DEAD_LETTERED
    }

    enum ProcessingResult {
        SUCCESS,
        DUPLICATE
    }

    record QueueConfiguration(
        String name,
        int capacity,
        int maximumAttempts,
        Duration retryBaseDelay,
        Duration retryMaximumDelay,
        Duration visibilityTimeout
    ) {
        QueueConfiguration {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Queue name is required");
            }

            if (capacity < 1 || maximumAttempts < 1) {
                throw new IllegalArgumentException("Invalid queue limits");
            }

            Objects.requireNonNull(retryBaseDelay);
            Objects.requireNonNull(retryMaximumDelay);
            Objects.requireNonNull(visibilityTimeout);

            if (retryBaseDelay.isNegative()
                    || retryMaximumDelay.isNegative()
                    || visibilityTimeout.isZero()
                    || visibilityTimeout.isNegative()) {
                throw new IllegalArgumentException("Invalid duration");
            }
        }
    }

    record MessagePayload(
        String transactionId,
        double amount,
        String customerId
    ) {
        MessagePayload {
            if (transactionId == null || transactionId.isBlank()) {
                throw new IllegalArgumentException("Transaction ID required");
            }

            if (!Double.isFinite(amount) || amount <= 0) {
                throw new IllegalArgumentException("Invalid amount");
            }

            if (customerId == null || customerId.isBlank()) {
                throw new IllegalArgumentException("Customer ID required");
            }
        }
    }

    static final class Message {

        private final String id;
        private final String producerId;
        private final String routingKey;
        private final MessagePayload payload;
        private final Instant createdAt;
        private final int maximumAttempts;

        private MessageStatus status;
        private int attempts;
        private String consumerId;
        private String lastError;
        private Instant deliveredAt;
        private Instant availableAt;
        private Instant acknowledgedAt;

        Message(
            String producerId,
            String routingKey,
            MessagePayload payload,
            int maximumAttempts
        ) {
            if (producerId == null || producerId.isBlank()) {
                throw new IllegalArgumentException("Producer ID required");
            }

            if (routingKey == null || routingKey.isBlank()) {
                throw new IllegalArgumentException("Routing key required");
            }

            if (maximumAttempts < 1) {
                throw new IllegalArgumentException("Invalid attempt limit");
            }

            this.id = UUID.randomUUID().toString();
            this.producerId = producerId;
            this.routingKey = routingKey;
            this.payload = Objects.requireNonNull(payload);
            this.maximumAttempts = maximumAttempts;

            this.createdAt = Instant.now();
            this.availableAt = createdAt;
            this.status = MessageStatus.READY;
        }

        String id() {
            return id;
        }

        MessagePayload payload() {
            return payload;
        }

        MessageStatus status() {
            return status;
        }

        int attempts() {
            return attempts;
        }

        String lastError() {
            return lastError;
        }

        String consumerId() {
            return consumerId;
        }
    }

    record Delivery(
        String messageId,
        String consumerId,
        int attempt,
        Instant deliveredAt
    ) {}

    record QueueMetrics(
        long published,
        long delivered,
        long acknowledged,
        long retried,
        long failed,
        long rejected,
        long deadLettered
    ) {}

    record QueueSnapshot(
        String name,
        int ready,
        int inFlight,
        int retryWaiting,
        int completed,
        int deadLetters,
        QueueMetrics metrics
    ) {}

    static class QueueException extends RuntimeException {
        QueueException(String message) {
            super(message);
        }
    }

    static class AcknowledgmentException extends QueueException {
        AcknowledgmentException(String message) {
            super(message);
        }
    }

    static class MessageQueue {

        private final QueueConfiguration configuration;

        private final Deque<Message> ready = new ArrayDeque<>();

        private final Map<String, Message> inFlight =
            new HashMap<>();

        private final List<Message> retryWaiting =
            new ArrayList<>();

        private final List<Message> completed =
            new ArrayList<>();

        private final List<Message> deadLetters =
            new ArrayList<>();

        private final Set<String> knownIds = new HashSet<>();

        private final ReentrantLock lock = new ReentrantLock();

        private final AtomicLong published = new AtomicLong();
        private final AtomicLong delivered = new AtomicLong();
        private final AtomicLong acknowledged = new AtomicLong();
        private final AtomicLong retried = new AtomicLong();
        private final AtomicLong failed = new AtomicLong();
        private final AtomicLong rejected = new AtomicLong();
        private final AtomicLong deadLettered = new AtomicLong();

        MessageQueue(QueueConfiguration configuration) {
            this.configuration = Objects.requireNonNull(configuration);
        }

        String name() {
            return configuration.name();
        }

        private int currentSize() {
            return ready.size()
                + inFlight.size()
                + retryWaiting.size();
        }

        void publish(Message message) {
            Objects.requireNonNull(message);

            lock.lock();

            try {
                if (currentSize() >= configuration.capacity()) {
                    rejected.incrementAndGet();
                    throw new QueueException("Queue capacity exceeded");
                }

                if (!knownIds.add(message.id())) {
                    throw new QueueException("Duplicate message ID");
                }

                message.status = MessageStatus.READY;
                ready.addLast(message);
                published.incrementAndGet();

            } finally {
                lock.unlock();
            }
        }

        private void promoteRetries() {
            Instant now = Instant.now();

            List<Message> eligible = retryWaiting.stream()
                .filter(message -> !message.availableAt.isAfter(now))
                .toList();

            for (Message message : eligible) {
                retryWaiting.remove(message);
                message.status = MessageStatus.READY;
                ready.addLast(message);
            }
        }

        Optional<Delivery> receive(String consumerId) {
            if (consumerId == null || consumerId.isBlank()) {
                throw new IllegalArgumentException("Consumer ID required");
            }

            lock.lock();

            try {
                promoteRetries();

                Message message = ready.pollFirst();

                if (message == null) {
                    return Optional.empty();
                }

                message.status = MessageStatus.IN_FLIGHT;
                message.consumerId = consumerId;
                message.attempts++;
                message.deliveredAt = Instant.now();

                inFlight.put(message.id(), message);
                delivered.incrementAndGet();

                return Optional.of(
                    new Delivery(
                        message.id(),
                        consumerId,
                        message.attempts,
                        message.deliveredAt
                    )
                );

            } finally {
                lock.unlock();
            }
        }

        void acknowledge(String messageId, String consumerId) {
            lock.lock();

            try {
                Message message = inFlight.get(messageId);

                if (message == null) {
                    throw new QueueException("Message is not in flight");
                }

                if (!message.consumerId.equals(consumerId)) {
                    throw new AcknowledgmentException(
                        "Consumer does not own delivery"
                    );
                }

                inFlight.remove(messageId);

                message.status = MessageStatus.ACKNOWLEDGED;
                message.acknowledgedAt = Instant.now();
                message.consumerId = null;

                completed.add(message);
                acknowledged.incrementAndGet();

            } finally {
                lock.unlock();
            }
        }

        void reject(
            String messageId,
            String consumerId,
            String reason,
            boolean requeue
        ) {
            lock.lock();

            try {
                Message message = inFlight.get(messageId);

                if (message == null) {
                    throw new QueueException("Message is not in flight");
                }

                if (!message.consumerId.equals(consumerId)) {
                    throw new AcknowledgmentException(
                        "Consumer does not own delivery"
                    );
                }

                inFlight.remove(messageId);

                message.consumerId = null;
                message.lastError = reason;

                failed.incrementAndGet();

                if (requeue
                        && message.attempts < message.maximumAttempts) {

                    message.status = MessageStatus.RETRY_PENDING;

                    long exponent = Math.min(
                        message.attempts - 1,
                        30
                    );

                    long multiplier = 1L << exponent;

                    long delayMillis;

                    try {
                        delayMillis = Math.multiplyExact(
                            configuration.retryBaseDelay().toMillis(),
                            multiplier
                        );
                    } catch (ArithmeticException exception) {
                        delayMillis = Long.MAX_VALUE;
                    }

                    delayMillis = Math.min(
                        delayMillis,
                        configuration.retryMaximumDelay().toMillis()
                    );

                    message.availableAt = Instant.now().plusMillis(
                        delayMillis
                    );

                    retryWaiting.add(message);
                    retried.incrementAndGet();

                } else {
                    moveToDeadLetter(message);
                }

            } finally {
                lock.unlock();
            }
        }

        private void moveToDeadLetter(Message message) {
            message.status = MessageStatus.DEAD_LETTERED;
            deadLetters.add(message);
            deadLettered.incrementAndGet();
        }

        int recoverExpired() {
            lock.lock();

            try {
                Instant deadline = Instant.now().minus(
                    configuration.visibilityTimeout()
                );

                List<String> expired = inFlight.entrySet().stream()
                    .filter(entry ->
                        !entry.getValue().deliveredAt.isAfter(deadline)
                    )
                    .map(Map.Entry::getKey)
                    .collect(Collectors.toList());

                for (String id : expired) {
                    Message message = inFlight.remove(id);

                    message.consumerId = null;
                    message.lastError = "Visibility timeout exceeded";

                    if (message.attempts < message.maximumAttempts) {
                        message.status = MessageStatus.RETRY_PENDING;
                        message.availableAt = Instant.now();

                        retryWaiting.add(message);
                        retried.incrementAndGet();
                    } else {
                        moveToDeadLetter(message);
                    }
                }

                return expired.size();

            } finally {
                lock.unlock();
            }
        }

        QueueSnapshot snapshot() {
            lock.lock();

            try {
                QueueMetrics metrics = new QueueMetrics(
                    published.get(),
                    delivered.get(),
                    acknowledged.get(),
                    retried.get(),
                    failed.get(),
                    rejected.get(),
                    deadLettered.get()
                );

                return new QueueSnapshot(
                    name(),
                    ready.size(),
                    inFlight.size(),
                    retryWaiting.size(),
                    completed.size(),
                    deadLetters.size(),
                    metrics
                );

            } finally {
                lock.unlock();
            }
        }

        List<Message> deadLetterMessages() {
            lock.lock();

            try {
                return Collections.unmodifiableList(
                    new ArrayList<>(deadLetters)
                );

            } finally {
                lock.unlock();
            }
        }
    }

    static final class Broker {

        private final Map<String, MessageQueue> queues =
            new ConcurrentHashMap<>();

        MessageQueue declareQueue(QueueConfiguration configuration) {
            return queues.computeIfAbsent(
                configuration.name(),
                key -> new MessageQueue(configuration)
            );
        }

        MessageQueue getQueue(String name) {
            MessageQueue queue = queues.get(name);

            if (queue == null) {
                throw new QueueException("Unknown queue: " + name);
            }

            return queue;
        }

        List<QueueSnapshot> snapshots() {
            return queues.values()
                .stream()
                .map(MessageQueue::snapshot)
                .toList();
        }
    }

    static final class ProducerService {

        private final String producerId;
        private final Broker broker;

        ProducerService(String producerId, Broker broker) {
            this.producerId = Objects.requireNonNull(producerId);
            this.broker = Objects.requireNonNull(broker);

            if (producerId.isBlank()) {
                throw new IllegalArgumentException("Producer ID required");
            }
        }

        String send(
            String queueName,
            String routingKey,
            MessagePayload payload
        ) {
            Message message = new Message(
                producerId,
                routingKey,
                payload,
                broker.getQueue(queueName).configuration.maximumAttempts()
            );

            broker.getQueue(queueName).publish(message);

            return message.id();
        }
    }

    static final class IdempotencyService {

        private final Map<String, ProcessingResult> completed =
            new ConcurrentHashMap<>();

        ProcessingResult execute(
            String idempotencyKey,
            Runnable businessOperation
        ) {
            Objects.requireNonNull(idempotencyKey);

            if (idempotencyKey.isBlank()) {
                throw new IllegalArgumentException(
                    "Idempotency key required"
                );
            }

            synchronized (completed) {
                if (completed.containsKey(idempotencyKey)) {
                    return ProcessingResult.DUPLICATE;
                }

                // Record completion only after the operation succeeds.
                businessOperation.run();

                completed.put(
                    idempotencyKey,
                    ProcessingResult.SUCCESS
                );

                return ProcessingResult.SUCCESS;
            }
        }
    }

    interface MessageHandler<T> {
        void handle(T payload) throws Exception;
    }

    static final class ConsumerService<T> {

        private final String consumerId;
        private final MessageQueue queue;
        private final MessageHandler<T> handler;

        ConsumerService(
            String consumerId,
            MessageQueue queue,
            MessageHandler<T> handler
        ) {
            this.consumerId = Objects.requireNonNull(consumerId);
            this.queue = Objects.requireNonNull(queue);
            this.handler = Objects.requireNonNull(handler);
        }

        void consumeOne(
            java.util.function.Function<MessagePayload, T> mapper
        ) {
            Optional<Delivery> optionalDelivery = queue.receive(consumerId);

            if (optionalDelivery.isEmpty()) {
                return;
            }

            Delivery delivery = optionalDelivery.get();

            // The queue owns the message. A production implementation
            // would expose a delivery object containing the payload.
            try {
                throw new UnsupportedOperationException(
                    "Use PaymentConsumerService for typed payment deliveries"
                );

            } catch (Exception exception) {
                queue.reject(
                    delivery.messageId(),
                    consumerId,
                    exception.getMessage(),
                    false
                );
            }
        }
    }

    static final class PaymentConsumerService {

        private final String consumerId;
        private final MessageQueue queue;
        private final IdempotencyService idempotency;

        private final List<String> processedTransactions =
            new ArrayList<>();

        PaymentConsumerService(
            String consumerId,
            MessageQueue queue,
            IdempotencyService idempotency
        ) {
            this.consumerId = Objects.requireNonNull(consumerId);
            this.queue = Objects.requireNonNull(queue);
            this.idempotency = Objects.requireNonNull(idempotency);
        }

        void consumeOne() {
            Optional<Delivery> optional = queue.receive(consumerId);

            if (optional.isEmpty()) {
                return;
            }

            Delivery delivery = optional.get();

            try {
                // Retrieve payload through the queue's controlled delivery API.
                MessagePayload payload = queuePayload(delivery.messageId());

                idempotency.execute(
                    payload.transactionId(),
                    () -> {
                        processedTransactions.add(
                            payload.transactionId()
                        );

                        System.out.println(
                            "Payment processed: "
                                + payload.transactionId()
                                + " amount=" + payload.amount()
                        );
                    }
                );

                queue.acknowledge(
                    delivery.messageId(),
                    consumerId
                );

            } catch (Exception exception) {
                queue.reject(
                    delivery.messageId(),
                    consumerId,
                    exception.getMessage(),
                    true
                );
            }
        }

        private MessagePayload queuePayload(String messageId) {
            return queue.getPayloadForConsumer(messageId, consumerId);
        }

        List<String> processedTransactions() {
            return List.copyOf(processedTransactions);
        }
    }

    public static void main(String[] args) {

        Broker broker = new Broker();

        QueueConfiguration configuration = new QueueConfiguration(
            "payments",
            100,
            3,
            Duration.ofMillis(10),
            Duration.ofMillis(100),
            Duration.ofSeconds(30)
        );

        MessageQueue queue = broker.declareQueue(configuration);

        ProducerService producer = new ProducerService(
            "payment-api",
            broker
        );

        IdempotencyService idempotency = new IdempotencyService();

        PaymentConsumerService consumer = new PaymentConsumerService(
            "payment-worker-01",
            queue,
            idempotency
        );

        producer.send(
            "payments",
            "payment.created",
            new MessagePayload(
                "TX-1001",
                2500,
                "CUSTOMER-01"
            )
        );

        producer.send(
            "payments",
            "payment.created",
            new MessagePayload(
                "TX-1002",
                5000,
                "CUSTOMER-02"
            )
        );

        consumer.consumeOne();
        consumer.consumeOne();

        System.out.println("\nQUEUE REPORT");

        for (QueueSnapshot snapshot : broker.snapshots()) {
            System.out.println(snapshot);
        }

        System.out.println("\nPROCESSED TRANSACTIONS");

        consumer.processedTransactions().forEach(
            System.out::println
        );
    }
}
