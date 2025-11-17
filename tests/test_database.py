"""Unit tests for database operations."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import psycopg2

from app.database import (
    get_db_connection,
    QuestionRepository,
    SavedAnswersRepository,
    RecentQuestionsRepository,
)


class TestDatabaseConnection:
    """Test cases for database connection management."""
    
    @patch('app.database.psycopg2.connect')
    def test_get_db_connection_success(self, mock_connect):
        """Test successful database connection."""
        # Mock connection
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        # Test context manager
        with get_db_connection() as conn:
            assert conn == mock_conn
        
        # Verify connection was attempted and closed
        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('app.database.psycopg2.connect')
    def test_get_db_connection_error_with_rollback(self, mock_connect):
        """Test database connection error handling with rollback."""
        # Mock connection that raises an error
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        # Simulate an error during context manager execution
        with pytest.raises(psycopg2.Error):
            with get_db_connection() as conn:
                # Simulate a database error
                raise psycopg2.Error("Test database error")
        
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('app.database.psycopg2.connect')
    def test_get_db_connection_connection_error(self, mock_connect):
        """Test database connection failure."""
        # Mock connection failure
        mock_connect.side_effect = psycopg2.Error("Connection failed")
        
        # Should raise the connection error
        with pytest.raises(psycopg2.Error, match="Connection failed"):
            with get_db_connection() as conn:
                pass


class TestQuestionRepository:
    """Test cases for QuestionRepository."""
    
    @patch('app.database.get_db_connection')
    def test_create_question_success(self, mock_get_db_connection):
        """Test successful question creation."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"id": 123}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None
        
        # Test question creation
        question_id = QuestionRepository.create_question(
            user_id=1,
            question="What is love?"
        )
        
        # Assertions
        assert question_id == 123
        
        # Verify database operations
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO questions (user_id, question, parent_question_id) VALUES (%s, %s, %s) RETURNING id;",
            (1, "What is love?", None)
        )
        mock_cursor.fetchone.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @patch('app.database.get_db_connection')
    def test_create_answer_success(self, mock_get_db_connection):
        """Test successful answer creation."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None
        
        # Test answer creation
        QuestionRepository.create_answer(
            question_id=123,
            answer="God is love, as stated in 1 John 4:8."
        )
        
        # Verify database operations
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO answers (question_id, answer) VALUES (%s, %s);",
            (123, "God is love, as stated in 1 John 4:8.")
        )
        mock_conn.commit.assert_called_once()
    
    @patch('app.database.get_db_connection')
    def test_get_question_history_success(self, mock_get_db_connection):
        """Test successful question history retrieval."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_history_data = [
            {
                "id": 1,
                "question": "What is love?",
                "created_at": "2025-07-31T12:00:00Z",
                "answer": "God is love."
            },
            {
                "id": 2,
                "question": "What is faith?",
                "created_at": "2025-07-31T11:00:00Z", 
                "answer": "Faith is believing in God."
            }
        ]
        mock_cursor.fetchall.return_value = mock_history_data
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None
        
        # Test history retrieval
        result = QuestionRepository.get_question_history(
            user_id=1,
            limit=10
        )
        
        # Assertions
        assert result == mock_history_data
        assert len(result) == 2
        
        # Verify database query
        mock_cursor.execute.assert_called_once()
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "q.asked_at AS created_at" in executed_query
        assert "ORDER BY q.asked_at DESC" in executed_query
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1] == (1, 10)  # Parameters
        mock_cursor.fetchall.assert_called_once()
    
    @patch('app.database.get_db_connection')
    def test_get_question_history_empty(self, mock_get_db_connection):
        """Test question history retrieval with no results."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None
        
        # Test history retrieval
        result = QuestionRepository.get_question_history(
            user_id=999,
            limit=10
        )
        
        # Should return empty list
        assert result == []
        assert len(result) == 0
    
    @patch('app.database.get_db_connection')
    def test_create_question_database_error(self, mock_get_db_connection):
        """Test question creation with database error."""
        # Mock database connection to raise error
        mock_get_db_connection.side_effect = psycopg2.Error("Database connection failed")
        
        # Should propagate the database error
        with pytest.raises(psycopg2.Error, match="Database connection failed"):
            QuestionRepository.create_question(
                user_id=1,
                question="Test question?"
            )
    
    @patch('app.database.get_db_connection')
    def test_create_answer_database_error(self, mock_get_db_connection):
        """Test answer creation with database error."""
        # Mock database connection to raise error
        mock_get_db_connection.side_effect = psycopg2.Error("Database timeout")
        
        # Should propagate the database error
        with pytest.raises(psycopg2.Error, match="Database timeout"):
            QuestionRepository.create_answer(
                question_id=123,
                answer="Test answer"
            )
    
    @patch('app.database.get_db_connection')
    def test_get_question_history_database_error(self, mock_get_db_connection):
        """Test question history retrieval with database error."""
        # Mock database connection to raise error
        mock_get_db_connection.side_effect = psycopg2.Error("Query failed")
        
        # Should propagate the database error
        with pytest.raises(psycopg2.Error, match="Query failed"):
            QuestionRepository.get_question_history(
                user_id=1,
                limit=10
            )

    @patch('app.database.get_db_connection')
    def test_get_root_question_id_returns_result(self, mock_get_db_connection):
        """Test retrieving the root question id when a result exists."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"id": 42}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = QuestionRepository.get_root_question_id(99)
        assert result == 42

    @patch('app.database.get_db_connection')
    def test_get_root_question_id_defaults_when_missing(self, mock_get_db_connection):
        """Test retrieving the root question id when no result is found."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = QuestionRepository.get_root_question_id(77)
        assert result == 77

    @patch('app.database.get_db_connection')
    def test_get_conversation_thread_success(self, mock_get_db_connection):
        """Test retrieving the conversation thread for a question."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "question": "Root", "parent_question_id": None, "asked_at": "ts", "answer": "A", "depth": 0},
            {"id": 2, "question": "Follow-up", "parent_question_id": 1, "asked_at": "ts2", "answer": "B", "depth": 1},
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = QuestionRepository.get_conversation_thread(1)
        assert len(result) == 2
        assert result[0]["question"] == "Root"
        assert result[1]["depth"] == 1


class TestSavedAnswersRepository:
    """Test cases for SavedAnswersRepository."""

    @patch('app.database.QuestionRepository.get_root_question_id', return_value=5)
    @patch('app.database.get_db_connection')
    def test_save_answer_success(self, mock_get_db_connection, mock_get_root_id):
        """Test saving an answer stores root question and returns record."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {
            "id": 10,
            "user_id": 1,
            "question_id": 5,
            "tags": ["faith"],
            "saved_at": "2025-11-16T00:00:00Z"
        }
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = SavedAnswersRepository.save_answer(1, 99, ["faith"])

        mock_get_root_id.assert_called_once_with(99)
        mock_conn.commit.assert_called_once()
        assert result["id"] == 10

    @patch('app.database.QuestionRepository.get_conversation_thread', return_value=[{"id": 5}])
    @patch('app.database.get_db_connection')
    def test_get_user_saved_answers(self, mock_get_db_connection, mock_thread):
        """Test retrieving saved answers builds conversation thread data."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 11,
                "question_id": 5,
                "question": "Root question",
                "answer": "Root answer",
                "tags": ["faith"],
                "saved_at": "2025-11-16T00:00:00Z",
                "parent_question_id": None,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = SavedAnswersRepository.get_user_saved_answers(1, limit=10)

        assert len(result) == 1
        assert result[0]["conversation_thread"] == [{"id": 5}]
        mock_thread.assert_called_once_with(5)

    @patch('app.database.get_db_connection')
    def test_delete_saved_answer(self, mock_get_db_connection):
        """Test deleting a saved answer returns boolean."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        deleted = SavedAnswersRepository.delete_saved_answer(1, 11)
        assert deleted is True
        mock_conn.commit.assert_called_once()

    @patch('app.database.get_db_connection')
    def test_get_user_tags(self, mock_get_db_connection):
        """Test retrieving tags for a user."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [{"tag": "Faith"}, {"tag": "Hope"}]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        tags = SavedAnswersRepository.get_user_tags(1)
        assert tags == ["Faith", "Hope"]

    @patch('app.database.QuestionRepository.get_conversation_thread', return_value=[{"id": 5}])
    @patch('app.database.get_db_connection')
    def test_search_saved_answers_by_tag(self, mock_get_db_connection, mock_thread):
        """Test searching saved answers by tag invokes proper query."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 11,
                "question_id": 5,
                "question": "Root question",
                "answer": "Root answer",
                "tags": ["faith"],
                "saved_at": "2025-11-16T00:00:00Z",
                "parent_question_id": None,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        results = SavedAnswersRepository.search_saved_answers(1, tag="faith")
        assert len(results) == 1
        mock_thread.assert_called_once_with(5)

    @patch('app.database.QuestionRepository.get_conversation_thread', return_value=[{"id": 5}])
    @patch('app.database.get_db_connection')
    def test_search_saved_answers_by_query(self, mock_get_db_connection, mock_thread):
        """Test searching saved answers by query uses LIKE filter."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 11,
                "question_id": 5,
                "question": "Root question",
                "answer": "Root answer",
                "tags": ["faith"],
                "saved_at": "2025-11-16T00:00:00Z",
                "parent_question_id": None,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        results = SavedAnswersRepository.search_saved_answers(1, query="Root")
        assert len(results) == 1
        mock_thread.assert_called_once_with(5)

    def test_search_saved_answers_delegates_to_default(self, monkeypatch):
        """Test that search without filters returns default results."""
        def fake_get_user_saved_answers(user_id):
            return ["sentinel"]

        monkeypatch.setattr(SavedAnswersRepository, "get_user_saved_answers", fake_get_user_saved_answers)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = None
        mock_conn.cursor.return_value = mock_cursor

        @contextmanager
        def fake_connection():
            yield mock_conn

        monkeypatch.setattr("app.database.get_db_connection", fake_connection)

        result = SavedAnswersRepository.search_saved_answers(1)
        assert result == ["sentinel"]


class TestRecentQuestionsRepository:
    """Test cases for RecentQuestionsRepository."""

    @patch('app.database.get_db_connection')
    def test_add_recent_question_noop_for_missing_input(self, mock_get_db_connection):
        """Ensure add_recent_question does nothing when inputs are blank."""
        RecentQuestionsRepository.add_recent_question(0, "")
        mock_get_db_connection.assert_not_called()

    @patch('app.database.get_db_connection')
    def test_add_recent_question_success(self, mock_get_db_connection):
        """Test adding a recent question trims list and commits."""
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        RecentQuestionsRepository.add_recent_question(1, "Example question")

        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    @patch('app.database.get_db_connection')
    def test_get_recent_questions_requires_user(self, mock_get_db_connection):
        """Ensure get_recent_questions returns empty list without user id."""
        assert RecentQuestionsRepository.get_recent_questions(0) == []
        mock_get_db_connection.assert_not_called()

    @patch('app.database.get_db_connection')
    def test_get_recent_questions_success(self, mock_get_db_connection):
        """Test retrieving recent questions returns ordered results."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "question": "Q1", "asked_at": "ts"}
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        results = RecentQuestionsRepository.get_recent_questions(1)
        assert results[0]["question"] == "Q1"

    @patch('app.database.get_db_connection')
    def test_clear_user_recent_questions(self, mock_get_db_connection):
        """Test clearing recent questions issues delete and commit."""
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        RecentQuestionsRepository.clear_user_recent_questions(1)
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('app.database.get_db_connection')
    def test_clear_user_recent_questions_no_user(self, mock_get_db_connection):
        """Clearing with a falsey user id exits early without touching the database."""
        RecentQuestionsRepository.clear_user_recent_questions(0)
        mock_get_db_connection.assert_not_called()

    @patch('app.database.get_db_connection')
    def test_delete_recent_question_success(self, mock_get_db_connection):
        """Test deleting a recent question returns boolean status."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        deleted = RecentQuestionsRepository.delete_recent_question(1, 99)
        assert deleted is True
        mock_conn.commit.assert_called_once()

    @patch('app.database.get_db_connection')
    def test_delete_recent_question_not_found(self, mock_get_db_connection):
        """Test deleting a nonexistent recent question returns False."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        deleted = RecentQuestionsRepository.delete_recent_question(1, 999)
        assert deleted is False
        mock_conn.commit.assert_called_once()

    @patch('app.database.get_db_connection')
    def test_delete_recent_question_missing_inputs(self, mock_get_db_connection):
        """Missing identifiers returns False without querying the database."""
        assert RecentQuestionsRepository.delete_recent_question(0, 5) is False
        assert RecentQuestionsRepository.delete_recent_question(4, 0) is False
        mock_get_db_connection.assert_not_called()


# Test fixtures
@pytest.fixture
def mock_db_connection():
    """Mock database connection for testing."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None
    return mock_conn, mock_cursor
