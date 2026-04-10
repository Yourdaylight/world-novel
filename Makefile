# ============================================================
#  WorldNovel — AI Novel Generation System
#  常用命令速查 + 工程化 harness
# ============================================================

.PHONY: dev prod install build deploy stop clean help \
        lint test unit smoke harness \
        docker-up docker-down docker-logs docker-smoke \
        check ci quick-check

# ── 默认目标 ──────────────────────────────────────

help: ## 显示帮助
	@echo ""
	@echo "  🌍 WorldNovel 命令速查"
	@echo "  ════════════════════════════════════════"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  ─── 快速工作流 ──"
	@echo "  make dev              # 启动开发环境"
	@echo "  make quick-check      # lint + 构建 (提交前必跑)"
	@echo "  make smoke            # 冒烟测试 (服务需运行中)"
	@echo "  make ci               # 完整 CI (lint+test+build+smoke)"
	@echo ""

# ── 开发 & 启动 ────────────────────────────────────

dev: ## 开发模式 (前后端热重载)
	@bash scripts/start-local.sh

prod: ## 生产模式 (构建前端, 单进程)
	@bash scripts/start-local.sh --prod

# ── 代码质量 ──────────────────────────────────────

lint: ## 代码检查 (ruff + vue-tsc)
	@bash scripts/test-harness.sh lint

typecheck: ## TypeScript 类型检查 (别名)
	@cd web && npx vue-tsc -b --noEmit

# ── 测试 ──────────────────────────────────────────

test: ## 运行单元测试
	@bash scripts/test-harness.sh unit

unit: ## 运行单元测试 (别名)
	@bash scripts/test-harness.sh unit

e2e: ## 端到端测试 (无需运行服务, 测试完整创世+API流程)
	@uv run pytest tests/test_e2e.py -v --tb=short

smoke: ## 冒烟测试 (需要运行中的服务)
	@bash scripts/smoke-test.sh ${PORT:+--port $(PORT)}

harness: ## 运行完整测试 harness
	@bash scripts/test-harness.sh all

quick-check: ## 快速检查: lint + build (提交前)
	@bash scripts/test-harness.sh quick

ci: ## 完整 CI 流水线: lint → test → build → smoke
	@echo ""
	@echo "╔══════════════════════════════════════════╗"
	@echo "║  🚀 Running Full CI Pipeline              ║"
	@echo "╚══════════════════════════════════════════╝"
	@bash scripts/test-harness.sh all

check: ## 同 ci
	@$(MAKE) ci

# ── 构建与部署 ────────────────────────────────────

install: ## 安装所有依赖 (Python + Node)
	uv sync
	cd web && npm install

build: ## 构建前端
	cd web && npm run build

build-full: ## 完整构建 (依赖 + 前端 + 后端验证)
	@$(MAKE) install
	@$(MAKE) build
	@echo ""
	@echo "✅ Build complete — run 'make smoke' to verify"

# ── Docker 部署 ───────────────────────────────────

docker-init: ## 生成 Docker 部署文件
	@bash scripts/deploy-docker.sh init

docker-up: ## Docker 启动部署 [PORT=9000]
	@bash scripts/deploy-docker.sh up

docker-build: ## 仅构建 Docker 镜像
	@bash scripts/deploy-docker.sh build-image

docker-down: ## Docker 停止清理
	@bash scripts/deploy-docker.sh down

docker-restart: ## Docker 重启
	@bash scripts/deploy-docker.sh restart

docker-status: ## Docker 状态
	@bash scripts/deploy-docker.sh status

docker-logs: ## Docker 日志
	@bash scripts/deploy-docker.sh logs

docker-smoke: ## Docker 冒烟测试
	@bash scripts/deploy-docker.sh smoke

# ── 远程部署 ──────────────────────────────────────
# 用法: make deploy HOST=user@host [PORT=8000] [ENV=.env.production]

deploy: ## 部署到远程 (需要 HOST=user@host)
ifndef HOST
	$(error 用法: make deploy HOST=user@host [PORT=8000] [ENV=.env.prod])
endif
	@bash scripts/deploy-remote.sh $(HOST) \
		$(if $(PORT),--port $(PORT)) \
		$(if $(ENV),--env $(ENV)) \
		$(if $(DIR),--dir $(DIR))

deploy-code: ## 仅同步代码并重启 (跳过依赖安装)
ifndef HOST
	$(error 用法: make deploy-code HOST=user@host)
endif
	@bash scripts/deploy-remote.sh $(HOST) --skip-deps \
		$(if $(PORT),--port $(PORT))

restart: ## 远程重启 (不同步代码)
ifndef HOST
	$(error 用法: make restart HOST=user@host)
endif
	@bash scripts/deploy-remote.sh $(HOST) --restart \
		$(if $(PORT),--port $(PORT))

# ── 工具 ──────────────────────────────────────────

clean: ## 清理构建产物
	rm -rf web/dist web/node_modules/.vite
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

logs: ## 查看远程日志 (需要 HOST=user@host)
ifndef HOST
	$(error 用法: make logs HOST=user@host)
endif
	ssh $(HOST) "tail -f /opt/novel-creator/logs/server.log"

# ── Git hooks ──────────────────────────────────────
# 提交前自动跑 quick-check

install-hooks: ## 安装 pre-commit hook
	@test -d .git && (\
	  echo '#!/bin/bash\nexec make quick-check' > .git/hooks/pre-commit && \
	  chmod +x .git/hooks/pre-commit && \
	  echo "✅ pre-commit hook installed" \
	) || echo "⚠️  Not a git repo, skipping"

remove-hooks: ## 移除 pre-commit hook
	@rm -f .git/hooks/pre-commit && echo "🗑️  pre-commit hook removed"
