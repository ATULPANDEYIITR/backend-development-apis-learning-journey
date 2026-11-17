-- ============================================================
-- REDIS ADVANCED ENGINEERING
-- PostgreSQL 15+
--
-- Operational governance model for:
-- 1. Redis pipelines
-- 2. Redis transactions
-- 3. Lua scripts
-- 4. Distributed locks
-- 5. Lock leases and fencing tokens
-- 6. Operation auditing and performance reporting
--
-- PostgreSQL stores operational metadata and audit information.
-- Redis remains the execution engine for Redis commands.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS redis_governance;

SET search_path TO redis_governance, public;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

CREATE TYPE operation_type AS ENUM (
    'PIPELINE',
    'TRANSACTION',
    'LUA_SCRIPT',
    'LOCK_ACQUIRE',
    'LOCK_RELEASE',
    'LOCK_RENEW',
    'FENCING_VALIDATION'
);

CREATE TYPE operation_status AS ENUM (
    'PENDING',
    'RUNNING',
    'SUCCEEDED',
    'PARTIALLY_FAILED',
    'FAILED',
    'TIMED_OUT',
    'CANCELLED'
);

CREATE TYPE transaction_mode AS ENUM (
    'MULTI_EXEC',
    'WATCH_MULTI_EXEC'
);

CREATE TYPE lock_status AS ENUM (
    'REQUESTED',
    'ACQUIRED',
    'BUSY',
    'RELEASED',
    'EXPIRED',
    'OWNERSHIP_LOST'
);

CREATE TYPE script_status AS ENUM (
    'ACTIVE',
    'DISABLED',
    'RETIRED'
);

-- ============================================================
-- 2. REDIS DEPLOYMENTS
-- ============================================================

CREATE TABLE redis_deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_name VARCHAR(120) NOT NULL UNIQUE,

    environment VARCHAR(30) NOT NULL
        CHECK (
            environment IN (
                'DEVELOPMENT',
                'TESTING',
                'STAGING',
                'PRODUCTION'
            )
        ),

    endpoint_alias VARCHAR(150) NOT NULL,

    redis_version VARCHAR(30) NOT NULL,

    cluster_mode BOOLEAN NOT NULL DEFAULT FALSE,

    tls_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    max_connections INTEGER NOT NULL DEFAULT 100
        CHECK (max_connections > 0),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. APPLICATIONS
-- ============================================================

CREATE TABLE applications (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    application_name VARCHAR(150) NOT NULL UNIQUE,

    owner_team VARCHAR(120) NOT NULL,

    criticality VARCHAR(20) NOT NULL
        CHECK (
            criticality IN (
                'LOW',
                'MEDIUM',
                'HIGH',
                'CRITICAL'
            )
        ),

    deployment_id BIGINT NOT NULL
        REFERENCES redis_deployments(deployment_id),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_applications_deployment
ON applications(deployment_id);

-- ============================================================
-- 4. LUA SCRIPT REGISTRY
-- ============================================================

CREATE TABLE lua_scripts (
    script_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    application_id BIGINT NOT NULL
        REFERENCES applications(application_id),

    script_name VARCHAR(150) NOT NULL,

    sha1_hash CHAR(40) NOT NULL,

    source_text TEXT NOT NULL,

    script_version INTEGER NOT NULL
        CHECK (script_version > 0),

    status script_status NOT NULL DEFAULT 'ACTIVE',

    idempotency_required BOOLEAN NOT NULL DEFAULT FALSE,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(application_id, script_name, script_version),

    UNIQUE(sha1_hash)
);

CREATE INDEX idx_lua_scripts_active
ON lua_scripts(application_id, status)
WHERE status = 'ACTIVE';

-- ============================================================
-- 5. OPERATION EXECUTION LOG
-- ============================================================

CREATE TABLE redis_operations (
    operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    application_id BIGINT NOT NULL
        REFERENCES applications(application_id),

    deployment_id BIGINT NOT NULL
        REFERENCES redis_deployments(deployment_id),

    operation_type operation_type NOT NULL,

    status operation_status NOT NULL DEFAULT 'PENDING',

    correlation_id UUID NOT NULL DEFAULT gen_random_uuid(),

    idempotency_key VARCHAR(200),

    command_count INTEGER NOT NULL DEFAULT 0
        CHECK (command_count >= 0),

    successful_commands INTEGER NOT NULL DEFAULT 0
        CHECK (successful_commands >= 0),

    failed_commands INTEGER NOT NULL DEFAULT 0
        CHECK (failed_commands >= 0),

    duration_ms NUMERIC(12, 3)
        CHECK (duration_ms IS NULL OR duration_ms >= 0),

    error_message TEXT,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        successful_commands + failed_commands <= command_count
    ),

    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    ),

    UNIQUE(application_id, idempotency_key)
);

CREATE INDEX idx_operations_application_time
ON redis_operations(application_id, created_at DESC);

CREATE INDEX idx_operations_status
ON redis_operations(status, created_at DESC);

CREATE INDEX idx_operations_type_time
ON redis_operations(operation_type, created_at DESC);

CREATE INDEX idx_operations_correlation
ON redis_operations(correlation_id);

-- ============================================================
-- 6. PIPELINE COMMANDS
-- ============================================================

CREATE TABLE pipeline_commands (
    pipeline_command_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    operation_id BIGINT NOT NULL
        REFERENCES redis_operations(operation_id)
        ON DELETE CASCADE,

    sequence_number INTEGER NOT NULL
        CHECK (sequence_number > 0),

    command_name VARCHAR(50) NOT NULL,

    redis_key VARCHAR(512) NOT NULL,

    payload_size_bytes INTEGER NOT NULL DEFAULT 0
        CHECK (payload_size_bytes >= 0),

    result_status operation_status NOT NULL DEFAULT 'PENDING',

    error_message TEXT,

    UNIQUE(operation_id, sequence_number)
);

CREATE INDEX idx_pipeline_command_operation
ON pipeline_commands(operation_id, sequence_number);

-- ============================================================
-- 7. TRANSACTIONS
-- ============================================================

CREATE TABLE redis_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    operation_id BIGINT NOT NULL UNIQUE
        REFERENCES redis_operations(operation_id),

    transaction_mode transaction_mode NOT NULL,

    watched_key_count INTEGER NOT NULL DEFAULT 0
        CHECK (watched_key_count >= 0),

    queued_command_count INTEGER NOT NULL DEFAULT 0
        CHECK (queued_command_count >= 0),

    watch_conflict BOOLEAN NOT NULL DEFAULT FALSE,

    exec_returned_null BOOLEAN NOT NULL DEFAULT FALSE,

    committed BOOLEAN NOT NULL DEFAULT FALSE,

    runtime_error_count INTEGER NOT NULL DEFAULT 0
        CHECK (runtime_error_count >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        NOT committed OR NOT exec_returned_null
    )
);

-- ============================================================
-- 8. LUA SCRIPT EXECUTIONS
-- ============================================================

CREATE TABLE lua_executions (
    lua_execution_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    operation_id BIGINT NOT NULL UNIQUE
        REFERENCES redis_operations(operation_id),

    script_id BIGINT NOT NULL
        REFERENCES lua_scripts(script_id),

    execution_sha1 CHAR(40) NOT NULL,

    eval_mode VARCHAR(10) NOT NULL
        CHECK (eval_mode IN ('EVAL', 'EVALSHA')),

    noscript_fallback BOOLEAN NOT NULL DEFAULT FALSE,

    key_count INTEGER NOT NULL DEFAULT 0
        CHECK (key_count >= 0),

    argument_count INTEGER NOT NULL DEFAULT 0
        CHECK (argument_count >= 0),

    execution_time_ms NUMERIC(12, 3)
        CHECK (
            execution_time_ms IS NULL
            OR execution_time_ms >= 0
        ),

    returned_result JSONB,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lua_execution_script
ON lua_executions(script_id, created_at DESC);

-- ============================================================
-- 9. DISTRIBUTED LOCKS
-- ============================================================

CREATE TABLE distributed_locks (
    lock_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES redis_deployments(deployment_id),

    application_id BIGINT NOT NULL
        REFERENCES applications(application_id),

    lock_key VARCHAR(512) NOT NULL,

    owner_identifier VARCHAR(150) NOT NULL,

    ownership_token UUID NOT NULL,

    fencing_token BIGINT NOT NULL
        CHECK (fencing_token > 0),

    status lock_status NOT NULL DEFAULT 'REQUESTED',

    lease_duration_ms BIGINT NOT NULL
        CHECK (lease_duration_ms > 0),

    acquired_at TIMESTAMPTZ,

    expires_at TIMESTAMPTZ,

    released_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        expires_at IS NULL
        OR acquired_at IS NULL
        OR expires_at > acquired_at
    ),

    CHECK (
        released_at IS NULL
        OR acquired_at IS NULL
        OR released_at >= acquired_at
    ),

    UNIQUE(deployment_id, ownership_token)
);

CREATE INDEX idx_locks_key_status
ON distributed_locks(
    deployment_id,
    lock_key,
    status
);

CREATE INDEX idx_locks_expiration
ON distributed_locks(expires_at)
WHERE status = 'ACQUIRED';

CREATE INDEX idx_locks_fencing
ON distributed_locks(deployment_id, lock_key, fencing_token DESC);

-- ============================================================
-- 10. FENCING TOKEN SEQUENCES
-- ============================================================

CREATE TABLE fencing_sequences (
    deployment_id BIGINT NOT NULL
        REFERENCES redis_deployments(deployment_id),

    lock_key VARCHAR(512) NOT NULL,

    last_token BIGINT NOT NULL DEFAULT 0
        CHECK (last_token >= 0),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY(deployment_id, lock_key)
);

-- ============================================================
-- 11. LOCK EVENT AUDIT
-- ============================================================

CREATE TABLE lock_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    lock_id BIGINT
        REFERENCES distributed_locks(lock_id),

    event_type VARCHAR(30) NOT NULL
        CHECK (
            event_type IN (
                'REQUESTED',
                'ACQUIRED',
                'RENEWED',
                'RELEASED',
                'EXPIRED',
                'OWNERSHIP_LOST',
                'BUSY'
            )
        ),

    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX idx_lock_events_lock_time
ON lock_events(lock_id, event_time DESC);

-- ============================================================
-- 12. AUTOMATIC OPERATION VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_redis_operation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.command_count < 0 THEN
        RAISE EXCEPTION 'Invalid command count';
    END IF;

    IF NEW.successful_commands + NEW.failed_commands
       > NEW.command_count THEN
        RAISE EXCEPTION 'Command results exceed command count';
    END IF;

    IF NEW.status = 'RUNNING' AND NEW.started_at IS NULL THEN
        NEW.started_at := NOW();
    END IF;

    IF NEW.status IN (
        'SUCCEEDED',
        'PARTIALLY_FAILED',
        'FAILED',
        'TIMED_OUT',
        'CANCELLED'
    ) THEN
        NEW.completed_at := COALESCE(
            NEW.completed_at,
            NOW()
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_redis_operation
BEFORE INSERT OR UPDATE ON redis_operations
FOR EACH ROW
EXECUTE FUNCTION validate_redis_operation();

-- ============================================================
-- 13. LOCK EVENT AUDIT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION audit_lock_status_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO lock_events(
            lock_id,
            event_type,
            event_details
        )
        VALUES (
            NEW.lock_id,
            'REQUESTED',
            jsonb_build_object(
                'lock_key', NEW.lock_key,
                'owner', NEW.owner_identifier
            )
        );

        RETURN NEW;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO lock_events(
            lock_id,
            event_type,
            event_details
        )
        VALUES (
            NEW.lock_id,
            NEW.status::TEXT,
            jsonb_build_object(
                'previous_status', OLD.status,
                'new_status', NEW.status,
                'fencing_token', NEW.fencing_token
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_audit_lock_status
AFTER INSERT OR UPDATE OF status ON distributed_locks
FOR EACH ROW
EXECUTE FUNCTION audit_lock_status_change();

-- ============================================================
-- 14. FENCING TOKEN ALLOCATION
-- ============================================================

CREATE OR REPLACE FUNCTION allocate_fencing_token(
    p_deployment_id BIGINT,
    p_lock_key VARCHAR
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_token BIGINT;
BEGIN
    INSERT INTO fencing_sequences(
        deployment_id,
        lock_key,
        last_token
    )
    VALUES (
        p_deployment_id,
        p_lock_key,
        1
    )
    ON CONFLICT(deployment_id, lock_key)
    DO UPDATE SET
        last_token = fencing_sequences.last_token + 1,
        updated_at = NOW()
    RETURNING last_token INTO v_token;

    RETURN v_token;
END;
$$;

-- ============================================================
-- 15. LOCK ACQUISITION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE acquire_distributed_lock(
    IN p_deployment_id BIGINT,
    IN p_application_id BIGINT,
    IN p_lock_key VARCHAR,
    IN p_owner VARCHAR,
    IN p_lease_ms BIGINT,
    INOUT p_lock_id BIGINT DEFAULT NULL,
    INOUT p_result VARCHAR DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_token UUID;
    v_fencing BIGINT;
BEGIN
    IF p_lease_ms <= 0 THEN
        RAISE EXCEPTION 'Lease duration must be positive';
    END IF;

    IF p_lock_key IS NULL OR p_lock_key = '' THEN
        RAISE EXCEPTION 'Lock key is required';
    END IF;

    -- Serialize lock acquisition for a given deployment/key.
    PERFORM pg_advisory_xact_lock(
        p_deployment_id,
        hashtext(p_lock_key)
    );

    UPDATE distributed_locks
    SET status = 'EXPIRED'
    WHERE deployment_id = p_deployment_id
      AND lock_key = p_lock_key
      AND status = 'ACQUIRED'
      AND expires_at <= NOW();

    IF EXISTS (
        SELECT 1
        FROM distributed_locks
        WHERE deployment_id = p_deployment_id
          AND lock_key = p_lock_key
          AND status = 'ACQUIRED'
          AND expires_at > NOW()
    ) THEN
        p_result := 'BUSY';
        p_lock_id := NULL;
        RETURN;
    END IF;

    v_token := gen_random_uuid();

    v_fencing := allocate_fencing_token(
        p_deployment_id,
        p_lock_key
    );

    INSERT INTO distributed_locks(
        deployment_id,
        application_id,
        lock_key,
        owner_identifier,
        ownership_token,
        fencing_token,
        status,
        lease_duration_ms,
        acquired_at,
        expires_at
    )
    VALUES (
        p_deployment_id,
        p_application_id,
        p_lock_key,
        p_owner,
        v_token,
        v_fencing,
        'ACQUIRED',
        p_lease_ms,
        NOW(),
        NOW() + p_lease_ms * INTERVAL '1 millisecond'
    )
    RETURNING lock_id INTO p_lock_id;

    p_result := 'ACQUIRED';
END;
$$;

-- ============================================================
-- 16. SAFE LOCK RELEASE
-- ============================================================

CREATE OR REPLACE FUNCTION release_distributed_lock(
    p_lock_id BIGINT,
    p_ownership_token UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE distributed_locks
    SET
        status = 'RELEASED',
        released_at = NOW()
    WHERE lock_id = p_lock_id
      AND ownership_token = p_ownership_token
      AND status = 'ACQUIRED'
      AND expires_at > NOW();

    GET DIAGNOSTICS v_updated = ROW_COUNT;

    RETURN v_updated = 1;
END;
$$;

-- ============================================================
-- 17. FENCING VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_fencing_token(
    p_deployment_id BIGINT,
    p_lock_key VARCHAR,
    p_token BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_latest BIGINT;
BEGIN
    SELECT last_token
    INTO v_latest
    FROM fencing_sequences
    WHERE deployment_id = p_deployment_id
      AND lock_key = p_lock_key;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    RETURN p_token = v_latest;
END;
$$;

-- ============================================================
-- 18. OPERATION METRICS VIEW
-- ============================================================

CREATE OR REPLACE VIEW operation_metrics AS
SELECT
    d.deployment_name,
    a.application_name,
    o.operation_type,
    COUNT(*) AS total_operations,

    COUNT(*) FILTER (
        WHERE o.status = 'SUCCEEDED'
    ) AS successful_operations,

    COUNT(*) FILTER (
        WHERE o.status = 'FAILED'
    ) AS failed_operations,

    ROUND(
        AVG(o.duration_ms),
        3
    ) AS average_duration_ms,

    ROUND(
        PERCENTILE_CONT(0.95)
        WITHIN GROUP (ORDER BY o.duration_ms)::NUMERIC,
        3
    ) AS p95_duration_ms

FROM redis_operations o

JOIN applications a
    ON a.application_id = o.application_id

JOIN redis_deployments d
    ON d.deployment_id = o.deployment_id

GROUP BY
    d.deployment_name,
    a.application_name,
    o.operation_type;

-- ============================================================
-- 19. PIPELINE PERFORMANCE VIEW
-- ============================================================

CREATE OR REPLACE VIEW pipeline_performance AS
SELECT
    o.operation_id,
    a.application_name,
    COUNT(pc.pipeline_command_id) AS queued_commands,

    COUNT(*) FILTER (
        WHERE pc.result_status = 'SUCCEEDED'
    ) AS successful_commands,

    COUNT(*) FILTER (
        WHERE pc.result_status = 'FAILED'
    ) AS failed_commands,

    o.duration_ms,

    CASE
        WHEN o.duration_ms > 0
        THEN ROUND(
            COUNT(pc.pipeline_command_id)::NUMERIC
            / o.duration_ms * 1000,
            2
        )
        ELSE NULL
    END AS commands_per_second

FROM redis_operations o

JOIN applications a
    ON a.application_id = o.application_id

LEFT JOIN pipeline_commands pc
    ON pc.operation_id = o.operation_id

WHERE o.operation_type = 'PIPELINE'

GROUP BY
    o.operation_id,
    a.application_name,
    o.duration_ms;

-- ============================================================
-- 20. LOCK EXPIRATION MONITORING VIEW
-- ============================================================

CREATE OR REPLACE VIEW active_lock_monitor AS
SELECT
    l.lock_id,
    d.deployment_name,
    l.lock_key,
    l.owner_identifier,
    l.fencing_token,
    l.acquired_at,
    l.expires_at,

    GREATEST(
        0,
        EXTRACT(
            EPOCH FROM (l.expires_at - NOW())
        ) * 1000
    )::BIGINT AS remaining_lease_ms

FROM distributed_locks l

JOIN redis_deployments d
    ON d.deployment_id = l.deployment_id

WHERE l.status = 'ACQUIRED'
  AND l.expires_at > NOW();

-- ============================================================
-- 21. SAMPLE DEPLOYMENTS
-- ============================================================

INSERT INTO redis_deployments(
    deployment_name,
    environment,
    endpoint_alias,
    redis_version,
    cluster_mode,
    tls_enabled
)
VALUES
(
    'redis-development',
    'DEVELOPMENT',
    'redis-dev.internal',
    '7.4',
    FALSE,
    FALSE
),
(
    'redis-production',
    'PRODUCTION',
    'redis-prod.internal',
    '7.4',
    TRUE,
    TRUE
);

INSERT INTO applications(
    application_name,
    owner_team,
    criticality,
    deployment_id
)
SELECT
    'inventory-service',
    'Platform Engineering',
    'HIGH',
    deployment_id
FROM redis_deployments
WHERE deployment_name = 'redis-development';

INSERT INTO applications(
    application_name,
    owner_team,
    criticality,
    deployment_id
)
SELECT
    'payment-service',
    'Payments Engineering',
    'CRITICAL',
    deployment_id
FROM redis_deployments
WHERE deployment_name = 'redis-production';

-- ============================================================
-- 22. LUA SCRIPT REGISTRY DATA
-- ============================================================

INSERT INTO lua_scripts(
    application_id,
    script_name,
    sha1_hash,
    source_text,
    script_version,
    idempotency_required,
    description
)
SELECT
    application_id,
    'inventory-reservation',
    repeat('a', 40),
    'Atomic stock validation and decrement using Lua.',
    1,
    TRUE,
    'Prevents concurrent inventory over-reservation.'
FROM applications
WHERE application_name = 'inventory-service';

-- ============================================================
-- 23. SAMPLE PIPELINE OPERATION
-- ============================================================

INSERT INTO redis_operations(
    application_id,
    deployment_id,
    operation_type,
    status,
    command_count,
    successful_commands,
    failed_commands,
    duration_ms,
    started_at
)
SELECT
    a.application_id,
    a.deployment_id,
    'PIPELINE',
    'SUCCEEDED',
    3,
    3,
    0,
    4.250,
    NOW() - INTERVAL '5 seconds'
FROM applications a
WHERE a.application_name = 'inventory-service';

INSERT INTO pipeline_commands(
    operation_id,
    sequence_number,
    command_name,
    redis_key,
    payload_size_bytes,
    result_status
)
SELECT
    operation_id,
    command.sequence_number,
    command.command_name,
    command.redis_key,
    command.payload_size,
    'SUCCEEDED'
FROM redis_operations o
CROSS JOIN (
    VALUES
        (1, 'SET', 'metrics:requests', 20),
        (2, 'INCRBY', 'metrics:requests', 8),
        (3, 'GET', 'metrics:requests', 10)
) AS command(
    sequence_number,
    command_name,
    redis_key,
    payload_size
)
WHERE o.operation_type = 'PIPELINE'
  AND o.status = 'SUCCEEDED';

-- ============================================================
-- 24. SAMPLE TRANSACTION
-- ============================================================

WITH new_operation AS (
    INSERT INTO redis_operations(
        application_id,
        deployment_id,
        operation_type,
        status,
        command_count,
        successful_commands,
        duration_ms,
        started_at
    )
    SELECT
        application_id,
        deployment_id,
        'TRANSACTION',
        'SUCCEEDED',
        4,
        4,
        2.800,
        NOW()
    FROM applications
    WHERE application_name = 'payment-service'
    RETURNING operation_id
)
INSERT INTO redis_transactions(
    operation_id,
    transaction_mode,
    watched_key_count,
    queued_command_count,
    committed
)
SELECT
    operation_id,
    'MULTI_EXEC',
    0,
    4,
    TRUE
FROM new_operation;

-- ============================================================
-- 25. SAMPLE LUA EXECUTION
-- ============================================================

WITH new_operation AS (
    INSERT INTO redis_operations(
        application_id,
        deployment_id,
        operation_type,
        status,
        command_count,
        successful_commands,
        duration_ms
    )
    SELECT
        a.application_id,
        a.deployment_id,
        'LUA_SCRIPT',
        'SUCCEEDED',
        1,
        1,
        1.350
    FROM applications a
    WHERE a.application_name = 'inventory-service'
    RETURNING operation_id
)
INSERT INTO lua_executions(
    operation_id,
    script_id,
    execution_sha1,
    eval_mode,
    key_count,
    argument_count,
    execution_time_ms,
    returned_result
)
SELECT
    n.operation_id,
    s.script_id,
    s.sha1_hash,
    'EVALSHA',
    2,
    1,
    1.350,
    '{"remaining_stock": 15}'::JSONB
FROM new_operation n
CROSS JOIN lua_scripts s
WHERE s.script_name = 'inventory-reservation';

-- ============================================================
-- 26. SAMPLE LOCK ACQUISITION
-- ============================================================

DO $$
DECLARE
    v_deployment BIGINT;
    v_application BIGINT;
    v_lock_id BIGINT;
    v_result VARCHAR;
BEGIN
    SELECT deployment_id
    INTO v_deployment
    FROM redis_deployments
    WHERE deployment_name = 'redis-development';

    SELECT application_id
    INTO v_application
    FROM applications
    WHERE application_name = 'inventory-service';

    CALL acquire_distributed_lock(
        v_deployment,
        v_application,
        'locks:inventory-reconciliation',
        'worker-01',
        30000,
        v_lock_id,
        v_result
    );

    RAISE NOTICE
        'Lock acquisition: %, lock ID: %',
        v_result,
        v_lock_id;
END;
$$;

-- ============================================================
-- 27. SAMPLE FAILURE OPERATION
-- ============================================================

INSERT INTO redis_operations(
    application_id,
    deployment_id,
    operation_type,
    status,
    command_count,
    successful_commands,
    failed_commands,
    duration_ms,
    error_message
)
SELECT
    application_id,
    deployment_id,
    'TRANSACTION',
    'FAILED',
    3,
    1,
    2,
    8.500,
    'Transaction contained runtime command errors.'
FROM applications
WHERE application_name = 'payment-service';

-- ============================================================
-- 28. RETRIEVAL QUERIES
-- ============================================================

-- Retrieve recent Redis operations.
SELECT
    operation_id,
    operation_type,
    status,
    command_count,
    successful_commands,
    failed_commands,
    duration_ms,
    created_at
FROM redis_operations
ORDER BY created_at DESC;

-- Retrieve pipeline command details.
SELECT
    o.operation_id,
    pc.sequence_number,
    pc.command_name,
    pc.redis_key,
    pc.result_status
FROM pipeline_commands pc
JOIN redis_operations o
    ON o.operation_id = pc.operation_id
ORDER BY o.operation_id, pc.sequence_number;

-- ============================================================
-- 29. VALIDATION QUERIES
-- ============================================================

-- Identify failed operations.
SELECT *
FROM redis_operations
WHERE status IN (
    'FAILED',
    'PARTIALLY_FAILED',
    'TIMED_OUT'
);

-- Identify active locks close to expiration.
SELECT *
FROM active_lock_monitor
WHERE remaining_lease_ms < 5000;

-- Identify Lua script hash mismatches.
SELECT
    script_id,
    script_name,
    sha1_hash,
    LENGTH(source_text) AS source_length
FROM lua_scripts
WHERE status = 'ACTIVE'
  AND LENGTH(sha1_hash) <> 40;

-- ============================================================
-- 30. AGGREGATION AND REPORTING
-- ============================================================

-- Operation counts by application and type.
SELECT
    a.application_name,
    o.operation_type,
    COUNT(*) AS total,
    COUNT(*) FILTER (
        WHERE o.status = 'SUCCEEDED'
    ) AS successful,
    COUNT(*) FILTER (
        WHERE o.status = 'FAILED'
    ) AS failed
FROM redis_operations o
JOIN applications a
    ON a.application_id = o.application_id
GROUP BY
    a.application_name,
    o.operation_type
ORDER BY
    a.application_name,
    o.operation_type;

-- Average and maximum execution duration.
SELECT
    operation_type,
    ROUND(AVG(duration_ms), 3) AS average_ms,
    ROUND(MAX(duration_ms), 3) AS maximum_ms
FROM redis_operations
WHERE duration_ms IS NOT NULL
GROUP BY operation_type;

-- ============================================================
-- 31. TRANSACTION EVALUATION
-- ============================================================

SELECT
    t.transaction_id,
    t.transaction_mode,
    t.queued_command_count,
    t.watch_conflict,
    t.exec_returned_null,
    t.committed,
    t.runtime_error_count
FROM redis_transactions t
ORDER BY t.created_at DESC;

-- ============================================================
-- 32. LOCK GOVERNANCE REPORT
-- ============================================================

SELECT
    lock_key,
    owner_identifier,
    fencing_token,
    status,
    acquired_at,
    expires_at,
    released_at
FROM distributed_locks
ORDER BY created_at DESC;

-- ============================================================
-- 33. LUA EXECUTION REPORT
-- ============================================================

SELECT
    s.script_name,
    s.script_version,
    l.eval_mode,
    l.noscript_fallback,
    l.execution_time_ms,
    l.returned_result
FROM lua_executions l
JOIN lua_scripts s
    ON s.script_id = l.script_id
ORDER BY l.created_at DESC;

-- ============================================================
-- 34. EXPIRED LOCK CLEANUP
-- ============================================================

UPDATE distributed_locks
SET status = 'EXPIRED'
WHERE status = 'ACQUIRED'
  AND expires_at <= NOW();

-- ============================================================
-- 35. EXAMPLE SAFE RELEASE
-- ============================================================

-- The release function requires the original ownership token.
-- A caller must supply the actual UUID returned at acquisition.
--
-- SELECT release_distributed_lock(
--     1,
--     '00000000-0000-0000-0000-000000000000'
-- );

-- ============================================================
-- 36. PERFORMANCE AND SECURITY NOTES
-- ============================================================

-- Pipeline commands reduce network round trips.
-- Pipeline size should be bounded to prevent excessive memory use.
--
-- MULTI/EXEC provides atomic execution but not rollback of runtime
-- command errors. WATCH can detect optimistic concurrency conflicts.
--
-- Lua scripts execute atomically on Redis. Long-running scripts
-- can block Redis command processing.
--
-- Distributed locks use unique ownership tokens and expiration.
-- Release must compare the token before deleting the lock.
--
-- Fencing tokens must be enforced by the protected resource.
-- A PostgreSQL audit table does not itself make a Redis lock atomic.
--
-- Never store Redis passwords, raw credentials, or sensitive
-- command payloads in audit tables.
--
-- In Redis Cluster, all keys accessed by one Lua script or
-- multi-key transaction must be compatible with hash-slot rules.
--
-- PostgreSQL indexes improve reporting but increase write cost.
-- Time-based partitioning is appropriate for large audit volumes.

COMMIT;
