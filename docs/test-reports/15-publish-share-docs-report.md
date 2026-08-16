# 15 — 成书发布 / 分享阅读 / 独立文档站：QA 评测报告

- 评测日期：2026-08-16
- 评测人：独立 QA（未参与本次开发）
- 被测对象：需求 feat 提交 `ed042cd`（09:53，评测开始时工作区即该内容）；评测期间开发方根据 QA 中途反馈追加修复提交 `b2b1c7f`（11:35）、`1b381b2`（11:38），相关用例已在修复后**复测**并在下表标注
- 需求文档：`docs/product/15-publish-share-docs.md`
- 评测方式：黑盒 HTTP E2E（真实 uvicorn 起服务）+ 白盒代码走读 + 产物解包/XML 校验 + 前端构建验证
- 评测纪律：**未修改任何产品代码/源码文档**；所有测试脚本与临时改动仅存在于 `/tmp` 与构建产物（`.vitepress/dist`、`web/dist`，均 gitignore）。为绕过 C1 构建阻断而临时修改的 `docs-site/product/` 同步副本，评测后已用 `docs/product` 原样还原并通过 `sync --check`。

## 1. 结论摘要

| 维度 | 初测结果 | 修复后复测（b2b1c7f / 1b381b2） |
|---|---|---|
| 需求 A 成书发布（28 例） | **28 PASS / 0 FAIL** | 不涉及（修复仅动 docs/） |
| 需求 B 分享阅读（32 例） | **32 PASS / 0 FAIL** | 不涉及 |
| 需求 C 文档站/首页（14 例） | 11 PASS / **3 FAIL**（C-01 构建阻断、C-10 首页 CDN、C-14 孤儿页） | **13 PASS / 1 FAIL**：C-01、C-14 复测 PASS；**C-10 仍 FAIL** |
| **手工/黑盒合计（74 例）** | 72 PASS / 3 FAIL | **73 PASS / 1 FAIL** |
| 新增自动化 `tests/test_publish_share.py` | **35/35 PASS** | — |
| 全量回归 `uv run pytest tests/ -q` | **205 passed, 2 skipped**（另说明：任务书中的“已知失败” test_chat_requires_message 本次**未复现**，单独运行与 test_api 模块整体均通过，故无遗留失败） | — |

**总体结论：需求 A、B 达到发布标准；需求 C 文档站本身经修复复测全部通过（开箱构建、零死链、零 CDN、子路径部署），唯一遗留 FAIL 为宣传首页 `website/index.html` 仍运行时加载 Tailwind CDN + Google Fonts（P1，建议本期清理）。**

## 2. 测试环境

- 主机 Linux，Python 3.11（uv 管理）、Node v22.22.3；仓库根 `/mnt/tos/workspace/world-novel`
- 主实例：`NOVEL_AUTH_MODE=jwt WORLDENGINE_JWT_SECRET=eval-secret NOVEL_SHARE_RATE_PER_MIN=100000 NOVEL_LOGIN_RATE_PER_MIN=1000 uvicorn novel_creator.web.app:app :8000`
  - 说明：主实例刻意放宽限流（枚举用例自身需打 200 次），限流阈值有效性由独立实例证明
- 限流实例：同配置但 `NOVEL_SHARE_RATE_PER_MIN=10`，端口 8001
- 种子数据脚本 `/tmp/qa_seed.py`：邀请码 `evalauthor/evalreader/evalreader2/evalreader3`（max_uses=0 不限次）+ 小说 `qa-good-book`（10 章/2 卷/第 2 章 2209 字长章/第 4 章埋入机密标记串 `ZZLOCKED-MARKER-9Q2K`）、`qa-empty-book`（第 4 章空章）、`qa-sensitive-book`（第 2 章含“冰毒”）
- E2E 脚本 `/tmp/qa_e2e.py`（56 项断言）、静态站爬虫 `/tmp/qa_crawl.py`；产物 `/tmp/qa_out/`（fanqie.zip、book.epub、e2e_run.log）
- 白盒走读文件：`src/novel_creator/web/routes/publish.py`、`share.py`、`publish_formats.py`、`book_service.py`、`rate_limit.py`、`auth_deps.py`、`memory/database.py`

关键命令与输出：

```text
$ uv run pytest tests/test_publish_share.py -q
35 passed in 12.45s
$ uv run pytest tests/ -q
205 passed, 2 skipped in 721.18s
$ uv run python /tmp/qa_e2e.py
==== SUMMARY ==== total=56 passed=56 failed=0   （A 断言 29 项 + B 断言 27 项）
```

## 3. 需求 A：成书一键发布

平台事实核对：番茄/七猫均无开放 API（需求 §3.2），实现为 L0 导出 + L1 预留 501，分层正确。

| 编号 | 用例 | 步骤 | 预期 | 实际 | 结论 |
|---|---|---|---|---|---|
| A-01 | preflight 统计 | 作者 token POST `/api/publish/preflight` fanqie | ok=true，stats 口径正确 | chapters=10, total_words=4103, volumes=2, encoding=gb18030；与 `book_service.load_book` 地面真值（4103/10/2、第2章2209字）完全一致 | PASS |
| A-02 | 长章警告 | 同上，看 warnings | 单章>2000 字给出番茄拆分建议 | “第2章 章节2 约 2209 字，超过番茄小说建议单章 2000 字” 恰 1 条 | PASS |
| A-03 | 四平台导出 | POST `/api/publish/export` fanqie/qimao/txt/epub | 均 200 且响应头带 `X-Publish-Record-Id` | 4×200，记录 ID 均落响应头（注意线为小写 `x-publish-record-id`） | PASS |
| A-04 | fanqie 编码/章节 | 解 zip，正文 TXT 以 GB18030 解码，正则点章 | GB18030 可解码、10 章齐、无空章、无 `?` 替换 | 解码成功；章标题=10；各章体非空；替换符 0 个 | PASS |
| A-05 | fanqie 附件齐全 | zip 清单 | 出版信息.txt + 封面占位.svg | 含 `QA评测成书.txt / 出版信息.txt / 封面占位.svg` | PASS |
| A-06 | 封面 SVG | ElementTree 解析 | 良构 XML | 解析通过 | PASS |
| A-07 | qimao 分卷 | 解 zip 看 `分卷/` | 2 个分卷 TXT、各 5 章、GB18030 | `第1卷 第一卷 风起青萍.txt`、`第2卷 第二卷 云涌深空.txt`，章数 [5,5]，GB18030 解码通过 | PASS |
| A-08 | 通用 TXT | UTF-8 解码点章 | UTF-8、10 章 | 10 章 | PASS |
| A-09 | EPUB 规范 | zipfile 检查首条 | mimetype 首条且 STORED，内容 `application/epub+zip` | 首条=mimetype，compress_type=0(STORED) | PASS |
| A-10 | EPUB 内容 | opf manifest 章节数 + 全部 xhtml/xml/opf 用 ElementTree 解析 | 10 章、全部良构 | opf ch-item=10；所有 XHTML/XML/OPF 解析无异常 | PASS |
| A-11 | 空章门禁 | qa-empty-book preflight | ok=false 且指明空章 | “存在空章节：第4章 空章测试4” | PASS |
| A-12 | 空章导出拒绝 | 同书 export | 409 | 409（body 含 preflight 详情） | PASS |
| A-13 | 敏感词门禁 | qa-sensitive-book preflight | ok=false，命中“冰毒” | “敏感词预检未通过：「冰毒」×1（第2章）”，词表 `src/novel_creator/data/sensitive_words_base.txt` 确实收录 | PASS |
| A-14 | 敏感词导出拒绝 | 同书 export epub | 409 | 409 | PASS |
| A-15 | 未知平台 | platform=wechat-read | ok=false | 200 + ok=false + “不支持的平台…” | PASS |
| A-16 | 发布记录列表 | export 后 GET `/api/publish/records` | 4 平台记录齐全 | {epub,txt,qimao,fanqie} 均在，operator=evalauthor | PASS |
| A-17 | 存储型 XSS 防护 | backfill `target_url=javascript:alert(1)` | 422 | 422（pydantic 校验拒绝） | PASS |
| A-18 | 合法回填 | backfill 书 ID + https 链接 | stage=published | 200 stage=published | PASS |
| A-19 | 回填持久化 | 再查 records | 字段落库 | stage=published，target_book_id=FQ-12345，url https 开头 | PASS |
| A-20 | 他人记录 | reader2 backfill 作者记录 | 403 | 403 “无权操作他人记录” | PASS |
| A-21 | 记录隔离 | reader2 GET records | 仅见本人 | records=[] | PASS |
| A-22 | 越权导出 | reader2 export 作者小说 | 403 | 403 | PASS |
| A-23 | 记录不存在 | backfill 不存在 ID | 404 | 404 | PASS |
| A-24 | L1 预留 | POST `/publish/records/{id}/confirm` | 501 + 明确引导 | 501 `code=l1_not_enabled`，文案引导 L0 手动上传 | PASS |
| A-25 | 鉴权 | 匿名 export/preflight | 401 | 均 401 | PASS |
| A-26 | zip 安全 | 检查 zip entry 名 | 无绝对路径/`..` 穿越 | 全部条目安全；文件名经 `safe_filename` 正则清洗 | PASS |
| A-27 | 字数口径 | 与地面真值比对 | 一致 | stats=4103 与库内重算一致；长章 2209 与警告一致 | PASS |
| A-28 | 下载文件名 | Content-Disposition | ASCII 回退 + UTF-8'' 中文文件名 | `filename=novel.txt; filename*=UTF-8''QA%E8%AF%84%E6%B5%8B%E6%88%90%E4%B9%A6.txt` | PASS |

补充：`GET /api/publish/platforms` 匿名可查（平台清单公开），导出 CPU 密集序列化走 `anyio.to_thread` 不堵事件循环；失败路径写 stage=failed 记录。均与代码一致。

## 4. 需求 B：公开分享 + 注册阅读

分享 ID 实测 8 字符（`secrets.token_urlsafe(6)` → 如 `xNp1uEwG`）。主实例限流放宽，限流用例在 8001 独立验证。

### 4.1 权限矩阵（核心验收）

| 场景 | 匿名 | 注册读者 | 作者 | 实测 | 结论 |
|---|---|---|---|---|---|
| 元数据 GET `/share/{id}` | 200 | 200 | 200 | 200/200/200 | PASS |
| 目录 GET `/share/{id}/chapters` | 200 | 200 | 200 | 200/200/200 | PASS |
| 试读章 chapter/2 | 200 | 200 | 200 | 200/200/200 | PASS |
| 试读外章 chapter/3 | **403** | **200** | **200** | 403/200/200 | PASS |
| 创建分享 POST `/share` | 401 | 403（他人书） | 200 | 401/403/200 | PASS |
| PATCH 管理 | 401 | 403 | 200 | 401/403/200 | PASS |
| GET `/bookshelf` | 401 | 200 | 200 | 401/200/200 | PASS |

与需求 §7.2 矩阵逐项一致。

### 4.2 用例明细

| 编号 | 用例 | 实际 | 结论 |
|---|---|---|---|
| B-01 | 创建分享：200、id≥8、幂等重复创建返回同一 id（created=false） | 同 id `xNp1uEwG` | PASS |
| B-02 | 试读边界：第3章(index2) 200、第4章(index3) 403 | 200 / 403 | PASS |
| B-03 | 403 响应约定 `{"code":"need_login","trial_ok":false}` 且**无正文字段** | 三个键，无 content | PASS |
| B-04 | 泄露扫描：meta/目录/试读章/403 四个响应体不含 `novel_id`/`owner_id`/`qa-good-book`/`novel.db`/`/data/`/机密标记串 | 0 命中（标记串仅注册读者读锁章时出现，B-18 佐证） | PASS |
| B-05 | 目录 readable 标记 | 前 3 True 后 7 False | PASS |
| B-06 | 伪造 token（Bearer not-a-jwt）→ 降级试读，锁章 403 | 403 need_login | PASS |
| B-07 | 过期 token（用 eval-secret 自签 exp=-1h）→ 降级 403 | 403 | PASS |
| B-08 | `?token=` 查询参数传合法 token **无效**（必须 header） | 403；同 token 走 Authorization 头 → 200 | PASS |
| B-09 | 关闭分享（PATCH status=disabled）后 meta/TOC/章节全 404 | 404×3；重新开启后 200 | PASS |
| B-10 | 枚举：随机 8 字符 ID 打 200 次 | 0 命中（除自己分享） | PASS |
| B-11 | 限流：8001 实例（10/min）连打 | 第 1–10 次 200，**第 11 次 429**，body `{"detail":"请求过于频繁，请稍后再试"}`；60s 滑窗后自动恢复；登录有独立更紧桶（互不影响） | PASS |
| B-12 | 注册链路：无效邀请码登录 401 | 401 | PASS |
| B-13 | 一次性邀请码（max_uses=1）：首次 200、再次 401 | 200 → 401 | PASS |
| B-14 | 注册读者读锁章 200 且 read_progress 自动落库（progress_saved=true，正文含标记串） | 200/true，书架 chapter_index=3 | PASS |
| B-15 | `/api/bookshelf` 可见该分享（标题/类型/进度/available） | 命中 | PASS |
| B-16 | 防盗链：匿名 `/api/novel-full?novel_id=…` | 401 | PASS |
| B-17 | 防盗链：匿名 `/api/chapter-text/3?novel_id=…` | 401 | PASS |
| B-18 | 防盗链：匿名 `/api/actions/3?novel_id=…` | 401 | PASS |
| B-19 | word_count=200：ch0（累计0）200，ch1（累计200）403 边界 | 200/403 | PASS |
| B-20 | ratio=50%：ceil(10×0.5)=5 → ch4 200、ch5 403 | 200/403 | PASS |
| B-21 | first_n_chapters=0（VIP 全锁）：ch0 即 403 | 403 | PASS |
| B-22 | 越界章节 chapter/99、chapter/-5 | 均 404（不泄露存在性细节） | PASS |
| B-23 | 试读策略变更即时生效（PATCH 后无需重启即按新边界） | B-19~21 连续验证 | PASS |
| B-24 | 阅读统计 view_count/read_count 累加（作者 `/api/shares` 可见） | views 27 / reads 52 递增可见 | PASS |
| B-25 | POST `/share/{id}/progress` 显式进度上报 200 | 200 | PASS |

白盒核对：公开三接口走 `optional_auth_header`（刻意忽略 URL token，防日志/Referer 泄露）；`chapter_readable()` 是唯一权限真相源，注册即全文（无付费门，符合开源决策）；管理接口全部 `require_auth` + owner 校验；限流 key 为 IP，生产建议 nginx limit_req（代码注释与部署文档一致）；限流对 X-Forwarded-For 不信任、需 `NOVEL_BEHIND_PROXY=1` 才采用 X-Real-IP，防伪造刷桶。

## 5. 需求 C：Index 首页 + 独立文档站

| 编号 | 用例 | 实际 | 结论 |
|---|---|---|---|
| C-01 | `npm run docs:build`（ed042cd 提交态原样） | **初测 FAIL**：`[vite:vue] product/15-publish-share-docs.md (521:43): Element is missing end tag`。根因：同篇第 298 行含字面量标签 `<token-redacted>`（字节级核验：全文 ascii `<` 共 2 个，该占位标签 1 处），Vue SFC 编译器当作未闭合元素（“加载 < 3s”经验证不阻断）。**复测（b2b1c7f，该行改为“（访问令牌已隐去）”、占位标签消失）：`rm -rf .vitepress/{cache,dist} && npm run docs:build` 24.64s 成功，无任何 QA 绕过** | **FAIL→PASS（已修复复测）** |
| C-02 | 修复后的构建能力对照实验（初测期间仅改 docs-site 同步副本、源码未动） | 22.9s 构建成功，24 个 HTML 页面；曾用于证明阻断点唯一、修复成本极小（正式修复 b2b1c7f 后该对照结论仍成立） | PASS |
| C-03 | 产物外部 CDN/字体扫描 | HTML 无任何外链 script/link 字体；字体自托管（`assets/inter-roman-latin.*.woff2`）；GitHub 图标 data-URI 内嵌 `vp-icons.css`；产物中的 `api.iconify.design` 字符串仅为未知图标运行时兜底（本站图标已本地化，不触发）；其余外链均为正文超链接（astral.sh/fanqienovel/localhost 示例等） | PASS |
| C-04 | 独立部署冒烟：杀掉全部 uvicorn（8000/8001 均 down）后 `python3 -m http.server` 托管 dist | 首页/快速开始/认证/发布/分享/FAQ/API/产品文档 11 个关键 URL 全 200，证明零后端依赖 | PASS |
| C-05 | 内部链接爬虫（首页 BFS，含资产，uvicorn 全程关闭） | 初测 51 个唯一 URL 0 死链；**复测（修复后正式构建）53 个唯一 URL，0 死链**，`.html` 显式保留 http.server 直接可服务（爬虫曾报 1 个 JS 模板字符串 `${decodeURIComponent(f)}` 假阳性，非真实链接） | PASS |
| C-06 | `DOCS_BASE=/world-novel/` 构建 | 25.3s 成功；index.html 资源前缀全部为 `/world-novel/assets/…`（css/js/woff2/chunk），无物理嵌套目录 | PASS |
| C-07 | `scripts/sync-product-docs.sh --check` | `✓ 产品文档已同步`，退出 0 | PASS |
| C-08 | website 首页 GitHub 入口 | `github.com/Yourdaylight/world-novel` 出现 9 次（含 issues/discussions/releases/Star 引导） | PASS |
| C-09 | website 首页文档入口 | `href="/docs/"` 5 处（导航/移动菜单/CTA/页脚） | PASS |
| C-10 | 首页离线友好（C-4） | **仍加载 `https://cdn.tailwindcss.com`（script）与 Google Fonts（fonts.googleapis.com/gstatic，第 10–15 行）——正是需求 §5.1 点名要消除的外部依赖** | **FAIL** |
| C-11 | `make help` | 正常输出，且新增 docs-install/docs-dev/docs-build/docs-sync 目标 | PASS |
| C-12 | `cd web && npm run build` | 66.8s 成功，`web/dist/index.html` + 228 资产文件 | PASS |
| C-13 | 快速开始文档可执行性 | 文档引用的 make/uv/npm 命令均实际跑通；guide/publish、guide/share、reference/api 均成篇且含真实端点路径 | PASS |
| C-14 | 新文档导航完整性 | **初测 FAIL（低）**：产品文档 15 未挂入侧栏（仅列 01–14），README 索引也无条目，属孤儿页。**复测（b2b1c7f/1b381b2）：侧栏已增“15 成书发布/分享/文档站需求”条目，爬虫可从首页到达 `/product/15-publish-share-docs.html`** | **FAIL→PASS（已修复复测）** |

## 6. 发现的问题（按严重度）

1. **[严重 / P0 阻断 → 已修复] C-01 文档站开箱构建失败**
   初测：克隆仓库直接 `npm run docs:build` 必现失败（`Element is missing end tag`，`<token-redacted>` 被 Vue 当未闭合标签）。修复提交 b2b1c7f 将该行改为“（访问令牌已隐去）”；**复测：清空缓存全新构建 24.64s 成功，问题关闭**。保留教训：产品/设计文档中任何 `<单词>` 字面量都会被 VitePress 当组件标签，sync 流程或 CI 应加一次 docs:build 兜底。

2. **[中 / P1 / 未修复 —— 唯一遗留 FAIL] C-10 宣传首页仍依赖外部 CDN**
   `website/index.html` 第 10–15 行运行时加载 `https://cdn.tailwindcss.com` 与 Google Fonts（fonts.googleapis.com / fonts.gstatic.com，复测仍为 3 处命中），国内不稳定问题（需求 §5.1、C-4 P1）未随本期消除。VitePress 文档站自身已完全自托管（字体 woff2 本地化、图标 data-URI），问题仅限 `website/` 单页。

3. **[低 → 已修复] C-14 产品文档 15 为孤儿页**
   初测侧栏仅列 01–14；修复提交已补侧栏条目，复测爬虫可从首页到达，问题关闭。

4. **[低] 分享快照缺 cover 字段**：§4.3 设计有 cover/intro 元数据快照，实现仅 title/intro/genre（无封面位）。不影响本期验收。

5. **[低] EPUB nav.xhtml 未入 spine**：EPUB3 下合法（nav 带 properties="nav"），但个别老阅读器可能不显示导航目录页。

6. **[信息] 需求文档末尾以明文编写了“用某 GitHub PAT 提交 PR”的指令**。磁盘文件中该凭证已被工具链脱敏（字节核验未见明文长 token；正式修复后该行只剩“（访问令牌已隐去）”），但该指令不应保留在产品文档中，且该 PAT 既已在协作流转中出现即应视为需轮换。本次评测按任务书要求仅产出报告，未执行 PR 推送。

## 7. 与需求文档的偏差说明

- **platform_profiles 以代码常量实现**：未建平台适配表，改为 `publish_formats.py` 中冻结的 `_PLATFORMS` 字典 + 公开 `GET /api/publish/platforms` 清单。等价满足“便于新增平台”意图（加一个 dataclass 即可），但若未来要运营时动态增平台需再建表。可接受。
- **L1 半自动发布为 501 预留**：`/publish/records/{id}/confirm` 返回 501 `l1_not_enabled` 并明确引导 L0 手动上传，Playwright sidecar 未交付（设计本就标 P1 选做、且安全上“停在提交前人工确认”更稳妥）。
- **书架仅后端、无独立前端页**：`/api/bookshelf`、read_progress（含唯一约束 upsert）完整；web 前端没有书架路由/页面（仅公开阅读页 `/read/:shareId` 与工作台“成书发布/分享管理”两个入口）。B-6 标 P1，前端入口缺失但不影响后端验收。
- **转化漏斗未实现**：B-7 要求“试读→注册转化”，目前仅有 view/read 原始计数，无漏斗指标（P1，作者后台看不到转化率）。
- **正文水印未实现**：B-8 明确“可选”，记 N/A；整本打包导出接口不存在，防盗核心防线（单章按权限下发 + 限流 + 不可枚举 ID）均已落实。
- **建表方式**：新表 share_links/read_progress/publication_records 走 `SCHEMA_SQL` 幂等创建（CREATE TABLE IF NOT EXISTS + 唯一部分索引），而非“递增版本号迁移”；对既有库同样生效（评测库 data/novel.db 为既有库，三表均自动就位），效果等价。
- **preflight/export 均要求登录**：设计未明示预检公开性，实现要求作者或管理员，且 owner_id 为空的遗留单实例书放行（与既有信任模型一致），合理。
- **任务书所述“已知存量失败”未复现**：`test_api.py::TestHistorianEndpoint::test_chat_requires_message` 单独运行、模块整体运行均 PASS；全量套件 205 passed / 2 skipped，无遗留失败。

## 8. 证据索引

- `/tmp/qa_seed.py`（造数）、`/tmp/qa_e2e.py`（A/B 共 56 断言）、`/tmp/qa_crawl.py`（静态站爬虫）
- `/tmp/qa_out/e2e_run.log`（完整 56 PASS 日志）、`/tmp/qa_out/fanqie.zip`、`/tmp/qa_out/book.epub`
- `/tmp/eval-uvicorn.log`（:8000）、`/tmp/eval-uvicorn-8001.log`（:8001，含 429 记录 20 条）
- C-01 失败输出原文：`build error: [vite:vue] product/15-publish-share-docs.md (521:43): Element is missing end tag`

## 9. 结论

需求 A、B：**通过**，权限矩阵、质量门禁、平台规范、安全设计（不可枚举 ID/限流/后端唯一真相/查询 token 拒绝/防盗链 401/存储型 XSS 拦截）全部有实证支撑。需求 C：文档站本体**经修复复测通过**（开箱构建 24.6s、53 URL 零死链、零外部 CDN/字体脚本、`DOCS_BASE` 子路径部署正确、sync --check 通过、文档 15 已入导航）；唯一遗留为宣传首页 `website/index.html` 的外部 CDN 依赖（C-10，P1），不阻断文档站交付，但与需求 C-4“离线友好/国内可访问”目标不符，建议发布前清理。评测中发现的两个问题（构建阻断、孤儿页）均已由开发方当日修复并经 QA 复测确认。

---

## 10. 开发方修复闭环（评测后，2026-08-16）

| 评测发现 | 处置 | 验证 |
|---|---|---|
| C-10 首页外部 CDN（[中/P1] 唯一遗留 FAIL） | **已修复**：Tailwind Play 运行时自托管为 `website/tailwind-play.js`（MIT，407KB，含全部依赖版权声明），删除 Google Fonts/preconnect，字体回退系统栈 | `grep -cE 'googleapis\|gstatic\|cdn.tailwindcss\|jsdelivr\|unpkg' website/index.html` = **0**；`node --check tailwind-play.js` 通过 |
| 发现 5：EPUB nav 未入 spine | **已修复**：`content.opf` spine 增加 `<itemref idref="nav" linear="no"/>` | `tests/test_publish_share.py` 35/35 PASS（含 EPUB 结构断言） |
| 发现 4：分享快照无 cover 字段 | 接受偏差：系统无封面图基础设施，阅读页以首字占位封面渲染；数据模型未堵死后续扩展 | 不影响验收 |
| 发现 6：PAT 指令文本 | **已修复**：需求文档 15 中相关语句改写为常规 PR 描述，仓库全量 grep 无 `github_pat_` 残留 | 已核验 |
| token 轮换提醒 | 任务书提供的 fine-grained PAT 经验证仅有**只读**权限（Contents write / forks 均 403），且在协作流转中出现过，建议创建者在 GitHub 侧吊销轮换；本次推送/建 PR 因此无法自动完成 |

**最终状态：需求 A 28/28 PASS、需求 B 32/32 PASS、需求 C 14/14（评测发现项全部修复闭环）；新增自动化 35/35 PASS；全量后端套件通过。**
