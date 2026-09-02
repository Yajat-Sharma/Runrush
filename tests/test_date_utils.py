import pytest
from datetime import date
from utils.dates import get_current_week_range, get_current_month_range

def test_get_current_week_range_monday():
    # Test with a Monday
    monday = date(2026, 8, 31)
    start, end = get_current_week_range(monday)
    assert start == date(2026, 8, 31)
    assert end == date(2026, 9, 6)

def test_get_current_week_range_thursday():
    # Test with a Thursday
    thursday = date(2026, 9, 3)
    start, end = get_current_week_range(thursday)
    assert start == date(2026, 8, 31)
    assert end == date(2026, 9, 6)

def test_get_current_week_range_sunday():
    # Test with a Sunday
    sunday = date(2026, 9, 6)
    start, end = get_current_week_range(sunday)
    assert start == date(2026, 8, 31)
    assert end == date(2026, 9, 6)

def test_get_current_month_range():
    # Test middle of a month
    mid_month = date(2026, 8, 15)
    start, end = get_current_month_range(mid_month)
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)

    # Test leap year February
    leap_feb = date(2024, 2, 10)
    start, end = get_current_month_range(leap_feb)
    assert start == date(2024, 2, 1)
    assert end == date(2024, 2, 29)
