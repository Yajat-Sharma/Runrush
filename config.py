"""
Configuration management for RunRush.
Supports multiple environments: development, testing, production.
"""

import os
from datetime import timedelta


class Config:
    """Base configuration."""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///runs.db')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Session
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
    WTF_CSRF_SSL_STRICT = False  # Set True in production with HTTPS
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True
    
    # Email
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'RunRush <noreply@runrush.app>')
    
    # Admin
    ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID', '1')
    
    # Security
    BCRYPT_LOG_ROUNDS = 12  # Cost factor for bcrypt
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_ATTEMPT_WINDOW = 300  # 5 minutes in seconds
    
    # API
    API_VERSION = 'v1'
    API_TITLE = 'RunRush API'
    API_DESCRIPTION = 'REST API for RunRush running tracker'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Disable CSRF in development for easier testing


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    DATABASE_URL = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    BCRYPT_LOG_ROUNDS = 4  # Faster hashing for tests


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True

    @classmethod
    def validate(cls):
        """Validate critical production settings at runtime (not import time)."""
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError(
                'SECRET_KEY must be set via environment variable in production. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on FLASK_ENV environment variable."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
