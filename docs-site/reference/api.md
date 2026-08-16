# API 参考

WorldNovel 后端为 FastAPI，所有接口挂在 `/api` 前缀下。
完整 OpenAPI Schema 由后端自动生成：[`/openapi.json`（在线服务）](https://github.com/Yourdaylight/world-novel)，
文档站内置快照见 [openapi.json](/openapi.json)。

## 认证

三种模式（`NOVEL_AUTH_MODE`）：`jwt`（默认）/ `casdoor` / `disabled`。
受保护接口通过以下任一方式携带令牌：

- 请求头 `X-User-Token: <token>`（前端默认）
- 请求头 `Authorization: Bearer <token>`
- 查询参数 `?token=<token>`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/login` | 邀请码登录，返回 JWT |
| GET | `/auth/config` | 前端探测认证模式 |
| GET | `/auth/me` | 当前用户信息 |
| GET | `/auth/quota` | 当前用户额度 |

## 需求 A：成书发布

全部接口需要登录。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/publish/platforms` | 平台适配清单（番茄 / 七猫 / TXT / EPUB） |
| POST | `/publish/preflight` | 发布前质量门禁 `{novel_id, platform?}` |
| POST | `/publish/export` | 按平台导出文件（同时写发布记录） |
| GET | `/publish/records?novel_id=` | 发布历史 |
| PATCH | `/publish/records/{id}` | 回填平台书 ID / 链接 / 状态 |

预检响应示例：

```json
{
  "ok": true,
  "errors": [],
  "warnings": ["番茄小说建议单章 ≤ 2000 字，2 章超出…"],
  "stats": { "chapter_count": 10, "planned_count": 10, "total_words": 32000, "empty_chapters": 0 },
  "sensitive_hits": []
}
```

## 需求 B：公开分享 + 注册阅读

### 公开面（匿名可访问，限流 60 次/分钟/IP）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/share/{id}` | 分享元数据 + 当前访问级别 |
| GET | `/share/{id}/chapters` | 目录（标题 + 可读标记，**不含正文**） |
| GET | `/share/{id}/chapter/{n}` | 章节正文；超试读边界 → `403 {code:"need_login"}` |

### 作者面（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/share` | 创建 / 获取本书分享 `{novel_id, trial_mode, trial_value}` |
| GET | `/share/mine` | 我的分享列表 |
| PATCH | `/share/{id}` | 改试读策略 / 关闭（仅 owner 或管理员） |

### 读者面（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/bookshelf` | 书架 + 阅读进度 |
| POST | `/bookshelf/progress` | 上报进度 |

试读模式 `trial_mode`：`first_n_chapters`（默认，值=章数）、
`word_count`（值=累计字数）、`ratio`（值=百分比 0–100）。

## 其他既有接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/novels` | 书架列表 |
| POST | `/worlds/create` | 创建小说 |
| GET | `/novel-full?novel_id=` | 全书内容（工作台用） |
| GET | `/worlds/{id}/export/markdown` | 导出 Markdown |
| WS | `/ws` | 生成过程事件推送 |
