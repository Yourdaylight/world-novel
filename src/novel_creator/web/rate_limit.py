"""In-app fixed-window rate limiter (Milestone 15, Requirement B-8).

Used for public share endpoints: single instance, 60 requests/min per IP by
default. Production may additionally enable nginx ``limit_req`` — this module
is the application-level guarantee so the limit holds regardless of proxy.

Client IP resolution honours ``X-Forwarded-For`` **only** when the direct
connection comes from a trusted proxy (``NOVEL_TRUSTED_PROXIES``); otherwise
the header is attacker-controlled and is ignored (needs doc §4.6).

Memory is bounded: stale windows are evicted on each check.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status

from novel_creator.config import settings


class FixedWindowLimiter:
    """Fixed-window counter (asyncio single-thread event loop)."""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, tuple[int, int]] = {}  # key -> (window_index, count)
        self._last_prune = 0.0

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_index = int(now // self.window_seconds)

        # Opportunistic prune every window; compare WINDOW INDICES (not raw
        # seconds) so the active window is never evicted.
        if now - self._last_prune > self.window_seconds:
            cutoff_index = window_index - 2
            self._buckets = {
                k: v for k, v in self._buckets.items() if v[0] > cutoff_index
            }
            self._last_prune = now

        cur_window, count = self._buckets.get(key, (window_index, 0))
        if cur_window != window_index:
            cur_window, count = window_index, 0
        count += 1
        self._buckets[key] = (cur_window, count)
        return count <= self.limit


# Public share page endpoints: 60 req/min per client IP (needs doc §4.6)
share_limiter = FixedWindowLimiter(limit=settings.share_rate_limit, window_seconds=60)

# Auth endpoints (registration abuse prevention, §4.6-4): 20 req/min per IP
auth_limiter = FixedWindowLimiter(limit=20, window_seconds=60)


def _trusted_proxies() -> set[str]:
    return {p.strip() for p in settings.trusted_proxies.split(",") if p.strip()}


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    X-Forwarded-For is honoured ONLY when the direct peer is a configured
    trusted proxy; in that case the right-most untrusted hop is the client.
    Direct (unproxied) deployments therefore cannot be bypassed by spoofing
    the header.
    """
    direct = request.client.host if request.client else "unknown"
    if direct not in _trusted_proxies():
        return direct

    fwd = request.headers.get("x-forwarded-for", "")
    if not fwd:
        return direct
    hops = [h.strip() for h in fwd.split(",") if h.strip()]
    trusted = _trusted_proxies()
    # Walk from the right: first hop NOT in trusted set is the client
    for hop in reversed(hops):
        if hop not in trusted:
            return hop
    return hops[0] if hops else direct


def enforce(limiter: FixedWindowLimiter, request: Request, scope: str = "") -> None:
    """Raise 429 when the client exceeds its window budget."""
    key = f"{scope}:{client_ip(request)}"
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
