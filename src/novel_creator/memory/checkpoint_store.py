"""Generation-checkpoint persistence for pause / resume."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import aiosqlite

from novel_creator.models.checkpoint import GenerationCheckpoint


async def save_checkpoint(conn: aiosqlite.Connection, state: dict) -> str:
    """Serialize *state* and persist a checkpoint. Returns the checkpoint_id."""
    cp_id = f"cp_{uuid.uuid4().hex[:8]}"
    outline = state.get("outline")
    title = outline.title if outline else ""
    total = len(outline.chapters) if outline else 0
    completed = state.get("current_chapter", 0)

    # Build a JSON-safe copy of state
    safe_state = _serialize_state(state)

    await conn.execute(
        """INSERT INTO generation_checkpoints
           (checkpoint_id, last_completed_chapter, phase, state_json,
            novel_title, total_chapters, completed_chapters)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            cp_id,
            completed - 1 if completed > 0 else 0,
            state.get("phase", "simulating"),
            json.dumps(safe_state, ensure_ascii=False, default=str),
            title,
            total,
            completed,
        ),
    )
    await conn.commit()
    return cp_id


async def load_latest(conn: aiosqlite.Connection) -> GenerationCheckpoint | None:
    """Load the most recent checkpoint."""
    cursor = await conn.execute(
        "SELECT * FROM generation_checkpoints ORDER BY created_at DESC LIMIT 1",
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_checkpoint(row)


async def load_by_id(conn: aiosqlite.Connection, checkpoint_id: str) -> GenerationCheckpoint | None:
    """Load a specific checkpoint by ID."""
    cursor = await conn.execute(
        "SELECT * FROM generation_checkpoints WHERE checkpoint_id = ?",
        (checkpoint_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_checkpoint(row)


async def list_all(conn: aiosqlite.Connection) -> list[GenerationCheckpoint]:
    """List all checkpoints, newest first."""
    cursor = await conn.execute(
        "SELECT * FROM generation_checkpoints ORDER BY created_at DESC",
    )
    rows = await cursor.fetchall()
    return [_row_to_checkpoint(r) for r in rows]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _serialize_state(state: dict) -> dict:
    """Create a JSON-friendly shallow copy of the LangGraph state."""
    import copy

    safe: dict = {}
    for key, val in state.items():
        if val is None:
            safe[key] = None
        elif isinstance(val, (str, int, float, bool)):
            safe[key] = val
        elif isinstance(val, list):
            safe[key] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in val
            ]
        elif hasattr(val, "model_dump"):
            safe[key] = val.model_dump()
        else:
            safe[key] = str(val)
    return safe


def _row_to_checkpoint(row) -> GenerationCheckpoint:
    return GenerationCheckpoint(
        checkpoint_id=row["checkpoint_id"],
        created_at=row["created_at"] if isinstance(row["created_at"], datetime) else datetime.fromisoformat(str(row["created_at"])),
        last_completed_chapter=row["last_completed_chapter"],
        phase=row["phase"] or "simulating",
        state_json=row["state_json"],
        novel_title=row["novel_title"] or "",
        total_chapters=row["total_chapters"],
        completed_chapters=row["completed_chapters"],
    )
