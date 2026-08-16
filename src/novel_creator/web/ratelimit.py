"""Tiny in-process fixed-window rate limiter.

The share reader endpoints are public, so they need basic abuse protection
(share-id enumeration, scraping). Single-instance deployments — the documented
topology — are covered here; for multi-instance or stricter limits add nginx
``limit_req`` in front (deployment docs recommend exactly that).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass


@dataclass
class _Window:
    started: float
    count: int


class FixedWindowRateLimiter:
    # Bound memory even under a spoofed-key flood.
    MAX_BUCKETS = 10_000

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            w = self._buckets.get(key)
            if w is None or now - w.started >= self.window:
                self._prune(now)
                if len(self._buckets) >= self.MAX_BUCKETS:
                    # Degrade safely: reject unknown keys rather than grow unbounded.
                    return False, int(self.window)
                self._buckets[key] = _Window(started=now, count=1)
                return True, 0
            if w.count >= self.max_requests:
                return False, max(1, int(self.window - (now - w.started)))
            w.count += 1
            return True, 0

    def _prune(self, now: float) -> None:
        stale = [k for k, w in self._buckets.items() if now - w.started >= self.window]
        for k in stale:
            self._buckets.pop(k, None)


# 60 public-share requests / minute / client (requirement B-8)
share_limiter = FixedWindowRateLimiter(max_requests=60, window_seconds=60.0)


def client_key(scope) -> str:
    """Client identity for rate limiting.

    The leftmost X-Forwarded-For value is client-controlled, so it is trusted
    ONLY when NOVEL_TRUST_PROXY is set (i.e. a known proxy appends the real
    peer). Otherwise use the TCP peer, which cannot be spoofed.
    """
    client = scope.get("client")
    peer = client[0] if client else "unknown"
    if not os.environ.get("NOVEL_TRUST_PROXY"):
        return peer
    for k, v in (scope.get("headers") or []):
        if k == b"x-forwarded-for":
            # nginx appends the real peer at the RIGHT end.
            hops = [h.strip() for h in v.decode("latin1").split(",") if h.strip()]
            return hops[-1] if hops else peer
    return peer
