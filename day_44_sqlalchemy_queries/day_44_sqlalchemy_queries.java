import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

public class SqlAlchemyQueryConcepts {

    record Department(
        int id,
        String name
    ) {}

    record Employee(
        int id,
        String name,
        String email,
        BigDecimal salary,
        int departmentId
    ) {}

    record Project(
        int id,
        String name,
        BigDecimal budget,
        String status
    ) {}

    record EmployeeProject(
        int employeeId,
        int projectId
    ) {}

    record EmployeeDepartmentView(
        Employee employee,
        Department department
    ) {}

    record Page<T>(
        List<T> records,
        int page,
        int pageSize,
        int total,
        int totalPages
    ) {}

    enum SortField {
        NAME,
        SALARY
    }

    static final List<Department> DEPARTMENTS = List.of(
        new Department(1, "Engineering"),
        new Department(2, "Data Science"),
        new Department(3, "Security"),
        new Department(4, "Operations"),
        new Department(5, "Research")
    );

    static final List<Employee> EMPLOYEES = List.of(
        new Employee(
            1,
            "Aarav Sharma",
            "aarav@example.com",
            new BigDecimal("95000"),
            1
        ),
        new Employee(
            2,
            "Priya Nair",
            "priya@example.com",
            new BigDecimal("125000"),
            2
        ),
        new Employee(
            3,
            "Rohan Mehta",
            "rohan@example.com",
            new BigDecimal("110000"),
            3
        ),
        new Employee(
            4,
            "Ananya Singh",
            "ananya@example.com",
            new BigDecimal("88000"),
            4
        ),
        new Employee(
            5,
            "Vikram Rao",
            "vikram@example.com",
            new BigDecimal("135000"),
            5
        ),
        new Employee(
            6,
            "Neha Kapoor",
            "neha@example.com",
            new BigDecimal("102000"),
            1
        ),
        new Employee(
            7,
            "Kabir Verma",
            "kabir@example.com",
            new BigDecimal("76000"),
            4
        ),
        new Employee(
            8,
            "Isha Gupta",
            "isha@example.com",
            new BigDecimal("118000"),
            3
        )
    );

    static final List<Project> PROJECTS = List.of(
        new Project(
            1,
            "Cloud Migration",
            new BigDecimal("450000"),
            "active"
        ),
        new Project(
            2,
            "Threat Detection Platform",
            new BigDecimal("650000"),
            "active"
        ),
        new Project(
            3,
            "Data Quality Initiative",
            new BigDecimal("300000"),
            "completed"
        ),
        new Project(
            4,
            "Research Knowledge Graph",
            new BigDecimal("525000"),
            "active"
        )
    );

    static final List<EmployeeProject> EMPLOYEE_PROJECTS = List.of(
        new EmployeeProject(1, 1),
        new EmployeeProject(6, 1),
        new EmployeeProject(4, 1),
        new EmployeeProject(3, 2),
        new EmployeeProject(8, 2),
        new EmployeeProject(1, 2),
        new EmployeeProject(2, 3),
        new EmployeeProject(7, 3),
        new EmployeeProject(5, 4),
        new EmployeeProject(2, 4)
    );

    static void printEmployees(
        String title,
        List<Employee> employees
    ) {
        System.out.println("\n=== " + title + " ===");

        employees.forEach(employee ->
            System.out.printf(
                "%d | %s | %s | %s%n",
                employee.id(),
                employee.name(),
                employee.salary(),
                employee.email()
            )
        );
    }

    static List<Employee> filter(
        List<Employee> employees,
        java.util.function.Predicate<Employee> predicate
    ) {
        return employees.stream()
            .filter(predicate)
            .toList();
    }

    static List<EmployeeDepartmentView> innerJoinDepartments() {
        Map<Integer, Department> departmentsById =
            DEPARTMENTS.stream()
                .collect(Collectors.toMap(
                    Department::id,
                    Function.identity()
                ));

        return EMPLOYEES.stream()
            .filter(employee ->
                departmentsById.containsKey(
                    employee.departmentId()
                )
            )
            .map(employee ->
                new EmployeeDepartmentView(
                    employee,
                    departmentsById.get(
                        employee.departmentId()
                    )
                )
            )
            .toList();
    }

    static void demonstrateSelect() {
        printEmployees(
            "SELECT Employees",
            EMPLOYEES
        );
    }

    static void demonstrateFiltering() {
        List<Employee> result = filter(
            EMPLOYEES,
            employee ->
                employee.salary()
                    .compareTo(new BigDecimal("110000")) >= 0
        );

        printEmployees(
            "WHERE salary >= 110000",
            result
        );
    }

    static void demonstrateCombinedFiltering() {
        List<Employee> result = filter(
            EMPLOYEES,
            employee -> {
                boolean salaryMatches =
                    employee.salary()
                        .compareTo(new BigDecimal("90000")) >= 0 &&
                    employee.salary()
                        .compareTo(new BigDecimal("130000")) < 0;

                boolean departmentMatches =
                    employee.departmentId() == 1 ||
                    employee.departmentId() == 3;

                return salaryMatches &&
                       departmentMatches;
            }
        );

        printEmployees(
            "Combined Filtering",
            result
        );
    }

    static void demonstrateJoin() {
        List<EmployeeDepartmentView> result =
            innerJoinDepartments();

        System.out.println(
            "\n=== INNER JOIN Employees -> Departments ==="
        );

        result.forEach(row ->
            System.out.printf(
                "%s | %s%n",
                row.employee().name(),
                row.department().name()
            )
        );
    }

    static void demonstrateOrdering() {
        List<Employee> result =
            EMPLOYEES.stream()
                .sorted(
                    Comparator
                        .comparing(
                            Employee::salary
                        )
                        .reversed()
                        .thenComparing(Employee::name)
                )
                .toList();

        printEmployees(
            "ORDER BY salary DESC, name ASC",
            result
        );
    }

    static void demonstrateAggregation() {
        BigDecimal total =
            EMPLOYEES.stream()
                .map(Employee::salary)
                .reduce(
                    BigDecimal.ZERO,
                    BigDecimal::add
                );

        BigDecimal average =
            total.divide(
                BigDecimal.valueOf(EMPLOYEES.size()),
                2,
                RoundingMode.HALF_UP
            );

        BigDecimal minimum =
            EMPLOYEES.stream()
                .map(Employee::salary)
                .min(BigDecimal::compareTo)
                .orElse(BigDecimal.ZERO);

        BigDecimal maximum =
            EMPLOYEES.stream()
                .map(Employee::salary)
                .max(BigDecimal::compareTo)
                .orElse(BigDecimal.ZERO);

        System.out.println("\n=== Aggregation ===");
        System.out.println("COUNT = " + EMPLOYEES.size());
        System.out.println("SUM   = " + total);
        System.out.println("AVG   = " + average);
        System.out.println("MIN   = " + minimum);
        System.out.println("MAX   = " + maximum);
    }

    static void demonstrateGroupAggregation() {
        Map<Integer, List<Employee>> groups =
            EMPLOYEES.stream()
                .collect(Collectors.groupingBy(
                    Employee::departmentId
                ));

        Map<Integer, Department> departmentMap =
            DEPARTMENTS.stream()
                .collect(Collectors.toMap(
                    Department::id,
                    Function.identity()
                ));

        System.out.println(
            "\n=== GROUP BY Department ==="
        );

        groups.entrySet().stream()
            .sorted(
                Comparator.comparing(
                    entry ->
                        departmentMap
                            .get(entry.getKey())
                            .name()
                )
            )
            .forEach(entry -> {
                List<Employee> employees =
                    entry.getValue();

                BigDecimal total =
                    employees.stream()
                        .map(Employee::salary)
                        .reduce(
                            BigDecimal.ZERO,
                            BigDecimal::add
                        );

                BigDecimal average =
                    total.divide(
                        BigDecimal.valueOf(
                            employees.size()
                        ),
                        2,
                        RoundingMode.HALF_UP
                    );

                Department department =
                    departmentMap.get(entry.getKey());

                System.out.printf(
                    "%s | count=%d | avg=%s%n",
                    department.name(),
                    employees.size(),
                    average
                );
            });
    }

    static <T> Page<T> paginate(
        List<T> source,
        int page,
        int pageSize
    ) {
        if (page < 1) {
            throw new IllegalArgumentException(
                "page must be >= 1"
            );
        }

        if (pageSize < 1 || pageSize > 100) {
            throw new IllegalArgumentException(
                "pageSize must be between 1 and 100"
            );
        }

        int total = source.size();

        int totalPages =
            total == 0
                ? 0
                : (total + pageSize - 1) / pageSize;

        int start = (page - 1) * pageSize;

        if (start >= total) {
            return new Page<>(
                List.of(),
                page,
                pageSize,
                total,
                totalPages
            );
        }

        int end =
            Math.min(
                start + pageSize,
                total
            );

        return new Page<>(
            source.subList(start, end),
            page,
            pageSize,
            total,
            totalPages
        );
    }

    static void demonstratePagination() {
        List<Employee> ordered =
            EMPLOYEES.stream()
                .sorted(
                    Comparator.comparingInt(
                        Employee::id
                    )
                )
                .toList();

        Page<Employee> page =
            paginate(ordered, 2, 3);

        printEmployees(
            "Page " + page.page(),
            page.records()
        );

        System.out.printf(
            "total=%d, pageSize=%d, totalPages=%d%n",
            page.total(),
            page.pageSize(),
            page.totalPages()
        );
    }

    static void demonstrateExists() {
        Set<Integer> activeProjectIds =
            PROJECTS.stream()
                .filter(project ->
                    project.status().equals("active")
                )
                .map(Project::id)
                .collect(Collectors.toSet());

        List<Employee> result =
            EMPLOYEES.stream()
                .filter(employee ->
                    EMPLOYEE_PROJECTS.stream()
                        .anyMatch(assignment ->
                            assignment.employeeId() ==
                                employee.id() &&
                            activeProjectIds.contains(
                                assignment.projectId()
                            )
                        )
                )
                .toList();

        printEmployees(
            "Employees with Active Projects",
            result
        );
    }

    static void demonstrateAboveAverage() {
        BigDecimal total =
            EMPLOYEES.stream()
                .map(Employee::salary)
                .reduce(
                    BigDecimal.ZERO,
                    BigDecimal::add
                );

        BigDecimal average =
            total.divide(
                BigDecimal.valueOf(
                    EMPLOYEES.size()
                ),
                2,
                RoundingMode.HALF_UP
            );

        List<Employee> result =
            EMPLOYEES.stream()
                .filter(employee ->
                    employee.salary()
                        .compareTo(average) > 0
                )
                .sorted(
                    Comparator
                        .comparing(Employee::salary)
                        .reversed()
                )
                .toList();

        printEmployees(
            "Employees Above Average",
            result
        );
    }

    static void demonstrateDynamicQuery(
        String departmentName,
        BigDecimal minimumSalary,
        SortField sortField
    ) {
        Map<String, Department> departmentMap =
            DEPARTMENTS.stream()
                .collect(Collectors.toMap(
                    Department::name,
                    Function.identity()
                ));

        List<Employee> result =
            EMPLOYEES.stream()
                .filter(employee -> {
                    if (departmentName == null) {
                        return true;
                    }

                    Department department =
                        departmentMap.get(
                            departmentName
                        );

                    return department != null &&
                        employee.departmentId() ==
                            department.id();
                })
                .filter(employee ->
                    minimumSalary == null ||
                    employee.salary()
                        .compareTo(minimumSalary) >= 0
                )
                .sorted(
                    sortField == SortField.SALARY
                        ? Comparator
                            .comparing(
                                Employee::salary
                            )
                            .reversed()
                        : Comparator.comparing(
                            Employee::name
                        )
                )
                .toList();

        printEmployees(
            "Dynamic Query",
            result
        );
    }

    static void demonstrateValidationFailure() {
        try {
            paginate(EMPLOYEES, 0, 10);
        } catch (IllegalArgumentException exception) {
            System.out.println(
                "\n=== Pagination Validation ==="
            );
            System.out.println(
                exception.getMessage()
            );
        }
    }

    public static void main(String[] args) {
        demonstrateSelect();
        demonstrateFiltering();
        demonstrateCombinedFiltering();
        demonstrateJoin();
        demonstrateOrdering();
        demonstrateAggregation();
        demonstrateGroupAggregation();
        demonstratePagination();
        demonstrateExists();
        demonstrateAboveAverage();

        demonstrateDynamicQuery(
            "Security",
            new BigDecimal("100000"),
            SortField.SALARY
        );

        demonstrateValidationFailure();
    }
}
