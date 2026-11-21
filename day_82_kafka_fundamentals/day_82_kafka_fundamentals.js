"use strict";

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");

class KafkaError extends Error {}
class ValidationError extends KafkaError {}
class TopicNotFoundError extends KafkaError {}
class OffsetError extends KafkaError {}
class BrokerUnavailableError extends KafkaError {}

const AckMode = Object.freeze({
    LEADER: "leader",
    ALL: "all"
});

function validateName(value, field) {
    if (
        typeof value !== "string" ||
        value.trim().length === 0
    ) {
        throw new ValidationError(`${field} is required`);
    }
}

function stableHash(value) {
    // Cryptographic hashing avoids process-dependent routing behavior.
    const digest = crypto
        .createHash("sha256")
        .update(value, "utf8")
        .digest();

    return digest.readUInt32BE(0);
}

class Broker {
    constructor(id) {
        this.id = id;
        this.available = true;
        this.partitions = new Set();
    }
}

class Partition {
    constructor(id, leader, replicas) {
        this.id = id;
        this.leader = leader;
        this.replicas = replicas;
        this.log = [];
        this.highWatermark = 0;
    }

    append(record) {
        const offset = this.log.length;

        this.log.push(
            Object.freeze({
                ...record,
                offset
            })
        );

        this.highWatermark = this.log.length;

        return offset;
    }

    read(offset, limit) {
        if (!Number.isInteger(offset) || offset < 0) {
            throw new OffsetError("Offset must be a non-negative integer");
        }

        if (!Number.isInteger(limit) || limit < 1) {
            throw new ValidationError("Limit must be positive");
        }

        return this.log.slice(offset, offset + limit);
    }
}

class Topic {
    constructor(name, partitions, replicationFactor) {
        this.name = name;
        this.partitions = partitions;
        this.replicationFactor = replicationFactor;
        this.createdAt = new Date().toISOString();
    }

    partitionFor(key) {
        if (key === null || key === undefined) {
            return this.partitions[0];
        }

        const index = stableHash(String(key)) % this.partitions.length;

        return this.partitions[index];
    }
}

class ConsumerGroup {
    constructor(groupId) {
        this.groupId = groupId;
        this.offsets = new Map();
        this.members = new Map();
        this.assignments = new Map();
        this.generation = 0;
    }

    offsetKey(topic, partition) {
        return `${topic}:${partition}`;
    }

    getOffset(topic, partition) {
        return this.offsets.get(
            this.offsetKey(topic, partition)
        ) ?? 0;
    }

    commit(topic, partition, nextOffset, maximum) {
        const key = this.offsetKey(topic, partition);

        if (
            !Number.isInteger(nextOffset) ||
            nextOffset < 0 ||
            nextOffset > maximum
        ) {
            throw new OffsetError("Invalid committed offset");
        }

        const previous = this.getOffset(topic, partition);

        if (nextOffset < previous) {
            throw new OffsetError(
                "Committed offsets cannot move backwards"
            );
        }

        this.offsets.set(key, nextOffset);
    }
}

class KafkaCluster extends EventEmitter {
    constructor(brokerCount = 3) {
        super();

        if (!Number.isInteger(brokerCount) || brokerCount < 1) {
            throw new ValidationError("Invalid broker count");
        }

        this.brokers = new Map();

        for (let id = 1; id <= brokerCount; id++) {
            this.brokers.set(id, new Broker(id));
        }

        this.topics = new Map();
        this.groups = new Map();
        this.sequence = 0;
    }

    createTopic(name, partitionCount = 3, replicationFactor = 2) {
        validateName(name, "Topic name");

        if (this.topics.has(name)) {
            throw new ValidationError("Topic already exists");
        }

        if (
            !Number.isInteger(partitionCount) ||
            partitionCount < 1
        ) {
            throw new ValidationError("Invalid partition count");
        }

        if (
            !Number.isInteger(replicationFactor) ||
            replicationFactor < 1 ||
            replicationFactor > this.brokers.size
        ) {
            throw new ValidationError("Invalid replication factor");
        }

        const brokerIds = [...this.brokers.keys()];
        const partitions = [];

        for (let index = 0; index < partitionCount; index++) {
            const leaderIndex = index % brokerIds.length;

            const replicas = Array.from(
                { length: replicationFactor },
                (_, i) => brokerIds[
                    (leaderIndex + i) % brokerIds.length
                ]
            );

            const partition = new Partition(
                index,
                replicas[0],
                replicas
            );

            partitions.push(partition);

            for (const brokerId of replicas) {
                this.brokers
                    .get(brokerId)
                    .partitions
                    .add(`${name}:${index}`);
            }
        }

        const topic = new Topic(
            name,
            partitions,
            replicationFactor
        );

        this.topics.set(name, topic);

        this.emit("topic.created", {
            topic: name,
            partitionCount,
            replicationFactor
        });

        return topic;
    }

    getTopic(name) {
        const topic = this.topics.get(name);

        if (!topic) {
            throw new TopicNotFoundError(name);
        }

        return topic;
    }

    produce(topicName, key, value, ack = AckMode.ALL) {
        const topic = this.getTopic(topicName);

        if (
            value === null ||
            typeof value !== "object" ||
            Array.isArray(value)
        ) {
            throw new ValidationError(
                "Message value must be an object"
            );
        }

        if (!Object.values(AckMode).includes(ack)) {
            throw new ValidationError("Unsupported acknowledgment mode");
        }

        const partition = topic.partitionFor(key);
        const leader = this.brokers.get(partition.leader);

        if (!leader.available) {
            throw new BrokerUnavailableError(
                `Leader ${leader.id} is unavailable`
            );
        }

        if (ack === AckMode.ALL) {
            const allAvailable = partition.replicas.every(
                id => this.brokers.get(id).available
            );

            if (!allAvailable) {
                throw new BrokerUnavailableError(
                    "A required replica is unavailable"
                );
            }
        }

        const record = {
            key: key === null ? null : String(key),
            value: structuredClone(value),
            timestamp: Date.now(),
            messageId: crypto.randomUUID(),
            sequence: ++this.sequence
        };

        const offset = partition.append(record);

        const result = {
            topic: topicName,
            partition: partition.id,
            offset,
            messageId: record.messageId
        };

        this.emit("record.produced", result);

        return result;
    }

    getOrCreateGroup(groupId) {
        validateName(groupId, "Consumer group");

        if (!this.groups.has(groupId)) {
            this.groups.set(
                groupId,
                new ConsumerGroup(groupId)
            );
        }

        return this.groups.get(groupId);
    }

    rebalance(groupId, topicName, consumerIds) {
        const topic = this.getTopic(topicName);

        if (!Array.isArray(consumerIds) || consumerIds.length === 0) {
            throw new ValidationError("Consumers are required");
        }

        if (
            new Set(consumerIds).size !== consumerIds.length ||
            consumerIds.some(
                id => typeof id !== "string" || !id.trim()
            )
        ) {
            throw new ValidationError("Invalid consumer IDs");
        }

        const group = this.getOrCreateGroup(groupId);

        const assignments = new Map(
            consumerIds.map(id => [id, []])
        );

        topic.partitions.forEach((partition, index) => {
            const consumerId = consumerIds[
                index % consumerIds.length
            ];

            assignments.get(consumerId).push({
                topic: topicName,
                partition: partition.id
            });
        });

        group.members = new Map(
            consumerIds.map(id => [id, true])
        );

        group.assignments = assignments;
        group.generation++;

        this.emit("group.rebalanced", {
            groupId,
            generation: group.generation,
            assignments: Object.fromEntries(assignments)
        });

        return assignments;
    }

    poll(groupId, topicName, partitionId, limit = 10) {
        const group = this.groups.get(groupId);

        if (!group) {
            throw new ValidationError("Consumer group does not exist");
        }

        const topic = this.getTopic(topicName);

        if (
            !Number.isInteger(partitionId) ||
            partitionId < 0 ||
            partitionId >= topic.partitions.length
        ) {
            throw new ValidationError("Invalid partition");
        }

        const partition = topic.partitions[partitionId];

        const offset = group.getOffset(topicName, partitionId);

        return partition.read(offset, limit).map(record => ({
            topic: topicName,
            partition: partitionId,
            ...record
        }));
    }

    commit(groupId, topicName, partitionId, nextOffset) {
        const group = this.groups.get(groupId);

        if (!group) {
            throw new ValidationError("Unknown consumer group");
        }

        const topic = this.getTopic(topicName);
        const partition = topic.partitions[partitionId];

        if (!partition) {
            throw new ValidationError("Unknown partition");
        }

        group.commit(
            topicName,
            partitionId,
            nextOffset,
            partition.highWatermark
        );

        this.emit("offset.committed", {
            groupId,
            topic: topicName,
            partition: partitionId,
            nextOffset
        });
    }

    setBrokerAvailability(id, available) {
        const broker = this.brokers.get(id);

        if (!broker) {
            throw new ValidationError("Unknown broker");
        }

        broker.available = Boolean(available);

        this.emit("broker.availability.changed", {
            brokerId: id,
            available: broker.available
        });
    }

    metadata() {
        return {
            brokers: [...this.brokers.values()].map(broker => ({
                id: broker.id,
                available: broker.available,
                partitions: [...broker.partitions]
            })),

            topics: [...this.topics.values()].map(topic => ({
                name: topic.name,
                replicationFactor: topic.replicationFactor,
                partitions: topic.partitions.map(partition => ({
                    id: partition.id,
                    leader: partition.leader,
                    replicas: partition.replicas,
                    recordCount: partition.log.length,
                    highWatermark: partition.highWatermark
                }))
            }))
        };
    }
}

class Producer {
    constructor(cluster, options = {}) {
        this.cluster = cluster;
        this.ack = options.ack ?? AckMode.ALL;
    }

    async send(topic, key, value) {
        // Promise-based interface allows integration with asynchronous
        // processing pipelines while preserving error propagation.
        return Promise.resolve().then(
            () => this.cluster.produce(
                topic,
                key,
                value,
                this.ack
            )
        );
    }

    async sendBatch(topic, messages) {
        const results = [];

        for (const message of messages) {
            results.push(
                await this.send(
                    topic,
                    message.key,
                    message.value
                )
            );
        }

        return results;
    }
}

class Consumer {
    constructor(cluster, groupId, consumerId) {
        this.cluster = cluster;
        this.groupId = groupId;
        this.consumerId = consumerId;

        cluster.getOrCreateGroup(groupId);
    }

    async process(topic, partitionId, handler, limit = 10) {
        const records = this.cluster.poll(
            this.groupId,
            topic,
            partitionId,
            limit
        );

        let processed = 0;

        for (const record of records) {
            await handler(record);
            processed++;
        }

        if (processed > 0) {
            const nextOffset = records[processed - 1].offset + 1;

            this.cluster.commit(
                this.groupId,
                topic,
                partitionId,
                nextOffset
            );
        }

        return processed;
    }
}

async function runDemo() {
    const cluster = new KafkaCluster(3);

    cluster.on("topic.created", event => {
        console.log("TOPIC CREATED:", event);
    });

    cluster.on("record.produced", event => {
        console.log("PRODUCED:", event);
    });

    cluster.on("offset.committed", event => {
        console.log("OFFSET COMMITTED:", event);
    });

    cluster.createTopic("payments", 3, 2);

    const producer = new Producer(cluster, {
        ack: AckMode.ALL
    });

    const messages = [
        {
            key: "account-101",
            value: { paymentId: 1, amount: 500 }
        },
        {
            key: "account-102",
            value: { paymentId: 2, amount: 900 }
        },
        {
            key: "account-101",
            value: { paymentId: 3, amount: 1200 }
        },
        {
            key: "account-103",
            value: { paymentId: 4, amount: 300 }
        }
    ];

    await producer.sendBatch("payments", messages);

    const consumerIds = ["worker-A", "worker-B"];

    const assignments = cluster.rebalance(
        "payment-processors",
        "payments",
        consumerIds
    );

    const completed = [];

    const handler = async record => {
        // Business processing should be idempotent because a crash
        // before offset commit can cause the record to be delivered again.
        completed.push(record.value.paymentId);

        console.log(
            `Processed payment ${record.value.paymentId}`,
            `at offset ${record.offset}`
        );
    };

    for (const [consumerId, partitions] of assignments) {
        const consumer = new Consumer(
            cluster,
            "payment-processors",
            consumerId
        );

        for (const assignment of partitions) {
            await consumer.process(
                assignment.topic,
                assignment.partition,
                handler
            );
        }
    }

    console.log("\nPROCESSED PAYMENT IDS:", completed);

    console.log(
        "\nCLUSTER METADATA:",
        JSON.stringify(cluster.metadata(), null, 2)
    );

    const group = cluster.groups.get("payment-processors");

    console.log(
        "\nCOMMITTED OFFSETS:",
        Object.fromEntries(group.offsets)
    );

    // A failed handler must not advance the committed offset.
    cluster.createTopic("retry-events", 1, 1);

    await producer.send(
        "retry-events",
        "retry-1",
        { task: "reconciliation" }
    );

    const retryConsumer = new Consumer(
        cluster,
        "retry-group",
        "retry-worker"
    );

    try {
        await retryConsumer.process(
            "retry-events",
            0,
            async () => {
                throw new Error("Simulated processing failure");
            }
        );
    } catch (error) {
        console.log("\nEXPECTED PROCESSING FAILURE:", error.message);
    }

    console.log(
        "RETRY OFFSET:",
        cluster.groups.get("retry-group").getOffset(
            "retry-events",
            0
        )
    );

    // Broker availability failure.
    const leader = cluster.getTopic("payments").partitions[0].leader;

    cluster.setBrokerAvailability(leader, false);

    try {
        await producer.send(
            "payments",
            "account-999",
            { paymentId: 999 }
        );
    } catch (error) {
        console.log("\nEXPECTED BROKER FAILURE:", error.message);
    }

    cluster.setBrokerAvailability(leader, true);

    const report = {
        generatedAt: new Date().toISOString(),
        metadata: cluster.metadata(),
        consumerGroups: [...cluster.groups.values()].map(group => ({
            groupId: group.groupId,
            generation: group.generation,
            committedOffsets: Object.fromEntries(group.offsets)
        }))
    };

    await fs.writeFile(
        "kafka_report.json",
        JSON.stringify(report, null, 2),
        { encoding: "utf8", mode: 0o600 }
    );

    console.log("\nReport written to kafka_report.json");
}

runDemo().catch(error => {
    console.error("APPLICATION FAILURE:", error);
    process.exitCode = 1;
});
