"""Tests for requirement A (publish/export) and B (public share + register-to-read).

Runs against the real FastAPI app with TestClient, all data redirected into a
tmp directory. No LLM calls — chapter texts are written straight to SQLite.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.web.auth_deps import create_access_token
from novel_creator.web.rate_limit import share_limiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    import novel_creator.memory.registry as registry_mod
    monkeypatch.setattr(registry_mod, "REGISTRY_PATH", data_dir / "registry.json")
    monkeypatch.setattr(registry_mod, "NOVELS_DIR", data_dir / "novels")
    monkeypatch.setattr(settings, "db_path", str(data_dir / "global.db"))
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    # Public-share rate limit is exercised in its own test
    monkeypatch.setenv("NOVEL_SHARE_RATE_PER_MIN", "0")
    share_limiter.reset()
    return data_dir


@pytest.fixture
def client():
    from novel_creator.web.app import app
    return TestClient(app, raise_server_exceptions=False)


def auth(code: str, admin: bool = False) -> dict:
    return {"X-User-Token": create_access_token(code, admin)}


async def _seed_novel(novel_id: str = "test-book", chapters: int = 5,
                      empty: list[int] | None = None,
                      sensitive: bool = False,
                      long_chapter: bool = False,
                      with_volume: bool = False,
                      title: str = "测试成书",
                      owner: str = ""):
    """Populate a novel DB directly: outline + volumes + chapter_texts.

    Register under the slug (novel_id, ASCII) so the directory/id are stable;
    the human-readable Chinese title lives in the outline.
    """
    from novel_creator.memory.registry import register_novel, get_novel_by_id
    register_novel(title=novel_id, genre="武侠", num_chapters=chapters, owner_id=owner)
    new_db = get_novel_by_id(novel_id).db_path

    empty = empty or []
    outline = {
        "title": title,
        "genre": "武侠",
        "premise": "少年剑客下山闯荡江湖的故事。",
        "central_conflict": "侠义和庙堂的终极抉择。",
        "chapters": [
            {"chapter_index": i, "title": f"章节标题{i}", "summary": f"概要{i}"}
            for i in range(chapters)
        ],
        "volumes": [],
    }
    conn = await get_connection(str(new_db))
    await conn.execute(
        "INSERT INTO story_outline (id, outline_json) VALUES (1, ?)",
        (json.dumps(outline, ensure_ascii=False),),
    )
    if with_volume:
        await conn.execute(
            "INSERT INTO volumes (volume_index,title,chapter_start,chapter_end) VALUES (0,?,0,?)",
            ("初入江湖", chapters - 1),
        )
    for i in range(chapters):
        text = "" if i in empty else (
            f"这是第{i+1}章的正文内容。MARKER-{i} 剑客出门远行。\n天色渐晚，他在驿站歇脚。"
            + ("很长的章节。" * 400 if long_chapter and i == 0 else "")
        )
        if sensitive and i == 0:
            text += " 故事里有人吸食冰毒。"
        await conn.execute(
            "INSERT INTO chapter_texts (chapter_index, scene_index, title, content) VALUES (?,0,?,?)",
            (i, f"章节标题{i}", text),
        )
    await conn.commit()
    await conn.close()
    return novel_id


# ===========================================================================
# Requirement A — publish
# ===========================================================================

class TestPreflight:
    def test_healthy_book_passes(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "fanqie"},
                        headers=auth("author1"))
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["errors"] == []
        assert data["stats"]["chapters"] == 5
        assert data["stats"]["encoding"] == "gb18030"
        assert data["stats"]["total_words"] > 0

    def test_empty_chapter_blocks(self, client):
        import asyncio
        asyncio.run(_seed_novel(empty=[2]))
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "fanqie"},
                        headers=auth("author1"))
        data = r.json()
        assert data["ok"] is False
        assert any("空章节" in e for e in data["errors"])

    def test_broken_gap_blocks(self, client):
        import asyncio
        # 5 planned chapters, but chapter index 3 row missing entirely
        asyncio.run(_seed_novel(chapters=5))
        from novel_creator.memory.registry import get_novel_by_id
        import aiosqlite
        db = get_novel_by_id("test-book").db_path

        async def _drop_ch3():
            async with aiosqlite.connect(db) as c:
                await c.execute("DELETE FROM chapter_texts WHERE chapter_index=3")
                await c.commit()
        asyncio.run(_drop_ch3())
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "txt"},
                        headers=auth("author1"))
        data = r.json()
        # Missing planned chapter surfaces as an empty chapter (gate blocks)
        assert data["ok"] is False
        assert any("空章节" in e or "断章" in e for e in data["errors"])

    def test_sensitive_word_blocks(self, client):
        import asyncio
        asyncio.run(_seed_novel(sensitive=True))
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "fanqie"},
                        headers=auth("author1"))
        data = r.json()
        assert data["ok"] is False
        assert any("敏感词" in e for e in data["errors"])
        assert data["sensitive_hits"]

    def test_long_chapter_warns(self, client):
        import asyncio
        asyncio.run(_seed_novel(long_chapter=True))
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "fanqie"},
                        headers=auth("author1"))
        data = r.json()
        assert data["ok"] is True
        assert any("2000" in w for w in data["warnings"])

    def test_unknown_platform(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "wechat"},
                        headers=auth("author1"))
        assert r.json()["ok"] is False

    def test_requires_auth(self, client):
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "x", "platform": "fanqie"})
        assert r.status_code == 401


class TestExport:
    def test_fanqie_zip_gb18030(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        r = client.post("/api/publish/export",
                        json={"novel_id": "test-book", "platform": "fanqie"},
                        headers=auth("author1"))
        assert r.status_code == 200
        assert ".zip" in r.headers["content-disposition"]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert any(n.endswith(".txt") and "出版信息" not in n for n in names)
        assert "出版信息.txt" in names
        assert "封面占位.svg" in names
        txt = next(n for n in names if n.endswith(".txt") and "出版信息" not in n)
        raw = zf.read(txt)
        # GB18030 decodes cleanly; UTF-8 round-trip must not be silently used
        decoded = raw.decode("gb18030")
        assert "测试成书" in decoded
        assert "第1章 章节标题0" in decoded
        with pytest.raises(UnicodeDecodeError):
            raw.decode("ascii")

    def test_qimao_volume_files(self, client):
        import asyncio
        asyncio.run(_seed_novel(with_volume=True))
        r = client.post("/api/publish/export",
                        json={"novel_id": "test-book", "platform": "qimao"},
                        headers=auth("author1"))
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        assert any(n.startswith("分卷/") and n.endswith(".txt") for n in zf.namelist())

    def test_txt_utf8(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        r = client.post("/api/publish/export",
                        json={"novel_id": "test-book", "platform": "txt"},
                        headers=auth("author1"))
        assert "text/plain" in r.headers["content-type"]
        assert r.content.decode("utf-8").count("第") >= 5

    def test_epub_valid(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=4))
        r = client.post("/api/publish/export",
                        json={"novel_id": "test-book", "platform": "epub"},
                        headers=auth("author1"))
        assert r.status_code == 200
        assert "application/epub" in r.headers["content-type"]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"
        names = zf.namelist()
        assert "OEBPS/content.opf" in names
        assert "OEBPS/nav.xhtml" in names
        opf = zf.read("OEBPS/content.opf").decode("utf-8")
        assert opf.count("ch00") >= 4  # 4 chapters in manifest/spine
        assert "<dc:title>测试成书</dc:title>" in opf

    def test_export_blocked_by_gate_returns_409(self, client):
        import asyncio
        asyncio.run(_seed_novel(empty=[1]))
        r = client.post("/api/publish/export",
                        json={"novel_id": "test-book", "platform": "fanqie"},
                        headers=auth("author1"))
        assert r.status_code == 409
        assert r.json()["preflight"]["ok"] is False

    def test_record_created_and_backfilled(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        client.post("/api/publish/export",
                    json={"novel_id": "test-book", "platform": "fanqie"},
                    headers=auth("author1"))
        r = client.get("/api/publish/records?novel_id=test-book", headers=auth("author1"))
        recs = r.json()["records"]
        assert len(recs) == 1 and recs[0]["stage"] == "exported"
        rid = recs[0]["id"]
        r2 = client.post(f"/api/publish/records/{rid}/backfill",
                         json={"target_url": "https://fanqienovel.com/page/123"},
                         headers=auth("author1"))
        assert r2.status_code == 200
        r3 = client.get("/api/publish/records", headers=auth("author1"))
        assert r3.json()["records"][0]["stage"] == "published"

    def test_records_isolated_per_operator(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        client.post("/api/publish/export",
                    json={"novel_id": "test-book", "platform": "txt"},
                    headers=auth("author1"))
        r = client.get("/api/publish/records", headers=auth("author2"))
        assert r.json()["records"] == []

    def test_backfill_other_users_record_forbidden(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        client.post("/api/publish/export",
                    json={"novel_id": "test-book", "platform": "txt"},
                    headers=auth("author1"))
        rid = client.get("/api/publish/records", headers=auth("author1")).json()["records"][0]["id"]
        r = client.post(f"/api/publish/records/{rid}/backfill",
                        json={"target_url": "http://x"}, headers=auth("author2"))
        assert r.status_code == 403

    def test_l1_confirm_returns_501(self, client):
        r = client.post("/api/publish/records/nope/confirm", headers=auth("author1"))
        assert r.status_code == 501
        assert r.json()["code"] == "l1_not_enabled"


# ===========================================================================
# Requirement B — share
# ===========================================================================

class TestSharePermissionMatrix:
    def _create_share(self, client, code="author1", value=3):
        r = client.post("/api/share",
                        json={"novel_id": "test-book", "trial_mode": "first_n_chapters",
                              "trial_value": value},
                        headers=auth(code))
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_full_matrix(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=6))
        sid = self._create_share(client)
        assert len(sid) >= 8

        # ── anonymous ──
        meta = client.get(f"/api/share/{sid}")
        assert meta.status_code == 200
        body = meta.json()
        assert "novel_id" not in body and "owner_id" not in body
        assert body["authed"] is False
        assert body["trial_open_chapters"] == 3

        toc = client.get(f"/api/share/{sid}/chapters").json()["chapters"]
        flags = [c["readable"] for c in toc]
        assert flags == [True, True, True, False, False, False]
        # TOC carries no body text at all
        assert "MARKER-3" not in json.dumps(toc, ensure_ascii=False)

        # boundary: chapter index 2 readable, 3 locked
        ch2 = client.get(f"/api/share/{sid}/chapter/2")
        assert ch2.status_code == 200
        assert "MARKER-2" in ch2.json()["content"]
        ch3 = client.get(f"/api/share/{sid}/chapter/3")
        assert ch3.status_code == 403
        payload = ch3.json()
        assert payload["code"] == "need_login" and payload["trial_ok"] is False
        assert "content" not in payload and "MARKER-3" not in ch3.text

        # metadata/toc never leak locked content
        assert "MARKER-3" not in meta.text
        assert "MARKER-4" not in client.get(f"/api/share/{sid}/chapters").text

        # ── registered reader ──
        reader = auth("readerX")
        full = client.get(f"/api/share/{sid}/chapter/3", headers=reader)
        assert full.status_code == 200
        assert "MARKER-3" in full.json()["content"]

        # ── share management is author-only ──
        assert client.patch(f"/api/share/{sid}", json={"status": "disabled"}).status_code == 401
        assert client.patch(f"/api/share/{sid}", json={"status": "disabled"},
                            headers=reader).status_code == 403
        ok = client.patch(f"/api/share/{sid}", json={"status": "disabled"},
                          headers=auth("author1"))
        assert ok.status_code == 200

        # disabled → all public endpoints 404
        assert client.get(f"/api/share/{sid}").status_code == 404
        assert client.get(f"/api/share/{sid}/chapters").status_code == 404
        assert client.get(f"/api/share/{sid}/chapter/0").status_code == 404

    def test_trial_zero_locks_all(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=3))
        sid = self._create_share(client, value=0)
        r = client.get(f"/api/share/{sid}/chapter/0")
        assert r.status_code == 403

    def test_word_count_trial(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=4))
        sid = self._create_share(client)
        # word_count: ch0 (~39 chars) readable, cumulative threshold locks ch1
        client.patch(f"/api/share/{sid}",
                     json={"trial_mode": "word_count", "trial_value": 30},
                     headers=auth("author1"))
        assert client.get(f"/api/share/{sid}/chapter/0").status_code == 200
        assert client.get(f"/api/share/{sid}/chapter/1").status_code == 403

    def test_ratio_trial(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=10))
        sid = self._create_share(client)
        client.patch(f"/api/share/{sid}",
                     json={"trial_mode": "ratio", "trial_value": 40},
                     headers=auth("author1"))
        toc = client.get(f"/api/share/{sid}/chapters").json()["chapters"]
        assert sum(c["readable"] for c in toc) == 4

    def test_share_id_unenumerable(self, client):
        import asyncio, secrets
        asyncio.run(_seed_novel())
        self._create_share(client)
        # Random ids must all miss
        for _ in range(30):
            guess = secrets.token_urlsafe(6)
            assert client.get(f"/api/share/{guess}").status_code == 404

    def test_rate_limit_enforced(self, client, monkeypatch):
        import asyncio
        asyncio.run(_seed_novel())
        sid = self._create_share(client)
        monkeypatch.setenv("NOVEL_SHARE_RATE_PER_MIN", "5")
        share_limiter.reset()
        statuses = [client.get(f"/api/share/{sid}").status_code for _ in range(8)]
        assert statuses[:5] == [200] * 5
        assert 429 in statuses[5:]

    def test_invalid_token_falls_back_to_trial(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=5))
        sid = self._create_share(client)
        # garbage/expired token → anonymous rights, not error, not full access
        r = client.get(f"/api/share/{sid}/chapter/3",
                       headers={"X-User-Token": "not-a-valid-jwt"})
        assert r.status_code == 403

    def test_register_via_invite_code_unlocks(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=5))
        sid = self._create_share(client)
        # seed an invite code in the global DB
        from novel_creator.memory.quota_store import create_invite_code

        async def mk():
            c = await get_connection(settings.db_path)
            await create_invite_code(c, code="WELCOME1", max_uses=10)
            await c.close()
        asyncio.run(mk())
        # login with invite code (the open-source "registration")
        lr = client.post("/api/auth/login", json={"invite_code": "WELCOME1"})
        assert lr.status_code == 200
        token = lr.json()["access_token"]
        full = client.get(f"/api/share/{sid}/chapter/4",
                          headers={"X-User-Token": token})
        assert full.status_code == 200

    def test_invalid_invite_code_rejected(self, client):
        r = client.post("/api/auth/login", json={"invite_code": "NOPE9999"})
        assert r.status_code == 401

    def test_bookshelf_and_progress(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=5))
        sid = self._create_share(client)
        reader = auth("readerShelf")
        client.get(f"/api/share/{sid}/chapter/2", headers=reader)
        shelf = client.get("/api/bookshelf", headers=reader).json()["books"]
        assert len(shelf) == 1
        assert shelf[0]["share_id"] == sid
        assert shelf[0]["chapter_index"] == 2
        assert shelf[0]["available"] is True

    def test_idempotent_share_creation(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        a = client.post("/api/share", json={"novel_id": "test-book"}, headers=auth("author1"))
        b = client.post("/api/share", json={"novel_id": "test-book"}, headers=auth("author1"))
        assert a.json()["id"] == b.json()["id"]
        assert b.json()["created"] is False

    def test_share_missing_novel_404(self, client):
        r = client.post("/api/share", json={"novel_id": "missing"}, headers=auth("a"))
        assert r.status_code == 404

    def test_share_stats_increment(self, client):
        import asyncio
        asyncio.run(_seed_novel(chapters=3))
        sid = self._create_share(client)
        v1 = client.get(f"/api/share/{sid}").json()["stats"]["views"]
        v2 = client.get(f"/api/share/{sid}").json()["stats"]["views"]
        assert v2 == v1 + 1
        client.get(f"/api/share/{sid}/chapter/0")
        mine = client.get("/api/shares", headers=auth("author1")).json()["shares"][0]
        assert mine["read_count"] >= 1

# ===========================================================================
# Review regression tests (hardening from code review)
# ===========================================================================

class TestHardeningRegressions:
    def test_legacy_content_endpoints_require_auth(self, client):
        """S1: anonymous must NOT pull full text via legacy workbench routes."""
        import asyncio
        asyncio.run(_seed_novel())
        assert client.get("/api/novels").status_code == 401
        assert client.get("/api/novel-full", params={"novel_id": "test-book"}).status_code == 401
        assert client.get("/api/chapter-text/0", params={"novel_id": "test-book"}).status_code == 401
        assert client.get("/api/actions/0", params={"novel_id": "test-book"}).status_code == 401
        # authed still works
        ok = client.get("/api/novel-full", params={"novel_id": "test-book"}, headers=auth("author1"))
        assert ok.status_code == 200

    def test_share_other_users_novel_forbidden(self, client):
        """S4: only owner (or admin) may share an attributed novel."""
        import asyncio
        asyncio.run(_seed_novel(owner="author1"))
        r = client.post("/api/share", json={"novel_id": "test-book"}, headers=auth("intruder"))
        assert r.status_code == 403
        # admin can
        r2 = client.post("/api/share", json={"novel_id": "test-book"}, headers=auth("admin1", admin=True))
        assert r2.status_code == 200

    def test_publish_other_users_novel_forbidden(self, client):
        import asyncio
        asyncio.run(_seed_novel(owner="author1"))
        r = client.post("/api/publish/preflight",
                        json={"novel_id": "test-book", "platform": "txt"}, headers=auth("intruder"))
        assert r.status_code == 403

    def test_query_token_ignored_on_public_share(self, client):
        """B2: ?token= must not authenticate public reader endpoints."""
        import asyncio
        asyncio.run(_seed_novel(chapters=5))
        sid = client.post("/api/share", json={"novel_id": "test-book"},
                          headers=auth("author1")).json()["id"]
        token = create_access_token("readerQ")
        r = client.get(f"/api/share/{sid}/chapter/3", params={"token": token})
        assert r.status_code == 403  # query token ignored → anonymous trial
        # same token via header unlocks
        assert client.get(f"/api/share/{sid}/chapter/3",
                          headers={"X-User-Token": token}).status_code == 200

    def test_backfill_rejects_javascript_url(self, client):
        """S2: stored-XSS guard on platform backfill URL."""
        import asyncio
        asyncio.run(_seed_novel())
        client.post("/api/publish/export",
                    json={"novel_id": "test-book", "platform": "txt"},
                    headers=auth("author1"))
        rid = client.get("/api/publish/records", headers=auth("author1")).json()["records"][0]["id"]
        r = client.post(f"/api/publish/records/{rid}/backfill",
                        json={"target_url": "javascript:alert(1)"},
                        headers=auth("author1"))
        assert r.status_code == 422
        # empty backfill rejected too
        r2 = client.post(f"/api/publish/records/{rid}/backfill",
                         json={"target_url": "", "target_book_id": ""},
                         headers=auth("author1"))
        assert r2.status_code == 400

    def test_share_id_length_and_charset(self, client):
        import asyncio
        asyncio.run(_seed_novel())
        sid = client.post("/api/share", json={"novel_id": "test-book"},
                          headers=auth("a")).json()["id"]
        assert len(sid) == 8
        assert all(c.isalnum() or c in "-_" for c in sid)
