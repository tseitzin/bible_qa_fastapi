"""Tests for custom exception classes."""
from app.utils.exceptions import DatabaseError, OpenAIError, ValidationError


class TestDatabaseError:
    """Tests for DatabaseError."""

    def test_default_detail(self):
        err = DatabaseError()
        assert err.status_code == 500
        assert err.detail == "Database operation failed"

    def test_custom_detail(self):
        err = DatabaseError(detail="Connection pool exhausted")
        assert err.status_code == 500
        assert err.detail == "Connection pool exhausted"


class TestOpenAIError:
    """Tests for OpenAIError."""

    def test_default_detail(self):
        err = OpenAIError()
        assert err.status_code == 503
        assert err.detail == "AI service unavailable"

    def test_custom_detail(self):
        err = OpenAIError(detail="Rate limit exceeded")
        assert err.status_code == 503
        assert err.detail == "Rate limit exceeded"


class TestValidationError:
    """Tests for ValidationError."""

    def test_default_detail(self):
        err = ValidationError()
        assert err.status_code == 400
        assert err.detail == "Invalid input"

    def test_custom_detail(self):
        err = ValidationError(detail="Question too short")
        assert err.status_code == 400
        assert err.detail == "Question too short"
