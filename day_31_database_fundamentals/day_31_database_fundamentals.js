"use strict";

/*
 * Database Fundamentals in JavaScript
 *
 * This file models a relational project-management database without requiring
 * npm packages. It focuses on JavaScript-specific techniques for representing
 * tables, rows, primary keys, relationships, reviewable changes, validation,
 * events, transactions, and query-like operations.
 *
 * Runtime:
 *     node database_fundamentals.js
 *
 * The program deliberately keeps the relational model in memory so that the
 * file remains executable on a standard Node.js installation.
 */

const database = {
  projects: new Map(),
  tasks: new Map(),
  members: new Map(),
  projectMembers: new Map(),
  indexes: {
    tasksByProject: new Map(),
  },
};

const events = new Map();

function printHeading(title) {
  console.log(`\n${"=".repeat(72)}`);
  console.log(title);
  console.log("=".repeat(72));
}

function emit(eventName, payload) {
  const handlers = events.get(eventName) ?? [];

  for (const handler of handlers) {
    try {
      handler(payload);
    } catch (error) {
      console.error(`Event handler failed for ${eventName}:`, error.message);
    }
  }
}

function on(eventName, handler) {
  if (!events.has(eventName)) {
    events.set(eventName, []);
  }

  events.get(eventName).push(handler);

  return () => {
    const handlers = events.get(eventName) ?? [];
    events.set(
      eventName,
      handlers.filter((candidate) => candidate !== handler),
    );
  };
}

class PrimaryKeyGenerator {
  constructor(start = 1) {
    this.nextId = start;
  }

  next() {
    return this.nextId++;
  }
}

const projectIdGenerator = new PrimaryKeyGenerator();
const taskIdGenerator = new PrimaryKeyGenerator();
const memberIdGenerator = new PrimaryKeyGenerator();

function requireNonEmptyString(value, fieldName) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TypeError(`${fieldName} must be a non-empty string`);
  }

  return value.trim();
}

function requirePositiveInteger(value, fieldName) {
  if (!Number.isInteger(value) || value <= 0) {
    throw new TypeError(`${fieldName} must be a positive integer`);
  }

  return value;
}

function insertProject({ name, owner }) {
  name = requireNonEmptyString(name, "name");
  owner = requireNonEmptyString(owner, "owner");

  for (const project of database.projects.values()) {
    if (project.name.toLowerCase() === name.toLowerCase()) {
      throw new Error(`UNIQUE constraint failed: project name '${name}'`);
    }
  }

  const project = {
    projectId: projectIdGenerator.next(),
    name,
    owner,
    createdAt: new Date().toISOString(),
  };

  database.projects.set(project.projectId, project);
  emit("project.created", project);

  return project;
}

function insertTask({ projectId, title, status = "todo", dueDate = null }) {
  projectId = requirePositiveInteger(projectId, "projectId");
  title = requireNonEmptyString(title, "title");

  const validStatuses = new Set(["todo", "in_progress", "done"]);

  if (!validStatuses.has(status)) {
    throw new Error(`CHECK constraint failed: unsupported task status '${status}'`);
  }

  if (!database.projects.has(projectId)) {
    throw new Error(`FOREIGN KEY constraint failed: project ${projectId} does not exist`);
  }

  if (dueDate !== null && !/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) {
    throw new TypeError("dueDate must use YYYY-MM-DD format");
  }

  const task = {
    taskId: taskIdGenerator.next(),
    projectId,
    title,
    status,
    dueDate,
  };

  database.tasks.set(task.taskId, task);

  if (!database.indexes.tasksByProject.has(projectId)) {
    database.indexes.tasksByProject.set(projectId, new Set());
  }

  database.indexes.tasksByProject.get(projectId).add(task.taskId);

  emit("task.created", task);

  return task;
}

function insertMember(name) {
  name = requireNonEmptyString(name, "member name");

  for (const member of database.members.values()) {
    if (member.name.toLowerCase() === name.toLowerCase()) {
      throw new Error(`UNIQUE constraint failed: member '${name}'`);
    }
  }

  const member = {
    memberId: memberIdGenerator.next(),
    name,
  };

  database.members.set(member.memberId, member);
  return member;
}

function addProjectMember(projectId, memberId, role) {
  requirePositiveInteger(projectId, "projectId");
  requirePositiveInteger(memberId, "memberId");
  role = requireNonEmptyString(role, "role");

  if (!database.projects.has(projectId)) {
    throw new Error("Cannot create membership for a missing project");
  }

  if (!database.members.has(memberId)) {
    throw new Error("Cannot create membership for a missing member");
  }

  // A composite key models PRIMARY KEY(project_id, member_id).
  const compositeKey = `${projectId}:${memberId}`;

  if (database.projectMembers.has(compositeKey)) {
    throw new Error("Duplicate project membership rejected");
  }

  database.projectMembers.set(compositeKey, {
    projectId,
    memberId,
    role,
  });
}

function selectRows(tableName) {
  if (!(tableName in database) || tableName === "indexes") {
    throw new Error(`Unknown relational table: ${tableName}`);
  }

  return Array.from(database[tableName].values());
}

function updateTaskStatus(taskId, status) {
  const task = database.tasks.get(taskId);

  if (!task) {
    throw new Error(`Task ${taskId} does not exist`);
  }

  const validStatuses = new Set(["todo", "in_progress", "done"]);

  if (!validStatuses.has(status)) {
    throw new Error(`Invalid task status: ${status}`);
  }

  const previousStatus = task.status;
  task.status = status;

  emit("task.updated", {
    taskId,
    previousStatus,
    status,
  });

  return task;
}

function projectTaskJoin() {
  /*
   * This is an in-memory equivalent of a relational JOIN. The projectId
   * foreign key in each task determines which project row is related.
   */
  const joinedRows = [];

  for (const project of database.projects.values()) {
    const taskIds = database.indexes.tasksByProject.get(project.projectId) ?? new Set();

    if (taskIds.size === 0) {
      joinedRows.push({
        projectId: project.projectId,
        projectName: project.name,
        taskId: null,
        taskTitle: null,
        status: null,
      });
      continue;
    }

    for (const taskId of taskIds) {
      const task = database.tasks.get(taskId);

      joinedRows.push({
        projectId: project.projectId,
        projectName: project.name,
        taskId: task.taskId,
        taskTitle: task.title,
        status: task.status,
      });
    }
  }

  return joinedRows;
}

function membersForProject(projectId) {
  requirePositiveInteger(projectId, "projectId");

  return Array.from(database.projectMembers.values())
    .filter((membership) => membership.projectId === projectId)
    .map((membership) => ({
      projectId,
      memberId: membership.memberId,
      memberName: database.members.get(membership.memberId).name,
      role: membership.role,
    }));
}

function countTasksByStatus(projectId) {
  const taskIds = database.indexes.tasksByProject.get(projectId) ?? new Set();

  return Array.from(taskIds).reduce(
    (counts, taskId) => {
      const status = database.tasks.get(taskId).status;
      counts[status] += 1;
      return counts;
    },
    {
      todo: 0,
      in_progress: 0,
      done: 0,
    },
  );
}

function cloneDatabaseState() {
  /*
   * A transaction needs an isolated snapshot. structuredClone preserves the
   * nested Map and Set structures supported by modern Node.js.
   */
  return structuredClone({
    projects: database.projects,
    tasks: database.tasks,
    members: database.members,
    projectMembers: database.projectMembers,
    indexes: database.indexes,
  });
}

function restoreDatabaseState(snapshot) {
  database.projects = snapshot.projects;
  database.tasks = snapshot.tasks;
  database.members = snapshot.members;
  database.projectMembers = snapshot.projectMembers;
  database.indexes = snapshot.indexes;
}

function transaction(work) {
  const snapshot = cloneDatabaseState();

  try {
    return work();
  } catch (error) {
    restoreDatabaseState(snapshot);
    throw error;
  }
}

function safeUserSearch(searchTerm) {
  /*
   * The search is performed as data, not as executable query text. This is
   * conceptually similar to a parameterized database query.
   */
  const normalized = requireNonEmptyString(searchTerm, "searchTerm").toLowerCase();

  return Array.from(database.projects.values()).filter((project) =>
    project.name.toLowerCase().includes(normalized),
  );
}

function buildProjectReport() {
  return Array.from(database.projects.values()).map((project) => {
    const counts = countTasksByStatus(project.projectId);

    return {
      project: project.name,
      owner: project.owner,
      totalTasks: counts.todo + counts.in_progress + counts.done,
      completedTasks: counts.done,
      completionPercent:
        counts.todo + counts.in_progress + counts.done === 0
          ? 0
          : (counts.done /
              (counts.todo + counts.in_progress + counts.done)) *
            100,
    };
  });
}

function demonstrateSchemaConcepts() {
  printHeading("Tables, rows, columns, and keys");

  console.log("projects columns: projectId, name, owner, createdAt");
  console.log("tasks columns: taskId, projectId, title, status, dueDate");
  console.log("projectId is the primary key of projects.");
  console.log("taskId is the primary key of tasks.");
  console.log("tasks.projectId references projects.projectId.");
}

function demonstrateBasicRows() {
  printHeading("Stored rows");

  console.table(selectRows("projects"));
  console.table(selectRows("tasks"));
}

function demonstrateRelationships() {
  printHeading("One-to-many relationship");

  console.table(projectTaskJoin());

  printHeading("Many-to-many relationship");

  for (const project of database.projects.values()) {
    console.log(project.name);
    console.table(membersForProject(project.projectId));
  }
}

function demonstrateConstraints() {
  printHeading("Constraint failures");

  const attempts = [
    () => insertProject({ name: "", owner: "Tester" }),
    () => insertProject({ name: "Market Analytics", owner: "Duplicate Owner" }),
    () => insertTask({ projectId: 999, title: "Orphan task" }),
    () => insertTask({ projectId: 1, title: "Invalid status", status: "archived_forever" }),
  ];

  for (const attempt of attempts) {
    try {
      attempt();
    } catch (error) {
      console.log("Rejected:", error.message);
    }
  }
}

function demonstrateTransaction() {
  printHeading("Application transaction simulation");

  const before = database.projects.size;

  try {
    transaction(() => {
      insertProject({
        name: "Temporary Import",
        owner: "Migration Service",
      });

      // This intentionally fails because project 9999 does not exist.
      insertTask({
        projectId: 9999,
        title: "Should be rolled back",
      });
    });
  } catch (error) {
    console.log("Transaction failed:", error.message);
  }

  console.log(
    "Project count before:",
    before,
    "after rollback:",
    database.projects.size,
  );
}

function demonstrateIndexLookup() {
  printHeading("Indexed relationship lookup");

  const project = Array.from(database.projects.values())[0];
  const taskIds = database.indexes.tasksByProject.get(project.projectId) ?? new Set();

  console.log(`Tasks for '${project.name}' retrieved through tasksByProject index:`);

  for (const taskId of taskIds) {
    console.log(database.tasks.get(taskId));
  }

  console.log(
    "The index avoids scanning every task when the application repeatedly asks",
    "for tasks belonging to one project.",
  );
}

function demonstrateEvents() {
  printHeading("Event-driven data changes");

  const unsubscribe = on("task.updated", (event) => {
    console.log(
      `Event received: task ${event.taskId} changed from ` +
        `${event.previousStatus} to ${event.status}`,
    );
  });

  updateTaskStatus(2, "done");
  unsubscribe();
}

function demonstrateValidationAndSecurity() {
  printHeading("Validation and safe searching");

  try {
    insertTask({
      projectId: 1,
      title: "Prepare database migration",
      status: "in_progress",
      dueDate: "2026-10-20",
    });
    console.log("Validated task accepted.");
  } catch (error) {
    console.log("Validation failed:", error.message);
  }

  console.log(
    "Search result for hostile-looking text:",
    safeUserSearch("Market' OR 1=1 --"),
  );
}

function demonstrateAggregation() {
  printHeading("Relational-style aggregation");

  console.table(buildProjectReport());
}

function demonstrateEdgeCases() {
  printHeading("Relationship edge cases");

  const emptyProject = insertProject({
    name: "Empty Project",
    owner: "Operations",
  });

  console.log(
    "LEFT-JOIN-like representation for a project without tasks:",
    projectTaskJoin().find((row) => row.projectId === emptyProject.projectId),
  );

  try {
    addProjectMember(emptyProject.projectId, 9999, "Unknown");
  } catch (error) {
    console.log("Missing member rejected:", error.message);
  }

  try {
    addProjectMember(emptyProject.projectId, 1, "Coordinator");
    addProjectMember(emptyProject.projectId, 1, "Duplicate Coordinator");
  } catch (error) {
    console.log("Duplicate composite key rejected:", error.message);
  }
}

function seed() {
  const market = insertProject({
    name: "Market Analytics",
    owner: "Atul",
  });

  const assets = insertProject({
    name: "Asset Tracking",
    owner: "Priya",
  });

  const research = insertProject({
    name: "Research Portal",
    owner: "Rahul",
  });

  insertTask({
    projectId: market.projectId,
    title: "Design relational schema",
    status: "done",
    dueDate: "2026-10-03",
  });

  insertTask({
    projectId: market.projectId,
    title: "Build portfolio data model",
    status: "in_progress",
    dueDate: "2026-10-08",
  });

  insertTask({
    projectId: assets.projectId,
    title: "Register tracked assets",
    status: "done",
    dueDate: "2026-10-04",
  });

  insertTask({
    projectId: assets.projectId,
    title: "Store movement history",
    status: "in_progress",
    dueDate: "2026-10-11",
  });

  insertTask({
    projectId: research.projectId,
    title: "Import research records",
    status: "todo",
    dueDate: "2026-10-15",
  });

  const atul = insertMember("Atul");
  const priya = insertMember("Priya");
  const rahul = insertMember("Rahul");

  addProjectMember(market.projectId, atul.memberId, "Product Owner");
  addProjectMember(market.projectId, priya.memberId, "Data Engineer");
  addProjectMember(assets.projectId, atul.memberId, "System Designer");
  addProjectMember(assets.projectId, priya.memberId, "Operations");
  addProjectMember(research.projectId, atul.memberId, "Research Lead");
  addProjectMember(research.projectId, rahul.memberId, "Analyst");
}

function main() {
  printHeading("Database Fundamentals with JavaScript");
  console.log("The relational model is represented with Maps and Sets.");
  console.log("The design emphasizes primary keys, foreign keys, and relationships.");

  demonstrateSchemaConcepts();
  seed();
  demonstrateBasicRows();
  demonstrateRelationships();
  demonstrateConstraints();
  demonstrateTransaction();
  demonstrateIndexLookup();
  demonstrateEvents();
  demonstrateValidationAndSecurity();
  demonstrateAggregation();
  demonstrateEdgeCases();

  printHeading("Final database state");
  console.log("Projects:", database.projects.size);
  console.log("Tasks:", database.tasks.size);
  console.log("Members:", database.members.size);
  console.log("Memberships:", database.projectMembers.size);
}

main();
