"""Unit tests for TriviaService."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import TriviaAnswerSubmit, TriviaSessionSubmitRequest
from app.services.trivia_service import TriviaService, OpenAIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service() -> TriviaService:
    """Return a TriviaService with OpenAI constructor patched out."""
    with patch("app.services.trivia_service.OpenAI"):
        return TriviaService()


def _answer(*, is_correct: bool, time_seconds: int | None = None) -> dict:
    return {"question_id": 1, "chosen_answer": "X", "is_correct": is_correct, "time_seconds": time_seconds}


# ---------------------------------------------------------------------------
# calculate_score — deterministic unit tests (no I/O)
# ---------------------------------------------------------------------------

class TestCalculateScoreEasyNoTimer:
    """3 correct answers, easy difficulty, timer disabled.

    Streak bonus kicks in on the 3rd consecutive answer: 25 * max(0, 3-2) = 25.
    Q1: 100, Q2: 100, Q3: 100 + 25 = 125 → total = 325.
    """

    def test_total_score(self):
        svc = _make_service()
        answers = [_answer(is_correct=True) for _ in range(3)]
        result = svc.calculate_score(answers, difficulty="easy", timer_enabled=False)
        assert result["total_score"] == 325

    def test_correct_count(self):
        svc = _make_service()
        answers = [_answer(is_correct=True) for _ in range(3)]
        result = svc.calculate_score(answers, difficulty="easy", timer_enabled=False)
        assert result["correct_count"] == 3

    def test_no_time_bonus(self):
        svc = _make_service()
        answers = [_answer(is_correct=True) for _ in range(3)]
        result = svc.calculate_score(answers, difficulty="easy", timer_enabled=False)
        assert result["time_bonus"] == 0

    def test_accuracy_100(self):
        svc = _make_service()
        answers = [_answer(is_correct=True) for _ in range(3)]
        result = svc.calculate_score(answers, difficulty="easy", timer_enabled=False)
        assert result["accuracy_percent"] == 100.0


class TestCalculateScoreHardWithTimer:
    """2 correct answers, hard difficulty, time_seconds=10 (20s remaining of 30).

    Per-question time bonus: round(50 * 20/30) = 33
    Per-question score: round((200 + 33 + 0) * 1.5) = round(349.5) = 350
    Total score: 350 * 2 = 700
    Time bonus total: round(33 * 1.5) * 2 = 50 * 2 = 100
    """

    def setup_method(self):
        self.svc = _make_service()
        self.answers = [_answer(is_correct=True, time_seconds=10) for _ in range(2)]
        self.result = self.svc.calculate_score(self.answers, difficulty="hard", timer_enabled=True)

    def test_total_score(self):
        # round((200 + 33) * 1.5) = round(349.5) = 350 per question → 700 total
        assert self.result["total_score"] == 700

    def test_correct_count(self):
        assert self.result["correct_count"] == 2

    def test_time_bonus_positive(self):
        assert self.result["time_bonus"] > 0

    def test_difficulty_multiplier_applied(self):
        # base_score = round(200 * 1.5) * 2 = 300 * 2 = 600
        assert self.result["base_score"] == 600


class TestCalculateScoreStreakBonus:
    """5 consecutive correct answers — streak bonus kicks in from the 3rd answer."""

    def setup_method(self):
        self.svc = _make_service()
        self.answers = [_answer(is_correct=True) for _ in range(5)]
        self.result = self.svc.calculate_score(self.answers, difficulty="easy", timer_enabled=False)

    def test_streak_max_is_five(self):
        assert self.result["streak_max"] == 5

    def test_streak_bonus_positive(self):
        # At streak 3: sb=25*1=25, streak 4: sb=25*2=50, streak 5: sb=25*3=75 → total 150
        assert self.result["streak_bonus"] == 150

    def test_total_score_includes_streak(self):
        # base: 5*100 = 500; streak bonus: 150 → 650
        assert self.result["total_score"] == 650

    def test_correct_count(self):
        assert self.result["correct_count"] == 5


class TestCalculateScoreAllWrong:
    """5 wrong answers → zero score everywhere."""

    def setup_method(self):
        self.svc = _make_service()
        self.answers = [_answer(is_correct=False) for _ in range(5)]
        self.result = self.svc.calculate_score(self.answers, difficulty="medium", timer_enabled=False)

    def test_total_score_zero(self):
        assert self.result["total_score"] == 0

    def test_correct_count_zero(self):
        assert self.result["correct_count"] == 0

    def test_streak_max_zero(self):
        assert self.result["streak_max"] == 0

    def test_accuracy_zero(self):
        assert self.result["accuracy_percent"] == 0.0


class TestCalculateScoreMixed:
    """Correct, wrong, correct — streak resets after the wrong answer."""

    def setup_method(self):
        self.svc = _make_service()
        self.answers = [
            _answer(is_correct=True),
            _answer(is_correct=False),
            _answer(is_correct=True),
        ]
        self.result = self.svc.calculate_score(self.answers, difficulty="easy", timer_enabled=False)

    def test_correct_count(self):
        assert self.result["correct_count"] == 2

    def test_streak_max_is_one(self):
        # The streak resets after the wrong answer, so the longest run is 1.
        assert self.result["streak_max"] == 1

    def test_no_streak_bonus(self):
        assert self.result["streak_bonus"] == 0

    def test_total_score(self):
        # 2 correct × 100 × 1.0 = 200
        assert self.result["total_score"] == 200

    def test_accuracy_percent(self):
        assert self.result["accuracy_percent"] == pytest.approx(66.7, abs=0.1)


# ---------------------------------------------------------------------------
# submit_game_session — server-side answer validation
# ---------------------------------------------------------------------------

class TestSubmitGameSessionServerValidatesAnswers:
    """Server must re-validate chosen_answer against the stored correct_answer.

    The client claims is_correct=True but sends "Moses" while the DB answer is
    "David". The service must override the client's claim and set is_correct=False.
    """

    @pytest.mark.asyncio
    async def test_server_overrides_client_is_correct(self):
        svc = _make_service()

        db_question = {
            "id": 1,
            "question_text": "Who slew Goliath?",
            "correct_answer": "David",
            "explanation": "1 Samuel 17",
            "scripture_reference": "1 Samuel 17:50",
        }

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.create_game_session",
                return_value=99,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.increment_questions_usage",
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_user_best_rank",
                return_value=None,
            ),
            patch(
                "app.services.trivia_service.CacheService.delete",
            ),
        ):
            session_request = TriviaSessionSubmitRequest(
                category="old_testament",
                difficulty="easy",
                question_count=5,
                answers=[
                    TriviaAnswerSubmit(
                        question_id=1,
                        chosen_answer="Moses",   # Wrong — client lies
                        is_correct=True,         # Client claims correct
                    )
                ],
                timer_enabled=False,
            )

            result = await svc.submit_game_session(user_id=1, session_request=session_request)

        assert result["session_id"] == 99
        review = result["answers_review"]
        assert len(review) == 1
        # Server re-validated: Moses != David → must be False
        assert review[0]["is_correct"] is False
        assert review[0]["correct_answer"] == "David"
        assert review[0]["chosen_answer"] == "Moses"

    @pytest.mark.asyncio
    async def test_correct_answer_verified_server_side(self):
        """Client sends correct answer and is_correct=False — server corrects to True."""
        svc = _make_service()

        db_question = {
            "id": 2,
            "question_text": "Who slew Goliath?",
            "correct_answer": "David",
            "explanation": "1 Samuel 17",
            "scripture_reference": "1 Samuel 17:50",
        }

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.create_game_session",
                return_value=100,
            ),
            patch("app.services.trivia_service.TriviaRepository.increment_questions_usage"),
            patch(
                "app.services.trivia_service.TriviaRepository.get_user_best_rank",
                return_value=1,
            ),
            patch("app.services.trivia_service.CacheService.delete"),
        ):
            session_request = TriviaSessionSubmitRequest(
                category="old_testament",
                difficulty="easy",
                question_count=5,
                answers=[
                    TriviaAnswerSubmit(
                        question_id=2,
                        chosen_answer="David",   # Correct
                        is_correct=False,        # Client mistakenly says wrong
                    )
                ],
                timer_enabled=False,
            )

            result = await svc.submit_game_session(user_id=1, session_request=session_request)

        review = result["answers_review"]
        assert review[0]["is_correct"] is True


# ---------------------------------------------------------------------------
# get_daily_challenge — cache / DB / generate branching
# ---------------------------------------------------------------------------

class TestGetDailyChallengeCache:
    """When the cache contains today's question, the DB must NOT be consulted."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        svc = _make_service()

        cached_question = {
            "id": 7,
            "question_text": "Who built the ark?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["Moses", "Noah", "Abraham", "David"],
            "scripture_reference": "Genesis 6:14",
        }

        with (
            patch(
                "app.services.trivia_service.CacheService.get",
                return_value=cached_question,
            ) as mock_cache_get,
            patch(
                "app.services.trivia_service.TriviaRepository.get_daily_challenge",
            ) as mock_db,
        ):
            result = await svc.get_daily_challenge()

        mock_db.assert_not_called()
        assert result["question_text"] == "Who built the ark?"
        assert result == cached_question


class TestGetDailyChallengeDbHit:
    """Cache miss → DB hit → CacheService.set called, answer fields stripped."""

    @pytest.mark.asyncio
    async def test_db_hit_calls_cache_set_and_strips_answer(self):
        svc = _make_service()

        db_question = {
            "id": 8,
            "question_text": "Who built the ark?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["Moses", "Noah", "Abraham", "David"],
            "correct_answer": "Noah",
            "correct_index": 1,
            "explanation": "Genesis 6",
            "scripture_reference": "Genesis 6:14",
        }

        with (
            patch(
                "app.services.trivia_service.CacheService.get",
                return_value=None,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_daily_challenge",
                return_value=db_question,
            ),
            patch(
                "app.services.trivia_service.CacheService.set",
            ) as mock_set,
        ):
            result = await svc.get_daily_challenge()

        mock_set.assert_called_once()
        assert "correct_answer" not in result
        # correct_index is intentionally included for client-side visual feedback
        assert result["question_text"] == "Who built the ark?"

    @pytest.mark.asyncio
    async def test_db_hit_does_not_call_generate(self):
        svc = _make_service()

        db_question = {
            "id": 9,
            "question_text": "Sample?",
            "question_type": "multiple_choice",
            "category": "new_testament",
            "difficulty": "easy",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "Test",
            "scripture_reference": None,
        }

        with (
            patch("app.services.trivia_service.CacheService.get", return_value=None),
            patch(
                "app.services.trivia_service.TriviaRepository.get_daily_challenge",
                return_value=db_question,
            ),
            patch("app.services.trivia_service.CacheService.set"),
        ):
            generate_mock = AsyncMock()
            svc.generate_question = generate_mock
            await svc.get_daily_challenge()

        generate_mock.assert_not_called()


class TestGetDailyChallengeGenerates:
    """Cache miss + DB miss → generate_question and set_daily_challenge called."""

    @pytest.mark.asyncio
    async def test_generates_when_both_miss(self):
        svc = _make_service()

        generated_question = {
            "id": 42,
            "question_text": "Who wrote Revelation?",
            "question_type": "multiple_choice",
            "category": "new_testament",
            "difficulty": "medium",
            "options": ["Paul", "John", "Luke", "Peter"],
            "correct_answer": "John",
            "correct_index": 1,
            "explanation": "The apostle John wrote Revelation.",
            "scripture_reference": "Revelation 1:1",
        }

        fetched_from_db = {**generated_question}

        with (
            patch("app.services.trivia_service.CacheService.get", return_value=None),
            patch(
                "app.services.trivia_service.TriviaRepository.get_daily_challenge",
                return_value=None,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.set_daily_challenge",
            ) as mock_set_daily,
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value=fetched_from_db,
            ),
            patch("app.services.trivia_service.CacheService.set"),
        ):
            svc.generate_question = AsyncMock(return_value=generated_question)
            result = await svc.get_daily_challenge()

        svc.generate_question.assert_awaited_once()
        # Verify set_daily_challenge was called with the generated question id and a date string
        call_args = mock_set_daily.call_args[0]
        assert call_args[0] == 42
        assert isinstance(call_args[1], str) and len(call_args[1]) == 10  # YYYY-MM-DD
        assert "correct_answer" not in result

    @pytest.mark.asyncio
    async def test_set_daily_challenge_called_with_correct_id(self):
        svc = _make_service()

        generated = {
            "id": 55,
            "question_text": "Test Q?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "medium",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "Explanation",
            "scripture_reference": None,
        }

        with (
            patch("app.services.trivia_service.CacheService.get", return_value=None),
            patch(
                "app.services.trivia_service.TriviaRepository.get_daily_challenge",
                return_value=None,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.set_daily_challenge",
            ) as mock_set_daily,
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value={**generated},
            ),
            patch("app.services.trivia_service.CacheService.set"),
        ):
            svc.generate_question = AsyncMock(return_value=generated)
            await svc.get_daily_challenge()

        called_id = mock_set_daily.call_args[0][0]
        assert called_id == 55


# ---------------------------------------------------------------------------
# calculate_score — edge cases
# ---------------------------------------------------------------------------

class TestCalculateScoreEmptyAnswers:
    """Empty answer list → all zeroes and 0.0 accuracy."""

    def test_empty_answers_returns_zero_score(self):
        svc = _make_service()
        result = svc.calculate_score([], difficulty="easy", timer_enabled=False)
        assert result["total_score"] == 0
        assert result["correct_count"] == 0
        assert result["accuracy_percent"] == 0.0
        assert result["streak_max"] == 0


class TestCalculateScoreMediumDifficulty:
    """Medium difficulty multiplier (1.25) applied correctly."""

    def test_medium_base_score(self):
        svc = _make_service()
        result = svc.calculate_score(
            [_answer(is_correct=True)], difficulty="medium", timer_enabled=False
        )
        # round(150 * 1.25) = round(187.5) = 188
        assert result["base_score"] == 188

    def test_single_correct_no_streak_bonus(self):
        svc = _make_service()
        result = svc.calculate_score(
            [_answer(is_correct=True)], difficulty="medium", timer_enabled=False
        )
        assert result["streak_bonus"] == 0
        assert result["streak_max"] == 1


class TestCalculateScoreTimerDisabledIgnoresTime:
    """timer_enabled=False must not grant a time_bonus even if time_seconds present."""

    def test_timer_disabled_no_bonus(self):
        svc = _make_service()
        result = svc.calculate_score(
            [_answer(is_correct=True, time_seconds=5)],
            difficulty="easy",
            timer_enabled=False,
        )
        assert result["time_bonus"] == 0


# ---------------------------------------------------------------------------
# _validate_question_data — direct unit tests
# ---------------------------------------------------------------------------

class TestValidateQuestionData:
    """Static method tests — no service instantiation required."""

    def test_valid_data_passes(self):
        data = {
            "question_text": "Who built the ark?",
            "options": ["Noah", "Moses", "Abraham", "David"],
            "correct_answer": "Noah",
            "explanation": "Genesis 6",
        }
        TriviaService._validate_question_data(data, "multiple_choice")  # must not raise

    def test_missing_required_field_raises(self):
        data = {
            "question_text": "Q?",
            "options": ["A", "B"],
            # "correct_answer" is missing
            "explanation": "E",
        }
        with pytest.raises(ValueError, match="correct_answer"):
            TriviaService._validate_question_data(data, "multiple_choice")

    def test_options_not_list_raises(self):
        data = {
            "question_text": "Q?",
            "options": "not_a_list",
            "correct_answer": "A",
            "explanation": "E",
        }
        with pytest.raises(ValueError, match="options"):
            TriviaService._validate_question_data(data, "multiple_choice")

    def test_options_too_short_raises(self):
        data = {
            "question_text": "Q?",
            "options": ["only_one"],
            "correct_answer": "only_one",
            "explanation": "E",
        }
        with pytest.raises(ValueError, match="options"):
            TriviaService._validate_question_data(data, "multiple_choice")

    def test_correct_answer_not_in_options_raises_without_index(self):
        data = {
            "question_text": "Q?",
            "options": ["A", "B"],
            "correct_answer": "C",
            "explanation": "E",
        }
        with pytest.raises(ValueError, match="correct_answer"):
            TriviaService._validate_question_data(data, "multiple_choice")

    def test_correct_answer_recovered_via_correct_index(self):
        """If correct_answer not in options but correct_index is valid, recover it."""
        data = {
            "question_text": "Q?",
            "options": ["A", "B", "C"],
            "correct_answer": "WRONG",  # Not in options
            "correct_index": 1,         # Points to "B"
            "explanation": "E",
        }
        TriviaService._validate_question_data(data, "multiple_choice")
        assert data["correct_answer"] == "B"

    def test_missing_explanation_raises(self):
        data = {
            "question_text": "Q?",
            "options": ["A", "B"],
            "correct_answer": "A",
            # explanation missing
        }
        with pytest.raises(ValueError, match="explanation"):
            TriviaService._validate_question_data(data, "multiple_choice")


# ---------------------------------------------------------------------------
# generate_question — retry logic
# ---------------------------------------------------------------------------

class TestGenerateQuestionRetries:
    """generate_question must retry up to MAX_GENERATE_RETRIES times on failure."""

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        svc = _make_service()
        # _run_tool_loop always fails
        svc._run_tool_loop = AsyncMock(side_effect=OpenAIError("API down"))

        with pytest.raises(OpenAIError, match="Failed to generate"):
            await svc.generate_question("old_testament", "easy")

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt_after_duplicate(self):
        """First call returns a duplicate (create_question returns None → ValueError),
        second call with different data succeeds."""
        svc = _make_service()

        valid_data = {
            "question_text": "Who led Israel out of Egypt?",
            "question_type": "multiple_choice",
            "options": ["Moses", "Joshua", "Aaron", "Caleb"],
            "correct_answer": "Moses",
            "correct_index": 0,
            "explanation": "Exodus 14",
            "scripture_reference": "Exodus 14:21",
        }

        svc._run_tool_loop = AsyncMock(return_value=valid_data)

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.create_question",
                side_effect=[None, 10],  # First → duplicate, second → success
            ),
        ):
            result = await svc.generate_question("old_testament", "easy")

        assert result["id"] == 10

    @pytest.mark.asyncio
    async def test_raises_when_all_attempts_duplicate(self):
        svc = _make_service()

        valid_data = {
            "question_text": "Test?",
            "question_type": "multiple_choice",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "Explanation",
            "scripture_reference": "Gen 1:1",
        }

        svc._run_tool_loop = AsyncMock(return_value=valid_data)

        with patch(
            "app.services.trivia_service.TriviaRepository.create_question",
            return_value=None,  # Always a duplicate
        ):
            with pytest.raises(OpenAIError, match="Failed to generate"):
                await svc.generate_question("old_testament", "easy")


# ---------------------------------------------------------------------------
# get_questions_for_round — shortfall fill and pool top-up trigger
# ---------------------------------------------------------------------------

class TestGetQuestionsForRound:
    """Service-level get_questions_for_round method."""

    @pytest.mark.asyncio
    async def test_returns_stripped_questions_from_db(self):
        svc = _make_service()

        db_questions = [
            {
                "id": i,
                "question_text": f"Q{i}?",
                "question_type": "multiple_choice",
                "category": "old_testament",
                "difficulty": "easy",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "correct_index": 0,
                "explanation": "E",
                "scripture_reference": f"Gen {i}:1",
            }
            for i in range(1, 6)
        ]

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.count_available_questions",
                return_value=100,  # Above threshold, no top-up needed
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=db_questions,
            ),
        ):
            result = await svc.get_questions_for_round("old_testament", "easy", 5)

        assert len(result) == 5
        for q in result:
            assert "correct_answer" not in q

    @pytest.mark.asyncio
    async def test_deduplicates_by_scripture_reference(self):
        """Two questions with the same scripture_reference → only one returned."""
        svc = _make_service()

        db_questions = [
            {
                "id": 1,
                "question_text": "Q1?",
                "question_type": "multiple_choice",
                "category": "old_testament",
                "difficulty": "easy",
                "options": ["A", "B"],
                "correct_answer": "A",
                "correct_index": 0,
                "explanation": "E",
                "scripture_reference": "Gen 1:1",
            },
            {
                "id": 2,
                "question_text": "Q2?",
                "question_type": "multiple_choice",
                "category": "old_testament",
                "difficulty": "easy",
                "options": ["A", "B"],
                "correct_answer": "A",
                "correct_index": 0,
                "explanation": "E",
                "scripture_reference": "Gen 1:1",  # Duplicate ref
            },
        ]

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.count_available_questions",
                return_value=100,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=db_questions,
            ),
        ):
            # Ask for 1 question — deduplication should give exactly 1
            result = await svc.get_questions_for_round("old_testament", "easy", 1)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_triggers_background_topup_when_pool_thin(self):
        """When available < MIN_QUESTION_POOL * 2, a background task must be created."""
        svc = _make_service()

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.count_available_questions",
                return_value=5,  # Very thin pool
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=[
                    {
                        "id": 1,
                        "question_text": "Q?",
                        "question_type": "multiple_choice",
                        "category": "old_testament",
                        "difficulty": "easy",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "correct_index": 0,
                        "explanation": "E",
                        "scripture_reference": None,
                    }
                ],
            ),
            patch("app.services.trivia_service.asyncio.create_task") as mock_task,
        ):
            await svc.get_questions_for_round("old_testament", "easy", 1)

        mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_fills_shortfall_via_generate(self):
        """When DB returns fewer questions than requested, generate fills the shortfall."""
        svc = _make_service()

        generated_q = {
            "id": 99,
            "question_text": "Generated Q?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "E",
            "scripture_reference": "Isaiah 1:1",
        }
        svc.generate_question = AsyncMock(return_value=generated_q)

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.count_available_questions",
                return_value=100,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=[],  # DB returns nothing → full shortfall
            ),
        ):
            result = await svc.get_questions_for_round("old_testament", "easy", 1)

        svc.generate_question.assert_awaited_once()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# submit_game_session — time tracking and cache invalidation
# ---------------------------------------------------------------------------

class TestSubmitGameSessionTimeTotals:
    """time_taken_seconds must be the sum of per-answer time_seconds."""

    @pytest.mark.asyncio
    async def test_time_taken_seconds_summed(self):
        svc = _make_service()

        db_question = {
            "id": 1,
            "question_text": "Q?",
            "correct_answer": "A",
            "explanation": None,
            "scripture_reference": None,
        }

        captured = {}

        def capture_create_session(**kwargs):
            captured.update(kwargs)
            return 1

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.create_game_session",
                side_effect=lambda **kw: captured.update(kw) or 1,
            ),
            patch("app.services.trivia_service.TriviaRepository.increment_questions_usage"),
            patch(
                "app.services.trivia_service.TriviaRepository.get_user_best_rank",
                return_value=None,
            ),
            patch("app.services.trivia_service.CacheService.delete"),
        ):
            session_request = TriviaSessionSubmitRequest(
                category="old_testament",
                difficulty="easy",
                question_count=5,
                answers=[
                    TriviaAnswerSubmit(question_id=1, chosen_answer="A", is_correct=True, time_seconds=10),
                    TriviaAnswerSubmit(question_id=1, chosen_answer="A", is_correct=True, time_seconds=20),
                ],
                timer_enabled=True,
            )
            await svc.submit_game_session(user_id=1, session_request=session_request)

        assert captured.get("time_taken_seconds") == 30

    @pytest.mark.asyncio
    async def test_time_taken_none_when_no_times(self):
        svc = _make_service()

        db_question = {
            "id": 1,
            "question_text": "Q?",
            "correct_answer": "A",
            "explanation": None,
            "scripture_reference": None,
        }

        captured = {}

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.create_game_session",
                side_effect=lambda **kw: captured.update(kw) or 1,
            ),
            patch("app.services.trivia_service.TriviaRepository.increment_questions_usage"),
            patch(
                "app.services.trivia_service.TriviaRepository.get_user_best_rank",
                return_value=None,
            ),
            patch("app.services.trivia_service.CacheService.delete"),
        ):
            session_request = TriviaSessionSubmitRequest(
                category="old_testament",
                difficulty="easy",
                question_count=5,
                answers=[
                    TriviaAnswerSubmit(question_id=1, chosen_answer="A", is_correct=True, time_seconds=None),
                ],
                timer_enabled=False,
            )
            await svc.submit_game_session(user_id=1, session_request=session_request)

        assert captured.get("time_taken_seconds") is None

    @pytest.mark.asyncio
    async def test_cache_invalidated_for_both_periods(self):
        svc = _make_service()

        db_question = {
            "id": 1,
            "question_text": "Q?",
            "correct_answer": "A",
            "explanation": None,
            "scripture_reference": None,
        }

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.get_question_by_id",
                return_value=db_question,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.create_game_session",
                return_value=1,
            ),
            patch("app.services.trivia_service.TriviaRepository.increment_questions_usage"),
            patch(
                "app.services.trivia_service.TriviaRepository.get_user_best_rank",
                return_value=None,
            ),
            patch("app.services.trivia_service.CacheService.delete") as mock_delete,
        ):
            session_request = TriviaSessionSubmitRequest(
                category="old_testament",
                difficulty="easy",
                question_count=5,
                answers=[
                    TriviaAnswerSubmit(question_id=1, chosen_answer="A", is_correct=True),
                ],
                timer_enabled=False,
            )
            await svc.submit_game_session(user_id=1, session_request=session_request)

        # Must delete for both all_time and weekly
        delete_keys = [c.args[0] for c in mock_delete.call_args_list]
        assert any("all_time" in k for k in delete_keys)
        assert any("weekly" in k for k in delete_keys)


# ---------------------------------------------------------------------------
# get_leaderboard — cache hit and miss
# ---------------------------------------------------------------------------

class TestGetLeaderboardService:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        svc = _make_service()
        cached = [{"rank": 1, "user_id": 1, "username": "alice", "best_score": 900}]

        with (
            patch(
                "app.services.trivia_service.CacheService.get",
                return_value=cached,
            ) as mock_cache_get,
            patch(
                "app.services.trivia_service.TriviaRepository.get_leaderboard",
            ) as mock_db,
        ):
            result = await svc.get_leaderboard(None, None, "all_time")

        mock_db.assert_not_called()
        assert result == cached

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db_and_sets_cache(self):
        svc = _make_service()
        db_rows = [{"user_id": 2, "username": "bob", "best_score": 500, "avg_accuracy": 80.0, "total_games": 3}]

        with (
            patch("app.services.trivia_service.CacheService.get", return_value=None),
            patch(
                "app.services.trivia_service.TriviaRepository.get_leaderboard",
                return_value=db_rows,
            ),
            patch("app.services.trivia_service.CacheService.set") as mock_set,
        ):
            result = await svc.get_leaderboard(None, None, "weekly")

        mock_set.assert_called_once()
        assert result[0]["rank"] == 1
        assert result[0]["username"] == "bob"

    @pytest.mark.asyncio
    async def test_cache_key_includes_category_and_difficulty(self):
        svc = _make_service()

        with (
            patch(
                "app.services.trivia_service.CacheService.get",
                return_value=None,
            ) as mock_cache_get,
            patch(
                "app.services.trivia_service.TriviaRepository.get_leaderboard",
                return_value=[],
            ),
            patch("app.services.trivia_service.CacheService.set"),
        ):
            await svc.get_leaderboard("old_testament", "hard", "all_time")

        cache_key = mock_cache_get.call_args[0][0]
        assert "old_testament" in cache_key
        assert "hard" in cache_key


# ---------------------------------------------------------------------------
# _run_tool_loop — unit tests exercising the OpenAI loop directly
# ---------------------------------------------------------------------------

class TestRunToolLoop:
    """Test _run_tool_loop directly by mocking self.client.chat.completions.create."""

    def _make_response(self, content=None, tool_calls=None):
        """Build a minimal mock response object."""
        msg = MagicMock()
        msg.content = content
        msg.tool_calls = tool_calls
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg
        return resp

    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_direct_response(self):
        """When the model returns JSON content directly, parse and return it."""
        svc = _make_service()
        json_content = '{"question_text": "Q?", "options": ["A", "B"], "correct_answer": "A", "explanation": "E"}'
        svc.client.chat.completions.create = MagicMock(
            return_value=self._make_response(content=json_content)
        )

        result = await svc._run_tool_loop(
            [{"role": "user", "content": "test"}], []
        )

        assert result["question_text"] == "Q?"

    @pytest.mark.asyncio
    async def test_raises_on_empty_content(self):
        """Empty message content → OpenAIError."""
        svc = _make_service()
        svc.client.chat.completions.create = MagicMock(
            return_value=self._make_response(content="")
        )

        with pytest.raises(OpenAIError, match="Empty response"):
            await svc._run_tool_loop([{"role": "user", "content": "test"}], [])

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json_content(self):
        """Non-JSON content → ValueError."""
        svc = _make_service()
        svc.client.chat.completions.create = MagicMock(
            return_value=self._make_response(content="not json at all")
        )

        with pytest.raises(ValueError, match="non-JSON"):
            await svc._run_tool_loop([{"role": "user", "content": "test"}], [])

    @pytest.mark.asyncio
    async def test_raises_after_max_iterations_with_tool_calls(self):
        """If tool_calls come back every iteration, hit the 6-iteration cap."""
        svc = _make_service()

        tc = MagicMock()
        tc.function.name = "get_verse"
        tc.function.arguments = '{"reference": "Gen 1:1"}'
        tc.id = "tc_1"

        response_with_tools = self._make_response(tool_calls=[tc])
        svc.client.chat.completions.create = MagicMock(return_value=response_with_tools)

        with patch(
            "app.services.trivia_service.execute_mcp_tool",
            return_value={"text": "In the beginning..."},
        ):
            with pytest.raises(OpenAIError, match="Maximum tool iterations"):
                await svc._run_tool_loop(
                    [{"role": "user", "content": "test"}], []
                )

    @pytest.mark.asyncio
    async def test_tool_call_error_appended_as_error_result(self):
        """When execute_mcp_tool raises, the error is caught and added to messages,
        then the loop continues. Next iteration returns content."""
        svc = _make_service()

        tc = MagicMock()
        tc.function.name = "get_verse"
        tc.function.arguments = '{"reference": "Bad:Ref"}'
        tc.id = "tc_err"

        tool_call_response = self._make_response(tool_calls=[tc])
        json_content = '{"question_text": "Q?", "options": ["A", "B"], "correct_answer": "A", "explanation": "E"}'
        final_response = self._make_response(content=json_content)

        svc.client.chat.completions.create = MagicMock(
            side_effect=[tool_call_response, final_response]
        )

        with patch(
            "app.services.trivia_service.execute_mcp_tool",
            side_effect=RuntimeError("Tool blew up"),
        ):
            result = await svc._run_tool_loop(
                [{"role": "user", "content": "test"}], []
            )

        assert result["question_text"] == "Q?"


# ---------------------------------------------------------------------------
# get_questions_for_round — shortfall exception handling + dedup continue branch
# ---------------------------------------------------------------------------

class TestGetQuestionsForRoundEdgeCases:

    @pytest.mark.asyncio
    async def test_shortfall_fill_exception_breaks_and_returns_partial(self):
        """When generate_question raises during shortfall fill, the loop breaks
        and the partial list is returned."""
        svc = _make_service()
        svc.generate_question = AsyncMock(side_effect=RuntimeError("AI down"))

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.count_available_questions",
                return_value=100,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=[],  # Empty → shortfall = count
            ),
        ):
            # Requesting 2 questions, DB returns 0, generate fails → partial result
            result = await svc.get_questions_for_round("old_testament", "easy", 2)

        # Should return 0 — the generate failed, so no questions were added
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_dedup_skips_second_question_with_same_ref(self):
        """When DB returns more than requested with duplicate refs,
        the continue branch (line 195) is exercised and the extra is skipped."""
        svc = _make_service()

        # Three questions: Q1 ref=A, Q2 ref=A (dupe), Q3 ref=B
        # Requesting count=2. After dedup: Q1 (ref A) and Q3 (ref B) → exactly 2
        db_questions = [
            {
                "id": 1, "question_text": "Q1?", "question_type": "multiple_choice",
                "category": "old_testament", "difficulty": "easy",
                "options": ["A", "B"], "correct_answer": "A", "correct_index": 0,
                "explanation": "E", "scripture_reference": "Gen 1:1",
            },
            {
                "id": 2, "question_text": "Q2?", "question_type": "multiple_choice",
                "category": "old_testament", "difficulty": "easy",
                "options": ["A", "B"], "correct_answer": "A", "correct_index": 0,
                "explanation": "E", "scripture_reference": "Gen 1:1",  # Duplicate
            },
            {
                "id": 3, "question_text": "Q3?", "question_type": "multiple_choice",
                "category": "old_testament", "difficulty": "easy",
                "options": ["A", "B"], "correct_answer": "A", "correct_index": 0,
                "explanation": "E", "scripture_reference": "Gen 2:1",
            },
        ]

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.count_available_questions",
                return_value=100,
            ),
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=db_questions,
            ),
        ):
            result = await svc.get_questions_for_round("old_testament", "easy", 2)

        ids = [q["id"] for q in result]
        assert 2 not in ids  # The duplicate was skipped
        assert len(result) == 2


# ---------------------------------------------------------------------------
# generate_question — avoid_topics hint path (line 258)
# ---------------------------------------------------------------------------

class TestGenerateQuestionAvoidTopics:

    @pytest.mark.asyncio
    async def test_avoid_topics_included_in_user_message(self):
        """When avoid_topics is provided, generate_question builds the avoid_hint
        and includes it in the user message passed to _run_tool_loop."""
        svc = _make_service()

        valid_data = {
            "question_text": "Who built the ark?",
            "question_type": "multiple_choice",
            "options": ["Noah", "Moses", "Abraham", "David"],
            "correct_answer": "Noah",
            "correct_index": 0,
            "explanation": "Genesis 6",
            "scripture_reference": "Genesis 6:14",
        }

        captured_messages = []

        async def capture_loop(messages, tools):
            captured_messages.extend(messages)
            return valid_data

        svc._run_tool_loop = capture_loop

        with patch(
            "app.services.trivia_service.TriviaRepository.create_question",
            return_value=1,
        ):
            await svc.generate_question(
                "old_testament", "easy", avoid_topics=["Exodus 14:21", "Genesis 1:1"]
            )

        user_msg = next(m for m in captured_messages if m["role"] == "user")
        assert "Exodus 14:21" in user_msg["content"]
        assert "Do NOT ask about" in user_msg["content"]


# ---------------------------------------------------------------------------
# get_daily_challenge — isoformat branch (line 539)
# ---------------------------------------------------------------------------

class TestGetDailyChallengeIsoformatBranch:

    @pytest.mark.asyncio
    async def test_date_fields_converted_to_isoformat_string(self):
        """If a question dict contains a date/datetime value, it must be
        converted to a string before being cached (line 539)."""
        from datetime import date as date_cls
        svc = _make_service()

        db_question = {
            "id": 10,
            "question_text": "Daily Q?",
            "question_type": "multiple_choice",
            "category": "old_testament",
            "difficulty": "easy",
            "options": ["A", "B"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "E",
            "scripture_reference": None,
            # A real date object — must be serialised before caching
            "daily_date": date_cls(2026, 3, 10),
        }

        with (
            patch("app.services.trivia_service.CacheService.get", return_value=None),
            patch(
                "app.services.trivia_service.TriviaRepository.get_daily_challenge",
                return_value=db_question,
            ),
            patch("app.services.trivia_service.CacheService.set") as mock_set,
        ):
            result = await svc.get_daily_challenge()

        # daily_date must have been converted to a string
        assert isinstance(result["daily_date"], str)
        assert result["daily_date"] == "2026-03-10"


# ---------------------------------------------------------------------------
# _background_topup — exception handler (lines 574-584)
# ---------------------------------------------------------------------------

class TestBackgroundTopup:

    @pytest.mark.asyncio
    async def test_exception_is_swallowed_and_logged(self):
        """_background_topup must not propagate exceptions — it logs them."""
        svc = _make_service()
        svc.generate_question = AsyncMock(side_effect=RuntimeError("AI down"))

        with (
            patch(
                "app.services.trivia_service.TriviaRepository.get_questions_for_round",
                return_value=[],
            ),
        ):
            # Should not raise — exception must be swallowed
            await svc._background_topup("old_testament", "easy", 1)

    @pytest.mark.asyncio
    async def test_generates_target_count_questions(self):
        """_background_topup calls generate_question target_count times."""
        svc = _make_service()

        generated = {
            "id": 1,
            "question_text": "Q?",
            "question_type": "multiple_choice",
            "options": ["A", "B"],
            "correct_answer": "A",
            "correct_index": 0,
            "explanation": "E",
            "scripture_reference": "Gen 1:1",
        }
        svc.generate_question = AsyncMock(return_value=generated)

        with patch(
            "app.services.trivia_service.TriviaRepository.get_questions_for_round",
            return_value=[],
        ):
            await svc._background_topup("old_testament", "easy", 3)

        assert svc.generate_question.await_count == 3
