#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Department {
    int id;
    std::string name;
};

struct Employee {
    int id;
    std::string name;
    std::string email;
    double salary;
    int departmentId;
};

struct Project {
    int id;
    std::string name;
    double budget;
    std::string status;
};

struct EmployeeProject {
    int employeeId;
    int projectId;
};

struct EmployeeDepartmentRow {
    Employee employee;
    Department department;
};

struct ProjectEmployeeRow {
    Project project;
    Employee employee;
};

class RepositoryGovernanceQueryEngine {
private:
    std::vector<Department> departments_;
    std::vector<Employee> employees_;
    std::vector<Project> projects_;
    std::vector<EmployeeProject> assignments_;

public:
    RepositoryGovernanceQueryEngine() {
        seed();
    }

    void seed() {
        departments_ = {
            {1, "Engineering"},
            {2, "Data Science"},
            {3, "Security"},
            {4, "Operations"},
            {5, "Research"}
        };

        employees_ = {
            {1, "Aarav Sharma", "aarav@example.com", 95000, 1},
            {2, "Priya Nair", "priya@example.com", 125000, 2},
            {3, "Rohan Mehta", "rohan@example.com", 110000, 3},
            {4, "Ananya Singh", "ananya@example.com", 88000, 4},
            {5, "Vikram Rao", "vikram@example.com", 135000, 5},
            {6, "Neha Kapoor", "neha@example.com", 102000, 1},
            {7, "Kabir Verma", "kabir@example.com", 76000, 4},
            {8, "Isha Gupta", "isha@example.com", 118000, 3}
        };

        projects_ = {
            {1, "Cloud Migration", 450000, "active"},
            {2, "Threat Detection Platform", 650000, "active"},
            {3, "Data Quality Initiative", 300000, "completed"},
            {4, "Research Knowledge Graph", 525000, "active"}
        };

        assignments_ = {
            {1, 1},
            {6, 1},
            {4, 1},
            {3, 2},
            {8, 2},
            {1, 2},
            {2, 3},
            {7, 3},
            {5, 4},
            {2, 4}
        };
    }

    const Department* findDepartment(int id) const {
        for (const auto& department : departments_) {
            if (department.id == id) {
                return &department;
            }
        }

        return nullptr;
    }

    const Project* findProject(int id) const {
        for (const auto& project : projects_) {
            if (project.id == id) {
                return &project;
            }
        }

        return nullptr;
    }

    /*
     * This method models SELECT with a projection. It does not return entire
     * employee records because the caller only needs selected fields.
     */
    void selectEmployees() const {
        std::cout << "\n=== SELECT Employees ===\n";

        for (const auto& employee : employees_) {
            std::cout
                << employee.id << " | "
                << employee.name << " | "
                << employee.salary << '\n';
        }
    }

    /*
     * WHERE conditions are represented as a predicate. The same idea maps to
     * SQLAlchemy's Select.where() expressions.
     */
    std::vector<Employee> filterSalary(double minimum) const {
        std::vector<Employee> result;

        std::copy_if(
            employees_.begin(),
            employees_.end(),
            std::back_inserter(result),
            [minimum](const Employee& employee) {
                return employee.salary >= minimum;
            }
        );

        return result;
    }

    void demonstrateFiltering() const {
        const auto result = filterSalary(110000);

        std::cout << "\n=== WHERE salary >= 110000 ===\n";

        for (const auto& employee : result) {
            std::cout
                << employee.name
                << " | salary=" << employee.salary
                << '\n';
        }
    }

    /*
     * An indexed lookup is represented explicitly with an unordered_map.
     * In a real SQL database, the database engine would normally maintain the
     * physical index rather than application code.
     */
    std::unordered_map<int, Department> buildDepartmentIndex() const {
        std::unordered_map<int, Department> index;

        for (const auto& department : departments_) {
            index.emplace(department.id, department);
        }

        return index;
    }

    std::vector<EmployeeDepartmentRow> innerJoinEmployeesDepartments() const {
        const auto departmentIndex = buildDepartmentIndex();
        std::vector<EmployeeDepartmentRow> result;

        for (const auto& employee : employees_) {
            auto iterator = departmentIndex.find(employee.departmentId);

            if (iterator != departmentIndex.end()) {
                result.push_back({
                    employee,
                    iterator->second
                });
            }
        }

        return result;
    }

    void demonstrateJoin() const {
        const auto result = innerJoinEmployeesDepartments();

        std::cout << "\n=== INNER JOIN Employees -> Departments ===\n";

        for (const auto& row : result) {
            std::cout
                << row.employee.name
                << " | "
                << row.department.name
                << '\n';
        }
    }

    std::vector<ProjectEmployeeRow> projectEmployeeJoin() const {
        std::unordered_map<int, Employee> employeeIndex;

        for (const auto& employee : employees_) {
            employeeIndex.emplace(employee.id, employee);
        }

        std::vector<ProjectEmployeeRow> result;

        for (const auto& assignment : assignments_) {
            const Project* project = findProject(assignment.projectId);

            auto employeeIterator =
                employeeIndex.find(assignment.employeeId);

            if (project != nullptr &&
                employeeIterator != employeeIndex.end()) {
                result.push_back({
                    *project,
                    employeeIterator->second
                });
            }
        }

        return result;
    }

    void demonstrateManyToManyJoin() const {
        const auto result = projectEmployeeJoin();

        std::cout << "\n=== Project <-> Employee Join ===\n";

        for (const auto& row : result) {
            std::cout
                << row.project.name
                << " | "
                << row.employee.name
                << '\n';
        }
    }

    void demonstrateOrdering() const {
        std::vector<Employee> result = employees_;

        std::sort(
            result.begin(),
            result.end(),
            [](const Employee& left, const Employee& right) {
                if (left.salary != right.salary) {
                    return left.salary > right.salary;
                }

                return left.name < right.name;
            }
        );

        std::cout << "\n=== ORDER BY salary DESC, name ASC ===\n";

        for (const auto& employee : result) {
            std::cout
                << std::fixed
                << std::setprecision(2)
                << employee.name
                << " | "
                << employee.salary
                << '\n';
        }
    }

    struct DepartmentAggregate {
        int employeeCount = 0;
        double totalSalary = 0.0;
        double minimumSalary = 0.0;
        double maximumSalary = 0.0;
    };

    void demonstrateAggregation() const {
        std::map<int, DepartmentAggregate> aggregates;

        for (const auto& employee : employees_) {
            auto& aggregate = aggregates[employee.departmentId];

            aggregate.employeeCount++;
            aggregate.totalSalary += employee.salary;

            if (aggregate.employeeCount == 1) {
                aggregate.minimumSalary = employee.salary;
                aggregate.maximumSalary = employee.salary;
            } else {
                aggregate.minimumSalary =
                    std::min(
                        aggregate.minimumSalary,
                        employee.salary
                    );

                aggregate.maximumSalary =
                    std::max(
                        aggregate.maximumSalary,
                        employee.salary
                    );
            }
        }

        std::cout << "\n=== GROUP BY Department ===\n";

        for (const auto& [departmentId, aggregate] : aggregates) {
            const Department* department =
                findDepartment(departmentId);

            if (department == nullptr) {
                continue;
            }

            double averageSalary =
                aggregate.totalSalary /
                aggregate.employeeCount;

            std::cout
                << department->name
                << " | count=" << aggregate.employeeCount
                << " | avg=" << averageSalary
                << " | min=" << aggregate.minimumSalary
                << " | max=" << aggregate.maximumSalary
                << '\n';
        }
    }

    std::vector<Employee> paginate(
        std::vector<Employee> rows,
        int page,
        int pageSize
    ) const {
        if (page < 1) {
            throw std::invalid_argument(
                "page must be at least 1"
            );
        }

        if (pageSize < 1 || pageSize > 100) {
            throw std::invalid_argument(
                "pageSize must be between 1 and 100"
            );
        }

        const std::size_t start =
            static_cast<std::size_t>((page - 1) * pageSize);

        if (start >= rows.size()) {
            return {};
        }

        const std::size_t end =
            std::min(
                start + static_cast<std::size_t>(pageSize),
                rows.size()
            );

        return std::vector<Employee>(
            rows.begin() + static_cast<long>(start),
            rows.begin() + static_cast<long>(end)
        );
    }

    void demonstratePagination() const {
        std::vector<Employee> ordered = employees_;

        std::sort(
            ordered.begin(),
            ordered.end(),
            [](const Employee& left, const Employee& right) {
                return left.id < right.id;
            }
        );

        const auto page = paginate(ordered, 2, 3);

        std::cout << "\n=== Page 2, Size 3 ===\n";

        for (const auto& employee : page) {
            std::cout
                << employee.id
                << " | "
                << employee.name
                << '\n';
        }

        const int total =
            static_cast<int>(ordered.size());

        const int pageSize = 3;

        const int totalPages =
            (total + pageSize - 1) / pageSize;

        std::cout
            << "total=" << total
            << ", totalPages=" << totalPages
            << '\n';
    }

    void demonstrateAboveAverage() const {
        const double totalSalary =
            std::accumulate(
                employees_.begin(),
                employees_.end(),
                0.0,
                [](double total, const Employee& employee) {
                    return total + employee.salary;
                }
            );

        const double average =
            totalSalary / employees_.size();

        std::cout << "\n=== Salary Above Average ===\n";
        std::cout << "Average salary: " << average << '\n';

        for (const auto& employee : employees_) {
            if (employee.salary > average) {
                std::cout
                    << employee.name
                    << " | "
                    << employee.salary
                    << '\n';
            }
        }
    }

    void demonstrateActiveProjectExists() const {
        std::set<int> activeProjectIds;

        for (const auto& project : projects_) {
            if (project.status == "active") {
                activeProjectIds.insert(project.id);
            }
        }

        std::cout
            << "\n=== Employees with an Active Project ===\n";

        for (const auto& employee : employees_) {
            bool exists = false;

            for (const auto& assignment : assignments_) {
                if (assignment.employeeId == employee.id &&
                    activeProjectIds.contains(
                        assignment.projectId
                    )) {
                    exists = true;
                    break;
                }
            }

            if (exists) {
                std::cout << employee.name << '\n';
            }
        }
    }

    void demonstrateComplexQuery() const {
        /*
         * This case study combines JOIN, WHERE, projection, ORDER BY and
         * pagination. It resembles an API endpoint that lists highly paid
         * employees while showing their department.
         */
        auto joined = innerJoinEmployeesDepartments();

        joined.erase(
            std::remove_if(
                joined.begin(),
                joined.end(),
                [](const EmployeeDepartmentRow& row) {
                    return row.employee.salary < 90000 ||
                           row.department.name == "Operations";
                }
            ),
            joined.end()
        );

        std::sort(
            joined.begin(),
            joined.end(),
            [](const EmployeeDepartmentRow& left,
               const EmployeeDepartmentRow& right) {
                if (left.employee.salary !=
                    right.employee.salary) {
                    return left.employee.salary >
                           right.employee.salary;
                }

                return left.employee.name <
                       right.employee.name;
            }
        );

        const int page = 1;
        const int pageSize = 4;

        const std::size_t start =
            static_cast<std::size_t>(
                (page - 1) * pageSize
            );

        const std::size_t end =
            std::min(
                start + static_cast<std::size_t>(pageSize),
                joined.size()
            );

        std::cout
            << "\n=== Complex Query Result ===\n";

        for (std::size_t index = start; index < end; ++index) {
            const auto& row = joined[index];

            std::cout
                << row.employee.name
                << " | "
                << row.department.name
                << " | "
                << row.employee.salary
                << '\n';
        }
    }
};

int main() {
    try {
        RepositoryGovernanceQueryEngine engine;

        engine.selectEmployees();
        engine.demonstrateFiltering();
        engine.demonstrateJoin();
        engine.demonstrateManyToManyJoin();
        engine.demonstrateOrdering();
        engine.demonstrateAggregation();
        engine.demonstratePagination();
        engine.demonstrateAboveAverage();
        engine.demonstrateActiveProjectExists();
        engine.demonstrateComplexQuery();
    } catch (const std::exception& exception) {
        std::cerr
            << "Query processing failed: "
            << exception.what()
            << '\n';

        return 1;
    }

    return 0;
}
