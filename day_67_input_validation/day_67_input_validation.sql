-- ============================================================
-- INPUT VALIDATION AND SECURE REQUEST PROCESSING
-- PostgreSQL 15+
--
-- Domain:
-- Enterprise API registration and procurement request handling.
--
-- Capabilities:
-- 1. Schema and structural validation
-- 2. Type enforcement
-- 3. Boundary validation
-- 4. Format validation
-- 5. Sanitization
-- 6. Malicious input indicators
-- 7. Business policy validation
-- 8. Validation audit records
-- 9. Transaction-safe registration
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS input_security;

SET search_path TO input_security, public;

-- ------------------------------------------------------------
-- ENUMERATIONS
-- ------------------------------------------------------------

CREATE TYPE validation_status AS ENUM (
    'PENDING',
    'ACCEPTED',
    'REJECTED'
);

CREATE TYPE validation_category AS ENUM (
    'REQUIRED',
    'TYPE',
    'FORMAT',
    'BOUNDARY',
    'SECURITY',
    'UNKNOWN_FIELD',
    'BUSINESS_RULE'
);

CREATE TYPE severity_level AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

-- ------------------------------------------------------------
-- REUSABLE VALIDATION FUNCTIONS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION normalize_text(p_value TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
STRICT
AS $$
    SELECT btrim(
        regexp_replace(
            normalize(p_value, NFC),
            '[[:cntrl:]]',
            '',
            'g'
        )
    );
$$;

CREATE OR REPLACE FUNCTION is_valid_email(p_email TEXT)
RETURNS BOOLEAN
LANGUAGE SQL
IMMUTABLE
STRICT
AS $$
    SELECT
        length(p_email) BETWEEN 6 AND 254
        AND p_email ~
        '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$';
$$;

CREATE OR REPLACE FUNCTION is_valid_supplier_code(p_code TEXT)
RETURNS BOOLEAN
LANGUAGE SQL
IMMUTABLE
STRICT
AS $$
    SELECT p_code ~ '^[A-Z]{2,4}-[0-9]{3,8}$';
$$;

CREATE OR REPLACE FUNCTION detect_malicious_input(p_value TEXT)
RETURNS TEXT[]
LANGUAGE SQL
IMMUTABLE
STRICT
AS $$
    SELECT array_remove(
        ARRAY[
            CASE
                WHEN p_value ~* '(\bUNION\s+SELECT\b|\bDROP\s+TABLE\b|--[[:space:]])'
                THEN 'SQL_INJECTION_INDICATOR'
            END,
            CASE
                WHEN p_value ~* '<[[:space:]]*script\b|javascript[[:space:]]*:'
                THEN 'SCRIPT_INJECTION_INDICATOR'
            END,
            CASE
                WHEN p_value ~ '\.\.[/\\]'
                THEN 'PATH_TRAVERSAL_INDICATOR'
            END,
            CASE
                WHEN p_value ~ '\$\([^)]*\)|`[^`]*`'
                THEN 'COMMAND_SUBSTITUTION_INDICATOR'
            END
        ]::TEXT[],
        NULL
    );
$$;

-- ------------------------------------------------------------
-- VALIDATION POLICIES
-- ------------------------------------------------------------

CREATE TABLE validation_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name VARCHAR(100) NOT NULL UNIQUE,
    field_name VARCHAR(100) NOT NULL,
    expected_type VARCHAR(30) NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    minimum_value NUMERIC,
    maximum_value NUMERIC,
    minimum_length INTEGER,
    maximum_length INTEGER,
    pattern TEXT,
    allowed_values TEXT[],
    reject_malicious BOOLEAN NOT NULL DEFAULT TRUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT valid_expected_type
        CHECK (
            expected_type IN (
                'TEXT',
                'INTEGER',
                'NUMERIC',
                'BOOLEAN'
            )
        ),

    CONSTRAINT valid_numeric_boundaries
        CHECK (
            minimum_value IS NULL
            OR maximum_value IS NULL
            OR minimum_value <= maximum_value
        ),

    CONSTRAINT valid_length_boundaries
        CHECK (
            (minimum_length IS NULL OR minimum_length >= 0)
            AND
            (maximum_length IS NULL OR maximum_length >= 0)
            AND
            (
                minimum_length IS NULL
                OR maximum_length IS NULL
                OR minimum_length <= maximum_length
            )
        )
);

INSERT INTO validation_policies (
    policy_name,
    field_name,
    expected_type,
    required,
    minimum_length,
    maximum_length,
    pattern
)
VALUES
(
    'Supplier code policy',
    'supplier_code',
    'TEXT',
    TRUE,
    6,
    15,
    '^[A-Z]{2,4}-[0-9]{3,8}$'
),
(
    'Company name policy',
    'company_name',
    'TEXT',
    TRUE,
    3,
    100,
    NULL
),
(
    'Email policy',
    'email',
    'TEXT',
    TRUE,
    6,
    254,
    '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$'
),
(
    'Employee count policy',
    'employee_count',
    'INTEGER',
    TRUE,
    NULL,
    NULL,
    NULL
),
(
    'Revenue policy',
    'annual_revenue',
    'NUMERIC',
    TRUE,
    NULL,
    NULL,
    NULL
),
(
    'Country policy',
    'country',
    'TEXT',
    TRUE,
    2,
    2,
    '^[A-Z]{2}$'
);

-- ------------------------------------------------------------
-- MASTER DATA
-- ------------------------------------------------------------

CREATE TABLE countries (
    country_code CHAR(2) PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE,
    restricted BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO countries (
    country_code,
    country_name,
    restricted
)
VALUES
('IN', 'India', FALSE),
('US', 'United States', FALSE),
('GB', 'United Kingdom', FALSE),
('SG', 'Singapore', FALSE),
('DE', 'Germany', TRUE);

CREATE TABLE suppliers (
    supplier_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    supplier_code VARCHAR(15) NOT NULL UNIQUE,
    company_name VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    country_code CHAR(2) NOT NULL
        REFERENCES countries(country_code),

    employee_count INTEGER NOT NULL,
    annual_revenue NUMERIC(18,2) NOT NULL,

    status validation_status NOT NULL DEFAULT 'PENDING',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_supplier_code
        CHECK (is_valid_supplier_code(supplier_code)),

    CONSTRAINT valid_company_name
        CHECK (
            length(btrim(company_name)) BETWEEN 3 AND 100
        ),

    CONSTRAINT valid_supplier_email
        CHECK (is_valid_email(email)),

    CONSTRAINT valid_employee_count
        CHECK (employee_count BETWEEN 1 AND 1000000),

    CONSTRAINT valid_annual_revenue
        CHECK (
            annual_revenue BETWEEN 0 AND 1000000000000
        )
);

CREATE INDEX idx_suppliers_status
    ON suppliers(status);

CREATE INDEX idx_suppliers_country
    ON suppliers(country_code);

CREATE INDEX idx_suppliers_created
    ON suppliers(created_at DESC);

-- ------------------------------------------------------------
-- REQUESTS
-- ------------------------------------------------------------

CREATE TABLE validation_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    request_type VARCHAR(50) NOT NULL,

    raw_payload JSONB NOT NULL,

    sanitized_payload JSONB,

    status validation_status NOT NULL DEFAULT 'PENDING',

    supplier_id BIGINT
        REFERENCES suppliers(supplier_id),

    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    processed_at TIMESTAMPTZ,

    CONSTRAINT valid_request_type
        CHECK (
            request_type IN (
                'SUPPLIER_REGISTRATION',
                'SUPPLIER_UPDATE'
            )
        ),

    CONSTRAINT request_payload_size
        CHECK (octet_length(raw_payload::TEXT) <= 16384)
);

CREATE INDEX idx_requests_status_time
    ON validation_requests(status, received_at DESC);

CREATE INDEX idx_requests_payload
    ON validation_requests
    USING GIN(raw_payload);

-- ------------------------------------------------------------
-- VALIDATION AUDIT
-- ------------------------------------------------------------

CREATE TABLE validation_errors (
    error_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id UUID NOT NULL
        REFERENCES validation_requests(request_id)
        ON DELETE CASCADE,

    field_name VARCHAR(100) NOT NULL,

    category validation_category NOT NULL,

    severity severity_level NOT NULL,

    error_message TEXT NOT NULL,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_validation_errors_request
    ON validation_errors(request_id);

CREATE INDEX idx_validation_errors_category
    ON validation_errors(category, detected_at DESC);

CREATE INDEX idx_validation_errors_severity
    ON validation_errors(severity, detected_at DESC);

-- ------------------------------------------------------------
-- TRIGGER: AUTOMATIC AUDIT TIMESTAMP
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_request_processed_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status <> OLD.status THEN
        NEW.processed_at = NOW();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_request_processed_at
BEFORE UPDATE OF status
ON validation_requests
FOR EACH ROW
EXECUTE FUNCTION set_request_processed_at();

-- ------------------------------------------------------------
-- TRIGGER: RESTRICT SUPPLIER STATE TRANSITIONS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION enforce_supplier_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IN ('APPROVED', 'REJECTED')
       AND NEW.status <> OLD.status THEN

        RAISE EXCEPTION
            'Final supplier status cannot be changed directly';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_supplier_state_transition
BEFORE UPDATE OF status
ON suppliers
FOR EACH ROW
EXECUTE FUNCTION enforce_supplier_transition();

-- ------------------------------------------------------------
-- VALIDATION PROCEDURE
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE validate_supplier_request(
    p_request_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_payload JSONB;
    v_company TEXT;
    v_email TEXT;
    v_code TEXT;
    v_country TEXT;
    v_employees INTEGER;
    v_revenue NUMERIC;

    v_issues INTEGER := 0;
    v_suspicious TEXT[];
    v_existing BIGINT;
    v_supplier_id BIGINT;
BEGIN
    SELECT raw_payload
    INTO v_payload
    FROM validation_requests
    WHERE request_id = p_request_id
      AND status = 'PENDING'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Request does not exist or is not pending';
    END IF;

    -- Reject unexpected root-level attributes.
    IF EXISTS (
        SELECT 1
        FROM jsonb_object_keys(v_payload) AS key_name
        WHERE key_name NOT IN (
            'supplier_code',
            'company_name',
            'email',
            'country',
            'employee_count',
            'annual_revenue'
        )
    ) THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            '$',
            'UNKNOWN_FIELD',
            'MEDIUM',
            'Payload contains unknown attributes.'
        );

        v_issues := v_issues + 1;
    END IF;

    -- Required field checks.
    IF NOT (
        v_payload ? 'supplier_code'
        AND v_payload ? 'company_name'
        AND v_payload ? 'email'
        AND v_payload ? 'country'
        AND v_payload ? 'employee_count'
        AND v_payload ? 'annual_revenue'
    ) THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            '$',
            'REQUIRED',
            'HIGH',
            'One or more required attributes are missing.'
        );

        v_issues := v_issues + 1;
    END IF;

    -- Type validation.
    IF jsonb_typeof(v_payload -> 'supplier_code') <> 'string'
       OR jsonb_typeof(v_payload -> 'company_name') <> 'string'
       OR jsonb_typeof(v_payload -> 'email') <> 'string'
       OR jsonb_typeof(v_payload -> 'country') <> 'string'
       OR jsonb_typeof(v_payload -> 'employee_count') <> 'number'
       OR jsonb_typeof(v_payload -> 'annual_revenue') <> 'number'
    THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            '$',
            'TYPE',
            'HIGH',
            'One or more attributes have incorrect JSON types.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF v_issues > 0 THEN
        UPDATE validation_requests
        SET status = 'REJECTED'
        WHERE request_id = p_request_id;

        RETURN;
    END IF;

    -- Conversion occurs only after JSON type validation.
    v_code := normalize_text(v_payload ->> 'supplier_code');
    v_company := normalize_text(v_payload ->> 'company_name');
    v_email := normalize_text(v_payload ->> 'email');
    v_country := normalize_text(v_payload ->> 'country');

    v_employees := (v_payload ->> 'employee_count')::INTEGER;
    v_revenue := (v_payload ->> 'annual_revenue')::NUMERIC;

    -- Format and boundary validation.
    IF NOT is_valid_supplier_code(v_code) THEN
        INSERT INTO validation_errors VALUES (
            DEFAULT,
            p_request_id,
            'supplier_code',
            'FORMAT',
            'MEDIUM',
            'Supplier code format is invalid.',
            NOW()
        );

        v_issues := v_issues + 1;
    END IF;

    IF length(v_company) NOT BETWEEN 3 AND 100 THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'company_name',
            'BOUNDARY',
            'MEDIUM',
            'Company name length must be between 3 and 100.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF NOT is_valid_email(v_email) THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'email',
            'FORMAT',
            'MEDIUM',
            'Email address format is invalid.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF v_employees NOT BETWEEN 1 AND 1000000 THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'employee_count',
            'BOUNDARY',
            'MEDIUM',
            'Employee count is outside the permitted range.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF v_revenue NOT BETWEEN 0 AND 1000000000000 THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'annual_revenue',
            'BOUNDARY',
            'MEDIUM',
            'Annual revenue is outside the permitted range.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM countries
        WHERE country_code = v_country
    ) THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'country',
            'FORMAT',
            'MEDIUM',
            'Country code is not registered.'
        );

        v_issues := v_issues + 1;
    END IF;

    -- Security inspection is detection, not sanitization.
    SELECT array_cat(
        detect_malicious_input(v_company),
        detect_malicious_input(v_email)
    )
    INTO v_suspicious;

    IF cardinality(v_suspicious) > 0 THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'company_name/email',
            'SECURITY',
            'HIGH',
            'Potential malicious input indicator detected: '
                || array_to_string(v_suspicious, ', ')
        );

        v_issues := v_issues + 1;
    END IF;

    -- Duplicate detection is supported by a unique constraint too.
    SELECT supplier_id
    INTO v_existing
    FROM suppliers
    WHERE supplier_code = v_code;

    IF FOUND THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'supplier_code',
            'BUSINESS_RULE',
            'MEDIUM',
            'Supplier code already exists.'
        );

        v_issues := v_issues + 1;
    END IF;

    -- Business policy: minimum workforce and revenue.
    IF v_employees < 10 OR v_revenue < 1000000 THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'supplier_eligibility',
            'BUSINESS_RULE',
            'MEDIUM',
            'Supplier does not satisfy onboarding thresholds.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM countries
        WHERE country_code = v_country
          AND restricted = TRUE
    ) THEN
        INSERT INTO validation_errors (
            request_id,
            field_name,
            category,
            severity,
            error_message
        )
        VALUES (
            p_request_id,
            'country',
            'BUSINESS_RULE',
            'HIGH',
            'Country requires restricted compliance review.'
        );

        v_issues := v_issues + 1;
    END IF;

    IF v_issues > 0 THEN
        UPDATE validation_requests
        SET
            status = 'REJECTED',
            sanitized_payload = jsonb_build_object(
                'supplier_code', v_code,
                'company_name', v_company,
                'email', v_email,
                'country', v_country
            )
        WHERE request_id = p_request_id;

        RETURN;
    END IF;

    -- Only fully validated data reaches the master table.
    INSERT INTO suppliers (
        supplier_code,
        company_name,
        email,
        country_code,
        employee_count,
        annual_revenue
    )
    VALUES (
        v_code,
        v_company,
        v_email,
        v_country,
        v_employees,
        v_revenue
    )
    RETURNING supplier_id INTO v_supplier_id;

    UPDATE validation_requests
    SET
        status = 'ACCEPTED',
        supplier_id = v_supplier_id,
        sanitized_payload = jsonb_build_object(
            'supplier_code', v_code,
            'company_name', v_company,
            'email', v_email,
            'country', v_country,
            'employee_count', v_employees,
            'annual_revenue', v_revenue
        )
    WHERE request_id = p_request_id;

END;
$$;

-- ------------------------------------------------------------
-- VIEWS
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW request_validation_report AS
SELECT
    r.request_id,
    r.request_type,
    r.status,
    r.received_at,
    r.processed_at,
    s.supplier_code,
    s.company_name,
    COUNT(e.error_id) AS error_count,
    COUNT(e.error_id) FILTER (
        WHERE e.category = 'SECURITY'
    ) AS security_error_count,
    COUNT(e.error_id) FILTER (
        WHERE e.category = 'BOUNDARY'
    ) AS boundary_error_count
FROM validation_requests r
LEFT JOIN suppliers s
    ON s.supplier_id = r.supplier_id
LEFT JOIN validation_errors e
    ON e.request_id = r.request_id
GROUP BY
    r.request_id,
    r.request_type,
    r.status,
    r.received_at,
    r.processed_at,
    s.supplier_code,
    s.company_name;

CREATE OR REPLACE VIEW validation_category_summary AS
SELECT
    category,
    severity,
    COUNT(*) AS total_errors,
    COUNT(DISTINCT request_id) AS affected_requests
FROM validation_errors
GROUP BY category, severity;

-- ------------------------------------------------------------
-- SAMPLE REQUESTS
-- ------------------------------------------------------------

INSERT INTO validation_requests (
    request_id,
    request_type,
    raw_payload
)
VALUES
(
    '11111111-1111-4111-8111-111111111111',
    'SUPPLIER_REGISTRATION',
    '{
        "supplier_code": "SUP-1001",
        "company_name": "National Technology Services",
        "email": "supplier@example.com",
        "country": "IN",
        "employee_count": 50,
        "annual_revenue": 5000000
    }'::JSONB
),
(
    '22222222-2222-4222-8222-222222222222',
    'SUPPLIER_REGISTRATION',
    '{
        "supplier_code": "SUP-1002",
        "company_name": "Small Supplier",
        "email": "small@example.com",
        "country": "IN",
        "employee_count": 2,
        "annual_revenue": 50000
    }'::JSONB
),
(
    '33333333-3333-4333-8333-333333333333',
    'SUPPLIER_REGISTRATION',
    '{
        "supplier_code": "SUP-1003",
        "company_name": "<script>alert(1)</script>",
        "email": "attack@example.com",
        "country": "IN",
        "employee_count": 50,
        "annual_revenue": 5000000
    }'::JSONB
),
(
    '44444444-4444-4444-8444-444444444444',
    'SUPPLIER_REGISTRATION',
    '{
        "supplier_code": "SUP-1004",
        "company_name": "Unknown Attribute Supplier",
        "email": "extra@example.com",
        "country": "IN",
        "employee_count": 50,
        "annual_revenue": 5000000,
        "is_administrator": true
    }'::JSONB
),
(
    '55555555-5555-4555-8555-555555555555',
    'SUPPLIER_REGISTRATION',
    '{
        "supplier_code": "SUP-1005",
        "company_name": "Restricted Supplier",
        "email": "restricted@example.com",
        "country": "DE",
        "employee_count": 50,
        "annual_revenue": 5000000
    }'::JSONB
);

-- ------------------------------------------------------------
-- PROCESS REQUESTS
-- ------------------------------------------------------------

CALL validate_supplier_request(
    '11111111-1111-4111-8111-111111111111'
);

CALL validate_supplier_request(
    '22222222-2222-4222-8222-222222222222'
);

CALL validate_supplier_request(
    '33333333-3333-4333-8333-333333333333'
);

CALL validate_supplier_request(
    '44444444-4444-4444-8444-444444444444'
);

CALL validate_supplier_request(
    '55555555-5555-4555-8555-555555555555'
);

-- ------------------------------------------------------------
-- RETRIEVAL
-- ------------------------------------------------------------

SELECT
    supplier_id,
    supplier_code,
    company_name,
    email,
    country_code,
    employee_count,
    annual_revenue,
    status
FROM suppliers
ORDER BY supplier_id;

-- ------------------------------------------------------------
-- VALIDATION RESULTS
-- ------------------------------------------------------------

SELECT *
FROM request_validation_report
ORDER BY received_at;

-- ------------------------------------------------------------
-- ERROR DETAILS
-- ------------------------------------------------------------

SELECT
    request_id,
    field_name,
    category,
    severity,
    error_message,
    detected_at
FROM validation_errors
ORDER BY detected_at, error_id;

-- ------------------------------------------------------------
-- AGGREGATION
-- ------------------------------------------------------------

SELECT *
FROM validation_category_summary
ORDER BY total_errors DESC;

-- ------------------------------------------------------------
-- ELIGIBILITY DETERMINATION
-- ------------------------------------------------------------

SELECT
    s.supplier_code,
    s.company_name,
    s.employee_count,
    s.annual_revenue,
    c.restricted,
    CASE
        WHEN c.restricted THEN 'COMPLIANCE_REVIEW'
        WHEN s.employee_count < 10 THEN 'NOT_ELIGIBLE'
        WHEN s.annual_revenue < 1000000 THEN 'NOT_ELIGIBLE'
        ELSE 'ELIGIBLE'
    END AS eligibility
FROM suppliers s
JOIN countries c
    ON c.country_code = s.country_code;

-- ------------------------------------------------------------
-- CTE: REQUEST PROCESSING METRICS
-- ------------------------------------------------------------

WITH request_metrics AS (
    SELECT
        status,
        COUNT(*) AS request_count
    FROM validation_requests
    GROUP BY status
)
SELECT
    status,
    request_count,
    ROUND(
        100.0 * request_count /
        NULLIF(SUM(request_count) OVER (), 0),
        2
    ) AS percentage
FROM request_metrics
ORDER BY request_count DESC;

-- ------------------------------------------------------------
-- JSON SECURITY INSPECTION
-- ------------------------------------------------------------

SELECT
    request_id,
    detect_malicious_input(
        COALESCE(raw_payload ->> 'company_name', '')
    ) AS detected_indicators
FROM validation_requests
ORDER BY received_at;

-- ------------------------------------------------------------
-- TRANSACTIONAL STATE CHECK
-- ------------------------------------------------------------

DO $$
DECLARE
    v_accepted INTEGER;
    v_rejected INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_accepted
    FROM validation_requests
    WHERE status = 'ACCEPTED';

    SELECT COUNT(*)
    INTO v_rejected
    FROM validation_requests
    WHERE status = 'REJECTED';

    RAISE NOTICE 'Accepted requests: %', v_accepted;
    RAISE NOTICE 'Rejected requests: %', v_rejected;
END;
$$;

COMMIT;

-- ============================================================
-- PRODUCTION NOTES
--
-- 1. Database constraints protect stored data even when an
--    application-level validation layer is bypassed.
--
-- 2. JSONB validation handles request structure before casting.
--
-- 3. Unique constraints protect against concurrent duplicate
--    supplier registrations.
--
-- 4. Validation errors contain diagnostic information rather
--    than copying complete untrusted payloads into audit records.
--
-- 5. Detection patterns are indicators, not a complete attack
--    classifier. Parameterized SQL remains mandatory.
--
-- 6. HTML output must be encoded by the consuming application.
--
-- 7. Restrict execution privileges on validation procedures and
--    protect audit tables through database roles.
--
-- 8. The sample procedure rejects restricted countries. A real
--    compliance workflow may route them to a separate review queue.
-- ============================================================
