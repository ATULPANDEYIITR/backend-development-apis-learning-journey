#include <algorithm>
#include <cstdint>
#include <exception>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class AckMode {
    LEADER,
    ALL
};

enum class BrokerState {
    AVAILABLE,
    UNAVAILABLE
};

struct Message {
    string key;
    string value;
    int64_t timestamp;
};

struct StoredRecord {
    uint64_t offset;
    Message message;
};

class KafkaException : public runtime_error {
public:
    explicit KafkaException(const string& message)
        : runtime_error(message) {}
};

class ValidationException : public KafkaException {
public:
    explicit ValidationException(const string& message)
        : KafkaException(message) {}
};

class BrokerException : public KafkaException {
public:
    explicit BrokerException(const string& message)
        : KafkaException(message) {}
};

class OffsetException : public KafkaException {
public:
    explicit OffsetException(const string& message)
        : KafkaException(message) {}
};

class Broker {
private:
    int id;
    BrokerState state;
    set<pair<string, int>> hostedPartitions;

public:
    explicit Broker(int brokerId)
        : id(brokerId), state(BrokerState::AVAILABLE) {}

    int getId() const {
        return id;
    }

    bool isAvailable() const {
        return state == BrokerState::AVAILABLE;
    }

    void setAvailable(bool available) {
        state = available
            ? BrokerState::AVAILABLE
            : BrokerState::UNAVAILABLE;
    }

    void registerPartition(const string& topic, int partition) {
        hostedPartitions.insert({topic, partition});
    }

    void printStatus() const {
        cout << "Broker " << id
             << " status="
             << (isAvailable() ? "AVAILABLE" : "UNAVAILABLE")
             << " hosted_partitions=" << hostedPartitions.size()
             << '\n';
    }
};

class Partition {
private:
    int id;
    int leaderBroker;
    vector<int> replicas;
    vector<StoredRecord> log;

public:
    Partition(int partitionId, int leader, vector<int> replicaIds)
        : id(partitionId),
          leaderBroker(leader),
          replicas(move(replicaIds)) {}

    int getId() const {
        return id;
    }

    int getLeader() const {
        return leaderBroker;
    }

    const vector<int>& getReplicas() const {
        return replicas;
    }

    uint64_t nextOffset() const {
        return log.size();
    }

    uint64_t append(const Message& message) {
        uint64_t offset = nextOffset();

        log.push_back({
            offset,
            message
        });

        return offset;
    }

    vector<StoredRecord> read(
        uint64_t offset,
        size_t limit
    ) const {
        if (offset > log.size()) {
            throw OffsetException("Requested offset exceeds log end");
        }

        if (limit == 0) {
            throw ValidationException("Read limit must be positive");
        }

        size_t start = static_cast<size_t>(offset);

        size_t end = min(
            log.size(),
            start + limit
        );

        return vector<StoredRecord>(
            log.begin() + static_cast<ptrdiff_t>(start),
            log.begin() + static_cast<ptrdiff_t>(end)
        );
    }
};

class Topic {
private:
    string name;
    int replicationFactor;
    vector<Partition> partitions;

    static uint64_t stableHash(const string& value) {
        // FNV-1a provides deterministic routing for this simulation.
        uint64_t hash = 14695981039346656037ULL;

        for (unsigned char character : value) {
            hash ^= character;
            hash *= 1099511628211ULL;
        }

        return hash;
    }

public:
    Topic(
        string topicName,
        int partitionCount,
        int replication,
        const vector<int>& brokerIds
    )
        : name(move(topicName)),
          replicationFactor(replication) {

        if (name.empty()) {
            throw ValidationException("Topic name is required");
        }

        if (partitionCount < 1) {
            throw ValidationException("Partition count must be positive");
        }

        if (
            replication < 1 ||
            replication > static_cast<int>(brokerIds.size())
        ) {
            throw ValidationException("Invalid replication factor");
        }

        for (int i = 0; i < partitionCount; ++i) {
            int leaderIndex = i % static_cast<int>(brokerIds.size());

            vector<int> replicas;

            for (int j = 0; j < replication; ++j) {
                int index = (leaderIndex + j)
                    % static_cast<int>(brokerIds.size());

                replicas.push_back(brokerIds[index]);
            }

            partitions.emplace_back(
                i,
                replicas.front(),
                replicas
            );
        }
    }

    const string& getName() const {
        return name;
    }

    int getReplicationFactor() const {
        return replicationFactor;
    }

    size_t partitionCount() const {
        return partitions.size();
    }

    Partition& getPartition(int id) {
        if (id < 0 || static_cast<size_t>(id) >= partitions.size()) {
            throw ValidationException("Invalid partition ID");
        }

        return partitions[id];
    }

    const Partition& getPartition(int id) const {
        if (id < 0 || static_cast<size_t>(id) >= partitions.size()) {
            throw ValidationException("Invalid partition ID");
        }

        return partitions[id];
    }

    Partition& partitionFor(const string& key) {
        size_t index = key.empty()
            ? 0
            : stableHash(key) % partitions.size();

        return partitions[index];
    }

    const vector<Partition>& getPartitions() const {
        return partitions;
    }
};

class ConsumerGroup {
private:
    string groupId;

    // Values represent the next offset to consume, not the last
    // successfully processed offset.
    map<pair<string, int>, uint64_t> committedOffsets;

    map<string, vector<pair<string, int>>> assignments;

public:
    explicit ConsumerGroup(string id)
        : groupId(move(id)) {

        if (groupId.empty()) {
            throw ValidationException("Group ID is required");
        }
    }

    const string& getId() const {
        return groupId;
    }

    uint64_t getCommittedOffset(
        const string& topic,
        int partition
    ) const {
        auto key = make_pair(topic, partition);

        auto it = committedOffsets.find(key);

        return it == committedOffsets.end() ? 0 : it->second;
    }

    void commit(
        const string& topic,
        int partition,
        uint64_t nextOffset,
        uint64_t maximum
    ) {
        if (nextOffset > maximum) {
            throw OffsetException("Cannot commit beyond log end");
        }

        uint64_t previous = getCommittedOffset(topic, partition);

        if (nextOffset < previous) {
            throw OffsetException("Offset regression is not allowed");
        }

        committedOffsets[{topic, partition}] = nextOffset;
    }

    void assign(
        const string& topic,
        const vector<string>& consumerIds,
        size_t partitionCount
    ) {
        if (consumerIds.empty()) {
            throw ValidationException("Consumer list cannot be empty");
        }

        set<string> uniqueConsumers(
            consumerIds.begin(),
            consumerIds.end()
        );

        if (uniqueConsumers.size() != consumerIds.size()) {
            throw ValidationException("Duplicate consumer ID");
        }

        assignments.clear();

        for (const auto& consumer : consumerIds) {
            assignments[consumer] = {};
        }

        for (size_t i = 0; i < partitionCount; ++i) {
            const string& consumer =
                consumerIds[i % consumerIds.size()];

            assignments[consumer].push_back({
                topic,
                static_cast<int>(i)
            });
        }
    }

    const map<string, vector<pair<string, int>>>&
    getAssignments() const {
        return assignments;
    }

    const map<pair<string, int>, uint64_t>&
    getOffsets() const {
        return committedOffsets;
    }
};

class KafkaCluster {
private:
    map<int, Broker> brokers;
    map<string, Topic> topics;
    map<string, ConsumerGroup> groups;

    int64_t clock = 0;

public:
    explicit KafkaCluster(int brokerCount) {
        if (brokerCount < 1) {
            throw ValidationException("At least one broker is required");
        }

        for (int i = 1; i <= brokerCount; ++i) {
            brokers.emplace(piecewise_construct,
                forward_as_tuple(i),
                forward_as_tuple(i));
        }
    }

    void createTopic(
        const string& name,
        int partitionCount,
        int replicationFactor
    ) {
        if (topics.count(name)) {
            throw ValidationException("Topic already exists");
        }

        vector<int> brokerIds;

        for (const auto& [id, broker] : brokers) {
            brokerIds.push_back(id);
        }

        Topic topic(
            name,
            partitionCount,
            replicationFactor,
            brokerIds
        );

        for (const auto& partition : topic.getPartitions()) {
            for (int brokerId : partition.getReplicas()) {
                brokers.at(brokerId).registerPartition(
                    name,
                    partition.getId()
                );
            }
        }

        topics.emplace(name, move(topic));

        cout << "Created topic: " << name
             << " partitions=" << partitionCount
             << " replication=" << replicationFactor
             << '\n';
    }

    Topic& getTopic(const string& name) {
        auto it = topics.find(name);

        if (it == topics.end()) {
            throw ValidationException("Topic not found: " + name);
        }

        return it->second;
    }

    ConsumerGroup& getOrCreateGroup(const string& id) {
        auto it = groups.find(id);

        if (it == groups.end()) {
            it = groups.emplace(
                piecewise_construct,
                forward_as_tuple(id),
                forward_as_tuple(id)
            ).first;
        }

        return it->second;
    }

    struct ProduceResult {
        string topic;
        int partition;
        uint64_t offset;
    };

    ProduceResult produce(
        const string& topicName,
        const string& key,
        const string& value,
        AckMode acknowledgment = AckMode::ALL
    ) {
        Topic& topic = getTopic(topicName);

        Partition& partition = topic.partitionFor(key);

        int leaderId = partition.getLeader();

        if (!brokers.at(leaderId).isAvailable()) {
            throw BrokerException("Partition leader is unavailable");
        }

        if (acknowledgment == AckMode::ALL) {
            for (int replica : partition.getReplicas()) {
                if (!brokers.at(replica).isAvailable()) {
                    throw BrokerException(
                        "A configured replica is unavailable"
                    );
                }
            }
        }

        Message message{
            key,
            value,
            ++clock
        };

        uint64_t offset = partition.append(message);

        return {
            topicName,
            partition.getId(),
            offset
        };
    }

    void rebalance(
        const string& groupId,
        const string& topicName,
        const vector<string>& consumerIds
    ) {
        Topic& topic = getTopic(topicName);

        ConsumerGroup& group = getOrCreateGroup(groupId);

        group.assign(
            topicName,
            consumerIds,
            topic.partitionCount()
        );
    }

    vector<StoredRecord> poll(
        const string& groupId,
        const string& topicName,
        int partitionId,
        size_t limit = 10
    ) {
        auto groupIt = groups.find(groupId);

        if (groupIt == groups.end()) {
            throw ValidationException("Unknown consumer group");
        }

        Topic& topic = getTopic(topicName);

        Partition& partition = topic.getPartition(partitionId);

        uint64_t offset = groupIt->second.getCommittedOffset(
            topicName,
            partitionId
        );

        return partition.read(offset, limit);
    }

    void commit(
        const string& groupId,
        const string& topicName,
        int partitionId,
        uint64_t nextOffset
    ) {
        auto groupIt = groups.find(groupId);

        if (groupIt == groups.end()) {
            throw ValidationException("Unknown consumer group");
        }

        Topic& topic = getTopic(topicName);

        const Partition& partition = topic.getPartition(partitionId);

        groupIt->second.commit(
            topicName,
            partitionId,
            nextOffset,
            partition.nextOffset()
        );
    }

    void setBrokerAvailability(int id, bool available) {
        auto it = brokers.find(id);

        if (it == brokers.end()) {
            throw ValidationException("Unknown broker");
        }

        it->second.setAvailable(available);
    }

    void printMetadata() const {
        cout << "\nBROKER METADATA\n";

        for (const auto& [id, broker] : brokers) {
            broker.printStatus();
        }

        cout << "\nTOPIC METADATA\n";

        for (const auto& [name, topic] : topics) {
            cout << "Topic: " << name
                 << " replication=" << topic.getReplicationFactor()
                 << '\n';

            for (const auto& partition : topic.getPartitions()) {
                cout << "  Partition " << partition.getId()
                     << " leader=" << partition.getLeader()
                     << " replicas=";

                for (int replica : partition.getReplicas()) {
                    cout << replica << " ";
                }

                cout << " records=" << partition.nextOffset()
                     << '\n';
            }
        }
    }

    void printGroup(const string& groupId) const {
        auto it = groups.find(groupId);

        if (it == groups.end()) {
            throw ValidationException("Unknown group");
        }

        cout << "\nCONSUMER GROUP: " << groupId << '\n';

        for (const auto& [consumer, assignments] :
             it->second.getAssignments()) {

            cout << consumer << ": ";

            for (const auto& [topic, partition] : assignments) {
                cout << topic << "[" << partition << "] ";
            }

            cout << '\n';
        }

        for (const auto& [key, offset] : it->second.getOffsets()) {
            cout << "Committed " << key.first
                 << "[" << key.second << "]="
                 << offset << '\n';
        }
    }
};

class Consumer {
private:
    KafkaCluster& cluster;
    string groupId;
    string consumerId;

public:
    Consumer(
        KafkaCluster& kafka,
        string group,
        string id
    )
        : cluster(kafka),
          groupId(move(group)),
          consumerId(move(id)) {}

    size_t process(
        const string& topic,
        int partition,
        size_t limit = 10
    ) {
        auto records = cluster.poll(
            groupId,
            topic,
            partition,
            limit
        );

        size_t processed = 0;

        for (const auto& record : records) {
            cout << consumerId
                 << " processed key=" << record.message.key
                 << " value=" << record.message.value
                 << " offset=" << record.offset
                 << '\n';

            ++processed;
        }

        if (processed > 0) {
            uint64_t nextOffset = records.back().offset + 1;

            cluster.commit(
                groupId,
                topic,
                partition,
                nextOffset
            );
        }

        return processed;
    }
};

int main() {
    try {
        KafkaCluster cluster(3);

        cluster.createTopic("inventory", 3, 2);

        vector<pair<string, string>> messages = {
            {"product-A", "stock-update-100"},
            {"product-B", "stock-update-200"},
            {"product-A", "stock-update-150"},
            {"product-C", "stock-update-300"},
            {"product-B", "stock-update-250"},
            {"product-D", "stock-update-400"}
        };

        cout << "\nPRODUCER OPERATIONS\n";

        for (const auto& [key, value] : messages) {
            auto result = cluster.produce(
                "inventory",
                key,
                value,
                AckMode::ALL
            );

            cout << "Produced topic=" << result.topic
                 << " partition=" << result.partition
                 << " offset=" << result.offset
                 << '\n';
        }

        string groupId = "inventory-processors";

        vector<string> consumers = {
            "worker-1",
            "worker-2"
        };

        cluster.rebalance(
            groupId,
            "inventory",
            consumers
        );

        cluster.printMetadata();
        cluster.printGroup(groupId);

        cout << "\nCONSUMER OPERATIONS\n";

        Consumer worker1(cluster, groupId, "worker-1");
        Consumer worker2(cluster, groupId, "worker-2");

        size_t totalProcessed = 0;

        totalProcessed += worker1.process("inventory", 0);
        totalProcessed += worker2.process("inventory", 1);
        totalProcessed += worker1.process("inventory", 2);

        cout << "\nTotal processed: "
             << totalProcessed << '\n';

        cluster.printGroup(groupId);

        cout << "\nREDELIVERY CHECK\n";

        auto replay = cluster.poll(
            groupId,
            "inventory",
            0
        );

        cout << "Records remaining after commit: "
             << replay.size() << '\n';

        cout << "\nINVALID OFFSET CHECK\n";

        try {
            cluster.commit(
                groupId,
                "inventory",
                0,
                999999
            );
        } catch (const OffsetException& error) {
            cout << "Expected failure: "
                 << error.what() << '\n';
        }

        cout << "\nBROKER FAILURE CHECK\n";

        cluster.setBrokerAvailability(1, false);

        try {
            cluster.produce(
                "inventory",
                "product-Z",
                "stock-update-50",
                AckMode::ALL
            );
        } catch (const BrokerException& error) {
            cout << "Expected failure: "
                 << error.what() << '\n';
        }

        cluster.setBrokerAvailability(1, true);

        // Same key always routes to the same partition.
        auto first = cluster.produce(
            "inventory",
            "product-A",
            "stock-update-500"
        );

        cout << "\nKEY ROUTING CHECK\n";
        cout << "product-A partition: "
             << first.partition << '\n';

        if (totalProcessed != 6) {
            throw KafkaException("Unexpected processing count");
        }

        cout << "\nAll validation checks completed.\n";

        return 0;
    } catch (const exception& error) {
        cerr << "APPLICATION ERROR: "
             << error.what() << '\n';

        return 1;
    }
}
