# 快速开始

WorldNovel 后端为 Python 3.11+ / FastAPI / LangGraph，前端为 Vue 3 + Vite。推荐用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖。

## 1. 获取代码

```bash
git clone https://github.com/Yourdaylight/world-novel.git
cd world-novel
```

## 2. 安装依赖

```bash
make install
# 等价于：uv sync（后端）+ cd web && npm install（前端）
```

> 如遇到 npm peer 依赖冲突（vite 与插件版本），可在 `web/` 下用 `npm install --legacy-peer-deps`。

## 3. 配置环境变量

```bash
cp .env.example .env
```

至少配置 LLM 与认证：

```bash
# LLM（OpenAI 兼容接口或 OpenRouter）
NOVEL_LLM_PROVIDER=openai
NOVEL_OPENAI_API_KEY=sk-xxxx
NOVEL_OPENAI_BASE_URL=https://api.openai.com/v1

# 认证模式：jwt（开源默认）/ casdoor（企业）/ disabled（开发）
NOVEL_AUTH_MODE=jwt
WORLDENGINE_JWT_SECRET=请改成随机字符串
```

全部环境变量见 [环境变量参考](/reference/env)。

## 4. 启动

```bash
make dev          # 开发模式：FastAPI :8000 + Vite :5173（热重载）
# 或生产模式
make prod         # 构建前端并由 FastAPI 托管静态产物
```

- 开发：打开 `http://localhost:5173`
- 生产/API：`http://localhost:8000`，健康检查 `GET /api/health`

也可以直接用 uvicorn：

```bash
NOVEL_AUTH_MODE=jwt uv run uvicorn novel_creator.web.app:app --host 0.0.0.0 --port 8000
```

## 5. 创建第一部小说

1. 打开工作台，点击「创建世界」，填写书名、类型与三个终极命题；
2. 进入「控制台」开始生成（七阶段流水线）；
3. 在「章节」页阅读成文，在「发布」页导出，在「分享」页生成公开链接。

## 6. 邀请码（jwt 模式）

jwt 模式下「邀请码」既是登录凭证也是注册凭证。管理员（code 以 `admin` 开头）可通过 CLI 或直接写库发放：

```bash
uv run python -c "
import asyncio
from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import create_invite_code
async def main():
    c = await get_connection(settings.db_path)
    print(await create_invite_code(c, code='admin_seed', max_uses=0))  # 0=不限次
    await c.close()
asyncio.run(main())
"
```

读者在公开阅读页用邀请码「注册 / 登录」后即可阅读全书（开源版注册即全文）。

## 下一步

- [认证配置](/guide/auth)
- [成书一键发布](/guide/publish)
- [公开分享与注册阅读](/guide/share)
- [独立部署](/guide/deploy)
