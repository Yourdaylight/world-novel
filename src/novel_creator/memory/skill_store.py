"""CharacterSkill CRUD — user-managed skills for character agents.

Stored in the `character_skills` table, one row per skill per character.
DB is the source of truth; AgentFileSync exports them to
`agents/{character_id}/skills/{skill_id}.md` for human viewing/editing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import aiosqlite

from novel_creator.models.skill import CharacterSkill


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SkillStore:
    """CRUD for character skills, isolated by character_id."""

    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id

    async def upsert(self, skill: CharacterSkill) -> str:
        skill_id = skill.skill_id or f"sk_{uuid.uuid4().hex[:8]}"
        await self.conn.execute(
            """INSERT INTO character_skills
               (skill_id, character_id, name, category, description,
                trigger_conditions, level, direction, enabled, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(skill_id, character_id)
               DO UPDATE SET
                   name = excluded.name,
                   category = excluded.category,
                   description = excluded.description,
                   trigger_conditions = excluded.trigger_conditions,
                   level = excluded.level,
                   direction = excluded.direction,
                   enabled = excluded.enabled,
                   priority = excluded.priority""",
            (
                skill_id, self.character_id, skill.name, skill.category,
                skill.description, skill.trigger_conditions, skill.level,
                skill.direction, 1 if skill.enabled else 0, skill.priority,
                skill.created_at or _now(),
            ),
        )
        await self.conn.commit()
        return skill_id

    async def get(self, skill_id: str) -> CharacterSkill | None:
        cursor = await self.conn.execute(
            """SELECT * FROM character_skills
               WHERE skill_id = ? AND character_id = ?""",
            (skill_id, self.character_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_skill(row)

    async def get_all(self, enabled_only: bool = False) -> list[CharacterSkill]:
        sql = """SELECT * FROM character_skills WHERE character_id = ?"""
        params: list = [self.character_id]
        if enabled_only:
            sql += " AND enabled = 1"
        sql += " ORDER BY priority DESC, created_at ASC"
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [self._row_to_skill(r) for r in rows]

    async def delete(self, skill_id: str) -> bool:
        cursor = await self.conn.execute(
            """DELETE FROM character_skills
               WHERE skill_id = ? AND character_id = ?""",
            (skill_id, self.character_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def set_enabled(self, skill_id: str, enabled: bool) -> bool:
        cursor = await self.conn.execute(
            """UPDATE character_skills SET enabled = ?
               WHERE skill_id = ? AND character_id = ?""",
            (1 if enabled else 0, skill_id, self.character_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def set_priority(self, skill_id: str, priority: int) -> bool:
        cursor = await self.conn.execute(
            """UPDATE character_skills SET priority = ?
               WHERE skill_id = ? AND character_id = ?""",
            (priority, skill_id, self.character_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    def _row_to_skill(self, row: aiosqlite.Row) -> CharacterSkill:
        return CharacterSkill(
            character_id=row["character_id"],
            skill_id=row["skill_id"],
            name=row["name"],
            category=row["category"],
            description=row["description"] or "",
            trigger_conditions=row["trigger_conditions"] or "",
            level=row["level"] or 0.0,
            direction=row["direction"] or "",
            enabled=bool(row["enabled"]),
            priority=row["priority"] or 0,
            created_at=row["created_at"] or "",
        )
