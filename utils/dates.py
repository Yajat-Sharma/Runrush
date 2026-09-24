from datetime import datetime, timezone, timedelta
import calendar

def get_today():
    """Returns the current date in UTC."""
    return datetime.now(timezone.utc).date()

def get_current_day_range(today=None):
    """
    Returns (day_start, day_end) for the current day.
    If today is not provided, uses UTC now.
    """
    if today is None:
        today = get_today()
    return today, today

def get_current_week_range(today=None):
    """
    Returns (week_start, week_end) for the current week (Monday-Sunday).
    If today is not provided, uses UTC now.
    """
    if today is None:
        today = get_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end

def get_current_month_range(today=None):
    """
    Returns (month_start, month_end) for the current month.
    If today is not provided, uses UTC now.
    """
    if today is None:
        today = get_today()
    month_start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day)
    return month_start, month_end

def get_previous_month_range(today=None):
    """
    Returns (month_start, month_end) for the previous month.
    If today is not provided, uses UTC now.
    """
    if today is None:
        today = get_today()
    first_of_current = today.replace(day=1)
    last_of_prev = first_of_current - timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)
    return first_of_prev, last_of_prev

