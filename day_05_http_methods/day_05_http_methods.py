"""
HTTP METHODS: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS,
IDEMPOTENCY, SAFE METHODS, HTTP SEMANTICS, VALIDATION, SIMULATION,
ERROR HANDLING, TESTING, SECURITY, PERFORMANCE, AND PRODUCTION DESIGN.

This is a self-contained educational script. It uses only Python's standard
library and demonstrates HTTP methods from beginner through advanced concepts.

The examples are simulations unless explicitly stated otherwise. No external
HTTP server or third-party package is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from http import HTTPStatus
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse
import hashlib
import json
import time
import unittest


# ============================================================================
# 1. HTTP FUNDAMENTALS
# ============================================================================

"""
HTTP stands for Hypertext Transfer Protocol.

HTTP is an application-layer protocol used for communication between clients
and servers.

A typical HTTP interaction looks like:

    Client -> HTTP Request -> Server
    Client <- HTTP Response <- Server

An HTTP request contains concepts such as:

    Method
    Request target / URL
    Headers
    Optional body

An HTTP response contains:

    Status code
    Headers
    Optional body

Examples of methods:

    GET
    POST
    PUT
    PATCH
    DELETE
    HEAD
    OPTIONS

A method communicates the intended semantics of a request. It is not merely
a label for a URL.
"""


@dataclass
class HTTPRequest:
    method: str
    target: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None

    def __post_init__(self) -> None:
        self.method = self.method.upper()

    def __str__(self) -> str:
        lines = [f"{self.method} {self.target} HTTP/1.1"]
        for name, value in self.headers.items():
            lines.append(f"{name}: {value}")

        lines.append("")

        if self.body is not None:
            lines.append(self.body)

        return "\n".join(lines)


@dataclass
class HTTPResponse:
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None

    @property
    def reason(self) -> str:
        try:
            return HTTPStatus(self.status_code).phrase
        except ValueError:
            return "Unknown Status"

    def __str__(self) -> str:
        lines = [f"HTTP/1.1 {self.status_code} {self.reason}"]

        for name, value in self.headers.items():
            lines.append(f"{name}: {value}")

        lines.append("")

        if self.body is not None:
            lines.append(self.body)

        return "\n".join(lines)


# ============================================================================
# 2. HTTP METHODS AND TERMINOLOGY
# ============================================================================

class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


METHOD_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "GET": {
        "purpose": "Retrieve a representation of a resource.",
        "safe": True,
        "idempotent": True,
        "typical_body": False,
    },
    "POST": {
        "purpose": "Submit data for processing or create subordinate resources.",
        "safe": False,
        "idempotent": False,
        "typical_body": True,
    },
    "PUT": {
        "purpose": "Create or replace the state of a resource at a known target URI.",
        "safe": False,
        "idempotent": True,
        "typical_body": True,
    },
    "PATCH": {
        "purpose": "Apply partial modifications to a resource.",
        "safe": False,
        "idempotent": NotImplemented,
        "typical_body": True,
    },
    "DELETE": {
        "purpose": "Remove a resource.",
        "safe": False,
        "idempotent": True,
        "typical_body": False,
    },
    "HEAD": {
        "purpose": "Retrieve the headers that would accompany a GET response.",
        "safe": True,
        "idempotent": True,
        "typical_body": False,
    },
    "OPTIONS": {
        "purpose": "Discover communication options supported for a resource/server.",
        "safe": True,
        "idempotent": True,
        "typical_body": False,
    },
}


def print_method_reference() -> None:
    """Print a compact semantic reference for the major HTTP methods."""

    print("\nHTTP METHOD REFERENCE")
    print("=" * 90)

    for method, details in METHOD_DEFINITIONS.items():
        idempotent = details["idempotent"]

        if idempotent is NotImplemented:
            idempotent_text = "depends on operation design"
        else:
            idempotent_text = str(idempotent)

        print(
            f"{method:8} | "
            f"safe={str(details['safe']):5} | "
            f"idempotent={idempotent_text:27} | "
            f"{details['purpose']}"
        )


# ============================================================================
# 3. SAFE METHODS
# ============================================================================

"""
A safe method is one whose defined semantics are intended to be read-only
from the client's perspective.

GET, HEAD, and OPTIONS are safe methods.

Safe does NOT mean:

    - the server performs absolutely no internal work
    - the request is free from side effects in an implementation
    - the request cannot consume resources
    - the request cannot be abused

For example, a GET request can cause logging, caching, metrics collection,
authentication checks, or database reads.

A server should not design a GET endpoint so that ordinary GET usage performs
a state-changing business action.

Bad conceptual design:

    GET /delete-account?id=123

Better design:

    DELETE /accounts/123
"""


def is_safe_method(method: str) -> bool:
    """Return whether a method has safe HTTP semantics."""

    return method.upper() in {"GET", "HEAD", "OPTIONS"}


def demonstrate_safe_methods() -> None:
    print("\nSAFE METHODS")
    print("=" * 50)

    for method in ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]:
        print(f"{method:8} -> safe={is_safe_method(method)}")


# ============================================================================
# 4. IDEMPOTENCY
# ============================================================================

"""
Idempotency is a property of an operation.

A method is idempotent when making the same request multiple times has the
same intended server state as making it once.

Conceptually:

    f(f(state)) = f(state)

Idempotency does NOT necessarily mean:

    - identical response bodies
    - identical timestamps
    - identical logs
    - no side effects whatsoever
    - the request can never fail

GET is idempotent.

PUT is idempotent when it replaces a resource with the same representation.

DELETE is idempotent with respect to the final resource state:
deleting an existing resource and deleting an already-deleted resource can
lead to the same final state.

POST is generally not idempotent.

For example:

    POST /orders

may create:

    order 101

and repeating it may create:

    order 102

PATCH is not automatically idempotent. It depends on the patch operation.

An operation such as:

    {"balance": 100}

can be idempotent.

An operation such as:

    {"increment_balance": 10}

is not idempotent if repeated.
"""


def apply_put(state: Dict[str, Any], replacement: Dict[str, Any]) -> Dict[str, Any]:
    """PUT-like replacement semantics."""

    return dict(replacement)


def apply_delete(state: Dict[str, Any]) -> Dict[str, Any]:
    """DELETE-like final-state simulation."""

    return {}


def apply_increment_patch(state: Dict[str, Any], amount: int) -> Dict[str, Any]:
    """A non-idempotent PATCH-like operation."""

    updated = dict(state)
    updated["balance"] = updated.get("balance", 0) + amount
    return updated


def apply_set_patch(state: Dict[str, Any], value: int) -> Dict[str, Any]:
    """An idempotent PATCH-like operation."""

    updated = dict(state)
    updated["balance"] = value
    return updated


def demonstrate_idempotency() -> None:
    print("\nIDEMPOTENCY")
    print("=" * 50)

    initial = {"balance": 100}

    once_put = apply_put(initial, {"balance": 200})
    twice_put = apply_put(once_put, {"balance": 200})

    print("PUT once :", once_put)
    print("PUT twice:", twice_put)
    print("Same final state:", once_put == twice_put)

    once_increment = apply_increment_patch(initial, 10)
    twice_increment = apply_increment_patch(once_increment, 10)

    print("\nIncrement PATCH once :", once_increment)
    print("Increment PATCH twice:", twice_increment)
    print("Same final state:", once_increment == twice_increment)

    once_set = apply_set_patch(initial, 200)
    twice_set = apply_set_patch(once_set, 200)

    print("\nSet PATCH once :", once_set)
    print("Set PATCH twice:", twice_set)
    print("Same final state:", once_set == twice_set)


# ============================================================================
# 5. GET
# ============================================================================

"""
GET retrieves a representation of a resource.

Examples:

    GET /users
    GET /users/42
    GET /products?category=books
    GET /orders/1001

Typical properties:

    Safe: yes
    Idempotent: yes
    Cacheable: often, subject to HTTP caching rules

GET query parameters normally express filtering, sorting, pagination, or
other retrieval criteria.

Example:

    /products?category=books&page=2&limit=20
"""


class InMemoryStore:
    """A small in-memory database used for HTTP method demonstrations."""

    def __init__(self) -> None:
        self.resources: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1

    def create(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        resource_copy = dict(resource)
        resource_id = self.next_id
        self.next_id += 1

        resource_copy["id"] = resource_id
        self.resources[resource_id] = resource_copy

        return dict(resource_copy)

    def get(self, resource_id: int) -> Optional[Dict[str, Any]]:
        resource = self.resources.get(resource_id)

        if resource is None:
            return None

        return dict(resource)

    def get_all(self) -> List[Dict[str, Any]]:
        return [dict(resource) for resource in self.resources.values()]

    def replace(self, resource_id: int, resource: Dict[str, Any]) -> Dict[str, Any]:
        replacement = dict(resource)
        replacement["id"] = resource_id
        self.resources[resource_id] = replacement
        return dict(replacement)

    def patch(self, resource_id: int, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if resource_id not in self.resources:
            return None

        self.resources[resource_id].update(changes)
        self.resources[resource_id]["id"] = resource_id

        return dict(self.resources[resource_id])

    def delete(self, resource_id: int) -> bool:
        return self.resources.pop(resource_id, None) is not None


store = InMemoryStore()


def simulate_get(resource_id: Optional[int] = None) -> HTTPResponse:
    """Simulate GET /resources or GET /resources/{id}."""

    if resource_id is None:
        body = json.dumps(store.get_all())
        return HTTPResponse(
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "max-age=60",
            },
            body=body,
        )

    resource = store.get(resource_id)

    if resource is None:
        return HTTPResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Resource not found"}),
        )

    return HTTPResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=json.dumps(resource),
    )


# ============================================================================
# 6. POST
# ============================================================================

"""
POST submits a representation for processing.

Common uses:

    POST /users
    POST /orders
    POST /payments
    POST /messages

POST is commonly used for creation when the server assigns the resource URI.

Example:

    POST /users

Request body:

    {
        "name": "Alice",
        "email": "alice@example.com"
    }

Possible response:

    201 Created

with:

    Location: /users/42

POST is generally not idempotent.

Repeated POST requests can create repeated resources.

For operations where clients may retry requests, an application can introduce
an idempotency-key mechanism. The key is an application-level design feature;
it should not be confused with the intrinsic semantics of POST.
"""


def simulate_post(payload: Dict[str, Any]) -> HTTPResponse:
    """Simulate POST /resources."""

    if "name" not in payload:
        return HTTPResponse(
            status_code=400,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "name is required"}),
        )

    created = store.create(payload)

    return HTTPResponse(
        status_code=201,
        headers={
            "Content-Type": "application/json",
            "Location": f"/resources/{created['id']}",
        },
        body=json.dumps(created),
    )


# ============================================================================
# 7. PUT
# ============================================================================

"""
PUT replaces the representation of a target resource.

Example:

    PUT /users/42

with:

    {
        "name": "Alice",
        "email": "alice@example.com"
    }

A crucial distinction:

    PUT = replacement semantics

    PATCH = partial modification semantics

If a resource is represented as:

    {
        "name": "Alice",
        "email": "alice@example.com",
        "city": "Delhi"
    }

and PUT receives:

    {
        "name": "Alice Updated"
    }

the server's replacement semantics generally mean the complete representation
is now the submitted representation, rather than simply changing "name".

API contracts may define validation rules around required fields.
"""


def simulate_put(resource_id: int, replacement: Dict[str, Any]) -> HTTPResponse:
    """Simulate PUT /resources/{id}."""

    if not replacement:
        return HTTPResponse(
            status_code=400,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Complete replacement representation required"}),
        )

    existed = store.get(resource_id) is not None
    updated = store.replace(resource_id, replacement)

    return HTTPResponse(
        status_code=200 if existed else 201,
        headers={
            "Content-Type": "application/json",
            "Location": f"/resources/{resource_id}",
        },
        body=json.dumps(updated),
    )


# ============================================================================
# 8. PATCH
# ============================================================================

"""
PATCH applies partial modifications.

Example:

    PATCH /users/42

Body:

    {
        "city": "Lucknow"
    }

The resource can retain its other fields.

PATCH has no blanket guarantee of idempotency.

An idempotent PATCH operation:

    {"status": "active"}

Repeated application results in:

    status = active

A non-idempotent PATCH operation:

    {"operation": "increment", "amount": 1}

Repeated application changes state each time.

PATCH formats include application-specific designs and standardized patch
formats such as JSON Patch and JSON Merge Patch. This script implements a
simple dictionary update to make the underlying concept clear.
"""


def simulate_patch(resource_id: int, changes: Dict[str, Any]) -> HTTPResponse:
    """Simulate a simple partial update."""

    updated = store.patch(resource_id, changes)

    if updated is None:
        return HTTPResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Resource not found"}),
        )

    return HTTPResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=json.dumps(updated),
    )


# ============================================================================
# 9. DELETE
# ============================================================================

"""
DELETE requests removal of a resource.

Example:

    DELETE /users/42

Possible successful responses include:

    204 No Content

A second DELETE can result in:

    404 Not Found

or an application may choose another response depending on its contract.

The method is still idempotent in the HTTP semantic sense because repeated
application can have the same intended final state: the resource is absent.

Idempotent does not mean every response must be identical.
"""


def simulate_delete(resource_id: int) -> HTTPResponse:
    """Simulate DELETE /resources/{id}."""

    existed = store.delete(resource_id)

    if not existed:
        return HTTPResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Resource not found"}),
        )

    return HTTPResponse(
        status_code=204,
        headers={},
        body=None,
    )


# ============================================================================
# 10. HEAD
# ============================================================================

"""
HEAD is similar to GET, except the server must not send response content in
the response body.

HEAD is useful for:

    - checking whether a resource exists
    - inspecting Content-Length
    - inspecting ETag
    - checking Last-Modified
    - checking cache-related metadata
    - validating remote content before downloading it

The headers should generally correspond to those of a GET response, subject
to the specific implementation and current resource state.
"""


def simulate_head(resource_id: int) -> HTTPResponse:
    """Simulate HEAD by deriving metadata without returning a body."""

    resource = store.get(resource_id)

    if resource is None:
        return HTTPResponse(
            status_code=404,
            headers={},
            body=None,
        )

    serialized = json.dumps(resource)

    return HTTPResponse(
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(serialized.encode("utf-8"))),
            "ETag": generate_etag(serialized),
        },
        body=None,
    )


# ============================================================================
# 11. OPTIONS
# ============================================================================

"""
OPTIONS asks what communication options are available.

A resource can respond with:

    Allow: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS

OPTIONS is also important in CORS scenarios.

A browser can issue a CORS preflight request such as:

    OPTIONS /api/users

with headers describing the intended cross-origin request.

The server can respond with headers such as:

    Access-Control-Allow-Origin
    Access-Control-Allow-Methods
    Access-Control-Allow-Headers

CORS is a browser security mechanism. It is not a replacement for
authentication or authorization.
"""


ALLOWED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}


def simulate_options() -> HTTPResponse:
    """Simulate an OPTIONS response."""

    return HTTPResponse(
        status_code=204,
        headers={
            "Allow": ", ".join(sorted(ALLOWED_METHODS)),
        },
        body=None,
    )


# ============================================================================
# 12. URL STRUCTURE AND QUERY PARAMETERS
# ============================================================================

"""
Example URL:

    https://example.com:443/api/users/42?active=true&sort=name#profile

Components:

    scheme      -> https
    host        -> example.com
    port        -> 443
    path        -> /api/users/42
    query       -> active=true&sort=name
    fragment    -> profile

The fragment is generally handled by the client and is not sent as part of
the HTTP request to the server.
"""


def parse_url_example(url: str) -> Dict[str, Any]:
    """Parse a URL and expose its main components."""

    parsed = urlparse(url)

    query = {
        key: values
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
    }

    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "path": parsed.path,
        "query": query,
        "fragment": parsed.fragment,
    }


def build_query_url(base_url: str, parameters: Dict[str, Any]) -> str:
    """Safely encode query parameters rather than manually concatenating them."""

    return f"{base_url}?{urlencode(parameters)}"


# ============================================================================
# 13. HTTP STATUS CODES
# ============================================================================

"""
Important status-code classes:

    1xx -> informational
    2xx -> successful
    3xx -> redirection
    4xx -> client-side error
    5xx -> server-side error

Common codes:

    200 OK
    201 Created
    202 Accepted
    204 No Content
    301 Moved Permanently
    302 Found
    304 Not Modified
    400 Bad Request
    401 Unauthorized
    403 Forbidden
    404 Not Found
    405 Method Not Allowed
    409 Conflict
    412 Precondition Failed
    415 Unsupported Media Type
    422 Unprocessable Content
    429 Too Many Requests
    500 Internal Server Error
    502 Bad Gateway
    503 Service Unavailable
    504 Gateway Timeout

405 is particularly important for HTTP methods:

    Allow: GET, HEAD

can tell the client which methods are supported for the resource.
"""


def classify_status(status_code: int) -> str:
    """Return the HTTP status class."""

    if 100 <= status_code <= 199:
        return "1xx Informational"

    if 200 <= status_code <= 299:
        return "2xx Success"

    if 300 <= status_code <= 399:
        return "3xx Redirection"

    if 400 <= status_code <= 499:
        return "4xx Client Error"

    if 500 <= status_code <= 599:
        return "5xx Server Error"

    return "Invalid HTTP status"


# ============================================================================
# 14. METHOD ROUTING
# ============================================================================

"""
A server commonly maps:

    HTTP method + request target

to a handler.

For example:

    GET    /users
    POST   /users
    GET    /users/{id}
    PUT    /users/{id}
    PATCH  /users/{id}
    DELETE /users/{id}

The same path can legitimately support different methods.
"""


class MethodNotAllowed(Exception):
    """Raised when a resource exists but the requested method is unsupported."""


class NotFound(Exception):
    """Raised when a route does not exist."""


class Router:
    """Small educational method-aware router."""

    def __init__(self) -> None:
        self.routes: Dict[Tuple[str, str], Callable[..., HTTPResponse]] = {}

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable[..., HTTPResponse],
    ) -> None:
        self.routes[(method.upper(), path)] = handler

    def allowed_methods(self, path: str) -> List[str]:
        return sorted(
            method
            for method, registered_path in self.routes
            if registered_path == path
        )

    def dispatch(self, request: HTTPRequest) -> HTTPResponse:
        key = (request.method, request.target)

        if key in self.routes:
            return self.routes[key]()

        methods = self.allowed_methods(request.target)

        if methods:
            return HTTPResponse(
                status_code=405,
                headers={"Allow": ", ".join(methods)},
                body=json.dumps({"error": "Method Not Allowed"}),
            )

        return HTTPResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Route Not Found"}),
        )


def build_demo_router() -> Router:
    router = Router()

    router.add_route("GET", "/demo", lambda: HTTPResponse(200, body="GET response"))
    router.add_route(
        "POST",
        "/demo",
        lambda: HTTPResponse(201, body="POST response"),
    )
    router.add_route(
        "OPTIONS",
        "/demo",
        lambda: HTTPResponse(
            204,
            headers={"Allow": "GET, POST, OPTIONS"},
        ),
    )

    return router


# ============================================================================
# 15. CONTENT NEGOTIATION
# ============================================================================

"""
HTTP headers communicate representation preferences.

Common request headers include:

    Accept
    Content-Type
    Authorization
    If-None-Match
    If-Match
    If-Modified-Since
    If-Unmodified-Since
    Idempotency-Key

Content-Type describes the media type of the request representation.

Example:

    Content-Type: application/json

Accept expresses which response representations the client can accept.

Example:

    Accept: application/json

These headers serve different purposes:

    Content-Type = what this body is
    Accept       = what representation I want in the response
"""


def choose_representation(accept_header: str) -> str:
    """Choose a simple response media type from an Accept header."""

    accepted = [
        value.strip().lower()
        for value in accept_header.split(",")
    ]

    if "application/json" in accepted:
        return "application/json"

    if "text/plain" in accepted:
        return "text/plain"

    if "*/*" in accepted:
        return "application/json"

    return "application/json"


# ============================================================================
# 16. ETAG AND CONDITIONAL REQUESTS
# ============================================================================

"""
Conditional requests improve correctness and performance.

An ETag identifies a particular representation version.

Example:

    ETag: "abc123"

A client can send:

    If-None-Match: "abc123"

For GET/HEAD, the server may respond:

    304 Not Modified

if the representation has not changed.

For write operations, clients can use:

    If-Match: "abc123"

This can prevent lost updates.

Example:

    Client A reads version 5.
    Client B changes the resource to version 6.
    Client A attempts to PUT based on version 5.

If Client A sends:

    If-Match: "version-5"

the server can reject the write with:

    412 Precondition Failed

This is an optimistic concurrency control mechanism.
"""


def generate_etag(content: str) -> str:
    """Generate a deterministic content-derived ETag-like value."""

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f'"{digest}"'


def conditional_get(
    content: str,
    if_none_match: Optional[str],
) -> HTTPResponse:
    """Simulate conditional GET behavior."""

    etag = generate_etag(content)

    if if_none_match == etag:
        return HTTPResponse(
            status_code=304,
            headers={"ETag": etag},
            body=None,
        )

    return HTTPResponse(
        status_code=200,
        headers={
            "Content-Type": "text/plain",
            "ETag": etag,
        },
        body=content,
    )


def conditional_put(
    current_content: str,
    new_content: str,
    if_match: Optional[str],
) -> HTTPResponse:
    """Simulate an optimistic-concurrency PUT."""

    current_etag = generate_etag(current_content)

    if if_match is None:
        return HTTPResponse(
            status_code=428,
            headers={},
            body=json.dumps({"error": "Precondition required"}),
        )

    if if_match != current_etag:
        return HTTPResponse(
            status_code=412,
            headers={"ETag": current_etag},
            body=json.dumps({"error": "Resource changed"}),
        )

    new_etag = generate_etag(new_content)

    return HTTPResponse(
        status_code=200,
        headers={"ETag": new_etag},
        body=new_content,
    )


# ============================================================================
# 17. IDEMPOTENCY KEYS FOR RETRY-SENSITIVE POST OPERATIONS
# ============================================================================

"""
POST is normally non-idempotent.

Payment systems and other critical operations may need safe retries.

An application can accept:

    Idempotency-Key: 9f7e...

The server stores the result associated with the key.

If the same key is received again with the same logical request, the server
can return the previously generated result rather than creating another
operation.

Important production concerns:

    - keys must have suitable uniqueness
    - request fingerprints can prevent key reuse for different payloads
    - records need expiration/retention rules
    - concurrent requests using the same key need synchronization
    - failures must have clearly defined replay semantics

The mechanism below is a simple educational implementation.
"""


class IdempotencyConflict(Exception):
    """Raised when an idempotency key is reused with a different request."""


class IdempotencyStore:
    """Small in-memory idempotency-key store."""

    def __init__(self) -> None:
        self.entries: Dict[str, Tuple[str, HTTPResponse]] = {}

    @staticmethod
    def fingerprint(payload: Dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def execute(
        self,
        key: str,
        payload: Dict[str, Any],
        operation: Callable[[], HTTPResponse],
    ) -> HTTPResponse:
        fingerprint = self.fingerprint(payload)

        if key in self.entries:
            stored_fingerprint, stored_response = self.entries[key]

            if stored_fingerprint != fingerprint:
                raise IdempotencyConflict(
                    "The same idempotency key was used for a different payload."
                )

            return stored_response

        response = operation()
        self.entries[key] = (fingerprint, response)

        return response


# ============================================================================
# 18. CACHEABILITY AND METHOD SEMANTICS
# ============================================================================

"""
HTTP caching is closely related to method semantics.

GET and HEAD are commonly cacheable when response headers permit caching.

Caching a state-changing POST/PUT/PATCH/DELETE response requires careful
attention to HTTP caching rules and application behavior.

Example response:

    Cache-Control: max-age=60

means a response can be considered fresh for a specified period under the
cache-control semantics.

Important cache-related headers include:

    Cache-Control
    ETag
    Last-Modified
    Expires
    Vary

Vary matters because a response may depend on request headers such as:

    Accept-Encoding
    Accept-Language
    Origin

A cache that ignores relevant variation can return an incorrect response.
"""


def cache_key(
    method: str,
    url: str,
    varying_headers: Optional[Dict[str, str]] = None,
) -> str:
    """Build a simple conceptual cache key."""

    parts = [method.upper(), url]

    if varying_headers:
        for name in sorted(varying_headers):
            parts.append(f"{name.lower()}={varying_headers[name]}")

    return "|".join(parts)


# ============================================================================
# 19. AUTHENTICATION AND AUTHORIZATION
# ============================================================================

"""
Authentication asks:

    Who are you?

Authorization asks:

    What are you allowed to do?

HTTP methods do not replace authorization.

A user who can perform:

    GET /accounts/42

must not automatically be assumed to have permission for:

    DELETE /accounts/42

The server should authorize every sensitive operation.

Common security headers and mechanisms can include:

    Authorization
    WWW-Authenticate
    HTTPS/TLS
    SameSite cookies
    CSRF protections
    Content-Security-Policy
    Strict-Transport-Security

The exact security design depends on the application architecture.
"""


@dataclass
class User:
    user_id: int
    roles: set[str]


def can_perform(user: User, method: str, operation: str) -> bool:
    """Simple role-based authorization demonstration."""

    method = method.upper()

    if operation == "read":
        return "reader" in user.roles or "admin" in user.roles

    if operation == "write":
        return "writer" in user.roles or "admin" in user.roles

    if operation == "delete":
        return method == "DELETE" and "admin" in user.roles

    return False


# ============================================================================
# 20. CSRF AND SAFE METHODS
# ============================================================================

"""
Cross-Site Request Forgery (CSRF) is particularly relevant to browser-based
applications that authenticate using automatically attached credentials such
as cookies.

A crucial design principle is:

    GET must not perform state-changing actions.

Otherwise, a malicious site could potentially cause a victim's browser to
trigger a state-changing GET.

For cookie-authenticated applications, common defenses include:

    - SameSite cookie attributes
    - CSRF tokens
    - Origin checking
    - Referrer checking where appropriate
    - Proper method semantics

CORS does not itself solve CSRF.
"""


def is_state_changing_method(method: str) -> bool:
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


# ============================================================================
# 21. INPUT VALIDATION
# ============================================================================

"""
HTTP method correctness does not make input safe.

Servers should validate:

    method
    path
    query parameters
    headers
    content type
    body schema
    authorization
    resource ownership
    size limits

Validation should occur before business logic.

A useful distinction:

    400 Bad Request
        The request is malformed or invalid at a general request level.

    401 Unauthorized
        Authentication credentials are missing or invalid.

    403 Forbidden
        The server understands the request but refuses authorization.

    404 Not Found
        The target resource is unavailable or the server chooses not to reveal
        its existence.

    405 Method Not Allowed
        The resource exists but does not support that method.

    409 Conflict
        The request conflicts with the current state.

    415 Unsupported Media Type
        The submitted representation format is unsupported.

    422 Unprocessable Content
        The request is syntactically understood but fails semantic validation
        under the API's contract.
"""


def validate_user_payload(payload: Dict[str, Any]) -> List[str]:
    """Validate a small example user representation."""

    errors: List[str] = []

    if not isinstance(payload, dict):
        return ["Payload must be an object."]

    name = payload.get("name")

    if not isinstance(name, str) or not name.strip():
        errors.append("name must be a non-empty string.")

    email = payload.get("email")

    if not isinstance(email, str) or "@" not in email:
        errors.append("email must be a valid-looking email address.")

    return errors


# ============================================================================
# 22. METHOD OVERRIDING
# ============================================================================

"""
Some infrastructure or application frameworks have historically supported
method override mechanisms when clients cannot directly send certain methods.

Examples include:

    X-HTTP-Method-Override: PATCH

or form-based mechanisms.

This is not a reason to treat POST as semantically identical to PATCH.
The application/framework interprets the override and should apply the
intended method semantics consistently.

Method overriding should be carefully controlled because proxies, caches,
security systems, and application code must agree about the effective method.
"""


def effective_method(
    actual_method: str,
    override_header: Optional[str] = None,
) -> str:
    """Resolve an optional application-level method override."""

    if override_header:
        return override_header.upper()

    return actual_method.upper()


# ============================================================================
# 23. RETRIES AND DISTRIBUTED SYSTEMS
# ============================================================================

"""
Retries are common when:

    - a connection times out
    - a proxy returns a transient failure
    - a load balancer fails over
    - a client loses the response after the server processed the request

Idempotent methods are generally safer to retry from an application-semantics
perspective, but "safe to retry" is not identical to "idempotent".

A timeout does not tell the client whether the server processed the request.

For POST:

    Client -> POST
    Server processes operation
    Network fails before response reaches client
    Client retries POST

Without an idempotency strategy, duplicate work may occur.

For PUT:

    Client -> PUT same representation
    Client retries same PUT

The intended resulting resource state can remain the same.

Production retry design should consider:

    - timeout types
    - retryable status codes
    - exponential backoff
    - jitter
    - maximum attempts
    - request deadlines
    - idempotency
    - rate limits
    - server overload

Never blindly retry every request.
"""


def exponential_backoff(
    attempt: int,
    base_seconds: float = 0.5,
    maximum_seconds: float = 30.0,
) -> float:
    """Calculate an exponential backoff delay."""

    delay = base_seconds * (2 ** attempt)
    return min(delay, maximum_seconds)


# ============================================================================
# 24. RATE LIMITING
# ============================================================================

"""
Rate limiting protects APIs from excessive traffic.

Common response:

    429 Too Many Requests

A server may communicate retry information through:

    Retry-After

Rate limiting can be based on:

    - IP address
    - authenticated user
    - API key
    - tenant
    - route
    - method
    - resource

Write operations often require stricter controls because they can have
greater business impact.
"""


class SimpleRateLimiter:
    """A small fixed-window rate limiter for educational purposes."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def allow(self, client_id: str, now: Optional[float] = None) -> bool:
        current_time = time.monotonic() if now is None else now

        timestamps = self.requests.setdefault(client_id, [])

        cutoff = current_time - self.window_seconds
        timestamps[:] = [
            timestamp
            for timestamp in timestamps
            if timestamp > cutoff
        ]

        if len(timestamps) >= self.limit:
            return False

        timestamps.append(current_time)
        return True


# ============================================================================
# 25. REQUEST BODY SIZE AND RESOURCE PROTECTION
# ============================================================================

"""
A production server should impose reasonable limits on request bodies.

Without limits, an attacker or malfunctioning client could send unexpectedly
large payloads and consume memory, CPU, disk, bandwidth, or downstream
resources.

Useful controls include:

    - maximum request body size
    - maximum header size
    - timeout limits
    - connection limits
    - rate limits
    - parsing limits
    - decompression limits

This is particularly important for POST, PUT, and PATCH because they commonly
carry request bodies.
"""


def validate_content_length(
    content_length: Optional[int],
    maximum_bytes: int,
) -> Optional[str]:
    """Validate a declared Content-Length value."""

    if content_length is None:
        return None

    if content_length < 0:
        return "Content-Length cannot be negative."

    if content_length > maximum_bytes:
        return "Request body exceeds configured size limit."

    return None


# ============================================================================
# 26. CORS PREFLIGHT SIMULATION
# ============================================================================

"""
A simplified CORS preflight request can contain:

    Origin: https://client.example
    Access-Control-Request-Method: PATCH
    Access-Control-Request-Headers: Content-Type, Authorization

A server can decide whether the cross-origin request is permitted.

The following simulation intentionally uses an explicit allowlist.
Production CORS configuration should avoid reflecting arbitrary origins.
"""


@dataclass
class CORSConfiguration:
    allowed_origins: set[str]
    allowed_methods: set[str]
    allowed_headers: set[str]


def handle_cors_preflight(
    origin: str,
    requested_method: str,
    requested_headers: Iterable[str],
    config: CORSConfiguration,
) -> HTTPResponse:
    """Evaluate a simplified CORS preflight request."""

    normalized_method = requested_method.upper()
    normalized_headers = {
        header.strip().lower()
        for header in requested_headers
    }

    allowed_headers = {
        header.lower()
        for header in config.allowed_headers
    }

    if origin not in config.allowed_origins:
        return HTTPResponse(
            status_code=403,
            body=json.dumps({"error": "Origin not allowed"}),
        )

    if normalized_method not in config.allowed_methods:
        return HTTPResponse(
            status_code=405,
            headers={"Allow": ", ".join(sorted(config.allowed_methods))},
            body=json.dumps({"error": "Method not allowed"}),
        )

    if not normalized_headers.issubset(allowed_headers):
        return HTTPResponse(
            status_code=403,
            body=json.dumps({"error": "Requested headers not allowed"}),
        )

    return HTTPResponse(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": ", ".join(
                sorted(config.allowed_methods)
            ),
            "Access-Control-Allow-Headers": ", ".join(
                sorted(config.allowed_headers)
            ),
        },
        body=None,
    )


# ============================================================================
# 27. HTTP METHOD COMPARISON
# ============================================================================

def compare_methods() -> None:
    print("\nMETHOD COMPARISON")
    print("=" * 100)

    headers = [
        "Method",
        "Primary purpose",
        "Safe",
        "Idempotent",
        "Typical body",
    ]

    print(
        f"{headers[0]:10}"
        f"{headers[1]:45}"
        f"{headers[2]:8}"
        f"{headers[3]:14}"
        f"{headers[4]:12}"
    )
    print("-" * 100)

    for method, details in METHOD_DEFINITIONS.items():
        idempotent = details["idempotent"]

        if idempotent is NotImplemented:
            idempotent_text = "Depends"
        else:
            idempotent_text = str(idempotent)

        print(
            f"{method:10}"
            f"{details['purpose'][:45]:45}"
            f"{str(details['safe']):8}"
            f"{idempotent_text:14}"
            f"{str(details['typical_body']):12}"
        )


# ============================================================================
# 28. REST-STYLE RESOURCE DESIGN
# ============================================================================

"""
A common resource-oriented API might use:

    GET    /users
    POST   /users
    GET    /users/42
    PUT    /users/42
    PATCH  /users/42
    DELETE /users/42

Instead of action-heavy URLs such as:

    GET  /getUsers
    POST /createUser
    POST /updateUser
    POST /deleteUser

The method communicates the operation while the URI identifies the target
resource.

This is a design convention rather than a requirement that every API must
follow exactly.
"""


def rest_style_examples() -> List[Tuple[str, str, str]]:
    return [
        ("GET", "/users", "List users"),
        ("POST", "/users", "Create a user"),
        ("GET", "/users/42", "Retrieve user 42"),
        ("PUT", "/users/42", "Replace user 42"),
        ("PATCH", "/users/42", "Partially update user 42"),
        ("DELETE", "/users/42", "Delete user 42"),
    ]


# ============================================================================
# 29. COMPLETE REQUEST/RESPONSE SIMULATION
# ============================================================================

class DemoAPI:
    """A complete small API simulator demonstrating the major methods."""

    def __init__(self) -> None:
        self.store = InMemoryStore()

    def handle(self, request: HTTPRequest) -> HTTPResponse:
        parsed = urlparse(request.target)
        path = parsed.path

        if path == "/resources":
            if request.method == "GET":
                return self.get_collection(parsed.query)

            if request.method == "POST":
                return self.post_collection(request)

            if request.method == "HEAD":
                return self.head_collection()

            if request.method == "OPTIONS":
                return self.options_collection()

            return self.method_not_allowed(
                ["GET", "POST", "HEAD", "OPTIONS"]
            )

        prefix = "/resources/"

        if path.startswith(prefix):
            identifier_text = path[len(prefix):]

            if not identifier_text.isdigit():
                return HTTPResponse(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"error": "Invalid resource ID"}),
                )

            resource_id = int(identifier_text)

            if request.method == "GET":
                return self.get_resource(resource_id)

            if request.method == "PUT":
                return self.put_resource(resource_id, request)

            if request.method == "PATCH":
                return self.patch_resource(resource_id, request)

            if request.method == "DELETE":
                return self.delete_resource(resource_id)

            if request.method == "HEAD":
                return self.head_resource(resource_id)

            if request.method == "OPTIONS":
                return self.options_resource()

            return self.method_not_allowed(
                ["GET", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
            )

        return HTTPResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Not Found"}),
        )

    def get_collection(self, query: str) -> HTTPResponse:
        parameters = parse_qs(query)

        resources = self.store.get_all()

        if "name" in parameters:
            desired_name = parameters["name"][0].lower()

            resources = [
                resource
                for resource in resources
                if str(resource.get("name", "")).lower() == desired_name
            ]

        return HTTPResponse(
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "max-age=60",
            },
            body=json.dumps(resources),
        )

    def post_collection(self, request: HTTPRequest) -> HTTPResponse:
        payload = self.parse_json_body(request)

        if payload is None:
            return self.invalid_json_response()

        errors = validate_user_payload(payload)

        if errors:
            return HTTPResponse(
                status_code=422,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"errors": errors}),
            )

        created = self.store.create(payload)

        return HTTPResponse(
            status_code=201,
            headers={
                "Content-Type": "application/json",
                "Location": f"/resources/{created['id']}",
            },
            body=json.dumps(created),
        )

    def get_resource(self, resource_id: int) -> HTTPResponse:
        resource = self.store.get(resource_id)

        if resource is None:
            return HTTPResponse(
                status_code=404,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": "Not Found"}),
            )

        body = json.dumps(resource)
        return HTTPResponse(
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "ETag": generate_etag(body),
            },
            body=body,
        )

    def put_resource(
        self,
        resource_id: int,
        request: HTTPRequest,
    ) -> HTTPResponse:
        payload = self.parse_json_body(request)

        if payload is None:
            return self.invalid_json_response()

        errors = validate_user_payload(payload)

        if errors:
            return HTTPResponse(
                status_code=422,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"errors": errors}),
            )

        existed = self.store.get(resource_id) is not None
        updated = self.store.replace(resource_id, payload)

        return HTTPResponse(
            status_code=200 if existed else 201,
            headers={
                "Content-Type": "application/json",
                "Location": f"/resources/{resource_id}",
            },
            body=json.dumps(updated),
        )

    def patch_resource(
        self,
        resource_id: int,
        request: HTTPRequest,
    ) -> HTTPResponse:
        payload = self.parse_json_body(request)

        if payload is None:
            return self.invalid_json_response()

        if not isinstance(payload, dict):
            return HTTPResponse(
                status_code=422,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": "PATCH body must be an object"}),
            )

        updated = self.store.patch(resource_id, payload)

        if updated is None:
            return HTTPResponse(
                status_code=404,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": "Not Found"}),
            )

        return HTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(updated),
        )

    def delete_resource(self, resource_id: int) -> HTTPResponse:
        if not self.store.delete(resource_id):
            return HTTPResponse(
                status_code=404,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": "Not Found"}),
            )

        return HTTPResponse(
            status_code=204,
            headers={},
            body=None,
        )

    def head_collection(self) -> HTTPResponse:
        body = json.dumps(self.store.get_all())

        return HTTPResponse(
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body.encode("utf-8"))),
            },
            body=None,
        )

    def head_resource(self, resource_id: int) -> HTTPResponse:
        resource = self.store.get(resource_id)

        if resource is None:
            return HTTPResponse(
                status_code=404,
                headers={},
                body=None,
            )

        body = json.dumps(resource)

        return HTTPResponse(
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body.encode("utf-8"))),
                "ETag": generate_etag(body),
            },
            body=None,
        )

    def options_collection(self) -> HTTPResponse:
        return HTTPResponse(
            status_code=204,
            headers={
                "Allow": "GET, POST, HEAD, OPTIONS",
            },
            body=None,
        )

    def options_resource(self) -> HTTPResponse:
        return HTTPResponse(
            status_code=204,
            headers={
                "Allow": "GET, PUT, PATCH, DELETE, HEAD, OPTIONS",
            },
            body=None,
        )

    @staticmethod
    def parse_json_body(request: HTTPRequest) -> Optional[Dict[str, Any]]:
        if request.body is None:
            return None

        content_type = request.headers.get("Content-Type", "").lower()

        if "application/json" not in content_type:
            return None

        try:
            parsed = json.loads(request.body)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        return parsed

    @staticmethod
    def invalid_json_response() -> HTTPResponse:
        return HTTPResponse(
            status_code=400,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Invalid or missing JSON body"}),
        )

    @staticmethod
    def method_not_allowed(methods: List[str]) -> HTTPResponse:
        return HTTPResponse(
            status_code=405,
            headers={"Allow": ", ".join(methods)},
            body=json.dumps({"error": "Method Not Allowed"}),
        )


# ============================================================================
# 30. USING THE DEMO API
# ============================================================================

def demonstrate_demo_api() -> None:
    print("\nCOMPLETE API SIMULATION")
    print("=" * 70)

    api = DemoAPI()

    create_request = HTTPRequest(
        method="POST",
        target="/resources",
        headers={"Content-Type": "application/json"},
        body=json.dumps(
            {
                "name": "Alice",
                "email": "alice@example.com",
            }
        ),
    )

    create_response = api.handle(create_request)

    print("\nPOST response:")
    print(create_response)

    print("\nGET response:")
    print(
        api.handle(
            HTTPRequest(
                method="GET",
                target="/resources/1",
            )
        )
    )

    print("\nPATCH response:")
    print(
        api.handle(
            HTTPRequest(
                method="PATCH",
                target="/resources/1",
                headers={"Content-Type": "application/json"},
                body=json.dumps({"city": "Lucknow"}),
            )
        )
    )

    print("\nPUT response:")
    print(
        api.handle(
            HTTPRequest(
                method="PUT",
                target="/resources/1",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "name": "Alice Updated",
                        "email": "alice.updated@example.com",
                    }
                ),
            )
        )
    )

    print("\nHEAD response:")
    print(
        api.handle(
            HTTPRequest(
                method="HEAD",
                target="/resources/1",
            )
        )
    )

    print("\nOPTIONS response:")
    print(
        api.handle(
            HTTPRequest(
                method="OPTIONS",
                target="/resources/1",
            )
        )
    )

    print("\nDELETE response:")
    print(
        api.handle(
            HTTPRequest(
                method="DELETE",
                target="/resources/1",
            )
        )
    )


# ============================================================================
# 31. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\nEDGE CASES")
    print("=" * 70)

    api = DemoAPI()

    cases = [
        HTTPRequest("GET", "/does-not-exist"),
        HTTPRequest("POST", "/resources", body="not-json"),
        HTTPRequest(
            "POST",
            "/resources",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"name": ""}),
        ),
        HTTPRequest("DELETE", "/resources/999"),
        HTTPRequest("TRACE", "/resources"),
    ]

    for request in cases:
        response = api.handle(request)

        print(
            f"{request.method:8} {request.target:20} "
            f"-> {response.status_code} {response.reason}"
        )


# ============================================================================
# 32. HTTP METHODS AND DATABASE OPERATIONS
# ============================================================================

"""
HTTP methods and database operations are related but not identical.

A common conceptual mapping is:

    GET    -> SELECT
    POST   -> INSERT
    PUT    -> replacement/update
    PATCH  -> partial update
    DELETE -> DELETE

This mapping is useful but incomplete.

HTTP is an application protocol with semantics that exist independently of a
specific database.

For example:

    GET /reports/monthly

could read from:

    - a database
    - a cache
    - an object store
    - a computed result
    - another service

Similarly, POST does not necessarily mean "INSERT a row".
"""


def conceptual_database_mapping() -> Dict[str, str]:
    return {
        "GET": "Read/retrieve",
        "POST": "Submit/process/create subordinate resource",
        "PUT": "Replace/create target representation",
        "PATCH": "Partially modify",
        "DELETE": "Remove",
        "HEAD": "Retrieve metadata without body",
        "OPTIONS": "Discover supported communication options",
    }


# ============================================================================
# 33. METHOD SEMANTICS VS RESPONSE STATUS
# ============================================================================

"""
Method semantics and status codes answer different questions.

Method:

    What kind of operation is requested?

Status:

    What happened when the server processed the request?

For example:

    PUT /users/42

can produce:

    200 OK
    201 Created
    204 No Content
    400 Bad Request
    404 Not Found
    409 Conflict
    412 Precondition Failed
    415 Unsupported Media Type
    422 Unprocessable Content
    500 Internal Server Error

A method does not dictate one single status code.
"""


def explain_status_for_method(method: str) -> List[int]:
    """Return common status codes relevant to an HTTP method."""

    common = {
        "GET": [200, 206, 304, 400, 401, 403, 404, 429, 500, 503],
        "POST": [201, 202, 400, 401, 403, 409, 415, 422, 429, 500, 503],
        "PUT": [200, 201, 204, 400, 401, 403, 404, 409, 412, 415, 422, 500],
        "PATCH": [200, 204, 400, 401, 403, 404, 409, 412, 415, 422, 500],
        "DELETE": [200, 202, 204, 401, 403, 404, 409, 412, 429, 500],
        "HEAD": [200, 304, 400, 401, 403, 404, 500],
        "OPTIONS": [200, 204, 400, 403, 405, 500],
    }

    return common.get(method.upper(), [])


# ============================================================================
# 34. PERFORMANCE CONSIDERATIONS
# ============================================================================

"""
HTTP performance depends on more than method selection.

Relevant factors include:

    - connection reuse
    - HTTP/1.1 persistent connections
    - HTTP/2 multiplexing
    - HTTP/3 over QUIC
    - compression
    - caching
    - conditional requests
    - payload size
    - server processing time
    - database latency
    - network latency
    - TLS overhead
    - connection pooling

HEAD can be useful when metadata is needed without downloading a response
body.

GET caching can dramatically reduce repeated server work.

ETag-based conditional requests can avoid retransmitting unchanged bodies.

PATCH can reduce payload size compared with sending a complete representation
through PUT, but the complexity of patch semantics can increase server-side
processing and validation requirements.

Performance should not be optimized by violating method semantics.
"""


def estimate_transfer_savings(
    full_size_bytes: int,
    partial_size_bytes: int,
) -> Dict[str, float]:
    """Estimate payload reduction from a smaller partial-update body."""

    if full_size_bytes <= 0:
        raise ValueError("full_size_bytes must be positive")

    if partial_size_bytes < 0:
        raise ValueError("partial_size_bytes cannot be negative")

    savings = full_size_bytes - partial_size_bytes
    percentage = savings / full_size_bytes * 100

    return {
        "bytes_saved": savings,
        "percentage_saved": percentage,
    }


# ============================================================================
# 35. SECURITY-SENSITIVE METHOD DESIGN
# ============================================================================

"""
Security principles:

1. Use HTTPS for sensitive traffic.
2. Authenticate protected operations.
3. Authorize every resource operation.
4. Validate request bodies and parameters.
5. Apply request-size limits.
6. Rate-limit abuse-prone endpoints.
7. Do not place secrets in URLs.
8. Treat query strings as potentially logged.
9. Avoid state-changing GET endpoints.
10. Configure CORS explicitly.
11. Protect cookie-authenticated state-changing requests against CSRF.
12. Use conditional requests for concurrency-sensitive writes where useful.
13. Avoid leaking sensitive information through detailed error messages.
14. Log security-relevant events without logging secrets.
15. Apply method restrictions consistently across proxies and application
    servers.

A common security mistake is assuming:

    "DELETE is dangerous, so DELETE is automatically protected."

The actual security control is authorization, not the method name.
"""


def contains_sensitive_url_data(url: str) -> bool:
    """
    Demonstrate a simple warning heuristic.

    Real security systems should not rely on this function. Secrets should
    not be placed in URLs in the first place.
    """

    parsed = urlparse(url)
    sensitive_names = {
        "password",
        "passwd",
        "token",
        "access_token",
        "api_key",
        "secret",
    }

    parameters = parse_qs(parsed.query)

    return any(name.lower() in sensitive_names for name in parameters)


# ============================================================================
# 36. OBSERVABILITY
# ============================================================================

"""
Production HTTP services need observability.

Useful dimensions include:

    - method
    - route
    - status code
    - latency
    - request ID
    - authenticated principal or tenant identifier
    - error category
    - upstream dependency
    - response size

Avoid logging:

    - passwords
    - authentication tokens
    - session secrets
    - payment-card data
    - sensitive personal information

Metrics should distinguish:

    GET /users/{id}

from a literal path containing thousands of different IDs where possible.

Route templates produce more useful aggregation.
"""


@dataclass
class RequestMetric:
    method: str
    route: str
    status_code: int
    latency_ms: float


def summarize_metrics(metrics: List[RequestMetric]) -> Dict[str, Any]:
    """Produce basic latency and status statistics."""

    if not metrics:
        return {
            "count": 0,
            "average_latency_ms": 0.0,
            "error_rate": 0.0,
        }

    average_latency = sum(
        metric.latency_ms
        for metric in metrics
    ) / len(metrics)

    errors = sum(
        metric.status_code >= 400
        for metric in metrics
    )

    return {
        "count": len(metrics),
        "average_latency_ms": average_latency,
        "error_rate": errors / len(metrics),
    }


# ============================================================================
# 37. TESTS
# ============================================================================

class HTTPMethodTests(unittest.TestCase):
    """Unit tests for method semantics and the educational API."""

    def test_safe_methods(self) -> None:
        self.assertTrue(is_safe_method("GET"))
        self.assertTrue(is_safe_method("HEAD"))
        self.assertTrue(is_safe_method("OPTIONS"))
        self.assertFalse(is_safe_method("POST"))
        self.assertFalse(is_safe_method("DELETE"))

    def test_put_idempotency(self) -> None:
        state = {"name": "Alice"}

        first = apply_put(state, {"name": "Bob"})
        second = apply_put(first, {"name": "Bob"})

        self.assertEqual(first, second)

    def test_increment_patch_is_not_idempotent(self) -> None:
        state = {"balance": 100}

        first = apply_increment_patch(state, 10)
        second = apply_increment_patch(first, 10)

        self.assertNotEqual(first, second)

    def test_set_patch_is_idempotent(self) -> None:
        state = {"balance": 100}

        first = apply_set_patch(state, 200)
        second = apply_set_patch(first, 200)

        self.assertEqual(first, second)

    def test_post_creates_resource(self) -> None:
        api = DemoAPI()

        response = api.handle(
            HTTPRequest(
                "POST",
                "/resources",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "name": "Alice",
                        "email": "alice@example.com",
                    }
                ),
            )
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("Location", response.headers)

    def test_get_missing_resource(self) -> None:
        api = DemoAPI()

        response = api.handle(
            HTTPRequest("GET", "/resources/999")
        )

        self.assertEqual(response.status_code, 404)

    def test_patch_preserves_other_fields(self) -> None:
        api = DemoAPI()

        create_response = api.handle(
            HTTPRequest(
                "POST",
                "/resources",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "name": "Alice",
                        "email": "alice@example.com",
                    }
                ),
            )
        )

        self.assertEqual(create_response.status_code, 201)

        patch_response = api.handle(
            HTTPRequest(
                "PATCH",
                "/resources/1",
                headers={"Content-Type": "application/json"},
                body=json.dumps({"city": "Lucknow"}),
            )
        )

        self.assertEqual(patch_response.status_code, 200)

        payload = json.loads(patch_response.body)
        self.assertEqual(payload["name"], "Alice")
        self.assertEqual(payload["city"], "Lucknow")

    def test_head_has_no_body(self) -> None:
        api = DemoAPI()

        api.handle(
            HTTPRequest(
                "POST",
                "/resources",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "name": "Alice",
                        "email": "alice@example.com",
                    }
                ),
            )
        )

        response = api.handle(
            HTTPRequest("HEAD", "/resources/1")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.body)
        self.assertIn("ETag", response.headers)

    def test_options_reports_allow(self) -> None:
        api = DemoAPI()

        response = api.handle(
            HTTPRequest("OPTIONS", "/resources/1")
        )

        self.assertEqual(response.status_code, 204)
        self.assertIn("GET", response.headers["Allow"])
        self.assertIn("DELETE", response.headers["Allow"])

    def test_method_not_allowed(self) -> None:
        api = DemoAPI()

        response = api.handle(
            HTTPRequest("POST", "/resources/1")
        )

        self.assertEqual(response.status_code, 405)
        self.assertIn("Allow", response.headers)

    def test_idempotency_key_replays_result(self) -> None:
        idempotency_store = IdempotencyStore()
        executions = {"count": 0}

        def operation() -> HTTPResponse:
            executions["count"] += 1
            return HTTPResponse(201, body="created")

        first = idempotency_store.execute(
            "key-123",
            {"amount": 100},
            operation,
        )

        second = idempotency_store.execute(
            "key-123",
            {"amount": 100},
            operation,
        )

        self.assertEqual(first.body, second.body)
        self.assertEqual(executions["count"], 1)

    def test_idempotency_key_conflict(self) -> None:
        idempotency_store = IdempotencyStore()

        idempotency_store.execute(
            "key-123",
            {"amount": 100},
            lambda: HTTPResponse(201, body="created"),
        )

        with self.assertRaises(IdempotencyConflict):
            idempotency_store.execute(
                "key-123",
                {"amount": 200},
                lambda: HTTPResponse(201, body="created"),
            )

    def test_conditional_get(self) -> None:
        content = "same content"

        first = conditional_get(content, None)
        second = conditional_get(
            content,
            first.headers["ETag"],
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 304)

    def test_conditional_put_rejects_stale_version(self) -> None:
        response = conditional_put(
            current_content="version 2",
            new_content="version 3",
            if_match=generate_etag("version 1"),
        )

        self.assertEqual(response.status_code, 412)


# ============================================================================
# 38. RUNNING TESTS
# ============================================================================

def run_tests() -> None:
    """Run the educational test suite."""

    print("\nRUNNING UNIT TESTS")
    print("=" * 70)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        HTTPMethodTests
    )

    result = unittest.TextTestRunner(
        verbosity=1
    ).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


# ============================================================================
# 39. PRACTICAL EXAMPLES
# ============================================================================

def demonstrate_practical_examples() -> None:
    print("\nPRACTICAL EXAMPLES")
    print("=" * 70)

    examples = [
        ("GET", "/products", "Retrieve products"),
        ("GET", "/products/101", "Retrieve one product"),
        ("POST", "/products", "Create a product"),
        ("PUT", "/products/101", "Replace product 101"),
        ("PATCH", "/products/101", "Change selected product fields"),
        ("DELETE", "/products/101", "Delete product 101"),
        ("HEAD", "/products/101", "Inspect metadata"),
        ("OPTIONS", "/products/101", "Discover supported methods"),
    ]

    for method, target, explanation in examples:
        print(f"{method:8} {target:25} -> {explanation}")


# ============================================================================
# 40. COMPARISON: PUT VS PATCH
# ============================================================================

def demonstrate_put_vs_patch() -> None:
    print("\nPUT VS PATCH")
    print("=" * 70)

    original = {
        "name": "Alice",
        "email": "alice@example.com",
        "city": "Delhi",
    }

    put_payload = {
        "name": "Alice Updated",
        "email": "alice.updated@example.com",
    }

    patch_payload = {
        "city": "Lucknow",
    }

    put_result = apply_put(original, put_payload)
    patch_result = dict(original)
    patch_result.update(patch_payload)

    print("Original:")
    print(original)

    print("\nPUT replacement:")
    print(put_result)

    print("\nPATCH partial update:")
    print(patch_result)


# ============================================================================
# 41. COMPARISON: POST VS PUT
# ============================================================================

def demonstrate_post_vs_put() -> None:
    print("\nPOST VS PUT")
    print("=" * 70)

    print(
        "POST commonly asks the server to process a submitted representation "
        "and may result in a newly created subordinate resource."
    )

    print(
        "PUT targets a known URI and requests creation or replacement of "
        "that target representation."
    )

    print(
        "POST is generally non-idempotent; PUT is idempotent when its "
        "operation follows HTTP replacement semantics."
    )


# ============================================================================
# 42. METHOD VALIDATION
# ============================================================================

def validate_http_method(method: str) -> str:
    """
    Validate a method against the major methods covered by this script.

    HTTP itself supports an extensible method namespace, so rejecting every
    method not in this set is an application policy rather than a universal
    HTTP rule.
    """

    normalized = method.upper()

    if normalized not in ALLOWED_METHODS:
        raise ValueError(
            f"Method {normalized!r} is not supported by this educational API."
        )

    return normalized


# ============================================================================
# 43. CUSTOM METHOD AWARENESS
# ============================================================================

"""
HTTP permits extension methods.

Therefore, the following statement is too broad:

    "HTTP only has GET, POST, PUT, PATCH, DELETE, HEAD and OPTIONS."

Those are important and commonly encountered methods, but HTTP has additional
standardized methods such as:

    CONNECT
    TRACE

and extension methods can exist.

CONNECT is commonly associated with establishing a tunnel through a proxy.

TRACE is intended for diagnostic loop-back behavior and is frequently disabled
in production configurations when not needed because of security concerns.

An application should distinguish:

    - what HTTP defines
    - what the framework supports
    - what the API chooses to expose
"""


# ============================================================================
# 44. PROXY AND LOAD-BALANCER CONSIDERATIONS
# ============================================================================

"""
A production HTTP request can pass through:

    Client
      |
      v
    CDN
      |
      v
    WAF
      |
      v
    Load Balancer
      |
      v
    Reverse Proxy
      |
      v
    Application
      |
      v
    Database

Every layer should agree about:

    - allowed methods
    - URL normalization
    - authentication headers
    - forwarding headers
    - request size
    - timeouts
    - caching
    - CORS behavior
    - method overrides

A dangerous configuration occurs when one layer interprets a request
differently from another.

For example, if a security layer authorizes the apparent method while an
application interprets an override header as another method, authorization
can become inconsistent.
"""


# ============================================================================
# 45. TIMEOUTS
# ============================================================================

def classify_timeout_scenario(
    method: str,
    request_processed: Optional[bool],
) -> str:
    """
    Explain retry implications for a simplified timeout scenario.

    None means the client cannot determine whether the operation completed.
    """

    method = method.upper()

    if request_processed is True:
        return (
            "The server processed the request. A retry must account for "
            "possible duplicate processing."
        )

    if request_processed is False:
        return (
            "The server did not process the request. A retry may be possible "
            "subject to normal retry policy."
        )

    if method in {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}:
        return (
            "Processing status is unknown. The method is idempotent by "
            "semantics, but retry policy must still consider application "
            "effects and infrastructure behavior."
        )

    return (
        "Processing status is unknown. For POST, use an application-level "
        "idempotency strategy when duplicate processing is unacceptable."
    )


# ============================================================================
# 46. ERROR HANDLING DESIGN
# ============================================================================

def error_response(
    status_code: int,
    error_code: str,
    message: str,
) -> HTTPResponse:
    """Create a consistent JSON error representation."""

    return HTTPResponse(
        status_code=status_code,
        headers={
            "Content-Type": "application/json",
        },
        body=json.dumps(
            {
                "error": {
                    "code": error_code,
                    "message": message,
                }
            }
        ),
    )


# ============================================================================
# 47. HTTP HEADER NORMALIZATION
# ============================================================================

def normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Normalize header names.

    HTTP field names are case-insensitive. This function normalizes names to
    lowercase for predictable application processing.
    """

    return {
        name.lower(): value
        for name, value in headers.items()
    }


# ============================================================================
# 48. JSON SERIALIZATION
# ============================================================================

def serialize_json(data: Any) -> str:
    """Serialize JSON deterministically for hashing or comparison."""

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    )


# ============================================================================
# 49. SECURITY: SAFE URL PARAMETER BUILDING
# ============================================================================

def demonstrate_url_encoding() -> None:
    print("\nSAFE QUERY PARAMETER ENCODING")
    print("=" * 70)

    url = build_query_url(
        "https://example.com/search",
        {
            "q": "HTTP methods & semantics",
            "page": 2,
        },
    )

    print(url)


# ============================================================================
# 50. SECURITY: METHOD ALLOWLIST
# ============================================================================

def method_allowlist(
    requested_method: str,
    allowed_methods: Iterable[str],
) -> HTTPResponse:
    """Return a method-specific authorization-style decision."""

    normalized_requested = requested_method.upper()
    normalized_allowed = {
        method.upper()
        for method in allowed_methods
    }

    if normalized_requested not in normalized_allowed:
        return HTTPResponse(
            status_code=405,
            headers={
                "Allow": ", ".join(sorted(normalized_allowed)),
            },
            body=json.dumps({"error": "Method Not Allowed"}),
        )

    return HTTPResponse(
        status_code=200,
        headers={},
        body=json.dumps({"allowed": True}),
    )


# ============================================================================
# 51. PERFORMANCE: CACHE SIMULATION
# ============================================================================

@dataclass
class CacheEntry:
    response: HTTPResponse
    expires_at: float


class SimpleCache:
    """A tiny educational response cache."""

    def __init__(self) -> None:
        self.entries: Dict[str, CacheEntry] = {}

    def put(
        self,
        key: str,
        response: HTTPResponse,
        ttl_seconds: float,
        now: Optional[float] = None,
    ) -> None:
        current_time = time.monotonic() if now is None else now

        self.entries[key] = CacheEntry(
            response=response,
            expires_at=current_time + ttl_seconds,
        )

    def get(
        self,
        key: str,
        now: Optional[float] = None,
    ) -> Optional[HTTPResponse]:
        current_time = time.monotonic() if now is None else now

        entry = self.entries.get(key)

        if entry is None:
            return None

        if current_time >= entry.expires_at:
            del self.entries[key]
            return None

        return entry.response


# ============================================================================
# 52. METHOD DECISION HELPER
# ============================================================================

def choose_method_for_operation(
    operation: str,
    known_resource_uri: bool = False,
) -> str:
    """
    Provide a conceptual method-selection rule.

    This is a teaching aid, not a universal API generator.
    """

    normalized = operation.lower()

    if normalized == "retrieve":
        return "GET"

    if normalized == "inspect-metadata":
        return "HEAD"

    if normalized == "discover-options":
        return "OPTIONS"

    if normalized == "create" and not known_resource_uri:
        return "POST"

    if normalized == "create-or-replace" and known_resource_uri:
        return "PUT"

    if normalized == "replace":
        return "PUT"

    if normalized == "partial-update":
        return "PATCH"

    if normalized == "delete":
        return "DELETE"

    raise ValueError(f"Unknown operation: {operation}")


# ============================================================================
# 53. COMPLETE STUDY DEMONSTRATION
# ============================================================================

def run_all_demonstrations() -> None:
    """Run the educational examples in logical learning order."""

    print("\n" + "=" * 90)
    print("HTTP METHODS COMPLETE STUDY SCRIPT")
    print("=" * 90)

    print_method_reference()
    demonstrate_safe_methods()
    demonstrate_idempotency()

    print("\nURL PARSING")
    print("=" * 50)
    example_url = (
        "https://example.com:443/api/users/42"
        "?active=true&sort=name#profile"
    )
    print(parse_url_example(example_url))

    print("\nSTATUS CLASSIFICATION")
    print("=" * 50)
    for status in [200, 201, 204, 301, 304, 400, 401, 403, 404, 405, 429, 500]:
        print(status, "->", classify_status(status))

    compare_methods()
    demonstrate_post_vs_put()
    demonstrate_put_vs_patch()
    demonstrate_practical_examples()
    demonstrate_edge_cases()
    demonstrate_url_encoding()

    print("\nETAG EXAMPLE")
    print("=" * 70)
    first = conditional_get("Hello HTTP", None)
    print("First request:", first)
    second = conditional_get(
        "Hello HTTP",
        first.headers["ETag"],
    )
    print("Conditional request:", second)

    print("\nCORS PREFLIGHT EXAMPLE")
    print("=" * 70)

    cors_config = CORSConfiguration(
        allowed_origins={"https://client.example"},
        allowed_methods={"GET", "POST", "PATCH"},
        allowed_headers={"Content-Type", "Authorization"},
    )

    cors_response = handle_cors_preflight(
        origin="https://client.example",
        requested_method="PATCH",
        requested_headers=["Content-Type", "Authorization"],
        config=cors_config,
    )

    print(cors_response)

    print("\nRETRY BACKOFF")
    print("=" * 70)

    for attempt in range(5):
        print(
            f"attempt={attempt}, "
            f"delay={exponential_backoff(attempt):.2f}s"
        )

    print("\nREQUEST SIZE VALIDATION")
    print("=" * 70)
    print(
        validate_content_length(
            content_length=1024,
            maximum_bytes=2048,
        )
    )
    print(
        validate_content_length(
            content_length=4096,
            maximum_bytes=2048,
        )
    )

    print("\nMETRICS")
    print("=" * 70)

    metrics = [
        RequestMetric("GET", "/users/{id}", 200, 20),
        RequestMetric("GET", "/users/{id}", 200, 30),
        RequestMetric("POST", "/users", 201, 45),
        RequestMetric("DELETE", "/users/{id}", 204, 25),
        RequestMetric("GET", "/users/{id}", 404, 15),
    ]

    print(summarize_metrics(metrics))

    demonstrate_demo_api()


# ============================================================================
# 54. MAIN PROGRAM
# ============================================================================

def main() -> None:
    """
    Main entry point.

    The demonstrations run first. The unit tests run last so that the file
    functions both as a tutorial and as an executable correctness check.
    """

    run_all_demonstrations()
    run_tests()


if __name__ == "__main__":
    main()
