#!/usr/bin/env python3
"""
Advanced Apache Kafka: Consumer Groups, Rebalancing, Retention and Replication.

A self-contained simulation of advanced Kafka architecture and operations.

Demonstrates:
- Topics, partitions, records and offsets
- Consumer groups and partition ownership
- Cooperative and eager rebalancing
- Consumer membership and failure detection
- Offset commits and recovery
- Time-based and size-based retention
- Replication, leader election and ISR
- Acknowledgement policies
- Replication failure handling
- Operational validation and assertions

This is an educational broker-state simulation, not a Kafka protocol
implementation or replacement for a Kafka cluster.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)
logger = logging.getLogger("kafka_advanced")


class KafkaError(Exception):
    """Base exception for simulated Kafka operations."""


class ValidationError(KafkaError):
    pass


class AssignmentError(KafkaError):
    pass


class ReplicationError(KafkaError):
    pass


class CommitError(KafkaError):
    pass


class RetentionError(KafkaError):
    pass


class RebalanceProtocol(Enum):
    EAGER = "eager"
    COOPERATIVE = "cooperative"


class Acknowledgement(Enum):
    LEADER = 1
    ALL = -1


class ConsumerState(Enum):
    JOINING = "joining"
    STABLE = "stable"
    LEFT = "left"
    FAILED = "failed"


class BrokerState(Enum):
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True)
class Record:
    offset: int
    key: str
    value: str
    timestamp: float
    size: int


@dataclass
class Partition:
    topic: str
    partition_id: int
    replicas: list[int]
    leader: int
    isr: set[int]
    records: list[Record] = field(default_factory=list)
    log_start_offset: int = 0
    high_watermark: int = 0
    next_offset: int = 0

    def append(self, key: str, value: str, timestamp: float) -> Record:
        if not key or not isinstance(key, str):
            raise ValidationError("Record key must be a non-empty string.")

        if not isinstance(value, str):
            raise ValidationError("Record value must be a string.")

        record = Record(
            offset=self.next_offset,
            key=key,
            value=value,
            timestamp=timestamp,
            size=len(key.encode("utf-8")) + len(value.encode("utf-8"))
        )

        self.records.append(record)
        self.next_offset += 1
        return record

    def readable_records(self, offset: int) -> list[Record]:
        if offset < self.log_start_offset:
            raise RetentionError(
                f"Offset {offset} has expired. "
                f"Log starts at {self.log_start_offset}."
            )

        return [r for r in self.records if r.offset >= offset]


@dataclass
class Broker:
    broker_id: int
    state: BrokerState = BrokerState.ONLINE


@dataclass
class Consumer:
    consumer_id: str
    group_id: str
    subscribed_topics: set[str]
    state: ConsumerState = ConsumerState.JOINING
    assigned: set[tuple[str, int]] = field(default_factory=set)
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class ConsumerGroup:
    group_id: str
    consumers: dict[str, Consumer] = field(default_factory=dict)
    committed_offsets: dict[tuple[str, int], int] = field(default_factory=dict)
    generation: int = 0
    stable: bool = False


class KafkaCluster:
    def __init__(self, min_insync_replicas: int = 2):
        if min_insync_replicas < 1:
            raise ValidationError("Minimum ISR must be at least one.")

        self.min_insync_replicas = min_insync_replicas
        self.brokers: dict[int, Broker] = {}
        self.topics: dict[str, dict[int, Partition]] = {}
        self.groups: dict[str, ConsumerGroup] = {}

    def add_broker(self, broker_id: int) -> None:
        if broker_id in self.brokers:
            raise ValidationError("Broker already exists.")

        self.brokers[broker_id] = Broker(broker_id)

    def create_topic(
        self,
        name: str,
        partition_count: int,
        replication_factor: int
    ) -> None:
        if not name or name in self.topics:
            raise ValidationError("Invalid or duplicate topic name.")

        if partition_count < 1:
            raise ValidationError("Partition count must be positive.")

        if replication_factor < 1:
            raise ValidationError("Replication factor must be positive.")

        online = sorted(
            broker_id for broker_id, broker in self.brokers.items()
            if broker.state == BrokerState.ONLINE
        )

        if replication_factor > len(online):
            raise ValidationError(
                "Replication factor exceeds available online brokers."
            )

        partitions = {}

        for partition_id in range(partition_count):
            replicas = [
                online[(partition_id + index) % len(online)]
                for index in range(replication_factor)
            ]

            partitions[partition_id] = Partition(
                topic=name,
                partition_id=partition_id,
                replicas=replicas,
                leader=replicas[0],
                isr=set(replicas)
            )

        self.topics[name] = partitions
        logger.info("Created topic %s with %d partitions.", name, partition_count)

    def get_partition(self, topic: str, partition_id: int) -> Partition:
        try:
            return self.topics[topic][partition_id]
        except KeyError as exc:
            raise ValidationError("Unknown topic or partition.") from exc

    def produce(
        self,
        topic: str,
        partition_id: int,
        key: str,
        value: str,
        acknowledgement: Acknowledgement = Acknowledgement.ALL
    ) -> Record:
        partition = self.get_partition(topic, partition_id)

        leader = self.brokers[partition.leader]

        if leader.state != BrokerState.ONLINE:
            raise ReplicationError("Partition leader is offline.")

        if acknowledgement == Acknowledgement.ALL:
            online_isr = {
                broker_id for broker_id in partition.isr
                if self.brokers[broker_id].state == BrokerState.ONLINE
            }

            if len(online_isr) < self.min_insync_replicas:
                raise ReplicationError(
                    "Not enough in-sync replicas for acks=all."
                )

        record = partition.append(key, value, time.time())

        # The simulation models successful synchronous replication to ISR.
        # It does not model network transport or physical replica logs.
        if acknowledgement == Acknowledgement.ALL:
            partition.high_watermark = record.offset + 1
        else:
            partition.high_watermark = record.offset + 1

        return record

    def add_consumer(
        self,
        group_id: str,
        consumer_id: str,
        topics: set[str]
    ) -> Consumer:
        if not group_id or not consumer_id or not topics:
            raise ValidationError("Group, consumer and subscriptions are required.")

        unknown = topics.difference(self.topics)

        if unknown:
            raise ValidationError(f"Unknown topics: {sorted(unknown)}")

        group = self.groups.setdefault(group_id, ConsumerGroup(group_id))

        if consumer_id in group.consumers:
            raise ValidationError("Consumer already belongs to this group.")

        consumer = Consumer(
            consumer_id=consumer_id,
            group_id=group_id,
            subscribed_topics=set(topics)
        )

        group.consumers[consumer_id] = consumer
        group.stable = False
        return consumer

    def rebalance(
        self,
        group_id: str,
        protocol: RebalanceProtocol = RebalanceProtocol.COOPERATIVE
    ) -> dict[str, list[tuple[str, int]]]:
        if group_id not in self.groups:
            raise ValidationError("Unknown consumer group.")

        group = self.groups[group_id]

        active = sorted(
            (
                consumer for consumer in group.consumers.values()
                if consumer.state not in (ConsumerState.LEFT, ConsumerState.FAILED)
            ),
            key=lambda consumer: consumer.consumer_id
        )

        if not active:
            group.stable = True
            group.generation += 1
            return {}

        if protocol == RebalanceProtocol.EAGER:
            # Eager assignment revokes all previous ownership before reassignment.
            for consumer in active:
                consumer.assigned.clear()

        assignments = {consumer.consumer_id: set() for consumer in active}

        for topic in sorted(self.topics):
            subscribers = [
                consumer for consumer in active
                if topic in consumer.subscribed_topics
            ]

            if not subscribers:
                continue

            for partition_id in sorted(self.topics[topic]):
                partition_key = (topic, partition_id)

                # Stable deterministic round-robin assignment.
                index = partition_id % len(subscribers)
                assignments[subscribers[index].consumer_id].add(partition_key)

        for consumer in active:
            new_assignment = assignments[consumer.consumer_id]

            if protocol == RebalanceProtocol.COOPERATIVE:
                # Retain ownership only for partitions that remain assigned.
                consumer.assigned.intersection_update(new_assignment)

                # Revoke partitions that moved to another consumer.
                consumer.assigned.update(new_assignment)
            else:
                consumer.assigned = new_assignment

            consumer.state = ConsumerState.STABLE

        group.generation += 1
        group.stable = True

        logger.info(
            "Group %s completed generation %d using %s.",
            group_id,
            group.generation,
            protocol.value
        )

        return {
            consumer_id: sorted(assignment)
            for consumer_id, assignment in assignments.items()
        }

    def heartbeat(self, group_id: str, consumer_id: str) -> None:
        group = self.groups[group_id]
        consumer = group.consumers[consumer_id]

        if consumer.state in (ConsumerState.LEFT, ConsumerState.FAILED):
            raise KafkaError("Inactive consumer cannot send heartbeat.")

        consumer.last_heartbeat = time.time()

    def expire_consumers(self, group_id: str, timeout_seconds: float) -> list[str]:
        if timeout_seconds <= 0:
            raise ValidationError("Timeout must be positive.")

        group = self.groups[group_id]
        now = time.time()
        expired = []

        for consumer in group.consumers.values():
            if consumer.state in (ConsumerState.LEFT, ConsumerState.FAILED):
                continue

            if now - consumer.last_heartbeat > timeout_seconds:
                consumer.state = ConsumerState.FAILED
                consumer.assigned.clear()
                expired.append(consumer.consumer_id)

        if expired:
            group.stable = False

        return expired

    def commit_offset(
        self,
        group_id: str,
        topic: str,
        partition_id: int,
        next_offset: int
    ) -> None:
        group = self.groups[group_id]
        partition = self.get_partition(topic, partition_id)

        if next_offset < partition.log_start_offset:
            raise CommitError("Cannot commit an expired offset.")

        if next_offset > partition.high_watermark:
            raise CommitError("Cannot commit beyond the high watermark.")

        group.committed_offsets[(topic, partition_id)] = next_offset

    def fetch_offset(self, group_id: str, topic: str, partition_id: int) -> int:
        group = self.groups[group_id]
        partition = self.get_partition(topic, partition_id)

        return group.committed_offsets.get(
            (topic, partition_id),
            partition.log_start_offset
        )

    def consume(
        self,
        group_id: str,
        consumer_id: str,
        topic: str,
        partition_id: int
    ) -> list[Record]:
        consumer = self.groups[group_id].consumers[consumer_id]
        partition_key = (topic, partition_id)

        if consumer.state != ConsumerState.STABLE:
            raise AssignmentError("Consumer group is not stable.")

        if partition_key not in consumer.assigned:
            raise AssignmentError("Consumer does not own this partition.")

        offset = self.fetch_offset(group_id, topic, partition_id)
        partition = self.get_partition(topic, partition_id)

        return [
            record for record in partition.readable_records(offset)
            if record.offset < partition.high_watermark
        ]

    def retain(
        self,
        topic: str,
        partition_id: int,
        max_age_seconds: Optional[float] = None,
        max_bytes: Optional[int] = None,
        now: Optional[float] = None
    ) -> int:
        partition = self.get_partition(topic, partition_id)

        if max_age_seconds is None and max_bytes is None:
            raise ValidationError("At least one retention limit is required.")

        if max_age_seconds is not None and max_age_seconds < 0:
            raise ValidationError("Retention age cannot be negative.")

        if max_bytes is not None and max_bytes < 0:
            raise ValidationError("Retention size cannot be negative.")

        current_time = time.time() if now is None else now

        records = list(partition.records)

        if max_age_seconds is not None:
            cutoff = current_time - max_age_seconds
            records = [r for r in records if r.timestamp >= cutoff]

        if max_bytes is not None:
            retained = []
            total = 0

            # Preserve the newest records that fit the size limit.
            for record in reversed(records):
                if total + record.size > max_bytes:
                    break

                retained.append(record)
                total += record.size

            records = list(reversed(retained))

        removed = len(partition.records) - len(records)

        if removed:
            partition.records = records

            if records:
                partition.log_start_offset = records[0].offset
            else:
                partition.log_start_offset = partition.next_offset

        return removed

    def take_broker_offline(self, broker_id: int) -> None:
        broker = self.brokers[broker_id]
        broker.state = BrokerState.OFFLINE

        for partitions in self.topics.values():
            for partition in partitions.values():
                if broker_id not in partition.replicas:
                    continue

                partition.isr.discard(broker_id)

                if partition.leader == broker_id:
                    candidates = sorted(
                        replica for replica in partition.isr
                        if self.brokers[replica].state == BrokerState.ONLINE
                    )

                    if candidates:
                        partition.leader = candidates[0]
                        logger.info(
                            "Partition %s-%d elected leader %d.",
                            partition.topic,
                            partition.partition_id,
                            partition.leader
                        )
                    else:
                        logger.error(
                            "Partition %s-%d has no available ISR leader.",
                            partition.topic,
                            partition.partition_id
                        )

    def restore_broker(self, broker_id: int) -> None:
        broker = self.brokers[broker_id]
        broker.state = BrokerState.ONLINE

        # Returning online does not automatically make a replica caught up.
        # Real Kafka must replicate missing records before ISR re-entry.
        logger.info("Broker %d is online; ISR recovery is not assumed.", broker_id)


def demonstrate() -> None:
    cluster = KafkaCluster(min_insync_replicas=2)

    for broker_id in range(1, 4):
        cluster.add_broker(broker_id)

    cluster.create_topic(
        name="orders",
        partition_count=4,
        replication_factor=3
    )

    for partition_id in range(4):
        cluster.produce(
            "orders",
            partition_id,
            f"order-{partition_id}",
            '{"status":"created"}',
            Acknowledgement.ALL
        )

    cluster.add_consumer("order-processors", "consumer-A", {"orders"})
    cluster.add_consumer("order-processors", "consumer-B", {"orders"})

    assignments = cluster.rebalance(
        "order-processors",
        RebalanceProtocol.COOPERATIVE
    )

    print("\nConsumer assignments:")
    for consumer_id, partitions in assignments.items():
        print(consumer_id, partitions)

    records = cluster.consume(
        "order-processors",
        "consumer-A",
        "orders",
        0
    )

    print("\nConsumed records:")
    for record in records:
        print(record.offset, record.key, record.value)

    cluster.commit_offset("order-processors", "orders", 0, 1)

    print(
        "\nCommitted next offset:",
        cluster.fetch_offset("order-processors", "orders", 0)
    )

    removed = cluster.retain(
        "orders",
        0,
        max_age_seconds=3600,
        max_bytes=1024
    )

    print("Records removed by retention:", removed)

    print("\nSimulating broker failure:")
    cluster.take_broker_offline(1)

    try:
        cluster.produce(
            "orders",
            0,
            "order-failure",
            '{"status":"test"}',
            Acknowledgement.ALL
        )
    except ReplicationError as error:
        print("Expected replication failure:", error)

    cluster.restore_broker(1)

    print("\nFinal partition state:")
    for partition_id, partition in cluster.topics["orders"].items():
        print({
            "partition": partition_id,
            "leader": partition.leader,
            "replicas": partition.replicas,
            "isr": sorted(partition.isr),
            "high_watermark": partition.high_watermark,
            "log_start_offset": partition.log_start_offset
        })


if __name__ == "__main__":
    demonstrate()
