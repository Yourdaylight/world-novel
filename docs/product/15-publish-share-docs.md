# 15 — 需求设计：成书发布、分享阅读与独立文档站

> **定位**：WorldNovel开源项目开发。https://github.com/Yourdaylight/world-novel 
> github access token:（已隐去）
> **关联文档**：[01-产品愿景](./01-vision.md)、[02-系统架构](./02-architecture.md)、[06-商业模式](./06-pricing.md)、[08-里程碑路线图](./08-roadmap.md)

---

## 1. 背景与目标

### 1.1 背景

WorldNovel 当前已具备：多 Agent 世界演化与成书生成、角色技能系统、记忆系统、token 额度系统（邀请码 + JWT）、Casdoor 企业认证（可配置）、完整作者工作台前端。但产品闭环停留在"作者自己生成、自己看"：

- 成书后无法触达外部读者（无发布通道）；
- 作者之间、作者与读者之间无分享与消费逻辑（无公开阅读、无读者注册链路）；
- 对外形象页（`website/index.html`）是单文件宣传页，无 GitHub 入口、无使用文档，且未部署。

### 1.2 目标（本期三个能力）

| # | 能力 | 一句话描述 |
|---|------|-----------|
| A | **成书一键发布** | Agent 自行演进完成后，成书可一键发布到番茄/七猫等外部小说平台 |
| B | **公开分享 + 注册阅读** | 用户生成的小说可生成公开地址分享；匿名读者只能试读（默认前 3 章），**注册平台账号后即可看全部**（开源版"注册即会员"，付费会员为商业版预留） |
| C | **Index 首页 + 独立文档站** | 首页附 GitHub 链接；提供使用文档页；文档站与首页可独立部署（不依赖后端） |

### 1.3 非目标（本期不做）

- 不做多作者协作编辑；不做站内评论/打赏；不做移动端 App；不承诺对接任何平台的"官方开放 API"（现实约束见 §3.2）。

---

## 2. 现状盘点（代码事实）

| 项 | 现状 | 与本期关系 |
|----|------|-----------|
| 后端 | FastAPI，`world-novel.service`（uvicorn :8000） | 分享/阅读接口挂载于此 |
| 认证 | `auth_mode` 三态：`jwt`（默认开源）/ `casdoor` / `disabled`；token 额度系统（`invite_codes`/`user_quotas` 表） | 注册即全文的用户体系复用它 |
| 生成 | LangGraph 七阶段流水线，章节落 `chapter_texts` 表，成书有质量门禁基础（`generation_checkpoints`） | 发布前置条件 |
| 数据 | 每部小说独立 SQLite（`data/novels/{novel}/novel.db`），`volumes`/`chapter_texts`/`story_outline` 等 20+ 表 | 分享/发布直接读这些表 |
| 前端 | Vue3 工作台路由：`/`、`/create`、`/world/:novelId/{overview,world-view,characters,timeline,foreshadows,chapters,historian,tokens,control}` | 缺**读者阅读页**与**分享管理页** |
| 对外页 | `website/index.html`（1650 行单文件，Tailwind CDN）；`world-novel-theme/` 主题模板；`docs/product/` 14 篇设计文档 | 需要拆站/文档化/独立部署 |
| 线上 | `world-novel.programtree.cn` → 43.142.141.74；systemd + uvicorn + casdoor-auth-sidecar；Qdrant/Neo4j 可选（docker-compose） | 部署方案基于此拓扑 |

---

## 3. 需求 A：成书一键发布到番茄/七猫

### 3.1 用户故事

> 作为作者，我在"成书"页面点击"发布到番茄小说"，系统自动完成格式整理、封面/简介生成，打开发布向导；我确认后成书进入番茄作家后台草稿箱（或完成导出），我可继续在平台侧完成实名认证与最终发布。

### 3.2 平台现实约束（设计前提，务必在评审时确认）

| 平台 | 作者入口 | 开放 API | 结论 |
|------|---------|---------|------|
| 番茄小说 | 番茄作家助手（App/网页） | **无公开开放 API** | 只能浏览器自动化或导出后手动上传 |
| 七猫小说 | 七猫作家平台（网页） | **无公开开放 API** | 同上 |
| 起点/晋江等 | 各自作家后台 | 均无开放 API | 同上 |

**因此"一键发布"必须分层定义**，避免把不可承诺的"全自动直发"写死进需求：

- **L0 一键导出**（必做，MVP）：成书按平台规范导出 TXT/EPUB/Word（含分卷、章节、封面占位、简介、标签），一键打包下载；作者在平台侧上传。
- **L1 半自动发布**（选做）：Playwright 无头浏览器驱动作家后台，自动填充书名/简介/章节，停在"提交审核"前由人确认（防误发、防风控）。
- **L2 全自动直发**（不做/远期）：仅当某平台开放 API 或出现合规第三方渠道时才做。

### 3.3 功能需求

| ID | 需求 | 优先级 |
|----|------|--------|
| A-1 | 发布前质量门禁：章节完整性（无空章/断章）、字数统计、敏感词预检（本地词表）、封面/简介自动生成（AI 或模板） | P0 |
| A-2 | 按平台输出规范导出（番茄：每章 ≤ 2000 字推荐、TXT 编码 GB18030；七猫：支持分卷导入） | P0 |
| A-3 | 发布记录管理：`publication_records` 记录每次导出/发布的时间、平台、目标书 ID、状态 | P0 |
| A-4 | （L1）发布向导：选择平台 → 校验账号登录态 → 预填表单 → 人工确认 → 提交草稿 | P1 |
| A-5 | 发布后回流：作者在平台侧的链接/书 ID 回填，系统记录"已发布"状态 | P1 |

### 3.4 数据模型设计

```
publication_records
├── id            TEXT PK            -- 记录 ID
├── novel_id      TEXT               -- 关联小说（novels 表）
├── platform      TEXT               -- fanqie | qimao | txt | epub | ...
├── stage         TEXT               -- draft | exporting | exported | publishing | published | failed
├── target_book_id TEXT              -- 平台侧书 ID（发布后回填）
├── target_url    TEXT               -- 平台侧链接（发布后回填）
├── export_meta   JSON               -- {chapters, words, format, encoding, cover}
├── operator      TEXT               -- 触发人（JWT code / sidecar sub）
├── created_at / updated_at
```

导出规范建议沉淀为平台适配表 `platform_profiles`（平台名、分卷支持、章节字数建议、编码、封面上传要求），便于新增平台。

### 3.5 关键接口（设计）

```
POST /api/publish/preflight      -- 质量门禁预检，返回 {ok, warnings, stats}
POST /api/publish/export         -- 按平台导出，返回下载包/任务 ID
POST /api/publish/{id}/confirm   -- (L1) 确认提交草稿
GET  /api/publish/records        -- 发布历史
```

---

## 4. 需求 B：公开分享 + 注册阅读

### 4.1 用户故事

> 作者把小说"分享"生成一个公开链接（如 `world-novel.programtree.cn/read/9f3k2a`），发到群里。路人点开能看到封面、简介、目录和前 3 章试读；想继续读，需要注册平台账号（开源版邀请码注册，注册即全文）；注册后可全文阅读、记录进度、加入书架。作者在"分享管理"里可随时关闭分享、设置试读章节数、查看阅读数据。

> **开源决策（已确认）**：本期**不设置付费会员、不接支付**。访问控制简化为"匿名=试读，注册=全文"。付费会员/订阅（Casdoor Commerce 支付）为商业版预留，接口与数据模型预留扩展位但不实现。

### 4.2 权限模型（四级）

| 级别 | 身份 | 可访问内容 |
|------|------|-----------|
| L0 匿名 | 未登录 | 封面/简介/目录/试读章节（默认前 3 章，可配置） |
| L1 注册 | 已注册（开源版邀请码） | **全文** + 书架 + 进度同步 |
| L2 作者 | 小说所有者 | 全部 + 管理（关闭分享、改试读、看数据） |

> 付费会员（L1.5）为商业版预留：届时 L1 拆分为"注册=试读上限提升"与"会员=全文"，`user_quotas.plan_type` 字段已具备扩展条件，本期不启用。

试读策略做成**可配置**：`share_links.trial_mode = first_n_chapters | word_count | ratio`，默认前 3 章；VIP 小说可设 0 章（完全付费）。

### 4.3 数据模型设计

```
share_links
├── id            TEXT PK            -- 分享 ID（不可枚举：uuid 短码 ≥ 8 位）
├── novel_id      TEXT
├── owner_id      TEXT               -- 作者（JWT code / sidecar sub）
├── title/cover/intro_snapshot      -- 分享页展示的元数据快照（防改原文影响分享页）
├── trial_mode / trial_value        -- 试读策略
├── status        TEXT               -- active | disabled
├── view_count / read_count         -- 统计
├── created_at / disabled_at

read_progress（书架/进度）
├── user_code / novel_id / chapter_index / last_read_at
```

> **memberships 表本期不建**：开源版"注册即全文"，`require_auth` 通过即放行全文（jwt 模式的邀请码注册即用户）。商业版付费会员再建 `memberships` 表并扩展现有 `user_quotas.plan_type`。

### 4.4 功能需求

| ID | 需求 | 优先级 |
|----|------|--------|
| B-1 | 分享管理：创建/关闭分享、设置试读策略、查看阅读统计 | P0 |
| B-2 | 公开阅读页 `/read/{shareId}`：封面/简介/目录/正文渲染（移动端优先的阅读排版） | P0 |
| B-3 | 章节访问按权限返回：后端**只下发权限内内容**，禁止前端一次性拉全量 | P0 |
| B-4 | 注册/登录流：jwt 模式邀请码注册；casdoor 模式走 sidecar | P0 |
| B-5 | **注册即全文**：`require_auth` 通过即可读全部章节（本期无付费会员；商业版预留支付位） | P0 |
| B-6 | 书架与阅读进度（注册用户） | P1 |
| B-7 | 阅读统计：PV/UV、试读→注册转化（作者后台可见） | P1 |
| B-8 | 防盗：接口限流、分享 ID 不可枚举、阅读页禁止整本打包导出、正文水印（可选） | P0 |

### 4.5 关键接口（设计）

```
GET  /api/share/{shareId}            -- 分享页元数据（公开）
GET  /api/share/{shareId}/chapters   -- 目录（公开，含每章是否可读标记）
GET  /api/share/{shareId}/chapter/{n}-- 章节正文（匿名=试读边界，注册=全文；越权返回 403 + 注册引导）
POST /api/share                      -- 创建分享（作者）
PATCH /api/share/{shareId}           -- 改试读策略/关闭（作者）
GET  /api/bookshelf                  -- 书架+进度（注册）
```

**越权响应约定**：匿名请求试读边界外章节 → `403 {code: "need_login", trial_ok: false}`，前端弹注册引导；绝不下发正文。`/api/membership/*` 本期不实现（商业版预留）。

### 4.6 安全设计要点

1. **后端为唯一真相**：正文只经权限接口下发；前端不预置任何隐藏章节数据。
2. **分享 ID 不可枚举**：≥8 位随机短码（避免顺序 ID 被遍历），限流（单 IP 每分钟 ≤ 60 次分享页请求）。
3. **试读边界校验**：`trial_mode` 变更即时生效；作者关闭分享后所有分享接口立即 404。
4. **注册门槛**：全文访问以 `require_auth` 为唯一闸门（jwt 邀请码注册即用户）；注册接口做防滥用（邀请码有效性、频率限制）。
5. **内容保护**：阅读页禁用整章复制仅能缓解（防君子），核心防线是"接口只给权限内数据 + 限流 + 水印追责"。

---

## 5. 需求 C：Index 首页 + 独立文档站

### 5.1 现状问题

- `website/index.html` 单文件宣传页：无 GitHub 链接、无文档入口；依赖 Google Fonts / Tailwind CDN，国内访问不稳定。
- `docs/product/` 14 篇设计文档是给开发者看的 Markdown，**没有可浏览的文档站**（无索引页、无快速开始、无部署指南）。
- 线上未部署任何对外站（`/opt/world-novel/website` 不存在）。

### 5.2 目标

| ID | 需求 | 优先级 |
|----|------|--------|
| C-1 | 首页（Index）显眼位置放 GitHub 仓库链接（`github.com/Yourdaylight/world-novel`），含 Star 引导 | P0 |
| C-2 | 使用文档页：快速开始（安装/配置/启动）、功能说明、认证配置（jwt/casdoor）、发布与分享使用指南、FAQ | P0 |
| C-3 | **独立部署**：文档站 + 首页为纯静态产物，不依赖后端 API、不依赖数据库；任意静态服务器（nginx / GitHub Pages / 对象存储）可直接托管 | P0 |
| C-4 | 离线友好：自托管字体/样式（或移除外部 CDN 依赖），国内可访问 | P1 |

### 5.3 方案设计

**静态站生成选型对比**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| VitePress（Vue 生态） | 与前端技术栈一致、默认主题带搜索/目录、Markdown 即文档 | 构建依赖 Node | **推荐** |
| MkDocs Material | Python 生态、部署简单 | 与前端栈割裂 | 备选 |
| 纯 HTML 多页 | 零依赖最简 | 无搜索/无自动目录，维护成本高 | 不推荐 |

**站点结构**（VitePress `docs-site/` 独立目录，构建产物 `docs-site/dist`）：

```
/                      首页（宣传 + GitHub 链接 + 进入文档）
/guide/quickstart      快速开始（下载/克隆、uv sync、make dev、.env 配置）
/guide/auth            认证配置（jwt / casdoor / disabled 三模式说明）
/guide/publish         一键发布指南（番茄/七猫）
/guide/share           分享与注册阅读指南
/reference/api         API 参考（自动生成于 OpenAPI）
/product/*             产品设计文档（迁移自 docs/product）
```

**独立部署形态**：`docs-site/dist` 是纯静态目录，与主应用完全解耦。域名规划（已确认）：**主站子路径部署** `world-novel.programtree.cn/docs/`（nginx `location /docs/` 独立 root，与 Vue 工作台互不影响）。

---

## 6. 部署方案

### 6.1 总体拓扑（目标态）

```
                    ┌────────────────────────── 43.142.141.74 ──────────────────────────┐
公网 ── nginx ──────┤                                                                    │
                    │  world-novel.programtree.cn  → uvicorn :8000 (FastAPI + 静态工作台) │
                    │  docs.*（或 /docs/）          → 静态 root（docs-site/dist）          │
                    │  publish-browser（L1 可选）    → Playwright sidecar 容器 :9222        │
                    │  casdoor-auth-sidecar :9097   → Casdoor 认证（casdoor 模式）         │
                    │  qdrant/neo4j（可选）          → docker-compose                      │
                    └────────────────────────────────────────────────────────────────────┘
```
但是当前我们在本地测试。先不部署到公网，但是你需要知道这个结构，以便代码涉及到部署方案调整时能及时发现。
在单个需求正式部署测试前，必须启动subagent去执行一次code review，确保代码符合部署要求以及安全/性能/维护规范，在code review通过后，才能进行本地测试验证

### 6.2 需求 A 部署

- **L0 导出**：零新增服务。导出逻辑在 FastAPI 进程内完成（读 SQLite → 拼装 TXT/EPUB → 返回压缩包）。
- **L1 半自动**：新增 `publish-browser` 独立容器（`playwright:chromium`），仅暴露内部端口（如 :9222），FastAPI 通过内部网络调用；**不进主进程**（浏览器崩溃不影响主服务）。systemd 或 docker 管理，`Restart=always`。
- 敏感词词表：随仓库发布基础词表 + 支持自定义。

### 6.3 需求 B 部署

- 纯后端扩展：新增 `share_links`/`read_progress` 表（§4.3）走现有 SQLite 迁移机制（`memory/database.py` 递增版本号）。
- **不新增常驻进程、不接支付**：全文闸门复用 `require_auth`（jwt 邀请码注册 / casdoor sidecar 两种模式均天然支持）。
- 限流：nginx `limit_req`（推荐，简单可靠）或应用内计数（单实例）。

### 6.4 需求 C 部署

- 构建：CI 或本地 `npm run docs:build` 产出 `docs-site/dist`。
- 托管（三选一，均满足"独立部署"）：
  1. **同机 nginx 子路径**：`location /docs/ { alias /opt/world-novel-docs/dist/; }`；
  2. **独立子域**：`docs.world-novel.programtree.cn` → 独立 server 块（推荐）；
  3. **GitHub Pages**：仓库 gh-pages 分支自动发布（开源场景零成本）。
- 与主应用零耦合：文档站构建产物不含任何后端请求。



---

## 7. 评测方案（独立subagent执行）

### 7.1 需求 A（发布）评测

| 用例 | 步骤 | 预期 |
|------|------|------|
| E2E-导出 | 生成一部 ≥ 10 章小说 → `POST /api/publish/export`（fanqie）→ 解包校验 | 分卷/章节完整、无空章、编码 GB18030、字数统计正确 |
| 质量门禁 | 人为制造断章（空 chapter_texts）→ preflight | 返回 warning 且拒绝导出 |
| 平台规范 | 对照番茄/七猫格式清单逐项核对导出物 | 100% 符合清单 |
| （L1）发布 | 容器起 Playwright → 登录测试账号 → 走完向导到"确认提交" | 每一步人工可见、可中断 |

### 7.2 需求 B（分享/注册阅读）评测

**权限矩阵测试**（核心验收，逐项自动化）：

| 场景 | 匿名 | 注册用户 | 作者 |
|------|------|---------|------|
| 看元数据/目录 | ✅ | ✅ | ✅ |
| 看试读章节 | ✅ | ✅ | ✅ |
| 看试读外章节 | ❌ 403+注册引导 | ✅ 全文 | ✅ |
| 分享管理接口 | ❌ 401 | ❌ 403 | ✅ |

- 边界用例：试读恰好第 N 章边界（第 N 章可读、N+1 需注册）；关闭分享后所有接口 404；注册 token 过期后立即回到试读权限。
- 安全用例：遍历分享 ID（1000 次随机尝试，无越权数据返回）；限流生效（60 req/min 后 429）；响应体不包含隐藏章节内容（抓包核对）。
- 注册用例：邀请码注册→登录→全文可读；无效/已用邀请码被拒。

### 7.3 需求 C（文档站）评测

- **独立部署冒烟**：停掉 uvicorn 主服务 → 文档站仍 200、资源全部加载（证明零后端依赖）。
- 链接完整性：全站爬虫（如 `lychee`）零死链；文档内代码块命令可复制执行（快速开始走通）。
- 兼容性：桌面/移动端、Chrome/Safari；无外部 CDN 依赖时国内网络加载 < 3s。
- 内容同步：docs/product 迁移后与源码目录一致（脚本校验）。

上述全部需求评测完成后，将测试报告与代码修改以 Pull Request 形式提交到 GitHub 仓库。