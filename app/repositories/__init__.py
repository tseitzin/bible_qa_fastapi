"""Repository modules for database operations.

All repository classes are re-exported here for convenient imports.
"""
from app.repositories.question import QuestionRepository
from app.repositories.saved_answers import SavedAnswersRepository
from app.repositories.recent_questions import RecentQuestionsRepository
from app.repositories.user_notes import UserNotesRepository
from app.repositories.cross_reference import CrossReferenceRepository
from app.repositories.lexicon import LexiconRepository
from app.repositories.topic_index import TopicIndexRepository
from app.repositories.reading_plan import ReadingPlanRepository
from app.repositories.devotional_template import DevotionalTemplateRepository
from app.repositories.user_reading_plan import UserReadingPlanRepository
from app.repositories.api_request_log import ApiRequestLogRepository
from app.repositories.openai_api_call import OpenAIApiCallRepository
from app.repositories.page_analytics import PageAnalyticsRepository

__all__ = [
    "QuestionRepository",
    "SavedAnswersRepository",
    "RecentQuestionsRepository",
    "UserNotesRepository",
    "CrossReferenceRepository",
    "LexiconRepository",
    "TopicIndexRepository",
    "ReadingPlanRepository",
    "DevotionalTemplateRepository",
    "UserReadingPlanRepository",
    "ApiRequestLogRepository",
    "OpenAIApiCallRepository",
    "PageAnalyticsRepository",
]
