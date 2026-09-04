"""
HTTP Fundamentals
=================

A comprehensive, executable study script covering HTTP from absolute
beginner concepts through advanced practical behavior.

Topics demonstrated:
- What HTTP is and why it exists
- Client-server communication
- HTTP requests and responses
- URLs and URI components
- HTTP methods and method semantics
- Request and response headers
- Request and response bodies
- Media types and content negotiation
- HTTP status codes
- The HTTP request lifecycle
- HTTP/1.0, HTTP/1.1, HTTP/2, and HTTP/3 concepts
- Persistent connections
- Chunked transfer encoding
- Compression
- Cookies and sessions
- Caching
- Conditional requests
- Redirects
- Authentication and authorization concepts
- Idempotency and safety
- Content-Length and Transfer-Encoding
- Proxies and intermediaries
- Connection management
- TLS and HTTPS
- Timeouts and retries
- Error handling
- Security considerations
- API design considerations
- Raw HTTP message construction and parsing
- A small HTTP server and client using only the Python standard library
- Testing and practical diagnostics

The script intentionally uses the Python standard library so that the
fundamental HTTP mechanisms remain visible instead of being hidden behind
a third-party framework.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from http.cookies import SimpleCookie
from io import BytesIO
from typing import Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import (
    parse_qs,
    quote,
    unquote,
    urlencode,
    urlparse,
    urlunparse,
)
from urllib.request import Request, build_opener, HTTPBasicAuthHandler
from urllib.error import HTTPError, URLError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    """Print a readable subsection heading."""
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


# =============================================================================
# 1. HTTP: THE FUNDAMENTAL IDEA
# =============================================================================

section("1. HTTP: THE FUNDAMENTAL IDEA")

print(
    """
HTTP stands for Hypertext Transfer Protocol.

HTTP is an application-layer protocol used to exchange representations of
resources between clients and servers.

A client sends an HTTP request.
A server processes that request and sends an HTTP response.

The client is commonly a browser, mobile application, command-line client,
Python program, or another server.

The server is commonly a web server, API server, application server, proxy,
gateway, or reverse proxy.

A simplified communication pattern is:

    Client
       |
       | HTTP Request
       v
    Server
       |
       | HTTP Response
       v
    Client

HTTP itself defines the structure and semantics of messages. Network
connections, DNS resolution, TCP, TLS, and HTTP versions provide additional
layers that make the communication possible.
"""
)


# =============================================================================
# 2. CLIENT, SERVER, RESOURCE, REQUEST, RESPONSE
# =============================================================================

section("2. CLIENT, SERVER, RESOURCE, REQUEST, AND RESPONSE")

client = "Browser"
server = "example.com"
resource = "/products"

print(f"Client:   {client}")
print(f"Server:   {server}")
print(f"Resource: {resource}")

print(
    """
A resource is identified by a URI. A URL is a commonly used form of URI that
also provides the location and access scheme.

The important distinction is:

    Resource
        What is being requested.

    Request
        The message expressing what the client wants.

    Response
        The server's result.

An HTTP request does not necessarily mean "give me a webpage". It may mean:

    GET      retrieve a representation
    POST     submit data for processing
    PUT      replace a resource representation
    PATCH    partially modify a resource
    DELETE   remove a resource
    HEAD     retrieve metadata without a response body
    OPTIONS  ask about communication options
"""
)


# =============================================================================
# 3. URL STRUCTURE
# =============================================================================

section("3. URL STRUCTURE")

url = "https://api.example.com:8443/users/42?active=true&sort=name#profile"
parsed = urlparse(url)

print("URL:", url)
print("Scheme:", parsed.scheme)
print("Network location:", parsed.netloc)
print("Hostname:", parsed.hostname)
print("Port:", parsed.port)
print("Path:", parsed.path)
print("Query:", parsed.query)
print("Fragment:", parsed.fragment)

print(
    """
Typical URL structure:

    scheme://authority/path?query#fragment

Example:

    https://example.com/products/42?currency=INR#details

scheme:
    Identifies the protocol or access mechanism.

authority:
    Usually contains host information and optionally a port.

path:
    Identifies a resource or routing target.

query:
    Carries parameters associated with the request target.

fragment:
    Identifies a secondary location within a representation.

The fragment is normally processed by the user agent and is not sent to the
server in an ordinary HTTP request.
"""
)

query_parameters = parse_qs(parsed.query)
print("Parsed query parameters:", query_parameters)

encoded = quote("HTTP fundamentals & APIs")
print("Percent-encoded value:", encoded)
print("Decoded value:", unquote(encoded))

generated_query = urlencode(
    {
        "language": "Python",
        "topic": "HTTP",
        "page": 1,
    }
)
print("Generated query string:", generated_query)


# =============================================================================
# 4. DNS, CONNECTION, TLS, AND HTTP
# =============================================================================

section("4. WHAT HAPPENS BEFORE HTTP DATA IS EXCHANGED")

print(
    """
For a typical HTTPS request, several layers participate:

    Application:
        HTTP

    Security:
        TLS

    Transport:
        Usually TCP for HTTP/1.1 and HTTP/2

    Network:
        IP

    Name resolution:
        DNS

A simplified HTTPS lifecycle is:

    1. Application decides to access a URL.
    2. DNS resolves the hostname to an IP address.
    3. A transport connection is established.
    4. TLS negotiation occurs for HTTPS.
    5. HTTP request is sent.
    6. Server processes the request.
    7. HTTP response is returned.
    8. Client consumes the response.
    9. The connection may remain available for reuse.

HTTP/3 changes the transport layer by using QUIC over UDP instead of TCP.
"""
)


# =============================================================================
# 5. RAW HTTP REQUEST
# =============================================================================

section("5. RAW HTTP REQUEST")

raw_request = (
    "GET /products?page=2 HTTP/1.1\r\n"
    "Host: example.com\r\n"
    "Accept: application/json\r\n"
    "User-Agent: StudyClient/1.0\r\n"
    "Connection: keep-alive\r\n"
    "\r\n"
)

print(raw_request)

print(
    """
The request contains:

    Request line
        Method + request target + HTTP version

    Headers
        Metadata describing the request

    Blank line
        Separates headers from the optional body

    Body
        Optional request content

The blank line is significant. HTTP/1.x uses CRLF line endings for protocol
message formatting.
"""
)


# =============================================================================
# 6. RAW HTTP RESPONSE
# =============================================================================

section("6. RAW HTTP RESPONSE")

raw_response = (
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: text/plain; charset=utf-8\r\n"
    "Content-Length: 13\r\n"
    "\r\n"
    "Hello, client!"
)

print(raw_response)

print(
    """
A response contains:

    Status line
        HTTP version + status code + reason phrase

    Headers
        Metadata describing the response

    Blank line

    Body
        Optional representation or response data
"""
)


# =============================================================================
# 7. HTTP METHODS
# =============================================================================

section("7. HTTP METHODS")

methods = {
    "GET": {
        "purpose": "Retrieve a representation",
        "safe": True,
        "idempotent": True,
    },
    "HEAD": {
        "purpose": "Retrieve response metadata without the response content",
        "safe": True,
        "idempotent": True,
    },
    "POST": {
        "purpose": "Submit data for processing or create subordinate resources",
        "safe": False,
        "idempotent": False,
    },
    "PUT": {
        "purpose": "Create or replace the target representation",
        "safe": False,
        "idempotent": True,
    },
    "PATCH": {
        "purpose": "Apply partial modifications",
        "safe": False,
        "idempotent": False,
    },
    "DELETE": {
        "purpose": "Delete the target resource",
        "safe": False,
        "idempotent": True,
    },
    "OPTIONS": {
        "purpose": "Describe communication options",
        "safe": True,
        "idempotent": True,
    },
    "TRACE": {
        "purpose": "Diagnostic loop-back",
        "safe": True,
        "idempotent": True,
    },
    "CONNECT": {
        "purpose": "Establish a tunnel through an intermediary",
        "safe": False,
        "idempotent": False,
    },
}

for method, properties in methods.items():
    print(
        f"{method:8} | "
        f"safe={str(properties['safe']):5} | "
        f"idempotent={str(properties['idempotent']):5} | "
        f"{properties['purpose']}"
    )

print(
    """
Safety and idempotency are semantic properties.

Safe:
    The method is intended not to request a state-changing action from the
    origin server.

Idempotent:
    Repeating the same request has the same intended effect as making it once.

Important:
    Idempotent does not mean "the response will always be identical".

For example, a DELETE request may return 204 the first time and 404 later,
while the intended state-changing effect remains idempotent.

POST is generally non-idempotent because sending the same request repeatedly
may create multiple resources or trigger multiple operations.
"""
)


# =============================================================================
# 8. REQUEST TARGETS
# =============================================================================

section("8. REQUEST TARGET FORMS")

request_targets = [
    "/index.html",
    "https://example.com/index.html",
    "*",
    "example.com:443",
]

for target in request_targets:
    print(target)

print(
    """
HTTP defines several request-target forms.

Origin-form:
    /path?query

Absolute-form:
    https://example.com/path

Authority-form:
    example.com:443

Asterisk-form:
    *

The origin-form is common when a client communicates directly with an origin
server. Proxies can receive absolute-form targets.
"""
)


# =============================================================================
# 9. REQUEST HEADERS
# =============================================================================

section("9. REQUEST HEADERS")

request_headers = {
    "Host": "api.example.com",
    "User-Agent": "HTTPStudyClient/1.0",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json",
    "Content-Length": "27",
}

for name, value in request_headers.items():
    print(f"{name}: {value}")

print(
    """
Headers provide metadata and control information.

Common request headers include:

    Host
        Identifies the target host in HTTP/1.1 requests.

    User-Agent
        Identifies the client software.

    Accept
        Describes response media types the client can process.

    Accept-Encoding
        Advertises supported content codings.

    Content-Type
        Describes the media type of the request body.

    Content-Length
        Describes the body size in bytes when used.

    Authorization
        Carries authentication credentials or tokens.

    Cookie
        Sends previously stored cookies.

    If-None-Match
        Enables conditional requests using an entity tag.

    If-Modified-Since
        Enables conditional requests using a modification date.

Headers are case-insensitive by field name.
"""
)


# =============================================================================
# 10. RESPONSE HEADERS
# =============================================================================

section("10. RESPONSE HEADERS")

response_headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": "48",
    "Cache-Control": "max-age=60",
    "ETag": '"abc123"',
    "Date": format_datetime(datetime.now(timezone.utc), usegmt=True),
    "Set-Cookie": "session_id=example; Path=/; HttpOnly; Secure",
}

for name, value in response_headers.items():
    print(f"{name}: {value}")

print(
    """
Common response headers include:

    Content-Type
        Media type of the representation.

    Content-Length
        Number of body bytes when applicable.

    Content-Encoding
        Content coding such as gzip.

    Cache-Control
        Directives controlling caching.

    ETag
        Identifier for a particular representation state.

    Last-Modified
        Time associated with the selected representation.

    Location
        Identifies a URI associated with redirects or resource creation.

    Set-Cookie
        Requests that the user agent store a cookie.

    WWW-Authenticate
        Indicates authentication schemes for a 401 response.
"""
)


# =============================================================================
# 11. REQUEST BODY
# =============================================================================

section("11. REQUEST BODY")

json_payload = {
    "name": "Alice",
    "role": "developer",
}

request_body = json.dumps(json_payload).encode("utf-8")

print("Python object:", json_payload)
print("Serialized JSON:", request_body.decode("utf-8"))
print("Body size in bytes:", len(request_body))

print(
    """
A request body carries content associated with the request.

Typical body formats include:

    application/json
    application/x-www-form-urlencoded
    multipart/form-data
    text/plain
    application/xml
    application/octet-stream

The Content-Type header describes the representation format.

The server must not assume that a body is JSON merely because the URL ends
with an API-looking path.

It should inspect and validate the declared media type and actual content.
"""
)


# =============================================================================
# 12. RESPONSE BODY
# =============================================================================

section("12. RESPONSE BODY")

response_payload = {
    "id": 42,
    "name": "Alice",
    "active": True,
}

response_body = json.dumps(response_payload).encode("utf-8")

print(response_body.decode("utf-8"))
print("Response body length:", len(response_body))

print(
    """
A response body can contain:

    HTML
    JSON
    XML
    images
    audio
    video
    text
    binary data
    no content

A response body is not guaranteed to exist.

Examples where a response body may be absent include:

    HEAD responses
    204 No Content
    304 Not Modified

The semantics of the status code determine how the body should be handled.
"""
)


# =============================================================================
# 13. MEDIA TYPES
# =============================================================================

section("13. MEDIA TYPES")

media_types = [
    "text/html",
    "text/plain",
    "application/json",
    "application/xml",
    "application/octet-stream",
    "multipart/form-data",
    "application/x-www-form-urlencoded",
]

for media_type in media_types:
    print(media_type)

print(
    """
A media type identifies the format of a representation.

General form:

    type/subtype

Optional parameters can provide additional information:

    text/html; charset=utf-8

The client and server use Content-Type and Accept to communicate
representation expectations.

Content negotiation can become more sophisticated than simply choosing JSON.
"""
)


# =============================================================================
# 14. ACCEPT HEADER AND QUALITY VALUES
# =============================================================================

section("14. CONTENT NEGOTIATION")

accept_header = "text/html;q=0.8, application/json;q=1.0, text/plain;q=0.5"
print("Accept:", accept_header)

print(
    """
A client can express preferences using quality values.

For example:

    application/json;q=1.0
    text/html;q=0.8
    text/plain;q=0.5

The server may use these preferences when selecting a representation.

Content negotiation can involve:

    Accept
    Accept-Language
    Accept-Encoding

The selected response should still respect server capabilities and resource
semantics.
"""
)


# =============================================================================
# 15. STATUS CODES
# =============================================================================

section("15. HTTP STATUS CODES")

for status in HTTPStatus:
    if status.value < 600:
        print(f"{status.value:3} {status.phrase}")

print(
    """
HTTP status codes are grouped by their first digit:

    1xx
        Informational

    2xx
        Successful

    3xx
        Redirection

    4xx
        Client error

    5xx
        Server error

The numeric code is the important machine-readable value. The reason phrase
is secondary and should not be treated as a stable API contract.
"""
)


# =============================================================================
# 16. IMPORTANT STATUS CODES
# =============================================================================

section("16. IMPORTANT STATUS CODES")

important_statuses = [
    200,
    201,
    202,
    204,
    206,
    301,
    302,
    303,
    304,
    307,
    308,
    400,
    401,
    403,
    404,
    405,
    406,
    409,
    410,
    412,
    413,
    415,
    422,
    429,
    500,
    501,
    502,
    503,
    504,
]

for code in important_statuses:
    status = HTTPStatus(code)
    print(f"{code}: {status.phrase}")

print(
    """
Frequently encountered meanings:

200 OK
    Request succeeded.

201 Created
    A resource was successfully created.

202 Accepted
    Request accepted for processing, but processing may not be complete.

204 No Content
    Request succeeded and there is intentionally no response content.

206 Partial Content
    Server is returning a requested range of a representation.

301 Moved Permanently
    Permanent redirection.

302 Found
    Temporary redirection semantics.

303 See Other
    Redirects the client to another resource, commonly after POST.

304 Not Modified
    Cached representation remains valid under a conditional request.

307 Temporary Redirect
    Temporary redirect that preserves the request method.

308 Permanent Redirect
    Permanent redirect that preserves the request method.

400 Bad Request
    Request cannot be processed because of malformed or invalid input.

401 Unauthorized
    Authentication is required or failed. The name can be misleading:
    authentication, not authorization, is the primary concept.

403 Forbidden
    Server understood the request but refuses to fulfill it.

404 Not Found
    Target resource was not found or is intentionally undisclosed.

405 Method Not Allowed
    Method is known but not supported for the target resource.

409 Conflict
    Request conflicts with the current resource state.

412 Precondition Failed
    A supplied request precondition evaluated to false.

415 Unsupported Media Type
    Representation format is not supported.

422 Unprocessable Content
    Content type may be understood, but the content cannot be processed
    because of semantic validation problems.

429 Too Many Requests
    Client exceeded a rate limit.

500 Internal Server Error
    Unexpected server-side failure.

502 Bad Gateway
    Gateway or proxy received an invalid response from an upstream server.

503 Service Unavailable
    Server is temporarily unable to handle the request.

504 Gateway Timeout
    Gateway or proxy did not receive a timely upstream response.
"""
)


# =============================================================================
# 17. STATUS CODE DECISION EXAMPLES
# =============================================================================

section("17. STATUS CODE DECISION EXAMPLES")

def choose_creation_status(resource_created: bool) -> HTTPStatus:
    """Illustrate choosing a status according to operation outcome."""
    if resource_created:
        return HTTPStatus.CREATED
    return HTTPStatus.CONFLICT


def choose_get_status(found: bool) -> HTTPStatus:
    """Illustrate a simple retrieval outcome."""
    if found:
        return HTTPStatus.OK
    return HTTPStatus.NOT_FOUND


print("Create result:", choose_creation_status(True))
print("Create conflict:", choose_creation_status(False))
print("GET found:", choose_get_status(True))
print("GET missing:", choose_get_status(False))


# =============================================================================
# 18. HTTP LIFECYCLE
# =============================================================================

section("18. COMPLETE HTTP REQUEST LIFECYCLE")

lifecycle = [
    "Application constructs a target URL.",
    "Hostname may be resolved using DNS.",
    "Client establishes or reuses a network connection.",
    "TLS negotiation occurs for HTTPS when required.",
    "Client constructs the HTTP request.",
    "Request headers and optional body are transmitted.",
    "Intermediaries may inspect, route, cache, transform, or reject it.",
    "Origin server receives and parses the request.",
    "Application routing identifies the target operation.",
    "Authentication and authorization may be evaluated.",
    "Application logic processes the request.",
    "Server constructs an HTTP response.",
    "Response headers and optional body are transmitted.",
    "Client parses the status, headers, and body.",
    "Client may store cookies or cache metadata.",
    "Client may reuse or close the connection.",
]

for number, event in enumerate(lifecycle, start=1):
    print(f"{number:2}. {event}")


# =============================================================================
# 19. CONNECTION REUSE
# =============================================================================

section("19. PERSISTENT CONNECTIONS")

print(
    """
HTTP/1.0 commonly used short-lived connections unless persistence was
explicitly requested.

HTTP/1.1 made persistent connections the normal behavior.

Connection reuse avoids repeatedly establishing a transport connection.

Conceptually:

    Without reuse:

        Request -> connect -> response -> close
        Request -> connect -> response -> close

    With reuse:

        connect
        Request -> response
        Request -> response
        Request -> response
        close

Connection reuse can reduce latency and connection setup overhead.

Modern HTTP/2 and HTTP/3 provide additional multiplexing capabilities that
change how multiple requests and responses share a connection.
"""
)


# =============================================================================
# 20. HTTP/1.1, HTTP/2, HTTP/3
# =============================================================================

section("20. HTTP VERSION EVOLUTION")

versions = {
    "HTTP/1.0": "Simple request/response protocol; persistent connections were not the default.",
    "HTTP/1.1": "Persistent connections, chunked transfer, Host header, richer caching semantics.",
    "HTTP/2": "Binary framing, multiplexed streams, header compression, stream prioritization concepts.",
    "HTTP/3": "HTTP semantics over QUIC, which uses UDP and provides stream-oriented transport features.",
}

for version, description in versions.items():
    print(f"{version}: {description}")

print(
    """
The fundamental HTTP semantics remain recognizable across versions:

    methods
    status codes
    headers
    representations
    request/response semantics

The wire format and transport behavior differ.

HTTP/1.x:
    Text-oriented message syntax.

HTTP/2:
    Binary framing and multiplexed streams.

HTTP/3:
    Uses QUIC rather than TCP and therefore changes transport behavior.

An application developer should distinguish HTTP semantics from the details of
the protocol version used on the wire.
"""
)


# =============================================================================
# 21. CHUNKED TRANSFER ENCODING
# =============================================================================

section("21. CHUNKED TRANSFER ENCODING")

chunked_message = (
    "4\r\n"
    "Wiki\r\n"
    "5\r\n"
    "pedia\r\n"
    "0\r\n"
    "\r\n"
)

print(chunked_message)

print(
    """
Chunked transfer encoding is an HTTP/1.1 transfer mechanism.

The sender transmits:

    chunk size in hexadecimal
    CRLF
    chunk data
    CRLF

and ends the sequence with a zero-length chunk.

Chunked transfer encoding is different from content encoding.

Transfer encoding:
    Describes how the message is transferred.

Content encoding:
    Describes transformations applied to the representation, such as gzip.

HTTP/2 and HTTP/3 do not use HTTP/1.1 chunked transfer encoding in the same
way because their framing layers handle message boundaries differently.
"""
)


def decode_chunked_body(data: bytes) -> bytes:
    """Decode a simple chunked HTTP/1.1 body without chunk extensions."""
    stream = BytesIO(data)
    result = bytearray()

    while True:
        line = stream.readline()
        if not line:
            raise ValueError("Unexpected end of chunked data")

        line = line.rstrip(b"\r\n")
        size = int(line.split(b";", 1)[0], 16)

        if size == 0:
            while True:
                trailer = stream.readline()
                if trailer in (b"\r\n", b"\n", b""):
                    return bytes(result)

        chunk = stream.read(size)

        if len(chunk) != size:
            raise ValueError("Incomplete chunk")

        result.extend(chunk)

        terminator = stream.read(2)
        if terminator != b"\r\n":
            raise ValueError("Invalid chunk terminator")


decoded_chunked = decode_chunked_body(chunked_message.encode())
print("Decoded chunked body:", decoded_chunked.decode())


# =============================================================================
# 22. CONTENT-LENGTH
# =============================================================================

section("22. CONTENT-LENGTH")

body = b"Hello HTTP"
headers = {
    "Content-Type": "text/plain",
    "Content-Length": str(len(body)),
}

print("Body:", body)
print("Content-Length:", headers["Content-Length"])

print(
    """
Content-Length represents a byte count, not a character count.

This distinction matters for Unicode.

For example, the string:

    "é"

may occupy more than one byte when encoded as UTF-8.

Therefore:

    len("é")

and:

    len("é".encode("utf-8"))

can produce different values.
"""
)

unicode_text = "é"
print("Character count:", len(unicode_text))
print("UTF-8 byte count:", len(unicode_text.encode("utf-8")))


# =============================================================================
# 23. CONTENT ENCODING
# =============================================================================

section("23. CONTENT ENCODING")

original_text = "HTTP compression can reduce the number of transmitted bytes. " * 10
original_bytes = original_text.encode("utf-8")
compressed_bytes = gzip.compress(original_bytes)

print("Original bytes:", len(original_bytes))
print("Compressed bytes:", len(compressed_bytes))
print("Compression ratio:", round(len(compressed_bytes) / len(original_bytes), 3))

print(
    """
If a server sends compressed content, it can use:

    Content-Encoding: gzip

The client may advertise support with:

    Accept-Encoding: gzip

Content-Encoding is not the same as Content-Type.

Example:

    Content-Type: application/json
    Content-Encoding: gzip

This means the representation is JSON and the transferred representation has
gzip content coding.
"""
)


# =============================================================================
# 24. COOKIES
# =============================================================================

section("24. COOKIES")

cookie = SimpleCookie()
cookie["session_id"] = "abc123"
cookie["session_id"]["Path"] = "/"
cookie["session_id"]["HttpOnly"] = True
cookie["session_id"]["Secure"] = True
cookie["session_id"]["SameSite"] = "Lax"

print("Set-Cookie representation:")
print(cookie.output())

client_cookie = SimpleCookie()
client_cookie.load("session_id=abc123; theme=dark")

for key, morsel in client_cookie.items():
    print(f"Cookie: {key}={morsel.value}")

print(
    """
Cookies provide client-side state associated with HTTP interactions.

The server can send:

    Set-Cookie: session_id=abc123; Path=/; HttpOnly; Secure

The client later sends:

    Cookie: session_id=abc123

Important cookie attributes include:

    Secure
        Cookie should only be sent over secure connections.

    HttpOnly
        Prevents ordinary client-side scripts from reading the cookie.

    SameSite
        Controls cross-site sending behavior.

    Domain
        Controls which hosts can receive the cookie.

    Path
        Restricts applicable request paths.

    Max-Age / Expires
        Controls lifetime.

A cookie is not automatically secure merely because it exists.
"""
)


# =============================================================================
# 25. CACHING
# =============================================================================

section("25. HTTP CACHING")

print(
    """
Caching allows clients and intermediaries to reuse stored representations.

Important concepts include:

    Cache-Control
    ETag
    Last-Modified
    Expires
    If-None-Match
    If-Modified-Since

Example response:

    Cache-Control: max-age=60
    ETag: "abc123"

A later request can contain:

    If-None-Match: "abc123"

If the representation has not changed, the server can return:

    304 Not Modified

The client can then use its stored representation.

Caching reduces latency, server load, and bandwidth consumption, but incorrect
cache directives can cause stale or sensitive information to be exposed.
"""
)

cache_headers = {
    "Cache-Control": "public, max-age=60",
    "ETag": '"v42"',
}

conditional_request = {
    "If-None-Match": cache_headers["ETag"],
}

print("Cache headers:", cache_headers)
print("Conditional request:", conditional_request)


# =============================================================================
# 26. ETAG GENERATION
# =============================================================================

section("26. ETAG GENERATION")

representation = b'{"id":42,"name":"Alice"}'
etag_value = hashlib.sha256(representation).hexdigest()

print("Representation:", representation)
print("Generated hash:", etag_value)
print("Example ETag:", f'"{etag_value}"')

print(
    """
An ETag identifies a selected representation version.

Strong and weak validators have different semantics.

A strong validator can be used when byte-level equivalence is appropriate.

A weak validator has the form:

    W/"value"

Weak validation indicates that semantic equivalence may be sufficient even
when representations are not byte-for-byte identical.
"""
)


# =============================================================================
# 27. CONDITIONAL REQUEST SIMULATION
# =============================================================================

section("27. CONDITIONAL REQUEST SIMULATION")

server_etag = '"resource-version-5"'
client_etag = '"resource-version-5"'

if client_etag == server_etag:
    conditional_status = HTTPStatus.NOT_MODIFIED
else:
    conditional_status = HTTPStatus.OK

print("Client ETag:", client_etag)
print("Server ETag:", server_etag)
print("Result:", conditional_status.value, conditional_status.phrase)


# =============================================================================
# 28. REDIRECTS
# =============================================================================

section("28. REDIRECTS")

redirects = {
    301: "Permanent redirect",
    302: "Temporary redirect",
    303: "See another resource",
    307: "Temporary redirect preserving method semantics",
    308: "Permanent redirect preserving method semantics",
}

for code, meaning in redirects.items():
    print(code, "->", meaning)

print(
    """
Redirect responses commonly contain a Location header.

Example:

    HTTP/1.1 302 Found
    Location: /login

The client can then make another request to the indicated location.

307 and 308 are especially important when preserving the original method and
request body semantics matters.

Redirect handling is partly a client behavior and should not be confused with
the server merely returning a resource.
"""
)


# =============================================================================
# 29. AUTHENTICATION VS AUTHORIZATION
# =============================================================================

section("29. AUTHENTICATION VS AUTHORIZATION")

print(
    """
Authentication asks:

    Who are you?

Authorization asks:

    Are you allowed to perform this action?

HTTP commonly carries authentication information in the Authorization header.

Example conceptual form:

    Authorization: Bearer <token>

Basic authentication has the form:

    Authorization: Basic <base64-credentials>

Base64 is encoding, not encryption.

HTTPS should be used to protect credentials in transit.

A server should validate credentials and then apply authorization rules
independently.
"""
)


# =============================================================================
# 30. AUTHENTICATION HEADER PARSING
# =============================================================================

section("30. AUTHORIZATION HEADER PARSING")

def parse_authorization_header(value: str) -> Tuple[str, str]:
    """
    Split an Authorization header into scheme and credentials.

    This does not authenticate anyone. It only parses the syntax.
    """
    parts = value.split(" ", 1)

    if len(parts) != 2:
        raise ValueError("Invalid Authorization header")

    scheme, credentials = parts
    return scheme, credentials


authorization_value = "Bearer example-token"
scheme, credentials = parse_authorization_header(authorization_value)

print("Scheme:", scheme)
print("Credentials:", credentials)


# =============================================================================
# 31. HEAD
# =============================================================================

section("31. HEAD METHOD")

print(
    """
HEAD has the same request semantics as GET except that the server must not
send content in the response body.

HEAD is useful for obtaining metadata such as:

    Content-Length
    Content-Type
    Last-Modified
    ETag

It can help determine whether a resource exists or inspect representation
metadata without transferring the representation itself.

A server must take care that the headers associated with HEAD remain
consistent with what a corresponding GET would produce.
"""
)


# =============================================================================
# 32. OPTIONS
# =============================================================================

section("32. OPTIONS METHOD")

print(
    """
OPTIONS asks about communication options for a target resource or server.

A response can include an Allow header:

    Allow: GET, POST, OPTIONS

OPTIONS is also relevant to CORS preflight requests in browsers.

CORS is a browser security mechanism. It is not itself a replacement for
authentication or authorization.
"""
)

allow_header = "GET, POST, OPTIONS"
allowed_methods = [method.strip() for method in allow_header.split(",")]
print("Allowed methods:", allowed_methods)


# =============================================================================
# 33. CORS CONCEPTS
# =============================================================================

section("33. CORS CONCEPTS")

print(
    """
Cross-Origin Resource Sharing, or CORS, controls whether browser scripts from
one origin may access resources from another origin.

An origin consists conceptually of:

    scheme + host + port

Example:

    https://app.example.com

is a different origin from:

    https://api.example.com

A server can respond with headers such as:

    Access-Control-Allow-Origin
    Access-Control-Allow-Methods
    Access-Control-Allow-Headers
    Access-Control-Allow-Credentials

A browser may send an OPTIONS preflight request before certain cross-origin
requests.

CORS is primarily enforced by browsers. A command-line HTTP client is not
automatically subject to the same browser enforcement model.
"""
)


# =============================================================================
# 34. HTTP ERROR HANDLING
# =============================================================================

section("34. HTTP ERROR HANDLING")

def classify_status(status_code: int) -> str:
    """Classify a status code by its numeric class."""
    if 100 <= status_code <= 199:
        return "informational"
    if 200 <= status_code <= 299:
        return "success"
    if 300 <= status_code <= 399:
        return "redirection"
    if 400 <= status_code <= 499:
        return "client error"
    if 500 <= status_code <= 599:
        return "server error"
    return "invalid"


for code in [100, 200, 301, 404, 500, 999]:
    print(code, "=>", classify_status(code))

print(
    """
A robust HTTP client should distinguish:

    Network failure
        DNS failure, connection refusal, timeout, TLS failure.

    HTTP failure
        The server returned a valid HTTP response with a 4xx or 5xx status.

These are not the same.

For example, HTTP 404 means the server responded successfully at the
protocol level and explicitly reported that the target was not found.

A connection timeout means an HTTP response may never have been received.
"""
)


# =============================================================================
# 35. TIMEOUTS
# =============================================================================

section("35. TIMEOUTS")

print(
    """
A production HTTP client should avoid waiting forever.

Common timeout concepts include:

    Connection timeout
        Time allowed to establish a connection.

    Read timeout
        Time allowed while waiting for response data.

    Write timeout
        Time allowed while transmitting data.

    Total/request timeout
        Maximum permitted operation duration.

Timeouts are essential because remote systems can fail silently, become
overloaded, or become unreachable.
"""
)


# =============================================================================
# 36. RETRIES
# =============================================================================

section("36. RETRIES AND IDEMPOTENCY")

print(
    """
Retries can improve reliability when failures are transient.

But retries can duplicate operations.

Consider:

    POST /payments

If the server successfully processes the payment but the network fails before
the client receives the response, retrying blindly can create a duplicate
payment.

Idempotency is therefore important for retry design.

An API can also support an explicit idempotency key, allowing the server to
recognize repeated attempts at the same logical operation.

Retry policies should consider:

    method semantics
    status code
    network error type
    server overload
    request body replayability
    timeout
    backoff
    idempotency
"""
)


# =============================================================================
# 37. EXPONENTIAL BACKOFF
# =============================================================================

section("37. EXPONENTIAL BACKOFF")

def exponential_backoff(
    attempt: int,
    base_delay: float = 0.5,
    maximum_delay: float = 30.0,
) -> float:
    """Calculate a capped exponential backoff delay."""
    return min(maximum_delay, base_delay * (2 ** attempt))


for attempt in range(6):
    print(f"Attempt {attempt}: delay={exponential_backoff(attempt):.2f}s")

print(
    """
Exponential backoff increases the delay between repeated attempts.

A production implementation commonly adds jitter so that many clients do not
retry simultaneously after the same outage.

Retries should not be used as a substitute for fixing deterministic client
errors such as malformed requests or invalid authentication.
"""
)


# =============================================================================
# 38. PROXY AND GATEWAY
# =============================================================================

section("38. PROXIES, GATEWAYS, AND REVERSE PROXIES")

print(
    """
An intermediary can sit between a client and origin server.

Forward proxy:

    Client -> Proxy -> Internet

Reverse proxy:

    Client -> Reverse Proxy -> Application Servers

Intermediaries can provide:

    routing
    TLS termination
    caching
    compression
    load balancing
    access control
    rate limiting
    observability
    request filtering

Headers such as Via and Forwarded can communicate intermediary information.

An application should not blindly trust client-supplied forwarding headers
unless the network architecture explicitly establishes which intermediaries
are trusted.
"""
)


# =============================================================================
# 39. HTTP HOST HEADER
# =============================================================================

section("39. HOST HEADER AND VIRTUAL HOSTING")

host_header = "api.example.com"
print("Host:", host_header)

print(
    """
One server IP address can serve multiple domain names.

The Host field in HTTP/1.1 identifies the target authority.

For HTTPS, TLS also has the Server Name Indication extension, commonly known
as SNI, which allows the server to select an appropriate certificate during
TLS negotiation.

HTTP routing and TLS certificate selection are related but distinct layers.
"""
)


# =============================================================================
# 40. HTTPS
# =============================================================================

section("40. HTTPS")

print(
    """
HTTPS means HTTP carried over TLS.

TLS provides important security properties:

    Confidentiality
        Observers should not be able to read protected traffic.

    Integrity
        Traffic modification should be detectable.

    Server authentication
        Certificates help the client authenticate the server identity.

HTTPS does not automatically make an application secure.

Application vulnerabilities can still exist:

    injection
    broken authorization
    insecure session handling
    sensitive-data exposure
    request forgery
    logic flaws
    unsafe redirects

TLS protects the communication channel; it does not replace secure
application design.
"""
)


# =============================================================================
# 41. SSL CONTEXT INSPECTION
# =============================================================================

section("41. PYTHON TLS CONTEXT")

context = ssl.create_default_context()

print("TLS context created:", isinstance(context, ssl.SSLContext))
print("Default verification mode:", context.verify_mode)
print("Hostname checking:", context.check_hostname)

print(
    """
Python's create_default_context creates a context configured for secure
certificate verification appropriate for normal client use.

Disabling certificate verification can make HTTPS vulnerable to man-in-the-
middle attacks and should not be used casually in production code.
"""
)


# =============================================================================
# 42. HTTP REQUEST CONSTRUCTION
# =============================================================================

section("42. BUILDING AN HTTP REQUEST")

def build_http_request(
    method: str,
    target: str,
    headers: Mapping[str, str],
    body: bytes = b"",
) -> bytes:
    """Construct a simple HTTP/1.1 request message."""
    normalized_headers = dict(headers)

    if body and "Content-Length" not in normalized_headers:
        normalized_headers["Content-Length"] = str(len(body))

    lines = [f"{method} {target} HTTP/1.1"]

    for name, value in normalized_headers.items():
        lines.append(f"{name}: {value}")

    lines.append("")
    header_bytes = "\r\n".join(lines).encode("iso-8859-1") + b"\r\n"

    return header_bytes + body


request = build_http_request(
    "POST",
    "/users",
    {
        "Host": "example.com",
        "Content-Type": "application/json",
    },
    b'{"name":"Alice"}',
)

print(request.decode("iso-8859-1"))


# =============================================================================
# 43. SIMPLE HTTP REQUEST PARSER
# =============================================================================

section("43. PARSING A SIMPLE HTTP REQUEST")

@dataclass
class ParsedHTTPRequest:
    method: str
    target: str
    version: str
    headers: Dict[str, str]
    body: bytes = b""


def parse_simple_http_request(raw: bytes) -> ParsedHTTPRequest:
    """
    Parse a basic HTTP/1.x request.

    This educational parser intentionally does not implement every feature of
    the HTTP specification. Production servers should use hardened HTTP
    libraries rather than a parser like this.
    """
    separator = b"\r\n\r\n"

    if separator not in raw:
        raise ValueError("HTTP request is missing the header/body separator")

    header_section, body = raw.split(separator, 1)
    lines = header_section.split(b"\r\n")

    if not lines:
        raise ValueError("Missing request line")

    request_line = lines[0].decode("iso-8859-1")
    parts = request_line.split(" ")

    if len(parts) != 3:
        raise ValueError("Malformed request line")

    method, target, version = parts
    headers: Dict[str, str] = {}

    for line in lines[1:]:
        decoded = line.decode("iso-8859-1")

        if ":" not in decoded:
            raise ValueError("Malformed header")

        name, value = decoded.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return ParsedHTTPRequest(
        method=method,
        target=target,
        version=version,
        headers=headers,
        body=body,
    )


parsed_request = parse_simple_http_request(request)

print("Method:", parsed_request.method)
print("Target:", parsed_request.target)
print("Version:", parsed_request.version)
print("Headers:", parsed_request.headers)
print("Body:", parsed_request.body)


# =============================================================================
# 44. HEADER CASE INSENSITIVITY
# =============================================================================

section("44. HEADER FIELD NAMES ARE CASE-INSENSITIVE")

header_examples = {
    "Content-Type": "application/json",
    "content-type": "application/json",
    "CONTENT-TYPE": "application/json",
}

for name in header_examples:
    print(name, "normalizes to:", name.lower())

print(
    """
These field names represent the same HTTP header field:

    Content-Type
    content-type
    CONTENT-TYPE

Applications should compare header names case-insensitively.

Header values can have their own syntax and case rules, so it is incorrect to
blindly lowercase every header value.
"""
)


# =============================================================================
# 45. REQUEST BODY VALIDATION
# =============================================================================

section("45. REQUEST VALIDATION")

def parse_json_request_body(
    body: bytes,
    content_type: str,
) -> object:
    """Validate media type and decode a JSON request body."""
    media_type = content_type.split(";", 1)[0].strip().lower()

    if media_type != "application/json":
        raise ValueError("Expected application/json")

    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 JSON body") from exc


valid_body = b'{"name":"Alice","age":30}'
print(parse_json_request_body(valid_body, "application/json; charset=utf-8"))

try:
    parse_json_request_body(b"not-json", "application/json")
except ValueError as exc:
    print("Validation error:", exc)


# =============================================================================
# 46. CONTENT-LENGTH VALIDATION
# =============================================================================

section("46. CONTENT-LENGTH VALIDATION")

def validate_content_length(headers: Mapping[str, str], body: bytes) -> None:
    """Validate Content-Length when supplied."""
    content_length = headers.get("Content-Length")

    if content_length is None:
        return

    try:
        declared_length = int(content_length)
    except ValueError as exc:
        raise ValueError("Content-Length must be an integer") from exc

    if declared_length < 0:
        raise ValueError("Content-Length cannot be negative")

    if declared_length != len(body):
        raise ValueError(
            f"Content-Length says {declared_length} bytes, "
            f"but received {len(body)} bytes"
        )


validate_content_length(
    {"Content-Length": str(len(request_body))},
    request_body,
)

print("Content-Length validation passed.")


# =============================================================================
# 47. HTTP DATE
# =============================================================================

section("47. HTTP DATE")

now = datetime.now(timezone.utc)
http_date = format_datetime(now, usegmt=True)

print("Generated HTTP date:", http_date)

parsed_date = parsedate_to_datetime(http_date)
print("Parsed date:", parsed_date)

print(
    """
HTTP dates are commonly represented using the IMF-fixdate form, for example:

    Sun, 06 Nov 1994 08:49:37 GMT

Dates are used in headers such as:

    Date
    Expires
    Last-Modified
    If-Modified-Since

Time handling must be timezone-aware when comparing HTTP timestamps.
"""
)


# =============================================================================
# 48. RANGE REQUESTS
# =============================================================================

section("48. RANGE REQUESTS")

range_header = "bytes=0-99"
print("Range:", range_header)

print(
    """
Range requests allow a client to request part of a representation.

Example:

    Range: bytes=0-99

A server that supports the range can return:

    206 Partial Content

and may include:

    Content-Range: bytes 0-99/1000

Range requests are useful for large files, media streaming, and resumable
downloads.
"""
)


# =============================================================================
# 49. FORM ENCODING
# =============================================================================

section("49. APPLICATION/X-WWW-FORM-URLENCODED")

form_data = {
    "username": "alice",
    "topic": "HTTP fundamentals",
    "page": "1",
}

encoded_form = urlencode(form_data)

print("Encoded form:", encoded_form)
print("Decoded form:", parse_qs(encoded_form))

print(
    """
application/x-www-form-urlencoded encodes key-value pairs into a URL-style
representation.

It is frequently used by traditional HTML forms.

It differs from multipart/form-data, which is useful when form submissions
include files or multiple parts with separate metadata.
"""
)


# =============================================================================
# 50. MULTIPART CONCEPT
# =============================================================================

section("50. MULTIPART/FORM-DATA CONCEPT")

boundary = "----PythonHTTPStudyBoundary"
multipart_body = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="username"\r\n'
    "\r\n"
    "alice\r\n"
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="description"\r\n'
    "\r\n"
    "HTTP study file\r\n"
    f"--{boundary}--\r\n"
)

print(multipart_body)

print(
    """
multipart/form-data divides one request body into multiple parts.

A Content-Type might look like:

    multipart/form-data; boundary=...

Each part can contain its own headers and content.

Multipart is useful for forms containing:

    text fields
    files
    binary data
"""
)


# =============================================================================
# 51. HTTP SERVER WITH STANDARD LIBRARY
# =============================================================================

section("51. BUILDING A SMALL HTTP SERVER")

class DemoHTTPHandler(BaseHTTPRequestHandler):
    """Small educational HTTP server handler."""

    server_version = "HTTPStudyServer/1.0"

    def _send_json(
        self,
        status: HTTPStatus,
        payload: object,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Send a JSON response."""
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")

        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)

        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_json(
                HTTPStatus.OK,
                {
                    "message": "HTTP server is running",
                    "method": self.command,
                    "path": parsed.path,
                },
            )
            return

        if parsed.path == "/hello":
            query = parse_qs(parsed.query)
            name = query.get("name", ["World"])[0]

            self._send_json(
                HTTPStatus.OK,
                {
                    "message": f"Hello, {name}",
                    "query": query,
                },
            )
            return

        if parsed.path == "/redirect":
            self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
            self.send_header("Location", "/hello?name=Redirected")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "Resource not found",
                "path": parsed.path,
            },
        )

    def do_POST(self) -> None:
        """Handle a JSON POST request."""
        content_type = self.headers.get("Content-Type", "")
        content_length = self.headers.get("Content-Length")

        if not content_length:
            self._send_json(
                HTTPStatus.LENGTH_REQUIRED,
                {"error": "Content-Length is required"},
            )
            return

        try:
            length = int(content_length)
        except ValueError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid Content-Length"},
            )
            return

        if length > 1_000_000:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "Request body is too large"},
            )
            return

        body = self.rfile.read(length)

        try:
            payload = parse_json_request_body(body, content_type)
        except ValueError as exc:
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": str(exc)},
            )
            return

        self._send_json(
            HTTPStatus.CREATED,
            {
                "message": "Resource accepted",
                "received": payload,
            },
        )

    def do_OPTIONS(self) -> None:
        """Handle an OPTIONS request."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format_string: str, *args: object) -> None:
        """Use a compact educational access-log format."""
        print(f"[HTTP SERVER] {self.address_string()} - {format_string % args}")


print(
    """
The DemoHTTPHandler can be used with ThreadingHTTPServer.

The server is not started automatically yet. A helper below starts it on an
ephemeral local port and demonstrates requests against it.
"""
)


# =============================================================================
# 52. RUNNING THE LOCAL SERVER
# =============================================================================

section("52. RUNNING THE LOCAL SERVER")

server_holder: Dict[str, ThreadingHTTPServer] = {}


def start_demo_server() -> Tuple[ThreadingHTTPServer, threading.Thread]:
    """Start the educational HTTP server on localhost using an ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHTTPHandler)

    thread = threading.Thread(
        target=server.serve_forever,
        name="demo-http-server",
        daemon=True,
    )

    thread.start()

    server_holder["server"] = server

    return server, thread


demo_server, demo_thread = start_demo_server()

host, port = demo_server.server_address

print("Server host:", host)
print("Server port:", port)
print("Server thread alive:", demo_thread.is_alive())


# =============================================================================
# 53. HTTP CLIENT WITH HTTPCLIENT
# =============================================================================

section("53. PYTHON HTTP CLIENT")

connection = HTTPConnection(host, port, timeout=5)

try:
    connection.request(
        "GET",
        "/hello?name=Python",
        headers={
            "Accept": "application/json",
            "User-Agent": "HTTPStudyClient/1.0",
        },
    )

    response = connection.getresponse()
    body = response.read()

    print("Status:", response.status)
    print("Reason:", response.reason)
    print("Headers:")

    for name, value in response.getheaders():
        print(f"  {name}: {value}")

    print("Body:", body.decode("utf-8"))

finally:
    connection.close()


# =============================================================================
# 54. POST REQUEST TO LOCAL SERVER
# =============================================================================

section("54. POST REQUEST")

payload = {
    "name": "Alice",
    "skills": ["Python", "HTTP"],
}

payload_bytes = json.dumps(payload).encode("utf-8")

connection = HTTPConnection(host, port, timeout=5)

try:
    connection.request(
        "POST",
        "/users",
        body=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    response = connection.getresponse()
    response_body = response.read()

    print("Status:", response.status)
    print("Response:", response_body.decode("utf-8"))

finally:
    connection.close()


# =============================================================================
# 55. HEAD AND OPTIONS
# =============================================================================

section("55. HEAD AND OPTIONS")

connection = HTTPConnection(host, port, timeout=5)

try:
    connection.request("OPTIONS", "/")
    response = connection.getresponse()

    print("OPTIONS status:", response.status)
    print("Allow:", response.getheader("Allow"))
    response.read()

finally:
    connection.close()


# =============================================================================
# 56. QUERY STRING BEHAVIOR
# =============================================================================

section("56. QUERY STRING BEHAVIOR")

connection = HTTPConnection(host, port, timeout=5)

try:
    connection.request("GET", "/hello?name=HTTP%20Student")
    response = connection.getresponse()

    print("Status:", response.status)
    print("Body:", response.read().decode("utf-8"))

finally:
    connection.close()


# =============================================================================
# 57. NOT FOUND
# =============================================================================

section("57. 404 RESPONSE")

connection = HTTPConnection(host, port, timeout=5)

try:
    connection.request("GET", "/does-not-exist")
    response = connection.getresponse()

    print("Status:", response.status)
    print("Reason:", response.reason)
    print("Body:", response.read().decode("utf-8"))

finally:
    connection.close()


# =============================================================================
# 58. REDIRECT RESPONSE
# =============================================================================

section("58. REDIRECT RESPONSE")

connection = HTTPConnection(host, port, timeout=5)

try:
    connection.request("GET", "/redirect")
    response = connection.getresponse()

    print("Status:", response.status)
    print("Location:", response.getheader("Location"))
    print("Body length:", len(response.read()))

finally:
    connection.close()


# =============================================================================
# 59. HTTPERROR AND URLLIB
# =============================================================================

section("59. URLLIB REQUEST HANDLING")

request = Request(
    f"http://{host}:{port}/hello?name=urllib",
    headers={
        "Accept": "application/json",
        "User-Agent": "urllib-study-client/1.0",
    },
)

try:
    with build_opener().open(request, timeout=5) as response:
        print("URL:", response.geturl())
        print("Status:", response.status)
        print("Content-Type:", response.headers.get("Content-Type"))
        print("Body:", response.read().decode("utf-8"))
except HTTPError as exc:
    print("HTTP error:", exc.code, exc.reason)
except URLError as exc:
    print("URL/network error:", exc.reason)


# =============================================================================
# 60. NETWORK ERRORS VS HTTP ERRORS
# =============================================================================

section("60. NETWORK ERRORS VS HTTP ERRORS")

def explain_error(error: Exception) -> str:
    """Classify common urllib/network exceptions."""
    if isinstance(error, HTTPError):
        return f"HTTP-level error: {error.code}"
    if isinstance(error, URLError):
        return f"Network/URL-level error: {error.reason}"
    return f"Unexpected error: {type(error).__name__}"


try:
    bad_request = Request(f"http://{host}:{port}/missing")
    with build_opener().open(bad_request, timeout=5) as response:
        response.read()
except Exception as exc:
    print(explain_error(exc))


# =============================================================================
# 61. THREADING AND CONCURRENCY
# =============================================================================

section("61. CONCURRENT REQUESTS")

print(
    """
Modern web servers commonly handle many requests concurrently.

Concurrency can be implemented using:

    threads
    processes
    asynchronous event loops
    worker pools
    operating-system primitives
    distributed services

HTTP itself does not dictate the server's internal concurrency architecture.

ThreadingHTTPServer is used here only to demonstrate that independent
connections can be served concurrently.
"""
)


# =============================================================================
# 62. SERVER SHUTDOWN
# =============================================================================

section("62. SERVER SHUTDOWN")

demo_server.shutdown()
demo_server.server_close()

print("Demo server stopped.")
print("Server thread alive after shutdown:", demo_thread.is_alive())


# =============================================================================
# 63. HTTP CONNECTION REUSE WITH HTTPConnection
# =============================================================================

section("63. CONNECTION REUSE DEMONSTRATION")

reuse_server, reuse_thread = start_demo_server()
reuse_host, reuse_port = reuse_server.server_address

connection = HTTPConnection(reuse_host, reuse_port, timeout=5)

try:
    for path in ["/hello?name=One", "/hello?name=Two", "/"]:
        connection.request("GET", path)
        response = connection.getresponse()

        print(
            path,
            "=>",
            response.status,
            response.reason,
            response.read().decode("utf-8"),
        )
finally:
    connection.close()
    reuse_server.shutdown()
    reuse_server.server_close()


# =============================================================================
# 64. HTTPS CONNECTION EXAMPLE
# =============================================================================

section("64. HTTPS CONNECTION API")

print(
    """
Python's http.client also provides HTTPSConnection.

The following construction demonstrates the API without contacting an
external service:

    HTTPSConnection("example.com", 443, context=ssl.create_default_context())

A real HTTPS request requires network access and should use proper certificate
verification.
"""
)

secure_context = ssl.create_default_context()
https_connection = HTTPSConnection(
    "example.com",
    443,
    timeout=5,
    context=secure_context,
)

print("HTTPS connection object created:", type(https_connection).__name__)
https_connection.close()


# =============================================================================
# 65. REQUEST HEADER VALIDATION
# =============================================================================

section("65. BASIC HEADER VALIDATION")

def validate_header_name(name: str) -> None:
    """
    Reject obviously invalid header names.

    This is intentionally educational and is not a full RFC parser.
    """
    if not name:
        raise ValueError("Header name cannot be empty")

    if any(char.isspace() for char in name):
        raise ValueError("Header name cannot contain whitespace")

    if ":" in name:
        raise ValueError("Header name cannot contain ':'")


def validate_header_value(value: str) -> None:
    """Reject raw CRLF in a header value."""
    if "\r" in value or "\n" in value:
        raise ValueError("Header value cannot contain CRLF")


for name, value in [
    ("Content-Type", "application/json"),
    ("X-Request-ID", "abc-123"),
]:
    validate_header_name(name)
    validate_header_value(value)
    print("Valid:", name, value)


# =============================================================================
# 66. HTTP HEADER INJECTION
# =============================================================================

section("66. HEADER INJECTION SECURITY")

print(
    """
A dangerous pattern is constructing HTTP headers directly from untrusted
input without validation.

For example, accepting a user-provided value containing CRLF can allow an
attacker to inject additional header lines in systems that do not sanitize
the value.

Safe applications should:

    validate header names
    reject CR and LF in header values
    use mature HTTP libraries
    avoid manual HTTP message construction in production code
"""
)


# =============================================================================
# 67. PATH NORMALIZATION
# =============================================================================

section("67. URL PATH AND PERCENT ENCODING")

raw_path = "/files/hello%20world.txt"
decoded_path = unquote(raw_path)

print("Raw path:", raw_path)
print("Decoded path:", decoded_path)

print(
    """
Percent encoding allows characters that cannot be represented directly in
certain URI contexts.

The server must be careful about decoding and path normalization.

Security-sensitive path handling should account for:

    percent encoding
    dot segments
    repeated separators
    Unicode normalization
    filesystem-specific behavior
    access-control boundaries

A URL path should not automatically be treated as a safe filesystem path.
"""
)


# =============================================================================
# 68. SAFE AND UNSAFE URL JOINING
# =============================================================================

section("68. URL CONSTRUCTION")

base_url = "https://example.com/api/"
relative_path = "users/42"

joined_url = urlunparse(
    (
        "https",
        "example.com",
        "/api/users/42",
        "",
        "",
        "",
    )
)

print("Base URL:", base_url)
print("Relative path:", relative_path)
print("Constructed URL:", joined_url)

print(
    """
When constructing URLs, components should be encoded according to their role.

Path segments, query parameters, usernames, fragments, and entire URLs do not
share identical encoding rules.

Using dedicated URL parsing and encoding utilities is safer than manually
concatenating arbitrary strings.
"""
)


# =============================================================================
# 69. JSON API RESPONSE DESIGN
# =============================================================================

section("69. JSON API RESPONSE DESIGN")

api_success = {
    "data": {
        "id": 42,
        "name": "Alice",
    },
}

api_error = {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "The supplied name is invalid.",
        "details": {
            "field": "name",
        },
    }
}

print("Success response:")
print(json.dumps(api_success, indent=2))

print("Error response:")
print(json.dumps(api_error, indent=2))

print(
    """
HTTP status codes and response bodies serve different purposes.

The status code communicates broad protocol-level outcome.

The body can communicate application-specific information.

For example:

    400
    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "..."
        }
    }

A well-designed API should make status and body semantics consistent.
"""
)


# =============================================================================
# 70. HTTP METHOD ROUTING
# =============================================================================

section("70. METHOD-BASED ROUTING")

def route_request(method: str, path: str) -> str:
    """Illustrate basic HTTP method and path routing."""
    routes = {
        ("GET", "/users"): "List users",
        ("POST", "/users"): "Create user",
        ("GET", "/users/42"): "Retrieve user 42",
        ("PUT", "/users/42"): "Replace user 42",
        ("PATCH", "/users/42"): "Modify user 42",
        ("DELETE", "/users/42"): "Delete user 42",
    }

    if (method, path) in routes:
        return routes[(method, path)]

    path_exists = any(route_path == path for _, route_path in routes)

    if path_exists:
        return "405 Method Not Allowed"

    return "404 Not Found"


for method, path in [
    ("GET", "/users"),
    ("POST", "/users"),
    ("PATCH", "/users/42"),
    ("DELETE", "/unknown"),
]:
    print(method, path, "=>", route_request(method, path))


# =============================================================================
# 71. 405 AND ALLOW
# =============================================================================

section("71. 405 METHOD NOT ALLOWED")

print(
    """
A 405 response means the method is known but not supported for the target
resource.

The response should include an Allow header identifying supported methods.

Example conceptual response:

    HTTP/1.1 405 Method Not Allowed
    Allow: GET, POST
"""
)


# =============================================================================
# 72. 401 AND WWW-AUTHENTICATE
# =============================================================================

section("72. 401 AND WWW-AUTHENTICATE")

print(
    """
A 401 response is associated with authentication requirements.

A server can indicate an authentication challenge with:

    WWW-Authenticate: Bearer

A 403 response has a different meaning: the server refuses the request even
though the authentication/authorization context does not justify performing
the operation.

Exact API conventions can vary, but clients should not assume 401 and 403
are interchangeable.
"""
)


# =============================================================================
# 73. RATE LIMITING
# =============================================================================

section("73. RATE LIMITING")

print(
    """
HTTP APIs commonly use 429 Too Many Requests when a client exceeds a defined
rate limit.

A server may provide:

    Retry-After

to indicate when another attempt may be appropriate.

Rate limiting protects:

    server capacity
    database resources
    downstream dependencies
    authentication systems
    expensive operations

A robust client should interpret rate-limit responses instead of immediately
retrying in a tight loop.
"""
)

retry_after_seconds = 10
print("Example Retry-After:", retry_after_seconds)


# =============================================================================
# 74. OBSERVABILITY
# =============================================================================

section("74. HTTP OBSERVABILITY")

request_log = {
    "method": "GET",
    "path": "/users/42",
    "status": 200,
    "duration_ms": 18,
    "user_agent": "ExampleClient/1.0",
    "request_id": "req-123",
}

print(json.dumps(request_log, indent=2))

print(
    """
Useful HTTP observability data can include:

    method
    route
    status
    duration
    response size
    request ID
    trace ID
    user agent
    selected upstream
    cache status

Sensitive values should not be logged indiscriminately.

Examples of data requiring care:

    Authorization headers
    session cookies
    passwords
    access tokens
    personal information
    payment information
"""
)


# =============================================================================
# 75. CORRELATION IDENTIFIERS
# =============================================================================

section("75. REQUEST IDENTIFIERS")

request_id = "req-20260904-0001"

request_headers = {
    "X-Request-ID": request_id,
}

print(request_headers)

print(
    """
A request identifier can help correlate logs across components.

A distributed request may pass through:

    client
    load balancer
    reverse proxy
    API gateway
    application
    database-facing service

A shared correlation identifier makes troubleshooting much easier.

Security-sensitive systems should carefully consider whether externally
supplied identifiers are trusted or should be generated/validated by trusted
infrastructure.
"""
)


# =============================================================================
# 76. HTTP CACHE SIMULATION
# =============================================================================

section("76. SIMPLE CACHE SIMULATION")

@dataclass
class CacheEntry:
    value: bytes
    stored_at: float
    max_age: int
    etag: str


class SimpleHTTPCache:
    """Tiny educational HTTP cache."""

    def __init__(self) -> None:
        self.entries: Dict[str, CacheEntry] = {}

    def store(
        self,
        url: str,
        value: bytes,
        max_age: int,
        etag: str,
    ) -> None:
        self.entries[url] = CacheEntry(
            value=value,
            stored_at=time.time(),
            max_age=max_age,
            etag=etag,
        )

    def get(self, url: str) -> Optional[CacheEntry]:
        entry = self.entries.get(url)

        if entry is None:
            return None

        if time.time() - entry.stored_at > entry.max_age:
            return None

        return entry


cache = SimpleHTTPCache()
cache_url = "https://example.com/data"

cache.store(
    cache_url,
    b'{"value":42}',
    max_age=60,
    etag='"version-1"',
)

cached = cache.get(cache_url)

if cached:
    print("Cache hit:", cached.value)
    print("ETag:", cached.etag)
else:
    print("Cache miss")


# =============================================================================
# 77. CACHE-CONTROL DIRECTIVES
# =============================================================================

section("77. CACHE-CONTROL DIRECTIVES")

cache_directives = [
    "max-age=60",
    "no-cache",
    "no-store",
    "private",
    "public",
    "must-revalidate",
]

for directive in cache_directives:
    print(directive)

print(
    """
Important distinctions:

no-store:
    Do not store the response.

no-cache:
    A stored response generally requires validation before reuse.

private:
    Intended for a private cache rather than shared caches.

public:
    May be stored by shared caches when other requirements permit.

max-age:
    Freshness lifetime in seconds.

Cache-Control is more precise than relying solely on intuition about whether
a URL "looks static".
"""
)


# =============================================================================
# 78. SECURITY: SENSITIVE DATA
# =============================================================================

section("78. HTTP SECURITY: SENSITIVE DATA")

print(
    """
Sensitive information should be protected throughout its lifecycle.

Examples include:

    credentials
    tokens
    session identifiers
    personal information
    secrets

Security measures include:

    HTTPS
    secure cookie attributes
    appropriate authorization
    careful logging
    correct cache directives
    input validation
    output encoding
    rate limiting
    short-lived credentials where appropriate

A response containing private information should not accidentally be made
publicly cacheable.
"""
)


# =============================================================================
# 79. SECURITY: REQUEST SMUGGLING CONCEPT
# =============================================================================

section("79. HTTP REQUEST SMUGGLING CONCEPT")

print(
    """
HTTP request smuggling vulnerabilities can arise when different components
parse request boundaries differently.

A classic risk involves disagreement about:

    Content-Length
    Transfer-Encoding

between intermediaries and origin servers.

Consequences can include:

    request desynchronization
    cache poisoning
    unauthorized request routing
    security-control bypasses

Production infrastructure should use well-tested HTTP implementations and
consistent parsing rules rather than handwritten protocol parsers.
"""
)


# =============================================================================
# 80. SECURITY: CRLF
# =============================================================================

section("80. CRLF AND MESSAGE BOUNDARIES")

print(
    """
HTTP/1.x uses CRLF as a protocol line delimiter.

A CRLF sequence is:

    \\r\\n

A blank line is:

    \\r\\n\\r\\n

Because these sequences delimit protocol structure, applications must not
allow untrusted input to be inserted into raw protocol lines without
validation.

This is relevant to:

    header injection
    response splitting
    request construction
"""
)


# =============================================================================
# 81. HTTP MESSAGE PARSING LIMITATIONS
# =============================================================================

section("81. LIMITATIONS OF HANDWRITTEN HTTP PARSERS")

print(
    """
The parser earlier in this script intentionally handles only a small subset
of HTTP/1.x.

A real parser must account for many details, including:

    complete message framing
    repeated fields
    field-value grammar
    transfer codings
    trailers
    connection semantics
    protocol versions
    malformed messages
    limits
    interoperability
    security edge cases

Therefore:

    Educational parser -> useful for understanding

    Production parser -> use a mature, maintained HTTP implementation
"""
)


# =============================================================================
# 82. EDGE CASE: EMPTY BODY
# =============================================================================

section("82. EMPTY BODY")

empty_body = b""

print("Empty body length:", len(empty_body))

print(
    """
An empty body is different from a body containing textual data such as:

    ""

The application should interpret body presence according to the HTTP method,
status code, headers, and media type rather than assuming that every response
contains content.
"""
)


# =============================================================================
# 83. EDGE CASE: LARGE BODY
# =============================================================================

section("83. LARGE REQUEST BODIES")

MAX_BODY_SIZE = 1_000_000

def validate_body_size(body: bytes, maximum: int = MAX_BODY_SIZE) -> None:
    """Reject bodies larger than an application-defined limit."""
    if len(body) > maximum:
        raise ValueError(
            f"Request body exceeds maximum size of {maximum} bytes"
        )


validate_body_size(b"small body")
print("Small body accepted.")


# =============================================================================
# 84. EDGE CASE: INVALID JSON
# =============================================================================

section("84. INVALID JSON")

invalid_json_samples = [
    b"",
    b"{",
    b"not-json",
    b'{"name":}',
]

for sample in invalid_json_samples:
    try:
        json.loads(sample.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(repr(sample), "=> invalid:", type(exc).__name__)


# =============================================================================
# 85. EDGE CASE: UNICODE
# =============================================================================

section("85. UNICODE AND BYTE LENGTH")

unicode_values = [
    "hello",
    "café",
    "भारत",
    "你好",
    "🙂",
]

for value in unicode_values:
    print(
        repr(value),
        "characters=",
        len(value),
        "UTF-8 bytes=",
        len(value.encode("utf-8")),
    )

print(
    """
HTTP payload lengths are fundamentally byte-oriented.

Character encoding determines how text becomes bytes.

UTF-8 is widely used for modern text representations, but HTTP does not
magically convert arbitrary bytes into characters. The representation's media
type and encoding metadata matter.
"""
)


# =============================================================================
# 86. EDGE CASE: QUERY PARAMETERS
# =============================================================================

section("86. QUERY PARAMETER EDGE CASES")

queries = [
    "",
    "a=1",
    "a=1&a=2",
    "flag",
    "name=Alice%20Smith",
]

for query in queries:
    print(query, "=>", parse_qs(query, keep_blank_values=True))


# =============================================================================
# 87. HTTP API DESIGN: RESOURCE ORIENTED EXAMPLE
# =============================================================================

section("87. RESOURCE-ORIENTED API EXAMPLE")

api_operations = [
    ("GET", "/users", "Retrieve users"),
    ("GET", "/users/42", "Retrieve user 42"),
    ("POST", "/users", "Create a user"),
    ("PUT", "/users/42", "Replace user 42"),
    ("PATCH", "/users/42", "Partially modify user 42"),
    ("DELETE", "/users/42", "Delete user 42"),
]

for method, path, meaning in api_operations:
    print(f"{method:6} {path:20} {meaning}")

print(
    """
HTTP methods communicate operation semantics.

A clean API generally avoids encoding every action as an arbitrary POST route
when a standard method expresses the operation appropriately.

Still, HTTP method selection must reflect actual application semantics.
REST-style conventions are useful, but they do not eliminate the need for
careful API design.
"""
)


# =============================================================================
# 88. PUT VS PATCH
# =============================================================================

section("88. PUT VS PATCH")

print(
    """
PUT generally represents replacement of the target resource representation.

PATCH represents partial modification.

Example conceptual PUT:

    PUT /users/42
    {
        "name": "Alice",
        "email": "alice@example.com",
        "active": true
    }

Example conceptual PATCH:

    PATCH /users/42
    {
        "active": false
    }

The exact application semantics depend on the API contract.

PUT is defined as idempotent.

PATCH is not inherently idempotent, although a particular PATCH operation
can be designed to behave idempotently.
"""
)


# =============================================================================
# 89. DELETE
# =============================================================================

section("89. DELETE")

print(
    """
DELETE requests removal of the target resource association.

Possible successful responses include:

    200 OK
    202 Accepted
    204 No Content

The correct status depends on whether the operation is complete, asynchronous,
and whether a response representation is returned.

A second DELETE may result in 404, depending on the resource semantics.
Idempotency concerns the intended effect, not identical response codes.
"""
)


# =============================================================================
# 90. POST
# =============================================================================

section("90. POST")

print(
    """
POST asks the target resource to process enclosed content according to the
resource's semantics.

Common uses include:

    resource creation
    commands
    form submission
    triggering processing
    search operations that require a body

POST is not automatically equivalent to "create a row in a database".

Its semantics are determined by the target resource and API contract.
"""
)


# =============================================================================
# 91. HTTP STATUS AND APPLICATION ERRORS
# =============================================================================

section("91. PROTOCOL ERRORS VS APPLICATION ERRORS")

print(
    """
Consider an API request:

    POST /users

with:

    {
        "age": -5
    }

The HTTP request can be syntactically valid while the application rejects
the semantic content.

This distinction matters:

    HTTP message validity
        Is the HTTP message correctly formed?

    Application validation
        Does the submitted data satisfy application rules?

A valid HTTP request can therefore receive a 4xx response.
"""
)


# =============================================================================
# 92. IDEMPOTENCY EXAMPLE
# =============================================================================

section("92. IDEMPOTENCY SIMULATION")

class ResourceStore:
    """Tiny resource store for illustrating idempotent PUT and DELETE."""

    def __init__(self) -> None:
        self.resources: Dict[str, Dict[str, object]] = {}

    def put(self, resource_id: str, value: Dict[str, object]) -> HTTPStatus:
        """Replace the resource representation."""
        self.resources[resource_id] = dict(value)
        return HTTPStatus.OK

    def delete(self, resource_id: str) -> HTTPStatus:
        """Delete a resource."""
        self.resources.pop(resource_id, None)
        return HTTPStatus.NO_CONTENT


store = ResourceStore()

print(store.put("42", {"name": "Alice"}))
print(store.put("42", {"name": "Alice"}))
print(store.resources)

print(store.delete("42"))
print(store.delete("42"))
print(store.resources)

print(
    """
The internal state after repeated PUT operations is the same as after one
equivalent PUT.

Repeated DELETE operations also converge on the same absence of the resource.

The returned status may differ in a real API, and that does not by itself
violate idempotency.
"""
)


# =============================================================================
# 93. SAFE METHOD EXAMPLE
# =============================================================================

section("93. SAFE METHODS")

print(
    """
GET, HEAD, OPTIONS, and TRACE are defined as safe methods.

Safe does not mean:

    "the server performs absolutely no side effects"

Servers can update logs, metrics, caches, counters, or other incidental
internal state.

Safety means the method is intended for retrieval or non-state-changing
semantics from the perspective of the requested resource.
"""
)


# =============================================================================
# 94. HTTP REQUEST/RESPONSE DATA MODEL
# =============================================================================

section("94. HTTP MESSAGE DATA MODEL")

@dataclass
class HTTPMessage:
    """Generic educational representation of an HTTP message."""

    version: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def content_length(self) -> int:
        """Return body length in bytes."""
        return len(self.body)


@dataclass
class HTTPRequestMessage(HTTPMessage):
    """Educational HTTP request model."""

    method: str = "GET"
    target: str = "/"


@dataclass
class HTTPResponseMessage(HTTPMessage):
    """Educational HTTP response model."""

    status_code: int = 200
    reason: str = "OK"


request_message = HTTPRequestMessage(
    version="HTTP/1.1",
    method="GET",
    target="/users",
    headers={"Host": "example.com"},
)

response_message = HTTPResponseMessage(
    version="HTTP/1.1",
    status_code=200,
    reason="OK",
    headers={"Content-Type": "application/json"},
    body=b'{"users":[]}',
)

print(request_message)
print(response_message)
print("Response body bytes:", response_message.content_length())


# =============================================================================
# 95. HTTP RESPONSE CONSTRUCTION
# =============================================================================

section("95. BUILDING A RAW HTTP RESPONSE")

def build_http_response(
    status_code: int,
    headers: Mapping[str, str],
    body: bytes = b"",
) -> bytes:
    """Build a basic HTTP/1.1 response."""
    try:
        reason = HTTPStatus(status_code).phrase
    except ValueError:
        reason = ""

    normalized_headers = dict(headers)

    if body and "Content-Length" not in normalized_headers:
        normalized_headers["Content-Length"] = str(len(body))

    if not body and status_code not in {204, 304}:
        normalized_headers.setdefault("Content-Length", "0")

    lines = [f"HTTP/1.1 {status_code} {reason}"]

    for name, value in normalized_headers.items():
        lines.append(f"{name}: {value}")

    lines.append("")

    return (
        "\r\n".join(lines).encode("iso-8859-1")
        + b"\r\n"
        + body
    )


raw_built_response = build_http_response(
    200,
    {
        "Content-Type": "text/plain; charset=utf-8",
    },
    b"Hello HTTP",
)

print(raw_built_response.decode("iso-8859-1"))


# =============================================================================
# 96. HTTP RESPONSE PARSING
# =============================================================================

section("96. SIMPLE HTTP RESPONSE PARSER")

@dataclass
class ParsedHTTPResponse:
    version: str
    status_code: int
    reason: str
    headers: Dict[str, str]
    body: bytes


def parse_simple_http_response(raw: bytes) -> ParsedHTTPResponse:
    """Parse a simple HTTP/1.x response for educational purposes."""
    separator = b"\r\n\r\n"

    if separator not in raw:
        raise ValueError("Missing header/body separator")

    header_section, body = raw.split(separator, 1)
    lines = header_section.split(b"\r\n")

    status_line = lines[0].decode("iso-8859-1")
    parts = status_line.split(" ", 2)

    if len(parts) != 3:
        raise ValueError("Malformed status line")

    version, status_text, reason = parts

    try:
        status_code = int(status_text)
    except ValueError as exc:
        raise ValueError("Invalid status code") from exc

    headers: Dict[str, str] = {}

    for line in lines[1:]:
        decoded = line.decode("iso-8859-1")

        if ":" not in decoded:
            raise ValueError("Malformed header")

        name, value = decoded.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return ParsedHTTPResponse(
        version=version,
        status_code=status_code,
        reason=reason,
        headers=headers,
        body=body,
    )


parsed_response = parse_simple_http_response(raw_built_response)

print("Version:", parsed_response.version)
print("Status:", parsed_response.status_code)
print("Reason:", parsed_response.reason)
print("Headers:", parsed_response.headers)
print("Body:", parsed_response.body)


# =============================================================================
# 97. HTTP BODY FRAMING
# =============================================================================

section("97. HTTP BODY FRAMING")

print(
    """
A receiver needs to know where the message body ends.

In HTTP/1.x, body framing can depend on:

    request/response semantics
    Content-Length
    Transfer-Encoding
    connection closure
    status-code rules

Certain responses do not carry a body under HTTP semantics.

This is why parsing HTTP is more complicated than simply reading until a
socket closes.

HTTP/2 and HTTP/3 use explicit frame/stream mechanisms at the protocol level.
"""
)


# =============================================================================
# 98. CONNECTION CLOSE
# =============================================================================

section("98. CONNECTION CLOSURE")

print(
    """
A connection can be closed because:

    the client closes it
    the server closes it
    an intermediary closes it
    an error occurs
    protocol rules require closure

Connection closure can sometimes provide message delimitation in HTTP/1.x,
but applications should not treat every connection close as an application
error.

Connection lifecycle and message lifecycle are related but distinct.
"""
)


# =============================================================================
# 99. TCP SOCKET CONCEPT
# =============================================================================

section("99. RAW SOCKET CONCEPT")

print(
    """
HTTP/1.1 can be transported over a TCP byte stream.

A socket does not understand:

    GET
    POST
    HTTP/1.1
    headers
    JSON

Those are application-level concepts.

The application writes bytes to a socket and reads bytes from it.

The protocol implementation is responsible for turning those bytes into
structured HTTP messages.
"""
)


# =============================================================================
# 100. RAW LOCAL SOCKET HTTP CLIENT
# =============================================================================

section("100. RAW SOCKET HTTP CLIENT")

raw_server, raw_thread = start_demo_server()
raw_host, raw_port = raw_server.server_address

sock = socket.create_connection((raw_host, raw_port), timeout=5)

try:
    raw_socket_request = (
        f"GET /hello?name=Socket HTTP/1.1\r\n"
        f"Host: {raw_host}:{raw_port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")

    sock.sendall(raw_socket_request)

    received = bytearray()

    while True:
        chunk = sock.recv(4096)

        if not chunk:
            break

        received.extend(chunk)

    print(received.decode("utf-8", errors="replace"))

finally:
    sock.close()
    raw_server.shutdown()
    raw_server.server_close()


# =============================================================================
# 101. HTTP TRACE CONCEPT
# =============================================================================

section("101. TRACE")

print(
    """
TRACE can be used for diagnostic loop-back behavior.

Because exposing TRACE can create security concerns in some environments,
production servers should enable HTTP methods intentionally rather than
assuming every method should be exposed.

An API should explicitly define which methods are supported.
"""
)


# =============================================================================
# 102. CONNECT CONCEPT
# =============================================================================

section("102. CONNECT")

print(
    """
CONNECT establishes a tunnel through an intermediary.

It is commonly associated with proxies tunneling HTTPS connections.

Conceptually:

    Client
       |
       | CONNECT example.com:443
       v
    Proxy
       |
       | tunnel
       v
    Target

Once the tunnel is established, encrypted TLS traffic can pass through the
proxy without the proxy needing to interpret the protected HTTP messages.
"""
)


# =============================================================================
# 103. HTTP/2 CONCEPTUAL MODEL
# =============================================================================

section("103. HTTP/2 CONCEPTUAL MODEL")

print(
    """
HTTP/2 introduces a binary framing layer.

Important concepts include:

    streams
    frames
    multiplexing
    HPACK header compression
    stream-level flow control
    connection-level flow control

Multiple logical HTTP requests and responses can share one underlying
connection.

This reduces some limitations of HTTP/1.1's request scheduling model.

The application still works with familiar HTTP concepts such as methods,
headers, status codes, and bodies.
"""
)


# =============================================================================
# 104. HTTP/3 CONCEPTUAL MODEL
# =============================================================================

section("104. HTTP/3 CONCEPTUAL MODEL")

print(
    """
HTTP/3 maps HTTP semantics onto QUIC.

QUIC provides:

    encrypted transport
    independent streams
    connection migration features
    stream-level loss handling

HTTP/3 uses a binary framing model and does not use HTTP/1.1 chunked transfer
encoding.

The move from TCP to QUIC is a transport-level architectural difference, not
a replacement of HTTP request semantics.
"""
)


# =============================================================================
# 105. ALPN
# =============================================================================

section("105. APPLICATION-LAYER PROTOCOL NEGOTIATION")

print(
    """
ALPN allows TLS peers to negotiate an application protocol.

For HTTPS deployments, protocols such as:

    h2
    h3

can be selected through appropriate negotiation mechanisms.

The client and server therefore agree on the protocol used after or alongside
secure connection establishment according to the relevant transport model.
"""
)


# =============================================================================
# 106. HTTP SECURITY HEADERS
# =============================================================================

section("106. SECURITY-RELATED RESPONSE HEADERS")

security_headers = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

for name, value in security_headers.items():
    print(f"{name}: {value}")

print(
    """
Security-related response headers can strengthen browser security behavior.

Examples include:

    Strict-Transport-Security
        Requests HTTPS for a site after policy is established.

    Content-Security-Policy
        Restricts permitted resource/script behavior.

    X-Content-Type-Options
        Helps prevent MIME type sniffing behavior.

    Referrer-Policy
        Controls referrer information sent with requests.

Their correct values depend on the application's architecture.
"""
)


# =============================================================================
# 107. CSRF CONCEPT
# =============================================================================

section("107. CSRF CONCEPT")

print(
    """
Cross-Site Request Forgery can occur when a browser is induced to send an
authenticated request to a site where the browser automatically supplies
credentials such as cookies.

Common defenses include:

    SameSite cookie policies
    CSRF tokens
    origin/referrer validation where appropriate
    appropriate authentication architecture

CORS and CSRF are related to browser cross-origin behavior but solve different
security problems.
"""
)


# =============================================================================
# 108. XSS CONCEPT
# =============================================================================

section("108. XSS CONCEPT")

print(
    """
Cross-Site Scripting is an application-layer vulnerability where untrusted
content becomes executable script in a user's browser context.

HTTP transports the content, but HTTP itself does not prevent XSS.

Defenses depend on context and can include:

    output encoding
    input validation
    Content-Security-Policy
    safe templating
    avoiding unsafe HTML injection
"""
)


# =============================================================================
# 109. SQL INJECTION RELATIONSHIP
# =============================================================================

section("109. HTTP AND BACKEND INJECTION")

print(
    """
An HTTP request can be the delivery mechanism for malicious input targeting a
backend component.

For example:

    HTTP request
        |
        v
    application
        |
        v
    database

HTTP validation alone cannot prevent SQL injection.

The application must use safe database APIs, parameterized queries, and
appropriate validation.
"""
)


# =============================================================================
# 110. HTTP CLIENT BEST PRACTICES
# =============================================================================

section("110. HTTP CLIENT BEST PRACTICES")

client_best_practices = [
    "Set explicit timeouts.",
    "Use HTTPS for sensitive communication.",
    "Validate TLS certificates.",
    "Handle HTTP status codes explicitly.",
    "Distinguish network failures from HTTP responses.",
    "Retry only when the operation and failure mode justify it.",
    "Use exponential backoff with jitter for suitable transient failures.",
    "Respect Retry-After and rate-limit signals.",
    "Reuse connections when appropriate.",
    "Limit response and request sizes.",
    "Validate content types before parsing bodies.",
    "Avoid logging secrets and authorization headers.",
    "Use established HTTP libraries rather than handwritten parsers in production.",
]

for item in client_best_practices:
    print("*", item)


# =============================================================================
# 111. HTTP SERVER BEST PRACTICES
# =============================================================================

section("111. HTTP SERVER BEST PRACTICES")

server_best_practices = [
    "Validate request methods and targets.",
    "Validate Content-Type before parsing structured bodies.",
    "Enforce request-size limits.",
    "Use TLS correctly.",
    "Apply authentication and authorization separately.",
    "Return meaningful status codes.",
    "Do not expose unnecessary methods.",
    "Use secure cookie attributes.",
    "Configure caching intentionally.",
    "Protect sensitive responses from unintended shared caching.",
    "Rate-limit expensive or abusive operations.",
    "Log useful metadata without leaking secrets.",
    "Use robust HTTP parsing libraries.",
    "Set appropriate security headers.",
    "Handle timeouts and upstream failures.",
]

for item in server_best_practices:
    print("*", item)


# =============================================================================
# 112. PERFORMANCE CONSIDERATIONS
# =============================================================================

section("112. PERFORMANCE CONSIDERATIONS")

print(
    """
HTTP performance can be affected by:

    DNS latency
    TCP connection establishment
    TLS handshake
    request serialization
    server processing
    database latency
    response transfer
    packet loss
    congestion
    connection reuse
    compression
    caching
    multiplexing

Common techniques include:

    connection pooling
    persistent connections
    caching
    compression
    efficient payloads
    HTTP/2 multiplexing
    HTTP/3/QUIC where appropriate
    CDN usage
    asynchronous processing

Performance optimization should be measured rather than assumed.
"""
)


# =============================================================================
# 113. ASYNCHRONOUS PROCESSING
# =============================================================================

section("113. ASYNCHRONOUS HTTP OPERATIONS")

print(
    """
Some operations take longer than a normal request-response cycle.

A server may accept a request and return:

    202 Accepted

The body or headers can identify how the client can check progress.

This is useful for:

    report generation
    video processing
    data exports
    large imports
    long-running jobs

Returning 200 merely because a request was received can incorrectly imply
that the operation has already completed.
"""
)


# =============================================================================
# 114. HTTP AND WEB SOCKETS
# =============================================================================

section("114. HTTP AND WEBSOCKETS")

print(
    """
WebSocket is a different protocol designed for long-lived bidirectional
communication.

HTTP is primarily structured around request/response exchanges.

WebSocket connections can begin with an HTTP-based handshake and then
transition to WebSocket framing.

This distinction matters when choosing a communication protocol:

    HTTP
        Request/response resource interactions.

    WebSocket
        Long-lived bidirectional communication.

The correct choice depends on application requirements.
"""
)


# =============================================================================
# 115. HTTP AND SSE
# =============================================================================

section("115. HTTP STREAMING AND SERVER-SENT EVENTS")

print(
    """
Server-Sent Events use HTTP to provide a long-lived stream of server-to-client
events.

A response commonly uses:

    Content-Type: text/event-stream

The server can send events progressively instead of waiting to produce one
complete response body.

This differs from WebSocket because the communication direction and protocol
semantics are different.
"""
)


# =============================================================================
# 116. HTTP FILE DOWNLOAD
# =============================================================================

section("116. FILE DOWNLOAD HEADERS")

download_headers = {
    "Content-Type": "application/pdf",
    "Content-Disposition": 'attachment; filename="report.pdf"',
}

for name, value in download_headers.items():
    print(f"{name}: {value}")

print(
    """
Content-Disposition can influence how a user agent handles a representation.

For downloadable content, servers commonly specify:

    Content-Type
    Content-Disposition
    Content-Length

File download handling must consider filename safety and correct media type
handling.
"""
)


# =============================================================================
# 117. CONDITIONAL UPDATE
# =============================================================================

section("117. CONDITIONAL UPDATE WITH ETAG")

print(
    """
ETags can protect against lost updates.

Suppose:

    Client A reads resource version "5".
    Client B reads resource version "5".
    Client A updates it to version "6".
    Client B tries to update using:

        If-Match: "5"

The server can detect that the client's representation is stale and return:

    412 Precondition Failed

This is a form of optimistic concurrency control.
"""
)

current_etag = '"6"'
provided_if_match = '"5"'

if provided_if_match == current_etag:
    print("Update allowed")
else:
    print("Update rejected with 412 Precondition Failed")


# =============================================================================
# 118. IF-MATCH AND IF-NONE-MATCH
# =============================================================================

section("118. CONDITIONAL HEADER DISTINCTIONS")

conditional_headers = {
    "If-Match": "Used to require a matching current representation validator.",
    "If-None-Match": "Used to require that a validator not match.",
    "If-Modified-Since": "Conditional retrieval based on modification time.",
    "If-Unmodified-Since": "Conditional operation based on modification time.",
}

for header, meaning in conditional_headers.items():
    print(f"{header}: {meaning}")


# =============================================================================
# 119. HTTP CACHE AND VALIDATION FLOW
# =============================================================================

section("119. CACHE VALIDATION FLOW")

print(
    """
A typical validator-based cache flow:

    1. Client requests resource.
    2. Server returns 200 with body and ETag.
    3. Client stores body and ETag.
    4. Later client sends If-None-Match.
    5. Server compares ETag.
    6. If unchanged, server returns 304.
    7. Client reuses stored body.

This can save the cost of transferring an unchanged representation.
"""
)


# =============================================================================
# 120. HTTP REQUEST DEBUGGING CHECKLIST
# =============================================================================

section("120. HTTP DEBUGGING CHECKLIST")

debugging_checklist = [
    "Is the URL correct?",
    "Does DNS resolve the hostname?",
    "Is the target port reachable?",
    "Is TLS certificate validation succeeding?",
    "Is the HTTP method correct?",
    "Is the request target correct?",
    "Are required headers present?",
    "Is Content-Type correct?",
    "Is Content-Length correct when applicable?",
    "Is the request body valid?",
    "What status code did the server return?",
    "What response headers were returned?",
    "What does the response body contain?",
    "Was a redirect returned?",
    "Was authentication successful?",
    "Was authorization successful?",
    "Did a proxy or gateway modify the request?",
    "Did a timeout occur?",
    "Was the response served from a cache?",
]

for item in debugging_checklist:
    print("[ ]", item)


# =============================================================================
# 121. COMPLETE EXAMPLE REQUEST ANALYSIS
# =============================================================================

section("121. COMPLETE REQUEST ANALYSIS")

example_request = {
    "method": "POST",
    "url": "https://api.example.com/users?notify=true",
    "headers": {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer <redacted>",
    },
    "body": {
        "name": "Alice",
        "email": "alice@example.com",
    },
}

print(json.dumps(example_request, indent=2))

print(
    """
Analysis:

Method:
    POST indicates submission/processing semantics.

URL:
    HTTPS protects transport using TLS.

Path:
    /users identifies the target resource collection.

Query:
    notify=true provides additional request-target parameters.

Accept:
    Client prefers a JSON representation in the response.

Content-Type:
    Request body is JSON.

Authorization:
    Carries authentication credentials or authorization context.

Body:
    Contains application data that must be validated by the server.
"""
)


# =============================================================================
# 122. COMPLETE RESPONSE ANALYSIS
# =============================================================================

section("122. COMPLETE RESPONSE ANALYSIS")

example_response = {
    "status": 201,
    "reason": "Created",
    "headers": {
        "Content-Type": "application/json",
        "Location": "/users/42",
        "Cache-Control": "no-store",
    },
    "body": {
        "id": 42,
        "name": "Alice",
    },
}

print(json.dumps(example_response, indent=2))

print(
    """
Analysis:

201:
    The resource was created.

Location:
    Identifies the newly created resource.

Content-Type:
    Describes the response representation.

Cache-Control:
    Prevents storage under the specified no-store directive.

Body:
    Provides a representation containing the created resource.
"""
)


# =============================================================================
# 123. HTTP SEMANTICS VS IMPLEMENTATION
# =============================================================================

section("123. HTTP SEMANTICS VS IMPLEMENTATION")

print(
    """
HTTP defines protocol semantics.

Python libraries decide how those semantics are exposed through programming
interfaces.

A framework may expose:

    request.method
    request.headers
    request.body
    request.path
    response.status_code

Those are abstractions over lower-level HTTP behavior.

Understanding the protocol helps explain what those framework objects
actually represent.
"""
)


# =============================================================================
# 124. COMMON MISTAKES
# =============================================================================

section("124. COMMON HTTP MISTAKES")

mistakes = [
    "Treating every HTTP error as a network failure.",
    "Assuming 401 means authorization rather than authentication.",
    "Using 200 for every application outcome.",
    "Sending JSON without Content-Type: application/json.",
    "Confusing Content-Encoding with Content-Type.",
    "Assuming Content-Length counts characters rather than bytes.",
    "Blindly retrying POST operations.",
    "Disabling TLS certificate verification.",
    "Logging Authorization headers.",
    "Using cacheable responses for sensitive information without understanding cache semantics.",
    "Writing an HTTP parser for production use without handling protocol edge cases.",
    "Assuming browser CORS restrictions apply identically to all HTTP clients.",
    "Assuming safe means zero side effects of every kind.",
    "Assuming idempotent means identical response bodies.",
    "Treating URL paths as safe filesystem paths.",
]

for mistake in mistakes:
    print("*", mistake)


# =============================================================================
# 125. HTTP DESIGN PRINCIPLES
# =============================================================================

section("125. IMPORTANT HTTP DESIGN PRINCIPLES")

principles = [
    "Use method semantics consistently.",
    "Use status codes according to actual protocol/application outcomes.",
    "Describe representations with accurate media types.",
    "Validate request bodies.",
    "Treat headers as structured protocol metadata.",
    "Use HTTPS for protected communication.",
    "Make caching behavior explicit.",
    "Design retries around idempotency and failure semantics.",
    "Use conditional requests for efficient caching and concurrency control.",
    "Limit resource consumption.",
    "Use mature HTTP implementations in production.",
]

for principle in principles:
    print("*", principle)


# =============================================================================
# 126. MINI HTTP KNOWLEDGE TEST
# =============================================================================

section("126. MINI HTTP KNOWLEDGE TEST")

questions = {
    "What does HTTP stand for?": "Hypertext Transfer Protocol",
    "Which method normally retrieves a resource?": "GET",
    "Which header describes request body media type?": "Content-Type",
    "Which status code means Not Found?": "404",
    "Which status code means Created?": "201",
    "Which status code indicates Too Many Requests?": "429",
    "Which method is defined as idempotent?": "PUT",
    "Which header can identify a representation version?": "ETag",
    "Which status indicates an unchanged conditional representation?": "304",
    "Which protocol protects ordinary HTTPS traffic?": "TLS",
}

for question, answer in questions.items():
    print(f"Q: {question}")
    print(f"A: {answer}")


# =============================================================================
# 127. FINAL INTEGRATED EXAMPLE
# =============================================================================

section("127. FINAL INTEGRATED HTTP EXAMPLE")

integrated_request = HTTPRequestMessage(
    version="HTTP/1.1",
    method="POST",
    target="/api/users?source=study",
    headers={
        "Host": "api.example.com",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "HTTPStudyClient/1.0",
    },
    body=json.dumps(
        {
            "name": "Alice",
            "role": "developer",
        }
    ).encode("utf-8"),
)

integrated_request.headers["Content-Length"] = str(
    len(integrated_request.body)
)

print("REQUEST")
print(f"{integrated_request.method} {integrated_request.target} {integrated_request.version}")

for name, value in integrated_request.headers.items():
    print(f"{name}: {value}")

print()
print(integrated_request.body.decode("utf-8"))

integrated_response = HTTPResponseMessage(
    version="HTTP/1.1",
    status_code=HTTPStatus.CREATED.value,
    reason=HTTPStatus.CREATED.phrase,
    headers={
        "Content-Type": "application/json; charset=utf-8",
        "Location": "/api/users/42",
        "Cache-Control": "no-store",
    },
    body=json.dumps(
        {
            "id": 42,
            "name": "Alice",
            "role": "developer",
        }
    ).encode("utf-8"),
)

integrated_response.headers["Content-Length"] = str(
    len(integrated_response.body)
)

print("\nRESPONSE")
print(
    f"{integrated_response.version} "
    f"{integrated_response.status_code} "
    f"{integrated_response.reason}"
)

for name, value in integrated_response.headers.items():
    print(f"{name}: {value}")

print()
print(integrated_response.body.decode("utf-8"))


# =============================================================================
# 128. FINAL CONCEPTUAL MODEL
# =============================================================================

section("128. HTTP CONCEPTUAL MODEL")

print(
    """
The essential HTTP model can be represented as:

    URL
     |
     v
    Client
     |
     |  Method + Target + Headers + Optional Body
     v
    HTTP Request
     |
     v
    Intermediaries
     |
     v
    Server
     |
     |  Status + Headers + Optional Body
     v
    HTTP Response
     |
     v
    Client

The most important protocol concepts are:

    Request:
        method
        target
        version
        headers
        optional body

    Response:
        version
        status code
        reason phrase
        headers
        optional body

    Semantics:
        methods
        status codes
        caching
        conditional requests
        content negotiation
        authentication
        authorization
        redirects

    Transport and protocol versions:
        HTTP/1.0
        HTTP/1.1
        HTTP/2
        HTTP/3

    Security:
        TLS
        secure cookies
        authentication
        authorization
        validation
        safe parsing
        careful caching
        controlled exposure

HTTP is therefore more than a collection of verbs and status codes. It is a
structured application protocol whose semantics govern how clients,
servers, and intermediaries exchange representations and communicate the
outcome of operations.
"""
)


if __name__ == "__main__":
    print("\nHTTP fundamentals study script completed successfully.")
