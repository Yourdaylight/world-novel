"""Episodic memory CRUD operations.

V10: Supports optional Qdrant dual-write and search_similar().
"""

from __future__ import annotations

import json
import logging
import uuid

import aiosqlite

from novel_creator.models.memory import EpisodicMemory

logger = logging.getLogger("novel_creator.memory.vector")


class EpisodicStore:
    def __init__(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        *,
        vector_store=None,
    ):
        self.conn = conn
        self.character_id = character_id
        self._vector_store = vector_store

    async def add(self, memory: EpisodicMemory) -> str:
        memory_id = memory.memory_id or str(uuid.uuid4())
        await self.conn.execute(
            """INSERT INTO episodic_memories
               (memory_id, character_id, chapter_index, scene_index, content,
                importance, emotional_valence, involved_characters)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory_id, self.character_id, memory.chapter_index,
                memory.scene_index, memory.content, memory.importance,
                memory.emotional_valence, json.dumps(memory.involved_characters),
            ),
        )
        await self.conn.commit()

        # V10: Dual-write to Qdrant
        if self._vector_store is not None:
            try:
                await self._vector_store.upsert_episodic(
                    memory_id=memory_id,
                    character_id=self.character_id,
                    content=memory.content,
                    importance=memory.importance,
                    emotional_valence=memory.emotional_valence,
                    chapter_index=memory.chapter_index,
                    scene_index=memory.scene_index,
                )
            except Exception as e:
                logger.warning("Qdrant upsert_episodic failed: %s", e)

        return memory_id

    async def get_recent(self, limit: int = 10) -> list[EpisodicMemory]:
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ?
               ORDER BY chapter_index DESC, scene_index DESC, created_at DESC
               LIMIT ?""",
            (self.character_id, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_by_chapter(self, chapter_index: int) -> list[EpisodicMemory]:
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ? AND chapter_index = ?
               ORDER BY scene_index, created_at""",
            (self.character_id, chapter_index),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_important(self, min_importance: float = 0.7, limit: int = 10) -> list[EpisodicMemory]:
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ? AND importance >= ?
               ORDER BY importance DESC
               LIMIT ?""",
            (self.character_id, min_importance, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_by_era(
        self, chapter_start: int, chapter_end: int,
        min_importance: float = 0.0, limit: int = 10,
    ) -> list[EpisodicMemory]:
        """Get memories within a chapter range (era), optionally filtered by importance."""
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ?
                 AND chapter_index BETWEEN ? AND ?
                 AND importance >= ?
               ORDER BY importance DESC, chapter_index DESC
               LIMIT ?""",
            (self.character_id, chapter_start, chapter_end, min_importance, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    # ---- V10: Heat-aware methods ----

    async def get_hot(self, min_heat: float = 0.5, limit: int = 15) -> list[EpisodicMemory]:
        """Get hot-zone memories (high heat, direct context injection)."""
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ? AND consolidated = 0 AND heat_score >= ?
               ORDER BY heat_score DESC
               LIMIT ?""",
            (self.character_id, min_heat, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_warm(
        self, min_heat: float = 0.1, max_heat: float = 0.5, limit: int = 20,
    ) -> list[EpisodicMemory]:
        """Get warm-zone memories (medium heat, for on-demand retrieval)."""
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ? AND consolidated = 0
                 AND heat_score >= ? AND heat_score < ?
               ORDER BY heat_score DESC
               LIMIT ?""",
            (self.character_id, min_heat, max_heat, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_cold(self, max_heat: float = 0.1, limit: int = 50) -> list[EpisodicMemory]:
        """Get cold-zone memories (low heat, eligible for consolidation)."""
        cursor = await self.conn.execute(
            """SELECT * FROM episodic_memories
               WHERE character_id = ? AND consolidated = 0
                 AND heat_score < ? AND importance < 0.8
               ORDER BY chapter_index ASC
               LIMIT ?""",
            (self.character_id, max_heat, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def update_heat(self, memory_id: str, heat_score: float) -> None:
        """Manually set heat_score for a memory."""
        await self.conn.execute(
            "UPDATE episodic_memories SET heat_score = ? WHERE memory_id = ?",
            (heat_score, memory_id),
        )
        await self.conn.commit()

    async def search_similar(
        self, query: str, top_k: int = 5, min_heat: float = 0.1,
    ) -> list[tuple[EpisodicMemory, float]]:
        """Semantic search over episodic memories via Qdrant.

        Falls back to empty list if Qdrant is unavailable.
        """
        if self._vector_store is None:
            return []
        try:
            from novel_creator.memory.semantic_store import embed_texts
            query_emb = embed_texts([query])[0]
            hits = await self._vector_store.search_episodic(
                character_id=self.character_id,
                query_embedding=query_emb,
                top_k=top_k,
                min_heat=min_heat,
            )
            results = []
            for h in hits:
                mem = EpisodicMemory(
                    memory_id=h["memory_id"],
                    character_id=self.character_id,
                    chapter_index=h["chapter_index"],
                    scene_index=h["scene_index"],
                    content=h["content"],
                    importance=h["importance"],
                    emotional_valence=h["emotional_valence"],
                )
                results.append((mem, h["score"]))
            return results
        except Exception as e:
            logger.warning("Qdrant search_episodic failed: %s", e)
            return []

    def _row_to_memory(self, row: aiosqlite.Row) -> EpisodicMemory:
        return EpisodicMemory(
            memory_id=row["memory_id"],
            character_id=row["character_id"],
            chapter_index=row["chapter_index"],
            scene_index=row["scene_index"],
            content=row["content"],
            importance=row["importance"],
            emotional_valence=row["emotional_valence"],
            involved_characters=json.loads(row["involved_characters"]),
        )
