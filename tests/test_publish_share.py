"""Tests for requirement A (publish/export) and B (public share + register-read).

Run in jwt mode (the default) so anonymous vs. registered vs. owner can be
distinguished. Data is isolated to a tmp path per test.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from novel_creator.config import settings
from novel_creator.memory import registry as reg
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import create_invite_code


# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(reg, "REGISTRY_PATH", data_dir / "registry.json")
    monkeypatch.setattr(reg, "NOVELS_DIR", data_dir / "novels")
    monkeypatch.setattr(settings, "db_path", str(data_dir / "central.db"))
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    return data_dir


@pytest.fixture
def client(env):
    from novel_creator.web.app import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _login(client: TestClient, code: str) -> dict:
    r = client.post("/api/auth/login", json={"invite_code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _seed_invite(code: str):
    conn = await get_connection(settings.db_path)
    try:
        await create_invite_code(conn, code=code, max_uses=0)
    finally:
        await conn.close()


async def _build_novel(
    title: str, *, chapters: int = 12, owner: str = "OWNER1",
    empty: set[int] | None = None, gap_after: int | None = None,
    words: int = 600,
):
    """Create a registered novel with rendered chapter_texts."""
    info = reg.register_novel(title, "玄幻", owner_id=owner)
    conn = await get_connection(info.db_path)
    outline = {
        "title": title, "genre": "玄幻", "premise": "少年崛起",
        "central_conflict": "正邪", "setting": "九州", "chapters": [],
        "volumes": [{
            "volume_index": 0, "title": "卷一", "summary": "", "theme": "",
            "chapter_start": 0, "chapter_end": max(0, chapters - 1), "arc_goal": "",
        }],
    }
    await conn.execute(
        "INSERT INTO story_outline(id, outline_json) VALUES(1,?)",
        (json.dumps(outline, ensure_ascii=False),),
    )
    await conn.execute(
        "INSERT INTO volumes(volume_index,title,summary,theme,chapter_start,chapter_end,arc_goal)"
        " VALUES(0,'卷一','','',0,?, '')", (max(0, chapters - 1),),
    )
    empty = empty or set()
    indices = list(range(chapters))
    if gap_after is not None:
        indices = [i for i in indices if i != gap_after]
    for i in indices:
        body = "" if i in empty else ("天地玄黄宇宙洪荒。" * (words // 10 + 1))[:words]
        await conn.execute(
            "INSERT INTO chapter_texts(chapter_index,scene_index,title,content,pov_character,summary)"
            " VALUES(?,?,?,?,?,?)",
            (i, 0, f"标题{i}", body, "", ""),
        )
    await conn.commit()
    await conn.close()
    return info


# ══════════════════════════════════════════════════════════════════════════
# Requirement A — publish / export
# ══════════════════════════════════════════════════════════════════════════

class TestPublish:
    def test_preflight_and_export_bundle(self, client):
        import asyncio
        info = asyncio.run(_build_novel("导出测试书"))
        asyncio.run(_seed_invite("OWNER1"))
        h = _login(client, "OWNER1")

        r = client.post(f"/api/publish/preflight?platform=fanqie&novel_id={info.novel_id}", headers=h)
        assert r.status_code == 200
        v = r.json()
        assert v["ok"] is True
        assert v["stats"]["chapters"] == 12
        assert not v["errors"]

        r = client.post("/api/publish/export", json={"novel_id": info.novel_id, "platform": "bundle"}, headers=h)
        assert r.status_code == 200
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert any(n.endswith(".epub") for n in names)
        assert any("番茄" in n for n in names)
        # Fanqie TXT inside the bundle must be GB18030-decodable.
        fanqie = next(n for n in names if "番茄" in n)
        z.read(fanqie).decode("gb18030")

    def test_fanqie_gb18030_and_epub_valid(self, client):
        import asyncio
        info = asyncio.run(_build_novel("编码测试"))
        asyncio.run(_seed_invite("OWNER1"))
        h = _login(client, "OWNER1")

        r = client.post("/api/publish/export", json={"novel_id": info.novel_id, "platform": "fanqie"}, headers=h)
        assert r.status_code == 200
        text = r.content.decode("gb18030")
        assert "第1章" in text and "第12章" in text

        r = client.post("/api/publish/export", json={"novel_id": info.novel_id, "platform": "epub"}, headers=h)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        assert z.namelist()[0] == "mimetype"
        assert any(n.endswith(".opf") for n in z.namelist())

    def test_empty_chapter_blocks_export(self, client):
        import asyncio
        info = asyncio.run(_build_novel("断章书", chapters=6, empty={3}))
        asyncio.run(_seed_invite("OWNER1"))
        h = _login(client, "OWNER1")

        v = client.post(f"/api/publish/preflight?novel_id={info.novel_id}", headers=h).json()
        assert v["ok"] is False
        assert any(e["code"] == "empty_chapter" for e in v["errors"])

        r = client.post("/api/publish/export", json={"novel_id": info.novel_id, "platform": "txt"}, headers=h)
        assert r.status_code == 422

    def test_records_scoped_to_operator(self, client):
        import asyncio
        info = asyncio.run(_build_novel("记录书"))
        asyncio.run(_seed_invite("OWNER1"))
        asyncio.run(_seed_invite("READERX"))
        ho = _login(client, "OWNER1")
        hr = _login(client, "READERX")

        assert client.post("/api/publish/export", json={"novel_id": info.novel_id, "platform": "txt"}, headers=ho).status_code == 200
        # Non-owner cannot publish someone else's novel.
        r = client.post("/api/publish/preflight", json=None, params={"novel_id": info.novel_id}, headers=hr)
        assert r.status_code == 403
        # Reader's record list is empty; owner has one.
        assert len(client.get("/api/publish/records", headers=hr).json()["records"]) == 0
        assert len(client.get("/api/publish/records", headers=ho).json()["records"]) == 1

    def test_anonymous_cannot_publish(self, client):
        assert client.post("/api/publish/preflight").status_code == 401


# ══════════════════════════════════════════════════════════════════════════
# Requirement B — share + register-to-read
# ══════════════════════════════════════════════════════════════════════════

class TestShare:
    def _share(self, client, info, h, trial_value=3):
        r = client.post("/api/share", json={"novel_id": info.novel_id, "trial_value": trial_value}, headers=h)
        assert r.status_code == 200, r.text
        return r.json()["share"]["id"]

    def test_permission_matrix(self, client):
        import asyncio
        info = asyncio.run(_build_novel("权限矩阵书", chapters=12, owner="OWNER1"))
        asyncio.run(_seed_invite("OWNER1"))
        asyncio.run(_seed_invite("READER2"))
        h_owner = _login(client, "OWNER1")
        h_reader = _login(client, "READER2")
        sid = self._share(client, info, h_owner)

        # Anonymous metadata + TOC: only first 3 readable.
        r = client.get(f"/api/share/{sid}/chapters")
        assert r.status_code == 200
        readable = [c["chapter_index"] for c in r.json()["chapters"] if c["readable"]]
        assert readable == [0, 1, 2]

        # Boundary: 3rd chapter (idx 2) ok, 4th (idx 3) forbidden.
        assert client.get(f"/api/share/{sid}/chapter/2").status_code == 200
        r = client.get(f"/api/share/{sid}/chapter/3")
        assert r.status_code == 403
        body = r.json()["detail"]
        assert body["code"] == "need_login" and body["trial_ok"] is False
        # No body text leaks in the rejection.
        assert "天地玄黄" not in r.text

        # Registered reader gets the full book.
        r = client.get(f"/api/share/{sid}/chapter/11", headers=h_reader)
        assert r.status_code == 200 and "天地玄黄" in r.json()["text"]

        # Anonymous/non-owner management is blocked.
        assert client.post("/api/share", json={"novel_id": info.novel_id}).status_code == 401
        assert client.get("/api/shares/mine", headers=h_reader).status_code == 200
        assert client.patch(f"/api/share/{sid}", json={"status": "disabled"}, headers=h_reader).status_code == 403

    def test_legacy_fulltext_endpoint_no_longer_anonymous(self, client):
        import asyncio
        info = asyncio.run(_build_novel("封闭全书", owner="OWNER1"))
        asyncio.run(_seed_invite("OWNER1"))
        # The old public full-text endpoint must now require auth (no trial bypass).
        assert client.get(f"/api/novel-full?novel_id={info.novel_id}").status_code == 401
        assert client.get(f"/api/chapter-text/0?novel_id={info.novel_id}").status_code == 401

    def test_share_id_unguessable_and_disabled_404(self, client):
        import asyncio
        info = asyncio.run(_build_novel("关闭书"))
        asyncio.run(_seed_invite("OWNER1"))
        h = _login(client, "OWNER1")
        sid = self._share(client, info, h)
        assert len(sid) == 10 and sid.isalnum()

        # Unknown id and disabled id look identical (404).
        assert client.get("/api/share/zzZZZZ9999").status_code == 404
        assert client.patch(f"/api/share/{sid}", json={"status": "disabled"}, headers=h).status_code == 200
        assert client.get(f"/api/share/{sid}").status_code == 404
        assert client.get(f"/api/share/{sid}/chapter/0").status_code == 404

    def test_non_owner_cannot_share(self, client):
        import asyncio
        info = asyncio.run(_build_novel("他人之书", owner="OWNER1"))
        asyncio.run(_seed_invite("OWNER1"))
        asyncio.run(_seed_invite("EVILRDR"))
        h_evil = _login(client, "EVILRDR")
        r = client.post("/api/share", json={"novel_id": info.novel_id}, headers=h_evil)
        assert r.status_code == 403

    def test_rate_limit(self, client, monkeypatch):
        import asyncio
        from novel_creator.web.ratelimit import share_limiter
        info = asyncio.run(_build_novel("限流书"))
        asyncio.run(_seed_invite("OWNER1"))
        h = _login(client, "OWNER1")
        sid = self._share(client, info, h)

        share_limiter.max_requests = 5
        share_limiter._buckets.clear()
        statuses = [client.get(f"/api/share/{sid}").status_code for _ in range(8)]
        assert 429 in statuses
        share_limiter.max_requests = 60

    def test_word_count_trial_mode(self, client):
        import asyncio
        # trial window of ~500 chars; chapters are 600 chars each → only ch0.
        info = asyncio.run(_build_novel("字数试读", chapters=5, words=600))
        asyncio.run(_seed_invite("OWNER1"))
        h = _login(client, "OWNER1")
        r = client.post("/api/share", json={
            "novel_id": info.novel_id, "trial_mode": "word_count", "trial_value": 650,
        }, headers=h)
        sid = r.json()["share"]["id"]
        toc = client.get(f"/api/share/{sid}/chapters").json()["chapters"]
        flags = [c["readable"] for c in toc]
        assert flags[0] is True and flags[1] is False
