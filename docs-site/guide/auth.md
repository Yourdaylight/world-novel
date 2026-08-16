# 认证配置

WorldNovel 的认证由 `NOVEL_AUTH_MODE` 控制，共三种模式，**严格按模式路由，不做跨模式回退**。

| 模式 | 适用 | 身份来源 |
|------|------|---------|
| `jwt`（默认） | 开源自建 | 邀请码登录，签发 HS256 JWT（7 天） |
| `casdoor` | 企业/自托管 | casdoor-auth-sidecar 会话 |
| `disabled` | 本地开发 | 所有接口放行（视为匿名管理员） |

## jwt 模式（开源推荐）

```bash
NOVEL_AUTH_MODE=jwt
WORLDENGINE_JWT_SECRET=<随机长字符串>
```

- **邀请码 = 注册凭证**：读者在登录页或公开阅读页输入有效邀请码即可「注册 / 登录」，无需独立注册流程。
- code 以 `NOVEL_ADMIN_CODE_PREFIX`（默认 `admin`）开头时自动获得管理员权限。
- JWT 可通过三种方式携带：`X-User-Token` 头（前端默认）、`Authorization: Bearer <token>`、`?token=`。
- 配额（Token / 请求次数 / 章节数）由 `invite_codes`、`user_quotas` 表管理。

> ⚠️ 生产环境务必修改 `WORLDENGINE_JWT_SECRET`，不要使用开发默认值。

## casdoor 模式（企业）

```bash
NOVEL_AUTH_MODE=casdoor
NOVEL_AUTH_SIDECAR_URL=http://localhost:9098
NOVEL_PUBLIC_ORIGIN=https://your-domain
```

浏览器登录与会话校验都代理到 `casdoor-auth-sidecar`，前端跳转统一认证中心。

## disabled 模式

```bash
NOVEL_AUTH_MODE=disabled
```

仅供本地开发：`require_auth` 返回匿名用户、`optional_auth` 也返回该用户。
注意：此模式下**公开分享页会把所有访客视为已注册**（即可读全书），这与「全部接口开放」的定位一致，**切勿用于公网**。

## 权限模型（分享阅读）

| 级别 | 身份 | 可访问内容 |
|------|------|-----------|
| L0 匿名 | 未登录 | 封面/简介/目录 + 试读章节（默认前 3 章，可配置） |
| L1 注册 | 有效邀请码 / sidecar 会话 | **全书** + 书架 + 进度同步 |
| L2 作者 | 小说 owner 或管理员 | 全部 + 创建/关闭分享、发布导出 |

正文访问以**后端为唯一真相**：匿名请求试读边界之外的章节返回 `403 {code:"need_login"}`，响应体不含任何正文。详见[公开分享与注册阅读](/guide/share)。
