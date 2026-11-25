/*
    WebSocket Real-Time Communication Platform
    PostgreSQL 15+

    Domain:
    - Tenants and application users
    - Persistent WebSocket connections
    - Connection lifecycle
    - Authentication
    - Sessions and reconnection
    - Message delivery
    - Heartbeat monitoring
    - Outbound message queues
    - Connection events
    - Failure tracking
    - Operational metrics

    All timestamps use TIMESTAMPTZ.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS realtime;

SET search_path TO realtime, public;


-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE connection_state AS ENUM (
    'connecting',
    'open',
    'reconnecting',
    'closing',
    'closed',
    'failed'
);

CREATE TYPE message_type AS ENUM (
    'text',
    'binary',
    'ping',
    'pong',
    'close'
);

CREATE TYPE message_status AS ENUM (
    'queued',
    'sending',
    'sent',
    'acknowledged',
    'failed',
    'expired'
);

CREATE TYPE connection_event_type AS ENUM (
    'created',
    'handshake_started',
    'handshake_completed',
    'authenticated',
    'message_received',
    'message_sent',
    'heartbeat_sent',
    'heartbeat_received',
    'reconnecting',
    'connection_closed',
    'connection_failed',
    'session_replaced'
);


-- ============================================================
-- 2. TENANTS AND USERS
-- ============================================================

CREATE TABLE tenants (
    tenant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_name VARCHAR(150) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE application_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id BIGINT NOT NULL
        REFERENCES tenants(tenant_id),
    username VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, username),
    UNIQUE (tenant_id, email),
    UNIQUE (tenant_id, user_id)
);


-- ============================================================
-- 3. CONNECTION POLICIES
-- ============================================================

CREATE TABLE connection_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id BIGINT NOT NULL
        REFERENCES tenants(tenant_id),

    policy_name VARCHAR(100) NOT NULL,

    maximum_message_bytes INTEGER NOT NULL DEFAULT 1048576
        CHECK (maximum_message_bytes BETWEEN 1 AND 16777216),

    maximum_queued_messages INTEGER NOT NULL DEFAULT 100
        CHECK (maximum_queued_messages BETWEEN 1 AND 100000),

    maximum_queued_bytes BIGINT NOT NULL DEFAULT 4194304
        CHECK (maximum_queued_bytes BETWEEN 1 AND 1073741824),

    heartbeat_interval_seconds INTEGER NOT NULL DEFAULT 20
        CHECK (heartbeat_interval_seconds BETWEEN 5 AND 3600),

    idle_timeout_seconds INTEGER NOT NULL DEFAULT 60
        CHECK (idle_timeout_seconds BETWEEN 10 AND 86400),

    maximum_reconnect_attempts INTEGER NOT NULL DEFAULT 5
        CHECK (maximum_reconnect_attempts BETWEEN 0 AND 100),

    maximum_connections_per_user INTEGER NOT NULL DEFAULT 3
        CHECK (maximum_connections_per_user BETWEEN 1 AND 100),

    require_authenticated_user BOOLEAN NOT NULL DEFAULT TRUE,

    allow_binary_messages BOOLEAN NOT NULL DEFAULT FALSE,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, policy_name),
    UNIQUE (tenant_id, policy_id)
);


-- ============================================================
-- 4. WEBSOCKET CONNECTIONS
-- ============================================================

CREATE TABLE websocket_connections (

    connection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,

    policy_id BIGINT NOT NULL,

    session_id UUID NOT NULL DEFAULT gen_random_uuid(),

    parent_connection_id UUID
        REFERENCES websocket_connections(connection_id),

    client_ip INET,

    user_agent TEXT,

    protocol_version VARCHAR(10) NOT NULL DEFAULT '13'
        CHECK (protocol_version = '13'),

    state connection_state NOT NULL DEFAULT 'connecting',

    authenticated BOOLEAN NOT NULL DEFAULT FALSE,

    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_heartbeat_at TIMESTAMPTZ,

    closed_at TIMESTAMPTZ,

    close_code INTEGER,

    close_reason TEXT,

    reconnect_attempt INTEGER NOT NULL DEFAULT 0
        CHECK (reconnect_attempt >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (tenant_id, user_id)
        REFERENCES application_users(tenant_id, user_id),

    FOREIGN KEY (tenant_id, policy_id)
        REFERENCES connection_policies(tenant_id, policy_id),

    CHECK (
        close_code IS NULL OR
        close_code BETWEEN 1000 AND 4999
    ),

    CHECK (
        state <> 'closed' OR closed_at IS NOT NULL
    )
);


CREATE INDEX idx_connections_tenant_state
ON websocket_connections(tenant_id, state);


CREATE INDEX idx_connections_user_activity
ON websocket_connections(user_id, last_activity_at DESC);


CREATE INDEX idx_connections_active
ON websocket_connections(tenant_id, connected_at DESC)
WHERE state = 'open';


CREATE INDEX idx_connections_session
ON websocket_connections(session_id);


CREATE INDEX idx_connections_parent
ON websocket_connections(parent_connection_id)
WHERE parent_connection_id IS NOT NULL;


-- ============================================================
-- 5. CONNECTION STATE HISTORY
-- ============================================================

CREATE TABLE connection_state_history (

    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    connection_id UUID NOT NULL
        REFERENCES websocket_connections(connection_id),

    previous_state connection_state,

    new_state connection_state NOT NULL,

    transition_reason TEXT,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX idx_state_history_connection
ON connection_state_history(connection_id, changed_at DESC);


-- ============================================================
-- 6. CONNECTION EVENTS
-- ============================================================

CREATE TABLE connection_events (

    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    connection_id UUID NOT NULL
        REFERENCES websocket_connections(connection_id),

    event_type connection_event_type NOT NULL,

    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX idx_connection_events_timeline
ON connection_events(connection_id, created_at DESC);


CREATE INDEX idx_connection_events_type
ON connection_events(event_type, created_at DESC);


-- ============================================================
-- 7. REAL-TIME MESSAGES
-- ============================================================

CREATE TABLE websocket_messages (

    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id BIGINT NOT NULL
        REFERENCES tenants(tenant_id),

    connection_id UUID NOT NULL
        REFERENCES websocket_connections(connection_id),

    message_type message_type NOT NULL,

    direction VARCHAR(10) NOT NULL
        CHECK (direction IN ('inbound', 'outbound')),

    sequence_number BIGINT NOT NULL
        CHECK (sequence_number > 0),

    payload BYTEA NOT NULL,

    payload_bytes INTEGER GENERATED ALWAYS AS
        (OCTET_LENGTH(payload)) STORED,

    status message_status NOT NULL DEFAULT 'queued',

    correlation_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    sent_at TIMESTAMPTZ,

    acknowledged_at TIMESTAMPTZ,

    error_message TEXT,

    UNIQUE (connection_id, sequence_number),

    CHECK (
        (status NOT IN ('sent', 'acknowledged'))
        OR sent_at IS NOT NULL
    ),

    CHECK (
        status <> 'acknowledged'
        OR acknowledged_at IS NOT NULL
    )
);


CREATE INDEX idx_messages_outbound_queue
ON websocket_messages(connection_id, sequence_number)
WHERE direction = 'outbound'
AND status = 'queued';


CREATE INDEX idx_messages_status
ON websocket_messages(status, created_at);


CREATE INDEX idx_messages_correlation
ON websocket_messages(correlation_id)
WHERE correlation_id IS NOT NULL;


-- ============================================================
-- 8. HEARTBEAT RECORDS
-- ============================================================

CREATE TABLE connection_heartbeats (

    heartbeat_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    connection_id UUID NOT NULL
        REFERENCES websocket_connections(connection_id),

    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    received_at TIMESTAMPTZ,

    payload VARCHAR(125),

    CHECK (
        received_at IS NULL OR
        received_at >= sent_at
    )
);


CREATE INDEX idx_heartbeat_pending
ON connection_heartbeats(connection_id, sent_at DESC)
WHERE received_at IS NULL;


-- ============================================================
-- 9. CONNECTION METRICS
-- ============================================================

CREATE TABLE connection_metrics (

    metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    connection_id UUID NOT NULL
        REFERENCES websocket_connections(connection_id),

    messages_received BIGINT NOT NULL DEFAULT 0
        CHECK (messages_received >= 0),

    messages_sent BIGINT NOT NULL DEFAULT 0
        CHECK (messages_sent >= 0),

    bytes_received BIGINT NOT NULL DEFAULT 0
        CHECK (bytes_received >= 0),

    bytes_sent BIGINT NOT NULL DEFAULT 0
        CHECK (bytes_sent >= 0),

    heartbeat_failures INTEGER NOT NULL DEFAULT 0
        CHECK (heartbeat_failures >= 0),

    reconnect_count INTEGER NOT NULL DEFAULT 0
        CHECK (reconnect_count >= 0),

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX idx_metrics_connection_time
ON connection_metrics(connection_id, recorded_at DESC);


-- ============================================================
-- 10. CONNECTION STATE TRANSITION VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_connection_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    valid_transition BOOLEAN := FALSE;
BEGIN

    IF TG_OP = 'INSERT' THEN

        IF NEW.state <> 'connecting' THEN
            RAISE EXCEPTION
                'New connections must begin in connecting state';
        END IF;

        RETURN NEW;
    END IF;

    IF NEW.state = OLD.state THEN
        RETURN NEW;
    END IF;

    valid_transition := CASE OLD.state

        WHEN 'connecting' THEN
            NEW.state IN ('open', 'failed', 'closed')

        WHEN 'open' THEN
            NEW.state IN ('reconnecting', 'closing', 'failed')

        WHEN 'reconnecting' THEN
            NEW.state IN ('connecting', 'closing', 'failed')

        WHEN 'closing' THEN
            NEW.state IN ('closed', 'failed')

        WHEN 'failed' THEN
            NEW.state = 'closed'

        WHEN 'closed' THEN
            FALSE

        ELSE FALSE

    END;

    IF NOT valid_transition THEN
        RAISE EXCEPTION
            'Invalid connection transition: % -> %',
            OLD.state,
            NEW.state;
    END IF;

    IF NEW.state = 'open' AND NOT NEW.authenticated THEN
        RAISE EXCEPTION
            'Unauthenticated connections cannot enter open state';
    END IF;

    IF NEW.state = 'closed' AND NEW.closed_at IS NULL THEN
        NEW.closed_at := NOW();
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_validate_connection_transition
BEFORE INSERT OR UPDATE OF state, authenticated
ON websocket_connections
FOR EACH ROW
EXECUTE FUNCTION validate_connection_transition();


-- ============================================================
-- 11. CONNECTION HISTORY AUTOMATION
-- ============================================================

CREATE OR REPLACE FUNCTION record_connection_state_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    IF TG_OP = 'INSERT' THEN

        INSERT INTO connection_state_history (
            connection_id,
            previous_state,
            new_state,
            transition_reason
        )
        VALUES (
            NEW.connection_id,
            NULL,
            NEW.state,
            'Connection created'
        );

    ELSIF OLD.state IS DISTINCT FROM NEW.state THEN

        INSERT INTO connection_state_history (
            connection_id,
            previous_state,
            new_state,
            transition_reason
        )
        VALUES (
            NEW.connection_id,
            OLD.state,
            NEW.state,
            COALESCE(NEW.close_reason, 'Lifecycle transition')
        );

    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_connection_history
AFTER INSERT OR UPDATE OF state
ON websocket_connections
FOR EACH ROW
EXECUTE FUNCTION record_connection_state_change();


-- ============================================================
-- 12. AUTHENTICATION AND CONNECTION VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION authenticate_connection(
    p_connection_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_connection websocket_connections%ROWTYPE;
    v_policy connection_policies%ROWTYPE;
    v_active_count INTEGER;
BEGIN

    SELECT *
    INTO v_connection
    FROM websocket_connections
    WHERE connection_id = p_connection_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Connection not found';
    END IF;

    IF v_connection.state <> 'connecting' THEN
        RAISE EXCEPTION
            'Authentication requires connecting state';
    END IF;

    SELECT *
    INTO v_policy
    FROM connection_policies
    WHERE policy_id = v_connection.policy_id
      AND tenant_id = v_connection.tenant_id
      AND active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Connection policy is unavailable';
    END IF;

    IF v_policy.require_authenticated_user THEN

        PERFORM 1
        FROM application_users
        WHERE user_id = v_connection.user_id
          AND tenant_id = v_connection.tenant_id
          AND active = TRUE;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'User authentication or authorization failed';
        END IF;

    END IF;

    SELECT COUNT(*)
    INTO v_active_count
    FROM websocket_connections
    WHERE user_id = v_connection.user_id
      AND tenant_id = v_connection.tenant_id
      AND state = 'open'
      AND connection_id <> p_connection_id;

    IF v_active_count >= v_policy.maximum_connections_per_user THEN
        RAISE EXCEPTION
            'Maximum concurrent connections exceeded';
    END IF;

    UPDATE websocket_connections
    SET authenticated = TRUE,
        state = 'open',
        last_activity_at = NOW()
    WHERE connection_id = p_connection_id;

    INSERT INTO connection_events (
        connection_id,
        event_type,
        event_payload
    )
    VALUES (
        p_connection_id,
        'authenticated',
        jsonb_build_object(
            'authenticated', TRUE,
            'timestamp', NOW()
        )
    );

END;
$$;


-- ============================================================
-- 13. MESSAGE VALIDATION AND ENQUEUEING
-- ============================================================

CREATE OR REPLACE FUNCTION enqueue_message(
    p_connection_id UUID,
    p_message_type message_type,
    p_payload BYTEA
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_connection websocket_connections%ROWTYPE;
    v_policy connection_policies%ROWTYPE;

    v_sequence BIGINT;
    v_message_id UUID;

    v_message_size INTEGER;
    v_queue_count INTEGER;
    v_queue_bytes BIGINT;
BEGIN

    v_message_size := OCTET_LENGTH(p_payload);

    SELECT *
    INTO v_connection
    FROM websocket_connections
    WHERE connection_id = p_connection_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown connection';
    END IF;

    IF v_connection.state <> 'open' THEN
        RAISE EXCEPTION 'Connection is not open';
    END IF;

    IF NOT v_connection.authenticated THEN
        RAISE EXCEPTION 'Connection is not authenticated';
    END IF;

    SELECT *
    INTO v_policy
    FROM connection_policies
    WHERE policy_id = v_connection.policy_id;

    IF v_message_size > v_policy.maximum_message_bytes THEN
        RAISE EXCEPTION 'Message size limit exceeded';
    END IF;

    IF p_message_type IN ('ping', 'pong', 'close') THEN
        RAISE EXCEPTION
            'Control frames must use dedicated transport handlers';
    END IF;

    IF p_message_type = 'binary'
       AND NOT v_policy.allow_binary_messages THEN
        RAISE EXCEPTION 'Binary messages are disabled';
    END IF;

    SELECT
        COUNT(*),
        COALESCE(SUM(payload_bytes), 0)
    INTO
        v_queue_count,
        v_queue_bytes
    FROM websocket_messages
    WHERE connection_id = p_connection_id
      AND direction = 'outbound'
      AND status = 'queued';

    IF v_queue_count >= v_policy.maximum_queued_messages THEN
        RAISE EXCEPTION 'Outbound message queue is full';
    END IF;

    IF v_message_size >
       v_policy.maximum_queued_bytes - v_queue_bytes THEN
        RAISE EXCEPTION 'Outbound byte capacity exceeded';
    END IF;

    SELECT COALESCE(MAX(sequence_number), 0) + 1
    INTO v_sequence
    FROM websocket_messages
    WHERE connection_id = p_connection_id;

    INSERT INTO websocket_messages (
        tenant_id,
        connection_id,
        message_type,
        direction,
        sequence_number,
        payload
    )
    VALUES (
        v_connection.tenant_id,
        p_connection_id,
        p_message_type,
        'outbound',
        v_sequence,
        p_payload
    )
    RETURNING message_id
    INTO v_message_id;

    UPDATE websocket_connections
    SET last_activity_at = NOW()
    WHERE connection_id = p_connection_id;

    RETURN v_message_id;

END;
$$;


-- ============================================================
-- 14. MESSAGE DELIVERY
-- ============================================================

CREATE OR REPLACE PROCEDURE mark_message_sent(
    p_message_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_connection_id UUID;
BEGIN

    UPDATE websocket_messages
    SET status = 'sent',
        sent_at = NOW()
    WHERE message_id = p_message_id
      AND status = 'queued'
      AND direction = 'outbound'
    RETURNING connection_id
    INTO v_connection_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Message does not exist or cannot be sent';
    END IF;

    INSERT INTO connection_events (
        connection_id,
        event_type,
        event_payload
    )
    VALUES (
        v_connection_id,
        'message_sent',
        jsonb_build_object(
            'message_id', p_message_id
        )
    );

END;
$$;


CREATE OR REPLACE PROCEDURE acknowledge_message(
    p_message_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN

    UPDATE websocket_messages
    SET status = 'acknowledged',
        acknowledged_at = NOW()
    WHERE message_id = p_message_id
      AND status = 'sent';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Only sent messages can be acknowledged';
    END IF;

END;
$$;


-- ============================================================
-- 15. HEARTBEAT OPERATIONS
-- ============================================================

CREATE OR REPLACE FUNCTION record_heartbeat(
    p_connection_id UUID,
    p_payload VARCHAR(125) DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN

    PERFORM 1
    FROM websocket_connections
    WHERE connection_id = p_connection_id
      AND state = 'open'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Heartbeat requires an open connection';
    END IF;

    INSERT INTO connection_heartbeats (
        connection_id,
        payload
    )
    VALUES (
        p_connection_id,
        p_payload
    )
    RETURNING heartbeat_id
    INTO v_id;

    INSERT INTO connection_events (
        connection_id,
        event_type,
        event_payload
    )
    VALUES (
        p_connection_id,
        'heartbeat_sent',
        jsonb_build_object(
            'heartbeat_id', v_id
        )
    );

    RETURN v_id;

END;
$$;


CREATE OR REPLACE FUNCTION acknowledge_heartbeat(
    p_heartbeat_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_connection_id UUID;
BEGIN

    UPDATE connection_heartbeats
    SET received_at = NOW()
    WHERE heartbeat_id = p_heartbeat_id
      AND received_at IS NULL
    RETURNING connection_id
    INTO v_connection_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Heartbeat not found or already acknowledged';
    END IF;

    UPDATE websocket_connections
    SET last_activity_at = NOW(),
        last_heartbeat_at = NOW()
    WHERE connection_id = v_connection_id;

    INSERT INTO connection_events (
        connection_id,
        event_type,
        event_payload
    )
    VALUES (
        v_connection_id,
        'heartbeat_received',
        jsonb_build_object(
            'heartbeat_id', p_heartbeat_id
        )
    );

END;
$$;


-- ============================================================
-- 16. CONNECTION CLOSURE
-- ============================================================

CREATE OR REPLACE PROCEDURE close_connection(
    p_connection_id UUID,
    p_close_code INTEGER DEFAULT 1000,
    p_reason TEXT DEFAULT 'Normal closure'
)
LANGUAGE plpgsql
AS $$
BEGIN

    IF p_close_code NOT BETWEEN 1000 AND 4999 THEN
        RAISE EXCEPTION 'Invalid WebSocket close code';
    END IF;

    UPDATE websocket_connections
    SET state = 'closing',
        close_code = p_close_code,
        close_reason = p_reason
    WHERE connection_id = p_connection_id
      AND state IN ('open', 'reconnecting');

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Connection cannot enter closing state';
    END IF;

    UPDATE websocket_connections
    SET state = 'closed',
        closed_at = NOW()
    WHERE connection_id = p_connection_id
      AND state = 'closing';

    INSERT INTO connection_events (
        connection_id,
        event_type,
        event_payload
    )
    VALUES (
        p_connection_id,
        'connection_closed',
        jsonb_build_object(
            'close_code', p_close_code,
            'reason', p_reason
        )
    );

END;
$$;


-- ============================================================
-- 17. RECONNECTION
-- ============================================================

CREATE OR REPLACE FUNCTION begin_reconnection(
    p_old_connection UUID,
    p_new_connection UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_old websocket_connections%ROWTYPE;
    v_new websocket_connections%ROWTYPE;
    v_policy connection_policies%ROWTYPE;
BEGIN

    SELECT *
    INTO v_old
    FROM websocket_connections
    WHERE connection_id = p_old_connection
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Previous connection not found';
    END IF;

    SELECT *
    INTO v_new
    FROM websocket_connections
    WHERE connection_id = p_new_connection
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Replacement connection not found';
    END IF;

    IF v_old.user_id <> v_new.user_id
       OR v_old.tenant_id <> v_new.tenant_id THEN
        RAISE EXCEPTION
            'Reconnection identity mismatch';
    END IF;

    IF v_new.state <> 'connecting' THEN
        RAISE EXCEPTION
            'Replacement connection must be connecting';
    END IF;

    SELECT *
    INTO v_policy
    FROM connection_policies
    WHERE policy_id = v_old.policy_id;

    IF v_old.reconnect_attempt >=
       v_policy.maximum_reconnect_attempts THEN
        RAISE EXCEPTION
            'Maximum reconnection attempts exceeded';
    END IF;

    UPDATE websocket_connections
    SET state = 'reconnecting'
    WHERE connection_id = p_old_connection;

    UPDATE websocket_connections
    SET parent_connection_id = p_old_connection,
        reconnect_attempt = v_old.reconnect_attempt + 1
    WHERE connection_id = p_new_connection;

    INSERT INTO connection_events (
        connection_id,
        event_type,
        event_payload
    )
    VALUES (
        p_old_connection,
        'reconnecting',
        jsonb_build_object(
            'replacement_connection', p_new_connection
        )
    );

END;
$$;


-- ============================================================
-- 18. ACTIVE CONNECTION VIEW
-- ============================================================

CREATE OR REPLACE VIEW active_connections AS
SELECT
    c.connection_id,
    t.tenant_name,
    u.username,
    c.session_id,
    c.state,
    c.authenticated,
    c.connected_at,
    c.last_activity_at,
    p.policy_name,
    p.heartbeat_interval_seconds,
    p.idle_timeout_seconds
FROM websocket_connections c
JOIN tenants t
    ON t.tenant_id = c.tenant_id
JOIN application_users u
    ON u.user_id = c.user_id
   AND u.tenant_id = c.tenant_id
JOIN connection_policies p
    ON p.policy_id = c.policy_id
WHERE c.state = 'open';


-- ============================================================
-- 19. CONNECTION PERFORMANCE REPORT
-- ============================================================

CREATE OR REPLACE VIEW connection_performance AS
SELECT
    c.connection_id,
    c.tenant_id,
    c.user_id,
    c.state,
    COUNT(m.message_id) AS total_messages,
    COALESCE(SUM(m.payload_bytes), 0) AS total_payload_bytes,

    COUNT(m.message_id) FILTER (
        WHERE m.status = 'failed'
    ) AS failed_messages,

    COUNT(m.message_id) FILTER (
        WHERE m.status = 'acknowledged'
    ) AS acknowledged_messages,

    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (
                    m.acknowledged_at - m.sent_at
                )
            )
        ) FILTER (
            WHERE m.acknowledged_at IS NOT NULL
        ),
        3
    ) AS average_acknowledgement_seconds

FROM websocket_connections c
LEFT JOIN websocket_messages m
    ON m.connection_id = c.connection_id
GROUP BY
    c.connection_id,
    c.tenant_id,
    c.user_id,
    c.state;


-- ============================================================
-- 20. HEARTBEAT HEALTH REPORT
-- ============================================================

CREATE OR REPLACE VIEW heartbeat_health AS
SELECT
    c.connection_id,
    c.user_id,
    COUNT(h.heartbeat_id) AS total_heartbeats,

    COUNT(h.heartbeat_id) FILTER (
        WHERE h.received_at IS NOT NULL
    ) AS acknowledged_heartbeats,

    COUNT(h.heartbeat_id) FILTER (
        WHERE h.received_at IS NULL
    ) AS pending_heartbeats,

    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (
                    h.received_at - h.sent_at
                )
            )
        ) FILTER (
            WHERE h.received_at IS NOT NULL
        ),
        3
    ) AS average_round_trip_seconds

FROM websocket_connections c
LEFT JOIN connection_heartbeats h
    ON h.connection_id = c.connection_id
GROUP BY
    c.connection_id,
    c.user_id;


-- ============================================================
-- 21. SAMPLE DATA
-- ============================================================

INSERT INTO tenants (tenant_name)
VALUES
    ('Finance Platform'),
    ('Operations Platform');


INSERT INTO application_users (
    tenant_id,
    username,
    email
)
SELECT
    tenant_id,
    username,
    email
FROM tenants
CROSS JOIN (
    VALUES
        ('alice', 'alice@example.com'),
        ('bob', 'bob@example.com'),
        ('charlie', 'charlie@example.com')
) AS users(username, email)
WHERE tenant_name = 'Finance Platform';


INSERT INTO connection_policies (
    tenant_id,
    policy_name,
    maximum_message_bytes,
    maximum_queued_messages,
    maximum_queued_bytes,
    heartbeat_interval_seconds,
    idle_timeout_seconds,
    maximum_reconnect_attempts,
    maximum_connections_per_user,
    allow_binary_messages
)
SELECT
    tenant_id,
    'standard-policy',
    1048576,
    100,
    4194304,
    20,
    60,
    5,
    3,
    FALSE
FROM tenants
WHERE tenant_name = 'Finance Platform';


INSERT INTO websocket_connections (
    connection_id,
    tenant_id,
    user_id,
    policy_id,
    client_ip,
    user_agent,
    state,
    authenticated,
    connected_at,
    last_activity_at
)
SELECT
    '10000000-0000-0000-0000-000000000001'::UUID,
    t.tenant_id,
    u.user_id,
    p.policy_id,
    '192.168.1.10'::INET,
    'Chrome WebSocket Client',
    'open',
    TRUE,
    NOW() - INTERVAL '30 minutes',
    NOW() - INTERVAL '5 seconds'
FROM tenants t
JOIN application_users u
    ON u.tenant_id = t.tenant_id
JOIN connection_policies p
    ON p.tenant_id = t.tenant_id
WHERE t.tenant_name = 'Finance Platform'
  AND u.username = 'alice'
  AND p.policy_name = 'standard-policy';


INSERT INTO websocket_connections (
    connection_id,
    tenant_id,
    user_id,
    policy_id,
    client_ip,
    user_agent,
    state,
    authenticated
)
SELECT
    '10000000-0000-0000-0000-000000000002'::UUID,
    t.tenant_id,
    u.user_id,
    p.policy_id,
    '192.168.1.11'::INET,
    'Mobile WebSocket Client',
    'connecting',
    FALSE
FROM tenants t
JOIN application_users u
    ON u.tenant_id = t.tenant_id
JOIN connection_policies p
    ON p.tenant_id = t.tenant_id
WHERE t.tenant_name = 'Finance Platform'
  AND u.username = 'bob'
  AND p.policy_name = 'standard-policy';


INSERT INTO websocket_connections (
    connection_id,
    tenant_id,
    user_id,
    policy_id,
    client_ip,
    state,
    authenticated,
    closed_at,
    close_code,
    close_reason
)
SELECT
    '10000000-0000-0000-0000-000000000003'::UUID,
    t.tenant_id,
    u.user_id,
    p.policy_id,
    '192.168.1.12'::INET,
    'closed',
    TRUE,
    NOW(),
    1001,
    'Client going away'
FROM tenants t
JOIN application_users u
    ON u.tenant_id = t.tenant_id
JOIN connection_policies p
    ON p.tenant_id = t.tenant_id
WHERE t.tenant_name = 'Finance Platform'
  AND u.username = 'charlie'
  AND p.policy_name = 'standard-policy';


-- ============================================================
-- 22. SAMPLE MESSAGE OPERATIONS
-- ============================================================

SELECT enqueue_message(
    '10000000-0000-0000-0000-000000000001',
    'text',
    convert_to(
        '{"type":"notification","data":"Payment completed"}',
        'UTF8'
    )
) AS first_message_id;


SELECT enqueue_message(
    '10000000-0000-0000-0000-000000000001',
    'text',
    convert_to(
        '{"type":"notification","data":"Settlement completed"}',
        'UTF8'
    )
) AS second_message_id;


-- ============================================================
-- 23. SAMPLE HEARTBEAT
-- ============================================================

SELECT record_heartbeat(
    '10000000-0000-0000-0000-000000000001',
    'heartbeat-001'
) AS heartbeat_id;


-- ============================================================
-- 24. TRANSACTIONAL DELIVERY EXAMPLE
-- ============================================================

DO $$
DECLARE
    v_message UUID;
BEGIN

    SELECT message_id
    INTO v_message
    FROM websocket_messages
    WHERE connection_id =
        '10000000-0000-0000-0000-000000000001'
      AND status = 'queued'
    ORDER BY sequence_number
    LIMIT 1;

    IF v_message IS NOT NULL THEN
        CALL mark_message_sent(v_message);
        CALL acknowledge_message(v_message);
    END IF;

END;
$$;


-- ============================================================
-- 25. RETRIEVAL QUERIES
-- ============================================================

-- All currently active WebSocket sessions.
SELECT *
FROM active_connections
ORDER BY connected_at DESC;


-- Messages belonging to a connection.
SELECT
    message_id,
    sequence_number,
    message_type,
    direction,
    payload_bytes,
    status,
    created_at,
    sent_at,
    acknowledged_at
FROM websocket_messages
WHERE connection_id =
    '10000000-0000-0000-0000-000000000001'
ORDER BY sequence_number;


-- Complete lifecycle history.
SELECT
    previous_state,
    new_state,
    transition_reason,
    changed_at
FROM connection_state_history
WHERE connection_id =
    '10000000-0000-0000-0000-000000000001'
ORDER BY changed_at;


-- ============================================================
-- 26. VALIDATION QUERIES
-- ============================================================

-- Connections that are open but unauthenticated.
SELECT connection_id, user_id, state
FROM websocket_connections
WHERE state = 'open'
  AND authenticated = FALSE;


-- Messages that violate their policy size limit.
SELECT
    m.message_id,
    m.payload_bytes,
    p.maximum_message_bytes
FROM websocket_messages m
JOIN websocket_connections c
    ON c.connection_id = m.connection_id
JOIN connection_policies p
    ON p.policy_id = c.policy_id
WHERE m.payload_bytes > p.maximum_message_bytes;


-- Potential idle connections.
SELECT
    c.connection_id,
    c.user_id,
    c.last_activity_at,
    p.idle_timeout_seconds,
    NOW() - c.last_activity_at AS idle_duration
FROM websocket_connections c
JOIN connection_policies p
    ON p.policy_id = c.policy_id
WHERE c.state = 'open'
  AND c.last_activity_at <
      NOW() - make_interval(
          secs => p.idle_timeout_seconds
      );


-- ============================================================
-- 27. AGGREGATION AND REPORTING
-- ============================================================

-- Connection distribution by state.
SELECT
    tenant_id,
    state,
    COUNT(*) AS connection_count
FROM websocket_connections
GROUP BY tenant_id, state
ORDER BY tenant_id, state;


-- Message throughput by connection.
SELECT *
FROM connection_performance
ORDER BY total_messages DESC;


-- Heartbeat performance.
SELECT *
FROM heartbeat_health
ORDER BY pending_heartbeats DESC;


-- Daily message volume.
SELECT
    DATE_TRUNC('day', created_at) AS activity_day,
    direction,
    COUNT(*) AS message_count,
    SUM(payload_bytes) AS total_bytes
FROM websocket_messages
GROUP BY
    DATE_TRUNC('day', created_at),
    direction
ORDER BY activity_day DESC;


-- ============================================================
-- 28. ELIGIBILITY AND OPERATIONAL EVALUATION
-- ============================================================

-- Determine whether each connection satisfies operational rules.
WITH connection_evaluation AS (

    SELECT
        c.connection_id,
        c.user_id,
        c.state,
        c.authenticated,

        p.active AS policy_active,

        p.require_authenticated_user,

        CASE
            WHEN c.state <> 'open'
                THEN FALSE

            WHEN p.active = FALSE
                THEN FALSE

            WHEN p.require_authenticated_user
                 AND c.authenticated = FALSE
                THEN FALSE

            ELSE TRUE
        END AS operationally_eligible,

        CASE
            WHEN c.state <> 'open'
                THEN 'CONNECTION_NOT_OPEN'

            WHEN p.active = FALSE
                THEN 'POLICY_DISABLED'

            WHEN p.require_authenticated_user
                 AND c.authenticated = FALSE
                THEN 'AUTHENTICATION_REQUIRED'

            ELSE 'ELIGIBLE'
        END AS evaluation_reason

    FROM websocket_connections c
    JOIN connection_policies p
        ON p.policy_id = c.policy_id
)

SELECT *
FROM connection_evaluation
ORDER BY connection_id;


-- ============================================================
-- 29. FAILURE AND QUEUE MONITORING
-- ============================================================

-- Messages requiring retry or investigation.
SELECT
    connection_id,
    message_id,
    sequence_number,
    status,
    error_message,
    created_at
FROM websocket_messages
WHERE status IN ('failed', 'expired')
ORDER BY created_at DESC;


-- Connections with unacknowledged heartbeats.
SELECT
    connection_id,
    COUNT(*) AS outstanding_heartbeats
FROM connection_heartbeats
WHERE received_at IS NULL
GROUP BY connection_id
HAVING COUNT(*) > 0;


-- Outbound queue utilization.
SELECT
    c.connection_id,
    COUNT(m.message_id) AS queued_messages,
    COALESCE(SUM(m.payload_bytes), 0) AS queued_bytes,
    p.maximum_queued_messages,
    p.maximum_queued_bytes
FROM websocket_connections c
JOIN connection_policies p
    ON p.policy_id = c.policy_id
LEFT JOIN websocket_messages m
    ON m.connection_id = c.connection_id
   AND m.direction = 'outbound'
   AND m.status = 'queued'
GROUP BY
    c.connection_id,
    p.maximum_queued_messages,
    p.maximum_queued_bytes
ORDER BY queued_bytes DESC;


-- ============================================================
-- 30. TRANSACTION AND FAILURE HANDLING EXAMPLE
-- ============================================================

-- Run this block independently when testing transactional closure.
-- Any exception rolls back the complete transaction.

DO $$
BEGIN

    BEGIN

        UPDATE websocket_connections
        SET state = 'closing',
            close_code = 1001,
            close_reason = 'Administrative shutdown'
        WHERE connection_id =
            '10000000-0000-0000-0000-000000000001'
          AND state = 'open';

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Connection cannot be closed';
        END IF;

        UPDATE websocket_connections
        SET state = 'closed',
            closed_at = NOW()
        WHERE connection_id =
            '10000000-0000-0000-0000-000000000001'
          AND state = 'closing';

    EXCEPTION WHEN OTHERS THEN

        RAISE NOTICE
            'Transactional shutdown failed: %',
            SQLERRM;

    END;

END;
$$;


-- ============================================================
-- 31. DATA RETENTION
-- ============================================================

-- Example: identify old closed connections eligible for archival.
-- Actual deletion should follow the tenant's retention policy.

SELECT
    connection_id,
    closed_at
FROM websocket_connections
WHERE state = 'closed'
  AND closed_at < NOW() - INTERVAL '90 days'
ORDER BY closed_at;


COMMIT;


/*
Operational considerations:

1. PostgreSQL stores connection metadata and durable events.
   It is not the WebSocket transport.

2. Actual sockets, TLS, frame parsing and network backpressure
   belong to the application server.

3. A queued message is not a delivered message.

4. A sent message is not necessarily acknowledged by the client.

5. A WebSocket pong is transport liveness evidence, not proof
   that an application operation succeeded.

6. The connection row lock serializes sequence allocation and
   queue capacity checks for an individual connection.

7. High-volume systems should use partitioning for messages,
   events and heartbeat records.

8. Production systems should use restricted database roles,
   parameterized SQL, encrypted transport, retention controls
   and tenant-scoped authorization.

9. Database transactions cannot atomically guarantee successful
   network delivery. An outbox and retry mechanism are required
   for reliable application-level delivery.
*/
