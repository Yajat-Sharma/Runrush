"""
Streak service - Business logic for streak and user stats calculation.
Ported from app.py into a testable service layer.
"""

from datetime import datetime, timedelta, date

from db import get_db, IntegrityError


def calculate_streak_for_user(user_id):
    """
    Calculate current and best streak for a user from their run history.

    Args:
        user_id: User ID

    Returns:
        tuple: (current_streak, best_streak)
    """
    conn = get_db()

    runs = conn.execute(
        "SELECT DISTINCT date FROM runs WHERE user_id = ? ORDER BY date ASC",
        (user_id,)
    ).fetchall()

    conn.close()

    if not runs:
        return 0, 0

    all_dates = [datetime.strptime(r['date'], "%Y-%m-%d").date() for r in runs]
    today = date.today()

    # Calculate current streak (backward from today or yesterday)
    current_streak = 0
    day_pointer = today
    while day_pointer in all_dates:
        current_streak += 1
        day_pointer = day_pointer - timedelta(days=1)

    # Calculate best streak
    best_streak = 0
    streak = 1
    for i in range(1, len(all_dates)):
        if all_dates[i] == all_dates[i - 1] + timedelta(days=1):
            streak += 1
        else:
            best_streak = max(best_streak, streak)
            streak = 1
    best_streak = max(best_streak, streak)

    return current_streak, best_streak


def initialize_user_stats(user_id):
    """
    Create initial stats row for a user if it doesn't already exist.

    Args:
        user_id: User ID

    Returns:
        dict-like row of the user's stats
    """
    conn = get_db()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn.execute(
            """
            INSERT INTO user_stats
                (user_id, total_distance_km, current_streak, best_streak, updated_at)
            VALUES (?, 0.0, 0, 0, ?)
            """,
            (user_id, now_str)
        )
        conn.commit()
    except IntegrityError:
        # Stats row already exists — that's fine
        pass

    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()
    return stats


def update_user_stats(user_id, run_date_str, distance_km, operation='add'):
    """
    Incrementally update user_stats when a run is added or deleted.

    Args:
        user_id: User ID
        run_date_str: Date string of the affected run (YYYY-MM-DD)
        distance_km: Distance of the affected run in km
        operation: 'add' or 'delete'
    """
    conn = get_db()

    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if not stats:
        conn.close()
        initialize_user_stats(user_id)
        conn = get_db()
        stats = conn.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    # Update total distance
    if operation == 'add':
        new_total = stats['total_distance_km'] + distance_km
    else:  # 'delete'
        new_total = max(0.0, stats['total_distance_km'] - distance_km)

    # Recalculate streaks from scratch for accuracy
    current_streak, best_streak = calculate_streak_for_user(user_id)

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute(
        """
        UPDATE user_stats
        SET total_distance_km = ?,
            current_streak    = ?,
            best_streak       = ?,
            last_activity_date = ?,
            updated_at        = ?
        WHERE user_id = ?
        """,
        (new_total, current_streak, best_streak, run_date_str, now_str, user_id)
    )
    conn.commit()
    conn.close()
