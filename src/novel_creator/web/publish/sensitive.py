"""Sensitive-word pre-check for publication (A-1, needs doc §3.3).

Local word-list based: a small base list ships with the repo and can be
extended via ``data/sensitive_words_custom.txt`` (one word per line) or the
``NOVEL_SENSITIVE_WORDS_PATH`` env var.

This is a pre-publication hygiene gate, not a full content-safety system.
"""

from __future__ import annotations

from pathlib import Path

from novel_creator.config import settings

_BASE_LIST_PATH = Path(__file__).parent / "data" / "sensitive_words_base.txt"


def _load_words(path: Path) -> set[str]:
    words: set[str] = set()
    if not path.exists():
        return words
    try:
        # 自定义词表编码不可控：容错读取，坏行跳过而不是让预检崩溃
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                words.add(w)
    except OSError:
        pass
    return words


def load_sensitive_words() -> set[str]:
    """Base list + custom list (custom wins on conflict, both are unions)."""
    words = _load_words(_BASE_LIST_PATH)

    custom_env = getattr(settings, "sensitive_words_path", "") or ""
    candidates = [
        Path(custom_env) if custom_env else None,
        Path("data/sensitive_words_custom.txt"),
    ]
    for cand in candidates:
        if cand is not None and cand.exists():
            words |= _load_words(cand)
    return words


def scan_text(text: str, words: set[str] | None = None) -> list[dict]:
    """Scan text; return hit list ``[{word, count, chapter_hint}]``.

    ``chapter_hint`` is filled by callers that scan chapter-by-chapter; here we
    just report occurrences in the given text.
    """
    if words is None:
        words = load_sensitive_words()
    hits: list[dict] = []
    for w in sorted(words, key=len, reverse=True):
        count = text.count(w)
        if count > 0:
            hits.append({"word": w, "count": count})
    return hits
