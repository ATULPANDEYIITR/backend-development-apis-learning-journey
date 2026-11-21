# Kafka Fundamentals: Topics, Partitions, Brokers, Producers, Consumers, and Offsets

## 1. Kafka Architecture

Apache Kafka is a distributed event-streaming platform designed to publish, store, and consume records across multiple machines.

Its architecture separates message production, message storage, and message consumption.

The principal components are:

| Component | Responsibility |
|---|---|
| Broker | Stores partitions and handles client requests |
| Topic | Logical category to which records are published |
| Partition | Ordered, append-only sequence of records |
| Producer | Publishes records to topic partitions |
| Consumer | Retrieves and processes records |
| Consumer group | Coordinates multiple consumers |
| Offset | Identifies a record's position within a partition |
| Replication | Maintains copies of partition data across brokers |
| Coordinator | Manages consumer-group membership and assignments |

A typical event-processing architecture follows this structure:

    Application
        |
        v
    Producer
        |
        v
    Kafka Cluster
        |
        +------ Broker 1
        |          |
        |          +------ Topic A / Partition 0
        |          +------ Topic B / Partition 1
        |
        +------ Broker 2
        |          |
        |          +------ Topic A / Partition 1
        |          +------ Topic B / Partition 0
        |
        +------ Broker 3
                   |
                   +------ Replicated partitions

        |
        v
    Consumer Groups
        |
        +------ Consumer 1
        +------ Consumer 2
        +------ Consumer 3

The implementations use an in-memory educational model to demonstrate these mechanisms. They do not implement the Kafka network protocol or replace a production Kafka cluster.

## 2. Topics

A topic is a named stream of records.

Applications publish related events to the same topic.

Examples:

| Topic | Example records |
|---|---|
| `orders` | Order creation, payment, cancellation |
| `payments` | Payment authorization and settlement |
| `inventory` | Stock changes and product updates |
| `notifications` | Email, SMS, and application notifications |
| `user-events` | Registration, login, and account changes |

A topic provides logical organization. It does not imply that all records are stored in one physical location.

Kafka distributes topic data across partitions.

### Topic configuration

Important topic properties include:

- Partition count: Number of independent partition logs.
- Replication factor: Number of configured copies of each partition.
- Retention: How long records remain available under the configured retention policy.
- Cleanup policy: Whether records are removed according to retention or compacted according to keys.

A topic with three partitions and replication factor two has three logical partitions and six configured replica placements.

The replica count is:

`Partition Count × Replication Factor`

For example:

`3 × 2 = 6 replica placements`

The number of unique brokers hosting these replicas depends on the cluster topology.

## 3. Partitions

A partition is an ordered, append-only log.

Each record receives an offset within its partition.

Consider a topic containing three partitions:

| Partition | Offset | Record |
|---|---:|---|
| 0 | 0 | Order A |
| 0 | 1 | Order B |
| 0 | 2 | Order C |
| 1 | 0 | Order D |
| 1 | 1 | Order E |
| 2 | 0 | Order F |

The ordering guarantee applies within a partition.

Kafka does not provide a general total ordering across all partitions of a topic.

### Partitioning and parallelism

Partitions allow different consumers to process different subsets of a topic simultaneously.

For example:

    Orders Topic
        |
        +------ Partition 0 ---> Consumer 1
        |
        +------ Partition 1 ---> Consumer 2
        |
        +------ Partition 2 ---> Consumer 3

Within one consumer group, a partition is assigned to at most one active consumer at a time.

Consequently:

- Three partitions can support up to three simultaneously active consumers for that topic within one group.
- Five consumers with three partitions leave at least two consumers without a partition assignment.
- One consumer can process multiple partitions.
- Multiple consumer groups can independently read the same topic.

Increasing the partition count can improve parallel processing capacity, but it also introduces additional operational and resource costs.

Partition-count changes can also affect key-based partition routing.

### Partition keys

A producer can provide a key when publishing a record.

The partitioning strategy generally uses the key to determine the destination partition.

Records with the same key are normally routed to the same partition under a consistent partitioning strategy.

Example:

| Message key | Event | Partition |
|---|---|---:|
| `customer-101` | Order created | 0 |
| `customer-102` | Order created | 1 |
| `customer-101` | Payment completed | 0 |
| `customer-103` | Order created | 2 |

This arrangement preserves the relative order of events for a key within its partition.

A key should be selected according to the ordering and distribution requirements of the application.

A highly concentrated key can create a hot partition and limit effective parallelism.

## 4. Brokers

A broker is a Kafka server responsible for storing partition replicas and serving client operations.

A Kafka cluster normally contains multiple brokers.

Each partition has a leader replica and may have follower replicas.

### Leader replicas

The leader handles normal read and write requests for its partition.

A producer sends a record to the broker hosting the relevant partition leader.

Consumers normally retrieve records through the partition leader.

### Follower replicas

Followers maintain copies of partition data.

They replicate records from the leader and can participate in leader replacement when failure occurs.

The configured replication factor determines the intended number of replicas.

For example:

| Partition | Leader | Followers |
|---|---|---|
| Partition 0 | Broker 1 | Broker 2 |
| Partition 1 | Broker 2 | Broker 3 |
| Partition 2 | Broker 3 | Broker 1 |

This arrangement distributes leadership and replication responsibilities across the brokers.

### Replication and availability

Replication improves resilience, but replication alone does not guarantee availability.

Operational behavior depends on:

- Replica synchronization.
- Available brokers.
- Leader election.
- Minimum in-sync replica settings.
- Producer acknowledgment settings.
- Cluster metadata and controller behavior.

A producer configured with `acks=all` waits for acknowledgment according to the configured replication and in-sync replica requirements.

It does not automatically mean that every configured replica must acknowledge under every possible Kafka configuration.

The examples use a deliberately stricter educational rule: every configured replica must be available for the simulated `ALL` acknowledgment mode.

## 5. Producers

A producer publishes records to Kafka topics.

The producer is responsible for creating messages, selecting a destination partition, and handling broker responses.

A record generally contains:

| Field | Meaning |
|---|---|
| Key | Optional partitioning key |
| Value | Event payload |
| Timestamp | Record timestamp |
| Headers | Optional metadata |
| Offset | Assigned by Kafka within a partition |

### Producer workflow

    Application Event
          |
          v
    Create Record
          |
          v
    Select Topic
          |
          v
    Determine Partition
          |
          v
    Locate Partition Leader
          |
          v
    Send Record
          |
          v
    Broker Appends Record
          |
          v
    Acknowledgment
          |
          v
    Producer Receives Result

The broker assigns the offset when the record is appended to the partition log.

The producer should not independently assign Kafka offsets.

### Acknowledgment modes

Kafka producer acknowledgment configuration controls when the producer considers a send successful.

| Configuration | Meaning |
|---|---|
| `acks=0` | Producer does not wait for broker acknowledgment |
| `acks=1` | Producer waits for the leader acknowledgment |
| `acks=all` | Producer waits for the configured in-sync replica acknowledgment condition |

The trade-off involves durability, latency, and availability.

A stronger acknowledgment requirement can increase latency and cause sends to fail when replication requirements cannot be satisfied.

### Producer idempotence

Network failures can create uncertainty about whether a broker received a request.

A producer may retry a request when it does not receive an expected acknowledgment.

Without suitable duplicate protection, retries can produce duplicate records.

Kafka producer idempotence uses producer identities and sequence numbers to suppress duplicate writes caused by retries within its supported producer protocol.

Application-level idempotence is a separate concern.

A consumer may still encounter repeated business-processing attempts, especially when processing succeeds but offset commitment fails.

## 6. Consumers

A consumer retrieves records from Kafka and processes them.

Consumers generally use polling to obtain records.

Unlike a traditional queue, Kafka does not normally remove a record simply because one consumer has read it.

The record remains available according to the topic's retention and cleanup configuration.

This allows independent applications to consume the same event stream.

### Consumer workflow

    Consumer Starts
          |
          v
    Join Consumer Group
          |
          v
    Receive Partition Assignment
          |
          v
    Read From Committed Offset
          |
          v
    Process Records
          |
          v
    Commit Next Offset
          |
          v
    Continue Polling

The consumer is responsible for handling processing failures and offset management.

### Multiple consumers

Suppose a topic has four partitions and a group has two consumers.

| Consumer | Assignment |
|---|---|
| Consumer A | Partitions 0 and 1 |
| Consumer B | Partitions 2 and 3 |

A partition is not normally processed concurrently by multiple active members of the same consumer group.

Different groups maintain independent consumption progress.

For example:

- `order-processors` processes orders for fulfillment.
- `analytics-processors` analyzes the same orders for reporting.
- `fraud-detection` evaluates the same events for suspicious activity.

Each group has independent committed offsets.

### Consumer rebalancing

Rebalancing occurs when consumer-group membership or assignment requirements change.

Common triggers include:

- A consumer joins.
- A consumer leaves.
- A consumer crashes.
- A consumer stops sending heartbeats.
- Topic partition metadata changes.
- Group membership or assignment configuration changes.

During a rebalance, partitions may be reassigned.

The transition can temporarily interrupt consumption.

Partition assignment strategies influence how partitions are distributed among group members.

The source implementations use a simple round-robin strategy to demonstrate the assignment relationship. They do not implement Kafka's group coordinator protocol or production assignment strategies.

## 7. Offsets

An offset is a sequential position assigned to a record within a partition.

Offsets are partition-specific.

Consider:

| Partition | Offset | Event |
|---|---:|---|
| 0 | 0 | Order created |
| 0 | 1 | Payment completed |
| 0 | 2 | Order shipped |
| 1 | 0 | Customer registered |
| 1 | 1 | Customer updated |

Offset `1` in partition 0 is unrelated to offset `1` in partition 1.

An offset identifies a record's position, not a globally unique message position.

### Next-offset semantics

A committed consumer offset represents the next offset the consumer intends to read.

For example:

| Committed offset | Interpretation |
|---:|---|
| 0 | Start from the first available record |
| 1 | Records before offset 1 have been acknowledged |
| 5 | Next record to read is offset 5 |
| 10 | Next record to read is offset 10 |

If offsets 0 through 4 have been processed successfully, the consumer normally commits offset 5.

This distinction is important when implementing consumption and replay.

### Offset storage

Kafka maintains consumer-group offset information independently for each topic partition.

A conceptual offset structure is:

| Group | Topic | Partition | Committed offset |
|---|---|---:|---:|
| orders-group | orders | 0 | 5 |
| orders-group | orders | 1 | 8 |
| orders-group | orders | 2 | 3 |
| analytics-group | orders | 0 | 2 |

The two groups can process the same topic at different speeds.

### Offset commit strategies

| Strategy | Behavior | Risk |
|---|---|---|
| Automatic commit | Offsets are committed periodically | Records may be committed before processing finishes |
| Synchronous commit | Application waits for commit completion | Adds latency |
| Asynchronous commit | Commit requests are issued without waiting for every response | Failure and ordering handling require care |
| Manual commit | Application controls commit timing | Requires correct application logic |

Manual commitment provides greater control over the relationship between processing and acknowledgment.

## 8. Consumer Lag

Consumer lag measures the difference between the latest available log position and the consumer's committed position.

The basic calculation is:

`Consumer Lag = Log End Offset - Committed Offset`

Example:

| Partition | Log end offset | Committed offset | Lag |
|---|---:|---:|---:|
| 0 | 1000 | 950 | 50 |
| 1 | 800 | 790 | 10 |
| 2 | 1200 | 1100 | 100 |

Total lag is:

`50 + 10 + 100 = 160`

Lag is useful for monitoring consumer performance and identifying processing bottlenecks.

High lag can indicate:

- Insufficient consumer capacity.
- Slow downstream services.
- Expensive message processing.
- Unbalanced partition assignments.
- Repeated processing failures.
- Broker or network problems.

A lag measurement is meaningful only when its log-end and committed-offset semantics are clearly defined.

## 9. Delivery Semantics

Kafka applications must account for the relationship between message delivery, processing, and offset commitment.

### At-most-once

The consumer commits its position before completing processing.

A failure after commitment can cause a record to be skipped when processing resumes.

This favors avoiding duplicate processing at the cost of possible message loss at the application-processing level.

### At-least-once

The consumer processes a record before committing its offset.

If processing succeeds but the consumer crashes before commitment, the record can be delivered again.

This avoids skipping successfully uncommitted records but permits duplicate processing.

### Exactly-once

Exactly-once processing requires coordinated handling of records, offsets, and output operations.

Kafka supports transactional mechanisms for specific Kafka-to-Kafka processing workflows.

For external databases and services, reliable exactly-once business effects generally require additional coordination, such as idempotency keys, transactional outbox patterns, or appropriate transactional integration.

A simple offset commit does not guarantee exactly-once business processing.

## 10. Kafka Fundamentals and the Five Implementations

The source files demonstrate the same distributed-streaming concepts from different engineering perspectives.

| File | Engineering perspective | Main implementation |
|---|---|---|
| Python | Repository-style workflow simulation | Cluster, producer, consumer, partitions, and JSON reporting |
| JavaScript | Event-driven application | EventEmitter, Promises, asynchronous processing, and metadata events |
| C++17 | Performance-oriented domain model | STL containers, deterministic partition routing, and explicit state management |
| Java 17 | Enterprise service architecture | Records, domain types, policy objects, processing services, and validation |
| PostgreSQL | Relational operational model | Normalized tables, constraints, procedures, triggers, and analytical views |

### Python implementation

The Python program defines:

- `KafkaCluster` for cluster administration.
- `Broker` for broker availability.
- `Topic` for topic configuration.
- `Partition` for ordered message storage.
- `Producer` for record publication.
- `Consumer` for record retrieval and processing.
- `ConsumerGroup` for assignments and committed offsets.
- `Message` for immutable message metadata.

The cluster uses a reentrant lock to protect shared in-memory state.

Partition selection uses a key-based hash. Messages with the same key are routed consistently within a running simulation.

The producer validates acknowledgment requirements before appending records.

The consumer commits its next offset after successful batch processing.

The JSON report provides a persistent snapshot of cluster metadata and group progress.

### JavaScript implementation

The JavaScript implementation emphasizes event-driven behavior.

`EventEmitter` publishes operational events such as:

- `topic.created`
- `record.produced`
- `group.rebalanced`
- `offset.committed`
- `broker.availability.changed`

The producer exposes Promise-based operations.

The consumer supports asynchronous message handlers.

The implementation uses `Map` for cluster registries, `Set` for broker partition membership, and SHA-256-based key routing.

The use of `structuredClone` separates stored message payloads from caller-owned objects.

The processing example demonstrates that a failed handler does not advance the committed offset.

### C++17 implementation

The C++ program emphasizes explicit domain modeling and controlled resource usage.

Its main types are:

- `Broker`
- `Partition`
- `Topic`
- `ConsumerGroup`
- `KafkaCluster`
- `Consumer`

The implementation uses:

- `std::map` for ordered broker, topic, and group registries.
- `std::vector` for partition logs and replica collections.
- `std::set` for unique consumer identities and broker partition membership.
- `std::optional`-compatible domain design where optional values are required.
- Exceptions for invalid state and failed operations.

The FNV-1a hash function provides deterministic key-based routing for the educational scenario.

The implementation avoids unnecessary message copying during record retrieval by using explicit value and reference boundaries.

### Java 17 implementation

The Java implementation follows an enterprise-oriented design.

Its domain model uses records for immutable message and operation data.

The major service responsibilities are separated:

| Type | Responsibility |
|---|---|
| `Broker` | Broker availability and replica membership |
| `Partition` | Message log and offset management |
| `Topic` | Partition configuration and routing |
| `ConsumerGroup` | Membership, assignment, and offset state |
| `KafkaCluster` | Cluster-level coordination |
| `ConsumerService` | Message polling and processing |
| `PaymentProcessor` | Business processing and duplicate identification |
| `ReviewableProcessingPolicy` | Acknowledgment and batch constraints |

The processing service commits only after successful batch processing.

The payment processor tracks processed message identifiers within the running application.

A production application would require durable idempotency state and transactional business operations rather than relying on an in-memory set.

## 11. PostgreSQL Relational Model

The SQL implementation creates a dedicated `kafka_lab` schema.

It represents Kafka concepts through relational entities.

### Entity relationships

    brokers
       |
       +------ partition_replicas
       |              |
       |              v
       |          partitions
       |              |
       |              +------ messages
       |              |
       |              +------ consumer_assignments
       |              |
       |              +------ committed_offsets
       |
       +------ topics
                      |
                      v
                  partitions

    consumer_groups
          |
          +------ consumers
          |
          +------ consumer_assignments
          |
          +------ committed_offsets
          |
          +------ message_processing

    producers
          |
          +------ messages

### Database integrity

Primary keys identify records.

Foreign keys enforce relationships between topics, partitions, brokers, producers, consumers, and messages.

Unique constraints prevent duplicate topic names, consumer identities within a group, and offsets within the same partition.

Check constraints validate numeric boundaries and permitted states.

Partial unique indexes ensure that only one active leader record exists for a partition and that one consumer group does not assign the same partition to multiple active consumers.

### Triggers

The partition log-end trigger updates the next available offset after a message insertion.

The committed-offset trigger rejects offsets beyond the partition's known log end.

The replication-factor trigger checks the configured broker count.

These controls provide relational consistency within the simulated database.

They do not replace Kafka's distributed replication protocol.

### Stored procedures

The SQL implementation includes procedures for:

- Creating topics and partition replicas.
- Registering consumers.
- Assigning partitions.
- Committing consumer offsets.

The `produce_message` function validates producer configuration, leader availability, and replica availability before inserting a message.

The assignment procedure performs a transactional round-robin assignment.

The offset-commit procedure validates the proposed next offset and rejects backward movement.

### Reporting views

`consumer_lag_report` calculates consumer lag for every consumer-group and partition combination.

`partition_production_eligibility` evaluates whether a partition meets the educational replica-availability conditions.

Additional queries report:

- Broker and partition distribution.
- Replica placement.
- Message records.
- Consumer assignments.
- Offset positions.
- Processing successes and failures.
- Aggregate consumer lag.
- Production eligibility.

The intentional failure scenarios demonstrate validation without preventing the remaining SQL workflow from completing.

## 12. Important Operational Distinctions

Several Kafka concepts are closely related but should not be treated as interchangeable.

| Concept | What it represents | What it does not represent |
|---|---|---|
| Topic | Logical event stream | Physical server |
| Partition | Ordered log | Entire topic |
| Broker | Kafka server | Consumer group |
| Leader | Replica handling normal partition requests | Separate topic |
| Follower | Replicated partition copy | Independent consumer |
| Producer | Record publisher | Record processor |
| Consumer | Record reader and processor | Record owner |
| Consumer group | Shared consumption coordination | Topic replication |
| Offset | Partition position | Global message identifier |
| Consumer lag | Difference between log end and committed position | Guaranteed processing time |

### Ordering versus parallelism

Ordering is provided within a partition.

Parallelism is achieved across partitions.

Increasing parallelism should not be confused with increasing the ordering guarantees of a topic.

### Replication versus partitioning

Partitioning distributes a topic into independent logs.

Replication creates additional copies of those logs.

Partitioning primarily supports scalability and parallel processing.

Replication primarily supports fault tolerance and availability.

### Consumer groups versus brokers

Brokers manage distributed storage and client requests.

Consumer groups manage how application consumers share partition workloads.

They operate at different architectural layers.

## 13. Failure Handling and Edge Cases

The five implementations exercise several important failure conditions.

| Failure | Expected behavior |
|---|---|
| Missing topic | Reject the operation |
| Invalid partition | Reject the operation |
| Invalid replication factor | Reject topic creation |
| Unavailable leader | Reject production |
| Unavailable required replica | Reject strict all-replica acknowledgment |
| Invalid offset | Reject polling or commitment |
| Offset regression | Reject the commit |
| Empty consumer list | Reject assignment |
| Duplicate consumer identity | Reject assignment |
| Failed message handler | Do not advance the committed offset |
| Repeated processing | Require duplicate-safe business logic |

### Duplicate processing

A consumer may successfully process a message and fail before committing its offset.

When it restarts, it may read that message again.

A reliable application should use a stable event identifier and an idempotent processing operation.

For financial operations, a database transaction should coordinate the business update and idempotency record.

### Poison messages

A poison message repeatedly fails processing.

An application needs a defined retry strategy, error classification, and dead-letter handling policy.

Blindly advancing the offset after a failure can cause message loss from the application's perspective.

Blocking the entire partition indefinitely can also prevent later records from being processed.

### Retention and offset expiration

Kafka retains records according to topic policies.

An old committed offset may refer to data that has already been deleted through retention.

Applications must define their behavior when the requested offset is no longer available.

Possible policies include starting from the earliest available record or moving to the latest position, depending on the application's requirements.

## 14. Performance Considerations

Kafka performance depends on several interacting factors.

### Partition count

More partitions can increase parallelism.

They also increase:

- Metadata overhead.
- Replication workload.
- File and segment management.
- Consumer assignment complexity.
- Operational monitoring requirements.

Partition count should reflect expected throughput, ordering requirements, and future workload.

### Batching

Batching groups records into fewer producer requests.

It can improve network efficiency and throughput.

Excessive batching can increase message latency.

### Compression

Kafka supports compression algorithms including gzip, Snappy, LZ4, and Zstandard, subject to client and broker configuration.

Compression can reduce network and storage requirements at the cost of CPU consumption.

### Consumer processing

A consumer's effective throughput depends on:

- Poll frequency.
- Batch size.
- Processing time.
- Number of assigned partitions.
- Downstream database performance.
- Network latency.
- Offset commit frequency.

Increasing consumer count alone does not guarantee higher throughput when partition count or downstream capacity is the limiting factor.

### Complexity characteristics

| Operation | Educational implementation complexity |
|---|---|
| Topic lookup | O(1) average with hash maps; O(log T) with ordered maps |
| Partition selection | O(1) after hashing |
| Message append | Amortized O(1) with dynamic arrays |
| Offset lookup | O(1) average with hash maps; O(log G) with ordered maps |
| Sequential record retrieval | O(K), where K is the requested batch size |
| Round-robin assignment | O(P), where P is partition count |
| Consumer lag aggregation | O(P × G) for a full group-partition report |

The complexity figures describe the educational implementations and do not capture Kafka's network, disk, replication, or coordination costs.

## 15. Security and Production Considerations

A production Kafka environment requires controls beyond the basic models.

### Authentication

Kafka supports authentication mechanisms such as SASL and TLS client authentication.

Client identity should be established before access is granted.

### Authorization

Access control should be applied to topics and consumer groups.

Typical permissions include:

- Read.
- Write.
- Create.
- Describe.
- Alter.
- Delete.
- Group access.

Least-privilege permissions reduce accidental or unauthorized operations.

### Encryption

TLS protects network traffic between clients and brokers.

Storage-level encryption may be required for persisted records, depending on infrastructure and compliance requirements.

### Sensitive data

Events should contain only necessary business information.

Passwords, authentication tokens, private keys, and unnecessary personal information should not be published in message payloads.

Sensitive payload fields should be protected through appropriate application-level controls.

### Operational monitoring

Important monitoring indicators include:

- Broker availability.
- Under-replicated partitions.
- Offline partitions.
- Producer error rate.
- Producer request latency.
- Consumer lag.
- Rebalance frequency.
- Failed processing attempts.
- Disk utilization.
- Network throughput.

A production deployment should also define retention policies, replication settings, recovery procedures, capacity limits, and disaster-recovery requirements.

## 16. Implementation Limitations

These implementations deliberately model Kafka fundamentals without reproducing the full distributed platform.

| Capability | Implementation status |
|---|---|
| Topics | Implemented |
| Partitions | Implemented |
| Broker metadata | Implemented |
| Leader and follower assignments | Modeled |
| Key-based partition selection | Implemented |
| Producer acknowledgment modes | Simulated |
| Consumer groups | Implemented |
| Round-robin assignments | Implemented |
| Record polling | Implemented |
| Committed offsets | Implemented |
| Consumer lag | Implemented in SQL |
| Basic failure handling | Implemented |
| Event-driven notifications | Implemented in JavaScript |
| Asynchronous processing | Demonstrated in JavaScript |
| Domain-specific business processing | Demonstrated in Java |
| Kafka network protocol | Not implemented |
| Actual distributed replication | Not implemented |
| Kafka controller and coordinator protocols | Not implemented |
| Durable broker storage | Not implemented in source simulations |
| Kafka transactions | Not implemented |
| Production exactly-once processing | Not implemented |
| Production authentication and authorization | Not implemented |
| Production partition rebalancing protocols | Not implemented |

The SQL implementation is a relational representation of Kafka metadata and message-processing state. It is not a substitute for Kafka's distributed log or replication architecture.

The source programs are suitable for examining component responsibilities, record flow, partition routing, group assignments, and offset behavior without requiring a running Kafka installation.
