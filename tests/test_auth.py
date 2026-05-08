"""
Tests for authentication functionality.
"""

import pytest
from services.auth_service import authenticate_user, register_user, change_user_pin
from models.user import User
from utils.validators import ValidationError


class TestUserModel:
    """Test User model."""
    
    def test_hash_pin(self):
        """Test PIN hashing."""
        pin = "1234"
        hashed = User.hash_pin(pin)
        
        assert hashed != pin
        assert len(hashed) > 20  # Bcrypt hashes are long
    
    def test_check_pin_correct(self, sample_user):
        """Test PIN verification with correct PIN."""
        user = User(sample_user)
        assert user.check_pin('1234') is True
    
    def test_check_pin_incorrect(self, sample_user):
        """Test PIN verification with incorrect PIN."""
        user = User(sample_user)
        assert user.check_pin('9999') is False
    
    def test_is_admin(self, sample_user):
        """Test admin role check."""
        sample_user['role'] = 'admin'
        user = User(sample_user)
        assert user.is_admin is True
    
    def test_is_not_admin(self, sample_user):
        """Test non-admin role check."""
        user = User(sample_user)
        assert user.is_admin is False
    
    def test_is_active(self, sample_user):
        """Test active status check."""
        user = User(sample_user)
        assert user.is_active is True
    
    def test_is_blocked(self, sample_user):
        """Test blocked status check."""
        sample_user['status'] = 'blocked'
        user = User(sample_user)
        assert user.is_blocked is True


class TestAuthentication:
    """Test authentication service."""
    
    def test_register_user_success(self, app):
        """Test successful user registration."""
        with app.app_context():
            success, user_id, error = register_user('newuser', '1234')
            
            assert success is True
            assert user_id is not None
            assert error is None
    
    def test_register_user_duplicate(self, app):
        """Test registration with duplicate username."""
        with app.app_context():
            register_user('duplicate', '1234')
            success, user_id, error = register_user('duplicate', '5678')
            
            assert success is False
            assert user_id is None
            assert 'already taken' in error.lower()
    
    def test_register_user_invalid_pin(self, app):
        """Test registration with invalid PIN."""
        with app.app_context():
            success, user_id, error = register_user('user', '12')  # Too short
            
            assert success is False
            assert 'at least 4 digits' in error.lower()
    
    def test_authenticate_user_success(self, app):
        """Test successful authentication."""
        with app.app_context():
            register_user('authuser', '1234')
            success, user, error = authenticate_user('authuser', '1234')
            
            assert success is True
            assert user is not None
            assert user.username == 'authuser'
            assert error is None
    
    def test_authenticate_user_wrong_pin(self, app):
        """Test authentication with wrong PIN."""
        with app.app_context():
            register_user('authuser2', '1234')
            success, user, error = authenticate_user('authuser2', '9999')
            
            assert success is False
            assert user is None
            assert 'invalid' in error.lower()
    
    def test_authenticate_user_nonexistent(self, app):
        """Test authentication with nonexistent user."""
        with app.app_context():
            success, user, error = authenticate_user('ghost', '1234')
            
            assert success is False
            assert user is None
            assert 'invalid' in error.lower()
    
    def test_change_pin_success(self, app):
        """Test successful PIN change."""
        with app.app_context():
            success, user_id, _ = register_user('pinchange', '1234')
            success, error = change_user_pin(user_id, '1234', '5678')
            
            assert success is True
            assert error is None
            
            # Verify new PIN works
            success, user, _ = authenticate_user('pinchange', '5678')
            assert success is True
    
    def test_change_pin_wrong_current(self, app):
        """Test PIN change with wrong current PIN."""
        with app.app_context():
            success, user_id, _ = register_user('pinchange2', '1234')
            success, error = change_user_pin(user_id, '9999', '5678')
            
            assert success is False
            assert 'incorrect' in error.lower()
    
    def test_change_pin_same_as_current(self, app):
        """Test PIN change with same PIN."""
        with app.app_context():
            success, user_id, _ = register_user('pinchange3', '1234')
            success, error = change_user_pin(user_id, '1234', '1234')
            
            assert success is False
            assert 'different' in error.lower()


class TestAuthRoutes:
    """Test authentication routes."""
    
    def test_register_page(self, client):
        """Test register page loads."""
        response = client.get('/auth/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower()
    
    def test_login_page(self, client):
        """Test login page loads."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
    
    def test_register_post(self, client):
        """Test user registration via POST."""
        response = client.post('/auth/register', data={
            'username': 'webuser',
            'pin': '1234'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_login_post(self, client):
        """Test user login via POST."""
        # Register first
        client.post('/auth/register', data={
            'username': 'loginuser',
            'pin': '1234'
        })
        
        # Login
        response = client.post('/auth/login', data={
            'username': 'loginuser',
            'pin': '1234'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_logout(self, auth_client):
        """Test logout."""
        response = auth_client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify can't access protected route
        response = auth_client.get('/dashboard')
        assert response.status_code == 302  # Redirect to login
    
    def test_protected_route_without_login(self, client):
        """Test accessing protected route without login."""
        response = client.get('/dashboard')
        assert response.status_code == 302  # Redirect to login
