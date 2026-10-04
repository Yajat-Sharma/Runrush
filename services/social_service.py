"""
Social service - activity feed, likes, follow lists, runner suggestions and
social notifications (new follower, run liked, friend just ran).
"""

from datetime import datetime, timedelta, date

from db import get_db, IntegrityError

FEED_WINDOW_HOURS = 24
FEED_LIMIT = 50
TOP_RUNS_COUNT = 3
SUGGESTION_LIMIT = 8
ALL_RUNNERS_LIMIT = 500


def _display_name(user):
    return user["display_name"] or user["username"]


def _parse_ts(value):
    """created_at is stored as text ('YYYY-MM-DD HH:MM:SS', maybe with fractions/tz)."""
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------

def get_activity_feed(viewer_id, now=None):
    """
    Runs logged by anyone in the last 24 hours, most-liked first (newest first
    among equal likes), plus the ids of the top 3 liked runs. Old runs that were
    bulk-imported recently are excluded by also requiring a recent run date.
    """
    now = now or datetime.now()
    cutoff = (now - timedelta(hours=FEED_WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    min_run_date = (now.date() - timedelta(days=2)).isoformat()

    conn = get_db()
    rows = conn.execute(
        """
        SELECT r.id, r.date, r.distance_km, r.time_min, r.pace, r.run_type, r.created_at,
               u.id AS user_id, u.username, u.display_name, u.profile_emoji,
               CASE WHEN u.avatar_image IS NOT NULL THEN 1 ELSE 0 END AS has_avatar,
               (SELECT COUNT(*) FROM run_likes l WHERE l.run_id = r.id) AS like_count,
               (SELECT COUNT(*) FROM run_likes l WHERE l.run_id = r.id AND l.user_id = ?) AS liked,
               (SELECT COUNT(*) FROM friends f WHERE f.follower_id = ? AND f.followed_id = u.id) AS following
        FROM runs r
        JOIN users u ON u.id = r.user_id
        WHERE r.created_at >= ? AND r.date >= ?
          AND COALESCE(u.status, 'active') = 'active'
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT ?
        """,
        (viewer_id, viewer_id, cutoff, min_run_date, FEED_LIMIT),
    ).fetchall()
    conn.close()

    runs = []
    for r in rows:
        logged_at = _parse_ts(r["created_at"])
        minutes_ago = max(0, int((now - logged_at).total_seconds() // 60)) if logged_at else None
        runs.append({
            "id": r["id"],
            "date": str(r["date"])[:10],
            "distance_km": round(float(r["distance_km"]), 2),
            "time_min": round(float(r["time_min"]), 2),
            "pace": round(float(r["pace"]), 2) if r["pace"] else None,
            "run_type": r["run_type"] or "easy",
            "minutes_ago": minutes_ago,
            "username": r["username"],
            "display_name": r["display_name"] or r["username"],
            "profile_emoji": r["profile_emoji"] or "🏃🏻",
            "has_avatar": bool(r["has_avatar"]),
            "like_count": int(r["like_count"]),
            "liked": bool(r["liked"]),
            "is_own": r["user_id"] == viewer_id,
            "following": bool(r["following"]),
        })

    # Most-liked first; newest first among equal likes (rows are already newest-first, sort is stable)
    runs.sort(key=lambda r: -r["like_count"])
    top = [r for r in runs if r["like_count"] > 0][:TOP_RUNS_COUNT]

    return {"runs": runs, "top_run_ids": [r["id"] for r in top]}


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

def set_run_like(actor, run_id, liked):
    """
    Like or unlike a run (idempotent). Returns (like_count, liked) or None if
    the run doesn't exist. The runner is notified the first time a like lands.
    """
    conn = get_db()
    run = conn.execute(
        "SELECT id, user_id, distance_km FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    if not run:
        conn.close()
        return None

    newly_liked = False
    if liked:
        try:
            conn.execute(
                "INSERT INTO run_likes (run_id, user_id, created_at) VALUES (?, ?, ?)",
                (run_id, actor["id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            newly_liked = True
        except IntegrityError:
            conn.rollback()  # already liked
    else:
        conn.execute(
            "DELETE FROM run_likes WHERE run_id = ? AND user_id = ?", (run_id, actor["id"])
        )
        conn.commit()

    like_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM run_likes WHERE run_id = ?", (run_id,)
    ).fetchone()["cnt"]

    if newly_liked and run["user_id"] != actor["id"]:
        _notify(
            conn, [run["user_id"]], actor["id"], "LIKE",
            "New like ❤️",
            f"{_display_name(actor)} liked your {float(run['distance_km']):.2f} km run.",
        )
    conn.close()
    return int(like_count), liked


# ---------------------------------------------------------------------------
# Follow lists & suggestions
# ---------------------------------------------------------------------------

def get_follow_list(target_username, which, viewer_id):
    """People who follow `target_username` (which='followers') or whom they follow ('following')."""
    conn = get_db()
    target = conn.execute(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND COALESCE(status, 'active') = 'active'",
        (target_username,),
    ).fetchone()
    if not target:
        conn.close()
        return None

    join_col, filter_col = ("follower_id", "followed_id") if which == "followers" else ("followed_id", "follower_id")
    rows = conn.execute(
        f"""
        SELECT u.id, u.username, u.display_name, u.profile_emoji,
               CASE WHEN u.avatar_image IS NOT NULL THEN 1 ELSE 0 END AS has_avatar,
               (SELECT COUNT(*) FROM friends v WHERE v.follower_id = ? AND v.followed_id = u.id) AS following
        FROM friends f
        JOIN users u ON u.id = f.{join_col}
        WHERE f.{filter_col} = ? AND COALESCE(u.status, 'active') = 'active'
        ORDER BY f.created_at DESC
        """,
        (viewer_id or 0, target["id"]),
    ).fetchall()
    conn.close()
    return [_person(r, viewer_id) for r in rows]


def get_suggested_runners(viewer_id):
    """Active runners (ran in the last 30 days) the viewer doesn't follow yet, most active first."""
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.profile_emoji,
               CASE WHEN u.avatar_image IS NOT NULL THEN 1 ELSE 0 END AS has_avatar,
               COALESCE(SUM(r.distance_km), 0) AS recent_km,
               COUNT(r.id) AS recent_runs,
               COALESCE(MAX(us.current_streak), 0) AS current_streak
        FROM users u
        JOIN runs r ON r.user_id = u.id AND r.date >= ?
        LEFT JOIN user_stats us ON us.user_id = u.id
        WHERE u.id != ?
          AND COALESCE(u.status, 'active') = 'active'
          AND u.id NOT IN (SELECT followed_id FROM friends WHERE follower_id = ?)
        GROUP BY u.id
        ORDER BY (COALESCE(SUM(r.distance_km), 0) * 2 + COUNT(r.id) * 5
                  + COALESCE(MAX(us.current_streak), 0) * 10) DESC
        LIMIT ?
        """,
        (cutoff, viewer_id, viewer_id, SUGGESTION_LIMIT),
    ).fetchall()
    conn.close()
    return [
        {**_person(r, viewer_id), "recent_km": round(float(r["recent_km"]), 1),
         "recent_runs": int(r["recent_runs"]), "current_streak": int(r["current_streak"])}
        for r in rows
    ]


def get_all_runners(viewer_id):
    """Every active runner except the viewer, most active (last 30 days) first, with follow state."""
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.profile_emoji,
               CASE WHEN u.avatar_image IS NOT NULL THEN 1 ELSE 0 END AS has_avatar,
               COALESCE(SUM(r.distance_km), 0) AS recent_km,
               COUNT(r.id) AS recent_runs,
               (SELECT COUNT(*) FROM friends f WHERE f.follower_id = ? AND f.followed_id = u.id) AS following
        FROM users u
        LEFT JOIN runs r ON r.user_id = u.id AND r.date >= ?
        WHERE u.id != ? AND COALESCE(u.status, 'active') = 'active'
        GROUP BY u.id
        ORDER BY COALESCE(SUM(r.distance_km), 0) DESC, LOWER(u.username)
        LIMIT ?
        """,
        (viewer_id, cutoff, viewer_id, ALL_RUNNERS_LIMIT),
    ).fetchall()
    conn.close()
    return [
        {**_person(r, viewer_id), "recent_km": round(float(r["recent_km"]), 1),
         "recent_runs": int(r["recent_runs"])}
        for r in rows
    ]


def _person(row, viewer_id):
    return {
        "username": row["username"],
        "display_name": row["display_name"] or row["username"],
        "profile_emoji": row["profile_emoji"] or "🏃🏻",
        "has_avatar": bool(row["has_avatar"]),
        "following": bool(row["following"]) if "following" in row.keys() else False,
        "is_self": row["id"] == viewer_id,
    }


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def notify_new_follower(actor, target_id):
    conn = get_db()
    _notify(conn, [target_id], actor["id"], "FOLLOW",
            "New follower 👋", f"{_display_name(actor)} started following you.")
    conn.close()


def notify_followers_of_run(actor, distance_km, run_date):
    """Tell the runner's followers they just ran — skipped for back-dated runs."""
    try:
        run_day = datetime.strptime(str(run_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return
    if run_day < date.today() - timedelta(days=1):
        return

    conn = get_db()
    follower_ids = [
        r["follower_id"] for r in conn.execute(
            "SELECT follower_id FROM friends WHERE followed_id = ?", (actor["id"],)
        ).fetchall()
    ]
    _notify(conn, follower_ids, actor["id"], "FRIEND_RUN",
            f"🏃 {_display_name(actor)} just ran",
            f"{_display_name(actor)} logged {float(distance_km):.2f} km. Your turn — keep your streak alive!")
    conn.close()


def _notify(conn, user_ids, created_by, notif_type, title, message):
    """One notification row delivered to each of `user_ids`. Never raises."""
    if not user_ids:
        return
    try:
        notif_id = conn.execute(
            "INSERT INTO notifications (title, message, type, created_by, audience_type) "
            "VALUES (?, ?, ?, ?, ?) RETURNING id",
            (title, message, notif_type, created_by, "SPECIFIC_USER"),
        ).fetchone()["id"]
        for uid in set(user_ids):
            conn.execute(
                "INSERT INTO user_notifications (notification_id, user_id) VALUES (?, ?)",
                (notif_id, uid),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[social] notification ({notif_type}) failed: {e}")
