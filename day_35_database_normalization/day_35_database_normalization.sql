-- PostgreSQL-compatible database normalization case study.
--
-- Domain:
--   teams
--   developers
--   projects
--   skills
--   project_assignments
--   developer_skills
--
-- The schema is intentionally normalized so that:
--   1NF: relationship values are atomic and repeating groups become rows.
--   2NF: relationship attributes depend on the complete composite key.
--   3NF: team facts are separated from project facts to remove transitive
--        dependencies.
--
-- A BCNF example is represented separately with instructor/course relations.
-- A denormalized reporting view is included at the end to demonstrate
-- controlled redundancy without making the reporting projection authoritative.

DROP SCHEMA IF EXISTS normalization_demo CASCADE;
CREATE SCHEMA normalization_demo;
SET search_path TO normalization_demo;

-- ---------------------------------------------------------------------------
-- Core normalized entities
-- ---------------------------------------------------------------------------

CREATE TABLE teams (
    team_id       TEXT PRIMARY KEY,
    team_name     TEXT NOT NULL UNIQUE,
    CHECK (btrim(team_name) <> '')
);

CREATE TABLE developers (
    developer_id  TEXT PRIMARY KEY,
    developer_name TEXT NOT NULL,
    team_id       TEXT NOT NULL,
    CONSTRAINT developers_team_fk
        FOREIGN KEY (team_id)
        REFERENCES teams(team_id),
    CHECK (btrim(developer_name) <> '')
);

CREATE TABLE projects (
    project_id    TEXT PRIMARY KEY,
    project_name  TEXT NOT NULL,
    team_id       TEXT NOT NULL,
    CONSTRAINT projects_team_fk
        FOREIGN KEY (team_id)
        REFERENCES teams(team_id),
    CONSTRAINT projects_name_unique UNIQUE (project_name),
    CHECK (btrim(project_name) <> '')
);

CREATE TABLE skills (
    skill_id      TEXT PRIMARY KEY,
    skill_name    TEXT NOT NULL UNIQUE,
    CHECK (btrim(skill_name) <> '')
);

-- The primary key is composite because one developer can be assigned to many
-- projects and one project can contain many developers. allocation_percent is
-- a fact about the complete project/developer relationship.
CREATE TABLE project_assignments (
    project_id          TEXT NOT NULL,
    developer_id        TEXT NOT NULL,
    allocation_percent  INTEGER NOT NULL,
    PRIMARY KEY (project_id, developer_id),
    CONSTRAINT assignments_project_fk
        FOREIGN KEY (project_id)
        REFERENCES projects(project_id)
        ON DELETE CASCADE,
    CONSTRAINT assignments_developer_fk
        FOREIGN KEY (developer_id)
        REFERENCES developers(developer_id)
        ON DELETE CASCADE,
    CONSTRAINT allocation_range
        CHECK (allocation_percent BETWEEN 1 AND 100)
);

-- Many-to-many relationship. The composite primary key prevents the same
-- developer/skill fact from being inserted twice.
CREATE TABLE developer_skills (
    developer_id TEXT NOT NULL,
    skill_id     TEXT NOT NULL,
    PRIMARY KEY (developer_id, skill_id),
    CONSTRAINT developer_skills_developer_fk
        FOREIGN KEY (developer_id)
        REFERENCES developers(developer_id)
        ON DELETE CASCADE,
    CONSTRAINT developer_skills_skill_fk
        FOREIGN KEY (skill_id)
        REFERENCES skills(skill_id)
        ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- PostgreSQL automatically indexes primary keys and UNIQUE constraints.
-- Foreign-key columns should be indexed when they participate frequently in
-- joins or parent-delete checks.
CREATE INDEX developers_team_idx
    ON developers(team_id);

CREATE INDEX projects_team_idx
    ON projects(team_id);

CREATE INDEX assignments_developer_idx
    ON project_assignments(developer_id);

CREATE INDEX developer_skills_skill_idx
    ON developer_skills(skill_id);

-- ---------------------------------------------------------------------------
-- Sample normalized data
-- ---------------------------------------------------------------------------

INSERT INTO teams (team_id, team_name) VALUES
    ('T10', 'Data Platform'),
    ('T20', 'Security Engineering');

INSERT INTO developers (developer_id, developer_name, team_id) VALUES
    ('D01', 'Asha', 'T10'),
    ('D02', 'Ravi', 'T10'),
    ('D03', 'Meera', 'T20');

INSERT INTO projects (project_id, project_name, team_id) VALUES
    ('P100', 'Market Analytics', 'T10'),
    ('P200', 'Risk Engine', 'T10'),
    ('P300', 'Security Monitor', 'T20');

INSERT INTO skills (skill_id, skill_name) VALUES
    ('S01', 'PostgreSQL'),
    ('S02', 'Python'),
    ('S03', 'C++'),
    ('S04', 'Database Design'),
    ('S05', 'Security Engineering');

INSERT INTO project_assignments
    (project_id, developer_id, allocation_percent)
VALUES
    ('P100', 'D01', 60),
    ('P100', 'D02', 40),
    ('P200', 'D02', 70),
    ('P200', 'D03', 30);

INSERT INTO developer_skills (developer_id, skill_id) VALUES
    ('D01', 'S01'),
    ('D01', 'S02'),
    ('D01', 'S04'),
    ('D02', 'S01'),
    ('D02', 'S02'),
    ('D02', 'S03'),
    ('D03', 'S05');

-- ---------------------------------------------------------------------------
-- 1NF demonstration
-- ---------------------------------------------------------------------------

-- The normalized developer_skills table stores one skill relationship per row.
-- There is no "Python,SQL,C++" value that must be parsed by application code.
SELECT
    developer_id,
    skill_id
FROM developer_skills
ORDER BY developer_id, skill_id;

-- ---------------------------------------------------------------------------
-- 2NF demonstration
-- ---------------------------------------------------------------------------

-- project_assignments has a composite primary key:
--     (project_id, developer_id)
--
-- allocation_percent depends on both attributes because it describes the
-- assignment itself. Project name is intentionally absent because it depends
-- only on project_id. Developer name is intentionally absent because it depends
-- only on developer_id.
SELECT
    project_id,
    developer_id,
    allocation_percent
FROM project_assignments
ORDER BY project_id, developer_id;

-- ---------------------------------------------------------------------------
-- 3NF demonstration
-- ---------------------------------------------------------------------------

-- Project stores team_id but not team_name.
--
-- The dependency chain is:
--     project_id -> team_id
--     team_id -> team_name
--
-- Storing team_name in Project would introduce a transitive dependency.
SELECT
    p.project_id,
    p.project_name,
    p.team_id,
    t.team_name
FROM projects AS p
JOIN teams AS t
    ON t.team_id = p.team_id
ORDER BY p.project_id;

-- ---------------------------------------------------------------------------
-- Practical normalized query
-- ---------------------------------------------------------------------------

WITH developer_skill_list AS (
    SELECT
        ds.developer_id,
        string_agg(s.skill_name, ', ' ORDER BY s.skill_name) AS skills
    FROM developer_skills AS ds
    JOIN skills AS s
        ON s.skill_id = ds.skill_id
    GROUP BY ds.developer_id
)
SELECT
    p.project_name,
    d.developer_name,
    pa.allocation_percent,
    COALESCE(dsl.skills, '') AS skills
FROM project_assignments AS pa
JOIN projects AS p
    ON p.project_id = pa.project_id
JOIN developers AS d
    ON d.developer_id = pa.developer_id
LEFT JOIN developer_skill_list AS dsl
    ON dsl.developer_id = d.developer_id
ORDER BY p.project_name, d.developer_name;

-- ---------------------------------------------------------------------------
-- Database-level failure cases
-- ---------------------------------------------------------------------------

-- The following statements are intentionally disabled because this script
-- must execute successfully from start to finish. They demonstrate the exact
-- integrity rules that reject invalid data.
--
-- Unknown foreign key:
-- INSERT INTO project_assignments
--     (project_id, developer_id, allocation_percent)
-- VALUES
--     ('P999', 'D01', 50);
--
-- Duplicate composite key:
-- INSERT INTO project_assignments
--     (project_id, developer_id, allocation_percent)
-- VALUES
--     ('P100', 'D01', 60);
--
-- CHECK constraint:
-- INSERT INTO project_assignments
--     (project_id, developer_id, allocation_percent)
-- VALUES
--     ('P100', 'D02', 101);

-- ---------------------------------------------------------------------------
-- Transactional update demonstrating anomaly prevention
-- ---------------------------------------------------------------------------

-- Team name is stored exactly once. Projects reference team_id.
-- Renaming the team therefore does not require updating every project row.
BEGIN;

UPDATE teams
SET team_name = 'Data Platform Core'
WHERE team_id = 'T10';

COMMIT;

SELECT
    p.project_id,
    p.project_name,
    t.team_name
FROM projects AS p
JOIN teams AS t
    ON t.team_id = p.team_id
WHERE p.team_id = 'T10'
ORDER BY p.project_id;

-- ---------------------------------------------------------------------------
-- BCNF case study
-- ---------------------------------------------------------------------------

-- Teaching(student_id, course_id, instructor_id)
--
-- Assumptions:
--   (student_id, course_id) -> instructor_id
--   instructor_id -> course_id
--
-- The second dependency violates BCNF when instructor_id is not a superkey,
-- because one instructor determines a course but does not identify a student.
--
-- Decomposition:
--   instructor_courses(instructor_id, course_id)
--   student_instructors(student_id, instructor_id)

CREATE TABLE instructor_courses (
    instructor_id TEXT PRIMARY KEY,
    course_id     TEXT NOT NULL,
    CHECK (btrim(course_id) <> '')
);

CREATE TABLE student_instructors (
    student_id    TEXT NOT NULL,
    instructor_id TEXT NOT NULL,
    PRIMARY KEY (student_id, instructor_id),
    FOREIGN KEY (instructor_id)
        REFERENCES instructor_courses(instructor_id)
);

INSERT INTO instructor_courses (instructor_id, course_id) VALUES
    ('I01', 'DB101'),
    ('I02', 'DB201');

INSERT INTO student_instructors (student_id, instructor_id) VALUES
    ('ST01', 'I01'),
    ('ST02', 'I01'),
    ('ST03', 'I02');

SELECT
    si.student_id,
    si.instructor_id,
    ic.course_id
FROM student_instructors AS si
JOIN instructor_courses AS ic
    ON ic.instructor_id = si.instructor_id
ORDER BY si.student_id;

-- ---------------------------------------------------------------------------
-- Lossless reconstruction
-- ---------------------------------------------------------------------------

-- The normalized Project/Team decomposition can reconstruct the project-team
-- facts using team_id. A correct decomposition does not invent project/team
-- combinations that were not present in the source relation.
SELECT
    p.project_id,
    p.project_name,
    p.team_id,
    t.team_name
FROM projects AS p
JOIN teams AS t
    ON t.team_id = p.team_id;

-- ---------------------------------------------------------------------------
-- Dependency-oriented anomaly checks
-- ---------------------------------------------------------------------------

-- Every project references an existing team.
SELECT COUNT(*) AS projects_with_missing_teams
FROM projects AS p
LEFT JOIN teams AS t
    ON t.team_id = p.team_id
WHERE t.team_id IS NULL;

-- Every assignment references an existing project and developer.
SELECT COUNT(*) AS orphan_assignments
FROM project_assignments AS pa
LEFT JOIN projects AS p
    ON p.project_id = pa.project_id
LEFT JOIN developers AS d
    ON d.developer_id = pa.developer_id
WHERE p.project_id IS NULL
   OR d.developer_id IS NULL;

-- ---------------------------------------------------------------------------
-- Controlled denormalization
-- ---------------------------------------------------------------------------

-- This view creates a convenient read projection without making duplicated
-- values authoritative. The base tables remain normalized.
--
-- If a workload proves that the join is expensive, the same shape could be
-- implemented as a materialized view or maintained reporting table. Such a
-- design deliberately trades write simplicity and storage for read efficiency.
CREATE VIEW project_staffing_read_model AS
SELECT
    p.project_id,
    p.project_name,
    p.team_id,
    t.team_name,
    d.developer_id,
    d.developer_name,
    pa.allocation_percent
FROM project_assignments AS pa
JOIN projects AS p
    ON p.project_id = pa.project_id
JOIN teams AS t
    ON t.team_id = p.team_id
JOIN developers AS d
    ON d.developer_id = pa.developer_id;

SELECT *
FROM project_staffing_read_model
ORDER BY project_id, developer_id;

-- ---------------------------------------------------------------------------
-- Update-anomaly comparison
-- ---------------------------------------------------------------------------

-- This query shows that a team rename affects one authoritative row while
-- every project immediately sees the new value through the join.
UPDATE teams
SET team_name = 'Data Platform'
WHERE team_id = 'T10';

SELECT
    p.project_id,
    p.project_name,
    t.team_name
FROM projects AS p
JOIN teams AS t
    ON t.team_id = p.team_id
WHERE p.team_id = 'T10'
ORDER BY p.project_id;

-- ---------------------------------------------------------------------------
-- Normalization design record
-- ---------------------------------------------------------------------------

-- 1NF:
-- Atomic values and row-based relationships eliminate repeating groups.
--
-- 2NF:
-- Attributes describing a project/developer assignment remain dependent on
-- the entire composite key rather than only one key component.
--
-- 3NF:
-- Team-specific attributes live in Team, preventing project rows from carrying
-- attributes that depend on another non-key attribute.
--
-- BCNF:
-- The instructor/course example demonstrates the stricter rule that every
-- non-trivial determinant must be a superkey.
--
-- Denormalization:
-- The read-model view provides a performance-oriented shape while retaining
-- normalized authoritative tables as the source of truth.
