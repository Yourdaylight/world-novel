"""Book assembly service — load a finished novel from its per-novel SQLite DB.

Shared by the publish pipeline (requirement A) and the public share reader
(requirement B). Both features need the same view of a book: ordered chapters
with merged scene texts, volume structure, and metadata from the story
outline.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import NovelInfo, get_novel_by_id

_WS_RE = re.compile(r"\s+")


def count_words(text: str) -> int:
    """中文网文字数口径：去除空白后的字符数。"""
    return len(_WS_RE.sub("", text or ""))


@dataclass
class Chapter:
    index: int  # 0-based, matches chapter_texts.chapter_index
    title: str
    text: str
    words: int

    @property
    def display_title(self) -> str:
        return f"第{self.index + 1}章 {self.title}".strip() if self.title else f"第{self.index + 1}章"


@dataclass
class Volume:
    index: int
    title: str
    summary: str
    chapter_start: int
    chapter_end: int


@dataclass
class Book:
    novel_id: str
    title: str
    genre: str
    theme: str
    premise: str
    intro: str
    volumes: list[Volume] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    planned_total: int = 0

    @property
    def total_words(self) -> int:
        return sum(c.words for c in self.chapters)


def build_intro(outline: dict) -> str:
    """模板生成简介：优先 premise/central_conflict，兜底 propositions。"""
    parts: list[str] = []
    for key in ("premise", "central_conflict", "setting"):
        val = (outline.get(key) or "").strip()
        if val and val not in parts:
            parts.append(val)
    intro = "\n".join(parts)
    if intro:
        return intro[:600]
    return ""


# Short TTL cache for assembled books. Public reader traffic re-loads the
# whole book on every chapter/TOC request; invalidating on novel.db mtime
# keeps content fresh within ~15s while cutting repeated full scans.
_BOOK_CACHE: dict[str, tuple[float, float, "Book"]] = {}
_CACHE_TTL = 15.0


async def load_book(novel: NovelInfo) -> Book:
    """Load and assemble a full book from the novel's SQLite database.

    Chapter scenes are merged in (chapter_index, scene_index) order — same
    rule the existing /novel-full export uses.
    """
    try:
        mtime = os.path.getmtime(novel.db_path)
    except OSError:
        mtime = 0.0
    cached = _BOOK_CACHE.get(novel.db_path)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL and cached[1] == mtime:
        return cached[2]
    if len(_BOOK_CACHE) > 128:
        _BOOK_CACHE.clear()

    conn = await get_connection(novel.db_path)
    try:
        cursor = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row = await cursor.fetchone()
        outline = json.loads(row["outline_json"]) if row else {}

        cursor = await conn.execute(
            "SELECT volume_index, title, summary, chapter_start, chapter_end "
            "FROM volumes ORDER BY volume_index"
        )
        volumes = [
            Volume(
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

    title = (outline.get("title") or novel.title or "未命名小说").strip()
    genre = (outline.get("genre") or novel.genre or "").strip()

    grouped: dict[int, dict] = {}
    for r in rows:
        ci = r["chapter_index"]
        bucket = grouped.setdefault(ci, {"title": r["title"] or "", "scenes": []})
        bucket["scenes"].append(r["content"] or "")
        if not bucket["title"] and r["title"]:
            bucket["title"] = r["title"]

    # Outline supplies planned chapter titles (and count) even when a chapter
    # body is missing — preflight needs that to detect broken/missing chapters.
    planned: dict[int, str] = {}
    for ch in outline.get("chapters", []) or []:
        try:
            idx = max(0, int(ch.get("chapter_index", len(planned))))
        except (TypeError, ValueError):
            idx = len(planned)
        planned[idx] = (ch.get("title") or "").strip()

    chapters: list[Chapter] = []
    for ci in sorted(set(grouped) | set(planned)):
        bucket = grouped.get(ci)
        text = "\n\n".join(s for s in bucket["scenes"] if s) if bucket else ""
        title_ch = (bucket["title"] if bucket else "") or planned.get(ci, "")
        chapters.append(Chapter(index=ci, title=title_ch, text=text, words=count_words(text)))

    planned_total = len(planned)
    intro = build_intro(outline)
    if not intro:
        intro = (novel.propositions.get("what_is") or "").strip() if novel.propositions else ""

    book = Book(
        novel_id=novel.novel_id,
        title=title,
        genre=genre,
        theme=(outline.get("theme") or "").strip(),
        premise=(outline.get("premise") or "").strip(),
        intro=intro,
        volumes=volumes,
        chapters=chapters,
        planned_total=planned_total,
    )
    _BOOK_CACHE[novel.db_path] = (now, mtime, book)
    return book


async def load_book_by_id(novel_id: str) -> Book | None:
    novel = get_novel_by_id(novel_id)
    if novel is None:
        return None
    return await load_book(novel)
