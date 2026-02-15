"""Tests for GeolocationService."""
import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock

import httpx

from app.services.geolocation_service import GeolocationService


class TestIsPrivateIp:
    """Tests for _is_private_ip static method."""

    def test_private_192_range(self):
        assert GeolocationService._is_private_ip("192.168.1.1") is True

    def test_loopback(self):
        assert GeolocationService._is_private_ip("127.0.0.1") is True

    def test_public_ip(self):
        assert GeolocationService._is_private_ip("8.8.8.8") is False

    def test_invalid_ip_string(self):
        assert GeolocationService._is_private_ip("not-an-ip") is True

    def test_private_10_range(self):
        assert GeolocationService._is_private_ip("10.0.0.1") is True

    def test_private_172_range(self):
        assert GeolocationService._is_private_ip("172.16.0.1") is True

    def test_link_local(self):
        assert GeolocationService._is_private_ip("169.254.1.1") is True


class TestLookupIp:
    """Tests for async lookup_ip."""

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.httpx.AsyncClient")
    async def test_success(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "countryCode": "US",
            "country": "United States",
            "region": "California",
            "city": "San Francisco",
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await GeolocationService.lookup_ip("8.8.8.8")

        assert result is not None
        assert result["country_code"] == "US"
        assert result["country_name"] == "United States"
        assert result["region"] == "California"
        assert result["city"] == "San Francisco"

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.httpx.AsyncClient")
    async def test_failed_status_in_response(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "fail",
            "message": "reserved range",
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await GeolocationService.lookup_ip("8.8.8.8")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.httpx.AsyncClient")
    async def test_non_200_http_status(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await GeolocationService.lookup_ip("8.8.8.8")

        assert result is None

    @pytest.mark.asyncio
    async def test_private_ip_returns_none(self):
        result = await GeolocationService.lookup_ip("192.168.1.1")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_ip_returns_none(self):
        result = await GeolocationService.lookup_ip("")
        assert result is None

    @pytest.mark.asyncio
    async def test_none_ip_returns_none(self):
        result = await GeolocationService.lookup_ip(None)
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.httpx.AsyncClient")
    async def test_timeout_exception_returns_none(self, mock_client_class):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await GeolocationService.lookup_ip("8.8.8.8")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.httpx.AsyncClient")
    async def test_general_exception_returns_none(self, mock_client_class):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await GeolocationService.lookup_ip("8.8.8.8")

        assert result is None


class TestLookupIpSync:
    """Tests for synchronous lookup_ip_sync."""

    @patch("app.services.geolocation_service.httpx.Client")
    def test_success(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "countryCode": "GB",
            "country": "United Kingdom",
            "region": "ENG",
            "city": "London",
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = GeolocationService.lookup_ip_sync("8.8.8.8")

        assert result is not None
        assert result["country_code"] == "GB"
        assert result["country_name"] == "United Kingdom"
        assert result["region"] == "ENG"
        assert result["city"] == "London"

    @patch("app.services.geolocation_service.httpx.Client")
    def test_failed_status_in_response(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "fail",
            "message": "invalid query",
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = GeolocationService.lookup_ip_sync("8.8.8.8")

        assert result is None

    @patch("app.services.geolocation_service.httpx.Client")
    def test_non_200_http_status(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 429

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = GeolocationService.lookup_ip_sync("8.8.8.8")

        assert result is None

    def test_private_ip_returns_none(self):
        result = GeolocationService.lookup_ip_sync("192.168.1.1")
        assert result is None

    def test_empty_ip_returns_none(self):
        result = GeolocationService.lookup_ip_sync("")
        assert result is None

    @patch("app.services.geolocation_service.httpx.Client")
    def test_timeout_returns_none(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = GeolocationService.lookup_ip_sync("8.8.8.8")

        assert result is None

    @patch("app.services.geolocation_service.httpx.Client")
    def test_general_exception_returns_none(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get.side_effect = ConnectionError("refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = GeolocationService.lookup_ip_sync("8.8.8.8")

        assert result is None
