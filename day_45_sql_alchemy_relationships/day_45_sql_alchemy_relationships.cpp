#include <algorithm>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using EmployeeId = int;
using ProjectId = int;
using DepartmentId = int;
using ProfileId = int;

struct Profile {
    ProfileId id;
    EmployeeId employeeId;
    std::string jobTitle;
    std::string officeLocation;
};

struct Project {
    ProjectId id;
    std::string name;
    std::unordered_set<EmployeeId> employeeIds;
};

struct Employee {
    EmployeeId id;
    std::string name;
    std::string email;
    DepartmentId departmentId;

    // optional models the fact that an employee can have zero or one profile.
    std::optional<ProfileId> profileId;

    // A set represents a many-to-many association without duplicate links.
    std::unordered_set<ProjectId> projectIds;
};

struct Department {
    DepartmentId id;
    std::string name;
    std::unordered_set<EmployeeId> employeeIds;
};

/*
 * Technical case study:
 *
 * A government engineering organization maintains departments, employees,
 * employee profiles, and cross-functional projects. The repository must
 * preserve relationship invariants while supporting reassignment and
 * deletion.
 *
 * Relationship design:
 *   Department 1 ---- N Employee
 *   Employee   1 ---- 1 Profile
 *   Employee   N ---- N Project
 *
 * Cascading rules:
 *   deleting an employee deletes its profile and association links;
 *   deleting a department cascades to its employees;
 *   removing a project assignment does not delete the project.
 */
class Repository {
private:
    DepartmentId nextDepartmentId = 1;
    EmployeeId nextEmployeeId = 1;
    ProfileId nextProfileId = 1;
    ProjectId nextProjectId = 1;

    std::unordered_map<DepartmentId, Department> departments;
    std::unordered_map<EmployeeId, Employee> employees;
    std::unordered_map<ProfileId, Profile> profiles;
    std::unordered_map<ProjectId, Project> projects;

public:
    DepartmentId createDepartment(const std::string& name) {
        if (name.empty()) {
            throw std::invalid_argument("Department name cannot be empty.");
        }

        Department department{
            nextDepartmentId++,
            name,
            {}
        };

        const auto id = department.id;
        departments.emplace(id, department);
        return id;
    }

    EmployeeId createEmployee(
        const std::string& name,
        const std::string& email,
        DepartmentId departmentId
    ) {
        if (!departments.contains(departmentId)) {
            throw std::invalid_argument(
                "Employee references a nonexistent department."
            );
        }

        for (const auto& [id, employee] : employees) {
            if (employee.email == email) {
                throw std::invalid_argument(
                    "Employee email must be unique."
                );
            }
        }

        Employee employee{
            nextEmployeeId++,
            name,
            email,
            departmentId,
            std::nullopt,
            {}
        };

        const auto id = employee.id;
        employees.emplace(id, employee);
        departments.at(departmentId).employeeIds.insert(id);

        return id;
    }

    ProfileId createProfile(
        EmployeeId employeeId,
        const std::string& jobTitle,
        const std::string& officeLocation
    ) {
        auto employeeIt = employees.find(employeeId);

        if (employeeIt == employees.end()) {
            throw std::invalid_argument(
                "Cannot create a profile for an unknown employee."
            );
        }

        // This is the application-side representation of a UNIQUE
        // employee_id constraint in a relational one-to-one mapping.
        if (employeeIt->second.profileId.has_value()) {
            throw std::logic_error(
                "One-to-one constraint violated: profile already exists."
            );
        }

        Profile profile{
            nextProfileId++,
            employeeId,
            jobTitle,
            officeLocation
        };

        const auto id = profile.id;
        profiles.emplace(id, profile);
        employeeIt->second.profileId = id;

        return id;
    }

    ProjectId createProject(const std::string& name) {
        if (name.empty()) {
            throw std::invalid_argument("Project name cannot be empty.");
        }

        Project project{
            nextProjectId++,
            name,
            {}
        };

        const auto id = project.id;
        projects.emplace(id, project);
        return id;
    }

    void assignProject(EmployeeId employeeId, ProjectId projectId) {
        if (!employees.contains(employeeId)) {
            throw std::invalid_argument("Unknown employee.");
        }

        if (!projects.contains(projectId)) {
            throw std::invalid_argument("Unknown project.");
        }

        employees.at(employeeId).projectIds.insert(projectId);
        projects.at(projectId).employeeIds.insert(employeeId);
    }

    void removeProjectAssignment(
        EmployeeId employeeId,
        ProjectId projectId
    ) {
        if (!employees.contains(employeeId) ||
            !projects.contains(projectId)) {
            throw std::invalid_argument(
                "Employee and project must both exist."
            );
        }

        employees.at(employeeId).projectIds.erase(projectId);
        projects.at(projectId).employeeIds.erase(employeeId);
    }

    void moveEmployee(
        EmployeeId employeeId,
        DepartmentId destinationDepartmentId
    ) {
        if (!employees.contains(employeeId)) {
            throw std::invalid_argument("Unknown employee.");
        }

        if (!departments.contains(destinationDepartmentId)) {
            throw std::invalid_argument("Unknown destination department.");
        }

        auto& employee = employees.at(employeeId);

        departments.at(employee.departmentId)
            .employeeIds.erase(employeeId);

        departments.at(destinationDepartmentId)
            .employeeIds.insert(employeeId);

        employee.departmentId = destinationDepartmentId;
    }

    void deleteEmployee(EmployeeId employeeId) {
        auto employeeIt = employees.find(employeeId);

        if (employeeIt == employees.end()) {
            return;
        }

        Employee employee = employeeIt->second;

        departments.at(employee.departmentId)
            .employeeIds.erase(employeeId);

        // Cascade to the one-to-one dependent.
        if (employee.profileId.has_value()) {
            profiles.erase(*employee.profileId);
        }

        // Cascade only removes association rows. It does not delete projects.
        for (ProjectId projectId : employee.projectIds) {
            auto projectIt = projects.find(projectId);

            if (projectIt != projects.end()) {
                projectIt->second.employeeIds.erase(employeeId);
            }
        }

        employees.erase(employeeIt);
    }

    void deleteDepartment(DepartmentId departmentId) {
        auto departmentIt = departments.find(departmentId);

        if (departmentIt == departments.end()) {
            return;
        }

        // Copy IDs because deleteEmployee modifies the department's set.
        std::vector<EmployeeId> employeeIds(
            departmentIt->second.employeeIds.begin(),
            departmentIt->second.employeeIds.end()
        );

        for (EmployeeId employeeId : employeeIds) {
            deleteEmployee(employeeId);
        }

        departments.erase(departmentIt);
    }

    const Employee& employee(EmployeeId id) const {
        auto it = employees.find(id);

        if (it == employees.end()) {
            throw std::out_of_range("Employee not found.");
        }

        return it->second;
    }

    const Project& project(ProjectId id) const {
        auto it = projects.find(id);

        if (it == projects.end()) {
            throw std::out_of_range("Project not found.");
        }

        return it->second;
    }

    const Profile& profile(ProfileId id) const {
        auto it = profiles.find(id);

        if (it == profiles.end()) {
            throw std::out_of_range("Profile not found.");
        }

        return it->second;
    }

    const Department& department(DepartmentId id) const {
        auto it = departments.find(id);

        if (it == departments.end()) {
            throw std::out_of_range("Department not found.");
        }

        return it->second;
    }

    bool employeeExists(EmployeeId id) const {
        return employees.contains(id);
    }

    bool profileExists(ProfileId id) const {
        return profiles.contains(id);
    }

    void printEmployee(EmployeeId employeeId) const {
        const auto& employeeRecord = employee(employeeId);
        const auto& departmentRecord = department(
            employeeRecord.departmentId
        );

        std::cout << employeeRecord.name
                  << " | " << employeeRecord.email
                  << " | department=" << departmentRecord.name;

        if (employeeRecord.profileId.has_value()) {
            const auto& profileRecord = profile(
                *employeeRecord.profileId
            );

            std::cout
                << " | profile=" << profileRecord.jobTitle
                << " @ " << profileRecord.officeLocation;
        } else {
            std::cout << " | profile=<none>";
        }

        std::cout << " | projects=";

        for (ProjectId projectId : employeeRecord.projectIds) {
            std::cout << project(projectId).name << " ";
        }

        std::cout << '\n';
    }
};

int main() {
    try {
        Repository repository;

        const auto engineering =
            repository.createDepartment("Engineering");

        const auto operations =
            repository.createDepartment("Operations");

        const auto alice = repository.createEmployee(
            "Alice Sharma",
            "alice@example.com",
            engineering
        );

        const auto bob = repository.createEmployee(
            "Bob Mehta",
            "bob@example.com",
            engineering
        );

        const auto carol = repository.createEmployee(
            "Carol Singh",
            "carol@example.com",
            operations
        );

        const auto aliceProfile = repository.createProfile(
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

        const auto apiPlatform =
            repository.createProject("API Platform");

        const auto dataMigration =
            repository.createProject("Data Migration");

        const auto observability =
            repository.createProject("Observability");

        repository.assignProject(alice, apiPlatform);
        repository.assignProject(alice, observability);

        repository.assignProject(bob, apiPlatform);
        repository.assignProject(bob, dataMigration);

        repository.assignProject(carol, dataMigration);
        repository.assignProject(carol, observability);

        std::cout << "Initial relationship graph\n";
        repository.printEmployee(alice);
        repository.printEmployee(bob);
        repository.printEmployee(carol);

        std::cout << "\nRemoving Alice's Observability association\n";
        repository.removeProjectAssignment(alice, observability);
        repository.printEmployee(alice);

        std::cout << "\nMoving Alice to Operations\n";
        repository.moveEmployee(alice, operations);
        repository.printEmployee(alice);

        std::cout << "\nAttempting a second Alice profile\n";

        try {
            repository.createProfile(
                alice,
                "Platform Architect",
                "Bengaluru"
            );
        } catch (const std::exception& error) {
            std::cout << "Rejected: "
                      << error.what()
                      << '\n';
        }

        std::cout << "\nDeleting Alice\n";
        repository.deleteEmployee(alice);

        std::cout
            << "Alice exists: "
            << std::boolalpha
            << repository.employeeExists(alice)
            << '\n';

        std::cout
            << "Alice profile exists: "
            << repository.profileExists(aliceProfile)
            << '\n';

        std::cout << "\nDeleting Operations department\n";
        repository.deleteDepartment(operations);

        std::cout
            << "Carol exists after department cascade: "
            << repository.employeeExists(carol)
            << '\n';

        /*
         * Complexity notes:
         *
         * Relationship membership uses unordered_set, giving expected
         * constant-time insertion, lookup, and removal.
         *
         * Employee email validation scans employees and is O(n). A production
         * implementation would maintain a unique email index.
         *
         * Deleting a department traverses its employees, so its cost is
         * proportional to the number of employees owned by that department
         * plus their relationship links.
         */

    } catch (const std::exception& error) {
        std::cerr
            << "Fatal relationship error: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
