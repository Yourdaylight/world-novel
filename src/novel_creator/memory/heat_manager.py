"""Memory heat decay and consolidation manager (MemoryOS).

Implements the heat-based segmented paging strategy from the Survey on AI Memory paper.
Each episodic memory has a heat_score that decays per chapter and gets boosted on access.
Cold memories are consolidated into era summaries via LLM compression.
"""

from __future__ import annotations

import json
import logging
import uuid

import aiosqlite

from novel_creator.config import settings

logger = logging.getLogger("novel_creator.memory.heat")


class HeatManager:
    """Manages memory heat decay, partitioning, and cold-zone consolidation."""

    def __init__(
        self,
        conn: aiosqlite.Connection,
        *,
        decay_factor: float | None = None,
        access_bonus: float | None = None,
        trauma_floor: float | None = None,
        cold_threshold: float | None = None,
        consolidate_count: int | None = None,
    ):
        self.conn = conn
        self.decay_factor = decay_factor or settings.memory_decay_factor
        self.access_bonus = access_bonus or settings.memory_access_bonus
        self.trauma_floor = trauma_floor or settings.memory_trauma_floor
        self.cold_threshold = cold_threshold or settings.memory_cold_threshold
        self.consolidate_count = consolidate_count or settings.memory_consolidate_count

    async def decay_all(self, character_id: str, current_chapter: int) -> int:
        """Batch-decay all non-consolidated memories for a character.

        heat_score = importance * decay_factor^(current_chapter - chapter_index)
                   + access_bonus * access_count

        Returns the number of rows updated.
        """
        await self.conn.execute(
            """UPDATE episodic_memories
               SET heat_score = MAX(
                   importance * POWER(?, ? - chapter_index)
                   + ? * access_count,
                   0.0
               )
               WHERE character_id = ? AND consolidated = 0""",
            (
                self.decay_factor,
                current_chapter,
                self.access_bonus,
                character_id,
            ),
        )
        # Enforce trauma floor: memories linked to trauma_memories keep minimum heat
        await self.conn.execute(
            """UPDATE episodic_memories
               SET heat_score = MAX(heat_score, ?)
               WHERE character_id = ? AND consolidated = 0
                 AND importance >= 0.8""",
            (self.trauma_floor, character_id),
        )
        await self.conn.commit()
        cursor = await self.conn.execute(
            "SELECT changes()"
        )
        row = await cursor.fetchone()
        count = row[0] if row else 0
        logger.info(
            "Decayed memories for %s at chapter %d (factor=%.2f)",
            character_id, current_chapter, self.decay_factor,
        )
        return count

    async def record_access(self, memory_id: str, current_chapter: int) -> None:
        """Boost heat when a memory is retrieved/accessed."""
        await self.conn.execute(
            """UPDATE episodic_memories
               SET access_count = access_count + 1,
                   last_accessed_chapter = ?,
                   heat_score = heat_score + ?
               WHERE memory_id = ?""",
            (current_chapter, self.access_bonus, memory_id),
        )
        await self.conn.commit()

    async def get_partition(self, character_id: str) -> dict[str, list[dict]]:
        """Return memories partitioned by heat zone.

        Returns: {hot: [...], warm: [...], cold: [...], frozen: [...]}
        """
        cursor = await self.conn.execute(
            """SELECT memory_id, chapter_index, scene_index, content,
                      importance, emotional_valence, involved_characters,
                      heat_score, access_count, consolidated
               FROM episodic_memories
               WHERE character_id = ?
               ORDER BY heat_score DESC""",
            (character_id,),
        )
        rows = await cursor.fetchall()

        result: dict[str, list[dict]] = {
            "hot": [], "warm": [], "cold": [], "frozen": [],
        }
        for r in rows:
            item = {
                "memory_id": r["memory_id"],
                "chapter_index": r["chapter_index"],
                "scene_index": r["scene_index"],
                "content": r["content"],
                "importance": r["importance"],
                "emotional_valence": r["emotional_valence"],
                "involved_characters": json.loads(r["involved_characters"] or "[]"),
                "heat_score": r["heat_score"],
                "access_count": r["access_count"],
                "consolidated": bool(r["consolidated"]),
            }
            heat = r["heat_score"]
            if r["consolidated"]:
                continue  # Skip consolidated memories from active partitions
            if r["importance"] >= 0.8 and heat >= self.trauma_floor:
                result["frozen"].append(item)
            elif heat >= 0.5:
                result["hot"].append(item)
            elif heat >= self.cold_threshold:
                result["warm"].append(item)
            else:
                result["cold"].append(item)

        return result

    async def get_cold_memories(
        self, character_id: str, limit: int = 50,
    ) -> list[dict]:
        """Get cold-zone memories eligible for consolidation."""
        cursor = await self.conn.execute(
            """SELECT memory_id, chapter_index, scene_index, content,
                      importance, heat_score
               FROM episodic_memories
               WHERE character_id = ? AND consolidated = 0
                 AND heat_score < ?
                 AND importance < 0.8
               ORDER BY chapter_index ASC
               LIMIT ?""",
            (character_id, self.cold_threshold, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def consolidate_cold(
        self, character_id: str, *, llm=None,
    ) -> str | None:
        """Consolidate cold memories into an era summary.

        If cold-zone count exceeds consolidate_count, groups by chapter range,
        calls LLM to compress, writes era_summary, and marks originals as consolidated.

        Returns summary_id if consolidation happened, None otherwise.
        """
        cold = await self.get_cold_memories(character_id, limit=100)
        if len(cold) < self.consolidate_count:
            return None

        # Group by chapter range
        chapters = [m["chapter_index"] for m in cold]
        ch_start = min(chapters)
        ch_end = max(chapters)
        memory_texts = [
            f"[第{m['chapter_index']+1}章] {m['content']}" for m in cold
        ]
        memory_ids = [m["memory_id"] for m in cold]

        # LLM compression
        if llm is not None:
            prompt = (
                "你是一个记忆整合专家。以下是一个角色的多条旧记忆，"
                "请将它们压缩为一段简洁的时代摘要，"
                "保留核心事件和情感转折，去除细节。用第三人称叙述，不超过200字。\n\n"
                + "\n".join(memory_texts)
            )
            try:
                resp = await llm.ainvoke([{"role": "user", "content": prompt}])
                summary_text = resp.content.strip()
            except Exception as e:
                logger.warning("LLM consolidation failed: %s", e)
                summary_text = "；".join(
                    m["content"][:30] for m in cold[:5]
                ) + "……（自动摘要失败，保留关键片段）"
        else:
            summary_text = "；".join(
                m["content"][:40] for m in cold[:8]
            ) + f"……（共{len(cold)}条记忆，第{ch_start+1}-{ch_end+1}章）"

        summary_id = str(uuid.uuid4())
        await self.conn.execute(
            """INSERT INTO era_summaries
               (summary_id, character_id, era_id, chapter_start, chapter_end,
                summary, source_memory_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                summary_id, character_id, "",
                ch_start, ch_end,
                summary_text, json.dumps(memory_ids),
            ),
        )

        # Mark originals as consolidated
        placeholders = ",".join("?" * len(memory_ids))
        await self.conn.execute(
            f"UPDATE episodic_memories SET consolidated = 1 WHERE memory_id IN ({placeholders})",
            memory_ids,
        )
        await self.conn.commit()

        logger.info(
            "Consolidated %d cold memories for %s (ch %d-%d) → %s",
            len(cold), character_id, ch_start, ch_end, summary_id,
        )
        return summary_id

    async def get_era_summaries(self, character_id: str) -> list[dict]:
        """Get all era summaries for a character."""
        cursor = await self.conn.execute(
            """SELECT summary_id, character_id, era_id, chapter_start, chapter_end,
                      summary, source_memory_ids, created_at
               FROM era_summaries
               WHERE character_id = ?
               ORDER BY chapter_start""",
            (character_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "summary_id": r["summary_id"],
                "era_id": r["era_id"],
                "chapter_start": r["chapter_start"],
                "chapter_end": r["chapter_end"],
                "summary": r["summary"],
                "source_memory_count": len(json.loads(r["source_memory_ids"] or "[]")),
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]

    async def get_stats(self, character_id: str) -> dict:
        """Get heat distribution statistics."""
        partition = await self.get_partition(character_id)
        return {
            "hot_count": len(partition["hot"]),
            "warm_count": len(partition["warm"]),
            "cold_count": len(partition["cold"]),
            "frozen_count": len(partition["frozen"]),
            "total_active": (
                len(partition["hot"]) + len(partition["warm"])
                + len(partition["cold"]) + len(partition["frozen"])
            ),
        }
