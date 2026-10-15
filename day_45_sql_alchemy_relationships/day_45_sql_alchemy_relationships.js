"use strict";

/*
 * SQLAlchemy is a Python ORM, so JavaScript cannot instantiate its
 * relationship objects directly. This file models the same relational
 * behavior from an event-driven repository-service perspective.
 *
 * The implementation focuses on relationship semantics:
 * - one-to-one profile ownership
 * - one-to-many department membership
 * - many-to-many project assignments
 * - cascading deletion and association removal
 *
 * Run with:
 *   node sqlalchemy_relationships.js
 */

class RelationshipError extends Error {
    constructor(message) {
        super(message);
        this.name = "RelationshipError";
    }
}

class Repository {
    constructor() {
        this.departments = new Map();
        this.employees = new Map();
        this.profiles = new Map();
        this.projects = new Map();

        this.nextIds = {
            department: 1,
            employee: 1,
            profile: 1,
            project: 1
        };
    }

    createDepartment(name) {
        if (!name?.trim()) {
            throw new RelationshipError("Department name is required.");
        }

        if ([...this.departments.values()].some(d => d.name === name)) {
            throw new RelationshipError(`Department already exists: ${name}`);
        }

        const department = {
            id: this.nextIds.department++,
            name,
            employeeIds: new Set()
        };

        this.departments.set(department.id, department);
        return department;
    }

    createEmployee(name, email, departmentId) {
        if (!name?.trim() || !email?.trim()) {
            throw new RelationshipError("Employee name and email are required.");
        }

        if (this.employeesByEmail(email)) {
            throw new RelationshipError(`Email already exists: ${email}`);
        }

        const department = this.departments.get(departmentId);

        if (!department) {
            throw new RelationshipError(
                `Department ${departmentId} does not exist.`
            );
        }

        const employee = {
            id: this.nextIds.employee++,
            name,
            email,
            departmentId,
            profileId: null,
            projectIds: new Set()
        };

        this.employees.set(employee.id, employee);
        department.employeeIds.add(employee.id);

        return employee;
    }

    employeesByEmail(email) {
        return [...this.employees.values()].find(
            employee => employee.email === email
        );
    }

    createProfile(employeeId, jobTitle, officeLocation) {
        const employee = this.employees.get(employeeId);

        if (!employee) {
            throw new RelationshipError("Cannot profile nonexistent employee.");
        }

        if (employee.profileId !== null) {
            throw new RelationshipError(
                "One-to-one violation: employee already has a profile."
            );
        }

        const profile = {
            id: this.nextIds.profile++,
            employeeId,
            jobTitle,
            officeLocation
        };

        this.profiles.set(profile.id, profile);
        employee.profileId = profile.id;

        return profile;
    }

    createProject(name) {
        if (!name?.trim()) {
            throw new RelationshipError("Project name is required.");
        }

        const project = {
            id: this.nextIds.project++,
            name,
            employeeIds: new Set()
        };

        this.projects.set(project.id, project);
        return project;
    }

    assignEmployeeToProject(employeeId, projectId) {
        const employee = this.employees.get(employeeId);
        const project = this.projects.get(projectId);

        if (!employee || !project) {
            throw new RelationshipError(
                "Both employee and project must exist."
            );
        }

        // A Set models the composite-key behavior of an association table:
        // the same employee/project relationship cannot be inserted twice.
        employee.projectIds.add(projectId);
        project.employeeIds.add(employeeId);
    }

    removeEmployeeFromProject(employeeId, projectId) {
        const employee = this.employees.get(employeeId);
        const project = this.projects.get(projectId);

        if (!employee || !project) {
            throw new RelationshipError(
                "Both employee and project must exist."
            );
        }

        employee.projectIds.delete(projectId);
        project.employeeIds.delete(employeeId);

        // Removing a many-to-many link does not delete either endpoint.
    }

    moveEmployee(employeeId, newDepartmentId) {
        const employee = this.employees.get(employeeId);
        const newDepartment = this.departments.get(newDepartmentId);

        if (!employee || !newDepartment) {
            throw new RelationshipError(
                "Employee and destination department must exist."
            );
        }

        const oldDepartment = this.departments.get(employee.departmentId);

        oldDepartment.employeeIds.delete(employee.id);
        newDepartment.employeeIds.add(employee.id);
        employee.departmentId = newDepartment.id;
    }

    deleteEmployee(employeeId) {
        const employee = this.employees.get(employeeId);

        if (!employee) {
            return;
        }

        const department = this.departments.get(employee.departmentId);
        department?.employeeIds.delete(employee.id);

        // Cascade employee -> profile.
        if (employee.profileId !== null) {
            this.profiles.delete(employee.profileId);
        }

        // Cascade employee -> many-to-many association rows.
        for (const projectId of employee.projectIds) {
            const project = this.projects.get(projectId);
            project?.employeeIds.delete(employee.id);
        }

        this.employees.delete(employee.id);
    }

    deleteDepartment(departmentId) {
        const department = this.departments.get(departmentId);

        if (!department) {
            return;
        }

        // This application chooses explicit cascading semantics for the
        // one-to-many ownership relation.
        for (const employeeId of [...department.employeeIds]) {
            this.deleteEmployee(employeeId);
        }

        this.departments.delete(departmentId);
    }

    employeeView(employeeId) {
        const employee = this.employees.get(employeeId);

        if (!employee) {
            throw new RelationshipError("Employee does not exist.");
        }

        const department = this.departments.get(employee.departmentId);
        const profile = employee.profileId === null
            ? null
            : this.profiles.get(employee.profileId);

        const projects = [...employee.projectIds]
            .map(id => this.projects.get(id))
            .filter(Boolean);

        return {
            id: employee.id,
            name: employee.name,
            email: employee.email,
            department: department?.name ?? null,
            profile: profile
                ? {
                    jobTitle: profile.jobTitle,
                    officeLocation: profile.officeLocation
                }
                : null,
            projects: projects.map(project => project.name)
        };
    }

    projectView(projectId) {
        const project = this.projects.get(projectId);

        if (!project) {
            throw new RelationshipError("Project does not exist.");
        }

        return {
            name: project.name,
            employees: [...project.employeeIds]
                .map(id => this.employees.get(id)?.name)
                .filter(Boolean)
        };
    }
}

function printJson(label, value) {
    console.log(`\n${label}`);
    console.log(JSON.stringify(value, null, 2));
}

function runDemo() {
    const repository = new Repository();

    const engineering = repository.createDepartment("Engineering");
    const operations = repository.createDepartment("Operations");

    const alice = repository.createEmployee(
        "Alice Sharma",
        "alice@example.com",
        engineering.id
    );

    const bob = repository.createEmployee(
        "Bob Mehta",
        "bob@example.com",
        engineering.id
    );

    const carol = repository.createEmployee(
        "Carol Singh",
        "carol@example.com",
        operations.id
    );

    repository.createProfile(
        alice.id,
        "Backend Engineer",
        "Lucknow"
    );

    repository.createProfile(
        bob.id,
        "Database Engineer",
        "Delhi"
    );

    repository.createProfile(
        carol.id,
        "Operations Analyst",
        "Mumbai"
    );

    const apiPlatform = repository.createProject("API Platform");
    const dataMigration = repository.createProject("Data Migration");
    const observability = repository.createProject("Observability");

    repository.assignEmployeeToProject(alice.id, apiPlatform.id);
    repository.assignEmployeeToProject(alice.id, observability.id);
    repository.assignEmployeeToProject(bob.id, apiPlatform.id);
    repository.assignEmployeeToProject(bob.id, dataMigration.id);
    repository.assignEmployeeToProject(carol.id, dataMigration.id);
    repository.assignEmployeeToProject(carol.id, observability.id);

    printJson(
        "One-to-one employee/profile relationship",
        repository.employeeView(alice.id)
    );

    printJson(
        "One-to-many department membership",
        {
            department: engineering.name,
            employees: [...engineering.employeeIds]
                .map(id => repository.employees.get(id).name)
        }
    );

    printJson(
        "Many-to-many project membership",
        repository.projectView(apiPlatform.id)
    );

    console.log("\nMoving Alice from Engineering to Operations...");
    repository.moveEmployee(alice.id, operations.id);

    printJson(
        "Alice after reassignment",
        repository.employeeView(alice.id)
    );

    console.log("\nRemoving Alice from Observability...");
    repository.removeEmployeeFromProject(
        alice.id,
        observability.id
    );

    printJson(
        "Alice after association removal",
        repository.employeeView(alice.id)
    );

    console.log("\nDeleting Alice...");
    repository.deleteEmployee(alice.id);

    console.log(
        "Alice exists:",
        repository.employees.has(alice.id)
    );

    console.log(
        "Alice profile exists:",
        [...repository.profiles.values()]
            .some(profile => profile.employeeId === alice.id)
    );

    printJson(
        "Observability after Alice deletion",
        repository.projectView(observability.id)
    );

    console.log("\nDemonstrating one-to-one validation...");

    try {
        repository.createProfile(
            bob.id,
            "Second Profile",
            "Chennai"
        );
    } catch (error) {
        console.log(error.message);
    }

    console.log("\nDeleting the Operations department...");
    repository.deleteDepartment(operations.id);

    console.log(
        "Carol exists after department cascade:",
        repository.employees.has(carol.id)
    );

    console.log(
        "Carol profile exists after cascade:",
        [...repository.profiles.values()]
            .some(profile => profile.employeeId === carol.id)
    );
}

runDemo();
