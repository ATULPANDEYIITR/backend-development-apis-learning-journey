from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)


# SQLAlchemy 2.x declarative models use a Base class as the registry for mapped
# Python classes. The generated metadata contains the database schema.
class Base(DeclarativeBase):
    pass


# An association table is appropriate when a many-to-many relationship does
# not require its own business attributes.
pull_request_reviewers = Table(
    "pull_request_reviewers",
    Base.metadata,
    mapped_column("pull_request_id", ForeignKey("pull_requests.id"), primary_key=True),
    mapped_column("reviewer_id", ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    authored_pull_requests: Mapped[List["PullRequest"]] = relationship(
        back_populates="author",
        foreign_keys="PullRequest.author_id",
    )

    reviews: Mapped[List["Review"]] = relationship(
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )

    assigned_pull_requests: Mapped[List["PullRequest"]] = relationship(
        secondary=pull_request_reviewers,
        back_populates="reviewers",
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, username={self.username!r})"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    branches: Mapped[List["Branch"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    pull_requests: Mapped[List["PullRequest"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False,
    )

    repository: Mapped["Repository"] = relationship(back_populates="branches")

    protection_policy: Mapped[Optional["BranchProtection"]] = relationship(
        back_populates="branch",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="open", nullable=False)

    source_branch: Mapped[str] = mapped_column(String(120), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(120), nullable=False)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")

    author: Mapped["User"] = relationship(
        back_populates="authored_pull_requests",
        foreign_keys=[author_id],
    )

    reviewers: Mapped[List["User"]] = relationship(
        secondary=pull_request_reviewers,
        back_populates="assigned_pull_requests",
    )

    reviews: Mapped[List["Review"]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan",
    )

    commits: Mapped[List["Commit"]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan",
    )


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id"),
        nullable=False,
    )

    pull_request: Mapped["PullRequest"] = relationship(back_populates="commits")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)

    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id"),
        nullable=False,
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    pull_request: Mapped["PullRequest"] = relationship(back_populates="reviews")
    reviewer: Mapped["User"] = relationship(back_populates="reviews")


class BranchProtection(Base):
    __tablename__ = "branch_protection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"),
        unique=True,
        nullable=False,
    )

    required_reviews: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    require_status_checks: Mapped[bool] = mapped_column(default=True, nullable=False)
    allow_force_push: Mapped[bool] = mapped_column(default=False, nullable=False)

    branch: Mapped["Branch"] = relationship(back_populates="protection_policy")


def create_demo_database():
    # SQLite keeps the example executable without requiring a separate server.
    # The same declarative models can be used with PostgreSQL by changing the URL.
    engine = create_engine("sqlite:///:memory:", echo=False)

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        alice = User(username="alice", email="alice@example.com")
        bob = User(username="bob", email="bob@example.com")
        carol = User(username="carol", email="carol@example.com")

        repository = Repository(name="payment-service")

        main = Branch(name="main", repository=repository)
        feature = Branch(name="feature/payment-validation", repository=repository)

        protection = BranchProtection(
            branch=main,
            required_reviews=2,
            require_status_checks=True,
            allow_force_push=False,
        )

        pull_request = PullRequest(
            title="Add payment validation",
            description="Validates payment requests before processing.",
            state="open",
            source_branch=feature.name,
            target_branch=main.name,
            repository=repository,
            author=alice,
            reviewers=[bob, carol],
        )

        commit = Commit(
            sha="0123456789abcdef0123456789abcdef01234567",
            message="Add payment validation rules",
            pull_request=pull_request,
        )

        review_from_bob = Review(
            state="approved",
            body="Validation rules are clear.",
            pull_request=pull_request,
            reviewer=bob,
        )

        review_from_carol = Review(
            state="approved",
            body="Tests cover the important edge cases.",
            pull_request=pull_request,
            reviewer=carol,
        )

        session.add_all([
            alice,
            bob,
            carol,
            repository,
            main,
            feature,
            protection,
            pull_request,
            commit,
            review_from_bob,
            review_from_carol,
        ])

        session.commit()

        # SQLAlchemy automatically assigns primary keys after flush/commit.
        print(f"Repository ID: {repository.id}")
        print(f"Pull Request ID: {pull_request.id}")
        print(f"Author: {pull_request.author.username}")
        print(f"Target branch: {pull_request.target_branch}")
        print(f"Reviewer count: {len(pull_request.reviewers)}")

        # The modern SQLAlchemy 2.x query style uses select() with Session.scalars().
        statement = select(PullRequest).where(PullRequest.state == "open")
        open_pull_requests = session.scalars(statement).all()

        for item in open_pull_requests:
            print(f"Open PR: #{item.id} {item.title}")

        # Relationship collections provide object-level navigation over foreign keys.
        for review in pull_request.reviews:
            print(
                f"Review by {review.reviewer.username}: "
                f"{review.state}"
            )

        return engine


if __name__ == "__main__":
    create_demo_database()
