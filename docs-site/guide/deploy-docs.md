# 独立部署文档站

文档站（本站）与首页是**纯静态产物**，不依赖 WorldNovel 后端 API 或数据库，
任何静态服务器（nginx / GitHub Pages / 对象存储）都可以托管。

## 构建

```bash
cd docs-site
npm install
npm run docs:build     # 输出到 docs-site/.vitepress/dist
```

`docs:build` 会先执行 `scripts/sync_product_docs.py`，把 `docs/product/`
的产品设计文档同步到 `docs-site/product/`，保证两边一致。

## 三种部署形态

### 1. 同机 nginx 子路径（推荐的当前规划）

规划域名：`world-novel.programtree.cn/docs/`。

构建时指定 base 路径：

```bash
DOCS_BASE=/docs/ npm run docs:build
```

nginx：

```nginx
location /docs/ {
    alias /opt/world-novel-docs/dist/;
    # $uri.html 用于支持 cleanUrls（无 .html 后缀的页面地址）
    try_files $uri $uri.html $uri/ =404;
}
```

工作台与 API 仍走 `location /` → uvicorn:8000，两者互不影响。

### 2. 独立子域

```bash
DOCS_BASE=/ npm run docs:build
```

```nginx
server {
    server_name docs.example.com;
    root /opt/world-novel-docs/dist;
    # $uri.html 用于支持 cleanUrls（无 .html 后缀的页面地址）
    location / { try_files $uri $uri.html $uri/ /index.html; }
}
```

### 3. GitHub Pages（开源零成本）

项目页默认部署在 `https://<user>.github.io/<repo>/`，此时：

```bash
DOCS_BASE=/world-novel/ npm run docs:build
```

然后把 `.vitepress/dist` 推送到 `gh-pages` 分支即可。

## 独立部署冒烟验证

按评测要求，文档站必须能在主服务停掉时正常工作：

```bash
# 1. 停掉 uvicorn 主服务
systemctl stop world-novel

# 2. 用任意静态服务器托管 dist
cd docs-site/.vitepress/dist && python3 -m http.server 8090

# 3. 验证：页面 200、全部资源 200、无任何 /api 请求
curl -I http://localhost:8090/
```

## 离线 / 国内网络友好

- VitePress 把 JS / CSS 全部构建为本地静态资源，**无 CDN 依赖**；
- 默认主题使用系统字体栈，不加载 Google Fonts；
- 搜索为浏览器端本地索引（`local` provider），无外部服务。

## 首页（宣传页）

仓库 `website/index.html` 是独立单文件宣传页，含 GitHub 仓库入口，
同样可以直接用任意静态服务器托管，与本文档站解耦。
