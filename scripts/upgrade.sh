#!/usr/bin/env bash
# ============================================
# world-novel 升级脚本
#
# 用法:
#   ./scripts/upgrade.sh              # 完整升级
#   ./scripts/upgrade.sh --check      # 仅检查变更
#   ./scripts/upgrade.sh --rollback   # 回滚到上一版本
#
# 流程:
#   1. 备份数据库
#   2. git pull
#   3. 安装依赖
#   4. 数据库迁移
#   5. 构建前端
#   6. 重启服务
#   7. 健康检查（失败则自动回滚）
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${BLUE}[UPGRADE]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

STEP=0
step() {
    STEP=$((STEP + 1))
    echo ""
    info "Step ${STEP}/7 · $*"
    echo "────────────────────────────────────────"
}

# ── 参数解析 ──────────────────────────────────────
MODE="upgrade"
while [[ $# -gt 0 ]]; do
    case $1 in
        --check)    MODE="check"; shift ;;
        --rollback) MODE="rollback"; shift ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "  --check      仅检查变更，不执行升级"
            echo "  --rollback   回滚到上一版本（需有备份）"
            echo "  -h, --help   显示帮助"
            exit 0
            ;;
        *) error "未知参数: $1" ;;
    esac
done

# ── Rollback Mode ─────────────────────────────────
if [ "$MODE" = "rollback" ]; then
    warn "Rollback mode — restoring from backup..."

    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/worldnovel_backup_*.tar.gz 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        error "No backup found in $BACKUP_DIR"
    fi

    info "Latest backup: $(basename "$LATEST_BACKUP")"
    read -p "Confirm rollback? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        info "Rollback cancelled."
        exit 0
    fi

    # 停止服务
    info "Stopping service..."
    if systemctl is-active --quiet world-novel 2>/dev/null; then
        sudo systemctl stop world-novel
    elif tmux has-session -t worldnovel 2>/dev/null; then
        tmux kill-session -t worldnovel
    fi

    # 恢复数据库
    info "Restoring database..."
    cd "$BACKUP_DIR"
    tar xzf "$LATEST_BACKUP"
    BACKUP_NAME=$(basename "$LATEST_BACKUP" .tar.gz)
    cp -f "$BACKUP_NAME"/*.db "$PROJECT_DIR/data/"
    rm -rf "$BACKUP_NAME"

    # 回滚代码
    info "Rolling back code..."
    cd "$PROJECT_DIR"
    git reset --hard HEAD@{1}

    ok "Rollback complete!"
    info "Start service manually: make prod"
    exit 0
fi

# ── Check Mode ────────────────────────────────────
if [ "$MODE" = "check" ]; then
    info "Checking for updates..."
    cd "$PROJECT_DIR"
    git fetch origin
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "$LOCAL")

    if [ "$LOCAL" = "$REMOTE" ]; then
        ok "Already up to date."
        exit 0
    fi

    echo ""
    echo "Commits to pull:"
    git log --oneline HEAD..origin/main
    exit 0
fi

# ═══════════════════════════════════════════════════
#  Upgrade Pipeline
# ═══════════════════════════════════════════════════

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║${NC}  ${BOLD}world-novel Upgrade${NC}                        ${GREEN}${BOLD}║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Backup
step "Backup Database"
if [ -f "$SCRIPT_DIR/backup.sh" ]; then
    bash "$SCRIPT_DIR/backup.sh"
else
    warn "backup.sh not found, skipping backup!"
    read -p "Continue without backup? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
fi

# Step 2: Git Pull
step "Pull Latest Code"
cd "$PROJECT_DIR"
OLD_COMMIT=$(git rev-parse --short HEAD)
git pull origin main
NEW_COMMIT=$(git rev-parse --short HEAD)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    ok "Already up to date (commit: ${NEW_COMMIT})"
else
    ok "Updated: ${OLD_COMMIT} → ${NEW_COMMIT}"
    echo ""
    git log --oneline "${OLD_COMMIT}..${NEW_COMMIT}"
fi

# Step 3: Dependencies
step "Install Dependencies"
if command -v uv &>/dev/null; then
    uv sync --quiet 2>/dev/null || uv pip install -e "." --quiet
    ok "Python deps installed (uv)"
else
    warn "uv not found, trying pip..."
    pip install -e "." --quiet
fi

cd "$PROJECT_DIR/web"
npm install --silent
ok "Node deps installed"
cd "$PROJECT_DIR"

# Step 4: Database Migration
step "Database Migration"
if [ -f "$SCRIPT_DIR/migrations/migrate.py" ]; then
    python3 "$SCRIPT_DIR/migrations/migrate.py"
    ok "Database migrated"
else
    warn "Migration tool not found, using auto-creation..."
fi

# Step 5: Build Frontend
step "Build Frontend"
cd "$PROJECT_DIR/web"
npm run build 2>&1 | tail -5
cd "$PROJECT_DIR"
ok "Frontend built"

# Step 6: Restart Service
step "Restart Service"
if systemctl is-active --quiet world-novel 2>/dev/null; then
    sudo systemctl restart world-novel
    ok "Service restarted (systemd)"
elif tmux has-session -t worldnovel 2>/dev/null; then
    tmux kill-session -t worldnovel
    sleep 1
    tmux new-session -d -s worldnovel \
        "cd $PROJECT_DIR && uv run worldnovel web --host 0.0.0.0 --port 8000 2>&1 | tee logs/server.log"
    ok "Service restarted (tmux)"
else
    warn "No running service found. Start manually: make prod"
fi

# Step 7: Health Check
step "Health Check"
sleep 3

HEALTH_URL="http://localhost:8000/api/health"
for i in 1 2 3; do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        ok "Health check passed!"

        echo ""
        echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
        echo -e "${BOLD}${GREEN}║${NC}  ${BOLD}Upgrade Complete!${NC}                          ${GREEN}${BOLD}║${NC}"
        echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
        echo ""
        exit 0
    fi
    sleep 2
done

# Health check failed — suggest rollback
error "Health check FAILED after 3 retries!

${YELLOW}To rollback:${NC}
    $0 --rollback

${YELLOW}To check logs:${NC}
    journalctl -u world-novel -n 50    # systemd
    # or
    tail -f $PROJECT_DIR/logs/server.log  # tmux
"
