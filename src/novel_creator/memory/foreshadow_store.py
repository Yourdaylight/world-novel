"""Foreshadow and plot-thread persistence."""

from __future__ import annotations

import json

import aiosqlite

from novel_creator.models.foreshadow import Foreshadow, ForeshadowStatus, PlotThread


# ------------------------------------------------------------------
# Foreshadow CRUD
# ------------------------------------------------------------------

async def save_foreshadow(conn: aiosqlite.Connection, fs: Foreshadow) -> None:
    """Insert or replace a foreshadow record."""
    await conn.execute(
        """INSERT INTO foreshadows
           (foreshadow_id, description, hint_text, planted_chapter,
            expected_payoff_chapter, actual_payoff_chapter, status,
            importance, related_characters, related_plot_thread)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(foreshadow_id) DO UPDATE SET
               description=excluded.description, hint_text=excluded.hint_text,
               planted_chapter=excluded.planted_chapter,
               expected_payoff_chapter=excluded.expected_payoff_chapter,
               actual_payoff_chapter=excluded.actual_payoff_chapter,
               status=excluded.status, importance=excluded.importance,
               related_characters=excluded.related_characters,
               related_plot_thread=excluded.related_plot_thread""",
        (
            fs.foreshadow_id, fs.description, fs.hint_text,
            fs.planted_chapter, fs.expected_payoff_chapter,
            fs.actual_payoff_chapter, fs.status.value,
            fs.importance, json.dumps(fs.related_characters, ensure_ascii=False),
            fs.related_plot_thread,
        ),
    )
    await conn.commit()


async def get_all_foreshadows(conn: aiosqlite.Connection) -> list[Foreshadow]:
    """Return every foreshadow in the database."""
    cursor = await conn.execute("SELECT * FROM foreshadows ORDER BY planted_chapter")
    rows = await cursor.fetchall()
    return [_row_to_foreshadow(r) for r in rows]


async def get_pending_for_chapter(
    conn: aiosqlite.Connection, chapter: int,
) -> tuple[list[Foreshadow], list[Foreshadow]]:
    """Return (to_plant, to_payoff) foreshadows relevant to *chapter*."""
    all_fs = await get_all_foreshadows(conn)
    to_plant = [f for f in all_fs if f.planted_chapter == chapter and f.status == ForeshadowStatus.PLANTED]
    to_payoff = [
        f for f in all_fs
        if f.expected_payoff_chapter == chapter
        and f.status in (ForeshadowStatus.PLANTED, ForeshadowStatus.REINFORCED)
    ]
    return to_plant, to_payoff


async def get_dangling(conn: aiosqlite.Connection, current_chapter: int) -> list[Foreshadow]:
    """Return foreshadows past their expected payoff chapter that are still open."""
    cursor = await conn.execute(
        """SELECT * FROM foreshadows
           WHERE expected_payoff_chapter < ?
             AND status IN ('planted', 'reinforced')""",
        (current_chapter,),
    )
    rows = await cursor.fetchall()
    return [_row_to_foreshadow(r) for r in rows]


async def mark_payoff(conn: aiosqlite.Connection, foreshadow_id: str, chapter: int) -> None:
    """Mark a foreshadow as paid off in *chapter*."""
    await conn.execute(
        "UPDATE foreshadows SET status = 'payoff', actual_payoff_chapter = ? WHERE foreshadow_id = ?",
        (chapter, foreshadow_id),
    )
    await conn.commit()


async def mark_dangling(conn: aiosqlite.Connection, foreshadow_id: str) -> None:
    """Mark a foreshadow as dangling (overdue)."""
    await conn.execute(
        "UPDATE foreshadows SET status = 'dangling' WHERE foreshadow_id = ?",
        (foreshadow_id,),
    )
    await conn.commit()


# ------------------------------------------------------------------
# PlotThread CRUD
# ------------------------------------------------------------------

async def save_plot_thread(conn: aiosqlite.Connection, pt: PlotThread) -> None:
    """Insert or replace a plot thread."""
    await conn.execute(
        """INSERT INTO plot_threads
           (thread_id, name, description, status, start_chapter,
            key_characters, foreshadow_ids, chapter_progress)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(thread_id) DO UPDATE SET
               name=excluded.name, description=excluded.description,
               status=excluded.status, start_chapter=excluded.start_chapter,
               key_characters=excluded.key_characters,
               foreshadow_ids=excluded.foreshadow_ids,
               chapter_progress=excluded.chapter_progress""",
        (
            pt.thread_id, pt.name, pt.description, pt.status,
            pt.start_chapter, json.dumps(pt.key_characters, ensure_ascii=False),
            json.dumps(pt.foreshadow_ids, ensure_ascii=False),
            json.dumps(pt.chapter_progress, ensure_ascii=False),
        ),
    )
    await conn.commit()


async def get_all_plot_threads(conn: aiosqlite.Connection) -> list[PlotThread]:
    """Return all plot threads."""
    cursor = await conn.execute("SELECT * FROM plot_threads ORDER BY start_chapter")
    rows = await cursor.fetchall()
    return [_row_to_plot_thread(r) for r in rows]


# ------------------------------------------------------------------
# Row converters
# ------------------------------------------------------------------

def _row_to_foreshadow(row) -> Foreshadow:
    return Foreshadow(
        foreshadow_id=row["foreshadow_id"],
        description=row["description"],
        hint_text=row["hint_text"] or "",
        planted_chapter=row["planted_chapter"],
        expected_payoff_chapter=row["expected_payoff_chapter"],
        actual_payoff_chapter=row["actual_payoff_chapter"],
        status=ForeshadowStatus(row["status"]),
        importance=row["importance"] or "minor",
        related_characters=json.loads(row["related_characters"] or "[]"),
        related_plot_thread=row["related_plot_thread"] or "",
    )


def _row_to_plot_thread(row) -> PlotThread:
    return PlotThread(
        thread_id=row["thread_id"],
        name=row["name"],
        description=row["description"] or "",
        status=row["status"] or "active",
        start_chapter=row["start_chapter"],
        key_characters=json.loads(row["key_characters"] or "[]"),
        foreshadow_ids=json.loads(row["foreshadow_ids"] or "[]"),
        chapter_progress=json.loads(row["chapter_progress"] or "{}"),
    )
