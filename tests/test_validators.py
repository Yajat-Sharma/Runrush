"""
Tests for input validators.
"""

import pytest
from datetime import date, timedelta
from utils.validators import (
    validate_pin,
    validate_distance,
    validate_time,
    validate_date,
    validate_pace,
    sanitize_notes,
    validate_email,
    validate_username,
    validate_run_type,
    ValidationError
)


class TestPINValidator:
    """Test PIN validation."""
    
    def test_valid_pin(self):
        """Test valid PIN."""
        assert validate_pin('1234') == '1234'
        assert validate_pin('123456') == '123456'
    
    def test_pin_too_short(self):
        """Test PIN too short."""
        with pytest.raises(ValidationError, match='at least 4 digits'):
            validate_pin('123')
    
    def test_pin_too_long(self):
        """Test PIN too long."""
        with pytest.raises(ValidationError, match='at most 8 digits'):
            validate_pin('123456789')
    
    def test_pin_non_numeric(self):
        """Test non-numeric PIN."""
        with pytest.raises(ValidationError, match='only digits'):
            validate_pin('12ab')
    
    def test_pin_empty(self):
        """Test empty PIN."""
        with pytest.raises(ValidationError, match='required'):
            validate_pin('')


class TestDistanceValidator:
    """Test distance validation."""
    
    def test_valid_distance(self):
        """Test valid distance."""
        assert validate_distance(5.0) == 5.0
        assert validate_distance('10.5') == 10.5
    
    def test_distance_zero(self):
        """Test zero distance."""
        with pytest.raises(ValidationError, match='greater than 0'):
            validate_distance(0)
    
    def test_distance_negative(self):
        """Test negative distance."""
        with pytest.raises(ValidationError, match='greater than 0'):
            validate_distance(-5)
    
    def test_distance_unrealistic(self):
        """Test unrealistic distance."""
        with pytest.raises(ValidationError, match='unrealistic'):
            validate_distance(600)
    
    def test_distance_invalid_format(self):
        """Test invalid distance format."""
        with pytest.raises(ValidationError, match='valid number'):
            validate_distance('abc')


class TestTimeValidator:
    """Test time validation."""
    
    def test_valid_time(self):
        """Test valid time."""
        assert validate_time(30.0) == 30.0
        assert validate_time('45.5') == 45.5
    
    def test_time_zero(self):
        """Test zero time."""
        with pytest.raises(ValidationError, match='greater than 0'):
            validate_time(0)
    
    def test_time_negative(self):
        """Test negative time."""
        with pytest.raises(ValidationError, match='greater than 0'):
            validate_time(-10)
    
    def test_time_unrealistic(self):
        """Test unrealistic time."""
        with pytest.raises(ValidationError, match='unrealistic'):
            validate_time(1500)  # > 24 hours


class TestDateValidator:
    """Test date validation."""
    
    def test_valid_date(self):
        """Test valid date."""
        today = date.today()
        date_str = today.strftime('%Y-%m-%d')
        assert validate_date(date_str) == today
    
    def test_future_date(self):
        """Test future date."""
        future = date.today() + timedelta(days=1)
        date_str = future.strftime('%Y-%m-%d')
        
        with pytest.raises(ValidationError, match='future'):
            validate_date(date_str)
    
    def test_invalid_format(self):
        """Test invalid date format."""
        with pytest.raises(ValidationError, match='Invalid date format'):
            validate_date('2026/05/01')
    
    def test_too_old_date(self):
        """Test date too far in past."""
        old = date.today() - timedelta(days=4000)
        date_str = old.strftime('%Y-%m-%d')
        
        with pytest.raises(ValidationError, match='too far in the past'):
            validate_date(date_str)


class TestPaceValidator:
    """Test pace validation."""
    
    def test_valid_pace(self):
        """Test valid pace."""
        pace = validate_pace(5.0, 25.0)  # 5 min/km
        assert pace == 5.0
    
    def test_pace_too_slow(self):
        """Test pace too slow."""
        with pytest.raises(ValidationError, match='too slow'):
            validate_pace(1.0, 35.0)  # 35 min/km
    
    def test_pace_too_fast(self):
        """Test pace too fast."""
        with pytest.raises(ValidationError, match='too fast'):
            validate_pace(10.0, 15.0)  # 1.5 min/km


class TestNoteSanitizer:
    """Test note sanitization."""
    
    def test_sanitize_plain_text(self):
        """Test sanitizing plain text."""
        notes = "Great run today!"
        assert sanitize_notes(notes) == "Great run today!"
    
    def test_sanitize_html(self):
        """Test sanitizing HTML."""
        notes = "<script>alert('xss')</script>Nice run"
        result = sanitize_notes(notes)
        assert '<script>' not in result
        assert 'Nice run' in result
    
    def test_sanitize_long_notes(self):
        """Test truncating long notes."""
        notes = "a" * 600
        result = sanitize_notes(notes, max_length=500)
        assert len(result) == 500
    
    def test_sanitize_empty(self):
        """Test sanitizing empty notes."""
        assert sanitize_notes('') == ''
        assert sanitize_notes(None) == ''


class TestEmailValidator:
    """Test email validation."""
    
    def test_valid_email(self):
        """Test valid email."""
        assert validate_email('test@example.com') == 'test@example.com'
        assert validate_email('user.name@domain.co.uk') == 'user.name@domain.co.uk'
    
    def test_invalid_email(self):
        """Test invalid email."""
        with pytest.raises(ValidationError, match='Invalid email'):
            validate_email('notanemail')
        
        with pytest.raises(ValidationError, match='Invalid email'):
            validate_email('@example.com')
    
    def test_email_too_long(self):
        """Test email too long."""
        long_email = 'a' * 250 + '@example.com'
        with pytest.raises(ValidationError, match='too long'):
            validate_email(long_email)
    
    def test_email_none(self):
        """Test None email."""
        assert validate_email(None) is None
        assert validate_email('') is None


class TestUsernameValidator:
    """Test username validation."""
    
    def test_valid_username(self):
        """Test valid username."""
        assert validate_username('user123') == 'user123'
        assert validate_username('test_user') == 'test_user'
    
    def test_username_too_short(self):
        """Test username too short."""
        with pytest.raises(ValidationError, match='at least 3'):
            validate_username('ab')
    
    def test_username_too_long(self):
        """Test username too long."""
        with pytest.raises(ValidationError, match='at most 30'):
            validate_username('a' * 31)
    
    def test_username_invalid_chars(self):
        """Test username with invalid characters."""
        with pytest.raises(ValidationError, match='letters, numbers, and underscores'):
            validate_username('user@123')


class TestRunTypeValidator:
    """Test run type validation."""
    
    def test_valid_run_types(self):
        """Test valid run types."""
        assert validate_run_type('easy') == 'easy'
        assert validate_run_type('tempo') == 'tempo'
        assert validate_run_type('long') == 'long'
        assert validate_run_type('interval') == 'interval'
        assert validate_run_type('race') == 'race'
    
    def test_invalid_run_type(self):
        """Test invalid run type."""
        with pytest.raises(ValidationError, match='Invalid run type'):
            validate_run_type('sprint')
    
    def test_empty_run_type(self):
        """Test empty run type defaults to easy."""
        assert validate_run_type('') == 'easy'
        assert validate_run_type(None) == 'easy'
