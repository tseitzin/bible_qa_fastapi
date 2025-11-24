"""Tests for the MCP router endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user_optional
from app.config import Settings, get_settings

client = TestClient(app)


@pytest.fixture
def authenticated_user():
    app.dependency_overrides[get_current_user_optional] = lambda: {"id": 1}
    yield
    app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def mcp_key_required():
    app.dependency_overrides[get_settings] = lambda: Settings(mcp_api_key="secret")
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture(autouse=True)
def mock_bible_service():
    """Patch the Bible service used by MCP tools so tests avoid the database."""
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_verse.return_value = {
            "reference": "John 3:16",
            "book": "John",
            "chapter": 3,
            "verse": 16,
            "text": "For God so loved the world...",
        }
        service.get_passage.return_value = [service.get_verse.return_value]
        service.get_chapter.return_value = {
            "book": "John",
            "chapter": 3,
            "verses": [
                {"verse": 16, "text": "For God so loved the world..."},
            ],
        }
        service.search_verses.return_value = [service.get_verse.return_value]
        mock_get_service.return_value = service
        yield service


def test_list_tools_returns_phase_one_tools():
    response = client.get("/api/mcp/tools")
    assert response.status_code == 200
    data = response.json()
    tool_names = {tool["name"] for tool in data["tools"]}
    assert {"get_verse", "get_passage", "get_chapter", "search_verses"}.issubset(tool_names)


def test_invoke_get_verse_tool(mock_bible_service: MagicMock):
    payload = {
        "tool": "get_verse",
        "arguments": {"book": "John", "chapter": 3, "verse": 16},
    }
    response = client.post("/api/mcp/call", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["result"]["reference"] == "John 3:16"
    mock_bible_service.get_verse.assert_called_once()


def test_invoke_unknown_tool_returns_404():
    response = client.post("/api/mcp/call", json={"tool": "missing", "arguments": {}})
    assert response.status_code == 404


def test_validation_error_bubbles_up(mock_bible_service: MagicMock):
    mock_bible_service.get_chapter.return_value = None
    response = client.post(
        "/api/mcp/call",
        json={"tool": "get_chapter", "arguments": {"book": "John", "chapter": 99}},
    )
    assert response.status_code == 400
    assert "Chapter not found" in response.json()["detail"]


def test_search_tool_passes_limit_override(mock_bible_service: MagicMock):
    response = client.post(
        "/api/mcp/call",
        json={"tool": "search_verses", "arguments": {"keyword": "love", "limit": 5}},
    )
    assert response.status_code == 200
    mock_bible_service.search_verses.assert_called_once_with(keyword="love", limit=5)


def test_user_tool_requires_authentication():
    response = client.post(
        "/api/mcp/call", json={"tool": "get_saved_answers", "arguments": {}},
    )
    assert response.status_code == 400
    assert "Authentication required" in response.json()["detail"]


@patch("app.mcp.tools.user_tools.SavedAnswersRepository.get_user_saved_answers", return_value=[{"id": 1}])
def test_get_saved_answers_tool_returns_payload(mock_repo, authenticated_user):
    response = client.post(
        "/api/mcp/call",
        json={"tool": "get_saved_answers", "arguments": {"limit": 5}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["total"] == 1
    mock_repo.assert_called_once_with(user_id=1, limit=5)


def test_mcp_authorization_accepts_valid_key(mcp_key_required):
    response = client.get("/api/mcp/tools", headers={"x-mcp-api-key": "secret"})
    assert response.status_code == 200


def test_mcp_authorization_rejects_missing_key(mcp_key_required):
    response = client.get("/api/mcp/tools")
    assert response.status_code == 401
