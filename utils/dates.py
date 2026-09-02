from datetime import datetime, timezone, timedelta
import calendar

def get_today():
    """Returns the current date in UTC."""
    return datetime.now(timezone.utc).date()

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
