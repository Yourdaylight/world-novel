# 数据库抽象层设计方案

## 决策：SQLite + sqlite-vec → PG + pgvector 渐进式兼容

### 为什么要做

| 阶段 | 场景 | 最佳选择 | 原因 |
|------|------|---------|------|
| V4 本地版 / 开发者 | 单机、单用户、1-5 世界 | **SQLite + sqlite-vec** | 零运维、文件级隔离、离线可用 |
| V5 轻量 SaaS | 小规模多用户、<1000 世界 | **SQLite + sqlite-vec** | 仍然可行，每用户一目录 |
| V6 正式 SaaS | 大规模多用户、协作、分析 | **PG + pgvector** | 连接池、事务、跨世界查询、备份 |
| BYOK 本地部署 | 企业私有化 | **SQLite** | 客户不想运维 PG |

**结论**：两种后端长期都需要。SQLite 不会被淘汰（本地版永远需要），PG 不是替代而是新增。

### 怎么做：三步走

```
Phase A (V4) — 抽象接口 + sqlite-vec 升级
  ↓  改动量：中等，~3天
Phase B (V5) — PG 后端实现
  ↓  改动量：中等，~5天（有了接口后是填空题）
Phase C (V6) — 运行时切换 + 连接池
     改动量：小，~2天
```

---

## Phase A：抽象接口设计

### 核心思路

不做 ORM（太重），做**轻量级 Repository 接口**：

```
现在                              目标
─────                            ─────
Store → aiosqlite.Connection      Store → DatabaseAdapter (Protocol)
                                          ├── SQLiteAdapter
                                          └── PostgresAdapter
```

### 接口定义

```python
# src/novel_creator/memory/adapters/protocol.py

from __future__ import annotations
from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class DatabaseAdapter(Protocol):
    """数据库适配器协议 — SQLite 和 PG 都实现这个接口"""

    async def execute(self, sql: str, params: tuple = ()) -> Any:
        """执行写操作（INSERT/UPDATE/DELETE）"""
        ...

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """查询单条"""
        ...

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """查询多条"""
        ...

    async def execute_script(self, sql: str) -> None:
        """执行多条 SQL（建表等）"""
        ...

    async def commit(self) -> None:
        """提交事务"""
        ...

    async def close(self) -> None:
        """关闭连接"""
        ...


@runtime_checkable
class VectorAdapter(Protocol):
    """向量搜索适配器 — sqlite-vec 和 pgvector 都实现这个"""

    async def vector_insert(
        self,
        table: str,
        id: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        ...

    async def vector_search(
        self,
        table: str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_sql: str = "",
        filter_params: tuple = (),
    ) -> list[tuple[str, float, dict]]:
        """返回 [(id, score, metadata), ...]"""
        ...
```

### SQLite 适配器实现

```python
# src/novel_creator/memory/adapters/sqlite_adapter.py

import aiosqlite
import numpy as np
from .protocol import DatabaseAdapter, VectorAdapter


class SQLiteAdapter:
    """SQLite + sqlite-vec 适配器"""

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def execute(self, sql: str, params: tuple = ()):
        return await self._conn.execute(sql, params)

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def execute_script(self, sql: str) -> None:
        await self._conn.executescript(sql)

    async def commit(self) -> None:
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()


class SQLiteVecAdapter:
    """sqlite-vec 向量搜索（替代当前的 NumPy 暴力扫描）"""

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def _ensure_vec_table(self, table: str, dimensions: int):
        # sqlite-vec 虚拟表
        await self._conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {table}_vec
            USING vec0(embedding float[{dimensions}])
        """)

    async def vector_insert(self, table, id, embedding, metadata):
        # 写入主表 + vec 虚拟表
        emb_bytes = np.array(embedding, dtype=np.float32).tobytes()
        await self._conn.execute(
            f"INSERT OR REPLACE INTO {table}_vec(rowid, embedding) VALUES (?, ?)",
            (hash(id) & 0x7FFFFFFFFFFFFFFF, emb_bytes),
        )

    async def vector_search(self, table, query_embedding, top_k=5,
                            filter_sql="", filter_params=()):
        emb_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        rows = await self._conn.execute(f"""
            SELECT rowid, distance
            FROM {table}_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        """, (emb_bytes, top_k))
        return [(r[0], 1.0 - r[1], {}) for r in await rows.fetchall()]


class SQLiteFallbackVecAdapter:
    """无 sqlite-vec 时的降级方案（当前的 NumPy 暴力扫描，保持兼容）"""

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def vector_search(self, table, query_embedding, top_k=5,
                            filter_sql="", filter_params=()):
        query_emb = np.array(query_embedding, dtype=np.float32)
        sql = f"SELECT memory_id, embedding FROM {table}"
        if filter_sql:
            sql += f" WHERE {filter_sql}"
        cursor = await self._conn.execute(sql, filter_params)
        rows = await cursor.fetchall()

        results = []
        for row in rows:
            stored = np.frombuffer(row["embedding"], dtype=np.float32)
            norm_a, norm_b = np.linalg.norm(query_emb), np.linalg.norm(stored)
            score = float(np.dot(query_emb, stored) / (norm_a * norm_b)) if norm_a and norm_b else 0.0
            results.append((row["memory_id"], score, {}))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
```

### PG 适配器实现（Phase B 填空）

```python
# src/novel_creator/memory/adapters/pg_adapter.py (V5/V6 实现)

import asyncpg
from .protocol import DatabaseAdapter, VectorAdapter


class PostgresAdapter:
    """PostgreSQL 适配器"""

    def __init__(self, pool: asyncpg.Pool, world_schema: str = "public"):
        self._pool = pool
        self._schema = world_schema  # 用 schema 做世界隔离

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        # 注意: PG 用 $1, $2 而不是 ?
        pg_sql = self._convert_placeholders(sql)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(pg_sql, *params)
            return [dict(r) for r in rows]
    ...


class PgVectorAdapter:
    """pgvector 向量搜索"""

    async def vector_search(self, table, query_embedding, top_k=5,
                            filter_sql="", filter_params=()):
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT id, 1 - (embedding <=> $1) as score, metadata
                FROM {self._schema}.{table}
                {f'WHERE {filter_sql}' if filter_sql else ''}
                ORDER BY embedding <=> $1
                LIMIT $2
            """, query_embedding, top_k)
            return [(r["id"], r["score"], r["metadata"]) for r in rows]
```

### SQL 方言差异处理

```python
# src/novel_creator/memory/adapters/dialect.py

class SQLDialect:
    """处理 SQLite vs PG 的语法差异"""

    def __init__(self, backend: str):
        self.backend = backend  # "sqlite" | "postgres"

    def placeholder(self, index: int) -> str:
        """SQLite: ? | PG: $1"""
        return "?" if self.backend == "sqlite" else f"${index}"

    def upsert(self, table: str, columns: list[str], conflict_col: str) -> str:
        """SQLite: INSERT OR REPLACE | PG: ON CONFLICT DO UPDATE"""
        if self.backend == "sqlite":
            cols = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            return f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        else:
            cols = ", ".join(columns)
            placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c != conflict_col)
            return (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_col}) DO UPDATE SET {updates}")

    def auto_timestamp(self) -> str:
        """SQLite: CURRENT_TIMESTAMP | PG: NOW()"""
        return "CURRENT_TIMESTAMP" if self.backend == "sqlite" else "NOW()"

    def json_type(self) -> str:
        """SQLite: TEXT | PG: JSONB"""
        return "TEXT" if self.backend == "sqlite" else "JSONB"

    def blob_type(self) -> str:
        """SQLite: BLOB | PG: BYTEA"""
        return "BLOB" if self.backend == "sqlite" else "BYTEA"

    def vector_type(self, dim: int) -> str:
        """SQLite: BLOB | PG: vector(dim)"""
        return "BLOB" if self.backend == "sqlite" else f"vector({dim})"
```

---

## Store 改造示例

### 改造前（当前代码）

```python
class SemanticStore:
    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn          # ← 硬绑定 aiosqlite
        self.character_id = character_id

    async def search(self, query: str, top_k=5):
        cursor = await self.conn.execute(...)  # ← 直接用 aiosqlite API
```

### 改造后

```python
class SemanticStore:
    def __init__(self, db: DatabaseAdapter, vec: VectorAdapter, character_id: str):
        self.db = db              # ← 依赖抽象接口
        self.vec = vec            # ← 向量搜索抽象
        self.character_id = character_id

    async def search(self, query: str, top_k=5):
        query_emb = embed_texts([query])[0]
        results = await self.vec.vector_search(
            table="semantic_memories",
            query_embedding=query_emb,
            top_k=top_k,
            filter_sql="character_id = ?",
            filter_params=(self.character_id,),
        )
        # 再从主表取完整数据
        ...
```

**其他 9 个 Store 改动量很小**（它们不涉及向量，只需把 `self.conn.execute(...)` 换成 `self.db.fetch_all(...)`）。

---

## PG 下的世界隔离方案

### 方案对比

| 方案 | SQLite 模式 | PG Schema 模式 | PG 行级隔离 |
|------|------------|---------------|------------|
| 隔离单元 | 一个 .db 文件 | 一个 PG Schema | 每行 world_id |
| 创建世界 | 创建文件 | `CREATE SCHEMA world_xxx` | 写入 world_id |
| 删除世界 | 删除文件 | `DROP SCHEMA world_xxx CASCADE` | 按 world_id 删 |
| 跨世界查询 | 不可能 | 可以（切换 search_path） | 天然支持 |
| 备份 | 复制文件 | pg_dump --schema | 按 world_id 导出 |
| 分支世界 | 复制文件 | 复制 schema | 复制行 |
| **推荐** | ✅ 本地版 | ✅ SaaS 版 | ❌ 污染查询 |

**推荐 PG 方案：Schema 隔离**
- 每个世界一个 PG Schema（如 `world_abc123`）
- 建表语句完全一样，只是在不同 schema 下
- `SET search_path TO world_abc123` 切换上下文
- 和 SQLite "每世界一个文件" 的心智模型完全一致

---

## 配置扩展

```python
# config.py 扩展

class Settings(BaseSettings):
    # 数据库后端
    db_backend: str = "sqlite"                  # "sqlite" | "postgres"
    db_path: str = "data/novel.db"              # SQLite 路径
    pg_dsn: str = ""                            # PG 连接串 (仅 pg 模式)
    # e.g. "postgresql://user:pass@localhost:5432/worldengine"

    # 向量搜索
    vec_backend: str = "numpy"                  # "numpy" | "sqlite-vec" | "pgvector"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
```

### 工厂函数

```python
# src/novel_creator/memory/adapters/factory.py

async def create_adapter(
    backend: str,
    db_path: str | None = None,
    pg_dsn: str | None = None,
    world_id: str | None = None,
) -> tuple[DatabaseAdapter, VectorAdapter]:
    """根据配置创建适配器对"""

    if backend == "sqlite":
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        db = SQLiteAdapter(conn)
        # 尝试加载 sqlite-vec，失败则降级
        try:
            await conn.enable_load_extension(True)
            await conn.load_extension("vec0")
            vec = SQLiteVecAdapter(conn)
        except Exception:
            vec = SQLiteFallbackVecAdapter(conn)
        return db, vec

    elif backend == "postgres":
        import asyncpg
        pool = await asyncpg.create_pool(pg_dsn)
        schema = f"world_{world_id}" if world_id else "public"
        db = PostgresAdapter(pool, schema)
        vec = PgVectorAdapter(pool, schema)
        return db, vec
```

---

## 迁移路径（影响最小化）

### 改动文件清单

| 文件 | 改动类型 | 工作量 |
|------|---------|--------|
| `memory/adapters/__init__.py` | 新增 | — |
| `memory/adapters/protocol.py` | 新增 | 0.5d |
| `memory/adapters/sqlite_adapter.py` | 新增 | 1d |
| `memory/adapters/pg_adapter.py` | 新增（V5） | 2d |
| `memory/adapters/dialect.py` | 新增 | 0.5d |
| `memory/adapters/factory.py` | 新增 | 0.5d |
| `memory/database.py` | 小改 | 0.5d |
| `memory/semantic_store.py` | 中改 | 0.5d |
| `memory/episodic_store.py` | 小改 | 0.25d |
| `memory/emotional_store.py` | 小改 | 0.25d |
| `memory/relationship_store.py` | 小改 | 0.25d |
| `memory/character_memory.py` | 小改 | 0.25d |
| 其他 5 个 store | 小改 | 1d |
| `config.py` | 小改 | 0.25d |
| `graph/nodes.py` | 小改 | 0.5d |
| `web/routes.py` | 小改 | 0.5d |

**Phase A 总工作量：~3-4 天**（抽象接口 + SQLite 实现 + 所有 Store 迁移）
**Phase B 追加：~3 天**（PG 实现 + Schema 隔离 + 测试）

---

## 不建议的方案

### ❌ 上 SQLAlchemy / Tortoise ORM
- 当前 SQL 都很简单直接，ORM 反而增加复杂度
- 向量搜索 ORM 支持差
- 运行时开销不必要

### ❌ 现在就全面切 PG
- 本地版/开发者版永远需要 SQLite（零运维）
- BYOK 用户不想装 PG
- "每世界一个文件" 的可移植性是产品优势
