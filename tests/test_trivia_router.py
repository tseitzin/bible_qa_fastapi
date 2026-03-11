"""Unit tests for the /api/trivia router endpoints."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_or_create_guest_user


# ---------------------------------------------------------------------------
# Module-level test client
# ---------------------------------------------------------------------------

client = TestClient(app)

# A guest user returned by the auth dependency override
_GUEST_USER = {
    "id": 99,
    "email": "guest_abc@guest.local",
    "username": "guest_abc",
    "is_active": True,
    "is_admin": False,
    "is_guest": True,
}


@pytest.fixture(autouse=True)
def clear_overrides():
    """Reset dependency overrides before and after every test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def guest_auth():
    """Override get_or_create_guest_user to bypass real auth logic."""
    async def _override():
        return _GUEST_USER

    app.dependency_overrides[get_or_create_guest_user] = _override


# ---------------------------------------------------------------------------
# Helper: build a minimal safe question dict (no correct_answer)
# ---------------------------------------------------------------------------

def _safe_question(
    qid: int = 1,
    text: str = "Who led the Israelites out of Egypt?",
    category: str = "old_testament",
    difficulty: str = "easy",
) -> dict:
    return {
        "id": qid,
        "question_text": text,
        "question_type": "multiple_choice",
        "category": category,
        "difficulty": difficulty,
        "options": ["Moses", "Aaron", "Joshua", "Caleb"],
        "scripture_reference": "Exodus 14:21",
    }


# ---------------------------------------------------------------------------
# GET /api/trivia/questions
# ---------------------------------------------------------------------------

class TestGetQuestions:

    def test_returns_correct_top_level_fields(self):
        """Response contains questions, total, category, difficulty."""
        safe_questions = [_safe_question(qid=i) for i in range(1, 6)]

        with patch(
            "app.routers.trivia._service.get_questions_for_round",
            new_callable=AsyncMock,
            return_value=safe_questions,
        ):
            response = client.get(
                "/api/trivia/questions",
                params={"category": "old_testament", "difficulty": "easy", "count": 5},
            )

        assert response.status_code == 200
        data = response.json()
        assert "questions" in data
        assert "total" in data
        assert "category" in data
        assert "difficulty" in data
        assert data["category"] == "old_testament"
        assert data["difficulty"] == "easy"
        assert data["total"] == 5

    def test_correct_answer_not_in_questions(self):
        """The correct_answer field must never be returned to the client."""
        # Deliberately include correct_answer to verify the router strips it
        questions_with_answer = [
            {**_safe_question(qid=1), "correct_answer": "Moses", "correct_index": 0}
        ]

        with patch(
            "app.routers.trivia._service.get_questions_for_round",
            new_callable=AsyncMock,
            return_value=questions_with_answer,
        ):
            response = client.get(
                "/api/trivia/questions",
                params={"category": "old_testament", "difficulty": "easy", "count": 5},
            )

        assert response.status_code == 200
        for q in response.json()["questions"]:
            assert "correct_answer" not in q
            # correct_index is intentionally included for client-side visual feedback

    def test_invalid_category_returns_400(self):
        """An unrecognised category string → HTTP 400."""
        response = client.get(
            "/api/trivia/questions",
            params={"category": "invalid_cat", "difficulty": "easy", "count": 5},
        )
        assert response.status_code == 400
        assert "category" in response.json()["detail"].lower()

    def test_invalid_difficulty_returns_400(self):
        """An unrecognised difficulty string → HTTP 400."""
        response = client.get(
            "/api/trivia/questions",
            params={"category": "old_testament", "difficulty": "expert", "count": 5},
        )
        assert response.status_code == 400
        assert "difficulty" in response.json()["detail"].lower()

    def test_missing_category_returns_422(self):
        """Omitting a required query parameter → HTTP 422 from FastAPI validation."""
        response = client.get(
            "/api/trivia/questions",
            params={"difficulty": "easy", "count": 5},
        )
        assert response.status_code == 422

    def test_missing_difficulty_returns_422(self):
        response = client.get(
            "/api/trivia/questions",
            params={"category": "old_testament", "count": 5},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/trivia/sessions
# ---------------------------------------------------------------------------

class TestSubmitSession:

    def test_valid_session_returns_score_breakdown(self, guest_auth):
        """A valid session submission must return session_id and score_breakdown."""
        mock_result = {
            "session_id": 77,
            "score_breakdown": {
                "total_score": 300,
                "base_score": 300,
                "time_bonus": 0,
                "streak_bonus": 0,
                "correct_count": 3,
                "accuracy_percent": 60.0,
                "streak_max": 3,
            },
            "leaderboard_position": None,
            "answers_review": [],
        }

        with patch(
            "app.routers.trivia._service.submit_game_session",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = client.post(
                "/api/trivia/sessions",
                json={
                    "category": "old_testament",
                    "difficulty": "easy",
                    "question_count": 5,
                    "answers": [
                        {
                            "question_id": 1,
                            "chosen_answer": "Moses",
                            "is_correct": True,
                            "time_seconds": None,
                        }
                    ],
                    "timer_enabled": False,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == 77
        assert "score_breakdown" in data
        assert data["score_breakdown"]["total_score"] == 300

    def test_invalid_category_returns_400(self, guest_auth):
        response = client.post(
            "/api/trivia/sessions",
            json={
                "category": "bad_category",
                "difficulty": "easy",
                "question_count": 5,
                "answers": [],
            },
        )
        assert response.status_code == 400

    def test_invalid_difficulty_returns_400(self, guest_auth):
        response = client.post(
            "/api/trivia/sessions",
            json={
                "category": "old_testament",
                "difficulty": "legendary",
                "question_count": 5,
                "answers": [],
            },
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/trivia/leaderboard
# ---------------------------------------------------------------------------

class TestGetLeaderboard:

    def test_returns_entries_list(self):
        mock_entries = [
            {
                "rank": 1,
                "user_id": 1,
                "username": "alice",
                "best_score": 900,
                "avg_accuracy": 90.0,
                "total_games": 5,
            }
        ]
        mock_response = {
            "entries": mock_entries,
            "category": None,
            "difficulty": None,
            "period": "all_time",
            "user_rank": None,
        }

        with patch(
            "app.routers.trivia._service.get_leaderboard",
            new_callable=AsyncMock,
            return_value=mock_entries,
        ):
            response = client.get("/api/trivia/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert data["entries"][0]["rank"] == 1

    def test_invalid_period_returns_400(self):
        response = client.get(
            "/api/trivia/leaderboard",
            params={"period": "daily"},  # only all_time/weekly allowed
        )
        assert response.status_code == 400

    def test_invalid_category_filter_returns_400(self):
        response = client.get(
            "/api/trivia/leaderboard",
            params={"category": "garbage"},
        )
        assert response.status_code == 400

    def test_invalid_difficulty_filter_returns_400(self):
        response = client.get(
            "/api/trivia/leaderboard",
            params={"difficulty": "impossible"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/trivia/daily-challenge
# ---------------------------------------------------------------------------

class TestGetDailyChallenge:

    def test_returns_question_text(self):
        safe_q = _safe_question()

        with patch(
            "app.routers.trivia._service.get_daily_challenge",
            new_callable=AsyncMock,
            return_value=safe_q,
        ):
            response = client.get("/api/trivia/daily-challenge")

        assert response.status_code == 200
        data = response.json()
        assert "question_text" in data
        assert data["question_text"] == safe_q["question_text"]

    def test_correct_answer_not_exposed(self):
        """The daily challenge response must not expose correct_answer."""
        safe_q = _safe_question()

        with patch(
            "app.routers.trivia._service.get_daily_challenge",
            new_callable=AsyncMock,
            return_value=safe_q,
        ):
            response = client.get("/api/trivia/daily-challenge")

        assert "correct_answer" not in response.json()


# ---------------------------------------------------------------------------
# POST /api/trivia/daily-challenge/submit
# ---------------------------------------------------------------------------

class TestSubmitDailyChallenge:

    def test_correct_answer_returns_is_correct_true(self, guest_auth):
        db_question = {
            "id": 1,
            "question_text": "Who led the Israelites out of Egypt?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["Moses", "Aaron", "Joshua", "Caleb"],
            "correct_answer": "Moses",
            "correct_index": 0,
            "explanation": "Exodus 14:21",
            "scripture_reference": "Exodus 14:21",
        }

        with (
            patch(
                "app.routers.trivia.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 1, "chosen_answer": "Moses"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "is_correct" in data
        assert data["is_correct"] is True
        assert data["correct_answer"] == "Moses"

    def test_wrong_answer_returns_is_correct_false(self, guest_auth):
        db_question = {
            "id": 1,
            "question_text": "Who led the Israelites out of Egypt?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["Moses", "Aaron", "Joshua", "Caleb"],
            "correct_answer": "Moses",
            "correct_index": 0,
            "explanation": "Exodus 14:21",
            "scripture_reference": "Exodus 14:21",
        }

        with (
            patch(
                "app.routers.trivia.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 1, "chosen_answer": "Aaron"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is False
        assert data["correct_answer"] == "Moses"

    def test_unknown_question_id_returns_404(self, guest_auth):
        with patch(
            "app.routers.trivia.TriviaRepository.get_question_by_id",
            return_value=None,
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 9999, "chosen_answer": "David"},
            )

        assert response.status_code == 404

    def test_response_includes_score(self, guest_auth):
        """Even for a wrong answer the score key must be present (value 0)."""
        db_question = {
            "id": 1,
            "question_text": "Q?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": None,
            "scripture_reference": None,
        }

        with patch(
            "app.routers.trivia.TriviaRepository.get_question_by_id",
            return_value=db_question,
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 1, "chosen_answer": "B"},  # wrong
            )

        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert data["score"] == 0  # wrong answer → no points


# ---------------------------------------------------------------------------
# GET /api/trivia/questions — error paths
# ---------------------------------------------------------------------------

class TestGetQuestionsErrorPaths:

    def test_unexpected_exception_returns_500(self):
        """An unhandled exception in the service must return HTTP 500."""
        with patch(
            "app.routers.trivia._service.get_questions_for_round",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Unexpected boom"),
        ):
            response = client.get(
                "/api/trivia/questions",
                params={"category": "old_testament", "difficulty": "easy", "count": 5},
            )
        assert response.status_code == 500

    def test_count_below_minimum_returns_422(self):
        """count < 5 should be rejected by FastAPI schema validation."""
        response = client.get(
            "/api/trivia/questions",
            params={"category": "old_testament", "difficulty": "easy", "count": 2},
        )
        assert response.status_code == 422

    def test_count_above_maximum_returns_422(self):
        response = client.get(
            "/api/trivia/questions",
            params={"category": "old_testament", "difficulty": "easy", "count": 25},
        )
        assert response.status_code == 422

    def test_question_type_filter_forwarded(self):
        """Optional question_type query param should be forwarded to the service."""
        safe_questions = [_safe_question()]

        with patch(
            "app.routers.trivia._service.get_questions_for_round",
            new_callable=AsyncMock,
            return_value=safe_questions,
        ) as mock_service:
            response = client.get(
                "/api/trivia/questions",
                params={
                    "category": "old_testament",
                    "difficulty": "easy",
                    "count": 5,
                    "question_type": "true_false",
                },
            )

        assert response.status_code == 200
        _, kwargs = mock_service.call_args
        assert mock_service.call_args[0][3] == "true_false"


# ---------------------------------------------------------------------------
# POST /api/trivia/sessions — additional paths
# ---------------------------------------------------------------------------

class TestSubmitSessionAdditionalPaths:

    def test_unauthenticated_still_processed_via_guest(self, guest_auth):
        """Guest auth override means no auth cookie is required."""
        mock_result = {
            "session_id": 5,
            "score_breakdown": {
                "total_score": 0,
                "base_score": 0,
                "time_bonus": 0,
                "streak_bonus": 0,
                "correct_count": 0,
                "accuracy_percent": 0.0,
                "streak_max": 0,
            },
            "leaderboard_position": None,
            "answers_review": [],
        }

        with patch(
            "app.routers.trivia._service.submit_game_session",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = client.post(
                "/api/trivia/sessions",
                json={
                    "category": "new_testament",
                    "difficulty": "medium",
                    "question_count": 5,
                    "answers": [],
                    "timer_enabled": False,
                },
            )

        assert response.status_code == 200

    def test_unexpected_exception_returns_500(self, guest_auth):
        with patch(
            "app.routers.trivia._service.submit_game_session",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB exploded"),
        ):
            response = client.post(
                "/api/trivia/sessions",
                json={
                    "category": "old_testament",
                    "difficulty": "easy",
                    "question_count": 5,
                    "answers": [],
                    "timer_enabled": False,
                },
            )
        assert response.status_code == 500

    def test_response_has_leaderboard_position_field(self, guest_auth):
        mock_result = {
            "session_id": 12,
            "score_breakdown": {
                "total_score": 200,
                "base_score": 200,
                "time_bonus": 0,
                "streak_bonus": 0,
                "correct_count": 2,
                "accuracy_percent": 100.0,
                "streak_max": 2,
            },
            "leaderboard_position": 3,
            "answers_review": [],
        }

        with patch(
            "app.routers.trivia._service.submit_game_session",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = client.post(
                "/api/trivia/sessions",
                json={
                    "category": "old_testament",
                    "difficulty": "easy",
                    "question_count": 5,
                    "answers": [],
                    "timer_enabled": False,
                },
            )

        data = response.json()
        assert data["leaderboard_position"] == 3


# ---------------------------------------------------------------------------
# GET /api/trivia/leaderboard — additional paths
# ---------------------------------------------------------------------------

class TestGetLeaderboardAdditionalPaths:

    def test_valid_category_and_difficulty_filters_accepted(self):
        mock_entries = []
        with patch(
            "app.routers.trivia._service.get_leaderboard",
            new_callable=AsyncMock,
            return_value=mock_entries,
        ):
            response = client.get(
                "/api/trivia/leaderboard",
                params={"category": "new_testament", "difficulty": "hard", "period": "weekly"},
            )

        assert response.status_code == 200

    def test_unexpected_exception_returns_500(self):
        with patch(
            "app.routers.trivia._service.get_leaderboard",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Cache exploded"),
        ):
            response = client.get("/api/trivia/leaderboard")
        assert response.status_code == 500

    def test_weekly_period_accepted(self):
        with patch(
            "app.routers.trivia._service.get_leaderboard",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = client.get("/api/trivia/leaderboard", params={"period": "weekly"})
        assert response.status_code == 200

    def test_limit_param_forwarded(self):
        with patch(
            "app.routers.trivia._service.get_leaderboard",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_svc:
            response = client.get("/api/trivia/leaderboard", params={"limit": 25})

        assert response.status_code == 200
        assert mock_svc.call_args[0][3] == 25

    def test_limit_above_max_returns_422(self):
        response = client.get("/api/trivia/leaderboard", params={"limit": 100})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/trivia/daily-challenge — error paths
# ---------------------------------------------------------------------------

class TestGetDailyChallengeErrorPaths:

    def test_unexpected_exception_returns_500(self):
        with patch(
            "app.routers.trivia._service.get_daily_challenge",
            new_callable=AsyncMock,
            side_effect=RuntimeError("OpenAI down"),
        ):
            response = client.get("/api/trivia/daily-challenge")
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/trivia/daily-challenge/submit — timer path
# ---------------------------------------------------------------------------

class TestSubmitDailyChallengeTimer:

    def test_correct_answer_with_timer_gives_nonzero_score(self, guest_auth):
        """A correct answer submitted with time_seconds should earn a positive score."""
        db_question = {
            "id": 1,
            "question_text": "Who led the Israelites?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["Moses", "Aaron", "Joshua", "Caleb"],
            "correct_answer": "Moses",
            "correct_index": 0,
            "explanation": "Exodus 14",
            "scripture_reference": "Exodus 14:21",
        }

        with patch(
            "app.routers.trivia.TriviaRepository.get_question_by_id",
            return_value=db_question,
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 1, "chosen_answer": "Moses", "time_seconds": 5},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is True
        assert data["score"] > 0

    def test_unexpected_exception_returns_500(self, guest_auth):
        with patch(
            "app.routers.trivia.TriviaRepository.get_question_by_id",
            side_effect=RuntimeError("DB down"),
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 1, "chosen_answer": "Moses"},
            )
        assert response.status_code == 500

    def test_explanation_included_in_response(self, guest_auth):
        db_question = {
            "id": 1,
            "question_text": "Q?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "This is the explanation",
            "scripture_reference": "Gen 1:1",
        }

        with patch(
            "app.routers.trivia.TriviaRepository.get_question_by_id",
            return_value=db_question,
        ):
            response = client.post(
                "/api/trivia/daily-challenge/submit",
                json={"question_id": 1, "chosen_answer": "A"},
            )

        data = response.json()
        assert data["explanation"] == "This is the explanation"
        assert data["scripture_reference"] == "Gen 1:1"
