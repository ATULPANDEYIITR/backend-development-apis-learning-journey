from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/repository_governance",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class PRState(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(str, Enum):
    COMMENTED = "commented"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DISMISSED = "dismissed"


class MergeStrategy(str, Enum):
    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)

    branches: Mapped[list["Branch"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    protection: Mapped["BranchProtection | None"] = relationship(
        back_populates="repository",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="branches")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_branch: Mapped[str] = mapped_column(String(100), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[PRState] = mapped_column(SAEnum(PRState), default=PRState.OPEN, nullable=False)
    merge_strategy: Mapped[MergeStrategy] = mapped_column(
        SAEnum(MergeStrategy), default=MergeStrategy.SQUASH, nullable=False
    )
    commits: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    repository: Mapped[Repository] = relationship(back_populates="pull_requests")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )
    checks: Mapped[list["StatusCheck"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )


class Reviewer(Base):
    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE")
    )
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("reviewers.id", ondelete="RESTRICT"))
    state: Mapped[ReviewState] = mapped_column(SAEnum(ReviewState), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    pull_request: Mapped[PullRequest] = relationship(back_populates="reviews")
    reviewer: Mapped[Reviewer] = relationship()


class StatusCheck(Base):
    __tablename__ = "status_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    pull_request: Mapped[PullRequest] = relationship(back_populates="checks")


class BranchProtection(Base):
    __tablename__ = "branch_protection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        unique=True,
    )
    required_reviews: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    require_status_checks: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_conversation_resolution: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    restrict_direct_push: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    restrict_force_push: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    restrict_deletion: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_linear_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="protection")


class RepositoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    default_branch: str = Field(default="main", min_length=1, max_length=100)


class RepositoryRead(RepositoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PullRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=5, max_length=200)
    source_branch: str = Field(min_length=1, max_length=100)
    target_branch: str = Field(min_length=1, max_length=100)
    merge_strategy: MergeStrategy = MergeStrategy.SQUASH
    commits: int = Field(default=1, ge=1)

    @field_validator("source_branch", "target_branch")
    @classmethod
    def validate_branch(cls, value: str) -> str:
        if value.startswith("-") or " " in value:
            raise ValueError("branch name cannot contain spaces or start with '-'")
        return value


class PullRequestRead(PullRequestCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    state: PRState
    created_at: datetime


class ReviewCreate(BaseModel):
    reviewer_id: int
    state: ReviewState
    body: str | None = Field(default=None, max_length=5000)


class ProtectionCreate(BaseModel):
    required_reviews: int = Field(default=1, ge=0, le=20)
    require_status_checks: bool = True
    require_conversation_resolution: bool = True
    restrict_direct_push: bool = True
    restrict_force_push: bool = True
    restrict_deletion: bool = True
    require_linear_history: bool = False


class MergeEligibility(BaseModel):
    eligible: bool
    reasons: list[str]


app = FastAPI(
    title="Repository Governance CRUD API",
    version="1.0.0",
    description=(
        "Production-style API for repositories, Pull Requests, reviews, approvals, "
        "status checks, and branch-protection policies."
    ),
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    # In production, schema changes should be handled by Alembic migrations.
    Base.metadata.create_all(engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/repositories",
    response_model=RepositoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_repository(payload: RepositoryCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(Repository).where(Repository.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="repository already exists")

    repository = Repository(**payload.model_dump())
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


@app.get("/repositories", response_model=list[RepositoryRead])
def list_repositories(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return db.scalars(select(Repository).order_by(Repository.id).limit(limit)).all()


@app.get("/repositories/{repository_id}", response_model=RepositoryRead)
def get_repository(repository_id: int, db: Session = Depends(get_db)):
    repository = db.get(Repository, repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="repository not found")
    return repository


@app.patch("/repositories/{repository_id}", response_model=RepositoryRead)
def update_repository(
    repository_id: int,
    payload: RepositoryCreate,
    db: Session = Depends(get_db),
):
    repository = db.get(Repository, repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="repository not found")

    duplicate = db.scalar(
        select(Repository).where(
            Repository.name == payload.name,
            Repository.id != repository_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="repository name already exists")

    repository.name = payload.name
    repository.default_branch = payload.default_branch
    db.commit()
    db.refresh(repository)
    return repository


@app.delete("/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(repository_id: int, db: Session = Depends(get_db)):
    repository = db.get(Repository, repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="repository not found")

    db.delete(repository)
    db.commit()


@app.post(
    "/repositories/{repository_id}/pull-requests",
    response_model=PullRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_pull_request(
    repository_id: int,
    payload: PullRequestCreate,
    db: Session = Depends(get_db),
):
    repository = db.get(Repository, repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="repository not found")

    if payload.source_branch == payload.target_branch:
        raise HTTPException(
            status_code=422,
            detail="source and target branches must differ",
        )

    pr = PullRequest(
        repository_id=repository_id,
        **payload.model_dump(),
    )
    if payload.title.lower().startswith("[draft]"):
        pr.state = PRState.DRAFT

    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr


@app.get(
    "/repositories/{repository_id}/pull-requests",
    response_model=list[PullRequestRead],
)
def list_pull_requests(
    repository_id: int,
    state_filter: PRState | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not db.get(Repository, repository_id):
        raise HTTPException(status_code=404, detail="repository not found")

    query = select(PullRequest).where(PullRequest.repository_id == repository_id)
    if state_filter:
        query = query.where(PullRequest.state == state_filter)

    return db.scalars(query.order_by(PullRequest.id.desc())).all()


@app.post(
    "/pull-requests/{pull_request_id}/reviews",
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    pull_request_id: int,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
):
    pr = db.get(PullRequest, pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull Request not found")

    reviewer = db.get(Reviewer, payload.reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="reviewer not found")
    if not reviewer.eligible:
        raise HTTPException(status_code=403, detail="reviewer is not eligible")

    if payload.state == ReviewState.APPROVED:
        previous = db.scalars(
            select(Review).where(
                Review.pull_request_id == pull_request_id,
                Review.reviewer_id == payload.reviewer_id,
                Review.state == ReviewState.APPROVED,
                Review.stale.is_(False),
            )
        ).all()
        for review in previous:
            review.stale = True

    review = Review(
        pull_request_id=pull_request_id,
        reviewer_id=payload.reviewer_id,
        state=payload.state,
        body=payload.body,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "id": review.id,
        "pull_request_id": pull_request_id,
        "reviewer": reviewer.username,
        "state": review.state,
        "stale": review.stale,
    }


@app.put("/repositories/{repository_id}/protection")
def configure_branch_protection(
    repository_id: int,
    payload: ProtectionCreate,
    db: Session = Depends(get_db),
):
    repository = db.get(Repository, repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="repository not found")

    protection = repository.protection
    if protection is None:
        protection = BranchProtection(repository_id=repository_id)
        db.add(protection)

    for key, value in payload.model_dump().items():
        setattr(protection, key, value)

    db.commit()
    db.refresh(protection)
    return protection


def evaluate_merge(pr: PullRequest, protection: BranchProtection | None) -> MergeEligibility:
    if protection is None:
        return MergeEligibility(eligible=True, reasons=[])

    reasons: list[str] = []

    if pr.state != PRState.OPEN:
        reasons.append(f"Pull Request is not open: {pr.state.value}")

    if protection.require_status_checks:
        failed = [check.name for check in pr.checks if not check.passed]
        if failed:
            reasons.append("failed status checks: " + ", ".join(failed))
        elif not pr.checks:
            reasons.append("required status checks have not run")

    if protection.required_reviews:
        approvals = {
            review.reviewer_id
            for review in pr.reviews
            if review.state == ReviewState.APPROVED
            and not review.stale
            and review.reviewer.eligible
        }
        changes_requested = any(
            review.state == ReviewState.CHANGES_REQUESTED and not review.stale
            for review in pr.reviews
        )
        if changes_requested:
            reasons.append("an active reviewer requested changes")
        if len(approvals) < protection.required_reviews:
            reasons.append(
                f"{protection.required_reviews} eligible approval(s) required; "
                f"{len(approvals)} currently valid"
            )

    if pr.target_branch == pr.repository.default_branch and pr.commits < 1:
        reasons.append("Pull Request contains no commits")

    return MergeEligibility(eligible=not reasons, reasons=reasons)


@app.get(
    "/pull-requests/{pull_request_id}/merge-eligibility",
    response_model=MergeEligibility,
)
def merge_eligibility(
    pull_request_id: int,
    db: Session = Depends(get_db),
):
    pr = db.get(PullRequest, pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull Request not found")

    return evaluate_merge(pr, pr.repository.protection)


@app.post("/pull-requests/{pull_request_id}/merge")
def merge_pull_request(
    pull_request_id: int,
    db: Session = Depends(get_db),
):
    pr = db.get(PullRequest, pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull Request not found")

    result = evaluate_merge(pr, pr.repository.protection)
    if not result.eligible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "merge blocked", "reasons": result.reasons},
        )

    pr.state = PRState.MERGED
    db.commit()

    return {
        "pull_request_id": pr.id,
        "state": pr.state,
        "merge_strategy": pr.merge_strategy,
    }
