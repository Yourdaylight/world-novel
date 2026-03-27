# 🌍 WorldEngine — 多Agent小说生成系统

> **造物主的创世工坊**：通过三个终极命题定义世界，由AI Agent团队自动生成完整小说。

## 概览

WorldEngine 是一个基于多Agent协作的长篇小说自动生成系统。每个角色都是独立的AI Agent，拥有自己的记忆、情感、关系网络和行动逻辑。系统通过 LangGraph 编排 7 个阶段的流水线，从世界观构建到章节写作全程自动化，同时提供 Web 可视化仪表板实时观察每个 Agent 的心理活动和交互。

### 核心特性

- 🎭 **独立Agent意识** — 每个角色独立思考、对话、行动、反应，拥有情景记忆和情感状态
- 📜 **史官对话** — 与掌握全部角色记忆的AI史官对话，指导撰写、分析剧情、生成章节片段
- 🔮 **命运裁决** — God Agent 在章节间审视世界走向，触发世界事件和支线剧情
- 📊 **伏笔系统** — 自动规划伏笔埋设与回收，跨章节剧情线追踪
- 🌍 **三命题创世** — 通过"是什么/从何来/往何去"三个终极命题定义世界本质
- ⏸ **暂停/继续** — 随时暂停生成，修改世界观或角色设定后继续，新设定自动融入
- 📥 **成书导出** — Markdown/JSON 一键导出，文件管理器下载所有工作区文件

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web 仪表板 (Vue 3 SPA)                │
│  概览 │ 世界观 │ 角色 │ 大纲 │ 伏笔 │ 章节 │ 成书 │ 史官 │ 控制台  │
└────────────────────────┬────────────────────────────────┘
                         │ REST API + WebSocket
┌────────────────────────┴────────────────────────────────┐
│                  FastAPI 后端 (Python)                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           LangGraph Pipeline (7 阶段)             │   │
│  │                                                    │   │
│  │  Director → World → Foreshadow → Scene → Write    │   │
│  │                                    ↕               │   │
│  │                              God Agent             │   │
│  │                                    ↓               │   │
│  │                               Compile              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │ 角色 Agent  │ │ 史官 Agent  │ │ 命运 Agent (God)   │   │
│  │ ·独立记忆   │ │ ·全局知识   │ │ ·世界事件          │   │
│  │ ·情感状态   │ │ ·对话撰写   │ │ ·支线触发          │   │
│  │ ·关系网络   │ │ ·文件输出   │ │ ·叙事指引          │   │
│  └────────────┘ └────────────┘ └────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              SQLite 持久层 (per novel)             │   │
│  │  characters │ actions │ memories │ emotions       │   │
│  │  world │ outline │ foreshadows │ timeline │ god   │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 生成流水线

```
1. 📋 导演规划 (Director)
   ├── 注入三个终极命题
   ├── 生成故事大纲 (章节+场景)
   ├── 创建角色档案与关系图谱
   └── 初始化时间线

2. 🌍 世界观构建 (World Builder)
   ├── 力量体系、势力、地点、历史
   └── 持久化到 world_building 表

3. 📊 伏笔规划 (Foreshadow Planner)
   ├── 规划伏笔埋设与回收点
   ├── 创建剧情线
   └── 为每个场景分配伏笔任务

4. 🎭 场景模拟 (Scene Simulation) ← 逐章循环
   ├── Round 1: 每个角色独立行动 (并行)
   │   └── 角色Agent: 回忆 → 思考 → 行动/对话
   ├── Round 2: 角色互相反应 (并行)
   │   └── 看到他人行动后反应
   └── 记录: 行动、情感变化、情景记忆、关系变化

5. ✍️ 章节写作 (Writer)
   ├── 基于场景行动记录撰写文学叙事
   ├── 融入伏笔暗示和命运指引
   └── 800-1500字/场景

6. 🔮 命运裁决 (God Agent) — 每章结束后
   ├── 审视世界走向
   ├── 触发世界事件 (资本暗战、隐世追踪...)
   ├── 触发支线 (内部裂痕、信任试炼...)
   ├── 时间推进决策
   └── 下章叙事指引

7. 📖 编译成书 (Compile) — 全部章节完成后
   └── 汇总所有章节为完整小说
```

---

## 角色Agent系统

每个角色是独立的AI Agent，拥有：

| 维度 | 说明 |
|------|------|
| **身份档案** | 姓名、角色定位、背景故事、说话风格、目标、隐藏目标 |
| **情景记忆** | 每个场景后记录发生了什么，按重要度和情感倾向排序 |
| **情感状态** | 6维情感: 快乐/愤怒/恐惧/悲伤/信任/惊讶 (-1.0 ~ 1.0) |
| **关系网络** | 与每个角色的关系类型、信任值、好感值，动态演化 |
| **行动记录** | 4种类型: 💬对话 / 💭内心独白 / ⚡行为 / 🔄反应 |
| **灵魂文件** | `soul.md` 可编辑的深层性格设定，影响Agent决策 |

### Agent交互流程

```
场景开始
  ├── 角色A: 回忆相关记忆 → 感知环境 → 独立行动
  ├── 角色B: 回忆相关记忆 → 感知环境 → 独立行动
  ├── 角色C: ...
  │
  ├── 角色A: 看到B和C的行动 → 反应
  ├── 角色B: 看到A和C的行动 → 反应
  ├── 角色C: ...
  │
  └── 各角色: 更新情感 → 存储记忆 → 更新关系
```

---

## Web 仪表板

### 页面结构

| 页面 | 功能 |
|------|------|
| **📖 概览** | 创世面板 (开始/暂停/继续) + 三命题展示 + 实时事件日志 + 统计 |
| **🌍 世界观** | 力量体系/势力/地点/历史卡片，支持在线编辑并保存 |
| **👥 角色** | 关系图谱 + 角色列表，点击查看完整档案 (行动记录/记忆/情感轨迹) |
| **📋 大纲与时间线** | 故事大纲 (章节+场景可展开) + 时代事件 + 命运决策详情 |
| **🔮 伏笔** | 伏笔列表 (状态追踪) + 剧情线 |
| **📝 章节** | 逐章阅读已完成章节 |
| **📚 成书** | 完整小说阅读 + Markdown/JSON导出 + 文件管理器 |
| **📜 史官** | 与AI史官对话 (历史持久化)，讨论剧情/撰写片段/分析角色 |
| **⚙️ 控制台** | 运行控制 + 检查点列表 |

### 史官对话

史官是一个特殊的AI Agent，掌握当前世界的全部信息：
- 所有角色的每一句话、每一个想法、每一个行动
- 世界观、大纲、伏笔、命运决策
- 角色关系演化历史

你可以让史官：
- 基于角色记忆撰写章节片段、内心独白、对话场景
- 分析角色关系发展和剧情冲突
- 建议新角色、新剧情线
- 输出文档到工作区供下载

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (Python包管理)

### 安装

```bash
# 安装所有依赖
make install

# 复制环境配置
cp .env.example .env
# 编辑 .env 填入你的 LLM API 配置
```

### 配置 LLM

编辑 `.env`，支持任何 OpenAI 兼容 API：

```env
# LLM API (OpenAI / Kimi / DeepSeek / 等)
NOVEL_OPENAI_API_KEY=sk-your-key
NOVEL_OPENAI_BASE_URL=https://api.openai.com/v1

# 模型配置 (所有Agent共用或分别指定)
NOVEL_DIRECTOR_MODEL=gpt-4o      # 导演/审校/史官
NOVEL_CHARACTER_MODEL=gpt-4o-mini # 角色Agent (调用频繁)
NOVEL_WRITER_MODEL=gpt-4o        # 写手Agent
NOVEL_GOD_MODEL=gpt-4o           # 命运Agent
```

### 本地运行

```bash
# 开发模式 (前后端热重载)
make dev

# 生产模式 (前端打包，单进程)
make prod
```

打开 http://localhost:8000 → 首页 → 创建新世界 → 开始创世

### 远程部署

```bash
# 一键部署到远程服务器
make deploy HOST=user@host PORT=8800

# 仅同步代码并重启
make deploy-code HOST=user@host

# 查看远程日志
make logs HOST=user@host
```

---

## CLI 命令

```bash
# 生成小说 (CLI模式)
novel-creator generate --genre 玄幻 --premise "..." --chapters 10

# 从检查点恢复
novel-creator resume

# 书架管理
novel-creator novels             # 列出所有小说
novel-creator novels create -t "书名" -g "类型"
novel-creator novels select 小说ID
novel-creator novels export      # 导出Markdown
novel-creator novels delete 小说ID

# 查看数据
novel-creator world              # 世界观
novel-creator timeline           # 时间线
novel-creator review             # 伏笔审查
novel-creator status             # 生成进度
novel-creator agents             # Agent文件状态

# 同步Agent文件
novel-creator sync --direction export  # DB → 文件
novel-creator sync --direction import  # 文件 → DB

# 启动Web
novel-creator web --port 8000
```

---

## 数据结构

每个小说世界独立存储在 `data/novels/{novel_id}/` 目录：

```
data/novels/玄尘界/
├── novel.db              # SQLite 数据库 (所有结构化数据)
├── agents/               # Agent 文件 (可人工编辑)
│   ├── hero/
│   │   ├── agent.md      # 角色Agent提示词
│   │   └── soul.md       # 角色灵魂文件 (深层性格)
│   ├── villain/
│   ├── heroine/
│   └── god/
│       ├── agent.md      # God Agent提示词
│       └── decisions.md  # 命运决策记录
└── historian/            # 史官输出文件 (可下载)
    └── *.md
```

### 数据库表

| 表 | 说明 |
|----|------|
| `characters` | 角色档案 (profile_json) |
| `character_actions` | 行动记录 (对话/思考/行为/反应) |
| `episodic_memories` | 情景记忆 |
| `emotional_states` | 情感状态历史 |
| `relationships` | 角色关系 (信任/好感) |
| `world_building` | 世界观 JSON |
| `story_outline` | 故事大纲 JSON |
| `chapter_texts` | 章节文本 |
| `foreshadows` | 伏笔追踪 |
| `plot_threads` | 剧情线 |
| `story_eras` | 时代划分 |
| `timeline_events` | 时间线事件 |
| `god_decisions` | 命运决策 |
| `generation_checkpoints` | 检查点 (暂停/恢复) |
| `world_propositions` | 三个终极命题 |

---

## API 参考

### 小说管理
- `GET /api/novels` — 列出所有小说
- `POST /api/novels/select` — 切换活跃小说
- `POST /api/worlds/create` — 创建新世界
- `DELETE /api/worlds/{id}` — 删除世界

### 生成控制
- `POST /api/worlds/{id}/generate` — 开始生成
- `POST /api/worlds/{id}/resume` — 从检查点继续
- `POST /api/worlds/{id}/pause` — 暂停生成
- `GET /api/worlds/{id}/status` — 综合状态

### 数据查询
- `GET /api/world` — 世界观
- `GET /api/outline` — 大纲
- `GET /api/story` — 角色列表
- `GET /api/relationships` — 关系图谱
- `GET /api/chapters` — 章节列表
- `GET /api/chapter-text/{idx}` — 章节内容
- `GET /api/novel-full` — 完整小说
- `GET /api/timeline` — 时间线
- `GET /api/god-decisions` — 命运决策
- `GET /api/foreshadows` — 伏笔
- `GET /api/plot-threads` — 剧情线
- `GET /api/progress` — 生成进度

### 角色详情
- `GET /api/characters/{id}/full-profile` — 完整档案+统计
- `GET /api/characters/{id}/actions-all` — 全部行动记录
- `GET /api/characters/{id}/memories` — 全部记忆
- `GET /api/emotions/{id}` — 情感历史

### AI 交互
- `POST /api/ai/historian-chat` — 与史官对话
- `POST /api/ai/analyze-proposition` — 命题分析
- `POST /api/ai/historian-write-file` — 史官输出文件

### 导出与文件
- `GET /api/worlds/{id}/export/markdown` — 导出Markdown
- `GET /api/worlds/{id}/export/json` — 导出世界数据
- `GET /api/worlds/{id}/files` — 列出工作区文件
- `GET /api/worlds/{id}/files/download?path=` — 下载文件

### 编辑
- `PUT /api/world` — 保存世界观
- `PUT /api/agents/{id}/soul` — 编辑角色灵魂文件

---

## 技术栈

| 层 | 技术 |
|----|------|
| **前端** | Vue 3 + TypeScript + Pinia + Element Plus + SCSS |
| **后端** | FastAPI + Pydantic + aiosqlite |
| **AI编排** | LangGraph (状态机图) |
| **LLM** | LangChain + ChatOpenAI (兼容任何OpenAI API) |
| **通信** | REST API + WebSocket (实时事件推送) |
| **存储** | SQLite (per novel) + JSON Registry + Agent文件 |
| **部署** | uv + npm + rsync + tmux |

---

## License

MIT
