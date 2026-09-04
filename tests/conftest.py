"""
Pytest fixtures and configuration.
"""

import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force test database URL before importing app/db modules
os.environ["DATABASE_URL"] = "sqlite:///test_runs.db"
# Allow insecure SECRET_KEY in test mode (see app.py startup check)
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")
os.environ.setdefault("GOOGLE_CLIENT_ID", "mock-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "mock-client-secret")

import pytest
from app import app as flask_app
from db import get_db
from models.user import User


@pytest.fixture
def app():
    """Configure and yield the test Flask application."""
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['BCRYPT_LOG_ROUNDS'] = 4  # Fast hashing for tests
    flask_app.config['RATELIMIT_ENABLED'] = False  # Prevent limiter bleed across tests
    
    from extensions import bcrypt, limiter
    limiter.enabled = False
    bcrypt.init_app(flask_app)
    
    import db
    import uuid
    # Use a unique in-memory database per test to guarantee clean state and prevent file locks
    db_id = str(uuid.uuid4())
    db.DATABASE_URL = f"sqlite:///file:{db_id}?mode=memory&cache=shared"
    os.environ["DATABASE_URL"] = db.DATABASE_URL
             
    # Hold a connection open to prevent SQLite from destroying the shared in-memory DB when init_db() closes its connection
    _keepalive_conn = db.get_db()
    
    # Ensure test database exists and has schema
    init_test_db()
    
    yield flask_app
    
    _keepalive_conn.close()


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
    client.post('/register', data={
        'username': 'testuser',
        'pin': '1234'
    })
    
    client.post('/login', data={
        'username': 'testuser',
        'pin': '1234'
    })
    
    return client


@pytest.fixture
def admin_client(client, app):
    """Create an authenticated admin test client."""
    with app.app_context():
        # Register admin user
        client.post('/register', data={
            'username': 'admin',
            'pin': '9999'
        })
        
        # Promote to admin
        conn = get_db()
        conn.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
        conn.commit()
        conn.close()
        
        # Login
        client.post('/login', data={
            'username': 'admin',
            'pin': '9999'
        })
    
    return client


def init_test_db():
    """Initialize test database with schema."""
    from app import init_db
    init_db()


@pytest.fixture
def sample_user(app):
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
