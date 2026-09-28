"""
API VERSIONING: URL VERSIONING, HEADER VERSIONING, BACKWARD COMPATIBILITY,
AND DEPRECATION STRATEGY

A standalone study program that progresses from fundamentals to advanced
API-versioning design.

Run:
    python api_versioning.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple
import copy
import json
import re
import time
import unittest


# ============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# ============================================================================

def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_subsection(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


print_section("API VERSIONING FUNDAMENTALS")

print(
    """
API versioning is the practice of allowing an API to evolve while controlling
the impact of changes on existing consumers.

A version is a compatibility contract. For example:

    /api/v1/users
    /api/v2/users

or:

    Accept: application/vnd.example.user+json;version=2

Important terms:

- Consumer/client:
    An application that calls the API.

- Provider/server:
    The application exposing the API.

- Contract:
    The externally observable request and response behavior.

- Breaking change:
    A change that can cause an existing valid client to fail or behave
    incorrectly.

- Backward compatibility:
    A newer server continues to correctly serve older clients.

- Deprecation:
    A formal statement that an API feature remains available but should
    no longer be used.

- Retirement/sunset:
    The point at which a deprecated version is no longer served.

- Version negotiation:
    The mechanism used to determine which API representation or contract
    the client requests.

A useful distinction:

    Versioning answers: "Which contract does this request target?"
    Compatibility answers: "Can old consumers continue to work?"
    Deprecation answers: "How do consumers move away from an old contract?"
"""
)


# ============================================================================
# 2. SEMANTIC VERSION REPRESENTATION
# ============================================================================

@dataclass(frozen=True, order=True)
class ApiVersion:
    """Small immutable representation of a major API version."""

    major: int

    def __post_init__(self) -> None:
        if self.major < 1:
            raise ValueError("API major version must be positive.")

    def __str__(self) -> str:
        return f"v{self.major}"


print_subsection("Version Representation")

versions = [ApiVersion(1), ApiVersion(2), ApiVersion(3)]
for version in versions:
    print("Version:", version)

print("v1 < v2:", ApiVersion(1) < ApiVersion(2))


# ============================================================================
# 3. URL VERSIONING
# ============================================================================

class VersioningError(Exception):
    """Base exception for API-versioning errors."""


class UnsupportedVersionError(VersioningError):
    """Raised when the requested API version is unsupported."""


class InvalidVersionError(VersioningError):
    """Raised when a version value is malformed."""


URL_VERSION_PATTERN = re.compile(r"^/api/v(?P<major>[1-9][0-9]*)/(?P<resource>[a-zA-Z0-9_-]+)$")


def parse_url_version(path: str) -> Tuple[ApiVersion, str]:
    """
    Extract the version and resource from a URL.

    Examples:
        /api/v1/users -> (v1, users)
        /api/v2/orders -> (v2, orders)

    Invalid paths are rejected instead of silently assuming a default.
    """
    match = URL_VERSION_PATTERN.fullmatch(path.rstrip("/"))
    if not match:
        raise InvalidVersionError(f"Invalid versioned API path: {path}")

    return ApiVersion(int(match.group("major"))), match.group("resource")


print_subsection("URL Versioning")

for path in ["/api/v1/users", "/api/v2/users", "/api/v10/orders"]:
    version, resource = parse_url_version(path)
    print(f"{path} -> version={version}, resource={resource}")

try:
    parse_url_version("/api/users")
except InvalidVersionError as exc:
    print("Rejected:", exc)


# ============================================================================
# 4. HEADER VERSIONING
# ============================================================================

def parse_version_header(headers: Mapping[str, str]) -> ApiVersion:
    """
    Parse a simple custom version header.

    Example:
        API-Version: 2

    A real production API might instead use:
        Accept: application/vnd.company.resource+json;version=2

    Explicit validation prevents malformed version strings from becoming
    accidental routing behavior.
    """
    raw_value = headers.get("API-Version")

    if raw_value is None:
        raise InvalidVersionError("API-Version header is required.")

    if not raw_value.isdigit():
        raise InvalidVersionError("API-Version must contain an integer.")

    return ApiVersion(int(raw_value))


print_subsection("Header Versioning")

request_headers = {"API-Version": "2", "Accept": "application/json"}
print("Requested version:", parse_version_header(request_headers))

try:
    parse_version_header({"API-Version": "abc"})
except InvalidVersionError as exc:
    print("Rejected:", exc)


# ============================================================================
# 5. MEDIA-TYPE / ACCEPT HEADER VERSIONING
# ============================================================================

MEDIA_TYPE_PATTERN = re.compile(
    r"application/vnd\.(?P<vendor>[a-z0-9.-]+)\.(?P<resource>[a-z0-9.-]+)"
    r"\+json\s*;\s*version=(?P<version>[1-9][0-9]*)",
    re.IGNORECASE,
)


def parse_accept_version(accept_header: str) -> ApiVersion:
    """Extract an explicit version from a vendor media type."""
    match = MEDIA_TYPE_PATTERN.search(accept_header)

    if not match:
        raise InvalidVersionError(
            "Accept header does not contain a supported vendor version."
        )

    return ApiVersion(int(match.group("version")))


print_subsection("Media-Type Versioning")

accept = "application/vnd.example.user+json;version=2"
print("Requested version:", parse_accept_version(accept))


# ============================================================================
# 6. COMPARING VERSIONING STRATEGIES
# ============================================================================

versioning_strategies = {
    "URL": {
        "example": "/api/v2/users",
        "visibility": "High",
        "routing": "Simple",
        "cache_behavior": "Straightforward because URL changes",
        "main_tradeoff": "Version becomes part of resource URL",
    },
    "Custom header": {
        "example": "API-Version: 2",
        "visibility": "Medium",
        "routing": "Simple with infrastructure support",
        "cache_behavior": "Caches must vary on the header",
        "main_tradeoff": "Less visible and easier to overlook",
    },
    "Media type": {
        "example": "Accept: application/vnd.example.user+json;version=2",
        "visibility": "Medium",
        "routing": "Requires content-negotiation logic",
        "cache_behavior": "Caches must correctly account for Accept",
        "main_tradeoff": "More expressive but more complex",
    },
}

for strategy, details in versioning_strategies.items():
    print(f"\n{strategy} versioning:")
    for key, value in details.items():
        print(f"  {key}: {value}")


# ============================================================================
# 7. REQUEST AND RESPONSE MODELS
# ============================================================================

@dataclass
class ApiRequest:
    method: str
    path: str
    headers: Dict[str, str]
    body: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApiResponse:
    status_code: int
    body: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# 8. USER DATA AND VERSIONED REPRESENTATIONS
# ============================================================================

@dataclass(frozen=True)
class User:
    user_id: int
    name: str
    email: str
    phone: Optional[str]
    active: bool
    created_at: str


def serialize_user_v1(user: User) -> Dict[str, Any]:
    """
    Version 1 contract.

    V1 exposes "name", "email", and "active". New internal fields do not
    automatically leak into an old representation.
    """
    return {
        "id": user.user_id,
        "name": user.name,
        "email": user.email,
        "active": user.active,
    }


def serialize_user_v2(user: User) -> Dict[str, Any]:
    """
    Version 2 contract.

    V2 separates the person's name into first_name and last_name and
    introduces phone.
    """
    name_parts = user.name.split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) == 2 else ""

    return {
        "id": user.user_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.active,
    }


def serialize_user_v3(user: User) -> Dict[str, Any]:
    """
    Version 3 demonstrates another evolution: a nested identity object.

    The internal User model stays stable while representations evolve.
    """
    name_parts = user.name.split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) == 2 else ""

    return {
        "id": user.user_id,
        "identity": {
            "firstName": first_name,
            "lastName": last_name,
        },
        "contact": {
            "email": user.email,
            "phone": user.phone,
        },
        "status": "active" if user.active else "inactive",
        "createdAt": user.created_at,
    }


USER = User(
    user_id=101,
    name="Atul Pandey",
    email="atul@example.com",
    phone="+91-9000000000",
    active=True,
    created_at="2026-01-15T10:00:00Z",
)

print_subsection("Versioned Representations")

print("V1:", json.dumps(serialize_user_v1(USER), indent=2))
print("V2:", json.dumps(serialize_user_v2(USER), indent=2))
print("V3:", json.dumps(serialize_user_v3(USER), indent=2))


# ============================================================================
# 9. BREAKING VS NON-BREAKING CHANGES
# ============================================================================

def classify_change(description: str, breaking: bool) -> str:
    """Represent a documented compatibility decision."""
    return f"{description}: {'BREAKING' if breaking else 'NON-BREAKING'}"


print_subsection("Breaking and Non-Breaking Changes")

changes = [
    classify_change("Add an optional response field", False),
    classify_change("Add an optional request field", False),
    classify_change("Add a new endpoint", False),
    classify_change("Rename response field 'name' to 'full_name'", True),
    classify_change("Change integer ID to incompatible object shape", True),
    classify_change("Make a previously optional request field mandatory", True),
    classify_change("Change meaning of an existing field", True),
    classify_change("Remove an existing endpoint", True),
]

for change in changes:
    print(change)


# ============================================================================
# 10. COMPATIBILITY RULES
# ============================================================================

def is_backward_compatible_response(
    old_payload: Mapping[str, Any],
    new_payload: Mapping[str, Any],
    required_old_fields: Iterable[str],
) -> bool:
    """
    A deliberately conservative compatibility check.

    Adding fields can usually be compatible with tolerant readers.
    Removing or renaming required fields is not.
    """
    return all(field_name in new_payload for field_name in required_old_fields)


print_subsection("Backward Compatibility Check")

old_contract_fields = {"id", "name", "email", "active"}

compatible_payload = {
    "id": 101,
    "name": "Atul Pandey",
    "email": "atul@example.com",
    "active": True,
    "phone": "+91-9000000000",
}

incompatible_payload = {
    "id": 101,
    "full_name": "Atul Pandey",
    "email": "atul@example.com",
    "active": True,
}

print(
    "Added field:",
    is_backward_compatible_response(
        old_contract_fields,
        compatible_payload,
        old_contract_fields,
    ),
)

print(
    "Renamed required field:",
    is_backward_compatible_response(
        old_contract_fields,
        incompatible_payload,
        old_contract_fields,
    ),
)


# ============================================================================
# 11. VERSION ROUTER
# ============================================================================

Serializer = Callable[[User], Dict[str, Any]]


class VersionRouter:
    """Routes a request to the correct representation implementation."""

    def __init__(self, serializers: Mapping[int, Serializer]):
        self._serializers = dict(serializers)

    def supported_versions(self) -> List[int]:
        return sorted(self._serializers)

    def serialize(self, version: ApiVersion, user: User) -> Dict[str, Any]:
        serializer = self._serializers.get(version.major)

        if serializer is None:
            raise UnsupportedVersionError(
                f"Unsupported API version: {version}"
            )

        return serializer(user)


router = VersionRouter(
    {
        1: serialize_user_v1,
        2: serialize_user_v2,
        3: serialize_user_v3,
    }
)

print_subsection("Version Router")
print("Supported versions:", router.supported_versions())
print("V2 response:", router.serialize(ApiVersion(2), USER))

try:
    router.serialize(ApiVersion(4), USER)
except UnsupportedVersionError as exc:
    print("Rejected:", exc)


# ============================================================================
# 12. URL-BASED REQUEST DISPATCH
# ============================================================================

def handle_url_versioned_request(request: ApiRequest, user: User) -> ApiResponse:
    """Dispatch using the version embedded in the URL."""
    try:
        version, resource = parse_url_version(request.path)
    except InvalidVersionError as exc:
        return ApiResponse(400, {"error": str(exc)})

    if request.method != "GET" or resource != "users":
        return ApiResponse(
            404,
            {"error": "Only GET /api/vN/users is implemented."},
        )

    try:
        payload = router.serialize(version, user)
    except UnsupportedVersionError as exc:
        return ApiResponse(
            400,
            {"error": str(exc)},
            {
                "Supported-Versions": ", ".join(
                    f"v{item}" for item in router.supported_versions()
                )
            },
        )

    return ApiResponse(
        200,
        payload,
        {
            "Content-Type": "application/json",
            "API-Version": str(version),
        },
    )


print_subsection("URL-Versioned Request")

response = handle_url_versioned_request(
    ApiRequest("GET", "/api/v2/users", {"Accept": "application/json"}),
    USER,
)
print("Status:", response.status_code)
print("Headers:", response.headers)
print("Body:", json.dumps(response.body, indent=2))


# ============================================================================
# 13. HEADER-BASED REQUEST DISPATCH
# ============================================================================

def handle_header_versioned_request(request: ApiRequest, user: User) -> ApiResponse:
    """Dispatch using API-Version rather than the URL."""
    try:
        version = parse_version_header(request.headers)
        payload = router.serialize(version, user)
    except InvalidVersionError as exc:
        return ApiResponse(400, {"error": str(exc)})
    except UnsupportedVersionError as exc:
        return ApiResponse(
            406,
            {"error": str(exc)},
            {
                "Supported-Versions": ", ".join(
                    f"v{item}" for item in router.supported_versions()
                )
            },
        )

    return ApiResponse(
        200,
        payload,
        {
            "Content-Type": "application/json",
            "API-Version": str(version),
            "Vary": "API-Version",
        },
    )


print_subsection("Header-Versioned Request")

response = handle_header_versioned_request(
    ApiRequest(
        "GET",
        "/api/users",
        {"API-Version": "2", "Accept": "application/json"},
    ),
    USER,
)

print("Status:", response.status_code)
print("Headers:", response.headers)
print("Body:", json.dumps(response.body, indent=2))


# ============================================================================
# 14. NEGOTIATION AND DEFAULT VERSION POLICY
# ============================================================================

class VersionSelectionPolicy:
    """
    Demonstrates explicit version selection and a documented default.

    A default should be deliberate and observable. Silent implicit upgrades
    can unexpectedly change response semantics for clients.
    """

    def __init__(
        self,
        supported_versions: Iterable[int],
        default_version: Optional[int] = None,
    ):
        self.supported_versions = set(supported_versions)
        self.default_version = default_version

        if default_version is not None and default_version not in self.supported_versions:
            raise ValueError("Default version must be supported.")

    def select(self, requested_version: Optional[int]) -> ApiVersion:
        if requested_version is None:
            if self.default_version is None:
                raise InvalidVersionError("Explicit API version is required.")
            return ApiVersion(self.default_version)

        if requested_version not in self.supported_versions:
            raise UnsupportedVersionError(
                f"Version v{requested_version} is not supported."
            )

        return ApiVersion(requested_version)


print_subsection("Version Selection Policy")

policy = VersionSelectionPolicy([1, 2, 3], default_version=2)

for requested in [None, 1, 3]:
    selected = policy.select(requested)
    print("Requested:", requested, "Selected:", selected)


# ============================================================================
# 15. DEPRECATION MODEL
# ============================================================================

class VersionLifecycle(Enum):
    CURRENT = "current"
    SUPPORTED = "supported"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"


@dataclass
class VersionPolicy:
    version: ApiVersion
    lifecycle: VersionLifecycle
    released_at: datetime
    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    successor: Optional[ApiVersion] = None
    migration_url: Optional[str] = None

    def validate(self) -> None:
        if self.lifecycle == VersionLifecycle.DEPRECATED:
            if self.deprecation_date is None:
                raise ValueError("Deprecated versions require a deprecation date.")

        if self.lifecycle == VersionLifecycle.SUNSET:
            if self.sunset_date is None:
                raise ValueError("Sunset versions require a sunset date.")

        if (
            self.deprecation_date is not None
            and self.sunset_date is not None
            and self.sunset_date < self.deprecation_date
        ):
            raise ValueError("Sunset date cannot precede deprecation date.")


print_subsection("Deprecation Lifecycle")

now = datetime.now(timezone.utc)

lifecycle = [
    VersionPolicy(
        ApiVersion(1),
        VersionLifecycle.DEPRECATED,
        now - timedelta(days=700),
        deprecation_date=now - timedelta(days=100),
        sunset_date=now + timedelta(days=80),
        successor=ApiVersion(2),
        migration_url="https://example.com/docs/migrate-v1-v2",
    ),
    VersionPolicy(
        ApiVersion(2),
        VersionLifecycle.SUPPORTED,
        now - timedelta(days=300),
    ),
    VersionPolicy(
        ApiVersion(3),
        VersionLifecycle.CURRENT,
        now - timedelta(days=30),
    ),
]

for item in lifecycle:
    item.validate()
    print(
        item.version,
        item.lifecycle.value,
        "successor=",
        item.successor,
    )


# ============================================================================
# 16. DEPRECATION HEADERS
# ============================================================================

def deprecation_headers(policy: VersionPolicy) -> Dict[str, str]:
    """
    Generate advisory response headers for deprecated APIs.

    Deprecation and Sunset headers should be treated as communication
    mechanisms. Organizations should also publish migration documentation
    and communicate through their normal developer channels.
    """
    headers: Dict[str, str] = {}

    if policy.lifecycle == VersionLifecycle.DEPRECATED:
        headers["Deprecation"] = "true"

        if policy.sunset_date is not None:
            headers["Sunset"] = policy.sunset_date.isoformat()

        if policy.migration_url:
            headers["Link"] = (
                f'<{policy.migration_url}>; rel="successor-version"'
            )

    return headers


print_subsection("Deprecation Response Headers")

for item in lifecycle:
    print(item.version, deprecation_headers(item))


# ============================================================================
# 17. CLIENT USAGE TELEMETRY
# ============================================================================

@dataclass
class UsageEvent:
    client_id: str
    version: int
    timestamp: datetime
    endpoint: str
    status_code: int


class UsageTracker:
    """Collects minimal in-memory usage data for migration planning."""

    def __init__(self) -> None:
        self.events: List[UsageEvent] = []

    def record(
        self,
        client_id: str,
        version: int,
        endpoint: str,
        status_code: int,
    ) -> None:
        self.events.append(
            UsageEvent(
                client_id=client_id,
                version=version,
                timestamp=datetime.now(timezone.utc),
                endpoint=endpoint,
                status_code=status_code,
            )
        )

    def counts_by_version(self) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        for event in self.events:
            counts[event.version] = counts.get(event.version, 0) + 1
        return counts

    def clients_using_version(self, version: int) -> List[str]:
        return sorted(
            {
                event.client_id
                for event in self.events
                if event.version == version
            }
        )


print_subsection("Migration Telemetry")

tracker = UsageTracker()

sample_events = [
    ("client-a", 1, 200),
    ("client-a", 1, 200),
    ("client-b", 2, 200),
    ("client-c", 3, 200),
    ("client-d", 1, 200),
    ("client-b", 2, 200),
    ("client-e", 3, 200),
]

for client_id, version, status in sample_events:
    tracker.record(client_id, version, "/users", status)

print("Requests by version:", tracker.counts_by_version())
print("Clients still using v1:", tracker.clients_using_version(1))


# ============================================================================
# 18. SAFE DEPRECATION PLAN
# ============================================================================

def create_deprecation_plan(
    old_version: ApiVersion,
    new_version: ApiVersion,
    announcement_days: int,
    migration_days: int,
    now: datetime,
) -> Dict[str, Any]:
    """
    Produce a concrete lifecycle schedule.

    The dates are planning values rather than universal standards.
    Real timelines depend on contractual obligations, client populations,
    risk, release cadence, and service-level commitments.
    """
    announcement = now
    migration_deadline = now + timedelta(days=migration_days)
    sunset = migration_deadline + timedelta(days=announcement_days)

    return {
        "old_version": str(old_version),
        "successor": str(new_version),
        "announcement": announcement.isoformat(),
        "migration_deadline": migration_deadline.isoformat(),
        "sunset": sunset.isoformat(),
        "actions": [
            "Publish migration documentation.",
            "Notify affected consumers.",
            "Mark the old version as deprecated.",
            "Add response warnings and lifecycle headers.",
            "Measure traffic by client and version.",
            "Contact remaining consumers.",
            "Confirm contractual and operational readiness.",
            "Retire only after the documented sunset policy is satisfied.",
        ],
    }


print_subsection("Example Deprecation Plan")
print(
    json.dumps(
        create_deprecation_plan(
            ApiVersion(1),
            ApiVersion(2),
            announcement_days=30,
            migration_days=90,
            now=now,
        ),
        indent=2,
    )
)


# ============================================================================
# 19. VERSIONED REQUEST SCHEMA VALIDATION
# ============================================================================

def validate_user_request_v1(payload: Mapping[str, Any]) -> List[str]:
    """V1 requires name and email."""
    errors: List[str] = []

    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        errors.append("name must be a non-empty string.")

    if not isinstance(payload.get("email"), str) or "@" not in payload["email"]:
        errors.append("email must be a valid-looking email string.")

    return errors


def validate_user_request_v2(payload: Mapping[str, Any]) -> List[str]:
    """V2 separates first_name and last_name."""
    errors: List[str] = []

    for field_name in ("first_name", "last_name"):
        if not isinstance(payload.get(field_name), str):
            errors.append(f"{field_name} must be a string.")

    if not isinstance(payload.get("email"), str) or "@" not in payload["email"]:
        errors.append("email must be a valid-looking email string.")

    return errors


print_subsection("Version-Specific Validation")

v1_request = {"name": "Atul Pandey", "email": "atul@example.com"}
v2_request = {
    "first_name": "Atul",
    "last_name": "Pandey",
    "email": "atul@example.com",
}

print("V1 errors:", validate_user_request_v1(v1_request))
print("V2 errors:", validate_user_request_v2(v2_request))

# A V1 request cannot be assumed to be a V2 request because the contracts
# intentionally use different field shapes.
print(
    "V1 request through V2 validator:",
    validate_user_request_v2(v1_request),
)


# ============================================================================
# 20. ADAPTER PATTERN FOR COMPATIBILITY
# ============================================================================

def adapt_v1_user_request_to_internal(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Translate a legacy V1 request into a canonical internal shape.

    This isolates compatibility logic at the API boundary instead of
    contaminating domain logic with version-specific field names.
    """
    errors = validate_user_request_v1(payload)
    if errors:
        raise ValueError("; ".join(errors))

    return {
        "first_name": payload["name"].strip().split()[0],
        "last_name": " ".join(payload["name"].strip().split()[1:]),
        "email": payload["email"].strip().lower(),
    }


def adapt_v2_user_request_to_internal(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """Translate V2 directly into the same canonical internal shape."""
    errors = validate_user_request_v2(payload)
    if errors:
        raise ValueError("; ".join(errors))

    return {
        "first_name": payload["first_name"].strip(),
        "last_name": payload["last_name"].strip(),
        "email": payload["email"].strip().lower(),
    }


print_subsection("Compatibility Adapter")

print(
    "V1 internal model:",
    adapt_v1_user_request_to_internal(v1_request),
)

print(
    "V2 internal model:",
    adapt_v2_user_request_to_internal(v2_request),
)


# ============================================================================
# 21. WHY ADAPTERS MATTER
# ============================================================================

class UserService:
    """
    Domain service independent of public API versions.

    Keeping the service version-neutral reduces duplicated business logic.
    """

    def create_user(self, canonical_input: Mapping[str, Any]) -> User:
        first_name = canonical_input["first_name"].strip()
        last_name = canonical_input["last_name"].strip()

        if not first_name:
            raise ValueError("First name cannot be empty.")

        return User(
            user_id=999,
            name=f"{first_name} {last_name}".strip(),
            email=canonical_input["email"],
            phone=None,
            active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


service = UserService()

print_subsection("Version-Neutral Domain Service")

print(
    service.create_user(
        adapt_v1_user_request_to_internal(v1_request)
    )
)

print(
    service.create_user(
        adapt_v2_user_request_to_internal(v2_request)
    )
)


# ============================================================================
# 22. CONTENT NEGOTIATION
# ============================================================================

def choose_media_type(accept_header: str) -> str:
    """
    Demonstrate a simplified Accept-header preference.

    Real HTTP negotiation can contain q-values, wildcards, parameters,
    multiple media types, and framework-specific behavior.
    """
    candidates = [
        "application/vnd.example.user+json;version=3",
        "application/vnd.example.user+json;version=2",
        "application/vnd.example.user+json;version=1",
    ]

    for candidate in candidates:
        if candidate.lower() in accept_header.lower():
            return candidate

    if "application/json" in accept_header.lower():
        return "application/json"

    return "406 Not Acceptable"


print_subsection("Content Negotiation")

for accept_header in [
    "application/vnd.example.user+json;version=2",
    "application/vnd.example.user+json;version=3, application/json",
    "application/json",
    "text/plain",
]:
    print(accept_header, "=>", choose_media_type(accept_header))


# ============================================================================
# 23. CACHING AND VARY
# ============================================================================

def cache_key_for_header_version(
    path: str,
    api_version: str,
) -> str:
    """
    Header-versioned representations need cache separation.

    If a cache keys only on URL, a V1 response could accidentally be served
    to a V2 client. A production HTTP cache should be configured to honor
    the appropriate Vary behavior or use a cache key containing the version.
    """
    return f"{path}|API-Version={api_version}"


print_subsection("Cache Safety")

print(cache_key_for_header_version("/api/users", "1"))
print(cache_key_for_header_version("/api/users", "2"))
print(
    "The two representations have distinct cache identities:",
    cache_key_for_header_version("/api/users", "1")
    != cache_key_for_header_version("/api/users", "2"),
)


# ============================================================================
# 24. IDEMPOTENCY AND VERSIONING
# ============================================================================

def versioned_idempotency_key(
    api_version: ApiVersion,
    client_key: str,
) -> str:
    """
    Versioning should not accidentally cause duplicate side effects.

    The key format demonstrates one possible strategy when request semantics
    differ between versions. A real design should define idempotency behavior
    explicitly in the API contract.
    """
    return f"{api_version}:{client_key}"


print_subsection("Idempotency Consideration")

print(versioned_idempotency_key(ApiVersion(1), "payment-123"))
print(versioned_idempotency_key(ApiVersion(2), "payment-123"))


# ============================================================================
# 25. ERROR CONTRACTS
# ============================================================================

def versioned_error_response(
    status_code: int,
    error_code: str,
    message: str,
    version: ApiVersion,
) -> ApiResponse:
    """
    Keep machine-readable error codes stable where possible.

    Human-readable messages may evolve, but client logic should generally
    rely on documented error codes rather than string matching.
    """
    body = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    if version.major >= 2:
        body["error"]["version"] = str(version)

    return ApiResponse(status_code, body)


print_subsection("Versioned Error Contract")

for version in [ApiVersion(1), ApiVersion(2)]:
    error = versioned_error_response(
        400,
        "INVALID_REQUEST",
        "The supplied request is invalid.",
        version,
    )
    print(str(version), json.dumps(error.body, indent=2))


# ============================================================================
# 26. VERSION-NEGOTIATION FAILURE MODES
# ============================================================================

def explain_failure_mode(name: str, symptom: str, prevention: str) -> None:
    print(f"\n{name}")
    print(f"  Symptom: {symptom}")
    print(f"  Prevention: {prevention}")


print_subsection("Common Failure Modes")

explain_failure_mode(
    "Unknown version",
    "Client requests a version that the server does not support.",
    "Return a documented 4xx response and advertise supported versions.",
)

explain_failure_mode(
    "Silent default upgrade",
    "An unversioned client unexpectedly receives a new representation.",
    "Use an explicit default policy and document it.",
)

explain_failure_mode(
    "Cache collision",
    "A cache returns one version's representation to another client.",
    "Use Vary headers and version-aware cache keys.",
)

explain_failure_mode(
    "Domain duplication",
    "Every API version contains a separate copy of business rules.",
    "Use adapters and a shared domain service where semantics permit.",
)

explain_failure_mode(
    "Premature retirement",
    "Consumers lose access before migration is complete.",
    "Measure usage, communicate deadlines, and verify migration status.",
)


# ============================================================================
# 27. SECURITY CONSIDERATIONS
# ============================================================================

print_subsection("Security Considerations")

security_points = [
    "Authenticate and authorize every version; do not assume old versions are trusted.",
    "Apply the same security baseline to old and new versions unless a documented exception exists.",
    "Do not keep obsolete vulnerable behavior alive merely for compatibility.",
    "Validate version input before routing to implementation code.",
    "Prevent version confusion where URL and header versions disagree.",
    "Keep secrets and sensitive fields out of legacy representations.",
    "Audit version-specific authorization and serialization logic.",
    "Monitor deprecated versions because they can remain attractive attack surfaces.",
]

for number, point in enumerate(security_points, start=1):
    print(f"{number}. {point}")


# ============================================================================
# 28. VERSION CONFLICT DETECTION
# ============================================================================

def select_consistent_version(
    url_version: Optional[ApiVersion],
    header_version: Optional[ApiVersion],
) -> Optional[ApiVersion]:
    """
    A gateway should have a documented policy for conflicting version signals.

    This implementation rejects disagreement rather than silently choosing one.
    """
    if url_version and header_version and url_version != header_version:
        raise InvalidVersionError(
            "URL version and header version conflict."
        )

    return url_version or header_version


print_subsection("Conflicting Version Signals")

print(
    "Same version:",
    select_consistent_version(ApiVersion(2), ApiVersion(2)),
)

try:
    select_consistent_version(ApiVersion(1), ApiVersion(2))
except InvalidVersionError as exc:
    print("Rejected:", exc)


# ============================================================================
# 29. FEATURE FLAGS VS API VERSIONS
# ============================================================================

print_subsection("API Versions vs Feature Flags")

print(
    """
API version:
    Changes the public contract and communicates a compatibility boundary.

Feature flag:
    Controls behavior or rollout independently of the public contract.

Do not create a new API version for every small implementation experiment.
Likewise, do not use a feature flag to disguise an incompatible public
contract change.
"""
)


# ============================================================================
# 30. PERFORMANCE CONSIDERATIONS
# ============================================================================

def benchmark_serialization(
    serializer: Serializer,
    user: User,
    iterations: int = 10_000,
) -> float:
    start = time.perf_counter()

    for _ in range(iterations):
        serializer(user)

    return time.perf_counter() - start


print_subsection("Performance")

for version_number, serializer in [
    (1, serialize_user_v1),
    (2, serialize_user_v2),
    (3, serialize_user_v3),
]:
    elapsed = benchmark_serialization(serializer, USER)
    print(f"V{version_number}: {elapsed:.6f} seconds for 10,000 serializations")

print(
    """
Versioning overhead is usually not caused by the version string itself.
The important costs are often:

- additional serialization logic,
- duplicated business logic,
- database queries caused by legacy fields,
- transformations between schemas,
- increased testing surface,
- operational complexity,
- cache fragmentation,
- maintaining multiple deployments or implementations.

Measure the actual system before optimizing.
"""
)


# ============================================================================
# 31. TESTING MATRIX
# ============================================================================

class ApiVersioningTests(unittest.TestCase):
    def test_url_parser(self) -> None:
        version, resource = parse_url_version("/api/v2/users")
        self.assertEqual(version, ApiVersion(2))
        self.assertEqual(resource, "users")

    def test_url_parser_rejects_unversioned_path(self) -> None:
        with self.assertRaises(InvalidVersionError):
            parse_url_version("/api/users")

    def test_v1_representation(self) -> None:
        payload = serialize_user_v1(USER)
        self.assertEqual(payload["name"], "Atul Pandey")
        self.assertNotIn("first_name", payload)

    def test_v2_representation(self) -> None:
        payload = serialize_user_v2(USER)
        self.assertEqual(payload["first_name"], "Atul")
        self.assertEqual(payload["last_name"], "Pandey")

    def test_unsupported_version(self) -> None:
        with self.assertRaises(UnsupportedVersionError):
            router.serialize(ApiVersion(99), USER)

    def test_v1_adapter(self) -> None:
        canonical = adapt_v1_user_request_to_internal(
            {"name": "Jane Doe", "email": "JANE@EXAMPLE.COM"}
        )
        self.assertEqual(canonical["first_name"], "Jane")
        self.assertEqual(canonical["last_name"], "Doe")
        self.assertEqual(canonical["email"], "jane@example.com")

    def test_v2_adapter(self) -> None:
        canonical = adapt_v2_user_request_to_internal(
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "JANE@EXAMPLE.COM",
            }
        )
        self.assertEqual(canonical["first_name"], "Jane")
        self.assertEqual(canonical["last_name"], "Doe")

    def test_version_conflict(self) -> None:
        with self.assertRaises(InvalidVersionError):
            select_consistent_version(ApiVersion(1), ApiVersion(2))

    def test_deprecation_headers(self) -> None:
        headers = deprecation_headers(lifecycle[0])
        self.assertEqual(headers["Deprecation"], "true")
        self.assertIn("Sunset", headers)
        self.assertIn("successor-version", headers["Link"])

    def test_cache_keys_differ(self) -> None:
        self.assertNotEqual(
            cache_key_for_header_version("/api/users", "1"),
            cache_key_for_header_version("/api/users", "2"),
        )


def run_tests() -> None:
    print_subsection("Automated Tests")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ApiVersioningTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("Tests passed:", result.wasSuccessful())


run_tests()


# ============================================================================
# 32. ADVANCED VERSIONING ARCHITECTURE
# ============================================================================

@dataclass
class EndpointDefinition:
    method: str
    path_template: str
    supported_versions: Tuple[int, ...]
    deprecated_versions: Tuple[int, ...] = ()
    sunset_versions: Tuple[int, ...] = ()

    def supports(self, version: int) -> bool:
        return version in self.supported_versions

    def is_deprecated(self, version: int) -> bool:
        return version in self.deprecated_versions

    def is_sunset(self, version: int) -> bool:
        return version in self.sunset_versions


class ApiCatalog:
    """
    A small API catalog models the metadata an organization can use to
    document and govern multiple endpoint versions.
    """

    def __init__(self) -> None:
        self.endpoints: List[EndpointDefinition] = []

    def register(self, endpoint: EndpointDefinition) -> None:
        self.endpoints.append(endpoint)

    def find(self, method: str, path_template: str) -> Optional[EndpointDefinition]:
        for endpoint in self.endpoints:
            if (
                endpoint.method.upper() == method.upper()
                and endpoint.path_template == path_template
            ):
                return endpoint
        return None


catalog = ApiCatalog()

catalog.register(
    EndpointDefinition(
        method="GET",
        path_template="/api/users",
        supported_versions=(1, 2, 3),
        deprecated_versions=(1,),
    )
)

catalog.register(
    EndpointDefinition(
        method="POST",
        path_template="/api/users",
        supported_versions=(1, 2),
        deprecated_versions=(1,),
    )
)

print_subsection("API Catalog")

for endpoint in catalog.endpoints:
    print(
        endpoint.method,
        endpoint.path_template,
        "supported=",
        endpoint.supported_versions,
        "deprecated=",
        endpoint.deprecated_versions,
    )


# ============================================================================
# 33. GOVERNANCE CHECK
# ============================================================================

def governance_check(
    catalog: ApiCatalog,
    policies: Iterable[VersionPolicy],
) -> List[str]:
    """
    Identify obvious lifecycle inconsistencies.

    Governance checks should be expanded to match organizational policy.
    """
    policy_by_version = {
        policy.version.major: policy
        for policy in policies
    }

    findings: List[str] = []

    for endpoint in catalog.endpoints:
        for version in endpoint.deprecated_versions:
            policy = policy_by_version.get(version)

            if policy is None:
                findings.append(
                    f"{endpoint.path_template}: v{version} is marked "
                    "deprecated but has no lifecycle policy."
                )

            elif policy.lifecycle != VersionLifecycle.DEPRECATED:
                findings.append(
                    f"{endpoint.path_template}: endpoint says v{version} "
                    f"is deprecated, but policy says {policy.lifecycle.value}."
                )

    return findings


print_subsection("Governance Check")
for finding in governance_check(catalog, lifecycle):
    print("Finding:", finding)


# ============================================================================
# 34. PRODUCTION CHECKLIST
# ============================================================================

print_section("PRODUCTION API VERSIONING CHECKLIST")

production_checklist = [
    "Define what constitutes a breaking change.",
    "Choose one primary version-selection mechanism.",
    "Document supported versions.",
    "Define behavior for missing version information.",
    "Define behavior for unknown versions.",
    "Keep domain logic independent of public version names when practical.",
    "Use explicit adapters for incompatible request and response shapes.",
    "Preserve stable machine-readable error codes.",
    "Test every supported version.",
    "Test interactions between versioning and authentication/authorization.",
    "Test caches and Vary behavior.",
    "Monitor traffic by version, client, endpoint, and status code.",
    "Publish migration documentation.",
    "Announce deprecation before retirement.",
    "Provide a clear successor version.",
    "Set and communicate a sunset date where appropriate.",
    "Contact or otherwise identify remaining consumers.",
    "Check contracts and service-level obligations before retirement.",
    "Remove retired code deliberately and verify routing cannot reach it.",
    "Record lifecycle decisions in API documentation and governance systems.",
]

for number, item in enumerate(production_checklist, start=1):
    print(f"{number:02d}. {item}")


# ============================================================================
# 35. FINAL WORKED SCENARIO
# ============================================================================

print_section("END-TO-END WORKED SCENARIO")

scenario_requests = [
    ApiRequest(
        "GET",
        "/api/v1/users",
        {"Accept": "application/json"},
    ),
    ApiRequest(
        "GET",
        "/api/v2/users",
        {"Accept": "application/json"},
    ),
    ApiRequest(
        "GET",
        "/api/v3/users",
        {"Accept": "application/json"},
    ),
    ApiRequest(
        "GET",
        "/api/v4/users",
        {"Accept": "application/json"},
    ),
]

v1_policy = lifecycle[0]

for request in scenario_requests:
    response = handle_url_versioned_request(request, USER)

    version_match = re.search(r"/api/v(\d+)/", request.path)
    requested_major = int(version_match.group(1)) if version_match else None

    if requested_major == v1_policy.version.major:
        response.headers.update(deprecation_headers(v1_policy))

    print("\nRequest:", request.method, request.path)
    print("Status:", response.status_code)
    print("Response headers:", response.headers)
    print("Response body:", json.dumps(response.body, indent=2))


# ============================================================================
# 36. KEY PRINCIPLES AS EXECUTABLE DATA
# ============================================================================

principles = [
    (
        "Explicit contracts",
        "A version identifies a stable public contract.",
    ),
    (
        "Compatibility boundaries",
        "Breaking changes require controlled migration.",
    ),
    (
        "Boundary translation",
        "Version-specific adapters can isolate contract differences.",
    ),
    (
        "Observable lifecycle",
        "Deprecation should be visible through documentation, headers, and telemetry.",
    ),
    (
        "Measured retirement",
        "Sunsetting should account for actual consumer usage and obligations.",
    ),
    (
        "Defense in depth",
        "Authentication, authorization, validation, monitoring, and security controls "
        "must remain effective across versions.",
    ),
]

print_section("CORE PRINCIPLES")

for name, description in principles:
    print(f"{name}: {description}")


print_section("PROGRAM COMPLETE")

print(
    """
The examples above form a complete learning progression:

1. Identify versions and versioning terminology.
2. Parse URL and header version signals.
3. Compare URL, custom-header, and media-type strategies.
4. Produce different public representations from one domain model.
5. Distinguish breaking from non-breaking changes.
6. Route requests to version-specific implementations.
7. Validate version-specific request contracts.
8. Adapt legacy contracts into a shared internal model.
9. Model deprecation and sunset lifecycles.
10. Track consumer usage for migration decisions.
11. Protect caches, errors, security controls, and idempotency behavior.
12. Test version behavior and lifecycle governance.
13. Apply the concepts to a production-oriented architecture.
"""
)
