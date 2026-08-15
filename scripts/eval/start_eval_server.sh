#!/usr/bin/env bash
# Start an isolated eval server on :8123 with its own data dir + jwt auth.
# Usage: ./scripts/eval/start_eval_server.sh  (Ctrl+C to stop)
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

EVAL_DIR="${ROOT_DIR}/data-eval"
mkdir -p "$EVAL_DIR"

export NOVEL_DB_PATH="$EVAL_DIR/novel.db"
export NOVEL_AUTH_MODE=jwt
export NOVEL_JWT_SECRET=eval-secret-do-not-use-in-prod
export NOVEL_WEB_PORT=8123
unset NOVEL_AUTH_ENABLED || true

# Seed demo data + run server from the SAME dir (registry uses CWD-relative paths)
cd "$EVAL_DIR"
uv run --project "$ROOT_DIR" python "$ROOT_DIR/scripts/eval/seed_demo_novel.py" --chapters 12

echo "→ eval server at http://127.0.0.1:8123 (data: $EVAL_DIR)"
exec uv run --project "$ROOT_DIR" uvicorn novel_creator.web.app:app --host 127.0.0.1 --port 8123 --no-proxy-headers
