/*
 * Database Normalization: Enterprise Repository Management Domain
 *
 * Java 17, standard library only.
 *
 * The domain intentionally separates:
 *   Team             -> team-specific facts
 *   Developer        -> developer-specific facts
 *   Project          -> project-specific facts
 *   Assignment       -> facts about the project/developer relationship
 *   Skill            -> skill-specific facts
 *   DeveloperSkill   -> many-to-many relationship
 *
 * The service layer demonstrates the same integrity boundaries that a
 * relational database would enforce with primary keys, foreign keys,
 * UNIQUE constraints, and CHECK constraints.
 */

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class NormalizationEnterpriseDemo {

    record Team(String id, String name) {
        Team {
            requireText(id, "team id");
            requireText(name, "team name");
        }
    }

    record Developer(String id, String name, String teamId) {
        Developer {
            requireText(id, "developer id");
            requireText(name, "developer name");
            requireText(teamId, "team id");
        }
    }

    record Project(String id, String name, String teamId) {
        Project {
            requireText(id, "project id");
            requireText(name, "project name");
            requireText(teamId, "team id");
        }
    }

    record Skill(String id, String name) {
        Skill {
            requireText(id, "skill id");
            requireText(name, "skill name");
        }
    }

    record AssignmentKey(String projectId, String developerId) {
        AssignmentKey {
            requireText(projectId, "project id");
            requireText(developerId, "developer id");
        }
    }

    record Assignment(
        AssignmentKey key,
        int allocationPercent
    ) {
        Assignment {
            Objects.requireNonNull(key, "assignment key");
            if (allocationPercent < 1 || allocationPercent > 100) {
                throw new DomainException(
                    "Allocation must be between 1 and 100 percent."
                );
            }
        }
    }

    record DeveloperSkillKey(String developerId, String skillId) {
        DeveloperSkillKey {
            requireText(developerId, "developer id");
            requireText(skillId, "skill id");
        }
    }

    /*
     * This domain exception represents a business-integrity violation.
     * In a database-backed service, equivalent conditions should also be
     * protected by database constraints so concurrent requests cannot bypass
     * application-only validation.
     */
    static final class DomainException extends RuntimeException {
        DomainException(String message) {
            super(message);
        }
    }

    static final class ProjectManagementService {
        private final Map<String, Team> teams = new HashMap<>();
        private final Map<String, Developer> developers = new HashMap<>();
        private final Map<String, Project> projects = new HashMap<>();
        private final Map<String, Skill> skills = new HashMap<>();

        private final Map<AssignmentKey, Assignment> assignments = new HashMap<>();
        private final Set<DeveloperSkillKey> developerSkills = new HashSet<>();

        void registerTeam(Team team) {
            requireUnique(teams, team.id(), "team");
            teams.put(team.id(), team);
        }

        void registerDeveloper(Developer developer) {
            requireUnique(developers, developer.id(), "developer");
            requireExists(
                teams,
                developer.teamId(),
                "developer's team"
            );
            developers.put(developer.id(), developer);
        }

        void registerProject(Project project) {
            requireUnique(projects, project.id(), "project");
            requireExists(
                teams,
                project.teamId(),
                "project's team"
            );
            projects.put(project.id(), project);
        }

        void registerSkill(Skill skill) {
            requireUnique(skills, skill.id(), "skill");
            skills.put(skill.id(), skill);
        }

        void assignDeveloper(
            String projectId,
            String developerId,
            int allocationPercent
        ) {
            requireExists(projects, projectId, "project");
            requireExists(developers, developerId, "developer");

            AssignmentKey key = new AssignmentKey(projectId, developerId);

            if (assignments.containsKey(key)) {
                throw new DomainException(
                    "The developer is already assigned to this project."
                );
            }

            assignments.put(
                key,
                new Assignment(key, allocationPercent)
            );
        }

        void assignSkill(String developerId, String skillId) {
            requireExists(developers, developerId, "developer");
            requireExists(skills, skillId, "skill");

            DeveloperSkillKey key = new DeveloperSkillKey(
                developerId,
                skillId
            );

            if (!developerSkills.add(key)) {
                throw new DomainException(
                    "The developer already has this skill."
                );
            }
        }

        /*
         * A normalized query reconstructs the required business view by
         * joining relations conceptually. Entity attributes are not copied
         * into Assignment merely to make this report convenient.
         */
        List<StaffingRow> staffingReport() {
            List<StaffingRow> result = new ArrayList<>();

            Map<String, List<String>> skillsByDeveloper = new HashMap<>();

            for (DeveloperSkillKey relation : developerSkills) {
                Skill skill = skills.get(relation.skillId());

                skillsByDeveloper
                    .computeIfAbsent(relation.developerId(), ignored -> new ArrayList<>())
                    .add(skill.name());
            }

            for (Assignment assignment : assignments.values()) {
                Project project = projects.get(assignment.key().projectId());
                Developer developer = developers.get(
                    assignment.key().developerId()
                );

                List<String> developerSkillNames = new ArrayList<>(
                    skillsByDeveloper.getOrDefault(
                        developer.id(),
                        Collections.emptyList()
                    )
                );

                developerSkillNames.sort(String::compareTo);

                result.add(
                    new StaffingRow(
                        project.name(),
                        developer.name(),
                        assignment.allocationPercent(),
                        String.join(", ", developerSkillNames)
                    )
                );
            }

            result.sort(
                Comparator
                    .comparing(StaffingRow::project)
                    .thenComparing(StaffingRow::developer)
            );

            return result;
        }

        /*
         * This update changes the determinant's fact only once. Projects store
         * teamId rather than a duplicated teamName, so the database does not
         * need to repair multiple project rows after the rename.
         */
        void renameTeam(String teamId, String newName) {
            requireExists(teams, teamId, "team");

            requireText(newName, "new team name");

            teams.put(teamId, new Team(teamId, newName));
        }

        static <K, V> void requireUnique(
            Map<K, V> map,
            K key,
            String entity
        ) {
            if (map.containsKey(key)) {
                throw new DomainException(
                    "Duplicate " + entity + " identifier: " + key
                );
            }
        }

        static <K, V> void requireExists(
            Map<K, V> map,
            K key,
            String entity
        ) {
            if (!map.containsKey(key)) {
                throw new DomainException(
                    "Unknown " + entity + ": " + key
                );
            }
        }
    }

    record StaffingRow(
        String project,
        String developer,
        int allocation,
        String skills
    ) {}

    /*
     * BCNF example:
     *
     * Teaching(student, course, instructor)
     *
     * Functional dependencies:
     *   (student, course) -> instructor
     *   instructor -> course
     *
     * instructor is a determinant but not a superkey, so the dependency
     * violates BCNF. The domain types below make the decomposition explicit.
     */
    record InstructorCourse(String instructorId, String courseId) {}

    record StudentInstructor(String studentId, String instructorId) {}

    private static void demonstrateNormalForms() {
        heading("1NF: atomic attributes");

        System.out.println(
            "A value such as \"Java,SQL,PostgreSQL\" inside one skill column "
                + "is a repeating group. 1NF represents each skill as a separate "
                + "relationship row."
        );

        System.out.println("\n2NF: complete dependency on a composite key");
        System.out.println(
            "Assignment(projectId, developerId, allocation) contains a fact "
                + "about the complete project/developer relationship."
        );
        System.out.println(
            "projectName is not placed in Assignment because it depends only "
                + "on projectId. developerName is not placed there because it "
                + "depends only on developerId."
        );

        System.out.println("\n3NF: transitive dependency removal");
        System.out.println(
            "Project.projectId -> Project.teamId and Team.teamId -> Team.name. "
                + "Team.name therefore belongs to Team rather than Project."
        );

        System.out.println("\nBCNF: determinant must be a superkey");
        System.out.println(
            "If instructor -> course but instructor does not identify a student, "
                + "instructor is not a superkey. Separating InstructorCourse from "
                + "StudentInstructor removes the BCNF violation."
        );
    }

    private static void demonstrateEnterpriseWorkflow() {
        heading("Enterprise-oriented normalized domain");

        ProjectManagementService service = new ProjectManagementService();

        service.registerTeam(new Team("T10", "Data Platform"));
        service.registerTeam(new Team("T20", "Security Engineering"));

        service.registerDeveloper(new Developer("D01", "Asha", "T10"));
        service.registerDeveloper(new Developer("D02", "Ravi", "T10"));
        service.registerDeveloper(new Developer("D03", "Meera", "T20"));

        service.registerProject(
            new Project("P100", "Market Analytics", "T10")
        );
        service.registerProject(
            new Project("P200", "Risk Engine", "T10")
        );
        service.registerProject(
            new Project("P300", "Security Monitor", "T20")
        );

        service.registerSkill(new Skill("S01", "Java"));
        service.registerSkill(new Skill("S02", "SQL"));
        service.registerSkill(new Skill("S03", "Database Design"));
        service.registerSkill(new Skill("S04", "Security Engineering"));

        service.assignDeveloper("P100", "D01", 60);
        service.assignDeveloper("P100", "D02", 40);
        service.assignDeveloper("P200", "D02", 70);
        service.assignDeveloper("P200", "D03", 30);

        service.assignSkill("D01", "S02");
        service.assignSkill("D01", "S03");
        service.assignSkill("D02", "S01");
        service.assignSkill("D02", "S02");
        service.assignSkill("D03", "S04");

        printReport(service.staffingReport());

        heading("Integrity failure states");

        attempt(
            () -> service.assignDeveloper("P999", "D01", 50),
            "Unknown project"
        );

        attempt(
            () -> service.assignDeveloper("P100", "D01", 50),
            "Duplicate composite relationship"
        );

        attempt(
            () -> service.assignDeveloper("P100", "D02", 101),
            "Invalid allocation"
        );

        attempt(
            () -> service.assignSkill("D01", "S02"),
            "Duplicate many-to-many relationship"
        );

        heading("Update anomaly prevented by normalization");

        service.renameTeam("T10", "Data Platform Core");

        System.out.println(
            "Team T10 was renamed once. Projects retain T10 as the foreign-key "
                + "relationship and therefore do not contain stale copies of the team name."
        );
    }

    private static void printReport(List<StaffingRow> rows) {
        System.out.println(
            "\nProject | Developer | Allocation | Skills"
        );

        for (StaffingRow row : rows) {
            System.out.printf(
                "%s | %s | %d%% | %s%n",
                row.project(),
                row.developer(),
                row.allocation(),
                row.skills()
            );
        }
    }

    private static void attempt(
        Runnable operation,
        String description
    ) {
        try {
            operation.run();
            System.out.println(
                "Unexpected success: " + description
            );
        } catch (DomainException error) {
            System.out.println(
                description + " -> rejected: " + error.getMessage()
            );
        }
    }

    private static void requireText(
        String value,
        String field
    ) {
        if (value == null || value.isBlank()) {
            throw new DomainException(field + " is required.");
        }
    }

    private static void heading(String title) {
        System.out.println(
            "\n" + "=".repeat(78)
                + "\n"
                + title
                + "\n"
                + "=".repeat(78)
        );
    }

    public static void main(String[] args) {
        demonstrateNormalForms();
        demonstrateEnterpriseWorkflow();

        heading("Normalization and physical design");

        System.out.println(
            "Normalization determines the logical ownership of facts. "
                + "It does not prohibit indexes, caching, materialized views, "
                + "or controlled read models."
        );

        System.out.println(
            "A normalized transactional schema can still be optimized with "
                + "indexes and carefully designed queries. Denormalization is "
                + "a deliberate physical or read-model decision that introduces "
                + "redundancy and therefore creates an explicit consistency obligation."
        );
    }
}
