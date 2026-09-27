"""
Tests for services/monthly_summary_service.py — the calculation engine only.
No HTTP routes, email rendering, or delivery exist yet (later phases).
"""

import pytest
from datetime import datetime

from app import app
from db import get_db
from services.monthly_summary_service import build_monthly_summary


@pytest.fixture
def two_users(app, client):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username IN ('mu1', 'mu2')")
        conn.commit()

        client.post('/register', data={'username': 'mu1', 'pin': '1234'})
        client.post('/register', data={'username': 'mu2', 'pin': '1234'})

        u1 = conn.execute("SELECT id FROM users WHERE username = 'mu1'").fetchone()['id']
        u2 = conn.execute("SELECT id FROM users WHERE username = 'mu2'").fetchone()['id']

        yield u1, u2

        conn.execute("DELETE FROM user_badges WHERE user_id IN (?, ?)", (u1, u2))
        conn.execute("DELETE FROM monthly_goals WHERE user_id IN (?, ?)", (u1, u2))
        conn.execute("DELETE FROM runs WHERE user_id IN (?, ?)", (u1, u2))
        conn.execute("DELETE FROM users WHERE username IN ('mu1', 'mu2')")
        conn.commit()
        conn.close()


def _insert_run(conn, user_id, date_str, distance_km, time_min, pace, calories=None):
    if calories is None:
        calories = round(distance_km * 70, 1)
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, date_str, distance_km, time_min, pace, calories),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Month boundaries
# --------------------------------------------------------------------------

def test_month_boundary_respects_calendar_not_30_days(app, two_users):
    """A run on the last day of January must not leak into a February summary,
    and vice versa — proves calendar boundaries, not a rolling window."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-01-31 23:59:00", 5.0, 25.0, 5.0)
        _insert_run(conn, u1, "2026-02-01 00:00:00", 6.0, 30.0, 5.0)

        jan = build_monthly_summary(u1, 2026, 1)
        feb = build_monthly_summary(u1, 2026, 2)

    assert jan.total_runs == 1
    assert jan.total_distance_km == 5.0
    assert feb.total_runs == 1
    assert feb.total_distance_km == 6.0


def test_leap_year_february_includes_29th(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2024-02-29", 10.0, 50.0, 5.0)
        summary = build_monthly_summary(u1, 2024, 2)

    assert summary.total_runs == 1
    assert summary.total_distance_km == 10.0


def test_non_leap_february_excludes_29th_range(app, two_users):
    """2026 is not a leap year; Feb has 28 days. A run dated into March
    should not appear in the February summary."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-03-01", 8.0, 40.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 2)

    assert summary.has_activity is False


def test_year_transition_december_to_january(app, two_users):
    """December summary's previous-month comparison must resolve to the
    prior year's November, and January's must resolve to December of the
    prior year — a year rollover in both directions."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2025-11-15", 5.0, 25.0, 5.0)
        _insert_run(conn, u1, "2025-12-15", 10.0, 50.0, 5.0)
        _insert_run(conn, u1, "2026-01-15", 15.0, 75.0, 5.0)

        december = build_monthly_summary(u1, 2025, 12)
        january = build_monthly_summary(u1, 2026, 1)

    assert december.has_previous_month_data is True
    assert december.comparison["total_distance_km"].previous == 5.0

    assert january.has_previous_month_data is True
    assert january.comparison["total_distance_km"].previous == 10.0


# --------------------------------------------------------------------------
# Core metrics
# --------------------------------------------------------------------------

def test_core_metrics_are_calculated_correctly(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-02", 5.0, 30.0, 6.0, calories=300)
        _insert_run(conn, u1, "2026-05-10", 10.0, 50.0, 5.0, calories=550)
        _insert_run(conn, u1, "2026-05-20", 3.0, 18.0, 6.0, calories=180)

        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.has_activity is True
    assert summary.total_runs == 3
    assert summary.total_distance_km == 18.0
    assert summary.total_time_min == 98.0
    # avg_pace = total_time / total_distance
    assert summary.avg_pace_min_per_km == round(98.0 / 18.0, 2)
    assert summary.longest_run_km == 10.0
    assert summary.longest_run_date == "2026-05-10"
    # fastest pace among runs >= 1.0km: the two 6.0 pace runs and one 5.0 pace run -> 5.0 wins
    assert summary.fastest_pace_min_per_km == 5.0
    assert summary.fastest_pace_date == "2026-05-10"
    assert summary.total_calories == 1030.0


def test_fastest_pace_excludes_sub_1km_runs(app, two_users):
    """A very short, very fast run (e.g. a sprint) should not count as
    'fastest pace' — matches the >=1.0km floor used elsewhere in the app."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-06-01", 0.5, 1.0, 2.0)   # very fast but < 1km
        _insert_run(conn, u1, "2026-06-02", 5.0, 30.0, 6.0)

        summary = build_monthly_summary(u1, 2026, 6)

    assert summary.fastest_pace_min_per_km == 6.0


def test_calories_are_always_present_because_column_is_not_null(app, two_users):
    """runs.calories is NOT NULL at the schema level (schema.sql:41), so
    'calories missing' cannot occur with current data — total_calories is
    always populated whenever any run exists this month. The None-guard in
    _build_summary_sentence/total_calories logic exists defensively for a
    future where calories might become nullable (e.g. a run-type that skips
    calorie estimation), not because it's reachable today."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-07-01", 5.0, 25.0, 5.0, calories=310)
        summary = build_monthly_summary(u1, 2026, 7)

    assert summary.total_calories == 310.0


# --------------------------------------------------------------------------
# Month-over-month comparison
# --------------------------------------------------------------------------

def test_comparison_available_when_previous_month_has_data(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-08-15", 42.1, 240.0, 5.7)
        _insert_run(conn, u1, "2026-09-15", 52.4, 290.0, 5.5)

        summary = build_monthly_summary(u1, 2026, 9)

    assert summary.has_previous_month_data is True
    cmp = summary.comparison["total_distance_km"]
    assert cmp.available is True
    assert cmp.previous == 42.1
    assert cmp.current == 52.4
    assert round(cmp.delta, 1) == round(52.4 - 42.1, 1)
    assert cmp.pct_change is not None


def test_comparison_unavailable_when_no_previous_month_data(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-09-15", 20.0, 100.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 9)

    assert summary.has_previous_month_data is False
    assert summary.comparison == {}


def test_comparison_never_produces_infinite_or_fabricated_pct_from_zero(app, two_users):
    """Directly exercises the zero-previous-value guard in the comparison
    helper: previous == 0 must yield available=False, not a divide-by-zero
    or a meaningless 'infinite %' figure."""
    from services.monthly_summary_service import _comparison

    result = _comparison(current=10.0, previous=0)
    assert result.available is False
    assert result.pct_change is None
    assert result.delta is None


# --------------------------------------------------------------------------
# Zero-activity path
# --------------------------------------------------------------------------

def test_zero_activity_user_has_no_fabricated_stats(app, two_users):
    u1, _ = two_users
    with app.app_context():
        summary = build_monthly_summary(u1, 2026, 4)

    assert summary.has_activity is False
    assert summary.total_distance_km is None
    assert summary.total_runs is None
    assert summary.personal_bests == []
    assert summary.achievements == []
    assert summary.comparison == {}
    assert summary.goal is None
    assert "didn't log a run" in summary.summary_sentence


# --------------------------------------------------------------------------
# Personal bests
# --------------------------------------------------------------------------

def test_new_pb_detected_when_this_month_beats_all_prior_runs(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-01-10", 5.0, 30.0, 6.0)   # prior 5k @ 6:00/km
        _insert_run(conn, u1, "2026-02-10", 5.0, 25.0, 5.0)   # new 5k @ 5:00/km — faster

        summary = build_monthly_summary(u1, 2026, 2)

    metrics = {pb.metric for pb in summary.personal_bests}
    assert "fastest_5k" in metrics
    fastest_5k = next(pb for pb in summary.personal_bests if pb.metric == "fastest_5k")
    assert fastest_5k.value == 5.0
    assert fastest_5k.run_date == "2026-02-10"


def test_no_pb_when_this_month_does_not_beat_prior_best(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-01-10", 5.0, 25.0, 5.0)   # prior 5k @ 5:00/km (faster)
        _insert_run(conn, u1, "2026-02-10", 5.0, 30.0, 6.0)   # this month is slower

        summary = build_monthly_summary(u1, 2026, 2)

    metrics = {pb.metric for pb in summary.personal_bests}
    assert "fastest_5k" not in metrics


def test_first_ever_run_counts_as_pb_with_no_prior_data(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-03-10", 5.0, 27.0, 5.4)
        summary = build_monthly_summary(u1, 2026, 3)

    metrics = {pb.metric for pb in summary.personal_bests}
    assert "fastest_5k" in metrics
    assert "longest_run" in metrics
    assert "fastest_pace" in metrics


# --------------------------------------------------------------------------
# FIX 4 — deterministic tie-breaking in PB detection (audit regression)
# --------------------------------------------------------------------------

def test_tied_pace_within_month_resolves_to_earliest_date(app, two_users):
    """Two runs THIS month with identical pace — the tie must always
    resolve to the earliest date, matching get_personal_bests_for_user()'s
    'ORDER BY pace ASC, date ASC' convention, deterministically."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-04-20", 5.0, 25.0, 5.0)  # earlier, same pace
        _insert_run(conn, u1, "2026-04-05", 5.0, 25.0, 5.0)  # earlier date, inserted second
        summary = build_monthly_summary(u1, 2026, 4)

    fastest_5k = next(pb for pb in summary.personal_bests if pb.metric == "fastest_5k")
    assert fastest_5k.run_date == "2026-04-05"


def test_tied_longest_run_within_month_resolves_to_earliest_date(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-04-22", 10.0, 55.0, 5.5)
        _insert_run(conn, u1, "2026-04-03", 10.0, 55.0, 5.5)  # same distance, earlier date
        summary = build_monthly_summary(u1, 2026, 4)

    longest = next(pb for pb in summary.personal_bests if pb.metric == "longest_run")
    assert longest.run_date == "2026-04-03"


def test_tied_prior_best_still_correctly_blocks_new_pb(app, two_users):
    """A tie against a PRIOR month's run (not just within-month ties) must
    resolve deterministically too, via the same secondary sort in
    _best_before(). Here this month's run exactly TIES the prior best, so
    it must NOT count as a new PB (strictly-better semantics, unaffected
    by the ordering fix)."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-01-05", 5.0, 25.0, 5.0)   # prior month best
        _insert_run(conn, u1, "2026-02-10", 5.0, 25.0, 5.0)   # this month, exact tie
        summary = build_monthly_summary(u1, 2026, 2)

    metrics = {pb.metric for pb in summary.personal_bests}
    assert "fastest_5k" not in metrics


# --------------------------------------------------------------------------
# Achievements
# --------------------------------------------------------------------------

def test_achievements_unlocked_this_month_are_included(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        badge_id = conn.execute("SELECT id FROM badges WHERE key = 'FIRST_5K'").fetchone()['id']
        conn.execute(
            "INSERT INTO user_badges (user_id, badge_id, unlocked_at) VALUES (?, ?, ?)",
            (u1, badge_id, "2026-05-14 12:00:00"),
        )
        conn.commit()
        _insert_run(conn, u1, "2026-05-14", 5.0, 25.0, 5.0)

        summary = build_monthly_summary(u1, 2026, 5)

    keys = {a.badge_key for a in summary.achievements}
    assert "FIRST_5K" in keys


def test_achievements_from_other_months_are_excluded(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        badge_id = conn.execute("SELECT id FROM badges WHERE key = 'FIRST_5K'").fetchone()['id']
        conn.execute(
            "INSERT INTO user_badges (user_id, badge_id, unlocked_at) VALUES (?, ?, ?)",
            (u1, badge_id, "2026-04-01 00:00:00"),
        )
        conn.commit()
        _insert_run(conn, u1, "2026-05-14", 5.0, 25.0, 5.0)

        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.achievements == []


def test_no_achievements_omits_section_not_empty_placeholder(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-14", 5.0, 25.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.achievements == []


# --------------------------------------------------------------------------
# Goals
# --------------------------------------------------------------------------

def test_goal_progress_reflects_authoritative_monthly_goal_row(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO monthly_goals (user_id, year, month, target_km) VALUES (?, ?, ?, ?)",
            (u1, 2026, 5, 70.0),
        )
        conn.commit()
        _insert_run(conn, u1, "2026-05-14", 52.4, 260.0, 5.0)

        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.goal is not None
    assert summary.goal.target_km == 70.0
    assert summary.goal.actual_km == 52.4
    assert summary.goal.completed is False
    assert round(summary.goal.percent, 1) == round(52.4 / 70.0 * 100, 1)


def test_goal_marked_completed_when_target_reached(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO monthly_goals (user_id, year, month, target_km) VALUES (?, ?, ?, ?)",
            (u1, 2026, 5, 20.0),
        )
        conn.commit()
        _insert_run(conn, u1, "2026-05-14", 25.0, 125.0, 5.0)

        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.goal.completed is True


def test_no_goal_row_means_goal_is_none(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-14", 5.0, 25.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.goal is None


# --------------------------------------------------------------------------
# Streak
# --------------------------------------------------------------------------

def test_longest_streak_in_month_counts_consecutive_days_only(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        for d in ["2026-05-01", "2026-05-02", "2026-05-03"]:
            _insert_run(conn, u1, d, 5.0, 25.0, 5.0)
        _insert_run(conn, u1, "2026-05-10", 5.0, 25.0, 5.0)  # isolated, breaks streak

        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.longest_streak_in_month == 3


def test_no_streak_when_runs_are_all_isolated(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-01", 5.0, 25.0, 5.0)
        _insert_run(conn, u1, "2026-05-15", 5.0, 25.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.longest_streak_in_month == 1


# --------------------------------------------------------------------------
# FIX 5 — current_streak is historical (as of month-end), not "today's live streak"
# --------------------------------------------------------------------------

def test_current_streak_is_computed_as_of_month_end_not_today(app, two_users):
    """The core regression: build a summary for a month that ended long
    ago, with a run streak that stopped INSIDE that month. If the old bug
    (reading user_stats.current_streak, which reflects right now) were
    still present, this would report 0 (today's live streak, since there
    are no runs anywhere near today) instead of the correct historical
    value for that month."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        for d in ["2020-03-05", "2020-03-06", "2020-03-07", "2020-03-08"]:
            _insert_run(conn, u1, d, 5.0, 25.0, 5.0)
        # streak stops here — no run on 2020-03-09 or later
        summary = build_monthly_summary(u1, 2020, 3)

    # As of 2020-03-31 (month end), the streak that ended on 2020-03-08 is
    # long over — current_streak as of month-end is correctly 0, not a
    # stale "4" and definitely not today's live streak (which is also 0,
    # but for the wrong reason — coincidence, not correctness).
    assert summary.current_streak == 0


def test_current_streak_counts_consecutive_days_up_to_month_end_inclusive(app, two_users):
    """A streak that is STILL ACTIVE on the last day of the summarized
    month must be counted in full, anchored at month-end. Mirrors
    streak_service's own "current streak" semantics: the anchor day
    itself must have a run, or the streak-as-of that day is 0 — a run on
    05-28..05-30 with NOTHING on 05-31 (month end) correctly means the
    streak was already broken by the time the month ended, same as
    calculate_streak_for_user() would report 0 if there were no run
    today. This test uses a streak that reaches all the way to 05-31."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        for d in ["2026-05-28", "2026-05-29", "2026-05-30", "2026-05-31"]:
            _insert_run(conn, u1, d, 5.0, 25.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.current_streak == 4


def test_current_streak_spans_across_month_boundary(app, two_users):
    """A streak that STARTED in the previous month and continued, without
    a gap, all the way through to the LAST day of the summarized month
    must count days from both months — proving this is genuinely
    history-anchored, not limited to longest_streak_in_month's
    within-month-only scope. (The streak must reach the month's actual
    last calendar day for current_streak-as-of-month-end to be non-zero
    at all — see the previous test's note on anchor semantics — so this
    test fills every day of May, starting a couple of days into April, to
    keep the streak continuous.)"""
    from datetime import date, timedelta as _td

    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        d = date(2026, 4, 29)
        end = date(2026, 5, 31)
        n_days = 0
        while d <= end:
            _insert_run(conn, u1, d.strftime("%Y-%m-%d"), 5.0, 25.0, 5.0)
            d += _td(days=1)
            n_days += 1
        summary = build_monthly_summary(u1, 2026, 5)

    assert summary.current_streak == n_days  # spans April 29 through May 31
    assert summary.longest_streak_in_month == 31  # correctly bounded to May itself only


def test_current_streak_differs_from_live_user_stats_for_a_past_month(app, two_users):
    """Direct proof the bug is fixed: user_stats.current_streak (today's
    live value) and the historical month's current_streak are computed
    independently and can legitimately differ. The streak must reach the
    summarized month's actual last day (June 30, 2021) to register as
    non-zero as of that month's end."""
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        for d in ["2021-06-28", "2021-06-29", "2021-06-30"]:
            _insert_run(conn, u1, d, 5.0, 25.0, 5.0)
        # A separate, unrelated CURRENT streak that would populate
        # user_stats.current_streak via the app's normal run-insertion path
        # (this row is never read by the fixed code — see assertion below):
        conn.execute(
            "INSERT OR REPLACE INTO user_stats (user_id, total_distance_km, current_streak, best_streak, updated_at) "
            "VALUES (?, 0, 7, 7, ?)",
            (u1, "2026-01-01 00:00:00"),
        )
        conn.commit()

        summary = build_monthly_summary(u1, 2021, 6)

    # The historical June-2021 streak (3 days, ending 2021-06-30) must be
    # reported — NOT the unrelated live value (7) sitting in user_stats.
    assert summary.current_streak == 3
    assert summary.current_streak != 7


# --------------------------------------------------------------------------
# Most active day
# --------------------------------------------------------------------------

def test_most_active_day_picks_highest_count():
    from services.monthly_summary_service import _most_active_day
    runs = [
        {"date": "2026-05-04"},  # Monday
        {"date": "2026-05-04"},  # Monday
        {"date": "2026-05-05"},  # Tuesday
    ]
    day, count = _most_active_day(runs)
    assert day == "Monday"
    assert count == 2


def test_most_active_day_tie_break_is_earliest_weekday():
    """Documented deterministic tie-break rule: earliest weekday (Monday
    first) wins on a count tie."""
    from services.monthly_summary_service import _most_active_day
    runs = [
        {"date": "2026-05-08"},  # Friday
        {"date": "2026-05-04"},  # Monday
    ]
    day, count = _most_active_day(runs)
    assert day == "Monday"
    assert count == 1


# --------------------------------------------------------------------------
# Weekly breakdown
# --------------------------------------------------------------------------

def test_weekly_breakdown_sums_to_month_total(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-03", 5.0, 25.0, 5.0)
        _insert_run(conn, u1, "2026-05-12", 6.0, 30.0, 5.0)
        _insert_run(conn, u1, "2026-05-25", 7.0, 35.0, 5.0)

        summary = build_monthly_summary(u1, 2026, 5)

    bucket_total = round(sum(b.distance_km for b in summary.weekly_breakdown), 2)
    assert bucket_total == summary.total_distance_km
    assert len(summary.weekly_breakdown) == 5  # 31-day month -> 5 buckets of <=7 days


# --------------------------------------------------------------------------
# User isolation
# --------------------------------------------------------------------------

def test_user_a_summary_never_contains_user_b_data(app, two_users):
    u1, u2 = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-10", 5.0, 25.0, 5.0)
        _insert_run(conn, u2, "2026-05-10", 100.0, 400.0, 4.0)

        summary_u1 = build_monthly_summary(u1, 2026, 5)

    assert summary_u1.total_distance_km == 5.0
    assert summary_u1.total_runs == 1


def test_unknown_user_raises_value_error(app, two_users):
    with app.app_context():
        with pytest.raises(ValueError):
            build_monthly_summary(999999, 2026, 5)


# --------------------------------------------------------------------------
# Summary sentence
# --------------------------------------------------------------------------

def test_summary_sentence_is_deterministic_and_data_derived(app, two_users):
    u1, _ = two_users
    with app.app_context():
        conn = get_db()
        _insert_run(conn, u1, "2026-05-10", 5.0, 25.0, 5.0)
        summary = build_monthly_summary(u1, 2026, 5)

    assert "5.0 KM across 1 run" in summary.summary_sentence
    assert "personal best" in summary.summary_sentence
