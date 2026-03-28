"""Inner agenda store — cross-scene psychological undercurrents.

Tracks a character's hidden intentions and vigilance points that persist
across scenes, filling the gap between discrete emotion floats and
narrative-level psychological continuity.
"""

from __future__ import annotations

import aiosqlite


class InnerAgendaStore:
    """Per-character inner agenda CRUD (singleton row per character)."""

    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def get(self) -> tuple[str, str]:
        """Return (agenda, vigilance) for this character.

        Returns empty strings if no agenda has been recorded yet.
        """
        cursor = await self.conn.execute(
            "SELECT agenda, vigilance FROM character_inner_agenda WHERE character_id = ?",
            (self.character_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return ("", "")
        return (row["agenda"], row["vigilance"])

    async def update(
        self,
        agenda: str,
        vigilance: str,
        chapter: int = 0,
        scene: int = 0,
    ) -> None:
        """Upsert the character's inner agenda."""
        await self.conn.execute(
            """INSERT INTO character_inner_agenda
               (character_id, agenda, vigilance, chapter_updated, scene_updated)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(character_id) DO UPDATE SET
                   agenda = excluded.agenda,
                   vigilance = excluded.vigilance,
                   chapter_updated = excluded.chapter_updated,
                   scene_updated = excluded.scene_updated""",
            (self.character_id, agenda, vigilance, chapter, scene),
        )
        await self.conn.commit()
