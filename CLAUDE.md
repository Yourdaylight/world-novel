# CLAUDE.md — WorldEngine

## 项目概述
WorldEngine 是一个多Agent小说生成系统。每个角色是独立AI Agent，拥有自己的记忆、情感、关系网络。通过 LangGraph 编排7阶段流水线自动生成长篇网文。

## 技术栈
- 后端: Python 3.11+ / FastAPI / LangGraph / LangChain / aiosqlite
- 前端: Vue 3 / TypeScript / Element Plus / SCSS / ECharts / vis-network
- 包管理: uv (Python) / npm (前端)

## 设计系统
在做任何视觉或UI决策之前，必须先阅读 DESIGN.md。
所有字体选择、颜色、间距和美学方向都在该文件中定义。
不得在未经用户明确同意的情况下偏离设计系统。
在QA模式下，标记任何不符合 DESIGN.md 的代码。

## 常用命令
```bash
make install    # 安装所有依赖
make dev        # 开发模式 (前后端热重载)
make prod       # 生产模式
```

## 目录结构
- `src/novel_creator/` — Python后端源码
- `web/` — Vue 3前端
- `web/src/styles/` — SCSS样式文件
- `docs/product/` — 产品设计文档
- `data/novels/` — 小说数据 (per-novel SQLite)
