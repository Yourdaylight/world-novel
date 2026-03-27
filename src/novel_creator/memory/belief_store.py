"""Core beliefs CRUD operations."""

from __future__ import annotations

import uuid

import aiosqlite

from novel_creator.models.layered_memory import CoreBelief


class BeliefStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def add(self, belief: CoreBelief) -> str:
        belief_id = belief.belief_id or str(uuid.uuid4())[:8]
        await self.conn.execute(
            """INSERT INTO core_beliefs
               (belief_id, character_id, content, strength, origin_chapter, last_reinforced_chapter)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                belief_id, self.character_id, belief.content,
                belief.strength, belief.origin_chapter, belief.last_reinforced_chapter,
            ),
        )
        await self.conn.commit()
        return belief_id

    async def get_all(self) -> list[CoreBelief]:
        cursor = await self.conn.execute(
            """SELECT * FROM core_beliefs
               WHERE character_id = ?
               ORDER BY strength DESC""",
            (self.character_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_belief(r) for r in rows]

    async def update_strength(self, belief_id: str, new_strength: float, chapter: int) -> None:
        await self.conn.execute(
            """UPDATE core_beliefs
               SET strength = ?, last_reinforced_chapter = ?
               WHERE belief_id = ?""",
            (max(0.0, min(1.0, new_strength)), chapter, belief_id),
        )
        await self.conn.commit()

    async def get_relevant(self, query_keywords: list[str]) -> list[CoreBelief]:
        """Simple keyword match on content."""
        all_beliefs = await self.get_all()
        results = []
        for belief in all_beliefs:
            for kw in query_keywords:
                if kw in belief.content:
                    results.append(belief)
                    break
        return results

    def _row_to_belief(self, row: aiosqlite.Row) -> CoreBelief:
        return CoreBelief(
            belief_id=row["belief_id"],
            character_id=row["character_id"],
            content=row["content"],
            strength=row["strength"],
            origin_chapter=row["origin_chapter"],
            last_reinforced_chapter=row["last_reinforced_chapter"],
        )
