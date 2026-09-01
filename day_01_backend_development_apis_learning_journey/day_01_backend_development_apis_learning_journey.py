"""
===============================================================================
BACKEND DEVELOPMENT FUNDAMENTALS
===============================================================================

A comprehensive, executable learning module covering:

1. What backend development is
2. Frontend vs backend
3. Responsibilities of a backend
4. Server-side programming
5. Backend architecture
6. Request processing
7. Client-server architecture
8. HTTP fundamentals
9. URLs, methods, headers, body and status codes
10. Servers, ports and sockets
11. Static vs dynamic content
12. APIs and endpoints
13. Application logic
14. Databases and persistence
15. Authentication and authorization concepts
16. Validation and error handling
17. Middleware
18. Logging and observability
19. Synchronous vs asynchronous processing
20. Stateless vs stateful systems
21. Monoliths, modular monoliths and microservices
22. Reverse proxies and load balancers
23. Caching
24. Queues and background processing
25. Scalability and reliability
26. Security fundamentals
27. Request lifecycle simulation
28. A mini backend server using Python's standard library
29. Exercises and quizzes
30. Automatic generation of Markdown learning notes

Required tools:
- Python 3
- VS Code
- Browser
- Terminal

No third-party Python packages are required.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import threading
import time
import uuid
import hashlib
import secrets
import os
import sys


# =============================================================================
# SECTION 0: BASIC UTILITIES
# =============================================================================

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"


def title(text):
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)


def section(text):
    print("\n" + "-" * 80)
    print(text)
    print("-" * 80)


def explain(concept, explanation):
    print(f"\n{BOLD}{CYAN}{concept}{RESET}")
    print(explanation)


def pause():
    input("\nPress Enter to continue...")


def quiz(question, options, correct):
    print("\n" + BOLD + question + RESET)

    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")

    try:
        answer = int(input("Your answer: "))
        if answer == correct:
            print(GREEN + "Correct!" + RESET)
            return True
        else:
            print(RED + f"Incorrect. Correct answer: {correct}" + RESET)
            return False
    except ValueError:
        print(RED + "Please enter a number." + RESET)
        return False


# =============================================================================
# SECTION 1: WHAT IS BACKEND DEVELOPMENT?
# =============================================================================

def lesson_what_is_backend():
    title("1. WHAT IS BACKEND DEVELOPMENT?")

    explain(
        "Definition",
        """
Backend development is the development of the server-side portion of an
application.

The backend receives requests from clients, performs processing, applies
business rules, interacts with databases and external services, handles
authentication and authorization, and sends responses back to clients.

A simplified model is:

        Client
           |
           | HTTP Request
           v
        Backend
           |
      +----+----+
      |         |
      v         v
   Database   External APIs
      |
      v
    Data
      |
      +-----------> Backend
                       |
                       | HTTP Response
                       v
                     Client
"""
    )

    explain(
        "Backend is not simply 'the database'",
        """
A common beginner misconception is:

Backend = Database

This is incorrect.

A database stores and retrieves information.

The backend is the application layer responsible for deciding:

- what data should be retrieved
- who is allowed to retrieve it
- what calculations should occur
- what business rules apply
- how data should be validated
- how errors should be handled
- how external services should be contacted
- what response should be returned

The database is one component of a backend system.
"""
    )

    explain(
        "Example",
        """
Suppose you build an online shopping application.

The frontend may display:

    Product: Laptop
    Price: ₹75,000
    Button: Buy Now

When the user clicks Buy Now:

1. Browser sends a request.
2. Backend receives the request.
3. Backend identifies the user.
4. Backend verifies the product.
5. Backend checks inventory.
6. Backend calculates price.
7. Backend applies discounts.
8. Backend creates an order.
9. Backend updates inventory.
10. Backend may contact a payment service.
11. Backend returns the result.

That entire process is backend development.
"""
    )


# =============================================================================
# SECTION 2: FRONTEND VS BACKEND
# =============================================================================

def lesson_frontend_vs_backend():
    title("2. FRONTEND VS BACKEND")

    comparison = [
        ("Runs primarily", "Browser/device", "Server/infrastructure"),
        ("Primary purpose", "User interface", "Business logic/data processing"),
        ("Typical technologies", "HTML, CSS, JavaScript", "Python, Java, Go, Node.js, C#, etc."),
        ("Database access", "Usually indirect", "Usually direct through application layer"),
        ("Visibility", "Much of code is delivered to client", "Server implementation is normally hidden"),
        ("Authentication logic", "UI/session handling", "Actual identity verification and authorization"),
        ("Business rules", "May display rules", "Authoritative rules should live server-side"),
    ]

    print(f"{'Area':<25} {'Frontend':<35} {'Backend':<35}")
    print("-" * 95)

    for row in comparison:
        print(f"{row[0]:<25} {row[1]:<35} {row[2]:<35}")

    explain(
        "Important distinction",
        """
Frontend asks:

    "How should this information be presented?"

Backend asks:

    "What information should this user be allowed to receive,
     how should it be processed, and what should happen next?"

A frontend can request:

    GET /users/42

But the backend decides whether the requesting user is authorized
to access user 42.
"""
    )

    explain(
        "Why backend security matters",
        """
Never trust the frontend.

A malicious user can modify browser code, manipulate requests, use
developer tools, write their own HTTP client, or directly call your API.

Therefore:

Frontend validation = user experience

Backend validation = security and correctness
"""
    )


# =============================================================================
# SECTION 3: CLIENT-SERVER MODEL
# =============================================================================

def lesson_client_server():
    title("3. CLIENT-SERVER ARCHITECTURE")

    explain(
        "Client",
        """
A client is a program that initiates communication.

Examples:

- Web browser
- Mobile application
- Desktop application
- Command-line program
- Another backend service
- IoT device
"""
    )

    explain(
        "Server",
        """
A server is a program or system that listens for requests and provides
services or resources.

The word 'server' can refer to:

1. Hardware
2. Operating system
3. Network machine
4. Application process
5. A logical service

In backend development, we commonly mean the server-side application
that handles requests.
"""
    )

    explain(
        "Basic communication",
        """
Client:

    "Please give me the profile of user 42."

Server:

    "The user's name is Atul and the account is active."

Technically, this communication commonly happens through HTTP over TCP/IP.
HTTPS adds TLS encryption.
"""
    )


# =============================================================================
# SECTION 4: REQUEST-RESPONSE CYCLE
# =============================================================================

@dataclass
class Request:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None


@dataclass
class Response:
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None


def lesson_request_response():
    title("4. REQUEST-RESPONSE CYCLE")

    explain(
        "The complete conceptual lifecycle",
        """
1. User performs an action.
2. Frontend creates a request.
3. DNS may resolve a hostname.
4. Network connection is established.
5. Request reaches the server.
6. Reverse proxy/load balancer may receive it.
7. Request is routed to the backend.
8. Middleware processes it.
9. Authentication may occur.
10. Authorization may occur.
11. Input validation occurs.
12. Application logic executes.
13. Database/external services may be contacted.
14. Response is generated.
15. Response travels back to client.
16. Frontend processes the response.
17. UI is updated.
"""
    )

    request = Request(
        method="GET",
        url="https://example.com/api/users/42",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer example-token",
        },
    )

    print("\nExample request:")
    print(request)

    response = Response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body={
            "id": 42,
            "name": "Example User",
        },
    )

    print("\nExample response:")
    print(response)

    quiz(
        "Which component normally contains the authoritative business logic?",
        [
            "Only the browser",
            "Backend application",
            "Keyboard",
            "Monitor",
        ],
        2,
    )


# =============================================================================
# SECTION 5: HTTP FUNDAMENTALS
# =============================================================================

def lesson_http():
    title("5. HTTP FUNDAMENTALS")

    explain(
        "HTTP",
        """
HTTP stands for Hypertext Transfer Protocol.

It defines a standard way for clients and servers to communicate.

An HTTP request can contain:

- Method
- URL/path
- Query parameters
- Headers
- Body

An HTTP response contains:

- Status code
- Headers
- Body
"""
    )

    methods = {
        "GET": "Retrieve a resource",
        "POST": "Create a resource or trigger an operation",
        "PUT": "Replace/update a resource",
        "PATCH": "Partially modify a resource",
        "DELETE": "Delete a resource",
        "HEAD": "Retrieve headers without normal response body",
        "OPTIONS": "Discover supported communication options",
    }

    print("\nHTTP methods:")
    for method, meaning in methods.items():
        print(f"{method:<10} -> {meaning}")

    status_codes = {
        200: "OK",
        201: "Created",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found/temporary redirect",
        400: "Bad Request",
        401: "Unauthorized / authentication required",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Content",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }

    print("\nCommon status codes:")
    for code, meaning in status_codes.items():
        print(f"{code:<5} -> {meaning}")

    explain(
        "401 vs 403",
        """
401 means the client has not successfully authenticated.

403 means the server understands who the client is but refuses
the requested action.

Example:

Unauthenticated request:
    401

Authenticated normal user attempting administrator operation:
    403
"""
    )


# =============================================================================
# SECTION 6: URL, PATH AND QUERY PARAMETERS
# =============================================================================

def lesson_urls():
    title("6. URLS, PATHS AND QUERY PARAMETERS")

    url = "https://api.example.com/products/123?category=laptop&sort=price"

    parsed = urlparse(url)

    print("Full URL:")
    print(url)

    print("\nScheme:")
    print(parsed.scheme)

    print("\nHost:")
    print(parsed.netloc)

    print("\nPath:")
    print(parsed.path)

    print("\nQuery string:")
    print(parsed.query)

    print("\nParsed query parameters:")
    print(parse_qs(parsed.query))

    explain(
        "Path parameter",
        """
/products/123

Here 123 identifies a specific resource.
"""
    )

    explain(
        "Query parameter",
        """
/products?category=laptop&sort=price

Query parameters commonly control filtering, sorting, searching,
pagination and optional behavior.
"""
    )


# =============================================================================
# SECTION 7: HEADERS AND BODY
# =============================================================================

def lesson_headers_body():
    title("7. HEADERS AND REQUEST BODIES")

    request = Request(
        method="POST",
        url="/api/users",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ExampleBrowser/1.0",
        },
        body={
            "name": "Alice",
            "email": "alice@example.com",
        },
    )

    print(json.dumps({
        "method": request.method,
        "url": request.url,
        "headers": request.headers,
        "body": request.body,
    }, indent=2))

    explain(
        "Headers",
        """
Headers carry metadata.

Examples:

Content-Type:
    Describes the request/response body format.

Authorization:
    Carries authentication credentials/tokens.

Accept:
    Tells the server which response formats the client prefers.

User-Agent:
    Identifies the client software.

Cache-Control:
    Controls caching behavior.
"""
    )

    explain(
        "Body",
        """
The body carries data.

Example JSON:

{
    "username": "alice",
    "password": "example"
}

The body is common with POST, PUT and PATCH requests.
"""


# =============================================================================
# SECTION 8: SERVER-SIDE PROGRAMMING
# =============================================================================

def lesson_server_side_programming():
    title("8. SERVER-SIDE PROGRAMMING")

    explain(
        "What happens server-side?",
        """
Server-side programming means code executes on infrastructure controlled
by the application owner rather than primarily inside the user's browser.

Typical responsibilities include:

- Routing
- Authentication
- Authorization
- Validation
- Business logic
- Database access
- File processing
- External API calls
- Background jobs
- Logging
- Error handling
"""
    )

    explain(
        "Example business rule",
        """
Suppose:

A customer has ₹1,000 in their account.

They attempt to purchase an item costing ₹1,500.

The backend must determine:

    balance >= price ?

If false:

    reject transaction

The browser should never be the final authority for this rule.
"""
    )


# =============================================================================
# SECTION 9: BACKEND ARCHITECTURE
# =============================================================================

def lesson_architecture():
    title("9. BACKEND ARCHITECTURE")

    explain(
        "Layered architecture",
        """
A common conceptual structure is:

            Client
               |
               v
        +--------------+
        |   Routing    |
        +--------------+
               |
               v
        +--------------+
        | Controllers  |
        +--------------+
               |
               v
        +--------------+
        |   Services   |
        +--------------+
               |
               v
        +--------------+
        | Repositories |
        +--------------+
               |
               v
        +--------------+
        |   Database   |
        +--------------+

Additional cross-cutting concerns:

- Authentication
- Authorization
- Validation
- Logging
- Error handling
- Configuration
- Caching
"""
    )

    explain(
        "Presentation/API layer",
        """
Responsible for communication with clients.

Typical responsibilities:

- Parse requests
- Match routes
- Validate basic request structure
- Call application services
- Format responses
"""
    )

    explain(
        "Service layer",
        """
Contains business logic.

Example:

    calculate_order_total()
    create_order()
    cancel_order()
    apply_discount()
"""
    )

    explain(
        "Repository/data-access layer",
        """
Responsible for persistence operations.

Examples:

    get_user()
    save_user()
    delete_order()
    find_products()
"""
    )

    explain(
        "Why layers exist",
        """
The goal is separation of concerns.

If everything is placed inside one giant request handler:

    request -> 500 lines of code

the application becomes difficult to:

- test
- maintain
- debug
- modify
- scale organizationally
"""
    )


# =============================================================================
# SECTION 10: ROUTING
# =============================================================================

class SimpleRouter:
    def __init__(self):
        self.routes = {}

    def add(self, method, path, handler):
        self.routes[(method.upper(), path)] = handler

    def resolve(self, method, path):
        return self.routes.get((method.upper(), path))


def lesson_routing():
    title("10. ROUTING")

    explain(
        "Routing",
        """
Routing determines which application code should handle an incoming request.

Example:

GET /users
    -> list_users()

GET /users/42
    -> get_user(42)

POST /users
    -> create_user()

DELETE /users/42
    -> delete_user(42)
"""
    )

    router = SimpleRouter()

    router.add("GET", "/users", lambda: "list_users")
    router.add("POST", "/users", lambda: "create_user")

    print("GET /users ->", router.resolve("GET", "/users")())
    print("POST /users ->", router.resolve("POST", "/users")())
    print("GET /missing ->", router.resolve("GET", "/missing"))


# =============================================================================
# SECTION 11: DATABASE CONCEPT
# =============================================================================

def lesson_database():
    title("11. BACKEND AND DATABASES")

    explain(
        "Why databases exist",
        """
Applications need persistence.

Without persistence:

    Program starts
       |
       v
    Data exists in memory
       |
       v
    Program stops
       |
       v
    Data disappears

A database allows information to survive application restarts.
"""
    )

    explain(
        "Database categories",
        """
Relational databases:

- PostgreSQL
- MySQL
- MariaDB
- SQL Server
- Oracle Database

NoSQL categories:

- Document databases
- Key-value stores
- Wide-column databases
- Graph databases

Different databases solve different problems.
"""
    )

    explain(
        "Typical request",
        """
GET /users/42

Backend:

    1. Parse ID = 42
    2. Validate ID
    3. Authorize request
    4. Query database
    5. Transform database result
    6. Return JSON response
"""
    )


# =============================================================================
# SECTION 12: IN-MEMORY DATABASE SIMULATION
# =============================================================================

class InMemoryUserRepository:
    def __init__(self):
        self.users = {
            1: {
                "id": 1,
                "name": "Alice",
                "email": "alice@example.com",
            },
            2: {
                "id": 2,
                "name": "Bob",
                "email": "bob@example.com",
            },
        }

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def create(self, name, email):
        new_id = max(self.users.keys()) + 1 if self.users else 1

        user = {
            "id": new_id,
            "name": name,
            "email": email,
        }

        self.users[new_id] = user

        return user


class UserService:
    def __init__(self, repository):
        self.repository = repository

    def get_user(self, user_id):
        if user_id <= 0:
            raise ValueError("User ID must be positive")

        return self.repository.get_by_id(user_id)

    def create_user(self, name, email):
        if not name:
            raise ValueError("Name is required")

        if "@" not in email:
            raise ValueError("Invalid email")

        return self.repository.create(name, email)


def lesson_application_layers():
    title("12. APPLICATION LAYER SIMULATION")

    repository = InMemoryUserRepository()
    service = UserService(repository)

    print("Existing user:")
    print(service.get_user(1))

    print("\nCreating user:")
    print(service.create_user("Charlie", "charlie@example.com"))

    print("\nAll stored users:")
    print(repository.users)


# =============================================================================
# SECTION 13: VALIDATION
# =============================================================================

def lesson_validation():
    title("13. INPUT VALIDATION")

    explain(
        "Why validation matters",
        """
Clients are untrusted.

A client might send:

{
    "age": -500
}

or:

{
    "email": "not-an-email"
}

or:

{
    "amount": "DROP TABLE users"
}

Validation ensures data satisfies expected constraints.
"""
    )

    def validate_user(data):
        errors = {}

        if not isinstance(data.get("name"), str):
            errors["name"] = "Name must be a string"

        if not data.get("name"):
            errors["name"] = "Name is required"

        email = data.get("email", "")

        if "@" not in email:
            errors["email"] = "Invalid email"

        return errors

    examples = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "", "email": "wrong"},
        {"name": 123, "email": "wrong"},
    ]

    for example in examples:
        print("\nInput:", example)
        print("Errors:", validate_user(example))


# =============================================================================
# SECTION 14: AUTHENTICATION AND AUTHORIZATION
# =============================================================================

def lesson_auth():
    title("14. AUTHENTICATION VS AUTHORIZATION")

    explain(
        "Authentication",
        """
Authentication answers:

    WHO are you?

Examples:

- Password
- Session
- API key
- JWT
- OAuth
- Passkey
"""
    )

    explain(
        "Authorization",
        """
Authorization answers:

    WHAT are you allowed to do?

Example:

Alice is authenticated.

Alice attempts:

    DELETE /users/42

The backend asks:

    Does Alice have permission to delete user 42?

If not:

    403 Forbidden
"""
    )

    explain(
        "Critical principle",
        """
Authentication does not automatically mean authorization.

Being logged in does not mean being allowed to perform every operation.
"""
    )


# =============================================================================
# SECTION 15: PASSWORD HASHING CONCEPT
# =============================================================================

def lesson_password_hashing():
    title("15. PASSWORD STORAGE")

    explain(
        "Never store plaintext passwords",
        """
Bad:

    password = "MyPassword123"

Database:

    MyPassword123

If the database is compromised, passwords are immediately exposed.
"""
    )

    explain(
        "Hashing",
        """
A password should be transformed using a password hashing algorithm.

Conceptually:

    password
       |
       v
    password-hashing-function
       |
       v
    stored hash

During login:

    entered password
          |
          v
    verify against stored hash
"""
    )

    # Educational demonstration only, not a production password hashing system.
    password = "example-password"

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        200_000,
    )

    print("Educational password-hashing demonstration:")
    print("Salt:", salt.hex())
    print("Hash:", digest.hex())

    explain(
        "Production note",
        """
Real applications should use a dedicated password hashing library and a
modern password hashing scheme such as Argon2id, scrypt or bcrypt, with
appropriate parameters.

Do not implement password security from scratch merely because a simple
hash function works in a demonstration.
"""
    )


# =============================================================================
# SECTION 16: MIDDLEWARE
# =============================================================================

def lesson_middleware():
    title("16. MIDDLEWARE")

    explain(
        "Middleware",
        """
Middleware is logic that executes around request processing.

Conceptually:

Request
   |
   v
Middleware A
   |
   v
Middleware B
   |
   v
Route Handler
   |
   v
Middleware B
   |
   v
Middleware A
   |
   v
Response
"""
    )

    explain(
        "Common middleware responsibilities",
        """
- Logging
- Authentication
- CORS handling
- Request IDs
- Compression
- Rate limiting
- Security headers
- Metrics
"""
    )


# =============================================================================
# SECTION 17: ERROR HANDLING
# =============================================================================

def lesson_error_handling():
    title("17. ERROR HANDLING")

    explain(
        "Two broad classes",
        """
Client errors:

    400
    401
    403
    404
    409
    422
    429

Server errors:

    500
    502
    503
    504
"""
    )

    explain(
        "Do not leak internal details",
        """
Bad response:

{
    "error": "PostgreSQL connection failed at 10.0.0.17 using password xyz"
}

Better:

{
    "error": "Internal server error",
    "request_id": "abc-123"
}

Detailed information should be available in protected server logs,
not exposed unnecessarily to clients.
"""
    )


# =============================================================================
# SECTION 18: LOGGING
# =============================================================================

def lesson_logging():
    title("18. LOGGING")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    logger = logging.getLogger("backend")

    request_id = str(uuid.uuid4())

    logger.info(
        "request_id=%s method=%s path=%s",
        request_id,
        "GET",
        "/users/42",
    )

    logger.info(
        "request_id=%s status=%s",
        request_id,
        200,
    )

    explain(
        "Why request IDs matter",
        """
A request may travel through:

Browser
  ->
Load Balancer
  ->
Backend
  ->
Database

A request ID allows logs from the same operation to be correlated.
"""
    )


# =============================================================================
# SECTION 19: STATELESS VS STATEFUL
# =============================================================================

def lesson_state():
    title("19. STATELESS VS STATEFUL BACKENDS")

    explain(
        "Stateless",
        """
A stateless backend does not depend on local memory from a previous request
to understand the current request.

Example:

Request 1:
    GET /profile
    Authorization: token

Request 2:
    GET /orders
    Authorization: token

Each request contains enough information for the server to process it,
possibly with shared external state such as a database or distributed cache.
"""
    )

    explain(
        "Stateful",
        """
A stateful server keeps client-specific state in local server memory.

This can create scaling complications.

Suppose:

Client
   |
Load Balancer
   |
+-------+-------+
|               |
Server A      Server B

If session data exists only on Server A, a later request sent to Server B
may not find it.

Solutions include:

- Shared session storage
- Distributed cache
- Database-backed sessions
- Carefully designed sticky sessions
"""
    )


# =============================================================================
# SECTION 20: SYNCHRONOUS VS ASYNCHRONOUS
# =============================================================================

def lesson_sync_async():
    title("20. SYNCHRONOUS VS ASYNCHRONOUS PROCESSING")

    explain(
        "Synchronous",
        """
The caller waits for the operation to finish.

Example:

Client
  |
  | create report
  v
Backend
  |
  | generate huge report
  | ...
  | ...
  v
Response

This may be inappropriate for long-running work.
"""
    )

    explain(
        "Asynchronous/background processing",
        """
Client
  |
  | request report
  v
Backend
  |
  | create job
  v
Queue
  |
  v
Worker
  |
  | generate report
  v
Storage

The client can receive:

    202 Accepted

and later retrieve the result.
"""
    )


# =============================================================================
# SECTION 21: CACHING
# =============================================================================

def lesson_caching():
    title("21. CACHING")

    explain(
        "Why caching exists",
        """
Suppose:

    Database query = 200 ms

and the same data is requested 10,000 times.

A cache may allow frequently accessed data to be served much faster.
"""
    )

    explain(
        "Conceptual cache flow",
        """
Request
  |
  v
Cache?
 /   \
hit   miss
 |      |
 v      v
Return Database
        |
        v
      Cache
"""
    )

    explain(
        "Caching risks",
        """
Caching creates new problems:

- stale data
- invalidation
- memory usage
- cache stampedes
- consistency questions
- cache poisoning

A famous engineering lesson is that cache invalidation is deceptively
difficult.
"""
    )


# =============================================================================
# SECTION 22: REVERSE PROXY AND LOAD BALANCER
# =============================================================================

def lesson_proxy_load_balancer():
    title("22. REVERSE PROXY AND LOAD BALANCER")

    explain(
        "Reverse proxy",
        """
A reverse proxy sits in front of backend servers.

Client
  |
  v
Reverse Proxy
  |
  +--------+
  |        |
  v        v
Backend A Backend B

Common responsibilities include:

- TLS termination
- routing
- compression
- security filtering
- static content
- request limits
"""
    )

    explain(
        "Load balancing",
        """
A load balancer distributes traffic among multiple backend instances.

Example:

1000 requests
      |
      v
Load Balancer
      |
 +----+----+----+
 |    |    |    |
 v    v    v    v
A    B    C    D

This allows horizontal scaling.
"""
    )


# =============================================================================
# SECTION 23: MONOLITHS AND MICROSERVICES
# =============================================================================

def lesson_architectural_styles():
    title("23. MONOLITHS VS MICROSERVICES")

    explain(
        "Monolith",
        """
A monolith packages most application functionality into one deployable
application.

Advantages:

- simple deployment
- easier local development
- easier transactions
- straightforward debugging
- less network complexity

Disadvantages:

- can become large
- tightly coupled modules
- scaling may be less granular
"""
    )

    explain(
        "Microservices",
        """
A microservice architecture splits capabilities into independently
deployable services.

Example:

             API Gateway
                  |
       +----------+----------+
       |          |          |
       v          v          v
    Users      Orders     Payments
    Service    Service     Service

Advantages:

- independent deployment
- independent scaling
- team autonomy
- technology flexibility

Costs:

- distributed systems complexity
- network failures
- observability challenges
- deployment complexity
- data consistency challenges
"""
    )

    explain(
        "Practical lesson",
        """
Microservices are not automatically more advanced or better.

A well-designed modular monolith is often a better starting point
than prematurely creating many services.
"""
    )


# =============================================================================
# SECTION 24: API DESIGN
# =============================================================================

def lesson_api_design():
    title("24. API DESIGN FUNDAMENTALS")

    explain(
        "Resource-oriented API",
        """
Example:

GET    /users
GET    /users/42
POST   /users
PATCH  /users/42
DELETE /users/42

Orders:

GET    /orders
GET    /orders/100
POST   /orders
PATCH  /orders/100
"""
    )

    explain(
        "Response design",
        """
A consistent API should establish conventions for:

- success responses
- validation errors
- authentication errors
- pagination
- filtering
- sorting
- resource naming
- versioning
- error structures
"""
    )

    example = {
        "data": {
            "id": 42,
            "name": "Alice"
        },
        "meta": {
            "request_id": "example-request-id"
        }
    }

    print("\nExample response:")
    print(json.dumps(example, indent=2))


# =============================================================================
# SECTION 25: PAGINATION
# =============================================================================

def lesson_pagination():
    title("25. PAGINATION")

    explain(
        "Why pagination exists",
        """
Imagine:

GET /users

returns 10 million users.

Sending everything in one response is inefficient.

Instead:

GET /users?page=1&limit=20

or cursor-based pagination:

GET /users?cursor=abc123&limit=20
"""
    )

    explain(
        "Offset pagination",
        """
page=5
limit=20

Conceptually:

OFFSET = (page - 1) * limit
"""
    )

    explain(
        "Cursor pagination",
        """
A cursor represents a position in the result set.

It is often better for large or frequently changing datasets because
deep offsets can become expensive and results may shift while paging.
"""
    )


# =============================================================================
# SECTION 26: RATE LIMITING
# =============================================================================

def lesson_rate_limiting():
    title("26. RATE LIMITING")

    explain(
        "Purpose",
        """
Rate limiting restricts how frequently a client can make requests.

Example:

100 requests/minute per API key

Why?

- prevent abuse
- protect infrastructure
- control costs
- reduce accidental overload
- mitigate some denial-of-service patterns
"""
    )

    explain(
        "Common algorithms",
        """
- Fixed window
- Sliding window
- Token bucket
- Leaky bucket
"""
    )


# =============================================================================
# SECTION 27: SECURITY FUNDAMENTALS
# =============================================================================

def lesson_security():
    title("27. BACKEND SECURITY FUNDAMENTALS")

    principles = [
        "Never trust client input",
        "Validate input",
        "Use parameterized database queries",
        "Hash passwords using dedicated password hashing algorithms",
        "Use HTTPS",
        "Apply least privilege",
        "Protect secrets",
        "Do not expose stack traces to users",
        "Use secure session/token handling",
        "Implement authorization checks server-side",
        "Rate-limit sensitive operations",
        "Log security-relevant events",
        "Keep dependencies updated",
        "Avoid unnecessary attack surface",
    ]

    for number, principle in enumerate(principles, 1):
        print(f"{number:>2}. {principle}")

    explain(
        "SQL injection concept",
        """
Dangerous conceptual pattern:

    SQL = "SELECT * FROM users WHERE name = '" + user_input + "'"

If user_input is malicious, the resulting SQL may be altered.

The correct approach is parameterized queries or an appropriately safe
database abstraction.
"""
    )

    explain(
        "Secrets",
        """
Do not hard-code:

- database passwords
- API keys
- private keys
- JWT signing secrets
- cloud credentials

Use environment variables or a dedicated secret-management system.
"""
    )


# =============================================================================
# SECTION 28: CONFIGURATION
# =============================================================================

def lesson_configuration():
    title("28. CONFIGURATION")

    explain(
        "Configuration vs code",
        """
Application behavior often depends on environment-specific values.

Development:

    DATABASE_HOST=localhost

Production:

    DATABASE_HOST=production-db.internal

The code can remain the same while configuration changes.
"""
    )

    demo_config = {
        "APP_ENV": os.getenv("APP_ENV", "development"),
        "PORT": os.getenv("PORT", "8000"),
        "DEBUG": os.getenv("DEBUG", "true"),
    }

    print("\nCurrent demonstration configuration:")
    print(json.dumps(demo_config, indent=2))


# =============================================================================
# SECTION 29: REQUEST PIPELINE SIMULATION
# =============================================================================

def request_pipeline_simulation():
    title("29. COMPLETE REQUEST PIPELINE SIMULATION")

    request = Request(
        method="GET",
        url="/api/users/1",
        headers={
            "Authorization": "Bearer demo-token",
            "Accept": "application/json",
        },
    )

    print("\nIncoming request:")
    print(request)

    pipeline = [
        "1. Network receives request",
        "2. Reverse proxy receives request",
        "3. Routing identifies endpoint",
        "4. Request ID is generated",
        "5. Authentication is performed",
        "6. Authorization is checked",
        "7. Input is validated",
        "8. Controller receives request",
        "9. Service layer executes business logic",
        "10. Repository accesses persistence",
        "11. Result is returned",
        "12. Response is serialized",
        "13. Response middleware executes",
        "14. Server sends response",
        "15. Client renders/processes response",
    ]

    for step in pipeline:
        print(step)
        time.sleep(0.05)

    response = Response(
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": str(uuid.uuid4()),
        },
        body={
            "id": 1,
            "name": "Alice",
        },
    )

    print("\nFinal response:")
    print(response)


# =============================================================================
# SECTION 30: MINI BACKEND APPLICATION
# =============================================================================

USERS = {
    1: {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
    },
    2: {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
    },
}


class BackendHandler(BaseHTTPRequestHandler):

    def _send_json(self, status_code, data):
        payload = json.dumps(data).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()

        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_json(
                200,
                {
                    "message": "Backend Fundamentals Demo",
                    "endpoint": "/users",
                },
            )
            return

        if parsed.path == "/users":
            self._send_json(200, list(USERS.values()))
            return

        if parsed.path.startswith("/users/"):
            try:
                user_id = int(parsed.path.split("/")[-1])
            except ValueError:
                self._send_json(
                    400,
                    {"error": "Invalid user ID"},
                )
                return

            user = USERS.get(user_id)

            if not user:
                self._send_json(
                    404,
                    {"error": "User not found"},
                )
                return

            self._send_json(200, user)
            return

        self._send_json(
            404,
            {"error": "Route not found"},
        )


def run_mini_server():
    title("30. MINI BACKEND SERVER")

    explain(
        "What this server demonstrates",
        """
This server uses only Python's standard library.

Endpoints:

GET /
GET /users
GET /users/1
GET /users/2

You can open them in a browser.

For example:

http://127.0.0.1:8000/
http://127.0.0.1:8000/users
http://127.0.0.1:8000/users/1
"""
    )

    print("\nStarting server on http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")

    server = HTTPServer(("127.0.0.1", 8000), BackendHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


# =============================================================================
# SECTION 31: TERMINAL WORKFLOW
# =============================================================================

def lesson_terminal_workflow():
    title("31. TERMINAL WORKFLOW")

    explain(
        "Useful commands",
        """
Create a project directory:

    mkdir backend-fundamentals

Enter it:

    cd backend-fundamentals

Create a Python file:

    code backend_development_fundamentals.py

Run it:

    python backend_development_fundamentals.py

Depending on your system:

    python3 backend_development_fundamentals.py
"""
    )

    explain(
        "Testing the mini server",
        """
Start the server.

Then use your browser:

    http://127.0.0.1:8000/

You can also use a terminal HTTP client if available:

    curl http://127.0.0.1:8000/

The important lesson is that the browser and curl are both clients.
"""
    )


# =============================================================================
# SECTION 32: BROWSER DEVELOPER TOOLS
# =============================================================================

def lesson_browser():
    title("32. BROWSER DEVELOPER TOOLS")

    explain(
        "Network tab",
        """
Open browser developer tools and inspect the Network tab.

When loading a webpage, observe:

- Request URL
- Request method
- Status code
- Request headers
- Response headers
- Request payload
- Response body
- Timing
"""
    )

    explain(
        "Why this is important",
        """
Backend development becomes much easier when you can actually observe
the request/response exchange.

Do not treat HTTP as invisible magic.

Inspect it.
"""
    )


# =============================================================================
# SECTION 33: PORTS
# =============================================================================

def lesson_ports():
    title("33. PORTS")

    explain(
        "What is a port?",
        """
An IP address identifies a machine/interface.

A port identifies a network service endpoint on that machine.

Example:

127.0.0.1:8000

127.0.0.1
    -> local machine

8000
    -> port

Common examples:

80   -> HTTP
443  -> HTTPS
22   -> SSH
5432 -> PostgreSQL
3306 -> MySQL

These are conventional defaults, not magical requirements.
"""
    )


# =============================================================================
# SECTION 34: DNS
# =============================================================================

def lesson_dns():
    title("34. DNS")

    explain(
        "DNS",
        """
DNS stands for Domain Name System.

Humans prefer:

    api.example.com

Networks ultimately communicate using IP addresses.

DNS translates names to network addresses.

Conceptually:

api.example.com
       |
       v
DNS
       |
       v
203.0.113.10
"""
    )


# =============================================================================
# SECTION 35: HTTPS
# =============================================================================

def lesson_https():
    title("35. HTTP VS HTTPS")

    explain(
        "HTTP",
        """
HTTP transfers application-layer messages without TLS encryption.
"""
    )

    explain(
        "HTTPS",
        """
HTTPS is HTTP carried over TLS.

TLS provides important security properties including:

- encryption
- server authentication
- integrity protection

For production web applications, HTTPS is essential.
"""
    )


# =============================================================================
# SECTION 36: STATIC VS DYNAMIC
# =============================================================================

def lesson_static_dynamic():
    title("36. STATIC VS DYNAMIC CONTENT")

    explain(
        "Static content",
        """
Static content is served largely as stored.

Examples:

- CSS
- JavaScript files
- images
- static HTML
"""
    )

    explain(
        "Dynamic content",
        """
Dynamic content is generated based on state, input or business logic.

Example:

GET /profile

The backend might retrieve the authenticated user's information and
construct a response dynamically.
"""
    )


# =============================================================================
# SECTION 37: CONCURRENCY
# =============================================================================

def lesson_concurrency():
    title("37. CONCURRENCY FUNDAMENTALS")

    explain(
        "Concurrency",
        """
Concurrency is about managing multiple tasks that overlap in execution.

A backend may need to handle:

    Request A
    Request B
    Request C
    Request D
    ...

at approximately the same time.
"""
    )

    explain(
        "CPU-bound vs I/O-bound",
        """
CPU-bound:

    encryption
    image processing
    model inference
    large calculations

I/O-bound:

    database query
    file read
    network request
    waiting for another service

Different workloads benefit from different concurrency strategies.
"""
    )


# =============================================================================
# SECTION 38: SCALABILITY
# =============================================================================

def lesson_scalability():
    title("38. SCALABILITY")

    explain(
        "Vertical scaling",
        """
Increase resources on one machine.

Example:

    4 CPU -> 16 CPU
    8 GB RAM -> 64 GB RAM
"""
    )

    explain(
        "Horizontal scaling",
        """
Add more instances.

Before:

    Client -> Server A

After:

              Load Balancer
              /     |     \
             A      B      C
"""
    )

    explain(
        "Scaling creates new problems",
        """
More servers introduce:

- load balancing
- distributed sessions
- shared caches
- database bottlenecks
- network failures
- observability requirements
- deployment coordination

Scaling is not simply 'buy another server'.
"""
    )


# =============================================================================
# SECTION 39: DATABASE BOTTLENECK
# =============================================================================

def lesson_bottlenecks():
    title("39. BACKEND BOTTLENECKS")

    explain(
        "Possible bottlenecks",
        """
A backend can be limited by:

- CPU
- memory
- disk
- network
- database
- external APIs
- locks
- connection pools
- serialization
- application code
"""
    )

    explain(
        "Important principle",
        """
Do not optimize based on assumptions.

Measure.

A slow endpoint might appear to be a Python problem but actually spend
95% of its time waiting for a database query.
"""
    )


# =============================================================================
# SECTION 40: OBSERVABILITY
# =============================================================================

def lesson_observability():
    title("40. OBSERVABILITY")

    explain(
        "Three classic pillars",
        """
Logs:

    What happened?

Metrics:

    How often/how much?

Traces:

    Where did time go across distributed components?
"""
    )

    explain(
        "Useful backend metrics",
        """
- request rate
- error rate
- latency
- CPU utilization
- memory utilization
- database latency
- queue depth
- cache hit rate
- active connections
"""
    )


# =============================================================================
# SECTION 41: DEPLOYMENT CONCEPT
# =============================================================================

def lesson_deployment():
    title("41. FROM LOCAL DEVELOPMENT TO PRODUCTION")

    explain(
        "Local",
        """
Developer computer:

    Browser
       |
       v
    Backend
       |
       v
    Local database
"""
    )

    explain(
        "Production",
        """
Users
  |
DNS
  |
CDN / Reverse Proxy
  |
Load Balancer
  |
Backend instances
  |
+--------+--------+
|                 |
Database          Cache
|
External services
"""
    )

    explain(
        "Environment differences",
        """
Development optimizes for:

- speed of development
- debugging
- experimentation

Production optimizes for:

- reliability
- security
- performance
- availability
- observability
- controlled deployments
"""
    )


# =============================================================================
# SECTION 42: GIT CONCEPT
# =============================================================================

def lesson_git():
    title("42. VERSION CONTROL")

    explain(
        "Why Git matters to backend developers",
        """
Backend applications contain code, configuration templates, migrations,
tests and infrastructure definitions.

Git tracks changes.

Basic workflow:

    git init
    git status
    git add .
    git commit -m "Initial backend"
    git branch
    git log
"""
    )


# =============================================================================
# SECTION 43: TESTING
# =============================================================================

def lesson_testing():
    title("43. BACKEND TESTING")

    explain(
        "Unit tests",
        """
Test small pieces of logic.

Example:

    calculate_discount()
"""
    )

    explain(
        "Integration tests",
        """
Test multiple components together.

Example:

    API -> service -> database
"""
    )

    explain(
        "End-to-end tests",
        """
Test the system from the perspective of a real user/client.

Example:

    Client -> API -> database -> response
"""
    )


# =============================================================================
# SECTION 44: BACKEND DESIGN THINKING
# =============================================================================

def lesson_design_thinking():
    title("44. HOW TO THINK LIKE A BACKEND DEVELOPER")

    principles = [
        "What request is being made?",
        "Who is making it?",
        "Can the requester perform this action?",
        "What input is supplied?",
        "Is the input valid?",
        "What business rules apply?",
        "What data is required?",
        "Where is the data stored?",
        "What happens if the database fails?",
        "What happens if an external service fails?",
        "What response should be returned?",
        "How should errors be represented?",
        "How will this be logged?",
        "How will this be monitored?",
        "What happens under high traffic?",
        "What security risks exist?",
    ]

    for i, principle in enumerate(principles, 1):
        print(f"{i:02d}. {principle}")


# =============================================================================
# SECTION 45: COMPLETE EXAMPLE
# =============================================================================

def complete_example():
    title("45. COMPLETE BACKEND REQUEST EXAMPLE")

    explain(
        "Scenario",
        """
A customer clicks:

    "View My Orders"
"""
    )

    steps = [
        ("1", "Browser", "GET /api/orders"),
        ("2", "Network", "Send HTTPS request"),
        ("3", "Reverse proxy", "Receive and forward request"),
        ("4", "Backend", "Match route"),
        ("5", "Middleware", "Create request ID"),
        ("6", "Authentication", "Verify identity"),
        ("7", "Authorization", "Verify order access"),
        ("8", "Validation", "Validate query parameters"),
        ("9", "Service", "Apply business rules"),
        ("10", "Repository", "Query database"),
        ("11", "Database", "Return order records"),
        ("12", "Service", "Transform records"),
        ("13", "Backend", "Create JSON response"),
        ("14", "Network", "Send HTTPS response"),
        ("15", "Browser", "Render orders"),
    ]

    print(f"\n{'#':<5} {'Component':<20} Action")
    print("-" * 75)

    for number, component, action in steps:
        print(f"{number:<5} {component:<20} {action}")


# =============================================================================
# SECTION 46: PRACTICE QUESTIONS
# =============================================================================

def practice_questions():
    title("46. PRACTICE QUIZ")

    score = 0

    questions = [
        (
            "Which side normally executes backend application code?",
            [
                "Browser only",
                "Server-side environment",
                "Keyboard",
                "Monitor",
            ],
            2,
        ),
        (
            "What does HTTP 404 generally mean?",
            [
                "Unauthorized",
                "Server crashed",
                "Resource not found",
                "Request successful",
            ],
            3,
        ),
        (
            "What does authentication determine?",
            [
                "Who you are",
                "What color the UI uses",
                "Database size",
                "Server CPU count",
            ],
            1,
        ),
        (
            "What does authorization determine?",
            [
                "Who you are",
                "What you are allowed to do",
                "Your IP address",
                "Your browser version",
            ],
            2,
        ),
        (
            "Which method is normally used to retrieve a resource?",
            [
                "GET",
                "DELETE",
                "PATCH",
                "HEADLESS",
            ],
            1,
        ),
        (
            "Why should the frontend not be trusted?",
            [
                "It is always slow",
                "Users can manipulate client-side behavior",
                "Browsers cannot send requests",
                "HTML is encrypted",
            ],
            2,
        ),
    ]

    for q, options, correct in questions:
        if quiz(q, options, correct):
            score += 1

    print(f"\nScore: {score}/{len(questions)}")


# =============================================================================
# SECTION 47: LEARNING EXERCISES
# =============================================================================

def exercises():
    title("47. HANDS-ON EXERCISES")

    exercises_list = [
        """
Exercise 1:
Create a Python HTTP server and add:
GET /
GET /about
GET /contact
""",
        """
Exercise 2:
Create:
GET /users
GET /users/1
GET /users/2
GET /users/3

Return 404 when a user does not exist.
""",
        """
Exercise 3:
Add POST /users.

Accept JSON containing:

{
    "name": "...",
    "email": "..."
}

Validate both fields.
""",
        """
Exercise 4:
Add an artificial 2-second delay and observe the effect of synchronous
processing.
""",
        """
Exercise 5:
Add request logging with a unique request ID.
""",
        """
Exercise 6:
Add an authorization rule:

Only an admin may delete users.
""",
        """
Exercise 7:
Implement simple pagination for a list of 100 users.
""",
        """
Exercise 8:
Create a cache dictionary and measure the difference between cache hits
and simulated database misses.
""",
        """
Exercise 9:
Use browser developer tools to inspect every request made by a webpage.
""",
        """
Exercise 10:
Draw your own architecture for:

Browser
API
Authentication
Business logic
Database
Cache
External payment service
"""
    ]

    for i, exercise in enumerate(exercises_list, 1):
        print(f"\n{i}. {exercise.strip()}")


# =============================================================================
# SECTION 48: FINAL MENTAL MODEL
# =============================================================================

def final_mental_model():
    title("48. FINAL BACKEND MENTAL MODEL")

    explain(
        "Remember this architecture",
        """
                        INTERNET
                           |
                           v
                       CLIENT
                           |
                           | HTTPS
                           v
                   REVERSE PROXY
                           |
                           v
                    LOAD BALANCER
                           |
              +------------+------------+
              |            |            |
              v            v            v
          BACKEND A    BACKEND B    BACKEND C
              |            |            |
              +------------+------------+
                           |
                           v
                      APPLICATION
                         LOGIC
                           |
              +------------+-------------+
              |            |             |
              v            v             v
          DATABASE      CACHE       QUEUE
                                        |
                                        v
                                     WORKER
                                        |
                                        v
                              EXTERNAL SERVICES
"""
    )

    explain(
        "The backend developer's core question",
        """
For every request, think:

    INPUT
      |
      v
    ROUTE
      |
      v
    AUTHENTICATE
      |
      v
    AUTHORIZE
      |
      v
    VALIDATE
      |
      v
    BUSINESS LOGIC
      |
      v
    DATA / EXTERNAL SERVICES
      |
      v
    ERROR HANDLING
      |
      v
    RESPONSE
      |
      v
    LOG / MEASURE / TRACE

This mental model will remain useful even when you move from simple Python
servers to FastAPI, Django, Node.js, Java/Spring, Go, .NET or distributed
microservice architectures.
"""
    )


# =============================================================================
# SECTION 49: GENERATE MARKDOWN NOTES
# =============================================================================

MARKDOWN_NOTES = r"""
# Backend Development Fundamentals

## 1. What Backend Development Is

Backend development is the development of server-side application
functionality.

A backend commonly:

- Receives client requests
- Routes requests
- Authenticates users
- Authorizes operations
- Validates input
- Executes business logic
- Reads and writes data
- Communicates with external services
- Handles errors
- Produces responses
- Logs and monitors application behavior

The backend is not simply a database. A database is one component that
backend software may use.

---

## 2. Frontend vs Backend

| Area | Frontend | Backend |
|---|---|---|
| Main environment | Browser/device | Server |
| Main purpose | User interface | Processing and business logic |
| Common technologies | HTML, CSS, JavaScript | Python, Java, Go, Node.js, C#, etc. |
| Database access | Usually indirect | Usually through backend |
| Security authority | Not trusted | Authoritative |
| Main question | How should information be presented? | What should happen and who may do it? |

A critical rule:

> Never trust the frontend.

Frontend validation improves user experience. Backend validation protects
correctness and security.

---

## 3. Client-Server Architecture

A client initiates communication.

Examples:

- Browser
- Mobile application
- Desktop application
- CLI program
- Another server

A server receives requests and provides resources or performs operations.

Typical flow:

```text
Client
   |
   | Request
   v
Server
   |
   +----> Database
   |
   +----> External Services
   |
   v
Response
   |
   v
Client
