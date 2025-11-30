"""Authentication routes for user registration and login."""
from fastapi import APIRouter, HTTPException, Request, Response, status
from app.models.schemas import UserCreate, UserLogin, User
from app.auth import (
    create_user,
    get_user_by_email,
    verify_password,
    create_access_token,
    get_current_user,
    set_auth_cookie,
    clear_auth_cookie,
    get_user_by_id,
    generate_csrf_token,
    set_csrf_cookie,
    clear_csrf_cookie,
)
from app.config import get_settings
import logging
from psycopg2 import IntegrityError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
settings = get_settings()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register a new user."""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        user = create_user(
            email=user_data.email,
            username=user_data.username,
            password=user_data.password
        )
        
        logger.info(f"New user registered: {user['email']}")
        return User.model_validate(user).model_dump()
    
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login")
async def login(credentials: UserLogin, response: Response):
    """Authenticate user and establish a session via secure cookie."""
    user = get_user_by_email(credentials.email)
    
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user["id"])})
    set_auth_cookie(response, access_token)

    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)
    response.headers[settings.csrf_header_name] = csrf_token

    logger.info(f"User logged in: {user['email']}")

    sanitized_user = get_user_by_id(user["id"]) or {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "is_active": user["is_active"],
        "is_admin": user.get("is_admin", False),
        "created_at": user.get("created_at"),
    }
    return User.model_validate(sanitized_user).model_dump()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Terminate the current session by clearing the auth cookie."""
    clear_auth_cookie(response)
    clear_csrf_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me")
async def get_current_user_info(request: Request):
    """Get current authenticated user information."""
    current_user = await get_current_user(request=request)
    return User.model_validate(current_user).model_dump()
