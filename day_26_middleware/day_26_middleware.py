"""
Middleware: request lifecycle, response interception, and custom middleware.

This standalone study file demonstrates middleware from beginner concepts through
advanced implementation patterns without requiring a web framework.

The implementation models a small HTTP-like application pipeline:

    Request
       |
       v
    Middleware 1
       |
       v
    Middleware 2
       |
       v
    Application Handler
       |
       v
    Middleware 2 response processing
       |
       v
    Middleware 1 response processing
       |
       v
    Response

The same fundamental pattern appears in web frameworks such as WSGI/ASGI
applications, Express, ASP.NET Core, Spring, and many other server systems.

Run:
    python middleware_study.py
"""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional


# ============================================================================
# 1. FUNDAMENTAL HTTP-LIKE DATA STRUCTURES
# ============================================================================

@dataclass
class Request:
    """
    Represents the information entering an application.

    A real HTTP request contains considerably more information, but these
    fields cover the important middleware concepts:
        method
        path
        headers
        query parameters
        body
        state shared between middleware components
    """

    method: str
    path: str
    headers: MutableMapping[str, str] = field(default_factory=dict)
    query: MutableMapping[str, str] = field(default_factory=dict)
    body: Any = None
    state: MutableMapping[str, Any] = field(default_factory=dict)

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """HTTP header names are case-insensitive."""
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return default


@dataclass
class Response:
    """
    Represents the application's response.

    Middleware can inspect or modify a Response after the downstream handler
    returns it. This is the central idea behind response interception.
    """

    status_code: int = 200
    headers: MutableMapping[str, str] = field(default_factory=dict)
    body: Any = None

    def json(self) -> str:
        """Serialize the response body for demonstration purposes."""
        return json.dumps(self.body, default=str)


# A handler receives a Request and returns a Response.
Handler = Callable[[Request], Response]

# A middleware is a callable that receives the request and the next handler.
Middleware = Callable[[Request, Handler], Response]


# ============================================================================
# 2. SIMPLE APPLICATION HANDLER
# ============================================================================

def application(request: Request) -> Response:
    """
    The final application endpoint.

    Middleware surrounds this function. It can execute before it, call it,
    then execute more code after it returns.
    """
    if request.path == "/":
        return Response(
            status_code=200,
            body={
                "message": "Application response",
                "path": request.path,
            },
        )

    if request.path == "/users":
        return Response(
            status_code=200,
            body={
                "users": [
                    {"id": 1, "name": "Asha"},
                    {"id": 2, "name": "Rahul"},
                ]
            },
        )

    if request.path == "/missing":
        return Response(
            status_code=404,
            body={"error": "Resource not found"},
        )

    if request.path == "/error":
        raise ValueError("Demonstration application failure")

    return Response(
        status_code=200,
        body={"message": "Generic endpoint", "path": request.path},
    )


# ============================================================================
# 3. THE BASIC MIDDLEWARE PATTERN
# ============================================================================

def basic_logging_middleware(request: Request, next_handler: Handler) -> Response:
    """
    The smallest useful middleware pattern.

    1. Inspect request.
    2. Execute code before the handler.
    3. Call next_handler.
    4. Inspect response.
    5. Return response.

    The function therefore wraps downstream execution.
    """
    print(f"[basic logging] incoming {request.method} {request.path}")

    response = next_handler(request)

    print(f"[basic logging] outgoing {response.status_code}")
    return response


# ============================================================================
# 4. REQUEST ENRICHMENT
# ============================================================================

def request_id_middleware(request: Request, next_handler: Handler) -> Response:
    """
    Assign a unique request ID.

    Middleware often adds data that downstream code needs. Request state is
    used here rather than changing the endpoint's function signature.
    """
    request_id = request.get_header("X-Request-ID") or str(uuid.uuid4())

    request.state["request_id"] = request_id

    response = next_handler(request)

    # The same ID is returned to the caller so a request can be traced.
    response.headers["X-Request-ID"] = request_id
    return response


# ============================================================================
# 5. RESPONSE INTERCEPTION
# ============================================================================

def security_headers_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Add response headers after downstream processing.

    This is response interception: the middleware waits until the response
    exists, then modifies it before the response leaves the application.
    """
    response = next_handler(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# ============================================================================
# 6. AUTHENTICATION / AUTHORIZATION
# ============================================================================

def authentication_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Demonstrates authentication middleware.

    Authentication answers:
        "Who is making this request?"

    Authorization answers:
        "Is that identity allowed to perform this operation?"

    This example uses a deliberately simple header rather than a real token
    verification system.
    """
    token = request.get_header("Authorization")

    if token == "Bearer demo-user-token":
        request.state["user"] = {
            "id": 101,
            "name": "Demo User",
            "roles": ["user"],
        }
    else:
        request.state["user"] = None

    return next_handler(request)


def protected_endpoint(request: Request) -> Response:
    """An endpoint that requires an authenticated identity."""
    user = request.state.get("user")

    if user is None:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            body={"error": "Authentication required"},
        )

    return Response(
        status_code=200,
        body={
            "message": "Protected resource",
            "user": user,
        },
    )


# ============================================================================
# 7. AUTHORIZATION MIDDLEWARE
# ============================================================================

def admin_authorization_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Authorization should normally occur after authentication.

    The middleware checks whether the authenticated identity has an admin
    role before allowing execution to continue.
    """
    user = request.state.get("user")

    if user is None:
        return Response(
            status_code=401,
            body={"error": "Authentication required"},
        )

    if "admin" not in user.get("roles", []):
        return Response(
            status_code=403,
            body={"error": "Insufficient permissions"},
        )

    return next_handler(request)


# ============================================================================
# 8. TIMING / PERFORMANCE MIDDLEWARE
# ============================================================================

def timing_middleware(request: Request, next_handler: Handler) -> Response:
    """
    Measure total downstream processing time.

    perf_counter() is preferred for elapsed-time measurement because it is
    designed for performance timing rather than wall-clock timestamps.
    """
    start = time.perf_counter()

    response = next_handler(request)

    elapsed_ms = (time.perf_counter() - start) * 1000

    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.3f}"
    print(f"[timing] {request.path}: {elapsed_ms:.3f} ms")

    return response


# ============================================================================
# 9. ERROR-HANDLING MIDDLEWARE
# ============================================================================

def error_handling_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Convert unexpected exceptions into controlled responses.

    Error middleware is normally placed around the application so it can
    catch failures occurring deeper in the pipeline.
    """
    try:
        return next_handler(request)
    except Exception as exc:
        request.state["exception"] = exc

        # Do not expose internal tracebacks to clients in production.
        return Response(
            status_code=500,
            body={
                "error": "Internal server error",
                "request_id": request.state.get("request_id"),
            },
        )


# ============================================================================
# 10. RESPONSE TRANSFORMATION
# ============================================================================

def response_envelope_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Transform application responses into a consistent API envelope.

    This demonstrates a useful response interception pattern but also shows
    why middleware must understand the response format it is modifying.
    """
    response = next_handler(request)

    if isinstance(response.body, dict):
        response.body = {
            "status": "success" if response.status_code < 400 else "error",
            "data": response.body,
            "request_id": request.state.get("request_id"),
        }

    return response


# ============================================================================
# 11. CUSTOM MIDDLEWARE CLASS
# ============================================================================

class RateLimitMiddleware:
    """
    A stateful middleware example.

    The dictionary stores request counts. A real distributed production
    system would normally use a shared store such as Redis rather than
    process-local memory.
    """

    def __init__(self, limit: int = 3):
        if limit <= 0:
            raise ValueError("Rate limit must be positive")

        self.limit = limit
        self.request_counts: dict[str, int] = defaultdict(int)

    def __call__(self, request: Request, next_handler: Handler) -> Response:
        client_id = request.get_header("X-Client-ID", "anonymous")
        self.request_counts[client_id] += 1

        count = self.request_counts[client_id]

        if count > self.limit:
            return Response(
                status_code=429,
                headers={"Retry-After": "60"},
                body={
                    "error": "Rate limit exceeded",
                    "limit": self.limit,
                    "client": client_id,
                },
            )

        response = next_handler(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.limit - count)
        )
        return response


# ============================================================================
# 12. CACHING MIDDLEWARE
# ============================================================================

class SimpleCacheMiddleware:
    """
    Demonstrates short-lived response caching.

    Important production considerations:
        * cache keys must include relevant request dimensions
        * private/user-specific responses must not be shared accidentally
        * expiration is necessary
        * invalidation is difficult
        * distributed applications need shared cache infrastructure
    """

    def __init__(self, ttl_seconds: float = 10.0):
        self.ttl_seconds = ttl_seconds
        self.cache: dict[str, tuple[float, Response]] = {}

    def _key(self, request: Request) -> str:
        return f"{request.method}:{request.path}:{sorted(request.query.items())}"

    def __call__(self, request: Request, next_handler: Handler) -> Response:
        if request.method.upper() != "GET":
            return next_handler(request)

        key = self._key(request)
        now = time.monotonic()

        cached = self.cache.get(key)

        if cached:
            timestamp, response = cached
            if now - timestamp < self.ttl_seconds:
                response.headers["X-Cache"] = "HIT"
                return response

            del self.cache[key]

        response = next_handler(request)

        # Only cache successful GET responses in this demonstration.
        if response.status_code == 200:
            self.cache[key] = (now, response)
            response.headers["X-Cache"] = "MISS"

        return response


# ============================================================================
# 13. MIDDLEWARE COMPOSITION
# ============================================================================

def build_pipeline(
    middlewares: Iterable[Middleware],
    final_handler: Handler,
) -> Handler:
    """
    Compose middleware into a single executable handler.

    The reversal is important.

    Given:
        A, B, C

    The resulting call structure is:

        A(
          B(
            C(
              application
            )
          )
        )

    Consequently, entry order is A -> B -> C -> application, while response
    processing occurs in reverse order: application -> C -> B -> A.
    """
    handler = final_handler

    for middleware in reversed(list(middlewares)):
        downstream = handler

        def wrapped(
            request: Request,
            current=middleware,
            next_handler=downstream,
        ) -> Response:
            return current(request, next_handler)

        handler = wrapped

    return handler


# ============================================================================
# 14. VISUALIZING THE REQUEST/RESPONSE LIFECYCLE
# ============================================================================

def demonstrate_lifecycle() -> None:
    print("\n" + "=" * 72)
    print("REQUEST / RESPONSE LIFECYCLE")
    print("=" * 72)

    request = Request(
        method="GET",
        path="/users",
        headers={"X-Client-ID": "client-1"},
    )

    rate_limit = RateLimitMiddleware(limit=5)
    cache = SimpleCacheMiddleware(ttl_seconds=5)

    pipeline = build_pipeline(
        [
            error_handling_middleware,
            request_id_middleware,
            basic_logging_middleware,
            timing_middleware,
            rate_limit,
            cache,
            security_headers_middleware,
            response_envelope_middleware,
        ],
        application,
    )

    response = pipeline(request)

    print("Response status:", response.status_code)
    print("Response headers:", dict(response.headers))
    print("Response body:", response.json())


# ============================================================================
# 15. MIDDLEWARE ORDER MATTERS
# ============================================================================

def demonstrate_order() -> None:
    print("\n" + "=" * 72)
    print("MIDDLEWARE ORDER")
    print("=" * 72)

    events: list[str] = []

    def middleware_a(request: Request, next_handler: Handler) -> Response:
        events.append("A before")
        response = next_handler(request)
        events.append("A after")
        return response

    def middleware_b(request: Request, next_handler: Handler) -> Response:
        events.append("B before")
        response = next_handler(request)
        events.append("B after")
        return response

    def endpoint(request: Request) -> Response:
        events.append("endpoint")
        return Response(body={"ok": True})

    pipeline = build_pipeline(
        [middleware_a, middleware_b],
        endpoint,
    )

    pipeline(Request("GET", "/order"))

    for event in events:
        print(event)

    print(
        "\nExpected order:\n"
        "A before\n"
        "B before\n"
        "endpoint\n"
        "B after\n"
        "A after"
    )


# ============================================================================
# 16. SHORT-CIRCUITING
# ============================================================================

def maintenance_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Middleware can stop the pipeline without calling next_handler.

    This is called short-circuiting.
    """
    if request.path == "/maintenance":
        return Response(
            status_code=503,
            body={"error": "Service temporarily unavailable"},
        )

    return next_handler(request)


def demonstrate_short_circuiting() -> None:
    print("\n" + "=" * 72)
    print("SHORT-CIRCUITING")
    print("=" * 72)

    pipeline = build_pipeline(
        [maintenance_middleware, basic_logging_middleware],
        application,
    )

    for path in ["/", "/maintenance"]:
        response = pipeline(Request("GET", path))
        print(path, "->", response.status_code, response.body)


# ============================================================================
# 17. REQUEST VALIDATION
# ============================================================================

def validation_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Validate request properties before executing business logic.

    Validation and security are related but not identical. Validation checks
    whether data satisfies expected constraints; authentication and
    authorization establish identity and permissions.
    """
    if not request.method:
        return Response(
            status_code=400,
            body={"error": "HTTP method is required"},
        )

    if not request.path.startswith("/"):
        return Response(
            status_code=400,
            body={"error": "Path must begin with /"},
        )

    content_length = request.get_header("Content-Length")

    if content_length is not None:
        try:
            length = int(content_length)
        except ValueError:
            return Response(
                status_code=400,
                body={"error": "Invalid Content-Length"},
            )

        if length < 0:
            return Response(
                status_code=400,
                body={"error": "Content-Length cannot be negative"},
            )

    return next_handler(request)


# ============================================================================
# 18. METRICS MIDDLEWARE
# ============================================================================

class MetricsMiddleware:
    """
    Collect simple in-process request metrics.

    Production telemetry normally needs dimensions, aggregation, sampling,
    concurrency safety, and an external monitoring system.
    """

    def __init__(self) -> None:
        self.total_requests = 0
        self.status_counts: dict[int, int] = defaultdict(int)
        self.path_counts: dict[str, int] = defaultdict(int)

    def __call__(self, request: Request, next_handler: Handler) -> Response:
        self.total_requests += 1
        self.path_counts[request.path] += 1

        response = next_handler(request)
        self.status_counts[response.status_code] += 1

        return response

    def report(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "status_counts": dict(self.status_counts),
            "path_counts": dict(self.path_counts),
        }


# ============================================================================
# 19. CORRELATION AND LOGGING
# ============================================================================

def structured_logging_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Structured logs are easier for machines to query than free-form strings.
    """
    request_id = request.state.get("request_id", "unknown")

    logging.info(
        json.dumps(
            {
                "event": "request_started",
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
            }
        )
    )

    response = next_handler(request)

    logging.info(
        json.dumps(
            {
                "event": "request_completed",
                "request_id": request_id,
                "status_code": response.status_code,
            }
        )
    )

    return response


# ============================================================================
# 20. CONTENT NEGOTIATION DEMONSTRATION
# ============================================================================

def content_negotiation_middleware(
    request: Request,
    next_handler: Handler,
) -> Response:
    """
    Demonstrates basic content negotiation.

    A real implementation must support the full HTTP Accept grammar,
    quality values, wildcards, and media-type parameters.
    """
    response = next_handler(request)

    accepted = request.get_header("Accept", "application/json")

    if "application/json" in accepted or "*/*" in accepted:
        response.headers["Content-Type"] = "application/json"
    else:
        response.headers["Content-Type"] = "application/octet-stream"

    return response


# ============================================================================
# 21. SECURITY: SENSITIVE DATA MUST NOT BE LOGGED
# ============================================================================

def safe_header_snapshot(request: Request) -> dict[str, str]:
    """
    Create a sanitized representation for logging.

    Authentication credentials, cookies, API keys, and other secrets should
    not be copied into ordinary logs.
    """
    sensitive_headers = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
    }

    return {
        key: ("[REDACTED]" if key.lower() in sensitive_headers else value)
        for key, value in request.headers.items()
    }


def demonstrate_safe_logging() -> None:
    print("\n" + "=" * 72)
    print("SAFE LOGGING")
    print("=" * 72)

    request = Request(
        "GET",
        "/secure",
        headers={
            "Authorization": "Bearer secret-value",
            "Accept": "application/json",
            "X-Client-ID": "client-7",
        },
    )

    print(safe_header_snapshot(request))


# ============================================================================
# 22. ASYNCHRONOUS MIDDLEWARE CONCEPT
# ============================================================================

async def async_application(request: Request) -> Response:
    """
    Conceptual asynchronous endpoint.

    No external framework is required to understand the pattern. In a real
    ASGI server, asynchronous middleware uses await to suspend execution while
    waiting for I/O.
    """
    return Response(
        status_code=200,
        body={"message": "Async response"},
    )


# ============================================================================
# 23. ASYNCHRONOUS PIPELINE
# ============================================================================

from typing import Awaitable

AsyncHandler = Callable[[Request], Awaitable[Response]]
AsyncMiddleware = Callable[[Request, AsyncHandler], Awaitable[Response]]


async def async_logging_middleware(
    request: Request,
    next_handler: AsyncHandler,
) -> Response:
    """Async middleware keeps the same conceptual before/after structure."""
    print(f"[async] before {request.path}")

    response = await next_handler(request)

    print(f"[async] after {response.status_code}")
    return response


def build_async_pipeline(
    middlewares: Iterable[AsyncMiddleware],
    final_handler: AsyncHandler,
) -> AsyncHandler:
    """Compose asynchronous middleware in the same nesting order."""
    handler = final_handler

    for middleware in reversed(list(middlewares)):
        downstream = handler

        async def wrapped(
            request: Request,
            current=middleware,
            next_handler=downstream,
        ) -> Response:
            return await current(request, next_handler)

        handler = wrapped

    return handler


# ============================================================================
# 24. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n" + "=" * 72)
    print("EDGE CASES")
    print("=" * 72)

    invalid_requests = [
        Request("", "/"),
        Request("GET", "users"),
        Request(
            "POST",
            "/users",
            headers={"Content-Length": "not-a-number"},
        ),
        Request(
            "POST",
            "/users",
            headers={"Content-Length": "-1"},
        ),
    ]

    pipeline = build_pipeline(
        [validation_middleware],
        application,
    )

    for request in invalid_requests:
        response = pipeline(request)
        print(
            repr(request.method),
            repr(request.path),
            "->",
            response.status_code,
            response.body,
        )


# ============================================================================
# 25. ERROR BEHAVIOR
# ============================================================================

def demonstrate_error_handling() -> None:
    print("\n" + "=" * 72)
    print("ERROR HANDLING")
    print("=" * 72)

    pipeline = build_pipeline(
        [
            error_handling_middleware,
            request_id_middleware,
        ],
        application,
    )

    request = Request("GET", "/error")
    response = pipeline(request)

    print("Status:", response.status_code)
    print("Body:", response.body)


# ============================================================================
# 26. PROTECTED ENDPOINT PIPELINE
# ============================================================================

def demonstrate_authentication_and_authorization() -> None:
    print("\n" + "=" * 72)
    print("AUTHENTICATION AND AUTHORIZATION")
    print("=" * 72)

    pipeline = build_pipeline(
        [
            request_id_middleware,
            authentication_middleware,
            admin_authorization_middleware,
        ],
        protected_endpoint,
    )

    requests = [
        Request("GET", "/admin"),
        Request(
            "GET",
            "/admin",
            headers={"Authorization": "Bearer demo-user-token"},
        ),
    ]

    for request in requests:
        response = pipeline(request)
        print(response.status_code, response.body)


# ============================================================================
# 27. TESTABLE CUSTOM MIDDLEWARE
# ============================================================================

def test_request_id_is_added() -> None:
    request = Request("GET", "/")

    pipeline = build_pipeline(
        [request_id_middleware],
        application,
    )

    response = pipeline(request)

    assert request.state["request_id"]
    assert response.headers["X-Request-ID"] == request.state["request_id"]


def test_missing_resource_returns_404() -> None:
    response = application(Request("GET", "/missing"))

    assert response.status_code == 404


def test_maintenance_short_circuits() -> None:
    called = False

    def endpoint(request: Request) -> Response:
        nonlocal called
        called = True
        return Response(body={"unexpected": True})

    pipeline = build_pipeline(
        [maintenance_middleware],
        endpoint,
    )

    response = pipeline(Request("GET", "/maintenance"))

    assert response.status_code == 503
    assert called is False


def test_rate_limit() -> None:
    limiter = RateLimitMiddleware(limit=2)

    pipeline = build_pipeline(
        [limiter],
        application,
    )

    request1 = Request(
        "GET",
        "/",
        headers={"X-Client-ID": "test"},
    )
    request2 = Request(
        "GET",
        "/",
        headers={"X-Client-ID": "test"},
    )
    request3 = Request(
        "GET",
        "/",
        headers={"X-Client-ID": "test"},
    )

    assert pipeline(request1).status_code == 200
    assert pipeline(request2).status_code == 200
    assert pipeline(request3).status_code == 429


def run_tests() -> None:
    print("\n" + "=" * 72)
    print("SELF-TESTS")
    print("=" * 72)

    tests = [
        test_request_id_is_added,
        test_missing_resource_returns_404,
        test_maintenance_short_circuits,
        test_rate_limit,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")


# ============================================================================
# 28. PRODUCTION DESIGN CHECKLIST
# ============================================================================

def print_design_checklist() -> None:
    print("\n" + "=" * 72)
    print("MIDDLEWARE DESIGN PRINCIPLES")
    print("=" * 72)

    principles = [
        "Keep middleware focused on one responsibility.",
        "Call the downstream handler exactly when the request should continue.",
        "Short-circuit deliberately and return a complete response.",
        "Preserve important response metadata when transforming responses.",
        "Place error handling around components whose failures must be caught.",
        "Never log secrets such as passwords, tokens, or session cookies.",
        "Avoid process-local state when running multiple server instances.",
        "Keep expensive middleware out of latency-sensitive paths unless justified.",
        "Use correlation/request IDs for distributed tracing.",
        "Make ordering explicit because middleware behavior is order-dependent.",
        "Validate external input before business logic uses it.",
        "Avoid changing semantics invisibly through generic response transforms.",
    ]

    for number, principle in enumerate(principles, start=1):
        print(f"{number:02d}. {principle}")


# ============================================================================
# 29. MAIN STUDY PROGRAM
# ============================================================================

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    demonstrate_lifecycle()
    demonstrate_order()
    demonstrate_short_circuiting()
    demonstrate_edge_cases()
    demonstrate_error_handling()
    demonstrate_authentication_and_authorization()
    demonstrate_safe_logging()
    run_tests()
    print_design_checklist()

    print("\n" + "=" * 72)
    print("STUDY COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
