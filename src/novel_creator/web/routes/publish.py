"""Publish routes — 成书一键导出（L0）+ 发布记录。

挂载点：/api/publish/*（全部需要登录）

- GET  /publish/platforms          平台适配清单
- POST /publish/preflight          发布前质量门禁
- POST /publish/export             按平台导出 TXT/EPUB/ZIP（含发布记录）
- GET  /publish/records            发布历史
- PATCH /publish/records/{id}      回填平台侧书 ID / 链接（A-5）

L1 半自动（Playwright 驱动作家后台）为远期能力，平台均无开放 API。
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from novel_creator.publishing import records as record_store
from novel_creator.publishing.exporters import export_content
from novel_creator.publishing.loader import load_novel_content
from novel_creator.publishing.platforms import get_profile, platform_dicts
from novel_creator.publishing.preflight import run_preflight

from ..auth_deps import AuthUser, require_auth

# 每个端点单独声明 require_auth：既完成鉴权，又在需要时拿到用户标识，
# 避免“路由级 + 参数级”重复验签（casdoor 模式尤其避免重复 sidecar 请求）。
router = APIRouter()


def _operator(user: AuthUser) -> str:
    return user.code or user.sub or user.username or "unknown"


class PreflightRequest(BaseModel):
    novel_id: str
    platform: str | None = Field(default=None, description="可选：按平台规范追加检查")


class ExportRequest(BaseModel):
    novel_id: str
    platform: str = Field(description="fanqie | qimao | txt | epub")


class RecordBackfill(BaseModel):
    target_book_id: str | None = None
    target_url: str | None = None
    stage: str | None = Field(default=None, description="exported | published | failed")


@router.get("/publish/platforms")
async def list_platforms(_user: AuthUser = Depends(require_auth)):
    return {"platforms": platform_dicts()}


@router.post("/publish/preflight")
async def preflight(req: PreflightRequest, _user: AuthUser = Depends(require_auth)):
    content = await load_novel_content(req.novel_id)
    if content is None:
        raise HTTPException(status_code=404, detail="未找到该小说")
    report = run_preflight(content, req.platform)
    report["novel_id"] = req.novel_id
    report["title"] = content.title
    return report


@router.post("/publish/export")
async def export_novel(req: ExportRequest, user: AuthUser = Depends(require_auth)):
    profile = get_profile(req.platform)
    if profile is None:
        raise HTTPException(status_code=400, detail=f"不支持的平台：{req.platform}")

    content = await load_novel_content(req.novel_id)
    if content is None:
        raise HTTPException(status_code=404, detail="未找到该小说")

    report = run_preflight(content, profile.key)
    if not report["ok"]:
        raise HTTPException(
            status_code=409,
            detail={"message": "质量门禁未通过，请先修复以下问题", "report": report},
        )

    result = export_content(content, profile)
    record = await record_store.create_record(
        novel_id=req.novel_id,
        platform=profile.key,
        operator=_operator(user),
        export_meta=result.meta,
    )

    filename = quote(result.filename)
    return Response(
        content=result.data,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Publish-Record-Id": record.get("id", ""),
            "Access-Control-Expose-Headers": "X-Publish-Record-Id, Content-Disposition",
        },
    )


@router.get("/publish/records")
async def list_records(
    novel_id: str | None = None,
    _user: AuthUser = Depends(require_auth),
):
    return {"records": await record_store.list_records(novel_id)}


@router.patch("/publish/records/{record_id}")
async def backfill_record(
    record_id: str,
    req: RecordBackfill,
    _user: AuthUser = Depends(require_auth),
):
    if req.stage is not None and req.stage not in ("exported", "published", "failed"):
        raise HTTPException(status_code=400, detail="stage 必须是 exported/published/failed")
    record = await record_store.update_record(
        record_id,
        target_book_id=req.target_book_id,
        target_url=req.target_url,
        stage=req.stage,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="发布记录不存在")
    return record
