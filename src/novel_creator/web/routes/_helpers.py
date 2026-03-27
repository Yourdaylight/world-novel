"""Shared helpers and common imports for route modules."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import (
    load_registry,
    list_novels,
    set_active_novel,
    get_active_novel,
    register_novel,
    update_novel_status,
    get_novel_by_id,
    delete_novel,
    save_registry,
)

logger = logging.getLogger("novel_creator.web")


async def _get_novel_db(novel_id: str | None = None) -> str:
    """Resolve novel_id to db_path. Falls back to active novel, then settings."""
    registry = load_registry()
    if novel_id:
        novel = next((n for n in registry.novels if n.novel_id == novel_id), None)
        if novel:
            return novel.db_path
    if registry.active_novel_id:
        novel = next(
            (n for n in registry.novels if n.novel_id == registry.active_novel_id),
            None,
        )
        if novel:
            return novel.db_path
    return settings.db_path  # ultimate fallback
