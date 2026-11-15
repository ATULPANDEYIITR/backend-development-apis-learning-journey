/*
===============================================================================
REDIS FUNDAMENTALS - POSTGRESQL RELATIONAL MODEL
===============================================================================

This script models Redis-style key-value storage using PostgreSQL.

Supported structures:
1. Strings
2. Hashes
3. Lists
4. Sets
5. Sorted sets

Additional mechanisms:
- Typed keys
- Expiration and TTL
- Unique key constraints
- Atomic updates
- Hash-field management
- List ordering
- Set membership
- Sorted-set ranking
- Transactions
- Views
- Functions and procedures
- Triggers
- Reporting and validation

PostgreSQL 15+
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS redis_lab;

SET search_path TO redis_lab, public;

-- ============================================================================
-- ENUMERATED DATA TYPES
-- ============================================================================

CREATE TYPE redis_value_type AS ENUM (
    'string',
    'hash',
    'list',
    'set',
    'zset'
);

CREATE TYPE redis_operation AS ENUM (
    'SET',
    'GET',
    'HSET',
    'HGET',
    'LPUSH',
    'RPUSH',
    'LPOP',
    'RPOP',
    'SADD',
    'SREM',
    'ZADD',
    'DEL',
    'EXPIRE'
);

-- ============================================================================
-- CORE KEY REGISTRY
-- ============================================================================

CREATE TABLE redis_keys (
    key_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    key_name TEXT NOT NULL UNIQUE,

    value_type redis_value_type NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ,

    CHECK (length(key_name) BETWEEN 1 AND 512),

    CHECK (
        expires_at IS NULL OR
        expires_at > created_at
    )
);

CREATE INDEX idx_redis_keys_expiration
ON redis_keys(expires_at)
WHERE expires_at IS NOT NULL;

CREATE INDEX idx_redis_keys_type
ON redis_keys(value_type);

-- ============================================================================
-- STRING STORAGE
-- ============================================================================

CREATE TABLE redis_strings (
    key_id BIGINT PRIMARY KEY
        REFERENCES redis_keys(key_id)
        ON DELETE CASCADE,

    value TEXT NOT NULL
);

-- ============================================================================
-- HASH STORAGE
-- ============================================================================

CREATE TABLE redis_hash_fields (
    key_id BIGINT NOT NULL
        REFERENCES redis_keys(key_id)
        ON DELETE CASCADE,

    field_name TEXT NOT NULL,

    field_value TEXT NOT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (key_id, field_name),

    CHECK (length(field_name) > 0)
);

CREATE INDEX idx_hash_field_name
ON redis_hash_fields(field_name);

-- ============================================================================
-- LIST STORAGE
-- ============================================================================

CREATE TABLE redis_list_items (
    key_id BIGINT NOT NULL
        REFERENCES redis_keys(key_id)
        ON DELETE CASCADE,

    position BIGINT NOT NULL,

    item_value TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (key_id, position)
);

CREATE INDEX idx_list_order
ON redis_list_items(key_id, position);

-- ============================================================================
-- SET STORAGE
-- ============================================================================

CREATE TABLE redis_set_members (
    key_id BIGINT NOT NULL
        REFERENCES redis_keys(key_id)
        ON DELETE CASCADE,

    member_value TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (key_id, member_value)
);

CREATE INDEX idx_set_member_lookup
ON redis_set_members(member_value);

-- ============================================================================
-- SORTED SET STORAGE
-- ============================================================================

CREATE TABLE redis_sorted_members (
    key_id BIGINT NOT NULL
        REFERENCES redis_keys(key_id)
        ON DELETE CASCADE,

    member_value TEXT NOT NULL,

    score DOUBLE PRECISION NOT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (key_id, member_value),

    CHECK (
        score > '-Infinity'::DOUBLE PRECISION
        AND score < 'Infinity'::DOUBLE PRECISION
    )
);

CREATE INDEX idx_sorted_set_rank
ON redis_sorted_members(key_id, score, member_value);

-- ============================================================================
-- OPERATION AUDIT
-- ============================================================================

CREATE TABLE redis_operation_log (
    operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    key_name TEXT NOT NULL,

    operation redis_operation NOT NULL,

    operation_status TEXT NOT NULL DEFAULT 'SUCCESS',

    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    CHECK (
        operation_status IN (
            'SUCCESS',
            'FAILED',
            'EXPIRED'
        )
    )
);

CREATE INDEX idx_operation_log_key_time
ON redis_operation_log(key_name, executed_at DESC);

CREATE INDEX idx_operation_log_time
ON redis_operation_log(executed_at DESC);

-- ============================================================================
-- UPDATED TIMESTAMP TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION update_key_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_update_key_timestamp
BEFORE UPDATE ON redis_keys
FOR EACH ROW
EXECUTE FUNCTION update_key_timestamp();

-- ============================================================================
-- KEY TYPE VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_key_type(
    p_key TEXT,
    p_expected redis_value_type
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_type redis_value_type;
    v_expiration TIMESTAMPTZ;
BEGIN
    IF p_key IS NULL OR length(p_key) = 0 THEN
        RAISE EXCEPTION 'Key cannot be empty';
    END IF;

    SELECT key_id, value_type, expires_at
    INTO v_id, v_type, v_expiration
    FROM redis_keys
    WHERE key_name = p_key
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF v_expiration IS NOT NULL AND v_expiration <= NOW() THEN
        DELETE FROM redis_keys WHERE key_id = v_id;
        RETURN NULL;
    END IF;

    IF v_type <> p_expected THEN
        RAISE EXCEPTION
            'WRONGTYPE: expected %, found %',
            p_expected,
            v_type;
    END IF;

    RETURN v_id;
END;
$$;

-- ============================================================================
-- KEY CREATION
-- ============================================================================

CREATE OR REPLACE FUNCTION create_redis_key(
    p_key TEXT,
    p_type redis_value_type
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    IF p_key IS NULL OR length(p_key) = 0 THEN
        RAISE EXCEPTION 'Invalid key';
    END IF;

    INSERT INTO redis_keys(key_name, value_type)
    VALUES (p_key, p_type)
    ON CONFLICT (key_name) DO NOTHING;

    SELECT key_id
    INTO v_id
    FROM redis_keys
    WHERE key_name = p_key
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Key creation failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM redis_keys
        WHERE key_id = v_id
          AND value_type = p_type
    ) THEN
        RAISE EXCEPTION 'WRONGTYPE: key already has another type';
    END IF;

    RETURN v_id;
END;
$$;

-- ============================================================================
-- STRING COMMANDS
-- ============================================================================

CREATE OR REPLACE PROCEDURE redis_set(
    p_key TEXT,
    p_value TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    IF p_value IS NULL THEN
        RAISE EXCEPTION 'String value cannot be NULL';
    END IF;

    SELECT key_id
    INTO v_id
    FROM redis_keys
    WHERE key_name = p_key
    FOR UPDATE;

    IF FOUND THEN
        DELETE FROM redis_keys WHERE key_id = v_id;
    END IF;

    INSERT INTO redis_keys(key_name, value_type)
    VALUES (p_key, 'string')
    RETURNING key_id INTO v_id;

    INSERT INTO redis_strings(key_id, value)
    VALUES (v_id, p_value);

    INSERT INTO redis_operation_log(
        key_name,
        operation
    )
    VALUES (p_key, 'SET');
END;
$$;

CREATE OR REPLACE FUNCTION redis_get(p_key TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_value TEXT;
BEGIN
    v_id := validate_key_type(p_key, 'string');

    IF v_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT value
    INTO v_value
    FROM redis_strings
    WHERE key_id = v_id;

    INSERT INTO redis_operation_log(key_name, operation)
    VALUES (p_key, 'GET');

    RETURN v_value;
END;
$$;

CREATE OR REPLACE FUNCTION redis_incrby(
    p_key TEXT,
    p_increment BIGINT DEFAULT 1
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_current BIGINT;
    v_result BIGINT;
    v_value TEXT;
    v_id BIGINT;
BEGIN
    v_id := validate_key_type(p_key, 'string');

    IF v_id IS NULL THEN
        PERFORM create_redis_key(p_key, 'string');

        SELECT key_id
        INTO v_id
        FROM redis_keys
        WHERE key_name = p_key
        FOR UPDATE;

        INSERT INTO redis_strings(key_id, value)
        VALUES (v_id, '0');
    END IF;

    SELECT value
    INTO v_value
    FROM redis_strings
    WHERE key_id = v_id
    FOR UPDATE;

    IF v_value !~ '^-?[0-9]+$' THEN
        RAISE EXCEPTION 'Value is not an integer';
    END IF;

    BEGIN
        v_current := v_value::BIGINT;
        v_result := v_current + p_increment;
    EXCEPTION
        WHEN numeric_value_out_of_range THEN
            RAISE EXCEPTION 'Integer overflow';
    END;

    UPDATE redis_strings
    SET value = v_result::TEXT
    WHERE key_id = v_id;

    RETURN v_result;
END;
$$;

-- ============================================================================
-- HASH COMMANDS
-- ============================================================================

CREATE OR REPLACE FUNCTION redis_hset(
    p_key TEXT,
    p_field TEXT,
    p_value TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_inserted BOOLEAN;
BEGIN
    IF p_field IS NULL OR length(p_field) = 0 THEN
        RAISE EXCEPTION 'Invalid hash field';
    END IF;

    IF p_value IS NULL THEN
        RAISE EXCEPTION 'Hash value cannot be NULL';
    END IF;

    v_id := create_redis_key(p_key, 'hash');

    INSERT INTO redis_hash_fields(
        key_id,
        field_name,
        field_value
    )
    VALUES (
        v_id,
        p_field,
        p_value
    )
    ON CONFLICT (key_id, field_name)
    DO UPDATE SET
        field_value = EXCLUDED.field_value,
        updated_at = NOW();

    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    INSERT INTO redis_operation_log(key_name, operation)
    VALUES (p_key, 'HSET');

    RETURN v_inserted;
END;
$$;

CREATE OR REPLACE FUNCTION redis_hget(
    p_key TEXT,
    p_field TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_value TEXT;
BEGIN
    v_id := validate_key_type(p_key, 'hash');

    IF v_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT field_value
    INTO v_value
    FROM redis_hash_fields
    WHERE key_id = v_id
      AND field_name = p_field;

    RETURN v_value;
END;
$$;

CREATE OR REPLACE FUNCTION redis_hgetall(p_key TEXT)
RETURNS TABLE (
    field_name TEXT,
    field_value TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    v_id := validate_key_type(p_key, 'hash');

    IF v_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT h.field_name, h.field_value
    FROM redis_hash_fields h
    WHERE h.key_id = v_id
    ORDER BY h.field_name;
END;
$$;

-- ============================================================================
-- LIST COMMANDS
-- ============================================================================

CREATE OR REPLACE FUNCTION redis_rpush(
    p_key TEXT,
    p_value TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_position BIGINT;
BEGIN
    IF p_value IS NULL THEN
        RAISE EXCEPTION 'List item cannot be NULL';
    END IF;

    v_id := create_redis_key(p_key, 'list');

    SELECT COALESCE(MAX(position), -1) + 1
    INTO v_position
    FROM redis_list_items
    WHERE key_id = v_id
    FOR UPDATE;

    INSERT INTO redis_list_items(
        key_id,
        position,
        item_value
    )
    VALUES (
        v_id,
        v_position,
        p_value
    );

    RETURN v_position + 1;
END;
$$;

CREATE OR REPLACE FUNCTION redis_lpush(
    p_key TEXT,
    p_value TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    v_id := create_redis_key(p_key, 'list');

    UPDATE redis_list_items
    SET position = position + 1
    WHERE key_id = v_id;

    INSERT INTO redis_list_items(
        key_id,
        position,
        item_value
    )
    VALUES (v_id, 0, p_value);

    RETURN (
        SELECT COUNT(*)
        FROM redis_list_items
        WHERE key_id = v_id
    );
END;
$$;

CREATE OR REPLACE FUNCTION redis_lrange(p_key TEXT)
RETURNS TABLE (
    position BIGINT,
    item_value TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    v_id := validate_key_type(p_key, 'list');

    IF v_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT l.position, l.item_value
    FROM redis_list_items l
    WHERE l.key_id = v_id
    ORDER BY l.position;
END;
$$;

CREATE OR REPLACE FUNCTION redis_lpop(p_key TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_position BIGINT;
    v_value TEXT;
BEGIN
    v_id := validate_key_type(p_key, 'list');

    IF v_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT position, item_value
    INTO v_position, v_value
    FROM redis_list_items
    WHERE key_id = v_id
    ORDER BY position
    LIMIT 1
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    DELETE FROM redis_list_items
    WHERE key_id = v_id
      AND position = v_position;

    IF NOT EXISTS (
        SELECT 1 FROM redis_list_items WHERE key_id = v_id
    ) THEN
        DELETE FROM redis_keys WHERE key_id = v_id;
    END IF;

    RETURN v_value;
END;
$$;

-- ============================================================================
-- SET COMMANDS
-- ============================================================================

CREATE OR REPLACE FUNCTION redis_sadd(
    p_key TEXT,
    p_member TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_count BIGINT;
BEGIN
    v_id := create_redis_key(p_key, 'set');

    INSERT INTO redis_set_members(key_id, member_value)
    VALUES (v_id, p_member)
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN v_count > 0;
END;
$$;

CREATE OR REPLACE FUNCTION redis_smembers(p_key TEXT)
RETURNS TABLE(member_value TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    v_id := validate_key_type(p_key, 'set');

    IF v_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT s.member_value
    FROM redis_set_members s
    WHERE s.key_id = v_id
    ORDER BY s.member_value;
END;
$$;

CREATE OR REPLACE FUNCTION redis_sinter(
    p_first TEXT,
    p_second TEXT
)
RETURNS TABLE(member_value TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_first BIGINT;
    v_second BIGINT;
BEGIN
    v_first := validate_key_type(p_first, 'set');
    v_second := validate_key_type(p_second, 'set');

    IF v_first IS NULL OR v_second IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT a.member_value
    FROM redis_set_members a
    INNER JOIN redis_set_members b
        ON b.member_value = a.member_value
    WHERE a.key_id = v_first
      AND b.key_id = v_second
    ORDER BY a.member_value;
END;
$$;

-- ============================================================================
-- SORTED SET COMMANDS
-- ============================================================================

CREATE OR REPLACE FUNCTION redis_zadd(
    p_key TEXT,
    p_member TEXT,
    p_score DOUBLE PRECISION
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_count BIGINT;
BEGIN
    IF p_member IS NULL OR length(p_member) = 0 THEN
        RAISE EXCEPTION 'Invalid sorted-set member';
    END IF;

    IF p_score IS NULL OR
       p_score = 'Infinity'::DOUBLE PRECISION OR
       p_score = '-Infinity'::DOUBLE PRECISION OR
       p_score = 'NaN'::DOUBLE PRECISION THEN
        RAISE EXCEPTION 'Score must be finite';
    END IF;

    v_id := create_redis_key(p_key, 'zset');

    INSERT INTO redis_sorted_members(
        key_id,
        member_value,
        score
    )
    VALUES (
        v_id,
        p_member,
        p_score
    )
    ON CONFLICT (key_id, member_value)
    DO UPDATE SET
        score = EXCLUDED.score,
        updated_at = NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN v_count > 0;
END;
$$;

CREATE OR REPLACE FUNCTION redis_zrange(p_key TEXT)
RETURNS TABLE (
    member_value TEXT,
    score DOUBLE PRECISION,
    rank BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    v_id := validate_key_type(p_key, 'zset');

    IF v_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        z.member_value,
        z.score,
        ROW_NUMBER() OVER (
            ORDER BY z.score, z.member_value
        ) - 1 AS rank
    FROM redis_sorted_members z
    WHERE z.key_id = v_id
    ORDER BY z.score, z.member_value;
END;
$$;

-- ============================================================================
-- KEY MANAGEMENT
-- ============================================================================

CREATE OR REPLACE FUNCTION redis_exists(p_key TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM redis_keys
        WHERE key_name = p_key
          AND (
              expires_at IS NULL
              OR expires_at > NOW()
          )
    );
END;
$$;

CREATE OR REPLACE FUNCTION redis_type(p_key TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_type TEXT;
BEGIN
    SELECT value_type::TEXT
    INTO v_type
    FROM redis_keys
    WHERE key_name = p_key
      AND (
          expires_at IS NULL
          OR expires_at > NOW()
      );

    RETURN COALESCE(v_type, 'none');
END;
$$;

CREATE OR REPLACE FUNCTION redis_ttl(p_key TEXT)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_expiration TIMESTAMPTZ;
BEGIN
    SELECT expires_at
    INTO v_expiration
    FROM redis_keys
    WHERE key_name = p_key;

    IF NOT FOUND THEN
        RETURN -2;
    END IF;

    IF v_expiration IS NULL THEN
        RETURN -1;
    END IF;

    IF v_expiration <= NOW() THEN
        RETURN -2;
    END IF;

    RETURN FLOOR(
        EXTRACT(EPOCH FROM (v_expiration - NOW()))
    )::BIGINT;
END;
$$;

CREATE OR REPLACE PROCEDURE redis_expire(
    p_key TEXT,
    p_seconds INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_seconds <= 0 THEN
        RAISE EXCEPTION 'Expiration must be positive';
    END IF;

    UPDATE redis_keys
    SET expires_at = NOW() + make_interval(secs => p_seconds)
    WHERE key_name = p_key;

    IF NOT FOUND THEN
        RAISE NOTICE 'Key does not exist: %', p_key;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION redis_del(p_key TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_count BIGINT;
BEGIN
    DELETE FROM redis_keys
    WHERE key_name = p_key;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN v_count > 0;
END;
$$;

-- ============================================================================
-- EXPIRED KEY CLEANUP
-- ============================================================================

CREATE OR REPLACE PROCEDURE redis_cleanup_expired()
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM redis_keys
    WHERE expires_at IS NOT NULL
      AND expires_at <= NOW();

    RAISE NOTICE 'Expired key cleanup completed';
END;
$$;

-- ============================================================================
-- REPORTING VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW redis_key_inventory AS
SELECT
    k.key_name,
    k.value_type,
    k.created_at,
    k.updated_at,
    k.expires_at,
    CASE
        WHEN k.expires_at IS NULL THEN -1
        WHEN k.expires_at <= NOW() THEN -2
        ELSE FLOOR(
            EXTRACT(EPOCH FROM (k.expires_at - NOW()))
        )::BIGINT
    END AS ttl_seconds
FROM redis_keys k
WHERE k.expires_at IS NULL
   OR k.expires_at > NOW();

CREATE OR REPLACE VIEW redis_type_statistics AS
SELECT
    value_type,
    COUNT(*) AS total_keys,
    COUNT(*) FILTER (
        WHERE expires_at IS NOT NULL
    ) AS expiring_keys
FROM redis_keys
WHERE expires_at IS NULL OR expires_at > NOW()
GROUP BY value_type;

CREATE OR REPLACE VIEW redis_sorted_leaderboard AS
SELECT
    k.key_name,
    z.member_value,
    z.score,
    RANK() OVER (
        PARTITION BY z.key_id
        ORDER BY z.score DESC
    ) AS descending_rank
FROM redis_sorted_members z
JOIN redis_keys k
    ON k.key_id = z.key_id;

-- ============================================================================
-- SAMPLE DATA: STRINGS
-- ============================================================================

CALL redis_set('app:name', 'Redis Fundamentals');
CALL redis_set('counter:visits', '1000');

SELECT redis_incrby('counter:visits', 25);

-- ============================================================================
-- SAMPLE DATA: HASHES
-- ============================================================================

SELECT redis_hset('user:1001', 'name', 'Atul');
SELECT redis_hset('user:1001', 'department', 'Engineering');
SELECT redis_hset('user:1001', 'status', 'active');

SELECT * FROM redis_hgetall('user:1001');

-- ============================================================================
-- SAMPLE DATA: LISTS
-- ============================================================================

SELECT redis_rpush('queue:jobs', 'build');
SELECT redis_rpush('queue:jobs', 'test');
SELECT redis_rpush('queue:jobs', 'deploy');
SELECT redis_lpush('queue:jobs', 'validate');

SELECT * FROM redis_lrange('queue:jobs');

-- ============================================================================
-- SAMPLE DATA: SETS
-- ============================================================================

SELECT redis_sadd('skills:backend', 'Python');
SELECT redis_sadd('skills:backend', 'Java');
SELECT redis_sadd('skills:backend', 'C++');

SELECT redis_sadd('skills:cloud', 'Java');
SELECT redis_sadd('skills:cloud', 'Go');
SELECT redis_sadd('skills:cloud', 'Python');

SELECT * FROM redis_smembers('skills:backend');

SELECT * FROM redis_sinter(
    'skills:backend',
    'skills:cloud'
);

-- ============================================================================
-- SAMPLE DATA: SORTED SETS
-- ============================================================================

SELECT redis_zadd('leaderboard', 'Alice', 950);
SELECT redis_zadd('leaderboard', 'Bob', 850);
SELECT redis_zadd('leaderboard', 'Charlie', 900);

SELECT * FROM redis_zrange('leaderboard');

-- ============================================================================
-- EXPIRATION EXAMPLE
-- ============================================================================

CALL redis_set('session:1001', 'authenticated');
CALL redis_expire('session:1001', 3600);

SELECT
    redis_exists('session:1001') AS session_exists,
    redis_ttl('session:1001') AS remaining_seconds;

-- ============================================================================
-- FAILURE CASE: TYPE MISMATCH
-- ============================================================================
-- The following statement is intentionally commented out because it raises
-- WRONGTYPE and would abort the current transaction.
--
-- SELECT redis_hgetall('counter:visits');

-- ============================================================================
-- RETRIEVAL AND VALIDATION
-- ============================================================================

SELECT redis_get('app:name');

SELECT redis_get('counter:visits');

SELECT redis_type('user:1001');

SELECT redis_exists('user:1001');

SELECT redis_ttl('session:1001');

SELECT *
FROM redis_key_inventory
ORDER BY key_name;

-- ============================================================================
-- AGGREGATION
-- ============================================================================

SELECT *
FROM redis_type_statistics
ORDER BY value_type;

SELECT
    value_type,
    COUNT(*) AS keys_per_type
FROM redis_keys
GROUP BY value_type;

-- ============================================================================
-- SORTED-SET RANKING
-- ============================================================================

SELECT *
FROM redis_sorted_leaderboard
ORDER BY descending_rank;

-- ============================================================================
-- CTE: TOP SORTED-SET MEMBERS
-- ============================================================================

WITH ranked_members AS (
    SELECT
        key_name,
        member_value,
        score,
        ROW_NUMBER() OVER (
            PARTITION BY key_name
            ORDER BY score DESC, member_value
        ) AS position
    FROM redis_sorted_leaderboard
)
SELECT *
FROM ranked_members
WHERE position <= 3
ORDER BY key_name, position;

-- ============================================================================
-- OPERATION REPORT
-- ============================================================================

SELECT
    key_name,
    operation,
    COUNT(*) AS operation_count,
    MAX(executed_at) AS last_executed
FROM redis_operation_log
GROUP BY key_name, operation
ORDER BY key_name, operation;

-- ============================================================================
-- TRANSACTION EXAMPLE
-- ============================================================================

SAVEPOINT before_transaction_demo;

CALL redis_set('transaction:example', 'initial');

SELECT redis_get('transaction:example');

UPDATE redis_strings
SET value = 'updated'
WHERE key_id = (
    SELECT key_id
    FROM redis_keys
    WHERE key_name = 'transaction:example'
);

SELECT redis_get('transaction:example');

ROLLBACK TO SAVEPOINT before_transaction_demo;

-- ============================================================================
-- DATA INTEGRITY VALIDATION
-- ============================================================================

-- Every registered key must have exactly one corresponding primary value
-- record for its declared type.

SELECT
    k.key_name,
    k.value_type,
    (
        SELECT COUNT(*)
        FROM redis_strings s
        WHERE s.key_id = k.key_id
    ) AS string_records,
    (
        SELECT COUNT(*)
        FROM redis_hash_fields h
        WHERE h.key_id = k.key_id
    ) AS hash_records,
    (
        SELECT COUNT(*)
        FROM redis_list_items l
        WHERE l.key_id = k.key_id
    ) AS list_records,
    (
        SELECT COUNT(*)
        FROM redis_set_members s
        WHERE s.key_id = k.key_id
    ) AS set_records,
    (
        SELECT COUNT(*)
        FROM redis_sorted_members z
        WHERE z.key_id = k.key_id
    ) AS zset_records
FROM redis_keys k
ORDER BY k.key_name;

-- ============================================================================
-- FINAL DATABASE REPORT
-- ============================================================================

SELECT
    COUNT(*) AS total_registered_keys,
    COUNT(*) FILTER (
        WHERE expires_at IS NOT NULL
    ) AS expiring_keys,
    COUNT(DISTINCT value_type) AS active_data_types
FROM redis_keys
WHERE expires_at IS NULL OR expires_at > NOW();

COMMIT;
