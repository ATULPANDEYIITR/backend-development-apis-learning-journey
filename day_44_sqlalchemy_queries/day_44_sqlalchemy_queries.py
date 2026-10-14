from __future__ import annotations

"""
SQLAlchemy Queries: SELECT, filtering, joins, ordering, aggregation, pagination.

Requires:
    pip install sqlalchemy

The script uses SQLAlchemy 2.x ORM APIs with an in-memory SQLite database.
The same query patterns can be adapted to PostgreSQL, MySQL, or other supported
relational databases by changing the database URL and dialect-specific details.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    and_,
    asc,
    create_engine,
    desc,
    func,
    or_,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    employees: Mapped[list["Employee"]] = relationship(
        back_populates="department"
    )

    def __repr__(self) -> str:
        return f"Department(id={self.id}, name={self.name!r})"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
    )

    department: Mapped[Department] = relationship(
        back_populates="employees"
    )
    projects: Mapped[list["Project"]] = relationship(
        secondary="employee_projects",
        back_populates="employees",
    )

    def __repr__(self) -> str:
        return (
            f"Employee(id={self.id}, name={self.name!r}, "
            f"salary={self.salary}, department_id={self.department_id})"
        )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    employees: Mapped[list[Employee]] = relationship(
        secondary="employee_projects",
        back_populates="projects",
    )

    def __repr__(self) -> str:
        return f"Project(id={self.id}, name={self.name!r}, status={self.status!r})"


class EmployeeProject(Base):
    __tablename__ = "employee_projects"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"),
        primary_key=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        primary_key=True,
    )


@dataclass(frozen=True)
class EmployeeSummary:
    employee_id: int
    employee_name: str
    department_name: str
    salary: Decimal


def create_database():
    """
    SQLite is used so the example is executable without installing a database
    server. SQLAlchemy still builds real SQL statements and executes them
    through the database dialect.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        echo=False,
    )
    Base.metadata.create_all(engine)
    return engine


def seed_database(session: Session) -> None:
    departments = [
        Department(name="Engineering"),
        Department(name="Data Science"),
        Department(name="Security"),
        Department(name="Operations"),
        Department(name="Research"),
    ]

    session.add_all(departments)
    session.flush()

    department_by_name = {d.name: d for d in departments}

    now = datetime.now().replace(microsecond=0)

    employees = [
        Employee(
            name="Aarav Sharma",
            email="aarav@example.com",
            salary=Decimal("95000.00"),
            joined_at=now - timedelta(days=1100),
            department=department_by_name["Engineering"],
        ),
        Employee(
            name="Priya Nair",
            email="priya@example.com",
            salary=Decimal("125000.00"),
            joined_at=now - timedelta(days=800),
            department=department_by_name["Data Science"],
        ),
        Employee(
            name="Rohan Mehta",
            email="rohan@example.com",
            salary=Decimal("110000.00"),
            joined_at=now - timedelta(days=700),
            department=department_by_name["Security"],
        ),
        Employee(
            name="Ananya Singh",
            email="ananya@example.com",
            salary=Decimal("88000.00"),
            joined_at=now - timedelta(days=500),
            department=department_by_name["Operations"],
        ),
        Employee(
            name="Vikram Rao",
            email="vikram@example.com",
            salary=Decimal("135000.00"),
            joined_at=now - timedelta(days=1300),
            department=department_by_name["Research"],
        ),
        Employee(
            name="Neha Kapoor",
            email="neha@example.com",
            salary=Decimal("102000.00"),
            joined_at=now - timedelta(days=300),
            department=department_by_name["Engineering"],
        ),
        Employee(
            name="Kabir Verma",
            email="kabir@example.com",
            salary=Decimal("76000.00"),
            joined_at=now - timedelta(days=200),
            department=department_by_name["Operations"],
        ),
        Employee(
            name="Isha Gupta",
            email="isha@example.com",
            salary=Decimal("118000.00"),
            joined_at=now - timedelta(days=1000),
            department=department_by_name["Security"],
        ),
    ]

    projects = [
        Project(
            name="Cloud Migration",
            budget=Decimal("450000.00"),
            status="active",
        ),
        Project(
            name="Threat Detection Platform",
            budget=Decimal("650000.00"),
            status="active",
        ),
        Project(
            name="Data Quality Initiative",
            budget=Decimal("300000.00"),
            status="completed",
        ),
        Project(
            name="Research Knowledge Graph",
            budget=Decimal("525000.00"),
            status="active",
        ),
    ]

    session.add_all(employees)
    session.add_all(projects)
    session.flush()

    employee_by_name = {e.name: e for e in employees}
    project_by_name = {p.name: p for p in projects}

    assignments = {
        "Cloud Migration": [
            "Aarav Sharma",
            "Neha Kapoor",
            "Ananya Singh",
        ],
        "Threat Detection Platform": [
            "Rohan Mehta",
            "Isha Gupta",
            "Aarav Sharma",
        ],
        "Data Quality Initiative": [
            "Priya Nair",
            "Kabir Verma",
        ],
        "Research Knowledge Graph": [
            "Vikram Rao",
            "Priya Nair",
        ],
    }

    for project_name, employee_names in assignments.items():
        project = project_by_name[project_name]
        project.employees.extend(
            employee_by_name[name] for name in employee_names
        )

    session.commit()


def print_rows(title: str, rows: Iterable[object]) -> None:
    print(f"\n=== {title} ===")
    for row in rows:
        print(row)


def basic_select(session: Session) -> None:
    """Demonstrate SELECTing complete ORM entities."""
    statement = select(Employee)

    employees = session.scalars(statement).all()

    print_rows("Basic SELECT", employees)


def select_specific_columns(session: Session) -> None:
    """
    Selecting columns rather than complete ORM objects is useful when the
    application only needs a small projection of the underlying table.
    """
    statement = select(
        Employee.name,
        Employee.email,
        Employee.salary,
    )

    rows = session.execute(statement).all()

    print_rows(
        "SELECT Specific Columns",
        [
            {
                "name": row.name,
                "email": row.email,
                "salary": row.salary,
            }
            for row in rows
        ],
    )


def filtering_with_where(session: Session) -> None:
    """
    SQLAlchemy's where() constructs the SQL WHERE clause. Multiple expressions
    can be combined using &, |, and explicit and_/or_ functions.
    """
    high_earners = session.scalars(
        select(Employee)
        .where(Employee.salary >= Decimal("110000.00"))
        .order_by(Employee.salary.desc())
    ).all()

    print_rows("Employees with salary >= 110000", high_earners)

    engineering_or_security = session.scalars(
        select(Employee)
        .where(
            or_(
                Employee.department.has(name="Engineering"),
                Employee.department.has(name="Security"),
            )
        )
        .order_by(Employee.name)
    ).all()

    print_rows(
        "Engineering or Security Employees",
        engineering_or_security,
    )


def multiple_filter_conditions(session: Session) -> None:
    statement = (
        select(Employee)
        .where(
            and_(
                Employee.salary >= Decimal("90000.00"),
                Employee.salary < Decimal("130000.00"),
            )
        )
        .order_by(Employee.salary)
    )

    employees = session.scalars(statement).all()

    print_rows(
        "Salary Range: 90000 <= salary < 130000",
        employees,
    )


def filtering_by_membership_and_pattern(session: Session) -> None:
    departments = ["Engineering", "Security"]

    statement = (
        select(Employee)
        .join(Employee.department)
        .where(
            Department.name.in_(departments),
            Employee.name.like("%a%"),
        )
        .order_by(Employee.name)
    )

    employees = session.scalars(statement).all()

    print_rows(
        "Department Membership + Name Pattern",
        employees,
    )


def join_queries(session: Session) -> None:
    """
    An explicit join is appropriate when the query needs columns from related
    tables or when the relationship path should be visible in the statement.
    """
    statement = (
        select(
            Employee.name,
            Department.name.label("department"),
        )
        .join(Employee.department)
        .order_by(Department.name, Employee.name)
    )

    rows = session.execute(statement).all()

    print_rows(
        "INNER JOIN Employees -> Departments",
        [
            {
                "employee": row.name,
                "department": row.department,
            }
            for row in rows
        ],
    )


def many_to_many_join(session: Session) -> None:
    """
    Projects and employees use a many-to-many association table. SQLAlchemy
    follows the ORM relationships while the generated SQL uses the association
    table to connect both entities.
    """
    statement = (
        select(
            Project.name.label("project"),
            Employee.name.label("employee"),
        )
        .join(Project.employees)
        .order_by(Project.name, Employee.name)
    )

    rows = session.execute(statement).all()

    print_rows(
        "Many-to-Many Project Assignment Query",
        [
            {
                "project": row.project,
                "employee": row.employee,
            }
            for row in rows
        ],
    )


def ordering_queries(session: Session) -> None:
    newest = session.scalars(
        select(Employee)
        .order_by(desc(Employee.joined_at), asc(Employee.name))
    ).all()

    print_rows(
        "Newest Employees First",
        newest,
    )

    salary_order = session.scalars(
        select(Employee)
        .order_by(
            desc(Employee.salary),
            asc(Employee.name),
        )
    ).all()

    print_rows(
        "Salary Descending with Name Tie-Breaker",
        salary_order,
    )


def aggregation_queries(session: Session) -> None:
    """
    SQL aggregation functions are represented with SQLAlchemy's func object.
    """
    statement = select(
        func.count(Employee.id).label("employee_count"),
        func.avg(Employee.salary).label("average_salary"),
        func.min(Employee.salary).label("minimum_salary"),
        func.max(Employee.salary).label("maximum_salary"),
        func.sum(Employee.salary).label("salary_total"),
    )

    result = session.execute(statement).one()

    print("\n=== Global Aggregation ===")
    print(f"Employee count: {result.employee_count}")
    print(f"Average salary: {result.average_salary}")
    print(f"Minimum salary: {result.minimum_salary}")
    print(f"Maximum salary: {result.maximum_salary}")
    print(f"Salary total: {result.salary_total}")


def grouped_aggregation(session: Session) -> None:
    """
    GROUP BY separates aggregation into department-level groups.
    HAVING filters groups after aggregation.
    """
    statement = (
        select(
            Department.name.label("department"),
            func.count(Employee.id).label("employee_count"),
            func.avg(Employee.salary).label("average_salary"),
            func.max(Employee.salary).label("highest_salary"),
        )
        .join(Department.employees)
        .group_by(Department.id, Department.name)
        .having(func.count(Employee.id) >= 1)
        .order_by(desc(func.avg(Employee.salary)))
    )

    rows = session.execute(statement).all()

    print_rows(
        "Department Aggregation",
        [
            {
                "department": row.department,
                "employee_count": row.employee_count,
                "average_salary": round(float(row.average_salary), 2),
                "highest_salary": float(row.highest_salary),
            }
            for row in rows
        ],
    )


def project_employee_counts(session: Session) -> None:
    statement = (
        select(
            Project.name,
            func.count(Employee.id).label("assigned_employees"),
        )
        .join(Project.employees)
        .group_by(Project.id, Project.name)
        .order_by(desc("assigned_employees"), Project.name)
    )

    rows = session.execute(statement).all()

    print_rows(
        "Employees per Project",
        [
            {
                "project": row.name,
                "assigned_employees": row.assigned_employees,
            }
            for row in rows
        ],
    )


def pagination_with_limit_offset(session: Session) -> None:
    """
    Pagination should use deterministic ordering. Without ORDER BY, database
    row order is not a reliable API contract.
    """
    page_size = 3

    for page_number in range(1, 4):
        offset = (page_number - 1) * page_size

        statement = (
            select(Employee)
            .order_by(Employee.id)
            .limit(page_size)
            .offset(offset)
        )

        employees = session.scalars(statement).all()

        print(f"\n=== Page {page_number} ===")
        for employee in employees:
            print(employee)


def reusable_pagination(
    session: Session,
    page: int,
    page_size: int,
) -> list[Employee]:
    """
    Validate pagination parameters before sending them to the database.
    """
    if page < 1:
        raise ValueError("page must be >= 1")

    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")

    offset = (page - 1) * page_size

    statement = (
        select(Employee)
        .order_by(Employee.id)
        .limit(page_size)
        .offset(offset)
    )

    return session.scalars(statement).all()


def pagination_with_total_count(
    session: Session,
    page: int,
    page_size: int,
) -> tuple[list[Employee], int]:
    """
    API endpoints often need both the current page and the total matching
    record count.
    """
    if page < 1:
        raise ValueError("page must be >= 1")

    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")

    total = session.scalar(
        select(func.count(Employee.id))
    ) or 0

    statement = (
        select(Employee)
        .order_by(Employee.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    records = session.scalars(statement).all()
    return records, total


def dynamic_query(
    session: Session,
    department_name: str | None = None,
    minimum_salary: Decimal | None = None,
    maximum_salary: Decimal | None = None,
    name_search: str | None = None,
) -> list[Employee]:
    """
    Dynamic filtering is safer when each optional condition is represented by
    a SQLAlchemy expression instead of concatenating raw SQL strings.
    """
    conditions = []

    if department_name:
        conditions.append(Department.name == department_name)

    if minimum_salary is not None:
        conditions.append(Employee.salary >= minimum_salary)

    if maximum_salary is not None:
        conditions.append(Employee.salary <= maximum_salary)

    if name_search:
        conditions.append(Employee.name.ilike(f"%{name_search}%"))

    statement = select(Employee).join(Employee.department)

    if conditions:
        statement = statement.where(*conditions)

    statement = statement.order_by(Employee.name)

    return session.scalars(statement).all()


def demonstrate_dynamic_query(session: Session) -> None:
    employees = dynamic_query(
        session,
        department_name="Security",
        minimum_salary=Decimal("100000.00"),
    )

    print_rows(
        "Dynamic Query",
        employees,
    )


def subquery_example(session: Session) -> None:
    """
    A scalar subquery can calculate a value once and use it inside another
    query. Here it identifies employees earning above the company average.
    """
    average_salary = select(
        func.avg(Employee.salary)
    ).scalar_subquery()

    statement = (
        select(Employee)
        .where(Employee.salary > average_salary)
        .order_by(Employee.salary.desc())
    )

    employees = session.scalars(statement).all()

    print_rows(
        "Employees Above Company Average",
        employees,
    )


def exists_example(session: Session) -> None:
    """
    EXISTS is useful when the application needs to test whether a related
    record exists rather than retrieve every matching related row.
    """
    project_exists = (
        select(Project.id)
        .join(Project.employees)
        .where(
            Employee.id == Employee.id,
            Project.status == "active",
        )
    )

    statement = (
        select(Employee)
        .where(
            Employee.projects.any(Project.status == "active")
        )
        .order_by(Employee.name)
    )

    employees = session.scalars(statement).all()

    print_rows(
        "Employees Assigned to at Least One Active Project",
        employees,
    )

    # The explicit subquery above illustrates the concept while SQLAlchemy's
    # relationship-aware any() expression is clearer for this ORM model.
    _ = project_exists


def projection_into_dataclass(session: Session) -> list[EmployeeSummary]:
    statement = (
        select(
            Employee.id,
            Employee.name,
            Department.name.label("department_name"),
            Employee.salary,
        )
        .join(Employee.department)
        .order_by(Employee.id)
    )

    return [
        EmployeeSummary(
            employee_id=row.id,
            employee_name=row.name,
            department_name=row.department_name,
            salary=row.salary,
        )
        for row in session.execute(statement)
    ]


def inspect_generated_sql(session: Session) -> None:
    """
    SQLAlchemy statements can be inspected before execution. Compiling with
    literal_binds is useful for learning and debugging, but values should not
    be manually interpolated into production SQL.
    """
    statement = (
        select(Employee.name, Employee.salary)
        .where(Employee.salary >= Decimal("100000.00"))
        .order_by(Employee.salary.desc())
        .limit(5)
    )

    compiled = statement.compile(
        session.get_bind(),
        compile_kwargs={"literal_binds": True},
    )

    print("\n=== Generated SQL ===")
    print(compiled)


def error_handling_example(session: Session) -> None:
    """
    SQLAlchemy raises database and ORM exceptions rather than silently
    converting failed operations into successful application states.
    """
    try:
        invalid_statement = select(Employee).where(
            Employee.salary > "not-a-number"
        )
        session.scalars(invalid_statement).all()
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        print("\n=== Query Error Handling ===")
        print(f"Query could not be processed: {type(exc).__name__}: {exc}")


def transaction_example(session: Session) -> None:
    """
    Queries and writes can participate in a transaction. The transaction is
    committed only after the operation succeeds.
    """
    try:
        with session.begin():
            department = session.scalar(
                select(Department)
                .where(Department.name == "Research")
            )

            if department is None:
                raise ValueError("Research department does not exist")

            employee = Employee(
                name="Temporary Analyst",
                email="temporary.analyst@example.com",
                salary=Decimal("91000.00"),
                joined_at=datetime.now().replace(microsecond=0),
                department=department,
            )

            session.add(employee)

        print("\n=== Transaction ===")
        print("New employee committed successfully.")

    except (SQLAlchemyError, ValueError) as exc:
        print(f"Transaction failed: {exc}")


def verify_transaction(session: Session) -> None:
    employee = session.scalar(
        select(Employee)
        .where(Employee.email == "temporary.analyst@example.com")
    )

    print("\n=== Transaction Verification ===")
    print(employee)


def common_query_patterns(session: Session) -> None:
    """
    A compact collection of patterns useful when building repository methods
    or service-layer query functions.
    """
    salary_statement = (
        select(Employee)
        .where(Employee.salary.between(
            Decimal("80000.00"),
            Decimal("120000.00"),
        ))
        .order_by(Employee.salary)
    )

    employees = session.scalars(salary_statement).all()

    print_rows(
        "BETWEEN Salary Query",
        employees,
    )

    null_check_statement = select(Employee).where(
        Employee.email.is_not(None)
    )

    email_rows = session.scalars(null_check_statement).all()

    print_rows(
        "IS NOT NULL Query",
        email_rows[:3],
    )


def main() -> None:
    engine = create_database()

    with Session(engine) as session:
        seed_database(session)

        basic_select(session)
        select_specific_columns(session)
        filtering_with_where(session)
        multiple_filter_conditions(session)
        filtering_by_membership_and_pattern(session)
        join_queries(session)
        many_to_many_join(session)
        ordering_queries(session)
        aggregation_queries(session)
        grouped_aggregation(session)
        project_employee_counts(session)
        pagination_with_limit_offset(session)

        paginated_records = reusable_pagination(
            session,
            page=2,
            page_size=2,
        )

        print_rows(
            "Reusable Pagination Function",
            paginated_records,
        )

        records, total = pagination_with_total_count(
            session,
            page=1,
            page_size=3,
        )

        print("\n=== Pagination Metadata ===")
        print(f"Returned records: {len(records)}")
        print(f"Total matching records: {total}")

        demonstrate_dynamic_query(session)
        subquery_example(session)
        exists_example(session)
        common_query_patterns(session)

        summaries = projection_into_dataclass(session)

        print("\n=== Typed Query Projection ===")
        for summary in summaries:
            print(summary)

        inspect_generated_sql(session)
        error_handling_example(session)
        transaction_example(session)
        verify_transaction(session)


if __name__ == "__main__":
    main()
