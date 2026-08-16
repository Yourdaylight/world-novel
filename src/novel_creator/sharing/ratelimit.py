"""In-memory sliding-window rate limiter (single-instance).

For multi-instance deployments use nginx limit_req (recommended in the
deployment docs); this module is the application-level backstop so the
public share endpoints are protected out of the box.
"""

from __future__ import annotations

import ipaddress
import threading
import time
from collections import defaultdict, deque


def is_trusted_proxy(host: str) -> bool:
    """Only trust X-Forwarded-For / X-Real-IP from loopback or private nets."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = 0.0
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> bool:
        """Record one hit; return True if still within the limit."""
        now = now if now is not None else time.monotonic()
        cutoff = now - self.window
        with self._lock:
            self._maybe_sweep(now, cutoff)
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True

    def _maybe_sweep(self, now: float, cutoff: float) -> None:
        """Periodically drop stale buckets so spoofed IPs can't exhaust memory."""
        if now - self._last_sweep < self.window:
            return
        self._last_sweep = now
        dead = [key for key, bucket in self._hits.items() if not bucket or bucket[-1] < cutoff]
        for key in dead:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# 分享页/章节接口：单 IP 每分钟 ≤ 60 次（需求 B-8）
share_rate_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60.0)
