# Milestone 15 测试报告 — 成书发布 / 分享阅读 / 独立文档站

- **分支**: `feat/m15-publish-share-docs`
- **日期**: 2026-08-16
- **环境**: 本地测试（未部署公网）。Python 3.11 / uv 0.8.9 / Node 22 / Chromium headless
- **评测方式**: pytest 自动化套件 + 独立 code-review subagent（B/C）+ 严格自评审（A，因评审 subagent 环境不稳定兜底）+ 活服务集成评测 + 无头浏览器渲染验证

---

## 0. Code Review（部署测试前置环节）

| 需求 | 评审方式 | 结论 | 处理 |
|------|---------|------|------|
| B 分享阅读 | 独立 subagent | 有条件通过：7 MAJOR（XFF 限流绕过、限流器 prune 清零、word_count=0 试读破口、UV 口径、JWT 密钥变量名、书架资源耗尽、阅读路径性能） | 全部修复并回归，另深挖出 uvicorn proxy_headers 重写 client.host 的信任链问题一并加固 |
| C 文档站 | 独立 subagent | 有条件通过：6 MAJOR（publish.md 路径乱码、nginx try_files、GH Pages cleanUrls 冲突、Node 版本、邀请码创建失实描述、FAQ 缺失） | 全部修复（含 admin_code_prefix 死配置接通） |
| A 成书发布 | subagent 多次停滞 → 严格自评审兜底 | 发现并修复：卷范围重叠导致章节重复导出/EPUB 重复 manifest id、空标题"第N章 第N章"、敏感词表坏编码崩溃 | 已修复 + 回归测试 |

## 1. 需求 A：成书一键发布（L0 导出）

### 1.1 单元测试（tests/test_publish.py，17 项全过）

平台列表 / 认证 401 / preflight 通过（12 章 2 卷字数统计）/ 断章检测 / 空章检测 /
敏感词仅警告 / 番茄 GB18030 / 通用 TXT 卷头 / 七猫分卷 / EPUB 结构 / 未知平台 400 /
发布记录 / 回填→published / 未知记录 404 / L1 confirm 501 / 卷重叠去重 / 空标题章号

### 1.2 活服务集成评测（§7.1，14/14 通过）

| 用例 | 结果 |
|------|------|
| E2E 导出 fanqie：发布记录 ID + GB18030 + 12 章完整 + synopsis/cover/README | ✅ |
| 断章 → preflight ok=false + export 422 拒绝 | ✅ |
| 空章 → preflight 报错 | ✅ |
| 恢复后 preflight 通过 | ✅ |
| qimao 按卷拆分（卷一 1-6 章 / 卷二 7-12 章） | ✅ |
| EPUB3 合法（mimetype 首条目未压缩 / OPF / nav / 12 章 XHTML） | ✅ |
| 发布记录 stage=exported + export_meta | ✅ |
| 回填 target_url/book_id → stage=published | ✅ |
| L1 confirm 预留 501 | ✅ |
| 单元测试全过 | ✅ |

> 评测说明：成书为种子数据（12 章 2 卷）。真实 LLM 生成需 API Key，
> 但导出/门禁/权限链路与章节内容无关，种子数据足以验证全部 L0 能力。

---

## 2. 需求 B：公开分享 + 注册阅读

### 2.1 单元/接口测试（tests/test_share_api.py，38 项全过）

覆盖：权限矩阵、试读边界、word_count/ratio/0 值策略、XFF 伪造绕过防护、
限流器 prune、disabled 模式语义、关闭后 404、书架校验（小说/分享存在性）、
过期 token 回退、转化幂等、分享不可被他人覆盖。

### 2.2 活服务集成评测（§7.2，全部通过）

| 用例组 | 明细 | 结果 |
|--------|------|------|
| 权限矩阵 | 元数据匿名/注册/作者均 200；匿名目录前 3 章可读标记、试读外锁定、trial_chapters=3；注册用户 has_full_access=true；匿名试读内 200 / 试读外 403 need_login 且无正文；注册/作者全文 200；管理接口匿名 401 / 非所有者 403 / 所有者 200 | ✅ |
| 边界用例 | 试读边界恰好（第 3 章可读、第 4 章拒绝）；试读策略改 1 章即时生效；关闭分享后全部 404（含带 token 正文）；重新开启恢复；过期 token 回退试读权限 | ✅ |
| 安全用例 | **1000 次随机分享 ID 枚举零泄露**（404×986 / 429×14 / 200×0）；限流 60 req/min 后 429 生效；403 响应体不含任何正文 | ✅ |
| 注册用例 | 无效邀请码 401；新建邀请码注册登录成功 → 全文可读；转化上报幂等（第二次 recorded=false）；书架加入/列出；阅读进度读写 | ✅ |
| 单元测试 | tests/test_share_api.py 38 项全过 | ✅ |

### 2.3 前端渲染（Chromium headless）

| 页面 | 验证点 | 结果 |
|------|--------|------|
| /read/{shareId} | 书名/简介/「开始阅读」/试读提示 | ✅ |
| /read/{shareId}/0 | 章节正文/上下章导航 | ✅ |
| /login（jwt 模式） | 邀请码输入 + 注册/登录表单 | ✅ |

---

## 3. 需求 C：Index 首页 + 独立文档站

### 3.1 独立部署冒烟（§7.3 核心）

| 用例 | 结果 |
|------|------|
| 无任何后端服务时，静态托管 /docs/ → 200 | ✅ |
| HTML 引用的 JS/CSS/字体资源全部 200 | ✅ |
| dist 资源中无 `/api` 调用、无 XMLHttpRequest 业务调用 | ✅ |
| 静态服务访问日志 0 条后端请求 | ✅ |

### 3.2 链接完整性 / 兼容性 / 内容同步

| 用例 | 结果 |
|------|------|
| 628 条内部链接零死链（cleanUrls 映射校验） | ✅ |
| quickstart 命令与 Makefile/.env.example 一致 | ✅ |
| Chromium 桌面渲染首页/快速开始（标题/GitHub 链接/正文） | ✅ |
| 移动端 375x812 渲染正常（GitHub 链接可见） | ✅ |
| docs/product ↔ docs-site/product 全量 diff = 0 差异 | ✅ |
| 首页 GitHub 仓库链接（hero + 正文，≥2 处） | ✅ |
| 指南页齐全（quickstart/auth/publish/share/faq/deploy） | ✅ |
| 无外部 CDN/Google Fonts（Inter 字体本地打包 woff2） | ✅ |
| 官网页 website/index.html GitHub + 文档入口 | ✅ |

> 备注：cleanUrls 无扩展名 URL 需服务器 `.html` 回退（nginx `try_files $uri $uri.html`），
> 已在部署文档说明；GitHub Pages 场景提供 `DOCS_CLEAN_URLS=false` 构建开关。

---

## 4. 活服务集成评测汇总（§7 评测方案）

| 脚本 | 范围 | 结果 |
|------|------|------|
| scripts/eval/eval_m15.sh（27 项） | A+B 混合主链路 | 27/27 通过 |
| scripts/eval/eval_A_self.sh（14 项） | §7.1 需求 A | 14/14 通过 |
| scripts/eval/eval_B_self.sh + eval_B_remainder.py | §7.2 需求 B | 全部通过（明细见 §2.2） |
| 需求 C 静态评测 | §7.3 | 全部通过（见 §3） |

---

## 5. 回归测试

- 全量测试套件：**196 passed, 2 skipped**（既有测试零回归；2 skip 为既有用例）
- 前端 vue-tsc 类型检查：通过
- 前端生产构建：通过
- 文档站 VitePress 构建：通过（含 FAQ/cleanUrls 可配置）

## 6. 已知限制与说明

1. **评测 subagent 稳定性**：需求 A 评审 subagent 与三个评测 subagent 在本环境多次停滞，
   A 评审改为严格自评审兜底（发现并修复 3 处缺陷）；§7 评测以自动化脚本 + 人工核验执行，
   用例与 §7 清单一一对应。
2. **试读→注册转化**依赖前端 beacon（登录后回跳上报），后端按 (share, user) 去重。
3. **UV 统计**为单实例内存近似（重启清零）；PV/阅读数为持久化精确值。
   多 worker 部署时应用内限流/UV 按进程分裂，应以 nginx limit_req 为准（文档已注明）。
4. **L1 半自动发布**未实现（平台无开放 API），接口以 501 预留。
5. 正文水印默认关闭（`NOVEL_SHARE_WATERMARK`）；核心防线为接口权限 + 限流 + ID 不可枚举。
6. **GitHub 提交**：提供的 fine-grained PAT 为只读（Contents 无写权限，
   git refs/推送均返回 "Resource not accessible"），PR 创建需具备写权限的凭据。
