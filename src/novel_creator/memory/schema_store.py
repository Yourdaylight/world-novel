"""Relationship schema (mental model) CRUD operations."""

from __future__ import annotations

import uuid

import aiosqlite

from novel_creator.models.layered_memory import RelationshipSchema


class SchemaStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def upsert(self, schema: RelationshipSchema) -> str:
        schema_id = schema.schema_id or str(uuid.uuid4())[:8]
        await self.conn.execute(
            """INSERT INTO relationship_schemas
               (schema_id, character_id, target_id, mental_model, confidence, last_updated_chapter)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(character_id, target_id)
               DO UPDATE SET
                   mental_model = excluded.mental_model,
                   confidence = excluded.confidence,
                   last_updated_chapter = excluded.last_updated_chapter""",
            (
                schema_id, self.character_id, schema.target_id,
                schema.mental_model, schema.confidence, schema.last_updated_chapter,
            ),
        )
        await self.conn.commit()
        return schema_id

    async def get_for_target(self, target_id: str) -> RelationshipSchema | None:
        cursor = await self.conn.execute(
            """SELECT * FROM relationship_schemas
               WHERE character_id = ? AND target_id = ?""",
            (self.character_id, target_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_schema(row)

    async def get_all(self) -> list[RelationshipSchema]:
        cursor = await self.conn.execute(
            """SELECT * FROM relationship_schemas
               WHERE character_id = ?
               ORDER BY confidence DESC""",
            (self.character_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_schema(r) for r in rows]

    def _row_to_schema(self, row: aiosqlite.Row) -> RelationshipSchema:
        return RelationshipSchema(
            schema_id=row["schema_id"],
            character_id=row["character_id"],
            target_id=row["target_id"],
            mental_model=row["mental_model"],
            confidence=row["confidence"],
            last_updated_chapter=row["last_updated_chapter"],
        )
