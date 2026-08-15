# 一键发布（番茄 / 七猫）

成书后，在作品工作台的「发布」页可以一键导出符合平台规范的发布包。

## 重要前提：平台现实约束

| 平台 | 作者入口 | 开放 API | 结论 |
|------|---------|---------|------|
| 番茄小说 | 番茄作家助手（App/网页） | 无公开 API | 导出后手动上传 |
| 七猫小说 | 七猫作家平台（网页） | 无公开 API | 导出后手动上传 |
| 起点/晋江等 | 各自作家后台 | 均无开放 API | 同上 |

因此发布能力分层提供：

- **L0 一键导出（当前版本）**：质量门禁 + 按平台规范打包下载，作者在平台侧手动上传；
- **L1 半自动发布（远期）**：浏览器自动化填充作家后台，停在提交前人工确认；
- **L2 全自动直发**：仅当平台开放 API 后才可能。

## 使用流程

1. 进入作品工作台 → 「发布」页；
2. 点击「运行质量门禁」：
   - 章节完整性检查（断章 / 空章会**阻断导出**）
   - 字数统计（总字数、单章均值、最短章警告）
   - 敏感词预检（本地词表，命中仅警告不阻断）
   - 平台适配检查（如番茄建议单章 ≤ 2000 字）
3. 选择目标平台，点击「一键导出下载」获得 ZIP 包；
4. 前往平台作家后台，完成实名认证、创建新书、上传正文/简介/封面；
5. 回到「发布」页，在发布记录中「回填链接」，标记为已发布。

## 平台导出规范

| 平台 | 格式 | 编码 | 分卷 | 说明 |
|------|------|------|------|------|
| 番茄小说 | 单文件 TXT | **GB18030** | 否 | 建议单章 ≤ 2000 字 |
| 七猫小说 | 按卷拆分 TXT | UTF-8 | **是** | 每个卷一个文件，按顺序上传 |
| 通用 TXT | 单文件 TXT | UTF-8 | 卷头标记 | 适用任意平台粘贴 |
| EPUB | 标准 EPUB3 | UTF-8 | 目录分章 | 阅读器直接打开 / 转格式 |

每个导出包都包含：

```
{书名}-{平台}-export.zip
├── 全文.txt / 卷01-xxx.txt / 书名.epub   # 正文（按平台格式）
├── synopsis.txt                          # 简介（取自大纲 premise/setting）
├── cover.svg                             # 封面占位图（请在平台侧替换正式封面）
├── README-发布说明.txt                    # 平台操作步骤
└── meta.json                             # 导出元数据（章节数/字数/记录ID）
```

## API 参考

```
GET   /api/publish/platforms     # 可用平台与上传规范
POST  /api/publish/preflight     # 质量门禁预检 {novel_id, platform?}
POST  /api/publish/export        # 按平台导出，返回 ZIP {novel_id, platform}
GET   /api/publish/records       # 发布历史（?novel_id 过滤）
PATCH /api/publish/records/{record_id}  # 回填平台侧书 ID / 链接（自动标记已发布）
POST  /api/publish/records/{record_id}/confirm  # (L1 预留) 平台无开放 API，当前返回 501
```

发布记录状态机：`exporting → exported → published`（失败为 `failed`；
`draft` / `publishing` 为 L1 半自动发布预留状态）。

## 敏感词表

内置基础词表覆盖典型违法广告/灰产引流词，位于
`src/novel_creator/web/publish/data/sensitive_words_base.txt`。

扩充方式（二选一）：

- 创建 `data/sensitive_words_custom.txt`（每行一词，`#` 注释）；
- 或设置 `NOVEL_SENSITIVE_WORDS_PATH=/path/to/words.txt`。

::: tip
预检命中敏感词只产生警告、不阻断导出；平台审核是最终关口，请人工复核命中章节。
:::
