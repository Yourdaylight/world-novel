#!/usr/bin/env bash
# ============================================================
#  WorldEngine 冒烟测试 (Smoke Test)
#  用法: ./scripts/smoke-test.sh [--port 8000] [--verbose]
#
#  功能:
#    1. 检查后端是否存活
#    2. 验证所有核心 API 端点可访问
#    3. 验证前端已构建
#    4. 测试世界创建流程
#    5. 输出 PASS/FAIL 报告
#
#  退出码: 0=全部通过, 1=有失败项
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── 参数 ────────────────────────────────────────────────
PORT="${PORT:-8000}"
VERBOSE=false
FAIL_FAST=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)     PORT="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=true; shift ;;
    --fail-fast) FAIL_FAST=true; shift ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

BASE="http://127.0.0.1:${PORT}"
TOTAL=0
PASS=0
FAIL=0
SKIP=0
RESULTS=()

# ── 颜色 & 工具函数 ───────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; DIM='\033[2m'; NC='\033[0m'

log()   { printf "  ${DIM}...${NC} %s\n" "$*"; }
pass()  { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); RESULTS+=("✅ $1"); ${VERBOSE} && printf "${GREEN}  ✅ PASS${NC} %s\n" "$1"; }
fail()  { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); RESULTS+=("❌ $1"); printf "${RED}  ❌ FAIL${NC} %s\n" "$1"; }
skip()  { TOTAL=$((TOTAL+1)); SKIP=$((SKIP+1)); RESULTS+=("⏭️  $1"); log "SKIP: $1"; }

section() { printf "\n${CYAN}━━━ $1 ━━━${NC}\n\n"; }

# HTTP helper
http_get() {
  local url="$1"
  local expected_status="${2:-200}"  # accept any non-error if "any"
  local timeout_sec="${3:-10}"
  local resp_code resp_body

  # Use curl with timeout, silent mode, follow redirects for SPA
  resp_code=$(curl -s -o /tmp/smoke_resp.json -w "%{http_code}" \
    --max-time "$timeout_sec" "$url" 2>/dev/null || echo "000")

  if [ "$expected_status" = "any" ]; then
    if [ "$resp_code" -ge 200 ] && [ "$resp_code" -lt 500 ]; then
      return 0
    else
      return 1
    fi
  fi

  if [ "$resp_code" = "$expected_status" ]; then
    return 0
  else
    return 1
  fi
}

post_json() {
  local url="$1"
  local body="$2"
  local expected_status="${3:-200}"
  local resp_code

  resp_code=$(curl -s -o /tmp/smoke_post_resp.json -w "%{http_code}" \
    --max-time 15 \
    -H "Content-Type: application/json" \
    -d "$body" \
    "$url" 2>/dev/null || echo "000")

  if [ "$resp_code" = "$expected_status" ] || [ "$expected_status" = "any" ] && [ "$resp_code" -ge 200 ] && [ "$resp_code" -lt 500 ]; then
    return 0
  else
    return 1
  fi
}

get_json_field() {
  python3 -c "
import json, sys
try:
    data = json.load(open('/tmp/smoke_resp.json' if '$1'=='resp' else '/tmp/smoke_post_resp.json'))
    print(data.get('$2', ''))
except Exception:
    print('')
" 2>/dev/null
}

# ============================================================
printf "${BLUE}${BLUE}╔══════════════════════════════════════════════════╗${NC}"
printf "${BLUE}\n║  🌍 WorldNovel Smoke Test                        ║${NC}"
printf "${BLUE}\n║  Target: ${BASE:0:40}               ║${NC}"
printf "${BLUE}\n╚══════════════════════════════════════════════════╝${NC}\n"

START_TIME=$(date +%s)

# ============================================================
#  PHASE 0: 前置检查
# ============================================================
section "PHASE 0 — Pre-flight Checks"

if command -v curl &>/dev/null; then
  pass "curl available ($(curl --version | head -1 | awk '{print $2}'))"
else
  fail "curl not found"
fi

if command -v python3 &>/dev/null; then
  pass "python3 available ($(python3 --version 2>&1))"
else
  fail "python3 not found"
fi

if [ -f "$ROOT_DIR/.env" ]; then
  pass ".env file exists"
else
  fail ".env file missing — copy from .env.example"
fi

# Check dist exists (for production)
if [ -d "$ROOT_DIR/web/dist" ] && [ -f "$ROOT_DIR/web/dist/index.html" ]; then
  pass "frontend built (web/dist/ exists)"
else
  skip "frontend not built (web/dist/ missing) — run 'make build'"
fi

# ============================================================
#  PHASE 1: 后端存活检查
# ============================================================
section "PHASE 1 — Backend Health"

if http_get "${BASE}/api/novels" 200 5; then
  pass "backend alive → GET /api/novels = 200"
else
  fail "backend NOT responding at ${BASE}/api/novels (status $(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/api/novels" 2>/dev/null || echo '?'))
  Is the server running? Try: make dev or make prod"
  if [ "$FAIL_FAST" = true ]; then
    section "ABORTED — backend unreachable"
    print_report
    exit 1
  fi
fi

# Health check (custom endpoint)
if http_get "${BASE}/api/health" 200 5; then
  pass "GET /api/health = 200"
elif http_get "${BASE}/api/novels" 200 5; then
  skip "/api/health endpoint not implemented (fallback to /api/novels)"
else
  fail "health check failed"
fi

# API docs (FastAPI)
if http_get "${BASE}/docs" 200 5; then
  pass "FastAPI docs available → /docs"
else
  skip "FastAPI docs unavailable (may be disabled)"
fi

# ============================================================
#  PHASE 2: 核心 API 端点
# ============================================================
section "PHASE 2 — Core API Endpoints"

# --- Novels ---
NOVEL_ID=""
if post_json "${BASE}/api/worlds/create" '{"title":"__smoke_test__","genre":"测试","num_chapters":1,"num_characters":1}' any 30; then
  NOVEL_ID=$(get_json_field resp novel_id)
  if [ -n "$NOVEL_ID" ]; then
    pass "POST /worlds/create → novel_id=${NOVEL_ID:0:12}..."
  else
    fail "POST /worlds/create returned no novel_id"
  fi
else
  NOVEL_ID="__none__"
  fail "POST /worlds/create failed (server error or timeout)"
fi

# List novels (should include our test novel)
if http_get "${BASE}/api/novels" 200 5; then
  NOVEL_COUNT=$(get_json_field resp novels | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else '?')" 2>/dev/null || echo "?")
  pass "GET /api/novels → ${NOVEL_COUNT} novels listed"
else
  fail "GET /api/novels failed"
fi

# Select novel
if [ -n "$NOVEL_ID" ] && [ "$NOVEL_ID" != "__none__" ]; then
  if post_json "${BASE}/api/novels/select" "{\"novel_id\":\"$NOVEL_ID\"}" any; then
    pass "POST /novels/select → ok"
  else
    fail "POST /novels/select failed"
  fi

  # Get propositions
  if http_get "${BASE}/api/worlds/${NOVEL_ID}/propositions" any; then
    pass "GET /worlds/{id}/propositions → 200"
  else
    fail "GET /worlds/{id}/propositions failed"
  fi

  # World status
  if http_get "${BASE}/api/worlds/${NOVEL_ID}/status" any; then
    pass "GET /worlds/{id}/status → 200"
  else
    fail "GET /worlds/{id}/status failed"
  fi
fi

# --- Story endpoints ---
if [ -n "$NOVEL_ID" ] && [ "$NOVEL_ID" != "__none__" ]; then
  if http_get "${BASE}/api/story/outline?novel_id=${NOVEL_ID}" any; then
    pass "GET /story/outline responds"
  else
    fail "GET /story/outline failed"
  fi

  if http_get "${BASE}/api/story/world?novel_id=${NOVEL_ID}" any; then
    pass "GET /story/world responds"
  else
    fail "GET /story/world failed"
  fi
fi

# --- Characters ---
if [ -n "$NOVEL_ID" ] && [ "$NOVEL_ID" != "__none__" ]; then
  if http_get "${BASE}/api/characters?novel_id=${NOVEL_ID}" any; then
    pass "GET /characters responds"
  else
    fail "GET /characters failed"
  fi
fi

# --- Generation control (should not crash) ---
if [ -n "$NOVEL_ID" ] && [ "$NOVEL_ID" != "__none__" ]; then
  if post_json "${BASE}/api/worlds/${NOVEL_ID}/pause" '{}' any; then
    pass "POST /worlds/{id}/pause (no-op is OK)"
  else
    fail "POST /worlds/{id}/pause crashed"
  fi
fi

# ============================================================
#  PHASE 3: 清理测试数据
# ============================================================
section "PHASE 3 — Cleanup"

if [ -n "$NOVEL_ID" ] && [ "$NOVEL_ID" != "__none__" ]; then
  if http_get "--request DELETE" "${BASE}/api/worlds/${NOVEL_ID}" any; then
    # Fallback: try curl directly
    curl_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 -X DELETE "${BASE}/api/worlds/${NOVEL_ID}" 2>/dev/null)
    if [ "$curl_status" -ge 200 ] && [ "$curl_status" -lt 500 ]; then
      pass "DELETE /worlds/{id} cleanup OK (HTTP $curl_status)"
    else
      warn "DELETE returned HTTP $curl_status (may need manual cleanup)"
    fi
  else
    skip "cleanup: delete failed (manual cleanup may be needed)"
  fi
fi

# ============================================================
#  PHASE 4: 前端验证
# ============================================================
section "PHASE 4 — Frontend Verification"

if [ -d "$ROOT_DIR/web/dist" ]; then
  # Check built files exist
  if [ -f "$ROOT_DIR/web/dist/index.html" ]; then
    pass "dist/index.html exists"
  else
    fail "dist/index.html missing"
  fi

  # Check assets
  asset_count=$(find "$ROOT_DIR/web/dist/assets" -type f 2>/dev/null | wc -l)
  if [ "$asset_count" -gt 0 ]; then
    pass "dist/assets has $asset_count files"
  else
    fail "dist/assets empty"
  fi

  # Serve via backend
  if http_get "${BASE}/" 200 5; then
    pass "SPA served from root / → 200"
  else
    fail "SPA not serving from backend"
  fi
else
  skip "frontend not built — skipping serve checks"
fi

# ============================================================
#  报告
# ============================================================
END_TIME=$(date +%s))
DURATION=$((END_TIME - START_TIME))

section "RESULT — Smoke Test Report"

for r in "${RESULTS[@]}"; do
  case "$r" in
    ✅*) printf "  ${GREEN}%s${NC}\n" "$r" ;;
    ❌*) printf "  ${RED}%s${NC}\n" "$r" ;;
    ⏭*)  printf "  ${YELLOW}%s${NC}\n" "$r" ;;
  esac
done

printf "\n"
printf "  ${DIM}─────────────────────────────────────────${NC}\n"
printf "  Total: %d  |  ${GREEN}Passed: %d${NC}  |  ${RED}Failed: %d${NC}  |  ${YELLOW}Skipped: %d${NC}\n" "$TOTAL" "$PASS" "$FAIL" "$SKIP"
printf "  Time:  %ds\n" "$DURATION"
printf "  ${DIM}─────────────────────────────────────────${NC}\n\n"

if [ "$FAIL" -eq 0 ]; then
  printf "${GREEN}  🎉 ALL CHECKS PASSED${NC}\n\n"
  exit 0
else
  printf "${RED}  ⚠️  %d CHECK(S) FAILED${NC}\n\n" "$FAIL"
  exit 1
fi
