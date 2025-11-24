"""Unit tests for the MCP Bible tool handlers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.mcp.models import MCPContext
from app.utils.exceptions import ValidationError


@pytest.fixture
def bible_tools_module():
    import importlib

    module = importlib.import_module("app.mcp.tools.bible_tools")
    return module


def test_handle_get_passage_returns_data(bible_tools_module):
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_passage.return_value = [{"reference": "John 3:16"}]
        mock_get_service.return_value = service

        result = bible_tools_module._handle_get_passage(
            {"book": "John", "chapter": 3, "start_verse": 16, "end_verse": 17},
            MCPContext(),
        )
        assert result[0]["reference"] == "John 3:16"
        service.get_passage.assert_called_once()


def test_handle_get_chapter_missing_args_raises(bible_tools_module):
    with pytest.raises(ValidationError):
        bible_tools_module._handle_get_chapter({}, MCPContext())


def test_handle_get_verse_not_found(bible_tools_module):
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_verse.return_value = None
        mock_get_service.return_value = service

        with pytest.raises(ValidationError):
            bible_tools_module._handle_get_verse({"book": "John", "chapter": 3}, MCPContext())


def test_handle_get_verse_returns_payload(bible_tools_module):
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_verse.return_value = {"reference": "John 3:16"}
        mock_get_service.return_value = service

        result = bible_tools_module._handle_get_verse({"book": "John", "chapter": 3, "verse": 16}, MCPContext())

        assert result["reference"] == "John 3:16"


def test_handle_get_passage_not_found(bible_tools_module):
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_passage.return_value = None
        mock_get_service.return_value = service

        with pytest.raises(ValidationError):
            bible_tools_module._handle_get_passage(
                {"book": "John", "chapter": 3, "start_verse": 1, "end_verse": 2},
                MCPContext(),
            )


def test_handle_get_chapter_not_found(bible_tools_module):
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_chapter.return_value = None
        mock_get_service.return_value = service

        with pytest.raises(ValidationError):
            bible_tools_module._handle_get_chapter({"book": "John", "chapter": 3}, MCPContext())


def test_handle_get_chapter_returns_data(bible_tools_module):
    with patch("app.mcp.tools.bible_tools.get_bible_service") as mock_get_service:
        service = MagicMock()
        service.get_chapter.return_value = {"book": "John", "chapter": 3}
        mock_get_service.return_value = service

        result = bible_tools_module._handle_get_chapter({"book": "John", "chapter": 3}, MCPContext())

        assert result["chapter"] == 3
