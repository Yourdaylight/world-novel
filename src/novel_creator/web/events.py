"""Event broadcasting for real-time WebSocket updates.

Pipeline nodes call ``emit_event()`` to push progress updates.
The web app consumes the queue and broadcasts to connected clients.
"""

from __future__ import annotations

import asyncio
from typing import Any

_event_queue: asyncio.Queue | None = None


def get_event_queue() -> asyncio.Queue:
    """Get (or lazily create) the singleton event queue."""
    global _event_queue
    if _event_queue is None:
        _event_queue = asyncio.Queue()
    return _event_queue


async def emit_event(event_type: str, data: dict[str, Any] | None = None) -> None:
    """Emit a pipeline event to the WebSocket broadcast queue.

    Safe to call even when no web server is running — events are
    silently dropped if no consumer is listening.
    """
    payload: dict[str, Any] = {"type": event_type}
    if data:
        payload.update(data)
    try:
        q = get_event_queue()
        q.put_nowait(payload)
    except Exception:
        pass  # Non-critical — don't break the pipeline
