"""Trial-reading policy — 匿名试读边界判定（唯一真相在后端）。"""

from __future__ import annotations


def trial_chapter_count(
    *,
    trial_mode: str,
    trial_value: int,
    total_chapters: int,
    chapter_words: list[int] | None = None,
) -> int:
    """How many leading chapters an anonymous reader may read.

    - first_n_chapters: 前 N 章
    - word_count:       累计字数不超过 N 的章节前缀
    - ratio:            全书章节数的 N%
    """
    if total_chapters <= 0:
        return 0
    value = max(0, trial_value)

    if trial_mode == "word_count":
        # value=0 表示关闭试读（强制注册），任何章节都不下发
        if value == 0 or not chapter_words:
            return 0
        readable = 0
        cumulative = 0
        for words in chapter_words:
            if cumulative + words > value and readable > 0:
                break
            cumulative += words
            readable += 1
            if readable >= total_chapters:
                break
        return readable

    if trial_mode == "ratio":
        value = min(100, value)
        # round down, but at least 0
        return int(total_chapters * value / 100)

    # default: first_n_chapters
    return min(value, total_chapters)


def is_chapter_readable(
    *,
    trial_mode: str,
    trial_value: int,
    chapter_index: int,
    total_chapters: int,
    chapter_words: list[int] | None = None,
    is_authenticated: bool,
) -> bool:
    """Registered readers (L1) get the full book; anonymous readers are
    bounded by the trial policy. Index is 0-based."""
    if is_authenticated:
        return True
    if chapter_index < 0 or chapter_index >= total_chapters:
        return False
    limit = trial_chapter_count(
        trial_mode=trial_mode,
        trial_value=trial_value,
        total_chapters=total_chapters,
        chapter_words=chapter_words,
    )
    return chapter_index < limit
