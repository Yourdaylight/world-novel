"""Routes package — combines all sub-routers into a single ``router``."""

from __future__ import annotations

from fastapi import APIRouter

from .novels import router as novels_router
from .story import router as story_router
from .characters import router as characters_router
from .generation import router as generation_router
from .historian import router as historian_router
from .export import router as export_router

router = APIRouter()

router.include_router(novels_router)
router.include_router(story_router)
router.include_router(characters_router)
router.include_router(generation_router)
router.include_router(historian_router)
router.include_router(export_router)
