/*
    Database Normalization Case Study
    ----------------------------------
    Scenario: a technical organization manages teams, projects, developers,
    skills, and project assignments.

    The program acts as a small repository-independent relational design engine.
    It starts with an intentionally redundant assignment structure and evaluates
    the functional dependencies that justify decomposition.

    C++17 standard library only.
*/

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using Attributes = std::set<std::string>;

struct FunctionalDependency {
    Attributes determinant;
    Attributes dependent;
};

struct Project {
    std::string id;
    std::string name;
    std::string teamId;
};

struct Team {
    std::string id;
    std::string name;
};

struct Developer {
    std::string id;
    std::string name;
    std::string teamId;
};

struct Assignment {
    std::string projectId;
    std::string developerId;
    int allocationPercent;
};

struct Skill {
    std::string id;
    std::string name;
};

struct DeveloperSkill {
    std::string developerId;
    std::string skillId;
};

std::string joinAttributes(const Attributes& attributes) {
    std::string result;
    bool first = true;

    for (const auto& attribute : attributes) {
        if (!first) {
            result += ", ";
        }
        result += attribute;
        first = false;
    }

    return result;
}

Attributes closure(
    Attributes initial,
    const std::vector<FunctionalDependency>& dependencies
) {
    Attributes result = std::move(initial);

    bool changed = true;
    while (changed) {
        changed = false;

        for (const auto& dependency : dependencies) {
            bool determinantSatisfied = std::includes(
                result.begin(),
                result.end(),
                dependency.determinant.begin(),
                dependency.determinant.end()
            );

            if (determinantSatisfied) {
                const std::size_t before = result.size();
                result.insert(
                    dependency.dependent.begin(),
                    dependency.dependent.end()
                );

                changed = result.size() != before;
            }
        }
    }

    return result;
}

bool isSuperkey(
    const Attributes& determinant,
    const Attributes& relationAttributes,
    const std::vector<FunctionalDependency>& dependencies
) {
    return closure(determinant, dependencies) == relationAttributes;
}

void printDependency(const FunctionalDependency& dependency) {
    std::cout
        << "  {" << joinAttributes(dependency.determinant)
        << "} -> {" << joinAttributes(dependency.dependent) << "}\n";
}

void demonstrateOneNF() {
    std::cout << "\n=== 1NF: atomic attributes ===\n";

    std::cout
        << "An unnormalized project record stores developer IDs as a single\n"
        << "comma-separated value. That is a repeating group, not a relational\n"
        << "relationship.\n\n";

    std::cout << "UNF: project=P100, developers=[D01,D02,D03]\n";

    std::cout
        << "\nAfter 1NF, each row contains one project/developer relationship:\n"
        << "P100 | D01\n"
        << "P100 | D02\n"
        << "P100 | D03\n";

    std::cout
        << "\nThe important change is structural: a query can address one\n"
        << "developer relationship without parsing a string.\n";
}

void demonstrateTwoNF() {
    std::cout << "\n=== 2NF: remove partial dependencies ===\n";

    std::cout
        << "Consider Assignment(project_id, developer_id, project_name,\n"
        << "developer_name, allocation_percent).\n\n";

    std::cout
        << "The composite key is (project_id, developer_id).\n"
        << "project_name depends only on project_id.\n"
        << "developer_name depends only on developer_id.\n"
        << "allocation_percent depends on the complete assignment key.\n";

    std::cout
        << "\nDecomposition:\n"
        << "Project(project_id, project_name)\n"
        << "Developer(developer_id, developer_name)\n"
        << "Assignment(project_id, developer_id, allocation_percent)\n";

    std::cout
        << "\nThis removes repeated project and developer facts from every\n"
        << "assignment row.\n";
}

void demonstrateThreeNF() {
    std::cout << "\n=== 3NF: remove transitive dependencies ===\n";

    std::cout
        << "Project(project_id, project_name, team_id, team_name) contains:\n"
        << "project_id -> team_id\n"
        << "team_id -> team_name\n\n";

    std::cout
        << "Therefore team_name is transitively dependent on project_id.\n"
        << "The team relation should own team_name.\n\n";

    std::cout
        << "Project(project_id, project_name, team_id)\n"
        << "Team(team_id, team_name)\n";

    std::cout
        << "\nThe project row now references a team instead of copying team facts.\n";
}

void demonstrateBCNF() {
    std::cout << "\n=== BCNF: every determinant must be a superkey ===\n";

    Attributes attributes{"student", "course", "instructor"};

    std::vector<FunctionalDependency> dependencies{
        {{"student", "course"}, {"instructor"}},
        {{"instructor"}, {"course"}}
    };

    std::cout << "Functional dependencies:\n";
    for (const auto& dependency : dependencies) {
        printDependency(dependency);
    }

    Attributes instructorOnly{"instructor"};

    std::cout
        << "\nClosure of {instructor}: {"
        << joinAttributes(closure(instructorOnly, dependencies))
        << "}\n";

    std::cout
        << "\nThe closure does not contain student, so instructor is not a\n"
        << "superkey. Therefore instructor -> course violates BCNF.\n";

    std::cout
        << "\nBCNF decomposition:\n"
        << "InstructorCourse(instructor, course)\n"
        << "StudentInstructor(student, instructor)\n";
}

class GovernanceDataStore {
private:
    std::unordered_map<std::string, Team> teams_;
    std::unordered_map<std::string, Developer> developers_;
    std::unordered_map<std::string, Project> projects_;
    std::unordered_map<std::string, Skill> skills_;

    // A tuple gives the relationship a natural composite-key representation.
    std::map<std::pair<std::string, std::string>, Assignment> assignments_;

    // Many-to-many relationship between developers and skills.
    std::set<std::pair<std::string, std::string>> developerSkills_;

public:
    void addTeam(const Team& team) {
        if (team.id.empty() || team.name.empty()) {
            throw std::invalid_argument("Team ID and name are required.");
        }
        if (!teams_.emplace(team.id, team).second) {
            throw std::invalid_argument("Duplicate team ID.");
        }
    }

    void addDeveloper(const Developer& developer) {
        if (developer.id.empty() || developer.name.empty()) {
            throw std::invalid_argument("Developer ID and name are required.");
        }
        if (!teams_.contains(developer.teamId)) {
            throw std::invalid_argument("Developer references an unknown team.");
        }
        if (!developers_.emplace(developer.id, developer).second) {
            throw std::invalid_argument("Duplicate developer ID.");
        }
    }

    void addProject(const Project& project) {
        if (project.id.empty() || project.name.empty()) {
            throw std::invalid_argument("Project ID and name are required.");
        }
        if (!teams_.contains(project.teamId)) {
            throw std::invalid_argument("Project references an unknown team.");
        }
        if (!projects_.emplace(project.id, project).second) {
            throw std::invalid_argument("Duplicate project ID.");
        }
    }

    void addSkill(const Skill& skill) {
        if (skill.id.empty() || skill.name.empty()) {
            throw std::invalid_argument("Skill ID and name are required.");
        }
        if (!skills_.emplace(skill.id, skill).second) {
            throw std::invalid_argument("Duplicate skill ID.");
        }
    }

    void addAssignment(
        const std::string& projectId,
        const std::string& developerId,
        int allocationPercent
    ) {
        if (!projects_.contains(projectId)) {
            throw std::invalid_argument("Unknown project.");
        }
        if (!developers_.contains(developerId)) {
            throw std::invalid_argument("Unknown developer.");
        }
        if (allocationPercent < 1 || allocationPercent > 100) {
            throw std::invalid_argument("Allocation must be 1..100.");
        }

        const auto key = std::make_pair(projectId, developerId);

        if (assignments_.contains(key)) {
            throw std::invalid_argument("Duplicate project/developer assignment.");
        }

        assignments_.emplace(
            key,
            Assignment{projectId, developerId, allocationPercent}
        );
    }

    void addDeveloperSkill(
        const std::string& developerId,
        const std::string& skillId
    ) {
        if (!developers_.contains(developerId)) {
            throw std::invalid_argument("Unknown developer.");
        }
        if (!skills_.contains(skillId)) {
            throw std::invalid_argument("Unknown skill.");
        }

        if (!developerSkills_.emplace(developerId, skillId).second) {
            throw std::invalid_argument("Duplicate developer/skill relation.");
        }
    }

    std::vector<std::tuple<std::string, std::string, int>> staffingReport() const {
        std::vector<std::tuple<std::string, std::string, int>> report;

        for (const auto& [key, assignment] : assignments_) {
            const auto projectIt = projects_.find(assignment.projectId);
            const auto developerIt = developers_.find(assignment.developerId);

            report.emplace_back(
                projectIt->second.name,
                developerIt->second.name,
                assignment.allocationPercent
            );
        }

        return report;
    }
};

void demonstratePracticalDesign() {
    std::cout << "\n=== Practical normalized case study ===\n";

    GovernanceDataStore store;

    store.addTeam({"T10", "Data Platform"});
    store.addTeam({"T20", "Security Engineering"});

    store.addDeveloper({"D01", "Asha", "T10"});
    store.addDeveloper({"D02", "Ravi", "T10"});
    store.addDeveloper({"D03", "Meera", "T20"});

    store.addProject({"P100", "Market Analytics", "T10"});
    store.addProject({"P200", "Risk Engine", "T10"});
    store.addProject({"P300", "Security Monitor", "T20"});

    store.addSkill({"S01", "C++"});
    store.addSkill({"S02", "SQL"});
    store.addSkill({"S03", "Database Design"});
    store.addSkill({"S04", "Security Engineering"});

    store.addAssignment("P100", "D01", 60);
    store.addAssignment("P100", "D02", 40);
    store.addAssignment("P200", "D02", 70);
    store.addAssignment("P200", "D03", 30);

    store.addDeveloperSkill("D01", "S02");
    store.addDeveloperSkill("D01", "S03");
    store.addDeveloperSkill("D02", "S01");
    store.addDeveloperSkill("D02", "S02");
    store.addDeveloperSkill("D03", "S04");

    std::cout
        << "\nNormalized relations keep entity facts separate from relationship facts.\n";

    for (const auto& [project, developer, allocation] : store.staffingReport()) {
        std::cout
            << "Project=" << std::left << std::setw(20) << project
            << " Developer=" << std::setw(10) << developer
            << " Allocation=" << allocation << "%\n";
    }

    std::cout << "\nIntegrity failure examples:\n";

    try {
        store.addAssignment("P999", "D01", 50);
    } catch (const std::exception& error) {
        std::cout << "  Foreign-key-like failure: " << error.what() << '\n';
    }

    try {
        store.addAssignment("P100", "D01", 50);
    } catch (const std::exception& error) {
        std::cout << "  Composite-key failure: " << error.what() << '\n';
    }

    try {
        store.addAssignment("P100", "D02", 101);
    } catch (const std::exception& error) {
        std::cout << "  Check-constraint-like failure: " << error.what() << '\n';
    }
}

void demonstrateDenormalizationTradeoff() {
    std::cout << "\n=== Denormalization trade-off ===\n";

    std::cout
        << "Suppose a dashboard displays project_name and team_name for millions\n"
        << "of report reads. A separate read model may duplicate team_name to\n"
        << "avoid repeatedly joining Project and Team.\n\n";

    std::cout
        << "The duplicated value must not become a second source of truth.\n"
        << "A transactional refresh, materialized view, event-driven projection,\n"
        << "or rebuild process can keep the read model synchronized.\n\n";

    std::cout
        << "Denormalization can reduce join work, but it increases write complexity,\n"
        << "storage, cache invalidation risk, and consistency responsibilities.\n";
}

int main() {
    try {
        demonstrateOneNF();
        demonstrateTwoNF();
        demonstrateThreeNF();
        demonstrateBCNF();
        demonstratePracticalDesign();
        demonstrateDenormalizationTradeoff();

        std::cout
            << "\n=== Design conclusion ===\n"
            << "Normalization is driven by functional dependencies and relationship\n"
            << "semantics. 1NF addresses atomic structure, 2NF removes partial\n"
            << "dependencies, 3NF removes transitive dependencies, and BCNF requires\n"
            << "every non-trivial determinant to be a superkey.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
