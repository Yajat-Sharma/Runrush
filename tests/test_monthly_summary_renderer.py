"""
Tests for services/monthly_summary_renderer.py — HTML rendering only.
Summaries are constructed directly (no DB) to keep this test module
independent from monthly_summary_service / the database layer.
"""

from services.monthly_summary_service import (
    MonthlySummary,
    ComparisonValue,
    PersonalBestEntry,
    AchievementEntry,
    WeekBucket,
    GoalProgress,
)
from services.monthly_summary_renderer import render_subject, render_html


def _base_summary(**overrides):
    defaults = dict(
        user_id=1,
        year=2026,
        month=9,
        month_label="September 2026",
        has_activity=True,
        display_name="Yajat",
        email="yajat@example.com",
        total_distance_km=52.4,
        total_runs=14,
        total_time_min=295.0,
        avg_pace_min_per_km=5.63,
        longest_run_km=12.4,
        longest_run_date="2026-09-20",
        fastest_pace_min_per_km=5.07,
        fastest_pace_date="2026-09-12",
        total_calories=3600.0,
        most_active_day="Sunday",
        most_active_day_count=5,
        weekly_breakdown=[
            WeekBucket("Week 1", 1, 7, 12.4),
            WeekBucket("Week 2", 8, 14, 16.8),
            WeekBucket("Week 3", 15, 21, 9.7),
            WeekBucket("Week 4", 22, 28, 13.5),
        ],
        has_previous_month_data=True,
        comparison={
            "total_distance_km": ComparisonValue(52.4, 42.1, 10.3, 24.5, True),
            "total_runs": ComparisonValue(14, 12, 2, 16.7, True),
            "longest_run_km": ComparisonValue(12.4, 10.0, 2.4, 24.0, True),
        },
        personal_bests=[PersonalBestEntry("fastest_5k", 5.07, "min/km", "2026-09-12")],
        achievements=[AchievementEntry("TOTAL_50KM", "50KM Club", "\U0001f3c3", "2026-09-25 10:00:00")],
        current_streak=3,
        longest_streak_in_month=6,
        goal=GoalProgress(target_km=70.0, actual_km=52.4, percent=74.9, completed=False),
        summary_sentence="52.4 KM across 14 runs, with a new 5K personal best.",
    )
    defaults.update(overrides)
    return MonthlySummary(**defaults)


def _zero_activity_summary(**overrides):
    defaults = dict(
        user_id=1,
        year=2026,
        month=9,
        month_label="September 2026",
        has_activity=False,
        display_name="Yajat",
        email="yajat@example.com",
        summary_sentence="You didn't log a run in September 2026.",
    )
    defaults.update(overrides)
    return MonthlySummary(**defaults)


# --------------------------------------------------------------------------
# Subject line
# --------------------------------------------------------------------------

def test_subject_for_active_month_includes_name_and_month():
    summary = _base_summary()
    subject = render_subject(summary)
    assert "Yajat" in subject
    assert "September 2026" in subject


def test_subject_for_zero_activity_does_not_claim_stats():
    summary = _zero_activity_summary()
    subject = render_subject(summary)
    assert "September 2026" in subject
    assert "KM" not in subject


# --------------------------------------------------------------------------
# Escaping / XSS safety
# --------------------------------------------------------------------------

def test_display_name_is_html_escaped():
    summary = _base_summary(display_name="<script>alert(1)</script>")
    html_out = render_html(summary)
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_display_name_escaped_in_zero_activity_template_too():
    summary = _zero_activity_summary(display_name="<img src=x onerror=alert(1)>")
    html_out = render_html(summary)
    assert "<img src=x" not in html_out
    assert "&lt;img" in html_out


def test_achievement_name_is_escaped():
    summary = _base_summary(achievements=[
        AchievementEntry("X", "<b>Injected</b>", "\U0001f3c6", "2026-09-01")
    ])
    html_out = render_html(summary)
    assert "<b>Injected</b>" not in html_out


# --------------------------------------------------------------------------
# Zero-activity path
# --------------------------------------------------------------------------

def test_zero_activity_html_has_no_fabricated_numbers():
    summary = _zero_activity_summary()
    html_out = render_html(summary)
    assert "didn't log a run" in html_out
    # None of the stat labels used in the active template should appear
    assert "KM THIS MONTH" not in html_out
    assert "RUNS LOGGED" not in html_out
    assert "GOAL PROGRESS" not in html_out
    assert "ACHIEVEMENTS" not in html_out


def test_zero_activity_html_invites_next_month():
    summary = _zero_activity_summary(year=2026, month=9)
    html_out = render_html(summary)
    assert "October" in html_out


def test_zero_activity_december_rolls_into_next_year_january():
    summary = _zero_activity_summary(year=2026, month=12, month_label="December 2026")
    html_out = render_html(summary)
    assert "January" in html_out


# --------------------------------------------------------------------------
# Optional sections render only when data exists
# --------------------------------------------------------------------------

def test_renders_without_goal_section_when_no_goal():
    summary = _base_summary(goal=None)
    html_out = render_html(summary)
    assert "GOAL PROGRESS" not in html_out


def test_renders_goal_section_when_goal_present():
    summary = _base_summary()
    html_out = render_html(summary)
    assert "GOAL PROGRESS" in html_out
    assert "70" in html_out


def test_goal_complete_badge_shown_only_when_completed():
    incomplete = _base_summary(goal=GoalProgress(70.0, 52.4, 74.9, False))
    complete = _base_summary(goal=GoalProgress(50.0, 52.4, 104.8, True))
    assert "Monthly Goal Complete" not in render_html(incomplete)
    assert "Monthly Goal Complete" in render_html(complete)


def test_renders_without_achievements_section_when_none():
    summary = _base_summary(achievements=[])
    html_out = render_html(summary)
    assert "ACHIEVEMENTS" not in html_out


def test_renders_without_personal_bests_section_when_none():
    summary = _base_summary(personal_bests=[])
    html_out = render_html(summary)
    assert "PERSONAL BESTS" not in html_out


def test_first_month_message_when_no_previous_data():
    summary = _base_summary(has_previous_month_data=False, comparison={})
    html_out = render_html(summary)
    assert "first month" in html_out.lower()
    assert "VS LAST MONTH" not in html_out


def test_comparison_section_when_previous_data_exists():
    summary = _base_summary()
    html_out = render_html(summary)
    assert "VS LAST MONTH" in html_out
    assert "first month" not in html_out.lower()


def test_renders_without_streak_highlight_when_zero():
    summary = _base_summary(longest_streak_in_month=0)
    html_out = render_html(summary)
    assert "Best Streak" not in html_out


# --------------------------------------------------------------------------
# Template renders without crashing across sparse combinations
# --------------------------------------------------------------------------

def test_renders_with_all_optional_sections_absent():
    summary = _base_summary(
        goal=None,
        achievements=[],
        personal_bests=[],
        has_previous_month_data=False,
        comparison={},
        most_active_day=None,
        most_active_day_count=None,
        longest_streak_in_month=0,
        weekly_breakdown=[],
    )
    html_out = render_html(summary)
    assert "RunRush" in html_out
    assert "<html>" in html_out


def test_weekly_breakdown_bars_present_for_each_week():
    summary = _base_summary()
    html_out = render_html(summary)
    assert "Week 1" in html_out
    assert "Week 4" in html_out


def test_unsubscribe_and_preferences_link_present():
    html_out = render_html(_base_summary())
    assert "runrush.app/settings" in html_out
    assert "unsubscribe" in html_out.lower()
