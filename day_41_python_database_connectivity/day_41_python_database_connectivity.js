'use strict';

/*
 * Node.js database-connectivity example using the PostgreSQL `pg` driver.
 *
 * Install the driver with:
 *   npm install pg
 *
 * The important lifecycle is:
 *   Pool -> client -> query -> transaction -> release -> pool.end()
 *
 * A connection pool is preferable to opening a new physical connection for
 * every request because PostgreSQL connections are relatively expensive and
 * should be reused safely.
 */

const { Pool } = require('pg');

const pool = new Pool({
    host: process.env.PGHOST || 'localhost',
    port: Number(process.env.PGPORT || 5432),
    database: process.env.PGDATABASE || 'repository_governance',
    user: process.env.PGUSER || 'postgres',
    password: process.env.PGPASSWORD || 'postgres',
    max: 5,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 5_000
});

async function createSchema(client) {
    await client.query(`
        CREATE TABLE IF NOT EXISTS repositories (
            repository_id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            default_branch TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS branches (
            branch_id BIGSERIAL PRIMARY KEY,
            repository_id BIGINT NOT NULL REFERENCES repositories(repository_id),
            name TEXT NOT NULL,
            protected BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE(repository_id, name)
        );

        CREATE TABLE IF NOT EXISTS pull_requests (
            pull_request_id BIGSERIAL PRIMARY KEY,
            repository_id BIGINT NOT NULL REFERENCES repositories(repository_id),
            source_branch_id BIGINT NOT NULL REFERENCES branches(branch_id),
            target_branch_id BIGINT NOT NULL REFERENCES branches(branch_id),
            title TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('draft', 'open', 'closed', 'merged')),
            head_sha TEXT NOT NULL,
            UNIQUE(repository_id, source_branch_id, target_branch_id, head_sha)
        );

        CREATE TABLE IF NOT EXISTS reviewers (
            reviewer_id BIGSERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS reviews (
            review_id BIGSERIAL PRIMARY KEY,
            pull_request_id BIGINT NOT NULL
                REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
            reviewer_id BIGINT NOT NULL REFERENCES reviewers(reviewer_id),
            state TEXT NOT NULL
                CHECK (state IN ('commented', 'changes_requested', 'approved')),
            commit_sha TEXT NOT NULL,
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS status_checks (
            status_check_id BIGSERIAL PRIMARY KEY,
            pull_request_id BIGINT NOT NULL
                REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
            check_name TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'passed', 'failed')),
            UNIQUE(pull_request_id, check_name)
        );
    `);
}

async function seedRepository(client) {
    const repository = await client.query(
        `
        INSERT INTO repositories(name, default_branch)
        VALUES ($1, $2)
        ON CONFLICT (name)
        DO UPDATE SET default_branch = EXCLUDED.default_branch
        RETURNING repository_id, name
        `,
        ['orders-service', 'main']
    );

    const repositoryId = repository.rows[0].repository_id;

    const mainBranch = await client.query(
        `
        INSERT INTO branches(repository_id, name, protected)
        VALUES ($1, $2, TRUE)
        ON CONFLICT (repository_id, name)
        DO UPDATE SET protected = TRUE
        RETURNING branch_id
        `,
        [repositoryId, 'main']
    );

    const featureBranch = await client.query(
        `
        INSERT INTO branches(repository_id, name, protected)
        VALUES ($1, $2, FALSE)
        ON CONFLICT (repository_id, name)
        DO UPDATE SET protected = FALSE
        RETURNING branch_id
        `,
        [repositoryId, 'feature/order-validation']
    );

    const pullRequest = await client.query(
        `
        INSERT INTO pull_requests(
            repository_id,
            source_branch_id,
            target_branch_id,
            title,
            state,
            head_sha
        )
        VALUES ($1, $2, $3, $4, 'open', $5)
        ON CONFLICT DO NOTHING
        RETURNING pull_request_id
        `,
        [
            repositoryId,
            featureBranch.rows[0].branch_id,
            mainBranch.rows[0].branch_id,
            'Validate order totals before persistence',
            'deadbeef12345678'
        ]
    );

    if (pullRequest.rowCount === 0) {
        const existing = await client.query(
            `
            SELECT pull_request_id
            FROM pull_requests
            WHERE repository_id = $1
              AND source_branch_id = $2
              AND target_branch_id = $3
              AND head_sha = $4
            `,
            [
                repositoryId,
                featureBranch.rows[0].branch_id,
                mainBranch.rows[0].branch_id,
                'deadbeef12345678'
            ]
        );

        return existing.rows[0].pull_request_id;
    }

    return pullRequest.rows[0].pull_request_id;
}

async function addReviewers(client) {
    const result = await client.query(`
        INSERT INTO reviewers(username)
        VALUES ('alice'), ('bob')
        ON CONFLICT (username) DO UPDATE SET active = TRUE
        RETURNING reviewer_id, username
    `);

    return Object.fromEntries(
        result.rows.map(row => [row.username, row.reviewer_id])
    );
}

async function recordReviewsAndChecks(client, pullRequestId, reviewers) {
    await client.query(
        `
        INSERT INTO reviews(
            pull_request_id,
            reviewer_id,
            state,
            commit_sha
        )
        VALUES ($1, $2, 'approved', $3)
        `,
        [pullRequestId, reviewers.alice, 'deadbeef12345678']
    );

    await client.query(
        `
        INSERT INTO reviews(
            pull_request_id,
            reviewer_id,
            state,
            commit_sha
        )
        VALUES ($1, $2, 'approved', $3)
        `,
        [pullRequestId, reviewers.bob, 'deadbeef12345678']
    );

    await client.query(
        `
        INSERT INTO status_checks(pull_request_id, check_name, status)
        VALUES
            ($1, 'unit-tests', 'passed'),
            ($1, 'security-scan', 'passed')
        ON CONFLICT (pull_request_id, check_name)
        DO UPDATE SET status = EXCLUDED.status
        `,
        [pullRequestId]
    );
}

async function evaluateMergeEligibility(client, pullRequestId) {
    const result = await client.query(
        `
        SELECT
            p.pull_request_id,
            p.state,
            p.title,
            COUNT(DISTINCT r.reviewer_id)
                FILTER (
                    WHERE r.state = 'approved'
                      AND r.commit_sha = p.head_sha
                ) AS approvals,
            COUNT(sc.status_check_id) AS total_checks,
            COUNT(sc.status_check_id)
                FILTER (WHERE sc.status = 'passed') AS passed_checks
        FROM pull_requests p
        LEFT JOIN reviews r
            ON r.pull_request_id = p.pull_request_id
        LEFT JOIN status_checks sc
            ON sc.pull_request_id = p.pull_request_id
        WHERE p.pull_request_id = $1
        GROUP BY
            p.pull_request_id,
            p.state,
            p.title,
            p.head_sha
        `,
        [pullRequestId]
    );

    const row = result.rows[0];

    if (!row) {
        throw new Error('Pull request not found');
    }

    const approvals = Number(row.approvals);
    const totalChecks = Number(row.total_checks);
    const passedChecks = Number(row.passed_checks);

    return {
        pullRequestId: row.pull_request_id,
        title: row.title,
        state: row.state,
        approvals,
        statusChecks: `${passedChecks}/${totalChecks} passed`,
        mergeAllowed:
            row.state === 'open' &&
            approvals >= 2 &&
            totalChecks > 0 &&
            passedChecks === totalChecks
    };
}

async function transactionExample() {
    const client = await pool.connect();

    try {
        await client.query('BEGIN');

        await client.query(
            `
            INSERT INTO reviewers(username)
            VALUES ($1)
            ON CONFLICT (username) DO NOTHING
            `,
            ['transaction-user']
        );

        await client.query(
            `
            INSERT INTO reviewers(username)
            VALUES ($1)
            ON CONFLICT (username) DO NOTHING
            `,
            ['transaction-user']
        );

        await client.query('COMMIT');
    } catch (error) {
        await client.query('ROLLBACK');
        console.error(`Transaction rolled back: ${error.message}`);
    } finally {
        // Pool clients must be released even when an operation fails.
        client.release();
    }
}

async function parameterizedQuery(title) {
    // Parameters are sent separately from SQL syntax, preventing the title
    // from being interpreted as executable SQL.
    const result = await pool.query(
        `
        SELECT pull_request_id, title, state
        FROM pull_requests
        WHERE title = $1
        `,
        [title]
    );

    return result.rows;
}

async function main() {
    let client;

    try {
        client = await pool.connect();
        console.log('PostgreSQL connection acquired from pool');

        await client.query('BEGIN');

        try {
            await createSchema(client);
            const pullRequestId = await seedRepository(client);
            const reviewers = await addReviewers(client);

            await recordReviewsAndChecks(
                client,
                pullRequestId,
                reviewers
            );

            await client.query('COMMIT');

            console.log(`Prepared pull request #${pullRequestId}`);

            const eligibility = await evaluateMergeEligibility(
                client,
                pullRequestId
            );

            console.table(eligibility);

            const searchResult = await parameterizedQuery(
                'Validate order totals before persistence'
            );

            console.table(searchResult);

        } catch (error) {
            await client.query('ROLLBACK');
            throw error;
        }
    } catch (error) {
        console.error(`Database workflow failed: ${error.message}`);
        process.exitCode = 1;
    } finally {
        if (client) {
            client.release();
        }

        await transactionExample();

        // Pool shutdown is different from releasing one client. It should be
        // performed when the Node.js process no longer needs database access.
        await pool.end();
        console.log('PostgreSQL pool closed');
    }
}

main();
