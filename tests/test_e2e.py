"""End-to-end tests — full world lifecycle via FastAPI TestClient.

These tests exercise the real API endpoints with a real SQLite database
(in a temp directory), verifying that:
  1. World creation writes actual data to DB
  2. Novels appear in the list after creation
  3. Status, propositions, and other queries work
  4. Cleanup (delete) works

No LLM calls are made (generation is not started).
Run with: uv run pytest tests/test_e2e.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_data(tmp_path, monkeypatch):
    """Redirect all data to a temp directory so tests don't pollute real data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Redirect registry and novels dir to temp
    import novel_creator.memory.registry as registry_mod
    monkeypatch.setattr(registry_mod, "REGISTRY_PATH", data_dir / "registry.json")
    monkeypatch.setattr(registry_mod, "NOVELS_DIR", data_dir / "novels")

    # Redirect default DB path
    monkeypatch.setenv("NOVEL_DB_PATH", str(data_dir / "novel.db"))


@pytest.fixture
def client():
    """Fresh TestClient for each test."""
    from novel_creator.web.app import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# World creation lifecycle
# ---------------------------------------------------------------------------

class TestWorldLifecycle:
    """Full lifecycle: create → list → status → propositions → delete."""

    def test_create_world_returns_novel_id(self, client):
        """POST /api/worlds/create should return ok=True and a novel_id."""
        resp = client.post("/api/worlds/create", json={
            "title": "测试武侠世界",
            "genre": "武侠",
            "propositions": {
                "what_is": "一个修仙的世界",
                "where_from": "远古大战后的废墟",
                "where_to": "新的纪元"
            },
            "num_chapters": 5,
            "num_characters": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "novel_id" in data
        assert "db_path" in data
        # DB file should exist
        assert Path(data["db_path"]).exists()

    def test_create_and_list_world(self, client):
        """Created world should appear in the novels list."""
        # Create
        create_resp = client.post("/api/worlds/create", json={
            "title": "列表测试世界",
            "genre": "科幻",
            "num_chapters": 3,
        })
        assert create_resp.json()["ok"] is True
        novel_id = create_resp.json()["novel_id"]

        # List
        list_resp = client.get("/api/novels")
        assert list_resp.status_code == 200
        novels = list_resp.json()["novels"]
        ids = [n["novel_id"] for n in novels]
        assert novel_id in ids

    def test_create_and_select_world(self, client):
        """Can select the created world as active."""
        create_resp = client.post("/api/worlds/create", json={
            "title": "选择测试",
            "genre": "武侠",
            "num_chapters": 3,
        })
        novel_id = create_resp.json()["novel_id"]

        select_resp = client.post("/api/novels/select", json={"novel_id": novel_id})
        assert select_resp.status_code == 200
        assert select_resp.json()["ok"] is True

        active_resp = client.get("/api/novels/active")
        assert active_resp.status_code == 200
        assert active_resp.json()["active"]["novel_id"] == novel_id

    def test_world_status(self, client):
        """GET /api/worlds/{id}/status should return valid structure."""
        create_resp = client.post("/api/worlds/create", json={
            "title": "状态测试",
            "genre": "武侠",
            "num_chapters": 3,
        })
        novel_id = create_resp.json()["novel_id"]

        status_resp = client.get(f"/api/worlds/{novel_id}/status", params={"novel_id": novel_id})
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["novel_id"] == novel_id
        assert "is_running" in data
        assert "chapters_completed" in data

    def test_propositions_saved(self, client):
        """Propositions should be persisted in DB and retrievable."""
        create_resp = client.post("/api/worlds/create", json={
            "title": "命题测试",
            "genre": "仙侠",
            "propositions": {
                "what_is": "一个修真世界",
                "where_from": "太古时代",
                "where_to": "飞升大限"
            },
            "num_chapters": 10,
        })
        novel_id = create_resp.json()["novel_id"]

        prop_resp = client.get(f"/api/worlds/{novel_id}/propositions", params={"novel_id": novel_id})
        assert prop_resp.status_code == 200
        data = prop_resp.json()
        assert data["what_is"] == "一个修真世界"
        assert data["where_from"] == "太古时代"
        assert data["where_to"] == "飞升大限"

    def test_delete_world(self, client):
        """DELETE should remove the world from the list."""
        create_resp = client.post("/api/worlds/create", json={
            "title": "删除测试",
            "genre": "奇幻",
            "num_chapters": 1,
        })
        novel_id = create_resp.json()["novel_id"]

        # Verify it exists
        list_resp1 = client.get("/api/novels")
        ids_before = [n["novel_id"] for n in list_resp1.json()["novels"]]
        assert novel_id in ids_before

        # Delete
        del_resp = client.delete(f"/api/worlds/{novel_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True

        # Verify it's gone
        list_resp2 = client.get("/api/novels")
        ids_after = [n["novel_id"] for n in list_resp2.json()["novels"]]
        assert novel_id not in ids_after

    def test_create_multiple_worlds(self, client):
        """Multiple worlds should coexist independently."""
        ids = []
        for i in range(3):
            resp = client.post("/api/worlds/create", json={
                "title": f"多世界测试{i}",
                "genre": "武侠",
                "num_chapters": 2,
            })
            assert resp.json()["ok"] is True
            ids.append(resp.json()["novel_id"])

        list_resp = client.get("/api/novels")
        listed_ids = [n["novel_id"] for n in list_resp.json()["novels"]]
        for nid in ids:
            assert nid in listed_ids


# ---------------------------------------------------------------------------
# Story data endpoints (empty world)
# ---------------------------------------------------------------------------

class TestStoryEndpointsEmpty:
    """Story data queries should return empty but valid structures for new worlds."""

    @pytest.fixture
    def novel_id(self, client):
        resp = client.post("/api/worlds/create", json={
            "title": "空数据测试",
            "genre": "武侠",
            "num_chapters": 3,
        })
        nid = resp.json()["novel_id"]
        client.post("/api/novels/select", json={"novel_id": nid})
        return nid

    def test_story_returns_empty_characters(self, client, novel_id):
        resp = client.get("/api/story", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["characters"] == []

    def test_relationships_returns_empty(self, client, novel_id):
        resp = client.get("/api/relationships", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["edges"] == []

    def test_chapters_returns_empty(self, client, novel_id):
        resp = client.get("/api/chapters", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["chapters"] == []

    def test_outline_returns_none(self, client, novel_id):
        resp = client.get("/api/outline", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["outline"] is None

    def test_world_returns_none(self, client, novel_id):
        resp = client.get("/api/world", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["world"] is None

    def test_foreshadows_returns_empty(self, client, novel_id):
        resp = client.get("/api/foreshadows", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["foreshadows"] == []

    def test_timeline_returns_empty(self, client, novel_id):
        resp = client.get("/api/timeline", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["eras"] == []
        assert resp.json()["events"] == []

    def test_progress_returns_idle(self, client, novel_id):
        resp = client.get("/api/progress", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["phase"] == "idle"

    def test_token_stats_returns_zero(self, client, novel_id):
        resp = client.get("/api/token-stats", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["total"]["total_tokens"] == 0


# ---------------------------------------------------------------------------
# Generation control (no LLM — just test API contract)
# ---------------------------------------------------------------------------

class TestGenerationControl:
    """Test generation endpoints respond correctly without actual LLM calls."""

    @pytest.fixture
    def novel_id(self, client):
        resp = client.post("/api/worlds/create", json={
            "title": "生成控制测试",
            "genre": "武侠",
            "propositions": {"what_is": "测试", "where_from": "测试", "where_to": "测试"},
            "num_chapters": 3,
        })
        return resp.json()["novel_id"]

    def test_pause_no_running_task(self, client, novel_id):
        resp = client.post(f"/api/worlds/{novel_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_generation_error_empty(self, client, novel_id):
        resp = client.get(f"/api/worlds/{novel_id}/generation-error")
        assert resp.status_code == 200
        assert resp.json()["error"] is None

    def test_simulation_progress_empty(self, client, novel_id):
        resp = client.get(f"/api/worlds/{novel_id}/simulation-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["completed"] == 0

    def test_simulation_beats_empty(self, client, novel_id):
        resp = client.get(f"/api/worlds/{novel_id}/simulation-beats")
        assert resp.status_code == 200
        assert resp.json()["beats"] == []

    def test_generate_missing_novel(self, client):
        resp = client.post("/api/worlds/nonexistent-id/generate", json={"mode": "full"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is False


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

class TestExportEndpoints:
    @pytest.fixture
    def novel_id(self, client):
        resp = client.post("/api/worlds/create", json={
            "title": "导出测试",
            "genre": "武侠",
            "num_chapters": 1,
        })
        return resp.json()["novel_id"]

    def test_export_markdown_empty(self, client, novel_id):
        resp = client.get(f"/api/worlds/{novel_id}/export/markdown")
        # Should return 404 (no chapters) or valid response
        assert resp.status_code in (200, 404)

    def test_export_json_structure(self, client, novel_id):
        resp = client.get(f"/api/worlds/{novel_id}/export/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == novel_id
        assert "characters" in data
        assert "propositions" in data

    def test_novel_full_empty(self, client, novel_id):
        client.post("/api/novels/select", json={"novel_id": novel_id})
        resp = client.get("/api/novel-full", params={"novel_id": novel_id})
        assert resp.status_code == 200
        assert resp.json()["word_count"] == 0


# ---------------------------------------------------------------------------
# SPA and WebSocket
# ---------------------------------------------------------------------------

class TestSPAAndWS:
    def test_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "html" in resp.headers.get("content-type", "").lower()

    def test_api_404(self, client):
        resp = client.get("/api/nonexistent-route-xyz")
        assert resp.status_code == 404

    def test_websocket_connects(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.close()
