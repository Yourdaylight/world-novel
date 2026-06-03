# 部署逻辑与升级平滑度评估报告

> 评估日期: 2026-06-03 | 版本: v0.6.0 | 评估人: AI Assistant

---

## 一、总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 部署简易度 | ⭐⭐⭐⭐ (4/5) | 多方式支持(dev/prod/docker/remote)，一键启动 |
| 升级平滑度 | ⭐⭐ (2/5) | 数据库迁移简陋，无回滚机制，无版本管理 |
| 生产就绪度 | ⭐⭐⭐ (3/5) | 缺少systemd/.dockerignore/日志轮转 |
| 配置管理 | ⭐⭐⭐ (3/5) | pydantic-settings好用，但.env.example不完整 |
| 安全合规 | ⭐⭐⭐ (3/5) | 非root运行、healthcheck有，但secrets管理缺失 |

**综合评分: 3/5 — 适合小团队/个人使用，生产环境需补强**

---

## 二、部署方式矩阵

```
┌─────────────────┬────────────────────────────────────────────┬──────────┐
│ 方式            │ 命令                                       │ 适用场景 │
├─────────────────┼────────────────────────────────────────────┼──────────┤
│ 本地开发        │ make dev                                   │ 开发     │
│ 本地生产        │ make prod                                  │ 本地演示 │
│ Docker          │ make docker-up                             │ 单机部署 │
│ 远程SSH         │ make deploy HOST=user@host                 │ VPS/云   │
│ Docker Compose  │ ./scripts/deploy-docker.sh up              │ 容器化   │
│ 远程代码同步    │ make deploy-code HOST=user@host            │ 热更新   │
│ 远程重启        │ make restart HOST=user@host                │ 运维     │
└─────────────────┴────────────────────────────────────────────┴──────────┘
```

**优点**: 7种部署方式覆盖全场景，Makefile统一入口，脚本健壮（set -euo pipefail）。

---

## 三、发现的问题（按严重程度排序）

### 🔴 P0 — 阻碍生产部署

#### 1. 项目名称严重不一致

| 文件 | 使用的名称 |
|------|-----------|
| `Makefile` | WorldNovel |
| `start.sh` | WorldEngine |
| `start-local.sh` | WorldNovel |
| `deploy-docker.sh` | WorldEngine → WorldNovel 混合 |
| `deploy-remote.sh` | WorldNovel |
| `smoke-test.sh` | WorldEngine → WorldNovel |
| `docker-compose.yml` | WorldNovel → container: worldengine |
| `.env.example` | WorldEngine |
| `src/`代码注释 | WorldEngine / WorldNovel 混合 |

**影响**: Docker容器名、服务名、日志标识混乱，运维排查困难。

**修复**: 全局统一为 `world-novel`（与GitHub仓库名一致）。

#### 2. 缺少 .dockerignore

**影响**: Docker构建复制 `.git/`、`__pycache__/`、`node_modules/`、`.venv/` 等，镜像体积膨胀数GB，构建速度极慢。

**修复**: 添加 `.dockerignore`。

#### 3. 数据库迁移机制不可靠

当前模式（`database.py`）:
```python
try:
    await conn.execute("ALTER TABLE ... ADD COLUMN ...")
except Exception:
    pass  # Column already exists
```

**问题**:
- 静默吞掉所有错误（包括真正的数据库错误）
- 没有迁移版本号记录，无法判断当前数据库版本
- 无法处理破坏性变更（RENAME COLUMN、DROP COLUMN、数据转换）
- 没有回滚能力
- 新增表只依赖 `CREATE TABLE IF NOT EXISTS`，跨版本兼容性未验证

**影响**: 未来版本升级时可能导致数据丢失或静默失败。

### 🟡 P1 — 建议修复

#### 4. .env.example 不完整

缺少本次新增的配置项:
- `NOVEL_JWT_SECRET` — JWT密钥
- `NOVEL_ADMIN_CODE_PREFIX` — 管理员前缀
- `NOVEL_CORS_ORIGINS` — CORS来源

#### 5. Dockerfile 不在版本控制中

`Dockerfile` 和 `docker-compose.deploy.yml` 由 `deploy-docker.sh init` 动态生成。

**问题**:
- 无法代码审查Dockerfile变更
- 无法追踪部署配置历史
- CI/CD流水线无法直接 `docker build`

#### 6. 远程部署使用 tmux（非生产级）

**问题**:
- 服务器重启后服务不会自动恢复
- 没有日志轮转，日志文件无限增长
- 没有资源限制（OOM风险）
- 没有健康检查和自动重启

#### 7. 没有数据备份机制

- SQLite数据库无自动备份
- 升级前无快照能力
- 回滚 impossible

### 🟢 P2 — 优化项

#### 8. 脚本中存在hardcoded路径
- `logs/server.log` 无轮转
- 远程目录 `/opt/worldnovel` 无自定义空间检查

#### 9. 健康检查端点未文档化
- `/api/health` 存在但未在README中说明
- Docker HEALTHCHECK 用 `/api/novels`（可能因空数据失败）

---

## 四、升级路径风险分析

### 场景: v0.6.0 → v0.7.0（假设新增功能）

| 风险点 | 当前行为 | 期望行为 |
|--------|---------|---------|
| 新增数据库表 | `CREATE TABLE IF NOT EXISTS` 自动创建 | ✅ 正常 |
| 新增列 | `ALTER TABLE ADD COLUMN` try/except | ⚠️ 静默失败不可见 |
| 修改列类型 | ❌ 无法处理 | 需要迁移脚本 |
| 删除列/表 | ❌ 无法处理 | 需要迁移脚本 |
| 数据转换 | ❌ 无法处理 | 需要迁移脚本 |
| 回滚 | ❌ 无备份无回滚 | 需要备份+回滚脚本 |

**结论**: 当前只能处理"新增表"和"新增列"两种场景，其他升级场景有风险。

---

## 五、改进建议与实施计划

### 阶段1: 立即修复（P0 + P1）

#### 1. 统一项目命名
```bash
# 全局替换（保留GitHub路径中的Yourdaylight/world-novel）
WorldEngine → world-novel（用户可见文本）
WorldNovel  → world-novel（用户可见文本）
worldengine → world-novel（Docker容器名、服务名）
```

#### 2. 添加 .dockerignore
```
# .dockerignore
.git/
.gitignore
.venv/
__pycache__/
*.pyc
*.pyo
*.egg-info/
.pytest_cache/
.ruff_cache/

web/node_modules/
web/dist/

# 数据（通过volume挂载）
data/*.db
data/*.db-journal
data/*.db-wal
data/*.db-shm

# 文档和测试
docs/
tests/
*.md
DEPLOYMENT_REVIEW.md

# IDE
.vscode/
.idea/
*.swp
```

#### 3. 引入数据库迁移框架

推荐方案: **alembic**（SQLAlchemy生态的标准迁移工具）

替代方案: **yoyo-migrations**（轻量级，纯SQL）

建议采用轻量级方案（保持项目简洁）:
```
scripts/migrations/
├── 001_v6_token_usage.sql
├── 002_v7_invite_codes.sql
├── 003_v8_quota_system.sql
└── migrate.py  # 简单的迁移runner
```

`migrate.py` 核心逻辑:
```python
# 记录已执行的迁移到 _migrations 表
# 按顺序执行未执行的 .sql 文件
# 每个迁移在一个事务中执行
# 失败时回滚并报错（不静默吞异常）
```

#### 4. 固化 Dockerfile

将 `deploy-docker.sh` 生成的 Dockerfile 提取为项目根目录的 `Dockerfile`:
```dockerfile
# Dockerfile（多阶段构建）
# Stage 1: 构建前端
FROM node:20-alpine AS frontend-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --silent
COPY web/ .
RUN npm run build

# Stage 2: Python运行时
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src/ ./src/
COPY --from=frontend-builder /app/web/dist ./web/dist
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uv", "run", "novel-creator", "web", "--host", "0.0.0.0", "--port", "8000"]
```

#### 5. 完善 .env.example
```env
# ── 认证与安全 ──────────────────────────────────────────
NOVEL_JWT_SECRET=change-me-in-production-to-random-string
NOVEL_ADMIN_CODE_PREFIX=admin
NOVEL_CORS_ORIGINS=*
```

### 阶段2: 生产级加固

#### 6. 添加 systemd 服务模板
`scripts/world-novel.service`:
```ini
[Unit]
Description=world-novel AI Novel Generation System
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/world-novel
ExecStart=/opt/world-novel/.venv/bin/worldnovel web --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

# 资源限制
MemoryMax=2G
CPUQuota=200%

# 日志
StandardOutput=append:/var/log/world-novel/server.log
StandardError=append:/var/log/world-novel/server.log

[Install]
WantedBy=multi-user.target
```

#### 7. 添加备份脚本
```bash
#!/bin/bash
# scripts/backup.sh
# 定时任务: 0 3 * * * /opt/world-novel/scripts/backup.sh
BACKUP_DIR="/opt/world-novel/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp /opt/world-novel/data/*.db "$BACKUP_DIR/"
tar czf "$BACKUP_DIR.tar.gz" -C "$BACKUP_DIR" .
rm -rf "$BACKUP_DIR"
# 保留最近30天
find /opt/world-novel/backups -name "*.tar.gz" -mtime +30 -delete
```

#### 8. 升级脚本
```bash
#!/bin/bash
# scripts/upgrade.sh
# 1. 备份数据库
# 2. git pull
# 3. 安装依赖
# 4. 运行数据库迁移
# 5. 构建前端
# 6. 重启服务
# 7. 健康检查（失败则回滚）
```

---

## 六、推荐的最简生产部署流程

```bash
# 1. 准备服务器 (Ubuntu 22.04+)
ssh root@server
apt update && apt install -y python3.11 nodejs npm
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建用户
useradd -m -r appuser
mkdir -p /opt/world-novel && chown appuser:appuser /opt/world-novel

# 3. 克隆代码
git clone https://github.com/Yourdaylight/world-novel.git /opt/world-novel
cd /opt/world-novel
cp .env.example .env
# 编辑 .env 填入 API Key

# 4. 安装 + 构建
make install
make build

# 5. 初始化数据库（首次）
# 自动完成，无需手动操作

# 6. 安装 systemd 服务
cp scripts/world-novel.service /etc/systemd/system/
mkdir -p /var/log/world-novel && chown appuser:appuser /var/log/world-novel
systemctl daemon-reload
systemctl enable world-novel
systemctl start world-novel

# 7. 验证
systemctl status world-novel
curl http://localhost:8000/api/health
```

---

## 七、Docker 部署（推荐方式）

```bash
# 1. 克隆
git clone https://github.com/Yourdaylight/world-novel.git
cd world-novel
cp .env.example .env
# 编辑 .env

# 2. 构建 + 启动
docker build -t world-novel:latest .
docker run -d \
  --name world-novel \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  --restart unless-stopped \
  --memory=2g \
  world-novel:latest

# 3. 验证
curl http://localhost:8000/api/health
```

---

## 八、升级检查清单

```
□ 备份数据库: scripts/backup.sh
□ 查看变更日志: git log --oneline
□ 检查是否有破坏性变更
□ 拉取新代码: git pull origin main
□ 安装新依赖: make install
□ 运行数据库迁移: uv run python scripts/migrate.py
□ 构建前端: make build
□ 重启服务: sudo systemctl restart world-novel
□ 健康检查: curl /api/health
□ 功能验证: make smoke
□ (如失败) 回滚: 还原备份 + git checkout 上一版本
```

---

## 九、总结

当前部署系统**"能用但不完美"**:
- ✅ 多种部署方式覆盖全场景
- ✅ 脚本健壮（错误处理、颜色输出、帮助文档）
- ✅ SQLite自动创建表 + WAL模式
- ❌ 项目名称混乱
- ❌ 数据库迁移不可靠
- ❌ 无备份/回滚机制
- ❌ .dockerignore 缺失
- ❌ Dockerfile 未版本控制

**优先级**: 先修复P0项目（命名统一+.dockerignore+迁移框架），再逐步完善生产级功能。
