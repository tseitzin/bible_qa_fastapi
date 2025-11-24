"""Pydantic models for request/response schemas."""
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any


class QuestionRequest(BaseModel):
    """Request model for asking questions."""
    question: str = Field(..., min_length=1, max_length=1000, description="The question to ask")
    user_id: int = Field(default=1, description="User ID (placeholder for future auth)")


class ConversationMessage(BaseModel):
    """Model for a single message in conversation history."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class FollowUpQuestionRequest(BaseModel):
    """Request model for follow-up questions."""
    question: str = Field(..., min_length=1, max_length=1000, description="The follow-up question")
    conversation_history: List[ConversationMessage] = Field(default_factory=list, description="Previous conversation context")
    user_id: int = Field(default=1, description="User ID")
    parent_question_id: Optional[int] = Field(None, description="ID of the original question this follows up on")


class QuestionResponse(BaseModel):
    """Response model for question answers."""
    answer: str = Field(..., description="The AI-generated answer")
    question_id: int = Field(..., description="The ID of the stored question")
    is_biblical: bool = Field(..., description="Whether the AI response is considered biblical")


class BibleVerseResponse(BaseModel):
    """Response model for Bible verse lookups."""
    reference: str = Field(..., description="Full verse reference, e.g. 'John 3:16'")
    book: str = Field(..., description="Book name")
    chapter: int = Field(..., ge=1, description="Chapter number")
    verse: int = Field(..., ge=1, description="Verse number")
    text: str = Field(..., description="Verse text")


class BiblePassageResponse(BaseModel):
    """Response model for multi-verse passage lookups."""
    reference: str = Field(..., description="Human-readable reference string")
    book: str = Field(..., description="Book name")
    chapter: int = Field(..., ge=1, description="Chapter number")
    end_chapter: Optional[int] = Field(default=None, description="Ending chapter when the passage spans multiple chapters")
    start_verse: Optional[int] = Field(default=None, description="First verse in the passage")
    end_verse: Optional[int] = Field(default=None, description="Last verse in the passage")
    verses: List[BibleVerseResponse] = Field(..., description="Ordered verses in the passage")


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


class RecentQuestionCreate(BaseModel):
    """Request model for manually recording a recent question."""
    question: str = Field(..., min_length=1, max_length=1000, description="Question text")


class RecentQuestionItem(BaseModel):
    """Response model for a single recent question entry."""
    id: int
    question: str
    asked_at: datetime


class RecentQuestionsResponse(BaseModel):
    """Response model wrapping recent questions list."""
    recent_questions: List[RecentQuestionItem]


class HealthCheck(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str = "1.0.0"


# Authentication Schemas
class UserCreate(BaseModel):
    """Request model for user registration."""
    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, max_length=100, description="Password")


class UserLogin(BaseModel):
    """Request model for user login."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="Password")


class User(BaseModel):
    """Response model for user data."""
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime


# Saved Answers Schemas
class SavedAnswerCreate(BaseModel):
    """Request model for saving an answer."""
    question_id: int = Field(..., description="ID of the question to save")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")


class ThreadItem(BaseModel):
    """Model for a single item in a conversation thread."""
    id: int
    question: str
    answer: Optional[str]
    parent_question_id: Optional[int]
    asked_at: datetime
    depth: int


class SavedAnswerResponse(BaseModel):
    """Response model for a saved answer."""
    id: int
    question_id: int
    question: str
    answer: str
    tags: List[str]
    saved_at: datetime
    parent_question_id: Optional[int] = None
    conversation_thread: List[ThreadItem] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class SavedAnswersListResponse(BaseModel):
    """Response model for list of saved answers."""
    saved_answers: List[SavedAnswerResponse]
    total: int


class CrossReferenceEntry(BaseModel):
    """Single cross reference entry."""
    reference: str
    note: Optional[str] = None


class CrossReferenceResponse(BaseModel):
    """Response for cross reference lookups."""
    book: str
    chapter: int
    verse: int
    references: List[CrossReferenceEntry]


class TopicReferenceEntry(BaseModel):
    """Reference associated with a topical theme."""
    passage: str
    note: Optional[str] = None


class TopicEntry(BaseModel):
    """Single topical index item."""
    topic: str
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    references: List[TopicReferenceEntry] = Field(default_factory=list)


class TopicSearchResponse(BaseModel):
    """Wrapper for topical search results."""
    keyword: Optional[str] = None
    results: List[TopicEntry]


class ReadingPlanMeta(BaseModel):
    """Metadata describing a reading plan."""
    slug: str
    name: str
    description: Optional[str] = None
    duration_days: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadingPlanScheduleItem(BaseModel):
    """Single day entry for a reading plan."""
    day_number: int
    title: str
    passage: str
    notes: Optional[str] = None
    scheduled_date: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadingPlanDetailResponse(BaseModel):
    """Detailed reading plan payload."""
    plan: ReadingPlanMeta
    schedule: List[ReadingPlanScheduleItem]


class DevotionalTemplate(BaseModel):
    """Template metadata for devotional generation."""
    slug: str
    title: str
    body: str
    prompt_1: str
    prompt_2: str
    default_passage: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DevotionalRequest(BaseModel):
    """Request payload for devotional generation."""
    topic: str = Field(..., min_length=2)
    template_slug: Optional[str] = Field(default="classic", description="Slug of template to use")
    passage: Optional[str] = None
    plan_slug: Optional[str] = None
    day: Optional[int] = Field(default=None, ge=1)


class GeneratedDevotionalResponse(BaseModel):
    """Response body for devotional generation."""
    title: str
    passage: Optional[str] = None
    summary: str
    reflection_questions: List[str]
    supporting_reading: Optional[ReadingPlanScheduleItem] = None

