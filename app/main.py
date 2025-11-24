"""Bible Q&A FastAPI Application."""
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import get_settings
from app.models.schemas import (
    QuestionRequest, QuestionResponse, FollowUpQuestionRequest,
    HistoryResponse, HealthCheck
)
from app.services.question_service import QuestionService
from app.utils.exceptions import DatabaseError, OpenAIError
from app.auth import get_current_user, get_current_user_optional
from app.routers import auth, saved_answers, bible, recent_questions, study_resources
from app.mcp.router import router as mcp_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Log CORS configuration for debugging
logger.info(f"CORS allowed origins: {settings.allowed_origins}")
# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered Bible Q&A API",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.herokuapp\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
question_service = QuestionService()

# Include routers
app.include_router(auth.router)
app.include_router(saved_answers.router)
app.include_router(bible.router)
app.include_router(recent_questions.router)
app.include_router(study_resources.router)
app.include_router(mcp_router)


@app.get("/", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow()
    )


@app.post("/api/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """Submit a Bible-related question and get an AI-generated answer (guest or authenticated)."""
    try:
        # Use authenticated user's ID if logged in, otherwise use default guest ID
        if current_user:
            request.user_id = current_user["id"]
        else:
            request.user_id = 1  # Guest user ID
        
        result = await question_service.process_question(
            request,
            record_recent=bool(current_user)
        )
        return result
    except (DatabaseError, OpenAIError):
        # Let custom error handlers handle these
        raise
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/ask/followup", response_model=QuestionResponse)
async def ask_followup_question(
    request: FollowUpQuestionRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """Submit a follow-up question with conversation context."""
    try:
        # Use authenticated user's ID if logged in, otherwise use default guest ID
        if current_user:
            request.user_id = current_user["id"]
        else:
            request.user_id = 1  # Guest user ID
        
        result = await question_service.process_followup_question(
            request,
            record_recent=bool(current_user)
        )
        return result
    except (DatabaseError, OpenAIError):
        # Let custom error handlers handle these
        raise
    except Exception as e:
        logger.error(f"Error processing follow-up question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/history", response_model=HistoryResponse)
async def get_question_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get question history for authenticated user."""
    try:
        if limit > 100:
            limit = 100  # Reasonable limit
        
        history = question_service.get_user_history(current_user["id"], limit)
        return history
    except (DatabaseError, OpenAIError):
        # Let custom error handlers handle these
        raise
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handlers
@app.exception_handler(DatabaseError)
async def database_error_handler(request, exc):
    logger.error(f"Database error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(OpenAIError)
async def openai_error_handler(request, exc):
    logger.error(f"OpenAI error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
