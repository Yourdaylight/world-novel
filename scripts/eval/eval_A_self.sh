#!/usr/bin/env bash
# §7.1 需求 A 评测（自执行版）— 针对 http://127.0.0.1:8126 (data-eval-a)
set -uo pipefail
cd /mnt/tos/workspace/world-novel
B=http://127.0.0.1:8126
PASS=*** FAIL=0
pass() { PASS=*** echo "  ✅ $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ $1"; }
jqget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval('d'+sys.argv[1]))" "$1"; }

TOKEN=$(curl -s -X POST $B/api/auth/login -H 'Content-Type: application/json' -d '{"invite_code":"admin_demo"}' | jqget "['access_token']")
[ -n "$TOKEN" ] && [ "$TOKEN" != "None" ] && pass "admin_demo 登录" || { fail "登录失败"; exit 1; }

echo "== 用例1: E2E 导出 (fanqie, 12章) =="
curl -s -o /tmp/evalA_fanqie.zip -D /tmp/evalA_h.txt -X POST $B/api/publish/export \
  -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"novel_id":"星尘纪元","platform":"fanqie"}'
grep -qi "x-publication-record-id" /tmp/evalA_h.txt && pass "导出返回发布记录ID" || fail "缺发布记录ID"
uv run python - <<'PY' && pass "fanqie: GB18030编码+12章完整+配套文件" || fail "fanqie 包校验失败"
import zipfile, re
zf = zipfile.ZipFile('/tmp/evalA_fanqie.zip')
names = zf.namelist()
txt = next(n for n in names if n.endswith('.txt') and '全文' in n)
t = zf.read(txt).decode('gb18030')  # 必须GB18030
chs = sorted(set(int(x) for x in re.findall(r'第(\d+)章', t)))
assert chs == list(range(1, 13)), f"章节不全: {chs}"
assert any('synopsis' in n for n in names), "缺synopsis"
assert any('cover.svg' in n for n in names), "缺cover"
assert any('README' in n for n in names), "缺README"
assert '星舰穿过陨石带' in t, "正文缺失"
PY

echo "== 用例2: 质量门禁 (断章/空章) =="
DB=data-eval-a/data/novels/星尘纪元/novel.db
uv run python - <<'PY'
import sqlite3
c = sqlite3.connect('data-eval-a/data/novels/星尘纪元/novel.db')
c.execute("DELETE FROM chapter_texts WHERE chapter_index = 4")
c.commit(); c.close()
PY
PRE=$(curl -s -X POST $B/api/publish/preflight -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元"}')
echo "$PRE" | grep -q '"ok":false' && pass "断章 → preflight ok=false" || fail "断章未拦截: $PRE"
echo "$PRE" | grep -q "断章" && pass "断章错误信息" || fail "缺断章信息"
EXP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST $B/api/publish/export -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元","platform":"fanqie"}')
[ "$EXP_CODE" = "422" ] && pass "断章 → export 422 拒绝" || fail "断章导出未拒绝($EXP_CODE)"
uv run python - <<'PY'
import sqlite3
c = sqlite3.connect('data-eval-a/data/novels/星尘纪元/novel.db')
c.execute("UPDATE chapter_texts SET content = '' WHERE chapter_index = 4")
# 先恢复第5章行
c.execute("INSERT OR IGNORE INTO chapter_texts (chapter_index, scene_index, title, content, summary) VALUES (4, 0, '归途5', '', '概要')")
c.execute("UPDATE chapter_texts SET content='' WHERE chapter_index=4")
c.commit(); c.close()
PY
PRE=$(curl -s -X POST $B/api/publish/preflight -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元"}')
echo "$PRE" | grep -q "空章节" && pass "空章 → preflight 报错" || fail "空章未拦截: $PRE"
# 恢复
uv run python - <<'PY'
import sqlite3
body = ("星舰穿过陨石带的瞬间，林远看见了那颗蓝色星球的轮廓。"
        "三百年前的航迹图上，这里被标注为禁区。他握紧操纵杆，低声说：我们回家。") * 8
c = sqlite3.connect('data-eval-a/data/novels/星尘纪元/novel.db')
c.execute("UPDATE chapter_texts SET content=? WHERE chapter_index=4", (body,))
c.commit(); c.close()
PY
PRE=$(curl -s -X POST $B/api/publish/preflight -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元"}')
echo "$PRE" | grep -q '"ok":true' && pass "恢复后 preflight 通过" || fail "恢复失败: $PRE"

echo "== 用例3: 平台规范清单 =="
# qimao 分卷
curl -s -o /tmp/evalA_qimao.zip -X POST $B/api/publish/export -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元","platform":"qimao"}'
uv run python - <<'PY' && pass "qimao: 按卷拆分2文件且章节归属正确" || fail "qimao 分卷校验失败"
import zipfile, re
zf = zipfile.ZipFile('/tmp/evalA_qimao.zip')
vols = sorted(n for n in zf.namelist() if '卷' in n and n.endswith('.txt'))
assert len(vols) == 2, vols
v1 = zf.read(vols[0]).decode('utf-8')
v2 = zf.read(vols[1]).decode('utf-8')
c1 = sorted(set(int(x) for x in re.findall(r'第(\d+)章', v1)))
c2 = sorted(set(int(x) for x in re.findall(r'第(\d+)章', v2)))
assert c1 == list(range(1, 7)) and c2 == list(range(7, 13)), (c1, c2)
PY
# epub
curl -s -o /tmp/evalA_epub.zip -X POST $B/api/publish/export -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"novel_id":"星尘纪元","platform":"epub"}'
uv run python - <<'PY' && pass "epub: EPUB3结构合法(mimetype首条目/OPF/nav/12章)" || fail "epub 校验失败"
import zipfile
outer = zipfile.ZipFile('/tmp/evalA_epub.zip')
epub_name = next(n for n in outer.namelist() if n.endswith('.epub'))
zf = zipfile.ZipFile(__import__('io').BytesIO(outer.read(epub_name)))
names = zf.namelist()
assert names[0] == 'mimetype', names[0]
info = zf.getinfo('mimetype')
assert info.compress_type == zipfile.ZIP_STORED
assert zf.read('mimetype') == b'application/epub+zip'
assert 'META-INF/container.xml' in names
assert 'OEBPS/content.opf' in names
assert 'OEBPS/nav.xhtml' in names
chapters = [n for n in names if n.startswith('OEBPS/chapter-')]
assert len(chapters) == 12, len(chapters)
opf = zf.read('OEBPS/content.opf').decode('utf-8')
assert '星尘纪元' in opf
PY
# 发布记录 + 回填
RECS=$(curl -s "$B/api/publish/records?novel_id=%E6%98%9F%E5%B0%98%E7%BA%AA%E5%85%83" -H "X-User-Token: $TOKEN")
echo "$RECS" | grep -q '"stage":"exported"' && pass "发布记录已写入(stage=exported)" || fail "发布记录: $RECS"
RID=$(echo "$RECS" | jqget "['records'][0]['id']")
BK=$(curl -s -X PATCH "$B/api/publish/records/$RID" -H "X-User-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"target_url":"https://example.com/book/1","target_book_id":"BK-1"}')
echo "$BK" | grep -q '"stage":"published"' && pass "回填 → stage=published" || fail "回填: $BK"
CONF=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$B/api/publish/records/$RID/confirm" -H "X-User-Token: $TOKEN")
[ "$CONF" = "501" ] && pass "L1 confirm 预留 501" || fail "confirm=$CONF"

echo "== 用例4: 单元测试 =="
if uv run pytest tests/test_publish.py -q 2>&1 | tail -1 | grep -qE "[0-9]+ passed"; then
  pass "tests/test_publish.py 全过"
else
  fail "test_publish.py 有失败"
fi

echo ""
echo "━━━ 需求A评测: $PASS 通过 / $FAIL 失败 ━━━"
exit $FAIL
