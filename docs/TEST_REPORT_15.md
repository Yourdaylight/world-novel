# TEST_REPORT_15 — 成书发布 / 公开分享 / 独立文档站 验收测试报告

- 报告日期：2026-08-16
- 评测角色：独立评测工程师（仅运行验证，未改动任何应用源码；临时脚本全部放在 `/tmp`）
- 被测版本：工作区未提交改动（评测报告写入前 `git status` 共 35 项：19 项已修改、16 项新增；本报告写入后新增文件变为 17 项，详见用例 9）
- 总体结论：**PASS（通过）**——9 个验收用例全部达成预期，未发现阻断性（Blocker/Critical）缺陷；记录 4 项低severity观察项。

---

## 一、概述

本次对三项需求进行真机/真栈验证：

- **需求 A 成书一键发布**：`POST /api/publish/preflight`、`POST /api/publish/export`（fanqie/qimao/txt/epub/rtf/bundle）、质量门禁（空章/断章 422）、`GET /api/publish/records` 操作人归属隔离。
- **需求 B 公开分享 + 注册阅读**：`POST /api/share`、`GET /api/share/{id}`、`/chapters`、`/chapter/{n}`；匿名试读默认前 3 章、注册用户全书、超出试读 403 且不泄漏正文；关闭后 404；10 位不可猜测 ID；60 次/分钟限流 429；关闭老接口 `/api/novel-full`、`/api/chapter-text/{n}` 的匿名绕过。
- **需求 C 独立文档站**：`docs-site/` VitePress 纯静态，零后端依赖、运行时零外部 CDN/字体、支持 `DOCS_BASE=/docs/` 子路径构建。

后端验证以 FastAPI `TestClient`（与线上同一 ASGI app）为主，前端执行真实 `vue-tsc` 与生产构建，文档站执行真实 VitePress 构建并用 `python3 -m http.server` 在**后端停机**状态下回源验证。

---

## 二、测试环境与方法

| 项 | 值 |
|---|---|
| Python | 3.11.13（仓库 `.venv`，uv 管理） |
| FastAPI | 0.135.2，认证模式 jwt（默认） |
| Node | 22 / npm；前端 vite/rolldown 生产构建 |
| 文档站 | vitepress 1.6.4 |
| 数据隔离 | 每个脚本使用 `tempfile.mkdtemp()` 独立 registry + central.db |
| 造数方式 | 仿 `tests/test_publish_share.py._build_novel`：`register_novel(owner_id=…)` + 写 `story_outline/volumes/chapter_texts`；邀请码 `create_invite_code(code=…, max_uses=0)`，登录 `POST /api/auth/login` |
| 评测脚本 | `/tmp/eval_case1.py`、`/tmp/eval_case2.py`、`/tmp/eval_case345.py`、`/tmp/eval_xff.py`（均为一次性脚本，不在仓库内） |

命令与输出均逐字记录于下文“证据”。

---

## 三、分需求用例结果

### 需求 A：成书一键发布

#### 用例 1 — A-E2E 全平台导出（12 章 / 2 卷）　结论：**PASS**

- 步骤摘要：构造 12 章、2 卷（卷一「初入江湖」0–4；卷二「名动天下」5–11）、每章约 1600 字的小说；owner=OWNERA 登录后依次打 preflight 与 6 种平台导出，解包/解码产物。
- 预期：preflight ok；番茄 GB18030 可解码且含首章/末章标题与 12 个章节标题；bundle 含 番茄/七猫/epub/rtf/cover；EPUB `mimetype` 为首条目且 STORED；七猫含「第N卷」。
- 实际：**全部符合**。

证据（逐字）：

```
PREFLIGHT status: 200  ok: True  chapters: 12  volumes: 2  words: 16527  errors: []
FANQIE  200  bytes: 33272   content-type: text/plain; charset=gb18030
        GB18030 decode OK; 含 第1章=True 含 第12章=True; 章节标题命中 12/12
QIMAO   200  bytes: 49874   含 第1卷/第2卷/初入江湖/名动天下 均 True
TXT     200  bytes: 49874
EPUB    200  bytes: 8109    media: application/epub+zip
        前38字节: PK\x03\x04…mimetype（mimetype 物理首位）
        first entry: mimetype  compress_type=0(STORED); entries=17; testzip=None
RTF     200  bytes: 135979  以 {\rtf1 开头；CJK 全部 \uN 转义（无裸中文）
BUNDLE  200  bytes: 9951    条目：
        导出E2E测试书/封面.txt(84)  cover.svg(946)
        导出E2E测试书-番茄.txt(33272，GB18030 二次解码 OK)
        导出E2E测试书-七猫.txt(49874)  .epub(8110)  .rtf(135979)  meta.txt(83)
RECORDS count: 6（fanqie/qimao/txt/epub/rtf/bundle，operator 均为 OWNERA，含 bytes/chapters/total_words）
未知平台 weird → 400
```

补充说明：番茄 33KB < 七猫 49KB 符合编码规律（GB18030 每汉字 2 字节、UTF-8 3 字节）；EPUB 局部头 `mimetype` 前无 extra field，符合 EPUB3 OCF 规范。

#### 用例 2 — A 质量门禁（空章 / 断章）　结论：**PASS**

- 步骤：分别构造「第 4 章正文为空」与「缺第 5 章（序号 4）造成断档」两本 6 章书。
- 预期：preflight `ok=false` 且错误码分别为 `empty_chapter` / `gap`；export 一律 422。
- 实际：**符合**。

证据：

```
[空章书] preflight status=200 ok=False
  ERROR empty_chapter | 存在空章/过短章节（<20字）：[4]   indices: [3]
  export status=422  detail: 质量门禁未通过，请先修复以下问题（携带 preflight 明细）
[断章书] preflight status=200 ok=False
  ERROR gap | 章节不连续，疑似断章：缺失序号 [4]（0-based） indices: [4]
  export status=422
CASE2 RESULT: PASS
```

---

### 需求 B：公开分享 + 注册阅读

#### 用例 3 — B 权限矩阵（匿名 / 注册读者 / 作者）　结论：**PASS**

试读值 trial_value=3，12 章：

| 操作 | 匿名 | 注册读者（非 owner） | 作者 owner | 结论 |
|---|---|---|---|---|
| 元数据 `GET /share/{id}` | 200 | 200（`authenticated=true, can_read_full=true`） | 200 | 符合 |
| 目录 `GET /share/{id}/chapters` | 200，`readable=[0,1,2]` | 200 | 200 | 符合 |
| 试读内章节 ch2 | 200，正文含唯一标记串 | — | — | 符合 |
| 超试读章节 ch3 | **403**，body 无正文 | **200**（ch11 末章，正文含标记串） | 200 | 符合 |
| `POST /api/share`（管理） | **401** | **403**（非owner） | 200 | 符合 |
| `GET /api/shares/mine` | —（401） | 200，本人列表 0 条 | 200 | 符合 |
| `PATCH /share/{id}` 关闭他人分享 | — | **403** | 200 | 符合 |

403 原始响应（证明只返回结构化拒绝、不返回正文）：

```
anon ch3 → 403
{"detail":{"code":"need_login","trial_ok":false,
 "message":"试读到这里，注册后即可阅读全部章节","chapter_index":3}}
响应中是否包含唯一正文标记 '天地玄黄…XYZ'：False
```

#### 用例 4 — B 边界与生命周期　结论：**PASS**

- 试读边界（trial=3）：`ch0=200, ch2=200, ch3=403, ch11=403, 越界 ch99=404` —— 边界精确落在第 3/4 章之间。
- 未知 ID：`/api/share/zzZZZZ9999` 与随机串均 **404** `{"detail":"分享不存在或已关闭"}`。
- 生命周期：owner `PATCH {status:"disabled"}` → 200；随后 `GET /share/{id}`、`/chapters`、`/chapter/0` **全部 404**，且状态码与未知 ID 完全一致（不泄漏“存在但已关闭”）。
- 字数试读模式：每章 600 字、trial_value=650（累计≤650 可读）：目录 `readable=[True,False,False,False,False]`，`ch0=200 / ch1=403` —— 累计到 ch0=600≤650、ch1=1200>650，**只放 ch0，符合预期**。

#### 用例 5 — B 安全项　结论：**PASS**

1. **关闭匿名绕过老接口**：
   ```
   GET /api/novel-full?novel_id=…     匿名 → 401 {"detail":"请先登录"}
   GET /api/chapter-text/0?novel_id=… 匿名 → 401
   owner 带 token → 200
   ```
   源码佐证：`src/novel_creator/web/routes/export.py` 中两接口已迁至 `protected_router = APIRouter(dependencies=[Depends(require_auth)])`，并留注释说明唯一匿名内容面是 share 阅读器。
2. **限流**：将 `share_limiter.max_requests=5` 后连发 8 次 → `[200,200,200,200,200,429,429,429]`，恰在第 6 次触发；响应头 `Retry-After: 59`。生产默认 60/min。
3. **ID 不可猜测**：示例 `pxx9jDHBbL`、`BLUNQptRkY`，均为 10 位、`[A-Za-z0-9]`，多次生成不重复。
4. **403/401 响应零正文泄漏**：grep 唯一正文标记串，均为 False。
5. **限流器 XFF 伪造防护**（附加实测）：不设 `NOVEL_TRUST_PROXY` 时，每请求伪造不同 `X-Forwarded-For: 1.2.3.i`，8 次中仍恰为 3×200 + 3×429 —— 伪造 XFF **不能**换桶绕过；源码 `ratelimit.client_key` 仅在显式信任代理时取 XFF **最右**一跳。

---

### 需求 A/B 非回归

#### 用例 6 — 历史测试 + 新增测试　结论：**PASS（0 失败）**

```
$ NOVEL_AUTH_MODE=disabled .venv/bin/python -m pytest \
    tests/test_api.py tests/test_e2e.py tests/test_config.py tests/test_quota_system.py -q
70 passed, 2 warnings in 6.74s

$ .venv/bin/python -m pytest tests/test_publish_share.py -q
11 passed, 2 warnings in 5.93s
```

合计 **81 passed / 0 failed**。关于任务说明中提到的两个“已知失败”：本次**均未复现**——
- `test_chat_requires_message` 断言为 `status_code in (422,400,200,405)` 的宽容断言，当前稳定通过；
- SPA random-route 用例因当前 `web/dist/index.html` 已存在而返回 200 通过。
即除上述两项外不存在任何失败，符合“只有这两个可能失败”的预期（且本次一个都没失败）。

---

### 前端

#### 用例 7 — vue-tsc 与生产构建　结论：**PASS**

```
$ cd web && npx vue-tsc --noEmit -p tsconfig.json
VUE-TSC EXIT:0
```

生产构建（virtiofs 上 dart-sass EPERM，按既定方案拷贝到 `/tmp/webbuild/web-tmp`、symlink 原 node_modules）：

```
$ npm run build
✓ built in 25.99s        BUILD EXIT:0   （共 161 个 JS chunk）
```

需求相关 chunk 全部产出（`dist/assets/`）：

```
PublicReaderPage-DDkdWX6r.js / .css      （读者页 /read/:shareId）
PublishPage-CTSPkFrS.js / .css           （成书发布工作区）
ShareManagePage-DP0O6ddS.js / .css       （分享管理工作区）
share-BoAmyRye.js                        （分享 API 封装）
```

路由与 401 拦截器佐证：`web/src/router/index.ts:19 path:'/read/:shareId' → PublicReaderPage.vue`；`web/src/api/client.ts:60` 401 时清空 token 并跳转登录，且对 `/read`、`/login` 公共路径与 `_skipAuthRedirect` 请求豁免（公开读者页不会被陈旧 token 弹走）。

---

### 需求 C：独立文档站

#### 用例 8 — 构建 / 后端停机回源 / 零外链 / 子路径　结论：**PASS**

1. 构建：`cd docs-site && npm run docs:build` → `build complete`，**EXIT 0**；产出 **25 个 HTML**（首页 + 6 guide + 15 product + 2 reference + 404，数量与来源一致）。
2. 后端停机回源：先确认 `curl http://127.0.0.1:8000/api/health → 000`（无后端）；在 `docs-site/dist` 起 `python3 -m http.server 8123`：
   ```
   /                                     200
   /guide/publish.html /guide/share.html 200
   /product/04-features.html             200
   /product/14-memory-…-architecture.html 200
   /reference/api.html                   200
   /api/health（静态服务器）              404   ← 证明页面不依赖任何后端
   ```
3. 运行时零外部依赖：
   - 全量 grep `<script|link … src/href="http(s)://…">`：**0 条**；CSS 无 `@import http`、无 `url(https://…fonts)`。
   - 字体：使用 VitePress **自托管** Inter（`assets/inter-*.woff2`，同源），符合“自托管 woff2 可以”。
   - GitHub 社交图标为**同源 data-URI**：`/vp-icons.css` 内 `.vpi-social-github{--icon:url("data:image/svg+xml,…")}`，HTML 通过 `<link href="/vp-icons.css">` 加载；bundle 内虽含 `api.iconify.design` 字符串，但那是 VitePress 对“未知图标名”的兜底死代码，配置使用的是内置已知图标 `github`，CSS mask 已就绪、运行时不会发起该请求（见“观察项 O3”）。
4. 子路径构建：`DOCS_BASE=/docs/ npx vitepress build --outDir /tmp/docsbase` → EXIT 0；产物中资源与内链全部带前缀：
   ```
   href="/docs/assets/style.*.css"  src="/docs/assets/app.*.js"
   href="/docs/guide/quickstart"   href="/docs/product/"  href="/docs/vp-icons.css"
   任何裸 "/assets/…" 引用：0 条
   ```
5. 产品文档数量一致：`ls docs/product/0*.md docs/product/1*.md` = **14**，`docs-site/product/` 同名 14 篇一一对应。
6. 首页含仓库入口：`grep github.com/Yourdaylight/world-novel index.html` 命中（nav「GitHub 仓库」「Issue 反馈」+ social link）。

---

### 工程卫生

#### 用例 9 — `.github` / git 卫生　结论：**PASS**

`git status --short` 在报告写入前共 35 项（19 modified、16 untracked；写入 `docs/TEST_REPORT_15.md` 后 untracked 为 17）。忽略规则验证：

```
$ git check-ignore docs-site/node_modules docs-site/dist web/node_modules web/dist
docs-site/node_modules      ← 已忽略
docs-site/dist              ← 已忽略
web/node_modules            ← 已忽略
web/dist                    ← 已忽略
$ git add -n docs-site/ | wc -l           → 29（全部为 .ts/.md/.json/.css 源文件）
$ git add -n docs-site/ | grep -E 'node_modules|dist/'   → 空（无构建泄漏）
```

待提交新增文件（16 个功能条目，另有本报告 1 篇）：后端 `src/novel_creator/web/{book,platforms,quality,sensitive,ratelimit}.py`、`web/routes/{publish,share}.py`、`memory/{publication_store,share_store}.py`；前端 `web/src/api/{publish,share}.ts`、`components/{publish,share,read}/`；测试 `tests/test_publish_share.py`；以及整站 `docs-site/`。

---

## 四、发现的问题

未发现 Blocker / Critical / Major 级缺陷。以下为低severity观察项（不阻断验收）：

| 编号 | 级别 | 描述 | 建议 |
|---|---|---|---|
| O1 | 低（提示） | 前端生产构建提示 3 个 chunk >500KB：`echarts`(1.03MB)、`CharactersPage`(980KB)、`es`(865KB)，gzip 后 275–336KB。 | 后续按需路由级拆包/手动 vendor 分块；本次功能页面已正确按路由切分。 |
| O2 | 低（卫生） | `web/tsconfig.tsbuildinfo` 作为**已跟踪**文件在本次被修改（`M`），属构建缓存。 | 建议加入 `.gitignore` 并 `git rm --cached`（历史遗留，非本次需求引入）。 |
| O3 | 低（知会） | 文档站 bundle 内含 `https://api.iconify.design/simple-icons/{icon}.svg` 兜底字符串。当前用内置 `github` 图标时该路径不触发（图标由同源 `/vp-icons.css` data-URI 提供，已核实 mask 规则存在）。 | 若今后在 `socialLinks` 使用 VitePress 不内置的自定义图标名，会在运行时拉取该外部 URL，违反“零外链”约束；届时应改传内联 SVG 对象。 |
| O4 | 低（环境） | 本沙箱内跨进程 loopback TCP 被限制（uvicorn 真实启动日志显示 `Application startup complete`，但另一进程 curl 得 000），故 HTTP 层用同 ASGI 的 TestClient 完成，覆盖等价；线上无此限制。 | 无需改代码；在非沙箱环境补一次 docker-compose 冒烟即可。 |

---

## 五、Code Review 整改记录摘要

依据源码与实测，前一轮 review 提出的安全/可配置项均已落地：

1. **关闭 novel-full 匿名绕过**：`/api/novel-full`、`/api/chapter-text/{n}` 由原公开 `router` 迁至 `protected_router`（`Depends(require_auth)`），匿名 401、登录可读（用例 5 实测）。
2. **IDOR 归属校验**：新增 `_helpers.can_manage_novel()`，发布/分享/关闭均校验 owner 或管理员；非 owner 对他人小说 preflight/share/PATCH 一律 403；`/publish/records/{id}/backfill` 二次核对记录 operator；`GET /publish/records` 非管理员仅见本人记录（用例 1/3 实测归属隔离）。
3. **限流器 XFF 加固**：`client_key()` 默认只用 TCP 对端 IP，仅当显式 `NOVEL_TRUST_PROXY` 时才取 X-Forwarded-For **最右**一跳（nginx 追加的真实 peer），伪造实测不可绕过（用例 5-5）。
4. **前端 401 拦截器**：`web/src/api/client.ts` 统一拦截 401，清 token 并跳登录，同时豁免公开读者页 `/read` 与登录页，避免匿名浏览被弹走。
5. **JWT `.env` 与管理员前缀可配**：密钥优先读 `WORLDENGINE_JWT_SECRET`（.env 自动加载），回退 `NOVEL_JWT_SECRET`（settings，前缀 `NOVEL_`）；管理员识别前缀由 `NOVEL_ADMIN_CODE_PREFIX` 配置（默认 `admin`），`.env.example` 已给出三项示例与注释。

---

## 六、总体结论

| 需求 | 用例 | 结论 |
|---|---|---|
| A 成书发布 | 1 全平台 E2E / 2 质量门禁 / 6 非回归 | PASS / PASS / PASS |
| B 分享阅读 | 3 权限矩阵 / 4 边界生命周期 / 5 安全 | PASS / PASS / PASS |
| C 文档站 | 8 构建·停机回源·零外链·子路径 | PASS |
| 前端 | 7 vue-tsc + 生产构建 + chunk | PASS |
| 工程 | 9 git 卫生 | PASS |

**9/9 用例 PASS，自动化测试 81 passed / 0 failed，前端类型检查 0 错误、生产构建成功，文档站 25 页在后端停机下全部 200 且运行时零外部依赖。三项需求达到验收标准，建议合并；4 项低severity观察项可择机优化，不阻断发布。**
