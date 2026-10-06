-- PostgreSQL Advanced Fundamentals
-- PostgreSQL 15+ compatible SQL
--
-- Demonstrates:
--   schemas
--   sequences
--   UUIDs
--   enums
--   JSONB
--   arrays
--   extensions
--   constraints
--   indexes
--   generated database values
--   transactions
--   CTEs
--   JSONB containment and transformation
--   array membership and expansion
--   PostgreSQL catalog introspection
--
-- The script intentionally creates a dedicated schema so the laboratory
-- objects do not interfere with unrelated application tables.

BEGIN;

DROP SCHEMA IF EXISTS pg_advanced_fundamentals CASCADE;

CREATE SCHEMA pg_advanced_fundamentals;

COMMENT ON SCHEMA pg_advanced_fundamentals IS
    'Laboratory for advanced PostgreSQL fundamentals';

COMMIT;

-- pgcrypto is a PostgreSQL extension. The database administrator or the
-- executing role must have permission to install extensions.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

CREATE TYPE pg_advanced_fundamentals.environment_type AS ENUM (
    'development',
    'staging',
    'production'
);

CREATE TYPE pg_advanced_fundamentals.deployment_status AS ENUM (
    'planned',
    'running',
    'succeeded',
    'failed',
    'cancelled'
);

CREATE TYPE pg_advanced_fundamentals.release_channel AS ENUM (
    'internal',
    'beta',
    'stable'
);

-- Sequences are independent database objects. They are useful when a
-- monotonically increasing numeric value is required. They should not be
-- confused with UUID identity values.
CREATE SEQUENCE pg_advanced_fundamentals.application_number_seq
    START WITH 10000
    INCREMENT BY 1
    MINVALUE 10000
    CACHE 20;

CREATE TABLE pg_advanced_fundamentals.applications (
    application_id UUID
        PRIMARY KEY
        DEFAULT gen_random_uuid(),

    application_number BIGINT
        NOT NULL
        DEFAULT nextval(
            'pg_advanced_fundamentals.application_number_seq'
        ),

    application_name TEXT
        NOT NULL,

    owner_email TEXT
        NOT NULL,

    environment pg_advanced_fundamentals.environment_type
        NOT NULL,

    release_channel pg_advanced_fundamentals.release_channel
        NOT NULL
        DEFAULT 'internal',

    supported_regions TEXT[]
        NOT NULL
        DEFAULT '{}',

    enabled_features TEXT[]
        NOT NULL
        DEFAULT '{}',

    configuration JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    CONSTRAINT applications_name_unique
        UNIQUE (application_name),

    CONSTRAINT applications_number_unique
        UNIQUE (application_number),

    CONSTRAINT applications_owner_email_check
        CHECK (
            position('@' IN owner_email) > 1
        ),

    CONSTRAINT applications_regions_cardinality_check
        CHECK (
            cardinality(supported_regions) <= 20
        ),

    CONSTRAINT applications_features_cardinality_check
        CHECK (
            cardinality(enabled_features) <= 100
        ),

    CONSTRAINT applications_configuration_object_check
        CHECK (
            jsonb_typeof(configuration) = 'object'
        )
);

CREATE TABLE pg_advanced_fundamentals.deployments (
    deployment_id UUID
        PRIMARY KEY
        DEFAULT gen_random_uuid(),

    application_id UUID
        NOT NULL
        REFERENCES pg_advanced_fundamentals.applications(application_id)
        ON DELETE CASCADE,

    status pg_advanced_fundamentals.deployment_status
        NOT NULL
        DEFAULT 'planned',

    requested_by TEXT
        NOT NULL,

    target_regions TEXT[]
        NOT NULL
        DEFAULT '{}',

    tags TEXT[]
        NOT NULL
        DEFAULT '{}',

    metadata JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    requested_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    CONSTRAINT deployments_metadata_object_check
        CHECK (
            jsonb_typeof(metadata) = 'object'
        ),

    CONSTRAINT deployments_completed_after_started_check
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE TABLE pg_advanced_fundamentals.release_events (
    event_id UUID
        PRIMARY KEY
        DEFAULT gen_random_uuid(),

    application_id UUID
        NOT NULL
        REFERENCES pg_advanced_fundamentals.applications(application_id)
        ON DELETE CASCADE,

    event_name TEXT
        NOT NULL,

    event_payload JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    event_tags TEXT[]
        NOT NULL
        DEFAULT '{}',

    occurred_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    CONSTRAINT release_events_payload_object_check
        CHECK (
            jsonb_typeof(event_payload) = 'object'
        )
);

-- GIN indexes are appropriate for containment and membership searches on
-- JSONB and array columns.
CREATE INDEX applications_configuration_gin_idx
    ON pg_advanced_fundamentals.applications
    USING GIN (configuration);

CREATE INDEX applications_regions_gin_idx
    ON pg_advanced_fundamentals.applications
    USING GIN (supported_regions);

CREATE INDEX applications_features_gin_idx
    ON pg_advanced_fundamentals.applications
    USING GIN (enabled_features);

CREATE INDEX deployments_metadata_gin_idx
    ON pg_advanced_fundamentals.deployments
    USING GIN (metadata);

CREATE INDEX deployments_target_regions_gin_idx
    ON pg_advanced_fundamentals.deployments
    USING GIN (target_regions);

CREATE INDEX release_events_payload_gin_idx
    ON pg_advanced_fundamentals.release_events
    USING GIN (event_payload);

CREATE INDEX deployments_application_id_idx
    ON pg_advanced_fundamentals.deployments(application_id);

CREATE INDEX release_events_application_id_idx
    ON pg_advanced_fundamentals.release_events(application_id);

COMMENT ON COLUMN pg_advanced_fundamentals.applications.application_id IS
    'UUID identity generated by pgcrypto';

COMMENT ON COLUMN pg_advanced_fundamentals.applications.application_number IS
    'Sequence-backed numeric identifier suitable for human-facing references';

COMMIT;

-- UUIDs are opaque identifiers and do not expose row count information.
-- The extension function is executed by PostgreSQL rather than the client.
INSERT INTO pg_advanced_fundamentals.applications (
    application_name,
    owner_email,
    environment,
    release_channel,
    supported_regions,
    enabled_features,
    configuration
)
VALUES
(
    'market-risk-engine',
    'platform@example.com',
    'production',
    'stable',
    ARRAY['ap-south-1', 'eu-west-1'],
    ARRAY['risk', 'alerts', 'audit'],
    jsonb_build_object(
        'runtime', 'python',
        'replicas', 6,
        'autoscaling', true,
        'limits', jsonb_build_object(
            'requests_per_minute', 2500,
            'max_position_count', 7500
        ),
        'observability', jsonb_build_object(
            'metrics', true,
            'tracing', true
        )
    )
),
(
    'research-notebook-service',
    'research@example.com',
    'development',
    'beta',
    ARRAY['ap-south-1'],
    ARRAY['notebooks', 'datasets'],
    jsonb_build_object(
        'runtime', 'jupyter',
        'replicas', 1,
        'autoscaling', false,
        'limits', jsonb_build_object(
            'requests_per_minute', 100
        )
    )
),
(
    'release-control-plane',
    'release@example.com',
    'staging',
    'beta',
    ARRAY['ap-south-1', 'eu-west-1'],
    ARRAY['deployments', 'audit', 'approvals'],
    jsonb_build_object(
        'runtime', 'java',
        'replicas', 3,
        'autoscaling', true,
        'limits', jsonb_build_object(
            'requests_per_minute', 1000
        )
    )
);

-- A sequence value can be consumed independently from a UUID identity.
SELECT
    application_id,
    application_number,
    application_name,
    environment,
    release_channel
FROM pg_advanced_fundamentals.applications
ORDER BY application_number;

-- PostgreSQL enums expose a controlled vocabulary and preserve enum ordering.
SELECT
    enumtypid::regtype AS enum_type,
    enumlabel,
    enumsortorder
FROM pg_enum
WHERE enumtypid IN (
    'pg_advanced_fundamentals.environment_type'::regtype,
    'pg_advanced_fundamentals.deployment_status'::regtype,
    'pg_advanced_fundamentals.release_channel'::regtype
)
ORDER BY enumtypid::regtype::text, enumsortorder;

-- Array membership uses PostgreSQL's ANY operator.
SELECT
    application_name,
    supported_regions
FROM pg_advanced_fundamentals.applications
WHERE 'ap-south-1' = ANY(supported_regions);

-- Array containment tests whether one array contains every requested value.
SELECT
    application_name,
    enabled_features
FROM pg_advanced_fundamentals.applications
WHERE enabled_features @> ARRAY['audit']::text[];

-- Arrays can be expanded into rows with unnest.
SELECT
    application_name,
    region
FROM pg_advanced_fundamentals.applications
CROSS JOIN LATERAL unnest(supported_regions) AS region
ORDER BY application_name, region;

-- JSONB scalar extraction returns text with ->>.
SELECT
    application_name,
    configuration ->> 'runtime' AS runtime,
    configuration ->> 'replicas' AS replicas
FROM pg_advanced_fundamentals.applications
ORDER BY application_name;

-- -> returns JSONB, which is useful when the selected value remains a
-- structured JSON document.
SELECT
    application_name,
    configuration -> 'limits' AS limits
FROM pg_advanced_fundamentals.applications
ORDER BY application_name;

-- #>> traverses a nested JSONB path and returns text.
SELECT
    application_name,
    configuration #>> '{limits,requests_per_minute}'
        AS request_limit
FROM pg_advanced_fundamentals.applications
ORDER BY application_name;

-- @> performs JSONB containment. This is one of the important operations
-- supported efficiently by a suitable GIN index.
SELECT
    application_name,
    configuration
FROM pg_advanced_fundamentals.applications
WHERE configuration @> '{"observability": {"metrics": true}}'::jsonb;

-- ? checks whether a top-level JSONB key exists.
SELECT
    application_name
FROM pg_advanced_fundamentals.applications
WHERE configuration ? 'autoscaling';

-- jsonb_array_elements_text converts a JSON array into a row set.
SELECT
    application_name,
    feature
FROM pg_advanced_fundamentals.applications
CROSS JOIN LATERAL jsonb_array_elements_text(
    configuration -> 'features'
) AS feature
WHERE configuration ? 'features'
ORDER BY application_name, feature;

-- jsonb_set updates one nested JSONB path without reconstructing the entire
-- document in application code.
UPDATE pg_advanced_fundamentals.applications
SET configuration = jsonb_set(
    configuration,
    '{limits,max_position_count}',
    '10000'::jsonb,
    true
)
WHERE application_name = 'market-risk-engine';

SELECT
    application_name,
    configuration -> 'limits' AS updated_limits
FROM pg_advanced_fundamentals.applications
WHERE application_name = 'market-risk-engine';

-- Insert deployment rows using a foreign-key relationship to applications.
INSERT INTO pg_advanced_fundamentals.deployments (
    application_id,
    status,
    requested_by,
    target_regions,
    tags,
    metadata,
    started_at,
    completed_at
)
SELECT
    application_id,
    'succeeded',
    'release-bot',
    ARRAY['ap-south-1'],
    ARRAY['production', 'automated'],
    jsonb_build_object(
        'commit_sha', 'abc123def456',
        'pipeline', 'production-release',
        'artifact', jsonb_build_object(
            'name', application_name,
            'version', '2026.10.06'
        )
    ),
    now() - interval '20 minutes',
    now() - interval '5 minutes'
FROM pg_advanced_fundamentals.applications
WHERE application_name = 'market-risk-engine';

INSERT INTO pg_advanced_fundamentals.deployments (
    application_id,
    status,
    requested_by,
    target_regions,
    tags,
    metadata
)
SELECT
    application_id,
    'planned',
    'researcher',
    ARRAY['ap-south-1'],
    ARRAY['development', 'manual'],
    jsonb_build_object(
        'commit_sha', 'fed987654321',
        'pipeline', 'development-release'
    )
FROM pg_advanced_fundamentals.applications
WHERE application_name = 'research-notebook-service';

-- Release events demonstrate an event-style JSONB payload alongside typed
-- relational columns.
INSERT INTO pg_advanced_fundamentals.release_events (
    application_id,
    event_name,
    event_payload,
    event_tags
)
SELECT
    application_id,
    'deployment.completed',
    jsonb_build_object(
        'status', 'succeeded',
        'version', '2026.10.06',
        'duration_seconds', 900,
        'verification', jsonb_build_object(
            'smoke_tests', true,
            'security_scan', true
        )
    ),
    ARRAY['deployment', 'verification', 'audit']
FROM pg_advanced_fundamentals.applications
WHERE application_name = 'market-risk-engine';

-- Transactional workflow: the deployment record and application configuration
-- change either commit together or roll back together.
BEGIN;

WITH target_application AS (
    SELECT application_id
    FROM pg_advanced_fundamentals.applications
    WHERE application_name = 'release-control-plane'
)
INSERT INTO pg_advanced_fundamentals.deployments (
    application_id,
    status,
    requested_by,
    target_regions,
    tags,
    metadata,
    started_at,
    completed_at
)
SELECT
    application_id,
    'succeeded',
    'release-bot',
    ARRAY['ap-south-1', 'eu-west-1'],
    ARRAY['staging', 'automated'],
    jsonb_build_object(
        'commit_sha', '123456789abc',
        'pipeline', 'staging-release'
    ),
    now() - interval '8 minutes',
    now() - interval '2 minutes'
FROM target_application;

UPDATE pg_advanced_fundamentals.applications
SET configuration = jsonb_set(
    configuration,
    '{last_deployment}',
    jsonb_build_object(
        'status', 'succeeded',
        'source', 'release-bot',
        'at', now()
    ),
    true
)
WHERE application_name = 'release-control-plane';

COMMIT;

-- Demonstrate a transaction that must be rolled back because completed_at
-- cannot precede started_at.
BEGIN;

INSERT INTO pg_advanced_fundamentals.deployments (
    application_id,
    status,
    requested_by,
    started_at,
    completed_at
)
SELECT
    application_id,
    'failed',
    'test-runner',
    now(),
    now() - interval '1 hour'
FROM pg_advanced_fundamentals.applications
WHERE application_name = 'market-risk-engine';

ROLLBACK;

-- Aggregate relational data while extracting JSONB fields.
SELECT
    a.application_name,
    a.environment,
    COUNT(d.deployment_id) AS deployment_count,
    COUNT(*) FILTER (
        WHERE d.status = 'succeeded'
    ) AS successful_deployment_count,
    MAX(d.completed_at) AS latest_completion,
    MAX(
        d.metadata ->> 'commit_sha'
    ) AS latest_commit_seen
FROM pg_advanced_fundamentals.applications AS a
LEFT JOIN pg_advanced_fundamentals.deployments AS d
    ON d.application_id = a.application_id
GROUP BY
    a.application_id,
    a.application_name,
    a.environment
ORDER BY a.application_name;

-- JSONB aggregation can produce a structured application-facing result.
SELECT
    jsonb_build_object(
        'application', a.application_name,
        'environment', a.environment,
        'regions', a.supported_regions,
        'features', a.enabled_features,
        'configuration', a.configuration,
        'deployment_count', COUNT(d.deployment_id)
    ) AS application_document
FROM pg_advanced_fundamentals.applications AS a
LEFT JOIN pg_advanced_fundamentals.deployments AS d
    ON d.application_id = a.application_id
GROUP BY
    a.application_id,
    a.application_name,
    a.environment,
    a.supported_regions,
    a.enabled_features,
    a.configuration
ORDER BY a.application_name;

-- Sequence metadata comes from PostgreSQL's pg_sequences view.
SELECT
    schemaname,
    sequencename,
    start_value,
    min_value,
    max_value,
    increment_by,
    cycle,
    cache_size
FROM pg_sequences
WHERE schemaname = 'pg_advanced_fundamentals';

-- PostgreSQL information_schema exposes portable relational metadata.
SELECT
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'pg_advanced_fundamentals'
ORDER BY table_name;

SELECT
    table_name,
    column_name,
    data_type,
    udt_schema,
    udt_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'pg_advanced_fundamentals'
ORDER BY table_name, ordinal_position;

-- PostgreSQL's pg_indexes view exposes the actual index definitions.
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'pg_advanced_fundamentals'
ORDER BY tablename, indexname;

-- Extension metadata confirms that pgcrypto is installed.
SELECT
    extname,
    extversion
FROM pg_extension
WHERE extname = 'pgcrypto';

-- Demonstrate the distinction between UUID generation and sequences.
SELECT
    gen_random_uuid() AS generated_uuid,
    nextval(
        'pg_advanced_fundamentals.application_number_seq'
    ) AS generated_sequence_value;

-- This statement intentionally fails if uncommented because PostgreSQL enum
-- values are constrained to the declared vocabulary:
--
-- INSERT INTO pg_advanced_fundamentals.applications (
--     application_name,
--     owner_email,
--     environment
-- )
-- VALUES (
--     'invalid-enum-demo',
--     'demo@example.com',
--     'unknown-environment'
-- );

-- This statement intentionally fails if uncommented because the CHECK
-- constraint rejects a JSONB scalar where an object is required:
--
-- INSERT INTO pg_advanced_fundamentals.applications (
--     application_name,
--     owner_email,
--     environment,
--     configuration
-- )
-- VALUES (
--     'invalid-jsonb-demo',
--     'demo@example.com',
--     'development',
--     '"scalar"'
-- );

-- Final relational view of the laboratory.
SELECT
    a.application_number,
    a.application_id,
    a.application_name,
    a.environment,
    a.release_channel,
    cardinality(a.supported_regions) AS region_count,
    cardinality(a.enabled_features) AS feature_count,
    COUNT(d.deployment_id) AS deployments
FROM pg_advanced_fundamentals.applications AS a
LEFT JOIN pg_advanced_fundamentals.deployments AS d
    ON d.application_id = a.application_id
GROUP BY
    a.application_number,
    a.application_id,
    a.application_name,
    a.environment,
    a.release_channel,
    a.supported_regions,
    a.enabled_features
ORDER BY a.application_number;
