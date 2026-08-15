"""Routes package — combines all sub-routers into a single ``router``."""

from __future__ import annotations

from fastapi import APIRouter

from .auth import router as auth_router
from .novels import router as novels_router
from .novels import protected_router as novels_protected_router
from .story import router as story_router
from .characters import router as characters_router
from .characters import protected_router as characters_protected_router
from .generation import router as generation_router
from .historian import router as historian_router
from .export import router as export_router
from .admin import router as admin_router
from .export import protected_router as export_protected_router
from .share import router as share_router
from .share import protected_router as share_protected_router
from .publish import router as publish_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(novels_router)
router.include_router(novels_protected_router)
router.include_router(story_router)
router.include_router(characters_router)
router.include_router(characters_protected_router)
router.include_router(generation_router)
router.include_router(historian_router)
router.include_router(export_router)
router.include_router(admin_router)
router.include_router(export_protected_router)
router.include_router(share_router)
router.include_router(share_protected_router)
router.include_router(publish_router)
