"""
Authentication service - handles user authentication and authorization.
"""

import os
from datetime import datetime
from flask import session
from db import get_db, IntegrityError
from models.user import User
from utils.validators import validate_username, validate_pin, ValidationError


def get_current_user():
    """
    Get currently logged-in user from session.
    
    Returns:
        User: User object or None
    """
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    try:
        user_row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (session['user_id'],)
        ).fetchone()
        
        if not user_row:
            return None
        
        return User(dict(user_row))
    finally:
        conn.close()


def get_user_role(user):
    """
    Get user's role with super admin check.
    
    Args:
        user: User object
        
    Returns:
        str: 'admin', 'moderator', or 'user'
    """
    if not user:
        return None
    
    # Super Admin Check (from environment)
    admin_id = os.environ.get("ADMIN_USER_ID")
    if admin_id and str(user.id) == str(admin_id):
        return "admin"
    
    # Database role
    return user.role if user.role in ["admin", "moderator"] else "user"


def authenticate_user(username, pin):
    """
    Authenticate user with username and PIN.
    
    Args:
        username: Username
        pin: PIN (will be checked against hash)
        
    Returns:
        tuple: (success: bool, user: User or None, error: str or None)
    """
    try:
        # Validate inputs
        username = validate_username(username)
        pin = validate_pin(pin)
    except ValidationError as e:
        return False, None, str(e)
    
    conn = get_db()
    try:
        user_row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        
        if not user_row:
            return False, None, "Invalid username or PIN"
        
        user = User(dict(user_row))
        
        # Check if blocked
        if user.is_blocked:
            return False, None, "Your account has been blocked"
        
        # Verify PIN
        if not user.check_pin(pin):
            return False, None, "Invalid username or PIN"
        
        # Update last login
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (now_str, user.id)
        )
        conn.commit()
        
        # Log activity
        log_activity(user.id, "LOGIN", "User logged in")
        
        return True, user, None
        
    finally:
        conn.close()


def register_user(username, pin):
    """
    Register a new user.
    
    Args:
        username: Username
        pin: PIN (will be hashed)
        
    Returns:
        tuple: (success: bool, user_id: int or None, error: str or None)
    """
    try:
        # Validate inputs
        username = validate_username(username)
        pin = validate_pin(pin)
    except ValidationError as e:
        return False, None, str(e)
    
    # Hash PIN
    pin_hash = User.hash_pin(pin)
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, pin) VALUES (?, ?)",
            (username, pin_hash)
        )
        conn.commit()
        
        # Get user ID
        user_row = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        
        user_id = user_row['id']
        
        # Log activity
        log_activity(user_id, "REGISTER", "User registered")
        
        return True, user_id, None
        
    except IntegrityError:
        return False, None, "Username already taken"
    finally:
        conn.close()


def change_user_pin(user_id, current_pin, new_pin):
    """
    Change user's PIN.
    
    Args:
        user_id: User ID
        current_pin: Current PIN
        new_pin: New PIN
        
    Returns:
        tuple: (success: bool, error: str or None)
    """
    try:
        # Validate new PIN
        new_pin = validate_pin(new_pin)
    except ValidationError as e:
        return False, str(e)
    
    conn = get_db()
    try:
        # Get user
        user_row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        
        if not user_row:
            return False, "User not found"
        
        user = User(dict(user_row))
        
        # Verify current PIN
        if not user.check_pin(current_pin):
            return False, "Current PIN is incorrect"
        
        # Check if new PIN is same as current
        if user.check_pin(new_pin):
            return False, "New PIN must be different from current PIN"
        
        # Hash new PIN
        new_pin_hash = User.hash_pin(new_pin)
        
        # Update PIN
        conn.execute(
            "UPDATE users SET pin = ? WHERE id = ?",
            (new_pin_hash, user_id)
        )
        conn.commit()
        
        # Log activity
        log_activity(user_id, "CHANGE_PIN", "User changed PIN")
        
        return True, None
        
    finally:
        conn.close()


def log_activity(user_id, action, details=None):
    """
    Log user activity to audit trail.
    
    Args:
        user_id: User ID (can be None for system actions)
        action: Action type
        details: Optional details
    """
    try:
        conn = get_db()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now_str)
        )
        conn.commit()
        conn.close()
    except Exception:
        # Don't fail if logging fails
        pass


def validate_api_key(api_key):
    """
    Validate API key (placeholder for future implementation).
    
    Args:
        api_key: API key to validate
        
    Returns:
        bool: True if valid
    """
    # TODO: Implement API key validation
    # For now, check against environment variable
    valid_key = os.environ.get('API_KEY')
    return valid_key and api_key == valid_key
