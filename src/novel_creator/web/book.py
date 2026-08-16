"""Shared compiled-book loader.

A single source of truth for reading a finished novel out of its per-novel
SQLite database. Used by both the publish/export pipeline (requirement A) and
the public share reader (requirement B) so that chapter ordering, volume
grouping and word counting never drift between features.

Everything here is read-only and raises ``BookNotFound`` when the novel is not
registered or has no rendered chapters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id


class BookNotFound(Exception):
    """Raised when a novel id is unknown or has no rendered chapters."""


@dataclass
class Chapter:
    chapter_index: int
    title: str
    text: str
    word_count: int = 0
    summary: str = ""
    scenes: list[str] = field(default_factory=list)


@dataclass
class Volume:
    volume_index: int
    title: str
    summary: str
    theme: str
    chapter_start: int
    chapter_end: int
    arc_goal: str = ""


@dataclass
class Book:
    novel_id: str
    title: str
    genre: str
    theme: str
    premise: str
    setting: str
    central_conflict: str
    resolution_direction: str
    chapters: list[Chapter]
    volumes: list[Volume]

    @property
    def total_words(self) -> int:
        return sum(c.word_count for c in self.chapters)

    @property
    def intro(self) -> str:
        """Auto-generated 简介 (synopsis) from outline fields when present."""
        parts = [p for p in (self.premise, self.central_conflict, self.setting) if p]
        return "\n".join(parts)


async def load_book(novel_id: str) -> Book:
    """Load a compiled book for ``novel_id``.

    Raises ``BookNotFound`` if the novel is not in the registry or has no
    rendered ``chapter_texts`` rows.
    """
    novel = get_novel_by_id(novel_id)
    if novel is None:
        raise BookNotFound(f"未找到小说: {novel_id}")

    conn = await get_connection(novel.db_path)
    try:
        cursor = await conn.execute(
            "SELECT outline_json FROM story_outline WHERE id = 1"
        )
        row = await cursor.fetchone()
        outline = json.loads(row["outline_json"]) if row else {}

        cursor = await conn.execute(
            "SELECT chapter_index, scene_index, title, content, summary "
            "FROM chapter_texts ORDER BY chapter_index, scene_index"
        )
        rows = await cursor.fetchall()

        cursor = await conn.execute(
            "SELECT volume_index, title, summary, theme, chapter_start, "
            "chapter_end, arc_goal FROM volumes ORDER BY volume_index"
        )
        volume_rows = await cursor.fetchall()
    finally:
        await conn.close()

    if not rows:
        raise BookNotFound(f"小说尚无成文章节: {novel_id}")

    grouped: dict[int, Chapter] = {}
    for r in rows:
        ci = r["chapter_index"]
        ch = grouped.get(ci)
        if ch is None:
            ch = Chapter(
                chapter_index=ci,
                title=r["title"] or "",
                text="",
                summary=r["summary"] or "",
            )
            grouped[ci] = ch
        ch.scenes.append(r["content"] or "")

    chapters: list[Chapter] = []
    for ci in sorted(grouped):
        ch = grouped[ci]
        ch.text = "\n\n".join(s for s in ch.scenes if s).strip()
        ch.word_count = len(ch.text)
        chapters.append(ch)

    volumes = [
        Volume(
            volume_index=v["volume_index"],
            title=v["title"] or "",
            summary=v["summary"] or "",
            theme=v["theme"] or "",
            chapter_start=v["chapter_start"],
            chapter_end=v["chapter_end"],
            arc_goal=v["arc_goal"] or "",
        )
        for v in volume_rows
    ]

    return Book(
        novel_id=novel_id,
        title=outline.get("title") or novel.title,
        genre=outline.get("genre") or novel.genre,
        theme=outline.get("theme", ""),
        premise=outline.get("premise", ""),
        setting=outline.get("setting", ""),
        central_conflict=outline.get("central_conflict", ""),
        resolution_direction=outline.get("resolution_direction", ""),
        chapters=chapters,
        volumes=volumes,
    )
