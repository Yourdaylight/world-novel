# 成书发布（番茄 / 七猫）

## 现实约束：平台没有开放 API

番茄小说、七猫小说、起点、晋江等主流网文平台**均未公开开放 API**。
因此 WorldNovel 的「一键发布」分层定义：

| 层级 | 能力 | 状态 |
| --- | --- | --- |
| **L0 一键导出** | 按平台规范导出 TXT / EPUB / 分卷 ZIP，作者手动上传 | ✅ 本期实现 |
| L1 半自动发布 | Playwright 驱动作家后台，停在「提交审核」前人工确认 | 🚧 远期 |
| L2 全自动直发 | 仅当平台开放合规 API 时 | 🔭 不承诺 |

## 使用流程

工作台 → 选择小说 → 侧栏「**成书发布**」：

1. **选择平台**：番茄小说 / 七猫小说 / 通用 TXT / EPUB；
2. **运行质量门禁**：检查断章、空章、字数、敏感词；
3. **一键导出**：浏览器下载导出物，每次导出自动写入发布记录；
4. 到对应平台**作家后台手动上传**；
5. 平台侧发布成功后，回到发布记录点击「回填链接」，粘贴作品 URL，记录标记为「已发布」。

## 平台导出规范

| 平台 | 格式 | 编码 | 说明 |
| --- | --- | --- | --- |
| 番茄小说 | 单文件 TXT | **GB18030** | 章节以「第N章 标题」分隔；建议单章 ≤ 2000 字，超长章节门禁会警告 |
| 七猫小说 | ZIP | GB18030 | 按分卷生成 TXT，附 `简介.txt` 与 `cover.svg` 封面占位 |
| 通用 TXT | 单文件 TXT | UTF-8 | 适用任意支持 TXT 导入的平台 |
| EPUB | EPUB3 | UTF-8 | 含书名页、目录导航、分卷分组 |

## 质量门禁检查项

- **错误（阻断导出）**：无已渲染章节；存在断章（缺少计划中的章节）；空章节；
- **警告（不阻断）**：章节过短（< 300 字）；缺少书名/简介；超出平台单章字数建议；敏感词命中。

敏感词预检使用仓库自带基础词表（`src/novel_creator/publishing/sensitive_words.txt`），
在 `data/config/sensitive_words.txt` 放置自定义词表可叠加扩展。
**本地预检仅为辅助，最终以平台审核为准。**

## API

```
GET  /api/publish/platforms           平台适配清单
POST /api/publish/preflight           质量门禁预检
POST /api/publish/export              按平台导出（同时写发布记录）
GET  /api/publish/records?novel_id=   发布历史
PATCH /api/publish/records/{id}       回填平台书 ID / 链接 / 状态
```

全部接口需要登录（jwt / casdoor 任一模式）。示例：

```bash
# 预检
curl -X POST http://localhost:8000/api/publish/preflight \
  -H "X-User-Token: <jwt>" -H "Content-Type: application/json" \
  -d '{"novel_id": "my-book", "platform": "fanqie"}'

# 导出
curl -X POST http://localhost:8000/api/publish/export \
  -H "X-User-Token: <jwt>" -H "Content-Type: application/json" \
  -d '{"novel_id": "my-book", "platform": "fanqie"}' \
  --output book-fanqie.txt
```

## 数据模型

每次导出写入全局库 `publication_records` 表：

| 字段 | 含义 |
| --- | --- |
| id | 记录 ID（`pub_` 前缀） |
| novel_id / platform | 小说 / 平台 |
| stage | exported / published / failed |
| target_book_id / target_url | 平台侧回填 |
| export_meta | 章节数、字数、格式、编码等 |
| operator | 触发人（JWT code / Sidecar sub） |

## 部署说明

- L0 导出在 FastAPI 进程内完成（SQLite → 内存拼装 → 下载），**不新增任何服务**；
- 一本百万字小说导出的峰值内存约为正文的 3–5 倍，单进程 systemd 部署无压力；
- 远期 L1 的 Playwright 浏览器将作为**独立 sidecar 容器**运行，不进主进程。
