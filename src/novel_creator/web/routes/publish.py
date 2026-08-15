"""Publish routes — one-click export to external platforms (Milestone 15, Req A).

All endpoints require auth (author surface).

  GET   /publish/platforms              — available platform profiles
  POST  /publish/preflight              — quality gate (A-1)
  POST  /publish/export                 — L0 export package download (A-2/A-3)
  GET   /publish/records                — publication history (A-3)
  PATCH /publish/records/{record_id}    — backfill platform book id / url (A-5)
  POST  /publish/records/{record_id}/confirm — (L1 reserved) 501 until platforms
        open an API (needs doc §3.2: no public open API exists today)
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from urllib.parse import quote

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id
from novel_creator.web.auth_deps import AuthUser, require_auth
from novel_creator.web.publish import exporter, platforms
from novel_creator.web.publish.preflight import run_preflight

router = APIRouter(prefix="/publish", dependencies=[Depends(require_auth)])


def _user_key(user: AuthUser) -> str:
    return user.code or user.sub or "anonymous"


class PreflightRequest(BaseModel):
    novel_id: str
    platform: str = ""  # optional platform-specific fit check


class ExportRequest(BaseModel):
    novel_id: str
    platform: str = Field(description="fanqie | qimao | txt | epub")


class BackfillRequest(BaseModel):
    target_book_id: str = ""
    target_url: str = ""
    stage: str = ""


@router.get("/platforms")
async def list_platforms():
    """Available export targets with their upload specs."""
    conn = await get_connection(settings.db_path)
    try:
        profiles = await platforms.list_platform_profiles(conn)
    finally:
        await conn.close()
    return {"platforms": profiles}


async def _open_novel(novel_id: str):
    novel = get_novel_by_id(novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


@router.post("/preflight")
async def publish_preflight(req: PreflightRequest, user: AuthUser = Depends(require_auth)):
    """Quality gate before export (A-1).

    ``ok=false`` blocks export (broken/empty chapters). Warnings are advisory.
    """
    novel = await _open_novel(req.novel_id)

    conn = await get_connection(settings.db_path)
    try:
        profile = None
        if req.platform:
            profile = await platforms.get_platform_profile(conn, req.platform)
            if profile is None:
                raise HTTPException(
                    status_code=400, detail=f"未知平台: {req.platform}"
                )
    finally:
        await conn.close()

    novel_conn = await get_connection(novel.db_path)
    try:
        result = await run_preflight(
            novel_conn, platform_profile=profile, registry_title=novel.title
        )
    finally:
        await novel_conn.close()

    return result


async def _load_export_data(db_path: str) -> tuple[list[dict], list[dict], dict]:
    """Chapters (with joined body), volumes, meta for the exporter."""
    conn = await get_connection(db_path)
    try:
        cursor = await conn.execute(
            """SELECT chapter_index, title,
                      GROUP_CONCAT(content, CHAR(10)) AS body
               FROM chapter_texts GROUP BY chapter_index
               ORDER BY chapter_index"""
        )
        chapters = [
            {
                "chapter_index": r["chapter_index"],
                "title": r["title"] or "",
                "body": r["body"] or "",
            }
            for r in await cursor.fetchall()
        ]
        cursor = await conn.execute(
            "SELECT volume_index, title, chapter_start, chapter_end "
            "FROM volumes ORDER BY volume_index"
        )
        volumes = [dict(r) for r in await cursor.fetchall()]

        import json as _json

        meta: dict = {}
        cursor = await conn.execute(
            "SELECT outline_json FROM story_outline WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row:
            try:
                meta = _json.loads(row["outline_json"])
            except Exception:
                meta = {}
    finally:
        await conn.close()
    return chapters, volumes, meta


@router.post("/export")
async def publish_export(req: ExportRequest, user: AuthUser = Depends(require_auth)):
    """L0 one-click export: run the gate, build the platform package, record it.

    Returns the ZIP directly (synchronous — exports are fast SQLite reads).
    """
    novel = await _open_novel(req.novel_id)

    conn = await get_connection(settings.db_path)
    try:
        profile = await platforms.get_platform_profile(conn, req.platform)
        if profile is None:
            raise HTTPException(status_code=400, detail=f"未知平台: {req.platform}")
    finally:
        await conn.close()

    chapters, volumes, meta = await _load_export_data(novel.db_path)

    # Gate: refuse to export broken books
    novel_conn = await get_connection(novel.db_path)
    try:
        gate = await run_preflight(
            novel_conn, platform_profile=profile, registry_title=novel.title
        )
    finally:
        await novel_conn.close()
    if not gate["ok"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "质量门禁未通过，已拒绝导出", "errors": gate["errors"]},
        )

    title = gate["title"] or novel.title
    record_id = f"pub_{secrets.token_hex(8)}"

    conn = await get_connection(settings.db_path)
    try:
        await platforms.create_publication_record(
            conn,
            record_id=record_id,
            novel_id=req.novel_id,
            platform=req.platform,
            operator=_user_key(user),
            stage="exporting",
        )
        try:
            package, filename, export_meta = exporter.build_package(
                platform_profile=profile,
                title=title,
                novel_id=req.novel_id,
                chapters=chapters,
                volumes=volumes,
                meta=meta,
                stats=gate["stats"],
            )
        except Exception as e:
            await platforms.update_publication_record(
                conn, record_id, stage="failed"
            )
            raise HTTPException(status_code=500, detail=f"导出失败: {e}")

        export_meta["record_id"] = record_id
        await platforms.update_publication_record(
            conn, record_id, stage="exported", export_meta=export_meta
        )
    finally:
        await conn.close()

    return Response(
        content=package,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            ),
            "X-Publication-Record-Id": record_id,
        },
    )


@router.get("/records")
async def publish_records(novel_id: str = "", user: AuthUser = Depends(require_auth)):
    """Publication history, optionally filtered by novel."""
    conn = await get_connection(settings.db_path)
    try:
        records = await platforms.list_publication_records(
            conn, novel_id=novel_id or None
        )
    finally:
        await conn.close()
    return {"records": records}


@router.patch("/records/{record_id}")
async def publish_backfill(record_id: str, req: BackfillRequest, user: AuthUser = Depends(require_auth)):
    """Backfill the platform-side book id/url after manual upload (A-5).

    Providing a target_url auto-marks the record as ``published``.
    """
    conn = await get_connection(settings.db_path)
    try:
        record = await platforms.get_publication_record(conn, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="发布记录不存在")

        stage = req.stage or ""
        if not stage and req.target_url:
            stage = "published"
        if stage and stage not in platforms.VALID_STAGES:
            raise HTTPException(status_code=400, detail=f"非法状态: {stage}")

        await platforms.update_publication_record(
            conn,
            record_id,
            stage=stage or None,
            target_book_id=req.target_book_id or None,
            target_url=req.target_url or None,
        )
        record = await platforms.get_publication_record(conn, record_id)
    finally:
        await conn.close()
    return {"ok": True, "record": record}


@router.post("/records/{record_id}/confirm")
async def publish_confirm(record_id: str, user: AuthUser = Depends(require_auth)):
    """L1 semi-auto publishing (Playwright draft submission) — reserved.

    Needs doc §3.2: no platform exposes an open API; L1 ships only when a
    compliant channel exists. The endpoint is defined now so clients can rely
    on a stable contract.
    """
    conn = await get_connection(settings.db_path)
    try:
        record = await platforms.get_publication_record(conn, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="发布记录不存在")
    finally:
        await conn.close()
    raise HTTPException(
        status_code=501,
        detail=(
            "L1 半自动发布暂未开放：目标平台无公开 API。"
            "请使用 L0 导出包在平台作家后台手动上传。"
        ),
    )
