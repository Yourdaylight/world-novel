"""Reflection log CRUD operations."""

from __future__ import annotations

import uuid

import aiosqlite

from novel_creator.models.layered_memory import ReflectionLog


class ReflectionStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def log_reflection(self, log: ReflectionLog) -> str:
        reflection_id = log.reflection_id or str(uuid.uuid4())[:8]
        await self.conn.execute(
            """INSERT INTO reflection_logs
               (reflection_id, character_id, chapter_index, beliefs_updated,
                schemas_updated, traumas_identified, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                reflection_id, self.character_id, log.chapter_index,
                log.beliefs_updated, log.schemas_updated,
                log.traumas_identified, log.summary,
            ),
        )
        await self.conn.commit()
        return reflection_id

    async def get_last_reflection(self) -> ReflectionLog | None:
        cursor = await self.conn.execute(
            """SELECT * FROM reflection_logs
               WHERE character_id = ?
               ORDER BY chapter_index DESC, created_at DESC
               LIMIT 1""",
            (self.character_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_log(row)

    async def should_reflect(self, current_chapter: int, interval: int = 2) -> bool:
        """True if no reflection in last `interval` chapters."""
        last = await self.get_last_reflection()
        if last is None:
            return True
        return (current_chapter - last.chapter_index) >= interval

    def _row_to_log(self, row: aiosqlite.Row) -> ReflectionLog:
        return ReflectionLog(
            reflection_id=row["reflection_id"],
            character_id=row["character_id"],
            chapter_index=row["chapter_index"],
            beliefs_updated=row["beliefs_updated"],
            schemas_updated=row["schemas_updated"],
            traumas_identified=row["traumas_identified"],
            summary=row["summary"],
        )
