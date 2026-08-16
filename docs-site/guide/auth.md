# 认证配置

WorldNovel 支持三种认证模式，由环境变量 `NOVEL_AUTH_MODE` 切换：

| 模式 | 适用场景 | 用户身份 |
| --- | --- | --- |
| `jwt`（默认） | 开源版 / 个人部署 | 邀请码即账号，登录签发 JWT |
| `casdoor` | 企业部署 | Casdoor Sidecar 统一认证（SSO） |
| `disabled` | 本地开发 / 内网试用 | 所有接口匿名开放 |

## jwt 模式（邀请码 + JWT）

开源版默认模式，也是「分享阅读 → 注册读全书」的用户体系基础。

### 工作流

1. 管理员创建邀请码（Token 统计页 / 直接写库）；
2. 读者在登录页输入邀请码 → `POST /api/auth/login`；
3. 校验通过后签发 7 天有效的 JWT（HS256），前端以 `X-User-Token` 头携带；
4. **邀请码即账号**：首次登录自动创建用户档案（额度记录）。

```bash
NOVEL_AUTH_MODE=jwt
# JWT 密钥：生产环境务必修改
WORLDENGINE_JWT_SECRET=请改成随机长字符串
```

> 安全提示：默认密钥仅用于本地开发。生产环境必须设置 `WORLDENGINE_JWT_SECRET`
> 为随机长字符串，否则任何人都可以伪造令牌。code 以 `admin` 开头的邀请码自动具备管理员权限。

### 创建邀请码

通过管理员接口（需 admin 身份）：

```bash
curl -X POST http://localhost:8000/api/admin/invite-codes \
  -H "X-User-Token: <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"code": "reader001", "max_uses": 0, "description": "读者邀请码"}'
```

`max_uses=0` 表示不限使用次数。

## casdoor 模式（企业 SSO）

通过 [casdoor-auth-sidecar](https://github.com/Yourdaylight/world-novel) 对接 Casdoor：

```bash
NOVEL_AUTH_MODE=casdoor
NOVEL_AUTH_SIDECAR_URL=http://localhost:9098
NOVEL_PUBLIC_ORIGIN=https://your-domain
```

此模式下登录页自动变为「前往统一认证中心」SSO 跳转。Sidecar 负责 OAuth 流程与会话校验。

## disabled 模式

```bash
NOVEL_AUTH_MODE=disabled
```

所有接口无需登录，分享阅读页所有访问者都按「注册用户」对待（可读全书）。
**仅限本地开发或完全可信的内网环境使用。**

## 认证与分享阅读的关系

| 身份 | 分享页权限 |
| --- | --- |
| 匿名（无 token / token 失效） | 封面、简介、目录、试读章节 |
| 注册用户（有效 JWT / Sidecar 会话） | **全书** + 书架 + 阅读进度 |
| 作者（分享创建者） | 全书 + 分享管理（关闭、改试读策略、看数据） |

开源版**注册即全文**，不设付费会员；付费会员 / 订阅为商业版预留能力
（数据模型已预留 `user_quotas.plan_type` 扩展位）。
