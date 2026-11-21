-- ============================================================
-- KAFKA FUNDAMENTALS: RELATIONAL WORKFLOW SIMULATION
-- PostgreSQL 14+
--
-- Models:
-- Brokers, topics, partitions, replicas, producers, messages,
-- consumer groups, assignments, offsets, and processing.
--
-- This is a relational educational model. PostgreSQL is not
-- being used as a replacement for Kafka's distributed log.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS kafka_lab;

SET search_path TO kafka_lab, public;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

CREATE TYPE broker_status AS ENUM (
    'AVAILABLE',
    'UNAVAILABLE',
    'MAINTENANCE'
);

CREATE TYPE acknowledgment_mode AS ENUM (
    'LEADER',
    'ALL'
);

CREATE TYPE message_status AS ENUM (
    'PENDING',
    'PROCESSED',
    'FAILED'
);

CREATE TYPE replica_role AS ENUM (
    'LEADER',
    'FOLLOWER'
);

-- ============================================================
-- 2. BROKERS
-- ============================================================

CREATE TABLE brokers (
    broker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    broker_name VARCHAR(100) NOT NULL UNIQUE,
    hostname VARCHAR(255) NOT NULL UNIQUE,
    port INTEGER NOT NULL DEFAULT 9092,
    status broker_status NOT NULL DEFAULT 'AVAILABLE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_broker_port
        CHECK (port BETWEEN 1 AND 65535)
);

-- ============================================================
-- 3. TOPICS
-- ============================================================

CREATE TABLE topics (
    topic_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic_name VARCHAR(249) NOT NULL UNIQUE,
    partition_count INTEGER NOT NULL,
    replication_factor INTEGER NOT NULL,
    retention_ms BIGINT NOT NULL DEFAULT 604800000,
    cleanup_policy VARCHAR(30) NOT NULL DEFAULT 'delete',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_partition_count
        CHECK (partition_count > 0),

    CONSTRAINT valid_replication_factor
        CHECK (replication_factor > 0),

    CONSTRAINT valid_retention
        CHECK (retention_ms > 0),

    CONSTRAINT valid_cleanup_policy
        CHECK (cleanup_policy IN ('delete', 'compact', 'compact_delete'))
);

-- ============================================================
-- 4. PARTITIONS
-- ============================================================

CREATE TABLE partitions (
    partition_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic_id BIGINT NOT NULL REFERENCES topics(topic_id)
        ON DELETE CASCADE,
    partition_number INTEGER NOT NULL,
    leader_broker_id BIGINT REFERENCES brokers(broker_id),
    log_start_offset BIGINT NOT NULL DEFAULT 0,
    log_end_offset BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_topic_partition
        UNIQUE(topic_id, partition_number),

    CONSTRAINT valid_partition_number
        CHECK (partition_number >= 0),

    CONSTRAINT valid_log_offsets
        CHECK (
            log_start_offset >= 0
            AND log_end_offset >= log_start_offset
        )
);

CREATE INDEX idx_partitions_topic
    ON partitions(topic_id, partition_number);

CREATE INDEX idx_partitions_leader
    ON partitions(leader_broker_id);

-- ============================================================
-- 5. REPLICATION ASSIGNMENTS
-- ============================================================

CREATE TABLE partition_replicas (
    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,

    broker_id BIGINT NOT NULL REFERENCES brokers(broker_id),

    replica_position INTEGER NOT NULL,

    role replica_role NOT NULL,

    is_in_sync BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY(partition_id, broker_id),

    CONSTRAINT unique_replica_position
        UNIQUE(partition_id, replica_position),

    CONSTRAINT valid_replica_position
        CHECK (replica_position >= 0)
);

CREATE UNIQUE INDEX idx_one_leader_per_partition
    ON partition_replicas(partition_id)
    WHERE role = 'LEADER';

CREATE INDEX idx_replicas_broker
    ON partition_replicas(broker_id);

-- ============================================================
-- 6. PRODUCERS
-- ============================================================

CREATE TABLE producers (
    producer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producer_name VARCHAR(120) NOT NULL UNIQUE,
    client_id VARCHAR(150) NOT NULL UNIQUE,
    acknowledgment acknowledgment_mode NOT NULL DEFAULT 'ALL',
    idempotence_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 7. MESSAGE LOG
--
-- The unique key (partition_id, offset) models offset uniqueness
-- within a partition. Different partitions can have the same offset.
-- ============================================================

CREATE TABLE messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id),

    producer_id BIGINT REFERENCES producers(producer_id),

    message_key VARCHAR(500),

    message_value JSONB NOT NULL,

    offset_value BIGINT NOT NULL,

    producer_sequence BIGINT,

    message_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_partition_offset
        UNIQUE(partition_id, offset_value),

    CONSTRAINT valid_message_offset
        CHECK (offset_value >= 0),

    CONSTRAINT valid_producer_sequence
        CHECK (
            producer_sequence IS NULL
            OR producer_sequence >= 0
        )
);

CREATE INDEX idx_messages_partition_offset
    ON messages(partition_id, offset_value);

CREATE INDEX idx_messages_timestamp
    ON messages(message_timestamp DESC);

CREATE INDEX idx_messages_key
    ON messages(partition_id, message_key);

CREATE INDEX idx_messages_json
    ON messages USING GIN(message_value);

-- ============================================================
-- 8. CONSUMER GROUPS
-- ============================================================

CREATE TABLE consumer_groups (
    group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name VARCHAR(150) NOT NULL UNIQUE,
    state VARCHAR(30) NOT NULL DEFAULT 'STABLE',
    generation_id BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_group_state
        CHECK (
            state IN (
                'STABLE',
                'REBALANCING',
                'EMPTY',
                'DEAD'
            )
        ),

    CONSTRAINT valid_generation
        CHECK (generation_id >= 0)
);

-- ============================================================
-- 9. CONSUMERS
-- ============================================================

CREATE TABLE consumers (
    consumer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES consumer_groups(group_id)
        ON DELETE CASCADE,
    consumer_name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_heartbeat TIMESTAMPTZ,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_consumer_in_group
        UNIQUE(group_id, consumer_name)
);

CREATE INDEX idx_consumers_active
    ON consumers(group_id, is_active);

-- ============================================================
-- 10. PARTITION ASSIGNMENTS
--
-- A partition has one active owner within a consumer group.
-- Different consumer groups can independently consume the same
-- partition.
-- ============================================================

CREATE TABLE consumer_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    group_id BIGINT NOT NULL REFERENCES consumer_groups(group_id)
        ON DELETE CASCADE,

    consumer_id BIGINT NOT NULL REFERENCES consumers(consumer_id)
        ON DELETE CASCADE,

    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    revoked_at TIMESTAMPTZ,

    CONSTRAINT valid_assignment_period
        CHECK (
            revoked_at IS NULL
            OR revoked_at >= assigned_at
        )
);

CREATE UNIQUE INDEX idx_one_active_owner
    ON consumer_assignments(group_id, partition_id)
    WHERE revoked_at IS NULL;

CREATE INDEX idx_assignments_consumer
    ON consumer_assignments(consumer_id, revoked_at);

-- ============================================================
-- 11. COMMITTED OFFSETS
--
-- Committed offset means the next record the consumer intends
-- to read. A committed offset of 10 means offsets 0 through 9
-- have been acknowledged by the application.
-- ============================================================

CREATE TABLE committed_offsets (
    group_id BIGINT NOT NULL REFERENCES consumer_groups(group_id)
        ON DELETE CASCADE,

    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,

    committed_offset BIGINT NOT NULL DEFAULT 0,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(group_id, partition_id),

    CONSTRAINT nonnegative_committed_offset
        CHECK (committed_offset >= 0)
);

CREATE INDEX idx_offsets_partition
    ON committed_offsets(partition_id, committed_offset);

-- ============================================================
-- 12. MESSAGE PROCESSING RECORDS
-- ============================================================

CREATE TABLE message_processing (
    group_id BIGINT NOT NULL REFERENCES consumer_groups(group_id)
        ON DELETE CASCADE,

    message_id UUID NOT NULL REFERENCES messages(message_id)
        ON DELETE CASCADE,

    status message_status NOT NULL DEFAULT 'PENDING',

    attempt_count INTEGER NOT NULL DEFAULT 0,

    processed_at TIMESTAMPTZ,

    error_message TEXT,

    PRIMARY KEY(group_id, message_id),

    CONSTRAINT valid_attempt_count
        CHECK (attempt_count >= 0),

    CONSTRAINT valid_processing_timestamp
        CHECK (
            status <> 'PROCESSED'
            OR processed_at IS NOT NULL
        )
);

CREATE INDEX idx_processing_status
    ON message_processing(group_id, status);

-- ============================================================
-- 13. VALIDATION FUNCTIONS
-- ============================================================

CREATE OR REPLACE FUNCTION validate_topic_replication()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    broker_total INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO broker_total
    FROM brokers;

    IF NEW.replication_factor > broker_total THEN
        RAISE EXCEPTION
            'Replication factor % exceeds available broker count %',
            NEW.replication_factor,
            broker_total;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_topic_replication
BEFORE INSERT OR UPDATE OF replication_factor
ON topics
FOR EACH ROW
EXECUTE FUNCTION validate_topic_replication();

-- ============================================================
-- 14. PARTITION OFFSET MANAGEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION update_partition_log_end()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE partitions
    SET log_end_offset = GREATEST(
        log_end_offset,
        NEW.offset_value + 1
    )
    WHERE partition_id = NEW.partition_id;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_update_partition_log_end
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION update_partition_log_end();

-- ============================================================
-- 15. COMMITTED OFFSET VALIDATION
--
-- The function prevents committing an offset beyond the
-- partition's currently known log end.
-- ============================================================

CREATE OR REPLACE FUNCTION validate_committed_offset()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    maximum_offset BIGINT;
BEGIN
    SELECT log_end_offset
    INTO maximum_offset
    FROM partitions
    WHERE partition_id = NEW.partition_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partition does not exist';
    END IF;

    IF NEW.committed_offset > maximum_offset THEN
        RAISE EXCEPTION
            'Committed offset % exceeds log end %',
            NEW.committed_offset,
            maximum_offset;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_committed_offset
BEFORE INSERT OR UPDATE OF committed_offset
ON committed_offsets
FOR EACH ROW
EXECUTE FUNCTION validate_committed_offset();

-- ============================================================
-- 16. TOPIC CREATION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE create_topic(
    p_topic_name VARCHAR,
    p_partition_count INTEGER,
    p_replication_factor INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    new_topic_id BIGINT;
    broker_ids BIGINT[];
    broker_count INTEGER;
    partition_number INTEGER;
    replica_number INTEGER;
    selected_broker BIGINT;
    selected_leader BIGINT;
    new_partition_id BIGINT;
BEGIN
    IF p_topic_name IS NULL OR LENGTH(TRIM(p_topic_name)) = 0 THEN
        RAISE EXCEPTION 'Topic name is required';
    END IF;

    IF p_partition_count < 1 THEN
        RAISE EXCEPTION 'Partition count must be positive';
    END IF;

    IF p_replication_factor < 1 THEN
        RAISE EXCEPTION 'Replication factor must be positive';
    END IF;

    SELECT ARRAY_AGG(broker_id ORDER BY broker_id)
    INTO broker_ids
    FROM brokers
    WHERE status = 'AVAILABLE';

    broker_count := COALESCE(
        CARDINALITY(broker_ids),
        0
    );

    IF p_replication_factor > broker_count THEN
        RAISE EXCEPTION
            'Insufficient available brokers for replication';
    END IF;

    INSERT INTO topics(
        topic_name,
        partition_count,
        replication_factor
    )
    VALUES (
        p_topic_name,
        p_partition_count,
        p_replication_factor
    )
    RETURNING topic_id INTO new_topic_id;

    FOR partition_number IN 0..p_partition_count - 1 LOOP

        selected_leader := broker_ids[
            (partition_number % broker_count) + 1
        ];

        INSERT INTO partitions(
            topic_id,
            partition_number,
            leader_broker_id
        )
        VALUES (
            new_topic_id,
            partition_number,
            selected_leader
        )
        RETURNING partition_id INTO new_partition_id;

        FOR replica_number IN 0..p_replication_factor - 1 LOOP

            selected_broker := broker_ids[
                ((partition_number + replica_number)
                    % broker_count) + 1
            ];

            INSERT INTO partition_replicas(
                partition_id,
                broker_id,
                replica_position,
                role
            )
            VALUES (
                new_partition_id,
                selected_broker,
                replica_number,
                CASE
                    WHEN replica_number = 0 THEN 'LEADER'::replica_role
                    ELSE 'FOLLOWER'::replica_role
                END
            );

        END LOOP;
    END LOOP;
END;
$$;

-- ============================================================
-- 17. MESSAGE PRODUCTION FUNCTION
--
-- The caller supplies a partition number. This function validates
-- broker availability and acknowledgment requirements.
-- ============================================================

CREATE OR REPLACE FUNCTION produce_message(
    p_topic_name VARCHAR,
    p_partition_number INTEGER,
    p_producer_id BIGINT,
    p_message_key VARCHAR,
    p_message_value JSONB
)
RETURNS TABLE(
    result_message_id UUID,
    result_partition INTEGER,
    result_offset BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_partition BIGINT;
    selected_offset BIGINT;
    selected_leader BIGINT;
    producer_ack acknowledgment_mode;
    replica_count INTEGER;
    available_replica_count INTEGER;
    new_message_id UUID;
BEGIN
    IF p_message_value IS NULL THEN
        RAISE EXCEPTION 'Message payload cannot be null';
    END IF;

    SELECT pr.partition_id,
           pr.leader_broker_id
    INTO selected_partition,
         selected_leader
    FROM partitions pr
    JOIN topics t
        ON t.topic_id = pr.topic_id
    WHERE t.topic_name = p_topic_name
      AND pr.partition_number = p_partition_number
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Topic partition not found';
    END IF;

    SELECT acknowledgment
    INTO producer_ack
    FROM producers
    WHERE producers.producer_id = p_producer_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producer not found';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM brokers
        WHERE broker_id = selected_leader
          AND status = 'AVAILABLE'
    ) THEN
        RAISE EXCEPTION 'Partition leader is unavailable';
    END IF;

    IF producer_ack = 'ALL' THEN

        SELECT COUNT(*),
               COUNT(*) FILTER (
                   WHERE b.status = 'AVAILABLE'
                     AND r.is_in_sync
               )
        INTO replica_count,
             available_replica_count
        FROM partition_replicas r
        JOIN brokers b
            ON b.broker_id = r.broker_id
        WHERE r.partition_id = selected_partition;

        IF available_replica_count <> replica_count THEN
            RAISE EXCEPTION
                'Not all replicas are available and in sync';
        END IF;
    END IF;

    SELECT log_end_offset
    INTO selected_offset
    FROM partitions
    WHERE partition_id = selected_partition;

    INSERT INTO messages(
        partition_id,
        producer_id,
        message_key,
        message_value,
        offset_value
    )
    VALUES (
        selected_partition,
        p_producer_id,
        p_message_key,
        p_message_value,
        selected_offset
    )
    RETURNING message_id INTO new_message_id;

    RETURN QUERY
    SELECT
        new_message_id,
        p_partition_number,
        selected_offset;
END;
$$;

-- ============================================================
-- 18. CONSUMER GROUP REGISTRATION
-- ============================================================

CREATE OR REPLACE FUNCTION register_consumer(
    p_group_name VARCHAR,
    p_consumer_name VARCHAR
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_group_id BIGINT;
    selected_consumer_id BIGINT;
BEGIN
    INSERT INTO consumer_groups(group_name)
    VALUES (p_group_name)
    ON CONFLICT (group_name)
    DO UPDATE SET group_name = EXCLUDED.group_name
    RETURNING group_id INTO selected_group_id;

    INSERT INTO consumers(
        group_id,
        consumer_name,
        last_heartbeat
    )
    VALUES (
        selected_group_id,
        p_consumer_name,
        CURRENT_TIMESTAMP
    )
    RETURNING consumer_id INTO selected_consumer_id;

    RETURN selected_consumer_id;
END;
$$;

-- ============================================================
-- 19. PARTITION ASSIGNMENT PROCEDURE
--
-- Round-robin assignment is used for demonstration.
-- Assignment replacement is transactional.
-- ============================================================

CREATE OR REPLACE PROCEDURE assign_partitions(
    p_group_name VARCHAR,
    p_topic_name VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_group_id BIGINT;
    selected_topic_id BIGINT;
    consumer_ids BIGINT[];
    consumer_count INTEGER;
    partition_record RECORD;
    selected_consumer BIGINT;
    assignment_index INTEGER := 0;
BEGIN
    SELECT group_id
    INTO selected_group_id
    FROM consumer_groups
    WHERE group_name = p_group_name
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Consumer group does not exist';
    END IF;

    SELECT topic_id
    INTO selected_topic_id
    FROM topics
    WHERE topic_name = p_topic_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Topic does not exist';
    END IF;

    SELECT ARRAY_AGG(consumer_id ORDER BY consumer_id)
    INTO consumer_ids
    FROM consumers
    WHERE group_id = selected_group_id
      AND is_active = TRUE;

    consumer_count := COALESCE(
        CARDINALITY(consumer_ids),
        0
    );

    IF consumer_count = 0 THEN
        RAISE EXCEPTION 'No active consumers available';
    END IF;

    UPDATE consumer_groups
    SET state = 'REBALANCING',
        generation_id = generation_id + 1
    WHERE group_id = selected_group_id;

    UPDATE consumer_assignments
    SET revoked_at = CURRENT_TIMESTAMP
    WHERE group_id = selected_group_id
      AND revoked_at IS NULL;

    FOR partition_record IN
        SELECT partition_id
        FROM partitions
        WHERE topic_id = selected_topic_id
        ORDER BY partition_number
    LOOP

        selected_consumer := consumer_ids[
            (assignment_index % consumer_count) + 1
        ];

        INSERT INTO consumer_assignments(
            group_id,
            consumer_id,
            partition_id
        )
        VALUES (
            selected_group_id,
            selected_consumer,
            partition_record.partition_id
        );

        assignment_index := assignment_index + 1;
    END LOOP;

    UPDATE consumer_groups
    SET state = 'STABLE'
    WHERE group_id = selected_group_id;
END;
$$;

-- ============================================================
-- 20. CONSUMER OFFSET COMMIT PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE commit_consumer_offset(
    p_group_name VARCHAR,
    p_partition_id BIGINT,
    p_next_offset BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_group_id BIGINT;
    selected_end_offset BIGINT;
BEGIN
    SELECT group_id
    INTO selected_group_id
    FROM consumer_groups
    WHERE group_name = p_group_name
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Consumer group not found';
    END IF;

    SELECT log_end_offset
    INTO selected_end_offset
    FROM partitions
    WHERE partition_id = p_partition_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partition not found';
    END IF;

    IF p_next_offset < 0
       OR p_next_offset > selected_end_offset THEN
        RAISE EXCEPTION 'Invalid committed offset';
    END IF;

    INSERT INTO committed_offsets(
        group_id,
        partition_id,
        committed_offset
    )
    VALUES (
        selected_group_id,
        p_partition_id,
        p_next_offset
    )
    ON CONFLICT (group_id, partition_id)
    DO UPDATE SET
        committed_offset = EXCLUDED.committed_offset,
        updated_at = CURRENT_TIMESTAMP
    WHERE committed_offsets.committed_offset
        <= EXCLUDED.committed_offset;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Offset regression rejected';
    END IF;
END;
$$;

-- ============================================================
-- 21. SAMPLE BROKERS
-- ============================================================

INSERT INTO brokers(
    broker_name,
    hostname,
    port
)
VALUES
    ('broker-1', 'kafka-broker-1.internal', 9092),
    ('broker-2', 'kafka-broker-2.internal', 9092),
    ('broker-3', 'kafka-broker-3.internal', 9092);

-- ============================================================
-- 22. SAMPLE PRODUCERS
-- ============================================================

INSERT INTO producers(
    producer_name,
    client_id,
    acknowledgment,
    idempotence_enabled
)
VALUES
    ('Order Service', 'order-service-01', 'ALL', TRUE),
    ('Inventory Service', 'inventory-service-01', 'LEADER', TRUE);

-- ============================================================
-- 23. SAMPLE TOPIC AND PARTITIONS
-- ============================================================

CALL create_topic('orders', 3, 2);
CALL create_topic('inventory', 2, 2);

-- ============================================================
-- 24. SAMPLE CONSUMER GROUPS
-- ============================================================

INSERT INTO consumer_groups(group_name)
VALUES
    ('order-processors'),
    ('analytics-processors');

INSERT INTO consumers(
    group_id,
    consumer_name,
    last_heartbeat
)
SELECT
    group_id,
    'order-worker-1',
    CURRENT_TIMESTAMP
FROM consumer_groups
WHERE group_name = 'order-processors';

INSERT INTO consumers(
    group_id,
    consumer_name,
    last_heartbeat
)
SELECT
    group_id,
    'order-worker-2',
    CURRENT_TIMESTAMP
FROM consumer_groups
WHERE group_name = 'order-processors';

INSERT INTO consumers(
    group_id,
    consumer_name,
    last_heartbeat
)
SELECT
    group_id,
    'analytics-worker-1',
    CURRENT_TIMESTAMP
FROM consumer_groups
WHERE group_name = 'analytics-processors';

-- ============================================================
-- 25. SAMPLE MESSAGE PRODUCTION
-- ============================================================

SELECT *
FROM produce_message(
    'orders',
    0,
    (SELECT producer_id FROM producers
     WHERE client_id = 'order-service-01'),
    'customer-101',
    '{"order_id": 1001, "amount": 2500, "currency": "INR"}'
);

SELECT *
FROM produce_message(
    'orders',
    1,
    (SELECT producer_id FROM producers
     WHERE client_id = 'order-service-01'),
    'customer-102',
    '{"order_id": 1002, "amount": 1800, "currency": "INR"}'
);

SELECT *
FROM produce_message(
    'orders',
    0,
    (SELECT producer_id FROM producers
     WHERE client_id = 'order-service-01'),
    'customer-101',
    '{"order_id": 1003, "amount": 4200, "currency": "INR"}'
);

SELECT *
FROM produce_message(
    'orders',
    2,
    (SELECT producer_id FROM producers
     WHERE client_id = 'order-service-01'),
    'customer-103',
    '{"order_id": 1004, "amount": 900, "currency": "INR"}'
);

SELECT *
FROM produce_message(
    'inventory',
    0,
    (SELECT producer_id FROM producers
     WHERE client_id = 'inventory-service-01'),
    'product-A',
    '{"product_id": "A", "stock": 120}'
);

-- ============================================================
-- 26. CONSUMER PARTITION ASSIGNMENT
-- ============================================================

CALL assign_partitions(
    'order-processors',
    'orders'
);

CALL assign_partitions(
    'analytics-processors',
    'orders'
);

-- ============================================================
-- 27. SAMPLE PROCESSING STATES
-- ============================================================

INSERT INTO message_processing(
    group_id,
    message_id,
    status,
    attempt_count,
    processed_at
)
SELECT
    cg.group_id,
    m.message_id,
    'PROCESSED',
    1,
    CURRENT_TIMESTAMP
FROM consumer_groups cg
CROSS JOIN messages m
JOIN partitions p
    ON p.partition_id = m.partition_id
JOIN topics t
    ON t.topic_id = p.topic_id
WHERE cg.group_name = 'order-processors'
  AND t.topic_name = 'orders'
  AND m.offset_value = 0;

INSERT INTO message_processing(
    group_id,
    message_id,
    status,
    attempt_count,
    error_message
)
SELECT
    cg.group_id,
    m.message_id,
    'FAILED',
    3,
    'Temporary downstream payment service failure'
FROM consumer_groups cg
CROSS JOIN messages m
JOIN partitions p
    ON p.partition_id = m.partition_id
JOIN topics t
    ON t.topic_id = p.topic_id
WHERE cg.group_name = 'order-processors'
  AND t.topic_name = 'orders'
  AND m.offset_value = 1;

-- ============================================================
-- 28. COMMIT SAMPLE OFFSETS
-- ============================================================

DO $$
DECLARE
    partition_zero BIGINT;
    partition_one BIGINT;
    partition_two BIGINT;
BEGIN
    SELECT p.partition_id
    INTO partition_zero
    FROM partitions p
    JOIN topics t ON t.topic_id = p.topic_id
    WHERE t.topic_name = 'orders'
      AND p.partition_number = 0;

    SELECT p.partition_id
    INTO partition_one
    FROM partitions p
    JOIN topics t ON t.topic_id = p.topic_id
    WHERE t.topic_name = 'orders'
      AND p.partition_number = 1;

    SELECT p.partition_id
    INTO partition_two
    FROM partitions p
    JOIN topics t ON t.topic_id = p.topic_id
    WHERE t.topic_name = 'orders'
      AND p.partition_number = 2;

    CALL commit_consumer_offset(
        'order-processors',
        partition_zero,
        1
    );

    CALL commit_consumer_offset(
        'order-processors',
        partition_one,
        0
    );

    CALL commit_consumer_offset(
        'order-processors',
        partition_two,
        1
    );
END;
$$;

-- ============================================================
-- 29. RETRIEVAL: TOPICS AND PARTITION METADATA
-- ============================================================

SELECT
    t.topic_name,
    t.partition_count,
    t.replication_factor,
    p.partition_number,
    b.broker_name AS leader,
    p.log_start_offset,
    p.log_end_offset
FROM topics t
JOIN partitions p
    ON p.topic_id = t.topic_id
LEFT JOIN brokers b
    ON b.broker_id = p.leader_broker_id
ORDER BY t.topic_name, p.partition_number;

-- ============================================================
-- 30. RETRIEVAL: REPLICA DISTRIBUTION
-- ============================================================

SELECT
    t.topic_name,
    p.partition_number,
    b.broker_name,
    r.role,
    r.is_in_sync
FROM partition_replicas r
JOIN partitions p
    ON p.partition_id = r.partition_id
JOIN topics t
    ON t.topic_id = p.topic_id
JOIN brokers b
    ON b.broker_id = r.broker_id
ORDER BY t.topic_name, p.partition_number, r.replica_position;

-- ============================================================
-- 31. RETRIEVAL: MESSAGE LOG
-- ============================================================

SELECT
    t.topic_name,
    p.partition_number,
    m.offset_value,
    m.message_key,
    m.message_value,
    m.message_timestamp
FROM messages m
JOIN partitions p
    ON p.partition_id = m.partition_id
JOIN topics t
    ON t.topic_id = p.topic_id
ORDER BY t.topic_name, p.partition_number, m.offset_value;

-- ============================================================
-- 32. CONSUMER ASSIGNMENT REPORT
-- ============================================================

SELECT
    cg.group_name,
    c.consumer_name,
    t.topic_name,
    p.partition_number,
    ca.assigned_at
FROM consumer_assignments ca
JOIN consumer_groups cg
    ON cg.group_id = ca.group_id
JOIN consumers c
    ON c.consumer_id = ca.consumer_id
JOIN partitions p
    ON p.partition_id = ca.partition_id
JOIN topics t
    ON t.topic_id = p.topic_id
WHERE ca.revoked_at IS NULL
ORDER BY cg.group_name, c.consumer_name, p.partition_number;

-- ============================================================
-- 33. OFFSET REPORT
-- ============================================================

SELECT
    cg.group_name,
    t.topic_name,
    p.partition_number,
    COALESCE(co.committed_offset, 0) AS committed_offset,
    p.log_end_offset,
    p.log_end_offset -
        COALESCE(co.committed_offset, 0) AS remaining_records
FROM consumer_groups cg
CROSS JOIN topics t
JOIN partitions p
    ON p.topic_id = t.topic_id
LEFT JOIN committed_offsets co
    ON co.group_id = cg.group_id
   AND co.partition_id = p.partition_id
ORDER BY cg.group_name, t.topic_name, p.partition_number;

-- ============================================================
-- 34. CONSUMER LAG AGGREGATION
-- ============================================================

CREATE OR REPLACE VIEW consumer_lag_report AS
SELECT
    cg.group_name,
    t.topic_name,
    p.partition_number,
    p.log_end_offset,
    COALESCE(co.committed_offset, 0) AS committed_offset,
    GREATEST(
        p.log_end_offset -
        COALESCE(co.committed_offset, 0),
        0
    ) AS consumer_lag
FROM consumer_groups cg
CROSS JOIN topics t
JOIN partitions p
    ON p.topic_id = t.topic_id
LEFT JOIN committed_offsets co
    ON co.group_id = cg.group_id
   AND co.partition_id = p.partition_id;

SELECT *
FROM consumer_lag_report
ORDER BY group_name, topic_name, partition_number;

-- ============================================================
-- 35. GROUP-LEVEL LAG AGGREGATION
-- ============================================================

SELECT
    group_name,
    topic_name,
    SUM(consumer_lag) AS total_lag,
    MAX(consumer_lag) AS maximum_partition_lag,
    AVG(consumer_lag)::NUMERIC(12,2) AS average_partition_lag
FROM consumer_lag_report
GROUP BY group_name, topic_name
ORDER BY group_name, topic_name;

-- ============================================================
-- 36. PROCESSING SUCCESS AND FAILURE REPORT
-- ============================================================

SELECT
    cg.group_name,
    mp.status,
    COUNT(*) AS message_count,
    SUM(mp.attempt_count) AS total_attempts
FROM message_processing mp
JOIN consumer_groups cg
    ON cg.group_id = mp.group_id
GROUP BY cg.group_name, mp.status
ORDER BY cg.group_name, mp.status;

-- ============================================================
-- 37. ELIGIBILITY: PARTITION PRODUCTION READINESS
-- ============================================================

CREATE OR REPLACE VIEW partition_production_eligibility AS
SELECT
    t.topic_name,
    p.partition_number,
    leader.broker_name AS leader_name,

    CASE
        WHEN leader.status <> 'AVAILABLE'
            THEN FALSE

        WHEN replica_stats.replica_count <> t.replication_factor
            THEN FALSE

        WHEN replica_stats.available_count <> t.replication_factor
            THEN FALSE

        WHEN replica_stats.in_sync_count <> t.replication_factor
            THEN FALSE

        ELSE TRUE
    END AS production_eligible,

    replica_stats.replica_count,
    replica_stats.available_count,
    replica_stats.in_sync_count

FROM partitions p

JOIN topics t
    ON t.topic_id = p.topic_id

JOIN brokers leader
    ON leader.broker_id = p.leader_broker_id

CROSS JOIN LATERAL (
    SELECT
        COUNT(*) AS replica_count,

        COUNT(*) FILTER (
            WHERE b.status = 'AVAILABLE'
        ) AS available_count,

        COUNT(*) FILTER (
            WHERE b.status = 'AVAILABLE'
              AND r.is_in_sync = TRUE
        ) AS in_sync_count

    FROM partition_replicas r

    JOIN brokers b
        ON b.broker_id = r.broker_id

    WHERE r.partition_id = p.partition_id
) replica_stats;

SELECT *
FROM partition_production_eligibility;

-- ============================================================
-- 38. CONSUMER ASSIGNMENT VALIDATION
-- ============================================================

SELECT
    cg.group_name,
    t.topic_name,
    p.partition_number,
    COUNT(ca.assignment_id) AS active_assignment_count,

    CASE
        WHEN COUNT(ca.assignment_id) = 1
            THEN 'VALID'
        WHEN COUNT(ca.assignment_id) = 0
            THEN 'UNASSIGNED'
        ELSE 'INVALID_DUPLICATE_ASSIGNMENT'
    END AS assignment_status

FROM consumer_groups cg
CROSS JOIN topics t
JOIN partitions p
    ON p.topic_id = t.topic_id

LEFT JOIN consumer_assignments ca
    ON ca.group_id = cg.group_id
   AND ca.partition_id = p.partition_id
   AND ca.revoked_at IS NULL

GROUP BY
    cg.group_name,
    t.topic_name,
    p.partition_number

ORDER BY cg.group_name, t.topic_name, p.partition_number;

-- ============================================================
-- 39. FAILURE SCENARIO: INVALID OFFSET
--
-- The savepoint ensures the intentional failure does not abort
-- the remainder of the script.
-- ============================================================

SAVEPOINT invalid_offset_test;

DO $$
DECLARE
    selected_group_id BIGINT;
    selected_partition BIGINT;
BEGIN
    SELECT group_id
    INTO selected_group_id
    FROM consumer_groups
    WHERE group_name = 'order-processors';

    SELECT partition_id
    INTO selected_partition
    FROM partitions p
    JOIN topics t ON t.topic_id = p.topic_id
    WHERE t.topic_name = 'orders'
      AND p.partition_number = 0;

    BEGIN
        INSERT INTO committed_offsets(
            group_id,
            partition_id,
            committed_offset
        )
        VALUES (
            selected_group_id,
            selected_partition,
            999999
        )
        ON CONFLICT (group_id, partition_id)
        DO UPDATE SET
            committed_offset = EXCLUDED.committed_offset;

    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Expected offset validation failure: %',
            SQLERRM;
    END;
END;
$$;

ROLLBACK TO SAVEPOINT invalid_offset_test;

RELEASE SAVEPOINT invalid_offset_test;

-- ============================================================
-- 40. FAILURE SCENARIO: BROKER UNAVAILABILITY
-- ============================================================

SAVEPOINT broker_failure_test;

UPDATE brokers
SET status = 'UNAVAILABLE'
WHERE broker_name = 'broker-1';

SELECT
    topic_name,
    partition_number,
    production_eligible
FROM partition_production_eligibility
ORDER BY topic_name, partition_number;

ROLLBACK TO SAVEPOINT broker_failure_test;

RELEASE SAVEPOINT broker_failure_test;

-- ============================================================
-- 41. OPERATIONAL TOPIC REPORT
-- ============================================================

SELECT
    t.topic_name,
    COUNT(DISTINCT p.partition_id) AS partitions,
    COUNT(m.message_id) AS total_messages,
    COALESCE(SUM(p.log_end_offset), 0) AS aggregate_log_end_offsets,
    MAX(m.message_timestamp) AS latest_message
FROM topics t
LEFT JOIN partitions p
    ON p.topic_id = t.topic_id
LEFT JOIN messages m
    ON m.partition_id = p.partition_id
GROUP BY t.topic_id, t.topic_name
ORDER BY t.topic_name;

COMMIT;

-- ============================================================
-- END OF KAFKA FUNDAMENTALS DATABASE WORKFLOW
-- ============================================================
