-- ============================================================
-- SERVER-SENT EVENTS: POSTGRESQL STREAMING DATA MODEL
-- ============================================================
--
-- PostgreSQL 14+
--
-- Models:
--   1. Tenants and authenticated application users.
--   2. Event streams.
--   3. Typed events and ordered event identifiers.
--   4. Bounded event retention.
--   5. Subscriber registrations.
--   6. Event subscriptions.
--   7. Delivery tracking and reconnect cursors.
--   8. Transactional outbox.
--   9. Publication and notification.
--  10. Stream authorization.
--  11. Operational reporting.
--
-- PostgreSQL is the durable event store.
-- HTTP SSE connections are maintained by an application server.
-- LISTEN/NOTIFY provides a wake-up signal, not durable delivery.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS sse;

SET search_path TO sse, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE event_type AS ENUM (
    'message',
    'update',
    'notification',
    'progress',
    'error'
);

CREATE TYPE subscriber_status AS ENUM (
    'connected',
    'disconnected',
    'slow_consumer',
    'revoked'
);

CREATE TYPE delivery_status AS ENUM (
    'pending',
    'delivered',
    'failed',
    'expired'
);

CREATE TYPE outbox_status AS ENUM (
    'pending',
    'processing',
    'published',
    'failed'
);

-- ============================================================
-- 2. TENANTS AND USERS
-- ============================================================

CREATE TABLE tenant (
    tenant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_name VARCHAR(150) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE application_user (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(tenant_id),
    username VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, username),
    UNIQUE (tenant_id, user_id)
);

-- ============================================================
-- 3. STREAM DEFINITIONS
-- ============================================================

CREATE TABLE event_stream (
    stream_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    tenant_id BIGINT NOT NULL REFERENCES tenant(tenant_id),

    stream_name VARCHAR(150) NOT NULL,

    description TEXT,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    retention_limit INTEGER NOT NULL DEFAULT 10000,

    next_event_id BIGINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, stream_name),

    UNIQUE (tenant_id, stream_id),

    CHECK (retention_limit BETWEEN 1 AND 1000000),

    CHECK (next_event_id > 0)
);

-- ============================================================
-- 4. SUBSCRIBERS
-- ============================================================

CREATE TABLE subscriber (
    subscriber_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    tenant_id BIGINT NOT NULL,

    user_id BIGINT NOT NULL,

    client_identifier VARCHAR(150) NOT NULL,

    status subscriber_status NOT NULL DEFAULT 'disconnected',

    connected_at TIMESTAMPTZ,

    disconnected_at TIMESTAMPTZ,

    last_seen_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (tenant_id, user_id)
        REFERENCES application_user(tenant_id, user_id),

    UNIQUE (tenant_id, client_identifier),

    UNIQUE (tenant_id, subscriber_id)
);

CREATE INDEX idx_subscriber_active
    ON subscriber(tenant_id, status)
    WHERE status = 'connected';

-- ============================================================
-- 5. EVENT SUBSCRIPTIONS
-- ============================================================

CREATE TABLE event_subscription (
    subscription_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    tenant_id BIGINT NOT NULL,

    stream_id BIGINT NOT NULL,

    subscriber_id BIGINT NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    event_filter event_type[],

    last_event_id BIGINT NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (tenant_id, stream_id)
        REFERENCES event_stream(tenant_id, stream_id),

    FOREIGN KEY (tenant_id, subscriber_id)
        REFERENCES subscriber(tenant_id, subscriber_id),

    UNIQUE (stream_id, subscriber_id),

    CHECK (last_event_id >= 0)
);

CREATE INDEX idx_subscription_enabled
    ON event_subscription(stream_id, subscriber_id)
    WHERE enabled = TRUE;

-- ============================================================
-- 6. DURABLE EVENTS
-- ============================================================

CREATE TABLE stream_event (
    event_pk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    stream_id BIGINT NOT NULL
        REFERENCES event_stream(stream_id),

    event_id BIGINT NOT NULL,

    event_type event_type NOT NULL,

    payload JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ,

    FOREIGN KEY (stream_id)
        REFERENCES event_stream(stream_id),

    UNIQUE (stream_id, event_id),

    CHECK (event_id > 0),

    CHECK (
        expires_at IS NULL OR
        expires_at > created_at
    ),

    CHECK (jsonb_typeof(payload) = 'object'),

    CHECK (octet_length(payload::TEXT) <= 64000)
);

CREATE INDEX idx_stream_event_replay
    ON stream_event(stream_id, event_id);

CREATE INDEX idx_stream_event_recent
    ON stream_event(stream_id, created_at DESC);

CREATE INDEX idx_stream_event_type
    ON stream_event(stream_id, event_type, event_id);

-- ============================================================
-- 7. DELIVERY RECORDS
-- ============================================================

CREATE TABLE event_delivery (
    delivery_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_pk BIGINT NOT NULL
        REFERENCES stream_event(event_pk),

    subscription_id BIGINT NOT NULL
        REFERENCES event_subscription(subscription_id),

    status delivery_status NOT NULL DEFAULT 'pending',

    attempt_count INTEGER NOT NULL DEFAULT 0,

    delivered_at TIMESTAMPTZ,

    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (event_pk, subscription_id),

    CHECK (attempt_count >= 0)
);

CREATE INDEX idx_delivery_pending
    ON event_delivery(status, created_at)
    WHERE status = 'pending';

CREATE INDEX idx_delivery_subscription
    ON event_delivery(subscription_id, delivery_id);

-- ============================================================
-- 8. TRANSACTIONAL OUTBOX
-- ============================================================

CREATE TABLE event_outbox (
    outbox_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    stream_id BIGINT NOT NULL
        REFERENCES event_stream(stream_id),

    event_type event_type NOT NULL,

    payload JSONB NOT NULL,

    status outbox_status NOT NULL DEFAULT 'pending',

    attempts INTEGER NOT NULL DEFAULT 0,

    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    published_at TIMESTAMPTZ,

    last_error TEXT,

    CHECK (attempts >= 0),

    CHECK (jsonb_typeof(payload) = 'object'),

    CHECK (octet_length(payload::TEXT) <= 64000)
);

CREATE INDEX idx_outbox_ready
    ON event_outbox(available_at, outbox_id)
    WHERE status = 'pending';

-- ============================================================
-- 9. EVENT ID ALLOCATION AND PUBLICATION
-- ============================================================

CREATE OR REPLACE FUNCTION publish_event(
    p_stream_id BIGINT,
    p_event_type event_type,
    p_payload JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id BIGINT;
    v_active BOOLEAN;
BEGIN
    IF p_payload IS NULL
       OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'Payload must be a JSON object';
    END IF;

    IF octet_length(p_payload::TEXT) > 64000 THEN
        RAISE EXCEPTION 'Payload exceeds 64 KB';
    END IF;

    /*
     * Updating the stream row serializes event ID allocation
     * for a given stream and prevents duplicate identifiers.
     */
    UPDATE event_stream
    SET next_event_id = next_event_id + 1
    WHERE stream_id = p_stream_id
      AND active = TRUE
    RETURNING next_event_id - 1
    INTO v_event_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Stream does not exist or is inactive';
    END IF;

    INSERT INTO stream_event (
        stream_id,
        event_id,
        event_type,
        payload
    )
    VALUES (
        p_stream_id,
        v_event_id,
        p_event_type,
        p_payload
    );

    /*
     * Notification is transactional. Consumers must query the
     * durable event table after receiving this wake-up signal.
     */
    PERFORM pg_notify(
        'sse_event_available',
        json_build_object(
            'stream_id', p_stream_id,
            'event_id', v_event_id
        )::TEXT
    );

    RETURN v_event_id;
END;
$$;

-- ============================================================
-- 10. SUBSCRIPTION AUTHORIZATION
-- ============================================================

CREATE OR REPLACE FUNCTION authorize_subscription(
    p_tenant_id BIGINT,
    p_stream_id BIGINT,
    p_user_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM event_stream es
        JOIN application_user au
          ON au.tenant_id = es.tenant_id
        JOIN tenant t
          ON t.tenant_id = es.tenant_id
        WHERE es.tenant_id = p_tenant_id
          AND es.stream_id = p_stream_id
          AND au.user_id = p_user_id
          AND es.active = TRUE
          AND au.active = TRUE
          AND t.active = TRUE
    );
END;
$$;

-- ============================================================
-- 11. SUBSCRIPTION REGISTRATION
-- ============================================================

CREATE OR REPLACE FUNCTION register_subscription(
    p_tenant_id BIGINT,
    p_stream_id BIGINT,
    p_subscriber_id BIGINT,
    p_filter event_type[] DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_subscription_id BIGINT;
    v_user_id BIGINT;
BEGIN
    SELECT user_id
    INTO v_user_id
    FROM subscriber
    WHERE subscriber_id = p_subscriber_id
      AND tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Subscriber not found';
    END IF;

    IF NOT authorize_subscription(
        p_tenant_id,
        p_stream_id,
        v_user_id
    ) THEN
        RAISE EXCEPTION 'Subscription authorization denied';
    END IF;

    INSERT INTO event_subscription (
        tenant_id,
        stream_id,
        subscriber_id,
        event_filter
    )
    VALUES (
        p_tenant_id,
        p_stream_id,
        p_subscriber_id,
        p_filter
    )
    ON CONFLICT (stream_id, subscriber_id)
    DO UPDATE SET
        enabled = TRUE,
        event_filter = EXCLUDED.event_filter
    RETURNING subscription_id
    INTO v_subscription_id;

    RETURN v_subscription_id;
END;
$$;

-- ============================================================
-- 12. EVENT RETRIEVAL AND RECONNECTION
-- ============================================================

CREATE OR REPLACE FUNCTION replay_events(
    p_stream_id BIGINT,
    p_last_event_id BIGINT DEFAULT 0,
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    event_id BIGINT,
    event_type event_type,
    payload JSONB,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_oldest BIGINT;
BEGIN
    IF p_last_event_id < 0 THEN
        RAISE EXCEPTION 'Invalid Last-Event-ID';
    END IF;

    IF p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'Replay limit must be between 1 and 1000';
    END IF;

    SELECT MIN(se.event_id)
    INTO v_oldest
    FROM stream_event se
    WHERE se.stream_id = p_stream_id;

    /*
     * A cursor older than retained history cannot guarantee
     * complete replay. The application must initiate a snapshot
     * or full resynchronization rather than silently assuming
     * that no events were missed.
     */
    IF v_oldest IS NOT NULL
       AND p_last_event_id < v_oldest - 1 THEN
        RAISE EXCEPTION
            'Replay cursor expired; full resynchronization required';
    END IF;

    RETURN QUERY
    SELECT
        se.event_id,
        se.event_type,
        se.payload,
        se.created_at
    FROM stream_event se
    WHERE se.stream_id = p_stream_id
      AND se.event_id > p_last_event_id
      AND (
          se.expires_at IS NULL OR
          se.expires_at > NOW()
      )
    ORDER BY se.event_id
    LIMIT p_limit;
END;
$$;

-- ============================================================
-- 13. DELIVERY ELIGIBILITY
-- ============================================================

CREATE OR REPLACE FUNCTION eligible_deliveries(
    p_stream_id BIGINT
)
RETURNS TABLE (
    subscription_id BIGINT,
    subscriber_id BIGINT,
    event_id BIGINT,
    event_type event_type,
    payload JSONB
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        esub.subscription_id,
        esub.subscriber_id,
        se.event_id,
        se.event_type,
        se.payload
    FROM event_subscription esub
    JOIN subscriber s
      ON s.subscriber_id = esub.subscriber_id
    JOIN stream_event se
      ON se.stream_id = esub.stream_id
    WHERE esub.stream_id = p_stream_id
      AND esub.enabled = TRUE
      AND s.status = 'connected'
      AND se.event_id > esub.last_event_id
      AND (
          esub.event_filter IS NULL OR
          se.event_type = ANY(esub.event_filter)
      )
    ORDER BY esub.subscription_id, se.event_id;
$$;

-- ============================================================
-- 14. DELIVERY CURSOR ADVANCEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION acknowledge_delivery(
    p_subscription_id BIGINT,
    p_event_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_stream_id BIGINT;
    v_event_pk BIGINT;
BEGIN
    SELECT stream_id
    INTO v_stream_id
    FROM event_subscription
    WHERE subscription_id = p_subscription_id
      AND enabled = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    SELECT event_pk
    INTO v_event_pk
    FROM stream_event
    WHERE stream_id = v_stream_id
      AND event_id = p_event_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    UPDATE event_subscription
    SET last_event_id = GREATEST(last_event_id, p_event_id)
    WHERE subscription_id = p_subscription_id;

    UPDATE event_delivery
    SET status = 'delivered',
        delivered_at = NOW()
    WHERE subscription_id = p_subscription_id
      AND event_pk = v_event_pk;

    RETURN TRUE;
END;
$$;

-- ============================================================
-- 15. EVENT RETENTION
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_event_retention(
    p_stream_id BIGINT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_limit INTEGER;
    v_deleted INTEGER;
BEGIN
    SELECT retention_limit
    INTO v_limit
    FROM event_stream
    WHERE stream_id = p_stream_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown stream';
    END IF;

    WITH ranked AS (
        SELECT
            event_pk,
            ROW_NUMBER() OVER (
                ORDER BY event_id DESC
            ) AS position
        FROM stream_event
        WHERE stream_id = p_stream_id
    ),
    removed AS (
        DELETE FROM stream_event se
        USING ranked r
        WHERE se.event_pk = r.event_pk
          AND r.position > v_limit
        RETURNING se.event_pk
    )
    SELECT COUNT(*)::INTEGER
    INTO v_deleted
    FROM removed;

    RETURN v_deleted;
END;
$$;

-- ============================================================
-- 16. OUTBOX PROCESSING
-- ============================================================

CREATE OR REPLACE PROCEDURE process_event_outbox(
    p_batch_size INTEGER DEFAULT 50
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_record RECORD;
BEGIN
    IF p_batch_size < 1 OR p_batch_size > 500 THEN
        RAISE EXCEPTION 'Invalid batch size';
    END IF;

    /*
     * SKIP LOCKED allows multiple workers to process separate
     * batches without claiming the same outbox row.
     *
     * The event insertion and outbox completion happen within
     * the same transaction.
     */
    FOR v_record IN
        SELECT
            outbox_id,
            stream_id,
            event_type,
            payload
        FROM event_outbox
        WHERE status = 'pending'
          AND available_at <= NOW()
        ORDER BY outbox_id
        LIMIT p_batch_size
        FOR UPDATE SKIP LOCKED
    LOOP
        BEGIN
            UPDATE event_outbox
            SET status = 'processing',
                attempts = attempts + 1
            WHERE outbox_id = v_record.outbox_id;

            PERFORM publish_event(
                v_record.stream_id,
                v_record.event_type,
                v_record.payload
            );

            UPDATE event_outbox
            SET status = 'published',
                published_at = NOW(),
                last_error = NULL
            WHERE outbox_id = v_record.outbox_id;

        EXCEPTION WHEN OTHERS THEN

            UPDATE event_outbox
            SET status = CASE
                    WHEN attempts >= 5 THEN 'failed'::outbox_status
                    ELSE 'pending'::outbox_status
                END,
                available_at = NOW() +
                    LEAST(
                        attempts * INTERVAL '10 seconds',
                        INTERVAL '5 minutes'
                    ),
                last_error = SQLERRM
            WHERE outbox_id = v_record.outbox_id;
        END;
    END LOOP;
END;
$$;

-- ============================================================
-- 17. REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW stream_operational_report AS
SELECT
    es.stream_id,
    es.stream_name,
    es.tenant_id,

    COUNT(DISTINCT se.event_pk) AS retained_events,

    COUNT(DISTINCT s.subscriber_id)
        FILTER (WHERE s.status = 'connected')
        AS connected_subscribers,

    COUNT(DISTINCT s.subscriber_id)
        FILTER (WHERE s.status = 'slow_consumer')
        AS slow_consumers,

    MAX(se.created_at) AS latest_event_at

FROM event_stream es

LEFT JOIN stream_event se
    ON se.stream_id = es.stream_id

LEFT JOIN event_subscription sub
    ON sub.stream_id = es.stream_id
   AND sub.enabled = TRUE

LEFT JOIN subscriber s
    ON s.subscriber_id = sub.subscriber_id

GROUP BY
    es.stream_id,
    es.stream_name,
    es.tenant_id;

-- ============================================================
-- 18. SAMPLE DATA
-- ============================================================

INSERT INTO tenant (tenant_name)
VALUES
    ('Enterprise-A'),
    ('Enterprise-B');

INSERT INTO application_user (
    tenant_id,
    username
)
VALUES
    (1, 'admin'),
    (1, 'developer'),
    (2, 'external-user');

INSERT INTO event_stream (
    tenant_id,
    stream_name,
    description,
    retention_limit
)
VALUES
    (
        1,
        'deployment-events',
        'Application deployment event stream',
        100
    ),
    (
        1,
        'job-progress',
        'Background job progress stream',
        50
    ),
    (
        2,
        'external-notifications',
        'External tenant notifications',
        100
    );

INSERT INTO subscriber (
    tenant_id,
    user_id,
    client_identifier,
    status,
    connected_at,
    last_seen_at
)
VALUES
    (
        1,
        1,
        'browser-admin-001',
        'connected',
        NOW(),
        NOW()
    ),
    (
        1,
        2,
        'browser-developer-001',
        'connected',
        NOW(),
        NOW()
    ),
    (
        1,
        2,
        'browser-slow-001',
        'slow_consumer',
        NOW(),
        NOW()
    ),
    (
        2,
        3,
        'browser-external-001',
        'connected',
        NOW(),
        NOW()
    );

INSERT INTO event_subscription (
    tenant_id,
    stream_id,
    subscriber_id,
    event_filter
)
VALUES
    (1, 1, 1, ARRAY['message', 'notification']::event_type[]),
    (1, 1, 2, ARRAY['update', 'progress']::event_type[]),
    (1, 2, 2, ARRAY['progress']::event_type[]),
    (1, 2, 3, NULL),
    (2, 3, 4, NULL);

-- ============================================================
-- 19. INITIAL EVENT PUBLICATION
-- ============================================================

SELECT publish_event(
    1,
    'message',
    '{"message":"Deployment initialized","environment":"staging"}'
);

SELECT publish_event(
    1,
    'update',
    '{"service":"api","status":"building"}'
);

SELECT publish_event(
    1,
    'notification',
    '{"message":"Deployment started"}'
);

SELECT publish_event(
    2,
    'progress',
    '{"job_id":"job-100","progress":25,"status":"processing"}'
);

SELECT publish_event(
    2,
    'progress',
    '{"job_id":"job-100","progress":100,"status":"completed"}'
);

SELECT publish_event(
    3,
    'notification',
    '{"message":"External tenant event"}'
);

-- ============================================================
-- 20. OUTBOX SAMPLE
-- ============================================================

INSERT INTO event_outbox (
    stream_id,
    event_type,
    payload
)
VALUES
(
    1,
    'notification',
    '{"message":"Queued deployment notification"}'
),
(
    2,
    'progress',
    '{"job_id":"job-200","progress":50,"status":"processing"}'
);

-- ============================================================
-- 21. DELIVERY ELIGIBILITY
-- ============================================================

SELECT *
FROM eligible_deliveries(1);

-- ============================================================
-- 22. RECONNECTION REPLAY
-- ============================================================

SELECT *
FROM replay_events(
    1,
    1,
    100
);

-- ============================================================
-- 23. OUTBOX WORKFLOW
-- ============================================================

CALL process_event_outbox(50);

-- ============================================================
-- 24. DELIVERY ACKNOWLEDGEMENT
-- ============================================================

SELECT acknowledge_delivery(
    1,
    1
);

-- ============================================================
-- 25. RETENTION VALIDATION
-- ============================================================

SELECT enforce_event_retention(1);

-- ============================================================
-- 26. OPERATIONAL REPORTING
-- ============================================================

SELECT *
FROM stream_operational_report
ORDER BY tenant_id, stream_id;

-- Event counts by event category.

SELECT
    stream_id,
    event_type,
    COUNT(*) AS total_events,
    MIN(created_at) AS first_event,
    MAX(created_at) AS latest_event
FROM stream_event
GROUP BY stream_id, event_type
ORDER BY stream_id, event_type;

-- Subscription status report.

SELECT
    es.stream_name,
    s.client_identifier,
    s.status,
    sub.enabled,
    sub.last_event_id
FROM event_subscription sub
JOIN event_stream es
    ON es.stream_id = sub.stream_id
JOIN subscriber s
    ON s.subscriber_id = sub.subscriber_id
ORDER BY es.stream_name, s.client_identifier;

-- Failed and pending outbox records.

SELECT
    outbox_id,
    stream_id,
    status,
    attempts,
    available_at,
    last_error
FROM event_outbox
WHERE status IN ('pending', 'failed')
ORDER BY created_at;

-- ============================================================
-- 27. TRANSACTIONAL PUBLICATION EXAMPLE
-- ============================================================

SAVEPOINT before_test_publication;

SELECT publish_event(
    1,
    'notification',
    '{"message":"Transactional publication test"}'
);

-- The publication can be retained or rolled back.
-- Rolling back also rolls back its transactional notification.

ROLLBACK TO SAVEPOINT before_test_publication;

RELEASE SAVEPOINT before_test_publication;

-- ============================================================
-- 28. SECURITY AND INTEGRITY CHECKS
-- ============================================================

SELECT
    authorize_subscription(1, 1, 1)
        AS tenant_a_access,

    authorize_subscription(2, 3, 3)
        AS tenant_b_access,

    authorize_subscription(2, 1, 3)
        AS cross_tenant_access;

-- Invalid publication is rejected by the function.

DO $$
BEGIN
    BEGIN
        PERFORM publish_event(
            1,
            'message',
            '[]'::JSONB
        );

        RAISE EXCEPTION
            'Invalid payload was unexpectedly accepted';

    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'Invalid payload was unexpectedly accepted' THEN
            RAISE;
        END IF;

        RAISE NOTICE 'Invalid payload correctly rejected';
    END;
END;
$$;

COMMIT;

-- ============================================================
-- OPERATIONAL NOTES
-- ============================================================
--
-- 1. LISTEN/NOTIFY is a wake-up mechanism. It is not a durable
--    event queue and must not replace stream_event.
--
-- 2. A client should use the SSE Last-Event-ID header when
--    reconnecting. The server should query replay_events().
--
-- 3. Database acknowledgement means that the application has
--    processed a delivery according to its acknowledgement
--    policy. It does not prove that browser application code
--    completed its business operation.
--
-- 4. Exactly-once network delivery is not guaranteed.
--    Clients should tolerate duplicate events and use event IDs
--    for deduplication.
--
-- 5. The outbox pattern prevents loss between business database
--    commits and event publication, provided processing and
--    publication share the same transaction.
--
-- 6. Production retention should account for the oldest active
--    subscriber cursor and the required recovery window.
--
-- 7. Tenant authorization must also be enforced by the HTTP
--    application. Database functions alone do not secure
--    unrestricted database access.
--
-- 8. Production deployments should restrict schema permissions,
--    use TLS, authenticate subscribers, and apply connection
--    limits at the application and infrastructure layers.
