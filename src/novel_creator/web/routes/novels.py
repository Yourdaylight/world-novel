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
    """List all registered novels with DB-accurate chapter counts."""
    registry = load_registry()
    novels = []
    for n in registry.novels:
        data = n.model_dump()
        data["created_at"] = str(data["created_at"])
        # Override stale in-memory counts with DB ground truth
        try:
            conn = await get_connection(n.db_path)
            # Actual completed chapters
            cursor = await conn.execute("SELECT COUNT(DISTINCT chapter_index) FROM chapter_texts")
            row = await cursor.fetchone()
            actual_completed = row[0] if row else 0
            # Total planned from outline
            cursor2 = await conn.execute("SELECT outline_json FROM story_outline LIMIT 1")
            outline_row = await cursor2.fetchone()
            actual_total = 0
            if outline_row:
                import json as _json
                outline_data = _json.loads(outline_row[0])
                actual_total = len(outline_data.get("chapters", []))
            await conn.close()
            # Sync registry to reality
            if actual_completed != n.chapters_completed:
                n.chapters_completed = actual_completed
            if actual_total > 0 and actual_total != n.chapters_total:
                n.chapters_total = actual_total
            data["chapters_completed"] = actual_completed
            data["chapters_total"] = actual_total if actual_total > 0 else n.chapters_total
        except Exception:
            pass
        novels.append(data)
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
    actual_total = 0
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
                "paused": row["phase"] == "paused",
            }
        # Count actual chapters in DB as ground truth
        cursor2 = await conn.execute(
            "SELECT COUNT(DISTINCT chapter_index) FROM chapter_texts"
        )
        count_row = await cursor2.fetchone()
        if count_row:
            actual_chapter_count = count_row[0]
        # Read total from outline
        cursor3 = await conn.execute("SELECT outline_json FROM story_outline LIMIT 1")
        outline_row = await cursor3.fetchone()
        if outline_row:
            outline_data = json.loads(outline_row[0])
            actual_total = len(outline_data.get("chapters", []))
        await conn.close()
    except Exception:
        pass

    # Use the most reliable chapter count:
    # - During active generation: registry value is live-updated, trust it
    # - Otherwise: use DB actual count as ground truth
    chapters_completed = novel.chapters_completed
    chapters_total = novel.chapters_total
    if not is_running:
        if actual_chapter_count != chapters_completed:
            chapters_completed = actual_chapter_count
            novel.chapters_completed = actual_chapter_count
        if actual_total > 0 and actual_total != chapters_total:
            chapters_total = actual_total
            novel.chapters_total = actual_total

    return {
        "novel_id": novel_id,
        "title": novel.title,
        "status": novel.status,
        "is_running": is_running,
        "chapters_completed": chapters_completed,
        "chapters_total": chapters_total,
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
