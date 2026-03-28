"""Generation control routes: /worlds/{id}/generate, /worlds/{id}/resume, /worlds/{id}/pause, /progress, /checkpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback

from fastapi import APIRouter, Query
from pydantic import BaseModel

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import (
    get_novel_by_id,
    update_novel_status,
)

from ._helpers import _get_novel_db

logger = logging.getLogger("novel_creator.web")

router = APIRouter()

# Background task tracker
_generation_tasks: dict[str, asyncio.Task] = {}


class GenerateRequest(BaseModel):
    mode: str = "full"  # "full" | "chapter_by_chapter"


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


@router.get("/progress")
async def get_progress(novel_id: str | None = Query(None)):
    """Get generation progress from the latest checkpoint, with DB fallback."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            "SELECT * FROM generation_checkpoints ORDER BY created_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row is not None:
            await conn.close()
            return {
                "completed": row["completed_chapters"],
                "total": row["total_chapters"],
                "phase": row["phase"],
                "paused": row["phase"] not in ("done",),
                "checkpoint_id": row["checkpoint_id"],
                "novel_title": row["novel_title"],
            }
        # No checkpoint — count actual chapters as fallback
        cursor2 = await conn.execute(
            "SELECT COUNT(DISTINCT chapter_index) FROM chapter_texts"
        )
        count_row = await cursor2.fetchone()
        actual = count_row[0] if count_row else 0
        await conn.close()
        if actual > 0:
            return {"completed": actual, "total": 0, "phase": "idle", "paused": False}
        return {"completed": 0, "total": 0, "phase": "idle", "paused": False}
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
