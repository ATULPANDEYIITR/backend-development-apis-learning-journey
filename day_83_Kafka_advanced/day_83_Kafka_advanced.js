"use strict";

/*
 * Advanced Kafka operational model.
 *
 * Focus:
 * - Event-driven consumer membership
 * - Partition assignment and cooperative rebalancing
 * - Consumer offset management
 * - Retention policies
 * - Replica health and leader election
 * - Asynchronous processing and failure handling
 *
 * This is a deterministic educational simulation, not a Kafka client.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");

class KafkaError extends Error {}
class ValidationError extends KafkaError {}
class ConsumerError extends KafkaError {}
class ReplicationError extends KafkaError {}
class OffsetError extends KafkaError {}

const BrokerStatus = Object.freeze({
    ONLINE: "ONLINE",
    OFFLINE: "OFFLINE"
});

const MemberStatus = Object.freeze({
    JOINING: "JOINING",
    ACTIVE: "ACTIVE",
    FAILED: "FAILED",
    LEFT: "LEFT"
});

const RebalanceMode = Object.freeze({
    EAGER: "EAGER",
    COOPERATIVE: "COOPERATIVE"
});

function assertPositiveInteger(value, name) {
    if (!Number.isSafeInteger(value) || value <= 0) {
        throw new ValidationError(`${name} must be a positive integer`);
    }
}

class Broker {
    constructor(id) {
        assertPositiveInteger(id, "Broker ID");
        this.id = id;
        this.status = BrokerStatus.ONLINE;
    }
}

class KafkaPartition {
    constructor(topic, id, replicaIds) {
        this.topic = topic;
        this.id = id;
        this.replicas = [...replicaIds];
        this.leader = replicaIds[0];
        this.isr = new Set(replicaIds);
        this.log = [];
        this.nextOffset = 0;
        this.logStartOffset = 0;
        this.highWatermark = 0;
    }

    append(key, value, timestamp = Date.now()) {
        if (typeof key !== "string" || key.length === 0) {
            throw new ValidationError("Message key is required");
        }

        if (typeof value !== "string") {
            throw new ValidationError("Message value must be a string");
        }

        const message = Object.freeze({
            offset: this.nextOffset++,
            key,
            value,
            timestamp,
            size: Buffer.byteLength(key) + Buffer.byteLength(value)
        });

        this.log.push(message);
        return message;
    }

    read(offset) {
        if (offset < this.logStartOffset) {
            throw new OffsetError("Requested offset is outside retained log");
        }

        return this.log.filter(
            message =>
                message.offset >= offset &&
                message.offset < this.highWatermark
        );
    }

    applyRetention(policy, now = Date.now()) {
        const { retentionMs, maxBytes } = policy;

        if (
            retentionMs == null &&
            maxBytes == null
        ) {
            throw new ValidationError("Retention policy is empty");
        }

        if (
            retentionMs != null &&
            (!Number.isFinite(retentionMs) || retentionMs < 0)
        ) {
            throw new ValidationError("Invalid retention duration");
        }

        if (
            maxBytes != null &&
            (!Number.isSafeInteger(maxBytes) || maxBytes < 0)
        ) {
            throw new ValidationError("Invalid retention size");
        }

        let retained = this.log;

        if (retentionMs != null) {
            const cutoff = now - retentionMs;
            retained = retained.filter(
                message => message.timestamp >= cutoff
            );
        }

        if (maxBytes != null) {
            const result = [];
            let bytes = 0;

            for (let i = retained.length - 1; i >= 0; i--) {
                const message = retained[i];

                if (bytes + message.size > maxBytes) {
                    break;
                }

                result.unshift(message);
                bytes += message.size;
            }

            retained = result;
        }

        const removed = this.log.length - retained.length;
        this.log = retained;

        if (removed > 0) {
            this.logStartOffset = retained.length
                ? retained[0].offset
                : this.nextOffset;
        }

        return removed;
    }
}

class ConsumerMember {
    constructor(id, subscriptions) {
        if (!id || !Array.isArray(subscriptions) || !subscriptions.length) {
            throw new ValidationError("Invalid consumer membership");
        }

        this.id = id;
        this.subscriptions = new Set(subscriptions);
        this.assignment = new Set();
        this.status = MemberStatus.JOINING;
        this.lastHeartbeat = Date.now();
    }

    heartbeat() {
        if (this.status !== MemberStatus.ACTIVE) {
            throw new ConsumerError("Inactive consumer cannot heartbeat");
        }

        this.lastHeartbeat = Date.now();
    }
}

class ConsumerGroup extends EventEmitter {
    constructor(id, cluster) {
        super();

        if (!id) {
            throw new ValidationError("Group ID is required");
        }

        this.id = id;
        this.cluster = cluster;
        this.members = new Map();
        this.offsets = new Map();
        this.generation = 0;
        this.stable = false;
        this.rebalanceQueue = Promise.resolve();
    }

    join(consumerId, subscriptions) {
        if (this.members.has(consumerId)) {
            throw new ConsumerError("Duplicate consumer ID");
        }

        for (const topic of subscriptions) {
            if (!this.cluster.topics.has(topic)) {
                throw new ValidationError(`Unknown topic: ${topic}`);
            }
        }

        const member = new ConsumerMember(consumerId, subscriptions);
        this.members.set(consumerId, member);
        this.stable = false;

        this.emit("member:joined", {
            group: this.id,
            consumer: consumerId
        });

        return member;
    }

    leave(consumerId) {
        const member = this.members.get(consumerId);

        if (!member) {
            return false;
        }

        member.assignment.clear();
        member.status = MemberStatus.LEFT;
        this.members.delete(consumerId);
        this.stable = false;

        this.emit("member:left", { consumer: consumerId });
        return true;
    }

    /*
     * Serializing rebalance operations prevents overlapping assignment
     * calculations from publishing inconsistent generations.
     */
    rebalance(mode = RebalanceMode.COOPERATIVE) {
        const operation = async () => {
            const members = [...this.members.values()]
                .filter(m => m.status !== MemberStatus.FAILED)
                .sort((a, b) => a.id.localeCompare(b.id));

            if (mode === RebalanceMode.EAGER) {
                for (const member of members) {
                    member.assignment.clear();
                }
            }

            const desired = new Map(
                members.map(member => [member.id, new Set()])
            );

            for (const [topic, partitions] of this.cluster.topics) {
                const subscribers = members.filter(
                    member => member.subscriptions.has(topic)
                );

                if (!subscribers.length) continue;

                for (const partition of partitions) {
                    const index = partition.id % subscribers.length;
                    const key = `${topic}:${partition.id}`;

                    desired.get(subscribers[index].id).add(key);
                }
            }

            const changes = [];

            for (const member of members) {
                const previous = new Set(member.assignment);
                const next = desired.get(member.id);

                const revoked = [...previous].filter(p => !next.has(p));
                const added = [...next].filter(p => !previous.has(p));

                // Cooperative mode keeps unaffected assignments.
                member.assignment = next;
                member.status = MemberStatus.ACTIVE;

                if (revoked.length || added.length) {
                    changes.push({
                        consumer: member.id,
                        revoked,
                        added
                    });
                }
            }

            this.generation++;
            this.stable = true;

            const result = Object.freeze({
                group: this.id,
                generation: this.generation,
                mode,
                changes
            });

            this.emit("rebalance:completed", result);
            return result;
        };

        this.rebalanceQueue = this.rebalanceQueue.then(operation);
        return this.rebalanceQueue;
    }

    detectFailures(sessionTimeoutMs, now = Date.now()) {
        assertPositiveInteger(sessionTimeoutMs, "Session timeout");

        const failed = [];

        for (const member of this.members.values()) {
            if (
                member.status === MemberStatus.ACTIVE &&
                now - member.lastHeartbeat > sessionTimeoutMs
            ) {
                member.status = MemberStatus.FAILED;
                member.assignment.clear();
                failed.push(member.id);
            }
        }

        if (failed.length) {
            this.stable = false;
            this.emit("member:failed", failed);
        }

        return failed;
    }

    commit(topic, partitionId, nextOffset) {
        if (!this.cluster.topics.has(topic)) {
            throw new OffsetError("Unknown topic");
        }

        const partition = this.cluster.getPartition(topic, partitionId);

        if (!Number.isSafeInteger(nextOffset) || nextOffset < 0) {
            throw new OffsetError("Invalid offset");
        }

        if (
            nextOffset < partition.logStartOffset ||
            nextOffset > partition.highWatermark
        ) {
            throw new OffsetError("Offset outside committed range");
        }

        this.offsets.set(`${topic}:${partitionId}`, nextOffset);
    }

    fetchOffset(topic, partitionId) {
        const partition = this.cluster.getPartition(topic, partitionId);

        return this.offsets.get(`${topic}:${partitionId}`)
            ?? partition.logStartOffset;
    }

    async process(memberId, topic, partitionId, handler) {
        if (!this.stable) {
            throw new ConsumerError("Consumer group is rebalancing");
        }

        const member = this.members.get(memberId);

        if (!member || member.status !== MemberStatus.ACTIVE) {
            throw new ConsumerError("Consumer is not active");
        }

        const key = `${topic}:${partitionId}`;

        if (!member.assignment.has(key)) {
            throw new ConsumerError("Partition is not assigned to consumer");
        }

        if (typeof handler !== "function") {
            throw new ValidationError("Handler must be a function");
        }

        const partition = this.cluster.getPartition(topic, partitionId);
        const start = this.fetchOffset(topic, partitionId);
        const messages = partition.read(start);

        for (const message of messages) {
            // Awaiting each handler makes processing order explicit.
            await handler(message);

            // Commit only after successful processing.
            this.commit(topic, partitionId, message.offset + 1);
        }

        return messages.length;
    }
}

class KafkaCluster extends EventEmitter {
    constructor(minInsyncReplicas = 2) {
        super();
        assertPositiveInteger(minInsyncReplicas, "Minimum ISR");

        this.minInsyncReplicas = minInsyncReplicas;
        this.brokers = new Map();
        this.topics = new Map();
        this.groups = new Map();
    }

    addBroker(id) {
        if (this.brokers.has(id)) {
            throw new ValidationError("Broker already exists");
        }

        this.brokers.set(id, new Broker(id));
    }

    createTopic(name, partitionCount, replicationFactor) {
        assertPositiveInteger(partitionCount, "Partition count");
        assertPositiveInteger(replicationFactor, "Replication factor");

        if (!name || this.topics.has(name)) {
            throw new ValidationError("Invalid or duplicate topic");
        }

        const available = [...this.brokers.values()]
            .filter(b => b.status === BrokerStatus.ONLINE)
            .map(b => b.id)
            .sort((a, b) => a - b);

        if (replicationFactor > available.length) {
            throw new ValidationError("Insufficient brokers");
        }

        const partitions = [];

        for (let id = 0; id < partitionCount; id++) {
            const replicas = Array.from(
                { length: replicationFactor },
                (_, index) => available[(id + index) % available.length]
            );

            partitions.push(new KafkaPartition(name, id, replicas));
        }

        this.topics.set(name, partitions);
    }

    getPartition(topic, id) {
        const partition = this.topics.get(topic)?.[id];

        if (!partition) {
            throw new ValidationError("Unknown partition");
        }

        return partition;
    }

    produce(topic, partitionId, key, value, acks = "all") {
        const partition = this.getPartition(topic, partitionId);
        const leader = this.brokers.get(partition.leader);

        if (!leader || leader.status !== BrokerStatus.ONLINE) {
            throw new ReplicationError("Leader unavailable");
        }

        if (!["all", "1"].includes(acks)) {
            throw new ValidationError("Unsupported acknowledgement mode");
        }

        if (acks === "all") {
            const availableISR = [...partition.isr].filter(
                id => this.brokers.get(id)?.status === BrokerStatus.ONLINE
            );

            if (availableISR.length < this.minInsyncReplicas) {
                throw new ReplicationError("Minimum ISR not satisfied");
            }
        }

        const message = partition.append(key, value);
        partition.highWatermark = message.offset + 1;

        this.emit("record:produced", {
            topic,
            partitionId,
            offset: message.offset
        });

        return message;
    }

    createConsumerGroup(id) {
        if (this.groups.has(id)) {
            throw new ValidationError("Group already exists");
        }

        const group = new ConsumerGroup(id, this);
        this.groups.set(id, group);
        return group;
    }

    failBroker(id) {
        const broker = this.brokers.get(id);

        if (!broker) {
            throw new ValidationError("Unknown broker");
        }

        broker.status = BrokerStatus.OFFLINE;

        for (const partitions of this.topics.values()) {
            for (const partition of partitions) {
                if (!partition.replicas.includes(id)) continue;

                partition.isr.delete(id);

                if (partition.leader === id) {
                    const candidates = [...partition.isr]
                        .filter(
                            candidate =>
                                this.brokers.get(candidate)?.status ===
                                BrokerStatus.ONLINE
                        )
                        .sort((a, b) => a - b);

                    if (candidates.length) {
                        partition.leader = candidates[0];
                        this.emit("leader:elected", {
                            partition: `${partition.topic}:${partition.id}`,
                            leader: partition.leader
                        });
                    } else {
                        this.emit("partition:unavailable", {
                            topic: partition.topic,
                            partition: partition.id
                        });
                    }
                }
            }
        }
    }
}

async function main() {
    const cluster = new KafkaCluster(2);

    [1, 2, 3].forEach(id => cluster.addBroker(id));

    cluster.createTopic("payments", 4, 3);

    cluster.on("leader:elected", event => {
        console.log("New leader:", event);
    });

    cluster.on("rebalance:completed", event => {
        console.log("Rebalance completed:", event);
    });

    for (let i = 0; i < 4; i++) {
        cluster.produce(
            "payments",
            i,
            `payment-${i}`,
            JSON.stringify({ amount: 100 + i, currency: "INR" })
        );
    }

    const group = cluster.createConsumerGroup("payment-processors");

    group.on("member:failed", ids => {
        console.log("Failed consumers:", ids);
    });

    group.join("worker-A", ["payments"]);
    group.join("worker-B", ["payments"]);

    await group.rebalance(RebalanceMode.COOPERATIVE);

    const worker = [...group.members.values()].find(
        member => member.assignment.has("payments:0")
    );

    if (worker) {
        const processed = await group.process(
            worker.id,
            "payments",
            0,
            async message => {
                console.log("Processed:", message.key);
                await Promise.resolve();
            }
        );

        console.log("Processed count:", processed);
        console.log("Next offset:", group.fetchOffset("payments", 0));
    }

    const partition = cluster.getPartition("payments", 0);

    const removed = partition.applyRetention({
        retentionMs: 24 * 60 * 60 * 1000,
        maxBytes: 1024 * 1024
    });

    console.log("Retention removed:", removed);

    cluster.failBroker(1);

    console.log("\nCluster partition status:");

    for (const partitions of cluster.topics.values()) {
        for (const p of partitions) {
            console.log({
                topic: p.topic,
                partition: p.id,
                leader: p.leader,
                replicas: p.replicas,
                isr: [...p.isr]
            });
        }
    }

    console.log("Simulation ID:", randomUUID());
}

main().catch(error => {
    console.error("Kafka simulation failed:", error.message);
    process.exitCode = 1;
});
