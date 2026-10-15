import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/*
 * Enterprise-oriented SQLAlchemy relationship model.
 *
 * The domain represents an internal engineering organization:
 *
 * Department -> Employee is one-to-many.
 * Employee -> EmployeeProfile is one-to-one.
 * Employee <-> Project is many-to-many.
 *
 * The service layer makes relationship rules explicit rather than hiding
 * them inside output statements. This mirrors the kinds of invariants that
 * an ORM mapping and database constraints must preserve.
 */
public class RelationshipGovernance {

    enum RelationshipState {
        ACTIVE,
        DELETED
    }

    static final class RelationshipException extends RuntimeException {
        RelationshipException(String message) {
            super(message);
        }
    }

    record EmployeeProfile(
        long id,
        long employeeId,
        String jobTitle,
        String officeLocation
    ) {
    }

    static final class Department {
        private final long id;
        private final String name;
        private final Set<Long> employeeIds = new HashSet<>();

        Department(long id, String name) {
            this.id = id;
            this.name = Objects.requireNonNull(name);
        }
    }

    static final class Project {
        private final long id;
        private final String name;
        private final Set<Long> employeeIds = new HashSet<>();

        Project(long id, String name) {
            this.id = id;
            this.name = Objects.requireNonNull(name);
        }
    }

    static final class Employee {
        private final long id;
        private final String name;
        private final String email;

        private long departmentId;
        private Long profileId;
        private final Set<Long> projectIds = new HashSet<>();

        private RelationshipState state = RelationshipState.ACTIVE;

        Employee(
            long id,
            String name,
            String email,
            long departmentId
        ) {
            this.id = id;
            this.name = Objects.requireNonNull(name);
            this.email = Objects.requireNonNull(email);
            this.departmentId = departmentId;
        }
    }

    /*
     * Repository owns the object graph. In a database-backed application,
     * these collections correspond conceptually to tables and relationship
     * tables. Keeping ownership explicit makes cascading operations auditable.
     */
    static final class Repository {
        private long nextDepartmentId = 1;
        private long nextEmployeeId = 1;
        private long nextProfileId = 1;
        private long nextProjectId = 1;

        private final Map<Long, Department> departments = new HashMap<>();
        private final Map<Long, Employee> employees = new HashMap<>();
        private final Map<Long, EmployeeProfile> profiles = new HashMap<>();
        private final Map<Long, Project> projects = new HashMap<>();

        Department createDepartment(String name) {
            requireText(name, "Department name");

            if (departments.values().stream()
                .anyMatch(department -> department.name.equals(name))) {
                throw new RelationshipException(
                    "Department name must be unique."
                );
            }

            Department department =
                new Department(nextDepartmentId++, name);

            departments.put(department.id, department);
            return department;
        }

        Employee createEmployee(
            String name,
            String email,
            Department department
        ) {
            requireText(name, "Employee name");
            requireText(email, "Employee email");

            if (employees.values().stream()
                .anyMatch(employee -> employee.email.equals(email))) {
                throw new RelationshipException(
                    "Employee email must be unique."
                );
            }

            Employee employee = new Employee(
                nextEmployeeId++,
                name,
                email,
                department.id
            );

            employees.put(employee.id, employee);
            department.employeeIds.add(employee.id);

            return employee;
        }

        EmployeeProfile createProfile(
            Employee employee,
            String jobTitle,
            String officeLocation
        ) {
            requireActive(employee);
            requireText(jobTitle, "Job title");
            requireText(officeLocation, "Office location");

            /*
             * uselist=False in SQLAlchemy expresses one-to-one ORM
             * cardinality. A UNIQUE constraint on employee_id is still
             * required at the relational database layer.
             */
            if (employee.profileId != null) {
                throw new RelationshipException(
                    "Employee already has a profile."
                );
            }

            EmployeeProfile profile = new EmployeeProfile(
                nextProfileId++,
                employee.id,
                jobTitle,
                officeLocation
            );

            profiles.put(profile.id(), profile);
            employee.profileId = profile.id();

            return profile;
        }

        Project createProject(String name) {
            requireText(name, "Project name");

            Project project =
                new Project(nextProjectId++, name);

            projects.put(project.id, project);
            return project;
        }

        void assignProject(Employee employee, Project project) {
            requireActive(employee);

            /*
             * A Set represents the uniqueness of the pair
             * (employee_id, project_id), similar to a composite primary key
             * in an association table.
             */
            employee.projectIds.add(project.id);
            project.employeeIds.add(employee.id);
        }

        void removeProjectAssignment(
            Employee employee,
            Project project
        ) {
            requireActive(employee);

            employee.projectIds.remove(project.id);
            project.employeeIds.remove(employee.id);
        }

        void moveEmployee(
            Employee employee,
            Department destination
        ) {
            requireActive(employee);

            Department source = departments.get(employee.departmentId);

            if (source == null) {
                throw new RelationshipException(
                    "Employee has an invalid source department."
                );
            }

            source.employeeIds.remove(employee.id);
            destination.employeeIds.add(employee.id);
            employee.departmentId = destination.id;
        }

        void deleteEmployee(Employee employee) {
            if (employee.state == RelationshipState.DELETED) {
                return;
            }

            Department department =
                departments.get(employee.departmentId);

            if (department != null) {
                department.employeeIds.remove(employee.id);
            }

            /*
             * Cascade employee -> profile. The profile is dependent on the
             * employee and cannot remain as an orphaned one-to-one child.
             */
            if (employee.profileId != null) {
                profiles.remove(employee.profileId);
                employee.profileId = null;
            }

            /*
             * Many-to-many cascade removes relationship rows from both
             * sides. The Project entities themselves remain intact.
             */
            for (Long projectId : Set.copyOf(employee.projectIds)) {
                Project project = projects.get(projectId);

                if (project != null) {
                    project.employeeIds.remove(employee.id);
                }
            }

            employee.projectIds.clear();
            employee.state = RelationshipState.DELETED;
        }

        void deleteDepartment(Department department) {
            /*
             * Explicitly cascade through the one-to-many relationship.
             * Copying IDs prevents concurrent modification of the collection.
             */
            for (Long employeeId :
                Set.copyOf(department.employeeIds)) {

                Employee employee = employees.get(employeeId);

                if (employee != null) {
                    deleteEmployee(employee);
                }
            }

            department.employeeIds.clear();
            departments.remove(department.id);
        }

        List<String> projectNames(Employee employee) {
            return employee.projectIds.stream()
                .map(projects::get)
                .filter(Objects::nonNull)
                .map(project -> project.name)
                .sorted()
                .toList();
        }

        String departmentName(Employee employee) {
            Department department =
                departments.get(employee.departmentId);

            return department == null
                ? "<invalid>"
                : department.name;
        }

        EmployeeProfile profile(Employee employee) {
            return employee.profileId == null
                ? null
                : profiles.get(employee.profileId);
        }

        private static void requireText(
            String value,
            String field
        ) {
            if (value == null || value.isBlank()) {
                throw new RelationshipException(
                    field + " is required."
                );
            }
        }

        private static void requireActive(Employee employee) {
            if (employee.state != RelationshipState.ACTIVE) {
                throw new RelationshipException(
                    "Operation cannot target a deleted employee."
                );
            }
        }
    }

    static void printEmployee(
        Repository repository,
        Employee employee
    ) {
        EmployeeProfile profile =
            repository.profile(employee);

        System.out.printf(
            "%s | %s | department=%s | profile=%s | projects=%s%n",
            employee.name,
            employee.email,
            repository.departmentName(employee),
            profile == null
                ? "<none>"
                : profile.jobTitle(),
            repository.projectNames(employee)
        );
    }

    public static void main(String[] args) {
        Repository repository = new Repository();

        Department engineering =
            repository.createDepartment("Engineering");

        Department operations =
            repository.createDepartment("Operations");

        Employee alice = repository.createEmployee(
            "Alice Sharma",
            "alice@example.com",
            engineering
        );

        Employee bob = repository.createEmployee(
            "Bob Mehta",
            "bob@example.com",
            engineering
        );

        Employee carol = repository.createEmployee(
            "Carol Singh",
            "carol@example.com",
            operations
        );

        repository.createProfile(
            alice,
            "Backend Engineer",
            "Lucknow"
        );

        repository.createProfile(
            bob,
            "Database Engineer",
            "Delhi"
        );

        repository.createProfile(
            carol,
            "Operations Analyst",
            "Mumbai"
        );

        Project apiPlatform =
            repository.createProject("API Platform");

        Project dataMigration =
            repository.createProject("Data Migration");

        Project observability =
            repository.createProject("Observability");

        repository.assignProject(alice, apiPlatform);
        repository.assignProject(alice, observability);

        repository.assignProject(bob, apiPlatform);
        repository.assignProject(bob, dataMigration);

        repository.assignProject(carol, dataMigration);
        repository.assignProject(carol, observability);

        System.out.println("Initial enterprise relationship state");
        printEmployee(repository, alice);
        printEmployee(repository, bob);
        printEmployee(repository, carol);

        System.out.println(
            "\nRemoving Alice's Observability association"
        );

        repository.removeProjectAssignment(
            alice,
            observability
        );

        printEmployee(repository, alice);

        System.out.println(
            "\nMoving Alice to Operations"
        );

        repository.moveEmployee(alice, operations);
        printEmployee(repository, alice);

        System.out.println(
            "\nTesting one-to-one constraint"
        );

        try {
            repository.createProfile(
                alice,
                "Platform Architect",
                "Bengaluru"
            );
        } catch (RelationshipException exception) {
            System.out.println(
                "Rejected: " + exception.getMessage()
            );
        }

        System.out.println(
            "\nDeleting Alice and cascading dependent relationships"
        );

        repository.deleteEmployee(alice);

        System.out.println(
            "Alice state: " + alice.state
        );

        System.out.println(
            "Alice profile: " + repository.profile(alice)
        );

        System.out.println(
            "Alice projects: " + repository.projectNames(alice)
        );

        System.out.println(
            "\nDeleting Operations department"
        );

        repository.deleteDepartment(operations);

        System.out.println(
            "Carol state after department cascade: "
            + carol.state
        );

        System.out.println(
            "Bob remains active: "
            + (bob.state == RelationshipState.ACTIVE)
        );

        /*
         * The Java model deliberately separates:
         * - cardinality: which entities may be related;
         * - association management: how links are created or removed;
         * - lifecycle: what dependent objects do when an owner disappears.
         *
         * This distinction is important when translating the domain into
         * SQLAlchemy relationship(), cascade, ForeignKey, and database
         * constraints.
         */
    }
}
