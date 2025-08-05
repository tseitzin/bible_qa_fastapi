"""Pydantic models for request/response schemas."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class QuestionRequest(BaseModel):
    """Request model for asking questions."""
    question: str = Field(..., min_length=1, max_length=1000, description="The question to ask")
    user_id: int = Field(default=1, description="User ID (placeholder for future auth)")


class QuestionResponse(BaseModel):
    """Response model for question answers."""
    answer: str = Field(..., description="The AI-generated answer")
    question_id: int = Field(..., description="The ID of the stored question")


class HistoryItem(BaseModel):
    """Model for question history items."""
    id: int
    question: str
    answer: Optional[str]
    created_at: datetime


class HistoryResponse(BaseModel):
    """Response model for question history."""
    questions: list[HistoryItem]
    total: int


class HealthCheck(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str = "1.0.0"
