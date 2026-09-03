from datetime import datetime, date, timedelta
from db import get_db, IntegrityError
from services.badge_service import award_badge, BADGE_METADATA


def _this_month_range():
    today = date.today()
    start = today.replace(day=1)
    if today.month == 12:
        end_dt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        end_dt = today.replace(month=today.month + 1, day=1)
    end = end_dt - timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _build_challenges():
    month_start, month_end = _this_month_range()
    return [
        {
            "key": "MONTHLY_20KM",
            "name": "20K This Month",
            "description": "Run a total of 20 km within this calendar month.",
            "goal_type": "distance_km",
            "goal_value": 20.0,
            "start_date": month_start,
            "end_date": month_end,
            "reward_badge_key": "TOTAL_50KM",
            "icon": "fas fa-map-marked-alt",
        },
        {
            "key": "MONTHLY_50KM",
            "name": "50K Month",
            "description": "Run a total of 50 km within this calendar month.",
            "goal_type": "distance_km",
            "goal_value": 50.0,
            "start_date": month_start,
            "end_date": month_end,
            "reward_badge_key": "TOTAL_100KM",
            "icon": "fas fa-route",
        },
        {
            "key": "MONTHLY_10RUNS",
            "name": "10 Runs This Month",
            "description": "Log 10 runs within this calendar month.",
            "goal_type": "run_count",
            "goal_value": 10,
            "start_date": month_start,
            "end_date": month_end,
            "reward_badge_key": "STREAK_7DAY",
            "icon": "fas fa-shoe-prints",
        },
        {
            "key": "MONTHLY_LONG_RUN",
            "name": "Long Run Month",
            "description": "Complete a single run of 15 km or more this month.",
            "goal_type": "single_distance_km",
            "goal_value": 15.0,
            "start_date": month_start,
            "end_date": month_end,
            "reward_badge_key": "FIRST_10K",
            "icon": "fas fa-running",
        },
    ]


CHALLENGES = _build_challenges()


def get_active_challenges():
    today_str = date.today().strftime("%Y-%m-%d")
    return [c for c in CHALLENGES if c["start_date"] <= today_str <= c["end_date"]]


def _compute_progress(conn, user_id, challenge):
    goal_type = challenge["goal_type"]
    start_date = challenge["start_date"]
    end_date = challenge["end_date"]
    if goal_type == "distance_km":
        row = conn.execute(
            "SELECT COALESCE(SUM(distance_km), 0.0) AS progress FROM runs "
            "WHERE user_id = ? AND date >= ? AND date <= ?",
            (user_id, start_date, end_date),
        ).fetchone()
        return float(row["progress"])
    elif goal_type == "run_count":
        row = conn.execute(
            "SELECT COUNT(*) AS progress FROM runs "
            "WHERE user_id = ? AND date >= ? AND date <= ?",
            (user_id, start_date, end_date),
        ).fetchone()
        return float(row["progress"])
    elif goal_type == "single_distance_km":
        row = conn.execute(
            "SELECT COALESCE(MAX(distance_km), 0.0) AS progress FROM runs "
            "WHERE user_id = ? AND date >= ? AND date <= ?",
            (user_id, start_date, end_date),
        ).fetchone()
        return float(row["progress"])
    return 0.0


def evaluate_challenges_for_user(user_id, run_id=None):
    active = get_active_challenges()
    if not active:
        return []
    conn = get_db()
    newly_completed = []
    try:
        for challenge in active:
            key = challenge["key"]
            goal_value = float(challenge["goal_value"])
            current_progress = _compute_progress(conn, user_id, challenge)
            existing = conn.execute(
                "SELECT current_progress, completed_at FROM user_challenge_progress "
                "WHERE user_id = ? AND challenge_key = ?",
                (user_id, key),
            ).fetchone()
            already_completed = existing and existing["completed_at"] is not None
            completed_at = None
            if current_progress >= goal_value and not already_completed:
                completed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                newly_completed.append(key)
            if existing:
                conn.execute(
                    "UPDATE user_challenge_progress "
                    "SET current_progress = ?, completed_at = COALESCE(completed_at, ?) "
                    "WHERE user_id = ? AND challenge_key = ?",
                    (current_progress, completed_at, user_id, key),
                )
            else:
                try:
                    conn.execute(
                        "INSERT INTO user_challenge_progress "
                        "(user_id, challenge_key, current_progress, completed_at) "
                        "VALUES (?, ?, ?, ?)",
                        (user_id, key, current_progress, completed_at),
                    )
                except IntegrityError:
                    conn.execute(
                        "UPDATE user_challenge_progress "
                        "SET current_progress = ?, completed_at = COALESCE(completed_at, ?) "
                        "WHERE user_id = ? AND challenge_key = ?",
                        (current_progress, completed_at, user_id, key),
                    )
        conn.commit()
    finally:
        conn.close()
    # Award reward badges outside the DB transaction
    for key in newly_completed:
        ch = next((c for c in CHALLENGES if c["key"] == key), None)
        if ch and ch.get("reward_badge_key"):
            award_badge(user_id, ch["reward_badge_key"])
    return newly_completed


def reset_challenge_progress(user_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE user_challenge_progress SET current_progress = 0.0, completed_at = NULL WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_challenge_progress(user_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM user_challenge_progress WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_user_challenges(user_id):
    active = get_active_challenges()
    if not active:
        return []
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT challenge_key, current_progress, completed_at "
            "FROM user_challenge_progress WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    progress_map = {r["challenge_key"]: r for r in rows}
    result = []
    for c in active:
        key = c["key"]
        prog_row = progress_map.get(key)
        current_progress = float(prog_row["current_progress"]) if prog_row else 0.0
        completed_at = prog_row["completed_at"] if prog_row else None
        goal_value = float(c["goal_value"])
        percent = min(100, int(current_progress / goal_value * 100)) if goal_value > 0 else 0
        reward_key = c.get("reward_badge_key", "")
        reward_meta = BADGE_METADATA.get(reward_key, {})
        result.append({
            "key": key,
            "name": c["name"],
            "description": c["description"],
            "goal_type": c["goal_type"],
            "goal_value": goal_value,
            "start_date": c["start_date"],
            "end_date": c["end_date"],
            "icon": c["icon"],
            "current_progress": round(current_progress, 2),
            "percent_complete": percent,
            "completed": completed_at is not None,
            "completed_at": completed_at,
            "reward_badge_key": reward_key,
            "reward_badge_name": reward_meta.get("name", ""),
            "reward_badge_icon": reward_meta.get("icon", ""),
        })
    return result
