-- ============================================================
-- ADVANCED GRAPHQL BACKEND DATA MODEL
--
-- PostgreSQL 15+
--
-- Features:
--   1. GraphQL-oriented relational schema
--   2. Users, roles and permissions
--   3. Posts and nested comments
--   4. Authorization functions
--   5. Fragment and variable execution metadata
--   6. Query complexity controls
--   7. DataLoader-compatible batch retrieval
--   8. N+1 query measurement
--   9. Query execution auditing
--  10. Transaction-safe publishing operations
--
-- This script models the database layer of a GraphQL service.
-- PostgreSQL does not parse or execute GraphQL documents natively.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS graphql_app;

SET search_path TO graphql_app, public;

-- ============================================================
-- ENUMERATIONS
-- ============================================================

CREATE TYPE user_role AS ENUM (
    'ADMIN',
    'EDITOR',
    'USER',
    'GUEST'
);

CREATE TYPE post_status AS ENUM (
    'DRAFT',
    'PUBLISHED',
    'ARCHIVED'
);

CREATE TYPE execution_status AS ENUM (
    'SUCCESS',
    'VALIDATION_ERROR',
    'AUTHORIZATION_ERROR',
    'EXECUTION_ERROR'
);

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    username VARCHAR(80) NOT NULL UNIQUE,

    email VARCHAR(254) NOT NULL UNIQUE,

    role user_role NOT NULL DEFAULT 'USER',

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT username_not_empty
        CHECK (length(trim(username)) > 0),

    CONSTRAINT email_not_empty
        CHECK (length(trim(email)) > 0)
);

-- ============================================================
-- POSTS
-- ============================================================

CREATE TABLE posts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    title VARCHAR(250) NOT NULL,

    body TEXT NOT NULL,

    author_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    status post_status NOT NULL DEFAULT 'DRAFT',

    version INTEGER NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_post_title
        CHECK (length(trim(title)) > 0),

    CONSTRAINT valid_post_body
        CHECK (length(trim(body)) > 0),

    CONSTRAINT positive_post_version
        CHECK (version > 0)
);

CREATE INDEX idx_posts_author
    ON posts(author_id);

CREATE INDEX idx_posts_published
    ON posts(created_at DESC)
    WHERE status = 'PUBLISHED';

CREATE INDEX idx_posts_author_status
    ON posts(author_id, status, id);

-- ============================================================
-- COMMENTS
-- ============================================================

CREATE TABLE comments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    post_id BIGINT NOT NULL
        REFERENCES posts(id)
        ON DELETE CASCADE,

    author_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    content TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_comment_content
        CHECK (
            length(trim(content)) > 0
            AND length(content) <= 10000
        )
);

CREATE INDEX idx_comments_post
    ON comments(post_id, id);

CREATE INDEX idx_comments_author
    ON comments(author_id);

-- ============================================================
-- PERMISSION MODEL
-- ============================================================

CREATE TABLE role_permissions (
    role user_role NOT NULL,

    permission VARCHAR(100) NOT NULL,

    PRIMARY KEY (role, permission)
);

INSERT INTO role_permissions(role, permission)
VALUES
    ('ADMIN', 'READ_ALL_USERS'),
    ('ADMIN', 'READ_PRIVATE_POSTS'),
    ('ADMIN', 'READ_ALL_EMAILS'),
    ('ADMIN', 'PUBLISH_POSTS'),
    ('ADMIN', 'CREATE_POSTS'),
    ('EDITOR', 'READ_PRIVATE_POSTS'),
    ('EDITOR', 'CREATE_POSTS'),
    ('EDITOR', 'PUBLISH_POSTS'),
    ('USER', 'CREATE_COMMENTS'),
    ('USER', 'READ_PUBLISHED_POSTS'),
    ('GUEST', 'READ_PUBLISHED_POSTS');

-- ============================================================
-- GRAPHQL EXECUTION AUDIT
-- ============================================================

CREATE TABLE graphql_execution_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id UUID NOT NULL UNIQUE,

    user_id BIGINT
        REFERENCES users(id)
        ON DELETE SET NULL,

    operation_name VARCHAR(150),

    operation_type VARCHAR(20) NOT NULL DEFAULT 'QUERY',

    query_hash VARCHAR(128),

    complexity_score INTEGER NOT NULL DEFAULT 0,

    database_query_count INTEGER NOT NULL DEFAULT 0,

    execution_status execution_status NOT NULL,

    error_code VARCHAR(100),

    execution_time_ms NUMERIC(12, 3),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_operation_type
        CHECK (operation_type IN ('QUERY', 'MUTATION', 'SUBSCRIPTION')),

    CONSTRAINT nonnegative_complexity
        CHECK (complexity_score >= 0),

    CONSTRAINT nonnegative_query_count
        CHECK (database_query_count >= 0),

    CONSTRAINT nonnegative_execution_time
        CHECK (
            execution_time_ms IS NULL
            OR execution_time_ms >= 0
        )
);

CREATE INDEX idx_graphql_execution_created
    ON graphql_execution_log(created_at DESC);

CREATE INDEX idx_graphql_execution_user
    ON graphql_execution_log(user_id, created_at DESC);

CREATE INDEX idx_graphql_execution_status
    ON graphql_execution_log(execution_status, created_at DESC);

-- ============================================================
-- GRAPHQL FIELD METADATA
--
-- A real GraphQL schema is maintained by the application.
-- This table provides a relational representation of field
-- metadata for auditing and policy analysis.
-- ============================================================

CREATE TABLE graphql_fields (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    parent_type VARCHAR(100) NOT NULL,

    field_name VARCHAR(100) NOT NULL,

    return_type VARCHAR(100) NOT NULL,

    requires_authentication BOOLEAN NOT NULL DEFAULT FALSE,

    required_permission VARCHAR(100),

    complexity_weight INTEGER NOT NULL DEFAULT 1,

    is_list BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(parent_type, field_name),

    CHECK (complexity_weight > 0)
);

INSERT INTO graphql_fields(
    parent_type,
    field_name,
    return_type,
    requires_authentication,
    required_permission,
    complexity_weight,
    is_list
)
VALUES
    ('Query', 'posts', '[Post]', FALSE, NULL, 5, TRUE),
    ('Query', 'me', 'User', TRUE, NULL, 1, FALSE),
    ('Query', 'user', 'User', TRUE, 'READ_ALL_USERS', 2, FALSE),
    ('Post', 'id', 'ID', FALSE, NULL, 1, FALSE),
    ('Post', 'title', 'String', FALSE, NULL, 1, FALSE),
    ('Post', 'author', 'User', FALSE, NULL, 2, FALSE),
    ('Post', 'comments', '[Comment]', FALSE, NULL, 5, TRUE),
    ('User', 'email', 'String', TRUE, 'READ_ALL_EMAILS', 1, FALSE),
    ('User', 'posts', '[Post]', TRUE, NULL, 5, TRUE),
    ('Comment', 'content', 'String', TRUE, NULL, 1, FALSE);

-- ============================================================
-- CURRENT PRINCIPAL
--
-- The application sets this transaction-local setting after
-- authentication. It is not a substitute for trusted identity
-- verification or protection against arbitrary SQL execution.
-- ============================================================

CREATE FUNCTION current_user_id()
RETURNS BIGINT
LANGUAGE SQL
STABLE
AS $$
    SELECT NULLIF(
        current_setting('app.user_id', TRUE), ''
    )::BIGINT;
$$;

CREATE FUNCTION has_permission(
    p_permission VARCHAR
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM users u
        JOIN role_permissions rp
          ON rp.role = u.role
        WHERE u.id = current_user_id()
          AND u.active = TRUE
          AND rp.permission = p_permission
    );
$$;

CREATE FUNCTION is_post_readable(
    p_post_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM posts p
        WHERE p.id = p_post_id
          AND (
              p.status = 'PUBLISHED'
              OR p.author_id = current_user_id()
              OR has_permission('READ_PRIVATE_POSTS')
          )
    );
$$;

CREATE FUNCTION can_read_user_email(
    p_user_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT (
        current_user_id() = p_user_id
        OR has_permission('READ_ALL_EMAILS')
    );
$$;

-- ============================================================
-- GRAPHQL DATA RETRIEVAL FUNCTIONS
-- ============================================================

CREATE FUNCTION resolve_published_posts()
RETURNS TABLE (
    post_id BIGINT,
    title VARCHAR,
    author_id BIGINT,
    author_name VARCHAR
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        p.id,
        p.title,
        u.id,
        u.username
    FROM posts p
    JOIN users u
      ON u.id = p.author_id
    WHERE p.status = 'PUBLISHED'
    ORDER BY p.created_at DESC, p.id;
$$;

CREATE FUNCTION resolve_post(
    p_post_id BIGINT
)
RETURNS TABLE (
    post_id BIGINT,
    title VARCHAR,
    body TEXT,
    author_id BIGINT,
    status post_status
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF NOT is_post_readable(p_post_id) THEN
        RAISE EXCEPTION 'Post access denied'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT
        p.id,
        p.title,
        p.body,
        p.author_id,
        p.status
    FROM posts p
    WHERE p.id = p_post_id;
END;
$$;

CREATE FUNCTION resolve_user(
    p_user_id BIGINT
)
RETURNS TABLE (
    user_id BIGINT,
    username VARCHAR,
    email VARCHAR
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF current_user_id() IS NULL THEN
        RAISE EXCEPTION 'Authentication required'
            USING ERRCODE = '28000';
    END IF;

    IF NOT has_permission('READ_ALL_USERS')
       AND current_user_id() <> p_user_id THEN
        RAISE EXCEPTION 'User access denied'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT
        u.id,
        u.username,
        CASE
            WHEN can_read_user_email(u.id) THEN u.email
            ELSE NULL
        END
    FROM users u
    WHERE u.id = p_user_id;
END;
$$;

-- ============================================================
-- DATALOADER-COMPATIBLE BATCH QUERY
--
-- One database call returns comments for multiple posts.
-- This avoids the N+1 pattern:
--
-- N+1:
--   SELECT posts;
--   SELECT comments WHERE post_id = 101;
--   SELECT comments WHERE post_id = 102;
--   SELECT comments WHERE post_id = 103;
--
-- Batched:
--   SELECT comments WHERE post_id = ANY(array_of_ids);
-- ============================================================

CREATE FUNCTION resolve_comments_batch(
    p_post_ids BIGINT[]
)
RETURNS TABLE (
    post_id BIGINT,
    comment_id BIGINT,
    content TEXT,
    author_id BIGINT,
    author_name VARCHAR
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_post_ids IS NULL THEN
        RAISE EXCEPTION 'Post ID array cannot be NULL';
    END IF;

    IF cardinality(p_post_ids) > 500 THEN
        RAISE EXCEPTION 'Maximum batch size is 500';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM unnest(p_post_ids) AS requested(id)
        WHERE requested.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Batch contains NULL post IDs';
    END IF;

    RETURN QUERY
    SELECT
        c.post_id,
        c.id,
        c.content,
        u.id,
        u.username
    FROM comments c
    JOIN users u
      ON u.id = c.author_id
    WHERE c.post_id = ANY(p_post_ids)
      AND is_post_readable(c.post_id)
    ORDER BY c.post_id, c.id;
END;
$$;

-- ============================================================
-- N+1 QUERY COMPARISON
-- ============================================================

CREATE FUNCTION count_n_plus_one_queries(
    p_parent_count INTEGER
)
RETURNS INTEGER
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT GREATEST(p_parent_count, 0) + 1;
$$;

CREATE FUNCTION count_batched_queries(
    p_parent_count INTEGER
)
RETURNS INTEGER
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_parent_count <= 0 THEN 1
        ELSE 2
    END;
$$;

-- ============================================================
-- QUERY COMPLEXITY ESTIMATION
--
-- A simplified static field-weight model.
-- Production GraphQL systems should also consider list
-- pagination, argument values, recursion and resolver cost.
-- ============================================================

CREATE FUNCTION estimate_query_complexity(
    p_field_names TEXT[]
)
RETURNS INTEGER
LANGUAGE SQL
STABLE
AS $$
    SELECT COALESCE(
        SUM(gf.complexity_weight),
        0
    )::INTEGER
    FROM unnest(p_field_names) AS requested(field_name)
    JOIN graphql_fields gf
      ON gf.field_name = requested.field_name;
$$;

CREATE FUNCTION validate_query_complexity(
    p_complexity INTEGER,
    p_maximum INTEGER DEFAULT 100
)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_complexity < 0 OR p_maximum <= 0 THEN
        RAISE EXCEPTION 'Invalid complexity parameters';
    END IF;

    IF p_complexity > p_maximum THEN
        RAISE EXCEPTION
            'Query complexity % exceeds maximum %',
            p_complexity,
            p_maximum;
    END IF;

    RETURN TRUE;
END;
$$;

-- ============================================================
-- POST MANAGEMENT FUNCTION
-- ============================================================

CREATE FUNCTION publish_post(
    p_post_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    IF NOT has_permission('PUBLISH_POSTS') THEN
        RAISE EXCEPTION 'Publishing permission required'
            USING ERRCODE = '42501';
    END IF;

    UPDATE posts
    SET status = 'PUBLISHED',
        version = version + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_post_id
      AND status = 'DRAFT';

    GET DIAGNOSTICS affected_rows = ROW_COUNT;

    IF affected_rows = 0 THEN
        RAISE EXCEPTION
            'Post does not exist or is not in draft state';
    END IF;

    RETURN TRUE;
END;
$$;

-- ============================================================
-- VERSION AND TIMESTAMP TRIGGER
-- ============================================================

CREATE FUNCTION maintain_post_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.title IS DISTINCT FROM OLD.title
       OR NEW.body IS DISTINCT FROM OLD.body
       OR NEW.status IS DISTINCT FROM OLD.status THEN

        NEW.version := OLD.version + 1;
        NEW.updated_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_post_version
BEFORE UPDATE ON posts
FOR EACH ROW
EXECUTE FUNCTION maintain_post_version();

-- ============================================================
-- REPORTING VIEWS
-- ============================================================

CREATE VIEW published_post_statistics AS
SELECT
    p.id AS post_id,
    p.title,
    u.username AS author,
    COUNT(c.id) AS comment_count,
    MAX(c.created_at) AS latest_comment
FROM posts p
JOIN users u
  ON u.id = p.author_id
LEFT JOIN comments c
  ON c.post_id = p.id
WHERE p.status = 'PUBLISHED'
GROUP BY p.id, p.title, u.username;

CREATE VIEW graphql_execution_statistics AS
SELECT
    execution_status,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time_ms), 3) AS average_time_ms,
    ROUND(AVG(complexity_score), 2) AS average_complexity,
    SUM(database_query_count) AS database_queries
FROM graphql_execution_log
GROUP BY execution_status;

-- ============================================================
-- SAMPLE DATA
-- ============================================================

INSERT INTO users(username, email, role)
VALUES
    ('atul', 'atul@example.com', 'ADMIN'),
    ('rahul', 'rahul@example.com', 'EDITOR'),
    ('priya', 'priya@example.com', 'USER'),
    ('guest_user', 'guest@example.com', 'GUEST');

INSERT INTO posts(title, body, author_id, status)
VALUES
    (
        'GraphQL Advanced Architecture',
        'Nested queries, fragments and variables.',
        1,
        'PUBLISHED'
    ),
    (
        'DataLoader Optimization',
        'Batching and caching database operations.',
        2,
        'PUBLISHED'
    ),
    (
        'Private GraphQL Draft',
        'Unpublished implementation notes.',
        1,
        'DRAFT'
    ),
    (
        'GraphQL Security',
        'Authorization and query complexity.',
        2,
        'PUBLISHED'
    );

INSERT INTO comments(post_id, author_id, content)
VALUES
    (1, 2, 'Excellent explanation.'),
    (1, 3, 'Useful architecture.'),
    (2, 1, 'Batching is important.'),
    (2, 3, 'Caching improves performance.'),
    (4, 1, 'Security must be enforced at resolvers.');

-- ============================================================
-- DEMONSTRATION: TRANSACTION-LOCAL IDENTITY
-- ============================================================

SELECT set_config('app.user_id', '1', TRUE);

-- ============================================================
-- QUERY 1: NESTED POST AND AUTHOR RETRIEVAL
-- ============================================================

SELECT
    p.id,
    p.title,
    jsonb_build_object(
        'id', u.id,
        'username', u.username
    ) AS author
FROM posts p
JOIN users u
  ON u.id = p.author_id
WHERE p.status = 'PUBLISHED'
ORDER BY p.id;

-- ============================================================
-- QUERY 2: NESTED COMMENTS WITH AUTHORS
-- ============================================================

SELECT
    p.id,
    p.title,
    COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'id', c.id,
                'content', c.content,
                'author', jsonb_build_object(
                    'id', u.id,
                    'name', u.username
                )
            )
            ORDER BY c.id
        ) FILTER (WHERE c.id IS NOT NULL),
        '[]'::JSONB
    ) AS comments
FROM posts p
LEFT JOIN comments c
  ON c.post_id = p.id
LEFT JOIN users u
  ON u.id = c.author_id
WHERE p.status = 'PUBLISHED'
GROUP BY p.id, p.title
ORDER BY p.id;

-- ============================================================
-- QUERY 3: BATCHED COMMENTS
-- ============================================================

SELECT *
FROM resolve_comments_batch(ARRAY[1, 2, 4]::BIGINT[]);

-- ============================================================
-- QUERY 4: AUTHORIZATION
-- ============================================================

SELECT
    id,
    title,
    status,
    is_post_readable(id) AS can_read
FROM posts
ORDER BY id;

-- ============================================================
-- QUERY 5: EMAIL AUTHORIZATION
-- ============================================================

SELECT
    id,
    username,
    CASE
        WHEN can_read_user_email(id) THEN email
        ELSE NULL
    END AS visible_email
FROM users
ORDER BY id;

-- ============================================================
-- QUERY 6: QUERY COMPLEXITY
-- ============================================================

SELECT estimate_query_complexity(
    ARRAY[
        'posts',
        'title',
        'author',
        'comments'
    ]
);

SELECT validate_query_complexity(15, 100);

-- ============================================================
-- QUERY 7: N+1 PERFORMANCE COMPARISON
-- ============================================================

SELECT
    parent_count,
    count_n_plus_one_queries(parent_count)
        AS n_plus_one_queries,
    count_batched_queries(parent_count)
        AS batched_queries
FROM (
    VALUES (1), (10), (100), (500)
) AS scenarios(parent_count);

-- ============================================================
-- QUERY 8: AGGREGATION
-- ============================================================

SELECT
    author_id,
    COUNT(*) AS post_count,
    COUNT(*) FILTER (
        WHERE status = 'PUBLISHED'
    ) AS published_count,
    COUNT(*) FILTER (
        WHERE status = 'DRAFT'
    ) AS draft_count
FROM posts
GROUP BY author_id
ORDER BY author_id;

-- ============================================================
-- QUERY 9: EXECUTION AUDIT
-- ============================================================

INSERT INTO graphql_execution_log(
    request_id,
    user_id,
    operation_name,
    operation_type,
    complexity_score,
    database_query_count,
    execution_status,
    execution_time_ms
)
VALUES
    (
        gen_random_uuid(),
        1,
        'PublishedPosts',
        'QUERY',
        20,
        2,
        'SUCCESS',
        12.500
    ),
    (
        gen_random_uuid(),
        3,
        'PrivateUserLookup',
        'QUERY',
        5,
        0,
        'AUTHORIZATION_ERROR',
        1.200
    ),
    (
        gen_random_uuid(),
        2,
        'NestedComments',
        'QUERY',
        35,
        2,
        'SUCCESS',
        18.300
    );

SELECT *
FROM graphql_execution_statistics
ORDER BY execution_status;

-- ============================================================
-- QUERY 10: COMMON TABLE EXPRESSION
-- ============================================================

WITH post_metrics AS (
    SELECT
        p.id,
        p.title,
        p.author_id,
        COUNT(c.id) AS comment_count
    FROM posts p
    LEFT JOIN comments c
      ON c.post_id = p.id
    WHERE p.status = 'PUBLISHED'
    GROUP BY p.id, p.title, p.author_id
)
SELECT
    pm.id,
    pm.title,
    u.username,
    pm.comment_count
FROM post_metrics pm
JOIN users u
  ON u.id = pm.author_id
ORDER BY pm.comment_count DESC, pm.id;

-- ============================================================
-- QUERY 11: VALIDATION OF FIELD METADATA
-- ============================================================

SELECT
    parent_type,
    field_name,
    return_type,
    requires_authentication,
    required_permission,
    complexity_weight
FROM graphql_fields
WHERE requires_authentication = TRUE
   OR required_permission IS NOT NULL
ORDER BY parent_type, field_name;

-- ============================================================
-- QUERY 12: POST VERSION VALIDATION
-- ============================================================

UPDATE posts
SET title = 'GraphQL Advanced Architecture - Revised'
WHERE id = 1;

SELECT id, title, version, updated_at
FROM posts
WHERE id = 1;

-- ============================================================
-- QUERY 13: TRANSACTIONAL PUBLISHING
-- ============================================================

SAVEPOINT before_publish;

SELECT publish_post(3);

SELECT id, title, status, version
FROM posts
WHERE id = 3;

-- ============================================================
-- QUERY 14: TRANSACTION ROLLBACK DEMONSTRATION
-- ============================================================

ROLLBACK TO SAVEPOINT before_publish;

SELECT id, title, status
FROM posts
WHERE id = 3;

-- ============================================================
-- QUERY 15: FINAL DATA QUALITY CHECKS
-- ============================================================

SELECT
    COUNT(*) AS total_users
FROM users;

SELECT
    COUNT(*) AS total_posts,
    COUNT(*) FILTER (
        WHERE status = 'PUBLISHED'
    ) AS published_posts,
    COUNT(*) FILTER (
        WHERE status = 'DRAFT'
    ) AS draft_posts
FROM posts;

SELECT
    COUNT(*) AS orphaned_comments
FROM comments c
LEFT JOIN posts p
  ON p.id = c.post_id
WHERE p.id IS NULL;

COMMIT;

-- ============================================================
-- END OF GRAPHQL DATABASE MODEL
-- ============================================================
