# Backend Development & APIs Learning Journey
## 120-Day Roadmap: Beginner → Advanced → Extreme Advanced

| S.No. | Day | Topic | Subtopics Covered | Tools Covered |
|---:|---:|---|---|---|
| 1 | Day 1 | Backend Development Fundamentals | What backend development is, frontend vs backend, responsibilities of a backend, server-side programming, backend architecture, request processing | VS Code, Browser, Terminal |
| 2 | Day 2 | Web Architecture | Client-server architecture, clients, servers, intermediaries, request-response model, network communication | Browser DevTools, Terminal |
| 3 | Day 3 | Internet Fundamentals | Internet, ISP, packets, routing, IP addresses, ports, sockets, TCP/IP basics | Terminal, ping, tracert/traceroute |
| 4 | Day 4 | HTTP Fundamentals | HTTP purpose, requests, responses, methods, headers, body, status codes, HTTP lifecycle | Browser DevTools, cURL |
| 5 | Day 5 | HTTP Methods | GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, idempotency, safe methods | cURL, Postman |
| 6 | Day 6 | HTTP Status Codes | 1xx, 2xx, 3xx, 4xx, 5xx, common errors, choosing appropriate status codes | Postman, cURL |
| 7 | Day 7 | URLs and URIs | URL structure, scheme, host, port, path, query parameters, fragments, URI vs URL | Browser, cURL |
| 8 | Day 8 | HTTP Headers | Request headers, response headers, Content-Type, Accept, Authorization, Cache-Control, cookies | Postman, Browser DevTools |
| 9 | Day 9 | JSON and Data Serialization | JSON syntax, objects, arrays, primitive values, serialization, deserialization, JSON limitations | Python, VS Code |
| 10 | Day 10 | Backend Programming Fundamentals | Variables, functions, modules, packages, exceptions, file handling, environments | Python, VS Code |
| 11 | Day 11 | Python for Backend Development | Python data structures, functions, classes, decorators, iterators, generators, typing | Python, VS Code |
| 12 | Day 12 | Object-Oriented Backend Design | Classes, inheritance, composition, abstraction, encapsulation, polymorphism | Python |
| 13 | Day 13 | Python Virtual Environments | pip, venv, requirements.txt, dependency management, package isolation | Python, pip |
| 14 | Day 14 | Git Fundamentals | repositories, commits, branches, merge, rebase, .gitignore, Git workflow | Git, GitHub |
| 15 | Day 15 | Backend Project Structure | application layers, modules, packages, configuration, services, utilities | Python, VS Code, Git |
| 16 | Day 16 | Web Servers | Web server responsibilities, static files, reverse proxy concept, application servers | Nginx, Python |
| 17 | Day 17 | WSGI and ASGI | WSGI, ASGI, synchronous vs asynchronous servers, application server architecture | Uvicorn, Gunicorn |
| 18 | Day 18 | FastAPI Introduction | FastAPI architecture, application instance, routes, decorators, path operations | FastAPI, Uvicorn |
| 19 | Day 19 | FastAPI Routing | GET routes, POST routes, PUT routes, PATCH routes, DELETE routes, route parameters | FastAPI, Swagger UI |
| 20 | Day 20 | Path and Query Parameters | Path parameters, query parameters, optional parameters, validation, defaults | FastAPI, Pydantic |
| 21 | Day 21 | Request Bodies | JSON request bodies, Pydantic models, nested objects, required vs optional fields | FastAPI, Pydantic |
| 22 | Day 22 | Response Models | Response schemas, serialization, response validation, excluding fields | FastAPI, Pydantic |
| 23 | Day 23 | API Documentation | OpenAPI, Swagger UI, ReDoc, schemas, operation IDs, API metadata | FastAPI, Swagger UI |
| 24 | Day 24 | Pydantic Deep Dive | BaseModel, Field, validators, nested models, constrained values, custom validation | Pydantic |
| 25 | Day 25 | Error Handling | Exceptions, HTTPException, custom exceptions, exception handlers, structured errors | FastAPI |
| 26 | Day 26 | Middleware | Middleware concept, request lifecycle, response interception, custom middleware | FastAPI |
| 27 | Day 27 | Dependency Injection | Dependencies, reusable logic, dependency chains, database dependencies | FastAPI |
| 28 | Day 28 | API Versioning | URL versioning, header versioning, backward compatibility, deprecation strategy | FastAPI |
| 29 | Day 29 | REST Architecture | REST principles, resources, representations, statelessness, uniform interface | FastAPI, Postman |
| 30 | Day 30 | REST API Design | Resource naming, nesting, CRUD conventions, status codes, response structures | FastAPI, Postman |
| 31 | Day 31 | Database Fundamentals | Database concepts, tables, rows, columns, primary keys, relationships | PostgreSQL, pgAdmin |
| 32 | Day 32 | SQL Fundamentals | SELECT, INSERT, UPDATE, DELETE, WHERE, ORDER BY, GROUP BY | PostgreSQL |
| 33 | Day 33 | SQL Joins | INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL JOIN, CROSS JOIN, self joins | PostgreSQL |
| 34 | Day 34 | Database Constraints | PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK, DEFAULT | PostgreSQL |
| 35 | Day 35 | Database Normalization | 1NF, 2NF, 3NF, BCNF, denormalization, practical database design | PostgreSQL |
| 36 | Day 36 | PostgreSQL Advanced Fundamentals | schemas, sequences, UUIDs, enums, JSONB, arrays, extensions | PostgreSQL |
| 37 | Day 37 | Indexing | B-tree, hash, composite indexes, partial indexes, index selectivity | PostgreSQL |
| 38 | Day 38 | Query Optimization | EXPLAIN, EXPLAIN ANALYZE, sequential scans, index scans, query planning | PostgreSQL |
| 39 | Day 39 | Transactions | ACID, BEGIN, COMMIT, ROLLBACK, atomicity, consistency | PostgreSQL |
| 40 | Day 40 | Isolation Levels | Read Uncommitted, Read Committed, Repeatable Read, Serializable | PostgreSQL |
| 41 | Day 41 | Python Database Connectivity | database drivers, connections, cursors, connection lifecycle | psycopg, PostgreSQL |
| 42 | Day 42 | ORM Fundamentals | ORM concept, models, mappings, relationships, advantages and tradeoffs | SQLAlchemy |
| 43 | Day 43 | SQLAlchemy Models | declarative models, columns, primary keys, relationships | SQLAlchemy |
| 44 | Day 44 | SQLAlchemy Queries | SELECT, filtering, joins, ordering, aggregation, pagination | SQLAlchemy |
| 45 | Day 45 | SQLAlchemy Relationships | one-to-one, one-to-many, many-to-many, cascading | SQLAlchemy |
| 46 | Day 46 | Database Migrations | migration concepts, schema evolution, migration history | Alembic |
| 47 | Day 47 | Repository Pattern | repositories, data access abstraction, separation of concerns | FastAPI, SQLAlchemy |
| 48 | Day 48 | Service Layer Architecture | controllers, services, repositories, domain logic | FastAPI, SQLAlchemy |
| 49 | Day 49 | Backend Architecture | layered architecture, modular monolith, clean architecture | FastAPI, PostgreSQL |
| 50 | Day 50 | Project 1: CRUD API | Build production-style CRUD API with validation, database, documentation | FastAPI, PostgreSQL, SQLAlchemy |
| 51 | Day 51 | Authentication Fundamentals | authentication vs authorization, identity, sessions, credentials | FastAPI |
| 52 | Day 52 | Password Security | password hashing, salting, brute-force resistance, secure password storage | Passlib/Argon2 |
| 53 | Day 53 | JWT Fundamentals | JWT structure, header, payload, signature, claims, expiration | Python, JWT |
| 54 | Day 54 | JWT Authentication | access tokens, token validation, protected routes | FastAPI, JWT |
| 55 | Day 55 | Refresh Tokens | access vs refresh tokens, rotation, revocation, token lifecycle | FastAPI, PostgreSQL |
| 56 | Day 56 | OAuth 2.0 | authorization flows, scopes, clients, resource servers, authorization server | FastAPI, OAuth2 |
| 57 | Day 57 | OpenID Connect | identity layer, ID tokens, user info, authentication providers | OAuth2, OIDC |
| 58 | Day 58 | Role-Based Access Control | roles, permissions, resource authorization, admin access | FastAPI |
| 59 | Day 59 | Attribute-Based Access Control | policies, attributes, contextual authorization | FastAPI |
| 60 | Day 60 | API Keys | API key generation, storage, validation, rotation, revocation | FastAPI, PostgreSQL |
| 61 | Day 61 | Web Security Fundamentals | CIA triad, attack surfaces, secure coding, threat modeling | OWASP |
| 62 | Day 62 | OWASP API Security | broken authorization, excessive data exposure, injection, SSRF, security misconfiguration | OWASP |
| 63 | Day 63 | SQL Injection | injection mechanisms, parameterized queries, ORM protection | PostgreSQL, SQLAlchemy |
| 64 | Day 64 | XSS and CSRF | reflected XSS, stored XSS, CSRF, cookies, SameSite | Browser, FastAPI |
| 65 | Day 65 | CORS | same-origin policy, preflight requests, allowed origins, credentials | FastAPI |
| 66 | Day 66 | Rate Limiting | fixed window, sliding window, token bucket, distributed rate limiting | Redis, FastAPI |
| 67 | Day 67 | Input Validation | schema validation, sanitization, boundary validation, malicious inputs | Pydantic |
| 68 | Day 68 | Secure Secrets Management | environment variables, secret rotation, credentials, secret managers | .env, Docker |
| 69 | Day 69 | HTTPS and TLS | encryption, certificates, TLS handshake, HTTPS termination | OpenSSL, Nginx |
| 70 | Day 70 | Secure API Project | Build authentication + authorization + security controls into an API | FastAPI, PostgreSQL, Redis |
| 71 | Day 71 | API Pagination | offset pagination, cursor pagination, keyset pagination | FastAPI, PostgreSQL |
| 72 | Day 72 | Filtering and Searching | filters, search parameters, sorting, dynamic query construction | FastAPI, PostgreSQL |
| 73 | Day 73 | API Response Design | envelopes, metadata, consistency, error schemas | FastAPI |
| 74 | Day 74 | Idempotency | idempotent APIs, idempotency keys, duplicate requests, payment-style workflows | FastAPI, PostgreSQL |
| 75 | Day 75 | API Caching | HTTP caching, Cache-Control, ETags, conditional requests | FastAPI, Redis |
| 76 | Day 76 | Redis Fundamentals | key-value model, strings, hashes, lists, sets, sorted sets | Redis |
| 77 | Day 77 | Redis Caching | cache-aside, write-through, TTL, cache invalidation | Redis, FastAPI |
| 78 | Day 78 | Redis Advanced | pipelines, transactions, Lua scripts, distributed locks | Redis |
| 79 | Day 79 | Background Tasks | asynchronous jobs, task queues, worker processes | Celery, Redis |
| 80 | Day 80 | Message Queues | producers, consumers, brokers, acknowledgments, retries | RabbitMQ |
| 81 | Day 81 | Event-Driven Architecture | events, event producers, consumers, event schemas | RabbitMQ |
| 82 | Day 82 | Kafka Fundamentals | topics, partitions, brokers, producers, consumers, offsets | Apache Kafka |
| 83 | Day 83 | Kafka Advanced | consumer groups, rebalancing, retention, replication | Apache Kafka |
| 84 | Day 84 | Async Python | async/await, coroutines, event loops, concurrency | Python asyncio |
| 85 | Day 85 | Async FastAPI | asynchronous endpoints, async database operations, blocking pitfalls | FastAPI, asyncio |
| 86 | Day 86 | WebSockets | persistent connections, real-time communication, connection lifecycle | FastAPI, WebSockets |
| 87 | Day 87 | Server-Sent Events | streaming responses, event streams, real-time updates | FastAPI |
| 88 | Day 88 | GraphQL Fundamentals | schemas, types, queries, mutations, resolvers | GraphQL, Strawberry |
| 89 | Day 89 | GraphQL Advanced | nested queries, fragments, variables, authorization, N+1 problem | Strawberry, DataLoader |
| 90 | Day 90 | gRPC | RPC model, Protocol Buffers, services, stubs, streaming | gRPC, Protobuf |
| 91 | Day 91 | API Testing Fundamentals | unit tests, integration tests, endpoint testing, test structure | pytest |
| 92 | Day 92 | FastAPI Testing | TestClient, dependency overrides, authentication testing | pytest, FastAPI |
| 93 | Day 93 | Database Testing | test databases, transactions, fixtures, database isolation | pytest, PostgreSQL |
| 94 | Day 94 | Mocking | mocks, stubs, patches, external API simulation | pytest, unittest.mock |
| 95 | Day 95 | Contract Testing | API contracts, consumer-driven contracts, compatibility testing | Pact |
| 96 | Day 96 | Integration Testing | service integration, database integration, queue integration | pytest, Docker |
| 97 | Day 97 | Docker Fundamentals | images, containers, Dockerfiles, volumes, networks | Docker |
| 98 | Day 98 | Docker Compose | multi-container applications, service dependencies, environment configuration | Docker Compose |
| 99 | Day 99 | Production Containerization | multi-stage builds, image optimization, non-root users, health checks | Docker |
| 100 | Day 100 | CI/CD | continuous integration, automated tests, build pipelines, deployment workflows | GitHub Actions |
| 101 | Day 101 | Linux for Backend Engineers | processes, permissions, services, logs, networking, shell scripting | Linux, Bash |
| 102 | Day 102 | Nginx and Reverse Proxies | reverse proxy, load balancing, TLS termination, static files | Nginx |
| 103 | Day 103 | Cloud Fundamentals | compute, storage, networking, regions, availability zones | AWS |
| 104 | Day 104 | Cloud Deployment | deploy API, managed databases, environment configuration | AWS, Docker |
| 105 | Day 105 | Load Balancing | horizontal scaling, health checks, load-balancing algorithms | Nginx, AWS |
| 106 | Day 106 | Kubernetes Fundamentals | pods, deployments, services, namespaces, config maps, secrets | Kubernetes, kubectl |
| 107 | Day 107 | Kubernetes Advanced | ingress, autoscaling, probes, rolling updates, resource limits | Kubernetes |
| 108 | Day 108 | Microservices Architecture | service boundaries, decomposition, communication, service discovery | Docker, FastAPI |
| 109 | Day 109 | Distributed Systems | consistency, availability, partition tolerance, CAP theorem | PostgreSQL, Redis |
| 110 | Day 110 | Distributed Transactions | two-phase commit, sagas, compensating transactions | FastAPI, Kafka |
| 111 | Day 111 | Reliability Engineering | retries, timeouts, circuit breakers, bulkheads, graceful degradation | Python, Redis |
| 112 | Day 112 | Observability | logs, metrics, traces, correlation IDs, structured logging | OpenTelemetry |
| 113 | Day 113 | Monitoring | latency, throughput, error rates, saturation, dashboards, alerts | Prometheus, Grafana |
| 114 | Day 114 | Distributed Tracing | trace IDs, spans, context propagation, service tracing | OpenTelemetry, Jaeger |
| 115 | Day 115 | Performance Engineering | profiling, CPU bottlenecks, memory usage, database bottlenecks, concurrency | Python, py-spy |
| 116 | Day 116 | Advanced API Performance | connection pooling, caching, batching, async I/O, query optimization | FastAPI, PostgreSQL, Redis |
| 117 | Day 117 | High Availability | redundancy, failover, replication, health checks, disaster recovery | PostgreSQL, Kubernetes |
| 118 | Day 118 | System Design | URL shortener, notification system, payment API, file storage API, scalable architecture | Draw.io, AWS, Kafka |
| 119 | Day 119 | Capstone: Production Backend Platform | Build scalable API platform with authentication, PostgreSQL, Redis, queues, WebSockets, testing, Docker, CI/CD, monitoring | FastAPI, PostgreSQL, Redis, Kafka, Docker, GitHub Actions, Prometheus, Grafana |
| 120 | Day 120 | Extreme Backend Engineering | scalability review, security audit, performance tuning, distributed architecture, failure scenarios, disaster recovery, production readiness | Kubernetes, AWS, OpenTelemetry, Grafana, Prometheus |
