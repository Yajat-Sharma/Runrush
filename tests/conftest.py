"""
Pytest fixtures and configuration.
"""

import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app_new import create_app
from db import get_db
from models.user import User


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    app = create_app('testing')
    
    with app.app_context():
        # Initialize database
        init_test_db()
    
    yield app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def auth_client(client):
    """Create an authenticated test client."""
    # Register and login a test user
    client.post('/auth/register', data={
        'username': 'testuser',
        'pin': '1234'
    })
    
    client.post('/auth/login', data={
        'username': 'testuser',
        'pin': '1234'
    })
    
    return client


@pytest.fixture
def admin_client(client, app):
    """Create an authenticated admin test client."""
    with app.app_context():
        # Register admin user
        client.post('/auth/register', data={
            'username': 'admin',
            'pin': '9999'
        })
        
        # Promote to admin
        conn = get_db()
        conn.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
        conn.commit()
        conn.close()
        
        # Login
        client.post('/auth/login', data={
            'username': 'admin',
            'pin': '9999'
        })
    
    return client


def init_test_db():
    """Initialize test database with schema."""
    from app import init_db
    init_db()


@pytest.fixture
def sample_user():
    """Create a sample user dict."""
    return {
        'id': 1,
        'username': 'testuser',
        'pin': User.hash_pin('1234'),
        'display_name': 'Test User',
        'weight': 70.0,
        'height': 175.0,
        'weekly_goal_km': 20.0,
        'theme': 'dark',
        'last_login': None,
        'role': 'user',
        'status': 'active',
        'email': 'test@example.com',
        'email_weekly_summary': 1
    }


@pytest.fixture
def sample_run():
    """Create a sample run dict."""
    return {
        'date': '2026-05-01',
        'distance': 5.0,
        'time': 25.0,
        'run_type': 'easy',
        'notes': 'Morning run'
    }
