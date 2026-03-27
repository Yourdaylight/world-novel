"""Story data query routes: /story, /relationships, /chapters, /actions/{ch}, /emotions/{char}, /world GET, /outline, /foreshadows, /plot-threads, /timeline, /god-decisions."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from novel_creator.memory.database import get_connection

from ._helpers import _get_novel_db

router = APIRouter()


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


@router.get("/token-stats")
async def get_token_stats(novel_id: str | None = Query(None)):
    """Get token usage statistics."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)

        # Total
        cursor = await conn.execute(
            "SELECT COALESCE(SUM(prompt_tokens),0) as p, COALESCE(SUM(completion_tokens),0) as c, COALESCE(SUM(total_tokens),0) as t FROM token_usage"
        )
        total_row = await cursor.fetchone()

        # By role
        cursor2 = await conn.execute(
            "SELECT role, SUM(prompt_tokens) as p, SUM(completion_tokens) as c, SUM(total_tokens) as t FROM token_usage GROUP BY role ORDER BY t DESC"
        )
        role_rows = await cursor2.fetchall()

        # By chapter
        cursor3 = await conn.execute(
            "SELECT chapter_index, SUM(total_tokens) as t FROM token_usage WHERE chapter_index >= 0 GROUP BY chapter_index ORDER BY chapter_index"
        )
        chapter_rows = await cursor3.fetchall()

        await conn.close()
        return {
            "total": {
                "prompt_tokens": total_row["p"],
                "completion_tokens": total_row["c"],
                "total_tokens": total_row["t"],
            },
            "by_role": [
                {"role": r["role"], "prompt_tokens": r["p"], "completion_tokens": r["c"], "total_tokens": r["t"]}
                for r in role_rows
            ],
            "by_chapter": [
                {"chapter_index": r["chapter_index"], "total_tokens": r["t"]}
                for r in chapter_rows
            ],
        }
    except Exception as e:
        return {"error": str(e), "total": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "by_role": [], "by_chapter": []}


@router.get("/relationship-history")
async def get_relationship_history(
    novel_id: str | None = Query(None),
    source_id: str | None = Query(None),
    target_id: str | None = Query(None),
    chapter_index: int | None = Query(None),
):
    """Get relationship history snapshots, optionally filtered."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)

        query = "SELECT * FROM relationship_history WHERE 1=1"
        params: list = []
        if source_id:
            query += " AND (source_id = ? OR target_id = ?)"
            params.extend([source_id, source_id])
        if target_id:
            query += " AND (source_id = ? OR target_id = ?)"
            params.extend([target_id, target_id])
        if chapter_index is not None:
            query += " AND chapter_index = ?"
            params.append(chapter_index)
        query += " ORDER BY chapter_index, id"

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await conn.close()

        return {
            "history": [
                {
                    "source_id": r["source_id"],
                    "target_id": r["target_id"],
                    "relationship_type": r["relationship_type"],
                    "trust": r["trust"],
                    "affection": r["affection"],
                    "description": r["description"],
                    "chapter_index": r["chapter_index"],
                    "change_reason": r["change_reason"],
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"error": str(e), "history": []}
