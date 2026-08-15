# 常见问题 FAQ

## 安装与启动

### `make install` 时前端依赖安装失败？

国内网络可先设置 npm 镜像：

```bash
npm config set registry https://registry.npmmirror.com
```

如遇 `ERESOLVE` peer 依赖冲突，使用 `npm install --legacy-peer-deps`
（仓库 `web/.npmrc` 已内置该配置）。

### Node 版本要求是多少？

**≥ 20.19**（推荐 22 LTS）。前端构建工具 Vite 8 的引擎要求
`node ^20.19.0 || >=22.12.0`，更低版本会在 `make dev` / `make build` 时报错。

### 启动报数据库/表不存在？

表结构由 `get_connection()` 的 SCHEMA_SQL 自动创建；历史库可运行迁移工具补齐：

```bash
uv run python scripts/migrations/migrate.py
```

### 没有 LLM API Key 能体验吗？

不能直接生成（生成流水线依赖 LLM）。但分享/阅读、发布导出等围绕成书的能力，
可以用已有书籍数据体验；测试与评测使用种子数据（见 `scripts/eval/`）。

## 认证与邀请码

### 第一个管理员邀请码从哪来？

全新数据库自动播种默认管理员码 `admin_default`（迁移脚本 006）。
**生产环境请立即创建自己的 admin 码并停用它。**

### 如何给读者/作者发邀请码？

当前通过管理接口创建（暂无独立管理页面）：

```bash
curl -X POST http://localhost:8000/api/admin/invite-codes \
  -H "X-User-Token: $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"max_uses": 10, "initial_tokens": 100000, "initial_requests": 500}'
```

### 读者注册要收费吗？

开源版不收费：「匿名试读 → 注册即全文」。付费会员是商业版预留能力。

### 忘记改 JWT 密钥会有什么后果？

启动日志会出现默认密钥告警。默认密钥下任何人都能伪造合法 token
（包括 admin），生产环境必须设置 `NOVEL_JWT_SECRET`。

## 分享与阅读

### 分享链接被别人扫出来怎么办？

分享 ID 是 10 位随机短码（去除易混淆字符），枚举不可行；公开接口另有
单 IP 每分钟 60 次限流（超限 429）。关闭分享后所有公开接口立即 404。

### 匿名读者能看到多少？

默认前 3 章（可配置：前 N 章 / 前 N 字 / 全书百分比，可设 0）。
试读外的章节接口返回 `403 need_login`，**绝不包含正文**。

### 生产环境还需要在 nginx 配限流吗？

建议双保险：应用内已有限流（单实例），nginx `limit_req` 可在代理层提前拦截。
注意：若加 `--workers N` 多进程部署，应用内计数按 worker 分裂，
应以 nginx 限流为准。

## 发布

### 为什么不能全自动直发番茄/七猫？

平台均无公开开放 API（见 [一键发布](./publish.md) §平台现实约束）。
当前提供 L0 一键导出（平台规范打包），由作者在作家后台手动上传；
L1 半自动（浏览器填充、人工确认提交）为远期能力。

### 导出的 TXT 上传后乱码？

番茄请使用 GB18030 编码文件（导出默认即此编码）；七猫按卷上传 UTF-8 文件。
若平台模板仍乱码，尝试转码为 GBK 重新上传。

### 质量门禁报「断章」怎么办？

说明 `chapter_texts` 的章节索引存在缺口（生成中断/手动删除）。
重新继续生成补齐章节，或检查断点恢复（`worldnovel resume`）。

## 部署

### 文档站如何部署到 GitHub Pages？

GitHub Pages 不支持无扩展名 URL，构建时需关闭 cleanUrls：

```bash
DOCS_BASE=/world-novel/ DOCS_CLEAN_URLS=false npm run docs:build
```

详见 [部署指南](./deploy.md)。

### Qdrant / Neo4j 必须部署吗？

可选。默认关闭（`NOVEL_QDRANT_ENABLED` / `NOVEL_NEO4J_ENABLED`），
不部署不影响核心生成与分享/发布功能。
