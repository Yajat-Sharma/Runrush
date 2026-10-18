"""Training load (ACWR) calculation module.

Pure calculation logic — no Flask or DB imports. All functions take plain
lists/dicts so they are trivially testable with fixed dates.

ACWR = Acute workload (last 7 days) / Chronic workload (4-week rolling average).

Reference: "today" is passed in as a parameter (copied from streak_service.py's
date.today() approach) so tests are deterministic — no bare datetime.now() inside.
"""

from datetime import date, datetime, timedelta


# ── ACWR zone thresholds (documented constants) ──────────────────────────
# Format: (lower_bound_inclusive, upper_bound_exclusive, zone_name)
ZONE_DETRAINING = "Detraining risk"    # < 0.8
ZONE_SWEET_SPOT = "Sweet spot"          # 0.8 - 1.3
ZONE_CAUTION = "Caution"                # 1.3 - 1.5
ZONE_HIGH_SPIKE = "High spike"          # > 1.5

ACWR_ZONE_THRESHOLDS = (
    (0.0, 0.8, ZONE_DETRAINING),
    (0.8, 1.3, ZONE_SWEET_SPOT),
    (1.3, 1.5, ZONE_CAUTION),
    (1.5, float("inf"), ZONE_HIGH_SPIKE),
)

# Windows
ACUTE_DAYS = 7          # acute load = last 7 days
CHRONIC_DAYS = 28       # chronic load = last 28 days
CHRONIC_WEEKS = 4       # chronic = sum(28 days) / 4
SERIES_DAYS = 56        # daily ACWR series for the last 8 weeks
MIN_HISTORY_DAYS = 28   # need at least 28 days between first run and today


def _median_pace_min_per_km(runs):
    """Median pace (min/km) across runs that have both distance and duration."""
    paces = []
    for r in runs:
        dist = r.get("distance_km")
        t = r.get("time_min")
        if dist and dist > 0 and t and t > 0:
            paces.append(float(t) / float(dist))
    if not paces:
        return None
    paces.sort()
    n = len(paces)
    mid = n // 2
    if n % 2 == 1:
        return paces[mid]
    return (paces[mid - 1] + paces[mid]) / 2.0


def _parse_run_date(raw_date):
    """Parse a run's date into a date object, or None if unparseable."""
    if raw_date is None:
        return None
    if isinstance(raw_date, date):
        return raw_date
    try:
        return datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _load_for_run(run, median_pace):
    """Return load (minutes) for a single run.

    Uses duration (time_min) as the base load. If duration is missing but
    distance exists, estimates load from distance using the user's median pace.
    If neither is usable, returns None (run is skipped).
    """
    time_min = run.get("time_min")
    distance_km = run.get("distance_km")

    if time_min is not None:
        try:
            t = float(time_min)
            if t > 0:
                return t
        except (TypeError, ValueError):
            pass

    if distance_km is not None and median_pace:
        try:
            d = float(distance_km)
            if d > 0:
                return d * median_pace
        except (TypeError, ValueError):
            pass

    return None


def compute_training_load(runs, today=None):
    """Compute Acute:Chronic Workload Ratio (ACWR) for a user.

    Args:
        runs: List of run dicts with keys: date (str YYYY-MM-DD or date),
              distance_km (float or None), time_min (float or None).
        today: date object used as the reference "today" (for deterministic tests).
               Defaults to date.today() if not provided.

    Returns:
        dict with keys:
            status: "ok" or "insufficient_data"
            acwr: float or None
            acute: float (sum of last 7 days load in minutes)
            chronic: float (average weekly load over last 28 days, in minutes)
            zone: str zone name or None
            series: list of {"date": str, "acwr": float or None} for last 8 weeks
            weekly_change_pct: float or None
            message: str plain-sentence guidance
    """
    if today is None:
        today = date.today()

    # ── Build daily load map (days with no run = 0) ─────────────────────
    median_pace = _median_pace_min_per_km(runs)
    daily_loads = {}          # date -> total load in minutes
    valid_run_dates = []

    for r in runs:
        run_date = _parse_run_date(r.get("date"))
        if run_date is None:
            continue
        load = _load_for_run(r, median_pace)
        if load is None:
            continue
        daily_loads[run_date] = daily_loads.get(run_date, 0.0) + load
        valid_run_dates.append(run_date)

    # No usable runs at all
    if not valid_run_dates:
        return _empty_result("Log some runs to see your training load.")

    # ── Minimum history check ───────────────────────────────────────────
    first_run = min(valid_run_dates)
    if (today - first_run).days < MIN_HISTORY_DAYS:
        return _empty_result("Need 4 weeks of runs to calculate your training load.")

    # ── Acute load (last 7 days, including today) ───────────────────────
    acute = sum(
        daily_loads.get(today - timedelta(days=i), 0.0)
        for i in range(ACUTE_DAYS)
    )

    # ── Chronic load (average weekly load over last 28 days) ────────────
    chronic_total = sum(
        daily_loads.get(today - timedelta(days=i), 0.0)
        for i in range(CHRONIC_DAYS)
    )
    chronic = chronic_total / CHRONIC_WEEKS

    if chronic == 0:
        return _empty_result("Need 4 weeks of runs to calculate your training load.")

    # ── ACWR ────────────────────────────────────────────────────────────
    acwr = round(acute / chronic, 2)

    # ── Zone ────────────────────────────────────────────────────────────
    zone = ZONE_HIGH_SPIKE
    for low, high, name in ACWR_ZONE_THRESHOLDS:
        if low <= acwr < high:
            zone = name
            break

    # ── Week-over-week mileage change % ─────────────────────────────────
    prev_load = sum(
        daily_loads.get(today - timedelta(days=i), 0.0)
        for i in range(ACUTE_DAYS, ACUTE_DAYS * 2)
    )
    if prev_load > 0:
        weekly_change_pct = round(((acute - prev_load) / prev_load) * 100, 1)
    else:
        weekly_change_pct = None

    # ── Daily ACWR series for the last 8 weeks (56 days) ────────────────
    series = []
    for i in range(SERIES_DAYS - 1, -1, -1):
        d = today - timedelta(days=i)
        day_acute = sum(
            daily_loads.get(d - timedelta(days=j), 0.0)
            for j in range(ACUTE_DAYS)
        )
        day_chronic_total = sum(
            daily_loads.get(d - timedelta(days=j), 0.0)
            for j in range(CHRONIC_DAYS)
        )
        day_chronic = day_chronic_total / CHRONIC_WEEKS
        if day_chronic > 0:
            series.append({
                "date": d.isoformat(),
                "acwr": round(day_acute / day_chronic, 2),
            })
        else:
            series.append({
                "date": d.isoformat(),
                "acwr": None,
            })

    # ── Guidance message (one plain sentence, no medical claims) ────────
    if zone == ZONE_SWEET_SPOT:
        message = f"Your training load is steady at {acwr}x your 4-week average. Keep it up!"
    elif zone == ZONE_DETRAINING:
        message = (
            f"Your load is {acwr}x your 4-week average — below your usual volume. "
            "Consider adding an easy run."
        )
    elif zone == ZONE_CAUTION:
        message = (
            f"Your load is {acwr}x your 4-week average. "
            "Slightly elevated — monitor how you feel."
        )
    else:  # High spike
        change_str = ""
        if weekly_change_pct is not None and weekly_change_pct > 0:
            change_str = f" (up {abs(weekly_change_pct):.0f}% this week)"
        message = (
            f"Your load spiked to {acwr}x your 4-week average{change_str}. "
            "Consider an easier day."
        )

    return {
        "status": "ok",
        "acwr": acwr,
        "acute": round(acute, 1),
        "chronic": round(chronic, 1),
        "zone": zone,
        "series": series,
        "weekly_change_pct": weekly_change_pct,
        "message": message,
    }


def _empty_result(message):
    """Return an insufficient_data result with the given message."""
    return {
        "status": "insufficient_data",
        "acwr": None,
        "acute": 0.0,
        "chronic": 0.0,
        "zone": None,
        "series": [],
        "weekly_change_pct": None,
        "message": message,
    }
