from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable
import hashlib
import json
import re


class PullRequestState(Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(Enum):
    COMMENTED = "commented"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DISMISSED = "dismissed"


class CheckState(Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class User:
    username: str
    team: str
    administrator: bool = False


@dataclass
class Commit:
    sha: str
    author: User
    message: str
    files: tuple[str, ...]


@dataclass
class ReviewComment:
    reviewer: User
    file_path: str
    line: int
    body: str
    resolved: bool = False


@dataclass
class Review:
    reviewer: User
    state: ReviewState
    submitted_commit: str
    comments: list[ReviewComment] = field(default_factory=list)


@dataclass
class StatusCheck:
    name: str
    state: CheckState
    details: str


@dataclass(frozen=True)
class SecurityFinding:
    category: str
    severity: Severity
    endpoint: str
    description: str


@dataclass
class BranchProtection:
    required_approvals: int = 2
    required_checks: tuple[str, ...] = (
        "unit-tests",
        "api-security-scan",
        "authorization-tests",
    )
    require_conversation_resolution: bool = True
    allow_force_push: bool = False
    allow_branch_deletion: bool = False
    require_linear_history: bool = True
    require_code_owner_review: bool = True
    administrators_can_bypass: bool = False


@dataclass
class Branch:
    name: str
    protected: bool
    head_sha: str


@dataclass
class PullRequest:
    number: int
    title: str
    author: User
    source_branch: str
    target_branch: str
    base_sha: str
    head_sha: str
    state: PullRequestState = PullRequestState.OPEN
    draft: bool = False
    commits: list[Commit] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    checks: list[StatusCheck] = field(default_factory=list)
    findings: list[SecurityFinding] = field(default_factory=list)
    comments: list[ReviewComment] = field(default_factory=list)
    merge_commit_sha: str | None = None
    reopened_count: int = 0


class SecurityPolicy:
    """Repository policy for API security changes."""

    HIGH_RISK_CATEGORIES = {
        "broken_authorization",
        "excessive_data_exposure",
        "injection",
        "ssrf",
        "security_misconfiguration",
    }

    def evaluate(self, findings: Iterable[SecurityFinding]) -> list[str]:
        failures: list[str] = []

        for finding in findings:
            if finding.category not in self.HIGH_RISK_CATEGORIES:
                failures.append(
                    f"Unknown security category: {finding.category}"
                )
            if finding.severity in {Severity.HIGH, Severity.CRITICAL}:
                failures.append(
                    f"{finding.severity.value} finding: "
                    f"{finding.category} at {finding.endpoint}"
                )

        return failures


class MergeEligibility:
    def __init__(
        self,
        protection: BranchProtection,
        security_policy: SecurityPolicy,
        code_owners: dict[str, set[str]],
    ) -> None:
        self.protection = protection
        self.security_policy = security_policy
        self.code_owners = code_owners

    def evaluate(
        self,
        pr: PullRequest,
        target: Branch,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if pr.state != PullRequestState.OPEN:
            reasons.append(f"Pull Request is {pr.state.value}.")

        if pr.draft:
            reasons.append("Draft Pull Requests cannot be merged.")

        if target.protected:
            if not self.protection.allow_force_push and not target.name:
                reasons.append("Invalid protected branch state.")

            if target.head_sha != pr.base_sha:
                reasons.append(
                    "Pull Request base is stale relative to the target branch."
                )

            passed_checks = {
                check.name
                for check in pr.checks
                if check.state == CheckState.PASSED
            }

            for required in self.protection.required_checks:
                if required not in passed_checks:
                    reasons.append(f"Required check is not passing: {required}")

            unresolved = [
                comment
                for comment in pr.comments
                if not comment.resolved
            ]
            if self.protection.require_conversation_resolution and unresolved:
                reasons.append(
                    f"{len(unresolved)} review conversation(s) remain unresolved."
                )

            security_failures = self.security_policy.evaluate(pr.findings)
            reasons.extend(security_failures)

            approvals = self._eligible_approvals(pr)
            if len(approvals) < self.protection.required_approvals:
                reasons.append(
                    f"Only {len(approvals)} eligible approval(s); "
                    f"{self.protection.required_approvals} required."
                )

            if self.protection.require_code_owner_review:
                if not self._has_code_owner_approval(pr):
                    reasons.append("Required code-owner approval is missing.")

        return not reasons, reasons

    def _eligible_approvals(self, pr: PullRequest) -> set[str]:
        """Only the latest review from each reviewer counts."""
        latest: dict[str, Review] = {}

        for review in pr.reviews:
            if review.reviewer.username == pr.author.username:
                continue
            if review.state == ReviewState.DISMISSED:
                latest.pop(review.reviewer.username, None)
                continue
            latest[review.reviewer.username] = review

        return {
            username
            for username, review in latest.items()
            if review.state == ReviewState.APPROVED
            and review.submitted_commit == pr.head_sha
        }

    def _has_code_owner_approval(self, pr: PullRequest) -> bool:
        touched_files = {
            path
            for commit in pr.commits
            for path in commit.files
        }

        required_users: set[str] = set()
        for pattern, owners in self.code_owners.items():
            regex = re.compile(pattern)
            if any(regex.search(path) for path in touched_files):
                required_users.update(owners)

        approved = self._eligible_approvals(pr)
        return bool(required_users & approved)


class Repository:
    def __init__(self, name: str, default_branch: str = "main") -> None:
        self.name = name
        self.default_branch = default_branch
        self.users: dict[str, User] = {}
        self.branches: dict[str, Branch] = {}
        self.pull_requests: dict[int, PullRequest] = {}
        self.next_pr_number = 1
        self.protection = BranchProtection()
        self.security_policy = SecurityPolicy()
        self.code_owners: dict[str, set[str]] = {
            r"(^|/)auth/": {"security-lead"},
            r"(^|/)api/": {"security-lead"},
        }

    def add_user(self, user: User) -> None:
        if user.username in self.users:
            raise ValueError(f"User already exists: {user.username}")
        self.users[user.username] = user

    def add_branch(self, name: str, head_sha: str, protected: bool = False) -> None:
        if name in self.branches:
            raise ValueError(f"Branch already exists: {name}")
        self.branches[name] = Branch(name, protected, head_sha)

    def create_pull_request(
        self,
        author: User,
        title: str,
        source_branch: str,
        target_branch: str,
        draft: bool = False,
    ) -> PullRequest:
        if source_branch not in self.branches:
            raise ValueError("Source branch does not exist.")
        if target_branch not in self.branches:
            raise ValueError("Target branch does not exist.")
        if source_branch == target_branch:
            raise ValueError("Source and target branches must differ.")

        target = self.branches[target_branch]
        source = self.branches[source_branch]

        pr = PullRequest(
            number=self.next_pr_number,
            title=title,
            author=author,
            source_branch=source_branch,
            target_branch=target_branch,
            base_sha=target.head_sha,
            head_sha=source.head_sha,
            draft=draft,
            state=PullRequestState.DRAFT if draft else PullRequestState.OPEN,
        )

        self.pull_requests[pr.number] = pr
        self.next_pr_number += 1
        return pr

    def add_commit(
        self,
        pr: PullRequest,
        author: User,
        message: str,
        files: list[str],
    ) -> Commit:
        if pr.state not in {PullRequestState.OPEN, PullRequestState.DRAFT}:
            raise ValueError("Cannot add commits to a closed or merged PR.")
        if not files:
            raise ValueError("A commit must change at least one file.")

        payload = f"{author.username}|{message}|{','.join(files)}|{pr.head_sha}"
        sha = hashlib.sha1(payload.encode()).hexdigest()[:12]

        commit = Commit(
            sha=sha,
            author=author,
            message=message,
            files=tuple(files),
        )
        pr.commits.append(commit)
        pr.head_sha = sha
        self.branches[pr.source_branch].head_sha = sha

        # New commits invalidate previous approvals.
        for review in pr.reviews:
            if review.state == ReviewState.APPROVED:
                review.state = ReviewState.DISMISSED

        return commit

    def synchronize(self, pr: PullRequest) -> None:
        target = self.branches[pr.target_branch]
        pr.base_sha = target.head_sha

    def reopen(self, pr: PullRequest) -> None:
        if pr.state != PullRequestState.CLOSED:
            raise ValueError("Only closed Pull Requests can be reopened.")
        pr.state = PullRequestState.OPEN
        pr.reopened_count += 1

    def close(self, pr: PullRequest) -> None:
        if pr.state == PullRequestState.MERGED:
            raise ValueError("A merged Pull Request cannot be closed.")
        pr.state = PullRequestState.CLOSED

    def add_review(
        self,
        pr: PullRequest,
        reviewer: User,
        state: ReviewState,
        body: str,
        file_path: str | None = None,
        line: int | None = None,
    ) -> Review:
        if pr.state != PullRequestState.OPEN:
            raise ValueError("Reviews require an open Pull Request.")
        if reviewer.username == pr.author.username:
            raise ValueError("Self-approval is not permitted.")

        review = Review(
            reviewer=reviewer,
            state=state,
            submitted_commit=pr.head_sha,
        )

        if body:
            comment = ReviewComment(
                reviewer=reviewer,
                file_path=file_path or "",
                line=line or 0,
                body=body,
            )
            review.comments.append(comment)
            pr.comments.append(comment)

        pr.reviews.append(review)
        return review

    def add_check(
        self,
        pr: PullRequest,
        name: str,
        state: CheckState,
        details: str,
    ) -> None:
        pr.checks = [
            check for check in pr.checks
            if check.name != name
        ]
        pr.checks.append(StatusCheck(name, state, details))

    def add_security_finding(
        self,
        pr: PullRequest,
        category: str,
        severity: Severity,
        endpoint: str,
        description: str,
    ) -> None:
        pr.findings.append(
            SecurityFinding(
                category=category,
                severity=severity,
                endpoint=endpoint,
                description=description,
            )
        )

    def resolve_comment(
        self,
        pr: PullRequest,
        reviewer: User,
        file_path: str,
        line: int,
    ) -> None:
        for comment in pr.comments:
            if (
                comment.reviewer.username == reviewer.username
                and comment.file_path == file_path
                and comment.line == line
            ):
                comment.resolved = True
                return
        raise ValueError("Review conversation was not found.")

    def merge(self, pr: PullRequest) -> str:
        target = self.branches[pr.target_branch]
        evaluator = MergeEligibility(
            self.protection,
            self.security_policy,
            self.code_owners,
        )

        eligible, reasons = evaluator.evaluate(pr, target)
        if not eligible:
            raise RuntimeError(
                "Merge blocked:\n- " + "\n- ".join(reasons)
            )

        merge_payload = (
            f"{pr.number}|{pr.head_sha}|{target.head_sha}|"
            f"{self.name}"
        )
        merge_sha = hashlib.sha1(
            merge_payload.encode()
        ).hexdigest()[:12]

        target.head_sha = merge_sha
        pr.merge_commit_sha = merge_sha
        pr.state = PullRequestState.MERGED
        return merge_sha


def demonstrate_api_security_review() -> None:
    repository = Repository("secure-api-platform")

    developer = User("developer", "backend")
    security_lead = User("security-lead", "security")
    reviewer = User("reviewer", "backend")

    for user in (developer, security_lead, reviewer):
        repository.add_user(user)

    repository.add_branch("main", "main000001", protected=True)
    repository.add_branch("feature/api-authorization", "feature00001")

    pr = repository.create_pull_request(
        author=developer,
        title="Harden API authorization and SSRF validation",
        source_branch="feature/api-authorization",
        target_branch="main",
    )

    repository.add_commit(
        pr,
        developer,
        "Enforce object ownership and outbound URL policy",
        [
            "api/orders.py",
            "api/client.py",
            "auth/policy.py",
            "tests/test_authorization.py",
        ],
    )

    repository.add_security_finding(
        pr,
        "broken_authorization",
        Severity.LOW,
        "GET /api/orders/{id}",
        "Ownership check is enforced before returning the object.",
    )

    # The finding above documents the security area without making it a
    # blocking vulnerability. A high-severity finding would block the PR.
    repository.add_check(
        pr,
        "unit-tests",
        CheckState.PASSED,
        "412 tests passed.",
    )
    repository.add_check(
        pr,
        "api-security-scan",
        CheckState.PASSED,
        "No blocking API vulnerabilities detected.",
    )
    repository.add_check(
        pr,
        "authorization-tests",
        CheckState.PASSED,
        "Cross-tenant access tests passed.",
    )

    repository.add_review(
        pr,
        reviewer,
        ReviewState.APPROVED,
        "Authorization boundaries and response filtering reviewed.",
    )

    repository.add_review(
        pr,
        security_lead,
        ReviewState.APPROVED,
        "Security policy and SSRF controls reviewed.",
    )

    # Demonstrate that an unresolved discussion blocks merging.
    comment = repository.add_review(
        pr,
        security_lead,
        ReviewState.COMMENTED,
        "Verify the outbound hostname after DNS resolution.",
        "api/client.py",
        88,
    )

    try:
        repository.merge(pr)
    except RuntimeError as exc:
        print("Expected merge block:")
        print(exc)
        repository.resolve_comment(
            pr,
            security_lead,
            "api/client.py",
            88,
        )

    merge_sha = repository.merge(pr)

    print("\nMerged Pull Request")
    print(f"PR: #{pr.number}")
    print(f"State: {pr.state.value}")
    print(f"Merge commit: {merge_sha}")

    # Demonstrate stale approval behavior.
    repository.add_branch(
        "feature/exposure-fix",
        "feature00002",
    )
    second_pr = repository.create_pull_request(
        author=developer,
        title="Reduce API response exposure",
        source_branch="feature/exposure-fix",
        target_branch="main",
    )

    repository.add_commit(
        second_pr,
        developer,
        "Return only fields required by the mobile client",
        ["api/orders.py"],
    )

    for name in repository.protection.required_checks:
        repository.add_check(
            second_pr,
            name,
            CheckState.PASSED,
            "Passed.",
        )

    repository.add_review(
        second_pr,
        security_lead,
        ReviewState.APPROVED,
        "Response schema reviewed.",
    )
    repository.add_review(
        second_pr,
        reviewer,
        ReviewState.APPROVED,
        "API contract reviewed.",
    )

    # A new commit changes the reviewed commit SHA and dismisses approvals.
    repository.add_commit(
        second_pr,
        developer,
        "Refine response serialization",
        ["api/orders.py"],
    )

    try:
        repository.merge(second_pr)
    except RuntimeError as exc:
        print("\nExpected stale-approval block:")
        print(exc)

    # A fresh review restores eligibility.
    repository.add_review(
        second_pr,
        security_lead,
        ReviewState.APPROVED,
        "Re-reviewed after the latest commit.",
    )
    repository.add_review(
        second_pr,
        reviewer,
        ReviewState.APPROVED,
        "Re-reviewed response changes.",
    )

    merge_sha = repository.merge(second_pr)
    print("\nSecond Pull Request merged:")
    print(merge_sha)

    report = {
        "repository": repository.name,
        "merged_pull_requests": [
            number
            for number, item in repository.pull_requests.items()
            if item.state == PullRequestState.MERGED
        ],
        "protected_branch": repository.default_branch,
        "required_approvals": repository.protection.required_approvals,
        "required_checks": list(repository.protection.required_checks),
        "security_categories": sorted(
            SecurityPolicy.HIGH_RISK_CATEGORIES
        ),
    }

    print("\nRepository governance report:")
    print(json.dumps(report, indent=2))


def validation_examples() -> None:
    repository = Repository("validation-demo")
    user = User("user", "backend")

    repository.add_user(user)
    repository.add_branch("main", "main123", protected=True)
    repository.add_branch("feature", "feature123")

    try:
        repository.create_pull_request(
            user,
            "Invalid",
            "missing",
            "main",
        )
    except ValueError as exc:
        print("\nValidation example:", exc)

    try:
        repository.add_branch("main", "duplicate")
    except ValueError as exc:
        print("Validation example:", exc)


if __name__ == "__main__":
    demonstrate_api_security_review()
    validation_examples()
