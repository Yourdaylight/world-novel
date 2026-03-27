"""Episodic memory CRUD operations."""

from __future__ import annotations

import json
import uuid

import aiosqlite

from novel_creator.models.memory import EpisodicMemory


class EpisodicStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

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
