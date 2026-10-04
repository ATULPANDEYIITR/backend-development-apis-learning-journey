"""
Database Normalization: 1NF, 2NF, 3NF, BCNF, Denormalization, and Practical Design

Self-contained executable demonstration using only the Python standard library.

The examples use a software-development organization because normalization decisions
are easier to see when entities have real dependencies:

    teams -> projects -> developers -> project assignments
    projects -> releases
    developers -> skills

The script deliberately demonstrates:
- An unnormalized repeating-group structure
- First Normal Form (1NF)
- Second Normal Form (2NF)
- Third Normal Form (3NF)
- Boyce-Codd Normal Form (BCNF)
- Lossless decomposition
- Functional-dependency reasoning
- Candidate keys and determinants
- Dependency-preserving decomposition
- Denormalization for read performance
- Practical integrity and indexing considerations
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from typing import Iterable, Sequence
import copy


def heading(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def show_rows(title: str, rows: Iterable[dict]) -> None:
    print(f"\n{title}")
    rows = list(rows)
    if not rows:
        print("(no rows)")
        return

    columns = list(rows[0])
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    print(" | ".join(column.ljust(widths[column]) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" | ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


# ---------------------------------------------------------------------------
# 1NF: atomic values and removal of repeating groups
# ---------------------------------------------------------------------------

def demonstrate_unnormalized_data() -> None:
    heading("Unnormalized relation: repeating groups")

    # A project row contains multiple developer IDs and multiple skill names
    # inside strings. This makes individual values difficult to address,
    # validate, index, and constrain at the relational level.
    unnormalized = [
        {
            "project_id": "P100",
            "project_name": "Market Analytics",
            "team_id": "T10",
            "team_name": "Data Platform",
            "developer_ids": "D01,D02",
            "developer_names": "Asha, Ravi",
            "skills": "Python,SQL,PostgreSQL",
        },
        {
            "project_id": "P200",
            "project_name": "Risk Engine",
            "team_id": "T10",
            "team_name": "Data Platform",
            "developer_ids": "D02,D03",
            "developer_names": "Ravi, Meera",
            "skills": "Python,C++",
        },
    ]
    show_rows("Repeating groups violate the atomic-value requirement of 1NF:", unnormalized)


def convert_to_1nf() -> list[dict]:
    # One row now represents one project/developer assignment and one skill.
    # Each column contains one value rather than a list encoded in text.
    rows = [
        {
            "project_id": "P100",
            "project_name": "Market Analytics",
            "team_id": "T10",
            "team_name": "Data Platform",
            "developer_id": "D01",
            "developer_name": "Asha",
            "skill": "Python",
        },
        {
            "project_id": "P100",
            "project_name": "Market Analytics",
            "team_id": "T10",
            "team_name": "Data Platform",
            "developer_id": "D01",
            "developer_name": "Asha",
            "skill": "SQL",
        },
        {
            "project_id": "P100",
            "project_name": "Market Analytics",
            "team_id": "T10",
            "team_name": "Data Platform",
            "developer_id": "D02",
            "developer_name": "Ravi",
            "skill": "Python",
        },
        {
            "project_id": "P100",
            "project_name": "Market Analytics",
            "team_id": "T10",
            "team_name": "Data Platform",
            "developer_id": "D02",
            "developer_name": "Ravi",
            "skill": "PostgreSQL",
        },
    ]
    return rows


def demonstrate_1nf() -> list[dict]:
    heading("First Normal Form (1NF)")
    rows = convert_to_1nf()
    show_rows("Atomic values and separate rows for repeating relationships:", rows)

    # A simple atomicity check catches the original comma-separated-list error.
    for row in rows:
        if any("," in str(value) for value in row.values()):
            raise ValueError("1NF violation: a column contains multiple encoded values.")

    print("\n1NF property verified: every attribute value is atomic.")
    return rows


# ---------------------------------------------------------------------------
# Functional dependencies and candidate keys
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionalDependency:
    determinant: frozenset[str]
    dependent: frozenset[str]

    def __str__(self) -> str:
        left = ", ".join(sorted(self.determinant))
        right = ", ".join(sorted(self.dependent))
        return f"{left} -> {right}"


def attribute_closure(
    attributes: set[str],
    dependencies: Sequence[FunctionalDependency],
) -> set[str]:
    """
    Compute X+ for a set of attributes X.

    If a dependency's determinant is already contained in the closure,
    its dependent attributes can also be inferred.
    """
    closure = set(attributes)
    changed = True

    while changed:
        changed = False
        for dependency in dependencies:
            if dependency.determinant <= closure:
                before = len(closure)
                closure.update(dependency.dependent)
                changed |= len(closure) != before

    return closure


def candidate_keys(
    relation_attributes: set[str],
    dependencies: Sequence[FunctionalDependency],
) -> list[frozenset[str]]:
    """Find minimal candidate keys for small educational relations."""
    from itertools import combinations

    keys: list[frozenset[str]] = []
    ordered = sorted(relation_attributes)

    for size in range(1, len(ordered) + 1):
        for combination in combinations(ordered, size):
            candidate = frozenset(combination)

            if any(key <= candidate for key in keys):
                continue

            closure = attribute_closure(set(candidate), dependencies)
            if closure == relation_attributes:
                keys.append(candidate)

    return keys


def demonstrate_functional_dependencies() -> None:
    heading("Functional dependencies and candidate keys")

    attributes = {
        "project_id",
        "project_name",
        "team_id",
        "team_name",
        "developer_id",
        "developer_name",
        "skill",
    }

    dependencies = [
        FunctionalDependency(frozenset({"project_id"}), frozenset({"project_name", "team_id"})),
        FunctionalDependency(frozenset({"team_id"}), frozenset({"team_name"})),
        FunctionalDependency(frozenset({"developer_id"}), frozenset({"developer_name"})),
        FunctionalDependency(
            frozenset({"project_id", "developer_id", "skill"}),
            frozenset(),
        ),
    ]

    for dependency in dependencies:
        print(dependency)

    keys = candidate_keys(attributes, dependencies)
    print("\nCandidate keys inferred from the dependencies:")
    for key in keys:
        print("{" + ", ".join(sorted(key)) + "}")

    print(
        "\nThe composite assignment key contains project_id and developer_id "
        "when skill is excluded from the assignment relation."
    )


# ---------------------------------------------------------------------------
# 2NF: remove partial dependencies on part of a composite key
# ---------------------------------------------------------------------------

def demonstrate_2nf() -> dict[str, list[dict]]:
    heading("Second Normal Form (2NF)")

    # In this relation, (project_id, developer_id) identifies an assignment.
    # project_name depends only on project_id, and developer_name depends only
    # on developer_id. Those are partial dependencies on a composite key.
    assignment_1nf = [
        {
            "project_id": "P100",
            "developer_id": "D01",
            "project_name": "Market Analytics",
            "developer_name": "Asha",
            "allocation_percent": 60,
        },
        {
            "project_id": "P100",
            "developer_id": "D02",
            "project_name": "Market Analytics",
            "developer_name": "Ravi",
            "allocation_percent": 40,
        },
        {
            "project_id": "P200",
            "developer_id": "D02",
            "project_name": "Risk Engine",
            "developer_name": "Ravi",
            "allocation_percent": 70,
        },
    ]

    show_rows("1NF relation with partial dependencies:", assignment_1nf)

    projects = [
        {"project_id": "P100", "project_name": "Market Analytics"},
        {"project_id": "P200", "project_name": "Risk Engine"},
    ]

    developers = [
        {"developer_id": "D01", "developer_name": "Asha"},
        {"developer_id": "D02", "developer_name": "Ravi"},
    ]

    assignments = [
        {"project_id": "P100", "developer_id": "D01", "allocation_percent": 60},
        {"project_id": "P100", "developer_id": "D02", "allocation_percent": 40},
        {"project_id": "P200", "developer_id": "D02", "allocation_percent": 70},
    ]

    show_rows("Project relation after 2NF decomposition:", projects)
    show_rows("Developer relation after 2NF decomposition:", developers)
    show_rows("Assignment relation containing attributes dependent on the whole key:", assignments)

    print(
        "\nThe decomposition prevents a project name from being repeated once "
        "for every developer assigned to that project."
    )

    return {
        "projects": projects,
        "developers": developers,
        "assignments": assignments,
    }


# ---------------------------------------------------------------------------
# 3NF: remove transitive dependencies
# ---------------------------------------------------------------------------

def demonstrate_3nf() -> dict[str, list[dict]]:
    heading("Third Normal Form (3NF)")

    # team_name depends on team_id, while team_id depends on project_id.
    # Therefore project_id -> team_id -> team_name is a transitive dependency.
    project_2nf = [
        {
            "project_id": "P100",
            "project_name": "Market Analytics",
            "team_id": "T10",
            "team_name": "Data Platform",
        },
        {
            "project_id": "P200",
            "project_name": "Risk Engine",
            "team_id": "T10",
            "team_name": "Data Platform",
        },
        {
            "project_id": "P300",
            "project_name": "Security Monitor",
            "team_id": "T20",
            "team_name": "Security Engineering",
        },
    ]

    show_rows("2NF project relation containing a transitive dependency:", project_2nf)

    projects = [
        {"project_id": "P100", "project_name": "Market Analytics", "team_id": "T10"},
        {"project_id": "P200", "project_name": "Risk Engine", "team_id": "T10"},
        {"project_id": "P300", "project_name": "Security Monitor", "team_id": "T20"},
    ]

    teams = [
        {"team_id": "T10", "team_name": "Data Platform"},
        {"team_id": "T20", "team_name": "Security Engineering"},
    ]

    show_rows("Project relation after 3NF decomposition:", projects)
    show_rows("Team relation holding team-specific facts:", teams)

    print(
        "\nNow project_id determines project facts and team_id determines team facts. "
        "Changing a team's name requires one team-row update."
    )

    return {"projects": projects, "teams": teams}


# ---------------------------------------------------------------------------
# BCNF: every determinant must be a candidate key
# ---------------------------------------------------------------------------

def is_superkey(
    determinant: frozenset[str],
    attributes: set[str],
    dependencies: Sequence[FunctionalDependency],
) -> bool:
    return attribute_closure(set(determinant), dependencies) == attributes


def bcnf_violations(
    attributes: set[str],
    dependencies: Sequence[FunctionalDependency],
    candidate_keys_found: Sequence[frozenset[str]],
) -> list[FunctionalDependency]:
    violations = []

    for dependency in dependencies:
        # Trivial dependencies do not violate BCNF.
        if dependency.dependent <= dependency.determinant:
            continue

        if not is_superkey(dependency.determinant, attributes, dependencies):
            violations.append(dependency)

    return violations


def demonstrate_bcnf() -> None:
    heading("Boyce-Codd Normal Form (BCNF)")

    # Consider a scheduling relation:
    #
    #   (student, course, instructor)
    #
    # Assume:
    #   (student, course) -> instructor
    #   instructor -> course
    #
    # If an instructor teaches exactly one course, instructor determines course.
    # "instructor" is not a superkey because it does not determine student.
    # That dependency violates BCNF even though the relation can satisfy 3NF
    # under the usual 3NF definition because "course" participates in a
    # candidate key.
    attributes = {"student", "course", "instructor"}
    dependencies = [
        FunctionalDependency(
            frozenset({"student", "course"}),
            frozenset({"instructor"}),
        ),
        FunctionalDependency(
            frozenset({"instructor"}),
            frozenset({"course"}),
        ),
    ]

    keys = candidate_keys(attributes, dependencies)
    violations = bcnf_violations(attributes, dependencies, keys)

    print("Candidate keys:")
    for key in keys:
        print("{" + ", ".join(sorted(key)) + "}")

    print("\nBCNF violations:")
    for violation in violations:
        print(f"  {violation}")

    print(
        "\nBCNF decomposition separates the instructor-to-course dependency "
        "from student enrollment:"
    )

    instructor_course = [
        {"instructor": "I01", "course": "DB101"},
        {"instructor": "I02", "course": "DB201"},
    ]
    student_instructor = [
        {"student": "S01", "instructor": "I01"},
        {"student": "S02", "instructor": "I01"},
        {"student": "S03", "instructor": "I02"},
    ]

    show_rows("InstructorCourse:", instructor_course)
    show_rows("StudentInstructor:", student_instructor)

    print(
        "\nBCNF is stricter than 3NF: every non-trivial determinant must be a "
        "superkey, not merely a dependency whose right side is a prime attribute."
    )


# ---------------------------------------------------------------------------
# Lossless join demonstration
# ---------------------------------------------------------------------------

def natural_join(left: list[dict], right: list[dict]) -> list[dict]:
    if not left or not right:
        return []

    common = set(left[0]).intersection(right[0])
    result = []

    for lrow in left:
        for rrow in right:
            if all(lrow[column] == rrow[column] for column in common):
                merged = dict(lrow)
                merged.update(rrow)
                result.append(merged)

    return result


def demonstrate_lossless_join() -> None:
    heading("Lossless decomposition")

    projects = [
        {"project_id": "P100", "project_name": "Market Analytics", "team_id": "T10"},
        {"project_id": "P200", "project_name": "Risk Engine", "team_id": "T10"},
    ]

    teams = [
        {"team_id": "T10", "team_name": "Data Platform"},
    ]

    joined = natural_join(projects, teams)
    show_rows("Joining Project and Team reconstructs the original facts:", joined)

    print(
        "\nThe common key team_id provides the relationship needed for the join. "
        "A decomposition that produces spurious combinations would not be lossless."
    )


# ---------------------------------------------------------------------------
# Dependency preservation
# ---------------------------------------------------------------------------

def demonstrate_dependency_preservation() -> None:
    heading("Dependency preservation")

    print(
        "A useful normalized decomposition should allow important functional "
        "dependencies to be enforced without reconstructing the original relation."
    )

    print("\nExample dependencies:")
    print("  project_id -> project_name, team_id")
    print("  team_id -> team_name")
    print("  developer_id -> developer_name")

    print(
        "\nAfter decomposition, each dependency belongs to a single relation, "
        "so primary keys and UNIQUE constraints can enforce them directly."
    )


# ---------------------------------------------------------------------------
# Denormalization: deliberate redundancy for read performance
# ---------------------------------------------------------------------------

def demonstrate_denormalization() -> None:
    heading("Denormalization")

    normalized_projects = [
        {"project_id": "P100", "project_name": "Market Analytics", "team_id": "T10"},
        {"project_id": "P200", "project_name": "Risk Engine", "team_id": "T10"},
        {"project_id": "P300", "project_name": "Security Monitor", "team_id": "T20"},
    ]

    normalized_teams = [
        {"team_id": "T10", "team_name": "Data Platform"},
        {"team_id": "T20", "team_name": "Security Engineering"},
    ]

    # A reporting workload may repeatedly need project + team information.
    # A deliberately denormalized read model can store team_name beside the
    # project to reduce joins. The duplicate value becomes a consistency concern.
    read_model = []
    team_by_id = {row["team_id"]: row["team_name"] for row in normalized_teams}

    for project in normalized_projects:
        read_model.append(
            {
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "team_id": project["team_id"],
                "team_name": team_by_id[project["team_id"]],
            }
        )

    show_rows("Normalized source data:", normalized_projects)
    show_rows("Denormalized reporting model:", read_model)

    print(
        "\nThe duplicated team_name is intentional. It can improve read performance "
        "or simplify an analytics projection, but writes must keep both representations "
        "consistent."
    )

    # Demonstrate the failure mode created by uncontrolled redundancy.
    read_model[0]["team_name"] = "Renamed Data Platform"
    print(
        "\nAfter an incorrect partial update, the read model contains stale data:"
    )
    show_rows("Inconsistent denormalized row:", [read_model[0]])

    print(
        "\nA production design should update the projection transactionally, rebuild "
        "it from authoritative normalized tables, or accept explicitly managed "
        "eventual consistency."
    )


# ---------------------------------------------------------------------------
# Practical schema design and integrity checks
# ---------------------------------------------------------------------------

def validate_assignments(
    projects: list[dict],
    developers: list[dict],
    assignments: list[dict],
) -> list[str]:
    errors: list[str] = []

    project_ids = {row["project_id"] for row in projects}
    developer_ids = {row["developer_id"] for row in developers}
    seen_pairs: set[tuple[str, str]] = set()

    for assignment in assignments:
        pair = (assignment["project_id"], assignment["developer_id"])

        if assignment["project_id"] not in project_ids:
            errors.append(f"Unknown project: {assignment['project_id']}")

        if assignment["developer_id"] not in developer_ids:
            errors.append(f"Unknown developer: {assignment['developer_id']}")

        if pair in seen_pairs:
            errors.append(f"Duplicate assignment: {pair}")

        if not 0 < assignment["allocation_percent"] <= 100:
            errors.append(f"Invalid allocation: {pair}")

        seen_pairs.add(pair)

    return errors


def demonstrate_integrity() -> None:
    heading("Practical integrity checks after normalization")

    normalized = demonstrate_2nf()
    bad_assignments = copy.deepcopy(normalized["assignments"])
    bad_assignments.append(
        {
            "project_id": "P999",
            "developer_id": "D02",
            "allocation_percent": 50,
        }
    )
    bad_assignments.append(
        {
            "project_id": "P100",
            "developer_id": "D01",
            "allocation_percent": 120,
        }
    )

    errors = validate_assignments(
        normalized["projects"],
        normalized["developers"],
        bad_assignments,
    )

    for error in errors:
        print(f"Validation error: {error}")

    print(
        "\nApplication validation is useful, but the relational database should "
        "also enforce foreign keys, uniqueness, NOT NULL, and CHECK constraints."
    )


# ---------------------------------------------------------------------------
# Normalization decision helper
# ---------------------------------------------------------------------------

def recommend_design(
    write_frequency: str,
    join_cost: str,
    data_consistency_priority: str,
    analytical_read_frequency: str,
) -> str:
    """
    Illustrate that normalization is a design decision, not an absolute rule.

    The helper intentionally uses explicit factors rather than assuming that
    maximum normalization is always the optimal physical design.
    """
    if data_consistency_priority == "high" and write_frequency == "high":
        return "Prefer normalized authoritative tables; optimize with indexes and query design."

    if analytical_read_frequency == "high" and join_cost == "high":
        return (
            "Keep normalized source tables and consider a controlled denormalized "
            "reporting projection."
        )

    if write_frequency == "low" and analytical_read_frequency == "high":
        return (
            "A denormalized read model may be appropriate if its refresh and "
            "consistency strategy is explicit."
        )

    return "Start normalized, measure workload behavior, then denormalize only for a demonstrated need."


def demonstrate_design_tradeoffs() -> None:
    heading("Practical normalization decision")

    scenarios = [
        {
            "name": "Transactional project management",
            "write_frequency": "high",
            "join_cost": "low",
            "data_consistency_priority": "high",
            "analytical_read_frequency": "low",
        },
        {
            "name": "Executive project dashboard",
            "write_frequency": "low",
            "join_cost": "high",
            "data_consistency_priority": "medium",
            "analytical_read_frequency": "high",
        },
    ]

    for scenario in scenarios:
        decision = recommend_design(
            scenario["write_frequency"],
            scenario["join_cost"],
            scenario["data_consistency_priority"],
            scenario["analytical_read_frequency"],
        )
        print(f"{scenario['name']}: {decision}")


# ---------------------------------------------------------------------------
# End-to-end practical model
# ---------------------------------------------------------------------------

def build_normalized_model() -> dict[str, list[dict]]:
    """
    Construct a compact 3NF-style model.

    Each table represents one primary subject:
    - teams contain team facts
    - developers contain developer facts
    - projects contain project facts
    - assignments contain facts about a project/developer relationship
    - skills contain skill facts
    - developer_skills represent the many-to-many relationship
    """
    teams = [
        {"team_id": "T10", "team_name": "Data Platform"},
        {"team_id": "T20", "team_name": "Security Engineering"},
    ]

    developers = [
        {"developer_id": "D01", "developer_name": "Asha", "team_id": "T10"},
        {"developer_id": "D02", "developer_name": "Ravi", "team_id": "T10"},
        {"developer_id": "D03", "developer_name": "Meera", "team_id": "T20"},
    ]

    projects = [
        {"project_id": "P100", "project_name": "Market Analytics", "team_id": "T10"},
        {"project_id": "P200", "project_name": "Risk Engine", "team_id": "T10"},
        {"project_id": "P300", "project_name": "Security Monitor", "team_id": "T20"},
    ]

    assignments = [
        {"project_id": "P100", "developer_id": "D01", "allocation_percent": 60},
        {"project_id": "P100", "developer_id": "D02", "allocation_percent": 40},
        {"project_id": "P200", "developer_id": "D02", "allocation_percent": 70},
        {"project_id": "P200", "developer_id": "D03", "allocation_percent": 30},
    ]

    skills = [
        {"skill_id": "S01", "skill_name": "Python"},
        {"skill_id": "S02", "skill_name": "PostgreSQL"},
        {"skill_id": "S03", "skill_name": "C++"},
        {"skill_id": "S04", "skill_name": "Security Engineering"},
    ]

    developer_skills = [
        {"developer_id": "D01", "skill_id": "S01"},
        {"developer_id": "D01", "skill_id": "S02"},
        {"developer_id": "D02", "skill_id": "S01"},
        {"developer_id": "D02", "skill_id": "S02"},
        {"developer_id": "D02", "skill_id": "S03"},
        {"developer_id": "D03", "skill_id": "S04"},
    ]

    return {
        "teams": teams,
        "developers": developers,
        "projects": projects,
        "assignments": assignments,
        "skills": skills,
        "developer_skills": developer_skills,
    }


def demonstrate_end_to_end_query(model: dict[str, list[dict]]) -> None:
    heading("End-to-end query over the normalized model")

    developer_by_id = {row["developer_id"]: row for row in model["developers"]}
    project_by_id = {row["project_id"]: row for row in model["projects"]}
    skill_by_id = {row["skill_id"]: row for row in model["skills"]}

    result = []

    skills_by_developer: dict[str, list[str]] = defaultdict(list)
    for relation in model["developer_skills"]:
        skills_by_developer[relation["developer_id"]].append(
            skill_by_id[relation["skill_id"]]["skill_name"]
        )

    for assignment in model["assignments"]:
        developer = developer_by_id[assignment["developer_id"]]
        project = project_by_id[assignment["project_id"]]
        result.append(
            {
                "project": project["project_name"],
                "developer": developer["developer_name"],
                "allocation": assignment["allocation_percent"],
                "skills": ", ".join(sorted(skills_by_developer[developer["developer_id"]])),
            }
        )

    show_rows("Project staffing report assembled from normalized relations:", result)


def main() -> None:
    demonstrate_unnormalized_data()
    demonstrate_1nf()
    demonstrate_functional_dependencies()
    demonstrate_2nf()
    demonstrate_3nf()
    demonstrate_bcnf()
    demonstrate_lossless_join()
    demonstrate_dependency_preservation()
    demonstrate_denormalization()
    demonstrate_integrity()
    demonstrate_design_tradeoffs()

    heading("Normalized practical model")
    model = build_normalized_model()

    for table_name, rows in model.items():
        show_rows(table_name, rows)

    errors = validate_assignments(
        model["projects"],
        model["developers"],
        model["assignments"],
    )
    if errors:
        raise AssertionError(f"Valid model unexpectedly failed: {errors}")

    demonstrate_end_to_end_query(model)

    print(
        "\nDesign principle demonstrated: normalize authoritative transactional data "
        "around real dependencies and relationships; use denormalization deliberately "
        "when measured workload requirements justify controlled redundancy."
    )


if __name__ == "__main__":
    main()
