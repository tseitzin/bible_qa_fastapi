"""Bible Q&A FastAPI Application."""
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import get_settings
from app.models.schemas import (
    QuestionRequest, QuestionResponse, 
    HistoryResponse, HealthCheck
)
from app.services.question_service import QuestionService
from app.utils.exceptions import DatabaseError, OpenAIError

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


@app.get("/", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow()
    )


@app.post("/api/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """Submit a Bible-related question and get an AI-generated answer."""
    try:
        result = await question_service.process_question(request)
        return result
    except (DatabaseError, OpenAIError):
        # Let custom error handlers handle these
        raise
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/history/{user_id}", response_model=HistoryResponse)
async def get_question_history(user_id: int, limit: int = 10):
    """Get question history for a user."""
    try:
        if limit > 100:
            limit = 100  # Reasonable limit
        
        history = question_service.get_user_history(user_id, limit)
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
