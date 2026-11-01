"""Live calculations for a user's calendar-month running report."""

from calendar import monthrange
from datetime import date, timedelta
from math import isfinite

from db import get_db
from utils.dates import get_month_range

_MIN_BEST_RUN_DISTANCE_KM = 1.0


def _valid_run(row):
    try:
        distance = float(row["distance_km"])
        duration = float(row["time_min"])
        pace = float(row["pace"])
    except (TypeError, ValueError):
        return False
    return all(isfinite(value) and value > 0 for value in (distance, duration, pace))


def _runs_for_month(conn, user_id, year, month, through_date=None):
    start, end = get_month_range(year, month)
    if through_date and through_date.year == year and through_date.month == month:
        end = min(end, through_date)
    end_exclusive = end + timedelta(days=1)
    rows = conn.execute(
        """SELECT date, distance_km, time_min, pace
           FROM runs
           WHERE user_id = ? AND date >= ? AND date < ?
           ORDER BY date ASC""",
        (user_id, start.strftime("%Y-%m-%d"), end_exclusive.strftime("%Y-%m-%d")),
    ).fetchall()
    valid = []
    for row in rows:
        if not _valid_run(row):
            continue
        try:
            run_date = date.fromisoformat(str(row["date"])[:10])
        except ValueError:
            continue
        valid.append({
            "date": str(row["date"]),
            "day": run_date,
            "distance_km": float(row["distance_km"]),
            "time_min": float(row["time_min"]),
            "pace": float(row["pace"]),
        })
    return valid


def _previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _comparison(current, previous):
    if previous is None or previous == 0:
        return {"current": current, "previous": previous, "delta": None, "percentage": None}
    delta = current - previous
    return {
        "current": current,
        "previous": previous,
        "delta": round(delta, 2),
        "percentage": round(delta / previous * 100, 1),
    }


def _metrics(runs, year, month, through_date=None):
    total_distance = sum(run["distance_km"] for run in runs)
    total_time = sum(run["time_min"] for run in runs)
    best_candidates = [run for run in runs if run["distance_km"] >= _MIN_BEST_RUN_DISTANCE_KM]
    best = min(best_candidates, key=lambda run: (run["pace"], -run["distance_km"], run["day"])) if best_candidates else None
    days_with_runs = {run["day"] for run in runs}
    days_in_month = monthrange(year, month)[1]
    days_elapsed = min(days_in_month, through_date.day) if through_date and (through_date.year, through_date.month) == (year, month) else days_in_month
    return {
        "total_distance_km": round(total_distance, 2),
        "run_count": len(runs),
        "average_pace_min_per_km": round(total_time / total_distance, 2) if total_distance else None,
        "longest_run_km": round(max((run["distance_km"] for run in runs), default=0), 2),
        "consistency_percentage": round(len(days_with_runs) / days_elapsed * 100, 1) if days_elapsed else 0.0,
        "best_run": {
            "date": best["date"],
            "distance_km": round(best["distance_km"], 2),
            "time_min": round(best["time_min"], 2),
            "pace_min_per_km": round(best["pace"], 2),
        } if best else None,
    }


def build_monthly_report(user_id, year, month, *, as_of_date=None, is_live=False):
    """Recalculate a month from stored runs; no report snapshot is persisted."""
    if as_of_date and (as_of_date.year, as_of_date.month) != (year, month):
        as_of_date = None
    conn = get_db()
    try:
        current_runs = _runs_for_month(conn, user_id, year, month, as_of_date if is_live else None)
        previous_year, previous_month = _previous_month(year, month)
        previous_runs = _runs_for_month(conn, user_id, previous_year, previous_month)
    finally:
        conn.close()

    previous_has_activity = bool(previous_runs)
    current = _metrics(current_runs, year, month, as_of_date if is_live else None)
    previous = _metrics(previous_runs, previous_year, previous_month) if previous_has_activity else None
    comparisons = {}
    for key in ("total_distance_km", "run_count", "average_pace_min_per_km", "longest_run_km", "consistency_percentage"):
        comparisons[key] = _comparison(current[key], previous[key] if previous else None)

    month_end = get_month_range(year, month)[1]
    through = as_of_date if is_live and as_of_date else month_end
    return {
        "year": year,
        "month": month,
        "month_label": date(year, month, 1).strftime("%B %Y"),
        "metrics": current,
        "comparisons": comparisons,
        "has_activity": bool(current_runs),
        "is_live": bool(is_live),
        "data_through": through.isoformat(),
        "previous_month": {
            "year": previous_year,
            "month": previous_month,
            "has_data": previous_has_activity,
        },
    }
