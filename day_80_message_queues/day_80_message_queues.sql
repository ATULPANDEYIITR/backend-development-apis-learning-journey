-- ============================================================
-- MESSAGE QUEUE MANAGEMENT SYSTEM
-- PostgreSQL 15+
--
-- Domain:
-- Producers -> Broker -> Queues -> Consumers
--                          |
--                          +-> Deliveries
--                                |
--                                +-> ACK
--                                +-> NACK / RETRY
--                                +-> DEAD LETTER
--
-- Features:
-- - Relational message storage
-- - Queue and producer registration
-- - Consumer registration
-- - Atomic message claiming
-- - Delivery ownership
-- - Acknowledgments
-- - Negative acknowledgments
-- - Exponential retry scheduling
-- - Visibility timeout recovery
-- - Dead-letter handling
-- - Idempotency keys
-- - Queue metrics and reporting
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS message_system;

SET search_path TO message_system, public;

-- ------------------------------------------------------------
-- 1. DOMAIN TYPES
-- ------------------------------------------------------------

CREATE TYPE message_status AS ENUM (
    'READY',
    'IN_FLIGHT',
    'ACKNOWLEDGED',
    'RETRY_PENDING',
    'DEAD_LETTERED'
);

CREATE TYPE delivery_outcome AS ENUM (
    'ACK',
    'NACK',
    'TIMEOUT',
    'DEAD_LETTER'
);

CREATE TYPE consumer_status AS ENUM (
    'ACTIVE',
    'PAUSED',
    'DISABLED'
);

-- ------------------------------------------------------------
-- 2. PRODUCERS
-- ------------------------------------------------------------

CREATE TABLE producers (
    producer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producer_name VARCHAR(120) NOT NULL UNIQUE,
    service_name VARCHAR(120) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 3. QUEUES
-- ------------------------------------------------------------

CREATE TABLE queues (
    queue_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    queue_name VARCHAR(120) NOT NULL UNIQUE,
    capacity INTEGER NOT NULL DEFAULT 1000,
    maximum_attempts INTEGER NOT NULL DEFAULT 3,
    visibility_timeout_seconds INTEGER NOT NULL DEFAULT 30,
    retry_base_seconds INTEGER NOT NULL DEFAULT 5,
    retry_max_seconds INTEGER NOT NULL DEFAULT 300,
    dead_letter_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_capacity CHECK (capacity > 0),
    CONSTRAINT valid_attempts CHECK (maximum_attempts > 0),
    CONSTRAINT valid_visibility_timeout
        CHECK (visibility_timeout_seconds > 0),
    CONSTRAINT valid_retry_base
        CHECK (retry_base_seconds >= 0),
    CONSTRAINT valid_retry_max
        CHECK (retry_max_seconds >= retry_base_seconds)
);

-- ------------------------------------------------------------
-- 4. CONSUMERS
-- ------------------------------------------------------------

CREATE TABLE consumers (
    consumer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    consumer_name VARCHAR(120) NOT NULL UNIQUE,
    queue_id BIGINT NOT NULL REFERENCES queues(queue_id),
    status consumer_status NOT NULL DEFAULT 'ACTIVE',
    concurrency_limit INTEGER NOT NULL DEFAULT 1,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_concurrency CHECK (concurrency_limit > 0)
);

-- ------------------------------------------------------------
-- 5. MESSAGES
-- ------------------------------------------------------------

CREATE TABLE messages (
    message_id UUID PRIMARY KEY,
    queue_id BIGINT NOT NULL REFERENCES queues(queue_id),
    producer_id BIGINT NOT NULL REFERENCES producers(producer_id),

    routing_key VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,

    status message_status NOT NULL DEFAULT 'READY',

    attempt_count INTEGER NOT NULL DEFAULT 0,
    maximum_attempts INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,

    current_consumer_id BIGINT REFERENCES consumers(consumer_id),
    last_error TEXT,

    CONSTRAINT valid_message_attempts CHECK (
        attempt_count >= 0
        AND maximum_attempts > 0
        AND attempt_count <= maximum_attempts
    ),

    CONSTRAINT valid_payload CHECK (
        jsonb_typeof(payload) = 'object'
    ),

    CONSTRAINT valid_routing_key CHECK (
        LENGTH(TRIM(routing_key)) > 0
    ),

    CONSTRAINT valid_delivery_state CHECK (
        (
            status = 'IN_FLIGHT'
            AND current_consumer_id IS NOT NULL
            AND delivered_at IS NOT NULL
        )
        OR
        (
            status <> 'IN_FLIGHT'
            AND current_consumer_id IS NULL
        )
    )
);

-- ------------------------------------------------------------
-- 6. DELIVERY HISTORY
-- ------------------------------------------------------------

CREATE TABLE deliveries (
    delivery_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES messages(message_id),
    consumer_id BIGINT NOT NULL REFERENCES consumers(consumer_id),

    attempt_number INTEGER NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    outcome delivery_outcome,
    error_message TEXT,

    CONSTRAINT unique_message_attempt
        UNIQUE (message_id, attempt_number),

    CONSTRAINT valid_delivery_attempt CHECK (attempt_number > 0),

    CONSTRAINT valid_delivery_completion CHECK (
        (outcome IS NULL AND completed_at IS NULL)
        OR
        (outcome IS NOT NULL AND completed_at IS NOT NULL)
    )
);

-- ------------------------------------------------------------
-- 7. IDEMPOTENCY RECORDS
-- ------------------------------------------------------------

CREATE TABLE idempotency_records (
    idempotency_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producer_id BIGINT NOT NULL REFERENCES producers(producer_id),
    idempotency_key VARCHAR(200) NOT NULL,
    message_id UUID REFERENCES messages(message_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_producer_idempotency
        UNIQUE (producer_id, idempotency_key)
);

-- ------------------------------------------------------------
-- 8. DEAD-LETTER RECORDS
-- ------------------------------------------------------------

CREATE TABLE dead_letters (
    dead_letter_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id UUID NOT NULL UNIQUE REFERENCES messages(message_id),
    original_queue_id BIGINT NOT NULL REFERENCES queues(queue_id),
    final_attempt INTEGER NOT NULL,
    failure_reason TEXT NOT NULL,
    dead_lettered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 9. OPERATIONAL INDEXES
-- ------------------------------------------------------------

-- Supports FIFO-style ready message discovery.
CREATE INDEX idx_messages_ready
ON messages(queue_id, available_at, created_at)
WHERE status IN ('READY', 'RETRY_PENDING');

-- Supports consumer visibility timeout recovery.
CREATE INDEX idx_messages_inflight
ON messages(delivered_at)
WHERE status = 'IN_FLIGHT';

-- Supports producer history.
CREATE INDEX idx_messages_producer
ON messages(producer_id, created_at DESC);

-- Supports delivery history reporting.
CREATE INDEX idx_deliveries_message
ON deliveries(message_id, attempt_number);

CREATE INDEX idx_deliveries_consumer
ON deliveries(consumer_id, delivered_at DESC);

CREATE INDEX idx_dead_letters_queue
ON dead_letters(original_queue_id, dead_lettered_at DESC);

CREATE INDEX idx_messages_routing
ON messages(queue_id, routing_key);

-- ------------------------------------------------------------
-- 10. MESSAGE INSERTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION publish_message(
    p_producer_id BIGINT,
    p_queue_id BIGINT,
    p_routing_key VARCHAR,
    p_payload JSONB,
    p_idempotency_key VARCHAR DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_message_id UUID;
    v_existing UUID;
    v_max_attempts INTEGER;
BEGIN
    IF p_routing_key IS NULL
       OR LENGTH(TRIM(p_routing_key)) = 0 THEN
        RAISE EXCEPTION 'Routing key is required';
    END IF;

    IF p_payload IS NULL
       OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'Payload must be a JSON object';
    END IF;

    PERFORM 1
    FROM producers
    WHERE producer_id = p_producer_id
      AND enabled = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producer is missing or disabled';
    END IF;

    SELECT maximum_attempts
    INTO v_max_attempts
    FROM queues
    WHERE queue_id = p_queue_id
      AND enabled = TRUE
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Queue is missing or disabled';
    END IF;

    IF p_idempotency_key IS NOT NULL THEN

        INSERT INTO idempotency_records (
            producer_id,
            idempotency_key
        )
        VALUES (
            p_producer_id,
            p_idempotency_key
        )
        ON CONFLICT (producer_id, idempotency_key)
        DO NOTHING;

        IF NOT FOUND THEN
            SELECT message_id
            INTO v_existing
            FROM idempotency_records
            WHERE producer_id = p_producer_id
              AND idempotency_key = p_idempotency_key;

            IF v_existing IS NULL THEN
                RAISE EXCEPTION
                    'Idempotency key exists without message association';
            END IF;

            RETURN v_existing;
        END IF;
    END IF;

    v_message_id := gen_random_uuid();

    INSERT INTO messages (
        message_id,
        queue_id,
        producer_id,
        routing_key,
        payload,
        maximum_attempts
    )
    VALUES (
        v_message_id,
        p_queue_id,
        p_producer_id,
        p_routing_key,
        p_payload,
        v_max_attempts
    );

    IF p_idempotency_key IS NOT NULL THEN
        UPDATE idempotency_records
        SET message_id = v_message_id
        WHERE producer_id = p_producer_id
          AND idempotency_key = p_idempotency_key;
    END IF;

    RETURN v_message_id;
END;
$$;

-- ------------------------------------------------------------
-- 11. ATOMIC MESSAGE CLAIMING
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION claim_message(
    p_queue_id BIGINT,
    p_consumer_id BIGINT
)
RETURNS TABLE (
    claimed_message_id UUID,
    claimed_payload JSONB,
    claimed_attempt INTEGER,
    claimed_routing_key VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_message RECORD;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM consumers
        WHERE consumer_id = p_consumer_id
          AND queue_id = p_queue_id
          AND status = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'Consumer is not active for this queue';
    END IF;

    -- The row lock prevents multiple workers from claiming
    -- the same message concurrently.
    SELECT m.*
    INTO v_message
    FROM messages m
    WHERE m.queue_id = p_queue_id
      AND m.status IN ('READY', 'RETRY_PENDING')
      AND m.available_at <= NOW()
      AND m.attempt_count < m.maximum_attempts
    ORDER BY m.available_at, m.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE messages
    SET status = 'IN_FLIGHT',
        attempt_count = attempt_count + 1,
        current_consumer_id = p_consumer_id,
        delivered_at = NOW()
    WHERE message_id = v_message.message_id;

    INSERT INTO deliveries (
        message_id,
        consumer_id,
        attempt_number
    )
    VALUES (
        v_message.message_id,
        p_consumer_id,
        v_message.attempt_count + 1
    );

    RETURN QUERY
    SELECT
        v_message.message_id,
        v_message.payload,
        v_message.attempt_count + 1,
        v_message.routing_key;
END;
$$;

-- ------------------------------------------------------------
-- 12. ACKNOWLEDGMENT
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION acknowledge_message(
    p_message_id UUID,
    p_consumer_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_attempt INTEGER;
BEGIN
    UPDATE messages
    SET status = 'ACKNOWLEDGED',
        acknowledged_at = NOW(),
        current_consumer_id = NULL
    WHERE message_id = p_message_id
      AND status = 'IN_FLIGHT'
      AND current_consumer_id = p_consumer_id
    RETURNING attempt_count INTO v_attempt;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Invalid acknowledgment or consumer ownership';
    END IF;

    UPDATE deliveries
    SET outcome = 'ACK',
        completed_at = NOW()
    WHERE message_id = p_message_id
      AND attempt_number = v_attempt
      AND outcome IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active delivery record not found';
    END IF;

    RETURN TRUE;
END;
$$;

-- ------------------------------------------------------------
-- 13. NEGATIVE ACKNOWLEDGMENT AND RETRY
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION reject_message(
    p_message_id UUID,
    p_consumer_id BIGINT,
    p_error TEXT,
    p_requeue BOOLEAN DEFAULT TRUE
)
RETURNS message_status
LANGUAGE plpgsql
AS $$
DECLARE
    v_message RECORD;
    v_delay INTEGER;
    v_final_status message_status;
BEGIN
    SELECT
        m.*,
        q.retry_base_seconds,
        q.retry_max_seconds,
        q.dead_letter_enabled
    INTO v_message
    FROM messages m
    JOIN queues q ON q.queue_id = m.queue_id
    WHERE m.message_id = p_message_id
      AND m.status = 'IN_FLIGHT'
      AND m.current_consumer_id = p_consumer_id
    FOR UPDATE OF m;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Message not in flight or consumer ownership invalid';
    END IF;

    UPDATE deliveries
    SET outcome = 'NACK',
        completed_at = NOW(),
        error_message = p_error
    WHERE message_id = p_message_id
      AND attempt_number = v_message.attempt_count
      AND outcome IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active delivery record not found';
    END IF;

    IF p_requeue
       AND v_message.attempt_count < v_message.maximum_attempts THEN

        v_delay := LEAST(
            v_message.retry_max_seconds,
            v_message.retry_base_seconds
            * POWER(
                2,
                LEAST(v_message.attempt_count - 1, 30)
            )::INTEGER
        );

        UPDATE messages
        SET status = 'RETRY_PENDING',
            current_consumer_id = NULL,
            available_at = NOW() + make_interval(secs => v_delay),
            last_error = p_error
        WHERE message_id = p_message_id;

        v_final_status := 'RETRY_PENDING';

    ELSE

        UPDATE messages
        SET status = 'DEAD_LETTERED',
            current_consumer_id = NULL,
            last_error = p_error
        WHERE message_id = p_message_id;

        IF v_message.dead_letter_enabled THEN
            INSERT INTO dead_letters (
                message_id,
                original_queue_id,
                final_attempt,
                failure_reason
            )
            VALUES (
                p_message_id,
                v_message.queue_id,
                v_message.attempt_count,
                COALESCE(p_error, 'Maximum attempts exhausted')
            );
        END IF;

        UPDATE deliveries
        SET outcome = 'DEAD_LETTER'
        WHERE message_id = p_message_id
          AND attempt_number = v_message.attempt_count;

        v_final_status := 'DEAD_LETTERED';
    END IF;

    RETURN v_final_status;
END;
$$;

-- ------------------------------------------------------------
-- 14. VISIBILITY TIMEOUT RECOVERY
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION recover_expired_messages(
    p_queue_id BIGINT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_message RECORD;
    v_recovered INTEGER := 0;
    v_delay INTEGER;
BEGIN
    FOR v_message IN
        SELECT
            m.*,
            q.visibility_timeout_seconds,
            q.retry_base_seconds,
            q.retry_max_seconds,
            q.dead_letter_enabled
        FROM messages m
        JOIN queues q ON q.queue_id = m.queue_id
        WHERE m.queue_id = p_queue_id
          AND m.status = 'IN_FLIGHT'
          AND m.delivered_at
              < NOW() - make_interval(
                  secs => q.visibility_timeout_seconds
              )
        FOR UPDATE OF m SKIP LOCKED
    LOOP

        UPDATE deliveries
        SET outcome = 'TIMEOUT',
            completed_at = NOW(),
            error_message = 'Visibility timeout exceeded'
        WHERE message_id = v_message.message_id
          AND attempt_number = v_message.attempt_count
          AND outcome IS NULL;

        IF v_message.attempt_count < v_message.maximum_attempts THEN

            v_delay := LEAST(
                v_message.retry_max_seconds,
                v_message.retry_base_seconds
                * POWER(
                    2,
                    LEAST(v_message.attempt_count - 1, 30)
                )::INTEGER
            );

            UPDATE messages
            SET status = 'RETRY_PENDING',
                current_consumer_id = NULL,
                available_at = NOW() + make_interval(secs => v_delay),
                last_error = 'Visibility timeout exceeded'
            WHERE message_id = v_message.message_id;

        ELSE

            UPDATE messages
            SET status = 'DEAD_LETTERED',
                current_consumer_id = NULL,
                last_error = 'Visibility timeout exceeded'
            WHERE message_id = v_message.message_id;

            IF v_message.dead_letter_enabled THEN
                INSERT INTO dead_letters (
                    message_id,
                    original_queue_id,
                    final_attempt,
                    failure_reason
                )
                VALUES (
                    v_message.message_id,
                    p_queue_id,
                    v_message.attempt_count,
                    'Visibility timeout exceeded'
                );
            END IF;

        END IF;

        v_recovered := v_recovered + 1;
    END LOOP;

    RETURN v_recovered;
END;
$$;

-- ------------------------------------------------------------
-- 15. DEAD-LETTER REPLAY
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION replay_dead_letter(
    p_message_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_message RECORD;
BEGIN
    SELECT *
    INTO v_message
    FROM messages
    WHERE message_id = p_message_id
      AND status = 'DEAD_LETTERED'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dead-letter message not found';
    END IF;

    DELETE FROM dead_letters
    WHERE message_id = p_message_id;

    UPDATE messages
    SET status = 'READY',
        attempt_count = 0,
        current_consumer_id = NULL,
        available_at = NOW(),
        delivered_at = NULL,
        acknowledged_at = NULL,
        last_error = NULL
    WHERE message_id = p_message_id;

    RETURN TRUE;
END;
$$;

-- ------------------------------------------------------------
-- 16. QUEUE METRICS VIEW
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW queue_metrics AS
SELECT
    q.queue_id,
    q.queue_name,

    COUNT(m.message_id) AS total_messages,

    COUNT(*) FILTER (
        WHERE m.status = 'READY'
    ) AS ready_messages,

    COUNT(*) FILTER (
        WHERE m.status = 'IN_FLIGHT'
    ) AS in_flight_messages,

    COUNT(*) FILTER (
        WHERE m.status = 'RETRY_PENDING'
    ) AS retry_messages,

    COUNT(*) FILTER (
        WHERE m.status = 'ACKNOWLEDGED'
    ) AS acknowledged_messages,

    COUNT(*) FILTER (
        WHERE m.status = 'DEAD_LETTERED'
    ) AS dead_letter_messages,

    COALESCE(
        ROUND(
            AVG(m.attempt_count)::NUMERIC,
            2
        ),
        0
    ) AS average_attempts

FROM queues q
LEFT JOIN messages m ON m.queue_id = q.queue_id
GROUP BY q.queue_id, q.queue_name;

-- ------------------------------------------------------------
-- 17. CONSUMER LOAD VIEW
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW consumer_load AS
SELECT
    c.consumer_id,
    c.consumer_name,
    q.queue_name,
    c.status,
    c.concurrency_limit,

    COUNT(m.message_id) FILTER (
        WHERE m.status = 'IN_FLIGHT'
    ) AS active_deliveries

FROM consumers c
JOIN queues q ON q.queue_id = c.queue_id
LEFT JOIN messages m
    ON m.current_consumer_id = c.consumer_id
GROUP BY
    c.consumer_id,
    c.consumer_name,
    q.queue_name,
    c.status,
    c.concurrency_limit;

-- ------------------------------------------------------------
-- 18. ELIGIBILITY DETERMINATION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION queue_is_eligible(
    p_queue_id BIGINT,
    p_consumer_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM queues q
        JOIN consumers c ON c.queue_id = q.queue_id
        WHERE q.queue_id = p_queue_id
          AND c.consumer_id = p_consumer_id
          AND q.enabled = TRUE
          AND c.status = 'ACTIVE'
          AND (
              SELECT COUNT(*)
              FROM messages m
              WHERE m.current_consumer_id = c.consumer_id
                AND m.status = 'IN_FLIGHT'
          ) < c.concurrency_limit
    );
$$;

-- ------------------------------------------------------------
-- 19. SAMPLE DATA
-- ------------------------------------------------------------

INSERT INTO producers (
    producer_name,
    service_name
)
VALUES
    ('payment-api', 'payment-service'),
    ('order-api', 'order-service'),
    ('notification-api', 'notification-service');

INSERT INTO queues (
    queue_name,
    capacity,
    maximum_attempts,
    visibility_timeout_seconds,
    retry_base_seconds,
    retry_max_seconds
)
VALUES
    ('payments', 1000, 3, 30, 1, 60),
    ('orders', 2000, 5, 30, 2, 120),
    ('notifications', 5000, 4, 60, 5, 300);

INSERT INTO consumers (
    consumer_name,
    queue_id,
    concurrency_limit
)
SELECT
    'payment-worker-01',
    queue_id,
    5
FROM queues
WHERE queue_name = 'payments';

INSERT INTO consumers (
    consumer_name,
    queue_id,
    concurrency_limit
)
SELECT
    'payment-worker-02',
    queue_id,
    3
FROM queues
WHERE queue_name = 'payments';

INSERT INTO consumers (
    consumer_name,
    queue_id,
    concurrency_limit
)
SELECT
    'order-worker-01',
    queue_id,
    4
FROM queues
WHERE queue_name = 'orders';

INSERT INTO consumers (
    consumer_name,
    queue_id,
    concurrency_limit,
    status
)
SELECT
    'notification-worker-paused',
    queue_id,
    2,
    'PAUSED'
FROM queues
WHERE queue_name = 'notifications';

-- ------------------------------------------------------------
-- 20. VALID MESSAGE PUBLICATION
-- ------------------------------------------------------------

SELECT publish_message(
    (SELECT producer_id FROM producers
     WHERE producer_name = 'payment-api'),
    (SELECT queue_id FROM queues
     WHERE queue_name = 'payments'),
    'payment.created',
    '{"transaction_id":"TX-1001","amount":2500,"currency":"INR"}',
    'PAYMENT-KEY-1001'
);

SELECT publish_message(
    (SELECT producer_id FROM producers
     WHERE producer_name = 'payment-api'),
    (SELECT queue_id FROM queues
     WHERE queue_name = 'payments'),
    'payment.created',
    '{"transaction_id":"TX-1002","amount":5000,"currency":"INR"}',
    'PAYMENT-KEY-1002'
);

SELECT publish_message(
    (SELECT producer_id FROM producers
     WHERE producer_name = 'order-api'),
    (SELECT queue_id FROM queues
     WHERE queue_name = 'orders'),
    'order.created',
    '{"order_id":"ORD-1001","items":3}',
    'ORDER-KEY-1001'
);

-- Duplicate publication returns the original message ID.
SELECT publish_message(
    (SELECT producer_id FROM producers
     WHERE producer_name = 'payment-api'),
    (SELECT queue_id FROM queues
     WHERE queue_name = 'payments'),
    'payment.created',
    '{"transaction_id":"TX-1001","amount":2500,"currency":"INR"}',
    'PAYMENT-KEY-1001'
);

-- ------------------------------------------------------------
-- 21. MESSAGE CLAIM AND ACKNOWLEDGMENT
-- ------------------------------------------------------------

DO $$
DECLARE
    v_queue_id BIGINT;
    v_consumer_id BIGINT;
    v_message_id UUID;
BEGIN
    SELECT queue_id INTO v_queue_id
    FROM queues
    WHERE queue_name = 'payments';

    SELECT consumer_id INTO v_consumer_id
    FROM consumers
    WHERE consumer_name = 'payment-worker-01';

    SELECT claimed_message_id
    INTO v_message_id
    FROM claim_message(v_queue_id, v_consumer_id);

    IF v_message_id IS NOT NULL THEN
        PERFORM acknowledge_message(
            v_message_id,
            v_consumer_id
        );
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- 22. NEGATIVE ACKNOWLEDGMENT
-- ------------------------------------------------------------

DO $$
DECLARE
    v_queue_id BIGINT;
    v_consumer_id BIGINT;
    v_message_id UUID;
BEGIN
    SELECT queue_id INTO v_queue_id
    FROM queues
    WHERE queue_name = 'payments';

    SELECT consumer_id INTO v_consumer_id
    FROM consumers
    WHERE consumer_name = 'payment-worker-02';

    SELECT claimed_message_id
    INTO v_message_id
    FROM claim_message(v_queue_id, v_consumer_id);

    IF v_message_id IS NOT NULL THEN
        PERFORM reject_message(
            v_message_id,
            v_consumer_id,
            'Temporary payment gateway failure',
            TRUE
        );
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- 23. VALIDATION EXAMPLES
-- ------------------------------------------------------------

-- Inactive consumers are not eligible.
SELECT queue_is_eligible(
    q.queue_id,
    c.consumer_id
) AS consumer_eligible
FROM queues q
JOIN consumers c ON c.queue_id = q.queue_id
WHERE q.queue_name = 'notifications';

-- Display current queue load.
SELECT *
FROM queue_metrics
ORDER BY queue_name;

-- Display consumer load.
SELECT *
FROM consumer_load
ORDER BY queue_name, consumer_name;

-- ------------------------------------------------------------
-- 24. RETRY AND FAILURE REPORTING
-- ------------------------------------------------------------

SELECT
    q.queue_name,
    m.message_id,
    m.status,
    m.attempt_count,
    m.maximum_attempts,
    m.available_at,
    m.last_error
FROM messages m
JOIN queues q ON q.queue_id = m.queue_id
WHERE m.status IN (
    'RETRY_PENDING',
    'DEAD_LETTERED'
)
ORDER BY m.created_at;

-- ------------------------------------------------------------
-- 25. DELIVERY PERFORMANCE REPORT
-- ------------------------------------------------------------

SELECT
    c.consumer_name,
    COUNT(d.delivery_id) AS total_deliveries,

    COUNT(*) FILTER (
        WHERE d.outcome = 'ACK'
    ) AS successful_deliveries,

    COUNT(*) FILTER (
        WHERE d.outcome = 'NACK'
    ) AS rejected_deliveries,

    COUNT(*) FILTER (
        WHERE d.outcome = 'TIMEOUT'
    ) AS timed_out_deliveries,

    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (d.completed_at - d.delivered_at)
            )
        )::NUMERIC,
        3
    ) AS average_processing_seconds

FROM consumers c
LEFT JOIN deliveries d
    ON d.consumer_id = c.consumer_id
GROUP BY c.consumer_id, c.consumer_name
ORDER BY c.consumer_name;

-- ------------------------------------------------------------
-- 26. WORKFLOW PROCESSING USING A CTE
-- ------------------------------------------------------------

WITH queue_summary AS (
    SELECT
        queue_id,
        COUNT(*) FILTER (
            WHERE status = 'READY'
        ) AS ready_count,

        COUNT(*) FILTER (
            WHERE status = 'IN_FLIGHT'
        ) AS active_count,

        COUNT(*) FILTER (
            WHERE status = 'RETRY_PENDING'
        ) AS retry_count
    FROM messages
    GROUP BY queue_id
)
SELECT
    q.queue_name,
    COALESCE(s.ready_count, 0) AS ready_count,
    COALESCE(s.active_count, 0) AS active_count,
    COALESCE(s.retry_count, 0) AS retry_count,
    q.capacity
FROM queues q
LEFT JOIN queue_summary s ON s.queue_id = q.queue_id
ORDER BY q.queue_name;

-- ------------------------------------------------------------
-- 27. EXPIRED DELIVERY RECOVERY
-- ------------------------------------------------------------

SELECT recover_expired_messages(
    (SELECT queue_id
     FROM queues
     WHERE queue_name = 'payments')
);

-- ------------------------------------------------------------
-- 28. DEAD-LETTER INSPECTION
-- ------------------------------------------------------------

SELECT
    dl.dead_letter_id,
    m.message_id,
    q.queue_name,
    dl.final_attempt,
    dl.failure_reason,
    dl.dead_lettered_at,
    m.payload
FROM dead_letters dl
JOIN messages m ON m.message_id = dl.message_id
JOIN queues q ON q.queue_id = dl.original_queue_id
ORDER BY dl.dead_lettered_at DESC;

-- ------------------------------------------------------------
-- 29. REPORTING: DELIVERY SUCCESS RATE
-- ------------------------------------------------------------

SELECT
    q.queue_name,

    COUNT(d.delivery_id) AS total_attempts,

    COUNT(*) FILTER (
        WHERE d.outcome = 'ACK'
    ) AS successful_attempts,

    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE d.outcome = 'ACK')
        / NULLIF(COUNT(d.delivery_id), 0),
        2
    ) AS success_percentage

FROM queues q
LEFT JOIN messages m ON m.queue_id = q.queue_id
LEFT JOIN deliveries d ON d.message_id = m.message_id
GROUP BY q.queue_id, q.queue_name
ORDER BY q.queue_name;

COMMIT;

-- ============================================================
-- OPERATIONAL NOTES
--
-- 1. claim_message uses FOR UPDATE SKIP LOCKED to support
--    concurrent workers without claiming the same database row.
--
-- 2. ACK updates message state and delivery history in one
--    database transaction.
--
-- 3. NACK schedules a retry using exponential backoff.
--
-- 4. Visibility timeout recovery handles abandoned deliveries.
--
-- 5. Idempotency keys prevent duplicate publication for a
--    producer/key pair.
--
-- 6. Delivery is at-least-once. Consumers must make business
--    processing idempotent.
--
-- 7. The database model does not by itself guarantee atomicity
--    between an external business operation and a message ACK.
--    Use a transactional outbox/inbox or an appropriate
--    distributed transaction design for that requirement.
--
-- 8. Production deployments should restrict function execution,
--    separate application roles, encrypt sensitive payloads,
--    configure retention, and monitor queue age and retry rates.
-- ============================================================
