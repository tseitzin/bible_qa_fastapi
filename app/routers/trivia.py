"""Trivia router for BibleQuest - Scripture Scholar Trivia."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_or_create_guest_user
from app.models.schemas import (
    TriviaAnswerResultResponse,
    TriviaAnswerSubmitRequest,
    TriviaLeaderboardEntry,
    TriviaLeaderboardResponse,
    TriviaQuestionResponse,
    TriviaRoundResponse,
    TriviaSessionResultResponse,
    TriviaSessionSubmitRequest,
)
from app.repositories.trivia import TriviaRepository
from app.services.trivia_service import (
    VALID_CATEGORIES,
    VALID_DIFFICULTIES,
    TriviaService,
)
from app.utils.exceptions import DatabaseError, OpenAIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trivia", tags=["trivia"])

_service = TriviaService()


@router.get("/questions", response_model=TriviaRoundResponse)
async def get_questions(
    category: str = Query(..., description="Trivia category"),
    difficulty: str = Query(..., description="Difficulty level: easy, medium, hard"),
    count: int = Query(10, ge=5, le=20, description="Number of questions"),
    question_type: Optional[str] = Query(None, description="Question type filter"),
) -> TriviaRoundResponse:
    """Fetch a set of trivia questions for one game round."""
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    if difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid difficulty. Must be one of: {sorted(VALID_DIFFICULTIES)}",
        )

    try:
        questions = await _service.get_questions_for_round(category, difficulty, count, question_type)
        return TriviaRoundResponse(
            questions=[TriviaQuestionResponse(**q) for q in questions],
            category=category,
            difficulty=difficulty,
            total=len(questions),
        )
    except OpenAIError:
        raise
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error fetching trivia questions")
        raise HTTPException(status_code=500, detail="Failed to load trivia questions") from exc


@router.post("/sessions", response_model=TriviaSessionResultResponse)
async def submit_session(
    session_request: TriviaSessionSubmitRequest,
    user: Dict[str, Any] = Depends(get_or_create_guest_user),
) -> TriviaSessionResultResponse:
    """Submit a completed trivia game session and receive a scored result."""
    if session_request.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    if session_request.difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid difficulty. Must be one of: {sorted(VALID_DIFFICULTIES)}",
        )

    try:
        result = await _service.submit_game_session(user["id"], session_request)
        return TriviaSessionResultResponse(**result)
    except OpenAIError:
        raise
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error submitting trivia session")
        raise HTTPException(status_code=500, detail="Failed to submit trivia session") from exc


@router.get("/leaderboard", response_model=TriviaLeaderboardResponse)
async def get_leaderboard(
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    period: str = Query("all_time", description="Time period: all_time or weekly"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of entries"),
) -> TriviaLeaderboardResponse:
    """Return the trivia leaderboard, optionally filtered by category and difficulty."""
    if category is not None and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    if difficulty is not None and difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid difficulty. Must be one of: {sorted(VALID_DIFFICULTIES)}",
        )
    if period not in ("all_time", "weekly"):
        raise HTTPException(
            status_code=400,
            detail="Invalid period. Must be 'all_time' or 'weekly'",
        )

    try:
        entries = await _service.get_leaderboard(category, difficulty, period, limit)
        return TriviaLeaderboardResponse(
            entries=[TriviaLeaderboardEntry(**e) for e in entries],
            category=category,
            difficulty=difficulty,
            period=period,
            user_rank=None,
        )
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error fetching trivia leaderboard")
        raise HTTPException(status_code=500, detail="Failed to load leaderboard") from exc


@router.get("/daily-challenge", response_model=TriviaQuestionResponse)
async def get_daily_challenge() -> TriviaQuestionResponse:
    """Return today's daily challenge question (no auth required)."""
    try:
        question = await _service.get_daily_challenge()
        return TriviaQuestionResponse(**question)
    except OpenAIError:
        raise
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error fetching daily challenge")
        raise HTTPException(status_code=500, detail="Failed to load daily challenge") from exc


@router.post("/daily-challenge/submit", response_model=TriviaAnswerResultResponse)
async def submit_daily_challenge(
    answer_request: TriviaAnswerSubmitRequest,
    user: Dict[str, Any] = Depends(get_or_create_guest_user),
) -> TriviaAnswerResultResponse:
    """Submit an answer for the daily challenge question."""
    try:
        question = TriviaRepository.get_question_by_id(answer_request.question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        is_correct = answer_request.chosen_answer == question["correct_answer"]

        single_answer = {
            "question_id": answer_request.question_id,
            "chosen_answer": answer_request.chosen_answer,
            "is_correct": is_correct,
            "time_seconds": answer_request.time_seconds,
        }
        score_breakdown = _service.calculate_score(
            [single_answer], difficulty="medium", timer_enabled=answer_request.time_seconds is not None
        )

        return TriviaAnswerResultResponse(
            is_correct=is_correct,
            correct_answer=question["correct_answer"],
            explanation=question.get("explanation"),
            scripture_reference=question.get("scripture_reference"),
            score=score_breakdown["total_score"],
        )
    except HTTPException:
        raise
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error submitting daily challenge answer")
        raise HTTPException(status_code=500, detail="Failed to submit daily challenge") from exc
