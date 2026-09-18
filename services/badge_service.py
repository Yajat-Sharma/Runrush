"""
Badge service - Business logic for the badge/achievement system.
Ported from app.py into a testable service layer.
"""

from datetime import datetime
from db import get_db, IntegrityError
from services.streak_service import initialize_user_stats

BADGE_METADATA = {
    'FIRST_5K': {
        'name': 'First 5K',
        'icon': '🏅',
        'description': 'Completed your first 5K run.'
    },
    'FIRST_10K': {
        'name': 'First 10K',
        'icon': '🎯',
        'description': 'Completed your first 10K run.'
    },
    'TOTAL_50KM': {
        'name': '50KM Club',
        'icon': '🏃‍♂️',
        'description': 'Ran a total of 50 kilometers.'
    },
    'TOTAL_100KM': {
        'name': '100KM Club',
        'icon': '🔥',
        'description': 'Ran a total of 100 kilometers.'
    },
    'STREAK_7DAY': {
        'name': '7-Day Streak',
        'icon': '⚡',
        'description': 'Maintained a 7-day running streak.'
    },
    'STREAK_30DAY': {
        'name': '30-Day Streak',
        'icon': '🌟',
        'description': 'Maintained an incredible 30-day running streak.'
    }
}
# --------------- Public API ---------------

def get_user_badges(user_id):
    """
    Retrieve all badges earned by a user.
    """
    conn = get_db()
    badges = conn.execute(
        """
        SELECT ub.unlocked_at, ub.run_id as activity_id, b.key as badge_key, b.name, b.icon_url
        FROM user_badges ub
        JOIN badges b ON ub.badge_id = b.id
        WHERE ub.user_id = ?
        ORDER BY ub.unlocked_at DESC
        """,
        (user_id,)
    ).fetchall()
    conn.close()
    return badges


def award_badge(user_id, badge_key, activity_id=None):
    """
    Award a badge to a user.
    """
    conn = get_db()
    try:
        badge = conn.execute("SELECT id FROM badges WHERE key = ?", (badge_key,)).fetchone()
        if not badge:
            print(f"Error: Badge definition missing for key '{badge_key}'")
            return False

        badge_id = badge['id'] if isinstance(badge, dict) else badge[0]

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO user_badges (user_id, badge_id, unlocked_at, run_id)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, badge_id, now_str, activity_id)
        )
        conn.commit()
        return True  # Newly awarded
    except IntegrityError:
        # UNIQUE constraint — user already has this badge
        conn.rollback()
        return False
    finally:
        conn.close()


def evaluate_badges_for_user(user_id, last_run_id=None):
    """
    Evaluate all badge criteria for a user after a run is added.
    Awards any newly-earned badges and returns a list of their keys.
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

    # Award each candidate
    newly_awarded = []
    for badge_key, activity_id in candidates:
        if award_badge(user_id, badge_key, activity_id):
            newly_awarded.append(badge_key)

    return newly_awarded
