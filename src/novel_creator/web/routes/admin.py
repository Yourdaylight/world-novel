"""Admin管理路由 - 邀请码管理、额度分配、使用统计。

所有接口需要管理员权限（admin级别的邀请码）。
提供邀请码的CRUD、用户配额管理和系统使用统计功能。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import (
    add_user_quota,
    create_invite_code,
    deactivate_invite_code,
    delete_invite_code,
    ensure_user_quota_exists,
    get_usage_summary,
    get_user_quota,
    get_user_usage_logs,
    list_invite_codes,
    set_user_quota,
)
from novel_creator.web.auth_deps import AuthUser, require_admin

logger = logging.getLogger("novel_creator.web.admin")

router = APIRouter()


# ========== 请求/响应模型 ==========


class CreateInviteCodeRequest(BaseModel):
    """创建邀请码请求参数。"""

    code: Optional[str] = None  # 不提供则自动生成
    description: str = ""
    max_uses: int = 1
    initial_tokens: int = 100000  # 初始token额度
    initial_requests: int = 500  # 初始请求额度
    initial_chapters: int = 10  # 初始章节额度
    plan_type: str = "free"


class SetQuotaRequest(BaseModel):
    """设置用户配额请求参数（覆盖式）。"""

    total_tokens: Optional[int] = None
    total_requests: Optional[int] = None
    chapter_quota: Optional[int] = None
    plan_type: Optional[str] = None
    expires_at: Optional[str] = None  # ISO格式日期字符串


class AddQuotaRequest(BaseModel):
    """增加用户配额请求参数（充值）。"""

    tokens: int = 0
    requests: int = 0
    chapters: int = 0


# ========== 辅助函数 ==========


def _parse_expires_at(expires_at_str: Optional[str]) -> Optional[datetime]:
    """解析ISO格式日期字符串为datetime对象。"""
    if not expires_at_str:
        return None
    try:
        # 尝试解析带时区的ISO格式
        if expires_at_str.endswith("Z"):
            expires_at_str = expires_at_str[:-1] + "+00:00"
        return datetime.fromisoformat(expires_at_str)
    except (ValueError, TypeError):
        return None


# ========== 邀请码管理 ==========


@router.post("/admin/invite-codes")
async def admin_create_invite_code(
    req: CreateInviteCodeRequest,
    auth: AuthUser = Depends(require_admin),
):
    """创建新的邀请码，可选初始额度。

    如果提供了初始额度参数，在创建邀请码后会自动为该邀请码创建配额记录。
    """
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))

        # 创建邀请码
        created_code = await create_invite_code(
            conn=conn,
            code=req.code,
            description=req.description,
            max_uses=req.max_uses,
            created_by=auth.code,
        )

        # 如果提供了初始额度，创建并设置配额
        if (
            req.initial_tokens > 0
            or req.initial_requests > 0
            or req.initial_chapters > 0
        ):
            await ensure_user_quota_exists(conn, created_code)
            await set_user_quota(
                conn=conn,
                code=created_code,
                total_tokens=req.initial_tokens,
                total_requests=req.initial_requests,
                chapter_quota=req.initial_chapters,
                plan_type=req.plan_type,
                expires_at=None,
            )

        await conn.commit()

        return {
            "ok": True,
            "code": created_code,
            "message": f"邀请码 {created_code} 创建成功",
        }
    except ValueError as e:
        # 邀请码已存在等验证错误
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.error("创建邀请码失败: %s", e, exc_info=True)
        return {"ok": False, "error": f"创建邀请码失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


@router.get("/admin/invite-codes")
async def admin_list_invite_codes(
    auth: AuthUser = Depends(require_admin),
):
    """列出所有邀请码及其使用状态。"""
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))
        codes = await list_invite_codes(conn)

        return {"ok": True, "data": codes}
    except Exception as e:
        logger.error("列出邀请码失败: %s", e, exc_info=True)
        return {"ok": False, "error": f"列出邀请码失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


@router.delete("/admin/invite-codes/{code}")
async def admin_delete_invite_code(
    code: str,
    auth: AuthUser = Depends(require_admin),
):
    """删除邀请码及其配额记录（硬删除）。"""
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))
        success = await delete_invite_code(conn, code)
        await conn.commit()

        if success:
            return {"ok": True, "message": f"邀请码 {code} 已删除"}
        else:
            return {"ok": False, "error": f"邀请码 {code} 不存在或删除失败"}
    except Exception as e:
        logger.error("删除邀请码 %s 失败: %s", code, e, exc_info=True)
        return {"ok": False, "error": f"删除邀请码失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


@router.post("/admin/invite-codes/{code}/deactivate")
async def admin_deactivate_invite_code(
    code: str,
    auth: AuthUser = Depends(require_admin),
):
    """禁用邀请码（软删除），禁用后该邀请码无法继续使用。"""
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))
        success = await deactivate_invite_code(conn, code)
        await conn.commit()

        if success:
            return {"ok": True, "message": f"邀请码 {code} 已禁用"}
        else:
            return {"ok": False, "error": f"邀请码 {code} 不存在或禁用失败"}
    except Exception as e:
        logger.error("禁用邀请码 %s 失败: %s", code, e, exc_info=True)
        return {"ok": False, "error": f"禁用邀请码失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


# ========== 用户额度管理 ==========


@router.get("/admin/users/{code}/quota")
async def admin_get_user_quota(
    code: str,
    auth: AuthUser = Depends(require_admin),
):
    """查询指定邀请码的额度详情。"""
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))
        quota = await get_user_quota(conn, code)

        if quota is None:
            return {"ok": False, "error": f"邀请码 {code} 的配额记录不存在"}

        return {"ok": True, "data": quota}
    except Exception as e:
        logger.error("查询用户 %s 额度失败: %s", code, e, exc_info=True)
        return {"ok": False, "error": f"查询额度失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


@router.post("/admin/users/{code}/quota")
async def admin_set_user_quota(
    code: str,
    req: SetQuotaRequest,
    auth: AuthUser = Depends(require_admin),
):
    """设置用户配额（覆盖式）。

    会将指定邀请码的配额完全替换为请求中的值。
    管理员账号（total_tokens=0）不受额度限制。
    """
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))

        # 确保配额记录存在
        await ensure_user_quota_exists(conn, code)

        # 解析过期时间
        expires_at = _parse_expires_at(req.expires_at)

        await set_user_quota(
            conn=conn,
            code=code,
            total_tokens=req.total_tokens,
            total_requests=req.total_requests,
            chapter_quota=req.chapter_quota,
            plan_type=req.plan_type,
            expires_at=expires_at,
        )
        await conn.commit()

        return {
            "ok": True,
            "message": f"邀请码 {code} 的配额已更新",
        }
    except Exception as e:
        logger.error("设置用户 %s 额度失败: %s", code, e, exc_info=True)
        return {"ok": False, "error": f"设置额度失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


@router.post("/admin/users/{code}/quota/add")
async def admin_add_user_quota(
    code: str,
    req: AddQuotaRequest,
    auth: AuthUser = Depends(require_admin),
):
    """为用户增加配额（充值）。

    在现有配额基础上增加指定的tokens、requests和chapters数量。
    """
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))

        # 确保配额记录存在
        await ensure_user_quota_exists(conn, code)

        await add_user_quota(
            conn=conn,
            code=code,
            tokens=req.tokens,
            requests=req.requests,
            chapters=req.chapters,
        )
        await conn.commit()

        return {
            "ok": True,
            "message": (
                f"已为邀请码 {code} 增加额度: "
                f"tokens +{req.tokens}, requests +{req.requests}, chapters +{req.chapters}"
            ),
        }
    except Exception as e:
        logger.error("为用户 %s 增加额度失败: %s", code, e, exc_info=True)
        return {"ok": False, "error": f"增加额度失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


# ========== 使用日志和统计 ==========


@router.get("/admin/users/{code}/usage")
async def admin_get_user_usage(
    code: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    auth: AuthUser = Depends(require_admin),
):
    """查询指定邀请码的使用日志。

    返回该用户的API调用记录，支持分页。
    """
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))
        logs = await get_user_usage_logs(
            conn=conn,
            code=code,
            limit=limit,
            offset=offset,
        )

        return {"ok": True, "data": logs, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("查询用户 %s 使用日志失败: %s", code, e, exc_info=True)
        return {"ok": False, "error": f"查询使用日志失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()


@router.get("/admin/usage-summary")
async def admin_get_usage_summary(
    auth: AuthUser = Depends(require_admin),
):
    """获取全局使用统计摘要。

    返回系统级别的使用情况统计，包括总调用次数、token消耗等。
    """
    conn = None
    try:
        conn = await get_connection(str(settings.db_full_path))
        summary = await get_usage_summary(conn)

        return {"ok": True, "data": summary}
    except Exception as e:
        logger.error("获取使用统计摘要失败: %s", e, exc_info=True)
        return {"ok": False, "error": f"获取使用统计失败: {e}"}
    finally:
        if conn is not None:
            await conn.close()
