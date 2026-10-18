"""Unit tests for the pure training_load calculation module.

Tests use fixed dates so they are deterministic — no reliance on the real clock.
"""

from datetime import date, timedelta

from services.training_load import compute_training_load


def _run(d, distance=None, time_min=None):
    """Helper to build a run dict."""
    return {
        "date": d.isoformat() if isinstance(d, date) else d,
        "distance_km": distance,
        "time_min": time_min,
    }


# ── Fixed reference dates ────────────────────────────────────────────────
TODAY = date(2026, 10, 19)
FOUR_WEEKS_AGO = TODAY - timedelta(days=28)
EIGHT_WEEKS_AGO = TODAY - timedelta(days=56)


def test_steady_training_acwr_about_one_sweet_spot():
    """Steady training (same load every day) -> ACWR ~1.0, zone 'Sweet spot'."""
    runs = []
    d = FOUR_WEEKS_AGO
    while d <= TODAY:
        # 30 min every day -> acute=210, chronic=210, ACWR=1.0
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "ok"
    assert result["acwr"] == 1.0
    assert result["zone"] == "Sweet spot"
    assert result["acute"] == 210.0
    assert result["chronic"] == 210.0


def test_sudden_double_week_high_spike():
    """Sudden 2x week -> zone 'High spike'."""
    runs = []
    d = FOUR_WEEKS_AGO
    # First 3 weeks: 30 min/day (normal)
    while d <= TODAY - timedelta(days=7):
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)
    # Last 7 days: 60 min/day (double)
    while d <= TODAY:
        runs.append(_run(d, distance=5.0, time_min=60.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "ok"
    # Acute = 7*60 = 420. Chronic = (21*30 + 7*60) / 4 = (630 + 420) / 4 = 262.5
    # ACWR = 420 / 262.5 = 1.6 -> High spike
    assert result["acwr"] == 1.6
    assert result["zone"] == "High spike"


def test_layoff_then_return_handles_zeros_no_division_by_zero():
    """Layoff then return: a run >28 days ago with no recent runs -> chronic==0,
    insufficient_data, no ZeroDivisionError."""
    # Run 30 days ago (passes the 28-day history check), then nothing for 28 days
    runs = [_run(TODAY - timedelta(days=30), distance=5.0, time_min=30.0)]

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "insufficient_data"
    assert result["acwr"] is None
    assert result["chronic"] == 0.0
    assert result["zone"] is None


def test_less_than_28_days_returns_insufficient_data():
    """<28 days of history -> 'insufficient_data'."""
    runs = [_run(TODAY - timedelta(days=i), distance=5.0, time_min=30.0) for i in range(10)]

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "insufficient_data"
    assert result["acwr"] is None


def test_missing_duration_with_distance_fallback():
    """Missing duration but distance present -> estimate load from median pace.

    Builds 28 days of steady runs (establishing median pace), then one run
    with distance but no time -> should estimate load using median pace.
    """
    runs = []
    d = FOUR_WEEKS_AGO
    while d <= TODAY:
        runs.append(_run(d, distance=5.0, time_min=30.0))  # pace = 6 min/km
        d += timedelta(days=1)
    # Add a run with distance but NO time on a recent day -> 5km * 6 = 30 min
    runs.append(_run(TODAY, distance=5.0, time_min=None))

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "ok"
    # Acute = last 7 days: Oct 13-18 (6 days * 30) + Oct 19 (30 loop + 30 fallback) = 180 + 60 = 240
    assert result["acute"] == 240.0


def test_run_with_neither_duration_nor_distance_is_skipped():
    """A run with neither duration nor distance is skipped (not counted)."""
    runs = [
        _run(date(2026, 9, 20), distance=None, time_min=None),
        _run(date(2026, 9, 21), distance=None, time_min=None),
    ]
    # Add enough history with valid runs to pass the 28-day check
    d = FOUR_WEEKS_AGO
    while d <= TODAY:
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "ok"
    assert result["acwr"] == 1.0


def test_multiple_runs_on_one_day_are_summed():
    """Multiple runs on the same day are summed into that day's load."""
    runs = [
        _run(TODAY, distance=5.0, time_min=30.0),
        _run(TODAY, distance=5.0, time_min=20.0),
    ]
    # Fill the rest of the 28 days with 30 min/day
    d = FOUR_WEEKS_AGO
    while d <= TODAY - timedelta(days=1):
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, TODAY)

    assert result["status"] == "ok"
    # Acute = last 7 days: Oct 13-18 (6 days * 30) + Oct 19 (30 + 20) = 180 + 50 = 230
    assert result["acute"] == 230.0


def test_no_runs_returns_insufficient_data():
    """Zero runs -> insufficient_data, no crash."""
    result = compute_training_load([], TODAY)

    assert result["status"] == "insufficient_data"
    assert result["acwr"] is None


def test_single_run_returns_insufficient_data():
    """One run -> insufficient_data (not enough 28-day history)."""
    result = compute_training_load([_run(TODAY, distance=5.0, time_min=30.0)], TODAY)

    assert result["status"] == "insufficient_data"


def test_zone_boundaries():
    """Zone thresholds are applied correctly at boundaries."""
    # ACWR exactly 0.8 -> Sweet spot (lower bound inclusive)
    runs = []
    d = FOUR_WEEKS_AGO
    while d <= TODAY - timedelta(days=7):
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)
    # Last 7 days: 24 min/day -> acute = 168, chronic = (21*30 + 7*24)/4 = (630+168)/4 = 199.5
    # ACWR = 168/199.5 = 0.842... -> Sweet spot
    while d <= TODAY:
        runs.append(_run(d, distance=5.0, time_min=24.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, TODAY)
    assert 0.79 < result["acwr"] < 0.85
    assert result["zone"] == "Sweet spot"


def test_series_has_56_daily_points():
    """Series returns 56 daily points for the last 8 weeks."""
    runs = []
    d = FOUR_WEEKS_AGO
    while d <= TODAY:
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, TODAY)

    assert len(result["series"]) == 56
    # First entry should be the oldest date (55 days ago)
    assert result["series"][0]["date"] == (TODAY - timedelta(days=55)).isoformat()
    # Last entry should be today
    assert result["series"][-1]["date"] == TODAY.isoformat()


def test_today_parameter_is_used_not_real_clock():
    """Passing today as a parameter works — function does not call date.today() internally."""
    # Use a fixed today far from real now
    fixed_today = date(2026, 1, 15)
    four_weeks_before = fixed_today - timedelta(days=28)
    runs = []
    d = four_weeks_before
    while d <= fixed_today:
        runs.append(_run(d, distance=5.0, time_min=30.0))
        d += timedelta(days=1)

    result = compute_training_load(runs, fixed_today)

    assert result["status"] == "ok"
    assert result["acwr"] == 1.0
