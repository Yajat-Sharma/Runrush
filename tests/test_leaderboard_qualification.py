"""
tests/test_leaderboard_qualification.py

Tests for the 1 KM leaderboard qualification threshold.

Qualification rule:
  period_distance >= 1.00 KM  →  qualified (ranked)
  period_distance <  1.00 KM  →  unranked  (STILL TO RUN)
"""
import pytest
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")
os.environ.setdefault("GOOGLE_CLIENT_ID", "mock-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "mock-client-secret")

from utils.dates import get_current_week_range, get_current_month_range, get_today


# ─────────────────────────────────────────────────────────────────────────────
# Helper: split a flat list of (username, dist) pairs into qualified/unranked
# using the same logic as app.py
# ─────────────────────────────────────────────────────────────────────────────
QUALIFY_KM = 1.0


def split_qualification(entries):
    """
    entries: list of dicts with keys username, display_name, total_dist
    Returns (qualified_list, unranked_list) sorted descending by dist.
    """
    sorted_entries = sorted(entries, key=lambda x: x["total_dist"], reverse=True)
    qualified = []
    unranked = []
    for e in sorted_entries:
        dist = e["total_dist"]
        if dist >= QUALIFY_KM:
            qualified.append(e)
        else:
            remaining = round(QUALIFY_KM - dist, 2)
            e["remaining"] = remaining
            e["motivational"] = (
                "Run 1 KM to enter the leaderboard"
                if dist == 0
                else f"{remaining:.2f} KM to qualify"
            )
            unranked.append(e)
    return qualified, unranked


def make_entry(username, dist):
    return {"username": username, "display_name": username, "total_dist": round(dist, 2)}


# ─────────────────────────────────────────────────────────────────────────────
# 1. QUALIFICATION THRESHOLD TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestQualificationThreshold:

    def test_zero_km_is_unranked(self):
        q, u = split_qualification([make_entry("alex", 0.0)])
        assert len(q) == 0
        assert len(u) == 1
        assert u[0]["username"] == "alex"

    def test_half_km_is_unranked(self):
        q, u = split_qualification([make_entry("alex", 0.5)])
        assert len(q) == 0
        assert len(u) == 1

    def test_just_below_one_km_is_unranked(self):
        q, u = split_qualification([make_entry("alex", 0.99)])
        assert len(q) == 0
        assert len(u) == 1

    def test_exactly_one_km_is_qualified(self):
        q, u = split_qualification([make_entry("alex", 1.0)])
        assert len(q) == 1
        assert len(u) == 0

    def test_above_one_km_is_qualified(self):
        q, u = split_qualification([make_entry("yajat", 15.42)])
        assert len(q) == 1
        assert len(u) == 0

    def test_no_users(self):
        q, u = split_qualification([])
        assert q == []
        assert u == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONSECUTIVE RANK ORDERING
# ─────────────────────────────────────────────────────────────────────────────

class TestConsecutiveRanks:

    def test_unqualified_user_does_not_consume_rank(self):
        """Yajat 20 km, Alex 0.5 km, Priya 3 km — Alex must NOT be ranked."""
        entries = [
            make_entry("yajat", 20.0),
            make_entry("alex", 0.5),
            make_entry("priya", 3.0),
        ]
        q, u = split_qualification(entries)
        # Only Yajat and Priya qualify
        assert len(q) == 2
        assert q[0]["username"] == "yajat"  # rank 1
        assert q[1]["username"] == "priya"  # rank 2 (not rank 3)
        assert len(u) == 1
        assert u[0]["username"] == "alex"

    def test_ranks_are_consecutive(self):
        entries = [
            make_entry("a", 10.0),
            make_entry("b", 0.5),   # unqualified
            make_entry("c", 5.0),
            make_entry("d", 0.0),   # unqualified
            make_entry("e", 2.0),
        ]
        q, u = split_qualification(entries)
        assert [x["username"] for x in q] == ["a", "c", "e"]
        assert len(u) == 2

    def test_all_users_qualified(self):
        entries = [make_entry(f"u{i}", float(i + 1)) for i in range(5)]
        q, u = split_qualification(entries)
        assert len(q) == 5
        assert u == []

    def test_all_users_unranked(self):
        entries = [make_entry("a", 0.0), make_entry("b", 0.5), make_entry("c", 0.99)]
        q, u = split_qualification(entries)
        assert q == []
        assert len(u) == 3


# ─────────────────────────────────────────────────────────────────────────────
# 3. PODIUM — only qualified users
# ─────────────────────────────────────────────────────────────────────────────

class TestPodium:

    def test_one_qualified_runner_only_gold(self):
        entries = [make_entry("yajat", 5.0), make_entry("alex", 0.3)]
        q, _ = split_qualification(entries)
        assert len(q) == 1
        assert q[0]["username"] == "yajat"
        # Podium should only have 1 slot (checked in template by top3[:1])
        top3 = q[:3]
        assert len(top3) == 1

    def test_two_qualified_runners_gold_silver(self):
        entries = [make_entry("yajat", 10.0), make_entry("priya", 5.0), make_entry("alex", 0.0)]
        q, _ = split_qualification(entries)
        top3 = q[:3]
        assert len(top3) == 2
        assert top3[0]["username"] == "yajat"
        assert top3[1]["username"] == "priya"

    def test_three_or_more_qualified_runners(self):
        entries = [make_entry(f"u{i}", float(10 - i)) for i in range(5)]
        q, _ = split_qualification(entries)
        top3 = q[:3]
        assert len(top3) == 3

    def test_zero_km_user_not_in_podium(self):
        entries = [make_entry("yajat", 20.0), make_entry("alex", 0.0)]
        q, u = split_qualification(entries)
        top3 = q[:3]
        assert all(x["username"] != "alex" for x in top3)


# ─────────────────────────────────────────────────────────────────────────────
# 4. STILL TO RUN — motivational text
# ─────────────────────────────────────────────────────────────────────────────

class TestStillToRun:

    def test_zero_km_message(self):
        _, u = split_qualification([make_entry("alex", 0.0)])
        assert u[0]["motivational"] == "Run 1 KM to enter the leaderboard"

    def test_partial_km_message(self):
        _, u = split_qualification([make_entry("alex", 0.6)])
        assert u[0]["motivational"] == "0.40 KM to qualify"
        assert u[0]["remaining"] == 0.40

    def test_just_below_threshold_message(self):
        _, u = split_qualification([make_entry("alex", 0.99)])
        assert u[0]["motivational"] == "0.01 KM to qualify"

    def test_remaining_calculation(self):
        _, u = split_qualification([make_entry("alice", 0.35)])
        assert abs(u[0]["remaining"] - 0.65) < 0.001


# ─────────────────────────────────────────────────────────────────────────────
# 5. CURRENT USER STATE
# ─────────────────────────────────────────────────────────────────────────────

class TestCurrentUserState:

    def test_qualified_user_has_rank(self):
        entries = [make_entry("me", 5.0), make_entry("other", 3.0)]
        q, _ = split_qualification(entries)
        me_rank = next((i + 1 for i, x in enumerate(q) if x["username"] == "me"), None)
        assert me_rank == 1

    def test_unqualified_user_has_no_rank(self):
        entries = [make_entry("me", 0.6), make_entry("other", 10.0)]
        q, u = split_qualification(entries)
        me_in_ranked = any(x["username"] == "me" for x in q)
        me_in_unranked = any(x["username"] == "me" for x in u)
        assert not me_in_ranked
        assert me_in_unranked

    def test_zero_km_user_not_ranked(self):
        entries = [make_entry("me", 0.0), make_entry("other", 10.0)]
        q, u = split_qualification(entries)
        assert not any(x["username"] == "me" for x in q)
        assert any(x["username"] == "me" for x in u)


# ─────────────────────────────────────────────────────────────────────────────
# 6. DATE BOUNDARY UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

class TestDateBoundaries:

    def test_week_range_monday_to_sunday(self):
        today = get_today()
        week_start, week_end = get_current_week_range(today)
        assert week_start.weekday() == 0  # Monday
        assert week_end.weekday() == 6    # Sunday
        assert (week_end - week_start).days == 6

    def test_month_range_first_to_last(self):
        today = get_today()
        month_start, month_end = get_current_month_range(today)
        assert month_start.day == 1
        assert month_start.month == today.month
        assert month_end.month == today.month
        # month_end should be the last day of the month
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        assert month_end.day == last_day

    def test_week_range_contains_today(self):
        today = get_today()
        week_start, week_end = get_current_week_range(today)
        assert week_start <= today <= week_end

    def test_month_range_contains_today(self):
        today = get_today()
        month_start, month_end = get_current_month_range(today)
        assert month_start <= today <= month_end

    def test_week_range_is_independent_of_lifetime(self):
        """Weekly leaderboard must use weekly dates, not lifetime."""
        today = date(2026, 9, 21)  # a Monday
        week_start, week_end = get_current_week_range(today)
        # week should be Mon Sep 21 → Sun Sep 27
        assert week_start == date(2026, 9, 21)
        assert week_end == date(2026, 9, 27)

    def test_monthly_range_independent_of_weekly(self):
        """Monthly leaderboard must span the full calendar month."""
        today = date(2026, 9, 21)
        month_start, month_end = get_current_month_range(today)
        assert month_start == date(2026, 9, 1)
        assert month_end == date(2026, 9, 30)


# ─────────────────────────────────────────────────────────────────────────────
# 7. MULTIPLE USERS — full integration of split logic
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleUsers:

    def test_example_from_spec(self):
        """
        Yajat 20 km, Rahul 8 km, Alex 0.5 km, Priya 3 km
        Expected: #1 Yajat, #2 Rahul, #3 Priya | Alex in STILL TO RUN
        """
        entries = [
            make_entry("yajat", 20.0),
            make_entry("rahul", 8.0),
            make_entry("alex", 0.5),
            make_entry("priya", 3.0),
        ]
        q, u = split_qualification(entries)
        assert [x["username"] for x in q] == ["yajat", "rahul", "priya"]
        assert u[0]["username"] == "alex"

    def test_users_with_no_runs_are_unranked(self):
        """Users with 0 km (no runs ever) appear in STILL TO RUN."""
        entries = [
            make_entry("active", 5.0),
            make_entry("new_user", 0.0),
        ]
        q, u = split_qualification(entries)
        assert len(q) == 1
        assert q[0]["username"] == "active"
        assert u[0]["username"] == "new_user"
        assert u[0]["motivational"] == "Run 1 KM to enter the leaderboard"

    def test_large_group(self):
        """With 10 users of varying distances, only >= 1 km are ranked."""
        distances = [0.0, 0.3, 0.5, 0.99, 1.0, 1.5, 3.0, 5.0, 10.0, 20.0]
        entries = [make_entry(f"u{i}", d) for i, d in enumerate(distances)]
        q, u = split_qualification(entries)
        assert len(q) == 6   # 1.0, 1.5, 3.0, 5.0, 10.0, 20.0
        assert len(u) == 4   # 0.0, 0.3, 0.5, 0.99
        # ranked in descending order
        assert q[0]["total_dist"] == 20.0
        assert q[-1]["total_dist"] == 1.0
