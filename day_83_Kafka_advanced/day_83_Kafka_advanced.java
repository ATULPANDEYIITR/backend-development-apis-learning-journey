import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

public class KafkaAdvanced {

    enum BrokerStatus {
        ONLINE, OFFLINE
    }

    enum ConsumerStatus {
        JOINING, ACTIVE, FAILED, LEFT
    }

    enum RebalanceProtocol {
        EAGER, COOPERATIVE
    }

    enum Acknowledgement {
        LEADER_ONLY, ALL
    }

    static class KafkaException extends RuntimeException {
        KafkaException(String message) {
            super(message);
        }
    }

    static class ConfigurationException extends KafkaException {
        ConfigurationException(String message) {
            super(message);
        }
    }

    static class ReplicationException extends KafkaException {
        ReplicationException(String message) {
            super(message);
        }
    }

    static class OffsetException extends KafkaException {
        OffsetException(String message) {
            super(message);
        }
    }

    record PartitionKey(String topic, int partition) {
        PartitionKey {
            Objects.requireNonNull(topic);

            if (topic.isBlank() || partition < 0) {
                throw new ConfigurationException("Invalid partition key");
            }
        }

        @Override
        public String toString() {
            return topic + "-" + partition;
        }
    }

    record KafkaRecord(
        long offset,
        String key,
        String value,
        Instant timestamp,
        int size
    ) {
        KafkaRecord {
            Objects.requireNonNull(key);
            Objects.requireNonNull(value);
            Objects.requireNonNull(timestamp);

            if (key.isBlank() || offset < 0 || size < 0) {
                throw new ConfigurationException("Invalid record");
            }
        }
    }

    static final class Broker {
        private final int id;
        private BrokerStatus status = BrokerStatus.ONLINE;

        Broker(int id) {
            if (id <= 0) {
                throw new ConfigurationException("Invalid broker ID");
            }

            this.id = id;
        }

        int id() {
            return id;
        }

        BrokerStatus status() {
            return status;
        }
    }

    static final class KafkaPartition {
        private final PartitionKey key;
        private final List<Integer> replicas;
        private final Set<Integer> isr;
        private final List<KafkaRecord> log = new ArrayList<>();

        private int leader;
        private long nextOffset;
        private long logStartOffset;
        private long highWatermark;

        KafkaPartition(PartitionKey key, List<Integer> replicas) {
            if (replicas.isEmpty()) {
                throw new ConfigurationException("No replicas configured");
            }

            this.key = key;
            this.replicas = List.copyOf(replicas);
            this.leader = replicas.get(0);
            this.isr = new TreeSet<>(replicas);
        }

        synchronized KafkaRecord append(
            String recordKey,
            String value,
            Instant timestamp
        ) {
            if (recordKey == null || recordKey.isBlank() || value == null) {
                throw new ConfigurationException("Invalid record payload");
            }

            int size =
                recordKey.getBytes(StandardCharsets.UTF_8).length +
                value.getBytes(StandardCharsets.UTF_8).length;

            KafkaRecord record = new KafkaRecord(
                nextOffset++,
                recordKey,
                value,
                timestamp,
                size
            );

            log.add(record);
            return record;
        }

        synchronized void advanceHighWatermark(long offset) {
            if (offset < highWatermark || offset > nextOffset) {
                throw new OffsetException("Invalid high watermark");
            }

            highWatermark = offset;
        }

        synchronized List<KafkaRecord> read(long offset) {
            if (offset < logStartOffset || offset > highWatermark) {
                throw new OffsetException("Offset is outside readable range");
            }

            return log.stream()
                .filter(record ->
                    record.offset() >= offset &&
                    record.offset() < highWatermark
                )
                .toList();
        }

        synchronized int applyRetention(
            Duration retention,
            long maximumBytes,
            Instant now
        ) {
            if (
                retention == null &&
                maximumBytes < 0
            ) {
                throw new ConfigurationException("Invalid retention policy");
            }

            if (retention != null && retention.isNegative()) {
                throw new ConfigurationException("Negative retention duration");
            }

            if (maximumBytes < -1) {
                throw new ConfigurationException("Invalid size limit");
            }

            int original = log.size();

            if (retention != null) {
                Instant cutoff = now.minus(retention);

                log.removeIf(record -> record.timestamp().isBefore(cutoff));
            }

            if (maximumBytes >= 0) {
                List<KafkaRecord> retained = new ArrayList<>();
                long total = 0;

                for (int i = log.size() - 1; i >= 0; i--) {
                    KafkaRecord record = log.get(i);

                    if (record.size() > maximumBytes - total) {
                        break;
                    }

                    retained.add(record);
                    total += record.size();
                }

                java.util.Collections.reverse(retained);
                log.clear();
                log.addAll(retained);
            }

            if (log.size() != original) {
                logStartOffset = log.isEmpty()
                    ? nextOffset
                    : log.get(0).offset();
            }

            return original - log.size();
        }

        PartitionKey key() {
            return key;
        }

        List<Integer> replicas() {
            return replicas;
        }

        Set<Integer> isr() {
            return Set.copyOf(isr);
        }

        int leader() {
            return leader;
        }
    }

    static final class Consumer {
        private final String id;
        private final Set<String> subscriptions;
        private final Set<PartitionKey> assignments = new HashSet<>();

        private ConsumerStatus status = ConsumerStatus.JOINING;
        private Instant lastHeartbeat = Instant.now();

        Consumer(String id, Set<String> subscriptions) {
            if (id == null || id.isBlank() || subscriptions.isEmpty()) {
                throw new ConfigurationException("Invalid consumer");
            }

            this.id = id;
            this.subscriptions = Set.copyOf(subscriptions);
        }

        String id() {
            return id;
        }

        Set<PartitionKey> assignments() {
            return Set.copyOf(assignments);
        }
    }

    static final class ConsumerGroup {
        private final String id;
        private final Map<String, Consumer> consumers = new LinkedHashMap<>();
        private final Map<PartitionKey, Long> committedOffsets = new HashMap<>();

        private long generation;
        private boolean stable;

        ConsumerGroup(String id) {
            this.id = id;
        }

        void addConsumer(Consumer consumer) {
            if (consumers.putIfAbsent(consumer.id(), consumer) != null) {
                throw new ConfigurationException("Duplicate consumer");
            }

            stable = false;
        }

        boolean isStable() {
            return stable;
        }
    }

    static final class ReviewPolicy {
        private final int minimumApprovals;
        private final Set<String> eligibleReviewers;
        private final boolean approvalFromAuthorAllowed;

        ReviewPolicy(
            int minimumApprovals,
            Set<String> eligibleReviewers,
            boolean approvalFromAuthorAllowed
        ) {
            if (minimumApprovals < 0) {
                throw new ConfigurationException("Invalid approval count");
            }

            this.minimumApprovals = minimumApprovals;
            this.eligibleReviewers = Set.copyOf(eligibleReviewers);
            this.approvalFromAuthorAllowed = approvalFromAuthorAllowed;
        }

        boolean eligible(String reviewer, String author) {
            return eligibleReviewers.contains(reviewer) &&
                (approvalFromAuthorAllowed || !reviewer.equals(author));
        }

        int minimumApprovals() {
            return minimumApprovals;
        }
    }

    static final class KafkaCluster {
        private final Map<Integer, Broker> brokers = new HashMap<>();
        private final Map<String, List<KafkaPartition>> topics =
            new LinkedHashMap<>();
        private final Map<String, ConsumerGroup> groups = new HashMap<>();

        private final int minimumISR;
        private final AtomicLong producedRecords = new AtomicLong();

        KafkaCluster(int minimumISR) {
            if (minimumISR < 1) {
                throw new ConfigurationException("Minimum ISR must be positive");
            }

            this.minimumISR = minimumISR;
        }

        synchronized void addBroker(int id) {
            if (brokers.putIfAbsent(id, new Broker(id)) != null) {
                throw new ConfigurationException("Duplicate broker");
            }
        }

        synchronized void createTopic(
            String name,
            int partitionCount,
            int replicationFactor
        ) {
            if (
                name == null ||
                name.isBlank() ||
                topics.containsKey(name) ||
                partitionCount < 1 ||
                replicationFactor < 1
            ) {
                throw new ConfigurationException("Invalid topic configuration");
            }

            List<Integer> available = brokers.values().stream()
                .filter(b -> b.status() == BrokerStatus.ONLINE)
                .map(Broker::id)
                .sorted()
                .toList();

            if (replicationFactor > available.size()) {
                throw new ConfigurationException("Insufficient brokers");
            }

            List<KafkaPartition> partitions = new ArrayList<>();

            for (int p = 0; p < partitionCount; p++) {
                List<Integer> replicas = new ArrayList<>();

                for (int r = 0; r < replicationFactor; r++) {
                    replicas.add(available.get((p + r) % available.size()));
                }

                partitions.add(
                    new KafkaPartition(
                        new PartitionKey(name, p),
                        replicas
                    )
                );
            }

            topics.put(name, partitions);
        }

        KafkaPartition getPartition(PartitionKey key) {
            List<KafkaPartition> partitions = topics.get(key.topic());

            if (
                partitions == null ||
                key.partition() >= partitions.size()
            ) {
                throw new ConfigurationException("Unknown partition");
            }

            return partitions.get(key.partition());
        }

        synchronized KafkaRecord produce(
            PartitionKey key,
            String recordKey,
            String value,
            Acknowledgement acknowledgement
        ) {
            KafkaPartition partition = getPartition(key);
            Broker leader = brokers.get(partition.leader());

            if (leader == null || leader.status() != BrokerStatus.ONLINE) {
                throw new ReplicationException("Leader unavailable");
            }

            if (acknowledgement == Acknowledgement.ALL) {
                long onlineISR = partition.isr().stream()
                    .filter(id -> brokers.get(id).status() == BrokerStatus.ONLINE)
                    .count();

                if (onlineISR < minimumISR) {
                    throw new ReplicationException("Minimum ISR not satisfied");
                }
            }

            KafkaRecord record = partition.append(
                recordKey,
                value,
                Instant.now()
            );

            partition.advanceHighWatermark(record.offset() + 1);
            producedRecords.incrementAndGet();

            return record;
        }

        synchronized ConsumerGroup createGroup(String groupId) {
            if (groups.containsKey(groupId)) {
                throw new ConfigurationException("Consumer group exists");
            }

            ConsumerGroup group = new ConsumerGroup(groupId);
            groups.put(groupId, group);
            return group;
        }

        synchronized void join(
            String groupId,
            String consumerId,
            Set<String> subscriptions
        ) {
            ConsumerGroup group = Objects.requireNonNull(groups.get(groupId));

            for (String topic : subscriptions) {
                if (!topics.containsKey(topic)) {
                    throw new ConfigurationException("Unknown subscription");
                }
            }

            group.addConsumer(new Consumer(consumerId, subscriptions));
        }

        synchronized Map<String, Set<PartitionKey>> rebalance(
            String groupId,
            RebalanceProtocol protocol
        ) {
            ConsumerGroup group = Objects.requireNonNull(groups.get(groupId));

            List<Consumer> active = group.consumers.values().stream()
                .filter(c ->
                    c.status != ConsumerStatus.FAILED &&
                    c.status != ConsumerStatus.LEFT
                )
                .sorted(Comparator.comparing(Consumer::id))
                .toList();

            if (protocol == RebalanceProtocol.EAGER) {
                active.forEach(c -> c.assignments.clear());
            }

            Map<String, Set<PartitionKey>> desired = new LinkedHashMap<>();

            active.forEach(c -> desired.put(c.id(), new TreeSet<>(
                Comparator.comparing(PartitionKey::topic)
                    .thenComparingInt(PartitionKey::partition)
            )));

            for (var topicEntry : topics.entrySet()) {
                String topic = topicEntry.getKey();

                List<Consumer> subscribers = active.stream()
                    .filter(c -> c.subscriptions.contains(topic))
                    .toList();

                if (subscribers.isEmpty()) {
                    continue;
                }

                for (KafkaPartition partition : topicEntry.getValue()) {
                    Consumer owner = subscribers.get(
                        partition.key().partition() % subscribers.size()
                    );

                    desired.get(owner.id()).add(partition.key());
                }
            }

            for (Consumer consumer : active) {
                Set<PartitionKey> next = desired.get(consumer.id());

                if (protocol == RebalanceProtocol.COOPERATIVE) {
                    consumer.assignments.retainAll(next);
                }

                consumer.assignments.clear();
                consumer.assignments.addAll(next);
                consumer.status = ConsumerStatus.ACTIVE;
            }

            group.generation++;
            group.stable = true;

            return desired;
        }

        synchronized void heartbeat(String groupId, String consumerId) {
            Consumer consumer = groups.get(groupId).consumers.get(consumerId);

            if (consumer == null || consumer.status != ConsumerStatus.ACTIVE) {
                throw new KafkaException("Consumer is inactive");
            }

            consumer.lastHeartbeat = Instant.now();
        }

        synchronized List<String> detectFailures(
            String groupId,
            Duration timeout,
            Instant now
        ) {
            if (timeout.isNegative() || timeout.isZero()) {
                throw new ConfigurationException("Invalid timeout");
            }

            ConsumerGroup group = groups.get(groupId);
            List<String> failed = new ArrayList<>();

            for (Consumer consumer : group.consumers.values()) {
                if (
                    consumer.status == ConsumerStatus.ACTIVE &&
                    Duration.between(consumer.lastHeartbeat, now).compareTo(timeout) > 0
                ) {
                    consumer.status = ConsumerStatus.FAILED;
                    consumer.assignments.clear();
                    failed.add(consumer.id());
                }
            }

            if (!failed.isEmpty()) {
                group.stable = false;
            }

            return failed;
        }

        synchronized void commitOffset(
            String groupId,
            PartitionKey key,
            long nextOffset
        ) {
            ConsumerGroup group = groups.get(groupId);
            KafkaPartition partition = getPartition(key);

            if (
                nextOffset < partition.logStartOffset ||
                nextOffset > partition.highWatermark
            ) {
                throw new OffsetException("Commit outside valid offset range");
            }

            group.committedOffsets.put(key, nextOffset);
        }

        synchronized long fetchOffset(String groupId, PartitionKey key) {
            ConsumerGroup group = groups.get(groupId);
            KafkaPartition partition = getPartition(key);

            return group.committedOffsets.getOrDefault(
                key,
                partition.logStartOffset
            );
        }

        synchronized void failBroker(int brokerId) {
            Broker broker = brokers.get(brokerId);

            if (broker == null) {
                throw new ConfigurationException("Unknown broker");
            }

            broker.status = BrokerStatus.OFFLINE;

            for (List<KafkaPartition> partitions : topics.values()) {
                for (KafkaPartition partition : partitions) {
                    if (!partition.replicas().contains(brokerId)) {
                        continue;
                    }

                    partition.isr.remove(brokerId);

                    if (partition.leader == brokerId) {
                        Integer candidate = partition.isr.stream()
                            .filter(id ->
                                brokers.get(id).status() == BrokerStatus.ONLINE
                            )
                            .min(Integer::compareTo)
                            .orElse(null);

                        if (candidate == null) {
                            throw new ReplicationException(
                                "No available ISR leader"
                            );
                        }

                        partition.leader = candidate;
                    }
                }
            }
        }

        synchronized void restoreBroker(int brokerId) {
            Broker broker = brokers.get(brokerId);

            if (broker == null) {
                throw new ConfigurationException("Unknown broker");
            }

            broker.status = BrokerStatus.ONLINE;

            // Rejoining ISR requires replica catch-up and is not automatic.
        }

        synchronized void displayStatus() {
            for (List<KafkaPartition> partitions : topics.values()) {
                for (KafkaPartition partition : partitions) {
                    System.out.printf(
                        "%s | leader=%d | replicas=%s | ISR=%s%n",
                        partition.key(),
                        partition.leader(),
                        partition.replicas(),
                        partition.isr()
                    );
                }
            }
        }

        long producedCount() {
            return producedRecords.get();
        }
    }

    static void demonstrateEnterpriseWorkflow() {
        KafkaCluster cluster = new KafkaCluster(2);

        for (int id = 1; id <= 3; id++) {
            cluster.addBroker(id);
        }

        cluster.createTopic("audit-events", 6, 3);

        for (int i = 0; i < 6; i++) {
            cluster.produce(
                new PartitionKey("audit-events", i),
                "event-" + i,
                "{\"action\":\"login\",\"status\":\"success\"}",
                Acknowledgement.ALL
            );
        }

        cluster.createGroup("audit-analytics");

        cluster.join(
            "audit-analytics",
            "analytics-1",
            Set.of("audit-events")
        );

        cluster.join(
            "audit-analytics",
            "analytics-2",
            Set.of("audit-events")
        );

        Map<String, Set<PartitionKey>> assignments = cluster.rebalance(
            "audit-analytics",
            RebalanceProtocol.COOPERATIVE
        );

        System.out.println("Consumer group assignments:");

        assignments.forEach((consumer, partitions) ->
            System.out.println(consumer + " -> " + partitions)
        );

        PartitionKey key = new PartitionKey("audit-events", 0);

        cluster.commitOffset("audit-analytics", key, 1);

        System.out.println(
            "Recovered offset: " +
            cluster.fetchOffset("audit-analytics", key)
        );

        System.out.println("Produced records: " + cluster.producedCount());

        System.out.println("\nBroker failure simulation:");

        cluster.failBroker(1);
        cluster.displayStatus();

        cluster.restoreBroker(1);

        System.out.println("\nBroker restored; replica catch-up is required.");

        // Enterprise policy objects are separate from Kafka's
        // consumer-group assignment and replication mechanisms.
        ReviewPolicy operationalPolicy = new ReviewPolicy(
            2,
            Set.of("platform-admin", "reliability-engineer", "security-lead"),
            false
        );

        System.out.println(
            "Minimum eligible operational approvals: " +
            operationalPolicy.minimumApprovals()
        );
    }

    public static void main(String[] args) {
        try {
            demonstrateEnterpriseWorkflow();
        } catch (KafkaException exception) {
            System.err.println("Operational failure: " + exception.getMessage());
        } catch (Exception exception) {
            System.err.println("Unexpected failure: " + exception.getMessage());
            throw exception;
        }
    }
}
