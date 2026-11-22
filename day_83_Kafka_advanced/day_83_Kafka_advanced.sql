-- ================================================================
-- ADVANCED KAFKA OPERATIONS DATABASE
-- PostgreSQL 15+
--
-- Models:
--   Brokers, topics, partitions, replicas and ISR
--   Consumer groups and consumer membership
--   Partition assignments and generations
--   Messages, offsets and retention
--   Producer acknowledgement policies
--   Replication and leader elections
--   Operational failures and recovery
--
-- This database is an operational metadata and audit simulation.
-- It does not implement Kafka's distributed log or wire protocol.
-- ================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS kafka_ops;

SET search_path TO kafka_ops, public;

-- ================================================================
-- 1. ENUMERATIONS
-- ================================================================

CREATE TYPE broker_status AS ENUM (
    'ONLINE',
    'OFFLINE',
    'MAINTENANCE'
);

CREATE TYPE consumer_status AS ENUM (
    'JOINING',
    'ACTIVE',
    'FAILED',
    'LEFT'
);

CREATE TYPE rebalance_protocol AS ENUM (
    'EAGER',
    'COOPERATIVE'
);

CREATE TYPE acknowledgement_mode AS ENUM (
    'LEADER_ONLY',
    'ALL'
);

CREATE TYPE review_status AS ENUM (
    'STABLE',
    'REBALANCING',
    'UNAVAILABLE'
);

-- ================================================================
-- 2. BROKERS
-- ================================================================

CREATE TABLE brokers (
    broker_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL UNIQUE,
    rack_id VARCHAR(100),
    status broker_status NOT NULL DEFAULT 'ONLINE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ================================================================
-- 3. TOPICS
-- ================================================================

CREATE TABLE topics (
    topic_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic_name VARCHAR(249) NOT NULL UNIQUE,
    partition_count INTEGER NOT NULL CHECK (partition_count > 0),
    replication_factor INTEGER NOT NULL CHECK (replication_factor > 0),
    min_insync_replicas INTEGER NOT NULL DEFAULT 1
        CHECK (min_insync_replicas > 0),
    retention_ms BIGINT NOT NULL DEFAULT 604800000
        CHECK (retention_ms >= -1),
    retention_bytes BIGINT NOT NULL DEFAULT -1
        CHECK (retention_bytes >= -1),
    cleanup_policy VARCHAR(30) NOT NULL DEFAULT 'delete'
        CHECK (cleanup_policy IN ('delete', 'compact', 'delete,compact')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (min_insync_replicas <= replication_factor)
);

-- ================================================================
-- 4. PARTITIONS
-- ================================================================

CREATE TABLE partitions (
    partition_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic_id BIGINT NOT NULL REFERENCES topics(topic_id)
        ON DELETE CASCADE,
    partition_number INTEGER NOT NULL CHECK (partition_number >= 0),
    leader_broker_id INTEGER REFERENCES brokers(broker_id),
    log_start_offset BIGINT NOT NULL DEFAULT 0
        CHECK (log_start_offset >= 0),
    high_watermark BIGINT NOT NULL DEFAULT 0
        CHECK (high_watermark >= 0),
    next_offset BIGINT NOT NULL DEFAULT 0
        CHECK (next_offset >= 0),
    UNIQUE (topic_id, partition_number),
    CHECK (log_start_offset <= high_watermark),
    CHECK (high_watermark <= next_offset)
);

CREATE INDEX idx_partitions_leader
    ON partitions(leader_broker_id);

-- ================================================================
-- 5. REPLICAS
-- ================================================================

CREATE TABLE partition_replicas (
    replica_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,
    broker_id INTEGER NOT NULL REFERENCES brokers(broker_id),
    replica_position INTEGER NOT NULL CHECK (replica_position >= 0),
    is_leader BOOLEAN NOT NULL DEFAULT FALSE,
    in_sync BOOLEAN NOT NULL DEFAULT FALSE,
    replica_log_end_offset BIGINT NOT NULL DEFAULT 0
        CHECK (replica_log_end_offset >= 0),
    last_caught_up_at TIMESTAMPTZ,
    UNIQUE (partition_id, broker_id),
    UNIQUE (partition_id, replica_position)
);

CREATE UNIQUE INDEX idx_one_leader_per_partition
    ON partition_replicas(partition_id)
    WHERE is_leader = TRUE;

CREATE INDEX idx_replica_isr
    ON partition_replicas(partition_id, in_sync);

CREATE INDEX idx_replica_broker
    ON partition_replicas(broker_id);

-- ================================================================
-- 6. CONSUMER GROUPS
-- ================================================================

CREATE TABLE consumer_groups (
    group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name VARCHAR(255) NOT NULL UNIQUE,
    generation BIGINT NOT NULL DEFAULT 0 CHECK (generation >= 0),
    state review_status NOT NULL DEFAULT 'REBALANCING',
    protocol rebalance_protocol NOT NULL DEFAULT 'COOPERATIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE consumers (
    consumer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES consumer_groups(group_id)
        ON DELETE CASCADE,
    member_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    hostname VARCHAR(255),
    status consumer_status NOT NULL DEFAULT 'JOINING',
    session_timeout_ms INTEGER NOT NULL DEFAULT 45000
        CHECK (session_timeout_ms > 0),
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (group_id, member_id)
);

CREATE INDEX idx_consumers_group_status
    ON consumers(group_id, status);

CREATE INDEX idx_consumers_heartbeat
    ON consumers(last_heartbeat)
    WHERE status = 'ACTIVE';

CREATE TABLE consumer_subscriptions (
    consumer_id BIGINT NOT NULL REFERENCES consumers(consumer_id)
        ON DELETE CASCADE,
    topic_id BIGINT NOT NULL REFERENCES topics(topic_id)
        ON DELETE CASCADE,
    PRIMARY KEY (consumer_id, topic_id)
);

-- ================================================================
-- 7. PARTITION ASSIGNMENTS
-- ================================================================

CREATE TABLE partition_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    consumer_id BIGINT NOT NULL REFERENCES consumers(consumer_id)
        ON DELETE CASCADE,
    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,
    generation BIGINT NOT NULL CHECK (generation >= 0),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    CHECK (revoked_at IS NULL OR revoked_at >= assigned_at)
);

-- One active consumer per partition within a group.
CREATE UNIQUE INDEX idx_active_partition_assignment
    ON partition_assignments(partition_id, generation)
    WHERE revoked_at IS NULL;

CREATE INDEX idx_assignment_consumer
    ON partition_assignments(consumer_id, generation);

-- ================================================================
-- 8. MESSAGE LOG METADATA
-- ================================================================

CREATE TABLE messages (
    message_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,
    message_offset BIGINT NOT NULL CHECK (message_offset >= 0),
    message_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    message_size BIGINT NOT NULL CHECK (message_size >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (partition_id, message_offset)
);

CREATE INDEX idx_messages_partition_offset
    ON messages(partition_id, message_offset);

CREATE INDEX idx_messages_timestamp
    ON messages(created_at);

-- ================================================================
-- 9. CONSUMER OFFSETS
-- ================================================================

CREATE TABLE consumer_offsets (
    offset_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES consumer_groups(group_id)
        ON DELETE CASCADE,
    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id)
        ON DELETE CASCADE,
    committed_offset BIGINT NOT NULL CHECK (committed_offset >= 0),
    generation BIGINT NOT NULL CHECK (generation >= 0),
    committed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (group_id, partition_id)
);

CREATE INDEX idx_offsets_partition
    ON consumer_offsets(partition_id);

-- ================================================================
-- 10. PRODUCER ACKNOWLEDGEMENTS
-- ================================================================

CREATE TABLE producer_events (
    producer_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    partition_id BIGINT NOT NULL REFERENCES partitions(partition_id),
    message_offset BIGINT NOT NULL,
    acknowledgement acknowledgement_mode NOT NULL,
    required_isr INTEGER NOT NULL CHECK (required_isr > 0),
    available_isr INTEGER NOT NULL CHECK (available_isr >= 0),
    accepted BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    failure_reason TEXT
);

-- ================================================================
-- 11. OPERATIONAL AUDIT
-- ================================================================

CREATE TABLE operational_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id BIGINT,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_operational_events_time
    ON operational_events(occurred_at DESC);

CREATE INDEX idx_operational_events_type
    ON operational_events(event_type, occurred_at DESC);

-- ================================================================
-- 12. VALIDATION FUNCTIONS
-- ================================================================

CREATE OR REPLACE FUNCTION validate_partition_replication()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    configured_factor INTEGER;
    replica_count INTEGER;
    current_isr INTEGER;
    current_leader INTEGER;
BEGIN
    SELECT t.replication_factor
    INTO configured_factor
    FROM partitions p
    JOIN topics t ON t.topic_id = p.topic_id
    WHERE p.partition_id = NEW.partition_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partition does not exist';
    END IF;

    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE in_sync),
        COUNT(*) FILTER (WHERE is_leader)
    INTO replica_count, current_isr, current_leader
    FROM partition_replicas
    WHERE partition_id = NEW.partition_id
      AND replica_id <> COALESCE(NEW.replica_id, -1);

    replica_count := replica_count + 1;

    IF replica_count > configured_factor THEN
        RAISE EXCEPTION 'Replication factor exceeded';
    END IF;

    IF NEW.is_leader AND NOT NEW.in_sync THEN
        RAISE EXCEPTION 'Leader must belong to ISR';
    END IF;

    IF NEW.replica_log_end_offset < 0 THEN
        RAISE EXCEPTION 'Invalid replica offset';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_replica
BEFORE INSERT OR UPDATE ON partition_replicas
FOR EACH ROW
EXECUTE FUNCTION validate_partition_replication();

-- ================================================================
-- 13. OFFSET VALIDATION
-- ================================================================

CREATE OR REPLACE FUNCTION validate_committed_offset()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    current_start BIGINT;
    current_watermark BIGINT;
    current_generation BIGINT;
BEGIN
    SELECT log_start_offset, high_watermark
    INTO current_start, current_watermark
    FROM partitions
    WHERE partition_id = NEW.partition_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partition not found';
    END IF;

    IF NEW.committed_offset < current_start
       OR NEW.committed_offset > current_watermark THEN
        RAISE EXCEPTION
            'Offset % is outside valid range [% - %]',
            NEW.committed_offset,
            current_start,
            current_watermark;
    END IF;

    SELECT generation
    INTO current_generation
    FROM consumer_groups
    WHERE group_id = NEW.group_id;

    IF NEW.generation > current_generation THEN
        RAISE EXCEPTION 'Offset generation exceeds group generation';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_offset
BEFORE INSERT OR UPDATE ON consumer_offsets
FOR EACH ROW
EXECUTE FUNCTION validate_committed_offset();

-- ================================================================
-- 14. CONSUMER HEARTBEAT
-- ================================================================

CREATE OR REPLACE FUNCTION record_consumer_heartbeat(
    p_group_id BIGINT,
    p_member_id VARCHAR
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE consumers
    SET last_heartbeat = NOW(),
        status = 'ACTIVE'
    WHERE group_id = p_group_id
      AND member_id = p_member_id
      AND status IN ('JOINING', 'ACTIVE');

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active consumer membership not found';
    END IF;
END;
$$;

-- ================================================================
-- 15. CONSUMER FAILURE DETECTION
-- ================================================================

CREATE OR REPLACE FUNCTION detect_failed_consumers()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    affected INTEGER;
BEGIN
    UPDATE consumers
    SET status = 'FAILED'
    WHERE status = 'ACTIVE'
      AND last_heartbeat <
          NOW() - session_timeout_ms * INTERVAL '1 millisecond';

    GET DIAGNOSTICS affected = ROW_COUNT;

    IF affected > 0 THEN
        UPDATE consumer_groups g
        SET state = 'REBALANCING',
            updated_at = NOW()
        WHERE EXISTS (
            SELECT 1
            FROM consumers c
            WHERE c.group_id = g.group_id
              AND c.status = 'FAILED'
        );

        INSERT INTO operational_events(
            event_type,
            entity_type,
            details
        )
        VALUES (
            'CONSUMER_FAILURE_DETECTION',
            'CONSUMER_GROUP',
            jsonb_build_object('failed_count', affected)
        );
    END IF;

    RETURN affected;
END;
$$;

-- ================================================================
-- 16. PARTITION REBALANCING
-- ================================================================

CREATE OR REPLACE FUNCTION rebalance_consumer_group(
    p_group_id BIGINT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    next_generation BIGINT;
    assignment_count INTEGER;
BEGIN
    PERFORM 1
    FROM consumer_groups
    WHERE group_id = p_group_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Consumer group does not exist';
    END IF;

    UPDATE consumer_groups
    SET state = 'REBALANCING',
        generation = generation + 1,
        updated_at = NOW()
    WHERE group_id = p_group_id
    RETURNING generation INTO next_generation;

    -- Revoke previous active assignments for this group.
    UPDATE partition_assignments pa
    SET revoked_at = NOW()
    FROM consumers c
    WHERE pa.consumer_id = c.consumer_id
      AND c.group_id = p_group_id
      AND pa.revoked_at IS NULL;

    -- Deterministic round-robin assignment.
    WITH eligible AS (
        SELECT
            c.consumer_id,
            t.topic_id,
            p.partition_id,
            ROW_NUMBER() OVER (
                PARTITION BY p.partition_id
                ORDER BY c.member_id
            ) AS member_rank,
            COUNT(*) OVER (
                PARTITION BY p.partition_id
            ) AS member_count
        FROM consumers c
        JOIN consumer_subscriptions cs
            ON cs.consumer_id = c.consumer_id
        JOIN topics t
            ON t.topic_id = cs.topic_id
        JOIN partitions p
            ON p.topic_id = t.topic_id
        WHERE c.group_id = p_group_id
          AND c.status = 'ACTIVE'
    ),
    selected AS (
        SELECT DISTINCT ON (partition_id)
            consumer_id,
            partition_id
        FROM eligible
        WHERE member_rank =
            (partition_id % member_count) + 1
        ORDER BY partition_id, consumer_id
    )
    INSERT INTO partition_assignments(
        consumer_id,
        partition_id,
        generation
    )
    SELECT
        consumer_id,
        partition_id,
        next_generation
    FROM selected;

    GET DIAGNOSTICS assignment_count = ROW_COUNT;

    UPDATE consumer_groups
    SET state = 'STABLE',
        updated_at = NOW()
    WHERE group_id = p_group_id;

    INSERT INTO operational_events(
        event_type,
        entity_type,
        entity_id,
        details
    )
    VALUES (
        'GROUP_REBALANCED',
        'CONSUMER_GROUP',
        p_group_id,
        jsonb_build_object(
            'generation', next_generation,
            'assignments', assignment_count
        )
    );

    RETURN assignment_count;
END;
$$;

-- ================================================================
-- 17. OFFSET COMMIT PROCEDURE
-- ================================================================

CREATE OR REPLACE PROCEDURE commit_consumer_offset(
    p_group_id BIGINT,
    p_partition_id BIGINT,
    p_offset BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    current_generation BIGINT;
BEGIN
    SELECT generation
    INTO current_generation
    FROM consumer_groups
    WHERE group_id = p_group_id
      AND state = 'STABLE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Group must be stable before committing';
    END IF;

    INSERT INTO consumer_offsets(
        group_id,
        partition_id,
        committed_offset,
        generation
    )
    VALUES (
        p_group_id,
        p_partition_id,
        p_offset,
        current_generation
    )
    ON CONFLICT (group_id, partition_id)
    DO UPDATE SET
        committed_offset = EXCLUDED.committed_offset,
        generation = EXCLUDED.generation,
        committed_at = NOW();

    INSERT INTO operational_events(
        event_type,
        entity_type,
        entity_id,
        details
    )
    VALUES (
        'OFFSET_COMMITTED',
        'CONSUMER_GROUP',
        p_group_id,
        jsonb_build_object(
            'partition_id', p_partition_id,
            'offset', p_offset
        )
    );
END;
$$;

-- ================================================================
-- 18. PRODUCER ISR ELIGIBILITY
-- ================================================================

CREATE OR REPLACE FUNCTION evaluate_producer_eligibility(
    p_partition_id BIGINT,
    p_ack acknowledgement_mode
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    required_count INTEGER;
    available_count INTEGER;
BEGIN
    SELECT t.min_insync_replicas
    INTO required_count
    FROM partitions p
    JOIN topics t ON t.topic_id = p.topic_id
    WHERE p.partition_id = p_partition_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partition not found';
    END IF;

    IF p_ack = 'LEADER_ONLY' THEN
        RETURN EXISTS (
            SELECT 1
            FROM partitions p
            JOIN brokers b ON b.broker_id = p.leader_broker_id
            WHERE p.partition_id = p_partition_id
              AND b.status = 'ONLINE'
        );
    END IF;

    SELECT COUNT(*)
    INTO available_count
    FROM partition_replicas pr
    JOIN brokers b ON b.broker_id = pr.broker_id
    WHERE pr.partition_id = p_partition_id
      AND pr.in_sync
      AND b.status = 'ONLINE';

    RETURN available_count >= required_count;
END;
$$;

-- ================================================================
-- 19. REPLICA HEALTH VIEW
-- ================================================================

CREATE OR REPLACE VIEW replica_health AS
SELECT
    t.topic_name,
    p.partition_number,
    p.partition_id,
    p.leader_broker_id,
    COUNT(pr.replica_id) AS configured_replicas,
    COUNT(*) FILTER (
        WHERE pr.in_sync AND b.status = 'ONLINE'
    ) AS available_isr,
    t.min_insync_replicas,
    p.high_watermark,
    p.log_start_offset,
    CASE
        WHEN COUNT(pr.replica_id) < t.replication_factor
            THEN 'UNDER_REPLICATED'
        WHEN COUNT(*) FILTER (
            WHERE pr.in_sync AND b.status = 'ONLINE'
        ) < t.min_insync_replicas
            THEN 'INSUFFICIENT_ISR'
        ELSE 'HEALTHY'
    END AS health_status
FROM partitions p
JOIN topics t ON t.topic_id = p.topic_id
LEFT JOIN partition_replicas pr
    ON pr.partition_id = p.partition_id
LEFT JOIN brokers b
    ON b.broker_id = pr.broker_id
GROUP BY
    t.topic_name,
    p.partition_number,
    p.partition_id,
    p.leader_broker_id,
    t.replication_factor,
    t.min_insync_replicas,
    p.high_watermark,
    p.log_start_offset;

-- ================================================================
-- 20. CONSUMER LAG VIEW
-- ================================================================

CREATE OR REPLACE VIEW consumer_lag AS
SELECT
    g.group_name,
    t.topic_name,
    p.partition_number,
    COALESCE(o.committed_offset, p.log_start_offset) AS committed_offset,
    p.high_watermark,
    GREATEST(
        p.high_watermark -
        COALESCE(o.committed_offset, p.log_start_offset),
        0
    ) AS lag_records,
    g.state,
    g.generation
FROM consumer_groups g
CROSS JOIN partitions p
JOIN topics t ON t.topic_id = p.topic_id
LEFT JOIN consumer_offsets o
    ON o.group_id = g.group_id
   AND o.partition_id = p.partition_id;

-- ================================================================
-- 21. RETENTION PROCESSING
-- ================================================================

CREATE OR REPLACE FUNCTION apply_time_retention()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER := 0;
    current_count INTEGER;
BEGIN
    WITH expired AS (
        DELETE FROM messages m
        USING partitions p, topics t
        WHERE m.partition_id = p.partition_id
          AND p.topic_id = t.topic_id
          AND t.retention_ms >= 0
          AND m.created_at <
              NOW() - t.retention_ms * INTERVAL '1 millisecond'
        RETURNING m.message_id
    )
    SELECT COUNT(*) INTO current_count FROM expired;

    deleted_count := current_count;

    -- Advance log start offsets to the oldest retained message.
    UPDATE partitions p
    SET log_start_offset = COALESCE(
        (
            SELECT MIN(m.message_offset)
            FROM messages m
            WHERE m.partition_id = p.partition_id
        ),
        p.next_offset
    )
    WHERE EXISTS (
        SELECT 1
        FROM topics t
        WHERE t.topic_id = p.topic_id
          AND t.retention_ms >= 0
    );

    INSERT INTO operational_events(
        event_type,
        entity_type,
        details
    )
    VALUES (
        'RETENTION_EXECUTED',
        'TOPIC',
        jsonb_build_object('deleted_messages', deleted_count)
    );

    RETURN deleted_count;
END;
$$;

-- ================================================================
-- 22. SEED BROKERS
-- ================================================================

INSERT INTO brokers(hostname, rack_id)
VALUES
    ('kafka-broker-01.internal', 'rack-a'),
    ('kafka-broker-02.internal', 'rack-b'),
    ('kafka-broker-03.internal', 'rack-c');

-- ================================================================
-- 23. SEED TOPICS
-- ================================================================

INSERT INTO topics(
    topic_name,
    partition_count,
    replication_factor,
    min_insync_replicas,
    retention_ms,
    retention_bytes
)
VALUES
    ('orders', 4, 3, 2, 604800000, -1),
    ('payments', 3, 3, 2, 259200000, -1),
    ('audit-events', 2, 3, 2, 86400000, -1);

-- ================================================================
-- 24. CREATE PARTITIONS
-- ================================================================

INSERT INTO partitions(
    topic_id,
    partition_number,
    leader_broker_id
)
SELECT
    t.topic_id,
    n.partition_number,
    ((n.partition_number % 3) + 1)::INTEGER
FROM topics t
CROSS JOIN LATERAL generate_series(
    0,
    t.partition_count - 1
) AS n(partition_number);

-- ================================================================
-- 25. CREATE REPLICAS
-- ================================================================

INSERT INTO partition_replicas(
    partition_id,
    broker_id,
    replica_position,
    is_leader,
    in_sync,
    replica_log_end_offset,
    last_caught_up_at
)
SELECT
    p.partition_id,
    ((p.partition_number + r.replica_position) % 3 + 1)::INTEGER,
    r.replica_position,
    r.replica_position = 0,
    TRUE,
    0,
    NOW()
FROM partitions p
CROSS JOIN LATERAL generate_series(
    0,
    2
) AS r(replica_position);

-- ================================================================
-- 26. SEED CONSUMER GROUPS
-- ================================================================

INSERT INTO consumer_groups(group_name, protocol)
VALUES
    ('order-processors', 'COOPERATIVE'),
    ('payment-analytics', 'EAGER');

INSERT INTO consumers(
    group_id,
    member_id,
    client_id,
    hostname,
    status
)
SELECT
    g.group_id,
    c.member_id,
    c.client_id,
    c.hostname,
    'ACTIVE'
FROM consumer_groups g
CROSS JOIN (
    VALUES
        ('order-worker-01', 'orders-client-01', 'worker-01.internal'),
        ('order-worker-02', 'orders-client-02', 'worker-02.internal')
) AS c(member_id, client_id, hostname)
WHERE g.group_name = 'order-processors';

INSERT INTO consumers(
    group_id,
    member_id,
    client_id,
    hostname,
    status
)
SELECT
    g.group_id,
    c.member_id,
    c.client_id,
    c.hostname,
    'ACTIVE'
FROM consumer_groups g
CROSS JOIN (
    VALUES
        ('payment-worker-01', 'payments-client-01', 'worker-03.internal'),
        ('payment-worker-02', 'payments-client-02', 'worker-04.internal')
) AS c(member_id, client_id, hostname)
WHERE g.group_name = 'payment-analytics';

-- ================================================================
-- 27. SEED SUBSCRIPTIONS
-- ================================================================

INSERT INTO consumer_subscriptions(consumer_id, topic_id)
SELECT c.consumer_id, t.topic_id
FROM consumers c
JOIN consumer_groups g ON g.group_id = c.group_id
JOIN topics t ON t.topic_name =
    CASE
        WHEN g.group_name = 'order-processors' THEN 'orders'
        ELSE 'payments'
    END;

-- ================================================================
-- 28. INITIAL REBALANCING
-- ================================================================

SELECT rebalance_consumer_group(group_id)
FROM consumer_groups
ORDER BY group_id;

-- ================================================================
-- 29. SEED MESSAGE LOGS
-- ================================================================

INSERT INTO messages(
    partition_id,
    message_offset,
    message_key,
    payload,
    message_size,
    created_at
)
SELECT
    p.partition_id,
    n.message_offset,
    'event-' || p.partition_number || '-' || n.message_offset,
    jsonb_build_object(
        'partition', p.partition_number,
        'sequence', n.message_offset,
        'status', 'processed'
    ),
    128,
    NOW() - n.message_offset * INTERVAL '1 minute'
FROM partitions p
CROSS JOIN generate_series(0, 4) AS n(message_offset);

UPDATE partitions
SET next_offset = 5,
    high_watermark = 5;

UPDATE partition_replicas
SET replica_log_end_offset = 5,
    last_caught_up_at = NOW();

-- ================================================================
-- 30. SEED COMMITTED OFFSETS
-- ================================================================

INSERT INTO consumer_offsets(
    group_id,
    partition_id,
    committed_offset,
    generation
)
SELECT
    g.group_id,
    p.partition_id,
    3,
    g.generation
FROM consumer_groups g
JOIN topics t ON t.topic_name =
    CASE
        WHEN g.group_name = 'order-processors' THEN 'orders'
        ELSE 'payments'
    END
JOIN partitions p ON p.topic_id = t.topic_id;

-- ================================================================
-- 31. PRODUCER ACKNOWLEDGEMENT EXAMPLES
-- ================================================================

INSERT INTO producer_events(
    partition_id,
    message_offset,
    acknowledgement,
    required_isr,
    available_isr,
    accepted,
    failure_reason
)
SELECT
    p.partition_id,
    4,
    'ALL',
    2,
    3,
    TRUE,
    NULL
FROM partitions p
LIMIT 1;

INSERT INTO producer_events(
    partition_id,
    message_offset,
    acknowledgement,
    required_isr,
    available_isr,
    accepted,
    failure_reason
)
SELECT
    p.partition_id,
    5,
    'ALL',
    2,
    1,
    FALSE,
    'Not enough in-sync replicas'
FROM partitions p
OFFSET 1
LIMIT 1;

-- ================================================================
-- 32. REPLICATION HEALTH REPORT
-- ================================================================

SELECT
    topic_name,
    partition_number,
    leader_broker_id,
    configured_replicas,
    available_isr,
    min_insync_replicas,
    health_status
FROM replica_health
ORDER BY topic_name, partition_number;

-- ================================================================
-- 33. CONSUMER LAG REPORT
-- ================================================================

SELECT
    group_name,
    topic_name,
    partition_number,
    committed_offset,
    high_watermark,
    lag_records
FROM consumer_lag
ORDER BY group_name, topic_name, partition_number;

-- ================================================================
-- 34. CONSUMER ASSIGNMENT REPORT
-- ================================================================

SELECT
    g.group_name,
    g.generation,
    c.member_id,
    t.topic_name,
    p.partition_number,
    pa.assigned_at
FROM partition_assignments pa
JOIN consumers c ON c.consumer_id = pa.consumer_id
JOIN consumer_groups g ON g.group_id = c.group_id
JOIN partitions p ON p.partition_id = pa.partition_id
JOIN topics t ON t.topic_id = p.topic_id
WHERE pa.revoked_at IS NULL
ORDER BY g.group_name, c.member_id, t.topic_name, p.partition_number;

-- ================================================================
-- 35. RETENTION ELIGIBILITY REPORT
-- ================================================================

SELECT
    t.topic_name,
    p.partition_number,
    COUNT(m.message_id) AS retained_records,
    MIN(m.created_at) AS oldest_record,
    MAX(m.created_at) AS newest_record,
    t.retention_ms
FROM topics t
JOIN partitions p ON p.topic_id = t.topic_id
LEFT JOIN messages m ON m.partition_id = p.partition_id
GROUP BY
    t.topic_name,
    p.partition_number,
    t.retention_ms
ORDER BY t.topic_name, p.partition_number;

-- ================================================================
-- 36. REBALANCE FAILURE AND RECOVERY EXAMPLE
-- ================================================================

-- Simulate an expired consumer heartbeat.
UPDATE consumers
SET last_heartbeat = NOW() - INTERVAL '2 hours'
WHERE member_id = 'order-worker-02';

SELECT detect_failed_consumers();

-- The group now requires a new assignment generation.
SELECT group_name, generation, state
FROM consumer_groups
WHERE group_name = 'order-processors';

-- ================================================================
-- 37. TRANSACTIONAL OFFSET COMMIT EXAMPLE
-- ================================================================

DO $$
DECLARE
    target_group BIGINT;
    target_partition BIGINT;
BEGIN
    SELECT g.group_id, p.partition_id
    INTO target_group, target_partition
    FROM consumer_groups g
    JOIN topics t ON t.topic_name = 'orders'
    JOIN partitions p ON p.topic_id = t.topic_id
    WHERE g.group_name = 'order-processors'
    ORDER BY p.partition_number
    LIMIT 1;

    IF target_group IS NOT NULL THEN
        -- This transaction commits metadata atomically.
        CALL commit_consumer_offset(
            target_group,
            target_partition,
            4
        );
    END IF;
END;
$$;

-- ================================================================
-- 38. INVALID OFFSET TEST
-- ================================================================

DO $$
DECLARE
    target_group BIGINT;
    target_partition BIGINT;
BEGIN
    SELECT g.group_id, p.partition_id
    INTO target_group, target_partition
    FROM consumer_groups g
    JOIN topics t ON t.topic_name = 'orders'
    JOIN partitions p ON p.topic_id = t.topic_id
    WHERE g.group_name = 'order-processors'
    ORDER BY p.partition_number
    LIMIT 1;

    BEGIN
        INSERT INTO consumer_offsets(
            group_id,
            partition_id,
            committed_offset,
            generation
        )
        VALUES (
            target_group,
            target_partition,
            999999,
            (
                SELECT generation
                FROM consumer_groups
                WHERE group_id = target_group
            )
        );

    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Expected offset validation failure: %', SQLERRM;
    END;
END;
$$;

-- ================================================================
-- 39. OPERATIONAL SUMMARY
-- ================================================================

SELECT
    (SELECT COUNT(*) FROM brokers) AS total_brokers,
    (SELECT COUNT(*) FROM topics) AS total_topics,
    (SELECT COUNT(*) FROM partitions) AS total_partitions,
    (SELECT COUNT(*) FROM partition_replicas) AS total_replicas,
    (SELECT COUNT(*) FROM consumers) AS total_consumers,
    (SELECT COUNT(*) FROM messages) AS retained_messages,
    (SELECT COUNT(*) FROM consumer_groups) AS total_groups;

COMMIT;

-- ================================================================
-- 40. USEFUL OPERATIONAL QUERIES
-- ================================================================

-- A. Find under-replicated partitions.
SELECT *
FROM replica_health
WHERE health_status <> 'HEALTHY';

-- B. Find consumer groups with excessive lag.
SELECT *
FROM consumer_lag
WHERE lag_records > 1000
ORDER BY lag_records DESC;

-- C. Find offline brokers.
SELECT broker_id, hostname, rack_id, status
FROM brokers
WHERE status <> 'ONLINE';

-- D. Identify failed consumer members.
SELECT
    g.group_name,
    c.member_id,
    c.last_heartbeat,
    c.session_timeout_ms
FROM consumers c
JOIN consumer_groups g ON g.group_id = c.group_id
WHERE c.status = 'FAILED';

-- E. Find partitions with no active leader.
SELECT
    t.topic_name,
    p.partition_number
FROM partitions p
JOIN topics t ON t.topic_id = p.topic_id
LEFT JOIN brokers b ON b.broker_id = p.leader_broker_id
WHERE b.status IS DISTINCT FROM 'ONLINE';

-- F. Identify stale replica progress.
SELECT
    t.topic_name,
    p.partition_number,
    pr.broker_id,
    p.high_watermark,
    pr.replica_log_end_offset,
    p.high_watermark - pr.replica_log_end_offset AS replica_lag
FROM partition_replicas pr
JOIN partitions p ON p.partition_id = pr.partition_id
JOIN topics t ON t.topic_id = p.topic_id
WHERE pr.replica_log_end_offset < p.high_watermark
ORDER BY replica_lag DESC;

-- G. Review operational failures.
SELECT
    event_type,
    entity_type,
    entity_id,
    details,
    occurred_at
FROM operational_events
ORDER BY occurred_at DESC
LIMIT 50;
