#!/usr/bin/env bash
# ============================================================
#  WorldNovel 一键本地启动脚本
#  用法: ./scripts/start-local.sh [--prod] [--port 8000]
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── 参数解析 ────────────────────────────────────────────────
MODE="dev"
BACKEND_PORT=8000
FRONTEND_PORT=5173

while [[ $# -gt 0 ]]; do
  case $1 in
    --prod)       MODE="prod"; shift ;;
    --port)       BACKEND_PORT="$2"; shift 2 ;;
    --front-port) FRONTEND_PORT="$2"; shift 2 ;;
    -h|--help)
      echo "用法: $0 [选项]"
      echo ""
      echo "选项:"
      echo "  --prod          生产模式 (构建前端, 单进程服务)"
      echo "  --port N        后端端口 (默认 8000)"
      echo "  --front-port N  前端开发端口 (默认 5173, 仅 dev 模式)"
      echo "  -h, --help      显示帮助"
      exit 0
      ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

# ── 颜色 ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 依赖检查 ────────────────────────────────────────────────
info "检查依赖..."

# Python
if command -v uv &>/dev/null; then
  PY_TOOL="uv"
elif [ -f "$ROOT_DIR/.venv/bin/python" ]; then
  PY_TOOL="venv"
else
  error "未找到 uv 或 .venv。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Node
command -v node &>/dev/null || error "未找到 Node.js。请安装: https://nodejs.org/"
command -v npm  &>/dev/null || error "未找到 npm。"

ok "Python: $([ "$PY_TOOL" = "uv" ] && uv run python --version 2>/dev/null || .venv/bin/python --version)"
ok "Node:   $(node --version)"
ok "npm:    $(npm --version)"

# ── .env 检查 ───────────────────────────────────────────────
if [ ! -f "$ROOT_DIR/.env" ]; then
  if [ -f "$ROOT_DIR/.env.example" ]; then
    warn ".env 不存在，从 .env.example 复制..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    warn "请编辑 .env 填入你的 API Key: $ROOT_DIR/.env"
    exit 1
  else
    error ".env 文件不存在，请创建。参考 .env.example"
  fi
fi

ok ".env 已就绪"

# ── Python 依赖 ─────────────────────────────────────────────
info "安装 Python 依赖..."
if [ "$PY_TOOL" = "uv" ]; then
  uv sync --quiet 2>/dev/null || uv pip install -e "." --quiet
else
  .venv/bin/pip install -e "." --quiet 2>/dev/null
fi
ok "Python 依赖已安装"

# ── 前端依赖 ────────────────────────────────────────────────
info "安装前端依赖..."
cd "$ROOT_DIR/web"
if [ ! -d "node_modules" ]; then
  npm install --silent
else
  ok "node_modules 已存在，跳过安装"
fi
cd "$ROOT_DIR"
ok "前端依赖已安装"

# ── 数据目录 ────────────────────────────────────────────────
mkdir -p "$ROOT_DIR/data"
ok "数据目录已就绪"

# ── 启动 ────────────────────────────────────────────────────
# 收集子进程 PID，退出时一起清理
PIDS=()
cleanup() {
  echo ""
  info "正在停止服务..."
  for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  ok "所有服务已停止"
}
trap cleanup EXIT INT TERM

if [ "$MODE" = "prod" ]; then
  # ── 生产模式 ──────────────────────────────────────────────
  info "=== 生产模式 ==="

  # 构建前端 (如果 dist/ 不存在或源码比 dist 新则重新构建)
  if [ ! -f "$ROOT_DIR/web/dist/index.html" ] || \
     [ "$(find "$ROOT_DIR/web/src" -newer "$ROOT_DIR/web/dist/index.html" -print -quit 2>/dev/null)" ]; then
    info "构建前端..."
    cd "$ROOT_DIR/web"
    npm run build --silent 2>&1 | tail -3
    cd "$ROOT_DIR"
    ok "前端构建完成 → web/dist/"
  else
    ok "前端 dist/ 已是最新，跳过构建"
  fi

  # 启动后端 (serve web/dist/)
  info "启动服务: http://0.0.0.0:${BACKEND_PORT}"
  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  🌍 WorldNovel 已启动 (生产模式)                   ║${NC}"
  echo -e "${GREEN}║                                                  ║${NC}"
  echo -e "${GREEN}║  地址: http://localhost:${BACKEND_PORT}                    ║${NC}"
  echo -e "${GREEN}║  API:  http://localhost:${BACKEND_PORT}/docs                ║${NC}"
  echo -e "${GREEN}║                                                  ║${NC}"
  echo -e "${GREEN}║  Ctrl+C 停止服务                                 ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""

  if [ "$PY_TOOL" = "uv" ]; then
    uv run worldnovel web --host 0.0.0.0 --port "$BACKEND_PORT"
  else
    .venv/bin/worldnovel web --host 0.0.0.0 --port "$BACKEND_PORT"
  fi

else
  # ── 开发模式 ──────────────────────────────────────────────
  info "=== 开发模式 ==="

  # 启动后端 (with reload)
  info "启动后端 (port ${BACKEND_PORT}, reload=on)..."
  if [ "$PY_TOOL" = "uv" ]; then
    uv run uvicorn novel_creator.web.app:app \
      --host 0.0.0.0 --port "$BACKEND_PORT" --reload \
      --reload-dir src 2>&1 &
  else
    .venv/bin/uvicorn novel_creator.web.app:app \
      --host 0.0.0.0 --port "$BACKEND_PORT" --reload \
      --reload-dir src 2>&1 &
  fi
  PIDS+=($!)
  sleep 1

  # 启动前端 Vite dev server
  info "启动前端 (port ${FRONTEND_PORT})..."
  cd "$ROOT_DIR/web"
  npx vite --port "$FRONTEND_PORT" --host 2>&1 &
  PIDS+=($!)
  cd "$ROOT_DIR"
  sleep 2

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  🌍 WorldNovel 已启动 (开发模式)                   ║${NC}"
  echo -e "${GREEN}║                                                  ║${NC}"
  echo -e "${GREEN}║  前端: http://localhost:${FRONTEND_PORT}                   ║${NC}"
  echo -e "${GREEN}║  后端: http://localhost:${BACKEND_PORT}                    ║${NC}"
  echo -e "${GREEN}║  API:  http://localhost:${BACKEND_PORT}/docs                ║${NC}"
  echo -e "${GREEN}║                                                  ║${NC}"
  echo -e "${GREEN}║  前端热更新已开启 · 后端自动重载已开启             ║${NC}"
  echo -e "${GREEN}║  Ctrl+C 停止所有服务                              ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""

  # 等待子进程
  wait
fi
