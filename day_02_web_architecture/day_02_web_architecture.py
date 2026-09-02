"""
WEB ARCHITECTURE
================

A self-contained academic learning script covering Web Architecture
from fundamentals to advanced concepts.

The script is intentionally educational rather than framework-specific.
It uses Python examples and simulations to explain how modern web systems
are structured, how requests travel through them, and why particular
architectural decisions are made.

The examples are simplified models of real systems. They are not intended
to replace production infrastructure, but they demonstrate the underlying
ideas and relationships between components.

Topics covered
--------------
1. What web architecture means
2. Internet and web fundamentals
3. Clients and servers
4. URLs and URI structure
5. DNS
6. IP addresses
7. TCP and UDP
8. TLS and HTTPS
9. HTTP
10. HTTP methods
11. HTTP status codes
12. Headers
13. Cookies
14. Sessions
15. Authentication and authorization
16. Stateless and stateful architecture
17. Request-response lifecycle
18. Three-tier architecture
19. N-tier architecture
20. Monolithic architecture
21. Modular monolith
22. Microservices
23. Service-oriented architecture
24. API architecture
25. REST
26. GraphQL
27. RPC and gRPC concepts
28. Reverse proxies
29. Forward proxies
30. Web servers
31. Application servers
32. Load balancers
33. Load balancing algorithms
34. Horizontal and vertical scaling
35. Auto-scaling
36. Caching
37. Browser caching
38. Server-side caching
39. Redis-like caching concepts
40. CDN architecture
41. Database architecture
42. SQL and NoSQL
43. Database replication
44. Read replicas
45. Sharding
46. Connection pooling
47. Transactions
48. CAP theorem
49. Consistency models
50. Message queues
51. Event-driven architecture
52. Pub/Sub
53. Asynchronous processing
54. WebSockets
55. Server-Sent Events
56. Long polling
57. Background jobs
58. File and object storage
59. Search architecture
60. Rate limiting
61. Idempotency
62. Fault tolerance
63. Circuit breakers
64. Retries and exponential backoff
65. Health checks
66. Observability
67. Logging
68. Metrics
69. Distributed tracing
70. Security architecture
71. Authentication
72. Authorization
73. JWT concepts
74. OAuth concepts
75. CORS
76. CSRF
77. XSS
78. SQL injection
79. DDoS
80. Secrets management
81. Zero-trust principles
82. Deployment architecture
83. Containers
84. Kubernetes concepts
85. CI/CD
86. Blue-green deployment
87. Canary deployment
88. Rolling deployment
89. Disaster recovery
90. High availability
91. Multi-region architecture
92. Latency
93. Throughput
94. Availability
95. Reliability
96. Scalability
97. Performance
98. Architectural bottlenecks
99. System design reasoning
100. Complete web architecture simulation
"""

from dataclasses import dataclass, field
from collections import deque
from typing import Dict, List, Optional, Any
import hashlib
import json
import random
import time
import uuid


# ============================================================
# 1. BASIC UTILITY FUNCTIONS
# ============================================================

def title(text):
    print("\n" + "=" * 80)
    print(text.upper())
    print("=" * 80)


def subtitle(text):
    print("\n" + "-" * 80)
    print(text)
    print("-" * 80)


def explain(text):
    print(text)


def bullet(text):
    print(f"• {text}")


def pause():
    """
    Deliberately does not wait for user input.

    The function exists so that the script can be converted easily
    into an interactive teaching program later.
    """
    pass


# ============================================================
# 2. WHAT IS WEB ARCHITECTURE?
# ============================================================

def section_what_is_web_architecture():
    title("1. What Is Web Architecture")

    explain("""
Web architecture describes the structure of a web system and the way
different components cooperate to deliver a web application or web service.

A simple web application can consist of:

    Browser
       |
       v
    Web Server
       |
       v
    Application
       |
       v
    Database

A modern production system may look more like:

    User
      |
      v
    DNS
      |
      v
    CDN
      |
      v
    Load Balancer
      |
      v
    Reverse Proxy
      |
      +-----------------------+
      |                       |
      v                       v
  Application A          Application B
      |                       |
      +-----------+-----------+
                  |
                  v
             Cache Layer
                  |
                  v
             Database
                  |
          +-------+-------+
          |               |
          v               v
      Message Queue   Object Storage

The important point is that web architecture is not simply about
HTML pages or web servers. It concerns the complete path between a
client and the resources or services required to satisfy its request.
""")

    bullet("The browser is usually the client.")
    bullet("The server receives and processes requests.")
    bullet("DNS translates domain names into network destinations.")
    bullet("HTTP defines how web clients and servers communicate.")
    bullet("Databases persist structured application data.")
    bullet("Caches reduce repeated computation and database access.")
    bullet("Load balancers distribute traffic.")
    bullet("CDNs distribute content geographically.")
    bullet("Queues allow work to be processed asynchronously.")
    bullet("Observability helps operators understand system behavior.")
    bullet("Security controls protect data, identities, services, and infrastructure.")


# ============================================================
# 3. CLIENT-SERVER MODEL
# ============================================================

def section_client_server():
    title("2. Client-Server Architecture")

    explain("""
The client-server model divides responsibilities between two broad roles.

The client initiates a request.

The server receives the request, performs some processing, and returns
a response.

For example:

    Client
       |
       | GET /products
       |
       v
    Server
       |
       | Query database
       |
       v
    Database
       |
       | Product records
       |
       v
    Server
       |
       | HTTP response
       |
       v
    Client

A browser does not normally communicate directly with a database.

Instead, the application server controls access to the database.

This separation provides security, abstraction, validation, and control.
""")

    bullet("Client responsibility: presentation, user interaction, request generation.")
    bullet("Server responsibility: business logic, validation, persistence, authorization.")
    bullet("Database responsibility: persistent data storage and retrieval.")

    explain("""
A useful distinction is:

Presentation layer
    What the user sees.

Application layer
    What the application does.

Data layer
    What the application stores.

These layers form the foundation of many web architectures.
""")


# ============================================================
# 4. URL STRUCTURE
# ============================================================

def section_url():
    title("3. URL Architecture")

    url = "https://example.com:443/products/42?sort=price#reviews"

    explain(f"""
Example URL:

    {url}

The URL can be interpreted as:

    https
        |
        +-- Scheme / protocol

    example.com
        |
        +-- Hostname

    :443
        |
        +-- Port

    /products/42
        |
        +-- Path

    ?sort=price
        |
        +-- Query string

    #reviews
        |
        +-- Fragment

The fragment is normally handled by the client and is not sent to
the server as part of a normal HTTP request.

The path and query parameters usually influence what resource or
representation the server returns.
""")


# ============================================================
# 5. DNS
# ============================================================

def section_dns():
    title("4. DNS Architecture")

    explain("""
DNS means Domain Name System.

Humans prefer names such as:

    www.example.com

Networks ultimately communicate using IP addresses such as:

    203.0.113.20

DNS provides the naming system that connects these concepts.

A simplified lookup is:

    Browser
       |
       v
    DNS Resolver
       |
       v
    Root DNS
       |
       v
    TLD DNS
       |
       v
    Authoritative DNS
       |
       v
    IP Address

In practice, caching can make the process much shorter.

A resolver may already have the answer cached.

Common DNS records include:

A
    Maps a domain to an IPv4 address.

AAAA
    Maps a domain to an IPv6 address.

CNAME
    Creates an alias to another hostname.

MX
    Specifies mail servers.

TXT
    Stores text records used for verification and other purposes.

NS
    Identifies authoritative name servers.

DNS is therefore an important part of web architecture because
a web request usually begins with name resolution.
""")

    explain("""
DNS caching introduces an important architectural concept:

TTL

TTL means Time To Live.

A DNS record can be cached for a defined period.

Long TTL:
    Fewer DNS lookups
    Faster resolution
    Slower propagation of changes

Short TTL:
    More frequent lookups
    Easier changes
    More resolver traffic

This is an architectural trade-off rather than simply a technical setting.
""")


# ============================================================
# 6. NETWORK PROTOCOL STACK
# ============================================================

def section_network_stack():
    title("5. Network Protocol Stack")

    explain("""
A web request travels through multiple layers.

A simplified model is:

    Application
        |
        | HTTP
        v
    Transport
        |
        | TCP
        v
    Internet
        |
        | IP
        v
    Network Interface

Modern web systems may use:

    HTTP/1.1 over TCP
    HTTP/2 over TCP
    HTTP/3 over QUIC
    QUIC over UDP

The important architectural idea is layering.

Each layer has a responsibility.

Application layer:
    HTTP semantics

Transport layer:
    Reliable or low-level communication behavior

Network layer:
    Addressing and routing

Physical/link layer:
    Movement of packets over networks
""")


# ============================================================
# 7. TCP AND UDP
# ============================================================

def section_tcp_udp():
    title("6. TCP and UDP")

    explain("""
TCP provides a connection-oriented transport mechanism.

Important characteristics include:

    Reliability
    Ordering
    Retransmission
    Congestion control
    Connection management

UDP is connectionless and provides fewer guarantees.

UDP is useful when an application can tolerate loss or wants to
implement its own communication behavior.

QUIC, which is used by HTTP/3, is built on UDP while providing
modern transport features.

The architectural lesson is that the choice of transport affects:

    latency
    reliability
    connection establishment
    congestion behavior
    protocol design
""")


# ============================================================
# 8. HTTP
# ============================================================

@dataclass
class HttpRequest:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


@dataclass
class HttpResponse:
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


def section_http():
    title("7. HTTP Architecture")

    request = HttpRequest(
        method="GET",
        path="/products/42",
        headers={
            "Host": "example.com",
            "Accept": "application/json",
            "User-Agent": "ExampleBrowser/1.0"
        }
    )

    response = HttpResponse(
        status_code=200,
        headers={
            "Content-Type": "application/json"
        },
        body='{"id":42,"name":"Laptop"}'
    )

    explain("""
HTTP is the primary application protocol used by the Web.

An HTTP request contains:

    Method
    Target / path
    Headers
    Optional body

An HTTP response contains:

    Status code
    Headers
    Optional body
""")

    print("\nREQUEST")
    print(request)

    print("\nRESPONSE")
    print(response)


# ============================================================
# 9. HTTP METHODS
# ============================================================

def section_http_methods():
    title("8. HTTP Methods")

    methods = {
        "GET": "Retrieve a representation of a resource.",
        "POST": "Submit data or request creation/processing.",
        "PUT": "Replace a resource representation.",
        "PATCH": "Partially modify a resource.",
        "DELETE": "Delete a resource.",
        "HEAD": "Retrieve response metadata without the normal response body.",
        "OPTIONS": "Discover communication options."
    }

    for method, meaning in methods.items():
        print(f"{method:8} -> {meaning}")

    explain("""
Two concepts matter when designing APIs:

Safe
    A method is safe when it is intended not to modify server state.

Idempotent
    Repeating the same request produces the same intended server state.

GET is safe and idempotent.

PUT is generally idempotent.

DELETE is generally idempotent, although repeated requests can
produce different response codes.

POST is generally not idempotent.

Idempotency is particularly important in distributed systems because
network failures can cause clients to retry requests.
""")


# ============================================================
# 10. HTTP STATUS CODES
# ============================================================

def section_status_codes():
    title("9. HTTP Status Codes")

    statuses = {
        200: "OK",
        201: "Created",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found / temporary redirect",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized / authentication required",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout"
    }

    for code, meaning in statuses.items():
        print(f"{code}: {meaning}")

    explain("""
Status codes communicate the outcome of a request.

The first digit identifies the broad category:

1xx
    Informational

2xx
    Successful

3xx
    Redirection

4xx
    Client-side request problem

5xx
    Server-side failure

Architecturally, these codes allow clients, proxies, monitoring systems,
and other services to understand what happened without knowing internal
implementation details.
""")


# ============================================================
# 11. HTTP HEADERS
# ============================================================

def section_headers():
    title("10. HTTP Headers")

    headers = {
        "Host": "example.com",
        "Content-Type": "application/json",
        "Content-Length": "128",
        "Authorization": "Bearer <token>",
        "Cache-Control": "max-age=3600",
        "Accept": "application/json",
        "User-Agent": "Browser",
        "Origin": "https://example.com"
    }

    for key, value in headers.items():
        print(f"{key}: {value}")

    explain("""
Headers carry metadata.

Examples:

Content-Type
    Describes the representation format.

Authorization
    Carries authentication credentials or tokens.

Cache-Control
    Controls caching behavior.

Accept
    Describes formats the client can process.

Origin
    Identifies the origin associated with a browser request.

Headers are an important mechanism for communication between clients,
servers, proxies, browsers, and security systems.
""")


# ============================================================
# 12. COOKIES AND SESSIONS
# ============================================================

def section_cookies_sessions():
    title("11. Cookies and Sessions")

    explain("""
HTTP itself is stateless.

A server processes an individual request without automatically
remembering previous requests.

Web applications often need continuity.

For example:

    Request 1:
        User logs in.

    Request 2:
        User visits account page.

The server needs to know that both requests belong to the same user.

Cookies provide one mechanism.

A browser can store:

    session_id=abc123

and send it with later requests.

The server can use that identifier to locate session information.
""")

    explain("""
Two broad session strategies are common.

Server-side sessions:

    Browser
       |
       | session ID
       v
    Server
       |
       v
    Session Store

Token-based approach:

    Browser
       |
       | token
       v
    Server
       |
       v
    Validate token

Neither approach is automatically superior.

The architecture must consider:

    security
    revocation
    scalability
    storage
    token size
    expiration
    operational complexity
""")


# ============================================================
# 13. AUTHENTICATION AND AUTHORIZATION
# ============================================================

def section_auth():
    title("12. Authentication and Authorization")

    explain("""
Authentication answers:

    Who are you?

Authorization answers:

    What are you allowed to do?

Example:

    Authentication:
        User successfully logs in as "alice".

    Authorization:
        Alice may read invoices.

    Authorization:
        Alice may not delete invoices.

A typical request may pass through:

    Client
      |
      v
    Authentication
      |
      v
    Authorization
      |
      v
    Application logic
      |
      v
    Database

These concepts must not be treated as the same thing.
""")


# ============================================================
# 14. REQUEST RESPONSE LIFECYCLE
# ============================================================

def section_request_lifecycle():
    title("13. Complete Web Request Lifecycle")

    steps = [
        "User enters URL or activates an application action.",
        "Browser checks local caches and browser state.",
        "DNS resolution determines the destination.",
        "A network connection is established.",
        "TLS negotiation occurs for HTTPS.",
        "The browser sends an HTTP request.",
        "CDN or edge infrastructure may receive the request.",
        "A load balancer may select an application server.",
        "A reverse proxy may route the request.",
        "The application authenticates the request.",
        "Authorization is evaluated.",
        "Application logic executes.",
        "Cache may be checked.",
        "Database or another service may be called.",
        "The response is generated.",
        "The response travels back through infrastructure.",
        "The browser processes the response.",
        "Additional resources may be requested.",
        "The page or application interface is rendered."
    ]

    for index, step in enumerate(steps, start=1):
        print(f"{index:02}. {step}")

    explain("""
A single browser action can therefore involve many architectural layers.

This is why web architecture is best understood as a system rather
than as a single server program.
""")


# ============================================================
# 15. THREE-TIER ARCHITECTURE
# ============================================================

def section_three_tier():
    title("14. Three-Tier Architecture")

    explain("""
A classic three-tier architecture contains:

    Presentation Tier
          |
          v
    Application Tier
          |
          v
    Data Tier

Presentation tier:
    Browser-facing interface.

Application tier:
    Business rules and application processing.

Data tier:
    Database and persistent storage.

Example:

    Browser
       |
       v
    Frontend
       |
       v
    Backend API
       |
       v
    PostgreSQL

The benefit is separation of concerns.

The frontend does not need to know how database tables are structured.

The database does not need to know how a button is rendered.

The application layer acts as a controlled boundary between them.
""")


# ============================================================
# 16. N-TIER ARCHITECTURE
# ============================================================

def section_n_tier():
    title("15. N-Tier Architecture")

    explain("""
N-tier architecture expands the number of logical layers.

For example:

    Presentation
        |
    API Gateway
        |
    Authentication
        |
    Business Logic
        |
    Cache
        |
    Data Access
        |
    Database

Logical layers do not necessarily mean separate physical machines.

A single application may contain several logical layers.

Architectural layering helps control dependencies and responsibilities.
""")


# ============================================================
# 17. MONOLITHIC ARCHITECTURE
# ============================================================

def section_monolith():
    title("16. Monolithic Architecture")

    explain("""
A monolith is an application deployed as one primary unit.

Example:

    Web Application
       |
       +-- Authentication
       +-- Products
       +-- Orders
       +-- Payments
       +-- Reporting
       +-- Administration
       |
       v
    Database

A monolith is not necessarily badly designed.

A well-structured monolith can contain clear internal modules.

Advantages:

    Simple deployment
    Simple local development
    Simple debugging
    Straightforward transactions
    Fewer network calls

Disadvantages can include:

    Large deployment unit
    Strong coupling
    Scaling unrelated modules together
    Larger failure domain
    Increasing complexity as the system grows

The important distinction is between:

    Monolith

and:

    Poorly structured monolith

They are not identical.
""")


# ============================================================
# 18. MODULAR MONOLITH
# ============================================================

def section_modular_monolith():
    title("17. Modular Monolith")

    explain("""
A modular monolith remains one deployable application but has strong
internal boundaries.

For example:

    Application
    |
    +-- User Module
    |
    +-- Order Module
    |
    +-- Payment Module
    |
    +-- Reporting Module

Modules communicate through defined interfaces.

The deployment unit remains unified.

This can provide many benefits of modular design without introducing
the operational complexity of distributed microservices.
""")


# ============================================================
# 19. MICROSERVICES
# ============================================================

def section_microservices():
    title("18. Microservices Architecture")

    explain("""
Microservices divide an application into independently deployable services.

Example:

                     API Gateway
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      User Service   Order Service   Payment Service
          |              |              |
          v              v              v
       User DB        Order DB       Payment DB

Each service owns a specific business responsibility.

Potential advantages:

    Independent deployment
    Independent scaling
    Team autonomy
    Fault isolation
    Technology flexibility

Potential costs:

    Network communication
    Distributed transactions
    Service discovery
    Monitoring complexity
    Deployment complexity
    Data consistency challenges
    More operational infrastructure

Microservices move complexity from inside one application
to the boundaries between applications.
""")


# ============================================================
# 20. SERVICE ORIENTED ARCHITECTURE
# ============================================================

def section_soa():
    title("19. Service-Oriented Architecture")

    explain("""
Service-oriented architecture also organizes systems around services.

The distinction between SOA and microservices is not simply the
number of services.

SOA traditionally emphasizes broader enterprise services,
integration infrastructure, shared capabilities, and organizational
boundaries.

Microservices generally favor smaller independently deployable services,
strong ownership boundaries, decentralized implementation, and
independent scaling.

There is significant overlap between the two architectural styles.
""")


# ============================================================
# 21. API ARCHITECTURE
# ============================================================

def section_api():
    title("20. API Architecture")

    explain("""
An API provides a defined interface through which software components
communicate.

Example:

    GET /users/42

The client does not need to know how the user is stored.

The API provides an abstraction.

A well-designed API defines:

    Resources
    Operations
    Request formats
    Response formats
    Authentication
    Authorization
    Errors
    Versioning
    Rate limits
    Idempotency behavior
""")


# ============================================================
# 22. REST
# ============================================================

def section_rest():
    title("21. REST Architecture")

    explain("""
REST is an architectural style based on constraints.

Important ideas include:

    Client-server separation
    Stateless interactions
    Cacheability
    Uniform interface
    Layered system
    Resource-oriented representation

Example resources:

    /users
    /users/42
    /orders
    /orders/1001

A REST API might use:

    GET    /users/42
    PATCH  /users/42
    DELETE /users/42

REST is not simply "JSON over HTTP."

JSON is a data representation.

HTTP is a protocol.

REST is an architectural style.
""")


# ============================================================
# 23. GRAPHQL
# ============================================================

def section_graphql():
    title("22. GraphQL Architecture")

    explain("""
GraphQL allows clients to specify the data they require.

Traditional REST:

    GET /user/42
    GET /user/42/orders
    GET /user/42/preferences

GraphQL may allow a single query to request:

    user
      id
      name
      orders
      preferences

Potential advantages:

    Client-controlled data selection
    Reduced over-fetching
    Reduced under-fetching

Potential challenges:

    Query complexity
    Caching
    Authorization at field level
    Resource exhaustion
    More complex server-side execution
""")


# ============================================================
# 24. RPC AND GRPC
# ============================================================

def section_rpc():
    title("23. RPC and gRPC Concepts")

    explain("""
RPC means Remote Procedure Call.

The idea is that a program calls a remote operation in a style
similar to calling a local function.

For example:

    getUser(42)

The implementation may actually involve:

    Client
       |
       v
    Network
       |
       v
    Remote Service

gRPC is one modern RPC framework commonly used for service-to-service
communication.

RPC is often attractive for internal service communication where
strong contracts and efficient serialization are important.
""")


# ============================================================
# 25. WEB SERVER
# ============================================================

class WebServer:
    def handle(self, request):
        if request.path == "/":
            return HttpResponse(
                200,
                {"Content-Type": "text/plain"},
                "Welcome to the web server"
            )

        return HttpResponse(
            404,
            {"Content-Type": "text/plain"},
            "Not Found"
        )


def section_web_server():
    title("24. Web Server")

    explain("""
A web server accepts network requests and serves resources.

Examples of responsibilities include:

    Static files
    HTTP handling
    TLS termination
    Connection management
    Compression
    Proxying
    Routing

A web server may serve:

    HTML
    CSS
    JavaScript
    Images
    Fonts
    JSON

It may also forward dynamic requests to an application server.
""")

    server = WebServer()

    request = HttpRequest("GET", "/")
    response = server.handle(request)

    print("\nExample:")
    print(response)


# ============================================================
# 26. REVERSE PROXY
# ============================================================

def section_reverse_proxy():
    title("25. Reverse Proxy")

    explain("""
A reverse proxy sits between clients and backend servers.

    Client
       |
       v
    Reverse Proxy
       |
       +-------> Backend A
       |
       +-------> Backend B
       |
       +-------> Backend C

The client communicates with the proxy rather than directly with
the backend application.

Common reverse-proxy responsibilities:

    Routing
    TLS termination
    Load balancing
    Compression
    Caching
    Authentication integration
    Request filtering
    Header manipulation

A reverse proxy also hides internal server topology from clients.
""")


# ============================================================
# 27. FORWARD PROXY
# ============================================================

def section_forward_proxy():
    title("26. Forward Proxy")

    explain("""
The direction is different.

Forward proxy:

    Client
       |
       v
    Forward Proxy
       |
       v
    Internet

Reverse proxy:

    Internet
       |
       v
    Reverse Proxy
       |
       v
    Servers

A forward proxy represents clients.

A reverse proxy represents servers.
""")


# ============================================================
# 28. LOAD BALANCING
# ============================================================

@dataclass
class Backend:
    name: str
    healthy: bool = True
    active_requests: int = 0


class LoadBalancer:
    def __init__(self, backends):
        self.backends = backends
        self.index = 0

    def round_robin(self):
        healthy = [b for b in self.backends if b.healthy]

        if not healthy:
            return None

        backend = healthy[self.index % len(healthy)]
        self.index += 1
        return backend

    def least_connections(self):
        healthy = [b for b in self.backends if b.healthy]

        if not healthy:
            return None

        return min(healthy, key=lambda b: b.active_requests)


def section_load_balancing():
    title("27. Load Balancing")

    explain("""
A load balancer distributes requests across multiple backend instances.

    Client
       |
       v
    Load Balancer
       |
       +------> Server 1
       |
       +------> Server 2
       |
       +------> Server 3

Reasons for load balancing:

    Increased capacity
    High availability
    Fault isolation
    Horizontal scaling
    Maintenance without complete downtime
""")

    backends = [
        Backend("Server-A", True, 3),
        Backend("Server-B", True, 1),
        Backend("Server-C", True, 5)
    ]

    lb = LoadBalancer(backends)

    print("\nRound-robin selections:")
    for _ in range(6):
        backend = lb.round_robin()
        print(backend.name)

    print("\nLeast-connection selection:")
    print(lb.least_connections().name)


# ============================================================
# 29. LOAD BALANCING ALGORITHMS
# ============================================================

def section_load_algorithms():
    title("28. Load Balancing Algorithms")

    algorithms = {
        "Round Robin": "Distribute requests sequentially.",
        "Weighted Round Robin": "Give stronger servers more requests.",
        "Least Connections": "Send requests to the server with fewer active connections.",
        "Random": "Choose a server randomly.",
        "IP Hash": "Use a client-related hash to select a backend.",
        "Consistent Hashing": "Minimize reassignment when nodes change."
    }

    for name, description in algorithms.items():
        print(f"{name}: {description}")

    explain("""
No algorithm is universally best.

The correct choice depends on:

    request cost
    session behavior
    backend capacity
    connection duration
    traffic distribution
    failure behavior
""")


# ============================================================
# 30. HORIZONTAL AND VERTICAL SCALING
# ============================================================

def section_scaling():
    title("29. Scaling")

    explain("""
Vertical scaling:

    Increase resources of one machine.

    4 CPU -> 16 CPU
    16 GB RAM -> 64 GB RAM

Horizontal scaling:

    Add more machines.

    Server A
    Server B
    Server C
    Server D

Horizontal scaling is central to many highly available web systems.

It introduces new requirements:

    Load balancing
    Shared state management
    Service discovery
    Distributed caching
    Centralized logging
    Database scaling
    Coordination

Scaling the application layer is often easier than scaling a
strongly consistent stateful database.
""")


# ============================================================
# 31. AUTO SCALING
# ============================================================

def section_autoscaling():
    title("30. Auto Scaling")

    explain("""
Auto scaling changes the number of instances according to demand.

Example:

    Normal traffic:
        3 application servers

    Peak traffic:
        10 application servers

    Traffic decreases:
        4 application servers

Scaling policies can consider:

    CPU utilization
    Memory
    Request rate
    Queue depth
    Latency
    Custom business metrics

A useful principle is that scaling decisions should be based on
signals that correlate with actual system pressure.
""")


# ============================================================
# 32. CACHING
# ============================================================

class SimpleCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


def section_caching():
    title("31. Caching")

    explain("""
Caching stores reusable information closer to where it is needed.

Without caching:

    Client
       |
       v
    Application
       |
       v
    Database

With caching:

    Client
       |
       v
    Application
       |
       v
     Cache
       |
       +---- HIT ----> Return value
       |
       +---- MISS ---> Database
                         |
                         v
                       Cache

Caching reduces:

    database load
    latency
    repeated computation
    network traffic
""")

    cache = SimpleCache()

    cache.set("product:42", {
        "id": 42,
        "name": "Laptop",
        "price": 85000
    })

    print("Cache lookup:")
    print(cache.get("product:42"))


# ============================================================
# 33. CACHE STRATEGIES
# ============================================================

def section_cache_strategies():
    title("32. Cache Strategies")

    strategies = {
        "Cache Aside": "Application checks cache, then loads database on a miss.",
        "Read Through": "Cache layer loads missing data automatically.",
        "Write Through": "Writes go through cache and are persisted immediately.",
        "Write Back": "Writes reach storage later after entering cache.",
        "Write Around": "Writes bypass cache and go directly to storage."
    }

    for name, description in strategies.items():
        print(f"{name}: {description}")

    explain("""
Cache invalidation is difficult because cached data can become stale.

A cache design must consider:

    expiration
    invalidation
    consistency
    eviction
    memory limits
    cache stampede
    hot keys
    serialization
""")


# ============================================================
# 34. CACHE EVICTION
# ============================================================

def section_cache_eviction():
    title("33. Cache Eviction")

    explain("""
Caches have limited capacity.

When space is needed, entries may be removed.

Common policies include:

    LRU
        Least Recently Used

    LFU
        Least Frequently Used

    FIFO
        First In First Out

    TTL-based expiration
        Remove entries after a defined time

Eviction policy should match access patterns.
""")


# ============================================================
# 35. CDN
# ============================================================

def section_cdn():
    title("34. Content Delivery Networks")

    explain("""
A CDN distributes content through geographically distributed edge locations.

Without a CDN:

    User in Asia
          |
          v
    Origin in Europe

With a CDN:

    User in Asia
          |
          v
    Asian Edge
          |
       cache hit
          |
          v
       Content

The CDN can cache:

    images
    JavaScript
    CSS
    videos
    static HTML
    sometimes API responses

CDNs reduce geographic latency and origin traffic.
""")


# ============================================================
# 36. DATABASE ARCHITECTURE
# ============================================================

def section_database():
    title("35. Database Architecture")

    explain("""
The database is usually the durable source of application state.

A simple system may use:

    Application
         |
         v
    PostgreSQL

A larger system may use:

    Application
       |
       +----> Cache
       |
       +----> Primary Database
                  |
                  +----> Read Replica 1
                  |
                  +----> Read Replica 2

Databases are often the most difficult component to scale because
they contain persistent state and consistency requirements.
""")


# ============================================================
# 37. SQL AND NOSQL
# ============================================================

def section_sql_nosql():
    title("36. SQL and NoSQL")

    explain("""
Relational databases generally organize data into tables with
relationships and schemas.

Examples:

    Users
    Orders
    Products

SQL systems commonly provide strong transactional guarantees.

NoSQL is a broad category including:

    Key-value stores
    Document databases
    Column-family databases
    Graph databases

NoSQL systems can be useful when the access pattern, data model,
scale characteristics, or availability requirements differ from
traditional relational workloads.

The choice should follow workload requirements rather than fashion.
""")


# ============================================================
# 38. DATABASE REPLICATION
# ============================================================

def section_replication():
    title("37. Database Replication")

    explain("""
Replication creates multiple copies of data.

Primary:

    Application
        |
        v
     Primary
       / \
      /   \
     v     v
 Replica  Replica

Replication can improve:

    Read capacity
    Availability
    Disaster recovery
    Geographic distribution

Replication introduces questions about:

    replication lag
    consistency
    failover
    conflict handling
    recovery
""")


# ============================================================
# 39. READ REPLICAS
# ============================================================

def section_read_replicas():
    title("38. Read Replicas")

    explain("""
A common pattern is:

    Writes
      |
      v
    Primary DB
      |
      v
    Replicas

Reads can be distributed across replicas.

But replicas may lag behind the primary.

Therefore:

    Write -> Primary
    Immediate Read -> Primary

may be necessary when read-after-write consistency is required.

This is an example of how scaling decisions interact with consistency.
""")


# ============================================================
# 40. SHARDING
# ============================================================

def shard_key(user_id, shard_count):
    return hash(user_id) % shard_count


def section_sharding():
    title("39. Database Sharding")

    explain("""
Sharding divides data across multiple database partitions.

Example:

    Shard 0 -> Users 0-999
    Shard 1 -> Users 1000-1999
    Shard 2 -> Users 2000-2999

A production system may use a hash-based partitioning strategy.

The shard key determines where a record is stored.
""")

    for user_id in ["alice", "bob", "charlie", "david"]:
        print(
            f"{user_id:10} -> shard "
            f"{shard_key(user_id, 4)}"
        )

    explain("""
A good shard key distributes load evenly.

A poor shard key creates hotspots.

Sharding also makes operations such as cross-shard queries and
transactions more complicated.
""")


# ============================================================
# 41. CONNECTION POOLING
# ============================================================

class ConnectionPool:
    def __init__(self, size):
        self.connections = deque(
            [f"connection-{i}" for i in range(size)]
        )

    def acquire(self):
        if not self.connections:
            return None
        return self.connections.popleft()

    def release(self, connection):
        self.connections.append(connection)


def section_connection_pooling():
    title("40. Database Connection Pooling")

    explain("""
Opening a new database connection for every request can be expensive.

A connection pool maintains reusable connections.

    Application
        |
        v
    Connection Pool
      /   |   \
     v    v    v
    DB   DB   DB

Requests acquire a connection and release it after use.
""")

    pool = ConnectionPool(3)

    c1 = pool.acquire()
    c2 = pool.acquire()

    print("Acquired:", c1, c2)

    pool.release(c1)

    print("Available connection:", pool.acquire())


# ============================================================
# 42. TRANSACTIONS
# ============================================================

def section_transactions():
    title("41. Database Transactions")

    explain("""
A transaction groups operations into a logical unit.

A classical transaction model is ACID.

Atomicity
    All operations succeed or the transaction is rolled back.

Consistency
    Valid state transitions preserve defined constraints.

Isolation
    Concurrent transactions should not incorrectly interfere.

Durability
    Committed data survives appropriate failures.

Example:

    Transfer ₹1000

    Debit Account A
    Credit Account B

Both operations should form one logical transaction.

Distributed systems make transactions more difficult because
operations may cross service or database boundaries.
""")


# ============================================================
# 43. CAP THEOREM
# ============================================================

def section_cap():
    title("42. CAP Theorem")

    explain("""
CAP theorem concerns distributed data systems.

The three properties are:

    Consistency
    Availability
    Partition Tolerance

A network partition means distributed nodes cannot reliably
communicate with each other.

When a partition occurs, a distributed system must make a trade-off
between consistency and availability.

This does not mean that distributed systems simply choose any
two letters permanently.

The important practical lesson is that network partitions are real,
and system behavior during partitions must be explicitly designed.
""")


# ============================================================
# 44. CONSISTENCY MODELS
# ============================================================

def section_consistency():
    title("43. Consistency Models")

    explain("""
Strong consistency:

    A successful read reflects the latest committed write according
    to the system's consistency guarantees.

Eventual consistency:

    If updates stop, replicas eventually converge.

Read-after-write consistency:

    After a client successfully writes data, subsequent reads by
    that client observe the write.

Consistency is a spectrum of guarantees.

A web architecture should define what correctness means for each
operation rather than assuming that every piece of data needs the
same consistency level.
""")


# ============================================================
# 45. MESSAGE QUEUES
# ============================================================

class MessageQueue:
    def __init__(self):
        self.messages = deque()

    def publish(self, message):
        self.messages.append(message)

    def consume(self):
        if not self.messages:
            return None
        return self.messages.popleft()


def section_message_queue():
    title("44. Message Queues")

    explain("""
A message queue decouples producers and consumers.

    Producer
       |
       v
    Message Queue
       |
       v
    Consumer

Example:

    Web Request
       |
       v
    Create Order
       |
       +----> Queue
                 |
                 v
             Email Worker

The web request does not need to wait for email delivery.
""")

    queue = MessageQueue()

    queue.publish({
        "event": "order.created",
        "order_id": 1001
    })

    print("Message:", queue.consume())


# ============================================================
# 46. EVENT-DRIVEN ARCHITECTURE
# ============================================================

def section_event_driven():
    title("45. Event-Driven Architecture")

    explain("""
In an event-driven architecture, components react to events.

Example:

    Order Service
        |
        | OrderCreated
        v
    Event Bus
       / \
      /   \
     v     v
 Email   Inventory
Service   Service

The producer does not necessarily need direct knowledge of every consumer.

Benefits include:

    loose coupling
    asynchronous processing
    independent consumers
    extensibility

Costs include:

    eventual consistency
    event ordering
    duplicate events
    debugging difficulty
    schema evolution
    replay management
""")


# ============================================================
# 47. PUB/SUB
# ============================================================

class PubSub:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, topic, callback):
        self.subscribers.setdefault(topic, []).append(callback)

    def publish(self, topic, message):
        for callback in self.subscribers.get(topic, []):
            callback(message)


def section_pubsub():
    title("46. Publish-Subscribe Architecture")

    pubsub = PubSub()

    def email_service(message):
        print("Email service received:", message)

    def analytics_service(message):
        print("Analytics service received:", message)

    pubsub.subscribe("order.created", email_service)
    pubsub.subscribe("order.created", analytics_service)

    pubsub.publish(
        "order.created",
        {"order_id": 5001}
    )

    explain("""
In publish-subscribe systems, one published event may be delivered
to multiple independent subscribers.

This is different from a simple work queue where a message may be
processed by one consumer from a consumer group.
""")


# ============================================================
# 48. ASYNCHRONOUS PROCESSING
# ============================================================

def section_async():
    title("47. Asynchronous Processing")

    explain("""
Synchronous flow:

    Request
       |
       v
    Task A
       |
       v
    Task B
       |
       v
    Response

Asynchronous flow:

    Request
       |
       v
    Submit task
       |
       v
    Immediate response

    Worker
       |
       v
    Process task

Asynchronous processing is useful for work such as:

    email
    video processing
    report generation
    image resizing
    notifications
    data pipelines
    large computations

The trade-off is that the caller may no longer receive the final
result immediately.
""")


# ============================================================
# 49. WEBSOCKETS
# ============================================================

def section_websockets():
    title("48. WebSockets")

    explain("""
Traditional HTTP:

    Client -> Request -> Server
    Client <- Response <- Server

WebSocket:

    Client <===========> Server

After establishing a connection, both sides can send messages.

This is useful for:

    chat
    collaborative editing
    live dashboards
    multiplayer applications
    real-time notifications

WebSockets introduce connection-management concerns:

    connection limits
    reconnection
    load balancing
    authentication
    heartbeat
    backpressure
    horizontal scaling
""")


# ============================================================
# 50. SERVER-SENT EVENTS
# ============================================================

def section_sse():
    title("49. Server-Sent Events")

    explain("""
Server-Sent Events allow the server to continuously send events
to a browser over an HTTP connection.

Conceptually:

    Client
       |
       | HTTP connection
       |
       v
    Server
       |
       +---- event
       +---- event
       +---- event

SSE is primarily server-to-client.

WebSockets support communication in both directions.

SSE can be useful for:

    notifications
    live status
    progress updates
    streaming text
""")


# ============================================================
# 51. LONG POLLING
# ============================================================

def section_long_polling():
    title("50. Long Polling")

    explain("""
Long polling is a technique where the client sends a request and
the server keeps it open until data is available or a timeout occurs.

After receiving a response, the client sends another request.

It can approximate real-time behavior without requiring a persistent
bidirectional WebSocket connection.

It generally creates more overhead than modern real-time mechanisms,
but the concept is important historically and architecturally.
""")


# ============================================================
# 52. BACKGROUND JOBS
# ============================================================

def section_background_jobs():
    title("51. Background Jobs")

    explain("""
Background jobs move expensive or non-urgent work away from the
interactive request path.

Example:

    User
      |
      v
    API
      |
      +----> Database
      |
      +----> Job Queue
                 |
                 v
              Worker
                 |
                 v
              Storage

This improves response time and isolates heavy processing.
""")


# ============================================================
# 53. OBJECT STORAGE
# ============================================================

def section_object_storage():
    title("52. Object Storage")

    explain("""
Large files are often stored outside the primary relational database.

Examples:

    images
    videos
    documents
    backups
    datasets

A common architecture is:

    Browser
       |
       v
    Application
       |
       | signed upload URL
       v
    Object Storage

The application stores metadata while the object store holds
the large binary object.

This avoids forcing the primary database to handle all file traffic.
""")


# ============================================================
# 54. SEARCH ARCHITECTURE
# ============================================================

def section_search():
    title("53. Search Architecture")

    explain("""
Database queries and search engines solve different problems.

A transactional database is optimized for structured application
operations.

A search engine can be optimized for:

    full-text search
    relevance ranking
    tokenization
    fuzzy matching
    faceting
    autocomplete

A common architecture is:

    Primary Database
          |
          | Change stream
          v
      Search Index

The search index becomes a derived representation of application data.

This introduces synchronization and eventual-consistency concerns.
""")


# ============================================================
# 55. RATE LIMITING
# ============================================================

class RateLimiter:
    def __init__(self, limit):
        self.limit = limit
        self.counts = {}

    def allow(self, client_id):
        current = self.counts.get(client_id, 0)

        if current >= self.limit:
            return False

        self.counts[client_id] = current + 1
        return True


def section_rate_limiting():
    title("54. Rate Limiting")

    explain("""
Rate limiting restricts how frequently a client can perform an action.

Example:

    100 requests per minute

Reasons:

    Abuse prevention
    Resource protection
    Fairness
    Cost control
    DDoS mitigation support

Common conceptual algorithms include:

    Fixed Window
    Sliding Window
    Token Bucket
    Leaky Bucket
""")

    limiter = RateLimiter(3)

    for i in range(5):
        print(
            f"Request {i + 1}: "
            f"{'allowed' if limiter.allow('client-1') else 'blocked'}"
        )


# ============================================================
# 56. IDEMPOTENCY
# ============================================================

def section_idempotency():
    title("55. Idempotency")

    explain("""
Suppose a client creates a payment.

The client sends:

    POST /payments

The network fails after the server processes the request.

The client cannot tell whether the payment succeeded.

It retries.

Without protection, the payment might be created twice.

An idempotency key can solve this class of problem.

Example:

    Idempotency-Key: abc-123

The server records the result associated with the key.

If the same request arrives again, the server can return the
previous result instead of performing the operation again.

This is particularly important for:

    payments
    orders
    reservations
    financial operations
""")


# ============================================================
# 57. RETRIES
# ============================================================

def section_retries():
    title("56. Retries and Exponential Backoff")

    explain("""
Distributed systems experience temporary failures.

A client may retry.

A dangerous pattern is:

    Request fails
       |
       v
    Retry immediately
       |
       v
    Retry immediately
       |
       v
    Retry immediately

If thousands of clients behave this way, the overloaded service
can become even more overloaded.

Exponential backoff increases the delay:

    1 second
    2 seconds
    4 seconds
    8 seconds
    16 seconds

Jitter adds randomness to prevent many clients from retrying
simultaneously.

Retries should also be limited.
""")


# ============================================================
# 58. CIRCUIT BREAKER
# ============================================================

class CircuitBreaker:
    def __init__(self, failure_threshold=3):
        self.failure_threshold = failure_threshold
        self.failures = 0
        self.open = False

    def record_success(self):
        self.failures = 0

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.open = True

    def allow_request(self):
        return not self.open


def section_circuit_breaker():
    title("57. Circuit Breaker")

    explain("""
A circuit breaker prevents continuous calls to an unhealthy service.

States:

    CLOSED
        Requests flow normally.

    OPEN
        Requests are blocked quickly.

    HALF-OPEN
        Limited requests test whether the service has recovered.

Conceptually:

    Application
        |
        v
    Circuit Breaker
        |
        v
    Remote Service

This protects the caller from repeatedly waiting on a failing dependency.
""")

    breaker = CircuitBreaker(3)

    for _ in range(4):
        if breaker.allow_request():
            print("Request attempted")
            breaker.record_failure()
        else:
            print("Circuit open: request blocked")


# ============================================================
# 59. TIMEOUTS
# ============================================================

def section_timeouts():
    title("58. Timeouts")

    explain("""
Every network dependency should have a defined timeout.

Without timeouts:

    Service A
       |
       v
    Service B
       |
       v
    Service C

If C becomes slow, B waits.

B then becomes slow.

A then becomes slow.

Eventually many requests may become stuck.

Timeouts limit how long a component waits for a dependency.

Different timeout types can exist:

    connection timeout
    read timeout
    request timeout
    database timeout
    queue processing timeout
""")


# ============================================================
# 60. HEALTH CHECKS
# ============================================================

def section_health_checks():
    title("59. Health Checks")

    explain("""
Load balancers and orchestration systems need to know whether
instances are usable.

A health endpoint may expose:

    /health

A basic liveness check asks:

    Is the process alive?

A readiness check asks:

    Is the process ready to receive traffic?

These are different questions.

An application can be alive but not ready because:

    database connection is unavailable
    required configuration is missing
    dependency initialization is incomplete
""")


# ============================================================
# 61. OBSERVABILITY
# ============================================================

def section_observability():
    title("60. Observability")

    explain("""
Observability helps determine what is happening inside a system
from its externally visible behavior.

Three major signals are:

    Logs
    Metrics
    Traces

Logs:
    Individual events and contextual information.

Metrics:
    Numeric measurements over time.

Traces:
    The path of a request through distributed components.
""")


# ============================================================
# 62. LOGGING
# ============================================================

def section_logging():
    title("61. Logging Architecture")

    explain("""
Centralized logging is important when many application instances exist.

Instead of:

    Server A -> local log
    Server B -> local log
    Server C -> local log

a system may use:

    Server A \
    Server B  ---> Log Collector ---> Central Storage
    Server C /

Useful log fields include:

    timestamp
    request ID
    trace ID
    user or actor identifier where appropriate
    endpoint
    status
    latency
    error details

Sensitive information should not be logged unnecessarily.
""")


# ============================================================
# 63. METRICS
# ============================================================

def section_metrics():
    title("62. Metrics")

    metrics = {
        "Request Rate": "Requests per second.",
        "Error Rate": "Percentage of failed requests.",
        "Latency": "Time taken to process requests.",
        "CPU": "Processor utilization.",
        "Memory": "Memory consumption.",
        "Queue Depth": "Number of waiting jobs.",
        "Database Connections": "Active database connections."
    }

    for name, meaning in metrics.items():
        print(f"{name}: {meaning}")

    explain("""
Latency should often be analyzed using percentiles.

p50:
    Median

p95:
    95% of requests are at or below this value.

p99:
    99% of requests are at or below this value.

Averages can hide slow-tail behavior.
""")


# ============================================================
# 64. DISTRIBUTED TRACING
# ============================================================

def section_tracing():
    title("63. Distributed Tracing")

    explain("""
Suppose a request follows:

    Browser
       |
       v
    API Gateway
       |
       v
    Order Service
       |
       v
    Payment Service
       |
       v
    Database

Tracing assigns a trace identity and records spans.

Example:

    Trace ID: abc123

    Span 1: API Gateway
    Span 2: Order Service
    Span 3: Payment Service
    Span 4: Database

This makes it possible to identify where latency or failure occurred.
""")


# ============================================================
# 65. WEB SECURITY
# ============================================================

def section_security():
    title("64. Web Security Architecture")

    explain("""
Security should exist across the entire architecture.

Client
    |
    v
CDN / Edge Security
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

Security controls may include:

    TLS
    Authentication
    Authorization
    Input validation
    Rate limiting
    Secrets management
    Network segmentation
    Access control
    Encryption
    Logging
    Monitoring
    Dependency management
""")


# ============================================================
# 66. HTTPS AND TLS
# ============================================================

def section_https():
    title("65. HTTPS and TLS")

    explain("""
HTTPS means HTTP over TLS.

TLS provides important properties such as:

    Encryption
    Server authentication
    Integrity protection

Without encryption, sensitive HTTP traffic could be observed
or manipulated on an untrusted network.

A simplified sequence is:

    Client
       |
       | TLS handshake
       v
    Server
       |
       | certificate verification
       v
    Encrypted communication

TLS protects the transport channel.

It does not automatically make the application secure.
""")


# ============================================================
# 67. JWT
# ============================================================

def create_demo_jwt_payload(user_id, role):
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time())
    }

    return payload


def section_jwt():
    title("66. JWT Concepts")

    explain("""
JWT means JSON Web Token.

A JWT commonly has three conceptual sections:

    Header
    Payload
    Signature

The payload may contain claims such as:

    subject
    expiration
    role
    issuer

A signed JWT allows a server to verify that the token was produced
by a trusted issuer and has not been modified.

A JWT is not automatically encrypted.

Therefore, sensitive information should not be placed in a JWT
payload merely because it is signed.
""")

    payload = create_demo_jwt_payload("user-42", "admin")

    print("\nExample payload:")
    print(json.dumps(payload, indent=2))


# ============================================================
# 68. OAUTH
# ============================================================

def section_oauth():
    title("67. OAuth Concepts")

    explain("""
OAuth is an authorization framework.

It allows an application to obtain delegated access to resources
without necessarily receiving the user's password.

A simplified conceptual relationship is:

    User
      |
      v
Authorization Server
      |
      v
Access Token
      |
      v
Resource Server

OAuth is primarily about delegated authorization.

Authentication and identity can be implemented using related
standards such as OpenID Connect.
""")


# ============================================================
# 69. CORS
# ============================================================

def section_cors():
    title("68. CORS")

    explain("""
CORS means Cross-Origin Resource Sharing.

Browsers enforce a same-origin security model.

An origin is determined by:

    scheme
    host
    port

For example:

    https://app.example.com

and:

    https://api.example.com

are different origins.

CORS allows a server to declare which browser origins may
access certain resources.

CORS is primarily a browser security mechanism.

It is not an authentication system.
""")


# ============================================================
# 70. CSRF
# ============================================================

def section_csrf():
    title("69. CSRF")

    explain("""
Cross-Site Request Forgery abuses authenticated browser context
to cause unwanted actions.

A common defense is a CSRF token.

Other important controls include:

    SameSite cookies
    Origin checks
    Referer validation where appropriate
    Proper authentication architecture

CSRF is especially relevant when authentication depends on
automatically attached browser credentials such as cookies.
""")


# ============================================================
# 71. XSS
# ============================================================

def section_xss():
    title("70. Cross-Site Scripting")

    explain("""
XSS occurs when attacker-controlled content is interpreted as
executable browser-side code.

Potential sources include:

    user comments
    search parameters
    profile fields
    stored database content

Important defenses include:

    output encoding
    safe templating
    Content Security Policy
    input handling
    avoiding unsafe HTML insertion

The architectural lesson is that data crossing trust boundaries
must be handled according to its context.
""")


# ============================================================
# 72. SQL INJECTION
# ============================================================

def section_sql_injection():
    title("71. SQL Injection")

    explain("""
SQL injection occurs when untrusted input changes the intended
meaning of a database query.

Unsafe conceptual pattern:

    query = "SELECT * FROM users WHERE name = '" + user_input + "'"

Safer architecture uses parameterized queries.

The database receives:

    SQL structure
    +
    data values

as separate concepts.

ORMs can help, but using an ORM does not automatically eliminate
all injection risks.
""")


# ============================================================
# 73. DDoS
# ============================================================

def section_ddos():
    title("72. DDoS and Traffic Protection")

    explain("""
A Distributed Denial-of-Service attack attempts to consume system
resources so legitimate users cannot receive service.

Defensive architecture can include:

    CDN
    Edge filtering
    Rate limiting
    Traffic analysis
    Load balancing
    Autoscaling
    Network controls
    Capacity planning

DDoS protection is usually strongest at the edge because traffic
can be filtered before it consumes expensive application resources.
""")


# ============================================================
# 74. SECRETS MANAGEMENT
# ============================================================

def section_secrets():
    title("73. Secrets Management")

    explain("""
Secrets include:

    database passwords
    API keys
    signing keys
    encryption keys
    service credentials

They should not normally be hard-coded into application source code.

A secure architecture separates:

    application code
    configuration
    secret material

Secret management systems can control:

    storage
    access
    rotation
    auditing
    expiration
""")


# ============================================================
# 75. ZERO TRUST
# ============================================================

def section_zero_trust():
    title("74. Zero Trust Principles")

    explain("""
Traditional network thinking often assumed that internal traffic
was trustworthy.

Zero-trust architecture rejects implicit trust.

A service should verify:

    identity
    authorization
    request context
    device or workload identity where applicable

A private network does not automatically make a request trustworthy.

This becomes particularly important in cloud and microservice environments.
""")


# ============================================================
# 76. DEPLOYMENT ARCHITECTURE
# ============================================================

def section_deployment():
    title("75. Deployment Architecture")

    explain("""
A production application normally has multiple environments.

Typical examples:

    Development
    Testing
    Staging
    Production

Deployment architecture determines how application artifacts move
between these environments.

A production system may include:

    Source Code
        |
        v
    CI Pipeline
        |
        v
    Build Artifact
        |
        v
    Registry
        |
        v
    Deployment System
        |
        v
    Production
""")


# ============================================================
# 77. CONTAINERS
# ============================================================

def section_containers():
    title("76. Containers")

    explain("""
A container packages an application together with its runtime
requirements in a standardized execution environment.

Conceptually:

    Application
    Runtime
    Dependencies
       |
       v
    Container Image

Containers improve consistency between environments.

They do not provide the same isolation model as a full virtual
machine in every respect.

Containers are commonly used as deployment units for modern
web services.
""")


# ============================================================
# 78. ORCHESTRATION
# ============================================================

def section_orchestration():
    title("77. Container Orchestration")

    explain("""
When there are many containers, manual management becomes difficult.

An orchestration platform can manage:

    scheduling
    service discovery
    health checks
    scaling
    rolling deployments
    restart behavior
    networking

Conceptually:

    Cluster
       |
       +-- Node 1
       |     +-- Container
       |     +-- Container
       |
       +-- Node 2
       |     +-- Container
       |
       +-- Node 3
             +-- Container
""")


# ============================================================
# 79. CI/CD
# ============================================================

def section_cicd():
    title("78. CI/CD")

    explain("""
Continuous Integration focuses on frequently integrating changes
and validating them automatically.

Continuous Delivery or Deployment automates the path toward production.

A simplified pipeline:

    Developer
       |
       v
    Git Repository
       |
       v
    Build
       |
       v
    Tests
       |
       v
    Security Checks
       |
       v
    Artifact
       |
       v
    Deployment
       |
       v
    Production

Automated pipelines reduce manual deployment errors and improve
repeatability.
""")


# ============================================================
# 80. BLUE GREEN
# ============================================================

def section_blue_green():
    title("79. Blue-Green Deployment")

    explain("""
Two production environments exist:

    Blue  -> current version
    Green -> new version

Traffic initially goes to Blue.

The new version is deployed to Green.

After validation:

    Traffic
       |
       v
    Green

If necessary, traffic can be switched back to Blue.

This reduces deployment risk but requires additional infrastructure.
""")


# ============================================================
# 81. CANARY
# ============================================================

def section_canary():
    title("80. Canary Deployment")

    explain("""
A canary deployment sends a small percentage of traffic to the
new version.

Example:

    95% -> Version A
     5% -> Version B

If Version B performs correctly:

    75% -> A
    25% -> B

Eventually:

    0% -> A
    100% -> B

Canary deployment allows real-world validation with limited exposure.
""")


# ============================================================
# 82. ROLLING DEPLOYMENT
# ============================================================

def section_rolling():
    title("81. Rolling Deployment")

    explain("""
A rolling deployment gradually replaces old instances.

Example:

    Old Old Old Old

    New Old Old Old

    New New Old Old

    New New New Old

    New New New New

This avoids replacing all instances simultaneously.

The architecture must maintain compatibility between versions
during the transition.
""")


# ============================================================
# 83. HIGH AVAILABILITY
# ============================================================

def section_high_availability():
    title("82. High Availability")

    explain("""
High availability means designing a system to remain operational
despite expected failures.

Single server:

    User
      |
      v
    Server
      X

No service.

High-availability design:

    User
      |
      v
    Load Balancer
       / \
      /   \
     v     v
    A       B

If A fails:

    Load Balancer
          |
          v
          B

High availability usually requires removing single points of failure.
""")


# ============================================================
# 84. FAULT TOLERANCE
# ============================================================

def section_fault_tolerance():
    title("83. Fault Tolerance")

    explain("""
Fault tolerance means a system continues operating despite component
failures.

Possible failures include:

    server crash
    network failure
    database failure
    dependency outage
    disk failure
    zone failure

Techniques include:

    redundancy
    replication
    failover
    retries
    timeouts
    circuit breakers
    graceful degradation
    queues
    backups
""")


# ============================================================
# 85. DISASTER RECOVERY
# ============================================================

def section_disaster_recovery():
    title("84. Disaster Recovery")

    explain("""
Disaster recovery concerns restoring service after severe failures.

Two important concepts are:

RPO
    Recovery Point Objective.

    How much data loss is acceptable?

RTO
    Recovery Time Objective.

    How long can recovery take?

Example:

    RPO = 5 minutes
    RTO = 30 minutes

This means the organization may accept up to approximately five
minutes of data loss and aims to restore service within thirty minutes.

Actual guarantees depend on the implementation.
""")


# ============================================================
# 86. MULTI-REGION ARCHITECTURE
# ============================================================

def section_multi_region():
    title("85. Multi-Region Architecture")

    explain("""
A multi-region system operates infrastructure in multiple geographic
regions.

Example:

                 Global Traffic
                       |
                Global Routing
                  /        \
                 /          \
                v            v
            Region A      Region B
               |             |
             Apps           Apps
               |             |
              DB             DB

Benefits:

    geographic resilience
    lower latency for global users
    disaster recovery

Challenges:

    replication
    data consistency
    routing
    operational complexity
    cross-region latency
    cost
""")


# ============================================================
# 87. LATENCY
# ============================================================

def section_latency():
    title("86. Latency")

    explain("""
Latency is the time taken for an operation.

A web request may contain multiple latency components:

    DNS
    connection establishment
    TLS
    network transfer
    load balancer
    application processing
    database query
    external API
    response transfer

Example:

    Total latency
       =
    network
    + application
    + database
    + external dependencies
    + serialization
    + queuing

Reducing one component does not necessarily solve the dominant bottleneck.
""")


# ============================================================
# 88. THROUGHPUT
# ============================================================

def section_throughput():
    title("87. Throughput")

    explain("""
Throughput describes how much work a system can process over time.

Examples:

    Requests per second
    Messages per second
    Transactions per second
    Megabytes per second

A system can have:

    High throughput but high latency

or:

    Low latency but limited throughput

They are related but not identical properties.
""")


# ============================================================
# 89. AVAILABILITY
# ============================================================

def section_availability():
    title("88. Availability")

    explain("""
Availability measures the proportion of time a service is operational.

Conceptually:

    Availability =
    Uptime / Total Observed Time

For example:

    99%
    99.9%
    99.99%
    99.999%

The additional "9" becomes increasingly expensive.

Availability targets should therefore be connected to actual business
requirements and failure costs.
""")


# ============================================================
# 90. RELIABILITY
# ============================================================

def section_reliability():
    title("89. Reliability")

    explain("""
Reliability concerns whether the system performs correctly over time.

A service that is always reachable but frequently returns incorrect
results is not reliable.

Reliability includes:

    correctness
    consistency
    failure handling
    recovery
    durability
    predictable behavior
""")


# ============================================================
# 91. PERFORMANCE
# ============================================================

def section_performance():
    title("90. Web Performance Architecture")

    explain("""
Performance optimization may involve:

    CDN caching
    compression
    HTTP/2 or HTTP/3
    browser caching
    database indexing
    query optimization
    connection pooling
    asynchronous processing
    code optimization
    reducing payload size
    reducing unnecessary network calls

Optimization should focus on measured bottlenecks.

A faster CPU does not solve a slow database query.

A faster database does not solve an inefficient client application.

Performance is an end-to-end property.
""")


# ============================================================
# 92. BOTTLENECKS
# ============================================================

def section_bottlenecks():
    title("91. Architectural Bottlenecks")

    explain("""
Common bottlenecks include:

    CPU
    Memory
    Database
    Network
    Disk
    Connection pools
    Thread pools
    External APIs
    Queue capacity
    Lock contention

Consider:

    Application -> Database

If the database can process 2,000 operations/second but the
application generates 5,000 operations/second, the database
becomes a bottleneck.

Adding application servers may make the problem worse by generating
even more database traffic.
""")


# ============================================================
# 93. BACKPRESSURE
# ============================================================

def section_backpressure():
    title("92. Backpressure")

    explain("""
Backpressure occurs when producers generate work faster than
consumers can process it.

Example:

    Producer: 10,000 messages/sec
    Consumer:  2,000 messages/sec

The queue grows.

A robust architecture needs a policy.

Possible responses:

    slow producers
    reject requests
    buffer work
    scale consumers
    prioritize important work
    shed low-value load

Without backpressure, queues can grow until memory or storage is exhausted.
""")


# ============================================================
# 94. GRACEFUL DEGRADATION
# ============================================================

def section_graceful_degradation():
    title("93. Graceful Degradation")

    explain("""
A system does not always need to fail completely when one component fails.

Example:

    Main Product Page
        |
        +-- Product Data
        |
        +-- Recommendations
        |
        +-- Reviews

If Recommendations fails, the product page may still work.

This is graceful degradation.

The architecture distinguishes:

    Critical dependencies
    Optional dependencies

Optional failures can be isolated instead of taking down the entire request.
""")


# ============================================================
# 95. SERVICE DISCOVERY
# ============================================================

def section_service_discovery():
    title("94. Service Discovery")

    explain("""
In dynamic environments, service instances may change frequently.

Instead of hard-coding:

    payment-service = 10.20.30.40

a service can discover available instances dynamically.

Conceptually:

    Order Service
         |
         v
    Service Discovery
         |
       / | \
      /  |  \
     v   v   v
   Pay Pay Pay

Discovery can be implemented using:

    DNS
    service registries
    orchestration platforms
    platform-native networking
""")


# ============================================================
# 96. API GATEWAY
# ============================================================

def section_api_gateway():
    title("95. API Gateway")

    explain("""
An API gateway provides a controlled entry point to backend services.

    Client
       |
       v
    API Gateway
       |
       +----> User Service
       |
       +----> Order Service
       |
       +----> Payment Service

Responsibilities may include:

    authentication
    authorization
    routing
    rate limiting
    request transformation
    logging
    aggregation
    TLS termination

A gateway can simplify clients but can also become a bottleneck
or single point of failure if poorly designed.
""")


# ============================================================
# 97. BFF
# ============================================================

def section_bff():
    title("96. Backend for Frontend")

    explain("""
Backend for Frontend, or BFF, creates backend interfaces tailored
to particular client types.

Example:

    Mobile App
        |
        v
    Mobile BFF
        |
        +----> Services

    Web App
        |
        v
    Web BFF
        |
        +----> Services

Mobile and web clients often have different requirements.

A BFF can adapt backend data to each client without forcing the
client to understand every internal service.
""")


# ============================================================
# 98. DATABASE INDEXING
# ============================================================

def section_indexes():
    title("97. Database Indexing")

    explain("""
An index provides a data structure that allows the database to find
records more efficiently.

Without a useful index:

    Search -> scan many rows

With an index:

    Search -> index lookup -> relevant rows

Indexes improve read performance but have costs:

    additional storage
    write overhead
    maintenance
    memory consumption

An index should be designed around actual query patterns.
""")


# ============================================================
# 99. DATABASE NORMALIZATION
# ============================================================

def section_normalization():
    title("98. Database Normalization")

    explain("""
Normalization organizes relational data to reduce inappropriate
duplication and update anomalies.

For example, instead of repeatedly storing:

    customer_name
    customer_email

inside every order row, a normalized design can separate:

    Customers
    Orders

with a relationship between them.

Normalization improves integrity.

Denormalization can sometimes improve read performance by storing
derived or repeated data.

The architectural trade-off is:

    consistency and maintainability

versus:

    read efficiency and query simplicity
""")


# ============================================================
# 100. DATABASE TRANSACTION ISOLATION
# ============================================================

def section_isolation():
    title("99. Transaction Isolation")

    explain("""
Concurrent database transactions can interfere in different ways.

Important phenomena include:

    Dirty Reads
    Non-repeatable Reads
    Phantom Reads

Database systems provide isolation levels to control these behaviors.

Common conceptual levels include:

    Read Uncommitted
    Read Committed
    Repeatable Read
    Serializable

Stronger isolation generally provides stronger consistency guarantees
but can reduce concurrency or increase contention.

Isolation is therefore both a correctness and performance decision.
""")


# ============================================================
# 101. DISTRIBUTED TRANSACTIONS
# ============================================================

def section_distributed_transactions():
    title("100. Distributed Transactions")

    explain("""
Consider:

    Order Service -> Order DB

and:

    Payment Service -> Payment DB

A business operation may require both to succeed.

A traditional single-database transaction cannot automatically
cover two independent databases.

Distributed transaction approaches exist, but they introduce
substantial complexity.

Another common approach is a saga.

Saga:

    Step 1 -> Step 2 -> Step 3

If Step 3 fails, compensating actions may undo the logical effects
of earlier steps.

This changes the problem from atomic database rollback to coordinated
business-level recovery.
""")


# ============================================================
# 102. EVENTUAL CONSISTENCY EXAMPLE
# ============================================================

def section_eventual_consistency_example():
    title("101. Eventual Consistency Example")

    explain("""
Suppose a user updates a profile.

Primary database:

    name = "Atul"

A replica may temporarily contain:

    name = "Old Name"

After replication:

    name = "Atul"

During this period, different readers can observe different values.

This may be acceptable for:

    analytics
    recommendations
    search indexes
    counters
    feeds

It may be unacceptable for:

    financial balances
    security permissions
    critical authorization decisions

The appropriate consistency model depends on the meaning of the data.
""")


# ============================================================
# 103. CDN + CACHE + APPLICATION
# ============================================================

def section_layered_cache():
    title("102. Layered Caching")

    explain("""
A large web system can have several cache layers.

    Browser Cache
          |
          v
    CDN Cache
          |
          v
    Reverse Proxy Cache
          |
          v
    Application Cache
          |
          v
    Database

A request may be satisfied at any layer.

Each layer has different:

    location
    lifetime
    capacity
    invalidation mechanism
    consistency characteristics

Layered caching can dramatically reduce origin load.
""")


# ============================================================
# 104. REQUEST COLLAPSING
# ============================================================

def section_request_collapsing():
    title("103. Request Collapsing")

    explain("""
Suppose a popular cache entry expires.

10,000 clients request it simultaneously.

Without protection:

    10,000 cache misses
        |
        v
    10,000 database requests

This is a cache stampede.

Request collapsing allows multiple clients to share one refresh operation.

Conceptually:

    10,000 requests
          |
          v
      One refresh
          |
          v
        Cache

The remaining requests reuse the result.
""")


# ============================================================
# 105. HOT KEYS
# ============================================================

def section_hot_keys():
    title("104. Hot Keys")

    explain("""
A hot key is a disproportionately popular cache or database key.

Example:

    product:1

may receive millions of requests while other products receive few.

This can create a bottleneck even when the overall cache capacity
looks sufficient.

Potential architectural techniques include:

    replication
    local caching
    request coalescing
    key spreading
    CDN caching
""")


# ============================================================
# 106. FILE UPLOAD ARCHITECTURE
# ============================================================

def section_file_upload():
    title("105. File Upload Architecture")

    explain("""
A scalable upload architecture often avoids sending large files
through the application server.

Less scalable:

    Browser
       |
       v
    Application
       |
       v
    Object Storage

More scalable:

    Browser
       |
       | upload authorization
       v
    Application
       |
       | signed URL
       v
    Browser
       |
       v
    Object Storage

The application handles authorization and metadata while the
storage service handles the large data transfer.
""")


# ============================================================
# 107. STATIC AND DYNAMIC CONTENT
# ============================================================

def section_static_dynamic():
    title("106. Static vs Dynamic Content")

    explain("""
Static content does not require application computation for every request.

Examples:

    CSS
    JavaScript
    images
    fonts

Dynamic content depends on request context or changing data.

Examples:

    account balances
    personalized dashboards
    order status

Static content is highly cacheable.

Dynamic content may still be cached, but the caching rules must
consider personalization and freshness.
""")


# ============================================================
# 108. SSR, CSR, SSG
# ============================================================

def section_rendering():
    title("107. Web Rendering Architecture")

    explain("""
Client-Side Rendering:

    Server sends application resources.
    Browser executes JavaScript.
    Browser builds much of the interface.

Server-Side Rendering:

    Server generates HTML.
    Browser receives rendered content.

Static Site Generation:

    HTML is generated ahead of time.

These approaches can be combined.

For example:

    Initial page -> server-rendered
    Later interaction -> client-side application

Architectural considerations include:

    SEO
    initial load time
    server cost
    interactivity
    caching
    data freshness
""")


# ============================================================
# 109. HTTP/1.1 VS HTTP/2 VS HTTP/3
# ============================================================

def section_http_versions():
    title("108. HTTP/1.1, HTTP/2 and HTTP/3")

    explain("""
HTTP/1.1:

    Text-based protocol
    Persistent connections
    Multiple requests require careful connection management

HTTP/2:

    Binary framing
    Multiplexed streams
    Header compression
    Multiple logical streams over one connection

HTTP/3:

    Uses QUIC
    QUIC is built on UDP
    Modern connection and transport behavior
    Better handling of some network changes

The evolution is largely about improving transport efficiency,
latency behavior, multiplexing, and connection management.
""")


# ============================================================
# 110. CONTENT COMPRESSION
# ============================================================

def section_compression():
    title("109. Compression")

    explain("""
Large responses consume network bandwidth.

Compression can reduce transfer size.

Common techniques include:

    gzip
    Brotli
    other modern compression formats

For text-based assets:

    HTML
    CSS
    JavaScript
    JSON

compression can substantially reduce network transfer size.

The trade-off is CPU consumption for compression and decompression.
""")


# ============================================================
# 111. BATCHING
# ============================================================

def section_batching():
    title("110. Request Batching")

    explain("""
Suppose a client needs 100 records.

Naive design:

    100 network requests

Batching:

    1 network request containing 100 logical operations

Batching can reduce:

    network round trips
    connection overhead
    serialization overhead

But excessively large batches can increase:

    latency
    memory usage
    failure scope

Batch size therefore matters.
""")


# ============================================================
# 112. DATABASE N+1
# ============================================================

def section_n_plus_one():
    title("111. N+1 Query Problem")

    explain("""
Suppose an application retrieves:

    100 orders

and then queries the database separately for each order's customer.

The system performs:

    1 query for orders
    +
    100 customer queries

Total:

    101 queries

This is the N+1 problem.

Possible solutions include:

    joins
    eager loading
    batching
    caching
    carefully designed data access layers
""")


# ============================================================
# 113. API VERSIONING
# ============================================================

def section_api_versioning():
    title("112. API Versioning")

    explain("""
APIs evolve.

A client may depend on:

    /api/v1/users

while a new design introduces:

    /api/v2/users

Versioning can be represented through:

    URL
    headers
    content negotiation

The important architectural requirement is controlled evolution.

Changing a response unexpectedly can break clients.
""")


# ============================================================
# 114. BACKWARD COMPATIBILITY
# ============================================================

def section_backward_compatibility():
    title("113. Backward Compatibility")

    explain("""
Distributed systems frequently have multiple versions running at once.

For example:

    Service A -> Version 1
    Service B -> Version 2

During deployment, both versions may coexist.

Therefore:

    old clients
    new clients
    old services
    new services

may communicate simultaneously.

Backward-compatible contracts reduce deployment risk.
""")


# ============================================================
# 115. SCHEMA EVOLUTION
# ============================================================

def section_schema_evolution():
    title("114. Schema Evolution")

    explain("""
Database and event schemas change over time.

A safe migration may involve:

    1. Add new field.
    2. Deploy code that understands both versions.
    3. Populate new field.
    4. Move reads to new field.
    5. Remove old field later.

Immediately renaming or deleting a field can break older application
instances during a rolling deployment.

Schema evolution is therefore closely related to deployment strategy.
""")


# ============================================================
# 116. DATA OWNERSHIP
# ============================================================

def section_data_ownership():
    title("115. Data Ownership in Distributed Systems")

    explain("""
In a microservice architecture, a service may own its data.

Example:

    User Service
       |
       v
    User Database

    Order Service
       |
       v
    Order Database

Other services interact through APIs or events rather than directly
reading another service's database.

This creates stronger boundaries but can make cross-domain queries
more difficult.
""")


# ============================================================
# 117. CQRS
# ============================================================

def section_cqrs():
    title("116. CQRS")

    explain("""
CQRS means Command Query Responsibility Segregation.

The idea is to separate:

    Commands
        Change state.

    Queries
        Read state.

A system might use:

    Command Model
        |
        v
    Primary Store

and:

    Read Model
        |
        v
    Optimized Query Store

This can improve read performance and model complex workloads,
but it introduces synchronization and operational complexity.
""")


# ============================================================
# 118. EVENT SOURCING
# ============================================================

def section_event_sourcing():
    title("117. Event Sourcing")

    explain("""
Event sourcing stores state changes as events.

Instead of storing only:

    Account Balance = 5000

the system may store:

    Deposited 1000
    Deposited 5000
    Withdrawn 1000

Current state can be derived by replaying events.

Benefits:

    audit history
    temporal reconstruction
    event-driven integration

Costs:

    event schema evolution
    storage growth
    replay complexity
    debugging complexity
""")


# ============================================================
# 119. FEATURE FLAGS
# ============================================================

def section_feature_flags():
    title("118. Feature Flags")

    explain("""
Feature flags separate deployment from feature activation.

Code can be deployed while a feature remains disabled.

Example:

    if feature_flag("new_checkout"):
        use_new_checkout()
    else:
        use_old_checkout()

This enables:

    gradual rollout
    targeted testing
    emergency disablement
    experimentation

Feature flags become architectural configuration and therefore
require lifecycle management.
""")


# ============================================================
# 120. MULTI-TENANCY
# ============================================================

def section_multitenancy():
    title("119. Multi-Tenant Architecture")

    explain("""
A multi-tenant system serves multiple customers from shared infrastructure.

Possible data models:

    Shared database
    Shared tables with tenant_id

or:

    Shared database
    Separate schema per tenant

or:

    Separate database per tenant

Each strategy has different trade-offs in:

    isolation
    cost
    operational complexity
    scaling
    backup
    customization
""")


# ============================================================
# 121. RATE LIMITING BY TENANT
# ============================================================

def section_tenant_limits():
    title("120. Tenant-Aware Resource Control")

    explain("""
Multi-tenant systems need fairness.

Suppose Tenant A consumes:

    95% of CPU

Tenant B may experience degraded performance.

Resource controls can therefore be applied per:

    user
    API key
    organization
    tenant
    IP
    endpoint

This is a form of workload isolation.
""")


# ============================================================
# 122. COMPLETE ARCHITECTURE DIAGRAM
# ============================================================

def section_complete_architecture():
    title("121. Complete Modern Web Architecture")

    explain(r"""
                         USERS
                           |
                           v
                    +-------------+
                    |   Browser   |
                    +-------------+
                           |
                           v
                    +-------------+
                    |     DNS     |
                    +-------------+
                           |
                           v
                    +-------------+
                    |     CDN     |
                    +-------------+
                           |
                           v
                 +-------------------+
                 | Edge / WAF / TLS  |
                 +-------------------+
                           |
                           v
                 +-------------------+
                 |  Load Balancer    |
                 +-------------------+
                           |
                           v
                 +-------------------+
                 | Reverse Proxy /   |
                 |   API Gateway     |
                 +-------------------+
                    /      |       \
                   /       |        \
                  v        v         v
             Frontend   API       Auth
                         |
                         v
                  +-------------+
                  | Application |
                  |   Services  |
                  +-------------+
                   /    |     \
                  /     |      \
                 v      v       v
              Cache   Queue   Search
                |       |       |
                |       v       |
                |    Workers    |
                |       |       |
                v       v       v
              +-------------------+
              | Persistent Data   |
              +-------------------+
                /       |       \
               v        v        v
           Primary   Replicas  Object
             DB        DB      Storage

Additional infrastructure:

    Monitoring
    Logging
    Tracing
    Secrets Management
    CI/CD
    Service Discovery
    Backup
    Disaster Recovery
    Security Controls
""")


# ============================================================
# 123. REQUEST WALKTHROUGH
# ============================================================

def section_request_walkthrough():
    title("122. Complete Request Walkthrough")

    explain("""
Assume a user requests:

    https://shop.example.com/products/42

STEP 1
    Browser determines whether local resources can satisfy the request.

STEP 2
    DNS resolves shop.example.com.

STEP 3
    Browser establishes a secure connection.

STEP 4
    HTTP request is sent.

STEP 5
    CDN receives the request.

STEP 6
    If the requested representation is cached, the CDN may respond.

STEP 7
    If not, the request reaches origin infrastructure.

STEP 8
    Load balancer selects an application instance.

STEP 9
    Reverse proxy routes the request.

STEP 10
    Application authenticates and authorizes if required.

STEP 11
    Application checks cache.

STEP 12
    Cache miss causes a database query.

STEP 13
    Database returns product data.

STEP 14
    Application builds the response.

STEP 15
    Response may be cached according to cache policy.

STEP 16
    Response travels back to the browser.

STEP 17
    Browser parses and renders the content.

This single operation demonstrates why web architecture involves
many interacting systems.
""")


# ============================================================
# 124. FAILURE SCENARIOS
# ============================================================

def section_failure_scenarios():
    title("123. Failure Scenarios")

    scenarios = [
        (
            "Application server fails",
            "Load balancer routes traffic to healthy instances."
        ),
        (
            "Cache fails",
            "Application may fall back to the database if designed to do so."
        ),
        (
            "Database replica fails",
            "Reads can be redirected to other replicas."
        ),
        (
            "External API becomes slow",
            "Timeouts and circuit breakers prevent unlimited waiting."
        ),
        (
            "Queue grows rapidly",
            "Autoscaling and backpressure can control the workload."
        ),
        (
            "Region becomes unavailable",
            "Traffic can potentially fail over to another region."
        ),
        (
            "Deployment contains a bug",
            "Canary, blue-green, or rollback strategies can limit impact."
        )
    ]

    for failure, response in scenarios:
        print(f"\nFailure: {failure}")
        print(f"Architectural response: {response}")


# ============================================================
# 125. BOTTLENECK ANALYSIS
# ============================================================

def section_bottleneck_analysis():
    title("124. Bottleneck Analysis")

    explain("""
Consider a service receiving:

    10,000 requests/sec

Suppose each request requires:

    1 database operation

The database supports:

    4,000 operations/sec

Then the database is the limiting component.

Adding more application servers:

    5 -> 20

does not solve the database capacity problem.

A better architecture may use:

    caching
    read replicas
    query optimization
    batching
    denormalization
    database scaling
    workload reduction

The correct architectural response depends on identifying the
actual limiting resource.
""")


# ============================================================
# 126. CAPACITY MODEL
# ============================================================

def section_capacity():
    title("125. Basic Capacity Reasoning")

    explain("""
Suppose:

    100,000 users

Each user produces:

    2 requests/minute

Average request rate:

    100,000 * 2 / 60
    =
    approximately 3,333 requests/sec

If peak traffic is 5 times average:

    approximately 16,665 requests/sec

Capacity planning must consider peak traffic rather than only average traffic.

Real systems also require headroom for:

    bursts
    failures
    maintenance
    uneven traffic
    background jobs
""")


# ============================================================
# 127. QUEUEING CONCEPT
# ============================================================

def section_queueing():
    title("126. Queueing and Waiting Time")

    explain("""
A service has limited processing capacity.

When arrival rate approaches service capacity, waiting time can
increase sharply.

For example:

    Arrival rate = 900 requests/sec
    Capacity     = 1,000 requests/sec

may be manageable.

But:

    Arrival rate = 990 requests/sec

leaves very little headroom.

If traffic temporarily exceeds capacity, queues form.

This explains why a system can appear healthy under normal traffic
and become extremely slow near saturation.
""")


# ============================================================
# 128. SINGLE POINT OF FAILURE
# ============================================================

def section_spof():
    title("127. Single Points of Failure")

    explain("""
A single point of failure is a component whose failure can
cause the service to become unavailable.

Example:

    Load Balancer
         |
         v
    Single Database

If the database fails, the system fails.

Possible improvement:

    Load Balancer
       /       \
      v         v
   DB Primary  DB Standby

But redundancy introduces operational requirements:

    failover
    replication
    monitoring
    recovery
    split-brain prevention
""")


# ============================================================
# 129. SECURITY BOUNDARIES
# ============================================================

def section_security_boundaries():
    title("128. Security Boundaries")

    explain("""
A security boundary separates components with different trust levels.

Example:

    Internet
       |
       v
    Edge
       |
       v
    Public API
       |
       v
    Internal Services
       |
       v
    Database

The database should generally not be directly exposed to the Internet.

Each layer can enforce different controls.

Defense in depth means that security does not depend on one control.
""")


# ============================================================
# 130. NETWORK SEGMENTATION
# ============================================================

def section_network_segmentation():
    title("129. Network Segmentation")

    explain("""
Infrastructure can be divided into network zones.

Example:

    Public Zone
       |
       v
    Application Zone
       |
       v
    Database Zone

Only required communication paths should be allowed.

For example:

    Internet -> Application
    Application -> Database

while:

    Internet -> Database

is blocked.

Segmentation reduces the impact of compromised components.
""")


# ============================================================
# 131. LEAST PRIVILEGE
# ============================================================

def section_least_privilege():
    title("130. Least Privilege")

    explain("""
Every identity should receive only the permissions required
to perform its function.

Example:

    Reporting Service
        |
        v
    Read-only database account

It should not automatically receive:

    DELETE
    DROP
    ALTER

Least privilege limits the consequences of credential compromise
or application vulnerabilities.
""")


# ============================================================
# 132. REQUEST ID
# ============================================================

def section_request_id():
    title("131. Request Correlation")

    request_id = str(uuid.uuid4())

    explain("""
A request ID can be assigned when a request enters the system.

Example:

    Request ID:
    """ + request_id)

    explain("""
That ID can be included in:

    application logs
    gateway logs
    database-related logs
    downstream requests
    error reports

This makes debugging distributed request flows easier.
""")


# ============================================================
# 133. DATA ENCRYPTION
# ============================================================

def section_encryption():
    title("132. Encryption in Web Architecture")

    explain("""
Encryption can protect data:

    In transit
        TLS

    At rest
        Database or storage encryption

Sensitive information may require additional application-level
encryption depending on the threat model.

Encryption introduces key-management requirements.

The key is often more sensitive than the encrypted data itself.
""")


# ============================================================
# 134. BACKUP ARCHITECTURE
# ============================================================

def section_backup():
    title("133. Backup Architecture")

    explain("""
Backups protect against:

    accidental deletion
    corruption
    operational mistakes
    ransomware
    catastrophic infrastructure failure

Backup architecture should consider:

    frequency
    retention
    encryption
    geographic separation
    restoration testing

A backup that has never been restored successfully should not be
treated as a fully verified recovery mechanism.
""")


# ============================================================
# 135. DISASTER RECOVERY STRATEGIES
# ============================================================

def section_dr_strategies():
    title("134. Disaster Recovery Strategies")

    strategies = {
        "Backup and Restore":
            "Restore infrastructure and data after failure.",
        "Pilot Light":
            "Keep minimal critical infrastructure available.",
        "Warm Standby":
            "Maintain a partially running recovery environment.",
        "Hot Standby":
            "Maintain an almost fully active secondary environment."
    }

    for name, description in strategies.items():
        print(f"{name}: {description}")

    explain("""
Recovery speed generally increases as more infrastructure is kept
ready, but cost and operational complexity also increase.
""")


# ============================================================
# 136. ARCHITECTURAL TRADE-OFFS
# ============================================================

def section_tradeoffs():
    title("135. Architectural Trade-Offs")

    explain("""
Web architecture is fundamentally about trade-offs.

Examples:

Simplicity vs flexibility

Consistency vs availability

Latency vs correctness guarantees

Cost vs redundancy

Centralization vs autonomy

Caching vs freshness

Normalization vs read performance

Synchronous processing vs asynchronous processing

Monolith simplicity vs distributed scalability

Strong isolation vs operational complexity

There is rarely one architecture that is best for every system.
""")


# ============================================================
# 137. MONOLITH VS MICROSERVICES
# ============================================================

def section_monolith_vs_microservices():
    title("136. Monolith vs Microservices")

    rows = [
        ("Deployment", "One main unit", "Multiple independent services"),
        ("Network calls", "Fewer internal calls", "Many service calls"),
        ("Data", "Often shared database", "Often service-owned data"),
        ("Scaling", "Scale larger unit", "Scale individual services"),
        ("Operations", "Simpler", "More complex"),
        ("Transactions", "Often easier", "More difficult"),
        ("Failure isolation", "Potentially broader", "Can be narrower"),
        ("Team boundaries", "Often centralized", "Strong service ownership")
    ]

    for item, monolith, microservices in rows:
        print(f"{item:20} | Monolith: {monolith}")
        print(f"{'':20} | Microservices: {microservices}")
        print()


# ============================================================
# 138. SYNCHRONOUS VS ASYNCHRONOUS
# ============================================================

def section_sync_async():
    title("137. Synchronous vs Asynchronous Architecture")

    explain("""
Synchronous:

    A -> B
    A waits for B.

Asynchronous:

    A -> Queue
    A continues.

    Worker -> B

Synchronous communication is easier to reason about.

Asynchronous communication can improve:

    resilience
    throughput
    responsiveness
    decoupling

but introduces:

    delayed results
    duplicate handling
    ordering concerns
    eventual consistency
""")


# ============================================================
# 139. EDGE COMPUTING
# ============================================================

def section_edge():
    title("138. Edge Architecture")

    explain("""
Edge computing moves computation closer to users.

Traditional:

    User -> Central Region -> Processing

Edge:

    User -> Nearby Edge -> Processing

Possible workloads include:

    caching
    authentication checks
    request filtering
    lightweight computation
    personalization

The closer computation is to the user, the lower network latency
can become, but distributed execution increases deployment and
consistency complexity.
""")


# ============================================================
# 140. WEB ARCHITECTURE AND CLOUD
# ============================================================

def section_cloud():
    title("139. Cloud Web Architecture")

    explain("""
Cloud platforms provide building blocks such as:

    virtual machines
    containers
    managed databases
    object storage
    load balancers
    CDNs
    queues
    monitoring
    identity services

A cloud architecture may therefore replace self-managed infrastructure
with managed services.

Managed services reduce operational burden but introduce:

    provider dependency
    cost complexity
    service-specific constraints
    networking complexity
""")


# ============================================================
# 141. SERVERLESS
# ============================================================

def section_serverless():
    title("140. Serverless Architecture")

    explain("""
Serverless architecture allows developers to deploy functions or
services without directly managing the underlying servers.

Conceptually:

    HTTP Request
         |
         v
    Function
         |
         v
    Database

The infrastructure still exists.

The term means that infrastructure management is abstracted away
from the application developer.

Potential advantages:

    automatic scaling
    usage-based execution
    reduced server management

Potential concerns:

    cold starts
    execution limits
    vendor coupling
    observability
    distributed complexity
""")


# ============================================================
# 142. WEBHOOKS
# ============================================================

def section_webhooks():
    title("141. Webhooks")

    explain("""
A webhook allows one system to notify another system through an
HTTP request when an event occurs.

Example:

    Payment Provider
          |
          | POST /webhook
          v
    Your Application

Webhook architecture must consider:

    authentication
    signature verification
    retries
    duplicate events
    idempotency
    event ordering
    replay attacks
""")


# ============================================================
# 143. API RETRY SAFETY
# ============================================================

def section_api_retry():
    title("142. Retry-Safe API Design")

    explain("""
Retry behavior must match HTTP semantics and business operations.

Safe example:

    GET /products/42

Repeated requests normally do not create additional products.

Dangerous example:

    POST /payments

Repeated requests may create duplicate payments.

Therefore:

    transport reliability

and:

    business operation idempotency

must be considered together.
""")


# ============================================================
# 144. DATA FLOW VS CONTROL FLOW
# ============================================================

def section_data_control_flow():
    title("143. Data Flow and Control Flow")

    explain("""
Control flow answers:

    Which component calls which component?

Data flow answers:

    Where does information move?

Example:

    Browser
       |
       | control flow
       v
    API
       |
       | data
       v
    Database

In distributed systems, both flows must be understood.

A system may have simple control flow but complicated data replication.

Or it may have simple data storage but complex service orchestration.
""")


# ============================================================
# 145. DOMAIN BOUNDARIES
# ============================================================

def section_domain_boundaries():
    title("144. Domain Boundaries")

    explain("""
A good service boundary usually reflects a meaningful business
or technical responsibility.

Poor decomposition:

    Service 1 -> getUserName
    Service 2 -> getUserEmail
    Service 3 -> getUserAddress

This can create excessive network calls.

Better decomposition might group related responsibilities:

    User Service

Service boundaries should minimize unnecessary communication while
maintaining clear ownership.
""")


# ============================================================
# 146. CHAT APPLICATION ARCHITECTURE
# ============================================================

def section_chat_architecture():
    title("145. Example: Chat Application")

    explain("""
A possible chat architecture:

    Browser
       |
       v
    Load Balancer
       |
       v
    WebSocket Gateway
       |
       +----> Message Service
       |
       +----> Presence Service
       |
       +----> Notification Service
                    |
                    v
                 Queue
                    |
                    v
              Push Workers

Data may be stored in:

    relational database
    message store
    cache

The cache can maintain:

    online status
    connection mappings
    recent messages

The queue can process:

    notifications
    offline delivery
    analytics
""")


# ============================================================
# 147. E-COMMERCE ARCHITECTURE
# ============================================================

def section_ecommerce():
    title("146. Example: E-Commerce Architecture")

    explain("""
A simplified e-commerce architecture:

    Customer
       |
       v
    CDN
       |
       v
    API Gateway
       |
       +----> Product Service
       |
       +----> Cart Service
       |
       +----> Order Service
       |
       +----> Payment Service
       |
       +----> User Service

Product data may use:

    Database
    Cache
    Search Index

Order creation may publish:

    OrderCreated

Consumers may include:

    Inventory
    Email
    Analytics
    Shipping

Payment operations require stronger correctness and idempotency
than many read-only product requests.
""")


# ============================================================
# 148. SOCIAL MEDIA ARCHITECTURE
# ============================================================

def section_social_media():
    title("147. Example: Social Media Architecture")

    explain("""
A simplified social platform can contain:

    User Service
    Post Service
    Media Service
    Feed Service
    Notification Service
    Search Service

Media:

    Browser
       |
       v
    Object Storage
       |
       v
    CDN

Posts:

    API
       |
       v
    Post Service
       |
       v
    Database

Feed generation can be:

    Pull model
        Generate feed when requested.

    Push model
        Precompute feed entries when content is published.

Large platforms often use hybrid approaches.
""")


# ============================================================
# 149. NEWS FEED ARCHITECTURE
# ============================================================

def section_feed():
    title("148. Feed Generation")

    explain("""
Pull-based feed:

    User requests feed
       |
       v
    Find followed users
       |
       v
    Retrieve recent posts
       |
       v
    Rank

Push-based feed:

    User publishes post
       |
       v
    Fan out to followers
       |
       v
    Precomputed feeds

Pull is easier for users with huge follower counts.

Push can provide fast reads but may produce enormous write amplification.

A hybrid design treats high-follower accounts differently.
""")


# ============================================================
# 150. SEARCH AUTOCOMPLETE
# ============================================================

def section_autocomplete():
    title("149. Search Autocomplete")

    explain("""
Autocomplete is latency-sensitive.

A typical architecture:

    Browser
       |
       v
    CDN / Edge
       |
       v
    Search API
       |
       v
    Prefix Index / Search Engine

Caching popular prefixes can reduce backend load.

For example:

    "py"
    "pyt"
    "pyth"

can be served from highly optimized indexes or caches.
""")


# ============================================================
# 151. ARCHITECTURAL SIMULATION
# ============================================================

class SimulatedApplication:
    def __init__(self):
        self.cache = SimpleCache()
        self.database = {
            1: {"id": 1, "name": "Laptop", "price": 85000},
            2: {"id": 2, "name": "Phone", "price": 50000}
        }

    def get_product(self, product_id):
        key = f"product:{product_id}"

        cached = self.cache.get(key)

        if cached is not None:
            return {
                "source": "cache",
                "data": cached
            }

        product = self.database.get(product_id)

        if product is None:
            return {
                "source": "database",
                "data": None
            }

        self.cache.set(key, product)

        return {
            "source": "database",
            "data": product
        }


def section_simulation():
    title("150. End-to-End Architecture Simulation")

    application = SimulatedApplication()

    print("First request:")
    print(application.get_product(1))

    print("\nSecond request:")
    print(application.get_product(1))

    explain("""
The first request reaches the database.

The application stores the result in the cache.

The second request is served from the cache.

This simple simulation demonstrates a core architectural principle:

    repeated expensive work can be avoided by storing reusable results.
""")


# ============================================================
# 152. ARCHITECTURE CHECKLIST AS CONCEPTS
# ============================================================

def section_architecture_reasoning():
    title("151. Architectural Reasoning Framework")

    explain("""
When analyzing a web architecture, ask:

    1. Who are the clients?
    2. How does DNS resolve the service?
    3. Where does TLS terminate?
    4. Where is traffic filtered?
    5. Where is load balancing performed?
    6. How are requests routed?
    7. Where does authentication occur?
    8. Where does authorization occur?
    9. Which components are stateless?
    10. Where is state stored?
    11. Which data is cached?
    12. How is cache invalidation handled?
    13. How does the database scale?
    14. Are replicas used?
    15. Is sharding required?
    16. Which tasks are synchronous?
    17. Which tasks are asynchronous?
    18. Where are queues used?
    19. How are failures handled?
    20. What are the timeouts?
    21. How are retries controlled?
    22. How is rate limiting implemented?
    23. How is traffic monitored?
    24. How are logs collected?
    25. How are distributed requests traced?
    26. How are secrets protected?
    27. How are deployments performed?
    28. What happens if a server fails?
    29. What happens if a database fails?
    30. What happens if a region fails?
    31. What is the recovery strategy?
    32. Which component is the bottleneck?
    33. Which component is the single point of failure?
    34. Which data requires strong consistency?
    35. Which data can tolerate eventual consistency?
""")


# ============================================================
# 153. ARCHITECTURE LAYERS
# ============================================================

def section_architecture_layers():
    title("152. Architectural Layers in One View")

    explain("""
A modern web system can be understood through several layers.

LAYER 1: USER
    Human or automated client.

LAYER 2: CLIENT
    Browser, mobile application, command-line client, API consumer.

LAYER 3: EDGE
    DNS, CDN, WAF, DDoS protection.

LAYER 4: TRAFFIC MANAGEMENT
    Load balancer, reverse proxy, API gateway.

LAYER 5: APPLICATION
    Business logic and API processing.

LAYER 6: DISTRIBUTED SERVICES
    Microservices, internal APIs, RPC.

LAYER 7: ASYNCHRONOUS INFRASTRUCTURE
    Queues, event buses, workers.

LAYER 8: DATA
    Databases, caches, search engines, object storage.

LAYER 9: OPERATIONS
    Logging, monitoring, tracing, deployment, backup.

LAYER 10: SECURITY
    Identity, authorization, encryption, secrets, segmentation.

These layers are conceptual. A real architecture may combine or
separate them differently.
""")


# ============================================================
# 154. ARCHITECTURAL ANTI-PATTERNS
# ============================================================

def section_antipatterns():
    title("153. Common Architectural Anti-Patterns")

    anti_patterns = [
        "Single server with no redundancy for a critical service.",
        "Database directly exposed to the public Internet.",
        "No timeout when calling external services.",
        "Unlimited retries.",
        "Retrying non-idempotent operations without protection.",
        "Caching sensitive personalized responses incorrectly.",
        "Using one database for unrelated high-scale workloads.",
        "Creating microservices without clear boundaries.",
        "Making every small operation a separate service.",
        "Logging sensitive secrets.",
        "No centralized observability.",
        "No database backup verification.",
        "Scaling application servers while ignoring database bottlenecks.",
        "Using synchronous calls for every background operation.",
        "Allowing one tenant to consume unlimited shared resources.",
        "Deploying incompatible service versions simultaneously.",
        "Assuming internal network traffic is automatically trustworthy."
    ]

    for item in anti_patterns:
        bullet(item)


# ============================================================
# 155. WEB ARCHITECTURE TERMINOLOGY
# ============================================================

def section_terminology():
    title("154. Important Web Architecture Terminology")

    terms = {
        "Origin":
            "Combination of scheme, host, and port.",
        "Endpoint":
            "A network-accessible API operation or resource.",
        "Stateless":
            "Each request contains the information needed for processing.",
        "Stateful":
            "The server maintains state across interactions.",
        "Latency":
            "Time required to complete an operation.",
        "Throughput":
            "Amount of work processed per unit time.",
        "Availability":
            "Proportion of time a service is operational.",
        "Scalability":
            "Ability to handle increasing workload by adding resources.",
        "Durability":
            "Ability to preserve data despite failures.",
        "Replication":
            "Maintaining multiple copies of data.",
        "Sharding":
            "Partitioning data across multiple nodes.",
        "Caching":
            "Storing reusable results closer to consumers.",
        "Queue":
            "Buffer for asynchronous work.",
        "Load Balancer":
            "Distributes requests across backend instances.",
        "Reverse Proxy":
            "Proxy representing backend servers to clients.",
        "CDN":
            "Distributed infrastructure for delivering content closer to users.",
        "API Gateway":
            "Controlled entry point for backend APIs.",
        "Service Discovery":
            "Mechanism for locating service instances.",
        "Circuit Breaker":
            "Prevents repeated calls to an unhealthy dependency.",
        "Observability":
            "Ability to understand system behavior from telemetry."
    }

    for term, meaning in terms.items():
        print(f"{term:20} -> {meaning}")


# ============================================================
# 156. FINAL TECHNICAL MODEL
# ============================================================

def section_final_model():
    title("155. Integrated Mental Model of Web Architecture")

    explain("""
The complete mental model can be expressed as:

USER
 |
 v
CLIENT
 |
 v
DNS
 |
 v
NETWORK
 |
 v
TLS
 |
 v
HTTP
 |
 v
CDN / EDGE
 |
 v
LOAD BALANCER
 |
 v
REVERSE PROXY / API GATEWAY
 |
 v
APPLICATION
 |
 +--------------------+
 |                    |
 v                    v
CACHE               SERVICES
 |                    |
 |              +-----+-----+
 |              |           |
 v              v           v
DATABASE       QUEUE      SEARCH
 |              |           |
 +------+-------+-----------+
        |
        v
  PERSISTENT STORAGE

Around every layer:

    SECURITY
    LOGGING
    METRICS
    TRACING
    BACKUPS
    DEPLOYMENT
    FAILURE RECOVERY

The architecture is not merely a collection of technologies.

It is a set of relationships.

Each component exists to perform a responsibility, and each boundary
creates both a benefit and a cost.

A cache provides speed but introduces freshness concerns.

A queue provides decoupling but introduces asynchronous behavior.

A replica provides availability and read capacity but can introduce lag.

A microservice provides independent deployment but introduces
network communication and distributed-system complexity.

A CDN reduces latency but introduces another caching layer.

A load balancer improves availability but becomes infrastructure
that itself must be highly available.

A database provides durable state but can become a scaling bottleneck.

Web architecture is therefore the discipline of organizing these
components so that the complete system satisfies its functional,
performance, security, scalability, availability, and operational
requirements.
""")


# ============================================================
# 157. RUN ALL SECTIONS
# ============================================================

def main():
    """
    Execute the complete Web Architecture learning program.
    """

    sections = [
        section_what_is_web_architecture,
        section_client_server,
        section_url,
        section_dns,
        section_network_stack,
        section_tcp_udp,
        section_http,
        section_http_methods,
        section_status_codes,
        section_headers,
        section_cookies_sessions,
        section_auth,
        section_request_lifecycle,
        section_three_tier,
        section_n_tier,
        section_monolith,
        section_modular_monolith,
        section_microservices,
        section_soa,
        section_api,
        section_rest,
        section_graphql,
        section_rpc,
        section_web_server,
        section_reverse_proxy,
        section_forward_proxy,
        section_load_balancing,
        section_load_algorithms,
        section_scaling,
        section_autoscaling,
        section_caching,
        section_cache_strategies,
        section_cache_eviction,
        section_cdn,
        section_database,
        section_sql_nosql,
        section_replication,
        section_read_replicas,
        section_sharding,
        section_connection_pooling,
        section_transactions,
        section_cap,
        section_consistency,
        section_message_queue,
        section_event_driven,
        section_pubsub,
        section_async,
        section_websockets,
        section_sse,
        section_long_polling,
        section_background_jobs,
        section_object_storage,
        section_search,
        section_rate_limiting,
        section_idempotency,
        section_retries,
        section_circuit_breaker,
        section_timeouts,
        section_health_checks,
        section_observability,
        section_logging,
        section_metrics,
        section_tracing,
        section_security,
        section_https,
        section_jwt,
        section_oauth,
        section_cors,
        section_csrf,
        section_xss,
        section_sql_injection,
        section_ddos,
        section_secrets,
        section_zero_trust,
        section_deployment,
        section_containers,
        section_orchestration,
        section_cicd,
        section_blue_green,
        section_canary,
        section_rolling,
        section_high_availability,
        section_fault_tolerance,
        section_disaster_recovery,
        section_multi_region,
        section_latency,
        section_throughput,
        section_availability,
        section_reliability,
        section_performance,
        section_bottlenecks,
        section_backpressure,
        section_graceful_degradation,
        section_service_discovery,
        section_api_gateway,
        section_bff,
        section_indexes,
        section_normalization,
        section_isolation,
        section_distributed_transactions,
        section_eventual_consistency_example,
        section_layered_cache,
        section_request_collapsing,
        section_hot_keys,
        section_file_upload,
        section_static_dynamic,
        section_rendering,
        section_http_versions,
        section_compression,
        section_batching,
        section_n_plus_one,
        section_api_versioning,
        section_backward_compatibility,
        section_schema_evolution,
        section_data_ownership,
        section_cqrs,
        section_event_sourcing,
        section_feature_flags,
        section_multitenancy,
        section_tenant_limits,
        section_complete_architecture,
        section_request_walkthrough,
        section_failure_scenarios,
        section_bottleneck_analysis,
        section_capacity,
        section_queueing,
        section_spof,
        section_security_boundaries,
        section_network_segmentation,
        section_least_privilege,
        section_request_id,
        section_encryption,
        section_backup,
        section_dr_strategies,
        section_tradeoffs,
        section_monolith_vs_microservices,
        section_sync_async,
        section_edge,
        section_cloud,
        section_serverless,
        section_webhooks,
        section_api_retry,
        section_data_control_flow,
        section_domain_boundaries,
        section_chat_architecture,
        section_ecommerce,
        section_social_media,
        section_feed,
        section_autocomplete,
        section_simulation,
        section_architecture_reasoning,
        section_architecture_layers,
        section_antipatterns,
        section_terminology,
        section_final_model
    ]

    print("\n")
    print("#" * 80)
    print("# WEB ARCHITECTURE")
    print("# Complete Academic Learning Program")
    print("#" * 80)

    for section in sections:
        section()

    print("\n")
    print("#" * 80)
    print("# END OF WEB ARCHITECTURE MATERIAL")
    print("#" * 80)


if __name__ == "__main__":
    main()
