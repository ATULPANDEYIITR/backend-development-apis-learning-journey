"""
HTTP HEADERS: A COMPREHENSIVE PYTHON STUDY SCRIPT

This script teaches HTTP headers from beginner to advanced level using only the
Python standard library.

Topics covered:
- HTTP request and response structure
- Request headers and response headers
- Header names and case-insensitivity
- Content-Type and media types
- Accept and content negotiation
- Authorization schemes
- Cache-Control and HTTP caching concepts
- Cookies and Set-Cookie
- User-Agent, Host, Referer, Origin and other common headers
- Security-related headers
- Conditional requests
- Range requests
- Redirects
- Compression
- CORS concepts
- Header parsing and validation
- Common mistakes and edge cases
- Practical HTTP clients and servers
- Testing and debugging headers

Run:
    python http_headers_tutorial.py

The demonstrations use localhost where networking is required.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =============================================================================
# SECTION 1: FUNDAMENTALS
# =============================================================================

print("=" * 80)
print("SECTION 1: HTTP FUNDAMENTALS")
print("=" * 80)

# HTTP is a request-response protocol.
#
# A simplified HTTP request:
#
# GET /products HTTP/1.1
# Host: example.com
# Accept: application/json
#
# A simplified HTTP response:
#
# HTTP/1.1 200 OK
# Content-Type: application/json
# Content-Length: 18
#
# {"status":"success"}

request_line = "GET /products HTTP/1.1"
response_status_line = "HTTP/1.1 200 OK"

print("Example request line:", request_line)
print("Example response status line:", response_status_line)


# =============================================================================
# SECTION 2: WHAT HTTP HEADERS ARE
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 2: HEADER STRUCTURE")
print("=" * 80)

# HTTP headers contain metadata about a request or response.
#
# Header syntax:
#
# Header-Name: Header Value
#
# Header names are case-insensitive according to HTTP specifications.
# Therefore these refer to the same logical header:
#
# Content-Type
# content-type
# CONTENT-TYPE

headers_example = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Python Tutorial Client/1.0",
}

for name, value in headers_example.items():
    print(f"{name}: {value}")


# =============================================================================
# SECTION 3: CASE-INSENSITIVE HEADER STORAGE
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 3: CASE-INSENSITIVE HEADERS")
print("=" * 80)


class CaseInsensitiveHeaders:
    """
    A simple educational implementation of case-insensitive HTTP headers.

    HTTP header field names are case-insensitive, but header values are generally
    not automatically case-insensitive.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[str, str]] = {}

    def set(self, name: str, value: str) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("Header name must be a non-empty string.")

        normalized_name = name.lower()
        self._data[normalized_name] = (name, value)

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        item = self._data.get(name.lower())
        return item[1] if item else default

    def remove(self, name: str) -> None:
        self._data.pop(name.lower(), None)

    def items(self) -> Iterable[Tuple[str, str]]:
        for original_name, value in self._data.values():
            yield original_name, value

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._data


case_headers = CaseInsensitiveHeaders()
case_headers.set("Content-Type", "application/json")

print("content-type:", case_headers.get("content-type"))
print("CONTENT-TYPE:", case_headers.get("CONTENT-TYPE"))
print("Content-Type:", case_headers.get("Content-Type"))


# =============================================================================
# SECTION 4: REQUEST HEADERS AND RESPONSE HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 4: REQUEST HEADERS VS RESPONSE HEADERS")
print("=" * 80)

request_headers = {
    "Host": "api.example.com",
    "Accept": "application/json",
    "Authorization": "Bearer example-token",
    "User-Agent": "ExampleClient/1.0",
}

response_headers = {
    "Content-Type": "application/json",
    "Cache-Control": "max-age=3600",
    "ETag": '"version-123"',
    "Set-Cookie": "session_id=abc123; HttpOnly",
}

print("Request headers:")
for name, value in request_headers.items():
    print(f"  {name}: {value}")

print("\nResponse headers:")
for name, value in response_headers.items():
    print(f"  {name}: {value}")


# =============================================================================
# SECTION 5: CONTENT-TYPE
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 5: CONTENT-TYPE")
print("=" * 80)

# Content-Type describes the representation contained in the HTTP message body.
#
# Common media types:
# application/json
# text/plain
# text/html
# application/xml
# application/pdf
# image/png
# image/jpeg
# multipart/form-data
#
# A Content-Type can also include parameters:
# Content-Type: application/json; charset=utf-8


@dataclass
class MediaType:
    main_type: str
    sub_type: str
    parameters: Dict[str, str] = field(default_factory=dict)

    @property
    def value(self) -> str:
        result = f"{self.main_type}/{self.sub_type}"
        for key, value in self.parameters.items():
            result += f"; {key}={value}"
        return result


def parse_content_type(content_type: str) -> MediaType:
    """
    Parse a simplified Content-Type header.

    Example:
        application/json; charset=utf-8
    """

    parts = [part.strip() for part in content_type.split(";")]

    if "/" not in parts[0]:
        raise ValueError("Invalid media type. Expected type/subtype.")

    main_type, sub_type = parts[0].split("/", 1)

    parameters: Dict[str, str] = {}

    for parameter in parts[1:]:
        if "=" in parameter:
            key, value = parameter.split("=", 1)
            parameters[key.strip().lower()] = value.strip().strip('"')

    return MediaType(
        main_type=main_type.lower(),
        sub_type=sub_type.lower(),
        parameters=parameters,
    )


content_type_examples = [
    "application/json",
    "text/html; charset=utf-8",
    "application/problem+json",
]

for example in content_type_examples:
    parsed = parse_content_type(example)
    print(
        f"Original: {example}\n"
        f"  Type: {parsed.main_type}\n"
        f"  Subtype: {parsed.sub_type}\n"
        f"  Parameters: {parsed.parameters}"
    )


# =============================================================================
# SECTION 6: CONTENT-TYPE VS ACCEPT
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 6: CONTENT-TYPE VS ACCEPT")
print("=" * 80)

# Content-Type answers:
# "What format is this message body?"
#
# Accept answers:
# "What response formats can the client handle?"

client_request = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain",
}

print("Client request headers:")
for name, value in client_request.items():
    print(f"  {name}: {value}")

print(
    "\nInterpretation:\n"
    "- Content-Type describes the request body format.\n"
    "- Accept expresses preferred response formats."
)


# =============================================================================
# SECTION 7: ACCEPT AND CONTENT NEGOTIATION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 7: ACCEPT AND CONTENT NEGOTIATION")
print("=" * 80)

# Accept may contain multiple media types.
#
# Quality values (q values) express relative preference.
#
# Accept: application/json;q=1.0, text/html;q=0.8, text/plain;q=0.5


@dataclass(order=True)
class AcceptPreference:
    quality: float
    media_type: str


def parse_accept_header(header_value: str) -> List[AcceptPreference]:
    """
    Parse a simplified Accept header and return preferences sorted by quality.
    """

    preferences: List[AcceptPreference] = []

    for entry in header_value.split(","):
        pieces = [piece.strip() for piece in entry.split(";")]

        media_type = pieces[0]
        quality = 1.0

        for parameter in pieces[1:]:
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0

        preferences.append(
            AcceptPreference(
                quality=quality,
                media_type=media_type,
            )
        )

    return sorted(preferences, reverse=True)


accept_header = (
    "application/json;q=1.0, "
    "text/html;q=0.8, "
    "text/plain;q=0.5"
)

preferences = parse_accept_header(accept_header)

print("Accept header:", accept_header)
print("Preferences:")
for preference in preferences:
    print(
        f"  {preference.media_type} "
        f"(quality={preference.quality})"
    )


def media_type_matches(accepted: str, available: str) -> bool:
    """
    Determine whether a simplified Accept media type matches an available type.

    Supports:
    - exact match
    - type wildcard, such as text/*
    - universal wildcard, such as */*
    """

    accepted = accepted.lower()
    available = available.lower()

    if accepted == "*/*":
        return True

    if accepted == available:
        return True

    if accepted.endswith("/*"):
        accepted_type = accepted.split("/", 1)[0]
        available_type = available.split("/", 1)[0]
        return accepted_type == available_type

    return False


def negotiate_content(
    accept_value: str,
    available_types: List[str],
) -> Optional[str]:
    """
    Select the best available representation based on simplified Accept rules.
    """

    preferences = parse_accept_header(accept_value)

    for preference in preferences:
        if preference.quality <= 0:
            continue

        for available in available_types:
            if media_type_matches(preference.media_type, available):
                return available

    return None


available_types = [
    "application/json",
    "text/html",
]

selected = negotiate_content(
    "text/*;q=0.7, application/json;q=0.9",
    available_types,
)

print("\nNegotiated response type:", selected)


# =============================================================================
# SECTION 8: AUTHORIZATION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 8: AUTHORIZATION")
print("=" * 80)

# Authorization contains credentials proving or asserting access permissions.
#
# Common schemes include:
# Basic
# Bearer
#
# Important:
# Authorization headers should normally be transmitted only over HTTPS in
# production because credentials may otherwise be exposed in transit.


def create_basic_authorization(username: str, password: str) -> str:
    """
    Create a Basic Authorization header value.

    Basic authentication is base64 encoding, not encryption.
    """

    credentials = f"{username}:{password}".encode("utf-8")
    encoded = base64.b64encode(credentials).decode("ascii")
    return f"Basic {encoded}"


basic_header = create_basic_authorization(
    "student",
    "example-password",
)

print("Basic Authorization header:")
print(" ", basic_header)

print(
    "\nSecurity note: Base64 is reversible. "
    "Basic authentication must not be treated as encrypted credentials."
)


def create_bearer_authorization(token: str) -> str:
    """
    Create a Bearer Authorization header.
    """

    if not token.strip():
        raise ValueError("Token must not be empty.")

    return f"Bearer {token}"


bearer_header = create_bearer_authorization(
    "example-access-token"
)

print("\nBearer Authorization header:")
print(" ", bearer_header)


def parse_authorization_header(value: str) -> Tuple[str, str]:
    """
    Split an Authorization header into authentication scheme and credentials.
    """

    parts = value.split(" ", 1)

    if len(parts) != 2:
        raise ValueError("Invalid Authorization header.")

    scheme, credentials = parts

    if not scheme or not credentials:
        raise ValueError("Authorization scheme and credentials are required.")

    return scheme, credentials


scheme, credentials = parse_authorization_header(
    "Bearer example-access-token"
)

print("\nParsed scheme:", scheme)
print("Parsed credentials:", credentials)


# =============================================================================
# SECTION 9: CACHE-CONTROL
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 9: CACHE-CONTROL")
print("=" * 80)

# Cache-Control controls caching behavior.
#
# Common directives:
#
# max-age=3600
# no-cache
# no-store
# public
# private
# must-revalidate
#
# Important distinction:
#
# no-cache:
# Cached data may exist, but it should be validated before reuse.
#
# no-store:
# The response should not be stored.


def parse_cache_control(value: str) -> Dict[str, Optional[str]]:
    """
    Parse a simplified Cache-Control header into directives.

    Example:
        max-age=3600, private

    Result:
        {
            "max-age": "3600",
            "private": None,
        }
    """

    directives: Dict[str, Optional[str]] = {}

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        if "=" in item:
            name, directive_value = item.split("=", 1)
            directives[name.strip().lower()] = (
                directive_value.strip().strip('"')
            )
        else:
            directives[item.lower()] = None

    return directives


cache_control_examples = [
    "max-age=3600",
    "private, max-age=600",
    "no-cache",
    "no-store",
]

for value in cache_control_examples:
    print(value, "->", parse_cache_control(value))


@dataclass
class CachedResponse:
    body: bytes
    stored_at: float
    max_age: Optional[int]

    def is_fresh(self, current_time: Optional[float] = None) -> bool:
        """
        Determine whether the cached response is still fresh.
        """

        if self.max_age is None:
            return False

        if current_time is None:
            current_time = time.time()

        age = current_time - self.stored_at
        return age < self.max_age


cached = CachedResponse(
    body=b'{"message":"cached"}',
    stored_at=time.time(),
    max_age=60,
)

print("\nCached response fresh:", cached.is_fresh())

expired = CachedResponse(
    body=b"old",
    stored_at=time.time() - 120,
    max_age=60,
)

print("Expired response fresh:", expired.is_fresh())


# =============================================================================
# SECTION 10: CONDITIONAL REQUESTS AND ETAG
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 10: CONDITIONAL REQUESTS AND ETAGS")
print("=" * 80)

# An ETag identifies a version of a representation.
#
# Server response:
# ETag: "abc123"
#
# Later request:
# If-None-Match: "abc123"
#
# If the resource has not changed, the server can return:
# 304 Not Modified


def generate_etag(content: bytes) -> str:
    """
    Generate a simple ETag using SHA-256.

    Production systems may use database versions, content hashes, or other
    efficient version identifiers.
    """

    digest = hashlib.sha256(content).hexdigest()
    return f'"{digest}"'


resource_body = b'{"product":"keyboard","price":100}'
resource_etag = generate_etag(resource_body)

print("Resource ETag:", resource_etag)


def handle_if_none_match(
    current_etag: str,
    client_etag: Optional[str],
) -> int:
    """
    Return a simplified response status based on If-None-Match.
    """

    if client_etag == current_etag:
        return HTTPStatus.NOT_MODIFIED

    return HTTPStatus.OK


status = handle_if_none_match(
    resource_etag,
    resource_etag,
)

print("Conditional request status:", status, status.phrase)


# =============================================================================
# SECTION 11: HTTP DATE HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 11: DATE HEADERS")
print("=" * 80)

current_datetime = datetime.now(timezone.utc)
http_date = format_datetime(current_datetime, usegmt=True)

print("HTTP date:", http_date)

parsed_date = parsedate_to_datetime(http_date)

print("Parsed date:", parsed_date.isoformat())


# =============================================================================
# SECTION 12: COOKIES
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 12: COOKIES")
print("=" * 80)

# Cookies are usually sent by a server through Set-Cookie.
#
# Example response:
#
# Set-Cookie: session_id=abc123; Path=/; HttpOnly; Secure; SameSite=Lax
#
# Browser request:
#
# Cookie: session_id=abc123
#
# Important attributes:
#
# Secure
#   Cookie should only be sent over HTTPS.
#
# HttpOnly
#   Browser-side JavaScript cannot directly read the cookie.
#
# SameSite
#   Helps control cross-site request behavior.
#
# Path
#   Restricts the URL path scope.
#
# Domain
#   Controls domain scope.
#
# Max-Age / Expires
#   Controls cookie lifetime.


@dataclass
class SimpleCookie:
    name: str
    value: str
    attributes: Dict[str, Optional[str]] = field(
        default_factory=dict
    )


def parse_set_cookie(header_value: str) -> SimpleCookie:
    """
    Parse a simplified Set-Cookie header.

    Real cookie parsing has additional specification details and edge cases.
    """

    parts = [part.strip() for part in header_value.split(";")]

    if "=" not in parts[0]:
        raise ValueError("Cookie name and value are required.")

    name, value = parts[0].split("=", 1)

    attributes: Dict[str, Optional[str]] = {}

    for attribute in parts[1:]:
        if "=" in attribute:
            key, attribute_value = attribute.split("=", 1)
            attributes[key.lower()] = attribute_value
        else:
            attributes[attribute.lower()] = None

    return SimpleCookie(
        name=name,
        value=value,
        attributes=attributes,
    )


set_cookie_value = (
    "session_id=abc123; "
    "Path=/; "
    "HttpOnly; "
    "Secure; "
    "SameSite=Lax"
)

cookie = parse_set_cookie(set_cookie_value)

print("Cookie name:", cookie.name)
print("Cookie value:", cookie.value)
print("Cookie attributes:", cookie.attributes)


def parse_cookie_header(header_value: str) -> Dict[str, str]:
    """
    Parse a simple Cookie request header.

    Example:
        theme=dark; session_id=abc123
    """

    cookies: Dict[str, str] = {}

    for item in header_value.split(";"):
        item = item.strip()

        if "=" not in item:
            continue

        name, value = item.split("=", 1)
        cookies[name.strip()] = value.strip()

    return cookies


request_cookie_header = "theme=dark; session_id=abc123"

print(
    "\nParsed request cookies:",
    parse_cookie_header(request_cookie_header),
)


# =============================================================================
# SECTION 13: MULTIPLE HEADER VALUES
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 13: MULTIPLE HEADER VALUES")
print("=" * 80)

# Some headers may contain comma-separated values.
# Some headers may appear multiple times.
#
# Set-Cookie is particularly important because multiple cookies are generally
# represented as separate Set-Cookie header fields rather than a single
# comma-separated value.


class MultiValueHeaders:
    """
    Store HTTP headers while preserving multiple values.
    """

    def __init__(self) -> None:
        self._headers: Dict[str, List[Tuple[str, str]]] = {}

    def add(self, name: str, value: str) -> None:
        key = name.lower()

        self._headers.setdefault(key, []).append(
            (name, value)
        )

    def get_all(self, name: str) -> List[str]:
        return [
            value
            for _, value in self._headers.get(
                name.lower(),
                [],
            )
        ]

    def items(self) -> Iterable[Tuple[str, str]]:
        for values in self._headers.values():
            yield from values


multi_headers = MultiValueHeaders()

multi_headers.add(
    "Set-Cookie",
    "session_id=abc; HttpOnly",
)

multi_headers.add(
    "Set-Cookie",
    "theme=dark; Path=/",
)

print("All Set-Cookie values:")
for value in multi_headers.get_all("set-cookie"):
    print(" ", value)


# =============================================================================
# SECTION 14: HOST HEADER
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 14: HOST HEADER")
print("=" * 80)

# Host identifies the target server.
#
# This is important because multiple websites may share the same IP address.

host_header = "api.example.com:443"

parsed_host = urllib.parse.urlsplit(
    f"https://{host_header}"
)

print("Host:", parsed_host.hostname)
print("Port:", parsed_host.port)


# =============================================================================
# SECTION 15: USER-AGENT
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 15: USER-AGENT")
print("=" * 80)

# User-Agent historically identifies the software making a request.
# Servers should not rely exclusively on User-Agent values for security because
# clients can modify them.

user_agent = "ExampleBrowser/1.0 ExamplePlatform"

print("User-Agent:", user_agent)


# =============================================================================
# SECTION 16: REFERER AND ORIGIN
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 16: REFERER AND ORIGIN")
print("=" * 80)

# Referer:
# Indicates the URL from which the request was made in many browser contexts.
#
# Origin:
# Represents the scheme, host, and port of a request origin.
#
# Example:
#
# Referer: https://example.com/page
# Origin: https://example.com
#
# These headers serve different purposes.

referer = "https://example.com/products"
origin = "https://example.com"

print("Referer:", referer)
print("Origin:", origin)


# =============================================================================
# SECTION 17: CORS-RELATED HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 17: CORS-RELATED HEADERS")
print("=" * 80)

# Cross-Origin Resource Sharing (CORS) is primarily enforced by browsers.
#
# Common response headers:
#
# Access-Control-Allow-Origin
# Access-Control-Allow-Methods
# Access-Control-Allow-Headers
# Access-Control-Allow-Credentials
#
# Example:
cors_response_headers = {
    "Access-Control-Allow-Origin": "https://frontend.example",
    "Access-Control-Allow-Methods": "GET, POST",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}

for name, value in cors_response_headers.items():
    print(f"{name}: {value}")

print(
    "\nImportant: CORS is not an authentication system. "
    "Server-side clients are not restricted by browser CORS enforcement."
)


# =============================================================================
# SECTION 18: CONTENT-LENGTH
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 18: CONTENT-LENGTH")
print("=" * 80)

message_body = b'{"message":"hello"}'

content_length = len(message_body)

print("Body:", message_body)
print("Content-Length:", content_length)

# Incorrect Content-Length values can cause protocol errors or clients to wait
# for bytes that will never arrive.


# =============================================================================
# SECTION 19: CONTENT-ENCODING AND COMPRESSION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 19: CONTENT-ENCODING AND COMPRESSION")
print("=" * 80)

original_content = (
    b"HTTP headers are metadata. " * 20
)

compressed_content = gzip.compress(original_content)

print("Original bytes:", len(original_content))
print("Compressed bytes:", len(compressed_content))

decompressed_content = gzip.decompress(compressed_content)

print(
    "Decompression restored original:",
    decompressed_content == original_content,
)

# Typical headers:
#
# Request:
# Accept-Encoding: gzip, deflate
#
# Response:
# Content-Encoding: gzip


# =============================================================================
# SECTION 20: ACCEPT-ENCODING NEGOTIATION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 20: ACCEPT-ENCODING")
print("=" * 80)


def client_accepts_encoding(
    accept_encoding: str,
    encoding: str,
) -> bool:
    """
    Simplified Accept-Encoding check.
    """

    accepted = [
        item.strip().split(";")[0].lower()
        for item in accept_encoding.split(",")
    ]

    return encoding.lower() in accepted or "*" in accepted


accept_encoding = "gzip, deflate"

print(
    "Client accepts gzip:",
    client_accepts_encoding(
        accept_encoding,
        "gzip",
    ),
)

print(
    "Client accepts br:",
    client_accepts_encoding(
        accept_encoding,
        "br",
    ),
)


# =============================================================================
# SECTION 21: SECURITY HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 21: SECURITY-RELATED RESPONSE HEADERS")
print("=" * 80)

security_headers = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=()",
}

for name, value in security_headers.items():
    print(f"{name}: {value}")

print(
    "\nSecurity headers complement application security. "
    "They do not replace authentication, authorization, input validation, "
    "secure session handling, or HTTPS."
)


# =============================================================================
# SECTION 22: CONTENT-DISPOSITION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 22: CONTENT-DISPOSITION")
print("=" * 80)

# Content-Disposition influences how content is presented.
#
# inline
# attachment
#
# Example:
# Content-Disposition: attachment; filename="report.pdf"

content_disposition = (
    'attachment; filename="report.pdf"'
)

print("Content-Disposition:", content_disposition)


# =============================================================================
# SECTION 23: RANGE REQUESTS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 23: RANGE REQUESTS")
print("=" * 80)

# A client may request part of a resource.
#
# Range: bytes=0-99
#
# The server may return:
# 206 Partial Content
#
# Content-Range: bytes 0-99/1000


def parse_byte_range(
    header_value: str,
    total_size: int,
) -> Tuple[int, int]:
    """
    Parse a simplified single HTTP byte range.

    Supports:
        bytes=0-99
        bytes=500-
        bytes=-100

    Returns inclusive start and end indexes.
    """

    if not header_value.startswith("bytes="):
        raise ValueError("Only bytes ranges are supported.")

    value = header_value[len("bytes="):]

    if "," in value:
        raise ValueError(
            "This educational implementation supports one range."
        )

    if "-" not in value:
        raise ValueError("Invalid range format.")

    start_text, end_text = value.split("-", 1)

    if not start_text and not end_text:
        raise ValueError("Range cannot be empty.")

    if not start_text:
        suffix_length = int(end_text)

        if suffix_length <= 0:
            raise ValueError(
                "Suffix length must be positive."
            )

        start = max(total_size - suffix_length, 0)
        end = total_size - 1

        return start, end

    start = int(start_text)

    if start >= total_size or start < 0:
        raise ValueError(
            "Range start is outside the resource."
        )

    if not end_text:
        return start, total_size - 1

    end = int(end_text)

    if end < start:
        raise ValueError(
            "Range end cannot be smaller than start."
        )

    end = min(end, total_size - 1)

    return start, end


file_data = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"

range_start, range_end = parse_byte_range(
    "bytes=5-9",
    len(file_data),
)

partial_data = file_data[
    range_start:range_end + 1
]

print(
    "Requested range:",
    range_start,
    "-",
    range_end,
)

print("Partial content:", partial_data)


# =============================================================================
# SECTION 24: IF-MODIFIED-SINCE
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 24: IF-MODIFIED-SINCE")
print("=" * 80)


def resource_modified_since(
    resource_time: datetime,
    if_modified_since: str,
) -> bool:
    """
    Determine whether a resource was modified after the supplied HTTP date.
    """

    client_time = parsedate_to_datetime(
        if_modified_since
    )

    if resource_time.tzinfo is None:
        resource_time = resource_time.replace(
            tzinfo=timezone.utc
        )

    if client_time.tzinfo is None:
        client_time = client_time.replace(
            tzinfo=timezone.utc
        )

    return resource_time > client_time


resource_time = datetime.now(timezone.utc)

past_time = format_datetime(
    resource_time.replace(
        year=max(resource_time.year - 1, 1971)
    ),
    usegmt=True,
)

print(
    "Resource modified since client timestamp:",
    resource_modified_since(
        resource_time,
        past_time,
    ),
)


# =============================================================================
# SECTION 25: REDIRECTION HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 25: REDIRECTION")
print("=" * 80)

# Redirect responses commonly use the Location header.
#
# HTTP/1.1 302 Found
# Location: https://example.com/new-location

redirect_response = {
    "Status": "302 Found",
    "Location": "https://example.com/new-location",
}

for name, value in redirect_response.items():
    print(f"{name}: {value}")


# =============================================================================
# SECTION 26: RETRY-AFTER
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 26: RETRY-AFTER")
print("=" * 80)

# Retry-After can appear with responses such as:
#
# 429 Too Many Requests
# 503 Service Unavailable
#
# It may specify a number of seconds or an HTTP date.


def parse_retry_after(value: str) -> float:
    """
    Parse Retry-After as seconds from now.

    This simplified implementation supports:
    - integer seconds
    - HTTP date
    """

    value = value.strip()

    if value.isdigit():
        return float(value)

    retry_datetime = parsedate_to_datetime(value)

    if retry_datetime.tzinfo is None:
        retry_datetime = retry_datetime.replace(
            tzinfo=timezone.utc
        )

    seconds = (
        retry_datetime
        - datetime.now(timezone.utc)
    ).total_seconds()

    return max(seconds, 0.0)


print(
    "Retry-After '30':",
    parse_retry_after("30"),
    "seconds",
)


# =============================================================================
# SECTION 27: RATE LIMIT HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 27: RATE LIMIT HEADERS")
print("=" * 80)

# APIs may communicate usage limits through response headers.
# Exact names vary by API implementation.

rate_limit_headers = {
    "RateLimit-Limit": "100",
    "RateLimit-Remaining": "42",
    "RateLimit-Reset": "60",
}

for name, value in rate_limit_headers.items():
    print(f"{name}: {value}")

print(
    "\nClients should not assume that every API uses the same "
    "rate-limit header naming convention."
)


# =============================================================================
# SECTION 28: FORWARDED AND PROXY HEADERS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 28: PROXIES AND FORWARDED HEADERS")
print("=" * 80)

# Reverse proxies may add forwarding metadata.
#
# Forwarded: for=192.0.2.1;proto=https;host=example.com
#
# X-Forwarded-For is also widely used:
# X-Forwarded-For: client, proxy1, proxy2
#
# Security warning:
# Applications must not blindly trust forwarding headers supplied directly by
# untrusted clients. Trust should be configured according to known proxies.


forwarded_value = (
    "for=192.0.2.1;proto=https;host=example.com"
)

print("Forwarded:", forwarded_value)


# =============================================================================
# SECTION 29: HEADER INJECTION AND VALIDATION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 29: HEADER VALIDATION")
print("=" * 80)

# Header values must not permit uncontrolled line breaks because CRLF sequences
# can potentially create header injection vulnerabilities in poorly designed
# systems.


def validate_header_value(value: str) -> None:
    """
    Reject CR and LF characters in header values.
    """

    if "\r" in value or "\n" in value:
        raise ValueError(
            "Header values must not contain CR or LF characters."
        )


safe_value = "application/json"
validate_header_value(safe_value)

print("Safe header value accepted:", safe_value)

try:
    validate_header_value(
        "safe-value\r\nInjected-Header: malicious"
    )
except ValueError as error:
    print("Unsafe header rejected:", error)


# =============================================================================
# SECTION 30: COMMON HEADER MISTAKES
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 30: COMMON MISTAKES")
print("=" * 80)

common_mistakes = [
    (
        "Using Content-Type to describe desired response format",
        "Use Accept to express preferred response formats.",
    ),
    (
        "Treating Base64 Basic credentials as encryption",
        "Use HTTPS because Base64 encoding is reversible.",
    ),
    (
        "Using no-cache when no storage is required",
        "Understand that no-cache allows storage but requires validation.",
    ),
    (
        "Combining multiple Set-Cookie values incorrectly",
        "Preserve separate Set-Cookie header fields.",
    ),
    (
        "Trusting User-Agent for authorization",
        "User-Agent values can be modified by clients.",
    ),
    (
        "Trusting X-Forwarded-For from arbitrary clients",
        "Only trust forwarding headers from configured proxies.",
    ),
    (
        "Sending secrets over HTTP",
        "Use HTTPS for credentials and sensitive data.",
    ),
]

for mistake, correction in common_mistakes:
    print(f"\nMistake: {mistake}")
    print(f"Correct approach: {correction}")


# =============================================================================
# SECTION 31: BUILDING A RAW HTTP REQUEST
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 31: RAW HTTP REQUEST CONSTRUCTION")
print("=" * 80)


def build_http_request(
    method: str,
    path: str,
    headers: Dict[str, str],
    body: bytes = b"",
) -> bytes:
    """
    Build a simplified HTTP/1.1 request message.

    This is educational code and does not implement every HTTP rule.
    """

    method = method.upper()

    request_lines = [
        f"{method} {path} HTTP/1.1"
    ]

    normalized_headers = dict(headers)

    if body and "Content-Length" not in normalized_headers:
        normalized_headers["Content-Length"] = str(
            len(body)
        )

    for name, value in normalized_headers.items():
        validate_header_value(value)
        request_lines.append(f"{name}: {value}")

    request_text = (
        "\r\n".join(request_lines)
        + "\r\n\r\n"
    )

    return request_text.encode("iso-8859-1") + body


raw_request = build_http_request(
    method="POST",
    path="/api/users",
    headers={
        "Host": "example.com",
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
    body=json.dumps(
        {
            "name": "Asha",
        }
    ).encode("utf-8"),
)

print(
    raw_request.decode(
        "utf-8",
        errors="replace",
    )
)


# =============================================================================
# SECTION 32: PARSING A SIMPLE HTTP HEADER BLOCK
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 32: PARSING HEADER BLOCKS")
print("=" * 80)


def parse_header_block(
    raw_headers: str,
) -> CaseInsensitiveHeaders:
    """
    Parse a simplified HTTP header block.

    Each line should have:
        Header-Name: Header Value
    """

    parsed_headers = CaseInsensitiveHeaders()

    for line in raw_headers.splitlines():
        line = line.strip()

        if not line:
            continue

        if ":" not in line:
            raise ValueError(
                f"Invalid header line: {line!r}"
            )

        name, value = line.split(":", 1)

        name = name.strip()
        value = value.strip()

        if not name:
            raise ValueError(
                "Header name cannot be empty."
            )

        validate_header_value(value)

        parsed_headers.set(name, value)

    return parsed_headers


raw_header_block = """
Content-Type: application/json
Accept: application/json
Cache-Control: no-cache
"""

parsed_headers = parse_header_block(
    raw_header_block
)

for name, value in parsed_headers.items():
    print(f"{name}: {value}")


# =============================================================================
# SECTION 33: PRACTICAL CLIENT USING urllib
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 33: PRACTICAL HTTP CLIENT")
print("=" * 80)

# urllib.request is part of the Python standard library.
#
# The following function demonstrates how to attach request headers and inspect
# response headers.


def fetch_url(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 5.0,
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Perform an HTTP GET request.

    Returns:
        status code
        response headers
        response body
    """

    request = urllib.request.Request(
        url=url,
        headers=headers or {},
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        response_headers = dict(
            response.headers.items()
        )

        return (
            response.status,
            response_headers,
            response.read(),
        )


print(
    "The fetch_url function is defined but external requests are not required "
    "for this tutorial demonstration."
)


# =============================================================================
# SECTION 34: LOCAL HTTP SERVER FOR HEADER DEMONSTRATION
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 34: LOCAL HTTP SERVER")
print("=" * 80)


class HeaderDemoHandler(BaseHTTPRequestHandler):
    """
    A small HTTP server handler demonstrating request inspection and response
    header construction.
    """

    server_version = "HeaderTutorialServer/1.0"

    def log_message(
        self,
        format_string: str,
        *arguments: Any,
    ) -> None:
        """
        Reduce default server logging for cleaner tutorial output.
        """

        return

    def do_GET(self) -> None:
        """
        Respond with JSON containing selected request header information.
        """

        accept = self.headers.get(
            "Accept",
            "*/*",
        )

        user_agent = self.headers.get(
            "User-Agent",
            "Unknown",
        )

        if_none_match = self.headers.get(
            "If-None-Match",
        )

        response_data = {
            "path": self.path,
            "accept": accept,
            "user_agent": user_agent,
            "message": "HTTP header demonstration",
        }

        body = json.dumps(
            response_data
        ).encode("utf-8")

        etag = generate_etag(body)

        if if_none_match == etag:
            self.send_response(
                HTTPStatus.NOT_MODIFIED
            )

            self.send_header(
                "ETag",
                etag,
            )

            self.end_headers()

            return

        self.send_response(HTTPStatus.OK)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Cache-Control",
            "max-age=60",
        )

        self.send_header(
            "ETag",
            etag,
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.send_header(
            "Set-Cookie",
            "tutorial=active; Path=/; HttpOnly",
        )

        self.end_headers()

        self.wfile.write(body)


def start_local_server() -> Tuple[
    ThreadingHTTPServer,
    threading.Thread,
]:
    """
    Start a local HTTP server on an automatically selected port.
    """

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        HeaderDemoHandler,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    thread.start()

    return server, thread


server, server_thread = start_local_server()

server_host, server_port = server.server_address

local_url = (
    f"http://{server_host}:{server_port}/headers"
)

print("Local server URL:", local_url)


# =============================================================================
# SECTION 35: CLIENT-SERVER HEADER EXCHANGE
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 35: CLIENT-SERVER HEADER EXCHANGE")
print("=" * 80)

request_headers = {
    "Accept": "application/json",
    "User-Agent": "HeaderTutorialClient/1.0",
}

status_code, response_headers, response_body = fetch_url(
    local_url,
    headers=request_headers,
)

print("Response status:", status_code)

print("\nSelected response headers:")
for header_name in [
    "Content-Type",
    "Content-Length",
    "Cache-Control",
    "ETag",
    "X-Content-Type-Options",
]:
    print(
        f"  {header_name}: "
        f"{response_headers.get(header_name)}"
    )

print(
    "\nResponse body:",
    response_body.decode("utf-8"),
)


# =============================================================================
# SECTION 36: CONDITIONAL REQUEST AGAINST THE LOCAL SERVER
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 36: CONDITIONAL LOCAL REQUEST")
print("=" * 80)

# Important subtlety:
#
# The local handler includes request-specific data such as User-Agent and Accept
# in the response body. A matching request is therefore required to reproduce
# the same ETag.

first_request_headers = {
    "Accept": "application/json",
    "User-Agent": "HeaderTutorialClient/1.0",
}

first_status, first_headers, first_body = fetch_url(
    local_url,
    headers=first_request_headers,
)

received_etag = first_headers.get("ETag")

print("First request status:", first_status)
print("Received ETag:", received_etag)

conditional_headers = {
    **first_request_headers,
    "If-None-Match": received_etag,
}

conditional_request = urllib.request.Request(
    local_url,
    headers=conditional_headers,
    method="GET",
)

try:
    with urllib.request.urlopen(
        conditional_request,
        timeout=5,
    ) as response:
        print(
            "Conditional response status:",
            response.status,
        )

except urllib.error.HTTPError as error:
    # urllib treats 304 as an HTTPError even though 304 is a valid conditional
    # response and not necessarily an application failure.
    print(
        "Conditional response status:",
        error.code,
        error.reason,
    )


# =============================================================================
# SECTION 37: INSPECTING RAW HEADERS WITH http.client
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 37: INSPECTING HTTP HEADERS WITH http.client")
print("=" * 80)

connection = HTTPConnection(
    server_host,
    server_port,
    timeout=5,
)

connection.request(
    "GET",
    "/raw-inspection",
    headers={
        "Accept": "application/json",
        "User-Agent": "RawInspectionClient/1.0",
    },
)

response = connection.getresponse()

print(
    "Status:",
    response.status,
    response.reason,
)

print("\nRaw-style response headers:")

for name, value in response.getheaders():
    print(f"  {name}: {value}")

response.read()
connection.close()


# =============================================================================
# SECTION 38: CONTENT-TYPE BASED RESPONSE PROCESSING
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 38: PROCESSING RESPONSES BY CONTENT-TYPE")
print("=" * 80)


def decode_response_body(
    content_type: str,
    body: bytes,
) -> Any:
    """
    Decode a response according to a simplified Content-Type strategy.
    """

    media_type = parse_content_type(
        content_type
    )

    full_type = (
        f"{media_type.main_type}/"
        f"{media_type.sub_type}"
    )

    charset = media_type.parameters.get(
        "charset",
        "utf-8",
    )

    if full_type == "application/json":
        return json.loads(
            body.decode(charset)
        )

    if full_type.startswith("text/"):
        return body.decode(charset)

    return body


json_body = b'{"status":"ok","count":3}'

decoded_json = decode_response_body(
    "application/json; charset=utf-8",
    json_body,
)

print(
    "Decoded JSON:",
    decoded_json,
)

text_body = b"Plain text response"

decoded_text = decode_response_body(
    "text/plain; charset=utf-8",
    text_body,
)

print(
    "Decoded text:",
    decoded_text,
)


# =============================================================================
# SECTION 39: SIMPLE API REQUEST BUILDER
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 39: API REQUEST BUILDER")
print("=" * 80)


@dataclass
class APIRequest:
    method: str
    url: str
    headers: Dict[str, str] = field(
        default_factory=dict
    )
    body: Optional[bytes] = None

    def set_json_body(
        self,
        data: Any,
    ) -> None:
        """
        Serialize Python data as JSON and set the appropriate Content-Type.
        """

        self.body = json.dumps(
            data,
            separators=(",", ":"),
        ).encode("utf-8")

        self.headers[
            "Content-Type"
        ] = "application/json"

        self.headers[
            "Content-Length"
        ] = str(len(self.body))

    def set_bearer_token(
        self,
        token: str,
    ) -> None:
        self.headers[
            "Authorization"
        ] = create_bearer_authorization(
            token
        )

    def set_accept_json(self) -> None:
        self.headers[
            "Accept"
        ] = "application/json"

    def build_summary(self) -> Dict[str, Any]:
        """
        Return a safe request summary.

        Authorization values are masked to avoid accidental secret exposure in
        logs and debugging output.
        """

        safe_headers = dict(self.headers)

        if "Authorization" in safe_headers:
            safe_headers[
                "Authorization"
            ] = "<redacted>"

        return {
            "method": self.method.upper(),
            "url": self.url,
            "headers": safe_headers,
            "body_length": (
                len(self.body)
                if self.body is not None
                else 0
            ),
        }


api_request = APIRequest(
    method="POST",
    url="https://api.example.com/users",
)

api_request.set_accept_json()

api_request.set_bearer_token(
    "example-secret-token"
)

api_request.set_json_body(
    {
        "name": "Asha",
        "role": "developer",
    }
)

print(
    json.dumps(
        api_request.build_summary(),
        indent=2,
    )
)


# =============================================================================
# SECTION 40: DEBUGGING HEADERS SAFELY
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 40: SAFE HEADER DEBUGGING")
print("=" * 80)

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}


def redact_headers(
    headers: Dict[str, str],
) -> Dict[str, str]:
    """
    Create a safe copy of headers for logs.
    """

    result: Dict[str, str] = {}

    for name, value in headers.items():
        if name.lower() in SENSITIVE_HEADERS:
            result[name] = "<redacted>"
        else:
            result[name] = value

    return result


headers_for_logging = {
    "Accept": "application/json",
    "Authorization": "Bearer secret-token",
    "Cookie": "session_id=private",
}

print(
    "Safe logging output:",
    redact_headers(
        headers_for_logging
    ),
)


# =============================================================================
# SECTION 41: PERFORMANCE CONSIDERATIONS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 41: PERFORMANCE CONSIDERATIONS")
print("=" * 80)

# Headers consume network bandwidth.
#
# Large cookies and excessively large custom headers increase request size.
#
# Repeated metadata can affect latency, especially in high-volume systems.
#
# Compression usually applies to message bodies rather than arbitrary
# application-level header design.
#
# Caching headers can significantly reduce repeated transfers.

performance_considerations = [
    "Avoid unnecessarily large cookies.",
    "Avoid transmitting secrets in URLs.",
    "Use cache validators such as ETag when appropriate.",
    "Use Cache-Control intentionally.",
    "Avoid excessive custom metadata.",
    "Use Content-Encoding when body compression is beneficial.",
]

for item in performance_considerations:
    print("-", item)


# =============================================================================
# SECTION 42: HEADER SIZE LIMITS
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 42: HEADER SIZE LIMITS")
print("=" * 80)

# Servers, proxies, browsers, and HTTP libraries may impose different limits on:
#
# - individual header size
# - total header section size
# - number of headers
#
# Applications should not assume arbitrarily large headers will be accepted.

large_header_value = "x" * 1000

print(
    "Example custom header value length:",
    len(large_header_value),
)

print(
    "Production systems should define and enforce reasonable header size limits."
)


# =============================================================================
# SECTION 43: TESTING HEADER LOGIC
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 43: TESTING")
print("=" * 80)


def run_basic_tests() -> None:
    """
    Execute basic assertions for important tutorial behavior.
    """

    headers = CaseInsensitiveHeaders()

    headers.set(
        "Content-Type",
        "application/json",
    )

    assert (
        headers.get("content-type")
        == "application/json"
    )

    assert (
        media_type_matches(
            "application/json",
            "application/json",
        )
        is True
    )

    assert (
        media_type_matches(
            "text/*",
            "text/plain",
        )
        is True
    )

    assert (
        media_type_matches(
            "text/*",
            "application/json",
        )
        is False
    )

    assert (
        negotiate_content(
            "application/json",
            ["text/html", "application/json"],
        )
        == "application/json"
    )

    assert (
        parse_cookie_header(
            "a=1; b=2"
        )
        == {
            "a": "1",
            "b": "2",
        }
    )

    assert (
        parse_cache_control(
            "private, max-age=60"
        )
        == {
            "private": None,
            "max-age": "60",
        }
    )

    assert (
        parse_byte_range(
            "bytes=0-4",
            10,
        )
        == (0, 4)
    )

    assert (
        parse_byte_range(
            "bytes=5-",
            10,
        )
        == (5, 9)
    )

    assert (
        parse_byte_range(
            "bytes=-3",
            10,
        )
        == (7, 9)
    )

    try:
        validate_header_value(
            "bad\nvalue"
        )
        raise AssertionError(
            "Unsafe header should have failed."
        )

    except ValueError:
        pass


run_basic_tests()

print(
    "All basic header tests passed."
)


# =============================================================================
# SECTION 44: POSTMAN AND BROWSER DEVTOOLS WORKFLOW
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 44: PRACTICAL INSPECTION WORKFLOW")
print("=" * 80)

print(
    """
Postman workflow:

1. Create an HTTP request.
2. Select the HTTP method.
3. Enter the URL.
4. Open the Headers section.
5. Add request headers such as:
       Accept: application/json
       Content-Type: application/json
       Authorization: Bearer <token>
6. Send the request.
7. Inspect response headers.
8. Compare Content-Type with the actual response body.
9. Inspect caching headers such as Cache-Control and ETag.
10. Avoid exposing secrets in shared screenshots or exported collections.

Browser DevTools workflow:

1. Open the browser developer tools.
2. Open the Network panel.
3. Perform the request.
4. Select the network request.
5. Inspect Request Headers.
6. Inspect Response Headers.
7. Inspect Cookies where available.
8. Compare status code, headers, timing, and response content.
9. Check cache-related behavior.
10. Inspect CORS-related headers when debugging browser requests.
""".strip()
)


# =============================================================================
# SECTION 45: PRACTICAL HEADER CHECKLIST
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 45: PRACTICAL HEADER CHECKLIST")
print("=" * 80)

checklist = {
    "Content-Type": (
        "Does it accurately describe the message body?"
    ),
    "Accept": (
        "Does it express the response formats the client can process?"
    ),
    "Authorization": (
        "Are credentials required and protected with HTTPS?"
    ),
    "Cache-Control": (
        "Does caching behavior match the data sensitivity and freshness needs?"
    ),
    "Cookies": (
        "Are Secure, HttpOnly, SameSite, Path, and lifetime attributes appropriate?"
    ),
    "ETag": (
        "Can conditional requests reduce unnecessary transfers?"
    ),
    "Security headers": (
        "Are browser security policies appropriate for the application?"
    ),
    "Logging": (
        "Are credentials and cookies redacted?"
    ),
    "Forwarded headers": (
        "Are proxy headers trusted only from configured infrastructure?"
    ),
}

for header_area, question in checklist.items():
    print(f"\n{header_area}:")
    print(f"  {question}")


# =============================================================================
# SECTION 46: SERVER SHUTDOWN
# =============================================================================

print("\n" + "=" * 80)
print("SECTION 46: CLEAN SHUTDOWN")
print("=" * 80)

server.shutdown()
server.server_close()

print(
    "Local HTTP server stopped."
)


# =============================================================================
# FINAL REFERENCE TABLE
# =============================================================================

print("\n" + "=" * 80)
print("HTTP HEADER REFERENCE")
print("=" * 80)

reference_headers = [
    (
        "Content-Type",
        "Describes the format of a message body.",
    ),
    (
        "Accept",
        "Expresses acceptable response media types.",
    ),
    (
        "Authorization",
        "Carries authentication credentials.",
    ),
    (
        "Cache-Control",
        "Controls caching behavior.",
    ),
    (
        "Cookie",
        "Sends stored cookies from client to server.",
    ),
    (
        "Set-Cookie",
        "Instructs a client to store or modify a cookie.",
    ),
    (
        "ETag",
        "Identifies a specific representation version.",
    ),
    (
        "If-None-Match",
        "Performs conditional requests using ETags.",
    ),
    (
        "Content-Length",
        "Indicates body length in bytes when applicable.",
    ),
    (
        "Content-Encoding",
        "Describes transformations such as compression.",
    ),
    (
        "Accept-Encoding",
        "Expresses supported response encodings.",
    ),
    (
        "Location",
        "Provides a target location, commonly for redirects.",
    ),
    (
        "Origin",
        "Identifies the origin associated with a request.",
    ),
    (
        "Access-Control-Allow-Origin",
        "Participates in browser CORS handling.",
    ),
    (
        "Strict-Transport-Security",
        "Directs browsers to prefer HTTPS under configured rules.",
    ),
]

for header_name, purpose in reference_headers:
    print(f"{header_name:35} {purpose}")

print("\nHTTP header tutorial completed successfully.")
