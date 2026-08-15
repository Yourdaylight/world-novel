#!/usr/bin/env python3
"""§7.2 需求 B 剩余评测（TOC 标记 / 注册用例）— Python 版，避开 shell 引号问题。"""
import json
import subprocess
import sys
import urllib.request
import urllib.error

B = "http://127.0.0.1:8127"
PASS = 0
FAIL = 0


def check(ok, name, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def req(method, path, token=None, body=None):
    url = B + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-User-Token", token)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def login(code):
    _, d = req("POST", "/api/auth/login", body={"invite_code": code})
    return d.get("access_token")


AUTHOR = login("author_demo")
READER = login("reader_demo")
ADMIN = login("admin_demo")

# 复用既有分享
_, sd = req("GET", "/api/shares", token=AUTHOR)
shares = sd.get("shares", [])
SID = shares[0]["share_id"] if shares else None
if not SID:
    _, cd = req("POST", "/api/share", token=AUTHOR,
                body={"novel_id": "星尘纪元", "trial_mode": "first_n_chapters", "trial_value": 3})
    SID = cd.get("share_id")
print(f"SID={SID}")

print("== TOC 可读标记 ==")
_, toc_a = req("GET", f"/api/share/{SID}/chapters")
flags = [c["readable"] for c in toc_a.get("chapters", [])]
check(flags[:3] == [True] * 3 and flags[3:] == [False] * 9
      and toc_a.get("has_full_access") is False and toc_a.get("trial_chapters") == 3,
      "匿名目录: 前3章可读/试读外锁定/trial_chapters=3",
      f"flags={flags[:5]}... hfa={toc_a.get('has_full_access')} tc={toc_a.get('trial_chapters')}")

_, toc_r = req("GET", f"/api/share/{SID}/chapters", token=READER)
check(toc_r.get("has_full_access") is True
      and all(c["readable"] for c in toc_r.get("chapters", [])),
      "注册用户: has_full_access=true 全部可读",
      f"hfa={toc_r.get('has_full_access')}")

print("== 注册用例 ==")
_, nc = req("POST", "/api/admin/invite-codes", token=ADMIN, body={"max_uses": 5})
NEWCODE = nc.get("code")
NEWTOKEN = login(NEWCODE) if NEWCODE else None
check(bool(NEWTOKEN), "新邀请码注册登录成功", f"code={NEWCODE}")

st, _ = req("GET", f"/api/share/{SID}/chapter/11", token=NEWTOKEN)
check(st == 200, "新注册用户全文可读(chapter/11)", f"status={st}")

cv1_st, cv1 = req("POST", f"/api/share/{SID}/conversion", token=NEWTOKEN, body={})
cv2_st, cv2 = req("POST", f"/api/share/{SID}/conversion", token=NEWTOKEN, body={})
check(cv1.get("recorded") is True and cv2.get("recorded") is False,
      "转化上报幂等", f"cv1={cv1} cv2={cv2}")

from urllib.parse import quote
st, _ = req("PUT", f"/api/bookshelf/{quote('星尘纪元')}", token=READER,
            body={"in_bookshelf": True, "share_id": SID})
st2, shelf = req("GET", "/api/bookshelf", token=READER)
check(any(e["novel_id"] == "星尘纪元" for e in shelf.get("bookshelf", [])),
      "书架加入/列出", f"shelf={shelf}")

req("PUT", f"/api/share/{SID}/progress", token=READER, body={"chapter_index": 7})
_, prog = req("GET", f"/api/share/{SID}/progress", token=READER)
check(prog.get("chapter_index") == 7, "阅读进度读写", f"prog={prog}")

print("== 单元测试 ==")
r = subprocess.run(["uv", "run", "pytest", "tests/test_share_api.py", "-q"],
                   capture_output=True, text=True, cwd="/mnt/tos/workspace/world-novel")
last = (r.stdout.strip().splitlines() or [""])[-1]
check("passed" in last and "failed" not in last, "tests/test_share_api.py 全过", last)

print()
print(f"━━━ 需求B剩余评测: {PASS} 通过 / {FAIL} 失败 ━━━")
sys.exit(FAIL)
