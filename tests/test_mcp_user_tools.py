"""Unit tests for MCP user data tool handlers."""
from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

from app.mcp.models import MCPContext
from app.utils.exceptions import ValidationError


@pytest.fixture
def user_tools_module():
    return importlib.import_module("app.mcp.tools.user_tools")


@patch("app.mcp.tools.user_tools.SavedAnswersRepository.get_user_saved_answers")
@patch("app.mcp.tools.user_tools.SavedAnswersRepository.save_answer")
def test_handle_save_answer_returns_latest(mock_save, mock_get, user_tools_module):
    mock_get.return_value = [{"id": 9, "question_id": 3, "tags": ["Faith"]}]
    ctx = MCPContext(user={"id": 2})

    result = user_tools_module._handle_save_answer({"question_id": 3, "tags": ["Faith "]}, ctx)

    mock_save.assert_called_once_with(user_id=2, question_id=3, tags=["Faith"])
    assert result["id"] == 9


def test_handle_save_answer_requires_auth(user_tools_module):
    with pytest.raises(ValidationError):
        user_tools_module._handle_save_answer({"question_id": 3}, MCPContext())


@patch("app.mcp.tools.user_tools.UserNotesRepository.create_note", return_value={"id": 5, "content": "note"})
def test_handle_save_note_validates_content(mock_create, user_tools_module):
    ctx = MCPContext(user={"id": 2})
    payload = {"content": " Remember this verse ", "metadata": {"verses": ["John 3:16"]}}

    result = user_tools_module._handle_save_note(payload, ctx)

    mock_create.assert_called_once()
    assert result["id"] == 5


def test_handle_save_note_rejects_bad_metadata(user_tools_module):
    ctx = MCPContext(user={"id": 2})
    with pytest.raises(ValidationError):
        user_tools_module._handle_save_note({"content": "note", "metadata": "oops"}, ctx)


@patch("app.mcp.tools.user_tools.UserNotesRepository.list_notes", return_value=[{"id": 1}])
def test_handle_get_notes_filters_question(mock_list, user_tools_module):
    ctx = MCPContext(user={"id": 4})
    user_tools_module._handle_get_notes({"question_id": 7, "limit": 1}, ctx)

    mock_list.assert_called_once_with(user_id=4, question_id=7, limit=1)


@patch("app.mcp.tools.user_tools.UserNotesRepository.list_notes", return_value=[])
def test_handle_get_notes_without_question(mock_list, user_tools_module):
    ctx = MCPContext(user={"id": 4})
    user_tools_module._handle_get_notes({"limit": 2}, ctx)
    mock_list.assert_called_once_with(user_id=4, question_id=None, limit=2)


@patch("app.mcp.tools.user_tools.QuestionRepository.get_question_history", return_value=[{"id": 1, "question": "Q", "answer": "A", "created_at": "ts"}])
def test_handle_get_history_formats_response(mock_history, user_tools_module):
    ctx = MCPContext(user={"id": 8})

    result = user_tools_module._handle_get_history({"limit": 5}, ctx)

    mock_history.assert_called_once_with(user_id=8, limit=5)
    assert result["total"] == 1
    assert result["questions"][0]["question"] == "Q"


@patch("app.mcp.tools.user_tools.SavedAnswersRepository.search_saved_answers", return_value=[{"id": 2}])
def test_handle_get_saved_answers_uses_search(mock_search, user_tools_module):
    ctx = MCPContext(user={"id": 10})
    result = user_tools_module._handle_get_saved_answers({"query": "love"}, ctx)
    mock_search.assert_called_once_with(user_id=10, query="love", tag=None)
    assert result["total"] == 1


def test_coerce_tags_validates_input(user_tools_module):
    with pytest.raises(ValidationError):
        user_tools_module._coerce_tags("faith")

    with pytest.raises(ValidationError):
        user_tools_module._coerce_tags([1])