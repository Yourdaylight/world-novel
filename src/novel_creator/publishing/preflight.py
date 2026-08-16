"""Pre-publish quality gate — completeness, word stats, sensitive-word scan.

设计原则：错误（errors）必须修复才能导出；警告（warnings）不阻断。
敏感词命中只警告——本地词表无法覆盖平台审核规则，最终以平台审核为准。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .loader import NovelContent
from .platforms import PlatformProfile, get_profile

# 单章正文字数低于此值视为过短
MIN_CHAPTER_CHARS = 300


@dataclass
class SensitiveHit:
    word: str
    count: int
    chapters: list[int]


def _parse_wordlist(text: str) -> set[str]:
    words: set[str] = set()
    for line in text.splitlines():
        word = line.strip()
        if word and not word.startswith("#"):
            words.add(word)
    return words


@lru_cache(maxsize=4)
def load_wordlist() -> frozenset[str]:
    """Merge the bundled base list with an optional custom list.

    Custom path: ``data/config/sensitive_words.txt`` (relative to CWD).
    """
    base_path = Path(__file__).parent / "sensitive_words.txt"
    words = _parse_wordlist(base_path.read_text(encoding="utf-8")) if base_path.exists() else set()
    custom_path = Path("data/config/sensitive_words.txt")
    if custom_path.exists():
        words |= _parse_wordlist(custom_path.read_text(encoding="utf-8"))
    return frozenset(words)


def scan_sensitive(content: NovelContent) -> list[SensitiveHit]:
    """Scan intro + every chapter; return aggregated hits."""
    words = load_wordlist()
    if not words:
        return []
    hits: dict[str, SensitiveHit] = {}

    def _scan(text: str, chapter_index: int | None) -> None:
        for word in words:
            count = text.count(word)
            if count <= 0:
                continue
            entry = hits.get(word)
            if entry is None:
                entry = SensitiveHit(word=word, count=0, chapters=[])
                hits[word] = entry
            entry.count += count
            if chapter_index is not None and chapter_index not in entry.chapters:
                entry.chapters.append(chapter_index)

    _scan(content.intro, None)
    for chapter in content.chapters:
        _scan(chapter.text, chapter.index)

    return sorted(hits.values(), key=lambda h: (-h.count, h.word))


def run_preflight(
    content: NovelContent,
    platform_key: str | None = None,
) -> dict:
    """Run all quality checks. ``ok`` is True only when there are no errors."""
    errors: list[str] = []
    warnings: list[str] = []

    # ── 章节完整性 ─────────────────────────────────────────────
    if not content.chapters:
        errors.append("成书没有任何已渲染章节，无法导出")
    else:
        present = content.chapter_indices
        planned = content.planned_count or (max(present) + 1)
        expected = set(range(planned))
        missing = sorted(expected - present)
        if missing:
            shown = ", ".join(str(i + 1) for i in missing[:20])
            extra = " …" if len(missing) > 20 else ""
            errors.append(f"存在断章：缺少第 {shown}{extra} 章（共缺 {len(missing)} 章）")

        empty = [c.index + 1 for c in content.chapters if not c.text.strip()]
        if empty:
            errors.append(f"存在空章节：第 {', '.join(map(str, empty[:20]))} 章正文为空")

        short = [
            c.index + 1
            for c in content.chapters
            if c.text.strip() and c.word_count < MIN_CHAPTER_CHARS
        ]
        if short:
            warnings.append(
                f"{len(short)} 个章节少于 {MIN_CHAPTER_CHARS} 字："
                f"第 {', '.join(map(str, short[:10]))} 章"
                + (" …" if len(short) > 10 else "")
            )

        # 分卷覆盖校验：卷范围并集必须覆盖全部已渲染章节，否则分卷导出会丢章
        if content.volumes:
            covered: set[int] = set()
            for volume in content.volumes:
                covered |= {
                    i for i in present
                    if volume.chapter_start <= i <= volume.chapter_end
                }
            uncovered = sorted(present - covered)
            if uncovered:
                shown = ", ".join(str(i + 1) for i in uncovered[:20])
                extra = " …" if len(uncovered) > 20 else ""
                warnings.append(
                    f"分卷范围未覆盖第 {shown}{extra} 章"
                    f"（共 {len(uncovered)} 章）；七猫 ZIP 会把这些章节归入"
                    f"「未分卷章节.txt」，建议调整分卷范围"
                )

    # ── 元数据 ─────────────────────────────────────────────────
    if not content.title.strip():
        warnings.append("缺少书名")
    if not content.intro.strip():
        warnings.append("缺少简介：导出时将使用三命题/主题自动生成简介占位")

    # ── 平台规范 ───────────────────────────────────────────────
    profile: PlatformProfile | None = get_profile(platform_key) if platform_key else None
    if profile and profile.chapter_chars_recommended:
        overlong = [
            c.index + 1
            for c in content.chapters
            if c.word_count > profile.chapter_chars_recommended
        ]
        if overlong:
            warnings.append(
                f"{profile.name}建议单章 ≤ {profile.chapter_chars_recommended} 字，"
                f"{len(overlong)} 章超出：第 {', '.join(map(str, overlong[:10]))} 章"
                + (" …" if len(overlong) > 10 else "")
                + "（可在平台侧或拆章后再上传）"
            )

    # ── 敏感词 ─────────────────────────────────────────────────
    sensitive = scan_sensitive(content)
    if sensitive:
        preview = ", ".join(f"{h.word}×{h.count}" for h in sensitive[:10])
        warnings.append(
            f"敏感词预检命中 {len(sensitive)} 个词（{preview} …），"
            "请对照平台审核标准人工复核"
        )

    stats = {
        "chapter_count": len(content.chapters),
        "planned_count": content.planned_count,
        "volume_count": len(content.volumes),
        "total_words": content.total_words,
        "empty_chapters": sum(1 for c in content.chapters if not c.text.strip()),
    }

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "sensitive_hits": [
            {"word": h.word, "count": h.count, "chapters": h.chapters}
            for h in sensitive
        ],
        "platform": profile.key if profile else None,
    }
