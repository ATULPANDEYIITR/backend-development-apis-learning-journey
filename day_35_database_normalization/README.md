# Database Normalization: 1NF, 2NF, 3NF, BCNF, Denormalization, and Practical Database Design

## Scope

This set of implementations treats normalization as a relational design discipline based on **functional dependencies, keys, relationship structure, and update anomalies**.

The central progression is:

- **1NF** controls the structure of attribute values and removes repeating groups.
- **2NF** removes partial dependencies on part of a composite candidate key.
- **3NF** removes transitive dependencies between non-key attributes.
- **BCNF** applies the stricter rule that every non-trivial determinant must be a superkey.
- **Denormalization** deliberately introduces redundancy when a measured workload benefits from it and the resulting consistency obligations can be controlled.

The examples use project-management and technical-team data because the domain exposes realistic dependencies:

`project_id -> project_name, team_id`

`team_id -> team_name`

`developer_id -> developer_name`

`(project_id, developer_id) -> allocation_percent`

A many-to-many relationship between developers and skills is represented by a separate associative relation.

---

## Why Normalization Matters

A relational table is not well designed merely because it has a primary key. The important question is whether every stored fact belongs to the relation represented by that key.

Consider a hypothetical table containing:

`project_id, project_name, team_id, team_name, developer_id, developer_name, allocation_percent`

If one row represents one developer assigned to one project, several different kinds of facts have been mixed together:

- `project_name` describes a project.
- `team_name` describes a team.
- `developer_name` describes a developer.
- `allocation_percent` describes a project/developer relationship.

The resulting redundancy produces anomalies.

An **update anomaly** occurs when one fact is duplicated across many rows and only some copies are changed.

An **insertion anomaly** occurs when a fact cannot be recorded naturally without also supplying an unrelated fact.

A **deletion anomaly** occurs when deleting one relationship accidentally removes the only stored copy of an independent fact.

Normalization separates these facts according to their dependencies.

---

## Functional Dependencies

A functional dependency expresses a rule of determination.

`A -> B` means that if two rows have the same value of `A`, they must have the same value of `B`.

For the project-management domain:

`project_id -> project_name`

means a project identifier determines exactly one project name.

`team_id -> team_name`

means a team identifier determines exactly one team name.

`developer_id -> developer_name`

means a developer identifier determines exactly one developer name.

For an assignment relation:

`(project_id, developer_id) -> allocation_percent`

means the allocation percentage is determined by the complete project/developer pair.

A functional dependency is a semantic rule about the data. It is not merely an observation about the rows currently stored.

That distinction matters when designing constraints. A table might happen to contain unique values today without those values being logically guaranteed to be unique tomorrow.

---

## Candidate Keys, Superkeys, and Determinants

A **superkey** is a set of attributes that uniquely identifies a row.

A **candidate key** is a minimal superkey. Removing any attribute from a candidate key means it no longer uniquely identifies the row.

For:

`Assignment(project_id, developer_id, allocation_percent)`

the pair:

`(project_id, developer_id)`

is the natural candidate key when a developer can have only one assignment record per project.

The individual `project_id` is not enough because several developers can work on the same project.

The individual `developer_id` is not enough because one developer can work on several projects.

A **determinant** is the left side of a functional dependency. In:

`team_id -> team_name`

`team_id` is the determinant.

Normalization repeatedly asks whether determinants and dependent attributes belong in the same relation.

---

## First Normal Form: 1NF

### Atomic values

The Python implementation begins with a deliberately unnormalized representation in which multiple developer IDs and skills are stored inside strings.

A value such as:

`"D01,D02"`

is one text value from the database's perspective. Application code must parse it to discover that it represents two relationships.

The 1NF representation instead stores separate rows:

`P100 | D01`

`P100 | D02`

Likewise, skills are represented as individual relationship rows rather than comma-separated text.

The important property is not simply "no commas." The actual requirement is that each attribute contains a single value appropriate to its domain and that repeating groups are represented relationally.

### Why 1NF is useful

Atomic storage makes predicates, constraints, joins, indexes, and updates meaningful.

A query can ask for the developer with ID `D01` without parsing a serialized list.

A foreign key can reference a developer identifier directly.

A unique constraint can operate on a relationship key.

An index can efficiently locate individual relationship rows.

### 1NF does not solve all redundancy

A table can satisfy 1NF while still containing severe redundancy.

For example:

`Project(project_id, project_name, developer_id, developer_name)`

can contain atomic values while repeating the project name and developer name across many rows.

That is why 2NF and 3NF address dependencies beyond atomicity.

---

## Second Normal Form: 2NF

2NF concerns **partial dependency on a composite candidate key**.

Suppose:

`Assignment(project_id, developer_id, project_name, developer_name, allocation_percent)`

has candidate key:

`(project_id, developer_id)`

The dependency:

`project_id -> project_name`

depends on only part of the composite key.

Likewise:

`developer_id -> developer_name`

depends on only one component.

These are partial dependencies.

The assignment relation should therefore contain the relationship-specific fact:

`(project_id, developer_id) -> allocation_percent`

while project and developer facts belong to their own relations.

The decomposition becomes:

`Project(project_id, project_name)`

`Developer(developer_id, developer_name)`

`Assignment(project_id, developer_id, allocation_percent)`

The C++ case study models this decomposition through a composite `std::pair` key.

The Java implementation uses the immutable `AssignmentKey` record:

`AssignmentKey(projectId, developerId)`

This is a useful application-level representation of the same relational idea.

The SQL implementation enforces the relationship using:

`PRIMARY KEY (project_id, developer_id)`

The database therefore rejects duplicate project/developer relationships.

---

## Third Normal Form: 3NF

3NF addresses **transitive dependencies**.

Consider:

`Project(project_id, project_name, team_id, team_name)`

with:

`project_id -> team_id`

and:

`team_id -> team_name`

The dependency chain is:

`project_id -> team_id -> team_name`

Therefore `team_name` is transitively dependent on `project_id`.

The project relation should store the team's identifier rather than copying the team's descriptive fact:

`Project(project_id, project_name, team_id)`

The team relation owns:

`Team(team_id, team_name)`

The project can recover the team name through a join.

This decomposition changes the ownership of the fact without losing the relationship.

### Update anomaly avoided by 3NF

If a team has 50 projects, storing `team_name` in every project row creates 50 potential copies.

A team rename then becomes a multi-row update.

If one row is missed, the database can contain two different names for the same team identifier.

With the normalized design, the authoritative fact exists once:

`T10 -> Data Platform`

Projects reference `T10`.

Renaming the team changes one row, and queries joining through `team_id` immediately see the new value.

---

## BCNF

Boyce-Codd Normal Form is stricter than 3NF.

The BCNF rule is:

> For every non-trivial functional dependency `X -> Y`, X must be a superkey.

The Java, C++, and SQL implementations use a teaching example:

`Teaching(student_id, course_id, instructor_id)`

with dependencies:

`(student_id, course_id) -> instructor_id`

and:

`instructor_id -> course_id`

The second dependency is problematic.

An instructor determines a course, but an instructor does not determine a student. Therefore `instructor_id` is not a superkey of the complete teaching relation.

That violates BCNF.

The decomposition separates the dependencies:

`InstructorCourse(instructor_id, course_id)`

`StudentInstructor(student_id, instructor_id)`

The relationship represented by the second table identifies which students are associated with instructors, while the first table records the course taught by each instructor.

### Why BCNF deserves separate treatment

3NF and BCNF are related but not interchangeable.

3NF permits some dependencies where the determinant is not a superkey when the dependent attribute is a prime attribute of a candidate key.

BCNF removes that exception.

As a result, BCNF can produce a cleaner dependency structure but can sometimes make dependency preservation more difficult than a 3NF decomposition.

The appropriate normal form depends on the actual dependency set and integrity requirements.

---

## Lossless Decomposition

Normalization should not destroy the information represented by the original relation.

A decomposition is **lossless** when joining the decomposed relations reconstructs the original information without generating incorrect combinations.

The project/team decomposition uses `team_id` as the connecting attribute:

`Project(project_id, project_name, team_id)`

joins with:

`Team(team_id, team_name)`

through:

`Project.team_id = Team.team_id`

The Python implementation includes a small natural-join routine to make this reconstruction visible.

The SQL implementation performs the same reconstruction with a relational `JOIN`.

A poor decomposition can create **spurious tuples**, where a join produces combinations that were not represented by the original facts.

Losslessness is therefore a fundamental test when decomposing relations.

---

## Dependency Preservation

A decomposition is useful when important dependencies remain enforceable in the resulting relations.

After separating Project and Team:

`project_id -> project_name, team_id`

can be enforced by the Project primary key.

`team_id -> team_name`

can be enforced by the Team primary key.

After separating Developer:

`developer_id -> developer_name`

can be enforced by the Developer primary key.

The dependencies do not need to be rediscovered by joining all the tables merely to enforce the basic ownership rules.

Dependency preservation is especially important for operational databases because integrity should be enforced as close as practical to the data.

---

## Practical Relational Model

The SQL implementation uses these authoritative relations:

| Relation | Primary key | Main responsibility |
| --- | --- | --- |
| `teams` | `team_id` | Stores team-specific facts |
| `developers` | `developer_id` | Stores developer-specific facts |
| `projects` | `project_id` | Stores project-specific facts |
| `skills` | `skill_id` | Stores skill-specific facts |
| `project_assignments` | `(project_id, developer_id)` | Stores project/developer relationship facts |
| `developer_skills` | `(developer_id, skill_id)` | Stores developer/skill relationship facts |

This arrangement prevents entity attributes from being copied into relationship tables unnecessarily.

The associative tables are particularly important because both project staffing and developer skills are many-to-many relationships.

---

## Referential Integrity

Normalization determines how facts are separated. Referential integrity determines whether the resulting relationships remain valid.

The SQL schema uses foreign keys such as:

`projects.team_id -> teams.team_id`

and:

`project_assignments.project_id -> projects.project_id`

and:

`project_assignments.developer_id -> developers.developer_id`

These constraints prevent a relationship from referring to a nonexistent parent.

The Java and C++ programs model the same rules through explicit service validation.

The JavaScript implementation uses `Map` objects to represent parent tables and checks those maps before creating relationships.

Application validation is useful for clear error messages, but a production relational database should still enforce critical integrity rules at the database layer. Application checks alone can be bypassed by another client or defeated by concurrent writes.

---

## Constraints Belonging at the Database Layer

The SQL schema uses several constraint types for distinct purposes.

### Primary keys

Primary keys identify the row represented by a relation.

Examples include:

`teams.team_id`

`projects.project_id`

and:

`project_assignments(project_id, developer_id)`

### Unique constraints

A unique constraint expresses a uniqueness rule that is not necessarily the primary identity of the relation.

The project name and team name are unique in the example because the model deliberately treats them as unique business identifiers.

A real system should add such a constraint only when the business rule actually guarantees uniqueness.

### Foreign keys

Foreign keys protect relationships between normalized entities.

They also make the dependency structure explicit.

### Check constraints

`allocation_percent BETWEEN 1 AND 100`

is a domain rule that belongs naturally in the database.

The database therefore rejects invalid allocation values regardless of which application submitted them.

---

## Indexing a Normalized Schema

Normalization can increase the number of relations and therefore increase the number of joins required by some queries.

That does not mean denormalization is automatically necessary.

Indexes can make normalized joins efficient.

The SQL implementation indexes:

`developers.team_id`

`projects.team_id`

`project_assignments.developer_id`

`developer_skills.skill_id`

Primary keys already create indexes in PostgreSQL, so redundant indexes on the same primary-key columns are unnecessary.

Index design should follow actual access patterns. An index has storage and write-maintenance costs, so creating an index for every column can make a write-heavy workload worse.

Query plans should be inspected before introducing duplicated data merely to avoid a join.

---

## Python Implementation

The Python program approaches normalization from the perspective of **dependency analysis and data transformation**.

It includes:

- an unnormalized representation with repeating groups;
- a 1NF transformation using atomic rows;
- functional-dependency objects;
- attribute-closure computation;
- candidate-key discovery;
- explicit 2NF decomposition;
- explicit 3NF decomposition;
- BCNF violation detection;
- a lossless natural-join demonstration;
- dependency-preservation discussion through decomposed relations;
- integrity validation;
- a normalized project-management model;
- a deliberately inconsistent denormalized reporting example.

The `attribute_closure()` function is particularly important because normalization reasoning depends on determining what attributes can be inferred from a determinant.

The program also demonstrates why normalization should not be treated as an irreversible performance rule. A normalized model can be the authoritative source while a carefully managed read model contains duplicated values for a particular workload.

---

## JavaScript Implementation

The JavaScript implementation takes a different approach by modeling normalization as an **application domain with indexed collections and event-driven read projections**.

`NormalizedProjectStore` uses `Map` objects as in-memory representations of relations.

The assignment key is represented as:

`projectId|developerId`

and is stored independently from project and developer attributes.

`Set` is used for the many-to-many developer/skill relationship so duplicate relationships can be detected.

The implementation also demonstrates a controlled denormalization pattern through `ProjectDashboard`.

The dashboard stores `teamName` beside project information even though the normalized source stores the team name only in the team entity.

This duplicated value is not authoritative.

When the team changes, an event is emitted and the projection is refreshed.

The asynchronous event boundary demonstrates a real trade-off: a denormalized read model can temporarily become stale unless the application provides a reliable synchronization mechanism.

This is fundamentally different from simply storing duplicate values in the main transactional tables without a consistency strategy.

---

## C++ Case Study

The C++ program treats normalization as a **technical data-modeling engine**.

The functional-dependency component computes attribute closure and determines whether a determinant is a superkey.

This is directly relevant to BCNF analysis.

The case study then implements a practical normalized project-management store using:

- `unordered_map` for entity lookup by primary identifier;
- `map<pair<string, string>, Assignment>` for composite relationship keys;
- `set<pair<string, string>>` for many-to-many uniqueness;
- exceptions for integrity failures.

The composite assignment key is important because it represents the semantics of the relationship directly.

A duplicate `(project_id, developer_id)` pair is rejected.

An unknown project or developer is rejected in the same conceptual role as a relational foreign-key constraint.

Allocation values are validated against the same domain range represented by the SQL `CHECK` constraint.

The program also separates the BCNF scheduling example from the project-management case study so that BCNF is demonstrated as a functional-dependency issue rather than being incorrectly treated as another name for 3NF.

---

## Java Enterprise Model

The Java implementation uses explicit domain types to make normalization boundaries visible.

`Team`, `Developer`, `Project`, and `Skill` are immutable records.

`AssignmentKey` represents the composite key of the project/developer relationship.

`DeveloperSkillKey` represents the composite key of the developer/skill relationship.

`ProjectManagementService` centralizes relationship creation and validates parent existence before inserting dependent relationships.

This makes the distinction between an entity and a relationship explicit:

`Project` describes a project.

`Developer` describes a developer.

`Assignment` describes what happens when a particular developer works on a particular project.

The service also demonstrates an update anomaly that normalization prevents. Renaming a team changes the Team record rather than requiring project records to contain and synchronize copied team names.

The Java example therefore emphasizes domain modeling and invariant enforcement rather than translating the Python algorithms line by line.

---

## SQL Data Model

The PostgreSQL script is the most direct demonstration of relational enforcement.

The DDL establishes primary keys, foreign keys, unique constraints, check constraints, and indexes.

The sample data demonstrates actual relationships instead of isolated normalization examples.

The SQL queries then reconstruct useful business information by joining the normalized relations.

The staffing query combines:

`project_assignments`

with:

`projects`

`developers`

`developer_skills`

and:

`skills`

This demonstrates a central consequence of normalization: useful business views are often reconstructed through joins rather than by copying every descriptive attribute into every relationship row.

The SQL script also includes transactional updates.

A team rename is performed against the single authoritative Team row, after which a join exposes the updated name for all related projects.

---

## Normalization and Denormalization

Normalization and denormalization are not simply opposites where one is always good and the other always bad.

A normalized transactional schema is generally valuable when:

- facts have clear ownership;
- writes are frequent;
- consistency is important;
- relationships change independently;
- duplicate facts would create update anomalies.

Denormalization can be useful when:

- a read-heavy workload repeatedly performs expensive joins;
- a reporting projection has a stable shape;
- analytical workloads benefit from precomputed or duplicated attributes;
- latency requirements justify additional storage;
- the synchronization strategy is explicit.

The key distinction is **authoritative data versus derived data**.

A denormalized reporting table should preferably be treated as a projection of authoritative normalized data.

It should not silently become a second independent source of truth.

---

## Controlled Denormalization

The JavaScript example demonstrates an event-driven projection.

The SQL example uses a view:

`project_staffing_read_model`

A database view does not physically duplicate the data. It provides a convenient query shape while retaining normalized storage.

For workloads that genuinely need physically stored derived data, PostgreSQL can use a materialized view or a separately maintained reporting table.

Physical denormalization introduces additional responsibilities:

- refresh timing;
- transaction boundaries;
- failure recovery;
- duplicate-data reconciliation;
- monitoring for stale values;
- rebuild procedures;
- additional storage;
- more complicated writes.

A performance improvement is not sufficient justification by itself. The workload should demonstrate that the additional complexity solves an actual bottleneck.

---

## Normalization Versus Query Complexity

A common criticism of normalization is that it creates too many joins.

The correct response is to distinguish **logical design** from **physical execution**.

A normalized logical model can still have:

- indexes;
- query optimization;
- covering indexes;
- partitioning where appropriate;
- materialized views;
- caching;
- read replicas;
- specialized analytical models.

A join between indexed relations is not inherently expensive.

The cost depends on relation sizes, cardinality, selectivity, indexes, query shape, statistics, and the database optimizer.

Duplicating a column simply because a query contains a join can move cost from reads to writes without solving the underlying workload problem.

---

## Common Design Mistakes

### Treating 1NF as "one table per entity"

1NF is about atomic values and repeating groups. It does not require every business concept to become a separate table.

The actual decomposition is driven by dependencies and relationship semantics.

### Assuming every composite key means the table violates 2NF

A composite key is not itself a normalization problem.

2NF becomes relevant when a non-key attribute depends on only part of that composite key.

If an attribute depends on the complete composite key, it belongs naturally in that relationship.

### Removing every transitive-looking attribute mechanically

3NF depends on actual functional dependencies.

A column should not be moved merely because it looks descriptive. The decision should be based on what determines the value and what the relation represents.

### Treating BCNF as identical to 3NF

BCNF is stricter.

A relation can satisfy 3NF while violating BCNF under particular dependency structures.

### Denormalizing before measuring

Premature denormalization can create synchronization problems that are harder to debug than the original query-performance problem.

The normalized model should usually be the baseline against which performance is measured.

### Relying only on application validation

Application code can validate an input, but another application, administrative query, batch process, or concurrent transaction can still modify the database.

Critical invariants should be enforced with relational constraints whenever possible.

---

## Lossless and Dependency-Preserving Design

A strong decomposition should be evaluated using more than the number of tables it creates.

Two important properties are:

**Losslessness:** joining the decomposed relations does not produce incorrect information.

**Dependency preservation:** important dependencies remain enforceable within the decomposed relations without requiring reconstruction of the original relation.

For the project-management model:

`Project(project_id, project_name, team_id)`

and:

`Team(team_id, team_name)`

retain the dependency structure needed to enforce project and team facts independently.

The foreign key connects the relations without copying the team's descriptive attributes.

---

## Performance Considerations

Normalization reduces redundancy but does not guarantee optimal performance.

The practical design process should consider:

- cardinality of relationships;
- frequency of reads versus writes;
- join selectivity;
- index maintenance;
- storage overhead;
- transaction contention;
- query-plan behavior;
- reporting requirements;
- data freshness requirements for derived models.

A normalized schema often benefits from indexing foreign-key columns used in joins.

Many-to-many tables frequently benefit from indexes in both relationship directions.

For example, `developer_skills` has a primary key beginning with `developer_id`, which supports developer-to-skill lookup. A separate index beginning with `skill_id` supports the reverse direction efficiently.

The SQL implementation explicitly demonstrates this indexing decision.

---

## Security and Data Integrity

Normalization itself is not a security mechanism, but clear data ownership makes authorization rules easier to reason about.

For example, a system can distinguish:

- permissions concerning a team;
- permissions concerning a project;
- permissions concerning a developer;
- permissions concerning a project/developer relationship.

Database constraints protect integrity, while authorization controls determine who is permitted to perform operations.

A production implementation should also consider transaction isolation, least-privilege database roles, auditing for sensitive changes, and safe handling of externally supplied identifiers.

These concerns complement normalization rather than replacing it.

---

## Practical Design Principle

The implementations use the following design boundary:

**Store each authoritative fact according to the dependency that determines it.**

When a value describes a project, keep it with the project.

When a value describes a team, keep it with the team.

When a value describes a developer, keep it with the developer.

When a value describes the relationship between two entities, keep it with that relationship.

When a workload genuinely benefits from duplicated or precomputed information, make the duplication an explicit read model or derived structure with a defined consistency strategy.

Normalization is therefore not simply a sequence of rules for splitting tables. It is a method for making the ownership, dependency, integrity, and lifecycle of stored facts explicit.
