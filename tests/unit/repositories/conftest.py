"""Shared fixtures for repository unit tests."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db():
    """Mock get_db_connection context manager yielding (connection, cursor).

    Usage in tests:
        def test_something(self, mock_db):
            conn, cur = mock_db
            cur.fetchone.return_value = {"id": 1}
            # ... call repository method ...
            cur.execute.assert_called_once()
    """
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.database.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_conn, mock_cursor
