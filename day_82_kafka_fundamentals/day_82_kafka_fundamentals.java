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

public class KafkaEnterpriseDemo {

    enum AckMode {
        LEADER,
        ALL
    }

    enum BrokerStatus {
        AVAILABLE,
        UNAVAILABLE
    }

    enum ProcessingStatus {
        PENDING,
        PROCESSING,
        PROCESSED,
        FAILED
    }

    static class KafkaException extends RuntimeException {
        KafkaException(String message) {
            super(message);
        }
    }

    static class ValidationException extends KafkaException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class OffsetException extends KafkaException {
        OffsetException(String message) {
            super(message);
        }
    }

    static class BrokerException extends KafkaException {
        BrokerException(String message) {
            super(message);
        }
    }

    record Message(
        String id,
        String key,
        String value,
        Instant timestamp
    ) {
        Message {
            Objects.requireNonNull(id);
            Objects.requireNonNull(value);
            Objects.requireNonNull(timestamp);

            if (value.isBlank()) {
                throw new ValidationException(
                    "Message value cannot be empty"
                );
            }
        }

        static Message create(String key, String value) {
            return new Message(
                UUID.randomUUID().toString(),
                key,
                value,
                Instant.now()
            );
        }
    }

    record ProduceResult(
        String topic,
        int partition,
        long offset,
        String messageId
    ) {}

    record Assignment(
        String topic,
        int partition
    ) {}

    record ConsumerRecord(
        String topic,
        int partition,
        long offset,
        Message message
    ) {}

    static final class Broker {
        private final int id;
        private BrokerStatus status;
        private final Set<Assignment> hostedPartitions =
            new HashSet<>();

        Broker(int id) {
            if (id < 1) {
                throw new ValidationException("Invalid broker ID");
            }

            this.id = id;
            this.status = BrokerStatus.AVAILABLE;
        }

        int getId() {
            return id;
        }

        boolean isAvailable() {
            return status == BrokerStatus.AVAILABLE;
        }

        void setStatus(BrokerStatus status) {
            this.status = Objects.requireNonNull(status);
        }

        void register(Assignment assignment) {
            hostedPartitions.add(assignment);
        }

        @Override
        public String toString() {
            return "Broker{" +
                "id=" + id +
                ", status=" + status +
                ", hostedPartitions=" + hostedPartitions.size() +
                '}';
        }
    }

    static final class Partition {
        private final int id;
        private final int leaderBroker;
        private final List<Integer> replicas;
        private final List<Message> log = new ArrayList<>();

        Partition(
            int id,
            int leaderBroker,
            List<Integer> replicas
        ) {
            this.id = id;
            this.leaderBroker = leaderBroker;
            this.replicas = List.copyOf(replicas);
        }

        int getId() {
            return id;
        }

        int getLeaderBroker() {
            return leaderBroker;
        }

        List<Integer> getReplicas() {
            return replicas;
        }

        synchronized long append(Message message) {
            long offset = log.size();
            log.add(message);
            return offset;
        }

        synchronized long nextOffset() {
            return log.size();
        }

        synchronized List<ConsumerRecord> read(
            String topic,
            long offset,
            int limit
        ) {
            if (offset < 0 || offset > log.size()) {
                throw new OffsetException("Invalid read offset");
            }

            if (limit < 1) {
                throw new ValidationException(
                    "Read limit must be positive"
                );
            }

            List<ConsumerRecord> result = new ArrayList<>();

            long end = Math.min(
                log.size(),
                offset + limit
            );

            for (long current = offset; current < end; current++) {
                result.add(
                    new ConsumerRecord(
                        topic,
                        id,
                        current,
                        log.get((int) current)
                    )
                );
            }

            return result;
        }
    }

    static final class Topic {
        private final String name;
        private final int replicationFactor;
        private final List<Partition> partitions;

        Topic(
            String name,
            int partitionCount,
            int replicationFactor,
            List<Integer> brokerIds
        ) {
            if (name == null || name.isBlank()) {
                throw new ValidationException(
                    "Topic name is required"
                );
            }

            if (partitionCount < 1) {
                throw new ValidationException(
                    "Partition count must be positive"
                );
            }

            if (
                replicationFactor < 1 ||
                replicationFactor > brokerIds.size()
            ) {
                throw new ValidationException(
                    "Invalid replication factor"
                );
            }

            this.name = name;
            this.replicationFactor = replicationFactor;
            this.partitions = new ArrayList<>();

            for (int i = 0; i < partitionCount; i++) {
                int leaderIndex = i % brokerIds.size();

                List<Integer> replicas = new ArrayList<>();

                for (int j = 0; j < replicationFactor; j++) {
                    replicas.add(
                        brokerIds.get(
                            (leaderIndex + j) % brokerIds.size()
                        )
                    );
                }

                partitions.add(
                    new Partition(
                        i,
                        replicas.get(0),
                        replicas
                    )
                );
            }
        }

        String getName() {
            return name;
        }

        int getReplicationFactor() {
            return replicationFactor;
        }

        List<Partition> getPartitions() {
            return Collections.unmodifiableList(partitions);
        }

        Partition getPartition(int id) {
            if (id < 0 || id >= partitions.size()) {
                throw new ValidationException("Invalid partition");
            }

            return partitions.get(id);
        }

        Partition selectPartition(String key) {
            int index = key == null
                ? 0
                : Math.floorMod(key.hashCode(), partitions.size());

            return partitions.get(index);
        }
    }

    static final class ReviewableProcessingPolicy {
        private final AckMode acknowledgment;
        private final boolean requireAllReplicas;
        private final int maximumBatchSize;

        ReviewableProcessingPolicy(
            AckMode acknowledgment,
            boolean requireAllReplicas,
            int maximumBatchSize
        ) {
            this.acknowledgment =
                Objects.requireNonNull(acknowledgment);

            this.requireAllReplicas = requireAllReplicas;

            if (maximumBatchSize < 1) {
                throw new ValidationException(
                    "Maximum batch size must be positive"
                );
            }

            this.maximumBatchSize = maximumBatchSize;
        }

        AckMode acknowledgment() {
            return acknowledgment;
        }

        boolean requireAllReplicas() {
            return requireAllReplicas;
        }

        int maximumBatchSize() {
            return maximumBatchSize;
        }
    }

    static final class ConsumerGroup {
        private final String groupId;

        private final Map<Assignment, Long> committedOffsets =
            new HashMap<>();

        private final Map<String, List<Assignment>> assignments =
            new LinkedHashMap<>();

        private long generation;

        ConsumerGroup(String groupId) {
            if (groupId == null || groupId.isBlank()) {
                throw new ValidationException(
                    "Consumer group ID is required"
                );
            }

            this.groupId = groupId;
        }

        String getGroupId() {
            return groupId;
        }

        long getGeneration() {
            return generation;
        }

        long committedOffset(Assignment assignment) {
            return committedOffsets.getOrDefault(assignment, 0L);
        }

        synchronized void commit(
            Assignment assignment,
            long nextOffset,
            long maximumOffset
        ) {
            if (
                nextOffset < 0 ||
                nextOffset > maximumOffset
            ) {
                throw new OffsetException(
                    "Commit offset exceeds log boundaries"
                );
            }

            long previous = committedOffset(assignment);

            if (nextOffset < previous) {
                throw new OffsetException(
                    "Offset regression is not allowed"
                );
            }

            committedOffsets.put(assignment, nextOffset);
        }

        synchronized void rebalance(
            String topic,
            List<String> consumerIds,
            int partitionCount
        ) {
            if (consumerIds == null || consumerIds.isEmpty()) {
                throw new ValidationException(
                    "At least one consumer is required"
                );
            }

            if (new HashSet<>(consumerIds).size() != consumerIds.size()) {
                throw new ValidationException(
                    "Consumer IDs must be unique"
                );
            }

            if (consumerIds.stream().anyMatch(
                id -> id == null || id.isBlank()
            )) {
                throw new ValidationException(
                    "Invalid consumer ID"
                );
            }

            assignments.clear();

            for (String consumerId : consumerIds) {
                assignments.put(
                    consumerId,
                    new ArrayList<>()
                );
            }

            for (int i = 0; i < partitionCount; i++) {
                String consumer = consumerIds.get(
                    i % consumerIds.size()
                );

                assignments.get(consumer).add(
                    new Assignment(topic, i)
                );
            }

            generation++;
        }

        Map<String, List<Assignment>> getAssignments() {
            Map<String, List<Assignment>> copy =
                new LinkedHashMap<>();

            assignments.forEach(
                (consumer, assigned) ->
                    copy.put(consumer, List.copyOf(assigned))
            );

            return Collections.unmodifiableMap(copy);
        }

        Map<Assignment, Long> getCommittedOffsets() {
            return Collections.unmodifiableMap(
                new HashMap<>(committedOffsets)
            );
        }
    }

    static final class KafkaCluster {
        private final Map<Integer, Broker> brokers =
            new LinkedHashMap<>();

        private final Map<String, Topic> topics =
            new LinkedHashMap<>();

        private final Map<String, ConsumerGroup> groups =
            new HashMap<>();

        private final ReviewableProcessingPolicy policy;

        KafkaCluster(
            int brokerCount,
            ReviewableProcessingPolicy policy
        ) {
            if (brokerCount < 1) {
                throw new ValidationException(
                    "At least one broker is required"
                );
            }

            this.policy = Objects.requireNonNull(policy);

            for (int i = 1; i <= brokerCount; i++) {
                brokers.put(i, new Broker(i));
            }
        }

        synchronized void createTopic(
            String name,
            int partitions,
            int replicationFactor
        ) {
            if (topics.containsKey(name)) {
                throw new ValidationException(
                    "Topic already exists"
                );
            }

            Topic topic = new Topic(
                name,
                partitions,
                replicationFactor,
                new ArrayList<>(brokers.keySet())
            );

            for (Partition partition : topic.getPartitions()) {
                Assignment assignment = new Assignment(
                    name,
                    partition.getId()
                );

                for (int brokerId : partition.getReplicas()) {
                    brokers.get(brokerId).register(assignment);
                }
            }

            topics.put(name, topic);
        }

        Topic getTopic(String name) {
            Topic topic = topics.get(name);

            if (topic == null) {
                throw new ValidationException(
                    "Topic not found: " + name
                );
            }

            return topic;
        }

        synchronized ProduceResult produce(
            String topicName,
            String key,
            String value
        ) {
            Topic topic = getTopic(topicName);

            Partition partition = topic.selectPartition(key);

            Broker leader = brokers.get(
                partition.getLeaderBroker()
            );

            if (!leader.isAvailable()) {
                throw new BrokerException(
                    "Partition leader unavailable"
                );
            }

            if (policy.acknowledgment() == AckMode.ALL) {
                for (int replica : partition.getReplicas()) {
                    if (!brokers.get(replica).isAvailable()) {
                        throw new BrokerException(
                            "Required replica unavailable"
                        );
                    }
                }
            }

            Message message = Message.create(key, value);

            long offset = partition.append(message);

            return new ProduceResult(
                topicName,
                partition.getId(),
                offset,
                message.id()
            );
        }

        ConsumerGroup getOrCreateGroup(String id) {
            return groups.computeIfAbsent(
                id,
                ConsumerGroup::new
            );
        }

        synchronized void rebalance(
            String groupId,
            String topicName,
            List<String> consumerIds
        ) {
            Topic topic = getTopic(topicName);

            getOrCreateGroup(groupId).rebalance(
                topicName,
                consumerIds,
                topic.getPartitions().size()
            );
        }

        List<ConsumerRecord> poll(
            String groupId,
            String topicName,
            int partitionId,
            int limit
        ) {
            ConsumerGroup group = groups.get(groupId);

            if (group == null) {
                throw new ValidationException(
                    "Unknown consumer group"
                );
            }

            Partition partition = getTopic(topicName)
                .getPartition(partitionId);

            Assignment assignment = new Assignment(
                topicName,
                partitionId
            );

            return partition.read(
                topicName,
                group.committedOffset(assignment),
                Math.min(limit, policy.maximumBatchSize())
            );
        }

        void commit(
            String groupId,
            String topicName,
            int partitionId,
            long nextOffset
        ) {
            ConsumerGroup group = groups.get(groupId);

            if (group == null) {
                throw new ValidationException(
                    "Unknown consumer group"
                );
            }

            Partition partition = getTopic(topicName)
                .getPartition(partitionId);

            group.commit(
                new Assignment(topicName, partitionId),
                nextOffset,
                partition.nextOffset()
            );
        }

        void setBrokerStatus(
            int brokerId,
            BrokerStatus status
        ) {
            Broker broker = brokers.get(brokerId);

            if (broker == null) {
                throw new ValidationException(
                    "Unknown broker"
                );
            }

            broker.setStatus(status);
        }

        void printMetadata() {
            System.out.println("\nBROKERS");

            brokers.values().forEach(System.out::println);

            System.out.println("\nTOPICS");

            topics.values().forEach(topic -> {
                System.out.println(
                    topic.getName() +
                    " replication=" +
                    topic.getReplicationFactor()
                );

                topic.getPartitions().forEach(partition ->
                    System.out.println(
                        "  partition=" + partition.getId() +
                        " leader=" + partition.getLeaderBroker() +
                        " replicas=" + partition.getReplicas() +
                        " records=" + partition.nextOffset()
                    )
                );
            });
        }
    }

    static final class ConsumerService {
        private final KafkaCluster cluster;
        private final String groupId;
        private final String consumerId;

        ConsumerService(
            KafkaCluster cluster,
            String groupId,
            String consumerId
        ) {
            this.cluster = cluster;
            this.groupId = groupId;
            this.consumerId = consumerId;
        }

        int process(
            String topic,
            int partition,
            java.util.function.Consumer<ConsumerRecord> handler
        ) {
            List<ConsumerRecord> records = cluster.poll(
                groupId,
                topic,
                partition,
                100
            );

            int processed = 0;

            for (ConsumerRecord record : records) {
                handler.accept(record);
                processed++;
            }

            // Commit only after all records in the batch succeed.
            // A failure before this point causes possible redelivery.
            if (processed > 0) {
                cluster.commit(
                    groupId,
                    topic,
                    partition,
                    records.get(processed - 1).offset() + 1
                );
            }

            return processed;
        }

        String getConsumerId() {
            return consumerId;
        }
    }

    static final class PaymentProcessor {
        private final Set<String> processedMessageIds =
            new HashSet<>();

        private final Map<String, ProcessingStatus> states =
            new HashMap<>();

        void handle(ConsumerRecord record) {
            String messageId = record.message().id();

            if (processedMessageIds.contains(messageId)) {
                System.out.println(
                    "Duplicate ignored: " + messageId
                );
                return;
            }

            states.put(
                messageId,
                ProcessingStatus.PROCESSING
            );

            try {
                System.out.println(
                    "Processing " +
                    record.message().value() +
                    " at offset " +
                    record.offset()
                );

                // A real payment processor would use a durable
                // idempotency key and a database transaction.
                processedMessageIds.add(messageId);

                states.put(
                    messageId,
                    ProcessingStatus.PROCESSED
                );

            } catch (RuntimeException exception) {
                states.put(
                    messageId,
                    ProcessingStatus.FAILED
                );

                throw exception;
            }
        }

        Map<String, ProcessingStatus> getStates() {
            return Collections.unmodifiableMap(states);
        }
    }

    public static void main(String[] args) {
        try {
            ReviewableProcessingPolicy policy =
                new ReviewableProcessingPolicy(
                    AckMode.ALL,
                    true,
                    100
                );

            KafkaCluster cluster = new KafkaCluster(
                3,
                policy
            );

            cluster.createTopic(
                "payments",
                3,
                2
            );

            List<String> keys = List.of(
                "account-A",
                "account-B",
                "account-A",
                "account-C",
                "account-B",
                "account-D"
            );

            List<String> values = List.of(
                "payment-100",
                "payment-200",
                "payment-300",
                "payment-400",
                "payment-500",
                "payment-600"
            );

            System.out.println("PRODUCING RECORDS");

            for (int i = 0; i < keys.size(); i++) {
                ProduceResult result = cluster.produce(
                    "payments",
                    keys.get(i),
                    values.get(i)
                );

                System.out.println(result);
            }

            String groupId = "payment-service-group";

            List<String> consumerIds = List.of(
                "payment-worker-1",
                "payment-worker-2"
            );

            cluster.rebalance(
                groupId,
                "payments",
                consumerIds
            );

            cluster.printMetadata();

            ConsumerGroup group = cluster.getOrCreateGroup(groupId);

            System.out.println("\nASSIGNMENTS");

            group.getAssignments().forEach(
                (consumer, assignments) ->
                    System.out.println(
                        consumer + " -> " + assignments
                    )
            );

            PaymentProcessor processor = new PaymentProcessor();

            ConsumerService worker1 = new ConsumerService(
                cluster,
                groupId,
                "payment-worker-1"
            );

            ConsumerService worker2 = new ConsumerService(
                cluster,
                groupId,
                "payment-worker-2"
            );

            int processed = 0;

            processed += worker1.process(
                "payments",
                0,
                processor::handle
            );

            processed += worker2.process(
                "payments",
                1,
                processor::handle
            );

            processed += worker1.process(
                "payments",
                2,
                processor::handle
            );

            System.out.println("\nProcessed records: " + processed);

            System.out.println(
                "Processing states: " + processor.getStates()
            );

            System.out.println(
                "Committed offsets: " +
                group.getCommittedOffsets()
            );

            // Invalid commit is rejected.
            try {
                cluster.commit(
                    groupId,
                    "payments",
                    0,
                    999999
                );
            } catch (OffsetException exception) {
                System.out.println(
                    "\nEXPECTED OFFSET FAILURE: " +
                    exception.getMessage()
                );
            }

            // Failure in an unavailable leader.
            int leader = cluster.getTopic("payments")
                .getPartition(0)
                .getLeaderBroker();

            cluster.setBrokerStatus(
                leader,
                BrokerStatus.UNAVAILABLE
            );

            try {
                cluster.produce(
                    "payments",
                    "account-Z",
                    "payment-999"
                );
            } catch (BrokerException exception) {
                System.out.println(
                    "\nEXPECTED BROKER FAILURE: " +
                    exception.getMessage()
                );
            }

            cluster.setBrokerStatus(
                leader,
                BrokerStatus.AVAILABLE
            );

            // Verify that same-key messages are routed consistently.
            ProduceResult routingCheck = cluster.produce(
                "payments",
                "account-A",
                "payment-777"
            );

            System.out.println(
                "\nKEY ROUTING PARTITION: " +
                routingCheck.partition()
            );

            if (processed != 6) {
                throw new KafkaException(
                    "Unexpected processing count"
                );
            }

            System.out.println("\nEnterprise workflow checks passed.");

        } catch (KafkaException exception) {
            System.err.println(
                "APPLICATION ERROR: " +
                exception.getMessage()
            );

            System.exit(1);
        }
    }
}
