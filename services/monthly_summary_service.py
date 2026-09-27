"""
Monthly summary service - calculation engine for the "Monthly Running Summary" feature.

Deliberately isolated from Flask routes, HTML rendering, and email transport:
this module only reads from the database and returns a structured MonthlySummary.
A later phase will add an HTML renderer that consumes MonthlySummary and an
email-sending layer that consumes the rendered HTML — neither exists yet.

Timezone / date semantics (see project audit notes):
- RunRush treats run dates as opaque strings, not timezone-aware datetimes
  (db.py forces Postgres TIMESTAMP columns back to strings; runs.date is
  entered by the user/device and is NOT guaranteed to be UTC).
- Existing month-scoped queries (api_monthly_progress in app.py) use plain
  lexicographic string range comparisons: date >= "YYYY-MM-DD" AND
  date <= "YYYY-MM-DD 23:59:59". This module follows that exact convention
  for consistency with the rest of the app, rather than introducing a new
  timezone assumption.
- Calendar month boundaries themselves (which year/month is "previous") are
  computed with utils.dates, whose get_today()/get_month_range() are UTC-based.
  This mirrors how send_weekly_summary() already mixes a UTC "today" with
  naive string-range run queries — an existing inconsistency, not a new one
  introduced here.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import calendar as _calendar

from db import get_db
from utils.dates import get_month_range

# Same >=1.0km floor used by app.py's get_personal_bests_for_user() for "best_pace",
# so a monthly "fastest pace" claim means the same thing as the all-time one shown
# elsewhere in the product. Not calling that function (kept isolated per scope),
# just matching its threshold for a consistent user-facing definition.
_MIN_DISTANCE_FOR_PACE_KM = 1.0
_5K_RANGE_KM = (4.5, 5.5)
_10K_RANGE_KM = (9.5, 10.5)

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class ComparisonValue:
    """One month-over-month metric comparison. `available` is False whenever
    a comparison would be meaningless (no previous-month data, or previous
    value is zero) — callers must check it before showing delta/pct_change."""
    current: float
    previous: Optional[float]
    delta: Optional[float]
    pct_change: Optional[float]
    available: bool


@dataclass
class PersonalBestEntry:
    metric: str          # "fastest_5k" | "fastest_10k" | "longest_run" | "fastest_pace"
    value: float
    unit: str             # "min/km" | "km"
    run_date: str


@dataclass
class AchievementEntry:
    badge_key: str
    name: str
    icon: str
    unlocked_at: str


@dataclass
class WeekBucket:
    label: str             # "Week 1"
    start_day: int
    end_day: int
    distance_km: float


@dataclass
class GoalProgress:
    target_km: float
    actual_km: float
    percent: float          # 0-100+, uncapped so overachievement is visible
    completed: bool


@dataclass
class MonthlySummary:
    user_id: int
    year: int
    month: int
    month_label: str        # "September 2026"
    has_activity: bool

    display_name: str
    email: Optional[str]

    # Core metrics — all None when has_activity is False
    total_distance_km: Optional[float] = None
    total_runs: Optional[int] = None
    total_time_min: Optional[float] = None
    avg_pace_min_per_km: Optional[float] = None
    longest_run_km: Optional[float] = None
    longest_run_date: Optional[str] = None
    fastest_pace_min_per_km: Optional[float] = None
    fastest_pace_date: Optional[str] = None
    total_calories: Optional[float] = None

    most_active_day: Optional[str] = None
    most_active_day_count: Optional[int] = None

    weekly_breakdown: List[WeekBucket] = field(default_factory=list)

    has_previous_month_data: bool = False
    comparison: Dict[str, ComparisonValue] = field(default_factory=dict)

    personal_bests: List[PersonalBestEntry] = field(default_factory=list)
    achievements: List[AchievementEntry] = field(default_factory=list)

    current_streak: Optional[int] = None
    longest_streak_in_month: Optional[int] = None

    goal: Optional[GoalProgress] = None

    summary_sentence: str = ""


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------

def _parse_run_date(date_str):
    """runs.date is sometimes 'YYYY-MM-DD' and sometimes 'YYYY-MM-DD HH:MM:SS'
    (see module docstring) — only the first 10 chars are ever meaningful for
    calendar-day purposes, and both forms share that prefix."""
    return datetime.strptime(date_str[:10], "%Y-%m-%d").date()


def _month_label(year, month):
    return f"{_calendar.month_name[month]} {year}"


def _previous_year_month(year, month):
    first_of_month = datetime(year, month, 1).date()
    last_of_prev = first_of_month - timedelta(days=1)
    return last_of_prev.year, last_of_prev.month


def _string_bounds_for_month(year, month):
    """Matches api_monthly_progress()'s existing convention exactly
    (app.py: start='YYYY-MM-DD', end='YYYY-MM-DD 23:59:59')."""
    month_start, month_end = get_month_range(year, month)
    start_str = month_start.strftime("%Y-%m-%d")
    end_str = f"{month_end.strftime('%Y-%m-%d')} 23:59:59"
    return start_str, end_str


def _fetch_runs_in_range(conn, user_id, start_str, end_str):
    rows = conn.execute(
        "SELECT date, distance_km, time_min, pace, calories FROM runs "
        "WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date ASC",
        (user_id, start_str, end_str),
    ).fetchall()
    return [dict(r) for r in rows]


def _comparison(current, previous):
    if previous is None or previous == 0:
        return ComparisonValue(current=current, previous=previous, delta=None,
                                pct_change=None, available=False)
    delta = current - previous
    pct_change = (delta / previous) * 100
    return ComparisonValue(current=current, previous=previous, delta=delta,
                            pct_change=pct_change, available=True)


def _weekly_breakdown(runs, year, month):
    """Buckets the month into fixed 7-day windows relative to day-of-month
    (days 1-7, 8-14, 15-21, 22-28, 29-end), NOT Mon-Sun calendar weeks.
    This is a deliberate, documented choice: calendar weeks straddle month
    boundaries and would require pulling in adjacent-month data or producing
    misleading partial first/last weeks, which the spec explicitly disallows.
    Day-of-month buckets are simple, always sum exactly to the month total,
    and need no data outside the month being summarized."""
    _, last_day = _calendar.monthrange(year, month)
    buckets = []
    day = 1
    week_num = 1
    while day <= last_day:
        end_day = min(day + 6, last_day)
        buckets.append(WeekBucket(label=f"Week {week_num}", start_day=day, end_day=end_day, distance_km=0.0))
        day = end_day + 1
        week_num += 1

    for r in runs:
        d = _parse_run_date(r["date"]).day
        for b in buckets:
            if b.start_day <= d <= b.end_day:
                b.distance_km += r["distance_km"] or 0.0
                break

    for b in buckets:
        b.distance_km = round(b.distance_km, 2)

    return buckets


def _most_active_day(runs):
    """Weekday (Mon-Sun) with the most runs. Ties are broken deterministically
    by earliest weekday index (Monday first) — documented per spec §13."""
    if not runs:
        return None, None
    counts = {}
    for r in runs:
        wd = _parse_run_date(r["date"]).weekday()
        counts[wd] = counts.get(wd, 0) + 1
    best_count = max(counts.values())
    best_wd = min(wd for wd, c in counts.items() if c == best_count)
    return _WEEKDAY_NAMES[best_wd], best_count


def _longest_streak_in_dates(dates_set):
    """Longest run of consecutive calendar days within the given date set.
    Independent from services/streak_service.py by design (that module
    computes all-time current/best streak from *all* of a user's runs;
    this is a month-scoped variant and is intentionally not merged with it,
    per explicit scope instructions for this feature)."""
    if not dates_set:
        return 0
    ordered = sorted(dates_set)
    longest = 1
    current = 1
    for i in range(1, len(ordered)):
        if ordered[i] == ordered[i - 1] + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _personal_bests_this_month(conn, user_id, month_start_str, month_end_str):
    """Returns PersonalBestEntry objects only for bests that are genuinely
    new this month, i.e. this month's best beats (or ties, for "achieved")
    every run strictly before month_start. A PB is never fabricated: if the
    user has no qualifying run this month for a given metric, or an equal-
    or-better run already exists before this month, nothing is returned for
    that metric."""
    results = []

    def _best_before(query_extra, params_extra, order_asc):
        order = "ASC" if order_asc else "DESC"
        row = conn.execute(
            f"SELECT distance_km, pace, date FROM runs WHERE user_id = ? AND date < ? {query_extra} "
            f"ORDER BY {'pace' if order_asc else 'distance_km'} {order} LIMIT 1",
            (user_id, month_start_str, *params_extra),
        ).fetchone()
        return dict(row) if row else None

    def _best_this_month(query_extra, params_extra, order_asc):
        order = "ASC" if order_asc else "DESC"
        row = conn.execute(
            f"SELECT distance_km, pace, date FROM runs WHERE user_id = ? AND date >= ? AND date <= ? {query_extra} "
            f"ORDER BY {'pace' if order_asc else 'distance_km'} {order} LIMIT 1",
            (user_id, month_start_str, month_end_str, *params_extra),
        ).fetchone()
        return dict(row) if row else None

    checks = [
        ("fastest_5k", "AND distance_km >= ? AND distance_km <= ?", _5K_RANGE_KM, True, "pace", "min/km"),
        ("fastest_10k", "AND distance_km >= ? AND distance_km <= ?", _10K_RANGE_KM, True, "pace", "min/km"),
        ("longest_run", "", (), False, "distance_km", "km"),
        ("fastest_pace", "AND distance_km >= ?", (_MIN_DISTANCE_FOR_PACE_KM,), True, "pace", "min/km"),
    ]

    for metric, extra_sql, extra_params, order_asc, value_field, unit in checks:
        this_month_best = _best_this_month(extra_sql, extra_params, order_asc)
        if not this_month_best:
            continue
        prior_best = _best_before(extra_sql, extra_params, order_asc)
        this_value = this_month_best[value_field]
        is_new = True
        if prior_best is not None:
            prior_value = prior_best[value_field]
            if order_asc:
                is_new = this_value < prior_value
            else:
                is_new = this_value > prior_value
        if is_new:
            results.append(PersonalBestEntry(
                metric=metric,
                value=this_value,
                unit=unit,
                run_date=this_month_best["date"],
            ))

    return results


def _achievements_this_month(conn, user_id, month_start_str, month_end_str):
    rows = conn.execute(
        """
        SELECT ub.unlocked_at, b.key as badge_key, b.name, b.icon_url
        FROM user_badges ub
        JOIN badges b ON ub.badge_id = b.id
        WHERE ub.user_id = ? AND ub.unlocked_at >= ? AND ub.unlocked_at <= ?
        ORDER BY ub.unlocked_at ASC
        """,
        (user_id, month_start_str, month_end_str),
    ).fetchall()
    return [
        AchievementEntry(
            badge_key=r["badge_key"],
            name=r["name"],
            icon=r["icon_url"] or "",
            unlocked_at=r["unlocked_at"],
        )
        for r in rows
    ]


def _build_summary_sentence(total_distance_km, total_runs, personal_bests):
    """Deterministic, data-derived one-liner. No LLM, no unverifiable
    superlatives ("strongest month ever") — only claims that follow
    directly from the numbers being reported."""
    base = f"{total_distance_km:.1f} KM across {total_runs} run{'s' if total_runs != 1 else ''}"
    if personal_bests:
        if len(personal_bests) == 1:
            pb = personal_bests[0]
            label = {
                "fastest_5k": "a new 5K personal best",
                "fastest_10k": "a new 10K personal best",
                "longest_run": "a new longest-run personal best",
                "fastest_pace": "a new fastest-pace personal best",
            }[pb.metric]
            return f"{base}, with {label}."
        return f"{base}, with {len(personal_bests)} new personal bests."
    return f"{base}."


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def build_monthly_summary(user_id, year, month):
    """
    Compute a MonthlySummary for the given user and explicit calendar
    year/month (the caller is expected to pass the *previous* calendar
    month when generating the automated end-of-month email — this function
    itself is deliberately agnostic to "current" vs "previous" so it can
    also be used for any historical month, e.g. from the dev preview CLI).

    Raises ValueError if the user does not exist.
    """
    conn = get_db()

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise ValueError(f"No such user: {user_id}")
    user = dict(user)

    month_start_str, month_end_str = _string_bounds_for_month(year, month)
    runs = _fetch_runs_in_range(conn, user_id, month_start_str, month_end_str)

    display_name = user.get("display_name") or user.get("username")
    email = user.get("email")

    summary = MonthlySummary(
        user_id=user_id,
        year=year,
        month=month,
        month_label=_month_label(year, month),
        has_activity=len(runs) > 0,
        display_name=display_name,
        email=email,
    )

    if not runs:
        # Zero-activity path: no fabricated stats, no comparisons, no PBs,
        # no achievements, no streak/goal claims derived from nonexistent data.
        conn.close()
        summary.summary_sentence = f"You didn't log a run in {_month_label(year, month)}."
        return summary

    total_distance_km = sum(r["distance_km"] or 0.0 for r in runs)
    total_runs = len(runs)
    total_time_min = sum(r["time_min"] or 0.0 for r in runs)
    avg_pace = (total_time_min / total_distance_km) if total_distance_km > 0 else None

    longest = max(runs, key=lambda r: r["distance_km"] or 0.0)
    pace_eligible = [r for r in runs if (r["distance_km"] or 0.0) >= _MIN_DISTANCE_FOR_PACE_KM and r["pace"]]
    fastest = min(pace_eligible, key=lambda r: r["pace"]) if pace_eligible else None

    calories_values = [r["calories"] for r in runs if r["calories"] is not None]
    total_calories = sum(calories_values) if calories_values else None

    most_active_day, most_active_day_count = _most_active_day(runs)
    weekly_breakdown = _weekly_breakdown(runs, year, month)

    summary.total_distance_km = round(total_distance_km, 2)
    summary.total_runs = total_runs
    summary.total_time_min = round(total_time_min, 2)
    summary.avg_pace_min_per_km = round(avg_pace, 2) if avg_pace is not None else None
    summary.longest_run_km = longest["distance_km"]
    summary.longest_run_date = longest["date"]
    if fastest:
        summary.fastest_pace_min_per_km = fastest["pace"]
        summary.fastest_pace_date = fastest["date"]
    summary.total_calories = round(total_calories, 1) if total_calories is not None else None
    summary.most_active_day = most_active_day
    summary.most_active_day_count = most_active_day_count
    summary.weekly_breakdown = weekly_breakdown

    # --- Previous month comparison ---
    prev_year, prev_month = _previous_year_month(year, month)
    prev_start_str, prev_end_str = _string_bounds_for_month(prev_year, prev_month)
    prev_runs = _fetch_runs_in_range(conn, user_id, prev_start_str, prev_end_str)

    summary.has_previous_month_data = len(prev_runs) > 0
    if prev_runs:
        prev_distance = sum(r["distance_km"] or 0.0 for r in prev_runs)
        prev_run_count = len(prev_runs)
        prev_time = sum(r["time_min"] or 0.0 for r in prev_runs)
        prev_avg_pace = (prev_time / prev_distance) if prev_distance > 0 else None
        prev_longest = max((r["distance_km"] or 0.0) for r in prev_runs)

        summary.comparison["total_distance_km"] = _comparison(summary.total_distance_km, round(prev_distance, 2))
        summary.comparison["total_runs"] = _comparison(summary.total_runs, prev_run_count)
        summary.comparison["total_time_min"] = _comparison(summary.total_time_min, round(prev_time, 2))
        if summary.avg_pace_min_per_km is not None and prev_avg_pace is not None:
            summary.comparison["avg_pace_min_per_km"] = _comparison(summary.avg_pace_min_per_km, round(prev_avg_pace, 2))
        summary.comparison["longest_run_km"] = _comparison(summary.longest_run_km, round(prev_longest, 2))
    # else: comparison stays empty and has_previous_month_data stays False —
    # callers must show "This is your first month with RunRush" (or "no prior
    # activity"), never a fabricated 0%/∞% delta.

    # --- Personal bests genuinely new this month ---
    summary.personal_bests = _personal_bests_this_month(conn, user_id, month_start_str, month_end_str)

    # --- Achievements unlocked this month ---
    summary.achievements = _achievements_this_month(conn, user_id, month_start_str, month_end_str)

    # --- Streak: current (all-time, as-of-now) + longest run of consecutive days within the month ---
    stats_row = conn.execute("SELECT current_streak FROM user_stats WHERE user_id = ?", (user_id,)).fetchone()
    summary.current_streak = stats_row["current_streak"] if stats_row else None
    run_dates = {_parse_run_date(r["date"]) for r in runs}
    summary.longest_streak_in_month = _longest_streak_in_dates(run_dates)

    # --- Monthly goal ---
    goal_row = conn.execute(
        "SELECT target_km FROM monthly_goals WHERE user_id = ? AND year = ? AND month = ?",
        (user_id, year, month),
    ).fetchone()
    if goal_row and goal_row["target_km"]:
        target_km = goal_row["target_km"]
        percent = (summary.total_distance_km / target_km) * 100 if target_km > 0 else 0
        summary.goal = GoalProgress(
            target_km=target_km,
            actual_km=summary.total_distance_km,
            percent=round(percent, 1),
            completed=summary.total_distance_km >= target_km,
        )

    conn.close()

    summary.summary_sentence = _build_summary_sentence(
        summary.total_distance_km, summary.total_runs, summary.personal_bests
    )

    return summary
