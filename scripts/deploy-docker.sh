#!/usr/bin/env bash
# ============================================================
#  WorldEngine Docker 一键部署
#
#  用法:
#    ./scripts/deploy-docker.sh                    # 默认端口 8000
#    ./scripts/deploy-docker.sh --port 9000        # 自定义端口
#    ./scripts/deploy-docker.sh --build            # 强制重建镜像
#    ./scripts/deploy-docker.sh down               # 停止并清理
#    ./scripts/deploy-docker.sh logs               # 查看日志
#    ./scripts/deploy-docker.sh status             # 容器状态
#
#  功能:
#    - 多阶段构建 (Python + Node 前端)
#    - 生产级配置 (非 root 运行、健康检查)
#    - 数据持久化 volume
#    - 一键启停、日志查看
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="docker-compose.yml"
IMAGE_NAME="worldnovel"
CONTAINER_NAME="worldnovel"
PORT="${PORT:-8000}"

# ── 颜色 ────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { printf "${BLUE}[DEPLOY]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*"; exit 1; }

# ── Dockerfile (多阶段构建) ────────────────────────────
generate_dockerfile() {
  cat > Dockerfile << 'DOCKERFILE'
# ============================================================
#  WorldEngine Multi-Stage Docker Build
#  Stage 1: Node — Build frontend
#  Stage 2: Python — Runtime
# ============================================================

# ── Stage 1: Frontend Build ─────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --silent
COPY web/ .
RUN npm run build

# ── Stage 2: Python Runtime ─────────────────────────────
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy Python project
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source (exclude unnecessary files)
COPY src/ ./src/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Non-root user
RUN useradd -m -r appuser && \
    chown -R appuser:appdir /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/novels')"]

CMD ["uv", "run", "novel-creator", "web", "--host", "0.0.0.0", "--port", "8000"]
DOCKERFILE

  ok "Dockerfile generated (multi-stage build)"
}

# ── docker-compose (完整版) ─────────────────────────────
generate_compose() {
  cat > docker-compose.deploy.yml << COMPOSE
# WorldEngine Production Deployment
# Usage: docker compose -f docker-compose.deploy.yml up -d

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: \${IMAGE_NAME:-worldengine-app}:latest
    container_name: \${CONTAINER_NAME:-worldengine}
    restart: unless-stopped
    ports:
      - "\${PORT:-8000}:8000"
    env_file:
      - .env
    volumes:
      - app_data:/app/data
      - app_logs:/app/logs
    environment:
      - NOVEL_WEB_HOST=0.0.0.0
      - NOVEL_WEB_PORT=8000
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/novels')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  # Optional vector DB (enable via .env: NOVEL_QDRANT_ENABLED=true)
  qdrant:
    image: qdrant/qdrant:v1.8.4
    container_name: worldengine-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    profiles:
      - vector-db

  # Optional graph DB (enable via .env: NOVEL_NEO4J_ENABLED=true)
  neo4j:
    image: neo4j:5.18-community
    container_name: worldengine-neo4j
    restart: unless-stopped
    environment:
      - NEO4J_AUTH=neo4j/worldengine
      - NEO4J_PLUGINS=["apoc"]
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    profiles:
      - graph-db

volumes:
  app_data:
  app_logs:
  qdrant_data:
  neo4j_data:
COMPOSE

  ok "docker-compose.deploy.yml generated"
}

# ============================================================
#  命令路由
# ============================================================
CMD="${1:-help}"
shift 2>/dev/null || true

case "$CMD" in
  up|start|deploy)
    # Ensure files exist
    [ -f Dockerfile ] || generate_dockerfile
    [ -f docker-compose.deploy.yml ] || generate_compose

    if [ "${1:-}" = "--build" ]; then
      info "Rebuilding image..."
      docker compose -f docker-compose.deploy.yml build --no-cache app
      shift
    fi

    info "Deploying WorldEngine (port ${PORT})..."
    PORT="$PORT" docker compose -f docker-compose.deploy.yml up -d "${@:---build}"

    sleep 3
    printf "\n"
    printf "${GREEN}╔══════════════════════════════════════════════════╗${NC}\n"
    printf "${GREEN}║  🌍 WorldNovel Docker 部署成功!                    ║${NC}\n"
    printf "${GREEN}║                                                  ║${NC}\n"
    printf "${GREEN}║  地址: http://localhost:%-27s   ║\n" "${PORT}"
    printf "${GREEN}║  API:  http://localhost:%-28s ║\n" "${PORT}/docs"
    printf "${GREEN}║                                                  ║\n"
    printf "${GREEN}║  管理:                                           ║\n"
    printf "${GREEN}║    日志: $0 logs                              ║\n"
    printf "${GREEN}║    状态: $0 status                            ║\n"
    printf "${GREEN}║    停止: $0 down                              ║\n"
    printf "${GREEN}╚══════════════════════════════════════════════════╝${NC}\n"
    ;;

  down|stop)
    info "Stopping WorldEngine..."
    docker compose -f docker-compose.deploy.yml down "${@:--volumes}"
    ok "WorldEngine stopped"
    ;;

  restart)
    $0 down
    sleep 2
    $0 start "$@"
    ;;

  logs)
    docker compose -f docker-compose.deploy.yml logs -f --tail=100 "${@:-app}"
    ;;

  status)
    printf "\n${CYAN}=== WorldNovel Container Status ===${NC}\n\n"
    docker compose -f docker-compose.deploy.yml ps
    printf "\n"
    if docker ps --format '{{.Names}}' | grep -q worldnovel; then
      printf "${GREEN}● Running: http://localhost:%s${NC}\n\n" "$PORT"
    else
      printf "${RED}○ Not running${NC}\n\n"
    fi
    ;;

  smoke)
    info "Running smoke test against Docker deployment..."
    exec "$ROOT_DIR/scripts/smoke-test.sh" --port "$PORT" --verbose
    ;;

  build-image)
    generate_dockerfile
    info "Building Docker image..."
    docker build -t "${IMAGE_NAME}:latest" --target runtime .
    ok "Image built: ${IMAGE_NAME}:latest ($(docker images -q ${IMAGE_NAME}:latest | xargs docker inspect --format='{{.Size}}' | awk '{printf "%.0f MB", $/1024/1024}'))"
    ;;

  init)
    info "Generating deployment files..."
    generate_dockerfile
    generate_compose
    ok "Ready! Run: $0 start"
    ;;

  help|*)
    cat <<HELP
WorldEngine Docker 一键部署工具

用法: $0 <命令> [选项]

命令:
  up/start/deploy [opts]  启动部署 (默认端口 8000)
    --build                强制重建镜像
  down/stop [opts]         停止并清理
    --volumes              同时删除 volumes
  restart                 重启
  logs [service]          查看日志
  status                  容器状态
  smoke                   运行冒烟测试
  build-image             仅构建镜像
  init                   生成 Dockerfile + compose
  help                   显示此帮助

环境变量:
  PORT=8000              服务端口

示例:
  $0 start                        # 默认部署
  $0 start --build --port 9000    # 重建 + 自定义端口
  $0 smoke                        # 冒烟测试
  $0 down --volumes               # 完全清理
HELP
    ;;
esac
