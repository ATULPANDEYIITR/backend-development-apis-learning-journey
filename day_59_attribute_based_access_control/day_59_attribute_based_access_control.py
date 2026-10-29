from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable
from datetime import datetime, timezone
import ipaddress
import re


class Effect(Enum):
    ALLOW = "allow"
    DENY = "deny"


class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyConflictError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


@dataclass(frozen=True)
class User:
    user_id: str
    department: str
    roles: frozenset[str]
    clearance: int
    active: bool = True


@dataclass(frozen=True)
class Resource:
    resource_id: str
    resource_type: str
    owner_department: str
    classification: int


@dataclass(frozen=True)
class RequestContext:
    user: User
    resource: Resource
    action: str
    ip_address: str
    device_trusted: bool
    mfa_verified: bool
    country: str
    hour_utc: int
    environment: str = "production"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Condition:
    attribute: str
    operator: str
    expected: Any

    def evaluate(self, context: RequestContext) -> bool:
        actual = resolve_attribute(context, self.attribute)

        if self.operator == "equals":
            return actual == self.expected
        if self.operator == "not_equals":
            return actual != self.expected
        if self.operator == "in":
            return actual in self.expected
        if self.operator == "contains":
            return self.expected in actual
        if self.operator == "gte":
            return actual >= self.expected
        if self.operator == "lte":
            return actual <= self.expected
        if self.operator == "regex":
            return bool(re.fullmatch(str(self.expected), str(actual)))
        if self.operator == "cidr":
            return ipaddress.ip_address(str(actual)) in ipaddress.ip_network(
                str(self.expected), strict=False
            )

        raise InvalidRequestError(f"Unsupported operator: {self.operator}")


@dataclass(frozen=True)
class Policy:
    policy_id: str
    name: str
    effect: Effect
    priority: int
    actions: frozenset[str]
    resource_types: frozenset[str]
    conditions: tuple[Condition, ...]
    enabled: bool = True

    def matches(self, context: RequestContext) -> bool:
        if not self.enabled:
            return False

        if context.action not in self.actions and "*" not in self.actions:
            return False

        if (
            context.resource.resource_type not in self.resource_types
            and "*" not in self.resource_types
        ):
            return False

        return all(condition.evaluate(context) for condition in self.conditions)


def resolve_attribute(context: RequestContext, path: str) -> Any:
    if path.startswith("user."):
        value = getattr(context.user, path[5:], None)
    elif path.startswith("resource."):
        value = getattr(context.resource, path[9:], None)
    elif path.startswith("request."):
        value = getattr(context, path[8:], None)
    else:
        value = context.attributes.get(path)

    if value is None:
        raise InvalidRequestError(f"Unknown or missing attribute: {path}")

    return value


@dataclass
class AuditEvent:
    timestamp: str
    user_id: str
    resource_id: str
    action: str
    decision: Decision
    matched_policies: list[str]
    reason: str


class AuthorizationEngine:
    def __init__(self, policies: Iterable[Policy]) -> None:
        self.policies = list(policies)
        self.audit_log: list[AuditEvent] = []

    def authorize(self, context: RequestContext) -> Decision:
        self._validate_context(context)

        matched = [
            policy for policy in self.policies
            if policy.matches(context)
        ]

        matched.sort(key=lambda p: p.priority, reverse=True)

        if not context.user.active:
            return self._record(
                context,
                Decision.DENY,
                matched,
                "Inactive user",
            )

        explicit_denies = [p for p in matched if p.effect == Effect.DENY]
        allows = [p for p in matched if p.effect == Effect.ALLOW]

        if explicit_denies:
            return self._record(
                context,
                Decision.DENY,
                matched,
                "Explicit deny policy matched",
            )

        if not allows:
            return self._record(
                context,
                Decision.DENY,
                matched,
                "Default deny: no allow policy matched",
            )

        highest_priority = allows[0].priority
        highest_allows = [
            p for p in allows if p.priority == highest_priority
        ]

        if len(highest_allows) > 1:
            signatures = {
                p.effect.value for p in highest_allows
            }
            if len(signatures) > 1:
                raise PolicyConflictError(
                    "Conflicting policies at identical priority"
                )

        return self._record(
            context,
            Decision.ALLOW,
            matched,
            "Highest-priority applicable allow policy matched",
        )

    def _validate_context(self, context: RequestContext) -> None:
        if not 0 <= context.hour_utc <= 23:
            raise InvalidRequestError("hour_utc must be between 0 and 23")

        try:
            ipaddress.ip_address(context.ip_address)
        except ValueError as exc:
            raise InvalidRequestError("Invalid IP address") from exc

        if not context.user.user_id:
            raise InvalidRequestError("Missing user identifier")

        if not context.resource.resource_id:
            raise InvalidRequestError("Missing resource identifier")

        if not context.action:
            raise InvalidRequestError("Missing action")

    def _record(
        self,
        context: RequestContext,
        decision: Decision,
        matched: list[Policy],
        reason: str,
    ) -> Decision:
        self.audit_log.append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                user_id=context.user.user_id,
                resource_id=context.resource.resource_id,
                action=context.action,
                decision=decision,
                matched_policies=[p.policy_id for p in matched],
                reason=reason,
            )
        )
        return decision


def build_policies() -> list[Policy]:
    return [
        Policy(
            policy_id="P001",
            name="Analysts may read internal reports",
            effect=Effect.ALLOW,
            priority=50,
            actions=frozenset({"read"}),
            resource_types=frozenset({"report"}),
            conditions=(
                Condition("user.roles", "contains", "analyst"),
                Condition("resource.classification", "lte", 2),
                Condition("request.device_trusted", "equals", True),
            ),
        ),
        Policy(
            policy_id="P002",
            name="Managers may read confidential reports with MFA",
            effect=Effect.ALLOW,
            priority=70,
            actions=frozenset({"read"}),
            resource_types=frozenset({"report"}),
            conditions=(
                Condition("user.roles", "contains", "manager"),
                Condition("resource.classification", "lte", 4),
                Condition("request.mfa_verified", "equals", True),
                Condition("request.device_trusted", "equals", True),
            ),
        ),
        Policy(
            policy_id="P003",
            name="Block external network access to restricted resources",
            effect=Effect.DENY,
            priority=100,
            actions=frozenset({"read", "write", "delete"}),
            resource_types=frozenset({"report", "database"}),
            conditions=(
                Condition("resource.classification", "gte", 4),
                Condition("request.ip_address", "cidr", "10.0.0.0/8"),
                Condition("request.device_trusted", "equals", False),
            ),
        ),
        Policy(
            policy_id="P004",
            name="Security team may administer databases",
            effect=Effect.ALLOW,
            priority=90,
            actions=frozenset({"read", "write", "delete"}),
            resource_types=frozenset({"database"}),
            conditions=(
                Condition("user.department", "equals", "security"),
                Condition("user.roles", "contains", "administrator"),
                Condition("request.mfa_verified", "equals", True),
                Condition("request.environment", "equals", "production"),
            ),
        ),
        Policy(
            policy_id="P005",
            name="Temporary emergency access",
            effect=Effect.ALLOW,
            priority=80,
            actions=frozenset({"read"}),
            resource_types=frozenset({"report"}),
            conditions=(
                Condition("user.roles", "contains", "incident_responder"),
                Condition("request.mfa_verified", "equals", True),
                Condition("request.attributes.emergency_ticket", "regex", r"INC-[0-9]{6}"),
            ),
        ),
    ]


def make_context(
    user: User,
    resource: Resource,
    action: str,
    *,
    ip: str = "10.20.30.40",
    trusted: bool = True,
    mfa: bool = True,
    country: str = "IN",
    hour: int = 10,
    environment: str = "production",
    attributes: dict[str, Any] | None = None,
) -> RequestContext:
    return RequestContext(
        user=user,
        resource=resource,
        action=action,
        ip_address=ip,
        device_trusted=trusted,
        mfa_verified=mfa,
        country=country,
        hour_utc=hour,
        environment=environment,
        attributes=attributes or {},
    )


def run_demo() -> None:
    analyst = User(
        user_id="U100",
        department="analytics",
        roles=frozenset({"employee", "analyst"}),
        clearance=2,
    )

    manager = User(
        user_id="U200",
        department="operations",
        roles=frozenset({"employee", "manager"}),
        clearance=4,
    )

    security_admin = User(
        user_id="U300",
        department="security",
        roles=frozenset({"employee", "administrator"}),
        clearance=5,
    )

    responder = User(
        user_id="U400",
        department="security",
        roles=frozenset({"employee", "incident_responder"}),
        clearance=5,
    )

    inactive = User(
        user_id="U500",
        department="analytics",
        roles=frozenset({"analyst"}),
        clearance=2,
        active=False,
    )

    public_report = Resource(
        resource_id="R100",
        resource_type="report",
        owner_department="analytics",
        classification=2,
    )

    confidential_report = Resource(
        resource_id="R200",
        resource_type="report",
        owner_department="security",
        classification=4,
    )

    database = Resource(
        resource_id="DB100",
        resource_type="database",
        owner_department="security",
        classification=5,
    )

    engine = AuthorizationEngine(build_policies())

    requests = [
        (
            "Analyst on trusted device",
            make_context(analyst, public_report, "read", mfa=False),
        ),
        (
            "Manager reading confidential report",
            make_context(manager, confidential_report, "read"),
        ),
        (
            "Manager without MFA",
            make_context(
                manager,
                confidential_report,
                "read",
                mfa=False,
            ),
        ),
        (
            "Security administrator deleting database",
            make_context(security_admin, database, "delete"),
        ),
        (
            "Untrusted device accessing restricted database",
            make_context(
                security_admin,
                database,
                "read",
                ip="10.1.2.3",
                trusted=False,
            ),
        ),
        (
            "Emergency responder with ticket",
            make_context(
                responder,
                confidential_report,
                "read",
                attributes={"request.attributes.emergency_ticket": "INC-123456"},
            ),
        ),
        (
            "Emergency responder with malformed ticket",
            make_context(
                responder,
                confidential_report,
                "read",
                attributes={"request.attributes.emergency_ticket": "BAD-123"},
            ),
        ),
        (
            "Inactive analyst",
            make_context(inactive, public_report, "read"),
        ),
    ]

    for description, request in requests:
        try:
            decision = engine.authorize(request)
            print(f"{description}: {decision.value}")
        except (InvalidRequestError, PolicyConflictError) as exc:
            print(f"{description}: ERROR: {exc}")

    print("\nAudit log:")
    for event in engine.audit_log:
        print(
            f"{event.timestamp} | "
            f"user={event.user_id} | "
            f"resource={event.resource_id} | "
            f"action={event.action} | "
            f"decision={event.decision.value} | "
            f"policies={event.matched_policies} | "
            f"{event.reason}"
        )


def run_assertions() -> None:
    engine = AuthorizationEngine(build_policies())

    analyst = User(
        "TEST1",
        "analytics",
        frozenset({"analyst"}),
        2,
    )
    report = Resource("TEST-R", "report", "analytics", 2)

    allowed = engine.authorize(
        make_context(analyst, report, "read")
    )
    assert allowed == Decision.ALLOW

    denied = engine.authorize(
        make_context(analyst, report, "delete")
    )
    assert denied == Decision.DENY

    try:
        engine.authorize(
            make_context(
                analyst,
                report,
                "read",
                ip="not-an-ip",
            )
        )
    except InvalidRequestError:
        pass
    else:
        raise AssertionError("Invalid IP should be rejected")


if __name__ == "__main__":
    run_assertions()
    run_demo()
