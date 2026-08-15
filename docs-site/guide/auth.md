# 认证配置

WorldNovel 的认证体系是**三模式可切换**的，由环境变量 `NOVEL_AUTH_MODE` 控制：

| 模式 | 取值 | 适用场景 | 用户体系 |
|------|------|---------|---------|
| JWT（默认） | `jwt` | 开源版 / 个人部署 | 邀请码注册 + JWT + token 额度 |
| Casdoor | `casdoor` | 企业 / 自托管 SSO | Casdoor Auth Sidecar 会话 |
| 关闭 | `disabled` | 本地开发 / 演示 | 全部接口开放 |

## jwt 模式（开源默认）

```bash
NOVEL_AUTH_MODE=jwt
NOVEL_JWT_SECRET=change-me-in-production-to-random-string   # 生产必须修改
NOVEL_ADMIN_CODE_PREFIX=admin
```

工作流程：

1. **管理员**：以 `admin` 前缀的邀请码登录（自动获得管理员权限，
   前缀可由 `NOVEL_ADMIN_CODE_PREFIX` 配置）；
2. 管理员创建普通邀请码（可设置初始 token/请求/章节额度）。
   当前通过管理接口创建：`POST /api/admin/invite-codes`（需管理员 token）；
3. **读者/作者**：在登录页输入邀请码，即完成注册 + 登录，获得 7 天 JWT；
4. 生成操作消耗额度；**阅读全文不消耗额度**（注册即可阅读所有已分享小说）。

额度体系数据表：`invite_codes`（邀请码）、`user_quotas`（额度）、
`user_token_usage_log`（使用日志），均位于主数据库（`NOVEL_DB_PATH`）。

::: warning 注册即全文
开源版不设置付费墙：匿名用户只能试读（默认前 3 章），
注册用户可阅读全文。付费会员是商业版能力，接口已预留扩展位。
:::

## casdoor 模式（企业 SSO）

需要部署 casdoor-auth-sidecar（认证边车，见 [部署指南](./deploy.md)）：

```bash
NOVEL_AUTH_MODE=casdoor
NOVEL_AUTH_SIDECAR_URL=http://localhost:9098
NOVEL_PUBLIC_ORIGIN=https://world-novel.programtree.cn   # 回调地址用
```

浏览器登录由 sidecar 代理到 Casdoor，会话 token 经
`/api/auth/sidecar/*` 系列接口验证与续期。兼容旧配置：
`NOVEL_AUTH_ENABLED=true` 等价于 `NOVEL_AUTH_MODE=casdoor`。

## disabled 模式（仅开发）

```bash
NOVEL_AUTH_MODE=disabled
```

所有接口开放、无额度限制。**不要用于公网环境。**

## 相关安全设计

- 登录接口限流：单 IP 每分钟 ≤ 20 次（防邀请码爆破）；
- 公开分享页限流：单 IP 每分钟 ≤ 60 次；
- JWT 使用 HS256 签名，有效期 7 天，过期后自动回退为匿名（试读）权限。
