"""
Input validation utilities.
"""

import re
from datetime import datetime, date
import bleach


class ValidationError(Exception):
    """Custom validation error."""
    pass


def validate_pin(pin):
    """
    Validate PIN format.
    
    Args:
        pin: PIN string to validate
        
    Returns:
        str: Validated PIN
        
    Raises:
        ValidationError: If PIN is invalid
    """
    if not pin:
        raise ValidationError("PIN is required")
    
    pin = str(pin).strip()
    
    if not pin.isdigit():
        raise ValidationError("PIN must contain only digits")
    
    if len(pin) < 4:
        raise ValidationError("PIN must be at least 4 digits")
    
    if len(pin) > 8:
        raise ValidationError("PIN must be at most 8 digits")
    
    return pin


def validate_distance(distance):
    """
    Validate distance value.
    
    Args:
        distance: Distance in km (string or float)
        
    Returns:
        float: Validated distance
        
    Raises:
        ValidationError: If distance is invalid
    """
    try:
        distance = float(distance)
    except (ValueError, TypeError):
        raise ValidationError("Distance must be a valid number")
    
    if distance <= 0:
        raise ValidationError("Distance must be greater than 0 km")
    
    if distance > 500:  # Reasonable upper limit
        raise ValidationError("Distance seems unrealistic (max 500 km)")
    
    return distance


def validate_time(time_min):
    """
    Validate time/duration value.
    
    Args:
        time_min: Time in minutes (string or float)
        
    Returns:
        float: Validated time
        
    Raises:
        ValidationError: If time is invalid
    """
    try:
        time_min = float(time_min)
    except (ValueError, TypeError):
        raise ValidationError("Time must be a valid number")
    
    if time_min <= 0:
        raise ValidationError("Time must be greater than 0 minutes")
    
    if time_min > 1440:  # 24 hours
        raise ValidationError("Time seems unrealistic (max 24 hours)")
    
    return time_min


def validate_date(date_str):
    """
    Validate date string.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        date: Validated date object
        
    Raises:
        ValidationError: If date is invalid
    """
    if not date_str:
        raise ValidationError("Date is required")
    
    try:
        run_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("Invalid date format (use YYYY-MM-DD)")
    
    today = date.today()
    if run_date > today:
        raise ValidationError("Cannot log runs for future dates")
    
    # Reasonable past limit (10 years)
    if (today - run_date).days > 3650:
        raise ValidationError("Date is too far in the past (max 10 years)")
    
    return run_date


def validate_pace(distance, time_min):
    """
    Validate pace is realistic.
    
    Args:
        distance: Distance in km
        time_min: Time in minutes
        
    Returns:
        float: Calculated pace
        
    Raises:
        ValidationError: If pace is unrealistic
    """
    pace = time_min / distance
    
    if pace > 30:
        raise ValidationError("Pace too slow (> 30 min/km). Please check your distance and time.")
    
    if pace < 2:
        raise ValidationError("Pace too fast (< 2 min/km). Please check your distance and time.")
    
    return pace


def sanitize_notes(notes, max_length=500):
    """
    Sanitize run notes to prevent XSS.
    
    Args:
        notes: Raw notes string
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized notes
    """
    if not notes:
        return ""
    
    # Truncate to max length
    notes = str(notes)[:max_length]
    
    # Allow only safe tags and attributes
    allowed_tags = []  # No HTML tags allowed
    allowed_attributes = {}
    
    # Clean HTML
    clean_notes = bleach.clean(
        notes,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )
    
    return clean_notes.strip()


def validate_email(email):
    """
    Validate email format.
    
    Args:
        email: Email string
        
    Returns:
        str: Validated email
        
    Raises:
        ValidationError: If email is invalid
    """
    if not email:
        return None
    
    email = email.strip().lower()
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")
    
    if len(email) > 254:  # RFC 5321
        raise ValidationError("Email too long")
    
    return email


def validate_username(username):
    """
    Validate username format.
    
    Args:
        username: Username string
        
    Returns:
        str: Validated username
        
    Raises:
        ValidationError: If username is invalid
    """
    if not username:
        raise ValidationError("Username is required")
    
    username = username.strip()
    
    if len(username) < 3:
        raise ValidationError("Username must be at least 3 characters")
    
    if len(username) > 30:
        raise ValidationError("Username must be at most 30 characters")
    
    # Allow alphanumeric and underscore only
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise ValidationError("Username can only contain letters, numbers, and underscores")
    
    return username


def validate_run_type(run_type):
    """
    Validate run type.
    
    Args:
        run_type: Run type string
        
    Returns:
        str: Validated run type
        
    Raises:
        ValidationError: If run type is invalid
    """
    valid_types = {'easy', 'tempo', 'long', 'interval', 'race'}
    
    if not run_type:
        return 'easy'
    
    run_type = run_type.strip().lower()
    
    if run_type not in valid_types:
        raise ValidationError(f"Invalid run type. Must be one of: {', '.join(valid_types)}")
    
    return run_type
