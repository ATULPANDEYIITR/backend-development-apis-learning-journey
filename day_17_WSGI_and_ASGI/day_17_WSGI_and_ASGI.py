"""
WSGI and ASGI: a progressive technical study

This standalone script teaches:
- HTTP server/application boundaries
- WSGI and ASGI
- synchronous versus asynchronous execution
- WSGI/ASGI callable interfaces
- middleware
- request/response flow
- Uvicorn and Gunicorn architecture
- Gunicorn worker models
- ASGI worker processes
- concurrency, parallelism, blocking I/O, and event loops
- lifespan handling
- streaming and WebSockets
- production configuration
- testing, observability, security, and performance
- a small WSGI application
- a small ASGI application
- a miniature ASGI dispatcher
- a concurrency simulation
- architecture comparisons

The examples use only the Python standard library.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Iterable


# ============================================================
# 1. BASIC TERMINOLOGY
# ============================================================

def explain_basic_architecture() -> None:
    print("\n=== 1. BASIC ARCHITECTURE ===")
    print("""
A web request commonly passes through several layers:

Client
  -> network
  -> HTTP server
  -> application server/interface
  -> framework/application
  -> database or external service

A web server handles network-facing HTTP concerns.
An application framework handles application logic.
WSGI and ASGI define interfaces between a server and a Python application.

WSGI is primarily synchronous and request/response oriented.
ASGI supports asynchronous applications and protocols such as HTTP and WebSocket.

A process is an operating-system execution environment.
A thread is an execution path inside a process.
An event loop coordinates asynchronous tasks.
A worker is a process or execution unit serving application traffic.

Concurrency means multiple operations can make progress during overlapping
periods. Parallelism means operations actually execute simultaneously, usually
on multiple CPU cores or execution resources.

An async function does not automatically make blocking code non-blocking.
A synchronous library called directly from an async function can block the
event loop.
""")


# ============================================================
# 2. A MINIMAL WSGI APPLICATION
# ============================================================

def wsgi_application(
    environ: dict[str, Any],
    start_response: Callable[[str, list[tuple[str, str]]], None],
) -> Iterable[bytes]:
    """
    Minimal WSGI application.

    WSGI application signature:

        application(environ, start_response) -> iterable[bytes]

    environ contains request metadata.
    start_response is called with an HTTP status and response headers.
    The returned iterable contains response body bytes.
    """
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if method != "GET":
        start_response(
            "405 Method Not Allowed",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Allow", "GET"),
            ],
        )
        return [b"Only GET is supported"]

    body = f"WSGI response for {path}\n".encode("utf-8")

    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def demonstrate_wsgi() -> None:
    print("\n=== 2. WSGI CALLABLE ===")

    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/hello",
        "QUERY_STRING": "name=Atul",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "wsgi.url_scheme": "http",
    }

    response_body = b"".join(wsgi_application(environ, start_response))

    print("Status:", captured["status"])
    print("Headers:", captured["headers"])
    print("Body:", response_body.decode())


# ============================================================
# 3. WSGI REQUEST ENVIRONMENT
# ============================================================

def show_wsgi_environment() -> None:
    print("\n=== 3. WSGI ENVIRONMENT ===")

    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/users",
        "QUERY_STRING": "active=true",
        "SERVER_NAME": "example.test",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "https",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": "18",
        "REMOTE_ADDR": "127.0.0.1",
    }

    for key, value in environ.items():
        print(f"{key:20} {value}")

    print("""
Important WSGI details:
- REQUEST_METHOD identifies the HTTP method.
- PATH_INFO identifies the URL path.
- QUERY_STRING contains the unparsed query component.
- HTTP_* keys conventionally represent HTTP request headers.
- wsgi.input can provide the request body.
- start_response establishes the response status and headers.
- The application returns bytes through an iterable.

WSGI was designed around synchronous callable execution and does not provide
native WebSocket semantics.
""")


# ============================================================
# 4. WSGI MIDDLEWARE
# ============================================================

def timing_wsgi_middleware(
    application: Callable[..., Iterable[bytes]],
) -> Callable[..., Iterable[bytes]]:
    """
    WSGI middleware wraps another WSGI application.

    Middleware can inspect or modify the request and response flow.
    """
    def wrapped(
        environ: dict[str, Any],
        start_response: Callable[[str, list[tuple[str, str]]], None],
    ) -> Iterable[bytes]:
        started = time.perf_counter()

        def wrapped_start_response(
            status: str,
            headers: list[tuple[str, str]],
            *args: Any,
        ) -> Any:
            elapsed = time.perf_counter() - started
            print(f"[WSGI middleware] response headers after {elapsed:.6f}s")
            return start_response(status, headers, *args)

        return application(environ, wrapped_start_response)

    return wrapped


def demonstrate_wsgi_middleware() -> None:
    print("\n=== 4. WSGI MIDDLEWARE ===")

    application = timing_wsgi_middleware(wsgi_application)
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/middleware",
            },
            start_response,
        )
    )

    print(captured["status"])
    print(body.decode())


# ============================================================
# 5. MINIMAL ASGI APPLICATION
# ============================================================

async def asgi_application(
    scope: dict[str, Any],
    receive: Callable[[], Any],
    send: Callable[[dict[str, Any]], Any],
) -> None:
    """
    Minimal ASGI HTTP application.

    ASGI application signature:

        async application(scope, receive, send)

    scope describes the connection/protocol.
    receive obtains incoming events.
    send emits outgoing events.

    Unlike WSGI, ASGI uses an event-driven message interface.
    """
    if scope["type"] != "http":
        return

    event = await receive()

    if event["type"] != "http.request":
        return

    path = scope.get("path", "/")
    body = f"ASGI response for {path}\n".encode("utf-8")

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"text/plain; charset=utf-8"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )

    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )


async def demonstrate_asgi() -> None:
    print("\n=== 5. ASGI CALLABLE ===")

    incoming_events = [
        {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }
    ]

    sent_events: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return incoming_events.pop(0)

    async def send(message: dict[str, Any]) -> None:
        sent_events.append(message)

    await asgi_application(
        {
            "type": "http",
            "method": "GET",
            "path": "/hello",
            "query_string": b"",
            "headers": [],
        },
        receive,
        send,
    )

    for event in sent_events:
        print(event)


# ============================================================
# 6. WSGI VERSUS ASGI STRUCTURE
# ============================================================

def compare_interfaces() -> None:
    print("\n=== 6. WSGI VERSUS ASGI ===")
    comparison = [
        ("Application shape", "callable(environ, start_response)", "async callable(scope, receive, send)"),
        ("Primary model", "synchronous", "event-driven / async-capable"),
        ("Input", "environment mapping", "events through receive()"),
        ("Output", "iterable of bytes", "events through send()"),
        ("WebSocket", "not native", "native protocol model"),
        ("Streaming", "iterable-based", "message-based"),
        ("Concurrency", "usually workers/threads/processes", "event loop plus workers/threads/processes"),
        ("Lifespan", "not a core WSGI protocol feature", "explicit ASGI lifespan scope"),
    ]

    for subject, wsgi, asgi in comparison:
        print(f"{subject:20} | WSGI: {wsgi} | ASGI: {asgi}")


# ============================================================
# 7. SYNCHRONOUS VERSUS ASYNCHRONOUS EXECUTION
# ============================================================

def synchronous_io_simulation(delay: float = 0.20) -> float:
    started = time.perf_counter()

    for _ in range(3):
        time.sleep(delay)

    return time.perf_counter() - started


async def asynchronous_io_simulation(delay: float = 0.20) -> float:
    started = time.perf_counter()

    await asyncio.gather(
        asyncio.sleep(delay),
        asyncio.sleep(delay),
        asyncio.sleep(delay),
    )

    return time.perf_counter() - started


def demonstrate_concurrency_difference() -> None:
    print("\n=== 7. SYNC VS ASYNC I/O ===")

    sync_time = synchronous_io_simulation()
    async_time = asyncio.run(asynchronous_io_simulation())

    print(f"Synchronous elapsed time: {sync_time:.3f}s")
    print(f"Asynchronous elapsed time: {async_time:.3f}s")

    print("""
The asynchronous example overlaps waiting periods.
This is especially useful for I/O-bound workloads.

It does not mean that three CPU-heavy operations automatically run in parallel.
Python async tasks normally share one event-loop thread and cooperate at await
points.
""")


# ============================================================
# 8. BLOCKING CODE INSIDE ASYNC CODE
# ============================================================

async def bad_async_operation() -> str:
    # time.sleep() blocks the event-loop thread.
    time.sleep(0.05)
    return "blocking operation completed"


async def good_async_operation() -> str:
    # asyncio.sleep() suspends this task while allowing other tasks to run.
    await asyncio.sleep(0.05)
    return "non-blocking wait completed"


async def blocking_vs_nonblocking_demo() -> None:
    print("\n=== 8. BLOCKING INSIDE ASYNC APPLICATIONS ===")

    started = time.perf_counter()
    await asyncio.gather(
        bad_async_operation(),
        bad_async_operation(),
        bad_async_operation(),
    )
    blocking_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    await asyncio.gather(
        good_async_operation(),
        good_async_operation(),
        good_async_operation(),
    )
    nonblocking_elapsed = time.perf_counter() - started

    print(f"Blocking async code: {blocking_elapsed:.3f}s")
    print(f"Non-blocking async code: {nonblocking_elapsed:.3f}s")


# ============================================================
# 9. OFFLOADING BLOCKING WORK
# ============================================================

def blocking_database_like_operation(record_id: int) -> dict[str, Any]:
    time.sleep(0.05)
    return {"id": record_id, "status": "loaded"}


async def async_wrapper_for_blocking_work(record_id: int) -> dict[str, Any]:
    """
    to_thread() prevents a blocking synchronous function from occupying the
    event-loop thread while it waits.
    """
    return await asyncio.to_thread(
        blocking_database_like_operation,
        record_id,
    )


async def demonstrate_offloading() -> None:
    print("\n=== 9. OFFLOADING BLOCKING WORK ===")

    results = await asyncio.gather(
        *(async_wrapper_for_blocking_work(i) for i in range(5))
    )

    print(results)


# ============================================================
# 10. ASGI HTTP EVENTS
# ============================================================

async def miniature_asgi_server(
    application: Callable[..., Any],
    method: str,
    path: str,
    request_body: bytes = b"",
) -> list[dict[str, Any]]:
    """
    A teaching-only ASGI server simulation.

    A real server such as Uvicorn handles sockets, HTTP parsing, connection
    management, protocol details, and event-loop integration.
    """
    input_events = [
        {
            "type": "http.request",
            "body": request_body,
            "more_body": False,
        }
    ]
    output_events: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        if input_events:
            return input_events.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        output_events.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [[b"host", b"localhost"]],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }

    await application(scope, receive, send)
    return output_events


async def demonstrate_mini_server() -> None:
    print("\n=== 10. MINIATURE ASGI SERVER ===")

    events = await miniature_asgi_server(
        asgi_application,
        "GET",
        "/mini-server",
    )

    for event in events:
        print(event)


# ============================================================
# 11. ASGI MIDDLEWARE
# ============================================================

class SimpleASGIMiddleware:
    """
    ASGI middleware is itself an ASGI application.

    It receives scope, receive, and send, then delegates to the wrapped app.
    """

    def __init__(self, application: Callable[..., Any]) -> None:
        self.application = application

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[dict[str, Any]], Any],
    ) -> None:
        started = time.perf_counter()

        async def wrapped_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    [
                        b"x-processing-time",
                        f"{time.perf_counter() - started:.6f}".encode(),
                    ]
                )
                message = {**message, "headers": headers}

            await send(message)

        await self.application(scope, receive, wrapped_send)


async def demonstrate_asgi_middleware() -> None:
    print("\n=== 11. ASGI MIDDLEWARE ===")

    application = SimpleASGIMiddleware(asgi_application)
    events = await miniature_asgi_server(
        application,
        "GET",
        "/middleware",
    )

    for event in events:
        print(event)


# ============================================================
# 12. ASGI LIFESPAN
# ============================================================

class LifespanApplication:
    """
    Demonstrates the conceptual ASGI lifespan protocol.

    Production frameworks often use lifespan to initialize and release resources
    such as database pools or clients.
    """

    def __init__(self) -> None:
        self.ready = False

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[dict[str, Any]], Any],
    ) -> None:
        if scope["type"] != "lifespan":
            return

        event = await receive()

        if event["type"] == "lifespan.startup":
            self.ready = True
            await send({"type": "lifespan.startup.complete"})

        elif event["type"] == "lifespan.shutdown":
            self.ready = False
            await send({"type": "lifespan.shutdown.complete"})


async def demonstrate_lifespan() -> None:
    print("\n=== 12. ASGI LIFESPAN ===")

    app = LifespanApplication()
    events = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]

    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return events.pop(0)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "lifespan"}

    await app(scope, receive, send)
    await app(scope, receive, send)

    print("Application ready:", app.ready)
    print("Events:", sent)


# ============================================================
# 13. WEBSOCKET MESSAGE MODEL
# ============================================================

async def websocket_echo_application(
    scope: dict[str, Any],
    receive: Callable[[], Any],
    send: Callable[[dict[str, Any]], Any],
) -> None:
    """
    Teaching example of the ASGI WebSocket event model.
    """
    if scope["type"] != "websocket":
        return

    connected = await receive()

    if connected["type"] != "websocket.connect":
        return

    await send({"type": "websocket.accept"})

    while True:
        event = await receive()

        if event["type"] == "websocket.receive":
            text = event.get("text")
            if text is None:
                await send(
                    {
                        "type": "websocket.close",
                        "code": 1003,
                    }
                )
                return

            await send(
                {
                    "type": "websocket.send",
                    "text": f"echo: {text}",
                }
            )

        elif event["type"] == "websocket.disconnect":
            return


async def demonstrate_websocket_model() -> None:
    print("\n=== 13. ASGI WEBSOCKET MODEL ===")

    events = [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "text": "hello"},
        {"type": "websocket.disconnect", "code": 1000},
    ]
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return events.pop(0)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await websocket_echo_application(
        {"type": "websocket"},
        receive,
        send,
    )

    print(sent)


# ============================================================
# 14. SIMPLE REQUEST VALIDATION
# ============================================================

@dataclass
class UserRequest:
    name: str
    age: int


def parse_user_request(raw_query: str) -> UserRequest:
    """
    Validation is application responsibility, not a substitute for the server's
    HTTP protocol validation.
    """
    parameters = urllib.parse.parse_qs(raw_query)

    name = parameters.get("name", [""])[0].strip()
    age_text = parameters.get("age", [""])[0]

    if not name:
        raise ValueError("name is required")

    if len(name) > 100:
        raise ValueError("name is too long")

    try:
        age = int(age_text)
    except ValueError as exc:
        raise ValueError("age must be an integer") from exc

    if not 0 <= age <= 150:
        raise ValueError("age must be between 0 and 150")

    return UserRequest(name=name, age=age)


def demonstrate_validation() -> None:
    print("\n=== 14. INPUT VALIDATION ===")

    valid = parse_user_request("name=Atul&age=30")
    print(valid)

    for invalid in (
        "age=30",
        "name=Atul&age=not-a-number",
        "name=Atul&age=999",
    ):
        try:
            parse_user_request(invalid)
        except ValueError as exc:
            print("Rejected:", invalid, "->", exc)


# ============================================================
# 15. JSON RESPONSE CREATION
# ============================================================

def json_response(data: Any) -> tuple[int, list[tuple[str, str]], bytes]:
    body = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]

    return 200, headers, body


def demonstrate_json_response() -> None:
    print("\n=== 15. JSON RESPONSE ===")

    status, headers, body = json_response(
        {"service": "demo", "protocol": "ASGI", "healthy": True}
    )

    print(status)
    print(headers)
    print(body.decode())


# ============================================================
# 16. ERROR HANDLING
# ============================================================

async def safe_async_operation() -> dict[str, Any]:
    try:
        await asyncio.sleep(0.01)
        raise TimeoutError("simulated downstream timeout")
    except TimeoutError as exc:
        # A production application would log structured context and translate
        # the failure into an appropriate HTTP response.
        return {
            "ok": False,
            "error": type(exc).__name__,
        }


async def demonstrate_error_handling() -> None:
    print("\n=== 16. ASYNC ERROR HANDLING ===")
    print(await safe_async_operation())


# ============================================================
# 17. TIMEOUTS
# ============================================================

async def downstream_call() -> str:
    await asyncio.sleep(0.20)
    return "downstream result"


async def demonstrate_timeout() -> None:
    print("\n=== 17. TIMEOUT CONTROL ===")

    try:
        result = await asyncio.wait_for(
            downstream_call(),
            timeout=0.05,
        )
        print(result)
    except asyncio.TimeoutError:
        print("Downstream operation timed out")


# ============================================================
# 18. CPU-BOUND WORK
# ============================================================

def cpu_bound_work(number: int) -> int:
    total = 0
    for value in range(number):
        total += value * value
    return total


async def demonstrate_cpu_bound_warning() -> None:
    print("\n=== 18. CPU-BOUND WORK ===")

    started = time.perf_counter()

    # This is intentionally synchronous. Running it directly inside the event
    # loop would occupy the event-loop thread until completion.
    result = cpu_bound_work(100_000)
    elapsed = time.perf_counter() - started

    print("Result:", result)
    print(f"Elapsed: {elapsed:.6f}s")
    print("""
For expensive CPU work, consider:
- multiple worker processes
- a process pool
- a dedicated job system
- native extensions or external compute services

Threads and async I/O primarily address concurrency for workloads that spend
time waiting. CPU saturation is a different bottleneck.
""")


# ============================================================
# 19. THREAD POOL MODEL
# ============================================================

def demonstrate_thread_pool() -> None:
    print("\n=== 19. THREAD-BASED CONCURRENCY ===")

    def task(number: int) -> str:
        time.sleep(0.05)
        return f"task {number} completed"

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(task, range(6)))

    print(results)

    print("""
A threaded worker model can serve blocking synchronous code concurrently.
The trade-off includes memory usage, scheduling overhead, synchronization
complexity, and limits on useful concurrency.
""")


# ============================================================
# 20. EVENT LOOP TASK STATES
# ============================================================

async def task_state_demo() -> None:
    print("\n=== 20. EVENT LOOP TASKS ===")

    async def worker(name: str, delay: float) -> str:
        print(name, "started")
        await asyncio.sleep(delay)
        print(name, "resumed")
        return name

    tasks = [
        asyncio.create_task(worker("A", 0.03)),
        asyncio.create_task(worker("B", 0.01)),
        asyncio.create_task(worker("C", 0.02)),
    ]

    results = await asyncio.gather(*tasks)
    print("Results:", results)


# ============================================================
# 21. PRODUCTION SERVER ARCHITECTURE
# ============================================================

def explain_server_architecture() -> None:
    print("\n=== 21. SERVER ARCHITECTURE ===")
    print("""
Typical ASGI deployment:

                Internet
                    |
             Reverse proxy
             / load balancer
                    |
             Uvicorn workers
              /    |    \\
          process process process
              \\    |    /
               ASGI app
                    |
       ----------------------------
       |             |            |
    database       cache       external APIs

Uvicorn is an ASGI server implementation. It provides the protocol/server
runtime that invokes an ASGI application.

Gunicorn is a process manager and WSGI/HTTP application server commonly used
to manage multiple worker processes. It can also manage Uvicorn worker
processes for ASGI deployments through an appropriate worker implementation.

The exact production architecture depends on traffic, protocol requirements,
deployment platform, TLS termination, observability, and application design.

A reverse proxy may handle TLS, buffering, compression, static files,
connection policies, routing, and other edge responsibilities.
""")


# ============================================================
# 22. GUNICORN WORKER CONCEPT
# ============================================================

@dataclass
class WorkerConfiguration:
    workers: int
    worker_class: str
    bind: str
    timeout_seconds: int


def validate_worker_configuration(config: WorkerConfiguration) -> None:
    if config.workers < 1:
        raise ValueError("At least one worker is required")

    if config.timeout_seconds <= 0:
        raise ValueError("Timeout must be positive")

    if not config.bind:
        raise ValueError("Bind address cannot be empty")


def demonstrate_worker_configuration() -> None:
    print("\n=== 22. WORKER CONFIGURATION ===")

    config = WorkerConfiguration(
        workers=4,
        worker_class="UvicornWorker",
        bind="127.0.0.1:8000",
        timeout_seconds=60,
    )

    validate_worker_configuration(config)
    print(config)

    print("""
Conceptual Gunicorn command for an ASGI deployment:

    gunicorn -w 4 -k uvicorn_worker.UvicornWorker module:app

The exact worker-class import path depends on the installed Uvicorn/Gunicorn
integration and package version. Production deployments should verify the
current package documentation and installed version.

The important architecture is:
Gunicorn master/process manager -> multiple worker processes -> ASGI server
runtime -> ASGI application.
""")


# ============================================================
# 23. Uvicorn CONCEPT
# ============================================================

def explain_uvicorn() -> None:
    print("\n=== 23. UVICORN ===")
    print("""
A typical development command is conceptually:

    uvicorn module:app --reload

A typical production-style command might specify:
- host
- port
- worker count
- logging configuration
- proxy-header behavior
- timeout behavior
- TLS settings when TLS is terminated there
- graceful shutdown behavior

The import target "module:app" means:
1. import the Python module
2. obtain the object named app
3. serve that ASGI application

--reload is designed for development. It watches source changes and restarts
the application. It should not be treated as an ordinary production scaling
mechanism.
""")


# ============================================================
# 24. APPLICATION FACTORY CONCEPT
# ============================================================

def create_application() -> Callable[..., Any]:
    """
    Application factory pattern.

    A factory allows configuration and resource construction to happen when
    the application is created.
    """
    async def application(
        scope: dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[dict[str, Any]], Any],
    ) -> None:
        if scope["type"] != "http":
            return

        await receive()

        body = json.dumps(
            {
                "application": "factory-created",
                "path": scope.get("path"),
            }
        ).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    return application


async def demonstrate_factory() -> None:
    print("\n=== 24. APPLICATION FACTORY ===")

    app = create_application()
    events = await miniature_asgi_server(
        app,
        "GET",
        "/factory",
    )

    print(events)


# ============================================================
# 25. BACKPRESSURE CONCEPT
# ============================================================

async def producer_consumer_demo() -> None:
    print("\n=== 25. BACKPRESSURE ===")

    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)

    async def producer() -> None:
        for item in range(6):
            await queue.put(item)
            print("produced", item)
        await queue.put(None)

    async def consumer() -> None:
        while True:
            item = await queue.get()
            try:
                if item is None:
                    return
                await asyncio.sleep(0.03)
                print("consumed", item)
            finally:
                queue.task_done()

    await asyncio.gather(producer(), consumer())

    print("""
A bounded queue limits how much work can accumulate.
Backpressure prevents a fast producer from overwhelming a slower consumer.
""")


# ============================================================
# 26. CONNECTION LIMIT SIMULATION
# ============================================================

class ConnectionLimiter:
    def __init__(self, maximum_connections: int) -> None:
        if maximum_connections < 1:
            raise ValueError("maximum_connections must be positive")
        self.semaphore = asyncio.Semaphore(maximum_connections)

    async def run(self, connection_id: int) -> str:
        async with self.semaphore:
            await asyncio.sleep(0.02)
            return f"connection {connection_id} served"


async def demonstrate_connection_limit() -> None:
    print("\n=== 26. CONNECTION LIMIT ===")

    limiter = ConnectionLimiter(2)

    results = await asyncio.gather(
        *(limiter.run(i) for i in range(6))
    )

    print(results)


# ============================================================
# 27. SECURITY BASICS
# ============================================================

def explain_security() -> None:
    print("\n=== 27. SECURITY ===")
    print("""
WSGI and ASGI are interfaces, not complete security systems.

Important production controls include:

1. Validate input.
2. Limit request body sizes.
3. Apply authentication and authorization correctly.
4. Use TLS at an appropriate network boundary.
5. Configure trusted proxy behavior carefully.
6. Avoid trusting arbitrary forwarded headers.
7. Set sensible connection and request timeouts.
8. Avoid leaking stack traces to clients.
9. Keep dependencies patched.
10. Protect secrets using environment or secret-management mechanisms.
11. Apply rate limits where appropriate.
12. Handle WebSocket authorization separately from HTTP assumptions.
13. Prevent resource exhaustion through bounded queues and concurrency limits.
14. Log security-relevant events without exposing secrets or credentials.

A server's ability to receive a request does not mean the application should
trust every value in that request.
""")


# ============================================================
# 28. OBSERVABILITY
# ============================================================

@dataclass
class RequestMetric:
    path: str
    elapsed_seconds: float
    status_code: int


def calculate_latency_statistics(metrics: list[RequestMetric]) -> dict[str, float]:
    if not metrics:
        return {}

    latencies = [metric.elapsed_seconds for metric in metrics]

    return {
        "count": float(len(latencies)),
        "mean_ms": statistics.mean(latencies) * 1000,
        "median_ms": statistics.median(latencies) * 1000,
        "max_ms": max(latencies) * 1000,
    }


def demonstrate_observability() -> None:
    print("\n=== 28. OBSERVABILITY ===")

    metrics = [
        RequestMetric("/", 0.010, 200),
        RequestMetric("/users", 0.021, 200),
        RequestMetric("/users", 0.040, 500),
        RequestMetric("/health", 0.003, 200),
    ]

    print(calculate_latency_statistics(metrics))

    print("""
Useful production signals include:
- request rate
- error rate
- latency distributions
- active connections
- worker restarts
- CPU usage
- memory usage
- event-loop lag
- downstream dependency latency
- database pool utilization

Averages alone can hide slow requests. Percentiles such as p95 and p99 are
often more informative for tail latency.
""")


# ============================================================
# 29. GRACEFUL SHUTDOWN
# ============================================================

class ShutdownController:
    def __init__(self) -> None:
        self.accepting_requests = True
        self.resources_closed = False

    async def shutdown(self) -> None:
        self.accepting_requests = False

        # Give in-flight work a chance to finish in a real application.
        await asyncio.sleep(0.01)

        self.resources_closed = True


async def demonstrate_graceful_shutdown() -> None:
    print("\n=== 29. GRACEFUL SHUTDOWN ===")

    controller = ShutdownController()
    await controller.shutdown()

    print("Accepting requests:", controller.accepting_requests)
    print("Resources closed:", controller.resources_closed)


# ============================================================
# 30. EDGE CASES
# ============================================================

def demonstrate_edge_cases() -> None:
    print("\n=== 30. EDGE CASES ===")

    edge_cases = [
        "",
        "name=Atul&age=0",
        "name=Atul&age=150",
        "name=%20&age=30",
        "name=Atul&age=1.5",
        "name=Atul&age=-1",
    ]

    for value in edge_cases:
        try:
            print(value, "=>", parse_user_request(value))
        except ValueError as exc:
            print(value, "=> rejected:", exc)


# ============================================================
# 31. SIMPLE ROUTER
# ============================================================

class ASGIRouter:
    """
    A small teaching router.

    Real frameworks provide richer routing features, parameter conversion,
    middleware integration, dependency injection, exception handling, and
    content negotiation.
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Callable[..., Any]] = {}

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
    ) -> None:
        self.routes[(method.upper(), path)] = handler

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[dict[str, Any]], Any],
    ) -> None:
        if scope["type"] != "http":
            return

        route = self.routes.get(
            (
                scope.get("method", "GET").upper(),
                scope.get("path", "/"),
            )
        )

        if route is None:
            body = b"Not Found"
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [[b"content-type", b"text/plain"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )
            return

        await route(scope, receive, send)


async def hello_handler(
    scope: dict[str, Any],
    receive: Callable[[], Any],
    send: Callable[[dict[str, Any]], Any],
) -> None:
    await receive()
    body = b"Hello from router"

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def demonstrate_router() -> None:
    print("\n=== 31. SIMPLE ASGI ROUTER ===")

    router = ASGIRouter()
    router.add_route("GET", "/hello", hello_handler)

    print(await miniature_asgi_server(router, "GET", "/hello"))
    print(await miniature_asgi_server(router, "GET", "/missing"))


# ============================================================
# 32. SERVER CAPACITY MODEL
# ============================================================

@dataclass
class CapacityScenario:
    workers: int
    concurrent_tasks_per_worker: int

    @property
    def theoretical_concurrency_slots(self) -> int:
        return self.workers * self.concurrent_tasks_per_worker


def demonstrate_capacity_model() -> None:
    print("\n=== 32. CAPACITY MODEL ===")

    scenarios = [
        CapacityScenario(1, 100),
        CapacityScenario(4, 100),
        CapacityScenario(8, 50),
    ]

    for scenario in scenarios:
        print(
            scenario,
            "slots=",
            scenario.theoretical_concurrency_slots,
        )

    print("""
This is only a conceptual model. Real capacity depends on:
- CPU
- memory
- network bandwidth
- connection counts
- application latency
- database capacity
- downstream services
- kernel/network limits
- serialization costs
- workload mix
- lock contention
- garbage collection
- protocol behavior

A larger worker count is not automatically faster.
""")


# ============================================================
# 33. PERFORMANCE PRINCIPLES
# ============================================================

def explain_performance() -> None:
    print("\n=== 33. PERFORMANCE PRINCIPLES ===")
    print("""
For an ASGI application:

I/O-bound workload:
    async I/O can increase useful concurrency by avoiding idle blocking.

CPU-bound workload:
    async syntax alone does not create CPU parallelism.

Blocking dependency:
    use a compatible async library where possible, or isolate blocking work
    in threads/processes when appropriate.

Worker count:
    more workers can use additional CPU cores but consume additional memory.

Keep-alive:
    reusing connections can reduce connection establishment overhead.

Serialization:
    JSON encoding, large payloads, and compression consume CPU.

Database:
    database connection pools must be sized together with application
    concurrency. Hundreds of application tasks do not imply hundreds of
    database connections.

Caching:
    caching can reduce repeated downstream work but introduces invalidation
    and consistency concerns.

Measure before changing architecture.
""")


# ============================================================
# 34. COMMON MISTAKES
# ============================================================

def explain_common_mistakes() -> None:
    print("\n=== 34. COMMON MISTAKES ===")
    mistakes = [
        "Using blocking time.sleep() in an async request handler.",
        "Assuming async automatically provides CPU parallelism.",
        "Using development auto-reload as a production process manager.",
        "Creating unlimited background tasks.",
        "Ignoring request and connection timeouts.",
        "Creating a database connection for every request without pooling.",
        "Trusting forwarded headers without configuring trusted proxies.",
        "Running too many workers for available memory.",
        "Using synchronous libraries heavily inside the event loop.",
        "Ignoring graceful shutdown and resource cleanup.",
        "Treating WSGI and ASGI as interchangeable callable signatures.",
        "Assuming a reverse proxy eliminates the need for application security.",
    ]

    for number, mistake in enumerate(mistakes, 1):
        print(f"{number}. {mistake}")


# ============================================================
# 35. WSGI ADAPTER CONCEPT
# ============================================================

async def call_wsgi_from_async_context(
    wsgi_app: Callable[..., Iterable[bytes]],
    environ: dict[str, Any],
) -> tuple[str, list[tuple[str, str]], bytes]:
    """
    Conceptual WSGI-to-async adaptation.

    The WSGI callable itself remains synchronous. Running it in a thread can
    keep it from blocking the event-loop thread.

    Real WSGI/ASGI adapters must correctly handle the full protocol semantics,
    request body, headers, errors, streaming, and lifecycle.
    """
    loop = asyncio.get_running_loop()

    def execute_wsgi() -> tuple[str, list[tuple[str, str]], bytes]:
        captured: dict[str, Any] = {}

        def start_response(
            status: str,
            headers: list[tuple[str, str]],
        ) -> None:
            captured["status"] = status
            captured["headers"] = headers

        body = b"".join(wsgi_app(environ, start_response))

        return (
            captured["status"],
            captured["headers"],
            body,
        )

    return await loop.run_in_executor(None, execute_wsgi)


async def demonstrate_wsgi_adapter_concept() -> None:
    print("\n=== 35. WSGI ADAPTATION CONCEPT ===")

    result = await call_wsgi_from_async_context(
        wsgi_application,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/adapted",
        },
    )

    print(result)


# ============================================================
# 36. COMPLETE EDUCATIONAL ASGI SERVICE
# ============================================================

class EducationalASGIService:
    """
    A compact service combining routing, validation, JSON responses,
    middleware-like behavior, and error handling.
    """

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[dict[str, Any]], Any],
    ) -> None:
        if scope["type"] != "http":
            return

        try:
            request_event = await receive()

            if request_event["type"] != "http.request":
                raise ValueError("Expected HTTP request")

            method = scope.get("method", "GET")
            path = scope.get("path", "/")

            if method == "GET" and path == "/health":
                status, headers, body = json_response(
                    {"status": "ok"}
                )

            elif method == "GET" and path == "/users":
                query_string = scope.get("query_string", b"").decode()
                user = parse_user_request(query_string)
                status, headers, body = json_response(
                    {
                        "name": user.name,
                        "age": user.age,
                    }
                )

            else:
                status, headers, body = (
                    404,
                    [("Content-Type", "text/plain; charset=utf-8")],
                    b"Not Found",
                )

            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [
                        [key.lower().encode(), value.encode()]
                        for key, value in headers
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )

        except ValueError as exc:
            body = json.dumps(
                {"error": str(exc)}
            ).encode()

            await send(
                {
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )

        except Exception:
            # Production applications should log the exception with context
            # while returning a generic response to avoid information leakage.
            body = b'{"error":"internal server error"}'

            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )


async def demonstrate_complete_service() -> None:
    print("\n=== 36. COMPLETE EDUCATIONAL ASGI SERVICE ===")

    app = EducationalASGIService()

    health = await miniature_asgi_server(
        app,
        "GET",
        "/health",
    )

    print("Health:", health)

    user_scope_events: list[dict[str, Any]] = []
    input_events = [
        {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }
    ]

    async def receive() -> dict[str, Any]:
        return input_events.pop(0)

    async def send(message: dict[str, Any]) -> None:
        user_scope_events.append(message)

    await app(
        {
            "type": "http",
            "method": "GET",
            "path": "/users",
            "query_string": b"name=Atul&age=30",
        },
        receive,
        send,
    )

    print("User:", user_scope_events)


# ============================================================
# 37. PERFORMANCE MEASUREMENT
# ============================================================

async def measured_async_task(delay: float) -> float:
    started = time.perf_counter()
    await asyncio.sleep(delay)
    return time.perf_counter() - started


async def demonstrate_measurement() -> None:
    print("\n=== 37. PERFORMANCE MEASUREMENT ===")

    delays = [0.01, 0.02, 0.03, 0.01, 0.02]

    measurements = await asyncio.gather(
        *(measured_async_task(delay) for delay in delays)
    )

    print(
        "mean_ms=",
        statistics.mean(measurements) * 1000,
        "max_ms=",
        max(measurements) * 1000,
    )


# ============================================================
# 38. FINAL ARCHITECTURAL CHECKLIST
# ============================================================

def architecture_checklist() -> None:
    print("\n=== 38. ARCHITECTURAL CHECKLIST ===")
    checklist = [
        "Choose WSGI for traditional synchronous Python web workloads.",
        "Choose ASGI when asynchronous execution or WebSockets are required.",
        "Identify blocking libraries before adopting an async architecture.",
        "Use Uvicorn as an ASGI server runtime.",
        "Use a process manager such as Gunicorn where its worker-management model fits.",
        "Keep development reload behavior separate from production process management.",
        "Use timeouts and bounded concurrency.",
        "Size database pools deliberately.",
        "Use graceful startup and shutdown.",
        "Instrument latency and errors.",
        "Configure proxies and forwarded headers securely.",
        "Test under realistic concurrency before selecting worker counts.",
    ]

    for item in checklist:
        print("[ ]", item)


# ============================================================
# 39. MAIN
# ============================================================

async def run_async_demos() -> None:
    await demonstrate_asgi()
    await demonstrate_concurrency_difference()
    await blocking_vs_nonblocking_demo()
    await demonstrate_offloading()
    await demonstrate_mini_server()
    await demonstrate_asgi_middleware()
    await demonstrate_lifespan()
    await demonstrate_websocket_model()
    await demonstrate_error_handling()
    await demonstrate_timeout()
    await demonstrate_cpu_bound_warning()
    await task_state_demo()
    await demonstrate_factory()
    await producer_consumer_demo()
    await demonstrate_connection_limit()
    await demonstrate_wsgi_adapter_concept()
    await demonstrate_complete_service()
    await demonstrate_measurement()
    await demonstrate_router()


def main() -> None:
    print("=" * 72)
    print("WSGI AND ASGI: PYTHON TECHNICAL STUDY")
    print("=" * 72)

    explain_basic_architecture()
    demonstrate_wsgi()
    show_wsgi_environment()
    demonstrate_wsgi_middleware()
    compare_interfaces()
    explain_server_architecture()
    demonstrate_worker_configuration()
    explain_uvicorn()
    demonstrate_validation()
    demonstrate_json_response()
    demonstrate_thread_pool()
    explain_security()
    demonstrate_observability()
    demonstrate_graceful_shutdown()
    demonstrate_edge_cases()
    demonstrate_capacity_model()
    explain_performance()
    explain_common_mistakes()
    architecture_checklist()

    asyncio.run(run_async_demos())

    print("\n=== STUDY COMPLETE ===")


if __name__ == "__main__":
    main()
