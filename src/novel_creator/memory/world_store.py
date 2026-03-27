"""World-view and story-outline persistence."""

from __future__ import annotations

import json

import aiosqlite

from novel_creator.models.story import StoryOutline
from novel_creator.models.world import WorldView


# ------------------------------------------------------------------
# WorldView helpers
# ------------------------------------------------------------------

async def save_world(conn: aiosqlite.Connection, world: WorldView) -> None:
    """Upsert the world-building singleton (id=1)."""
    await conn.execute(
        "INSERT INTO world_building (id, world_json) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET world_json = excluded.world_json",
        (world.model_dump_json(),),
    )
    await conn.commit()


async def load_world(conn: aiosqlite.Connection) -> WorldView | None:
    """Load the world-building singleton, or *None* if not yet created."""
    cursor = await conn.execute("SELECT world_json FROM world_building WHERE id = 1")
    row = await cursor.fetchone()
    if row is None:
        return None
    return WorldView.model_validate_json(row[0] if isinstance(row, tuple) else row["world_json"])


# ------------------------------------------------------------------
# StoryOutline helpers
# ------------------------------------------------------------------

async def save_outline(conn: aiosqlite.Connection, outline: StoryOutline) -> None:
    """Upsert the story-outline singleton (id=1)."""
    await conn.execute(
        "INSERT INTO story_outline (id, outline_json) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET outline_json = excluded.outline_json",
        (outline.model_dump_json(),),
    )
    await conn.commit()


async def load_outline(conn: aiosqlite.Connection) -> StoryOutline | None:
    """Load the story outline singleton, or *None* if not yet created."""
    cursor = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
    row = await cursor.fetchone()
    if row is None:
        return None
    return StoryOutline.model_validate_json(row[0] if isinstance(row, tuple) else row["outline_json"])
