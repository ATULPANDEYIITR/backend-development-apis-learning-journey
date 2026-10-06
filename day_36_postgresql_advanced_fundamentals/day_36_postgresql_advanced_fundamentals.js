"use strict";

/*
 * PostgreSQL Advanced Fundamentals
 *
 * This Node.js program complements the Python implementation by treating
 * PostgreSQL as an event-producing data platform. It demonstrates:
 *
 * - schemas
 * - sequences
 * - UUIDs
 * - PostgreSQL enums
 * - JSONB
 * - arrays
 * - extensions
 * - transactions
 * - database-side validation
 * - PostgreSQL-specific query operators
 *
 * Dependency:
 *   npm install pg
 *
 * Runtime:
 *   Node.js 18+
 */

const { Client } = require("pg");
const crypto = require("crypto");

const config = {
  host: process.env.PGHOST || "localhost",
  port: Number(process.env.PGPORT || 5432),
  database: process.env.PGDATABASE || "postgres",
  user: process.env.PGUSER || "postgres",
  password: process.env.PGPASSWORD || undefined,
};

const SCHEMA = "advanced_fundamentals_js";

function quoteIdentifier(identifier) {
  /*
   * PostgreSQL identifiers cannot be parameterized with $1 parameters.
   * Restricting this helper to known application-generated identifiers avoids
   * constructing SQL from arbitrary external input.
   */
  if (!/^[a-z_][a-z0-9_]*$/i.test(identifier)) {
    throw new Error(`Unsafe PostgreSQL identifier: ${identifier}`);
  }

  return `"${identifier.replaceAll('"', '""')}"`;
}

const schemaIdentifier = quoteIdentifier(SCHEMA);

async function query(client, text, values = []) {
  const result = await client.query(text, values);
  return result;
}

async function createDatabaseObjects(client) {
  await query(
    client,
    `
      DROP SCHEMA IF EXISTS ${schemaIdentifier} CASCADE;

      CREATE SCHEMA ${schemaIdentifier};

      CREATE EXTENSION IF NOT EXISTS pgcrypto;

      CREATE TYPE ${schemaIdentifier}.change_state AS ENUM (
        'draft',
        'review',
        'approved',
        'merged',
        'closed'
      );

      CREATE SEQUENCE ${schemaIdentifier}.change_number_seq
        START WITH 5000
        INCREMENT BY 1
        CACHE 20;

      CREATE TABLE ${schemaIdentifier}.repositories (
        repository_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        repository_number BIGINT NOT NULL
          DEFAULT nextval('${SCHEMA}.change_number_seq'),
        repository_name TEXT NOT NULL UNIQUE,
        maintainers TEXT[] NOT NULL DEFAULT '{}',
        settings JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

        CONSTRAINT repositories_maintainer_count
          CHECK (cardinality(maintainers) <= 50)
      );

      CREATE TABLE ${schemaIdentifier}.changes (
        change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        repository_id UUID NOT NULL
          REFERENCES ${schemaIdentifier}.repositories(repository_id)
          ON DELETE CASCADE,
        title TEXT NOT NULL,
        state ${schemaIdentifier}.change_state NOT NULL DEFAULT 'draft',
        labels TEXT[] NOT NULL DEFAULT '{}',
        details JSONB NOT NULL DEFAULT '{}',
        author TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

        CONSTRAINT change_title_length
          CHECK (length(trim(title)) BETWEEN 5 AND 200)
      );

      CREATE INDEX repositories_settings_gin_idx
        ON ${schemaIdentifier}.repositories USING GIN (settings);

      CREATE INDEX repositories_maintainers_gin_idx
        ON ${schemaIdentifier}.repositories USING GIN (maintainers);

      CREATE INDEX changes_details_gin_idx
        ON ${schemaIdentifier}.changes USING GIN (details);

      CREATE INDEX changes_labels_gin_idx
        ON ${schemaIdentifier}.changes USING GIN (labels);

      CREATE INDEX changes_repository_idx
        ON ${schemaIdentifier}.changes(repository_id);
    `
  );
}

async function insertRepository(client) {
  const repository = {
    name: "platform-control-plane",
    maintainers: ["atul", "priya", "marco"],
    settings: {
      merge_policy: {
        required_approvals: 2,
        require_linear_history: true,
      },
      automation: {
        dependabot: true,
        deployment: "staging-first",
      },
      protected_environments: ["staging", "production"],
    },
  };

  /*
   * UUID generation happens inside PostgreSQL through pgcrypto. The client
   * receives the generated identifier using RETURNING.
   */
  const result = await query(
    client,
    `
      INSERT INTO ${schemaIdentifier}.repositories (
        repository_name,
        maintainers,
        settings
      )
      VALUES ($1, $2::text[], $3::jsonb)
      RETURNING repository_id, repository_number, repository_name
    `,
    [
      repository.name,
      repository.maintainers,
      JSON.stringify(repository.settings),
    ]
  );

  return result.rows[0];
}

async function createChanges(client, repository) {
  const changes = [
    {
      title: "Require signed release metadata",
      labels: ["security", "release"],
      details: {
        risk: "medium",
        files_changed: 7,
        tests: {
          unit: true,
          integration: true,
        },
        reviewers: ["priya", "marco"],
      },
    },
    {
      title: "Add deployment audit events",
      labels: ["observability", "audit"],
      details: {
        risk: "low",
        files_changed: 4,
        tests: {
          unit: true,
          integration: false,
        },
        reviewers: ["priya"],
      },
    },
  ];

  const inserted = [];

  for (const change of changes) {
    const result = await query(
      client,
      `
        INSERT INTO ${schemaIdentifier}.changes (
          repository_id,
          title,
          labels,
          details,
          author,
          state
        )
        VALUES (
          $1,
          $2,
          $3::text[],
          $4::jsonb,
          $5,
          'review'
        )
        RETURNING change_id, title, state, labels, details
      `,
      [
        repository.repository_id,
        change.title,
        change.labels,
        JSON.stringify(change.details),
        "atul",
      ]
    );

    inserted.push(result.rows[0]);
  }

  return inserted;
}

async function queryJsonb(client) {
  const result = await query(
    client,
    `
      SELECT
        title,
        details ->> 'risk' AS risk,
        details -> 'tests' AS tests,
        details #>> '{reviewers,0}' AS first_reviewer
      FROM ${schemaIdentifier}.changes
      WHERE details @> '{"tests": {"unit": true}}'::jsonb
      ORDER BY title
    `
  );

  console.log("\nJSONB containment and traversal:");
  console.table(result.rows);
}

async function queryArrays(client) {
  const result = await query(
    client,
    `
      SELECT
        title,
        labels,
        cardinality(labels) AS label_count
      FROM ${schemaIdentifier}.changes
      WHERE 'security' = ANY(labels)
         OR 'audit' = ANY(labels)
      ORDER BY title
    `
  );

  console.log("\nArray membership:");
  console.table(result.rows);

  const expanded = await query(
    client,
    `
      SELECT
        c.title,
        label
      FROM ${schemaIdentifier}.changes AS c
      CROSS JOIN LATERAL unnest(c.labels) AS label
      ORDER BY c.title, label
    `
  );

  console.log("\nExpanded labels:");
  console.table(expanded.rows);
}

async function updateJsonb(client) {
  await query(
    client,
    `
      UPDATE ${schemaIdentifier}.changes
      SET details = jsonb_set(
        details,
        '{review_policy}',
        jsonb_build_object(
          'required_approvals', 2,
          'dismiss_stale_approvals', true
        ),
        true
      )
      WHERE title = 'Require signed release metadata'
    `
  );

  const result = await query(
    client,
    `
      SELECT
        title,
        details -> 'review_policy' AS review_policy
      FROM ${schemaIdentifier}.changes
      WHERE title = 'Require signed release metadata'
    `
  );

  console.log("\nUpdated JSONB document:");
  console.table(result.rows);
}

async function demonstrateTransaction(client, repositoryId) {
  await client.query("BEGIN");

  try {
    const result = await query(
      client,
      `
        INSERT INTO ${schemaIdentifier}.changes (
          repository_id,
          title,
          labels,
          details,
          author,
          state
        )
        VALUES (
          $1,
          $2,
          $3::text[],
          $4::jsonb,
          $5,
          'approved'
        )
        RETURNING change_id
      `,
      [
        repositoryId,
        "Transactionally created change",
        ["database", "transaction"],
        JSON.stringify({
          transaction: "explicit",
          atomicity: true,
        }),
        "automation",
      ]
    );

    /*
     * PostgreSQL transactions make multiple related operations atomic. If
     * either operation fails, the catch branch rolls back the whole unit.
     */
    await query(
      client,
      `
        UPDATE ${schemaIdentifier}.repositories
        SET settings = jsonb_set(
          settings,
          '{last_transactional_change}',
          to_jsonb($1::text),
          true
        )
        WHERE repository_id = $2
      `,
      [result.rows[0].change_id, repositoryId]
    );

    await client.query("COMMIT");
    console.log("\nTransaction committed.");
  } catch (error) {
    await client.query("ROLLBACK");
    console.error("Transaction rolled back:", error.message);
  }
}

async function inspectPostgresTypes(client) {
  const result = await query(
    client,
    `
      SELECT
        c.column_name,
        c.data_type,
        c.udt_schema,
        c.udt_name
      FROM information_schema.columns AS c
      WHERE c.table_schema = $1
      ORDER BY c.table_name, c.ordinal_position
    `,
    [SCHEMA]
  );

  console.log("\nPostgreSQL column types:");
  console.table(result.rows);
}

async function inspectSequence(client) {
  const result = await query(
    client,
    `
      SELECT
        schemaname,
        sequencename,
        start_value,
        increment_by,
        cache_size
      FROM pg_sequences
      WHERE schemaname = $1
    `,
    [SCHEMA]
  );

  console.log("\nSequence metadata:");
  console.table(result.rows);

  const nextValue = await query(
    client,
    `SELECT nextval('${SCHEMA}.change_number_seq') AS next_change_number`
  );

  console.log("\nSequence allocation:");
  console.table(nextValue.rows);
}

async function demonstrateUuidGeneration(client) {
  const result = await query(
    client,
    `
      SELECT
        gen_random_uuid() AS postgres_uuid,
        pg_typeof(gen_random_uuid()) AS postgres_type,
        $1::uuid AS client_uuid,
        pg_typeof($1::uuid) AS client_type
    `,
    [crypto.randomUUID()]
  );

  console.log("\nUUID generation and typing:");
  console.table(result.rows);
}

async function demonstrateValidation(client) {
  try {
    await query(
      client,
      `
        INSERT INTO ${schemaIdentifier}.changes (
          repository_id,
          title,
          labels,
          details,
          author
        )
        SELECT
          repository_id,
          'bad',
          ARRAY['invalid'],
          '{}'::jsonb,
          'tester'
        FROM ${schemaIdentifier}.repositories
        LIMIT 1
      `
    );
  } catch (error) {
    console.log(
      "\nExpected constraint failure:",
      error.code,
      error.message
    );
  }
}

async function main() {
  const client = new Client(config);

  try {
    await client.connect();

    console.log(
      `Connected to PostgreSQL ${config.host}:${config.port}/${config.database}`
    );

    await createDatabaseObjects(client);

    const repository = await insertRepository(client);
    console.log("\nCreated repository:");
    console.table([repository]);

    const changes = await createChanges(client, repository);
    console.log("\nCreated changes:");
    console.table(changes);

    await queryJsonb(client);
    await queryArrays(client);
    await updateJsonb(client);
    await demonstrateTransaction(client, repository.repository_id);
    await inspectPostgresTypes(client);
    await inspectSequence(client);
    await demonstrateUuidGeneration(client);
    await demonstrateValidation(client);

    const summary = await query(
      client,
      `
        SELECT
          r.repository_name,
          COUNT(c.change_id) AS change_count,
          COUNT(*) FILTER (
            WHERE c.state = 'approved'
          ) AS approved_count
        FROM ${schemaIdentifier}.repositories AS r
        LEFT JOIN ${schemaIdentifier}.changes AS c
          ON c.repository_id = r.repository_id
        GROUP BY r.repository_id, r.repository_name
      `
    );

    console.log("\nRepository summary:");
    console.table(summary.rows);

    console.log(
      `\nSchema ${SCHEMA} remains available for inspection.`
    );
  } catch (error) {
    console.error("Program failed:", error);
    process.exitCode = 1;
  } finally {
    await client.end();
  }
}

main();
