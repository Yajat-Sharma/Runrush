"""
Rumi AI Service - Personal Running Companion for RunRush.

Separates questions into:
1. Deterministic database-backed factual questions (answered 100% deterministically from DB).
2. Hybrid questions (uses verified database metrics as strict context for AI coaching).
3. Conversational questions (running terminology, training advice, motivation).

Gemini is never called for simple factual questions and never invents or calculates personal statistics.
"""

import os
import re
import calendar
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from db import get_db
from utils.dates import (
    get_today,
    get_current_week_range,
    get_current_month_range,
    get_previous_month_range,
    get_month_range,
)
from services.monthly_report_service import build_monthly_report

# Sensible threshold for pace-related queries
_MIN_DISTANCE_FOR_PACE_KM = 1.0
_MAX_MESSAGE_LENGTH = 500
_MAX_HISTORY_TURNS = 10  # 5 user + 5 assistant turns


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def _format_duration_min(minutes: float) -> str:
    """Format duration in minutes to human-readable string (e.g. '1h 24m' or '45m')."""
    if not minutes or minutes <= 0:
        return "0m"
    total_seconds = int(round(minutes * 60))
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    if mins > 0:
        return f"{mins}m {secs}s" if secs > 0 else f"{mins}m"
    return f"{secs}s"


def _format_pace(pace_min_km: Optional[float]) -> str:
    """Format pace (min/km) to standard 'M:SS /km' string."""
    if pace_min_km is None or pace_min_km <= 0:
        return "N/A"
    minutes = int(pace_min_km)
    seconds = int(round((pace_min_km - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d} /km"


# ---------------------------------------------------------------------------
# Deterministic Backend Data Functions (Scoped strictly to user_id)
# ---------------------------------------------------------------------------

def get_lifetime_stats(user_id: int) -> Dict[str, Any]:
    """Retrieve all-time distance, duration, runs count, and average pace."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT distance_km, time_min FROM runs WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        total_runs = len(rows)
        total_distance = round(sum(r["distance_km"] for r in rows), 2) if rows else 0.0
        total_duration = round(sum(r["time_min"] for r in rows), 2) if rows else 0.0
        avg_pace = round(total_duration / total_distance, 2) if total_distance > 0 else None
        return {
            "total_runs": total_runs,
            "total_distance_km": total_distance,
            "total_duration_min": total_duration,
            "total_duration_formatted": _format_duration_min(total_duration),
            "avg_pace": avg_pace,
            "avg_pace_formatted": _format_pace(avg_pace),
        }
    finally:
        conn.close()


def get_longest_run(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve the user's longest run to date."""
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, date, distance_km, time_min, pace, calories, run_type
            FROM runs
            WHERE user_id = ?
            ORDER BY distance_km DESC, date ASC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "distance_km": round(row["distance_km"], 2),
            "time_min": round(row["time_min"], 2),
            "time_formatted": _format_duration_min(row["time_min"]),
            "pace": round(row["pace"], 2),
            "pace_formatted": _format_pace(row["pace"]),
            "date": str(row["date"])[:10],
            "run_type": row["run_type"] or "easy",
        }
    finally:
        conn.close()


def get_fastest_run(user_id: int, min_distance_km: float = _MIN_DISTANCE_FOR_PACE_KM) -> Optional[Dict[str, Any]]:
    """Retrieve fastest run with sensible minimum distance applied."""
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, date, distance_km, time_min, pace, calories, run_type
            FROM runs
            WHERE user_id = ? AND distance_km >= ?
            ORDER BY pace ASC, date ASC
            LIMIT 1
            """,
            (user_id, min_distance_km)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "distance_km": round(row["distance_km"], 2),
            "time_min": round(row["time_min"], 2),
            "time_formatted": _format_duration_min(row["time_min"]),
            "pace": round(row["pace"], 2),
            "pace_formatted": _format_pace(row["pace"]),
            "date": str(row["date"])[:10],
            "run_type": row["run_type"] or "easy",
        }
    finally:
        conn.close()


def get_fastest_5k(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve fastest run in the 5K distance window (4.5 to 5.5 km)."""
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, date, distance_km, time_min, pace, calories
            FROM runs
            WHERE user_id = ? AND distance_km >= 4.5 AND distance_km <= 5.5
            ORDER BY pace ASC, date ASC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "distance_km": round(row["distance_km"], 2),
            "time_min": round(row["time_min"], 2),
            "duration_min": round(row["time_min"], 2),
            "time_formatted": _format_duration_min(row["time_min"]),
            "pace": round(row["pace"], 2),
            "pace_formatted": _format_pace(row["pace"]),
            "date": str(row["date"])[:10],
        }
    finally:
        conn.close()


def get_fastest_10k(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve fastest run in the 10K distance window (9.0 to 11.0 km)."""
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, date, distance_km, time_min, pace, calories
            FROM runs
            WHERE user_id = ? AND distance_km >= 9.0 AND distance_km <= 11.0
            ORDER BY pace ASC, date ASC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "distance_km": round(row["distance_km"], 2),
            "time_min": round(row["time_min"], 2),
            "duration_min": round(row["time_min"], 2),
            "time_formatted": _format_duration_min(row["time_min"]),
            "pace": round(row["pace"], 2),
            "pace_formatted": _format_pace(row["pace"]),
            "date": str(row["date"])[:10],
        }
    finally:
        conn.close()


def get_personal_records(user_id: int) -> Dict[str, Any]:
    """Retrieve structured dictionary of user personal records."""
    return {
        "longest_run": get_longest_run(user_id),
        "best_pace": get_fastest_run(user_id, min_distance_km=_MIN_DISTANCE_FOR_PACE_KM),
        "fastest_5k": get_fastest_5k(user_id),
        "fastest_10k": get_fastest_10k(user_id),
    }


def get_period_stats(
    user_id: int,
    period: str = "this_month",
    today: Optional[date] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve deterministic stats for a specific period:
    period: 'this_month', 'last_month', 'this_week', 'last_week', 'lifetime' or 'specific_month'
    """
    if today is None:
        today = get_today()

    if period == "lifetime":
        lt = get_lifetime_stats(user_id)
        return {
            "period": "lifetime",
            "label": "All Time",
            "distance_km": lt["total_distance_km"],
            "run_count": lt["total_runs"],
            "duration_min": lt["total_duration_min"],
            "duration_formatted": lt["total_duration_formatted"],
            "avg_pace": lt["avg_pace"],
            "avg_pace_formatted": lt["avg_pace_formatted"],
        }

    if period in ("this_month", "current_month"):
        y = today.year
        m = today.month
        rep = build_monthly_report(user_id, y, m, as_of_date=today, is_live=True)
        met = rep["metrics"]
        dur = round(sum(r["time_min"] for r in met.get("runs", [])) if "runs" in met else (met["total_distance_km"] * (met["average_pace_min_per_km"] or 0)), 2)
        return {
            "period": "this_month",
            "year": y,
            "month": m,
            "label": rep["month_label"],
            "distance_km": met["total_distance_km"],
            "run_count": met["run_count"],
            "avg_pace": met["average_pace_min_per_km"],
            "avg_pace_formatted": _format_pace(met["average_pace_min_per_km"]),
            "longest_run_km": met["longest_run_km"],
            "consistency_percentage": met["consistency_percentage"],
        }

    if period in ("last_month", "previous_month"):
        prev_d = (today.replace(day=1) - timedelta(days=1))
        y = prev_d.year
        m = prev_d.month
        rep = build_monthly_report(user_id, y, m, is_live=False)
        met = rep["metrics"]
        return {
            "period": "last_month",
            "year": y,
            "month": m,
            "label": rep["month_label"],
            "distance_km": met["total_distance_km"],
            "run_count": met["run_count"],
            "avg_pace": met["average_pace_min_per_km"],
            "avg_pace_formatted": _format_pace(met["average_pace_min_per_km"]),
            "longest_run_km": met["longest_run_km"],
            "consistency_percentage": met["consistency_percentage"],
        }

    if period == "specific_month" and year and month:
        rep = build_monthly_report(user_id, year, month, is_live=(year == today.year and month == today.month))
        met = rep["metrics"]
        return {
            "period": "specific_month",
            "year": year,
            "month": month,
            "label": rep["month_label"],
            "distance_km": met["total_distance_km"],
            "run_count": met["run_count"],
            "avg_pace": met["average_pace_min_per_km"],
            "avg_pace_formatted": _format_pace(met["average_pace_min_per_km"]),
            "longest_run_km": met["longest_run_km"],
            "consistency_percentage": met["consistency_percentage"],
        }

    if period in ("this_week", "current_week"):
        start_d, end_d = get_current_week_range(today)
        label = f"{start_d.strftime('%b %d')} - {end_d.strftime('%b %d, %Y')}"
    elif period in ("last_week", "previous_week"):
        curr_start, _ = get_current_week_range(today)
        start_d = curr_start - timedelta(days=7)
        end_d = curr_start - timedelta(days=1)
        label = f"{start_d.strftime('%b %d')} - {end_d.strftime('%b %d, %Y')}"
    else:
        start_d, end_d = get_current_week_range(today)
        label = "This Week"

    conn = get_db()
    try:
        start_str = start_d.strftime("%Y-%m-%d")
        end_str = end_d.strftime("%Y-%m-%d 23:59:59")
        rows = conn.execute(
            """
            SELECT distance_km, time_min, pace
            FROM runs
            WHERE user_id = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (user_id, start_str, end_str)
        ).fetchall()
        run_count = len(rows)
        dist = round(sum(r["distance_km"] for r in rows), 2) if rows else 0.0
        dur = round(sum(r["time_min"] for r in rows), 2) if rows else 0.0
        pace = round(dur / dist, 2) if dist > 0 else None
        longest = round(max((r["distance_km"] for r in rows), default=0.0), 2)
        return {
            "period": period,
            "label": label,
            "start": start_str,
            "end": end_str[:10],
            "distance_km": dist,
            "duration_min": dur,
            "duration_formatted": _format_duration_min(dur),
            "run_count": run_count,
            "avg_pace": pace,
            "avg_pace_formatted": _format_pace(pace),
            "longest_run_km": longest,
        }
    finally:
        conn.close()


def get_weekly_goal_progress(user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Retrieve weekly goal progress, remaining distance, and completion percentage."""
    if today is None:
        today = get_today()

    conn = get_db()
    try:
        wg_row = conn.execute(
            "SELECT goal_km FROM user_weekly_goals WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        goal_km = float(wg_row["goal_km"]) if wg_row and wg_row["goal_km"] is not None else None

        week_stats = get_period_stats(user_id, "this_week", today=today)
        current_km = week_stats["distance_km"]

        if goal_km and goal_km > 0:
            remaining_km = max(round(goal_km - current_km, 2), 0.0)
            progress_pct = round(min(100.0 * current_km / goal_km, 100.0), 1)
            achieved = current_km >= goal_km
        else:
            remaining_km = None
            progress_pct = 0.0
            achieved = False

        return {
            "weekly_goal_km": goal_km,
            "weekly_current_km": current_km,
            "weekly_remaining_km": remaining_km,
            "weekly_progress_pct": progress_pct,
            "weekly_achieved": achieved,
            "has_goal": goal_km is not None and goal_km > 0,
        }
    finally:
        conn.close()


def get_period_comparison(
    user_id: int,
    comparison_type: str = "month_over_month",
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Retrieve period comparisons (month-over-month or week-over-week)."""
    if today is None:
        today = get_today()

    if comparison_type == "month_over_month":
        curr = get_period_stats(user_id, "this_month", today=today)
        prev = get_period_stats(user_id, "last_month", today=today)
        prev_has_data = prev["run_count"] > 0
        delta_km = round(curr["distance_km"] - prev["distance_km"], 2)
        pct_change = round(delta_km / prev["distance_km"] * 100.0, 1) if (prev_has_data and prev["distance_km"] > 0) else None
        pace_delta = round(curr["avg_pace"] - prev["avg_pace"], 2) if (curr["avg_pace"] and prev["avg_pace"]) else None
        return {
            "type": "month_over_month",
            "current": curr,
            "previous": prev,
            "previous_has_data": prev_has_data,
            "distance_delta_km": delta_km,
            "distance_pct_change": pct_change,
            "pace_delta": pace_delta,
            "runs_delta": curr["run_count"] - prev["run_count"],
        }
    else:  # week_over_week
        curr = get_period_stats(user_id, "this_week", today=today)
        prev = get_period_stats(user_id, "last_week", today=today)
        prev_has_data = prev["run_count"] > 0
        delta_km = round(curr["distance_km"] - prev["distance_km"], 2)
        pct_change = round(delta_km / prev["distance_km"] * 100.0, 1) if (prev_has_data and prev["distance_km"] > 0) else None
        pace_delta = round(curr["avg_pace"] - prev["avg_pace"], 2) if (curr["avg_pace"] and prev["avg_pace"]) else None
        return {
            "type": "week_over_week",
            "current": curr,
            "previous": prev,
            "previous_has_data": prev_has_data,
            "distance_delta_km": delta_km,
            "distance_pct_change": pct_change,
            "pace_delta": pace_delta,
            "runs_delta": curr["run_count"] - prev["run_count"],
        }


def get_consistency_stats(user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Retrieve running consistency stats for the current month."""
    if today is None:
        today = get_today()
    curr_month = get_period_stats(user_id, "this_month", today=today)
    return {
        "month_label": curr_month["label"],
        "consistency_percentage": curr_month.get("consistency_percentage", 0.0),
        "total_runs": curr_month["run_count"],
        "total_distance_km": curr_month["distance_km"],
    }


def get_user_rumi_context(user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """
    Safely retrieve structured running context for an authenticated user.
    Used for hybrid queries and system prompt generation.
    """
    if today is None:
        today = get_today()

    conn = get_db()
    try:
        user_row = conn.execute(
            "SELECT id, username, display_name FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        display_name = "Runner"
        if user_row:
            display_name = user_row["display_name"] or user_row["username"] or "Runner"

        recent_rows = conn.execute(
            """
            SELECT date, distance_km, time_min, pace, run_type, notes
            FROM runs
            WHERE user_id = ?
            ORDER BY date DESC, id DESC
            LIMIT 5
            """,
            (user_id,)
        ).fetchall()
        recent_runs = []
        for r in recent_rows:
            recent_runs.append({
                "date": str(r["date"])[:10],
                "distance_km": round(r["distance_km"], 2),
                "duration_min": round(r["time_min"], 2),
                "pace_formatted": _format_pace(r["pace"]),
                "run_type": r["run_type"] or "easy",
                "notes": r["notes"][:60] if r["notes"] else "",
            })
    finally:
        conn.close()

    lt = get_lifetime_stats(user_id)
    pb = get_personal_records(user_id)
    cm = get_period_stats(user_id, "this_month", today=today)
    pm = get_period_stats(user_id, "last_month", today=today)
    mom = get_period_comparison(user_id, "month_over_month", today=today)
    cw = get_period_stats(user_id, "this_week", today=today)
    pw = get_period_stats(user_id, "last_week", today=today)
    wow = get_period_comparison(user_id, "week_over_week", today=today)
    goals = get_weekly_goal_progress(user_id, today=today)

    return {
        "user_id": user_id,
        "display_name": display_name,
        "as_of_date": today.strftime("%Y-%m-%d"),
        "lifetime": lt,
        "personal_bests": pb,
        "current_month": cm,
        "previous_month": pm,
        "month_over_month": {
            "distance_delta_km": mom["distance_delta_km"],
            "distance_pct_change": mom["distance_pct_change"],
            "pace_delta": mom["pace_delta"],
            "runs_delta": mom["runs_delta"],
            "previous_has_data": mom["previous_has_data"],
        },
        "current_week": cw,
        "previous_week": pw,
        "week_over_week": {
            "distance_delta_km": wow["distance_delta_km"],
            "runs_delta": wow["runs_delta"],
            "previous_has_data": wow["previous_has_data"],
        },
        "goals": goals,
        "recent_runs": recent_runs,
    }


# ---------------------------------------------------------------------------
# Intent Classification (Factual vs Hybrid vs Conversational)
# ---------------------------------------------------------------------------

class IntentType:
    FACTUAL = "factual"
    HYBRID = "hybrid"
    CONVERSATIONAL = "conversational"


def classify_rumi_intent(message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Classify a user message into FACTUAL, HYBRID, or CONVERSATIONAL.
    Returns (intent_type, payload_metadata).
    """
    msg = message.strip().lower()

    # 0. Check for conceptual explanations and definitions (strictly conversational)
    if re.search(r"\b(?:difference between|what does .*? mean|explain|definition of|meaning of)\b", msg):
        return IntentType.CONVERSATIONAL, {"topic": "explanation"}

    # 1. Check for HYBRID questions first (questions needing athletic advice tailored to personal stats)
    hybrid_patterns = [
        r"\bam i improving\b",
        r"\bhow can i improve my (?:5k|10k|pace|running|speed|distance|endurance)\b",
        r"\bhow to improve my (?:5k|10k|pace|running|speed|distance|endurance)\b",
        r"\b(?:create|give me|make|build) (?:a |an )?(?:simple |weekly |training )?plan\b",
        r"\bplan based on my (?:recent )?(?:performance|runs|data)\b",
        r"\bwhat should i run (?:next|this) week\b",
        r"\bhelp me run a faster 5k\b",
        r"\bhow do i get faster\b",
    ]
    for pat in hybrid_patterns:
        if re.search(pat, msg):
            return IntentType.HYBRID, {"topic": "improvement_or_plan"}

    # 2. Check for FACTUAL questions (pure database queries)

    # A. Monthly distance
    if re.search(r"\b(?:how many|how much|what) (?:km|kilometres|kilometers|distance) .*?(?:last month|previous month)\b", msg) or \
       re.search(r"\b(?:distance|km|kilometres) (?:run |logged )?(?:in |last )month\b", msg) or \
       re.search(r"\blast month(?:'s)? (?:distance|km|runs?)\b", msg) or \
       re.search(r"\bhow far did i run last month\b", msg):
        return IntentType.FACTUAL, {"type": "monthly_distance", "period": "last_month"}

    if re.search(r"\b(?:how many|how much|what) (?:km|kilometres|kilometers|distance) .*?(?:this month|current month)\b", msg) or \
       re.search(r"\b(?:distance|km|kilometres) (?:run |logged )?(?:this|current) month\b", msg) or \
       re.search(r"\bhow far did i run this month\b", msg):
        return IntentType.FACTUAL, {"type": "monthly_distance", "period": "this_month"}

    # Specific month lookup (e.g., "in October", "in September")
    month_names = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
    for m_name, m_num in month_names.items():
        if re.search(rf"\b(?:how far|distance|km|kilometres|runs?).*?\bin {m_name}\b", msg):
            return IntentType.FACTUAL, {"type": "specific_month_distance", "month_num": m_num, "month_name": m_name.capitalize()}

    # B. Weekly distance
    if re.search(r"\b(?:how many|how much|what) (?:km|kilometres|kilometers|distance) .*?(?:this week|current week)\b", msg) or \
       re.search(r"\b(?:distance|km|kilometres) (?:run |logged )?(?:this|current) week\b", msg) or \
       re.search(r"\bhow far did i run this week\b", msg):
        return IntentType.FACTUAL, {"type": "weekly_distance", "period": "this_week"}

    if re.search(r"\b(?:how many|how much|what) (?:km|kilometres|kilometers|distance) .*?(?:last week|previous week)\b", msg) or \
       re.search(r"\bhow far did i run last week\b", msg):
        return IntentType.FACTUAL, {"type": "weekly_distance", "period": "last_week"}

    # C. Lifetime / all-time distance
    if re.search(r"\b(?:total|lifetime|all[- ]time|overall) (?:distance|km|kilometres|kilometers)\b", msg) or \
       re.search(r"\bhow far have i run (?:overall|in total|all time|lifetime)\b", msg) or \
       re.search(r"\bhow many (?:total )?(?:km|kilometres) have i run\b", msg):
        return IntentType.FACTUAL, {"type": "lifetime_distance"}

    # D. Longest run
    if re.search(r"\b(?:what(?:'s| is)|my) longest run\b", msg) or \
       re.search(r"\blongest distance\b", msg) or \
       re.search(r"\bfurthest run\b", msg) or \
       re.search(r"\bmax(?:imum)? distance\b", msg):
        return IntentType.FACTUAL, {"type": "longest_run"}

    # E. Fastest run / Best pace / Fastest 5K / 10K / PRs
    if re.search(r"\bfastest 5k\b", msg):
        return IntentType.FACTUAL, {"type": "fastest_5k"}

    if re.search(r"\bfastest 10k\b", msg):
        return IntentType.FACTUAL, {"type": "fastest_10k"}

    if re.search(r"\b(?:what(?:'s| is)|my) (?:fastest run|best pace)\b", msg):
        return IntentType.FACTUAL, {"type": "fastest_run"}

    if re.search(r"\b(?:personal records?|personal bests?|prs?|pbs?)\b", msg):
        return IntentType.FACTUAL, {"type": "personal_records"}

    # F. Average pace
    if re.search(r"\b(?:what(?:'s| is)|my) average pace\b", msg) or \
       re.search(r"\baverage pace\b", msg) or \
       re.search(r"\bwhat pace do i (?:usually )?run\b", msg):
        return IntentType.FACTUAL, {"type": "average_pace"}

    # G. Total runs count
    if re.search(r"\bhow many runs (?:did i (?:complete|do)|have i logged|total)\b", msg) or \
       re.search(r"\b(?:number of|count of|total) runs\b", msg):
        if "this week" in msg:
            return IntentType.FACTUAL, {"type": "run_count", "period": "this_week"}
        if "last week" in msg:
            return IntentType.FACTUAL, {"type": "run_count", "period": "last_week"}
        if "this month" in msg:
            return IntentType.FACTUAL, {"type": "run_count", "period": "this_month"}
        if "last month" in msg:
            return IntentType.FACTUAL, {"type": "run_count", "period": "last_month"}
        return IntentType.FACTUAL, {"type": "run_count", "period": "lifetime"}

    # H. Goal progress
    if re.search(r"\b(?:weekly )?goal\b", msg) and \
       re.search(r"\b(?:how am i doing|progress|how much (?:left|remaining)|target|completion)\b", msg):
        return IntentType.FACTUAL, {"type": "goal_progress"}

    if re.search(r"\bhow am i doing with my weekly goal\b", msg) or \
       re.search(r"\bwhat(?:'s| is) my weekly goal\b", msg):
        return IntentType.FACTUAL, {"type": "goal_progress"}

    # I. Month-to-month comparison
    if re.search(r"\bcompare (?:this|current) month to (?:last|previous) month\b", msg) or \
       re.search(r"\bmonth[- ]to[- ]month (?:comparison|progress)\b", msg) or \
       re.search(r"\bmonth over month\b", msg):
        return IntentType.FACTUAL, {"type": "monthly_comparison"}

    # J. Consistency
    if re.search(r"\b(?:how consistent am i|running consistency|consistency percentage)\b", msg):
        return IntentType.FACTUAL, {"type": "consistency"}

    # 3. Default to CONVERSATIONAL (AI advice, motivation, running terminology)
    return IntentType.CONVERSATIONAL, {"topic": "general"}


# ---------------------------------------------------------------------------
# Deterministic Response Generator (No Gemini calls)
# ---------------------------------------------------------------------------

def generate_factual_response(
    user_id: int,
    intent_data: Dict[str, Any],
    today: Optional[date] = None,
) -> str:
    """
    Generate a deterministic, 100% verified response from the RunRush database.
    Does not call Gemini.
    """
    if today is None:
        today = get_today()

    q_type = intent_data.get("type")

    # A. Monthly Distance
    if q_type == "monthly_distance":
        period = intent_data.get("period", "this_month")
        st = get_period_stats(user_id, period, today=today)
        label = st["label"]
        dist = st["distance_km"]
        runs = st["run_count"]
        pace = st["avg_pace_formatted"]

        if runs == 0:
            if period == "last_month":
                return f"You didn't log any runs last month ({label}). Once you record runs, they'll appear right here!"
            return f"You haven't logged any runs yet this month ({label}). Record your first run with Quick Actions to start tracking your mileage!"
        
        runs_text = f"{runs} run" if runs == 1 else f"{runs} runs"
        return f"In **{label}**, you ran a total of **{dist} km** across **{runs_text}** with an average pace of **{pace}**."

    # Specific Month
    if q_type == "specific_month_distance":
        m_num = intent_data["month_num"]
        m_name = intent_data["month_name"]
        year = today.year if m_num <= today.month else today.year - 1
        st = get_period_stats(user_id, "specific_month", today=today, year=year, month=m_num)
        dist = st["distance_km"]
        runs = st["run_count"]
        pace = st["avg_pace_formatted"]
        if runs == 0:
            return f"You didn't log any runs in **{st['label']}**."
        runs_text = f"{runs} run" if runs == 1 else f"{runs} runs"
        return f"In **{st['label']}**, you ran **{dist} km** across **{runs_text}** (average pace: **{pace}**)."

    # B. Weekly Distance
    if q_type == "weekly_distance":
        period = intent_data.get("period", "this_week")
        st = get_period_stats(user_id, period, today=today)
        dist = st["distance_km"]
        runs = st["run_count"]
        pace = st["avg_pace_formatted"]
        label = st["label"]

        if runs == 0:
            if period == "last_week":
                return f"You didn't log any runs last week ({label})."
            return f"You haven't logged any runs yet this week ({label}). Ready to lace up?"

        runs_text = f"{runs} run" if runs == 1 else f"{runs} runs"
        period_name = "This week" if period == "this_week" else "Last week"
        return f"{period_name} ({label}), you logged **{dist} km** across **{runs_text}** (average pace: **{pace}**)."

    # C. Lifetime Distance
    if q_type == "lifetime_distance":
        lt = get_lifetime_stats(user_id)
        if lt["total_runs"] == 0:
            return "You haven't logged any runs yet on RunRush! Once you record your first run, I'll track your total distance."
        runs_text = f"{lt['total_runs']} run" if lt["total_runs"] == 1 else f"{lt['total_runs']} runs"
        return (
            f"You've run a grand total of **{lt['total_distance_km']} km** across **{runs_text}** "
            f"with an all-time duration of **{lt['total_duration_formatted']}** (average pace: **{lt['avg_pace_formatted']}**)."
        )

    # D. Longest Run
    if q_type == "longest_run":
        lr = get_longest_run(user_id)
        if not lr:
            return "You haven't logged any runs yet! Once you record a run with Quick Actions, I'll track your longest distance."
        return (
            f"Your longest run to date is **{lr['distance_km']} km**, completed on **{lr['date']}** "
            f"in **{lr['time_formatted']}** (average pace: **{lr['pace_formatted']}**). 🏆"
        )

    # E. Fastest 5K / 10K / Fastest Run / Personal Records
    if q_type == "fastest_5k":
        f5k = get_fastest_5k(user_id)
        if not f5k:
            return "You haven't logged a 5K run yet (between 4.5 and 5.5 km). Once you complete one, I'll record your 5K personal record!"
        return (
            f"Your fastest 5K is **{f5k['distance_km']} km** in **{f5k['time_formatted']}** "
            f"(pace: **{f5k['pace_formatted']}**), set on **{f5k['date']}**! ⚡"
        )

    if q_type == "fastest_10k":
        f10k = get_fastest_10k(user_id)
        if not f10k:
            return "You haven't logged a 10K run yet (between 9.0 and 11.0 km). Once you complete one, your 10K record will show up here!"
        return (
            f"Your fastest 10K is **{f10k['distance_km']} km** in **{f10k['time_formatted']}** "
            f"(pace: **{f10k['pace_formatted']}**), set on **{f10k['date']}**! ⚡"
        )

    if q_type == "fastest_run":
        fr = get_fastest_run(user_id)
        if not fr:
            return "You don't have any qualifying runs of 1.0 km or more logged yet."
        return (
            f"Your fastest recorded pace for a run $\\ge 1.0\\text{{ km}}$ is **{fr['pace_formatted']}** "
            f"({fr['distance_km']} km in {fr['time_formatted']} on {fr['date']})."
        )

    if q_type == "personal_records":
        pb = get_personal_records(user_id)
        items = []
        if pb["longest_run"]:
            items.append(f"- **Longest Run**: {pb['longest_run']['distance_km']} km ({pb['longest_run']['time_formatted']}, {pb['longest_run']['date']})")
        else:
            items.append("- **Longest Run**: None recorded yet")

        if pb["best_pace"]:
            items.append(f"- **Best Pace ($\\ge 1.0\\text{{ km}}$)**: {pb['best_pace']['pace_formatted']} ({pb['best_pace']['distance_km']} km on {pb['best_pace']['date']})")
        else:
            items.append("- **Best Pace ($\\ge 1.0\\text{{ km}}$)**: None recorded yet")

        if pb["fastest_5k"]:
            items.append(f"- **Fastest 5K**: {pb['fastest_5k']['time_formatted']} ({pb['fastest_5k']['pace_formatted']}, {pb['fastest_5k']['date']})")
        else:
            items.append("- **Fastest 5K**: None recorded yet (4.5–5.5 km)")

        if pb["fastest_10k"]:
            items.append(f"- **Fastest 10K**: {pb['fastest_10k']['time_formatted']} ({pb['fastest_10k']['pace_formatted']}, {pb['fastest_10k']['date']})")
        else:
            items.append("- **Fastest 10K**: None recorded yet (9.0–11.0 km)")

        return "Here are your verified **Personal Records**:\n" + "\n".join(items)

    # F. Average Pace
    if q_type == "average_pace":
        lt = get_lifetime_stats(user_id)
        cm = get_period_stats(user_id, "this_month", today=today)
        if lt["total_runs"] == 0:
            return "You haven't logged any runs yet on RunRush! Once you complete your first run, I'll calculate your average pace."
        
        reply = f"Your all-time average pace is **{lt['avg_pace_formatted']}** across **{lt['total_runs']} runs** (total distance: **{lt['total_distance_km']} km**)."
        if cm["run_count"] > 0:
            reply += f"\n\nThis month ({cm['label']}), your average pace is **{cm['avg_pace_formatted']}** across **{cm['run_count']} runs**."
        return reply

    # G. Run Count
    if q_type == "run_count":
        period = intent_data.get("period", "lifetime")
        if period == "this_week":
            st = get_period_stats(user_id, "this_week", today=today)
            cnt = st["run_count"]
            runs_text = f"{cnt} run" if cnt == 1 else f"{cnt} runs"
            return f"You have completed **{runs_text}** this week ({st['label']}), totaling **{st['distance_km']} km**."
        elif period == "last_week":
            st = get_period_stats(user_id, "last_week", today=today)
            cnt = st["run_count"]
            runs_text = f"{cnt} run" if cnt == 1 else f"{cnt} runs"
            return f"You completed **{runs_text}** last week ({st['label']}), totaling **{st['distance_km']} km**."
        elif period == "this_month":
            st = get_period_stats(user_id, "this_month", today=today)
            cnt = st["run_count"]
            runs_text = f"{cnt} run" if cnt == 1 else f"{cnt} runs"
            return f"You have logged **{runs_text}** this month ({st['label']}), totaling **{st['distance_km']} km**."
        elif period == "last_month":
            st = get_period_stats(user_id, "last_month", today=today)
            cnt = st["run_count"]
            runs_text = f"{cnt} run" if cnt == 1 else f"{cnt} runs"
            return f"You logged **{runs_text}** last month ({st['label']}), totaling **{st['distance_km']} km**."
        else:
            lt = get_lifetime_stats(user_id)
            runs_text = f"{lt['total_runs']} run" if lt["total_runs"] == 1 else f"{lt['total_runs']} runs"
            return f"You have completed **{runs_text}** in total on RunRush, covering **{lt['total_distance_km']} km**."

    # H. Goal Progress
    if q_type == "goal_progress":
        goals = get_weekly_goal_progress(user_id, today=today)
        if not goals["has_goal"]:
            return (
                "You don't currently have an active weekly goal set. "
                "You can set your weekly distance target anytime in your dashboard or settings to track your progress!"
            )
        target = goals["weekly_goal_km"]
        curr = goals["weekly_current_km"]
        rem = goals["weekly_remaining_km"]
        pct = goals["weekly_progress_pct"]

        if goals["weekly_achieved"]:
            return (
                f"You've smashed your weekly goal! 🎉\n"
                f"You have run **{curr} km** against your target of **{target} km** (**{pct}%**). Outstanding effort!"
            )
        return (
            f"You're making solid progress on your weekly goal:\n"
            f"- **Target**: {target} km\n"
            f"- **Completed**: {curr} km ({pct}%)\n"
            f"- **Remaining**: {rem} km remaining to go this week! 💪"
        )

    # I. Monthly Comparison
    if q_type == "monthly_comparison":
        comp = get_period_comparison(user_id, "month_over_month", today=today)
        curr = comp["current"]
        prev = comp["previous"]
        if not comp["previous_has_data"]:
            return (
                f"In **{curr['label']}**, you've run **{curr['distance_km']} km** across **{curr['run_count']} runs**. "
                f"There are no runs logged for the previous month ({prev['label']}) to compare with yet."
            )
        
        delta = comp["distance_delta_km"]
        pct = comp["distance_pct_change"]
        sign = "+" if delta >= 0 else ""
        pace_note = ""
        if comp["pace_delta"] is not None:
            if comp["pace_delta"] < 0:
                pace_note = f"\n- **Pace**: Improved by {abs(comp['pace_delta'])} min/km (faster!)"
            elif comp["pace_delta"] > 0:
                pace_note = f"\n- **Pace**: +{comp['pace_delta']} min/km slower"
            else:
                pace_note = f"\n- **Pace**: Exactly matching last month"

        return (
            f"**Month-over-Month Comparison** ({curr['label']} vs {prev['label']}):\n"
            f"- **Distance**: {curr['distance_km']} km vs {prev['distance_km']} km ({sign}{delta} km, {sign}{pct}%)\n"
            f"- **Runs**: {curr['run_count']} vs {prev['run_count']} runs ({sign}{comp['runs_delta']}){pace_note}"
        )

    # J. Consistency
    if q_type == "consistency":
        c = get_consistency_stats(user_id, today=today)
        pct = c["consistency_percentage"]
        if c["total_runs"] == 0:
            return f"You haven't logged any runs yet this month ({c['month_label']}). Log a run to start building your consistency streak!"
        return (
            f"For **{c['month_label']}**, your running consistency score is **{pct}%** "
            f"({c['total_runs']} runs logged totaling {c['total_distance_km']} km). Keep showing up!"
        )

    return "I couldn't find specific statistics for that request. Try asking about your monthly distance, average pace, longest run, or weekly goal!"


# ---------------------------------------------------------------------------
# Conversational / Hybrid AI Prompt & Calling
# ---------------------------------------------------------------------------

def build_rumi_system_prompt(user_context: Dict[str, Any], is_hybrid: bool = False) -> str:
    """
    Construct system prompt for Gemini. For hybrid questions, injects
    strictly verified user running statistics to prevent hallucinations.
    """
    lt = user_context["lifetime"]
    pb = user_context["personal_bests"]
    cm = user_context["current_month"]
    pm = user_context["previous_month"]
    mom = user_context["month_over_month"]
    cw = user_context["current_week"]
    pw = user_context["previous_week"]
    goals = user_context["goals"]

    longest_str = (
        f"{pb['longest_run']['distance_km']} km ({pb['longest_run']['pace_formatted']}, {pb['longest_run']['date']})"
        if pb["longest_run"] else "None recorded"
    )
    best_pace_str = (
        f"{pb['best_pace']['pace_formatted']} ({pb['best_pace']['distance_km']} km, {pb['best_pace']['date']})"
        if pb["best_pace"] else "None recorded"
    )
    if pb["fastest_5k"]:
        f5k_dur = pb["fastest_5k"].get("duration_min") or pb["fastest_5k"].get("time_min", 0)
        f5k_str = f"{pb['fastest_5k']['distance_km']} km in {f5k_dur}m ({pb['fastest_5k']['pace_formatted']})"
    else:
        f5k_str = "None recorded"

    if goals["weekly_goal_km"]:
        wg_status = "Achieved! 🎉" if goals["weekly_achieved"] else f"{goals['weekly_remaining_km']} km remaining ({goals['weekly_progress_pct']}% complete)"
        weekly_goal_str = f"Target: {goals['weekly_goal_km']} km | Current: {goals['weekly_current_km']} km | Status: {wg_status}"
    else:
        weekly_goal_str = "No weekly goal set currently."

    data_block = f"""
=== VERIFIED RUNRUSH USER DATA (DETERMINISTIC) ===
Runner: {user_context['display_name']}
As of date: {user_context['as_of_date']}

All-Time:
- Total Distance: {lt['total_distance_km']} km across {lt['total_runs']} runs
- Average Pace: {lt['avg_pace_formatted']}
- Longest Run: {longest_str}
- Best Pace (>= 1.0 km): {best_pace_str}
- Fastest 5K: {f5k_str}

This Month ({cm['label']}):
- Total Distance: {cm['distance_km']} km ({cm['run_count']} runs)
- Average Pace: {cm['avg_pace_formatted']}
- Consistency: {cm.get('consistency_percentage', 0.0)}%

Previous Month ({pm['label']}):
- Total Distance: {pm['distance_km']} km ({pm['run_count']} runs)
- Average Pace: {pm['avg_pace_formatted']}

Current Week: {cw['distance_km']} km ({cw['run_count']} runs) | Previous Week: {pw['distance_km']} km ({pw['run_count']} runs)
Weekly Goal: {weekly_goal_str}
=== END VERIFIED RUNRUSH USER DATA ===
"""

    return (
        "You are Rumi, the friendly personal running companion inside RunRush. "
        "You help users understand their running data, celebrate progress, explain running concepts, "
        "and offer practical, motivating athletic guidance. Be conversational, concise, encouraging and honest.\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Never invent, estimate, or independently calculate a user's running metrics, distances, pace, or records.\n"
        "2. If referencing personal statistics, rely exclusively on the verified data provided above.\n"
        "3. If data is unavailable or not recorded, state that clearly.\n"
        "4. Do not provide medical diagnoses or advice on severe injuries.\n"
        "5. Keep responses concise (1-3 paragraphs or clean bullet points).\n\n"
        + data_block.strip()
    )


def is_rumi_configured() -> bool:
    """Check if the Gemini API key is configured."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def generate_rumi_response(
    user_id: int,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Main entry point for processing a user's message.
    1. Directs factual questions to deterministic database logic (no Gemini call).
    2. Directs hybrid/conversational questions to Gemini with verified ground truth context.

    Returns:
        Dict with 'reply' (str), 'history' (list), and 'source' ('database' | 'gemini').
    """
    if not user_message or not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("Message cannot be empty.")

    clean_message = user_message.strip()
    if len(clean_message) > _MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message exceeds maximum length of {_MAX_MESSAGE_LENGTH} characters.")

    if today is None:
        today = get_today()

    # Classify Intent
    intent_type, intent_data = classify_rumi_intent(clean_message)

    # -----------------------------------------------------------------------
    # PATH A: Simple Factual Questions -> Deterministic Database Response
    # -----------------------------------------------------------------------
    if intent_type == IntentType.FACTUAL:
        reply_text = generate_factual_response(user_id, intent_data, today=today)

        # Update session history
        history = conversation_history or []
        trimmed_history = history[-_MAX_HISTORY_TURNS:]
        updated_history = list(trimmed_history)
        updated_history.append({"role": "user", "text": clean_message})
        updated_history.append({"role": "model", "text": reply_text})

        return {
            "reply": reply_text,
            "history": updated_history,
            "source": "database",
        }

    # -----------------------------------------------------------------------
    # PATH B: Hybrid or Conversational Questions -> Gemini AI Response
    # -----------------------------------------------------------------------
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("AI provider is not configured. GEMINI_API_KEY is missing.")

    try:
        from google import genai as _genai
        from google.genai import types as _types
    except ImportError as e:
        raise RuntimeError(f"Required AI dependencies are not installed: {e}")

    # Build verified context
    user_context = get_user_rumi_context(user_id, today=today)
    system_prompt = build_rumi_system_prompt(user_context, is_hybrid=(intent_type == IntentType.HYBRID))

    history = conversation_history or []
    trimmed_history = history[-_MAX_HISTORY_TURNS:]

    contents = []
    for item in trimmed_history:
        role = item.get("role")
        text = item.get("text", "")
        if role in ("user", "model") and text:
            contents.append(
                _types.Content(
                    role=role,
                    parts=[_types.Part.from_text(text=text[:_MAX_MESSAGE_LENGTH])]
                )
            )

    contents.append(
        _types.Content(
            role="user",
            parts=[_types.Part.from_text(text=clean_message)]
        )
    )

    model_name = os.environ.get("RUMI_GEMINI_MODEL", "gemini-3.5-flash-lite")

    client = _genai.Client(
        api_key=api_key,
        http_options={
            "timeout": 15000.0,
            "retry_options": {
                "attempts": 2,
                "initial_delay": 1.0,
                "max_delay": 8.0,
            },
        },
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=_types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=600,
                temperature=0.7,
            ),
        )

        reply_text = None
        candidates = getattr(response, "candidates", None)
        if candidates:
            reply_text = getattr(response, "text", None)

        if not reply_text:
            reply_text = "I'm having a little trouble thinking of a response right now. Could you ask that in another way?"

        clean_reply = reply_text.strip()

        updated_history = list(trimmed_history)
        updated_history.append({"role": "user", "text": clean_message})
        updated_history.append({"role": "model", "text": clean_reply})

        return {
            "reply": clean_reply,
            "history": updated_history,
            "source": "gemini",
        }
    except Exception as exc:
        err_str = str(exc)
        print(f"[rumi] AI Provider error: {type(exc).__name__}: {err_str}")
        if "402" in err_str or "credits are depleted" in err_str.lower():
            raise RuntimeError("Gemini API credits are depleted. Please replenish credits in Google AI Studio or provide a new key.") from exc
        if "403" in err_str or "api_key_invalid" in err_str.lower() or "invalid api key" in err_str.lower():
            raise RuntimeError("Gemini API key is invalid or lacks required permissions.") from exc
        raise RuntimeError(f"AI provider failed: {err_str}") from exc
