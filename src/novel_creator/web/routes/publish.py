"""Publish routes — L0 一键导出/发布（需求 A）。

番茄/七猫等平台无公开开放 API（需求文档 §3.2），本期实现：
  POST /publish/preflight          发布前质量门禁预检
  POST /publish/export             按平台规范导出 TXT/EPUB 并记录
  GET  /publish/platforms          平台适配清单
  GET  /publish/records            发布历史
  POST /publish/records/{id}/backfill  回填平台侧链接/书 ID（标记已发布）
  POST /publish/records/{id}/confirm  (L1 预留) 半自动提交草稿 → 501

L1（Playwright 半自动发布）为远期独立 sidecar 容器，不在 FastAPI 主进程。
"""

from __future__ import annotations

import json
import logging
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id
from novel_creator.web import publish_formats
from novel_creator.web.auth_deps import AuthUser, require_auth
from novel_creator.web.book_service import load_book_by_id
from novel_creator.web.publish_formats import (
    chapter_heading,
    export_warnings,
    get_profile,
    scan_sensitive,
)

logger = logging.getLogger("novel_creator.web.publish")

router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_auth)])


# ── Request models ────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    novel_id: str
    platform: str = "fanqie"


class BackfillRequest(BaseModel):
    target_book_id: str = ""
    target_url: str = ""

    @field_validator("target_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        # Storage XSS guard: only http(s) URLs are ever rendered as links.
        v = (v or "").strip()
        if v and not v.lower().startswith(("http://", "https://")):
            raise ValueError("链接必须以 http:// 或 https:// 开头")
        if len(v) > 500:
            raise ValueError("链接过长")
        return v

    @field_validator("target_book_id")
    @classmethod
    def _validate_book_id(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 64:
            raise ValueError("书 ID 过长")
        return v


# ── Preflight ─────────────────────────────────────────────────────────────

async def run_preflight(novel_id: str, platform: str) -> dict:
    """质量门禁：章节完整性 / 字数 / 敏感词 / 平台规范。"""
    try:
        profile = get_profile(platform)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "stats": {}}

    book = await load_book_by_id(novel_id)
    if book is None:
        return {"ok": False, "errors": ["未找到该小说"], "warnings": [], "stats": {}}

    errors: list[str] = []
    if not book.chapters:
        errors.append("尚无任何已生成章节，无法发布")

    empties = [ch for ch in book.chapters if ch.words == 0]
    if empties:
        errors.append("存在空章节：" + "、".join(chapter_heading(ch) for ch in empties[:10]))

    present = sorted(ch.index for ch in book.chapters)
    if present:
        missing = sorted(set(range(present[-1] + 1)) - set(present))
        if missing:
            errors.append(
                "存在断章（缺失第 "
                + "、".join(str(m + 1) for m in missing[:10])
                + " 章）"
            )

    sensitive_hits = scan_sensitive(book)
    if sensitive_hits:
        sample = "、".join(
            f"「{h['word']}」×{h['count']}（第{h['chapter_index'] + 1}章）"
            for h in sensitive_hits[:8]
        )
        errors.append(f"敏感词预检未通过：{sample}……请修改后重新预检")

    warnings = export_warnings(book, profile)
    # Encoding loss check (GB18030 covers all Unicode in practice; defends
    # against corrupted/surrogate input from LLM JSON).
    sample = "\n".join(ch.text for ch in book.chapters)
    try:
        sample.encode(profile.encoding)
    except UnicodeEncodeError:
        warnings.append(
            f"存在无法以 {profile.encoding.upper()} 编码的字符，TXT 导出将以？替换，建议改用 EPUB 导出"
        )
    if book.total_words and book.total_words < 1000:
        warnings.append(f"全书仅约 {book.total_words} 字，篇幅较短，平台签约通常要求更长篇幅")

    stats = {
        "chapters": len([c for c in book.chapters if c.words > 0]),
        "planned": book.planned_total or len(book.chapters),
        "total_words": book.total_words,
        "volumes": len(book.volumes),
        "encoding": profile.encoding,
        "platform": profile.key,
        "platform_label": profile.label,
        "has_intro": bool(book.intro),
    }
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "sensitive_hits": sensitive_hits,
        "stats": stats,
    }


def _check_novel_access(novel_id: str, user: AuthUser):
    """Owner or admin may publish; owner_id='' = legacy trusted single-instance."""
    novel = get_novel_by_id(novel_id)
    if novel is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "未找到该小说"})
    if novel.owner_id and novel.owner_id != (user.sub or "") and not user.is_admin:
        return JSONResponse(status_code=403, content={"ok": False, "error": "无权导出他人的小说"})
    return None


@protected_router.post("/publish/preflight")
async def preflight(req: ExportRequest, user: AuthUser = Depends(require_auth)):
    denied = _check_novel_access(req.novel_id, user)
    if denied is not None:
        return denied
    return await run_preflight(req.novel_id, req.platform)


@router.get("/publish/platforms")
async def platforms():
    """平台适配清单（静态信息，公开）。"""
    return {"platforms": publish_formats.platform_catalog()}


# ── Export ────────────────────────────────────────────────────────────────

async def _write_record(record: dict) -> None:
    conn = await get_connection(settings.db_path)
    try:
        await conn.execute(
            """INSERT INTO publication_records
               (id, novel_id, platform, stage, target_book_id, target_url,
                export_meta, operator, created_at, updated_at)
               VALUES (:id, :novel_id, :platform, :stage, '', '', :meta, :operator,
                       CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            record,
        )
        await conn.commit()
    finally:
        await conn.close()


@protected_router.post("/publish/export")
async def export(req: ExportRequest, user: AuthUser = Depends(require_auth)):
    """按平台规范导出成书；质量门禁不通过返回 409 + 预检详情。"""
    denied = _check_novel_access(req.novel_id, user)
    if denied is not None:
        return denied
    check = await run_preflight(req.novel_id, req.platform)
    if not check["ok"]:
        return JSONResponse(status_code=409, content={"ok": False, "preflight": check})

    book = await load_book_by_id(req.novel_id)
    record_id = secrets.token_hex(8)
    try:
        # CPU-bound serialization (TXT/EPUB/ZIP) — keep the event loop free
        import anyio
        filename, media_type, payload = await anyio.to_thread.run_sync(
            publish_formats.build_export, book, req.platform,
        )
        profile = get_profile(req.platform)
        await _write_record({
            "id": record_id,
            "novel_id": req.novel_id,
            "platform": profile.key,
            "stage": "exported",
            "meta": json.dumps({
                "chapters": check["stats"]["chapters"],
                "words": check["stats"]["total_words"],
                "format": profile.format,
                "encoding": profile.encoding,
                "filename": filename,
                "size": len(payload),
                "warnings": check["warnings"][:10],
            }, ensure_ascii=False),
            "operator": user.sub or "anonymous",
        })
    except Exception:
        logger.exception("publish export failed: novel=%s platform=%s", req.novel_id, req.platform)
        try:
            await _write_record({
                "id": record_id,
                "novel_id": req.novel_id,
                "platform": req.platform,
                "stage": "failed",
                "meta": json.dumps({"error": "export_failed"}, ensure_ascii=False),
                "operator": user.sub or "anonymous",
            })
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "导出失败，请稍后重试"},
        )

    encoded = quote(filename)
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            # ASCII fallback for older clients, UTF-8'' for the real CJK name
            "Content-Disposition": (
                f"attachment; filename=novel.{profile.format if profile.format != 'txt' else 'txt'}; "
                f"filename*=UTF-8''{encoded}"
            ),
            "X-Publish-Record-Id": record_id,
        },
    )


# ── Records ───────────────────────────────────────────────────────────────

def _record_dict(row) -> dict:
    meta = {}
    try:
        meta = json.loads(row["export_meta"] or "{}")
    except json.JSONDecodeError:
        pass
    return {
        "id": row["id"],
        "novel_id": row["novel_id"],
        "platform": row["platform"],
        "stage": row["stage"],
        "target_book_id": row["target_book_id"],
        "target_url": row["target_url"],
        "export_meta": meta,
        "operator": row["operator"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@protected_router.get("/publish/records")
async def list_records(
    novel_id: str | None = None,
    user: AuthUser = Depends(require_auth),
):
    """发布历史：本人可见自己的记录，管理员可见全部。"""
    conn = await get_connection(settings.db_path)
    try:
        sql = "SELECT * FROM publication_records"
        clauses, params = [], []
        if not user.is_admin:
            clauses.append("operator = ?")
            params.append(user.sub or "anonymous")
        if novel_id:
            clauses.append("novel_id = ?")
            params.append(novel_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT 200"
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
    finally:
        await conn.close()
    return {"records": [_record_dict(r) for r in rows]}


@protected_router.post("/publish/records/{record_id}/backfill")
async def backfill_record(
    record_id: str,
    req: BackfillRequest,
    user: AuthUser = Depends(require_auth),
):
    """作者在平台侧上传后回填书 ID/链接，记录状态置为已发布。"""
    conn = await get_connection(settings.db_path)
    try:
        cursor = await conn.execute(
            "SELECT * FROM publication_records WHERE id = ?", (record_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return JSONResponse(status_code=404, content={"ok": False, "error": "记录不存在"})
        if not user.is_admin and row["operator"] != (user.sub or "anonymous"):
            return JSONResponse(status_code=403, content={"ok": False, "error": "无权操作他人记录"})
        if not (req.target_book_id or req.target_url):
            return JSONResponse(
                status_code=400, content={"ok": False, "error": "请至少回填书 ID 或作品链接"},
            )
        await conn.execute(
            """UPDATE publication_records
               SET target_book_id = ?, target_url = ?, stage = 'published',
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (req.target_book_id.strip(), req.target_url.strip(), record_id),
        )
        await conn.commit()
    finally:
        await conn.close()
    return {"ok": True, "id": record_id, "stage": "published"}


@protected_router.post("/publish/records/{record_id}/confirm")
async def confirm_publish(record_id: str, user: AuthUser = Depends(require_auth)):
    """L1 半自动发布预留接口：需要独立 publish-browser 容器，本期未启用。"""
    return JSONResponse(
        status_code=501,
        content={
            "ok": False,
            "code": "l1_not_enabled",
            "error": "L1 半自动发布未启用（需要独立 publish-browser sidecar 容器），"
                     "当前版本请使用 L0 导出后在作家后台手动上传",
        },
    )
