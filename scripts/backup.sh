#!/usr/bin/env bash
# ============================================
# world-novel 数据库备份脚本
#
# 用法:
#   ./scripts/backup.sh              # 手动备份
#   ./scripts/backup.sh --cron       # 定时任务模式（静默）
#
# 定时任务配置:
#   crontab -e
#   0 3 * * * /opt/world-novel/scripts/backup.sh --cron
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="${PROJECT_DIR}/data"
BACKUP_DIR="${PROJECT_DIR}/backups"
KEEP_DAYS=30
CRON_MODE=false

# 参数解析
if [[ "${1:-}" == "--cron" ]]; then
    CRON_MODE=true
fi

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { $CRON_MODE || echo -e "${BLUE}[BACKUP]${NC} $*"; }
ok()   { $CRON_MODE || echo -e "${GREEN}[OK]${NC}   $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# 检查数据目录
if [ ! -d "$DATA_DIR" ]; then
    warn "Data directory not found: $DATA_DIR"
    exit 1
fi

# 创建备份目录
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="worldnovel_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

info "Creating backup: ${BACKUP_NAME}..."

# 创建临时目录
mkdir -p "$BACKUP_PATH"

# 备份SQLite数据库（使用VACUUM INTO创建一致性快照）
for db in "$DATA_DIR"/*.db; do
    if [ -f "$db" ]; then
        db_name=$(basename "$db")
        info "  Backing up ${db_name}..."
        sqlite3 "$db" "VACUUM INTO '${BACKUP_PATH}/${db_name}'"
    fi
done

# 备份 .env（脱敏处理）
if [ -f "${PROJECT_DIR}/.env" ]; then
    cp "${PROJECT_DIR}/.env" "${BACKUP_PATH}/.env"
    # 脱敏API Key
    sed -i 's/=sk-.*/=***REDACTED***/g' "${BACKUP_PATH}/.env"
    sed -i 's/=ghp-.*/=***REDACTED***/g' "${BACKUP_PATH}/.env"
fi

# 打包
tar czf "${BACKUP_PATH}.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_PATH"

BACKUP_SIZE=$(du -h "${BACKUP_PATH}.tar.gz" | cut -f1)
ok "Backup created: ${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})"

# 清理旧备份
DELETED=$(find "$BACKUP_DIR" -name "worldnovel_backup_*.tar.gz" -mtime +${KEEP_DAYS} | wc -l)
if [ "$DELETED" -gt 0 ]; then
    find "$BACKUP_DIR" -name "worldnovel_backup_*.tar.gz" -mtime +${KEEP_DAYS} -delete
    info "Cleaned ${DELETED} old backup(s) (> ${KEEP_DAYS} days)"
fi

# 显示备份列表
TOTAL=$(find "$BACKUP_DIR" -name "worldnovel_backup_*.tar.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
ok "Total backups: ${TOTAL} (${TOTAL_SIZE})"

if ! $CRON_MODE; then
    echo ""
    echo "Latest backups:"
    ls -lt "$BACKUP_DIR"/worldnovel_backup_*.tar.gz 2>/dev/null | head -5 | awk '{print "  " $9 " (" $5 ")"}'
fi
