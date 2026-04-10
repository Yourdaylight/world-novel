#!/usr/bin/env bash
# ============================================================
#  WorldNovel 一键开发启动 (改进版)
#  用法: ./scripts/dev.sh [--port 8000] [--no-frontend]
#
#  特性:
#    - 自动清理占用端口
#    - 自动安装依赖 (如果需要)
#    - 后端/前端日志分离到 logs/ 目录
#    - 启动后自动健康检查
#    - Ctrl+C 优雅退出
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${NOVEL_WEB_PORT:-8000}"
FRONTEND_PORT=5173
NO_FRONTEND=false
LOG_DIR="$ROOT_DIR/logs"

while [[ $# -gt 0 ]]; do
  case $1 in
    --port)         BACKEND_PORT="$2"; shift 2 ;;
    --front-port)   FRONTEND_PORT="$2"; shift 2 ;;
    --no-frontend)  NO_FRONTEND=true; shift ;;
    -h|--help)
      echo "用法: $0 [--port N] [--front-port N] [--no-frontend]"
      exit 0 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

# ── 颜色 ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; DIM='\033[2m'; NC='\033[0m'

info()  { echo -e "${BLUE}[DEV]${NC}  $*"; }
ok()    { echo -e "${GREEN}[DEV]${NC}  ✅ $*"; }
warn()  { echo -e "${YELLOW}[DEV]${NC}  ⚠️  $*"; }
error() { echo -e "${RED}[DEV]${NC}  ❌ $*"; exit 1; }

# ── 1. 清理端口 ──────────────────────────────────────────────
info "清理端口 ${BACKEND_PORT}, ${FRONTEND_PORT}..."
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    warn "已终止端口 $port 上的旧进程"
  fi
done
sleep 0.5

# ── 2. 环境检查 ──────────────────────────────────────────────
[ -f "$ROOT_DIR/.env" ] || error ".env 不存在。请复制: cp .env.example .env 并填入 API Key"

if ! command -v uv &>/dev/null; then
  error "未找到 uv。请安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# ── 3. 依赖安装 ──────────────────────────────────────────────
info "检查 Python 依赖..."
uv sync --quiet 2>/dev/null && ok "Python 依赖就绪" || {
  warn "uv sync 失败，尝试 pip install..."
  uv pip install -e "." --quiet
}

if [ "$NO_FRONTEND" = false ]; then
  info "检查前端依赖..."
  if [ ! -d "$ROOT_DIR/web/node_modules" ]; then
    cd "$ROOT_DIR/web" && npm install --silent && cd "$ROOT_DIR"
    ok "前端依赖已安装"
  else
    ok "前端依赖已存在"
  fi
fi

# ── 4. 创建日志目录 ──────────────────────────────────────────
mkdir -p "$LOG_DIR" data

# ── 5. 启动服务 ──────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  info "正在停止所有服务..."
  for pid in "${PIDS[@]+${PIDS[@]}}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  ok "所有服务已停止"
}
trap cleanup EXIT INT TERM

# 后端
BACKEND_LOG="$LOG_DIR/backend.log"
info "启动后端 (port ${BACKEND_PORT}, reload=on)..."
NOVEL_LOG_DIR="$LOG_DIR" uv run uvicorn novel_creator.web.app:app \
  --host 0.0.0.0 --port "$BACKEND_PORT" --reload \
  --reload-dir src \
  --log-level info 2>&1 | tee "$BACKEND_LOG" &
PIDS+=($!)

# 前端
if [ "$NO_FRONTEND" = false ]; then
  FRONTEND_LOG="$LOG_DIR/frontend.log"
  info "启动前端 (port ${FRONTEND_PORT})..."
  cd "$ROOT_DIR/web"
  npx vite --port "$FRONTEND_PORT" --host 2>&1 | tee "$FRONTEND_LOG" &
  PIDS+=($!)
  cd "$ROOT_DIR"
fi

# ── 6. 健康检查 ──────────────────────────────────────────────
info "等待服务启动..."
RETRIES=0
MAX_RETRIES=15
while [ $RETRIES -lt $MAX_RETRIES ]; do
  sleep 1
  RETRIES=$((RETRIES + 1))
  if curl -s --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    ok "后端已就绪 (${RETRIES}s)"
    break
  fi
  if [ $RETRIES -eq $MAX_RETRIES ]; then
    error "后端启动超时！查看日志: tail -50 $BACKEND_LOG"
  fi
done

if [ "$NO_FRONTEND" = false ]; then
  RETRIES=0
  while [ $RETRIES -lt 10 ]; do
    sleep 1
    RETRIES=$((RETRIES + 1))
    if curl -s --max-time 2 "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
      ok "前端已就绪"
      break
    fi
  done
fi

# ── 7. 输出信息 ──────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🌍 WorldNovel 开发环境已启动                          ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
if [ "$NO_FRONTEND" = false ]; then
echo -e "${GREEN}║  前端:     http://localhost:${FRONTEND_PORT}                      ║${NC}"
fi
echo -e "${GREEN}║  后端 API: http://localhost:${BACKEND_PORT}                       ║${NC}"
echo -e "${GREEN}║  API 文档: http://localhost:${BACKEND_PORT}/docs                  ║${NC}"
echo -e "${GREEN}║  健康检查: http://localhost:${BACKEND_PORT}/api/health             ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  日志目录: ${LOG_DIR}                                ║${NC}"
echo -e "${GREEN}║    后端: tail -f ${LOG_DIR}/backend.log              ║${NC}"
echo -e "${GREEN}║    应用: tail -f ${LOG_DIR}/worldnovel.log           ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  Ctrl+C 停止所有服务                                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# 等待子进程
wait
