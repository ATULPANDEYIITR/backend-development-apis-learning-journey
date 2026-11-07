/*
================================================================
SECURE SECRETS MANAGEMENT
PostgreSQL 15+

Scope:
- Environment configuration metadata
- Secret-manager inventory
- Credential versions
- Access-control policies
- Rotation workflows
- Expiry and revocation
- Audit events
- Rotation approvals
- Eligibility evaluation

SECURITY DESIGN:
Actual secret values are NOT stored in PostgreSQL.
Credentials remain in an external secrets manager.
This database stores secret identifiers, provider references,
version metadata, lifecycle states, and audit information.

Execute using a database role authorized to create schemas,
tables, functions, triggers, and procedures.
================================================================
*/

BEGIN;

-- ============================================================
-- 1. Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS secrets_mgmt;

SET search_path TO secrets_mgmt, public;

-- ============================================================
-- 2. Enumerated domain types
-- ============================================================

CREATE TYPE secret_state AS ENUM (
    'ACTIVE',
    'STAGED',
    'RETIRED',
    'REVOKED'
);

CREATE TYPE rotation_state AS ENUM (
    'REQUESTED',
    'STAGED',
    'VERIFIED',
    'ACTIVATED',
    'FAILED',
    'CANCELLED'
);

CREATE TYPE access_action AS ENUM (
    'READ',
    'CREATE',
    'ROTATE',
    'REVOKE',
    'METADATA'
);

CREATE TYPE audit_outcome AS ENUM (
    'SUCCESS',
    'DENIED',
    'FAILED'
);

-- ============================================================
-- 3. Application identities
-- ============================================================

CREATE TABLE principals (
    principal_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    principal_name VARCHAR(128) NOT NULL UNIQUE,

    principal_type VARCHAR(30) NOT NULL
        CHECK (
            principal_type IN (
                'APPLICATION',
                'HUMAN',
                'SERVICE',
                'AUDITOR'
            )
        ),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. Secret-manager providers
-- ============================================================

CREATE TABLE secret_providers (
    provider_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    provider_name VARCHAR(100) NOT NULL UNIQUE,

    provider_type VARCHAR(30) NOT NULL
        CHECK (
            provider_type IN (
                'VAULT',
                'CLOUD_SECRET_MANAGER',
                'HSM',
                'KMS',
                'DEVELOPMENT'
            )
        ),

    endpoint_reference TEXT,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- endpoint_reference is configuration metadata.
-- Never store provider authentication credentials here.

-- ============================================================
-- 5. Secret inventory
-- ============================================================

CREATE TABLE secrets (
    secret_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    secret_name VARCHAR(128) NOT NULL UNIQUE,

    description TEXT,

    provider_id BIGINT NOT NULL
        REFERENCES secret_providers(provider_id),

    provider_secret_reference VARCHAR(512) NOT NULL,

    environment VARCHAR(20) NOT NULL
        CHECK (
            environment IN (
                'DEVELOPMENT',
                'TESTING',
                'STAGING',
                'PRODUCTION'
            )
        ),

    owner_id BIGINT NOT NULL
        REFERENCES principals(principal_id),

    rotation_interval_days INTEGER NOT NULL DEFAULT 90
        CHECK (rotation_interval_days BETWEEN 1 AND 365),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (provider_id, provider_secret_reference)
);

-- ============================================================
-- 6. Secret versions
-- ============================================================

CREATE TABLE secret_versions (
    version_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    secret_id BIGINT NOT NULL
        REFERENCES secrets(secret_id),

    version_number INTEGER NOT NULL
        CHECK (version_number > 0),

    state secret_state NOT NULL,

    provider_version_reference VARCHAR(512) NOT NULL,

    fingerprint_sha256 CHAR(64),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    activated_at TIMESTAMPTZ,

    expires_at TIMESTAMPTZ,

    revoked_at TIMESTAMPTZ,

    created_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    UNIQUE (secret_id, version_number),

    UNIQUE (secret_id, provider_version_reference),

    CHECK (
        fingerprint_sha256 IS NULL
        OR fingerprint_sha256 ~ '^[0-9a-f]{64}$'
    ),

    CHECK (
        expires_at IS NULL
        OR expires_at > created_at
    ),

    CHECK (
        revoked_at IS NULL
        OR revoked_at >= created_at
    )
);

-- One active version per secret.
CREATE UNIQUE INDEX uq_secret_one_active_version
    ON secret_versions(secret_id)
    WHERE state = 'ACTIVE';

-- One staged version per secret.
CREATE UNIQUE INDEX uq_secret_one_staged_version
    ON secret_versions(secret_id)
    WHERE state = 'STAGED';

CREATE INDEX idx_secret_versions_lifecycle
    ON secret_versions(secret_id, state, version_number DESC);

CREATE INDEX idx_secret_versions_expiry
    ON secret_versions(expires_at)
    WHERE state = 'ACTIVE' AND expires_at IS NOT NULL;

-- ============================================================
-- 7. Access-control roles
-- ============================================================

CREATE TABLE access_roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    role_name VARCHAR(64) NOT NULL UNIQUE,

    description TEXT
);

CREATE TABLE role_permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    role_id BIGINT NOT NULL
        REFERENCES access_roles(role_id),

    action access_action NOT NULL,

    UNIQUE (role_id, action)
);

CREATE TABLE principal_roles (
    principal_id BIGINT NOT NULL
        REFERENCES principals(principal_id),

    role_id BIGINT NOT NULL
        REFERENCES access_roles(role_id),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (principal_id, role_id)
);

-- ============================================================
-- 8. Secret-specific access grants
-- ============================================================

CREATE TABLE secret_access_grants (
    grant_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    secret_id BIGINT NOT NULL
        REFERENCES secrets(secret_id),

    principal_id BIGINT NOT NULL
        REFERENCES principals(principal_id),

    action access_action NOT NULL,

    granted_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CHECK (
        expires_at IS NULL
        OR expires_at > granted_at
    ),

    UNIQUE (secret_id, principal_id, action)
);

CREATE INDEX idx_secret_grants_principal
    ON secret_access_grants(principal_id, secret_id);

-- ============================================================
-- 9. Rotation workflow
-- ============================================================

CREATE TABLE rotation_requests (
    rotation_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    secret_id BIGINT NOT NULL
        REFERENCES secrets(secret_id),

    old_version_id BIGINT
        REFERENCES secret_versions(version_id),

    new_version_id BIGINT
        REFERENCES secret_versions(version_id),

    requested_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    approved_by BIGINT
        REFERENCES principals(principal_id),

    state rotation_state NOT NULL DEFAULT 'REQUESTED',

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    staged_at TIMESTAMPTZ,

    verified_at TIMESTAMPTZ,

    activated_at TIMESTAMPTZ,

    failure_reason TEXT,

    CHECK (
        old_version_id IS NULL
        OR new_version_id IS NULL
        OR old_version_id <> new_version_id
    )
);

CREATE INDEX idx_rotation_requests_state
    ON rotation_requests(state, requested_at);

CREATE INDEX idx_rotation_requests_secret
    ON rotation_requests(secret_id, requested_at DESC);

-- ============================================================
-- 10. Rotation verification
-- ============================================================

CREATE TABLE rotation_verifications (
    verification_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    rotation_id BIGINT NOT NULL
        REFERENCES rotation_requests(rotation_id),

    verifier_name VARCHAR(128) NOT NULL,

    verification_passed BOOLEAN NOT NULL,

    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    details TEXT
);

-- Details must contain diagnostic metadata only.
-- Never include credentials, passwords, tokens, or key material.

-- ============================================================
-- 11. Audit events
-- ============================================================

CREATE TABLE secret_audit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    secret_id BIGINT
        REFERENCES secrets(secret_id),

    principal_id BIGINT
        REFERENCES principals(principal_id),

    action access_action NOT NULL,

    version_id BIGINT
        REFERENCES secret_versions(version_id),

    outcome audit_outcome NOT NULL,

    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    source_ip INET,

    correlation_id UUID,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    CHECK (
        NOT (
            details ? 'secret_value'
            OR details ? 'password'
            OR details ? 'token'
            OR details ? 'private_key'
        )
    )
);

CREATE INDEX idx_secret_audit_time
    ON secret_audit_events(event_time DESC);

CREATE INDEX idx_secret_audit_secret
    ON secret_audit_events(secret_id, event_time DESC);

CREATE INDEX idx_secret_audit_principal
    ON secret_audit_events(principal_id, event_time DESC);

-- ============================================================
-- 12. Access-control evaluation function
-- ============================================================

CREATE OR REPLACE FUNCTION has_secret_permission(
    p_principal_id BIGINT,
    p_secret_id BIGINT,
    p_action access_action
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM principals p
        JOIN secret_access_grants g
            ON g.principal_id = p.principal_id
        WHERE p.principal_id = p_principal_id
          AND g.secret_id = p_secret_id
          AND g.action = p_action
          AND p.enabled = TRUE
          AND g.enabled = TRUE
          AND (
              g.expires_at IS NULL
              OR g.expires_at > NOW()
          )
    );
$$;

-- ============================================================
-- 13. Audit insertion function
-- ============================================================

CREATE OR REPLACE FUNCTION record_secret_audit(
    p_secret_id BIGINT,
    p_principal_id BIGINT,
    p_action access_action,
    p_version_id BIGINT,
    p_outcome audit_outcome,
    p_details JSONB DEFAULT '{}'::JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id BIGINT;
BEGIN
    IF p_details ?| ARRAY[
        'secret_value',
        'password',
        'token',
        'private_key'
    ] THEN
        RAISE EXCEPTION
            'Sensitive credential content is prohibited in audit details';
    END IF;

    INSERT INTO secret_audit_events (
        secret_id,
        principal_id,
        action,
        version_id,
        outcome,
        details
    )
    VALUES (
        p_secret_id,
        p_principal_id,
        p_action,
        p_version_id,
        p_outcome,
        COALESCE(p_details, '{}'::JSONB)
    )
    RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$;

-- ============================================================
-- 14. Secret-version lifecycle trigger
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_secret_version_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.state NOT IN ('ACTIVE', 'STAGED') THEN
            RAISE EXCEPTION
                'New versions must be ACTIVE or STAGED';
        END IF;

        IF NEW.state = 'ACTIVE'
           AND NEW.activated_at IS NULL THEN
            NEW.activated_at := NOW();
        END IF;

        RETURN NEW;
    END IF;

    IF OLD.state = 'REVOKED' THEN
        RAISE EXCEPTION
            'Revoked versions are immutable';
    END IF;

    IF OLD.state = NEW.state THEN
        IF (
            OLD.secret_id,
            OLD.version_number,
            OLD.provider_version_reference,
            OLD.fingerprint_sha256,
            OLD.created_by
        ) IS DISTINCT FROM (
            NEW.secret_id,
            NEW.version_number,
            NEW.provider_version_reference,
            NEW.fingerprint_sha256,
            NEW.created_by
        ) THEN
            RAISE EXCEPTION
                'Version identity fields cannot be modified';
        END IF;

        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.state = 'STAGED' AND NEW.state IN ('ACTIVE', 'REVOKED'))
        OR
        (OLD.state = 'ACTIVE' AND NEW.state IN ('RETIRED', 'REVOKED'))
        OR
        (OLD.state = 'RETIRED' AND NEW.state = 'REVOKED')
    ) THEN
        RAISE EXCEPTION
            'Invalid secret lifecycle transition: % -> %',
            OLD.state,
            NEW.state;
    END IF;

    IF NEW.state = 'ACTIVE' THEN
        NEW.activated_at := NOW();
    END IF;

    IF NEW.state = 'REVOKED' THEN
        NEW.revoked_at := NOW();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_secret_version_transition
BEFORE INSERT OR UPDATE
ON secret_versions
FOR EACH ROW
EXECUTE FUNCTION enforce_secret_version_transition();

-- ============================================================
-- 15. Rotation-state trigger
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_rotation_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.state IN ('ACTIVATED', 'FAILED', 'CANCELLED') THEN
            RAISE EXCEPTION
                'Terminal rotation requests cannot be modified';
        END IF;

        IF OLD.state = NEW.state THEN
            RETURN NEW;
        END IF;

        IF NOT (
            (OLD.state = 'REQUESTED' AND NEW.state IN ('STAGED', 'FAILED', 'CANCELLED'))
            OR
            (OLD.state = 'STAGED' AND NEW.state IN ('VERIFIED', 'FAILED', 'CANCELLED'))
            OR
            (OLD.state = 'VERIFIED' AND NEW.state IN ('ACTIVATED', 'FAILED'))
        ) THEN
            RAISE EXCEPTION
                'Invalid rotation transition: % -> %',
                OLD.state,
                NEW.state;
        END IF;

        IF NEW.state = 'STAGED' THEN
            NEW.staged_at := NOW();
        ELSIF NEW.state = 'VERIFIED' THEN
            NEW.verified_at := NOW();
        ELSIF NEW.state = 'ACTIVATED' THEN
            NEW.activated_at := NOW();
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_rotation_transition
BEFORE UPDATE
ON rotation_requests
FOR EACH ROW
EXECUTE FUNCTION enforce_rotation_transition();

-- ============================================================
-- 16. Rotation activation procedure
-- ============================================================

CREATE OR REPLACE PROCEDURE activate_secret_rotation(
    p_rotation_id BIGINT,
    p_actor_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rotation rotation_requests%ROWTYPE;
    v_old_state secret_state;
    v_new_state secret_state;
BEGIN
    -- Serialize competing activation attempts.
    SELECT *
    INTO v_rotation
    FROM rotation_requests
    WHERE rotation_id = p_rotation_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rotation request not found';
    END IF;

    IF v_rotation.state <> 'VERIFIED' THEN
        RAISE EXCEPTION
            'Only verified rotations can be activated';
    END IF;

    IF v_rotation.approved_by IS NULL THEN
        RAISE EXCEPTION
            'Rotation approval is required';
    END IF;

    IF v_rotation.approved_by = v_rotation.requested_by THEN
        RAISE EXCEPTION
            'Requester cannot approve their own rotation';
    END IF;

    IF NOT has_secret_permission(
        p_actor_id,
        v_rotation.secret_id,
        'ROTATE'
    ) THEN
        RAISE EXCEPTION
            'Actor does not have rotation permission';
    END IF;

    SELECT state
    INTO v_new_state
    FROM secret_versions
    WHERE version_id = v_rotation.new_version_id
      AND secret_id = v_rotation.secret_id
    FOR UPDATE;

    IF NOT FOUND OR v_new_state <> 'STAGED' THEN
        RAISE EXCEPTION
            'New version is not in STAGED state';
    END IF;

    IF v_rotation.old_version_id IS NOT NULL THEN
        SELECT state
        INTO v_old_state
        FROM secret_versions
        WHERE version_id = v_rotation.old_version_id
          AND secret_id = v_rotation.secret_id
        FOR UPDATE;

        IF NOT FOUND OR v_old_state <> 'ACTIVE' THEN
            RAISE EXCEPTION
                'Old version is not ACTIVE';
        END IF;

        UPDATE secret_versions
        SET state = 'RETIRED'
        WHERE version_id = v_rotation.old_version_id;
    END IF;

    UPDATE secret_versions
    SET state = 'ACTIVE'
    WHERE version_id = v_rotation.new_version_id;

    UPDATE rotation_requests
    SET state = 'ACTIVATED'
    WHERE rotation_id = p_rotation_id;

    PERFORM record_secret_audit(
        v_rotation.secret_id,
        p_actor_id,
        'ROTATE',
        v_rotation.new_version_id,
        'SUCCESS',
        jsonb_build_object(
            'rotation_id', p_rotation_id,
            'operation', 'ACTIVATION'
        )
    );
END;
$$;

-- ============================================================
-- 17. Secret expiry and rotation eligibility view
-- ============================================================

CREATE OR REPLACE VIEW secret_rotation_status AS
SELECT
    s.secret_id,
    s.secret_name,
    s.environment,
    s.rotation_interval_days,
    sv.version_number,
    sv.state,
    sv.activated_at,
    sv.expires_at,

    CASE
        WHEN sv.state <> 'ACTIVE'
            THEN 'NOT_ACTIVE'

        WHEN sv.expires_at IS NOT NULL
             AND sv.expires_at <= NOW()
            THEN 'EXPIRED'

        WHEN sv.activated_at IS NOT NULL
             AND sv.activated_at
                 + make_interval(days => s.rotation_interval_days)
                 <= NOW()
            THEN 'ROTATION_DUE'

        ELSE 'CURRENT'
    END AS rotation_status

FROM secrets s
LEFT JOIN secret_versions sv
    ON sv.secret_id = s.secret_id
   AND sv.state = 'ACTIVE';

-- ============================================================
-- 18. Expiry monitoring
-- ============================================================

CREATE OR REPLACE VIEW expiring_secrets AS
SELECT
    s.secret_name,
    s.environment,
    sv.version_number,
    sv.expires_at,
    EXTRACT(
        DAY FROM sv.expires_at - NOW()
    ) AS days_remaining

FROM secrets s
JOIN secret_versions sv
    ON sv.secret_id = s.secret_id

WHERE sv.state = 'ACTIVE'
  AND sv.expires_at IS NOT NULL
  AND sv.expires_at <= NOW() + INTERVAL '30 days';

-- ============================================================
-- 19. Sample providers and identities
-- ============================================================

INSERT INTO secret_providers (
    provider_name,
    provider_type,
    endpoint_reference
)
VALUES
(
    'Development Vault',
    'DEVELOPMENT',
    'internal-development-vault'
),
(
    'Production Vault',
    'VAULT',
    'production-vault-service'
);

INSERT INTO principals (
    principal_name,
    principal_type
)
VALUES
('payment-service', 'APPLICATION'),
('security-admin', 'HUMAN'),
('rotation-worker', 'SERVICE'),
('compliance-auditor', 'AUDITOR'),
('database-service', 'APPLICATION');

INSERT INTO access_roles (role_name, description)
VALUES
('APPLICATION_READER', 'Application secret retrieval'),
('SECURITY_ADMIN', 'Secret lifecycle administration'),
('ROTATION_SERVICE', 'Automated credential rotation'),
('AUDITOR', 'Metadata and audit inspection');

INSERT INTO role_permissions (role_id, action)
SELECT r.role_id, p.action
FROM access_roles r
CROSS JOIN (
    VALUES
        ('APPLICATION_READER', 'READ'::access_action),
        ('SECURITY_ADMIN', 'READ'::access_action),
        ('SECURITY_ADMIN', 'CREATE'::access_action),
        ('SECURITY_ADMIN', 'ROTATE'::access_action),
        ('SECURITY_ADMIN', 'REVOKE'::access_action),
        ('SECURITY_ADMIN', 'METADATA'::access_action),
        ('ROTATION_SERVICE', 'READ'::access_action),
        ('ROTATION_SERVICE', 'CREATE'::access_action),
        ('ROTATION_SERVICE', 'ROTATE'::access_action),
        ('AUDITOR', 'METADATA'::access_action)
) AS p(role_name, action)
WHERE r.role_name = p.role_name;

INSERT INTO principal_roles (principal_id, role_id)
SELECT p.principal_id, r.role_id
FROM (
    VALUES
        ('payment-service', 'APPLICATION_READER'),
        ('security-admin', 'SECURITY_ADMIN'),
        ('rotation-worker', 'ROTATION_SERVICE'),
        ('compliance-auditor', 'AUDITOR'),
        ('database-service', 'APPLICATION_READER')
) AS mapping(principal_name, role_name)
JOIN principals p
    ON p.principal_name = mapping.principal_name
JOIN access_roles r
    ON r.role_name = mapping.role_name;

-- ============================================================
-- 20. Sample secret inventory
-- ============================================================

INSERT INTO secrets (
    secret_name,
    description,
    provider_id,
    provider_secret_reference,
    environment,
    owner_id,
    rotation_interval_days
)
SELECT
    'payment-api-key',
    'Payment gateway API credential reference',
    sp.provider_id,
    'production/payment-api-key',
    'PRODUCTION',
    p.principal_id,
    60
FROM secret_providers sp
CROSS JOIN principals p
WHERE sp.provider_name = 'Production Vault'
  AND p.principal_name = 'security-admin';

INSERT INTO secrets (
    secret_name,
    description,
    provider_id,
    provider_secret_reference,
    environment,
    owner_id,
    rotation_interval_days
)
SELECT
    'database-password',
    'Application database credential reference',
    sp.provider_id,
    'production/database-password',
    'PRODUCTION',
    p.principal_id,
    90
FROM secret_providers sp
CROSS JOIN principals p
WHERE sp.provider_name = 'Production Vault'
  AND p.principal_name = 'security-admin';

-- ============================================================
-- 21. Secret-specific grants
-- ============================================================

INSERT INTO secret_access_grants (
    secret_id,
    principal_id,
    action,
    granted_by
)
SELECT
    s.secret_id,
    p.principal_id,
    g.action,
    admin.principal_id
FROM secrets s
JOIN principals admin
    ON admin.principal_name = 'security-admin'
CROSS JOIN principals p
CROSS JOIN (
    VALUES
        ('payment-service', 'READ'::access_action),
        ('database-service', 'READ'::access_action),
        ('rotation-worker', 'ROTATE'::access_action),
        ('rotation-worker', 'READ'::access_action),
        ('compliance-auditor', 'METADATA'::access_action)
) AS g(principal_name, action)
WHERE p.principal_name = g.principal_name;

-- ============================================================
-- 22. Initial secret versions
-- ============================================================

INSERT INTO secret_versions (
    secret_id,
    version_number,
    state,
    provider_version_reference,
    fingerprint_sha256,
    created_by,
    activated_at,
    expires_at
)
SELECT
    secret_id,
    1,
    'ACTIVE',
    secret_name || '/versions/1',
    repeat('a', 64),
    owner_id,
    NOW() - INTERVAL '10 days',
    NOW() + INTERVAL '80 days'
FROM secrets;

-- ============================================================
-- 23. Demonstration rotation request
-- ============================================================

INSERT INTO rotation_requests (
    secret_id,
    old_version_id,
    requested_by,
    state
)
SELECT
    s.secret_id,
    sv.version_id,
    worker.principal_id,
    'REQUESTED'
FROM secrets s
JOIN secret_versions sv
    ON sv.secret_id = s.secret_id
   AND sv.state = 'ACTIVE'
JOIN principals worker
    ON worker.principal_name = 'rotation-worker'
WHERE s.secret_name = 'payment-api-key';

-- ============================================================
-- 24. Create staged version
-- ============================================================

INSERT INTO secret_versions (
    secret_id,
    version_number,
    state,
    provider_version_reference,
    fingerprint_sha256,
    created_by
)
SELECT
    s.secret_id,
    2,
    'STAGED',
    s.secret_name || '/versions/2',
    repeat('b', 64),
    worker.principal_id
FROM secrets s
JOIN principals worker
    ON worker.principal_name = 'rotation-worker'
WHERE s.secret_name = 'payment-api-key';

UPDATE rotation_requests rr
SET
    new_version_id = sv.version_id,
    state = 'STAGED'
FROM secret_versions sv
WHERE rr.secret_id = sv.secret_id
  AND sv.version_number = 2
  AND rr.state = 'REQUESTED';

-- ============================================================
-- 25. Verify staged credential
-- ============================================================

INSERT INTO rotation_verifications (
    rotation_id,
    verifier_name,
    verification_passed,
    details
)
SELECT
    rotation_id,
    'payment-gateway-connectivity',
    TRUE,
    'New credential accepted by downstream verification service.'
FROM rotation_requests
WHERE state = 'STAGED';

UPDATE rotation_requests rr
SET state = 'VERIFIED'
WHERE rr.state = 'STAGED'
  AND EXISTS (
      SELECT 1
      FROM rotation_verifications rv
      WHERE rv.rotation_id = rr.rotation_id
        AND rv.verification_passed = TRUE
  );

-- ============================================================
-- 26. Independent rotation approval
-- ============================================================

UPDATE rotation_requests rr
SET approved_by = admin.principal_id
FROM principals admin
WHERE admin.principal_name = 'security-admin'
  AND rr.state = 'VERIFIED'
  AND rr.requested_by <> admin.principal_id;

-- ============================================================
-- 27. Demonstrate transactional activation
-- ============================================================

SAVEPOINT before_rotation_activation;

CALL activate_secret_rotation(
    (
        SELECT rotation_id
        FROM rotation_requests
        WHERE state = 'VERIFIED'
        ORDER BY rotation_id
        LIMIT 1
    ),
    (
        SELECT principal_id
        FROM principals
        WHERE principal_name = 'rotation-worker'
    )
);

RELEASE SAVEPOINT before_rotation_activation;

-- ============================================================
-- 28. Audit initial events
-- ============================================================

INSERT INTO secret_audit_events (
    secret_id,
    principal_id,
    action,
    version_id,
    outcome,
    details
)
SELECT
    s.secret_id,
    p.principal_id,
    'CREATE',
    sv.version_id,
    'SUCCESS',
    jsonb_build_object(
        'operation', 'INITIAL_VERSION_CREATION'
    )
FROM secrets s
JOIN secret_versions sv
    ON sv.secret_id = s.secret_id
   AND sv.version_number = 1
JOIN principals p
    ON p.principal_name = 'security-admin';

-- ============================================================
-- 29. Retrieval query: secret inventory
-- ============================================================

SELECT
    s.secret_name,
    s.environment,
    sp.provider_name,
    s.rotation_interval_days,
    s.enabled
FROM secrets s
JOIN secret_providers sp
    ON sp.provider_id = s.provider_id
ORDER BY s.secret_name;

-- ============================================================
-- 30. Retrieval query: version history
-- ============================================================

SELECT
    s.secret_name,
    sv.version_number,
    sv.state,
    sv.created_at,
    sv.activated_at,
    sv.expires_at,
    sv.revoked_at
FROM secret_versions sv
JOIN secrets s
    ON s.secret_id = sv.secret_id
ORDER BY
    s.secret_name,
    sv.version_number;

-- ============================================================
-- 31. Eligibility evaluation
-- ============================================================

SELECT
    secret_name,
    environment,
    version_number,
    rotation_status
FROM secret_rotation_status
ORDER BY secret_name;

-- ============================================================
-- 32. Access validation
-- ============================================================

SELECT
    p.principal_name,
    s.secret_name,
    a.action,
    has_secret_permission(
        p.principal_id,
        s.secret_id,
        a.action
    ) AS authorized
FROM principals p
CROSS JOIN secrets s
CROSS JOIN (
    VALUES
        ('READ'::access_action),
        ('ROTATE'::access_action),
        ('REVOKE'::access_action),
        ('METADATA'::access_action)
) AS a(action)
WHERE p.principal_name IN (
    'payment-service',
    'rotation-worker',
    'compliance-auditor'
)
ORDER BY
    p.principal_name,
    s.secret_name,
    a.action;

-- ============================================================
-- 33. Aggregation: lifecycle distribution
-- ============================================================

SELECT
    state,
    COUNT(*) AS version_count
FROM secret_versions
GROUP BY state
ORDER BY state;

-- ============================================================
-- 34. Reporting: rotation workflow
-- ============================================================

SELECT
    rr.rotation_id,
    s.secret_name,
    rr.state,
    requester.principal_name AS requested_by,
    approver.principal_name AS approved_by,
    rr.requested_at,
    rr.staged_at,
    rr.verified_at,
    rr.activated_at
FROM rotation_requests rr
JOIN secrets s
    ON s.secret_id = rr.secret_id
JOIN principals requester
    ON requester.principal_id = rr.requested_by
LEFT JOIN principals approver
    ON approver.principal_id = rr.approved_by
ORDER BY rr.requested_at DESC;

-- ============================================================
-- 35. Reporting: audit events
-- ============================================================

SELECT
    ae.event_id,
    s.secret_name,
    p.principal_name,
    ae.action,
    ae.outcome,
    ae.event_time,
    ae.details
FROM secret_audit_events ae
LEFT JOIN secrets s
    ON s.secret_id = ae.secret_id
LEFT JOIN principals p
    ON p.principal_id = ae.principal_id
ORDER BY ae.event_time DESC;

-- ============================================================
-- 36. Reporting: principal activity
-- ============================================================

SELECT
    COALESCE(p.principal_name, 'UNKNOWN') AS principal,
    ae.action,
    ae.outcome,
    COUNT(*) AS operation_count
FROM secret_audit_events ae
LEFT JOIN principals p
    ON p.principal_id = ae.principal_id
GROUP BY
    p.principal_name,
    ae.action,
    ae.outcome
ORDER BY operation_count DESC;

-- ============================================================
-- 37. Failure-case validation
-- ============================================================

-- This query identifies secrets without active versions.
SELECT
    s.secret_name
FROM secrets s
LEFT JOIN secret_versions sv
    ON sv.secret_id = s.secret_id
   AND sv.state = 'ACTIVE'
WHERE sv.version_id IS NULL;

-- This query identifies expired active credentials.
SELECT
    s.secret_name,
    sv.version_number,
    sv.expires_at
FROM secrets s
JOIN secret_versions sv
    ON sv.secret_id = s.secret_id
WHERE sv.state = 'ACTIVE'
  AND sv.expires_at <= NOW();

-- This query identifies pending rotations.
SELECT
    rotation_id,
    secret_id,
    state,
    requested_at
FROM rotation_requests
WHERE state IN ('REQUESTED', 'STAGED', 'VERIFIED');

-- This query identifies unsuccessful verifications.
SELECT
    rr.rotation_id,
    s.secret_name,
    rv.verifier_name,
    rv.verified_at
FROM rotation_verifications rv
JOIN rotation_requests rr
    ON rr.rotation_id = rv.rotation_id
JOIN secrets s
    ON s.secret_id = rr.secret_id
WHERE rv.verification_passed = FALSE;

-- ============================================================
-- 38. CTE: secret governance health
-- ============================================================

WITH active_versions AS (
    SELECT
        secret_id,
        COUNT(*) AS active_count
    FROM secret_versions
    WHERE state = 'ACTIVE'
    GROUP BY secret_id
),
staged_versions AS (
    SELECT
        secret_id,
        COUNT(*) AS staged_count
    FROM secret_versions
    WHERE state = 'STAGED'
    GROUP BY secret_id
)
SELECT
    s.secret_name,
    COALESCE(a.active_count, 0) AS active_versions,
    COALESCE(st.staged_count, 0) AS staged_versions,
    CASE
        WHEN NOT s.enabled THEN 'DISABLED'
        WHEN COALESCE(a.active_count, 0) = 0
            THEN 'NO_ACTIVE_VERSION'
        WHEN COALESCE(a.active_count, 0) > 1
            THEN 'MULTIPLE_ACTIVE_VERSIONS'
        WHEN COALESCE(st.staged_count, 0) > 1
            THEN 'MULTIPLE_STAGED_VERSIONS'
        ELSE 'VALID'
    END AS governance_status
FROM secrets s
LEFT JOIN active_versions a
    ON a.secret_id = s.secret_id
LEFT JOIN staged_versions st
    ON st.secret_id = s.secret_id
ORDER BY s.secret_name;

-- ============================================================
-- 39. Transaction rollback demonstration
-- ============================================================

SAVEPOINT before_test_update;

UPDATE secrets
SET enabled = FALSE
WHERE secret_name = 'database-password';

-- Demonstration rollback preserves the original configuration.
ROLLBACK TO SAVEPOINT before_test_update;

RELEASE SAVEPOINT before_test_update;

-- ============================================================
-- 40. Commit
-- ============================================================

COMMIT;

/*
================================================================
PRODUCTION SECURITY NOTES

1. Secret values never enter these relational tables.
2. Provider credentials must be managed outside this database.
3. Access control must also be enforced at the provider boundary.
4. Use TLS and authenticated service identities.
5. Database permissions must restrict direct table modifications.
6. Restrict EXECUTE privileges on security-sensitive procedures.
7. Export audit records to protected, tamper-resistant storage.
8. Use separate credentials for development and production.
9. Verify replacement credentials before activating rotation.
10. Revoke previous credentials after the rollback window.
11. Configure provider-side expiry and emergency revocation.
12. Database transactions cannot atomically commit an external
    secret-manager operation. Use an idempotent workflow,
    durable event records, and reconciliation for that boundary.
================================================================
*/
