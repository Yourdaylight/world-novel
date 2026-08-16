# 独立部署

## 拓扑

```
公网 ── nginx ──┬─ world-novel.example.com  → uvicorn :8000 (FastAPI + 工作台静态产物)
                ├─ /docs/                   → 纯静态文档站（docs-site/dist）
                └─ (可选) casdoor-sidecar :9098 / qdrant / neo4j
```

## 后端

```bash
uv sync
cd web && npm install --legacy-peer-deps && npm run build && cd ..
NOVEL_AUTH_MODE=jwt WORLDENGINE_JWT_SECRET=<secret> \
  uv run uvicorn novel_creator.web.app:app --host 0.0.0.0 --port 8000
```

推荐 systemd 托管（`Restart=always`）。每部小说一个独立 SQLite（`data/novels/<id>/novel.db`），中央库 `data/novel.db` 存放邀请码、额度、分享链接、发布记录。

## 文档站（纯静态、零后端依赖）

文档站是独立 npm 包，不依赖 FastAPI / 数据库：

```bash
cd docs-site
npm ci          # 或 npm install --legacy-peer-deps
npm run docs:build          # 产物在 docs-site/dist
```

三种托管方式任选：

1. **同机子路径**：`DOCS_BASE=/docs/ npm run docs:build`，nginx 配置
   ```nginx
   location /docs/ {
     alias /opt/world-novel/docs-site/dist/;
     try_files $uri $uri/ /docs/index.html;
   }
   ```
2. **独立子域**：`docs.example.com` 直接 root 指向 `dist/`（`DOCS_BASE=/`）。
3. **GitHub Pages**：把 `dist/` 发布到 gh-pages 分支即可，零成本。

离线友好：构建产物内联所需样式，使用系统字体栈，**运行时不请求任何外部 CDN / 字体**。

## nginx 限流（分享接口）

```nginx
limit_req_zone $binary_remote_addr zone=share:10m rate=60r/m;
location /api/share/ {
  limit_req zone=share burst=20 nodelay;
  proxy_pass http://127.0.0.1:8000;
}
```

位于 nginx 之后时设置 `NOVEL_TRUST_PROXY=true`，应用会按 `X-Forwarded-For` 最右一跳识别真实客户端。
