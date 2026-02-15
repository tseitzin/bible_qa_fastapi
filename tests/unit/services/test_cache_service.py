"""Tests for CacheService."""
import json
import pytest
from unittest.mock import patch, MagicMock, Mock
from redis.exceptions import RedisError

from app.services.cache_service import (
    CacheService,
    _generate_cache_key,
    initialize_redis,
    close_redis,
    _get_client,
)


class TestGenerateCacheKey:
    """Tests for _generate_cache_key helper."""

    def test_generates_consistent_keys(self):
        key1 = _generate_cache_key("verse", "John 3:16")
        key2 = _generate_cache_key("verse", "John 3:16")
        assert key1 == key2

    def test_different_inputs_produce_different_keys(self):
        key1 = _generate_cache_key("verse", "John 3:16")
        key2 = _generate_cache_key("verse", "John 3:17")
        assert key1 != key2

    def test_prefix_is_included(self):
        key = _generate_cache_key("verse", "test")
        assert key.startswith("verse:")

    def test_handles_dict_args(self):
        key = _generate_cache_key("question", "test", {"key": "value"})
        assert key.startswith("question:")

    def test_handles_list_args(self):
        key = _generate_cache_key("question", "test", [1, 2, 3])
        assert key.startswith("question:")

    def test_handles_numeric_args(self):
        key = _generate_cache_key("passage", "John", 3, 16, 18)
        assert key.startswith("passage:")

    def test_normalizes_case(self):
        key1 = _generate_cache_key("verse", "John 3:16")
        key2 = _generate_cache_key("verse", "JOHN 3:16")
        assert key1 == key2


class TestCacheServiceGet:
    """Tests for CacheService.get()."""

    @patch("app.services.cache_service._get_client")
    def test_returns_none_when_no_client(self, mock_client):
        mock_client.return_value = None
        assert CacheService.get("key") is None

    @patch("app.services.cache_service._get_client")
    def test_returns_none_on_cache_miss(self, mock_client):
        client = MagicMock()
        client.get.return_value = None
        mock_client.return_value = client

        assert CacheService.get("key") is None

    @patch("app.services.cache_service._get_client")
    def test_returns_parsed_json(self, mock_client):
        client = MagicMock()
        client.get.return_value = '{"answer": "God is love"}'
        mock_client.return_value = client

        result = CacheService.get("key")
        assert result == {"answer": "God is love"}

    @patch("app.services.cache_service._get_client")
    def test_returns_raw_string_on_json_error(self, mock_client):
        client = MagicMock()
        client.get.return_value = "not json"
        mock_client.return_value = client

        result = CacheService.get("key")
        assert result == "not json"

    @patch("app.services.cache_service._get_client")
    def test_returns_none_on_redis_error(self, mock_client):
        client = MagicMock()
        client.get.side_effect = RedisError("Connection lost")
        mock_client.return_value = client

        assert CacheService.get("key") is None


class TestCacheServiceSet:
    """Tests for CacheService.set()."""

    @patch("app.services.cache_service._get_client")
    def test_returns_false_when_no_client(self, mock_client):
        mock_client.return_value = None
        assert CacheService.set("key", "value") is False

    @patch("app.services.cache_service._get_client")
    def test_sets_dict_as_json(self, mock_client):
        client = MagicMock()
        mock_client.return_value = client

        result = CacheService.set("key", {"answer": "test"})

        assert result is True
        client.set.assert_called_once()

    @patch("app.services.cache_service._get_client")
    def test_sets_with_ttl(self, mock_client):
        client = MagicMock()
        mock_client.return_value = client

        CacheService.set("key", "value", ttl=3600)

        client.setex.assert_called_once_with("key", 3600, "value")

    @patch("app.services.cache_service._get_client")
    def test_sets_without_ttl(self, mock_client):
        client = MagicMock()
        mock_client.return_value = client

        CacheService.set("key", "value", ttl=0)

        client.set.assert_called_once()

    @patch("app.services.cache_service._get_client")
    def test_returns_false_on_redis_error(self, mock_client):
        client = MagicMock()
        client.set.side_effect = RedisError("Write failed")
        mock_client.return_value = client

        assert CacheService.set("key", "value") is False


class TestCacheServiceDelete:
    """Tests for CacheService.delete()."""

    @patch("app.services.cache_service._get_client")
    def test_returns_false_when_no_client(self, mock_client):
        mock_client.return_value = None
        assert CacheService.delete("key") is False

    @patch("app.services.cache_service._get_client")
    def test_deletes_key(self, mock_client):
        client = MagicMock()
        mock_client.return_value = client

        result = CacheService.delete("key")

        assert result is True
        client.delete.assert_called_once_with("key")


class TestCacheServiceClearPattern:
    """Tests for CacheService.clear_pattern()."""

    @patch("app.services.cache_service._get_client")
    def test_returns_zero_when_no_client(self, mock_client):
        mock_client.return_value = None
        assert CacheService.clear_pattern("question:*") == 0

    @patch("app.services.cache_service._get_client")
    def test_clears_matching_keys(self, mock_client):
        client = MagicMock()
        client.keys.return_value = ["question:abc", "question:def"]
        client.delete.return_value = 2
        mock_client.return_value = client

        result = CacheService.clear_pattern("question:*")

        assert result == 2

    @patch("app.services.cache_service._get_client")
    def test_returns_zero_when_no_matching_keys(self, mock_client):
        client = MagicMock()
        client.keys.return_value = []
        mock_client.return_value = client

        result = CacheService.clear_pattern("nonexistent:*")

        assert result == 0


class TestCacheServiceConvenienceMethods:
    """Tests for verse/passage/chapter/search/question convenience methods."""

    @patch("app.services.cache_service.CacheService.get")
    def test_get_verse(self, mock_get):
        mock_get.return_value = {"text": "In the beginning..."}
        result = CacheService.get_verse("Genesis 1:1")
        assert result["text"] == "In the beginning..."

    @patch("app.services.cache_service.get_settings")
    @patch("app.services.cache_service.CacheService.set")
    def test_set_verse(self, mock_set, mock_settings):
        mock_settings.return_value = Mock(cache_ttl_verses=86400)
        mock_set.return_value = True
        result = CacheService.set_verse("Genesis 1:1", {"text": "test"})
        assert result is True

    @patch("app.services.cache_service.CacheService.get")
    def test_get_question(self, mock_get):
        mock_get.return_value = "God is love"
        result = CacheService.get_question("What is love?")
        assert result == "God is love"

    @patch("app.services.cache_service.get_settings")
    @patch("app.services.cache_service.CacheService.set")
    def test_set_question(self, mock_set, mock_settings):
        mock_settings.return_value = Mock(cache_ttl_questions=86400)
        mock_set.return_value = True
        result = CacheService.set_question("What is love?", "God is love")
        assert result is True

    @patch("app.services.cache_service.CacheService.get")
    def test_get_question_with_history(self, mock_get):
        mock_get.return_value = "Answer with context"
        history = [{"role": "user", "content": "Previous Q"}]
        result = CacheService.get_question("Follow up?", conversation_history=history)
        assert result == "Answer with context"


class TestInitializeRedis:
    """Tests for initialize_redis()."""

    @patch("app.services.cache_service._redis_client", None)
    @patch("app.services.cache_service.get_settings")
    def test_skips_when_cache_disabled(self, mock_settings):
        mock_settings.return_value = Mock(cache_enabled=False)
        initialize_redis()
        # Should return without creating client

    @patch("app.services.cache_service._redis_client", "already_set")
    @patch("app.services.cache_service.get_settings")
    def test_skips_when_already_initialized(self, mock_settings):
        """Should warn and return when client already exists."""
        initialize_redis()
        # Should not call get_settings since it returns early
