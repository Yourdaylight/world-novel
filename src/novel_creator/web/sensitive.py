"""Local sensitive-word pre-check (requirement A-1).

Platforms (番茄/七猫/…) run their own content review on submission; this is a
first-pass local lint so obvious violations are caught *before* export. It is
deliberately conservative and customisable:

- a bundled seed list ships with the package (``data/sensitive_words.txt``)
- ``NOVEL_SENSITIVE_WORDS_PATH`` may point at a site-maintained list which is
  merged on top (one word per line, ``#`` comments, blank lines ignored)

The scanner is a simple Aho–Corasick-free multi-substring scan; lists are
small (hundreds of terms) and books are scanned once per preflight.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_WORDS_FILE = Path(__file__).parent / "data" / "sensitive_words.txt"


@dataclass
class Hit:
    word: str
    count: int
    samples: list[str]


def _read_words(path: Path) -> set[str]:
    words: set[str] = set()
    if not path.exists():
        return words
    for raw in path.read_text(encoding="utf-8").splitlines():
        w = raw.strip()
        if w and not w.startswith("#"):
            words.add(w.lower())
    return words


@lru_cache(maxsize=4)
def _word_list(custom_path: str) -> frozenset[str]:
    words = _read_words(_WORDS_FILE)
    if custom_path:
        words |= _read_words(Path(custom_path))
    return frozenset(w for w in words if len(w) >= 2)


def get_word_list() -> frozenset[str]:
    return _word_list(os.environ.get("NOVEL_SENSITIVE_WORDS_PATH", ""))


def _snippet(text: str, start: int, word: str, radius: int = 12) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), start + len(word) + radius)
    return text[lo:hi].replace("\n", " ").strip()


def scan_text(text: str, *, max_samples_per_word: int = 2) -> list[Hit]:
    """Return sensitive-word hits found in ``text`` (case-insensitive)."""
    if not text:
        return []
    lowered = text.lower()
    hits: dict[str, Hit] = {}
    for word in get_word_list():
        count = lowered.count(word)
        if count <= 0:
            continue
        samples: list[str] = []
        idx = lowered.find(word)
        while idx != -1 and len(samples) < max_samples_per_word:
            samples.append(_snippet(text, idx, word))
            idx = lowered.find(word, idx + len(word))
        hits[word] = Hit(word=word, count=count, samples=samples)
    return sorted(hits.values(), key=lambda h: (-h.count, h.word))
