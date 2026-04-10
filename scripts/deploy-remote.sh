#!/usr/bin/env bash
# ============================================================
#  WorldNovel 远程部署脚本
#
#  用法:
#    ./scripts/deploy-remote.sh user@host [选项]
#
#  功能:
#    1. rsync 同步源码到远程服务器
#    2. 远程安装依赖 (uv + npm)
#    3. 远程构建前端
#    4. 远程启动服务 (tmux 后台)
#
#  前提:
#    - 已配置 SSH 免密登录 (ssh-copy-id)
#    - 远程已安装 Python 3.11+ / Node 18+ / uv
# ============================================================
set -euo pipefail

# ── 参数解析 ────────────────────────────────────────────────
REMOTE_HOST=""
REMOTE_DIR="/opt/worldnovel"
REMOTE_PORT=8000
ENV_FILE=""
SKIP_DEPS=false
RESTART_ONLY=false

usage() {
  cat <<EOF
用法: $0 user@host [选项]

参数:
  user@host          远程服务器 SSH 地址 (必需)

选项:
  --dir PATH         远程安装目录 (默认: /opt/worldnovel)
  --port N           服务端口 (默认: 8000)
  --env FILE         本地 .env 文件路径 (将同步到远程)
  --skip-deps        跳过依赖安装 (仅同步代码并重启)
  --restart          仅重启服务 (不同步代码)
  -h, --help         显示帮助

示例:
  $0 root@42.123.45.67
  $0 deploy@myserver --dir /home/deploy/worldnovel --port 9000
  $0 root@myserver --env .env.production --skip-deps
  $0 root@myserver --restart
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)     usage ;;
    --dir)         REMOTE_DIR="$2"; shift 2 ;;
    --port)        REMOTE_PORT="$2"; shift 2 ;;
    --env)         ENV_FILE="$2"; shift 2 ;;
    --skip-deps)   SKIP_DEPS=true; shift ;;
    --restart)     RESTART_ONLY=true; shift ;;
    -*)            echo "未知选项: $1"; exit 1 ;;
    *)             REMOTE_HOST="$1"; shift ;;
  esac
done

[ -z "$REMOTE_HOST" ] && { echo "错误: 请指定远程主机 (user@host)"; echo ""; usage; }

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

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

# ── SSH 连通性检查 ──────────────────────────────────────────
info "检查 SSH 连接到 ${REMOTE_HOST}..."
ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "echo ok" &>/dev/null \
  || error "无法连接到 ${REMOTE_HOST}。请确认:
  1. SSH 地址正确
  2. 已配置免密登录 (ssh-copy-id ${REMOTE_HOST})
  3. 防火墙允许 SSH"
ok "SSH 连接成功"

# ── 仅重启模式 ─────────────────────────────────────────────
if [ "$RESTART_ONLY" = true ]; then
  info "仅重启模式..."
  ssh "$REMOTE_HOST" bash <<RESTART_EOF
    set -e
    # 停止旧进程
    if tmux has-session -t worldnovel 2>/dev/null; then
      tmux kill-session -t worldnovel
      echo "[OK] 旧服务已停止"
    fi
    # 启动
    cd "${REMOTE_DIR}"
    tmux new-session -d -s worldnovel \
      "source .venv/bin/activate && worldnovel web --host 0.0.0.0 --port ${REMOTE_PORT} 2>&1 | tee logs/server.log"
    echo "[OK] 服务已重启 → http://\$(hostname -I | awk '{print \$1}'):${REMOTE_PORT}"
RESTART_EOF
  ok "远程服务已重启"
  exit 0
fi

# ── 同步源码 ───────────────────────────────────────────────
info "同步源码到 ${REMOTE_HOST}:${REMOTE_DIR}..."

# 创建远程目录
ssh "$REMOTE_HOST" "mkdir -p ${REMOTE_DIR}"

# rsync 排除不需要的文件
rsync -azP --delete \
  --exclude '.venv/' \
  --exclude 'web/node_modules/' \
  --exclude 'web/dist/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.git/' \
  --exclude '.claude/' \
  --exclude '.claude-internal/' \
  --exclude 'data/*.db' \
  --exclude '.ruff_cache/' \
  --exclude '.pytest_cache/' \
  "$ROOT_DIR/" "${REMOTE_HOST}:${REMOTE_DIR}/"

ok "源码同步完成"

# ── 同步 .env ──────────────────────────────────────────────
if [ -n "$ENV_FILE" ]; then
  info "同步 .env 文件: ${ENV_FILE}"
  scp "$ENV_FILE" "${REMOTE_HOST}:${REMOTE_DIR}/.env"
  ok ".env 已同步"
elif [ -f "$ROOT_DIR/.env" ]; then
  # 检查远程是否已有 .env
  if ! ssh "$REMOTE_HOST" "[ -f ${REMOTE_DIR}/.env ]"; then
    info "同步本地 .env 到远程..."
    scp "$ROOT_DIR/.env" "${REMOTE_HOST}:${REMOTE_DIR}/.env"
    ok ".env 已同步"
  else
    ok "远程 .env 已存在，跳过"
  fi
fi

# ── 远程安装依赖 + 构建 + 启动 ────────────────────────────
info "远程安装依赖并启动服务..."

ssh "$REMOTE_HOST" bash <<REMOTE_EOF
  set -e

  cd "${REMOTE_DIR}"
  mkdir -p logs data

  echo ""
  echo "=========================================="
  echo "  远程部署: ${REMOTE_DIR}"
  echo "=========================================="
  echo ""

  # ── 检查工具链 ──────────────────────────────
  echo "[INFO] 检查工具链..."

  # uv
  if ! command -v uv &>/dev/null; then
    echo "[INFO] 安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="\$HOME/.local/bin:\$PATH"
  fi
  echo "[OK] uv: \$(uv --version)"

  # Node
  if ! command -v node &>/dev/null; then
    echo "[ERROR] Node.js 未安装。请先安装: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
    exit 1
  fi
  echo "[OK] node: \$(node --version)"

  # ── Python 依赖 ────────────────────────────
  if [ "${SKIP_DEPS}" = "false" ]; then
    echo "[INFO] 安装 Python 依赖..."
    uv sync --quiet 2>/dev/null || {
      uv venv .venv --python 3.11 2>/dev/null || true
      uv pip install -e "." --quiet
    }
    echo "[OK] Python 依赖已安装"

    # ── 前端依赖 + 构建 ────────────────────────
    echo "[INFO] 安装前端依赖..."
    cd web
    npm install --silent 2>/dev/null
    echo "[INFO] 构建前端..."
    npm run build --silent 2>&1 | tail -3
    cd ..
    echo "[OK] 前端构建完成 → web/dist/"
  else
    echo "[INFO] 跳过依赖安装 (--skip-deps)"
  fi

  # ── 停止旧服务 ─────────────────────────────
  if tmux has-session -t worldnovel 2>/dev/null; then
    tmux kill-session -t worldnovel
    echo "[OK] 旧服务已停止"
    sleep 1
  fi

  # ── 启动新服务 ─────────────────────────────
  echo "[INFO] 启动服务 (tmux session: worldnovel)..."

  # 确保 .venv/bin 在 PATH 中
  ACTIVATE_CMD=""
  if [ -f ".venv/bin/activate" ]; then
    ACTIVATE_CMD="source .venv/bin/activate && "
  fi

  tmux new-session -d -s worldnovel \
    "\${ACTIVATE_CMD} cd ${REMOTE_DIR} && worldnovel web --host 0.0.0.0 --port ${REMOTE_PORT} 2>&1 | tee logs/server.log"

  sleep 2

  # ── 验证 ───────────────────────────────────
  if tmux has-session -t worldnovel 2>/dev/null; then
    SERVER_IP=\$(hostname -I 2>/dev/null | awk '{print \$1}' || echo "0.0.0.0")
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  🌍 WorldNovel 远程部署成功!                       ║"
    echo "║                                                  ║"
    echo "║  地址: http://\${SERVER_IP}:${REMOTE_PORT}              "
    echo "║  API:  http://\${SERVER_IP}:${REMOTE_PORT}/docs         "
    echo "║                                                  ║"
    echo "║  管理:                                           ║"
    echo "║    查看日志: tmux attach -t worldnovel             ║"
    echo "║    停止服务: tmux kill-session -t worldnovel        ║"
    echo "║    查看输出: tail -f ${REMOTE_DIR}/logs/server.log"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
  else
    echo "[ERROR] 服务启动失败，请检查日志: ${REMOTE_DIR}/logs/server.log"
    tail -20 "${REMOTE_DIR}/logs/server.log" 2>/dev/null || true
    exit 1
  fi
REMOTE_EOF

ok "远程部署完成！"
echo ""
echo -e "${GREEN}查看远程日志:${NC}  ssh ${REMOTE_HOST} 'tail -f ${REMOTE_DIR}/logs/server.log'"
echo -e "${GREEN}进入远程终端:${NC}  ssh ${REMOTE_HOST} 'tmux attach -t worldnovel'"
echo -e "${GREEN}停止远程服务:${NC}  ssh ${REMOTE_HOST} 'tmux kill-session -t worldnovel'"
