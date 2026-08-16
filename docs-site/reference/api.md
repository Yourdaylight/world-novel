# HTTP API 参考

所有接口前缀 `/api`。需要登录的接口接受 `X-User-Token: <token>`、`Authorization: Bearer <token>` 或 `?token=` 三种凭证传递方式。交互式文档见服务自带的 `/docs`（OpenAPI）。

## 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/login` | 邀请码登录，返回 JWT 与额度 |
| GET | `/auth/config` | 当前认证模式（jwt / casdoor / disabled） |
| GET | `/auth/me` | 当前用户（需登录） |
| POST | `/auth/refresh` | 刷新 JWT（需登录） |

## 小说与生成

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/novels` | 小说列表（含真实章节数） |
| POST | `/worlds/create` | 创建小说（需登录） |
| DELETE | `/worlds/{id}` | 删除小说（需登录） |
| GET | `/worlds/{id}/status` | 生成状态/进度 |
| POST | `/worlds/{id}/generate` | 开始生成（需登录） |
| POST | `/worlds/{id}/resume` | 继续生成（需登录） |
| POST | `/worlds/{id}/pause` | 暂停生成（需登录） |
| GET | `/chapter-text/{n}` | 工作台章节内容（需登录） |
| GET | `/novel-full` | 工作台全书文本（需登录） |

> 工作台接口面向作者本人；面向公众的阅读通道是下面的分享接口（随机短码 + 权限边界）。

## 成书发布（L0）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/publish/platforms` | 公开 | 平台适配清单 |
| POST | `/publish/preflight` | 作者 | 质量门禁预检 `{novel_id, platform}` |
| POST | `/publish/export` | 作者 | 导出 TXT/EPUB/ZIP（门禁不过返回 409） |
| GET | `/publish/records` | 作者 | 发布历史（本人；管理员全部） |
| POST | `/publish/records/{id}/backfill` | 作者 | 回填平台链接，标记已发布 |
| POST | `/publish/records/{id}/confirm` | 作者 | L1 预留，当前 501 |

预检返回：

```json
{
  "ok": true,
  "errors": [],
  "warnings": ["第3章 约 2400 字，超过番茄建议单章 2000 字，建议拆分"],
  "sensitive_hits": [],
  "stats": { "chapters": 10, "total_words": 28400, "encoding": "gb18030" }
}
```

## 公开分享与阅读

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/share` | 作者 | 创建/复用分享链接 |
| GET | `/shares` | 作者 | 我的分享列表 |
| PATCH | `/share/{id}` | 作者 | 修改试读策略、关闭/重开 |
| GET | `/share/{id}` | 公开（限流） | 分享页元数据快照（不含 novel_id） |
| GET | `/share/{id}/chapters` | 公开（限流） | 目录 + 逐章可读标记 |
| GET | `/share/{id}/chapter/{n}` | 公开（限流） | 单章正文；越权返回 403 `need_login` |
| POST | `/share/{id}/progress` | 注册读者 | 上报阅读进度 |
| GET | `/bookshelf` | 注册读者 | 书架 |

越权响应（试读边界外）：

```
HTTP 403
{ "code": "need_login", "message": "该章节超出试读范围，注册后即可阅读全部章节", "trial_ok": false }
```

分享关闭或不存在统一返回 404（不区分"不存在"与"已关闭"，避免探测）。

## 错误码约定

| 状态码 | 含义 |
|--------|------|
| 400 | 参数非法 |
| 401 | 未登录 / 凭证失效 |
| 403 | 无权操作（他人资源、越权章节） |
| 404 | 资源不存在或已关闭 |
| 409 | 业务冲突（质量门禁不通过等） |
| 429 | 触发限流 |
| 501 | L1 等远期能力未启用 |
