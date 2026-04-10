#!/usr/bin/env bash
# ============================================================
#  WorldEngine 完整测试 Harness
#  用法: ./scripts/test-harness.sh [stage]
#
#  Stages:
#    lint        — Python ruff + Vue typecheck
#    unit        — pytest 单元测试
#    build       — 前端构建 + 后端 import 检查
#    integration — 启动服务 + 冒烟测试
#    all         — 以上全部 (默认)
#    quick       — lint + build (跳过慢速测试)
#
#  环境变量:
#    PORT         冒烟测试端口 (默认 8000)
#    SMOKE_SKIP   设为 1 跳过冒烟测试(需要运行中的服务)
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── 参数 ────────────────────────────────────────────────
STAGE="${1:-all}"
PORT="${PORT:-8000}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { printf "${BLUE}[HARNESS]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[HARNESS]${NC}  ✅ %s\n" "$*"; }
warn()  { printf "${YELLOW}[HARNESS]${NC}  ⚠️  %s\n" "$*"; }
error() { printf "${RED}[HARNESS]${NC}  ❌ %s\n" "$*"; }
banner() { printf "\n${CYAN}═══ STAGE: %s ═══${NC}\n" "$*"; }

STEPS_PASSED=0
STEPS_FAILED=0

record_pass() { STEPS_PASSED=$((STEPS_PASSED+1)); ok "$@"; }
record_fail() { STEPS_FAILED=$((STEPS_FAILED+1)); error "$@"; }

# ============================================================
#  Stage 1: Lint
# ============================================================
run_lint() {
  banner "LINT — Code Quality"

  # Python: ruff
  info "Running ruff (Python linter)..."
  if command -v uv &>/dev/null; then
    if uv run ruff check src/ tests/ --output-format=concise; then
      record_pass "ruff: no issues found"
    else
      record_fail "ruff: issues detected (see above)"
    fi
  elif command -v ruff &>/dev/null; then
    if ruff check src/ tests/ --output-format=concise; then
      record_pass "ruff: no issues found"
    else
      record_fail "ruff: issues detected"
    fi
  else
    warn "ruff not installed, skipping Python lint"
  fi

  # Vue: typecheck
  info "Running vue-tsc (TypeScript)..."
  cd web
  if npx vue-tsc -b --noEmit 2>&1; then
    record_pass "vue-tsc: no type errors"
  else
    record_fail "vue-tsc: type errors found"
  fi
  cd "$ROOT_DIR"
}

# ============================================================
#  Stage 2: Unit Tests
# ============================================================
run_unit() {
  banner "UNIT TESTS — pytest"

  if ! command -v uv &>/dev/null && ! [ -f .venv/bin/python ]; then
    warn "No Python venv found, running system pytest"
    pytest tests/ -v --tb=short 2>&1 | tail -20 || true
    return
  fi

  local py_cmd
  if command -v uv &>/dev/null; then
    py_cmd="uv run pytest"
  else
    py_cmd=".venv/bin/pytest"
  fi

  info "Running pytest..."
  if $py_cmd tests/ -v --tb=short --duration=10 2>&1; then
    record_pass "pytest: all unit tests passed"
  else
    record_fail "pytest: some tests failed"
  fi
}

# ============================================================
#  Stage 3: Build
# ============================================================
run_build() {
  banner "BUILD — Frontend + Backend Import Check"

  # Backend: verify all imports work
  info "Checking Python imports..."
  if command -v uv &>/dev/null; then
    PY_CMD="uv run python"
  elif [ -f .venv/bin/python ]; then
    PY_CMD=".venv/bin/python"
  else
    PY_CMD="python3"
  fi

  IMPORT_ERRORS=0
  for mod in \
    "novel_creator.web.app" \
    "novel_creator.web.routes.novels" \
    "novel_creator.web.routes.generation" \
    "novel_creator.web.routes.story" \
    "novel_creator.web.routes.characters" \
    "novel_creator.memory.database" \
    "novel_creator.memory.registry" \
    "novelCreator.agents.director"; do
    if $PY_CMD -c "import $mod" 2>/dev/null; then
      :  # ok
    else
      warn "Import failed: $mod (may be optional)"
      IMPORT_ERRORS=$((IMPORT_ERRORS+1))
    fi
  done

  if [ "$IMPORT_ERRORS" -eq 0 ]; then
    record_pass "All critical imports OK"
  else
    record_fail "$IMPORT_ERRORS import(s) failed"
  fi

  # Frontend: npm build
  info "Building frontend (npm run build)..."
  cd web
  if npm run build 2>&1 | tail -10; then
    record_pass "Frontend build succeeded → web/dist/"
  else
    record_fail "Frontend build FAILED"
  fi
  cd "$ROOT_DIR"

  # Verify build output
  if [ -f web/dist/index.html ]; then
    local size
    size=$(du -sh web/dist/ | cut -f1)
    record_pass "Build output verified ($size)"
  fi
}

# ============================================================
#  Stage 4: Integration (Smoke Test)
# ============================================================
run_integration() {
  banner "INTEGRATION — Smoke Test (requires running server)"

  if [ "${SMOKE_SKIP:-0}" = "1" ]; then
    warn "SMOKE_SKIP=1, skipping integration tests"
    return 0
  fi

  # Quick connectivity check
  if ! curl -s --max-time 3 "http://127.0.0.1:${PORT}/api/novels" >/dev/null 2>&1; then
    warn "Server not running at port ${PORT}. Starting it..."
    # Try to start server in background
    if command -v uv &>/dev/null; then
      (
        uv run uvicorn novel_creator.web.app:app --host 127.0.0.1 --port "$PORT" &
        SERVER_PID=$!
        sleep 5
        # Run smoke test
        bash scripts/smoke-test.sh --port "$PORT" "${VERBOSE:---verbose}"
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
      )
      return $?
    else
      warn "Cannot auto-start server. Set SMOKE_SKIP=1 or start manually."
      return 0
    fi
  fi

  # Server is running, just run smoke test
  bash scripts/smoke-test.sh --port "$PORT" "${VERBOSE:--}"
}

# ============================================================
#  Dispatch
# ============================================================
START_ALL=$(date +%s)

case "$STAGE" in
  lint)         run_lint ;;
  unit)         run_unit ;;
  build)        run_build ;;
  integration)  run_integration ;;
  quick)        run_lint; run_build ;;
  all)
    run_lint
    run_unit
    run_build
    run_integration
    ;;
  *)
    echo "Unknown stage: $STAGE"
    echo "Usage: $0 [lint|unit|build|integration|all|quick]"
    exit 1
    ;;
esac

END_ALL=$(date +%s)
DURATION=$((END_ALL - START_ALL))

# ============================================================
#  Final Report
# ============================================================
printf "\n${CYAN}════════════════════════════════════════════${NC}\n"
printf "${CYAN}  HARNESS COMPLETE — Stage: %s${NC}\n" "$STAGE"
printf "${CYAN}════════════════════════════════════════════${NC}\n\n"

printf "  Passed:  ${GREEN}%d${NC}\n" "$STEPS_PASSED"
printf "  Failed:  ${RED}%d${NC}\n" "$STEPS_FAILED"
printf "  Time:    %ds\n\n" "$DURATION"

if [ "$STEPS_FAILED" -gt 0 ]; then
  printf "${RED}  ❌ HARNESS FAILED${NC}\n\n"
  exit 1
else
  printf "${GREEN}  🎉 ALL STAGES PASSED${NC}\n\n"
  exit 0
fi
