# API 参考

> 本页由 OpenAPI schema 自动生成：`uv run python docs-site/scripts/gen_api_reference.py`
> 交互式 Swagger UI 仅本地开发可用：启动服务后访问 `http://localhost:8000/docs`
> （生产环境 `/docs/` 路径由本文档站占用）。

认证方式：请求头 `X-User-Token: <token>` 或 `Authorization: Bearer <token>`。jwt 模式下 token 来自 `POST /api/auth/login`（邀请码登录）。

## 认证与额度

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/auth/config` | Auth Config |
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/auth/me` | Auth Me |
| `GET` | `/api/auth/quota` | Get My Quota |
| `POST` | `/api/auth/refresh` | Refresh Token |
| `GET` | `/api/auth/sidecar/callback` | Sidecar Callback |
| `GET` | `/api/auth/sidecar/login` | Sidecar Login Get |
| `POST` | `/api/auth/sidecar/login` | Sidecar Login Post |
| `POST` | `/api/auth/sidecar/logout` | Sidecar Logout |
| `GET` | `/api/auth/sidecar/logout-complete` | Sidecar Logout Complete |
| `POST` | `/api/auth/sidecar/refresh` | Auth Sidecar Refresh |

## 分享与阅读

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/bookshelf` | Get Bookshelf |
| `PUT` | `/api/bookshelf/{novel_id}` | Update Bookshelf |
| `POST` | `/api/share` | Create Share |
| `GET` | `/api/share/{share_id}` | Get Share Page |
| `PATCH` | `/api/share/{share_id}` | Patch Share |
| `DELETE` | `/api/share/{share_id}` | Disable Share |
| `GET` | `/api/share/{share_id}/chapter/{chapter_index}` | Get Share Chapter |
| `GET` | `/api/share/{share_id}/chapters` | Get Share Chapters |
| `POST` | `/api/share/{share_id}/conversion` | Share Conversion |
| `GET` | `/api/share/{share_id}/progress` | Get My Progress |
| `PUT` | `/api/share/{share_id}/progress` | Update My Progress |
| `GET` | `/api/share/{share_id}/stats` | Share Stats |
| `GET` | `/api/shares` | List My Shares |

## 成书发布

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/publish/export` | Publish Export |
| `GET` | `/api/publish/platforms` | List Platforms |
| `POST` | `/api/publish/preflight` | Publish Preflight |
| `GET` | `/api/publish/records` | Publish Records |
| `PATCH` | `/api/publish/records/{record_id}` | Publish Backfill |
| `POST` | `/api/publish/records/{record_id}/confirm` | Publish Confirm |

## 管理后台

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/invite-codes` | Admin List Invite Codes |
| `POST` | `/api/admin/invite-codes` | Admin Create Invite Code |
| `DELETE` | `/api/admin/invite-codes/{code}` | Admin Delete Invite Code |
| `POST` | `/api/admin/invite-codes/{code}/deactivate` | Admin Deactivate Invite Code |
| `GET` | `/api/admin/usage-summary` | Admin Get Usage Summary |
| `GET` | `/api/admin/users/{code}/quota` | Admin Get User Quota |
| `POST` | `/api/admin/users/{code}/quota` | Admin Set User Quota |
| `POST` | `/api/admin/users/{code}/quota/add` | Admin Add User Quota |
| `GET` | `/api/admin/users/{code}/usage` | Admin Get User Usage |

## 史官 / AI

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/ai/analyze-proposition` | Api Analyze Proposition |
| `POST` | `/api/ai/historian-chat` | Api Historian Chat |
| `POST` | `/api/ai/historian-write-file` | Api Historian Write File |

## 章节与内容

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/chapter-text/{chapter_index}` | Get Chapter Text |
| `GET` | `/api/chapters` | Get Chapters |
| `GET` | `/api/novel-full` | Get Novel Full |

## 角色与 Agent

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/actions/{chapter_index}` | Get Chapter Actions |
| `GET` | `/api/agents/{character_id}/files` | Get Agent Files |
| `GET` | `/api/agents/{character_id}/skills` | List Character Skills |
| `POST` | `/api/agents/{character_id}/skills` | Create Character Skill |
| `PUT` | `/api/agents/{character_id}/skills/{skill_id}` | Update Character Skill |
| `DELETE` | `/api/agents/{character_id}/skills/{skill_id}` | Delete Character Skill |
| `PUT` | `/api/agents/{character_id}/skills/{skill_id}/toggle` | Toggle Character Skill |
| `PUT` | `/api/agents/{character_id}/soul` | Update Agent Soul |
| `GET` | `/api/characters/{character_id}/actions-all` | Get Character All Actions |
| `GET` | `/api/characters/{character_id}/era-summaries` | Get Era Summaries |
| `GET` | `/api/characters/{character_id}/full-profile` | Get Character Full Profile |
| `GET` | `/api/characters/{character_id}/memories` | Get Character Memories |
| `GET` | `/api/characters/{character_id}/memory-heat` | Get Memory Heat |
| `GET` | `/api/emotions/{character_id}` | Get Emotion History |

## 世界观与故事

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/foreshadows` | Get Foreshadows |
| `GET` | `/api/god-decisions` | Get God Decisions |
| `GET` | `/api/graph/path` | Get Graph Path |
| `GET` | `/api/graph/relationships` | Get Graph Data |
| `GET` | `/api/graph/social-context/{character_id}` | Get Social Context |
| `POST` | `/api/memory/consolidate` | Consolidate Memories |
| `GET` | `/api/outline` | Get Outline |
| `GET` | `/api/plot-threads` | Get Plot Threads |
| `GET` | `/api/relationship-history` | Get Relationship History |
| `GET` | `/api/relationships` | Get Relationships |
| `GET` | `/api/story` | Get Story |
| `GET` | `/api/timeline` | Get Timeline |
| `GET` | `/api/token-stats` | Get Token Stats |
| `GET` | `/api/world` | Get World |
| `PUT` | `/api/world` | Api Save World |

## 小说与世界

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/novels` | Api List Novels |
| `GET` | `/api/novels/active` | Api Active Novel |
| `POST` | `/api/novels/select` | Api Select Novel |
| `POST` | `/api/worlds/create` | Api Create World |
| `DELETE` | `/api/worlds/{novel_id}` | Api Delete World |
| `GET` | `/api/worlds/{novel_id}/export/json` | Api Export Json |
| `GET` | `/api/worlds/{novel_id}/export/markdown` | Api Export Markdown |
| `GET` | `/api/worlds/{novel_id}/files` | Api List World Files |
| `GET` | `/api/worlds/{novel_id}/files/download` | Api Download File |
| `GET` | `/api/worlds/{novel_id}/propositions` | Api Get Propositions |
| `GET` | `/api/worlds/{novel_id}/status` | Api World Status |

## 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | Health |
| `GET` | `/{full_path}` | Spa Fallback |
