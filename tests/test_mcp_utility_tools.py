"""Unit tests for the MCP utility tools module."""
from datetime import date

import pytest

from app.mcp.tools import utility_tools
from app.utils.exceptions import ValidationError


class TestValidators:
    """Input validation helpers."""

    def test_validate_positive_int_accepts_positive_values(self):
        assert utility_tools._validate_positive_int(3, "chapter") == 3

    def test_validate_positive_int_rejects_non_positive(self):
        with pytest.raises(ValidationError):
            utility_tools._validate_positive_int(0, "chapter")

    def test_normalize_keyword_trims_and_validates(self):
        assert utility_tools._normalize_keyword("  hope  ", "topic") == "hope"

    def test_normalize_keyword_rejects_blank(self):
        with pytest.raises(ValidationError):
            utility_tools._normalize_keyword("   ", "topic")


class TestHandlers:
    """Happy path and error handling for MCP tools."""

    def test_handle_get_cross_references_returns_payload(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.CrossReferenceRepository,
            "get_cross_references",
            lambda *args, **kwargs: [{"reference": "Romans 5:8"}],
        )

        result = utility_tools._handle_get_cross_references(
            {"book": "John", "chapter": 3, "verse": 16},
            _=None,
        )

        assert result["references"][0]["reference"] == "Romans 5:8"

    def test_handle_get_cross_references_errors_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.CrossReferenceRepository,
            "get_cross_references",
            lambda *args, **kwargs: [],
        )

        with pytest.raises(ValidationError):
            utility_tools._handle_get_cross_references(
                {"book": "John", "chapter": 3, "verse": 16},
                _=None,
            )

    def test_handle_lexicon_lookup_normalizes_inputs(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.LexiconRepository,
            "get_entry",
            lambda strongs_number=None, lemma=None: {
                "strongs_number": strongs_number,
                "lemma": lemma,
            },
        )

        entry = utility_tools._handle_lexicon_lookup(
            {"strongs_number": " g26 ", "lemma": " agape "},
            _=None,
        )

        assert entry["strongs_number"] == "g26"
        assert entry["lemma"] == "agape"

    def test_handle_topic_search_clamps_limit(self, monkeypatch):
        captured = {}

        def fake_search(keyword, limit):
            captured["keyword"] = keyword
            captured["limit"] = limit
            return ["topic"]

        monkeypatch.setattr(utility_tools.TopicIndexRepository, "search_topics", fake_search)

        result = utility_tools._handle_topic_search({"keyword": " hope ", "limit": 999}, _=None)

        assert result["keyword"] == "hope"
        assert captured["limit"] == 25

    def test_handle_generate_reading_plan_personalizes_schedule(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.ReadingPlanRepository,
            "get_plan_by_slug",
            lambda slug: {
                "id": 1,
                "slug": slug,
                "name": "Plan",
                "description": "",
                "duration_days": 5,
            },
        )
        monkeypatch.setattr(
            utility_tools.ReadingPlanRepository,
            "get_plan_schedule",
            lambda plan_id, max_days=None: [
                {"day_number": 1, "title": "Day 1", "passage": "John 1"}
            ],
        )

        payload = utility_tools._handle_generate_reading_plan(
            {"plan_slug": "demo", "days": 10, "start_date": date(2024, 1, 1).isoformat()},
            _=None,
        )

        assert payload["plan"]["slug"] == "demo"
        assert payload["schedule"][0]["scheduled_date"] == date(2024, 1, 1).isoformat()

    def test_handle_generate_reading_plan_invalid_date(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.ReadingPlanRepository,
            "get_plan_by_slug",
            lambda slug: {
                "id": 1,
                "slug": slug,
                "name": "Plan",
                "description": "",
                "duration_days": 5,
            },
        )
        monkeypatch.setattr(
            utility_tools.ReadingPlanRepository,
            "get_plan_schedule",
            lambda plan_id, max_days=None: [],
        )

        with pytest.raises(ValidationError):
            utility_tools._handle_generate_reading_plan(
                {"plan_slug": "demo", "start_date": "2024/01/01"},
                _=None,
            )

    def test_handle_generate_devotional_with_plan_support(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.DevotionalTemplateRepository,
            "get_template",
            lambda slug: {
                "slug": slug,
                "title": "{topic} Focus",
                "body": "Reflect on {topic} at {passage}",
                "prompt_1": "Why {topic}?",
                "prompt_2": "Live {topic}?",
                "default_passage": "John 15",
            },
        )
        monkeypatch.setattr(
            utility_tools.ReadingPlanRepository,
            "get_plan_by_slug",
            lambda slug: {
                "id": 2,
                "slug": slug,
                "name": "Plan",
                "description": "",
                "duration_days": 30,
            },
        )
        monkeypatch.setattr(
            utility_tools.ReadingPlanRepository,
            "get_plan_schedule",
            lambda plan_id, max_days=None: [
                {"day_number": 1, "title": "Day 1", "passage": "John 1"}
            ],
        )

        payload = utility_tools._handle_generate_devotional(
            {"topic": "Hope", "template_slug": "classic", "plan_slug": "plan", "day": 1},
            _=None,
        )

        assert payload["supporting_reading"]["passage"] == "John 1"
        assert "Hope" in payload["title"]

    def test_handle_generate_devotional_defaults_when_no_plan(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.DevotionalTemplateRepository,
            "get_template",
            lambda slug: {
                "slug": slug,
                "title": "{topic}",
                "body": "{topic}",
                "prompt_1": "",
                "prompt_2": "",
                "default_passage": "Psalm 23",
            },
        )
        monkeypatch.setattr(utility_tools.ReadingPlanRepository, "get_plan_by_slug", lambda slug: None)

        payload = utility_tools._handle_generate_devotional({"topic": "Love", "template_slug": "classic"}, _=None)

        assert payload["supporting_reading"] is None
        assert payload["passage"] == "Psalm 23"

    def test_handle_generate_devotional_unknown_template(self, monkeypatch):
        monkeypatch.setattr(utility_tools.DevotionalTemplateRepository, "get_template", lambda slug: None)

        with pytest.raises(ValidationError):
            utility_tools._handle_generate_devotional({"topic": "Joy"}, _=None)

    def test_normalize_keyword_requires_string(self):
        with pytest.raises(ValidationError):
            utility_tools._normalize_keyword(123, "keyword")

    def test_handle_lexicon_lookup_errors_when_missing_entry(self, monkeypatch):
        monkeypatch.setattr(utility_tools.LexiconRepository, "get_entry", lambda **kwargs: None)

        with pytest.raises(ValidationError):
            utility_tools._handle_lexicon_lookup({"lemma": "agape"}, _=None)

    def test_handle_generate_reading_plan_unknown_slug(self, monkeypatch):
        monkeypatch.setattr(utility_tools.ReadingPlanRepository, "get_plan_by_slug", lambda slug: None)

        with pytest.raises(ValidationError):
            utility_tools._handle_generate_reading_plan({"plan_slug": "missing"}, _=None)

    def test_handle_generate_devotional_uses_custom_passage(self, monkeypatch):
        monkeypatch.setattr(
            utility_tools.DevotionalTemplateRepository,
            "get_template",
            lambda slug: {
                "slug": slug,
                "title": "{topic}",
                "body": "{topic} - {passage}",
                "prompt_1": "",
                "prompt_2": "",
                "default_passage": "Hebrews 11",
            },
        )

        payload = utility_tools._handle_generate_devotional({"topic": "Faith", "passage": "  Luke 1  "}, _=None)

        assert payload["passage"] == "Luke 1"
