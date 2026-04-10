"""Character detail routes: /characters/{id}/full-profile, /characters/{id}/actions-all, /characters/{id}/memories, /agents/{id}/files, /agents/{id}/soul PUT."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from novel_creator.memory.database import get_connection

from ._helpers import _get_novel_db

router = APIRouter()


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


@router.get("/characters/{character_id}/memory-heat")
async def get_memory_heat(character_id: str, novel_id: str | None = Query(None)):
    """Get memory heat distribution (Hot/Warm/Cold/Frozen partitions + stats)."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        from novel_creator.memory.heat_manager import HeatManager
        hm = HeatManager(conn)
        partition = await hm.get_partition(character_id)
        stats = await hm.get_stats(character_id)
        await conn.close()
        return {"partition": partition, "stats": stats}
    except Exception as e:
        return {"error": str(e), "partition": {}, "stats": {}}


@router.get("/characters/{character_id}/era-summaries")
async def get_era_summaries(character_id: str, novel_id: str | None = Query(None)):
    """Get era summaries (compressed cold-zone memories) for a character."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        from novel_creator.memory.heat_manager import HeatManager
        hm = HeatManager(conn)
        summaries = await hm.get_era_summaries(character_id)
        await conn.close()
        return {"summaries": summaries, "total": len(summaries)}
    except Exception as e:
        return {"error": str(e), "summaries": [], "total": 0}


@router.post("/memory/consolidate")
async def consolidate_memories(
    character_id: str = Query(...),
    novel_id: str | None = Query(None),
):
    """Manually trigger cold-zone memory consolidation for a character."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        from novel_creator.memory.heat_manager import HeatManager
        hm = HeatManager(conn)
        summary_id = await hm.consolidate_cold(character_id)
        await conn.close()
        if summary_id:
            return {"ok": True, "summary_id": summary_id}
        return {"ok": True, "summary_id": None, "message": "Not enough cold memories to consolidate"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/agents/{character_id}/files")
async def get_agent_files(character_id: str, novel_id: str | None = Query(None)):
    """Read agent.md and soul.md for a character."""
    try:
        db_path = await _get_novel_db(novel_id)
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
