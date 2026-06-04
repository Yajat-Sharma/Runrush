"""
Run service - Business logic for run management.
Ported from app.py into a testable service layer.
"""

import hashlib
import random
from datetime import datetime, timedelta, date

from db import get_db, IntegrityError
from utils.validators import (
    validate_date, validate_distance, validate_time,
    validate_run_type, sanitize_notes, ValidationError
)


def calc_stats(distance_km, time_min, weight_kg=70.0):
    """
    Calculate pace and calories for a run.

    Args:
        distance_km: Distance in kilometres
        time_min: Duration in minutes
        weight_kg: User's body weight in kg (default 70)

    Returns:
        tuple: (pace_min_per_km, calories)
    """
    pace = time_min / distance_km
    calories = weight_kg * distance_km
    return round(pace, 2), round(calories, 0)


# Alias kept for backward compat
calculate_stats = calc_stats


def generate_run_insight(user_id, distance, pace, calories):
    """
    Generate a friendly, motivational 1-2 line insight about the run.
    Analyzes performance vs user's history and provides encouraging feedback.

    Args:
        user_id: User ID
        distance: Distance in km
        pace: Pace in min/km
        calories: Calories burned

    Returns:
        str: Motivational insight string
    """
    conn = get_db()

    cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent_runs = conn.execute("""
        SELECT distance_km, pace, calories
        FROM runs
        WHERE user_id = ?
        AND date >= ?
        ORDER BY date DESC
        LIMIT 10
    """, (user_id, cutoff_date)).fetchall()

    conn.close()

    if len(recent_runs) <= 1:
        return random.choice([
            "Great start! Every journey begins with a single step 🏃",
            "Welcome to your running journey! Keep it up 💪",
            "First run logged! This is just the beginning 🔥",
            "Awesome! You've taken the first step toward your goals 🎯"
        ])

    avg_pace = sum(r["pace"] for r in recent_runs[1:]) / len(recent_runs[1:])
    avg_distance = sum(r["distance_km"] for r in recent_runs[1:]) / len(recent_runs[1:])

    insights = []

    if pace < avg_pace * 0.95:
        insights.append("You beat your average pace! 🔥")
    elif pace < avg_pace:
        insights.append("Solid pace today! 👏")
    elif pace > avg_pace * 1.1:
        insights.append("Pace was slower today — try starting easier next time 🏃")

    if distance >= 5 and distance < 5.5:
        insights.append("You hit 5K! Great milestone 🎉")
    elif distance >= 10 and distance < 10.5:
        insights.append("Double digits! 10K completed 🏆")
    elif distance > avg_distance * 1.2:
        insights.append("Longest run in a while! Keep pushing 💪")
    elif distance > avg_distance:
        insights.append("You went further than usual today!")

    if len(recent_runs) >= 5:
        insights.append("Great consistency this month!")

    if insights:
        return " ".join(insights[:2])

    return random.choice([
        "Another run in the books! Keep it up 🏃",
        "Consistent effort pays off. Well done! 💪",
        "Every run counts. Great work today! 🔥",
        "You showed up and that's what matters! 👏"
    ])


def add_run(user_id, date_str, distance_km, time_min, run_type='easy',
            notes='', weight_kg=70.0):
    """
    Add a new run for a user.

    Args:
        user_id: User ID
        date_str: Run date string (YYYY-MM-DD)
        distance_km: Distance in km
        time_min: Duration in minutes
        run_type: Type of run (easy/tempo/long/interval/race)
        notes: Optional notes
        weight_kg: User weight for calorie calculation

    Returns:
        tuple: (success, run_id, insight, error)
    """
    try:
        # Validate inputs
        date_obj = validate_date(date_str)
        distance_km = validate_distance(distance_km)
        time_min = validate_time(time_min)
        run_type = validate_run_type(run_type)
        notes = sanitize_notes(notes)
    except ValidationError as e:
        return False, None, None, str(e)

    pace, calories = calc_stats(distance_km, time_min, weight_kg)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO runs (user_id, date, distance_km, time_min, pace,
                              calories, run_type, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, date_str, distance_km, time_min, pace,
             calories, run_type, notes, now_str)
        )
        conn.commit()

        # Fetch the inserted run id
        run_row = conn.execute(
            "SELECT id FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        run_id = run_row["id"] if run_row else None

        insight = generate_run_insight(user_id, distance_km, pace, calories)

        # Persist insight
        if run_id and insight:
            conn.execute(
                "UPDATE runs SET insight = ? WHERE id = ?",
                (insight, run_id)
            )
            conn.commit()

        return True, run_id, insight, None
    except Exception as e:
        return False, None, None, str(e)
    finally:
        conn.close()


def get_user_runs(user_id, sort_by='date', filter_opt='all'):
    """
    Retrieve runs for a user with optional sorting and filtering.

    Args:
        user_id: User ID
        sort_by: Sort field ('date', 'distance', 'time')
        filter_opt: Filter option ('all', 'last7', 'month', '5k10k')

    Returns:
        list: List of run rows
    """
    if sort_by == 'distance':
        order_clause = " ORDER BY distance_km DESC, date DESC"
    elif sort_by == 'time':
        order_clause = " ORDER BY time_min DESC, date DESC"
    else:
        order_clause = " ORDER BY date DESC, id DESC"

    conn = get_db()
    runs = conn.execute(
        "SELECT * FROM runs WHERE user_id = ?" + order_clause,
        (user_id,)
    ).fetchall()
    conn.close()

    # Apply filter
    if filter_opt == 'last7':
        cutoff = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        runs = [r for r in runs if r['date'] >= cutoff]
    elif filter_opt == 'month':
        today = date.today()
        runs = [r for r in runs
                if r['date'].startswith(f"{today.year}-{today.month:02d}")]
    elif filter_opt == '5k10k':
        runs = [r for r in runs if 5.0 <= r['distance_km'] <= 10.0]

    return runs


def update_run(run_id, user_id, fields):
    """
    Update fields of an existing run. Logs changes to edit_history.

    Args:
        run_id: Run ID to update
        user_id: User performing the update
        fields: dict of field_name -> new_value

    Returns:
        tuple: (success, error)
    """
    conn = get_db()
    try:
        run = conn.execute(
            "SELECT * FROM runs WHERE id = ? AND user_id = ?",
            (run_id, user_id)
        ).fetchone()

        if not run:
            return False, "Run not found"

        changes = {}
        for field, new_value in fields.items():
            old_value = run[field]
            if str(old_value) != str(new_value):
                changes[field] = (old_value, new_value)

        if not changes:
            return True, None  # No changes

        # Recalculate stats if distance or time changed
        distance = float(fields.get('distance_km', run['distance_km']))
        time_min = float(fields.get('time_min', run['time_min']))
        pace = round(time_min / distance, 2)

        conn.execute(
            """UPDATE runs SET distance_km=?, time_min=?, pace=?,
               run_type=?, notes=?, date=?
               WHERE id=?""",
            (
                distance, time_min, pace,
                fields.get('run_type', run['run_type']),
                sanitize_notes(fields.get('notes', run['notes'] or '')),
                fields.get('date', run['date']),
                run_id
            )
        )

        # Log edit history
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for field, (old_val, new_val) in changes.items():
            conn.execute(
                """INSERT INTO edit_history
                   (run_id, user_id, field_name, old_value, new_value, edited_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, user_id, field, str(old_val), str(new_val), now_str)
            )

        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_run(run_id, user_id):
    """
    Delete a run by ID.

    Args:
        run_id: Run ID to delete
        user_id: Requesting user's ID (ownership check)

    Returns:
        tuple: (success, distance_km, date_str, error)
    """
    conn = get_db()
    try:
        run = conn.execute(
            "SELECT * FROM runs WHERE id = ? AND user_id = ?",
            (run_id, user_id)
        ).fetchone()

        if not run:
            return False, None, None, "Run not found or unauthorized"

        distance_km = run['distance_km']
        date_str = run['date']

        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()
        return True, distance_km, date_str, None
    except Exception as e:
        return False, None, None, str(e)
    finally:
        conn.close()


def sync_offline_run(user_id, data):
    """
    Sync an offline-logged run. Detects duplicates via SHA-256 hash.

    Args:
        user_id: User ID
        data: dict with keys: date, distance, time, hash, tempId, notes, run_type

    Returns:
        dict: Result with success, runId, insight, newBadges
    """
    required = ['date', 'distance', 'time', 'hash']
    for field in required:
        if field not in data:
            return {'success': False, 'error': f'Missing field: {field}'}

    # Verify SHA-256 hash
    expected_hash = hashlib.sha256(
        f"{data['date']}{data['distance']}{data['time']}".encode()
    ).hexdigest()

    if data['hash'] != expected_hash:
        return {'success': False, 'error': 'Hash mismatch — data integrity check failed', 'status_code': 400}

    # Check for duplicate
    conn = get_db()
    existing = conn.execute(
        """SELECT id FROM runs WHERE user_id = ? AND date = ?
           AND ABS(distance_km - ?) < 0.01 AND ABS(time_min - ?) < 0.1""",
        (user_id, data['date'], float(data['distance']), float(data['time']))
    ).fetchone()
    conn.close()

    if existing:
        return {'success': False, 'error': 'Duplicate run detected', 'status_code': 409}

    # Get user weight for calorie calculation
    conn = get_db()
    user_row = conn.execute("SELECT weight FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    weight = float(user_row['weight']) if user_row and user_row['weight'] else 70.0

    success, run_id, insight, error = add_run(
        user_id=user_id,
        date_str=data['date'],
        distance_km=float(data['distance']),
        time_min=float(data['time']),
        run_type=data.get('run_type', 'easy'),
        notes=data.get('notes', ''),
        weight_kg=weight,
    )

    if not success:
        return {'success': False, 'error': error}

    return {
        'success': True,
        'runId': run_id,
        'insight': insight,
        'newBadges': [],
        'message': 'Run synced successfully'
    }
