"""Timeline and God-decision persistence — CRUD for eras, events, decisions."""

from __future__ import annotations

import json
import uuid

import aiosqlite

from novel_creator.models.god import GodDecision
from novel_creator.models.timeline import StoryEra, StoryTimeline, TimelineEvent


# ------------------------------------------------------------------
# Era CRUD
# ------------------------------------------------------------------

async def save_era(conn: aiosqlite.Connection, era: StoryEra) -> None:
    """Insert or replace a story era."""
    await conn.execute(
        """INSERT INTO story_eras
           (era_id, name, description, "order", story_time_start, story_time_end,
            chapter_start, chapter_end, volume_index)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(era_id) DO UPDATE SET
               name=excluded.name, description=excluded.description,
               "order"=excluded."order", story_time_start=excluded.story_time_start,
               story_time_end=excluded.story_time_end,
               chapter_start=excluded.chapter_start, chapter_end=excluded.chapter_end,
               volume_index=excluded.volume_index""",
        (
            era.era_id, era.name, era.description, era.order,
            era.story_time_start, era.story_time_end,
            era.chapter_start, era.chapter_end, era.volume_index,
        ),
    )
    await conn.commit()


async def get_all_eras(conn: aiosqlite.Connection) -> list[StoryEra]:
    """Return all eras ordered by their sequence."""
    cursor = await conn.execute('SELECT * FROM story_eras ORDER BY "order"')
    rows = await cursor.fetchall()
    return [_row_to_era(r) for r in rows]


async def get_current_era(conn: aiosqlite.Connection, chapter_index: int) -> StoryEra | None:
    """Return the era covering the given chapter."""
    cursor = await conn.execute(
        "SELECT * FROM story_eras WHERE chapter_start <= ? AND chapter_end >= ? LIMIT 1",
        (chapter_index, chapter_index),
    )
    row = await cursor.fetchone()
    return _row_to_era(row) if row else None


# ------------------------------------------------------------------
# Event CRUD
# ------------------------------------------------------------------

async def save_event(conn: aiosqlite.Connection, event: TimelineEvent) -> None:
    """Insert or replace a timeline event."""
    await conn.execute(
        """INSERT INTO timeline_events
           (event_id, era_id, chapter_index, story_time, event_type, title,
            description, affected_characters, affected_locations, source, importance)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(event_id) DO UPDATE SET
               era_id=excluded.era_id, chapter_index=excluded.chapter_index,
               story_time=excluded.story_time, event_type=excluded.event_type,
               title=excluded.title, description=excluded.description,
               affected_characters=excluded.affected_characters,
               affected_locations=excluded.affected_locations,
               source=excluded.source, importance=excluded.importance""",
        (
            event.event_id, event.era_id, event.chapter_index,
            event.story_time, event.event_type, event.title, event.description,
            json.dumps(event.affected_characters, ensure_ascii=False),
            json.dumps(event.affected_locations, ensure_ascii=False),
            event.source, event.importance,
        ),
    )
    await conn.commit()


async def get_events_for_chapter(
    conn: aiosqlite.Connection, chapter_index: int,
) -> list[TimelineEvent]:
    """Return all events for a given chapter."""
    cursor = await conn.execute(
        "SELECT * FROM timeline_events WHERE chapter_index = ? ORDER BY importance DESC",
        (chapter_index,),
    )
    rows = await cursor.fetchall()
    return [_row_to_event(r) for r in rows]


async def get_all_events(conn: aiosqlite.Connection) -> list[TimelineEvent]:
    """Return all timeline events."""
    cursor = await conn.execute(
        "SELECT * FROM timeline_events ORDER BY chapter_index, importance DESC"
    )
    rows = await cursor.fetchall()
    return [_row_to_event(r) for r in rows]


# ------------------------------------------------------------------
# God decision CRUD
# ------------------------------------------------------------------

async def save_god_decision(conn: aiosqlite.Connection, decision: GodDecision) -> None:
    """Persist a God Agent decision."""
    await conn.execute(
        """INSERT INTO god_decisions (decision_id, chapter_index, decision_json)
           VALUES (?, ?, ?)
           ON CONFLICT(decision_id) DO UPDATE SET
               chapter_index=excluded.chapter_index, decision_json=excluded.decision_json""",
        (decision.decision_id, decision.chapter_index, decision.model_dump_json()),
    )
    await conn.commit()


async def get_god_decisions(conn: aiosqlite.Connection) -> list[GodDecision]:
    """Return all God Agent decisions."""
    cursor = await conn.execute(
        "SELECT decision_json FROM god_decisions ORDER BY chapter_index"
    )
    rows = await cursor.fetchall()
    return [GodDecision.model_validate_json(r["decision_json"]) for r in rows]


async def get_god_decision_for_chapter(
    conn: aiosqlite.Connection, chapter_index: int,
) -> GodDecision | None:
    """Return the God decision for a specific chapter."""
    cursor = await conn.execute(
        "SELECT decision_json FROM god_decisions WHERE chapter_index = ?",
        (chapter_index,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return GodDecision.model_validate_json(row["decision_json"])


# ------------------------------------------------------------------
# Composite: load full timeline
# ------------------------------------------------------------------

async def load_timeline(conn: aiosqlite.Connection) -> StoryTimeline:
    """Load the full timeline from DB."""
    eras = await get_all_eras(conn)
    events = await get_all_events(conn)
    return StoryTimeline(eras=eras, events=events)


# ------------------------------------------------------------------
# Row converters
# ------------------------------------------------------------------

def _row_to_era(row) -> StoryEra:
    return StoryEra(
        era_id=row["era_id"],
        name=row["name"],
        description=row["description"] or "",
        order=row["order"],
        story_time_start=row["story_time_start"] or "",
        story_time_end=row["story_time_end"] or "",
        chapter_start=row["chapter_start"],
        chapter_end=row["chapter_end"],
        volume_index=row["volume_index"] or 0,
    )


def _row_to_event(row) -> TimelineEvent:
    return TimelineEvent(
        event_id=row["event_id"],
        era_id=row["era_id"],
        chapter_index=row["chapter_index"],
        story_time=row["story_time"] or "",
        event_type=row["event_type"],
        title=row["title"],
        description=row["description"] or "",
        affected_characters=json.loads(row["affected_characters"] or "[]"),
        affected_locations=json.loads(row["affected_locations"] or "[]"),
        source=row["source"] or "director",
        importance=row["importance"] or 0.5,
    )
