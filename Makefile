# ============================================================
#  WorldEngine (novel-creator) Makefile
#  常用命令速查
# ============================================================

.PHONY: dev prod install build deploy stop clean help

# 默认目标
help: ## 显示帮助
	@echo ""
	@echo "  🌍 WorldEngine 命令速查"
	@echo "  ════════════════════════════════════════"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── 本地启动 ────────────────────────────────────────────

dev: ## 开发模式 (前后端热重载)
	@bash scripts/start-local.sh

prod: ## 生产模式 (构建前端, 单进程)
	@bash scripts/start-local.sh --prod

# ── 安装与构建 ──────────────────────────────────────────

install: ## 安装所有依赖 (Python + Node)
	uv sync
	cd web && npm install

build: ## 构建前端
	cd web && npm run build

typecheck: ## 前端类型检查
	cd web && npx vue-tsc -b

# ── 远程部署 ────────────────────────────────────────────
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

# ── 工具 ───────────────────────────────────────────────

clean: ## 清理构建产物
	rm -rf web/dist web/node_modules/.vite
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

logs: ## 查看远程日志 (需要 HOST=user@host)
ifndef HOST
	$(error 用法: make logs HOST=user@host)
endif
	ssh $(HOST) "tail -f /opt/novel-creator/logs/server.log"
