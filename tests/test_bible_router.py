"""Tests for Bible verse API endpoints."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import bible
from app.utils.exceptions import ValidationError

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    """Ensure dependency overrides are cleared between tests."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_fetch_bible_verse_success():
    """Should return verse data when service finds a match."""
    def override_service():
        mock_service = Mock()
        mock_service.get_verse.return_value = {
            "reference": "John 3:16",
            "book": "John",
            "chapter": 3,
            "verse": 16,
            "text": "For God so loved the world...",
        }
        return mock_service

    app.dependency_overrides[bible.get_bible_service] = override_service

    response = client.get("/api/bible/verse", params={"ref": "John 3:16"})

    assert response.status_code == 200
    data = response.json()
    assert data["reference"] == "John 3:16"
    assert data["text"].startswith("For God so loved")


def test_fetch_bible_verse_not_found():
    """Should return 404 when verse is missing."""
    def override_service():
        mock_service = Mock()
        mock_service.get_verse.return_value = None
        return mock_service

    app.dependency_overrides[bible.get_bible_service] = override_service

    response = client.get("/api/bible/verse", params={"ref": "John 3:17"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Verse not found"


def test_fetch_bible_verse_invalid_reference():
    """Should return 400 for invalid reference format."""
    def override_service():
        mock_service = Mock()
        mock_service.get_verse.side_effect = ValidationError("Invalid reference format")
        return mock_service

    app.dependency_overrides[bible.get_bible_service] = override_service

    response = client.get("/api/bible/verse", params={"ref": "bad"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid reference format"
