# 需求 15 测试报告：成书发布 · 分享阅读 · 独立文档站

- 分支：`feature/publish-share-docs`
- 日期：2026-08-16
- 范围：需求 A（成书一键发布）、需求 B（公开分享 + 注册阅读）、需求 C（独立文档站）

## 0. 评测方法

| 层级 | 方式 |
| --- | --- |
| 单元/接口测试 | `tests/test_publish_share.py`（25 个用例）+ 既有回归 `test_api/test_config/test_models` |
| 真实服务 E2E | 播种 10 章成书（`scripts/seed_demo_novel.py`）→ 启动 uvicorn(jwt) → 全链路 HTTP 调用 |
| 独立 code review | 三个独立 subagent 分别审查 A（工程）、B（安全对抗）、C（文档/部署），blocker 全部修复后复测 |
| 静态站冒烟 | 停掉 uvicorn，`python3 -m http.server` 托管 VitePress dist |

测试基线：`68 passed`（既有 2 个环境相关失败在构建出 `web/dist` 后转绿，与本次改动无关）。

## 1. 需求 A：成书发布

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| E2E 导出 ≥10 章 → fanqie TXT | ✅ | GB18030 可解码，10 个「第N章」齐全，1345+ 字 |
| EPUB 合法性 | ✅ | ZIP 首条目为 STORED `mimetype`，10 个 chap xhtml + nav + opf |
| 七猫分卷 ZIP | ✅ | `初入江湖.txt` + `简介.txt` + `cover.svg`，GB18030 |
| 质量门禁：断章 | ✅ | 缺 2/4 章 + 空章 → `ok=false`，错误含「断章」「空章节」 |
| 门禁失败拒绝导出 | ✅ | 导出返回 409 + report |
| 平台规范 | ✅ | 番茄 GB18030 + ≤2000 字警告；七猫分卷；UTF-8 TXT；EPUB3 |
| 发布记录 + 回填 | ✅ | 3 次导出 3 条记录；PATCH 回填 URL/stage=published |
| 未登录导出 | ✅ | 401 |

**review 发现并修复**：
1. 七猫 ZIP 会**静默丢失卷范围外章节** → preflight 警告 + ZIP 兜底 `未分卷章节.txt`（新增守护测试）+ 卷标题同名去重；
2. TXT 下载响应头未声明 GB18030 charset → 显式 `text/plain; charset=gb18030`；
3. EPUB 未过滤 XML 1.0 非法字符 → 导出前清洗；
4. 重复鉴权（路由级+参数级）→ 改为每端点单次 `require_auth`；
5. 注册表存在但库文件被删时会新建空库再 500 → 先判文件存在性。

**范围说明**：番茄/七猫均无开放 API，本期实现 L0 一键导出（需求文档已分层确认）；L1 Playwright 半自动发布为远期，不进主进程，部署文档已预留 sidecar 拓扑。

## 2. 需求 B：公开分享 + 注册阅读

### 权限矩阵（核心验收）

| 场景 | 匿名 | 注册用户 | 作者 | 结果 |
| --- | --- | --- | --- | --- |
| 元数据/目录 | ✅ | ✅ | ✅（access.level=author） | ✅ |
| 试读章节（前3） | ✅ | ✅ | ✅ | ✅ |
| 试读外章节 | ❌ 403 `need_login` | ✅ 全文（第10章实测 200） | ✅ | ✅ |
| 分享管理 | ❌ 401 | ❌ 404（不泄露存在性） | ✅ | ✅ |
| 书架 | ❌ 401 | ✅ 进度自动落库 | — | ✅ |

### 边界与安全

| 用例 | 结果 |
| --- | --- |
| 试读边界：第 N 章 200 / 第 N+1 章 403 | ✅ |
| 关闭分享后元数据/目录/正文全部 404 | ✅ |
| 1000 次随机 ID 遍历全部 404（12 位 ≈72bit） | ✅ |
| 限流：60 次 200 后精确 429（实测 60×200 + 5×429） | ✅ |
| 目录/403 响应体不含隐藏章节正文（抓包断言） | ✅ |
| 邀请码登录 → JWT → 全文；无效邀请码 401 | ✅ |
| word_count=0 关闭试读（修复后） | ✅ |
| 伪造 X-Forwarded-For 绕限流（修复后，受信代理判定） | ✅ |
| disabled 认证模式不再把匿名当注册（修复后） | ✅ |

**review 发现并修复**：
1. **B1 限流绕过**：XFF 取最左值可被伪造 → 仅在直连为受信代理（loopback/内网）时采信 `X-Real-IP`/XFF 最右一跳；限流器增加过期 bucket 定期清理防内存耗尽；
2. **B2 `/share/mine` 被 `/share/{id}` 路由遮蔽**（真实 bug，作者"我的分享"100% 404）→ 调整注册顺序 + 守护测试；
3. **B3 disabled 模式匿名=注册、全书无门槛** → 公开接口在 disabled 模式一律按未认证处理；
4. **B4 word_count=0 仍下发首章** → value=0 直接返回 0 章；
5. 其余：复用分享时应用最新试读设置、书架过滤已关闭分享、`(novel_id, owner_id)` 唯一索引、404 文案不泄露状态。

**已知设计边界**（与现有系统一致，非本期引入）：分享创建不校验小说属主（registry 无 owner 字段，与既有导出接口同一模型）；`admin` 前缀邀请码自动管理员；多 worker 部署需改用 nginx `limit_req`（已写入部署文档）。

## 3. 需求 C：独立文档站

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 独立部署冒烟（停 uvicorn） | ✅ | 首页/指南/产品文档/API/openapi.json 全部 200（`$uri.html`） |
| 零外部依赖 | ✅ | 对 dist 全量 grep：无 googleapis/gstatic/jsdelivr/unpkg/cdnjs 引用；本地搜索、自托管资源 |
| GitHub 入口 | ✅ | 导航栏 + Hero 按钮 + 社交图标；website 首页导航补「使用文档」 |
| 死链 | ✅ | VitePress 构建 0 dead link（localhost 链接显式豁免） |
| 产品文档同步 | ✅ | `sync_product_docs.py --check` 退出 0，15 篇一致 |
| OpenAPI 快照 | ✅ | 87 个路径，随后端生成 |
| 子路径部署 | ✅ | `DOCS_BASE=/docs/` 支持；nginx `try_files $uri.html` 文档修正 |

**review 发现并修复**：`docs-site/node_modules` 未被 gitignore（入库风险）、nginx cleanUrls 缺 `$uri.html`、FAQ 断锚、Makefile 重复同步。

## 4. 前端

- 新增：公开阅读页 `/read/:shareId`（移动端优先排版、目录抽屉、试读边界注册引导）、成书发布页、分享管理页；
- 补齐 **jwt 模式邀请码登录/注册 UI**（此前开源默认模式无登录入口，是需求 B-4 的前置缺口）；
- `vue-tsc` 0 错误，`vite build` 成功；工作台侧栏新增「成书发布」「分享阅读」。

## 5. 遗留与建议（不阻断合并）

- `world_propositions` 等表无 owner，"按属主隔离"属系统性改造，建议单独立项；
- 应用内限流为单进程实现，多 worker 部署以 nginx 为准（文档已说明）；
- L1 半自动发布、付费会员为商业版/远期预留，数据模型已留扩展位。
