/*
===============================================================================
BACKGROUND TASK MANAGEMENT DATABASE
===============================================================================

PostgreSQL 14+

Domain:
    Asynchronous jobs
    Task queues
    Worker processes
    Scheduling
    Priority management
    Retry policies
    Task dependencies
    Idempotency
    Dead-letter processing
    Execution monitoring

The schema separates:
    Task definition
    Task execution state
    Queue scheduling
    Worker identity
    Retry policy
    Dependency relationships
    Execution attempts
    Operational results

All task state transitions are validated at database level.
===============================================================================
*/

BEGIN;

DROP SCHEMA IF EXISTS background_tasks CASCADE;

CREATE SCHEMA background_tasks;

SET search_path TO background_tasks, public;


-- ============================================================================
-- 1. ENUM TYPES
-- ============================================================================

CREATE TYPE task_status AS ENUM (
    'pending',
    'queued',
    'running',
    'retry_wait',
    'completed',
    'failed',
    'dead_letter',
    'cancelled'
);

CREATE TYPE task_priority AS ENUM (
    'critical',
    'high',
    'normal',
    'low'
);

CREATE TYPE worker_status AS ENUM (
    'online',
    'busy',
    'offline',
    'unhealthy'
);

CREATE TYPE attempt_status AS ENUM (
    'running',
    'succeeded',
    'failed',
    'timed_out',
    'cancelled'
);


-- ============================================================================
-- 2. REPOSITORY AND TENANT-LIKE EXECUTION CONTEXT
-- ============================================================================

CREATE TABLE execution_projects (
    project_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_name VARCHAR(150) NOT NULL UNIQUE,

    description TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- 3. WORKER PROCESSES
-- ============================================================================

CREATE TABLE workers (
    worker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL
        REFERENCES execution_projects(project_id),

    worker_name VARCHAR(150) NOT NULL,

    hostname VARCHAR(255),

    process_id INTEGER,

    status worker_status NOT NULL DEFAULT 'offline',

    supported_task_types TEXT[] NOT NULL DEFAULT '{}',

    max_concurrency INTEGER NOT NULL DEFAULT 1
        CHECK (max_concurrency BETWEEN 1 AND 1000),

    active_tasks INTEGER NOT NULL DEFAULT 0
        CHECK (active_tasks >= 0),

    last_heartbeat TIMESTAMPTZ,

    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(project_id, worker_name)
);


CREATE INDEX idx_workers_project_status
ON workers(project_id, status);


CREATE INDEX idx_workers_heartbeat
ON workers(last_heartbeat)
WHERE status IN ('online', 'busy');


-- ============================================================================
-- 4. RETRY POLICIES
-- ============================================================================

CREATE TABLE retry_policies (
    retry_policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(100) NOT NULL UNIQUE,

    max_attempts INTEGER NOT NULL DEFAULT 3
        CHECK (max_attempts BETWEEN 1 AND 100),

    initial_delay_seconds NUMERIC(12, 3) NOT NULL DEFAULT 1
        CHECK (initial_delay_seconds >= 0),

    max_delay_seconds NUMERIC(12, 3) NOT NULL DEFAULT 300
        CHECK (max_delay_seconds >= 0),

    multiplier NUMERIC(8, 3) NOT NULL DEFAULT 2
        CHECK (multiplier >= 1),

    jitter_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (max_delay_seconds >= initial_delay_seconds)
);


INSERT INTO retry_policies (
    policy_name,
    max_attempts,
    initial_delay_seconds,
    max_delay_seconds,
    multiplier,
    jitter_enabled
)
VALUES
(
    'standard',
    3,
    2,
    60,
    2,
    TRUE
),
(
    'critical',
    5,
    1,
    120,
    2,
    TRUE
),
(
    'single_attempt',
    1,
    0,
    0,
    1,
    FALSE
);


-- ============================================================================
-- 5. BACKGROUND TASKS
-- ============================================================================

CREATE TABLE tasks (
    task_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL
        REFERENCES execution_projects(project_id),

    task_type VARCHAR(100) NOT NULL,

    task_name VARCHAR(200) NOT NULL,

    payload JSONB NOT NULL DEFAULT '{}'::JSONB,

    priority task_priority NOT NULL DEFAULT 'normal',

    status task_status NOT NULL DEFAULT 'pending',

    retry_policy_id BIGINT NOT NULL
        REFERENCES retry_policies(retry_policy_id),

    idempotency_key VARCHAR(255),

    max_runtime_seconds INTEGER NOT NULL DEFAULT 300
        CHECK (max_runtime_seconds BETWEEN 1 AND 86400),

    attempt_count INTEGER NOT NULL DEFAULT 0
        CHECK (attempt_count >= 0),

    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_error TEXT,

    result JSONB,

    assigned_worker_id BIGINT
        REFERENCES workers(worker_id),

    version BIGINT NOT NULL DEFAULT 0,

    UNIQUE(project_id, idempotency_key),

    CHECK (jsonb_typeof(payload) = 'object'),

    CHECK (
        completed_at IS NULL
        OR status IN ('completed', 'failed', 'dead_letter')
    )
);


CREATE INDEX idx_tasks_project_status
ON tasks(project_id, status);


CREATE INDEX idx_tasks_ready
ON tasks(priority, scheduled_at, task_id)
WHERE status IN ('pending', 'queued', 'retry_wait');


CREATE INDEX idx_tasks_assigned_worker
ON tasks(assigned_worker_id)
WHERE assigned_worker_id IS NOT NULL;


CREATE INDEX idx_tasks_created_at
ON tasks(created_at DESC);


CREATE INDEX idx_tasks_payload
ON tasks USING GIN(payload);


-- ============================================================================
-- 6. TASK DEPENDENCIES
-- ============================================================================

CREATE TABLE task_dependencies (
    task_id BIGINT NOT NULL
        REFERENCES tasks(task_id) ON DELETE CASCADE,

    depends_on_task_id BIGINT NOT NULL
        REFERENCES tasks(task_id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY(task_id, depends_on_task_id),

    CHECK (task_id <> depends_on_task_id)
);


CREATE INDEX idx_task_dependencies_parent
ON task_dependencies(depends_on_task_id);


-- ============================================================================
-- 7. TASK EXECUTION ATTEMPTS
-- ============================================================================

CREATE TABLE task_attempts (
    attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    task_id BIGINT NOT NULL
        REFERENCES tasks(task_id),

    worker_id BIGINT
        REFERENCES workers(worker_id),

    attempt_number INTEGER NOT NULL
        CHECK (attempt_number > 0),

    status attempt_status NOT NULL DEFAULT 'running',

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    finished_at TIMESTAMPTZ,

    duration_ms BIGINT
        CHECK (duration_ms IS NULL OR duration_ms >= 0),

    error_message TEXT,

    output_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    UNIQUE(task_id, attempt_number),

    CHECK (
        finished_at IS NULL OR finished_at >= started_at
    )
);


CREATE INDEX idx_attempts_task
ON task_attempts(task_id, attempt_number DESC);


CREATE INDEX idx_attempts_worker
ON task_attempts(worker_id, started_at DESC);


-- ============================================================================
-- 8. DEAD-LETTER QUEUE
-- ============================================================================

CREATE TABLE dead_letter_tasks (
    dead_letter_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    task_id BIGINT NOT NULL UNIQUE
        REFERENCES tasks(task_id),

    failure_reason TEXT NOT NULL,

    original_attempt_count INTEGER NOT NULL,

    moved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    reprocessed_at TIMESTAMPTZ,

    reprocessing_note TEXT
);


CREATE INDEX idx_dead_letter_moved_at
ON dead_letter_tasks(moved_at DESC);


-- ============================================================================
-- 9. STATE TRANSITION AUDIT
-- ============================================================================

CREATE TABLE task_state_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    task_id BIGINT NOT NULL
        REFERENCES tasks(task_id),

    previous_status task_status,

    new_status task_status NOT NULL,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    changed_by TEXT NOT NULL DEFAULT CURRENT_USER,

    reason TEXT
);


CREATE INDEX idx_task_history_task
ON task_state_history(task_id, changed_at DESC);


-- ============================================================================
-- 10. AUTOMATIC UPDATED_AT MANAGEMENT
-- ============================================================================

CREATE FUNCTION update_task_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.version = OLD.version + 1;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_task_timestamp
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION update_task_timestamp();


-- ============================================================================
-- 11. STATE TRANSITION VALIDATION
-- ============================================================================

CREATE FUNCTION validate_task_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.status = 'pending'
            AND NEW.status IN ('queued', 'cancelled'))

        OR

        (OLD.status = 'queued'
            AND NEW.status IN ('running', 'cancelled'))

        OR

        (OLD.status = 'running'
            AND NEW.status IN (
                'completed',
                'retry_wait',
                'failed',
                'dead_letter'
            ))

        OR

        (OLD.status = 'retry_wait'
            AND NEW.status IN (
                'queued',
                'cancelled',
                'dead_letter'
            ))

        OR

        (OLD.status = 'failed'
            AND NEW.status IN ('queued', 'dead_letter'))
    ) THEN
        RAISE EXCEPTION
            'Invalid task transition: % -> %',
            OLD.status,
            NEW.status;
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_validate_task_transition
BEFORE UPDATE OF status ON tasks
FOR EACH ROW
EXECUTE FUNCTION validate_task_transition();


-- ============================================================================
-- 12. TASK STATE AUDIT TRIGGER
-- ============================================================================

CREATE FUNCTION audit_task_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN

        INSERT INTO task_state_history (
            task_id,
            previous_status,
            new_status,
            reason
        )
        VALUES (
            NEW.task_id,
            OLD.status,
            NEW.status,
            COALESCE(NEW.last_error, 'State transition')
        );

    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_audit_task_transition
AFTER UPDATE OF status ON tasks
FOR EACH ROW
EXECUTE FUNCTION audit_task_transition();


-- ============================================================================
-- 13. DEPENDENCY CYCLE PREVENTION
-- ============================================================================

CREATE FUNCTION validate_dependency_cycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    cycle_found BOOLEAN;
BEGIN
    WITH RECURSIVE dependency_tree(task_id, path, cycle) AS (
        SELECT
            NEW.depends_on_task_id,
            ARRAY[NEW.depends_on_task_id]::BIGINT[],
            FALSE

        UNION ALL

        SELECT
            d.depends_on_task_id,
            tree.path || d.depends_on_task_id,
            d.depends_on_task_id = ANY(tree.path)

        FROM dependency_tree tree

        JOIN task_dependencies d
            ON d.task_id = tree.task_id

        WHERE NOT tree.cycle
    )

    SELECT EXISTS (
        SELECT 1
        FROM dependency_tree
        WHERE task_id = NEW.task_id
    )
    INTO cycle_found;

    IF cycle_found THEN
        RAISE EXCEPTION
            'Task dependency cycle detected for task %',
            NEW.task_id;
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_dependency_cycle
BEFORE INSERT OR UPDATE ON task_dependencies
FOR EACH ROW
EXECUTE FUNCTION validate_dependency_cycle();


-- ============================================================================
-- 14. WORKER CAPACITY VALIDATION
-- ============================================================================

CREATE FUNCTION validate_worker_capacity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    current_worker workers%ROWTYPE;
BEGIN
    IF NEW.assigned_worker_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT *
    INTO current_worker
    FROM workers
    WHERE worker_id = NEW.assigned_worker_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Worker does not exist.';
    END IF;

    IF current_worker.status NOT IN ('online', 'busy') THEN
        RAISE EXCEPTION 'Worker is not available.';
    END IF;

    IF current_worker.active_tasks >= current_worker.max_concurrency THEN
        RAISE EXCEPTION 'Worker concurrency limit reached.';
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_worker_capacity
BEFORE INSERT OR UPDATE OF assigned_worker_id ON tasks
FOR EACH ROW
WHEN (NEW.assigned_worker_id IS NOT NULL)
EXECUTE FUNCTION validate_worker_capacity();


-- ============================================================================
-- 15. PROJECT AND SAMPLE WORKERS
-- ============================================================================

INSERT INTO execution_projects (
    project_name,
    description
)
VALUES
(
    'Operations Reporting',
    'Scheduled reporting and notification processing.'
),
(
    'Data Processing',
    'Asynchronous data transformation workloads.'
);


INSERT INTO workers (
    project_id,
    worker_name,
    hostname,
    process_id,
    status,
    supported_task_types,
    max_concurrency,
    last_heartbeat
)
VALUES
(
    1,
    'report-worker-01',
    'worker-node-01',
    1001,
    'online',
    ARRAY['report', 'export'],
    5,
    NOW()
),
(
    1,
    'notification-worker-01',
    'worker-node-02',
    1002,
    'online',
    ARRAY['notification'],
    10,
    NOW()
),
(
    2,
    'data-worker-01',
    'worker-node-03',
    1003,
    'busy',
    ARRAY['transform', 'validation'],
    4,
    NOW()
);


-- ============================================================================
-- 16. SAMPLE TASKS
-- ============================================================================

INSERT INTO tasks (
    project_id,
    task_type,
    task_name,
    payload,
    priority,
    status,
    retry_policy_id,
    idempotency_key,
    scheduled_at
)
VALUES
(
    1,
    'report',
    'Monthly Operations Report',
    '{"report_type":"monthly","month":"2026-11"}',
    'high',
    'pending',
    1,
    'monthly-report-2026-11',
    NOW()
),
(
    1,
    'notification',
    'Send Operations Notification',
    '{"recipient":"operations@example.com"}',
    'normal',
    'pending',
    1,
    'operations-notification-2026-11',
    NOW()
),
(
    1,
    'export',
    'Historical Data Export',
    '{"format":"csv","records":50000}',
    'low',
    'pending',
    1,
    NULL,
    NOW() + INTERVAL '1 hour'
),
(
    2,
    'transform',
    'Customer Data Transformation',
    '{"records":100000,"format":"parquet"}',
    'critical',
    'pending',
    2,
    NULL,
    NOW()
),
(
    2,
    'validation',
    'Failed Validation Task',
    '{"dataset":"invalid-source"}',
    'normal',
    'dead_letter',
    3,
    NULL,
    NOW()
);


-- The notification depends on the report.
INSERT INTO task_dependencies (
    task_id,
    depends_on_task_id
)
VALUES (2, 1);


-- ============================================================================
-- 17. SAMPLE EXECUTION HISTORY
-- ============================================================================

INSERT INTO task_attempts (
    task_id,
    worker_id,
    attempt_number,
    status,
    started_at,
    finished_at,
    duration_ms,
    output_metadata
)
VALUES
(
    1,
    1,
    1,
    'succeeded',
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '9 minutes 59 seconds',
    1000,
    '{"records_processed":2500}'
),
(
    5,
    3,
    1,
    'failed',
    NOW() - INTERVAL '20 minutes',
    NOW() - INTERVAL '19 minutes',
    60000,
    '{"error_category":"validation"}'
);


INSERT INTO dead_letter_tasks (
    task_id,
    failure_reason,
    original_attempt_count
)
VALUES (
    5,
    'Permanent dataset validation failure.',
    1
);


-- ============================================================================
-- 18. ELIGIBILITY DETERMINATION
-- ============================================================================

CREATE FUNCTION task_is_eligible(p_task_id BIGINT)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    target_task tasks%ROWTYPE;
    all_dependencies_completed BOOLEAN;
BEGIN
    SELECT *
    INTO target_task
    FROM tasks
    WHERE task_id = p_task_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF target_task.status NOT IN ('pending', 'retry_wait') THEN
        RETURN FALSE;
    END IF;

    IF target_task.scheduled_at > NOW() THEN
        RETURN FALSE;
    END IF;

    IF target_task.attempt_count >= (
        SELECT max_attempts
        FROM retry_policies
        WHERE retry_policy_id = target_task.retry_policy_id
    ) THEN
        RETURN FALSE;
    END IF;

    SELECT NOT EXISTS (
        SELECT 1
        FROM task_dependencies d
        JOIN tasks dependency
            ON dependency.task_id = d.depends_on_task_id
        WHERE d.task_id = p_task_id
          AND dependency.status <> 'completed'
    )
    INTO all_dependencies_completed;

    RETURN all_dependencies_completed;
END;
$$;


-- ============================================================================
-- 19. ATOMIC TASK CLAIMING
-- ============================================================================

CREATE FUNCTION claim_next_task(
    p_project_id BIGINT,
    p_worker_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_task_id BIGINT;
    worker_record workers%ROWTYPE;
BEGIN
    SELECT *
    INTO worker_record
    FROM workers
    WHERE worker_id = p_worker_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Worker does not exist.';
    END IF;

    IF worker_record.status NOT IN ('online', 'busy') THEN
        RETURN NULL;
    END IF;

    IF worker_record.active_tasks >= worker_record.max_concurrency THEN
        RETURN NULL;
    END IF;

    SELECT t.task_id
    INTO selected_task_id
    FROM tasks t

    WHERE t.project_id = p_project_id
      AND t.status IN ('pending', 'queued', 'retry_wait')
      AND t.scheduled_at <= NOW()

      AND task_is_eligible(t.task_id)

      AND (
          cardinality(worker_record.supported_task_types) = 0
          OR t.task_type = ANY(worker_record.supported_task_types)
      )

    ORDER BY
        CASE t.priority
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'normal' THEN 3
            WHEN 'low' THEN 4
        END,
        t.scheduled_at,
        t.task_id

    FOR UPDATE OF t SKIP LOCKED

    LIMIT 1;

    IF selected_task_id IS NULL THEN
        RETURN NULL;
    END IF;

    UPDATE tasks
    SET
        status = 'queued',
        assigned_worker_id = p_worker_id
    WHERE task_id = selected_task_id
      AND status IN ('pending', 'retry_wait');

    UPDATE tasks
    SET
        status = 'running',
        attempt_count = attempt_count + 1,
        started_at = NOW()
    WHERE task_id = selected_task_id;

    UPDATE workers
    SET
        active_tasks = active_tasks + 1,
        status = 'busy',
        last_heartbeat = NOW()
    WHERE worker_id = p_worker_id;

    INSERT INTO task_attempts (
        task_id,
        worker_id,
        attempt_number,
        status
    )
    SELECT
        task_id,
        p_worker_id,
        attempt_count,
        'running'
    FROM tasks
    WHERE task_id = selected_task_id;

    RETURN selected_task_id;
END;
$$;


-- ============================================================================
-- 20. TASK COMPLETION FUNCTION
-- ============================================================================

CREATE FUNCTION complete_task(
    p_task_id BIGINT,
    p_result JSONB
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    assigned_worker BIGINT;
BEGIN
    UPDATE tasks
    SET
        status = 'completed',
        result = p_result,
        completed_at = NOW(),
        last_error = NULL
    WHERE task_id = p_task_id
      AND status = 'running'

    RETURNING assigned_worker_id INTO assigned_worker;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Task is not running.';
    END IF;

    UPDATE task_attempts
    SET
        status = 'succeeded',
        finished_at = NOW(),
        duration_ms = (
            EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000
        )::BIGINT,
        output_metadata = p_result
    WHERE task_id = p_task_id
      AND status = 'running';

    UPDATE workers
    SET
        active_tasks = GREATEST(active_tasks - 1, 0),
        status = CASE
            WHEN active_tasks <= 1 THEN 'online'::worker_status
            ELSE 'busy'::worker_status
        END,
        last_heartbeat = NOW()
    WHERE worker_id = assigned_worker;
END;
$$;


-- ============================================================================
-- 21. TASK FAILURE AND RETRY FUNCTION
-- ============================================================================

CREATE FUNCTION fail_task(
    p_task_id BIGINT,
    p_error TEXT,
    p_permanent BOOLEAN DEFAULT FALSE
)
RETURNS task_status
LANGUAGE plpgsql
AS $$
DECLARE
    current_task tasks%ROWTYPE;
    policy retry_policies%ROWTYPE;
    next_status task_status;
    assigned_worker BIGINT;
    delay_seconds NUMERIC;
BEGIN
    SELECT *
    INTO current_task
    FROM tasks
    WHERE task_id = p_task_id
    FOR UPDATE;

    IF NOT FOUND OR current_task.status <> 'running' THEN
        RAISE EXCEPTION 'Task is not running.';
    END IF;

    SELECT *
    INTO policy
    FROM retry_policies
    WHERE retry_policy_id = current_task.retry_policy_id;

    assigned_worker := current_task.assigned_worker_id;

    IF p_permanent OR current_task.attempt_count >= policy.max_attempts THEN

        next_status := 'dead_letter';

        INSERT INTO dead_letter_tasks (
            task_id,
            failure_reason,
            original_attempt_count
        )
        VALUES (
            p_task_id,
            COALESCE(p_error, 'Unknown failure'),
            current_task.attempt_count
        )
        ON CONFLICT (task_id)
        DO UPDATE SET
            failure_reason = EXCLUDED.failure_reason,
            original_attempt_count = EXCLUDED.original_attempt_count,
            moved_at = NOW();

    ELSE

        next_status := 'retry_wait';

        delay_seconds := LEAST(
            policy.initial_delay_seconds *
            POWER(
                policy.multiplier,
                current_task.attempt_count - 1
            ),
            policy.max_delay_seconds
        );

        IF policy.jitter_enabled THEN
            delay_seconds := delay_seconds *
                (0.8 + random() * 0.4);
        END IF;

    END IF;

    UPDATE tasks
    SET
        status = next_status,
        last_error = p_error,
        scheduled_at = CASE
            WHEN next_status = 'retry_wait'
                THEN NOW() + make_interval(
                    secs => delay_seconds::DOUBLE PRECISION
                )
            ELSE scheduled_at
        END,
        completed_at = CASE
            WHEN next_status = 'dead_letter' THEN NOW()
            ELSE NULL
        END
    WHERE task_id = p_task_id;

    UPDATE task_attempts
    SET
        status = 'failed',
        finished_at = NOW(),
        duration_ms = (
            EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000
        )::BIGINT,
        error_message = p_error
    WHERE task_id = p_task_id
      AND status = 'running';

    UPDATE workers
    SET
        active_tasks = GREATEST(active_tasks - 1, 0),
        status = CASE
            WHEN active_tasks <= 1 THEN 'online'::worker_status
            ELSE 'busy'::worker_status
        END,
        last_heartbeat = NOW()
    WHERE worker_id = assigned_worker;

    RETURN next_status;
END;
$$;


-- ============================================================================
-- 22. TASK PROCESSING PROCEDURE
-- ============================================================================

CREATE PROCEDURE process_project_queue(
    p_project_id BIGINT,
    p_worker_id BIGINT,
    p_batch_size INTEGER DEFAULT 10
)
LANGUAGE plpgsql
AS $$
DECLARE
    claimed_task BIGINT;
    processed_count INTEGER := 0;
BEGIN
    IF p_batch_size < 1 OR p_batch_size > 1000 THEN
        RAISE EXCEPTION 'Invalid batch size.';
    END IF;

    WHILE processed_count < p_batch_size LOOP

        claimed_task := claim_next_task(
            p_project_id,
            p_worker_id
        );

        EXIT WHEN claimed_task IS NULL;

        -- The claim is persisted as RUNNING.
        -- Actual task execution occurs in an external worker process.
        processed_count := processed_count + 1;

        EXIT;
    END LOOP;

    RAISE NOTICE 'Claimed tasks: %', processed_count;
END;
$$;


-- ============================================================================
-- 23. TASK QUEUE VIEW
-- ============================================================================

CREATE VIEW ready_task_queue AS
SELECT
    t.task_id,
    t.project_id,
    p.project_name,
    t.task_type,
    t.task_name,
    t.priority,
    t.status,
    t.attempt_count,
    rp.max_attempts,
    t.scheduled_at,
    t.created_at,
    t.idempotency_key

FROM tasks t

JOIN execution_projects p
    ON p.project_id = t.project_id

JOIN retry_policies rp
    ON rp.retry_policy_id = t.retry_policy_id

WHERE t.status IN ('pending', 'queued', 'retry_wait')
  AND t.scheduled_at <= NOW()
  AND task_is_eligible(t.task_id);


-- ============================================================================
-- 24. WORKER UTILIZATION VIEW
-- ============================================================================

CREATE VIEW worker_utilization AS
SELECT
    w.worker_id,
    w.worker_name,
    w.hostname,
    w.status,
    w.max_concurrency,
    w.active_tasks,

    ROUND(
        100.0 * w.active_tasks /
        NULLIF(w.max_concurrency, 0),
        2
    ) AS utilization_percentage,

    w.last_heartbeat

FROM workers w;


-- ============================================================================
-- 25. TASK PERFORMANCE REPORT
-- ============================================================================

CREATE VIEW task_performance_report AS
SELECT
    t.project_id,
    p.project_name,
    t.task_type,

    COUNT(*) AS total_tasks,

    COUNT(*) FILTER (
        WHERE t.status = 'completed'
    ) AS completed_tasks,

    COUNT(*) FILTER (
        WHERE t.status = 'failed'
    ) AS failed_tasks,

    COUNT(*) FILTER (
        WHERE t.status = 'dead_letter'
    ) AS dead_letter_tasks,

    COUNT(*) FILTER (
        WHERE t.status = 'running'
    ) AS running_tasks,

    ROUND(
        AVG(a.duration_ms),
        2
    ) AS average_execution_ms,

    ROUND(
        MAX(a.duration_ms),
        2
    ) AS maximum_execution_ms

FROM tasks t

JOIN execution_projects p
    ON p.project_id = t.project_id

LEFT JOIN task_attempts a
    ON a.task_id = t.task_id

GROUP BY
    t.project_id,
    p.project_name,
    t.task_type;


-- ============================================================================
-- 26. VALIDATION QUERIES
-- ============================================================================

-- Tasks with exhausted retry limits.
SELECT
    t.task_id,
    t.task_name,
    t.attempt_count,
    rp.max_attempts
FROM tasks t
JOIN retry_policies rp
    ON rp.retry_policy_id = t.retry_policy_id
WHERE t.attempt_count >= rp.max_attempts;


-- Tasks blocked by incomplete dependencies.
SELECT
    t.task_id,
    t.task_name,
    dependency.task_id AS blocked_by_task,
    dependency.status AS dependency_status
FROM task_dependencies d
JOIN tasks t
    ON t.task_id = d.task_id
JOIN tasks dependency
    ON dependency.task_id = d.depends_on_task_id
WHERE dependency.status <> 'completed';


-- Invalid or missing worker heartbeats.
SELECT
    worker_id,
    worker_name,
    last_heartbeat
FROM workers
WHERE last_heartbeat IS NULL
   OR last_heartbeat < NOW() - INTERVAL '5 minutes';


-- ============================================================================
-- 27. ELIGIBILITY REPORT
-- ============================================================================

SELECT
    task_id,
    task_name,
    status,
    task_is_eligible(task_id) AS eligible_for_execution
FROM tasks
ORDER BY task_id;


-- ============================================================================
-- 28. AGGREGATION REPORT
-- ============================================================================

SELECT
    project_id,
    status,
    COUNT(*) AS task_count,
    AVG(attempt_count) AS average_attempts
FROM tasks
GROUP BY project_id, status
ORDER BY project_id, status;


-- ============================================================================
-- 29. DEAD-LETTER REPORT
-- ============================================================================

SELECT
    d.dead_letter_id,
    t.task_name,
    t.task_type,
    d.failure_reason,
    d.original_attempt_count,
    d.moved_at
FROM dead_letter_tasks d
JOIN tasks t
    ON t.task_id = d.task_id
ORDER BY d.moved_at DESC;


-- ============================================================================
-- 30. TRANSACTIONAL WORKFLOW DEMONSTRATION
-- ============================================================================

-- Claim a task using row locking and atomic state updates.
-- This demonstration is rolled back so sample data remains unchanged.

SAVEPOINT before_claim_demo;

DO $$
DECLARE
    claimed_id BIGINT;
BEGIN
    claimed_id := claim_next_task(1, 1);

    RAISE NOTICE 'Claimed task: %', claimed_id;

    IF claimed_id IS NOT NULL THEN
        PERFORM complete_task(
            claimed_id,
            '{"records_processed":2500,"status":"success"}'::JSONB
        );
    END IF;
END;
$$;

ROLLBACK TO SAVEPOINT before_claim_demo;


-- ============================================================================
-- 31. REPORTING AND RETRIEVAL
-- ============================================================================

SELECT *
FROM ready_task_queue
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'normal' THEN 3
        WHEN 'low' THEN 4
    END,
    scheduled_at;


SELECT *
FROM worker_utilization
ORDER BY utilization_percentage DESC NULLS LAST;


SELECT *
FROM task_performance_report
ORDER BY project_id, task_type;


SELECT
    task_id,
    previous_status,
    new_status,
    changed_at,
    changed_by,
    reason
FROM task_state_history
ORDER BY changed_at DESC;


-- ============================================================================
-- 32. COMMIT
-- ============================================================================

COMMIT;


/*
===============================================================================
OPERATIONAL NOTES
===============================================================================

1. Task creation:
   Insert a task into tasks. Use an idempotency key to prevent duplicate
   submissions within a project.

2. Scheduling:
   scheduled_at controls when a task becomes eligible for execution.

3. Dependencies:
   task_dependencies prevents execution until all parent tasks complete.

4. Queue claiming:
   claim_next_task uses FOR UPDATE SKIP LOCKED to support concurrent workers.

5. Worker execution:
   A worker claims a task, executes its business logic outside the database,
   and calls complete_task or fail_task.

6. Retries:
   fail_task applies the configured exponential backoff policy.

7. Dead-letter processing:
   Exhausted or permanently failed tasks are recorded in dead_letter_tasks.

8. Observability:
   task_attempts and task_state_history retain execution and transition history.

9. Security:
   Application roles should receive only the permissions required for their
   operations. Workers should not receive unrestricted DDL privileges.

10. Production:
    Worker heartbeats, task leases, stale-task recovery, outbox delivery,
    and external exactly-once effects require additional operational controls.

11. Performance:
    SKIP LOCKED, partial indexes, bounded payloads, and targeted indexes
    reduce queue contention and unnecessary scanning.
===============================================================================
*/
