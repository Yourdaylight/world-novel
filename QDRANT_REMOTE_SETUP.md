# 远程 Qdrant 向量数据库部署方案

> 分析日期: 2026-06-04 | 目标: 将向量检索能力从主应用分离

---

## 一、好消息：代码已完全支持远程 Qdrant

当前代码架构天然支持远程部署，**不需要任何代码修改**:

```python
# config.py — 已支持通过环境变量配置远程地址
qdrant_host: str = "localhost"      # ← 改为远程IP
qdrant_port: int = 6333             # ← 改为远程端口
qdrant_api_key: str = ""            # ← 设置访问密钥
qdrant_enabled: bool = False        # ← 开启开关
```

### Fallback 机制（自动降级）

代码中已有完善的容错设计（`memory_router.py`）:

```
用户查询 → MemoryRouter.search()
  ├── 1. SQLite hot memories（本地，O(1)）
  ├── 2. Qdrant semantic search（远程，HNSW O(logN)）
  │     └── 如果 Qdrant 连接失败 → 自动回退 SQLite cosine scan
  ├── 3. Trauma memories（本地）
  └── 4. 去重+排序返回
```

**即使远程 Qdrant 宕机，系统也完全可用**（只是向量检索变慢，从 O(logN) 退化为全表扫描 O(N)）。

---

## 二、三种远程方案对比

| 方案 | 成本 | 部署复杂度 | 数据安全 | 推荐度 |
|------|------|-----------|---------|--------|
| **A. Qdrant Cloud 免费版** | ¥0 | 极低 | ★★★ | ⭐⭐⭐⭐⭐ 首选 |
| **B. 自建远程 Qdrant** | 1台2C4G服务器 | 中等 | ★★★★ | ⭐⭐⭐⭐ 数据量大时 |
| **C. 不用 Qdrant** | ¥0 | 无 | ★★★★★ | ⭐⭐⭐⭐ 完全OK |

---

## 三、方案A：Qdrant Cloud（推荐，5分钟搞定）

### 步骤

```bash
# 1. 注册 https://cloud.qdrant.io/ (免费1GB)
# 2. 创建 Cluster，获取 Endpoint 和 API Key

# 3. 配置 .env
NOVEL_QDRANT_ENABLED=true
NOVEL_QDRANT_HOST=xxx.eu-central.aws.cloud.qdrant.io
NOVEL_QDRANT_PORT=6333
NOVEL_QDRANT_API_KEY=your-api-key-from-dashboard
```

**优势**:
- 零运维，自动备份
- 免费1GB足够支撑 50-100 本小说的向量数据
- SSL加密传输
- 全球CDN加速

---

## 四、方案B：自建远程 Qdrant

### 服务器要求

| 配置 | 可支撑数据量 | 月费(阿里云) |
|------|-------------|-------------|
| 1C2G | 10-20本小说 | ~¥30 |
| 2C4G | 50-100本小说 | ~¥60 |

### 部署步骤

```bash
# === 远程服务器（假设IP: 192.168.1.100）===

# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 启动 Qdrant（带持久化和认证）
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v /data/qdrant:/qdrant/storage:z \
  -e QDRANT__SERVICE__API_KEY="your-secure-key-here" \
  -e QDRANT__SERVICE__ENABLE_TLS="false" \
  qdrant/qdrant:v1.8.4

# 3. 防火墙（只开放给应用服务器）
# 安全组: 允许 192.168.1.x/24 访问 6333 端口
# 禁止 0.0.0.0/0 访问
```

### 主应用配置

```bash
# === 主应用服务器（2C8G）===

# .env
NOVEL_QDRANT_ENABLED=true
NOVEL_QDRANT_HOST=192.168.1.100
NOVEL_QDRANT_PORT=6333
NOVEL_QDRANT_API_KEY=your-secure-key-here
```

---

## 五、方案C：不用 Qdrant（也完全OK）

当前系统**不启用 Qdrant 时所有功能完全可用**:

| 功能 | 有 Qdrant | 无 Qdrant (SQLite) |
|------|----------|-------------------|
| 语义检索 | HNSW O(logN) | 全表扫描 O(N) |
| 记忆存储 | SQLite + Qdrant 双写 | 仅 SQLite |
| 角色对话质量 | ★★★★★ | ★★★★☆（差距极小） |
| 长文本向量检索 | 精确高效 | 大库时略慢 |

**实际影响**: 对于10万字级别的小说，SQLite 存储的记忆条目通常 < 1000 条，全表扫描也完全够用。Qdrant 的优势在**超大规模**（百万级记忆条目）时才能体现。

**结论**: 如果预算有限，**完全可以不部署 Qdrant**，系统通过 SQLite cosine similarity 实现相同功能。

---

## 六、网络延迟影响

### 向量操作类型

| 操作 | 数据量 | 延迟敏感度 | 远程影响 |
|------|--------|-----------|---------|
| 写入向量 | 512维浮点数组 (~2KB) | 低（异步写入） | 几乎无影响 |
| 相似度搜索 | 512维查询向量 | 中 | +10-50ms（可接受） |
| 批量写入 | N个向量 | 低 | 批量API减少往返 |

### 实际体验

```
本地 Qdrant:   search() → 1-2ms
同机房 Qdrant: search() → 3-5ms
跨机房 Qdrant: search() → 10-30ms
Qdrant Cloud:  search() → 20-50ms

对比 LLM API 调用: 2000-10000ms
→ 向量检索延迟占比 < 1%，完全可忽略
```

---

## 七、数据流架构图

```
                    ┌─────────────────────────────────────┐
                    │           2C8G 主应用服务器           │
                    │                                     │
│用户│ ←──HTTP──→ │  FastAPI + Vue前端 + LangGraph       │
                    │                                     │
                    │  ┌──────────────┐  ┌─────────────┐  │
                    │  │   fastembed  │  │   SQLite    │  │
                    │  │  (本地CPU生成  │  │  (本地文件)  │  │
                    │  │   512维向量)  │  │             │  │
                    │  └──────┬───────┘  └─────────────┘  │
                    │         │                            │
                    │    向量数据 (2KB/条)                  │
                    │         │                            │
                    └─────────┼────────────────────────────┘
                              │  gRPC/HTTP (6333端口)
                              ▼
                    ┌─────────────────────────────────────┐
                    │       远程 Qdrant 服务器             │
                    │  (1C2G 足够 / 或 Qdrant Cloud)      │
                    │                                     │
                    │  ┌──────────────┐                   │
                    │  │  HNSW Index  │  ← 向量检索加速    │
                    │  │  3 Collections │                   │
                    │  │  • semantic   │                   │
                    │  │  • episodic   │                   │
                    │  │  • world_knowledge              │
                    │  └──────────────┘                   │
                    └─────────────────────────────────────┘
```

---

## 八、推荐配置

### 对于你的场景（2C8G主应用），我的建议：

| 阶段 | Qdrant方案 | 理由 |
|------|-----------|------|
| **初期（<10用户）** | **不启用** | SQLite完全够用，省一台服务器 |
| **中期（10-50用户）** | **Qdrant Cloud免费版** | 零运维，1GB免费足够 |
| **后期（>50用户）** | **自建1C2G远程** | 数据量大时成本更低 |

### 最简启用命令

```bash
# 如果你决定用 Qdrant Cloud（推荐）
# 1. 注册 https://cloud.qdrant.io
# 2. 复制 Endpoint 和 API Key
# 3. 编辑 .env，添加4行:
echo '
NOVEL_QDRANT_ENABLED=true
NOVEL_QDRANT_HOST=xxx.eu-central.aws.cloud.qdrant.io
NOVEL_QDRANT_PORT=6333
NOVEL_QDRANT_API_KEY=your-key
' >> .env

# 4. 重启服务
make restart
```

---

## 九、关键总结

| 问题 | 答案 |
|------|------|
| 远程Qdrant需要改代码吗？ | **不需要**，已原生支持 |
| Qdrant挂了会影响主应用吗？ | **不会**，自动fallback到SQLite |
| 网络延迟影响大吗？ | **不大**，向量检索只占LLM调用时间的1% |
| 初期必须部署Qdrant吗？ | **不必**，SQLite完全够用 |
| 免费方案有吗？ | **有**，Qdrant Cloud 1GB免费 |
| 自建Qdrant要什么配置？ | **1C2G足够**，磁盘看数据量 |
