CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP VIEW IF EXISTS password_authentication_report;
DROP TABLE IF EXISTS password_authentication_events;
DROP TABLE IF EXISTS user_passwords;
DROP TABLE IF EXISTS password_policies;
DROP TABLE IF EXISTS application_users;

CREATE TABLE application_users (
    user_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    account_status TEXT NOT NULL DEFAULT 'active',
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT application_users_status_ck
        CHECK (account_status IN ('active', 'disabled', 'locked')),
    CONSTRAINT application_users_failed_attempts_ck
        CHECK (failed_attempts >= 0)
);

CREATE TABLE password_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    policy_name TEXT NOT NULL UNIQUE,
    minimum_length INTEGER NOT NULL,
    maximum_length INTEGER NOT NULL,
    password_hash_algorithm TEXT NOT NULL,
    work_factor INTEGER NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT password_policy_length_ck
        CHECK (
            minimum_length >= 8
            AND maximum_length >= minimum_length
        ),
    CONSTRAINT password_policy_algorithm_ck
        CHECK (
            password_hash_algorithm IN (
                'bcrypt',
                'scrypt',
                'argon2'
            )
        ),
    CONSTRAINT password_policy_work_factor_ck
        CHECK (work_factor > 0)
);

CREATE TABLE user_passwords (
    password_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE
        REFERENCES application_users(user_id)
        ON DELETE CASCADE,
    policy_id BIGINT NOT NULL
        REFERENCES password_policies(policy_id),
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    compromised BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT password_hash_not_empty_ck
        CHECK (length(password_hash) > 20)
);

CREATE TABLE password_authentication_events (
    event_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT
        REFERENCES application_users(user_id)
        ON DELETE SET NULL,
    username_attempted TEXT NOT NULL,
    successful BOOLEAN NOT NULL,
    failure_reason TEXT,
    source_ip INET,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT authentication_failure_reason_ck
        CHECK (
            successful
            OR failure_reason IS NOT NULL
        )
);

CREATE INDEX password_auth_events_user_time_idx
    ON password_authentication_events(user_id, occurred_at DESC);

CREATE INDEX password_auth_events_username_time_idx
    ON password_authentication_events(username_attempted, occurred_at DESC);

INSERT INTO password_policies (
    policy_name,
    minimum_length,
    maximum_length,
    password_hash_algorithm,
    work_factor
)
VALUES
    ('Production bcrypt policy', 12, 128, 'bcrypt', 12),
    ('Legacy bcrypt policy', 8, 128, 'bcrypt', 10);

INSERT INTO application_users (
    username,
    email
)
VALUES
    ('alice', 'alice@example.test'),
    ('bob', 'bob@example.test'),
    ('carol', 'carol@example.test');

-- pgcrypto generates a unique random salt for each bcrypt password.
-- The plaintext password is never stored in user_passwords.
INSERT INTO user_passwords (
    user_id,
    policy_id,
    password_hash
)
SELECT
    u.user_id,
    p.policy_id,
    crypt(
        CASE u.username
            WHEN 'alice' THEN 'CorrectHorseBatteryStaple!2026'
            WHEN 'bob' THEN 'DatabasePassword!2026'
            WHEN 'carol' THEN 'LegacyPassword!2026'
        END,
        gen_salt(
            'bf',
            CASE
                WHEN u.username = 'carol' THEN 10
                ELSE 12
            END
        )
    )
FROM application_users AS u
JOIN password_policies AS p
    ON p.policy_name =
       CASE
           WHEN u.username = 'carol'
               THEN 'Legacy bcrypt policy'
           ELSE 'Production bcrypt policy'
       END;

CREATE OR REPLACE FUNCTION authenticate_user(
    p_username TEXT,
    p_password TEXT,
    p_source_ip INET DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_user application_users%ROWTYPE;
    v_hash TEXT;
    v_success BOOLEAN := FALSE;
    v_failure_reason TEXT;
BEGIN
    IF p_username IS NULL OR p_password IS NULL THEN
        RETURN FALSE;
    END IF;

    SELECT *
    INTO v_user
    FROM application_users
    WHERE username = p_username;

    IF NOT FOUND THEN
        INSERT INTO password_authentication_events (
            user_id,
            username_attempted,
            successful,
            failure_reason,
            source_ip
        )
        VALUES (
            NULL,
            p_username,
            FALSE,
            'unknown_username',
            p_source_ip
        );

        RETURN FALSE;
    END IF;

    IF v_user.account_status <> 'active' THEN
        INSERT INTO password_authentication_events (
            user_id,
            username_attempted,
            successful,
            failure_reason,
            source_ip
        )
        VALUES (
            v_user.user_id,
            p_username,
            FALSE,
            'account_not_active',
            p_source_ip
        );

        RETURN FALSE;
    END IF;

    IF v_user.locked_until IS NOT NULL
       AND v_user.locked_until > CURRENT_TIMESTAMP THEN

        INSERT INTO password_authentication_events (
            user_id,
            username_attempted,
            successful,
            failure_reason,
            source_ip
        )
        VALUES (
            v_user.user_id,
            p_username,
            FALSE,
            'account_temporarily_locked',
            p_source_ip
        );

        RETURN FALSE;
    END IF;

    SELECT password_hash
    INTO v_hash
    FROM user_passwords
    WHERE user_id = v_user.user_id
      AND compromised = FALSE;

    IF NOT FOUND THEN
        v_failure_reason := 'password_record_unavailable';
    ELSE
        v_success := crypt(p_password, v_hash) = v_hash;

        IF NOT v_success THEN
            v_failure_reason := 'invalid_password';
        END IF;
    END IF;

    IF v_success THEN
        UPDATE application_users
        SET failed_attempts = 0,
            locked_until = NULL,
            account_status = 'active'
        WHERE user_id = v_user.user_id;

        INSERT INTO password_authentication_events (
            user_id,
            username_attempted,
            successful,
            failure_reason,
            source_ip
        )
        VALUES (
            v_user.user_id,
            p_username,
            TRUE,
            NULL,
            p_source_ip
        );

        RETURN TRUE;
    END IF;

    UPDATE application_users
    SET failed_attempts = failed_attempts + 1,
        account_status =
            CASE
                WHEN failed_attempts + 1 >= 5
                    THEN 'locked'
                ELSE account_status
            END,
        locked_until =
            CASE
                WHEN failed_attempts + 1 >= 5
                    THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes'
                ELSE locked_until
            END
    WHERE user_id = v_user.user_id;

    INSERT INTO password_authentication_events (
        user_id,
        username_attempted,
        successful,
        failure_reason,
        source_ip
    )
    VALUES (
        v_user.user_id,
        p_username,
        FALSE,
        v_failure_reason,
        p_source_ip
    );

    RETURN FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION password_hash_modified_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.changed_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER user_password_changed_at_trigger
BEFORE UPDATE OF password_hash ON user_passwords
FOR EACH ROW
EXECUTE FUNCTION password_hash_modified_at();

CREATE OR REPLACE VIEW password_authentication_report AS
SELECT
    u.username,
    u.account_status,
    u.failed_attempts,
    u.locked_until,
    p.policy_name,
    p.password_hash_algorithm,
    p.work_factor,
    up.compromised,
    up.changed_at
FROM application_users AS u
JOIN user_passwords AS up
    ON up.user_id = u.user_id
JOIN password_policies AS p
    ON p.policy_id = up.policy_id;

-- Successful authentication uses crypt() to recompute bcrypt using
-- the salt embedded in the stored bcrypt hash.
SELECT authenticate_user(
    'alice',
    'CorrectHorseBatteryStaple!2026',
    '192.0.2.10'
);

-- An incorrect password is rejected and counted.
SELECT authenticate_user(
    'alice',
    'WrongPassword!2026',
    '192.0.2.10'
);

-- Repeated failures demonstrate account lockout behavior.
SELECT authenticate_user('bob', 'wrong-1', '192.0.2.20');
SELECT authenticate_user('bob', 'wrong-2', '192.0.2.20');
SELECT authenticate_user('bob', 'wrong-3', '192.0.2.20');
SELECT authenticate_user('bob', 'wrong-4', '192.0.2.20');
SELECT authenticate_user('bob', 'wrong-5', '192.0.2.20');

-- Correct credentials do not bypass an active lockout.
SELECT authenticate_user(
    'bob',
    'DatabasePassword!2026',
    '192.0.2.20'
);

-- Detect records using a weaker legacy work factor.
SELECT
    username,
    policy_name,
    work_factor,
    CASE
        WHEN work_factor < 12
            THEN 'rehash recommended'
        ELSE 'current policy'
    END AS password_policy_status
FROM password_authentication_report
ORDER BY username;

-- Review authentication failures for operational monitoring.
SELECT
    username_attempted,
    COUNT(*) AS failed_attempts
FROM password_authentication_events
WHERE successful = FALSE
GROUP BY username_attempted
ORDER BY failed_attempts DESC, username_attempted;

-- Show that password hashes do not expose the plaintext password.
SELECT
    username,
    password_hash,
    length(password_hash) AS stored_hash_length
FROM user_passwords
JOIN application_users USING (user_id)
ORDER BY username;

-- Transactional password rotation.
BEGIN;

UPDATE user_passwords
SET password_hash = crypt(
        'RotatedPassword!2026',
        gen_salt('bf', 12)
    ),
    policy_id = (
        SELECT policy_id
        FROM password_policies
        WHERE policy_name = 'Production bcrypt policy'
    ),
    compromised = FALSE
WHERE user_id = (
    SELECT user_id
    FROM application_users
    WHERE username = 'alice'
);

COMMIT;

-- Verify the rotated credential and reject the previous credential.
SELECT authenticate_user(
    'alice',
    'RotatedPassword!2026',
    '192.0.2.10'
);

SELECT authenticate_user(
    'alice',
    'CorrectHorseBatteryStaple!2026',
    '192.0.2.10'
);

SELECT *
FROM password_authentication_report
ORDER BY username;
