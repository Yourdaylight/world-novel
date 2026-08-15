# 11 — 记忆框架增强方案：基于论文 4W Taxonomy

> 版本: 1.0 | 2026-04-02

---

## 1. 目标与范围

基于 *Survey on AI Memory* 论文的 4W Memory Taxonomy，针对 WorldEngine 当前三个核心缺陷，引入：

- **Qdrant**（向量数据库）替代 SQLite BLOB 向量存储
- **Neo4j**（图数据库）承载关系网络与知识图谱
- **记忆热度衰减层**（Memory Decay）模拟人类遗忘曲线

现有 SQLite 保留其事务性/结构化数据职责，不替换。

---

## 2. 当前痛点 → 论文对应缺陷

| 痛点 | 当前实现 | 论文定义的问题类型 |
|------|---------|----------------|
| 向量检索低效 | SQLite BLOB 全表扫描 cosine | `hoW` 维度：缺乏专用 Vector Storage |
| 关系推理无法多跳 | SQLite `relationships` 单表 | `hoW` 维度：缺乏 Graph Memory |
| 记忆无遗忘机制 | 只增不减，100章后堆积 | `hoW` 操作：缺乏 Forgetting / Consolidation |
| 情景记忆无向量检索 | 只能按时间/重要性线性查找 | `Which` 维度：Retrieve 能力单一 |
| 跨角色共享知识无路径 | 每角色完全隔离 | MAS 的 Task-level Memory Sharing 缺失 |

---

## 3. 新增存储后端

### 3.1 Qdrant — 向量记忆库

**覆盖范围**：`SemanticMemory` + `EpisodicMemory` 的语义检索层

```
Collections:
├── semantic_memories        # 语义记忆（知识/观察）
│     payload: {character_id, content, category, importance, chapter_index}
│     vector:  bge-small-zh-v1.5 (512 dim)
│
├── episodic_memories        # 情景记忆 —— 新增向量检索
│     payload: {character_id, content, importance, emotional_valence,
│               involved_characters, chapter_index, scene_index, heat_score}
│     vector:  bge-small-zh-v1.5 (512 dim)
│
└── world_knowledge          # 角色世界认知（新增全局检索支持）
      payload: {character_id, knowledge_type, knowledge_key, confidence, content}
      vector:  bge-small-zh-v1.5 (512 dim)
```

**替代逻辑**：
- `SemanticStore.search()` → 调用 Qdrant `semantic_memories` collection
- `EpisodicStore` 新增 `search_similar()` → 调用 Qdrant `episodic_memories` collection
- SQLite 中的 `semantic_memories.embedding BLOB` 字段废弃（数据迁移脚本提供）

**Qdrant 优势**：
- HNSW 索引，万级向量毫秒级检索（vs 当前全表扫描）
- 支持 payload 过滤（`character_id = X AND importance > 0.6`）
- 支持 `heat_score` 字段联合排序（向量相似 + 热度加权）

---

### 3.2 Neo4j — 关系与世界知识图谱

**覆盖范围**：`RelationshipStore` + `WorldKnowledgeStore` + 新增跨角色推理

```
Node Labels:
├── Character     {character_id, name, role}
├── Location      {name, description, controlling_faction}
├── Faction       {name, description, ideology, leader}
├── PowerSystem   {name, description}
├── Event         {event_id, chapter_index, title, description, importance}
└── Memory        {memory_id, content, chapter_index, importance}  # 关键记忆节点

Edge Types:
├── KNOWS          (Character)-[conf:0.8]->(Character)       # 关系强度
├── TRUSTS         (Character)-[val:0.6]->(Character)        # 信任度
├── HOSTILE_TO     (Character)->(Character)                  # 敌对
├── BELONGS_TO     (Character)->(Faction)                    # 所属势力
├── VISITED        (Character)-[ch:3]->(Location)            # 到过的地点
├── KNOWS_FACTION  (Character)-[conf:0.5]->(Faction)         # 对势力的认知
├── WITNESSED      (Character)->(Event)                      # 目睹事件
├── CAUSED         (Character)->(Event)                      # 引发事件
├── INVOLVED_IN    (Memory)->(Event)                         # 记忆与事件关联
└── ERA_CHANGE     (Event)-[reason]->(Relationship)          # 事件改变关系
```

**替代逻辑**：
- `RelationshipStore.upsert()` → 同步写入 Neo4j `KNOWS/TRUSTS/HOSTILE_TO` 边
- `RelationshipStore.get_all()` → 从 Neo4j 查询（SQLite 保留为 fallback）
- 新增 `RelationshipStore.find_path(a, b)` → Neo4j 最短路径查询
- 新增 `RelationshipStore.get_common_contacts(a, b)` → 共同人物查询

**多跳推理示例**（现在无法做的查询）：
```cypher
// 主角的"敌人的敌人"是谁？
MATCH (me:Character {character_id: $cid})
      -[:HOSTILE_TO]->(enemy:Character)
      <-[:HOSTILE_TO]-(potential_ally:Character)
WHERE potential_ally.character_id <> $cid
RETURN potential_ally

// 某地点发生的重大事件，有哪些角色目睹？
MATCH (loc:Location {name: $loc_name})
      <-[:AT_LOCATION]-(ev:Event {importance: 1.0})
      <-[:WITNESSED]-(char:Character)
RETURN char, ev

// 某角色所知道的势力之间有什么关系？
MATCH (me:Character {character_id: $cid})-[:KNOWS_FACTION]->(f1:Faction)
MATCH (f1)-[r]-(f2:Faction)
RETURN f1, type(r), f2
```

---

### 3.3 记忆热度衰减层（Memory Heat System）

基于论文 MemoryOS 的 heat-based segmented paging 思路，专为小说叙事场景适配。

#### 3.3.1 热度模型

每条情景记忆维护一个 `heat_score`，初始值由重要性决定，随章节推进衰减：

```
heat_score(chapter) = base_importance × decay_factor^(current_chapter - origin_chapter)
                    + access_bonus × recent_access_count
```

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `decay_factor` | 0.92 | 每章衰减8%（类比 Ebbinghaus 遗忘曲线） |
| `access_bonus` | 0.15 | 每次被检索命中，热度+0.15 |
| `trauma_floor` | 0.6 | 创伤记忆最低热度下限（不会低于此值）|
| `consolidation_threshold` | 0.1 | 低于此值触发记忆合并/淘汰 |

#### 3.3.2 三层记忆分区

论文 MemoryOS 的 Short/Mid/Long-term 分层策略，映射到叙事场景：

```
Hot  (heat >= 0.5)  → 直接注入上下文 (最近3-5章的活跃记忆)
Warm (0.1-0.5)      → 向量检索按需唤起 (重要历史节点)
Cold (< 0.1)        → 合并压缩为"时代摘要"，存入 era_summary
Frozen              → 创伤记忆专区，永不淘汰但只在触发时注入
```

#### 3.3.3 记忆整合（Consolidation）

当 Cold 区记忆累积超过阈值（默认20条），触发整合：
1. 按 `era_id` 聚类 Cold 记忆
2. LLM 压缩摘要为 1 条 `era_memory`（保留核心事件）
3. 原始记忆从 Qdrant 软删除（标记 `consolidated=True`），SQLite 记录保留
4. `era_memory` 写入 `era_summaries` 表，作为"模糊回忆"注入上下文

---

## 4. 架构图：增强后存储职责划分

```
                        ┌────────────────────────────────────┐
                        │        CharacterMemory (Facade)     │
                        └──────────────┬─────────────────────┘
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          │                            │                             │
          ▼                            ▼                             ▼
  ┌──────────────┐           ┌──────────────────┐         ┌──────────────────┐
  │   SQLite     │           │     Qdrant        │         │     Neo4j        │
  │  (结构化事务) │           │  (向量检索层)     │         │  (图关系推理层)  │
  │              │           │                   │         │                  │
  │ • 角色档案   │           │ semantic_memories │         │ • 角色关系网络   │
  │ • 情感状态   │  同步写   │ episodic_memories │  同步写 │ • 势力关系图谱   │
  │ • 情景记忆   │ ────────▶ │ world_knowledge   │ ──────▶ │ • 地点-事件连接  │
  │ • 关系快照   │           │                   │         │ • 多跳推理查询   │
  │ • 世界认知   │           │  heat_score 字段   │         │                  │
  │ • 信念/创伤  │           │  payload 过滤      │         │                  │
  │ • 伏笔/章节  │           │  HNSW 近邻检索     │         │                  │
  └──────────────┘           └──────────────────┘         └──────────────────┘
        ▲                             ▲                             ▲
        │                             │                             │
        └─────────────────────────────┴─────────────────────────────┘
                                      │
                          MemoryRouter (路由层，新增)
                          决定从哪个后端读取
```

**SQLite 保留职责**（不变）：
- 事务性写入（章节生成原子操作）
- Checkpoint/恢复
- 伏笔/剧情线状态
- Token 统计
- 作为所有数据的 Source of Truth（Qdrant/Neo4j 是派生索引）

---

## 5. 新增组件设计

### 5.1 `memory/vector_store.py` — Qdrant 客户端封装

```python
class VectorMemoryStore:
    """Qdrant-backed vector search for semantic/episodic memories."""

    def __init__(self, host: str, port: int, collection_prefix: str = "worldengine"):
        ...

    async def upsert_semantic(self, memory: SemanticMemory) -> None:
        """写入或更新语义记忆向量"""

    async def upsert_episodic(self, memory: EpisodicMemory, heat: float) -> None:
        """写入情景记忆向量，带热度字段"""

    async def search_semantic(
        self, character_id: str, query: str,
        top_k: int = 5, min_importance: float = 0.0
    ) -> list[tuple[SemanticMemory, float]]:
        """语义检索 + payload 过滤"""

    async def search_episodic(
        self, character_id: str, query: str,
        top_k: int = 5, min_heat: float = 0.1
    ) -> list[tuple[EpisodicMemory, float]]:
        """情景记忆语义检索，只检索 heat >= min_heat 的记忆"""

    async def decay_and_consolidate(
        self, character_id: str, current_chapter: int
    ) -> list[str]:
        """衰减热度，返回待整合的 Cold 记忆 ID 列表"""
```

### 5.2 `memory/graph_store.py` — Neo4j 客户端封装

```python
class GraphMemoryStore:
    """Neo4j-backed relationship and knowledge graph."""

    def __init__(self, uri: str, auth: tuple[str, str]):
        ...

    # --- 关系操作 ---
    async def sync_relationship(self, rel: Relationship, chapter: int) -> None:
        """将 SQLite 关系同步到 Neo4j"""

    async def find_path(self, from_id: str, to_id: str, max_depth: int = 3) -> list[dict]:
        """两角色间的关系路径查询"""

    async def get_social_context(self, character_id: str) -> str:
        """生成社交环境摘要（朋友/中立/敌人 + 二度关系）"""

    # --- 知识图谱操作 ---
    async def sync_world_knowledge(self, character_id: str, entry: dict) -> None:
        """同步角色世界认知到知识图谱"""

    async def query_faction_network(self, character_id: str) -> str:
        """该角色视角的势力关系网络"""

    # --- 事件追踪 ---
    async def record_event(
        self, event_id: str, chapter: int,
        witnesses: list[str], caused_by: str | None = None
    ) -> None:
        """记录事件及涉及角色"""
```

### 5.3 `memory/memory_router.py` — 统一查询路由

```python
class MemoryRouter:
    """Routes memory queries to the appropriate backend.
    
    Priority:
    1. Hot memories → SQLite (direct)
    2. Semantic search → Qdrant
    3. Relationship paths → Neo4j
    4. Fallback → SQLite full scan
    """

    def __init__(
        self,
        sqlite_conn: aiosqlite.Connection,
        vector_store: VectorMemoryStore | None = None,
        graph_store: GraphMemoryStore | None = None,
    ):
        ...

    async def recall_relevant(
        self, character_id: str, query: str,
        chapter: int, top_k: int = 8,
    ) -> list[MemoryFragment]:
        """
        混合检索策略：
        1. SQLite: Hot 记忆 (近3章 + heat >= 0.5)
        2. Qdrant: 语义相关记忆 (heat 0.1-0.5 区间)
        3. SQLite: 创伤/信念（固定注入）
        4. Dedup + 按 heat × similarity 重排
        """

    async def get_relationship_context(
        self, character_id: str, present_characters: list[str],
    ) -> str:
        """
        如果 Neo4j 可用：返回 social_context + 多跳关系摘要
        否则：降级到 SQLite relationship_store
        """
```

---

## 6. `CharacterMemory` 改造

### 6.1 构造函数扩展（向后兼容）

```python
class CharacterMemory:
    def __init__(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        *,
        vector_store: VectorMemoryStore | None = None,   # 新增，可选
        graph_store: GraphMemoryStore | None = None,      # 新增，可选
    ):
        # 原有 stores 不变...
        self.router = MemoryRouter(conn, vector_store, graph_store)
```

**向后兼容**：`vector_store=None` 时自动降级到当前 SQLite 行为，无需改动现有调用代码。

### 6.2 `get_context_window()` 改造

```python
async def get_context_window(self, chapter: int, scene: int, *, timeline=None) -> str:
    parts = []
    
    # 1. 身份（不变）
    
    # 2. 记忆（改：使用 MemoryRouter 混合检索）
    query = f"第{chapter}章 场景{scene} 相关记忆"
    fragments = await self.router.recall_relevant(
        self.character_id, query, chapter, top_k=8
    )
    # 按热度分区展示
    hot = [f for f in fragments if f.heat >= 0.5]
    warm = [f for f in fragments if 0.1 <= f.heat < 0.5]
    ...
    
    # 3. 关系（改：Neo4j 多跳 or SQLite 降级）
    rel_context = await self.router.get_relationship_context(
        self.character_id, present_characters
    )
    
    # 4-7. 情感/信念/创伤/内心（不变）
```

---

## 7. 配置扩展（`config.py`）

```python
class Settings(BaseSettings):
    # 现有字段不变...

    # Qdrant (可选)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_enabled: bool = False          # 默认关闭，手动开启

    # Neo4j (可选)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_enabled: bool = False           # 默认关闭，手动开启

    # Memory Decay
    memory_decay_factor: float = 0.92    # 每章衰减系数
    memory_access_bonus: float = 0.15    # 被检索时热度增量
    memory_trauma_floor: float = 0.6     # 创伤记忆最低热度
    memory_cold_threshold: float = 0.1   # 进入 Cold 区的阈值
    memory_consolidate_count: int = 20   # Cold 区触发整合的条数
```

---

## 8. 数据库 Schema 变更（SQLite V10）

```sql
-- V10: 情景记忆新增热度字段
ALTER TABLE episodic_memories ADD COLUMN heat_score REAL DEFAULT 0.5;
ALTER TABLE episodic_memories ADD COLUMN last_accessed_chapter INTEGER DEFAULT 0;
ALTER TABLE episodic_memories ADD COLUMN access_count INTEGER DEFAULT 0;
ALTER TABLE episodic_memories ADD COLUMN consolidated INTEGER DEFAULT 0;

-- V10: 时代摘要表（Cold 区记忆整合后的压缩摘要）
CREATE TABLE IF NOT EXISTS era_summaries (
    summary_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    era_id TEXT DEFAULT '',
    chapter_start INTEGER NOT NULL,
    chapter_end INTEGER NOT NULL,
    summary TEXT NOT NULL,               -- LLM 压缩摘要
    source_memory_ids TEXT DEFAULT '[]', -- 被整合的记忆 ID 列表
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_era_summaries_char ON era_summaries(character_id);

-- V10: character_inner_agenda 已在 V5 手术中定义（确保存在）
CREATE TABLE IF NOT EXISTS character_inner_agenda (
    character_id TEXT PRIMARY KEY,
    agenda TEXT DEFAULT '',
    vigilance TEXT DEFAULT '',
    chapter_updated INTEGER DEFAULT 0,
    scene_updated INTEGER DEFAULT 0
);

-- V10: character_world_knowledge 已在 V5 手术中定义（确保存在）
CREATE TABLE IF NOT EXISTS character_world_knowledge (
    character_id TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,
    knowledge_key TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'backstory',
    confidence REAL DEFAULT 0.5,
    chapter_learned INTEGER DEFAULT 0,
    PRIMARY KEY (character_id, knowledge_type, knowledge_key)
);
```

---

## 9. Neo4j Schema（初始化 Cypher）

```cypher
// 约束
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Character) REQUIRE c.character_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (f:Faction) REQUIRE f.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

// 索引
CREATE INDEX IF NOT EXISTS FOR (c:Character) ON (c.name);
CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.chapter_index);
CREATE INDEX IF NOT EXISTS FOR ()-[r:KNOWS]-() ON (r.trust);
```

---

## 10. 实施阶段

### Phase 1 — 记忆热度衰减（纯 SQLite，无新依赖）⭐ 优先

**工作量**：约2天

1. `database.py`：SQLite V10 迁移（新增 `heat_score` 等字段）
2. `episodic_store.py`：新增 `update_heat()`, `get_hot()`, `get_cold()` 方法
3. `memory/heat_manager.py`：实现衰减计算和整合触发逻辑
4. `character_memory.py`：`get_context_window()` 按热度分区展示记忆
5. `agents/character.py`：场景结束后调用 `heat_manager.decay()`

**验证**：生成100章后，Hot区记忆不超过15条，Cold区自动整合成摘要。

---

### Phase 2 — Qdrant 向量检索升级⭐ 次优先

**工作量**：约3天

1. `pyproject.toml`：新增 `qdrant-client>=1.7`
2. `config.py`：新增 Qdrant 配置项
3. `memory/vector_store.py`：实现 `VectorMemoryStore`
4. `memory/semantic_store.py`：保留 SQLite 接口，检测 Qdrant 配置后路由
5. `memory/episodic_store.py`：新增 `search_similar()` 方法（走 Qdrant）
6. 迁移脚本：将现有 SQLite BLOB 向量迁移到 Qdrant
7. `memory/memory_router.py`：实现混合检索路由

**验证**：1000条语义记忆，检索延迟 < 50ms（vs 现在 ~200ms）。

---

### Phase 3 — Neo4j 关系图谱（长期）

**工作量**：约5天

1. `pyproject.toml`：新增 `neo4j>=5.0`
2. `config.py`：新增 Neo4j 配置项
3. `memory/graph_store.py`：实现 `GraphMemoryStore`
4. `memory/relationship_store.py`：写入时同步 Neo4j
5. `memory/world_knowledge_store.py`：learn() 时同步节点
6. `character_memory.py`：`get_context_window()` 关系部分使用 Neo4j
7. Web API：新增图谱可视化端点（供前端 vis-network 使用）

**验证**：能执行"主角的敌人的盟友是谁"类多跳查询。

---

## 11. 部署方案

### 本地开发（Docker Compose）

```yaml
# docker-compose.yml 新增
services:
  qdrant:
    image: qdrant/qdrant:v1.8.4
    ports:
      - "6333:6333"
    volumes:
      - ./data/qdrant:/qdrant/storage

  neo4j:
    image: neo4j:5.18-community
    environment:
      - NEO4J_AUTH=neo4j/worldengine
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt
    volumes:
      - ./data/neo4j:/data
```

### 环境变量（`.env`）

```bash
NOVEL_QDRANT_ENABLED=true
NOVEL_QDRANT_HOST=localhost
NOVEL_QDRANT_PORT=6333

NOVEL_NEO4J_ENABLED=true
NOVEL_NEO4J_URI=bolt://localhost:7687
NOVEL_NEO4J_PASSWORD=worldengine
```

### 最小运行（无新依赖）

```bash
NOVEL_QDRANT_ENABLED=false
NOVEL_NEO4J_ENABLED=false
# 完全降级到当前 SQLite 行为，所有功能正常
```

---

## 12. 新旧记忆检索对比

### 旧流程（`recall_relevant`）

```
query → embed → SQLite全表扫描余弦距离 → 取前5条
+ 最近3条情景记忆 (by chapter_index DESC)
+ 重要度>0.7的情景记忆 (by importance DESC)
= 简单合并，无权重，无遗忘
```

### 新流程（`MemoryRouter.recall_relevant`）

```
query
  │
  ├─→ [Hot区] SQLite: heat_score >= 0.5 的情景记忆（直接注入，3-5条）
  │
  ├─→ [语义] Qdrant: semantic_memories + episodic_memories HNSW检索
  │     filter: character_id = X AND heat_score > 0.1
  │     score: cosine_similarity × heat_score 加权
  │     top_k: 5条
  │
  ├─→ [图关系] Neo4j: 当前场景中出现的角色 → 补充关系路径摘要
  │     （非文本召回，直接结构化描述）
  │
  ├─→ [固定注入] SQLite: 创伤记忆 + 核心信念（不经检索，始终注入）
  │
  └─→ Dedup + Re-rank → 最终上下文（不超过12条）
```

---

## 13. 前端可视化扩展（Phase 3 附带）

Phase 3 完成后，可在前端新增：

- **关系图谱页**：调用 Neo4j 数据，用 `vis-network` 渲染角色关系网络（当前仅有静态快照，改为实时图谱）
- **记忆热度图**：显示每个角色的记忆热度分布（Hot/Warm/Cold 占比饼图）
- **知识扩散追踪**：某条世界知识"从哪个场景学到的"的传播路径可视化

---

## 14. 风险与取舍

| 风险 | 缓解方案 |
|------|---------|
| Qdrant/Neo4j 服务不可用 | 所有新组件设计为 Optional，`enabled=false` 自动降级 SQLite |
| Neo4j 写入延迟 | 关系同步改为异步后台任务，不阻塞角色行动 |
| 向量模型变更导致 Qdrant 失效 | 模型版本记录在 collection metadata，变更时重建 collection |
| 大量章节后 Neo4j 图谱膨胀 | 只保留近3个 Era 的活跃边，历史边 `active=false` 标记 |
| Phase 1 热度衰减影响现有测试 | heat_score 默认0.5，存量数据行为等同现在 |
