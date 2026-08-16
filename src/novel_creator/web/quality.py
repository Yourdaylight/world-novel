"""Pre-export quality gate (requirement A-1).

Given a compiled :class:`~novel_creator.web.book.Book`, return a structured
verdict. ``errors`` block export (empty chapters / gaps / no content);
``warnings`` do not (over-long chapters, sensitive-word hits, missing intro).
"""

from __future__ import annotations

from .book import Book
from .platforms import PLATFORMS
from .sensitive import scan_text


def run_preflight(book: Book, platform: str = "fanqie") -> dict:
    profile = PLATFORMS.get(platform)
    lo, hi = profile.chapter_words_recommended if profile else (1500, 3000)

    errors: list[dict] = []
    warnings: list[dict] = []

    if not book.chapters:
        errors.append({"code": "no_chapters", "message": "小说没有任何成文章节，无法发布"})

    present = sorted(c.chapter_index for c in book.chapters)
    missing: list[int] = []
    if present:
        expected = set(range(present[0], present[-1] + 1))
        missing = sorted(expected - set(present))
        if missing:
            errors.append({
                "code": "gap",
                "message": f"章节不连续，疑似断章：缺失序号 {missing[:20]}（0-based）",
                "indices": missing,
            })

    empty = [c.chapter_index for c in book.chapters if c.word_count < 20]
    if empty:
        errors.append({
            "code": "empty_chapter",
            "message": f"存在空章/过短章节（<20字）：{[i + 1 for i in empty][:20]}",
            "indices": empty,
        })

    per_chapter = [
        {"chapter_index": c.chapter_index, "title": c.title, "word_count": c.word_count}
        for c in book.chapters
    ]
    long_chapters = [c.chapter_index for c in book.chapters if c.word_count > hi]
    short_chapters = [
        c.chapter_index for c in book.chapters if 20 <= c.word_count < lo
    ]
    if long_chapters:
        warnings.append({
            "code": "long_chapter",
            "message": f"{len(long_chapters)} 章超过平台推荐上限 {hi} 字，建议拆分："
                       f"{[i + 1 for i in long_chapters][:20]}",
            "indices": long_chapters,
        })
    if short_chapters:
        warnings.append({
            "code": "short_chapter",
            "message": f"{len(short_chapters)} 章低于平台推荐下限 {lo} 字："
                       f"{[i + 1 for i in short_chapters][:20]}",
            "indices": short_chapters,
        })

    if not book.intro.strip():
        warnings.append({"code": "no_intro", "message": "缺少故事前提/简介，发布前建议补充作品简介"})
    elif profile and len(book.intro) > profile.intro_max_chars:
        warnings.append({
            "code": "intro_too_long",
            "message": f"简介 {len(book.intro)} 字，超过该平台 {profile.intro_max_chars} 字上限",
        })

    sensitive = []
    for c in book.chapters:
        for hit in scan_text(c.text):
            sensitive.append({
                "word": hit.word,
                "count": hit.count,
                "chapter_index": c.chapter_index,
                "samples": hit.samples,
            })
    if sensitive:
        total = sum(s["count"] for s in sensitive)
        warnings.append({
            "code": "sensitive",
            "message": f"本地敏感词预检命中 {len(sensitive)} 处/共 {total} 次，平台审核可能驳回，请人工复核",
        })

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "sensitive": sensitive,
        "stats": {
            "platform": platform,
            "chapters": len(book.chapters),
            "volumes": len(book.volumes),
            "total_words": book.total_words,
            "missing_indices": missing,
            "empty_indices": empty,
            "per_chapter": per_chapter,
        },
    }
