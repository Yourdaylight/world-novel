# 快速开始

WorldNovel 是一个多 Agent 长篇小说自动生成系统：每个角色是独立 AI Agent，
拥有自己的记忆、情感与关系网络，通过 LangGraph 七阶段流水线自动演化并成书。

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 推荐用 [uv](https://astral.sh/uv) 管理 |
| Node.js | ≥ 20.19（推荐 22 LTS） | 前端构建工具 Vite 8 的引擎要求 |
| LLM API Key | — | OpenAI / OpenRouter / DeepSeek 等兼容接口 |

可选服务（默认不启用）：Qdrant（向量检索）、Neo4j（关系图谱），见 `docker-compose.yml`。

## 安装

```bash
git clone https://github.com/Yourdaylight/world-novel.git
cd world-novel

cp .env.example .env    # 然后编辑 .env，填入你的 API Key

make install            # = uv sync + cd web && npm install
```

::: tip 国内网络提示
前端依赖如遇安装失败，可先设置 npm 镜像：`npm config set registry https://registry.npmmirror.com`
:::

## 配置 LLM

编辑 `.env`（三种 Provider 任选其一）：

```bash
# 方式一：OpenAI 官方
NOVEL_OPENAI_API_KEY=sk-...
NOVEL_OPENAI_BASE_URL=https://api.openai.com/v1

# 方式二：OpenRouter（一个 Key 用所有模型）
NOVEL_LLM_PROVIDER=openrouter
NOVEL_OPENROUTER_API_KEY=sk-or-v1-...
NOVEL_DIRECTOR_MODEL=openai/gpt-4o

# 方式三：任意 OpenAI 兼容接口（DeepSeek / 月之暗面 / 本地 Ollama）
NOVEL_OPENAI_API_KEY=your-key
NOVEL_OPENAI_BASE_URL=https://api.deepseek.com/v1
NOVEL_DIRECTOR_MODEL=deepseek-chat
```

三个核心模型分工：

- `NOVEL_DIRECTOR_MODEL` — 故事总规划（需要强推理，推荐 gpt-4o 级）
- `NOVEL_CHARACTER_MODEL` — 角色 Agent（调用频繁，推荐性价比模型）
- `NOVEL_WRITER_MODEL` — 史官/叙述（需要文学表达力）

## 启动

```bash
make dev        # 开发模式：后端 :8000 + 前端热重载 :5173
make prod       # 生产模式：构建前端后单进程服务 :8000
```

打开 <http://localhost:5173>（开发）或 <http://localhost:8000>（生产）。

## 第一次成书

1. 首页点击「开始创作」，填写书名、类型、三大世界命题；
2. 系统自动经历：世界构建 → 角色生成 → 大纲规划 → 逐章模拟与写作；
3. 在「章节」页阅读正文，在「大纲与时间线」页查看结构；
4. 成书后到「发布」页一键导出到番茄/七猫（见 [一键发布](./publish.md)），
   或在「分享管理」生成公开阅读链接（见 [分享与注册阅读](./share.md)）。

## 邀请码与登录

开源版默认 `auth_mode=jwt`：管理员邀请码（以 `admin` 开头的 code）登录后，
通过管理接口创建普通邀请码分发给用户：

```bash
# 管理员登录后，用返回的 access_token 创建邀请码
curl -X POST http://localhost:8000/api/admin/invite-codes \
  -H "X-User-Token: $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"max_uses": 10, "initial_tokens": 100000, "initial_requests": 500}'
```

::: info 首个管理员码
全新数据库会自动播种默认管理员邀请码 `admin_default`（见迁移脚本 006），
生产环境请立即创建自己的 admin 码并删除/停用它。
:::

详见 [认证配置](./auth.md)。

## 常用命令速查

```bash
make help           # 全部命令
make lint           # ruff + vue-tsc 检查
make test           # 单元测试
make smoke          # 冒烟测试（需服务运行中）
make ci             # 完整 CI：lint → test → build → smoke
```

## 下一步

- [认证配置](./auth.md) — jwt / casdoor / disabled 三模式
- [一键发布](./publish.md) — 番茄/七猫导出规范
- [分享与注册阅读](./share.md) — 公开链接与读者体系
- [部署指南](./deploy.md) — systemd / Docker / nginx
