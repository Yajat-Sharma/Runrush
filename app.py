import sqlite3
import csv
import io
import os
import hashlib
from flask import Flask, render_template, request, redirect, session, url_for, make_response, flash, jsonify
from datetime import date, datetime, timedelta

app = Flask(__name__)
# ... (rest of imports)
app.secret_key = "super-secret-key-change-this"  # needed for sessions

DEFAULT_WEIGHT = 0.0   # used if user hasn't set weight yet


# ----------------- DB HELPERS -----------------

def get_db():
    conn = sqlite3.connect("runs.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pin TEXT NOT NULL
        )
    """)

    # add new columns if they don't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN weight REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN weekly_goal_km REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN theme TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN height REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    except sqlite3.OperationalError:
        pass

    # Add created_at to runs table for locking
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass
    
    # Add insight column for AI-generated run insights
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN insight TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Create edit_history table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            edited_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES runs(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # runs table, linked to user
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            distance_km REAL NOT NULL,
            time_min REAL NOT NULL,
            pace REAL NOT NULL,
            calories REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # activity logs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # admin notes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_user_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (target_user_id) REFERENCES users(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
# Make sure DB/tables exist when app starts (for Render / gunicorn)
with app.app_context():
    init_db()



def calc_stats(distance_km, time_min, weight_kg):
    pace = time_min / distance_km
    calories = weight_kg * distance_km
    return round(pace, 2), round(calories, 0)


def format_time_min(minutes):
    total_seconds = int(round(minutes * 60))
    m = total_seconds // 60
    s = total_seconds % 60
    return f"{m}m {s:02d}s"


def require_login():
    return "user_id" in session


def get_current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


def get_user_role(user):
    """
    Returns 'admin', 'moderator', or 'user'.
    Checks ENV variable for Super Admin first.
    """
    if not user:
        return None
    
    # Super Admin Check
    admin_id = os.environ.get("ADMIN_USER_ID")
    if str(user["id"]) == str(admin_id):
        return "admin"
    
    # DB Role Check
    return user["role"] if user["role"] in ["admin", "moderator"] else "user"


def log_activity(user_id, action, details=None):
    try:
        conn = get_db()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now_str)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if 'conn' in locals():
            conn.close()


def generate_run_insight(user_id, distance, pace, calories):
    """
    Generate a friendly, motivational 1-2 line insight about the run.
    Analyzes performance vs user's history and provides encouraging feedback.
    """
    import random
    
    conn = get_db()
    
    # Get user's recent stats (last 30 days)
    recent_runs = conn.execute("""
        SELECT distance_km, pace, calories 
        FROM runs 
        WHERE user_id = ? 
        AND date >= date('now', '-30 days')
        ORDER BY date DESC
        LIMIT 10
    """, (user_id,)).fetchall()
    
    conn.close()
    
    # If this is first run or very few runs
    if len(recent_runs) <= 1:
        return random.choice([
            "Great start! Every journey begins with a single step 🏃",
            "Welcome to your running journey! Keep it up 💪",
            "First run logged! This is just the beginning 🔥",
            "Awesome! You've taken the first step toward your goals 🎯"
        ])
    
    # Calculate averages from recent runs (excluding current one)
    avg_pace = sum(r["pace"] for r in recent_runs[1:]) / len(recent_runs[1:])
    avg_distance = sum(r["distance_km"] for r in recent_runs[1:]) / len(recent_runs[1:])
    
    insights = []
    
    # Pace analysis
    if pace < avg_pace * 0.95:  # 5% faster
        insights.append("You beat your average pace! 🔥")
    elif pace < avg_pace:
        insights.append("Solid pace today! 👏")
    elif pace > avg_pace * 1.1:  # 10% slower
        insights.append("Pace was slower today — try starting easier next time 🏃")
    
    # Distance milestones
    if distance >= 5 and distance < 5.5:
        insights.append("You hit 5K! Great milestone 🎉")
    elif distance >= 10 and distance < 10.5:
        insights.append("Double digits! 10K completed 🏆")
    elif distance > avg_distance * 1.2:  # 20% longer
        insights.append("Longest run in a while! Keep pushing 💪")
    elif distance > avg_distance:
        insights.append("You went further than usual today!")
    
    # Consistency praise
    if len(recent_runs) >= 5:
        insights.append("Great consistency this month!")
    
    # Return insight or default
    if insights:
        return " ".join(insights[:2])  # Max 2 insights
    
    # Default encouraging messages
    return random.choice([
        "Another run in the books! Keep it up 🏃",
        "Consistent effort pays off. Well done! 💪",
        "Every run counts. Great work today! 🔥",
        "You showed up and that's what matters! 👏"
    ])



def is_run_locked(run):
    """Check if run is locked (>24h old)"""
    if not run.get('created_at'):
        return False  # Legacy runs without created_at are not locked
    
    try:
        created = datetime.strptime(run['created_at'], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        age_hours = (now - created).total_seconds() / 3600
        return age_hours > 24
    except (ValueError, TypeError):
        return False


def can_edit_run(run, user):
    """Check if user can edit this run"""
    # Admin/moderator override
    if get_user_role(user) in ['admin', 'moderator']:
        return True
    
    # Owner check
    if run['user_id'] != user['id']:
        return False
    
    # Lock check
    return not is_run_locked(run)


def log_edit_history(run_id, user_id, changes):
    """Log all field changes to edit_history table"""
    if not changes:
        return
    
    conn = get_db()
    try:
        for field, (old_val, new_val) in changes.items():
            conn.execute(
                """
                INSERT INTO edit_history (run_id, user_id, field_name, old_value, new_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, user_id, field, str(old_val), str(new_val))
            )
        conn.commit()
    finally:
        conn.close()


# ----------------- BADGE SYSTEM -----------------

def evaluate_badges_for_user(user_id, last_run_id=None):
    """
    Evaluate all badge criteria for a user after a run is added.
    Returns list of newly awarded badge keys.
    """
    conn = get_db()
    
    # Get user stats
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?", 
        (user_id,)
    ).fetchone()
    
    if not stats:
        # Initialize stats if first run
        stats = initialize_user_stats(user_id)
    
    # Get the last run details if provided
    last_run = None
    if last_run_id:
        last_run = conn.execute(
            "SELECT * FROM runs WHERE id = ?", 
            (last_run_id,)
        ).fetchone()
    
    # Evaluate all badge types
    badges_to_award = []
    
    # 1. SINGLE_DISTANCE badges
    if last_run:
        if last_run['distance_km'] >= 5.0 and last_run['distance_km'] < 7.0:
            badges_to_award.append(('FIRST_5K', last_run_id))
        if last_run['distance_km'] >= 10.0:
            badges_to_award.append(('FIRST_10K', last_run_id))
    
    # 2. ACCUMULATIVE_DISTANCE badges
    if stats['total_distance_km'] >= 50.0:
        badges_to_award.append(('TOTAL_50KM', None))
    
    if stats['total_distance_km'] >= 100.0:
        badges_to_award.append(('TOTAL_100KM', None))
    
    # 3. STREAK badges
    if stats['current_streak'] >= 7:
        badges_to_award.append(('STREAK_7DAY', None))
    
    if stats['current_streak'] >= 30:
        badges_to_award.append(('STREAK_30DAY', None))
    
    # Award badges (with duplicate prevention via UNIQUE constraint)
    newly_awarded = []
    for badge_key, activity_id in badges_to_award:
        awarded = award_badge(user_id, badge_key, activity_id)
        if awarded:
            newly_awarded.append(badge_key)
    
    conn.close()
    return newly_awarded


def award_badge(user_id, badge_key, activity_id=None):
    """
    Award a badge to a user. Returns True if newly awarded, False if already exists.
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
        conn.close()
        return True  # Newly awarded
    except sqlite3.IntegrityError:
        # Badge already exists (UNIQUE constraint violation)
        conn.close()
        return False


def update_user_stats(user_id, run_date_str, distance_km, operation='add'):
    """
    Incrementally update user stats when a run is added or deleted.
    
    Args:
        operation: 'add' or 'delete'
    """
    conn = get_db()
    
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?", 
        (user_id,)
    ).fetchone()
    
    if not stats:
        stats = initialize_user_stats(user_id)
        stats = conn.execute(
            "SELECT * FROM user_stats WHERE user_id = ?", 
            (user_id,)
        ).fetchone()
    
    # Update total distance
    if operation == 'add':
        new_total = stats['total_distance_km'] + distance_km
    else:  # delete
        new_total = max(0, stats['total_distance_km'] - distance_km)
    
    # Recalculate streak (always recalculate to ensure accuracy)
    current_streak, best_streak = calculate_streak_for_user(user_id)
    
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    conn.execute(
        """
        UPDATE user_stats
        SET total_distance_km = ?,
            current_streak = ?,
            best_streak = ?,
            last_activity_date = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (new_total, current_streak, best_streak, run_date_str, now_str, user_id)
    )
    conn.commit()
    conn.close()


def calculate_streak_for_user(user_id):
    """
    Calculate current and best streak for a user.
    Returns: (current_streak, best_streak)
    """
    conn = get_db()
    
    # Get all unique activity dates, sorted
    runs = conn.execute(
        "SELECT DISTINCT date FROM runs WHERE user_id = ? ORDER BY date ASC",
        (user_id,)
    ).fetchall()
    
    if not runs:
        conn.close()
        return 0, 0
    
    all_dates = [datetime.strptime(r['date'], "%Y-%m-%d").date() for r in runs]
    today = date.today()
    
    # Calculate current streak (backward from today)
    current_streak = 0
    day_pointer = today
    
    while day_pointer in all_dates:
        current_streak += 1
        day_pointer = day_pointer - timedelta(days=1)
    
    # Calculate best streak
    best_streak = 0
    streak = 1
    for i in range(1, len(all_dates)):
        if all_dates[i] == all_dates[i-1] + timedelta(days=1):
            streak += 1
        else:
            best_streak = max(best_streak, streak)
            streak = 1
    best_streak = max(best_streak, streak)
    
    conn.close()
    return current_streak, best_streak


def initialize_user_stats(user_id):
    """Create initial stats record for a user."""
    conn = get_db()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        conn.execute(
            """
            INSERT INTO user_stats (user_id, total_distance_km, current_streak, best_streak, updated_at)
            VALUES (?, 0.0, 0, 0, ?)
            """,
            (user_id, now_str)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Stats already exist
        pass
    
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    
    conn.close()
    return stats


# ----------------- ROUTES -----------------


@app.route("/")
def home_redirect():
    if not require_login():
        return redirect(url_for("login"))
    return redirect(url_for("index"))


@app.route("/dashboard", methods=["GET"])
def index():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    username = user["username"]
    display_name = user["display_name"] or username
    user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT

        # ---- BMI CALCULATION (uses actual stored weight + height) ----
    raw_weight = user["weight"]
    raw_height = user["height"] if "height" in user.keys() else None

    bmi_value = None
    bmi_status = None

    try:
        if raw_weight is not None and raw_height is not None:
            w = float(raw_weight)
            h_cm = float(raw_height)
            if h_cm > 0:
                h_m = h_cm / 100.0
                bmi_value = round(w / (h_m * h_m), 1)

                if bmi_value < 18.5:
                    bmi_status = "Underweight"
                elif bmi_value < 25:
                    bmi_status = "Normal"
                elif bmi_value < 30:
                    bmi_status = "Overweight"
                else:
                    bmi_status = "Obese"
    except (TypeError, ValueError):
        bmi_value = None
        bmi_status = None

    # theme from DB (fallback dark)
    theme = user["theme"] or "dark"

    # --- read sort + filter from query params ---
    sort_by = request.args.get("sort", "date")      # date | distance | time
    filter_opt = request.args.get("filter", "all")  # all | last7 | month | 5k10k

    conn = get_db()

    # --- base query with sorting ---
    base_query = "SELECT * FROM runs WHERE user_id = ?"
    if sort_by == "distance":
        order_clause = " ORDER BY distance_km DESC, date DESC"
    elif sort_by == "time":
        order_clause = " ORDER BY time_min DESC, date DESC"
    else:  # default = date
        order_clause = " ORDER BY date DESC, id DESC"

    runs = conn.execute(base_query + order_clause, (user["id"],)).fetchall()

    # ---- All-time stats (use ALL runs) ----
    total_km = sum(r["distance_km"] for r in runs) if runs else 0
    total_cal = sum(r["calories"] for r in runs) if runs else 0
    avg_pace = (sum(r["pace"] for r in runs) / len(runs)) if runs else 0

    # ---- This month stats (use ALL runs) ----
    today = date.today()
    current_year = today.year
    current_month = today.month

    month_runs = []
    for r in runs:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if d.year == current_year and d.month == current_month:
                month_runs.append(r)
        except Exception:
            continue

    month_km = sum(r["distance_km"] for r in month_runs) if month_runs else 0
    month_cal = sum(r["calories"] for r in month_runs) if month_runs else 0
    month_avg_pace = (sum(r["pace"] for r in month_runs) / len(month_runs)) if month_runs else 0

    # ---- WEEKLY DISTANCE + GOAL PROGRESS ----
    week_start = today - timedelta(days=today.weekday())   # Monday
    week_end = week_start + timedelta(days=6)

    week_runs = []
    for r in runs:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if week_start <= d <= week_end:
                week_runs.append(r)
        except Exception:
            continue

    weekly_km = sum(r["distance_km"] for r in week_runs) if week_runs else 0.0

    weekly_goal = (
        user["weekly_goal_km"]
        if "weekly_goal_km" in user.keys() and user["weekly_goal_km"] is not None
        else None
    )

    if weekly_goal and weekly_goal > 0:
        weekly_remaining = max(weekly_goal - weekly_km, 0)
        weekly_progress_percent = min(100.0 * weekly_km / weekly_goal, 100.0)
    else:
        weekly_remaining = None
        weekly_progress_percent = 0.0

    # ---- Personal bests (use ALL runs) ----
    pb_5k_time = None
    pb_5k_pace = None
    pb_10k_time = None
    pb_10k_pace = None

    for r in runs:
        dist = r["distance_km"]
        t = r["time_min"]
        pace = r["pace"]

        # treat 4.5–5.5 km as 5K
        if 4.5 <= dist <= 5.5:
            if pb_5k_time is None or t < pb_5k_time:
                pb_5k_time = t
                pb_5k_pace = pace

        # treat 9–11 km as 10K
        if 9.0 <= dist <= 11.0:
            if pb_10k_time is None or t < pb_10k_time:
                pb_10k_time = t
                pb_10k_pace = pace

    pb_5k_time_str = format_time_min(pb_5k_time) if pb_5k_time is not None else None
    pb_10k_time_str = format_time_min(pb_10k_time) if pb_10k_time is not None else None

    # ---- FILTER for history table (not stats) ----
    filtered_runs = list(runs)

    if filter_opt == "last7":
        cutoff = today - timedelta(days=7)
        temp = []
        for r in runs:
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                if d >= cutoff:
                    temp.append(r)
            except Exception:
                continue
        filtered_runs = temp

    elif filter_opt == "month":
        filtered_runs = month_runs

    elif filter_opt == "5k10k":
        temp = []
        for r in runs:
            dist = r["distance_km"]
            if (4.5 <= dist <= 5.5) or (9.0 <= dist <= 11.0):
                temp.append(r)
        filtered_runs = temp

    # ---------- STREAK CALCULATION ----------
    all_dates = []
    for r in runs:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            all_dates.append(d)
        except Exception:
            pass

    if all_dates:
        all_dates = sorted(list(set(all_dates)))  # unique + sorted ASC

        # ---- CURRENT STREAK ----
        current_streak = 0
        day_pointer = today

        while day_pointer in all_dates:
            current_streak += 1
            day_pointer = day_pointer - timedelta(days=1)

        # ---- BEST STREAK ----
        best_streak = 0
        streak = 1
        for i in range(1, len(all_dates)):
            if all_dates[i] == all_dates[i-1] + timedelta(days=1):
                streak += 1
            else:
                best_streak = max(best_streak, streak)
                streak = 1
        best_streak = max(best_streak, streak)

        # ---- WEEKLY STREAK BAR (Mon–Sun) ----
        week_start = today - timedelta(days=today.weekday())   # Monday
        week_days = [week_start + timedelta(days=i) for i in range(7)]

        streak_bar = []
        for d in week_days:
            if d in all_dates:
                streak_bar.append("🔥")
            else:
                streak_bar.append("—")
    else:
        current_streak = 0
        best_streak = 0
        streak_bar = ["—"] * 7

    # ---- WEEKLY LEADERBOARD (Top 10) ----
    lb_start_str = week_start.strftime("%Y-%m-%d")
    lb_end_str = week_end.strftime("%Y-%m-%d")

    lb_query = """
        SELECT 
            u.username, 
            u.display_name, 
            COALESCE(SUM(r.distance_km), 0) as total_dist
        FROM users u
        JOIN runs r ON u.id = r.user_id
        WHERE r.date BETWEEN ? AND ?
        GROUP BY u.id
        HAVING total_dist > 0
        ORDER BY total_dist DESC
        LIMIT 10
    """
    
    lb_rows = conn.execute(lb_query, (lb_start_str, lb_end_str)).fetchall()
    
    weekly_leaderboard = []
    for row in lb_rows:
        weekly_leaderboard.append({
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "total_dist": row["total_dist"]
        })

    conn.close()

    return render_template(
        "index.html",
        theme=theme,
        runs=filtered_runs,              # history table uses filtered list
        total_km=round(total_km, 2),
        total_cal=round(total_cal, 0),
        avg_pace=round(avg_pace, 2),
        month_km=round(month_km, 2),
        month_cal=round(month_cal, 0),
        month_avg_pace=round(month_avg_pace, 2),
        pb_5k_time=pb_5k_time_str,
        pb_5k_pace=round(pb_5k_pace, 2) if pb_5k_pace is not None else None,
        pb_10k_time=pb_10k_time_str,
        pb_10k_pace=round(pb_10k_pace, 2) if pb_10k_pace is not None else None,
        weight=user_weight,
        username=username,
        display_name=display_name,
        active_sort=sort_by,
        active_filter=filter_opt,
        current_streak=current_streak,
        best_streak=best_streak,
        streak_bar=streak_bar,
        weekly_km=round(weekly_km, 1),
        weekly_goal=weekly_goal,
        weekly_remaining=round(weekly_remaining, 1) if weekly_remaining is not None else None,
        weekly_progress_percent=round(weekly_progress_percent, 1),
        bmi_status=bmi_status,
        today=today.strftime("%Y-%m-%d"),
        height=raw_height,
        weekly_leaderboard=weekly_leaderboard
    )


# ---------- ADD RUN ----------

@app.route("/add", methods=["POST"])
def add_run():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    date_str = request.form.get("date", "").strip()
    distance_str = request.form.get("distance", "").strip()
    time_str = request.form.get("time", "").strip()
    notes = request.form.get("notes", "").strip()

    # Validation: Date
    if date_str:
        try:
            run_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            today_date = datetime.now().date()
            if run_date > today_date:
                log_activity(user["id"], "VALIDATION_FAIL", f"Attempted future date: {date_str}")
                flash("You cannot log runs for future dates.", "danger")
                return redirect(url_for("index"))
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("index"))
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Validation: Distance (must be positive)
    try:
        distance = float(distance_str)
        if distance <= 0:
            log_activity(user["id"], "VALIDATION_FAIL", f"Invalid distance: {distance}")
            flash("Distance must be greater than 0 km.", "danger")
            return redirect(url_for("index"))
    except (ValueError, TypeError):
        flash("Invalid distance value.", "danger")
        return redirect(url_for("index"))

    # Validation: Duration (must be positive)
    try:
        time_min = float(time_str)
        if time_min <= 0:
            log_activity(user["id"], "VALIDATION_FAIL", f"Invalid duration: {time_min}")
            flash("Duration must be greater than 0 minutes.", "danger")
            return redirect(url_for("index"))
    except (ValueError, TypeError):
        flash("Invalid duration value.", "danger")
        return redirect(url_for("index"))

    # Validation: Pace (realistic check)
    pace_check = time_min / distance
    if pace_check > 30:  # Slower than 30 min/km (very slow walking)
        log_activity(user["id"], "VALIDATION_FAIL", f"Unrealistic pace (too slow): {pace_check:.2f} min/km")
        flash("Pace seems unrealistic. Please check your distance and time.", "danger")
        return redirect(url_for("index"))
    if pace_check < 2:  # Faster than 2 min/km (world record territory)
        log_activity(user["id"], "VALIDATION_FAIL", f"Unrealistic pace (too fast): {pace_check:.2f} min/km")
        flash("Pace seems too fast. Please check your distance and time.", "danger")
        return redirect(url_for("index"))


    user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT
    pace, calories = calc_stats(distance, time_min, user_weight)
    
    # Generate AI insight for this run
    insight = generate_run_insight(user["id"], distance, pace, calories)

    conn = get_db()
    # Insert run with created_at timestamp and insight
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        """
        INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, created_at, insight)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user["id"], date_str, distance, time_min, pace, calories, now_str, insight),
    )
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # ⭐ NEW: Update stats and evaluate badges
    update_user_stats(user["id"], date_str, distance, operation='add')
    newly_awarded = evaluate_badges_for_user(user["id"], run_id)
    
    # Store newly awarded badges in session for celebration modal
    if newly_awarded:
        session['new_badges'] = newly_awarded
    
    log_activity(user["id"], "RUN_ADDED", f"Added run: {distance}km in {time_min}min")

    return redirect(url_for("index"))




# ---------- SYNC OFFLINE RUN ----------

@app.route("/api/sync-run", methods=["POST"])
def sync_offline_run():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        
        # Extract data
        temp_id = data.get('tempId')
        date_str = data.get('date', '').strip()
        distance_str = str(data.get('distance', ''))
        time_str = str(data.get('time', ''))
        notes = data.get('notes', '').strip()
        client_hash = data.get('hash', '')
        
        # Validate required fields
        if not all([temp_id, date_str, distance_str, time_str]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Hash verification for data integrity
        server_hash_data = f"{date_str}{distance_str}{time_str}"
        server_hash = hashlib.sha256(server_hash_data.encode()).hexdigest()
        
        if client_hash and client_hash != server_hash:
            log_activity(user["id"], "SYNC_FAIL", f"Hash mismatch for {temp_id}")
            return jsonify({"error": "Data integrity check failed"}), 400
        
        # Parse and validate date
        try:
            run_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            today_date = datetime.now().date()
            if run_date > today_date:
                log_activity(user["id"], "SYNC_FAIL", f"Future date in {temp_id}: {date_str}")
                return jsonify({"error": "Cannot sync future-dated runs"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
        
        # Parse and validate distance
        try:
            distance = float(distance_str)
            if distance <= 0:
                log_activity(user["id"], "SYNC_FAIL", f"Invalid distance in {temp_id}: {distance}")
                return jsonify({"error": "Distance must be greater than 0"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid distance value"}), 400
        
        # Parse and validate time
        try:
            time_min = float(time_str)
            if time_min <= 0:
                log_activity(user["id"], "SYNC_FAIL", f"Invalid time in {temp_id}: {time_min}")
                return jsonify({"error": "Duration must be greater than 0"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid duration value"}), 400
        
        # Validate pace
        pace_check = time_min / distance
        if pace_check > 30:
            log_activity(user["id"], "SYNC_FAIL", f"Unrealistic pace in {temp_id}: {pace_check:.2f}")
            return jsonify({"error": "Pace too slow (> 30 min/km)"}), 400
        if pace_check < 2:
            log_activity(user["id"], "SYNC_FAIL", f"Unrealistic pace in {temp_id}: {pace_check:.2f}")
            return jsonify({"error": "Pace too fast (< 2 min/km)"}), 400
        
        # Check for duplicate run
        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM runs WHERE user_id = ? AND date = ? AND distance_km = ? AND time_min = ?",
            (user["id"], date_str, distance, time_min)
        ).fetchone()
        
        if existing:
            conn.close()
            log_activity(user["id"], "SYNC_DUPLICATE", f"Duplicate run detected: {temp_id}")
            return jsonify({"error": "Duplicate run detected"}), 409
        
        
        # Calculate stats
        user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT
        pace, calories = calc_stats(distance, time_min, user_weight)
        
        # Generate AI insight for this run
        insight = generate_run_insight(user["id"], distance, pace, calories)
        
        # Insert run with insight
        cursor = conn.execute(
            """
            INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, insight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user["id"], date_str, distance, time_min, pace, calories, insight)
        )
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # ⭐ Update stats and evaluate badges
        update_user_stats(user["id"], date_str, distance, operation='add')
        newly_awarded = evaluate_badges_for_user(user["id"], run_id)
        
        # Log successful sync
        log_activity(user["id"], "SYNC_SUCCESS", f"Synced offline run: {temp_id} -> {run_id}")
        
        return jsonify({
            "success": True,
            "runId": run_id,
            "insight": insight,
            "newBadges": newly_awarded,  # Include badges in response
            "message": "Run synced successfully"
        }), 200

        
    except Exception as e:
        log_activity(user["id"], "SYNC_ERROR", f"Sync exception: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# ---------- WEEKLY GOAL ----------

@app.route("/weekly-goal", methods=["POST"])
def weekly_goal():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    goal_str = request.form.get("weekly_goal", "").strip()
    try:
        goal_val = float(goal_str) if goal_str else None
    except ValueError:
        goal_val = None

    conn = get_db()
    conn.execute(
        "UPDATE users SET weekly_goal_km = ? WHERE id = ?",
        (goal_val, user["id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ---------- DELETE RUN ----------

@app.route("/delete/<int:run_id>", methods=["POST"])
def delete_run(run_id):
    if not require_login():
        return redirect(url_for("login"))

    conn = get_db()
    
    # Get run details before deletion
    run = conn.execute(
        "SELECT * FROM runs WHERE id = ? AND user_id = ?",
        (run_id, session["user_id"])
    ).fetchone()
    
    if run:
        conn.execute(
            "DELETE FROM runs WHERE id = ? AND user_id = ?",
            (run_id, session["user_id"]),
        )
        conn.commit()
        
        # ⭐ Update stats (but don't revoke badges - industry standard)
        update_user_stats(
            session["user_id"], 
            run['date'], 
            run['distance_km'], 
            operation='delete'
        )
    
    conn.close()
    return redirect(url_for("index"))



# ---------- SETTINGS ----------

@app.route("/settings", methods=["GET"])
def settings():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()

    return render_template(
        "settings.html",
        display_name=user["display_name"] or user["username"],
        username=user["username"],
        weight=user["weight"],
        height=user["height"],
        theme=user["theme"] or "dark"
    )

@app.route("/profile", methods=["POST"])
def update_profile():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    display_name = request.form.get("display_name")
    weight = request.form.get("weight")

    conn = get_db()
    conn.execute("""
        UPDATE users SET display_name = ?, weight = ?
        WHERE id = ?
    """, (display_name, weight, user["id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("index"))

@app.route("/settings/update", methods=["POST"])
def update_settings():
    if not require_login():
        return redirect(url_for("login"))

    theme = request.form.get("theme")
    display_name = request.form.get("display_name")
    weight = request.form.get("weight")
    height = request.form.get("height")   # ⭐ NEW

    user = get_current_user()

    conn = get_db()
    conn.execute("""
        UPDATE users
        SET theme = ?, display_name = ?, weight = ?, height = ?
        WHERE id = ?
    """, (theme, display_name, weight, height, user["id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("settings"))

#-------Delete acc-----#
@app.route("/delete-account", methods=["POST"])
def delete_account():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()

    # 1) Delete all runs for this user
    conn.execute("DELETE FROM runs WHERE user_id = ?", (user["id"],))

    # 2) Delete the user record
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))

    conn.commit()
    conn.close()

    # 3) Clear session and send back to login
    session.clear()
    return redirect(url_for("login"))

# ---------- EDIT RUN ---------

@app.route("/edit/<int:run_id>", methods=["GET", "POST"])
def edit_run(run_id):
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    run = conn.execute(
        "SELECT * FROM runs WHERE id = ? AND user_id = ?",
        (run_id, session["user_id"])
    ).fetchone()
    
    if not run:
        conn.close()
        return redirect(url_for("index"))
    
    # Handle POST request (update)
    if request.method == "POST":
        try:
            distance = float(request.form["distance"])
            time_min = float(request.form["time"])
            run_date = request.form.get("date")

            if distance <= 0 or time_min <= 0:
                conn.close()
                flash("Distance and time must be positive.", "danger")
                return redirect(url_for("edit_run", run_id=run_id))


            user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT
            pace, calories = calc_stats(distance, time_min, user_weight)
            
            # Regenerate insight with updated data
            insight = generate_run_insight(user["id"], distance, pace, calories)

            conn.execute("""
                UPDATE runs
                SET date = ?, distance_km = ?, time_min = ?, pace = ?, calories = ?, insight = ?
                WHERE id = ? AND user_id = ?
            """, (run_date, distance, time_min, pace, calories, insight, run_id, session["user_id"]))
            conn.commit()
            conn.close()
            flash("Run updated successfully!", "success")
            return redirect(url_for("index"))

        except (ValueError, TypeError):
            conn.close()
            flash("Invalid distance or time.", "danger")
            return redirect(url_for("edit_run", run_id=run_id))

    # Handle GET request (show form)
    conn.close()
    display_name = user["display_name"] or user["username"]
    user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT

    return render_template(
        "edit.html",
        run=run,
        weight=user_weight,
        username=user["username"],
        display_name=display_name,
        theme=user["theme"] or "dark"
    )


# ---------- EXPORT / LEADERBOARD ----------

@app.route("/export")
def export_runs():
    if not require_login():
        return redirect(url_for("login"))
    
    user = get_current_user()
    conn = get_db()
    runs = conn.execute(
        "SELECT date, distance_km, time_min, pace, calories FROM runs WHERE user_id = ? ORDER BY date DESC",
        (user["id"],)
    ).fetchall()
    conn.close()

    # Create CSV in memory
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Date", "Distance (km)", "Time (min)", "Pace (min/km)", "Calories"])
    for r in runs:
        cw.writerow([r["date"], r["distance_km"], r["time_min"], r["pace"], r["calories"]])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=run_history.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@app.route("/leaderboard")
def leaderboard():
    if not require_login():
        return redirect(url_for("login"))
    
    user = get_current_user()
    
    conn = get_db()
    # Rank by total distance
    # We join users and runs. If a user has no runs, they won't appear (or we can use LEFT JOIN if we want them to show with 0)
    # Let's use LEFT JOIN so everyone is included.
    query = """
        SELECT 
            u.username, 
            u.display_name, 
            COALESCE(SUM(r.distance_km), 0) as total_dist, 
            COALESCE(SUM(r.time_min), 0) as total_time
        FROM users u
        LEFT JOIN runs r ON u.id = r.user_id
        GROUP BY u.id
        ORDER BY total_dist DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    leaderboard_data = []
    for row in rows:
        leaderboard_data.append({
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "total_dist": round(row["total_dist"], 2),
            "total_time": round(row["total_time"], 1),
            "avg_pace": round(row["total_time"] / row["total_dist"], 2) if row["total_dist"] > 0 else 0
        })

    return render_template(
        "leaderboard.html",
        leaderboard=leaderboard_data,
        username=user["username"],
        display_name=user["display_name"] or user["username"],
        theme=user["theme"] or "dark"
    )


# ---------- AUTH ROUTES ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        pin = request.form["pin"].strip()

        if not username or not pin:
            return render_template("register.html", error="Username and PIN are required.")

        if len(pin) < 4 or not pin.isdigit():
            return render_template("register.html", error="Use a 4+ digit numeric PIN.")

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, pin) VALUES (?, ?)",
                (username, pin)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already taken.")
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        session["user_id"] = user["id"]
        session["username"] = username
        return redirect(url_for("onboarding"))

    return render_template("register.html")

#Onboarding program 

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    # If user already has basic data, don't keep showing onboarding
    if request.method == "GET":
        if (user["display_name"] is not None or user["weight"] is not None
                or user["weekly_goal_km"] is not None):
            return redirect(url_for("index"))

        return render_template(
            "onboarding.html",
            username=user["username"]
        )

    # POST: save onboarding data
    display_name = request.form.get("display_name", "").strip() or user["username"]
    weight_raw = request.form.get("weight", "").strip()
    weekly_goal_raw = request.form.get("weekly_goal", "").strip()

    try:
        weight = float(weight_raw) if weight_raw else None
    except ValueError:
        weight = None

    try:
        weekly_goal = float(weekly_goal_raw) if weekly_goal_raw else None
    except ValueError:
        weekly_goal = None

    conn = get_db()
    conn.execute("""
        UPDATE users
        SET display_name = ?, weight = ?, weekly_goal_km = ?
        WHERE id = ?
    """, (display_name, weight, weekly_goal, user["id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        pin = request.form["pin"].strip()

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND pin = ?",
            (username, pin)
        ).fetchone()
        conn.close()

        if not user:
            return render_template("login.html", error="Invalid username or PIN.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        # Check if blocked
        if user["status"] == "blocked":
            session.clear()
            return render_template("login.html", error="Your account has been blocked.")

        # Update last_login
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db()
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_str, user["id"]))
            conn.commit()
            conn.close()
            
            log_activity(user["id"], "LOGIN", "User logged in")
        except Exception:
            pass # Non-critical if fails
        
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/admin")
def admin_dashboard():
    if not require_login():
        return redirect(url_for("login"))
    
    user = get_current_user()
    role = get_user_role(user)
    
    if role not in ["admin", "moderator"]:
         return render_template("403.html"), 403

    conn = get_db()
    
    # Get all users
    users = conn.execute("SELECT * FROM users ORDER BY last_login DESC").fetchall()
    
    # Stats: Total Users
    total_users = len(users)
    
    # Stats: Active Users (last 7 days)
    cutoff = datetime.now() - timedelta(days=7)
    active_users = 0
    for u in users:
        if u["last_login"]:
            try:
                # Format match: YYYY-MM-DD HH:MM:SS
                if datetime.strptime(u["last_login"], "%Y-%m-%d %H:%M:%S") >= cutoff:
                    active_users += 1
            except:
                pass

    # Stats: Total KM (platform wide)
    total_km_row = conn.execute("SELECT SUM(distance_km) FROM runs").fetchone()
    total_km = round(total_km_row[0] or 0, 1)

    # Activity Logs (Limit 20)
    logs = conn.execute("""
        SELECT a.action, a.details, a.timestamp, u.username 
        FROM activity_logs a 
        LEFT JOIN users u ON a.user_id = u.id 
        ORDER BY a.id DESC LIMIT 20
    """).fetchall()

    conn.close()
    
    return render_template(
        "admin.html", 
        users=users, 
        role=role,
        total_users=total_users,
        active_users=active_users,
        total_km=total_km,
        logs=logs
    )


@app.route("/admin/user/<int:user_id>/<action>", methods=["POST"])
def admin_user_action(user_id, action):
    if not require_login():
        return redirect(url_for("login"))
        
    current_user = get_current_user()
    current_role = get_user_role(current_user)
    
    # Permissions
    if current_role not in ["admin", "moderator"]:
         return render_template("403.html"), 403
         
    # Moderators cannot delete
    if action == "delete" and current_role != "admin":
         return render_template("403.html"), 403

    conn = get_db()
    
    # Protect Super Admin from being touched
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target_user:
        target_role = get_user_role(target_user)
        # Cannot modify admins unless you are an admin
        # Ideally, Super Admin (ENV) shouldn't be touched by DB admins either, but simple logic for now:
        # Don't let moderators touch admins
        if target_role == "admin" and current_role != "admin":
             conn.close()
             return render_template("403.html"), 403
        
        # Super Admin Env Check (Immutable)
        admin_id_env = os.environ.get("ADMIN_USER_ID")
        if str(user_id) == str(admin_id_env):
             conn.close()
             # Flash message ideal here, but simpler to just redirect
             return redirect(url_for("admin_dashboard"))

        if action == "block":
            conn.execute("UPDATE users SET status = 'blocked' WHERE id = ?", (user_id,))
            log_activity(current_user["id"], "BLOCK_USER", f"Blocked user {target_user['username']}")
            flash(f"User {target_user['username']} has been blocked.", "warning")

        elif action == "unblock":
            conn.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
            log_activity(current_user["id"], "UNBLOCK_USER", f"Unblocked user {target_user['username']}")
            flash(f"User {target_user['username']} has been unblocked.", "success")

        elif action == "promote":
            # Only Admin can promote
            if current_role == "admin":
                conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
                log_activity(current_user["id"], "PROMOTE_USER", f"Promoted {target_user['username']} to admin")
                flash(f"User {target_user['username']} promoted to Admin.", "success")

        elif action == "demote":
            # Only Admin can demote
            if current_role == "admin":
                conn.execute("UPDATE users SET role = 'user' WHERE id = ?", (user_id,))
                log_activity(current_user["id"], "DEMOTE_USER", f"Demoted {target_user['username']} to user")
                flash(f"User {target_user['username']} demoted to User.", "info")
        
        elif action == "delete":
            # Delete runs then user
             conn.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
             conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
             log_activity(current_user["id"], "DELETE_USER", f"Deleted user {target_user['username']}")
             flash(f"User {target_user['username']} deleted permanently.", "danger")

        conn.commit()
    
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/api/progress-data")
def api_progress_data():
    if not require_login():
        return {"error": "Unauthorized"}, 401
    
    user = get_current_user()
    range_type = request.args.get("range", "week")  # week, month, year
    
    conn = get_db()
    now = datetime.now()
    
    if range_type == "week":
        # Last 7 days (Mon-Sun) - only up to today
        start_date = now - timedelta(days=now.weekday() + 7)  # Last Monday
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        data = [0.0] * 7
        
        runs = conn.execute(
            "SELECT date, SUM(distance_km) as total FROM runs WHERE user_id = ? AND date >= ? AND date <= ? GROUP BY date",
            (user["id"], start_date.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
        ).fetchall()
        
        for run in runs:
            run_date = datetime.strptime(run["date"], "%Y-%m-%d")
            # Only include dates up to today
            if run_date.date() <= now.date():
                day_index = run_date.weekday()
                if 0 <= day_index < 7:
                    data[day_index] = round(run["total"], 2)
    
    elif range_type == "month":
        # Current month daily - only up to today
        start_date = now.replace(day=1)
        days_in_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        num_days = days_in_month.day
        
        labels = [str(i) for i in range(1, num_days + 1)]
        data = [0.0] * num_days
        
        runs = conn.execute(
            "SELECT date, SUM(distance_km) as total FROM runs WHERE user_id = ? AND date >= ? AND date <= ? GROUP BY date",
            (user["id"], start_date.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
        ).fetchall()
        
        for run in runs:
            run_date = datetime.strptime(run["date"], "%Y-%m-%d")
            # Only include dates up to today
            if run_date.date() <= now.date():
                day_index = run_date.day - 1
                if 0 <= day_index < num_days:
                    data[day_index] = round(run["total"], 2)
    
    elif range_type == "year":
        # Current year monthly - only up to current month
        start_date = now.replace(month=1, day=1)
        labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        data = [0.0] * 12
        
        runs = conn.execute(
            "SELECT date, SUM(distance_km) as total FROM runs WHERE user_id = ? AND date >= ? AND date <= ? GROUP BY date",
            (user["id"], start_date.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
        ).fetchall()
        
        for run in runs:
            run_date = datetime.strptime(run["date"], "%Y-%m-%d")
            # Only include dates up to today
            if run_date.date() <= now.date():
                month_index = run_date.month - 1
                if 0 <= month_index < 12:
                    data[month_index] += run["total"]
        
        data = [round(d, 2) for d in data]
    
    else:
        conn.close()
        return {"error": "Invalid range"}, 400
    
    # Calculate stats
    total = sum(data)
    active_days = sum(1 for d in data if d > 0)
    average = round(total / active_days, 2) if active_days > 0 else 0
    best = max(data) if data else 0
    
    conn.close()
    
    return {
        "labels": labels,
        "data": data,
        "stats": {
            "total": round(total, 2),
            "average": average,
            "best": best,
            "active_days": active_days
        }
    }


# ---------- BADGE API ENDPOINTS ----------

@app.route("/api/badges", methods=["GET"])
def get_badges():
    """
    Returns all badges with unlock status for the current user.
    """
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    conn = get_db()
    
    # Get all badge definitions
    badges = conn.execute("SELECT * FROM badges ORDER BY criteria_value ASC").fetchall()
    
    # Get user's unlocked badges
    unlocked = conn.execute(
        "SELECT badge_key, unlocked_at FROM user_badges WHERE user_id = ?",
        (user["id"],)
    ).fetchall()
    unlocked_keys = {b['badge_key']: b['unlocked_at'] for b in unlocked}
    
    # Get user stats for progress calculation
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user["id"],)
    ).fetchone()
    
    conn.close()
    
    result = []
    for badge in badges:
        is_unlocked = badge['key'] in unlocked_keys
        
        # Calculate progress
        progress = 0
        target = badge['criteria_value']
        current = 0
        
        if badge['criteria_type'] == 'ACCUMULATIVE_DISTANCE':
            current = stats['total_distance_km'] if stats else 0
            progress = min(100, (current / target) * 100) if target > 0 else 0
        elif badge['criteria_type'] == 'STREAK':
            current = stats['current_streak'] if stats else 0
            progress = min(100, (current / target) * 100) if target > 0 else 0
        elif badge['criteria_type'] == 'SINGLE_DISTANCE':
            # For single-distance badges, it's either 0% or 100%
            progress = 100 if is_unlocked else 0
            current = target if is_unlocked else 0
        
        result.append({
            'key': badge['key'],
            'name': badge['name'],
            'description': badge['description'],
            'icon_url': badge['icon_url'],
            'is_unlocked': is_unlocked,
            'unlocked_at': unlocked_keys.get(badge['key']),
            'progress': round(progress, 1),
            'current': round(current, 1),
            'target': target,
            'criteria_type': badge['criteria_type']
        })
    
    return jsonify({'badges': result}), 200


@app.route("/api/badges/progress", methods=["GET"])
def get_badge_progress():
    """
    Returns compact progress data for UI progress bars.
    """
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    conn = get_db()
    
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user["id"],)
    ).fetchone()
    
    conn.close()
    
    if not stats:
        return jsonify({
            'total_distance': 0,
            'current_streak': 0,
            'best_streak': 0
        }), 200
    
    return jsonify({
        'total_distance': stats['total_distance_km'],
        'current_streak': stats['current_streak'],
        'best_streak': stats['best_streak']
    }), 200


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- RUN APP ----------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

