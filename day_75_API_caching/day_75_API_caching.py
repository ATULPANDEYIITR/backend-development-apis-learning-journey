#!/usr/bin/env python3
"""
API Caching: HTTP Cache-Control, ETags, Conditional Requests.

Demonstrates:
- HTTP cache directives and freshness calculation.
- ETag generation and validation.
- If-None-Match and If-Modified-Since.
- Conditional GET and HTTP 304 responses.
- Vary-based cache keys.
- no-store, no-cache, private and public policies.
- Stale cache revalidation.
- Concurrent request coalescing.
- Cache invalidation and eviction.
- Security-aware cache isolation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime
from enum import Enum
from typing import Callable, Optional
from urllib.parse import urlsplit


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("api-cache")


class CacheError(Exception):
    pass


class ValidationError(CacheError):
    pass


class CachePolicyError(CacheError):
    pass


class CacheStatus(Enum):
    MISS = "MISS"
    HIT = "HIT"
    REVALIDATED = "REVALIDATED"
    BYPASS = "BYPASS"
    STALE = "STALE"


@dataclass(frozen=True)
class CacheControl:
    max_age: Optional[int] = None
    s_maxage: Optional[int] = None
    no_store: bool = False
    no_cache: bool = False
    private: bool = False
    public: bool = False
    must_revalidate: bool = False
    immutable: bool = False
    stale_while_revalidate: int = 0

    @classmethod
    def parse(cls, header: str) -> "CacheControl":
        if len(header) > 4096:
            raise ValidationError("Cache-Control header is too large")

        directives = {}

        for item in header.split(","):
            item = item.strip()

            if not item:
                continue

            key, separator, value = item.partition("=")
            key = key.strip().lower()

            if key in directives:
                raise ValidationError(
                    f"Duplicate Cache-Control directive: {key}"
                )

            if not key or not key.replace("-", "").isalnum():
                raise ValidationError("Invalid cache directive")

            if separator:
                value = value.strip().strip('"')

            directives[key] = value if separator else True

        def integer(name: str, default=None):
            value = directives.get(name)

            if value is None:
                return default

            try:
                number = int(value)
            except (ValueError, TypeError):
                raise ValidationError(
                    f"Invalid integer directive: {name}"
                )

            if number < 0:
                raise ValidationError(
                    f"Negative directive: {name}"
                )

            return number

        return cls(
            max_age=integer("max-age"),
            s_maxage=integer("s-maxage"),
            no_store="no-store" in directives,
            no_cache="no-cache" in directives,
            private="private" in directives,
            public="public" in directives,
            must_revalidate="must-revalidate" in directives,
            immutable="immutable" in directives,
            stale_while_revalidate=integer(
                "stale-while-revalidate", 0
            )
        )

    def freshness_lifetime(self, shared: bool = True) -> int:
        if shared and self.s_maxage is not None:
            return self.s_maxage

        return self.max_age or 0


@dataclass
class HTTPResponse:
    status: int
    body: Optional[dict]
    headers: dict[str, str] = field(default_factory=dict)

    def json_body(self) -> str:
        return json.dumps(
            self.body,
            sort_keys=True,
            separators=(",", ":")
        )


@dataclass
class CacheEntry:
    response: HTTPResponse
    stored_at: float
    initial_age: float
    etag: Optional[str]
    last_modified: Optional[str]
    vary: tuple[str, ...]
    vary_values: tuple[str, ...]
    freshness: int
    stale_while_revalidate: int
    must_revalidate: bool
    generation: int = 0

    def current_age(self, now: float) -> float:
        return self.initial_age + max(0, now - self.stored_at)

    def fresh(self, now: float) -> bool:
        return self.current_age(now) < self.freshness


def generate_etag(body: dict) -> str:
    serialized = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    digest = hashlib.sha256(serialized).hexdigest()

    return f'"{digest}"'


def parse_http_date(value: Optional[str]) -> Optional[float]:
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def etag_matches(header: str, etag: str) -> bool:
    """Weak comparison is appropriate for If-None-Match on GET/HEAD."""
    if header.strip() == "*":
        return True

    target = etag.removeprefix("W/")

    for candidate in header.split(","):
        candidate = candidate.strip()

        if candidate == "*":
            return True

        if candidate.removeprefix("W/") == target:
            return True

    return False


class OriginServer:
    """Small origin-server simulation with versioned resources."""

    def __init__(self):
        self.resources = {}
        self.lock = threading.RLock()
        self.request_count = 0

    def publish(self, path: str, body: dict) -> None:
        with self.lock:
            if not path.startswith("/"):
                raise ValidationError("Resource path must be absolute")

            if not isinstance(body, dict):
                raise ValidationError("Resource must be a dictionary")

            self.resources[path] = {
                "body": body.copy(),
                "modified": time.time()
            }

    def get(
        self,
        path: str,
        request_headers: Optional[dict] = None
    ) -> HTTPResponse:
        request_headers = {
            k.lower(): v for k, v in
            (request_headers or {}).items()
        }

        with self.lock:
            self.request_count += 1

            resource = self.resources.get(path)

            if resource is None:
                return HTTPResponse(404, {"error": "Not found"})

            body = resource["body"].copy()
            modified = resource["modified"]
            etag = generate_etag(body)

            last_modified = formatdate(
                modified,
                usegmt=True
            )

            headers = {
                "ETag": etag,
                "Last-Modified": last_modified,
                "Cache-Control": "public, max-age=30, s-maxage=60",
                "Content-Type": "application/json"
            }

            # If-None-Match takes precedence over If-Modified-Since.
            inm = request_headers.get("if-none-match")

            if inm is not None:
                if etag_matches(inm, etag):
                    return HTTPResponse(304, None, headers)

            else:
                ims = parse_http_date(
                    request_headers.get("if-modified-since")
                )

                if ims is not None and int(modified) <= int(ims):
                    return HTTPResponse(304, None, headers)

            return HTTPResponse(200, body, headers)


class HTTPCache:
    """
    Thread-safe in-memory HTTP cache.

    Cache keys include normalized URL and Vary request-header values.
    Authentication-sensitive responses are never shared across users.
    """

    def __init__(
        self,
        origin: OriginServer,
        capacity: int = 100,
        shared: bool = True
    ):
        if capacity < 1:
            raise ValidationError("Capacity must be positive")

        self.origin = origin
        self.capacity = capacity
        self.shared = shared
        self.entries = OrderedDict()
        self.lock = threading.RLock()
        self.inflight = {}
        self.generation = {}

    @staticmethod
    def normalize_url(url: str) -> str:
        parsed = urlsplit(url)

        if parsed.scheme not in ("http", "https"):
            raise ValidationError("Unsupported URL scheme")

        if not parsed.netloc:
            raise ValidationError("URL requires a host")

        if parsed.username or parsed.password:
            raise ValidationError("Credentials in URLs are forbidden")

        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path or '/'}" + (
            f"?{parsed.query}" if parsed.query else ""
        )

    @staticmethod
    def _headers(headers: dict) -> dict:
        result = {}

        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidationError("Headers must contain strings")

            result[key.lower()] = value

        return result

    def _base_key(self, url: str, user_id: Optional[str]) -> tuple:
        return (
            self.normalize_url(url),
            user_id if not self.shared else None
        )

    def _find_entry(self, base_key, request_headers):
        for key, entry in reversed(self.entries.items()):
            if key[:2] != base_key:
                continue

            values = tuple(
                request_headers.get(name, "")
                for name in entry.vary
            )

            if values == entry.vary_values:
                self.entries.move_to_end(key)
                return key, entry

        return None, None

    def _make_entry(
        self,
        response: HTTPResponse,
        request_headers: dict,
        previous: Optional[CacheEntry] = None
    ) -> Optional[CacheEntry]:
        if response.status != 200:
            return None

        headers = {
            k.lower(): v for k, v in response.headers.items()
        }

        directives = CacheControl.parse(
            headers.get("cache-control", "")
        )

        if directives.no_store:
            return None

        if self.shared and directives.private:
            return None

        vary_header = headers.get("vary", "")
        vary = tuple(sorted(
            x.strip().lower()
            for x in vary_header.split(",")
            if x.strip()
        ))

        if "*" in vary:
            return None

        if any(not x.replace("-", "").isalnum() for x in vary):
            return None

        age_header = headers.get("age", "0")

        try:
            age = max(0, int(age_header))
        except ValueError:
            age = 0

        return CacheEntry(
            response=response,
            stored_at=time.time(),
            initial_age=age,
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
            vary=vary,
            vary_values=tuple(
                request_headers.get(name, "")
                for name in vary
            ),
            freshness=directives.freshness_lifetime(self.shared),
            stale_while_revalidate=directives.stale_while_revalidate,
            must_revalidate=directives.must_revalidate,
            generation=previous.generation if previous else 0
        )

    def _store(self, base_key, entry):
        key = base_key + (entry.vary, entry.vary_values)

        self.entries[key] = entry
        self.entries.move_to_end(key)

        while len(self.entries) > self.capacity:
            evicted, _ = self.entries.popitem(last=False)
            logger.info("Evicted cache key: %s", evicted[0])

    def request(
        self,
        url: str,
        headers: Optional[dict] = None,
        method: str = "GET",
        user_id: Optional[str] = None
    ) -> tuple[HTTPResponse, CacheStatus]:
        method = method.upper()

        if method not in ("GET", "HEAD"):
            return (
                self.origin.get(
                    self._path(url),
                    headers
                ),
                CacheStatus.BYPASS
            )

        request_headers = self._headers(headers or {})

        if "authorization" in request_headers and self.shared:
            return (
                self.origin.get(self._path(url), request_headers),
                CacheStatus.BYPASS
            )

        if request_headers.get("cache-control", "").lower().find(
            "no-store"
        ) >= 0:
            return (
                self.origin.get(self._path(url), request_headers),
                CacheStatus.BYPASS
            )

        base_key = self._base_key(url, user_id)
        path = self._path(url)

        # A single lock protects lookup and request coalescing.
        with self.lock:
            key, entry = self._find_entry(
                base_key,
                request_headers
            )

            if entry and entry.fresh(time.time()):
                response = entry.response

                if method == "HEAD":
                    response = HTTPResponse(
                        response.status, None, response.headers.copy()
                    )

                return response, CacheStatus.HIT

            if key in self.inflight:
                event = self.inflight[key]
                event.wait()

                _, refreshed = self._find_entry(
                    base_key,
                    request_headers
                )

                if refreshed and refreshed.fresh(time.time()):
                    return refreshed.response, CacheStatus.HIT

            event = threading.Event()

            lock_key = key if key is not None else base_key

            if lock_key not in self.inflight:
                self.inflight[lock_key] = event

        try:
            conditional_headers = request_headers.copy()

            if entry:
                if entry.etag:
                    conditional_headers["if-none-match"] = entry.etag
                elif entry.last_modified:
                    conditional_headers["if-modified-since"] = (
                        entry.last_modified
                    )

            response = self.origin.get(
                path,
                conditional_headers
            )

            if response.status == 304 and entry:
                # A 304 updates metadata while retaining the cached body.
                merged = entry.response.headers.copy()
                merged.update(response.headers)

                refreshed_response = HTTPResponse(
                    200,
                    entry.response.body,
                    merged
                )

                new_entry = self._make_entry(
                    refreshed_response,
                    request_headers,
                    entry
                )

                with self.lock:
                    if new_entry:
                        self._store(base_key, new_entry)
                    else:
                        self.entries.pop(key, None)

                return refreshed_response, CacheStatus.REVALIDATED

            new_entry = self._make_entry(
                response,
                request_headers
            )

            with self.lock:
                if new_entry:
                    self._store(base_key, new_entry)

            if method == "HEAD":
                response = HTTPResponse(
                    response.status, None, response.headers.copy()
                )

            return response, (
                CacheStatus.MISS if response.status == 200
                else CacheStatus.BYPASS
            )

        finally:
            with self.lock:
                signal = self.inflight.pop(lock_key, None)

                if signal:
                    signal.set()

    @staticmethod
    def _path(url: str) -> str:
        return HTTPCache.normalize_url(url).split(
            "://", 1
        )[1].split("/", 1)[-1].join(["/", ""]).split("#")[0] if False else (
            urlsplit(HTTPCache.normalize_url(url)).path or "/"
        )

    def invalidate(self, url: str) -> int:
        normalized = self.normalize_url(url)

        with self.lock:
            keys = [
                key for key in self.entries
                if key[0] == normalized
            ]

            for key in keys:
                del self.entries[key]

            self.generation[normalized] = (
                self.generation.get(normalized, 0) + 1
            )

            return len(keys)


def demonstrate():
    origin = OriginServer()

    origin.publish(
        "/api/products/101",
        {
            "id": 101,
            "name": "Industrial Sensor",
            "price": 2500,
            "available": True
        }
    )

    cache = HTTPCache(
        origin,
        capacity=20,
        shared=True
    )

    url = "https://api.example.com/api/products/101"

    print("\n1. Initial request")
    response, status = cache.request(url)
    print(status.value, response.status, response.body)

    print("\n2. Repeated request")
    response, status = cache.request(url)
    print(status.value, response.status)

    assert status == CacheStatus.HIT

    print("\n3. Origin request count")
    print(origin.request_count)

    assert origin.request_count == 1

    print("\n4. Cache invalidation")
    removed = cache.invalidate(url)
    print("Removed entries:", removed)

    response, status = cache.request(url)

    print(status.value, response.body)

    print("\n5. Cache-Control parsing")
    policy = CacheControl.parse(
        "public, max-age=120, s-maxage=300, must-revalidate"
    )

    print(policy)
    print("Shared freshness:", policy.freshness_lifetime())

    print("\n6. ETag validation")
    etag = generate_etag({"version": 1})
    assert etag_matches(f"W/{etag}", etag)
    print("ETag:", etag)

    print("\n7. Error handling")

    try:
        CacheControl.parse("max-age=-10")
    except ValidationError as error:
        print("Rejected:", error)

    try:
        HTTPCache.normalize_url("file:///etc/passwd")
    except ValidationError as error:
        print("Rejected:", error)

    print("\n8. Final origin request count")
    print(origin.request_count)


if __name__ == "__main__":
    demonstrate()
