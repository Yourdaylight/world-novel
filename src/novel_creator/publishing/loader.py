"""Load a finished novel from its per-novel SQLite DB into exportable structures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id


@dataclass
class ChapterBrief:
    """One rendered chapter (scenes already joined)."""

    index: int
    title: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text)


@dataclass
class VolumeBrief:
    """One volume with its 0-based inclusive chapter range."""

    index: int
    title: str
    summary: str
    chapter_start: int
    chapter_end: int


@dataclass
class NovelContent:
    """Everything an exporter / preflight needs, independent of SQLite."""

    novel_id: str
    title: str
    genre: str
    intro: str
    author: str = ""
    volumes: list[VolumeBrief] = field(default_factory=list)
    chapters: list[ChapterBrief] = field(default_factory=list)
    planned_count: int = 0

    @property
    def total_words(self) -> int:
        return sum(c.word_count for c in self.chapters)

    @property
    def chapter_indices(self) -> set[int]:
        return {c.index for c in self.chapters}


def _extract_intro(outline: dict) -> str:
    """Best-effort synopsis: synopsis → premise → theme → proposition text."""
    for key in ("synopsis", "intro", "premise", "theme"):
        value = outline.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def load_novel_content(novel_id: str) -> NovelContent | None:
    """Load a registered novel's outline, volumes and rendered chapters.

    Returns None when the novel is not in the registry. A novel with zero
    rendered chapters still returns a NovelContent (preflight then flags it).
    """
    novel = get_novel_by_id(novel_id)
    if novel is None:
        return None
    if not Path(novel.db_path).exists():
        # 注册表还在但库文件被删：不要让 get_connection 新建空库
        return None

    conn = await get_connection(novel.db_path)
    try:
        cursor = await conn.execute(
            "SELECT outline_json FROM story_outline WHERE id = 1"
        )
        row = await cursor.fetchone()
        outline = json.loads(row["outline_json"]) if row and row["outline_json"] else {}

        cursor = await conn.execute(
            "SELECT volume_index, title, summary, chapter_start, chapter_end "
            "FROM volumes ORDER BY volume_index"
        )
        volumes = [
            VolumeBrief(
                index=r["volume_index"],
                title=r["title"] or f"第{r['volume_index'] + 1}卷",
                summary=r["summary"] or "",
                chapter_start=r["chapter_start"],
                chapter_end=r["chapter_end"],
            )
            for r in await cursor.fetchall()
        ]

        cursor = await conn.execute(
            "SELECT chapter_index, scene_index, title, content "
            "FROM chapter_texts ORDER BY chapter_index, scene_index"
        )
        rows = await cursor.fetchall()
    finally:
        await conn.close()

    title = outline.get("title") or novel.title
    genre = outline.get("genre") or novel.genre or ""
    intro = _extract_intro(outline)
    planned = len(outline.get("chapters") or []) or novel.chapters_total

    grouped: dict[int, dict] = {}
    for r in rows:
        ci = r["chapter_index"]
        if ci not in grouped:
            grouped[ci] = {"title": r["title"] or "", "scenes": []}
        grouped[ci]["scenes"].append(r["content"] or "")

    chapters = [
        ChapterBrief(
            index=ci,
            title=grouped[ci]["title"] or f"第{ci + 1}章",
            text="\n\n".join(s.strip() for s in grouped[ci]["scenes"] if s and s.strip()),
        )
        for ci in sorted(grouped)
    ]

    return NovelContent(
        novel_id=novel_id,
        title=title,
        genre=genre,
        intro=intro,
        volumes=volumes,
        chapters=chapters,
        planned_count=planned,
    )
