"""Emotional state tracking store."""

from __future__ import annotations

import aiosqlite

from novel_creator.models.memory import EmotionalState


class EmotionalStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def save_state(self, state: EmotionalState) -> None:
        await self.conn.execute(
            """INSERT INTO emotional_states
               (character_id, chapter_index, scene_index,
                happiness, anger, fear, sadness, trust, surprise)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.character_id, state.chapter_index, state.scene_index,
                state.happiness, state.anger, state.fear,
                state.sadness, state.trust, state.surprise,
            ),
        )
        await self.conn.commit()

    async def get_latest(self) -> EmotionalState:
        cursor = await self.conn.execute(
            """SELECT * FROM emotional_states
               WHERE character_id = ?
               ORDER BY chapter_index DESC, scene_index DESC, id DESC
               LIMIT 1""",
            (self.character_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return EmotionalState(character_id=self.character_id)
        return EmotionalState(
            character_id=row["character_id"],
            happiness=row["happiness"],
            anger=row["anger"],
            fear=row["fear"],
            sadness=row["sadness"],
            trust=row["trust"],
            surprise=row["surprise"],
            chapter_index=row["chapter_index"],
            scene_index=row["scene_index"],
        )

    async def get_history(self, limit: int = 20) -> list[EmotionalState]:
        cursor = await self.conn.execute(
            """SELECT * FROM emotional_states
               WHERE character_id = ?
               ORDER BY chapter_index DESC, scene_index DESC, id DESC
               LIMIT ?""",
            (self.character_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            EmotionalState(
                character_id=r["character_id"],
                happiness=r["happiness"], anger=r["anger"],
                fear=r["fear"], sadness=r["sadness"],
                trust=r["trust"], surprise=r["surprise"],
                chapter_index=r["chapter_index"], scene_index=r["scene_index"],
            )
            for r in rows
        ]
