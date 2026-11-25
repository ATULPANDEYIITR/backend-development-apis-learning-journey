import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;

/*
 * Enterprise WebSocket Connection Management System
 *
 * Java 17 implementation.
 *
 * Features:
 * - Typed connection domain model
 * - Explicit lifecycle transitions
 * - Authentication and authorization
 * - Session management
 * - Connection policies
 * - Message validation
 * - Backpressure
 * - Heartbeat monitoring
 * - Asynchronous event processing
 * - Reconnection management
 * - Metrics
 * - Graceful resource shutdown
 *
 * The application demonstrates connection-management services.
 * Actual network framing and HTTP upgrade are provided by the
 * Java WebSocket transport API in production deployments.
 */

public class WebSocketEnterprise {

    enum ConnectionState {
        CONNECTING,
        OPEN,
        RECONNECTING,
        CLOSING,
        CLOSED,
        FAILED
    }

    enum MessageType {
        TEXT,
        BINARY,
        PING,
        PONG,
        CLOSE
    }

    enum CloseCode {
        NORMAL(1000),
        GOING_AWAY(1001),
        PROTOCOL_ERROR(1002),
        POLICY_VIOLATION(1008),
        MESSAGE_TOO_BIG(1009),
        INTERNAL_ERROR(1011);

        private final int value;

        CloseCode(int value) {
            this.value = value;
        }

        public int value() {
            return value;
        }
    }

    record ConnectionIdentity(
        String connectionId,
        String userId,
        String tenantId,
        String sessionId
    ) {
        ConnectionIdentity {
            requireText(connectionId, "connectionId");
            requireText(userId, "userId");
            requireText(tenantId, "tenantId");
            requireText(sessionId, "sessionId");
        }
    }

    record WebSocketMessage(
        long sequence,
        MessageType type,
        String payload,
        Instant createdAt
    ) {
        WebSocketMessage {
            Objects.requireNonNull(type);
            Objects.requireNonNull(payload);
            Objects.requireNonNull(createdAt);
        }
    }

    record ConnectionPolicy(
        int maximumMessageBytes,
        int maximumQueuedMessages,
        long maximumQueuedBytes,
        Duration idleTimeout,
        Duration heartbeatInterval,
        int maximumMissedHeartbeats,
        int maximumReconnectAttempts
    ) {
        ConnectionPolicy {
            if (
                maximumMessageBytes <= 0 ||
                maximumQueuedMessages <= 0 ||
                maximumQueuedBytes <= 0 ||
                maximumMissedHeartbeats <= 0 ||
                maximumReconnectAttempts < 0
            ) {
                throw new IllegalArgumentException(
                    "Invalid connection policy limits"
                );
            }

            requirePositive(idleTimeout, "idleTimeout");
            requirePositive(heartbeatInterval, "heartbeatInterval");
        }

        static ConnectionPolicy standard() {
            return new ConnectionPolicy(
                1024 * 1024,
                100,
                4 * 1024 * 1024,
                Duration.ofSeconds(60),
                Duration.ofSeconds(20),
                2,
                5
            );
        }
    }

    record ConnectionSnapshot(
        ConnectionIdentity identity,
        ConnectionState state,
        Instant connectedAt,
        Instant lastActivity,
        long messagesReceived,
        long messagesSent,
        long bytesReceived,
        long bytesSent,
        int queuedMessages,
        long queuedBytes,
        int missedHeartbeats
    ) {}

    static final class ConnectionException
            extends RuntimeException {

        ConnectionException(String message) {
            super(message);
        }
    }

    static final class PolicyViolationException
            extends RuntimeException {

        PolicyViolationException(String message) {
            super(message);
        }
    }

    static final class ConnectionMetrics {

        private final AtomicLong received = new AtomicLong();
        private final AtomicLong sent = new AtomicLong();
        private final AtomicLong bytesReceived = new AtomicLong();
        private final AtomicLong bytesSent = new AtomicLong();
        private final AtomicLong failures = new AtomicLong();
        private final AtomicLong reconnections = new AtomicLong();

        void received(long bytes) {
            received.incrementAndGet();
            bytesReceived.addAndGet(bytes);
        }

        void sent(long bytes) {
            sent.incrementAndGet();
            bytesSent.addAndGet(bytes);
        }

        void failure() {
            failures.incrementAndGet();
        }

        void reconnected() {
            reconnections.incrementAndGet();
        }

        void report() {
            System.out.println("Messages received: " + received.get());
            System.out.println("Messages sent: " + sent.get());
            System.out.println("Bytes received: " + bytesReceived.get());
            System.out.println("Bytes sent: " + bytesSent.get());
            System.out.println("Failures: " + failures.get());
            System.out.println("Reconnections: " + reconnections.get());
        }
    }

    static final class ManagedConnection {

        private static final Map<ConnectionState, Set<ConnectionState>>
            TRANSITIONS = createTransitions();

        private final ConnectionIdentity identity;
        private final ConnectionPolicy policy;
        private final ConnectionMetrics metrics;

        private final ArrayDeque<WebSocketMessage> outboundQueue =
            new ArrayDeque<>();

        private ConnectionState state = ConnectionState.CONNECTING;

        private final Instant connectedAt = Instant.now();

        private Instant lastActivity = connectedAt;
        private Instant lastHeartbeat = connectedAt;

        private long queuedBytes;
        private long nextSequence = 1;

        private int missedHeartbeats;
        private int reconnectAttempts;

        private boolean authenticated;

        ManagedConnection(
            ConnectionIdentity identity,
            ConnectionPolicy policy,
            ConnectionMetrics metrics
        ) {
            this.identity = Objects.requireNonNull(identity);
            this.policy = Objects.requireNonNull(policy);
            this.metrics = Objects.requireNonNull(metrics);
        }

        private static Map<ConnectionState, Set<ConnectionState>>
        createTransitions() {

            Map<ConnectionState, Set<ConnectionState>> map =
                new EnumMap<>(ConnectionState.class);

            map.put(
                ConnectionState.CONNECTING,
                Set.of(
                    ConnectionState.OPEN,
                    ConnectionState.FAILED,
                    ConnectionState.CLOSED
                )
            );

            map.put(
                ConnectionState.OPEN,
                Set.of(
                    ConnectionState.RECONNECTING,
                    ConnectionState.CLOSING,
                    ConnectionState.FAILED
                )
            );

            map.put(
                ConnectionState.RECONNECTING,
                Set.of(
                    ConnectionState.CONNECTING,
                    ConnectionState.CLOSING,
                    ConnectionState.FAILED
                )
            );

            map.put(
                ConnectionState.CLOSING,
                Set.of(
                    ConnectionState.CLOSED,
                    ConnectionState.FAILED
                )
            );

            map.put(
                ConnectionState.FAILED,
                Set.of(ConnectionState.CLOSED)
            );

            map.put(
                ConnectionState.CLOSED,
                Set.of()
            );

            return Collections.unmodifiableMap(map);
        }

        private synchronized void transition(
            ConnectionState next
        ) {

            if (!TRANSITIONS.get(state).contains(next)) {
                throw new ConnectionException(
                    "Invalid lifecycle transition: " +
                    state + " -> " + next
                );
            }

            state = next;
        }

        synchronized void authenticate(boolean valid) {

            if (state != ConnectionState.CONNECTING) {
                throw new ConnectionException(
                    "Authentication requires a connecting session"
                );
            }

            if (!valid) {
                transition(ConnectionState.FAILED);
                metrics.failure();

                throw new PolicyViolationException(
                    "Connection authentication rejected"
                );
            }

            authenticated = true;

            transition(ConnectionState.OPEN);

            lastActivity = Instant.now();
        }

        synchronized void send(
            MessageType type,
            String payload
        ) {

            requireText(payload, "payload");

            if (state != ConnectionState.OPEN) {
                throw new ConnectionException(
                    "Connection is not open"
                );
            }

            if (!authenticated) {
                throw new PolicyViolationException(
                    "Unauthenticated connection"
                );
            }

            if (
                type == MessageType.PING ||
                type == MessageType.PONG ||
                type == MessageType.CLOSE
            ) {
                throw new IllegalArgumentException(
                    "Use dedicated control-frame operations"
                );
            }

            long bytes = payload.getBytes(
                java.nio.charset.StandardCharsets.UTF_8
            ).length;

            if (bytes > policy.maximumMessageBytes()) {
                metrics.failure();

                throw new PolicyViolationException(
                    "Message exceeds size limit"
                );
            }

            if (
                outboundQueue.size() >=
                policy.maximumQueuedMessages()
            ) {
                throw new PolicyViolationException(
                    "Outbound message queue is full"
                );
            }

            if (
                bytes >
                policy.maximumQueuedBytes() - queuedBytes
            ) {
                throw new PolicyViolationException(
                    "Outbound byte capacity exceeded"
                );
            }

            outboundQueue.addLast(
                new WebSocketMessage(
                    nextSequence++,
                    type,
                    payload,
                    Instant.now()
                )
            );

            queuedBytes += bytes;

            lastActivity = Instant.now();
        }

        synchronized Optional<WebSocketMessage> pollMessage() {

            WebSocketMessage message = outboundQueue.pollFirst();

            if (message == null) {
                return Optional.empty();
            }

            long bytes = message.payload().getBytes(
                java.nio.charset.StandardCharsets.UTF_8
            ).length;

            queuedBytes -= bytes;

            metrics.sent(bytes);

            return Optional.of(message);
        }

        synchronized void receive(
            MessageType type,
            String payload
        ) {

            if (state != ConnectionState.OPEN) {
                throw new ConnectionException(
                    "Cannot receive on a closed connection"
                );
            }

            long bytes = payload.getBytes(
                java.nio.charset.StandardCharsets.UTF_8
            ).length;

            if (bytes > policy.maximumMessageBytes()) {
                metrics.failure();

                throw new PolicyViolationException(
                    "Incoming message too large"
                );
            }

            if (
                type == MessageType.CLOSE ||
                type == MessageType.PING
            ) {
                throw new IllegalArgumentException(
                    "Control frames need dedicated handlers"
                );
            }

            if (type == MessageType.PONG) {
                acknowledgeHeartbeat();
                return;
            }

            metrics.received(bytes);

            lastActivity = Instant.now();
        }

        synchronized void acknowledgeHeartbeat() {
            missedHeartbeats = 0;
            lastActivity = Instant.now();
        }

        synchronized boolean checkHeartbeat() {

            if (state != ConnectionState.OPEN) {
                return false;
            }

            Instant now = Instant.now();

            if (
                Duration.between(
                    lastHeartbeat,
                    now
                ).compareTo(policy.heartbeatInterval()) >= 0
            ) {

                missedHeartbeats++;

                lastHeartbeat = now;

                if (
                    missedHeartbeats >
                    policy.maximumMissedHeartbeats()
                ) {
                    fail("Heartbeat threshold exceeded");
                    return false;
                }

                return true;
            }

            return false;
        }

        synchronized boolean checkIdleTimeout() {

            if (state != ConnectionState.OPEN) {
                return false;
            }

            boolean expired =
                Duration.between(
                    lastActivity,
                    Instant.now()
                ).compareTo(policy.idleTimeout()) > 0;

            if (expired) {
                fail("Idle timeout");
            }

            return expired;
        }

        synchronized void reconnect() {

            if (
                state != ConnectionState.RECONNECTING &&
                state != ConnectionState.FAILED
            ) {
                throw new ConnectionException(
                    "Connection is not eligible for reconnection"
                );
            }

            if (
                reconnectAttempts >=
                policy.maximumReconnectAttempts()
            ) {
                throw new ConnectionException(
                    "Maximum reconnection attempts reached"
                );
            }

            reconnectAttempts++;

            if (state == ConnectionState.FAILED) {
                transition(ConnectionState.CLOSED);

                throw new ConnectionException(
                    "Failed sessions require a new connection identity"
                );
            }

            transition(ConnectionState.CONNECTING);

            authenticated = false;

            metrics.reconnected();
        }

        synchronized void beginClose() {

            if (state == ConnectionState.OPEN ||
                state == ConnectionState.RECONNECTING) {
                transition(ConnectionState.CLOSING);
            } else {
                throw new ConnectionException(
                    "Connection cannot enter closing state"
                );
            }
        }

        synchronized void completeClose() {

            if (
                state != ConnectionState.CLOSING &&
                state != ConnectionState.FAILED
            ) {
                throw new ConnectionException(
                    "Connection is not eligible for closure"
                );
            }

            outboundQueue.clear();
            queuedBytes = 0;

            transition(ConnectionState.CLOSED);
        }

        synchronized void fail(String reason) {

            if (
                state == ConnectionState.CLOSED ||
                state == ConnectionState.FAILED
            ) {
                return;
            }

            transition(ConnectionState.FAILED);

            outboundQueue.clear();
            queuedBytes = 0;

            metrics.failure();

            System.err.println(
                "Connection failed: " +
                identity.connectionId() +
                " | " + reason
            );
        }

        synchronized ConnectionSnapshot snapshot() {

            return new ConnectionSnapshot(
                identity,
                state,
                connectedAt,
                lastActivity,
                metrics.received.get(),
                metrics.sent.get(),
                metrics.bytesReceived.get(),
                metrics.bytesSent.get(),
                outboundQueue.size(),
                queuedBytes,
                missedHeartbeats
            );
        }

        synchronized boolean isOpen() {
            return state == ConnectionState.OPEN;
        }

        ConnectionIdentity identity() {
            return identity;
        }
    }

    interface ConnectionListener {
        void onEvent(String event, ConnectionSnapshot snapshot);
    }

    static final class ConnectionRegistry {

        private final Map<String, ManagedConnection> connections =
            new HashMap<>();

        private final Map<String, String> activeSessions =
            new HashMap<>();

        private final Map<String, ConnectionMetrics> metrics =
            new HashMap<>();

        private final List<ConnectionListener> listeners =
            new ArrayList<>();

        synchronized ManagedConnection register(
            ConnectionIdentity identity,
            ConnectionPolicy policy
        ) {

            if (connections.containsKey(identity.connectionId())) {
                throw new ConnectionException(
                    "Duplicate connection identifier"
                );
            }

            ConnectionMetrics connectionMetrics =
                new ConnectionMetrics();

            ManagedConnection connection = new ManagedConnection(
                identity,
                policy,
                connectionMetrics
            );

            connections.put(
                identity.connectionId(),
                connection
            );

            metrics.put(
                identity.connectionId(),
                connectionMetrics
            );

            publish("REGISTERED", connection);

            return connection;
        }

        synchronized void authenticate(
            String connectionId,
            boolean valid
        ) {

            ManagedConnection connection = requireConnection(
                connectionId
            );

            connection.authenticate(valid);

            activeSessions.put(
                connection.identity().userId(),
                connectionId
            );

            publish("CONNECTED", connection);
        }

        synchronized void replaceSession(
            String userId,
            String newConnectionId
        ) {

            ManagedConnection next = requireConnection(
                newConnectionId
            );

            if (!next.isOpen()) {
                throw new ConnectionException(
                    "Replacement session is not open"
                );
            }

            if (!next.identity().userId().equals(userId)) {
                throw new PolicyViolationException(
                    "User identity mismatch"
                );
            }

            String previousId = activeSessions.get(userId);

            if (previousId != null &&
                !previousId.equals(newConnectionId)) {

                ManagedConnection previous =
                    requireConnection(previousId);

                previous.beginClose();
                previous.completeClose();

                publish("REPLACED", previous);
            }

            activeSessions.put(userId, newConnectionId);

            publish("SESSION_REPLACED", next);
        }

        synchronized void sendToUser(
            String userId,
            String message
        ) {

            String connectionId = activeSessions.get(userId);

            if (connectionId == null) {
                throw new ConnectionException(
                    "No active session for user"
                );
            }

            ManagedConnection connection =
                requireConnection(connectionId);

            connection.send(MessageType.TEXT, message);
        }

        synchronized void broadcast(String message) {

            for (ManagedConnection connection :
                    connections.values()) {

                if (connection.isOpen()) {
                    connection.send(
                        MessageType.TEXT,
                        message
                    );
                }
            }
        }

        synchronized void close(String connectionId) {

            ManagedConnection connection =
                requireConnection(connectionId);

            connection.beginClose();
            connection.completeClose();

            activeSessions.remove(
                connection.identity().userId(),
                connectionId
            );

            publish("CLOSED", connection);
        }

        synchronized ManagedConnection requireConnection(
            String id
        ) {

            ManagedConnection connection = connections.get(id);

            if (connection == null) {
                throw new ConnectionException(
                    "Unknown connection: " + id
                );
            }

            return connection;
        }

        synchronized void addListener(ConnectionListener listener) {
            listeners.add(Objects.requireNonNull(listener));
        }

        private void publish(
            String event,
            ManagedConnection connection
        ) {

            ConnectionSnapshot snapshot = connection.snapshot();

            for (ConnectionListener listener : listeners) {
                listener.onEvent(event, snapshot);
            }
        }

        synchronized void report() {

            System.out.println("\nENTERPRISE CONNECTION REPORT");

            connections.values().forEach(connection -> {
                System.out.println(connection.snapshot());
            });

            System.out.println("\nMETRICS");

            metrics.forEach((id, metric) -> {
                System.out.println("Connection: " + id);
                metric.report();
            });

            System.out.println(
                "Active sessions: " + activeSessions.size()
            );
        }
    }

    static final class AsyncEventProcessor
            implements AutoCloseable {

        private final ExecutorService executor =
            Executors.newFixedThreadPool(2);

        CompletableFuture<Void> process(
            ManagedConnection connection,
            String payload,
            Consumer<String> handler
        ) {

            return CompletableFuture.runAsync(() -> {

                try {
                    connection.receive(
                        MessageType.TEXT,
                        payload
                    );

                    handler.accept(payload);

                } catch (RuntimeException error) {
                    throw new CompletionException(error);
                }

            }, executor);
        }

        @Override
        public void close() {

            executor.shutdown();

            try {
                if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                    executor.shutdownNow();
                }
            } catch (InterruptedException error) {
                executor.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }

    private static void requireText(
        String value,
        String field
    ) {

        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                field + " cannot be empty"
            );
        }
    }

    private static void requirePositive(
        Duration value,
        String field
    ) {

        Objects.requireNonNull(value, field);

        if (value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(
                field + " must be positive"
            );
        }
    }

    public static void main(String[] args) {

        ConnectionRegistry registry = new ConnectionRegistry();

        ConnectionPolicy policy = ConnectionPolicy.standard();

        registry.addListener((event, snapshot) -> {
            System.out.println(
                "EVENT " + event +
                " | " + snapshot.identity().connectionId() +
                " | " + snapshot.state()
            );
        });

        ConnectionIdentity alice = new ConnectionIdentity(
            "conn-1001",
            "alice",
            "tenant-finance",
            "session-001"
        );

        ConnectionIdentity bob = new ConnectionIdentity(
            "conn-1002",
            "bob",
            "tenant-finance",
            "session-002"
        );

        ManagedConnection aliceConnection =
            registry.register(alice, policy);

        ManagedConnection bobConnection =
            registry.register(bob, policy);

        registry.authenticate("conn-1001", true);
        registry.authenticate("conn-1002", true);

        registry.sendToUser(
            "alice",
            "Transaction processing completed"
        );

        registry.sendToUser(
            "bob",
            "Account notification received"
        );

        registry.broadcast(
            "Platform operational announcement"
        );

        try (AsyncEventProcessor processor =
                 new AsyncEventProcessor()) {

            processor.process(
                aliceConnection,
                "Client acknowledgement",
                message -> System.out.println(
                    "Processed asynchronously: " + message
                )
            ).join();
        }

        Optional<WebSocketMessage> outbound =
            aliceConnection.pollMessage();

        outbound.ifPresent(message -> {
            System.out.println(
                "Delivered message: " + message.payload()
            );
        });

        bobConnection.receive(
            MessageType.PONG,
            "heartbeat"
        );

        bobConnection.acknowledgeHeartbeat();

        // A new authenticated connection replaces the old user session.
        ConnectionIdentity replacementIdentity =
            new ConnectionIdentity(
                "conn-1003",
                "alice",
                "tenant-finance",
                "session-003"
            );

        registry.register(
            replacementIdentity,
            policy
        );

        registry.authenticate("conn-1003", true);

        registry.replaceSession(
            "alice",
            "conn-1003"
        );

        // Invalid payloads are rejected by policy enforcement.
        try {
            bobConnection.send(
                MessageType.TEXT,
                "x".repeat(2 * 1024 * 1024)
            );
        } catch (PolicyViolationException error) {
            System.out.println(
                "Expected policy rejection: " +
                error.getMessage()
            );
        }

        registry.report();

        registry.close("conn-1002");
        registry.close("conn-1003");

        System.out.println("\nAfter graceful shutdown:");

        registry.report();
    }
}
