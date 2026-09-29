"""
REST Architecture: Resources, Representations, Statelessness, and Uniform Interface
====================================================================================

A self-contained educational implementation of REST principles using only the
Python standard library.

The example models a small Book Catalog API without requiring an external web
framework. It demonstrates:

- Resources and resource identifiers
- Representations
- HTTP methods and semantics
- Statelessness
- Uniform interface
- Resource-oriented URL design
- CRUD operations
- Content negotiation
- Conditional requests with ETags
- HTTP status codes
- Idempotency
- Cache-related concepts
- Hypermedia links
- Validation and error representations
- Authentication context without server-side session state
- Pagination and filtering
- Concurrency considerations
- Security considerations
- Testing and performance observations

The implementation uses a miniature HTTP server based on Python's standard
library so that the mechanics remain visible rather than being hidden by a
framework.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import unittest
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse


# ============================================================================
# 1. FUNDAMENTAL REST TERMINOLOGY
# ============================================================================

def explain_rest_concepts() -> None:
    """Print the major REST concepts before running the executable examples."""
    concepts = {
        "Resource": (
            "A conceptual entity identified by a URI, such as /books/42."
        ),
        "Representation": (
            "A transferable representation of a resource, commonly JSON."
        ),
        "Statelessness": (
            "Each request contains the information needed to process it; "
            "the server does not depend on conversational session state."
        ),
        "Uniform interface": (
            "Clients interact through consistent resource identification, "
            "representations, self-descriptive messages, and hypermedia."
        ),
        "HTTP method": (
            "A standardized operation semantic such as GET, POST, PUT, "
            "PATCH, or DELETE."
        ),
        "Idempotency": (
            "Repeating an operation produces the same intended server state "
            "as performing it once, for methods where HTTP defines that property."
        ),
        "Safe method": (
            "A method intended for retrieval without requesting a state change."
        ),
    }

    print("=" * 80)
    print("REST ARCHITECTURE FUNDAMENTALS")
    print("=" * 80)

    for name, description in concepts.items():
        print(f"{name:22}: {description}")

    print()


# ============================================================================
# 2. RESOURCE MODEL
# ============================================================================

@dataclass
class Book:
    """Domain resource represented internally by the server."""

    id: int
    title: str
    author: str
    year: int
    genre: str
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_representation(self, base_url: str) -> dict[str, Any]:
        """
        Convert the domain resource into a JSON-compatible representation.

        The internal version and timestamps are not necessarily part of the
        public representation. REST does not require exposing the server's
        internal object structure.
        """
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "genre": self.genre,
            "links": {
                "self": f"{base_url}/books/{self.id}",
                "collection": f"{base_url}/books",
            },
        }


# ============================================================================
# 3. RESOURCE STORE
# ============================================================================

class BookStore:
    """
    Thread-safe in-memory resource store.

    In a production service, this responsibility would usually be delegated
    to a database or another durable persistence system.
    """

    def __init__(self) -> None:
        self._books: dict[int, Book] = {}
        self._next_id = 1
        self._lock = threading.RLock()

    def list_books(
        self,
        *,
        author: Optional[str] = None,
        genre: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Book]:
        with self._lock:
            books = list(self._books.values())

            if author:
                books = [
                    book for book in books
                    if book.author.casefold() == author.casefold()
                ]

            if genre:
                books = [
                    book for book in books
                    if book.genre.casefold() == genre.casefold()
                ]

            books.sort(key=lambda book: book.id)
            return books[offset:offset + limit]

    def count(
        self,
        *,
        author: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> int:
        return len(
            self.list_books(
                author=author,
                genre=genre,
                limit=max(len(self._books), 1),
                offset=0,
            )
        )

    def get(self, book_id: int) -> Optional[Book]:
        with self._lock:
            return self._books.get(book_id)

    def create(
        self,
        title: str,
        author: str,
        year: int,
        genre: str,
    ) -> Book:
        with self._lock:
            now = time.time()
            book = Book(
                id=self._next_id,
                title=title,
                author=author,
                year=year,
                genre=genre,
                created_at=now,
                updated_at=now,
            )
            self._books[self._next_id] = book
            self._next_id += 1
            return book

    def replace(
        self,
        book_id: int,
        title: str,
        author: str,
        year: int,
        genre: str,
    ) -> Optional[Book]:
        with self._lock:
            book = self._books.get(book_id)

            if book is None:
                return None

            book.title = title
            book.author = author
            book.year = year
            book.genre = genre
            book.version += 1
            book.updated_at = time.time()
            return book

    def patch(
        self,
        book_id: int,
        changes: dict[str, Any],
    ) -> Optional[Book]:
        with self._lock:
            book = self._books.get(book_id)

            if book is None:
                return None

            for field_name in ("title", "author", "year", "genre"):
                if field_name in changes:
                    setattr(book, field_name, changes[field_name])

            book.version += 1
            book.updated_at = time.time()
            return book

    def delete(self, book_id: int) -> bool:
        with self._lock:
            return self._books.pop(book_id, None) is not None


# ============================================================================
# 4. VALIDATION
# ============================================================================

REQUIRED_BOOK_FIELDS = {"title", "author", "year", "genre"}
ALLOWED_BOOK_FIELDS = REQUIRED_BOOK_FIELDS


class ValidationError(ValueError):
    """Raised when a representation violates the resource contract."""


def validate_book_payload(
    payload: Any,
    *,
    partial: bool = False,
) -> dict[str, Any]:
    """
    Validate an incoming representation.

    A real API should validate at the boundary before changing domain state.
    """
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")

    if partial:
        unknown = set(payload) - ALLOWED_BOOK_FIELDS
        if unknown:
            raise ValidationError(
                f"Unknown fields: {', '.join(sorted(unknown))}"
            )

        if not payload:
            raise ValidationError("PATCH requires at least one field.")
    else:
        missing = REQUIRED_BOOK_FIELDS - set(payload)
        unknown = set(payload) - ALLOWED_BOOK_FIELDS

        if missing:
            raise ValidationError(
                f"Missing fields: {', '.join(sorted(missing))}"
            )

        if unknown:
            raise ValidationError(
                f"Unknown fields: {', '.join(sorted(unknown))}"
            )

    if "title" in payload:
        if not isinstance(payload["title"], str) or not payload["title"].strip():
            raise ValidationError("title must be a non-empty string.")

    if "author" in payload:
        if not isinstance(payload["author"], str) or not payload["author"].strip():
            raise ValidationError("author must be a non-empty string.")

    if "genre" in payload:
        if not isinstance(payload["genre"], str) or not payload["genre"].strip():
            raise ValidationError("genre must be a non-empty string.")

    if "year" in payload:
        if (
            not isinstance(payload["year"], int)
            or isinstance(payload["year"], bool)
            or not 0 < payload["year"] <= 3000
        ):
            raise ValidationError("year must be an integer between 1 and 3000.")

    return payload


# ============================================================================
# 5. REPRESENTATIONS AND ETAGS
# ============================================================================

def canonical_json(data: Any) -> str:
    """Produce deterministic JSON suitable for hashing."""
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def calculate_etag(book: Book, base_url: str) -> str:
    """
    An ETag identifies a representation version.

    The quotes follow the normal HTTP ETag representation syntax.
    """
    representation = canonical_json(book.to_representation(base_url))
    digest = hashlib.sha256(representation.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def json_bytes(data: Any) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


# ============================================================================
# 6. API APPLICATION
# ============================================================================

class RestApplication:
    """
    Resource-oriented application layer.

    The application is deliberately independent of the HTTP handler. This
    separation makes the resource rules easier to test.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.store = BookStore()
        self.base_url = base_url.rstrip("/")

    def seed(self) -> None:
        self.store.create(
            "The Pragmatic Programmer",
            "Andrew Hunt",
            1999,
            "software",
        )
        self.store.create(
            "Clean Architecture",
            "Robert C. Martin",
            2017,
            "software",
        )
        self.store.create(
            "Designing Data-Intensive Applications",
            "Martin Kleppmann",
            2017,
            "data",
        )

    def route(
        self,
        method: str,
        path: str,
        *,
        query: Optional[dict[str, list[str]]] = None,
        body: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict[str, str], Any]:
        """
        Process an HTTP-like request without requiring a network connection.

        Returning status, headers, and representation makes the REST mechanics
        visible and easy to unit-test.
        """
        query = query or {}
        headers = {key.lower(): value for key, value in (headers or {}).items()}

        normalized_path = path.rstrip("/") or "/"

        if normalized_path == "/":
            return self._response(
                200,
                {
                    "service": "REST Book API",
                    "links": {
                        "books": f"{self.base_url}/books",
                    },
                },
            )

        if normalized_path == "/books":
            return self._books_collection(
                method,
                query,
                body,
                headers,
            )

        match = re.fullmatch(r"/books/([0-9]+)", normalized_path)

        if match:
            return self._single_book(
                method,
                int(match.group(1)),
                body,
                headers,
            )

        return self._error(
            404,
            "not_found",
            "The requested resource does not exist.",
        )

    def _books_collection(
        self,
        method: str,
        query: dict[str, list[str]],
        body: Optional[Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], Any]:
        if method == "GET":
            try:
                limit = self._integer_query(query, "limit", 20)
                offset = self._integer_query(query, "offset", 0)

                if limit < 1 or limit > 100:
                    raise ValidationError("limit must be between 1 and 100.")

                if offset < 0:
                    raise ValidationError("offset cannot be negative.")

                author = self._first_query_value(query, "author")
                genre = self._first_query_value(query, "genre")

                books = self.store.list_books(
                    author=author,
                    genre=genre,
                    limit=limit,
                    offset=offset,
                )

                total = self.store.count(author=author, genre=genre)

                representation = {
                    "items": [
                        book.to_representation(self.base_url)
                        for book in books
                    ],
                    "pagination": {
                        "offset": offset,
                        "limit": limit,
                        "count": len(books),
                        "total": total,
                    },
                    "links": {
                        "self": (
                            f"{self.base_url}/books"
                            f"?offset={offset}&limit={limit}"
                        )
                    },
                }

                if offset + limit < total:
                    representation["links"]["next"] = (
                        f"{self.base_url}/books"
                        f"?offset={offset + limit}&limit={limit}"
                    )

                if offset > 0:
                    previous_offset = max(offset - limit, 0)
                    representation["links"]["previous"] = (
                        f"{self.base_url}/books"
                        f"?offset={previous_offset}&limit={limit}"
                    )

                return self._response(
                    200,
                    representation,
                    extra_headers={"Cache-Control": "no-cache"},
                )

            except ValidationError as exc:
                return self._error(400, "invalid_query", str(exc))

        if method == "POST":
            try:
                payload = validate_book_payload(body, partial=False)

                book = self.store.create(
                    payload["title"].strip(),
                    payload["author"].strip(),
                    payload["year"],
                    payload["genre"].strip(),
                )

                representation = book.to_representation(self.base_url)

                return self._response(
                    201,
                    representation,
                    extra_headers={
                        "Location": f"{self.base_url}/books/{book.id}",
                        "ETag": calculate_etag(book, self.base_url),
                        "Cache-Control": "no-cache",
                    },
                )

            except ValidationError as exc:
                return self._error(400, "invalid_representation", str(exc))

        return self._error(
            405,
            "method_not_allowed",
            "The method is not supported for this resource.",
            extra_headers={"Allow": "GET, POST"},
        )

    def _single_book(
        self,
        method: str,
        book_id: int,
        body: Optional[Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], Any]:
        book = self.store.get(book_id)

        if method == "GET":
            if book is None:
                return self._error(
                    404,
                    "not_found",
                    "Book does not exist.",
                )

            etag = calculate_etag(book, self.base_url)

            if headers.get("if-none-match") == etag:
                return 304, {"ETag": etag}, None

            return self._response(
                200,
                book.to_representation(self.base_url),
                extra_headers={
                    "ETag": etag,
                    "Cache-Control": "max-age=60",
                },
            )

        if method == "PUT":
            if book is None:
                return self._error(
                    404,
                    "not_found",
                    "Book does not exist.",
                )

            if_match = headers.get("if-match")
            current_etag = calculate_etag(book, self.base_url)

            if if_match and if_match != current_etag:
                return self._error(
                    412,
                    "precondition_failed",
                    "The representation changed before this replacement.",
                )

            try:
                payload = validate_book_payload(body, partial=False)

                updated = self.store.replace(
                    book_id,
                    payload["title"].strip(),
                    payload["author"].strip(),
                    payload["year"],
                    payload["genre"].strip(),
                )

                assert updated is not None

                return self._response(
                    200,
                    updated.to_representation(self.base_url),
                    extra_headers={
                        "ETag": calculate_etag(updated, self.base_url),
                    },
                )

            except ValidationError as exc:
                return self._error(400, "invalid_representation", str(exc))

        if method == "PATCH":
            if book is None:
                return self._error(
                    404,
                    "not_found",
                    "Book does not exist.",
                )

            if_match = headers.get("if-match")
            current_etag = calculate_etag(book, self.base_url)

            if if_match and if_match != current_etag:
                return self._error(
                    412,
                    "precondition_failed",
                    "The representation changed before this update.",
                )

            try:
                payload = validate_book_payload(body, partial=True)

                # Normalize string values before storing them.
                normalized = dict(payload)

                for field_name in ("title", "author", "genre"):
                    if field_name in normalized:
                        normalized[field_name] = normalized[field_name].strip()

                updated = self.store.patch(book_id, normalized)
                assert updated is not None

                return self._response(
                    200,
                    updated.to_representation(self.base_url),
                    extra_headers={
                        "ETag": calculate_etag(updated, self.base_url),
                    },
                )

            except ValidationError as exc:
                return self._error(400, "invalid_patch", str(exc))

        if method == "DELETE":
            if book is None:
                # DELETE is idempotent at the state level: after the resource
                # is absent, repeating DELETE does not make it more absent.
                return 204, {}, None

            if_match = headers.get("if-match")
            current_etag = calculate_etag(book, self.base_url)

            if if_match and if_match != current_etag:
                return self._error(
                    412,
                    "precondition_failed",
                    "The representation changed before deletion.",
                )

            self.store.delete(book_id)
            return 204, {}, None

        return self._error(
            405,
            "method_not_allowed",
            "The method is not supported for this resource.",
            extra_headers={"Allow": "GET, PUT, PATCH, DELETE"},
        )

    @staticmethod
    def _first_query_value(
        query: dict[str, list[str]],
        name: str,
    ) -> Optional[str]:
        values = query.get(name, [])
        return values[0] if values else None

    @staticmethod
    def _integer_query(
        query: dict[str, list[str]],
        name: str,
        default: int,
    ) -> int:
        value = RestApplication._first_query_value(query, name)

        if value is None:
            return default

        try:
            return int(value)
        except ValueError as exc:
            raise ValidationError(f"{name} must be an integer.") from exc

    @staticmethod
    def _response(
        status: int,
        representation: Any,
        *,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict[str, str], Any]:
        response_headers = {
            "Content-Type": "application/json; charset=utf-8",
        }

        if extra_headers:
            response_headers.update(extra_headers)

        return status, response_headers, representation

    @staticmethod
    def _error(
        status: int,
        error_code: str,
        message: str,
        *,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict[str, str], Any]:
        representation = {
            "error": {
                "code": error_code,
                "message": message,
            }
        }

        return RestApplication._response(
            status,
            representation,
            extra_headers=extra_headers,
        )


# ============================================================================
# 7. HTTP ADAPTER
# ============================================================================

class RestRequestHandler(BaseHTTPRequestHandler):
    """
    Translate actual HTTP messages into calls to RestApplication.

    HTTP transport is an implementation detail. The application itself remains
    resource-oriented.
    """

    application: RestApplication

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PUT(self) -> None:
        self._handle_request("PUT")

    def do_PATCH(self) -> None:
        self._handle_request("PATCH")

    def do_DELETE(self) -> None:
        self._handle_request("DELETE")

    def _handle_request(self, method: str) -> None:
        parsed = urlparse(self.path)

        query = parse_qs(parsed.query)

        headers = {
            key.lower(): value
            for key, value in self.headers.items()
        }

        body = None

        if method in {"POST", "PUT", "PATCH"}:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))

                if content_length > 1_000_000:
                    self._write_error(413, "request_too_large")
                    return

                raw_body = self.rfile.read(content_length)

                if raw_body:
                    body = json.loads(raw_body.decode("utf-8"))

            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self._write_error(
                    400,
                    "invalid_json",
                    "Request body must contain valid UTF-8 JSON.",
                )
                return

        status, response_headers, representation = self.application.route(
            method,
            parsed.path,
            query=query,
            body=body,
            headers=headers,
        )

        self.send_response(status)

        for key, value in response_headers.items():
            self.send_header(key, value)

        if representation is not None:
            payload = json_bytes(representation)
            self.send_header("Content-Length", str(len(payload)))
        else:
            payload = b""
            self.send_header("Content-Length", "0")

        self.end_headers()

        if payload:
            self.wfile.write(payload)

    def _write_error(
        self,
        status: int,
        code: str,
        message: str = "Request could not be processed.",
    ) -> None:
        payload = json_bytes({
            "error": {
                "code": code,
                "message": message,
            }
        })

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format_string: str, *args: Any) -> None:
        # Keep demonstration output focused.
        return


# ============================================================================
# 8. IN-PROCESS REST EXAMPLES
# ============================================================================

def demonstrate_resource_interactions() -> None:
    app = RestApplication()
    app.seed()

    print("=" * 80)
    print("RESOURCE INTERACTIONS")
    print("=" * 80)

    status, headers, body = app.route("GET", "/books")
    print("GET /books")
    print("Status:", status)
    print(json.dumps(body, indent=2))
    print()

    status, headers, body = app.route(
        "GET",
        "/books",
        query={"genre": ["software"], "limit": ["2"]},
    )
    print("GET /books?genre=software&limit=2")
    print("Status:", status)
    print(json.dumps(body, indent=2))
    print()

    status, headers, body = app.route(
        "POST",
        "/books",
        body={
            "title": "RESTful Web Services",
            "author": "Leonard Richardson",
            "year": 2007,
            "genre": "web",
        },
    )
    print("POST /books")
    print("Status:", status)
    print("Location:", headers.get("Location"))
    print(json.dumps(body, indent=2))
    print()

    created_id = body["id"]

    status, headers, body = app.route(
        "GET",
        f"/books/{created_id}",
    )
    print(f"GET /books/{created_id}")
    print("Status:", status)
    print("ETag:", headers.get("ETag"))
    print(json.dumps(body, indent=2))
    print()

    etag = headers["ETag"]

    status, headers, body = app.route(
        "GET",
        f"/books/{created_id}",
        headers={"If-None-Match": etag},
    )
    print("Conditional GET with matching ETag")
    print("Status:", status)
    print("Body:", body)
    print()

    status, headers, body = app.route(
        "PATCH",
        f"/books/{created_id}",
        headers={"If-Match": etag},
        body={"genre": "web-architecture"},
    )
    print("PATCH /books/{id}")
    print("Status:", status)
    print(json.dumps(body, indent=2))
    print()

    status, headers, body = app.route(
        "DELETE",
        f"/books/{created_id}",
    )
    print("DELETE /books/{id}")
    print("Status:", status)
    print("Body:", body)
    print()


# ============================================================================
# 9. REST PRINCIPLES DEMONSTRATED AS DATA
# ============================================================================

def demonstrate_rest_constraints() -> None:
    """
    REST is an architectural style defined through constraints.

    The constraints are not merely a list of HTTP methods.
    """
    constraints = [
        (
            "Client-server",
            "Separate user interface concerns from data/storage concerns.",
        ),
        (
            "Stateless",
            "Every request is self-contained from the server's perspective.",
        ),
        (
            "Cacheable",
            "Responses should explicitly indicate whether they can be reused.",
        ),
        (
            "Uniform interface",
            "Use consistent resource identifiers, representations, "
            "messages, and hypermedia.",
        ),
        (
            "Layered system",
            "A client need not know whether it communicates directly with "
            "the origin server or through intermediaries.",
        ),
        (
            "Code-on-demand",
            "Optional REST constraint allowing executable code to be "
            "transferred to clients.",
        ),
    ]

    print("=" * 80)
    print("REST ARCHITECTURAL CONSTRAINTS")
    print("=" * 80)

    for name, explanation in constraints:
        print(f"{name:20}: {explanation}")

    print()


# ============================================================================
# 10. HTTP SEMANTICS
# ============================================================================

def demonstrate_http_method_semantics() -> None:
    methods = {
        "GET": {
            "purpose": "Retrieve a representation.",
            "safe": True,
            "idempotent": True,
        },
        "HEAD": {
            "purpose": "Retrieve headers corresponding to GET without a body.",
            "safe": True,
            "idempotent": True,
        },
        "POST": {
            "purpose": "Submit data for resource-specific processing.",
            "safe": False,
            "idempotent": False,
        },
        "PUT": {
            "purpose": "Replace or create a representation at a known URI.",
            "safe": False,
            "idempotent": True,
        },
        "PATCH": {
            "purpose": "Apply partial modifications.",
            "safe": False,
            "idempotent": "Not inherently",
        },
        "DELETE": {
            "purpose": "Remove a resource.",
            "safe": False,
            "idempotent": True,
        },
    }

    print("=" * 80)
    print("HTTP METHOD SEMANTICS")
    print("=" * 80)

    for method, properties in methods.items():
        print(method)
        for key, value in properties.items():
            print(f"  {key}: {value}")

    print()


# ============================================================================
# 11. STATELESSNESS DEMONSTRATION
# ============================================================================

def demonstrate_statelessness() -> None:
    """
    A stateless API does not require a server-side conversational object such
    as "current page for this user" or "last selected book".

    Each request contains its own URI and query information.
    Authentication credentials would likewise accompany each request, usually
    through an Authorization header or another standardized mechanism.
    """
    app = RestApplication()
    app.seed()

    first_request = app.route(
        "GET",
        "/books/1",
    )

    second_request = app.route(
        "GET",
        "/books/2",
    )

    print("=" * 80)
    print("STATELESSNESS")
    print("=" * 80)
    print("First request:")
    print(json.dumps(first_request[2], indent=2))
    print()
    print("Independent second request:")
    print(json.dumps(second_request[2], indent=2))
    print()
    print(
        "The server does not need to remember that the first request occurred "
        "in order to understand the second request."
    )
    print()


# ============================================================================
# 12. ERROR HANDLING AND STATUS CODES
# ============================================================================

def demonstrate_errors() -> None:
    app = RestApplication()
    app.seed()

    print("=" * 80)
    print("ERROR HANDLING")
    print("=" * 80)

    examples = [
        (
            "GET /books/999",
            app.route("GET", "/books/999"),
        ),
        (
            "POST /books with missing fields",
            app.route(
                "POST",
                "/books",
                body={"title": "Incomplete"},
            ),
        ),
        (
            "GET /unknown",
            app.route("GET", "/unknown"),
        ),
        (
            "DELETE /books/999",
            app.route("DELETE", "/books/999"),
        ),
    ]

    for description, response in examples:
        status, headers, body = response
        print(description)
        print("Status:", status)
        print("Body:", json.dumps(body, indent=2) if body else None)
        print()


# ============================================================================
# 13. OPTIMISTIC CONCURRENCY CONTROL
# ============================================================================

def demonstrate_optimistic_concurrency() -> None:
    """
    ETags can prevent lost updates.

    Client A reads version A.
    Client B changes the resource.
    Client A attempts an update using the stale ETag.
    The server rejects the stale update with 412.
    """
    app = RestApplication()
    app.seed()

    status, headers, body = app.route("GET", "/books/1")
    stale_etag = headers["ETag"]

    app.route(
        "PATCH",
        "/books/1",
        headers={"If-Match": stale_etag},
        body={"genre": "changed-by-client-b"},
    )

    status, headers, body = app.route(
        "PATCH",
        "/books/1",
        headers={"If-Match": stale_etag},
        body={"genre": "stale-client-update"},
    )

    print("=" * 80)
    print("OPTIMISTIC CONCURRENCY CONTROL")
    print("=" * 80)
    print("Stale update status:", status)
    print(json.dumps(body, indent=2))
    print()


# ============================================================================
# 14. PERFORMANCE CONSIDERATIONS
# ============================================================================

def demonstrate_complexity() -> None:
    """
    The in-memory list implementation uses linear scanning for filtering.

    A database-backed production implementation could use indexes for fields
    such as author and genre.

    Pagination limits response size but does not automatically make a database
    query efficient. Offset pagination can become expensive for large offsets;
    cursor/keyset pagination can be preferable for large changing datasets.
    """
    print("=" * 80)
    print("PERFORMANCE CONSIDERATIONS")
    print("=" * 80)
    print("In-memory lookup by ID: average O(1)")
    print("Filtering the dictionary values: O(n)")
    print("Sorting the collection: O(n log n)")
    print("Pagination after sorting: O(n log n) in this simple implementation")
    print("Production database indexes can reduce filtering cost.")
    print("Cursor pagination can avoid expensive large offsets.")
    print()


# ============================================================================
# 15. SECURITY CONSIDERATIONS
# ============================================================================

def demonstrate_security_considerations() -> None:
    """
    Security is not a REST constraint, but a production REST API must address
    security independently.
    """
    controls = [
        "Use HTTPS/TLS in production.",
        "Authenticate clients with an appropriate mechanism.",
        "Authorize every protected resource operation.",
        "Validate request bodies, query parameters, and path parameters.",
        "Apply request-size limits.",
        "Rate-limit sensitive or expensive operations.",
        "Avoid exposing secrets in representations or logs.",
        "Use safe serialization and avoid unsafe object deserialization.",
        "Configure CORS intentionally rather than allowing every origin blindly.",
        "Return appropriate security headers at the HTTP layer.",
        "Avoid leaking internal database or stack-trace details.",
        "Use audit logging for security-sensitive actions.",
    ]

    print("=" * 80)
    print("SECURITY CONSIDERATIONS")
    print("=" * 80)

    for index, control in enumerate(controls, start=1):
        print(f"{index:2}. {control}")

    print()


# ============================================================================
# 16. UNIT TESTS
# ============================================================================

class RestApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = RestApplication()
        self.app.seed()

    def test_list_books(self) -> None:
        status, _, body = self.app.route("GET", "/books")

        self.assertEqual(status, 200)
        self.assertEqual(body["pagination"]["total"], 3)

    def test_create_book(self) -> None:
        status, headers, body = self.app.route(
            "POST",
            "/books",
            body={
                "title": "Example",
                "author": "Author",
                "year": 2026,
                "genre": "testing",
            },
        )

        self.assertEqual(status, 201)
        self.assertIn("Location", headers)
        self.assertEqual(body["title"], "Example")

    def test_missing_book(self) -> None:
        status, _, body = self.app.route("GET", "/books/9999")

        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_conditional_get(self) -> None:
        status, headers, _ = self.app.route("GET", "/books/1")
        etag = headers["ETag"]

        status, headers, body = self.app.route(
            "GET",
            "/books/1",
            headers={"If-None-Match": etag},
        )

        self.assertEqual(status, 304)
        self.assertIsNone(body)
        self.assertEqual(headers["ETag"], etag)

    def test_put_is_repeatable_for_same_representation(self) -> None:
        payload = {
            "title": "Stable",
            "author": "Author",
            "year": 2026,
            "genre": "test",
        }

        status_1, _, body_1 = self.app.route(
            "PUT",
            "/books/1",
            body=payload,
        )

        status_2, _, body_2 = self.app.route(
            "PUT",
            "/books/1",
            body=payload,
        )

        self.assertEqual(status_1, 200)
        self.assertEqual(status_2, 200)
        self.assertEqual(body_1["title"], body_2["title"])
        self.assertEqual(body_1["author"], body_2["author"])

    def test_delete_is_idempotent(self) -> None:
        status_1, _, _ = self.app.route("DELETE", "/books/1")
        status_2, _, _ = self.app.route("DELETE", "/books/1")

        self.assertEqual(status_1, 204)
        self.assertEqual(status_2, 204)

    def test_invalid_payload(self) -> None:
        status, _, body = self.app.route(
            "POST",
            "/books",
            body={
                "title": "",
                "author": "Author",
                "year": 2026,
                "genre": "test",
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_representation")


# ============================================================================
# 17. OPTIONAL SERVER
# ============================================================================

def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """
    Start the demonstration HTTP server.

    Example requests:
        GET    /books
        GET    /books/1
        POST   /books
        PUT    /books/1
        PATCH  /books/1
        DELETE /books/1

    Use Ctrl+C to stop the server.
    """
    application = RestApplication(
        base_url=f"http://{host}:{port}",
    )
    application.seed()

    class Handler(RestRequestHandler):
        pass

    Handler.application = application

    server = ThreadingHTTPServer((host, port), Handler)

    print(f"REST API listening on http://{host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


# ============================================================================
# 18. COMMAND-LINE ENTRY POINT
# ============================================================================

def main() -> None:
    explain_rest_concepts()
    demonstrate_rest_constraints()
    demonstrate_http_method_semantics()
    demonstrate_resource_interactions()
    demonstrate_statelessness()
    demonstrate_errors()
    demonstrate_optimistic_concurrency()
    demonstrate_complexity()
    demonstrate_security_considerations()

    print("=" * 80)
    print("UNIT TESTS")
    print("=" * 80)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        RestApplicationTests
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)

    print()
    print("Educational demonstrations completed successfully.")
    print()
    print("To run the HTTP server instead, change the final call to:")
    print("    run_server()")


if __name__ == "__main__":
    main()
