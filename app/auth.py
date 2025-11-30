"""Authentication utilities for JWT tokens and password hashing."""
from datetime import datetime, timedelta
from typing import Optional
import inspect
import secrets
import uuid

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security.utils import get_authorization_scheme_param
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.database import get_db_connection
from app.models.schemas import User

import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

settings = get_settings()

# JWT settings - these should be in environment variables for production
SECRET_KEY = settings.secret_key if hasattr(settings, "secret_key") else "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _extract_token_from_request(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None

    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        return token

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    scheme, param = get_authorization_scheme_param(auth_header)
    if scheme.lower() != "bearer":
        return None
    return param


async def _resolve_dependency_override(request: Optional[Request], dependency):
    """Return override result and flag if FastAPI dependency override exists."""
    if request is None:
        return None, False

    overrides = getattr(getattr(request, "app", None), "dependency_overrides", None)
    if not overrides:
        return None, False

    override = overrides.get(dependency)
    if override is None:
        return None, False

    result = override()
    if inspect.isawaitable(result):
        result = await result
    return result, True


def generate_csrf_token() -> str:
    """Return a random token for CSRF double submit protection."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Persist the CSRF token in a cookie accessible to browser JavaScript."""
    cookie_domain = settings.auth_cookie_domain or None
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=settings.csrf_cookie_max_age,
        httponly=False,
        secure=settings.csrf_cookie_secure,
        samesite=settings.csrf_cookie_samesite,
        domain=cookie_domain,
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    """Remove the CSRF cookie from the client."""
    cookie_domain = settings.auth_cookie_domain or None
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        domain=cookie_domain,
        path="/",
    )


def set_auth_cookie(response: Response, token: str) -> None:
    """Persist the JWT in an HttpOnly cookie."""
    cookie_domain = settings.auth_cookie_domain or None
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_cookie_max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=cookie_domain,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Remove the authentication cookie from the client."""
    cookie_domain = settings.auth_cookie_domain or None
    response.delete_cookie(
        key=settings.auth_cookie_name,
        domain=cookie_domain,
        path="/",
    )


def _convert_user(row: Optional[dict]) -> Optional[dict]:
    """Normalize database rows to plain dicts for downstream consumers."""
    if not row:
        return None
    # RealDictRow already behaves like a dict but ensure plain dict copy for safety
    return {
        "id": row["id"],
        "email": row["email"],
        "username": row["username"],
        "is_active": row["is_active"],
        "is_admin": row.get("is_admin", False),
        "created_at": row["created_at"],
        **({"hashed_password": row["hashed_password"]} if "hashed_password" in row else {})
    }


def get_user_by_email(email: str) -> Optional[dict]:
    """Get a user by email from the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, username, hashed_password, is_active, is_admin, created_at FROM users WHERE email = %s",
                (email,)
            )
            return _convert_user(cur.fetchone())


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get a user by ID from the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, username, is_active, is_admin, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            return _convert_user(cur.fetchone())


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request, handling proxies."""
    # Check X-Forwarded-For header (set by proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs; take the first (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (set by some proxies)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    if request.client and request.client.host:
        return request.client.host
    
    return "unknown"


def create_guest_user(ip_address: str) -> dict:
    """Create a unique anonymous guest user."""
    # Generate unique username using UUID
    guest_username = f"guest_{uuid.uuid4().hex[:12]}"
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, email, is_active, is_admin, is_guest, last_ip_address)
                VALUES (%s, NULL, TRUE, FALSE, TRUE, %s)
                RETURNING id, email, username, is_active, is_admin, is_guest, last_ip_address, created_at
                """,
                (guest_username, ip_address)
            )
            user = cur.fetchone()
            conn.commit()
            
            # Convert to dict format
            if user:
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "username": user["username"],
                    "is_active": user["is_active"],
                    "is_admin": user["is_admin"],
                    "is_guest": user.get("is_guest", True),
                    "last_ip_address": user.get("last_ip_address"),
                    "created_at": user["created_at"]
                }
            return None


def create_user(email: str, username: str, password: str, ip_address: Optional[str] = None) -> dict:
    """Create a new registered user in the database."""
    hashed_password = get_password_hash(password)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, username, hashed_password, is_active, is_admin, is_guest, last_ip_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, email, username, is_active, is_admin, created_at
                """,
                (email, username, hashed_password, True, False, False, ip_address)
            )
            user = cur.fetchone()
            conn.commit()
            return _convert_user(user)


async def get_current_user(
    request: Optional[Request] = None,
    token: Optional[str] = None,
) -> dict:
    """Get the current authenticated user from the JWT token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_value = token or _extract_token_from_request(request)
    if not token_value:
        raise credentials_exception

    try:
        payload = jwt.decode(token_value, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(int(user_id))
    if user is None:
        raise credentials_exception

    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


async def get_current_user_optional(
    request: Optional[Request] = None,
    token: Optional[str] = None,
) -> Optional[dict]:
    """Get the current user if authenticated, otherwise return None (for guest access)."""

    token_value = token or _extract_token_from_request(request)
    if not token_value:
        return None

    try:
        payload = jwt.decode(token_value, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    user = get_user_by_id(int(user_id))
    if user is None or not user.get("is_active"):
        return None

    return user


async def get_current_user_dependency(request: Request) -> dict:
    """Wrapper for FastAPI dependency injection of required current user."""
    override_value = await _resolve_dependency_override(request, get_current_user_dependency)
    if override_value[1]:
        return override_value[0]

    override_value = await _resolve_dependency_override(request, get_current_user)
    if override_value[1]:
        return override_value[0]

    return await get_current_user(request=request)


async def get_current_user_optional_dependency(request: Request) -> Optional[dict]:
    """Wrapper for FastAPI dependency injection of optional current user."""
    override_value = await _resolve_dependency_override(request, get_current_user_optional_dependency)
    if override_value[1]:
        return override_value[0]

    override_value = await _resolve_dependency_override(request, get_current_user_optional)
    if override_value[1]:
        return override_value[0]

    return await get_current_user_optional(request=request)


async def get_current_active_user(current_user: dict = Depends(get_current_user_dependency)) -> dict:
    """Get the current active user (additional check)."""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(current_user: dict = Depends(get_current_user_dependency)) -> dict:
    """Require current user to be admin."""
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


GUEST_USER_COOKIE_NAME = "guest_user_id"


async def get_or_create_guest_user(request: Request, response: Response = None) -> dict:
    """Get authenticated user or create a guest user if not authenticated.
    
    This ensures every request has a user associated with it for tracking purposes.
    Guest users are uniquely identified and tracked.
    """
    # First try to get authenticated user
    override_value = await _resolve_dependency_override(request, get_current_user_optional_dependency)
    if override_value[1]:
        user = override_value[0]
        if user:
            return user
    
    # Try normal auth
    user = await get_current_user_optional(request=request)
    if user:
        return user
    
    # No authenticated user - check for existing guest user in cookie
    guest_user_id = request.cookies.get(GUEST_USER_COOKIE_NAME)
    if guest_user_id:
        try:
            guest_user = get_user_by_id(int(guest_user_id))
            if guest_user and guest_user.get("is_guest", False):
                return guest_user
        except (ValueError, TypeError):
            pass  # Invalid guest user ID, create new one
    
    # Create new guest user
    ip_address = get_client_ip(request)
    guest_user = create_guest_user(ip_address)
    
    # Store guest user ID in cookie if response object is available
    # Note: Response object needs to be injected via dependency for cookie setting
    if response and guest_user:
        response.set_cookie(
            key=GUEST_USER_COOKIE_NAME,
            value=str(guest_user["id"]),
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
            path="/",
        )
    
    return guest_user


async def get_or_create_guest_user_dependency(request: Request) -> dict:
    """FastAPI dependency that ensures a user (authenticated or guest) exists."""
    override_value = await _resolve_dependency_override(request, get_or_create_guest_user_dependency)
    if override_value[1]:
        return override_value[0]
    
    return await get_or_create_guest_user(request)
