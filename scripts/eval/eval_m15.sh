#!/usr/bin/env bash
# ============================================================
#  Milestone 15 集成评测 (需求 A/B 活服务验收)
#
#  前置: 服务已启动 (make dev 或 scripts/eval/start_eval_server.sh)
#  用法: ./scripts/eval/eval_m15.sh [--port 8123]
#  依赖: curl, python3 (解包校验用 uv run python)
# ============================================================
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8123}"
while [[ $# -gt 0 ]]; do
  case $1 in
    --port) PORT="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

BASE="http://127.0.0.1:${PORT}"
TOTAL=0; PASS=0; FAIL=0
RESULTS=()

pass() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); RESULTS+=("PASS: $1"); echo "  ✅ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); RESULTS+=("FAIL: $1"); echo "  ❌ $1"; }

jqget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval('d'+sys.argv[1]))" "$1" 2>/dev/null; }

# URL-encoded novel id (中文必须转义，否则 h11 拒绝请求行)
NOVEL_ID="星尘纪元"
NOVEL_ENC=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$NOVEL_ID")

echo "━━━ M15 评测: ${BASE} ━━━"

# ── 0. 服务存活 ─────────────────────────────────────────
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health")
if [ "$code" != "200" ]; then echo "服务未启动($code)"; exit 1; fi
pass "服务存活 /api/health"

# ── 1. 登录链路 (§7.2 注册用例) ──────────────────────────
resp=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{"invite_code":"INVALID_CODE_X"}')
code=$(echo "$resp" | tail -1)
[ "$code" = "401" ] && pass "无效邀请码 → 401" || fail "无效邀请码 → $code (期望401)"

AUTHOR_TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{"invite_code":"author_demo"}' | jqget "['access_token']")
READER_TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{"invite_code":"reader_demo"}' | jqget "['access_token']")
[ -n "$AUTHOR_TOKEN" ] && [ "$AUTHOR_TOKEN" != "None" ] && pass "作者邀请码登录" || fail "作者邀请码登录"
[ -n "$READER_TOKEN" ] && [ "$READER_TOKEN" != "None" ] && pass "读者邀请码登录" || fail "读者邀请码登录"

# ── 2. 分享创建与公开页 (§7.2) ───────────────────────────
SHARE_JSON=$(curl -s -X POST "$BASE/api/share" \
  -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"novel_id":"星尘纪元","trial_mode":"first_n_chapters","trial_value":3}')
SHARE_ID=$(echo "$SHARE_JSON" | jqget "['share_id']")
if [ -n "$SHARE_ID" ] && [ "$SHARE_ID" != "None" ]; then pass "创建分享: $SHARE_ID"; else fail "创建分享: $SHARE_JSON"; SHARE_ID=""; fi

META_CODE=$(curl -s -o /tmp/m15_meta.json -w "%{http_code}" "$BASE/api/share/$SHARE_ID")
[ "$META_CODE" = "200" ] && pass "匿名访问分享元数据" || fail "匿名访问分享元数据 → $META_CODE"

# ── 3. 权限矩阵 (§7.2 核心验收) ─────────────────────────
toc=$(curl -s "$BASE/api/share/$SHARE_ID/chapters")
trial0_readable=$(echo "$toc" | jqget "['chapters'][0]['readable']")
trial5_readable=$(echo "$toc" | jqget "['chapters'][5]['readable']")
[ "$trial0_readable" = "True" ] && pass "匿名目录: 试读内可读" || fail "匿名目录试读内标记=$trial0_readable"
[ "$trial5_readable" = "False" ] && pass "匿名目录: 试读外锁定" || fail "匿名目录试读外标记=$trial5_readable"

c2=$(curl -s -o /tmp/m15_c2.json -w "%{http_code}" "$BASE/api/share/$SHARE_ID/chapter/2")
[ "$c2" = "200" ] && pass "匿名读第3章(试读边界内)" || fail "匿名读第3章 → $c2"

resp=$(curl -s -w "\n%{http_code}" "$BASE/api/share/$SHARE_ID/chapter/5")
code=$(echo "$resp" | tail -1)
body=$(echo "$resp" | head -n -1)
if [ "$code" = "403" ]; then
  pass "匿名读试读外 → 403"
  echo "$body" | grep -q "need_login" && pass "403含 need_login 约定" || fail "403缺 need_login"
  echo "$body" | grep -q "星舰穿过陨石带" && fail "403响应泄露正文!" || pass "403响应不含正文"
else
  fail "匿名读试读外 → $code (期望403)"
fi

r5=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/share/$SHARE_ID/chapter/5" -H "X-User-Token: $READER_TOKEN")
[ "$r5" = "200" ] && pass "注册用户读全文 → 200" || fail "注册用户读全文 → $r5"

# 管理接口权限
m1=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/share/$SHARE_ID" -H 'Content-Type: application/json' -d '{"trial_value":1}')
m2=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/share/$SHARE_ID" -H "X-User-Token: $READER_TOKEN" -H 'Content-Type: application/json' -d '{"trial_value":1}')
m3=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/share/$SHARE_ID" -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' -d '{"trial_value":3}')
[ "$m1" = "401" ] && pass "管理接口: 匿名401" || fail "管理接口匿名 → $m1"
[ "$m2" = "403" ] && pass "管理接口: 非所有者403" || fail "管理接口非所有者 → $m2"
[ "$m3" = "200" ] && pass "管理接口: 所有者200" || fail "管理接口所有者 → $m3"

# ── 4. 试读边界与即时生效 (§7.2 边界用例) ────────────────
curl -s -o /dev/null -X PATCH "$BASE/api/share/$SHARE_ID" -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' -d '{"trial_value":1}'
b1=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/share/$SHARE_ID/chapter/0")
b2=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/share/$SHARE_ID/chapter/1")
[ "$b1" = "200" ] && [ "$b2" = "403" ] && pass "试读改为1章即时生效" || fail "试读即时生效(0章=$b1,1章=$b2)"
curl -s -o /dev/null -X PATCH "$BASE/api/share/$SHARE_ID" -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' -d '{"trial_value":3}'

# ── 5. 关闭分享 → 全 404 ────────────────────────────────
curl -s -o /dev/null -X DELETE "$BASE/api/share/$SHARE_ID" -H "X-User-Token: $AUTHOR_TOKEN"
d1=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/share/$SHARE_ID")
d2=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/share/$SHARE_ID/chapter/0" -H "X-User-Token: $READER_TOKEN")
[ "$d1" = "404" ] && [ "$d2" = "404" ] && pass "关闭分享后全部404" || fail "关闭后(元数据=$d1,正文=$d2)"
curl -s -o /dev/null -X PATCH "$BASE/api/share/$SHARE_ID" -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' -d '{"status":"active"}'

# ── 6. 限流 (§7.2 安全用例: 60 req/min → 429) ───────────
# 并发突发，确保单窗口内超过 60 次
seq 1 90 | xargs -P 20 -I{} curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/share/$SHARE_ID" > /tmp/m15_rates.txt
if grep -q 429 /tmp/m15_rates.txt; then
  pass "分享页限流429生效 ($(grep -c 429 /tmp/m15_rates.txt)/90 被限)"
else
  fail "90次并发请求未触发429"
fi
sleep 62   # 等待限流窗口复位

# ── 7. 分享ID枚举 (§7.2: 无越权数据返回) ─────────────────
leak=0
for i in $(seq 1 100); do
  rid=$(head -c5 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-10)
  c=$(curl -s -o /tmp/m15_enum.json -w "%{http_code}" "$BASE/api/share/$rid")
  if [ "$c" = "200" ]; then leak=1; break; fi
done
[ "$leak" = "0" ] && pass "100次随机ID枚举无泄露" || fail "枚举出现200泄露!"

# ── 8. 书架/进度 (§7.2) ─────────────────────────────────
curl -s -o /dev/null -X PUT "$BASE/api/bookshelf/$NOVEL_ENC" -H "X-User-Token: $READER_TOKEN" -H 'Content-Type: application/json' -d "{\"in_bookshelf\":true,\"share_id\":\"$SHARE_ID\"}"
shelf=$(curl -s "$BASE/api/bookshelf" -H "X-User-Token: $READER_TOKEN")
echo "$shelf" | grep -q "星尘纪元" && pass "书架加入/列出" || fail "书架: $shelf"

# ── 9. 需求A: 质量门禁 + 导出 E2E (§7.1) ────────────────
pre=$(curl -s -X POST "$BASE/api/publish/preflight" -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元","platform":"fanqie"}')
echo "$pre" | grep -q '"ok":true' && pass "preflight 通过" || fail "preflight: $(echo "$pre" | head -c 200)"

curl -s -o /tmp/m15_fanqie.zip -D /tmp/m15_fanqie.headers -X POST "$BASE/api/publish/export" \
  -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"novel_id":"星尘纪元","platform":"fanqie"}'
if [ -s /tmp/m15_fanqie.zip ] && unzip -l /tmp/m15_fanqie.zip >/dev/null 2>&1; then
  pass "番茄导出ZIP可解包"
  grep -qi "x-publication-record-id" /tmp/m15_fanqie.headers && pass "导出返回发布记录ID" || fail "缺发布记录ID头"
  uv run python - <<'PYEOF' && pass "番茄TXT为GB18030且章节完整" || fail "番茄导出内容校验失败"
import io, zipfile
zf = zipfile.ZipFile('/tmp/m15_fanqie.zip')
txt = next(n for n in zf.namelist() if n.endswith('.txt') and '全文' in n)
text = zf.read(txt).decode('gb18030')
assert '第1章' in text and '第12章' in text, 'chapters missing'
assert any('synopsis' in n for n in zf.namelist()), 'synopsis missing'
PYEOF
else
  fail "番茄导出失败"
fi

curl -s -o /tmp/m15_qimao.zip -X POST "$BASE/api/publish/export" \
  -H "X-User-Token: $AUTHOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"novel_id":"星尘纪元","platform":"qimao"}'
uv run python - <<'PYEOF' && pass "七猫按卷拆分(2卷)" || fail "七猫分卷校验失败"
import zipfile
zf = zipfile.ZipFile('/tmp/m15_qimao.zip')
vols = [n for n in zf.namelist() if '卷' in n and n.endswith('.txt')]
assert len(vols) == 2, f'expected 2 volumes, got {len(vols)}'
PYEOF

recs=$(curl -s "$BASE/api/publish/records?novel_id=$NOVEL_ENC" -H "X-User-Token: $AUTHOR_TOKEN")
echo "$recs" | grep -q '"stage":"exported"' && pass "发布记录已写入" || fail "发布记录: $(echo "$recs" | head -c 200)"

# ── 汇总 ────────────────────────────────────────────────
echo ""
echo "━━━ 评测结果: $PASS/$TOTAL 通过, $FAIL 失败 ━━━"
[ "$FAIL" = "0" ] && exit 0 || exit 1
