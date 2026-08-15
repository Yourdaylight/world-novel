# WorldNovel 统一认证接入说明

WorldNovel 通过 `casdoor-auth-sidecar` 接入 Casdoor 统一认证，采用与 PinHaoClaw 一致的代理模式。

## 架构

```
浏览器 → WorldNovel (FastAPI) → casdoor-auth-sidecar (localhost:9098) → https://auth.jqcloudnet.cn
```

- Sidecar 只监听 `localhost`，不直接暴露公网。
- 浏览器所有认证请求都经由 WorldNovel 后端代理。
- 业务 API 通过 `POST sidecar /api/auth/verify` 验证 `X-User-Token`。

## 前置条件

1. Casdoor 线上服务：`https://auth.jqcloudnet.cn`
2. 为 WorldNovel 创建一个 Casdoor Application（如 `app_worldnovel_jq`），记录：
   - `client_id`
   - `client_secret`
   - `organization`
   - `application`
3. 在 Casdoor 后台配置回调地址：
   - 生产：`https://world-novel.programtree.cn/api/auth/sidecar/callback`
   - 本地开发：`http://localhost:8000/api/auth/sidecar/callback`
4. grantTypes 必须包含 `authorization_code` 与 `refresh_token`。

## 配置 Sidecar

在 `casdoor-auth-sidecar` 仓库中生成 WorldNovel 专属配置：

```bash
cd /home/jq/code/casdoor-auth-sidecar
./casdoor-auth-sidecar init-config \
  --output ./configs/world-novel.yaml \
  --endpoint https://auth.jqcloudnet.cn \
  --client-id <your-client-id> \
  --client-secret <your-client-secret> \
  --organization JQ \
  --application app_worldnovel_jq \
  --redirect-path /api/auth/sidecar/callback \
  --public-origin https://world-novel.programtree.cn
```

本地开发时 `public-origin` 改为 `http://localhost:8000`。

验证配置：

```bash
./casdoor-auth-sidecar --config ./configs/world-novel.yaml validate
./casdoor-auth-sidecar --config ./configs/world-novel.yaml test-connection
./casdoor-auth-sidecar --config ./configs/world-novel.yaml login-url
```

## 配置 WorldNovel

复制 `.env.example` 为 `.env`（如尚未创建），并添加：

```env
NOVEL_AUTH_ENABLED=true
NOVEL_AUTH_SIDECAR_URL=http://localhost:9098
NOVEL_PUBLIC_ORIGIN=http://localhost:8000
```

生产环境：

```env
NOVEL_AUTH_ENABLED=true
NOVEL_AUTH_SIDECAR_URL=http://localhost:9098
NOVEL_PUBLIC_ORIGIN=https://world-novel.programtree.cn
```

## 启动顺序

```bash
# 1. 启动 sidecar
cd /home/jq/code/casdoor-auth-sidecar
./casdoor-auth-sidecar --config ./configs/world-novel.yaml serve

# 2. 启动 WorldNovel（另一个终端）
cd /home/jq/code/world-novel
make dev
```

## 登录流程

1. 用户访问 `https://world-novel.programtree.cn`，未登录时前端跳转 `/login`。
2. 点击“前往统一认证中心”，浏览器访问 `/api/auth/sidecar/login`。
3. WorldNovel 代理到 sidecar `/api/auth/login`，sidecar 生成 OAuth2 URL 并重定向到 `auth.jqcloudnet.cn`。
4. 用户在 Casdoor 登录后，Casdoor 重定向回 `https://world-novel.programtree.cn/api/auth/sidecar/callback`。
5. WorldNovel 代理到 sidecar `/api/auth/callback`，sidecar 换取 token、创建 session，返回桥接 HTML。
6. 桥接 HTML 写入 `localStorage.casdoor_auth_token` 并跳转回首页。
7. 后续 API 请求自动携带 `X-User-Token`。

## 常见问题

- **redirect_uri 不匹配**：检查 Casdoor 后台、sidecar 配置、`NOVEL_PUBLIC_ORIGIN` 三者是否一致（含协议和端口）。
- **本地开发无法回调**：确保 Casdoor 后台已添加 `http://localhost:8000/api/auth/sidecar/callback`，且 sidecar 本地配置的 `public_origin` 也是 `http://localhost:8000`。
- **401 所有请求**：检查 sidecar 是否已启动，以及 `NOVEL_AUTH_SIDECAR_URL` 是否正确。
