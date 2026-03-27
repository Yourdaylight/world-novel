"""API routes for the novel creator dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("novel_creator.web")

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import (
    load_registry,
    list_novels,
    set_active_novel,
    get_active_novel,
    register_novel,
    update_novel_status,
    get_novel_by_id,
    delete_novel,
    save_registry,
)

router = APIRouter()


# ------------------------------------------------------------------
# Helper: resolve novel_id → db_path
# ------------------------------------------------------------------

async def _get_novel_db(novel_id: str | None = None) -> str:
    """Resolve novel_id to db_path. Falls back to active novel, then settings."""
    registry = load_registry()
    if novel_id:
        novel = next((n for n in registry.novels if n.novel_id == novel_id), None)
        if novel:
            return novel.db_path
    if registry.active_novel_id:
        novel = next(
            (n for n in registry.novels if n.novel_id == registry.active_novel_id),
            None,
        )
        if novel:
            return novel.db_path
    return settings.db_path  # ultimate fallback


# ==================================================================
# Novel management APIs
# ==================================================================

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


# ==================================================================
# Original V1 routes — all updated with novel_id query param
# ==================================================================


@router.get("/story")
async def get_story(novel_id: str | None = Query(None)):
    """Get the current story outline and metadata."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute("SELECT character_id, profile_json FROM characters")
        rows = await cursor.fetchall()
        characters = []
        for row in rows:
            profile = json.loads(row["profile_json"])
            characters.append({
                "id": row["character_id"],
                "name": profile.get("name", ""),
                "role": profile.get("role", ""),
                "backstory": profile.get("backstory", ""),
            })
        await conn.close()
        return {"characters": characters}
    except Exception as e:
        return {"error": str(e), "characters": []}


@router.get("/relationships")
async def get_relationships(novel_id: str | None = Query(None)):
    """Get all character relationships for the vis.js graph."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute("SELECT * FROM relationships")
        rows = await cursor.fetchall()
        edges = []
        for row in rows:
            edges.append({
                "from": row["source_id"],
                "to": row["target_id"],
                "label": row["relationship_type"],
                "trust": row["trust"],
                "affection": row["affection"],
            })
        await conn.close()
        return {"edges": edges}
    except Exception as e:
        return {"error": str(e), "edges": []}


@router.get("/chapters")
async def get_chapters(novel_id: str | None = Query(None)):
    """Get completed chapters — now includes rendered text if available."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        # Get chapter indices from actions (backward compat)
        cursor = await conn.execute(
            """SELECT DISTINCT chapter_index FROM character_actions ORDER BY chapter_index"""
        )
        action_rows = await cursor.fetchall()
        action_chapters = {row["chapter_index"] for row in action_rows}

        # Also get chapters from chapter_texts (V2)
        cursor2 = await conn.execute(
            """SELECT DISTINCT chapter_index FROM chapter_texts ORDER BY chapter_index"""
        )
        text_rows = await cursor2.fetchall()
        text_chapters = {row["chapter_index"] for row in text_rows}

        all_indices = sorted(action_chapters | text_chapters)
        chapters = [
            {"chapter_index": idx, "has_text": idx in text_chapters}
            for idx in all_indices
        ]
        await conn.close()
        return {"chapters": chapters}
    except Exception as e:
        return {"error": str(e), "chapters": []}


@router.get("/actions/{chapter_index}")
async def get_chapter_actions(chapter_index: int, novel_id: str | None = Query(None)):
    """Get all character actions for a specific chapter."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            """SELECT * FROM character_actions
               WHERE chapter_index = ?
               ORDER BY scene_index, id""",
            (chapter_index,),
        )
        rows = await cursor.fetchall()
        actions = [
            {
                "character_id": row["character_id"],
                "scene_index": row["scene_index"],
                "action_type": row["action_type"],
                "content": row["content"],
                "target": row["target_character_id"],
            }
            for row in rows
        ]
        await conn.close()
        return {"actions": actions}
    except Exception as e:
        return {"error": str(e), "actions": []}


@router.get("/emotions/{character_id}")
async def get_emotion_history(character_id: str, novel_id: str | None = Query(None)):
    """Get emotional state history for a character."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            """SELECT * FROM emotional_states
               WHERE character_id = ?
               ORDER BY chapter_index, scene_index""",
            (character_id,),
        )
        rows = await cursor.fetchall()
        states = [
            {
                "chapter": row["chapter_index"],
                "scene": row["scene_index"],
                "happiness": row["happiness"],
                "anger": row["anger"],
                "fear": row["fear"],
                "sadness": row["sadness"],
                "trust": row["trust"],
                "surprise": row["surprise"],
            }
            for row in rows
        ]
        await conn.close()
        return {"states": states}
    except Exception as e:
        return {"error": str(e), "states": []}


# ======================================================================
# V2: New API routes — all updated with novel_id query param
# ======================================================================


@router.get("/world")
async def get_world(novel_id: str | None = Query(None)):
    """Get the world-building data."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute("SELECT world_json FROM world_building WHERE id = 1")
        row = await cursor.fetchone()
        await conn.close()
        if row is None:
            return {"world": None}
        return {"world": json.loads(row["world_json"])}
    except Exception as e:
        return {"error": str(e), "world": None}


@router.get("/outline")
async def get_outline(novel_id: str | None = Query(None)):
    """Get the full story outline including volumes."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row = await cursor.fetchone()
        # Also fetch volumes
        vol_cursor = await conn.execute("SELECT * FROM volumes ORDER BY volume_index")
        vol_rows = await vol_cursor.fetchall()
        await conn.close()

        outline = json.loads(row["outline_json"]) if row else None
        volumes = [
            {
                "volume_index": v["volume_index"],
                "title": v["title"],
                "summary": v["summary"],
                "theme": v["theme"],
                "chapter_start": v["chapter_start"],
                "chapter_end": v["chapter_end"],
                "arc_goal": v["arc_goal"],
            }
            for v in vol_rows
        ]
        return {"outline": outline, "volumes": volumes}
    except Exception as e:
        return {"error": str(e), "outline": None, "volumes": []}


@router.get("/foreshadows")
async def get_foreshadows(novel_id: str | None = Query(None)):
    """Get all foreshadows and their status."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute("SELECT * FROM foreshadows ORDER BY planted_chapter")
        rows = await cursor.fetchall()
        await conn.close()
        items = [
            {
                "foreshadow_id": r["foreshadow_id"],
                "description": r["description"],
                "hint_text": r["hint_text"],
                "planted_chapter": r["planted_chapter"],
                "expected_payoff_chapter": r["expected_payoff_chapter"],
                "actual_payoff_chapter": r["actual_payoff_chapter"],
                "status": r["status"],
                "importance": r["importance"],
                "related_characters": json.loads(r["related_characters"] or "[]"),
                "related_plot_thread": r["related_plot_thread"],
            }
            for r in rows
        ]
        return {"foreshadows": items}
    except Exception as e:
        return {"error": str(e), "foreshadows": []}


@router.get("/plot-threads")
async def get_plot_threads(novel_id: str | None = Query(None)):
    """Get all plot threads."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute("SELECT * FROM plot_threads ORDER BY start_chapter")
        rows = await cursor.fetchall()
        await conn.close()
        items = [
            {
                "thread_id": r["thread_id"],
                "name": r["name"],
                "description": r["description"],
                "status": r["status"],
                "start_chapter": r["start_chapter"],
                "key_characters": json.loads(r["key_characters"] or "[]"),
                "foreshadow_ids": json.loads(r["foreshadow_ids"] or "[]"),
                "chapter_progress": json.loads(r["chapter_progress"] or "{}"),
            }
            for r in rows
        ]
        return {"plot_threads": items}
    except Exception as e:
        return {"error": str(e), "plot_threads": []}


@router.get("/progress")
async def get_progress(novel_id: str | None = Query(None)):
    """Get generation progress from the latest checkpoint."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            "SELECT * FROM generation_checkpoints ORDER BY created_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        await conn.close()
        if row is None:
            return {"completed": 0, "total": 0, "phase": "idle", "paused": False}
        return {
            "completed": row["completed_chapters"],
            "total": row["total_chapters"],
            "phase": row["phase"],
            "paused": row["phase"] not in ("done",),
            "checkpoint_id": row["checkpoint_id"],
            "novel_title": row["novel_title"],
        }
    except Exception as e:
        return {"error": str(e), "completed": 0, "total": 0, "phase": "error", "paused": False}


@router.get("/checkpoints")
async def get_checkpoints(novel_id: str | None = Query(None)):
    """Get all generation checkpoints."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            "SELECT checkpoint_id, created_at, last_completed_chapter, phase, "
            "novel_title, total_chapters, completed_chapters "
            "FROM generation_checkpoints ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        await conn.close()
        items = [
            {
                "checkpoint_id": r["checkpoint_id"],
                "created_at": str(r["created_at"]),
                "last_completed_chapter": r["last_completed_chapter"],
                "phase": r["phase"],
                "novel_title": r["novel_title"],
                "total_chapters": r["total_chapters"],
                "completed_chapters": r["completed_chapters"],
            }
            for r in rows
        ]
        return {"checkpoints": items}
    except Exception as e:
        return {"error": str(e), "checkpoints": []}


@router.get("/chapter-text/{chapter_index}")
async def get_chapter_text(chapter_index: int, novel_id: str | None = Query(None)):
    """Get the rendered literary text for a specific chapter."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            """SELECT * FROM chapter_texts
               WHERE chapter_index = ?
               ORDER BY scene_index""",
            (chapter_index,),
        )
        rows = await cursor.fetchall()
        await conn.close()
        if not rows:
            return {"title": "", "scenes": [], "full_text": "", "summary": ""}

        title = rows[0]["title"]
        summary = rows[0]["summary"] or ""
        scenes = [
            {
                "scene_index": r["scene_index"],
                "content": r["content"],
                "pov_character": r["pov_character"],
            }
            for r in rows
        ]
        full_text = "\n\n".join(r["content"] for r in rows)
        return {"title": title, "scenes": scenes, "full_text": full_text, "summary": summary}
    except Exception as e:
        return {"error": str(e), "title": "", "scenes": [], "full_text": "", "summary": ""}


@router.get("/novel-full")
async def get_novel_full(novel_id: str | None = Query(None)):
    """Get the full compiled novel text — all chapters joined."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        # Get outline for title
        cursor0 = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row0 = await cursor0.fetchone()
        outline = json.loads(row0["outline_json"]) if row0 else {}
        title = outline.get("title", "未命名小说")
        genre = outline.get("genre", "")

        # Get all chapter texts
        cursor = await conn.execute(
            """SELECT chapter_index, scene_index, title, content
               FROM chapter_texts ORDER BY chapter_index, scene_index"""
        )
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            return {"title": title, "genre": genre, "chapters": [], "full_text": "", "word_count": 0}

        # Group by chapter
        chapters = {}
        for r in rows:
            ci = r["chapter_index"]
            if ci not in chapters:
                chapters[ci] = {"chapter_index": ci, "title": r["title"], "scenes": []}
            chapters[ci]["scenes"].append(r["content"])

        # Build full text
        parts = [f"# {title}\n"]
        chapter_list = []
        for ci in sorted(chapters.keys()):
            ch = chapters[ci]
            chapter_text = "\n\n".join(ch["scenes"])
            parts.append(f"\n## 第{ci + 1}章 {ch['title']}\n")
            parts.append(chapter_text)
            chapter_list.append({
                "chapter_index": ci,
                "title": ch["title"],
                "text": chapter_text,
                "word_count": len(chapter_text),
            })

        full_text = "\n".join(parts)
        return {
            "title": title,
            "genre": genre,
            "chapters": chapter_list,
            "full_text": full_text,
            "word_count": len(full_text),
        }
    except Exception as e:
        return {"error": str(e), "title": "", "genre": "", "chapters": [], "full_text": "", "word_count": 0}


# ======================================================================
# V3: Timeline, God decisions, Agent files APIs
# ======================================================================


@router.get("/timeline")
async def get_timeline(novel_id: str | None = Query(None)):
    """Get the full story timeline (eras + events)."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        from novel_creator.memory import timeline_store
        timeline = await timeline_store.load_timeline(conn)
        await conn.close()
        return {
            "eras": [era.model_dump() for era in timeline.eras],
            "events": [event.model_dump() for event in timeline.events],
        }
    except Exception as e:
        return {"error": str(e), "eras": [], "events": []}


@router.get("/god-decisions")
async def get_god_decisions(novel_id: str | None = Query(None)):
    """Get all God Agent decisions."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        from novel_creator.memory import timeline_store
        decisions = await timeline_store.get_god_decisions(conn)
        await conn.close()
        return {
            "decisions": [d.model_dump() for d in decisions],
        }
    except Exception as e:
        return {"error": str(e), "decisions": []}


@router.get("/agents/{character_id}/files")
async def get_agent_files(character_id: str, novel_id: str | None = Query(None)):
    """Read agent.md and soul.md for a character."""
    try:
        db_path = await _get_novel_db(novel_id)
        from pathlib import Path
        novel_dir = Path(db_path).parent
        agents_dir = novel_dir / "agents" / character_id

        agent_md = ""
        soul_md = ""
        if agents_dir.exists():
            agent_path = agents_dir / "agent.md"
            soul_path = agents_dir / "soul.md"
            if agent_path.exists():
                agent_md = agent_path.read_text(encoding="utf-8")
            if soul_path.exists():
                soul_md = soul_path.read_text(encoding="utf-8")

        return {
            "character_id": character_id,
            "agent_md": agent_md,
            "soul_md": soul_md,
        }
    except Exception as e:
        return {"error": str(e), "character_id": character_id, "agent_md": "", "soul_md": ""}


class SoulUpdateRequest(BaseModel):
    content: str


@router.put("/agents/{character_id}/soul")
async def update_agent_soul(
    character_id: str,
    req: SoulUpdateRequest,
    novel_id: str | None = Query(None),
):
    """Update soul.md for a character and sync back to DB."""
    try:
        db_path = await _get_novel_db(novel_id)
        from pathlib import Path
        novel_dir = Path(db_path).parent
        agents_dir = novel_dir / "agents" / character_id
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Write soul.md
        soul_path = agents_dir / "soul.md"
        soul_path.write_text(req.content, encoding="utf-8")

        # Sync back to DB
        from novel_creator.sync.agent_files import AgentFileSync
        sync = AgentFileSync(novel_dir)
        conn = await get_connection(db_path)
        changed = await sync.import_character(conn, character_id)
        await conn.close()

        return {"ok": True, "synced": changed}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ======================================================================
# V4: Character detail APIs — actions, memories, full history
# ======================================================================


@router.get("/characters/{character_id}/actions-all")
async def get_character_all_actions(character_id: str, novel_id: str | None = Query(None)):
    """Get ALL actions for a character across all chapters (dialogue, thought, behavior, reaction)."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            """SELECT * FROM character_actions
               WHERE character_id = ?
               ORDER BY chapter_index, scene_index, id""",
            (character_id,),
        )
        rows = await cursor.fetchall()
        await conn.close()

        actions = []
        for row in rows:
            actions.append({
                "character_id": row["character_id"],
                "chapter_index": row["chapter_index"],
                "scene_index": row["scene_index"],
                "action_type": row["action_type"],
                "content": row["content"],
                "target": row["target_character_id"],
                "emotional_shift": json.loads(row["emotional_shift"] or "{}"),
            })
        return {"actions": actions, "total": len(actions)}
    except Exception as e:
        return {"error": str(e), "actions": [], "total": 0}


@router.get("/characters/{character_id}/memories")
async def get_character_memories(character_id: str, novel_id: str | None = Query(None)):
    """Get all episodic memories for a character."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ?
               ORDER BY chapter_index, scene_index""",
            (character_id,),
        )
        rows = await cursor.fetchall()
        await conn.close()

        memories = []
        for row in rows:
            memories.append({
                "memory_id": row["memory_id"],
                "chapter_index": row["chapter_index"],
                "scene_index": row["scene_index"],
                "content": row["content"],
                "importance": row["importance"],
                "emotional_valence": row["emotional_valence"],
                "involved_characters": json.loads(row["involved_characters"] or "[]"),
            })
        return {"memories": memories, "total": len(memories)}
    except Exception as e:
        return {"error": str(e), "memories": [], "total": 0}


@router.get("/characters/{character_id}/full-profile")
async def get_character_full_profile(character_id: str, novel_id: str | None = Query(None)):
    """Get complete character profile + stats summary."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)

        # Profile
        cursor = await conn.execute(
            "SELECT profile_json FROM characters WHERE character_id = ?",
            (character_id,),
        )
        row = await cursor.fetchone()
        profile = json.loads(row["profile_json"]) if row else {}

        # Action counts by type
        cursor2 = await conn.execute(
            """SELECT action_type, COUNT(*) as cnt
               FROM character_actions WHERE character_id = ?
               GROUP BY action_type""",
            (character_id,),
        )
        type_counts = {r["action_type"]: r["cnt"] for r in await cursor2.fetchall()}

        # Total actions
        cursor3 = await conn.execute(
            "SELECT COUNT(*) as total FROM character_actions WHERE character_id = ?",
            (character_id,),
        )
        total_actions = (await cursor3.fetchone())["total"]

        # Chapters appeared in
        cursor4 = await conn.execute(
            "SELECT DISTINCT chapter_index FROM character_actions WHERE character_id = ?",
            (character_id,),
        )
        chapters_in = [r["chapter_index"] for r in await cursor4.fetchall()]

        # Memory count
        cursor5 = await conn.execute(
            "SELECT COUNT(*) as total FROM episodic_memories WHERE character_id = ?",
            (character_id,),
        )
        total_memories = (await cursor5.fetchone())["total"]

        # Latest emotional state
        cursor6 = await conn.execute(
            """SELECT * FROM emotional_states
               WHERE character_id = ?
               ORDER BY chapter_index DESC, scene_index DESC LIMIT 1""",
            (character_id,),
        )
        emo_row = await cursor6.fetchone()
        latest_emotion = None
        if emo_row:
            latest_emotion = {
                "happiness": emo_row["happiness"],
                "anger": emo_row["anger"],
                "fear": emo_row["fear"],
                "sadness": emo_row["sadness"],
                "trust": emo_row["trust"],
                "surprise": emo_row["surprise"],
            }

        # Relationships
        cursor7 = await conn.execute(
            """SELECT * FROM relationships
               WHERE source_id = ? OR target_id = ?""",
            (character_id, character_id),
        )
        rel_rows = await cursor7.fetchall()
        relationships = [
            {
                "source_id": r["source_id"],
                "target_id": r["target_id"],
                "relationship_type": r["relationship_type"],
                "trust": r["trust"],
                "affection": r["affection"],
                "description": r["description"],
            }
            for r in rel_rows
        ]

        await conn.close()

        return {
            "character_id": character_id,
            "profile": profile,
            "stats": {
                "total_actions": total_actions,
                "action_types": type_counts,
                "chapters_appeared": sorted(chapters_in),
                "total_memories": total_memories,
            },
            "latest_emotion": latest_emotion,
            "relationships": relationships,
        }
    except Exception as e:
        return {"error": str(e)}


# ======================================================================
# V4: World creation & generation APIs
# ======================================================================


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


class GenerateRequest(BaseModel):
    mode: str = "full"  # "full" | "chapter_by_chapter"


# Background task tracker
_generation_tasks: dict[str, asyncio.Task] = {}


@router.post("/worlds/{novel_id}/generate")
async def api_start_generation(novel_id: str, req: GenerateRequest):
    """Start novel generation (async, progress via WebSocket)."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        # Check if already running
        if novel_id in _generation_tasks and not _generation_tasks[novel_id].done():
            return {"ok": False, "error": "Generation already in progress"}

        # Load propositions from DB
        conn = await get_connection(novel.db_path)
        cursor = await conn.execute("SELECT what_is, where_from, where_to FROM world_propositions WHERE id = 1")
        prop_row = await cursor.fetchone()
        await conn.close()

        propositions = {}
        if prop_row:
            propositions = {
                "what_is": prop_row["what_is"],
                "where_from": prop_row["where_from"],
                "where_to": prop_row["where_to"],
            }

        # Build enhanced premise from propositions
        premise = novel.propositions.get("premise", "") if novel.propositions else ""
        if propositions and any(propositions.values()):
            parts = []
            if propositions.get("what_is"):
                parts.append(f"【世界本质】{propositions['what_is']}")
            if propositions.get("where_from"):
                parts.append(f"【世界起源】{propositions['where_from']}")
            if propositions.get("where_to"):
                parts.append(f"【世界命运】{propositions['where_to']}")
            if premise:
                parts.append(f"【故事前提】{premise}")
            premise = "\n".join(parts)

        if not premise:
            premise = f"一个关于{novel.genre}的故事"

        # Get theme from registry or default
        theme = novel.propositions.get("theme", "") if novel.propositions else ""
        if not theme:
            theme = "成长与命运"

        update_novel_status(novel_id, status="generating")

        async def _run_generation():
            try:
                from novel_creator.graph.builder import compile_novel_graph
                from novel_creator.memory.database import reset_database
                from novel_creator.web.events import emit_event

                await reset_database(novel.db_path)

                # Re-save propositions after DB reset
                if propositions and any(propositions.values()):
                    conn2 = await get_connection(novel.db_path)
                    await conn2.execute(
                        """INSERT INTO world_propositions (id, what_is, where_from, where_to)
                           VALUES (1, ?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET
                               what_is=excluded.what_is, where_from=excluded.where_from,
                               where_to=excluded.where_to""",
                        (
                            propositions.get("what_is", ""),
                            propositions.get("where_from", ""),
                            propositions.get("where_to", ""),
                        ),
                    )
                    await conn2.commit()
                    await conn2.close()

                graph = compile_novel_graph()
                initial_state = {
                    "genre": novel.genre,
                    "theme": theme,
                    "premise": premise,
                    "num_chapters": novel.chapters_total or 3,
                    "num_characters": 3,
                    "num_volumes": 0,
                    "db_path": novel.db_path,
                    "current_chapter": 0,
                    "current_scene": 0,
                    "chapters_completed": [],
                    "chapter_summaries": [],
                    "character_actions": [],
                    "phase": "directing",
                    "generation_mode": req.mode,
                    "pause_after_chapter": False,
                    "foreshadows": [],
                    "plot_threads": [],
                    "foreshadow_issues": [],
                }

                await emit_event("generation_started", {"novel_id": novel_id})
                result = await graph.ainvoke(initial_state)

                if result.get("novel"):
                    update_novel_status(
                        novel_id,
                        status="completed",
                        chapters_completed=len(result["novel"].chapters),
                        word_count=result["novel"].word_count,
                    )
                elif result.get("last_checkpoint_id"):
                    update_novel_status(
                        novel_id,
                        status="paused",
                        chapters_completed=result.get("current_chapter", 0),
                    )
                else:
                    update_novel_status(novel_id, status="idle")

                await emit_event("generation_finished", {
                    "novel_id": novel_id,
                    "status": "completed" if result.get("novel") else "paused",
                })
            except Exception as e:
                logger.error("Generation failed for %s: %s", novel_id, e)
                traceback.print_exc()
                update_novel_status(novel_id, status="idle")
                from novel_creator.web.events import emit_event
                await emit_event("generation_error", {
                    "novel_id": novel_id,
                    "error": str(e),
                })

        task = asyncio.create_task(_run_generation())
        _generation_tasks[novel_id] = task

        return {"ok": True, "message": "Generation started"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/worlds/{novel_id}/resume")
async def api_resume_generation(novel_id: str, req: GenerateRequest):
    """Resume generation from last checkpoint."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        if novel_id in _generation_tasks and not _generation_tasks[novel_id].done():
            return {"ok": False, "error": "Generation already in progress"}

        update_novel_status(novel_id, status="generating")

        async def _run_resume():
            try:
                from novel_creator.graph.builder import compile_resume_graph
                from novel_creator.memory import checkpoint_store, world_store, foreshadow_store, timeline_store
                from novel_creator.models.character import CharacterProfile
                from novel_creator.models.relationship import Relationship, RelationshipGraph
                from novel_creator.web.events import emit_event
                from pathlib import Path

                conn = await get_connection(novel.db_path)

                cp = await checkpoint_store.load_latest(conn)
                if cp is None:
                    await conn.close()
                    update_novel_status(novel_id, status="paused")
                    await emit_event("generation_error", {"novel_id": novel_id, "error": "No checkpoint found"})
                    return

                world = await world_store.load_world(conn)
                outline = await world_store.load_outline(conn)
                foreshadows = await foreshadow_store.get_all_foreshadows(conn)
                plot_threads = await foreshadow_store.get_all_plot_threads(conn)
                timeline = await timeline_store.load_timeline(conn)

                # Import any edits to agent files
                try:
                    from novel_creator.sync.agent_files import AgentFileSync
                    novel_dir = Path(novel.db_path).parent
                    sync_obj = AgentFileSync(novel_dir)
                    await sync_obj.import_all(conn)
                except Exception:
                    pass

                if outline is None:
                    await conn.close()
                    update_novel_status(novel_id, status="idle")
                    await emit_event("generation_error", {"novel_id": novel_id, "error": "No outline found"})
                    return

                state_data = json.loads(cp.state_json)
                start_chapter = cp.completed_chapters

                cursor = await conn.execute("SELECT character_id, profile_json FROM characters")
                rows = await cursor.fetchall()
                characters = [CharacterProfile.model_validate_json(row["profile_json"]) for row in rows]

                cursor2 = await conn.execute("SELECT * FROM relationships")
                rel_rows = await cursor2.fetchall()
                rels = [
                    Relationship(
                        source_id=r["source_id"], target_id=r["target_id"],
                        relationship_type=r["relationship_type"],
                        trust=r["trust"], affection=r["affection"],
                        description=r["description"] or "",
                    ) for r in rel_rows
                ]
                relationships = RelationshipGraph(relationships=rels)
                chapter_summaries = state_data.get("chapter_summaries", [])

                await conn.close()

                resume_state = {
                    "genre": outline.genre,
                    "theme": outline.theme,
                    "premise": outline.premise,
                    "num_chapters": len(outline.chapters),
                    "num_characters": len(characters),
                    "outline": outline,
                    "characters": characters,
                    "relationships": relationships,
                    "world_view": world,
                    "foreshadows": foreshadows,
                    "plot_threads": plot_threads,
                    "current_chapter": start_chapter,
                    "current_scene": 0,
                    "chapters_completed": [],
                    "chapter_summaries": chapter_summaries[:start_chapter],
                    "character_actions": [],
                    "phase": "simulating",
                    "db_path": novel.db_path,
                    "generation_mode": req.mode,
                    "pause_after_chapter": False,
                    "foreshadow_issues": [],
                    "timeline": timeline,
                    "god_decision": None,
                }

                await emit_event("generation_started", {"novel_id": novel_id, "resumed": True})
                graph = compile_resume_graph()
                result = await graph.ainvoke(resume_state)

                if result.get("novel"):
                    update_novel_status(
                        novel_id, status="completed",
                        chapters_completed=len(result["novel"].chapters),
                        word_count=result["novel"].word_count,
                    )
                elif result.get("last_checkpoint_id"):
                    update_novel_status(novel_id, status="paused",
                                        chapters_completed=result.get("current_chapter", 0))
                else:
                    update_novel_status(novel_id, status="idle")

                await emit_event("generation_finished", {
                    "novel_id": novel_id,
                    "status": "completed" if result.get("novel") else "paused",
                })
            except Exception as e:
                logger.error("Resume failed for %s: %s", novel_id, e)
                traceback.print_exc()
                update_novel_status(novel_id, status="paused")
                from novel_creator.web.events import emit_event
                await emit_event("generation_error", {"novel_id": novel_id, "error": str(e)})

        task = asyncio.create_task(_run_resume())
        _generation_tasks[novel_id] = task
        return {"ok": True, "message": "Resume started"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/worlds/{novel_id}/pause")
async def api_pause_generation(novel_id: str):
    """Pause a running generation (will stop after current chapter completes)."""
    try:
        if novel_id in _generation_tasks and not _generation_tasks[novel_id].done():
            _generation_tasks[novel_id].cancel()
            del _generation_tasks[novel_id]
            update_novel_status(novel_id, status="paused")
            return {"ok": True, "message": "Generation paused"}
        else:
            update_novel_status(novel_id, status="paused")
            return {"ok": True, "message": "Status set to paused"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


class WorldSaveRequest(BaseModel):
    world: dict


@router.put("/world")
async def api_save_world(req: WorldSaveRequest, novel_id: str | None = Query(None)):
    """Save edited world-building data."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        world_json = json.dumps(req.world, ensure_ascii=False)
        await conn.execute(
            """INSERT INTO world_building (id, world_json)
               VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET world_json=excluded.world_json""",
            (world_json,),
        )
        await conn.commit()
        await conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class AnalyzePropositionRequest(BaseModel):
    step: int  # 1=what_is, 2=where_from, 3=where_to
    text: str
    context: dict = Field(default_factory=dict)  # previous steps


@router.post("/ai/analyze-proposition")
async def api_analyze_proposition(req: AnalyzePropositionRequest):
    """AI analysis of a proposition step (non-streaming)."""
    try:
        from langchain_openai import ChatOpenAI

        step_names = {1: "世界本质（是什么）", 2: "世界起源（从何而来）", 3: "世界命运（往何处去）"}
        step_name = step_names.get(req.step, "未知")

        context_parts = []
        if req.context.get("what_is"):
            context_parts.append(f"【世界本质】{req.context['what_is']}")
        if req.context.get("where_from"):
            context_parts.append(f"【世界起源】{req.context['where_from']}")
        context_text = "\n".join(context_parts) if context_parts else "（这是第一个命题）"

        system_prompt = (
            "你是一个专业的小说世界观顾问。用户正在通过三个终极命题来构建一个小说世界。\n"
            "请分析用户输入的命题，给出专业的评价和建议。\n"
            "输出格式 (JSON):\n"
            '{"analysis": "对基调和主题的简短判断", '
            '"conflict_points": ["可以挖掘的冲突点1", "冲突点2"], '
            '"suggestions": ["补充建议1", "建议2"], '
            '"references": ["类似作品参考1", "参考2"]}'
        )

        user_prompt = (
            f"当前步骤: {step_name}\n"
            f"已有命题:\n{context_text}\n\n"
            f"用户输入:\n{req.text}\n\n"
            "请分析这个命题并给出建议。返回 JSON 格式。"
        )

        llm = ChatOpenAI(
            model=settings.director_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        resp = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        # Try to parse as JSON, fallback to raw text
        content = resp.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1))
                except json.JSONDecodeError:
                    result = {"analysis": content, "suggestions": [], "references": []}
            else:
                result = {"analysis": content, "suggestions": [], "references": []}

        return result
    except Exception as e:
        return {
            "analysis": f"AI 分析暂不可用: {str(e)}",
            "suggestions": [],
            "references": [],
        }


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

    # Check if generation task is running
    is_running = novel_id in _generation_tasks and not _generation_tasks[novel_id].done()

    # Get DB progress
    progress = {"completed": 0, "total": 0, "phase": "idle", "paused": False}
    try:
        conn = await get_connection(novel.db_path)
        cursor = await conn.execute(
            "SELECT * FROM generation_checkpoints ORDER BY created_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        await conn.close()
        if row:
            progress = {
                "completed": row["completed_chapters"],
                "total": row["total_chapters"],
                "phase": row["phase"],
                "paused": row["phase"] not in ("done",),
            }
    except Exception:
        pass

    return {
        "novel_id": novel_id,
        "title": novel.title,
        "status": novel.status,
        "is_running": is_running,
        "chapters_completed": novel.chapters_completed,
        "chapters_total": novel.chapters_total,
        "word_count": novel.word_count,
        "progress": progress,
    }


# ======================================================================
# V4: Historian Chat API — 与史官对话撰写小说
# ======================================================================

class HistorianChatRequest(BaseModel):
    message: str
    novel_id: str
    history: list = Field(default_factory=list)  # [{role, content}, ...]


@router.post("/ai/historian-chat")
async def api_historian_chat(req: HistorianChatRequest):
    """Chat with the historian agent — uses all character memories, actions, world data to answer."""
    try:
        novel = get_novel_by_id(req.novel_id)
        if novel is None:
            return {"reply": "未找到该世界", "error": "not found"}

        db_path = novel.db_path
        conn = await get_connection(db_path)

        # Gather world context
        cursor_o = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row_o = await cursor_o.fetchone()
        outline_text = ""
        if row_o:
            outline = json.loads(row_o["outline_json"])
            outline_text = f"标题: {outline.get('title','')}\n类型: {outline.get('genre','')}\n前提: {outline.get('premise','')}\n核心冲突: {outline.get('central_conflict','')}"

        # Characters
        cursor_c = await conn.execute("SELECT character_id, profile_json FROM characters")
        char_rows = await cursor_c.fetchall()
        chars_text = ""
        for r in char_rows:
            p = json.loads(r["profile_json"])
            chars_text += f"\n【{p.get('name',r['character_id'])}】({p.get('role','')}) {p.get('backstory','')[:200]}"

        # Recent actions (last 50)
        cursor_a = await conn.execute(
            "SELECT character_id, chapter_index, scene_index, action_type, content, target_character_id "
            "FROM character_actions ORDER BY chapter_index DESC, scene_index DESC, id DESC LIMIT 50"
        )
        action_rows = await cursor_a.fetchall()
        actions_text = ""
        for a in action_rows:
            target = f" → {a['target_character_id']}" if a['target_character_id'] else ""
            actions_text += f"\n第{a['chapter_index']+1}章场景{a['scene_index']+1} [{a['action_type']}] {a['character_id']}{target}: {a['content'][:150]}"

        # World building
        cursor_w = await conn.execute("SELECT world_json FROM world_building WHERE id = 1")
        row_w = await cursor_w.fetchone()
        world_text = ""
        if row_w:
            w = json.loads(row_w["world_json"])
            world_text = f"世界: {w.get('world_name','')}\n{w.get('world_description','')[:300]}"

        # God decisions
        cursor_g = await conn.execute("SELECT decision_json FROM god_decisions ORDER BY chapter_index")
        god_rows = await cursor_g.fetchall()
        god_text = ""
        for g in god_rows:
            d = json.loads(g["decision_json"])
            guidance = d.get("next_chapter_guidance", "")[:200]
            events = ", ".join(e.get("title","") for e in d.get("world_events",[]))
            god_text += f"\n命运决策: {events} | 指引: {guidance}"

        # Chapter texts (summaries)
        cursor_t = await conn.execute(
            "SELECT DISTINCT chapter_index, title, summary FROM chapter_texts ORDER BY chapter_index"
        )
        chapter_rows = await cursor_t.fetchall()
        chapters_text = ""
        for ch in chapter_rows:
            chapters_text += f"\n第{ch['chapter_index']+1}章 {ch['title']}: {(ch['summary'] or '')[:100]}"

        await conn.close()

        system_prompt = (
            "你是这个小说世界的「史官」，掌握这个世界的所有信息：世界观、角色档案、角色的每一句话和每一个行动、命运决策、剧情走向。\n"
            "你的职责：\n"
            "1. 回答造物主（用户）关于这个世界的任何问题\n"
            "2. 根据造物主的要求，基于角色的记忆和行动撰写章节片段、对话场景、内心独白\n"
            "3. 分析角色关系发展、剧情冲突、伏笔回收情况\n"
            "4. 建议新角色、新剧情线、新的命运转折\n\n"
            "你掌握的信息：\n"
            f"## 故事大纲\n{outline_text}\n\n"
            f"## 世界观\n{world_text}\n\n"
            f"## 角色档案\n{chars_text}\n\n"
            f"## 已完成章节\n{chapters_text}\n\n"
            f"## 近期角色行动记录\n{actions_text}\n\n"
            f"## 命运决策\n{god_text}\n\n"
            "回复时使用中文，语言要符合小说世界的基调。"
        )

        messages = [{"role": "system", "content": system_prompt}]
        # Add chat history
        for h in req.history[-10:]:  # Keep last 10 turns
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": req.message})

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=settings.director_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        resp = await llm.ainvoke(messages)
        return {"reply": resp.content}
    except Exception as e:
        logger.error("Historian chat error: %s", e)
        return {"reply": f"史官暂时无法回应: {str(e)}", "error": str(e)}


# ======================================================================
# V4: Export & File Download APIs
# ======================================================================


@router.get("/worlds/{novel_id}/export/markdown")
async def api_export_markdown(novel_id: str):
    """Export the full novel as Markdown text."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return PlainTextResponse("未找到该世界", status_code=404)

        conn = await get_connection(novel.db_path)
        cursor0 = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row0 = await cursor0.fetchone()
        outline = json.loads(row0["outline_json"]) if row0 else {}
        title = outline.get("title", novel.title)

        cursor = await conn.execute(
            "SELECT chapter_index, scene_index, title, content "
            "FROM chapter_texts ORDER BY chapter_index, scene_index"
        )
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            return PlainTextResponse("暂无章节内容", status_code=404)

        chapters: dict[int, dict] = {}
        for r in rows:
            ci = r["chapter_index"]
            if ci not in chapters:
                chapters[ci] = {"title": r["title"], "scenes": []}
            chapters[ci]["scenes"].append(r["content"])

        parts = [f"# {title}\n"]
        for ci in sorted(chapters.keys()):
            ch = chapters[ci]
            parts.append(f"\n## 第{ci + 1}章 {ch['title']}\n")
            parts.append("\n\n".join(ch["scenes"]))

        full_text = "\n".join(parts)
        from urllib.parse import quote
        safe_filename = quote(f"{novel_id}.md")
        return PlainTextResponse(
            full_text,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
            },
        )
    except Exception as e:
        return PlainTextResponse(f"导出失败: {e}", status_code=500)


@router.get("/worlds/{novel_id}/export/json")
async def api_export_json(novel_id: str):
    """Export the full world data as JSON (outline, characters, world, timeline, etc.)."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"error": "not found"}

        conn = await get_connection(novel.db_path)

        # Outline
        cursor = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row = await cursor.fetchone()
        outline = json.loads(row["outline_json"]) if row else None

        # World
        cursor = await conn.execute("SELECT world_json FROM world_building WHERE id = 1")
        row = await cursor.fetchone()
        world = json.loads(row["world_json"]) if row else None

        # Characters
        cursor = await conn.execute("SELECT character_id, profile_json FROM characters")
        characters = [json.loads(r["profile_json"]) for r in await cursor.fetchall()]

        # Relationships
        cursor = await conn.execute("SELECT * FROM relationships")
        rels = [dict(r) for r in await cursor.fetchall()]

        # Propositions
        cursor = await conn.execute("SELECT what_is, where_from, where_to FROM world_propositions WHERE id = 1")
        prop_row = await cursor.fetchone()
        propositions = dict(prop_row) if prop_row else {}

        await conn.close()

        return {
            "novel_id": novel_id,
            "title": novel.title,
            "genre": novel.genre,
            "propositions": propositions,
            "outline": outline,
            "world": world,
            "characters": characters,
            "relationships": rels,
        }
    except Exception as e:
        return {"error": str(e)}


class HistorianWriteFileRequest(BaseModel):
    novel_id: str
    filename: str
    content: str


@router.post("/ai/historian-write-file")
async def api_historian_write_file(req: HistorianWriteFileRequest):
    """Historian writes a file to the novel's workspace/historian/ directory."""
    try:
        novel = get_novel_by_id(req.novel_id)
        if novel is None:
            return {"ok": False, "error": "not found"}

        novel_dir = Path(novel.db_path).parent
        historian_dir = novel_dir / "historian"
        historian_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = req.filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        if not safe_name:
            safe_name = "output.md"

        file_path = historian_dir / safe_name
        file_path.write_text(req.content, encoding="utf-8")

        return {"ok": True, "path": str(file_path), "filename": safe_name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/worlds/{novel_id}/files")
async def api_list_world_files(novel_id: str):
    """List all downloadable files in a novel's workspace."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"files": []}

        novel_dir = Path(novel.db_path).parent
        files = []

        # Historian output files
        historian_dir = novel_dir / "historian"
        if historian_dir.exists():
            for f in sorted(historian_dir.iterdir()):
                if f.is_file():
                    files.append({
                        "name": f.name,
                        "path": f"historian/{f.name}",
                        "size": f.stat().st_size,
                        "source": "historian",
                    })

        # Agent files
        agents_dir = novel_dir / "agents"
        if agents_dir.exists():
            for char_dir in sorted(agents_dir.iterdir()):
                if char_dir.is_dir():
                    for f in sorted(char_dir.iterdir()):
                        if f.is_file():
                            files.append({
                                "name": f"{char_dir.name}/{f.name}",
                                "path": f"agents/{char_dir.name}/{f.name}",
                                "size": f.stat().st_size,
                                "source": "agent",
                            })

        return {"files": files, "total": len(files)}
    except Exception as e:
        return {"error": str(e), "files": []}


@router.get("/worlds/{novel_id}/files/download")
async def api_download_file(novel_id: str, path: str = Query(...)):
    """Download a specific file from a novel's workspace."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return PlainTextResponse("not found", status_code=404)

        novel_dir = Path(novel.db_path).parent
        file_path = novel_dir / path

        # Security: ensure path stays within novel_dir
        if not str(file_path.resolve()).startswith(str(novel_dir.resolve())):
            return PlainTextResponse("forbidden", status_code=403)

        if not file_path.exists():
            return PlainTextResponse("file not found", status_code=404)

        return FileResponse(
            str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
        )
    except Exception as e:
        return PlainTextResponse(f"error: {e}", status_code=500)
