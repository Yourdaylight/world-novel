"""Relationship CRUD store.

V10: Optionally syncs to Neo4j graph_store on upsert (fire-and-forget).
"""

from __future__ import annotations

import asyncio
import logging

import aiosqlite

from novel_creator.models.relationship import Relationship

logger = logging.getLogger("novel_creator.memory.graph")


class RelationshipStore:
    def __init__(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        *,
        graph_store=None,
    ):
        self.conn = conn
        self.character_id = character_id
        self._graph_store = graph_store

    async def upsert(
        self,
        rel: Relationship,
        *,
        chapter_index: int = -1,
        change_reason: str = "",
    ) -> None:
        await self.conn.execute(
            """INSERT INTO relationships (source_id, target_id, relationship_type, trust, affection, description)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_id, target_id) DO UPDATE SET
                 relationship_type = excluded.relationship_type,
                 trust = excluded.trust,
                 affection = excluded.affection,
                 description = excluded.description,
                 updated_at = CURRENT_TIMESTAMP""",
            (rel.source_id, rel.target_id, rel.relationship_type,
             rel.trust, rel.affection, rel.description),
        )
        # Write history snapshot
        if chapter_index >= 0:
            try:
                await self.conn.execute(
                    """INSERT INTO relationship_history
                       (source_id, target_id, relationship_type, trust, affection, description, chapter_index, change_reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rel.source_id, rel.target_id, rel.relationship_type,
                     rel.trust, rel.affection, rel.description,
                     chapter_index, change_reason),
                )
            except Exception:
                pass
        await self.conn.commit()

        # V10: Async sync to Neo4j (fire-and-forget)
        if self._graph_store is not None:
            try:
                asyncio.create_task(self._sync_neo4j(rel, chapter_index))
            except Exception as e:
                logger.warning("Neo4j sync schedule failed: %s", e)

    async def _sync_neo4j(self, rel: Relationship, chapter: int) -> None:
        """Background task to sync relationship to Neo4j."""
        try:
            await self._graph_store.sync_relationship(
                source_id=rel.source_id,
                target_id=rel.target_id,
                relationship_type=rel.relationship_type,
                trust=rel.trust,
                affection=rel.affection,
                description=rel.description,
                chapter=chapter,
            )
        except Exception as e:
            logger.warning("Neo4j sync_relationship failed: %s", e)

    async def get_with(self, target_id: str) -> Relationship | None:
        cursor = await self.conn.execute(
            """SELECT * FROM relationships
               WHERE source_id = ? AND target_id = ?""",
            (self.character_id, target_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Relationship(
            source_id=row["source_id"], target_id=row["target_id"],
            relationship_type=row["relationship_type"],
            trust=row["trust"], affection=row["affection"],
            description=row["description"],
        )

    async def get_all(self) -> list[Relationship]:
        cursor = await self.conn.execute(
            """SELECT * FROM relationships
               WHERE source_id = ? OR target_id = ?""",
            (self.character_id, self.character_id),
        )
        rows = await cursor.fetchall()
        return [
            Relationship(
                source_id=r["source_id"], target_id=r["target_id"],
                relationship_type=r["relationship_type"],
                trust=r["trust"], affection=r["affection"],
                description=r["description"],
            )
            for r in rows
        ]
