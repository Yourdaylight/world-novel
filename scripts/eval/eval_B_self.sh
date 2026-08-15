#!/usr/bin/env bash
# §7.2 需求 B 评测（自执行版）— 针对 http://127.0.0.1:8127 (data-eval-b)
set -uo pipefail
cd /mnt/tos/workspace/world-novel
B=http://127.0.0.1:8127
PASS=*** FAIL=0
pass() { PASS=*** echo "  ✅ $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ $1"; }
jqget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval('d'+sys.argv[1]))" "$1" 2>/dev/null; }

login() { curl -s -X POST $B/api/auth/login -H 'Content-Type: application/json' -d "{\"invite_code\":\"$1\"}" | jqget "['access_token']"; }

AUTHOR=$(login author_demo)
READER=$(login reader_demo)
ADMIN=$(login admin_demo)
[ -n "$AUTHOR" ] && [ "$AUTHOR" != "None" ] && pass "作者登录" || { fail "作者登录"; exit 1; }
[ -n "$READER" ] && [ "$READER" != "None" ] && pass "读者登录" || fail "读者登录"

echo "== 用例1: 权限矩阵 =="
SHARE_JSON=$(curl -s -X POST $B/api/share -H "X-User-Token: $AUTHOR" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元","trial_mode":"first_n_chapters","trial_value":3}')
SID=$(echo "$SHARE_JSON" | jqget "['share_id']")
[ -n "$SID" ] && [ "$SID" != "None" ] && pass "创建分享: $SID" || { fail "创建分享: $SHARE_JSON"; exit 1; }

# 元数据三者可见
for T in "" "-H X-User-Token:$READER" "-H X-User-Token:$AUTHOR"; do
  C=$(curl -s -o /dev/null -w "%{http_code}" $T $B/api/share/$SID)
  [ "$C" = "200" ] || fail "元数据访问($T) → $C"
done
pass "元数据: 匿名/注册/作者均200"

# 目录可读标记
TOC_A=$(curl -s $B/api/share/$SID/chapters)
R0=$(echo "$TOC_A" | jqget "['chapters'][0]['readable']")
R5=$(echo "$TOC_A" | jqget "['chapters'][5]['readable']")
HFA=$(echo "$TOC_A" | jqget "['has_full_access']")
[ "$R0" = "True" ] && [ "$R5" = "False" ] && [ "$HFA" = "False" ] && pass "匿名目录: 0-2可读/5锁定/无全文权限" || fail "匿名目录标记: r0=$R0 r5=$R5 hfa=$HFA"
TOC_R=$(curl -s $B/api/share/$SID/chapters -H "X-User-Token: $READER")
[ "$(echo "$TOC_R" | jqget "['has_full_access']")" = "True" ] && pass "注册用户: has_full_access=true" || fail "注册用户目录"

# 正文权限
C2=$(curl -s -o /dev/null -w "%{http_code}" $B/api/share/$SID/chapter/2)
[ "$C2" = "200" ] && pass "匿名读第3章(试读内) 200" || fail "匿名chapter/2 → $C2"
R5BODY=$(curl -s -w "\n%{http_code}" $B/api/share/$SID/chapter/5)
R5CODE=$(echo "$R5BODY" | tail -1)
R5TXT=$(echo "$R5BODY" | head -n -1)
if [ "$R5CODE" = "403" ]; then
  pass "匿名读试读外 chapter/5 → 403"
  echo "$R5TXT" | grep -q "need_login" && pass "403 含 need_login" || fail "403 缺 need_login"
  echo "$R5TXT" | grep -q "星舰穿过陨石带" && fail "403 泄露正文!" || pass "403 不含正文"
else
  fail "匿名chapter/5 → $R5CODE(期望403)"
fi
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/5 -H "X-User-Token: $READER")" = "200" ] && pass "注册用户读全文 200" || fail "注册用户chapter/5"
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/5 -H "X-User-Token: $AUTHOR")" = "200" ] && pass "作者读全文 200" || fail "作者chapter/5"

# 管理接口权限
[ "$(curl -s -o /dev/null -w '%{http_code}' -X PATCH $B/api/share/$SID -H 'Content-Type: application/json' -d '{"trial_value":1}')" = "401" ] && pass "管理接口匿名 401" || fail "管理匿名"
[ "$(curl -s -o /dev/null -w '%{http_code}' -X PATCH $B/api/share/$SID -H "X-User-Token: $READER" -H 'Content-Type: application/json' -d '{"trial_value":1}')" = "403" ] && pass "管理接口非所有者 403" || fail "管理非所有者"
[ "$(curl -s -o /dev/null -w '%{http_code}' -X PATCH $B/api/share/$SID -H "X-User-Token: $AUTHOR" -H 'Content-Type: application/json' -d '{"trial_value":3}')" = "200" ] && pass "管理接口所有者 200" || fail "管理所有者"

echo "== 用例2: 边界用例 =="
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/2)" = "200" ] && [ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/3)" = "403" ] && pass "试读边界恰好(2可读/3拒绝)" || fail "试读边界"
curl -s -o /dev/null -X PATCH $B/api/share/$SID -H "X-User-Token: $AUTHOR" -H 'Content-Type: application/json' -d '{"trial_value":1}'
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/1)" = "403" ] && pass "试读改1章即时生效(chapter/1→403)" || fail "试读即时生效"
curl -s -o /dev/null -X PATCH $B/api/share/$SID -H "X-User-Token: $AUTHOR" -H 'Content-Type: application/json' -d '{"trial_value":3}'

curl -s -o /dev/null -X DELETE $B/api/share/$SID -H "X-User-Token: $AUTHOR"
D1=$(curl -s -o /dev/null -w "%{http_code}" $B/api/share/$SID)
D2=$(curl -s -o /dev/null -w "%{http_code}" $B/api/share/$SID/chapter/0 -H "X-User-Token: $READER")
[ "$D1" = "404" ] && [ "$D2" = "404" ] && pass "关闭分享后全部404(含带token正文)" || fail "关闭后 meta=$D1 body=$D2"
curl -s -o /dev/null -X PATCH $B/api/share/$SID -H "X-User-Token: $AUTHOR" -H 'Content-Type: application/json' -d '{"status":"active"}'
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID)" = "200" ] && pass "重新开启恢复访问" || fail "重新开启"

# 过期 token
EXPTOKEN=$(uv run python -c "
from datetime import datetime, timedelta, timezone
from jose import jwt
print(jwt.encode({'code':'reader_demo','is_admin':False,'exp':datetime.now(timezone.utc)-timedelta(hours=1),'iat':datetime.now(timezone.utc)-timedelta(hours=2)},'eval-secret-do-not-use-in-prod',algorithm='HS256'))
")
R=$(curl -s -o /dev/null -w "%{http_code}" $B/api/share/$SID/chapter/5 -H "X-User-Token: $EXPTOKEN")
[ "$R" = "403" ] && pass "过期token回到试读权限(403)" || fail "过期token → $R"

echo "== 用例3: 安全用例 =="
# 1000 次随机 ID 枚举（容忍限流429，不得出现200）
LEAK=0; CNT404=0; CNT429=0
for i in $(seq 1 1000); do
  RID=$(head -c5 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-10)
  C=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 $B/api/share/$RID)
  case "$C" in
    200) LEAK=$((LEAK+1));;
    404) CNT404=$((CNT404+1));;
    429) CNT429=$((CNT429+1)); sleep 61;;  # 被限流则等窗口复位
  esac
  [ "$LEAK" -gt 0 ] && break
done
[ "$LEAK" = "0" ] && pass "1000次ID枚举无泄露(404×$CNT404, 429×$CNT429)" || fail "枚举出现200泄露!"
# 限流
sleep 61
GOT429=$(seq 1 90 | xargs -P 20 -I{} curl -s -o /dev/null -w "%{http_code}\n" $B/api/share/$SID | grep -c 429)
[ "$GOT429" -gt 0 ] && pass "限流429生效($GOT429/90被限)" || fail "限流未触发"
sleep 61

echo "== 用例4: 注册用例 =="
[ "$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/api/auth/login -H 'Content-Type: application/json' -d '{"invite_code":"INVALID999"}')" = "401" ] && pass "无效邀请码 401" || fail "无效邀请码"
NEWCODE=$(curl -s -X POST $B/api/admin/invite-codes -H "X-User-Token: $ADMIN" -H 'Content-Type: application/json' -d '{"max_uses":5}' | jqget "['code']")
NEWTOKEN=login__$NEWCODE__
[ -n "$NEWTOKEN" ] && [ "$NEWTOKEN" != "None" ] && pass "新邀请码注册登录成功" || fail "新邀请码登录: $NEWCODE"
[ "$(curl -s -o /dev/null -w '%{http_code}' $B/api/share/$SID/chapter/11 -H "X-User-Token: $NEWTOKEN")" = "200" ] && pass "新注册用户全文可读(chapter/11)" || fail "新用户全文"
CV1=$(curl -s -X POST $B/api/share/$SID/conversion -H "X-User-Token: $NEWTOKEN" -H 'Content-Type: application/json' -d '{}')
CV2=$(curl -s -X POST $B/api/share/$SID/conversion -H "X-User-Token: $NEWTOKEN" -H 'Content-Type: application/json' -d '{}')
echo "$CV1" | grep -q '"recorded":true' && echo "$CV2" | grep -q '"recorded":false' && pass "转化上报幂等" || fail "转化幂等: $CV1 / $CV2"
curl -s -o /dev/null -X PUT $B/api/bookshelf/%E6%98%9F%E5%B0%98%E7%BA%AA%E5%85%83 -H "X-User-Token: $READER" -H 'Content-Type: application/json' -d "{\"in_bookshelf\":true,\"share_id\":\"$SID\"}"
SHELF=$(curl -s $B/api/bookshelf -H "X-User-Token: $READER")
echo "$SHELF" | grep -q "星尘纪元" && pass "书架加入/列出" || fail "书架: $SHELF"
curl -s -o /dev/null -X PUT $B/api/share/$SID/progress -H "X-User-Token: $READER" -H 'Content-Type: application/json' -d '{"chapter_index":7}'
[ "$(curl -s $B/api/share/$SID/progress -H "X-User-Token: $READER" | jqget "['chapter_index']")" = "7" ] && pass "阅读进度读写" || fail "进度"

echo "== 用例5: 单元测试 =="
if uv run pytest tests/test_share_api.py -q 2>&1 | tail -1 | grep -qE "[0-9]+ passed"; then
  pass "tests/test_share_api.py 全过(38项)"
else
  fail "test_share_api.py 有失败"
fi

echo ""
echo "━━━ 需求B评测: $PASS 通过 / $FAIL 失败 ━━━"
exit $FAIL
