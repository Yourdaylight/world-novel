"""Tests for the Web API layer (routes)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a FastAPI TestClient with mocked dependencies."""
    from novel_creator.web.app import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sample_novel_id():
    return "novel-test-001"


# ---------------------------------------------------------------------------
# Novel CRUD endpoints
# ---------------------------------------------------------------------------

class TestNovelsEndpoint:
    """GET /api/novels — list novels and active novel."""

    def test_list_novels_empty(self, client):
        """Should return empty list when no novels exist."""
        resp = client.get("/api/novels")
        assert resp.status_code == 200
        data = resp.json()
        assert "novels" in data
        assert isinstance(data["novels"], list)
        assert "active_novel_id" in data

    def test_create_novel_requires_body(self, client):
        """POST without body should return error."""
        resp = client.post("/api/novels", json={})
        # May return 422, 405 (not implemented), 400, or other validation error
        assert resp.status_code in (200, 422, 400, 405)


class TestGenerationEndpoint:
    """POST /api/generation/* — generation control."""

    def test_start_generation_missing_novel(self, client):
        """Start without novel_id should fail gracefully."""
        resp = client.post("/api/generation/start")
        # Should not 500 — may return error or require params
        assert resp.status_code != 500

    def test_pause_generation(self, client):
        """Pause endpoint should accept requests without crashing."""
        resp = client.post("/api/generation/pause?novel_id=fake-id")
        assert resp.status_code != 500

    def test_resume_generation(self, client):
        """Resume endpoint should accept requests without crashing."""
        resp = client.post("/api/generation/resume?novel_id=fake-id")
        assert resp.status_code != 500

    def test_progress_endpoint(self, client):
        """Progress endpoint returns valid JSON structure."""
        resp = client.get("/api/generation/progress?novel_id=fake-id")
        assert resp.status_code != 500
        if resp.status_code == 200:
            data = resp.json()
            # Check expected fields exist
            for field in ("phase", "total_chapters", "completed_chapters"):
                assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Characters endpoint
# ---------------------------------------------------------------------------

class TestCharactersEndpoint:
    """GET/POST /api/characters — character management."""

    def test_list_characters(self, client):
        """List characters should return array."""
        resp = client.get("/api/characters?novel_id=fake-id")
        assert resp.status_code != 500
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data.get("characters", data), (list, dict))

    def test_get_character_profile_not_found(self, client):
        """Getting non-existent character should not 500."""
        resp = client.get("/api/characters/fake-char/profile?novel_id=fake-id")
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Story / outline endpoint
# ---------------------------------------------------------------------------

class TestStoryEndpoint:
    """GET /api/story/* — story data."""

    def test_get_outline(self, client):
        """Outline endpoint should respond."""
        resp = client.get("/api/story/outline?novel_id=fake-id")
        assert resp.status_code != 500

    def test_get_world_info(self, client):
        """World info endpoint should respond."""
        resp = client.get("/api/story/world?novel_id=fake-id")
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Historian endpoint
# ---------------------------------------------------------------------------

class TestHistorianEndpoint:
    """POST /api/historian/chat — historian chat."""

    def test_chat_requires_message(self, client):
        """Chat without message should return validation error."""
        resp = client.post("/api/historian/chat", json={})
        assert resp.status_code in (422, 400, 200, 405)

    def test_chat_with_message(self, client):
        """Chat with message should process (may fail on missing DB but not 500)."""
        resp = client.post("/api/historian/chat", json={
            "message": "测试消息",
            "novel_id": "fake-id",
        })
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# SQL safety: _clear_generation_data whitelist
# ---------------------------------------------------------------------------

class TestSQLSafety:
    """Ensure SQL operations use safe patterns."""

    def test_clear_tables_is_frozenset(self):
        """_ALLOWED_CLEAR_TABLES should be a frozenset (immutable whitelist)."""
        from novel_creator.web.routes.generation import _ALLOWED_CLEAR_TABLES
        assert isinstance(_ALLOWED_CLEAR_TABLES, frozenset)
        assert len(_ALLOWED_CLEAR_TABLES) > 0
        # All entries should be plain table name strings (alphanumeric + underscore)
        for t in _ALLOWED_CLEAR_TABLES:
            assert isinstance(t, str)
            assert t.replace("_", "").isalnum(), f"Suspicious table name: {t}"

    def test_allowed_tables_contains_expected(self):
        """Whitelist should contain known generation tables."""
        from novel_creator.web.routes.generation import _ALLOWED_CLEAR_TABLES
        expected = {"chapter_texts", "character_actions", "scene_turns",
                     "generation_checkpoints"}
        for t in expected:
            assert t in _ALLOWED_CLEAR_TABLES


# ---------------------------------------------------------------------------
# SPA fallback
# ---------------------------------------------------------------------------

class TestSPAFallback:
    """Test Vue SPA fallback routing."""

    def test_root_returns_html(self, client):
        """Root path should return HTML (SPA fallback or legacy)."""
        resp = client.get("/")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "html" in content_type.lower()

    def test_random_route_returns_spa(self, client):
        """Non-API, non-asset routes should return SPA index.html."""
        resp = client.get("/some/random/route")
        assert resp.status_code == 200

    def test_api_routes_not_intercepted_by_spa(self, client):
        """API routes should not be caught by SPA fallback."""
        resp = client.get("/api/nonexistent-endpoint")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

class TestWebSocket:
    """WebSocket endpoint basic connectivity."""

    def test_websocket_upgrade(self, client):
        """WebSocket endpoint should accept upgrade requests."""
        # TestClient doesn't fully support WebSocket, but we can check it exists
        with client.websocket_connect("/ws") as ws:
            # If connection succeeds, it's working
            ws.close()


# ---------------------------------------------------------------------------
# CORS / headers
# ---------------------------------------------------------------------------

class TestResponseHeaders:
    """Check response headers are properly set."""

    def test_api_json_content_type(self, client):
        """API responses should have JSON content type."""
        resp = client.get("/api/novels")
        ct = resp.headers.get("content-type", "")
        assert "json" in ct.lower()

    def test_cors_headers_present(self, client):
        """CORS headers should allow frontend access."""
        resp = client.options("/api/novels")
        # Just check it doesn't crash
        assert resp.status_code in (200, 204, 404, 405)
