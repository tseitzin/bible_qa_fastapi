"""Custom exceptions for the Bible Q&A API."""
from fastapi import HTTPException


class DatabaseError(HTTPException):
    """Database-related errors."""
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(status_code=500, detail=detail)


class OpenAIError(HTTPException):
    """OpenAI API-related errors."""
    def __init__(self, detail: str = "AI service unavailable"):
        super().__init__(status_code=503, detail=detail)


class ValidationError(HTTPException):
    """Input validation errors."""
    def __init__(self, detail: str = "Invalid input"):
        super().__init__(status_code=400, detail=detail)
