"use strict";

/*
 * SQLAlchemy Queries: SELECT, filtering, joins, ordering, aggregation,
 * and pagination.
 *
 * This file provides a JavaScript-side query workflow model complementary
 * to the SQLAlchemy ORM implementation. It focuses on the same relational
 * query semantics while using JavaScript's data-processing and functional
 * capabilities to make the query stages observable.
 *
 * Run:
 *   node sqlalchemy_queries.js
 */

const departments = [
  { id: 1, name: "Engineering" },
  { id: 2, name: "Data Science" },
  { id: 3, name: "Security" },
  { id: 4, name: "Operations" },
  { id: 5, name: "Research" },
];

const employees = [
  {
    id: 1,
    name: "Aarav Sharma",
    email: "aarav@example.com",
    salary: 95000,
    departmentId: 1,
  },
  {
    id: 2,
    name: "Priya Nair",
    email: "priya@example.com",
    salary: 125000,
    departmentId: 2,
  },
  {
    id: 3,
    name: "Rohan Mehta",
    email: "rohan@example.com",
    salary: 110000,
    departmentId: 3,
  },
  {
    id: 4,
    name: "Ananya Singh",
    email: "ananya@example.com",
    salary: 88000,
    departmentId: 4,
  },
  {
    id: 5,
    name: "Vikram Rao",
    email: "vikram@example.com",
    salary: 135000,
    departmentId: 5,
  },
  {
    id: 6,
    name: "Neha Kapoor",
    email: "neha@example.com",
    salary: 102000,
    departmentId: 1,
  },
  {
    id: 7,
    name: "Kabir Verma",
    email: "kabir@example.com",
    salary: 76000,
    departmentId: 4,
  },
  {
    id: 8,
    name: "Isha Gupta",
    email: "isha@example.com",
    salary: 118000,
    departmentId: 3,
  },
];

const projects = [
  { id: 1, name: "Cloud Migration", budget: 450000, status: "active" },
  {
    id: 2,
    name: "Threat Detection Platform",
    budget: 650000,
    status: "active",
  },
  {
    id: 3,
    name: "Data Quality Initiative",
    budget: 300000,
    status: "completed",
  },
  {
    id: 4,
    name: "Research Knowledge Graph",
    budget: 525000,
    status: "active",
  },
];

const employeeProjects = [
  { employeeId: 1, projectId: 1 },
  { employeeId: 6, projectId: 1 },
  { employeeId: 4, projectId: 1 },
  { employeeId: 3, projectId: 2 },
  { employeeId: 8, projectId: 2 },
  { employeeId: 1, projectId: 2 },
  { employeeId: 2, projectId: 3 },
  { employeeId: 7, projectId: 3 },
  { employeeId: 5, projectId: 4 },
  { employeeId: 2, projectId: 4 },
];

function printRows(title, rows) {
  console.log(`\n=== ${title} ===`);
  console.table(rows);
}

function selectEmployees() {
  return employees;
}

function selectColumns(rows, columns) {
  return rows.map((row) => {
    const result = {};

    for (const column of columns) {
      result[column] = row[column];
    }

    return result;
  });
}

function where(rows, predicate) {
  return rows.filter(predicate);
}

function orderBy(rows, selector, direction = "asc") {
  return [...rows].sort((a, b) => {
    const left = selector(a);
    const right = selector(b);

    if (left === right) {
      return 0;
    }

    const comparison = left < right ? -1 : 1;
    return direction === "asc" ? comparison : -comparison;
  });
}

function innerJoin(leftRows, rightRows, leftKey, rightKey, projector) {
  const rightIndex = new Map();

  for (const rightRow of rightRows) {
    const key = rightKey(rightRow);

    if (!rightIndex.has(key)) {
      rightIndex.set(key, []);
    }

    rightIndex.get(key).push(rightRow);
  }

  const result = [];

  for (const leftRow of leftRows) {
    const matches = rightIndex.get(leftKey(leftRow)) || [];

    for (const rightRow of matches) {
      result.push(projector(leftRow, rightRow));
    }
  }

  return result;
}

function groupBy(rows, keySelector) {
  const groups = new Map();

  for (const row of rows) {
    const key = keySelector(row);

    if (!groups.has(key)) {
      groups.set(key, []);
    }

    groups.get(key).push(row);
  }

  return groups;
}

function aggregateGroup(groupRows) {
  const salaries = groupRows.map((employee) => employee.salary);

  const total = salaries.reduce((sum, salary) => sum + salary, 0);
  const average = total / salaries.length;

  return {
    employeeCount: salaries.length,
    totalSalary: total,
    averageSalary: average,
    minimumSalary: Math.min(...salaries),
    maximumSalary: Math.max(...salaries),
  };
}

function paginate(rows, page, pageSize) {
  if (!Number.isInteger(page) || page < 1) {
    throw new RangeError("page must be a positive integer");
  }

  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
    throw new RangeError("pageSize must be between 1 and 100");
  }

  const start = (page - 1) * pageSize;
  const end = start + pageSize;

  return {
    records: rows.slice(start, end),
    page,
    pageSize,
    total: rows.length,
    totalPages: Math.ceil(rows.length / pageSize),
  };
}

function queryEmployees({
  departmentName,
  minimumSalary,
  maximumSalary,
  nameContains,
  sort = "name",
  direction = "asc",
}) {
  let rows = [...employees];

  if (departmentName) {
    const department = departments.find(
      (item) => item.name === departmentName
    );

    if (!department) {
      return [];
    }

    rows = where(rows, (employee) => {
      return employee.departmentId === department.id;
    });
  }

  if (minimumSalary !== undefined) {
    rows = where(rows, (employee) => {
      return employee.salary >= minimumSalary;
    });
  }

  if (maximumSalary !== undefined) {
    rows = where(rows, (employee) => {
      return employee.salary <= maximumSalary;
    });
  }

  if (nameContains) {
    const normalized = nameContains.toLowerCase();

    rows = where(rows, (employee) => {
      return employee.name.toLowerCase().includes(normalized);
    });
  }

  const selectors = {
    id: (employee) => employee.id,
    name: (employee) => employee.name,
    salary: (employee) => employee.salary,
  };

  if (!(sort in selectors)) {
    throw new Error(`Unsupported sort field: ${sort}`);
  }

  return orderBy(rows, selectors[sort], direction);
}

function demonstrateSelect() {
  const result = selectEmployees();

  printRows("SELECT Employees", result);
}

function demonstrateFiltering() {
  const result = where(employees, (employee) => {
    return employee.salary >= 110000;
  });

  printRows("WHERE salary >= 110000", result);
}

function demonstrateCombinedFiltering() {
  const result = where(employees, (employee) => {
    return (
      employee.salary >= 90000 &&
      employee.salary < 130000 &&
      [1, 3].includes(employee.departmentId)
    );
  });

  printRows("Combined WHERE Conditions", result);
}

function demonstrateProjection() {
  const result = selectColumns(employees, [
    "id",
    "name",
    "salary",
  ]);

  printRows("Column Projection", result);
}

function demonstrateJoin() {
  const result = innerJoin(
    employees,
    departments,
    (employee) => employee.departmentId,
    (department) => department.id,
    (employee, department) => ({
      employee: employee.name,
      department: department.name,
      salary: employee.salary,
    })
  );

  printRows("Employee -> Department Join", result);
}

function demonstrateManyToManyJoin() {
  const employeeProjectRows = innerJoin(
    employeeProjects,
    employees,
    (assignment) => assignment.employeeId,
    (employee) => employee.id,
    (assignment, employee) => ({
      employeeId: employee.id,
      employeeName: employee.name,
      projectId: assignment.projectId,
    })
  );

  const result = innerJoin(
    employeeProjectRows,
    projects,
    (row) => row.projectId,
    (project) => project.id,
    (row, project) => ({
      employee: row.employeeName,
      project: project.name,
      status: project.status,
    })
  );

  printRows("Many-to-Many Project Join", result);
}

function demonstrateOrdering() {
  const result = orderBy(
    employees,
    (employee) => employee.salary,
    "desc"
  );

  printRows("ORDER BY salary DESC", result);
}

function demonstrateAggregation() {
  const salaries = employees.map((employee) => employee.salary);

  const total = salaries.reduce((sum, salary) => sum + salary, 0);
  const average = total / salaries.length;

  console.log("\n=== Global Aggregation ===");
  console.log(`COUNT: ${salaries.length}`);
  console.log(`SUM: ${total}`);
  console.log(`AVG: ${average.toFixed(2)}`);
  console.log(`MIN: ${Math.min(...salaries)}`);
  console.log(`MAX: ${Math.max(...salaries)}`);
}

function demonstrateGroupAggregation() {
  const joined = innerJoin(
    employees,
    departments,
    (employee) => employee.departmentId,
    (department) => department.id,
    (employee, department) => ({
      employee,
      department,
    })
  );

  const groups = groupBy(
    joined,
    (row) => row.department.name
  );

  const result = [...groups.entries()].map(
    ([departmentName, rows]) => {
      const values = aggregateGroup(
        rows.map((row) => row.employee)
      );

      return {
        department: departmentName,
        ...values,
      };
    }
  );

  const ordered = orderBy(
    result,
    (row) => row.averageSalary,
    "desc"
  );

  printRows("GROUP BY Department", ordered);
}

function demonstratePagination() {
  const ordered = orderBy(
    employees,
    (employee) => employee.id,
    "asc"
  );

  const firstPage = paginate(ordered, 1, 3);
  const secondPage = paginate(ordered, 2, 3);

  printRows("Pagination Page 1", firstPage.records);
  printRows("Pagination Page 2", secondPage.records);

  console.log("\nPagination Metadata");
  console.log({
    total: firstPage.total,
    pageSize: firstPage.pageSize,
    totalPages: firstPage.totalPages,
  });
}

function demonstrateDynamicQuery() {
  const result = queryEmployees({
    departmentName: "Security",
    minimumSalary: 100000,
    sort: "salary",
    direction: "desc",
  });

  printRows("Dynamic Query", result);
}

function demonstrateAboveAverageQuery() {
  const total = employees.reduce(
    (sum, employee) => sum + employee.salary,
    0
  );

  const average = total / employees.length;

  const result = employees
    .filter((employee) => employee.salary > average)
    .sort((a, b) => b.salary - a.salary);

  console.log(`\nCompany average salary: ${average.toFixed(2)}`);

  printRows(
    "Employees Above Average",
    result
  );
}

function demonstrateExistsQuery() {
  const activeProjectIds = new Set(
    projects
      .filter((project) => project.status === "active")
      .map((project) => project.id)
  );

  const employeesWithActiveProjects = employees.filter(
    (employee) => {
      return employeeProjects.some(
        (assignment) =>
          assignment.employeeId === employee.id &&
          activeProjectIds.has(assignment.projectId)
      );
    }
  );

  printRows(
    "Employees with Active Projects",
    employeesWithActiveProjects
  );
}

function demonstrateQueryPipeline() {
  /*
   * This pipeline resembles the conceptual order of an ORM query:
   * FROM/JOIN -> WHERE -> SELECT -> ORDER BY -> LIMIT/OFFSET.
   *
   * Keeping the stages separate makes debugging easier because each stage
   * has a clearly defined input and output.
   */
  const joined = innerJoin(
    employees,
    departments,
    (employee) => employee.departmentId,
    (department) => department.id,
    (employee, department) => ({
      employeeId: employee.id,
      employeeName: employee.name,
      departmentName: department.name,
      salary: employee.salary,
    })
  );

  const filtered = joined.filter(
    (row) =>
      row.salary >= 90000 &&
      row.departmentName !== "Operations"
  );

  const projected = filtered.map((row) => ({
    employee: row.employeeName,
    department: row.departmentName,
    salary: row.salary,
  }));

  const ordered = [...projected].sort(
    (a, b) => b.salary - a.salary
  );

  const result = ordered.slice(0, 4);

  printRows(
    "JOIN -> WHERE -> SELECT -> ORDER BY -> LIMIT",
    result
  );
}

function demonstrateErrorHandling() {
  try {
    paginate(employees, 0, 10);
  } catch (error) {
    console.log("\n=== Validation Failure ===");
    console.log(`${error.name}: ${error.message}`);
  }

  try {
    queryEmployees({
      sort: "unknownColumn",
    });
  } catch (error) {
    console.log("\n=== Sort Validation Failure ===");
    console.log(`${error.name}: ${error.message}`);
  }
}

function main() {
  demonstrateSelect();
  demonstrateProjection();
  demonstrateFiltering();
  demonstrateCombinedFiltering();
  demonstrateJoin();
  demonstrateManyToManyJoin();
  demonstrateOrdering();
  demonstrateAggregation();
  demonstrateGroupAggregation();
  demonstratePagination();
  demonstrateDynamicQuery();
  demonstrateAboveAverageQuery();
  demonstrateExistsQuery();
  demonstrateQueryPipeline();
  demonstrateErrorHandling();
}

main();
