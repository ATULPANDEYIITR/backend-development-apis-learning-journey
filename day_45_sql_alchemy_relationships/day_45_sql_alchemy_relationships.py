from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import (
    ForeignKey,
    String,
    Table,
    create_engine,
    event,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
)
from sqlalchemy.orm.exc import NoResultFound


# SQLAlchemy relationship mapping
#
# This script demonstrates:
# - one-to-one: User <-> UserProfile
# - one-to-many: Department -> Employee
# - many-to-many: Employee <-> Project
# - cascading: ownership and deletion behavior
#
# SQLite is used so the file runs without an external database server.
# SQLite foreign-key enforcement is explicitly enabled because SQLite does
# not enable it by default for every connection.


class Base(DeclarativeBase):
    pass


employee_project = Table(
    "employee_project",
    Base.metadata,
    mapped_column(
        "employee_id",
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    mapped_column(
        "project_id",
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # One department owns many employees.
    # delete-orphan means an Employee removed from the collection is no
    # longer considered an independent child of that department.
    employees: Mapped[list["Employee"]] = relationship(
        back_populates="department",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Department(id={self.id}, name={self.name!r})"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    department: Mapped["Department"] = relationship(
        back_populates="employees"
    )

    # Many employees can work on many projects.
    projects: Mapped[list["Project"]] = relationship(
        secondary=employee_project,
        back_populates="employees",
        lazy="selectin",
    )

    # Exactly one profile is associated with each employee.
    profile: Mapped["EmployeeProfile | None"] = relationship(
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Employee(id={self.id}, name={self.name!r})"


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    job_title: Mapped[str] = mapped_column(String(120), nullable=False)
    office_location: Mapped[str] = mapped_column(String(120), nullable=False)

    employee: Mapped["Employee"] = relationship(
        back_populates="profile"
    )

    def __repr__(self) -> str:
        return (
            f"EmployeeProfile(id={self.id}, "
            f"job_title={self.job_title!r}, "
            f"office_location={self.office_location!r})"
        )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    employees: Mapped[list[Employee]] = relationship(
        secondary=employee_project,
        back_populates="projects",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"Project(id={self.id}, name={self.name!r})"


def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Turn on SQLite foreign-key enforcement for every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(
    "sqlite:///sqlalchemy_relationships.db",
    echo=False,
)

event.listen(
    engine,
    "connect",
    enable_sqlite_foreign_keys,
)

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


def create_sample_graph(session: Session) -> None:
    """Build a complete relationship graph in one unit of work."""

    engineering = Department(name="Engineering")
    operations = Department(name="Operations")

    alice = Employee(
        name="Alice Sharma",
        email="alice@example.com",
        department=engineering,
    )
    bob = Employee(
        name="Bob Mehta",
        email="bob@example.com",
        department=engineering,
    )
    carol = Employee(
        name="Carol Singh",
        email="carol@example.com",
        department=operations,
    )

    alice.profile = EmployeeProfile(
        job_title="Backend Engineer",
        office_location="Lucknow",
    )
    bob.profile = EmployeeProfile(
        job_title="Database Engineer",
        office_location="Delhi",
    )
    carol.profile = EmployeeProfile(
        job_title="Operations Analyst",
        office_location="Mumbai",
    )

    api_platform = Project(name="API Platform")
    data_migration = Project(name="Data Migration")
    observability = Project(name="Observability")

    # The same Project can be associated with several Employees.
    alice.projects.extend([api_platform, observability])
    bob.projects.extend([api_platform, data_migration])
    carol.projects.extend([data_migration, observability])

    session.add_all([engineering, operations])
    session.commit()


def demonstrate_one_to_one(session: Session) -> None:
    print("\n--- ONE-TO-ONE ---")

    employee = session.scalar(
        select(Employee)
        .where(Employee.email == "alice@example.com")
        .options(selectinload(Employee.profile))
    )

    if employee is None:
        raise NoResultFound("Alice does not exist")

    print(employee)
    print("Profile:", employee.profile)

    # The ORM relationship uses uselist=False, while the database uses
    # UNIQUE(employee_id). Both layers express the one-to-one invariant.
    duplicate = EmployeeProfile(
        employee_id=employee.id,
        job_title="Duplicate Profile",
        office_location="Delhi",
    )
    session.add(duplicate)

    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        print("Duplicate profile rejected by UNIQUE(employee_id).")


def demonstrate_one_to_many(session: Session) -> None:
    print("\n--- ONE-TO-MANY ---")

    department = session.scalar(
        select(Department)
        .where(Department.name == "Engineering")
        .options(selectinload(Department.employees))
    )

    if department is None:
        raise NoResultFound("Engineering department does not exist")

    print("Department:", department.name)

    for employee in department.employees:
        print("  Employee:", employee.name)


def demonstrate_many_to_many(session: Session) -> None:
    print("\n--- MANY-TO-MANY ---")

    projects = session.scalars(
        select(Project)
        .options(selectinload(Project.employees))
        .order_by(Project.name)
    ).all()

    for project in projects:
        employee_names = [employee.name for employee in project.employees]
        print(f"{project.name}: {employee_names}")

    alice = session.scalar(
        select(Employee)
        .where(Employee.email == "alice@example.com")
        .options(selectinload(Employee.projects))
    )

    if alice is not None:
        print(
            "Alice's projects:",
            [project.name for project in alice.projects],
        )


def demonstrate_cascade_delete_orphan(session: Session) -> None:
    print("\n--- DELETE-ORPHAN CASCADE ---")

    department = session.scalar(
        select(Department)
        .where(Department.name == "Operations")
        .options(selectinload(Department.employees))
    )

    if department is None:
        raise NoResultFound("Operations department does not exist")

    employee = next(
        employee
        for employee in department.employees
        if employee.email == "carol@example.com"
    )

    print("Before removal:", employee, employee.profile)

    # Because EmployeeProfile is configured with delete-orphan,
    # removing the Employee from the Department relationship causes the
    # Employee itself to be deleted. Its profile is also deleted through
    # the Employee's own delete-orphan cascade.
    #
    # This is an intentionally destructive demonstration, so it occurs
    # inside a transaction that is committed after inspection.
    session.delete(employee)
    session.commit()

    remaining_employee = session.scalar(
        select(Employee).where(Employee.email == "carol@example.com")
    )

    remaining_profile = session.scalar(
        select(EmployeeProfile).where(
            EmployeeProfile.job_title == "Operations Analyst"
        )
    )

    print("Employee after delete:", remaining_employee)
    print("Profile after employee delete:", remaining_profile)


def demonstrate_many_to_many_association_removal(session: Session) -> None:
    print("\n--- MANY-TO-MANY ASSOCIATION REMOVAL ---")

    alice = session.scalar(
        select(Employee)
        .where(Employee.email == "alice@example.com")
        .options(selectinload(Employee.projects))
    )

    if alice is None:
        raise NoResultFound("Alice does not exist")

    project = next(
        project
        for project in alice.projects
        if project.name == "Observability"
    )

    alice.projects.remove(project)
    session.commit()

    refreshed = session.scalar(
        select(Employee)
        .where(Employee.email == "alice@example.com")
        .options(selectinload(Employee.projects))
    )

    print(
        "Alice's projects after removing Observability:",
        [project.name for project in refreshed.projects],
    )

    # Removing the association does not delete the Project itself.
    existing_project = session.scalar(
        select(Project).where(Project.name == "Observability")
    )
    print("Project still exists:", existing_project is not None)


def demonstrate_eager_loading(session: Session) -> None:
    print("\n--- RELATIONSHIP LOADING ---")

    employees = session.scalars(
        select(Employee)
        .options(
            selectinload(Employee.department),
            selectinload(Employee.profile),
            selectinload(Employee.projects),
        )
        .order_by(Employee.name)
    ).all()

    for employee in employees:
        print(
            employee.name,
            "| department =", employee.department.name,
            "| profile =", employee.profile.job_title
            if employee.profile
            else None,
            "| projects =",
            [project.name for project in employee.projects],
        )


def demonstrate_relationship_reassignment(session: Session) -> None:
    print("\n--- RELATIONSHIP REASSIGNMENT ---")

    alice = session.scalar(
        select(Employee).where(Employee.email == "alice@example.com")
    )

    operations = session.scalar(
        select(Department).where(Department.name == "Operations")
    )

    if alice is None or operations is None:
        raise NoResultFound("Required entities are missing")

    original_department = alice.department

    # Reassigning the many-to-one relationship changes department_id.
    # It does not create a second Employee row.
    alice.department = operations
    session.commit()

    print(
        f"{alice.name}: "
        f"{original_department.name} -> {alice.department.name}"
    )

    # Restore the original relationship for the remaining examples.
    engineering = session.scalar(
        select(Department).where(Department.name == "Engineering")
    )
    alice.department = engineering
    session.commit()


def demonstrate_invalid_foreign_key(session: Session) -> None:
    print("\n--- FOREIGN-KEY VALIDATION ---")

    invalid_employee = Employee(
        name="Invalid Employee",
        email="invalid@example.com",
        department_id=999999,
    )

    session.add(invalid_employee)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        print("Employee with nonexistent department rejected.")


def print_database_state(session: Session) -> None:
    print("\n--- FINAL DATABASE STATE ---")

    departments = session.scalars(
        select(Department)
        .options(selectinload(Department.employees))
        .order_by(Department.name)
    ).all()

    for department in departments:
        print(
            department.name,
            "=>",
            [employee.name for employee in department.employees],
        )

    print(
        "Projects:",
        [
            project.name
            for project in session.scalars(
                select(Project).order_by(Project.name)
            )
        ],
    )


def main() -> None:
    with Session(engine) as session:
        create_sample_graph(session)

        demonstrate_one_to_one(session)
        demonstrate_one_to_many(session)
        demonstrate_many_to_many(session)
        demonstrate_eager_loading(session)
        demonstrate_relationship_reassignment(session)
        demonstrate_invalid_foreign_key(session)
        demonstrate_many_to_many_association_removal(session)
        demonstrate_cascade_delete_orphan(session)

        print_database_state(session)


if __name__ == "__main__":
    main()
