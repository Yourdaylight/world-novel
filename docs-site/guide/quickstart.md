# 快速开始

WorldNovel 后端为 Python 3.11+ / FastAPI / LangGraph，前端为 Vue 3 + Vite。

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 推荐 [uv](https://docs.astral.sh/uv/) 管理 |
| Node.js | ≥ 18 | 构建前端工作台 |
| SQLite | 系统自带 | 每部小说独立 DB 文件，无需额外服务 |

可选：Qdrant / Neo4j（向量与图记忆增强，默认关闭）。

## 1. 获取代码

```bash
git clone https://github.com/Yourdaylight/world-novel.git
cd world-novel
```

## 2. 安装与启动

```bash
make install    # uv sync + 前端依赖
make dev        # 开发模式：后端 :8000，前端热重载 :5173
```

生产模式（构建前端、单进程托管）：

```bash
make prod       # 构建 web/dist，uvicorn :8000 同时托管 API 与工作台
```

启动后访问：

- 作者工作台：<http://localhost:8000>（开发模式为 <http://localhost:5173>）
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

## 3. 配置 LLM

通过环境变量或项目根目录 `.env` 配置：

```bash
# OpenAI 兼容服务均可（OpenRouter / 自建网关 / 国内代理）
NOVEL_LLM_PROVIDER=openai
NOVEL_OPENAI_API_KEY=sk-xxxx
NOVEL_OPENAI_BASE_URL=https://api.openai.com/v1

# 模型分工
NOVEL_DIRECTOR_MODEL=gpt-4o
NOVEL_WRITER_MODEL=gpt-4o
NOVEL_CHARACTER_MODEL=gpt-4o-mini
```

全部配置项见 [`src/novel_creator/config.py`](https://github.com/Yourdaylight/world-novel/blob/main/src/novel_creator/config.py)。

## 4. 创建第一部小说

1. 打开工作台 → **创建世界**：填写书名、类型、三个终极命题、章节数；
2. 进入小说工作台 → **控制台** → 开始生成；
3. 在「章节」页实时查看写作过程，全部完成后即可[发布](./publish)或[分享](./share)。

## 部署 {#deploy}

### 单机 systemd（推荐）

```ini
# /etc/systemd/system/world-novel.service
[Unit]
Description=WorldNovel (FastAPI + 工作台静态托管)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/world-novel
Environment=NOVEL_AUTH_MODE=jwt
Environment=NOVEL_BEHIND_PROXY=1
Environment=WORLDENGINE_JWT_SECRET=请替换为强随机密钥
ExecStart=/usr/local/bin/uv run uvicorn novel_creator.web.app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### nginx 反代要点

```nginx
# http {} 顶层定义限流区（每个客户端 IP 60 请求/分钟）
limit_req_zone $binary_remote_addr zone=share:10m rate=60r/m;

server {
    listen 80;
    server_name your.domain;

    client_max_body_size 20m;
    location /api/ {
        limit_req zone=share burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    location / { proxy_pass http://127.0.0.1:8000; }
}
```

应用内也内置了限流（默认 60 次/分/IP，可用 `NOVEL_SHARE_RATE_PER_MIN` 调整，0 关闭）。
部署在 nginx 之后时设置 `NOVEL_BEHIND_PROXY=1`，限流才会按 `X-Forwarded-For` 中的真实客户端 IP 计费（否则所有人共用回环地址桶）。

### 文档站独立部署

本站（你正在看的页面）是**纯静态产物**，与主应用零耦合：

```bash
cd docs-site
npm install
DOCS_BASE=/docs/ npm run docs:build    # 主站子路径部署用 /docs/；独立域名用 /
```

产物在 `docs-site/.vitepress/dist`，任选一种托管：

```nginx
# 同机子路径
location /docs/ { alias /opt/world-novel/docs-site/.vitepress/dist/; }
```

或独立子域、GitHub Pages（`DOCS_BASE=/world-novel/`）、对象存储静态托管均可。**停掉主应用后文档站照常可访问。**

## 常用命令

| 命令 | 作用 |
|------|------|
| `make dev` | 开发模式 |
| `make prod` | 生产模式 |
| `make test` | 单元测试 |
| `make lint` | ruff + vue-tsc |
| `make smoke` | 冒烟测试（需服务运行中） |
