"""Novel CRUD routes: /novels, /novels/select, /novels/active, /worlds/create, /worlds/{id} DELETE, /worlds/{id}/status, /worlds/{id}/propositions."""

from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import (
    load_registry,
    set_active_novel,
    get_active_novel,
    register_novel,
    get_novel_by_id,
    delete_novel,
    save_registry,
    update_novel_status,
)

from ._helpers import _get_novel_db, logger

router = APIRouter()

# Forward reference to generation module's _generation_tasks (lazy import to avoid circular)


class SelectNovelRequest(BaseModel):
    novel_id: str


@router.get("/novels")
async def api_list_novels():
    """List all registered novels."""
    registry = load_registry()
    novels = [n.model_dump() for n in registry.novels]
    # Serialize datetime
    for n in novels:
        n["created_at"] = str(n["created_at"])
    return {
        "novels": novels,
        "active_novel_id": registry.active_novel_id,
    }


@router.post("/novels/select")
async def api_select_novel(req: SelectNovelRequest):
    """Switch the active novel."""
    try:
        info = set_active_novel(req.novel_id)
        return {"ok": True, "active_novel_id": info.novel_id, "title": info.title}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@router.get("/novels/active")
async def api_active_novel():
    """Get the currently active novel info."""
    active = get_active_novel()
    if active is None:
        return {"active": None}
    data = active.model_dump()
    data["created_at"] = str(data["created_at"])
    return {"active": data}


class CreateWorldRequest(BaseModel):
    title: str
    genre: str = "武侠"
    propositions: dict = Field(default_factory=dict)  # {what_is, where_from, where_to}
    num_chapters: int = 3
    num_characters: int = 3
    num_volumes: int = 0
    theme: str = ""
    premise: str = ""


@router.post("/worlds/create")
async def api_create_world(req: CreateWorldRequest):
    """Create a new world (register novel + save propositions)."""
    try:
        # Register novel
        info = register_novel(title=req.title, genre=req.genre, num_chapters=req.num_chapters)

        # Save propositions to registry
        if req.propositions:
            registry = load_registry()
            for n in registry.novels:
                if n.novel_id == info.novel_id:
                    n.propositions = req.propositions
                    break
            save_registry(registry)

        # Save propositions to DB
        if req.propositions:
            conn = await get_connection(info.db_path)
            await conn.execute(
                """INSERT INTO world_propositions (id, what_is, where_from, where_to)
                   VALUES (1, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       what_is=excluded.what_is, where_from=excluded.where_from,
                       where_to=excluded.where_to""",
                (
                    req.propositions.get("what_is", ""),
                    req.propositions.get("where_from", ""),
                    req.propositions.get("where_to", ""),
                ),
            )
            await conn.commit()
            await conn.close()

        return {
            "ok": True,
            "novel_id": info.novel_id,
            "db_path": info.db_path,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/worlds/{novel_id}")
async def api_delete_world(novel_id: str):
    """Delete a world/novel."""
    try:
        success = delete_novel(novel_id)
        return {"ok": success}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/worlds/{novel_id}/status")
async def api_world_status(novel_id: str):
    """Get combined world status — registry + DB progress + generation task."""
    novel = get_novel_by_id(novel_id)
    if novel is None:
        return {"error": "not found"}

    # Check if generation task is running (lazy import to avoid circular)
    from .generation import _generation_tasks
    is_running = novel_id in _generation_tasks and not _generation_tasks[novel_id].done()

    # Get DB progress from checkpoints
    progress = {"completed": 0, "total": 0, "phase": "idle", "paused": False}
    actual_chapter_count = 0
    try:
        conn = await get_connection(novel.db_path)
        cursor = await conn.execute(
            "SELECT * FROM generation_checkpoints ORDER BY created_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row:
            progress = {
                "completed": row["completed_chapters"],
                "total": row["total_chapters"],
                "phase": row["phase"],
                "paused": row["phase"] not in ("done",),
            }
        # Also count actual chapters in DB as ground truth
        cursor2 = await conn.execute(
            "SELECT COUNT(DISTINCT chapter_index) FROM chapter_texts"
        )
        count_row = await cursor2.fetchone()
        if count_row:
            actual_chapter_count = count_row[0]
        await conn.close()
    except Exception:
        pass

    # Use the most reliable chapter count:
    # - During active generation: registry value is live-updated, trust it
    # - Otherwise: use DB actual count as ground truth
    chapters_completed = novel.chapters_completed
    if not is_running and actual_chapter_count != chapters_completed:
        chapters_completed = actual_chapter_count
        # Sync registry to match reality
        novel.chapters_completed = actual_chapter_count

    return {
        "novel_id": novel_id,
        "title": novel.title,
        "status": novel.status,
        "is_running": is_running,
        "chapters_completed": chapters_completed,
        "chapters_total": novel.chapters_total,
        "word_count": novel.word_count,
        "progress": progress,
    }


@router.get("/worlds/{novel_id}/propositions")
async def api_get_propositions(novel_id: str):
    """Get the three propositions for a world."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"what_is": "", "where_from": "", "where_to": ""}

        conn = await get_connection(novel.db_path)
        cursor = await conn.execute(
            "SELECT what_is, where_from, where_to FROM world_propositions WHERE id = 1"
        )
        row = await cursor.fetchone()
        await conn.close()

        if row is None:
            return {"what_is": "", "where_from": "", "where_to": ""}
        return {
            "what_is": row["what_is"],
            "where_from": row["where_from"],
            "where_to": row["where_to"],
        }
    except Exception:
        return {"what_is": "", "where_from": "", "where_to": ""}
