"""Tiny in-process sliding-window rate limiter (single-instance deployments).

For multi-instance / production deployments prefer nginx ``limit_req`` (see
docs-site deployment guide); this module exists so the open-source single
node is protected out of the box.

Configure with ``NOVEL_SHARE_RATE_PER_MIN`` (default 60; 0 disables).
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def _limit() -> int:
    try:
        return max(0, int(os.environ.get("NOVEL_SHARE_RATE_PER_MIN", "60")))
    except ValueError:
        return 60


class SlidingWindowLimiter:
    """Per-key sliding window. Caps the key count to bound memory even when
    clients spoof their identity (each spoofed key still costs an entry)."""

    MAX_KEYS = 100_000

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            # Lazy eviction: drop expired buckets, bound total keys
            if len(self._hits) > self.MAX_KEYS:
                for k in [k for k, b in self._hits.items() if not b or now - b[-1] > window]:
                    del self._hits[k]
                for k in list(self._hits)[: len(self._hits) - self.MAX_KEYS]:
                    del self._hits[k]

            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


share_limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    # X-Forwarded-For is client-controlled: with nginx `$proxy_add_x_forwarded_for`
    # the client-supplied value stays FIRST, so never trust it blindly. Prefer
    # X-Real-IP (nginx sets it to $remote_addr, unforgeable) when behind a proxy;
    # fall back to the direct peer address otherwise.
    behind_proxy = os.environ.get("NOVEL_BEHIND_PROXY", "") == "1"
    if behind_proxy:
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            # Last hop is the closest trusted proxy's peer — most trustworthy
            # when X-Real-IP is unavailable.
            return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def share_rate_limit(request: Request) -> None:
    """FastAPI dependency: cap public share endpoints per client IP."""
    limit = _limit()
    if limit == 0:
        return
    if not share_limiter.check(f"share:{client_ip(request)}", limit):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


# Login is a separate, tighter bucket (credential endpoint brute-force).
login_limiter = SlidingWindowLimiter()


def _login_limit() -> int:
    try:
        return max(0, int(os.environ.get("NOVEL_LOGIN_RATE_PER_MIN", "10")))
    except ValueError:
        return 10


async def login_rate_limit(request: Request) -> None:
    limit = _login_limit()
    if limit == 0:
        return
    if not login_limiter.check(f"login:{client_ip(request)}", limit):
        raise HTTPException(status_code=429, detail="尝试过于频繁，请稍后再试")
