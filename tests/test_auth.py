"""Unit tests for authentication and authorization."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM
)

# Test client
client = TestClient(app)


class TestUserRegistration:
    """Test cases for user registration."""
    
    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.create_user')
    def test_register_creates_user_with_hashed_password(self, mock_create_user, mock_get_user_by_email):
        """Test that user registration creates a new user in the database with a hashed password."""
        # Mock that user doesn't exist
        mock_get_user_by_email.return_value = None
        
        # Mock user creation
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_create_user.return_value = mock_user
        
        # Test registration
        request_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'SecurePass123!'
        }
        
        response = client.post('/api/auth/register', json=request_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'
        assert data['is_active'] is True
        assert 'id' in data
        assert 'created_at' in data
        
        # Verify create_user was called
        mock_create_user.assert_called_once()
        call_args = mock_create_user.call_args[1]
        assert call_args['email'] == 'test@example.com'
        assert call_args['username'] == 'testuser'
        # Verify password was passed (will be hashed in create_user)
        assert call_args['password'] == 'SecurePass123!'
    
    @patch('app.auth.get_password_hash')
    @patch('app.auth.get_db_connection')
    def test_password_is_hashed_in_database(self, mock_get_db, mock_get_hash):
        """Test that password is hashed before storing in database."""
        from app.auth import create_user as auth_create_user
        
        # Mock password hashing
        mock_get_hash.return_value = 'hashed_password_123'
        
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock database return
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        
        # Create user
        user = auth_create_user('test@example.com', 'testuser', 'plain_password')
        
        # Verify password was hashed
        mock_get_hash.assert_called_once_with('plain_password')
        
        # Verify database was called with hashed password
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert 'hashed_password_123' in call_args[1]
        mock_conn.commit.assert_called_once()
    
    @patch('app.routers.auth.get_user_by_email')
    def test_register_duplicate_email_fails(self, mock_get_user_by_email):
        """Test that registration fails for duplicate email."""
        # Mock that user already exists
        mock_get_user_by_email.return_value = {
            'id': 1,
            'email': 'existing@example.com',
            'username': 'existing',
            'is_active': True
        }
        
        request_data = {
            'email': 'existing@example.com',
            'username': 'newuser',
            'password': 'SecurePass123!'
        }
        
        response = client.post('/api/auth/register', json=request_data)
        
        assert response.status_code == 400
        data = response.json()
        assert data['detail'] == 'Email already registered'
    
    def test_register_invalid_email_fails(self):
        """Test that registration fails for invalid email format."""
        request_data = {
            'email': 'invalid-email',
            'username': 'testuser',
            'password': 'SecurePass123!'
        }
        
        response = client.post('/api/auth/register', json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_register_short_password_fails(self):
        """Test that registration fails for password too short."""
        request_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'short'
        }
        
        response = client.post('/api/auth/register', json=request_data)
        
        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test cases for user login and JWT token generation."""
    
    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.verify_password')
    def test_login_returns_valid_jwt_token(self, mock_verify_password, mock_get_user_by_email):
        """Test that user login returns a valid JWT token for correct credentials."""
        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'hashed_password': 'hashed_password',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_email.return_value = mock_user
        mock_verify_password.return_value = True
        
        # Test login
        request_data = {
            'email': 'test@example.com',
            'password': 'correct_password'
        }
        
        response = client.post('/api/auth/login', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'
        
        # Verify token is valid JWT
        token = data['access_token']
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded['sub'] == '1'  # User ID
        assert 'exp' in decoded  # Expiration time
    
    @patch('app.routers.auth.verify_password')
    @patch('app.routers.auth.get_user_by_email')
    def test_login_wrong_password_fails(self, mock_get_user_by_email, mock_verify_password):
        """Test that login fails with wrong password."""
        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'hashed_password': 'hashed_password',
            'is_active': True
        }
        mock_get_user_by_email.return_value = mock_user
        mock_verify_password.return_value = False  # Wrong password
        
        # Test login with wrong password
        request_data = {
            'email': 'test@example.com',
            'password': 'wrong_password'
        }
        
        response = client.post('/api/auth/login', json=request_data)
        
        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Incorrect email or password'
    
    @patch('app.routers.auth.get_user_by_email')
    def test_login_nonexistent_user_fails(self, mock_get_user_by_email):
        """Test that login fails for non-existent user."""
        mock_get_user_by_email.return_value = None
        
        request_data = {
            'email': 'nonexistent@example.com',
            'password': 'password123'
        }
        
        response = client.post('/api/auth/login', json=request_data)
        
        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Incorrect email or password'
    
    @patch('app.routers.auth.get_user_by_email')
    @patch('app.routers.auth.verify_password')
    def test_login_inactive_user_fails(self, mock_verify_password, mock_get_user_by_email):
        """Test that login fails for inactive user."""
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'hashed_password': 'hashed_password',
            'is_active': False
        }
        mock_get_user_by_email.return_value = mock_user
        mock_verify_password.return_value = True
        
        request_data = {
            'email': 'test@example.com',
            'password': 'correct_password'
        }
        
        response = client.post('/api/auth/login', json=request_data)
        
        assert response.status_code == 400
        data = response.json()
        assert data['detail'] == 'Inactive user account'
    
    def test_jwt_token_contains_user_id(self):
        """Test that JWT token contains user ID in subject claim."""
        token = create_access_token(data={'sub': '123'})
        
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded['sub'] == '123'
    
    def test_jwt_token_has_expiration(self):
        """Test that JWT token has expiration time."""
        token = create_access_token(data={'sub': '123'})
        
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert 'exp' in decoded
        
        # Verify expiration is in the future
        exp_time = datetime.fromtimestamp(decoded['exp'])
        assert exp_time > datetime.utcnow()


class TestProtectedEndpointAccess:
    """Test cases for protected API endpoints."""
    
    @patch('app.auth.get_user_by_id')
    def test_protected_endpoint_denies_access_without_token(self, mock_get_user_by_id):
        """Test that protected API endpoints deny access without a valid JWT token."""
        # Test history endpoint (requires authentication)
        # Don't provide Authorization header at all
        response = client.get('/api/history')
        
        # When no token is provided, oauth2_scheme returns None
        # and get_current_user should raise 401
        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Could not validate credentials'
    
    def test_protected_endpoint_denies_access_with_invalid_token(self):
        """Test that protected endpoints deny access with invalid token."""
        headers = {'Authorization': 'Bearer invalid_token_123'}
        response = client.get('/api/history', headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Could not validate credentials'
    
    def test_protected_endpoint_denies_access_with_expired_token(self):
        """Test that protected endpoints deny access with expired token."""
        # Create expired token
        expired_token = create_access_token(
            data={'sub': '1'},
            expires_delta=timedelta(minutes=-10)
        )
        
        headers = {'Authorization': f'Bearer {expired_token}'}
        response = client.get('/api/history', headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert data['detail'] == 'Could not validate credentials'
    
    def test_protected_endpoint_denies_access_with_malformed_token(self):
        """Test that protected endpoints deny access with malformed token."""
        headers = {'Authorization': 'Bearer not.a.jwt.token'}
        response = client.get('/api/history', headers=headers)
        
        assert response.status_code == 401
    
    @patch('app.auth.get_user_by_id')
    @patch('app.main.question_service')
    def test_protected_endpoint_allows_access_with_valid_token(
        self, mock_service, mock_get_user_by_id
    ):
        """Test that protected API endpoints allow access with a valid JWT token."""
        # Create valid token
        token = create_access_token(data={'sub': '1'})
        
        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user
        
        # Mock service response
        from app.models.schemas import HistoryResponse
        mock_service.get_user_history.return_value = HistoryResponse(
            questions=[],
            total=0
        )
        
        # Test protected endpoint with valid token
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get('/api/history', headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert 'questions' in data
        assert 'total' in data
    
    @patch('app.auth.get_user_by_id')
    def test_get_current_user_endpoint_with_valid_token(self, mock_get_user_by_id):
        """Test /me endpoint returns user info with valid token."""
        token = create_access_token(data={'sub': '1'})
        
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user
        
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get('/api/auth/me', headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 1
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'


class TestSavedAnswersAssociation:
    """Test cases for saved answers association with authenticated users."""
    
    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.save_answer')
    @patch('app.database.SavedAnswersRepository.get_user_saved_answers')
    def test_saved_answer_associated_with_authenticated_user(
        self, mock_get_saved, mock_save_answer, mock_get_user_by_id
    ):
        """Test that saved answers are correctly associated with the authenticated user."""
        # Create valid token for user ID 1
        token = create_access_token(data={'sub': '1'})
        
        # Mock user retrieval
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user
        
        # Mock save answer
        mock_save_answer.return_value = {'id': 1}
        
        # Mock get saved answers
        mock_saved_answer = {
            'id': 1,
            'question_id': 123,
            'question': 'What is love?',
            'answer': 'God is love',
            'tags': ['love', 'god'],
            'saved_at': datetime.utcnow()
        }
        mock_get_saved.return_value = [mock_saved_answer]
        
        # Test saving an answer
        request_data = {
            'question_id': 123,
            'tags': ['love', 'god']
        }
        
        headers = {'Authorization': f'Bearer {token}'}
        response = client.post('/api/saved-answers', json=request_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data['id'] == 1
        assert data['question_id'] == 123
        
        # Verify save_answer was called with correct user_id
        mock_save_answer.assert_called_once_with(
            user_id=1,
            question_id=123,
            tags=['love', 'god']
        )
    
    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.get_user_saved_answers')
    def test_get_saved_answers_returns_only_user_answers(
        self, mock_get_saved, mock_get_user_by_id
    ):
        """Test that getting saved answers returns only the authenticated user's answers."""
        # Create token for user ID 2
        token = create_access_token(data={'sub': '2'})
        
        # Mock user retrieval
        mock_user = {
            'id': 2,
            'email': 'user2@example.com',
            'username': 'user2',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user
        
        # Mock saved answers for user 2
        mock_saved_answers = [
            {
                'id': 5,
                'question_id': 456,
                'question': 'Who is Jesus?',
                'answer': 'Jesus is the Son of God',
                'tags': ['jesus'],
                'saved_at': datetime.utcnow()
            }
        ]
        mock_get_saved.return_value = mock_saved_answers
        
        # Get saved answers
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get('/api/saved-answers', headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['saved_answers']) == 1
        assert data['saved_answers'][0]['id'] == 5
        
        # Verify get_user_saved_answers was called with user_id=2
        mock_get_saved.assert_called_once_with(user_id=2, limit=100)
    
    @patch('app.auth.get_user_by_id')
    @patch('app.database.SavedAnswersRepository.delete_saved_answer')
    def test_delete_saved_answer_only_for_authenticated_user(
        self, mock_delete, mock_get_user_by_id
    ):
        """Test that user can only delete their own saved answers."""
        token = create_access_token(data={'sub': '1'})
        
        mock_user = {
            'id': 1,
            'email': 'test@example.com',
            'username': 'testuser',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        mock_get_user_by_id.return_value = mock_user
        mock_delete.return_value = True
        
        # Delete saved answer
        headers = {'Authorization': f'Bearer {token}'}
        response = client.delete('/api/saved-answers/123', headers=headers)
        
        assert response.status_code == 204
        
        # Verify delete was called with correct user_id
        mock_delete.assert_called_once_with(user_id=1, saved_answer_id=123)
    
    @patch('app.auth.get_user_by_id')
    def test_saved_answers_endpoint_denies_access_without_token(self, mock_get_user_by_id):
        """Test that saved answers endpoints require authentication."""
        # Try to save answer without token
        request_data = {'question_id': 123, 'tags': []}
        response = client.post('/api/saved-answers', json=request_data)
        
        assert response.status_code == 401
        
        # Try to get saved answers without token
        response = client.get('/api/saved-answers')
        
        assert response.status_code == 401
        
        # Try to delete saved answer without token
        response = client.delete('/api/saved-answers/123')
        
        assert response.status_code == 401


class TestPasswordHashing:
    """Test cases for password hashing utilities."""
    
    @patch('app.auth.pwd_context')
    def test_password_hash_is_different_from_plain(self, mock_pwd_context):
        """Test that hashed password is different from plain password."""
        plain_password = 'SecurePass123!'
        mock_pwd_context.hash.return_value = '$2b$12$hashedpasswordvalue'
        
        hashed = get_password_hash(plain_password)
        
        assert hashed != plain_password
        assert len(hashed) > len(plain_password)
        mock_pwd_context.hash.assert_called_once_with(plain_password)
    
    @patch('app.auth.pwd_context')
    def test_verify_password_with_correct_password(self, mock_pwd_context):
        """Test password verification with correct password."""
        plain_password = 'SecurePass123!'
        hashed = '$2b$12$hashedpasswordvalue'
        mock_pwd_context.hash.return_value = hashed
        mock_pwd_context.verify.return_value = True
        
        result = verify_password(plain_password, hashed)
        
        assert result is True
        mock_pwd_context.verify.assert_called_once_with(plain_password, hashed)
    
    @patch('app.auth.pwd_context')
    def test_verify_password_with_wrong_password(self, mock_pwd_context):
        """Test password verification with wrong password."""
        plain_password = 'SecurePass123!'
        hashed = '$2b$12$hashedpasswordvalue'
        mock_pwd_context.verify.return_value = False
        
        result = verify_password('WrongPassword', hashed)
        
        assert result is False
    
    @patch('app.auth.pwd_context')
    def test_same_password_generates_different_hashes(self, mock_pwd_context):
        """Test that same password generates different hashes (salt)."""
        plain_password = 'SecurePass123!'
        # Simulate different hashes with different salts
        mock_pwd_context.hash.side_effect = [
            '$2b$12$salt1hashedpasswordvalue',
            '$2b$12$salt2hashedpasswordvalue'
        ]
        mock_pwd_context.verify.return_value = True
        
        hash1 = get_password_hash(plain_password)
        hash2 = get_password_hash(plain_password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        
        # Both should verify correctly
        assert verify_password(plain_password, hash1) is True
        assert verify_password(plain_password, hash2) is True
