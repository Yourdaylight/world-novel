# 环境变量

变量可写入项目根目录 `.env`（启动时自动加载，参考 `.env.example`）；已存在的真实环境变量优先级高于 `.env`。除 `WORLDENGINE_JWT_SECRET` 外，业务变量均为 `NOVEL_` 前缀。

| 变量 | 默认 | 说明 |
|------|------|------|
| `NOVEL_AUTH_MODE` | `jwt` | `jwt` / `casdoor` / `disabled` |
| `WORLDENGINE_JWT_SECRET`（亦可 `NOVEL_JWT_SECRET` 回退） | 开发默认值 | jwt 签名密钥，**生产必须修改** |
| `NOVEL_ADMIN_CODE_PREFIX` | `admin` | 以此开头的邀请码自动成为管理员 |
| `NOVEL_AUTH_SIDECAR_URL` | — | casdoor 模式的 sidecar 地址 |
| `NOVEL_PUBLIC_ORIGIN` | `http://localhost:8000` | 对外源，用于回调 / 登录链接 |
| `NOVEL_CORS_ORIGINS` | `*` | 逗号分隔，生产应限定具体域名 |
| `NOVEL_DB_PATH` | `data/novel.db` | 中央库（邀请码/额度/分享/发布记录） |
| `NOVEL_WEB_HOST` / `NOVEL_WEB_PORT` | `0.0.0.0` / `8000` | 监听地址 |
| `NOVEL_LLM_PROVIDER` | — | `openai` / `openrouter` |
| `NOVEL_OPENAI_API_KEY` | — | LLM Key |
| `NOVEL_OPENAI_BASE_URL` | OpenAI | OpenAI 兼容 base_url |
| `NOVEL_DIRECTOR_MODEL` / `NOVEL_CHARACTER_MODEL` / `NOVEL_WRITER_MODEL` / `NOVEL_GOD_MODEL` | gpt-4o 等 | 各 Agent 模型 |
| `NOVEL_OPENROUTER_API_KEY` / `NOVEL_OPENROUTER_BASE_URL` | — | provider=openrouter 时生效 |
| `NOVEL_EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 嵌入模型 |
| `NOVEL_TRUST_PROXY` | `false` | 位于受信反代后时置真，按 XFF 最右一跳限流 |
| `NOVEL_SENSITIVE_WORDS_PATH` | — | 自定义敏感词表，与内置表合并 |

> 完整字段见 `src/novel_creator/config.py` 的 `Settings`。

### 可选基础设施

| 变量 | 说明 |
|------|------|
| `NOVEL_QDRANT_ENABLED` / `NOVEL_QDRANT_HOST` | Qdrant 向量库 |
| `NOVEL_NEO4J_ENABLED` / `NOVEL_NEO4J_URI` / `NOVEL_NEO4J_USER` / `NOVEL_NEO4J_PASSWORD` | Neo4j 图数据库 |
