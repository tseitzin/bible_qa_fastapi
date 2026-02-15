"""Tests for the network utility module."""
from unittest.mock import Mock

from app.utils.network import get_client_ip


class TestGetClientIP:
    """Tests for get_client_ip()."""

    def test_extracts_from_x_forwarded_for(self):
        """Should return the first IP from X-Forwarded-For header."""
        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"}
        request.client = Mock(host="10.0.0.1")

        assert get_client_ip(request) == "203.0.113.50"

    def test_extracts_single_x_forwarded_for(self):
        """Should handle a single IP in X-Forwarded-For."""
        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.50"}
        request.client = Mock(host="10.0.0.1")

        assert get_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace_from_x_forwarded_for(self):
        """Should strip whitespace from extracted IP."""
        request = Mock()
        request.headers = {"X-Forwarded-For": "  203.0.113.50 , 70.41.3.18"}
        request.client = Mock(host="10.0.0.1")

        assert get_client_ip(request) == "203.0.113.50"

    def test_falls_back_to_x_real_ip(self):
        """Should use X-Real-IP when X-Forwarded-For is absent."""
        request = Mock()
        request.headers = {"X-Real-IP": "198.51.100.23"}
        request.client = Mock(host="10.0.0.1")

        assert get_client_ip(request) == "198.51.100.23"

    def test_strips_whitespace_from_x_real_ip(self):
        """Should strip whitespace from X-Real-IP."""
        request = Mock()
        request.headers = {"X-Real-IP": "  198.51.100.23  "}
        request.client = Mock(host="10.0.0.1")

        assert get_client_ip(request) == "198.51.100.23"

    def test_falls_back_to_client_host(self):
        """Should use request.client.host when no proxy headers present."""
        request = Mock()
        request.headers = {}
        request.client = Mock(host="192.168.1.5")

        assert get_client_ip(request) == "192.168.1.5"

    def test_returns_unknown_when_no_client(self):
        """Should return 'unknown' when request.client is None."""
        request = Mock()
        request.headers = {}
        request.client = None

        assert get_client_ip(request) == "unknown"

    def test_returns_unknown_when_client_host_is_none(self):
        """Should return 'unknown' when client.host is None."""
        request = Mock()
        request.headers = {}
        request.client = Mock(host=None)

        assert get_client_ip(request) == "unknown"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self):
        """X-Forwarded-For should be preferred over X-Real-IP."""
        request = Mock()
        request.headers = {
            "X-Forwarded-For": "203.0.113.50",
            "X-Real-IP": "198.51.100.23",
        }
        request.client = Mock(host="10.0.0.1")

        assert get_client_ip(request) == "203.0.113.50"
