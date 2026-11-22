#include <algorithm>
#include <cstdint>
#include <exception>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class BrokerStatus {
    ONLINE,
    OFFLINE
};

enum class Acknowledgement {
    LEADER_ONLY,
    ALL
};

enum class MemberStatus {
    ACTIVE,
    FAILED,
    LEFT
};

struct Record {
    int64_t offset;
    string key;
    string value;
    int64_t timestamp;
    size_t size;
};

struct Broker {
    int id;
    BrokerStatus status = BrokerStatus::ONLINE;
};

struct Partition {
    string topic;
    int id;
    vector<int> replicas;
    int leader;
    set<int> isr;
    vector<Record> log;
    int64_t nextOffset = 0;
    int64_t logStartOffset = 0;
    int64_t highWatermark = 0;

    Partition(
        string topicName,
        int partitionId,
        vector<int> replicaIds
    ) :
        topic(move(topicName)),
        id(partitionId),
        replicas(move(replicaIds)),
        leader(replicas.front()),
        isr(replicas.begin(), replicas.end()) {}

    Record append(
        const string& key,
        const string& value,
        int64_t timestamp
    ) {
        if (key.empty()) {
            throw invalid_argument("Record key cannot be empty");
        }

        Record record{
            nextOffset++,
            key,
            value,
            timestamp,
            key.size() + value.size()
        };

        log.push_back(record);
        return record;
    }

    vector<Record> read(int64_t offset) const {
        if (offset < logStartOffset) {
            throw runtime_error("Requested offset has expired");
        }

        vector<Record> result;

        for (const auto& record : log) {
            if (
                record.offset >= offset &&
                record.offset < highWatermark
            ) {
                result.push_back(record);
            }
        }

        return result;
    }

    size_t retainByAge(int64_t cutoff) {
        size_t previous = log.size();

        log.erase(
            remove_if(
                log.begin(),
                log.end(),
                [cutoff](const Record& record) {
                    return record.timestamp < cutoff;
                }
            ),
            log.end()
        );

        if (!log.empty()) {
            logStartOffset = log.front().offset;
        } else if (previous != log.size()) {
            logStartOffset = nextOffset;
        }

        return previous - log.size();
    }

    size_t retainBySize(size_t maximumBytes) {
        size_t previous = log.size();
        size_t retainedBytes = 0;
        vector<Record> retained;

        // Walk backwards to preserve the newest complete records.
        for (auto it = log.rbegin(); it != log.rend(); ++it) {
            if (it->size > maximumBytes - retainedBytes) {
                break;
            }

            retainedBytes += it->size;
            retained.push_back(*it);
        }

        reverse(retained.begin(), retained.end());
        log = move(retained);

        if (previous != log.size()) {
            logStartOffset = log.empty() ? nextOffset : log.front().offset;
        }

        return previous - log.size();
    }
};

struct Consumer {
    string id;
    string groupId;
    set<string> subscriptions;
    set<pair<string, int>> assignments;
    MemberStatus status = MemberStatus::ACTIVE;
};

struct ConsumerGroup {
    string id;
    map<string, Consumer> members;
    map<pair<string, int>, int64_t> committedOffsets;
    int generation = 0;
    bool stable = false;
};

class KafkaGovernanceEngine {
private:
    unordered_map<int, Broker> brokers;
    map<string, vector<Partition>> topics;
    map<string, ConsumerGroup> groups;
    int minimumISR;

    Partition& partition(
        const string& topic,
        int partitionId
    ) {
        auto topicIt = topics.find(topic);

        if (topicIt == topics.end() ||
            partitionId < 0 ||
            partitionId >= static_cast<int>(topicIt->second.size())) {
            throw invalid_argument("Unknown topic or partition");
        }

        return topicIt->second[partitionId];
    }

    const Partition& partition(
        const string& topic,
        int partitionId
    ) const {
        auto topicIt = topics.find(topic);

        if (topicIt == topics.end() ||
            partitionId < 0 ||
            partitionId >= static_cast<int>(topicIt->second.size())) {
            throw invalid_argument("Unknown topic or partition");
        }

        return topicIt->second[partitionId];
    }

public:
    explicit KafkaGovernanceEngine(int minISR = 2) :
        minimumISR(minISR) {
        if (minISR < 1) {
            throw invalid_argument("Minimum ISR must be positive");
        }
    }

    void addBroker(int id) {
        if (id <= 0 || brokers.count(id)) {
            throw invalid_argument("Invalid or duplicate broker");
        }

        brokers.emplace(id, Broker{id});
    }

    void createTopic(
        const string& name,
        int partitionCount,
        int replicationFactor
    ) {
        if (name.empty() || topics.count(name)) {
            throw invalid_argument("Invalid or duplicate topic");
        }

        if (partitionCount <= 0 || replicationFactor <= 0) {
            throw invalid_argument("Invalid topic configuration");
        }

        vector<int> available;

        for (const auto& [id, broker] : brokers) {
            if (broker.status == BrokerStatus::ONLINE) {
                available.push_back(id);
            }
        }

        sort(available.begin(), available.end());

        if (replicationFactor > static_cast<int>(available.size())) {
            throw runtime_error("Insufficient brokers");
        }

        vector<Partition> partitions;

        for (int p = 0; p < partitionCount; ++p) {
            vector<int> replicas;

            for (int r = 0; r < replicationFactor; ++r) {
                replicas.push_back(
                    available[(p + r) % available.size()]
                );
            }

            partitions.emplace_back(name, p, replicas);
        }

        topics.emplace(name, move(partitions));
    }

    Record produce(
        const string& topic,
        int partitionId,
        const string& key,
        const string& value,
        int64_t timestamp,
        Acknowledgement acknowledgement
    ) {
        Partition& p = partition(topic, partitionId);

        if (brokers.at(p.leader).status != BrokerStatus::ONLINE) {
            throw runtime_error("Partition leader is unavailable");
        }

        if (acknowledgement == Acknowledgement::ALL) {
            int onlineISR = 0;

            for (int id : p.isr) {
                if (brokers.at(id).status == BrokerStatus::ONLINE) {
                    ++onlineISR;
                }
            }

            if (onlineISR < minimumISR) {
                throw runtime_error("Minimum ISR requirement failed");
            }
        }

        Record record = p.append(key, value, timestamp);

        // The simulation treats the current ISR as synchronously replicated.
        p.highWatermark = record.offset + 1;

        return record;
    }

    void joinGroup(
        const string& groupId,
        const string& consumerId,
        const set<string>& subscriptions
    ) {
        if (groupId.empty() || consumerId.empty() || subscriptions.empty()) {
            throw invalid_argument("Invalid consumer registration");
        }

        for (const string& topic : subscriptions) {
            if (!topics.count(topic)) {
                throw invalid_argument("Unknown subscribed topic");
            }
        }

        if (!groups.count(groupId)) {
            groups.emplace(groupId, ConsumerGroup{groupId});
        }

        ConsumerGroup& group = groups.at(groupId);

        if (group.members.count(consumerId)) {
            throw invalid_argument("Duplicate consumer membership");
        }

        group.members.emplace(
            consumerId,
            Consumer{
                consumerId,
                groupId,
                subscriptions
            }
        );

        group.stable = false;
    }

    map<string, set<pair<string, int>>> rebalance(
        const string& groupId,
        bool cooperative
    ) {
        ConsumerGroup& group = groups.at(groupId);

        vector<Consumer*> active;

        for (auto& [id, consumer] : group.members) {
            if (consumer.status == MemberStatus::ACTIVE) {
                active.push_back(&consumer);

                if (!cooperative) {
                    consumer.assignments.clear();
                }
            }
        }

        sort(
            active.begin(),
            active.end(),
            [](const Consumer* a, const Consumer* b) {
                return a->id < b->id;
            }
        );

        map<string, set<pair<string, int>>> desired;

        for (Consumer* consumer : active) {
            desired[consumer->id] = {};
        }

        for (const auto& [topicName, partitions] : topics) {
            vector<Consumer*> subscribers;

            for (Consumer* consumer : active) {
                if (consumer->subscriptions.count(topicName)) {
                    subscribers.push_back(consumer);
                }
            }

            if (subscribers.empty()) {
                continue;
            }

            for (const Partition& p : partitions) {
                Consumer* owner = subscribers[
                    p.id % subscribers.size()
                ];

                desired[owner->id].insert({topicName, p.id});
            }
        }

        for (Consumer* consumer : active) {
            if (cooperative) {
                set<pair<string, int>> retained;

                set_intersection(
                    consumer->assignments.begin(),
                    consumer->assignments.end(),
                    desired[consumer->id].begin(),
                    desired[consumer->id].end(),
                    inserter(retained, retained.begin())
                );

                consumer->assignments = move(retained);
            }

            consumer->assignments = desired[consumer->id];
        }

        group.generation++;
        group.stable = true;

        return desired;
    }

    void commitOffset(
        const string& groupId,
        const string& topic,
        int partitionId,
        int64_t nextOffset
    ) {
        ConsumerGroup& group = groups.at(groupId);
        const Partition& p = partition(topic, partitionId);

        if (
            nextOffset < p.logStartOffset ||
            nextOffset > p.highWatermark
        ) {
            throw runtime_error("Invalid committed offset");
        }

        group.committedOffsets[{topic, partitionId}] = nextOffset;
    }

    int64_t fetchOffset(
        const string& groupId,
        const string& topic,
        int partitionId
    ) const {
        const ConsumerGroup& group = groups.at(groupId);
        const Partition& p = partition(topic, partitionId);

        auto it = group.committedOffsets.find({topic, partitionId});

        return it == group.committedOffsets.end()
            ? p.logStartOffset
            : it->second;
    }

    void failBroker(int brokerId) {
        if (!brokers.count(brokerId)) {
            throw invalid_argument("Unknown broker");
        }

        brokers.at(brokerId).status = BrokerStatus::OFFLINE;

        for (auto& [topic, partitions] : topics) {
            for (Partition& p : partitions) {
                if (
                    find(
                        p.replicas.begin(),
                        p.replicas.end(),
                        brokerId
                    ) == p.replicas.end()
                ) {
                    continue;
                }

                p.isr.erase(brokerId);

                if (p.leader == brokerId) {
                    vector<int> candidates;

                    for (int id : p.isr) {
                        if (brokers.at(id).status == BrokerStatus::ONLINE) {
                            candidates.push_back(id);
                        }
                    }

                    if (candidates.empty()) {
                        throw runtime_error(
                            "No available in-sync replica for leader election"
                        );
                    }

                    p.leader = *min_element(
                        candidates.begin(),
                        candidates.end()
                    );
                }
            }
        }
    }

    void restoreBroker(int brokerId) {
        if (!brokers.count(brokerId)) {
            throw invalid_argument("Unknown broker");
        }

        brokers.at(brokerId).status = BrokerStatus::ONLINE;

        // A restored broker is not automatically an ISR member.
    }

    void displayStatus() const {
        cout << "\nCluster partition status\n";

        for (const auto& [topic, partitions] : topics) {
            for (const Partition& p : partitions) {
                cout << topic
                     << "-" << p.id
                     << " leader=" << p.leader
                     << " ISR={";

                bool first = true;

                for (int id : p.isr) {
                    if (!first) cout << ",";
                    cout << id;
                    first = false;
                }

                cout << "} highWatermark=" << p.highWatermark
                     << " logStart=" << p.logStartOffset
                     << "\n";
            }
        }
    }

    void demonstrateRetention(
        const string& topic,
        int partitionId,
        int64_t cutoff,
        size_t maximumBytes
    ) {
        Partition& p = partition(topic, partitionId);

        size_t removedByAge = p.retainByAge(cutoff);
        size_t removedBySize = p.retainBySize(maximumBytes);

        cout << "Age-retention removals: " << removedByAge << "\n";
        cout << "Size-retention removals: " << removedBySize << "\n";
    }
};

int main() {
    try {
        KafkaGovernanceEngine cluster(2);

        for (int id = 1; id <= 3; ++id) {
            cluster.addBroker(id);
        }

        cluster.createTopic("transactions", 4, 3);

        for (int p = 0; p < 4; ++p) {
            cluster.produce(
                "transactions",
                p,
                "transaction-" + to_string(p),
                "{\"amount\":500,\"currency\":\"INR\"}",
                1000 + p,
                Acknowledgement::ALL
            );
        }

        cluster.joinGroup(
            "transaction-workers",
            "worker-A",
            {"transactions"}
        );

        cluster.joinGroup(
            "transaction-workers",
            "worker-B",
            {"transactions"}
        );

        auto assignments = cluster.rebalance(
            "transaction-workers",
            true
        );

        cout << "\nConsumer assignments\n";

        for (const auto& [consumer, partitions] : assignments) {
            cout << consumer << ": ";

            for (const auto& [topic, partitionId] : partitions) {
                cout << topic << "-" << partitionId << " ";
            }

            cout << "\n";
        }

        cluster.commitOffset(
            "transaction-workers",
            "transactions",
            0,
            1
        );

        cout << "\nCommitted offset: "
             << cluster.fetchOffset(
                    "transaction-workers",
                    "transactions",
                    0
                )
             << "\n";

        cluster.demonstrateRetention(
            "transactions",
            0,
            0,
            1024
        );

        cout << "\nSimulating broker failure\n";
        cluster.failBroker(1);

        cluster.displayStatus();

        cluster.restoreBroker(1);

        cout << "\nBroker 1 restored. ISR recovery requires replication.\n";

        // An invalid commit must be rejected.
        try {
            cluster.commitOffset(
                "transaction-workers",
                "transactions",
                0,
                999
            );
        } catch (const exception& error) {
            cout << "Expected validation failure: "
                 << error.what() << "\n";
        }

    } catch (const exception& error) {
        cerr << "Cluster error: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
