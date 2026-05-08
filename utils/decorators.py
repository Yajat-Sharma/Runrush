"""
Custom decorators for route protection.
"""

from functools import wraps
from flask import session, redirect, url_for, render_template, request, jsonify


def login_required(f):
    """
    Decorator to require login for a route.
    Redirects to login page if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # For API routes, return JSON error
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            # For web routes, redirect to login
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin role.
    Returns 403 if user is not admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login'))
        
        # Import here to avoid circular imports
        from services.auth_service import get_current_user, get_user_role
        
        user = get_current_user()
        if not user or get_user_role(user) != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Forbidden - Admin access required'}), 403
            return render_template('403.html'), 403
        
        return f(*args, **kwargs)
    return decorated_function


def moderator_required(f):
    """
    Decorator to require moderator or admin role.
    Returns 403 if user is not moderator/admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login'))
        
        # Import here to avoid circular imports
        from services.auth_service import get_current_user, get_user_role
        
        user = get_current_user()
        role = get_user_role(user)
        
        if not user or role not in ['admin', 'moderator']:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Forbidden - Moderator access required'}), 403
            return render_template('403.html'), 403
        
        return f(*args, **kwargs)
    return decorated_function


def api_key_required(f):
    """
    Decorator to require API key for external API access.
    Checks X-API-Key header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Import here to avoid circular imports
        from services.auth_service import validate_api_key
        
        if not validate_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function
