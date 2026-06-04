"""
Badge service - Business logic for the badge/achievement system.
Ported from app.py into a testable service layer.
"""

from datetime import datetime

from db import get_db, IntegrityError
from services.streak_service import initialize_user_stats


# --------------- Public API ---------------

def get_user_badges(user_id):
    """
    Retrieve all badges earned by a user.

    Args:
        user_id: User ID

    Returns:
        list: List of badge rows (badge_key, unlocked_at, activity_id)
    """
    conn = get_db()
    badges = conn.execute(
        "SELECT * FROM user_badges WHERE user_id = ? ORDER BY unlocked_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return badges


def award_badge(user_id, badge_key, activity_id=None):
    """
    Award a badge to a user.

    Args:
        user_id: User ID
        badge_key: Badge identifier string (e.g. 'FIRST_5K')
        activity_id: Optional run ID associated with this badge

    Returns:
        bool: True if newly awarded, False if the user already had it.
    """
    conn = get_db()
    try:
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO user_badges (user_id, badge_key, unlocked_at, activity_id)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, badge_key, now_str, activity_id)
        )
        conn.commit()
        return True  # Newly awarded
    except IntegrityError:
        # UNIQUE constraint — user already has this badge
        return False
    finally:
        conn.close()


def evaluate_badges_for_user(user_id, last_run_id=None):
    """
    Evaluate all badge criteria for a user after a run is added.
    Awards any newly-earned badges and returns a list of their keys.

    Args:
        user_id: User ID
        last_run_id: Optional ID of the most recently logged run

    Returns:
        list[str]: Keys of newly awarded badges (empty list if none)
    """
    conn = get_db()

    # Get current stats
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if not stats:
        initialize_user_stats(user_id)
        stats = conn.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    # Get the triggering run (if provided)
    last_run = None
    if last_run_id:
        last_run = conn.execute(
            "SELECT * FROM runs WHERE id = ?",
            (last_run_id,)
        ).fetchone()

    conn.close()

    candidates = []

    # 1. Single-run distance milestones
    if last_run:
        dist = last_run['distance_km']
        if 5.0 <= dist < 7.0:
            candidates.append(('FIRST_5K', last_run_id))
        if dist >= 10.0:
            candidates.append(('FIRST_10K', last_run_id))

    # 2. Cumulative distance milestones
    total = stats['total_distance_km'] if stats else 0
    if total >= 50.0:
        candidates.append(('TOTAL_50KM', None))
    if total >= 100.0:
        candidates.append(('TOTAL_100KM', None))

    # 3. Streak milestones
    streak = stats['current_streak'] if stats else 0
    if streak >= 7:
        candidates.append(('STREAK_7DAY', None))
    if streak >= 30:
        candidates.append(('STREAK_30DAY', None))

    # Award each candidate (duplicate-safe via UNIQUE constraint)
    newly_awarded = []
    for badge_key, activity_id in candidates:
        if award_badge(user_id, badge_key, activity_id):
            newly_awarded.append(badge_key)

    return newly_awarded
