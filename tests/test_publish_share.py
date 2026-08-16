"""Tests for requirement A (publishing/export) and B (share/register-read).

Covers:
- A: preflight quality gate, platform export (TXT GB18030 / EPUB / ZIP), records
- B: permission matrix (anonymous / registered / author), trial boundary,
     disabled share, ID enumeration, rate limiting, response body never leaks
     hidden chapter text, invite-code login → full-text chain.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_creator.config import settings
from novel_creator.memory import registry as registry_mod
from novel_creator.memory.database import get_connection
from novel_creator.sharing.ratelimit import share_rate_limiter
from novel_creator.web.auth_deps import create_access_token


# ---------------------------------------------------------------------------
# Fixtures — isolated tmp workspace: registry.json + one novel DB + global DB
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    novels_dir = tmp_path / "novels"
    novels_dir.mkdir()
    monkeypatch.setattr(registry_mod, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(registry_mod, "NOVELS_DIR", novels_dir)
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "global.db"))
    return tmp_path


async def _make_novel(
    workspace: Path,
    novel_id: str = "demo-novel",
    title: str = "测试成书",
    chapter_count: int = 10,
    *,
    missing: set[int] | None = None,
    empty: set[int] | None = None,
    short: set[int] | None = None,
    planned: int | None = None,
    with_volumes: bool = True,
):
    """Create a registered novel with rendered chapters."""
    missing = missing or set()
    empty = empty or set()
    short = short or set()

    novel_dir = workspace / "novels" / novel_id
    novel_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(novel_dir / "novel.db")

    conn = await get_connection(db_path)
    outline = {
        "title": title,
        "genre": "玄幻",
        "premise": "一个由多 Agent 演化生成的世界。",
        "synopsis": "这是一部用于发布测试的小说，简介完整。",
        "chapters": [{"index": i} for i in range(planned or chapter_count)],
    }
    await conn.execute(
        "INSERT INTO story_outline (id, outline_json) VALUES (1, ?)",
        (json.dumps(outline, ensure_ascii=False),),
    )
    if with_volumes:
        await conn.execute(
            "INSERT INTO volumes (volume_index, title, chapter_start, chapter_end) "
            "VALUES (0, '初入江湖', 0, ?)",
            (chapter_count - 1,),
        )
    for i in range(chapter_count):
        if i in missing:
            continue
        if i in empty:
            text = "   "
        elif i in short:
            text = "短章。"
        else:
            para = f"这是第{i + 1}章的正文内容，情节跌宕起伏，角色对话精彩。" * 30
            text = para
        await conn.execute(
            "INSERT INTO chapter_texts (chapter_index, scene_index, title, content) "
            "VALUES (?, 0, ?, ?)",
            (i, f"章节{i + 1}", text),
        )
    await conn.commit()
    await conn.close()

    info = registry_mod.NovelInfo(
        novel_id=novel_id,
        title=title,
        genre="玄幻",
        db_path=db_path,
        status="completed",
        chapters_completed=chapter_count,
        chapters_total=planned or chapter_count,
        word_count=12345,
    )
    reg = registry_mod.NovelRegistry(novels=[info], active_novel_id=novel_id)
    registry_mod.save_registry(reg)
    return info


@pytest.fixture
def client(workspace):
    # rate limiter is a process-wide singleton — isolate tests
    share_rate_limiter.reset()
    from novel_creator.web.app import app
    return TestClient(app, raise_server_exceptions=False)


def auth_headers(code: str = "author1") -> dict:
    token = create_access_token(code=code, is_admin=False)
    return {"X-User-Token": token}


# ═══════════════════════════════════════════════════════════════════════
# 需求 A — 成书发布
# ═══════════════════════════════════════════════════════════════════════

class TestPublishing:
    @pytest.mark.asyncio
    async def test_platforms_list(self, client, workspace):
        await _make_novel(workspace)
        resp = client.get("/api/publish/platforms", headers=auth_headers())
        assert resp.status_code == 200
        keys = {p["key"] for p in resp.json()["platforms"]}
        assert {"fanqie", "qimao", "txt", "epub"} <= keys

    @pytest.mark.asyncio
    async def test_preflight_flags_missing_and_empty(self, client, workspace):
        await _make_novel(
            workspace, chapter_count=5, missing={2, 4}, empty={3}, planned=5
        )
        resp = client.post(
            "/api/publish/preflight",
            json={"novel_id": "demo-novel", "platform": "fanqie"},
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        joined = " ".join(data["errors"])
        assert "断章" in joined and "空章节" in joined

    @pytest.mark.asyncio
    async def test_preflight_rejects_unknown_novel(self, client, workspace):
        resp = client.post(
            "/api/publish/preflight",
            json={"novel_id": "ghost"},
            headers=auth_headers(),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_requires_auth(self, client, workspace):
        await _make_novel(workspace)
        resp = client.post(
            "/api/publish/export", json={"novel_id": "demo-novel", "platform": "txt"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_export_fanqie_txt_gb18030(self, client, workspace):
        """E2E: ≥10 章成书导出番茄 TXT，GB18030 可解码、章节完整。"""
        await _make_novel(workspace, chapter_count=10)
        resp = client.post(
            "/api/publish/export",
            json={"novel_id": "demo-novel", "platform": "fanqie"},
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        assert "gb18030" in resp.headers["content-type"]  # 声明真实编码
        text = resp.content.decode("gb18030")
        for i in range(1, 11):
            assert f"第{i}章" in text
        assert "测试成书" in text
        assert resp.headers["X-Publish-Record-Id"].startswith("pub_")

    @pytest.mark.asyncio
    async def test_export_epub_is_valid_zip(self, client, workspace):
        await _make_novel(workspace, chapter_count=10)
        resp = client.post(
            "/api/publish/export",
            json={"novel_id": "demo-novel", "platform": "epub"},
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/epub+zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        # mimetype must be the first stored entry
        assert zf.infolist()[0].filename == "mimetype"
        assert zf.read("mimetype") == b"application/epub+zip"
        names = zf.namelist()
        assert "OEBPS/content.opf" in names
        assert "OEBPS/nav.xhtml" in names
        opf = zf.read("OEBPS/content.opf").decode("utf-8")
        assert opf.count("chap-") >= 10

    @pytest.mark.asyncio
    async def test_export_qimao_zip_volumes(self, client, workspace):
        await _make_novel(workspace, chapter_count=6, with_volumes=True)
        resp = client.post(
            "/api/publish/export",
            json={"novel_id": "demo-novel", "platform": "qimao"},
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert "简介.txt" in names
        assert "cover.svg" in names
        assert any(n.endswith(".txt") and "简介" not in n for n in names)
        zf.read("简介.txt").decode("gb18030")  # GB18030 可解码

    @pytest.mark.asyncio
    async def test_qimao_zip_keeps_chapters_outside_volumes(self, client, workspace):
        """卷范围未覆盖的章节必须进入「未分卷章节.txt」，不得静默丢失。"""
        info = await _make_novel(
            workspace, chapter_count=6, with_volumes=False
        )
        # 只覆盖前 3 章的分卷
        conn = await get_connection(info.db_path)
        await conn.execute(
            "INSERT INTO volumes (volume_index, title, chapter_start, chapter_end) "
            "VALUES (0, '卷一', 0, 2)"
        )
        await conn.commit()
        await conn.close()

        resp = client.post(
            "/api/publish/export",
            json={"novel_id": "demo-novel", "platform": "qimao"},
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        assert "未分卷章节.txt" in zf.namelist()
        leftover = zf.read("未分卷章节.txt").decode("gb18030")
        assert "第4章" in leftover and "第6章" in leftover

    @pytest.mark.asyncio
    async def test_export_blocked_when_preflight_fails(self, client, workspace):
        await _make_novel(workspace, chapter_count=3, missing={2}, planned=3)
        resp = client.post(
            "/api/publish/export",
            json={"novel_id": "demo-novel", "platform": "txt"},
            headers=auth_headers(),
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_records_and_backfill(self, client, workspace):
        await _make_novel(workspace, chapter_count=4)
        client.post(
            "/api/publish/export",
            json={"novel_id": "demo-novel", "platform": "txt"},
            headers=auth_headers(),
        )
        listing = client.get(
            "/api/publish/records?novel_id=demo-novel", headers=auth_headers()
        ).json()
        assert len(listing["records"]) == 1
        record_id = listing["records"][0]["id"]

        patched = client.patch(
            f"/api/publish/records/{record_id}",
            json={"target_url": "https://fanqienovel.com/page/123", "stage": "published"},
            headers=auth_headers(),
        )
        assert patched.status_code == 200
        assert patched.json()["stage"] == "published"
        assert patched.json()["target_url"].endswith("123")


# ═══════════════════════════════════════════════════════════════════════
# 需求 B — 公开分享 + 注册阅读
# ═══════════════════════════════════════════════════════════════════════

class TestSharePermissionMatrix:
    @pytest.mark.asyncio
    async def _create_share(self, client, workspace, trial_value=3, code="author1"):
        await _make_novel(workspace, chapter_count=6)
        resp = client.post(
            "/api/share",
            json={
                "novel_id": "demo-novel",
                "trial_mode": "first_n_chapters",
                "trial_value": trial_value,
            },
            headers=auth_headers(code),
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_anonymous_metadata_and_catalog(self, client, workspace):
        share_id = await self._create_share(client, workspace)
        meta = client.get(f"/api/share/{share_id}")
        assert meta.status_code == 200
        body = meta.json()
        assert body["access"]["level"] == "anonymous"
        assert body["title"] == "测试成书"

        catalog = client.get(f"/api/share/{share_id}/chapters").json()
        assert catalog["trial_chapter_count"] == 3
        flags = [c["readable"] for c in catalog["chapters"]]
        assert flags == [True, True, True, False, False, False]
        # 目录响应绝不能包含隐藏章节正文
        raw = json.dumps(catalog, ensure_ascii=False)
        assert "跌宕起伏" not in raw

    @pytest.mark.asyncio
    async def test_trial_boundary_chapter_n_and_n_plus_1(self, client, workspace):
        """试读恰好第 N 章边界：第 N 章可读、N+1 需注册。"""
        share_id = await self._create_share(client, workspace, trial_value=3)
        assert client.get(f"/api/share/{share_id}/chapter/2").status_code == 200
        denied = client.get(f"/api/share/{share_id}/chapter/3")
        assert denied.status_code == 403
        payload = denied.json()
        assert payload["code"] == "need_login"
        assert payload["trial_ok"] is False
        assert "content" not in payload

    @pytest.mark.asyncio
    async def test_registered_user_reads_full_and_bookshelf(self, client, workspace):
        share_id = await self._create_share(client, workspace)
        headers = auth_headers("reader1")
        ok = client.get(f"/api/share/{share_id}/chapter/5", headers=headers)
        assert ok.status_code == 200
        assert "content" in ok.json()

        shelf = client.get("/api/bookshelf", headers=headers).json()
        assert len(shelf["books"]) == 1
        assert shelf["books"][0]["chapter_index"] == 5

    @pytest.mark.asyncio
    async def test_author_level(self, client, workspace):
        share_id = await self._create_share(client, workspace, code="author1")
        meta = client.get(
            f"/api/share/{share_id}", headers=auth_headers("author1")
        ).json()
        assert meta["access"]["level"] == "author"
        assert meta["access"]["is_owner"] is True

    @pytest.mark.asyncio
    async def test_disabled_share_returns_404_everywhere(self, client, workspace):
        share_id = await self._create_share(client, workspace)
        patched = client.patch(
            f"/api/share/{share_id}",
            json={"status": "disabled"},
            headers=auth_headers("author1"),
        )
        assert patched.status_code == 200
        assert client.get(f"/api/share/{share_id}").status_code == 404
        assert client.get(f"/api/share/{share_id}/chapters").status_code == 404
        assert client.get(f"/api/share/{share_id}/chapter/0").status_code == 404

    @pytest.mark.asyncio
    async def test_non_owner_cannot_manage(self, client, workspace):
        share_id = await self._create_share(client, workspace, code="author1")
        resp = client.patch(
            f"/api/share/{share_id}",
            json={"trial_value": 99},
            headers=auth_headers("intruder"),
        )
        assert resp.status_code == 404  # 不存在或无权 —— 不泄露存在性

    @pytest.mark.asyncio
    async def test_share_id_not_enumerable(self, client, workspace):
        """1000 次随机 ID 尝试：全部 404，无越权数据返回。"""
        share_id = await self._create_share(client, workspace)
        import secrets
        # 1000 次随机 ID 尝试（分批重置应用层限流，模拟真实遍历的判定）
        for attempt in range(1000):
            if attempt % 55 == 0:
                share_rate_limiter.reset()
            guess = secrets.token_urlsafe(9)
            if guess == share_id:
                continue
            resp = client.get(f"/api/share/{guess}")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rate_limit_429(self, client, workspace):
        """单 IP 每分钟 ≤ 60 次：第 61 次返回 429。"""
        share_id = await self._create_share(client, workspace)
        for _ in range(60):
            assert client.get(f"/api/share/{share_id}").status_code == 200
        assert client.get(f"/api/share/{share_id}").status_code == 429

    @pytest.mark.asyncio
    async def test_mine_listing_not_shadowed(self, client, workspace):
        """GET /share/mine 绝不能被 GET /share/{share_id} 路由遮蔽。"""
        await self._create_share(client, workspace)
        resp = client.get("/api/share/mine", headers=auth_headers("author1"))
        assert resp.status_code == 200
        shares = resp.json()["shares"]
        assert len(shares) == 1
        assert shares[0]["owner_id"] == "author1"

    @pytest.mark.asyncio
    async def test_word_count_zero_means_no_trial(self, client, workspace):
        """word_count 模式 value=0 表示关闭试读：任何章节都不下发。"""
        await _make_novel(workspace, chapter_count=4)
        share_id = client.post(
            "/api/share",
            json={"novel_id": "demo-novel", "trial_mode": "word_count", "trial_value": 0},
            headers=auth_headers(),
        ).json()["id"]
        catalog = client.get(f"/api/share/{share_id}/chapters").json()
        assert catalog["trial_chapter_count"] == 0
        assert all(c["readable"] is False for c in catalog["chapters"])
        assert client.get(f"/api/share/{share_id}/chapter/0").status_code == 403

    @pytest.mark.asyncio
    async def test_disabled_auth_mode_treats_visitor_as_anonymous(self, client, workspace, monkeypatch):
        """disabled 模式下公开分享接口仍按匿名处理，不给全书。"""
        share_id = await self._create_share(client, workspace, trial_value=2)
        monkeypatch.setattr(settings, "auth_mode", "disabled")
        resp = client.get(f"/api/share/{share_id}/chapter/3")
        assert resp.status_code == 403
        catalog = client.get(f"/api/share/{share_id}/chapters").json()
        assert catalog["authenticated"] is False

    @pytest.mark.asyncio
    async def test_spoofed_xff_cannot_bypass_rate_limit(self, client, workspace):
        """直连非受信代理时，伪造 X-Forwarded-For 不能换 key 绕过限流。"""
        share_id = await self._create_share(client, workspace)
        codes = []
        for i in range(65):
            codes.append(
                client.get(
                    f"/api/share/{share_id}",
                    headers={"X-Forwarded-For": f"10.0.{i // 256}.{i % 256}"},
                ).status_code
            )
        assert codes.count(200) == 60
        assert 429 in codes

    @pytest.mark.asyncio
    async def test_word_count_trial_mode(self, client, workspace):
        await _make_novel(workspace, chapter_count=6)
        share_id = client.post(
            "/api/share",
            json={"novel_id": "demo-novel", "trial_mode": "word_count", "trial_value": 100},
            headers=auth_headers(),
        ).json()["id"]
        catalog = client.get(f"/api/share/{share_id}/chapters").json()
        assert catalog["trial_chapter_count"] >= 1
        assert catalog["chapters"][0]["readable"] is True


class TestInviteCodeLoginChain:
    """B-4/B-5: 邀请码注册/登录 → JWT → 全文可读。"""

    @pytest.mark.asyncio
    async def test_invite_code_login_unlocks_full_text(self, client, workspace):
        await _make_novel(workspace, chapter_count=4)
        # 管理员签发邀请码
        conn = await get_connection(settings.db_path)
        await conn.execute(
            "INSERT INTO invite_codes (code, is_active, max_uses) VALUES (?, 1, 0)",
            ("reader888",),
        )
        await conn.commit()
        await conn.close()

        login = client.post(
            "/api/auth/login", json={"invite_code": "reader888"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"X-User-Token": token}

        share = client.post(
            "/api/share",
            json={"novel_id": "demo-novel", "trial_value": 1},
            headers=auth_headers("author1"),
        ).json()
        share_id = share["id"]

        # 匿名：第 2 章 403
        assert client.get(f"/api/share/{share_id}/chapter/1").status_code == 403
        # 注册用户：全文
        ok = client.get(f"/api/share/{share_id}/chapter/3", headers=headers)
        assert ok.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_invite_code_rejected(self, client, workspace):
        resp = client.post("/api/auth/login", json={"invite_code": "nope"})
        assert resp.status_code == 401
