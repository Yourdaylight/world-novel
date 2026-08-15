"""In-app fixed-window rate limiter (Milestone 15, Requirement B-8).

Used for public share endpoints: single instance, 60 requests/min per IP by
default. Production may additionally enable nginx ``limit_req`` — this module
is the application-level guarantee so the limit holds regardless of proxy.

Memory is bounded: stale windows are evicted on each check.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status

from novel_creator.config import settings


class FixedWindowLimiter:
    """Thread-safe-ish fixed-window counter (asyncio single-thread event loop)."""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, tuple[int, int]] = {}  # key -> (window_start, count)
        self._last_prune = 0.0

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        # Opportunistic prune every 60s to bound memory
        if now - self._last_prune > self.window_seconds:
            cutoff = now - self.window_seconds * 2
            self._buckets = {
                k: v for k, v in self._buckets.items() if v[0] > cutoff
            }
            self._last_prune = now

        window_start = int(now // self.window_seconds)
        cur_window, count = self._buckets.get(key, (window_start, 0))
        if cur_window != window_start:
            cur_window, count = window_start, 0
        count += 1
        self._buckets[key] = (cur_window, count)
        return count <= self.limit


# Public share page endpoints: 60 req/min per client IP (needs doc §4.6)
share_limiter = FixedWindowLimiter(limit=settings.share_rate_limit, window_seconds=60)

# Auth endpoints (registration abuse prevention, §4.6-4): 20 req/min per IP
auth_limiter = FixedWindowLimiter(limit=20, window_seconds=60)


def client_ip(request: Request) -> str:
    """Best-effort client IP. Honors X-Forwarded-For first hop (behind nginx)."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(limiter: FixedWindowLimiter, request: Request, scope: str = "") -> None:
    """Raise 429 when the client exceeds its window budget."""
    key = f"{scope}:{client_ip(request)}"
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
