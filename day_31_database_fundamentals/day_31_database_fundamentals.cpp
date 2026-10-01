/*
 * Database Fundamentals: relational model case study
 *
 * Scenario:
 * A project-management service stores projects, tasks, team members, and
 * project memberships. The program models the database layer with C++17
 * standard-library containers and enforces relational rules explicitly.
 *
 * The case study demonstrates:
 *   - tables as structured collections
 *   - rows as individual records
 *   - columns as typed attributes
 *   - primary keys
 *   - foreign keys
 *   - one-to-many relationships
 *   - many-to-many relationships through an associative table
 *   - composite keys
 *   - validation and constraints
 *   - indexed lookup
 *   - joins and aggregation
 *   - transaction-style rollback
 *   - referential-integrity failures
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic database_fundamentals.cpp -o database_fundamentals
 *
 * Run:
 *   ./database_fundamentals
 */

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

struct Project {
    int id{};
    std::string name;
    std::string owner;
};

struct Task {
    int id{};
    int projectId{};
    std::string title;
    std::string status;
    std::string dueDate;
};

struct Member {
    int id{};
    std::string name;
};

struct ProjectMember {
    int projectId{};
    int memberId{};
    std::string role;
};

class Database {
private:
    /*
     * These vectors represent logical tables. Each object is a row, and each
     * member of the object is a column.
     */
    std::vector<Project> projects_;
    std::vector<Task> tasks_;
    std::vector<Member> members_;
    std::vector<ProjectMember> projectMembers_;

    /*
     * These sets model indexes. An actual database engine stores index
     * structures in optimized on-disk representations; this case study uses
     * hash sets to demonstrate the same lookup principle.
     */
    std::unordered_map<int, std::unordered_set<int>> taskIdsByProject_;

    int nextProjectId_ = 1;
    int nextTaskId_ = 1;
    int nextMemberId_ = 1;

    static bool isValidStatus(const std::string& status) {
        return status == "todo" ||
               status == "in_progress" ||
               status == "done";
    }

    bool projectNameExists(const std::string& name) const {
        return std::any_of(
            projects_.begin(),
            projects_.end(),
            [&](const Project& project) {
                return project.name == name;
            }
        );
    }

    bool memberNameExists(const std::string& name) const {
        return std::any_of(
            members_.begin(),
            members_.end(),
            [&](const Member& member) {
                return member.name == name;
            }
        );
    }

    bool hasProject(int projectId) const {
        return std::any_of(
            projects_.begin(),
            projects_.end(),
            [projectId](const Project& project) {
                return project.id == projectId;
            }
        );
    }

    bool hasMember(int memberId) const {
        return std::any_of(
            members_.begin(),
            members_.end(),
            [memberId](const Member& member) {
                return member.id == memberId;
            }
        );
    }

    bool hasTask(int taskId) const {
        return std::any_of(
            tasks_.begin(),
            tasks_.end(),
            [taskId](const Task& task) {
                return task.id == taskId;
            }
        );
    }

    bool membershipExists(int projectId, int memberId) const {
        return std::any_of(
            projectMembers_.begin(),
            projectMembers_.end(),
            [&](const ProjectMember& membership) {
                return membership.projectId == projectId &&
                       membership.memberId == memberId;
            }
        );
    }

public:
    int addProject(const std::string& name, const std::string& owner) {
        if (name.empty()) {
            throw std::invalid_argument("project name cannot be empty");
        }

        if (owner.empty()) {
            throw std::invalid_argument("project owner cannot be empty");
        }

        // This models a UNIQUE constraint on the project name.
        if (projectNameExists(name)) {
            throw std::runtime_error("duplicate project name rejected");
        }

        Project project{
            nextProjectId_++,
            name,
            owner
        };

        projects_.push_back(project);
        return project.id;
    }

    int addTask(
        int projectId,
        const std::string& title,
        const std::string& status,
        const std::string& dueDate
    ) {
        if (!hasProject(projectId)) {
            // This is the application-level equivalent of a foreign-key check.
            throw std::runtime_error("foreign key violation: project does not exist");
        }

        if (title.empty()) {
            throw std::invalid_argument("task title cannot be empty");
        }

        if (!isValidStatus(status)) {
            throw std::invalid_argument("invalid task status");
        }

        Task task{
            nextTaskId_++,
            projectId,
            title,
            status,
            dueDate
        };

        tasks_.push_back(task);

        // Maintain the project -> task index whenever a task is inserted.
        taskIdsByProject_[projectId].insert(task.id);

        return task.id;
    }

    int addMember(const std::string& name) {
        if (name.empty()) {
            throw std::invalid_argument("member name cannot be empty");
        }

        if (memberNameExists(name)) {
            throw std::runtime_error("duplicate member name rejected");
        }

        Member member{
            nextMemberId_++,
            name
        };

        members_.push_back(member);
        return member.id;
    }

    void addProjectMember(
        int projectId,
        int memberId,
        const std::string& role
    ) {
        if (!hasProject(projectId)) {
            throw std::runtime_error("membership references missing project");
        }

        if (!hasMember(memberId)) {
            throw std::runtime_error("membership references missing member");
        }

        if (role.empty()) {
            throw std::invalid_argument("membership role cannot be empty");
        }

        /*
         * projectId + memberId form a composite primary key. This prevents
         * the same person from being associated with the same project twice.
         */
        if (membershipExists(projectId, memberId)) {
            throw std::runtime_error("duplicate composite key rejected");
        }

        projectMembers_.push_back({
            projectId,
            memberId,
            role
        });
    }

    void updateTaskStatus(int taskId, const std::string& newStatus) {
        if (!isValidStatus(newStatus)) {
            throw std::invalid_argument("invalid task status");
        }

        for (Task& task : tasks_) {
            if (task.id == taskId) {
                task.status = newStatus;
                return;
            }
        }

        throw std::runtime_error("task does not exist");
    }

    void printProjects() const {
        std::cout << "\nPROJECTS TABLE\n";
        std::cout << std::left
                  << std::setw(8) << "ID"
                  << std::setw(24) << "NAME"
                  << "OWNER\n";
        std::cout << std::string(55, '-') << '\n';

        for (const Project& project : projects_) {
            std::cout << std::left
                      << std::setw(8) << project.id
                      << std::setw(24) << project.name
                      << project.owner << '\n';
        }
    }

    void printTasks() const {
        std::cout << "\nTASKS TABLE\n";
        std::cout << std::left
                  << std::setw(8) << "ID"
                  << std::setw(12) << "PROJECT"
                  << std::setw(34) << "TITLE"
                  << std::setw(15) << "STATUS"
                  << "DUE DATE\n";
        std::cout << std::string(90, '-') << '\n';

        for (const Task& task : tasks_) {
            std::cout << std::left
                      << std::setw(8) << task.id
                      << std::setw(12) << task.projectId
                      << std::setw(34) << task.title
                      << std::setw(15) << task.status
                      << task.dueDate << '\n';
        }
    }

    void printOneToManyJoin() const {
        /*
         * This is a relational JOIN performed manually. For each project,
         * matching task rows are found by the foreign-key value.
         */
        std::cout << "\nPROJECT -> TASK JOIN\n";
        std::cout << std::left
                  << std::setw(24) << "PROJECT"
                  << std::setw(8) << "TASK ID"
                  << std::setw(34) << "TASK"
                  << "STATUS\n";
        std::cout << std::string(82, '-') << '\n';

        for (const Project& project : projects_) {
            bool matched = false;

            for (const Task& task : tasks_) {
                if (task.projectId == project.id) {
                    matched = true;
                    std::cout << std::left
                              << std::setw(24) << project.name
                              << std::setw(8) << task.id
                              << std::setw(34) << task.title
                              << task.status << '\n';
                }
            }

            /*
             * A LEFT JOIN retains the parent row when no child row exists.
             */
            if (!matched) {
                std::cout << std::left
                          << std::setw(24) << project.name
                          << std::setw(8) << "-"
                          << std::setw(34) << "(no tasks)"
                          << "-" << '\n';
            }
        }
    }

    void printManyToManyJoin() const {
        /*
         * A many-to-many relationship cannot be represented cleanly by
         * putting a single member_id column into projects. The associative
         * projectMembers_ table resolves that relationship.
         */
        std::cout << "\nPROJECT -> MEMBER MANY-TO-MANY JOIN\n";
        std::cout << std::left
                  << std::setw(24) << "PROJECT"
                  << std::setw(16) << "MEMBER"
                  << "ROLE\n";
        std::cout << std::string(60, '-') << '\n';

        for (const ProjectMember& membership : projectMembers_) {
            const auto projectIt = std::find_if(
                projects_.begin(),
                projects_.end(),
                [&](const Project& project) {
                    return project.id == membership.projectId;
                }
            );

            const auto memberIt = std::find_if(
                members_.begin(),
                members_.end(),
                [&](const Member& member) {
                    return member.id == membership.memberId;
                }
            );

            if (projectIt != projects_.end() && memberIt != members_.end()) {
                std::cout << std::left
                          << std::setw(24) << projectIt->name
                          << std::setw(16) << memberIt->name
                          << membership.role << '\n';
            }
        }
    }

    void printIndexedLookup(int projectId) const {
        /*
         * Instead of scanning every task, the index first identifies task IDs
         * belonging to the project. This models the purpose of an index.
         */
        std::cout << "\nINDEXED TASK LOOKUP FOR PROJECT "
                  << projectId << '\n';

        const auto indexIt = taskIdsByProject_.find(projectId);

        if (indexIt == taskIdsByProject_.end()) {
            std::cout << "No indexed task IDs found.\n";
            return;
        }

        for (int taskId : indexIt->second) {
            const auto taskIt = std::find_if(
                tasks_.begin(),
                tasks_.end(),
                [taskId](const Task& task) {
                    return task.id == taskId;
                }
            );

            if (taskIt != tasks_.end()) {
                std::cout << taskIt->id
                          << " | "
                          << taskIt->title
                          << " | "
                          << taskIt->status
                          << '\n';
            }
        }
    }

    void printProjectStatistics() const {
        /*
         * This is equivalent to GROUP BY project_id with conditional counts.
         */
        std::cout << "\nPROJECT TASK STATISTICS\n";

        for (const Project& project : projects_) {
            int total = 0;
            int done = 0;
            int inProgress = 0;
            int todo = 0;

            for (const Task& task : tasks_) {
                if (task.projectId != project.id) {
                    continue;
                }

                ++total;

                if (task.status == "done") {
                    ++done;
                } else if (task.status == "in_progress") {
                    ++inProgress;
                } else {
                    ++todo;
                }
            }

            const double completion =
                total == 0
                    ? 0.0
                    : (static_cast<double>(done) / total) * 100.0;

            std::cout << project.name
                      << ": total=" << total
                      << ", done=" << done
                      << ", in_progress=" << inProgress
                      << ", todo=" << todo
                      << ", completion=" << std::fixed
                      << std::setprecision(1)
                      << completion << "%\n";
        }
    }

    void removeProject(int projectId) {
        /*
         * ON DELETE RESTRICT behavior: a parent cannot be deleted while child
         * rows still reference it. This protects referential integrity.
         */
        const auto hasChildren = std::any_of(
            tasks_.begin(),
            tasks_.end(),
            [projectId](const Task& task) {
                return task.projectId == projectId;
            }
        );

        if (hasChildren) {
            throw std::runtime_error(
                "delete restricted: project still has related tasks"
            );
        }

        const auto oldSize = projects_.size();

        projects_.erase(
            std::remove_if(
                projects_.begin(),
                projects_.end(),
                [projectId](const Project& project) {
                    return project.id == projectId;
                }
            ),
            projects_.end()
        );

        if (projects_.size() == oldSize) {
            throw std::runtime_error("project does not exist");
        }
    }

    void validateIntegrity() const {
        /*
         * A database integrity check verifies that every relationship points
         * to a valid parent and that every indexed task exists in the table.
         */
        for (const Task& task : tasks_) {
            if (!hasProject(task.projectId)) {
                throw std::runtime_error(
                    "integrity failure: orphan task detected"
                );
            }
        }

        for (const ProjectMember& membership : projectMembers_) {
            if (!hasProject(membership.projectId)) {
                throw std::runtime_error(
                    "integrity failure: membership has invalid project"
                );
            }

            if (!hasMember(membership.memberId)) {
                throw std::runtime_error(
                    "integrity failure: membership has invalid member"
                );
            }
        }

        for (const auto& [projectId, taskIds] : taskIdsByProject_) {
            if (!hasProject(projectId)) {
                throw std::runtime_error(
                    "integrity failure: index points to missing project"
                );
            }

            for (int taskId : taskIds) {
                if (!hasTask(taskId)) {
                    throw std::runtime_error(
                        "integrity failure: index points to missing task"
                    );
                }
            }
        }
    }

    /*
     * A real database transaction is handled by the database engine. For this
     * educational model, a snapshot is used to provide atomic behavior.
     */
    template <typename Operation>
    void transaction(Operation operation) {
        const auto projectsBackup = projects_;
        const auto tasksBackup = tasks_;
        const auto membersBackup = members_;
        const auto membershipsBackup = projectMembers_;
        const auto indexBackup = taskIdsByProject_;
        const int nextProjectBackup = nextProjectId_;
        const int nextTaskBackup = nextTaskId_;
        const int nextMemberBackup = nextMemberId_;

        try {
            operation();
        } catch (...) {
            projects_ = projectsBackup;
            tasks_ = tasksBackup;
            members_ = membersBackup;
            projectMembers_ = membershipsBackup;
            taskIdsByProject_ = indexBackup;
            nextProjectId_ = nextProjectBackup;
            nextTaskId_ = nextTaskBackup;
            nextMemberId_ = nextMemberBackup;
            throw;
        }
    }

    std::size_t projectCount() const {
        return projects_.size();
    }

    std::size_t taskCount() const {
        return tasks_.size();
    }
};

void printSection(const std::string& title) {
    std::cout << "\n"
              << std::string(72, '=')
              << "\n"
              << title
              << "\n"
              << std::string(72, '=')
              << "\n";
}

int main() {
    try {
        printSection("Database Fundamentals: Repository Project Case Study");

        Database db;

        printSection("Creating parent and child rows");

        const int marketProject =
            db.addProject("Market Analytics", "Atul");

        const int assetProject =
            db.addProject("Asset Tracking", "Priya");

        const int researchProject =
            db.addProject("Research Portal", "Rahul");

        db.addTask(
            marketProject,
            "Design relational schema",
            "done",
            "2026-10-03"
        );

        db.addTask(
            marketProject,
            "Build portfolio data model",
            "in_progress",
            "2026-10-08"
        );

        db.addTask(
            assetProject,
            "Register tracked assets",
            "done",
            "2026-10-04"
        );

        db.addTask(
            assetProject,
            "Store movement history",
            "in_progress",
            "2026-10-11"
        );

        db.addTask(
            researchProject,
            "Import research records",
            "todo",
            "2026-10-15"
        );

        db.printProjects();
        db.printTasks();

        printSection("One-to-many relationship");
        db.printOneToManyJoin();

        printSection("Many-to-many relationship");

        const int atul = db.addMember("Atul");
        const int priya = db.addMember("Priya");
        const int rahul = db.addMember("Rahul");

        db.addProjectMember(marketProject, atul, "Product Owner");
        db.addProjectMember(marketProject, priya, "Data Engineer");
        db.addProjectMember(assetProject, atul, "System Designer");
        db.addProjectMember(assetProject, priya, "Operations");
        db.addProjectMember(researchProject, atul, "Research Lead");
        db.addProjectMember(researchProject, rahul, "Analyst");

        db.printManyToManyJoin();

        printSection("Primary-key and foreign-key validation");

        try {
            db.addTask(
                9999,
                "Orphan task",
                "todo",
                "2026-10-30"
            );
        } catch (const std::exception& error) {
            std::cout << "Foreign-key failure: "
                      << error.what()
                      << '\n';
        }

        try {
            db.addProject("Market Analytics", "Another Owner");
        } catch (const std::exception& error) {
            std::cout << "Unique-key failure: "
                      << error.what()
                      << '\n';
        }

        try {
            db.addProjectMember(marketProject, atul, "Duplicate Role");
        } catch (const std::exception& error) {
            std::cout << "Composite-key failure: "
                      << error.what()
                      << '\n';
        }

        printSection("Indexed lookup");
        db.printIndexedLookup(marketProject);

        printSection("Update through a validated operation");

        db.updateTaskStatus(2, "done");
        db.printTasks();

        try {
            db.updateTaskStatus(2, "invalid_status");
        } catch (const std::exception& error) {
            std::cout << "CHECK-style failure: "
                      << error.what()
                      << '\n';
        }

        printSection("Aggregation across related rows");
        db.printProjectStatistics();

        printSection("Delete behavior");

        try {
            db.removeProject(marketProject);
        } catch (const std::exception& error) {
            std::cout << "Referential-integrity protection: "
                      << error.what()
                      << '\n';
        }

        printSection("Transaction rollback");

        const std::size_t projectsBefore = db.projectCount();
        const std::size_t tasksBefore = db.taskCount();

        try {
            db.transaction([&]() {
                const int temporaryProject =
                    db.addProject("Temporary Migration", "Migration Service");

                /*
                 * The second operation fails. The transaction restores the
                 * project that was successfully inserted immediately before it.
                 */
                db.addTask(
                    999999,
                    "This row must not survive",
                    "todo",
                    "2026-11-01"
                );

                // This line cannot execute because the previous operation fails.
                db.updateTaskStatus(temporaryProject, "done");
            });
        } catch (const std::exception& error) {
            std::cout << "Transaction aborted: "
                      << error.what()
                      << '\n';
        }

        std::cout << "Projects before transaction: "
                  << projectsBefore
                  << "\nProjects after rollback:  "
                  << db.projectCount()
                  << "\nTasks before transaction:    "
                  << tasksBefore
                  << "\nTasks after rollback:         "
                  << db.taskCount()
                  << '\n';

        printSection("Empty parent and LEFT JOIN behavior");

        const int emptyProject =
            db.addProject("Empty Project", "Operations");

        db.printOneToManyJoin();

        try {
            db.addProjectMember(emptyProject, 9999, "Unknown");
        } catch (const std::exception& error) {
            std::cout << "Invalid membership rejected: "
                      << error.what()
                      << '\n';
        }

        printSection("Integrity validation");

        db.validateIntegrity();
        std::cout << "All modeled foreign-key and index relationships are valid.\n";

        printSection("Design observations");
        std::cout
            << "Projects and tasks are separate tables because one project can "
               "have many tasks.\n"
            << "The task row stores projectId rather than duplicating project "
               "name and owner.\n"
            << "Project membership uses an associative table because both "
               "projects and members can have many counterparts.\n"
            << "Primary keys provide row identity; foreign keys preserve "
               "relationships between tables.\n"
            << "Indexes improve repeated lookup patterns but require extra "
               "maintenance when rows are inserted, updated, or deleted.\n"
            << "Transactions protect multi-step changes from partial failure.\n";

        printSection("Case study complete");
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: "
                  << error.what()
                  << '\n';
        return 1;
    }

    return 0;
}
