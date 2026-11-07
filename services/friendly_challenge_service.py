"""
Friendly Challenges Service (V1)
Handles 1v1 peer challenges: distance, consistency, longest run, and daily distance.
Authoritative scores are computed strictly on demand from the `runs` table.
"""

from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json

from db import get_db, USE_PG

VALID_CHALLENGE_TYPES = {"DISTANCE", "CONSISTENCY", "LONGEST", "DAILY"}
VALID_STATUSES = {"INVITED", "ACCEPTED", "REJECTED", "CANCELLED", "EXPIRED", "COMPLETED"}
SCORE_UNITS = {
    "DISTANCE": "km",
    "CONSISTENCY": "days",
    "LONGEST": "km",
    "DAILY": "km",
}


# ---------------------------------------------------------------------------
# Schema Initialization Primitives
# ---------------------------------------------------------------------------

def create_friendly_challenge_tables(conn=None):
    """
    Creates friendly challenges tables and indexes idempotently.
    Supports both SQLite and PostgreSQL.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        from db import USE_PG as is_pg
        if is_pg:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS friendly_challenges (
                    id SERIAL PRIMARY KEY,
                    challenger_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    opponent_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    challenge_type TEXT NOT NULL,
                    challenge_mode TEXT NOT NULL DEFAULT '1V1',
                    max_participants INTEGER NOT NULL DEFAULT 2,
                    title TEXT,
                    message TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    challenge_timezone TEXT NOT NULL DEFAULT 'UTC',
                    status TEXT NOT NULL DEFAULT 'INVITED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    responded_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    winner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    result_type TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (opponent_id IS NULL OR challenger_id != opponent_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS challenge_participants (
                    id SERIAL PRIMARY KEY,
                    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    invitation_status TEXT NOT NULL DEFAULT 'ACCEPTED',
                    final_score REAL DEFAULT 0.0,
                    score_unit TEXT NOT NULL,
                    result TEXT DEFAULT 'PENDING',
                    rank INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(challenge_id, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS challenge_awards (
                    id SERIAL PRIMARY KEY,
                    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    award_type TEXT NOT NULL DEFAULT 'FRIENDLY_CHALLENGE_WIN',
                    rank INTEGER DEFAULT 1,
                    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(challenge_id, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS challenge_activity (
                    id SERIAL PRIMARY KEY,
                    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
                    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    activity_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ensure columns exist on existing PG databases
            pg_col_migrations = [
                "ALTER TABLE friendly_challenges ADD COLUMN IF NOT EXISTS challenge_mode TEXT NOT NULL DEFAULT '1V1'",
                "ALTER TABLE friendly_challenges ADD COLUMN IF NOT EXISTS max_participants INTEGER NOT NULL DEFAULT 2",
                "ALTER TABLE friendly_challenges ALTER COLUMN opponent_id DROP NOT NULL",
                "ALTER TABLE challenge_participants ADD COLUMN IF NOT EXISTS invitation_status TEXT NOT NULL DEFAULT 'ACCEPTED'",
                "ALTER TABLE challenge_participants ADD COLUMN IF NOT EXISTS rank INTEGER",
                "ALTER TABLE challenge_awards ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 1",
            ]
            for stmt in pg_col_migrations:
                try:
                    conn.execute(stmt)
                except Exception:
                    pass
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS friendly_challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenger_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    opponent_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    challenge_type TEXT NOT NULL,
                    challenge_mode TEXT NOT NULL DEFAULT '1V1',
                    max_participants INTEGER NOT NULL DEFAULT 2,
                    title TEXT,
                    message TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    challenge_timezone TEXT NOT NULL DEFAULT 'UTC',
                    status TEXT NOT NULL DEFAULT 'INVITED',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    responded_at TEXT,
                    expires_at TEXT,
                    completed_at TEXT,
                    winner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    result_type TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    CHECK (opponent_id IS NULL OR challenger_id != opponent_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS challenge_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    invitation_status TEXT NOT NULL DEFAULT 'ACCEPTED',
                    final_score REAL DEFAULT 0.0,
                    score_unit TEXT NOT NULL,
                    result TEXT DEFAULT 'PENDING',
                    rank INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(challenge_id, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS challenge_awards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    award_type TEXT NOT NULL DEFAULT 'FRIENDLY_CHALLENGE_WIN',
                    rank INTEGER DEFAULT 1,
                    awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(challenge_id, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS challenge_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
                    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    activity_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ensure columns exist on existing SQLite databases
            sqlite_col_migrations = [
                "ALTER TABLE friendly_challenges ADD COLUMN challenge_mode TEXT NOT NULL DEFAULT '1V1'",
                "ALTER TABLE friendly_challenges ADD COLUMN max_participants INTEGER NOT NULL DEFAULT 2",
                "ALTER TABLE challenge_participants ADD COLUMN invitation_status TEXT NOT NULL DEFAULT 'ACCEPTED'",
                "ALTER TABLE challenge_participants ADD COLUMN rank INTEGER",
                "ALTER TABLE challenge_awards ADD COLUMN rank INTEGER DEFAULT 1",
            ]
            for stmt in sqlite_col_migrations:
                try:
                    conn.execute(stmt)
                except Exception:
                    pass

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_friendly_challenges_status ON friendly_challenges(status)",
            "CREATE INDEX IF NOT EXISTS idx_friendly_challenges_challenger ON friendly_challenges(challenger_id)",
            "CREATE INDEX IF NOT EXISTS idx_friendly_challenges_opponent ON friendly_challenges(opponent_id)",
            "CREATE INDEX IF NOT EXISTS idx_friendly_challenges_dates ON friendly_challenges(start_date, end_date)",
            "CREATE INDEX IF NOT EXISTS idx_friendly_challenges_mode ON friendly_challenges(challenge_mode)",
            "CREATE INDEX IF NOT EXISTS idx_challenge_participants_user ON challenge_participants(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_challenge_participants_challenge ON challenge_participants(challenge_id)",
            "CREATE INDEX IF NOT EXISTS idx_challenge_participants_invitation_status ON challenge_participants(invitation_status)",
            "CREATE INDEX IF NOT EXISTS idx_challenge_awards_user ON challenge_awards(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_challenge_awards_challenge ON challenge_awards(challenge_id)",
            "CREATE INDEX IF NOT EXISTS idx_challenge_activity_challenge ON challenge_activity(challenge_id)",
        ]
        for idx in indexes:
            try:
                conn.execute(idx)
            except Exception:
                pass
        conn.commit()
    finally:
        if should_close:
            conn.close()


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def validate_timezone(tz_name):
    """Ensure timezone is a valid IANA timezone string."""
    if not tz_name or not isinstance(tz_name, str):
        raise ValueError("Timezone must be a non-empty string.")
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Invalid IANA timezone: '{tz_name}'.")
    return tz_name


def parse_iso_date(date_str):
    """Validates and parses YYYY-MM-DD string into a date object."""
    if not date_str or not isinstance(date_str, str) or len(date_str) != 10:
        raise ValueError(f"Invalid date format: '{date_str}'. Expected 'YYYY-MM-DD'.")
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date: '{date_str}'. Expected valid calendar date in 'YYYY-MM-DD'.")


def validate_challenge_params(challenger_id, opponent_id, challenge_type, start_date_str, end_date_str, tz_name="UTC", title=None, message=None):
    """
    Validates all parameters for creating a new challenge.
    Returns cleaned parameters dictionary.
    """
    if challenger_id is None or opponent_id is None:
        raise ValueError("Challenger ID and Opponent ID are required.")
    
    try:
        c_id = int(challenger_id)
        o_id = int(opponent_id)
    except (ValueError, TypeError):
        raise ValueError("Participant IDs must be valid integers.")

    if c_id == o_id:
        raise ValueError("Cannot challenge yourself.")

    if not challenge_type or challenge_type.upper() not in VALID_CHALLENGE_TYPES:
        raise ValueError(f"Invalid challenge type: '{challenge_type}'. Must be one of: {sorted(VALID_CHALLENGE_TYPES)}.")
    norm_type = challenge_type.upper()

    norm_tz = validate_timezone(tz_name or "UTC")
    start_d = parse_iso_date(start_date_str)
    end_d = parse_iso_date(end_date_str)

    if start_d > end_d:
        raise ValueError(f"Start date ({start_date_str}) cannot be after end date ({end_date_str}).")

    if norm_type == "DAILY":
        if start_d != end_d:
            raise ValueError("Daily challenges must have identical start and end dates.")

    max_days = 365
    if (end_d - start_d).days > max_days:
        raise ValueError(f"Challenge duration cannot exceed {max_days} days.")

    clean_title = (title or "").strip()[:100] or None
    clean_message = (message or "").strip()[:500] or None

    return {
        "challenger_id": c_id,
        "opponent_id": o_id,
        "challenge_type": norm_type,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "challenge_timezone": norm_tz,
        "title": clean_title,
        "message": clean_message,
    }


# ---------------------------------------------------------------------------
# Run Date & Timezone Utilities
# ---------------------------------------------------------------------------

def parse_run_local_date(run_date, tz_name="UTC"):
    """
    Converts a run's `date` or timestamp field to a calendar date (YYYY-MM-DD)
    in the challenge's designated IANA timezone.
    """
    target_tz = ZoneInfo(tz_name)

    if isinstance(run_date, datetime):
        if run_date.tzinfo is None:
            # Naive datetime: assume UTC
            run_date = run_date.replace(tzinfo=timezone.utc)
        return run_date.astimezone(target_tz).strftime("%Y-%m-%d")

    if isinstance(run_date, date):
        return run_date.strftime("%Y-%m-%d")

    if isinstance(run_date, str):
        val = run_date.strip()
        # If it's strictly YYYY-MM-DD (10 chars, digits and hyphens)
        if len(val) == 10 and val.count("-") == 2 and val.replace("-", "").isdigit():
            return val

        # Otherwise parse full datetime
        # Handles 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DDTHH:MM:SS', '...Z', '+00:00', etc.
        try:
            # Replace space with T for ISO format parsing if needed
            iso_val = val.replace(" ", "T")
            dt = datetime.fromisoformat(iso_val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(target_tz).strftime("%Y-%m-%d")
        except ValueError:
            # Fallback to first 10 characters if valid date
            if len(val) >= 10:
                prefix = val[:10]
                if prefix.count("-") == 2 and prefix.replace("-", "").isdigit():
                    return prefix
            raise ValueError(f"Unable to parse run date timestamp: '{run_date}'")

    raise TypeError(f"Unsupported run date type: {type(run_date)}")


# ---------------------------------------------------------------------------
# Authoritative Run Querying & Calculations
# ---------------------------------------------------------------------------

def get_eligible_runs(conn, user_id, start_date_str, end_date_str, tz_name="UTC"):
    """
    Queries all saved, valid, non-deleted runs for a user that fall within the
    challenge window in the challenge's timezone.
    
    Includes GPS, manual, and voice runs (all stored in runs table with distance_km > 0).
    Excludes drafts and deleted runs (drafts aren't in runs; deleted runs are removed).
    """
    # Buffer SQL query by +/- 2 days to account for any timezone offsets
    start_d = parse_iso_date(start_date_str)
    end_d = parse_iso_date(end_date_str)
    buffer_start = (start_d - timedelta(days=2)).strftime("%Y-%m-%d")
    buffer_end = (end_d + timedelta(days=2)).strftime("%Y-%m-%d")

    query = """
        SELECT id, user_id, date, distance_km, time_min, pace, calories,
               run_type, notes, created_at
        FROM runs
        WHERE user_id = ?
          AND distance_km > 0
          AND time_min > 0
          AND substr(CAST(date AS TEXT), 1, 10) >= ?
          AND substr(CAST(date AS TEXT), 1, 10) <= ?
        ORDER BY date ASC, id ASC
    """
    rows = conn.execute(query, (user_id, buffer_start, buffer_end)).fetchall()

    eligible = []
    for r in rows:
        row_dict = dict(r) if hasattr(r, "keys") else {
            "id": r[0], "user_id": r[1], "date": r[2], "distance_km": r[3],
            "time_min": r[4], "pace": r[5], "calories": r[6], "run_type": r[7],
            "notes": r[8], "created_at": r[9]
        }
        local_date = parse_run_local_date(row_dict["date"], tz_name)
        if start_date_str <= local_date <= end_date_str:
            row_dict["local_date"] = local_date
            eligible.append(row_dict)

    return eligible


def calculate_score(eligible_runs, challenge_type):
    """
    Calculates deterministic score and unit from eligible runs.
    Returns (unrounded_score, score_unit).
    """
    norm_type = challenge_type.upper()
    unit = SCORE_UNITS.get(norm_type, "km")

    if not eligible_runs:
        return 0.0, unit

    if norm_type == "DISTANCE":
        score = sum(float(r["distance_km"]) for r in eligible_runs)
        return float(score), unit

    elif norm_type == "CONSISTENCY":
        distinct_days = len(set(r["local_date"] for r in eligible_runs))
        return float(distinct_days), unit

    elif norm_type == "LONGEST":
        max_dist = max((float(r["distance_km"]) for r in eligible_runs), default=0.0)
        return float(max_dist), unit

    elif norm_type == "DAILY":
        score = sum(float(r["distance_km"]) for r in eligible_runs)
        return float(score), unit

    else:
        raise ValueError(f"Unknown challenge type: '{challenge_type}'")


def compare_scores(score_a, score_b, epsilon=1e-5):
    """
    Compares two unrounded scores with floating-point tolerance.
    Returns:
       1 if score_a > score_b (A wins)
      -1 if score_b > score_a (B wins)
       0 if scores are tied (Draw)
    """
    diff = score_a - score_b
    if abs(diff) <= epsilon:
        return 0
    return 1 if diff > 0 else -1


# ---------------------------------------------------------------------------
# Challenge Lifecycle & State Transitions
# ---------------------------------------------------------------------------

def create_challenge(challenger_id, opponent_id, challenge_type, start_date_str, end_date_str,
                     tz_name="UTC", title=None, message=None, expires_hours=48, conn=None):
    """
    Creates a new 1v1 challenge invitation and participant rows in a transaction.
    Returns challenge_id.
    """
    params = validate_challenge_params(
        challenger_id, opponent_id, challenge_type,
        start_date_str, end_date_str, tz_name, title, message
    )

    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        expires_dt = now_dt + timedelta(hours=expires_hours)
        expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Insert challenge
        cursor = conn.execute("""
            INSERT INTO friendly_challenges (
                challenger_id, opponent_id, challenge_type, title, message,
                start_date, end_date, challenge_timezone, status,
                created_at, expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'INVITED', ?, ?, ?)
        """, (
            params["challenger_id"], params["opponent_id"], params["challenge_type"],
            params["title"], params["message"], params["start_date"], params["end_date"],
            params["challenge_timezone"], now_str, expires_str, now_str
        ))

        # Get last inserted id
        chal_row = conn.execute("SELECT id FROM friendly_challenges WHERE challenger_id = ? AND opponent_id = ? ORDER BY id DESC LIMIT 1",
                                (params["challenger_id"], params["opponent_id"])).fetchone()
        challenge_id = chal_row["id"] if hasattr(chal_row, "keys") else chal_row[0]

        unit = SCORE_UNITS[params["challenge_type"]]

        # Insert both participants with initial score 0.0 and PENDING result
        conn.execute("""
            INSERT INTO challenge_participants (challenge_id, user_id, final_score, score_unit, result, created_at, updated_at)
            VALUES (?, ?, 0.0, ?, 'PENDING', ?, ?)
        """, (challenge_id, params["challenger_id"], unit, now_str, now_str))

        conn.execute("""
            INSERT INTO challenge_participants (challenge_id, user_id, final_score, score_unit, result, created_at, updated_at)
            VALUES (?, ?, 0.0, ?, 'PENDING', ?, ?)
        """, (challenge_id, params["opponent_id"], unit, now_str, now_str))

        # Log activity
        meta = json.dumps({"challenge_type": params["challenge_type"], "start_date": params["start_date"], "end_date": params["end_date"]})
        conn.execute("""
            INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, metadata, created_at)
            VALUES (?, ?, 'CREATED', ?, ?)
        """, (challenge_id, params["challenger_id"], meta, now_str))

        conn.commit()
        return challenge_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def get_challenge_by_id(challenge_id, conn=None):
    """Fetches challenge record by ID."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        row = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def check_and_update_expiry(challenge, now_dt=None, conn=None):
    """
    Checks if an unresponded challenge has expired. If so, updates status to EXPIRED.
    Returns True if expired, False otherwise.
    """
    if challenge["status"] != "INVITED":
        return False

    now_dt = now_dt or datetime.now(timezone.utc)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    is_expired = False
    if challenge.get("expires_at"):
        try:
            exp_str = str(challenge["expires_at"])[:19]
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if now_dt >= exp_dt:
                is_expired = True
        except Exception:
            pass

    # Also check if challenge end_date has already passed in its timezone
    tz_name = challenge.get("challenge_timezone") or "UTC"
    current_local_date = now_dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    if current_local_date > challenge["end_date"]:
        is_expired = True

    if is_expired:
        should_close = False
        if conn is None:
            conn = get_db()
            should_close = True
        try:
            conn.execute("""
                UPDATE friendly_challenges
                SET status = 'EXPIRED', updated_at = ?
                WHERE id = ? AND status = 'INVITED'
            """, (now_str, challenge["id"]))
            conn.commit()
            challenge["status"] = "EXPIRED"
            return True
        finally:
            if should_close:
                conn.close()

    return False


def get_challenge_display_status(challenge, now_dt=None):
    """
    Returns the real-time display status:
    - PENDING: status == 'INVITED' and not expired
    - EXPIRED: status == 'EXPIRED' or expired unresponded
    - REJECTED: status == 'REJECTED'
    - CANCELLED: status == 'CANCELLED'
    - When status == 'ACCEPTED':
        - SCHEDULED: local_date < start_date
        - ACTIVE: start_date <= local_date <= end_date
        - COMPLETED: local_date > end_date
    - When status == 'COMPLETED': COMPLETED
    """
    status = challenge.get("status")
    if status == "INVITED":
        return "EXPIRED" if check_and_update_expiry(challenge, now_dt=now_dt) else "PENDING"
    if status in ("REJECTED", "CANCELLED", "EXPIRED"):
        return status
    if status == "COMPLETED":
        return "COMPLETED"

    tz_name = challenge.get("challenge_timezone") or "UTC"
    validate_timezone(tz_name)
    now_dt = now_dt or datetime.now(timezone.utc)
    current_local_date = now_dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")

    if current_local_date < challenge["start_date"]:
        return "SCHEDULED"
    elif current_local_date <= challenge["end_date"]:
        return "ACTIVE"
    else:
        return "COMPLETED"


def accept_challenge(challenge_id, user_id, conn=None):
    """Opponent accepts challenge invitation."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            raise ValueError("Challenge not found.")
        chal = dict(chal)

        if int(chal["opponent_id"]) != int(user_id):
            raise PermissionError("Only the invited opponent can accept this challenge.")

        if check_and_update_expiry(chal, conn=conn):
            raise ValueError("This challenge invitation has expired.")

        if chal["status"] != "INVITED":
            raise ValueError(f"Cannot accept challenge with status '{chal['status']}'.")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE friendly_challenges
            SET status = 'ACCEPTED', responded_at = ?, updated_at = ?
            WHERE id = ?
        """, (now_str, now_str, challenge_id))

        conn.execute("""
            INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, created_at)
            VALUES (?, ?, 'ACCEPTED', ?)
        """, (challenge_id, user_id, now_str))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def reject_challenge(challenge_id, user_id, conn=None):
    """Opponent rejects challenge invitation."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            raise ValueError("Challenge not found.")
        chal = dict(chal)

        if int(chal["opponent_id"]) != int(user_id):
            raise PermissionError("Only the invited opponent can reject this challenge.")

        if chal["status"] != "INVITED":
            raise ValueError(f"Cannot reject challenge with status '{chal['status']}'.")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE friendly_challenges
            SET status = 'REJECTED', responded_at = ?, updated_at = ?
            WHERE id = ?
        """, (now_str, now_str, challenge_id))

        conn.execute("""
            INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, created_at)
            VALUES (?, ?, 'REJECTED', ?)
        """, (challenge_id, user_id, now_str))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def cancel_challenge(challenge_id, user_id, conn=None):
    """Challenger cancels challenge invitation before response."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            raise ValueError("Challenge not found.")
        chal = dict(chal)

        if int(chal["challenger_id"]) != int(user_id):
            raise PermissionError("Only the challenger can cancel this invitation.")

        if chal["status"] != "INVITED":
            raise ValueError(f"Cannot cancel challenge with status '{chal['status']}'.")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE friendly_challenges
            SET status = 'CANCELLED', updated_at = ?
            WHERE id = ?
        """, (now_str, challenge_id))

        conn.execute("""
            INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, created_at)
            VALUES (?, ?, 'CANCELLED', ?)
        """, (challenge_id, user_id, now_str))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


# ---------------------------------------------------------------------------
# Dynamic Score Recalculation & Progress
# ---------------------------------------------------------------------------

def calculate_time_remaining(start_date_str, end_date_str, tz_name="UTC", now_dt=None):
    """Computes human-readable remaining time string in challenge timezone."""
    tz = ZoneInfo(validate_timezone(tz_name))
    now = (now_dt or datetime.now(timezone.utc)).astimezone(tz)
    today = now.date()

    start_d = datetime.strptime(start_date_str[:10], "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date_str[:10], "%Y-%m-%d").date()

    if today < start_d:
        diff = (start_d - today).days
        return f"Starts in {diff} day{'s' if diff != 1 else ''}"
    elif today > end_d:
        return "Completed"
    else:
        diff = (end_d - today).days
        if diff == 0:
            return "Ends today"
        elif diff == 1:
            return "1 day left"
        else:
            return f"{diff} days left"


def calculate_participant_score(conn, user_id, challenge_type, start_date, end_date, tz_name="UTC"):
    """Fetches eligible runs and calculates deterministic score for a participant."""
    runs = get_eligible_runs(conn, user_id, start_date, end_date, tz_name)
    score, unit = calculate_score(runs, challenge_type)
    return score, unit, runs


def get_challenge_progress(challenge_id, conn=None):
    """
    Computes current authoritative progress for both participants.
    Recalculates from the `runs` table every time — never trusts client scores.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            return None
        chal = dict(chal)

        # Check expiry if still invited
        check_and_update_expiry(chal, conn=conn)

        # Challenger & Opponent user info
        challenger_user = conn.execute("SELECT id, username, display_name, profile_emoji FROM users WHERE id = ?",
                                       (chal["challenger_id"],)).fetchone()
        opponent_user = conn.execute("SELECT id, username, display_name, profile_emoji FROM users WHERE id = ?",
                                     (chal["opponent_id"],)).fetchone()

        c_score, unit, c_runs = calculate_participant_score(
            conn, chal["challenger_id"], chal["challenge_type"],
            chal["start_date"], chal["end_date"], chal["challenge_timezone"]
        )
        o_score, unit, o_runs = calculate_participant_score(
            conn, chal["opponent_id"], chal["challenge_type"],
            chal["start_date"], chal["end_date"], chal["challenge_timezone"]
        )

        cmp_result = compare_scores(c_score, o_score)
        if cmp_result == 1:
            leader_id = chal["challenger_id"]
            is_tied = False
        elif cmp_result == -1:
            leader_id = chal["opponent_id"]
            is_tied = False
        else:
            leader_id = None
            is_tied = True

        # Score ratio bar (ratio of current scores, not prediction)
        total_score = c_score + o_score
        if total_score > 0:
            c_ratio = round((c_score / total_score) * 100, 1)
            o_ratio = round((o_score / total_score) * 100, 1)
        else:
            c_ratio = 50.0
            o_ratio = 50.0

        time_remaining = calculate_time_remaining(chal["start_date"], chal["end_date"], chal["challenge_timezone"])

        return {
            "challenge": chal,
            "score_unit": unit,
            "leader_id": leader_id,
            "is_tied": is_tied,
            "ratio_challenger": c_ratio,
            "ratio_opponent": o_ratio,
            "time_remaining": time_remaining,
            "challenger": {
                "user_id": chal["challenger_id"],
                "username": challenger_user["username"] if challenger_user else "",
                "display_name": (challenger_user["display_name"] or challenger_user["username"]) if challenger_user else "",
                "profile_emoji": challenger_user["profile_emoji"] if challenger_user else "🏃",
                "score": c_score,
                "display_score": round(c_score, 2) if unit == "km" else int(c_score),
                "qualifying_runs": c_runs,
            },
            "opponent": {
                "user_id": chal["opponent_id"],
                "username": opponent_user["username"] if opponent_user else "",
                "display_name": (opponent_user["display_name"] or opponent_user["username"]) if opponent_user else "",
                "profile_emoji": opponent_user["profile_emoji"] if opponent_user else "🏃",
                "score": o_score,
                "display_score": round(o_score, 2) if unit == "km" else int(o_score),
                "qualifying_runs": o_runs,
            }
        }
    finally:
        if should_close:
            conn.close()


# ---------------------------------------------------------------------------
# Finalization & Idempotent Awards
# ---------------------------------------------------------------------------

def _send_challenge_notif(conn, user_id, title, message, sender_id=None):
    """Dispatches in-app notification to a user upon challenge finalization."""
    try:
        from db import USE_PG
        actor_id = sender_id or user_id
        if USE_PG:
            n_cur = conn.execute(
                "INSERT INTO notifications (title, message, type, created_by, audience_type) "
                "VALUES (?, ?, 'CHALLENGE_RESULT', ?, 'SPECIFIC_USER') RETURNING id",
                (title, message, actor_id)
            )
            n_id = n_cur.fetchone()["id"]
        else:
            n_cur = conn.execute(
                "INSERT INTO notifications (title, message, type, created_by, audience_type) "
                "VALUES (?, ?, 'CHALLENGE_RESULT', ?, 'SPECIFIC_USER')",
                (title, message, actor_id)
            )
            n_id = n_cur._cursor.lastrowid if hasattr(n_cur, '_cursor') else n_cur.lastrowid

        conn.execute(
            "INSERT INTO user_notifications (notification_id, user_id) VALUES (?, ?)",
            (n_id, user_id)
        )
    except Exception as e:
        print(f"[RunRush] Finalization notification warning: {e}")


def is_challenge_past_end_date(challenge, now_dt=None):
    """
    Checks if current time in challenge's designated timezone is past
    the inclusive challenge end date.
    """
    now_dt = now_dt or datetime.now(timezone.utc)
    tz_name = challenge.get("challenge_timezone") or "UTC"
    current_local_date = now_dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    return current_local_date > challenge["end_date"]


def finalize_challenge_if_due(challenge_id, now_dt=None, conn=None):
    """
    Evaluates challenge completion.
    If the challenge is ACCEPTED and past end_date, computes final scores,
    determines winner/draw, updates participants, and idempotently awards the win medal.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            return None
        chal = dict(chal)

        if chal["status"] != "ACCEPTED":
            return chal

        if not is_challenge_past_end_date(chal, now_dt):
            return chal

        now_dt = now_dt or datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        c_id = chal["challenger_id"]
        o_id = chal["opponent_id"]
        c_score, unit, _ = calculate_participant_score(conn, c_id, chal["challenge_type"], chal["start_date"], chal["end_date"], chal["challenge_timezone"])
        o_score, unit, _ = calculate_participant_score(conn, o_id, chal["challenge_type"], chal["start_date"], chal["end_date"], chal["challenge_timezone"])

        cmp_res = compare_scores(c_score, o_score)
        if cmp_res == 0:
            winner_id = None
            result_type = "DRAW"
            c_result = "DRAW"
            o_result = "DRAW"
        elif cmp_res == 1:
            winner_id = c_id
            result_type = "WIN"
            c_result = "WIN"
            o_result = "LOSS"
        else:
            winner_id = o_id
            result_type = "WIN"
            c_result = "LOSS"
            o_result = "WIN"

        # Update participants
        conn.execute("""
            UPDATE challenge_participants
            SET final_score = ?, result = ?, updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (c_score, c_result, now_str, challenge_id, c_id))

        conn.execute("""
            UPDATE challenge_participants
            SET final_score = ?, result = ?, updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (o_score, o_result, now_str, challenge_id, o_id))

        # Update challenge
        conn.execute("""
            UPDATE friendly_challenges
            SET status = 'COMPLETED', completed_at = ?, winner_id = ?, result_type = ?, updated_at = ?
            WHERE id = ?
        """, (now_str, winner_id, result_type, now_str, challenge_id))

        # Idempotent award creation: only winner gets medal; draw gets none
        if winner_id:
            # Check if award already exists
            existing_award = conn.execute(
                "SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?",
                (challenge_id, winner_id)
            ).fetchone()
            if not existing_award:
                conn.execute("""
                    INSERT INTO challenge_awards (challenge_id, user_id, award_type, awarded_at)
                    VALUES (?, ?, 'FRIENDLY_CHALLENGE_WIN', ?)
                """, (challenge_id, winner_id, now_str))

        # Log completion
        conn.execute("""
            INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, metadata, created_at)
            VALUES (?, ?, 'COMPLETED', ?, ?)
        """, (challenge_id, winner_id or c_id, json.dumps({"winner_id": winner_id, "result_type": result_type}), now_str))

        # Notify participants
        chal_title = chal.get("title") or "Friendly Challenge"
        try:
            if winner_id:
                loser_id = o_id if winner_id == c_id else c_id
                _send_challenge_notif(conn, winner_id, "Challenge Victory! 🏆", f"You won the {chal_title} duel! 1 Friendly Challenges medal awarded.")
                _send_challenge_notif(conn, loser_id, "Challenge Completed", f"The {chal_title} duel has completed. Good effort!")
            else:
                _send_challenge_notif(conn, c_id, "Challenge Completed", f"The {chal_title} duel ended in a tie! 🤝")
                _send_challenge_notif(conn, o_id, "Challenge Completed", f"The {chal_title} duel ended in a tie! 🤝")
        except Exception as n_err:
            print(f"[RunRush] Finalization notification warning: {n_err}")

        conn.commit()

        chal["status"] = "COMPLETED"
        chal["winner_id"] = winner_id
        chal["result_type"] = result_type
        chal["completed_at"] = now_str
        return chal
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def recalibrate_challenge_if_needed(challenge_id, conn=None):
    """
    Safely corrects a COMPLETED challenge if underlying runs were edited or deleted.
    Updates participants' final scores, adjusts winner/draw status, and fixes awards.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal or chal["status"] != "COMPLETED":
            return None
        chal = dict(chal)

        c_id = chal["challenger_id"]
        o_id = chal["opponent_id"]
        c_score, unit, _ = calculate_participant_score(conn, c_id, chal["challenge_type"], chal["start_date"], chal["end_date"], chal["challenge_timezone"])
        o_score, unit, _ = calculate_participant_score(conn, o_id, chal["challenge_type"], chal["start_date"], chal["end_date"], chal["challenge_timezone"])

        cmp_res = compare_scores(c_score, o_score)
        if cmp_res == 0:
            winner_id = None
            result_type = "DRAW"
            c_result = "DRAW"
            o_result = "DRAW"
        elif cmp_res == 1:
            winner_id = c_id
            result_type = "WIN"
            c_result = "WIN"
            o_result = "LOSS"
        else:
            winner_id = o_id
            result_type = "WIN"
            c_result = "LOSS"
            o_result = "WIN"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Update participants
        conn.execute("""
            UPDATE challenge_participants
            SET final_score = ?, result = ?, updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (c_score, c_result, now_str, challenge_id, c_id))

        conn.execute("""
            UPDATE challenge_participants
            SET final_score = ?, result = ?, updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (o_score, o_result, now_str, challenge_id, o_id))

        conn.execute("""
            UPDATE friendly_challenges
            SET winner_id = ?, result_type = ?, updated_at = ?
            WHERE id = ?
        """, (winner_id, result_type, now_str, challenge_id))

        # Adjust awards: remove any award for non-winner
        if winner_id:
            # Remove award if given to loser
            conn.execute("DELETE FROM challenge_awards WHERE challenge_id = ? AND user_id != ?", (challenge_id, winner_id))
            # Ensure winner has award
            has_award = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (challenge_id, winner_id)).fetchone()
            if not has_award:
                conn.execute("""
                    INSERT INTO challenge_awards (challenge_id, user_id, award_type, awarded_at)
                    VALUES (?, ?, 'FRIENDLY_CHALLENGE_WIN', ?)
                """, (challenge_id, winner_id, now_str))
        else:
            # Draw: no awards
            conn.execute("DELETE FROM challenge_awards WHERE challenge_id = ?", (challenge_id,))

        # Audit trail & notification if winner or result changed
        old_winner_id = chal.get("winner_id")
        old_result_type = chal.get("result_type")
        if old_winner_id != winner_id or old_result_type != result_type:
            conn.execute("""
                INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, metadata, created_at)
                VALUES (?, ?, 'RECALIBRATED', ?, ?)
            """, (challenge_id, winner_id or c_id, json.dumps({
                "old_winner_id": old_winner_id,
                "new_winner_id": winner_id,
                "old_result_type": old_result_type,
                "new_result_type": result_type
            }), now_str))

            chal_title = chal.get("title") or "Friendly Challenge"
            try:
                if winner_id:
                    loser_id = o_id if winner_id == c_id else c_id
                    _send_challenge_notif(conn, winner_id, "Result Updated! 🏆", f"After a run update, you won the {chal_title} duel! Friendly Challenges medal awarded.")
                    _send_challenge_notif(conn, loser_id, "Result Updated", f"After a run update, the {chal_title} duel outcome was adjusted.")
                else:
                    _send_challenge_notif(conn, c_id, "Result Updated", f"After a run update, the {chal_title} duel resulted in a tie! 🤝")
                    _send_challenge_notif(conn, o_id, "Result Updated", f"After a run update, the {chal_title} duel resulted in a tie! 🤝")
            except Exception as n_err:
                print(f"[RunRush] Recalibration notification warning: {n_err}")

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def recalibrate_user_challenges_on_run_change(user_id, run_date_str, conn=None):
    """
    Finds any COMPLETED challenges where user is a participant and the run date
    overlaps the challenge window. Calls recalibrate_challenge_if_needed for each affected challenge.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        date_clean = str(run_date_str)[:10]
        rows = conn.execute("""
            SELECT id FROM friendly_challenges
            WHERE (challenger_id = ? OR opponent_id = ?)
              AND status = 'COMPLETED'
              AND start_date <= ? AND end_date >= ?
        """, (user_id, user_id, date_clean, date_clean)).fetchall()

        for r in rows:
            recalibrate_challenge_if_needed(r["id"], conn=conn)
    finally:
        if should_close:
            conn.close()


def get_user_friendly_challenge_stats(user_id, conn=None):
    """
    Returns authoritative summary stats for a user:
    - participated: total accepted/completed challenges
    - wins: count of challenges won
    - losses: count of challenges lost
    - draws: count of challenges drawn
    - medal_count: count of records in challenge_awards
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        # Participated: accepted or completed where user is participant
        part_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM challenge_participants cp
            JOIN friendly_challenges fc ON cp.challenge_id = fc.id
            WHERE cp.user_id = ? AND fc.status IN ('ACCEPTED', 'COMPLETED')
        """, (user_id,)).fetchone()
        participated = int(part_row["cnt"]) if part_row else 0

        # Wins, Losses, Draws from participants table where challenge is COMPLETED
        results_rows = conn.execute("""
            SELECT cp.result, COUNT(*) AS cnt
            FROM challenge_participants cp
            JOIN friendly_challenges fc ON cp.challenge_id = fc.id
            WHERE cp.user_id = ? AND fc.status = 'COMPLETED'
            GROUP BY cp.result
        """, (user_id,)).fetchall()

        wins = 0
        losses = 0
        draws = 0
        for r in results_rows:
            res = r["result"]
            cnt = int(r["cnt"])
            if res == "WIN":
                wins = cnt
            elif res == "LOSS":
                losses = cnt
            elif res == "DRAW":
                draws = cnt

        # Medal count strictly from challenge_awards table
        medal_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM challenge_awards
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        medal_count = int(medal_row["cnt"]) if medal_row else 0

        # Pending incoming invitations count
        inv_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM friendly_challenges
            WHERE opponent_id = ? AND status = 'INVITED'
        """, (user_id,)).fetchone()
        pending_invitations = int(inv_row["cnt"]) if inv_row else 0

        return {
            "participated": participated,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "medal_count": medal_count,
            "pending_invitations": pending_invitations,
        }
    finally:
        if should_close:
            conn.close()


def get_friendly_challenge_medal(user_id, conn=None):
    """
    Returns the Friendly Challenges medal badge representation:
    - Displayed medal: 'Friendly Challenges × N'
    - N = valid challenge wins count from challenge_awards table
    - If N == 0: locked badge
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        medal_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM challenge_awards
            WHERE user_id = ? AND award_type = 'FRIENDLY_CHALLENGE_WIN'
        """, (user_id,)).fetchone()
        medal_count = int(medal_row["cnt"]) if medal_row else 0

        is_earned = medal_count > 0
        name = f"Friendly Challenges × {medal_count}" if is_earned else "Friendly Challenges"
        desc = (
            f"Won {medal_count} 1v1 Friendly Challenge duel{'s' if medal_count != 1 else ''}."
            if is_earned
            else "Win a 1v1 Friendly Challenge against another runner to unlock this medal."
        )

        return {
            "key": "FRIENDLY_CHALLENGES",
            "name": name,
            "icon": "⚔️",
            "description": desc,
            "earned": is_earned,
            "unlocked_at": None,
            "count": medal_count
        }
    finally:
        if should_close:
            conn.close()

