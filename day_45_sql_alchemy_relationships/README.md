# SQLAlchemy Relationships: One-to-One, One-to-Many, Many-to-Many, and Cascading

## Scope

SQLAlchemy relationships describe how ORM objects correspond to related database rows. The four relationship areas covered here are related, but they solve different problems.

A **one-to-one** relationship means one parent object is associated with at most one dependent object. A typical example is an employee and an employee profile.

A **one-to-many** relationship means one parent can own multiple related objects. A department containing many employees is a one-to-many relationship.

A **many-to-many** relationship allows multiple rows on both sides to participate in the relationship. Employees working on projects require an association table because an employee can work on several projects and a project can contain several employees.

**Cascading** describes lifecycle behavior when related ORM objects are changed or deleted. It is not a fourth cardinality. It determines what happens to dependent objects or association rows when their related objects change.

The implementations use a single repository-development domain so that the relationship rules remain concrete:

- `Department -> Employee` represents one-to-many ownership.
- `Employee -> EmployeeProfile` represents one-to-one identity data.
- `Employee <-> Project` represents many-to-many project participation.
- Cascading controls what happens to profiles, employees, and association links during deletion.

## Relationship Cardinality

Cardinality answers the question: **how many related objects can participate in a relationship?**

The four concepts should not be collapsed into one mechanism.

| Relationship | ORM representation | Relational representation | Meaning |
|---|---|---|---|
| Employee to Profile | `uselist=False` | `employee_id UNIQUE` | One employee has at most one profile |
| Department to Employee | collection relationship | employee foreign key | One department has many employees |
| Employee to Project | `secondary=employee_project` | association table | Many employees can belong to many projects |
| Cascade | `cascade=...` | foreign-key `ON DELETE` where appropriate | Defines lifecycle behavior |

The ORM declaration describes how Python objects should behave. Database constraints still matter because the database is the final integrity boundary.

## One-to-One

The Python implementation maps an employee profile with:

`Employee.profile`

and configures the relationship with `uselist=False`.

That setting tells SQLAlchemy that the relationship should be represented as a scalar object rather than a collection.

The relational side is equally important. `EmployeeProfile.employee_id` has a `UNIQUE` constraint. Without that constraint, two profile rows could point to the same employee even if application code normally expects one profile.

The relationship therefore has two complementary layers:

- SQLAlchemy expresses the object-level cardinality.
- PostgreSQL or another relational database enforces the row-level uniqueness.

The Python demonstration deliberately attempts to create a second profile for Alice. The database rejects the duplicate relationship because `employee_id` is unique.

The Java and C++ implementations explicitly perform the same invariant check before creating a profile. This illustrates an important architectural distinction: application validation improves error messages, but database constraints protect integrity when multiple processes or applications write to the database.

A one-to-one relationship does not necessarily mean both records must exist. An employee may have no profile if the relationship is optional. The model therefore allows the profile reference to be absent while preventing more than one profile.

## One-to-Many

The department model demonstrates one-to-many behavior.

A department contains a collection of employees, while each employee contains a `department_id` foreign key. The foreign key is placed on the many side because every employee points to its owning department.

The SQLAlchemy relationship is represented through:

`Department.employees`

and:

`Employee.department`

The collection contains multiple employees, while each employee has one department reference.

Reassignment is also different from many-to-many association removal. Moving Alice from Engineering to Operations changes her `department_id`. It does not create a second employee and it does not create an independent association row.

The database model reinforces this through:

`employees.department_id REFERENCES departments(department_id)`

This prevents an employee from referencing a department that does not exist.

The example also uses `ON DELETE RESTRICT` for departments. This is a deliberate lifecycle policy. A department cannot be deleted while employees still depend on it. An application must first reassign or remove those employees.

That behavior contrasts with the employee-profile relationship, where deletion is allowed to cascade to the dependent profile.

## Many-to-Many

Many-to-many relationships require an association table.

The SQLAlchemy model defines:

`employee_project`

as the secondary table connecting employees and projects.

The relationship is then represented by:

`Employee.projects`

and:

`Project.employees`

Neither side owns the other in the same way that a department owns its employee collection. An employee can be assigned to several projects, and the same project can contain several employees.

The association table contains:

`employee_id`

and:

`project_id`

The composite primary key prevents the same employee-project pair from being inserted twice.

Removing Alice from Observability therefore removes the association rather than deleting Alice or the Observability project.

This distinction is central to many-to-many relationships. The association itself is the object being changed. The endpoint entities normally remain available.

The C++ implementation represents this with `unordered_set` collections on both endpoints. The Java implementation uses `Set<Long>` for the same uniqueness property. The JavaScript model uses JavaScript `Set` objects to prevent duplicate associations.

The SQL implementation makes the relationship explicit with the `employee_project` table and foreign keys to both endpoints.

## Cascading

Cascading concerns lifecycle behavior rather than cardinality.

The Python model uses:

`cascade="all, delete-orphan"`

for the department-to-employee relationship.

This expresses ownership semantics at the ORM level. An employee associated as a dependent child of a department can be removed as part of the department's lifecycle.

The employee-to-profile relationship also uses delete-orphan semantics because the profile is modeled as a dependent record whose existence has no independent meaning in this domain.

The many-to-many relationship uses a different strategy. Deleting an employee removes its association rows, but the projects themselves remain.

This produces three distinct lifecycle behaviors:

| Operation | Dependent behavior |
|---|---|
| Delete employee | Profile is removed |
| Delete employee | Employee-project association rows are removed |
| Remove employee from project | Project remains |
| Reassign employee | Employee remains and its department reference changes |
| Delete department | Domain policy determines whether employees are restricted or cascaded |

These differences are why cascade settings should be chosen according to domain ownership rather than applied mechanically to every relationship.

## ORM Cascade Versus Database Cascade

SQLAlchemy cascade and database `ON DELETE CASCADE` are related but not identical mechanisms.

An ORM cascade controls how SQLAlchemy manages related Python objects and SQL statements during a unit-of-work operation.

A database cascade is enforced by the database when a referenced row is deleted.

The SQL script uses database-level cascades for dependent relationships:

`employee_profiles.employee_id -> employees.employee_id ON DELETE CASCADE`

and:

`employee_project.employee_id -> employees.employee_id ON DELETE CASCADE`

The project endpoint also cascades to association rows when a project is deleted.

This protects integrity even when deletion does not originate from the SQLAlchemy ORM.

A robust application should therefore understand which rules belong in ORM configuration and which rules must be guaranteed by database constraints.

## Python Implementation

The Python program uses SQLAlchemy's declarative mapping style.

`DeclarativeBase` provides the base for mapped classes. `Mapped[...]` and `mapped_column()` express typed ORM attributes and database columns.

The relationship definitions are intentionally different:

- `Department.employees` is a collection because one department can contain many employees.
- `Employee.profile` is scalar because the profile is one-to-one.
- `Employee.projects` and `Project.employees` are collections connected through `employee_project`.

The Python program also enables SQLite foreign-key enforcement explicitly. SQLite can otherwise accept operations that would violate expected foreign-key behavior.

The `selectinload()` calls demonstrate relationship loading without repeatedly issuing one query for every individual related object. This is useful when a result set needs several related collections or dependent records.

The script tests actual failure behavior instead of only printing relationship declarations. A duplicate profile violates the one-to-one constraint, while an employee pointing to a nonexistent department violates the foreign-key constraint.

The relationship reassignment example demonstrates the difference between changing a many-to-one foreign key and modifying a many-to-many association.

## JavaScript Implementation

JavaScript does not execute SQLAlchemy itself, so its role is to model the relationship semantics through an event-driven in-memory repository.

The repository contains explicit collections for departments, employees, profiles, and projects.

The one-to-one rule is represented by `employee.profileId`. An employee cannot receive another profile when that reference is already populated.

The one-to-many relationship is represented by a department's `employeeIds` set and each employee's `departmentId`.

The many-to-many relationship uses sets on both employees and projects. Adding a project updates both endpoints, while removing the relationship updates only the association.

This bidirectional update is important. If only one side were updated, subsequent queries could produce contradictory relationship states.

The JavaScript deletion workflow explicitly removes the employee's profile and project associations. Projects are preserved because the relationship is many-to-many rather than dependent ownership.

The implementation also uses JavaScript errors to represent invalid relationship operations, such as creating a second profile or assigning an unknown employee to a project.

## C++ Case Study

The C++ program treats the relationship domain as an in-memory repository for an engineering organization.

The domain objects are:

`Department`, `Employee`, `Profile`, and `Project`.

`unordered_set` is used for relationship collections. This makes duplicate many-to-many associations naturally representable as a single set member and gives expected constant-time insertion and removal.

The repository implements explicit operations for:

- employee creation
- profile creation
- project creation
- project assignment
- project association removal
- department reassignment
- employee deletion
- department deletion

The one-to-one constraint is represented through `std::optional<ProfileId>`. A populated profile reference prevents another profile from being created for the same employee.

Employee deletion demonstrates cascading behavior. The employee's profile is removed, project association links are removed, and the projects remain.

Department deletion first copies employee identifiers because deleting employees mutates the department's employee set. This is a concrete implementation concern that occurs when modifying containers during traversal.

The program also illustrates performance trade-offs. Email uniqueness is implemented with a linear scan, making validation O(n). A production repository would normally use a database unique index or an additional hash-based lookup structure.

Relationship set operations are expected O(1), while cascading through an employee's relationships is proportional to the number of related objects.

## Java Implementation

The Java implementation uses an enterprise-oriented service and repository model.

The domain uses:

- `Department`
- `Employee`
- `EmployeeProfile`
- `Project`
- `RelationshipState`

`EmployeeProfile` is a Java record because it represents immutable profile data after creation.

`Employee` maintains an explicit relationship state. This prevents operations such as assigning projects to an employee that has already been deleted.

The repository exposes domain operations instead of allowing arbitrary callers to mutate relationship collections. This is useful when relationship changes need centralized validation, auditing, authorization, or transactional behavior in a larger application.

The one-to-one rule is enforced before profile creation. The many-to-many association uses `Set<Long>` so the employee-project pair cannot be duplicated within the in-memory model.

The deletion method demonstrates selective cascading. Employee deletion removes the employee's profile and association links while leaving project entities intact.

The department deletion operation explicitly traverses dependent employees and invokes employee deletion. This makes the lifecycle policy visible instead of hiding it inside a generic collection operation.

## SQL Data Model

The PostgreSQL schema separates endpoint entities from relationship data.

`departments` contains department identities.

`employees` contains the many-side foreign key:

`department_id`

`employee_profiles` contains a unique employee reference, producing one-to-one cardinality.

`projects` contains independent project identities.

`employee_project` contains the many-to-many association.

The database therefore represents the domain with a conventional relational structure:

`departments 1 -> N employees`

`employees 1 -> 1 employee_profiles`

`employees N -> N projects`

The many-to-many association is decomposed into two foreign-key relationships:

`employee_project.employee_id -> employees.employee_id`

and:

`employee_project.project_id -> projects.project_id`

The composite primary key prevents duplicate associations.

## Constraints and Integrity

Database constraints are important because ORM-level assumptions are not sufficient protection against every invalid state.

The schema uses:

- primary keys for entity identity
- unique constraints for department names, employee emails, project names, and profile ownership
- foreign keys for relationship integrity
- check constraints for controlled status values
- indexes for common relationship lookups

The unique `employee_profiles.employee_id` constraint is particularly important. A normal foreign key alone would permit several profile rows for one employee.

The composite primary key on `employee_project` prevents duplicate many-to-many relationships.

The employee-to-department foreign key prevents an employee from referencing a nonexistent department.

## Relationship Loading

SQLAlchemy relationship loading determines when related data is retrieved.

The Python implementation uses `selectinload()` for several examples. This strategy retrieves the primary rows and then loads related rows using additional set-oriented queries rather than issuing an individual query for every parent.

The practical issue is the N+1 query pattern. A program that retrieves many employees and then independently loads each employee's department, profile, and projects can generate excessive database traffic.

Relationship loading should therefore be selected according to the query's actual access pattern.

Lazy loading can be convenient for small interactions, while eager strategies can be useful when a known result set requires related objects.

The correct choice depends on cardinality, query frequency, result size, and transaction boundaries.

## Reassignment Versus Association Removal

These operations may appear similar but have different relational meanings.

When Alice moves from Engineering to Operations, the employee's `department_id` changes.

There is still one Alice record and one department reference.

When Alice is removed from Observability, the employee remains unchanged and the project remains unchanged. Only one row in the many-to-many association is removed.

This distinction is essential when designing ORM models because the location of the foreign key or association table determines what an update actually means.

## Orphan Behavior

An orphan is a dependent object that no longer has the relationship required by its ownership model.

The employee profile is treated as an owned dependent. Its lifecycle follows the employee.

The project is not treated as an employee-owned dependent. Removing the employee from a project must not delete the project.

The same distinction applies to department employees. Whether removing an employee from a department should delete the employee or simply reassign it is a domain decision.

`delete-orphan` should therefore be used only when the child has the intended ownership semantics. Applying it casually can cause destructive deletions that are surprising to application users.

## Transactional Behavior

Relationship modifications should normally occur within a transaction.

Creating an employee, assigning a profile, and creating project associations can require several SQL statements. If one operation fails while the earlier operations have already committed independently, the database may contain a partially completed relationship graph.

The Python implementation uses SQLAlchemy sessions as the unit of work.

The SQL implementation explicitly demonstrates `BEGIN`, relationship changes, and `COMMIT` or `ROLLBACK`.

The duplicate-profile example is rolled back after the database rejects the unique constraint violation.

This illustrates why relationship changes should be treated as a coherent unit rather than as unrelated writes.

## Common Relationship Failure Modes

A one-to-one relationship can fail when the ORM assumes uniqueness but the database does not enforce it. The result can be multiple database rows representing one logical profile.

A one-to-many relationship can fail when foreign keys are nullable or unconstrained even though the domain requires every employee to belong to a valid department.

A many-to-many relationship can fail when the association table lacks a unique key, allowing duplicate employee-project rows.

Cascading can fail when deletion rules are too broad. A cascade from an employee to a project would be inappropriate in this domain because projects have an independent lifecycle.

Relationship updates can also become inconsistent if application code updates only one side of a bidirectional in-memory association.

## Security and Production Considerations

Relationship definitions do not replace authorization.

A user who can modify an employee record should not automatically be assumed to have permission to move that employee between departments or delete the department itself.

Production systems should enforce authorization around relationship-changing operations.

Database constraints should remain enabled in every environment. Foreign-key enforcement that works in PostgreSQL but is disabled in a development database can hide integrity problems until deployment.

Deletion should be treated as a high-impact operation. Cascading can be useful for tightly owned dependent data such as an employee profile, but independent business entities such as projects generally require a different lifecycle policy.

Indexes should follow actual query patterns. Foreign-key columns used in joins and association-table lookups are common candidates for indexing.

## Performance Considerations

Relationship cardinality directly affects query size.

A one-to-one relationship usually produces a small related result, while a many-to-many relationship can expand rapidly because every employee-project pair creates an association row.

For many-to-many queries, indexing both sides of the association table is important when the application frequently asks both:

"Which projects belong to this employee?"

and:

"Which employees belong to this project?"

The Python implementation uses `selectinload()` to avoid repeatedly loading related rows one parent at a time.

The SQL implementation adds indexes on the employee foreign key and project foreign key in the association table.

For large production datasets, relationship loading strategy, pagination, indexes, transaction duration, and query plans should be evaluated together.

## Practical Relationship Map

The complete model can be represented as:

`Department`
→ contains many `Employee`

`Employee`
→ has at most one `EmployeeProfile`

`Employee`
↔ participates in many `Project`

`EmployeeProfile`
→ depends on `Employee`

`employee_project`
→ represents the many-to-many association

This separation makes the four concepts precise: cardinality defines how objects relate, association tables represent many-to-many links, and cascading defines lifecycle behavior.

## Implementation Comparison

| Concern | Python / SQLAlchemy | JavaScript | C++ | Java | PostgreSQL |
|---|---|---|---|---|---|
| One-to-one | `uselist=False` plus unique FK | scalar profile ID | `optional<ProfileId>` | nullable profile ID | `UNIQUE(employee_id)` |
| One-to-many | collection relationship | employee ID sets | department ID plus sets | collection-backed IDs | foreign key |
| Many-to-many | `secondary` association table | paired `Set` collections | paired `unordered_set` collections | paired `Set<Long>` collections | association table |
| Cascade | ORM cascade configuration | explicit repository deletion | explicit repository deletion | service-level lifecycle | `ON DELETE CASCADE` |
| Integrity | ORM plus database | application validation | repository validation | repository validation | constraints |
| Transactions | `Session` | repository operation boundary | repository operation boundary | service/repository boundary | `BEGIN` / `COMMIT` / `ROLLBACK` |

The implementations deliberately use different mechanisms because SQLAlchemy relationship behavior is not merely a matter of translating the same code into five programming languages. SQLAlchemy is the ORM layer, while JavaScript, C++, and Java model the domain behavior from different application perspectives, and PostgreSQL expresses the relational integrity directly.

## Design Boundary

The most important design boundary is between **cardinality** and **lifecycle**.

One-to-one, one-to-many, and many-to-many answer how records relate.

Cascading answers what should happen when one of those records is changed or deleted.

Keeping those questions separate makes relationship mappings easier to reason about and prevents accidental deletion policies from being embedded into otherwise ordinary relationship definitions.
