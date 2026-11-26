import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/*
 * Server-Sent Events: Enterprise Streaming Service
 *
 * Java 17 implementation.
 *
 * Features:
 * - Immutable event records.
 * - Typed event categories.
 * - Publisher and subscriber interfaces.
 * - Replay history.
 * - Last-Event-ID support.
 * - Bounded subscriber queues.
 * - Subscription filters.
 * - Asynchronous publication.
 * - Connection state management.
 * - Authorization policies.
 * - Graceful disconnection.
 * - Operational metrics.
 *
 * This implementation provides the application service layer.
 * An HTTP adapter can expose its subscription queues through
 * text/event-stream responses.
 */

public class Main {

    enum EventType {
        MESSAGE,
        UPDATE,
        NOTIFICATION,
        PROGRESS,
        ERROR
    }

    enum ConnectionState {
        CONNECTED,
        DISCONNECTED,
        SLOW_CONSUMER
    }

    enum AuthorizationResult {
        ALLOWED,
        DENIED
    }

    record SSEEvent(
        long id,
        EventType type,
        String data,
        Instant timestamp
    ) {
        SSEEvent {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Event ID must be positive"
                );
            }

            Objects.requireNonNull(type);
            Objects.requireNonNull(data);
            Objects.requireNonNull(timestamp);
        }

        String encode() {
            return "id: " + id + "\n"
                + "event: " + type.name().toLowerCase() + "\n"
                + "data: " + data + "\n\n";
        }
    }

    record SubscriberIdentity(
        String subscriberId,
        String tenantId,
        Set<EventType> permittedTypes
    ) {
        SubscriberIdentity {
            if (subscriberId == null || subscriberId.isBlank()) {
                throw new IllegalArgumentException(
                    "Subscriber ID is required"
                );
            }

            if (tenantId == null || tenantId.isBlank()) {
                throw new IllegalArgumentException(
                    "Tenant ID is required"
                );
            }

            permittedTypes = permittedTypes.isEmpty()
                ? Collections.emptySet()
                : Collections.unmodifiableSet(
                    EnumSet.copyOf(permittedTypes)
                );
        }
    }

    record StreamingPolicy(
        int historyCapacity,
        int subscriberQueueCapacity,
        int maximumPayloadLength,
        int maximumSubscribers
    ) {
        StreamingPolicy {
            if (
                historyCapacity <= 0 ||
                subscriberQueueCapacity <= 0 ||
                maximumPayloadLength <= 0 ||
                maximumSubscribers <= 0
            ) {
                throw new IllegalArgumentException(
                    "Policy capacities must be positive"
                );
            }
        }
    }

    static class StreamingException extends RuntimeException {
        StreamingException(String message) {
            super(message);
        }
    }

    static class AuthorizationException
        extends StreamingException {

        AuthorizationException(String message) {
            super(message);
        }
    }

    interface EventPublisher {
        SSEEvent publish(EventType type, String data);
    }

    interface EventSubscriber {
        List<SSEEvent> reconnect(
            SubscriberIdentity identity,
            Long lastEventId
        );
    }

    static class AuthorizationService {

        AuthorizationResult evaluate(
            SubscriberIdentity identity,
            EventType type,
            String requestedTenant
        ) {

            if (!identity.tenantId().equals(requestedTenant)) {
                return AuthorizationResult.DENIED;
            }

            if (
                !identity.permittedTypes().isEmpty() &&
                !identity.permittedTypes().contains(type)
            ) {
                return AuthorizationResult.DENIED;
            }

            return AuthorizationResult.ALLOWED;
        }

        void requireAccess(
            SubscriberIdentity identity,
            EventType type,
            String tenant
        ) {

            if (
                evaluate(identity, type, tenant) ==
                AuthorizationResult.DENIED
            ) {
                throw new AuthorizationException(
                    "Subscriber is not authorized"
                );
            }
        }
    }

    static class EventHistory {

        private final ArrayDeque<SSEEvent> events =
            new ArrayDeque<>();

        private final int capacity;

        EventHistory(int capacity) {
            this.capacity = capacity;
        }

        synchronized void append(SSEEvent event) {
            events.addLast(event);

            while (events.size() > capacity) {
                events.removeFirst();
            }
        }

        synchronized List<SSEEvent> after(Long cursor) {

            List<SSEEvent> result = new ArrayList<>();

            if (cursor == null) {
                result.addAll(events);
                return result;
            }

            boolean found = false;

            for (SSEEvent event : events) {
                if (found) {
                    result.add(event);
                }

                if (event.id() == cursor) {
                    found = true;
                }
            }

            return result;
        }

        synchronized int size() {
            return events.size();
        }
    }

    static class SubscriberSession {

        private final SubscriberIdentity identity;

        private final BlockingQueue<SSEEvent> queue;

        private volatile ConnectionState state =
            ConnectionState.CONNECTED;

        private long lastDeliveredId;

        SubscriberSession(
            SubscriberIdentity identity,
            int queueCapacity
        ) {
            this.identity = identity;
            this.queue = new ArrayBlockingQueue<>(queueCapacity);
        }

        boolean offer(SSEEvent event) {

            if (state != ConnectionState.CONNECTED) {
                return false;
            }

            if (!queue.offer(event)) {
                state = ConnectionState.SLOW_CONSUMER;
                return false;
            }

            return true;
        }

        SSEEvent poll() {
            SSEEvent event = queue.poll();

            if (event != null) {
                lastDeliveredId = event.id();
            }

            return event;
        }

        List<SSEEvent> drain() {
            List<SSEEvent> result = new ArrayList<>();

            queue.drainTo(result);

            if (!result.isEmpty()) {
                lastDeliveredId =
                    result.get(result.size() - 1).id();
            }

            return result;
        }

        SubscriberIdentity identity() {
            return identity;
        }

        ConnectionState state() {
            return state;
        }

        long lastDeliveredId() {
            return lastDeliveredId;
        }

        void disconnect() {
            state = ConnectionState.DISCONNECTED;
            queue.clear();
        }
    }

    static class StreamingService
        implements EventPublisher, EventSubscriber {

        private final StreamingPolicy policy;

        private final EventHistory history;

        private final AuthorizationService authorization;

        private final AtomicLong sequence = new AtomicLong();

        private final Map<String, SubscriberSession> sessions =
            new HashMap<>();

        private final ReentrantReadWriteLock lock =
            new ReentrantReadWriteLock();

        private final AtomicLong publishedCount =
            new AtomicLong();

        private final AtomicLong rejectedCount =
            new AtomicLong();

        StreamingService(
            StreamingPolicy policy,
            AuthorizationService authorization
        ) {
            this.policy = policy;
            this.history = new EventHistory(policy.historyCapacity());
            this.authorization = authorization;
        }

        @Override
        public SSEEvent publish(EventType type, String data) {

            Objects.requireNonNull(type);

            if (data == null || data.isBlank()) {
                throw new IllegalArgumentException(
                    "Event data cannot be empty"
                );
            }

            if (data.length() > policy.maximumPayloadLength()) {
                throw new IllegalArgumentException(
                    "Event payload exceeds policy limit"
                );
            }

            long id = sequence.incrementAndGet();

            SSEEvent event = new SSEEvent(
                id,
                type,
                data,
                Instant.now()
            );

            /*
             * History is updated before subscriber notification.
             * A reconnecting subscriber can therefore recover events
             * published while its connection was unavailable.
             */
            history.append(event);

            lock.readLock().lock();

            try {
                for (SubscriberSession session : sessions.values()) {

                    authorization.requireAccess(
                        session.identity(),
                        event.type(),
                        session.identity().tenantId()
                    );

                    if (!session.offer(event)) {
                        rejectedCount.incrementAndGet();
                    }
                }
            } finally {
                lock.readLock().unlock();
            }

            publishedCount.incrementAndGet();

            return event;
        }

        SubscriberSession connect(
            SubscriberIdentity identity
        ) {

            lock.writeLock().lock();

            try {
                if (sessions.containsKey(identity.subscriberId())) {
                    throw new StreamingException(
                        "Subscriber is already connected"
                    );
                }

                if (sessions.size() >= policy.maximumSubscribers()) {
                    throw new StreamingException(
                        "Maximum subscriber capacity reached"
                    );
                }

                SubscriberSession session =
                    new SubscriberSession(
                        identity,
                        policy.subscriberQueueCapacity()
                    );

                sessions.put(identity.subscriberId(), session);

                return session;

            } finally {
                lock.writeLock().unlock();
            }
        }

        @Override
        public List<SSEEvent> reconnect(
            SubscriberIdentity identity,
            Long lastEventId
        ) {

            if (lastEventId != null && lastEventId < 0) {
                throw new IllegalArgumentException(
                    "Invalid Last-Event-ID"
                );
            }

            List<SSEEvent> events = history.after(lastEventId);

            List<SSEEvent> authorized = new ArrayList<>();

            for (SSEEvent event : events) {

                authorization.requireAccess(
                    identity,
                    event.type(),
                    identity.tenantId()
                );

                authorized.add(event);
            }

            return authorized;
        }

        void disconnect(String subscriberId) {

            lock.writeLock().lock();

            try {
                SubscriberSession session =
                    sessions.remove(subscriberId);

                if (session != null) {
                    session.disconnect();
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        CompletableFuture<SSEEvent> publishAsync(
            EventType type,
            String data
        ) {

            return CompletableFuture.supplyAsync(
                () -> publish(type, data)
            );
        }

        int subscriberCount() {
            lock.readLock().lock();

            try {
                return sessions.size();
            } finally {
                lock.readLock().unlock();
            }
        }

        long publishedCount() {
            return publishedCount.get();
        }

        long rejectedCount() {
            return rejectedCount.get();
        }

        int historySize() {
            return history.size();
        }

        String heartbeat() {
            return ": heartbeat\n\n";
        }
    }

    static class JobService {

        private final EventPublisher publisher;

        JobService(EventPublisher publisher) {
            this.publisher = publisher;
        }

        SSEEvent updateProgress(
            String tenantId,
            String jobId,
            int percentage,
            String status
        ) {

            if (jobId == null || jobId.isBlank()) {
                throw new IllegalArgumentException(
                    "Job ID is required"
                );
            }

            if (percentage < 0 || percentage > 100) {
                throw new IllegalArgumentException(
                    "Progress must be between 0 and 100"
                );
            }

            if (tenantId == null || tenantId.isBlank()) {
                throw new IllegalArgumentException(
                    "Tenant ID is required"
                );
            }

            String payload =
                "{\"tenant\":\"" + tenantId
                + "\",\"job\":\"" + jobId
                + "\",\"progress\":" + percentage
                + ",\"status\":\"" + status + "\"}";

            return publisher.publish(
                EventType.PROGRESS,
                payload
            );
        }
    }

    public static void main(String[] args) {

        StreamingPolicy policy = new StreamingPolicy(
            100,
            20,
            64000,
            500
        );

        AuthorizationService authorization =
            new AuthorizationService();

        StreamingService streamingService =
            new StreamingService(policy, authorization);

        SubscriberIdentity subscriber =
            new SubscriberIdentity(
                "browser-001",
                "tenant-A",
                EnumSet.of(
                    EventType.PROGRESS,
                    EventType.NOTIFICATION
                )
            );

        SubscriberSession session =
            streamingService.connect(subscriber);

        JobService jobService =
            new JobService(streamingService);

        SSEEvent first = jobService.updateProgress(
            "tenant-A",
            "job-100",
            25,
            "processing"
        );

        SSEEvent second = streamingService.publish(
            EventType.NOTIFICATION,
            "{\"message\":\"Processing started\"}"
        );

        SSEEvent third = jobService.updateProgress(
            "tenant-A",
            "job-100",
            100,
            "completed"
        );

        System.out.println("Streaming events:");

        for (SSEEvent event : session.drain()) {
            System.out.println(event.encode());
        }

        System.out.println("Reconnection replay:");

        List<SSEEvent> replay = streamingService.reconnect(
            subscriber,
            first.id()
        );

        for (SSEEvent event : replay) {
            System.out.println(event.encode());
        }

        System.out.println("Heartbeat:");
        System.out.println(streamingService.heartbeat());

        System.out.println("Operational metrics:");
        System.out.println(
            "Published: " + streamingService.publishedCount()
        );
        System.out.println(
            "Rejected: " + streamingService.rejectedCount()
        );
        System.out.println(
            "Subscribers: " + streamingService.subscriberCount()
        );
        System.out.println(
            "History: " + streamingService.historySize()
        );

        try {
            streamingService.reconnect(
                new SubscriberIdentity(
                    "unauthorized-browser",
                    "tenant-B",
                    EnumSet.of(EventType.PROGRESS)
                ),
                0L
            );

            throw new IllegalStateException(
                "Expected authorization failure"
            );

        } catch (AuthorizationException expected) {
            System.out.println(
                "Cross-tenant authorization correctly rejected."
            );
        }

        try {
            jobService.updateProgress(
                "tenant-A",
                "job-100",
                120,
                "processing"
            );

            throw new IllegalStateException(
                "Expected validation failure"
            );

        } catch (IllegalArgumentException expected) {
            System.out.println(
                "Invalid progress correctly rejected."
            );
        }

        streamingService.disconnect("browser-001");

        if (
            streamingService.subscriberCount() != 0 ||
            session.state() != ConnectionState.DISCONNECTED
        ) {
            throw new IllegalStateException(
                "Disconnection state is inconsistent"
            );
        }

        System.out.println("All enterprise streaming tests passed.");
    }
}
