"""Unit tests for database operations."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import psycopg2

from app.database import get_db_connection, QuestionRepository


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
            "INSERT INTO questions (user_id, question) VALUES (%s, %s) RETURNING id;",
            (1, "What is love?")
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
        expected_query = """
                    SELECT q.id, q.question, q.created_at, a.answer
                    FROM questions q
                    LEFT JOIN answers a ON q.id = a.question_id
                    WHERE q.user_id = %s
                    ORDER BY q.created_at DESC
                    LIMIT %s
                """
        mock_cursor.execute.assert_called_once()
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


# Test fixtures
@pytest.fixture
def mock_db_connection():
    """Mock database connection for testing."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None
    return mock_conn, mock_cursor
