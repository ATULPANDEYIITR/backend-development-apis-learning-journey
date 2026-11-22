# Advanced Apache Kafka: Consumer Groups, Rebalancing, Retention and Replication

## 1. Architecture and Scope

Apache Kafka is a distributed event-streaming platform built around durable, partitioned logs. Its architecture separates message production, message storage, consumer coordination, replication and offset management.

This project develops five complementary implementations of advanced Kafka concepts:

| Implementation | Engineering perspective |
|---|---|
| Python | Repository-independent Kafka cluster and workflow simulation |
| JavaScript | Event-driven consumer coordination and asynchronous processing |
| C++17 | Efficient partition, replication and consumer-group state management |
| Java 17 | Enterprise-oriented domain modeling and operational services |
| PostgreSQL | Relational operational metadata, integrity enforcement and reporting |

The implementations are educational simulations. They model important Kafka behaviors but do not implement the Kafka network protocol, broker storage engine, controller quorum, replication protocol or actual client APIs.

## 2. Kafka's Distributed Architecture

A Kafka cluster consists of brokers that collectively host topics and their partitions.

A topic represents a logical stream of events. Kafka divides the topic into partitions to support parallel processing, horizontal scalability and distributed storage.

**Core relationships**

- A cluster contains brokers.
- A topic contains partitions.
- A partition contains an ordered sequence of records.
- A partition has one leader and zero or more follower replicas.
- A consumer group contains consumers.
- A consumer group coordinates ownership of subscribed partitions.
- Each consumer group maintains independent committed offsets.

A simplified architecture is:

    Producers
        |
        v
    Kafka Cluster
        |
        +-- Broker 1
        |     +-- Partition 0 (Leader)
        |     +-- Partition 1 (Replica)
        |
        +-- Broker 2
        |     +-- Partition 0 (Replica)
        |     +-- Partition 1 (Leader)
        |
        +-- Broker 3
              +-- Partition 0 (Replica)
              +-- Partition 1 (Replica)
        |
        v
    Consumer Group
        |
        +-- Consumer A
        +-- Consumer B
        +-- Consumer C

Partition leadership and consumer ownership are different mechanisms.

A broker leads a partition for producer and replication operations. A consumer owns a partition within a particular consumer group for message processing.

## 3. Consumer Groups

### 3.1 Definition

A consumer group is a collection of consumers that cooperate to process records from subscribed topics.

Consumers within the same group divide partition ownership. This enables parallel consumption while maintaining partition-level processing order.

Each group maintains its own offsets. Two independent groups can consume the same topic without sharing their processing positions.

For example:

| Consumer group | Purpose |
|---|---|
| order-processors | Process incoming orders |
| order-analytics | Calculate order statistics |
| order-audit | Maintain audit records |

Each group independently tracks its progress.

### 3.2 Partition-to-consumer relationship

A partition can be assigned to only one active consumer within a particular group at a given time.

A consumer can own multiple partitions.

For a topic containing eight partitions and four consumers, a balanced assignment could be:

| Consumer | Assigned partitions |
|---|---|
| Consumer A | 0, 4 |
| Consumer B | 1, 5 |
| Consumer C | 2, 6 |
| Consumer D | 3, 7 |

A consumer group with more consumers than available partitions cannot achieve additional partition-level parallelism.

For example, four partitions and six consumers leave at least two consumers without partition assignments.

This is an important capacity-planning consideration.

### 3.3 Consumer membership

A consumer joins a group and provides its subscriptions and membership information.

The group coordinator manages membership and coordinates assignment changes.

Consumers periodically send heartbeats. The coordinator uses membership information and session timeouts to identify inactive consumers.

Relevant concepts include:

- `group.id`: identifies the consumer group.
- `member.id`: identifies a consumer-group member.
- `generation.id`: identifies a group membership generation.
- `session.timeout.ms`: determines when a member can be considered inactive.
- `heartbeat.interval.ms`: controls heartbeat frequency.
- `max.poll.interval.ms`: limits the interval between consumer polling operations.

A consumer that continues heartbeating but fails to make processing progress may require a different failure investigation from one that stops sending heartbeats.

Session timeout and maximum poll interval address different failure conditions.

### 3.4 Consumer offset management

An offset identifies a record's position in a partition.

Consumer offsets are maintained independently for each group and partition.

A committed offset represents the next position from which the consumer group should resume.

For example:

| Processed record | Committed next offset |
|---|---:|
| Record 0 | 1 |
| Record 1 | 2 |
| Record 2 | 3 |
| Record 3 | 4 |

A consumer that has committed offset 4 resumes from offset 4.

Offset management determines recovery behavior after application restarts, consumer failures and rebalancing.

#### Automatic and manual commits

Automatic commits periodically store consumer progress.

Manual commits give the application more control over when progress becomes durable.

Manual commits are particularly useful when message processing includes database writes or external service calls.

The application must carefully coordinate processing and offset commits.

Committing before successful processing can cause message loss from the application's perspective.

Processing successfully and failing before committing can cause the same record to be processed again.

This is why idempotency and transactional processing matter.

### 3.5 Consumer processing guarantees

Kafka consumer applications commonly use three delivery models:

| Model | Meaning | Important consideration |
|---|---|---|
| At-most-once | A record is processed zero or one time | Processing progress may be committed before processing |
| At-least-once | A record may be processed more than once | Duplicate handling is required |
| Exactly-once | Supported processing operations achieve transactional guarantees | Requires appropriate Kafka transaction and application integration |

Exactly-once processing should not be interpreted as a universal guarantee covering arbitrary external systems.

For example, writing to an external payment API requires appropriate idempotency or transaction coordination.

## 4. Rebalancing

### 4.1 Definition

Rebalancing is the process of redistributing partition assignments among consumers in a group.

A rebalance is necessary when the group's membership or subscription requirements change.

Typical triggers include:

- A new consumer joins.
- An existing consumer leaves.
- A consumer fails.
- A subscription changes.
- A topic's partition count changes.
- Group membership metadata changes.

The objective is to establish a valid assignment for the current group generation.

### 4.2 Eager rebalancing

Eager rebalancing revokes existing partition assignments before establishing the new assignment.

Its simplified workflow is:

    Existing Assignment
            |
            v
    Revoke Existing Partitions
            |
            v
    Recalculate Assignment
            |
            v
    Assign Partitions
            |
            v
       Stable Group

This approach can temporarily stop processing across the affected group.

It is straightforward to reason about but can create significant processing interruptions in large groups.

### 4.3 Cooperative rebalancing

Cooperative rebalancing attempts to reduce unnecessary partition revocation.

Partitions that can remain with their existing owners are retained, while only partitions that must move are revoked and reassigned.

Its simplified workflow is:

    Existing Assignment
            |
            v
    Calculate New Assignment
            |
            v
    Identify Partitions to Move
            |
            v
    Revoke Required Partitions
            |
            v
    Transfer Ownership
            |
            v
       Stable Group

Cooperative rebalancing reduces unnecessary disruption.

It does not guarantee that no processing interruption occurs. A partition must not be simultaneously processed by two active owners within the same group.

### 4.4 Rebalancing protocols and assignors

Kafka supports different partition-assignment strategies.

Important examples include:

| Strategy | Characteristics |
|---|---|
| RangeAssignor | Assigns consecutive partition ranges to consumers |
| RoundRobinAssignor | Distributes partitions across eligible consumers |
| StickyAssignor | Attempts to preserve existing ownership while balancing assignments |
| CooperativeStickyAssignor | Supports cooperative reassignment while preserving existing ownership where possible |

The Python, C++ and Java demonstrations use deterministic round-robin assignment to illustrate ownership changes.

The JavaScript implementation also calculates desired assignments and exposes membership changes through events.

These implementations do not reproduce the complete behavior of Kafka's production assignors.

### 4.5 Rebalancing and processing continuity

Rebalancing affects:

- Processing availability.
- Partition ownership.
- Consumer generation.
- Offset management.
- Processing latency.
- Duplicate-processing exposure.

A poorly configured application can repeatedly trigger rebalances, producing a condition commonly described as a rebalance storm.

Possible causes include:

- Excessively aggressive session timeouts.
- Slow processing.
- Frequent consumer restarts.
- Unstable infrastructure.
- Incorrect polling behavior.
- Repeated membership changes.

Operational monitoring should examine rebalance frequency, duration, consumer lag and processing throughput together.

## 5. Kafka Retention

### 5.1 Definition

Kafka retention controls how long records remain available in partition logs.

Kafka is not a conventional message queue in which a successfully consumed record is automatically deleted.

Records can remain available after consumption, allowing multiple independent consumer groups to read the same data.

Retention is primarily configured at the topic or broker level.

### 5.2 Time-based retention

Time-based retention removes records after their retention period expires.

The principal configuration is:

- `retention.ms`

For example:

    retention.ms = 604800000

This represents seven days.

Time-based retention is useful for:

- Event replay.
- Operational recovery.
- Audit history.
- Analytics.
- Reprocessing.
- Temporary event storage.

Retention timing is not a guarantee that every expired record is deleted at the exact expiration instant. Kafka performs log-segment cleanup according to its storage-management processes.

### 5.3 Size-based retention

Size-based retention limits the amount of storage available for a topic.

The relevant configuration is:

- `retention.bytes`

This setting applies per partition rather than representing one global topic-wide limit.

For example, a topic with eight partitions and a configured limit of 1 GB per partition can retain substantially more than 1 GB in aggregate.

Actual storage use also depends on segment files, indexes, replication and filesystem overhead.

### 5.4 Cleanup policies

Kafka provides two important cleanup mechanisms.

| Cleanup policy | Function |
|---|---|
| delete | Removes old log segments according to retention limits |
| compact | Retains the latest value for each key, subject to compaction behavior |

The `compact,delete` policy combines compaction with time- or size-based deletion.

Compaction is particularly useful for state-oriented topics.

For example, a customer-profile topic may contain several updates for the same customer:

| Key | Value |
|---|---|
| customer-101 | Bronze |
| customer-102 | Silver |
| customer-101 | Gold |
| customer-101 | Platinum |

After compaction, the latest value for `customer-101` is retained as the current keyed state, subject to Kafka's compaction and tombstone semantics.

Compaction does not guarantee that every historical record is immediately removed.

### 5.5 Tombstones

A tombstone is a record with a key and a null value.

In a compacted topic, tombstones indicate that the corresponding key should eventually be removed from the retained compacted state.

Tombstones remain available for a configured deletion-retention period before cleanup.

They are important when maintaining replicated state, database change streams and compacted application topics.

### 5.6 Retention and consumer offsets

Retention and committed offsets are independent mechanisms.

Consider:

- Consumer group committed offset: 100.
- Partition log start offset: 150.
- Partition high watermark: 200.

The consumer's previously committed position is now outside the retained log.

This is an offset-out-of-range situation.

The application must apply an appropriate offset-reset policy.

Common settings include:

| Configuration | Behavior |
|---|---|
| earliest | Start from the earliest currently available record |
| latest | Start from the end of the available log |
| none | Raise an error when no valid initial position exists |

Retention should therefore be planned against expected consumer downtime, recovery requirements and replay requirements.

## 6. Kafka Replication

### 6.1 Purpose

Replication maintains copies of partition data across multiple brokers.

It improves fault tolerance and protects against individual broker failures.

Kafka replication operates at the partition level.

Each partition has:

- One leader replica.
- Zero or more follower replicas.
- A replication factor.
- An in-sync replica set.

### 6.2 Replication factor

The replication factor specifies the number of configured copies of each partition.

For example:

    replication.factor = 3

A partition is configured with three replicas distributed across brokers.

A higher replication factor increases storage requirements and replication traffic but can improve resilience against broker failures.

The distribution should consider rack and availability-zone placement.

Replicas placed on the same physical failure domain do not provide equivalent protection against infrastructure-wide failures.

### 6.3 Leader and follower replicas

The leader handles partition operations such as normal producer writes and consumer reads.

Followers replicate records from the leader.

A follower that remains sufficiently synchronized can participate in the in-sync replica set.

Kafka's replication design relies on the leader and replica progress information to manage data durability and recovery.

### 6.4 In-Sync Replicas

ISR means In-Sync Replicas.

It is the set of replicas that are sufficiently caught up with the leader under Kafka's replication rules.

The ISR can change when:

- A broker becomes unavailable.
- Replication falls behind.
- A follower recovers.
- A follower catches up.
- A broker experiences prolonged network interruption.

A replica being online does not automatically mean that it is in the ISR.

A recovering replica must catch up before it can safely rejoin the ISR.

### 6.5 High watermark

The high watermark represents the highest replicated log position that is safe for consumers to read.

A consumer normally cannot read beyond the high watermark in the standard committed-read path.

This prevents consumers from reading records that have not reached the required replication state.

Kafka also maintains other log positions, including the log end offset.

These positions should not be treated as interchangeable.

### 6.6 Producer acknowledgement settings

The `acks` configuration controls the acknowledgement requirement for producer writes.

| Setting | Behavior |
|---|---|
| acks=0 | Producer does not wait for a broker acknowledgement |
| acks=1 | Leader acknowledges after the local write |
| acks=all | Leader waits for the required ISR acknowledgement condition |

With `acks=all`, the `min.insync.replicas` setting determines the minimum number of in-sync replicas required for a successful write.

For example:

    replication.factor = 3
    min.insync.replicas = 2
    acks = all

This configuration allows a write when at least two in-sync replicas are available.

If only one ISR replica remains, the broker rejects the write under this configuration.

This reduces the possibility of acknowledging writes with insufficient replication.

The exact durability outcome also depends on the replication protocol, broker configuration and failure conditions.

### 6.7 Leader election

When a partition leader fails, Kafka elects another eligible replica.

An in-sync replica can become the new leader.

The election process restores partition availability when an eligible replica is available.

If no eligible replica is available, the partition may become unavailable.

Unclean leader election can improve availability by permitting an out-of-sync replica to become leader, but it introduces a risk of losing previously acknowledged data.

It should be treated as an explicit durability-versus-availability decision.

### 6.8 Replication lag

Replication lag represents the difference between the leader's progress and a follower's progress.

A follower with significant lag may be removed from the ISR.

Important operational indicators include:

- Under-replicated partitions.
- Offline partitions.
- ISR shrink and expansion events.
- Replica fetch latency.
- Leader distribution.
- Disk throughput.
- Network throughput.
- Broker availability.

The C++ and Java models expose replica state and leader changes. The SQL model provides replica-health and replication-lag reporting.

## 7. Relationship Between the Four Core Mechanisms

Consumer groups, rebalancing, retention and replication address different operational requirements.

| Mechanism | Primary concern | Main state |
|---|---|---|
| Consumer groups | Parallel event processing | Membership and partition ownership |
| Rebalancing | Ownership redistribution | Group generation and assignments |
| Retention | Data availability over time | Log start offset and retained records |
| Replication | Data durability and fault tolerance | Leader, followers and ISR |

Their relationship becomes clear during a broker failure.

Consider a topic with three replicas and a consumer group processing its partitions.

1. A broker fails.
2. The affected partition loses one replica from its available ISR.
3. An eligible replica may become the new leader.
4. Producer acknowledgement conditions are evaluated against the remaining ISR.
5. Consumers continue reading when the partition remains available.
6. Consumer membership changes only if consumers themselves fail or group membership changes.
7. If a consumer fails, the group coordinator initiates rebalancing.
8. Consumers resume from their committed offsets.
9. Retention determines whether the previously committed records are still available.

A broker failure does not automatically mean that the consumer group must rebalance.

A consumer failure does not automatically mean that the partition leader must change.

These distinctions are essential when diagnosing Kafka incidents.

## 8. Python Implementation

### 8.1 Design

The Python implementation uses a `KafkaCluster` class as the central simulation controller.

The main domain objects are:

| Object | Responsibility |
|---|---|
| Broker | Tracks broker availability |
| Partition | Maintains records, offsets and replication metadata |
| Record | Represents an immutable message |
| Consumer | Maintains subscription and ownership information |
| ConsumerGroup | Maintains membership and committed offsets |
| KafkaCluster | Coordinates cluster operations |

Enums represent broker status, consumer status, rebalance protocol and acknowledgement mode.

Custom exceptions distinguish invalid configuration, assignment problems, replication failures, commit errors and retention errors.

### 8.2 Rebalancing

The `rebalance()` method generates deterministic partition assignments.

The eager strategy clears existing assignments.

The cooperative strategy calculates desired ownership and retains ownership for partitions that remain with the same consumer.

The implementation increments the group generation after each completed rebalance.

### 8.3 Offset recovery

The `commit_offset()` method validates committed offsets against:

- The partition's current log start offset.
- The partition's high watermark.

The `fetch_offset()` method retrieves the next processing position.

The `consume()` method checks that the consumer owns the requested partition and that the group is stable.

### 8.4 Retention

The `retain()` method supports age-based and size-based cleanup.

Size-based retention walks records from newest to oldest and retains complete records within the configured limit.

When records are removed, the log start offset advances.

### 8.5 Replication failure

The cluster can take a broker offline and attempt to elect a new leader from the remaining ISR.

Restoring a broker does not automatically add it back to the ISR.

This distinction reflects the importance of replica synchronization.

## 9. JavaScript Implementation

### 9.1 Event-driven architecture

The JavaScript implementation uses Node.js `EventEmitter`.

Consumer groups publish events for:

- Consumer joining.
- Consumer leaving.
- Consumer failure.
- Rebalance completion.

This design separates state transitions from operational notifications.

An application can subscribe to these events to trigger monitoring, logging or downstream actions.

### 9.2 Asynchronous processing

The `process()` method accepts an asynchronous handler.

It awaits each record's processing before committing the next offset.

This creates explicit sequential processing within a partition.

The design reduces accidental offset advancement before successful handler completion.

It does not create a distributed transaction between Kafka and an external database.

### 9.3 Serialized rebalancing

The rebalance operation uses a Promise chain.

This ensures that concurrent requests to recalculate assignments execute sequentially.

Without serialization, overlapping assignment calculations could publish conflicting group generations.

### 9.4 Event-driven operational monitoring

The implementation emits events such as `leader:elected` and `partition:unavailable`.

These events illustrate how cluster-state changes can be exposed to operational monitoring components.

### 9.5 Failure handling

The JavaScript implementation validates subscriptions, consumer membership, message payloads, committed offsets and retention settings.

Errors are propagated through asynchronous operations and handled by the main execution function.

## 10. C++17 Implementation

### 10.1 Domain modeling

The C++ program models brokers, records, partitions, consumers and consumer groups using structs and classes.

Its central `KafkaGovernanceEngine` manages:

- Broker registration.
- Topic creation.
- Replica placement.
- Message production.
- Consumer membership.
- Partition assignment.
- Offset commits.
- Broker failure.
- Leader election.

### 10.2 STL-based state management

The implementation uses:

| Structure | Purpose |
|---|---|
| `unordered_map` | Efficient broker lookup |
| `map` | Deterministic topic and group traversal |
| `vector` | Ordered partition replicas and records |
| `set` | Unique ISR members and partition ownership |
| `algorithm` | Sorting, searching and retention filtering |

The design favors deterministic behavior for reproducible demonstrations.

### 10.3 Retention algorithms

The age-based cleanup uses `remove_if` to filter expired records.

The size-based cleanup walks the log backwards and preserves the newest records that fit the limit.

The implementation operates on complete records rather than truncating individual message payloads.

### 10.4 Failure handling

The broker-failure method removes an unavailable broker from affected ISR sets.

When the failed broker was a partition leader, an available ISR candidate is elected.

If no eligible candidate exists, the operation raises an exception.

The example demonstrates how replica availability influences write durability and partition availability.

## 11. Java 17 Implementation

### 11.1 Enterprise-oriented design

The Java implementation uses domain classes, records, enums and service-oriented responsibilities.

The `KafkaCluster` coordinates cluster operations, while `KafkaPartition` manages partition-local state.

Records represent immutable data structures such as:

- `PartitionKey`
- `KafkaRecord`

Enums represent explicit operational states.

This reduces ambiguity in state transitions.

### 11.2 Concurrency considerations

Synchronized cluster operations protect shared metadata in the demonstration.

`AtomicLong` tracks the number of produced records.

The implementation uses immutable collection copies for externally exposed assignments and replica information.

These mechanisms illustrate basic thread-safety boundaries.

They do not reproduce Kafka's distributed concurrency and coordination mechanisms.

### 11.3 Operational policy separation

The `ReviewPolicy` class illustrates how operational authorization rules can be modeled independently of consumer-group behavior.

Its eligible-reviewer rules are not Kafka approval mechanisms.

This separation is useful in enterprise platforms where technical execution and organizational authorization have different responsibilities.

### 11.4 Failure states

The Java implementation models:

- Invalid cluster configuration.
- Duplicate broker registration.
- Duplicate consumer membership.
- Missing partitions.
- Invalid offset commits.
- Insufficient ISR.
- Broker failures.
- Missing leader-election candidates.

Custom exceptions provide more specific failure categories.

## 12. PostgreSQL Implementation

### 12.1 Relational architecture

The SQL implementation provides a relational model for Kafka operational metadata.

Its main entities are:

| Table | Responsibility |
|---|---|
| brokers | Broker registration and availability |
| topics | Topic configuration |
| partitions | Partition metadata and log positions |
| partition_replicas | Replica placement and ISR membership |
| consumer_groups | Group identity and generation |
| consumers | Consumer membership |
| consumer_subscriptions | Topic subscriptions |
| partition_assignments | Consumer-to-partition ownership |
| messages | Message metadata |
| consumer_offsets | Committed group offsets |
| producer_events | Producer acknowledgement outcomes |
| operational_events | Operational audit history |

Foreign keys maintain entity relationships.

Unique constraints prevent duplicate topic names, broker hostnames and replica placements.

Check constraints enforce valid configuration values and offset ranges.

### 12.2 Referential integrity

A partition must reference an existing topic.

A replica must reference an existing broker and partition.

A consumer must reference an existing group.

A committed offset must reference an existing group and partition.

Cascading deletion is applied to selected dependent metadata where it is appropriate.

### 12.3 Triggers and functions

The SQL script defines database functions for:

- Replica configuration validation.
- Committed-offset validation.
- Consumer heartbeat updates.
- Consumer failure detection.
- Consumer-group rebalancing.
- Producer eligibility.
- Time-based retention processing.

The offset-validation trigger checks whether a committed offset falls between the log start offset and high watermark.

The replica-validation trigger enforces configured replication limits and requires a leader replica to belong to the ISR.

These constraints protect relational metadata against invalid operations.

They do not replace Kafka broker-side validation.

### 12.4 Rebalancing procedure

The `rebalance_consumer_group()` function:

1. Locks the consumer-group row.
2. Increments the group generation.
3. Revokes previous active assignments.
4. Finds eligible subscribed consumers.
5. Calculates deterministic partition ownership.
6. Inserts new assignment records.
7. Marks the group stable.
8. Records an operational event.

The transaction protects the database-side assignment update from partial completion.

This is a relational simulation of assignment management, not Kafka's actual group coordinator protocol.

### 12.5 Reporting views

Two important views are provided.

**replica_health**

Reports configured replicas, available ISR members, leader information and partition health.

**consumer_lag**

Calculates the difference between the high watermark and the committed offset.

Consumer lag is an operational indicator of processing progress.

A high lag value may indicate slow processing, insufficient consumers, an upstream production spike or a consumer failure.

Lag should be interpreted together with event production rate and processing throughput.

### 12.6 Transaction handling

The SQL implementation uses transactions for metadata operations.

The offset-commit procedure performs an upsert, updating an existing committed offset or creating a new one.

The demonstration also includes an invalid offset insertion to illustrate constraint enforcement and exception handling.

## 13. Important Configuration Parameters

The following Kafka configurations are particularly relevant to production environments.

### Consumer configuration

| Parameter | Purpose |
|---|---|
| `group.id` | Consumer-group identity |
| `enable.auto.commit` | Controls automatic offset commits |
| `auto.commit.interval.ms` | Automatic commit frequency |
| `auto.offset.reset` | Behavior when no valid committed offset exists |
| `session.timeout.ms` | Consumer membership failure detection |
| `heartbeat.interval.ms` | Heartbeat frequency |
| `max.poll.interval.ms` | Maximum permitted interval between polls |
| `max.poll.records` | Maximum records returned by a poll |
| `partition.assignment.strategy` | Consumer partition assignment strategy |

### Topic and retention configuration

| Parameter | Purpose |
|---|---|
| `num.partitions` | Default partition count for new topics |
| `default.replication.factor` | Default replica count |
| `retention.ms` | Time-based retention |
| `retention.bytes` | Per-partition size-based retention |
| `cleanup.policy` | Log deletion and compaction behavior |
| `segment.ms` | Log-segment rolling interval |
| `segment.bytes` | Maximum segment size |

### Broker replication configuration

| Parameter | Purpose |
|---|---|
| `min.insync.replicas` | Minimum ISR count for qualifying writes |
| `replica.lag.time.max.ms` | Replica lag evaluation |
| `unclean.leader.election.enable` | Whether out-of-sync replicas can become leaders |
| `default.replication.factor` | Default topic replication factor |
| `num.replica.fetchers` | Number of follower replication fetchers |
| `replica.fetch.max.bytes` | Maximum replica fetch response size |

Actual values should be chosen according to workload, durability requirements, infrastructure capacity and recovery objectives.

## 14. Performance and Scalability

### 14.1 Partition count

Increasing the number of partitions can improve processing parallelism.

It also increases:

- Broker metadata overhead.
- File and segment management.
- Replication traffic.
- Consumer assignment complexity.
- Operational monitoring requirements.

A large partition count is not automatically a better architecture.

### 14.2 Consumer-group scaling

Consumer parallelism is constrained by the number of partitions available to the group.

Adding consumers beyond that number may not increase throughput.

Throughput also depends on message size, application processing time, network bandwidth, broker disk performance and downstream system capacity.

### 14.3 Rebalancing efficiency

Frequent rebalances can interrupt processing.

Stable consumer membership and appropriate timeout configurations help reduce unnecessary assignment changes.

Cooperative assignment strategies can reduce the number of partitions that must be revoked.

### 14.4 Replication overhead

Replication increases storage requirements and network traffic.

For a topic containing 100 GB of logical data with a replication factor of three, approximately 300 GB of replicated data is required before accounting for indexes, segment overhead and other storage considerations.

Replica placement across independent failure domains improves resilience.

### 14.5 Retention and storage planning

Storage planning should consider:

- Average production throughput.
- Peak production throughput.
- Message size.
- Retention duration.
- Replication factor.
- Compression ratio.
- Segment and index overhead.
- Recovery requirements.

A rough logical storage estimate is:

    Storage =
        Production Rate
        × Average Record Size
        × Retention Duration
        × Replication Factor

This estimate is a planning approximation, not a precise broker disk-capacity calculation.

## 15. Security and Reliability Considerations

Production Kafka deployments require controls beyond partition assignment and replication.

Important security measures include:

- TLS encryption for broker and client communication.
- SASL authentication where appropriate.
- ACL-based authorization.
- Separate producer and consumer permissions.
- Restricted administrative access.
- Network segmentation.
- Credential rotation.
- Encryption and access control for operational metadata.
- Monitoring of unauthorized access attempts.

Reliability measures include:

- Replicas distributed across failure domains.
- Appropriate `min.insync.replicas`.
- Producer acknowledgement configuration.
- Controlled leader-election policies.
- Consumer idempotency.
- Offset-commit discipline.
- Monitoring of under-replicated partitions.
- Retention planning.
- Tested disaster-recovery procedures.

Kafka replication alone is not a complete disaster-recovery strategy.

Replication within one cluster does not necessarily protect against accidental deletion, application-level corruption or a cluster-wide infrastructure failure.

## 16. Operational Failure Scenarios

| Scenario | Potential consequence | Operational response |
|---|---|---|
| Consumer stops heartbeating | Group membership failure | Detect failure and rebalance |
| Consumer processing becomes slow | Increased lag or poll timeout | Investigate processing and polling |
| Consumer commits too early | Application-level message loss | Correct processing and commit order |
| Consumer commits too late | Duplicate processing | Implement idempotent handling |
| Broker leader fails | Leader election required | Elect an eligible ISR replica |
| ISR falls below minimum | `acks=all` writes may fail | Restore replication capacity |
| Follower falls behind | ISR shrink | Investigate network and disk performance |
| Retention expires unprocessed records | Previous offsets may become unavailable | Apply an explicit offset-reset policy |
| Too many consumers join | Rebalancing overhead | Review partition count and membership |
| Repeated consumer restarts | Rebalance instability | Investigate deployment and health checks |

## 17. Implementation Limitations

The five implementations focus on core mechanisms and deterministic demonstrations.

They intentionally do not implement every Kafka production feature.

| Feature | Implementation status |
|---|---|
| Topic and partition modeling | Implemented |
| Consumer-group membership | Implemented |
| Deterministic partition assignment | Implemented |
| Eager rebalancing | Simulated |
| Cooperative rebalancing | Simulated |
| Offset commits | Implemented in the simulation |
| Consumer failure detection | Implemented or modeled |
| Time-based retention | Implemented |
| Size-based retention | Implemented |
| Leader and follower metadata | Implemented |
| ISR tracking | Implemented |
| Leader election | Simulated |
| Physical replica synchronization | Not implemented |
| Kafka network protocol | Not implemented |
| Kafka controller quorum | Not implemented |
| Transactional producer protocol | Not implemented |
| Actual broker storage engine | Not implemented |
| Kafka Connect integration | Not implemented |
| Schema Registry integration | Not implemented |
| Distributed exactly-once processing | Not implemented |

The Python, JavaScript, C++17 and Java 17 programs use simplified in-memory cluster state.

Their replication models assume successful synchronization for accepted writes rather than transmitting records between physical brokers.

The PostgreSQL implementation stores operational metadata and demonstrates relational integrity. It is not a substitute for Kafka's distributed log.

## 18. Execution and Validation

### Python

Requirements:

- Python 3.10 or later.
- Standard library only.

Run the script directly.

The demonstration creates a three-broker cluster, produces records, joins consumers, rebalances the group, commits offsets, applies retention and simulates broker failure.

### JavaScript

Requirements:

- Node.js 18 or later.
- Standard library only.

Run the JavaScript file with Node.js.

The demonstration uses asynchronous processing and event-driven notifications.

### C++17

Requirements:

- C++17-compatible compiler.
- Standard library only.

Compile using C++17 support.

The demonstration exercises topic creation, replication, partition assignment, offset commits, retention and broker failure.

### Java 17

Requirements:

- JDK 17.
- Standard Java libraries only.

Compile and execute the `KafkaAdvanced` class.

The demonstration exercises enterprise-oriented cluster operations and typed domain models.

### PostgreSQL

Requirements:

- PostgreSQL 15 or later.
- Permission to create schemas, tables, functions, procedures and triggers.

Execute the SQL script in a database where the deployment role has the necessary privileges.

The script creates its own `kafka_ops` schema and inserts representative broker, topic, partition, consumer, replica, offset and message records.

The database script should be executed as a single deployment operation because its tables, functions, triggers and sample data depend on the preceding definitions.

## 19. Technical Learning Outcomes

The implementations establish the following distinctions:

1. A consumer group provides coordinated parallel processing, not broker replication.
2. Rebalancing changes partition ownership, not the underlying partition data.
3. Consumer offsets represent processing progress, not record deletion.
4. Retention controls record availability, not consumer membership.
5. Replication maintains partition copies, not application processing guarantees.
6. The leader handles normal partition operations, while followers maintain replicated copies.
7. ISR membership indicates replication synchronization, not merely broker availability.
8. `acks=all` and `min.insync.replicas` jointly influence producer write durability.
9. Cooperative rebalancing reduces unnecessary partition revocation but does not eliminate every processing interruption.
10. Reliable Kafka applications require coordinated decisions about partitioning, consumer processing, offset management, retention and replication.

These mechanisms collectively determine the scalability, durability, processing continuity and operational reliability of a Kafka-based event-streaming architecture.
