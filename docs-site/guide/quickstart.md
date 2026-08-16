# 快速开始

## 环境要求

- Python ≥ 3.11（推荐 [uv](https://docs.astral.sh/uv/)）
- Node.js ≥ 20（构建前端工作台）
- 一个 OpenAI 兼容的 LLM API（OpenAI / OpenRouter / 任意兼容网关）

## 1. 获取源码

```bash
git clone https://github.com/Yourdaylight/world-novel.git
cd world-novel
```

## 2. 安装依赖

```bash
# 后端（uv 会自动创建 .venv）
uv sync

# 前端工作台
cd web && npm install --legacy-peer-deps && cd ..
```

> 说明：`web/package.json` 中 vite 主版本较新，若 npm 报告 peer 依赖冲突，
> 使用 `--legacy-peer-deps` 即可，不影响构建。

## 3. 配置环境变量

```bash
cp .env.example .env
```

最小配置：

```bash
NOVEL_LLM_PROVIDER=openai
NOVEL_OPENAI_API_KEY=sk-xxxx
NOVEL_OPENAI_BASE_URL=https://api.openai.com/v1
NOVEL_AUTH_MODE=jwt          # 开源默认：邀请码 + JWT
```

常用配置项见 [认证配置](./auth)。

## 4. 启动开发环境

```bash
make dev
```

- 后端 API：`http://localhost:8000`
- 前端工作台（Vite dev server）：`http://localhost:5173`

生产模式（构建前端后单进程托管）：

```bash
make prod
```

## 5. 创建第一部小说

1. 打开工作台首页 → **创建世界**，填写三命题（世界是什么 / 从哪里来 / 到哪里去）；
2. 在「控制台」启动生成流水线（七阶段：命题 → 大纲 → 世界观 → 角色 → 模拟 → 写作 → 审校）；
3. 在「章节」页查看成书；
4. 在「成书发布」页运行质量门禁并导出，或在「分享阅读」页生成公开链接。

## 6. 常用命令

```bash
make dev          # 开发模式（前后端热重载）
make prod         # 生产模式（构建前端，单 uvicorn 进程）
make test         # 后端单元测试
make smoke        # 冒烟测试（需服务运行中）
```

## 下一步

- [认证配置](./auth)：邀请码、JWT、Casdoor 企业认证
- [成书发布](./publish)：导出到番茄 / 七猫
- [分享与注册阅读](./share)：公开链接与读者权限
