from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("kafka-fundamentals")


class KafkaError(Exception):
    pass


class ValidationError(KafkaError):
    pass


class TopicNotFoundError(KafkaError):
    pass


class OffsetError(KafkaError):
    pass


class ConsumerGroupError(KafkaError):
    pass


class Acknowledgment(Enum):
    NONE = "none"
    LEADER = "leader"
    ALL = "all"


@dataclass(frozen=True)
class Message:
    key: str | None
    value: dict[str, Any]
    timestamp: float
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class StoredRecord:
    offset: int
    message: Message


@dataclass
class Partition:
    partition_id: int
    leader_broker: int
    replicas: list[int]
    records: list[StoredRecord] = field(default_factory=list)

    @property
    def next_offset(self) -> int:
        return len(self.records)

    def append(self, message: Message) -> int:
        offset = self.next_offset
        self.records.append(StoredRecord(offset, message))
        return offset

    def read(self, offset: int, limit: int) -> list[StoredRecord]:
        if offset < 0:
            raise OffsetError("Offset cannot be negative")

        if limit <= 0:
            raise ValidationError("Read limit must be positive")

        return self.records[offset:offset + limit]


@dataclass
class Topic:
    name: str
    partitions: list[Partition]
    replication_factor: int
    created_at: float = field(default_factory=time.time)


@dataclass
class ConsumerGroup:
    group_id: str
    committed_offsets: dict[tuple[str, int], int] = field(
        default_factory=dict
    )
    assignments: dict[str, list[tuple[str, int]]] = field(
        default_factory=dict
    )


@dataclass
class Broker:
    broker_id: int
    available: bool = True
    hosted_partitions: set[tuple[str, int]] = field(
        default_factory=set
    )


class KafkaCluster:
    """
    An in-memory educational Kafka-style cluster.

    This simulation demonstrates partitioned logs, broker ownership,
    producer acknowledgments, consumer offsets, and group assignments.

    It does not implement Kafka networking, replication protocols,
    transactions, or durable disk storage.
    """

    def __init__(self, broker_count: int = 3):
        if broker_count < 1:
            raise ValidationError("At least one broker is required")

        self.brokers = {
            i: Broker(i) for i in range(1, broker_count + 1)
        }
        self.topics: dict[str, Topic] = {}
        self.consumer_groups: dict[str, ConsumerGroup] = {}
        self.lock = threading.RLock()

    def create_topic(
        self,
        name: str,
        partition_count: int = 3,
        replication_factor: int = 2
    ) -> Topic:
        with self.lock:
            if not name or not name.strip():
                raise ValidationError("Topic name cannot be empty")

            if name in self.topics:
                raise ValidationError(f"Topic already exists: {name}")

            if partition_count < 1:
                raise ValidationError("Partition count must be positive")

            if not 1 <= replication_factor <= len(self.brokers):
                raise ValidationError("Invalid replication factor")

            partitions = []

            broker_ids = sorted(self.brokers)

            for partition_id in range(partition_count):
                leader_index = partition_id % len(broker_ids)

                replicas = [
                    broker_ids[(leader_index + i) % len(broker_ids)]
                    for i in range(replication_factor)
                ]

                partition = Partition(
                    partition_id=partition_id,
                    leader_broker=replicas[0],
                    replicas=replicas
                )

                partitions.append(partition)

                for broker_id in replicas:
                    self.brokers[broker_id].hosted_partitions.add(
                        (name, partition_id)
                    )

            topic = Topic(
                name=name,
                partitions=partitions,
                replication_factor=replication_factor
            )

            self.topics[name] = topic

            logger.info(
                "Created topic=%s partitions=%d replication=%d",
                name,
                partition_count,
                replication_factor
            )

            return topic

    def get_topic(self, name: str) -> Topic:
        try:
            return self.topics[name]
        except KeyError:
            raise TopicNotFoundError(name) from None

    def select_partition(
        self,
        topic: Topic,
        key: str | None
    ) -> Partition:
        if key is None:
            return topic.partitions[0]

        # Stable key routing ensures records with the same key
        # are assigned to the same partition.
        partition_id = hash(key) % len(topic.partitions)
        return topic.partitions[partition_id]

    def produce(
        self,
        topic_name: str,
        value: dict[str, Any],
        key: str | None = None,
        acknowledgment: Acknowledgment = Acknowledgment.ALL
    ) -> dict[str, Any]:
        with self.lock:
            if not isinstance(value, dict):
                raise ValidationError("Message value must be a dictionary")

            if acknowledgment == Acknowledgment.NONE:
                raise ValidationError(
                    "This simulation requires leader or all acknowledgments"
                )

            topic = self.get_topic(topic_name)
            partition = self.select_partition(topic, key)

            leader = self.brokers[partition.leader_broker]

            if not leader.available:
                raise KafkaError("Partition leader is unavailable")

            if acknowledgment == Acknowledgment.ALL:
                available_replicas = sum(
                    self.brokers[broker_id].available
                    for broker_id in partition.replicas
                )

                if available_replicas != len(partition.replicas):
                    raise KafkaError(
                        "Not all configured replicas are available"
                    )

            message = Message(
                key=key,
                value=value,
                timestamp=time.time()
            )

            offset = partition.append(message)

            logger.info(
                "Produced topic=%s partition=%d offset=%d",
                topic_name,
                partition.partition_id,
                offset
            )

            return {
                "topic": topic_name,
                "partition": partition.partition_id,
                "offset": offset,
                "message_id": message.message_id
            }

    def create_consumer_group(self, group_id: str) -> ConsumerGroup:
        if not group_id or not group_id.strip():
            raise ValidationError("Consumer group ID is required")

        with self.lock:
            if group_id in self.consumer_groups:
                return self.consumer_groups[group_id]

            group = ConsumerGroup(group_id)
            self.consumer_groups[group_id] = group
            return group

    def assign_partitions(
        self,
        group_id: str,
        topic_name: str,
        consumer_ids: list[str]
    ) -> dict[str, list[tuple[str, int]]]:
        with self.lock:
            if not consumer_ids:
                raise ValidationError("At least one consumer is required")

            if len(set(consumer_ids)) != len(consumer_ids):
                raise ValidationError("Consumer IDs must be unique")

            topic = self.get_topic(topic_name)
            group = self.create_consumer_group(group_id)

            assignments = {
                consumer_id: [] for consumer_id in consumer_ids
            }

            # Each partition is assigned to at most one consumer
            # within the same consumer group.
            for index, partition in enumerate(topic.partitions):
                consumer_id = consumer_ids[index % len(consumer_ids)]

                assignments[consumer_id].append(
                    (topic_name, partition.partition_id)
                )

            group.assignments = assignments

            return assignments

    def consume(
        self,
        group_id: str,
        topic_name: str,
        partition_id: int,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        with self.lock:
            if group_id not in self.consumer_groups:
                raise ConsumerGroupError("Unknown consumer group")

            topic = self.get_topic(topic_name)

            if not 0 <= partition_id < len(topic.partitions):
                raise ValidationError("Invalid partition ID")

            group = self.consumer_groups[group_id]
            partition = topic.partitions[partition_id]

            committed = group.committed_offsets.get(
                (topic_name, partition_id),
                0
            )

            records = partition.read(committed, limit)

            return [
                {
                    "topic": topic_name,
                    "partition": partition_id,
                    "offset": record.offset,
                    "key": record.message.key,
                    "value": record.message.value,
                    "message_id": record.message.message_id
                }
                for record in records
            ]

    def commit_offset(
        self,
        group_id: str,
        topic_name: str,
        partition_id: int,
        next_offset: int
    ) -> None:
        with self.lock:
            if group_id not in self.consumer_groups:
                raise ConsumerGroupError("Unknown consumer group")

            topic = self.get_topic(topic_name)

            if not 0 <= partition_id < len(topic.partitions):
                raise ValidationError("Invalid partition ID")

            partition = topic.partitions[partition_id]

            if not 0 <= next_offset <= partition.next_offset:
                raise OffsetError("Cannot commit an unavailable offset")

            group = self.consumer_groups[group_id]
            key = (topic_name, partition_id)

            previous = group.committed_offsets.get(key, 0)

            if next_offset < previous:
                raise OffsetError(
                    "Committed offsets cannot move backwards in this model"
                )

            group.committed_offsets[key] = next_offset

            logger.info(
                "Committed group=%s topic=%s partition=%d next_offset=%d",
                group_id,
                topic_name,
                partition_id,
                next_offset
            )

    def broker_status(self) -> list[dict[str, Any]]:
        return [
            {
                "broker_id": broker.broker_id,
                "available": broker.available,
                "hosted_partitions": sorted(broker.hosted_partitions)
            }
            for broker in self.brokers.values()
        ]

    def set_broker_availability(
        self,
        broker_id: int,
        available: bool
    ) -> None:
        if broker_id not in self.brokers:
            raise ValidationError("Unknown broker")

        self.brokers[broker_id].available = available

    def topic_metadata(self, topic_name: str) -> dict[str, Any]:
        topic = self.get_topic(topic_name)

        return {
            "topic": topic.name,
            "replication_factor": topic.replication_factor,
            "partitions": [
                {
                    "partition_id": partition.partition_id,
                    "leader": partition.leader_broker,
                    "replicas": partition.replicas,
                    "record_count": len(partition.records),
                    "next_offset": partition.next_offset
                }
                for partition in topic.partitions
            ]
        }


class Producer:
    def __init__(
        self,
        cluster: KafkaCluster,
        acknowledgment: Acknowledgment = Acknowledgment.ALL
    ):
        self.cluster = cluster
        self.acknowledgment = acknowledgment

    def send(
        self,
        topic: str,
        key: str | None,
        value: dict[str, Any]
    ) -> dict[str, Any]:
        return self.cluster.produce(
            topic,
            value,
            key,
            self.acknowledgment
        )

    def send_batch(
        self,
        topic: str,
        messages: list[tuple[str | None, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        results = []

        for key, value in messages:
            results.append(self.send(topic, key, value))

        return results


class Consumer:
    def __init__(
        self,
        cluster: KafkaCluster,
        group_id: str,
        consumer_id: str
    ):
        self.cluster = cluster
        self.group_id = group_id
        self.consumer_id = consumer_id
        self.cluster.create_consumer_group(group_id)

    def poll(
        self,
        topic: str,
        partition_id: int,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        return self.cluster.consume(
            self.group_id,
            topic,
            partition_id,
            limit
        )

    def process(
        self,
        topic: str,
        partition_id: int,
        handler: Callable[[dict[str, Any]], None],
        limit: int = 10
    ) -> int:
        records = self.poll(topic, partition_id, limit)

        if not records:
            return 0

        processed = 0

        for record in records:
            # Commit only after successful processing.
            handler(record)
            processed += 1

        next_offset = records[-1]["offset"] + 1

        self.cluster.commit_offset(
            self.group_id,
            topic,
            partition_id,
            next_offset
        )

        return processed


def write_json_report(
    cluster: KafkaCluster,
    destination: str = "kafka_report.json"
) -> None:
    report = {
        "brokers": cluster.broker_status(),
        "topics": {
            name: cluster.topic_metadata(name)
            for name in cluster.topics
        },
        "consumer_groups": {
            group_id: {
                "committed_offsets": {
                    f"{topic}:{partition}": offset
                    for (topic, partition), offset
                    in group.committed_offsets.items()
                },
                "assignments": group.assignments
            }
            for group_id, group in cluster.consumer_groups.items()
        }
    }

    # Use a temporary file followed by replacement to avoid
    # leaving a partially written report.
    path = Path(destination)
    temporary = path.with_suffix(path.suffix + ".tmp")

    try:
        temporary.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8"
        )
        temporary.replace(path)
    except OSError:
        logger.exception("Could not write report")
        raise


def demonstrate() -> None:
    cluster = KafkaCluster(broker_count=3)

    cluster.create_topic(
        "orders",
        partition_count=3,
        replication_factor=2
    )

    producer = Producer(cluster, Acknowledgment.ALL)

    messages = [
        ("customer-101", {"order_id": 1001, "amount": 2500}),
        ("customer-102", {"order_id": 1002, "amount": 1800}),
        ("customer-101", {"order_id": 1003, "amount": 4200}),
        ("customer-103", {"order_id": 1004, "amount": 900})
    ]

    results = producer.send_batch("orders", messages)

    print("\nPRODUCER RESULTS")

    for result in results:
        print(result)

    group_id = "order-processing-group"

    consumers = ["consumer-1", "consumer-2"]

    assignments = cluster.assign_partitions(
        group_id,
        "orders",
        consumers
    )

    print("\nPARTITION ASSIGNMENTS")

    for consumer_id, partitions in assignments.items():
        print(consumer_id, partitions)

    processed_orders = []

    def order_handler(record: dict[str, Any]) -> None:
        processed_orders.append(record["value"])
        logger.info(
            "Processed offset=%d order=%s",
            record["offset"],
            record["value"]["order_id"]
        )

    print("\nCONSUMPTION")

    for consumer_id in consumers:
        consumer = Consumer(cluster, group_id, consumer_id)

        for topic, partition_id in assignments[consumer_id]:
            count = consumer.process(
                topic,
                partition_id,
                order_handler
            )
            print(
                consumer_id,
                topic,
                partition_id,
                count
            )

    print("\nPROCESSED ORDERS")
    print(processed_orders)

    print("\nTOPIC METADATA")
    print(json.dumps(cluster.topic_metadata("orders"), indent=2))

    print("\nBROKER STATUS")
    print(json.dumps(cluster.broker_status(), indent=2))

    # Re-reading begins at the committed next offset.
    consumer = Consumer(cluster, group_id, "consumer-1")

    first_partition = assignments["consumer-1"][0][1]

    print("\nAFTER OFFSET COMMIT")
    print(consumer.poll("orders", first_partition))

    # Failure scenario: leader unavailability.
    topic = cluster.get_topic("orders")
    leader = topic.partitions[0].leader_broker

    cluster.set_broker_availability(leader, False)

    try:
        producer.send(
            "orders",
            "customer-999",
            {"order_id": 9999, "amount": 500}
        )
    except KafkaError as error:
        print("\nEXPECTED BROKER FAILURE:", error)

    cluster.set_broker_availability(leader, True)

    # Invalid offset scenario.
    try:
        cluster.commit_offset(
            group_id,
            "orders",
            0,
            999999
        )
    except OffsetError as error:
        print("\nEXPECTED OFFSET FAILURE:", error)

    # Assertions verify important invariants.
    assert len(processed_orders) == len(messages)

    for partition in cluster.get_topic("orders").partitions:
        assert partition.next_offset == len(partition.records)

    write_json_report(cluster)

    print("\nReport written to kafka_report.json")


if __name__ == "__main__":
    demonstrate()
