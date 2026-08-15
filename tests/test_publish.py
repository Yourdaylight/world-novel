"""Milestone 15 Requirement A — publication preflight & platform export tests.

Covers needs-doc §7.1:
  - E2E export on a ≥10-chapter book (seeded directly — no LLM key needed)
  - quality gate refuses broken books (missing / empty chapters)
  - platform spec checks: GB18030 for fanqie, per-volume split for qimao,
    EPUB validity, word counts
  - publication records lifecycle + backfill
"""

import asyncio
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# ── Environment bootstrap (before importing the app) ─────────────
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root / "src"))

_tmpdir = tempfile.mkdtemp(prefix="wn_publish_test_")
DB_PATH = str(Path(_tmpdir) / "central.db")

os.environ["NOVEL_DB_PATH"] = DB_PATH
os.environ["NOVEL_JWT_SECRET"] = "publish-test-secret"
os.environ["NOVEL_AUTH_MODE"] = "jwt"
os.environ.pop("NOVEL_AUTH_ENABLED", None)

from fastapi.testclient import TestClient  # noqa: E402

from novel_creator.config import settings  # noqa: E402
from novel_creator.memory.database import get_connection  # noqa: E402
from novel_creator.memory.registry import register_novel  # noqa: E402
from novel_creator.web.app import app  # noqa: E402

ADMIN_CODE = "admin_publisher"
TOTAL_CHAPTERS = 12

# Filled by the module fixture
NOVEL_ID = None
NOVEL_DB = None
TOKEN = ""

client = TestClient(app, raise_server_exceptions=False)


def _run(coro):
    return asyncio.run(coro)


def _chapter_body(i: int) -> str:
    return f"第{i + 1}章正文。" + ("江湖夜雨十年灯，" * 40)


async def _seed():
    conn = await get_connection(DB_PATH)
    await conn.execute(
        "INSERT OR IGNORE INTO invite_codes (code, is_active, max_uses) VALUES (?, 1, 0)",
        (ADMIN_CODE,),
    )
    await conn.commit()
    await conn.close()

    info = register_novel(title="发布测试之书", genre="玄幻", num_chapters=TOTAL_CHAPTERS)
    conn = await get_connection(info.db_path)
    for i in range(TOTAL_CHAPTERS):
        await conn.execute(
            "INSERT INTO chapter_texts (chapter_index, scene_index, title, content, summary) "
            "VALUES (?, 0, ?, ?, ?)",
            (i, f"章节标题{i + 1}", _chapter_body(i), f"概要{i + 1}"),
        )
    # Two volumes: 0-5, 6-11
    await conn.execute(
        "INSERT INTO volumes (volume_index, title, chapter_start, chapter_end) "
        "VALUES (0, '卷一 觉醒', 0, 5)"
    )
    await conn.execute(
        "INSERT INTO volumes (volume_index, title, chapter_start, chapter_end) "
        "VALUES (1, '卷二 争锋', 6, 11)"
    )
    outline = {
        "title": "发布测试之书",
        "genre": "玄幻",
        "theme": "逆天改命",
        "premise": "少年偶得上古传承，自此一路横推。",
        "setting": "九天十地，万族林立。",
        "chapters": [
            {"chapter_index": i, "title": f"章节标题{i + 1}"} for i in range(TOTAL_CHAPTERS)
        ],
        "volumes": [],
    }
    await conn.execute(
        "INSERT INTO story_outline (id, outline_json) VALUES (1, ?)",
        (json.dumps(outline, ensure_ascii=False),),
    )
    await conn.commit()
    await conn.close()
    return info.novel_id, info.db_path


@pytest.fixture(scope="module", autouse=True)
def setup_publish_module():
    global NOVEL_ID, NOVEL_DB, TOKEN
    os.chdir(_tmpdir)
    settings.db_path = DB_PATH  # isolate from other test modules
    NOVEL_ID, NOVEL_DB = _run(_seed())
    resp = client.post("/api/auth/login", json={"invite_code": ADMIN_CODE})
    assert resp.status_code == 200, resp.text
    TOKEN = resp.json()["access_token"]
    yield


def _auth() -> dict:
    return {"X-User-Token": TOKEN}


# ══════════════════════════════════════════════════════════════
# Platform list
# ══════════════════════════════════════════════════════════════


def test_platforms_listed():
    resp = client.get("/api/publish/platforms", headers=_auth())
    assert resp.status_code == 200
    platforms = {p["platform"] for p in resp.json()["platforms"]}
    assert {"fanqie", "qimao", "txt", "epub"} <= platforms


def test_publish_requires_auth():
    assert client.get("/api/publish/platforms").status_code == 401
    assert (
        client.post("/api/publish/preflight", json={"novel_id": NOVEL_ID}).status_code == 401
    )


# ══════════════════════════════════════════════════════════════
# Preflight quality gate
# ══════════════════════════════════════════════════════════════


def test_preflight_ok_for_complete_book():
    resp = client.post(
        "/api/publish/preflight",
        json={"novel_id": NOVEL_ID, "platform": "fanqie"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["errors"] == []
    assert data["stats"]["chapters"] == TOTAL_CHAPTERS
    assert data["stats"]["total_words"] > 1000
    assert data["stats"]["volume_count"] == 2


def test_preflight_detects_missing_chapter():
    """人为制造断章 → 门禁拒绝。"""

    async def _break():
        conn = await get_connection(NOVEL_DB)
        await conn.execute("DELETE FROM chapter_texts WHERE chapter_index = 7")
        await conn.commit()
        await conn.close()

    _run(_break())
    data = client.post(
        "/api/publish/preflight", json={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()
    assert data["ok"] is False
    assert any("断章" in e or "缺失" in e for e in data["errors"])

    # export must also refuse
    resp = client.post(
        "/api/publish/export",
        json={"novel_id": NOVEL_ID, "platform": "fanqie"},
        headers=_auth(),
    )
    assert resp.status_code == 422

    async def _restore():
        conn = await get_connection(NOVEL_DB)
        await conn.execute(
            "INSERT INTO chapter_texts (chapter_index, scene_index, title, content, summary) "
            "VALUES (7, 0, ?, ?, ?)",
            ("章节标题8", _chapter_body(7), "概要8"),
        )
        await conn.commit()
        await conn.close()

    _run(_restore())
    data = client.post(
        "/api/publish/preflight", json={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()
    assert data["ok"] is True


def test_preflight_detects_empty_chapter():
    """空章节 → 门禁拒绝。"""

    async def _empty():
        conn = await get_connection(NOVEL_DB)
        await conn.execute(
            "UPDATE chapter_texts SET content = '' WHERE chapter_index = 3"
        )
        await conn.commit()
        await conn.close()

    _run(_empty())
    data = client.post(
        "/api/publish/preflight", json={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()
    assert data["ok"] is False
    assert any("空" in e for e in data["errors"])

    async def _fill():
        conn = await get_connection(NOVEL_DB)
        await conn.execute(
            "UPDATE chapter_texts SET content = ? WHERE chapter_index = 3",
            (_chapter_body(3),),
        )
        await conn.commit()
        await conn.close()

    _run(_fill())


def test_preflight_sensitive_word_warning():
    """敏感词命中 → warning（不阻断）。"""

    async def _inject():
        conn = await get_connection(NOVEL_DB)
        await conn.execute(
            "UPDATE chapter_texts SET content = content || ' 刷单返利 '"
            " WHERE chapter_index = 0"
        )
        await conn.commit()
        await conn.close()

    _run(_inject())
    data = client.post(
        "/api/publish/preflight", json={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()
    assert data["ok"] is True  # warning only
    assert any("敏感词" in w for w in data["warnings"])
    assert any(h["word"] == "刷单返利" for h in data["sensitive_hits"])

    async def _clean():
        conn = await get_connection(NOVEL_DB)
        await conn.execute(
            "UPDATE chapter_texts SET content = REPLACE(content, ' 刷单返利 ', '') "
            "WHERE chapter_index = 0"
        )
        await conn.commit()
        await conn.close()

    _run(_clean())


# ══════════════════════════════════════════════════════════════
# Export E2E (§7.1)
# ══════════════════════════════════════════════════════════════


def _export(platform: str):
    resp = client.post(
        "/api/publish/export",
        json={"novel_id": NOVEL_ID, "platform": platform},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text[:200]
    return resp


def test_export_fanqie_gb18030():
    """番茄导出：TXT GB18030、章节完整、字数正确。"""
    resp = _export("fanqie")
    assert resp.headers["content-type"] == "application/zip"
    record_id = resp.headers.get("x-publication-record-id")
    assert record_id

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    txt_name = next(n for n in names if n.endswith(".txt") and "全文" in n)
    raw = zf.read(txt_name)
    text = raw.decode("gb18030")  # 必须是 GB18030 编码

    for i in range(TOTAL_CHAPTERS):
        assert f"第{i + 1}章 章节标题{i + 1}" in text
    assert "第1章正文。" in text

    # 配套文件
    assert any("synopsis" in n for n in names)
    assert any(n.endswith("cover.svg") for n in names)
    assert any("README" in n for n in names)

    synopsis = zf.read(next(n for n in names if "synopsis" in n)).decode("gb18030")
    assert "少年偶得上古传承" in synopsis


def test_export_txt_generic_with_volume_marks():
    """通用 TXT 导出：UTF-8 + 分卷卷头标记。"""
    resp = _export("txt")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    txt_name = next(n for n in names if n.endswith(".txt") and "全文" in n)
    text = zf.read(txt_name).decode("utf-8")
    assert "卷一 觉醒" in text
    assert "卷二 争锋" in text
    assert "第7章" in text


def test_export_qimao_per_volume():
    """七猫导出：按卷拆分多个 TXT 文件（卷一=第1-6章，卷二=第7-12章）。"""
    resp = _export("qimao")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    volume_files = sorted(n for n in names if "卷" in n and n.endswith(".txt"))
    assert len(volume_files) == 2

    v1 = zf.read(volume_files[0]).decode("utf-8")
    v2 = zf.read(volume_files[1]).decode("utf-8")
    assert "第1章" in v1 and "第6章" in v1 and "第7章" not in v1
    assert "第7章" in v2 and "第12章" in v2 and "第1章 " not in v2


def test_export_epub_valid():
    """EPUB 导出：合法的 EPUB3 包结构。"""
    resp = _export("epub")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    epub_name = next(n for n in zf.namelist() if n.endswith(".epub"))
    epub = zipfile.ZipFile(io.BytesIO(zf.read(epub_name)))

    epub_names = epub.namelist()
    # mimetype must be the first entry
    assert epub_names[0] == "mimetype"
    assert epub.read("mimetype") == b"application/epub+zip"
    assert "META-INF/container.xml" in epub_names
    assert "OEBPS/content.opf" in epub_names
    assert "OEBPS/nav.xhtml" in epub_names

    chapter_files = [n for n in epub_names if n.startswith("OEBPS/chapter-")]
    assert len(chapter_files) == TOTAL_CHAPTERS

    opf = epub.read("OEBPS/content.opf").decode("utf-8")
    assert "发布测试之书" in opf
    ch0 = epub.read("OEBPS/chapter-0000.xhtml").decode("utf-8")
    assert "第1章正文" in ch0


def test_unknown_platform_400():
    resp = client.post(
        "/api/publish/export",
        json={"novel_id": NOVEL_ID, "platform": "not-exist"},
        headers=_auth(),
    )
    assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════
# Publication records & backfill (A-3 / A-5)
# ══════════════════════════════════════════════════════════════


def test_records_listed():
    records = client.get(
        "/api/publish/records", params={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()["records"]
    assert len(records) >= 3  # fanqie + qimao + epub
    stages = {r["stage"] for r in records}
    assert "exported" in stages
    metas = [r["export_meta"] for r in records]
    assert all(m.get("chapters") == TOTAL_CHAPTERS for m in metas)


def test_backfill_marks_published():
    records = client.get(
        "/api/publish/records", params={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()["records"]
    rec = records[0]

    resp = client.patch(
        f"/api/publish/records/{rec['id']}",
        json={"target_book_id": "BK12345", "target_url": "https://example.com/book/1"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    updated = resp.json()["record"]
    assert updated["stage"] == "published"
    assert updated["target_book_id"] == "BK12345"
    assert updated["target_url"] == "https://example.com/book/1"


def test_backfill_unknown_record_404():
    resp = client.patch(
        "/api/publish/records/pub_nonexistent",
        json={"target_url": "https://x"},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_confirm_l1_reserved_501():
    """L1 半自动发布：平台无开放 API → 501 + 明确文案。"""
    records = client.get(
        "/api/publish/records", params={"novel_id": NOVEL_ID}, headers=_auth()
    ).json()["records"]
    resp = client.post(
        f"/api/publish/records/{records[0]['id']}/confirm", headers=_auth()
    )
    assert resp.status_code == 501
    assert "L0" in resp.json()["detail"] or "手动" in resp.json()["detail"]
