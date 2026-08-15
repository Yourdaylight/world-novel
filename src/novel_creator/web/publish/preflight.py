"""Publication preflight quality gate (A-1, needs doc §3.3).

Checks run read-only against the novel DB:
1. chapter completeness — no missing indices (断章), no empty chapters (空章)
2. word-count statistics — total / per-chapter / min / max / avg
3. sensitive-word pre-check — local word list
4. metadata readiness — title / intro (premise) availability
5. platform fit — per-chapter length against the platform recommendation

``ok`` is False when any *error* exists (broken chapters make the export
meaningless). Warnings do not block the export.
"""

from __future__ import annotations

import json
from typing import Optional

import aiosqlite

from .sensitive import load_sensitive_words, scan_text


async def _load_chapters(novel_conn: aiosqlite.Connection) -> list[dict]:
    cursor = await novel_conn.execute(
        """SELECT chapter_index, title,
                  GROUP_CONCAT(content, CHAR(10)) AS body
           FROM chapter_texts
           GROUP BY chapter_index
           ORDER BY chapter_index"""
    )
    rows = await cursor.fetchall()
    return [
        {
            "chapter_index": r["chapter_index"],
            "title": r["title"] or "",
            "body": r["body"] or "",
        }
        for r in rows
    ]


async def _load_meta(novel_conn: aiosqlite.Connection) -> dict:
    outline: dict = {}
    cursor = await novel_conn.execute(
        "SELECT outline_json FROM story_outline WHERE id = 1"
    )
    row = await cursor.fetchone()
    if row:
        try:
            outline = json.loads(row["outline_json"])
        except Exception:
            outline = {}
    cursor = await novel_conn.execute(
        "SELECT COUNT(*) AS n FROM volumes"
    )
    vrow = await cursor.fetchone()
    return {
        "title": outline.get("title", ""),
        "genre": outline.get("genre", ""),
        "premise": outline.get("premise", ""),
        "setting": outline.get("setting", ""),
        "planned_chapters": len(outline.get("chapters", [])),
        "volume_count": vrow["n"] if vrow else 0,
    }


async def run_preflight(
    novel_conn: aiosqlite.Connection,
    *,
    platform_profile: Optional[dict] = None,
    registry_title: str = "",
) -> dict:
    """Return ``{ok, errors, warnings, stats}``."""
    errors: list[str] = []
    warnings: list[str] = []

    chapters = await _load_chapters(novel_conn)
    meta = await _load_meta(novel_conn)

    title = meta["title"] or registry_title

    # ── 1. chapter completeness ──────────────────────────────
    if not chapters:
        errors.append("没有任何章节内容，无法发布")
    else:
        indices = [c["chapter_index"] for c in chapters]
        expected = list(range(min(indices), max(indices) + 1))
        missing = sorted(set(expected) - set(indices))
        if missing:
            shown = ", ".join(f"第{i + 1}章" for i in missing[:10])
            more = "" if len(missing) <= 10 else f" 等 {len(missing)} 章"
            errors.append(f"存在断章（缺失章节）：{shown}{more}")

        empty = [
            c["chapter_index"]
            for c in chapters
            if not c["body"].strip()
        ]
        if empty:
            shown = ", ".join(f"第{i + 1}章" for i in empty[:10])
            errors.append(f"存在空章节（正文为空）：{shown}")

    # ── 2. word-count statistics ─────────────────────────────
    counts = [len(c["body"]) for c in chapters]
    total_words = sum(counts)
    stats = {
        "chapters": len(chapters),
        "total_words": total_words,
        "min_chapter_words": min(counts) if counts else 0,
        "max_chapter_words": max(counts) if counts else 0,
        "avg_chapter_words": int(total_words / len(counts)) if counts else 0,
        "volume_count": meta["volume_count"],
        "planned_chapters": meta["planned_chapters"],
    }
    if meta["planned_chapters"] and len(chapters) < meta["planned_chapters"]:
        warnings.append(
            f"成书章节数 {len(chapters)} 少于大纲规划 {meta['planned_chapters']} 章"
        )
    if counts and min(counts) < 300:
        warnings.append(f"最短章节仅 {min(counts)} 字，可能影响平台审核")

    # ── 3. sensitive words ───────────────────────────────────
    words = load_sensitive_words()
    sensitive_hits: list[dict] = []
    if words and chapters:
        for c in chapters:
            for hit in scan_text(c["body"], words):
                sensitive_hits.append(
                    {
                        "word": hit["word"],
                        "count": hit["count"],
                        "chapter_index": c["chapter_index"],
                    }
                )
    if sensitive_hits:
        preview = "、".join(h["word"] for h in sensitive_hits[:5])
        warnings.append(
            f"敏感词预检命中 {len(sensitive_hits)} 处（如：{preview}），请人工复核"
        )

    # ── 4. metadata readiness ────────────────────────────────
    if not title:
        warnings.append("缺少书名，导出将以 novel_id 代替")
    if not meta["premise"]:
        warnings.append("缺少故事前提，简介将使用模板占位文本")
    warnings.append("封面使用占位图（SVG），请在平台侧上传正式封面")

    # ── 5. platform fit ──────────────────────────────────────
    if platform_profile:
        cap = platform_profile.get("chapter_max_words") or 0
        if cap and counts:
            over = [
                c["chapter_index"] for c in chapters if len(c["body"]) > cap
            ]
            if over:
                warnings.append(
                    f"{len(over)} 章超过 {platform_profile['display_name']} "
                    f"建议单章 {cap} 字（不影响导出，平台侧可自行拆分）"
                )
        if platform_profile.get("cover_required") and not meta["premise"]:
            warnings.append("平台要求封面与简介，简介暂为占位文本")

    return {
        "ok": len(errors) == 0 and len(chapters) > 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "sensitive_hits": sensitive_hits,
        "title": title,
    }
