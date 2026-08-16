# HTTP API 参考

所有接口前缀 `/api`。认证通过 `X-User-Token: <jwt>` 或 `Authorization: Bearer <jwt>`。

## 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 版本与当前 auth_mode |

## 认证

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/auth/login` | 公开 | body `{invite_code}`，返回 `{access_token,...}` |
| GET | `/auth/me` | 已登录 | 当前用户 |
| GET | `/auth/config` | 公开 | 前端用：当前模式 |
| GET | `/auth/quota` | 已登录 | 当前额度 |

## 成书发布（需求 A）

| 方法 | 路径 | 权限 |
|------|------|------|
| POST | `/publish/preflight?novel_id=&platform=` | 小说 owner/管理员 |
| POST | `/publish/export` | 小说 owner/管理员 |
| GET | `/publish/records?novel_id=` | 本人（管理员全部） |
| POST | `/publish/records/{id}/backfill` | 记录 owner/管理员 |

`preflight` 返回：

```json
{
  "ok": true,
  "errors": [],
  "warnings": [{"code": "sensitive", "message": "..."}],
  "sensitive": [],
  "stats": {"chapters": 12, "volumes": 1, "total_words": 48213}
}
```

`export` body `{"novel_id":"...","platform":"fanqie|qimao|txt|epub|rtf|bundle"}`，
成功返回文件流（`Content-Disposition` 带文件名）；质量门禁未过返回 `422`。

## 公开分享 / 注册阅读（需求 B）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/share/{id}` | 公开·限流 | 分享元数据快照 |
| GET | `/share/{id}/chapters` | 公开·限流 | 目录，每章带 `readable` 标记 |
| GET | `/share/{id}/chapter/{n}` | 公开·限流 | 正文；匿名超界 `403 need_login` |
| POST | `/share` | owner/管理员 | 创建/复用分享 |
| GET | `/shares/mine` | 已登录 | 我的分享 |
| PATCH | `/share/{id}` | 分享 owner/管理员 | 改试读策略 / 关闭 |
| GET | `/bookshelf` | 已登录 | 阅读进度 |

匿名越权响应约定：

```json
HTTP 403
{"detail": {"code": "need_login", "trial_ok": false,
            "message": "试读到这里，注册后即可阅读全部章节"}}
```

关闭/不存在的分享一律 `404`。限流超出 `429`（`Retry-After`）。

## 工作台（既有）

小说 CRUD、章节、角色、世界观、时间线、伏笔、生成控制等接口见源码
`src/novel_creator/web/routes/`，在线交互文档可由 FastAPI 自动生成（`/docs`，如启用）。
