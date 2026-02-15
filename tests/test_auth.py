"""Unit tests for authentication and authorization."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException, Request, Response
from jose import jwt
from jose import JWTError

from app.main import app
from app.config import get_settings
from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    _extract_token_from_request,
    _convert_user,
    _resolve_dependency_override,
    get_user_by_email,
    get_user_by_id,
    update_user_ip_address,
    create_guest_user,
    create_user,
    get_current_user,
    get_current_user_optional,
    get_current_active_user,
    get_current_admin_user,
    get_or_create_guest_user,
    GUEST_USER_COOKIE_NAME,
    SECRET_KEY,
    ALGORITHM,
)

# Test client
client = TestClient(app)
settings = get_settings()


def _csrf_headers(token: str = "test-csrf-token"):
    """Attach a CSRF cookie to the shared client and return matching headers."""
    client.cookies.set(settings.csrf_cookie_name, token)
    return {settings.csrf_header_name: token}


def _make_mock_request(cookie_token=None, auth_header=None, cookies=None):
    """Build a mock Request with optional cookie and Authorization header."""
    request = Mock(spec=Request)
    cookie_dict = cookies or {}
    if cookie_token is not None:
        cookie_dict[settings.auth_cookie_name] = cookie_token
    request.cookies = cookie_dict
    headers = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    request.headers = headers
    return request


_UNSET = object()


def _mock_db_cursor(fetchone_return=_UNSET, fetchall_return=_UNSET):
    """Return (mock_get_db, mock_conn, mock_cursor) wired up as a context manager."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)
    if fetchone_return is not _UNSET:
        mock_cursor.fetchone.return_value = fetchone_return
    if fetchall_return is not _UNSET:
        mock_cursor.fetchall.return_value = fetchall_return

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_get_db = MagicMock()
    mock_get_db.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_get_db.return_value.__exit__ = Mock(return_value=None)

    return mock_get_db, mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# _extract_token_from_request
# ---------------------------------------------------------------------------

class TestExtractTokenFromRequest:
    """Tests for _extract_token_from_request helper."""

    def test_returns_none_when_request_is_none(self):
        assert _extract_token_from_request(None) is None

    def test_extracts_token_from_cookie(self):
        request = _make_mock_request(cookie_token="cookie-jwt-value")
        assert _extract_token_from_request(request) == "cookie-jwt-value"

    def test_extracts_token_from_bearer_header(self):
        request = _make_mock_request(auth_header="Bearer header-jwt-value")
        assert _extract_token_from_request(request) == "header-jwt-value"

    def test_cookie_takes_precedence_over_header(self):
        request = _make_mock_request(
            cookie_token="from-cookie",
            auth_header="Bearer from-header",
        )
        assert _extract_token_from_request(request) == "from-cookie"

    def test_returns_none_when_no_token_anywhere(self):
        request = _make_mock_request()
        assert _extract_token_from_request(request) is None

    def test_returns_none_for_non_bearer_scheme(self):
        request = _make_mock_request(auth_header="Basic dXNlcjpwYXNz")
        assert _extract_token_from_request(request) is None

    def test_returns_none_for_empty_auth_header(self):
        request = _make_mock_request(auth_header="")
        assert _extract_token_from_request(request) is None


# ---------------------------------------------------------------------------
# _convert_user
# ---------------------------------------------------------------------------

class TestConvertUser:
    """Tests for _convert_user normalizer."""

    def test_converts_normal_row(self):
        row = {
            "id": 1,
            "email": "test@example.com",
            "username": "tester",
            "is_active": True,
            "is_admin": False,
            "created_at": datetime(2024, 1, 1),
        }
        result = _convert_user(row)
        assert result == {
            "id": 1,
            "email": "test@example.com",
            "username": "tester",
            "is_active": True,
            "is_admin": False,
            "created_at": datetime(2024, 1, 1),
        }

    def test_returns_none_for_none_row(self):
        assert _convert_user(None) is None

    def test_returns_none_for_empty_dict(self):
        # Empty dict is falsy
        assert _convert_user({}) is None

    def test_includes_hashed_password_when_present(self):
        row = {
            "id": 1,
            "email": "test@example.com",
            "username": "tester",
            "is_active": True,
            "is_admin": True,
            "created_at": datetime(2024, 1, 1),
            "hashed_password": "bcrypt-hash-here",
        }
        result = _convert_user(row)
        assert result["hashed_password"] == "bcrypt-hash-here"

    def test_omits_hashed_password_when_absent(self):
        row = {
            "id": 2,
            "email": "a@b.com",
            "username": "u",
            "is_active": True,
            "is_admin": False,
            "created_at": datetime(2024, 6, 1),
        }
        result = _convert_user(row)
        assert "hashed_password" not in result

    def test_defaults_is_admin_to_false_when_missing(self):
        row = {
            "id": 3,
            "email": "noadmin@test.com",
            "username": "noadmin",
            "is_active": True,
            "created_at": datetime(2024, 3, 1),
        }
        result = _convert_user(row)
        assert result["is_admin"] is False


# ---------------------------------------------------------------------------
# _resolve_dependency_override
# ---------------------------------------------------------------------------

class TestResolveDependencyOverride:
    """Tests for _resolve_dependency_override."""

    @pytest.mark.asyncio
    async def test_returns_none_false_when_request_is_none(self):
        result, found = await _resolve_dependency_override(None, lambda: None)
        assert result is None
        assert found is False

    @pytest.mark.asyncio
    async def test_returns_none_false_when_no_overrides(self):
        request = Mock(spec=Request)
        request.app = Mock()
        request.app.dependency_overrides = {}
        result, found = await _resolve_dependency_override(request, lambda: None)
        assert result is None
        assert found is False

    @pytest.mark.asyncio
    async def test_returns_none_false_when_dependency_not_overridden(self):
        sentinel_dep = lambda: None  # noqa: E731
        request = Mock(spec=Request)
        request.app = Mock()
        request.app.dependency_overrides = {lambda: None: lambda: "x"}
        result, found = await _resolve_dependency_override(request, sentinel_dep)
        assert result is None
        assert found is False

    @pytest.mark.asyncio
    async def test_returns_sync_override_value(self):
        sentinel_dep = lambda: None  # noqa: E731
        request = Mock(spec=Request)
        request.app = Mock()
        request.app.dependency_overrides = {sentinel_dep: lambda: {"id": 42}}
        result, found = await _resolve_dependency_override(request, sentinel_dep)
        assert found is True
        assert result == {"id": 42}

    @pytest.mark.asyncio
    async def test_returns_async_override_value(self):
        sentinel_dep = lambda: None  # noqa: E731

        async def async_override():
            return {"id": 99}

        request = Mock(spec=Request)
        request.app = Mock()
        request.app.dependency_overrides = {sentinel_dep: async_override}
        result, found = await _resolve_dependency_override(request, sentinel_dep)
        assert found is True
        assert result == {"id": 99}

    @pytest.mark.asyncio
    async def test_returns_none_false_when_app_attr_missing(self):
        """Request without .app should not crash."""
        request = Mock(spec=[])  # No attributes at all
        result, found = await _resolve_dependency_override(request, lambda: None)
        assert result is None
        assert found is False


# ---------------------------------------------------------------------------
# get_user_by_email / get_user_by_id
# ---------------------------------------------------------------------------

class TestGetUserByEmail:
    """Tests for get_user_by_email."""

    @patch('app.auth.get_db_connection')
    def test_returns_user_when_found(self, mock_get_db):
        mock_get_db_obj, mock_conn, mock_cursor = _mock_db_cursor(
            fetchone_return={
                'id': 1,
                'email': 'test@example.com',
                'username': 'tester',
                'hashed_password': 'hashed',
                'is_active': True,
                'is_admin': False,
                'created_at': datetime(2024, 1, 1),
            }
        )
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = get_user_by_email('test@example.com')
        assert result['email'] == 'test@example.com'
        assert result['id'] == 1
        assert result['hashed_password'] == 'hashed'
        mock_cursor.execute.assert_called_once()

    @patch('app.auth.get_db_connection')
    def test_returns_none_when_not_found(self, mock_get_db):
        mock_get_db_obj, _, mock_cursor = _mock_db_cursor(fetchone_return=None)
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = get_user_by_email('missing@example.com')
        assert result is None


class TestGetUserById:
    """Tests for get_user_by_id."""

    @patch('app.auth.get_db_connection')
    def test_returns_user_when_found(self, mock_get_db):
        mock_get_db_obj, _, mock_cursor = _mock_db_cursor(
            fetchone_return={
                'id': 2,
                'email': 'user@example.com',
                'username': 'user',
                'is_active': True,
                'is_admin': False,
                'created_at': datetime(2024, 2, 1),
            }
        )
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = get_user_by_id(2)
        assert result['id'] == 2
        assert result['email'] == 'user@example.com'

    @patch('app.auth.get_db_connection')
    def test_returns_none_when_not_found(self, mock_get_db):
        mock_get_db_obj, _, _ = _mock_db_cursor(fetchone_return=None)
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = get_user_by_id(9999)
        assert result is None


# ---------------------------------------------------------------------------
# update_user_ip_address
# ---------------------------------------------------------------------------

class TestUpdateUserIpAddress:
    """Tests for update_user_ip_address."""

    @patch('app.auth.get_db_connection')
    def test_updates_ip_and_commits(self, mock_get_db):
        mock_get_db_obj, mock_conn, mock_cursor = _mock_db_cursor()
        mock_get_db.return_value = mock_get_db_obj.return_value

        update_user_ip_address(1, '192.168.1.1')

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert '192.168.1.1' in call_args[1]
        assert 1 in call_args[1]
        mock_conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# create_guest_user
# ---------------------------------------------------------------------------

class TestCreateGuestUser:
    """Tests for create_guest_user."""

    @patch('app.auth.get_db_connection')
    def test_creates_guest_with_geo_data(self, mock_get_db):
        created_at = datetime(2024, 5, 1)
        mock_get_db_obj, mock_conn, mock_cursor = _mock_db_cursor(
            fetchone_return={
                'id': 10,
                'email': None,
                'username': 'guest_abc123def456',
                'is_active': True,
                'is_admin': False,
                'is_guest': True,
                'last_ip_address': '8.8.8.8',
                'country_code': 'US',
                'country_name': 'United States',
                'city': 'Mountain View',
                'region': 'California',
                'created_at': created_at,
            }
        )
        mock_get_db.return_value = mock_get_db_obj.return_value

        geo = {
            'country_code': 'US',
            'country_name': 'United States',
            'city': 'Mountain View',
            'region': 'California',
        }
        result = create_guest_user('8.8.8.8', geo)

        assert result['id'] == 10
        assert result['is_guest'] is True
        assert result['email'] is None
        mock_conn.commit.assert_called_once()

        # Verify geo params were passed to the INSERT
        insert_args = mock_cursor.execute.call_args[0][1]
        assert 'US' in insert_args
        assert 'United States' in insert_args
        assert 'Mountain View' in insert_args
        assert 'California' in insert_args

    @patch('app.auth.get_db_connection')
    def test_creates_guest_without_geo_data(self, mock_get_db):
        mock_get_db_obj, mock_conn, mock_cursor = _mock_db_cursor(
            fetchone_return={
                'id': 11,
                'email': None,
                'username': 'guest_xyz789',
                'is_active': True,
                'is_admin': False,
                'is_guest': True,
                'last_ip_address': '127.0.0.1',
                'country_code': None,
                'country_name': None,
                'city': None,
                'region': None,
                'created_at': datetime(2024, 5, 2),
            }
        )
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = create_guest_user('127.0.0.1')
        assert result['id'] == 11
        assert result['is_guest'] is True

        insert_args = mock_cursor.execute.call_args[0][1]
        # The four geo columns should be None
        assert insert_args[2:] == (None, None, None, None)

    @patch('app.auth.get_db_connection')
    def test_returns_none_when_no_user_created(self, mock_get_db):
        mock_get_db_obj, mock_conn, _ = _mock_db_cursor(fetchone_return=None)
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = create_guest_user('0.0.0.0')
        assert result is None


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    """Tests for create_user."""

    @patch('app.auth.get_password_hash')
    @patch('app.auth.get_db_connection')
    def test_creates_registered_user(self, mock_get_db, mock_get_hash):
        mock_get_hash.return_value = 'hashed_password_123'
        mock_get_db_obj, mock_conn, mock_cursor = _mock_db_cursor(
            fetchone_return={
                'id': 5,
                'email': 'new@example.com',
                'username': 'newuser',
                'is_active': True,
                'is_admin': False,
                'created_at': datetime(2024, 6, 1),
            }
        )
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = create_user('new@example.com', 'newuser', 'plain_password', '10.0.0.1')

        assert result['id'] == 5
        assert result['email'] == 'new@example.com'
        mock_get_hash.assert_called_once_with('plain_password')
        mock_conn.commit.assert_called_once()

        insert_args = mock_cursor.execute.call_args[0][1]
        assert 'hashed_password_123' in insert_args
        assert '10.0.0.1' in insert_args

    @patch('app.auth.get_password_hash')
    @patch('app.auth.get_db_connection')
    def test_creates_user_without_ip(self, mock_get_db, mock_get_hash):
        mock_get_hash.return_value = 'hashed'
        mock_get_db_obj, mock_conn, mock_cursor = _mock_db_cursor(
            fetchone_return={
                'id': 6,
                'email': 'noip@example.com',
                'username': 'noipuser',
                'is_active': True,
                'is_admin': False,
                'created_at': datetime(2024, 6, 2),
            }
        )
        mock_get_db.return_value = mock_get_db_obj.return_value

        result = create_user('noip@example.com', 'noipuser', 'pass')

        assert result['id'] == 6
        insert_args = mock_cursor.execute.call_args[0][1]
        # ip_address should be None when not provided
        assert insert_args[-1] is None


# ---------------------------------------------------------------------------
# get_current_user (async)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for get_current_user."""

    @pytest.mark.asyncio
    @patch('app.auth.get_user_by_id')
    async def test_valid_token_returns_user(self, mock_get_user_by_id):
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime(2024, 1, 1),
        }
        mock_get_user_by_id.return_value = mock_user
        token = create_access_token(data={'sub': '1'})

        result = await get_current_user(token=token)
        assert result['id'] == 1
        assert result['email'] == 'test@example.com'
        mock_get_user_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_no_token_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_and_no_request_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=None, token=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', side_effect=JWTError('bad'))
    async def test_invalid_token_raises_401(self, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='garbage-token')
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={})
    async def test_missing_sub_raises_401(self, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='token')
        assert exc.value.status_code == 401
        mock_decode.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value=None)
    async def test_user_not_found_raises_401(self, mock_get_user_by_id, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='token')
        assert exc.value.status_code == 401
        mock_get_user_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value={'id': 1, 'is_active': False})
    async def test_inactive_user_raises_400(self, mock_get_user_by_id, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='token')
        assert exc.value.status_code == 400
        assert 'Inactive' in exc.value.detail

    @pytest.mark.asyncio
    @patch('app.auth.get_user_by_id')
    async def test_extracts_token_from_request_cookie(self, mock_get_user_by_id):
        """get_current_user should extract a token from the request cookie."""
        mock_user = {
            'id': 7,
            'email': 'cookie@example.com',
            'username': 'cookieuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime(2024, 3, 1),
        }
        mock_get_user_by_id.return_value = mock_user
        token = create_access_token(data={'sub': '7'})
        request = _make_mock_request(cookie_token=token)

        result = await get_current_user(request=request)
        assert result['id'] == 7


# ---------------------------------------------------------------------------
# get_current_user_optional (async)
# ---------------------------------------------------------------------------

class TestGetCurrentUserOptional:
    """Tests for get_current_user_optional."""

    @pytest.mark.asyncio
    @patch('app.auth.get_user_by_id')
    async def test_valid_token_returns_user(self, mock_get_user_by_id):
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime(2024, 1, 1),
        }
        mock_get_user_by_id.return_value = mock_user
        token = create_access_token(data={'sub': '1'})

        result = await get_current_user_optional(token=token)
        assert result['id'] == 1

    @pytest.mark.asyncio
    async def test_no_token_returns_none(self):
        result = await get_current_user_optional(token=None)
        assert result is None

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', side_effect=JWTError('bad token'))
    async def test_invalid_token_returns_none(self, mock_decode):
        result = await get_current_user_optional(token='bad')
        assert result is None
        mock_decode.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': None})
    async def test_missing_sub_returns_none(self, mock_decode):
        result = await get_current_user_optional(token='token')
        assert result is None
        mock_decode.assert_called_once_with('token', SECRET_KEY, algorithms=[ALGORITHM])

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value=None)
    async def test_user_not_found_returns_none(self, mock_get_user_by_id, mock_decode):
        result = await get_current_user_optional(token='token')
        assert result is None

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value={'id': 1, 'is_active': False})
    async def test_inactive_user_returns_none(self, mock_get_user_by_id, mock_decode):
        result = await get_current_user_optional(token='token')
        assert result is None
        mock_get_user_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch('app.auth.get_user_by_id')
    async def test_extracts_token_from_request(self, mock_get_user_by_id):
        mock_user = {
            'id': 3,
            'email': 'opt@example.com',
            'username': 'optuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime(2024, 4, 1),
        }
        mock_get_user_by_id.return_value = mock_user
        token = create_access_token(data={'sub': '3'})
        request = _make_mock_request(cookie_token=token)

        result = await get_current_user_optional(request=request)
        assert result['id'] == 3


# ---------------------------------------------------------------------------
# get_current_active_user / get_current_admin_user
# ---------------------------------------------------------------------------

class TestGetCurrentActiveUser:
    """Tests for get_current_active_user."""

    @pytest.mark.asyncio
    async def test_active_user_passes(self):
        user = {'id': 1, 'is_active': True, 'is_admin': False}
        result = await get_current_active_user(current_user=user)
        assert result['id'] == 1

    @pytest.mark.asyncio
    async def test_inactive_user_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_active_user(current_user={'is_active': False})
        assert exc.value.status_code == 400


class TestGetCurrentAdminUser:
    """Tests for get_current_admin_user."""

    @pytest.mark.asyncio
    async def test_admin_user_passes(self):
        user = {'id': 1, 'is_active': True, 'is_admin': True}
        result = await get_current_admin_user(current_user=user)
        assert result['id'] == 1

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_admin_user(current_user={'is_active': True, 'is_admin': False})
        assert exc.value.status_code == 403
        assert 'Admin' in exc.value.detail

    @pytest.mark.asyncio
    async def test_missing_is_admin_defaults_false(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_admin_user(current_user={'is_active': True})
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# get_or_create_guest_user (async)
# ---------------------------------------------------------------------------

class TestGetOrCreateGuestUser:
    """Tests for get_or_create_guest_user."""

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override')
    async def test_returns_authenticated_user_via_override(self, mock_resolve):
        """If a dependency override provides a user, return it directly."""
        auth_user = {
            'id': 1,
            'email': 'auth@example.com',
            'username': 'authuser',
            'is_active': True,
        }
        mock_resolve.return_value = (auth_user, True)

        request = Mock(spec=Request)
        response = Mock(spec=Response)

        result = await get_or_create_guest_user(request, response)
        assert result['id'] == 1
        assert result['email'] == 'auth@example.com'

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional')
    async def test_returns_authenticated_user_via_normal_auth(
        self, mock_get_optional, mock_resolve
    ):
        """If the user has a valid auth token, return the authenticated user."""
        auth_user = {
            'id': 2,
            'email': 'normal@example.com',
            'username': 'normaluser',
            'is_active': True,
        }
        mock_get_optional.return_value = auth_user

        request = Mock(spec=Request)
        response = Mock(spec=Response)

        result = await get_or_create_guest_user(request, response)
        assert result['id'] == 2

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    @patch('app.auth.get_user_by_id')
    async def test_returns_existing_guest_from_cookie(
        self, mock_get_user_by_id, mock_get_optional, mock_resolve
    ):
        """If a guest cookie points to a valid guest user, return that guest."""
        guest_user = {
            'id': 50,
            'email': None,
            'username': 'guest_abc',
            'is_active': True,
            'is_guest': True,
        }
        mock_get_user_by_id.return_value = guest_user

        request = Mock(spec=Request)
        request.cookies = {GUEST_USER_COOKIE_NAME: '50'}
        request.headers = {}
        response = Mock(spec=Response)

        result = await get_or_create_guest_user(request, response)
        assert result['id'] == 50
        assert result['is_guest'] is True
        mock_get_user_by_id.assert_called_once_with(50)

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    @patch('app.auth.get_user_by_id', return_value=None)
    @patch('app.auth.get_client_ip', return_value='10.0.0.1')
    @patch('app.auth.create_guest_user')
    async def test_creates_new_guest_when_cookie_id_invalid(
        self, mock_create_guest, mock_ip, mock_get_user_by_id,
        mock_get_optional, mock_resolve
    ):
        """If guest cookie ID doesn't match a valid guest, create a new one."""
        new_guest = {
            'id': 60,
            'email': None,
            'username': 'guest_new',
            'is_active': True,
            'is_guest': True,
        }
        mock_create_guest.return_value = new_guest

        request = Mock(spec=Request)
        request.cookies = {GUEST_USER_COOKIE_NAME: '999'}
        request.headers = {}
        response = Mock(spec=Response)

        with patch('app.auth.GeolocationService', create=True) as MockGeo:
            MockGeo.lookup_ip_sync.return_value = None
            with patch('app.services.geolocation_service.GeolocationService') as MockGeo2:
                MockGeo2.lookup_ip_sync.return_value = None
                result = await get_or_create_guest_user(request, response)

        assert result['id'] == 60
        mock_create_guest.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    @patch('app.auth.get_client_ip', return_value='203.0.113.1')
    @patch('app.auth.create_guest_user')
    async def test_creates_new_guest_with_geolocation_no_cookie(
        self, mock_create_guest, mock_ip,
        mock_get_optional, mock_resolve
    ):
        """No auth, no cookie -> creates a new guest with geolocation lookup."""
        new_guest = {
            'id': 70,
            'email': None,
            'username': 'guest_geo',
            'is_active': True,
            'is_guest': True,
        }
        mock_create_guest.return_value = new_guest

        request = Mock(spec=Request)
        request.cookies = {}
        request.headers = {}
        response = Mock(spec=Response)

        geo_data = {'country_code': 'DE', 'country_name': 'Germany', 'city': 'Berlin', 'region': 'Berlin'}
        with patch('app.services.geolocation_service.GeolocationService') as MockGeo:
            MockGeo.lookup_ip_sync.return_value = geo_data
            result = await get_or_create_guest_user(request, response)

        assert result['id'] == 70
        mock_create_guest.assert_called_once_with('203.0.113.1', geo_data)
        # Cookie should be set on response
        response.set_cookie.assert_called_once()
        cookie_call = response.set_cookie.call_args
        # Extract key from either kwargs or positional args
        key = cookie_call.kwargs.get('key') or (cookie_call.args[0] if cookie_call.args else None)
        assert key == GUEST_USER_COOKIE_NAME
        value = cookie_call.kwargs.get('value') or (cookie_call.args[1] if len(cookie_call.args) > 1 else None)
        assert value == '70'

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    @patch('app.auth.get_client_ip', return_value='127.0.0.1')
    @patch('app.auth.create_guest_user', return_value=None)
    async def test_returns_none_when_guest_creation_fails(
        self, mock_create_guest, mock_ip,
        mock_get_optional, mock_resolve
    ):
        """If create_guest_user returns None, the function returns None."""
        request = Mock(spec=Request)
        request.cookies = {}
        request.headers = {}
        response = Mock(spec=Response)

        with patch('app.services.geolocation_service.GeolocationService') as MockGeo:
            MockGeo.lookup_ip_sync.return_value = None
            result = await get_or_create_guest_user(request, response)

        assert result is None
        # set_cookie should NOT be called when guest is None
        response.set_cookie.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    @patch('app.auth.get_client_ip', return_value='127.0.0.1')
    @patch('app.auth.create_guest_user')
    async def test_no_cookie_set_when_response_is_none(
        self, mock_create_guest, mock_ip,
        mock_get_optional, mock_resolve
    ):
        """When response is None, the guest cookie is not set."""
        new_guest = {
            'id': 80,
            'email': None,
            'username': 'guest_noresponse',
            'is_active': True,
            'is_guest': True,
        }
        mock_create_guest.return_value = new_guest

        request = Mock(spec=Request)
        request.cookies = {}
        request.headers = {}

        with patch('app.services.geolocation_service.GeolocationService') as MockGeo:
            MockGeo.lookup_ip_sync.return_value = None
            result = await get_or_create_guest_user(request, response=None)

        assert result['id'] == 80

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    @patch('app.auth.get_user_by_id')
    async def test_cookie_with_non_guest_user_creates_new_guest(
        self, mock_get_user_by_id, mock_get_optional, mock_resolve
    ):
        """If the guest cookie points to a registered (non-guest) user, create a new guest."""
        registered_user = {
            'id': 50,
            'email': 'reg@example.com',
            'username': 'reguser',
            'is_active': True,
            'is_guest': False,  # Not a guest
        }
        mock_get_user_by_id.return_value = registered_user

        new_guest = {
            'id': 90,
            'email': None,
            'username': 'guest_new2',
            'is_active': True,
            'is_guest': True,
        }

        request = Mock(spec=Request)
        request.cookies = {GUEST_USER_COOKIE_NAME: '50'}
        request.headers = {}
        response = Mock(spec=Response)

        with patch('app.auth.get_client_ip', return_value='10.0.0.1'), \
             patch('app.auth.create_guest_user', return_value=new_guest), \
             patch('app.services.geolocation_service.GeolocationService') as MockGeo:
            MockGeo.lookup_ip_sync.return_value = None
            result = await get_or_create_guest_user(request, response)

        assert result['id'] == 90
        assert result['is_guest'] is True

    @pytest.mark.asyncio
    @patch('app.auth._resolve_dependency_override', return_value=(None, False))
    @patch('app.auth.get_current_user_optional', return_value=None)
    async def test_cookie_with_invalid_value_creates_new_guest(
        self, mock_get_optional, mock_resolve
    ):
        """If the guest cookie value is not a valid int, create a new guest."""
        new_guest = {
            'id': 100,
            'email': None,
            'username': 'guest_bad_cookie',
            'is_active': True,
            'is_guest': True,
        }

        request = Mock(spec=Request)
        request.cookies = {GUEST_USER_COOKIE_NAME: 'not-a-number'}
        request.headers = {}
        response = Mock(spec=Response)

        with patch('app.auth.get_client_ip', return_value='10.0.0.2'), \
             patch('app.auth.create_guest_user', return_value=new_guest), \
             patch('app.services.geolocation_service.GeolocationService') as MockGeo:
            MockGeo.lookup_ip_sync.return_value = None
            result = await get_or_create_guest_user(request, response)

        assert result['id'] == 100


# ===========================================================================
# Original integration-style tests (kept for backward compatibility)
# ===========================================================================


class TestUserRegistration:
    """Test cases for user registration."""

    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.create_user')
    def test_register_creates_user_with_hashed_password(self, mock_create_user, mock_get_user_by_email):
        """Test that user registration creates a new user in the database with a hashed password."""
        # Mock that user doesn't exist
        mock_get_user_by_email.return_value = None

        # Mock user creation
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        mock_create_user.return_value = mock_user

        # Test registration
        request_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'SecurePass123!'
        }

        response = client.post('/api/auth/register', json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'
        assert data['is_active'] is True
        assert 'id' in data
        assert 'created_at' in data

        # Verify create_user was called
        mock_create_user.assert_called_once()
        call_args = mock_create_user.call_args[1]
        assert call_args['email'] == 'test@example.com'
        assert call_args['username'] == 'testuser'
        # Verify password was passed (will be hashed in create_user)
        assert call_args['password'] == 'SecurePass123!'

    @patch('app.auth.get_password_hash')
    @patch('app.auth.get_db_connection')
    def test_password_is_hashed_in_database(self, mock_get_db, mock_get_hash):
        """Test that password is hashed before storing in database."""
        from app.auth import create_user as auth_create_user

        # Mock password hashing
        mock_get_hash.return_value = 'hashed_password_123'

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = None
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        # Mock database return
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }

        auth_create_user('test@example.com', 'testuser', 'plain_password')

        # Verify password was hashed
        mock_get_hash.assert_called_once_with('plain_password')

        # Verify database was called with hashed password
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert 'hashed_password_123' in call_args[1]
        mock_conn.commit.assert_called_once()

    @patch('app.routers.auth.get_user_by_email')
    def test_register_duplicate_email_fails(self, mock_get_user_by_email):
        """Test that registration fails for duplicate email."""
        # Mock that user already exists
        mock_get_user_by_email.return_value = {
            'id': 1,
            'email': 'existing@example.com',
            'username': 'existing',
            'is_active': True
        }

        request_data = {
            'email': 'existing@example.com',
            'username': 'newuser',
            'password': 'SecurePass123!'
        }

        response = client.post('/api/auth/register', json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert data['detail'] == 'Email already registered'

    def test_register_invalid_email_fails(self):
        """Test that registration fails for invalid email format."""
        request_data = {
            'email': 'invalid-email',
            'username': 'testuser',
            'password': 'SecurePass123!'
        }

        response = client.post('/api/auth/register', json=request_data)

        assert response.status_code == 422  # Validation error

    def test_register_short_password_fails(self):
        """Test that registration fails for password too short."""
        request_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'short'
        }

        response = client.post('/api/auth/register', json=request_data)

        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test cases for user login and JWT token generation."""

    @patch('app.routers.auth.update_user_ip_address')
    @patch('app.routers.auth.get_client_ip', return_value='127.0.0.1')
    @patch('app.routers.auth.get_user_by_id')
    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.verify_password')
    def test_login_sets_cookie_and_returns_user(self, mock_verify_password, mock_get_user_by_email, mock_get_user_by_id, mock_ip, mock_update_ip):
        """Successful login issues an HttpOnly cookie and returns sanitized user info."""
        client.cookies.clear()

        created_at = datetime.utcnow()
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'hashed_password': 'hashed_password',
            'is_active': True,
            'created_at': created_at,
        }
        mock_get_user_by_email.return_value = mock_user
        mock_verify_password.return_value = True
        mock_get_user_by_id.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': created_at,
        }

        request_data = {
            'email': 'test@example.com',
            'password': 'correct_password'
        }

        response = client.post('/api/auth/login', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'
        assert data['is_active'] is True

        cookie_value = response.cookies.get(settings.auth_cookie_name)
        assert cookie_value

        csrf_cookie = response.cookies.get(settings.csrf_cookie_name)
        assert csrf_cookie
        assert response.headers.get(settings.csrf_header_name) == csrf_cookie

        set_cookie_header = response.headers.get('set-cookie', '')
        assert settings.auth_cookie_name in set_cookie_header
        assert 'HttpOnly' in set_cookie_header

        decoded = jwt.decode(cookie_value, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded['sub'] == '1'
        assert 'exp' in decoded

    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.verify_password')
    def test_login_wrong_password_fails(self, mock_verify_password, mock_get_user_by_email):
        """Test that login fails with wrong password."""
        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'hashed_password': 'hashed_password',
            'is_active': True
        }
        mock_get_user_by_email.return_value = mock_user
        mock_verify_password.return_value = False  # Wrong password

        # Test login with wrong password
        request_data = {
            'email': 'test@example.com',
            'password': 'wrong_password'
        }

        client.cookies.clear()
        response = client.post('/api/auth/login', json=request_data)

        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Incorrect email or password'

    @patch('app.routers.auth.get_user_by_email')
    def test_login_nonexistent_user_fails(self, mock_get_user_by_email):
        """Test that login fails for non-existent user."""
        mock_get_user_by_email.return_value = None

        request_data = {
            'email': 'nonexistent@example.com',
            'password': 'password123'
        }

        client.cookies.clear()
        response = client.post('/api/auth/login', json=request_data)

        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Incorrect email or password'

    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.verify_password')
    def test_login_inactive_user_fails(self, mock_verify_password, mock_get_user_by_email):
        """Test that login fails for inactive user."""
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'hashed_password': 'hashed_password',
            'is_active': False
        }
        mock_get_user_by_email.return_value = mock_user
        mock_verify_password.return_value = True

        request_data = {
            'email': 'test@example.com',
            'password': 'correct_password'
        }

        client.cookies.clear()
        response = client.post('/api/auth/login', json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert data['detail'] == 'Inactive user account'

    def test_logout_clears_cookie(self):
        """Logout endpoint clears the auth cookie."""
        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, 'dummy')
        headers = _csrf_headers()

        response = client.post('/api/auth/logout', headers=headers)

        assert response.status_code == 204
        set_cookie_header = "; ".join(response.headers.get_list('set-cookie'))
        assert settings.auth_cookie_name in set_cookie_header
        assert settings.csrf_cookie_name in set_cookie_header
        assert 'max-age=0' in set_cookie_header.lower()

    def test_jwt_token_contains_user_id(self):
        """Test that JWT token contains user ID in subject claim."""
        token = create_access_token(data={'sub': '123'})

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded['sub'] == '123'

    def test_jwt_token_has_expiration(self):
        """Test that JWT token has expiration time."""
        token = create_access_token(data={'sub': '123'})

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert 'exp' in decoded

        # Verify expiration is in the future
        exp_time = datetime.fromtimestamp(decoded['exp'])
        assert exp_time > datetime.utcnow()


class TestProtectedEndpointAccess:
    """Test cases for protected API endpoints."""

    @patch('app.auth.get_user_by_id')
    def test_protected_endpoint_denies_access_without_token(self, mock_get_user_by_id):
        """Test that protected API endpoints deny access without a valid JWT token."""
        # Test history endpoint (requires authentication)
        # Don't provide Authorization header at all
        client.cookies.clear()
        response = client.get('/api/history')

        # When no token is provided, oauth2_scheme returns None
        # and get_current_user should raise 401
        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Could not validate credentials'

    def test_protected_endpoint_denies_access_with_invalid_token(self):
        """Test that protected endpoints deny access with invalid token."""
        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, 'invalid_token_123')
        response = client.get('/api/history')

        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Could not validate credentials'

    def test_protected_endpoint_denies_access_with_expired_token(self):
        """Test that protected endpoints deny access with expired token."""
        # Create expired token
        expired_token = create_access_token(
            data={'sub': '1'},
            expires_delta=timedelta(minutes=-10)
        )

        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, expired_token)
        response = client.get('/api/history')

        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Could not validate credentials'

    def test_protected_endpoint_denies_access_with_malformed_token(self):
        """Test that protected endpoints deny access with malformed token."""
        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, 'not.a.jwt.token')
        response = client.get('/api/history')

        assert response.status_code == 401

    @patch('app.auth.get_user_by_id')
    @patch('app.main.question_service')
    def test_protected_endpoint_allows_access_with_valid_token(
        self, mock_service, mock_get_user_by_id
    ):
        """Test that protected API endpoints allow access with a valid JWT token."""
        # Create valid token
        token = create_access_token(data={'sub': '1'})

        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user

        # Mock service response
        from app.models.schemas import HistoryResponse
        mock_service.get_user_history.return_value = HistoryResponse(
            questions=[],
            total=0
        )

        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, token)
        response = client.get('/api/history')

        assert response.status_code == 200
        data = response.json()
        assert 'questions' in data
        assert 'total' in data

    @patch('app.auth.get_user_by_id')
    def test_get_current_user_endpoint_with_valid_token(self, mock_get_user_by_id):
        """Test /me endpoint returns user info with valid token."""
        token = create_access_token(data={'sub': '1'})

        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user

        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, token)
        response = client.get('/api/auth/me')

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 1
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'


class TestSavedAnswersAssociation:
    """Test cases for saved answers association with authenticated users."""

    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.save_answer')
    @patch('app.database.SavedAnswersRepository.get_user_saved_answers')
    def test_saved_answer_associated_with_authenticated_user(
        self, mock_get_saved, mock_save_answer, mock_get_user_by_id
    ):
        """Test that saved answers are correctly associated with the authenticated user."""
        # Create valid token for user ID 1
        token = create_access_token(data={'sub': '1'})

        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user

        # Mock save answer
        mock_save_answer.return_value = {'id': 1}

        # Mock get saved answers
        mock_saved_answer = {
            'id': 1,
            'question_id': 123,
            'question': 'What is love?',
            'answer': 'God is love',
            'tags': ['love', 'god'],
            'saved_at': datetime.utcnow()
        }
        mock_get_saved.return_value = [mock_saved_answer]

        # Test saving an answer
        request_data = {
            'question_id': 123,
            'tags': ['love', 'god']
        }

        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, token)
        headers = _csrf_headers()
        response = client.post('/api/saved-answers', json=request_data, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data['id'] == 1
        assert data['question_id'] == 123

        # Verify save_answer was called with correct user_id
        mock_save_answer.assert_called_once_with(
            user_id=1,
            question_id=123,
            tags=['love', 'god']
        )

    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.get_user_saved_answers')
    def test_get_saved_answers_returns_only_user_answers(
        self, mock_get_saved, mock_get_user_by_id
    ):
        """Test that getting saved answers returns only the authenticated user's answers."""
        # Create token for user ID 2
        token = create_access_token(data={'sub': '2'})

        # Mock user retrieval
        mock_user = {
            'id': 2,
            'email': 'user2@example.com',
            'username': 'user2',
            'is_active': True,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user

        # Mock saved answers for user 2
        mock_saved_answers = [
            {
                'id': 5,
                'question_id': 456,
                'question': 'Who is Jesus?',
                'answer': 'Jesus is the Son of God',
                'tags': ['jesus'],
                'saved_at': datetime.utcnow()
            }
        ]
        mock_get_saved.return_value = mock_saved_answers

        # Get saved answers
        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, token)
        response = client.get('/api/saved-answers')

        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['saved_answers']) == 1
        assert data['saved_answers'][0]['id'] == 5

        # Verify get_user_saved_answers was called with user_id=2
        mock_get_saved.assert_called_once_with(user_id=2, limit=100)

    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.delete_saved_answer')
    def test_delete_saved_answer_only_for_authenticated_user(
        self, mock_delete, mock_get_user_by_id
    ):
        """Test that user can only delete their own saved answers."""
        token = create_access_token(data={'sub': '1'})

        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user
        mock_delete.return_value = True

        # Delete saved answer
        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, token)
        headers = _csrf_headers()
        response = client.delete('/api/saved-answers/123', headers=headers)

        assert response.status_code == 204

        # Verify delete was called with correct user_id
        mock_delete.assert_called_once_with(user_id=1, saved_answer_id=123)

    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.save_answer')
    def test_saved_answer_creation_requires_csrf_header(
        self, mock_save_answer, mock_get_user_by_id
    ):
        """Authenticated requests without a CSRF header should be rejected."""
        token = create_access_token(data={'sub': '1'})

        mock_get_user_by_id.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }

        client.cookies.clear()
        client.cookies.set(settings.auth_cookie_name, token)

        response = client.post('/api/saved-answers', json={'question_id': 1, 'tags': []})

        assert response.status_code == 403
        mock_save_answer.assert_not_called()

    @patch('app.auth.get_user_by_id')
    def test_saved_answers_endpoint_denies_access_without_token(self, mock_get_user_by_id):
        """Test that saved answers endpoints require authentication."""
        client.cookies.clear()
        # Try to save answer without token
        request_data = {'question_id': 123, 'tags': []}
        response = client.post('/api/saved-answers', json=request_data)

        assert response.status_code == 401

        # Try to get saved answers without token
        response = client.get('/api/saved-answers')

        assert response.status_code == 401

        # Try to delete saved answer without token
        response = client.delete('/api/saved-answers/123')

        assert response.status_code == 401


class TestPasswordHashing:
    """Test cases for password hashing utilities."""

    @patch('app.auth.pwd_context')
    def test_password_hash_is_different_from_plain(self, mock_pwd_context):
        """Test that hashed password is different from plain password."""
        plain_password = 'SecurePass123!'
        mock_pwd_context.hash.return_value = '$2b$12$hashedpasswordvalue'

        hashed = get_password_hash(plain_password)

        assert hashed != plain_password
        assert len(hashed) > len(plain_password)
        mock_pwd_context.hash.assert_called_once_with(plain_password)

    @patch('app.auth.pwd_context')
    def test_verify_password_with_correct_password(self, mock_pwd_context):
        """Test password verification with correct password."""
        plain_password = 'SecurePass123!'
        hashed = '$2b$12$hashedpasswordvalue'
        mock_pwd_context.hash.return_value = hashed
        mock_pwd_context.verify.return_value = True

        result = verify_password(plain_password, hashed)

        assert result is True
        mock_pwd_context.verify.assert_called_once_with(plain_password, hashed)

    @patch('app.auth.pwd_context')
    def test_verify_password_with_wrong_password(self, mock_pwd_context):
        """Test password verification with wrong password."""
        plain_password = 'SecurePass123!'
        hashed = '$2b$12$hashedpasswordvalue'
        mock_pwd_context.verify.return_value = False

        result = verify_password('WrongPassword', hashed)

        assert result is False

    @patch('app.auth.pwd_context')
    def test_same_password_generates_different_hashes(self, mock_pwd_context):
        """Test that same password generates different hashes (salt)."""
        plain_password = 'SecurePass123!'
        # Simulate different hashes with different salts
        mock_pwd_context.hash.side_effect = [
            '$2b$12$salt1hashedpasswordvalue',
            '$2b$12$salt2hashedpasswordvalue'
        ]
        mock_pwd_context.verify.return_value = True

        hash1 = get_password_hash(plain_password)
        hash2 = get_password_hash(plain_password)

        # Hashes should be different due to salt
        assert hash1 != hash2

        # Both should verify correctly
        assert verify_password(plain_password, hash1) is True
        assert verify_password(plain_password, hash2) is True


class TestAuthUtilities:
    """Additional tests covering auth helper functions."""

    @patch('app.auth.get_db_connection')
    def test_get_user_by_email(self, mock_get_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'tester',
            'hashed_password': 'hashed',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        result = get_user_by_email('test@example.com')
        assert result['email'] == 'test@example.com'

    @patch('app.auth.get_db_connection')
    def test_get_user_by_id(self, mock_get_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 2,
            'email': 'user@example.com',
            'username': 'user',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        result = get_user_by_id(2)
        assert result['id'] == 2

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={})
    async def test_get_current_user_missing_sub_raises(self, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='token')
        assert exc.value.status_code == 401
        mock_decode.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value=None)
    async def test_get_current_user_missing_user_raises(self, mock_get_user_by_id, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='token')
        assert exc.value.status_code == 401
        mock_get_user_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value={'id': 1, 'is_active': False})
    async def test_get_current_user_inactive(self, mock_get_user_by_id, mock_decode):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token='token')
        assert exc.value.status_code == 400
        mock_get_user_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_active_user(current_user={'is_active': False})
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_current_user_optional_no_token(self):
        result = await get_current_user_optional(token=None)
        assert result is None

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': None})
    async def test_get_current_user_optional_missing_sub(self, mock_decode):
        result = await get_current_user_optional(token='token')
        assert result is None
        mock_decode.assert_called_once_with('token', SECRET_KEY, algorithms=[ALGORITHM])

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', side_effect=JWTError('bad token'))
    async def test_get_current_user_optional_jwt_error(self, mock_decode):
        result = await get_current_user_optional(token='token')
        assert result is None
        mock_decode.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.auth.jwt.decode', return_value={'sub': '1'})
    @patch('app.auth.get_user_by_id', return_value={'id': 1, 'is_active': False})
    async def test_get_current_user_optional_inactive(self, mock_get_user_by_id, mock_decode):
        result = await get_current_user_optional(token='token')
        assert result is None
        mock_get_user_by_id.assert_called_once_with(1)
