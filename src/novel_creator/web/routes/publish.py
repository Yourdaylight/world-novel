"""Publish routes — requirement A (成书一键发布 L0).

  POST /publish/preflight            quality gate (protected)
  POST /publish/export              platform export download (protected)
  GET  /publish/records             publication history (protected)
  POST /publish/records/{id}/backfill  record platform-side book id/url (protected)

L1 browser automation (Playwright sidecar) is intentionally out of scope; the
``stage`` field and ``confirm`` hook are reserved for it.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from anyio.to_thread import run_sync

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.publication_store import (
    create_record,
    list_records,
    update_publish_backfill,
)
from novel_creator.memory.registry import get_novel_by_id

from ..auth_deps import AuthUser, require_auth
from ..book import BookNotFound, load_book
from ..platforms import PLATFORMS, export_book
from ..quality import run_preflight
from ._helpers import can_manage_novel, user_identity

router = APIRouter(dependencies=[Depends(require_auth)])


class ExportRequest(BaseModel):
    platform: str = Field(default="fanqie", description="fanqie|qimao|txt|epub|rtf|bundle")
    novel_id: str | None = None


def _require_manage(novel_id: str, user: AuthUser):
    """Resolve a novel and ensure the caller may publish/share it."""
    novel = get_novel_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="未找到小说")
    if not can_manage_novel(novel, user):
        raise HTTPException(status_code=403, detail="无权操作他人的小说")
    return novel


class BackfillRequest(BaseModel):
    target_book_id: str = ""
    target_url: str = ""
    stage: str = "published"


@router.post("/publish/preflight")
async def publish_preflight(
    novel_id: str | None = Query(None),
    platform: str = Query("fanqie"),
    user: AuthUser = Depends(require_auth),
):
    """Run the quality gate without producing a file."""
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"未知平台: {platform}")
    target = novel_id or _active_novel_id()
    _require_manage(target, user)
    try:
        book = await load_book(target)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    # CPU-bound scan — keep it off the event loop for large books.
    return await run_sync(run_preflight, book, platform)


@router.post("/publish/export")
async def publish_export(req: ExportRequest, user: AuthUser = Depends(require_auth)):
    """Export the book in the requested platform format.

    Errors (empty/gap) block export with 422. Warnings do not.
    """
    if req.platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"未知平台: {req.platform}")

    target = req.novel_id or _active_novel_id()
    _require_manage(target, user)
    try:
        book = await load_book(target)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    verdict = await run_sync(run_preflight, book, req.platform)
    if not verdict["ok"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "质量门禁未通过，请先修复以下问题", "preflight": verdict},
        )

    # CPU-bound rendering of all formats — off the event loop.
    payload, filename, media_type = await run_sync(export_book, book, req.platform)
    operator = user_identity(user)

    # Record the export in the central db.
    conn = await get_connection(settings.db_path)
    try:
        await create_record(
            conn,
            novel_id=target,
            platform=req.platform,
            stage="exported",
            export_meta={
                "filename": filename,
                "bytes": len(payload),
                "chapters": verdict["stats"]["chapters"],
                "total_words": verdict["stats"]["total_words"],
                "warnings": len(verdict["warnings"]),
            },
            operator=operator,
        )
    finally:
        await conn.close()

    encoded = quote(filename)
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition":
                f"attachment; filename=\"export.{PLATFORMS[req.platform].file_ext}\"; "
                f"filename*=UTF-8''{encoded}",
            "X-Export-Warnings": str(len(verdict["warnings"])),
        },
    )


@router.get("/publish/records")
async def publish_records(
    novel_id: str | None = Query(None),
    user: AuthUser = Depends(require_auth),
):
    """Publication history for the active (or given) novel.

    Non-admins only see their own records; admins see every record.
    """
    conn = await get_connection(settings.db_path)
    try:
        records = await list_records(
            conn,
            novel_id=novel_id,
            operator=None if user.is_admin else user_identity(user),
        )
    finally:
        await conn.close()
    return {"records": records, "total": len(records)}


@router.post("/publish/records/{record_id}/backfill")
async def publish_backfill(
    record_id: str, req: BackfillRequest, user: AuthUser = Depends(require_auth)
):
    """Record the platform-side book id / url after manual upload (A-5)."""
    conn = await get_connection(settings.db_path)
    try:
        async with conn.execute(
            "SELECT operator FROM publication_records WHERE id = ?", (record_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="发布记录不存在")
        if not user.is_admin and (row["operator"] != user_identity(user)):
            raise HTTPException(status_code=403, detail="无权操作他人的发布记录")
        ok = await update_publish_backfill(
            conn,
            record_id,
            target_book_id=req.target_book_id,
            target_url=req.target_url,
            stage=req.stage or "published",
        )
    finally:
        await conn.close()
    if not ok:
        raise HTTPException(status_code=404, detail="发布记录不存在")
    return {"ok": True}


def _active_novel_id() -> str:
    """Resolve the active novel id from the registry (empty string if none)."""
    from novel_creator.memory.registry import get_active_novel
    active = get_active_novel()
    return active.novel_id if active else ""
