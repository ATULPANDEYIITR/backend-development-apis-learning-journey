===============================================================================
IDEMPOTENCY ENGINEERING: PAYMENT API GOVERNANCE
PostgreSQL 15+

Implements:
- Idempotency key registration.
- Canonical request fingerprint storage.
- Duplicate request detection.
- Payment state management.
- Concurrent request coordination.
- Cached API responses.
- Key expiration.
- Gateway transaction references.
- Unknown outcome reconciliation.
- Audit logging.
- Reporting and eligibility queries.

Execute as a database owner in a dedicated development database.
===============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS payment_api;

SET search_path TO payment_api, public;

-- ============================================================================
-- DOMAIN TYPES
-- ============================================================================

CREATE TYPE payment_status AS ENUM (
    'PROCESSING',
    'SUCCEEDED',
    'FAILED',
    'UNKNOWN'
);

CREATE TYPE idempotency_state AS ENUM (
    'PROCESSING',
    'COMPLETED',
    'FAILED',
    'UNKNOWN'
);

CREATE TYPE gateway_outcome AS ENUM (
    'APPROVED',
    'DECLINED',
    'PENDING',
    'TIMEOUT',
    'NOT_FOUND'
);

CREATE TYPE api_event_type AS ENUM (
    'REQUEST_RECEIVED',
    'KEY_RESERVED',
    'DUPLICATE_DETECTED',
    'PAYMENT_SUCCEEDED',
    'PAYMENT_FAILED',
    'OUTCOME_UNKNOWN',
    'RECONCILED',
    'KEY_EXPIRED',
    'CONFLICT_REJECTED'
);

-- ============================================================================
-- CUSTOMERS
-- ============================================================================

CREATE TABLE customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_reference VARCHAR(80) NOT NULL UNIQUE,
    customer_name VARCHAR(150) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- PAYMENT METHODS
-- ============================================================================

CREATE TABLE payment_methods (
    payment_method_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),

    method_reference VARCHAR(120) NOT NULL UNIQUE,
    method_type VARCHAR(30) NOT NULL,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (payment_method_id, customer_id),

    CHECK (method_type IN ('CARD_TOKEN', 'BANK_TOKEN', 'WALLET_TOKEN'))
);

-- ============================================================================
-- PAYMENT TRANSACTIONS
-- ============================================================================

CREATE TABLE payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),

    payment_method_id BIGINT NOT NULL,

    amount_minor BIGINT NOT NULL,
    currency CHAR(3) NOT NULL,

    status payment_status NOT NULL DEFAULT 'PROCESSING',

    provider_reference VARCHAR(150) UNIQUE,

    failure_code VARCHAR(80),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (payment_method_id, customer_id)
        REFERENCES payment_methods(payment_method_id, customer_id),

    CHECK (amount_minor > 0),
    CHECK (amount_minor <= 100000000),
    CHECK (currency ~ '^[A-Z]{3}$'),

    CHECK (
        (status = 'FAILED' AND failure_code IS NOT NULL)
        OR
        (status <> 'FAILED')
    )
);

CREATE INDEX idx_payments_customer_created
    ON payments(customer_id, created_at DESC);

CREATE INDEX idx_payments_status_created
    ON payments(status, created_at DESC);

CREATE INDEX idx_payments_provider_reference
    ON payments(provider_reference)
    WHERE provider_reference IS NOT NULL;

-- ============================================================================
-- IDEMPOTENCY REGISTRY
-- ============================================================================

CREATE TABLE idempotency_keys (
    idempotency_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    idempotency_key VARCHAR(128) NOT NULL UNIQUE,

    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),

    request_fingerprint CHAR(64) NOT NULL,

    payment_id UUID UNIQUE
        REFERENCES payments(payment_id),

    state idempotency_state NOT NULL DEFAULT 'PROCESSING',

    cached_http_status SMALLINT,

    cached_response JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    completed_at TIMESTAMPTZ,

    CHECK (
        idempotency_key ~ '^[A-Za-z0-9_-]{16,128}$'
    ),

    CHECK (
        request_fingerprint ~ '^[a-f0-9]{64}$'
    ),

    CHECK (expires_at > created_at),

    CHECK (
        cached_http_status IS NULL
        OR cached_http_status BETWEEN 100 AND 599
    ),

    CHECK (
        (state = 'PROCESSING' AND completed_at IS NULL)
        OR
        (state <> 'PROCESSING' AND completed_at IS NOT NULL)
    ),

    CHECK (
        state NOT IN ('COMPLETED', 'FAILED')
        OR (
            cached_http_status IS NOT NULL
            AND cached_response IS NOT NULL
        )
    )
);

CREATE INDEX idx_idempotency_customer_created
    ON idempotency_keys(customer_id, created_at DESC);

CREATE INDEX idx_idempotency_expiration
    ON idempotency_keys(expires_at)
    WHERE state IN ('COMPLETED', 'FAILED');

CREATE INDEX idx_idempotency_payment
    ON idempotency_keys(payment_id);

-- ============================================================================
-- GATEWAY ATTEMPTS
-- ============================================================================

CREATE TABLE gateway_attempts (
    attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    payment_id UUID NOT NULL
        REFERENCES payments(payment_id),

    attempt_number INTEGER NOT NULL,

    outcome gateway_outcome NOT NULL,

    provider_reference VARCHAR(150),

    error_code VARCHAR(80),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (payment_id, attempt_number),

    CHECK (attempt_number > 0)
);

CREATE INDEX idx_gateway_attempts_payment
    ON gateway_attempts(payment_id, attempt_number DESC);

-- ============================================================================
-- AUDIT EVENTS
-- ============================================================================

CREATE TABLE api_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    idempotency_id BIGINT
        REFERENCES idempotency_keys(idempotency_id),

    payment_id UUID
        REFERENCES payments(payment_id),

    event_type api_event_type NOT NULL,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_events_type_created
    ON api_events(event_type, created_at DESC);

CREATE INDEX idx_api_events_payment
    ON api_events(payment_id, created_at DESC);

-- ============================================================================
-- PAYMENT STATE TRANSITION VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_payment_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = NEW.status THEN
        NEW.updated_at := NOW();
        RETURN NEW;
    END IF;

    IF OLD.status = 'PROCESSING'
       AND NEW.status IN ('SUCCEEDED', 'FAILED', 'UNKNOWN') THEN

        NEW.updated_at := NOW();
        RETURN NEW;

    ELSIF OLD.status = 'UNKNOWN'
       AND NEW.status IN ('SUCCEEDED', 'FAILED') THEN

        NEW.updated_at := NOW();
        RETURN NEW;

    END IF;

    RAISE EXCEPTION
        'Invalid payment transition: % -> %',
        OLD.status,
        NEW.status;

END;
$$;

CREATE TRIGGER trg_payment_transition
BEFORE UPDATE OF status ON payments
FOR EACH ROW
EXECUTE FUNCTION validate_payment_transition();

-- ============================================================================
-- AUDIT PAYMENT CHANGES
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_payment_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_event api_event_type;
BEGIN
    IF NEW.status = 'SUCCEEDED' THEN
        v_event := 'PAYMENT_SUCCEEDED';

    ELSIF NEW.status = 'FAILED' THEN
        v_event := 'PAYMENT_FAILED';

    ELSIF NEW.status = 'UNKNOWN' THEN
        v_event := 'OUTCOME_UNKNOWN';

    ELSE
        RETURN NEW;
    END IF;

    INSERT INTO api_events (
        payment_id,
        event_type,
        event_details
    )
    VALUES (
        NEW.payment_id,
        v_event,
        jsonb_build_object(
            'previous_status', OLD.status,
            'new_status', NEW.status
        )
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_payment_audit
AFTER UPDATE OF status ON payments
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION audit_payment_change();

-- ============================================================================
-- REGISTER IDEMPOTENCY REQUEST
-- ============================================================================
-- ON CONFLICT provides atomic key reservation.
-- A conflicting request must compare its fingerprint with the stored one.

CREATE OR REPLACE FUNCTION register_idempotency_request(
    p_key VARCHAR(128),
    p_customer_id BIGINT,
    p_fingerprint CHAR(64),
    p_retention INTERVAL DEFAULT INTERVAL '24 hours'
)
RETURNS TABLE (
    registered BOOLEAN,
    idempotency_id BIGINT,
    current_state idempotency_state,
    existing_payment_id UUID,
    cached_status SMALLINT,
    cached_body JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_fingerprint CHAR(64);
    v_state idempotency_state;
    v_payment_id UUID;
    v_http SMALLINT;
    v_body JSONB;
    v_expiry TIMESTAMPTZ;
BEGIN
    IF p_key IS NULL
       OR p_key !~ '^[A-Za-z0-9_-]{16,128}$' THEN
        RAISE EXCEPTION 'Invalid idempotency key'
            USING ERRCODE = '22023';
    END IF;

    IF p_fingerprint IS NULL
       OR p_fingerprint !~ '^[a-f0-9]{64}$' THEN
        RAISE EXCEPTION 'Invalid request fingerprint'
            USING ERRCODE = '22023';
    END IF;

    IF p_retention <= INTERVAL '0 seconds'
       OR p_retention > INTERVAL '30 days' THEN
        RAISE EXCEPTION 'Invalid retention interval'
            USING ERRCODE = '22023';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM customers c
        WHERE c.customer_id = p_customer_id
          AND c.active = TRUE
    ) THEN
        RAISE EXCEPTION 'Customer is not active or does not exist';
    END IF;

    INSERT INTO idempotency_keys (
        idempotency_key,
        customer_id,
        request_fingerprint,
        expires_at
    )
    VALUES (
        p_key,
        p_customer_id,
        p_fingerprint,
        NOW() + p_retention
    )
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING
        payment_api.idempotency_keys.idempotency_id
    INTO v_id;

    IF FOUND THEN

        INSERT INTO api_events (
            idempotency_id,
            event_type,
            event_details
        )
        VALUES (
            v_id,
            'KEY_RESERVED',
            jsonb_build_object(
                'customer_id', p_customer_id
            )
        );

        RETURN QUERY
        SELECT
            TRUE,
            v_id,
            'PROCESSING'::idempotency_state,
            NULL::UUID,
            NULL::SMALLINT,
            NULL::JSONB;

        RETURN;
    END IF;

    -- The unique constraint serializes competing inserts.
    -- Lock the winning record before evaluating the retry.
    SELECT
        k.idempotency_id,
        k.request_fingerprint,
        k.state,
        k.payment_id,
        k.cached_http_status,
        k.cached_response,
        k.expires_at
    INTO
        v_id,
        v_fingerprint,
        v_state,
        v_payment_id,
        v_http,
        v_body,
        v_expiry
    FROM idempotency_keys k
    WHERE k.idempotency_key = p_key
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Idempotency record disappeared';
    END IF;

    IF v_fingerprint <> p_fingerprint THEN

        INSERT INTO api_events (
            idempotency_id,
            event_type,
            event_details
        )
        VALUES (
            v_id,
            'CONFLICT_REJECTED',
            '{"reason":"REQUEST_FINGERPRINT_MISMATCH"}'::JSONB
        );

        RAISE EXCEPTION
            'Idempotency key reused with a different request'
            USING ERRCODE = '23505';
    END IF;

    IF v_expiry <= NOW() THEN

        INSERT INTO api_events (
            idempotency_id,
            event_type,
            event_details
        )
        VALUES (
            v_id,
            'KEY_EXPIRED',
            '{}'::JSONB
        );

        RAISE EXCEPTION
            'Idempotency key expired; reconciliation required'
            USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO api_events (
        idempotency_id,
        payment_id,
        event_type,
        event_details
    )
    VALUES (
        v_id,
        v_payment_id,
        'DUPLICATE_DETECTED',
        jsonb_build_object('state', v_state)
    );

    RETURN QUERY
    SELECT
        FALSE,
        v_id,
        v_state,
        v_payment_id,
        v_http,
        v_body;
END;
$$;

-- ============================================================================
-- COMPLETE PAYMENT OPERATION
-- ============================================================================
-- This function must be called in the same database transaction as
-- payment creation and idempotency record completion.

CREATE OR REPLACE FUNCTION complete_payment(
    p_idempotency_id BIGINT,
    p_payment_id UUID,
    p_outcome gateway_outcome,
    p_provider_reference VARCHAR(150) DEFAULT NULL,
    p_error_code VARCHAR(80) DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_status payment_status;
    v_state idempotency_state;
    v_http SMALLINT;
    v_response JSONB;
    v_customer_id BIGINT;
    v_attempt INTEGER;
BEGIN
    SELECT
        p.status,
        p.customer_id
    INTO
        v_status,
        v_customer_id
    FROM payments p
    WHERE p.payment_id = p_payment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Payment does not exist';
    END IF;

    PERFORM 1
    FROM idempotency_keys k
    WHERE k.idempotency_id = p_idempotency_id
      AND k.payment_id = p_payment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Idempotency record does not match payment';
    END IF;

    SELECT COALESCE(MAX(attempt_number), 0) + 1
    INTO v_attempt
    FROM gateway_attempts
    WHERE payment_id = p_payment_id;

    INSERT INTO gateway_attempts (
        payment_id,
        attempt_number,
        outcome,
        provider_reference,
        error_code
    )
    VALUES (
        p_payment_id,
        v_attempt,
        p_outcome,
        p_provider_reference,
        p_error_code
    );

    IF p_outcome = 'APPROVED' THEN

        IF p_provider_reference IS NULL THEN
            RAISE EXCEPTION 'Approved transaction requires provider reference';
        END IF;

        UPDATE payments
        SET status = 'SUCCEEDED',
            provider_reference = p_provider_reference,
            failure_code = NULL
        WHERE payment_id = p_payment_id;

        v_state := 'COMPLETED';
        v_http := 200;

    ELSIF p_outcome = 'DECLINED' THEN

        UPDATE payments
        SET status = 'FAILED',
            failure_code = COALESCE(p_error_code, 'GATEWAY_DECLINED')
        WHERE payment_id = p_payment_id;

        v_state := 'FAILED';
        v_http := 402;

    ELSIF p_outcome IN ('TIMEOUT', 'PENDING') THEN

        UPDATE payments
        SET status = 'UNKNOWN'
        WHERE payment_id = p_payment_id;

        v_state := 'UNKNOWN';
        v_http := 202;

    ELSE
        RAISE EXCEPTION 'Unsupported gateway outcome';
    END IF;

    SELECT p.status
    INTO v_status
    FROM payments p
    WHERE p.payment_id = p_payment_id;

    v_response := jsonb_build_object(
        'payment_id', p_payment_id,
        'customer_id', v_customer_id,
        'status', v_status,
        'provider_reference', p_provider_reference,
        'error_code', p_error_code
    );

    UPDATE idempotency_keys
    SET state = v_state,
        cached_http_status = v_http,
        cached_response = v_response,
        completed_at = CASE
            WHEN v_state = 'UNKNOWN' THEN NULL
            ELSE NOW()
        END
    WHERE idempotency_id = p_idempotency_id;

    RETURN v_response;
END;
$$;

-- ============================================================================
-- RECONCILE UNKNOWN PAYMENT
-- ============================================================================

CREATE OR REPLACE FUNCTION reconcile_payment(
    p_idempotency_id BIGINT,
    p_provider_confirmed BOOLEAN,
    p_provider_reference VARCHAR(150)
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_payment UUID;
    v_status payment_status;
    v_customer BIGINT;
    v_response JSONB;
    v_attempt INTEGER;
BEGIN
    SELECT
        k.payment_id,
        p.status,
        p.customer_id
    INTO
        v_payment,
        v_status,
        v_customer
    FROM idempotency_keys k
    JOIN payments p ON p.payment_id = k.payment_id
    WHERE k.idempotency_id = p_idempotency_id
    FOR UPDATE OF k, p;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Reconciliation record not found';
    END IF;

    IF v_status NOT IN ('UNKNOWN', 'PROCESSING') THEN
        RAISE EXCEPTION 'Payment is not eligible for reconciliation';
    END IF;

    SELECT COALESCE(MAX(attempt_number), 0) + 1
    INTO v_attempt
    FROM gateway_attempts
    WHERE payment_id = v_payment;

    IF p_provider_confirmed THEN

        IF p_provider_reference IS NULL THEN
            RAISE EXCEPTION 'Provider reference required';
        END IF;

        UPDATE payments
        SET status = 'SUCCEEDED',
            provider_reference = p_provider_reference,
            failure_code = NULL
        WHERE payment_id = v_payment;

        UPDATE idempotency_keys
        SET state = 'COMPLETED',
            cached_http_status = 200,
            cached_response = jsonb_build_object(
                'payment_id', v_payment,
                'status', 'SUCCEEDED',
                'reconciled', TRUE
            ),
            completed_at = NOW()
        WHERE idempotency_id = p_idempotency_id;

        INSERT INTO gateway_attempts (
            payment_id,
            attempt_number,
            outcome,
            provider_reference
        )
        VALUES (
            v_payment,
            v_attempt,
            'APPROVED',
            p_provider_reference
        );

    ELSE

        UPDATE payments
        SET status = 'FAILED',
            failure_code = 'PROVIDER_CONFIRMED_NO_CHARGE'
        WHERE payment_id = v_payment;

        UPDATE idempotency_keys
        SET state = 'FAILED',
            cached_http_status = 402,
            cached_response = jsonb_build_object(
                'payment_id', v_payment,
                'status', 'FAILED',
                'reconciled', TRUE
            ),
            completed_at = NOW()
        WHERE idempotency_id = p_idempotency_id;

        INSERT INTO gateway_attempts (
            payment_id,
            attempt_number,
            outcome,
            error_code
        )
        VALUES (
            v_payment,
            v_attempt,
            'NOT_FOUND',
            'PROVIDER_CONFIRMED_NO_CHARGE'
        );
    END IF;

    SELECT cached_response
    INTO v_response
    FROM idempotency_keys
    WHERE idempotency_id = p_idempotency_id;

    INSERT INTO api_events (
        idempotency_id,
        payment_id,
        event_type,
        event_details
    )
    VALUES (
        p_idempotency_id,
        v_payment,
        'RECONCILED',
        jsonb_build_object(
            'provider_confirmed', p_provider_confirmed
        )
    );

    RETURN v_response;
END;
$$;

-- ============================================================================
-- EXPIRED KEY CLEANUP
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_expired_keys(
    p_batch_size INTEGER DEFAULT 500
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    IF p_batch_size < 1 OR p_batch_size > 10000 THEN
        RAISE EXCEPTION 'Invalid batch size';
    END IF;

    WITH expired AS (
        SELECT idempotency_id
        FROM idempotency_keys
        WHERE expires_at <= NOW()
          AND state IN ('COMPLETED', 'FAILED')
        ORDER BY expires_at
        LIMIT p_batch_size
        FOR UPDATE SKIP LOCKED
    )
    DELETE FROM idempotency_keys k
    USING expired e
    WHERE k.idempotency_id = e.idempotency_id;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    RETURN v_deleted;
END;
$$;

-- ============================================================================
-- OPERATIONAL REPORTING VIEW
-- ============================================================================

CREATE OR REPLACE VIEW payment_operations_report AS
SELECT
    p.payment_id,
    c.external_reference AS customer_reference,
    p.amount_minor,
    p.currency,
    p.status AS payment_status,
    k.idempotency_key,
    k.state AS idempotency_state,
    k.expires_at,
    k.cached_http_status,
    COUNT(DISTINCT g.attempt_id) AS gateway_attempt_count,
    p.created_at
FROM payments p
JOIN customers c
    ON c.customer_id = p.customer_id
LEFT JOIN idempotency_keys k
    ON k.payment_id = p.payment_id
LEFT JOIN gateway_attempts g
    ON g.payment_id = p.payment_id
GROUP BY
    p.payment_id,
    c.external_reference,
    p.amount_minor,
    p.currency,
    p.status,
    k.idempotency_key,
    k.state,
    k.expires_at,
    k.cached_http_status,
    p.created_at;

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

INSERT INTO customers (
    external_reference,
    customer_name
)
VALUES
    ('CUSTOMER-5001', 'Enterprise Customer One'),
    ('CUSTOMER-5002', 'Enterprise Customer Two'),
    ('CUSTOMER-5003', 'Enterprise Customer Three');

INSERT INTO payment_methods (
    customer_id,
    method_reference,
    method_type
)
SELECT
    customer_id,
    'TOKEN-' || external_reference,
    'CARD_TOKEN'
FROM customers;

-- ============================================================================
-- TRANSACTION 1: SUCCESSFUL PAYMENT
-- ============================================================================

DO $$
DECLARE
    v_customer BIGINT;
    v_method BIGINT;
    v_key_id BIGINT;
    v_payment UUID;
    v_registration RECORD;
    v_fingerprint CHAR(64);
BEGIN
    SELECT customer_id
    INTO v_customer
    FROM customers
    WHERE external_reference = 'CUSTOMER-5001';

    SELECT payment_method_id
    INTO v_method
    FROM payment_methods
    WHERE customer_id = v_customer;

    v_fingerprint := encode(
        digest(
            jsonb_build_object(
                'customer_id', v_customer,
                'amount', 25000,
                'currency', 'INR',
                'payment_method_id', v_method
            )::TEXT,
            'sha256'
        ),
        'hex'
    );

    SELECT *
    INTO v_registration
    FROM register_idempotency_request(
        'payment_request_500001',
        v_customer,
        v_fingerprint,
        INTERVAL '24 hours'
    );

    IF NOT v_registration.registered THEN
        RAISE EXCEPTION 'Unexpected duplicate request';
    END IF;

    v_key_id := v_registration.idempotency_id;

    INSERT INTO payments (
        customer_id,
        payment_method_id,
        amount_minor,
        currency
    )
    VALUES (
        v_customer,
        v_method,
        25000,
        'INR'
    )
    RETURNING payment_id INTO v_payment;

    UPDATE idempotency_keys
    SET payment_id = v_payment
    WHERE idempotency_id = v_key_id;

    PERFORM complete_payment(
        v_key_id,
        v_payment,
        'APPROVED',
        'GATEWAY-500001',
        NULL
    );
END;
$$;

-- ============================================================================
-- TRANSACTION 2: FAILED PAYMENT
-- ============================================================================

DO $$
DECLARE
    v_customer BIGINT;
    v_method BIGINT;
    v_key_id BIGINT;
    v_payment UUID;
    v_fingerprint CHAR(64);
    v_registration RECORD;
BEGIN
    SELECT customer_id
    INTO v_customer
    FROM customers
    WHERE external_reference = 'CUSTOMER-5002';

    SELECT payment_method_id
    INTO v_method
    FROM payment_methods
    WHERE customer_id = v_customer;

    v_fingerprint := encode(
        digest(
            jsonb_build_object(
                'customer_id', v_customer,
                'amount', 15000,
                'currency', 'INR',
                'payment_method_id', v_method
            )::TEXT,
            'sha256'
        ),
        'hex'
    );

    SELECT *
    INTO v_registration
    FROM register_idempotency_request(
        'payment_request_500002',
        v_customer,
        v_fingerprint
    );

    v_key_id := v_registration.idempotency_id;

    INSERT INTO payments (
        customer_id,
        payment_method_id,
        amount_minor,
        currency
    )
    VALUES (
        v_customer,
        v_method,
        15000,
        'INR'
    )
    RETURNING payment_id INTO v_payment;

    UPDATE idempotency_keys
    SET payment_id = v_payment
    WHERE idempotency_id = v_key_id;

    PERFORM complete_payment(
        v_key_id,
        v_payment,
        'DECLINED',
        NULL,
        'INSUFFICIENT_FUNDS'
    );
END;
$$;

-- ============================================================================
-- TRANSACTION 3: UNKNOWN OUTCOME AND RECONCILIATION
-- ============================================================================

DO $$
DECLARE
    v_customer BIGINT;
    v_method BIGINT;
    v_key_id BIGINT;
    v_payment UUID;
    v_fingerprint CHAR(64);
    v_registration RECORD;
BEGIN
    SELECT customer_id
    INTO v_customer
    FROM customers
    WHERE external_reference = 'CUSTOMER-5003';

    SELECT payment_method_id
    INTO v_method
    FROM payment_methods
    WHERE customer_id = v_customer;

    v_fingerprint := encode(
        digest(
            jsonb_build_object(
                'customer_id', v_customer,
                'amount', 30000,
                'currency', 'INR',
                'payment_method_id', v_method
            )::TEXT,
            'sha256'
        ),
        'hex'
    );

    SELECT *
    INTO v_registration
    FROM register_idempotency_request(
        'payment_request_500003',
        v_customer,
        v_fingerprint
    );

    v_key_id := v_registration.idempotency_id;

    INSERT INTO payments (
        customer_id,
        payment_method_id,
        amount_minor,
        currency
    )
    VALUES (
        v_customer,
        v_method,
        30000,
        'INR'
    )
    RETURNING payment_id INTO v_payment;

    UPDATE idempotency_keys
    SET payment_id = v_payment
    WHERE idempotency_id = v_key_id;

    PERFORM complete_payment(
        v_key_id,
        v_payment,
        'TIMEOUT',
        NULL,
        'GATEWAY_TIMEOUT'
    );

    -- The provider later confirms that the charge succeeded.
    PERFORM reconcile_payment(
        v_key_id,
        TRUE,
        'GATEWAY-RECONCILED-500003'
    );
END;
$$;

COMMIT;

-- ============================================================================
-- OPERATIONAL QUERIES
-- ============================================================================

-- 1. Retrieve all payment operations.
SELECT *
FROM payment_operations_report
ORDER BY created_at DESC;

-- 2. Find repeated requests and their cached responses.
SELECT
    idempotency_key,
    state,
    cached_http_status,
    cached_response,
    created_at
FROM idempotency_keys
ORDER BY created_at DESC;

-- 3. Identify unresolved payments.
SELECT
    p.payment_id,
    p.status,
    k.idempotency_key,
    k.state,
    p.created_at
FROM payments p
JOIN idempotency_keys k
    ON k.payment_id = p.payment_id
WHERE p.status IN ('PROCESSING', 'UNKNOWN');

-- 4. Aggregate payment volume by status.
SELECT
    status,
    COUNT(*) AS transaction_count,
    SUM(amount_minor) AS total_amount_minor
FROM payments
GROUP BY status
ORDER BY status;

-- 5. Evaluate duplicate request activity.
SELECT
    event_type,
    COUNT(*) AS event_count
FROM api_events
GROUP BY event_type
ORDER BY event_count DESC;

-- 6. Inspect gateway attempts.
SELECT
    p.payment_id,
    p.status,
    g.attempt_number,
    g.outcome,
    g.provider_reference,
    g.error_code
FROM payments p
JOIN gateway_attempts g
    ON g.payment_id = p.payment_id
ORDER BY p.created_at, g.attempt_number;

-- 7. Detect payment records with inconsistent idempotency associations.
SELECT
    p.payment_id,
    p.status,
    COUNT(k.idempotency_id) AS associated_keys
FROM payments p
LEFT JOIN idempotency_keys k
    ON k.payment_id = p.payment_id
GROUP BY p.payment_id, p.status
HAVING COUNT(k.idempotency_id) <> 1;

-- 8. Detect keys approaching expiration.
SELECT
    idempotency_key,
    state,
    expires_at,
    EXTRACT(EPOCH FROM (expires_at - NOW())) AS seconds_remaining
FROM idempotency_keys
WHERE expires_at < NOW() + INTERVAL '1 hour'
ORDER BY expires_at;

-- 9. Identify provider operations that require reconciliation.
SELECT
    p.payment_id,
    p.status,
    g.outcome,
    g.created_at
FROM payments p
JOIN gateway_attempts g
    ON g.payment_id = p.payment_id
WHERE p.status = 'UNKNOWN'
  AND g.outcome IN ('TIMEOUT', 'PENDING');

-- 10. Calculate operational success and failure rates.
WITH payment_metrics AS (
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (
            WHERE status = 'SUCCEEDED'
        ) AS successful,
        COUNT(*) FILTER (
            WHERE status = 'FAILED'
        ) AS failed,
        COUNT(*) FILTER (
            WHERE status IN ('PROCESSING', 'UNKNOWN')
        ) AS unresolved
    FROM payments
)
SELECT
    total,
    successful,
    failed,
    unresolved,
    ROUND(
        100.0 * successful / NULLIF(total, 0),
        2
    ) AS success_percentage
FROM payment_metrics;

-- 11. Evaluate whether a payment is eligible for reconciliation.
SELECT
    p.payment_id,
    CASE
        WHEN p.status IN ('UNKNOWN', 'PROCESSING')
            THEN 'RECONCILIATION_REQUIRED'
        WHEN p.status = 'SUCCEEDED'
            THEN 'TERMINAL_SUCCESS'
        WHEN p.status = 'FAILED'
            THEN 'TERMINAL_FAILURE'
    END AS operational_decision
FROM payments p;

-- 12. Cleanup completed expired records in controlled batches.
SELECT cleanup_expired_keys(500);
