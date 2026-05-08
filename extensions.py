"""
Flask extensions initialization.
Extensions are initialized here and imported by blueprints.
"""

from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt as bcrypt_lib

# CSRF Protection
csrf = CSRFProtect()

# Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Will be overridden by config
)

# Bcrypt wrapper
class BcryptWrapper:
    """Wrapper for bcrypt to match Flask-Bcrypt API."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        self.log_rounds = app.config.get('BCRYPT_LOG_ROUNDS', 12)
    
    def generate_password_hash(self, password):
        """Generate password hash."""
        if isinstance(password, str):
            password = password.encode('utf-8')
        return bcrypt_lib.hashpw(password, bcrypt_lib.gensalt(self.log_rounds)).decode('utf-8')
    
    def check_password_hash(self, pw_hash, password):
        """Check password against hash."""
        if isinstance(password, str):
            password = password.encode('utf-8')
        if isinstance(pw_hash, str):
            pw_hash = pw_hash.encode('utf-8')
        return bcrypt_lib.checkpw(password, pw_hash)

bcrypt = BcryptWrapper()
