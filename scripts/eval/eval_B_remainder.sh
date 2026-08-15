#!/usr/bin/env bash
# §7.2 补跑：TOC 标记 / 注册用例 / 单元测试（修正脚本 bug 后的剩余项）
set -uo pipefail
cd /mnt/tos/workspace/world-novel
B=http://127.0.0.1:8127
PASS=*** FAIL=0
pass() { PASS=*** echo "  ✅ $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ $1"; }
jqget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval('d'+sys.argv[1]))" "$1" 2>/dev/null; }
login() { curl -s -X POST $B/api/auth/login -H 'Content-Type: application/json' -d "{\"invite_code\":\"$1\"}" | jqget "['access_token']"; }

AUTHOR=login__author_demo__
READER=login__reader_demo__
ADMIN=login__admin_demo__

# 既有分享
SID=$(curl -s $B/api/shares -H "X-User-Token: $AUTHOR" | jqget "['shares'][0]['share_id']")
[ -n "$SID" ] && [ "$SID" != "None" ] || { echo "无分享，重新创建"; SID=$(curl -s -X POST $B/api/share -H "X-User-Token: $AUTHOR" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元","trial_mode":"first_n_chapters","trial_value":3}' | jqget "['share_id']"); }
echo "SID=$SID"

echo "== TOC 可读标记 =="
TOC_A=$(curl -s $B/api/share/$SID/chapters)
R0=$(echo "$TOC_A" | jqget "['chapters'][0]['readable']")
R5=$(echo "$TOC_A" | jqget "['chapters'][5]['readable']")
HFA=$(echo "$TOC_A" | jqget "['has_full_access']")
TC=$(echo "$TOC_A" | jqget "['trial_chapters']")
[ "$R0" = "True" ] && [ "$R5" = "False" ] && [ "$HFA" = "False" ] && [ "$TC" = "3" ] && pass "匿名目录: 前3章可读标记/试读外锁定/trial_chapters=3" || fail "匿名目录: r0=$R0 r5=$R5 hfa=$HFA tc=$TC"
TOC_R=$(curl -s $B/api/share/$SID/chapters -H "X-User-Token: $READER")
[ "$(echo "$TOC_R" | jqget "['has_full_access']")" = "True" ] && pass "注册用户: has_full_access=true" || fail "注册用户目录"

echo "== 注册用例 =="
NEWCODE=$(curl -s -X POST $B/api/admin/invite-codes -H "X-User-Token: $ADMIN" -H 'Content-Type: application/json' -d '{"max_uses":5}' | jqget "['code']")
NEWTOKEN=login__$NEWCODE__
[ -n "$NEWTOKEN" ] && [ "$NEWTOKEN" != "None" ] && pass "新邀请码注册登录成功" || fail "新邀请码登录"
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/11 -H "X-User-Token: $NEWTOKEN")" = "200" ] && pass "新注册用户全文可读(chapter/11)" || fail "新用户全文"
CV1=$(curl -s -X POST $B/api/share/$SID/conversion -H "X-User-Token: $NEWTOKEN" -H 'Content-Type: application/json' -d '{}')
CV2=$(curl -s -X POST $B/api/share/$SID/conversion -H "X-User-Token: $NEWTOKEN" -H 'Content-Type: application/json' -d '{}')
echo "$CV1" | grep -q '"recorded":true' && echo "$CV2" | grep -q '"recorded":false' && pass "转化上报幂等" || fail "转化幂等: $CV1 / $CV2"
curl -s -o /dev/null -X PUT $B/api/bookshelf/%E6%98%9F%E5%B0%98%E7%BA%AA%E5%85%83 -H "X-User-Token: $READER" -H 'Content-Type: application/json' -d "{\"in_bookshelf\":true,\"share_id\":\"$SID\"}"
SHELF=$(curl -s $B/api/bookshelf -H "X-User-Token: $READER")
echo "$SHELF" | grep -q "星尘纪元" && pass "书架加入/列出" || fail "书架: $SHELF"
curl -s -o /dev/null -X PUT $B/api/share/$SID/progress -H "X-User-Token: $READER" -H 'Content-Type: application/json' -d '{"chapter_index":7}'
[ "$(curl -s $B/api/share/$SID/progress -H "X-User-Token: $READER" | jqget "['chapter_index']")" = "7" ] && pass "阅读进度读写" || fail "进度"

echo "== 单元测试 =="
if uv run pytest tests/test_share_api.py -q 2>&1 | tail -1 | grep -qE "[0-9]+ passed"; then
  pass "tests/test_share_api.py 全过"
else
  fail "test_share_api.py 有失败"
fi

echo ""
echo "━━━ 需求B补跑: $PASS 通过 / $FAIL 失败 ━━━"
exit $FAIL
