-- PostgreSQL implementation of SQLAlchemy-style relationship concepts.
--
-- The schema models:
--   Department -> Employee       one-to-many
--   Employee -> EmployeeProfile  one-to-one
--   Employee <-> Project         many-to-many
--
-- PostgreSQL is used because it provides strong referential-integrity
-- enforcement, DEFERRABLE constraints, transactional DML, useful indexing,
-- and expressive CTE/query support.

DROP SCHEMA IF EXISTS relationship_demo CASCADE;
CREATE SCHEMA relationship_demo;
SET search_path TO relationship_demo;

CREATE TABLE departments (
    department_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    employee_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id BIGINT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    employment_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT employees_status_chk
        CHECK (employment_status IN ('ACTIVE', 'INACTIVE')),

    CONSTRAINT employees_department_fk
        FOREIGN KEY (department_id)
        REFERENCES departments(department_id)
        ON DELETE RESTRICT
);

-- One-to-one is enforced by UNIQUE(employee_id), not only by application code.
CREATE TABLE employee_profiles (
    profile_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id BIGINT NOT NULL UNIQUE,
    job_title TEXT NOT NULL,
    office_location TEXT NOT NULL,

    CONSTRAINT employee_profiles_employee_fk
        FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id)
        ON DELETE CASCADE
);

CREATE TABLE projects (
    project_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    project_status TEXT NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT projects_status_chk
        CHECK (project_status IN ('ACTIVE', 'ARCHIVED'))
);

-- This is the relational representation of a many-to-many SQLAlchemy
-- relationship(secondary=...). The composite primary key prevents duplicate
-- employee/project associations.
CREATE TABLE employee_project (
    employee_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (employee_id, project_id),

    CONSTRAINT employee_project_employee_fk
        FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id)
        ON DELETE CASCADE,

    CONSTRAINT employee_project_project_fk
        FOREIGN KEY (project_id)
        REFERENCES projects(project_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_employees_department_id
    ON employees(department_id);

CREATE INDEX idx_employee_project_project_id
    ON employee_project(project_id);

CREATE INDEX idx_employee_project_employee_id
    ON employee_project(employee_id);

INSERT INTO departments (name)
VALUES
    ('Engineering'),
    ('Operations'),
    ('Data Platform');

INSERT INTO employees (
    department_id,
    full_name,
    email
)
SELECT
    d.department_id,
    employee_data.full_name,
    employee_data.email
FROM (
    VALUES
        ('Engineering', 'Alice Sharma', 'alice@example.com'),
        ('Engineering', 'Bob Mehta', 'bob@example.com'),
        ('Operations', 'Carol Singh', 'carol@example.com'),
        ('Data Platform', 'David Rao', 'david@example.com')
) AS employee_data(department_name, full_name, email)
JOIN departments d
    ON d.name = employee_data.department_name;

INSERT INTO employee_profiles (
    employee_id,
    job_title,
    office_location
)
SELECT
    e.employee_id,
    profile_data.job_title,
    profile_data.office_location
FROM (
    VALUES
        ('alice@example.com', 'Backend Engineer', 'Lucknow'),
        ('bob@example.com', 'Database Engineer', 'Delhi'),
        ('carol@example.com', 'Operations Analyst', 'Mumbai'),
        ('david@example.com', 'Data Engineer', 'Pune')
) AS profile_data(email, job_title, office_location)
JOIN employees e
    ON e.email = profile_data.email;

INSERT INTO projects (name)
VALUES
    ('API Platform'),
    ('Data Migration'),
    ('Observability');

INSERT INTO employee_project (employee_id, project_id)
SELECT e.employee_id, p.project_id
FROM (
    VALUES
        ('alice@example.com', 'API Platform'),
        ('alice@example.com', 'Observability'),
        ('bob@example.com', 'API Platform'),
        ('bob@example.com', 'Data Migration'),
        ('carol@example.com', 'Data Migration'),
        ('carol@example.com', 'Observability'),
        ('david@example.com', 'Data Migration')
) AS assignments(email, project_name)
JOIN employees e
    ON e.email = assignments.email
JOIN projects p
    ON p.name = assignments.project_name;

-- One-to-many query: each department with its employees.
SELECT
    d.name AS department,
    e.full_name,
    e.email
FROM departments d
LEFT JOIN employees e
    ON e.department_id = d.department_id
ORDER BY d.name, e.full_name;

-- One-to-one query: employee and exactly one profile when present.
SELECT
    e.full_name,
    e.email,
    ep.job_title,
    ep.office_location
FROM employees e
LEFT JOIN employee_profiles ep
    ON ep.employee_id = e.employee_id
ORDER BY e.full_name;

-- Many-to-many query: project membership.
SELECT
    p.name AS project,
    STRING_AGG(e.full_name, ', ' ORDER BY e.full_name) AS employees
FROM projects p
LEFT JOIN employee_project ep
    ON ep.project_id = p.project_id
LEFT JOIN employees e
    ON e.employee_id = ep.employee_id
GROUP BY p.project_id, p.name
ORDER BY p.name;

-- Identify employees with more than one project.
SELECT
    e.full_name,
    COUNT(ep.project_id) AS project_count
FROM employees e
JOIN employee_project ep
    ON ep.employee_id = e.employee_id
GROUP BY e.employee_id, e.full_name
HAVING COUNT(ep.project_id) > 1
ORDER BY project_count DESC, e.full_name;

-- Identify projects with no employees. This is useful when evaluating
-- whether deleting associations has accidentally removed endpoint records.
SELECT
    p.project_id,
    p.name
FROM projects p
LEFT JOIN employee_project ep
    ON ep.project_id = p.project_id
WHERE ep.project_id IS NULL;

-- The database itself prevents a second profile for the same employee.
-- The following transaction intentionally fails and is rolled back.
BEGIN;

INSERT INTO employee_profiles (
    employee_id,
    job_title,
    office_location
)
SELECT
    employee_id,
    'Duplicate Profile',
    'Chennai'
FROM employees
WHERE email = 'alice@example.com';

ROLLBACK;

-- Many-to-many association removal deletes only the relationship row.
BEGIN;

DELETE FROM employee_project
WHERE employee_id = (
    SELECT employee_id
    FROM employees
    WHERE email = 'alice@example.com'
)
AND project_id = (
    SELECT project_id
    FROM projects
    WHERE name = 'Observability'
);

COMMIT;

-- Confirm that the project still exists after the association was removed.
SELECT
    p.name,
    COUNT(ep.employee_id) AS employee_count
FROM projects p
LEFT JOIN employee_project ep
    ON ep.project_id = p.project_id
WHERE p.name = 'Observability'
GROUP BY p.project_id, p.name;

-- Reassignment for a one-to-many relationship changes the foreign key.
UPDATE employees
SET department_id = (
    SELECT department_id
    FROM departments
    WHERE name = 'Operations'
)
WHERE email = 'alice@example.com';

-- Confirm the reassignment.
SELECT
    e.full_name,
    e.email,
    d.name AS department
FROM employees e
JOIN departments d
    ON d.department_id = e.department_id
WHERE e.email = 'alice@example.com';

-- Demonstrate a dependent cascade:
-- deleting an employee removes its profile and many-to-many rows.
BEGIN;

DELETE FROM employees
WHERE email = 'alice@example.com';

COMMIT;

-- Alice's profile is gone because employee_profiles uses ON DELETE CASCADE.
SELECT *
FROM employee_profiles ep
JOIN employees e
    ON e.employee_id = ep.employee_id
WHERE e.email = 'alice@example.com';

-- Alice's association rows are also gone.
SELECT ep.*
FROM employee_project ep
WHERE ep.employee_id NOT IN (
    SELECT employee_id
    FROM employees
);

-- Projects themselves remain because the employee_project cascade targets
-- association rows rather than the project endpoint.
SELECT name
FROM projects
ORDER BY name;

-- Department deletion is intentionally restricted by the employee FK.
-- An application must decide whether employees should be reassigned or
-- deleted before the department can be removed.
--
-- This statement would fail while employees still belong to Operations:
--
-- DELETE FROM departments
-- WHERE name = 'Operations';

-- Transactional reassignment followed by safe department deletion.
BEGIN;

WITH target_department AS (
    SELECT department_id
    FROM departments
    WHERE name = 'Data Platform'
),
source_department AS (
    SELECT department_id
    FROM departments
    WHERE name = 'Operations'
)
UPDATE employees
SET department_id = (
    SELECT department_id
    FROM target_department
)
WHERE department_id = (
    SELECT department_id
    FROM source_department
);

DELETE FROM departments
WHERE name = 'Operations';

COMMIT;

-- Final integrity report.
SELECT
    d.name AS department,
    COUNT(e.employee_id) AS employee_count
FROM departments d
LEFT JOIN employees e
    ON e.department_id = d.department_id
GROUP BY d.department_id, d.name
ORDER BY d.name;

-- Orphan detection should return zero rows.
SELECT ep.profile_id, ep.employee_id
FROM employee_profiles ep
LEFT JOIN employees e
    ON e.employee_id = ep.employee_id
WHERE e.employee_id IS NULL;

-- Association integrity should return zero rows because both foreign keys
-- are enforced by the database.
SELECT ep.employee_id, ep.project_id
FROM employee_project ep
LEFT JOIN employees e
    ON e.employee_id = ep.employee_id
LEFT JOIN projects p
    ON p.project_id = ep.project_id
WHERE e.employee_id IS NULL
   OR p.project_id IS NULL;
