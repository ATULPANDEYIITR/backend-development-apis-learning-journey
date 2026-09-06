"""
HTTP STATUS CODES: BEGINNER TO ADVANCED
=======================================

A self-contained executable study guide covering:

- HTTP fundamentals relevant to status codes
- 1xx informational responses
- 2xx successful responses
- 3xx redirection responses
- 4xx client errors
- 5xx server errors
- Common status codes and their semantics
- Choosing appropriate status codes
- Headers, methods, idempotency, caching, and conditional requests
- Authentication and authorization errors
- Validation and resource lifecycle semantics
- Retry behavior and rate limiting
- Error response design
- REST API design considerations
- Security considerations
- Debugging with cURL
- Postman-oriented request/response concepts
- Python HTTP client demonstrations
- A small HTTP server implemented with the Python standard library
- Automated assertions and a miniature status-code decision engine
- Edge cases, anti-patterns, and production considerations

The script intentionally uses the Python standard library wherever possible.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from enum import Enum, IntEnum
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


# ============================================================================
# 1. HTTP STATUS CODE FUNDAMENTALS
# ============================================================================

print("=" * 78)
print("HTTP STATUS CODES: BEGINNER TO ADVANCED")
print("=" * 78)


class HTTPStatus(IntEnum):
    """
    A compact subset of the HTTP status-code registry.

    IntEnum allows status codes to behave like integers while still giving
    meaningful names to the values.
    """

    CONTINUE = 100
    SWITCHING_PROTOCOLS = 101

    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    PARTIAL_CONTENT = 206

    MULTIPLE_CHOICES = 300
    MOVED_PERMANENTLY = 301
    FOUND = 302
    SEE_OTHER = 303
    NOT_MODIFIED = 304
    TEMPORARY_REDIRECT = 307
    PERMANENT_REDIRECT = 308

    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    NOT_ACCEPTABLE = 406
    CONFLICT = 409
    GONE = 410
    LENGTH_REQUIRED = 411
    PRECONDITION_FAILED = 412
    CONTENT_TOO_LARGE = 413
    UNSUPPORTED_MEDIA_TYPE = 415
    UNPROCESSABLE_CONTENT = 422
    TOO_MANY_REQUESTS = 429

    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504
    HTTP_VERSION_NOT_SUPPORTED = 505


STATUS_DESCRIPTIONS: Dict[int, str] = {
    100: "Continue",
    101: "Switching Protocols",
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    206: "Partial Content",
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Content Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version Not Supported",
}


def status_class(code: int) -> str:
    """Return the broad HTTP status class for a numeric status code."""
    if 100 <= code <= 199:
        return "1xx Informational"
    if 200 <= code <= 299:
        return "2xx Successful"
    if 300 <= code <= 399:
        return "3xx Redirection"
    if 400 <= code <= 499:
        return "4xx Client Error"
    if 500 <= code <= 599:
        return "5xx Server Error"
    return "Non-standard / Invalid HTTP status code"


def explain_status(code: int) -> str:
    """
    Return a readable explanation.

    Unknown values inside a valid class are still legitimate possibilities:
    HTTP defines classes, and specific status codes can be extended.
    """
    description = STATUS_DESCRIPTIONS.get(code, "Unknown or less commonly used status")
    return f"{code} {description} [{status_class(code)}]"


print("\n1. STATUS CODE CLASSES")
for code in (100, 200, 300, 400, 500):
    print(explain_status(code))

print("\nImportant principle:")
print("The first digit communicates the broad meaning of the response.")
print("The complete three-digit code communicates the specific semantics.")


# ============================================================================
# 2. HTTP REQUEST / RESPONSE MODEL
# ============================================================================

print("\n" + "=" * 78)
print("2. HTTP REQUEST / RESPONSE MODEL")
print("=" * 78)

request_example = {
    "method": "GET",
    "target": "/users/42",
    "headers": {
        "Host": "api.example.com",
        "Accept": "application/json",
        "Authorization": "Bearer <token>",
    },
    "body": None,
}

response_example = {
    "status_line": "HTTP/1.1 200 OK",
    "headers": {
        "Content-Type": "application/json",
        "Cache-Control": "private, max-age=60",
    },
    "body": '{"id": 42, "name": "Asha"}',
}

print("Request:")
print(json.dumps(request_example, indent=2))

print("\nResponse:")
print(json.dumps(response_example, indent=2))

print(
    """
Status codes are metadata about the result of processing a request.
They do not replace the response body, headers, or HTTP method.

A useful mental model is:

    HTTP method + target + headers + body
                         |
                         v
                    server logic
                         |
                         v
        status code + headers + optional body
"""
)


# ============================================================================
# 3. 1XX INFORMATIONAL RESPONSES
# ============================================================================

print("\n" + "=" * 78)
print("3. 1XX INFORMATIONAL RESPONSES")
print("=" * 78)

informational_codes = {
    100: "Continue",
    101: "Switching Protocols",
    102: "Processing (WebDAV)",
    103: "Early Hints",
}

for code, description in informational_codes.items():
    print(f"{code}: {description}")

print(
    """
1xx responses indicate that the request has been received and processing
continues.

100 Continue:
    Commonly associated with Expect: 100-continue for large request bodies.

101 Switching Protocols:
    Indicates that the server is switching to another protocol when requested
    and supported.

103 Early Hints:
    Allows a server to provide preliminary header information before the final
    response.

1xx responses are generally not the final application result.
"""
)


# ============================================================================
# 4. 2XX SUCCESSFUL RESPONSES
# ============================================================================

print("\n" + "=" * 78)
print("4. 2XX SUCCESSFUL RESPONSES")
print("=" * 78)

successful_codes = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    203: "Non-Authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
}

for code, description in successful_codes.items():
    print(f"{code}: {description}")

print(
    """
200 OK
-------
Use when the request succeeded and the response contains the normal result.

Typical examples:
    GET /users/42 -> 200
    POST /search -> 200 when the operation is complete and returns results
    PUT /users/42 -> 200 when the updated representation is returned

201 Created
-----------
Use when the request successfully creates a resource.

A well-designed API commonly returns:
    201 Created
    Location: /users/42

The Location header identifies the newly created resource.

202 Accepted
------------
Use when the request has been accepted for processing but processing is not
complete.

Example:
    POST /reports -> 202

The server may return a job identifier that the client can use to inspect
processing status.

204 No Content
--------------
Use when the request succeeded and there is intentionally no response body.

Common examples:
    DELETE /users/42 -> 204
    PUT /settings -> 204

204 does not mean failure. It means successful completion without a response
representation.

206 Partial Content
-------------------
Used for successful range requests, especially resumable downloads and media
delivery.
"""
)


# ============================================================================
# 5. 3XX REDIRECTION RESPONSES
# ============================================================================

print("\n" + "=" * 78)
print("5. 3XX REDIRECTION RESPONSES")
print("=" * 78)

redirect_codes = {
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
}

for code, description in redirect_codes.items():
    print(f"{code}: {description}")

print(
    """
301 Moved Permanently
--------------------
The resource has a new permanent URI.

302 Found
---------
Historically used for temporary redirection. Client behavior around the
original method has legacy interoperability considerations.

303 See Other
-------------
Useful after an operation when the client should retrieve another resource
using GET.

304 Not Modified
----------------
Used with conditional requests and caching. It tells the client that its
cached representation can still be used.

307 Temporary Redirect
----------------------
Temporary redirect that preserves the original HTTP method and request body.

308 Permanent Redirect
---------------------
Permanent redirect that preserves the original HTTP method and request body.

Important distinction:
    301/302 have historical method-rewriting behavior in clients.
    307/308 explicitly preserve the method.
"""
)


# ============================================================================
# 6. 4XX CLIENT ERRORS
# ============================================================================

print("\n" + "=" * 78)
print("6. 4XX CLIENT ERRORS")
print("=" * 78)

client_error_codes = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Content Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    429: "Too Many Requests",
}

for code, description in client_error_codes.items():
    print(f"{code}: {description}")

print(
    """
400 Bad Request
---------------
The request is malformed or cannot be processed as a valid request.

Examples:
    invalid JSON syntax
    malformed query parameters
    invalid request framing

401 Unauthorized
----------------
Despite its name, this usually means that authentication is missing or
invalid.

Examples:
    missing Bearer token
    expired access token
    invalid credentials

403 Forbidden
-------------
The server understood the request but refuses to authorize it.

Example:
    authenticated user attempts an administrator-only operation.

404 Not Found
-------------
The requested resource cannot be found or is intentionally not disclosed.

405 Method Not Allowed
----------------------
The resource exists, but the HTTP method is not supported for that resource.

A server should generally include:
    Allow: GET, HEAD

409 Conflict
------------
The request conflicts with the current state of the resource.

Examples:
    duplicate username
    version conflict
    state transition conflict

410 Gone
--------
The resource was intentionally removed and is expected to remain unavailable.

412 Precondition Failed
-----------------------
A condition supplied by the client was not satisfied.

413 Content Too Large
---------------------
The request content exceeds a server-defined limit.

415 Unsupported Media Type
--------------------------
The request body uses an unsupported media type.

Example:
    Content-Type: application/xml
    while the endpoint only accepts application/json

422 Unprocessable Content
-------------------------
The request is syntactically valid, but its content cannot be processed
according to application rules.

Example:
    {"email": "not-an-email"}

429 Too Many Requests
---------------------
The client has exceeded a rate limit.

A Retry-After header may communicate when retrying is appropriate.
"""
)


# ============================================================================
# 7. 401 VS 403
# ============================================================================

print("\n" + "=" * 78)
print("7. 401 VS 403")
print("=" * 78)

auth_examples = [
    ("No token supplied", 401),
    ("Expired access token", 401),
    ("Valid token but insufficient role", 403),
    ("Authenticated user lacks permission", 403),
]

for scenario, code in auth_examples:
    print(f"{scenario:45} -> {explain_status(code)}")

print(
    """
A useful distinction:

401:
    "You have not successfully authenticated."

403:
    "I know who you are, but you are not permitted to do this."

Security-sensitive systems sometimes deliberately return 404 instead of 403
to avoid revealing whether a protected resource exists.
"""
)


# ============================================================================
# 8. 404 VS 410
# ============================================================================

print("\n" + "=" * 78)
print("8. 404 VS 410")
print("=" * 78)

print("404 -> Resource is not currently available at the requested URI.")
print("410 -> Resource was intentionally removed and is expected to remain gone.")

print(
    """
404 is the normal choice when the server does not want to make a stronger
statement about permanent removal.

410 is more explicit and can be useful when an API or website has deliberately
retired a resource.
"""
)


# ============================================================================
# 9. 400 VS 422
# ============================================================================

print("\n" + "=" * 78)
print("9. 400 VS 422")
print("=" * 78)


def validate_user_payload(payload: Mapping[str, Any]) -> Tuple[bool, List[str]]:
    """
    Application-level validation.

    A syntactically valid JSON document can still fail domain validation.
    """
    errors: List[str] = []

    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        errors.append("name must be a non-empty string")

    email = payload.get("email")
    if not isinstance(email, str) or "@" not in email:
        errors.append("email must contain @")

    age = payload.get("age")
    if not isinstance(age, int) or isinstance(age, bool):
        errors.append("age must be an integer")
    elif age < 18:
        errors.append("age must be at least 18")

    return len(errors) == 0, errors


valid_json_invalid_domain = {
    "name": "Ravi",
    "email": "invalid-email",
    "age": 16,
}

is_valid, validation_errors = validate_user_payload(valid_json_invalid_domain)

print("Payload:")
print(json.dumps(valid_json_invalid_domain, indent=2))
print("Validation successful:", is_valid)
print("Validation errors:", validation_errors)
print("A common API choice for this situation is HTTP 422.")

print(
    """
The exact boundary between 400 and 422 depends on API conventions.

A practical convention is:

400:
    The request itself is malformed or cannot be interpreted correctly.

422:
    The request is structurally valid but fails semantic/domain validation.

Consistency inside one API matters more than blindly following one convention.
"""
)


# ============================================================================
# 10. 5XX SERVER ERRORS
# ============================================================================

print("\n" + "=" * 78)
print("10. 5XX SERVER ERRORS")
print("=" * 78)

server_error_codes = {
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version Not Supported",
}

for code, description in server_error_codes.items():
    print(f"{code}: {description}")

print(
    """
500 Internal Server Error
------------------------
A generic unexpected server-side failure.

Do not expose stack traces, database credentials, SQL statements, or internal
architecture to clients.

501 Not Implemented
-------------------
The server does not support the functionality required to fulfill the request.

502 Bad Gateway
---------------
A gateway or proxy received an invalid response from an upstream server.

503 Service Unavailable
-----------------------
The service is currently unable to handle the request, commonly because of
temporary overload, maintenance, or dependency unavailability.

504 Gateway Timeout
-------------------
A gateway or proxy did not receive a timely response from an upstream server.

A key diagnostic distinction:

    502 -> upstream response was invalid
    504 -> upstream response did not arrive in time
    503 -> service is temporarily unable to serve the request
"""
)


# ============================================================================
# 11. COMPLETE STATUS-CODE REFERENCE TABLE
# ============================================================================

print("\n" + "=" * 78)
print("11. PRACTICAL STATUS-CODE REFERENCE")
print("=" * 78)

practical_reference = [
    (200, "Successful read or completed operation"),
    (201, "Resource successfully created"),
    (202, "Accepted for asynchronous processing"),
    (204, "Successful operation with no response body"),
    (301, "Permanent redirect"),
    (302, "Temporary/legacy redirect semantics"),
    (303, "See another resource, commonly via GET"),
    (304, "Cached representation is still valid"),
    (307, "Temporary redirect preserving method"),
    (308, "Permanent redirect preserving method"),
    (400, "Malformed or invalid request"),
    (401, "Authentication missing or invalid"),
    (403, "Authenticated but not permitted"),
    (404, "Resource not found or deliberately undisclosed"),
    (405, "Method not supported by resource"),
    (409, "Conflict with current resource state"),
    (410, "Resource intentionally gone"),
    (412, "Client precondition failed"),
    (413, "Request body/content too large"),
    (415, "Unsupported request media type"),
    (422, "Semantically invalid content"),
    (429, "Rate limit exceeded"),
    (500, "Unexpected server-side failure"),
    (501, "Functionality not implemented"),
    (502, "Bad upstream response"),
    (503, "Temporary service unavailability"),
    (504, "Upstream timeout"),
]

for code, meaning in practical_reference:
    print(f"{code:3} | {meaning}")


# ============================================================================
# 12. STATUS CODE DECISION ENGINE
# ============================================================================

print("\n" + "=" * 78)
print("12. STATUS CODE DECISION ENGINE")
print("=" * 78)


class RequestOutcome(Enum):
    SUCCESS = "success"
    CREATED = "created"
    ACCEPTED = "accepted"
    NO_CONTENT = "no_content"
    MALFORMED = "malformed"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    VALIDATION_FAILED = "validation_failed"
    UNSUPPORTED_MEDIA = "unsupported_media"
    RATE_LIMITED = "rate_limited"
    SERVER_FAILURE = "server_failure"
    BAD_UPSTREAM = "bad_upstream"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UPSTREAM_TIMEOUT = "upstream_timeout"


def choose_status_code(outcome: RequestOutcome) -> int:
    """
    Convert an application-level outcome into an HTTP status code.

    Keeping this mapping explicit makes API behavior easier to test.
    """
    mapping = {
        RequestOutcome.SUCCESS: 200,
        RequestOutcome.CREATED: 201,
        RequestOutcome.ACCEPTED: 202,
        RequestOutcome.NO_CONTENT: 204,
        RequestOutcome.MALFORMED: 400,
        RequestOutcome.UNAUTHENTICATED: 401,
        RequestOutcome.FORBIDDEN: 403,
        RequestOutcome.NOT_FOUND: 404,
        RequestOutcome.METHOD_NOT_ALLOWED: 405,
        RequestOutcome.CONFLICT: 409,
        RequestOutcome.VALIDATION_FAILED: 422,
        RequestOutcome.UNSUPPORTED_MEDIA: 415,
        RequestOutcome.RATE_LIMITED: 429,
        RequestOutcome.SERVER_FAILURE: 500,
        RequestOutcome.BAD_UPSTREAM: 502,
        RequestOutcome.SERVICE_UNAVAILABLE: 503,
        RequestOutcome.UPSTREAM_TIMEOUT: 504,
    }
    return mapping[outcome]


for outcome in RequestOutcome:
    code = choose_status_code(outcome)
    print(f"{outcome.value:24} -> {code}")


# ============================================================================
# 13. HTTP METHODS AND STATUS CODES
# ============================================================================

print("\n" + "=" * 78)
print("13. HTTP METHODS AND STATUS CODES")
print("=" * 78)

method_examples = {
    "GET": {
        "purpose": "Retrieve a representation",
        "typical_success": [200, 206, 304],
        "common_errors": [400, 401, 403, 404, 405, 429, 500],
    },
    "POST": {
        "purpose": "Create a resource or trigger processing",
        "typical_success": [200, 201, 202, 204],
        "common_errors": [400, 401, 403, 409, 415, 422, 429, 500],
    },
    "PUT": {
        "purpose": "Create/replace a representation at a known target URI",
        "typical_success": [200, 201, 204],
        "common_errors": [400, 401, 403, 404, 409, 412, 415, 422, 429, 500],
    },
    "PATCH": {
        "purpose": "Apply partial modifications",
        "typical_success": [200, 204],
        "common_errors": [400, 401, 403, 404, 409, 412, 415, 422, 429, 500],
    },
    "DELETE": {
        "purpose": "Remove a resource",
        "typical_success": [200, 202, 204],
        "common_errors": [401, 403, 404, 409, 429, 500],
    },
}

for method, information in method_examples.items():
    print(f"\n{method}")
    print(f"  Purpose: {information['purpose']}")
    print(f"  Typical success: {information['typical_success']}")
    print(f"  Common errors: {information['common_errors']}")


# ============================================================================
# 14. IDEMPOTENCY
# ============================================================================

print("\n" + "=" * 78)
print("14. IDEMPOTENCY AND STATUS CODES")
print("=" * 78)

print(
    """
Idempotency is a property of a method/operation where repeating the same
request has the same intended effect on server state as making it once.

Commonly:

GET     -> idempotent
HEAD    -> idempotent
PUT     -> idempotent
DELETE  -> idempotent
POST    -> generally not idempotent
PATCH   -> depends on the operation

Idempotency does NOT mean that every repeated response must have the same
status code.

For example, DELETE can be designed so that:
    first DELETE -> 204
    second DELETE -> 404

The state-changing effect is still compatible with idempotent semantics because
after the first deletion the resource remains deleted.

Payment APIs often introduce an application-level idempotency key so clients
can safely retry operations such as POST when network failures make the
original result uncertain.
"""
)


# ============================================================================
# 15. CACHE VALIDATION AND 304
# ============================================================================

print("\n" + "=" * 78)
print("15. CACHE VALIDATION")
print("=" * 78)


@dataclass
class CachedResource:
    body: str
    etag: str
    last_modified: str


def conditional_get(
    resource: CachedResource,
    if_none_match: Optional[str] = None,
) -> Tuple[int, Dict[str, str], Optional[str]]:
    """
    Demonstrate the core decision behind a simple ETag-based conditional GET.
    """
    headers = {
        "ETag": resource.etag,
        "Content-Type": "text/plain",
    }

    if if_none_match == resource.etag:
        return 304, headers, None

    return 200, headers, resource.body


cached = CachedResource(
    body="Version 7 of the resource",
    etag='"resource-v7"',
    last_modified="Sun, 06 Sep 2026 10:00:00 GMT",
)

code_first, headers_first, body_first = conditional_get(cached)
code_cached, headers_cached, body_cached = conditional_get(
    cached,
    if_none_match='"resource-v7"',
)

print("First request:", code_first, headers_first, body_first)
print("Conditional request:", code_cached, headers_cached, body_cached)

print(
    """
304 is not an ordinary application success response with an empty body.
It specifically communicates cache validation.

The client can reuse its stored representation.

304 responses do not contain the representation body.
"""
)


# ============================================================================
# 16. ERROR RESPONSE DESIGN
# ============================================================================

print("\n" + "=" * 78)
print("16. STRUCTURED ERROR RESPONSES")
print("=" * 78)


@dataclass
class APIError:
    status: int
    code: str
    message: str
    details: Optional[List[Dict[str, Any]]] = None
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }

        if self.details:
            result["error"]["details"] = self.details

        if self.request_id:
            result["error"]["request_id"] = self.request_id

        return result


validation_error = APIError(
    status=422,
    code="VALIDATION_ERROR",
    message="One or more fields are invalid.",
    details=[
        {"field": "email", "reason": "invalid format"},
        {"field": "age", "reason": "must be at least 18"},
    ],
    request_id="req-8f21",
)

print(f"HTTP status: {validation_error.status}")
print(json.dumps(validation_error.to_dict(), indent=2))

print(
    """
Good error responses usually contain:

    HTTP status
    stable machine-readable error code
    safe human-readable message
    optional structured details
    correlation/request identifier

Avoid returning:

    database passwords
    stack traces
    source-code paths
    SQL queries
    internal service credentials
    secrets
    unnecessary infrastructure details

The HTTP status code and application error code serve different purposes.

Example:

    422
    VALIDATION_ERROR

The status communicates the HTTP-level meaning.
The application code communicates the API-specific meaning.
"""
)


# ============================================================================
# 17. RETRYABLE VS NON-RETRYABLE ERRORS
# ============================================================================

print("\n" + "=" * 78)
print("17. RETRY BEHAVIOR")
print("=" * 78)


def is_likely_retryable(status: int) -> bool:
    """
    A simplified retry policy.

    Real systems should consider the method, operation semantics, idempotency,
    Retry-After, network failures, and application-specific behavior.
    """
    if status in {408, 429, 500, 502, 503, 504}:
        return True
    return False


for code in [400, 401, 404, 409, 422, 429, 500, 502, 503, 504]:
    print(f"{code}: retryable candidate = {is_likely_retryable(code)}")

print(
    """
Do not blindly retry every 5xx response.

A retry strategy should consider:

1. Is the operation safe or idempotent?
2. Could repeating it duplicate a side effect?
3. Does Retry-After exist?
4. Is the failure likely transient?
5. Is the dependency already overloaded?
6. Is exponential backoff required?
7. Should jitter be added to prevent synchronized retries?

Typical exponential backoff:

    delay = base * 2^attempt

With jitter, clients spread retry traffic rather than retrying simultaneously.
"""
)


def exponential_backoff(
    attempt: int,
    base_delay: float = 0.5,
    maximum_delay: float = 30.0,
) -> float:
    """Return a capped exponential-backoff delay."""
    return min(base_delay * (2**attempt), maximum_delay)


print("\nBackoff demonstration:")
for attempt in range(6):
    print(f"attempt={attempt}, delay={exponential_backoff(attempt):.1f}s")


# ============================================================================
# 18. RATE LIMITING
# ============================================================================

print("\n" + "=" * 78)
print("18. RATE LIMITING AND 429")
print("=" * 78)


@dataclass
class RateLimitState:
    limit: int
    remaining: int
    reset_epoch: int

    def headers(self) -> Dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Reset": str(self.reset_epoch),
        }


rate_limit = RateLimitState(
    limit=100,
    remaining=0,
    reset_epoch=int(time.time()) + 60,
)

print("Rate-limit headers:")
for key, value in rate_limit.headers().items():
    print(f"{key}: {value}")

print("Suggested response status:", 429)
print("Possible Retry-After value: 60")


# ============================================================================
# 19. 405 AND ALLOW HEADER
# ============================================================================

print("\n" + "=" * 78)
print("19. METHOD NOT ALLOWED")
print("=" * 78)

print(
    """
When an endpoint does not support a method, 405 is generally more precise
than 404.

Example:

    DELETE /reports/42

If /reports/42 exists but only supports GET:

    HTTP/1.1 405 Method Not Allowed
    Allow: GET, HEAD

The Allow header communicates supported methods.
"""
)


# ============================================================================
# 20. CONTENT NEGOTIATION
# ============================================================================

print("\n" + "=" * 78)
print("20. CONTENT NEGOTIATION")
print("=" * 78)


def negotiate_content_type(
    accept_header: str,
    supported_types: Iterable[str],
) -> Optional[str]:
    """A deliberately simple Accept-header negotiation demonstration."""
    requested = [
        item.split(";", 1)[0].strip().lower()
        for item in accept_header.split(",")
    ]

    supported = [item.lower() for item in supported_types]

    for requested_type in requested:
        if requested_type in supported:
            return requested_type
        if requested_type == "*/*":
            return supported[0] if supported else None

    return None


supported = ["application/json", "text/plain"]

for accept in [
    "application/json",
    "text/html, application/json",
    "application/xml",
    "*/*",
]:
    selected = negotiate_content_type(accept, supported)
    print(f"Accept={accept!r} -> {selected!r}")

print(
    """
406 Not Acceptable can be appropriate when the server cannot provide a
representation in any format acceptable to the client.

Do not confuse:

415:
    the server does not support the request body's Content-Type

406:
    the server cannot produce a response representation acceptable to the
    client according to Accept preferences
"""
)


# ============================================================================
# 21. CONTENT-TYPE VALIDATION
# ============================================================================

print("\n" + "=" * 78)
print("21. CONTENT-TYPE AND 415")
print("=" * 78)


def validate_content_type(content_type: str, supported: Iterable[str]) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in {item.lower() for item in supported}


for content_type in [
    "application/json",
    "application/json; charset=utf-8",
    "application/xml",
]:
    supported_json = validate_content_type(
        content_type,
        ["application/json"],
    )
    print(f"{content_type:40} -> supported={supported_json}")

print(
    """
A client should send an accurate Content-Type.

For a JSON API, a common request header is:

    Content-Type: application/json

If a server requires JSON but receives an unsupported media type, 415 is
usually more appropriate than 422.
"""
)


# ============================================================================
# 22. CONFLICTS AND OPTIMISTIC CONCURRENCY
# ============================================================================

print("\n" + "=" * 78)
print("22. 409, 412, AND CONCURRENCY")
print("=" * 78)


@dataclass
class VersionedResource:
    identifier: int
    value: str
    version: int


def update_with_if_match(
    resource: VersionedResource,
    new_value: str,
    if_match: Optional[str],
) -> Tuple[int, str]:
    """
    Demonstrate optimistic concurrency using a simplified ETag.

    Real systems may use stronger ETag generation and persistence semantics.
    """
    current_etag = f'"v{resource.version}"'

    if if_match is None:
        return 428, "Precondition Required"

    if if_match != current_etag:
        return 412, "Precondition Failed"

    resource.value = new_value
    resource.version += 1

    return 200, "Updated"


resource = VersionedResource(identifier=1, value="Original", version=7)

print(update_with_if_match(resource, "New value", '"v7"'))
print(update_with_if_match(resource, "Another value", '"v7"'))

print(
    """
412 is especially useful when a client supplied a precondition such as
If-Match and the condition is false.

409 can be used for broader application state conflicts.

A practical distinction:

412:
    a specific HTTP precondition failed.

409:
    the operation conflicts with the resource's current application state.

428 Precondition Required:
    a server requires a conditional request but the client did not provide
    the required precondition.
"""
)


# ============================================================================
# 23. LOCATION HEADER
# ============================================================================

print("\n" + "=" * 78)
print("23. 201 CREATED AND LOCATION")
print("=" * 78)


def create_user_response(user_id: int) -> Tuple[int, Dict[str, str], Dict[str, Any]]:
    body = {
        "id": user_id,
        "name": "Neha",
    }

    headers = {
        "Content-Type": "application/json",
        "Location": f"/users/{user_id}",
    }

    return 201, headers, body


created_status, created_headers, created_body = create_user_response(101)

print("Status:", created_status)
print("Headers:", created_headers)
print("Body:", created_body)


# ============================================================================
# 24. REDIRECTION DECISION TABLE
# ============================================================================

print("\n" + "=" * 78)
print("24. REDIRECTION DECISION TABLE")
print("=" * 78)

redirect_decisions = [
    ("Permanent URI change, normal web redirect", 301),
    ("Temporary redirect with legacy-compatible semantics", 302),
    ("After POST, instruct client to retrieve another URI", 303),
    ("Temporary redirect while preserving method", 307),
    ("Permanent redirect while preserving method", 308),
]

for scenario, code in redirect_decisions:
    print(f"{scenario:65} -> {code}")


# ============================================================================
# 25. PYTHON HTTP CLIENT
# ============================================================================

print("\n" + "=" * 78)
print("25. PYTHON HTTP CLIENT WITH urllib")
print("=" * 78)


def http_get(url: str, timeout: float = 5.0) -> Tuple[int, Dict[str, str], str]:
    """
    Perform a GET request with the standard library.

    HTTPError is a subclass of URLError and represents an HTTP response whose
    status is an error status such as 404 or 500.
    """
    request = Request(
        url,
        method="GET",
        headers={"Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            headers = dict(response.headers.items())
            return response.status, headers, body

    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        headers = dict(error.headers.items())
        return error.code, headers, body

    except URLError as error:
        raise RuntimeError(f"Network-level failure: {error}") from error


print(
    """
The function above demonstrates an important distinction:

HTTPError:
    The server successfully returned an HTTP response, but the status is an
    HTTP error such as 404.

URLError:
    The client could not successfully obtain a usable HTTP response, for
    example because DNS resolution or a connection failed.
"""
)


# ============================================================================
# 26. SMALL LOCAL HTTP SERVER
# ============================================================================

print("\n" + "=" * 78)
print("26. EXECUTABLE LOCAL HTTP SERVER")
print("=" * 78)


class DemoAPIHandler(BaseHTTPRequestHandler):
    """
    A small API server designed to demonstrate status-code behavior.

    Routes:
        GET  /health
        GET  /users/1
        GET  /users/999
        POST /users
        DELETE /users/1
        GET  /redirect
        GET  /temporary-redirect
        GET  /error
        GET  /slow
        PUT  /users/1
    """

    users: Dict[int, Dict[str, Any]] = {
        1: {
            "id": 1,
            "name": "Asha",
            "email": "asha@example.com",
        }
    }

    def send_json(
        self,
        status: int,
        payload: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        body = b""
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")

        if headers:
            for key, value in headers.items():
                self.send_header(key, value)

        if body:
            self.send_header("Content-Length", str(len(body)))

        self.end_headers()

        if body:
            self.wfile.write(body)

    def read_json_body(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        content_length = self.headers.get("Content-Length")

        if content_length is None:
            return None, "Content-Length header is required"

        try:
            length = int(content_length)
        except ValueError:
            return None, "Invalid Content-Length"

        if length > 1_000_000:
            return None, "Request body too large"

        raw_body = self.rfile.read(length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "Malformed JSON"

        if not isinstance(payload, dict):
            return None, "JSON body must be an object"

        return payload, None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.send_json(
                200,
                {
                    "status": "healthy",
                    "service": "demo-api",
                },
            )
            return

        if parsed.path == "/users/1":
            user = self.users.get(1)
            if user is None:
                self.send_json(
                    404,
                    {
                        "error": {
                            "code": "USER_NOT_FOUND",
                            "message": "User was not found.",
                        }
                    },
                )
                return

            self.send_json(200, user)
            return

        if parsed.path == "/users/999":
            self.send_json(
                404,
                {
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "User was not found.",
                    }
                },
            )
            return

        if parsed.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", "/health")
            self.end_headers()
            return

        if parsed.path == "/temporary-redirect":
            self.send_response(307)
            self.send_header("Location", "/health")
            self.end_headers()
            return

        if parsed.path == "/error":
            self.send_json(
                500,
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected server error occurred.",
                    }
                },
            )
            return

        if parsed.path == "/slow":
            time.sleep(2)
            self.send_json(
                200,
                {
                    "status": "slow response completed",
                },
            )
            return

        self.send_json(
            404,
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Route not found.",
                }
            },
        )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/users":
            self.send_json(
                404,
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Route not found.",
                    }
                },
            )
            return

        content_type = self.headers.get("Content-Type", "")

        if not content_type.lower().startswith("application/json"):
            self.send_json(
                415,
                {
                    "error": {
                        "code": "UNSUPPORTED_MEDIA_TYPE",
                        "message": "application/json is required.",
                    }
                },
            )
            return

        payload, body_error = self.read_json_body()

        if body_error:
            self.send_json(
                400,
                {
                    "error": {
                        "code": "BAD_REQUEST",
                        "message": body_error,
                    }
                },
            )
            return

        assert payload is not None

        is_valid, errors = validate_user_payload(payload)

        if not is_valid:
            self.send_json(
                422,
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "User data is invalid.",
                        "details": errors,
                    }
                },
            )
            return

        new_id = max(self.users, default=0) + 1

        user = {
            "id": new_id,
            "name": payload["name"].strip(),
            "email": payload["email"].strip(),
        }

        self.users[new_id] = user

        self.send_json(
            201,
            user,
            headers={"Location": f"/users/{new_id}"},
        )

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/users/1":
            self.send_json(
                404,
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "User not found.",
                    }
                },
            )
            return

        self.send_json(
            200,
            {
                "message": "User replacement demonstration",
            },
        )

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/users/1":
            self.send_json(
                404,
                {
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "User not found.",
                    }
                },
            )
            return

        if 1 not in self.users:
            self.send_json(
                404,
                {
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "User already does not exist.",
                    }
                },
            )
            return

        del self.users[1]

        self.send_response(204)
        self.end_headers()

    def do_PATCH(self) -> None:
        self.send_json(
            405,
            {
                "error": {
                    "code": "METHOD_NOT_ALLOWED",
                    "message": "PATCH is not supported by this demonstration.",
                }
            },
            headers={"Allow": "GET, POST, PUT, DELETE"},
        )

    def log_message(self, format: str, *args: Any) -> None:
        """
        Keep demonstration output concise.
        """
        print(f"[server] {format % args}")


def start_demo_server() -> Tuple[HTTPServer, Thread]:
    server = HTTPServer(("127.0.0.1", 0), DemoAPIHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


server, server_thread = start_demo_server()
server_port = server.server_address[1]
base_url = f"http://127.0.0.1:{server_port}"

print(f"Demo server started at {base_url}")


# ============================================================================
# 27. CLIENT CALLS AGAINST THE LOCAL SERVER
# ============================================================================

print("\n" + "=" * 78)
print("27. TESTING THE LOCAL SERVER")
print("=" * 78)


def request_with_body(
    method: str,
    url: str,
    body: Optional[Mapping[str, Any]] = None,
    content_type: str = "application/json",
    timeout: float = 3.0,
) -> Tuple[int, Dict[str, str], str]:
    """
    Generic standard-library HTTP client for the demo server.
    """
    encoded_body: Optional[bytes] = None

    headers = {
        "Accept": "application/json",
    }

    if body is not None:
        encoded_body = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = content_type

    request = Request(
        url,
        data=encoded_body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.headers.items()), response_body

    except HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        return error.code, dict(error.headers.items()), response_body


def print_response(
    label: str,
    result: Tuple[int, Dict[str, str], str],
) -> None:
    code, headers, body = result
    print(f"\n{label}")
    print(f"Status: {code} {STATUS_DESCRIPTIONS.get(code, '')}")
    print(f"Class:  {status_class(code)}")
    print("Headers:")
    for key, value in headers.items():
        if key.lower() in {
            "content-type",
            "content-length",
            "location",
            "allow",
        }:
            print(f"  {key}: {value}")
    print(f"Body: {body or '<empty>'}")


print_response(
    "GET /health",
    http_get(f"{base_url}/health"),
)

print_response(
    "GET /users/1",
    http_get(f"{base_url}/users/1"),
)

print_response(
    "GET /users/999",
    http_get(f"{base_url}/users/999"),
)

print_response(
    "GET /missing-route",
    http_get(f"{base_url}/missing-route"),
)

print_response(
    "POST /users with valid data",
    request_with_body(
        "POST",
        f"{base_url}/users",
        {
            "name": "Vikram",
            "email": "vikram@example.com",
            "age": 28,
        },
    ),
)

print_response(
    "POST /users with validation errors",
    request_with_body(
        "POST",
        f"{base_url}/users",
        {
            "name": "",
            "email": "invalid",
            "age": 15,
        },
    ),
)

print_response(
    "POST /users with unsupported Content-Type",
    request_with_body(
        "POST",
        f"{base_url}/users",
        {
            "name": "Kiran",
            "email": "kiran@example.com",
            "age": 30,
        },
        content_type="application/xml",
    ),
)

print_response(
    "PATCH /users/1",
    request_with_body(
        "PATCH",
        f"{base_url}/users/1",
        {
            "name": "Changed",
        },
    ),
)

print_response(
    "GET /redirect",
    http_get(f"{base_url}/redirect"),
)

print_response(
    "GET /error",
    http_get(f"{base_url}/error"),
)


# ============================================================================
# 28. cURL COMMANDS
# ============================================================================

print("\n" + "=" * 78)
print("28. cURL COMMANDS FOR STATUS-CODE DEBUGGING")
print("=" * 78)

curl_commands = [
    f'curl -i "{base_url}/health"',
    f'curl -i "{base_url}/users/999"',
    f'curl -i -X POST "{base_url}/users" -H "Content-Type: application/json" -d \'{{"name":"Asha","email":"asha@example.com","age":25}}\'',
    f'curl -i -X POST "{base_url}/users" -H "Content-Type: application/json" -d \'{{"name":"","email":"bad","age":12}}\'',
    f'curl -i -X DELETE "{base_url}/users/1"',
    f'curl -i -X PATCH "{base_url}/users/1"',
    f'curl -i "{base_url}/redirect"',
]

for command in curl_commands:
    print(command)

print(
    """
Useful cURL flags:

-i
    Include response headers.

-I
    Send a HEAD request when supported.

-v
    Show detailed connection and protocol information.

-L
    Follow redirects.

-X METHOD
    Explicitly specify an HTTP method.

-H
    Add a request header.

-d
    Send request data.

-o /dev/null
    Discard response body when testing.

-w
    Print selected metrics such as status code and total time.

Example diagnostic pattern:

    curl -i -v https://example.com/api/users/42

When debugging redirects:

    curl -i -L https://example.com/old-path

When you need to see the status without the body:

    curl -s -o /dev/null -w "%{http_code}\\n" https://example.com/health
"""
)


# ============================================================================
# 29. POSTMAN CONCEPTS
# ============================================================================

print("\n" + "=" * 78)
print("29. POSTMAN WORKFLOW")
print("=" * 78)

print(
    """
A Postman request normally consists of:

    Method
    URL
    Params
    Authorization
    Headers
    Body

When inspecting the response, examine:

    Status
    Response headers
    Response body
    Response time
    Response size
    Cookies
    Redirect behavior

A useful status-code debugging workflow:

1. Confirm the HTTP method.
2. Confirm the URL and path parameters.
3. Inspect query parameters.
4. Inspect Authorization.
5. Inspect Content-Type.
6. Inspect request JSON.
7. Send the request.
8. Read the numeric status first.
9. Inspect response headers.
10. Inspect the structured error body.
11. Compare the observed result with endpoint documentation.
12. Repeat with a minimal request to isolate the failing component.

Postman tests can assert status codes.

Conceptually:

    pm.response.to.have.status(200)

The exact syntax depends on the Postman scripting environment and version.
"""
)


# ============================================================================
# 30. STATUS CODE ASSERTIONS
# ============================================================================

print("\n" + "=" * 78)
print("30. AUTOMATED STATUS CODE ASSERTIONS")
print("=" * 78)


def assert_status(
    actual: int,
    expected: int,
    description: str,
) -> None:
    if actual != expected:
        raise AssertionError(
            f"{description}: expected {expected}, received {actual}"
        )


status, _, _ = http_get(f"{base_url}/health")
assert_status(status, 200, "Health endpoint")

status, _, _ = http_get(f"{base_url}/users/999")
assert_status(status, 404, "Missing user endpoint")

status, _, _ = request_with_body(
    "POST",
    f"{base_url}/users",
    {
        "name": "Valid User",
        "email": "valid@example.com",
        "age": 25,
    },
)
assert_status(status, 201, "Create user endpoint")

status, _, _ = request_with_body(
    "POST",
    f"{base_url}/users",
    {
        "name": "",
        "email": "bad",
        "age": 10,
    },
)
assert_status(status, 422, "Validation endpoint")

print("All local HTTP status assertions passed.")


# ============================================================================
# 31. ERROR HANDLING ANTI-PATTERNS
# ============================================================================

print("\n" + "=" * 78)
print("31. COMMON ANTI-PATTERNS")
print("=" * 78)

anti_patterns = [
    (
        "Returning 200 for every outcome",
        "Clients cannot reliably distinguish success from failure."
    ),
    (
        "Returning 500 for invalid user input",
        "Client mistakes should normally not be represented as server failures."
    ),
    (
        "Using 401 for authorization failures",
        "401 is primarily about authentication; 403 commonly represents refusal."
    ),
    (
        "Returning 404 for every failure",
        "It hides useful distinctions and makes debugging harder."
    ),
    (
        "Returning 204 with a response body",
        "204 means there is no response content."
    ),
    (
        "Using 200 for resource creation",
        "201 more precisely communicates successful creation."
    ),
    (
        "Retrying every 5xx automatically",
        "Retries can amplify outages or duplicate non-idempotent operations."
    ),
    (
        "Exposing stack traces",
        "Internal implementation details can become a security vulnerability."
    ),
    (
        "Changing status-code semantics between endpoints",
        "Inconsistent APIs increase client complexity and integration errors."
    ),
]

for anti_pattern, consequence in anti_patterns:
    print(f"\nAnti-pattern: {anti_pattern}")
    print(f"Problem:     {consequence}")


# ============================================================================
# 32. STATUS CODES ARE NOT BUSINESS LOGIC
# ============================================================================

print("\n" + "=" * 78)
print("32. HTTP SEMANTICS VS APPLICATION SEMANTICS")
print("=" * 78)

print(
    """
HTTP status codes should describe the HTTP-level result.

They should not be overloaded to encode every business state.

For example, consider a payment:

    202 Accepted
        Payment request accepted for asynchronous processing.

The response body may contain:

    {
        "payment_id": "pay_123",
        "state": "processing"
    }

The application state belongs in the domain model.

The HTTP status describes what happened to the HTTP request itself.

This separation keeps API behavior easier to understand and integrate.
"""
)


# ============================================================================
# 33. SECURITY CONSIDERATIONS
# ============================================================================

print("\n" + "=" * 78)
print("33. SECURITY CONSIDERATIONS")
print("=" * 78)

security_rules = [
    "Do not expose credentials or secrets in error messages.",
    "Do not expose stack traces in production responses.",
    "Avoid leaking whether protected resources exist when that information is sensitive.",
    "Use 401/403 consistently with the authentication and authorization model.",
    "Validate Content-Type and request size before expensive parsing.",
    "Apply rate limits where abuse is possible.",
    "Use HTTPS for sensitive data.",
    "Treat client-controlled headers and URLs as untrusted input.",
    "Use request IDs for safe correlation between client and server logs.",
    "Log diagnostic details on the server rather than returning them to clients.",
]

for number, rule in enumerate(security_rules, start=1):
    print(f"{number:2}. {rule}")


# ============================================================================
# 34. OBSERVABILITY
# ============================================================================

print("\n" + "=" * 78)
print("34. OBSERVABILITY AND STATUS CODES")
print("=" * 78)


@dataclass
class RequestMetric:
    method: str
    path: str
    status: int
    latency_ms: float

    @property
    def status_class(self) -> str:
        return status_class(self.status)


metrics = [
    RequestMetric("GET", "/users/1", 200, 42.1),
    RequestMetric("GET", "/users/999", 404, 35.4),
    RequestMetric("POST", "/users", 422, 18.8),
    RequestMetric("GET", "/reports/7", 503, 201.3),
    RequestMetric("GET", "/inventory/9", 504, 3000.0),
]

for metric in metrics:
    print(
        f"{metric.method:6} {metric.path:20} "
        f"{metric.status:3} {metric.status_class:20} "
        f"{metric.latency_ms:8.1f} ms"
    )

print(
    """
Production monitoring should examine more than a single aggregate success
percentage.

Useful dimensions include:

    status-code class
    individual status code
    endpoint
    HTTP method
    latency
    dependency
    region
    client/application version
    request ID

A rising 404 rate may indicate a client deployment problem.
A rising 429 rate may indicate traffic growth or an overly restrictive limit.
A rising 502/504 rate may indicate dependency or network problems.
A rising 500 rate may indicate an application regression.
"""
)


# ============================================================================
# 35. PROXY / GATEWAY SCENARIOS
# ============================================================================

print("\n" + "=" * 78)
print("35. PROXY, LOAD BALANCER, AND GATEWAY STATUS CODES")
print("=" * 78)

gateway_scenarios = [
    ("Client -> gateway -> healthy application", 200),
    ("Gateway receives invalid upstream response", 502),
    ("Gateway waits too long for upstream", 504),
    ("Application intentionally unavailable", 503),
    ("Client sends malformed request", 400),
]

for scenario, code in gateway_scenarios:
    print(f"{scenario:55} -> {code}")


# ============================================================================
# 36. STATUS-CODE CLASSIFICATION FUNCTION
# ============================================================================

print("\n" + "=" * 78)
print("36. PROGRAMMATIC CLASSIFICATION")
print("=" * 78)


def is_success(code: int) -> bool:
    return 200 <= code <= 299


def is_redirect(code: int) -> bool:
    return 300 <= code <= 399


def is_client_error(code: int) -> bool:
    return 400 <= code <= 499


def is_server_error(code: int) -> bool:
    return 500 <= code <= 599


sample_codes = [200, 201, 301, 304, 400, 404, 429, 500, 503]

for code in sample_codes:
    print(
        f"{code}: success={is_success(code)}, "
        f"redirect={is_redirect(code)}, "
        f"client_error={is_client_error(code)}, "
        f"server_error={is_server_error(code)}"
    )


# ============================================================================
# 37. STATUS CODE REGISTRY AND UNKNOWN CODES
# ============================================================================

print("\n" + "=" * 78)
print("37. UNKNOWN OR EXTENSION STATUS CODES")
print("=" * 78)

unknown_codes = [218, 299, 418, 450, 599]

for code in unknown_codes:
    print(explain_status(code))

print(
    """
Clients should generally understand status-code classes even when they do not
recognize a specific code.

For example, an unfamiliar 4xx code should normally be treated as a client
error rather than being mistaken for a success.

Likewise, an unfamiliar 5xx code represents a server-side failure class.
"""
)


# ============================================================================
# 38. SPECIAL STATUS CODE: 418
# ============================================================================

print("\n" + "=" * 78)
print("38. 418 I'M A TEAPOT")
print("=" * 78)

print(
    """
418 is a well-known humorous status code originating from an April Fools'
specification. It is not normally appropriate for ordinary API error handling.

The lesson is important:

Do not choose status codes merely because they look convenient or memorable.
Choose codes according to their defined semantics and the conventions of the
API ecosystem.
"""
)


# ============================================================================
# 39. REQUEST SIZE AND 413
# ============================================================================

print("\n" + "=" * 78)
print("39. REQUEST SIZE VALIDATION")
print("=" * 78)


def request_size_status(content_length: Optional[str], maximum: int) -> int:
    if content_length is None:
        return 400

    try:
        length = int(content_length)
    except ValueError:
        return 400

    if length < 0:
        return 400

    if length > maximum:
        return 413

    return 200


for value in ["100", "1000000", "not-a-number", "-1"]:
    print(
        f"Content-Length={value!r} -> "
        f"{request_size_status(value, maximum=500000)}"
    )


# ============================================================================
# 40. REQUEST TIMEOUT AND UPSTREAM TIMEOUT
# ============================================================================

print("\n" + "=" * 78)
print("40. 408 VS 504")
print("=" * 78)

print(
    """
408 Request Timeout:
    The server did not receive a complete request from the client within the
    time it was prepared to wait.

504 Gateway Timeout:
    A gateway or proxy did not receive a timely response from an upstream
    server.

The location of the timeout in the request chain matters.
"""
)


# ============================================================================
# 41. 502 VS 503 VS 504
# ============================================================================

print("\n" + "=" * 78)
print("41. 502 VS 503 VS 504")
print("=" * 78)

comparison = [
    ("502", "Bad Gateway", "Upstream returned an invalid/unacceptable response"),
    ("503", "Service Unavailable", "Service cannot currently handle the request"),
    ("504", "Gateway Timeout", "Gateway did not receive upstream response in time"),
]

for code, name, meaning in comparison:
    print(f"{code} {name:22} | {meaning}")


# ============================================================================
# 42. PRACTICAL API DESIGN SCENARIOS
# ============================================================================

print("\n" + "=" * 78)
print("42. PRACTICAL API DESIGN SCENARIOS")
print("=" * 78)

scenarios = [
    ("GET existing user", 200),
    ("GET missing user", 404),
    ("POST valid new user", 201),
    ("POST malformed JSON", 400),
    ("POST valid JSON but invalid fields", 422),
    ("POST duplicate unique resource", 409),
    ("PUT successful replacement without response body", 204),
    ("DELETE successful deletion", 204),
    ("GET cached resource unchanged", 304),
    ("Authenticated user without permission", 403),
    ("Missing/invalid authentication", 401),
    ("Unsupported request media type", 415),
    ("Too many requests", 429),
    ("Unexpected application exception", 500),
    ("Upstream returned invalid response", 502),
    ("Temporary service overload", 503),
    ("Gateway timeout", 504),
]

for scenario, code in scenarios:
    print(f"{scenario:55} -> {code}")


# ============================================================================
# 43. TESTING STATUS CODE CONTRACTS
# ============================================================================

print("\n" + "=" * 78)
print("43. STATUS CODE CONTRACT TESTING")
print("=" * 78)


@dataclass
class EndpointContract:
    method: str
    path: str
    expected_statuses: Tuple[int, ...]


contracts = [
    EndpointContract("GET", "/health", (200,)),
    EndpointContract("GET", "/users/999", (404,)),
    EndpointContract("POST", "/users", (201, 400, 415, 422)),
    EndpointContract("PATCH", "/users/1", (405,)),
]

for contract in contracts:
    print(
        f"{contract.method:6} {contract.path:20} "
        f"allowed statuses={contract.expected_statuses}"
    )


def status_is_contract_compliant(
    actual_status: int,
    contract: EndpointContract,
) -> bool:
    return actual_status in contract.expected_statuses


print(
    "\nContract check:",
    status_is_contract_compliant(
        404,
        contracts[1],
    ),
)


# ============================================================================
# 44. EDGE CASE: DELETE
# ============================================================================

print("\n" + "=" * 78)
print("44. DELETE EDGE CASES")
print("=" * 78)

print(
    """
Possible API policies for:

    DELETE /users/42

when the user does not exist:

    404 Not Found
        Strictly communicates that the target does not exist.

or sometimes:

    204 No Content
        Treats deletion as effectively complete from the client's desired
        state perspective.

The important engineering principle is consistency.

If one endpoint treats repeated DELETE as 404 while another silently returns
204, clients must understand endpoint-specific conventions.
"""
)


# ============================================================================
# 45. EDGE CASE: ASYNCHRONOUS OPERATIONS
# ============================================================================

print("\n" + "=" * 78)
print("45. 202 FOR ASYNCHRONOUS WORK")
print("=" * 78)


@dataclass
class AsyncJobResponse:
    status: int
    job_id: str
    status_url: str

    def body(self) -> Dict[str, str]:
        return {
            "job_id": self.job_id,
            "status": "queued",
            "status_url": self.status_url,
        }


job_response = AsyncJobResponse(
    status=202,
    job_id="job-123",
    status_url="/jobs/job-123",
)

print("Status:", job_response.status)
print(json.dumps(job_response.body(), indent=2))

print(
    """
202 is appropriate when the server has accepted the work but cannot truthfully
claim that the requested operation has completed.

Returning 200 with "processing" can work in some APIs, but 202 provides a
standard HTTP-level indication that processing has not completed.
"""
)


# ============================================================================
# 46. PERFORMANCE CONSIDERATIONS
# ============================================================================

print("\n" + "=" * 78)
print("46. PERFORMANCE CONSIDERATIONS")
print("=" * 78)

print(
    """
Status codes themselves are extremely cheap.

Performance problems usually arise from what happens before the status code
is produced.

Examples:

    404 can be fast when a lookup is indexed.
    500 may occur after expensive database work.
    503 may be intentionally returned quickly during overload protection.
    504 may reflect waiting on a slow dependency.

Production systems should measure:

    request latency
    time spent in dependencies
    response size
    error rate
    retry volume
    connection pool utilization
    database latency

A fast 503 can be healthier than allowing every request to consume resources
until the system collapses.
"""
)


# ============================================================================
# 47. CIRCUIT BREAKER CONCEPT
# ============================================================================

print("\n" + "=" * 78)
print("47. CIRCUIT BREAKER AND 503")
print("=" * 78)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class SimpleCircuitBreaker:
    failure_threshold: int = 3
    failures: int = 0
    state: CircuitState = CircuitState.CLOSED

    def record_success(self) -> None:
        self.failures = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def allow_request(self) -> bool:
        return self.state != CircuitState.OPEN


breaker = SimpleCircuitBreaker()

for _ in range(3):
    breaker.record_failure()
    print(
        f"failure_count={breaker.failures}, "
        f"state={breaker.state.value}, "
        f"allow_request={breaker.allow_request()}"
    )

print(
    """
Circuit breakers can prevent a failing dependency from consuming all
available application resources.

When a service refuses requests because a dependency is unavailable, 503 can
be more accurate than 500 when the condition is temporary and expected to
recover.
"""
)


# ============================================================================
# 48. PRODUCTION LOGGING MODEL
# ============================================================================

print("\n" + "=" * 78)
print("48. SAFE PRODUCTION LOGGING")
print("=" * 78)


@dataclass
class RequestLog:
    request_id: str
    method: str
    path: str
    status: int
    duration_ms: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }


log_record = RequestLog(
    request_id="req-10001",
    method="GET",
    path="/users/42",
    status=200,
    duration_ms=17.3,
)

print(json.dumps(log_record.as_dict(), indent=2))

print(
    """
Avoid logging sensitive request bodies, authorization tokens, passwords,
session identifiers, or payment information unless there is a carefully
controlled and justified operational requirement.

A request ID allows a safe client-facing error response to be correlated with
server-side diagnostics.
"""
)


# ============================================================================
# 49. MINI STATUS-CODE QUIZ
# ============================================================================

print("\n" + "=" * 78)
print("49. KNOWLEDGE CHECK")
print("=" * 78)

quiz = [
    ("A new resource was successfully created.", 201),
    ("Authentication credentials are missing.", 401),
    ("Authenticated user lacks permission.", 403),
    ("Resource does not exist.", 404),
    ("HTTP method is unsupported for this resource.", 405),
    ("Request conflicts with current state.", 409),
    ("Request failed domain validation.", 422),
    ("Rate limit exceeded.", 429),
    ("Unexpected server exception.", 500),
    ("Invalid response from upstream server.", 502),
    ("Service temporarily unavailable.", 503),
    ("Gateway timed out waiting for upstream.", 504),
]

for question, expected in quiz:
    print(f"{question:58} -> {expected}")


# ============================================================================
# 50. CLEANUP
# ============================================================================

print("\n" + "=" * 78)
print("50. SHUTTING DOWN DEMO SERVER")
print("=" * 78)

server.shutdown()
server.server_close()
server_thread.join(timeout=2)

print("Demo server stopped.")


# ============================================================================
# 51. FINAL PROGRAMMATIC CHECKS
# ============================================================================

print("\n" + "=" * 78)
print("51. FINAL SELF-TESTS")
print("=" * 78)

assert status_class(100) == "1xx Informational"
assert status_class(200) == "2xx Successful"
assert status_class(301) == "3xx Redirection"
assert status_class(404) == "4xx Client Error"
assert status_class(500) == "5xx Server Error"

assert choose_status_code(RequestOutcome.CREATED) == 201
assert choose_status_code(RequestOutcome.UNAUTHENTICATED) == 401
assert choose_status_code(RequestOutcome.FORBIDDEN) == 403
assert choose_status_code(RequestOutcome.VALIDATION_FAILED) == 422
assert choose_status_code(RequestOutcome.RATE_LIMITED) == 429
assert choose_status_code(RequestOutcome.UPSTREAM_TIMEOUT) == 504

assert is_success(200)
assert is_redirect(302)
assert is_client_error(404)
assert is_server_error(500)

assert negotiate_content_type(
    "text/html, application/json",
    ["application/json"],
) == "application/json"

assert validate_content_type(
    "application/json; charset=utf-8",
    ["application/json"],
)

assert request_size_status("100", 500) == 200
assert request_size_status("501", 500) == 413
assert request_size_status("invalid", 500) == 400

print("All final self-tests passed.")

print(
    """
===============================================================================
CORE STATUS-CODE SELECTION RULES
===============================================================================

200  -> successful operation with a result
201  -> successful creation
202  -> accepted for asynchronous processing
204  -> successful operation with no response body

301  -> permanent redirect
302  -> temporary/legacy redirect semantics
303  -> retrieve another resource
304  -> cached representation remains valid
307  -> temporary redirect preserving method
308  -> permanent redirect preserving method

400  -> malformed/invalid request
401  -> authentication problem
403  -> authorization refusal
404  -> resource not found or intentionally undisclosed
405  -> method not supported
409  -> application state conflict
412  -> supplied precondition failed
413  -> request content too large
415  -> unsupported request media type
422  -> semantically invalid content
429  -> rate limit exceeded

500  -> unexpected server-side failure
501  -> functionality not implemented
502  -> invalid upstream response
503  -> temporary service unavailability
504  -> upstream timeout

When choosing a status code, prioritize precise HTTP semantics, consistency,
client expectations, safe error reporting, and the actual behavior of the
system.
"""
)
