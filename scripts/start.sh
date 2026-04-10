#!/usr/bin/env bash
# ============================================================
#  WorldEngine 一键启动脚本（生产模式）
#  用法: ./scripts/start.sh [--port 8000] [--build-only]
#
#  功能:
#    1. 安装 Python + Node 依赖
#    2. 构建前端 (npm run build)
#    3. 启动后端 FastAPI，同时托管前端静态文件
#    4. 单端口访问，无需前后端分离部署
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── 参数解析 ────────────────────────────────────────────────
PORT=8000
BUILD_ONLY=false

for arg in "$@"; do
  case $arg in
    --port=*)     PORT="${arg#*=}"; shift ;;
    --port)       PORT="$2"; shift 2 ;;
    --build-only) BUILD_ONLY=true; shift ;;
    --help|-h)
      echo "用法: $0 [选项]"
      echo ""
      echo "  --port N        服务端口 (默认 8000)"
      echo "  --build-only    仅构建前端，不启动服务"
      echo "  --help, -h      显示帮助"
      exit 0
      ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

# ── 颜色 ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
banner() {
  echo ""
  echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}${BOLD}║${NC} ${BOLD}🌍 WorldEngine — 一键启动${NC}                           ${GREEN}${BOLD}║${NC}"
  echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
}

cleanup() {
  echo ""
  info "正在停止服务..."
  # 杀掉所有子进程
  jobs -p | xargs -r kill 2>/dev/null || true
  wait 2>/dev/null || true
  ok "服务已停止"
}
trap cleanup EXIT INT TERM

# ============================================================
#  Step 1: 环境检查
# ============================================================
banner
info "Step 1/5 · 环境检查..."

# Python 工具链
if command -v uv &>/dev/null; then
  PY_CMD="uv run python"
  PY_MAIN="uv run uvicorn novel_creator.web.app:app"
elif [ -f "$ROOT_DIR/.venv/bin/python" ]; then
  PY_CMD=".venv/bin/python"
  PY_MAIN=".venv/bin/uvicorn novel_creator.web.app:app"
else
  error "未找到 uv 或 .venv。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

command -v node &>/dev/null || error "未找到 Node.js → https://nodejs.org/"
command -v npm  &>/dev/null || error "未找到 npm"

ok "Python: $($PY_CMD --version 2>/dev/null || echo 'available')"
ok "Node:   $(node --version)"
ok "npm:    $(npm --version)"

# ── .env 检查 ───────────────────────────────────────────────
if [ ! -f "$ROOT_DIR/.env" ]; then
  if [ -f "$ROOT_DIR/.env.example" ]; then
    warn ".env 不存在，从 .env.example 复制..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    warn "⚠️  请编辑 $ROOT_DIR/.env 填入你的 API Key 后重新运行！"
    exit 1
  else
    error ".env 和 .env.example 都不存在，无法继续"
  fi
fi
ok ".env 已就绪"

# ============================================================
#  Step 2: 安装依赖
# ============================================================
info "Step 2/5 · 安装依赖..."

# Python
info "  安装 Python 依赖..."
if command -v uv &>/dev/null; then
  uv sync --quiet 2>/dev/null || uv pip install -e "." --quiet 2>/dev/null || true
else
  .venv/bin/pip install -e "." --quiet 2>/dev/null || true
fi
ok "Python 依赖已安装"

# Node
info "  安装前端依赖..."
cd "$ROOT_DIR/web"
if [ ! -d "node_modules" ]; then
  npm install --silent 2>&1 | tail -1
else
  ok "node_modules 已存在，跳过安装"
fi
cd "$ROOT_DIR"
ok "前端依赖已安装"

# ============================================================
#  Step 3: 构建前端
# ============================================================
info "Step 3/5 · 构建前端..."

cd "$ROOT_DIR/web"

# 判断是否需要重建
NEED_BUILD=false
if [ ! -f "dist/index.html" ]; then
  NEED_BUILD=true
  info "  dist/ 不存在，需要构建"
else
  # 检查源码是否有更新
  NEWER_SRC=$(find "$ROOT_DIR/web/src" -newer "dist/index.html" -print -quit 2>/dev/null || true)
  if [ -n "$NEWER_SRC" ]; then
    NEED_BUILD=true
    info "  检测到源码更新，重新构建..."
  fi
fi

if [ "$NEED_BUILD" = true ]; then
  info "  正在构建前端 (npm run build)..."
  if npm run build 2>&1; then
    ok "前端构建完成 → web/dist/"
  else
    error "前端构建失败！请检查上方错误信息"
  fi
else
  ok "dist/ 已是最新，跳过构建"
fi

cd "$ROOT_DIR"

# 如果只是构建模式，到此结束
if [ "$BUILD_ONLY" = true ]; then
  echo ""
  ok "✅ 构建完成！使用 '$0 --port $PORT' 启动服务"
  exit 0
fi

# ============================================================
#  Step 4: 准备数据目录
# ============================================================
info "Step 4/5 · 准备数据目录..."
mkdir -p "$ROOT_DIR/data"
ok "data/ 目录已就绪"

# ============================================================
#  Step 5: 启动服务
# ============================================================
info "Step 5/5 · 启动 WorldEngine..."

echo ""
echo -e "${GREEN}${BOLD}╔═════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║${NC}  ${BOLD}🌍 WorldEngine 已就绪${NC}                                    ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}║${NC}                                                            ${GREEN}${BOLD}║${NC}"
printf "${GREEN}${BOLD}║${NC}  📡 界面:  %-44s${GREEN}${BOLD}║${NC}\n" "http://localhost:${PORT}"
printf "${GREEN}${BOLD}║${NC}  🔌 API:   %-44s${GREEN}${BOLD}║${NC}\n" "http://localhost:${PORT}/docs"
printf "${GREEN}${BOLD}║${NC}  📁 DB:    %-44s${GREEN}${BOLD}║${NC}\n" "$ROOT_DIR/data/novel.db"
echo -e "${GREEN}${BOLD}║${NC}                                                            ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}║${NC}  按 Ctrl+C 停止服务                                       ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}╚═════════════════════════════════════════════════════════╝${NC}"
echo ""

# 单进程：FastAPI 同时托管 API + 前端静态文件
exec $PY_MAIN \
  --host 0.0.0.0 \
  --port "$PORT" \
  --log-level info
