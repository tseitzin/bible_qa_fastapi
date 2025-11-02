"""Authentication utilities for JWT tokens and password hashing."""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import get_settings
from app.database import get_db_connection
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

settings = get_settings()

# JWT settings - these should be in your .env file
SECRET_KEY = settings.secret_key if hasattr(settings, 'secret_key') else "your-secret-key-change-this-in-production"
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


def get_user_by_email(email: str) -> Optional[dict]:
    """Get a user by email from the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, username, hashed_password, is_active, created_at FROM users WHERE email = %s",
                (email,)
            )
            return cur.fetchone()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get a user by ID from the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, username, is_active, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            return cur.fetchone()


def create_user(email: str, username: str, password: str) -> dict:
    """Create a new user in the database."""
    hashed_password = get_password_hash(password)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, username, hashed_password, is_active) 
                VALUES (%s, %s, %s, %s) 
                RETURNING id, email, username, is_active, created_at
                """,
                (email, username, hashed_password, True)
            )
            user = cur.fetchone()
            conn.commit()
            return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get the current authenticated user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
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


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get the current active user (additional check)."""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_user_optional(token: str = Depends(oauth2_scheme)) -> Optional[dict]:
    """Get the current user if authenticated, otherwise return None (for guest access)."""
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    user = get_user_by_id(int(user_id))
    if user is None or not user.get("is_active"):
        return None
    
    return user
