# WorldNovel 文档站（独立静态站）

首页 + 使用文档，基于 [VitePress](https://vitepress.dev)。**纯静态产物，不依赖后端 API / 数据库**，
nginx、GitHub Pages、对象存储均可直接托管。

## 本地开发

```bash
npm install
npm run docs:dev      # http://localhost:5173 热重载
```

## 构建

```bash
npm run docs:build    # 产物：.vitepress/dist
npm run docs:preview  # 本地验证构建产物
```

### 部署路径

通过 `DOCS_BASE` 环境变量适配托管位置：

| 托管方式 | 命令 |
|----------|------|
| 独立域名 / 本地预览 | `npm run docs:build`（默认 `/`） |
| 主站子路径 `/docs/` | `DOCS_BASE=/docs/ npm run docs:build` |
| GitHub Pages（项目页） | `DOCS_BASE=/world-novel/ npm run docs:build` |

nginx 片段见 [`deploy/nginx-docs.conf.example`](./deploy/nginx-docs.conf.example)。
仓库根目录宣传页（`website/index.html`）的"使用文档"入口假设文档站部署在
**同机 `/docs/` 子路径**；若使用独立子域，请相应调整该链接。

已附带 `public/.nojekyll`，GitHub Pages 直接发布构建产物即可。

## 内容来源

- `guide/`、`reference/`：使用指南与 API 参考（手写维护）
- `product/`：从仓库 `docs/product/` **同步**而来，请勿直接编辑：

```bash
# 从仓库根目录
scripts/sync-product-docs.sh          # 同步
scripts/sync-product-docs.sh --check  # CI 一致性校验
```

## 离线友好

默认主题的全部字体、脚本、样式均为本地构建产物，不加载 Google Fonts / Tailwind CDN
等外部资源，国内网络可直接访问。
