#!/usr/bin/env python3
"""
PostgreSQL Advanced Fundamentals Demonstration

This self-contained script demonstrates advanced PostgreSQL fundamentals through
a repository engineering inventory domain:

- schemas
- sequences
- UUID identifiers
- enums
- JSONB
- arrays
- extensions
- constraints
- indexes
- transactions
- database introspection
- PostgreSQL-specific querying
- JSONB and array manipulation
- sequence behavior
- UUID generation
- error handling

The script uses only Python's standard library. It expects a PostgreSQL
installation and the PostgreSQL command-line client `psql`.

Example:
    python postgres_advanced_fundamentals.py

Connection defaults:
    host=localhost
    port=5432
    database=postgres
    user=postgres

Environment variables can override those values:
    PGHOST
    PGPORT
    PGDATABASE
    PGUSER
    PGPASSWORD

The script creates a dedicated schema named `advanced_fundamentals_lab`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "advanced_fundamentals_lab"
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")


@dataclass
class PsqlResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def require_psql() -> str:
    """Locate psql before any database operation is attempted."""
    executable = shutil.which("psql")
    if executable is None:
        raise RuntimeError(
            "The PostgreSQL command-line client `psql` was not found on PATH."
        )
    return executable


def run_psql(
    sql: str,
    *,
    database: str = DB_NAME,
    tuples_only: bool = False,
    stop_on_error: bool = True,
) -> PsqlResult:
    """
    Execute SQL through psql.

    SQL is supplied through stdin instead of being embedded in a shell command.
    This avoids shell quoting problems and keeps SQL statements intact.
    """
    executable = require_psql()

    command = [
        executable,
        "--host",
        DB_HOST,
        "--port",
        DB_PORT,
        "--username",
        DB_USER,
        "--dbname",
        database,
        "--no-psqlrc",
        "--quiet",
    ]

    if tuples_only:
        command.append("--tuples-only")

    if stop_on_error:
        command.extend(["--set", "ON_ERROR_STOP=1"])

    process = subprocess.run(
        command,
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )

    return PsqlResult(
        stdout=process.stdout,
        stderr=process.stderr,
        returncode=process.returncode,
    )


def print_result(title: str, result: PsqlResult) -> None:
    print(f"\n=== {title} ===")

    if result.stdout.strip():
        print(result.stdout.rstrip())

    if result.stderr.strip():
        print("stderr:")
        print(result.stderr.rstrip())

    if not result.ok:
        print(f"psql exited with status {result.returncode}")


def bootstrap_database() -> None:
    """
    Create the lab schema and PostgreSQL-specific objects.

    pgcrypto provides gen_random_uuid(). The extension is installed at the
    database level, while its functions become available to SQL statements.
    """
    sql = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;

CREATE SCHEMA {SCHEMA};

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE {SCHEMA}.deployment_status AS ENUM (
    'planned',
    'running',
    'succeeded',
    'failed',
    'cancelled'
);

CREATE TYPE {SCHEMA}.environment_type AS ENUM (
    'development',
    'staging',
    'production'
);

CREATE SEQUENCE {SCHEMA}.release_number_seq
    START WITH 1000
    INCREMENT BY 1
    MINVALUE 1000
    CACHE 10;

CREATE TABLE {SCHEMA}.applications (
    application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_number BIGINT NOT NULL
        DEFAULT nextval('{SCHEMA}.release_number_seq'),
    application_name TEXT NOT NULL,
    owner_email TEXT NOT NULL,
    environment {SCHEMA}.environment_type NOT NULL,
    supported_regions TEXT[] NOT NULL DEFAULT '{{}}',
    configuration JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT applications_name_unique
        UNIQUE (application_name),

    CONSTRAINT applications_owner_email_check
        CHECK (position('@' IN owner_email) > 1),

    CONSTRAINT applications_regions_check
        CHECK (cardinality(supported_regions) IS NULL
               OR cardinality(supported_regions) <= 20)
);

CREATE TABLE {SCHEMA}.deployments (
    deployment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL
        REFERENCES {SCHEMA}.applications(application_id)
        ON DELETE CASCADE,
    deployment_status {SCHEMA}.deployment_status NOT NULL DEFAULT 'planned',
    requested_by TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    deployment_tags TEXT[] NOT NULL DEFAULT '{{}}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    CONSTRAINT deployment_timestamps_check
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE INDEX applications_configuration_gin_idx
    ON {SCHEMA}.applications
    USING GIN (configuration);

CREATE INDEX applications_regions_gin_idx
    ON {SCHEMA}.applications
    USING GIN (supported_regions);

CREATE INDEX deployments_metadata_gin_idx
    ON {SCHEMA}.deployments
    USING GIN (metadata);

CREATE INDEX deployments_application_idx
    ON {SCHEMA}.deployments(application_id);

COMMENT ON SCHEMA {SCHEMA}
    IS 'Laboratory for PostgreSQL advanced fundamentals';

COMMENT ON COLUMN {SCHEMA}.applications.application_number
    IS 'Human-readable sequential identifier backed by a PostgreSQL sequence';

COMMENT ON COLUMN {SCHEMA}.applications.application_id
    IS 'Globally unique identifier generated by pgcrypto';
"""

    result = run_psql(sql)
    print_result("Database bootstrap", result)

    if not result.ok:
        raise RuntimeError("Database bootstrap failed.")


def demonstrate_inserts() -> None:
    """Insert realistic rows showing UUIDs, enums, JSONB, arrays, and defaults."""
    sql = f"""
INSERT INTO {SCHEMA}.applications (
    application_name,
    owner_email,
    environment,
    supported_regions,
    configuration
)
VALUES
(
    'market-risk-engine',
    'platform@example.com',
    'production',
    ARRAY['ap-south-1', 'eu-west-1'],
    jsonb_build_object(
        'runtime', 'python',
        'replicas', 4,
        'features', jsonb_build_array('risk', 'alerts', 'audit'),
        'limits', jsonb_build_object(
            'requests_per_minute', 1200,
            'max_position_count', 5000
        )
    )
),
(
    'research-notebook-service',
    'research@example.com',
    'development',
    ARRAY['ap-south-1'],
    jsonb_build_object(
        'runtime', 'jupyter',
        'replicas', 1,
        'features', jsonb_build_array('notebooks', 'datasets'),
        'limits', jsonb_build_object(
            'requests_per_minute', 100
        )
    )
);

INSERT INTO {SCHEMA}.deployments (
    application_id,
    deployment_status,
    requested_by,
    metadata,
    deployment_tags,
    started_at,
    completed_at
)
SELECT
    application_id,
    'succeeded',
    'release-bot',
    jsonb_build_object(
        'commit_sha', 'abc123def456',
        'pipeline', 'production-release',
        'artifact', jsonb_build_object(
            'name', application_name,
            'version', '2026.10.06'
        )
    ),
    ARRAY['production', 'automated', 'verified'],
    now() - interval '18 minutes',
    now() - interval '5 minutes'
FROM {SCHEMA}.applications
WHERE application_name = 'market-risk-engine';

INSERT INTO {SCHEMA}.deployments (
    application_id,
    deployment_status,
    requested_by,
    metadata,
    deployment_tags
)
SELECT
    application_id,
    'planned',
    'researcher',
    jsonb_build_object(
        'commit_sha', 'fed987654321',
        'pipeline', 'development-release'
    ),
    ARRAY['development', 'manual']
FROM {SCHEMA}.applications
WHERE application_name = 'research-notebook-service';
"""

    result = run_psql(sql)
    print_result("Realistic inserts", result)

    if not result.ok:
        raise RuntimeError("Insert demonstration failed.")


def demonstrate_identifiers_and_enums() -> None:
    """
    Show the distinction between a UUID primary key, a sequential business
    identifier, and an enum-controlled state.
    """
    sql = f"""
SELECT
    application_id,
    application_number,
    application_name,
    environment,
    pg_typeof(application_id) AS uuid_type,
    pg_typeof(application_number) AS sequence_backed_type,
    pg_typeof(environment) AS enum_type
FROM {SCHEMA}.applications
ORDER BY application_number;

SELECT
    enumlabel AS deployment_state
FROM pg_enum
WHERE enumtypid = '{SCHEMA}.deployment_status'::regtype
ORDER BY enumsortorder;

SELECT
    sequencename,
    start_value,
    increment_by,
    cache_size
FROM pg_sequences
WHERE schemaname = '{SCHEMA}'
  AND sequencename = 'release_number_seq';
"""

    result = run_psql(sql)
    print_result("UUIDs, sequence-backed identifiers, and enums", result)


def demonstrate_jsonb() -> None:
    """Exercise PostgreSQL JSONB operators and indexing-friendly expressions."""
    sql = f"""
SELECT
    application_name,
    configuration ->> 'runtime' AS runtime,
    configuration ->> 'replicas' AS replicas,
    configuration #>> '{{limits,requests_per_minute}}' AS request_limit
FROM {SCHEMA}.applications
ORDER BY application_name;

SELECT
    application_name,
    configuration
FROM {SCHEMA}.applications
WHERE configuration @> '{{"features": ["risk"]}}'::jsonb;

SELECT
    application_name,
    jsonb_array_elements_text(configuration -> 'features') AS feature
FROM {SCHEMA}.applications
ORDER BY application_name, feature;

UPDATE {SCHEMA}.applications
SET configuration = jsonb_set(
    configuration,
    '{{limits,max_position_count}}',
    '7500'::jsonb,
    true
)
WHERE application_name = 'market-risk-engine';

SELECT
    application_name,
    configuration -> 'limits' AS limits
FROM {SCHEMA}.applications
WHERE application_name = 'market-risk-engine';
"""

    result = run_psql(sql)
    print_result("JSONB operations", result)


def demonstrate_arrays() -> None:
    """Demonstrate PostgreSQL arrays as typed, queryable values."""
    sql = f"""
SELECT
    application_name,
    supported_regions,
    cardinality(supported_regions) AS region_count
FROM {SCHEMA}.applications
ORDER BY application_name;

SELECT
    application_name,
    supported_regions
FROM {SCHEMA}.applications
WHERE 'ap-south-1' = ANY(supported_regions);

SELECT
    application_name,
    unnest(supported_regions) AS region
FROM {SCHEMA}.applications
ORDER BY application_name, region;

UPDATE {SCHEMA}.applications
SET supported_regions = array_append(supported_regions, 'us-east-1')
WHERE application_name = 'market-risk-engine';

SELECT
    application_name,
    supported_regions
FROM {SCHEMA}.applications
WHERE application_name = 'market-risk-engine';
"""

    result = run_psql(sql)
    print_result("Array operations", result)


def demonstrate_transactions() -> None:
    """
    Demonstrate transactional consistency.

    The first transaction commits both the deployment and its state update.
    The second intentionally violates a check constraint and is rolled back.
    """
    successful_transaction = f"""
BEGIN;

WITH selected_application AS (
    SELECT application_id
    FROM {SCHEMA}.applications
    WHERE application_name = 'research-notebook-service'
)
INSERT INTO {SCHEMA}.deployments (
    application_id,
    deployment_status,
    requested_by,
    metadata,
    deployment_tags,
    started_at,
    completed_at
)
SELECT
    application_id,
    'succeeded',
    'release-bot',
    '{{"pipeline": "development-release", "commit_sha": "123abc"}}'::jsonb,
    ARRAY['development', 'automated'],
    now() - interval '7 minutes',
    now() - interval '2 minutes'
FROM selected_application;

UPDATE {SCHEMA}.applications
SET configuration = jsonb_set(
    configuration,
    '{{last_deployment}}',
    jsonb_build_object(
        'status', 'succeeded',
        'source', 'release-bot'
    ),
    true
)
WHERE application_name = 'research-notebook-service';

COMMIT;
"""

    result = run_psql(successful_transaction)
    print_result("Successful transaction", result)

    failing_transaction = f"""
BEGIN;

INSERT INTO {SCHEMA}.deployments (
    application_id,
    deployment_status,
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
FROM {SCHEMA}.applications
WHERE application_name = 'market-risk-engine';

ROLLBACK;
"""

    result = run_psql(failing_transaction)
    print_result("Rolled-back invalid transaction", result)


def demonstrate_relational_and_json_queries() -> None:
    """Combine joins, JSONB, arrays, grouping, and enum values."""
    sql = f"""
SELECT
    a.application_name,
    a.environment,
    COUNT(d.deployment_id) AS deployment_count,
    COUNT(*) FILTER (
        WHERE d.deployment_status = 'succeeded'
    ) AS successful_deployments,
    MAX(d.completed_at) AS latest_completion
FROM {SCHEMA}.applications AS a
LEFT JOIN {SCHEMA}.deployments AS d
    ON d.application_id = a.application_id
GROUP BY
    a.application_id,
    a.application_name,
    a.environment
ORDER BY a.application_name;

SELECT
    a.application_name,
    d.deployment_status,
    d.metadata ->> 'commit_sha' AS commit_sha,
    d.metadata #>> '{{artifact,version}}' AS artifact_version,
    d.deployment_tags
FROM {SCHEMA}.applications AS a
JOIN {SCHEMA}.deployments AS d
    ON d.application_id = a.application_id
WHERE d.metadata ? 'commit_sha'
ORDER BY d.deployment_id;
"""

    result = run_psql(sql)
    print_result("Combined PostgreSQL query patterns", result)


def demonstrate_schema_introspection() -> None:
    """Use PostgreSQL catalogs to inspect the objects created by the lab."""
    sql = f"""
SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = '{SCHEMA}'
ORDER BY table_name;

SELECT
    column_name,
    data_type,
    udt_schema,
    udt_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = '{SCHEMA}'
  AND table_name IN ('applications', 'deployments')
ORDER BY table_name, ordinal_position;

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = '{SCHEMA}'
ORDER BY indexname;

SELECT
    extname,
    extversion
FROM pg_extension
WHERE extname = 'pgcrypto';
"""

    result = run_psql(sql)
    print_result("System catalog and information schema introspection", result)


def demonstrate_sequence_behavior() -> None:
    """
    Demonstrate sequence allocation and an important PostgreSQL property:
    sequence values are not transactional business counters.

    A sequence value can be consumed even when the surrounding transaction
    later rolls back. This is intentional PostgreSQL sequence behavior.
    """
    sql = f"""
SELECT
    nextval('{SCHEMA}.release_number_seq') AS consumed_value;

SELECT
    currval('{SCHEMA}.release_number_seq') AS current_session_value;

BEGIN;

SELECT
    nextval('{SCHEMA}.release_number_seq') AS value_inside_transaction;

ROLLBACK;

SELECT
    nextval('{SCHEMA}.release_number_seq') AS value_after_rollback;
"""

    result = run_psql(sql)
    print_result("Sequence behavior", result)


def demonstrate_validation_failure() -> None:
    """Trigger a constraint failure without destroying the valid dataset."""
    sql = f"""
BEGIN;

INSERT INTO {SCHEMA}.applications (
    application_name,
    owner_email,
    environment,
    supported_regions
)
VALUES (
    'invalid-application',
    'not-an-email',
    'production',
    ARRAY['ap-south-1']
);

ROLLBACK;
"""

    result = run_psql(sql, stop_on_error=False)
    print_result("Constraint validation failure", result)


def export_report() -> Path:
    """
    Generate a small JSON report using query output.

    The file is created in the system temporary directory so the script does
    not modify the working repository unexpectedly.
    """
    sql = f"""
SELECT jsonb_build_object(
    'application', a.application_name,
    'application_id', a.application_id,
    'application_number', a.application_number,
    'environment', a.environment,
    'regions', a.supported_regions,
    'configuration', a.configuration,
    'deployment_count', COUNT(d.deployment_id)
)
FROM {SCHEMA}.applications AS a
LEFT JOIN {SCHEMA}.deployments AS d
    ON d.application_id = a.application_id
GROUP BY
    a.application_id,
    a.application_name,
    a.application_number,
    a.environment,
    a.supported_regions,
    a.configuration
ORDER BY a.application_number;
"""

    result = run_psql(sql, tuples_only=True)

    if not result.ok:
        raise RuntimeError(result.stderr)

    records: list[dict[str, Any]] = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Unexpected JSON returned by PostgreSQL: {line}"
            ) from exc

    destination = Path(tempfile.gettempdir()) / "postgres_advanced_fundamentals_report.json"
    destination.write_text(
        json.dumps(records, indent=2),
        encoding="utf-8",
    )

    return destination


def cleanup_database() -> None:
    """
    Remove the laboratory schema.

    The cleanup is explicit rather than automatic so a learner can inspect
    the created objects after running the script.
    """
    print(
        f"\nThe schema `{SCHEMA}` remains available for inspection. "
        "Drop it manually when finished."
    )


def main() -> int:
    print("PostgreSQL Advanced Fundamentals Laboratory")
    print(f"Connecting to {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    try:
        require_psql()
        bootstrap_database()
        demonstrate_inserts()
        demonstrate_identifiers_and_enums()
        demonstrate_jsonb()
        demonstrate_arrays()
        demonstrate_transactions()
        demonstrate_relational_and_json_queries()
        demonstrate_schema_introspection()
        demonstrate_sequence_behavior()
        demonstrate_validation_failure()

        report_path = export_report()
        print(f"\nJSON report written to: {report_path}")

        cleanup_database()
        return 0

    except KeyboardInterrupt:
        print("\nExecution interrupted.")
        return 130

    except Exception as exc:
        print(f"\nExecution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
