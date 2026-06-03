#!/usr/bin/env python3
"""
world-novel 数据库迁移工具

用法:
    python scripts/migrations/migrate.py          # 执行所有待执行迁移
    python scripts/migrations/migrate.py status   # 查看迁移状态
    python scripts/migrations/migrate.py create   # 创建新迁移模板

设计原则:
    - 轻量级: 零外部依赖（只用标准库 + aiosqlite）
    - 可追溯: 每次迁移记录到 _migrations 表
    - 事务安全: 每个迁移在一个事务中执行
    - 显式错误: 失败时抛出异常并回滚，不静默吞错
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 将项目根目录加入路径，以便导入 novel_creator
PROJECT_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import aiosqlite

from novel_creator.config import settings

MIGRATIONS_DIR = Path(__file__).parent
DB_PATH = settings.db_path


# ── 迁移记录表 ──────────────────────────────────────

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT
);
"""


# ── 核心函数 ────────────────────────────────────────

async def init_migration_table(conn: aiosqlite.Connection) -> None:
    """初始化迁移记录表。"""
    await conn.execute(_CREATE_MIGRATIONS_TABLE)
    await conn.commit()


async def get_applied_migrations(conn: aiosqlite.Connection) -> set[str]:
    """获取已执行的迁移文件名集合。"""
    try:
        cursor = await conn.execute("SELECT filename FROM _migrations")
        rows = await cursor.fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def get_available_migrations() -> list[Path]:
    """获取所有可用的迁移文件，按编号排序。"""
    sql_files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    return sql_files


def compute_checksum(filepath: Path) -> str:
    """计算文件SHA256校验和。"""
    import hashlib

    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


async def apply_migration(conn: aiosqlite.Connection, filepath: Path) -> None:
    """执行单个迁移文件。"""
    filename = filepath.name
    sql = filepath.read_text(encoding="utf-8")

    print(f"  Applying {filename}...", end=" ", flush=True)

    async with conn.execute("BEGIN"):
        # 执行迁移SQL
        await conn.executescript(sql)

        # 记录迁移
        checksum = compute_checksum(filepath)
        await conn.execute(
            "INSERT INTO _migrations (filename, checksum) VALUES (?, ?)",
            (filename, checksum),
        )

    print("OK")


async def migrate(db_path: str | None = None) -> None:
    """执行所有待执行的迁移。"""
    path = db_path or DB_PATH

    print(f"Database: {path}")
    print(f"Migrations dir: {MIGRATIONS_DIR}")
    print("")

    conn = await aiosqlite.connect(str(path))
    conn.row_factory = aiosqlite.Row

    try:
        # WAL mode（与主应用一致）
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=30000")
        await conn.execute("PRAGMA synchronous=NORMAL")

        # 初始化迁移表
        await init_migration_table(conn)

        # 获取已执行和待执行的迁移
        applied = await get_applied_migrations(conn)
        available = get_available_migrations()

        if not available:
            print("No migration files found.")
            return

        pending = [m for m in available if m.name not in applied]

        if not pending:
            print(f"All {len(applied)} migrations are up to date.")
            return

        print(f"Pending migrations: {len(pending)}")
        print("")

        # 按顺序执行
        for filepath in pending:
            await apply_migration(conn, filepath)

        print("")
        print(f"Done. Applied {len(pending)} migration(s).")

    except Exception as e:
        print(f"FAILED: {e}")
        raise
    finally:
        await conn.close()


async def status(db_path: str | None = None) -> None:
    """显示迁移状态。"""
    path = db_path or DB_PATH

    conn = await aiosqlite.connect(str(path))
    conn.row_factory = aiosqlite.Row

    try:
        await init_migration_table(conn)
        applied = await get_applied_migrations(conn)
        available = get_available_migrations()

        print(f"Database: {path}")
        print(f"Total migrations: {len(available)}")
        print(f"Applied: {len(applied)}")
        print(f"Pending: {len(available) - len(applied)}")
        print("")

        for filepath in available:
            marker = "✓" if filepath.name in applied else "○"
            print(f"  {marker} {filepath.name}")
    finally:
        await conn.close()


def create_migration(name: str) -> Path:
    """创建新的迁移文件模板。"""
    # 获取下一个编号
    existing = get_available_migrations()
    next_num = len(existing) + 1
    filename = f"{next_num:03d}_{name}.sql"
    filepath = MIGRATIONS_DIR / filename

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    content = f"""-- Migration {next_num:03d}: {name}
-- Created: {timestamp}

-- 在此添加迁移SQL
-- 注意: 每个迁移在一个事务中执行，失败会自动回滚

"""
    filepath.write_text(content, encoding="utf-8")
    print(f"Created: {filepath}")
    return filepath


# ── CLI ─────────────────────────────────────────────

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"

    if cmd == "migrate":
        asyncio.run(migrate())
    elif cmd == "status":
        asyncio.run(status())
    elif cmd == "create":
        name = sys.argv[2] if len(sys.argv) > 2 else "new_migration"
        create_migration(name)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
