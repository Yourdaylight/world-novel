# 05 — 工作空间隔离方案

## 设计原则

```
每个用户的每个世界 = 一个完全独立的工作空间
用户之间零共享、零干扰
世界之间零泄漏
```

---

## 三层隔离架构

```
┌─────────────────────────────────────────────────────────┐
│                      用户层隔离                           │
│                                                         │
│  User A                              User B             │
│  ┌─────────────────────┐             ┌────────────────┐ │
│  │ workspace/           │             │ workspace/      │ │
│  │ ├── user_a/          │             │ ├── user_b/     │ │
│  │ │   ├── world_1/     │             │ │   ├── world_x/│ │
│  │ │   ├── world_2/     │             │ │   └── world_y/│ │
│  │ │   └── world_3/     │             │ └───────────────│ │
│  │ └───────────────────│             └────────────────┘ │
│  └─────────────────────┘                                │
│                                                         │
│  完全不同的文件系统路径，互不可见                           │
└─────────────────────────────────────────────────────────┘
```

---

## 数据隔离方案

### Level 1: 文件系统隔离（当前方案 + 增强）

```
data/
├── registry.json                    # 全局注册表 (→ 升级为 per-user)
│
├── users/
│   ├── {user_id}/
│   │   ├── profile.json             # 用户配置
│   │   ├── registry.json            # 该用户的世界注册表
│   │   │
│   │   ├── worlds/
│   │   │   ├── {world_id_1}/
│   │   │   │   ├── novel.db         # 核心数据库 (SQLite)
│   │   │   │   ├── agents/          # Agent 文件
│   │   │   │   │   ├── char_001/
│   │   │   │   │   │   ├── agent.md
│   │   │   │   │   │   ├── soul.md
│   │   │   │   │   │   └── memories/
│   │   │   │   │   ├── char_002/
│   │   │   │   │   └── god/
│   │   │   │   ├── world/           # 世界设定文件
│   │   │   │   │   ├── worldview.md
│   │   │   │   │   └── rules.md
│   │   │   │   └── output/          # 输出成品
│   │   │   │       ├── novel_视角A.md
│   │   │   │       └── novel_视角B.md
│   │   │   │
│   │   │   └── {world_id_2}/
│   │   │       └── ...
│   │   │
│   │   └── templates/               # 用户收藏的世界模板
│   │       └── ...
│   │
│   └── {user_id_2}/
│       └── ...
│
└── shared/                          # 公共资源
    └── templates/                   # 官方世界模板
```

### Level 2: 数据库隔离

**每个世界一个独立 SQLite 文件**（已实现）。

增强措施：
```python
# 当前实现
db_path = f"data/{novel_id}/novel.db"

# 升级后
db_path = f"data/users/{user_id}/worlds/{world_id}/novel.db"
```

**关键约束**：
- API 层必须验证 `user_id` 对 `world_id` 的所有权
- 禁止通过 path traversal 访问其他用户的数据
- 每个 API 请求的 `novel_id` 必须属于当前认证用户

### Level 3: API 层隔离

```python
# 中间件：验证用户对世界的所有权
@app.middleware("http")
async def verify_ownership(request: Request, call_next):
    user_id = get_current_user(request)  # 从 JWT/Session 获取
    novel_id = request.query_params.get("novel_id")

    if novel_id:
        registry = load_user_registry(user_id)
        if novel_id not in [n.novel_id for n in registry.novels]:
            return JSONResponse({"error": "无权访问该世界"}, 403)

    request.state.user_id = user_id
    return await call_next(request)
```

---

## 用户认证方案

### Phase 1: 本地模式（当前）
- 无认证，单用户
- 数据在本地文件系统
- 适合开发者/个人使用

### Phase 2: 轻量认证（MVP SaaS）
```
方案: JWT + SQLite 用户表
注册: 邮箱 + 密码
登录: 签发 JWT (24h 过期)
存储: 服务端文件系统

优点: 最小改动，快速上线
缺点: 不支持水平扩展
```

### Phase 3: 正式认证（规模化）
```
方案: OAuth 2.0 + 对象存储
认证: GitHub/Google/微信 OAuth
存储: S3/OSS + 用户级加密
扩展: Kubernetes + 负载均衡

优点: 生产级安全性
缺点: 基础设施成本高
```

---

## 世界与世界的隔离

### 同一用户的多个世界

```python
class WorldRegistry:
    """用户级世界注册表"""
    user_id: str
    worlds: list[WorldInfo]
    active_world_id: str | None

class WorldInfo:
    world_id: str          # UUID
    title: str             # "星魂大陆"
    genre: str             # "玄幻"
    status: str            # idle | running | paused | completed
    created_at: datetime
    db_path: str           # 相对路径
    word_count: int        # 总字数
    chapter_count: int     # 总章数
    character_count: int   # 角色数
```

### 世界间数据完全隔离

| 数据 | 隔离方式 | 说明 |
|------|---------|------|
| 数据库 | 独立 SQLite 文件 | 每个世界一个 .db |
| Agent 文件 | 独立目录 | 每个世界独立的 agents/ |
| 记忆 | 数据库内 | 跟随各自的 SQLite |
| 输出 | 独立目录 | 每个世界独立的 output/ |
| 检查点 | 数据库内 | 跟随各自的 SQLite |

### 世界分支（平行世界）

```
world_001/                    # 原始世界
├── novel.db                  # 运行到第10章
└── ...

world_001_branch_a/           # 分支世界A (从第5章检查点分叉)
├── novel.db                  # 第5章检查点数据的副本
└── ...                       # 可以走完全不同的剧情

world_001_branch_b/           # 分支世界B (从第8章分叉)
├── novel.db
└── ...
```

**分支操作**：
```python
async def fork_world(user_id: str, source_world_id: str, checkpoint_id: str) -> str:
    """从检查点创建分支世界"""
    new_world_id = generate_uuid()
    source_path = get_world_path(user_id, source_world_id)
    target_path = get_world_path(user_id, new_world_id)

    # 1. 复制数据库
    shutil.copy(source_path / "novel.db", target_path / "novel.db")

    # 2. 复制 Agent 文件
    shutil.copytree(source_path / "agents", target_path / "agents")

    # 3. 回滚到指定检查点
    await rollback_to_checkpoint(target_path / "novel.db", checkpoint_id)

    # 4. 注册新世界
    register_world(user_id, new_world_id, ...)

    return new_world_id
```

---

## 配额与限制

| 套餐 | 世界数量上限 | 单世界最大章节 | 单世界最大角色 | 存储上限 |
|------|------------|--------------|--------------|---------|
| 免费版 | 1 | 10 | 3 | 50MB |
| 创作者版 | 5 | 100 | 10 | 500MB |
| 专业版 | 20 | 无限 | 20 | 5GB |
| 团队版 | 100 | 无限 | 50 | 50GB |

---

## 安全要点

| 风险 | 防护措施 |
|------|---------|
| Path Traversal | 所有路径基于 user_id + world_id 构造，禁止用户输入路径 |
| 越权访问 | API 层中间件校验 user_id → world_id 所有权 |
| 数据泄露 | SQLite 文件权限 600，仅属主用户可读 |
| 大文件攻击 | 限制单世界存储上限 + 文件上传大小限制 |
| API 滥用 | Rate limiting (per user) + Token 消耗追踪 |
| 敏感内容 | 世界创建时内容审核 + 输出审核 |
