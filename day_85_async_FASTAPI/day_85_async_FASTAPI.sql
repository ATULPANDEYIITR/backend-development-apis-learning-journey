/*
 * ASYNC FASTAPI ENGINEERING
 * PostgreSQL database design and asynchronous workload monitoring.
 *
 * Compatible with PostgreSQL 14+.
 *
 * Create database separately:
 *   CREATE DATABASE async_fastapi_db;
 *
 * Execute:
 *   psql -U postgres -d async_fastapi_db -f async_fastapi.sql
 *
 * Models:
 *   - Application instances
 *   - API requests
 *   - Asynchronous tasks
 *   - Task execution attempts
 *   - Database connection pools
 *   - Background jobs
 *   - Request failures
 *   - Idempotency
 *   - Operational metrics
 *   - Transactional task processing
 */

BEGIN;

CREATE SCHEMA IF NOT EXISTS async_service;

SET search_path TO async_service, public;

-- ---------------------------------------------------------
-- Enumerated domain types
-- ---------------------------------------------------------

CREATE TYPE request_state AS ENUM (
    'received',
    'running',
    'completed',
    'failed',
    'timed_out',
    'cancelled'
);

CREATE TYPE task_state AS ENUM (
    'pending',
    'running',
    'completed',
    'failed'
);

CREATE TYPE operation_category AS ENUM (
    'database_read',
    'database_write',
    'external_api',
    'file_io',
    'cpu_computation'
);

CREATE TYPE job_state AS ENUM (
    'queued',
    'running',
    'completed',
    'failed',
    'cancelled'
);


-- ---------------------------------------------------------
-- Application instances
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS application_instances (
    instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    instance_name VARCHAR(100) NOT NULL UNIQUE,

    host_name VARCHAR(255) NOT NULL,

    worker_count INTEGER NOT NULL DEFAULT 4,

    maximum_connections INTEGER NOT NULL DEFAULT 10,

    active_connections INTEGER NOT NULL DEFAULT 0,

    instance_status VARCHAR(20) NOT NULL DEFAULT 'active',

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_worker_count
        CHECK (worker_count BETWEEN 1 AND 256),

    CONSTRAINT valid_connection_capacity
        CHECK (maximum_connections BETWEEN 1 AND 1000),

    CONSTRAINT valid_active_connections
        CHECK (
            active_connections >= 0
            AND active_connections <= maximum_connections
        ),

    CONSTRAINT valid_instance_status
        CHECK (
            instance_status IN ('active', 'draining', 'stopped')
        )
);


-- ---------------------------------------------------------
-- API requests
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS api_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    instance_id UUID REFERENCES application_instances(instance_id),

    method VARCHAR(10) NOT NULL,

    endpoint VARCHAR(500) NOT NULL,

    request_state request_state NOT NULL DEFAULT 'received',

    http_status SMALLINT,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    duration_ms NUMERIC(14, 3),

    error_message TEXT,

    correlation_id UUID NOT NULL DEFAULT gen_random_uuid(),

    CONSTRAINT valid_http_method
        CHECK (
            method IN (
                'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'
            )
        ),

    CONSTRAINT valid_http_status
        CHECK (
            http_status IS NULL
            OR http_status BETWEEN 100 AND 599
        ),

    CONSTRAINT valid_duration
        CHECK (duration_ms IS NULL OR duration_ms >= 0),

    CONSTRAINT valid_completion_time
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE INDEX idx_requests_started
ON api_requests (started_at DESC);

CREATE INDEX idx_requests_state_started
ON api_requests (request_state, started_at DESC);

CREATE INDEX idx_requests_correlation
ON api_requests (correlation_id);

CREATE INDEX idx_requests_failed
ON api_requests (started_at DESC)
WHERE request_state IN ('failed', 'timed_out');


-- ---------------------------------------------------------
-- Asynchronous tasks
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    request_id UUID REFERENCES api_requests(request_id),

    title VARCHAR(150) NOT NULL,

    description TEXT NOT NULL DEFAULT '',

    task_status task_state NOT NULL DEFAULT 'pending',

    idempotency_key VARCHAR(100) UNIQUE,

    retry_count INTEGER NOT NULL DEFAULT 0,

    maximum_retries INTEGER NOT NULL DEFAULT 3,

    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_task_title
        CHECK (length(trim(title)) BETWEEN 3 AND 150),

    CONSTRAINT valid_task_description
        CHECK (length(description) <= 2000),

    CONSTRAINT valid_retry_count
        CHECK (
            retry_count >= 0
            AND maximum_retries BETWEEN 0 AND 20
            AND retry_count <= maximum_retries
        ),

    CONSTRAINT valid_task_timestamps
        CHECK (
            (started_at IS NULL OR started_at >= created_at)
            AND
            (completed_at IS NULL OR started_at IS NOT NULL)
            AND
            (completed_at IS NULL OR completed_at >= started_at)
        )
);

CREATE INDEX idx_tasks_status_created
ON tasks (task_status, created_at DESC);

CREATE INDEX idx_tasks_pending_schedule
ON tasks (scheduled_at, created_at)
WHERE task_status = 'pending';

CREATE INDEX idx_tasks_request
ON tasks (request_id);


-- ---------------------------------------------------------
-- Task execution attempts
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS task_attempts (
    attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    task_id UUID NOT NULL REFERENCES tasks(task_id),

    attempt_number INTEGER NOT NULL,

    execution_status task_state NOT NULL,

    worker_name VARCHAR(100),

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    duration_ms NUMERIC(14, 3),

    error_message TEXT,

    CONSTRAINT unique_task_attempt
        UNIQUE (task_id, attempt_number),

    CONSTRAINT valid_attempt_number
        CHECK (attempt_number > 0),

    CONSTRAINT valid_attempt_duration
        CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

CREATE INDEX idx_attempts_task
ON task_attempts (task_id, attempt_number DESC);


-- ---------------------------------------------------------
-- Database connection pool telemetry
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS connection_pool_metrics (
    metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    instance_id UUID NOT NULL
        REFERENCES application_instances(instance_id),

    pool_minimum INTEGER NOT NULL,

    pool_maximum INTEGER NOT NULL,

    active_connections INTEGER NOT NULL,

    idle_connections INTEGER NOT NULL,

    waiting_requests INTEGER NOT NULL DEFAULT 0,

    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_pool_limits
        CHECK (
            pool_minimum >= 0
            AND pool_maximum > 0
            AND pool_minimum <= pool_maximum
        ),

    CONSTRAINT valid_pool_usage
        CHECK (
            active_connections >= 0
            AND idle_connections >= 0
            AND waiting_requests >= 0
            AND active_connections + idle_connections <= pool_maximum
        )
);

CREATE INDEX idx_pool_metrics_instance_time
ON connection_pool_metrics (instance_id, captured_at DESC);


-- ---------------------------------------------------------
-- Background job management
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS background_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    task_id UUID REFERENCES tasks(task_id),

    job_name VARCHAR(150) NOT NULL,

    job_status job_state NOT NULL DEFAULT 'queued',

    priority INTEGER NOT NULL DEFAULT 5,

    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    locked_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    failure_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_job_priority
        CHECK (priority BETWEEN 1 AND 10)
);

CREATE INDEX idx_jobs_queue
ON background_jobs (
    priority DESC,
    scheduled_at,
    created_at
)
WHERE job_status = 'queued';


-- ---------------------------------------------------------
-- Database operation audit
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS operation_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id UUID REFERENCES api_requests(request_id),

    task_id UUID REFERENCES tasks(task_id),

    operation_name VARCHAR(100) NOT NULL,

    execution_status VARCHAR(30) NOT NULL,

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    details JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX idx_audit_request
ON operation_audit (request_id, recorded_at DESC);

CREATE INDEX idx_audit_task
ON operation_audit (task_id, recorded_at DESC);


-- ---------------------------------------------------------
-- Automatic task timestamp maintenance
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION update_task_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_task_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION update_task_timestamp();


-- ---------------------------------------------------------
-- Task state transition validation
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_task_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.task_status = NEW.task_status THEN
        RETURN NEW;
    END IF;

    IF OLD.task_status = 'pending'
       AND NEW.task_status IN ('running', 'failed') THEN

        IF NEW.task_status = 'running'
           AND NEW.started_at IS NULL THEN
            NEW.started_at := NOW();
        END IF;

        RETURN NEW;
    END IF;

    IF OLD.task_status = 'running'
       AND NEW.task_status IN ('completed', 'failed') THEN

        IF NEW.completed_at IS NULL THEN
            NEW.completed_at := NOW();
        END IF;

        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'Invalid task transition: % -> %',
        OLD.task_status,
        NEW.task_status;

END;
$$;

CREATE OR REPLACE TRIGGER trg_validate_task_transition
BEFORE UPDATE OF task_status ON tasks
FOR EACH ROW
EXECUTE FUNCTION validate_task_transition();


-- ---------------------------------------------------------
-- Request completion validation
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_request_completion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.request_state IN (
        'completed', 'failed', 'timed_out', 'cancelled'
    ) THEN

        IF NEW.completed_at IS NULL THEN
            NEW.completed_at := NOW();
        END IF;

        IF NEW.duration_ms IS NULL THEN
            NEW.duration_ms :=
                EXTRACT(
                    EPOCH FROM (NEW.completed_at - NEW.started_at)
                ) * 1000;
        END IF;

    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_request_completion
BEFORE INSERT OR UPDATE ON api_requests
FOR EACH ROW
EXECUTE FUNCTION validate_request_completion();


-- ---------------------------------------------------------
-- Create task function with idempotency
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION create_task(
    p_title VARCHAR(150),
    p_description TEXT,
    p_idempotency_key VARCHAR(100)
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_task_id UUID;
BEGIN
    IF length(trim(p_title)) < 3 THEN
        RAISE EXCEPTION 'Task title must contain at least 3 characters';
    END IF;

    IF length(p_description) > 2000 THEN
        RAISE EXCEPTION 'Task description is too long';
    END IF;

    INSERT INTO tasks (
        title,
        description,
        idempotency_key
    )
    VALUES (
        p_title,
        COALESCE(p_description, ''),
        p_idempotency_key
    )
    ON CONFLICT (idempotency_key)
    DO NOTHING
    RETURNING task_id INTO v_task_id;

    IF v_task_id IS NULL THEN

        SELECT task_id
        INTO v_task_id
        FROM tasks
        WHERE idempotency_key = p_idempotency_key;

        IF v_task_id IS NULL THEN
            RAISE EXCEPTION 'Unable to resolve idempotent task';
        END IF;

    END IF;

    RETURN v_task_id;
END;
$$;


-- ---------------------------------------------------------
-- Claim queued background jobs safely
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION claim_background_job(
    p_worker_name VARCHAR(100)
)
RETURNS TABLE (
    claimed_job_id UUID,
    claimed_job_name VARCHAR(150)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH candidate AS (
        SELECT job_id
        FROM background_jobs
        WHERE job_status = 'queued'
          AND scheduled_at <= NOW()
        ORDER BY priority DESC, scheduled_at, created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE background_jobs AS jobs
    SET
        job_status = 'running',
        locked_at = NOW()
    FROM candidate
    WHERE jobs.job_id = candidate.job_id
    RETURNING jobs.job_id, jobs.job_name;
END;
$$;


-- ---------------------------------------------------------
-- Operational views
-- ---------------------------------------------------------

CREATE OR REPLACE VIEW request_performance AS
SELECT
    instance_id,
    COUNT(*) AS total_requests,

    COUNT(*) FILTER (
        WHERE request_state = 'completed'
    ) AS successful_requests,

    COUNT(*) FILTER (
        WHERE request_state = 'failed'
    ) AS failed_requests,

    COUNT(*) FILTER (
        WHERE request_state = 'timed_out'
    ) AS timed_out_requests,

    ROUND(
        AVG(duration_ms),
        2
    ) AS average_duration_ms,

    ROUND(
        MAX(duration_ms),
        2
    ) AS maximum_duration_ms

FROM api_requests
GROUP BY instance_id;


CREATE OR REPLACE VIEW task_performance AS
SELECT
    task_status,
    COUNT(*) AS total_tasks,
    AVG(
        EXTRACT(
            EPOCH FROM (completed_at - started_at)
        ) * 1000
    ) FILTER (
        WHERE completed_at IS NOT NULL
    ) AS average_execution_ms

FROM tasks
GROUP BY task_status;


CREATE OR REPLACE VIEW database_pool_health AS
SELECT
    i.instance_name,
    i.maximum_connections,
    i.active_connections,
    i.instance_status,

    COALESCE(
        latest.waiting_requests,
        0
    ) AS waiting_requests,

    latest.captured_at

FROM application_instances i

LEFT JOIN LATERAL (
    SELECT
        waiting_requests,
        captured_at
    FROM connection_pool_metrics m
    WHERE m.instance_id = i.instance_id
    ORDER BY captured_at DESC
    LIMIT 1
) latest ON TRUE;


-- ---------------------------------------------------------
-- Demonstration instance
-- ---------------------------------------------------------

INSERT INTO application_instances (
    instance_name,
    host_name,
    worker_count,
    maximum_connections,
    active_connections
)
VALUES
    ('fastapi-worker-01', 'app-node-01', 4, 10, 2),
    ('fastapi-worker-02', 'app-node-02', 8, 20, 4)
ON CONFLICT (instance_name)
DO NOTHING;


-- ---------------------------------------------------------
-- Sample API requests
-- ---------------------------------------------------------

INSERT INTO api_requests (
    instance_id,
    method,
    endpoint,
    request_state,
    http_status,
    duration_ms
)
SELECT
    instance_id,
    'GET',
    '/tasks',
    'completed',
    200,
    24.5
FROM application_instances
WHERE instance_name = 'fastapi-worker-01'
ON CONFLICT DO NOTHING;


INSERT INTO api_requests (
    instance_id,
    method,
    endpoint,
    request_state,
    http_status,
    duration_ms,
    error_message
)
SELECT
    instance_id,
    'GET',
    '/health/database',
    'timed_out',
    504,
    5000,
    'Database acquisition timed out'
FROM application_instances
WHERE instance_name = 'fastapi-worker-02';


-- ---------------------------------------------------------
-- Sample tasks
-- ---------------------------------------------------------

INSERT INTO tasks (
    title,
    description,
    task_status,
    idempotency_key
)
VALUES
    (
        'Configure asynchronous database operations',
        'Use an asynchronous PostgreSQL connection pool.',
        'pending',
        'async-db-001'
    ),
    (
        'Measure event loop performance',
        'Monitor latency and blocking operations.',
        'pending',
        'event-loop-001'
    ),
    (
        'Implement asynchronous API integration',
        'Use non-blocking HTTP clients.',
        'pending',
        'http-client-001'
    ),
    (
        'Configure connection pool monitoring',
        'Track active and idle database connections.',
        'pending',
        'pool-monitor-001'
    )
ON CONFLICT (idempotency_key)
DO NOTHING;


-- ---------------------------------------------------------
-- Sample task attempts
-- ---------------------------------------------------------

INSERT INTO task_attempts (
    task_id,
    attempt_number,
    execution_status,
    worker_name,
    duration_ms
)
SELECT
    task_id,
    1,
    'completed',
    'worker-01',
    125.5
FROM tasks
WHERE idempotency_key = 'async-db-001'
ON CONFLICT (task_id, attempt_number)
DO NOTHING;


-- ---------------------------------------------------------
-- Sample background jobs
-- ---------------------------------------------------------

INSERT INTO background_jobs (
    task_id,
    job_name,
    priority,
    job_status
)
SELECT
    task_id,
    'process_async_database_task',
    8,
    'queued'
FROM tasks
WHERE idempotency_key = 'async-db-001';


-- ---------------------------------------------------------
-- Sample connection pool metrics
-- ---------------------------------------------------------

INSERT INTO connection_pool_metrics (
    instance_id,
    pool_minimum,
    pool_maximum,
    active_connections,
    idle_connections,
    waiting_requests
)
SELECT
    instance_id,
    2,
    maximum_connections,
    active_connections,
    maximum_connections - active_connections,
    0
FROM application_instances;


-- ---------------------------------------------------------
-- Transactional workflow: process one task
-- ---------------------------------------------------------

DO $$
DECLARE
    v_task_id UUID;
BEGIN
    SELECT task_id
    INTO v_task_id
    FROM tasks
    WHERE idempotency_key = 'async-db-001'
    FOR UPDATE;

    IF v_task_id IS NOT NULL THEN

        UPDATE tasks
        SET task_status = 'running'
        WHERE task_id = v_task_id
          AND task_status = 'pending';

        INSERT INTO operation_audit (
            task_id,
            operation_name,
            execution_status,
            details
        )
        VALUES (
            v_task_id,
            'task_started',
            'success',
            jsonb_build_object(
                'worker', 'worker-01',
                'execution_mode', 'asynchronous'
            )
        );

    END IF;
END;
$$;


COMMIT;


-- ---------------------------------------------------------
-- RETRIEVAL QUERIES
-- ---------------------------------------------------------

-- Retrieve all tasks in chronological order.

SELECT
    task_id,
    title,
    task_status,
    created_at,
    updated_at
FROM async_service.tasks
ORDER BY created_at DESC;


-- Retrieve one task by identifier.

SELECT *
FROM async_service.tasks
WHERE task_id = (
    SELECT task_id
    FROM async_service.tasks
    WHERE idempotency_key = 'async-db-001'
);


-- ---------------------------------------------------------
-- VALIDATION QUERIES
-- ---------------------------------------------------------

-- Detect instances with invalid connection utilization.

SELECT
    instance_name,
    active_connections,
    maximum_connections
FROM async_service.application_instances
WHERE active_connections > maximum_connections;


-- Identify tasks exceeding retry limits.

SELECT
    task_id,
    title,
    retry_count,
    maximum_retries
FROM async_service.tasks
WHERE retry_count >= maximum_retries
  AND task_status = 'failed';


-- Detect incomplete running requests.

SELECT
    request_id,
    endpoint,
    started_at
FROM async_service.api_requests
WHERE request_state = 'running'
  AND completed_at IS NULL
  AND started_at < NOW() - INTERVAL '30 seconds';


-- ---------------------------------------------------------
-- AGGREGATION AND REPORTING
-- ---------------------------------------------------------

SELECT *
FROM async_service.request_performance
ORDER BY total_requests DESC;


SELECT *
FROM async_service.task_performance
ORDER BY total_tasks DESC;


-- Connection pool utilization.

SELECT
    instance_name,
    maximum_connections,
    active_connections,
    ROUND(
        active_connections::NUMERIC /
        NULLIF(maximum_connections, 0) * 100,
        2
    ) AS utilization_percentage
FROM async_service.application_instances;


-- Request latency percentiles.

SELECT
    percentile_cont(0.50)
        WITHIN GROUP (ORDER BY duration_ms) AS p50_ms,

    percentile_cont(0.95)
        WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,

    percentile_cont(0.99)
        WITHIN GROUP (ORDER BY duration_ms) AS p99_ms

FROM async_service.api_requests
WHERE duration_ms IS NOT NULL;


-- ---------------------------------------------------------
-- CTE: task execution and retry report
-- ---------------------------------------------------------

WITH task_statistics AS (
    SELECT
        t.task_id,
        t.title,
        t.task_status,
        t.retry_count,
        COUNT(a.attempt_id) AS total_attempts,

        AVG(a.duration_ms) AS average_attempt_duration

    FROM async_service.tasks t

    LEFT JOIN async_service.task_attempts a
        ON a.task_id = t.task_id

    GROUP BY
        t.task_id,
        t.title,
        t.task_status,
        t.retry_count
)
SELECT
    *,
    CASE
        WHEN task_status = 'completed'
            THEN 'success'

        WHEN retry_count >= 3
            THEN 'retry_limit_reached'

        WHEN task_status = 'running'
            THEN 'in_progress'

        ELSE 'pending_processing'
    END AS processing_assessment

FROM task_statistics
ORDER BY total_attempts DESC;


-- ---------------------------------------------------------
-- WORKFLOW PROCESSING
-- ---------------------------------------------------------

-- Safely claim one queued job.
-- SKIP LOCKED allows multiple workers to claim different jobs.

BEGIN;

SELECT *
FROM async_service.claim_background_job('worker-02');

COMMIT;


-- ---------------------------------------------------------
-- ELIGIBILITY DETERMINATION
-- ---------------------------------------------------------

-- Identify jobs eligible for execution.

SELECT
    job_id,
    job_name,
    priority,
    scheduled_at,

    CASE
        WHEN job_status = 'queued'
         AND scheduled_at <= NOW()
            THEN TRUE
        ELSE FALSE
    END AS eligible_for_execution

FROM async_service.background_jobs;


-- Identify tasks eligible for another execution attempt.

SELECT
    task_id,
    title,
    retry_count,
    maximum_retries,

    (
        task_status IN ('pending', 'failed')
        AND retry_count < maximum_retries
    ) AS eligible_for_retry

FROM async_service.tasks;


-- ---------------------------------------------------------
-- PERFORMANCE AND FAILURE ANALYSIS
-- ---------------------------------------------------------

-- Detect connection pool pressure.

SELECT
    instance_name,
    waiting_requests,
    active_connections,
    maximum_connections,

    CASE
        WHEN waiting_requests > 0
            THEN 'connection_pressure'

        WHEN active_connections >= maximum_connections
            THEN 'pool_exhausted'

        ELSE 'normal'
    END AS pool_condition

FROM async_service.database_pool_health;


-- Identify slow API operations.

SELECT
    endpoint,
    COUNT(*) AS request_count,
    ROUND(AVG(duration_ms), 2) AS average_ms,
    ROUND(MAX(duration_ms), 2) AS maximum_ms

FROM async_service.api_requests

GROUP BY endpoint

HAVING AVG(duration_ms) > 1000

ORDER BY average_ms DESC;


-- ---------------------------------------------------------
-- TRANSACTIONAL IDEMPOTENCY EXAMPLE
-- ---------------------------------------------------------

BEGIN;

SELECT async_service.create_task(
    'Test idempotent task creation',
    'Repeated requests must not create duplicate tasks.',
    'idempotency-test-001'
) AS task_id;

COMMIT;


-- ---------------------------------------------------------
-- AUDIT RETRIEVAL
-- ---------------------------------------------------------

SELECT
    audit_id,
    operation_name,
    execution_status,
    recorded_at,
    details
FROM async_service.operation_audit
ORDER BY recorded_at DESC
LIMIT 100;
