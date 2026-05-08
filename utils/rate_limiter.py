"""
Rate limiting utilities for login attempts.
Uses in-memory storage (can be upgraded to Redis).
"""

import time
from collections import defaultdict
from threading import Lock

# In-memory storage for login attempts
# Format: {username: [(timestamp, success), ...]}
login_attempts = defaultdict(list)
attempts_lock = Lock()

# Configuration
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300  # 5 minutes


def check_login_attempts(username, max_attempts=MAX_ATTEMPTS, window=WINDOW_SECONDS):
    """
    Check if user has exceeded login attempt limit.
    
    Args:
        username: Username to check
        max_attempts: Maximum allowed attempts
        window: Time window in seconds
        
    Returns:
        tuple: (allowed: bool, remaining_attempts: int, retry_after: int)
    """
    with attempts_lock:
        now = time.time()
        cutoff = now - window
        
        # Get attempts within window
        if username in login_attempts:
            # Remove old attempts
            login_attempts[username] = [
                (ts, success) for ts, success in login_attempts[username]
                if ts > cutoff
            ]
            
            # Count failed attempts
            failed_attempts = sum(
                1 for ts, success in login_attempts[username]
                if not success
            )
            
            if failed_attempts >= max_attempts:
                # Calculate retry after time
                oldest_attempt = min(ts for ts, _ in login_attempts[username])
                retry_after = int(window - (now - oldest_attempt))
                return False, 0, retry_after
            
            remaining = max_attempts - failed_attempts
            return True, remaining, 0
        
        return True, max_attempts, 0


def record_login_attempt(username, success):
    """
    Record a login attempt.
    
    Args:
        username: Username
        success: Whether login was successful
    """
    with attempts_lock:
        now = time.time()
        login_attempts[username].append((now, success))
        
        # If successful, clear old failed attempts
        if success:
            cutoff = now - WINDOW_SECONDS
            login_attempts[username] = [
                (ts, succ) for ts, succ in login_attempts[username]
                if ts > cutoff and succ
            ]


def clear_login_attempts(username):
    """
    Clear all login attempts for a user.
    
    Args:
        username: Username to clear
    """
    with attempts_lock:
        if username in login_attempts:
            del login_attempts[username]


def cleanup_old_attempts():
    """
    Cleanup old login attempts (call periodically).
    """
    with attempts_lock:
        now = time.time()
        cutoff = now - WINDOW_SECONDS
        
        # Remove old attempts
        for username in list(login_attempts.keys()):
            login_attempts[username] = [
                (ts, success) for ts, success in login_attempts[username]
                if ts > cutoff
            ]
            
            # Remove empty entries
            if not login_attempts[username]:
                del login_attempts[username]
