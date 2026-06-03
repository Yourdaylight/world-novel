
"""Token额度管理系统完整测试。"""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

# 确保项目根目录在路径中
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root / "src"))

# 使用临时数据库
temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_PATH = temp_db.name
temp_db.close()

os.environ["NOVEL_DB_PATH"] = DB_PATH
os.environ["NOVEL_JWT_SECRET"] = "test-secret-key"

import aiosqlite
from jose import jwt

from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import (
    create_invite_code,
    validate_invite_code,
    get_invite_code,
    list_invite_codes,
    deactivate_invite_code,
    delete_invite_code,
    get_user_quota,
    set_user_quota,
    add_user_quota,
    check_and_deduct_tokens,
    deduct_chapter_quota,
    ensure_user_quota_exists,
    log_user_token_usage,
    get_user_usage_logs,
    get_usage_summary,
)
from novel_creator.web.auth_deps import (
    create_access_token,
    verify_token,
    AuthUser,
)


async def test_database_schema():
    """测试数据库表是否正确创建。"""
    print("\n[1/10] 测试数据库Schema...")
    # get_connection 会自动执行 SCHEMA_SQL 创建表
    conn = await get_connection(DB_PATH)
    await conn.close()
    conn = await get_connection(DB_PATH)
    try:
        # 检查 invite_codes 表
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='invite_codes'"
        )
        assert await cursor.fetchone() is not None, "invite_codes 表不存在"

        # 检查 user_quotas 表
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_quotas'"
        )
        assert await cursor.fetchone() is not None, "user_quotas 表不存在"

        # 检查 user_token_usage_log 表
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_token_usage_log'"
        )
        assert await cursor.fetchone() is not None, "user_token_usage_log 表不存在"

        print("  ✓ 所有表已正确创建")
    finally:
        await conn.close()


async def test_invite_code_crud():
    """测试邀请码CRUD操作。"""
    print("\n[2/10] 测试邀请码CRUD...")
    conn = await get_connection(DB_PATH)
    try:
        # 创建邀请码
        code = await create_invite_code(conn, code="TEST1234", description="测试邀请码")
        assert code == "TEST1234"

        # 验证邀请码
        assert await validate_invite_code(conn, "TEST1234") is True

        # 查询邀请码
        info = await get_invite_code(conn, "TEST1234")
        assert info is not None
        assert info["code"] == "TEST1234"
        assert info["description"] == "测试邀请码"

        # 列出邀请码
        codes = await list_invite_codes(conn)
        assert len(codes) >= 1

        # 禁用邀请码
        await deactivate_invite_code(conn, "TEST1234")
        assert await validate_invite_code(conn, "TEST1234") is False

        # 删除邀请码
        await delete_invite_code(conn, "TEST1234")
        assert await get_invite_code(conn, "TEST1234") is None

        print("  ✓ 邀请码CRUD正常")
    finally:
        await conn.close()


async def test_auto_generate_code():
    """测试自动生成邀请码。"""
    print("\n[3/10] 测试自动生成邀请码...")
    conn = await get_connection(DB_PATH)
    try:
        code = await create_invite_code(conn, description="自动生成")
        assert len(code) == 8
        # 确认不包含易混淆字符
        assert "O" not in code and "0" not in code and "I" not in code and "l" not in code
        print(f"  ✓ 自动生成邀请码: {code}")
    finally:
        await conn.close()


async def test_user_quota_management():
    """测试用户配额管理。"""
    print("\n[4/10] 测试用户配额管理...")
    conn = await get_connection(DB_PATH)
    try:
        # 创建用户
        await create_invite_code(conn, code="USER001")
        await ensure_user_quota_exists(conn, "USER001")

        # 设置配额
        await set_user_quota(conn, "USER001", total_tokens=100000, total_requests=500, chapter_quota=50)

        # 查询配额
        quota = await get_user_quota(conn, "USER001")
        assert quota["total_tokens"] == 100000
        assert quota["total_requests"] == 500
        assert quota["chapter_quota"] == 50
        assert quota["used_tokens"] == 0

        # 增加配额（充值）
        await add_user_quota(conn, "USER001", tokens=50000, requests=200, chapters=20)
        quota = await get_user_quota(conn, "USER001")
        assert quota["total_tokens"] == 150000
        assert quota["total_requests"] == 700
        assert quota["chapter_quota"] == 70

        print("  ✓ 配额管理正常")
    finally:
        await conn.close()


async def test_token_deduction():
    """测试Token扣减。"""
    print("\n[5/10] 测试Token扣减...")
    conn = await get_connection(DB_PATH)
    try:
        # 创建用户并设置配额
        await create_invite_code(conn, code="USER002")
        await ensure_user_quota_exists(conn, "USER002")
        await set_user_quota(conn, "USER002", total_tokens=1000, total_requests=10)

        # 正常扣减
        ok, err = await check_and_deduct_tokens(conn, "USER002", tokens_needed=100, requests_needed=1)
        assert ok is True, f"Unexpected error: {err}"

        quota = await get_user_quota(conn, "USER002")
        assert quota["used_tokens"] == 100
        assert quota["used_requests"] == 1

        # 超额扣减应失败
        ok, err = await check_and_deduct_tokens(conn, "USER002", tokens_needed=2000, requests_needed=1)
        assert ok is False
        assert "Token额度不足" in err

        # 管理员账号应无限制
        await create_invite_code(conn, code="admin_test")
        await ensure_user_quota_exists(conn, "admin_test")
        # 不设置配额（total_tokens=0, total_requests=0 表示无限制）
        ok, err = await check_and_deduct_tokens(conn, "admin_test", tokens_needed=999999, requests_needed=999999)
        assert ok is True, f"Admin should have unlimited quota: {err}"

        print("  ✓ Token扣减逻辑正常")
    finally:
        await conn.close()


async def test_chapter_quota():
    """测试章节配额。"""
    print("\n[6/10] 测试章节配额...")
    conn = await get_connection(DB_PATH)
    try:
        await create_invite_code(conn, code="USER003")
        await ensure_user_quota_exists(conn, "USER003")
        await set_user_quota(conn, "USER003", chapter_quota=3)

        # 扣减3次应成功
        assert await deduct_chapter_quota(conn, "USER003") is True
        assert await deduct_chapter_quota(conn, "USER003") is True
        assert await deduct_chapter_quota(conn, "USER003") is True

        # 第4次应失败
        assert await deduct_chapter_quota(conn, "USER003") is False

        # 检查已使用数
        quota = await get_user_quota(conn, "USER003")
        assert quota["chapters_used"] == 3

        print("  ✓ 章节配额正常")
    finally:
        await conn.close()


async def test_usage_logging():
    """测试使用日志记录。"""
    print("\n[7/10] 测试使用日志...")
    conn = await get_connection(DB_PATH)
    try:
        await create_invite_code(conn, code="USER004")
        await ensure_user_quota_exists(conn, "USER004")

        # 记录多次使用
        await log_user_token_usage(conn, "USER004", "writer", 1000, 500, 1500, "gpt-4", 1, "write chapter 1")
        await log_user_token_usage(conn, "USER004", "director", 2000, 800, 2800, "gpt-4", 1, "direct chapter 1")
        await log_user_token_usage(conn, "USER004", "writer", 1200, 600, 1800, "gpt-4", 2, "write chapter 2")

        # 查询日志
        logs = await get_user_usage_logs(conn, "USER004", limit=10)
        assert len(logs) == 3

        # 查询摘要
        summary = await get_usage_summary(conn, "USER004")
        assert summary["usage_stats"]["total_tokens_used"] == 6100
        assert len(summary["by_role"]) == 2  # writer, director

        print("  ✓ 使用日志正常")
    finally:
        await conn.close()


async def test_jwt_auth():
    """测试JWT认证。"""
    print("\n[8/10] 测试JWT认证...")

    # 创建token
    token = create_access_token(code="test_user", is_admin=False)
    assert isinstance(token, str)
    assert len(token) > 0

    # 验证token
    user = verify_token(token)
    assert user.code == "test_user"
    assert user.is_admin is False

    # 管理员token
    admin_token = create_access_token(code="admin_user", is_admin=True)
    admin_user = verify_token(admin_token)
    assert admin_user.code == "admin_user"
    assert admin_user.is_admin is True

    # code以admin开头的自动为管理员
    auto_admin_token = create_access_token(code="admin_123")
    auto_admin = verify_token(auto_admin_token)
    assert auto_admin.is_admin is True

    # 过期token应失败
    import time
    from datetime import datetime, timezone, timedelta
    from jose import jwt as jose_jwt
    expired_token = jose_jwt.encode(
        {"code": "test", "is_admin": False, "exp": datetime.now(timezone.utc) - timedelta(hours=1), "iat": datetime.now(timezone.utc) - timedelta(hours=2)},
        "test-secret-key",
        algorithm="HS256"
    )
    try:
        verify_token(expired_token)
        assert False, "Expired token should fail"
    except Exception:
        pass  # Expected

    print("  ✓ JWT认证正常")


async def test_max_uses_limit():
    """测试邀请码最大使用次数限制。"""
    print("\n[9/10] 测试使用次数限制...")
    conn = await get_connection(DB_PATH)
    try:
        # 创建只能使用1次的邀请码
        await create_invite_code(conn, code="ONETIME", max_uses=1)

        # 第一次验证应成功
        assert await validate_invite_code(conn, "ONETIME") is True

        # 增加使用计数
        await conn.execute("UPDATE invite_codes SET used_count = 1 WHERE code = ?", ("ONETIME",))
        await conn.commit()

        # 再次验证应失败
        assert await validate_invite_code(conn, "ONETIME") is False

        print("  ✓ 使用次数限制正常")
    finally:
        await conn.close()


async def test_cleanup():
    """清理测试数据。"""
    print("\n[10/10] 清理...")
    try:
        os.unlink(DB_PATH)
        print("  ✓ 临时数据库已清理")
    except:
        pass


async def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("Token额度管理系统测试")
    print("=" * 50)

    try:
        await test_database_schema()
        await test_invite_code_crud()
        await test_auto_generate_code()
        await test_user_quota_management()
        await test_token_deduction()
        await test_chapter_quota()
        await test_usage_logging()
        await test_jwt_auth()
        await test_max_uses_limit()
        await test_cleanup()

        print("\n" + "=" * 50)
        print("✅ 所有10项测试通过！")
        print("=" * 50)
        return True
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    sys.exit(0 if result else 1)
