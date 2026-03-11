"""Trivia service for BibleQuest - Scripture Scholar Trivia."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.config import get_settings
from app.mcp.tool_registry import list_tools
from app.repositories.trivia import TriviaRepository
from app.services.cache_service import CacheService
from app.services.mcp_integration import execute_mcp_tool
from app.utils.exceptions import OpenAIError

logger = logging.getLogger(__name__)

MIN_QUESTION_POOL = 30
MAX_GENERATE_RETRIES = 3

DIFFICULTY_BASE: Dict[str, int] = {"easy": 100, "medium": 150, "hard": 200}
DIFFICULTY_MULT: Dict[str, float] = {"easy": 1.0, "medium": 1.25, "hard": 1.5}

VALID_CATEGORIES = {"old_testament", "new_testament", "psalms_proverbs", "doctrine_theology"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}

# Rotation order for daily challenge category selection
_DAILY_CATEGORY_ROTATION = [
    "old_testament",
    "new_testament",
    "psalms_proverbs",
    "doctrine_theology",
]

TRIVIA_SYSTEM_PROMPT = """You are a Bible trivia question writer with deep knowledge of the King James Version Bible.

Your task is to create a single Bible trivia question. Follow these rules strictly:
1. Use get_verse or search_verses to retrieve the actual verse text BEFORE writing the question. NEVER quote scripture from memory.
2. Base the question on a real, verified verse you retrieved using the tools.
3. Make the question appropriate for the requested difficulty level:
   - easy: well-known stories, famous characters, clear narrative events
   - medium: requires knowledge of context, chapter detail, or less famous passages
   - hard: requires deep knowledge, specific details, or theological concepts
4. Output a single JSON object with this exact schema:
{
  "question_text": "...",
  "question_type": "multiple_choice" or "true_false",
  "options": ["A", "B", "C", "D"],
  "correct_answer": "...",
  "correct_index": 0,
  "explanation": "...",
  "scripture_reference": "Book Chapter:Verse"
}
5. CRITICAL: correct_answer MUST be copied EXACTLY (character-for-character) from one of the strings in the options array. correct_index must be the 0-based index of that same option.
6. Do NOT add any text outside the JSON object."""

CATEGORY_PROMPTS: Dict[str, str] = {
    "old_testament": "Focus on the Old Testament (Genesis through Malachi).",
    "new_testament": "Focus on the New Testament (Matthew through Revelation).",
    "psalms_proverbs": "Focus on Psalms or Proverbs.",
    "doctrine_theology": "Focus on biblical doctrine, theology, or key theological concepts found in scripture.",
}

_TRIVIA_TOOL_NAMES = {
    "get_verse",
    "get_passage",
    "get_chapter",
    "search_verses",
    "topic_search",
    # get_cross_references excluded — returns 400 for many verses and wastes tool iterations
}

# Book pools for variety — each generated question is assigned a random book
_CATEGORY_BOOKS: Dict[str, List[str]] = {
    "old_testament": [
        "Genesis",
        "Exodus",
        "Numbers",
        "Deuteronomy",
        "Joshua",
        "Judges",
        "Ruth",
        "1 Samuel",
        "2 Samuel",
        "1 Kings",
        "2 Kings",
        "Job",
        "Isaiah",
        "Jeremiah",
        "Ezekiel",
        "Daniel",
        "Jonah",
        "Esther",
        "Nehemiah",
        "Proverbs",
        "Ecclesiastes",
        "Song of Solomon",
        "Amos",
        "Micah",
        "Habakkuk",
        "Zechariah",
    ],
    "new_testament": [
        "Matthew",
        "Mark",
        "Luke",
        "John",
        "Acts",
        "Romans",
        "1 Corinthians",
        "2 Corinthians",
        "Galatians",
        "Ephesians",
        "Philippians",
        "Colossians",
        "1 Thessalonians",
        "Hebrews",
        "James",
        "1 Peter",
        "1 John",
        "Revelation",
    ],
    "psalms_proverbs": ["Psalms", "Proverbs"],
    "doctrine_theology": [
        "Romans",
        "Galatians",
        "Ephesians",
        "Hebrews",
        "James",
        "John",
        "1 John",
        "Isaiah",
        "Psalms",
        "1 Corinthians",
    ],
}


class TriviaService:
    """Service layer for trivia question generation, scoring, and session management."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def _build_trivia_tools(self) -> List[Dict[str, Any]]:
        """Build the OpenAI tool-call list restricted to trivia-relevant MCP tools."""
        all_tools = list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in all_tools
            if t.name in _TRIVIA_TOOL_NAMES
        ]

    async def get_questions_for_round(
        self,
        category: str,
        difficulty: str,
        count: int,
        question_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return `count` questions for a game round, generating extras if the pool is thin.

        The returned dicts are safe for client consumption — ``correct_answer`` and
        ``correct_index`` are stripped before returning.
        """
        available = TriviaRepository.count_available_questions(category, difficulty)

        if available < MIN_QUESTION_POOL * 2:
            target = MIN_QUESTION_POOL * 2 - available
            asyncio.create_task(self._background_topup(category, difficulty, target))

        # Fetch more than needed so we can deduplicate by scripture_reference
        raw_questions = TriviaRepository.get_questions_for_round(category, difficulty, count * 3)

        # Deduplicate: never serve two questions about the same passage in one round
        seen_refs: set = set()
        questions = []
        for q in raw_questions:
            ref = q.get("scripture_reference")
            if ref and ref in seen_refs:
                continue
            questions.append(q)
            if ref:
                seen_refs.add(ref)
            if len(questions) == count:
                break

        shortfall = count - len(questions)
        if shortfall > 0:
            existing_ids = [q["id"] for q in questions]
            # Track scripture references already used so each new question avoids them
            avoid_topics = list(seen_refs)
            for _ in range(shortfall):
                try:
                    new_q = await self.generate_question(
                        category,
                        difficulty,
                        question_type=question_type or "multiple_choice",
                        exclude_ids=existing_ids,
                        avoid_topics=avoid_topics,
                    )
                    questions.append(new_q)
                    existing_ids.append(new_q["id"])
                    if new_q.get("scripture_reference"):
                        avoid_topics.append(new_q["scripture_reference"])
                except Exception:
                    logger.exception("Failed to generate question during shortfall fill")
                    break

        return [self._strip_answer_fields(q) for q in questions]

    def _strip_answer_fields(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of the question dict without the raw correct_answer text.

        correct_index is intentionally kept so the client can highlight the
        correct option immediately after the user selects (better UX).
        Server-side re-validation still controls the authoritative score.
        """
        safe = dict(question)
        safe.pop("correct_answer", None)
        return safe

    async def generate_question(
        self,
        category: str,
        difficulty: str,
        question_type: str = "multiple_choice",
        exclude_ids: Optional[List[int]] = None,
        avoid_topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a single trivia question via OpenAI with MCP Bible tool support.

        The returned dict includes ``correct_answer`` for internal use.
        """
        category_hint = CATEGORY_PROMPTS.get(category, "")
        system_prompt = f"{TRIVIA_SYSTEM_PROMPT}\n\n{category_hint}"

        # Pick a random book from this category to ensure variety across questions
        books = _CATEGORY_BOOKS.get(category, [])
        book_hint = f" Focus your question on a verse from the book of **{random.choice(books)}**." if books else ""

        avoid_hint = ""
        if avoid_topics:
            avoid_hint = f" Do NOT ask about these already-used passages: {', '.join(avoid_topics)}."

        user_msg = (
            f"Create a {difficulty} difficulty {question_type.replace('_', ' ')} "
            f"Bible trivia question about the {category.replace('_', ' ')} category."
            f"{book_hint}{avoid_hint} "
            "Use get_verse or search_verses to look up the verse first, then base your question on it."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        tools = self._build_trivia_tools()

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_GENERATE_RETRIES):
            try:
                data = await self._run_tool_loop(messages, tools)
                self._validate_question_data(data, question_type)

                question_id = TriviaRepository.create_question(
                    question_text=data["question_text"],
                    question_type=data.get("question_type", question_type),
                    category=category,
                    difficulty=difficulty,
                    options=data["options"],
                    correct_answer=data["correct_answer"],
                    correct_index=data.get("correct_index"),
                    explanation=data.get("explanation"),
                    scripture_reference=data.get("scripture_reference"),
                )
                if question_id is None:
                    # Duplicate scripture_reference already in DB — retry with different book
                    raise ValueError(f"Duplicate scripture_reference: {data.get('scripture_reference')}")
                data["id"] = question_id
                data["category"] = category
                data["difficulty"] = difficulty
                return data

            except (OpenAIError, ValueError) as exc:
                last_exc = exc
                logger.warning("Trivia generation attempt %d failed: %s", attempt + 1, exc)

        raise OpenAIError(f"Failed to generate trivia question after {MAX_GENERATE_RETRIES} attempts") from last_exc

    async def _run_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute the OpenAI tool-call loop and return the parsed JSON result."""
        current_messages = list(messages)

        for iteration in range(6):
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=current_messages,
                tools=tools,
                response_format={"type": "json_object"},
                max_completion_tokens=1000,
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                current_messages.append(msg)
                for tc in msg.tool_calls:
                    try:
                        result = execute_mcp_tool(tc.function.name, json.loads(tc.function.arguments))
                    except Exception as exc:
                        logger.error("Tool %s failed: %s", tc.function.name, exc)
                        result = {"error": str(exc)}
                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )
                continue

            content = msg.content or ""
            if not content:
                raise OpenAIError("Empty response from OpenAI during question generation")

            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(f"OpenAI returned non-JSON content: {content[:200]}") from exc

        raise OpenAIError("Maximum tool iterations reached during trivia generation")

    @staticmethod
    def _validate_question_data(data: Dict[str, Any], expected_type: str) -> None:
        """Raise ValueError if required fields are missing or malformed."""
        required = ("question_text", "options", "correct_answer", "explanation")
        for field in required:
            if not data.get(field):
                raise ValueError(f"Generated question missing required field: {field}")

        options = data["options"]
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError("Generated question has invalid options list")

        if data["correct_answer"] not in options:
            # Try to recover using correct_index before failing
            idx = data.get("correct_index")
            if idx is not None and isinstance(idx, int) and 0 <= idx < len(options):
                data["correct_answer"] = options[idx]
            else:
                raise ValueError("correct_answer not found in options list")

    def calculate_score(
        self,
        answers: List[Dict[str, Any]],
        difficulty: str,
        timer_enabled: bool,
    ) -> Dict[str, Any]:
        """Calculate the score breakdown for a completed game session."""
        base = DIFFICULTY_BASE.get(difficulty, 100)
        mult = DIFFICULTY_MULT.get(difficulty, 1.0)

        total_score = 0
        base_score = 0
        time_bonus_total = 0
        streak_bonus_total = 0
        current_streak = 0
        streak_max = 0
        correct_count = 0

        for ans in answers:
            if ans.get("is_correct"):
                correct_count += 1
                current_streak += 1
                streak_max = max(streak_max, current_streak)

                tb = 0
                if timer_enabled and ans.get("time_seconds") is not None:
                    time_remaining = max(0, 30 - ans["time_seconds"])
                    tb = round(50 * time_remaining / 30)

                sb = 25 * max(0, current_streak - 2)

                q_base = base
                q_score = round((q_base + tb + sb) * mult)

                total_score += q_score
                base_score += round(q_base * mult)
                time_bonus_total += round(tb * mult)
                streak_bonus_total += round(sb * mult)
            else:
                current_streak = 0

        accuracy = round(correct_count / len(answers) * 100, 1) if answers else 0.0

        return {
            "total_score": total_score,
            "base_score": base_score,
            "time_bonus": time_bonus_total,
            "streak_bonus": streak_bonus_total,
            "correct_count": correct_count,
            "accuracy_percent": accuracy,
            "streak_max": streak_max,
        }

    async def submit_game_session(
        self,
        user_id: int,
        session_request: Any,
    ) -> Dict[str, Any]:
        """Validate answers, persist a game session, and return a full result payload."""
        validated_answers: List[Dict[str, Any]] = []
        usage_updates: List[Dict[str, Any]] = []

        for ans in session_request.answers:
            q = TriviaRepository.get_question_by_id(ans.question_id)
            is_correct = q is not None and (ans.chosen_answer == q["correct_answer"])
            validated_answers.append(
                {
                    **ans.model_dump(),
                    "is_correct": is_correct,
                    "correct_answer": q["correct_answer"] if q else "",
                    "question_text": q["question_text"] if q else "",
                    "explanation": q.get("explanation") if q else None,
                    "scripture_reference": q.get("scripture_reference") if q else None,
                }
            )
            usage_updates.append({"question_id": ans.question_id, "is_correct": is_correct})

        score_breakdown = self.calculate_score(
            validated_answers,
            session_request.difficulty,
            session_request.timer_enabled,
        )

        time_taken_seconds: Optional[int] = None
        time_values = [a["time_seconds"] for a in validated_answers if a.get("time_seconds") is not None]
        if time_values:
            time_taken_seconds = sum(time_values)

        # Store a leaner answers list (omit question_text to keep payload compact)
        stored_answers = [{k: v for k, v in a.items() if k != "question_text"} for a in validated_answers]

        session_id = TriviaRepository.create_game_session(
            user_id=user_id,
            category=session_request.category,
            difficulty=session_request.difficulty,
            question_count=session_request.question_count,
            score=score_breakdown["total_score"],
            correct_count=score_breakdown["correct_count"],
            time_taken_seconds=time_taken_seconds,
            streak_max=score_breakdown["streak_max"],
            is_daily_challenge=session_request.is_daily_challenge,
            daily_date=session_request.daily_date,
            answers=stored_answers,
        )

        TriviaRepository.increment_questions_usage(usage_updates)

        # Invalidate leaderboard cache entries for this category/difficulty
        for period in ("all_time", "weekly"):
            cat_key = session_request.category or "all"
            diff_key = session_request.difficulty or "all"
            CacheService.delete(f"trivia:leaderboard:{cat_key}:{diff_key}:{period}")
            CacheService.delete(f"trivia:leaderboard:all:all:{period}")

        leaderboard_position = TriviaRepository.get_user_best_rank(
            user_id,
            session_request.category,
            session_request.difficulty,
            "all_time",
        )

        answers_review = [
            {
                "question_id": a["question_id"],
                "question_text": a["question_text"],
                "chosen_answer": a["chosen_answer"],
                "correct_answer": a["correct_answer"],
                "explanation": a.get("explanation"),
                "scripture_reference": a.get("scripture_reference"),
                "is_correct": a["is_correct"],
            }
            for a in validated_answers
        ]

        return {
            "session_id": session_id,
            "score_breakdown": score_breakdown,
            "leaderboard_position": leaderboard_position,
            "answers_review": answers_review,
        }

    async def get_daily_challenge(self) -> Dict[str, Any]:
        """Return today's daily challenge question, generating one if needed.

        The returned dict is safe for client consumption (no correct_answer).
        """
        today = date.today().isoformat()
        cache_key = f"trivia:daily:{today}"

        cached = CacheService.get(cache_key)
        if cached:
            return cached

        question = TriviaRepository.get_daily_challenge(today)
        if not question:
            day_of_year = date.today().timetuple().tm_yday
            category = _DAILY_CATEGORY_ROTATION[day_of_year % len(_DAILY_CATEGORY_ROTATION)]

            question = await self.generate_question(category, "medium")
            TriviaRepository.set_daily_challenge(question["id"], today)
            # Re-fetch to get all DB-populated fields
            question = TriviaRepository.get_question_by_id(question["id"]) or question

        safe_question = self._strip_answer_fields(question)

        # Convert any date/datetime fields to strings so the dict is JSON-serializable
        for key, val in safe_question.items():
            if hasattr(val, "isoformat"):
                safe_question[key] = val.isoformat()

        # TTL = seconds until midnight UTC
        now_utc = datetime.now(timezone.utc)
        midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_utc += timedelta(days=1)
        ttl_seconds = int((midnight_utc - now_utc).total_seconds())

        CacheService.set(cache_key, safe_question, ttl=ttl_seconds)
        return safe_question

    async def get_leaderboard(
        self,
        category: Optional[str],
        difficulty: Optional[str],
        period: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return ranked leaderboard entries, served from cache when available."""
        cat_key = category or "all"
        diff_key = difficulty or "all"
        cache_key = f"trivia:leaderboard:{cat_key}:{diff_key}:{period}"

        cached = CacheService.get(cache_key)
        if cached:
            return cached

        rows = TriviaRepository.get_leaderboard(category, difficulty, period, limit)
        entries = [{"rank": idx + 1, **row} for idx, row in enumerate(rows)]

        CacheService.set(cache_key, entries, ttl=60)
        return entries

    async def _background_topup(self, category: str, difficulty: str, target_count: int) -> None:
        """Fire-and-forget coroutine that generates questions to top up the pool."""
        try:
            # Seed avoid_topics from whatever is already in the pool so the topup
            # doesn't repeat passages that already exist in the database.
            existing = TriviaRepository.get_questions_for_round(category, difficulty, MIN_QUESTION_POOL + target_count)
            avoid_topics: List[str] = [q["scripture_reference"] for q in existing if q.get("scripture_reference")]
            for _ in range(target_count):
                new_q = await self.generate_question(category, difficulty, avoid_topics=avoid_topics)
                if new_q.get("scripture_reference"):
                    avoid_topics.append(new_q["scripture_reference"])
        except Exception:
            logger.exception("Background trivia top-up failed for %s/%s", category, difficulty)
