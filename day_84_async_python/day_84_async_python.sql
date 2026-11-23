-- ============================================================
-- ASYNCHRONOUS JOB PROCESSING DATABASE
-- PostgreSQL 15+
--
-- Models:
--   - Asynchronous job submissions
--   - Job queues
--   - Workers
--   - Job state transitions
--   - Retry policies
--   - Execution attempts
--   - Worker leases
--   - Job dependencies
--   - Event logs
--   - Failure handling
--   - Concurrent queue consumption
--   - Operational reporting
--
-- Concurrency is coordinated through transactions,
-- row-level locks and FOR UPDATE SKIP LOCKED.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS async_engine;

SET search_path TO async_engine, public;


-- ============================================================
-- 1. ENUMERATIONS
-- ============================================================

CREATE TYPE job_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled'
);

CREATE TYPE worker_status AS ENUM (
    'active',
    'inactive'
);

CREATE TYPE execution_event AS ENUM (
    'submitted',
    'started',
    'completed',
    'failed',
    'retried',
    'cancelled',
    'lease_expired'
);


-- ============================================================
-- 2. REPOSITORY-LIKE TENANT AND QUEUE CONFIGURATION
-- ============================================================

CREATE TABLE tenants (
    tenant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE queues (
    queue_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id),
    queue_name VARCHAR(100) NOT NULL,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    default_timeout_seconds INTEGER NOT NULL DEFAULT 60,
    max_concurrency INTEGER NOT NULL DEFAULT 5,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_tenant_queue
        UNIQUE (tenant_id, queue_name),

    CONSTRAINT chk_max_attempts
        CHECK (max_attempts BETWEEN 1 AND 20),

    CONSTRAINT chk_timeout
        CHECK (default_timeout_seconds BETWEEN 1 AND 86400),

    CONSTRAINT chk_concurrency
        CHECK (max_concurrency BETWEEN 1 AND 1000)
);


-- ============================================================
-- 3. WORKERS
-- ============================================================

CREATE TABLE workers (
    worker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id),
    worker_name VARCHAR(100) NOT NULL UNIQUE,
    status worker_status NOT NULL DEFAULT 'active',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ,
    supported_queues TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    CONSTRAINT chk_worker_name
        CHECK (LENGTH(TRIM(worker_name)) > 0)
);

CREATE INDEX idx_workers_tenant_status
    ON workers(tenant_id, status);


-- ============================================================
-- 4. JOBS
-- ============================================================

CREATE TABLE jobs (
    job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id),

    queue_id BIGINT NOT NULL REFERENCES queues(queue_id),

    job_type VARCHAR(100) NOT NULL,

    payload JSONB NOT NULL,

    status job_status NOT NULL DEFAULT 'pending',

    priority INTEGER NOT NULL DEFAULT 5,

    attempts INTEGER NOT NULL DEFAULT 0,

    max_attempts INTEGER NOT NULL,

    timeout_seconds INTEGER NOT NULL,

    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    worker_id BIGINT REFERENCES workers(worker_id),

    lease_expires_at TIMESTAMPTZ,

    result JSONB,

    error_message TEXT,

    version BIGINT NOT NULL DEFAULT 0,

    CONSTRAINT chk_priority
        CHECK (priority BETWEEN 1 AND 10),

    CONSTRAINT chk_attempts
        CHECK (
            attempts >= 0
            AND attempts <= max_attempts
        ),

    CONSTRAINT chk_job_max_attempts
        CHECK (max_attempts BETWEEN 1 AND 20),

    CONSTRAINT chk_job_timeout
        CHECK (timeout_seconds > 0),

    CONSTRAINT chk_job_type
        CHECK (LENGTH(TRIM(job_type)) > 0),

    CONSTRAINT chk_job_lease
        CHECK (
            status = 'running'
            OR (
                worker_id IS NULL
                AND lease_expires_at IS NULL
            )
        )
);


-- ============================================================
-- 5. JOB DEPENDENCIES
-- ============================================================

CREATE TABLE job_dependencies (
    job_id BIGINT NOT NULL REFERENCES jobs(job_id)
        ON DELETE CASCADE,

    depends_on_job_id BIGINT NOT NULL REFERENCES jobs(job_id)
        ON DELETE CASCADE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (job_id, depends_on_job_id),

    CONSTRAINT chk_no_self_dependency
        CHECK (job_id <> depends_on_job_id)
);


-- ============================================================
-- 6. EXECUTION ATTEMPTS
-- ============================================================

CREATE TABLE job_attempts (
    attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    job_id BIGINT NOT NULL REFERENCES jobs(job_id),

    worker_id BIGINT NOT NULL REFERENCES workers(worker_id),

    attempt_number INTEGER NOT NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    finished_at TIMESTAMPTZ,

    success BOOLEAN,

    error_message TEXT,

    duration_ms BIGINT,

    CONSTRAINT uq_job_attempt
        UNIQUE (job_id, attempt_number),

    CONSTRAINT chk_duration
        CHECK (duration_ms IS NULL OR duration_ms >= 0)
);


-- ============================================================
-- 7. EXECUTION EVENT LOG
-- ============================================================

CREATE TABLE job_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    job_id BIGINT NOT NULL REFERENCES jobs(job_id),

    worker_id BIGINT REFERENCES workers(worker_id),

    event_type execution_event NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 8. INDEXES
-- ============================================================

-- Optimizes priority-based queue retrieval.
CREATE INDEX idx_jobs_pending_queue
    ON jobs(queue_id, priority DESC, available_at, created_at)
    WHERE status = 'pending';

-- Optimizes worker lease recovery.
CREATE INDEX idx_jobs_expired_leases
    ON jobs(lease_expires_at)
    WHERE status = 'running';

CREATE INDEX idx_jobs_tenant_status
    ON jobs(tenant_id, status, created_at DESC);

CREATE INDEX idx_job_attempts_job
    ON job_attempts(job_id, attempt_number DESC);

CREATE INDEX idx_job_events_job
    ON job_events(job_id, created_at DESC);

CREATE INDEX idx_job_events_type
    ON job_events(event_type, created_at DESC);

CREATE INDEX idx_job_payload
    ON jobs USING GIN(payload);

CREATE INDEX idx_dependencies_parent
    ON job_dependencies(depends_on_job_id);


-- ============================================================
-- 9. JOB EVENT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION record_job_status_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_event execution_event;
BEGIN

    IF TG_OP = 'INSERT' THEN

        INSERT INTO job_events (
            job_id,
            event_type,
            details
        )
        VALUES (
            NEW.job_id,
            'submitted',
            jsonb_build_object(
                'job_type', NEW.job_type,
                'priority', NEW.priority
            )
        );

        RETURN NEW;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN

        v_event := CASE NEW.status
            WHEN 'running' THEN 'started'::execution_event
            WHEN 'completed' THEN 'completed'::execution_event
            WHEN 'failed' THEN 'failed'::execution_event
            WHEN 'cancelled' THEN 'cancelled'::execution_event
            ELSE NULL
        END;

        IF v_event IS NOT NULL THEN

            INSERT INTO job_events (
                job_id,
                worker_id,
                event_type,
                details
            )
            VALUES (
                NEW.job_id,
                NEW.worker_id,
                v_event,
                jsonb_build_object(
                    'previous_status', OLD.status,
                    'new_status', NEW.status,
                    'attempts', NEW.attempts
                )
            );

        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_job_status_event
AFTER INSERT OR UPDATE OF status
ON jobs
FOR EACH ROW
EXECUTE FUNCTION record_job_status_event();


-- ============================================================
-- 10. VALIDATE JOB STATE TRANSITIONS
-- ============================================================

CREATE OR REPLACE FUNCTION validate_job_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    IF TG_OP = 'UPDATE' THEN

        IF OLD.status IN ('completed', 'cancelled')
           AND NEW.status <> OLD.status THEN

            RAISE EXCEPTION
                'Terminal job state % cannot be changed',
                OLD.status;
        END IF;

        IF OLD.status = 'failed'
           AND NEW.status NOT IN ('failed', 'pending') THEN

            RAISE EXCEPTION
                'Failed jobs can only remain failed or be retried';
        END IF;

        IF OLD.status = 'pending'
           AND NEW.status NOT IN (
               'pending',
               'running',
               'cancelled'
           ) THEN

            RAISE EXCEPTION
                'Invalid pending job transition';
        END IF;

        IF OLD.status = 'running'
           AND NEW.status NOT IN (
               'running',
               'completed',
               'failed',
               'pending',
               'cancelled'
           ) THEN

            RAISE EXCEPTION
                'Invalid running job transition';
        END IF;

        IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION
                'Job version must increment exactly once';
        END IF;

    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_job_transition
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION validate_job_transition();


-- ============================================================
-- 11. VALIDATE TENANT AND QUEUE CONSISTENCY
-- ============================================================

CREATE OR REPLACE FUNCTION validate_job_tenant()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_id BIGINT;
BEGIN

    SELECT tenant_id
    INTO v_tenant_id
    FROM queues
    WHERE queue_id = NEW.queue_id;

    IF v_tenant_id IS NULL
       OR v_tenant_id <> NEW.tenant_id THEN

        RAISE EXCEPTION
            'Job tenant does not match queue tenant';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_job_tenant
BEFORE INSERT OR UPDATE OF tenant_id, queue_id
ON jobs
FOR EACH ROW
EXECUTE FUNCTION validate_job_tenant();


-- ============================================================
-- 12. SUBMIT JOB FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION submit_job(
    p_tenant_id BIGINT,
    p_queue_id BIGINT,
    p_job_type VARCHAR,
    p_payload JSONB,
    p_priority INTEGER DEFAULT 5,
    p_timeout INTEGER DEFAULT 60
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_job_id BIGINT;
    v_max_attempts INTEGER;
BEGIN

    SELECT max_attempts
    INTO v_max_attempts
    FROM queues
    WHERE queue_id = p_queue_id
      AND tenant_id = p_tenant_id
      AND is_enabled = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Queue unavailable or tenant mismatch';
    END IF;

    IF p_payload IS NULL THEN
        RAISE EXCEPTION 'Payload is required';
    END IF;

    IF jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION
            'Job payload must be a JSON object';
    END IF;

    INSERT INTO jobs (
        tenant_id,
        queue_id,
        job_type,
        payload,
        priority,
        max_attempts,
        timeout_seconds
    )
    VALUES (
        p_tenant_id,
        p_queue_id,
        p_job_type,
        p_payload,
        p_priority,
        v_max_attempts,
        p_timeout
    )
    RETURNING job_id INTO v_job_id;

    RETURN v_job_id;
END;
$$;


-- ============================================================
-- 13. DEPENDENCY CYCLE VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_job_dependency()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_cycle BOOLEAN;
    v_tenant_a BIGINT;
    v_tenant_b BIGINT;
BEGIN

    SELECT tenant_id
    INTO v_tenant_a
    FROM jobs
    WHERE job_id = NEW.job_id;

    SELECT tenant_id
    INTO v_tenant_b
    FROM jobs
    WHERE job_id = NEW.depends_on_job_id;

    IF v_tenant_a IS DISTINCT FROM v_tenant_b THEN
        RAISE EXCEPTION
            'Dependencies must belong to the same tenant';
    END IF;

    WITH RECURSIVE dependency_path(job_id) AS (

        SELECT NEW.depends_on_job_id

        UNION

        SELECT d.depends_on_job_id
        FROM job_dependencies d
        JOIN dependency_path p
          ON d.job_id = p.job_id
    )

    SELECT EXISTS (
        SELECT 1
        FROM dependency_path
        WHERE job_id = NEW.job_id
    )
    INTO v_cycle;

    IF v_cycle THEN
        RAISE EXCEPTION
            'Circular job dependency detected';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_job_dependency
BEFORE INSERT ON job_dependencies
FOR EACH ROW
EXECUTE FUNCTION validate_job_dependency();


-- ============================================================
-- 14. CLAIM NEXT ELIGIBLE JOB
-- ============================================================

CREATE OR REPLACE FUNCTION claim_next_job(
    p_worker_id BIGINT,
    p_queue_id BIGINT,
    p_lease_seconds INTEGER DEFAULT 60
)
RETURNS TABLE (
    claimed_job_id BIGINT,
    claimed_job_type VARCHAR,
    claimed_payload JSONB,
    claimed_attempt INTEGER,
    claimed_lease TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_id BIGINT;
    v_job RECORD;
    v_now TIMESTAMPTZ := clock_timestamp();
BEGIN

    IF p_lease_seconds < 1 THEN
        RAISE EXCEPTION
            'Lease duration must be positive';
    END IF;

    SELECT tenant_id
    INTO v_tenant_id
    FROM workers
    WHERE worker_id = p_worker_id
      AND status = 'active';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Worker is not active';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM queues
        WHERE queue_id = p_queue_id
          AND tenant_id = v_tenant_id
          AND is_enabled
    ) THEN
        RAISE EXCEPTION
            'Worker cannot access requested queue';
    END IF;

    UPDATE workers
    SET last_heartbeat = v_now
    WHERE worker_id = p_worker_id;

    SELECT j.*
    INTO v_job
    FROM jobs j
    WHERE j.queue_id = p_queue_id
      AND j.tenant_id = v_tenant_id
      AND j.status = 'pending'
      AND j.available_at <= v_now
      AND j.attempts < j.max_attempts

      AND NOT EXISTS (
          SELECT 1
          FROM job_dependencies d
          JOIN jobs parent
            ON parent.job_id = d.depends_on_job_id
          WHERE d.job_id = j.job_id
            AND parent.status <> 'completed'
      )

    ORDER BY
        j.priority DESC,
        j.created_at ASC,
        j.job_id ASC

    FOR UPDATE OF j SKIP LOCKED

    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE jobs
    SET
        status = 'running',
        attempts = attempts + 1,
        worker_id = p_worker_id,
        started_at = v_now,
        lease_expires_at =
            v_now + make_interval(secs => p_lease_seconds),
        version = version + 1

    WHERE job_id = v_job.job_id;

    INSERT INTO job_attempts (
        job_id,
        worker_id,
        attempt_number
    )
    VALUES (
        v_job.job_id,
        p_worker_id,
        v_job.attempts + 1
    );

    RETURN QUERY
    SELECT
        j.job_id,
        j.job_type,
        j.payload,
        j.attempts,
        j.lease_expires_at
    FROM jobs j
    WHERE j.job_id = v_job.job_id;

END;
$$;


-- ============================================================
-- 15. COMPLETE JOB
-- ============================================================

CREATE OR REPLACE FUNCTION complete_job(
    p_job_id BIGINT,
    p_worker_id BIGINT,
    p_result JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_job jobs%ROWTYPE;
    v_now TIMESTAMPTZ := clock_timestamp();
BEGIN

    SELECT *
    INTO v_job
    FROM jobs
    WHERE job_id = p_job_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Job not found';
    END IF;

    IF v_job.status <> 'running'
       OR v_job.worker_id <> p_worker_id
       OR v_job.lease_expires_at <= v_now THEN

        RAISE EXCEPTION
            'Worker does not hold a valid job lease';
    END IF;

    UPDATE jobs
    SET
        status = 'completed',
        result = p_result,
        completed_at = v_now,
        worker_id = NULL,
        lease_expires_at = NULL,
        error_message = NULL,
        version = version + 1
    WHERE job_id = p_job_id;

    UPDATE job_attempts
    SET
        finished_at = v_now,
        success = TRUE,
        duration_ms =
            GREATEST(
                0,
                FLOOR(
                    EXTRACT(EPOCH FROM (v_now - started_at))
                    * 1000
                )::BIGINT
            )
    WHERE job_id = p_job_id
      AND attempt_number = v_job.attempts;

    RETURN TRUE;
END;
$$;


-- ============================================================
-- 16. FAIL AND RETRY JOB
-- ============================================================

CREATE OR REPLACE FUNCTION fail_job(
    p_job_id BIGINT,
    p_worker_id BIGINT,
    p_error TEXT
)
RETURNS job_status
LANGUAGE plpgsql
AS $$
DECLARE
    v_job jobs%ROWTYPE;
    v_now TIMESTAMPTZ := clock_timestamp();
    v_new_status job_status;
BEGIN

    SELECT *
    INTO v_job
    FROM jobs
    WHERE job_id = p_job_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Job not found';
    END IF;

    IF v_job.status <> 'running'
       OR v_job.worker_id <> p_worker_id
       OR v_job.lease_expires_at <= v_now THEN

        RAISE EXCEPTION
            'Worker does not hold a valid job lease';
    END IF;

    IF v_job.attempts < v_job.max_attempts THEN
        v_new_status := 'pending';
    ELSE
        v_new_status := 'failed';
    END IF;

    UPDATE jobs
    SET
        status = v_new_status,
        error_message = p_error,
        available_at = CASE
            WHEN v_new_status = 'pending'
            THEN v_now + make_interval(
                secs => LEAST(
                    300,
                    2 ^ LEAST(attempts, 8)
                )
            )
            ELSE available_at
        END,
        worker_id = NULL,
        lease_expires_at = NULL,
        version = version + 1
    WHERE job_id = p_job_id;

    UPDATE job_attempts
    SET
        finished_at = v_now,
        success = FALSE,
        error_message = p_error,
        duration_ms =
            GREATEST(
                0,
                FLOOR(
                    EXTRACT(EPOCH FROM (v_now - started_at))
                    * 1000
                )::BIGINT
            )
    WHERE job_id = p_job_id
      AND attempt_number = v_job.attempts;

    IF v_new_status = 'pending' THEN

        INSERT INTO job_events (
            job_id,
            worker_id,
            event_type,
            details
        )
        VALUES (
            p_job_id,
            p_worker_id,
            'retried',
            jsonb_build_object(
                'attempt', v_job.attempts,
                'error', p_error
            )
        );
    END IF;

    RETURN v_new_status;
END;
$$;


-- ============================================================
-- 17. EXPIRED LEASE RECOVERY
-- ============================================================

CREATE OR REPLACE FUNCTION recover_expired_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
    v_now TIMESTAMPTZ := clock_timestamp();
BEGIN

    WITH expired AS (

        SELECT job_id, worker_id, attempts, max_attempts
        FROM jobs
        WHERE status = 'running'
          AND lease_expires_at <= v_now
        FOR UPDATE SKIP LOCKED
    ),

    updated AS (

        UPDATE jobs j
        SET
            status = CASE
                WHEN e.attempts < e.max_attempts
                THEN 'pending'::job_status
                ELSE 'failed'::job_status
            END,

            worker_id = NULL,
            lease_expires_at = NULL,

            error_message = 'Worker lease expired',

            available_at = v_now + INTERVAL '5 seconds',

            version = version + 1

        FROM expired e
        WHERE j.job_id = e.job_id

        RETURNING j.job_id, e.worker_id, e.attempts
    ),

    attempts_closed AS (

        UPDATE job_attempts a
        SET
            finished_at = v_now,
            success = FALSE,
            error_message = 'Worker lease expired'

        FROM updated u

        WHERE a.job_id = u.job_id
          AND a.attempt_number = u.attempts

        RETURNING a.job_id
    )

    INSERT INTO job_events (
        job_id,
        worker_id,
        event_type,
        details
    )
    SELECT
        job_id,
        worker_id,
        'lease_expired',
        jsonb_build_object('attempt', attempts)
    FROM updated;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN v_count;
END;
$$;


-- ============================================================
-- 18. CANCEL JOB
-- ============================================================

CREATE OR REPLACE FUNCTION cancel_job(
    p_job_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_status job_status;
BEGIN

    SELECT status
    INTO v_status
    FROM jobs
    WHERE job_id = p_job_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Job not found';
    END IF;

    IF v_status IN ('completed', 'failed', 'cancelled') THEN
        RETURN FALSE;
    END IF;

    UPDATE jobs
    SET
        status = 'cancelled',
        worker_id = NULL,
        lease_expires_at = NULL,
        completed_at = clock_timestamp(),
        version = version + 1
    WHERE job_id = p_job_id;

    RETURN TRUE;
END;
$$;


-- ============================================================
-- 19. ASYNCHRONOUS QUEUE VIEW
-- ============================================================

CREATE OR REPLACE VIEW queue_overview AS
SELECT
    q.queue_id,
    q.queue_name,
    t.tenant_name,

    COUNT(j.job_id) AS total_jobs,

    COUNT(*) FILTER (
        WHERE j.status = 'pending'
    ) AS pending_jobs,

    COUNT(*) FILTER (
        WHERE j.status = 'running'
    ) AS running_jobs,

    COUNT(*) FILTER (
        WHERE j.status = 'completed'
    ) AS completed_jobs,

    COUNT(*) FILTER (
        WHERE j.status = 'failed'
    ) AS failed_jobs,

    COUNT(*) FILTER (
        WHERE j.status = 'cancelled'
    ) AS cancelled_jobs

FROM queues q

JOIN tenants t
    ON t.tenant_id = q.tenant_id

LEFT JOIN jobs j
    ON j.queue_id = q.queue_id

GROUP BY
    q.queue_id,
    q.queue_name,
    t.tenant_name;


-- ============================================================
-- 20. WORKER PERFORMANCE REPORT
-- ============================================================

CREATE OR REPLACE VIEW worker_performance AS
SELECT
    w.worker_id,
    w.worker_name,

    COUNT(a.attempt_id) AS total_attempts,

    COUNT(*) FILTER (
        WHERE a.success = TRUE
    ) AS successful_attempts,

    COUNT(*) FILTER (
        WHERE a.success = FALSE
    ) AS failed_attempts,

    ROUND(
        AVG(a.duration_ms),
        2
    ) AS average_duration_ms

FROM workers w

LEFT JOIN job_attempts a
    ON a.worker_id = w.worker_id

GROUP BY
    w.worker_id,
    w.worker_name;


-- ============================================================
-- 21. SAMPLE TENANTS AND QUEUES
-- ============================================================

INSERT INTO tenants (tenant_name)
VALUES
    ('Enterprise Operations'),
    ('Research Processing');

INSERT INTO queues (
    tenant_id,
    queue_name,
    max_attempts,
    default_timeout_seconds,
    max_concurrency
)
VALUES
    (1, 'data-processing', 3, 60, 5),
    (1, 'report-generation', 2, 120, 3),
    (2, 'research-analysis', 4, 300, 8);

INSERT INTO workers (
    tenant_id,
    worker_name,
    supported_queues
)
VALUES
    (1, 'worker-enterprise-01',
     ARRAY['data-processing', 'report-generation']),
    (1, 'worker-enterprise-02',
     ARRAY['data-processing']),
    (2, 'worker-research-01',
     ARRAY['research-analysis']);

UPDATE workers
SET last_heartbeat = NOW()
WHERE worker_id IN (1, 2, 3);


-- ============================================================
-- 22. SUBMIT SAMPLE JOBS
-- ============================================================

SELECT submit_job(
    1,
    1,
    'extract_data',
    '{"source":"system_a","records":1000}'::JSONB,
    8,
    60
);

SELECT submit_job(
    1,
    1,
    'validate_data',
    '{"source":"system_b","records":500}'::JSONB,
    7,
    60
);

SELECT submit_job(
    1,
    2,
    'generate_report',
    '{"report":"monthly","format":"pdf"}'::JSONB,
    5,
    120
);

SELECT submit_job(
    1,
    1,
    'transform_data',
    '{"source":"system_c","records":2500}'::JSONB,
    6,
    60
);

SELECT submit_job(
    2,
    3,
    'research_analysis',
    '{"dataset":"clinical","records":5000}'::JSONB,
    9,
    300
);


-- ============================================================
-- 23. DEFINE DEPENDENCIES
-- ============================================================

INSERT INTO job_dependencies (
    job_id,
    depends_on_job_id
)
VALUES
    (3, 1),
    (3, 2);


-- ============================================================
-- 24. CLAIM A JOB
-- ============================================================

-- A worker claims only one eligible job.
-- FOR UPDATE SKIP LOCKED supports multiple consumers.
SELECT *
FROM claim_next_job(1, 1, 60);


-- ============================================================
-- 25. EXECUTION SIMULATION
-- ============================================================

-- The following transaction claims and completes one job
-- atomically for demonstration purposes.

DO $$
DECLARE
    v_claim RECORD;
BEGIN

    SELECT *
    INTO v_claim
    FROM claim_next_job(2, 1, 60);

    IF v_claim.claimed_job_id IS NOT NULL THEN

        PERFORM complete_job(
            v_claim.claimed_job_id,
            2,
            '{"processed":true,"records":1000}'::JSONB
        );

    END IF;

END;
$$;


-- ============================================================
-- 26. ELIGIBILITY REPORT
-- ============================================================

SELECT
    j.job_id,
    j.job_type,
    j.status,
    j.priority,

    NOT EXISTS (
        SELECT 1
        FROM job_dependencies d
        JOIN jobs parent
            ON parent.job_id = d.depends_on_job_id
        WHERE d.job_id = j.job_id
          AND parent.status <> 'completed'
    ) AS dependencies_satisfied,

    (
        j.status = 'pending'
        AND j.available_at <= NOW()
        AND j.attempts < j.max_attempts
    ) AS time_and_attempts_valid

FROM jobs j
ORDER BY j.priority DESC, j.job_id;


-- ============================================================
-- 27. RETRIEVAL AND AGGREGATION
-- ============================================================

SELECT *
FROM queue_overview
ORDER BY tenant_name, queue_name;

SELECT *
FROM worker_performance
ORDER BY total_attempts DESC;

SELECT
    status,
    COUNT(*) AS job_count
FROM jobs
GROUP BY status
ORDER BY status;


-- ============================================================
-- 28. EVENT AUDIT
-- ============================================================

SELECT
    e.event_id,
    e.job_id,
    e.event_type,
    e.worker_id,
    e.details,
    e.created_at
FROM job_events e
ORDER BY e.created_at DESC;


-- ============================================================
-- 29. FAILED JOB INSPECTION
-- ============================================================

SELECT
    job_id,
    job_type,
    attempts,
    max_attempts,
    error_message,
    created_at
FROM jobs
WHERE status = 'failed'
ORDER BY created_at DESC;


-- ============================================================
-- 30. RECOVERY OPERATION
-- ============================================================

-- Reclaims expired work. Execute periodically from a worker
-- maintenance process or scheduled database operation.

SELECT recover_expired_jobs();


-- ============================================================
-- 31. TRANSACTIONAL CANCELLATION
-- ============================================================

BEGIN;

SELECT cancel_job(4);

COMMIT;


-- ============================================================
-- 32. VALIDATION EXAMPLES
-- ============================================================

-- Invalid priority: rejected by CHECK constraint.
-- INSERT INTO jobs (...) VALUES (..., 99, ...);

-- Invalid tenant/queue combination: rejected by trigger.
-- SELECT submit_job(2, 1, 'invalid', '{}'::JSONB);

-- Circular dependency: rejected by dependency trigger.
-- INSERT INTO job_dependencies VALUES (1, 3, NOW());

-- Invalid terminal state transition: rejected by trigger.
-- UPDATE jobs SET status = 'pending', version = version + 1
-- WHERE status = 'completed';

-- Unauthorized worker completion: rejected by lease validation.


-- ============================================================
-- 33. OPERATIONAL MONITORING
-- ============================================================

SELECT
    queue_name,
    total_jobs,
    pending_jobs,
    running_jobs,
    completed_jobs,
    failed_jobs,
    cancelled_jobs,

    ROUND(
        100.0 * completed_jobs /
        NULLIF(total_jobs, 0),
        2
    ) AS completion_percentage

FROM queue_overview;


SELECT
    worker_name,
    total_attempts,
    successful_attempts,
    failed_attempts,
    average_duration_ms,

    ROUND(
        100.0 * successful_attempts /
        NULLIF(total_attempts, 0),
        2
    ) AS success_percentage

FROM worker_performance;


-- ============================================================
-- 34. TRANSACTION SAFETY
-- ============================================================

-- In production, use a dedicated application role.
-- Restrict direct table updates and grant execution of
-- approved queue functions instead.
--
-- Queue claim, lease validation and completion should run
-- within transactions.
--
-- The application should not trust a job ID alone.
-- Worker ownership and lease expiration are checked.
--
-- Use TLS, database authentication, tenant-scoped access,
-- payload validation, least privilege and audit retention.

COMMIT;
