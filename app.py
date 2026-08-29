import csv
import io
import os
import re
import hashlib
import click

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, redirect, session, url_for, make_response, flash, jsonify
from datetime import date, datetime, timedelta
from db import get_db, IntegrityError, USE_PG
from extensions import csrf, limiter, bcrypt
from authlib.integrations.flask_client import OAuth

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = Flask(__name__)

# SECRET_KEY must come from the environment in production.
# Fail loudly at startup if it is missing or still set to the known placeholder.
_KNOWN_INSECURE_KEYS = {
    "super-secret-key-change-this",
    "dev-secret-key-change-in-production",
    "changeme",
    "",
}
_secret = os.environ.get("SECRET_KEY", "")
if not _secret or _secret in _KNOWN_INSECURE_KEYS:
    # Allow insecure key only in explicit testing/dev modes
    if os.environ.get("FLASK_ENV") in ("production", None) and not os.environ.get("TESTING"):
        raise RuntimeError(
            "[RunRush] SECRET_KEY is missing or is a known insecure placeholder. "
            "Set a strong SECRET_KEY environment variable before starting the app."
        )
    # Fallback for local dev / test runs
    _secret = _secret or "dev-secret-key-change-in-production"
app.secret_key = _secret

# Wire up Flask extensions
csrf.init_app(app)
limiter.init_app(app)
bcrypt.init_app(app)

oauth = OAuth(app)
if os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"):
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

DEFAULT_WEIGHT = 0.0   # used if user hasn't set weight yet


# ----------------- DB HELPERS -----------------



def init_db():
    conn = get_db()

    if USE_PG:
        print("[RunRush DB] Connected to PostgreSQL. Persistent storage is ACTIVE.")
        # ---- PostgreSQL DDL (all columns from the start) ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                pin TEXT NOT NULL,
                display_name TEXT,
                weight REAL,
                weekly_goal_km REAL,
                theme TEXT,
                height REAL,
                last_login TEXT,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'active'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                date TEXT NOT NULL,
                distance_km REAL NOT NULL,
                time_min REAL NOT NULL,
                pace REAL NOT NULL,
                calories REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                insight TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS edit_history (
                id SERIAL PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                edited_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_notes (
                id SERIAL PRIMARY KEY,
                target_user_id INTEGER NOT NULL REFERENCES users(id),
                author_id INTEGER NOT NULL REFERENCES users(id),
                note TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon_url TEXT,
                criteria_type TEXT NOT NULL,
                criteria_value REAL NOT NULL
            )
        """)

        # Add columns that may not exist (PG migration — uses IF NOT EXISTS, safe to re-run)
        for pg_migration in [
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS run_type TEXT DEFAULT 'easy'",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_weekly_summary INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_email TEXT",
            # Weather / location columns
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS home_city TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS home_latitude REAL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS home_longitude REAL",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS weather_temp REAL",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS weather_humidity INTEGER",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS weather_wind_kph REAL",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS weather_condition TEXT",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS weather_emoji TEXT",
            # PIN recovery columns
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_email TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_email_verified INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(pg_migration)
            except Exception:
                pass

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")

        # PIN recovery token table (PG)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pin_resets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                code_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                used_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                badge_key TEXT NOT NULL,
                unlocked_at TEXT,
                activity_id INTEGER,
                UNIQUE (user_id, badge_key)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
                total_distance_km REAL DEFAULT 0.0,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_activity_date TEXT,
                updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id SERIAL PRIMARY KEY,
                follower_id INTEGER NOT NULL REFERENCES users(id),
                followed_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (follower_id, followed_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_weekly_goals (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                goal_km REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    else:
        print("[RunRush DB WARNING] Connected to SQLite (runs.db). Data is EPHEMERAL on Render/cloud hosting. To persist profiles across deploys, set DATABASE_URL in Render environment variables.")
        # ---- SQLite DDL (with ALTER TABLE migrations) ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                pin TEXT NOT NULL
            )
        """)

        # add new columns if they don't exist (SQLite migration style)
        import sqlite3 as _sqlite3
        _alter_columns = [
            "ALTER TABLE users ADD COLUMN display_name TEXT",
            "ALTER TABLE users ADD COLUMN weight REAL",
            "ALTER TABLE users ADD COLUMN weekly_goal_km REAL",
            "ALTER TABLE users ADD COLUMN theme TEXT",
            "ALTER TABLE users ADD COLUMN height REAL",
            "ALTER TABLE users ADD COLUMN last_login TEXT",
            "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'",
            "ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'",
            "ALTER TABLE users ADD COLUMN email TEXT",
            "ALTER TABLE users ADD COLUMN email_weekly_summary INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN google_id TEXT",
            "ALTER TABLE users ADD COLUMN google_email TEXT",
            # Weather / location columns
            "ALTER TABLE users ADD COLUMN home_city TEXT",
            "ALTER TABLE users ADD COLUMN home_latitude REAL",
            "ALTER TABLE users ADD COLUMN home_longitude REAL",
            # PIN recovery columns
            "ALTER TABLE users ADD COLUMN recovery_email TEXT",
            "ALTER TABLE users ADD COLUMN recovery_email_verified INTEGER DEFAULT 0",
        ]
        for sql in _alter_columns:
            try:
                conn.execute(sql)
            except _sqlite3.OperationalError:
                pass

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")

        # PIN recovery token table (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pin_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # runs table
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

        # Add columns to runs if missing (SQLite migration — safe to re-run)
        for sql in [
            "ALTER TABLE runs ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE runs ADD COLUMN insight TEXT",
            "ALTER TABLE runs ADD COLUMN run_type TEXT DEFAULT 'easy'",
            "ALTER TABLE runs ADD COLUMN notes TEXT",  # Feature: friend mentions
            # Weather columns
            "ALTER TABLE runs ADD COLUMN weather_temp REAL",
            "ALTER TABLE runs ADD COLUMN weather_humidity INTEGER",
            "ALTER TABLE runs ADD COLUMN weather_wind_kph REAL",
            "ALTER TABLE runs ADD COLUMN weather_condition TEXT",
            "ALTER TABLE runs ADD COLUMN weather_emoji TEXT",
        ]:
            try:
                conn.execute(sql)
            except _sqlite3.OperationalError:
                pass

        # edit_history table
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

        # badges table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon_url TEXT,
                criteria_type TEXT NOT NULL,
                criteria_value REAL NOT NULL
            )
        """)

        # user_badges table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                unlocked_at TEXT,
                activity_id INTEGER,
                UNIQUE (user_id, badge_key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # user_stats table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                total_distance_km REAL DEFAULT 0.0,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_activity_date TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # friends / follow system
        conn.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                follower_id INTEGER NOT NULL,
                followed_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (follower_id, followed_id),
                FOREIGN KEY (follower_id) REFERENCES users(id),
                FOREIGN KEY (followed_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_weekly_goals (
                user_id INTEGER PRIMARY KEY,
                goal_km REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

    conn.commit()
    conn.close()


# Make sure DB/tables exist when app starts (for Render / gunicorn)
with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

@app.cli.command("migrate-pins")
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without writing to DB.")
def migrate_pins(dry_run):
    """
    Hash all plaintext PINs in the users table using bcrypt.

    Run ONLY against a local copy / backup of the database, never production.
    Idempotent: already-hashed PINs (starting with '$2') are skipped.
    """
    conn = get_db()
    users = conn.execute("SELECT id, username, pin FROM users").fetchall()
    updated = 0
    skipped = 0
    for u in users:
        raw_pin = u["pin"] or ""
        if raw_pin.startswith("$2"):  # already a bcrypt hash
            click.echo(f"  SKIP  user={u['username']} (already hashed)")
            skipped += 1
            continue
        hashed = bcrypt.generate_password_hash(raw_pin)
        if not dry_run:
            conn.execute("UPDATE users SET pin = ? WHERE id = ?", (hashed, u["id"]))
        click.echo(f"  {'DRY ' if dry_run else ''}HASH  user={u['username']}")
        updated += 1
    if not dry_run:
        conn.commit()
    conn.close()
    click.echo(f"\nDone. Updated={updated}, Skipped={skipped}" + (" (dry-run, no changes written)" if dry_run else ""))



def parse_date_val(val):
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val_str = val.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                pass
    return None


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


@app.before_request
def check_pin_setup():
    from flask import request, redirect, url_for, session
    if "user_id" in session:
        allowed_endpoints = [
            'set_pin', 'logout', 'static', 'google_disconnect',
            'google_login', 'google_auth',
            'auth.login', 'auth.register', 'auth.logout',
            # PIN recovery flow (unauthenticated)
            'forgot_pin', 'forgot_pin_methods', 'forgot_pin_send_email',
            'forgot_pin_verify', 'forgot_pin_reset',
        ]
        if request.endpoint and request.endpoint not in allowed_endpoints:
            conn = get_db()
            user = conn.execute("SELECT pin FROM users WHERE id = ?", (session["user_id"],)).fetchone()
            conn.close()
            if user and not user['pin']:
                return redirect(url_for('set_pin'))


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
    created_at = run["created_at"] if "created_at" in run.keys() else None
    if not created_at:
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
    except IntegrityError:
        # Badge already exists (UNIQUE constraint violation)
        conn.rollback()
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
    
    all_dates = []
    for r in runs:
        parsed_d = parse_date_val(r['date'])
        if parsed_d:
            all_dates.append(parsed_d)
            
    if not all_dates:
        conn.close()
        return 0, 0
        
    all_dates = sorted(list(set(all_dates)))
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
    except IntegrityError:
        # Stats already exist
        conn.rollback()
        pass
    
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    
    conn.close()
    return stats


# ----------------- ROUTES -----------------


@app.route('/api/admin/clean-spam')
def clean_spam():
    conn = get_db()
    spam_users = ['asdfgvbnm', 'Mihikaaaaa', 'Mike', 'fgbn 22345ty', 'Ateet', 'Palak']
    
    deleted_count = 0
    for u in spam_users:
        # Find user
        cur = conn.execute('SELECT id FROM users WHERE username = ?', (u,))
        row = cur.fetchone()
        if row:
            uid = row['id']
            conn.execute('DELETE FROM runs WHERE user_id = ?', (uid,))
            conn.execute('DELETE FROM users WHERE id = ?', (uid,))
            deleted_count += 1
            
    conn.commit()
    conn.close()
    return f'Success! Deleted {deleted_count} spam users.'

@app.route("/")
def home_redirect():
    if not require_login():
        return render_template("landing.html")
    return redirect(url_for("index"))


@app.route("/offline")
def offline():
    """PWA offline fallback page — served from Service Worker cache."""
    return render_template("offline.html")


@app.route("/sw.js")
def serve_sw():
    response = make_response(app.send_static_file("sw.js"))
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


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
        HAVING COALESCE(SUM(r.distance_km), 0) > 0
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

    # ---- Feature: Streak Reminder — detect if user ran today ----
    today_str = today.strftime("%Y-%m-%d")
    ran_today = any(
        r["date"] == today_str for r in runs
    )

    # ---- All-Time Leaderboard (for SPA Leaderboard Tab) ----
    all_time_query = """
        SELECT 
            u.username, 
            u.display_name, 
            COALESCE(SUM(r.distance_km), 0)  AS total_dist, 
            COALESCE(SUM(r.time_min), 0)     AS total_time,
            COUNT(r.id)                      AS run_count
        FROM users u
        LEFT JOIN runs r ON u.id = r.user_id
        WHERE COALESCE(u.status, 'active') != 'blocked'
        GROUP BY u.id
        ORDER BY total_dist DESC
    """
    all_time_rows = conn.execute(all_time_query).fetchall()
    all_time_leaderboard = []
    for row in all_time_rows:
        total_dist_at = row["total_dist"]
        total_time_at = row["total_time"]
        all_time_leaderboard.append({
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "total_dist": round(total_dist_at, 2),
            "total_time": round(total_time_at, 1),
            "run_count": row["run_count"],
            "avg_pace": round(total_time_at / total_dist_at, 2) if total_dist_at > 0 else 0
        })

    conn.close()

    # Pop new_badges so confetti only fires once per badge earn
    new_badges = session.pop('new_badges', None)

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
        today=today_str,
        height=raw_height,
        weekly_leaderboard=weekly_leaderboard,
        all_time_leaderboard=all_time_leaderboard,
        new_badges=new_badges or [],
        ran_today=ran_today,          # Feature: streak reminder
        google_id=user["google_id"] if "google_id" in user.keys() else None,
        google_email=user["google_email"] if "google_email" in user.keys() else None
    )


# ---------- ADD RUN ----------

@app.route("/add", methods=["POST"])
def add_run():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    try:
        date_str = request.form.get("date", "").strip()
        distance_str = request.form.get("distance", "").strip()
        time_str = request.form.get("time", "").strip()
        # Feature: Friend Mentions — truncate notes to 500 chars to prevent abuse
        notes = request.form.get("notes", "").strip()[:500]
        run_type = request.form.get("run_type", "easy").strip()
        valid_run_types = {"easy", "tempo", "long", "interval", "race"}
        if run_type not in valid_run_types:
            run_type = "easy"

        # Validation: Date
        if date_str:
            run_date = parse_date_val(date_str)
            if not run_date:
                flash("Invalid date format.", "danger")
                return redirect(url_for("index"))
            today_date = datetime.now().date()
            if run_date > today_date:
                log_activity(user["id"], "VALIDATION_FAIL", f"Attempted future date: {date_str}")
                flash("You cannot log runs for future dates.", "danger")
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

        user_weight = user["weight"] if "weight" in user.keys() and user["weight"] is not None else DEFAULT_WEIGHT
        pace, calories = calc_stats(distance, time_min, user_weight)
        
        # Generate AI insight for this run
        try:
            insight = generate_run_insight(user["id"], distance, pace, calories)
        except Exception:
            insight = "Great run logged! Keep up the effort! 🏃"

        # ── Auto-fetch weather for this run ─────────────────────────────────────
        weather = None
        if "home_latitude" in user.keys() and "home_longitude" in user.keys() and user["home_latitude"] and user["home_longitude"]:
            try:
                from services.weather_service import fetch_weather
                weather = fetch_weather(
                    run_date_str=date_str,
                    latitude=user["home_latitude"],
                    longitude=user["home_longitude"],
                )
            except Exception:
                weather = None  # Weather is non-critical — never block a run save
        # ─────────────────────────────────────────────────────────────────────────

        conn = get_db()
        # Insert run with created_at timestamp, insight, notes, run_type, and weather
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute(
            """
            INSERT INTO runs (
                user_id, date, distance_km, time_min, pace, calories, created_at,
                insight, run_type, notes,
                weather_temp, weather_humidity, weather_wind_kph, weather_condition, weather_emoji
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                user["id"], date_str, distance, time_min, pace, calories, now_str,
                insight, run_type, notes or None,
                weather["temp_c"]    if weather else None,
                weather["humidity"]  if weather else None,
                weather["wind_kph"]  if weather else None,
                weather["condition"] if weather else None,
                weather["emoji"]     if weather else None,
            ),
        ).fetchone()
        
        run_id = None
        if row:
            if hasattr(row, 'keys') and 'id' in row.keys():
                run_id = row['id']
            elif isinstance(row, dict) and 'id' in row:
                run_id = row['id']
            else:
                run_id = row[0]
                
        conn.commit()
        conn.close()
        
        # ⭐ NEW: Update stats and evaluate badges
        try:
            update_user_stats(user["id"], date_str, distance, operation='add')
        except Exception as st_err:
            print(f"Stats update warning: {st_err}")
            
        try:
            if run_id:
                newly_awarded = evaluate_badges_for_user(user["id"], run_id)
                if newly_awarded:
                    session['new_badges'] = newly_awarded
        except Exception as bdg_err:
            print(f"Badge eval warning: {bdg_err}")
        
        log_activity(user["id"], "RUN_ADDED", f"Added run: {distance}km in {time_min}min")
        flash("Run logged successfully!", "success")

    except Exception as e:
        import traceback
        print("CRITICAL ERROR IN /add:", traceback.format_exc())
        flash(f"An error occurred while saving the run: {str(e)}", "danger")

    return redirect(url_for("index"))




# ---------- SYNC OFFLINE RUN ----------

@app.route("/api/sync-run", methods=["POST"])
@csrf.exempt  # Called by the Service Worker offline background-sync queue; cannot carry a CSRF token
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

        # Feature: Friend Mentions — save notes from offline sync payload too
        notes = data.get('notes', '').strip()[:500] or None
        
        # Insert run with insight and notes
        row = conn.execute(
            """
            INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, insight, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (user["id"], date_str, distance, time_min, pace, calories, insight, notes)
        ).fetchone()
        run_id = row["id"] if isinstance(row, dict) else row[0]
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

    # Safely read new columns that may not exist in older DB schemas
    user_email = user["email"] if "email" in user.keys() else None
    user_email_pref = user["email_weekly_summary"] if "email_weekly_summary" in user.keys() else 1
    home_city = user["home_city"] if "home_city" in user.keys() else None
    google_id = user["google_id"] if "google_id" in user.keys() else None
    recovery_email = user["recovery_email"] if "recovery_email" in user.keys() else None
    recovery_email_verified = user["recovery_email_verified"] if "recovery_email_verified" in user.keys() else 0

    return render_template(
        "settings.html",
        display_name=user["display_name"] or user["username"],
        username=user["username"],
        weight=user["weight"],
        height=user["height"],
        theme=user["theme"] or "dark",
        email=user_email,
        email_weekly_summary=user_email_pref if user_email_pref is not None else 1,
        home_city=home_city,
        google_id=google_id,
        recovery_email=recovery_email,
        recovery_email_verified=recovery_email_verified,
    )


@app.route("/settings/location", methods=["POST"])
def update_location():
    """Save user's home city and resolve it to lat/lng for weather fetching."""
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    city = request.form.get("home_city", "").strip()

    if not city:
        # Clear location
        conn = get_db()
        conn.execute(
            "UPDATE users SET home_city = NULL, home_latitude = NULL, home_longitude = NULL WHERE id = ?",
            (user["id"],)
        )
        conn.commit()
        conn.close()
        flash("Location cleared.", "info")
        return redirect(url_for("settings"))

    # Geocode the city via Open-Meteo (no API key needed)
    from services.weather_service import geocode_city
    lat, lng, resolved_name = geocode_city(city)

    if lat is None:
        flash(f"Could not find '{city}'. Try a larger nearby city or use format 'City, Country'.", "warning")
        return redirect(url_for("settings"))

    conn = get_db()
    conn.execute(
        "UPDATE users SET home_city = ?, home_latitude = ?, home_longitude = ? WHERE id = ?",
        (resolved_name, lat, lng, user["id"])
    )
    conn.commit()
    conn.close()

    flash(f"📍 Location set to {resolved_name} ({lat}, {lng}). Weather will now be auto-logged with your runs!", "success")
    return redirect(url_for("settings"))

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


# ---------- EMAIL PREFERENCES ----------

@app.route("/settings/email", methods=["POST"])
def update_email_settings():
    """Save user's email address and weekly summary email preference."""
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    import re as _re
    email = request.form.get("email", "").strip()
    email_weekly_summary = 1 if request.form.get("email_weekly_summary") else 0

    if email and not _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for("settings"))

    conn = get_db()
    conn.execute(
        "UPDATE users SET email = ?, email_weekly_summary = ? WHERE id = ?",
        (email or None, email_weekly_summary, user["id"])
    )
    conn.commit()
    conn.close()

    log_activity(user["id"], "UPDATE_EMAIL", "User updated email preferences")
    flash("Email preferences saved! 📧", "success")
    return redirect(url_for("settings"))


# ---------- WEEKLY SUMMARY EMAIL HELPER ----------

def send_weekly_summary(user_id):
    """
    Send a weekly run summary email to a user via the Resend API.
    Uses only stdlib (urllib) — no extra packages required.
    Returns True on success, False on any failure.
    """
    import json as _json
    import urllib.request as _url_req
    import urllib.error as _url_err

    api_key    = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "RunRush <noreply@runrush.app>")

    if not api_key:
        return False

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False

    user_email = user["email"] if "email" in user.keys() else None
    opt_in     = user["email_weekly_summary"] if "email_weekly_summary" in user.keys() else 1
    if not user_email or not opt_in:
        conn.close()
        return False

    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    week_runs = conn.execute(
        "SELECT distance_km, time_min, pace, calories FROM runs WHERE user_id = ? AND date BETWEEN ? AND ?",
        (user_id, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
    ).fetchall()

    stats_row = conn.execute(
        "SELECT current_streak FROM user_stats WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()

    name              = user["display_name"] or user["username"]
    total_km          = sum(r["distance_km"] for r in week_runs)
    total_runs_count  = len(week_runs)
    avg_pace          = (sum(r["pace"] for r in week_runs) / total_runs_count) if total_runs_count > 0 else 0
    streak            = stats_row["current_streak"] if stats_row else 0
    weekly_goal       = user["weekly_goal_km"]

    goal_html = ""
    if weekly_goal and weekly_goal > 0:
        pct = min(100, round(total_km / weekly_goal * 100))
        goal_html = f"<p style='text-align:center;color:#888;margin-top:0;'>Goal: <b style='color:#F5A623'>{total_km:.1f} / {weekly_goal:.0f} km</b> — {pct}%</p>"

    if total_runs_count == 0:
        motivation = "No runs this week — next week is a fresh start! 💪"
    elif weekly_goal and total_km >= weekly_goal:
        motivation = "🎉 You crushed your weekly goal! Amazing work!"
    elif streak >= 7:
        motivation = f"🔥 {streak}-day streak! You are on fire!"
    else:
        motivation = "Keep running — every step counts! 🏃"

    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:20px;background:#09090f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:560px;margin:0 auto;background:#0d0d1a;border-radius:20px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#F5A623 0%,#ff6b35 100%);padding:32px;text-align:center;">
    <div style="font-size:2.5rem;">🏃</div>
    <h1 style="margin:8px 0 4px;color:#000;font-size:1.5rem;font-weight:800;">RunRush</h1>
    <p style="margin:0;color:rgba(0,0,0,0.65);font-size:0.9rem;">Weekly Summary for {name}</p>
  </div>
  <div style="padding:28px 32px;">
    <p style="color:#ccc;margin-top:0;">{motivation}</p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;">
      <div style="background:#1a1a2e;border-radius:12px;padding:18px;text-align:center;">
        <div style="font-size:1.8rem;font-weight:800;color:#F5A623;">{total_km:.1f}</div>
        <div style="color:#666;font-size:0.78rem;margin-top:4px;">KM THIS WEEK</div>
      </div>
      <div style="background:#1a1a2e;border-radius:12px;padding:18px;text-align:center;">
        <div style="font-size:1.8rem;font-weight:800;color:#4dadff;">{total_runs_count}</div>
        <div style="color:#666;font-size:0.78rem;margin-top:4px;">RUNS LOGGED</div>
      </div>
      <div style="background:#1a1a2e;border-radius:12px;padding:18px;text-align:center;">
        <div style="font-size:1.8rem;font-weight:800;color:#b0ff4f;">{streak}</div>
        <div style="color:#666;font-size:0.78rem;margin-top:4px;">DAY STREAK 🔥</div>
      </div>
      <div style="background:#1a1a2e;border-radius:12px;padding:18px;text-align:center;">
        <div style="font-size:1.8rem;font-weight:800;color:#d988ff;">{avg_pace:.1f}</div>
        <div style="color:#666;font-size:0.78rem;margin-top:4px;">AVG MIN/KM</div>
      </div>
    </div>
    {goal_html}
    <div style="text-align:center;margin-top:24px;">
      <a href="https://runrush.app/dashboard"
         style="background:#F5A623;color:#000;padding:13px 32px;border-radius:50px;text-decoration:none;font-weight:700;font-size:0.95rem;">Open Dashboard →</a>
    </div>
    <p style="color:#333;font-size:0.75rem;text-align:center;margin-top:24px;">You're receiving this because you opted in.
      <a href="https://runrush.app/settings" style="color:#555;">Change preferences</a>
    </p>
  </div>
</div></body></html>"""

    payload = _json.dumps({
        "from":    from_email,
        "to":      [user_email],
        "subject": f"🏃 {name}'s Weekly Running Summary – RunRush",
        "html":    html_body
    }).encode("utf-8")

    req = _url_req.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json"
        }
    )
    try:
        with _url_req.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (_url_err.URLError, Exception):
        return False


# ---------- CHANGE PIN ----------

@app.route("/settings/change-pin", methods=["POST"])
def change_pin():
    """
    Allows a logged-in user to change their numeric PIN.
    Validates current PIN, enforces 4+ digit numeric requirement,
    and checks new PIN confirmation matches.
    PINs are stored as bcrypt hashes; legacy plaintext PINs are also handled.
    """
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    current_pin = request.form.get("current_pin", "").strip()
    new_pin = request.form.get("new_pin", "").strip()
    confirm_pin = request.form.get("confirm_pin", "").strip()

    # ---- Validate current PIN (bcrypt-aware; constant-time for plaintext fallback) ----
    stored_pin = user["pin"] or ""
    if stored_pin.startswith("$2"):
        pins_match = bcrypt.check_password_hash(stored_pin, current_pin)
    else:
        import hmac as _hmac
        pins_match = _hmac.compare_digest(stored_pin.encode(), current_pin.encode())
    if not pins_match:
        flash("Current PIN is incorrect.", "danger")
        return redirect(url_for("settings"))

    # ---- Validate new PIN format ----
    if not new_pin.isdigit() or len(new_pin) < 4:
        flash("New PIN must be numeric and at least 4 digits.", "danger")
        return redirect(url_for("settings"))

    # ---- Validate confirmation ----
    if new_pin != confirm_pin:
        flash("New PIN and confirmation do not match.", "danger")
        return redirect(url_for("settings"))

    # ---- Prevent reusing the same PIN ----
    if new_pin == current_pin:
        flash("New PIN must be different from the current PIN.", "warning")
        return redirect(url_for("settings"))

    # ---- Update the PIN (stored as bcrypt hash) ----
    hashed_new_pin = bcrypt.generate_password_hash(new_pin)
    conn = get_db()
    conn.execute("UPDATE users SET pin = ? WHERE id = ?", (hashed_new_pin, user["id"]))
    conn.commit()
    conn.close()

    log_activity(user["id"], "CHANGE_PIN", "User changed PIN")
    flash("PIN changed successfully! 🔒", "success")
    return redirect(url_for("settings"))


#-------Clear Data-----#
@app.route("/settings/clear-data", methods=["POST"])
def clear_data():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    # Delete all runs for this user
    conn.execute("DELETE FROM runs WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()

    log_activity(user["id"], "CLEAR_DATA", "User cleared all their runs")
    flash("All your logged runs have been cleared! 🗑️", "success")
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
        "SELECT date, distance_km, time_min, pace, calories, run_type FROM runs WHERE user_id = ? ORDER BY date DESC",
        (user["id"],)
    ).fetchall()
    conn.close()

    # Create CSV in memory
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Date", "Distance (km)", "Time (min)", "Pace (min/km)", "Calories", "Run Type"])
    for r in runs:
        cw.writerow([r["date"], r["distance_km"], r["time_min"], r["pace"], r["calories"], r["run_type"] or "easy"])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=runrush_history.csv"
    output.headers["Content-type"] = "text/csv"
    return output


# ---------- STRAVA CSV IMPORT API ----------

def parse_duration_str(dur_str):
    if not dur_str:
        return None
    dur_str = str(dur_str).strip()
    if ':' in dur_str:
        parts = dur_str.split(':')
        try:
            if len(parts) == 3:
                h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
                return round(h * 60.0 + m + s / 60.0, 2)
            elif len(parts) == 2:
                m, s = float(parts[0]), float(parts[1])
                return round(m + s / 60.0, 2)
        except ValueError:
            return None
    try:
        val = float(dur_str.replace(',', ''))
        if val <= 0:
            return None
        if val > 300: # given in seconds
            return round(val / 60.0, 2)
        return round(val, 2)
    except ValueError:
        return None


def parse_distance_str(dist_str):
    if not dist_str:
        return None
    dist_str_clean = str(dist_str).strip().lower()
    is_miles = 'mi' in dist_str_clean or 'mile' in dist_str_clean
    num_str = re.sub(r'[^\d\.]', '', dist_str_clean)
    try:
        val = float(num_str)
        if val <= 0:
            return None
        if is_miles:
            return round(val * 1.60934, 2)
        if val > 150: # distance given in meters
            return round(val / 1000.0, 2)
        return round(val, 2)
    except ValueError:
        return None


def parse_strava_date(date_raw):
    if not date_raw:
        return None
    date_raw = str(date_raw).strip()
    d = parse_date_val(date_raw)
    if d:
        return d.strftime("%Y-%m-%d")
    
    strava_formats = [
        "%b %d, %Y, %I:%M:%S %p",
        "%b %d, %Y, %I:%M %p",
        "%b %d, %Y",
        "%d %b %Y, %H:%M:%S",
        "%d %b %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d"
    ]
    for fmt in strava_formats:
        try:
            dt = datetime.strptime(date_raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_strava_csv(csv_text, user_id, user_weight):
    si = io.StringIO(csv_text)
    try:
        reader = csv.DictReader(si)
    except Exception:
        raise ValueError("Invalid CSV file structure")

    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no header row")

    headers_lower = {fn.strip().lower(): fn for fn in reader.fieldnames if fn}

    def find_col(candidates):
        for c in candidates:
            if c.lower() in headers_lower:
                return headers_lower[c.lower()]
        return None

    date_col = find_col(["activity date", "date", "start time", "activity date/time"])
    dist_col = find_col(["distance", "distance (km)", "distance (m)", "distance_km"])
    time_col = find_col(["moving time", "elapsed time", "time (min)", "duration", "time", "time_min"])
    type_col = find_col(["activity type", "type", "sport", "run_type"])
    name_col = find_col(["activity name", "title", "name"])
    desc_col = find_col(["activity description", "description", "notes"])

    if not date_col or not dist_col or not time_col:
        cols_summary = ", ".join(reader.fieldnames[:6]) if reader.fieldnames else "none"
        raise ValueError(
            "Missing required columns in CSV. File must contain Date, Distance, and Duration/Time columns. "
            f"Found columns: {cols_summary}"
        )

    valid_runs = []
    duplicates = []
    skipped_non_run = []
    invalids = []
    seen_in_import = set()

    conn = get_db()
    existing_rows = conn.execute(
        "SELECT date, distance_km, time_min FROM runs WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    conn.close()

    existing_runs_list = []
    for er in existing_rows:
        existing_runs_list.append((
            str(er['date']),
            float(er['distance_km']),
            float(er['time_min'])
        ))

    row_index = 0
    running_activities = {"run", "trail run", "virtual run", "treadmill", "race", "running"}

    for raw_row in reader:
        row_index += 1
        
        act_name = (raw_row.get(name_col) or "").strip() if name_col else ""
        act_desc = (raw_row.get(desc_col) or "").strip() if desc_col else ""
        act_type_raw = (raw_row.get(type_col) or "").strip() if type_col else ""
        act_type_clean = act_type_raw.lower()

        notes_parts = [p for p in [act_name, act_desc] if p]
        notes = " - ".join(notes_parts)[:500] or "Imported from Strava"

        is_run = False
        if act_type_clean in running_activities:
            is_run = True
        elif not act_type_raw and ("run" in act_name.lower() or "jog" in act_name.lower()):
            is_run = True
        elif not type_col:
            is_run = True

        if not is_run:
            skipped_non_run.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "type": act_type_raw or "Non-run",
                "reason": f"Non-running activity ({act_type_raw or 'Other'})"
            })
            continue

        date_str = parse_strava_date(raw_row.get(date_col))
        if not date_str:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Invalid date: '{raw_row.get(date_col)}'"
            })
            continue

        try:
            r_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if r_date > date.today():
                invalids.append({
                    "row": row_index,
                    "name": act_name or f"Row {row_index}",
                    "reason": f"Future date not allowed: '{date_str}'"
                })
                continue
        except ValueError:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Invalid date format: '{date_str}'"
            })
            continue

        distance_km = parse_distance_str(raw_row.get(dist_col))
        if not distance_km or distance_km <= 0:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Invalid distance: '{raw_row.get(dist_col)}'"
            })
            continue

        time_min = parse_duration_str(raw_row.get(time_col))
        if not time_min or time_min <= 0:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Invalid duration: '{raw_row.get(time_col)}'"
            })
            continue

        pace_val = time_min / distance_km
        if pace_val < 2.0 or pace_val > 30.0:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Unrealistic pace ({pace_val:.2f} min/km)"
            })
            continue

        pace, calories = calc_stats(distance_km, time_min, user_weight)

        lower_notes = notes.lower()
        if "race" in lower_notes or "marathon" in lower_notes:
            run_type = "race"
        elif "interval" in lower_notes or "workout" in lower_notes or "reps" in lower_notes:
            run_type = "interval"
        elif "tempo" in lower_notes or "threshold" in lower_notes:
            run_type = "tempo"
        elif "long" in lower_notes or distance_km >= 15.0:
            run_type = "long"
        else:
            run_type = "easy"

        is_dup = False
        for ex_date, ex_dist, ex_time in existing_runs_list:
            if ex_date == date_str and abs(ex_dist - distance_km) < 0.05 and abs(ex_time - time_min) < 0.5:
                is_dup = True
                break

        dup_key = (date_str, round(distance_km, 2), round(time_min, 1))
        if dup_key in seen_in_import:
            is_dup = True

        run_item = {
            "date": date_str,
            "distance": distance_km,
            "time": time_min,
            "pace": pace,
            "calories": calories,
            "run_type": run_type,
            "notes": notes,
            "name": act_name or f"{distance_km} km Run"
        }

        if is_dup:
            duplicates.append(run_item)
        else:
            seen_in_import.add(dup_key)
            valid_runs.append(run_item)

    return {
        "total_rows": row_index,
        "valid_count": len(valid_runs),
        "skipped_non_run_count": len(skipped_non_run),
        "duplicate_count": len(duplicates),
        "invalid_count": len(invalids),
        "valid_runs": valid_runs,
        "duplicates": duplicates,
        "skipped": skipped_non_run,
        "invalids": invalids
    }


@app.route("/api/parse-import", methods=["POST"])
def parse_import():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({"error": "Only CSV files (.csv) are supported"}), 400

    try:
        file.seek(0, os.SEEK_END)
        size_bytes = file.tell()
        file.seek(0)

        if size_bytes > 5 * 1024 * 1024:
            return jsonify({"error": "File size exceeds limit (max 5 MB)"}), 400

        content = file.read().decode('utf-8-sig', errors='replace')
        
        user_weight = user["weight"] if "weight" in user.keys() and user["weight"] is not None else DEFAULT_WEIGHT
        res = parse_strava_csv(content, user["id"], user_weight)
        
        return jsonify({"success": True, "data": res}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        import traceback
        print("PARSE IMPORT ERROR:", traceback.format_exc())
        return jsonify({"error": f"Failed to parse CSV file: {str(e)}"}), 500


@app.route("/api/confirm-import", methods=["POST"])
def confirm_import():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json() or {}
    runs_to_import = payload.get("runs", [])

    if not runs_to_import or not isinstance(runs_to_import, list):
        return jsonify({"error": "No runs provided for import"}), 400

    user_weight = user["weight"] if "weight" in user.keys() and user["weight"] is not None else DEFAULT_WEIGHT
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    inserted_ids = []
    
    try:
        for item in runs_to_import:
            date_str = str(item.get("date", "")).strip()
            distance = float(item.get("distance", 0))
            time_min = float(item.get("time", 0))
            notes = str(item.get("notes", "")).strip()[:500] or "Imported from Strava"
            run_type = str(item.get("run_type", "easy")).strip()
            if run_type not in {"easy", "tempo", "long", "interval", "race"}:
                run_type = "easy"

            pace, calories = calc_stats(distance, time_min, user_weight)
            insight = f"Imported from Strava 🏃 ({distance} km in {time_min} min)"

            row = conn.execute(
                """
                INSERT INTO runs (
                    user_id, date, distance_km, time_min, pace, calories, created_at,
                    insight, run_type, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (user["id"], date_str, distance, time_min, pace, calories, now_str, insight, run_type, notes)
            ).fetchone()

            r_id = None
            if row:
                if hasattr(row, 'keys') and 'id' in row.keys():
                    r_id = row['id']
                elif isinstance(row, dict) and 'id' in row:
                    r_id = row['id']
                else:
                    r_id = row[0]
            if r_id:
                inserted_ids.append(r_id)

        conn.commit()
        conn.close()

    except Exception as e:
        conn.rollback()
        conn.close()
        import traceback
        print("BATCH IMPORT ROLLBACK:", traceback.format_exc())
        return jsonify({"error": f"Database import failed. All changes rolled back: {str(e)}"}), 500

    all_awarded = []
    if inserted_ids:
        try:
            latest_date = max(str(r.get("date", "")) for r in runs_to_import)
            total_dist_added = sum(float(r.get("distance", 0)) for r in runs_to_import)
            update_user_stats(user["id"], latest_date, total_dist_added, operation='add')
        except Exception as st_err:
            print(f"Stats update warning after import: {st_err}")

        try:
            for r_id in inserted_ids[:10]:
                awarded = evaluate_badges_for_user(user["id"], r_id)
                all_awarded.extend(awarded)
            all_awarded = list(set(all_awarded))
            if all_awarded:
                session['new_badges'] = all_awarded
        except Exception as bdg_err:
            print(f"Badge eval warning after import: {bdg_err}")

        log_activity(user["id"], "STRAVA_IMPORT", f"Imported {len(inserted_ids)} runs from Strava CSV")

    return jsonify({
        "success": True,
        "imported_count": len(inserted_ids),
        "new_badges": all_awarded,
        "message": f"Successfully imported {len(inserted_ids)} runs!"
    }), 200



# ---------- SCREENSHOT IMPORT ----------

@app.route("/api/parse-screenshot", methods=["POST"])
@limiter.limit("20 per hour")
def parse_screenshot():
    """
    Accept a screenshot image, send it to the Claude vision API,
    and return extracted run data as a preview JSON (no DB write).
    """
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Validate MIME type / extension (images only)
    allowed_mimes = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}
    content_type = (file.content_type or "").lower()
    fname = file.filename.lower()
    if content_type not in allowed_mimes:
        if not any(fname.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")):
            return jsonify({"error": "Only image files (JPG, PNG, HEIC, WEBP) are supported"}), 400
        # Fallback: infer media type from extension
        ext_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                   ".heic": "image/heic", ".heif": "image/heif", ".webp": "image/webp"}
        for ext, mime in ext_map.items():
            if fname.endswith(ext):
                content_type = mime
                break

    if content_type not in allowed_mimes:
        content_type = "image/jpeg"  # safe fallback

    # Validate size (<= 10 MB)
    file.seek(0, os.SEEK_END)
    size_bytes = file.tell()
    file.seek(0)
    if size_bytes > 10 * 1024 * 1024:
        return jsonify({"error": "Image size exceeds limit (max 10 MB)"}), 400

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[parse-screenshot] GEMINI_API_KEY not configured")
        return jsonify({"error": "Screenshot import is not configured on this server. Please enter your run manually."}), 503

    import json as _json
    try:
        from google import genai as _genai
        from google.genai import types as _types
        from google.genai.errors import APIError as _APIError
    except ImportError:
        return jsonify({"error": "Screenshot import is not available (missing dependency). Please enter your run manually."}), 503

    file_bytes = file.read()

    # --- Resize / recompress before sending to Gemini ---
    # Phone screenshots can be 3-5 MB; cap the longest dimension at 1568 px
    # and re-encode as JPEG @ quality=85. This typically reduces 3 MB → 200-400 KB,
    # cutting Render→Gemini upload time significantly.
    _orig_size = len(file_bytes)
    try:
        from PIL import Image as _PILImage
        import io as _io
        _img = _PILImage.open(_io.BytesIO(file_bytes))
        _img = _img.convert("RGB")  # drop alpha, normalise mode
        _max_dim = 1568
        _w, _h = _img.size
        if max(_w, _h) > _max_dim:
            _scale = _max_dim / max(_w, _h)
            _img = _img.resize(
                (int(_w * _scale), int(_h * _scale)),
                _PILImage.LANCZOS,
            )
        _buf = _io.BytesIO()
        _img.save(_buf, format="JPEG", quality=85, optimize=True)
        file_bytes = _buf.getvalue()
        content_type = "image/jpeg"
    except Exception as _resize_err:
        # Non-fatal: log and continue with original bytes
        print(f"[parse-screenshot] Image resize skipped ({_resize_err}); sending original")
    _new_size = len(file_bytes)
    print(
        f"[parse-screenshot] image size: {_orig_size:,} bytes → {_new_size:,} bytes "
        f"({_orig_size / 1024:.1f} KB → {_new_size / 1024:.1f} KB)"
    )

    PROMPT = (
        "You are a running data extractor. The user has uploaded a screenshot from a running app.\n"
        "Extract ONLY the following fields as strict JSON, with no extra text or markdown:\n"
        "{\n"
        '  "distance_km": <float or null>,\n'
        '  "duration_seconds": <int or null>,\n'
        '  "pace_per_km": <string like "5:30" or null>,\n'
        '  "date": <ISO date string "YYYY-MM-DD" if visible, else null>,\n'
        '  "calories": <int or null>,\n'
        '  "average_heart_rate": <int or null>,\n'
        '  "elevation_gain_m": <float or null>,\n'
        '  "source_app": <string — your best guess at the app name, e.g. "Strava", "Nike Run Club", "Garmin", "Apple Fitness", "Adidas Running", or "unknown">\n'
        "}\n"
        "Return ONLY the JSON object, no explanation."
    )
    try:
        client = _genai.Client(
            api_key=api_key,
            http_options={
                "timeout": 15000.0,
                # Default is 5 attempts; cap at 2 so a slow request doesn't
                # silently stack into 90-150s of retries before the user sees an error.
                "retry_options": {
                    "attempts": 2,
                    "initial_delay": 1.0,
                    "max_delay": 10.0,
                },
            },
        )
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                _types.Part.from_bytes(data=file_bytes, mime_type=content_type),
                PROMPT
            ],
            config=_types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        # response.text raises if the candidate is blocked/empty; guard it explicitly
        candidates = getattr(response, "candidates", None)
        raw = None
        if candidates:
            raw = getattr(response, "text", None)
        if not raw:
            finish = (
                candidates[0].finish_reason.name
                if candidates and hasattr(candidates[0], "finish_reason")
                else "UNKNOWN"
            )
            print(f"[parse-screenshot] Gemini returned empty/blocked response. finish_reason={finish}")
            return (
                jsonify({"error": "Couldn't read this screenshot clearly — try a clearer photo or enter your run manually."}),
                422,
            )
        raw = raw.strip()
    except Exception as e:
        import traceback
        print("[parse-screenshot] Gemini API error:", traceback.format_exc())
        return jsonify({"error": "Couldn't connect to the AI service. Please try again or enter your run manually."}), 502

    # Defensively parse JSON — strip markdown code fences if model included them
    raw_clean = raw
    if raw_clean.startswith("```"):
        parts = raw_clean.split("```")
        raw_clean = parts[1] if len(parts) > 1 else raw_clean
        if raw_clean.startswith("json"):
            raw_clean = raw_clean[4:]
    raw_clean = raw_clean.strip()

    try:
        parsed = _json.loads(raw_clean)
    except Exception:
        print("[parse-screenshot] JSON parse failed. Raw model output:", raw)
        return jsonify({"error": "Couldn't read this screenshot clearly — try a clearer photo or enter your run manually."}), 422

    # Validate required fields
    distance_km = parsed.get("distance_km")
    duration_seconds = parsed.get("duration_seconds")
    if not distance_km or not duration_seconds:
        return jsonify({"error": "Couldn't read this screenshot clearly — try a clearer photo or enter your run manually."}), 422

    try:
        distance_km = float(distance_km)
        duration_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        return jsonify({"error": "Couldn't read this screenshot clearly — try a clearer photo or enter your run manually."}), 422

    time_min = round(duration_seconds / 60.0, 2)

    return jsonify({
        "success": True,
        "data": {
            "distance_km": distance_km,
            "time_min": time_min,
            "duration_seconds": duration_seconds,
            "pace_per_km": parsed.get("pace_per_km"),
            "date": parsed.get("date"),
            "calories": parsed.get("calories"),
            "average_heart_rate": parsed.get("average_heart_rate"),
            "elevation_gain_m": parsed.get("elevation_gain_m"),
            "source_app": parsed.get("source_app") or "unknown",
        },
    }), 200


@app.route("/api/confirm-screenshot-import", methods=["POST"])
def confirm_screenshot_import():
    """
    Accept the (possibly user-edited) preview fields from /api/parse-screenshot
    and write the run to the database. Follows the same auth/CSRF/validation
    pattern as /api/confirm-import.
    """
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json() or {}

    # Validate & coerce core fields
    try:
        distance = float(payload.get("distance_km", 0))
        time_min = float(payload.get("time_min", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid distance or duration"}), 400

    if distance <= 0 or distance > 500:
        return jsonify({"error": "Distance must be between 0 and 500 km"}), 400
    if time_min <= 0 or time_min > 1440:
        return jsonify({"error": "Duration must be between 0 and 1440 minutes (24 h)"}), 400

    date_str = str(payload.get("date") or "").strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        run_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if run_date > date.today():
            return jsonify({"error": "Run date cannot be in the future"}), 400
    except ValueError:
        return jsonify({"error": "Invalid date format — expected YYYY-MM-DD"}), 400

    run_type = str(payload.get("run_type", "easy")).strip()
    if run_type not in {"easy", "tempo", "long", "interval", "race"}:
        run_type = "easy"

    source_app = str(payload.get("source_app") or "unknown")[:100]
    user_notes = str(payload.get("notes") or "").strip()[:400]
    tag = f"[Screenshot Import — {source_app}]"
    notes = f"{tag} {user_notes}".strip() if user_notes else tag

    user_weight = user["weight"] if "weight" in user.keys() and user["weight"] is not None else DEFAULT_WEIGHT
    pace, calories = calc_stats(distance, time_min, user_weight)
    insight = f"Imported from screenshot ({source_app}) \U0001f4f8 — {distance} km in {time_min} min"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    r_id = None
    try:
        row = conn.execute(
            """
            INSERT INTO runs (
                user_id, date, distance_km, time_min, pace, calories, created_at,
                insight, run_type, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (user["id"], date_str, distance, time_min, pace, calories, now_str,
             insight, run_type, notes),
        ).fetchone()

        if row:
            if hasattr(row, "keys") and "id" in row.keys():
                r_id = row["id"]
            elif isinstance(row, dict) and "id" in row:
                r_id = row["id"]
            else:
                r_id = row[0]

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        import traceback
        print("SCREENSHOT IMPORT ROLLBACK:", traceback.format_exc())
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    conn.close()

    all_awarded = []
    if r_id:
        try:
            update_user_stats(user["id"], date_str, distance, operation="add")
        except Exception as st_err:
            print(f"Stats update warning after screenshot import: {st_err}")
        try:
            awarded = evaluate_badges_for_user(user["id"], r_id)
            all_awarded = list(set(awarded))
            if all_awarded:
                session["new_badges"] = all_awarded
        except Exception as bdg_err:
            print(f"Badge eval warning after screenshot import: {bdg_err}")
        log_activity(user["id"], "SCREENSHOT_IMPORT",
                     f"Imported run via screenshot ({source_app}): {distance} km")

    return jsonify({
        "success": True,
        "run_id": r_id,
        "new_badges": all_awarded,
        "message": f"Run imported successfully from {source_app}!",
    }), 200


# ---------- HEATMAP API ----------

@app.route("/api/heatmap-data")
def api_heatmap_data():
    """Returns daily run distances for the past 365 days for the heatmap calendar."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    user = get_current_user()
    conn = get_db()

    today = date.today()
    start_date = today - timedelta(days=364)  # 52 weeks

    runs = conn.execute(
        """
        SELECT date, SUM(distance_km) as total
        FROM runs
        WHERE user_id = ? AND date >= ?
        GROUP BY date
        ORDER BY date ASC
        """,
        (user["id"], start_date.strftime("%Y-%m-%d"))
    ).fetchall()
    conn.close()

    run_map = {r["date"]: round(r["total"], 2) for r in runs}

    # Build a list of {date, km} for each of the 365 days
    days = []
    for i in range(365):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        days.append({"date": d_str, "km": run_map.get(d_str, 0)})

    return jsonify({"days": days})


# ---------- RUN TYPE STATS API ----------

@app.route("/api/run-type-stats")
def api_run_type_stats():
    """Returns a breakdown of run types for the pie chart."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    user = get_current_user()
    conn = get_db()

    rows = conn.execute(
        """
        SELECT COALESCE(run_type, 'easy') as run_type, COUNT(*) as count, SUM(distance_km) as total_km
        FROM runs
        WHERE user_id = ?
        GROUP BY run_type
        """,
        (user["id"],)
    ).fetchall()
    conn.close()

    result = {r["run_type"]: {"count": r["count"], "total_km": round(r["total_km"], 2)} for r in rows}
    return jsonify(result)


@app.route("/leaderboard")
def leaderboard():
    """All-time leaderboard: all users ranked by total km ever logged."""
    if not require_login():
        return redirect(url_for("login"))
    
    user = get_current_user()
    
    conn = get_db()
    # LEFT JOIN so users without runs still appear (with 0 distance)
    # run_count added so we can show on the leaderboard page
    query = """
        SELECT 
            u.username, 
            u.display_name, 
            COALESCE(SUM(r.distance_km), 0)  AS total_dist, 
            COALESCE(SUM(r.time_min), 0)     AS total_time,
            COUNT(r.id)                      AS run_count
        FROM users u
        LEFT JOIN runs r ON u.id = r.user_id
        WHERE COALESCE(u.status, 'active') != 'blocked'
        GROUP BY u.id
        ORDER BY total_dist DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    leaderboard_data = []
    for row in rows:
        total_dist = row["total_dist"]
        total_time = row["total_time"]
        leaderboard_data.append({
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "total_dist": round(total_dist, 2),
            "total_time": round(total_time, 1),
            "run_count": row["run_count"],
            # avg_pace in min/km; 0 if no runs
            "avg_pace": round(total_time / total_dist, 2) if total_dist > 0 else 0
        })

    return render_template(
        "leaderboard.html",
        leaderboard=leaderboard_data,
        username=user["username"],
        display_name=user["display_name"] or user["username"],
        theme=user["theme"] or "dark"
    )


# ---------- USER SEARCH API (for @mention autocomplete) ----------

@app.route("/api/users/search")
def api_user_search():
    """
    Returns a list of usernames matching the query string.
    Used by the @mention autocomplete in the run notes field.
    Limits to 8 results. Excludes the current user.
    """
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    if not q or len(q) < 1:
        return jsonify({"users": []})

    # Sanitise: only allow alphanumeric + underscore queries
    import re
    if not re.match(r'^[\w]+$', q):
        return jsonify({"users": []})

    user = get_current_user()
    conn = get_db()
    rows = conn.execute(
        """
        SELECT username, display_name
        FROM users
        WHERE username LIKE ?
          AND id != ?
          AND COALESCE(status, 'active') = 'active'
        ORDER BY username ASC
        LIMIT 8
        """,
        (q + "%", user["id"])
    ).fetchall()
    conn.close()

    return jsonify({
        "users": [
            {
                "username": row["username"],
                "display_name": row["display_name"] or row["username"]
            }
            for row in rows
        ]
    })


# ---------- FRIEND / FOLLOW SYSTEM ----------

@app.route("/follow/<username>", methods=["POST"])
def follow_user(username):
    """Follow another runner."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    target = conn.execute(
        "SELECT id, username, display_name FROM users WHERE username = ? AND COALESCE(status, 'active') = 'active'",
        (username,)
    ).fetchone()

    if not target:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    if target["id"] == user["id"]:
        conn.close()
        return jsonify({"error": "Cannot follow yourself"}), 400

    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO friends (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
            (user["id"], target["id"], now_str)
        )
        conn.commit()
        conn.close()
        log_activity(user["id"], "FOLLOW", f"Followed {username}")
        return jsonify({"success": True, "following": True}), 200
    except IntegrityError:
        conn.close()
        return jsonify({"success": True, "following": True, "note": "Already following"}), 200


@app.route("/unfollow/<username>", methods=["POST"])
def unfollow_user(username):
    """Unfollow a runner."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    target = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not target:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    conn.execute(
        "DELETE FROM friends WHERE follower_id = ? AND followed_id = ?",
        (user["id"], target["id"])
    )
    conn.commit()
    conn.close()
    log_activity(user["id"], "UNFOLLOW", f"Unfollowed {username}")
    return jsonify({"success": True, "following": False}), 200


@app.route("/social-feed")
def social_feed():
    """Social feed page — recent runs from users you follow."""
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()

    # Users this person follows
    following = conn.execute(
        """
        SELECT u.id, u.username, u.display_name
        FROM friends f
        JOIN users u ON f.followed_id = u.id
        WHERE f.follower_id = ?
          AND COALESCE(u.status, 'active') = 'active'
        ORDER BY u.username ASC
        """,
        (user["id"],)
    ).fetchall()

    # 30-day cutoff for dynamic engagement scoring
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Runs from followed users (last 30 days)
    following_ids = [f["id"] for f in following]
    feed_runs = []
    if following_ids:
        placeholders = ",".join("?" * len(following_ids))
        feed_runs = conn.execute(
            f"""
            SELECT r.id, r.date, r.distance_km, r.time_min, r.pace, r.calories,
                   r.run_type, r.notes, r.insight,
                   u.username, u.display_name
            FROM runs r
            JOIN users u ON r.user_id = u.id
            WHERE r.user_id IN ({placeholders}) AND r.date >= ?
            ORDER BY r.date DESC, r.id DESC
            LIMIT 30
            """,
            (*following_ids, cutoff)
        ).fetchall()

    # Discover runners not yet followed
    exclude_ids   = [f["id"] for f in following] + [user["id"]]
    placeholders2 = ",".join("?" * len(exclude_ids))
    
    # Social Score = (Recent KM * 2) + (Recent Runs * 5) + (Current Streak * 10)
    discover = conn.execute(
        f"""
        SELECT u.username, u.display_name,
               COALESCE(SUM(r.distance_km), 0) AS recent_km,
               COUNT(r.id) AS recent_runs,
               COALESCE(us.current_streak, 0) AS current_streak,
               (COALESCE(SUM(r.distance_km), 0) * 2 + COUNT(r.id) * 5 + COALESCE(us.current_streak, 0) * 10) AS social_score
        FROM users u
        LEFT JOIN runs r ON u.id = r.user_id AND r.date >= ?
        LEFT JOIN user_stats us ON u.id = us.user_id
        WHERE u.id NOT IN ({placeholders2})
          AND COALESCE(u.status, 'active') = 'active'
        GROUP BY u.id
        ORDER BY social_score DESC, recent_km DESC
        LIMIT 8
        """,
        (cutoff, *exclude_ids)
    ).fetchall()

    conn.close()

    return render_template(
        "social.html",
        user=user,
        following=following,
        feed_runs=feed_runs,
        discover=discover,
        theme=user["theme"] or "dark",
        username=user["username"],
        display_name=user["display_name"] or user["username"]
    )


# ---------- AUTH ROUTES ----------

@app.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        pin = request.form["pin"].strip()

        if not username or not pin:
            return render_template("register.html", error="Username and PIN are required.")

        if len(pin) < 4 or not pin.isdigit():
            return render_template("register.html", error="Use a 4+ digit numeric PIN.")

        hashed_pin = bcrypt.generate_password_hash(pin)
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, pin) VALUES (?, ?)",
                (username, hashed_pin)
            )
            conn.commit()
        except IntegrityError:
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
@limiter.limit("20 per hour")
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        pin = request.form["pin"].strip()

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        # Verify PIN using bcrypt. All PINs have been migrated to bcrypt hashes
        # via `flask migrate-pins` — plaintext fallback has been removed.
        if user:
            stored_pin = user["pin"] or ""
            pin_ok = bcrypt.check_password_hash(stored_pin, pin)
        else:
            pin_ok = False

        if not user or not pin_ok:
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


@app.route("/auth/google/login")
def google_login():
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        flash("Google Login is not configured on this server.", "danger")
        return redirect(url_for("login"))
    
    redirect_uri = url_for('google_auth', _external=True)
    session['linking'] = request.args.get('link') == 'true'
    session['intent'] = request.args.get('intent', 'login')
    if session['linking']:
        session['oauth_redirect_to'] = request.referrer
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
@limiter.limit("20 per hour")
def google_auth():
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        flash("Google Login is not configured.", "danger")
        return redirect(url_for("login"))
        
    try:
        token = oauth.google.authorize_access_token()
        userinfo = token.get('userinfo')
        if not userinfo:
            userinfo = oauth.google.userinfo()
    except Exception as e:
        flash(f"Google login failed: {str(e)}", "danger")
        return redirect(url_for("login"))
        
    google_id = userinfo.get('sub')
    email = userinfo.get('email')
    intent = session.pop('intent', 'login')
    
    if not google_id or not email:
        flash("Incomplete information received from Google.", "danger")
        return redirect(url_for("login"))
        
    conn = get_db()
    
    # 1. Check if google_id already exists
    user = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    
    if user:
        # ---- GOOGLE RECOVERY FLOW: must check BEFORE any login logic ----
        # intent is consumed from session (server-side) to prevent tampering
        if intent == 'recover':
            recovery_uid = session.get('recovery_user_id')
            session.pop('recovery_user_id', None)  # consume
            if not recovery_uid or user['id'] != recovery_uid:
                # Wrong Google account or stale session
                conn.close()
                flash("Recovery failed. The Google account you used does not match the account's linked Google identity.", "danger")
                return redirect(url_for('forgot_pin'))
            # Valid — grant access to reset
            conn.close()
            session['recovery_verified']    = True
            session['recovery_user_id']     = recovery_uid
            session['recovery_method']      = 'google'
            session['recovery_expires_at']  = (
                datetime.utcnow() + timedelta(minutes=15)
            ).strftime("%Y-%m-%d %H:%M:%S")
            return redirect(url_for('forgot_pin_reset'))

        if session.get('linking'):
            if user['id'] != session.get('user_id'):
                flash("This Google account is already linked to another user.", "danger")
                conn.close()
                return redirect(session.pop('oauth_redirect_to', url_for("settings")))
            else:
                flash("This Google account is already linked to your account.", "info")
                conn.close()
                return redirect(session.pop('oauth_redirect_to', url_for("settings")))
        
        # Log them in
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        if user["status"] == "blocked":
            session.clear()
            conn.close()
            return render_template("login.html", error="Your account has been blocked.")
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_str, user["id"]))
        conn.commit()
        conn.close()
        log_activity(user["id"], "LOGIN", "User logged in via Google")
        
        if not user['pin']:
            return redirect(url_for('set_pin'))
            
        return redirect(url_for("index"))
        
    # 2. Check if we are linking to a current session
    if session.get('linking') and session.get('user_id'):
        user_id = session['user_id']
        conn.execute("UPDATE users SET google_id = ?, google_email = ? WHERE id = ?", (google_id, email, user_id))
        conn.commit()
        conn.close()
        session.pop('linking', None)
        flash("Google account successfully linked!", "success")
        log_activity(user_id, "LINK_GOOGLE", "Linked Google account")
        return redirect(session.pop('oauth_redirect_to', url_for("settings")))
        
    # 3. Check for email collision with existing account
    existing_email_user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if existing_email_user:
        conn.close()
        flash("An account already exists with this email. Please log in with your existing username and PIN, then link your Google account from your Profile.", "warning")
        return redirect(url_for("login"))
        
    # 4. Handle based on intent
    if intent == 'login':
        conn.close()
        flash("No RunRush account found for this Google account. Please create an account first.", "warning")
        return redirect(url_for("login"))

    # Brand new registration (intent == 'register')
    base_username = email.split('@')[0]
    username = base_username
    counter = 2
    while conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
        username = f"{base_username}{counter}"
        counter += 1
        
    try:
        conn.execute(
            "INSERT INTO users (username, pin, email, google_id, google_email) VALUES (?, ?, ?, ?, ?)",
            (username, "", email, google_id, email)
        )
        conn.commit()
        new_user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        
        session["user_id"] = new_user["id"]
        session["username"] = username
        log_activity(new_user["id"], "REGISTER", "User registered via Google")
        conn.close()
        
        return redirect(url_for("set_pin"))
        
    except IntegrityError:
        conn.close()
        flash("Error creating account.", "danger")
        return redirect(url_for("login"))


@app.route("/auth/google/disconnect", methods=["POST"])
def google_disconnect():
    if not require_login():
        return redirect(url_for("login"))
        
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
        
    if not user['pin']:
        flash("You cannot disconnect your Google account because you don't have a backup PIN set. Please change your PIN first.", "danger")
        return redirect(request.referrer or url_for("settings"))
        
    conn = get_db()
    conn.execute("UPDATE users SET google_id = NULL, google_email = NULL WHERE id = ?", (user['id'],))
    conn.commit()
    conn.close()
    
    log_activity(user['id'], "UNLINK_GOOGLE", "Disconnected Google account")
    flash("Google account disconnected.", "success")
    return redirect(request.referrer or url_for("settings"))


# =============================================================================
# FORGOT PIN — Recovery flow
# =============================================================================

_RECOVERY_SESSION_LIFETIME = 900  # 15 minutes


def _recovery_session_valid():
    """True if the server-side recovery session is present, verified, and not expired."""
    if not session.get('recovery_verified'):
        return False
    expires_at_str = session.get('recovery_expires_at', '')
    if not expires_at_str:
        return False
    try:
        expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return datetime.utcnow() < expires_at


def _clear_recovery_session():
    """Wipe all recovery state from the server-side session."""
    for k in ('recovery_user_id', 'recovery_verified', 'recovery_method', 'recovery_expires_at'):
        session.pop(k, None)


@app.route("/forgot-pin", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def forgot_pin():
    """
    Step 1: collect username.
    POST: look up the user (never reveal whether it exists), set
    server-side recovery_user_id in session, redirect to methods page.
    """
    _clear_recovery_session()

    if request.method == "POST":
        username = request.form.get('username', '').strip()
        # Constant-time: always redirect to /forgot-pin/methods
        # We store the user_id only if found — otherwise store None
        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone() if username else None
        conn.close()

        # Store the (possibly None) user_id server-side
        # The methods page will display a generic message if None
        session['recovery_user_id'] = user['id'] if user else None
        session['recovery_verified'] = False
        return redirect(url_for('forgot_pin_methods'))

    return render_template('forgot_pin.html')


@app.route("/forgot-pin/methods", methods=["GET"])
@limiter.limit("20 per hour")
def forgot_pin_methods():
    """
    Step 2: show available recovery options without exposing account details.
    """
    user_id = session.get('recovery_user_id')
    SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', '<!-- CONFIGURE SUPPORT_EMAIL in environment -->')

    if not user_id:
        # Generic — never reveal whether the account exists
        return render_template('forgot_pin_methods.html',
                               has_google=False,
                               has_email=False,
                               no_method=True,
                               support_email=SUPPORT_EMAIL)

    conn = get_db()
    user = conn.execute(
        "SELECT google_id, recovery_email, recovery_email_verified FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if not user:
        return render_template('forgot_pin_methods.html',
                               has_google=False, has_email=False, no_method=True,
                               support_email=SUPPORT_EMAIL)

    has_google = bool(user['google_id'])
    has_email  = bool(user['recovery_email'] and user['recovery_email_verified'])

    # Mask the email — never expose the full address
    from services.pin_recovery_service import mask_email
    masked_email = mask_email(user['recovery_email']) if has_email else None

    return render_template(
        'forgot_pin_methods.html',
        has_google=has_google,
        has_email=has_email,
        masked_email=masked_email,
        no_method=(not has_google and not has_email),
        support_email=SUPPORT_EMAIL,
    )


@app.route("/forgot-pin/send-email", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_pin_send_email():
    """
    Step 2b: send a 6-digit recovery code to the verified recovery email.
    Always returns a generic response to prevent enumeration.
    """
    user_id = session.get('recovery_user_id')
    GENERIC_MSG = ("If an account with a recovery email exists, "
                   "we've sent a 6-digit code. Check your inbox.")

    if not user_id:
        flash(GENERIC_MSG, 'info')
        return redirect(url_for('forgot_pin_verify'))

    conn = get_db()
    user = conn.execute(
        "SELECT username, recovery_email, recovery_email_verified FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if not user or not user['recovery_email'] or not user['recovery_email_verified']:
        flash(GENERIC_MSG, 'info')
        return redirect(url_for('forgot_pin_verify'))

    from services.pin_recovery_service import generate_and_send_recovery_code
    ok, reason = generate_and_send_recovery_code(
        user_id, user['recovery_email'], user['username']
    )

    if not ok and reason == 'rate_limited':
        flash("Too many recovery requests. Please wait before trying again.", 'danger')
        return redirect(url_for('forgot_pin_methods'))

    # Always show generic success
    flash(GENERIC_MSG, 'info')
    return redirect(url_for('forgot_pin_verify'))


@app.route("/forgot-pin/google-recover", methods=["POST"])
@limiter.limit("10 per hour")
def forgot_pin_google_recover():
    """
    Step 2c: initiate Google OAuth for PIN recovery.
    We validate server-side that the account has a linked Google ID
    before we even start the OAuth flow.
    """
    user_id = session.get('recovery_user_id')

    if not user_id:
        flash("Recovery session expired. Please start again.", 'danger')
        return redirect(url_for('forgot_pin'))

    conn = get_db()
    user = conn.execute(
        "SELECT google_id FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if not user or not user['google_id']:
        flash("This account does not have a linked Google account.", 'danger')
        return redirect(url_for('forgot_pin_methods'))

    if not os.environ.get('GOOGLE_CLIENT_ID'):
        flash("Google is not configured on this server.", 'danger')
        return redirect(url_for('forgot_pin_methods'))

    # Store intent on server side — do NOT pass via URL parameter
    session['intent'] = 'recover'
    # recovery_user_id is already in session; google_auth will consume it
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/forgot-pin/verify", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def forgot_pin_verify():
    """
    Step 3 (email path): verify the 6-digit code.
    """
    user_id = session.get('recovery_user_id')

    if request.method == "POST":
        if not user_id:
            flash("Recovery session expired. Please start again.", 'danger')
            return redirect(url_for('forgot_pin'))

        code = request.form.get('code', '').strip()

        from services.pin_recovery_service import verify_recovery_code
        ok, reason = verify_recovery_code(user_id, code)

        if not ok:
            if reason == 'max_attempts':
                _clear_recovery_session()
                flash("Too many incorrect attempts. Please start the recovery flow again.", 'danger')
                return redirect(url_for('forgot_pin'))
            elif reason in ('no_active_code', 'wrong_code'):
                remaining_label = ''
                flash(f"Invalid or expired code. Please check and try again.", 'danger')
                return render_template('forgot_pin_verify.html')
            else:
                flash("Something went wrong. Please start again.", 'danger')
                return redirect(url_for('forgot_pin'))

        # Code verified — elevate to reset-capable session
        session['recovery_verified']   = True
        session['recovery_method']     = 'email'
        session['recovery_expires_at'] = (
            datetime.utcnow() + timedelta(minutes=15)
        ).strftime("%Y-%m-%d %H:%M:%S")
        return redirect(url_for('forgot_pin_reset'))

    return render_template('forgot_pin_verify.html')


@app.route("/forgot-pin/reset", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def forgot_pin_reset():
    """
    Step 4: set the new PIN.
    Requires a valid server-side recovery session.
    """
    if not _recovery_session_valid():
        _clear_recovery_session()
        flash("Your recovery session has expired. Please start again.", 'danger')
        return redirect(url_for('forgot_pin'))

    user_id = session.get('recovery_user_id')
    if not user_id:
        _clear_recovery_session()
        return redirect(url_for('forgot_pin'))

    if request.method == "POST":
        new_pin     = request.form.get('new_pin', '').strip()
        confirm_pin = request.form.get('confirm_pin', '').strip()

        if not new_pin.isdigit() or len(new_pin) < 4:
            return render_template('forgot_pin_reset.html',
                                   error="PIN must be at least 4 digits (numbers only).")
        if new_pin != confirm_pin:
            return render_template('forgot_pin_reset.html',
                                   error="PINs do not match. Please try again.")

        hashed = bcrypt.generate_password_hash(new_pin)
        conn = get_db()
        conn.execute("UPDATE users SET pin = ? WHERE id = ?", (hashed, user_id))
        # Invalidate all active recovery tokens for this account
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE pin_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
            (now_str, user_id)
        )
        conn.commit()
        conn.close()

        log_activity(user_id, "PIN_RESET", "PIN reset via recovery flow")
        _clear_recovery_session()

        flash("Your PIN has been reset successfully. Please log in with your new PIN.", 'success')
        return redirect(url_for('login'))

    return render_template('forgot_pin_reset.html')


# =============================================================================
# RECOVERY EMAIL — Settings (add & verify)
# =============================================================================

@app.route("/settings/recovery-email", methods=["POST"])
@limiter.limit("10 per hour")
def set_recovery_email():
    """
    Logged-in user sets a new recovery email.
    Sends a verification code; marks recovery_email_verified = 0 until verified.
    """
    if not require_login():
        return redirect(url_for('login'))

    from utils.validators import validate_email, ValidationError
    new_email = request.form.get('recovery_email', '').strip().lower()

    try:
        new_email = validate_email(new_email)
    except ValidationError as e:
        flash(str(e), 'danger')
        return redirect(url_for('settings'))

    if not new_email:
        flash("Please provide a valid email address.", 'danger')
        return redirect(url_for('settings'))

    user = get_current_user()
    conn = get_db()
    # Save the new (unverified) email immediately
    conn.execute(
        "UPDATE users SET recovery_email = ?, recovery_email_verified = 0 WHERE id = ?",
        (new_email, user['id'])
    )
    conn.commit()

    # Send verification code
    from services.pin_recovery_service import generate_and_send_verification_email
    ok, reason = generate_and_send_verification_email(
        user['id'], new_email, user['username']
    )
    conn.close()

    if not ok:
        if reason == 'rate_limited':
            flash("Too many verification requests. Please wait before trying again.", 'danger')
        else:
            flash("Failed to send verification email. Is RESEND_API_KEY configured?", 'danger')
    else:
        flash("A verification code was sent to your new recovery email. Enter it below to complete verification.", 'success')

    return redirect(url_for('settings'))


@app.route("/settings/verify-recovery-email", methods=["POST"])
@limiter.limit("10 per hour")
def verify_recovery_email():
    """
    Logged-in user submits the 6-digit code to confirm their recovery email.
    """
    if not require_login():
        return redirect(url_for('login'))

    user = get_current_user()
    code = request.form.get('verification_code', '').strip()

    from services.pin_recovery_service import verify_recovery_code
    ok, reason = verify_recovery_code(user['id'], code)

    if not ok:
        if reason == 'max_attempts':
            flash("Too many incorrect attempts. Please request a new code.", 'danger')
        elif reason == 'no_active_code':
            flash("No active verification code found. Please request a new code.", 'danger')
        else:
            flash("Invalid or expired code. Please try again.", 'danger')
        return redirect(url_for('settings'))

    conn = get_db()
    conn.execute(
        "UPDATE users SET recovery_email_verified = 1 WHERE id = ?", (user['id'],)
    )
    conn.commit()
    conn.close()
    flash("Recovery email verified successfully!", 'success')
    return redirect(url_for('settings'))




@app.route("/auth/set-pin", methods=["GET", "POST"])
def set_pin():
    if not require_login():
        return redirect(url_for("login"))
        
    user = get_current_user()
    if user['pin']:
        return redirect(url_for("index"))
        
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if len(pin) < 4 or not pin.isdigit():
            return render_template("set_pin.html", error="Use a 4+ digit numeric PIN.", username=user['username'])
            
        hashed_pin = bcrypt.generate_password_hash(pin)
        conn = get_db()
        conn.execute("UPDATE users SET pin = ? WHERE id = ?", (hashed_pin, user['id']))
        conn.commit()
        conn.close()
        
        flash("PIN successfully set! Welcome to RunRush.", "success")
        return redirect(url_for("onboarding"))
        
    return render_template("set_pin.html", username=user['username'])


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


# ---------- ADMIN USER ANALYTICS ----------

@app.route("/admin/user/<int:target_user_id>/analytics")
def admin_user_analytics(target_user_id):
    """Admin-only: returns full stats, charts, badges for a specific user as JSON."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    current_user = get_current_user()
    role = get_user_role(current_user)
    if role not in ["admin", "moderator"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_db()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (target_user_id,)).fetchone()
    if not target:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    stats = conn.execute("SELECT * FROM user_stats WHERE user_id = ?", (target_user_id,)).fetchone()
    runs  = conn.execute(
        "SELECT * FROM runs WHERE user_id = ? ORDER BY date DESC", (target_user_id,)
    ).fetchall()

    total_runs = len(runs)
    total_km   = sum(r["distance_km"] for r in runs)
    total_cal  = sum(r["calories"]    for r in runs)
    avg_pace   = (sum(r["pace"] for r in runs) / total_runs) if total_runs > 0 else 0

    # Monthly breakdown – last 6 months (no external deps needed)
    today      = date.today()
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    monthly_data   = {}
    monthly_ordered = []
    for i in range(5, -1, -1):
        total_months = today.year * 12 + today.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        key = f"{y}-{m:02d}"
        monthly_data[key]    = 0.0
        monthly_ordered.append((key, f"{month_names[m-1]} '{str(y)[2:]}"))

    for r in runs:
        try:
            key = r["date"][:7]   # "YYYY-MM"
            if key in monthly_data:
                monthly_data[key] += r["distance_km"]
        except Exception:
            pass

    monthly_labels = [lbl  for _, lbl in monthly_ordered]
    monthly_values = [round(monthly_data[key], 2) for key, _ in monthly_ordered]

    # Run-type breakdown
    run_type_breakdown = {}
    for r in runs:
        rt = r["run_type"] or "easy"
        run_type_breakdown[rt] = run_type_breakdown.get(rt, 0) + 1

    # Badges
    badges = conn.execute(
        "SELECT badge_key, unlocked_at FROM user_badges WHERE user_id = ? ORDER BY unlocked_at ASC",
        (target_user_id,)
    ).fetchall()

    conn.close()

    recent_runs = [
        {
            "date":        r["date"],
            "distance_km": round(r["distance_km"], 2),
            "time_min":    round(r["time_min"], 1),
            "pace":        round(r["pace"], 2),
            "calories":    round(r["calories"], 0),
            "run_type":    r["run_type"] or "easy"
        }
        for r in runs[:10]
    ]

    return jsonify({
        "user": {
            "id":           target["id"],
            "username":     target["username"],
            "display_name": target["display_name"] or target["username"],
            "role":         get_user_role(target),
            "status":       target["status"] or "active",
            "last_login":   target["last_login"],
        },
        "stats": {
            "total_runs":     total_runs,
            "total_km":       round(total_km, 2),
            "total_cal":      round(total_cal, 0),
            "avg_pace":       round(avg_pace, 2),
            "current_streak": stats["current_streak"] if stats else 0,
            "best_streak":    stats["best_streak"]    if stats else 0,
        },
        "monthly_chart": {"labels": monthly_labels, "values": monthly_values},
        "run_type_breakdown": run_type_breakdown,
        "badges":      [{"key": b["badge_key"], "unlocked_at": b["unlocked_at"]} for b in badges],
        "recent_runs": recent_runs
    })


@app.route("/api/trigger-weekly-emails", methods=["POST"])
@csrf.exempt  # Called by external cron scheduler; protected by CRON_SECRET shared-secret header
def trigger_weekly_emails():
    """
    Cron-triggered: send weekly summary emails to all opted-in users.

    Authentication: the caller must supply the CRON_SECRET value in the
    'Authorization: Bearer <secret>' header.  This replaces the previous
    admin-session check which is incompatible with automated cron jobs.
    """
    # Authenticate via either CRON_SECRET header or an admin session
    authenticated = False
    current_user = None

    cron_secret = os.environ.get("CRON_SECRET", "")
    auth_header = request.headers.get("Authorization", "")
    
    # 1. Check CRON_SECRET header
    if auth_header and cron_secret:
        provided = auth_header.removeprefix("Bearer ").strip()
        import hmac as _hmac
        if _hmac.compare_digest(provided, cron_secret):
            authenticated = True
            current_user = {"id": 0}  # Sentinel system user

    # 2. Check admin session (fallback)
    if not authenticated and require_login():
        current_user = get_current_user()
        role = get_user_role(current_user)
        if role in ["admin", "moderator"]:
            # Protect the admin session path from CSRF attacks
            from extensions import csrf
            csrf.protect()
            authenticated = True

    if not authenticated:
        if auth_header:
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify({"error": "Forbidden"}), 403

    conn = get_db()
    users_to_email = conn.execute(
        "SELECT id FROM users WHERE email IS NOT NULL AND email != '' AND COALESCE(email_weekly_summary, 1) = 1"
    ).fetchall()
    conn.close()

    sent = 0
    failed = 0
    for u in users_to_email:
        if send_weekly_summary(u["id"]):
            sent += 1
        else:
            failed += 1

    log_activity(current_user["id"], "WEEKLY_EMAILS", f"Sent: {sent}, Failed: {failed}")
    return jsonify({"success": True, "sent": sent, "failed": failed})


from ml_predictor import get_predictions_for_user

@app.route("/api/predict-next-run")
def api_predict_next_run():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    try:
        result = get_predictions_for_user(user["id"], get_db)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error predicting next run: {e}")
        return jsonify({"error": "Failed to predict next run"}), 500

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


# ---------- WEEKLY GOAL ----------

@app.route("/api/weekly-goal", methods=["POST"])
def set_weekly_goal():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
        
    user = get_current_user()
    data = request.get_json()
    
    if not data or 'goal_km' not in data:
        return jsonify({"error": "Missing goal_km"}), 400
        
    try:
        goal_km = float(data['goal_km'])
    except ValueError:
        return jsonify({"error": "Invalid goal_km"}), 400
        
    if goal_km <= 0 or goal_km > 500:
        return jsonify({"error": "Goal must be between 0.1 and 500 km"}), 400
        
    now = datetime.utcnow().isoformat()
    conn = get_db()
    
    # Upsert logic (compatible with both SQLite and Postgres)
    existing = conn.execute("SELECT user_id FROM user_weekly_goals WHERE user_id = ?", (user['id'],)).fetchone()
    
    if existing:
        conn.execute("UPDATE user_weekly_goals SET goal_km = ?, updated_at = ? WHERE user_id = ?", 
                     (goal_km, now, user['id']))
    else:
        conn.execute("INSERT INTO user_weekly_goals (user_id, goal_km, created_at, updated_at) VALUES (?, ?, ?, ?)", 
                     (user['id'], goal_km, now, now))
                     
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "goal_km": goal_km})

@app.route("/api/weekly-goal-progress", methods=["GET"])
def get_weekly_goal_progress():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
        
    user = get_current_user()
    conn = get_db()
    
    goal_row = conn.execute("SELECT goal_km FROM user_weekly_goals WHERE user_id = ?", (user['id'],)).fetchone()
    
    if not goal_row:
        conn.close()
        return jsonify({"goal_km": None})
        
    goal_km = goal_row['goal_km']
    
    # Exactly matching the week boundary calculation from Weekly Leaderboard
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())   # Monday
    week_end = week_start + timedelta(days=6)
    
    lb_start_str = week_start.strftime("%Y-%m-%d")
    lb_end_str = week_end.strftime("%Y-%m-%d")
    
    res = conn.execute("""
        SELECT COALESCE(SUM(distance_km), 0) as current_km 
        FROM runs 
        WHERE user_id = ? AND date BETWEEN ? AND ?
    """, (user['id'], lb_start_str, lb_end_str)).fetchone()
    
    conn.close()
    
    current_km = res['current_km']
    percent_complete = min(100, (current_km / goal_km) * 100) if goal_km > 0 else 0
    days_remaining = (week_end - today).days
    
    return jsonify({
        "goal_km": goal_km,
        "current_km": round(current_km, 2),
        "percent_complete": round(percent_complete, 1),
        "days_remaining_in_week": days_remaining
    })

# ---------- ANALYTICS: MONTHLY COMPARISON ----------

@app.route("/api/analytics/monthly-comparison")
def api_monthly_comparison():
    """Weekly-bucketed distance for this month vs last month."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    user = get_current_user()
    conn = get_db()
    now = datetime.now()

    # --- Date ranges ---
    # This month: 1st of current month → today
    this_month_start = now.replace(day=1)
    this_month_end   = now

    # Last month: 1st of previous month → last day of previous month
    last_month_end   = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    param = "%s" if USE_PG else "?"

    def fetch_runs(start, end):
        return conn.execute(
            f"SELECT date, SUM(distance_km) as total FROM runs "
            f"WHERE user_id = {param} AND date >= {param} AND date <= {param} "
            f"GROUP BY date ORDER BY date",
            (user["id"], start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        ).fetchall()

    def bucket_by_week(runs, month_start, num_days):
        """Aggregate runs into calendar-week buckets (days 1-7, 8-14, 15-21, 22-28, 29+)."""
        weeks = [0.0, 0.0, 0.0, 0.0, 0.0]
        for r in runs:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            week_idx = min((d.day - 1) // 7, 4)
            weeks[week_idx] += r["total"]
        # Only return buckets that fall within the month's days
        used = (num_days - 1) // 7 + 1
        return [round(w, 2) for w in weeks[:used]]

    def make_labels(month_start, month_abbr, num_days):
        """Generate 'Mon D1\u2013D2' labels for each week bucket."""
        import calendar
        labels = []
        starts = [1, 8, 15, 22, 29]
        for s in starts:
            if s > num_days:
                break
            e = min(s + 6, num_days)
            labels.append(f"{month_abbr} {s}\u2013{e}")
        return labels

    import calendar
    days_this = (now - this_month_start).days + 1
    days_last = last_month_end.day

    this_runs = fetch_runs(this_month_start, this_month_end)
    last_runs = fetch_runs(last_month_start, last_month_end)

    this_weeks = bucket_by_week(this_runs, this_month_start, days_this)
    last_weeks = bucket_by_week(last_runs, last_month_start, days_last)

    # Align lengths
    max_len = max(len(this_weeks), len(last_weeks))
    this_weeks += [0.0] * (max_len - len(this_weeks))
    last_weeks += [0.0] * (max_len - len(last_weeks))

    # Use current month's date-range labels (the x-axis represents calendar position)
    this_month_abbr = now.strftime("%b")
    labels = make_labels(this_month_start, this_month_abbr, days_this)
    # Pad labels if last month had more weeks
    while len(labels) < max_len:
        labels.append(f"Wk {len(labels)+1}")

    this_total = round(sum(this_weeks), 2)
    last_total = round(sum(last_weeks), 2)
    delta      = round(this_total - last_total, 2)

    this_month_name = now.strftime("%B")
    last_month_name = last_month_end.strftime("%B")

    conn.close()

    return jsonify({
        "labels":          labels,
        "this_month":      this_weeks,
        "last_month":      last_weeks,
        "this_month_name": this_month_name,
        "last_month_name": last_month_name,
        "this_total":      this_total,
        "last_total":      last_total,
        "delta":           delta,
    })


# ---------- ANALYTICS: PACE TREND ----------

@app.route("/api/analytics/pace-trend")
def api_pace_trend():
    """Average pace per run for the last 90 days, for trend analysis."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    user = get_current_user()
    conn = get_db()
    now = datetime.now()
    since = (now - timedelta(days=90)).strftime("%Y-%m-%d")

    param = "%s" if USE_PG else "?"

    runs = conn.execute(
        f"SELECT date, AVG(pace) as avg_pace, SUM(distance_km) as total_km "
        f"FROM runs WHERE user_id = {param} AND date >= {param} "
        f"GROUP BY date ORDER BY date",
        (user["id"], since)
    ).fetchall()

    if not runs:
        conn.close()
        return jsonify({"labels": [], "paces": [], "trend": []})

    labels = []
    paces  = []
    for r in runs:
        d = datetime.strptime(r["date"], "%Y-%m-%d")
        labels.append(d.strftime("%d %b"))
        paces.append(round(float(r["avg_pace"]), 2))

    # Linear regression for trend line
    n = len(paces)
    if n >= 2:
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(paces) / n
        num   = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, paces))
        denom = sum((x - mean_x) ** 2 for x in xs)
        slope     = num / denom if denom else 0
        intercept = mean_y - slope * mean_x
        trend = [round(slope * x + intercept, 2) for x in xs]
    else:
        slope = 0
        trend = paces[:]

    improving = (trend[-1] < trend[0]) if len(trend) >= 2 else True

    # Magnitude of the trend: slope in sec/km across the full date range
    # slope is in pace-units/run-index; convert to sec/km improvement over the span
    slope_sec_per_km = round(slope * 60, 2) if n >= 2 else 0  # negative = improving

    conn.close()

    return jsonify({
        "labels":           labels,
        "paces":            paces,
        "trend":            trend,
        "improving":        improving,
        "n":                n,
        "slope_sec_per_km": slope_sec_per_km,  # neg = faster per run, pos = slower
    })




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

