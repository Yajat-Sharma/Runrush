"""
Authentication blueprint - Login, register, logout routes.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import limiter
from services.auth_service import authenticate_user, register_user
from utils.rate_limiter import check_login_attempts, record_login_attempt, clear_login_attempts

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    """User registration."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        pin = request.form.get('pin', '').strip()
        
        # Register user
        success, user_id, error = register_user(username, pin)
        
        if not success:
            return render_template('register.html', error=error)
        
        # Auto-login after registration
        session['user_id'] = user_id
        session['username'] = username
        
        return redirect(url_for('dashboard.onboarding'))
    
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def login():
    """User login."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        pin = request.form.get('pin', '').strip()
        
        # Check rate limiting
        allowed, remaining, retry_after = check_login_attempts(username)
        
        if not allowed:
            error = f"Too many failed login attempts. Please try again in {retry_after} seconds."
            return render_template('login.html', error=error)
        
        # Authenticate
        success, user, error = authenticate_user(username, pin)
        
        # Record attempt
        record_login_attempt(username, success)
        
        if not success:
            flash(f"Login failed. {remaining - 1} attempts remaining.", 'warning')
            return render_template('login.html', error=error)
        
        # Clear rate limit on successful login
        clear_login_attempts(username)
        
        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        session.permanent = True  # Use PERMANENT_SESSION_LIFETIME from config
        
        return redirect(url_for('dashboard.index'))
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """User logout."""
    session.clear()
    return redirect(url_for('auth.login'))
