"""
Tests for rate limiting functionality.
"""

import pytest
import time
from utils.rate_limiter import (
    check_login_attempts,
    record_login_attempt,
    clear_login_attempts,
    cleanup_old_attempts
)


class TestRateLimiter:
    """Test rate limiting for login attempts."""
    
    def setup_method(self):
        """Clear attempts before each test."""
        from utils.rate_limiter import login_attempts
        login_attempts.clear()
    
    def test_first_attempt_allowed(self):
        """Test first login attempt is allowed."""
        allowed, remaining, retry_after = check_login_attempts('user1')
        
        assert allowed is True
        assert remaining == 5
        assert retry_after == 0
    
    def test_multiple_failed_attempts(self):
        """Test multiple failed attempts."""
        username = 'user2'
        
        # Record 4 failed attempts
        for i in range(4):
            record_login_attempt(username, success=False)
            allowed, remaining, _ = check_login_attempts(username)
            assert allowed is True
            assert remaining == 5 - (i + 1)
        
        # 5th attempt should still be allowed
        allowed, remaining, _ = check_login_attempts(username)
        assert allowed is True
        assert remaining == 1
        
        # Record 5th failed attempt
        record_login_attempt(username, success=False)
        
        # 6th attempt should be blocked
        allowed, remaining, retry_after = check_login_attempts(username)
        assert allowed is False
        assert remaining == 0
        assert retry_after > 0
    
    def test_successful_login_clears_attempts(self):
        """Test successful login clears failed attempts."""
        username = 'user3'
        
        # Record 3 failed attempts
        for _ in range(3):
            record_login_attempt(username, success=False)
        
        # Successful login
        record_login_attempt(username, success=True)
        
        # Should be reset
        allowed, remaining, _ = check_login_attempts(username)
        assert allowed is True
        assert remaining == 5
    
    def test_clear_login_attempts(self):
        """Test manually clearing login attempts."""
        username = 'user4'
        
        # Record failed attempts
        for _ in range(3):
            record_login_attempt(username, success=False)
        
        # Clear attempts
        clear_login_attempts(username)
        
        # Should be reset
        allowed, remaining, _ = check_login_attempts(username)
        assert allowed is True
        assert remaining == 5
    
    def test_cleanup_old_attempts(self):
        """Test cleanup of old attempts."""
        username = 'user5'
        
        # Record attempt
        record_login_attempt(username, success=False)
        
        # Manually set old timestamp (simulate old attempt)
        from utils.rate_limiter import login_attempts
        old_time = time.time() - 400  # 400 seconds ago (> 5 min window)
        login_attempts[username] = [(old_time, False)]
        
        # Cleanup
        cleanup_old_attempts()
        
        # Should be cleared
        assert username not in login_attempts or len(login_attempts[username]) == 0
    
    def test_different_users_independent(self):
        """Test that different users have independent rate limits."""
        user1 = 'alice'
        user2 = 'bob'
        
        # Block user1
        for _ in range(5):
            record_login_attempt(user1, success=False)
        
        # user1 should be blocked
        allowed1, _, _ = check_login_attempts(user1)
        assert allowed1 is False
        
        # user2 should still be allowed
        allowed2, remaining2, _ = check_login_attempts(user2)
        assert allowed2 is True
        assert remaining2 == 5
