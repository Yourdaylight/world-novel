# 认证配置

WorldNovel 的认证模式由 `NOVEL_AUTH_MODE` 控制，三态可选：

| 模式 | 取值 | 适用场景 |
|------|------|---------|
| 邀请码 + JWT | `jwt`（默认） | 开源版、个人/小团队部署 |
| Casdoor 单点登录 | `casdoor` | 企业内网、统一身份 |
| 关闭认证 | `disabled` | 本地开发、隔离环境 |

## jwt：邀请码 + JWT（开源默认）

- 用户身份即**邀请码**：输入有效邀请码登录，服务端签发 7 天有效的 HS256 JWT；
- 邀请码需要管理员预先创建（带使用次数上限）；
- 登录、额度接口：

```bash
# 登录（邀请码即账号）
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"invite_code":"你的邀请码"}'
# → { access_token, code, quota }

# 携带令牌
curl http://localhost:8000/api/auth/me -H "X-User-Token: <token>"
```

令牌支持 `X-User-Token` 头、`Authorization: Bearer` 与 `?token=` 三种传递方式。

### 创建邀请码

使用 Python：

```python
import asyncio
from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import create_invite_code

async def main():
    conn = await get_connection(settings.db_path)
    code = await create_invite_code(conn, description="读者邀请", max_uses=1)
    await conn.close()
    print(code)

asyncio.run(main())
```

以 `admin` 开头的邀请码自动获得管理员身份且不限额度。

### JWT 密钥

生产环境**必须**覆盖默认密钥，两种方式任选：

```bash
# 方式一：进程环境变量（systemd Environment 或 export，优先级最高）
WORLDENGINE_JWT_SECRET=$(openssl rand -hex 32)

# 方式二：写入项目根目录 .env（pydantic-settings 自动加载）
NOVEL_JWT_SECRET=<强随机密钥>
```

未配置时，服务每次启动会自动生成一个临时随机密钥并打印醒目警告
（重启后所有登录失效）——杜绝"源码公开默认密钥被用来伪造令牌"的风险。

## casdoor：企业 SSO

需要部署 casdoor-auth-sidecar 并配置：

```bash
NOVEL_AUTH_MODE=casdoor
NOVEL_AUTH_SIDECAR_URL=http://127.0.0.1:9098
NOVEL_PUBLIC_ORIGIN=https://your.domain
```

前端登录/登出会自动走 sidecar 的 OAuth 流程，接口层对业务代码透明。

## disabled：关闭认证

```bash
NOVEL_AUTH_MODE=disabled
```

所有 `require_auth` 接口放行（识别为 `anonymous`）。**仅限可信网络/本地开发**。

## 「注册即全文」与商业版预留

公开分享的阅读权限（见[分享指南](./share)）：

- 匿名访客 → 仅试读；
- `require_auth` 通过（jwt 邀请码登录 / casdoor 登录）→ **全文可读**。

开源版不设付费会员、不接支付；数据模型中 `user_quotas.plan_type` 已为商业版付费会员预留扩展位，届时"注册权益"与"会员权益"可拆分而不影响现有接口。
