"""Novel registry — manages multiple novels (bookshelf)."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


REGISTRY_PATH = Path("data/registry.json")
NOVELS_DIR = Path("data/novels")


class NovelInfo(BaseModel):
    novel_id: str
    title: str
    genre: str
    created_at: datetime = Field(default_factory=datetime.now)
    db_path: str
    status: str = "idle"  # idle / generating / paused / completed
    chapters_completed: int = 0
    chapters_total: int = 0
    word_count: int = 0
    propositions: dict = {}  # {"what_is": "...", "where_from": "...", "where_to": "..."}


class NovelRegistry(BaseModel):
    novels: list[NovelInfo] = Field(default_factory=list)
    active_novel_id: str | None = None


# ------------------------------------------------------------------
# Core I/O
# ------------------------------------------------------------------

def load_registry() -> NovelRegistry:
    """Load the registry from disk. Returns empty registry if not found."""
    if not REGISTRY_PATH.exists():
        return NovelRegistry()
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        return NovelRegistry.model_validate(data)
    except Exception:
        return NovelRegistry()


def save_registry(registry: NovelRegistry) -> None:
    """Persist the registry to disk."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        registry.model_dump_json(indent=2),
        encoding="utf-8",
    )


# ------------------------------------------------------------------
# Novel management
# ------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert title to a filesystem-safe slug (keep CJK, strip special chars)."""
    # Replace spaces / special chars with hyphens
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "-", text)
    slug = re.sub(r"-+", "-", slug).strip("-").lower()
    return slug or "novel"


def register_novel(
    title: str,
    genre: str,
    num_chapters: int = 0,
) -> NovelInfo:
    """Create a new novel directory, register it, and return the NovelInfo."""
    registry = load_registry()

    novel_id = _slugify(title)
    # Ensure uniqueness
    existing_ids = {n.novel_id for n in registry.novels}
    base_id = novel_id
    counter = 2
    while novel_id in existing_ids:
        novel_id = f"{base_id}-{counter}"
        counter += 1

    novel_dir = NOVELS_DIR / novel_id
    novel_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(novel_dir / "novel.db")

    info = NovelInfo(
        novel_id=novel_id,
        title=title,
        genre=genre,
        db_path=db_path,
        chapters_total=num_chapters,
    )

    registry.novels.append(info)
    registry.active_novel_id = novel_id
    save_registry(registry)
    return info


def get_active_novel() -> NovelInfo | None:
    """Return the currently active novel, or None."""
    registry = load_registry()
    if not registry.active_novel_id:
        return None
    return next(
        (n for n in registry.novels if n.novel_id == registry.active_novel_id),
        None,
    )


def set_active_novel(novel_id: str) -> NovelInfo:
    """Switch the active novel. Raises ValueError if not found."""
    registry = load_registry()
    novel = next((n for n in registry.novels if n.novel_id == novel_id), None)
    if novel is None:
        raise ValueError(f"Novel '{novel_id}' not found in registry")
    registry.active_novel_id = novel_id
    save_registry(registry)
    return novel


def update_novel_status(
    novel_id: str,
    *,
    status: str | None = None,
    chapters_completed: int | None = None,
    chapters_total: int | None = None,
    word_count: int | None = None,
) -> None:
    """Update stats for a registered novel."""
    registry = load_registry()
    novel = next((n for n in registry.novels if n.novel_id == novel_id), None)
    if novel is None:
        return  # silently skip if not registered (e.g. using --db directly)
    if status is not None:
        novel.status = status
    if chapters_completed is not None:
        novel.chapters_completed = chapters_completed
    if chapters_total is not None:
        novel.chapters_total = chapters_total
    if word_count is not None:
        novel.word_count = word_count
    save_registry(registry)


def delete_novel(novel_id: str) -> bool:
    """Delete a novel and its directory. Returns True if found and deleted."""
    registry = load_registry()
    novel = next((n for n in registry.novels if n.novel_id == novel_id), None)
    if novel is None:
        return False

    # Remove directory
    novel_dir = Path(novel.db_path).parent
    if novel_dir.exists():
        shutil.rmtree(novel_dir)

    registry.novels = [n for n in registry.novels if n.novel_id != novel_id]
    if registry.active_novel_id == novel_id:
        registry.active_novel_id = registry.novels[0].novel_id if registry.novels else None
    save_registry(registry)
    return True


def list_novels() -> list[NovelInfo]:
    """Return all registered novels."""
    return load_registry().novels


def get_novel_by_id(novel_id: str) -> NovelInfo | None:
    """Look up a novel by its ID."""
    registry = load_registry()
    return next((n for n in registry.novels if n.novel_id == novel_id), None)
