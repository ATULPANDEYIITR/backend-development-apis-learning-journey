"""
Rate Limiting: Fixed Window, Sliding Window, Token Bucket,
and Distributed Rate Limiting.

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import math
import threading
import time
import unittest

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


# ============================================================
# DOMAIN MODELS
# ============================================================

class Algorithm(Enum):
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: float
    algorithm: str
    limit: int


@dataclass
class WindowState:
    window_start: float
    count: int = 0


@dataclass
class TokenBucketState:
    tokens: float
    last_refill: float


class RateLimitError(Exception):
    pass


class ConfigurationError(ValueError):
    pass


# ============================================================
# RATE LIMIT POLICY
# ============================================================

@dataclass(frozen=True)
class RateLimitPolicy:
    limit: int
    window_seconds: float
    algorithm: Algorithm
    burst_capacity: Optional[float] = None
    refill_rate: Optional[float] = None

    def __post_init__(self):
        if self.limit <= 0:
            raise ConfigurationError("Limit must be positive.")

        if not math.isfinite(self.window_seconds):
            raise ConfigurationError("Window must be finite.")

        if self.window_seconds <= 0:
            raise ConfigurationError("Window must be positive.")

        if self.algorithm == Algorithm.TOKEN_BUCKET:
            capacity = self.burst_capacity or float(self.limit)
            refill = self.refill_rate or (
                self.limit / self.window_seconds
            )

            if not math.isfinite(capacity) or capacity <= 0:
                raise ConfigurationError("Invalid bucket capacity.")

            if not math.isfinite(refill) or refill <= 0:
                raise ConfigurationError("Invalid refill rate.")

            object.__setattr__(self, "burst_capacity", capacity)
            object.__setattr__(self, "refill_rate", refill)


# ============================================================
# FIXED WINDOW RATE LIMITER
# ============================================================

class FixedWindowLimiter:

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        if limit <= 0 or window_seconds <= 0:
            raise ConfigurationError("Invalid rate limit configuration.")

        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.states: dict[str, WindowState] = {}
        self.lock = threading.Lock()

    def allow(self, key: str, cost: int = 1) -> RateLimitDecision:
        if not key or cost <= 0:
            raise ValueError("Key and positive cost are required.")

        now = self.clock()

        with self.lock:
            state = self.states.get(key)

            if state is None:
                state = WindowState(
                    window_start=now,
                    count=0,
                )
                self.states[key] = state

            elapsed = now - state.window_start

            if elapsed >= self.window_seconds:
                periods = math.floor(elapsed / self.window_seconds)
                state.window_start += periods * self.window_seconds
                state.count = 0

            allowed = state.count + cost <= self.limit

            if allowed:
                state.count += cost

            remaining = max(0, self.limit - state.count)
            retry_after = max(
                0.0,
                state.window_start + self.window_seconds - now,
            )

            return RateLimitDecision(
                allowed=allowed,
                remaining=remaining,
                retry_after=0.0 if allowed else retry_after,
                algorithm=Algorithm.FIXED_WINDOW.value,
                limit=self.limit,
            )


# ============================================================
# SLIDING WINDOW LOG RATE LIMITER
# ============================================================

class SlidingWindowLogLimiter:

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        if limit <= 0 or window_seconds <= 0:
            raise ConfigurationError("Invalid rate limit configuration.")

        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, cost: int = 1) -> RateLimitDecision:
        if not key or cost <= 0:
            raise ValueError("Key and positive cost are required.")

        if cost > self.limit:
            return RateLimitDecision(
                False,
                0,
                0.0,
                Algorithm.SLIDING_WINDOW.value,
                self.limit,
            )

        now = self.clock()
        cutoff = now - self.window_seconds

        with self.lock:
            timestamps = self.requests[key]

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            allowed = len(timestamps) + cost <= self.limit

            if allowed:
                timestamps.extend([now] * cost)

            remaining = max(0, self.limit - len(timestamps))

            retry_after = (
                max(0.0, timestamps[0] + self.window_seconds - now)
                if timestamps and not allowed
                else 0.0
            )

            return RateLimitDecision(
                allowed=allowed,
                remaining=remaining,
                retry_after=retry_after,
                algorithm=Algorithm.SLIDING_WINDOW.value,
                limit=self.limit,
            )


# ============================================================
# TOKEN BUCKET RATE LIMITER
# ============================================================

class TokenBucketLimiter:

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        if (
            not math.isfinite(capacity)
            or not math.isfinite(refill_rate)
            or capacity <= 0
            or refill_rate <= 0
        ):
            raise ConfigurationError("Invalid token bucket configuration.")

        self.capacity = capacity
        self.refill_rate = refill_rate
        self.clock = clock
        self.buckets: dict[str, TokenBucketState] = {}
        self.lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0) -> RateLimitDecision:
        if not key or not math.isfinite(cost) or cost <= 0:
            raise ValueError("Key and positive finite cost are required.")

        now = self.clock()

        with self.lock:
            state = self.buckets.get(key)

            if state is None:
                state = TokenBucketState(
                    tokens=self.capacity,
                    last_refill=now,
                )
                self.buckets[key] = state

            elapsed = max(0.0, now - state.last_refill)

            state.tokens = min(
                self.capacity,
                state.tokens + elapsed * self.refill_rate,
            )
            state.last_refill = max(state.last_refill, now)

            allowed = cost <= self.capacity and state.tokens >= cost

            if allowed:
                state.tokens -= cost

            remaining = max(0, math.floor(state.tokens))

            retry_after = (
                max(0.0, (cost - state.tokens) / self.refill_rate)
                if not allowed and cost <= self.capacity
                else 0.0
            )

            return RateLimitDecision(
                allowed=allowed,
                remaining=remaining,
                retry_after=retry_after,
                algorithm=Algorithm.TOKEN_BUCKET.value,
                limit=int(self.capacity),
            )


# ============================================================
# DISTRIBUTED RATE LIMITING SIMULATION
# ============================================================

class SharedAtomicStore:
    """
    Simulates a shared atomic data store.

    All application instances access the same state and lock.
    A production implementation can use Redis Lua scripts,
    atomic Redis commands, or transactional database operations.
    """

    def __init__(self):
        self.data: dict[str, dict] = {}
        self.lock = threading.Lock()


class DistributedTokenBucketLimiter:

    def __init__(
        self,
        store: SharedAtomicStore,
        capacity: float,
        refill_rate: float,
        clock: Callable[[], float] = time.time,
    ):
        if capacity <= 0 or refill_rate <= 0:
            raise ConfigurationError("Invalid distributed configuration.")

        self.store = store
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.clock = clock

    def allow(
        self,
        user_id: str,
        cost: float = 1.0,
    ) -> RateLimitDecision:

        if not user_id or not math.isfinite(cost) or cost <= 0:
            raise ValueError("Invalid distributed request.")

        now = self.clock()
        key = f"rate-limit:{user_id}"

        with self.store.lock:
            state = self.store.data.get(key)

            if state is None:
                state = {
                    "tokens": self.capacity,
                    "timestamp": now,
                }

            elapsed = max(0.0, now - state["timestamp"])

            tokens = min(
                self.capacity,
                state["tokens"] + elapsed * self.refill_rate,
            )

            allowed = cost <= self.capacity and tokens >= cost

            if allowed:
                tokens -= cost

            self.store.data[key] = {
                "tokens": tokens,
                "timestamp": max(now, state["timestamp"]),
            }

            retry_after = (
                (cost - tokens) / self.refill_rate
                if not allowed and cost <= self.capacity
                else 0.0
            )

            return RateLimitDecision(
                allowed=allowed,
                remaining=max(0, math.floor(tokens)),
                retry_after=retry_after,
                algorithm="distributed_token_bucket",
                limit=int(self.capacity),
            )


# ============================================================
# API GATEWAY
# ============================================================

class APIGateway:

    def __init__(self):
        self.policies = {
            "login": FixedWindowLimiter(5, 60),
            "search": SlidingWindowLogLimiter(10, 60),
            "upload": TokenBucketLimiter(5, 1 / 10),
        }

    def handle_request(
        self,
        endpoint: str,
        user_id: str,
        cost: int = 1,
    ) -> dict:

        limiter = self.policies.get(endpoint)

        if limiter is None:
            return {
                "status": 404,
                "message": "Unknown endpoint",
            }

        decision = limiter.allow(user_id, cost)

        if not decision.allowed:
            return {
                "status": 429,
                "message": "Too many requests",
                "retry_after_seconds": round(
                    decision.retry_after, 3
                ),
                "remaining": decision.remaining,
            }

        return {
            "status": 200,
            "message": "Request accepted",
            "remaining": decision.remaining,
        }


# ============================================================
# TESTING
# ============================================================

class FakeClock:

    def __init__(self, initial: float = 1000.0):
        self.current = initial

    def __call__(self):
        return self.current

    def advance(self, seconds: float):
        if seconds < 0:
            raise ValueError("Clock cannot move backward.")
        self.current += seconds


class RateLimiterTests(unittest.TestCase):

    def test_fixed_window(self):
        clock = FakeClock()
        limiter = FixedWindowLimiter(2, 10, clock)

        self.assertTrue(limiter.allow("user-1").allowed)
        self.assertTrue(limiter.allow("user-1").allowed)
        self.assertFalse(limiter.allow("user-1").allowed)

        clock.advance(10)

        self.assertTrue(limiter.allow("user-1").allowed)

    def test_sliding_window(self):
        clock = FakeClock()
        limiter = SlidingWindowLogLimiter(2, 10, clock)

        self.assertTrue(limiter.allow("user-1").allowed)
        clock.advance(5)

        self.assertTrue(limiter.allow("user-1").allowed)
        self.assertFalse(limiter.allow("user-1").allowed)

        clock.advance(5)

        self.assertTrue(limiter.allow("user-1").allowed)

    def test_token_bucket(self):
        clock = FakeClock()
        limiter = TokenBucketLimiter(3, 1, clock)

        for _ in range(3):
            self.assertTrue(limiter.allow("user-1").allowed)

        self.assertFalse(limiter.allow("user-1").allowed)

        clock.advance(2)

        self.assertTrue(limiter.allow("user-1").allowed)

    def test_distributed_shared_state(self):
        clock = FakeClock()
        store = SharedAtomicStore()

        instance_a = DistributedTokenBucketLimiter(
            store, 2, 1, clock
        )
        instance_b = DistributedTokenBucketLimiter(
            store, 2, 1, clock
        )

        self.assertTrue(instance_a.allow("user-1").allowed)
        self.assertTrue(instance_b.allow("user-1").allowed)
        self.assertFalse(instance_a.allow("user-1").allowed)

    def test_independent_users(self):
        clock = FakeClock()
        limiter = FixedWindowLimiter(1, 10, clock)

        self.assertTrue(limiter.allow("alice").allowed)
        self.assertTrue(limiter.allow("bob").allowed)

    def test_expensive_request(self):
        clock = FakeClock()
        limiter = SlidingWindowLogLimiter(3, 10, clock)

        self.assertFalse(limiter.allow("alice", 4).allowed)

    def test_invalid_configuration(self):
        with self.assertRaises(ConfigurationError):
            FixedWindowLimiter(0, 10)

        with self.assertRaises(ValueError):
            TokenBucketLimiter(3, 1).allow("alice", -1)


# ============================================================
# EXECUTION
# ============================================================

def main():

    print("=" * 65)
    print("RATE LIMITING ENGINE")
    print("=" * 65)

    gateway = APIGateway()

    for endpoint in ["login"] * 7:
        result = gateway.handle_request(endpoint, "user-101")
        print(endpoint, result)

    print("\nDistributed rate limiting:")

    store = SharedAtomicStore()

    servers = [
        DistributedTokenBucketLimiter(store, 3, 0.5),
        DistributedTokenBucketLimiter(store, 3, 0.5),
    ]

    for index in range(5):
        server = servers[index % 2]
        decision = server.allow("customer-500")

        print(
            f"Server {index % 2 + 1}: "
            f"allowed={decision.allowed}, "
            f"remaining={decision.remaining}"
        )

    print("\nRunning tests:")
    unittest.main(argv=["rate_limiter.py"], exit=False)


if __name__ == "__main__":
    main()
