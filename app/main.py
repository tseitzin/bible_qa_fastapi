"""Bible Q&A FastAPI Application."""
from datetime import datetime
from typing import Annotated, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import json
import logging

from app.config import get_settings
from app.database import initialize_connection_pool, close_connection_pool
from app.services.cache_service import initialize_redis, close_redis
from app.models.schemas import (
    QuestionRequest, QuestionResponse, FollowUpQuestionRequest,
    HistoryResponse, HealthCheck
)
from app.services.question_service import QuestionService
from app.utils.exceptions import DatabaseError, OpenAIError
from app.auth import (
    get_current_user_dependency,
    get_current_user_optional_dependency,
)
from app.routers import auth, saved_answers, bible, recent_questions, study_resources, user_reading_plans, admin_api_logs, admin_users
from app.middleware.csrf import CSRFMiddleware
from app.middleware.api_request_logging import ApiRequestLoggingMiddleware
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

app.add_middleware(CSRFMiddleware, settings=settings)

# Add API request logging middleware
app.add_middleware(ApiRequestLoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.herokuapp\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize resources on application startup."""
    logger.info("Initializing application resources...")
    try:
        # Initialize database connection pool
        initialize_connection_pool(minconn=2, maxconn=20)
        
        # Initialize Redis cache
        initialize_redis()
        
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    logger.info("Shutting down application...")
    try:
        close_connection_pool()
        close_redis()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Initialize services
question_service = QuestionService()

# Include routers
app.include_router(auth.router)
app.include_router(saved_answers.router)
app.include_router(bible.router)
app.include_router(recent_questions.router)
app.include_router(study_resources.router)
app.include_router(user_reading_plans.router)
app.include_router(mcp_router)
app.include_router(admin_api_logs.router)
app.include_router(admin_users.router)

CurrentUser = Annotated[Dict[str, Any], Depends(get_current_user_dependency)]
OptionalCurrentUser = Annotated[Optional[Dict[str, Any]], Depends(get_current_user_optional_dependency)]


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
    current_user: OptionalCurrentUser
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


@app.post("/api/ask/stream")
async def ask_question_stream(
    request: QuestionRequest,
    current_user: OptionalCurrentUser
):
    """Submit a Bible-related question and get a streamed AI-generated answer.
    
    Returns Server-Sent Events (SSE) with the following event types:
    - cached: Complete cached answer (instant)
    - status: Status update during processing
    - content: Streaming text chunks
    - done: Processing complete with question_id
    - error: Error occurred
    """
    try:
        # Use authenticated user's ID if logged in, otherwise use default guest ID
        if current_user:
            request.user_id = current_user["id"]
        else:
            request.user_id = 1  # Guest user ID
        
        async def generate():
            try:
                async for chunk in question_service.stream_question(
                    request,
                    record_recent=bool(current_user)
                ):
                    # Format as Server-Sent Events
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as e:
                logger.error(f"Error in stream: {e}")
                yield f"data: {{\"type\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
    except (DatabaseError, OpenAIError):
        raise
    except Exception as e:
        logger.error(f"Error setting up stream: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/ask/followup", response_model=QuestionResponse)
async def ask_followup_question(
    request: FollowUpQuestionRequest,
    current_user: OptionalCurrentUser
):
    """Submit a follow-up question with conversation context."""
    try:
        # Use authenticated user's ID if logged in, otherwise use default guest ID
        if current_user:
            request.user_id = current_user["id"]
        else:
            request.user_id = 1  # Guest user ID
        
        # Follow-up questions should not appear in the "recent questions" list
        result = await question_service.process_followup_question(
            request,
            record_recent=False
        )
        return result
    except (DatabaseError, OpenAIError):
        # Let custom error handlers handle these
        raise
    except Exception as e:
        logger.error(f"Error processing follow-up question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/ask/followup/stream")
async def ask_followup_question_stream(
    request: FollowUpQuestionRequest,
    current_user: OptionalCurrentUser
):
    """Submit a follow-up question with conversation context and get a streamed answer.
    
    Returns Server-Sent Events (SSE) with the following event types:
    - cached: Complete cached answer (instant)
    - status: Status update during processing
    - content: Streaming text chunks
    - done: Processing complete with question_id
    - error: Error occurred
    """
    try:
        # Use authenticated user's ID if logged in, otherwise use default guest ID
        if current_user:
            request.user_id = current_user["id"]
        else:
            request.user_id = 1  # Guest user ID
        
        async def generate():
            try:
                async for chunk in question_service.stream_followup_question(
                    request,
                    record_recent=False  # Follow-ups don't go in recent questions
                ):
                    # Format as Server-Sent Events
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as e:
                logger.error(f"Error in follow-up stream: {e}")
                yield f"data: {{\"type\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
    except (DatabaseError, OpenAIError):
        raise
    except Exception as e:
        logger.error(f"Error setting up follow-up stream: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/history", response_model=HistoryResponse)
async def get_question_history(
    current_user: CurrentUser,
    limit: int = 10,
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


# Admin endpoints
from app.auth import get_current_admin_user
from app.database import QuestionRepository, SavedAnswersRepository


@app.delete("/api/admin/questions/{question_id}")
async def admin_delete_question(question_id: int, current_admin: dict = Depends(get_current_admin_user)):
    """Delete a question by ID (admin only)."""
    try:
        deleted = QuestionRepository.delete_question(question_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Question not found")
        return {"status": "deleted", "question_id": question_id}
    except Exception as e:
        logger.error(f"Admin delete question error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/admin/saved_answers/{answer_id}")
async def admin_delete_saved_answer(answer_id: int, current_admin: dict = Depends(get_current_admin_user)):
    """Delete a saved answer by ID (admin only)."""
    try:
        deleted = SavedAnswersRepository.admin_delete_saved_answer(answer_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Saved answer not found")
        return {"status": "deleted", "answer_id": answer_id}
    except Exception as e:
        logger.error(f"Admin delete saved answer error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
