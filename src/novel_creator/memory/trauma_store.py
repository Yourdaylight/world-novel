"""Trauma/anchor memory CRUD operations."""

from __future__ import annotations

import json
import uuid

import aiosqlite

from novel_creator.models.layered_memory import TraumaMemory


class TraumaStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def add(self, trauma: TraumaMemory) -> str:
        trauma_id = trauma.trauma_id or str(uuid.uuid4())[:8]
        await self.conn.execute(
            """INSERT INTO trauma_memories
               (trauma_id, character_id, content, trauma_type, trigger_keywords,
                emotional_impact, origin_chapter, importance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trauma_id, self.character_id, trauma.content,
                trauma.trauma_type, json.dumps(trauma.trigger_keywords),
                json.dumps(trauma.emotional_impact),
                trauma.origin_chapter, trauma.importance,
            ),
        )
        await self.conn.commit()
        return trauma_id

    async def get_all(self) -> list[TraumaMemory]:
        cursor = await self.conn.execute(
            """SELECT * FROM trauma_memories
               WHERE character_id = ?
               ORDER BY importance DESC""",
            (self.character_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_trauma(r) for r in rows]

    async def get_triggered_by(self, keywords: list[str]) -> list[TraumaMemory]:
        """Check if any keywords overlap with trigger_keywords."""
        all_traumas = await self.get_all()
        results = []
        keyword_set = set(keywords)
        for trauma in all_traumas:
            if keyword_set & set(trauma.trigger_keywords):
                results.append(trauma)
        return results

    def _row_to_trauma(self, row: aiosqlite.Row) -> TraumaMemory:
        return TraumaMemory(
            trauma_id=row["trauma_id"],
            character_id=row["character_id"],
            content=row["content"],
            trauma_type=row["trauma_type"],
            trigger_keywords=json.loads(row["trigger_keywords"]),
            emotional_impact=json.loads(row["emotional_impact"]),
            origin_chapter=row["origin_chapter"],
            importance=row["importance"],
        )
