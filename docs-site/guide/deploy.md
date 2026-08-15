# 部署指南

## 总体拓扑（生产参考）

```
                    ┌────────────────────────── 服务器 ──────────────────────────────┐
公网 ── nginx ──────┤                                                                │
                    │  主域名          → uvicorn :8000 (FastAPI + 静态工作台)          │
                    │  /docs/ 或子域    → 静态 root（docs-site/dist，零后端依赖）       │
                    │  casdoor sidecar → Casdoor 认证（casdoor 模式，可选）            │
                    │  qdrant / neo4j  → docker-compose（可选）                       │
                    └────────────────────────────────────────────────────────────────┘
```

## 主应用部署

### 方式一：systemd + uvicorn（推荐）

```bash
cd /opt/world-novel
make build                     # 构建前端 → web/dist
sudo tee /etc/systemd/system/world-novel.service <<'EOF'
[Unit]
Description=WorldNovel FastAPI
After=network.target

[Service]
WorkingDirectory=/opt/world-novel
ExecStart=/opt/world-novel/.venv/bin/uvicorn novel_creator.web.app:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/opt/world-novel/.env

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now world-novel
```

### 方式二：Docker

```bash
make docker-build
make docker-up        # 默认 :9000，见 scripts/deploy-docker.sh
```

## nginx 参考配置

```nginx
server {
    listen 443 ssl http2;
    server_name world-novel.example.com;

    # 主应用（API + 工作台 SPA）
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;      # WebSocket
        proxy_set_header Connection "upgrade";
    }

    # 分享页限流（与应用内限流双保险）
    location /api/share/ {
        limit_req zone=share burst=10 nodelay;
        proxy_pass http://127.0.0.1:8000;
    }

    # 文档站：独立静态 root，与主应用完全解耦
    location /docs/ {
        alias /opt/world-novel-docs/dist/;
        try_files $uri $uri/ /docs/index.html;
    }
}
# limit_req_zone $binary_remote_addr zone=share:10m rate=60r/m;
```

## 文档站独立部署

文档站（本站）构建产物是**纯静态目录**，不含任何后端请求、不依赖数据库，
三种托管方式任选：

### 1. 同机 nginx 子路径

```bash
cd docs-site
DOCS_BASE=/docs/ npm run docs:build      # base 必须与 location 路径一致
sudo mkdir -p /opt/world-novel-docs
sudo cp -r dist /opt/world-novel-docs/
```

### 2. 独立子域

```bash
DOCS_BASE=/ npm run docs:build
# nginx: server { server_name docs.example.com; root /opt/world-novel-docs/dist; }
```

### 3. GitHub Pages

```bash
DOCS_BASE=/world-novel/ npm run docs:build
# 将 dist/ 推送到 gh-pages 分支即可
```

**独立部署冒烟检验**：停掉主应用 uvicorn 服务后，文档站应仍返回 200
且全部资源加载成功 — 这证明零后端依赖。

## 可选组件

```bash
docker compose up -d        # Qdrant + Neo4j（.env 中开启对应开关）
```

- `NOVEL_QDRANT_ENABLED=true` — 语义记忆向量检索
- `NOVEL_NEO4J_ENABLED=true` — 角色关系图谱
