# 成书发布

工作台进入某部小说 → 侧边栏「**成书发布**」。

## 平台现实与能力分层

番茄、七猫、起点、晋江等平台**均无公开的写作开放 API**。因此"一键发布"分层实现：

| 层级 | 能力 | 状态 |
|------|------|------|
| **L0 一键导出** | 按平台规范导出 TXT/EPUB（分卷、章节、简介、封面占位），打包下载，作者在平台后台上传 | ✅ 本期实现 |
| **L1 半自动发布** | Playwright 驱动作家后台自动填表，停在"提交审核"前人工确认 | 🔜 远期（独立 `publish-browser` 容器，接口已预留） |
| **L2 全自动直发** | 平台开放官方 API 后才做 | ⛔ 不承诺 |

## 发布前质量门禁

点击「运行预检」，服务端检查：

- **章节完整性**：空章节、断章（缺失章节号）直接阻止导出；
- **字数统计**：按中文口径（非空白字符）统计全书与单章字数；
- **敏感词预检**：内置基础词表，命中即阻止导出；支持 `NOVEL_SENSITIVE_WORDS_PATH` 指定自定义词表（每行一个词）；
- **平台规范警告**：如番茄建议单章 ≤ 2000 字，超限警告但不阻止；
- **封面/简介**：简介由大纲前提/核心冲突模板生成；ZIP 内附 `封面占位.svg`，请替换为正式封面。

## 平台适配

| 平台 | 文件 | 编码 | 分卷 | 说明 |
|------|------|------|------|------|
| 番茄小说 | ZIP：全书 TXT + 出版信息 + 封面占位 | GB18030 | ✗ | 番茄作家助手导入 |
| 七猫小说 | ZIP：全书 TXT + `分卷/` 分卷 TXT + 出版信息 | GB18030 | ✓ | 按卷结构拆分 |
| 通用 TXT | 单文件 TXT | UTF-8 | ✗ | 任意平台/自留底稿 |
| EPUB | 标准 EPUB 3（目录/封面页/样式） | UTF-8 | ✗ | 电子书渠道/Apple Books/微信读书传书 |

## 发布记录与回填

每次导出都会在全局库写入 `publication_records`（平台、时间、字数、章节数、操作人）。
在平台侧完成上传发布后，点「回填平台链接」录入作品 URL/书 ID，记录状态变为**已发布**。

## HTTP API

```bash
# 平台清单
curl http://localhost:8000/api/publish/platforms

# 预检（需登录）
curl -X POST http://localhost:8000/api/publish/preflight \
  -H "X-User-Token: <token>" -H 'Content-Type: application/json' \
  -d '{"novel_id":"my-novel","platform":"fanqie"}'

# 导出（二进制文件流）
curl -X POST http://localhost:8000/api/publish/export \
  -H "X-User-Token: <token>" -H 'Content-Type: application/json' \
  -d '{"novel_id":"my-novel","platform":"fanqie"}' --output book.zip

# 发布历史 / 回填
curl "http://localhost:8000/api/publish/records?novel_id=my-novel" -H "X-User-Token: <token>"
curl -X POST http://localhost:8000/api/publish/records/<id>/backfill \
  -H "X-User-Token: <token>" -H 'Content-Type: application/json' \
  -d '{"target_url":"https://fanqienovel.com/page/xxxx"}'
```

## L1 部署形态（远期）

L1 不会运行在 FastAPI 主进程内（浏览器崩溃不影响主服务）：

```
nginx → uvicorn :8000 (主服务)
      → publish-browser 容器 (playwright:chromium, 仅内网 :9222)
```

`POST /api/publish/records/{id}/confirm` 当前返回 `501 l1_not_enabled`，为该能力预留。
