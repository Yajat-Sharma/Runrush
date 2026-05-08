"""
User model with password hashing.
"""

from extensions import bcrypt


class User:
    """User model with password hashing methods."""
    
    def __init__(self, user_dict):
        """Initialize from database row dict."""
        self.id = user_dict.get('id')
        self.username = user_dict.get('username')
        self.pin_hash = user_dict.get('pin')  # Now stores hash
        self.display_name = user_dict.get('display_name')
        self.weight = user_dict.get('weight')
        self.height = user_dict.get('height')
        self.weekly_goal_km = user_dict.get('weekly_goal_km')
        self.theme = user_dict.get('theme')
        self.last_login = user_dict.get('last_login')
        self.role = user_dict.get('role', 'user')
        self.status = user_dict.get('status', 'active')
        self.email = user_dict.get('email')
        self.email_weekly_summary = user_dict.get('email_weekly_summary', 1)
    
    @staticmethod
    def hash_pin(pin):
        """Hash a PIN using bcrypt."""
        return bcrypt.generate_password_hash(pin)
    
    def check_pin(self, pin):
        """Check if provided PIN matches stored hash."""
        if not self.pin_hash:
            return False
        return bcrypt.check_password_hash(self.pin_hash, pin)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'weight': self.weight,
            'height': self.height,
            'weekly_goal_km': self.weekly_goal_km,
            'theme': self.theme,
            'last_login': self.last_login,
            'role': self.role,
            'status': self.status,
            'email': self.email,
            'email_weekly_summary': self.email_weekly_summary
        }
    
    @property
    def is_admin(self):
        """Check if user is admin."""
        return self.role == 'admin'
    
    @property
    def is_moderator(self):
        """Check if user is moderator or admin."""
        return self.role in ['admin', 'moderator']
    
    @property
    def is_active(self):
        """Check if user account is active."""
        return self.status == 'active'
    
    @property
    def is_blocked(self):
        """Check if user account is blocked."""
        return self.status == 'blocked'
