"""
Web Servers: fundamentals through advanced concepts.

This standalone study script demonstrates:
- What a web server does
- HTTP request/response flow
- Static file serving
- MIME types and security boundaries
- Routing
- Application-server concepts
- Reverse-proxy behavior
- Load balancing
- Health checks
- Timeouts and retries
- Security headers
- Logging and metrics
- Caching
- A small production-oriented architecture simulation

Only the Python standard library is used.
"""

from __future__ import annotations

import mimetypes
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse


# ============================================================
# 1. FUNDAMENTALS: REQUESTS AND RESPONSES
# ============================================================

@dataclass
class HttpRequest:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def basic_http_exchange() -> None:
    """Show the conceptual structure of an HTTP transaction."""
    request = HttpRequest(
        method="GET",
        path="/index.html",
        headers={
            "Host": "example.test",
            "Accept": "text/html",
        },
    )

    response = HttpResponse(
        status=200,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": "18",
        },
        body=b"<h1>Hello</h1>",
    )

    print("\n=== HTTP request ===")
    print(request.method, request.path)
    print(request.headers)

    print("\n=== HTTP response ===")
    print(response.status, HTTPStatus(response.status).phrase)
    print(response.headers)
    print(response.text())


# ============================================================
# 2. STATIC FILE SERVING
# ============================================================

class StaticFileServer:
    """
    Minimal static-file server.

    A real web server such as nginx, Apache HTTP Server, Caddy, or a
    cloud load balancer performs many more optimizations and security
    checks. This class is educational rather than production-ready.
    """

    def __init__(self, document_root: str | Path):
        self.document_root = Path(document_root).resolve()

    def resolve_safe_path(self, request_path: str) -> Path | None:
        """
        Convert a URL path to a filesystem path while preventing
        traversal outside document_root.
        """
        parsed_path = urlparse(request_path).path

        # URL paths use '/', regardless of the host operating system.
        relative_path = parsed_path.lstrip("/")
        candidate = (self.document_root / relative_path).resolve()

        try:
            candidate.relative_to(self.document_root)
        except ValueError:
            return None

        return candidate

    def serve(self, request_path: str) -> HttpResponse:
        file_path = self.resolve_safe_path(request_path)

        if file_path is None:
            return HttpResponse(
                status=HTTPStatus.FORBIDDEN,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=b"Forbidden",
            )

        if not file_path.exists() or not file_path.is_file():
            return HttpResponse(
                status=HTTPStatus.NOT_FOUND,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=b"Not Found",
            )

        try:
            content = file_path.read_bytes()
        except OSError:
            return HttpResponse(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=b"Could not read file",
            )

        content_type, _ = mimetypes.guess_type(file_path.name)
        content_type = content_type or "application/octet-stream"

        return HttpResponse(
            status=HTTPStatus.OK,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(len(content)),
            },
            body=content,
        )


def demonstrate_static_files() -> None:
    root = Path("web_demo_public")
    root.mkdir(exist_ok=True)

    (root / "index.html").write_text(
        "<html><body><h1>Static page</h1></body></html>",
        encoding="utf-8",
    )
    (root / "style.css").write_text(
        "body { font-family: sans-serif; }",
        encoding="utf-8",
    )

    server = StaticFileServer(root)

    print("\n=== Static file serving ===")
    for path in ("/index.html", "/style.css", "/missing.html", "/../secret.txt"):
        response = server.serve(path)
        print(path, "->", response.status, HTTPStatus(response.status).phrase)

    # Clean up the educational files.
    for file_path in root.iterdir():
        file_path.unlink()
    root.rmdir()


# ============================================================
# 3. APPLICATION-SERVER CONCEPT
# ============================================================

class Application:
    """
    An application server executes application logic.

    The application does not need to know whether a client connected
    directly, through a reverse proxy, or through a load balancer.
    """

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed = urlparse(request.path)

        if parsed.path == "/":
            return HttpResponse(
                status=200,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=b"Application server is running",
            )

        if parsed.path == "/api/hello":
            query = parse_qs(parsed.query)
            name = query.get("name", ["world"])[0]

            # Validation prevents an unexpectedly large input from
            # consuming unnecessary memory or processing time.
            if len(name) > 100:
                return HttpResponse(
                    status=400,
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                    body=b"Name is too long",
                )

            message = f"Hello, {name}!".encode()
            return HttpResponse(
                status=200,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=message,
            )

        return HttpResponse(
            status=404,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            body=b"Application route not found",
        )


# ============================================================
# 4. REVERSE PROXY CONCEPT
# ============================================================

@dataclass
class Backend:
    name: str
    application: Application
    healthy: bool = True
    request_count: int = 0


class ReverseProxy:
    """
    Simplified reverse proxy.

    Client -> reverse proxy -> application server

    A reverse proxy can:
    - hide backend addresses
    - terminate TLS
    - route requests
    - balance traffic
    - apply security policies
    - cache responses
    - compress responses
    - enforce limits
    - perform health checks
    """

    def __init__(self, backends: list[Backend]):
        if not backends:
            raise ValueError("At least one backend is required")

        self.backends = backends
        self.next_index = 0

    def select_backend(self) -> Backend | None:
        healthy_backends = [backend for backend in self.backends if backend.healthy]

        if not healthy_backends:
            return None

        # Round-robin selection.
        backend = healthy_backends[self.next_index % len(healthy_backends)]
        self.next_index += 1
        return backend

    def handle(self, request: HttpRequest) -> HttpResponse:
        backend = self.select_backend()

        if backend is None:
            return HttpResponse(
                status=503,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=b"No healthy application server",
            )

        backend.request_count += 1

        # These headers illustrate information commonly supplied by
        # a proxy to the application.
        forwarded_request = HttpRequest(
            method=request.method,
            path=request.path,
            headers={
                **request.headers,
                "X-Forwarded-For": request.headers.get("Client-IP", "unknown"),
                "X-Forwarded-Proto": "http",
            },
            body=request.body,
        )

        response = backend.application.handle(forwarded_request)

        response.headers["X-Backend"] = backend.name
        response.headers["Via"] = "Educational-Reverse-Proxy"

        return response


def demonstrate_reverse_proxy() -> None:
    backends = [
        Backend("app-1", Application()),
        Backend("app-2", Application()),
        Backend("app-3", Application()),
    ]

    proxy = ReverseProxy(backends)

    print("\n=== Reverse proxy and load balancing ===")

    for index in range(6):
        request = HttpRequest(
            method="GET",
            path=f"/api/hello?name=user{index}",
            headers={"Client-IP": "192.0.2.10"},
        )

        response = proxy.handle(request)
        print(
            f"request={index + 1}, status={response.status}, "
            f"backend={response.headers.get('X-Backend')}, "
            f"body={response.text()}"
        )

    # Simulate a failed backend.
    backends[1].healthy = False

    print("\nAfter app-2 becomes unhealthy:")
    for index in range(4):
        response = proxy.handle(
            HttpRequest("GET", "/api/hello?name=health-test")
        )
        print(response.headers.get("X-Backend"))

    print("\nBackend request counts:")
    for backend in backends:
        print(backend.name, backend.request_count)


# ============================================================
# 5. CACHING
# ============================================================

@dataclass
class CacheEntry:
    response: HttpResponse
    expires_at: float


class ResponseCache:
    """Small TTL cache illustrating cache freshness."""

    def __init__(self, ttl_seconds: float = 10):
        self.ttl_seconds = ttl_seconds
        self.entries: dict[str, CacheEntry] = {}

    def get(self, key: str) -> HttpResponse | None:
        entry = self.entries.get(key)

        if entry is None:
            return None

        if time.monotonic() >= entry.expires_at:
            del self.entries[key]
            return None

        return entry.response

    def put(self, key: str, response: HttpResponse) -> None:
        self.entries[key] = CacheEntry(
            response=response,
            expires_at=time.monotonic() + self.ttl_seconds,
        )


def demonstrate_cache() -> None:
    cache = ResponseCache(ttl_seconds=1)
    response = HttpResponse(200, {"Content-Type": "text/plain"}, b"cached")

    cache.put("/api/data", response)

    print("\n=== Cache ===")
    print("Immediate lookup:", cache.get("/api/data").text())
    time.sleep(1.05)
    print("After TTL:", cache.get("/api/data"))


# ============================================================
# 6. SECURITY HEADERS
# ============================================================

def add_security_headers(response: HttpResponse) -> HttpResponse:
    """
    Security headers are commonly added at the proxy or web-server
    layer, although applications can also generate them.
    """
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }
    )
    return response


# ============================================================
# 7. OBSERVABILITY
# ============================================================

def log_request(
    request: HttpRequest,
    response: HttpResponse,
    duration_ms: float,
) -> None:
    print(
        f"[ACCESS] method={request.method} "
        f"path={request.path} "
        f"status={response.status} "
        f"duration_ms={duration_ms:.2f}"
    )


def demonstrate_observability(proxy: ReverseProxy) -> None:
    print("\n=== Logging ===")
    request = HttpRequest("GET", "/api/hello?name=observability")

    start = time.perf_counter()
    response = proxy.handle(request)
    response = add_security_headers(response)
    duration_ms = (time.perf_counter() - start) * 1000

    log_request(request, response, duration_ms)
    print("Security header:", response.headers["X-Content-Type-Options"])


# ============================================================
# 8. REAL HTTP SERVER
# ============================================================

class DemoRequestHandler(BaseHTTPRequestHandler):
    """
    A real HTTP endpoint using Python's standard library.

    The handler itself acts as a small web server. Production systems
    generally place a mature web server or reverse proxy in front of
    application processes.
    """

    application = Application()

    def send_application_response(self, response: HttpResponse) -> None:
        response = add_security_headers(response)

        self.send_response(response.status)

        for name, value in response.headers.items():
            self.send_header(name, value)

        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(response.body)

    def do_GET(self) -> None:
        request = HttpRequest(
            method="GET",
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
        )
        response = self.application.handle(request)
        self.send_application_response(response)

    def do_HEAD(self) -> None:
        request = HttpRequest("HEAD", self.path)
        response = self.application.handle(request)
        self.send_application_response(response)

    def log_message(self, format_string: str, *args) -> None:
        # Keep demonstration output concise.
        print("[HTTP]", format_string % args)


def run_real_http_server() -> None:
    """
    Start a local HTTP server for manual testing.

    Set RUN_HTTP_SERVER=1 to activate it:
        RUN_HTTP_SERVER=1 python web_servers.py

    The server listens only on localhost.
    """
    if os.environ.get("RUN_HTTP_SERVER") != "1":
        return

    host = "127.0.0.1"
    port = 8080

    server = ThreadingHTTPServer((host, port), DemoRequestHandler)

    print(f"\nHTTP server running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


# ============================================================
# 9. NETWORK FUNDAMENTALS
# ============================================================

def demonstrate_dns_and_ports() -> None:
    print("\n=== DNS and ports ===")

    hostname = "localhost"
    address = socket.gethostbyname(hostname)

    print(f"{hostname} resolves locally to {address}")
    print("HTTP commonly uses port 80.")
    print("HTTPS commonly uses port 443.")
    print("An application server may listen on another private port.")


# ============================================================
# 10. FAILURE MODES
# ============================================================

def demonstrate_failures() -> None:
    print("\n=== Failure handling ===")

    backends = [
        Backend("primary", Application()),
        Backend("secondary", Application()),
    ]

    proxy = ReverseProxy(backends)

    for backend in backends:
        backend.healthy = False

    response = proxy.handle(HttpRequest("GET", "/"))
    print("No healthy backends:", response.status, response.text())

    # Restore one server.
    backends[0].healthy = True
    response = proxy.handle(HttpRequest("GET", "/"))
    print("Recovered service:", response.status, response.text())


# ============================================================
# 11. PERFORMANCE MEASUREMENT
# ============================================================

def benchmark_proxy(iterations: int = 10_000) -> None:
    proxy = ReverseProxy(
        [
            Backend("app-1", Application()),
            Backend("app-2", Application()),
            Backend("app-3", Application()),
        ]
    )

    request = HttpRequest("GET", "/api/hello?name=benchmark")

    start = time.perf_counter()

    for _ in range(iterations):
        proxy.handle(request)

    elapsed = time.perf_counter() - start
    requests_per_second = iterations / elapsed if elapsed else float("inf")

    print("\n=== Simple benchmark ===")
    print("Iterations:", iterations)
    print(f"Elapsed: {elapsed:.6f} seconds")
    print(f"Requests/second: {requests_per_second:.0f}")

    print(
        "\nThis benchmark measures Python function dispatch, not network "
        "throughput. Real benchmarks must include the actual network stack, "
        "payload sizes, concurrency, TLS, storage, and workload."
    )


# ============================================================
# 12. ARCHITECTURE COMPARISON
# ============================================================

def architecture_comparison() -> None:
    print("\n=== Architectural roles ===")

    roles = {
        "Web server": "Accepts HTTP requests and commonly serves static content.",
        "Reverse proxy": "Receives client traffic and forwards it to backends.",
        "Application server": "Runs application/business logic.",
        "Load balancer": "Distributes requests across multiple backends.",
        "Database": "Persists application state and data.",
        "Cache": "Stores reusable data or responses to reduce latency/load.",
    }

    for role, responsibility in roles.items():
        print(f"{role}: {responsibility}")


# ============================================================
# 13. MAIN STUDY PROGRAM
# ============================================================

def main() -> None:
    print("WEB SERVERS: COMPLETE PYTHON STUDY PROGRAM")

    basic_http_exchange()
    demonstrate_static_files()
    demonstrate_reverse_proxy()
    demonstrate_cache()

    backends = [
        Backend("app-1", Application()),
        Backend("app-2", Application()),
    ]

    demonstrate_observability(ReverseProxy(backends))
    demonstrate_dns_and_ports()
    demonstrate_failures()
    architecture_comparison()

    benchmark_proxy()

    print("\n=== Production principles ===")
    print("1. Keep public traffic at a controlled network boundary.")
    print("2. Separate static delivery from dynamic application execution when useful.")
    print("3. Use timeouts so failed dependencies do not consume resources indefinitely.")
    print("4. Use health checks before routing traffic to a backend.")
    print("5. Log structured request information without exposing secrets.")
    print("6. Validate input at trust boundaries.")
    print("7. Use HTTPS for real deployments.")
    print("8. Apply appropriate caching rather than caching every response.")
    print("9. Monitor latency, error rate, throughput, and resource usage.")
    print("10. Design graceful failure instead of assuming every backend is available.")

    run_real_http_server()


if __name__ == "__main__":
    main()
