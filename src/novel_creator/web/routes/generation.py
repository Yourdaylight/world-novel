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

# Error storage — keeps the latest generation error per novel for polling
_generation_errors: dict[str, str] = {}


class GenerateRequest(BaseModel):
    mode: str = "full"  # "full" | "chapter_by_chapter"


async def _clear_generation_data(db_path: str) -> None:
    """Clear only generation products, preserving outlines, characters, foreshadows, etc."""
    conn = await get_connection(db_path)
    for table in (
        "chapter_texts",
        "character_actions",
        "scene_turns",
        "scene_metadata",
        "generation_checkpoints",
        "god_decisions",
        "timeline_events",
        "token_usage",
        "simulation_beats",
    ):
        await conn.execute(f"DELETE FROM {table}")  # noqa: S608
    await conn.commit()
    await conn.close()


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
        cursor = await conn.execute("SELECT what_is, where_from, where_to, expected_word_count FROM world_propositions WHERE id = 1")
        prop_row = await cursor.fetchone()
        await conn.close()

        propositions = {}
        expected_word_count = 1000000
        if prop_row:
            propositions = {
                "what_is": prop_row["what_is"],
                "where_from": prop_row["where_from"],
                "where_to": prop_row["where_to"],
            }
            expected_word_count = prop_row["expected_word_count"] or 1000000

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

        # Reset progress — fresh generation starts from scratch
        update_novel_status(novel_id, status="generating", chapters_completed=0, word_count=0)

        async def _run_generation():
            try:
                from novel_creator.graph.builder import compile_novel_graph
                from novel_creator.web.events import emit_event

                _generation_errors.pop(novel_id, None)

                await _clear_generation_data(novel.db_path)

                # Always re-save propositions after clearing (they were loaded before clear)
                conn2 = await get_connection(novel.db_path)
                await conn2.execute(
                    """INSERT INTO world_propositions (id, what_is, where_from, where_to, expected_word_count)
                       VALUES (1, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           what_is=excluded.what_is, where_from=excluded.where_from,
                           where_to=excluded.where_to, expected_word_count=excluded.expected_word_count""",
                    (
                        propositions.get("what_is", ""),
                        propositions.get("where_from", ""),
                        propositions.get("where_to", ""),
                        expected_word_count,
                    ),
                )
                await conn2.commit()
                await conn2.close()

                graph = compile_novel_graph()
                initial_state = {
                    "genre": novel.genre,
                    "theme": theme,
                    "premise": premise,
                    "num_chapters": 20,  # Base; director_node will derive from expected_word_count
                    "num_characters": 3,
                    "num_volumes": 0,
                    "db_path": novel.db_path,
                    "current_chapter": 0,
                    "current_scene": 0,
                    "chapters_completed": [],
                    "chapter_summaries": [],
                    "character_actions": [],
                    "scene_transcripts": [],
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
                _generation_errors[novel_id] = str(e)
                update_novel_status(novel_id, status="idle", chapters_completed=0)
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

                _generation_errors.pop(novel_id, None)

                conn = await get_connection(novel.db_path)

                cp = await checkpoint_store.load_latest(conn)

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
                    _generation_errors[novel_id] = "没有找到大纲，请重新开始生成"
                    update_novel_status(novel_id, status="idle", chapters_completed=0)
                    await emit_event("generation_error", {
                        "novel_id": novel_id,
                        "error": "没有找到大纲，请重新开始生成",
                    })
                    return

                # Determine start chapter from checkpoint or DB
                if cp is not None:
                    state_data = json.loads(cp.state_json)
                    start_chapter = cp.completed_chapters
                    chapter_summaries = state_data.get("chapter_summaries", [])
                else:
                    # No checkpoint — count chapters already in DB
                    cursor_count = await conn.execute(
                        "SELECT COUNT(DISTINCT chapter_index) FROM chapter_texts"
                    )
                    count_row = await cursor_count.fetchone()
                    start_chapter = count_row[0] if count_row else 0
                    chapter_summaries = []

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
                    "scene_transcripts": [],
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
                _generation_errors[novel_id] = str(e)
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


class WriteChapterRequest(BaseModel):
    chapter_index: int
    guidance: str = ""


@router.post("/worlds/{novel_id}/write-chapter")
async def api_write_chapter(novel_id: str, req: WriteChapterRequest):
    """Write a chapter from the simulation timeline (fully decoupled).

    Reads scene_turns from DB, gives the writer the full timeline,
    and lets it freely compose the narrative. Can run concurrently
    with simulation — no mutual blocking.
    """
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        conn = await get_connection(novel.db_path)
        import json as _json

        # Load outline for chapter title
        from novel_creator.memory.world_store import load_outline
        outline = await load_outline(conn)
        if not outline or req.chapter_index >= len(outline.chapters):
            await conn.close()
            return {"ok": False, "error": f"Chapter {req.chapter_index} not found in outline"}

        chapter_outline = outline.chapters[req.chapter_index]

        # Load character profiles + name map
        char_profiles: dict[str, str] = {}
        char_name_map: dict[str, str] = {}
        cursor_chars = await conn.execute("SELECT character_id, profile_json FROM characters")
        for cr in await cursor_chars.fetchall():
            try:
                profile = _json.loads(cr["profile_json"])
                name = profile.get('name', cr['character_id'])
                char_profiles[cr["character_id"]] = f"{name} ({profile.get('role', '')}) — {profile.get('speaking_style', '')}"
                char_name_map[cr["character_id"]] = name
            except Exception:
                char_profiles[cr["character_id"]] = cr["character_id"]
                char_name_map[cr["character_id"]] = cr["character_id"]

        # V9: Read timeline from simulation_beats (beat_range) if available,
        # falling back to scene_turns by chapter_index
        beat_range_start = chapter_outline.beat_range_start
        beat_range_end = chapter_outline.beat_range_end
        turn_rows = []
        meta_rows = []

        if beat_range_start is not None and beat_range_end is not None:
            # Query by beat_id for beats in the range
            cursor_beats = await conn.execute(
                "SELECT beat_id FROM simulation_beats WHERE sequence >= ? AND sequence <= ? AND status = 'completed' ORDER BY sequence",
                (beat_range_start, beat_range_end),
            )
            beat_rows = await cursor_beats.fetchall()
            beat_ids = [r["beat_id"] for r in beat_rows]

            if beat_ids:
                placeholders = ",".join("?" * len(beat_ids))
                cursor_turns = await conn.execute(
                    f"SELECT * FROM scene_turns WHERE beat_id IN ({placeholders}) ORDER BY scene_index, turn_index",
                    beat_ids,
                )
                turn_rows = await cursor_turns.fetchall()

                cursor_meta = await conn.execute(
                    f"SELECT * FROM scene_metadata WHERE beat_id IN ({placeholders}) ORDER BY scene_index",
                    beat_ids,
                )
                meta_rows = await cursor_meta.fetchall()

        # Fallback: query by chapter_index (legacy or no beat_range)
        if not turn_rows:
            cursor_turns = await conn.execute(
                "SELECT * FROM scene_turns WHERE chapter_index = ? ORDER BY scene_index, turn_index",
                (req.chapter_index,),
            )
            turn_rows = await cursor_turns.fetchall()

        if not meta_rows:
            cursor_meta = await conn.execute(
                "SELECT * FROM scene_metadata WHERE chapter_index = ? ORDER BY scene_index",
                (req.chapter_index,),
            )
            meta_rows = await cursor_meta.fetchall()

        # Build timeline text
        type_labels = {'say': '说', 'do': '做', 'think': '想（内心）', 'feel': '情绪表露', 'leave': '离开'}
        turns_by_scene: dict[int, list] = {}
        for t in turn_rows:
            turns_by_scene.setdefault(t["scene_index"], []).append(t)

        timeline_parts: list[str] = []
        for meta in meta_rows:
            si = meta["scene_index"]
            timeline_parts.append(f"### 场景{si + 1} — {meta['location']}")
            try:
                decisions = _json.loads(meta["opening_decisions_json"])
                if decisions:
                    timeline_parts.append("**角色开场心态：**")
                    for cid, d in decisions.items():
                        n = char_name_map.get(cid, cid)
                        timeline_parts.append(f"- {n}: 判断「{d.get('assessment', '')}」→ 渴望「{d.get('desire', '')}」→ 策略「{d.get('approach', '')}」({d.get('emotional_drive', '')})")
                    timeline_parts.append("")
            except Exception:
                pass
            for turn in turns_by_scene.get(si, []):
                n = char_name_map.get(turn["character_id"], turn["character_id"])
                label = type_labels.get(turn["turn_type"], turn["turn_type"])
                tgt = turn["target_id"]
                tgt_str = f" → {char_name_map.get(tgt, tgt)}" if tgt else ""
                vis = "（内心）" if not turn["is_visible"] else ""
                timeline_parts.append(f"  {turn['turn_index'] + 1}. [{n}] {label}{tgt_str}{vis}: {turn['content']}")
            timeline_parts.append(f"_({meta['total_turns']}轮, {meta['ended_by']})_\n")

        chapter_timeline = "\n".join(timeline_parts)

        # Fallback to character_actions if no scene_turns yet
        if not turn_rows:
            from novel_creator.models.memory import ActionType
            cursor_actions = await conn.execute(
                "SELECT * FROM character_actions WHERE chapter_index = ? ORDER BY id",
                (req.chapter_index,),
            )
            action_rows = await cursor_actions.fetchall()
            if not action_rows:
                await conn.close()
                return {"ok": False, "error": f"No simulation data for chapter {req.chapter_index + 1}"}
            fallback_parts = ["### 行动记录"]
            for ar in action_rows:
                n = char_name_map.get(ar["character_id"], ar["character_id"])
                tgt = ar["target_character_id"]
                tgt_str = f" → {char_name_map.get(tgt, tgt)}" if tgt else ""
                fallback_parts.append(f"- [{n}] {ar['action_type']}{tgt_str}: {ar['content']}")
            chapter_timeline = "\n".join(fallback_parts)

        # World context
        from novel_creator.memory.world_store import load_world
        world = await load_world(conn)
        world_context = world.summary() if world else ""

        # Previous chapter summaries
        prev_cursor = await conn.execute(
            "SELECT summary FROM chapter_texts WHERE chapter_index < ? ORDER BY chapter_index DESC LIMIT 2",
            (req.chapter_index,),
        )
        prev_context = "\n".join(r["summary"] for r in await prev_cursor.fetchall() if r["summary"])

        # Foreshadow instructions
        from novel_creator.memory import foreshadow_store
        to_plant, to_payoff = await foreshadow_store.get_pending_for_chapter(conn, req.chapter_index)
        fs_lines: list[str] = []
        for fs in to_plant:
            fs_lines.append(f"请在叙事中自然埋入暗示: {fs.description} (参考: {fs.hint_text})")
        for fs in to_payoff:
            fs_lines.append(f"请在叙事中揭示/回收: {fs.description}")

        await conn.close()

        # Run writer with full timeline
        from novel_creator.agents.writer import WriterAgent
        from novel_creator.models.narrative import Chapter, Scene

        writer = WriterAgent()
        guidance_block = f"\n\n用户写作要求: {req.guidance}" if req.guidance else ""

        scene = await writer.write_scene(
            chapter_index=req.chapter_index,
            scene_index=0,
            location="（多场景）",
            character_actions=[],
            character_profiles=char_profiles,
            previous_context=prev_context,
            world_context=world_context,
            foreshadow_instructions="\n".join(fs_lines),
            director_intent=chapter_outline.summary + guidance_block,
            chapter_timeline=chapter_timeline,
            word_count_target=2500,
        )

        chapter = Chapter(
            chapter_index=req.chapter_index,
            title=chapter_outline.title,
            scenes=[scene],
        )
        summary = await writer.write_chapter_summary(chapter.full_text)

        # Save
        conn2 = await get_connection(novel.db_path)
        await conn2.execute(
            """INSERT INTO chapter_texts (chapter_index, scene_index, title, content, pov_character, summary)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(chapter_index, scene_index) DO UPDATE SET
                   content=excluded.content, pov_character=excluded.pov_character, summary=excluded.summary""",
            (req.chapter_index, 0, chapter_outline.title, scene.content, scene.pov_character, summary),
        )
        await conn2.commit()
        await conn2.close()

        from novel_creator.web.events import emit_event
        await emit_event("chapter_written", {
            "chapter": req.chapter_index,
            "title": chapter_outline.title,
            "word_count": len(chapter.full_text),
        })

        return {"ok": True, "word_count": len(chapter.full_text), "title": chapter_outline.title}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


class RewriteRequest(BaseModel):
    chapter_index: int
    guidance: str = ""


@router.post("/worlds/{novel_id}/rewrite-chapter")
async def api_rewrite_chapter(novel_id: str, req: RewriteRequest):
    """Rewrite a single chapter's narrative text without re-simulating characters.

    The simulation layer (character actions, memories, relationships) stays unchanged.
    Only the writer/chronicler layer is re-run to produce new literary text.
    """
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        conn = await get_connection(novel.db_path)

        # Load outline
        from novel_creator.memory.world_store import load_outline
        outline = await load_outline(conn)
        if not outline or req.chapter_index >= len(outline.chapters):
            await conn.close()
            return {"ok": False, "error": f"Chapter {req.chapter_index} not found in outline"}

        chapter_outline = outline.chapters[req.chapter_index]

        # Load character profiles
        from novel_creator.memory.character_memory import CharacterMemory
        char_profiles: dict[str, str] = {}
        cursor_chars = await conn.execute("SELECT character_id, profile_json FROM characters")
        char_rows = await cursor_chars.fetchall()
        import json as _json
        for cr in char_rows:
            try:
                profile = _json.loads(cr["profile_json"])
                char_profiles[cr["character_id"]] = f"{profile.get('name', cr['character_id'])} ({profile.get('role', '')}) — {profile.get('speaking_style', '')}"
            except Exception:
                char_profiles[cr["character_id"]] = cr["character_id"]

        # Load existing character actions for this chapter
        from novel_creator.models.memory import CharacterAction, ActionType
        cursor_actions = await conn.execute(
            "SELECT * FROM character_actions WHERE chapter_index = ? ORDER BY id",
            (req.chapter_index,),
        )
        action_rows = await cursor_actions.fetchall()
        actions: list[CharacterAction] = []
        for ar in action_rows:
            actions.append(CharacterAction(
                character_id=ar["character_id"],
                chapter_index=ar["chapter_index"],
                scene_index=ar["scene_index"],
                action_type=ActionType(ar["action_type"]),
                content=ar["content"],
                target_character_id=ar["target_character_id"],
            ))

        # Load world context
        from novel_creator.memory.world_store import load_world
        world = await load_world(conn)
        world_context = world.summary() if world else ""

        # Previous context from prior chapters
        prev_cursor = await conn.execute(
            "SELECT summary FROM chapter_texts WHERE chapter_index < ? ORDER BY chapter_index DESC LIMIT 2",
            (req.chapter_index,),
        )
        prev_rows = await prev_cursor.fetchall()
        prev_context = "\n".join(r["summary"] for r in prev_rows if r["summary"])

        await conn.close()

        # Re-run writer for each scene
        from novel_creator.agents.writer import WriterAgent
        from novel_creator.models.narrative import Chapter

        writer = WriterAgent()
        scenes = []
        for scene_beat in chapter_outline.scenes:
            scene_actions = [a for a in actions if a.scene_index == scene_beat.scene_index]
            location_desc = ""
            if world:
                loc = world.get_location(scene_beat.location)
                if loc:
                    location_desc = f"{loc.name}: {loc.description}"

            # Build guidance into director_intent
            director_intent = scene_beat.objective
            if req.guidance:
                director_intent += f"\n\n用户重写要求: {req.guidance}"

            scene = await writer.write_scene(
                chapter_index=req.chapter_index,
                scene_index=scene_beat.scene_index,
                location=scene_beat.location,
                character_actions=scene_actions,
                character_profiles=char_profiles,
                previous_context=prev_context,
                world_context=world_context,
                location_description=location_desc,
                director_intent=director_intent,
            )
            scenes.append(scene)

        chapter = Chapter(
            chapter_index=req.chapter_index,
            title=chapter_outline.title,
            scenes=scenes,
        )
        summary = await writer.write_chapter_summary(chapter.full_text)

        # Save back to DB
        conn2 = await get_connection(novel.db_path)
        for scene in scenes:
            await conn2.execute(
                """INSERT INTO chapter_texts (chapter_index, scene_index, title, content, pov_character, summary)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(chapter_index, scene_index) DO UPDATE SET
                       content=excluded.content, pov_character=excluded.pov_character, summary=excluded.summary""",
                (req.chapter_index, scene.scene_index, chapter_outline.title,
                 scene.content, scene.pov_character, summary),
            )
        await conn2.commit()
        await conn2.close()

        return {
            "ok": True,
            "word_count": len(chapter.full_text),
            "title": chapter_outline.title,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        # No checkpoint — count actual chapters and read total from outline
        cursor2 = await conn.execute(
            "SELECT COUNT(DISTINCT chapter_index) FROM chapter_texts"
        )
        count_row = await cursor2.fetchone()
        actual = count_row[0] if count_row else 0
        # Read total from outline
        total = 0
        try:
            cursor3 = await conn.execute("SELECT outline_json FROM story_outline LIMIT 1")
            outline_row = await cursor3.fetchone()
            if outline_row:
                import json as _json
                outline_data = _json.loads(outline_row[0])
                total = len(outline_data.get("chapters", []))
        except Exception:
            pass
        await conn.close()
        return {"completed": actual, "total": total, "phase": "idle", "paused": False}
    except Exception as e:
        return {"error": str(e), "completed": 0, "total": 0, "phase": "error", "paused": False}


@router.get("/worlds/{novel_id}/generation-error")
async def get_generation_error(novel_id: str):
    """Return the latest generation error for a novel (if any)."""
    error = _generation_errors.get(novel_id)
    return {"error": error}


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


# ======================================================================
# V9: Decoupled pipeline — Preparation + Simulation APIs
# ======================================================================

# Background task trackers for new pipelines
_preparation_tasks: dict[str, asyncio.Task] = {}
_simulation_tasks: dict[str, asyncio.Task] = {}


@router.post("/worlds/{novel_id}/prepare")
async def api_start_preparation(novel_id: str, req: GenerateRequest):
    """Run the one-shot preparation graph (director → world → foreshadow → beat_plan).

    After this completes, simulation_beats are in DB and the simulation
    graph can be started independently.
    """
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        if novel_id in _preparation_tasks and not _preparation_tasks[novel_id].done():
            return {"ok": False, "error": "Preparation already in progress"}

        # Load propositions
        conn = await get_connection(novel.db_path)
        cursor = await conn.execute("SELECT what_is, where_from, where_to, expected_word_count FROM world_propositions WHERE id = 1")
        prop_row = await cursor.fetchone()
        await conn.close()

        propositions = {}
        expected_word_count = 1000000
        if prop_row:
            propositions = {
                "what_is": prop_row["what_is"],
                "where_from": prop_row["where_from"],
                "where_to": prop_row["where_to"],
            }
            expected_word_count = prop_row["expected_word_count"] or 1000000

        premise = novel.propositions.get("premise", "") if novel.propositions else ""
        if propositions and any(propositions.values()):
            parts = []
            if propositions.get("what_is"):
                parts.append(f"\u3010\u4e16\u754c\u672c\u8d28\u3011{propositions['what_is']}")
            if propositions.get("where_from"):
                parts.append(f"\u3010\u4e16\u754c\u8d77\u6e90\u3011{propositions['where_from']}")
            if propositions.get("where_to"):
                parts.append(f"\u3010\u4e16\u754c\u547d\u8fd0\u3011{propositions['where_to']}")
            if premise:
                parts.append(f"\u3010\u6545\u4e8b\u524d\u63d0\u3011{premise}")
            premise = "\n".join(parts)
        if not premise:
            premise = f"\u4e00\u4e2a\u5173\u4e8e{novel.genre}\u7684\u6545\u4e8b"

        theme = novel.propositions.get("theme", "") if novel.propositions else ""
        if not theme:
            theme = "\u6210\u957f\u4e0e\u547d\u8fd0"

        update_novel_status(novel_id, status="generating", chapters_completed=0, word_count=0)

        async def _run_preparation():
            try:
                from novel_creator.graph.builder import compile_preparation_graph
                from novel_creator.web.events import emit_event

                _generation_errors.pop(novel_id, None)
                await _clear_generation_data(novel.db_path)

                # Re-save propositions
                conn2 = await get_connection(novel.db_path)
                await conn2.execute(
                    """INSERT INTO world_propositions (id, what_is, where_from, where_to, expected_word_count)
                       VALUES (1, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           what_is=excluded.what_is, where_from=excluded.where_from,
                           where_to=excluded.where_to, expected_word_count=excluded.expected_word_count""",
                    (propositions.get("what_is", ""), propositions.get("where_from", ""),
                     propositions.get("where_to", ""), expected_word_count),
                )
                await conn2.commit()
                await conn2.close()

                graph = compile_preparation_graph()
                initial_state = {
                    "genre": novel.genre,
                    "theme": theme,
                    "premise": premise,
                    "num_chapters": 20,
                    "num_characters": 3,
                    "num_volumes": 0,
                    "db_path": novel.db_path,
                    "phase": "directing",
                    "foreshadows": [],
                    "plot_threads": [],
                    "simulation_beats": [],
                }

                await emit_event("preparation_started", {"novel_id": novel_id})
                result = await graph.ainvoke(initial_state)

                update_novel_status(novel_id, status="prepared")
                await emit_event("preparation_finished", {
                    "novel_id": novel_id,
                    "beat_count": len(result.get("simulation_beats", [])),
                })
            except Exception as e:
                logger.error("Preparation failed for %s: %s", novel_id, e)
                traceback.print_exc()
                _generation_errors[novel_id] = str(e)
                update_novel_status(novel_id, status="idle")
                from novel_creator.web.events import emit_event
                await emit_event("generation_error", {"novel_id": novel_id, "error": str(e)})

        task = asyncio.create_task(_run_preparation())
        _preparation_tasks[novel_id] = task
        return {"ok": True, "message": "Preparation started"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/worlds/{novel_id}/simulate")
async def api_start_simulation(novel_id: str):
    """Start the continuous simulation loop graph.

    Requires preparation to have completed (simulation_beats in DB).
    Can run independently of writing — writer reads from DB.
    """
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        if novel_id in _simulation_tasks and not _simulation_tasks[novel_id].done():
            return {"ok": False, "error": "Simulation already in progress"}

        # Verify beats exist
        conn = await get_connection(novel.db_path)
        cursor = await conn.execute("SELECT COUNT(*) FROM simulation_beats")
        row = await cursor.fetchone()
        beat_count = row[0] if row else 0
        await conn.close()

        if beat_count == 0:
            return {"ok": False, "error": "No simulation beats found. Run preparation first."}

        update_novel_status(novel_id, status="simulating")

        async def _run_simulation():
            try:
                from novel_creator.graph.builder import compile_simulation_graph
                from novel_creator.web.events import emit_event

                _generation_errors.pop(novel_id, None)

                graph = compile_simulation_graph()
                initial_state = {
                    "db_path": novel.db_path,
                    "current_beats": [],
                    "completed_beat_count": 0,
                    "total_beat_count": beat_count,
                    "beats_since_checkpoint": 0,
                    "phase": "loading",
                    "should_stop": False,
                }

                await emit_event("simulation_started", {"novel_id": novel_id, "beat_count": beat_count})
                result = await graph.ainvoke(initial_state)

                update_novel_status(novel_id, status="simulated")
                await emit_event("simulation_finished", {
                    "novel_id": novel_id,
                    "completed": result.get("completed_beat_count", 0),
                    "total": result.get("total_beat_count", 0),
                })
            except Exception as e:
                logger.error("Simulation failed for %s: %s", novel_id, e)
                traceback.print_exc()
                _generation_errors[novel_id] = str(e)
                update_novel_status(novel_id, status="prepared")
                from novel_creator.web.events import emit_event
                await emit_event("generation_error", {"novel_id": novel_id, "error": str(e)})

        task = asyncio.create_task(_run_simulation())
        _simulation_tasks[novel_id] = task
        return {"ok": True, "message": "Simulation started", "beat_count": beat_count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/worlds/{novel_id}/stop-simulation")
async def api_stop_simulation(novel_id: str):
    """Stop a running simulation gracefully (finishes current beat)."""
    if novel_id in _simulation_tasks and not _simulation_tasks[novel_id].done():
        _simulation_tasks[novel_id].cancel()
        del _simulation_tasks[novel_id]
        update_novel_status(novel_id, status="prepared")
        return {"ok": True, "message": "Simulation stopped"}
    return {"ok": True, "message": "No simulation running"}


@router.get("/worlds/{novel_id}/simulation-progress")
async def api_simulation_progress(novel_id: str):
    """Get simulation progress (completed beats / total beats)."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        conn = await get_connection(novel.db_path)

        cursor_total = await conn.execute("SELECT COUNT(*) FROM simulation_beats")
        total_row = await cursor_total.fetchone()
        total = total_row[0] if total_row else 0

        cursor_completed = await conn.execute("SELECT COUNT(*) FROM simulation_beats WHERE status = 'completed'")
        completed_row = await cursor_completed.fetchone()
        completed = completed_row[0] if completed_row else 0

        cursor_simulating = await conn.execute("SELECT COUNT(*) FROM simulation_beats WHERE status = 'simulating'")
        simulating_row = await cursor_simulating.fetchone()
        simulating = simulating_row[0] if simulating_row else 0

        await conn.close()

        running = novel_id in _simulation_tasks and not _simulation_tasks[novel_id].done()

        return {
            "total": total,
            "completed": completed,
            "simulating": simulating,
            "pending": total - completed - simulating,
            "running": running,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/worlds/{novel_id}/simulation-beats")
async def api_list_simulation_beats(novel_id: str):
    """List all simulation beats with their status."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"ok": False, "error": f"Novel '{novel_id}' not found"}

        conn = await get_connection(novel.db_path)
        cursor = await conn.execute(
            "SELECT beat_id, sequence, story_time, location, objective, status, "
            "suggested_chapter, parallel_group FROM simulation_beats ORDER BY sequence"
        )
        rows = await cursor.fetchall()
        await conn.close()

        beats = [
            {
                "beat_id": r["beat_id"],
                "sequence": r["sequence"],
                "story_time": r["story_time"],
                "location": r["location"],
                "objective": r["objective"],
                "status": r["status"],
                "suggested_chapter": r["suggested_chapter"],
                "parallel_group": r["parallel_group"],
            }
            for r in rows
        ]
        return {"beats": beats, "total": len(beats)}
    except Exception as e:
        return {"error": str(e)}
