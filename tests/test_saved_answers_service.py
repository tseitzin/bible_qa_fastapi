"""Tests for the saved answers service module."""
import pytest
from unittest.mock import Mock, patch

from app.services.saved_answers_service import SavedAnswersService


class TestSavedAnswersService:
    """Test cases for SavedAnswersService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = SavedAnswersService()

    @patch('app.services.saved_answers_service.SavedAnswersRepository')
    def test_delete_saved_answer_success(self, mock_repo):
        """Test successfully deleting a saved answer."""
        mock_repo.admin_delete_saved_answer.return_value = True

        result = self.service.delete_saved_answer(123)

        assert result is True
        mock_repo.admin_delete_saved_answer.assert_called_once_with(123)

    @patch('app.services.saved_answers_service.SavedAnswersRepository')
    def test_delete_saved_answer_not_found(self, mock_repo):
        """Test deleting a non-existent saved answer returns False."""
        mock_repo.admin_delete_saved_answer.return_value = False

        result = self.service.delete_saved_answer(999)

        assert result is False
        mock_repo.admin_delete_saved_answer.assert_called_once_with(999)

    @patch('app.services.saved_answers_service.SavedAnswersRepository')
    def test_delete_saved_answer_handles_exception(self, mock_repo):
        """Test that exceptions are caught and logged."""
        mock_repo.admin_delete_saved_answer.side_effect = Exception("Database error")

        result = self.service.delete_saved_answer(456)

        assert result is False
        mock_repo.admin_delete_saved_answer.assert_called_once_with(456)

    @patch('app.services.saved_answers_service.SavedAnswersRepository')
    def test_delete_saved_answer_with_zero_id(self, mock_repo):
        """Test deleting with ID 0."""
        mock_repo.admin_delete_saved_answer.return_value = False

        result = self.service.delete_saved_answer(0)

        assert result is False
        mock_repo.admin_delete_saved_answer.assert_called_once_with(0)

    @patch('app.services.saved_answers_service.SavedAnswersRepository')
    def test_delete_saved_answer_with_negative_id(self, mock_repo):
        """Test deleting with negative ID."""
        mock_repo.admin_delete_saved_answer.return_value = False

        result = self.service.delete_saved_answer(-1)

        assert result is False
        mock_repo.admin_delete_saved_answer.assert_called_once_with(-1)

    @patch('app.services.saved_answers_service.logger')
    @patch('app.services.saved_answers_service.SavedAnswersRepository')
    def test_delete_saved_answer_logs_error_on_exception(self, mock_repo, mock_logger):
        """Test that errors are logged when exception occurs."""
        error_msg = "Connection timeout"
        mock_repo.admin_delete_saved_answer.side_effect = Exception(error_msg)

        result = self.service.delete_saved_answer(789)

        assert result is False
        mock_logger.error.assert_called_once()
        # Verify error message contains the exception
        error_call_args = mock_logger.error.call_args[0][0]
        assert "Error deleting saved answer" in error_call_args
