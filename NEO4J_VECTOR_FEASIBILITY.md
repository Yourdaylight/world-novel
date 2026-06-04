# Neo4j 5.x 向量索引替代 Qdrant 技术可行性分析

> 分析日期: 2026-06-04 | 基于 Neo4j 5.23+ 向量索引能力

---

## 一、一句话结论

**技术上可行，但这是一场"统一架构"与"极致性能"的权衡。**

对于 world-novel 项目，有一个独特的加分项——**角色关系图谱 + 记忆向量检索天然可以融合查询**（这在 Qdrant 中做不到）。

---

## 二、Neo4j 5.x 向量索引技术能力

### 2.1 核心能力清单

| 能力 | Neo4j 5.23+ | world-novel 需求 | 匹配度 |
|------|-------------|-----------------|--------|
| HNSW 索引 | ✅ Apache Lucene HNSW | semantic/episodic 检索 | ✅ 满足 |
| 最大维度 | 4096 维 | 512 维 (bge-small) | ✅ 绰绰有余 |
| 相似度函数 | Cosine, Euclidean | Cosine | ✅ 满足 |
| 向量量化 | ✅ 5.23+ 支持 | 可选加速 | ✅ 加分 |
| HNSW 参数调优 | hnsw.m, hnsw.ef_construction | 调优空间 | ⚠️ 有限 |
| Payload 过滤 | Cypher WHERE 子句 | character_id + heat_score | ✅ 满足 |
| 节点向量索引 | ✅ 节点属性 | 角色记忆节点 | ✅ 天然匹配 |
| 关系向量索引 | ✅ 5.18+ 支持 | 关系语义 | 🎁 新增能力 |
| 事务支持 | ✅ ACID | 一致性 | ✅ 优于 Qdrant |

### 2.2 Neo4j 向量索引 Cypher 示例

```cypher
-- 创建向量索引
CREATE VECTOR INDEX memory_embedding_idx
FOR (m:Memory)
ON m.embedding
OPTIONS {indexConfig: {
    `vector.quantization.enabled`: true,
    `vector.hnsw.m`: 16,
    `vector.hnsw.ef_construction`: 100
}};

-- 带过滤的向量搜索
CALL db.index.vector.queryNodes(
    'memory_embedding_idx',
    5,  -- top_k
    $query_embedding
) YIELD node, score
WHERE node.character_id = $character_id
  AND node.heat_score >= 0.1
RETURN node.memory_id, node.content, score;

-- 🎁 混合查询：向量相似度 + 图遍历（Qdrant做不到）
CALL db.index.vector.queryNodes(
    'memory_embedding_idx',
    10,
    $query_embedding
) YIELD node, score
MATCH (node)<-[:HAS_MEMORY]-(c:Character)
MATCH (c)-[r:RELATES_TO]->(other:Character)
WHERE r.strength > 0.7
RETURN c.name, node.content, score, other.name as related_to
ORDER BY score DESC;
```

---

## 三、当前 Qdrant 使用方式映射

### 3.1 代码接口对比

当前 `VectorMemoryStore`（Qdrant）有 8 个核心方法：

| 方法 | Qdrant 实现 | Neo4j 实现 | 复杂度 |
|------|------------|-----------|--------|
| `init_collections()` | create_collection × 3 | CREATE VECTOR INDEX × 3 | 低 |
| `upsert_semantic()` | PointStruct + upsert | MERGE + SET embedding | 低 |
| `search_semantic()` | search + payload filter | CALL queryNodes + WHERE | 中 |
| `upsert_episodic()` | PointStruct + upsert | MERGE + SET embedding | 低 |
| `search_episodic()` | search + heat filter | CALL queryNodes + WHERE | 中 |
| `upsert_world_knowledge()` | PointStruct + upsert | MERGE + SET embedding | 低 |
| `update_heat_score()` | set_payload | SET node.heat_score | 低 |
| `delete_point()` | delete | DELETE node | 低 |

**结论**: 所有方法都有对应的 Neo4j 实现，不存在功能缺口。

### 3.2 数据模型重构建议

当前 Qdrant 是"扁平集合"模型，Neo4j 可以用"图谱+向量"模型：

```
Qdrant 模型（当前）:
  Collection: semantic_memories
  Collection: episodic_memories  
  Collection: world_knowledge
  （三者独立，无关联）

Neo4j 模型（建议）:
  (:Character)-[:HAS_MEMORY]->(:Memory {embedding: vector})
  (:Character)-[:KNOWS]->(:WorldKnowledge {embedding: vector})
  (:Memory)-[:RELATED_TO]->(:Memory)  ← 语义关联
  
  Index: :Memory(embedding)  — HNSW
  Index: :WorldKnowledge(embedding)  — HNSW
```

---

## 四、关键权衡对比

### 4.1 性能对比（学术研究数据）

| 指标 | Qdrant（专用向量DB） | Neo4j 5.x（图DB+HNSW） | 差距 |
|------|---------------------|----------------------|------|
| 向量检索延迟 | 1-3ms | 3-10ms | Neo4j 慢 2-5 倍 |
| HNSW 索引构建 | 基准 | 慢 5-6 倍 | Neo4j 慢显著 |
| 吞吐量（QPS） | 基准 | 低 3-5 倍 | Neo4j 低显著 |
| 混合查询（向量+图） | ❌ 不支持 | ✅ 原生支持 | Neo4j 独有 |
| 数据量 < 10万条 | 极快 | 快 | 差距可忽略 |
| 数据量 > 100万条 | 快 | 中等 | 差距明显 |

> 数据来源：TigerVector 论文（2025）、Forrester Wave Vector DB（2024）、清华大学 VDBMS 教程

### 4.2 world-novel 场景特殊性

**关键问题：我们的向量数据量有多大？**

```
一本小说:
  - 角色数: 5-20 个
  - 每角色语义记忆: 20-50 条
  - 每角色情节记忆: 50-200 条
  - 世界知识: 10-30 条
  → 单本总向量数: 500-5000 条

100 本小说:
  → 总向量数: 5万-50万条
  
512 维 float32 向量:
  → 50万条 ≈ 1GB 存储
```

**结论**: world-novel 的向量规模在 **< 100万条** 级别，这个量级下：
- Qdrant 和 Neo4j 的检索延迟差距 **可忽略**（都在 10ms 以内）
- HNSW 构建时间差距 **可忽略**（都在秒级）
- **性能不是决定性因素**

---

## 五、独特优势（Neo4j 独有的能力）

### 5.1 混合查询：向量相似度 + 图关系

这是 Qdrant 完全做不到的，对小说场景非常有价值：

```cypher
-- 场景1: 找语义相似的记忆，同时考虑角色关系亲疏
CALL db.index.vector.queryNodes('memory_idx', 10, $emb) YIELD node, score
MATCH (node)<-[:HAS_MEMORY]-(char:Character)
MATCH (char)-[r:RELATES_TO]->({character_id: $target_char})
RETURN node.content, score, r.strength as relationship_strength
ORDER BY score * r.strength DESC;  -- 综合排序

-- 场景2: 找与某记忆语义相似的"其他角色"的记忆
CALL db.index.vector.queryNodes('memory_idx', 5, $emb) YIELD node, score
MATCH (node)<-[:HAS_MEMORY]-(other:Character)
WHERE other.character_id <> $self_char
RETURN other.name, node.content, score;

-- 场景3: 沿关系图谱传播记忆热度
MATCH (c:Character)-[r:RELATES_TO]-(other)
WHERE r.strength > 0.8
CALL db.index.vector.queryNodes('memory_idx', 3, $emb) YIELD node, score
MATCH (node)<-[:HAS_MEMORY]-(other)
RETURN node.content, score, r.strength;
```

### 5.2 统一存储的收益

| 维度 | Qdrant + Neo4j（当前） | Neo4j 统一（方案） |
|------|----------------------|-------------------|
| 服务数 | 2（+ SQLite = 3） | 1（+ SQLite = 2） |
| 连接管理 | 多套配置/连接池 | 一套 |
| 数据一致性 | 应用层保证 | 事务保证 |
| 备份策略 | 分别备份 | 统一备份 |
| 运维复杂度 | 中 | 低 |
| 混合查询 | ❌ 做不到 | ✅ 原生 |
| 内存占用 | 两者之和 | 单一（但 Neo4j 本身较重） |

---

## 六、劣势与风险

### 6.1 Neo4j 的劣势

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| HNSW 参数调优受限 | 🟡 中 | 不能调整 exploration factor |
| 索引构建慢 | 🟢 低 | 我们的数据量小，影响可忽略 |
| 内存占用大 | 🟡 中 | Neo4j 本身需 1-2GB，比 Qdrant 重 |
| 向量操作是"附加功能" | 🟡 中 | 长期演进可能不如专用向量DB |
| 社区版限制 | 🟢 低 | 单机足够，不需要集群 |

### 6.2 迁移工作量

| 任务 | 工作量 | 说明 |
|------|--------|------|
| 重写 VectorMemoryStore | 1-2 天 | 8个方法，Cypher 替代 Qdrant API |
| 数据模型设计 | 0.5 天 | 节点类型、关系类型、索引 |
| 数据迁移脚本 | 0.5 天 | Qdrant → Neo4j 一次性迁移 |
| 配置项调整 | 0.5 天 | 去掉 qdrant_*，复用 neo4j_* |
| 测试验证 | 1 天 | 功能+性能对比 |
| **总计** | **3-4 天** | |

---

## 七、推荐方案

### 方案A：保持现状（Qdrant + Neo4j 分离）⭐ 推荐（当前阶段）

**理由**:
- 已经工作，不需要投入迁移成本
- Qdrant 在向量检索上确实更快
- 当前向量数据量小，性能差距可忽略
- 可以专注于核心业务功能

### 方案B：Neo4j 统一存储（未来演进方向）

**适用时机**:
- 项目进入维护期，有技术债务重构窗口
- 发现混合查询（向量+图）有真实业务价值
- 运维复杂度成为痛点（多DB管理）

**预期收益**:
- 混合查询能力（向量+图联合检索）
- 统一事务（记忆写入+关系更新原子性）
- 减少一个服务，简化运维

### 方案C：渐进式融合（最务实的路径）

**步骤**:
```
Phase 1（现在）: 保持 Qdrant + Neo4j 分离，专注业务

Phase 2（6个月后）: 在 Neo4j 中建立 Memory 节点
  - 保留 Qdrant 做向量检索
  - Neo4j 只做关系图谱 + 混合查询的" enrich 层"
  
Phase 3（1年后）: 评估是否完全迁移
  - 如果混合查询价值大 → 迁移到 Neo4j 统一存储
  - 如果向量性能成瓶颈 → 保持 Qdrant
```

---

## 八、我的建议

**现在不做迁移，但在 Neo4j 中预留向量能力。**

具体行动:
1. ✅ 保持 Qdrant 做向量检索（性能更好）
2. ✅ Neo4j 继续做关系图谱（已工作）
3. 🆕 在 Neo4j schema 中增加 `embedding` 属性（预留）
4. 🆕 未来需要混合查询时，可以基于 Neo4j 的向量索引做 enrich 层

**一句话：Qdrant 做"快"的向量检索，Neo4j 做"深"的图分析，两者互补而非替代。**

---

## 九、附录：如果决定迁移的代码框架

```python
# memory/neo4j_vector_store.py（概念实现）

class Neo4jVectorStore:
    """Neo4j-backed vector store replacing Qdrant."""
    
    def __init__(self, uri=None, user=None, password=None):
        from neo4j import AsyncGraphDatabase
        self._driver = AsyncGraphDatabase.driver(
            uri or settings.neo4j_uri,
            auth=(user or settings.neo4j_user, 
                  password or settings.neo4j_password)
        )
    
    async def search_semantic(self, character_id, query_embedding, top_k=5):
        """向量搜索 + payload filter — Cypher实现"""
        async with self._driver.session() as session:
            result = await session.run("""
                CALL db.index.vector.queryNodes(
                    'semantic_memory_idx', $top_k, $embedding
                ) YIELD node, score
                WHERE node.character_id = $char_id
                RETURN node.memory_id, node.content, 
                       node.category, node.importance, score
                ORDER BY score DESC
            """, top_k=top_k, embedding=query_embedding, 
                char_id=character_id)
            records = await result.data()
            return [{
                "memory_id": r["node.memory_id"],
                "content": r["node.content"],
                "score": r["score"],
            } for r in records]
```
