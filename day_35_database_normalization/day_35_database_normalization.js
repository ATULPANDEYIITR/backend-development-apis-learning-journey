/**
 * Database Normalization in JavaScript
 *
 * This Node.js program models a project-management data domain and demonstrates
 * normalization as a dependency and integrity problem rather than as a naming
 * convention.
 *
 * The implementation uses JavaScript-specific features:
 * - Maps for indexed in-memory relations
 * - Sets for uniqueness checks
 * - classes for a small domain model
 * - event-driven lifecycle for maintaining a denormalized read projection
 * - asynchronous event handling to show why denormalized projections require
 *   explicit consistency management
 *
 * Run with:
 *   node normalization.js
 */

"use strict";

const EventEmitter = require("node:events");

function printHeading(title) {
    console.log(`\n${"=".repeat(76)}\n${title}\n${"=".repeat(76)}`);
}

function printRows(title, rows) {
    console.log(`\n${title}`);

    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    const columns = Object.keys(rows[0]);
    const widths = Object.fromEntries(
        columns.map((column) => [
            column,
            Math.max(
                column.length,
                ...rows.map((row) => String(row[column] ?? "").length)
            ),
        ])
    );

    console.log(
        columns.map((column) => column.padEnd(widths[column])).join(" | ")
    );
    console.log(
        columns.map((column) => "-".repeat(widths[column])).join("-+-")
    );

    for (const row of rows) {
        console.log(
            columns
                .map((column) => String(row[column] ?? "").padEnd(widths[column]))
                .join(" | ")
        );
    }
}

/*
 * A normalized repository-like data store separates entity facts from
 * relationship facts. The Maps provide efficient primary-key lookups while
 * Sets enforce composite relationship uniqueness in application memory.
 */
class NormalizedProjectStore {
    constructor() {
        this.teams = new Map();
        this.developers = new Map();
        this.projects = new Map();
        this.skills = new Map();

        this.assignments = new Map();
        this.developerSkills = new Set();
    }

    addTeam(team) {
        if (!team.id || !team.name.trim()) {
            throw new Error("A team requires a non-empty id and name.");
        }
        if (this.teams.has(team.id)) {
            throw new Error(`Team ${team.id} already exists.`);
        }

        this.teams.set(team.id, { ...team });
    }

    addDeveloper(developer) {
        if (!developer.id || !developer.name.trim()) {
            throw new Error("A developer requires a non-empty id and name.");
        }
        if (!this.teams.has(developer.teamId)) {
            throw new Error(`Unknown team ${developer.teamId}.`);
        }
        if (this.developers.has(developer.id)) {
            throw new Error(`Developer ${developer.id} already exists.`);
        }

        this.developers.set(developer.id, { ...developer });
    }

    addProject(project) {
        if (!project.id || !project.name.trim()) {
            throw new Error("A project requires a non-empty id and name.");
        }
        if (!this.teams.has(project.teamId)) {
            throw new Error(`Unknown team ${project.teamId}.`);
        }
        if (this.projects.has(project.id)) {
            throw new Error(`Project ${project.id} already exists.`);
        }

        this.projects.set(project.id, { ...project });
    }

    addSkill(skill) {
        if (!skill.id || !skill.name.trim()) {
            throw new Error("A skill requires a non-empty id and name.");
        }
        if (this.skills.has(skill.id)) {
            throw new Error(`Skill ${skill.id} already exists.`);
        }

        this.skills.set(skill.id, { ...skill });
    }

    addAssignment(projectId, developerId, allocationPercent) {
        if (!this.projects.has(projectId)) {
            throw new Error(`Unknown project ${projectId}.`);
        }
        if (!this.developers.has(developerId)) {
            throw new Error(`Unknown developer ${developerId}.`);
        }
        if (!Number.isInteger(allocationPercent) ||
            allocationPercent < 1 ||
            allocationPercent > 100) {
            throw new Error("Allocation must be an integer between 1 and 100.");
        }

        const key = `${projectId}|${developerId}`;

        // This composite key corresponds to a relationship fact. It prevents
        // duplicate project/developer rows without copying entity attributes.
        if (this.assignments.has(key)) {
            throw new Error(`Duplicate assignment ${key}.`);
        }

        this.assignments.set(key, {
            projectId,
            developerId,
            allocationPercent,
        });
    }

    addDeveloperSkill(developerId, skillId) {
        if (!this.developers.has(developerId)) {
            throw new Error(`Unknown developer ${developerId}.`);
        }
        if (!this.skills.has(skillId)) {
            throw new Error(`Unknown skill ${skillId}.`);
        }

        const key = `${developerId}|${skillId}`;

        if (this.developerSkills.has(key)) {
            throw new Error(`Duplicate developer/skill relation ${key}.`);
        }

        this.developerSkills.add(key);
    }

    staffingReport() {
        const skillsByDeveloper = new Map();

        for (const relation of this.developerSkills) {
            const [developerId, skillId] = relation.split("|");
            if (!skillsByDeveloper.has(developerId)) {
                skillsByDeveloper.set(developerId, []);
            }
            skillsByDeveloper.get(developerId).push(
                this.skills.get(skillId).name
            );
        }

        const rows = [];

        for (const assignment of this.assignments.values()) {
            const project = this.projects.get(assignment.projectId);
            const developer = this.developers.get(assignment.developerId);

            rows.push({
                project: project.name,
                developer: developer.name,
                allocation: assignment.allocationPercent,
                skills: (skillsByDeveloper.get(developer.id) ?? []).sort().join(", "),
            });
        }

        return rows;
    }
}

/*
 * This class represents a denormalized reporting projection.
 *
 * The source-of-truth tables remain normalized. The projection intentionally
 * duplicates teamName beside projectName because dashboard reads should not
 * need to join the team table on every request.
 */
class ProjectDashboard extends EventEmitter {
    constructor(store) {
        super();
        this.store = store;
        this.rows = new Map();

        this.on("teamRenamed", async ({ teamId }) => {
            // Event-driven projection maintenance introduces eventual
            // consistency. The await makes the asynchronous boundary explicit.
            await this.refreshProjectsForTeam(teamId);
        });
    }

    build() {
        this.rows.clear();

        for (const project of this.store.projects.values()) {
            const team = this.store.teams.get(project.teamId);

            this.rows.set(project.id, {
                projectId: project.id,
                projectName: project.name,
                teamId: team.id,
                teamName: team.name,
            });
        }
    }

    async refreshProjectsForTeam(teamId) {
        // A real system could update this projection from an event queue.
        // Here the same behavior is deterministic and self-contained.
        await Promise.resolve();

        const team = this.store.teams.get(teamId);
        if (!team) {
            throw new Error(`Cannot refresh projection for ${teamId}.`);
        }

        for (const project of this.store.projects.values()) {
            if (project.teamId === teamId) {
                const row = this.rows.get(project.id);
                if (row) {
                    row.teamName = team.name;
                }
            }
        }
    }

    getRows() {
        return [...this.rows.values()];
    }
}

function demonstrateNormalizationStages() {
    printHeading("1NF: atomic values");

    const badProject = {
        projectId: "P100",
        developerIds: "D01,D02",
        skills: "JavaScript,SQL",
    };

    console.log("A comma-separated value is a single string, not two relational values.");
    console.log(badProject);

    const firstNormalFormRows = [
        {
            projectId: "P100",
            developerId: "D01",
            skill: "JavaScript",
        },
        {
            projectId: "P100",
            developerId: "D01",
            skill: "SQL",
        },
        {
            projectId: "P100",
            developerId: "D02",
            skill: "SQL",
        },
    ];

    printRows("1NF representation:", firstNormalFormRows);

    printHeading("2NF: complete dependence on a composite key");

    console.log(
        "If (projectId, developerId) identifies an assignment, projectName belongs",
        "to the project relation and developerName belongs to the developer relation."
    );

    const assignments = [
        { projectId: "P100", developerId: "D01", allocation: 60 },
        { projectId: "P100", developerId: "D02", allocation: 40 },
    ];

    printRows("Relationship facts:", assignments);

    printHeading("3NF: remove transitive dependencies");

    console.log(
        "projectId -> teamId and teamId -> teamName means teamName is transitively",
        "dependent on projectId. Team-specific facts therefore belong to Team."
    );
}

function demonstrateBCNFReasoning() {
    printHeading("BCNF: determinants must be superkeys");

    const relation = [
        { student: "S01", course: "DB101", instructor: "I01" },
        { student: "S02", course: "DB101", instructor: "I01" },
        { student: "S03", course: "DB201", instructor: "I02" },
    ];

    printRows("Scheduling relation:", relation);

    console.log(
        "\nAssume instructor -> course because each instructor teaches exactly one course."
    );
    console.log(
        "Instructor is not a superkey because it does not identify a student."
    );
    console.log(
        "The instructor/course dependency should therefore be represented separately."
    );
}

async function demonstratePracticalModel() {
    printHeading("Practical normalized model");

    const store = new NormalizedProjectStore();

    store.addTeam({ id: "T10", name: "Data Platform" });
    store.addTeam({ id: "T20", name: "Security Engineering" });

    store.addDeveloper({ id: "D01", name: "Asha", teamId: "T10" });
    store.addDeveloper({ id: "D02", name: "Ravi", teamId: "T10" });
    store.addDeveloper({ id: "D03", name: "Meera", teamId: "T20" });

    store.addProject({
        id: "P100",
        name: "Market Analytics",
        teamId: "T10",
    });
    store.addProject({
        id: "P200",
        name: "Risk Engine",
        teamId: "T10",
    });
    store.addProject({
        id: "P300",
        name: "Security Monitor",
        teamId: "T20",
    });

    store.addSkill({ id: "S01", name: "JavaScript" });
    store.addSkill({ id: "S02", name: "SQL" });
    store.addSkill({ id: "S03", name: "C++" });
    store.addSkill({ id: "S04", name: "Security Engineering" });

    store.addAssignment("P100", "D01", 60);
    store.addAssignment("P100", "D02", 40);
    store.addAssignment("P200", "D02", 70);
    store.addAssignment("P200", "D03", 30);

    store.addDeveloperSkill("D01", "S01");
    store.addDeveloperSkill("D01", "S02");
    store.addDeveloperSkill("D02", "S01");
    store.addDeveloperSkill("D02", "S02");
    store.addDeveloperSkill("D02", "S03");
    store.addDeveloperSkill("D03", "S04");

    printRows("Staffing query assembled from normalized relations:", store.staffingReport());

    printHeading("Application-level integrity failures");

    try {
        store.addAssignment("P999", "D01", 50);
    } catch (error) {
        console.log(`Foreign-key-like failure: ${error.message}`);
    }

    try {
        store.addAssignment("P100", "D01", 60);
    } catch (error) {
        console.log(`Unique-key-like failure: ${error.message}`);
    }

    try {
        store.addAssignment("P100", "D02", 0);
    } catch (error) {
        console.log(`Check-constraint-like failure: ${error.message}`);
    }

    printHeading("Controlled denormalization with an event-driven projection");

    const dashboard = new ProjectDashboard(store);
    dashboard.build();

    printRows("Initial reporting projection:", dashboard.getRows());

    const team = store.teams.get("T10");
    team.name = "Data Platform Core";

    // The normalized source changed first. The projection is stale until the
    // domain event is processed, making the consistency trade-off visible.
    printRows("Projection before synchronization:", dashboard.getRows());

    dashboard.emit("teamRenamed", { teamId: "T10" });
    await new Promise((resolve) => setImmediate(resolve));

    printRows("Projection after event processing:", dashboard.getRows());

    console.log(
        "\nThe duplicated teamName is useful for reads but is not authoritative.",
        "A production system needs an explicit refresh, event, transaction, or",
        "rebuild strategy so the projection cannot silently drift."
    );
}

async function main() {
    demonstrateNormalizationStages();
    demonstrateBCNFReasoning();
    await demonstratePracticalModel();

    printHeading("Normalization versus denormalization");

    console.log(
        "Normalization reduces update anomalies by storing each fact according",
        "to its determinant and relationship."
    );
    console.log(
        "Denormalization deliberately introduces redundancy when measured read",
        "workloads justify it and when consistency can be controlled."
    );
    console.log(
        "Indexes, query plans, caching, materialized views, and read projections",
        "should be considered before duplicating authoritative business facts."
    );
}

main().catch((error) => {
    console.error(`Fatal error: ${error.message}`);
    process.exitCode = 1;
});
