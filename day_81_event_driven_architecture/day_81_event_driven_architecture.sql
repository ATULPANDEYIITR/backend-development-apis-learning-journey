-- ============================================================
-- EVENT-DRIVEN ARCHITECTURE
-- PostgreSQL 15+
--
-- Models:
--   Event producers
--   Versioned event schemas
--   Event publication
--   Event consumers
--   Consumer subscriptions
--   Consumer delivery attempts
--   Idempotency
--   Dead-letter records
--   Event replay
--   Event filtering
--   Event processing metrics
--
-- The database acts as a durable event store and transactional
-- dispatch queue. External delivery is performed by workers.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS event_platform;

SET search_path TO event_platform, public;

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE producer_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED'
);

CREATE TYPE consumer_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED'
);

CREATE TYPE event_status AS ENUM (
    'PENDING',
    'PUBLISHED',
    'PROCESSING',
    'CONSUMED',
    'FAILED',
    'DEAD_LETTER'
);

CREATE TYPE delivery_status AS ENUM (
    'PENDING',
    'PROCESSING',
    'CONSUMED',
    'FAILED',
    'DEAD_LETTER',
    'FILTERED'
);

CREATE TYPE schema_status AS ENUM (
    'DRAFT',
    'ACTIVE',
    'DEPRECATED',
    'RETIRED'
);

-- ============================================================
-- EVENT PRODUCERS
-- ============================================================

CREATE TABLE producers (
    producer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    producer_name VARCHAR(120) NOT NULL UNIQUE,

    description TEXT,

    status producer_status NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT producer_name_not_blank
        CHECK (LENGTH(TRIM(producer_name)) > 0)
);

-- ============================================================
-- EVENT CONSUMERS
-- ============================================================

CREATE TABLE consumers (
    consumer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    consumer_name VARCHAR(120) NOT NULL UNIQUE,

    description TEXT,

    status consumer_status NOT NULL DEFAULT 'ACTIVE',

    max_retries INTEGER NOT NULL DEFAULT 3,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_max_retries
        CHECK (max_retries BETWEEN 0 AND 20)
);

-- ============================================================
-- EVENT SCHEMA REGISTRY
-- ============================================================

CREATE TABLE event_schemas (
    schema_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_type VARCHAR(150) NOT NULL,

    schema_version INTEGER NOT NULL,

    schema_definition JSONB NOT NULL,

    status schema_status NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_event_schema
        UNIQUE (event_type, schema_version),

    CONSTRAINT valid_schema_version
        CHECK (schema_version > 0),

    CONSTRAINT schema_definition_object
        CHECK (JSONB_TYPEOF(schema_definition) = 'object')
);

-- ============================================================
-- EVENT SUBSCRIPTIONS
-- ============================================================

CREATE TABLE subscriptions (
    subscription_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    consumer_id BIGINT NOT NULL
        REFERENCES consumers(consumer_id),

    event_type VARCHAR(150) NOT NULL,

    filter_definition JSONB NOT NULL DEFAULT '{}'::JSONB,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_consumer_subscription
        UNIQUE (consumer_id, event_type),

    CONSTRAINT valid_filter_definition
        CHECK (
            JSONB_TYPEOF(filter_definition) = 'object'
        )
);

-- ============================================================
-- EVENT STORE
-- ============================================================

CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    event_type VARCHAR(150) NOT NULL,

    schema_id BIGINT NOT NULL
        REFERENCES event_schemas(schema_id),

    producer_id BIGINT NOT NULL
        REFERENCES producers(producer_id),

    correlation_id UUID NOT NULL,

    causation_id UUID,

    aggregate_type VARCHAR(100),

    aggregate_id VARCHAR(150),

    aggregate_sequence BIGINT,

    payload JSONB NOT NULL,

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    status event_status NOT NULL DEFAULT 'PUBLISHED',

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_event_payload
        CHECK (JSONB_TYPEOF(payload) = 'object'),

    CONSTRAINT valid_event_metadata
        CHECK (JSONB_TYPEOF(metadata) = 'object'),

    CONSTRAINT valid_aggregate_sequence
        CHECK (
            aggregate_sequence IS NULL
            OR aggregate_sequence > 0
        )
);

-- Prevent duplicate aggregate sequence numbers where supplied.
CREATE UNIQUE INDEX unique_aggregate_event_sequence
ON events (
    aggregate_type,
    aggregate_id,
    aggregate_sequence
)
WHERE aggregate_sequence IS NOT NULL;

-- ============================================================
-- CONSUMER DELIVERY RECORDS
-- ============================================================

CREATE TABLE event_deliveries (
    delivery_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_id UUID NOT NULL
        REFERENCES events(event_id),

    consumer_id BIGINT NOT NULL
        REFERENCES consumers(consumer_id),

    status delivery_status NOT NULL DEFAULT 'PENDING',

    attempts INTEGER NOT NULL DEFAULT 0,

    max_retries INTEGER NOT NULL DEFAULT 3,

    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    locked_at TIMESTAMPTZ,

    locked_by VARCHAR(150),

    completed_at TIMESTAMPTZ,

    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_event_consumer_delivery
        UNIQUE (event_id, consumer_id),

    CONSTRAINT valid_attempts
        CHECK (attempts >= 0),

    CONSTRAINT valid_delivery_retries
        CHECK (max_retries BETWEEN 0 AND 20)
);

-- ============================================================
-- IDEMPOTENCY RECORDS
-- ============================================================

CREATE TABLE idempotency_records (
    idempotency_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    consumer_id BIGINT NOT NULL
        REFERENCES consumers(consumer_id),

    idempotency_key VARCHAR(200) NOT NULL,

    event_id UUID NOT NULL
        REFERENCES events(event_id),

    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_consumer_idempotency
        UNIQUE (consumer_id, idempotency_key)
);

-- ============================================================
-- DEAD-LETTER QUEUE
-- ============================================================

CREATE TABLE dead_letters (
    dead_letter_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    delivery_id BIGINT NOT NULL UNIQUE
        REFERENCES event_deliveries(delivery_id),

    event_id UUID NOT NULL
        REFERENCES events(event_id),

    consumer_id BIGINT NOT NULL
        REFERENCES consumers(consumer_id),

    failure_reason TEXT NOT NULL,

    failed_attempts INTEGER NOT NULL,

    failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    replayed_at TIMESTAMPTZ,

    replay_count INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT valid_failed_attempts
        CHECK (failed_attempts > 0),

    CONSTRAINT valid_replay_count
        CHECK (replay_count >= 0)
);

-- ============================================================
-- EVENT AUDIT LOG
-- ============================================================

CREATE TABLE event_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_id UUID
        REFERENCES events(event_id),

    consumer_id BIGINT
        REFERENCES consumers(consumer_id),

    action VARCHAR(100) NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PERFORMANCE INDEXES
-- ============================================================

CREATE INDEX idx_events_type_time
ON events (event_type, occurred_at DESC);

CREATE INDEX idx_events_correlation
ON events (correlation_id);

CREATE INDEX idx_events_status
ON events (status, published_at);

CREATE INDEX idx_events_payload
ON events USING GIN (payload);

CREATE INDEX idx_deliveries_pending
ON event_deliveries (available_at, delivery_id)
WHERE status IN ('PENDING', 'FAILED');

CREATE INDEX idx_deliveries_consumer_status
ON event_deliveries (consumer_id, status);

CREATE INDEX idx_dead_letters_consumer
ON dead_letters (consumer_id, failed_at DESC);

CREATE INDEX idx_audit_event
ON event_audit (event_id, recorded_at DESC);

-- ============================================================
-- SCHEMA VALIDATION FUNCTION
-- Supports a controlled JSON schema subset:
-- required, properties, and primitive JSON types.
-- ============================================================

CREATE OR REPLACE FUNCTION validate_event_payload(
    p_schema JSONB,
    p_payload JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_field RECORD;
    v_required JSONB;
    v_expected TEXT;
    v_actual TEXT;
BEGIN
    IF JSONB_TYPEOF(p_schema) <> 'object'
       OR JSONB_TYPEOF(p_payload) <> 'object' THEN
        RETURN FALSE;
    END IF;

    v_required := COALESCE(
        p_schema->'required',
        '[]'::JSONB
    );

    IF JSONB_TYPEOF(v_required) <> 'array' THEN
        RETURN FALSE;
    END IF;

    FOR v_field IN
        SELECT jsonb_array_elements_text(v_required) AS field_name
    LOOP
        IF NOT (p_payload ? v_field.field_name) THEN
            RETURN FALSE;
        END IF;
    END LOOP;

    IF JSONB_TYPEOF(p_schema->'properties') <> 'object' THEN
        RETURN FALSE;
    END IF;

    FOR v_field IN
        SELECT key, value
        FROM JSONB_EACH(p_schema->'properties')
    LOOP
        IF NOT (p_payload ? v_field.key) THEN
            CONTINUE;
        END IF;

        v_expected := v_field.value->>'type';

        v_actual := JSONB_TYPEOF(
            p_payload->v_field.key
        );

        IF v_expected IS NOT NULL
           AND v_expected <> v_actual THEN
            RETURN FALSE;
        END IF;
    END LOOP;

    -- Reject unknown properties when additionalProperties is false.
    IF COALESCE(
        (p_schema->>'additionalProperties')::BOOLEAN,
        TRUE
    ) = FALSE THEN

        FOR v_field IN
            SELECT key
            FROM JSONB_EACH(p_payload)
        LOOP
            IF NOT (
                p_schema->'properties' ? v_field.key
            ) THEN
                RETURN FALSE;
            END IF;
        END LOOP;
    END IF;

    RETURN TRUE;
END;
$$;

-- ============================================================
-- EVENT PUBLICATION PROCEDURE
-- Schema validation and event persistence occur together.
-- ============================================================

CREATE OR REPLACE FUNCTION publish_event(
    p_event_type VARCHAR,
    p_producer_name VARCHAR,
    p_version INTEGER,
    p_payload JSONB,
    p_correlation_id UUID DEFAULT gen_random_uuid()
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_producer_id BIGINT;
    v_schema_id BIGINT;
    v_schema JSONB;
    v_event_id UUID;
BEGIN
    SELECT producer_id
    INTO v_producer_id
    FROM producers
    WHERE producer_name = p_producer_name
      AND status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Producer is missing or inactive: %',
            p_producer_name;
    END IF;

    SELECT schema_id, schema_definition
    INTO v_schema_id, v_schema
    FROM event_schemas
    WHERE event_type = p_event_type
      AND schema_version = p_version
      AND status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No active schema for % version %',
            p_event_type,
            p_version;
    END IF;

    IF NOT validate_event_payload(v_schema, p_payload) THEN
        RAISE EXCEPTION
            'Event payload validation failed for %',
            p_event_type;
    END IF;

    v_event_id := gen_random_uuid();

    INSERT INTO events (
        event_id,
        event_type,
        schema_id,
        producer_id,
        correlation_id,
        payload,
        status
    )
    VALUES (
        v_event_id,
        p_event_type,
        v_schema_id,
        v_producer_id,
        p_correlation_id,
        p_payload,
        'PUBLISHED'
    );

    -- Create one durable delivery per active subscriber.
    INSERT INTO event_deliveries (
        event_id,
        consumer_id,
        max_retries
    )
    SELECT
        v_event_id,
        c.consumer_id,
        c.max_retries
    FROM consumers c
    JOIN subscriptions s
      ON s.consumer_id = c.consumer_id
    WHERE s.event_type = p_event_type
      AND s.enabled = TRUE
      AND c.status = 'ACTIVE';

    INSERT INTO event_audit (
        event_id,
        action,
        details
    )
    VALUES (
        v_event_id,
        'EVENT_PUBLISHED',
        jsonb_build_object(
            'event_type', p_event_type,
            'producer', p_producer_name,
            'schema_version', p_version
        )
    );

    RETURN v_event_id;
END;
$$;

-- ============================================================
-- DELIVERY PROCESSING
-- A worker claims deliveries using FOR UPDATE SKIP LOCKED.
-- External network calls must occur outside the claim transaction.
-- ============================================================

CREATE OR REPLACE FUNCTION claim_event_deliveries(
    p_worker VARCHAR,
    p_batch_size INTEGER DEFAULT 10
)
RETURNS TABLE (
    claimed_delivery_id BIGINT,
    claimed_event_id UUID,
    claimed_consumer_id BIGINT,
    claimed_event_type VARCHAR,
    claimed_payload JSONB,
    claimed_attempt INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_worker IS NULL OR LENGTH(TRIM(p_worker)) = 0 THEN
        RAISE EXCEPTION 'Worker name is required';
    END IF;

    IF p_batch_size < 1 OR p_batch_size > 500 THEN
        RAISE EXCEPTION 'Invalid batch size';
    END IF;

    RETURN QUERY
    WITH selected AS (
        SELECT d.delivery_id
        FROM event_deliveries d
        JOIN consumers c
          ON c.consumer_id = d.consumer_id
        JOIN events e
          ON e.event_id = d.event_id
        WHERE d.status IN ('PENDING', 'FAILED')
          AND d.available_at <= NOW()
          AND d.attempts < d.max_retries + 1
          AND c.status = 'ACTIVE'
          AND e.status IN ('PUBLISHED', 'PROCESSING')
        ORDER BY d.available_at, d.delivery_id
        LIMIT p_batch_size
        FOR UPDATE OF d SKIP LOCKED
    ),
    claimed AS (
        UPDATE event_deliveries d
        SET status = 'PROCESSING',
            attempts = d.attempts + 1,
            locked_at = NOW(),
            locked_by = p_worker
        FROM selected s
        WHERE d.delivery_id = s.delivery_id
        RETURNING d.*
    )
    SELECT
        d.delivery_id,
        e.event_id,
        d.consumer_id,
        e.event_type::VARCHAR,
        e.payload,
        d.attempts
    FROM claimed d
    JOIN events e
      ON e.event_id = d.event_id;
END;
$$;

-- ============================================================
-- DELIVERY COMPLETION
-- Idempotency record and successful delivery are committed
-- in the same transaction.
-- ============================================================

CREATE OR REPLACE PROCEDURE complete_delivery(
    p_delivery_id BIGINT,
    p_worker VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id UUID;
    v_consumer_id BIGINT;
BEGIN
    SELECT event_id, consumer_id
    INTO v_event_id, v_consumer_id
    FROM event_deliveries
    WHERE delivery_id = p_delivery_id
      AND status = 'PROCESSING'
      AND locked_by = p_worker
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Delivery is not owned by worker %',
            p_worker;
    END IF;

    INSERT INTO idempotency_records (
        consumer_id,
        idempotency_key,
        event_id
    )
    VALUES (
        v_consumer_id,
        v_event_id::TEXT,
        v_event_id
    )
    ON CONFLICT (
        consumer_id,
        idempotency_key
    )
    DO NOTHING;

    UPDATE event_deliveries
    SET status = 'CONSUMED',
        completed_at = NOW(),
        locked_at = NULL,
        locked_by = NULL,
        last_error = NULL
    WHERE delivery_id = p_delivery_id;

    INSERT INTO event_audit (
        event_id,
        consumer_id,
        action
    )
    VALUES (
        v_event_id,
        v_consumer_id,
        'DELIVERY_COMPLETED'
    );
END;
$$;

-- ============================================================
-- DELIVERY FAILURE AND DEAD-LETTER ROUTING
-- ============================================================

CREATE OR REPLACE PROCEDURE fail_delivery(
    p_delivery_id BIGINT,
    p_worker VARCHAR,
    p_error TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id UUID;
    v_consumer_id BIGINT;
    v_attempts INTEGER;
    v_max_retries INTEGER;
    v_status delivery_status;
BEGIN
    SELECT
        event_id,
        consumer_id,
        attempts,
        max_retries
    INTO
        v_event_id,
        v_consumer_id,
        v_attempts,
        v_max_retries
    FROM event_deliveries
    WHERE delivery_id = p_delivery_id
      AND status = 'PROCESSING'
      AND locked_by = p_worker
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delivery ownership validation failed';
    END IF;

    IF v_attempts >= v_max_retries + 1 THEN
        v_status := 'DEAD_LETTER';
    ELSE
        v_status := 'FAILED';
    END IF;

    UPDATE event_deliveries
    SET status = v_status,
        last_error = LEFT(p_error, 4000),
        available_at = CASE
            WHEN v_status = 'FAILED'
            THEN NOW() + (
                LEAST(POWER(2, v_attempts), 3600)
                * INTERVAL '1 second'
            )
            ELSE available_at
        END,
        locked_at = NULL,
        locked_by = NULL
    WHERE delivery_id = p_delivery_id;

    IF v_status = 'DEAD_LETTER' THEN
        INSERT INTO dead_letters (
            delivery_id,
            event_id,
            consumer_id,
            failure_reason,
            failed_attempts
        )
        VALUES (
            p_delivery_id,
            v_event_id,
            v_consumer_id,
            LEFT(p_error, 4000),
            v_attempts
        );

        INSERT INTO event_audit (
            event_id,
            consumer_id,
            action,
            details
        )
        VALUES (
            v_event_id,
            v_consumer_id,
            'DEAD_LETTER_CREATED',
            jsonb_build_object(
                'attempts', v_attempts,
                'error', LEFT(p_error, 4000)
            )
        );
    END IF;
END;
$$;

-- ============================================================
-- EVENT REPLAY
-- Only dead-letter deliveries can be replayed through this
-- procedure. Business-level idempotency remains necessary.
-- ============================================================

CREATE OR REPLACE PROCEDURE replay_dead_letter(
    p_dead_letter_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_delivery_id BIGINT;
    v_event_id UUID;
    v_consumer_id BIGINT;
BEGIN
    SELECT
        delivery_id,
        event_id,
        consumer_id
    INTO
        v_delivery_id,
        v_event_id,
        v_consumer_id
    FROM dead_letters
    WHERE dead_letter_id = p_dead_letter_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dead-letter record not found';
    END IF;

    UPDATE event_deliveries
    SET status = 'PENDING',
        attempts = 0,
        available_at = NOW(),
        completed_at = NULL,
        last_error = NULL,
        locked_at = NULL,
        locked_by = NULL
    WHERE delivery_id = v_delivery_id;

    UPDATE dead_letters
    SET replayed_at = NOW(),
        replay_count = replay_count + 1
    WHERE dead_letter_id = p_dead_letter_id;

    INSERT INTO event_audit (
        event_id,
        consumer_id,
        action
    )
    VALUES (
        v_event_id,
        v_consumer_id,
        'DEAD_LETTER_REPLAYED'
    );
END;
$$;

-- ============================================================
-- EVENT STATE RECONCILIATION
-- Event state is derived from its individual deliveries.
-- ============================================================

CREATE OR REPLACE FUNCTION reconcile_event_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id UUID;
    v_total INTEGER;
    v_consumed INTEGER;
    v_failed INTEGER;
    v_dead INTEGER;
    v_processing INTEGER;
BEGIN
    v_event_id := COALESCE(NEW.event_id, OLD.event_id);

    SELECT
        COUNT(*),
        COUNT(*) FILTER (
            WHERE status = 'CONSUMED'
        ),
        COUNT(*) FILTER (
            WHERE status = 'FAILED'
        ),
        COUNT(*) FILTER (
            WHERE status = 'DEAD_LETTER'
        ),
        COUNT(*) FILTER (
            WHERE status = 'PROCESSING'
        )
    INTO
        v_total,
        v_consumed,
        v_failed,
        v_dead,
        v_processing
    FROM event_deliveries
    WHERE event_id = v_event_id;

    UPDATE events
    SET status = CASE
        WHEN v_dead > 0 THEN 'DEAD_LETTER'::event_status
        WHEN v_processing > 0 THEN 'PROCESSING'::event_status
        WHEN v_total = 0 THEN 'PUBLISHED'::event_status
        WHEN v_consumed = v_total THEN 'CONSUMED'::event_status
        WHEN v_failed > 0 THEN 'FAILED'::event_status
        ELSE 'PUBLISHED'::event_status
    END
    WHERE event_id = v_event_id;

    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_reconcile_event_status
AFTER INSERT OR UPDATE OF status
ON event_deliveries
FOR EACH ROW
EXECUTE FUNCTION reconcile_event_status();

-- ============================================================
-- REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW event_processing_report AS
SELECT
    e.event_id,
    e.event_type,
    p.producer_name,
    e.correlation_id,
    e.status AS event_status,
    e.occurred_at,
    COUNT(d.delivery_id) AS total_deliveries,
    COUNT(*) FILTER (
        WHERE d.status = 'CONSUMED'
    ) AS consumed_deliveries,
    COUNT(*) FILTER (
        WHERE d.status = 'FAILED'
    ) AS failed_deliveries,
    COUNT(*) FILTER (
        WHERE d.status = 'DEAD_LETTER'
    ) AS dead_letter_deliveries,
    COUNT(*) FILTER (
        WHERE d.status = 'PROCESSING'
    ) AS processing_deliveries
FROM events e
JOIN producers p
  ON p.producer_id = e.producer_id
LEFT JOIN event_deliveries d
  ON d.event_id = e.event_id
GROUP BY
    e.event_id,
    e.event_type,
    p.producer_name,
    e.correlation_id,
    e.status,
    e.occurred_at;

-- ============================================================
-- SAMPLE PRODUCERS
-- ============================================================

INSERT INTO producers (
    producer_name,
    description
)
VALUES
(
    'OrderService',
    'Creates customer orders'
),
(
    'PaymentService',
    'Publishes payment-related events'
),
(
    'InventoryService',
    'Publishes stock-related events'
);

-- ============================================================
-- SAMPLE CONSUMERS
-- ============================================================

INSERT INTO consumers (
    consumer_name,
    description,
    max_retries
)
VALUES
(
    'InventoryConsumer',
    'Reserves stock for new orders',
    3
),
(
    'PaymentConsumer',
    'Processes payment authorization',
    3
),
(
    'NotificationConsumer',
    'Sends customer notifications',
    2
),
(
    'AnalyticsConsumer',
    'Collects order analytics',
    1
);

-- ============================================================
-- VERSIONED EVENT SCHEMAS
-- ============================================================

INSERT INTO event_schemas (
    event_type,
    schema_version,
    schema_definition,
    status
)
VALUES
(
    'OrderCreated',
    1,
    '{
        "type": "object",
        "required": [
            "order_id",
            "customer_id",
            "amount"
        ],
        "properties": {
            "order_id": {"type": "string"},
            "customer_id": {"type": "string"},
            "amount": {"type": "number"}
        },
        "additionalProperties": false
    }'::JSONB,
    'ACTIVE'
),
(
    'OrderCreated',
    2,
    '{
        "type": "object",
        "required": [
            "order_id",
            "customer_id",
            "amount",
            "currency"
        ],
        "properties": {
            "order_id": {"type": "string"},
            "customer_id": {"type": "string"},
            "amount": {"type": "number"},
            "currency": {"type": "string"}
        },
        "additionalProperties": false
    }'::JSONB,
    'ACTIVE'
),
(
    'PaymentCompleted',
    1,
    '{
        "type": "object",
        "required": [
            "payment_id",
            "order_id",
            "amount"
        ],
        "properties": {
            "payment_id": {"type": "string"},
            "order_id": {"type": "string"},
            "amount": {"type": "number"}
        },
        "additionalProperties": false
    }'::JSONB,
    'ACTIVE'
);

-- ============================================================
-- SUBSCRIPTIONS
-- ============================================================

INSERT INTO subscriptions (
    consumer_id,
    event_type,
    filter_definition
)
SELECT
    consumer_id,
    'OrderCreated',
    '{}'::JSONB
FROM consumers
WHERE consumer_name IN (
    'InventoryConsumer',
    'PaymentConsumer',
    'NotificationConsumer',
    'AnalyticsConsumer'
);

-- ============================================================
-- TRANSACTIONAL EVENT PUBLICATION
-- ============================================================

DO $$
DECLARE
    v_event_id UUID;
BEGIN
    v_event_id := publish_event(
        'OrderCreated',
        'OrderService',
        1,
        '{
            "order_id": "ORD-5001",
            "customer_id": "CUST-501",
            "amount": 2500.50
        }'::JSONB,
        gen_random_uuid()
    );

    RAISE NOTICE 'Published event: %', v_event_id;
END;
$$;

-- ============================================================
-- SAMPLE INVALID EVENT
-- Validation failure is caught without aborting the script.
-- ============================================================

DO $$
BEGIN
    PERFORM publish_event(
        'OrderCreated',
        'OrderService',
        1,
        '{
            "order_id": "ORD-INVALID",
            "amount": -500
        }'::JSONB,
        gen_random_uuid()
    );

EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Expected validation failure: %', SQLERRM;
END;
$$;

-- ============================================================
-- SAMPLE DELIVERY CLAIM
-- A real worker would commit this claim, process the message,
-- and call complete_delivery or fail_delivery afterward.
-- ============================================================

CREATE TEMP TABLE claimed_delivery_snapshot
ON COMMIT DROP
AS
SELECT *
FROM claim_event_deliveries(
    'worker-01',
    10
);

-- Demonstrate successful processing for inventory.
CALL complete_delivery(
    (
        SELECT claimed_delivery_id
        FROM claimed_delivery_snapshot
        WHERE claimed_consumer_id = (
            SELECT consumer_id
            FROM consumers
            WHERE consumer_name = 'InventoryConsumer'
        )
        LIMIT 1
    ),
    'worker-01'
);

-- Demonstrate a downstream failure.
CALL fail_delivery(
    (
        SELECT claimed_delivery_id
        FROM claimed_delivery_snapshot
        WHERE claimed_consumer_id = (
            SELECT consumer_id
            FROM consumers
            WHERE consumer_name = 'PaymentConsumer'
        )
        LIMIT 1
    ),
    'worker-01',
    'Payment gateway temporarily unavailable'
);

-- ============================================================
-- REPORTING QUERIES
-- ============================================================

-- 1. Event retrieval.
SELECT
    event_id,
    event_type,
    producer_id,
    payload,
    status,
    occurred_at
FROM events
ORDER BY occurred_at DESC;

-- 2. Delivery status by consumer.
SELECT
    c.consumer_name,
    d.status,
    COUNT(*) AS delivery_count
FROM event_deliveries d
JOIN consumers c
  ON c.consumer_id = d.consumer_id
GROUP BY c.consumer_name, d.status
ORDER BY c.consumer_name, d.status;

-- 3. Event processing performance.
SELECT
    event_type,
    COUNT(*) AS published_events,
    SUM(total_deliveries) AS deliveries,
    SUM(consumed_deliveries) AS consumed,
    SUM(failed_deliveries) AS failed,
    SUM(dead_letter_deliveries) AS dead_letters
FROM event_processing_report
GROUP BY event_type;

-- 4. Events with unsuccessful deliveries.
SELECT
    event_id,
    event_type,
    event_status,
    failed_deliveries,
    dead_letter_deliveries
FROM event_processing_report
WHERE failed_deliveries > 0
   OR dead_letter_deliveries > 0;

-- 5. Dead-letter inspection.
SELECT
    dl.dead_letter_id,
    e.event_type,
    c.consumer_name,
    dl.failure_reason,
    dl.failed_attempts,
    dl.failed_at,
    dl.replay_count
FROM dead_letters dl
JOIN events e
  ON e.event_id = dl.event_id
JOIN consumers c
  ON c.consumer_id = dl.consumer_id
ORDER BY dl.failed_at DESC;

-- 6. Correlation-based event tracing.
SELECT
    correlation_id,
    event_id,
    event_type,
    occurred_at,
    status
FROM events
WHERE correlation_id = (
    SELECT correlation_id
    FROM events
    ORDER BY occurred_at DESC
    LIMIT 1
)
ORDER BY occurred_at;

-- 7. Consumer eligibility.
SELECT
    c.consumer_name,
    c.status AS consumer_status,
    s.event_type,
    s.enabled
FROM consumers c
JOIN subscriptions s
  ON s.consumer_id = c.consumer_id
WHERE c.status = 'ACTIVE'
  AND s.enabled = TRUE;

-- 8. Pending work available for dispatch.
SELECT
    d.delivery_id,
    e.event_type,
    c.consumer_name,
    d.attempts,
    d.available_at
FROM event_deliveries d
JOIN events e
  ON e.event_id = d.event_id
JOIN consumers c
  ON c.consumer_id = d.consumer_id
WHERE d.status IN ('PENDING', 'FAILED')
  AND d.available_at <= NOW()
  AND d.attempts < d.max_retries + 1
ORDER BY d.available_at;

-- 9. Consumer success rates.
SELECT
    c.consumer_name,
    COUNT(d.delivery_id) AS total_deliveries,
    COUNT(*) FILTER (
        WHERE d.status = 'CONSUMED'
    ) AS successful_deliveries,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE d.status = 'CONSUMED'
        ) / NULLIF(COUNT(d.delivery_id), 0),
        2
    ) AS success_percentage
FROM consumers c
LEFT JOIN event_deliveries d
  ON d.consumer_id = c.consumer_id
GROUP BY c.consumer_id, c.consumer_name
ORDER BY c.consumer_name;

-- 10. Events with no registered consumers.
SELECT
    e.event_id,
    e.event_type
FROM events e
WHERE NOT EXISTS (
    SELECT 1
    FROM event_deliveries d
    WHERE d.event_id = e.event_id
);

COMMIT;

-- ============================================================
-- OPERATIONAL NOTES
--
-- 1. Publish events and create delivery records in one transaction.
-- 2. Claim work using FOR UPDATE SKIP LOCKED.
-- 3. Keep network calls outside database transactions.
-- 4. Complete delivery and persist idempotency atomically.
-- 5. Use bounded exponential retry delays.
-- 6. Monitor expired PROCESSING leases and recover abandoned work.
-- 7. Apply consumer-level idempotency to external side effects.
-- 8. Restrict direct table access through database roles.
-- 9. Use TLS and least-privilege database credentials.
-- 10. Partition high-volume event and audit tables by time.
-- 11. Retain event schemas for as long as their events remain
--     available for replay.
-- 12. Enforce payload size limits in the publishing service.
-- ============================================================
